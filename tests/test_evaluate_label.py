import json

from src import evaluate, label, schema
from src.jsonl import read_jsonl, write_jsonl


def test_prf_and_evaluate_hand_computed():
    assert evaluate.prf(8, 2, 2) == {"precision": 0.8, "recall": 0.8, "f1": 0.8}
    assert evaluate.prf(0, 0, 0)["f1"] == 0.0
    gold = [{"job_id": "a", "skills": ["SQL", "Python", "Tableau"], "seniority": "senior", "role_family": "DA", "salary_min": None, "salary_max": None},
            {"job_id": "b", "skills": ["Java"], "seniority": "junior", "role_family": "Software Eng", "salary_min": 100, "salary_max": 200},
            {"job_id": "c", "skills": [], "seniority": "mid", "role_family": "BA"}]
    pred = {"a": {"skills": ["sql", "python", "Excel"], "seniority": "senior", "role_family": "DA", "salary_stated": False, "salary_min": None, "salary_max": None},
            "b": {"skills": ["Java"], "seniority": "mid", "role_family": "Software Eng", "salary_stated": True, "salary_min": 100, "salary_max": 300}}
    r = evaluate.evaluate(gold, pred)
    assert r["n_postings"] == 2 and r["n_missing_predictions"] == 1
    assert (r["skills"]["tp"], r["skills"]["fp"], r["skills"]["fn"]) == (3, 1, 1)   # SQL, Python, Java ตรง · Excel เกิน · Tableau ขาด
    assert r["seniority_accuracy"] == 0.5 and r["role_family_accuracy"] == 1.0
    assert r["salary_stated_accuracy"] == 1.0 and r["salary_value_exact"] == "0/1"


def test_predictions_are_canonicalised_at_evaluation_time():
    gold = [{"job_id": "a", "skills": ["PowerBI"], "seniority": "mid", "role_family": "DA"}]
    pred = {"a": {"skills": ["power bi"], "seniority": "mid", "role_family": "DA", "salary_stated": False, "salary_min": None, "salary_max": None}}
    assert schema.canon_skill("PowerBI") == schema.canon_skill("power bi")
    assert evaluate.evaluate(gold, pred)["skills"]["f1"] == 1.0


def test_label_save_is_per_item_keeps_ai_origin_and_rejects_unknown(tmp_path, monkeypatch):
    gold = tmp_path / "gold"
    monkeypatch.setattr(label, "GOLD", gold)
    write_jsonl(gold / "sample.jsonl", [{"job_id": "a", "split": "dev", "raw_text": "x"}, {"job_id": "b", "split": "test", "raw_text": "y"}])
    ai = {"job_id": "a", "split": "dev", "skills": ["SQL"], "seniority": "mid", "role_family": "DA", "spoken_languages": [],
          "salary_min": None, "salary_max": None, "salary_currency": None, "salary_period": None, "salary_text": None,
          "labeler": "claude", "verified": True, "human_verified": False, "human_edited": False, "review_passes": 2}
    write_jsonl(gold / "labels.jsonl", [ai, {**ai, "job_id": "b", "split": "test"}])
    new = {k: ai[k] for k in label.FIELDS}
    out = label.save("a", {**new, "skills": ["SQL", "Python"]})
    assert out["human_verified"] and out["human_edited"] and out["labeler"] == "claude+human"
    assert out["changed_fields"] == ["skills"] and out["review_passes"] == 2
    rows = {r["job_id"]: r for r in read_jsonl(gold / "labels.jsonl")}
    assert rows["a"]["human_verified"] and not rows["b"]["human_verified"]   # ข้อ b ยังเป็นป้ายของ AI ที่ยังไม่ตรวจ
    assert not list(gold.glob("*.tmp"))
    try:
        label.save("zzz", new)
        assert False, "ต้อง raise KeyError"
    except KeyError:
        pass
