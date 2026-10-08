import json
import urllib.error

from src import collect


def setup(monkeypatch, tmp_path, fetchers):
    monkeypatch.setattr(collect, "RAW_DIR", tmp_path / "raw")
    monkeypatch.setattr(collect, "ROOT", tmp_path)
    monkeypatch.setattr(collect, "load_config", lambda: {"user_agent": "t", "delay_seconds": 0, "greenhouse": ["a", "b"], "lever": ["c"]})
    monkeypatch.setattr(collect, "FETCHERS", fetchers)
    monkeypatch.setattr(collect.time, "sleep", lambda s: None)


def test_logs_each_company_immediately_and_survives_errors(monkeypatch, tmp_path):
    def gh(token, cfg):
        if token == "b":
            raise urllib.error.HTTPError("u", 503, "x", {}, None)
        return {"jobs": [1, 2]}, 2
    setup(monkeypatch, tmp_path, {"greenhouse": gh, "lever": lambda t, c: ([1], 1)})
    rows = collect.run("2026-10-08")
    assert [r["status"] for r in rows] == ["ok", "http_error", "ok"]
    log = [json.loads(l) for l in (tmp_path / "raw" / "runs.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(log) == 3 and log[1]["http_status"] == 503
    assert sorted(p.name for p in (tmp_path / "raw" / "2026-10-08").iterdir()) == ["greenhouse__a.json", "lever__c.json"]


def test_same_day_rerun_skips_existing_files(monkeypatch, tmp_path):
    calls = []
    def gh(token, cfg):
        calls.append(token)
        return {"jobs": []}, 0
    setup(monkeypatch, tmp_path, {"greenhouse": gh, "lever": gh})
    collect.run("2026-10-08"); collect.run("2026-10-08")
    assert calls == ["a", "b", "c"]


def test_total_failure_leaves_no_empty_day_folder(monkeypatch, tmp_path):
    def boom(token, cfg):
        raise OSError("network down")
    setup(monkeypatch, tmp_path, {"greenhouse": boom, "lever": boom})
    rows = collect.run("2026-10-08")
    assert all(r["status"] == "error" for r in rows)
    assert not (tmp_path / "raw" / "2026-10-08").exists()
    assert len((tmp_path / "raw" / "runs.jsonl").read_text(encoding="utf-8").splitlines()) == 3
