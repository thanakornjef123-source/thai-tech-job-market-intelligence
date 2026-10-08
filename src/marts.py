"""ชั้น marts: รวมทุกวันที่เก็บ + ผลสกัด → ฐานข้อมูล DuckDB สำหรับแดชบอร์ด
ใช้: python -m src.marts   → data/marts/jobs.duckdb
ตาราง
  job_postings        1 แถวต่อประกาศ (หลังกันซ้ำ) พร้อม first_seen / last_seen / is_open (เห็นในการเก็บครั้งล่าสุดหรือไม่)
  posting_attributes  role_family, seniority, เงินเดือน, ภาษา และ "วิธีที่ได้ค่า" (extraction_method)
  posting_skills      job_id × skill
  daily_active        ประกาศที่เห็นในแต่ละวันที่เก็บ (ใช้ทำแนวโน้ม)
  funnel              ต่อวัน: ประกาศดิบทุกประเทศ → ไทย+สายเทค → หลังกันซ้ำ (ใช้แสดงว่าตัวเลขมาจากไหน)
ผลสกัดใช้ Gemini ก่อน ถ้าประกาศไหนยังไม่ได้สกัดด้วย Gemini จะใช้ baseline (พจนานุกรม) และระบุไว้ในคอลัมน์ extraction_method
"""
from __future__ import annotations

import json
from pathlib import Path

from src import baseline, extract, schema
from src.jsonl import read_jsonl
from src.roles import role_family

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "marts" / "jobs.duckdb"


_jsonl = read_jsonl


def _funnel() -> list[tuple]:
    active = json.loads((ROOT / "config" / "sources.json").read_text(encoding="utf-8"))
    last = {}
    for r in _jsonl(ROOT / "data" / "raw" / "runs.jsonl"):   # แถวล่าสุดของแต่ละบริษัทในแต่ละวัน (ล่มแล้วรันซ้ำ → ใช้แถวที่รันซ้ำ)
        if r.get("token") in active.get(r.get("source"), []) and r.get("status") == "ok":
            last[(r["run_date"], r["source"], r["token"])] = r["n_jobs"]
    out = []
    for p in sorted((ROOT / "data" / "staging").glob("canonical_*.jsonl")):
        day = p.stem.split("_", 1)[1]
        raw = sum(n for (d, _, _), n in last.items() if d == day) or None
        out.append((day, raw, len(_jsonl(p.with_name(f"postings_{day}.jsonl"))), len(_jsonl(p))))
    return out


