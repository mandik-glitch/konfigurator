#!/opt/konfigurator/api/venv/bin/python
"""Sazba montaze konfigurace podle typu sestavy (bot5, 2026-10-02): configurator_price.montaz_pct_for_assembly(cur, assembly_id).

Robert (pres bot3): montaz u stolu/skladovych sestav ANO, volitelne v %, sazbu nastavuje admin, auta beze zmeny. Sazba je radek v existujici tabulce
sestava_typ_sluzba (klic 'montaz', procento_z_ceny, aktivni) PRO TYP sestavy (STUL_SKLAD); typ AUTO a radky bez typu se nectou, nejasne = None (nenabidne se).
Docasne kopie product_assemblies a sestava_typ_sluzba (CREATE TEMPORARY TABLE ... LIKE), sestava_typ se jen cte. Do ostrych dat se nezapisuje.
Spusteni: systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator \\
  /opt/konfigurator/api/venv/bin/python3 scripts/2026-10-02_konfigurator_cena_testy/test_montaz_sazba.py     (kandidat: --setenv=CFG_PRICE_PY=...)
"""
import importlib.util
import os
import re
import sys

import pymysql

HERE = os.path.dirname(os.path.abspath(__file__))
API = os.path.abspath(os.path.join(HERE, "..", "..", "api"))
CFG = os.environ.get("CFG_PRICE_PY", os.path.join(API, "configurator_price.py"))
sys.path.insert(0, API)
spec = importlib.util.spec_from_file_location("configurator_price_test", CFG)
cp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cp)

vysl = []


def over(nazev, podminka, detail=None):
    vysl.append(bool(podminka))
    print(("OK   " if podminka else "FAIL ") + nazev + ("" if podminka else "  -> " + repr(detail)))


def spoj():
    return pymysql.connect(host=os.environ["DB_HOST"], user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"], database=os.environ["DB_NAME"],
                           port=int(os.environ.get("DB_PORT", 3306)), charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor)


def stav(c):
    with c.cursor() as cur:
        cur.execute("SELECT COUNT(*) AS n FROM sestava_typ_sluzba")
        a = cur.fetchone()["n"]
        cur.execute("SELECT COUNT(*) AS n FROM product_assemblies")
        return (a, cur.fetchone()["n"])


