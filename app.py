"""แดชบอร์ดวิเคราะห์ทักษะจากประกาศรับสมัครงานสายเทคในประเทศไทย (ไทย / English)
เรียกใช้: python -m streamlit run app.py  (หรือดับเบิลคลิก start.bat บน Windows)
อ่านจาก data/marts/jobs.duckdb ที่สร้างโดย python -m src.marts — ไม่มีตัวเลขที่พิมพ์ไว้ในไฟล์นี้ ทุกค่าคำนวณจากฐานข้อมูล
ชื่อผู้จัดทำ/สังกัดแก้ได้ที่ config/site.json
"""
from __future__ import annotations

import json
from html import escape
from pathlib import Path

import altair as alt
import duckdb
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from PIL import Image

from src.jsonl import read_jsonl

ROOT = Path(__file__).parent
DB = ROOT / "data" / "marts" / "jobs.duckdb"      # ฐานข้อมูลในเครื่อง (สร้างโดย src.marts)
SNAP = ROOT / "data" / "snapshot"                 # สำเนา Parquet สำหรับเว็บออนไลน์ (สร้างโดย src.snapshot)
SNAP_TABLES = ["job_postings", "posting_attributes", "posting_skills", "daily_active", "funnel"]

# สีหมวด (categorical) ช่อง 1-3 ผ่านตัวตรวจสีตาบอดสี · สีลำดับ (sequential) ไล่น้ำเงินอ่อน→เข้ม
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
SEQ = ["#e9f2fd", "#b7d4f6", "#6ea4ea", "#2f77d0", "#0d366b"]
NAVY, INK, MUTE, LINE, PAPER, GRID = "#0f2742", "#1a2433", "#5b6573", "#dde2e8", "#f5f6f8", "#eceff3"
FONT = "'IBM Plex Sans Thai','Noto Sans Thai','Leelawadee UI','Segoe UI',Tahoma,sans-serif"

ROLE_ORDER = ["BA", "SA", "DA", "DS/ML", "Data Eng", "Software Eng", "Product", "Other tech"]
SEN_ORDER = ["intern", "junior", "mid", "senior", "lead", "manager", "unknown"]
TREND_MIN_DAYS = 14

