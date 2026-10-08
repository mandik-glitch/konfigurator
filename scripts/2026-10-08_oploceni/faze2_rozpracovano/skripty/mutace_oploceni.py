#!/usr/bin/env python3
"""MUTACE generatoru OCHRANNY KRYT A OPLOCENI (bot8, 2026-10-08, faze 2): kazda umyslna chyba v api/oploceni_*.py (jadro, 3D model, cena, shop vrstva) a v zaplatach api/konfigurator_registr.py,
api/stul_shop.py, api/konfigurace_kosik.py, api/nabidka_z_konfigurace.py MUSI shodit prislusny test (CHYCENA = dobre, PREZILA = chybi test):
  * jadro / glb / cena           -> test_oploceni.py (hermeticky, ~15 s)             [sloupec `testy` "j"]
  * shop vrstva, registr, routy  -> test_oploceni_shop.py (DB jen cte, ~1 min)       [sloupec `testy` "s"; "js" = oba, staci aby shodil jeden]
  * skripty karet (--apply)      -> test_oploceni_karty.py (falesna DB, ~2 s)        [sloupec `testy` "k"]
Kazda mutace dostane vlastni kopii stromu (api/ = symlinky na koren API, jen mutovany soubor je kopie; scripts/ = tahle slozka + symlinky na ostatni; webapp = symlink), test bezi na kopii, 4 paralelne.
Zadna zmena DB, zadny zapis do zive stromu (mimo docasneho adresare). Mutace shop vrstvy potrebuji DB_* v prostredi => spoustet pres systemd-run (viz nize); `--jadro` spusti jen mutace bez DB.
Koren API: `OPLOCENI_API` (vychozi <koren repa>/api; v kandidatovi <kandidat>/api).

  systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --setenv=HOME=/root --working-directory=<koren repa> \\
      /opt/konfigurator/api/venv/bin/python3 <koren repa>/scripts/2026-10-08_oploceni/mutace_oploceni.py [--jadro | --shop] [nazev_mutace ...]      (bez argumentu vsechny)
  api/venv/bin/python3 scripts/2026-10-08_oploceni/mutace_oploceni.py --kotvy                  (jen overi, ze kazda kotva se v souboru najde prave jednou; bez DB)"""
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
API_ROOT = os.environ.get("OPLOCENI_API") or os.path.join(REPO, "api")
PY = os.path.join(REPO, "api", "venv", "bin", "python3")
K = "oploceni_konfigurator.py"
G = "oploceni_glb.py"
C = "oploceni_cena.py"
S = "oploceni_shop.py"
R = "konfigurator_registr.py"
H = "stul_shop.py"
KK = "konfigurace_kosik.py"
NZ = "nabidka_z_konfigurace.py"
ZKO = "zaloz_kartu_oploceni.py"                 # skripty karet jsou ve slozce scripts/2026-10-08_oploceni (ne v api/)
ZKV = "zaloz_karty_vyplni.py"
TESTY_PODLE_SOUBORU = {K: "j", G: "j", C: "j", S: "s", R: "s", H: "s", KK: "s", NZ: "s", ZKO: "k", ZKV: "k"}
TEST_SOUBOR = {"j": "test_oploceni.py", "s": "test_oploceni_shop.py", "k": "test_oploceni_karty.py"}
VE_SLOZCE_SCRIPTU = (ZKO, ZKV)


def _zdroj(soubor):
    """Cesta k puvodnimu souboru mutace (api/ nebo slozka scriptu)."""
    return os.path.join(HERE if soubor in VE_SLOZCE_SCRIPTU else API_ROOT, soubor)


