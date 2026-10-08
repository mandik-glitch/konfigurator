#!/usr/bin/env python3
"""Mutacni kontrola testu HORNI POLICE (bot8, fork 3, 2026-10-07; 2. kolo 2026-10-08 + sikma): test_hpolice.py, test_hpolice_shop.py a test_hpolice_sikma.py musi chytit kazdou zamerne vnesenou chybu v kandidatovi (api/stul_hpolice.py,
stul_konfigurator.py, stul_shop.py, stul_glb.py, stul_sse.py, stul_ovladani_verejne.py po zaplatach). Mutace se NEDELAJI v zivem stromu ani v kandidatovi: pro kazdou se postavi docasny koren
(api = symlinky na adresar kandidata, jen mutovany soubor je kopie; webapp = webapp kandidata, tj. s GLB desky 12 mm) a test se pusti nad nim pres STUL_API_OVERRIDE. Mutace je "chycena", kdyz
test skonci nenulovym kodem (testy se mutaci zastavuji na prvni chybe: HPOL_PRVNI_CHYBA=1).

Priprava kandidata:  bash scripts/2026-10-07_police_stojky/prepare_cand.sh <slozka kandidata>
Spusteni (z korene repa, jako root):
  STUL_KANDIDAT=<slozka kandidata> api/venv/bin/python3 scripts/2026-10-07_police_stojky/mutace_hpolice.py [m01 s03 ...] [-j 2]
Vystup: radek na mutaci (CHYCENA + co selhalo / NECHYCENA) a souhrn; konci kodem 0 jen kdyz jsou chycene VSECHNY. `--kotvy` jen overi, ze se kazdy vzor v souboru vyskytuje prave jednou."""
import concurrent.futures
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
KANDIDAT = os.environ.get("STUL_KANDIDAT")
if not KANDIDAT:
    sys.exit("CHYBA: nastav STUL_KANDIDAT=<slozka kandidata z prepare_cand.sh>")
ZDROJ = os.path.join(KANDIDAT, "api")
PY = os.path.join(REPO, "api", "venv", "bin", "python3")
ENV_SOUBOR = next((c for c in (os.path.join(REPO, "api", ".env"), "/opt/konfigurator/api/.env") if os.path.exists(c)), None)      # DB prihlaseni pro shop test (kandidat ho nemusi mit: dotfile se globem `*` nelinkuje)
if ENV_SOUBOR is None:
    sys.exit("CHYBA: nenalezen api/.env (shop test potrebuje DB_* pres systemd-run --property=EnvironmentFile=...)")
TEST_CORE = os.path.join(KANDIDAT, "repo", "scripts", "2026-10-07_police_stojky", "test_hpolice.py")
TEST_SHOP = os.path.join(KANDIDAT, "repo", "scripts", "2026-10-07_police_stojky", "test_hpolice_shop.py")
TEST_SIKMA = os.path.join(KANDIDAT, "repo", "scripts", "2026-10-07_police_stojky", "test_hpolice_sikma.py")
PORADI_TESTU = {"core": ("core", "sikma", "shop"), "shop": ("shop", "core", "sikma"), "sikma": ("sikma", "core", "shop")}       # prvni test je "vlastni"; kdyz mutaci nechyti, zkusi se i ostatni (chycena = selhal ktery koli)
# mutace, ktere NENI mozne chytit zadnym testem, protoze nemenji chovani (ekvivalentni) - zdovodneni (zapis do zaverecne zpravy)
EKVIVALENTNI = {
    "x36": "sikma_rel: clen lip_top v `high` je jen pojistka - pres vsechny dosazitelne kombinace (systemy 30 / 35 / 40 / 45 x laminodeska 18 / 12 mm x hloubka 150-600 x sklon 5-30) je `high - lip_top` aspon 29 mm (nejvyssi bod urcuje konzola nebo zadni roh desky), horni okraj lemu strop nikdy neurcuje",
    "k05": "_oznac_desky: vetev `or c.get(\"deska_id\")` je jen pojistka - klic desky police (\"hpol\", ...) nesplnuje zadnou z podminek, ktere deska_id prirazuji (\"t\" / \"kus\" / \"kusp\" / \"polic\" / \"polvyr\"), takze se deska_id neprepise ani bez ni",
}
HP, K, SH, GL, SS, OV = "stul_hpolice.py", "stul_konfigurator.py", "stul_shop.py", "stul_glb.py", "stul_sse.py", "stul_ovladani_verejne.py"

