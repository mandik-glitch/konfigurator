#!/usr/bin/env python3
"""Mutace RUCNICH SVITIDEL LED (bot8, 2026-10-08): kazda umyslna chyba v kandidatnim / nasazenem kodu MUSI shodit prislusny test (CHYCENA = dobre). Kazda mutace dostane kopii api/ (symlinky + jeden
upraveny soubor, STUL_API_OVERRIDE), test bezi v rychlem rezimu (TEST_STOP_PRVNI=1: prvni selhani konci). Po 4 paralelne (MUT_PARALELNE=N).
  g = test_led_rucne.py (generator, GLB, lux data, hash, 3D ovladani, zive tazeni; bez DB), s = test_led_rucne_shop.py (verejne API; DB jen cte, pres systemd-run).

  MUT_ZDROJ_API=<api s nasazenymi zaplatami (kandidat pred nasazenim: $SP/led_rucne/cand/api; po nasazeni: api/)> api/venv/bin/python3 scripts/2026-10-08_led_rucne/mutace.py [nazev_mutace ...]
  mutace.py --over   = jen overi, ze se kazdy puvodni text nachazi v souboru PRAVE jednou (bez spousteni testu)"""
import concurrent.futures
import glob
import os
import shutil
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ZDROJ = os.environ.get("MUT_ZDROJ_API") or os.path.join(REPO, "api")
D = "scripts/2026-10-08_led_rucne/"
TESTY = {"g": (D + "test_led_rucne.py", False), "s": (D + "test_led_rucne_shop.py", True)}
K, GL, SH, OV, SS = "stul_konfigurator.py", "stul_glb.py", "stul_shop.py", "stul_ovladani_verejne.py", "stul_sse.py"

