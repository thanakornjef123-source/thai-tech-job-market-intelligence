# SOURCES.md — ผลตรวจแหล่งข้อมูล (ช่วง 1)

วันที่ตรวจ: 2026-10-07

กฎที่ใช้ (จากเอกสารแผน): อ่านเงื่อนไขการใช้งาน + robots.txt ก่อนเก็บ · ถ้าห้ามหรือไม่แน่ใจ = **ไม่เก็บ** และรายงาน · ใช้ API/ฟีดที่อนุญาตชัดเจนก่อน · เก็บเฉพาะเนื้อหาประกาศ ไม่เก็บข้อมูลส่วนบุคคล

สถานะ: ✅ ใช้ได้ · ⚠️ ไม่แน่ใจ (ไม่เก็บจนกว่าได้รับอนุญาตเป็นลายลักษณ์อักษร) · ❌ ห้าม

## สรุปตาราง

| แหล่ง | ประเภท | ผลตรวจ | เหตุผลสั้นๆ | ลิงก์ที่ใช้ตรวจ |
|---|---|---|---|---|
| Greenhouse Job Board API | API ทางการของ ATS | ✅ | เอกสารทางการระบุว่าข้อมูล job board เป็นสาธารณะ GET ไม่ต้องยืนยันตัวตน · robots.txt ห้ามเฉพาะ `/embed/` | https://developers.greenhouse.io/job-board.html · https://boards-api.greenhouse.io/robots.txt |
| Lever Postings API | API ทางการของ ATS | ✅ | เอกสารทางการระบุว่าประกาศสถานะ published เป็นสาธารณะและบุคคลภายนอกอาจดึงไปได้ · robots.txt `Allow: /`, `Crawl-delay: 1` | https://github.com/lever/postings-api · https://api.lever.co/robots.txt |
| JobsDB (th.jobsdb.com, SEEK) | เว็บหางาน | ❌ | ข้อกำหนดของ SEEK/JobsDB ห้ามใช้ data mining, robots, screen scraping เว้นแต่ได้รับความยินยอมเป็นลายลักษณ์อักษร · เครื่องมือตรวจของเราถูกบล็อก bot detection ที่ th.jobsdb.com จึงอ่านข้อกำหนดจากหน้าเดียวกันของ hk.jobsdb.com / sg.jobstreet.com (ข้อกำหนดชุดเดียวที่ครอบคลุม "JobsDB by SEEK") | https://hk.jobsdb.com/en-hk/pages/terms/terms-conditions |
| JobThai (jobthai.com, THiNKNET) | เว็บหางาน | ⚠️→ไม่เก็บ | robots.txt ของเว็บปฏิเสธการเข้าถึงอัตโนมัติจากเครื่องมือตรวจของเรา และอ่านหน้า Terms of Service ไม่ได้ด้วยเหตุเดียวกัน → ถือว่า "ไม่แน่ใจ" ตามกฎข้อ 2 | https://www.jobthai.com/th/terms-of-service (เปิดอ่านด้วยตาเองได้) |
| LinkedIn Jobs | เว็บหางาน | ❌ | User Agreement ห้ามใช้ crawler/bot/script ดึงหรือคัดลอกข้อมูล (มีคดี hiQ ยืนยันการบังคับใช้) · หน้าทางการบล็อกเครื่องมือตรวจ อ่านผ่านแหล่งสรุปข้อกำหนด | https://www.linkedin.com/legal/user-agreement |
| Indeed | เว็บหางาน | ❌ | Publisher API ปิดไปแล้ว ไม่มี job-search API แบบสมัครเองได้ และ Developer Agreement ห้าม scraping/สร้างฐานข้อมูล | https://vorplabs.com/agent-tools/indeed-api (สรุป) |
| Careerjet Search API | API ของ aggregator (มี locale `th_TH`) | ⚠️ | ต้องสมัคร publisher account · ออกแบบมาเพื่อแสดงผลการค้นหาบนเว็บของ publisher และบังคับส่ง IP/User-Agent ของผู้ใช้ปลายทางทุกครั้ง · ไม่เห็นข้อความที่อนุญาตการเก็บสะสมเพื่อวิเคราะห์ · คืนเฉพาะ excerpt ไม่ใช่เนื้อหาเต็ม | https://www.careerjet.com/partners/api · https://www.careerjet.com/partners/publishers |
| Jooble REST API | API ของ aggregator | ⚠️ | ต้องกรอกฟอร์มขอ key · วัตถุประสงค์ที่ระบุคือให้ webmaster นำผลค้นหาไปแสดงบนเว็บตัวเอง · ไม่เห็นข้อความอนุญาตการเก็บสะสม | https://jooble.org/api/about · https://jooble.org/info/terms |
| data.go.th (กรมการจัดหางาน/สำนักงานจังหวัด) | Open data | ✅ แต่ไม่ตอบโจทย์หลัก | ใบอนุญาต Open Data Common แต่เป็นตัวเลขตำแหน่งว่างรวมรายจังหวัด อัปเดตรายปี ไม่มีเนื้อหาประกาศ → ใช้เป็นบริบทได้เท่านั้น | https://gdcc.data.go.th/en/dataset/dataset_14_22 |
| Scraper สำเร็จรูปบน Apify (JobsDB/JobThai/Indeed) | บริการบุคคลที่สาม | ❌ ไม่ใช้ | เป็นการเก็บจากเว็บที่ห้าม/ไม่แน่ใจผ่านคนกลาง = "หาวิธีอ้อม" ตามกฎข้อ 2 | — |

