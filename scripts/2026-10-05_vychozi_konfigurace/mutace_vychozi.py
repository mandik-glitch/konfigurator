#!/usr/bin/env python3
"""Mutace VYCHOZI KONFIGURACE GENERATORU (bot8, 2026-10-05): kazda umyslna chyba v api/stul_api.py / api/stul_shop.py MUSI shodit test_vychozi.py (CHYCENA = dobre).
Kazda mutace dostane kandidatni kopii api/ (symlinky + jeden upraveny soubor, STUL_API_OVERRIDE), test bezi pres systemd-run (DB jen cte, zapis jde do falesne DB). Po 4 paralelne.

  api/venv/bin/python3 scripts/2026-10-05_vychozi_konfigurace/mutace_vychozi.py [nazev_mutace ...]"""
import concurrent.futures
import glob
import os
import shutil
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TEST = "scripts/2026-10-05_vychozi_konfigurace/test_vychozi.py"
ZDROJ = os.environ.get("MUT_ZDROJ_API") or os.path.join(REPO, "api")      # odkud se bere puvodni soubor a symlinky (vychozi zivy api/; kandidat pred nasazenim: MUT_ZDROJ_API=<cesta ke kandidatnimu api/>)

# (nazev, soubor v api/, puvodni text, nahrada)
MUTACE = [
    ("m01_cache_bez_kopie", "stul_api.py", "        return dict(c[1]) if c[1] else None\n    sel = None", "        return c[1]\n    sel = None"),
    ("m02_cache_bez_ttl", "stul_api.py", "ted - c[0] < VYCHOZI_TTL_S:\n        return dict(c[1])", "ted - c[0] < 10 ** 9:\n        return dict(c[1])"),
    ("m03_chybny_json_vyhodi", "stul_api.py", "    except Exception as e:                                           # noqa: BLE001\n        app.logger.warning(\"stul: ulozena vychozi", "    except KeyError as e:                                           # noqa: BLE001\n        app.logger.warning(\"stul: ulozena vychozi"),
    ("m04_over_bez_nazvu", "stul_api.py", "not re.fullmatch(r\"[a-z0-9_]{1,40}\", k)", "False"),
    ("m05_over_prazdny_ok", "stul_api.py", "if not isinstance(sel, dict) or not sel:\n        raise ValueError(\"vychozi konfigurace musi", "if not isinstance(sel, dict):\n        raise ValueError(\"vychozi konfigurace musi"),
    ("m06_over_pole_ok", "stul_api.py", "if v is not None and not isinstance(v, (bool, int, float, str)):", "if False:"),
    ("m07_over_nan_ok", "stul_api.py", "if isinstance(v, float) and not math.isfinite(v):", "if False:"),
    ("m08_klic_vsem_stejny", "stul_api.py", "return f\"{VYCHOZI_KLIC}{int(product_id)}\"", "return f\"{VYCHOZI_KLIC}0\""),
    ("m09_smazani_nic", "stul_api.py", "            if sel is None:\n                cur.execute(\"DELETE FROM app_settings WHERE setting_key=%s\", (vychozi_klic(product_id),))", "            if sel is None:\n                pass"),
    ("m10_slij_bez_typu", "stul_shop.py", "        if k in out and _typ_sedi(zaklad[k], v):", "        if k in out:"),
    ("m11_slij_neznamy_klic", "stul_shop.py", "        if k in out and _typ_sedi(zaklad[k], v):", "        if True:"),
    ("m12_slij_bool_jako_cislo", "stul_shop.py", "return isinstance(hodnota, (int, float)) and not isinstance(hodnota, bool)\n    if isinstance(zaklad, str):", "return isinstance(hodnota, (int, float))\n    if isinstance(zaklad, str):"),
    ("m13_schema_bez_slouceni", "stul_shop.py", "    if ul:\n        out[\"default_selection\"] = slij_vychozi(out[\"default_selection\"], ul)", "    if False:\n        out[\"default_selection\"] = slij_vychozi(out[\"default_selection\"], ul)"),
    ("m14_schema_default_saved", "stul_shop.py", "    out[\"default_saved\"] = bool(ul)", "    out[\"default_saved\"] = False"),
    ("m15_put_bez_prava", "stul_shop.py", "@app.put(\"/api/shop/products/<int:product_id>/configurator/default\")\n@require_permission(\"nastaveni\", \"upravit\")\n", "@app.put(\"/api/shop/products/<int:product_id>/configurator/default\")\n"),
    ("m16_delete_bez_prava", "stul_shop.py", "@app.delete(\"/api/shop/products/<int:product_id>/configurator/default\")\n@require_permission(\"nastaveni\", \"upravit\")\n", "@app.delete(\"/api/shop/products/<int:product_id>/configurator/default\")\n"),
    ("m17_put_bez_404", "stul_shop.py", "    if not konfigurovatelny(product_id):\n        return _nenalezeno()\n    body = request.get_json(silent=True)\n    sel = body.get(\"selection\")", "    body = request.get_json(silent=True)\n    sel = body.get(\"selection\")"),
    ("m18_delete_bez_404", "stul_shop.py", "    if not konfigurovatelny(product_id):\n        return _nenalezeno()\n    system = system_pro_produkt(product_id)\n    stul_api.uloz_vychozi(product_id, None)", "    system = system_pro_produkt(product_id)\n    stul_api.uloz_vychozi(product_id, None)"),
    ("m19_put_neplatna_ok", "stul_shop.py", "    if not r[\"valid\"]:\n        chyby = ", "    if False:\n        chyby = "),
    ("m20_put_409_na_400", "stul_shop.py", "\"errors\": chyby}), 409", "\"errors\": chyby}), 400"),
    ("m21_uloz_surovy_vyber", "stul_shop.py", "ulozeno = stul_api.uloz_vychozi(product_id, r[\"selection\"])", "ulozeno = stul_api.uloz_vychozi(product_id, sel)"),
    ("m22_put_bez_tvaru", "stul_shop.py", "    if not isinstance(sel, dict) or not sel:\n        return jsonify({\"error\": \"telo musi byt", "    if False:\n        return jsonify({\"error\": \"telo musi byt"),
    ("m23_put_bez_validace_tvaru", "stul_shop.py", "        stul_api.vychozi_over(sel)\n        r = resolve(sel, \"cs\", skryt_cenu=True, system=system)", "        r = resolve(sel, \"cs\", skryt_cenu=True, system=system)"),
    ("m24_audit_akce", "stul_shop.py", "log_audit(u[\"id\"] if u else None, \"update\", \"configurator_default\"", "log_audit(u[\"id\"] if u else None, \"create\", \"configurator_default\""),
    ("m25_bez_auditu_put", "stul_shop.py", "    u = current_user()\n    log_audit(u[\"id\"] if u else None, \"update\", \"configurator_default\", product_id, {\"system\": system, \"kod\": r[\"kod\"], \"selection\": ulozeno})\n", "    u = current_user()\n"),
    ("m26_odpoved_vestavene", "stul_shop.py", "\"default_selection\": slij_vychozi(vychozi_vyber(system), ulozeno), \"hash\"", "\"default_selection\": vychozi_vyber(system), \"hash\""),
    ("m27_delete_odpoved_saved", "stul_shop.py", "return jsonify({\"default_saved\": False, \"default_selection\": vychozi_vyber(system)})", "return jsonify({\"default_saved\": True, \"default_selection\": vychozi_vyber(system)})"),
    ("m28_hash_odpoved", "stul_shop.py", "\"hash\": r[\"hash\"], \"kod\": r[\"kod\"],\n                    \"notices\"", "\"hash\": \"x\", \"kod\": r[\"kod\"],\n                    \"notices\""),
    # 2026-10-07: ulozena vychozi konfigurace BEZ vzper (rameno nad prahem) vypina pravidlo auto_on u produktu
    ("m29_auto_on_nikdy_neodebrat", "stul_shop.py", "if a and ul.get(sl[\"id\"]) is False and isinstance(kdy, (int, float)) and not isinstance(kdy, bool) and kdy > a[\"when\"][\"above\"]:", "if False:"),
    ("m30_auto_on_vzdy_odebrat_s_ulozenim", "stul_shop.py", "if a and ul.get(sl[\"id\"]) is False and isinstance(kdy, (int, float)) and not isinstance(kdy, bool) and kdy > a[\"when\"][\"above\"]:", "if a:"),
    ("m31_auto_on_bez_kontroly_ramene", "stul_shop.py", " and isinstance(kdy, (int, float)) and not isinstance(kdy, bool) and kdy > a[\"when\"][\"above\"]:", ":"),
    ("m32_auto_on_prah_rovno", "stul_shop.py", "not isinstance(kdy, bool) and kdy > a[\"when\"][\"above\"]:", "not isinstance(kdy, bool) and kdy >= a[\"when\"][\"above\"]:"),
    ("m33_auto_on_falsy_misto_false", "stul_shop.py", "if a and ul.get(sl[\"id\"]) is False and isinstance(kdy", "if a and not ul.get(sl[\"id\"]) and isinstance(kdy"),
    ("m34_auto_on_typ_ramene", "stul_shop.py", " and isinstance(kdy, (int, float)) and not isinstance(kdy, bool) and kdy >", " and kdy >"),
    ("m35_auto_on_bez_kontroly_vzper", "stul_shop.py", "if a and ul.get(sl[\"id\"]) is False and isinstance(kdy", "if a and True and isinstance(kdy"),
]


def spust(m):
    nazev, soubor, puvodni, nahrada = m
    d = tempfile.mkdtemp(prefix="mut_vychozi_")
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
        p = subprocess.run(["systemd-run", "--pipe", "--wait", "--quiet", f"--property=EnvironmentFile={REPO}/api/.env", "--setenv=HOME=/root", f"--setenv=STUL_API_OVERRIDE={d}/api",
                            f"--working-directory={REPO}", f"{REPO}/api/venv/bin/python3", TEST], capture_output=True, text=True, timeout=900)
        return nazev, p.returncode, p.stdout.count("CHYBA")
    finally:
        shutil.rmtree(d, ignore_errors=True)


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
            print(f"mutace {nazev}: rc={rc} ({'CHYCENA' if chycena else 'NECHYCENA'})  {info} CHYBA")
            if not chycena:
                necytene.append(nazev)
    print(f"\n==> {len(seznam) - len(necytene)}/{len(seznam)} mutaci chyceno" + (f"; NECHYCENE / VADNE: {', '.join(necytene)}" if necytene else " - VSECHNY CHYCENY"))
    sys.exit(1 if necytene else 0)
