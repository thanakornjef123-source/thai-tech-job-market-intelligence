"""รูปแบบผลสกัด (ใช้ร่วมกันทั้งผลจาก LLM และป้ายที่คนตรวจ) + ตัวทำความสะอาด/ตรวจกันมั่ว"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SENIORITY = ["intern", "junior", "mid", "senior", "lead", "manager", "unknown"]
ROLE_FAMILIES = ["BA", "SA", "DA", "DS/ML", "Data Eng", "Software Eng", "Product", "Other tech"]
PERIODS = ["month", "year", "hour", "day", None]
LANG_ALIASES = {"mandarin": "Chinese", "chinese (mandarin)": "Chinese", "thai": "Thai", "english": "English"}

DEFINITIONS = """\
- skills: named technical skills the posting mentions as required, preferred, OR as part of the role's tech stack
  (e.g. "we use Scala and Kafka"). Include: programming languages, frameworks/libraries, databases, cloud platforms
  and services, BI/analytics tools, developer tools (Git, Jira, Docker), enterprise systems (SAP, Salesforce, Workday),
  AI coding tools (Cursor, Claude Code, Copilot), and named methods/practices (Agile, Scrum, A/B testing, CI/CD, ETL,
  Data Modeling, Machine Learning, LLM, RAG, System Design, TDD, Microservices, Statistics, Regression).
  Exclude: soft skills, spoken languages, degrees, years of experience, certifications, regulations (GDPR, SOX),
  business domain knowledge (finance, e-commerce, logistics), and generic activities ("data analysis",
  "dashboards", "problem solving", "project management", "distributed systems", "software architecture").
  Ignore company boilerplate unrelated to the role. Use the name as written in the posting (English), one entry per skill.
- seniority: intern | junior (graduate / associate / 0-2 yrs) | mid (2-5 yrs) | senior (5+ yrs or "Senior" title)
  | lead (lead / staff / principal / architect lead) | manager (manages people: manager, head, director) | unknown.
  The level word in the title wins over years. "Product Manager" is a role name, not a people-manager level.
  An individual-contributor "Associate Manager" with no reports is senior. If the title lists several levels,
  use the years. If neither title nor years give a level, use unknown.
- role_family: BA (business analyst, strategy & analytics, insights), SA (system analyst / IT business analyst /
  application specialist / HRIS analyst), DA (data/BI/analytics analyst or BI developer), DS/ML (data scientist,
  ML/AI engineer, research scientist), Data Eng, Software Eng (incl. QA, DevOps, security eng, architects),
  Product (PM/PO), Other tech.
- salary: ONLY if a number is explicitly written in the posting text. Otherwise all salary fields are null.
  salary_text must be copied verbatim from the posting. Never estimate.
- spoken_languages: human languages the posting requires (e.g. English, Thai, Japanese; Mandarin -> Chinese).
  "Bonus"/"a plus" languages and citizenship requirements do not count.
