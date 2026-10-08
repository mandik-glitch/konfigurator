#!/usr/bin/env python3
"""MUTACE generatoru OCHRANNY KRYT A OPLOCENI (bot8, 2026-10-08): kazda umyslna chyba v oploceni_konfigurator.py / oploceni_glb.py / oploceni_cena.py MUSI shodit test_oploceni.py (CHYCENA = dobre,
PREZILA = chybi test). Kazda mutace dostane vlastni kopii adresare faze 1 (symlinky na api/, webapp/ a spolecne pomucky; upraveny je jen jeden soubor), test bezi na kopii, 4 paralelne.
Zadna DB, zadny zapis do zive stromu (mimo docasneho adresare).

  api/venv/bin/python3 scripts/2026-10-08_oploceni/mutace_oploceni.py [nazev_mutace ...]      (bez argumentu vsechny)
  api/venv/bin/python3 scripts/2026-10-08_oploceni/mutace_oploceni.py --kotvy                  (jen overi, ze kazda kotva se v souboru najde prave jednou)"""
import concurrent.futures
import glob
import os
import py_compile
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
PY = os.path.join(REPO, "api", "venv", "bin", "python3")
K = "oploceni_konfigurator.py"
G = "oploceni_glb.py"
C = "oploceni_cena.py"

