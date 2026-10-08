#!/usr/bin/env python3
"""Obrazky konfiguraci generatoru oploceni (GLB -> three.js -> PNG) do $SP/oploceni/img (bot8, 2026-10-08): (a) jako na fotce, (b) prosté oploceni, (c) kout L, (d) kryt se strechou a dvermi na dvou stranach.
Pouziti: api/venv/bin/python3 scripts/2026-10-08_oploceni/render_oploceni.py [vystupni_adresar]   (potrebuje node + playwright + internet pro three.js z jsdelivr; moduly bere z api/ nebo z $OPLOCENI_API)"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
API = os.environ.get("OPLOCENI_API") or os.path.join(REPO, "api")      # jadro, 3D model a cena jsou od faze 2 v api/ (ne v teto slozce)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "2026-10-07_police_bez_desky"))
import _spolecne as C  # noqa: E402

C.nacti_generator(hermeticky=True)                                  # fake env pro import stul_glb (bez DB)
sys.path.insert(0, API)
import oploceni_glb as OG  # noqa: E402
import oploceni_konfigurator as O  # noqa: E402

VYST = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.environ.get("SP", "/tmp"), "oploceni", "img")
os.makedirs(VYST, exist_ok=True)
KONFIGURACE = [
    ("a_jako_na_fotce", dict(sirka=1500, hloubka=1500, vyska=2200, celo="dvere", dvere_sirka=800, dvere_poloha="vpravo", dvere_zavesy="vpravo", strecha="vyplne", vyplne="pc_cira", vyplne_leva="pc_koura"), 62, [(35, 16, "3-4"), (0, 6, "celo")]),
    ("b_oploceni_4_pole", dict(sirka=4800, hloubka=700, vyska=1800, celo="stena", prava="otevreno", zadni="otevreno", leva="otevreno", strecha="zadna", vyplne="sit"), 0, [(28, 14, "3-4")]),
    ("c_kout_L", dict(sirka=2400, hloubka=2000, vyska=2000, celo="stena", prava="otevreno", zadni="otevreno", leva="stena", strecha="zadna", vyplne="pc_cira"), 0, [(40, 16, "3-4")]),
    ("d_kryt_dvoje_dvere", dict(sirka=2600, hloubka=1800, vyska=2300, celo="dvere", prava="dvere", zadni="stena", leva="stena", strecha="vyplne", vyplne="pc_cira", dvere_sirka=900, dvere_poloha="stred", zamek="zamek", patky=True), 40, [(38, 18, "3-4"), (-38, 18, "3-4_zezadu")]),
]
jobs = []
for nazev, par, otevrit, pohledy in KONFIGURACE:
    r = O.sestav_oploceni(**par)
    glb = OG.sestav_glb(r, otevrit_dvere=otevrit)
    cesta = os.path.join(VYST, nazev + ".glb")
    open(cesta, "wb").write(glb)
    print(nazev, "hash", r["hash"], "dilu", len(r["dily"]), "vyplni", len(r["vyplne"]), "glb %.1f kB" % (len(glb) / 1024.0))
    for az, el, jm in pohledy:
        jobs.append({"glb": cesta, "out": os.path.join(VYST, "%s_%s.png" % (nazev, jm)), "az": az, "el": el, "w": 1200, "h": 900})
jp = os.path.join(VYST, "jobs.json")
json.dump(jobs, open(jp, "w"))
subprocess.run(["node", os.path.join(HERE, "render_glb.js"), jp], check=False)
