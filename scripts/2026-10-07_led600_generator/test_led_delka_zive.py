#!/usr/bin/env python3
"""Test ZIVEHO TAZENI RAMENE LED se svitidly 600 (bot8, 2026-10-07; Robert: "LED 600 doplnit do generatoru"): stejna kontrola jako v scripts/2026-10-02_stul_testy/test_stul_zive.py (operace `zive` tahu
`led_rameno` aplikovane na GLB puvodniho stavu = GLB, ktery server poskladal pro novy parametr, <= 0,05 mm), ale pro konfigurace s `led_delka=600` (1 az 4 svitidla; svitidla jedou s pricnou
na predni konec ramen: seznam `pevne` v ovladani_3d musi znat dil product_5359). Funkce a pravidla bere z test_stul_zive.py (import modulu).
Spusteni: api/venv/bin/python3 scripts/2026-10-07_led600_generator/test_led_delka_zive.py        (STUL_API_OVERRIDE=<adresar api> = kandidat)"""
import importlib.util
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
spec = importlib.util.spec_from_file_location("test_stul_zive", os.path.join(REPO, "scripts", "2026-10-02_stul_testy", "test_stul_zive.py"))
Z = importlib.util.module_from_spec(spec)
spec.loader.exec_module(Z)

OK, FAILS = 0, []


def check(cond, msg):
    global OK
    if cond:
        OK += 1
    else:
        FAILS.append(msg)
        print(f"  CHYBA: {msg}")
        if os.environ.get("TEST_STOP_PRVNI"):
            sys.exit(1)


KONFIGURACE = (("led_rameno", dict(sirka=1600, led_delka=600), (+80.0, -100.0)),
               ("led_rameno", dict(sirka=2000, led_delka=600), (+60.0, -40.0)),
               ("led_rameno", dict(sirka=3000, led_delka=600), (+100.0,)),
               ("led_rameno", dict(sirka=700, led_delka=600), (+60.0, -40.0)),
               ("led_rameno", dict(sirka=1600, led_delka=600, vzpery=True), (-60.0, +60.0)),
               ("led_rameno", dict(sirka=1600, led_delka=1200), (+80.0,)))              # 1200: kontrolni (beze zmeny proti dosavadnimu chovani)
for tid, par, zmeny in KONFIGURACE:
    for zm in zmeny:
        j = f"{tid} {par} {zm:+.0f} mm"
        res = Z.porovnej(par, tid, zm, 0.05, j)
        if not res:
            check(False, f"{j}: porovnani se nepovedlo (chybi tah / zmenil se pocet dilu)")
            continue
        chyby, r0_ = res[0], res[5]
        lamp = [i for i, d in enumerate(r0_["dily"]) if d["part_id"] in ("product_4929", "product_5359")]
        lim = lambda i: 0.3 if r0_["dily"][i]["part_id"] == "product_4933" else 0.05          # noqa: E731 - desky stejne jako v puvodnim testu
        nej = max(chyby, key=lambda ci: ci[0] / lim(ci[1])) if chyby else (0, -1)
        check(chyby and all(c <= lim(i) for c, i in chyby), f"{j}: zive tazeni = model ze serveru (nejvetsi odchylka {nej[0]:.3f} mm u dilu {nej[1]})")
        chyby_led = [c for c, i in chyby if i in lamp]
        check(len(lamp) >= 1 and chyby_led and max(chyby_led) <= 0.05, f"{j}: svitidla ({len(lamp)} ks) jedou s ramenem a sedi s modelem ({max(chyby_led) if chyby_led else None})")
check(not Z.FAILS, f"pomocna kontrola z test_stul_zive.py nehlasi chybu ({Z.FAILS[:2]})")
print(f"\n==> {OK}/{OK + len(FAILS)} kontrol OK" + (f", SELHALO {len(FAILS)}: " + "; ".join(FAILS[:5]) if FAILS else ""))
sys.exit(1 if FAILS else 0)
