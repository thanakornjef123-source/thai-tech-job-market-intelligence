import json

import duckdb

from src import snapshot


def _make_db(path):
    con = duckdb.connect(str(path))
    con.execute("CREATE TABLE job_postings (job_id VARCHAR, title VARCHAR, raw_text VARCHAR)")
    con.execute("INSERT INTO job_postings VALUES ('a', 'Data Analyst', 'Contact jane.doe@example.com or +66 81 234 5678. SQL required.'), ('b', 'BA', NULL)")
    con.execute("CREATE TABLE posting_attributes (job_id VARCHAR, role_family VARCHAR)")
    con.execute("INSERT INTO posting_attributes VALUES ('a', 'DA'), ('b', 'BA')")
    con.execute("CREATE TABLE posting_skills (job_id VARCHAR, skill VARCHAR)")
    con.execute("INSERT INTO posting_skills VALUES ('a', 'SQL')")
    con.execute("CREATE TABLE daily_active (seen_date DATE, job_id VARCHAR)")
    con.execute("INSERT INTO daily_active VALUES ('2026-10-07', 'a')")
    con.execute("CREATE TABLE funnel (day DATE, raw_total INTEGER, thai_tech INTEGER, canonical INTEGER)")
    con.execute("INSERT INTO funnel VALUES ('2026-10-07', 10, 3, 2)")
    con.close()


def test_redact_removes_email_and_phone():
    out = snapshot.redact("mail a.b@c.co.th tel 02-123-4567 or 0812345678")
    assert "@" not in out and "123-4567" not in out and "0812345678" not in out
    assert snapshot.redact(None) is None
    assert snapshot.redact("Python 3.10, 5+ years") == "Python 3.10, 5+ years"


def test_export_writes_all_tables_and_creates_folder(tmp_path):
    db = tmp_path / "marts" / "jobs.duckdb"
    db.parent.mkdir()
    _make_db(db)
    out = tmp_path / "nested" / "snapshot"          # โฟลเดอร์ปลายทางยังไม่มี ต้องสร้างเอง
    meta = snapshot.export(db, out)
    for t in snapshot.TABLES:
        assert (out / f"{t}.parquet").exists()
    assert meta["rows"]["job_postings"] == 2
    assert json.loads((out / "meta.json").read_text(encoding="utf-8"))["rows"]["funnel"] == 1
    con = duckdb.connect()
    text = con.execute(f"SELECT raw_text FROM read_parquet('{(out / 'job_postings.parquet').as_posix()}') WHERE job_id = 'a'").fetchone()[0]
    assert "jane.doe" not in text and "234 5678" not in text and "SQL required" in text
    # ส่งออกซ้ำได้ (ทับของเดิม) และไม่เหลือโฟลเดอร์ชั่วคราว
    snapshot.export(db, out)
    assert not (out.parent / "snapshot.tmp").exists()


def test_export_without_db_raises(tmp_path):
    try:
        snapshot.export(tmp_path / "missing.duckdb", tmp_path / "snap")
    except FileNotFoundError:
        return
    raise AssertionError("expected FileNotFoundError")
