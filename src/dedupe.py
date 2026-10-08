"""ช่วง 3: กันประกาศซ้ำ (ภายในแหล่งเดียวกันและข้ามแหล่ง)

ประกาศ 2 รายการถือว่า "ซ้ำ" เมื่อ
  1) บริษัทเดียวกัน (เทียบชื่อแบบตัดคำว่า Co., Ltd., (Thailand) ฯลฯ) และ
  2a) ชื่อตำแหน่ง (หลังตัดคำบอกสถานที่ เช่น Bangkok-based, relocation provided) ตรงกัน
      และเนื้อหาคล้ายกัน: Jaccard ของชุดคำ 5 คำติดกัน (shingles) >= SIM_THRESHOLD หรือ
  2b) เนื้อหาเกือบเหมือนกันทุกคำ (Jaccard >= NEAR_IDENTICAL) แม้ชื่อตำแหน่งต่างกัน
      — พบจริงใน Agoda: ประกาศเดียวกันลงหลายชื่อ เช่น "Senior Analyst" / "Lead Analyst" ใช้เนื้อหาเดียวกัน 99–100%
      ถือเป็นความต้องการจ้างงานเดียวกัน (ถ้านับแยก ทักษะในประกาศนั้นจะถูกนับซ้ำหลายเท่า)
ประกาศที่ซ้ำจะถูกรวมเป็นกลุ่มเดียว ใช้ตัวแทนเดิมของเมื่อวานถ้ามี ไม่งั้นใช้ประกาศที่เผยแพร่ก่อนสุดเป็นตัวแทน (canonical)

ใช้: python -m src.dedupe [YYYY-MM-DD]
ผลลัพธ์: data/staging/canonical_<date>.jsonl, data/staging/dup_groups_<date>.json
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from src.jsonl import read_jsonl, write_jsonl

ROOT = Path(__file__).resolve().parent.parent
STAGING_DIR = ROOT / "data" / "staging"
SIM_THRESHOLD = 0.8
NEAR_IDENTICAL = 0.95

_LOC_WORDS = re.compile(r"\b(bangkok|thailand|based|relocation|provided|support|remote|hybrid)\b", re.I)
_NONWORD = re.compile(r"[^0-9a-zก-๙\u3040-\u30ff\u4e00-\u9fff]+")
_NOSPACE_SCRIPT = re.compile(r"[ก-๙\u3040-\u30ff\u4e00-\u9fff]")  # ไทย/ญี่ปุ่น/จีน: ไม่เว้นวรรคระหว่างคำ จึงนับด้วยตัวอักษรแทนคำ
_COMPANY_NOISE = re.compile(r"\b(co|ltd|limited|inc|corp|corporation|public|company|thailand|pcl)\b", re.I)


def norm_company(s: str) -> str:
    return _NONWORD.sub(" ", _COMPANY_NOISE.sub(" ", s.lower())).strip()


def norm_title(s: str) -> str:
    s = _LOC_WORDS.sub(" ", s.lower())
    return _NONWORD.sub(" ", s).strip()


def shingles(text: str, k: int = 5) -> set:
    """ชุดของ "คำ k คำติดกัน" (ภาษาที่ไม่เว้นวรรคใช้ตัวอักษร 8 ตัวติดกันแทน)
    ข้อความว่าง → ชุดว่าง (Jaccard = 0 จึงไม่ถูกรวมกับใครโดยบังเอิญ)
    ข้อความสั้นกว่า k คำ → ใช้ทั้งข้อความเป็น 1 ชิ้น (รวมกันได้ก็ต่อเมื่อเหมือนกันทุกคำ)"""
    norm = _NONWORD.sub(" ", text.lower()).strip()
    if not norm:
        return set()
    letters = [ch for ch in norm if ch != " "]
    if len(letters) and sum(bool(_NOSPACE_SCRIPT.match(ch)) for ch in letters) / len(letters) > 0.3:
        flat = "".join(letters)
        n = 8
        return {flat[i:i + n] for i in range(max(1, len(flat) - n + 1))}
    words = norm.split()
    return {" ".join(words[i:i + k]) for i in range(max(1, len(words) - k + 1))}


def jaccard(a: set, b: set) -> float:
    return len(a & b) / len(a | b) if a and b else 0.0


def find_groups(rows: list[dict]) -> list[list[int]]:
    """union-find: คืนกลุ่มของ index ที่ซ้ำกัน (รวมกลุ่มเดี่ยว)"""
    parent = list(range(len(rows)))

    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    sh = [shingles(r["raw_text"]) for r in rows]
    comp = [norm_company(r["company"]) for r in rows]
    title = [norm_title(r["title"]) for r in rows]
    for i in range(len(rows)):
        for j in range(i + 1, len(rows)):
            if comp[i] != comp[j]:
                continue
            sim = jaccard(sh[i], sh[j])
            both_empty = not sh[i] and not sh[j]  # เนื้อหาว่างทั้งคู่: รวมเฉพาะเมื่อชื่อตำแหน่งเหมือนกันเป๊ะ
            if (title[i] == title[j] and (sim >= SIM_THRESHOLD or both_empty)) or sim >= NEAR_IDENTICAL:
                parent[root(j)] = root(i)
    groups: dict[int, list[int]] = {}
    for i in range(len(rows)):
        groups.setdefault(root(i), []).append(i)
    return list(groups.values())


def latest_staging_date() -> str:
    files = sorted(STAGING_DIR.glob("postings_*.jsonl"))
    if not files:
        sys.exit("ยังไม่มี data/staging — รัน python -m src.stage ก่อน")
    return files[-1].stem.split("_", 1)[1]


def previous_canonical_ids(date: str) -> set:
    """job_id ที่เป็นตัวแทน (canonical) ในวันก่อนหน้า — ใช้คงตัวแทนเดิมไว้ ไม่ให้ id เปลี่ยนไปมาเมื่อประกาศที่เก่าสุดในกลุ่มปิดไป"""
    older = sorted(p for p in STAGING_DIR.glob("canonical_*.jsonl") if p.stem.split("_", 1)[1] < date)
    return {r["job_id"] for r in read_jsonl(older[-1])} if older else set()


def run(date: str | None = None) -> dict:
    date = date or latest_staging_date()
    rows = read_jsonl(STAGING_DIR / f"postings_{date}.jsonl")
    groups = find_groups(rows)
    prev = previous_canonical_ids(date)
    canonical, dup_report = [], []
    for g in groups:
        members = sorted((rows[i] for i in g), key=lambda r: (r["job_id"] not in prev, r.get("posted_date") or "9999", r["job_id"]))
        keep = dict(members[0])
        keep["duplicate_job_ids"] = [m["job_id"] for m in members[1:]]
        keep["duplicate_urls"] = [m["url"] for m in members[1:]]
        canonical.append(keep)
        if len(members) > 1:
            dup_report.append([{"job_id": m["job_id"], "title": m["title"], "url": m["url"], "posted_date": m["posted_date"]} for m in members])
    write_jsonl(STAGING_DIR / f"canonical_{date}.jsonl", canonical)
    (STAGING_DIR / f"dup_groups_{date}.json").write_text(json.dumps(dup_report, ensure_ascii=False, indent=1), encoding="utf-8")
    stats = {"date": date, "postings_in": len(rows), "canonical_out": len(canonical),
             "dup_groups": len(dup_report), "postings_removed_as_dup": len(rows) - len(canonical),
             "sim_threshold": SIM_THRESHOLD, "near_identical": NEAR_IDENTICAL}
    print(stats)
    return stats


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else None)
