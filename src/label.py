"""หน้าเว็บตรวจป้ายชุดทดสอบ (เปิดบนเครื่องตัวเองเท่านั้น ไม่ส่งข้อมูลออกนอกเครื่อง)
ใช้: python -m src.label   แล้วเบราว์เซอร์จะเปิด http://127.0.0.1:8765
- เริ่มจากป้ายร่างที่สร้างด้วย LLM (data/gold/drafts.jsonl) ถ้ายังไม่เคยตรวจ
- กด "ยืนยัน" = ตรวจแล้ว (verified) ถ้าแก้อะไรไป จะบันทึก human_edited = true และเก็บว่าแก้อะไร
- ผลอยู่ที่ data/gold/labels.jsonl (เขียนไฟล์ใหม่ทั้งไฟล์ทุกครั้งที่บันทึก แบบเขียนชั่วคราวแล้วแทนที่ ไม่เสียของเดิมถ้าดับกลางทาง)
- ป้ายที่ AI ติดไว้ยังไม่นับว่า "ตรวจแล้ว" จนกว่าคุณจะกดยืนยันข้อนั้น (human_verified = true)
"""
from __future__ import annotations

import json
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from src import baseline, schema
from src.jsonl import read_jsonl, write_jsonl

ROOT = Path(__file__).resolve().parent.parent
GOLD = ROOT / "data" / "gold"
FIELDS = ("skills", "seniority", "role_family", "spoken_languages", "salary_min", "salary_max", "salary_currency", "salary_period", "salary_text")
PORT = 8765
ALLOWED_HOSTS = {f"127.0.0.1:{PORT}", f"localhost:{PORT}"}
_LOCK = threading.Lock()   # บันทึกทีละคำขอ (เซิร์ฟเวอร์เป็นแบบหลายเธรด)
_load = read_jsonl


def state() -> dict:
    sample = _load(GOLD / "sample.jsonl")
    drafts = {r["job_id"]: r for r in _load(GOLD / "drafts.jsonl")}
    labels = {r["job_id"]: r for r in _load(GOLD / "labels.jsonl")}
    items = []
    for s in sample:
        lab = labels.get(s["job_id"]) or drafts.get(s["job_id"]) or {"skills": [], "seniority": "unknown", "role_family": "Other tech", "spoken_languages": []}
        items.append({"post": s, "label": lab, "draft": drafts.get(s["job_id"]),
                      "dict_hits": baseline.skills_from_text(s["raw_text"])})
    return {"items": items, "seniority": schema.SENIORITY, "roles": schema.ROLE_FAMILIES}


def save(job_id: str, new: dict):
    """บันทึกป้ายที่คนตรวจ 1 ข้อ — เขียนไฟล์ชั่วคราวแล้วค่อยแทนที่ (ปิดเครื่องกลางทางก็ไม่เสียป้ายเดิม)"""
    with _LOCK:
        sample = {r["job_id"]: r for r in _load(GOLD / "sample.jsonl")}
        if job_id not in sample:
            raise KeyError(job_id)
        drafts = {r["job_id"]: r for r in _load(GOLD / "drafts.jsonl")}
        labels = {r["job_id"]: r for r in _load(GOLD / "labels.jsonl")}
        prev = labels.get(job_id, {})
        d = drafts.get(job_id, {})
        norm = lambda v: sorted(v) if isinstance(v, list) else v
        base = prev if prev else d   # เทียบกับป้ายเดิมของ AI (ถ้ามี) เพื่อรู้ว่าคนแก้อะไร
        changed = [k for k in FIELDS if norm(new.get(k)) != norm(base.get(k))]
        was_ai = bool(d) or str(prev.get("labeler", "")).startswith("claude")
        labels[job_id] = {"job_id": job_id, "split": sample[job_id]["split"], **{k: new.get(k) for k in FIELDS},
                          "labeler": "claude+human" if was_ai else "human", "verified": True, "human_verified": True,
                          "human_edited": bool(changed) or bool(prev.get("human_edited")),
                          "review_passes": prev.get("review_passes", 0), "changed_fields": changed or prev.get("changed_fields", [])}
        order = [j for j in sample if j in labels]
        GOLD.mkdir(parents=True, exist_ok=True)
        write_jsonl(GOLD / "labels.jsonl", [labels[j] for j in order])
        return labels[job_id]


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        b = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code); self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

    def _guard(self) -> bool:
        """รับเฉพาะคำขอจากหน้านี้บนเครื่องตัวเอง (กันเว็บอื่นในเบราว์เซอร์ยิงมาแก้ป้าย)"""
        host = self.headers.get("Host", "")
        origin = self.headers.get("Origin")
        if host not in ALLOWED_HOSTS or (origin and origin.replace("http://", "") not in ALLOWED_HOSTS):
            self._send(403, '{"error":"forbidden"}')
            return False
        return True

    def do_GET(self):
        if not self._guard():
            return
        if self.path == "/":
            return self._send(200, PAGE, "text/html; charset=utf-8")
        if self.path == "/api/state":
            return self._send(200, json.dumps(state(), ensure_ascii=False))
        self._send(404, "{}")

    def do_POST(self):
        if not self._guard():
            return
        if self.path != "/api/save":
            return self._send(404, "{}")
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))).decode("utf-8"))
            out = save(body["job_id"], body["label"])
        except (KeyError, ValueError, TypeError):
            return self._send(400, '{"error":"bad request"}')
        self._send(200, json.dumps(out, ensure_ascii=False))


