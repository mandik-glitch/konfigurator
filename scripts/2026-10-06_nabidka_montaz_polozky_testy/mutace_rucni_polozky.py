#!/usr/bin/env python3
"""Mutace backendu RUCNICH POLOZEK (bot8, 2026-10-06): kazda umyslna chyba v api/scene_offers.py MUSI shodit test_rucni_polozky_db.py (CHYCENA = dobre).
Kandidat = kopie scene_offers.py s jednou zmenou (SCENE_OFFERS_PY), test bezi pres systemd-run nad docasnymi tabulkami (nic se nezapisuje). Po 4 paralelne.
  api/venv/bin/python3 scripts/2026-10-06_nabidka_montaz_polozky_testy/mutace_rucni_polozky.py [nazev_mutace ...]"""
import concurrent.futures
import os
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TEST = "scripts/2026-10-06_nabidka_montaz_polozky_testy/test_rucni_polozky_db.py"
ZDROJ = open(os.path.join(REPO, "api", "scene_offers.py"), encoding="utf-8").read()

MUTACE = [
    ("m02_jmena_obycejnych", "len(obycejne_in) != len(obycejne_cur) or jmena(obycejne_in) != jmena(obycejne_cur)", "len(obycejne_in) != len(obycejne_cur)"),
    ("m03_rucni_na_konec", "return obycejne_in + hotove, None", "return hotove + obycejne_in, None"),
    ("m04_max_polozek", "if len(rucni_in) > MANUAL_ITEMS_MAX:", "if False:"),
    ("m05_klic_cizi_nabidky", "if not m or int(m.group(1)) != offer_id:\n        return None\n    return os.path.join(OFFER_IMAGES_DIR", "if not m:\n        return None\n    return os.path.join(OFFER_IMAGES_DIR"),
    ("m06_obrazek_existuje", "or not os.path.isfile(os.path.join(OFFER_IMAGES_DIR, str(k))):", "or False:"),
    ("m07_max_obrazku", "if not isinstance(obr, list) or len(obr) > MANUAL_IMAGES_MAX:", "if not isinstance(obr, list):"),
    ("m08_produkt_existuje", "        if not row:\n            raise ValueError(f\"{pre}: produkt #{pid} v katalogu neexistuje.\")", "        if not row:\n            row = {}"),
    ("m09_model_soubor", "if not glb or not os.path.isfile(os.path.join(KATALOG_GLB_DIR, glb)):", "if False:"),
    ("m10_total", "\"total\": int(qty * unit + 0.5)", "\"total\": int(unit)"),
    ("m11_mnozstvi_rozsah", "return int(_rucni_cislo(v, f\"{pre}: množství\", 1, MANUAL_QTY_MAX, cele=True))", "return int(_rucni_cislo(v, f\"{pre}: množství\", 0, 10 ** 9, cele=True))"),
    ("m12_cena_zaporna", "unit = _rucni_cislo(it.get(\"unit_price\"), f\"{pre}: cena za kus\", 0, MANUAL_PRICE_MAX)", "unit = _rucni_cislo(it.get(\"unit_price\"), f\"{pre}: cena za kus\", -10 ** 9, MANUAL_PRICE_MAX)"),
    ("m13_whitelist_klicu", "out = {\"name\": name, \"dim\": dim, \"qty\": f\"{qty} ks\",", "out = {**{k: v for k, v in it.items() if k != 'manual'}, \"name\": name, \"dim\": dim, \"qty\": f\"{qty} ks\","),
    ("m14_upload_magic", "if (jpeg and raw[:3] != b\"\\xff\\xd8\\xff\") or (not jpeg and raw[:8] != b\"\\x89PNG\\r\\n\\x1a\\n\"):", "if False:"),
    ("m15_upload_strop", ">= MANUAL_IMAGES_PER_OFFER_MAX:", ">= 10 ** 9:"),
    ("m16_upload_nabidka_existuje", "            if not cur.fetchone():\n                return jsonify({\"error\": \"Nabídka neexistuje.\"}), 404\n    finally:\n        conn.close()\n    predpona", "            pass\n    finally:\n        conn.close()\n    predpona"),
    ("m17_verejny_obrazek_odkaz", "if not path or not any(_je_rucni(it) and key in (it[\"manual\"].get(\"obrazky\") or []) for it in items):", "if not path:"),
    ("m18_verejny_obrazek_aktivni", "    if not offer or not offer[\"is_active\"] or offer[\"expires_at\"] < datetime.datetime.now():\n        return jsonify({\"error\": \"Nabídka nebyla nalezena.\"}), 404\n    path = _obrazek_polozky_cesta(offer[\"id\"], key)", "    if not offer:\n        return jsonify({\"error\": \"Nabídka nebyla nalezena.\"}), 404\n    path = _obrazek_polozky_cesta(offer[\"id\"], key)"),
    ("m19_model_priznak", "if not any(_je_rucni(it) and it[\"manual\"].get(\"model\") is True and it.get(\"product_id\") == product_id for it in items):", "if not any(_je_rucni(it) and it.get(\"product_id\") == product_id for it in items):"),
    ("m20_model_produkt", "and it[\"manual\"].get(\"model\") is True and it.get(\"product_id\") == product_id for it in items):", "and it[\"manual\"].get(\"model\") is True for it in items):"),
    ("m21_model_etag", "    return resp.make_conditional(request)\n\n\n@app.put", "    return resp\n\n\n@app.put"),
    ("m22_edit_data_priznak", "\"rucni_polozky\": {\"max\": MANUAL_ITEMS_MAX, \"obrazky_max\": MANUAL_IMAGES_MAX},", ""),
    ("m23_put_overeni", "            items, chyba_polozek = _over_rucni_polozky(cur, offer_id, items, items_cur)", "            chyba_polozek = None"),
    ("m24_katalog_vrstva", "out[\"layer\"] = \"produkt\"", "pass"),
    ("m25_model_flag_true", "if m.get(\"model\") is True:", "if m.get(\"model\"):"),
    ("m26_mnozstvi_prefix", "m = re.fullmatch(r\"\\s*(\\d{1,6})\\s*(?:ks)?\\s*\", v, re.IGNORECASE)", "m = re.match(r\"\\s*(\\d{1,6})\\s*(?:ks)?\\s*\", v, re.IGNORECASE)"),
    ("m27_qty_cislo", "\"qty\": f\"{qty} ks\", \"unit_price\": unit,", "\"qty\": qty, \"unit_price\": unit,"),
    ("m28_mnozstvi_velke_ks", "(?:ks)?\\s*\", v, re.IGNORECASE)", "(?:ks)?\\s*\", v)"),
    ("m29_oddelovac_tisicu", "float(re.sub(r\"[\\s\\u00a0\\u202f]+\", \"\", str(v)).replace(\",\", \".\"))", "float(str(v).replace(\",\", \".\"))"),
]