# (nazev, test, soubor, puvodni text, nahrada)
MUTACE = [
    # ---- generator: konstanty, vstup
    ("k01_led_max_3", "g", K, '''LED_MAX = 4 ''', '''LED_MAX = 3 '''),
    ("k02_vychozi_pocet_2", "g", K, '''    "led_pocet": 1,               # Robert 2026-10-08''', '''    "led_pocet": 2,               # Robert 2026-10-08'''),
    ("k03_max_pocet_bez_previsu", "g", K, '''return max(1, min(LED_MAX, int((sirka + LED_PREVIS) // telo)))''', '''return max(1, min(LED_MAX, int((sirka) // telo)))'''),
    ("k04_max_pocet_bez_stropu", "g", K, '''return max(1, min(LED_MAX, int((sirka + LED_PREVIS) // telo)))''', '''return max(1, int((sirka + LED_PREVIS) // telo))'''),
    ("k05_vstup_bez_rozsahu", "g", K, '''    if not 1 <= int(lp_) <= LED_MAX:''', '''    if False:'''),
    ("k06_vstup_pocet_bool_ok", "g", K, '''    if isinstance(lp_, bool) or not isinstance(lp_, (int, float)) or not math.isfinite(lp_) or lp_ != int(lp_):''', '''    if not isinstance(lp_, (int, float)) or not math.isfinite(lp_) or lp_ != int(lp_):'''),
    ("k07_vstup_poloha_bool_ok", "g", K, '''        if isinstance(v_, bool) or not isinstance(v_, (int, float)) or not math.isfinite(v_):''', '''        if not isinstance(v_, (int, float)) or not math.isfinite(v_):'''),
    ("k08_poloha_bez_zaokrouhleni", "g", K, '''        out[k_] = round(float(v_), 1)''', '''        out[k_] = float(v_)'''),
    ("k09_dotaz_bez_led_pocet", "g", K, '''"led_delka", "led_pocet", ''', '''"led_delka", '''),
    ("k10_dotaz_polohy_bez_desetinnych", "g", K, ''' + LED_PARAMETRY_Z''', ''''''),
    ("k11_dotaz_polohy_bez_none", "g", K, '''or k == "hpolice_vyska" or k.startswith("led_z")) and str(v)''', '''or k == "hpolice_vyska") and str(v)'''),
    # ---- generator: rozlozeni svitidel
    ("l01_auto_bez_vystredeni", "g", K, '''    auto = [c0 + (k - (n - 1) / 2.0) * s_ for k in range(n)]''', '''    auto = [c0 + (k - 0.0) * s_ for k in range(n)]'''),
    ("l02_90_procent_je_100", "g", K, '''    q = MIN_PODIL_PROFILU_LED * s_
    cmin, cmax = p0 + q - s_ / 2.0, p1 - q + s_ / 2.0
    auto = [''', '''    q = s_
    cmin, cmax = p0 + q - s_ / 2.0, p1 - q + s_ / 2.0
    auto = ['''),
    ("l03_meze_90_procent_je_100", "g", K, '''    q = MIN_PODIL_PROFILU_LED * s_
    cmin, cmax = p0 + q - s_ / 2.0, p1 - q + s_ / 2.0
    n = len(v)''', '''    q = s_
    cmin, cmax = p0 + q - s_ / 2.0, p1 - q + s_ / 2.0
    n = len(v)'''),
    ("l04_prekryti_povoleno", "g", K, '''        lo = cmin if k == 0 else v[k - 1] + s_
        hi = cmax - (n - 1 - k) * s_''', '''        lo = cmin
        hi = cmax - (n - 1 - k) * s_'''),
    ("l05_misto_pro_dalsi_ignorovano", "g", K, '''        hi = cmax - (n - 1 - k) * s_
        if k:''', '''        hi = cmax
        if k:'''),
    ("l06_rozpeti_ignorovano", "g", K, '''            hi = min(hi, v[k - 1] + s_ + zbyva)''', '''            hi = hi'''),
    ("l07_zbyva_neubyva", "g", K, '''        if k:
            zbyva -= x - v[k - 1] - s_''', '''        if k:
            zbyva -= 0.0'''),
    ("l08_zbyva_o_mezeru_min", "g", K, '''    v, zbyva = [], max(0.0, rozpeti_max - n * s_)''', '''    v, zbyva = [], max(0.0, rozpeti_max - (n - 1) * s_)'''),
    ("l09_bez_horniho_orezu", "g", K, '''        x = min(max(chce, lo), hi) if lo <= hi else lo''', '''        x = max(chce, lo)'''),
    ("l10_bez_dolniho_orezu", "g", K, '''        x = min(max(chce, lo), hi) if lo <= hi else lo''', '''        x = min(chce, hi)'''),
    ("l11_pocet_neorezan", "g", K, '''        n_l = min(int(p["led_pocet"]), n_max_led)''', '''        n_l = int(p["led_pocet"])'''),
    ("l12_polohy_ignorovany", "g", K, '''        zad_led = [(zc_led + float(p[f"led_z{_k + 1}"])) if (proveditelne and p[f"led_z{_k + 1}"] is not None) else None for _k in range(n_l)]''', '''        zad_led = [None for _k in range(n_l)]'''),
    ("l13_osa_je_c0", "g", K, '''        zc_led = (z_lo_led + z_hi_led) / 2.0 ''', '''        zc_led = c0_led '''),
    ("l14_rozpeti_bez_previsu", "g", K, '''        rozpeti_led = (z_hi_led - z_lo_led) + LED_PREVIS''', '''        rozpeti_led = (z_hi_led - z_lo_led)'''),
    ("l15_auto_prah_nula", "g", K, '''            if abs(v_led[k_led] - auto_led[k_led]) < 0.05:''', '''            if abs(v_led[k_led] - auto_led[k_led]) < 0.0:'''),
    ("l16_auto_prah_velky", "g", K, '''            if abs(v_led[k_led] - auto_led[k_led]) < 0.05:''', '''            if abs(v_led[k_led] - auto_led[k_led]) < 5.0:'''),
    ("l17_poloha_bez_zaokrouhleni", "g", K, '''                rel_led.append(round(v_led[k_led] - zc_led, 1))''', '''                rel_led.append(v_led[k_led] - zc_led)'''),
    ("l18_prvni_svitidlo_nepohnuto", "g", K, '''        zakl["pos"][2] = z_base_led + (v_led[0] - c0_led)''', '''        zakl["pos"][2] = z_base_led'''),
    ("l19_dalsi_svitidla_v_roztec", "g", K, '''z_base_led + (v_led[k] - c0_led)]))''', '''z_base_led + k * s_led]))'''),
    ("l20_pocet_neni_efektivni", "g", K, '''        p["led_pocet"] = n_l                                         # efektivni hodnoty''', '''        pass                                         # efektivni hodnoty'''),
    ("l21_polohy_nad_poctem_nuly", "g", K, '''            p[f"led_z{k_led + 1}"] = rel_led[k_led] if k_led < n_l else None''', '''            p[f"led_z{k_led + 1}"] = rel_led[k_led] if k_led < n_l else 0.0'''),
    ("l22_polohy_nejsou_efektivni", "g", K, '''            p[f"led_z{k_led + 1}"] = rel_led[k_led] if k_led < n_l else None''', '''            pass'''),
    ("l23_bez_svitidla_pocet_zustane", "g", K, '''        p["led_pocet"] = 1
        for k_led in LED_PARAMETRY_Z:''', '''        for k_led in LED_PARAMETRY_Z:'''),
    ("l24_bez_svitidla_polohy_zustanou", "g", K, '''        for k_led in LED_PARAMETRY_Z:
            p[k_led] = None''', '''        for k_led in LED_PARAMETRY_Z:
            pass'''),
    ("l25_proveditelne_vzdy", "g", K, '''        proveditelne = bool(n_l * s_led <= rozpeti_led + 1e-9 and (z_hi_led - z_lo_led) >= MIN_PODIL_PROFILU_LED * s_led)''', '''        proveditelne = True'''),
    ("l26_klon_bez_dilu_zvolene_delky", "g", K, '''            kl["part_id"] = LED_TYPY[d_led]
            clenove[("led", k)] = kl''', '''            clenove[("led", k)] = kl'''),
    # ---- generator: led_info a nabidky
    ("i01_info_pocet_1", "g", K, '''led_info.update({"pocet": n_led, "max"''', '''led_info.update({"pocet": 1, "max"'''),
    ("i02_info_max_1", "g", K, '''"max": led_stav["n_max"], "telo": s_l''', '''"max": 1, "telo": s_l'''),
    ("i03_info_polohy_absolutne", "g", K, '''"polohy": [round(v_ - zc_l, 1) for v_ in led_stav["v"]]''', '''"polohy": [round(v_, 1) for v_ in led_stav["v"]]'''),
    ("i04_info_auto_je_polohy", "g", K, '''"auto": [round(a_ - zc_l, 1) for a_ in led_stav["auto"]]''', '''"auto": [round(a_ - zc_l, 1) for a_ in led_stav["v"]]'''),
    ("i05_info_stred_uzky", "g", K, '''"stred": [round(led_stav["stred_meze"][0] - zc_l, 1), round(led_stav["stred_meze"][1] - zc_l, 1)]''', '''"stred": [round(led_stav["stred_meze"][0] - zc_l + 10, 1), round(led_stav["stred_meze"][1] - zc_l, 1)]'''),
    ("i06_meze_bez_souseda_vpravo", "g", K, '''        hi = cmax if k == n - 1 else v[k + 1] - s_''', '''        hi = cmax'''),
    ("i07_meze_bez_souseda_vlevo", "g", K, '''        lo = cmin if k == 0 else v[k - 1] + s_
        hi = cmax if k == n - 1''', '''        lo = cmin
        hi = cmax if k == n - 1'''),
    ("i08_meze_bez_rozpeti_vlevo", "g", K, '''            lo = max(lo, v[-1] + s_ - rozpeti_max)''', '''            lo = lo'''),
    ("i09_meze_bez_rozpeti_vpravo", "g", K, '''            hi = min(hi, v[0] - s_ + rozpeti_max)''', '''            hi = hi'''),
    ("i10_pridat_spatny_pocet", "g", K, '''    out = {"led_pocet": len(pol)}''', '''    out = {"led_pocet": len(pol) + 1}'''),
    ("i11_pridat_nikdy_auto", "g", K, '''(None if abs(pol[k] - aut[k]) < 0.05 else round(pol[k] - zc, 1))''', '''round(pol[k] - zc, 1)'''),
    ("i12_odebrat_vzdy_prvni", "g", K, '''    v = [x for i, x in enumerate(st["v"]) if i != k]''', '''    v = [x for i, x in enumerate(st["v"]) if i != 0]'''),
    ("i13_pridat_na_maximu", "g", K, '''    if n >= st["n_max"]:
        return None''', '''    if n > st["n_max"]:
        return None'''),
    ("i14_pridat_vzdy_vystredit", "g", K, '''    kandidati = [v + [v[-1] + s_], [v[0] - s_] + v]
    for k in range(n - 1):
        if v[k + 1] - v[k] >= 2 * s_ - 1e-9:
            kandidati.append(v[:k + 1] + [v[k] + s_] + v[k + 1:])''', '''    kandidati = []'''),
    ("i15_typy_pocet_bez_stropu", "g", K, '''            n_t = led_max_pocet(p["sirka"], telo_l)''', '''            n_t = max(1, int((p["sirka"] + LED_PREVIS) // telo_l))'''),
    # ---- generator: 3D ovladani
    ("o01_tah_meze_prohozene", "g", K, '''"min": float(lo_led), "max": float(hi_led), "krok": 1.0, "casti": [f"led_{k_led + 1}"]''', '''"min": float(hi_led), "max": float(lo_led), "krok": 1.0, "casti": [f"led_{k_led + 1}"]'''),
    ("o02_mereni_od_levehp_znamenko", "g", K, '''{"label": "od levého okraje stolu", "param": f"led_z{k_led + 1}", "mul": 1.0,''', '''{"label": "od levého okraje stolu", "param": f"led_z{k_led + 1}", "mul": -1.0,'''),
    ("o03_mereni_od_praveho_znamenko", "g", K, '''{"label": "od pravého okraje stolu", "param": f"led_z{k_led + 1}", "mul": -1.0,''', '''{"label": "od pravého okraje stolu", "param": f"led_z{k_led + 1}", "mul": 1.0,'''),
    ("o04_mereni_svitidlo_vlevo_posun", "g", K, '''"mul": 1.0, "add": round(-(pol_led[k_led - 1] + tel_led), 1)}''', '''"mul": 1.0, "add": round(-(pol_led[k_led - 1]), 1)}'''),
    ("o05_mereni_svitidlo_vpravo_posun", "g", K, '''"mul": -1.0, "add": round(pol_led[k_led + 1] - tel_led, 1)}''', '''"mul": -1.0, "add": round(pol_led[k_led + 1], 1)}'''),
    ("o06_tah_cast_obecna", "g", K, '''"krok": 1.0, "casti": [f"led_{k_led + 1}"]''', '''"krok": 1.0, "casti": ["led"]'''),
    ("o07_tah_hodnota_absolutne", "g", K, '''"faktor": 1.0, "hodnota": round(pol_led[k_led], 1),''', '''"faktor": 1.0, "hodnota": 0.0,'''),
    ("o08_odebrat_vzdy_vypnout", "g", K, '''            odeb_led = (li_led.get("odebrat") or [None] * n_led_)[k_led] if n_led_ > 1 else {"led_svetlo": False}''', '''            odeb_led = {"led_svetlo": False}'''),
    ("o09_vratit_na_nulu", "g", K, '''pol("Vrátit svítidlo na výchozí místo", {f"led_z{k_led + 1}": None}''', '''pol("Vrátit svítidlo na výchozí místo", {f"led_z{k_led + 1}": 0.0}'''),
    ("o10_vratit_vzdy_povoleno", "g", K, '''"Už je na výchozím místě." if je_auto_led else None)], priorita=3)''', '''None)], priorita=3)'''),
    ("o11_skupina_nizka_priorita", "g", K, '''"Už je na výchozím místě." if je_auto_led else None)], priorita=3)''', '''"Už je na výchozím místě." if je_auto_led else None)], priorita=1)'''),
    ("o12_pridat_bez_duvodu", "g", K, '''None if pr_led else "Další svítidlo LED se sem nevejde (jejich délky dohromady by přesáhly šířku stolu)."))''', '''None))'''),
    ("o13_pridat_jiny_patch", "g", K, '''menu_led_delky.append(pol("Přidat svítidlo LED", pr_led,''', '''menu_led_delky.append(pol("Přidat svítidlo LED", {"led_pocet": 4},'''),
    # ---- generator: zive tazeni
    ("z01_zive_pul_posunu", "g", K, '''dej(f"led_z{k_led}", [op_posun([i_led], 1.0)])''', '''dej(f"led_z{k_led}", [op_posun([i_led], 0.5)])'''),
    ("z02_zive_spatny_dil", "g", K, '''ind_klic.get(("t", LED) if k_led == 1 else ("led", k_led - 1))''', '''ind_klic.get(("t", LED) if k_led == 1 else ("led", k_led))'''),
    ("z03_zive_zadne", "g", K, '''            dej(f"led_z{k_led}", [op_posun([i_led], 1.0)])''', '''            pass'''),
    # ---- GLB: hash
    ("h01_hash_pocet_1_vzdy_pryc", "g", GL, '''        if n_led == 1 and S.led_max_pocet(p["sirka"], S.led_telo_dilu(S.LED_TYPY[S._led_delka_int(p["led_delka"])])) == 1:''', '''        if n_led == 1:'''),
    ("h02_hash_pocet_1_nikdy_pryc", "g", GL, '''        if n_led == 1 and S.led_max_pocet(p["sirka"], S.led_telo_dilu(S.LED_TYPY[S._led_delka_int(p["led_delka"])])) == 1:''', '''        if False:'''),
    ("h03_hash_polohy_nad_poctem", "g", GL, '''            if p.get(k_led) is None or j > n_led:''', '''            if p.get(k_led) is None:'''),
    ("h04_hash_polohy_auto_nesou", "g", GL, '''            if p.get(k_led) is None or j > n_led:''', '''            if j > n_led:'''),
    ("h05_hash_bez_svitidla_pocet", "g", GL, '''        p.pop("led_pocet", None)
        for k_led in S.LED_PARAMETRY_Z:
            p.pop(k_led, None)
    else:''', '''        for k_led in S.LED_PARAMETRY_Z:
            p.pop(k_led, None)
    else:'''),
    ("h06_hash_bez_svitidla_polohy", "g", GL, '''        p.pop("led_pocet", None)
        for k_led in S.LED_PARAMETRY_Z:
            p.pop(k_led, None)
    else:''', '''        p.pop("led_pocet", None)
    else:'''),
    ("e01_sse_nezna_led_pocet", "g", SS, ''' + ("led_pocet",) + S.LED_PARAMETRY_Z''', ''''''),
    # ---- verejne 3D ovladani
    ("v01_slot_poctu", "s", OV, '''PARAM_NA_SLOT.update({"led_pocet": "ledcount",''', '''PARAM_NA_SLOT.update({"led_pocet": "ledcnt",'''),
    ("v02_cast_id", "s", OV, '''f"led_{_k}": f"ledlamp{_k}"''', '''f"led_{_k}": f"led{_k}"'''),
    ("v03_tah_id", "s", OV, '''           **{f"led_z{_k}": f"ledpos{_k}" for _k in range(1, S.LED_MAX + 1)}}''', '''           **{f"led_z{_k}": f"led_z{_k}" for _k in range(1, S.LED_MAX + 1)}}'''),
    ("v04_preklad_en", "s", OV, '''"Remove this light"''', '''"Remove this lamp"'''),
    ("v05_preklad_sk", "s", OV, '''"Odstrániť toto svietidlo"''', '''"Odstrániť svietidlo"'''),
    ("v06_preklad_mereni_en", "s", OV, '''"from the left edge of the table"''', '''"from the left edge"'''),
    ("v07_preklad_tah_sk", "s", OV, '''f"Posun svietidla LED {_k}"''', '''f"Posun LED {_k}"'''),
    # ---- verejne API
    ("p01_ledpos_bez_orezu_bool", "s", SH, '''    if v is None or v == "" or isinstance(v, bool):
        return None''', '''    if v is None or v == "":
        return None'''),
    ("p02_vychozi_pocet_2", "s", SH, '''"ledcount": 1, **{f"ledpos{k}": None''', '''"ledcount": 2, **{f"ledpos{k}": None'''),
    ("p03_zavislost_bez_poctu", "s", SH, '''for k_ in ("ledcount",) + tuple(f"ledpos{j}"''', '''for k_ in () + tuple(f"ledpos{j}"'''),
    ("p04_slider_max_3", "s", SH, '''slider("ledcount", "g_extras", 1, S.LED_MAX, 1, "ks", t["help_ledcount"]),''', '''slider("ledcount", "g_extras", 1, 3, 1, "ks", t["help_ledcount"]),'''),
    ("p05_slider_poloha_uzky", "s", SH, '''slider(f"ledpos{k}", "g_extras", -1500, 1500, 1, "mm",''', '''slider(f"ledpos{k}", "g_extras", -100, 100, 1, "mm",'''),
    ("p06_pocet_z_vyberu_ignorovan", "s", SH, '''    p["led_pocet"] = int(_cislo(sel.get("ledcount"), 1, S.LED_MAX, 1, 1)) if p["led"] else 1''', '''    p["led_pocet"] = 1'''),
    ("p07_polohy_z_vyberu_ignorovany", "s", SH, '''        p[f"led_z{k}"] = _ledpos(sel.get(f"ledpos{k}")) if (p["led"] and k <= p["led_pocet"]) else None''', '''        p[f"led_z{k}"] = None'''),
    ("p08_polohy_nad_poctem_zustanou", "s", SH, '''        p[f"led_z{k}"] = _ledpos(sel.get(f"ledpos{k}")) if (p["led"] and k <= p["led_pocet"]) else None''', '''        p[f"led_z{k}"] = _ledpos(sel.get(f"ledpos{k}")) if p["led"] else None'''),
    ("p09_echo_poctu_1", "s", SH, '''    norm["ledcount"] = int(p["led_pocet"])   ''', '''    norm["ledcount"] = 1   '''),
    ("p10_oznameni_vzdy", "s", SH, '''and pozad_led and int(pozad_led) > int(p["led_pocet"]):''', '''and pozad_led and int(pozad_led) >= int(p["led_pocet"]):'''),
    ("p11_oznameni_nikdy", "s", SH, '''and pozad_led and int(pozad_led) > int(p["led_pocet"]):''', '''and pozad_led and int(pozad_led) > 99:'''),
    ("p12_options_max_pocet", "s", SH, '''options["ledcount"] = {"min": 1, "max": max(1, int(li_["max"])), "value": n_led_}''', '''options["ledcount"] = {"min": 1, "max": S.LED_MAX, "value": n_led_}'''),
    ("p13_options_poloha_mezi_sousedy", "s", SH, '''"min": int(math.ceil(li_["stred"][0])), "max": int(math.floor(li_["stred"][1])),''', '''"min": int(math.ceil(li_["meze"][k - 1][0])), "max": int(math.floor(li_["meze"][k - 1][1])),'''),
    ("p14_options_skryte_s_mezemi", "s", SH, '''                                     if k <= n_led_ else {"hidden": True})''', '''                                     if k <= n_led_ else {"min": 0, "max": 0, "hidden": True})'''),
    ("p15_options_auto_vzdy", "s", SH, '''"auto": p[f"led_z{k}"] is None, "fits": True}''', '''"auto": True, "fits": True}'''),
    ("p16_options_bez_svitidla_otevrene", "s", SH, '''        options["ledcount"] = {"min": 1, "max": 1}
        for k in range(1, S.LED_MAX + 1):
            options[f"ledpos{k}"] = {"hidden": True}''', '''        options["ledcount"] = {"min": 1, "max": 4}
        for k in range(1, S.LED_MAX + 1):
            options[f"ledpos{k}"] = {"hidden": True}'''),
    ("p17_token_bez_J", "s", SH, '''        out["J"] = [n_led] + [None if p.get(f"led_z{k}") is None else round(float(p[f"led_z{k}"]), 1) for k in range(1, n_led + 1)]''', '''        out["Jx"] = [n_led] + [None if p.get(f"led_z{k}") is None else round(float(p[f"led_z{k}"]), 1) for k in range(1, n_led + 1)]'''),
    ("p18_token_J_vzdy", "s", SH, '''(int(p.get("led_pocet", 1)) != 1 or any(p.get(f"led_z{k}") is not None for k in range(1, S.LED_MAX + 1))):''', '''True):'''),
    ("p19_rozbal_bez_J", "s", SH, '''    if o.get("J"):
        p["led_pocet"] = int(o["J"][0])''', '''    if o.get("Jx"):
        p["led_pocet"] = int(o["J"][0])'''),
    ("p20_rozbal_polohy_float", "s", SH, '''            p[f"led_z{i}"] = None if v is None else float(v)''', '''            p[f"led_z{i}"] = None'''),
    ("p21_cache_bez_poctu", "s", SH, '''norm.get("ledlen"), norm.get("ledcount"), tuple(sorted(led_delky_pro_pozadavek())))''', '''norm.get("ledlen"), tuple(sorted(led_delky_pro_pozadavek())))'''),
    ("p22_souhrn_pocet_vzdy", "s", SH, '''    if not svitidlo_ or int(sel.get("ledcount") or 1) == 1:''', '''    if not svitidlo_:'''),
    ("p23_souhrn_polohy_vzdy", "s", SH, '''        if not svitidlo_ or k > int(sel.get("ledcount") or 1) or sel.get(f"ledpos{k}") is None:''', '''        if not svitidlo_ or k > int(sel.get("ledcount") or 1):'''),
    ("p24_odkaz_s_poctem_1", "s", SH, ''' and not (k == "led_pocet" and int(v) == 1)''', ''''''),
    ("p25_text_orezu_en", "s", SH, '''"en": "Number of LED lights reduced to {n} – more will not fit side by side (a narrower table or longer lights).",''', '''"en": "Number of LED lights reduced to {n}.",'''),
    ("p26_popisek_en", "s", SH, '''TEXTY["en"].update({"ledcount": "Number of LED lights",''', '''TEXTY["en"].update({"ledcount": "LED count",'''),
    ("p27_popisek_polohy_sk", "s", SH, '''**{f"ledpos{k}": f"Poloha svietidla LED {k}" for k in range(1, S.LED_MAX + 1)}})''', '''**{f"ledpos{k}": f"Svietidlo {k}" for k in range(1, S.LED_MAX + 1)}})'''),
    ("p28_ledpos_zaokrouhleni", "s", SH, '''    return round(min(3000.0, max(-3000.0, x)), 1) if math.isfinite(x) else None''', '''    return min(3000.0, max(-3000.0, x)) if math.isfinite(x) else None'''),
    ("p29_ledpos_nan_ok", "s", SH, '''    return round(min(3000.0, max(-3000.0, x)), 1) if math.isfinite(x) else None''', '''    return round(min(3000.0, max(-3000.0, x)), 1)'''),
]


