from src import baseline, schema


def test_clean_rejects_salary_not_in_text():
    out = schema.clean({"skills": ["sql", "Power BI"], "seniority": "senior", "role_family": "DA",
                        "spoken_languages": ["mandarin"], "salary_min": 50000, "salary_max": 70000,
                        "salary_text": "50,000 - 70,000 THB"}, "Requirements: SQL, Power BI")
    assert out["salary_rejected"] and not out["salary_stated"] and out["salary_min"] is None
    assert out["skills"] == ["Power BI", "SQL"] and out["spoken_languages"] == ["Chinese"]


def test_clean_keeps_salary_in_text():
    out = schema.clean({"skills": [], "seniority": "x", "role_family": "x", "salary_min": 50000,
                        "salary_text": "Salary 50,000 THB"}, "Benefits\nSalary 50,000 THB per month")
    assert out["salary_stated"] and out["seniority"] == "unknown" and out["role_family"] == "Other tech"


def test_baseline_dictionary_and_seniority():
    text = "We use Scala, Kafka and ReactJS. 3+ years of experience. Excellent communication. R&D team."
    s = baseline.skills_from_text(text)
    assert {"Scala", "Kafka", "React"} <= set(s) and "Excel" not in s and "R" not in s
    assert baseline.seniority("Data Analyst", text) == "mid"
    assert baseline.seniority("Senior Data Analyst", text) == "senior"
    assert baseline.seniority("Data Analyst Intern", text) == "intern"


def test_clean_salary_numbers_must_appear_in_salary_text():
    text = "Salary: 50,000 - 70,000 THB per month"
    ok = schema.clean({"salary_min": 50000, "salary_max": 70000, "salary_currency": "THB", "salary_period": "month",
                       "salary_text": "50,000 - 70,000 THB"}, text)
    assert ok["salary_stated"] and ok["salary_min"] == 50000 and ok["salary_max"] == 70000
    bad = schema.clean({"salary_min": 5000000, "salary_max": 70000, "salary_text": "50,000 - 70,000 THB"}, text)
    assert bad["salary_rejected"] and not bad["salary_stated"] and bad["salary_text"] is None
    swapped = schema.clean({"salary_min": 70000, "salary_max": 50000, "salary_text": "50,000 - 70,000 THB"}, text)
    assert (swapped["salary_min"], swapped["salary_max"]) == (50000, 70000)
    k = schema.clean({"salary_min": 50000, "salary_text": "from 50k"}, "from 50k a month")
    assert k["salary_stated"]


def test_clean_drops_hallucinated_salary_text_without_numbers():
    out = schema.clean({"salary_min": None, "salary_max": None, "salary_text": "competitive", "salary_currency": "THB"}, "competitive salary")
    assert not out["salary_stated"] and out["salary_text"] is None and out["salary_currency"] is None and not out["salary_rejected"]


def test_skill_names_merge_regardless_of_case():
    out = schema.clean({"skills": ["Pandas", "pandas", "FastAPI", "fastapi", "  ", "sql"]}, "")
    assert sorted(s.lower() for s in out["skills"]) == ["fastapi", "pandas", "sql"]
    assert len(out["skills"]) == 3


def test_baseline_ambiguous_words_need_context():
    s = baseline.skills_from_text("Move at swift pace, react to change, make go/no-go calls, go-to-market, you go looking. The node RPC.")
    assert s == []
    s = baseline.skills_from_text("Stack: Go, Swift, React, Node.js, Spark.\nPython, R\nAlso R.")
    assert {"Go", "Swift", "React", "Node.js", "Spark", "Python", "R"} <= set(s)


def test_baseline_seniority_rules():
    sen = baseline.seniority
    assert sen("Internal Tools Engineer", "") == "unknown" and sen("International Sales", "") == "unknown"
    assert sen("Associate Director, Data", "") == "manager" and sen("Lead Manager/Associate Director, Strategy", "") == "manager"
    assert sen("Associate Manager, Strategy & Analytics", "") == "senior"
    assert sen("Associate Data Analyst", "") == "junior" and sen("Senior Lead Software Engineer", "") == "lead"
    assert sen("Manager Data & Analytics", "") == "manager" and sen("Product Manager", "") == "unknown"
    assert sen("Data Analyst", "1 year of Python experience. 7+ years of experience in analytics") == "senior"
    assert sen("Data Analyst", "Company founded 15 years ago. No requirements listed.") == "unknown"


def test_load_env_handles_bom_quotes_and_garbage(tmp_path, monkeypatch):
    from src import extract
    monkeypatch.setattr(extract, "ROOT", tmp_path)
    for k in ("T_KEY1", "T_KEY2", "T_KEY3"):
        monkeypatch.delenv(k, raising=False)
    (tmp_path / ".env").write_bytes('﻿# comment\nT_KEY1 = "abc"\nT_KEY2=\'def\'\nT_KEY3=ghi\n'.encode("utf-8"))
    extract.load_env()
    import os
    assert (os.environ["T_KEY1"], os.environ["T_KEY2"], os.environ["T_KEY3"]) == ("abc", "def", "ghi")
    (tmp_path / ".env").write_bytes('T_KEY4=x'.encode("utf-16"))   # PowerShell '>' เขียนเป็น UTF-16
    extract.load_env()                                              # ต้องไม่ล้ม


def test_call_gemini_quota_and_busy_handling(monkeypatch):
    import pytest
    pytest.importorskip("google.genai")
    from src import extract
    monkeypatch.setattr(extract.time, "sleep", lambda s: None)

    class Resp:
        text = '{"skills": []}'
        usage_metadata = None

    class Client:
        def __init__(self, errors):
            self.errors, self.calls = list(errors), 0
            self.models = self
        def generate_content(self, **kw):
            self.calls += 1
            if self.errors:
                raise Exception(self.errors.pop(0))
            return Resp()

    c = Client(["503 UNAVAILABLE overloaded", "503 UNAVAILABLE overloaded"])
    assert extract.call_gemini(c, "p")[0] == {"skills": []} and c.calls == 3
    c = Client(["429 RESOURCE_EXHAUSTED quota", "429 RESOURCE_EXHAUSTED quota"])
    with pytest.raises(extract.QuotaExhausted):
        extract.call_gemini(c, "p")
    assert c.calls == 2
    c = Client(["400 Invalid request id 14290"])             # เลข 429 ที่ไม่ใช่รหัสสถานะต้องไม่ถูกมองเป็นโควตาหมด
    with pytest.raises(Exception) as e:
        extract.call_gemini(c, "p")
    assert not isinstance(e.value, extract.QuotaExhausted)