## รายละเอียดแหล่งที่ใช้ได้

### Greenhouse Job Board API
- Endpoint: `GET https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true` (ได้เนื้อหาประกาศเต็ม, location, department, `first_published`, `updated_at`)
- มี `?pay_transparency=true` ต่อประกาศ (ใช้ได้เฉพาะบริษัทที่เปิดเผยช่วงเงินเดือน)
- ทดสอบจริง 2026-10-07: board `agoda` ตอบกลับได้ มีประกาศที่กรุงเทพหลายตำแหน่งในกลุ่มเป้าหมาย เช่น Business Analyst (Supply Analytics), Associate Data Analyst (New Graduate, Thai Speaking), BI Engineer
- ต้องสร้างรายชื่อ board_token ของบริษัทที่มีตำแหน่งในไทยเอง (ทำในช่วง 2)

### Lever Postings API
- Endpoint: `GET https://api.lever.co/v0/postings/{site}?mode=json` (มี `descriptionPlain`, `lists`, `categories.location`, `salaryRange` ถ้ามี)
- robots.txt กำหนด crawl-delay 1 วินาที → ตัวเก็บต้องหน่วงอย่างน้อย 1 วินาที/คำขอ
- ยังไม่ได้ยืนยันว่าบริษัทในไทยรายใดใช้ Lever (ทำในช่วง 2)

## ข้อจำกัดที่ต้องรู้ (กระทบขอบเขตโปรเจกต์)

1. **ประกาศจาก ATS เป็นของบริษัทขนาดใหญ่/ต่างชาติ และเกือบทั้งหมดเป็นภาษาอังกฤษ** — ไม่ใช่ภาพตัวแทนของตลาดงานไทย และจะมีประกาศไทยปนอังกฤษน้อยมาก ซึ่งเป็นจุดขายข้อหนึ่งของแผน
2. แหล่งที่มีประกาศภาษาไทยจำนวนมาก (JobThai, JobsDB) **ใช้ไม่ได้** หากไม่ได้รับอนุญาตเป็นลายลักษณ์อักษร
3. ปริมาณต่อวันน่าจะเป็นหลักสิบถึงหลักร้อยประกาศ ไม่ใช่หลักพัน
4. ตัวเก็บต้องรันบนเครื่องที่เข้าถึงอินเทอร์เน็ตได้ปกติ (เครื่องของผู้จัดทำ หรือ CI เช่น GitHub Actions)

## ทางเลือกเพื่อให้ได้ประกาศภาษาไทย (ต้องได้รับอนุญาตก่อน)
- ส่งอีเมลขออนุญาตเป็นลายลักษณ์อักษรจาก JobThai (support@jobthai.com) และ JobsDB/SEEK สำหรับโปรเจกต์การศึกษา ไม่เชิงพาณิชย์ เก็บวันละครั้ง
- ส่งอีเมลถาม Careerjet / Jooble ว่าการเก็บสะสมเพื่อวิเคราะห์ (ไม่แสดงผลซ้ำ) อนุญาตหรือไม่
- เก็บด้วยมือจำนวนน้อย (เช่น 150–200 ประกาศสำหรับชุดทดสอบ) ยังต้องตรวจเงื่อนไขของเว็บต้นทางก่อนเช่นกัน

## อัปเดต 2026-10-07 (หลังทดลองเก็บจริง)
- เพิ่ม **Sertis, Xendit, Thoughtworks** (Greenhouse Job Board API — เงื่อนไขเดียวกับข้างบน) พบจาก `src/discover.py` ที่ลอง 60 ชื่อ
- ถอด **tsmg** (4,360 ประกาศทั่วโลก ประกาศไทยเป็นงานเก็บข้อมูลภาคสนาม) และ **rws** (ประกาศไทยเป็นงานถอดเสียง AI) เพราะไม่ใช่สายเทค
- LLM: Gemini API ฟรีเทียร์ — ข้อกำหนดระบุว่าข้อมูลจากบริการฟรีอาจถูกใช้ปรับปรุงระบบและมีคนอ่านได้ ห้ามส่งข้อมูลส่วนบุคคล → ส่งเฉพาะเนื้อหาประกาศงานสาธารณะ (https://ai.google.dev/gemini-api/terms)

## แหล่งอ้างอิงเงินเดือน (เพิ่ม 2026-10-08)

- **Adecco Thailand Salary Guide — E-Salary Search** (https://www.adecco.com/en-th/salary-guide/search)
  - ใช้ช่วงเงินเดือนรายตำแหน่งในหมวด Information Technology 6 ตำแหน่ง (Business Analyst, System Analyst, Data Analyst, Data Scientist / Data Engineer, Software Engineer, Product Manager) แยก 4 ช่วงประสบการณ์ บันทึกไว้ใน `config/salary_reference.json`
  - เปิดอ่านจากหน้าเว็บสาธารณะด้วยมือครั้งเดียว ไม่ได้ตั้งระบบดึงอัตโนมัติ และแสดงพร้อมอ้างอิงที่มาทุกครั้ง
  - เป็นข้อมูลสำรวจตลาด ไม่ได้มาจากประกาศที่ระบบรวบรวม จึงแสดงแยกจากเงินเดือนที่ระบุในประกาศ
  - ควรตรวจทานตัวเลขใหม่เมื่อ Adecco ออกฉบับปีถัดไป
