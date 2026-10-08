"""ชั้น staging (ช่วง 2 ส่วนแรก): แปลงไฟล์ raw ของวันหนึ่งเป็นรูปแบบเดียวกัน แล้วกรองเฉพาะ "ประเทศไทย + สายเทคโนโลยี"

ใช้: python -m src.stage            (ใช้วันล่าสุดที่มีใน data/raw)
     python -m src.stage 2026-10-08
ผลลัพธ์: data/staging/postings_<date>.jsonl และพิมพ์สรุปจำนวนที่ผ่าน/ไม่ผ่านแต่ละตัวกรอง
การกันซ้ำข้ามแหล่ง (ช่วง 3) ยังไม่ทำที่นี่ ทำเฉพาะซ้ำแบบเดียวกันทุกตัว (source + id)
"""
from __future__ import annotations

import hashlib
import html
import json
import re
import sys
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

from src.jsonl import write_jsonl

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
STAGING_DIR = ROOT / "data" / "staging"

_WS = re.compile(r"[ \t\r\f\v\xa0\u200b]+")


class _TextExtractor(HTMLParser):
    """แปลง HTML เป็นข้อความ: หัวข้อ/ย่อหน้า/รายการ/แถวตารางขึ้นบรรทัดใหม่ เซลล์ตารางคั่นด้วยช่องว่าง
    ข้อความที่เป็นเครื่องหมาย < > จริงๆ (เช่น "latency < 10ms") ไม่ถูกตัดทิ้งเหมือนการลบแท็กด้วย regex"""
    _BREAK = {"p", "br", "li", "ul", "ol", "div", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "table", "section", "article", "header", "footer"}
    _CELL = {"td", "th"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip += 1
        elif tag in self._BREAK:
            self.parts.append("\n")
        elif tag in self._CELL:
            self.parts.append(" ")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self._skip = max(0, self._skip - 1)
        elif tag in self._BREAK:
            self.parts.append("\n")
        elif tag in self._CELL:
            self.parts.append(" ")

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)


def html_to_text(s: str | None, escaped: bool = False) -> str:
    """escaped=True สำหรับ Greenhouse ซึ่งส่ง HTML มาแบบเข้ารหัสอักขระ (&lt;p&gt;) ต้องถอดรหัสก่อน 1 ชั้น
    (ถ้ายังเห็น &lt; อยู่หลังถอดชั้นแรกโดยไม่มีแท็กเลย แปลว่าเข้ารหัสซ้อน 2 ชั้น จึงถอดอีกชั้น)"""
    if not s:
        return ""
    if escaped:
        s = html.unescape(s)
        if "<" not in s and "&lt;" in s:
            s = html.unescape(s)
    parser = _TextExtractor()
    parser.feed(s)
    parser.close()
    text = "".join(parser.parts)
    lines = [_WS.sub(" ", ln).strip() for ln in text.split("\n")]
    return "\n".join(ln for ln in lines if ln)


def make_job_id(source: str, source_job_id: str) -> str:
    """job_id คงที่: เหมือนเดิมทุกวันตราบที่ประกาศเดิมยังอยู่"""
    return hashlib.sha1(f"{source}:{source_job_id}".encode()).hexdigest()[:16]


def normalize_greenhouse(job: dict, token: str) -> dict:
    offices = [o.get("location") or o.get("name") or "" for o in job.get("offices") or []]
    return {
        "source": "greenhouse",
        "token": token,
        "source_job_id": str(job["id"]),
        "url": job.get("absolute_url"),
        "title": (job.get("title") or "").strip(),
        "company": job.get("company_name") or token,
        "location": (job.get("location") or {}).get("name") or "",
        "location_extra": "; ".join(x for x in offices if x),
        "country_code": None,
        "department": "; ".join(d.get("name", "") for d in job.get("departments") or []),
        "posted_date": (job.get("first_published") or job.get("updated_at") or "")[:10] or None,
        "raw_text": html_to_text(job.get("content"), escaped=True),
        "salary_api": None,
        "internal_job_id": job.get("internal_job_id"),
    }


