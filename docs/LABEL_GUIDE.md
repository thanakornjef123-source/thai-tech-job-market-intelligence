# คู่มือติดป้ายชุดทดสอบ (gold labels)

ใช้ร่วมกันทั้งคนตรวจ ป้ายร่างจาก LLM และคำสั่ง (prompt) ของ Gemini — ข้อความเดียวกับ `DEFINITIONS` ใน `src/schema.py`

## ทักษะ (skills)
**นับ** ชื่อเฉพาะที่ประกาศพูดถึงว่า ต้องมี / มีแล้วดี / หรือเป็นเครื่องมือที่ทีมใช้ ("we use Scala and Kafka")
- ภาษาโปรแกรม, framework/library, ฐานข้อมูล, cloud และบริการ cloud, เครื่องมือ BI/วิเคราะห์ข้อมูล
- เครื่องมือพัฒนา (Git, Jira, Docker), ระบบองค์กร (SAP, Salesforce, Workday), เครื่องมือ AI ช่วยเขียนโค้ด (Cursor, Claude Code, Copilot)
- วิธีการที่มีชื่อ: Agile, Scrum, A/B Testing, CI/CD, ETL, Data Modeling, Machine Learning, LLM, RAG, System Design, TDD, Microservices, Statistics, Regression

**ไม่นับ** soft skill, ภาษาพูด, ปริญญา, จำนวนปี, ใบรับรอง (CSPO, CKA), กฎหมาย/มาตรฐานกำกับ (GDPR, SOX),
ความรู้ธุรกิจ (การเงิน, โลจิสติกส์), กิจกรรมทั่วไป ("data analysis", "dashboards", "project management", "distributed systems", "software architecture")
และข้อความโปรโมตบริษัทที่ไม่เกี่ยวกับตำแหน่ง

ชื่อที่เขียนต่างกันถูกรวมเป็นชื่อมาตรฐานด้วย `config/skills.json` ก่อนเทียบ (เช่น ReactJS → React)

## ระดับงาน (seniority)
intern · junior (จบใหม่/associate/0–2 ปี) · mid (2–5 ปี) · senior (5+ ปี หรือชื่อมี Senior) · lead (lead/staff/principal) · manager (ดูแลคน: manager/head/director) · unknown
- คำในชื่อตำแหน่งชนะจำนวนปี · "Product Manager" เป็นชื่อบทบาท ไม่ใช่ระดับผู้จัดการ
- "Associate Manager" ที่ระบุว่าไม่มีลูกทีม (individual contributor) = senior
- ชื่อที่ระบุหลายระดับ (Analyst/Senior Analyst) ใช้จำนวนปีตัดสิน · ไม่มีทั้งสองอย่าง = unknown

## กลุ่มตำแหน่ง (role_family)
BA (business analyst, strategy & analytics, insights) · SA (system analyst, IT BA, application specialist, HRIS analyst) ·
DA (data/BI/analytics analyst, BI developer) · DS/ML (data scientist, ML/AI engineer, research scientist) · Data Eng ·
Software Eng (รวม QA, DevOps, security, architect) · Product (PM/PO) · Other tech
ป้ายนี้ตัดสินจาก "งานจริง" ส่วนแดชบอร์ดที่ยังไม่มีผล LLM ใช้กฎจากชื่อตำแหน่ง (`config/role_families.json` — กฎเฉพาะอยู่ก่อนกฎกว้าง เช่น `data engineer` ก่อน `analytics`)

## เงินเดือน
ใส่เฉพาะตัวเลขที่เขียนในประกาศจริง คัดลอกข้อความตรงตัวลงช่อง salary_text ถ้าไม่มีให้ว่างทั้งหมด ห้ามเดา

## ภาษาพูด
เฉพาะที่ "ต้องใช้" (Mandarin → Chinese) · ภาษาที่เป็นแค่ข้อดี/โบนัส และเงื่อนไขสัญชาติ ไม่นับ

## ข้อควรรู้เรื่องความเป็นกลาง
- ป้ายทั้ง 80 ประกาศสร้างด้วย LLM (2026-10-07): ร่างจากการอ่านทุกประกาศ แล้วตรวจซ้ำโดยเทียบกับคำที่พจนานุกรมพบในข้อความ (แก้ 10 ประกาศ) — **ไม่ได้ผ่านการตรวจโดยคน**
- ถ้ามีคนตรวจภายหลังด้วย `run_label.bat` ป้ายนั้นจะถูกบันทึก human_verified = true (ป้ายที่ LLM ติดไว้ยังไม่นับว่าตรวจแล้วจนกว่าจะกดยืนยันทีละข้อ) และการรันรายวันจะวัดผลใหม่พร้อมระบุจำนวนป้ายที่คนตรวจ
- ตัวสกัดจริงคือ Gemini (คนละโมเดลกับที่ร่างป้าย)
- พจนานุกรม `config/skills.json` และกฎ `role_families.json` ถูกขยายระหว่างร่างป้ายชุดนี้ ดังนั้นคะแนนของ baseline บนชุดนี้ **สูงเกินจริง** ใช้เป็นเพดานบนของวิธีพจนานุกรม ไม่ใช่ค่าที่คาดว่าจะได้กับประกาศใหม่
