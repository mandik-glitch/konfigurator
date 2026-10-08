#!/opt/konfigurator/api/venv/bin/python
"""Klon Vandr karty pro jine vozidlo (bot5, 2026-10-07): scripts/2026-10-07_vandr_klon_karty_jine_vozidlo.py::klonuj nad DOCASNYMI tabulkami (kopie skutecne karty #4967 + kategorii 267 a
jejich deti; ostre tabulky se nemeni) a docasnym adresarem katalogu (GLB je jen maly soubor). Spusteni:
  systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator /opt/konfigurator/api/venv/bin/python3 scripts/2026-10-07_vandr_klon_karty_testy/test_klon.py"""
import importlib.util
import json
import os
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(REPO, "scripts"))
sys.path.insert(0, os.path.join(REPO, "api"))
sys.dont_write_bytecode = True
import pymysql  # noqa: E402
from _env import get_conn  # noqa: E402

spec = importlib.util.spec_from_file_location("klon", os.path.join(REPO, "scripts", "2026-10-07_vandr_klon_karty_jine_vozidlo.py"))
klon = importlib.util.module_from_spec(spec)
spec.loader.exec_module(klon)
vysl = []


def over(nazev, podminka, detail=None):
    vysl.append(bool(podminka))
    print(("OK   " if podminka else "FAIL ") + nazev + ("" if podminka else "  -> " + repr(detail)))


TABULKY = ("shop_products", "content_categories", "shop_product_categories", "shop_product_images", "product_usage_images", "shop_product_documents", "content_gallery_items", "audit_log", "bot_ukoly", "product_turntable_frames")
real = get_conn()
rc = real.cursor()


def stav():
    """stav OSTRYCH tabulek pres SAMOSTATNE spojeni (docasne tabulky testovaciho spojeni je zastinuji)"""
    c = get_conn()
    try:
        cu = c.cursor()
        out = {}
        for t in ("shop_products", "content_categories", "audit_log", "bot_ukoly", "product_turntable_frames", "content_gallery_items"):
            cu.execute("SELECT COUNT(*) AS n, COALESCE(MAX(id),0) AS m FROM `%s`" % t)
            r = cu.fetchone()
            out[t] = (r["n"], r["m"])
        return out
    finally:
        c.close()


pred = stav()
ZDROJ = 4967
rc.execute("SELECT id FROM shop_products WHERE id=%s", (ZDROJ,))
if not rc.fetchone():
    raise SystemExit("ABORT: zdrojova karta 4967 neexistuje")
rc.execute("CREATE TEMPORARY TABLE _src_sp AS SELECT * FROM shop_products WHERE id=%s", (ZDROJ,))
rc.execute("CREATE TEMPORARY TABLE _src_cat AS SELECT * FROM content_categories WHERE id=267 OR parent_id=267")
rc.execute("CREATE TEMPORARY TABLE _src_gal AS SELECT * FROM content_gallery_items WHERE owner_type='product' AND owner_id=%s", (ZDROJ,))
rc.execute("CREATE TEMPORARY TABLE _src_frm AS SELECT * FROM product_turntable_frames WHERE shop_product_id=%s AND is_active=1", (ZDROJ,))
for t in TABULKY:
    rc.execute("CREATE TEMPORARY TABLE `_tpl_%s` LIKE `%s`" % (t, t))
    rc.execute("CREATE TEMPORARY TABLE `%s` LIKE `_tpl_%s`" % (t, t))
rc.execute("INSERT INTO shop_products SELECT * FROM _src_sp")
rc.execute("INSERT INTO content_categories SELECT * FROM _src_cat")
rc.execute("DELETE FROM content_categories WHERE name='Vestavby pro MAN' AND parent_id=267")      # skutecna kategorie MAN uz v ostre DB je (zalozeno 2026-10-07); test ma zacit bez ni
rc.execute("INSERT INTO content_gallery_items SELECT * FROM _src_gal")
rc.execute("SELECT id, filename, caption, source_url FROM content_gallery_items ORDER BY id")
GAL = rc.fetchall()
upload = tempfile.mkdtemp(prefix="klon_upload_")
gal_dir = os.path.join(upload, "gallery-items")
os.makedirs(gal_dir)
rc.execute("INSERT INTO product_turntable_frames SELECT * FROM _src_frm")
rc.execute("SELECT id, filename FROM product_turntable_frames ORDER BY id")
FRM = rc.fetchall()
for f in FRM:                                    # skutecne cesty snimku (jen male atrapy souboru) v docasnem content-files
    cesta = os.path.join(upload, f["filename"].rstrip("/"))
    os.makedirs(os.path.dirname(cesta), exist_ok=True)
    if not f["filename"].endswith("/"):
        open(cesta, "wb").write(b"jpg-" + f["filename"].encode())
