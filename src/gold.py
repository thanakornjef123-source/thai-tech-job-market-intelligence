"""ช่วง 4: สร้างชุดทดสอบ (gold) จากประกาศ canonical
ใช้: python -m src.gold sample [--dev 30] [--seed 42]
ผลลัพธ์: data/gold/sample.jsonl  (ประกาศที่ใช้ติดป้าย พร้อม split = dev/test)
- dev  ใช้ดูข้อผิดพลาดและปรับคำสั่ง (prompt)
- test ใช้รายงานตัวเลขเท่านั้น ห้ามดูเพื่อปรับคำสั่ง
ถ้ามี sample อยู่แล้ว จะไม่สุ่มใหม่ (กันชุดทดสอบเปลี่ยนเงียบๆ) เพิ่มประกาศใหม่ด้วย --add เท่านั้น
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

from src.jsonl import read_jsonl, write_jsonl

ROOT = Path(__file__).resolve().parent.parent
GOLD = ROOT / "data" / "gold"
SAMPLE = GOLD / "sample.jsonl"
KEEP = ("job_id", "source", "company", "title", "url", "location", "posted_date", "raw_text")


def load_canonical() -> list[dict]:
    rows = {}
    for p in sorted((ROOT / "data" / "staging").glob("canonical_*.jsonl")):
        for r in read_jsonl(p):
            rows.setdefault(r["job_id"], r)
    return list(rows.values())


def sample(n_dev: int = 30, seed: int = 42, add: bool = False):
    GOLD.mkdir(parents=True, exist_ok=True)
    existing = read_jsonl(SAMPLE)
    if existing and not add:
        sys.exit(f"มี {SAMPLE} อยู่แล้ว ({len(existing)} ประกาศ) ใช้ --add เพื่อเพิ่มประกาศใหม่ที่ยังไม่อยู่ในชุด")
    have = {r["job_id"] for r in existing}
    new = sorted([r for r in load_canonical() if r["job_id"] not in have], key=lambda r: r["job_id"])
    random.Random(seed + len(existing)).shuffle(new)
    n_dev_new = max(0, round(len(new) * n_dev / 80)) if existing else n_dev
    for i, r in enumerate(new):
        existing.append({**{k: r.get(k) for k in KEEP}, "split": "dev" if i < n_dev_new else "test"})
    write_jsonl(SAMPLE, existing)
    print(f"sample: {len(existing)} ประกาศ (dev {sum(r['split']=='dev' for r in existing)}, test {sum(r['split']=='test' for r in existing)}) → {SAMPLE}")


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0] != "sample":
        sys.exit(__doc__)
    sample(int(a[a.index("--dev") + 1]) if "--dev" in a else 30, int(a[a.index("--seed") + 1]) if "--seed" in a else 42, "--add" in a)