# (nazev, soubor, puvodni text, nahrada) - puvodni text musi byt v souboru PRAVE JEDNOU
MUTACE = [
    # ---- normalizace a meze ----
    ("n01_sirka_min", K, '"sirka": (600.0, 6000.0)', '"sirka": (500.0, 6000.0)'),
    ("n02_sirka_max", K, '"sirka": (600.0, 6000.0)', '"sirka": (600.0, 7000.0)'),
    ("n03_vyska_min", K, '"vyska": (1000.0, 3000.0)', '"vyska": (900.0, 3000.0)'),
    ("n04_vyska_max", K, '"vyska": (1000.0, 3000.0)', '"vyska": (1000.0, 3200.0)'),
    ("n05_hloubka_max", K, '"hloubka": (600.0, 6000.0)', '"hloubka": (600.0, 6500.0)'),
    ("n06_dvere_sirka_min", K, '"dvere_sirka": (600.0, 1200.0)', '"dvere_sirka": (500.0, 1200.0)'),
    ("n07_dvere_sirka_max", K, '"dvere_sirka": (600.0, 1200.0)', '"dvere_sirka": (600.0, 1300.0)'),
    ("n08_dvere_vyska_min", K, '"dvere_vyska": (1500.0, 2400.0)', '"dvere_vyska": (1400.0, 2400.0)'),
    ("n09_bool_jako_cislo", K, "if isinstance(v, bool) or not isinstance(v, (int, float, str)):", "if not isinstance(v, (int, float, str)):"),
    ("n10_nan_projde", K, "if not math.isfinite(x):", "if False:"),
    ("n11_neznamy_parametr", K, "        if k not in VYCHOZI:\n", "        if False:\n"),
    ("n12_neznamy_typ_strany", K, "if p[k] not in TYPY_STRANY:", "if False:"),
    ("n13_neznama_strecha", K, 'if p["strecha"] not in STRECHY:', "if False:"),
    ("n14_neznama_vyplne", K, 'if p["vyplne"] not in VYPLNE:', "if False:"),
    ("n15_neznama_vyplne_strany", K, "if p[k] is not None and p[k] not in VYPLNE:", "if False:"),
    ("n16_prazdna_konstrukce", K, 'if all(p[k] == "otevreno" for k in STRANY) and p["strecha"] == "zadna":', "if False:"),
    ("n17_dvere_parametry_zustavaji", K, 'if not any(p[k] == "dvere" for k in STRANY):', "if False:"),
    ("n18_vyplne_otevrene_strany_zustava", K, '        if p[k.replace("vyplne_", "")] == "otevreno":\n', "        if False:\n"),
    ("n19_vyplne_strechy_zustava", K, '    if p["strecha"] != "vyplne":\n        p["vyplne_strecha"] = None', '    if False:\n        p["vyplne_strecha"] = None'),
    ("n20_hloubka_nekanonizuje", K, 'if existuji <= {"celo"} or existuji <= {"zadni"}:', "if False:"),
    ("n21_sirka_nekanonizuje", K, 'elif existuji <= {"prava"} or existuji <= {"leva"}:', "elif False:"),
    ("n23_patky_minimalni_vyska", K, "if H - y0 < 1000.0 - 1e-9:", "if False:"),
    ("n24_zamek_nekanonizuje", K, 'VYCHOZI["dvere_zavesy"], VYCHOZI["zamek"])', 'VYCHOZI["dvere_zavesy"], p["zamek"])'),
    ("n25_dvere_vyska_nekanonizuje", K, 'VYCHOZI["dvere_sirka"], None, VYCHOZI["dvere_poloha"]', 'VYCHOZI["dvere_sirka"], p["dvere_vyska"], VYCHOZI["dvere_poloha"]'),
    ("n26_zaokrouhleni_rozmeru", K, "    return round(x, 1)\n", "    return round(x, 0)\n"),
    ("n22_kanonizace_prilis_siroka", K, 'if existuji <= {"celo"} or existuji <= {"zadni"}:', "if len(existuji) <= 2:"),
    # ---- pravidla poli, radku, dveri ----
    ("r01_pole_max", K, "POLE_MAX = 1200.0", "POLE_MAX = 1300.0"),
    ("r02_mid_max", K, "MID_MAX = 1100.0", "MID_MAX = 1200.0"),
    ("r03_pole_hranice", K, "while (span - PROFIL * (n - 1)) / n > nmax + 1e-9:", "while (span - PROFIL * (n - 1)) / n >= nmax:"),
    ("r04_radek_hranice", K, "while (vyska_otvoru - PROFIL * nm) / (nm + 1) > MID_MAX + 1e-9:", "while (vyska_otvoru - PROFIL * nm) / (nm + 1) >= MID_MAX:"),
    ("r05_sirka_pole", K, "return n, (span - PROFIL * (n - 1)) / n", "return n, (span - PROFIL * n) / n"),
    ("r06_vyska_radku", K, "return nm, (vyska_otvoru - PROFIL * nm) / (nm + 1)", "return nm, (vyska_otvoru - PROFIL * (nm + 1)) / (nm + 1)"),
    ("r07_mezera_dveri", K, "MEZERA_DVERE = 3.0", "MEZERA_DVERE = 4.0"),
    ("r08_dvere_nad_podlahou", K, "DVERE_NAD_PODLAHOU = 5.0", "DVERE_NAD_PODLAHOU = 6.0"),
    ("r09_nadpraz_min", K, "NADPRAZ_MIN = 150.0", "NADPRAZ_MIN = 120.0"),
    ("r10_vychozi_vyska_dveri", K, "return min(2000.0, dh_max), spodek", "return min(2100.0, dh_max), spodek"),
    ("r11_vyska_patky", K, "PATKA_VYSKA = 79.0", "PATKA_VYSKA = 80.0"),
    ("r12_pole_min", K, "POLE_MIN = 150.0", "POLE_MIN = 100.0"),
    ("r13_poloha_dveri_vpravo", K, '    if p["dvere_poloha"] == "vpravo":', '    if p["dvere_poloha"] == "vlevo":'),
    ("r14_dvere_nevejdou_sirka", K, "if OW > S0 + 1e-9:", "if False:"),
    ("r15_dvere_nevejdou_vyska", K, "if p[\"dvere_vyska\"] > dh_max + 1e-9:", "if False:"),
    ("r16_uzke_pole_u_dveri", K, "    if strana_uzka(pole_sirka):", "    if False:"),
    ("r17_uzke_pole_stred", K, "        if strana_uzka(po_strane):", "        if False:"),
    # ---- dvere: zavesy, zamek ----
    ("d01_strana_zavesu", K, 'u_zav = u0 + MEZERA_DVERE / 2.0 if p["dvere_zavesy"] == "vlevo" else u1 - MEZERA_DVERE / 2.0', 'u_zav = u0 + MEZERA_DVERE / 2.0 if p["dvere_zavesy"] == "vpravo" else u1 - MEZERA_DVERE / 2.0'),
    ("d02_typ_zavesu", K, 'S._dil(PANT_PRAVY if p["dvere_zavesy"] == "vpravo" else PANT_LEVY,', 'S._dil(PANT_PRAVY if p["dvere_zavesy"] == "vlevo" else PANT_LEVY,'),
    ("d03_zapadka_na_strane_zavesu", K, 'u_st = (ur - 20.0) if p["dvere_zavesy"] == "vlevo" else (ul + 20.0)', 'u_st = (ur - 20.0) if p["dvere_zavesy"] == "vpravo" else (ul + 20.0)'),
    ("d04_zamek_zamenen", K, 'dil_id = ZAPADKA if p["zamek"] == "zapadka" else ZAMEK', 'dil_id = ZAPADKA if p["zamek"] != "zapadka" else ZAMEK'),
    ("d05_dva_zavesy", K, "ys = [spodek + ZAVESY_Y, (spodek + vrch) / 2.0, vrch - ZAVESY_Y]", "ys = [spodek + ZAVESY_Y, vrch - ZAVESY_Y]"),
    ("d06_zavesy_y", K, "ZAVESY_Y = 150.0", "ZAVESY_Y = 140.0"),
    ("d07_zavesy_odsazeni", K, "stred = pt(u_zav, yz) + n_out * (PROFIL / 2.0 + 6.15)", "stred = pt(u_zav, yz) + n_out * (PROFIL / 2.0 + 0.0)"),
    ("d08_zavesy_uvnitr", K, "stred = pt(u_zav, yz) + n_out * (PROFIL / 2.0 + 6.15)", "stred = pt(u_zav, yz) - n_out * (PROFIL / 2.0 + 6.15)"),
    ("d09_bez_nadprazi", K, 'S.pricka(pt(u0, y_nadpraz), pt(u1, y_nadpraz), f"nadpraží dveří ({s})", s, [UP], nadpraz=True)', "pass"),
    ("d10_nadpraz_spojky_dolu", K, 'f"nadpraží dveří ({s})", s, [UP], nadpraz=True)', 'f"nadpraží dveří ({s})", s, [UP, -UP], nadpraz=True)'),
    ("d11_bez_mezipricky_kridla", K, 'S.pricka(pt(ul + PROFIL, yc), pt(ur - PROFIL, yc), f"mezipříčka křídla ({s})", s, [UP, -UP], kridlo=True)', "pass"),
    ("d12_vyplne_kridla_o_radek_mene", K, "            for kk in range(nm + 1):\n                S.vypln(vyp, pt((ul + ur) / 2.0,", "            for kk in range(nm):\n                S.vypln(vyp, pt((ul + ur) / 2.0,"),
    ("d13_bez_zaslepek_stojek", K, 'S.zaslepka(np.array([c[0], vrch, c[2]]), -UP, f"zaslepka stojky křídla ({s})", kridlo=True)', "pass"),
    ("d14_zamek_vyska", K, "spodek + min(1000.0, dh / 2.0)) + n_out * (PROFIL / 2.0)", "spodek + min(900.0, dh / 2.0)) + n_out * (PROFIL / 2.0)"),
    ("d15_zamek_dosedaci_plocha", K, "stred_lic[OSA[normala]] = lo_[OSA[normala]]", "stred_lic[OSA[normala]] = (lo_[OSA[normala]] + hi_[OSA[normala]]) / 2.0"),
    ("d16_zamek_orientace_zapadky", K, "ZAMEK_MONTAZ = {ZAPADKA: (\"x\", \"y\"), ZAMEK: (\"z\", \"y\")}", "ZAMEK_MONTAZ = {ZAPADKA: (\"z\", \"y\"), ZAMEK: (\"z\", \"y\")}"),
    ("d17_zamek_orientace_zamku", K, "ZAMEK_MONTAZ = {ZAPADKA: (\"x\", \"y\"), ZAMEK: (\"z\", \"y\")}", "ZAMEK_MONTAZ = {ZAPADKA: (\"x\", \"y\"), ZAMEK: (\"x\", \"y\")}"),
    ("d18_osa_dveri_info", K, '"osa_bod": _zaokr(pt(u_zav, 0.0) + n_out * (PROFIL / 2.0 + 6.15))', '"osa_bod": _zaokr(pt(u_zav, 0.0))'),
    ("d19_stojka_kridla_vyska", K, "S.profil(np.array([c[0], spodek, c[2]]), np.array([c[0], vrch, c[2]]), f\"{role} ({s})\"", "S.profil(np.array([c[0], spodek, c[2]]), np.array([c[0], vrch - 10.0, c[2]]), f\"{role} ({s})\""),
    # ---- konstrukce: sloupky, pricky, spojky ----
    ("k01_mezilehly_sloupek_az_nahoru", K, 'vrch=H - PROFIL, eu=z["eu"], strana=s)', 'vrch=H, eu=z["eu"], strana=s)'),
    ("k02_T_spoj_jedna_spojka", K, "            for sm in (1.0, -1.0):\n                self.spojka(np.array([x, y_hor, z]), -UP,", "            for sm in (1.0,):\n                self.spojka(np.array([x, y_hor, z]), -UP,"),
    ("k03_horni_pricka_spojky_nahoru", K, 'f"horní příčka ({s})", s, [-UP])      # souvisla', 'f"horní příčka ({s})", s, [UP])      # souvisla'),
    ("k04_dolni_pricka_spojky_dolu", K, 'f"dolní příčka ({s})", s, [UP])', 'f"dolní příčka ({s})", s, [-UP])'),
    ("k05_bez_dolni_pricky", K, 'S.pricka(pt(u0, y0 + 20.0), pt(u1, y0 + 20.0), f"dolní příčka ({s})", s, [UP])', "pass"),
    ("k06_mezipricka_jedna_spojka", K, 'S.pricka(pt(u0, yc), pt(u1, yc), f"mezipříčka ({s})", s, [UP, -UP])', 'S.pricka(pt(u0, yc), pt(u1, yc), f"mezipříčka ({s})", s, [UP])'),
    ("k07_pravidlo_spojky_posun_a", K, "pos = np.asarray(Q, float) + (PROFIL / 2.0 + BLOK) * a - (BLOK / 2.0) * c", "pos = np.asarray(Q, float) + (PROFIL / 2.0 + BLOK - 1.0) * a - (BLOK / 2.0) * c"),
    ("k08_pravidlo_spojky_bez_posunu_c", K, "pos = np.asarray(Q, float) + (PROFIL / 2.0 + BLOK) * a - (BLOK / 2.0) * c", "pos = np.asarray(Q, float) + (PROFIL / 2.0 + BLOK) * a"),
    ("k09_pravidlo_spojky_znamenko_c", K, "pos = np.asarray(Q, float) + (PROFIL / 2.0 + BLOK) * a - (BLOK / 2.0) * c", "pos = np.asarray(Q, float) + (PROFIL / 2.0 + BLOK) * a + (BLOK / 2.0) * c"),
    ("k10_spojka_chiralita", K, "c = np.cross(b, a)\n        R = np.column_stack([b, a, c])", "c = np.cross(a, b)\n        R = np.column_stack([b, a, c])"),
    ("k11_spojka_osy", K, "R = np.column_stack([b, a, c])", "R = np.column_stack([a, b, c])"),
    ("k12_zaslepka_smer", K, "z = np.asarray(dovnitr, float)", "z = -np.asarray(dovnitr, float)"),
    ("k13_rohove_sloupky_vzdy", K, 'if strecha or any(typy[s] != "otevreno" for s in sousedi):', "if True:"),
    ("k14_rohove_sloupky_nikdy_bez_strechy", K, 'if strecha or any(typy[s] != "otevreno" for s in sousedi):', 'if any(typy[s] != "otevreno" for s in sousedi) and strecha:'),
    ("k15_strecha_jen_zadna", K, 'strecha = p["strecha"] != "zadna"', "strecha = True"),
    ("k16_horni_pricka_otevrene_strany", K, 'S.pricka(pt(PROFIL, H - 20.0), pt(z["L"] - PROFIL, H - 20.0), f"horní příčka ({s}, otevřená strana)", s, [-UP])', "pass"),
    ("k17_patka_chybi", K, "            self.patka(x, z)\n", "            pass\n"),
    ("k18_patky_vyska_nula", K, 'self.y0 = PATKA_VYSKA if p["patky"] else 0.0', "self.y0 = 0.0"),
    ("k19_sloupek_bez_zaslepky_nahore", K, 'self.zaslepka(np.array([x, y_hor, z]), -UP, "zaslepka sloupku (nahoře)")', "pass"),
    ("k20_pocet_spoju_podle_spojek", K, 'return len({tuple(np.round(sp["Q"], 1)) + tuple(np.round(sp["b"], 3)) for sp in S.spoje})', "return len(S.spoje)"),
    # ---- vyplne, vyrezy, strecha ----
    ("v01_vyrez_maly", K, "VYREZ = INS + BLOK + 1.0", "VYREZ = INS + BLOK - 5.0"),
    ("v02_zasunuti", K, "INS = 9.0", "INS = 8.0"),
    ("v03_bez_vyrezu_rohu", K, "N[(s1, s2)] = VYREZ", "N[(s1, s2)] = 0.0"),
    ("v04_strecha_bez_malych_vyrezu", K, '"střešní výplň", "strecha", male)', '"střešní výplň", "strecha", [])'),
    ("v05_strecha_deleni_x", K, "nx, wx = _deleni(ix)", "nx, wx = _deleni(ix + 40.0)"),
    ("v06_strecha_deleni_z", K, "nz, wz = _deleni(iz)", "nz, wz = _deleni(iz - 40.0)"),
    ("v07_strecha_pricky_podel_hloubky", K, "        for k in range(nx - 1):\n            xc = xs[k] + wx + PROFIL / 2.0", "        for k in range(nx):\n            xc = xs[k] + wx + PROFIL / 2.0"),
    ("v08_strecha_rovina", K, "        yc = H - 20.0\n        # pricky podel Z", "        yc = H - 10.0\n        # pricky podel Z"),
    ("v09_strecha_ram_ma_vyplne", K, 'if p["strecha"] == "vyplne":\n        vyp = p["vyplne_strecha"] or p["vyplne"]', 'if p["strecha"] != "zadna":\n        vyp = p["vyplne_strecha"] or p["vyplne"]'),
    ("v10_strecha_vyplne_strany", K, 'vyp = p["vyplne_strecha"] or p["vyplne"]', 'vyp = p["vyplne"]'),
    ("v11_stena_vyplne_strany", K, 'vyp = p["vyplne_" + s] or p["vyplne"]', 'vyp = p["vyplne"]'),
    ("v12_sonda_rohu_hluboko", K, 'sonda = np.array(v["stred"]) + e1 * s1 * (v["w"] / 2.0 - 1.0) + e2 * s2 * (v["h"] / 2.0 - 1.0)', 'sonda = np.array(v["stred"]) + e1 * s1 * (v["w"] / 2.0 - 45.0) + e2 * s2 * (v["h"] / 2.0 - 45.0)'),
    ("v12b_sonda_rohu_venku", K, 'sonda = np.array(v["stred"]) + e1 * s1 * (v["w"] / 2.0 - 1.0) + e2 * s2 * (v["h"] / 2.0 - 1.0)', 'sonda = np.array(v["stred"]) + e1 * s1 * (v["w"] / 2.0 + 1.0) + e2 * s2 * (v["h"] / 2.0 + 1.0)'),
    ("v13_pole_vyplne_o_radek_mene", K, "                for kk in range(nm + 1):\n                    S.vypln(vyp, pt(uc, yb + oh / 2.0)", "                for kk in range(nm):\n                    S.vypln(vyp, pt(uc, yb + oh / 2.0)"),
    ("v14_vypln_nadprazi_vyska", K, 'S.vypln(vyp, pt(uc, yb + oh_n / 2.0), z["eu"], UP, z["n"], w, oh_n, f"výplň nadpraží ({s})", s)', 'S.vypln(vyp, pt(uc, yb + oh_n / 2.0), z["eu"], UP, z["n"], w, oh_n - 10.0, f"výplň nadpraží ({s})", s)'),
    ("v15_nadpraz_bez_deleni", K, "nm_n, oh_n = _radky(y_horni_dolni - y_nad_dol)", "nm_n, oh_n = 0, y_horni_dolni - y_nad_dol"),
    ("v16_nadpraz_mezipricka_jedna_spojka", K, 'f"mezipříčka nadpraží ({s})", s, [UP, -UP])', 'f"mezipříčka nadpraží ({s})", s, [UP])'),
    # ---- kusovnik, entries, hash, rozmery ----
    ("b01_tesneni_obvod", K, 'tesneni[info["tesneni"]] = tesneni.get(info["tesneni"], 0.0) + 2.0 * (v["w"] + v["h"]) / 1000.0', 'tesneni[info["tesneni"]] = tesneni.get(info["tesneni"], 0.0) + (v["w"] + v["h"]) / 1000.0'),
    ("b02_spoje_na_prvni_profil_dvakrat", K, 'e["joint_count"] = pocet_spoju', 'e["joint_count"] = pocet_spoju * 2'),
    ("b03_spojovaci_material_mnozstvi", K, 'q["mnozstvi"] += ks * n', 'q["mnozstvi"] += n'),
    ("b04_sroub_na_spojku", K, '("2.1.21.0616", 2,', '("2.1.21.0616", 3,'),
    ("b05_hash_poradi_klicu", K, "json.dumps(p, sort_keys=True, separators", "json.dumps(p, sort_keys=False, separators"),
    ("b06_hash_delka", K, "hexdigest()[:16]", "hexdigest()[:12]"),
    ("b07_cena_vyplne_m2", K, '"cena_m2": 1150.0', '"cena_m2": 1100.0'),
    ("b08_cena_tesneni", K, '"cena_m": 32.0', '"cena_m": 30.0'),
    ("b09_rozmery_z_parametru", K, '"hloubka_mm": round(float(ext[2]), 1)', '"hloubka_mm": p["hloubka"]'),
    ("b10_uzavreny_vzdy", K, 'uzavreny = sum(1 for d in profily if d["role"].startswith("rohový sloupek")) == 4', "uzavreny = True"),
    ("b11_vyplne_v_entries_bez_rozmeru", K, 'entries.append({"product_id": "navrh:" + v["typ"], "width_mm": w, "height_mm": h})', 'entries.append({"product_id": "navrh:" + v["typ"], "width_mm": v["w"], "height_mm": v["h"]})'),
    ("b13_upozorneni_sit_podle_celkove_volby", K, 'if any(v["typ"] == "sit" for v in S.vyplne):', 'if p["vyplne"] == "sit":'),
    ("b14_upozorneni_kotveni_vyska", K, 'if p["vyska"] > 2500 or max(p["sirka"], p["hloubka"]) > 4000:', 'if p["vyska"] >= 2500 or max(p["sirka"], p["hloubka"]) > 4000:'),
    ("b15_upozorneni_kotveni_delka", K, 'if p["vyska"] > 2500 or max(p["sirka"], p["hloubka"]) > 4000:', 'if p["vyska"] > 2500 or p["sirka"] > 4000:'),
    ("b16_upozorneni_dvere_siroke", K, 'p["dvere_sirka"] > 1000:', 'p["dvere_sirka"] >= 1000:'),
    # (mutace 'upozorneni dvere_siroke bez podminky any(dvere)' je EKVIVALENTNI: normalizuj() vraci bez dveri dvere_sirka na 800, takze podminka je po kanonizaci redundantni - vynechano)
    ("b12_upozorneni_norma_chybi", K, 'upozorneni = [{"id": "norma",', 'upozorneni = [{"id": "norma_",'),
    # ---- GLB ----
    ("g01_bez_blend", G, 'm["alphaMode"] = "BLEND"', "pass"),
    ("g02_jednostranne", G, '"doubleSided": True}', '"doubleSided": False}'),
    ("g03_box_bez_posunu", G, "box_lo, box_hi = lo + posun, hi + posun", "box_lo, box_hi = lo, hi"),
    ("g04_necentrovano", G, "posun = np.array([-(lo[0] + hi[0]) / 2.0, -lo[1], -(lo[2] + hi[2]) / 2.0])", "posun = np.array([0.0, -lo[1], 0.0])"),
    ("g05_celo_dozadu", G, '"front": [0, 0, 1]', '"front": [0, 0, -1]'),
    ("g06_up_osa", G, '"up": [0, 1, 0]', '"up": [0, 0, 1]'),
    ("g07_tloustka_vyplne", G, "np.abs(nn) * t / 2.0", "np.abs(nn) * t"),
    ("g08_dvere_otvira_dovnitr", G, 'znam = 1.0 if d["zavesy"] == "vpravo" else -1.0', 'znam = -1.0 if d["zavesy"] == "vpravo" else 1.0'),
    ("g09_otevreni_bez_vyplne_kridla", G, 'if v["role"].startswith("výplň křídla") and v["strana"] in osy:', "if False:"),
    ("g10_otevreni_bez_dilu_kridla", G, "if _je_kridlo(dil) and dil.get(\"strana\") in osy:", "if False:"),
    ("g11_material_zaslepek", G, 'O.ZASLEPKA: "cerna"', 'O.ZASLEPKA: "ocel"'),
    ("g12_material_spojek", G, 'O.SPOJKA: "ocel"', 'O.SPOJKA: "alu"'),
    ("g13_sit_bez_textury", G, '"blend": True, "tex": "sit"}', '"blend": True}'),
    ("g14_sit_bez_uv", G, "uv = np.stack([P @ e1, P @ e2], axis=1) / SIT_ROZTEC if", "uv = None if True or"),
    ("g15_cache_neomezena_klic", G, "    h = r[\"hash\"]\n    if h in _CACHE:", "    h = \"x\"\n    if h in _CACHE:"),
    ("g16_prvni_hash", G, "return h, glb", "return h + \"x\", glb"),
    # ---- cena ----
    ("c01_vypln_neni_deska", C, '"is_board_material": True,', '"is_board_material": False,'),
    ("c02_cena_vyplne_polovicni", C, '"price_czk": info["cena_m2"],', '"price_czk": info["cena_m2"] / 2,'),
    ("c03_spojovaci_material_po_jednom", C, 'entries.extend({"product_id": pid} for _ in range(m["mnozstvi"]))', 'entries.extend({"product_id": pid} for _ in range(1))'),
    ("c04_chybejici_se_neohlasi", C, "            chybejici.append(m)\n", "            pass\n"),
    ("c05_bez_extra_prace", C, 'extra_work=r["extra_prace"])', "extra_work=None)"),
    ("c06_doplnky_bez_koeficientu", C, 'CP.apply_scene_coefficient(nove, ctx["pricing"].get("scene_price_coefficient", 1.0))', "pass"),
    ("c07_doplnky_koeficient_vsem", C, '"scene_coef": bool(r.get("is_profile_material")) or bool(r.get("dogus_url")),', '"scene_coef": True,'),
    ("c07b_doplnky_koeficient_nikomu", C, '"scene_coef": bool(r.get("is_profile_material")) or bool(r.get("dogus_url")),', '"scene_coef": False,'),
    ("c08_doplnky_prepis_existujici", C, '        if part_id in ctx["parts"]:\n            continue\n', "        pass\n"),
    ("c09_doplnky_jednotka", C, '"unit": (r.get("unit") or "").strip().lower() or None', '"unit": r.get("unit")'),
    ("c10_doplnky_hmotnost", C, 'float(r["weight_g"]) / 1000 if r["weight_g"] is not None else None', 'float(r["weight_g"]) if r["weight_g"] is not None else None'),
    ("c11_doplnky_neptat_se_na_sku", C, '" OR sku IN (" + ",".join(["%s"] * len(DOPLNKOVE_SKU)) + ")", tuple(DOPLNKOVE_KARTY) + tuple(DOPLNKOVE_SKU))', '"", tuple(DOPLNKOVE_KARTY))'),
]