for g in GAL:
    open(os.path.join(gal_dir, g["filename"]), "wb").write(b"img-" + g["filename"].encode())
rc.execute("SELECT COUNT(*) AS n FROM shop_products"); assert rc.fetchone()["n"] == 1
real.commit()
rc.execute("SELECT * FROM shop_products WHERE id=%s", (ZDROJ,))
Z = rc.fetchone()

kat = tempfile.mkdtemp(prefix="klon_katalog_")
os.makedirs(os.path.join(kat, "vandr"))
open(os.path.join(kat, Z["glb_file"]), "wb").write(b"glTF-test-" + os.urandom(64))
os.makedirs(os.path.join(kat, "thumbnails"))
open(os.path.join(kat, "thumbnails", "product-4967.jpg"), "wb").write(b"thumb-" + os.urandom(32))
rc.execute("UPDATE shop_products SET vandr_razitka_json='[1]', vandr_razitka_glb_otisk=%s, vandr_render_razitka_otisk=%s, vandr_stored_model_uuid=%s, thumbnail_file='thumbnails/product-4967.jpg', vandr_razitka_hotovo_at='2026-10-06 19:15:01' WHERE id=%s", ("a" * 64, "b" * 64, "11111111-2222-3333-4444-555555555555", ZDROJ))
rc.execute("INSERT INTO shop_product_images (product_id, filename, sort_order) VALUES (%s,'kota.png',1)", (ZDROJ,)) if False else None
real.commit()
rc.execute("SELECT * FROM shop_products WHERE id=%s", (ZDROJ,))
Z = rc.fetchone()


def soubory():
    return sorted(os.listdir(os.path.join(kat, "vandr")))


print("== K klon")
v = klon.klonuj(rc, ZDROJ, "MAN TGE L3H3 FWD", "VW Crafter L3H3 FWD", "Vestavby pro MAN", katalog_dir=kat, galerie_dir=gal_dir, upload_dir=upload)
real.commit()
rc.execute("SELECT * FROM shop_products WHERE id=%s", (v["id"],))
N = rc.fetchone()
rc.execute("SELECT * FROM content_categories WHERE id=%s", (v["kategorie_id"],))
KAT = rc.fetchone()
over("K1 novy radek: SKU VD-<uuid>, nazev s novym vozidlem, adresa z nazvu", re.match(r"^VD-[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$", N["sku"]) and N["sku"] != Z["sku"] and N["name"] == "Regálová vestavba – MAN TGE L3H3 FWD"
     and N["slug"].startswith("regalova-vestavba-man-tge-l3h3-fwd"), (N["sku"], N["name"], N["slug"]))
over("K2 popisy s novym vozidlem (zadny 'Crafter' v customer textu)", "MAN TGE L3H3 FWD" in (N["description"] or "") and "Crafter" not in (N["description"] or "") + (N["short_description"] or ""), (N["description"], N["short_description"]))
over("K3 neaktivni (pravidlo 54), bez aktivace, sklad 0, neni archivovana", N["active"] == 0 and N["activated_at"] is None and N["stock_qty"] == 0 and not N["is_archived"], (N["active"], N["activated_at"]))
over("K4 cena a dalsi komerční udaje beze zmeny", N["price_czk_placeholder"] == Z["price_czk_placeholder"] and N["weight_g"] == Z["weight_g"] and N["umisteni_id"] == Z["umisteni_id"] and N["availability_text"] == Z["availability_text"], (N["price_czk_placeholder"], Z["price_czk_placeholder"]))
over("K5 razitka a otisky se PREBIRAJI (stejny GLB), Vandr identita (unikatni uuid) NE, azimut a prurez zachovane", N["vandr_razitka_json"] == Z["vandr_razitka_json"] and N["vandr_razitka_glb_otisk"] == "a" * 64 and N["vandr_render_razitka_otisk"] == "b" * 64
     and N["vandr_razitka_hotovo_at"] == Z["vandr_razitka_hotovo_at"] and N["vandr_stored_model_uuid"] is None and N["vandr_predni_azimut_deg"] == Z["vandr_predni_azimut_deg"] and N["vandr_hlavni_prurez_mm"] == Z["vandr_hlavni_prurez_mm"], {c: N[c] for c in ("vandr_razitka_json", "vandr_stored_model_uuid")})