def _v_kopii(d, soubor):
    return os.path.join(d, "scripts", "2026-10-08_oploceni", soubor) if soubor in VE_SLOZCE_SCRIPTU else os.path.join(d, "api", soubor)

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
    ("n20_hloubka_nekanonizuje", K, 'if existuji and (existuji <= {"celo"} or existuji <= {"zadni"}):', "if False:"),
    ("n21_sirka_nekanonizuje", K, 'if existuji and (existuji <= {"prava"} or existuji <= {"leva"}):', "if False:"),
    ("n23_patky_minimalni_vyska", K, "if H - y0 < 1000.0 - 1e-9:", "if False:"),
    ("n24_zamek_nekanonizuje", K, 'VYCHOZI["dvere_zavesy"], VYCHOZI["zamek"])', 'VYCHOZI["dvere_zavesy"], p["zamek"])'),
    ("n25_dvere_vyska_nekanonizuje", K, 'VYCHOZI["dvere_sirka"], None, VYCHOZI["dvere_poloha"]', 'VYCHOZI["dvere_sirka"], p["dvere_vyska"], VYCHOZI["dvere_poloha"]'),
    ("n26_zaokrouhleni_rozmeru", K, "    return round(x, 1)\n", "    return round(x, 0)\n"),
    ("n22_kanonizace_prilis_siroka", K, 'if existuji and (existuji <= {"celo"} or existuji <= {"zadni"}):', "if existuji and len(existuji) <= 2:"),
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
    ("g10_otevreni_bez_dilu_kridla", G, 'if (_je_kridlo(dil) and dil.get("strana") in osy) else None', "if False else None"),
    ("g11_material_zaslepek", G, 'O.ZASLEPKA: "cerna"', 'O.ZASLEPKA: "ocel"'),
    ("g12_material_spojek", G, 'O.SPOJKA: "ocel"', 'O.SPOJKA: "alu"'),
    ("g13_sit_bez_textury", G, '"blend": True, "tex": "sit",', '"blend": True,'),
    ("g14_sit_bez_uv", G, "uv = np.stack([P @ e1, P @ e2], axis=1) / SIT_ROZTEC if", "uv = None if True or"),
    ("g15_cache_neomezena_klic", G, '    klic = (h, bool(razitka))', '    klic = ("x", bool(razitka))'),
    ("g16_prvni_hash", G, "return h, glb", "return h + \"x\", glb"),
    # ---- cena ----
    ("c01_vypln_neni_deska", C, '"is_board_material": True,', '"is_board_material": False,'),
    ("c02_cena_vyplne_polovicni", C, '"price_czk": info["cena_m2"],', '"price_czk": info["cena_m2"] / 2,'),
    ("c03_spojovaci_material_po_jednom", C, 'entries.extend({"product_id": pid} for _ in range(m["mnozstvi"]))', 'entries.extend({"product_id": pid} for _ in range(1))'),
    ("c04_chybejici_se_neohlasi", C, "            chybejici.append(m)\n", "            pass\n"),
    ("c05_bez_extra_prace", C, 'out = CP.price_entries(entries, ctx2, montaz_pct=montaz_pct, extra_work=extra)', 'out = CP.price_entries(entries, ctx2, montaz_pct=montaz_pct, extra_work=None)'),
    ("c06_doplnky_bez_koeficientu", C, 'CP.apply_scene_coefficient(nove, ctx["pricing"].get("scene_price_coefficient", 1.0))', "pass"),
    ("c07_doplnky_koeficient_vsem", C, '"scene_coef": bool(r.get("is_profile_material")) or bool(r.get("dogus_url")),', '"scene_coef": True,'),
    ("c07b_doplnky_koeficient_nikomu", C, '"scene_coef": bool(r.get("is_profile_material")) or bool(r.get("dogus_url")),', '"scene_coef": False,'),
    ("c08_doplnky_prepis_existujici", C, '        if part_id in ctx["parts"]:\n            continue\n', "        pass\n"),
    ("c09_doplnky_jednotka", C, '"unit": (r.get("unit") or "").strip().lower() or None', '"unit": r.get("unit")'),
    ("c10_doplnky_hmotnost", C, 'float(r["weight_g"]) / 1000 if r["weight_g"] is not None else None', 'float(r["weight_g"]) if r["weight_g"] is not None else None'),
    ("c11_doplnky_neptat_se_na_sku", C, '" OR sku IN (" + ",".join(["%s"] * len(DOPLNKOVE_SKU)) + ")", tuple(DOPLNKOVE_KARTY) + tuple(DOPLNKOVE_SKU))', '"", tuple(DOPLNKOVE_KARTY))'),
    # ================================================= FAZE 2 - jadro: dvere a hmotnost =================================================
    ("k01_dvere_sirka_svetlost", K, "S0 = L - 2 * PROFIL", "S0 = L - PROFIL"),
    ("k02_dvere_rezerva_zavesy", K, '(2 * (PROFIL + POLE_MIN) if poloha == "stred" else (PROFIL + POLE_MIN))', '(2 * (PROFIL + POLE_MIN) if poloha == "stred" else 0)'),
    ("k03_dvere_rezerva_stred", K, '(2 * (PROFIL + POLE_MIN) if poloha == "stred" else (PROFIL + POLE_MIN))', '((PROFIL + POLE_MIN) if poloha == "stred" else (PROFIL + POLE_MIN))'),
    ("k04_dvere_sirka_hranice", K, 'return float(m) if m >= ROZSAH["dvere_sirka"][0] - 1e-9 else None', 'return float(m) if m > ROZSAH["dvere_sirka"][0] else None'),
    ("k05_dvere_vyska_bez_nadprazi", K, "- NADPRAZ_MIN - (y0 + DVERE_NAD_PODLAHOU)", "- (y0 + DVERE_NAD_PODLAHOU)"),
    ("k06_dvere_vyska_bez_patek", K, '    y0 = PATKA_VYSKA if p["patky"] else 0.0\n    return p["vyska"] - PROFIL', '    y0 = 0.0\n    return p["vyska"] - PROFIL'),
    ("k07_dvere_min_vyska_bez_patek", K, '+ NADPRAZ_MIN + y0 + DVERE_NAD_PODLAHOU}', '+ NADPRAZ_MIN + DVERE_NAD_PODLAHOU}'),
    ("k08_dvere_min_delka", K, '+ 2 * MEZERA_DVERE + PROFIL + POLE_MIN + 2 * PROFIL}', '+ 2 * MEZERA_DVERE + PROFIL + POLE_MIN + PROFIL}'),
    ("k09_dvere_strana_stred", K, 'if dvere_sirka_max(L, "vpravo") is None:', 'if dvere_sirka_max(L, "stred") is None:'),
    ("k10_dvere_vyska_hranice", K, 'if vyska_dveri_max(p) < ROZSAH["dvere_vyska"][0] - 1e-9:\n        y0', 'if vyska_dveri_max(p) <= ROZSAH["dvere_vyska"][0]:\n        y0'),
    ("k11_delka_strany_prohozena", K, 'return p["sirka"] if s in ("celo", "zadni") else p["hloubka"]', 'return p["hloubka"] if s in ("celo", "zadni") else p["sirka"]'),
    ("k12_hmotnost_plocha", K, 'plocha_m2 = sum(k["e1"] * k["e2"] for k in v["kusy"]) / 1e6', 'plocha_m2 = sum(k["e1"] * k["e2"] for k in v["kusy"]) / 1e5'),
    ("k13_hmotnost_bez_tesneni", K, 'kg += float(t["mnozstvi"]) * TESNENI_KARTY[t["part_id"]]["kg_m"]', 'kg += 0.0'),
    ("k14_hmotnost_zaokrouhleni", K, "return round(kg, 3)\n", "return round(kg, 0)\n"),
    ("k15_hmotnost_kg_m2_pc", K, '"cena_m2": 1150.0, "kg_m2": 4.8', '"cena_m2": 1150.0, "kg_m2": 5.8'),
    ("k16_hmotnost_kg_m_tesneni", K, '"cena_m": 32.0, "kg_m": 0.082', '"cena_m": 32.0, "kg_m": 0.82'),
    # ================================================= FAZE 2 - 3D model: zjednoduseni, koty, rezimy =================================================
    ("gz01_bez_zjednoduseni", G, "ZJEDNODUSIT = {O.PATKA: 0.8, O.ZAMEK: 1.6}", "ZJEDNODUSIT = {}", "s"),
    ("gz02_zjednoduseni_prilis_hrube", G, "ZJEDNODUSIT = {O.PATKA: 0.8, O.ZAMEK: 1.6}", "ZJEDNODUSIT = {O.PATKA: 12.0, O.ZAMEK: 24.0}", "s"),
    ("gz03_rezimy_prohozene", G, "glb = sestav_glb(r, jednoduche=not razitka, textury=not razitka)", "glb = sestav_glb(r, jednoduche=razitka, textury=not razitka)", "s"),
    ("gz04_textura_v_nabidce", G, "glb = sestav_glb(r, jednoduche=not razitka, textury=not razitka)", "glb = sestav_glb(r, jednoduche=not razitka, textury=True)", "s"),
    ("gz05_cache_bez_rezimu", G, "    klic = (h, bool(razitka))", "    klic = (h, False)", "s"),
    ("gz06_strop_dilu_vypnuty", G, "if max_dilu is not None and len(r[\"dily\"]) > max_dilu:", "if False:", "s"),
    ("gz07_koty_odstup", G, "KOTY_ODSTUP = 120.0", "KOTY_ODSTUP = 0.0", "s"),
    ("gz08_koty_hloubka_vzdy", G, 'if rel["hloubka"] and z1 - z0 > 100.0:', "if True:", "s"),
    ("gz09_koty_sirka_vzdy", G, 'if rel["sirka"]:\n        out.append(kota((x0, y_dol, z1)', 'if True:\n        out.append(kota((x0, y_dol, z1)', "s"),
    ("gz10_zjednoduseni_shluk_prumer", G, "    npos /= cnt[:, None]\n", "", "s"),
    ("gz11_zjednoduseni_duplicity", G, "    t = t[np.sort(prvni)]\n", "", "s"),
    ("gz12_zjednoduseni_deg_trojuhelniky", G, "    t = t[(t[:, 0] != t[:, 1]) & (t[:, 1] != t[:, 2]) & (t[:, 0] != t[:, 2])]\n", "", "s"),
    ("gz13_zjednoduseni_cache_klic", G, "klic = (part_id, ZJEDNODUSIT[part_id])", "klic = (part_id, 0)", "s"),
    ("gz14_zjednoduseni_vsechny_dily", G, "if jednoduche and part_id in ZJEDNODUSIT:", "if jednoduche:", "s"),
    ("gz15_sit_pbr_bez_textury", G, '"pbr_bez": {"baseColorFactor": [0.40, 0.42, 0.45, 0.50]', '"pbr_bez": {"baseColorFactor": [0.40, 0.42, 0.45, 1.00]', "s"),
    # ================================================= FAZE 2 - cena: karty vyplni =================================================
    ("cz01_karty_vyplni_bool", C, "isinstance(v, int) and not isinstance(v, bool) and v > 0", "isinstance(v, int) and v > 0", "j"),
    ("cz02_karty_vyplni_nula", C, "isinstance(v, int) and not isinstance(v, bool) and v > 0", "isinstance(v, int) and not isinstance(v, bool)", "j"),
    ("cz03_karty_vyplni_neznamy_typ", C, "if t in O.VYPLNE and isinstance(v, int)", "if isinstance(v, int)", "j"),
    ("cz04_karty_vyplni_chyba_nepolknuta", C, "    except Exception:                                                   # noqa: BLE001 - nastaveni je doplnek, cena se vzdy spocita (virtualni desky)\n        return {}\n", "    except KeyError:\n        return {}\n", "j"),
    ("cz05_karty_vyplni_neslovnik", C, "    if not isinstance(d, dict):\n        return {}\n", "", "j"),
    ("cz06_kontext_karta_neni_deska", C, 'and ctx["parts"][f"product_{i}"].get("is_board_material")}', "}", "j"),
    ("cz07_kontext_karta_chybi_v_ctx", C, 'if f"product_{i}" in ctx["parts"] and ', "if ", "j"),
    ("cz08_kontext_sdileny_base", C, '    ctx["parts"] = dict(base["parts"])\n    doplnky_ctx(cur, ctx)', '    ctx["parts"] = base["parts"]\n    doplnky_ctx(cur, ctx)', "j"),
    ("cz09_kontext_bez_karet", C, '    ctx["karty_vyplni"] = {t: i for t, i in karty_vyplni(cur).items()', '    ctx["karty_vyplni"] = {t: i for t, i in {}.items()', "j"),
    ("cz10_cena_bez_prepnuti_na_kartu", C, '        if pid.startswith("navrh:") and pid[len("navrh:"):] in karty:\n            e = dict(e, product_id=f"product_{karty[pid[len(\'navrh:\'):]]}")\n', "", "j"),
    ("cz11_cena_prepnuti_vsechno", C, 'if pid.startswith("navrh:") and pid[len("navrh:"):] in karty:', 'if pid.startswith("navrh:"):', "j"),
    ("cz12_tesneni_obvod", C, "metry[pid] = metry.get(pid, 0.0) + 2.0 * (v[\"w\"] + v[\"h\"]) / 1000.0", "metry[pid] = metry.get(pid, 0.0) + (v[\"w\"] + v[\"h\"]) / 1000.0", "j"),
    ("cz13_tesneni_kolize_typu", C, 'metry[pid] = metry.get(pid, 0.0) + 2.0', 'metry[pid] = 2.0', "j"),
    ("cz14_tesneni_zaokrouhleni", C, '"qty": round(m, 3)', '"qty": round(m, 0)', "j"),
    ("cz15_vyplne_typy_ignorovano", C, "    if vyplne_typy is not None:\n        pole = ", "    if False:\n        pole = ", "s"),
    ("cz16_vyplne_typy_tesneni_stare", C, "        extra = tesneni_extra(r[\"vyplne\"], vyplne_typy)\n", "", "s"),
    ("cz17_virtualni_karta_bez_kontroly", C, "        if typ in karty:\n            continue\n", "", "j"),
    # ================================================= FAZE 2 - shop vrstva: konstanty a mapovani =================================================
    ("s01_strop_dilu_vypnuty", S, "MAX_DILU_MODEL = 600", "MAX_DILU_MODEL = 100000"),
    ("s02_strop_dilu_nizky", S, "MAX_DILU_MODEL = 600", "MAX_DILU_MODEL = 300"),
    ("s03_mez_w_max", S, '"w": (600, 4000, 10)', '"w": (600, 4100, 10)'),
    ("s04_mez_w_min", S, '"w": (600, 4000, 10)', '"w": (500, 4000, 10)'),
    ("s05_mez_d_krok", S, '"d": (600, 4000, 10)', '"d": (600, 4000, 20)'),
    ("s06_mez_h_max", S, '"h": (1000, 3000, 10)', '"h": (1000, 3200, 10)'),
    ("s07_mez_door_w", S, '"door_w": (600, 1200, 10)', '"door_w": (600, 1250, 10)'),
    ("s08_mez_door_h", S, '"door_h": (1500, 2400, 10)', '"door_h": (1400, 2400, 10)'),
    ("s09_vychozi_poloha_dveri", S, '("door_pos", "right")', '("door_pos", "left")'),
    ("s10_vychozi_vyplne", S, '("fill", "pc_clear")', '("fill", "pc_smoke")'),
    ("s11_recept", S, 'RECEPT = "oploceni_kryt"', 'RECEPT = "oploceni"'),
    ("s12_prefix_tokenu", S, 'PREFIX_TOKENU = "opl."', 'PREFIX_TOKENU = "dop."'),
    ("s13_mapovani_zavesy_prohozene", S, 'ZAVESY = {"left": "vlevo", "right": "vpravo"}', 'ZAVESY = {"left": "vpravo", "right": "vlevo"}'),
    ("s14_mapovani_poloha_prohozena", S, 'POLOHA = {"left": "vlevo", "center": "stred", "right": "vpravo"}', 'POLOHA = {"left": "vpravo", "center": "stred", "right": "vlevo"}'),
    ("s15_mapovani_zamek_prohozen", S, 'ZAMEK = {"latch": "zapadka", "lock": "zamek", "none": "zadny"}', 'ZAMEK = {"latch": "zamek", "lock": "zapadka", "none": "zadny"}'),
    ("s16_mapovani_strany_prohozene", S, 'STRANA_JADRO = {"front": "celo", "right": "prava", "back": "zadni", "left": "leva"}', 'STRANA_JADRO = {"front": "celo", "right": "leva", "back": "zadni", "left": "prava"}'),
    ("s17_mapovani_typ_strany_prohozen", S, 'TYP_STRANY = {"wall": "stena", "door": "dvere", "open": "otevreno"}', 'TYP_STRANY = {"wall": "dvere", "door": "stena", "open": "otevreno"}'),
    ("s18_mapovani_strecha_prohozena", S, 'STRECHA = {"none": "zadna", "frame": "ram", "fill": "vyplne"}', 'STRECHA = {"none": "zadna", "frame": "vyplne", "fill": "ram"}'),
    ("s19_mapovani_vyplne_prohozena", S, 'VYPLN = {"pc_clear": "pc_cira", "pc_smoke": "pc_koura", "acrylic": "plexi", "mesh": "sit", "solid": "plna"}', 'VYPLN = {"pc_clear": "pc_koura", "pc_smoke": "pc_cira", "acrylic": "plexi", "mesh": "sit", "solid": "plna"}'),
    ("s20_mapovani_vyplne_strany", S, '"fill_front": "vyplne_celo", "fill_right": "vyplne_prava"', '"fill_front": "vyplne_prava", "fill_right": "vyplne_celo"'),
    # ================================================= shop vrstva: vstup =================================================
    ("s21_vycet_nehashovatelny", S, "return v if isinstance(v, str) and v in ids else vychozi", "return v if v in ids else vychozi"),
    ("s22_cislo_bool", S, "    if isinstance(v, bool):\n        return vychozi\n", "    if False:\n        return vychozi\n"),
    ("s23_cislo_nekonecno", S, "return int(round(x)) if math.isfinite(x) else vychozi", "return int(round(x))"),
    ("s24_door_h_nesmysl", S, 'else _cislo(dh, None)', 'else _cislo(dh, 2000)'),
    ("s25_feet_retezec", S, 'p["feet"] = bool(f) if isinstance(f, (bool, int)) and f in (True, False, 0, 1) else p["feet"]', 'p["feet"] = bool(f)'),
    ("s26_fill_strany_vychozi", S, 'p[k] = _vycet(sel.get(k), VYPLN, "auto")', 'p[k] = _vycet(sel.get(k), VYPLN, p["fill"])'),
    ("s27_jadro_bez_dvere_vyska", S, '"dvere_vyska": None if p["door_h"] is None else float(p["door_h"])', '"dvere_vyska": None'),
    # ================================================= shop vrstva: uprava vyberu =================================================
    ("s30_meze_bez_orezu", S, "        v = min(hi, max(lo, p[k]))\n        if v != p[k]:\n            upravy.append((\"clamp\"", "        v = p[k]\n        if v != p[k]:\n            upravy.append((\"clamp\""),
    ("s31_patky_vyska_vypnuto", S, 'if p["feet"] and p["h"] < 1000 + O.PATKA_VYSKA:', "if False:"),
    ("s32_patky_vyska_hodnota", S, 'p["h"] = int(1000 + O.PATKA_VYSKA)', 'p["h"] = 1000'),
    ("s33_dvere_vzdy_vejdou", S, "        if ok:\n            dvere.append(s)", "        if True:\n            dvere.append(s)"),
    ("s34_dvere_zustavaji_na_strane", S, '            p[s] = "wall"\n', '            pass\n'),
    ("s35_dvere_poloha_stred", S, 'p["door_pos"] = "right"', 'p["door_pos"] = "left"'),
    ("s36_dvere_sirka_bez_orezu", S, 'w = int(math.floor(min(hi, max(lo, p["door_w"]), m) + 1e-9))', 'w = p["door_w"]'),
    ("s37_dvere_sirka_druh_oznameni", S, 'upravy.append(("door_w" if (m < hi and p["door_w"] > m) else "clamp"', 'upravy.append(("clamp"'),
    ("s38_dvere_vyska_bez_nadprazi", S, 'v = min(hi, dh_max, max(lo, p["door_h"]))', 'v = min(hi, max(lo, p["door_h"]))'),
    ("s39_strecha_vynucena_vypnuta", S, 'if all(p[s] == "open" for s in STRANY) and p["roof"] == "none":', "if False:"),
    ("s40_bez_dveri_neorezane", S, '        p["door_w"] = min(VEREJNE_MEZE["door_w"][1], max(VEREJNE_MEZE["door_w"][0], p["door_w"]))\n', '        pass\n'),
    ("s41_bez_dveri_vyska_neorezana", S, '            p["door_h"] = min(VEREJNE_MEZE["door_h"][1], max(VEREJNE_MEZE["door_h"][0], p["door_h"]))', '            pass'),
    ("s42_oznameni_bez_stitku", S, 'd["label"] = t.get(d["slot"], d["slot"])', 'd["label"] = d["slot"]'),
    ("s43_oznameni_strana_velka", S, 'd["strana"] = t[d["strana"]].split(" (")[0].lower()', 'd["strana"] = t[d["strana"]]'),
    ("s44_oznameni_desetinne", S, "            d[k] = int(round(d[k]))", "            d[k] = float(d[k])"),
    ("s45_oznameni_slot", S, 'return data.get("slot") or {"h_feet": "h"', 'return {"h_feet": "h"'),
    # ================================================= shop vrstva: stavy voleb =================================================
    ("s50_vyska_min_s_patkami", S, 'h_min = VEREJNE_MEZE["h"][0] + (O.PATKA_VYSKA if ef["feet"] else 0)', 'h_min = VEREJNE_MEZE["h"][0]'),
    ("s51_sirka_skryta", S, '    if not rel["sirka"]:\n        opt["w"]["hidden"] = True', '    if False:\n        opt["w"]["hidden"] = True'),
    ("s52_hloubka_skryta", S, '    if not rel["hloubka"]:\n        opt["d"]["hidden"] = True', '    if False:\n        opt["d"]["hidden"] = True'),
    ("s53_dvere_povoleny", S, '"door": {"price_delta": None, "disabled": not ok, "reason": None}}', '"door": {"price_delta": None, "disabled": False, "reason": None}}'),
    ("s54_dvere_duvod", S, "        if not ok:\n            stav[\"door\"][\"reason\"]", "        if False:\n            stav[\"door\"][\"reason\"]"),
    ("s55_strecha_zadna_povolena", S, '"none": {"price_delta": None, "disabled": vse_otevreno,', '"none": {"price_delta": None, "disabled": False,'),
    ("s56_vyplne_rozdil_znamenko", S, '["price_summary"]["total_czk"] - zakl\n        except', '["price_summary"]["total_czk"] + zakl\n        except'),
    ("s57_vyplne_strany_skryte", S, 'opt[k] = {"hidden": True} if jadro[strana_jadro] == "otevreno" else {}', 'opt[k] = {}'),
    ("s58_vyplne_strecha_skryta", S, 'opt["fill_roof"] = {} if jadro["strecha"] == "vyplne" else {"hidden": True}', 'opt["fill_roof"] = {}'),
    ("s59_dvere_sirka_max", S, '"max": int(math.floor(max(VEREJNE_MEZE["door_w"][0], dl)))}', '"max": VEREJNE_MEZE["door_w"][1]}'),
    ("s60_dvere_vyska_hodnota", S, '"value": int(round(r["dvere"][0]["vyska_kridla"])) if r["dvere"] else', '"value": 2000 if r["dvere"] else'),
    ("s61_dvere_vyska_auto", S, '"auto": ef["door_h"] is None}', '"auto": False}'),
    ("s62_dvere_volby_viditelne", S, '    if not jsou_dvere:\n        for k in ("door_w", "door_h", "door_pos", "door_hinge", "lock"):', '    if False:\n        for k in ("door_w", "door_h", "door_pos", "door_hinge", "lock"):'),
    ("s63_patky_bez_rozdilu_ceny", S, 'opt["feet"] = {"on": {"price_delta": dp if not jadro["patky"] else None,', 'opt["feet"] = {"on": {"price_delta": None,'),
    ("s64_patky_rozdil_bez_vysky", S, '            alt["vyska"] = max(alt["vyska"], 1000.0 + O.PATKA_VYSKA)', '            pass'),
    ("s65_vyplne_rozdil_strana_prepis", S, 'else v["typ"] for v in r["vyplne"]]', 'else typ_alt for v in r["vyplne"]]'),
    # ================================================= shop vrstva: resolve, cena, objednavka =================================================
    ("s70_chybejici_cena_ignorovana", S, '    if cena_r["warnings"]:', "    if False:"),
    ("s71_cena_s_dph", S, '"gross": round(net * (1 + stul_api.SAZBA_DPH / 100.0)), "currency": "CZK"}', '"gross": net, "currency": "CZK"}'),
    ("s72_cena_zaokrouhleni", S, '        net = int(sum_["total_czk"])\n        out["price"]', '        net = int(sum_["total_czk"]) + 1\n        out["price"]'),
    ("s73_hloubka_vzdy", S, '"depth_mm": int(round(r["rozmery"]["hloubka_mm"])) if rel["hloubka"] else None', '"depth_mm": int(round(r["rozmery"]["hloubka_mm"]))'),
    ("s74_kod_delka", S, '"kod": "OPL-" + h[:6].upper()', '"kod": "OPL-" + h[:8].upper()'),
    ("s75_info_upozorneni_chybi", S, '    out["notices"] = notices + _info_upozorneni(r, lang)', '    out["notices"] = notices'),
    ("s76_hash_bez_verze", S, '{"p": jadro, "v": RULES_VERSION}', '{"p": jadro}'),
    ("s77_cache_bez_jazyka", S, "klic = (json.dumps(p0, sort_keys=True), lang, RULES_VERSION)", "klic = (json.dumps(p0, sort_keys=True), RULES_VERSION)"),
    ("s78_cache_sdilena_kopie", S, "    out, jadro, r = _resolve_data(selection, lang)[:3]\n    out = copy.deepcopy(out)", "    out, jadro, r = _resolve_data(selection, lang)[:3]"),
    ("s79_model_strop_vypnuty", S, 'if r is not None and len(r["dily"]) > MAX_DILU_MODEL:', "if False:"),
    ("s80_skryt_cenu", S, "return _bez_ceny(out) if skryt_cenu else out", "return out"),
    ("s81_bez_ceny_delty", S, '                st.pop("price_delta", None)', "                pass"),
    ("s82_model_odkaz", S, '"odhad_ms": 0}\n    return _bez_ceny', '"odhad_ms": 0, "kod": "x"}\n    return _bez_ceny'),
    # ================================================= shop vrstva: blok pro zamestnance =================================================
    ("s90_staff_cena_s_dph", S, "    s_dph = round(net * (1 + stul_api.SAZBA_DPH / 100.0))", "    s_dph = net"),
    ("s91_staff_hmotnost", S, '    kus["hmotnost_kg"] = kg', '    kus["hmotnost_kg"] = 0'),
    ("s92_staff_varovani", S, "+ [u[\"text\"] for u in r[\"upozorneni\"]] +", "+ [] +"),
    ("s93_staff_spoje", S, '"pocet_spoju": r["pocet_spoju"], "hash": out["hash"]', '"pocet_spoju": 0, "hash": out["hash"]'),
    ("s94_staff_dily", S, '"dilu": len(r["dily"])}', '"dilu": 0}'),
    ("s95_staff_montaz", S, '"poznamka": "u tohoto produktu se nenabízí"}', '"poznamka": "x"}'),
    # ================================================= shop vrstva: objednavka =================================================
    ("s100_rules_changed_vypnuto", S, "    if rules_version is not None and str(rules_version) != RULES_VERSION:\n        return {\"ok\": False", "    if False:\n        return {\"ok\": False"),
    ("s101_objednavka_hmotnost", S, '    souhrn_cen["weight_kg"] = kg', "    pass"),
    ("s102_objednavka_rozmery_text", S, "rozmery_text=_rozmery_text(r))", "rozmery_text=None)"),
    ("s103_rozmery_text_vsechny", S, 'casti = ([p["sirka"]] if rel["sirka"] else []) + ([p["hloubka"]] if rel["hloubka"] else []) + [p["vyska"]]', 'casti = [p["sirka"], p["hloubka"], p["vyska"]]'),
    ("s104_bom_delky_pocet", S, 'delky[x["delka_mm"]] = delky.get(x["delka_mm"], 0) + x["ks"]', 'delky[x["delka_mm"]] = delky.get(x["delka_mm"], 0) + 1'),
    ("s105_bom_tesneni_zaokrouhleni", S, '"mnozstvi": round(x["mnozstvi"], 2), "rozmer": "m"}', '"mnozstvi": round(x["mnozstvi"], 0), "rozmer": "m"}'),
    ("s106_bom_vyplne_rozmer", S, 'x[\'sirka_mm\']:.0f} × {x[\'vyska_mm\']:.0f} mm"', 'x[\'vyska_mm\']:.0f} × {x[\'sirka_mm\']:.0f} mm"'),
    ("s107_hmotnost_bez_vyplni", S, "+ O.hmotnost_vyplni_kg(r)", "+ 0.0"),
    ("s108_souhrn_dvere_vzdy", S, '    if any(ef[s] == "door" for s in STRANY):\n        out.append', '    if True:\n        out.append'),
    ("s109_souhrn_patky_vzdy", S, '    if ef["feet"]:\n        out.append({"id": "feet"', '    if True:\n        out.append({"id": "feet"'),
    ("s110_souhrn_strany_vyplne_vzdy", S, '        if ef[k] != "auto":\n            out.append', '        if True:\n            out.append'),
    ("s111_glb_bytes_razitka", S, "OG.model_pro_parametry(jadro, razitka=razitka, max_dilu=MAX_DILU_MODEL)[1]", "OG.model_pro_parametry(jadro, razitka=False, max_dilu=MAX_DILU_MODEL)[1]"),
    ("s112_glb_bytes_bez_upravy", S, "    _p, jadro, _u = _uprav(_zaklad(selection))\n    return OG", "    jadro = O.normalizuj(**_na_jadro(_zaklad(selection)))\n    return OG"),
    # ================================================= shop vrstva: token, routy =================================================
    ("s120_token_platnost", S, "MODEL_PLATNOST_S = 15 * 60", "MODEL_PLATNOST_S = 150 * 60"),
    ("s121_token_neprosel", S, "        if (ted or time.time()) > int(exp):", "        if False:"),
    ("s122_token_podpis", S, "        if not hmac.compare_digest(spravny, _unb64(sig)):", "        if False:"),
    ("s123_token_prefix", S, "        if not token.startswith(PREFIX_TOKENU):", "        if False:"),
    ("s124_rules_409", S, '    if body.get("rules_version") and body.get("rules_version") != RULES_VERSION:', "    if False:"),
    ("s125_staff_bez_kontroly", S, "            if stul_shop._je_staff():", "            if True:"),
    ("s126_staff_bez_priznaku", S, '        if body.get("staff"):', "        if True:"),
    ("s127_model_neznamy_hash", S, "    if p is None:\n        return _nenalezeno()\n    return jsonify({\"model\"", "    if False:\n        return _nenalezeno()\n    return jsonify({\"model\""),
    ("s128_glb_vyprsel", S, '410 if chyba == "vyprsel" else 403', "403"),
    ("s129_glb_prilis_velky", S, '(413 if e.kod == "prilis_velky" else 400)', "400"),
    ("s130_glb_cache_verejna", S, 'resp.headers["Cache-Control"] = "private, max-age=600"', 'resp.headers["Cache-Control"] = "public, max-age=600"'),
    ("s131_glb_robots", S, '    resp.headers["X-Robots-Tag"] = "noindex"\n', ""),
    ("s132_glb_vary", S, '    resp.headers["Vary"] = "Accept-Encoding"\n', ""),
    ("s133_glb_verejny_plny_detail", S, "h, data = OG.model_pro_parametry(p, razitka=False, max_dilu=MAX_DILU_MODEL)", "h, data = OG.model_pro_parametry(p, razitka=True, max_dilu=MAX_DILU_MODEL)"),
    ("s134_schema_systemy", S, '    out["systems"] = []\n', ""),
    ("s135_schema_recept", S, '        "recipe": RECEPT,\n', ""),
    ("s136_schema_vychozi", S, '        "default_selection": vychozi_vyber(),', '        "default_selection": {},'),
    ("s137_schema_skupiny", S, 'for g in ("g_size", "g_sides", "g_fill", "g_fill_adv", "g_door", "g_extras")]', 'for g in ("g_size", "g_sides", "g_fill", "g_door", "g_extras")]'),
    ("s138_jazyk_hlavicka", S, '    al = (request.headers.get("Accept-Language") or "").lower()[:2] if request else ""', '    al = ""'),
    # ================================================= registr, routy, kosik, nabidka (zaplaty) =================================================
    ("r01_recept", R, 'RECEPT_OPLOCENI = "oploceni_kryt"', 'RECEPT_OPLOCENI = "oploceni"'),
    ("r02_prefix_tokenu", R, 'PREFIX_TOKENU_OPLOCENI = "opl."', 'PREFIX_TOKENU_OPLOCENI = "dop."'),
    ("r03_bez_montaze_jen_dopravnik", R, "RECEPTY_BEZ_MONTAZE = frozenset(MODULY)", "RECEPTY_BEZ_MONTAZE = frozenset((RECEPT_DOPRAVNIK,))"),
    ("r04_modul_pro_nic", R, "    return modul_receptu(recept_produktu(product_id))", "    return None"),
    ("r05_mimo_stul_jen_oploceni", R, "    return recept_produktu(product_id) in MODULY", "    return recept_produktu(product_id) == RECEPT_OPLOCENI"),
    ("r06_token_bez_modulu", R, "        if str(token).startswith(prefix):", "        if False:"),
    ("r07_hash_prvni_modul", R, 'if m is not None and getattr(m, "zna_hash", None) and m.zna_hash(h):', 'if m is not None and getattr(m, "zna_hash", None):'),
    ("r08_konfigurovatelny_jen_dopravnik", R, "or modul_pro(product_id) is not None", "or dopravnik_pro(product_id) is not None"),
    ("r09_objednavka_jen_dopravnik", R, "    dm = modul_pro(product_id)\n    if dm is not None:\n        return dm.pro_objednavku", "    dm = dopravnik_pro(product_id)\n    if dm is not None:\n        return dm.pro_objednavku"),
    ("r10_glb_jen_dopravnik", R, "    dm = modul_pro(product_id)\n    if dm is not None:\n        return dm.glb_bytes", "    dm = dopravnik_pro(product_id)\n    if dm is not None:\n        return dm.glb_bytes"),
    ("r11_karta_archivovana", R, 'bool(r and r["active"] and not r["is_archived"])', 'bool(r and r["active"])'),
    ("r12_karta_nejvyssi_id", R, "    return ids[0], bool(", "    return ids[-1], bool("),
    ("r13_modul_nenalezen_cache", R, 'if not st["existuje"] and time.time() - st["t"] < 30:', 'if not st["existuje"]:'),
    ("h01_routa_recepty_bez_kontroly", H, '    if not _je_staff():\n        return jsonify({"error": "forbidden"}), 403\n    nalez = konfigurator_registr.produkt_pro_recept(recept)', '    nalez = konfigurator_registr.produkt_pro_recept(recept)'),
    ("h02_routa_recepty_neznamy", H, "    if nalez is None:\n        return _nenalezeno()\n    return jsonify({\"recept\": recept", "    if False:\n        return _nenalezeno()\n    return jsonify({\"recept\": recept"),
    ("h03_routa_recepty_active", H, '"product_id": nalez[0], "active": nalez[1]}', '"product_id": nalez[0], "active": True}'),
    ("h04_schema_jen_dopravnik", H, "    dm = konfigurator_registr.modul_pro(product_id)\n    if dm is not None:\n        return dm.odpoved_schema(product_id)", "    dm = konfigurator_registr.dopravnik_pro(product_id)\n    if dm is not None:\n        return dm.odpoved_schema(product_id)"),
    ("h05_resolve_jen_dopravnik", H, 'dm = konfigurator_registr.modul_pro(body.get("product_id"))', 'dm = konfigurator_registr.dopravnik_pro(body.get("product_id"))'),
    ("h06_model_jen_dopravnik", H, "    dm = konfigurator_registr.modul_pro_hash(h)\n", "    dm = konfigurator_registr.dopravnik_modul()\n"),
    ("h07_glb_jen_dopravnik", H, "    if konfigurator_registr.recept_z_tokenu(token):\n        dm = konfigurator_registr.modul_z_tokenu(token)", "    if token.startswith(konfigurator_registr.PREFIX_TOKENU_DOPRAVNIKU):\n        dm = konfigurator_registr.dopravnik_modul()"),
    ("kk01_montaz_oploceni", KK, "konfigurator_registr.bez_montaze(product_id):", "konfigurator_registr.je_dopravnik(product_id):"),
    ("kk02_nazev_bez_rozmeru_modulu", KK, "rozmery = rozmery_text or ", "rozmery = "),
    ("kk03_vyres_bez_rozmeru", KK, '"rozmery_text": r.get("rozmery_text"),', '"rozmery_text": None,'),
    ("kk04_radek_bez_rozmeru", KK, 'jmeno_radku(product.get("name"), res["selection"], res["kod"], res.get("rozmery_text"))', 'jmeno_radku(product.get("name"), res["selection"], res["kod"])'),
    ("nz01_nabidka_jen_dopravnik", NZ, "dopravnik = konfigurator_registr.mimo_stul(produkt[\"id\"])", "dopravnik = konfigurator_registr.je_dopravnik(produkt[\"id\"])"),
    ("nz02_nabidka_nazev", NZ, 'kk.jmeno_radku(produkt["name"], res["selection"], res["kod"], res.get("rozmery_text"))', 'kk.jmeno_radku(produkt["name"], res["selection"], res["kod"])'),
    # ================================================= skripty karet (test_oploceni_karty.py, falesna DB) =================================================
    ("kz01_karta_aktivni", ZKO, "VALUES (%s,%s,%s,%s,%s,0,%s,%s)", "VALUES (%s,%s,%s,%s,%s,1,%s,%s)"),
    ("kz02_karta_jednotka", ZKO, '(SKU, NAZEV, slug_fn(cur, NAZEV), POPIS, "ks", META_T, META_D))', '(SKU, NAZEV, slug_fn(cur, NAZEV), POPIS, "m2", META_T, META_D))'),
    ("kz03_nastaveni_bez_zamku", ZKO, 'cur.execute("SELECT setting_value FROM app_settings WHERE setting_key=%s FOR UPDATE", (KLIC,))', 'cur.execute("SELECT setting_value FROM app_settings WHERE setting_key=%s", (KLIC,))'),
    ("kz04_nastaveni_cas_rozbity", ZKO, '"UPDATE app_settings SET setting_value=%s WHERE setting_key=%s AND setting_value=%s", (nova, KLIC, puvodni))', '"UPDATE app_settings SET setting_value=%s WHERE setting_key=%s AND setting_value=%s", (nova, KLIC, nova))'),
    ("kz05_nastaveni_rowcount_nekontrolovan", ZKO, '            if cur.rowcount != 1:\n                raise RuntimeError(f"zapis configurator_products', '            if False:\n                raise RuntimeError(f"zapis configurator_products'),
    ("kz06_audit_nastaveni_jina_entita", ZKO, '(None, "update", "app_settings", None, f"bot8: configurator_products', '(None, "update", "app_settings_x", None, f"bot8: configurator_products'),
    ("kz07_bez_rollbacku", ZKO, '        conn.rollback()\n        raise RuntimeError(f"{e} - ROLLBACK, nic se nezapsalo") from e', '        raise RuntimeError(f"{e} - ROLLBACK, nic se nezapsalo") from e'),
    ("kz08_bez_commitu", ZKO, '        conn.commit()\n        return pid', '        return pid'),
    ("kz09_neidempotentni", ZKO, "        if mapa.get(str(pid)) != RECEPT:", "        if True:"),
    ("kz10_vzdy_nova_karta", ZKO, "        if karta is None:\n            cur.execute(\"INSERT INTO shop_products", "        if True:\n            cur.execute(\"INSERT INTO shop_products"),
    ("kz11_smaze_ostatni_recepty", ZKO, "        mapa = json.loads(puvodni) if puvodni else {}\n        if karta is None:", "        mapa = {}\n        if karta is None:"),
    ("kz12_recept", ZKO, 'RECEPT = "oploceni_kryt"', 'RECEPT = "oploceni"'),
    ("kz13_jini_nositele_nehlaseni", ZKO, '    ostatni = {k: v for k, v in mapa.items() if v == RECEPT and (karta is None or str(karta["id"]) != k)}', "    ostatni = {}"),
    ("kz14_overeni_aktivni", ZKO, 'assert k2 and k2["sku"] == SKU and k2["active"] == 0', 'assert k2 and k2["sku"] == SKU and k2["active"] == 1'),
    ("kz15_nahled_zapisuje", ZKO, '    if not apply:\n        print("\\nplan (--apply): "', '    if False:\n        print("\\nplan (--apply): "'),
    ("kz16_apply_bez_slug_fn", ZKO, "    if slug_fn is None:\n        print(\"CHYBA: --apply jen pres systemd-run", "    if False:\n        print(\"CHYBA: --apply jen pres systemd-run"),
    ("kv01_karta_aktivni", ZKV, '("stock_qty", 0), ("active", 0), ("is_archived", 0)', '("stock_qty", 0), ("active", 1), ("is_archived", 0)'),
    ("kv02_neni_deska", ZKV, '("is_board_material", 1), ("board_sheet_width_mm", tw)', '("is_board_material", 0), ("board_sheet_width_mm", tw)'),
    ("kv03_mimo_scenu", ZKV, '("visible_in_scene", 1), ("is_supplier_item", 0)', '("visible_in_scene", 0), ("is_supplier_item", 0)'),
    ("kv04_jednotka_ks", ZKV, '("description", popis), ("unit", "m2"),', '("description", popis), ("unit", "ks"),'),
    ("kv05_cena_format", ZKV, '("price_czk_placeholder", f"{info[\'cena_m2\']:.2f}")', '("price_czk_placeholder", f"{info[\'cena_m2\']:.0f}")'),
    ("kv06_glb_nenastaven", ZKV, '"UPDATE shop_products SET glb_file=%s WHERE id=%s", (f"product_{pid}.glb", pid))', '"UPDATE shop_products SET glb_file=%s WHERE id=%s", (None, pid))'),
    ("kv07_glb_nesmazano", ZKV, "                os.remove(f)\n", "                pass\n"),
    ("kv08_bez_rollbacku", ZKV, "        conn.rollback()\n        for f in vytvorene_soubory:", "        for f in vytvorene_soubory:"),
    ("kv09_existujici_znovu", ZKV, "            if existujici[typ]:\n                nove_karty[typ]", "            if False:\n                nove_karty[typ]"),
    ("kv10_vzor_nekontrolovan", ZKV, 'if not vzor or vzor["sku"] != VZOR_SKU:', "if False:"),
    ("kv11_kategorie_nekontrolovana", ZKV, '            if not cur.fetchone():\n                raise RuntimeError(f"kategorie', '            if False:\n                raise RuntimeError(f"kategorie'),
    ("kv12_kategorie_ignorovana", ZKV, "sl = radek_karty(typ, kategorie, vzor,", "sl = radek_karty(typ, None, vzor,"),
    ("kv13_tloustka_glb", ZKV, 'glb_zapis(glb, float(info["tloustka"]))', "glb_zapis(glb, 1.0)"),
    ("kv14_nastaveni_cas_rozbity", ZKV, '"UPDATE app_settings SET setting_value=%s WHERE setting_key=%s AND setting_value=%s", (nova, KLIC, puvodni))', '"UPDATE app_settings SET setting_value=%s WHERE setting_key=%s AND setting_value=%s", (nova, KLIC, nova))'),
    ("kv15_nastaveni_bez_zamku", ZKV, 'cur.execute("SELECT setting_value FROM app_settings WHERE setting_key=%s FOR UPDATE", (KLIC,))', 'cur.execute("SELECT setting_value FROM app_settings WHERE setting_key=%s", (KLIC,))'),
    ("kv16_audit_nastaveni_jina_entita", ZKV, '(None, "update", "app_settings", None, f"bot8: {KLIC}', '(None, "update", "app_settings_x", None, f"bot8: {KLIC}'),
    ("kv17_overeni_kontext", ZKV, 'assert f"product_{pid}" in ctx["parts"] and ctx["parts"][f"product_{pid}"].get("is_board_material"), f"karta #{pid} neni v cenovem kontextu"', "pass"),
    ("kv18_overeni_soubor", ZKV, 'assert os.path.isfile(os.path.join(katalog, k["glb_file"])), k["glb_file"]', "pass"),
    ("kv19_dalsi_id", ZKV, 'dalsi = int(cur.fetchone()["a"])', 'dalsi = int(cur.fetchone()["a"]) + 1'),
    ("kv20_existujici_podle_nazvu", ZKV, 'existujici[typ] = [r for r in ex if r["sku"] == info["sku"]]', "existujici[typ] = ex"),
    ("kv21_mapovani_nezapsano", ZKV, "        if nove_mapovani != mapovani:", "        if False:"),
    ("kv22_insert_rowcount_nekontrolovan", ZKV, '            if cur.rowcount != 1:\n                raise RuntimeError(f"INSERT karty', '            if False:\n                raise RuntimeError(f"INSERT karty'),
    ("kv23_nahled_zapisuje", ZKV, '    if not apply:\n        print("\\n(nahled, nic nezapsano', '    if False:\n        print("\\n(nahled, nic nezapsano'),
    ("kv24_bez_commitu", ZKV, "        conn.commit()\n        return nove_karty", "        return nove_karty"),
]


