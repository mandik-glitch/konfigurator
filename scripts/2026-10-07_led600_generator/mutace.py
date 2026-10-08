#!/usr/bin/env python3
"""Mutace DELKY LED SVITIDLA (bot8, 2026-10-07): kazda umyslna chyba v kandidatnim / nasazenem kodu MUSI shodit prislusny test (CHYCENA = dobre). Kazda mutace dostane kopii api/ (symlinky + jeden
upraveny soubor, STUL_API_OVERRIDE), test bezi v rychlem rezimu (TEST_STOP_PRVNI=1: prvni selhani konci). Po 4 paralelne (MUT_PARALELNE=N).
  g = test_led_delka.py (generator, GLB, lux data; bez DB), z = test_led_delka_zive.py (zive tazeni ramene), s = test_led_delka_shop.py (verejne API; DB jen cte, pres systemd-run).

  MUT_ZDROJ_API=<api s nasazenymi zaplatami (kandidat pred nasazenim: $SP/led/cand/api; po nasazeni: api/)> api/venv/bin/python3 scripts/2026-10-07_led600_generator/mutace.py [nazev_mutace ...]"""
import concurrent.futures
import glob
import os
import shutil
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ZDROJ = os.environ.get("MUT_ZDROJ_API") or os.path.join(REPO, "api")
D = "scripts/2026-10-07_led600_generator/"
TESTY = {"g": (D + "test_led_delka.py", False), "z": (D + "test_led_delka_zive.py", False), "s": (D + "test_led_delka_shop.py", True)}
K, GL, SH, OV, OS, SS = "stul_konfigurator.py", "stul_glb.py", "stul_shop.py", "stul_ovladani_verejne.py", "stul_osvetleni.py", "stul_sse.py"