over("K6 GLB: nova kopie souboru (jine jmeno, stejny obsah), zdroj zustal; nahled (thumbnail) neni zdedeny", N["glb_file"] != Z["glb_file"] and N["glb_file"].startswith("vandr/vd_export_regalova_vestavba_man_tge_l3h3_fwd_") and N["glb_file"].endswith(".glb")
     and open(os.path.join(kat, N["glb_file"]), "rb").read() == open(os.path.join(kat, Z["glb_file"]), "rb").read() and os.path.isfile(os.path.join(kat, Z["glb_file"])), (N["glb_file"],))
over("K6b nahled karty: soubor zkopirovan pod nazvem klonu (stejny obsah), sloupec thumbnail_file nastaven, zdrojovy nahled zustal", N["thumbnail_file"] == "thumbnails/product-%d.jpg" % v["id"] and open(os.path.join(kat, N["thumbnail_file"]), "rb").read() == open(os.path.join(kat, "thumbnails", "product-4967.jpg"), "rb").read()
     and os.path.isfile(os.path.join(kat, "thumbnails", "product-4967.jpg")) and N["thumbnail_file"] != Z["thumbnail_file"], (N["thumbnail_file"], Z["thumbnail_file"]))
over("K7 kategorie MAN zalozena pod 267 (Vestavby podle vozidla), viditelna, adresa vestavby-pro-man, poradi za sourozenci, karta v ni", v["kategorie_nova"] and KAT["parent_id"] == 267 and KAT["name"] == "Vestavby pro MAN" and KAT["slug"] == "vestavby-pro-man" and KAT["is_visible"] == 1 and N["category_id"] == KAT["id"], KAT)
rc.execute("SELECT MAX(sort_order) AS m FROM content_categories WHERE parent_id=267 AND id<>%s", (KAT["id"],))
over("K8 poradi kategorie je za ostatnimi", KAT["sort_order"] == rc.fetchone()["m"] + 1, KAT["sort_order"])
rc.execute("SELECT COUNT(*) AS n FROM audit_log WHERE entity_type='shop_product' AND entity_id=%s AND detail LIKE %s", (v["id"], "%klon Vandr karty%"))
over("K9 audit_log zaznam o klonu", rc.fetchone()["n"] == 1, None)
rc.execute("SELECT text FROM bot_ukoly WHERE bot_id='bot7'")
u = rc.fetchall()
over("K10 ukol na zed pro bot7 (nova kategorie bez textu)", len(u) == 1 and "Vestavby pro MAN" in u[0]["text"] and str(KAT["id"]) in u[0]["text"], u)
rc.execute("SELECT sku, glb_file, name FROM shop_products WHERE id=%s", (ZDROJ,))
zz = rc.fetchone()
over("K11 zdrojova karta beze zmeny (SKU, GLB, nazev)", zz["sku"] == Z["sku"] and zz["glb_file"] == Z["glb_file"] and zz["name"] == Z["name"], zz)

rc.execute("SELECT id, filename, caption, source_url FROM content_gallery_items WHERE owner_type='product' AND owner_id=%s", (v["id"],))
GN = rc.fetchall()
dim_zdroj = [g for g in GAL if g["caption"] != "Náhled sestavy"]
over("K12 galerie klonu: Vandr 2D nakres i 'Nahled sestavy' zkopirovane (vlastni soubory s novym jmenem, zdrojove zustaly)", len(GN) == len(GAL) and sorted(g["caption"] for g in GN) == sorted(g["caption"] for g in GAL)
     and all(os.path.isfile(os.path.join(gal_dir, g["filename"])) for g in GN) and all(g["filename"] not in [z["filename"] for z in GAL] for g in GN) and all(os.path.isfile(os.path.join(gal_dir, g["filename"])) for g in GAL), (GN, [g["filename"] for g in GAL]))