def build() -> dict:
    import duckdb
    extract.load_env()
    posts, seen = {}, []
    for p in sorted((ROOT / "data" / "staging").glob("canonical_*.jsonl")):
        date = p.stem.split("_", 1)[1]
        for r in _jsonl(p):
            seen.append((date, r["job_id"]))
            prev = posts.get(r["job_id"])
            posts[r["job_id"]] = {**r, "first_seen": prev["first_seen"] if prev else date, "last_seen": date}
    ex = _jsonl(extract.OUT)
    gem_model, gem_pv = extract.model_name(), extract.PROMPT_VERSION
    best = {}
    for r in ex:  # ลำดับความสำคัญ: Gemini (รุ่น/prompt ปัจจุบัน) > baseline (รุ่นกฎปัจจุบัน) > คำนวณ baseline สดๆ ด้านล่าง
        if r["model"] == gem_model and r["prompt_version"] == gem_pv:
            best[r["job_id"]] = r
        elif r["model"] == baseline.MODEL and r["prompt_version"] == baseline.VERSION and r["job_id"] not in best:
            best[r["job_id"]] = r
    missing = [j for j in posts if j not in best]
    for j in missing:  # ประกาศใหม่ที่ยังไม่มีผลสกัด (หรือผล baseline เป็นรุ่นเก่า): ใช้ baseline รุ่นปัจจุบันทันที
        r = posts[j]
        raw = {"skills": baseline.skills_from_text(r["raw_text"]), "seniority": baseline.seniority(r["title"], r["raw_text"]),
               "role_family": role_family(r["title"]), "spoken_languages": []}
        best[j] = {"job_id": j, "model": baseline.MODEL, **schema.clean(raw, r["raw_text"])}
    # ถ้าประกาศไหนมีผล Gemini ปะปนกับ baseline ให้แน่ใจว่าชื่อทักษะผ่านตารางชื่อมาตรฐานปัจจุบัน
    for e in best.values():
        e["skills"] = schema.dedupe_skills(e["skills"])
    DB.parent.mkdir(parents=True, exist_ok=True)
    tmp = DB.with_suffix(".tmp.duckdb")
    for leftover in (tmp, tmp.with_name(tmp.name + ".wal")):  # เศษจากรอบที่ดับกลางทาง
        if leftover.exists():
            leftover.unlink()
    con = duckdb.connect(str(tmp))
    con.execute("""CREATE TABLE job_postings(job_id VARCHAR PRIMARY KEY, source VARCHAR, company VARCHAR, title VARCHAR,
        location VARCHAR, th_primary BOOLEAN, url VARCHAR, posted_date DATE, first_seen DATE, last_seen DATE,
        n_duplicates INTEGER, raw_text VARCHAR, is_open BOOLEAN)""")
    last_day = max((d for d, _ in seen), default=None)   # "ยังเปิดอยู่" = เห็นในการเก็บครั้งล่าสุด
    if posts:
        con.executemany("INSERT INTO job_postings VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", [
            (r["job_id"], r["source"], r["company"], r["title"], r["location"], r.get("th_primary"), r["url"],
             r.get("posted_date"), r["first_seen"], r["last_seen"], len(r.get("duplicate_job_ids") or []), r["raw_text"],
             r["last_seen"] == last_day) for r in posts.values()])
    con.execute("""CREATE TABLE posting_attributes(job_id VARCHAR, role_family VARCHAR, seniority VARCHAR, salary_stated BOOLEAN,
        salary_min DOUBLE, salary_max DOUBLE, salary_currency VARCHAR, salary_period VARCHAR, salary_text VARCHAR,
        spoken_languages VARCHAR[], extraction_method VARCHAR)""")
    attrs = [(j, e["role_family"], e["seniority"], e["salary_stated"], e["salary_min"], e["salary_max"], e["salary_currency"],
              e["salary_period"], e["salary_text"], e["spoken_languages"], e["model"]) for j, e in best.items() if j in posts]
    if attrs:
        con.executemany("INSERT INTO posting_attributes VALUES (?,?,?,?,?,?,?,?,?,?,?)", attrs)
    con.execute("CREATE TABLE posting_skills(job_id VARCHAR, skill VARCHAR)")
    sk = [(j, s) for j, e in best.items() if j in posts for s in e["skills"]]
    if sk:
        con.executemany("INSERT INTO posting_skills VALUES (?,?)", sk)
    con.execute("CREATE TABLE daily_active(seen_date DATE, job_id VARCHAR)")
    if seen:
        con.executemany("INSERT INTO daily_active VALUES (?,?)", seen)
    con.execute("CREATE TABLE funnel(day DATE, raw_total INTEGER, thai_tech INTEGER, canonical INTEGER)")
    fun = _funnel()
    if fun:
        con.executemany("INSERT INTO funnel VALUES (?,?,?,?)", fun)
    stats = dict(zip(["postings", "days", "first_day", "last_day"],
                     con.execute("SELECT (SELECT count(*) FROM job_postings), count(DISTINCT seen_date), min(seen_date), max(seen_date) FROM daily_active").fetchone()))
    stats["by_method"] = dict(con.execute("SELECT extraction_method, count(*) FROM posting_attributes GROUP BY 1").fetchall())
    con.close()
    tmp.replace(DB)
    print("marts:", stats, "→", DB)
    return stats


if __name__ == "__main__":
    build()
