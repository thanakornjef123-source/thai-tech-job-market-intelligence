from src import dedupe as d

BODY = " ".join(f"word{i}" for i in range(200))

def rec(i, title, text, company="Agoda"):
    return {"job_id": str(i), "company": company, "title": title, "raw_text": text, "url": str(i), "posted_date": f"2026-01-0{i}"}

def test_same_title_similar_text_is_dup():
    rows = [rec(1, "Data Analyst (Bangkok-based)", BODY), rec(2, "Data Analyst (Bangkok based, relocation provided)", BODY + " extra words here")]
    assert len(d.find_groups(rows)) == 1

def test_identical_text_different_title_is_dup():
    rows = [rec(1, "Senior Analyst", BODY), rec(2, "Lead Analyst", BODY)]
    assert len(d.find_groups(rows)) == 1

def test_different_company_never_dup():
    rows = [rec(1, "Data Analyst", BODY, "Agoda"), rec(2, "Data Analyst", BODY, "Coda")]
    assert len(d.find_groups(rows)) == 2

def test_different_title_and_text_not_dup():
    other = " ".join(f"other{i}" for i in range(200))
    rows = [rec(1, "Data Analyst", BODY), rec(2, "Backend Engineer", other)]
    assert len(d.find_groups(rows)) == 2

def test_company_normalisation():
    assert d.norm_company("Agoda Services Co., Ltd. (Thailand)") == d.norm_company("agoda services")

def test_role_family():
    from src.roles import role_family as rf
    assert rf("Senior Business Analyst (Bangkok-based)") == "BA"
    assert rf("Senior System Analyst") == "SA"
    assert rf("Marketing Data Analyst") == "DA"
    assert rf("[BI] Senior BI Developer (Analytics Engineer)") == "DA"
    assert rf("Staff / Lead Data Engineer - Bidding") == "Data Eng"
    assert rf("Lead Software Engineer - Front End") == "Software Eng"
    assert rf("Senior Product Manager") == "Product"


def test_empty_and_short_text_not_merged_by_accident():
    rows = [rec(1, "Data Analyst", ""), rec(2, "Backend Engineer", "")]
    assert len(d.find_groups(rows)) == 2                       # ว่างทั้งคู่แต่ชื่อต่างกัน → ไม่รวม
    rows = [rec(1, "Data Analyst", "See website"), rec(2, "Backend Engineer", "Apply now")]
    assert len(d.find_groups(rows)) == 2                       # สั้นกว่า 5 คำ และต่างกัน → ไม่รวม
    rows = [rec(1, "Data Analyst", ""), rec(2, "Data Analyst", "")]
    assert len(d.find_groups(rows)) == 1                       # ชื่อเหมือนกันเป๊ะและว่างทั้งคู่ → รวมได้


def test_thai_text_without_spaces_can_be_detected_as_duplicate():
    thai = "เรากำลังมองหานักวิเคราะห์ข้อมูลที่มีความเชี่ยวชาญด้านเอสคิวแอลและพาวเวอร์บีไอ" * 3
    rows = [rec(1, "Data Analyst", thai), rec(2, "Data Analyst", thai + "สมัครเลย")]
    assert len(d.find_groups(rows)) == 1
    other = "บริษัทของเราต้องการวิศวกรซอฟต์แวร์ที่ชำนาญด้านระบบหลังบ้านและคลาวด์โดยเฉพาะ" * 3
    assert len(d.find_groups([rec(1, "Data Analyst", thai), rec(2, "Backend Engineer", other)])) == 2


def test_canonical_prefers_yesterdays_representative(tmp_path, monkeypatch):
    import json
    from src.jsonl import write_jsonl
    monkeypatch.setattr(d, "STAGING_DIR", tmp_path)
    a = rec(1, "Senior Analyst", BODY); a.update(job_id="old", posted_date="2026-01-01")
    b = rec(2, "Lead Analyst", BODY); b.update(job_id="new", posted_date="2026-02-01")
    write_jsonl(tmp_path / "canonical_2026-10-07.jsonl", [b])     # เมื่อวาน "new" เป็นตัวแทน
    write_jsonl(tmp_path / "postings_2026-10-08.jsonl", [a, b])   # วันนี้ทั้งคู่ยังอยู่ ("old" เก่ากว่า)
    d.run("2026-10-08")
    out = [json.loads(l) for l in (tmp_path / "canonical_2026-10-08.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [r["job_id"] for r in out] == ["new"] and out[0]["duplicate_job_ids"] == ["old"]


def test_role_family_regressions():
    from src.roles import role_family as rf
    assert rf("Senior Data Engineer (Analytics Platform)") == "Data Eng"
    assert rf("Software Engineer, Analytics Infrastructure") == "Software Eng"
    assert rf("Product Manager, Data Analytics") == "Product"
    assert rf("Analytics Engineer") == "Data Eng"
    assert rf("Data Science Manager") == "DS/ML"
    assert rf("AI/ML Engineer Intern") == "DS/ML"
    assert rf("Security Analyst") == "Software Eng"
    assert rf("Workday Security Specialist, People Tech") == "Other tech"
    assert rf("Manager Data & Analytics") == "DA"