over("K13 vysledek nese seznam souboru galerie (pro chown na www-data)", sorted(v["galerie_soubory"]) == sorted(g["filename"] for g in GN), v["galerie_soubory"])

print("== R prevzate rendery")
R = v["rendery"]
rc.execute("SELECT * FROM product_turntable_frames WHERE shop_product_id=%s ORDER BY id", (v["id"],))
FN = rc.fetchall()
rc.execute("SELECT * FROM product_turntable_frames WHERE shop_product_id=%s ORDER BY id", (ZDROJ,))
FS = rc.fetchall()
over("R1 snimky otocky: radky klonu s cestami turntable-frames/<id klonu>/, vsechny soubory existuji, zdrojove zustaly, pocet sedi", len(FN) == len(FS) and len(FS) > 0 and all(f["is_active"] == 1 and f["filename"].startswith("turntable-frames/%d/" % v["id"]) for f in FN)
     and all(os.path.exists(os.path.join(upload, f["filename"].rstrip("/"))) for f in FN) and all(os.path.exists(os.path.join(upload, f["filename"].rstrip("/"))) for f in FS) and R["snimku"] == len(FS), (len(FN), len(FS), R and R["snimku"]))
over("R2 radky klonu maji stejna data jako zdroj (elevace, azimut, tier, batch, bytes)", sorted((f["elevation_deg"], f["azimuth_deg"], f["tier_px"], f["batch"], f["bytes"]) for f in FN) == sorted((f["elevation_deg"], f["azimuth_deg"], f["tier_px"], f["batch"], f["bytes"]) for f in FS), None)
rc.execute("SELECT COUNT(*) AS n FROM audit_log WHERE entity_type='shop_product' AND entity_id=%s AND detail LIKE %s", (v["id"], "%prevzate hotove rendery%"))
over("R3 audit_log zaznam o prevzeti renderu", rc.fetchone()["n"] == 1, None)
over("R4 'Nahled sestavy' je v galerii klonu", any(g["caption"] == "Náhled sestavy" for g in GN), [g["caption"] for g in GN])

print("== E chyby a opakovani")
f0 = soubory()
try:
    klon.klonuj(rc, ZDROJ, "MAN TGE L3H3 FWD", "VW Crafter L3H3 FWD", "Vestavby pro MAN", katalog_dir=kat, galerie_dir=gal_dir, upload_dir=upload)
    over("E1 podruhe stejna karta = Chyba", False)
except klon.Chyba as e:
    over("E1 podruhe stejna karta = Chyba (nezaklada se podruhe), zadny novy soubor", "uz existuje" in str(e) and soubory() == f0, str(e))
try:
    klon.klonuj(rc, ZDROJ, "Opel Movano", "Neexistujici vozidlo", "Vestavby pro MAN", katalog_dir=kat, galerie_dir=gal_dir, upload_dir=upload)
    over("E2 spatne --stare-vozidlo = Chyba", False)
except klon.Chyba as e:
    over("E2 spatne --stare-vozidlo = Chyba, nic nezapsano", "neobsahuje" in str(e) and soubory() == f0, str(e))
v2 = klon.klonuj(rc, ZDROJ, "MAN TGX L3H3 FWD", "VW Crafter L3H3 FWD", "Vestavby pro MAN", katalog_dir=kat, galerie_dir=gal_dir, upload_dir=upload)
rc.execute("SELECT COUNT(*) AS n FROM content_categories WHERE name='Vestavby pro MAN'")
rc.execute("SELECT COUNT(*) AS n FROM bot_ukoly WHERE bot_id='bot7'")
over("E3 druha karta do UZ existujici kategorie MAN: kategorie se nezaklada podruhe, dalsi ukol na zed nevznika", not v2["kategorie_nova"] and v2["kategorie_id"] == v["kategorie_id"] and rc.fetchone()["n"] == 1, (v2["kategorie_nova"], v2["kategorie_id"]))
rc.execute("INSERT INTO content_gallery_items (owner_type, owner_id, filename, sort_order) VALUES ('product',%s,'x.jpg',1)", (ZDROJ,)) if False else None
rc.execute("UPDATE shop_products SET sku='NE-VANDR' WHERE id=%s", (v2["id"],))
try:
    klon.klonuj(rc, v2["id"], "Neco", "MAN TGX L3H3 FWD", "Vestavby pro MAN", katalog_dir=kat, galerie_dir=gal_dir, upload_dir=upload)
    over("E4 zdroj bez VD- SKU = Chyba", False)
