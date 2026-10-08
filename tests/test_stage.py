import json, shutil
from pathlib import Path
from src import stage

FIX = Path(__file__).parent / "fixtures"

def test_html_to_text_greenhouse_escaped():
    t = stage.html_to_text("&lt;p&gt;Use &lt;b&gt;SQL&lt;/b&gt;&lt;/p&gt;&lt;ul&gt;&lt;li&gt;Python&lt;/li&gt;&lt;li&gt;R&amp;amp;D&lt;/li&gt;&lt;/ul&gt;", escaped=True)
    assert t == "Use SQL\nPython\nR&D"

def test_html_to_text_double_escaped_still_works():
    t = stage.html_to_text("&amp;lt;p&amp;gt;Use &amp;lt;b&amp;gt;SQL&amp;lt;/b&amp;gt;&amp;lt;/p&amp;gt;", escaped=True)
    assert t == "Use SQL"

def test_html_to_text_keeps_literal_angle_brackets_and_table_cells():
    assert stage.html_to_text("<p>salary &lt;100k and &gt;50k, latency &lt; 10ms</p>") == "salary <100k and >50k, latency < 10ms"
    assert stage.html_to_text("<table><tr><td>SQL</td><td>Python</td></tr></table>") == "SQL Python"
    assert stage.html_to_text("<p>Get to know\xa0our\u200b team</p>") == "Get to know our team"

def test_job_id_stable():
    assert stage.make_job_id("lever", "a1") == stage.make_job_id("lever", "a1")
    assert stage.make_job_id("lever", "a1") != stage.make_job_id("greenhouse", "a1")

def test_th_primary_excludes_multi_country():
    f = stage.load_filters()
    mk = lambda loc, extra="", cc=None: {"location": loc, "location_extra": extra, "country_code": cc}
    assert stage.is_thailand_primary(mk("Bangkok, Thailand"), f)
    assert stage.is_thailand_primary(mk("Bangkok", cc="TH"), f)
    assert not stage.is_thailand_primary(mk("Bali, Indonesia; Bangkok, Thailand; Jakarta, Indonesia"), f)
    assert not stage.is_thailand_primary(mk("Bangkok (One Bangkok Office) or Seoul office"), f)
    assert not stage.is_thailand_primary(mk("Japan or Bangkok (One Bangkok)"), f)
    assert not stage.is_thailand_primary(mk("Singapore"), f)

def test_end_to_end(tmp_path, monkeypatch):
    raw = tmp_path / "raw" / "2026-10-07"; raw.mkdir(parents=True)
    for f in FIX.glob("*.json"): shutil.copy(f, raw / f.name)
    monkeypatch.setattr(stage, "RAW_DIR", tmp_path / "raw")
    monkeypatch.setattr(stage, "STAGING_DIR", tmp_path / "staging")
    c = stage.run("2026-10-07", active={"greenhouse": ["agoda"], "lever": ["demo"]})
    assert c["raw_total"] == 9 and c["duplicate_exact"] == 1
    assert c["not_thailand"] == 2          # Seoul, Singapore
    assert c["thailand_not_tech"] == 3     # Pricing@Marketing, Account Executive, Sales Engineer
    assert c["kept"] == 3                  # BA, Analyst@Data Analytics, System Analyst (country=TH)
    rows = [json.loads(l) for l in (tmp_path/"staging"/"postings_2026-10-07.jsonl").read_text(encoding="utf-8").splitlines()]
    ba = next(r for r in rows if r["source_job_id"] == "7379326")
    assert "SQL" in ba["raw_text"] and "<" not in ba["raw_text"] and ba["posted_date"] == "2025-11-05"
    sa = next(r for r in rows if r["source_job_id"] == "a1")
    assert "Power BI" in sa["raw_text"] and sa["salary_api"]["min"] == 60000 and sa["posted_date"]
