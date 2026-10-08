import json

import pytest

duckdb = pytest.importorskip("duckdb")

from src import baseline, extract, marts
from src.jsonl import write_jsonl


def post(i, day_text="We use SQL and Python. 3+ years of experience."):
    return {"job_id": f"j{i}", "source": "lever", "company": "Acme", "title": "Data Analyst", "location": "Bangkok",
            "th_primary": True, "url": f"u{i}", "posted_date": "2026-10-01", "raw_text": day_text, "duplicate_job_ids": []}


@pytest.fixture
def env(tmp_path, monkeypatch):
    (tmp_path / "data" / "staging").mkdir(parents=True)
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "sources.json").write_text(json.dumps({"greenhouse": [], "lever": ["acme"]}), encoding="utf-8")
    monkeypatch.setattr(marts, "ROOT", tmp_path)
    monkeypatch.setattr(marts, "DB", tmp_path / "data" / "marts" / "jobs.duckdb")
    monkeypatch.setattr(extract, "OUT", tmp_path / "data" / "extracted" / "extractions.jsonl")
    monkeypatch.setattr(extract, "load_env", lambda: None)
    return tmp_path


def rows(db, sql):
    con = duckdb.connect(str(db), read_only=True)
    try:
        return con.execute(sql).fetchall()
    finally:
        con.close()


def test_two_days_first_last_seen_and_is_open(env):
    write_jsonl(env / "data/staging/canonical_2026-10-07.jsonl", [post(1), post(2)])
    write_jsonl(env / "data/staging/canonical_2026-10-08.jsonl", [post(1), post(3)])
    s = marts.build()
    assert s["postings"] == 3 and s["days"] == 2
    got = {r[0]: r[1:] for r in rows(marts.DB, "SELECT job_id, first_seen::VARCHAR, last_seen::VARCHAR, is_open FROM job_postings")}
    assert got["j1"] == ("2026-10-07", "2026-10-08", True)
    assert got["j2"] == ("2026-10-07", "2026-10-07", False)       # ปิดไปแล้ว
    assert got["j3"] == ("2026-10-08", "2026-10-08", True)


def test_gemini_beats_baseline_and_old_baseline_version_is_ignored(env):
    write_jsonl(env / "data/staging/canonical_2026-10-07.jsonl", [post(1), post(2), post(3)])
    base = lambda j, ver, skills: {"job_id": j, "model": baseline.MODEL, "prompt_version": ver, "skills": skills, "seniority": "mid",
                                   "role_family": "DA", "spoken_languages": [], "salary_stated": False, "salary_min": None, "salary_max": None,
                                   "salary_currency": None, "salary_period": None, "salary_text": None}
    gem = base("j1", extract.PROMPT_VERSION, ["dbt"]); gem["model"] = extract.model_name()
    write_jsonl(extract.OUT, [base("j1", baseline.VERSION, ["SQL"]), gem, base("j2", "rules-v0-old", ["STALE"]), base("j3", baseline.VERSION, ["SQL", "pandas", "Pandas"])])
    marts.build()
    sk = {}
    for j, s in rows(marts.DB, "SELECT job_id, skill FROM posting_skills"):
        sk.setdefault(j, set()).add(s)
    assert sk["j1"] == {"dbt"}                       # Gemini ชนะ baseline
    assert "STALE" not in sk.get("j2", set()) and "SQL" in sk["j2"]   # baseline รุ่นเก่าถูกแทนด้วยการคำนวณใหม่
    assert len([s for s in sk["j3"] if s.lower() == "pandas"]) == 1
    by = dict(rows(marts.DB, "SELECT job_id, extraction_method FROM posting_attributes"))
    assert by["j1"] == extract.model_name() and by["j2"] == baseline.MODEL


def test_funnel_counts_raw_stage_and_canonical(env):
    from src.jsonl import append_jsonl
    write_jsonl(env / "data/staging/postings_2026-10-07.jsonl", [post(1), post(2), post(3)])
    write_jsonl(env / "data/staging/canonical_2026-10-07.jsonl", [post(1), post(2)])
    append_jsonl(env / "data/raw/runs.jsonl", [
        {"run_date": "2026-10-07", "source": "lever", "token": "acme", "status": "error", "n_jobs": 0},
        {"run_date": "2026-10-07", "source": "lever", "token": "acme", "status": "ok", "n_jobs": 500},      # รันซ้ำสำเร็จ
        {"run_date": "2026-10-07", "source": "lever", "token": "removed", "status": "ok", "n_jobs": 999}])  # ไม่อยู่ใน config
    marts.build()
    assert rows(marts.DB, "SELECT raw_total, thai_tech, canonical FROM funnel") == [(500, 3, 2)]


def test_empty_day_does_not_crash(env):
    write_jsonl(env / "data/staging/canonical_2026-10-07.jsonl", [])
    s = marts.build()
    assert s["postings"] == 0
