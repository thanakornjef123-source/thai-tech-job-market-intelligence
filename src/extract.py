"""ช่วง 4: สกัดทักษะ ระดับงาน กลุ่มตำแหน่ง และเงินเดือน ด้วย Gemini (ฟรีเทียร์)

ตั้งค่าในไฟล์ .env (ห้าม commit — อยู่ใน .gitignore แล้ว):
    GEMINI_API_KEY=...            สร้างเองที่ https://aistudio.google.com/apikey
    GEMINI_MODEL=gemini-3.5-flash  (ไม่บังคับ)
ใช้:
    python -m src.extract                  สกัดประกาศใน canonical ล่าสุดที่ยังไม่เคยสกัด
    python -m src.extract --gold           สกัดชุดทดสอบ (data/gold/sample.jsonl) เพื่อวัดผล
ผลลัพธ์สะสม (cache): data/extracted/extractions.jsonl — 1 บรรทัดต่อ (job_id, model, prompt_version)
ประกาศที่สกัดแล้วจะไม่ถูกส่งซ้ำ จึงไม่เปลืองโควตา
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from src import schema
from src.jsonl import append_jsonl, read_jsonl

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "extracted" / "extractions.jsonl"
PROMPT_VERSION = "v1"
MAX_CHARS = 12000          # ตัดประกาศยาวมาก ลดโทเค็น (ประกาศส่วนใหญ่สั้นกว่านี้)
SLEEP_SECONDS = 7          # ~8 ครั้ง/นาที ต่ำกว่าโควตาฟรีเทียร์
MAX_PER_RUN = int(os.environ.get("EXTRACT_MAX_PER_RUN", "120"))
TIMEOUT_MS = 90_000        # ไม่รอ Gemini เกิน 90 วินาทีต่อคำขอ (กันค้างทั้งรอบเมื่อเน็ตหลุดกลางทาง)
MAX_CONSECUTIVE_ERRORS = 5  # ผิดพลาดติดกันกี่ครั้งถึงหยุดทั้งรอบ (key ผิด/ชื่อโมเดลผิด/เน็ตล่ม)
_QUOTA = re.compile(r"\b429\b|RESOURCE_EXHAUSTED")
_BUSY = re.compile(r"\b503\b|UNAVAILABLE")

PROMPT = """You extract structured data from a job posting. The posting may mix Thai and English.
Follow these definitions exactly:
{definitions}
Return JSON only.