def _kopie(mut):
    d = tempfile.mkdtemp(prefix="mut_oploceni_")
    os.makedirs(os.path.join(d, "scripts", "2026-10-08_oploceni"))
    for f in glob.glob(os.path.join(HERE, "*.py")):
        shutil.copy(f, os.path.join(d, "scripts", "2026-10-08_oploceni", os.path.basename(f)))
    for f in os.listdir(os.path.join(REPO, "scripts")):                    # zbytek scripts/ (moduly, ktere importuje app.py, napr. razitkovac) jako symlinky; kopie faze 1 je jen jedna
        if f != "2026-10-08_oploceni":
            os.symlink(os.path.join(REPO, "scripts", f), os.path.join(d, "scripts", f))
    os.symlink(os.path.join(REPO, "api"), os.path.join(d, "api"))
    os.symlink(os.path.join(REPO, "webapp"), os.path.join(d, "webapp"))
    return d


def spust(m):
    nazev, soubor, puvodni, nahrada = m
    d = _kopie(m)
    try:
        cil = os.path.join(d, "scripts", "2026-10-08_oploceni", soubor)
        s = open(cil, encoding="utf-8").read()
        if s.count(puvodni) != 1:
            return nazev, "KOTVA", f"puvodni text se v {soubor} nenasel prave jednou ({s.count(puvodni)}x)"
        open(cil, "w", encoding="utf-8").write(s.replace(puvodni, nahrada))
        try:
            py_compile.compile(cil, cfile=os.path.join(d, "x.pyc"), doraise=True)
        except py_compile.PyCompileError as e:
            return nazev, "NEPLATNA", str(e)[:200]
        p = subprocess.run([PY, os.path.join(d, "scripts", "2026-10-08_oploceni", "test_oploceni.py")], capture_output=True, text=True, timeout=900, cwd=d,
                           env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        n_chyb = p.stdout.count("CHYBA")
        if p.returncode == 0:
            return nazev, "PREZILA", ""
        if n_chyb:
            return nazev, "CHYCENA", f"{n_chyb} selhani"
        posledni = (p.stderr.strip().splitlines() or ["?"])[-1][:160]
        if posledni.startswith(("ModuleNotFoundError", "ImportError", "FileNotFoundError", "PermissionError", "OSError")):
            return nazev, "PROSTREDI", posledni                            # chyba prostredi mutacniho behu, ne dukaz, ze test mutaci chyta
        return nazev, "CHYCENA", "vyjimka: " + posledni
    finally:
        shutil.rmtree(d, ignore_errors=True)


def over_kotvy():
    zle = 0
    for nazev, soubor, puvodni, nahrada in MUTACE:
        s = open(os.path.join(HERE, soubor), encoding="utf-8").read()
        n = s.count(puvodni)
        if n != 1:
            zle += 1
            print(f"KOTVA {nazev}: {n}x v {soubor}")
        if puvodni == nahrada:
            zle += 1
            print(f"KOTVA {nazev}: nahrada je shodna s puvodnim textem")
    jmena = [m[0] for m in MUTACE]
    if len(set(jmena)) != len(jmena):
        zle += 1
        print("KOTVA: duplicitni nazvy mutaci")
    print(f"{len(MUTACE)} mutaci, kotev v poradku: {len(MUTACE) - zle}")
    return zle


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if "--kotvy" in sys.argv:
        sys.exit(1 if over_kotvy() else 0)
    vyber = [m for m in MUTACE if not args or m[0] in args]
    if not vyber:
        print("zadna mutace nevybrana")
        sys.exit(2)
    vysledky = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
        for nazev, stav, info in ex.map(spust, vyber):
            print(f"{stav:8s} {nazev:44s} {info}", flush=True)
            vysledky.append((nazev, stav, info))
    chycene = sum(1 for v in vysledky if v[1] == "CHYCENA")
    zle = [v for v in vysledky if v[1] != "CHYCENA"]
    print(f"\n==> CHYCENO {chycene}/{len(vysledky)}" + ("" if not zle else "; NECHYCENE / CHYBNE: " + ", ".join(f"{v[0]} ({v[1]})" for v in zle)))
    sys.exit(1 if zle else 0)
