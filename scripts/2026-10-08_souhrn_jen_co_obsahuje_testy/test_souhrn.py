#!/opt/konfigurator/api/venv/bin/python
"""Vypisy a popisy stolu z generatoru: jen to, co stul OBSAHUJE (Robert 2026-10-08: "nechceme zobrazovat to co stul nema, jen to co obsahuje") - bot5.
Souhrn voleb (`stul_shop._souhrn_voleb`, jde do kosiku, objednavky, online nabidky i embed objednavky) nesmi obsahovat zadny vypnuty prepinac ("ne"); dopravnik bez spodniho ramu radek ramu neuvadi.
Nic se nezapisuje ani neposila (cista funkce nad generatorem, DB jen cte ceny). Spusteni: systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator api/venv/bin/python3 scripts/2026-10-08_souhrn_jen_co_obsahuje_testy/test_souhrn.py"""
import os
import sys
import threading

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "api")))
sys.dont_write_bytecode = True
_o = threading.Thread.start
threading.Thread.start = lambda self, *a, **k: None if self.name == "render-dozorce" else _o(self, *a, **k)
import app  # noqa: E402,F401
import jazyky  # noqa: E402
import stul_shop as SH  # noqa: E402
vysl = []


def over(n, p, d=None):
    vysl.append(bool(p))
    print(("OK   " if p else "FAIL ") + n + ("" if p else "  -> " + repr(d)[:400]))


VYBERY = [
    {},
    {"w": 1500, "cut1": True, "shelf": 1},
    {"w": 1800, "led": True, "posts": True, "wheels": True, "drawers": True, "panels": True},
    {"w": 1200, "wheels": False, "feet": False, "drawers": False, "panels": False, "led": False, "socket": False, "pet": False, "braces": False, "upshelf": False, "bearings": False,
     "cut1": False, "cut2": False, "cut3": False, "posts": False, "shelf": 0},
    {"w": 2000, "led": True, "posts": True, "ledlight": False, "braces": True, "upshelf": True, "cut2": True, "cut2shelf": True, "bearings": True, "shelf": 2, "shelfboard": False},
    {"w": 1600, "drawers": True, "drawleft": False, "pet": True},
    {"w": 1600, "drawers": True, "drawleft": True},
]
SYSTEMY = (30, 35, 40, 41, 45)
NEGATIVNI = {}
for lang in ("cs", "en", "sk"):
    ano_ne = jazyky.ano_ne(lang) or (("ano", "ne") if lang == "cs" else ("yes", "no"))
    NEGATIVNI[lang] = ano_ne[1]

pocet, vadne, souhrny = 0, [], {}
for sy in SYSTEMY:
    for i, sel in enumerate(VYBERY):
        for lang in ("cs", "en", "sk"):
            r = SH.resolve(sel, lang, system=sy)
            sou = SH._souhrn_voleb(r["selection"], lang, sy)
            souhrny[(sy, i, lang)] = (r["selection"], sou)
            schema_ = {s["id"]: s for s in SH.schema(lang, sy)["slots"]}
            pocet += 1
            for x in sou:
                if schema_[x["id"]]["type"] == "toggle" and (not r["selection"][x["id"]] or x["value"] == NEGATIVNI[lang]):
                    vadne.append((sy, i, lang, x))
over("S1 zadny souhrn (%d kombinaci system x vyber x jazyk) neobsahuje vypnuty prepinac ani hodnotu '%s' u prepinace" % (pocet, "ne"), not vadne, vadne[:3])

sel, sou = souhrny[(30, 3, "cs")]
ids = {x["id"] for x in sou}
over("S2 stul bez prislusenstvi (vse vypnute): v souhrnu zadne kolecka, patky, suplíky, panely, LED, zlab, PET, vzpery, police, vyrezy, lozisky", not ids & {"wheels", "feet", "drawers", "panels", "led", "socket", "pet", "braces", "upshelf", "cut1", "cut2", "cut3", "bearings", "posts"}, sorted(ids))
over("S2b rozmery zustavaji (sirka, hloubka, vyska desky)", {"w", "d", "h"} <= ids, sorted(ids))
sel, sou = souhrny[(30, 2, "cs")]
ids = {x["id"]: x["value"] for x in sou}
over("S3 zapnute prislusenstvi se uvadi s 'ano': kolecka, suplíky, panely, LED, stojky", all(ids.get(k) == "ano" for k in ("wheels", "drawers", "panels", "led", "posts")), ids)
over("S3b vypnute z nich v souhrnu nejsou (patky, vzpery, police mezi stojkami, vyrezy, lozisky)", not set(ids) & {"feet", "braces", "upshelf", "cut1", "cut2", "cut3", "bearings"}, sorted(ids))
sel, sou = souhrny[(30, 4, "cs")]
ids = {x["id"] for x in sou}
over("S4 police bez desky: radek 'Desky na spodnich policich: ne' uz neni (vypnuty prepinac), police zustavaji", "shelfboard" not in ids and "shelf" in ids and "ledlight" not in ids, sorted(ids))
sel, sou = souhrny[(30, 5, "cs")]
over("S5 suplíky vpravo (drawleft vypnute) se neuvadi, vlevo se uvadi 'ano'", "drawleft" not in {x["id"] for x in sou} and {x["id"]: x["value"] for x in souhrny[(30, 6, "cs")][1]}.get("drawleft") == "ano")
sel, sou = souhrny[(41, 0, "cs")]
over("S6 system 41: souhrn obsahuje jen zapnute volby (zadne 'ne')", all(x["value"] != "ne" for x in sou) and any(x["id"] == "w" for x in sou), sou)
over("S7 stul s vychozim vyberem ma porad dost radku (neprazdny souhrn)", all(len(souhrny[(sy, 0, "cs")][1]) >= 4 for sy in SYSTEMY), [len(souhrny[(sy, 0, "cs")][1]) for sy in SYSTEMY])

# ---- dopravnik: bez spodniho ramu radek ramu neni
import dopravnik_shop as DS  # noqa: E402
p = {"rtype": "alu", "width": 590, "len": 2000, "pitch": 150, "h": 800, "legs": 4, "frame": "full"}
over("D1 dopravnik se spodnim ramem: 7 radku vcetne ramu", [x["id"] for x in DS._souhrn(p, "cs")][-1] == "frame" and len(DS._souhrn(p, "cs")) == 7)
over("D2 dopravnik bez spodniho ramu: 6 radku, 'frame' neni", [x["id"] for x in DS._souhrn(dict(p, frame="none"), "cs")] == ["rtype", "width", "len", "pitch", "h", "legs"])
print("\n%d/%d kontrol OK" % (sum(vysl), len(vysl)))
sys.exit(0 if all(vysl) else 1)
