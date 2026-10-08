"""อ่าน/เขียนไฟล์ .jsonl แบบปลอดภัย (ใช้ร่วมกันทุกโมดูล)

ทำไมไม่ใช้ read_text().splitlines(): str.splitlines() ตัดบรรทัดที่ตัวอักษร U+2028 / U+2029 / U+0085 ด้วย
ซึ่ง json.dumps(ensure_ascii=False) ไม่ escape ให้ — ประกาศงานจริงมีตัวอักษรนี้ (เจอใน Lever) ทำให้ 1 record ถูกแบ่งเป็น 2 บรรทัดแล้วอ่าน JSON พัง
ที่นี่อ่านทีละบรรทัดจากไฟล์ (ตัดที่ \\n เท่านั้น) และข้ามบรรทัดสุดท้ายที่เขียนไม่จบ (เครื่องดับกลางเขียน) พร้อมเตือน
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def read_jsonl(path: Path | str) -> list[dict]:
    p = Path(path)
    if not p.exists():
        return []
    rows, bad = [], 0
    with p.open(encoding="utf-8-sig", newline="\n") as f:
        for n, line in enumerate(f, 1):
            line = line.strip("\r\n")
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                bad += 1
                print(f"[เตือน] {p.name} บรรทัด {n} อ่านไม่ได้ (ข้าม)", file=sys.stderr)
    return rows


def dumps(obj) -> str:
    """json 1 บรรทัด: escape ตัวคั่นบรรทัดแบบ Unicode ไว้ด้วย เพื่อให้เครื่องมืออื่นที่ใช้ splitlines ก็อ่านได้"""
    s = json.dumps(obj, ensure_ascii=False)
    return s.replace("\u2028", "\\u2028").replace("\u2029", "\\u2029").replace("\u0085", "\\u0085")


def write_jsonl(path: Path | str, rows: list[dict]) -> None:
    """เขียนทั้งไฟล์แบบปลอดภัย: เขียนไฟล์ชั่วคราวก่อนแล้วค่อยแทนที่ (ไฟล์เดิมไม่เสียถ้าดับกลางทาง)"""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(dumps(r) + "\n")
    tmp.replace(p)


def append_jsonl(path: Path | str, rows: list[dict]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(dumps(r) + "\n")