# (id, popis, soubor, [(puvodni, nove), ...], test)
MUTACE = [
    # ---- geometrie a pravidla modulu stul_hpolice.py
    ("m01", "automaticka vyska: mezera nad panely 25 misto 60 mm", HP, [("MEZERA_NAD_PANELY = 60.0 ", "MEZERA_NAD_PANELY = 25.0 ")], "core"),
    ("m02", "automaticka vyska bez panelu 120 misto 150 mm", HP, [("VYSKA_BEZ_PANELU = 150.0 ", "VYSKA_BEZ_PANELU = 120.0 ")], "core"),
    ("m03", "vule pod ramenem LED 0 misto 15 mm", HP, [("MEZERA_POD_RAMENEM = 15.0 ", "MEZERA_POD_RAMENEM = 0.0 ")], "core"),
    ("m04", "zadni pricka kratsi o 2 mm", HP, [("clenove[kz] = S._klon(sab, S.ZRAIL_PANEL, [float(k[\"xr\"]), y_s, zc], delka=G)", "clenove[kz] = S._klon(sab, S.ZRAIL_PANEL, [float(k[\"xr\"]), y_s, zc], delka=G - 2.0)")], "core"),
    ("m05", "predni pricka o 5 mm dal (hloubka ramu)", HP, [("xf_c = xr + P - dout ", "xf_c = xr + P - dout + 5.0 ")], "core"),
    ("m06", "levy bocni profil o 1 mm vedle stojky", HP, [("for j, zb in enumerate((a_ + H, b_ - H)):", "for j, zb in enumerate((a_ + H + 1.0, b_ - H)):")], "core"),
    ("m07", "bocni profil delsi o jeden profil (delka_b)", HP, [("delka_b = dout - 2.0 * P ", "delka_b = dout - P ")], "core"),
    ("m08", "rozpon laminodesky 18 mm 1200 misto 800 (mene mezilist)", HP, [("ROZPON = {None: 800.0, \"lam18\": 800.0,", "ROZPON = {None: 800.0, \"lam18\": 1200.0,")], "core"),
    ("m09", "rozpon MDF 8 mm 800 misto 400", HP, [("\"mdf8\": 400.0,", "\"mdf8\": 800.0,")], "core"),
    ("m10", "mezilisty nerovnomerne (pitch k osam misto k volnym polim)", HP, [("    return [a + (j + 1) * g + j * P + P / 2.0 for j in range(n)]", "    return [a + (j + 1) * (b - a) / (n + 1) for j in range(n)]")], "core"),
    ("m11", "rovna deska nezacina na predni hrane ramu (o 10 mm vzadu)", HP, [("x_od = (xf_c - H) if tg != \"lem\" else None", "x_od = (xf_c - H + 10.0) if tg != \"lem\" else None")], "core"),
    ("m12", "deska lezi o 1 mm vys nad ramem", HP, [("(x_od + x_do) / 2.0, y_rt + tl / 2.0, (z0 + z1) / 2.0))", "(x_od + x_do) / 2.0, y_rt + tl / 2.0 + 1.0, (z0 + z1) / 2.0))")], "core"),
    ("m13", "deska lemu zacina 5 misto 1 mm za uhelniky", HP, [("float(uh_hi[0] - uh_lo[0]) + 1.0 ", "float(uh_hi[0] - uh_lo[0]) + 5.0 ")], "core"),
    ("m14", "lem 30 misto 40 mm vysoky", HP, [("LEM_VYSKA = 40.0 ", "LEM_VYSKA = 30.0 ")], "core"),
    ("m15", "lem: aspon 1 uhelnik misto 2", HP, [("n_b = max(2, int(math.ceil(G / UHELNIK_VZDALENOST_MAX)))", "n_b = max(1, int(math.ceil(G / UHELNIK_VZDALENOST_MAX)))")], "core"),
    ("m16", "lem: rozteč uhelniku 900 misto 450 mm", HP, [("UHELNIK_VZDALENOST_MAX = 450.0 ", "UHELNIK_VZDALENOST_MAX = 900.0 ")], "core"),
    ("m17", "lem: nejdelsi kus 1200 misto 2500 mm (deli se driv)", HP, [("LEM_MAX_DELKA = 2500.0 ", "LEM_MAX_DELKA = 1200.0 ")], "core"),
    ("m18", "deska v drazce zasahuje 6 misto 8 mm", HP, [("DRAZKA_ZASAH = {30: 8.0, 35: 8.0,", "DRAZKA_ZASAH = {30: 6.0, 35: 8.0,")], "core"),
    ("m19", "deska v drazce bez rezervy 1 mm u spojek (gap_c)", HP, [("gap_c = round(float(max(hi_c - lo_c)) + 1.0, 2)", "gap_c = round(float(max(hi_c - lo_c)) + 0.0, 2)")], "core"),
    ("m20", "deska v drazce zasahuje i do pricnych profilu (gap_c = 0, zasazeno_do pricky)", HP, [("gap_c = round(float(max(hi_c - lo_c)) + 1.0, 2)", "gap_c = 0.0")], "core"),
    ("m21", "prepazky: rozteč 520 misto 260 mm", HP, [("ROZTEC_PREPAZEK = 260.0 ", "ROZTEC_PREPAZEK = 520.0 ")], "core"),
    ("m22", "prepazky 200 misto 240 mm vysoke", HP, [("PREPAZKA_PART, PREPAZKA_TL, PREPAZKA_VYSKA, PREPAZKA_ODSAZENI = \"product_3539\", 10.0, 240.0, 2.0", "PREPAZKA_PART, PREPAZKA_TL, PREPAZKA_VYSKA, PREPAZKA_ODSAZENI = \"product_3539\", 10.0, 200.0, 2.0")], "core"),
    ("m23", "prepazky: odsazeni konce 2 misto 0 mm (dx = hloubka)", HP, [("PREPAZKA_PART, PREPAZKA_TL, PREPAZKA_VYSKA, PREPAZKA_ODSAZENI = \"product_3539\", 10.0, 240.0, 2.0", "PREPAZKA_PART, PREPAZKA_TL, PREPAZKA_VYSKA, PREPAZKA_ODSAZENI = \"product_3539\", 10.0, 240.0, 0.0")], "core"),
    ("m24", "prepazky: uhelniky vsechny na stejne strane (nestridave)", HP, [("sA = 1.0 if j % 2 == 0 else -1.0 ", "sA = 1.0 ")], "core"),
    ("m25", "prepazky: predni a zadni uhelnik na stejne strane prepazky", HP, [("((xf_c, sA), (float(k[\"xr\"]), -sA))", "((xf_c, sA), (float(k[\"xr\"]), sA))")], "core"),
    ("m26", "uhelniky prepazek 3 mm nad prickou", HP, [("uh, rozm = _uhelnik(uh_part, (0.0, 0.0, znak), (x_pric, y_rt, zj + znak * PREPAZKA_TL / 2.0))", "uh, rozm = _uhelnik(uh_part, (0.0, 0.0, znak), (x_pric, y_rt + 3.0, zj + znak * PREPAZKA_TL / 2.0))")], "core"),
    ("m27", "uhelnik 40x40 se pro system 40 nahradi 30x30", HP, [("UHELNIK = {30: \"product_3045\", 35: \"product_3045\", 40: \"product_3207\",", "UHELNIK = {30: \"product_3045\", 35: \"product_3045\", 40: \"product_3045\",")], "core"),
    ("m28", "laminodeska 12 mm povolena i v systemu 40", HP, [("40: (\"lam18\", \"pr10\"),", "40: (\"lam18\", \"lam12\", \"pr10\"),")], "core"),
    ("m29", "deska do drazky v systemu 30 je PR10 misto MDF 8", HP, [("DRAZKA_DESKA = {30: \"mdf8\",", "DRAZKA_DESKA = {30: \"pr10\",")], "core"),
    ("m30", "neznamy typ police se prijme", HP, [("    if typ not in TYPY:\n        raise StulChyba", "    if False:\n        raise StulChyba")], "core"),
    ("m31", "hloubka police az 900 mm", HP, [("HLOUBKA_VYCHOZI, HLOUBKA_MIN, HLOUBKA_MAX = 300.0, 150.0, 600.0", "HLOUBKA_VYCHOZI, HLOUBKA_MIN, HLOUBKA_MAX = 300.0, 150.0, 900.0")], "core"),
    ("m32", "ramova police si nechava zadanou desku (neni kanonicka)", HP, [("            out[\"hpolice_deska\"] = deska_pro(typ, deska, sys_) or DESKA_VYCHOZI         # nepouzita / pevna deska: jedna kanonicka podoba", "            pass")], "core"),
    ("m33", "automaticka vyska se nezaokrouhluje na 10 mm", HP, [("hv_auto = math.ceil((y_dolni_auto + P + tl_vrch - y_deska_hor) / 10.0 - 1e-9) * 10.0", "hv_auto = (y_dolni_auto + P + tl_vrch - y_deska_hor)")], "core"),
    ("m34", "s panely lze polici snizit pod panely (min vysky = 100)", HP, [("    hv_min = max(VYSKA_MIN, hv_auto) if y_pan is not None else VYSKA_MIN", "    hv_min = VYSKA_MIN")], "core"),
    ("m35", "deleni desky: nejblizsi mezilista misto hladoveho deleni", HP, [("                hranice.append(max(kand))", "                hranice.append(min(kand))")], "core"),
    ("m36", "minimalni hloubka drazkove police se nezvysuje", HP, [("        h_min = max(HLOUBKA_MIN, math.ceil((2.0 * P + 2.0 * gap_c + DELKA_DESKY_MIN) / 10.0) * 10.0)", "        h_min = HLOUBKA_MIN")], "core"),
    ("m37", "usek mezi stojkami uzsi nez 2P + 120 se nepreskoci (+10)", HP, [("SIRKA_MIN_PLUS = 120.0 ", "SIRKA_MIN_PLUS = 10.0 ")], "core"),
    ("m38", "kanonicky hash neodstranuje klice police pri vypnute policce", HP, [("    if not (p[\"hpolice\"] and p[\"stojky\"]):\n        for k in KLICE:\n            p.pop(k, None)\n        return p", "    if False:\n        return p")], "core"),
    ("m39", "typy[]: kazdy typ se 'vejde' (nabidka typu v UI)", HP, [("out.append({\"typ\": t, \"vejde\": duvod is None, \"duvod\": duvod,", "out.append({\"typ\": t, \"vejde\": True, \"duvod\": duvod,")], "shop"),
    ("m40", "3D menu: zadne zakazani typu, ktere se nevejde", HP, [("duvod = None if x.get(\"vejde\", True) else (\"Sem se nevejde (stůl se střední zadní nohou).\" if x.get(\"duvod\") == \"sekce\" else \"Sem se nevejde (málo místa nad rámem).\")", "duvod = None")], "core"),
    ("m41", "3D menu: o 50 mm vys nejde zakazat na maximu", HP, [("None if v[\"hodnota\"] + 1e-6 < v[\"max\"] else \"Výš už police nejde.\"", "None")], "core"),
    ("m42", "nabidka: typ s lemem nepotrebuje PR10 a uhelniky", HP, [("    if typ in (\"lem\", \"prepazky\", \"sikma\"):\n        out.update((PREPAZKA_PART, UHELNIK[system]))", "    if typ in (\"prepazky\", \"sikma\"):\n        out.update((PREPAZKA_PART, UHELNIK[system]))")], "core"),
    # ---- zaplaty generatoru (stul_konfigurator.py)
    ("k01", "police zapnuta ve vychozim stavu", K, [("\"hpolice\": False, \"hpolice_typ\": \"rovna\"", "\"hpolice\": True, \"hpolice_typ\": \"rovna\"")], "core"),
    ("k02", "hpolice neni mezi prepinaci (dotaz ?hpolice=1 neznamy)", K, [("\"navlek\", \"hpolice\")", "\"navlek\")")], "core"),
    ("k03", "otoceni spojky kolem uzlu opacnym smerem", K, [("    t = math.radians(stupne)\n    c, sn", "    t = math.radians(-stupne)\n    c, sn")], "core"),
    ("k04", "spojky police se cisluji pred ostatnimi (posunou cislovani)", K, [("    odvozene_spojky += hpolice_spojky ", "    odvozene_spojky[:0] = hpolice_spojky ")], "core"),
    ("k05", "deska police je prejmenovana na prac_ / pol (deska_id se prepise)", K, [("        if c[\"druh\"] != \"deska\" or c.get(\"deska_id\"):          # deska horni police", "        if c[\"druh\"] != \"deska\":          # deska horni police")], "core"),
    ("k06", "volne konce profilu police se kontroluji podle sablony (konce_ocek)", K, [("        if c.get(\"konce\") is not None:\n            konce_ocek[klic] = tuple(c[\"konce\"])", "        if False:\n            konce_ocek[klic] = tuple(c[\"konce\"])")], "core"),
    ("k07", "problem 'police se nevejde' se nehlasi", K, [("    if hpolice_info and hpolice_info.get(\"problem\") == \"misto\":", "    if False:")], "core"),
    ("k08", "police se pri problemu neodebere automaticky", K, [("                kandidati.setdefault(\"hpolice\", pr[\"text\"])", "                pass")], "core"),
    ("k09", "uhelniky police nemaji v cene spojovaci material", K, [("    \"product_3045\": [(\"2.1.21.0612\", 1,", "    \"product_3045\": [(\"2.1.21.0612\", 0,")], "core"),
    ("k10", "polozky ceny nezname desky police (MDF, PR10)", K, [("        elif d[\"part_id\"] == \"product_4933\" or d[\"part_id\"] in _hpol().DESKA_PARTY:\n            if d.get(\"deska_kus\"):", "        elif d[\"part_id\"] == \"product_4933\":\n            if d.get(\"deska_kus\"):")], "core"),
    ("k11", "role dilu police se nepoznaji", K, [("    if t == \"hpol\":\n        return _hpol().role(klic)", "    if False:\n        return _hpol().role(klic)")], "core"),
    ("k12", "montazni krok 7 pro polici se nepouzije", K, [("    if \"horní police\" in popis:\n        return 7\n", "")], "core"),
    ("k13", "popis desky police ve vypisu je obecny", K, [("    if deska_id.startswith(\"hpol\"):\n        return _hpol().popis_desky(deska_id)\n", "")], "core"),
    ("k14", "deska v drazce je prunik (zasazeno_do se ignoruje)", K, [("        for kk_ in c_.get(\"zasazeno_do\") or ():", "        for kk_ in ():")], "core"),
    ("k15", "3D ovladani nema skupinu police", K, [("    if hp_ and not hp_.get(\"problem\"):\n        skupina(\"hpolice\"", "    if False:\n        skupina(\"hpolice\"")], "core"),
    ("k16", "dotaz nezna ?hpolice_vyska", K, [("elzlab_z\", \"hpolice_vyska\")", "elzlab_z\")")], "core"),
    ("k17", "stojky_potreba nevypina polici (stojky vypnute, police zustane)", K, [("            for k in (\"panely\", \"led\", \"elektrozlab\", \"hpolice\"):", "            for k in (\"panely\", \"led\", \"elektrozlab\"):")], "core"),
    ("k18", "nabidka roztazeni nenabizi vyssi stojky pro polici", K, [("        if not nab and k in (\"panely\", \"hpolice\"):", "        if not nab and k in (\"panely\",):")], "shop"),
    ("k19", "nazvy novych dilu v kusovniku chybi", K, [("_NAZVY.update({\"product_3939\": \"MDF deska 8 mm (police)\",", "_NAZVY.update({\"product_3939\": \"deska\",")], "core"),
    ("k20", "GLB MDF desky se hleda pod spatnym jmenem", K, [("GLB_SOUBORY = {\"product_3939\": \"deska_mdf_seda_8.glb\",", "GLB_SOUBORY = {\"product_3939\": \"deska_mdf_seda_88.glb\",")], "core"),
    ("k21", "vyska polic: hpolice_vyska se pri kolizi neodstrani z posunu", K, [("and p[\"elzlab_z\"] == 0 and p[\"hpolice_vyska\"] is None):", "and p[\"elzlab_z\"] == 0):")], "core"),
    # ---- GLB, SSE, verejne ovladani
    ("g01", "hash se pocita bez kanonizace police (klice police i u vypnute)", GL, [("    p = S._hpol().kanon_hash(p) ", "    p = p ")], "core"),
    ("g02", "pořadí materialu bez mdf / preklizky", GL, [("\"chrom\", \"mdf\", \"preklizka\", \"ral7016\"]", "\"chrom\", \"ral7016\"]")], "core"),
    ("g03", "dily police nemaji v GLB svuj material", GL, [("MATERIAL_DILU.update(S._hpol().MATERIAL_DILU)", "pass")], "core"),
    ("g04", "GLB se nacita jen podle <part_id>.glb", GL, [("    path = S.glb_cesta(part_id)\n", "    path = os.path.join(S.KATALOG_DIR, part_id + \".glb\")\n")], "core"),
    ("s01", "SSE stul pripusti polici", SS, [("\"loz\", \"hpolice\")", "\"loz\")")], "core"),
    ("s02", "SSE nechava klice police (neignoruje)", SS, [("\"vzpera_delka\", \"hpolice_typ\", \"hpolice_deska\", \"hpolice_vyska\", \"hpolice_hloubka\", \"hpolice_sklon\")", "\"vzpera_delka\")")], "core"),
    ("o01", "verejne 3D menu nezna slot police", OV, [("                 \"hpolice\": \"upshelf\", \"hpolice_typ\": \"upshelftype\",", "                 \"hpolice_typ\": \"upshelftype\",")], "core"),
    ("o02", "verejne 3D menu: typ police jako generatorove id (ram) misto verejneho (frame)", OV, [("            out[slot] = S._hpol().TYP_VEREJNE[v] ", "            out[slot] = v ")], "core"),
    ("o03", "preklady menu police chybi", OV, [("] + S._hpol().PREKLADY ", "] ")], "core"),
    ("o04", "cast police nema verejne id", OV, [("\"ram\": \"frame\", \"hpolice\": \"upshelf\"}", "\"ram\": \"frame\"}")], "core"),
    # ---- verejne API (stul_shop.py)
    ("h01", "token nenese typ a rozmery police (klic R)", SH, [("        out[\"R\"] = [p[\"hpolice_typ\"]", "        out[\"RX\"] = [p[\"hpolice_typ\"]")], "shop"),
    ("h02", "rozbaleni tokenu zmeni hloubku police", SH, [("p[\"hpolice_hloubka\"] = float(o[\"R\"][3])", "p[\"hpolice_hloubka\"] = float(o[\"R\"][3]) + 10.0")], "shop"),
    ("h03", "bit police v tokenu chybi", SH, [("\"vzpery\", \"navlek\", \"hpolice\"]", "\"vzpery\", \"navlek\"]")], "shop"),
    ("h04", "normalizace nebere typ police z vyberu", SH, [("    p[\"hpolice_typ\"] = _upshelf_typ(sel.get(\"upshelftype\"), nab_hp) if p[\"hpolice\"] else HP.TYP_VYCHOZI", "    p[\"hpolice_typ\"] = HP.TYP_VYCHOZI")], "shop"),
    ("h05", "nabidka karet police neni v klici cache resolve", SH, [("tuple(sorted(delky)), nab_hp, norm.get(\"ledlen\")", "tuple(sorted(delky)), norm.get(\"ledlen\")")], "shop"),
    ("h06", "verejnost dostane i nenabizeny typ police", SH, [("    return t if t in nab[1] else (HP.TYP_VYCHOZI", "    return t if t else (HP.TYP_VYCHOZI")], "shop"),
    ("h07", "verejnost dostane vsechny karty police (zadny gating)", SH, [("        karty = None if (not has_request_context() or _je_staff()) else karty_police_verejne()", "        karty = None")], "shop"),
    ("h08", "vyska police v echu vyberu jako desetinne cislo", SH, [("    return None if v is None else (int(v) if float(v).is_integer() else round(float(v), 1))", "    return None if v is None else float(v)")], "shop"),
    ("h09", "odkaz na vyrobni list nese parametry police i bez police", SH, [(" and not (k.startswith(\"hpolice\") and k != \"hpolice\" and not p.get(\"hpolice\")) and not (k == \"hpolice\" and not v)", "")], "shop"),
    ("h10", "shrnuti vyberu ukazuje podvolby police i bez police", SH, [("        skryt.update((\"upshelftype\", \"upshelfboard\", \"upshelfpos\", \"upshelfdepth\", \"upshelftilt\"))\n    else:", "        pass\n    else:")], "shop"),
    ("h11", "podvolby police nezavisi na zapnute policce (depends_on)", SH, [("[\"posts\", \"upshelf\"] for k_ in", "[\"posts\"] for k_ in")], "shop"),
    ("h12", "schema verejnosti nabizi i nenabizene typy", SH, [("            sl[\"options\"] = [o for o in sl[\"options\"] if HP.TYP_ID[o[\"id\"]] in nab_hp[1]]", "            pass")], "shop"),
    ("h13", "options.upshelftype nezakazuje typy, ktere se nevejdou", SH, [("for x_ in hp_inf[\"typy\"] if not x_[\"vejde\"] and", "for x_ in hp_inf[\"typy\"] if False and")], "shop"),
    ("h14", "options.upshelfdepth bez nejmensi hloubky typu", SH, [("options[\"upshelfdepth\"] = {\"min\": int(hh[\"min\"]),", "options[\"upshelfdepth\"] = {\"min\": 150,")], "shop"),
    ("h15", "options.upshelfpos: nejvyssi vyska o 10 mm vys", SH, [("\"max\": int(math.floor(hv[\"max\"] / 10.0)) * 10, \"value\": round(float(hv[\"hodnota\"]", "\"max\": int(math.floor(hv[\"max\"] / 10.0)) * 10 + 10, \"value\": round(float(hv[\"hodnota\"]")], "shop"),
    ("h16", "ramova police ma volitelnou desku (options.upshelfboard)", SH, [("        if p[\"hpolice_typ\"] == \"ram\":\n            duv = dz[\"upshelf_deska_ram\"]", "        if False:\n            duv = dz[\"upshelf_deska_ram\"]")], "shop"),
    ("h17", "verejnost dostane desku 12 mm i s neaktivni kartou", SH, [("    pouz = [d for d in HP.nabidka_desek(system, typ) if d in nab[0]]", "    pouz = [d for d in HP.nabidka_desek(system, typ)]")], "shop"),
    ("h18", "automaticky odebrana police se nehlasi (kod hpolice_nevejde jen v generatoru)", SH, [("VOLBA_NA_SLOT[\"hpolice\"] = \"upshelf\"", "pass")], "shop"),

    # ---- 2. KOLO: SIKMA POLICE (stul_hpolice.py v2 + zaplaty generatoru / shopu); vlastni test = test_hpolice_sikma.py
    ("x01", "sikma: vychozi sklon 10 misto 15", HP, [("SKLON_VYCHOZI, SKLON_MIN, SKLON_MAX, SKLON_KROK = 15.0, 5.0, 30.0, 5.0", "SKLON_VYCHOZI, SKLON_MIN, SKLON_MAX, SKLON_KROK = 10.0, 5.0, 30.0, 5.0")], "sikma"),
    ("x02", "sikma: nejvetsi sklon 45 misto 30", HP, [("SKLON_VYCHOZI, SKLON_MIN, SKLON_MAX, SKLON_KROK = 15.0, 5.0, 30.0, 5.0", "SKLON_VYCHOZI, SKLON_MIN, SKLON_MAX, SKLON_KROK = 15.0, 5.0, 45.0, 5.0")], "sikma"),
    ("x03", "sikma: nejmensi sklon 0 misto 5", HP, [("SKLON_VYCHOZI, SKLON_MIN, SKLON_MAX, SKLON_KROK = 15.0, 5.0, 30.0, 5.0", "SKLON_VYCHOZI, SKLON_MIN, SKLON_MAX, SKLON_KROK = 15.0, 0.0, 30.0, 5.0")], "sikma"),
    ("x04", "sikma: krok sklonu 1 misto 5 (3D menu)", HP, [("SKLON_VYCHOZI, SKLON_MIN, SKLON_MAX, SKLON_KROK = 15.0, 5.0, 30.0, 5.0", "SKLON_VYCHOZI, SKLON_MIN, SKLON_MAX, SKLON_KROK = 15.0, 5.0, 30.0, 1.0")], "sikma"),
    ("x05", "sikma: nejnizsi bod jen 20 misto 50 mm nad deskou", HP, [("SIKMA_MIN_NAD_DESKOU = 50.0 ", "SIKMA_MIN_NAD_DESKOU = 20.0 ")], "sikma"),
    ("x06", "sikma: naklon na opacnou stranu (vpredu vys)", HP, [("info[\"rotace\"] = {\"O\": (xr, y_s), \"phi\": m[\"th\"]}", "info[\"rotace\"] = {\"O\": (xr, y_s), \"phi\": -m[\"th\"]}")], "sikma"),
    ("x07", "sikma: osa naklonu o 30 mm vys nez osa zadni pricky", HP, [("info[\"rotace\"] = {\"O\": (xr, y_s), \"phi\": m[\"th\"]}", "info[\"rotace\"] = {\"O\": (xr, y_s + 30.0), \"phi\": m[\"th\"]}")], "sikma"),
    ("x08", "sikma: vyska police bez tloustky desky (rear_top)", HP, [("rear_top = H * s + (H + tl) * c", "rear_top = H * s + H * c")], "sikma"),
    ("x09", "sikma: strop bez rezervy pod rohovou spojkou ramene LED (konzola)", HP, [("extra_konz = max(0.0, float(max(hi_c - lo_c)) + 5.0 - MEZERA_POD_RAMENEM)", "extra_konz = 0.0")], "sikma"),
    ("x10", "sikma: nejvyssi vyska bez ohledu na nejvyssi bod (lem, konzola)", HP, [("hv_max = (y_strop - MEZERA_POD_RAMENEM) - y_deska_hor + rel[\"rear_top\"] - rel[\"high\"]", "hv_max = (y_strop - MEZERA_POD_RAMENEM) - y_deska_hor + rel[\"rear_top\"] - rel[\"rear_top\"]")], "sikma"),
    ("x11", "sikma: nejnizsi vyska bez odstupu od desky stolu", HP, [("hv_desk = SIKMA_MIN_NAD_DESKOU - rel[\"low\"] + rel[\"rear_top\"]", "hv_desk = SIKMA_MIN_NAD_DESKOU")], "sikma"),
    ("x12", "sikma: automaticka vyska bez panelu nebere nejnizsi bod", HP, [("auto_raw = hv_pan if hv_pan is not None else (VYSKA_BEZ_PANELU - rel[\"low\"] + rel[\"rear_top\"])", "auto_raw = hv_pan if hv_pan is not None else VYSKA_BEZ_PANELU")], "sikma"),
    ("x13", "sikma: zadana vyska se neorezava na meze", HP, [("hv = hv_auto if zadana is None else min(max(float(zadana), hv_min), max(hv_max, hv_min))\n    return {\"P\": P, \"H\": H, \"typ\": \"sikma\"", "hv = hv_auto if zadana is None else float(zadana)\n    return {\"P\": P, \"H\": H, \"typ\": \"sikma\"")], "sikma"),
    ("x14", "sikma: dve sekce (stredni zadni noha) se nehlasi", HP, [("    if sikma and m[\"sekci_n\"] > 1:", "    if False:")], "sikma"),
    ("x15", "sikma: 3D menu / typy[] nezakazuji sikmou u dvou useku", HP, [("sekce_ok = (m.get(\"sekci_n\", 1) <= 1) if t == \"sikma\" else True", "sekce_ok = True")], "sikma"),
    ("x16", "sikma: bez lemu vpredu (rovny ram)", HP, [("tg = \"lem\" if sikma else typ", "tg = \"rovna\" if sikma else typ")], "sikma"),
    ("x17", "sikma: konzola neni spoj stojka - bok (cena prace za spoj)", HP, [("info[\"pary\"] += [(kl, boky[0]), (kr, boky[1])]", "pass")], "sikma"),
    ("x18", "sikma: presna kontrola kolizi vypnuta", HP, [("    if not info or not info.get(\"rotace\"):\n        return []\n    skup =", "    if True:\n        return []\n    skup =")], "sikma"),
    ("x19", "sikma: vzpery nevidi naklonenou polici ani konzoly", HP, [("    if not info or not info.get(\"rotace\"):\n        return kl_vse, bb_vse\n    bb = np.array(bb_vse, float)", "    if True:\n        return kl_vse, bb_vse\n    bb = np.array(bb_vse, float)")], "sikma"),
    ("x20", "sikma: kolize se sikmou vzperou jen proti AABB (falesne pruniky)", HP, [("            dep[jj] = _sat_obb_obb(c_w, R, h, c2, R2, h2)", "            pass")], "sikma"),
    ("x21", "sikma: konzola bez posunu o bod Q (rovina listu mimo stojku)", HP, [("\"pos\": T - M @ Q, \"quat\": _kvat_z_matice(M)", "\"pos\": T, \"quat\": _kvat_z_matice(M)")], "sikma"),
    ("x22", "sikma: leva konzola s opacnou osou Z", HP, [("M_levy = np.array([[0.0, -1.0, 0.0], [-1.0, 0.0, 0.0], [0.0, 0.0, -1.0]])", "M_levy = np.array([[0.0, -1.0, 0.0], [-1.0, 0.0, 0.0], [0.0, 0.0, 1.0]])")], "sikma"),
    ("x23", "sikma: vyska stredu konzoly pres sin misto tan", HP, [("y_c = y_s - (H + g[\"pivot_y\"] - g[\"y_zad\"]) * math.tan(th)", "y_c = y_s - (H + g[\"pivot_y\"] - g[\"y_zad\"]) * math.sin(th)")], "sikma"),
    ("x24", "sikma: meze (sikma_rel) s jinou vyskou konzoly nez stavba", HP, [("y_c = -(H + dpiv) * math.tan(th)", "y_c = -(H + dpiv) * math.sin(th)")], "sikma"),
    ("x25", "sikma: nejnizsi bod prvni pricky bez pulky profilu", HP, [("front_low = -(dout - P) * s - H * (c + s)", "front_low = -(dout - P) * s")], "sikma"),
    ("x26", "sikma: osa kloubu konzoly 3323 jinde (pivot_y 25 misto 20,98)", HP, [("\"pivot_y\": 20.98", "\"pivot_y\": 25.0")], "sikma"),
    ("x27", "sikma: system 40 pouzije konzolu 3323 (drazka 8)", HP, [("KONZOLE = {30: \"product_3323\", 35: \"product_3323\", 40: \"product_3324\", 45: \"product_3324\"}", "KONZOLE = {30: \"product_3323\", 35: \"product_3323\", 40: \"product_3323\", 45: \"product_3324\"}")], "sikma"),
    ("x28", "sikma: ram se neotoci (profily zustanou ploche)", HP, [("    if isinstance(k, tuple) and k and k[0] == \"hpol\":\n        return bool(c.get(\"hp_rot\"))", "    if isinstance(k, tuple) and k and k[0] == \"hpol\":\n        return False")], "sikma"),
    ("x29", "sikma: rohove spojky ramu se neotoci s ramem", HP, [("        return any(isinstance(v, tuple) and v and v[0] == \"hpol\" and bool(clenove.get(v, {}).get(\"hp_rot\")) for v in vl)", "        return False")], "sikma"),
    ("x30", "sikma: zaslepky ramu se neotoci s ramem", HP, [("        return isinstance(o, tuple) and bool(o) and o[0] == \"hpol\" and bool(clenove.get(o, {}).get(\"hp_rot\"))", "        return False")], "sikma"),
    ("x31", "sikma: konzoly se do sestavy nepridaji", HP, [("    for kz in (info or {}).get(\"konzoly\") or ():", "    for kz in ():")], "sikma"),
    ("x32", "sikma: sklon mimo 5-30 se prijme", HP, [("    if not SKLON_MIN <= sk <= SKLON_MAX:", "    if False:")], "sikma"),
    ("x33", "sikma: hash zavisi na sklonu i u jinych typu", HP, [("        p.pop(\"hpolice_sklon\", None)", "        pass")], "sikma"),
    ("x34", "sikma: sklon u jinych typu se nekanonizuje", HP, [("            out[\"hpolice_sklon\"] = SKLON_VYCHOZI                                         # sklon se pouziva", "            pass                                         # sklon se pouziva")], "sikma"),
    ("x35", "sikma: 3D menu dovoli vetsi sklon nez maximum", HP, [("None if sk[\"hodnota\"] + 1e-6 < sk[\"max\"] else \"Větší sklon už není možný.\"", "None")], "sikma"),
    ("x36", "sikma: horni okraj lemu bez vysky lemu (nejvyssi bod)", HP, [("lip_top = (-(dout - P) - H + PREPAZKA_TL) * s + (H + LEM_VYSKA) * c", "lip_top = (-(dout - P) - H + PREPAZKA_TL) * s + (H + 0.0) * c")], "sikma"),
    ("x37", "sikma: nejmensi vyska nad panely bez nejnizsiho rohu zadni pricky", HP, [("hv_pan = (y_pan + MEZERA_NAD_PANELY - y_deska_hor + rel[\"rear_top\"] - rel[\"rear_low\"]) if y_pan is not None else None", "hv_pan = (y_pan + MEZERA_NAD_PANELY - y_deska_hor + rel[\"rear_top\"]) if y_pan is not None else None")], "sikma"),
    ("z01", "sikma: konzole bez spojovaciho materialu (2 misto 4 sroubu)", K, [("\"product_3323\": [(\"2.1.21.0612\", 4,", "\"product_3323\": [(\"2.1.21.0612\", 2,")], "sikma"),
    ("z02", "sikma: nazvy konzol v kusovniku chybi", K, [("_NAZVY.update({\"product_3323\": \"úhlová naklápěcí konzola (drážka 8)\", \"product_3324\": \"úhlová naklápěcí konzola (drážka 10)\"})", "_NAZVY.update({})")], "sikma"),
    ("z03", "sikma: ram se pri vystupu do dily neotaci (generator)", K, [("if hpolice_info and hpolice_info.get(\"rotace\") and _hpol().v_rotaci(k, c, clenove):", "if False:")], "sikma"),
    ("z04", "sikma: AABB kontrola generatoru se pro naklonene dily nevypne", K, [("and i not in vz_vse and i not in sk_vse]", "and i not in vz_vse]")], "sikma"),
    ("z05", "sikma: spoje boku / mezilist na pricky se nepocitaji (lic_peers)", K, [("for ka_, kb_ in ((hpolice_info or {}).get(\"pary\") or ()):", "for ka_, kb_ in ():")], "sikma"),
    ("z06", "sikma: konzoly se nepridaji do sestavy (generator)", K, [("    _hpol().pridej_konzoly(hpolice_info, clenove)", "    pass")], "sikma"),
    ("z07", "sikma: vzpery nevidi naklonenou polici (volani v generatoru)", K, [("        kl_vse, bb_vse = _hpol().pro_vzpery(hpolice_info, kl_vse, bb_vse, clenove, spojky)", "        pass")], "sikma"),
    ("z08", "sikma: presna kontrola kolizi se nezapoji (volani v generatoru)", K, [("    problemy += _hpol().zkontroluj(hpolice_info, dily, bb, idx, clenove, spojky)", "    problemy += []")], "sikma"),
    ("z09", "sikma: vychozi sklon v generatoru 10", K, [("\"hpolice_hloubka\": 300.0, \"hpolice_sklon\": 15.0,", "\"hpolice_hloubka\": 300.0, \"hpolice_sklon\": 10.0,")], "sikma"),
    ("z10", "sikma: dotaz ?hpolice_sklon neni cislo", K, [("\"hpolice_hloubka\", \"hpolice_sklon\") + VYREZY_CISLA", "\"hpolice_hloubka\") + VYREZY_CISLA")], "sikma"),
    ("z11", "sikma: SSE nechava hpolice_sklon (neignoruje)", SS, [("\"hpolice_hloubka\", \"hpolice_sklon\")", "\"hpolice_hloubka\")")], "core"),
    ("z12", "sikma: verejne 3D menu nezna slot sklonu", OV, [(", \"hpolice_sklon\": \"upshelftilt\"}", "}")], "shop"),
    ("y01", "sikma: token nenese sklon (R[4])", SH, [("+ ([round(float(p[\"hpolice_sklon\"]), 1)] if p[\"hpolice_typ\"] == \"sikma\" else [])", "+ []")], "shop"),
    ("y02", "sikma: rozbaleni tokenu zahodi sklon", SH, [("p[\"hpolice_sklon\"] = float(o[\"R\"][4])", "p[\"hpolice_sklon\"] = 15.0")], "shop"),
    ("y03", "sikma: normalizace nebere sklon z vyberu", SH, [("p[\"hpolice_sklon\"] = _cislo(sel[\"upshelftilt\"], HP.SKLON_MIN, HP.SKLON_MAX, HP.SKLON_VYCHOZI, HP.SKLON_KROK) if (p[\"hpolice\"] and p[\"hpolice_typ\"] == \"sikma\") else float(HP.SKLON_VYCHOZI)", "p[\"hpolice_sklon\"] = float(HP.SKLON_VYCHOZI)")], "shop"),
    ("y04", "sikma: options.upshelftilt.max o 5 vys", SH, [("options[\"upshelftilt\"] = {\"min\": int(HP.SKLON_MIN), \"max\": int(HP.SKLON_MAX), \"value\": int(round(p[\"hpolice_sklon\"]))}", "options[\"upshelftilt\"] = {\"min\": int(HP.SKLON_MIN), \"max\": int(HP.SKLON_MAX) + 5, \"value\": int(round(p[\"hpolice_sklon\"]))}")], "shop"),
    ("y05", "sikma: posuvnik sklonu odemceny i u jinych typu", SH, [("options[\"upshelftilt\"] = {\"min\": int(HP.SKLON_VYCHOZI), \"max\": int(HP.SKLON_VYCHOZI)}", "options[\"upshelftilt\"] = {\"min\": int(HP.SKLON_MIN), \"max\": int(HP.SKLON_MAX)}")], "shop"),
    ("y06", "sikma: shrnuti ukazuje sklon i u jinych typu", SH, [("        if sel.get(\"upshelftype\") != \"slope\":\n            skryt.add(\"upshelftilt\")", "        pass")], "shop"),
    ("y07", "sikma: sklon nezavisi na zapnute policce (depends_on)", SH, [("for k_ in (\"upshelftype\", \"upshelfboard\", \"upshelfpos\", \"upshelfdepth\", \"upshelftilt\")})", "for k_ in (\"upshelftype\", \"upshelfboard\", \"upshelfpos\", \"upshelfdepth\")})")], "shop"),
    ("y08", "sikma: odkaz na vyrobni list nese sklon i u jinych typu", SH, [(" and not (k == \"hpolice_sklon\" and p.get(\"hpolice_typ\") != \"sikma\")", "")], "shop"),
    ("y09", "sikma: anglicky popisek sklonu chybi", SH, [("TEXTY[\"en\"].update({\"upshelftilt\": \"Shelf slope (lower at the front)\", \"upshelftype_slope\": \"Sloped, for boxes (with a front lip)\"})", "TEXTY[\"en\"].update({})")], "shop"),
    ("y10", "sikma: posuvnik sklonu v schematu 5-45", SH, [("slider(\"upshelftilt\", \"g_extras\", int(HP.SKLON_MIN), int(HP.SKLON_MAX),", "slider(\"upshelftilt\", \"g_extras\", int(HP.SKLON_MIN), int(HP.SKLON_MAX) + 15,")], "shop"),
    ("y11", "sikma: echo vyberu nese vychozi sklon misto zvoleneho", SH, [("norm[\"upshelftilt\"] = int(round(p[\"hpolice_sklon\"])) if (p[\"hpolice\"] and p[\"hpolice_typ\"] == \"sikma\") else int(HP.SKLON_VYCHOZI)", "norm[\"upshelftilt\"] = int(HP.SKLON_VYCHOZI)")], "shop"),
]


