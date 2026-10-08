#!/usr/bin/env python3
"""Mutacni kontrola testu PRICEK DO MULTIBOXU (bot8, 2026-10-07): testy musi chytit kazdou zamerne vnesenou chybu v api/nabidka_pricky.py, v3d_glb.py, v3d_merge.py, scene_offers.py a orders.py.
Mutace se NEDELAJI v zivem stromu: pro kazdou se zkopiruje slozka kandidatu (KANDIDAT = adresar s temito soubory, vychozi zive api/), v kopii se jeden soubor zmeni a pusti se prislusny test
(core = test_pricky.py, spec = test_spec_mbx.py, merge = test_merge_mbx.py, db = test_pricky_backend.py pres systemd-run s DB prihlasenim). Mutace je "chycena", kdyz test skonci nenulovym kodem.
Nejdriv se overi, ze NEMUTOVANY zaklad vsemi testy projde (jinak by kazda mutace byla "chycena" omylem).

Spusteni (z korene repa, jako root):  KANDIDAT=/cesta/k/api FIX=/cesta/k/fixtures api/venv/bin/python3 scripts/2026-10-07_multibox_pricky/mutace_pricky.py [m01 s03 ... | core | db]
Konci kodem 0 jen kdyz jsou chycene VSECHNY."""
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.environ.get("MUT_REPO") or os.path.abspath(os.path.join(HERE, "..", ".."))        # MUT_REPO: jen pro vyvoj mimo repo
KAND = os.environ.get("KANDIDAT") or os.path.join(REPO, "api")
FIX = os.environ.get("FIX") or os.path.join(HERE, "fixtures")
PY = os.path.join(REPO, "api", "venv", "bin", "python3")
NP, GL, MG, SO, OR = "nabidka_pricky.py", "v3d_glb.py", "v3d_merge.py", "scene_offers.py", "orders.py"

