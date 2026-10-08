"""ช่วง 4: วัดความแม่นยำของตัวสกัด เทียบกับป้ายที่คนตรวจแล้ว (data/gold/labels.jsonl, verified=true เท่านั้น)

ใช้: python -m src.evaluate [--split test|dev|all] [--baseline | --model ชื่อโมเดล]   (ค่าเริ่มต้น test, โมเดล Gemini ใน .env)
- ปรับคำสั่ง (prompt) โดยดูผลบน dev เท่านั้น แล้วรายงานตัวเลขจาก test เพื่อไม่ให้ชุดทดสอบกลายเป็นชุดที่สอน
- ผลถูกเพิ่มลง results.md อัตโนมัติ พร้อมวันที่ ขนาดชุดทดสอบ และรุ่นโมเดล/คำสั่ง
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

from src import baseline, extract, schema
from src.jsonl import read_jsonl

ROOT = Path(__file__).resolve().parent.parent


load_jsonl = read_jsonl


def prf(tp: int, fp: int, fn: int) -> dict:
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return {"precision": round(p, 3), "recall": round(r, 3), "f1": round(2 * p * r / (p + r), 3) if p + r else 0.0}


def evaluate(gold: list[dict], pred: dict) -> dict:
    tp = fp = fn = 0
    miss, extra = Counter(), Counter()
    sen_ok = role_ok = sal_stated_ok = sal_val_ok = sal_val_n = n = missing = 0
    for g in gold:
        p = pred.get(g["job_id"])
        if not p:
            missing += 1
            continue
        n += 1
        gs = {schema.canon_skill(s).lower() for s in g["skills"]}
        ps = {schema.canon_skill(s).lower() for s in p["skills"]}   # ตารางชื่อมาตรฐานเดียวกับฝั่งป้าย: แก้ตารางแล้วผลที่ cache ไว้ก็ถูกเทียบด้วยตารางใหม่
        tp += len(gs & ps); fp += len(ps - gs); fn += len(gs - ps)
        miss.update(gs - ps); extra.update(ps - gs)
        sen_ok += g["seniority"] == p["seniority"]
        role_ok += g["role_family"] == p["role_family"]
        g_stated = g.get("salary_min") is not None or g.get("salary_max") is not None
        sal_stated_ok += g_stated == p["salary_stated"]
        if g_stated:
            sal_val_n += 1
            sal_val_ok += (g.get("salary_min"), g.get("salary_max")) == (p["salary_min"], p["salary_max"])
    return {
        "n_postings": n,
        "n_missing_predictions": missing,
        "skills": {**prf(tp, fp, fn), "tp": tp, "fp": fp, "fn": fn},
        "seniority_accuracy": round(sen_ok / n, 3) if n else None,
        "role_family_accuracy": round(role_ok / n, 3) if n else None,
        "salary_stated_accuracy": round(sal_stated_ok / n, 3) if n else None,
        "salary_value_exact": f"{sal_val_ok}/{sal_val_n}",
        "top_missed_skills": miss.most_common(10),
        "top_extra_skills": extra.most_common(10),
    }


def run(split: str = "test", model: str | None = None, pv: str | None = None, once: bool = False):
    extract.load_env()
    gold = [g for g in load_jsonl(ROOT / "data" / "gold" / "labels.jsonl") if g.get("verified")]
    if split != "all":
        gold = [g for g in gold if g.get("split") == split]
    if not gold:
        sys.exit("ยังไม่มีป้ายที่ตรวจแล้ว (verified) — เปิด run_label.bat เพื่อตรวจป้าย")
    model = model or extract.model_name()
    pv = pv or (baseline.VERSION if model == baseline.MODEL else extract.PROMPT_VERSION)
    pred = {r["job_id"]: r for r in load_jsonl(extract.OUT) if r["model"] == model and r["prompt_version"] == pv}
    res = evaluate(gold, pred)
    n_hv = sum(bool(g.get("human_verified", g.get("labeler") != "claude")) for g in gold)
    if once:
        if res["n_missing_predictions"]:
            print(f"ยังสกัดชุดทดสอบไม่ครบ (ขาด {res['n_missing_predictions']}) — ข้ามการวัดผล")
            return
        # แท็กรวมจำนวนป้ายที่คนตรวจ: ตรวจป้ายเพิ่มภายหลัง → วัดและบันทึกผลใหม่อีกครั้งโดยอัตโนมัติ
        tag = f"{model} · prompt {pv} · n={res['n_postings']} · คนตรวจป้าย {n_hv}/{len(gold)}"
        if tag in (ROOT / "results.md").read_text(encoding="utf-8"):
            print("วัดผลชุดนี้ไปแล้ว — ข้าม")
            return
    res.update(split=split, model=model, prompt_version=pv, n_gold=len(gold),
               n_human_edited=sum(bool(g.get("human_edited")) for g in gold),
               n_human_verified=n_hv)
    who = "ป้ายโดย LLM ยังไม่ผ่านการตรวจโดยคน" if n_hv == 0 else f"คนตรวจป้าย {n_hv}/{len(gold)}"
    who_tag = f"คนตรวจป้าย {n_hv}/{len(gold)}"
    print(json.dumps(res, ensure_ascii=False, indent=1))
    out = ROOT / "data" / "eval"; out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    (out / f"eval_{split}_{datetime.now():%Y%m%d_%H%M}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    s = res["skills"]
    rows = [
        f"| {stamp} | สกัดทักษะ ({split}) precision / recall / F1 | {s['precision']} / {s['recall']} / {s['f1']} | `python -m src.evaluate --split {split}{' --baseline' if model == baseline.MODEL else ''}` · {model} · prompt {pv} · n={res['n_postings']} · {who_tag} · {who} |",
        f"| {stamp} | ระดับงาน accuracy ({split}) | {res['seniority_accuracy']} | เหมือนบรรทัดบน |",
        f"| {stamp} | กลุ่มตำแหน่ง accuracy ({split}) | {res['role_family_accuracy']} | เหมือนบรรทัดบน |",
        f"| {stamp} | ระบุเงินเดือนหรือไม่ accuracy ({split}) | {res['salary_stated_accuracy']} (ค่าตรงเป๊ะ {res['salary_value_exact']}) | เหมือนบรรทัดบน |",
    ]
    with (ROOT / "results.md").open("a", encoding="utf-8") as f:
        f.write(f"\n### ความแม่นยำตัวสกัด ({model}, {split})\n" + "\n| คำนวณเมื่อ (เวลาเครื่องที่รัน) | ตัวชี้วัด | ค่า | คำสั่ง/ไฟล์ที่มา |\n|---|---|---|---|\n" + "\n".join(rows) + "\n")
    print("เพิ่มผลลง results.md แล้ว")


if __name__ == "__main__":
    a = sys.argv
    split = a[a.index("--split") + 1] if "--split" in a else "test"
    model = baseline.MODEL if "--baseline" in a else (a[a.index("--model") + 1] if "--model" in a else None)
    run(split, model, once="--once" in a)
