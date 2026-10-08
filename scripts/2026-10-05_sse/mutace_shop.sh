#!/usr/bin/env bash
# Mutace verejneho API SSE (kazda chyba MUSI shodit test_sse_shop.py; DB jen cte). Spusti mutace po davkach (DB), vypise souhrn.
cd "$(dirname "$0")"
M() { ./mutuj_sse_db.sh "$@" & }
M s01_recept_system stul_shop.py 's = s.replace("RECEPT_SSE: 41}", "RECEPT_SSE: 40}")'
M s02_mid_ceil stul_shop_sse.py 's = s.replace("mn = max(5, math.ceil((lo - zl) / span * 100 - 1e-9))", "mn = max(5, math.floor((lo - zl) / span * 100 - 1e-9))")'
M s03_rozsah_d stul_shop_sse.py 's = s.replace("(\"d\", \"hloubka\"), (\"h\", \"vyska\")):\n        options[sid] = {\"min\": int(rz[par][0])", "(\"d\", \"hloubka\"), (\"h\", \"vyska\")):\n        options[sid] = {\"min\": int(S.ROZSAH[par][0])").replace("options[sid] = {\"min\": int(S.ROZSAH[par][0]), \"max\": int(rz[par][1])}", "options[sid] = {\"min\": int(S.ROZSAH[par][0]), \"max\": int(S.ROZSAH[par][1])}")'
M s04_bez_oznameni stul_shop_sse.py 's = s.replace("for o in gen[\"odebrano\"] if o[\"volba\"] == \"suplik\"]", "for o in []]")'
M s05_cache_klic stul_shop.py 's = s.replace("S.pravidlo(\"cena_noha_sse_400\", p[\"system\"]), S.pravidlo(\"cena_noha_sse_1100\", p[\"system\"]))", "0, 0)")'
M s06_bom_sse stul_shop.py 's = s.replace("elif d[\"part_id\"] in (S.SSE_JEKL_PART, S.SSE_PROFIL_PART):", "elif False:")'
M s07_hmotnost stul_shop.py 's = s.replace("chybi = sorted(set(chybi) | {\"nohy SSE (hmotnost jen odhadem z rozměrů)\"})", "pass")'
M s08_vychozi stul_shop_sse.py 's = s.replace("VYCHOZI = {\"w\": 2000,", "VYCHOZI = {\"w\": 1800,")'
M s09_police_clamp stul_shop_sse.py 's = s.replace("\"police\": 1 if pravda(sel[\"shelf\"]) else 0,", "\"police\": int(SH._cislo(sel[\"shelf\"], 0, 5, 1, 1)),")'
M s10_neutralni stul_shop_sse.py 's = s.replace("    norm = SH.vychozi_vyber(SYSTEM)", "    norm = dict(sel)")'
M s11_vodici stul_shop_sse.py 's = s.replace("    gen[\"ovladani_scena\"] = S.ovladani_3d(gen)\n", "    gen[\"ovladani_scena\"] = {\"casti\": [], \"tahy\": []}\n")'
M s12_cena_delta stul_shop_sse.py 's = s.replace("        sh[\"price_delta\"] = delta(police=1)[0]", "        sh[\"price_delta\"] = 0")'
wait