except klon.Chyba as e:
    over("E4 zdroj bez VD- SKU = Chyba, nic nezapsano", "neni Vandr karta" in str(e) and soubory() == sorted(f0 + [os.path.basename(v2["glb_file"])]), str(e))
try:
    klon.prevezmi_rendery(rc, ZDROJ, v["id"], upload_dir=upload)
    over("E6 druhe prevzeti renderu = Chyba", False)
except klon.Chyba as e:
    over("E6 druhe prevzeti renderu k klonu, ktery uz snimky ma = Chyba, nic neprepsano", "uz ma snimky" in str(e), str(e))
# dalsi strana/provedeni stejneho vozidla = stejny nazev (Vandr konvence): bez volby chyba, s volbou projde a adresa se rozlisi
try:
    klon.klonuj(rc, ZDROJ, "MAN TGE L3H3 FWD", "VW Crafter L3H3 FWD", "Vestavby pro MAN", katalog_dir=kat, galerie_dir=gal_dir, upload_dir=upload)
    over("E10 stejny nazev bez volby = Chyba", False)
except klon.Chyba as e:
    over("E10 stejny nazev bez --povol-stejny-nazev = Chyba s napovedou", "povol-stejny-nazev" in str(e), str(e))
vs = klon.klonuj(rc, ZDROJ, "MAN TGE L3H3 FWD", "VW Crafter L3H3 FWD", "Vestavby pro MAN", katalog_dir=kat, galerie_dir=gal_dir, upload_dir=upload, povol_stejny_nazev=True)
rc.execute("SELECT name, slug FROM shop_products WHERE id IN (%s,%s)", (v["id"], vs["id"]))
nn = rc.fetchall()
over("E11 s volbou vznikne dalsi karta se STEJNYM nazvem a RUZNOU adresou; kategorie se nezaklada podruhe", len(nn) == 2 and nn[0]["name"] == nn[1]["name"] and nn[0]["slug"] != nn[1]["slug"] and not vs["kategorie_nova"], nn)
# --dopln: klon BEZ snimku a bez nahledu (jako #4971 zalozeny drive) -> doplni se
rc.execute("DELETE FROM product_turntable_frames WHERE shop_product_id=%s", (v2["id"],))
rc.execute("DELETE FROM content_gallery_items WHERE owner_type='product' AND owner_id=%s AND caption='Náhled sestavy'", (v2["id"],))
real.commit()
import shutil as _sh0
_sh0.rmtree(os.path.join(upload, "turntable-frames", str(v2["id"])))          # klon bez souboru snimku (jako #4971 pred doplnenim)
d = klon.prevezmi_rendery(rc, ZDROJ, v2["id"], upload_dir=upload)
over("E7 --dopln: klonu bez renderu se snimky, razitka i 'Nahled sestavy' doplni; seznam novych souboru je k dispozici", d["snimku"] == len(FS) and d["galerie_nahled"] == 1 and len(d["nove_soubory"]) == 1 and os.path.isdir(d["frames_dst"]), d)
import shutil as _sh
rc.execute("DELETE FROM product_turntable_frames WHERE shop_product_id=%s", (v2["id"],))
_sh.rmtree(d["frames_dst"])
os.rename(os.path.join(upload, "turntable-frames", str(ZDROJ)), os.path.join(upload, "turntable-frames", "_schovano"))
try:
    klon.prevezmi_rendery(rc, ZDROJ, v2["id"], upload_dir=upload)
    over("E8 chybejici adresar snimku zdroje = Chyba", False)
except klon.Chyba as e:
    over("E8 chybejici adresar snimku zdroje = Chyba, zadny cilovy adresar nezustal", "chybi" in str(e) and not os.path.exists(os.path.join(upload, "turntable-frames", str(v2["id"]))), str(e))
