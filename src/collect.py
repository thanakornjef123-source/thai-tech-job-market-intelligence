"""ชั้น raw: ดึงประกาศจาก API ทางการของ Greenhouse และ Lever แล้วเก็บคำตอบต้นฉบับไว้ไม่แก้

ใช้: python -m src.collect
ผลลัพธ์:
  data/raw/<YYYY-MM-DD>/<source>__<token>.json   คำตอบจาก API (ต้นฉบับ)
  data/raw/runs.jsonl                              บันทึกการเก็บทุกครั้ง (1 บรรทัด/บริษัท)
ไม่เก็บข้อมูลส่วนบุคคล: endpoint ที่ใช้คืนเฉพาะเนื้อหาประกาศ และเราไม่เรียก endpoint สมัครงานเลย
"""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from src.jsonl import append_jsonl

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"

GREENHOUSE_URL = "https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true"
LEVER_URL = "https://api.lever.co/v0/postings/{token}?mode=json&skip={skip}&limit={limit}"
LEVER_PAGE = 100


def load_config() -> dict:
    return json.loads((ROOT / "config" / "sources.json").read_text(encoding="utf-8"))


def http_get_json(url: str, user_agent: str, timeout: int = 30):
    req = urllib.request.Request(url, headers={"User-Agent": user_agent, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_greenhouse(token: str, cfg: dict) -> tuple[object, int]:
    data = http_get_json(GREENHOUSE_URL.format(token=token), cfg["user_agent"])
    return data, len(data.get("jobs", []))


def fetch_lever(token: str, cfg: dict) -> tuple[object, int]:
    postings, skip = [], 0
    while True:
        page = http_get_json(LEVER_URL.format(token=token, skip=skip, limit=LEVER_PAGE), cfg["user_agent"])
        postings.extend(page)
        if len(page) < LEVER_PAGE:
            break
        skip += LEVER_PAGE
        time.sleep(cfg["delay_seconds"])  # robots.txt ของ Lever: Crawl-delay 1
    return postings, len(postings)


FETCHERS = {"greenhouse": fetch_greenhouse, "lever": fetch_lever}


def run(today: str | None = None) -> list[dict]:
    cfg = load_config()
    today = today or datetime.now().strftime("%Y-%m-%d")
    out_dir = RAW_DIR / today
    log_rows = []
    for source, fetch in FETCHERS.items():
        for token in cfg.get(source, []):
            started = datetime.now(timezone.utc).isoformat(timespec="seconds")
            row = {"run_date": today, "fetched_at": started, "source": source, "token": token}
            path = out_dir / f"{source}__{token}.json"
            if path.exists():  # ชั้น raw ไม่เขียนทับ: วันละ 1 ภาพต่อบริษัท
                print(f"[   skipped] {source:<10} {token:<20} มีไฟล์ของวันนี้แล้ว")
                continue
            try:
                data, n = fetch(token, cfg)
                out_dir.mkdir(parents=True, exist_ok=True)  # สร้างโฟลเดอร์ของวันเมื่อเก็บสำเร็จจริงเท่านั้น (วันที่ล่มหมดจะไม่เหลือโฟลเดอร์ว่าง)
                tmp = path.with_name(path.name + ".part")
                tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
                tmp.replace(path)  # เขียนเสร็จแล้วค่อยเปลี่ยนชื่อ: ไฟล์ครึ่งๆ กลางๆ จะไม่ถูกนับว่าเก็บแล้ว
                row.update(status="ok", n_jobs=n, file=str(path.relative_to(ROOT)))
            except urllib.error.HTTPError as e:
                row.update(status="http_error", http_status=e.code, n_jobs=0)
            except Exception as e:  # เครือข่ายล่ม/JSON เสีย: บันทึกแล้วไปบริษัทถัดไป ไม่ให้ทั้งรอบพัง
                row.update(status="error", error=type(e).__name__ + ": " + str(e)[:200], n_jobs=0)
            log_rows.append(row)
            append_jsonl(RAW_DIR / "runs.jsonl", [row])  # บันทึกทันทีทีละบริษัท: ถ้าโดนปิดเครื่องกลางทาง ข้อมูลที่เก็บได้แล้วยังมีบันทึกครบ
            print(f"[{row['status']:>10}] {source:<10} {token:<20} jobs={row['n_jobs']}")
            time.sleep(cfg["delay_seconds"])
    ok = sum(r["status"] == "ok" for r in log_rows)
    print(f"\nเสร็จ: สำเร็จ {ok}/{len(log_rows)} บริษัท, ประกาศทั้งหมด {sum(r['n_jobs'] for r in log_rows)} (ทุกประเทศ ยังไม่กรอง)")
    return log_rows


if __name__ == "__main__":
    rows = run()
    if rows and not any(r["status"] == "ok" for r in rows):
        sys.exit("เก็บไม่สำเร็จเลยสักบริษัท — ตรวจอินเทอร์เน็ต/ไฟร์วอลล์ (ไม่ไปต่อขั้นกรอง เพราะจะได้ข้อมูลว่าง)")