def _testy(m):
    return m[4] if len(m) > 4 else TESTY_PODLE_SOUBORU[m[1]]


def _kopie():
    d = tempfile.mkdtemp(prefix="mut_oploceni_")
    os.makedirs(os.path.join(d, "scripts", "2026-10-08_oploceni"))
    os.makedirs(os.path.join(d, "api"))
    for f in glob.glob(os.path.join(HERE, "*")):
        if os.path.isfile(f):
            shutil.copy(f, os.path.join(d, "scripts", "2026-10-08_oploceni", os.path.basename(f)))
    for f in os.listdir(os.path.join(REPO, "scripts")):                    # zbytek scripts/ (moduly, ktere importuje app.py, napr. razitkovac) jako symlinky; kopie teto slozky je jen jedna
        if f != "2026-10-08_oploceni":
            os.symlink(os.path.join(REPO, "scripts", f), os.path.join(d, "scripts", f))
    for f in os.listdir(API_ROOT):
        if f != "__pycache__":                                             # bytecode by se pres symlink zapsal do puvodniho api/
            os.symlink(os.path.join(API_ROOT, f), os.path.join(d, "api", f))
    os.symlink(os.path.join(REPO, "webapp"), os.path.join(d, "webapp"))
    for f in os.listdir(REPO):                                             # ostatni koren repa (docs, MD pravidla ...) pro testy, ktere z nej ctou
        if f not in ("api", "webapp", "scripts") and not os.path.exists(os.path.join(d, f)):
            os.symlink(os.path.join(REPO, f), os.path.join(d, f))
    return d