PAGE = r"""<!doctype html><html lang="th"><head><meta charset="utf-8"><title>ตรวจป้ายชุดทดสอบ</title>
<style>
:root{--bg:#f7f6f2;--card:#fff;--ink:#1d1d1b;--mute:#6b6a64;--line:#e3e1d9;--acc:#2f5d8a;--ok:#2e7d4f;--warn:#a65b00;--hl:#fff1a8}
*{box-sizing:border-box}body{margin:0;font:15px/1.55 system-ui,"Segoe UI",Tahoma,sans-serif;background:var(--bg);color:var(--ink)}
header{position:sticky;top:0;background:var(--ink);color:#fff;padding:10px 16px;display:flex;gap:16px;align-items:center;z-index:2;flex-wrap:wrap}
header b{font-size:16px}#prog{flex:1;min-width:200px}.bar{height:8px;background:#444;border-radius:4px;overflow:hidden}.bar i{display:block;height:100%;width:0;background:#7bc89a}
main{display:grid;grid-template-columns:1fr 420px;gap:16px;padding:16px;max-width:1500px;margin:auto}
@media(max-width:1000px){main{grid-template-columns:1fr}}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px}
#text{white-space:pre-wrap;max-height:calc(100vh - 150px);overflow:auto;font-size:14px}
mark{background:var(--hl);border-radius:3px;padding:0 1px}
h2{margin:0 0 4px;font-size:18px}.meta{color:var(--mute);font-size:13px;margin-bottom:10px}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin:6px 0}.chip{border:1px solid var(--line);border-radius:999px;padding:2px 8px;font-size:13px;background:#fafaf7;cursor:pointer}
.chip.on{background:#e8f0f8;border-color:#b9cde3}.chip.on:hover{text-decoration:line-through;background:#fde8e8}
.chip.sug{border-style:dashed;color:var(--warn)}.chip.sug:hover{background:#fff5e6}
label{display:block;font-weight:600;margin-top:12px;font-size:13px}select,input{font:inherit;padding:6px 8px;border:1px solid var(--line);border-radius:6px;width:100%}
.row{display:grid;grid-template-columns:1fr 1fr;gap:8px}button{font:inherit;padding:8px 14px;border-radius:8px;border:0;cursor:pointer}
.ok{background:var(--ok);color:#fff}.nav{background:#e9e7df}.small{font-size:12px;color:var(--mute)}
#list{display:flex;flex-wrap:wrap;gap:3px;margin-top:8px}#list a{width:22px;height:22px;font-size:11px;display:grid;place-items:center;border-radius:4px;background:#ddd;color:#333;text-decoration:none}
#list a.v{background:#7bc89a}#list a.cur{outline:2px solid var(--acc)}
</style></head><body>
<header><b>ตรวจป้ายชุดทดสอบ</b><div id="prog"><div class="small" style="color:#ccc" id="ptext"></div><div class="bar"><i id="pbar"></i></div></div>
<button class="nav" onclick="go(-1)">← ก่อนหน้า</button><button class="nav" onclick="nextTodo()">ข้อถัดไปที่ยังไม่ตรวจ →</button></header>
<main><section class="card"><h2 id="title">กำลังโหลด… (ประมาณ 3 วินาที)</h2><div class="meta" id="meta"></div><div id="text"></div></section>
<aside class="card">
<div class="small">กติกาย่อ: ทักษะ = ชื่อเครื่องมือ/ภาษา/แพลตฟอร์ม/วิธีการที่ระบุชื่อ (เช่น SQL, Tableau, A/B Testing) ไม่รวม soft skill, ภาษาพูด, ปริญญา, จำนวนปี, ใบรับรอง, กฎหมาย, ความรู้ธุรกิจ · ดู docs/LABEL_GUIDE.md</div>
<label>ทักษะ (คลิกเพื่อลบ)</label><div class="chips" id="skills"></div>
<input id="add" placeholder="พิมพ์ทักษะแล้วกด Enter (คั่นหลายตัวด้วย ,)">
<label>พบในข้อความแต่ยังไม่อยู่ในป้าย (คลิกเพื่อเพิ่ม ถ้าใช่)</label><div class="chips" id="sugs"></div>
<div class="row"><div><label>ระดับงาน</label><select id="sen"></select></div><div><label>กลุ่มตำแหน่ง</label><select id="role"></select></div></div>
<label>ภาษาที่ต้องใช้ (คั่นด้วย ,)</label><input id="langs">
<label>เงินเดือน (เฉพาะที่เขียนไว้จริง ถ้าไม่มีปล่อยว่าง)</label>
<div class="row"><input id="smin" placeholder="ต่ำสุด"><input id="smax" placeholder="สูงสุด"></div>
<div class="row" style="margin-top:6px"><input id="scur" placeholder="สกุลเงิน เช่น THB"><select id="sper"><option value="">-</option><option>month</option><option>year</option><option>hour</option><option>day</option></select></div>
<input id="stext" style="margin-top:6px" placeholder="ข้อความเงินเดือนตามประกาศ (คัดลอกตรงตัว)">
<div style="display:flex;gap:8px;margin-top:16px;align-items:center"><button class="ok" onclick="saveIt()">✓ ยืนยันและไปต่อ (Ctrl+Enter)</button><span id="status" class="small"></span></div>
<div id="list"></div></aside></main>
<script>
let S,i=0,cur;const $=id=>document.getElementById(id);
const esc=s=>s.replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
async function load(){S=await (await fetch('/api/state')).json();$('sen').innerHTML=S.seniority.map(x=>`<option>${x}</option>`).join('');$('role').innerHTML=S.roles.map(x=>`<option>${x}</option>`).join('');nextTodo(true)}
function vcount(){return S.items.filter(x=>x.label.human_verified).length}
function show(){const it=S.items[i];cur=JSON.parse(JSON.stringify(it.label));$('title').textContent=`#${i+1} ${it.post.title}`;
$('meta').textContent=`${it.post.company} · ${it.post.location||''} · split=${it.post.split}${it.label.human_verified?' · ตรวจแล้วโดยคุณ':' · ป้ายร่างจาก AI ยังไม่ได้ตรวจ'}`;
$('sen').value=cur.seniority;$('role').value=cur.role_family;$('langs').value=(cur.spoken_languages||[]).join(', ');
$('smin').value=cur.salary_min??'';$('smax').value=cur.salary_max??'';$('scur').value=cur.salary_currency??'';$('sper').value=cur.salary_period??'';$('stext').value=cur.salary_text??'';
render();const n=vcount();$('ptext').textContent=`ตรวจแล้ว ${n}/${S.items.length}`;$('pbar').style.width=(100*n/S.items.length)+'%';
$('list').innerHTML=S.items.map((x,k)=>`<a href="#" class="${x.label.human_verified?'v':''} ${k==i?'cur':''}" onclick="i=${k};show();return false">${k+1}</a>`).join('');$('status').textContent=''}
function render(){const it=S.items[i];$('skills').innerHTML=cur.skills.map((s,k)=>`<span class="chip on" onclick="cur.skills.splice(${k},1);render()">${esc(s)}</span>`).join('');
const have=new Set(cur.skills.map(s=>s.toLowerCase()));$('sugs').innerHTML=it.dict_hits.filter(s=>!have.has(s.toLowerCase())).map(s=>`<span class="chip sug" onclick="cur.skills.push('${s.replace(/'/g,"\\'")}');render()">+ ${esc(s)}</span>`).join('')||'<span class="small">—</span>';
let t=esc(it.post.raw_text);const terms=[...cur.skills].sort((a,b)=>b.length-a.length).filter(s=>s.length>1);
for(const s of terms){const rx=new RegExp('(?<![\\w])('+s.replace(/[.*+?^${}()|[\]\\/]/g,'\\$&')+')(?![\\w])','gi');t=t.replace(rx,'<mark>$1</mark>')}$('text').innerHTML=t}
$('add').addEventListener('keydown',e=>{if(e.key==='Enter'){e.target.value.split(',').map(s=>s.trim()).filter(Boolean).forEach(s=>{if(!cur.skills.some(x=>x.toLowerCase()==s.toLowerCase()))cur.skills.push(s)});e.target.value='';render()}});
document.addEventListener('keydown',e=>{if(e.key==='Enter'&&(e.ctrlKey||e.metaKey))saveIt()});
const num=v=>v.trim()===''?null:Number(v.replace(/,/g,''));const str=v=>v.trim()===''?null:v.trim();
async function saveIt(){const lab={skills:cur.skills,seniority:$('sen').value,role_family:$('role').value,spoken_languages:$('langs').value.split(',').map(s=>s.trim()).filter(Boolean),
salary_min:num($('smin').value),salary_max:num($('smax').value),salary_currency:str($('scur').value),salary_period:str($('sper').value),salary_text:str($('stext').value)};
const r=await fetch('/api/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({job_id:S.items[i].post.job_id,label:lab})});
S.items[i].label=await r.json();$('status').textContent='บันทึกแล้ว';nextTodo()}
function go(d){i=Math.max(0,Math.min(S.items.length-1,i+d));show()}
function nextTodo(first){const k=S.items.findIndex((x,k)=>!x.label.human_verified&&(first||k!==i));if(k<0){alert('ตรวจครบทุกข้อแล้ว');}else i=k;show()}
load();
</script></body></html>"""


def main():
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), H)
    url = f"http://127.0.0.1:{PORT}"
    print(f"เปิด {url}  (ปิดหน้าต่างนี้เพื่อหยุด)")
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    srv.serve_forever()


if __name__ == "__main__":
    main()