os.rename(os.path.join(upload, "turntable-frames", "_schovano"), os.path.join(upload, "turntable-frames", str(ZDROJ)))
# --dopln-nahled: klon bez nahledu -> doplni se; klon s nahledem -> nic
rc.execute("UPDATE shop_products SET thumbnail_file=NULL WHERE id=%s", (v2["id"],))
os.remove(os.path.join(kat, "thumbnails", "product-%d.jpg" % v2["id"]))
n1 = klon.prevezmi_nahled(rc, ZDROJ, v2["id"], katalog_dir=kat)
n2 = klon.prevezmi_nahled(rc, ZDROJ, v2["id"], katalog_dir=kat)
over("E9 prevezmi_nahled: klonu bez nahledu ho zkopiruje, podruhe (uz ma) nedela nic", n1 == os.path.join(kat, "thumbnails", "product-%d.jpg" % v2["id"]) and os.path.isfile(n1) and n2 is None, (n1, n2))
# selhani uprostred (duplikace vyhodi chybu): kopie GLB se smaze
puv = klon.product_duplicate.duplicate_product
klon.product_duplicate.duplicate_product = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("atrapa selhani"))
f1 = soubory()
try:
    klon.klonuj(rc, ZDROJ, "MAN TGS L3H3 FWD", "VW Crafter L3H3 FWD", "Vestavby pro MAN", katalog_dir=kat, galerie_dir=gal_dir, upload_dir=upload)
    over("E5 selhani uprostred = vyjimka", False)
except RuntimeError:
    over("E5 selhani uprostred: kopie GLB souboru smazana (zadne osirele soubory)", soubory() == f1, soubory())
finally:
    klon.product_duplicate.duplicate_product = puv

print("== M mapovani Vandr dat (klon -> zdroj)")
mf = os.path.join(tempfile.mkdtemp(prefix="klon_priv_"), "private-files", "vandr-klony.json")
SKU_Z, SKU_K, SKU_K2 = "VD-2c24d107-6726-4b5b-af74-c6fb9affc661", "VD-2f3c0f86-a45b-45ad-bee2-460e75d9d368", "VD-AAAAAAAA-0000-0000-0000-000000000001"
m1 = klon.zapis_mapovani(SKU_K, SKU_Z, soubor=mf)
over("M1 prvni zapis vytvori soubor (i adresar) s {uuid klonu: uuid zdroje} malymi pismeny", m1 == {"2f3c0f86-a45b-45ad-bee2-460e75d9d368": "2c24d107-6726-4b5b-af74-c6fb9affc661"} and json.load(open(mf)) == m1, m1)
over("M2 soubor je cteny pro vsechny (0644) a nezustal tmp", oct(os.stat(mf).st_mode & 0o777) == "0o644" and not os.path.exists(mf + ".tmp"), oct(os.stat(mf).st_mode & 0o777))
m2 = klon.zapis_mapovani(SKU_K2, SKU_K, soubor=mf)
over("M3 klon klonu se rozbali na PUVODNI zdroj; stare zaznamy zustavaji", m2.get("aaaaaaaa-0000-0000-0000-000000000001") == "2c24d107-6726-4b5b-af74-c6fb9affc661" and "2f3c0f86-a45b-45ad-bee2-460e75d9d368" in m2 and len(m2) == 2, m2)
m3 = klon.zapis_mapovani(SKU_K, SKU_Z, soubor=mf)
over("M4 opakovany zapis je idempotentni", m3 == m2, m3)
try:
    klon.zapis_mapovani("NE-VANDR", SKU_Z, soubor=mf)
    over("M5 neplatne SKU = Chyba", False)
except klon.Chyba:
    over("M5 neplatne SKU = Chyba, soubor beze zmeny", json.load(open(mf)) == m2, None)
open(mf, "w").write("[1,2]")
try:
    klon.zapis_mapovani(SKU_K, SKU_Z, soubor=mf)
    over("M6 soubor, ktery neni objekt = Chyba", False)
except klon.Chyba:
    over("M6 soubor, ktery neni objekt = Chyba (nic neprepise)", open(mf).read() == "[1,2]", None)

real.rollback()
po = stav()
over("Z ostre tabulky shop_products / content_categories / audit_log / bot_ukoly beze zmeny", po == pred, (pred, po))
print("\n%d/%d kontrol OK" % (sum(vysl), len(vysl)))
sys.exit(0 if all(vysl) else 1)
