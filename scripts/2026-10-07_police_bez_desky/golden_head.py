#!/usr/bin/env python3
"""Zlaty otisk stolu PRED zavedenim volby 'spodni police bez desky' (bot8, 2026-10-07): pro mrizku konfiguraci (viz _spolecne.mrizka) ulozi otisky vysledku generatoru (dily, klice, spoje,
problemy, kusovnik pro cenu, vyrobni vypis, koty, ovladani ve 3D bez nove polozky, hash) a u nekolika konfiguraci i otisk GLB do golden_head.json. test_police_bez_desky.py pak overi, ze s vychozi
hodnotou (police s deskou) je VSE beze zmeny.
Pouziti (nad API VE STAVU PRED zmenou; STUL_API_OVERRIDE = adresar api):  api/venv/bin/python3 scripts/2026-10-07_police_bez_desky/golden_head.py"""
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _spolecne as C  # noqa: E402

S, G, K = C.nacti_generator()

GLB_KONFIGURACE = [dict(system=30), dict(system=30, police=2), dict(system=35, sirka=2100, police=2), dict(system=40, hloubka=1000, police=1), dict(system=45, hloubka=1600, police=2),
                   dict(system=30, sirka=2800, police=1, stredni_opora="ram"), dict(system=40, vyrez1=True, vyrez1_police=True, police=1), dict(system=41, sirka=2000, police=1)]


def vypocti():
    out = {}
    for p in C.mrizka():
        out[C.klic_konfigurace(p)] = C.otisky(S, G, K, C.vysledek(S, p))
    glb = {}
    for p in GLB_KONFIGURACE:
        r = S.sestav_stul(**p)
        glb[C.klic_konfigurace(p)] = hashlib.sha256(G.model_pro_parametry(r["parametry"], razitka=False)[1]).hexdigest()[:20]
    klice = set()
    for p in C.mrizka():
        r = C.vysledek(S, p)
        if not isinstance(r, str):
            klice |= set(r["parametry"])
    return {"mrizka": out, "glb": glb, "klice_parametru": sorted(klice - {"police_deska"})}


if __name__ == "__main__":
    g = vypocti()
    cil = C.GOLDEN
    json.dump(g, open(cil, "w", encoding="utf-8"), indent=0, sort_keys=True)
    print("zapsano", len(g["mrizka"]), "konfiguraci a", len(g["glb"]), "GLB do", cil)
