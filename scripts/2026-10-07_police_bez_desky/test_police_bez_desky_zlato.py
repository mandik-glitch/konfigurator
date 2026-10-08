#!/usr/bin/env python3
"""ZLATY OTISK (bot8, 2026-10-07): s vychozi hodnotou `police_deska` (police s deskou) je VSE beze zmeny proti stavu PRED zavedenim volby 'spodni police bez desky' - uplna mrizka
konfiguraci (viz _spolecne.mrizka; dily, klice, spoje, problemy, kusovnik pro cenu, vyrobni vypis, koty, 3D ovladani bez nove polozky, hash) + GLB osmi konfiguraci, a pri vyslovnem
`police_deska=True` totez. Zlaty otisk vyrobil golden_head.py nad zakladnim stavem (pred zavedenim volby).
Spusteni: api/venv/bin/python3 scripts/2026-10-07_police_bez_desky/test_police_bez_desky_zlato.py     (env STUL_API_OVERRIDE = jiny adresar api; trva par minut)"""
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _spolecne as C  # noqa: E402

S, G, K = C.nacti_generator()
zlato = json.load(open(C.GOLDEN, encoding="utf-8"))
OK, FAILS = 0, []


def check(cond, msg, detail=""):
    global OK
    if cond:
        OK += 1
    else:
        FAILS.append(msg)
        print(f"  CHYBA: {msg} {detail}")


konf = list(C.mrizka())
check(set(C.klic_konfigurace(p) for p in konf) == set(zlato["mrizka"]), f"Z0: stejna mrizka konfiguraci jako zlaty otisk ({len(konf)})")
rozdily, rozdily_true = [], []
for p in konf:
    kl = C.klic_konfigurace(p)
    ted = C.otisky(S, G, K, C.vysledek(S, p), zlato.get("klice_parametru"))
    z = zlato["mrizka"][kl]
    if not C.shoduje(ted, z):
        rozdily.append((kl, sorted(k for k in set(ted) | set(z) if ted.get(k) != z.get(k))))
    r_true = C.vysledek(S, {**p, "police_deska": True})
    if not isinstance(r_true, str):
        o2 = C.otisky(S, G, K, r_true, zlato.get("klice_parametru"))
        if not C.shoduje(o2, z):
            rozdily_true.append((kl, sorted(k for k in set(o2) | set(z) if o2.get(k) != z.get(k))))
check(not rozdily, f"Z1: vychozi chovani: {len(rozdily)} z {len(konf)} konfiguraci se lisi od stavu pred zavedenim volby", str(rozdily[:3]))
check(not rozdily_true, f"Z2: police_deska=True: {len(rozdily_true)} z {len(konf)} konfiguraci se lisi", str(rozdily_true[:3]))
for kl, h in zlato["glb"].items():
    p = json.loads(kl)
    r = C.vysledek(S, p)
    check(hashlib.sha256(G.model_pro_parametry(r["parametry"], razitka=False)[1]).hexdigest()[:20] == h, f"Z3: GLB vychoziho stolu {kl} beze zmeny")
print(f"   ({len(konf)} konfiguraci, {len(zlato['glb'])} GLB)")
print(f"\n==> {OK}/{OK + len(FAILS)} kontrol OK" + (f", SELHALO {len(FAILS)}: " + "; ".join(FAILS[:5]) if FAILS else ""))
sys.exit(1 if FAILS else 0)
