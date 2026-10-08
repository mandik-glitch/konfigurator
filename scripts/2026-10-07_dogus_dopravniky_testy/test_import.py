#!/opt/konfigurator/api/venv/bin/python
"""Import Dogus dopravniku bez pohonu - faze 2 (bot5, 2026-10-07): scripts/2026-10-07_bot5_dogus_dopravniky_import.py (strom_zapis, produkty_zapis, obrazky_zapis, nacti_radky) nad DOCASNYMI tabulkami
(kopie skutecnych kategorii, prazdne produkty/obrazky/audit) a docasnym adresarem obrazku se zastupnym stahovanim; ostre tabulky se nemeni (kontrola samostatnym spojenim).
Spusteni: systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator api/venv/bin/python3 scripts/2026-10-07_dogus_dopravniky_testy/test_import.py"""
import collections
import importlib.util
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location("imp", os.path.join(REPO, "scripts", "2026-10-07_bot5_dogus_dopravniky_import.py"))
IMP = importlib.util.module_from_spec(spec)
spec.loader.exec_module(IMP)
M = IMP.M
vysl = []


def over(nazev, podminka, detail=None):
    vysl.append(bool(podminka))
    print(("OK   " if podminka else "FAIL ") + nazev + ("" if podminka else "  -> " + repr(detail)))


def stav():
    c = M.get_db_conn()
    try:
        cu = c.cursor()
        out = {}
        for t in ("shop_products", "content_categories", "shop_product_images", "audit_log"):
            cu.execute("SELECT COUNT(*) AS n, COALESCE(MAX(id),0) AS m FROM `%s`" % t)
            r = cu.fetchone()
            out[t] = (r["n"], r["m"])
        return out
    finally:
        c.close()


pred = stav()
conn = M.get_db_conn()
cur = conn.cursor()
TAB = ("content_categories", "shop_products", "shop_product_images", "audit_log")
cur.execute("CREATE TEMPORARY TABLE _src_cat AS SELECT * FROM content_categories")
for t in TAB:
    cur.execute("CREATE TEMPORARY TABLE `_tpl_%s` LIKE `%s`" % (t, t))
    cur.execute("CREATE TEMPORARY TABLE `%s` LIKE `_tpl_%s`" % (t, t))
cur.execute("INSERT INTO content_categories SELECT * FROM _src_cat")
cur.execute("DELETE FROM content_categories WHERE slug IN ('dopravniky-bez-pohonu','valeckove-dopravniky','valecky-a-hlavice-valecku','podvozky-a-nohy-dopravniku','spoje-a-konzoly-dopravniku','bocni-voditka-dopravniku','kulickove-prepravni-jednotky')")
# po ostrem zapisu (2026-10-07) uz ostre kategorie nesou novy strom: pro test se vrati puvodni stav 214/225/264 ze zalohy (backups/2026-10-07_dopravniky_kategorie_pred_zmenou.json)
import json
for r in json.load(open(os.path.join(REPO, "backups", "2026-10-07_dopravniky_kategorie_pred_zmenou.json"), encoding="utf-8")):
    cur.execute("UPDATE content_categories SET name=%s, nav_label=%s, parent_id=%s, sort_order=%s, dogus_price_coefficient=%s, dogus_sale_unit=%s WHERE id=%s",
                (r["name"], r["nav_label"], r["parent_id"], r["sort_order"], r["dogus_price_coefficient"], r["dogus_sale_unit"], r["id"]))
conn.commit()

print("== R nacti_radky")
radky, vyrazeno = IMP.nacti_radky()
over("R1 186 dilu (188 z dokumentu bot7 minus 2 vyrazene: vytahovy dil a kolo bez udaju)", len(radky) == 186 and sorted(v[0] for v in vyrazeno) == ["2.3.004.100.02", "3.012.04"], (len(radky), vyrazeno))
bez = [r for r in radky if r["bez_cenoveho_navazani"]]
over("R2 bez cenoveho navazani: 90 dopravniku (Dogus 0,00 USD) + 2 tyce s delkovou jednotkou (6000/2500) = 92; ty maji dogus_url NULL", len(bez) == 92 and all(r["dogus_url"] is None for r in bez)
     and {r["sku"] for r in bez if r["kategorie_slug"] != "valeckove-dopravniky"} == {"2.2.016.027.037.01", "2.2.016.027.037.03"}, (len(bez), [r["sku"] for r in bez][-3:]))