ostre = spoj()
pred = stav(ostre)
c = spoj()
try:
    with c.cursor() as cur:
        for t in ("product_assemblies", "sestava_typ_sluzba"):
            cur.execute(f"CREATE TEMPORARY TABLE `_tpl_{t}` LIKE `{t}`")
            cur.execute(f"CREATE TEMPORARY TABLE `{t}` LIKE `_tpl_{t}`")
            cur.execute(f"SHOW CREATE TABLE `{t}`")
            assert list(cur.fetchone().values())[1].startswith("CREATE TEMPORARY TABLE"), f"ABORT: {t} neni docasna"
        cur.execute("SELECT id, kod FROM sestava_typ")
        typy = {r["kod"]: r["id"] for r in cur.fetchall()}
        AUTO, STUL = typy["AUTO"], typy["STUL_SKLAD"]

        def sestava(id_, typ):
            cur.execute("INSERT INTO product_assemblies (id, name, data, sestava_typ_id) VALUES (%s,'t','{}',%s)", (id_, typ))

        def radek(typ, klic="montaz", mode="procento_z_ceny", hodnota=15, aktivni=1):
            cur.execute("INSERT INTO sestava_typ_sluzba (sestava_typ_id, klic, nazev, pricing_mode, hodnota, aktivni) VALUES (%s,%s,%s,%s,%s,%s)", (typ, klic, klic, mode, hodnota, aktivni))

        def smaz_radky():
            cur.execute("DELETE FROM sestava_typ_sluzba")

        def sazba(id_):
            return cp.montaz_pct_for_assembly(cur, id_)

        sestava(1001, STUL)
        sestava(1002, AUTO)
        sestava(1003, None)
        over("1 stul bez radku v sestava_typ_sluzba -> None (montaz se nenabizi)", sazba(1001) is None, sazba(1001))
        radek(STUL, hodnota=15)
        over("2 aktivni radek 'montaz' / procento_z_ceny / 15 pro typ STUL_SKLAD -> 15.0", sazba(1001) == 15.0 and isinstance(sazba(1001), float), sazba(1001))
        over("3 sestava do auta (typ AUTO) dostane None i kdyz existuje radek pro jiny typ; neexistujici sestava a sestava bez typu taky", sazba(1002) is None and sazba(9999999) is None and sazba(1003) is None, (sazba(1002), sazba(9999999), sazba(1003)))
        radek(AUTO, hodnota=30)
        radek(None, hodnota=40)
        over("4 radek pro typ AUTO a radek bez typu (vsechny typy) se nepouzivaji: auto dal None, stul dal 15", sazba(1002) is None and sazba(1001) == 15.0, (sazba(1002), sazba(1001)))
        for popis, kw in (("neaktivni", dict(aktivni=0)), ("informativni", dict(mode="informativni")), ("pevna castka", dict(mode="pevna_castka", hodnota=500)), ("jiny klic", dict(klic="doprava", hodnota=10))):
            smaz_radky()
            radek(STUL, **kw)
            over(f"5 radek '{popis}' neni sazba montaze -> None", sazba(1001) is None, sazba(1001))
        smaz_radky()
        for hodnota, cekano in ((0, None), (-5, None), (100.01, None), (None, None), (100, 100.0), (7.5, 7.5), (0.01, 0.01), (99.99, 99.99)):
            smaz_radky()
            radek(STUL, hodnota=hodnota)
            over(f"6 hodnota {hodnota!r} -> {cekano!r} (musi byt 0 < % <= 100, jinak se montaz nenabidne)", sazba(1001) == cekano, sazba(1001))
        smaz_radky()
        radek(STUL, hodnota=15)
        # navaznost na price_entries: montaz_czk = % z total_czk po balnem, montaz_pct_applied je pouzita sazba, bez montaz_pct plati globalni z ctx
        ctx = {"parts": {"product_1": {"id": "product_1", "name": "Dil", "layer": "produkt", "sku": "X1", "length_mm": None, "cross_section_mm": [None, None], "weight_kg": 1.0,
                                       "price_czk": 1000.0, "price_per_cut_czk": None, "is_board_material": False}},
               "pricing": {"joint_price_czk": 0, "profile_flat_fee_czk": 0, "packaging_pct": 3.0, "montaz_pct": 20.0, "accessories": [], "scene_price_coefficient": 1.0},
               "joint_rule_version": 3}
        vlastni = cp.price_entries([{"product_id": 1}] * 3, ctx, montaz_pct=sazba(1001))["price_summary"]
        globalni = cp.price_entries([{"product_id": 1}] * 3, ctx)["price_summary"]
        over("8 price_entries(montaz_pct=15): total 3 x 1000 + balne 3 % = 3090, montaz 15 % = 464 (zaokrouhleno jako ve scene), pouzita sazba 15",
             vlastni["total_czk"] == 3090 and vlastni["montaz_czk"] == 464 and vlastni["montaz_pct_applied"] == 15.0, vlastni)
        over("9 bez montaz_pct plati globalni sazba z ctx (20 % = 618) - sestavy do auta zustavaji beze zmeny", globalni["montaz_czk"] == 618 and globalni["montaz_pct_applied"] == 20.0 and globalni["total_czk"] == vlastni["total_czk"], globalni)
        over("10 montaz je sluzba mimo total_czk (stejny total s sazbou i bez ni)", vlastni["total_czk"] == globalni["total_czk"] == 3090, (vlastni["total_czk"], globalni["total_czk"]))
    c.commit()
    zdroj = open(CFG, encoding="utf-8").read()
    fn = zdroj[zdroj.index("def montaz_pct_for_assembly"):zdroj.index("def load_ctx")]
    over("11 montaz_pct_for_assembly cte jen pres predany kurzor: jen SELECT, zadny commit/rollback/get_conn", not re.search(r"\.commit\(|\.rollback\(|get_conn|INSERT|UPDATE|DELETE", fn) and len(re.findall(r"SELECT", fn)) == 2, None)
finally:
    with c.cursor() as cur:
        for t in ("product_assemblies", "sestava_typ_sluzba", "_tpl_product_assemblies", "_tpl_sestava_typ_sluzba"):
            cur.execute(f"DROP TEMPORARY TABLE IF EXISTS `{t}`")
    c.commit()
    c.close()
over("ostre tabulky sestava_typ_sluzba a product_assemblies jsou po testu beze zmeny", stav(ostre) == pred, (pred, stav(ostre)))
ostre.close()
ok = sum(vysl)
print(f"\nVYSLEDEK sazba montaze konfigurace podle typu sestavy: {ok}/{len(vysl)} OK")
sys.exit(0 if ok == len(vysl) else 1)