# EKVIVALENTNI mutace (zmena neni navenek pozorovatelna, test ji z principu nema chytat): nechycena = v poradku
EKVIVALENTNI = {
    "l25_proveditelne_vzdy": "`proveditelne` (stul prilis uzky pro svitidlo) ridi jen mezikrok pred automatickym odebranim LED; po odebrani se pocet i polohy vraci na vychozi, vysledek je tentyz",
    "i15_typy_pocet_bez_stropu": "strop LED_MAX = 4 se u `led_info.typy[].pocet` neprojevi, dokud je sirka stolu <= 3000 mm (3047 // 647 = 4); platilo by az pro sirsi stul",
}


def spust(m):
    nazev, kt, soubor, puvodni, nahrada = m
    test, db = TESTY[kt]
    d = tempfile.mkdtemp(prefix="mut_ledr_")
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


def over():
    vady = []
    jmena = set()
    for nazev, kt, soubor, puvodni, nahrada in MUTACE:
        s = open(os.path.join(ZDROJ, soubor), encoding="utf-8").read()
        if nazev in jmena:
            vady.append(f"{nazev}: duplicitni nazev")
        jmena.add(nazev)
        if s.count(puvodni) != 1:
            vady.append(f"{nazev}: puvodni text v {soubor} {s.count(puvodni)}x")
        if puvodni == nahrada:
            vady.append(f"{nazev}: nahrada = puvodni")
    return vady


if __name__ == "__main__":
    if "--over" in sys.argv:
        v = over()
        print("\n".join(v) if v else f"OK: {len(MUTACE)} mutaci, kazdy puvodni text je v souboru prave jednou")
        sys.exit(1 if v else 0)
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
            ekv = (not chycena) and nazev in EKVIVALENTNI
            print(f"mutace {nazev}: rc={rc} ({'CHYCENA' if chycena else ('EKVIVALENTNI - ' + EKVIVALENTNI[nazev] if ekv else 'NECHYCENA')})  {info if chycena or not ekv else ''}")
            if not chycena and not ekv:
                necytene.append(nazev)
    print(f"\n==> {len(seznam) - len(necytene)}/{len(seznam)} mutaci chyceno" + (f"; NECHYCENE / VADNE: {', '.join(necytene)}" if necytene else " - VSECHNY CHYCENY"))
    sys.exit(1 if necytene else 0)