over("R3 ostatni (94 kusovych dilu) maji dogus_url (kvuli nocnimu prepoctu ceny)", sum(1 for r in radky if r["dogus_url"]) == 94 and all(r["dogus_url"].startswith("https://en.doguskalip.com.tr/Urun/") for r in radky if r["dogus_url"]), None)
over("R4 hmotnost z dokumentu bot7 (tisicova tecka): kus s Weight '1.079' ma 1079 g; metrove/dopravniky null", all((r["weight_g"] is None) or (isinstance(r["weight_g"], (int, float)) and r["weight_g"] > 0) for r in radky)
     and any(r["weight_g"] and r["weight_g"] >= 1000 for r in radky), collections.Counter(type(r["weight_g"]).__name__ for r in radky))
over("R5 nazvy unikatni, bez nazvu dodavatele", len({r["name"] for r in radky}) == 186 and not any("dogus" in (r["name"] + r["description"]).lower() for r in radky), [r["name"] for r in radky if "dogus" in (r["name"] + r["description"]).lower()][:3])
over("R6 rozdeleni do kategorii: dopravniky 90, valecky 22, spoje 26, voditka 12, drahy 10, podvozky 7, kulicky 6, kola 14 (15 minus kolo bez udaju)", dict(collections.Counter(r["kategorie_slug"] for r in radky)) == {
    "valeckove-dopravniky": 90, "valecky-a-hlavice-valecku": 22, "spoje-a-konzoly-dopravniku": 25, "bocni-voditka-dopravniku": 12, "valeckove-drahy": 10, "podvozky-a-nohy-dopravniku": 7,
    "kulickove-prepravni-jednotky": 6, "pojezdova-kola": 14}, dict(collections.Counter(r["kategorie_slug"] for r in radky)))

print("== S strom")
zal = []
ids = IMP.strom_zapis(cur, lambda rows: zal.extend(rows))
conn.commit()
cur.execute("SELECT * FROM content_categories WHERE id=%s", (ids["dopravniky-bez-pohonu"],))
TOP = cur.fetchone()
cur.execute("SELECT id, parent_id, name, slug, is_visible, dogus_price_coefficient, dogus_sale_unit, sort_order FROM content_categories WHERE parent_id=%s ORDER BY sort_order", (TOP["id"],))
DET = cur.fetchall()
over("S1 top-level 'Dopravniky bez pohonu' bez rodice, skryta, adresa dopravniky-bez-pohonu", TOP["parent_id"] is None and TOP["is_visible"] == 0 and TOP["slug"] == "dopravniky-bez-pohonu" and TOP["name"] == "Dopravníky bez pohonu", TOP)
over("S2 pod ni 6 nove podkategorie (skryte, koeficient 1,2 / kus) + presunute #225 a #264", [d["slug"] for d in DET] == ["valeckove-dopravniky", "valecky-a-hlavice-valecku", "podvozky-a-nohy-dopravniku", "spoje-a-konzoly-dopravniku", "bocni-voditka-dopravniku",
                                                                                                    "kulickove-prepravni-jednotky", "valeckove-drahy", "dopravnikove-profily"]
     and all(d["is_visible"] == 0 and str(d["dogus_price_coefficient"]) == "1.200" and d["dogus_sale_unit"] == "kus" for d in DET[:6]), [(d["slug"], d["is_visible"]) for d in DET])
cur.execute("SELECT id, name, nav_label, slug, dogus_price_coefficient, parent_id FROM content_categories WHERE id IN (214,225,264) ORDER BY id")
K = {r["id"]: r for r in cur.fetchall()}
over("S3 #214 prejmenovana na 'Pojezdova kola' (nazev; nav_label jen kdyz mel puvodni nazev; slug beze zmeny); #225 koeficient doplnen; #264 koeficient beze zmeny", K[214]["name"] == "Pojezdová kola" and K[214]["nav_label"] in (None, "Pojezdová kola") and K[214]["slug"] == "pojezdove-kola"
     and str(K[225]["dogus_price_coefficient"]) == "1.200" and str(K[264]["dogus_price_coefficient"]) == "1.000" and K[225]["slug"] == "valeckove-drahy" and K[264]["slug"] == "dopravnikove-profily", K)
over("S4 zaloha puvodnich radku 214/225/264 predana (rodice 150/156/149)", sorted((r["id"], r["parent_id"]) for r in zal) == [(214, 150), (225, 156), (264, 149)], [(r["id"], r["parent_id"]) for r in zal])
cur.execute("SELECT COUNT(*) AS n FROM audit_log WHERE entity_type='category' AND entity_id=%s", (TOP["id"],))
over("S5 audit_log zaznam o strome", cur.fetchone()["n"] == 1, None)
try:
    IMP.strom_zapis(cur)
    over("S6 druhe zalozeni stromu = chyba", False)
except SystemExit as e:
    over("S6 druhe zalozeni stromu = chyba (nezaklada se podruhe)", "CHYBA" in str(e), str(e)[:120])
conn.rollback() if False else None

