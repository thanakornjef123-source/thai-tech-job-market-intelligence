"""คำนวณตัวเลขช่วง 2–3 จากไฟล์จริง แล้วเพิ่มลง results.md (ไม่เดา ไม่พิมพ์มือ)
ใช้: python -m src.stats [YYYY-MM-DD]
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

from src import collect, dedupe, extract, stage
from src.jsonl import read_jsonl
from src.roles import role_family

ROOT = Path(__file__).resolve().parent.parent


def compute(date: str) -> list[tuple[str, str, str]]:
    runs = [r for r in read_jsonl(collect.RAW_DIR / "runs.jsonl") if r["run_date"] == date]
    active = json.loads((ROOT / "config" / "sources.json").read_text(encoding="utf-8"))
    last = {}  # ถ้าบริษัทเดียวกันมีหลายแถวในวันเดียว (ล่มแล้วรันซ้ำ) ใช้แถวล่าสุด
    for r in runs:
        if r["token"] in active.get(r["source"], []):
            last[(r["source"], r["token"])] = r
    act = list(last.values())
    stg = read_jsonl(stage.STAGING_DIR / f"postings_{date}.jsonl")
    can = read_jsonl(stage.STAGING_DIR / f"canonical_{date}.jsonl")
    fams = Counter(role_family(r["title"]) for r in can)
    comp = Counter(r["company"] for r in can)
    src_raw = f"data/raw/runs.jsonl, data/raw/{date}/"
    gold = read_jsonl(ROOT / "data" / "gold" / "sample.jsonl")
    done = {r["job_id"] for r in read_jsonl(extract.OUT) if r["model"] == extract.model_name() and r["prompt_version"] == extract.PROMPT_VERSION}
    by_split = {sp: (sum(g["job_id"] in done for g in gold if g["split"] == sp), sum(g["split"] == sp for g in gold)) for sp in ("dev", "test")}
    out = [
        ("บริษัทที่เก็บสำเร็จ / ทั้งหมดที่ใช้", f"{sum(r['status']=='ok' for r in act)} / {len(act)}", src_raw),
        ("ประกาศดิบทุกประเทศ (บริษัทที่ใช้)", str(sum(r["n_jobs"] for r in act)), src_raw),
        ("ประกาศไทย + สายเทค (ก่อนกันซ้ำ)", str(len(stg)), f"`python -m src.stage {date}` → postings_{date}.jsonl"),
        ("  ในนั้น สถานที่หลักอยู่ในไทย", str(sum(r.get("th_primary", False) for r in stg)), "field th_primary"),
        ("หลังกันซ้ำ (canonical)", str(len(can)), f"`python -m src.dedupe {date}` → canonical_{date}.jsonl"),
        ("ประกาศที่ถูกรวมเพราะซ้ำ", f"{len(stg)-len(can)} ({len([c for c in can if c['duplicate_job_ids']])} กลุ่ม)", f"dup_groups_{date}.json · เกณฑ์ Jaccard {dedupe.SIM_THRESHOLD}/{dedupe.NEAR_IDENTICAL}"),
        ("ประกาศที่มีอักษรไทยในเนื้อหา", str(sum(any('฀' <= ch <= '๿' for ch in r["raw_text"]) for r in can)), "canonical"),
        ("ประกาศที่ API ให้ช่วงเงินเดือน", str(sum(r.get("salary_api") is not None for r in can)), "canonical field salary_api"),
        ("กลุ่มตำแหน่ง (กฎจากชื่อ)", ", ".join(f"{k} {v}" for k, v in fams.most_common()), "src/roles.py + config/role_families.json"),
        ("บริษัท", ", ".join(f"{k} {v}" for k, v in comp.most_common()), "canonical"),
        (f"ชุดทดสอบที่สกัดด้วย {extract.model_name()} แล้ว (dev / test)", f"{by_split['dev'][0]}/{by_split['dev'][1]} / {by_split['test'][0]}/{by_split['test'][1]}",
         "data/extracted/extractions.jsonl · data/gold/sample.jsonl"),
    ]
    return out


def run(date: str | None = None, force: bool = False):
    """เพิ่มหัวข้อ "การเก็บข้อมูล <วัน>" ลง results.md — วันเดียวกันรันซ้ำจะไม่เพิ่มซ้ำ (ใช้ --force เพื่อคำนวณใหม่แทนที่ของเดิม)"""
    date = date or dedupe.latest_staging_date()
    path = ROOT / "results.md"
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    heading = f"### การเก็บข้อมูล {date}"
    if heading in text and not force:
        print(f"results.md มีตัวเลขของ {date} แล้ว — ข้าม (ใช้ --force เพื่อคำนวณใหม่)")
        return
    rows = compute(date)
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [f"| {stamp} | {k.strip()} | {v} | {s} |" for k, v, s in rows]
    print("\n".join(lines))
    block = heading + "\n\n| คำนวณเมื่อ (เวลาเครื่องที่รัน) | ตัวชี้วัด | ค่า | คำสั่ง/ไฟล์ที่มา |\n|---|---|---|---|\n" + "\n".join(lines) + "\n"
    if heading in text:  # แทนที่เฉพาะหัวข้อของวันนั้น จนถึงหัวข้อถัดไป
        text = re.sub(re.escape(heading) + r".*?(?=\n#{2,3} |\Z)", lambda m: block.rstrip("\n") + "\n", text, count=1, flags=re.S)
    else:
        text = text.rstrip("\n") + "\n\n" + block
    path.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    run(args[0] if args else None, force="--force" in sys.argv)