def postav(tmp, soubor, obsah):
    """tmp = docasny koren: tmp/api = symlinky na ZDROJ (kandidat), jen `soubor` je kopie s upravenym obsahem; tmp/webapp = webapp kandidata (GLB desky 12 mm)."""
    os.makedirs(os.path.join(tmp, "api"))
    os.symlink(os.path.realpath(os.path.join(KANDIDAT, "webapp")), os.path.join(tmp, "webapp"))
    for jm in os.listdir(os.path.join(KANDIDAT, "repo")):                    # ostatni polozky korene repa (scripts, docs, ...): moduly api je hledaji relativne k api/..
        if jm not in ("api", "webapp") and not os.path.lexists(os.path.join(tmp, jm)):
            os.symlink(os.path.realpath(os.path.join(KANDIDAT, "repo", jm)), os.path.join(tmp, jm))
    for jm in os.listdir(ZDROJ):
        if jm in ("__pycache__",) or jm.startswith("tmp_"):
            continue
        cil = os.path.join(tmp, "api", jm)
        zdroj = os.path.join(ZDROJ, jm)
        if jm == soubor:
            with open(cil, "w", encoding="utf-8") as f:
                f.write(obsah)
        else:
            os.symlink(os.path.realpath(zdroj) if os.path.islink(zdroj) else zdroj, cil)