# (nazev, test, soubor, puvodni text, nahrada)
MUTACE = [
    # generator
    ("g01_600_je_dil_1200", "g", K, '''LED_TYPY = {1200: LED_PART, 600: "product_5359"}''', '''LED_TYPY = {1200: LED_PART, 600: LED_PART}'''),
    ("g02_vychozi_600", "g", K, '''LED_DELKA_VYCHOZI = 1200\n''', '''LED_DELKA_VYCHOZI = 600\n'''),
    ("g03_telo_o_mm_vic", "g", K, '''v = _LED_TELO[part_id] = float(round(_led_telo_presne(part_id)))''', '''v = _LED_TELO[part_id] = float(round(_led_telo_presne(part_id))) + 1.0'''),
    ("g04_vystredeni_podle_1247", "g", K, '''zakl["pos"][2] += (0 - (n_l - 1) / 2.0) * s_led''', '''zakl["pos"][2] += (0 - (n_l - 1) / 2.0) * LED_SIRKA'''),
    ("g05_roztec_1247", "g", K, '''np.array([0, 0, k * s_led]))''', '''np.array([0, 0, k * LED_SIRKA]))'''),
    ("g06_pocet_podle_1247", "g", K, '''n_l = max(1, int((p["sirka"] + LED_PREVIS) // s_led))''', '''n_l = max(1, int((p["sirka"] + LED_PREVIS) // LED_SIRKA))'''),
    ("g07_prvni_svitidlo_dil_1200", "g", K, '''        zakl["part_id"] = LED_TYPY[d_led]''', '''        zakl["part_id"] = LED_PART'''),
    ("g08_klony_dil_1200", "g", K, '''            kl["part_id"] = LED_TYPY[d_led]''', '''            kl["part_id"] = LED_PART'''),
    ("g09_delka_se_nevraci_na_vychozi", "g", K, '''        p["led_delka"] = float(LED_DELKA_VYCHOZI)                    # bez svitidla''', '''        pass                    # bez svitidla'''),
    ("g10_vstup_bez_kontroly", "g", K, '''or int(round(ld_)) not in LED_TYPY:''', '''or False:'''),
    ("g11_kontrola_profilu_podle_1247", "g", K, '''delka_svetla = sum(led_telo_dilu(c["part_id"]) for c in clenove.values() if c["druh"] == "prisl" and c["src"] == LED)''', '''delka_svetla = led_idx_n * LED_SIRKA'''),
    ("g12_led_info_vejde_vzdy", "g", K, '''presah_t <= LED_PREVIS + 1.0''', '''presah_t <= LED_PREVIS + 500.0'''),
    ("g13_led_info_pocet_1247", "g", K, '''n_t = max(1, int((p["sirka"] + LED_PREVIS) // telo_l))''', '''n_t = max(1, int((p["sirka"] + LED_PREVIS) // LED_SIRKA))'''),
    ("g14_prepinac_jen_1200", "g", K, '''**{pid_: "led" for pid_ in LED_PARTY}, "product_4932": "elektrozlab",''', '''"product_4929": "led", "product_4932": "elektrozlab",'''),
    ("g15_menu_cast_jen_1200", "g", K, '''lambda k, rl, d: d["part_id"] in LED_PARTY or k in (("t", XRAIL_TOP_L)''', '''lambda k, rl, d: d["part_id"] == "product_4929" or k in (("t", XRAIL_TOP_L)'''),
    ("g16_menu_nabizi_i_aktualni", "g", K, '''p["led_svetlo"] and t_["delka"] != int(p["led_delka"]):''', '''p["led_svetlo"]:'''),
    ("g17_menu_bez_parametru", "g", K, '''["led", "led_delka", "led_rameno", "vzpery", "led_svetlo"]''', '''["led", "led_rameno", "vzpery", "led_svetlo"]'''),
    ("g18_bez_nazvu_dilu", "g", K, '''_NAZVY.update({pid_: f"LED osvětlení {d_} mm" for d_, pid_ in LED_TYPY.items() if pid_ != LED_PART})''', '''_NAZVY.update({})'''),
    ("g19_cisla_bez_led_delka", "s", K, '''"panely_delka", "led_delka") + VYREZY_CISLA''', '''"panely_delka") + VYREZY_CISLA'''),
    ("g20_min_sirka_telo", "g", K, '''"min_sirka": int(math.ceil(telo_l - LED_PREVIS))''', '''"min_sirka": int(math.ceil(telo_l))'''),
    ("g21_pevne_jen_1200", "z", K, '''or dily[i]["part_id"] in LED_PARTY]''', '''or dily[i]["part_id"] == "product_4929"]'''),
    ("g22_led_info_neni_v_odpovedi", "g", K, '''        "led_info": led_info,\n''', '''        "led_info": {"delka": 1200, "typy": []},\n'''),
    ("g23_menu_bez_duvodu", "g", K, '''None if t_["vejde"] else "Tahle délka LED se sem nevejde (širší stůl)."''', '''None'''),
    ("g24_vstup_neceloc_ok", "g", K, '''or abs(ld_ - round(ld_)) > 1e-6 or int(round(ld_)) not in LED_TYPY:''', '''or int(round(ld_)) not in LED_TYPY:'''),
    ("g25_telo_vychozi_z_glb", "g", K, '''    if part_id == LED_PART:\n        return LED_SIRKA\n''', '''    if part_id == LED_PART:\n        return LED_SIRKA + 0.5\n'''),
    # GLB / hash
    ("b01_hash_vzdy_s_delkou", "g", GL, '''or int(round(p["led_delka"])) == S.LED_DELKA_VYCHOZI:''', '''or False:'''),
    ("b02_hash_s_delkou_i_bez_svitidla", "g", GL, '''if not (p["led"] and p["stojky"] and p.get("led_svetlo", True)) or int(round(p["led_delka"]))''', '''if int(round(p["led_delka"]))'''),
    ("b03_material_jen_1200", "g", GL, '''MATERIAL_DILU.update({pid_: "led" for pid_ in S.LED_PARTY})''', '''MATERIAL_DILU.update({})'''),
    ("b04_hash_nikdy_s_delkou", "g", GL, '''        p.pop("led_delka", None)\n    for j in range(1, 11):''', '''        p.pop("led_delka", None)\n    p.pop("led_delka", None)\n    for j in range(1, 11):'''),
    # pocitadlo luxu
    ("l01_typ_vzdy_1200", "g", OS, '''typ, sviti = TYP_DILU[pid]''', '''typ, sviti = TYP_DILU[pid][0].replace("600", "1200"), TYP_DILU[pid][1]'''),
    ("l02_sviti_vzdy_1200", "g", OS, '''typ, sviti = TYP_DILU[pid]''', '''typ, sviti = TYP_DILU[pid][0], 1200.0'''),
    ("l03_teleso_vzdy_1247", "g", OS, '''"housingLengthMm": float(S.led_telo_dilu(pid))''', '''"housingLengthMm": float(S.LED_SIRKA)'''),
    ("l04_jen_svitidla_1200", "g", OS, '''leds = [d for d in dily if d["part_id"] in TYP_DILU]''', '''leds = [d for d in dily if d["part_id"] == S.LED_TYPY[1200]]'''),
    ("l05_transformuj_1200", "g", OS, '''P, _, _ = transformuj(d["part_id"], d)''', '''P, _, _ = transformuj(S.LED_TYPY[1200], d)'''),
    # SSE
    ("e01_sse_nezna_led_delka", "g", SS, '''"panely_z", "panely_delka", "led_delka", "elzlab_y"''', '''"panely_z", "panely_delka", "elzlab_y"'''),
    # verejne API
    ("s01_nenabizene_delky_ok", "s", SH, '''return float(d) if (d in S.LED_TYPY and (povolene is None or d in povolene)) else float(S.LED_DELKA_VYCHOZI)''', '''return float(d) if (d in S.LED_TYPY) else float(S.LED_DELKA_VYCHOZI)'''),
    ("s02_karta_bez_active", "s", SH, '''if r["active"] and not r["is_archived"] and r["glb_file"] and r["visible_in_scene"]:''', '''if not r["is_archived"] and r["glb_file"] and r["visible_in_scene"]:'''),
    ("s03_karta_bez_archivace", "s", SH, '''if r["active"] and not r["is_archived"] and r["glb_file"] and r["visible_in_scene"]:''', '''if r["active"] and r["glb_file"] and r["visible_in_scene"]:'''),
    ("s04_karta_bez_glb", "s", SH, '''if r["active"] and not r["is_archived"] and r["glb_file"] and r["visible_in_scene"]:''', '''if r["active"] and not r["is_archived"] and r["visible_in_scene"]:'''),
    ("s05_karta_mimo_scenu", "s", SH, '''if r["active"] and not r["is_archived"] and r["glb_file"] and r["visible_in_scene"]:''', '''if r["active"] and not r["is_archived"] and r["glb_file"]:'''),
    ("s06_zavislost_jen_led", "s", SH, '''"ledlen": ["posts", "led", "ledlight"], ''', '''"ledlen": ["led"], '''),
    ("s07_slot_pred_ledlight", "s", SH, '''toggle("led", "g_extras"), toggle("ledlight", "g_extras"), select("ledlen", "g_extras", LEDLEN_IDS, t["help_ledlen"]),''', '''toggle("led", "g_extras"), select("ledlen", "g_extras", LEDLEN_IDS, t["help_ledlen"]), toggle("ledlight", "g_extras"),'''),
    ("s08_normalizuj_bez_ledlen", "s", SH, '''    norm["ledlen"] = str(int(round(p["led_delka"])))\n    ''', '''    norm["ledlen"] = "1200"\n    '''),
    ("s09_token_bez_K", "s", SH, '''        out["K"] = int(round(float(p["led_delka"])))''', '''        out["Kx"] = int(round(float(p["led_delka"])))'''),
    ("s10_token_rozbal_bez_K", "s", SH, '''    if o.get("K"):\n        p["led_delka"] = float(o["K"])\n''', '''    if o.get("K"):\n        pass\n'''),
    ("s11_cache_bez_ledlen", "s", SH, ''', norm.get("ledlen"), tuple(sorted(led_delky_pro_pozadavek())))''', ''')'''),
    ("s12_souhrn_vzdy_ledlen", "s", SH, '''or sel.get("ledlen", str(S.LED_DELKA_VYCHOZI)) == str(S.LED_DELKA_VYCHOZI):''', ''':'''),
    ("s13_odkaz_s_vychozi_delkou", "s", SH, ''' and not (k == "led_delka" and int(round(float(v))) == S.LED_DELKA_VYCHOZI)''', ''''''),
    ("s14_kratsi_led_nikdy", "s", SH, '''            kr_led = _led_kratsi(p, led_delky_pro_pozadavek())''', '''            kr_led = None'''),
    ("s15_stitek_roztahnout", "s", SH, '''ta["led_kratsi"].format(v=suggest["ledlen"])''', '''ta["roztahnout_w"].format(v=suggest["ledlen"])'''),
    ("s16_duvod_telo", "s", SH, '''LEDLEN_NEVEJDE[lang].format(l=t_["delka"], w=t_["min_sirka"])''', '''LEDLEN_NEVEJDE[lang].format(l=t_["delka"], w=t_["telo"])'''),
    ("s17_dil_na_slot_jen_1200", "s", SH, '''**{pid_: "led" for pid_ in S.LED_PARTY}, **{pid_: "drawers"''', '''"product_4929": "led", **{pid_: "drawers"'''),
    ("s18_popisek_600", "s", SH, '''"ledlen_600": "600 mm", "ledlen_1200": "1200 mm",
                    "help_ledlen": "LED svítidla''', '''"ledlen_600": "600", "ledlen_1200": "1200 mm",
                    "help_ledlen": "LED svítidla'''),
    ("s19_options_vzdy_hidden", "s", SH, '''    elif len(led_delky) < 2:\n        options["ledlen"] = {"hidden": True}''', '''    elif True:\n        options["ledlen"] = {"hidden": True}'''),
    ("s20_gating_schema", "s", SH, '''    if len(led_delky_) < 2:                                      # nabizi se jen 1200''', '''    if False:                                      # nabizi se jen 1200'''),
    ("s21_normalizuj_ledlen_bez_led", "s", SH, '''if p["led"] else float(S.LED_DELKA_VYCHOZI)          # delka svitidla LED (vsechna stejna); bez LED vychozi''', '''if True else float(S.LED_DELKA_VYCHOZI)          # delka svitidla LED (vsechna stejna); bez LED vychozi'''),
    ("s22_efektivni_delka_vzdy_600", "s", SH, '''norm["ledlen"] = str(int(round(p["led_delka"]))) if (p["led"] and p["stojky"] and p["led_svetlo"]) else str(S.LED_DELKA_VYCHOZI)''', '''norm["ledlen"] = "600"'''),
    # verejne 3D ovladani
    ("o01_param_na_slot", "s", OV, '''"panely_delka": "panellen", "led_delka": "ledlen", ''', '''"panely_delka": "panellen", '''),
    ("o02_text_misto_cisla", "s", OV, '''        if k == "led_delka":\n            out[slot] = str(int(round(float(v))))''', '''        if k == "led_delka":\n            out[slot] = float(v)'''),
    ("o03_bez_prekladu", "s", OV, '''    *[(f"Zvolit LED {_d} mm", f"Use the {_d} mm LED light", f"Zvoliť LED {_d} mm") for _d in S.LED_DELKY],\n''', ''''''),
]