# (id, popis, soubor, [(puvodni, nove)], test)
MUTACE = [
    ('m01', 'sloty 395 mm jen 5 misto 6', 'nabidka_pricky.py', [('("395", 380.0, 410.0, 395.5, 6)', '("395", 380.0, 410.0, 395.5, 5)')], 'core'),
    ('m02', 'sloty 288 mm 5 misto 4', 'nabidka_pricky.py', [('("288", 270.0, 310.0, 288.0, 4)', '("288", 270.0, 310.0, 288.0, 5)')], 'core'),
    ('m03', 'sloty 500 mm 6 misto 8', 'nabidka_pricky.py', [('("500", 480.0, 520.0, 500.0, 8)', '("500", 480.0, 520.0, 500.0, 6)')], 'core'),
    ('m04', 'vyber slotu bez zaokrouhleni nahoru (podlaha)', 'nabidka_pricky.py', [('int(math.floor(i * (S + 1) / (n + 1) + 0.5))', 'int(math.floor(i * (S + 1) / (n + 1)))')], 'core'),
    ('m05', 'rozteč slotu dela S misto S + 1 (posledni pricka mimo studnu)', 'nabidka_pricky.py', [('pitch = (x1 - x0) / (S + 1)\n    y = DNO', 'pitch = (x1 - x0) / S\n    y = DNO')], 'core'),
    ('m06', 'pricky do vykroje (studna zacina u 0)', 'nabidka_pricky.py', [('STUDNA_OD = 28.4 ', 'STUDNA_OD = 0.0 ')], 'core'),
    ('m10', 'over_vyber neodmitne neznamy box', 'nabidka_pricky.py', [('        if b is None:\n            raise ValueError("neznamy box %s" % bid)', '        if b is None:\n            continue')], 'core'),
    ('m11', 'over_vyber neodmitne pocet pricek nad pocet slotu', 'nabidka_pricky.py', [('        if not (0 <= n <= max_pricek(b["k"])):\n            raise ValueError("box %s: pocet pricek %d mimo 0..%d" % (bid, n, max_pricek(b["k"])))\n', '')], 'core'),
    ('m13', 'typ boxu: sirka 91 a 186 prohozene', 'nabidka_pricky.py', [('TRIDY_SIRKY = (("186", 183.0, 189.0, 186.0), ("91", 88.0, 95.0, 91.0))', 'TRIDY_SIRKY = (("91", 183.0, 189.0, 186.0), ("186", 88.0, 95.0, 91.0))')], 'core'),
    ('m14', 'spocti nescita ceny skupin (jen prvni skupina)', 'nabidka_pricky.py', [('    for sk in sorted(skupiny, key=lambda x: int(x["id"][1:])):\n        v = {bid', '    for sk in sorted(skupiny, key=lambda x: int(x["id"][1:]))[:1]:\n        v = {bid')], 'core'),
    ('m15', 'spocti bere z kazde skupiny jen prvni box', 'nabidka_pricky.py', [('        for bid, n in v.items():\n            d = dil_boxu', '        for bid, n in list(v.items())[:1]:\n            d = dil_boxu')], 'core'),
    ('m17', 'archivovana karta se bere jako aktivni', 'nabidka_pricky.py', [('"aktivni": bool(r["active"]) and not r["is_archived"]}', '"aktivni": bool(r["active"])}')], 'core'),
    ('m18', 'boxy bez skupiny se nezaradi do s0 (ale do s1)', 'nabidka_pricky.py', [('s = b.get("s") if type(b.get("s")) is int and b.get("s") >= 0 else 0', 's = b.get("s") if type(b.get("s")) is int and b.get("s") >= 0 else 1')], 'core'),
    ('m21', 'vyber_retezec nerazeny podle cisla (text)', 'nabidka_pricky.py', [('sorted(vyber.items(), key=lambda kv: int(kv[0][1:]))', 'sorted(vyber.items())')], 'core'),
    ('m22', 'rozpoznej_set: smisena skupina se bere jako plny set', 'nabidka_pricky.py', [('    return "vlastni"\n\n\ndef spocti', '    return "pln"\n\n\ndef spocti')], 'core'),
    ('m23', "rozpoznej_set: skupina bez pricek neni 'bez'", 'nabidka_pricky.py', [('    if not any(pocty):\n        return "bez"\n', '')], 'core'),
    ('m25', 'pocty_typu bez maximalniho poctu', 'nabidka_pricky.py', [('for n in range(0, max_pricek(k) + 1)]', 'for n in range(0, max_pricek(k))]')], 'core'),
    ('m26', 'payload bez klice dil u typu', 'nabidka_pricky.py', [('"dil": dil_boxu(k), ', '')], 'core'),
    ('m27', 'poznamka po_boxech bez nul (posunute poradi)', 'nabidka_pricky.py', [('"po_boxech": [vyber.get(bid, 0) for bid in sk["boxy"]]', '"po_boxech": [vyber[bid] for bid in sk["boxy"] if vyber.get(bid)]')], 'core'),
    ('v01', 'validate_spec neoveri e (povoli 5)', 'v3d_glb.py', [('        if type(e) is not int or e not in (-1, 1):\n            raise V3DError("%s.e: povoleno -1 nebo 1" % w)', '        pass')], 'spec'),
    ('v02', 'validate_spec povoli duplicitni id boxu', 'v3d_glb.py', [('        if bid in seen_b:\n            raise V3DError("%s.id: duplicitni %s" % (w, bid))', '        pass')], 'spec'),
    ('v03', 'odkazy na pivoty nezahrnuji mbx', 'v3d_glb.py', [('    for b in spec.get("mbx", []):\n        if b.get("p"):\n            refs.add(b["p"])\n', '')], 'spec'),
    ('v04', 'validate_spec neoveri skupinu s (povoli 0)', 'v3d_glb.py', [('bo["s"] = _int_in(b["s"], 1, _MAX_N, w + ".s")', 'bo["s"] = b["s"]')], 'spec'),
    ('v05', 'validate_spec povoli cizi klic v mbx', 'v3d_glb.py', [('_keys(b, ("id", "min", "max", "e"), ("p", "g", "n", "s", "sk"), w)', '_keys(b, ("id", "min", "max", "e"), ("p", "g", "n", "s", "sk", "jmeno"), w)')], 'spec'),
    ('v06', 'validate_spec povoli min > max', 'v3d_glb.py', [('        if any(b_min[j] > b_max[j] or b_max[j] - b_min[j] > _LIM_MBX_MM for j in range(3)):', '        if False:')], 'spec'),
    ('g01', 'slouceni neprecisluje pivot boxu', 'v3d_merge.py', [('                nb["p"] = piv[nb["p"]]\n            nb["id"]', '                pass\n            nb["id"]')], 'merge'),
    ('g02', 'slouceni neposouva cisla skupin', 'v3d_merge.py', [('                nb["s"] = int(nb["s"]) + max_sk', '                pass')], 'merge'),
    ('g03', 'slouceni nenavazuje id boxu', 'v3d_merge.py', [('nb["id"] = "b%02d" % (int(mt.group(1)) + max_bid)', 'nb["id"] = "b%02d" % int(mt.group(1))')], 'merge'),
    ('g04', 'slouceni nepise stranu g', 'v3d_merge.py', [('            if gs is not None:\n                nb["g"] = gs\n            if "n" in nb:', '            if "n" in nb:')], 'merge'),
    ('g05', 'slouceni zahodi multiboxy', 'v3d_merge.py', [('    if mbx:\n        spec["mbx"] = mbx\n', '')], 'merge'),
    ('s01', 'celkova cena bez pricek', 'scene_offers.py', [('    items_net += float((prefs or {}).get("pricky_net") or 0.0) * qty\n', '')], 'db'),
    ('s02', 'pricky se nenasobi poctem kusu', 'scene_offers.py', [('    items_net += float((prefs or {}).get("pricky_net") or 0.0) * qty\n', '    items_net += float((prefs or {}).get("pricky_net") or 0.0)\n')], 'db'),
    ('s04', 'QR ignoruje vyber (?pr=)', 'scene_offers.py', [('        if pr_res:\n            prefs_for_total["pricky_net"] = pr_res["net"]', '        pass')], 'db'),
    ('s05', 'QR prijme neplatny vyber', 'scene_offers.py', [('                except ValueError:\n                    return jsonify({"error": "Výběr příček není platný."}), 400', '                except ValueError:\n                    pr_res = None')], 'db'),
    ('s06', 'prijeti ignoruje vyber v celkove castce', 'scene_offers.py', [('            if pricky_res:\n                prefs_celkem["pricky_net"] = pricky_res["net"]', '            pass')], 'db'),
    ('s07', 'prijeti s neplatnym vyberem pokracuje', 'scene_offers.py', [('            except ValueError:\n                return jsonify({"error": "Výběr příček není platný, obnovte stránku."}), 400', '            except ValueError:\n                pricky_res = None')], 'db'),
    ('s10', 'verejny JSON bez bloku pricky', 'scene_offers.py', [('        "pricky": pricky_blok,\n', '')], 'db'),
    ('s11', 'objednavka bez radku pricek', 'scene_offers.py', [('                        extra_items=(pricky_res["radky"] if pricky_res else None),\n', '')], 'db'),
    ('s12', 'poznamka objednavky bez rozpisu pricek', 'scene_offers.py', [('            poznamky_objednavky = "\\n".join(x for x in (montaz_poznamka, pricky_poznamka) if x)', '            poznamky_objednavky = montaz_poznamka')], 'db'),
    ('s13', 'chyba modelu na disku shodi verejnou nabidku', 'scene_offers.py', [('    except Exception:                                       # noqa: BLE001 - chybejici / rozbity model = prislusenstvi se nenabizi, nabidka funguje dal\n        spec = None', '    except ZeroDivisionError:\n        spec = None')], 'db'),
    ('o01', 'radky pricek se nenasobi poctem kusu sestavy', 'orders.py', [('        q = int(it["qty"]) * mult\n', '        q = int(it["qty"])\n')], 'db'),
    ('o02', 'extra_items se nezapisou', 'orders.py', [('    for it in extra_items or []:\n', '    for it in []:\n')], 'db'),
    ('m07', 'uroven 2 = vsechny sloty (misto poloviny)', 'nabidka_pricky.py', [('2: lambda m: m // 2,', '2: lambda m: m,')], 'core'),
    ('m08', 'uroven 1 = 2 pricky', 'nabidka_pricky.py', [('1: lambda m: 1, 2:', '1: lambda m: 2, 2:')], 'core'),
    ('m09', 'uzky box pouziva dil 186 (cena i karta)', 'nabidka_pricky.py', [('    return "p186" if sirka_klic(k) == 186 else "p91"', '    return "p186"')], 'core'),
    ('m16', 'dostupne_boxy: admin nema nahled pred aktivaci', 'nabidka_pricky.py', [('(admin or vsechny_aktivni(ceny, potrebne))', 'vsechny_aktivni(ceny, potrebne)')], 'core'),
    ('m19', 'druh skupiny se nebere ze spec (vse jen box)', 'nabidka_pricky.py', [('        sk = "suplik" if k in TYPY_SUP else (DRUHY.get(b.get("sk"), "box") if DRUHY.get(b.get("sk")) != "suplik" else "box")', '        sk = "box"')], 'core'),
    ('m20', 'desky: pricka multiboxu ma tloustku 20 mm', 'nabidka_pricky.py', [('PRICKA_T = 2.0                                # tloustka', 'PRICKA_T = 20.0                               # tloustka')], 'core'),
    ('m24', 'vyber_ze_setu bere vzdy pocty plneho setu', 'nabidka_pricky.py', [('zip(sk["boxy"], sk["sety"][set_id]["po_boxech"])', 'zip(sk["boxy"], sk["sety"]["pln"]["po_boxech"])')], 'core'),
    ('s03', 'montaz se pocita bez pricek (poznamka)', 'scene_offers.py', [('pricky = float((prefs or {}).get("pricky_net") or 0.0) * qty', 'pricky = 0.0')], 'db'),
    ('s08', 'verejnost vidi i neaktivni skupiny (kontext bere admin sadu)', 'scene_offers.py', [('boxy = nabidka_pricky.dostupne_boxy(vse, ceny, True) if viewer_is_admin else verejne', 'boxy = nabidka_pricky.dostupne_boxy(vse, ceny, True)')], 'db'),
    ('s09', 'admin odkaz nema nahled pred aktivaci (kontext bere verejnou sadu)', 'scene_offers.py', [('boxy = nabidka_pricky.dostupne_boxy(vse, ceny, True) if viewer_is_admin else verejne', 'boxy = verejne')], 'db'),
    ('s14', 'poznamka objednavky bez poctu po boxech (vyroba nevi, kam co patri)', 'scene_offers.py', [("{', '.join(str(n) for n in p['po_boxech'])}", "{p['priccek']}")], 'db'),
    ('n01', 'podnos: vyska 137 mimo toleranci (typ se nepozna)', 'nabidka_pricky.py', [('("137", 135.5, 138.5, 137.0, 1.4)', '("137", 135.5, 136.0, 137.0, 1.4)')], 'core'),
    ('n02', 'podnos: sirka 950 mimo toleranci', 'nabidka_pricky.py', [('("950", 948.0, 952.0, 950.0, 11.7)', '("950", 948.0, 949.0, 950.0, 11.7)')], 'core'),
    ('n03', 'podnos: hloubka 384 mimo toleranci', 'nabidka_pricky.py', [('("384", 382.0, 386.0, 384.0, 0.5, 20.6)', '("384", 382.0, 383.0, 384.0, 0.5, 20.6)')], 'core'),
    ('n04', 'podnos: kombinace hloubka 384 x vyska 101 se nenabizi', 'nabidka_pricky.py', [('("332", "210"), ("384", "101"), ("384", "137")', '("332", "210"), ("384", "137")')], 'core'),
    ('n05', 'podnos: rozteč slotu 120 misto 100 mm', 'nabidka_pricky.py', [('SUP_ROZTEC = 100.0 ', 'SUP_ROZTEC = 120.0 ')], 'core'),
    ('n06', 'podnos: sloty nejsou souměrne kolem stredu sirky', 'nabidka_pricky.py', [('round(t["L"] / 2.0 + (j - (S + 1) / 2.0) * SUP_ROZTEC, 1)', 'round((j - 0.5) * SUP_ROZTEC, 1)')], 'core'),
    ('n07', 'podnos: pricka nestoji na podlaze (stred y bez podlahy)', 'nabidka_pricky.py', [('y = round(t["podlaha"] + t["pricka_v"] / 2.0, 1)', 'y = round(t["pricka_v"] / 2.0, 1)')], 'core'),
    ('n08', 'podnos: pricka uprostred AABB misto uprostred dutiny (z)', 'nabidka_pricky.py', [('z = round(t["cela"] + (t["W"] - t["cela"] - t["zad"]) / 2.0, 1)', 'z = round(t["W"] / 2.0, 1)')], 'core'),
    ('n09', 'podnos: pricka dlouha jako cela hloubka (zasahuje do lemu)', 'nabidka_pricky.py', [('"pricka_l": float(int(_h[3] - _h[4] - _h[5]))', '"pricka_l": float(_h[3])')], 'core'),
    ('n10', 'podnos: pricka sahá az k okraji (minus 0 mm)', 'nabidka_pricky.py', [('SUP_PRICKA_MINUS = 8.0 ', 'SUP_PRICKA_MINUS = 0.0 ')], 'core'),
    ('n11', 'podnos: dil pricky vzdy p186', 'nabidka_pricky.py', [('        return TYPY_SUP[k]["dil"]\n    return "p186" if', '        return "p186"\n    return "p186" if')], 'core'),
    ('n12', 'podnos: pocet slotu vzdy 4', 'nabidka_pricky.py', [('        return TYPY_SUP[k]["sloty"]', '        return 4')], 'core'),
    ('n13', 'podnos: os e = a (misto b)', 'nabidka_pricky.py', [('"druh": "suplik", "os": "b"', '"druh": "suplik", "os": "a"')], 'core'),
    ('n14', 'podnos: lem 28,4 v miniature', 'nabidka_pricky.py', [('"H": t["H"], "lem": 0.0}', '"H": t["H"], "lem": 28.4}')], 'core'),
    ('n15', 'multibox: vyska v geom typu 100', 'nabidka_pricky.py', [('"H": MB_VYSKA, "lem": STUDNA_OD}', '"H": 100.0, "lem": STUDNA_OD}')], 'core'),
    ('n16', 'gating: potrebne dily jen podle prvniho boxu skupiny', 'nabidka_pricky.py', [('potrebne = {dil_boxu(b["k"]) for b in bs}', 'potrebne = {dil_boxu(bs[0]["k"])}')], 'core'),
    ('n17', 'gating: verejnost vidi i neaktivni karty', 'nabidka_pricky.py', [('(admin or vsechny_aktivni(ceny, potrebne))', 'True')], 'core'),
    ('n18', 'payload: skryto vzdy False', 'nabidka_pricky.py', [('sk["skryto"] = any(bid not in ids_verejne for bid in sk["boxy"])', 'sk["skryto"] = False')], 'core'),
    ('n19', 'payload: banner podle parametru, ne podle skrytych skupin', 'nabidka_pricky.py', [('"nahled_admin": any(sk["skryto"] for sk in skupiny)', '"nahled_admin": bool(nahled_admin)')], 'core'),
    ('n20', 'payload: dily vsechny s cenou, ne jen pouzite', 'nabidka_pricky.py', [('for k in DILY if k in pouzite]', 'for k in DILY if k in ceny]')], 'core'),
    ('n21', 'druh skupiny: multibox se sk = 4 je suplik', 'nabidka_pricky.py', [('(DRUHY.get(b.get("sk"), "box") if DRUHY.get(b.get("sk")) != "suplik" else "box")', 'DRUHY.get(b.get("sk"), "box")')], 'core'),
    ('n22', 'spocti: slova vzdy jako u boxu', 'nabidka_pricky.py', [('sl = SLOVA["suplik" if sk["k"] == "suplik" else "box"]', 'sl = SLOVA["box"]')], 'core'),
    ('n23', "slova supliku: mistni pad 'boxech'", 'nabidka_pricky.py', [('"jednL": "šuplících"', '"jednL": "boxech"')], 'core'),
    ('n24', 'uroven 3 = m - 1 (ne vsechny sloty)', 'nabidka_pricky.py', [('3: lambda m: m}', '3: lambda m: m - 1}')], 'core'),
    ('n25', 'mix1: opacne poradi hustoty', 'nabidka_pricky.py', [('"mix1": lambda i, n: 3 if i % 2 == 0 else 1,', '"mix1": lambda i, n: 1 if i % 2 == 0 else 3,')], 'core'),
    ('n26', 'mix4: zaokrouhleni dolu', 'nabidka_pricky.py', [('1 + int(2.0 * i / (n - 1) + 0.5)', '1 + int(2.0 * i / (n - 1))')], 'core'),
    ('n27', 'sety se shodnymi pocty se nededuplikuji', 'nabidka_pricky.py', [('        if pocty in videne:\n            continue\n', '')], 'core'),
    ('n28', 'popis typu supliku: sirka a hloubka prohozene', 'nabidka_pricky.py', [('"Šuplík %d × %d mm, výška %d mm" % (t["L"], t["W"], t["H"])', '"Šuplík %d × %d mm, výška %d mm" % (t["W"], t["L"], t["H"])')], 'core'),
    ('n29', 'nazev dilu supliku: hloubka a vyska prohozene', 'nabidka_pricky.py', [('"nazev": "Příčka do ocelového šuplíku, hloubka %s mm, výška %s mm" % _hv', '"nazev": "Příčka do ocelového šuplíku, hloubka %s mm, výška %s mm" % (_hv[1], _hv[0])')], 'core'),
    ('n30', 'nacti_ceny bere jen prvni dva SKU', 'nabidka_pricky.py', [('    skus = list(SKU_NA_KLIC)\n', '    skus = list(SKU_NA_KLIC)[:2]\n')], 'core'),
    ('n31', 'boxy_ze_spec: typ podnosu se nepozna (jen multiboxy)', 'nabidka_pricky.py', [('    if abs(dy - MB_VYSKA) > 2.0:  ', '    if False:  ')], 'core'),
    ('v07', 'validate_spec: sk jen 1..3 (podnosy odmitnuty)', 'v3d_glb.py', [('bo["sk"] = _int_in(b["sk"], 1, 4, w + ".sk")', 'bo["sk"] = _int_in(b["sk"], 1, 3, w + ".sk")')], 'spec'),
    ('v08', 'validate_spec: sk 1..9 (neznamy druh povolen)', 'v3d_glb.py', [('bo["sk"] = _int_in(b["sk"], 1, 4, w + ".sk")', 'bo["sk"] = _int_in(b["sk"], 1, 9, w + ".sk")')], 'spec'),
    ('s20', "poznamka: nadpis vzdy 'do multiboxu'", 'scene_offers.py', [('    nadpis = "Příčky do multiboxů a šuplíků" if len(druhy) > 1 else ("Příčky do šuplíků" if druhy == {"Šuplík"} else "Příčky do multiboxů")', '    nadpis = "Příčky do multiboxů"')], 'db'),
    ('s21', "poznamka: jednotka vzdy 'boxu'", 'scene_offers.py', [("{p.get('jednotka') or 'boxů'}", 'boxů')], 'db'),
    ('s22', "poznamka: oznaceni vzdy 'Multibox'", 'scene_offers.py', [("{p.get('oznaceni') or 'Multibox'}", 'Multibox')], 'db'),
    ('s23', "poznamka: mistni pad vzdy 'boxech'", 'scene_offers.py', [("{p.get('jednotkaL') or 'boxech'}", 'boxech')], 'db'),
    ('b01', 'build: orientace celo (e) obracene', 'vandr_offer_build.py', [('"e": 1 if g_min < g_max else -1}', '"e": -1 if g_min < g_max else 1}')], 'build'),
    ('b02', 'build: drobne dily pod Default (kovani) se hlasi jako neznamy podnos', 'vandr_offer_build.py', [('    if max(float(sz[0]), float(sz[2])) < 300.0 or float(sz[1]) < 90.0:         # drobne dily pod "Default" (kovani, vodici listy) nejsou podnosy - bez varovani\n        return None\n', '')], 'build'),
    ('b03', 'build: vsechny podnosy v jedne skupine', 'vandr_offer_build.py', [('    return (predek.name if predek is not None else "suplik"), 4', '    return "suplik", 4')], 'build'),
    ('b04', 'build: podnosy maji druh skupiny 3', 'vandr_offer_build.py', [('    return (predek.name if predek is not None else "suplik"), 4', '    return (predek.name if predek is not None else "suplik"), 3')], 'build'),
    ('b05', 'build: kombinace hloubka x vyska bez 384 x 101 (podnosy 950 x 384 x 101 se neodevzdaji)', 'vandr_offer_build.py', [('_SUP_KOMB = {(332, 137), (332, 210), (384, 101), (384, 137), (384, 210)}', '_SUP_KOMB = {(332, 137), (332, 210), (384, 137), (384, 210)}')], 'build'),
]