def spust_jeden(tmp, druh):
    env = dict(os.environ, STUL_API_OVERRIDE=os.path.join(tmp, "api"), HPOL_PRVNI_CHYBA="1")
    if druh in ("core", "sikma"):
        cmd = [PY, TEST_CORE if druh == "core" else TEST_SIKMA]
    else:
        cmd = ["systemd-run", "--pipe", "--wait", "--quiet", "--property=EnvironmentFile=" + ENV_SOUBOR, "--setenv=HOME=/root", "--setenv=HPOL_PRVNI_CHYBA=1",
               "--setenv=STUL_API_OVERRIDE=" + env["STUL_API_OVERRIDE"], "--working-directory=" + os.path.join(KANDIDAT, "repo"), PY, TEST_SHOP]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=1500, env=env, cwd=os.path.join(KANDIDAT, "repo"))
    except subprocess.TimeoutExpired:
        return 124, ["TIMEOUT"]
    vystup = (p.stdout or "") + (p.stderr or "")
    selhalo = re.findall(r"^\s*CHYBA: (.{0,110})", vystup, re.M)[:2] + re.findall(r"^Traceback.*\n(?:.*\n){0,14}?(\w*(?:Error|Chyba)[^\n]{0,70})", vystup, re.M)[:1]
    if p.returncode != 0 and not selhalo:
        if "Traceback (most recent call last)" in vystup:                    # mutace shodila test vyjimkou (napr. ZeroDivisionError, KeyError na platnem vstupu) = chycena padem
            posledni = [r_ for r_ in vystup.splitlines() if r_.strip()][-1].strip()[:110]
            return p.returncode, ["PAD: " + posledni]
        return 99, ["BEH SELHAL BEZ VYPISU (rc=%d): %s" % (p.returncode, " ".join(vystup.split())[-140:])]      # napr. systemd-run nenastartoval jednotku (chybejici EnvironmentFile): to NENI chycena mutace
    return p.returncode, selhalo