"""


@lru_cache
def _aliases() -> dict:
    cfg = json.loads((ROOT / "config" / "skills.json").read_text(encoding="utf-8"))
    return cfg["aliases"]


def canon_skill(s: str) -> str:
    key = re.sub(r"\s+", " ", s.strip().lower())
    return _aliases().get(key, s.strip())


def dedupe_skills(items) -> list[str]:
    """รวมชื่อทักษะ (ผ่านตารางชื่อมาตรฐาน) และกันชื่อซ้ำที่ต่างกันแค่ตัวพิมพ์เล็กใหญ่ (Pandas / pandas → ตัวแรกที่เจอ)"""
    seen: dict[str, str] = {}
    for s in items or []:
        if not isinstance(s, str) or not s.strip():
            continue
        name = canon_skill(s)
        seen.setdefault(name.lower(), name)
    return sorted(seen.values(), key=str.lower)


def _num(x):
    try:
        return float(x) if x is not None and x != "" else None
    except (TypeError, ValueError):
        return None


_NUM_TOKEN = re.compile(r"(\d[\d,]*(?:\.\d+)?)\s*([kK])?")


def numbers_in(text: str) -> set[float]:
    """ตัวเลขทั้งหมดที่ปรากฏในข้อความ (ตัดคอมมา; "50k" นับเป็น 50 และ 50000 ทั้งคู่)"""
    out: set[float] = set()
    for m in _NUM_TOKEN.finditer(text or ""):
        try:
            v = float(m.group(1).replace(",", ""))
        except ValueError:
            continue
        out.add(v)
        if m.group(2):
            out.add(v * 1000)
    return out


def clean(rec: dict, raw_text: str) -> dict:
    """ทำให้ผลสกัดเป็นรูปแบบเดียวกัน และตัดเงินเดือนที่ไม่ได้อยู่ในประกาศจริงทิ้ง
    เงินเดือนผ่านก็ต่อเมื่อ (1) ข้อความเงินเดือน (salary_text) ปรากฏในประกาศจริง และ (2) ตัวเลขต่ำสุด/สูงสุดที่ได้ปรากฏอยู่ใน salary_text
    — กันกรณีโมเดลคัดลอกข้อความถูกแต่แปลงตัวเลขผิด หรือกุตัวเลขขึ้นเอง; ไม่มีตัวเลข → ไม่เก็บข้อความ/สกุล/หน่วยเงินเดือนไว้"""
    skills = dedupe_skills(rec.get("skills"))
    seniority = rec.get("seniority") if rec.get("seniority") in SENIORITY else "unknown"
    role = rec.get("role_family") if rec.get("role_family") in ROLE_FAMILIES else "Other tech"
    out = {
        "skills": skills,
        "seniority": seniority,
        "role_family": role,
        "spoken_languages": sorted({LANG_ALIASES.get(x.strip().lower(), x.strip().title()) for x in rec.get("spoken_languages") or [] if isinstance(x, str) and x.strip()}),
        "salary_min": _num(rec.get("salary_min")),
        "salary_max": _num(rec.get("salary_max")),
        "salary_currency": rec.get("salary_currency"),
        "salary_period": rec.get("salary_period") if rec.get("salary_period") in PERIODS else None,
        "salary_text": rec.get("salary_text"),
        "salary_rejected": False,
    }
    norm = lambda x: re.sub(r"\s+", " ", x).lower()
    st = (out["salary_text"] or "").strip()
    salary_keys = ("salary_min", "salary_max", "salary_currency", "salary_period", "salary_text")
    if out["salary_min"] is not None or out["salary_max"] is not None:
        in_text = st and norm(st) in norm(raw_text)
        nums = numbers_in(st)
        values_ok = all(v is None or v in nums for v in (out["salary_min"], out["salary_max"]))
        if not (in_text and values_ok):
            out["salary_rejected"] = True
            for k in salary_keys:
                out[k] = None
        elif out["salary_min"] is not None and out["salary_max"] is not None and out["salary_min"] > out["salary_max"]:
            out["salary_min"], out["salary_max"] = out["salary_max"], out["salary_min"]
    else:  # ไม่มีตัวเลขเงินเดือน = ไม่ได้ระบุ: ล้างฟิลด์ที่เหลือที่โมเดลอาจกุขึ้น
        for k in salary_keys:
            out[k] = None
    out["salary_stated"] = out["salary_min"] is not None or out["salary_max"] is not None
    return out


JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "skills": {"type": "array", "items": {"type": "string"}},
        "seniority": {"type": "string", "enum": SENIORITY},
        "role_family": {"type": "string", "enum": ROLE_FAMILIES},
        "spoken_languages": {"type": "array", "items": {"type": "string"}},
        "salary_min": {"type": "number", "nullable": True},
        "salary_max": {"type": "number", "nullable": True},
        "salary_currency": {"type": "string", "nullable": True},
        "salary_period": {"type": "string", "nullable": True, "enum": ["month", "year", "hour", "day"]},
        "salary_text": {"type": "string", "nullable": True},
    },
    "required": ["skills", "seniority", "role_family", "spoken_languages"],
}
