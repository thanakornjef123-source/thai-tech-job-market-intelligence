"""หาบริษัทเพิ่ม: ลองชื่อ token ที่เดาไว้บน Greenhouse และ Lever แล้วนับประกาศที่อยู่ในไทย
ใช้: python -m src.discover   → เขียนผลที่ data/discover_<date>.json (ไม่แก้ config เอง ให้คนตรวจก่อน)
ส่งคำขอ 1–2 ครั้งต่อชื่อ หน่วง 2 วินาที
"""
import json
import time
import urllib.error
from datetime import datetime

from src import collect, stage

CANDIDATES = [
    "lineman", "linemanwongnai", "wongnai", "bitkub", "omise", "opn", "opnpayments", "scb10x", "scbtechx", "kbtg",
    "ascend", "ascendmoney", "truedigital", "pomelo", "pomelofashion", "flashexpress", "flashgroup", "sertis", "datawow",
    "skooldio", "wisesight", "ninjavan", "airasia", "airasiadigital", "capitala", "xendit", "2c2p", "finnomena", "jitta",
    "ookbee", "priceza", "amity", "amitysolutions", "eko", "zipmex", "okx", "bybit", "kucoin", "cryptocom", "gojek",
    "rakuten", "deliveryhero", "foodpanda", "grab", "seamoney", "shopback", "carousell", "propertyguru", "ttb", "krungsri",
    "aiyara", "builk", "monix", "sunday", "rabbitcare", "ricult", "hubspot", "canva", "workato", "thoughtworks",
]
# รอบที่ 2 (2026-10-08): บริษัทที่มีสำนักงาน/ทีมเทคในกรุงเทพฯ หรือเอเชียตะวันออกเฉียงใต้
CANDIDATES += [
    "fastwork", "bitazza", "kasikornlabs", "kbank", "kasikornbusinessgroup", "centraltech", "centralgroup", "robinhood",
    "pttdigital", "hiveground", "kaidee", "seekster", "arcadia", "nium", "aspire", "thunes", "fundingsocieties",
    "airwallex", "doctoranywhere", "carro", "glints", "employmenthero", "rapyd", "checkoutcom", "chainalysis", "paxos",
    "kraken", "wise", "atome", "advance", "advanceintelligence", "aicadium", "tiket", "traveloka", "xendit", "ascendcorp",
    "trueidc", "dataiku", "databricks", "snowflake", "mongodb", "elastic", "gitlab", "zendesk", "agodaservices",
    "bookingholdings", "expedia", "klook", "tripcom", "foodpandathailand", "lalamove", "deliveree", "ezyhaul", "shippop",
    "boxme", "line", "linecorp", "lineplus", "seagroup", "garena", "moneylion", "kredivo", "akulaku", "tonik", "ula",
    "pace", "hoolah", "grabtaxi", "goto", "mekari", "accelbyte", "playstudios", "ubisoft", "yoozoo", "wildlife",
]
CANDIDATES = list(dict.fromkeys(CANDIDATES))  # ตัดชื่อซ้ำ คงลำดับเดิม



def run():
    cfg = collect.load_config()
    f = stage.load_filters()
    out = []
    have = {t.lower() for k in ("greenhouse", "lever") for t in cfg.get(k, [])}
    for prev in sorted((collect.ROOT / "data").glob("discover_*.json")):  # ข้ามชื่อที่เคยลองแล้ว
        try:
            have |= {r["token"].lower() for r in json.loads(prev.read_text(encoding="utf-8"))}
        except (OSError, ValueError, KeyError, TypeError):
            pass
    for token in [c for c in CANDIDATES if c.lower() not in have]:
        for source in ("greenhouse", "lever"):
            row = {"source": source, "token": token}
            try:
                data, n = collect.FETCHERS[source](token, cfg)
                items = data.get("jobs", []) if source == "greenhouse" else data
                norm = stage.normalize_greenhouse if source == "greenhouse" else stage.normalize_lever
                recs = [norm(x, token) for x in items]
                th = [r for r in recs if stage.is_thailand(r, f)]
                tech = [r for r in th if stage.is_tech(r, f)]
                row.update(status="ok", n_jobs=n, n_thailand=len(th), n_thailand_tech=len(tech),
                           sample_titles=[r["title"] for r in tech[:8]])
            except urllib.error.HTTPError as e:
                row.update(status=f"http_{e.code}")
            except Exception as e:
                row.update(status="error", error=str(e)[:120])
            out.append(row)
            if row["status"] == "ok":
                print(f"{source:<10} {token:<16} jobs={row['n_jobs']:<5} TH={row['n_thailand']:<4} TH-tech={row['n_thailand_tech']}")
            time.sleep(cfg["delay_seconds"])
    path = collect.ROOT / "data" / f"discover_{datetime.now():%Y-%m-%d}.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("บันทึก", path)


if __name__ == "__main__":
    run()