def spust(m):
    nazev, kt, soubor, puvodni, nahrada = m
    test, db = TESTY[kt]
    d = tempfile.mkdtemp(prefix="mut_led_")
    try:
        os.makedirs(os.path.join(d, "api"))
        for f in glob.glob(os.path.join(ZDROJ, "*")):
            os.symlink(f, os.path.join(d, "api", os.path.basename(f)))
        os.symlink(os.path.join(REPO, "webapp"), os.path.join(d, "webapp"))
        cil = os.path.join(d, "api", soubor)
        os.remove(cil)
        s = open(os.path.join(ZDROJ, soubor), encoding="utf-8").read()
        if s.count(puvodni) != 1:
            return nazev, None, f"puvodni text se v {soubor} nenasel prave jednou ({s.count(puvodni)}x)"
        open(cil, "w", encoding="utf-8").write(s.replace(puvodni, nahrada))
        env = dict(os.environ, TEST_STOP_PRVNI="1", STUL_API_OVERRIDE=os.path.join(d, "api"))
        if db:
            cmd = ["systemd-run", "--pipe", "--wait", "--quiet", f"--property=EnvironmentFile={REPO}/api/.env", "--setenv=HOME=/root", "--setenv=TEST_STOP_PRVNI=1", f"--setenv=STUL_API_OVERRIDE={d}/api",
                   f"--working-directory={REPO}", f"{REPO}/api/venv/bin/python3", test]
        else:
            cmd = [f"{REPO}/api/venv/bin/python3", test]
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=1500, env=env, cwd=REPO)
        posledni = [x for x in p.stdout.splitlines() if "CHYBA" in x][:1]
        return nazev, p.returncode, (posledni[0].strip()[:150] if posledni else (p.stderr.strip().splitlines() or [""])[-1][:150])
    finally:
        shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    vyber = set(sys.argv[1:])
    seznam = [m for m in MUTACE if not vyber or m[0] in vyber]
    necytene = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=int(os.environ.get("MUT_PARALELNE", "4"))) as ex:
        for nazev, rc, info in ex.map(spust, seznam):
            if rc is None:
                print(f"mutace {nazev}: CHYBA MUTACE - {info}")
                necytene.append(nazev)
                continue
            chycena = rc != 0
            print(f"mutace {nazev}: rc={rc} ({'CHYCENA' if chycena else 'NECHYCENA'})  {info}")
            if not chycena:
                necytene.append(nazev)
    print(f"\n==> {len(seznam) - len(necytene)}/{len(seznam)} mutaci chyceno" + (f"; NECHYCENE / VADNE: {', '.join(necytene)}" if necytene else " - VSECHNY CHYCENY"))
    sys.exit(1 if necytene else 0)
