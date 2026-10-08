"""ตัวเทียบ (baseline) แบบไม่ใช้ LLM: จับคำจากพจนานุกรมทักษะ (config/skills.json) + กฎจากชื่อตำแหน่ง/จำนวนปี
มีไว้ตอบคำถามสัมภาษณ์ว่า "ใช้ LLM แล้วดีกว่าวิธีง่ายๆ แค่ไหน" — วัดด้วย evaluate.py ชุดเดียวกัน
ใช้: python -m src.baseline [--gold]   → เขียนลง data/extracted/extractions.jsonl (model = baseline-dict)
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

from src import extract, schema
from src.jsonl import append_jsonl
from src.roles import role_family

ROOT = Path(__file__).resolve().parent.parent

MODEL = "baseline-dict"
CODE_VERSION = "rules-v2"   # เปลี่ยนเลขนี้ทุกครั้งที่แก้ตรรกะในไฟล์นี้ (config ที่แก้ → hash ด้านล่างเปลี่ยนเอง)


def _config_hash() -> str:
    """hash ของพจนานุกรมทักษะ + กฎกลุ่มตำแหน่ง: แก้ config แล้วผลสกัดแบบ baseline ที่ cache ไว้จะถูกคำนวณใหม่เอง ไม่ค้างของเก่า"""
    cfg = ROOT / "config"
    h = hashlib.sha1()
    for name in ("skills.json", "role_families.json"):
        h.update((cfg / name).read_bytes())
    return h.hexdigest()[:6]


VERSION = f"{CODE_VERSION}-{_config_hash()}"
_YEARS = re.compile(r"(\d{1,2})\s*(?:\+|\s*-\s*\d+\+?)?\s*(?:\+\s*)?years?", re.I)

# คำที่เป็นทั้งชื่อเทคโนโลยีและคำอังกฤษทั่วไป (swift/react/node/spark/hive/ruby): นับเมื่อเขียนขึ้นต้นด้วยตัวพิมพ์ใหญ่เท่านั้น
_CASE_SENSITIVE = {"swift", "react", "node", "ruby", "spark", "hive"}
_CONTEXT = {
    # Go: ตัว G ใหญ่ ไม่ใช่ go-to-market / go/no-go / "you go looking"; golang เขียนเล็กได้
    "go": r"(?i:\bgolang\b)|(?<![\w/-])Go\b(?![- ]to\b)(?![ ]?/[ ]?no)(?=[ ,/);.]|$)",
    # R: ตัว R ใหญ่เดี่ยวๆ คั่นด้วยคอมมา/วรรค/ท้ายบรรทัด/จุด ไม่ใช่ R&D
    "r": r"(?<![\w&-])R(?=[ ,/);.]|$)(?!&D)",
    "excel": r"(?i:\bexcel\b(?!lence|lent))",
    "oracle": r"(?i:\boracle\b)",
}
_AMBIGUOUS = {"c", "agents", "lambda", "algorithms", "spring", "regression", "rest", "api", "experimentation", "spreadsheets"}  # ไม่นับเลยถ้าไม่มีกฎบริบท


@lru_cache
def _patterns():
    out = []
    for alias, canon in schema._aliases().items():
        if len(alias) <= 2 and alias not in {"r", "go", "c#", "ml", "js", "rl"}:
            continue
        if alias in _CONTEXT:
            out.append((re.compile(_CONTEXT[alias], re.M), canon))
        elif alias in _AMBIGUOUS:
            continue
        elif alias in _CASE_SENSITIVE:
            out.append((re.compile(r"(?<![\w])" + re.escape(alias.capitalize()) + r"(?![\w])"), canon))
        else:
            out.append((re.compile(r"(?<![\w])" + re.escape(alias) + r"(?![\w])", re.I), canon))
    return out


def skills_from_text(text: str) -> list[str]:
    return sorted({canon for rx, canon in _patterns() if rx.search(text)}, key=str.lower)


_TITLE_LEVELS = [   # เรียงจากสูงไปต่ำ: ชื่อตำแหน่งที่มีหลายคำระดับ (เช่น Senior Lead, Lead Manager/Associate Director) ใช้ระดับสูงสุด
    ("intern", re.compile(r"\bintern(?:ship)?s?\b|accelerator program", re.I)),
    ("manager", re.compile(r"\bhead of\b|\bdirector\b|\bengineering manager\b|\b(?:senior|lead) manager\b|^\W*manager\b", re.I)),
    ("lead", re.compile(r"\blead\b|\bstaff\b|\bprincipal\b", re.I)),
    ("senior", re.compile(r"\bsenior\b|\bsr\.?(?=\s)|\bassociate manager\b", re.I)),   # Associate Manager ที่ไม่มีลูกทีม = senior (นิยามใน schema.DEFINITIONS)
    ("junior", re.compile(r"\bjunior\b|\bassociate\b|\bnew grad(?:uate)?\b|\bgraduate\b", re.I)),
]


def seniority(title: str, text: str) -> str:
    for lvl, rx in _TITLE_LEVELS:
        if rx.search(title):
            return lvl
    # ไม่มีคำระบุระดับในชื่อ: ดูจำนวนปีที่ประกาศขอ — ใช้ค่าสูงสุดที่อยู่ใกล้คำว่า experience (ตัวเลขเช่น "1 year of Python" ใน 7+ years ไม่ควรฉุดให้เป็น junior)
    yrs = []
    for m in _YEARS.finditer(text):
        y = int(m.group(1))
        if y < 30 and "experience" in text[max(0, m.start() - 100): m.end() + 100].lower():
            yrs.append(y)
    if not yrs:
        return "unknown"
    y = max(yrs)
    return "junior" if y < 2 else "mid" if y < 5 else "senior"


def run(gold: bool = False):
    done = extract.already_done()
    targets = [r for r in extract.load_targets(gold) if (r["job_id"], MODEL, VERSION) not in done]
    rows = []
    for r in targets:
        raw = {"skills": skills_from_text(r["raw_text"]), "seniority": seniority(r["title"], r["raw_text"]),
               "role_family": role_family(r["title"]), "spoken_languages": []}
        rows.append({"job_id": r["job_id"], "model": MODEL, "prompt_version": VERSION,
                     "extracted_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                     "input_tokens": 0, "output_tokens": 0, "raw_output": raw, **schema.clean(raw, r["raw_text"])})
    append_jsonl(extract.OUT, rows)
    print(f"baseline ({VERSION}): สกัด {len(targets)} ประกาศ → {extract.OUT}")


if __name__ == "__main__":
    run(gold="--gold" in sys.argv)