def normalize_lever(p: dict, token: str) -> dict:
    cats = p.get("categories") or {}
    parts = [p.get("descriptionPlain") or html_to_text(p.get("description"))]
    for lst in p.get("lists") or []:
        parts.append(f"{lst.get('text', '')}\n{html_to_text(lst.get('content'))}")
    parts.append(p.get("additionalPlain") or "")
    created = p.get("createdAt")
    posted = datetime.fromtimestamp(created / 1000, tz=timezone.utc).strftime("%Y-%m-%d") if isinstance(created, (int, float)) else None
    return {
        "source": "lever",
        "token": token,
        "source_job_id": str(p["id"]),
        "url": p.get("hostedUrl"),
        "title": (p.get("text") or "").strip(),
        "company": token,
        "location": cats.get("location") or "",
        "location_extra": "; ".join(cats.get("allLocations") or []),
        "country_code": p.get("country"),
        "department": "; ".join(x for x in [cats.get("department"), cats.get("team")] if x),
        "posted_date": posted,
        "raw_text": "\n\n".join(x.strip() for x in parts if x and x.strip()),
        "salary_api": p.get("salaryRange"),
        "internal_job_id": None,
    }


def load_filters() -> dict:
    cfg = json.loads((ROOT / "config" / "filters.json").read_text(encoding="utf-8"))
    comp = lambda pats: re.compile("|".join(f"(?:{x})" for x in pats), re.I)
    return {
        "th": comp(cfg["thailand_location_patterns"]),
        "title": comp(cfg["tech_title_patterns"]),
        "dept": comp(cfg["tech_department_patterns"]),
        "analyst": re.compile(cfg["generic_analyst_pattern"], re.I),
        "exclude": comp(cfg["exclude_title_patterns"]) if cfg["exclude_title_patterns"] else None,
    }


def is_thailand(rec: dict, f: dict) -> bool:
    if rec.get("country_code") == "TH":
        return True
    return bool(f["th"].search(f"{rec['location']} | {rec['location_extra']}"))


def is_thailand_primary(rec: dict, f: dict) -> bool:
    """สถานที่หลักของประกาศอยู่ในไทย — ไม่นับประกาศที่ระบุหลายประเทศ (มี ; หรือ "A or B") หรือเปิดรับหลายสำนักงาน"""
    loc = rec["location"]
    if ";" in loc or re.search(r"\bor\b", loc, re.I):
        return False
    return bool(f["th"].search(loc)) or (rec.get("country_code") == "TH" and not rec["location_extra"].count(";"))


def is_tech(rec: dict, f: dict) -> bool:
    title = rec["title"]
    if f["exclude"] and f["exclude"].search(title):
        return False
    if f["title"].search(title):
        return True
    # ชื่อแค่ "Analyst" (เช่น Analyst, Pricing) นับเมื่อแผนกเป็นสายเทค/ข้อมูลเท่านั้น
    return bool(f["analyst"].search(title) and f["dept"].search(rec["department"]))


def latest_raw_date() -> str:
    dates = sorted(p.name for p in RAW_DIR.iterdir() if p.is_dir())
    if not dates:
        sys.exit("ยังไม่มีข้อมูลใน data/raw — รัน python -m src.collect ก่อน")
    return dates[-1]


def run(date: str | None = None, active: dict | None = None) -> dict:
    date = date or latest_raw_date()
    f = load_filters()
    counts = {"raw_total": 0, "duplicate_exact": 0, "not_thailand": 0, "thailand_not_tech": 0, "kept": 0, "empty_text": 0}
    seen, kept = set(), []
    active = active or json.loads((ROOT / "config" / "sources.json").read_text(encoding="utf-8"))
    for path in sorted((RAW_DIR / date).glob("*.json")):
        source, token = path.stem.split("__", 1)
        if token not in active.get(source, []):  # บริษัทที่ถอดออกจาก config แล้ว ไม่นำมาใช้
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        items = data.get("jobs", []) if source == "greenhouse" else data
        norm = normalize_greenhouse if source == "greenhouse" else normalize_lever
        for item in items:
            counts["raw_total"] += 1
            rec = norm(item, token)
            key = (rec["source"], rec["source_job_id"])
            if key in seen:
                counts["duplicate_exact"] += 1
                continue
            seen.add(key)
            if not is_thailand(rec, f):
                counts["not_thailand"] += 1
                continue
            if not is_tech(rec, f):
                counts["thailand_not_tech"] += 1
                continue
            if not rec["raw_text"]:
                counts["empty_text"] += 1
            rec["job_id"] = make_job_id(rec["source"], rec["source_job_id"])
            rec["seen_date"] = date
            rec["th_primary"] = is_thailand_primary(rec, f)
            kept.append(rec)
    counts["kept"] = len(kept)
    counts["kept_th_primary"] = sum(r["th_primary"] for r in kept)
    STAGING_DIR.mkdir(parents=True, exist_ok=True)
    out = STAGING_DIR / f"postings_{date}.jsonl"
    write_jsonl(out, kept)
    print(f"วันที่ {date}: " + ", ".join(f"{k}={v}" for k, v in counts.items()))
    print(f"บันทึก {out}")
    return counts


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else None)
