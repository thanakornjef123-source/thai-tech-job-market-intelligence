"""จัดกลุ่มตำแหน่ง (role_family) ด้วยกฎใน config/role_families.json"""
import json
import re
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


@lru_cache
def _rules():
    cfg = json.loads((ROOT / "config" / "role_families.json").read_text(encoding="utf-8"))
    return [(fam, re.compile("|".join(f"(?:{p})" for p in pats), re.I)) for fam, pats in cfg["order"]], cfg["default"]


def role_family(title: str) -> str:
    rules, default = _rules()
    for fam, rx in rules:
        if rx.search(title):
            return fam
    return default
