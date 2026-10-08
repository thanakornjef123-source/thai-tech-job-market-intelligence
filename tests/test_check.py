from src import check

ACTIVE = {"greenhouse": ["agoda"], "lever": ["coda"]}


def row(date, src, tok, status="ok", n=10, **kw):
    return {"run_date": date, "source": src, "token": tok, "status": status, "n_jobs": n, **kw}


def test_all_ok_today():
    runs = [row("2026-10-08", "greenhouse", "agoda"), row("2026-10-08", "lever", "coda")]
    d, problems = check.evaluate(runs, ACTIVE, 80, 80, "2026-10-08")
    assert d == "2026-10-08" and problems == []


def test_error_then_successful_retry_same_day_is_ok():
    runs = [row("2026-10-08", "greenhouse", "agoda", "error", 0, error="Timeout"), row("2026-10-08", "lever", "coda"),
            row("2026-10-08", "greenhouse", "agoda")]
    assert check.evaluate(runs, ACTIVE, 80, 80, "2026-10-08")[1] == []


def test_error_without_retry_is_reported():
    runs = [row("2026-10-08", "greenhouse", "agoda", "http_error", 0, http_status=503), row("2026-10-08", "lever", "coda")]
    problems = check.evaluate(runs, ACTIVE, 80, 80, "2026-10-08")[1]
    assert len(problems) == 1 and "agoda" in problems[0] and "503" in problems[0]


def test_stale_data_is_reported():
    runs = [row("2026-10-07", "greenhouse", "agoda"), row("2026-10-07", "lever", "coda")]
    problems = check.evaluate(runs, ACTIVE, 80, 80, "2026-10-08")[1]
    assert any("วันนี้" in p for p in problems)


def test_zero_jobs_and_drop_and_missing_company():
    runs = [row("2026-10-07", "greenhouse", "agoda", n=50), row("2026-10-08", "greenhouse", "agoda", n=0)]
    problems = check.evaluate(runs, ACTIVE, 30, 80, "2026-10-08")[1]
    text = " ".join(problems)
    assert "0 ประกาศ" in text and "ลดจาก 80 เหลือ 30" in text and "lever/coda" in text


def test_removed_companies_are_ignored_and_empty_log():
    runs = [row("2026-10-08", "lever", "tsmg", "error", 0), row("2026-10-08", "greenhouse", "agoda"), row("2026-10-08", "lever", "coda")]
    assert check.evaluate(runs, ACTIVE, 80, 80, "2026-10-08")[1] == []
    assert check.evaluate([], ACTIVE, 0, None, "2026-10-08")[1] == ["ยังไม่มีบันทึกการเก็บข้อมูลเลย"]