TESTY = {
    "core": lambda d: [PY, os.path.join(HERE, "test_pricky.py"), d],
    "spec": lambda d: [PY, os.path.join(HERE, "test_spec_mbx.py"), d, FIX],
    "merge": lambda d: [PY, os.path.join(HERE, "test_merge_mbx.py"), d, FIX],
    "db": lambda d: ["systemd-run", "--pipe", "--wait", "--quiet", "--property=EnvironmentFile=" + os.path.join(REPO, "api", ".env"), "--setenv=HOME=/root", "--setenv=PRICKY_CAND=" + d,
                     "--setenv=PRICKY_FIX=" + FIX, "--working-directory=" + REPO, PY, os.path.join(HERE, "test_pricky_backend.py")],
}
BU = "vandr_offer_build.py"
BUILD_KARTY = ("4921", "4968")                                   # podnosy e = +1 (modely 4921) a otocena instalace e = -1 s drobnymi dily pod Default (4968)
KAND_V3D = os.environ.get("KANDIDAT_V3D") or os.path.join(REPO, "scripts", "v3d")                     # slozka scripts/v3d kandidata (vandr_offer_build.py, offer_model.py ...)
KAND_TESTY = os.environ.get("KANDIDAT_TESTY") or os.path.join(REPO, "scripts", "2026-10-02_v3d_testy")   # testy 3D nabidky s ctx fixturami (ctx_4921, ctx_4968)