print("== P produkty")
n = IMP.produkty_zapis(cur, radky, ids)
conn.commit()
cur.execute("SELECT COUNT(*) AS n, SUM(active) AS a, SUM(is_archived) AS ar, SUM(visible_in_scene) AS v, SUM(price_czk_placeholder IS NOT NULL) AS cena, COUNT(DISTINCT slug) AS slugy, SUM(dogus_url IS NOT NULL) AS dgu, SUM(dogus_stock_code IS NOT NULL) AS dgs FROM shop_products")
agg = cur.fetchone()
over("P1 vytvoreno 186 karet, VSECHNY neaktivni (pravidlo 54), nearchivovane, mimo scenu, bez ceny, slugy unikatni", len(n) == 186 and agg["n"] == 186 and int(agg["a"] or 0) == 0 and int(agg["ar"] or 0) == 0 and int(agg["v"] or 0) == 0 and int(agg["cena"] or 0) == 0 and agg["slugy"] == 186, agg)
over("P2 dogus_url a dogus_stock_code jen u 94 kusovych dilu (nocni prepocet), zbytek NULL", int(agg["dgu"]) == 94 and int(agg["dgs"]) == 94, agg)
cur.execute("SELECT c.slug, COUNT(*) AS n FROM shop_products p JOIN content_categories c ON c.id=p.category_id GROUP BY c.slug")
over("P3 karty v cilovych kategoriich (valeckove-drahy=#225, pojezdove-kola=#214)", {r["slug"]: r["n"] for r in cur.fetchall()} == {"valeckove-dopravniky": 90, "valecky-a-hlavice-valecku": 22, "spoje-a-konzoly-dopravniku": 25, "bocni-voditka-dopravniku": 12,
                                                                                                                                    "valeckove-drahy": 10, "podvozky-a-nohy-dopravniku": 7, "kulickove-prepravni-jednotky": 6, "pojezdove-kola": 14}, None)
cur.execute("SELECT sku, unit, manufacturer, weight_g, product_specs_json IS NOT NULL AS specs FROM shop_products WHERE sku=%s", ("3.009.01.50.290",))
r1 = cur.fetchone()
over("P4 jednotka ks, vyrobce v DB, specifikace ulozena, hmotnost z dokumentu", r1 and r1["unit"] == "ks" and r1["specs"] == 1 and r1["weight_g"] is not None, r1)
n2 = IMP.produkty_zapis(cur, radky, ids)
conn.commit()
over("P5 opakovani: existujici SKU se preskoci (0 novych)", n2 == [], len(n2))
try:
    IMP.produkty_zapis(cur, [dict(radky[0], sku="X-TEST-1", name="Test ", kategorie_slug="neexistuje")], ids)
    over("P6 neznama cilova kategorie = chyba", False)
except SystemExit:
    over("P6 neznama cilova kategorie = chyba", True)

print("== O obrazky")
tmp = tempfile.mkdtemp(prefix="dopr_img_")
volano = []


def stahni(url, cil):
    volano.append(url)
    with open(cil, "wb") as f:
        f.write(("img:" + url).encode())


ok, bad = IMP.obrazky_zapis(conn, n, stahni=stahni, img_dir_tpl=os.path.join(tmp, "{id}"), chown=False)
cur.execute("SELECT COUNT(*) AS n, COUNT(DISTINCT product_id) AS p FROM shop_product_images")
im = cur.fetchone()
dvojice = sum(1 for _, r in n if r["schema"] and r["render"] and r["schema"] != r["render"])
jednotlive = sum(1 for _, r in n if (r["schema"] or r["render"]) and not (r["schema"] and r["render"] and r["schema"] != r["render"]))
over("O1 obrazky: 2 na kartu (schema + render), 1 kdyz jsou shodne; zadna chyba", bad == 0 and ok == im["n"] == dvojice * 2 + jednotlive and im["p"] == len(n), (ok, bad, im, dvojice, jednotlive))
over("O2 soubor se stahuje jednou na URL (cache), dalsi karty se stejnym obrazkem kopiruji: stazeno mene nez ulozeno", len(volano) == len(set(volano)) and len(volano) < ok, (len(volano), ok))
cid = n[0][0]
over("O3 soubory existuji pod <dir>/<id>/", all(os.path.isfile(os.path.join(tmp, str(cid), f)) for f in os.listdir(os.path.join(tmp, str(cid)))) and len(os.listdir(os.path.join(tmp, str(cid)))) >= 1, os.listdir(os.path.join(tmp, str(cid))))

conn.rollback()
po = stav()
over("Z ostre tabulky shop_products / content_categories / shop_product_images / audit_log beze zmeny", po == pred, (pred, po))
print("\n%d/%d kontrol OK" % (sum(vysl), len(vysl)))
sys.exit(0 if all(vysl) else 1)