# ---------- ข้อความสองภาษา ----------
TXT = {
    "th": {
        "brand": "Thai Tech Job Market Intelligence",
        "asof": "ข้อมูล ณ วันที่ {d}",
        "title": "ความต้องการทักษะในประกาศรับสมัครงานสายเทคของประเทศไทย",
        "lede": "วิเคราะห์จากประกาศรับสมัครงานที่เผยแพร่บนระบบรับสมัครงานของบริษัท (Greenhouse และ Lever) คัดเฉพาะตำแหน่งสายเทคที่ปฏิบัติงานในประเทศไทย และตัดประกาศที่ซ้ำกันออกก่อนวิเคราะห์",
        "by": "จัดทำโดย",
        "st_posts": "ประกาศหลังตัดซ้ำ", "st_cos": "บริษัท", "st_days": "ช่วงเวลาข้อมูล ({p})", "days_unit": " วัน", "st_skills": "ทักษะที่แตกต่างกัน",
        "print": "พิมพ์ / บันทึก PDF",
        "no_db": "ยังไม่พบข้อมูลสำหรับแสดงผล (data/marts/jobs.duckdb หรือ data/snapshot/) — โปรดสร้างด้วย start.bat หรือคำสั่ง python -m src.marts",
        "h_fail": "การรวบรวมข้อมูลรอบล่าสุดพบข้อผิดพลาด: {p}",
        "h_stale": "ข้อมูลล่าสุดเป็นของวันที่ {d} — การรวบรวมรายวันอาจหยุดชะงัก (ตรวจสอบ logs/daily_log.txt)",
        "h_last": "การทำงานรายวันรอบล่าสุดไม่สมบูรณ์: {p}",
        "scope_title": "ขอบเขตข้อมูล · รวบรวม ณ วันที่ {d}",
        "fun": ["ประกาศทั้งหมดที่รวบรวมได้", "ตำแหน่งสายเทคในประเทศไทย", "หลังตัดประกาศซ้ำ (ใช้วิเคราะห์)"],
        "fun_note": "แกนแสดงด้วยสเกลรากที่สอง ตัวเลขท้ายแท่งคือจำนวนจริง",
        "q_title": "คุณภาพข้อมูลและวิธีการสกัด",
        "q_ext": "การสกัดทักษะ", "q_ext_v": "LLM (Gemini) {g}/{n} ประกาศ — ส่วนที่เหลือใช้ baseline-dict ระหว่างรอการสกัดต่อเนื่อง",
        "q_lab": "ป้ายอ้างอิงสำหรับประเมินผล", "q_lab_v": "จัดทำโดย AI · ผ่านการตรวจโดยบุคคล {h}/{n} ป้าย",
        "q_con": "การกระจุกตัวของแหล่งข้อมูล", "q_con_v": "{c} {k}/{n} ประกาศ ({p})",
        "lim_title": "ข้อจำกัดของข้อมูลและข้อควรระวังในการตีความ",
        "lim": ("1. ชุดข้อมูลคือประกาศที่เผยแพร่บนระบบรับสมัครงานของบริษัทที่รวบรวมได้ ไม่ใช่ภาพรวมของตลาดแรงงานไทย บริษัทส่วนใหญ่เป็นองค์กรขนาดใหญ่หรือบริษัทต่างชาติ และ{en}\n"
                "2. สัดส่วนประกาศจากบริษัทเดียวสูง ({c} {k} จาก {n} ประกาศ) ผลวิเคราะห์จึงสะท้อนบริษัทดังกล่าวเป็นหลัก\n"
                "3. บางประกาศรับสมัครหลายประเทศหรือทำงานระยะไกล ใช้ตัวกรอง “สถานที่” เพื่อจำกัดเฉพาะประเทศไทย\n"
                "4. ทักษะจาก baseline-dict เป็นการจับคู่คำตามพจนานุกรม ส่วน LLM สกัดทักษะนอกพจนานุกรมได้ จึงไม่ควรเปรียบเทียบสองวิธีโดยตรง (เลือกแยกวิธีได้ที่ตัวกรอง)\n"
                "5. ค่าความแม่นยำอ้างอิงป้ายที่จัดทำโดย AI และยังไม่ผ่านการตรวจโดยบุคคลครบทุกรายการ รายละเอียดอยู่ใน {results}\n"),
        "filters": "ตัวกรอง", "f_role": "กลุ่มตำแหน่ง", "f_role_help": "ค่าเริ่มต้น: BA, SA, DA", "f_sen": "ระดับงาน", "f_top": "จำนวนทักษะที่แสดง",
        "f_loc": "สถานที่", "loc": {"all": "ทั้งหมด", "th": "ประเทศไทยเป็นหลัก", "multi": "หลายประเทศ / ทำงานระยะไกล"},
        "f_scope": "สถานะประกาศ", "scope": {"open": "ประกาศที่ยังเปิดรับ", "all": "ประกาศทั้งหมดที่เคยพบ"}, "f_scope_help": "“ยังเปิดรับ” หมายถึงยังปรากฏในการรวบรวมครั้งล่าสุด",
        "f_meth": "วิธีสกัดทักษะ", "meth": {"all": "ทั้งหมด", "llm": "เฉพาะ LLM", "base": "เฉพาะ baseline-dict"}, "f_meth_help": "ผลจาก LLM และ baseline-dict ไม่ควรนำมาเปรียบเทียบปนกัน",
        "print_scope": "ขอบเขตที่เลือก: กลุ่มตำแหน่ง {r} · ระดับงาน {s} · สถานที่: {l} · {sc} · วิธีสกัด: {m}",
        "none": "ไม่พบประกาศที่ตรงกับตัวกรองที่เลือก โปรดขยายเงื่อนไขกลุ่มตำแหน่งหรือระดับงาน",
        "k_n": "ประกาศในขอบเขตที่เลือก", "k_co": "จำนวนบริษัท", "k_sk": "ทักษะต่อประกาศ (มัธยฐาน)", "k_sal": "สัดส่วนที่ระบุเงินเดือน", "k_sal_help": "{a} จาก {n} ประกาศ",
        "small_n": "จำนวนตัวอย่างในตัวกรองนี้มีน้อย (n = {n}) ผลอาจเปลี่ยนแปลงได้มากเมื่อมีประกาศเพิ่มขึ้น",
        "s1": "ทักษะที่ปรากฏบ่อยที่สุด", "s1_sub": "กลุ่ม {r} · {n} ประกาศ", "s1_lead": " · อันดับต้น: {l}",
        "skill": "ทักษะ", "postings": "จำนวนประกาศ", "share": "สัดส่วน", "x_share": "ร้อยละของประกาศที่ระบุทักษะ",
        "s1_note": "ตัวเลขท้ายแท่งแสดงจำนวนประกาศ · นับหนึ่งครั้งต่อประกาศ", "csv": "ดาวน์โหลด CSV",
        "s2": "การเปรียบเทียบทักษะตามกลุ่มตำแหน่ง ระดับงาน และสถานที่",
        "s2_sub": "ความเข้มของสีและตัวเลขในช่องแสดงร้อยละของประกาศในกลุ่มที่ระบุทักษะ · n คือจำนวนประกาศในกลุ่ม",
        "dim": "เปรียบเทียบตาม", "dims": {"role_family": "กลุ่มตำแหน่ง", "seniority": "ระดับงาน", "th_primary": "สถานที่"},
        "grp_th": "ประเทศไทย", "grp_multi": "หลายประเทศ / ระยะไกล", "n_group": "ประกาศในกลุ่ม",
        "s2_small": "กลุ่มที่มีน้อยกว่า 10 ประกาศ ({g}) ควรตีความอย่างระมัดระวัง เนื่องจากสัดส่วนเปลี่ยนแปลงง่ายเมื่อตัวอย่างน้อย",
        "s3": "เงินเดือน", "s3_sub": "ช่วงเงินเดือนตลาดตามประสบการณ์ จากแหล่งสำรวจภายนอก เทียบกับเงินเดือนที่ระบุในประกาศที่รวบรวมได้",
        "s3_ref": "ช่วงเงินเดือนอ้างอิงตลาด (บาท/เดือน) ตามกลุ่มตำแหน่งที่เลือก",
        "s3_band": "ประสบการณ์", "bands": {"0-3": "0–3 ปี", "3-5": "3–5 ปี", "5-7": "5–7 ปี", "7+": "มากกว่า 7 ปี"},
        "s3_role": "กลุ่มตำแหน่ง", "s3_title": "ตำแหน่งตามแหล่งข้อมูล", "s3_min": "ต่ำสุด", "s3_max": "สูงสุด", "s3_axis": "บาทต่อเดือน",
        "s3_cite": "ที่มา: {name} ({url}) ตำแหน่งในหมวด Information Technology · เข้าถึงเมื่อ {d} · เป็นข้อมูลสำรวจตลาด ไม่ได้มาจากประกาศที่ระบบรวบรวม และไม่ได้แยกตามบริษัท{extra}",
        "s3_shared": " · Data Science/ML และ Data Engineer ใช้ช่วงเดียวกัน (แหล่งข้อมูลรายงานรวมเป็น Data Scientist / Data Engineer)",
        "s3_noref": "ไม่มีช่วงเงินเดือนอ้างอิงสำหรับกลุ่มตำแหน่งที่เลือก", "s3_tbl": "ตารางช่วงเงินเดือนอ้างอิง",
        "s3_post": "เงินเดือนที่ระบุในประกาศ: <b>{a} จาก {n} ประกาศ ({p})</b> · แสดงเฉพาะตัวเลขที่ปรากฏในข้อความประกาศ ไม่มีการประมาณค่า",
        "cols": {"company": "บริษัท", "title": "ตำแหน่ง", "role_family": "กลุ่มตำแหน่ง", "seniority": "ระดับงาน", "location": "สถานที่",
                 "salary_min": "ขั้นต่ำ", "salary_max": "ขั้นสูง", "salary_currency": "สกุลเงิน", "salary_period": "รอบจ่าย", "salary_text": "ข้อความในประกาศ",
                 "first_seen": "พบครั้งแรก", "last_seen": "พบล่าสุด", "skills": "ทักษะ", "url": "ลิงก์", "extraction_method": "วิธีสกัด"},
        "s4": "แนวโน้มความต้องการทักษะ", "s4_prog": "ข้อมูลสะสม {d} จาก {m} วัน",
        "s4_note": "แสดงแนวโน้มเมื่อมีข้อมูลสะสมอย่างน้อย {m} วัน เพื่อให้เห็นแนวโน้มได้อย่างน่าเชื่อถือ",
        "s4_pick": "ทักษะที่ต้องการดู (สูงสุด 3)", "week": "สัปดาห์ (เริ่มวันจันทร์)", "y_open": "ร้อยละของประกาศที่เปิดรับ", "active": "ประกาศที่เปิดรับ",
        "s5": "ประสิทธิภาพของวิธีสกัดข้อมูล", "s5_sub_n": "ประเมินกับชุดทดสอบ {n} ประกาศ · ",
        "s5_sub": "อ้างอิงป้ายที่จัดทำโดย AI ซึ่งยังไม่ผ่านการตรวจโดยบุคคลครบถ้วน",
        "ev": {"m": "วิธีสกัด", "n": "ประกาศที่ประเมิน", "sen": "ความถูกต้องระดับงาน", "role": "ความถูกต้องกลุ่มตำแหน่ง", "hv": "ป้ายที่ตรวจโดยบุคคล"},
        "s5_note": "หมายเหตุ: ผลของ baseline-dict เป็นค่าขอบเขตบน (upper bound) เนื่องจากพจนานุกรมถูกปรับระหว่างการตรวจป้ายชุดเดียวกัน · ผลของ LLM จะแสดงเมื่อสกัดชุดทดสอบครบ",
        "s5_none": "ยังไม่มีผลการประเมิน",
        "listing": "รายการประกาศในขอบเขตที่เลือก ({n})",
        "foot_src": "แหล่งข้อมูลและแนวปฏิบัติ:",
        "foot_src_v": "รวบรวมวันละครั้งจาก API สาธารณะอย่างเป็นทางการของ Greenhouse และ Lever · ระบุตัวตนผ่าน User-Agent · ไม่เรียกใช้ endpoint สำหรับการสมัครงาน · ไม่เก็บข้อมูลส่วนบุคคล · ไม่ใช้เว็บไซต์ที่ห้ามหรือไม่ระบุชัดเจนเรื่องการเก็บข้อมูลอัตโนมัติ (JobsDB, JobThai, LinkedIn, Indeed) รายละเอียดใน {sources}",
        "foot_m": "ระเบียบวิธี:",
        "foot_m_v": "ตัวเลขทั้งหมดคำนวณจากฐานข้อมูลและบันทึกไว้ใน {results} · ทักษะสกัดด้วย LLM (Gemini) หรือ baseline-dict ตามที่ระบุในรายการประกาศ",
        "role_other": "สายเทคอื่น ๆ", "sen_unknown": "ไม่ระบุ",
        "en_all": "ประกาศทั้งหมดเขียนเป็นภาษาอังกฤษ", "en_most": "ประกาศส่วนใหญ่เขียนเป็นภาษาอังกฤษ ({p})",
    },
    "en": {
        "brand": "Thai Tech Job Market Intelligence",
        "asof": "Data as of {d}",
        "title": "Skill Demand in Thailand's Tech Job Postings",
        "lede": "Based on job postings published on company applicant-tracking systems (Greenhouse and Lever), limited to tech roles based in Thailand, with duplicate postings removed before analysis.",
        "by": "Prepared by",
        "st_posts": "postings (deduplicated)", "st_cos": "companies", "st_days": "data period ({p})", "days_unit": " days", "st_skills": "distinct skills",
        "print": "Print / Save as PDF",
        "no_db": "No dashboard data found (data/marts/jobs.duckdb or data/snapshot/). Build it with start.bat or python -m src.marts.",
        "h_fail": "The latest collection run reported problems: {p}",
        "h_stale": "Latest data is from {d}; daily collection may have stopped (see logs/daily_log.txt).",
        "h_last": "The latest daily run did not complete: {p}",
        "scope_title": "Data coverage · collected {d}",
        "fun": ["All postings collected", "Tech roles in Thailand", "After deduplication (analysed)"],
        "fun_note": "Square-root axis scale; labels show actual counts.",
        "q_title": "Data quality and extraction method",
        "q_ext": "Skill extraction", "q_ext_v": "LLM (Gemini) {g}/{n} postings; the remainder use baseline-dict until extraction completes",
        "q_lab": "Reference labels for evaluation", "q_lab_v": "AI-generated · human-verified {h}/{n}",
        "q_con": "Source concentration", "q_con_v": "{c} {k}/{n} postings ({p})",
        "lim_title": "Data limitations and interpretation notes",
        "lim": ("1. The dataset covers postings collected from company applicant-tracking systems; it is not a view of the whole Thai labour market. Most companies are large or multinational, and {en}.\n"
                "2. One company accounts for a large share ({c}: {k} of {n} postings), so results mainly reflect that company.\n"
                "3. Some postings are multi-country or remote; use the “Location” filter to restrict to Thailand.\n"
                "4. baseline-dict matches terms from a dictionary, while the LLM can extract skills outside it; the two methods should not be compared directly (they can be filtered separately).\n"
                "5. Accuracy figures are measured against AI-generated labels that have not all been verified by a person; see {results}.\n"),
        "filters": "Filters", "f_role": "Role family", "f_role_help": "Default: BA, SA, DA", "f_sen": "Seniority", "f_top": "Skills shown",
        "f_loc": "Location", "loc": {"all": "All", "th": "Thailand-based", "multi": "Multi-country / remote"},
        "f_scope": "Posting status", "scope": {"open": "Currently open", "all": "All postings seen"}, "f_scope_help": "“Currently open” means seen in the latest collection.",
        "f_meth": "Extraction method", "meth": {"all": "All", "llm": "LLM only", "base": "baseline-dict only"}, "f_meth_help": "LLM and baseline-dict results should not be mixed for strict comparison.",
        "print_scope": "Selection: role family {r} · seniority {s} · location: {l} · {sc} · method: {m}",
        "none": "No postings match the selected filters. Widen the role family or seniority selection.",
        "k_n": "Postings in selection", "k_co": "Companies", "k_sk": "Skills per posting (median)", "k_sal": "Salary disclosed", "k_sal_help": "{a} of {n} postings",
        "small_n": "Small sample in this selection (n = {n}); results may change substantially as more postings arrive.",
        "s1": "Most frequently requested skills", "s1_sub": "{r} · {n} postings", "s1_lead": " · top: {l}",
        "skill": "Skill", "postings": "Postings", "share": "Share", "x_share": "Share of postings mentioning the skill",
        "s1_note": "Bar labels show posting counts · each skill counted once per posting", "csv": "Download CSV",
        "s2": "Skills by role family, seniority and location",
        "s2_sub": "Cell colour and value show the share of postings in each group that mention the skill · n = postings in group",
        "dim": "Compare by", "dims": {"role_family": "Role family", "seniority": "Seniority", "th_primary": "Location"},
        "grp_th": "Thailand", "grp_multi": "Multi-country / remote", "n_group": "Postings in group",
        "s2_small": "Groups with fewer than 10 postings ({g}) should be read with caution; shares from small samples are volatile.",
        "s3": "Salary", "s3_sub": "Market salary ranges by experience from an external survey, alongside salaries stated in the collected postings",
        "s3_ref": "Market reference ranges (THB per month) for the selected role families",
        "s3_band": "Experience", "bands": {"0-3": "0–3 yrs", "3-5": "3–5 yrs", "5-7": "5–7 yrs", "7+": "7+ yrs"},
        "s3_role": "Role family", "s3_title": "Source job title", "s3_min": "Min", "s3_max": "Max", "s3_axis": "THB per month",
        "s3_cite": "Source: {name} ({url}), Information Technology category · accessed {d} · market survey data, not derived from the collected postings and not company-specific{extra}",
        "s3_shared": " · Data Science/ML and Data Engineer share one range (the source reports Data Scientist / Data Engineer together)",
        "s3_noref": "No reference salary range is available for the selected role families.", "s3_tbl": "Reference salary table",
        "s3_post": "Salary stated in postings: <b>{a} of {n} postings ({p})</b> · only figures written in the posting are shown; nothing is estimated",
        "cols": {"company": "Company", "title": "Title", "role_family": "Role family", "seniority": "Seniority", "location": "Location",
                 "salary_min": "Min", "salary_max": "Max", "salary_currency": "Currency", "salary_period": "Period", "salary_text": "Posting text",
                 "first_seen": "First seen", "last_seen": "Last seen", "skills": "Skills", "url": "Link", "extraction_method": "Method"},
        "s4": "Skill demand over time", "s4_prog": "{d} of {m} days collected",
        "s4_note": "Trends are shown once at least {m} days of data are available.",
        "s4_pick": "Skills to plot (up to 3)", "week": "Week (starting Monday)", "y_open": "Share of open postings", "active": "Open postings",
        "s5": "Extraction accuracy", "s5_sub_n": "Test set of {n} postings · ",
        "s5_sub": "measured against AI-generated labels not yet fully verified by a person",
        "ev": {"m": "Method", "n": "Postings evaluated", "sen": "Seniority accuracy", "role": "Role-family accuracy", "hv": "Human-verified labels"},
        "s5_note": "Note: baseline-dict figures are an upper bound because the dictionary was tuned while reviewing the same labels · LLM results appear once the test set is fully extracted.",
        "s5_none": "No evaluation results yet.",
        "listing": "Postings in selection ({n})",
        "foot_src": "Sources and practice:",
        "foot_src_v": "Collected once a day from the official public APIs of Greenhouse and Lever · identified via User-Agent · no application endpoints are called · no personal data is stored · sites that prohibit or do not clearly permit automated collection (JobsDB, JobThai, LinkedIn, Indeed) are not used; see {sources}",
        "foot_m": "Method:",
        "foot_m_v": "All figures are computed from the database and recorded in {results} · skills are extracted by an LLM (Gemini) or baseline-dict, as shown in the postings list",
        "role_other": "Other tech", "sen_unknown": "Not stated",
        "en_all": "all postings are written in English", "en_most": "most postings are written in English ({p})",
    },
}
ROLE_NAME = {"BA": "Business Analyst", "SA": "System Analyst", "DA": "Data/BI Analyst", "DS/ML": "Data Science / ML",
             "Data Eng": "Data Engineer", "Software Eng": "Software Engineer", "Product": "Product"}