def spust(klic, slozka):
    r = subprocess.run(TESTY[klic](slozka), capture_output=True, text=True, timeout=900)
    return r.returncode, (r.stdout + r.stderr)


def kopie():
    d = tempfile.mkdtemp(prefix="mut_pricky_")
    for f in (NP, GL, MG, SO, OR):
        shutil.copy(os.path.join(KAND, f), os.path.join(d, f))
    return d


def strom_build(text_buildu):
    """Kandidatni strom pro build karet: api/ a scripts/ jako symlinky na repo, krome 5 kandidatnich api souboru, scripts/v3d (kopie s UPRAVENYM vandr_offer_build.py) a testu 3D nabidky (fixtury)."""
    t = tempfile.mkdtemp(prefix="mut_build_")
    os.makedirs(os.path.join(t, "api"))
    os.makedirs(os.path.join(t, "scripts"))
    for f in os.listdir(os.path.join(REPO, "api")):
        if f not in (NP, GL, MG, SO, OR):
            os.symlink(os.path.join(REPO, "api", f), os.path.join(t, "api", f))
    for f in (NP, GL, MG, SO, OR):
        shutil.copy(os.path.join(KAND, f), os.path.join(t, "api", f))
    for f in os.listdir(os.path.join(REPO, "scripts")):
        if f not in ("v3d", "2026-10-02_v3d_testy"):
            os.symlink(os.path.join(REPO, "scripts", f), os.path.join(t, "scripts", f))
    shutil.copytree(KAND_V3D, os.path.join(t, "scripts", "v3d"), ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(KAND_TESTY, os.path.join(t, "scripts", "2026-10-02_v3d_testy"), ignore=shutil.ignore_patterns("__pycache__"))
    for f in os.listdir(REPO):
        if f not in ("api", "scripts"):
            os.symlink(os.path.join(REPO, f), os.path.join(t, f))
    if text_buildu is not None:
        open(os.path.join(t, "scripts", "v3d", BU), "w", encoding="utf-8").write(text_buildu)
    return t


def spust_build(text_buildu):
    """Postavi BUILD_KARTY ve stromu s (upravenym) buildem a pusti test_build_mbx.py nad vystupem; vraci (rc, vystup)."""
    t = strom_build(text_buildu)
    out = tempfile.mkdtemp(prefix="mut_build_out_")
    try:
        env = dict(os.environ, V3D_TEST_OUT=out, FORCE="1", PRICKY_API=KAND, PYTHONDONTWRITEBYTECODE="1")
        env.pop("V3D_TEST_REPO", None)
        b = subprocess.run([PY, os.path.join(t, "scripts", "2026-10-02_v3d_testy", "build_karty.py")] + list(BUILD_KARTY), capture_output=True, text=True, timeout=900, env=env)
        if b.returncode != 0:
            return 0 if False else 1, "BUILD SELHAL (mutace shodila build): " + (b.stdout + b.stderr)[-400:]
        r = subprocess.run([PY, os.path.join(HERE, "test_build_mbx.py")], capture_output=True, text=True, timeout=900, env=env)
        return r.returncode, (r.stdout + r.stderr)
    finally:
        shutil.rmtree(t, ignore_errors=True)
        shutil.rmtree(out, ignore_errors=True)


def main():
    vyber = [a for a in sys.argv[1:]]
    chtene = [m for m in MUTACE if not vyber or m[0] in vyber or m[4] in vyber]
    druhy = {m[4] for m in chtene}
    print("== zaklad (nemutovany kandidat) ==")
    z = kopie()
    for k in sorted(druhy):
        rc, out = spust_build(None) if k == "build" else spust(k, z)
        print("  zaklad %-5s: %s" % (k, "OK" if rc == 0 else "SELHAL (rc=%d) - mutace by nebyly spolehlive\n%s" % (rc, out[-600:])))
        if rc != 0:
            return 2
    shutil.rmtree(z, ignore_errors=True)
    nechycene = []
    for mid, popis, soubor, zmeny, test in chtene:
        if test == "build":
            s = open(os.path.join(KAND_V3D, soubor), encoding="utf-8").read()
            for a, b in zmeny:
                if s.count(a) != 1:
                    print("  %s CHYBA MUTACE: kotva se v %s nenasla jednou (%d x): %r" % (mid, soubor, s.count(a), a[:70]))
                    return 3
                s = s.replace(a, b)
            rc, out = spust_build(s)
        else:
            d = kopie()
            p = os.path.join(d, soubor)
            s = open(p, encoding="utf-8").read()
            for a, b in zmeny:
                if s.count(a) != 1:
                    print("  %s CHYBA MUTACE: kotva se v %s nenasla jednou (%d x): %r" % (mid, soubor, s.count(a), a[:70]))
                    return 3
                s = s.replace(a, b)
            open(p, "w", encoding="utf-8").write(s)
            rc, out = spust(test, d)
            shutil.rmtree(d, ignore_errors=True)
        selhalo = [r for r in out.splitlines() if r.startswith(("[CHYBA]", "FAIL", "BUILD SELHAL"))][:2]
        if rc != 0:
            print("  %s CHYCENA   (%s) %s | %s" % (mid, test, popis, "; ".join(x[:80] for x in selhalo) or "neosetrena chyba/vyjimka"))
        else:
            print("  %s NECHYCENA (%s) %s" % (mid, test, popis))
            nechycene.append(mid)
    print("\nchyceno %d z %d, nechyceno: %s" % (len(chtene) - len(nechycene), len(chtene), nechycene or "zadna"))
    return 1 if nechycene else 0


if __name__ == "__main__":
    sys.exit(main())