JOB TITLE: {title}
COMPANY: {company}
POSTING TEXT:
<<<
{text}
>>>"""


def load_env():
    """อ่าน .env แบบทนทาน: รองรับ BOM (Notepad), เครื่องหมายคำพูดเดี่ยว/คู่, ช่องว่างรอบ = และไฟล์ที่อ่านไม่ได้ (ข้ามเงียบๆ
    — ไม่ให้ขั้นสร้างแดชบอร์ดพังเพียงเพราะ .env เสีย)"""
    env = ROOT / ".env"
    if not env.exists():
        return
    try:
        lines = env.read_text(encoding="utf-8-sig").splitlines()
    except (UnicodeDecodeError, OSError):
        print("[เตือน] อ่าน .env ไม่ได้ (ต้องเป็นข้อความ UTF-8) — ข้ามไป", file=sys.stderr)
        return
    for line in lines:
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip("\"'"))


def model_name() -> str:
    return os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")


def build_prompt(rec: dict) -> str:
    return PROMPT.format(definitions=schema.DEFINITIONS, title=rec["title"], company=rec["company"],
                         text=rec["raw_text"][:MAX_CHARS])


class QuotaExhausted(Exception):
    pass


def call_gemini(client, prompt: str) -> tuple[dict, dict]:
    from google.genai import types
    cfg = types.GenerateContentConfig(temperature=0, response_mime_type="application/json",
                                      response_schema=schema.JSON_SCHEMA)
    for attempt in range(5):
        try:
            resp = client.models.generate_content(model=model_name(), contents=prompt, config=cfg)
            usage = getattr(resp, "usage_metadata", None)
            u = {"input_tokens": getattr(usage, "prompt_token_count", None),
                 "output_tokens": getattr(usage, "candidates_token_count", None)}
            return json.loads(resp.text), u
        except Exception as e:  # 503: เซิร์ฟเวอร์ไม่ว่าง รอแล้วลองใหม่ · 429: โควตาหมด ลองอีก 1 ครั้ง (เผื่อเป็นโควตาต่อนาที) แล้วหยุดทั้งรอบ
            msg = str(e)
            if _QUOTA.search(msg):
                if attempt >= 1:
                    raise QuotaExhausted(msg[:160])
                print("   โควตาเต็ม รอ 65 วินาทีแล้วลองอีกครั้ง")
                time.sleep(65)
                continue
            if _BUSY.search(msg) and attempt < 4:
                wait = 30 * (attempt + 1)
                print(f"   โควตา/เซิร์ฟเวอร์ไม่ว่าง รอ {wait} วินาที ({msg[:80]})")
                time.sleep(wait)
                continue
            raise


def already_done() -> set:
    return {(r["job_id"], r["model"], r["prompt_version"]) for r in read_jsonl(OUT)}


def load_targets(gold: bool) -> list[dict]:
    if gold:
        path = ROOT / "data" / "gold" / "sample.jsonl"
    else:
        files = sorted((ROOT / "data" / "staging").glob("canonical_*.jsonl"))
        if not files:
            sys.exit("ยังไม่มี canonical — รัน run_collect.bat ก่อน")
        path = files[-1]
    rows = read_jsonl(path)
    if gold:  # ชุด test ก่อน: ตัวเลขที่รายงานได้จะครบเร็วที่สุดเมื่อโควตาฟรีมีจำกัด
        rows.sort(key=lambda r: r.get("split") != "test")
    return rows


def run(gold: bool = False):
    load_env()
    if not os.environ.get("GEMINI_API_KEY"):
        sys.exit("ไม่พบ GEMINI_API_KEY — สร้างไฟล์ .env ตามวิธีใน README")
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"], http_options=types.HttpOptions(timeout=TIMEOUT_MS))
    done = already_done()
    todo = [r for r in load_targets(gold) if (r["job_id"], model_name(), PROMPT_VERSION) not in done][:MAX_PER_RUN]
    print(f"model={model_name()} prompt={PROMPT_VERSION} ต้องสกัด {len(todo)} ประกาศ")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    n_ok = n_err = streak = 0
    for i, rec in enumerate(todo, 1):
        try:
            raw, usage = call_gemini(client, build_prompt(rec))
            row = {"job_id": rec["job_id"], "model": model_name(), "prompt_version": PROMPT_VERSION,
                   "extracted_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                   **usage, "raw_output": raw, **schema.clean(raw, rec["raw_text"])}
            append_jsonl(OUT, [row])
            n_ok += 1
            streak = 0
            print(f"[{i}/{len(todo)}] ok  {rec['title'][:60]} → {len(row['skills'])} skills, {row['seniority']}")
        except QuotaExhausted as e:
            print(f"หยุด: โควตาฟรีของวันนี้หมดแล้ว ({e}) — ประกาศที่เหลือ {len(todo) - i + 1} จะถูกสกัดในรอบถัดไป (ผลที่ได้แล้วถูกเก็บไว้)")
            break
        except Exception as e:
            n_err += 1
            streak += 1
            print(f"[{i}/{len(todo)}] ERR {rec['title'][:60]}: {type(e).__name__}: {str(e)[:150]}")
            if streak >= MAX_CONSECUTIVE_ERRORS:
                print(f"หยุด: ผิดพลาดติดกัน {streak} ครั้ง — ตรวจ GEMINI_API_KEY / GEMINI_MODEL / อินเทอร์เน็ตใน .env แล้วรันใหม่")
                break
        time.sleep(SLEEP_SECONDS)
    print(f"เสร็จ: สำเร็จ {n_ok}, ผิดพลาด {n_err}")
    if streak >= MAX_CONSECUTIVE_ERRORS:
        sys.exit(1)


if __name__ == "__main__":
    run(gold="--gold" in sys.argv)