def _spust_test(d, test):
    p = subprocess.run([PY, os.path.join(d, "scripts", "2026-10-08_oploceni", TEST_SOUBOR[test])], capture_output=True, text=True, timeout=1500, cwd=d,
                       env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "OPLOCENI_API": os.path.join(d, "api"), "OPLOCENI_STOP_PRVNI": "1"})
    return p, p.stdout.count("CHYBA") + p.stdout.count("FAIL ")


def spust(m):
    nazev, soubor, puvodni, nahrada = m[:4]
    testy = _testy(m)
    d = _kopie()
    try:
        cil = _v_kopii(d, soubor)
        s = open(os.path.realpath(cil), encoding="utf-8").read()
        if s.count(puvodni) != 1:
            return nazev, "KOTVA", f"puvodni text se v {soubor} nenasel prave jednou ({s.count(puvodni)}x)"
        os.remove(cil)                                                     # symlink -> skutecna kopie (zive soubory se nemeni)
        open(cil, "w", encoding="utf-8").write(s.replace(puvodni, nahrada))
        try:
            py_compile.compile(cil, cfile=os.path.join(d, "x.pyc"), doraise=True)
        except py_compile.PyCompileError as e:
            return nazev, "NEPLATNA", str(e)[:200]
        poznamky = []
        for t in testy:
            p, n_chyb = _spust_test(d, t)
            if p.returncode != 0 and n_chyb:
                return nazev, "CHYCENA", f"{TEST_SOUBOR[t]}: {n_chyb} selhani"
            if p.returncode != 0:
                posledni = (p.stderr.strip().splitlines() or ["?"])[-1][:160]
                if posledni.startswith(("ModuleNotFoundError", "ImportError", "FileNotFoundError", "PermissionError", "OSError")):
                    return nazev, "PROSTREDI", posledni                    # chyba prostredi mutacniho behu, ne dukaz, ze test mutaci chyta
                return nazev, "CHYCENA", f"{TEST_SOUBOR[t]}: vyjimka: " + posledni
            poznamky.append(TEST_SOUBOR[t])
        return nazev, "PREZILA", "prosly: " + ", ".join(poznamky)
    finally:
        shutil.rmtree(d, ignore_errors=True)