SEN_NAME = {"intern": "Intern", "junior": "Junior", "mid": "Mid", "senior": "Senior", "lead": "Lead/Staff", "manager": "Manager+"}


def _icon():
    try:
        return Image.open(ROOT / "assets" / "icon.png")
    except (OSError, ValueError):
        return None


def _embed(html: str, height: int):
    """ฝัง HTML ที่มี JavaScript (ปุ่มพิมพ์) — Streamlit รุ่นใหม่ใช้ st.iframe รุ่นเก่าใช้ components.html"""
    if hasattr(st, "iframe"):
        st.iframe(html, height=height)
    else:
        components.html(html, height=height)


def _salary_ref() -> dict:
    try:
        return json.loads((ROOT / "config" / "salary_reference.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _site() -> dict:
    try:
        return json.loads((ROOT / "config" / "site.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


st.set_page_config(page_title="Thai Tech Job Market Intelligence", page_icon=_icon(), layout="wide", initial_sidebar_state="collapsed")

# ภาษา: จำไว้ใน URL (?lang=en) เพื่อให้ลิงก์/รีเฟรชได้ภาษาเดิม
_qlang = st.query_params.get("lang", "th")
LANG = _qlang if _qlang in TXT else "th"
T = TXT[LANG]

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+Thai:wght@400;500;600;700&display=swap');
.stApp, .stApp p, .stApp label, .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp li, .stApp td, .stApp th, .stApp dt, .stApp dd,
.stApp button, .stApp input, .stApp textarea, [data-testid="stMetricValue"], [data-testid="stMetricLabel"] {{ font-family: {FONT}; }}
.stApp {{ background: {PAPER}; color: {INK}; }}
.block-container {{ padding-top: 1.4rem; padding-bottom: 3.5rem; max-width: 1240px; }}
#MainMenu, footer, .stDeployButton {{ visibility: hidden; }}

.masthead {{ background: {NAVY}; color: #fff; border-radius: 4px; padding: 24px 32px 0; margin-bottom: 14px; border-bottom: 4px solid {BLUE}; }}
.masthead .top {{ display: flex; justify-content: space-between; gap: 16px; flex-wrap: wrap; font-size: 12.5px; letter-spacing: .09em;
                 text-transform: uppercase; color: #9db4d3; font-weight: 500; }}
.masthead h1 {{ margin: 10px 0 8px; padding: 0; font-size: 28px; line-height: 1.35; font-weight: 700; color: #fff; }}
.masthead .lede {{ margin: 0 0 8px; max-width: 900px; font-size: 15px; line-height: 1.7; color: #c9d6e8; }}
.masthead .byline {{ margin: 0 0 18px; font-size: 13.5px; color: #9db4d3; }}
.masthead .byline b {{ color: #fff; font-weight: 600; }}
.masthead .stats {{ display: flex; flex-wrap: wrap; border-top: 1px solid rgba(255,255,255,.16); }}
.masthead .stats div {{ padding: 14px 28px 16px 0; margin-right: 28px; }}
.masthead .stats div + div {{ border-left: 1px solid rgba(255,255,255,.16); padding-left: 28px; }}
.masthead .stats b {{ display: block; font-size: 24px; font-weight: 700; color: #fff; line-height: 1.25; }}
.masthead .stats span {{ font-size: 13px; color: #9db4d3; }}
@media (max-width: 760px) {{ .masthead {{ padding: 20px 20px 0; }} .masthead h1 {{ font-size: 23px; }}
  .masthead .stats div {{ flex: 1 1 42%; margin-right: 0; padding: 12px 12px 12px 0; }}
  .masthead .stats div + div {{ border-left: none; padding-left: 0; }} }}

.panel-title {{ font-size: 14px; font-weight: 600; color: {INK}; margin: 0 0 6px; }}
.card {{ background: #fff; border: 1px solid {LINE}; border-radius: 4px; padding: 16px 20px; height: 100%; }}
.card dl {{ display: grid; grid-template-columns: 170px 1fr; gap: 10px 16px; margin: 0; font-size: 14px; line-height: 1.6; }}
.card dt {{ color: {MUTE}; }}
.card dd {{ margin: 0; color: {INK}; }}

.sec {{ margin: 38px 0 4px; padding-top: 12px; border-top: 1px solid {INK}; display: flex; align-items: baseline; gap: 14px; break-after: avoid; }}
.sec .num {{ font-size: 13px; font-weight: 600; color: {BLUE}; letter-spacing: .06em; }}
.sec h2 {{ margin: 0; padding: 0; font-size: 20px; font-weight: 700; color: {INK}; }}
.sub {{ color: {MUTE}; margin: 4px 0 12px; font-size: 14.5px; }}
.sub b {{ color: {INK}; }}

[data-testid="stMetric"] {{ background: #fff; border: 1px solid {LINE}; border-radius: 4px; padding: 14px 18px; }}
[data-testid="stMetricValue"] {{ font-weight: 700; color: {INK}; }}
[data-testid="stMetricLabel"] p {{ color: {MUTE}; font-size: 14px; }}
.callout {{ border: 1px solid {LINE}; border-left: 3px solid #b8c0cb; border-radius: 4px; padding: 13px 18px; background: #fff; color: {INK}; font-size: 14.5px; }}
.foot {{ margin-top: 44px; padding-top: 14px; border-top: 1px solid {LINE}; color: {MUTE}; font-size: 13px; line-height: 1.75; }}
.foot b {{ color: {INK}; font-weight: 600; }}
.foot a {{ color: {BLUE}; text-decoration: none; }}
.print-only {{ display: none; }}

@media print {{
  @page {{ size: A4; margin: 12mm; }}
  html, body, .stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"], section.stMain, .block-container {{
     overflow: visible !important; height: auto !important; position: static !important; }}
  .stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"], section.stMain {{ background: #fff !important; }}
  .block-container {{ padding: 0 !important; max-width: none !important; }}
  [data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stDecoration"], [data-testid="stStatusWidget"],
  .st-key-controls, .st-key-filters, .st-key-listing, .st-key-dimension, .stDownloadButton, iframe {{ display: none !important; }}
  .print-only {{ display: block; color: {MUTE}; font-size: 12.5px; margin: 6px 0 10px; }}
  .masthead, .sec .num {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
  [data-testid="stMetric"], .card, .vega-embed {{ break-inside: avoid; }}
}}
</style>
""", unsafe_allow_html=True)


def _data_source():
    """ใช้ฐานข้อมูลในเครื่องถ้ามี ไม่งั้นใช้ snapshot (กรณีเว็บออนไลน์) — คืน (ชนิด, เวลาแก้ไขล่าสุด) หรือ (None, 0)"""
    if DB.exists():
        return "db", DB.stat().st_mtime
    files = [SNAP / f"{t}.parquet" for t in SNAP_TABLES]
    if all(f.exists() for f in files):
        return "snapshot", max(f.stat().st_mtime for f in files)
    return None, 0.0


@st.cache_data(ttl=300)
def load(kind: str, _mtime: float):
    if kind == "db":
        con = duckdb.connect(str(DB), read_only=True)
    else:   # อ่าน Parquet ในหน่วยความจำ ไม่เขียนไฟล์ใด ๆ (ระบบไฟล์บนคลาวด์อาจเขียนไม่ได้)
        con = duckdb.connect()
        for t in SNAP_TABLES:
            path = (SNAP / f"{t}.parquet").as_posix().replace("'", "''")
            con.execute(f"CREATE VIEW {t} AS SELECT * FROM read_parquet('{path}')")
    try:
        jobs = con.execute("""SELECT p.*, a.role_family, a.seniority, a.salary_stated, a.salary_min, a.salary_max,
            a.salary_currency, a.salary_period, a.salary_text, a.extraction_method
            FROM job_postings p JOIN posting_attributes a USING (job_id)""").df()
        skills = con.execute("SELECT * FROM posting_skills").df()
        daily = con.execute("SELECT * FROM daily_active").df()
        funnel = con.execute("SELECT * FROM funnel ORDER BY day").df()
    finally:
        con.close()
    return jobs, skills, daily, funnel


@st.cache_data(ttl=300)
def load_eval(_stamp: float, lang: str):
    """ผลวัดความแม่นยำล่าสุดของแต่ละตัวสกัด (ชุด test) จาก data/eval/*.json ที่ src.evaluate เขียนไว้"""
    ev = TXT[lang]["ev"]
    latest = {}
    for f in sorted((ROOT / "data" / "eval").glob("eval_test_*.json")):
        try:
            r = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        latest[r.get("model")] = r   # ไฟล์เรียงตามเวลา: ตัวหลังชนะ
    rows = []
    for m, r in latest.items():
        s = r["skills"]
        rows.append({ev["m"]: m, ev["n"]: r["n_postings"], "Precision": s["precision"], "Recall": s["recall"], "F1": s["f1"],
                     ev["sen"]: r["seniority_accuracy"], ev["role"]: r["role_family_accuracy"],
                     ev["hv"]: f'{r.get("n_human_verified", 0)}/{r.get("n_gold", r["n_postings"])}'})
    return pd.DataFrame(rows)


def style(c):
    return (c.configure(font=FONT, background="rgba(0,0,0,0)")
            .configure_axis(grid=False, labelColor=MUTE, titleColor=MUTE, domainColor="#cfd5dd", tickColor="#cfd5dd", labelFontSize=12.5, titleFontSize=12.5)
            .configure_legend(labelColor=MUTE, titleColor=MUTE, labelFontSize=12)
            .configure_view(stroke=None))


def section(n: int, title: str, sub: str = ""):
    st.markdown(f'<div class="sec"><span class="num">{n:02d}</span><h2>{title}</h2></div>' + (f'<p class="sub">{sub}</p>' if sub else ""), unsafe_allow_html=True)


def _doc_link(name: str) -> str:
    """ลิงก์ไปยังเอกสารใน GitHub ถ้ากำหนด repo_url ใน config/site.json ไม่งั้นแสดงชื่อไฟล์"""
    repo = str(site.get("repo_url", "")).rstrip("/")
    return f'<a href="{escape(repo)}/blob/main/{name}" target="_blank">{name}</a>' if repo else name


def role_name(r: str) -> str:
    return T["role_other"] if r == "Other tech" else ROLE_NAME.get(r, r)


def sen_name(s: str) -> str:
    return T["sen_unknown"] if s == "unknown" else SEN_NAME.get(s, s)


SRC_KIND, SRC_MTIME = _data_source()
if SRC_KIND is None:
    st.error(T["no_db"])
    st.stop()

eval_dir = ROOT / "data" / "eval"
jobs, skills, daily, funnel = load(SRC_KIND, SRC_MTIME)
evals = load_eval(max([f.stat().st_mtime for f in eval_dir.glob("*.json")] or [0]), LANG)
n_all = len(jobs)
d0, d1, ndays = daily.seen_date.min(), daily.seen_date.max(), daily.seen_date.nunique()
methods = jobs.extraction_method.value_counts().to_dict()
n_gem = sum(v for k, v in methods.items() if not k.startswith("baseline"))
labels = read_jsonl(ROOT / "data" / "gold" / "labels.jsonl")
n_hv = sum(bool(r.get("human_verified")) for r in labels)
thai_share = jobs.raw_text.str.contains("[฀-๿]", regex=True).mean()
top_company, top_company_n = jobs.company.value_counts().index[0], int(jobs.company.value_counts().iloc[0])
site = _site()

# ---------- แจ้งเตือนสถานะการรวบรวมข้อมูล (แสดงเฉพาะเมื่อมีปัญหา) ----------
_h = ROOT / "data" / "health.json"
if _h.exists():
    try:
        health = json.loads(_h.read_text(encoding="utf-8"))
        if not health.get("ok", True):
            st.warning(T["h_fail"].format(p="; ".join(health.get("problems", []))))
        if (pd.Timestamp.now() - pd.Timestamp(health["run_date"])).days > 2:
            st.warning(T["h_stale"].format(d=health["run_date"]))
    except (OSError, ValueError, KeyError):
        pass
_f = ROOT / "logs" / "LAST_FAILED.txt"
if _f.exists():
    st.warning(T["h_last"].format(p=_f.read_text(encoding="utf-8", errors="replace").strip()))

# ---------- ส่วนหัว ----------
period = f"{pd.Timestamp(d0):%Y-%m-%d}" + ("" if ndays == 1 else f" – {pd.Timestamp(d1):%Y-%m-%d}")
author = " · ".join(escape(str(site[k])) for k in ("author", "affiliation") if site.get(k))
byline = f'<p class="byline">{T["by"]} <b>{author}</b></p>' if author else '<p class="byline"></p>'
st.markdown(f"""
<div class="masthead">
<div class="top"><span>{T["brand"]}</span><span>{T["asof"].format(d=f"{pd.Timestamp(d1):%Y-%m-%d}")}</span></div>
<h1>{T["title"]}</h1>
<p class="lede">{T["lede"]}</p>
{byline}
<div class="stats">
<div><b>{n_all:,}</b><span>{T["st_posts"]}</span></div>
<div><b>{jobs.company.nunique()}</b><span>{T["st_cos"]}</span></div>
<div><b>{ndays}{T["days_unit"] if ndays != 1 or LANG == "th" else " day"}</b><span>{T["st_days"].format(p=period)}</span></div>
<div><b>{skills.skill.nunique()}</b><span>{T["st_skills"]}</span></div>
</div>
</div>
""", unsafe_allow_html=True)

with st.container(key="controls"):
    _sp, c_lang, c_print = st.columns([6, 1.5, 1.6], vertical_alignment="center")
    new_lang = c_lang.segmented_control("lang", ["th", "en"], default=LANG, format_func=lambda x: {"th": "ไทย", "en": "English"}[x],
                                        key="lang_toggle", label_visibility="collapsed")
    if new_lang and new_lang != LANG:
        st.query_params["lang"] = new_lang
        st.rerun()
    with c_print:
        _embed(f"""<body style="margin:0;overflow:hidden">
<button onclick="window.parent.print()" style="width:100%;height:38px;border:1px solid {LINE};border-radius:4px;background:#fff;color:{INK};
 font:500 14px {FONT};cursor:pointer" onmouseover="this.style.borderColor='{BLUE}';this.style.color='{BLUE}'"
 onmouseout="this.style.borderColor='{LINE}';this.style.color='{INK}'">{T["print"]}</button>""", 42)

# ---------- ขอบเขตและคุณภาพข้อมูล ----------
c_left, c_right = st.columns([1.15, 1])
with c_left:
    if len(funnel) and pd.notna(funnel.raw_total.iloc[-1]):
        f = funnel.iloc[-1]
        fd = pd.DataFrame({"stage": T["fun"], "n": [int(f.raw_total), int(f.thai_tech), int(f.canonical)]})
        base = alt.Chart(fd).encode(y=alt.Y("stage:N", sort=None, title=None, axis=alt.Axis(labelLimit=330, labelOverlap=False)))
        bars = base.mark_bar(color=BLUE, cornerRadiusEnd=2, height=22).encode(x=alt.X("n:Q", title=None, axis=None, scale=alt.Scale(type="sqrt")))
        txt = base.mark_text(align="left", dx=6, color=INK, fontSize=13, fontWeight=600).encode(x="n:Q", text=alt.Text("n:Q", format=","))
        st.markdown(f'<div class="panel-title">{T["scope_title"].format(d=f"{pd.Timestamp(f.day):%Y-%m-%d}")}</div>', unsafe_allow_html=True)
        st.altair_chart(style((bars + txt).properties(height=130)), width="stretch")
        st.caption(T["fun_note"])
with c_right:
    st.markdown(f"""
<div class="card"><div class="panel-title">{T["q_title"]}</div><dl>
<dt>{T["q_ext"]}</dt><dd>{T["q_ext_v"].format(g=n_gem, n=n_all)}</dd>
<dt>{T["q_lab"]}</dt><dd>{T["q_lab_v"].format(h=n_hv, n=len(labels))}</dd>
<dt>{T["q_con"]}</dt><dd>{T["q_con_v"].format(c=escape(str(top_company)), k=top_company_n, n=n_all, p=f"{top_company_n / n_all:.0%}")}</dd>
</dl></div>""", unsafe_allow_html=True)

with st.expander(T["lim_title"], expanded=ndays < 7):
    en_txt = T["en_all"] if thai_share == 0 else T["en_most"].format(p=f"{1 - thai_share:.0%}")
    st.markdown(T["lim"].format(en=en_txt, c=escape(str(top_company)), k=top_company_n, n=n_all, results=_doc_link("results.md")), unsafe_allow_html=True)

# ---------- ตัวกรอง ----------
st.markdown("&nbsp;")
with st.container(border=True, key="filters"):
    st.markdown(f'<div class="panel-title">{T["filters"]}</div>', unsafe_allow_html=True)
    r1a, r1b, r1c = st.columns([2.2, 2.2, 1.2])
    roles_present = [r for r in ROLE_ORDER if r in set(jobs.role_family)]
    default_roles = [r for r in ["BA", "SA", "DA"] if r in roles_present] or roles_present
    sel_roles = r1a.multiselect(T["f_role"], roles_present, default=default_roles, format_func=lambda r: f"{r} · {role_name(r)}",
                                help=T["f_role_help"], key="f_roles")
    sen_present = [s for s in SEN_ORDER if s in set(jobs.seniority)]
    sel_sen = r1b.multiselect(T["f_sen"], sen_present, default=sen_present, format_func=sen_name, key="f_sen")
    top_n = r1c.slider(T["f_top"], 5, 25, 15, key="f_top")
    r2a, r2b, r2c = st.columns([2.2, 2.2, 1.2])
    loc = r2a.radio(T["f_loc"], ["all", "th", "multi"], format_func=T["loc"].get, horizontal=True, key="f_loc")
    scope = r2b.radio(T["f_scope"], ["open", "all"], format_func=T["scope"].get, horizontal=True, help=T["f_scope_help"], key="f_scope")
    if jobs.extraction_method.nunique() > 1:
        meth = r2c.selectbox(T["f_meth"], ["all", "llm", "base"], format_func=T["meth"].get, help=T["f_meth_help"], key="f_meth")
    else:
        meth = "all"

view = jobs[jobs.role_family.isin(sel_roles) & jobs.seniority.isin(sel_sen)]
if loc == "th":
    view = view[view.th_primary == True]  # noqa: E712
elif loc == "multi":
    view = view[view.th_primary != True]  # noqa: E712
if scope == "open":
    view = view[view.is_open == True]  # noqa: E712
if meth == "llm":
    view = view[~view.extraction_method.str.startswith("baseline")]
elif meth == "base":
    view = view[view.extraction_method.str.startswith("baseline")]
n = len(view)
if n == 0:
    st.warning(T["none"])
    st.stop()
vs = skills[skills.job_id.isin(view.job_id)]
roles_txt = ", ".join(sel_roles)
st.markdown('<div class="print-only">' + escape(T["print_scope"].format(
    r=roles_txt, s=", ".join(sen_name(s) for s in sel_sen), l=T["loc"][loc], sc=T["scope"][scope], m=T["meth"][meth])) + "</div>",
    unsafe_allow_html=True)

k1, k2, k3, k4 = st.columns(4)
k1.metric(T["k_n"], n)
k2.metric(T["k_co"], view.company.nunique())
k3.metric(T["k_sk"], int(vs.groupby("job_id").size().reindex(view.job_id, fill_value=0).median()))
k4.metric(T["k_sal"], f"{view.salary_stated.mean():.0%}", help=T["k_sal_help"].format(a=int(view.salary_stated.sum()), n=n))
if n < 30:
    st.info(T["small_n"].format(n=n))

# ---------- 01 ทักษะที่ปรากฏบ่อย ----------
top = (vs.groupby("skill").job_id.nunique().rename("postings").reset_index()
       .sort_values(["postings", "skill"], ascending=[False, True]).head(top_n))
top["share"] = top.postings / n
lead = ", ".join(f"<b>{escape(str(r.skill))}</b> ({r.share:.0%})" for r in top.head(3).itertuples())
section(1, T["s1"], T["s1_sub"].format(r=roles_txt, n=n) + (T["s1_lead"].format(l=lead) if len(top) else ""))
if len(top):
    bar = (alt.Chart(top).mark_bar(color=BLUE, cornerRadiusEnd=2, height={"band": 0.72})
           .encode(y=alt.Y("skill:N", sort="-x", title=None, axis=alt.Axis(labelOverlap=False, labelLimit=240, labelFontSize=13.5)),
                   x=alt.X("share:Q", title=T["x_share"], axis=alt.Axis(format="%", tickCount=5, grid=True, gridColor=GRID)),
                   tooltip=[alt.Tooltip("skill", title=T["skill"]), alt.Tooltip("postings", title=T["postings"]),
                            alt.Tooltip("share", title=T["share"], format=".0%")]))
    labels_ = bar.mark_text(align="left", dx=5, color=INK, fontSize=12.5).encode(text=alt.Text("postings:Q"))
    st.altair_chart(style((bar + labels_).properties(height=max(220, 27 * len(top)))), width="stretch")
    cc1, cc2 = st.columns([5, 1.4])
    cc1.caption(T["s1_note"])
    cc2.download_button(T["csv"], top.rename(columns={"skill": T["skill"], "postings": T["postings"], "share": T["share"]}).to_csv(index=False).encode("utf-8-sig"),
                        file_name="top_skills.csv", mime="text/csv", width="stretch")

# ---------- 02 เปรียบเทียบ ----------
section(2, T["s2"], T["s2_sub"])
with st.container(key="dimension"):
    col = st.radio(T["dim"], ["role_family", "seniority", "th_primary"], format_func=T["dims"].get, horizontal=True, key="f_dim")
dim = T["dims"][col]
v2 = view.assign(th_primary=view.th_primary.map({True: T["grp_th"]}).fillna(T["grp_multi"]))
grp_n = v2.groupby(col).job_id.nunique()
if len(top) and len(grp_n):
    m = vs.merge(v2[["job_id", col]], on="job_id")
    heat = m[m.skill.isin(top.skill)].groupby([col, "skill"]).job_id.nunique().rename("postings").reset_index()
    full = pd.MultiIndex.from_product([grp_n.index, top.skill], names=[col, "skill"])
    heat = heat.set_index([col, "skill"]).reindex(full, fill_value=0).reset_index()
    heat["n_group"] = heat[col].map(grp_n)
    heat["share"] = heat.postings / heat.n_group
    order = [x for x in (ROLE_ORDER if col == "role_family" else SEN_ORDER if col == "seniority" else [T["grp_th"], T["grp_multi"]]) if x in grp_n.index]
    shown = {"role_family": lambda g: g, "seniority": sen_name, "th_primary": lambda g: g}[col]
    heat["group_label"] = [f"{shown(g)} (n={gn})" for g, gn in zip(heat[col], heat.n_group)]
    glabels = [f"{shown(g)} (n={grp_n[g]})" for g in order]
    heat["cell"] = heat.share.map(lambda v: "" if v == 0 else f"{v:.0%}")
    x = alt.X("group_label:N", sort=glabels, title=None, axis=alt.Axis(labelAngle=0, orient="top", labelLimit=170, labelFontSize=13))
    y = alt.Y("skill:N", sort=list(top.skill), title=None, axis=alt.Axis(labelOverlap=False, labelLimit=240, labelFontSize=13.5))
    hm = (alt.Chart(heat).mark_rect(stroke="white", strokeWidth=2, cornerRadius=2)
          .encode(x=x, y=y, color=alt.Color("share:Q", scale=alt.Scale(range=SEQ, domain=[0, 1]), legend=alt.Legend(format="%", title=T["share"], tickCount=5)),
                  tooltip=[alt.Tooltip("skill", title=T["skill"]), alt.Tooltip("group_label:N", title=dim),
                           alt.Tooltip("postings", title=T["postings"]), alt.Tooltip("n_group", title=T["n_group"]),
                           alt.Tooltip("share", title=T["share"], format=".0%")]))
    cell_txt = (alt.Chart(heat).mark_text(fontSize=12)
                .encode(x=x, y=y, text="cell:N", color=alt.condition(alt.datum.share > 0.5, alt.value("white"), alt.value(INK))))
    st.altair_chart(style((hm + cell_txt).properties(height=max(220, 27 * len(top)))), width="stretch")
    small = [shown(g) for g in order if grp_n[g] < 10]
    if small:
        st.caption(T["s2_small"].format(g=", ".join(small)))

# ---------- 03 เงินเดือน ----------
section(3, T["s3"], T["s3_sub"])
ref = _salary_ref()
ref_rows = []
for r in sel_roles:
    info = ref.get("roles", {}).get(r)
    if not info:
        continue
    for band, rng in zip(ref.get("bands", []), info["ranges"]):
        if rng and rng[1]:
            ref_rows.append({"role": r, "label": f"{r} · {role_name(r)}", "src_title": info["source_title"],
                             "band": T["bands"].get(band, band), "bi": band, "min": rng[0], "max": rng[1]})
if ref_rows:
    rf = pd.DataFrame(ref_rows)
    band_order = [T["bands"][b] for b in ref["bands"]]
    role_order = list(dict.fromkeys(rf.label))
    st.markdown(f'<div class="panel-title">{T["s3_ref"]}</div>', unsafe_allow_html=True)
    rc = (alt.Chart(rf).mark_bar(cornerRadius=2)
          .encode(y=alt.Y("label:N", sort=role_order, title=None, scale=alt.Scale(paddingInner=0.25), axis=alt.Axis(labelLimit=260, labelFontSize=13, labelOverlap=False, domain=False, ticks=False)),
                  yOffset=alt.YOffset("band:N", sort=band_order, scale=alt.Scale(paddingInner=0.15)),
                  x=alt.X("min:Q", title=T["s3_axis"], axis=alt.Axis(format=",.0f", grid=True, gridColor=GRID, tickCount=8)),
                  x2="max:Q",
                  color=alt.Color("band:N", sort=band_order, scale=alt.Scale(domain=band_order, range=SEQ[1:]),
                                  legend=alt.Legend(title=T["s3_band"], orient="top")),
                  tooltip=[alt.Tooltip("label:N", title=T["s3_role"]), alt.Tooltip("src_title:N", title=T["s3_title"]),
                           alt.Tooltip("band:N", title=T["s3_band"]), alt.Tooltip("min:Q", title=T["s3_min"], format=","),
                           alt.Tooltip("max:Q", title=T["s3_max"], format=",")]))
    st.altair_chart(style(rc.properties(height=120 * len(role_order))), width="stretch")
    src = ref.get("source", {})
    shared = any(r in sel_roles for r in ("DS/ML", "Data Eng"))
    st.caption(T["s3_cite"].format(name=src.get("name", ""), url=src.get("url", ""), d=src.get("retrieved", ""), extra=T["s3_shared"] if shared else ""))
    with st.expander(T["s3_tbl"]):
        tb = rf.pivot_table(index=["label", "src_title"], columns="band", values=["min", "max"], aggfunc="first")
        tb = pd.DataFrame({b: [f"{int(tb[('min', b)].iloc[i]):,} – {int(tb[('max', b)].iloc[i]):,}" if pd.notna(tb[("min", b)].iloc[i]) else "—"
                               for i in range(len(tb))] for b in band_order if ("min", b) in tb.columns}, index=tb.index)
        tb = tb.reset_index().rename(columns={"label": T["s3_role"], "src_title": T["s3_title"]})
        st.dataframe(tb, hide_index=True, width="stretch")
else:
    st.caption(T["s3_noref"])

sal = view[view.salary_stated == True]  # noqa: E712
st.markdown(f'<p class="sub" style="margin-top:14px">{T["s3_post"].format(a=len(sal), n=n, p=f"{len(sal) / n:.0%}")}</p>', unsafe_allow_html=True)
if len(sal):
    sal_cols = ["company", "title", "role_family", "seniority", "salary_min", "salary_max", "salary_currency", "salary_period", "salary_text"]
    st.dataframe(sal[sal_cols], hide_index=True, width="stretch", column_config={c: T["cols"][c] for c in sal_cols})

# ---------- 04 แนวโน้ม ----------
section(4, T["s4"])
if ndays < TREND_MIN_DAYS:
    st.progress(min(ndays / TREND_MIN_DAYS, 1.0), text=T["s4_prog"].format(d=ndays, m=TREND_MIN_DAYS))
    st.caption(T["s4_note"].format(m=TREND_MIN_DAYS))
elif len(top):
    pick = st.multiselect(T["s4_pick"], list(top.skill), default=list(top.skill[:3]), max_selections=3, key="f_trend")
    if pick:
        d = daily[daily.job_id.isin(view.job_id)].copy()
        d["week"] = pd.to_datetime(d.seen_date).dt.to_period("W").dt.start_time
        wk = d.drop_duplicates(["week", "job_id"])
        tot = wk.groupby("week").job_id.nunique().rename("active")
        t = wk.merge(skills[skills.skill.isin(pick)], on="job_id").groupby(["week", "skill"]).job_id.nunique().rename("postings").reset_index()
        t = t.set_index(["week", "skill"]).reindex(pd.MultiIndex.from_product([tot.index, pick], names=["week", "skill"]), fill_value=0).reset_index()
        t = t.merge(tot, on="week")
        t["share"] = t.postings / t.active
        line = (alt.Chart(t).mark_line(strokeWidth=2.5, point=alt.OverlayMarkDef(size=70, filled=True))
                .encode(x=alt.X("week:T", title=T["week"], axis=alt.Axis(format="%d %b", tickCount="week", labelAngle=0)),
                        y=alt.Y("share:Q", title=T["y_open"], axis=alt.Axis(format="%", grid=True, gridColor=GRID)),
                        color=alt.Color("skill:N", scale=alt.Scale(domain=pick, range=[BLUE, ORANGE, AQUA][:len(pick)]), title=T["skill"]),
                        tooltip=[alt.Tooltip("week:T", title=T["week"]), alt.Tooltip("skill", title=T["skill"]),
                                 alt.Tooltip("postings", title=T["postings"]), alt.Tooltip("active", title=T["active"]),
                                 alt.Tooltip("share", title=T["share"], format=".0%")]))
        st.altair_chart(style(line.properties(height=320)), width="stretch")

# ---------- 05 ความแม่นยำของวิธีสกัด ----------
EV = T["ev"]
n_eval = int(evals[EV["n"]].max()) if len(evals) else 0
section(5, T["s5"], (T["s5_sub_n"].format(n=n_eval) if n_eval else "") + T["s5_sub"])
if len(evals):
    ev_show = evals.copy()
    for c in ["Precision", "Recall", "F1", EV["sen"], EV["role"]]:
        ev_show[c] = ev_show[c].map(lambda v: f"{v:.2f}")
    st.table(ev_show.set_index(EV["m"]))
    st.caption(T["s5_note"])
else:
    st.caption(T["s5_none"])

# ---------- รายการประกาศ ----------
st.markdown("&nbsp;")
sk = vs.groupby("job_id").skill.apply(lambda s: ", ".join(sorted(s, key=str.lower))).rename("skills")
list_cols = ["company", "title", "role_family", "seniority", "location", "first_seen", "last_seen", "skills", "url", "extraction_method"]
tbl = view.merge(sk, on="job_id", how="left")[list_cols]
with st.container(key="listing"):
    with st.expander(T["listing"].format(n=n)):
        cfg = {c: T["cols"][c] for c in list_cols}
        cfg["url"] = st.column_config.LinkColumn(T["cols"]["url"])
        st.dataframe(tbl, hide_index=True, width="stretch", column_config=cfg)
        st.download_button(T["csv"], tbl.rename(columns=T["cols"]).to_csv(index=False).encode("utf-8-sig"), file_name="job_postings.csv", mime="text/csv")

credit = ""
if author:
    credit = f'<br><b>{T["by"]}</b> {author}' + (f' · {escape(str(site["contact"]))}' if site.get("contact") else "")
st.markdown(f"""
<div class="foot">
<b>{T["foot_src"]}</b> {T["foot_src_v"].format(sources=_doc_link("SOURCES.md"))}<br>
<b>{T["foot_m"]}</b> {T["foot_m_v"].format(results=_doc_link("results.md"))}{credit}
</div>
""", unsafe_allow_html=True)