def spust(m):
    nazev, puvodni, nahrada = m
    if ZDROJ.count(puvodni) != 1:
        return nazev, None, f"puvodni text se nenasel prave jednou ({ZDROJ.count(puvodni)}x)"
    d = tempfile.mkdtemp(prefix="mut_rp_")
    cesta = os.path.join(d, "scene_offers.py")
    open(cesta, "w", encoding="utf-8").write(ZDROJ.replace(puvodni, nahrada))
    p = subprocess.run(["systemd-run", "--pipe", "--wait", "--quiet", f"--property=EnvironmentFile={REPO}/api/.env", "--setenv=HOME=/root", f"--setenv=SCENE_OFFERS_PY={cesta}",
                        f"--working-directory={REPO}", f"{REPO}/api/venv/bin/python3", TEST], capture_output=True, text=True, timeout=900)
    return nazev, p.returncode, p.stdout.count("FAIL")


if __name__ == "__main__":
    vyber = set(sys.argv[1:])
    seznam = [m for m in MUTACE if not vyber or m[0] in vyber]
    necytene = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
        for nazev, rc, info in ex.map(spust, seznam):
            if rc is None:
                print(f"mutace {nazev}: CHYBA MUTACE - {info}")
                necytene.append(nazev)
                continue
            chycena = rc != 0
            print(f"mutace {nazev}: rc={rc} ({'CHYCENA' if chycena else 'NECHYCENA'})  {info} FAIL")
            if not chycena:
                necytene.append(nazev)
    print(f"\n==> {len(seznam) - len(necytene)}/{len(seznam)} mutaci chyceno" + (f"; NECHYCENE / VADNE: {', '.join(necytene)}" if necytene else " - VSECHNY CHYCENY"))
    sys.exit(1 if necytene else 0)
