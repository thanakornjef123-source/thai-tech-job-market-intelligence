"""ตรวจความผิดปกติหลังเก็บข้อมูลแต่ละวัน (กันกรณีเว็บ/API เปลี่ยนจนตัวเก็บพังแบบเงียบๆ)
ใช้: python -m src.check  → ออกด้วยรหัส 1 ถ้าผิดปกติ (run_daily.bat จะแจ้งเตือน) และเขียน data/health.json ให้แดชบอร์ดแสดง
กฎ
  (1) ไม่มีบันทึกการเก็บของ "วันนี้" เลย (ตัวเก็บไม่ได้รัน/ล่มก่อนเริ่ม)
  (2) บริษัทใดเก็บไม่สำเร็จ — ดูครั้งล่าสุดของวันนั้น (ถ้าล่มแล้วรันซ้ำสำเร็จ ถือว่าผ่าน)
  (3) บริษัทใดได้ 0 ประกาศทั้งที่ครั้งก่อนมี
  (4) ประกาศไทย+สายเทคหลังกันซ้ำลดลงเกิน 50% จากวันก่อน
นับเฉพาะบริษัทที่ยังอยู่ใน config/sources.json
"""
from __future__ import annotations

import json
import sys
from datetime import date, datetime
from pathlib import Path

from src.jsonl import read_jsonl

ROOT = Path(__file__).resolve().parent.parent


def evaluate(runs: list[dict], active: dict, n_today: int, n_prev: int | None, today_real: str) -> tuple[str, list[str]]:
    """แยกเป็นฟังก์ชันล้วนๆ เพื่อทดสอบได้ — คืน (run_date ล่าสุด, รายการปัญหา)"""
    runs = [r for r in runs if r.get("token") in active.get(r.get("source"), [])]
    problems: list[str] = []
    if not runs:
        return today_real, ["ยังไม่มีบันทึกการเก็บข้อมูลเลย"]
    run_date = max(r["run_date"] for r in runs)
    if run_date != today_real:
        problems.append(f"ไม่มีการเก็บข้อมูลของวันนี้ ({today_real}) — ครั้งล่าสุดคือ {run_date}")
    latest: dict = {}
    prev_ok: dict = {}
    for r in runs:  # runs.jsonl เรียงตามเวลา: ตัวหลังชนะ
        key = (r["source"], r["token"])
        if r["run_date"] == run_date:
            latest[key] = r
        elif r["status"] == "ok":
            prev_ok[key] = r
    for src, tokens in active.items():
        if src.startswith("_") or not isinstance(tokens, list):
            continue
        for tok in tokens:
            if (src, tok) not in latest:
                problems.append(f"{src}/{tok}: ไม่มีบันทึกการเก็บของวันที่ {run_date}")
    for (src, tok), r in latest.items():
        if r["status"] != "ok":
            problems.append(f"{src}/{tok}: {r['status']} {r.get('http_status') or r.get('error', '')}".strip())
        elif r["n_jobs"] == 0 and prev_ok.get((src, tok), {}).get("n_jobs", 0) > 0:
            problems.append(f"{src}/{tok}: ได้ 0 ประกาศ (ครั้งก่อน {prev_ok[(src, tok)]['n_jobs']})")
    if n_prev and n_today < 0.5 * n_prev:
        problems.append(f"ประกาศไทย+สายเทคลดจาก {n_prev} เหลือ {n_today}")
    return run_date, problems


def run() -> int:
    runs = read_jsonl(ROOT / "data" / "raw" / "runs.jsonl")
    active = json.loads((ROOT / "config" / "sources.json").read_text(encoding="utf-8"))
    can = sorted((ROOT / "data" / "staging").glob("canonical_*.jsonl"))
    n_today = len(read_jsonl(can[-1])) if can else 0
    n_prev = len(read_jsonl(can[-2])) if len(can) > 1 else None
    run_date, problems = evaluate(runs, active, n_today, n_prev, date.today().isoformat())
    health = {"checked_at": datetime.now().isoformat(timespec="seconds"), "run_date": run_date,
              "canonical_today": n_today, "canonical_prev": n_prev, "ok": not problems, "problems": problems}
    (ROOT / "data").mkdir(exist_ok=True)
    (ROOT / "data" / "health.json").write_text(json.dumps(health, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(health, ensure_ascii=False))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(run())