def spust(tmp, druh):
    """Pusti testy v poradi PORADI_TESTU[druh] az do prvniho selhani; vraci (rc, co selhalo, ktery test mutaci chytil)."""
    rc, selhalo = 0, []
    for d in PORADI_TESTU[druh]:
        rc, selhalo = spust_jeden(tmp, d)
        if rc != 0:
            return rc, selhalo, d                                            # rc == 99: beh testu selhal (ne mutace chycena) - vyhodnoti se jako CHYBA BEHU
    return rc, selhalo, None


def priprav(mid, soubor, nahrady):
    with open(os.path.join(ZDROJ, soubor), encoding="utf-8") as f:
        kod = f.read()
    for stary, novy in nahrady:
        if kod.count(stary) != 1:
            return None, "vzor se v %s nenasel prave jednou (%d x): %r" % (soubor, kod.count(stary), stary[:90])
        kod = kod.replace(stary, novy)
    return kod, None


def jedna(m):
    mid, popis, soubor, nahrady, druh = m
    kod, chyba = priprav(mid, soubor, nahrady)
    if chyba:
        return mid, popis, None, [chyba], None
    tmp = tempfile.mkdtemp(prefix="police_mut_")
    try:
        postav(os.path.join(tmp, "k"), soubor, kod)
        rc, selhalo, kdo = spust(os.path.join(tmp, "k"), druh)
        if rc == 99:
            rc = None
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return mid, popis, rc, selhalo, kdo


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    j = int(sys.argv[sys.argv.index("-j") + 1]) if "-j" in sys.argv else 2
    if "-j" in sys.argv:
        args = [a for a in args if a != str(j)]
    vybrane = set(args)
    seznam = [m for m in MUTACE if not vybrane or m[0] in vybrane]
    if "--kotvy" in sys.argv:
        zle = 0
        for mid, popis, soubor, nahrady, druh in seznam:
            kod, chyba = priprav(mid, soubor, nahrady)
            if chyba:
                zle += 1
                print(mid, "CHYBA KOTVY:", chyba)
        print("kotvy: %d mutaci, %d spatnych" % (len(seznam), zle))
        return 1 if zle else 0
    chycene, nechycene, ekviv = [], [], []
    with concurrent.futures.ThreadPoolExecutor(max_workers=j) as ex:
        for mid, popis, rc, selhalo, kdo in ex.map(jedna, seznam):
            if rc is None:
                nechycene.append(mid)
                print("%s CHYBA BEHU / MUTACE: %s" % (mid, selhalo[0]))
            elif rc != 0:
                chycene.append(mid)
                print("%s CHYCENA   [%s] %-72s -> %s" % (mid, kdo, popis, " | ".join(selhalo) or "rc=%d" % rc))
            elif mid in EKVIVALENTNI:
                ekviv.append(mid)
                print("%s EKVIVALENTNI %-72s (%s)" % (mid, popis, EKVIVALENTNI[mid]))
            else:
                nechycene.append(mid)
                print("%s NECHYCENA %-72s (zadny test neselhal i s chybou!)" % (mid, popis))
            sys.stdout.flush()
    print("\nSOUHRN: chyceno %d, ekvivalentni %d%s, nechyceno %d%s" % (len(chycene), len(ekviv), (" (" + ", ".join(ekviv) + ")") if ekviv else "", len(nechycene), (" (" + ", ".join(nechycene) + ")") if nechycene else ""))
    return 0 if not nechycene else 1


if __name__ == "__main__":
    sys.exit(main())