def over_kotvy():
    zle = 0
    for m in MUTACE:
        nazev, soubor, puvodni, nahrada = m[:4]
        if soubor not in TESTY_PODLE_SOUBORU:
            zle += 1
            print(f"KOTVA {nazev}: neznamy soubor {soubor}")
            continue
        s = open(_zdroj(soubor), encoding="utf-8").read()
        n = s.count(puvodni)
        if n != 1:
            zle += 1
            print(f"KOTVA {nazev}: {n}x v {soubor}")
        if puvodni == nahrada:
            zle += 1
            print(f"KOTVA {nazev}: nahrada je shodna s puvodnim textem")
        if not set(_testy(m)) <= set(TEST_SOUBOR):
            zle += 1
            print(f"KOTVA {nazev}: neznamy test {_testy(m)}")
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
    vyber = [m for m in MUTACE if (not args or m[0] in args) and ("--jadro" not in sys.argv or "s" not in _testy(m)) and ("--shop" not in sys.argv or "s" in _testy(m))]
    if not vyber:
        print("zadna mutace nevybrana")
        sys.exit(2)
    if any("s" in _testy(m) for m in vyber) and not os.environ.get("DB_HOST"):
        print("CHYBA: mutace shop vrstvy potrebuji DB_* v prostredi - spust pres systemd-run --property=EnvironmentFile=api/.env (nebo --jadro)")
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
