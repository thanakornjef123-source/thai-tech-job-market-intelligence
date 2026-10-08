"""ส่งออกฐานข้อมูลแดชบอร์ดเป็นไฟล์ Parquet ใน data/snapshot/ สำหรับเว็บออนไลน์ (Streamlit Community Cloud)
ใช้: python -m src.snapshot   (run_daily.bat เรียกให้อัตโนมัติหลังสร้างฐานข้อมูล)

ทำไมต้องมี: data/marts/jobs.duckdb ไม่ถูกเก็บใน git (.gitignore) — เว็บออนไลน์จึงอ่านจาก snapshot นี้แทน
ทุกครั้งที่ส่งออก จะลบอีเมลและเบอร์โทรศัพท์ที่อาจติดมาในข้อความประกาศ (กันข้อมูลส่วนบุคคลหลุดขึ้น repo สาธารณะ)
"""
from __future__ import annotations

import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "marts" / "jobs.duckdb"
OUT = ROOT / "data" / "snapshot"
TABLES = ["job_postings", "posting_attributes", "posting_skills", "daily_active", "funnel"]

EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE = re.compile(r"(?<!\d)(?:\+?66[\s-]?|0)\d{1,2}[\s-]?\d{3}[\s-]?\d{3,4}(?!\d)")


def redact(text):
    if not isinstance(text, str):   # None / NaN ไม่ต้องแก้
        return None if text is None or text != text else text
    return PHONE.sub("[phone removed]", EMAIL.sub("[email removed]", text))


def export(db: Path = DB, out: Path = OUT) -> dict:
    if not db.exists():
        raise FileNotFoundError(f"ไม่พบ {db} — รัน python -m src.marts ก่อน")
    tmp = out.with_name(out.name + ".tmp")
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    con = duckdb.connect(str(db), read_only=True)
    counts = {}
    try:
        for t in TABLES:
            df = con.execute(f"SELECT * FROM {t}").df()
            if "raw_text" in df.columns:
                df["raw_text"] = df["raw_text"].map(redact)
            out_con = duckdb.connect()
            try:
                out_con.register("df_view", df)
                target = (tmp / f"{t}.parquet").as_posix().replace("'", "''")
                out_con.execute(f"COPY (SELECT * FROM df_view) TO '{target}' (FORMAT PARQUET)")
            finally:
                out_con.close()
            counts[t] = len(df)
    finally:
        con.close()
    meta = {"exported_at": datetime.now().isoformat(timespec="seconds"), "rows": counts}
    (tmp / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    if out.exists():
        shutil.rmtree(out)
    tmp.replace(out)
    return meta


if __name__ == "__main__":
    try:
        print(json.dumps(export(), ensure_ascii=False))
    except FileNotFoundError as e:
        print(e, file=sys.stderr)
        sys.exit(1)
