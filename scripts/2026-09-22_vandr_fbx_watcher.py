#!/usr/bin/env python3
"""Automat: detekuje nove .fbx soubory pro Vandr (vanDrawee) vetev na
Sdilenem disku a zaklada/paruje odpovidajici karty (bot5, 2026-09-22,
Robert pres bot3 - viz PLAN_TVORBY_SESTAV.md "Vandr sestavy na eshopu").

⚠️ SAMOSTATNA vetev, NENI rozsireni card_auto_link/watchdog_prace/
card_auto_activate - ty ctou/pisou `product_assemblies`, ktery Vandr
karty (`shop_products.sku LIKE 'VD-%'`) vubec nemaji. Vlastni tabulka
`vandr_fbx_queue` (sql/2026-09-22_vandr_fbx_queue.sql).

Spoustec - DVA nezavisle zdroje (OPRAVA 2026-09-22, bot3, Robert se
ptal "umi to stahovat FBX primo z vandrawee adminu?"):

  A) PRIMARNI: `vandrawee_work.stored_models.fbx_exported_at IS NOT
     NULL` (nastavuje se, kdyz Robert klikne na export v designeru) -
     FBX se cte primo z `/opt/vandrawee/web/storage/app/exported_
     models/<uuid>/<uuid>.fbx`. Oba projekty bezi na stejne VPS pod
     stejnym OS uzivatelem `www-data`, takze konfigurator skript muze
     tenhle soubor cist bez zvlastnich prav (overeno zive pres
     `systemd-run --uid=www-data`, ne jen predpoklad).
  B) FALLBACK: novy .fbx na Sdilenem disku pod korenovou slozkou
     "vanDrawee sestavy" (`shared_drive_folders`, libovolna hloubka
     podslozek) - puvodni mechanismus, ponechan pro soubory odjinud
     nez z vandrawee adminu. Podslozky NEJSOU organizovane podle
     vozidla ani zadny jiny zavazny udaj - Robert: "nebudu vytvářet
     žádné sestavy podle aut, auta jsou dané v adminu, budu pridávat
     nové fbx jen rozdelené abych se v tom sám vyznal" (cisté osobni
     razeni, ne data). Skript proto NIKDY nesmi cerpat vozidlo/nazev
     ze slozky - jedina veta o zdroji pravdy je UUID + lokalni
     vandrawee_work/vandrawee DB (viz bod 3 nize).

Oba zdroje davaji stejny format identity - UUID - a jdou pres
STEJNOU idempotencni tabulku `vandr_fbx_queue`, klic ted
`UNIQUE(vandrawee_uuid)` (ne uz `shared_drive_file_id` - ten je od
migrace `2026-09-22b_vandr_fbx_queue_local_export.sql` nepovinny,
vyplni se jen kdyz UUID prislo cestou B). Stejne UUID nalezene obema
cestami (napr. Robert nejdriv exportuje v adminu, pak jeste rucne
nahraje na disk) se zpracuje jen JEDNOU.

Nazev souboru na Sdilenem disku (cesta B) MUSI byt "<uuid>.fbx" (presne
konvence, kterou uz Robert sam pouziva - overeno na prvnim skutecnem
souboru 2b6d4dd7-7a9d-400f-bfa6-a2d8e3aa743e.fbx, ten samy pripad byl
pak nezavisle nalezen i cestou A pri testovani, spravne deduplikovan).

Co skript dela s kazdym NOVYM (jeste nezpracovanym, viz vandr_fbx_queue)
.fbx souborem:
  1) UUID z nazvu souboru
  2) existuje uz `shop_products.sku='VD-<uuid>'`? (325 karet z puvodniho
     CSV importu, bot7, 2026-09-18) -> ANO: nic se nemeni, jen zaznam
     "karta_existovala" (karta uz ma nazev/cenu/vozidlo z CSV, ceka jen
     na render - viz 2026-09-22_vandr_card_activate.py).
  3) NEexistuje -> zkusi se dohledat metadata (nazev/cena/vaha) primo v
     lokalni `vandrawee_work`/`vandrawee` MySQL DB (OPRAVA 2026-09-22,
     bot3 nezavisle overil primo v DB a nasel presnou shodu pro prvni
     realny pripad - `stored_models.uuid` BINARY(16), `car_model_id` ->
     `vandrawee_work.car_models.unity_id` -> `vandrawee.car_models/
     car_types/car_manufacturers`, cena/vaha = soucet existujicich
     left_part/right_part/bulkhead_part - presne vzorec podle
     `StoredModel::price()`/`weight()` v /opt/vandrawee zdrojaku).
     ZADNE externi HTTP volani na vandrawee.eu - jen lokalni DB.
     Nalezeno -> DRAFT karta (active=0, ale UZ S nazvem/cenou/vahou).
     Nenalezeno -> DRAFT karta (active=0, bez ceny) + ukol na zed pro
     Roberta (jedina zbyvajici cesta, kdyz to neni ani u nas v DB).
     Karta se zaklada uz TED v obou pripadech, aby bot4 mel
     `shop_product_id`, na ktery muze renderovat
     (product_turntable_frames.shop_product_id je NOT NULL), i kdyz
     metadata chybi.

Nikdy nesahne na existujici kartu (zadny UPDATE zname sku, jen SELECT).
Nic nemaze. Idempotentni pres UNIQUE(vandr_fbx_queue.vandrawee_uuid).

Spusteni NA SERVERU (/opt/konfigurator):
    api/venv/bin/python3 scripts/2026-09-22_vandr_fbx_watcher.py
    api/venv/bin/python3 scripts/2026-09-22_vandr_fbx_watcher.py --apply
"""
import argparse
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import unicodedata
import uuid as uuid_module
from collections import Counter

import pymysql

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _env import get_conn  # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "api"))
import product_slug  # noqa: E402  jediný mechanismus adres produktu (čistý modul bez Flasku)

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT_FOLDER_NAME = "vanDrawee sestavy"
UUID_RE = re.compile(
    r"^([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\.fbx$",
    re.IGNORECASE,
)


def _slugify(text):
    # Stejna logika jako scripts/2026-09-02_product_slug_backfill.py -
    # OPRAVA 2026-09-23: watcher pri zalozeni draft karty slug vubec
    # nenastavoval (karta 4903 skoncila active=1 se slug=NULL, zjisteno
    # az pri aktivaci - verejna URL /produkt/<slug> nefungovala). Slug
    # se ted nastavuje uz pri INSERTu, at karta neceka na dalsi rucni
    # backfill beh.
    text = unicodedata.normalize("NFKD", text or "")
    text = text.encode("ascii", "ignore").decode("ascii").lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return re.sub(r"-+", "-", text).strip("-") or "produkt"


def _unique_slug(cur, base):
    candidate, n = base, 2
    while True:
        cur.execute("SELECT id FROM shop_products WHERE slug=%s", (candidate,))
        if not cur.fetchone():
            return candidate
        candidate = f"{base}-{n}"
        n += 1

# Sesterky projekt /opt/vandrawee - vlastni MySQL, vlastni .env (NENI
# konfigurator DB). Cteno za behu, zadny secret v tomhle souboru.
VANDR_ENV_PATH = "/opt/vandrawee/web/.env"


def _vandr_env():
    vals = {}
    try:
        with open(VANDR_ENV_PATH, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                vals[k.strip()] = v.strip()
    except OSError:
        return None
    return vals


def _vandr_conn(env, database):
    return pymysql.connect(
        host=env.get("DB_HOST", "127.0.0.1"),
        port=int(env.get("DB_PORT", "3306")),
        user=env["DB_USERNAME"],
        password=env["DB_PASSWORD"],
        database=database,
        cursorclass=pymysql.cursors.DictCursor,
    )


# bot3, 2026-09-23 (Robert nahlasil pres bot3): nove karty (#4903,
# #4904) zalozene watcherem mely category_id=NULL, na rozdil od 321
# CSV-importovanych karet (bot7), ktere vsechny maji category_id na
# jednu z 10 vetvi "Vestavby podle vozidla" (content_categories.
# parent_id=267) - overeno primo (321/321 CSV karet ma kategorii z
# TETO presne mnoziny). Bez kategorie se karta nezobrazi v zadnem
# prochazeni webu. Mapovano pres `vandrawee.car_manufacturers.id`
# (STABILNI klic - "name" NEsedi 1:1: vandrawee ma "Citroen"/"VW", nase
# kategorie "Citroën"/"Volkswagen", srovnavat retezce by bylo krehke).
ZNACKA_ID_TO_CATEGORY = {
    1: 269,   # Fiat -> Vestavby pro Fiat
    2: 268,   # Citroen -> Vestavby pro Citroën
    3: 288,   # Peugeot -> Vestavby pro Peugeot
    4: 279,   # Ford -> Vestavby pro Ford
    5: 271,   # VW -> Vestavby pro Volkswagen
    6: 270,   # Mercedes -> Vestavby pro Mercedes
    7: 286,   # Opel -> Vestavby pro Opel
    8: 287,   # Iveco -> Vestavby pro Iveco
    9: 281,   # Toyota -> Vestavby pro Toyota
    10: 285,  # Renault -> Vestavby pro Renault
}


def _secti_kusovnik(data_list):
    """Secte vyskyty unity_id v Unity receptu jedne casti (left/right/
    bulkhead_part.data) - postup navrzeny bot7 2026-09-23 (overeno na
    2 realnych castech, sedi): top-level je LIST "ramu", kazdy muze mit
    vlastni `unity_id`, volitelne `left_leg`/`right_leg` (vlastni
    unity_id), a `components[]` (vlastni unity_id + volitelne
    `extensions[]` s DALSIMI unity_id - napr. popruh na suplíku).
    `replaced_parts` (nahrada AL profilu kvuli spoji) se NEPOCITA -
    nizsi uroven nez "dil", ne skutecna polozka kusovniku."""
    c = Counter()
    for item in (data_list or []):
        if item.get("unity_id"):
            c[item["unity_id"]] += 1
        for leg_key in ("left_leg", "right_leg"):
            leg = item.get(leg_key)
            if leg and leg.get("unity_id"):
                c[leg["unity_id"]] += 1
        for comp in (item.get("components") or []):
            if comp.get("unity_id"):
                c[comp["unity_id"]] += 1
            for ext in (comp.get("extensions") or []):
                if ext.get("unity_id"):
                    c[ext["unity_id"]] += 1
    return c


def _format_kusovnik_specs(counter):
    """Rozdeli secteny kusovnik na "Nohy"/"Komponenty" (bot7: zivá
    stranka ma jemnejsi podnadpisy typu "Univerzální"/"1014 mm", ale ty
    v JSON receptu nejsou - radeji poctiva hruba sekce nez vymyslena
    kategorizace, TEXT_FILTR pravidlo 16). Vraci dict presne ve tvaru
    product_specs_json (dela renderMetaTable v product.html)."""
    nohy, komponenty = [], []
    for uid in sorted(counter):
        radek = (uid, counter[uid])
        (nohy if uid.startswith(("Noha.", "Nohy.")) else komponenty).append(radek)
    out = {}
    if nohy:
        out["Nohy"] = ", ".join(f"{n}x {uid}" for uid, n in nohy)
    if komponenty:
        out["Komponenty"] = ", ".join(f"{n}x {uid}" for uid, n in komponenty)
    return out


from _vandr_umisteni import urcit_umisteni_id  # noqa: E402  bot10 2026-09-24, WORKFLOW.md pravidlo 51


def _lookup_vandr_metadata(uuid):
    """Zkusi dohledat nazev/cenu/vahu v lokalni vandrawee_work/vandrawee
    DB (BEZ zadneho HTTP volani na vandrawee.eu - bot3, 2026-09-22,
    overil ze zive na prvnim realnem pripadu). Vraci None, kdyz se
    UUID v lokalni DB vubec nenajde (pak nezbyva nez ukol na zed)."""
    env = _vandr_env()
    if not env:
        return None
    uuid_hex = uuid.replace("-", "").upper()
    try:
        conn_w = _vandr_conn(env, env.get("DB_VANDRAWEE_WORK_DATABASE", "vandrawee_work"))
        try:
            with conn_w.cursor() as cur:
                cur.execute(
                    "SELECT id, car_model_id, left_part_id, right_part_id, bulkhead_part_id "
                    "FROM stored_models WHERE HEX(uuid)=%s",
                    (uuid_hex,),
                )
                sm = cur.fetchone()
                if not sm:
                    return None
                price = 0.0
                weight = 0.0
                found_part = False
                kusovnik = Counter()
                dim_images = []
                for part_id, part_role in ((sm["left_part_id"], "levá část"), (sm["right_part_id"], "pravá část"),
                                            (sm["bulkhead_part_id"], "přepážka")):
                    if part_id is None:
                        continue
                    cur.execute(
                        "SELECT price, weight, data, image_2D_with_dim FROM stored_model_parts WHERE id=%s",
                        (part_id,),
                    )
                    p = cur.fetchone()
                    if p:
                        found_part = True
                        price += float(p["price"] or 0)
                        weight += float(p["weight"] or 0)
                        try:
                            kusovnik += _secti_kusovnik(json.loads(p["data"]) if p["data"] else [])
                        except (TypeError, ValueError) as e:
                            print(f"[vandr-fbx-watcher] kusovnik parse selhal pro dil {part_id}: {e}", file=sys.stderr)
                        # Robert, 2026-09-23 ("porad cekam na kotovaný
                        # náhled") - stored_model_parts.image_2D_with_dim
                        # je skutecny kotovany 2D vykres (mm kotace primo
                        # v obrazku), fyzicky na VANDR_IMAGES_DIR. Kopiruje
                        # se do content_gallery_items pri zalozeni karty.
                        if p.get("image_2D_with_dim"):
                            fname = os.path.basename(p["image_2D_with_dim"])
                            src_path = os.path.join(VANDR_IMAGES_DIR, fname)
                            if os.path.isfile(src_path):
                                dim_images.append((src_path, part_role))
                nazev = None
                if sm["car_model_id"] is not None:
                    cur.execute("SELECT unity_id FROM car_models WHERE base_car_model_id=%s", (sm["car_model_id"],))
                    wcm = cur.fetchone()
                    if wcm:
                        nazev = wcm["unity_id"]
                # bot10, 2026-10-01 (Robert 2026-09-30: kombinace leve+prave
                # strany se deli na 2 karty): vanDrawee pri ulozeni sestavy
                # s vic stranami zaklada i samostatne modely jednotlivych stran
                # se stejnym dilem (StoredModelApiController::store) - dohledat
                # jejich UUID, at Robert vi, co exportovat misto kombinace.
                strany_sloupce = ("left_part_id", "right_part_id", "bulkhead_part_id")
                vyplnene_strany = [n for n in strany_sloupce if sm[n] is not None]
                samostatne_strany = {}
                if len(vyplnene_strany) >= 2:
                    for n in vyplnene_strany:
                        ostatni = [o for o in strany_sloupce if o != n]
                        cur.execute(
                            f"SELECT HEX(uuid) AS h FROM stored_models WHERE {n}=%s "
                            f"AND {ostatni[0]} IS NULL AND {ostatni[1]} IS NULL ORDER BY id LIMIT 1",
                            (sm[n],),
                        )
                        r = cur.fetchone()
                        samostatne_strany[n] = _format_uuid(r["h"]) if r and r["h"] else None
        finally:
            conn_w.close()
        # Cely lidsky nazev (znacka + model + varianta) je v HLAVNI
        # `vandrawee` DB (base_car_model_id -> car_models.car_type_id ->
        # car_types.car_manufacturer_id), presny retezec relaci jako
        # `App\Models\CarModel::get_full_name()` v /opt/vandrawee zdrojaku.
        znacka_id = None
        if sm["car_model_id"] is not None:
            conn_m = _vandr_conn(env, env.get("DB_VANDRAWEE_DATABASE", "vandrawee"))
            try:
                with conn_m.cursor() as cur:
                    cur.execute("SELECT car_type_id, name FROM car_models WHERE id=%s", (sm["car_model_id"],))
                    cm = cur.fetchone()
                    if cm:
                        cur.execute("SELECT car_manufacturer_id, name FROM car_types WHERE id=%s", (cm["car_type_id"],))
                        ct = cur.fetchone()
                        if ct:
                            znacka_id = ct["car_manufacturer_id"]
                            cur.execute("SELECT name FROM car_manufacturers WHERE id=%s", (ct["car_manufacturer_id"],))
                            mk = cur.fetchone()
                            if mk:
                                nazev = f"{mk['name']} {ct['name']} {cm['name']}"
            finally:
                conn_m.close()
        if not found_part:
            return None
        # OPRAVA 2026-09-23 (Robert na kartě 4903: "žádný popis a
        # specifikaci níže nevidim"): puvodni text slibovala "tabulku
        # specifikaci nize" s kusovnikem, ale `product_specs_json` (co
        # tabulku plni, viz renderMetaTable v product.html) se
        # nikdy nenastavovalo - slib byl fakticky nepravdivy (overeno
        # primo pres /api/shop/products/4903). DOPLNENO (postup
        # navrzeny bot7): `_secti_kusovnik()` spocita kusovnik primo z
        # Unity receptu (`stored_model_parts.data`) - STEJNY zdroj dat
        # jako zdroj pravdy, jen bez zavislosti na zverejneni na zivem
        # vandrawee.eu (to pro nove FBX-schvalene sestavy casto jeste
        # neexistuje, viz predchozi zprava). Kdyz kusovnik vyjde
        # prazdny (zadna data), text uz kusovnik NESLIBUJE - jinak
        # slib zustava, protoze uz je pravdivy.
        # OPRAVA 2026-09-23 (bot5): "vanDrawee" odstranena z ceskeho
        # zakaznickeho textu (TEXT_FILTR.md pravidlo 15 - Robert: "v
        # ceskych textech ho nebudeme pouzivat"). Blok "Cena obsahuje"
        # (Robert 2026-09-23) uz NENI tady zapeceny - je editovatelny v
        # adminu (app_settings, viz api/admin_settings.py
        # VANDRAWEE_CENA_OBSAHUJE_KEY) a pripojuje se DYNAMICKY az na
        # frontendu (webapp/product.html, api/products.py), aby zmena
        # nastaveni platila na vsech kartach bez dalsiho backfillu.
        # OPRAVA 2026-09-23b (Robert): "tuto větu nepouzivat: Přesný
        # obsah sestavy (kusovník) najdete v tabulce specifikací níže."
        # - odstranena natrvalo, `specs` uz proto nemusi rozhodovat o
        # dvou ruznych zneni popisu (predchozi "if specs:"/"else:"
        # vetev dava ted stejny vysledek - zjednoduseno).
        specs = _format_kusovnik_specs(kusovnik)
        popis = f"Hliníková regálová vestavba do nákladového prostoru {nazev}." if nazev else None
        kratky_popis = (f"Hliníková regálová vestavba pro {nazev}, cena bez montáže."
                        if nazev else None)
        return {"name": nazev, "price_czk": round(price) if price else None, "weight_g": weight if weight else None,
                "category_id": ZNACKA_ID_TO_CATEGORY.get(znacka_id), "description": popis, "short_description": kratky_popis,
                "product_specs_json": specs or None, "dim_images": dim_images,
                # WORKFLOW.md pravidlo 51 (stitek umisteni) - urceno primo ze `sm`
                # (left_part_id/right_part_id/bulkhead_part_id), stejna logika jako
                # scripts/2026-09-24_vandr_umisteni_backfill.py (existujici karty).
                "umisteni_id": urcit_umisteni_id(sm),
                "pocet_stran": len(vyplnene_strany), "samostatne_strany": samostatne_strany}
    except Exception as e:  # noqa: BLE001
        print(f"[vandr-fbx-watcher] lookup vandrawee_work selhal pro {uuid}: {e}", file=sys.stderr)
        return None


VANDR_EXPORT_DIR = "/opt/vandrawee/web/storage/app/exported_models"
VANDR_IMAGES_DIR = "/opt/vandrawee/web/storage/app/public/images"
GALLERY_ITEMS_DIR = os.path.join(REPO_ROOT, "webapp", "content-files", "gallery-items")


def _format_uuid(hex32):
    h = hex32.lower()
    return f"{h[0:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"


def _scan_local_exports():
    """Zdroj A (primarni, viz docstring modulu) - primo z vandrawee_work,
    zadne prohledavani Sdileneho disku. Vraci list kandidatu (dict:
    uuid, filename, shared_drive_file_id=None, fbx_path)."""
    env = _vandr_env()
    if not env:
        print("[vandr-fbx-watcher] /opt/vandrawee/web/.env nedostupny, zdroj A vynechan", file=sys.stderr)
        return []
    out = []
    try:
        conn_w = _vandr_conn(env, env.get("DB_VANDRAWEE_WORK_DATABASE", "vandrawee_work"))
        try:
            with conn_w.cursor() as cur_w:
                cur_w.execute("SELECT HEX(uuid) AS uuid_hex FROM stored_models WHERE fbx_exported_at IS NOT NULL")
                rows = cur_w.fetchall()
        finally:
            conn_w.close()
    except Exception as e:  # noqa: BLE001
        print(f"[vandr-fbx-watcher] scan vandrawee_work selhal: {e}", file=sys.stderr)
        return []
    for r in rows:
        uuid = _format_uuid(r["uuid_hex"])
        fbx_path = os.path.join(VANDR_EXPORT_DIR, uuid, f"{uuid}.fbx")
        if os.path.isfile(fbx_path):
            out.append({"uuid": uuid, "filename": f"{uuid}.fbx", "folder_id": None,
                        "shared_drive_file_id": None, "fbx_path": fbx_path})
    return out


def _descendant_folder_ids(cur, root_id):
    ids = {root_id}
    fronta = [root_id]
    while fronta:
        cur.execute("SELECT id FROM shared_drive_folders WHERE parent_folder_id=%s", (fronta.pop(),))
        for r in cur.fetchall():
            if r["id"] not in ids:
                ids.add(r["id"])
                fronta.append(r["id"])
    return ids


def _folder_path_label(cur, folder_id, cache):
    """Cesta slozek (bez korenu), napr. "A/B/C" - CISTE Robertovo vlastni
    razeni na Sdilenem disku (OPRAVA 2026-09-22: "nebudu vytvářet žádné
    sestavy podle aut... jen rozdelené abych se v tom sám vyznal"), NENI
    spolehlivy udaj o vozidlu/typu sestavy. Pouziva se jen jako
    diagnosticky kontext v logu/ukolu na zed, NIKDY jako soucast
    predpokladaneho nazvu vozidla."""
    if folder_id is None:
        return ""
    if folder_id in cache:
        return cache[folder_id]
    cur.execute("SELECT name, parent_folder_id FROM shared_drive_folders WHERE id=%s", (folder_id,))
    row = cur.fetchone()
    if not row:
        return ""
    parent_label = _folder_path_label(cur, row["parent_folder_id"], cache) if row["parent_folder_id"] else ""
    label = f"{parent_label}/{row['name']}" if parent_label else row["name"]
    cache[folder_id] = label
    return label


def _kopiruj_dim_obrazky(cur, shop_product_id, dim_images):
    """Zkopiruje kotovane 2D vykresy (stored_model_parts.image_2D_with_dim)
    do content_gallery_items - Robert 2026-09-23 ("porad cekam na
    kotovaný náhled"). Soubor uz ma vlastni vanDrawee vodoznak zapeceny
    primo v obrazku (stejne jako ostatni Vandr fotky) - NEPRIDAVAT dalsi."""
    cur.execute(
        "SELECT COALESCE(MAX(sort_order),-1)+1 AS n FROM content_gallery_items WHERE owner_type='product' AND owner_id=%s",
        (shop_product_id,),
    )
    sort_order = cur.fetchone()["n"]
    for src_path, part_role in dim_images:
        fname = f"product-{shop_product_id}_dim-{uuid_module.uuid4().hex[:8]}.png"
        dest = os.path.join(GALLERY_ITEMS_DIR, fname)
        try:
            shutil.copyfile(src_path, dest)
            os.chmod(dest, 0o644)
            subprocess.run(["chown", "www-data:www-data", dest], check=True)
        except OSError as e:
            print(f"[vandr-fbx-watcher] kopie kotovaneho nahledu selhala ({src_path}): {e}", file=sys.stderr)
            continue
        caption = "2D nákres s kótami" + (f", {part_role}" if part_role else "")
        cur.execute(
            "INSERT INTO content_gallery_items (owner_type, owner_id, filename, media_type, source_url, caption, is_public, sort_order) "
            "VALUES ('product', %s, %s, 'image', %s, %s, 1, %s)",
            (shop_product_id, fname, "vandrawee_work.stored_model_parts.image_2D_with_dim", caption, sort_order),
        )
        sort_order += 1


def _bez_diakritiky(s):
    return "".join(ch for ch in unicodedata.normalize("NFD", str(s)) if not unicodedata.combining(ch)).lower()


def _kategorie_modelu(cur, brand_cat, nazev):
    """Robert 2026-10-05 ("proč se poslední karty Master nezařadí do kategorie Master?"): karta se zařadí do kategorie MODELU
    (`Vestavby pro <značka> <model>`, dítě kategorie značky), pokud název vozidla obsahuje jeho model jako celé slovo(a);
    jinak zůstane v kategorii značky. Delší model (víc slov) vyhrává (Transit Connect nad Transit); shoda se stejným počtem slov
    u víc kategorií = nejednoznačné -> kategorie značky (nic se nehádá)."""
    if not brand_cat or not nazev:
        return brand_cat
    cur.execute("SELECT name FROM content_categories WHERE id=%s", (brand_cat,))
    rodic = cur.fetchone()
    cur.execute("SELECT id, name FROM content_categories WHERE parent_id=%s", (brand_cat,))
    deti = cur.fetchall()
    if not rodic or not deti:
        return brand_cat
    znacka = _bez_diakritiky(rodic["name"]).split()[-1]
    cil = _bez_diakritiky(nazev)
    shody = []
    for d in deti:
        model = re.sub(r"^(vestavby pro|vestavba dodavky)\s+", "", _bez_diakritiky(d["name"]))
        model = re.sub(rf"^{re.escape(znacka)}\s+", "", model).strip()
        if model and re.search(rf"(?<![a-z0-9]){re.escape(model)}(?![a-z0-9])", cil):
            shody.append((len(model.split()), d["id"]))
    if not shody:
        return brand_cat
    shody.sort(reverse=True)
    if len(shody) > 1 and shody[0][0] == shody[1][0]:
        return brand_cat
    return shody[0][1]


# Robert 2026-10-06 ("vestavby techto 3 modelu a jejich kategorie musime sloucit"): Ducato / Jumper / Boxer = JEDNA sloucena kategorie 233 ve stromu "Vestavby podle vozidla" (267);
# kategorie 300 "Vestavby pro Fiat Ducato" zanikla (scripts/2026-10-06_slouceni_ducato_jumper_boxer.py, zapis dela Robert). Nova karta tohoto modelu jde primarne rovnou do 233
# a znackova kategorie (Fiat 269 / Citroen 268 / Peugeot 288) zustane jako SEKUNDARNI vazba - stejne jako u presunutych sestav. Pred zapisem skriptu (233 jeste pod korenem 184)
# se nic nemeni a plati _kategorie_modelu.
SLOUCENA_KAT, SLOUCENA_RODIC = 233, 267
SLOUCENE_MODELY = {"ducato": 269, "jumper": 268, "boxer": 288}      # model -> znackova kategorie (musi sedet na kategorii z meta, jinak se nehada)


def _slouceny_model(cur, brand_cat, nazev):
    """-> (233, znackova_kategorie) pro vozidlo Ducato / Jumper / Boxer, je-li sloucena kategorie uz ve stromu (parent 267), jinak None. Nazev musi obsahovat PRESNE jeden z modelu
    jako cele slovo a znackova kategorie z meta musi sedet na tento model (Fiat Ducato -> 269 atd.); nejednoznacne = None (rozhodne _kategorie_modelu)."""
    if not brand_cat or not nazev:
        return None
    cil = _bez_diakritiky(nazev)
    modely = [m for m in SLOUCENE_MODELY if re.search(rf"(?<![a-z0-9]){m}(?![a-z0-9])", cil)]
    if len(modely) != 1 or SLOUCENE_MODELY[modely[0]] != brand_cat:
        return None
    cur.execute("SELECT id FROM content_categories WHERE id=%s AND parent_id=%s", (SLOUCENA_KAT, SLOUCENA_RODIC))
    return (SLOUCENA_KAT, brand_cat) if cur.fetchone() else None


def _zapsat_ukol_na_zed(cur, text, bot_id="bot5"):
    cur.execute("SELECT id FROM bot_ukoly WHERE bot_id=%s AND hotovo=0 AND text=%s", (bot_id, text))
    if cur.fetchone():
        return False
    cur.execute("INSERT INTO bot_ukoly (text, bot_id) VALUES (%s, %s)", (text, bot_id))
    return True


def _log(zprava):
    print(zprava)
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    entry = f"\n## vandr-fbx-watcher (automaticky, scripts/2026-09-22_vandr_fbx_watcher.py) — {ts}\n\n{zprava}\n"
    try:
        with open(os.path.join(REPO_ROOT, "AGENTS_LOG.md"), "a", encoding="utf-8") as f:
            f.write(entry)
    except OSError as e:
        print(f"[vandr-fbx-watcher] zapis do AGENTS_LOG.md selhal: {e}", file=sys.stderr)


def _scan_shared_drive(cur, jiz_zpracovane_soubory):
    """Zdroj B (fallback, viz docstring modulu). Vraci list kandidatu
    ve stejnem tvaru jako _scan_local_exports, plus rovnou 'chyba'
    zaznamy pro soubory s neplatnym nazvem (ty zadne UUID nemaji,
    dedupuji se proto zvlast - pres shared_drive_file_id, ne uuid)."""
    cur.execute(
        "SELECT id FROM shared_drive_folders WHERE parent_folder_id IS NULL AND name=%s",
        (ROOT_FOLDER_NAME,),
    )
    root = cur.fetchone()
    if not root:
        print(f"[vandr-fbx-watcher] korenova slozka '{ROOT_FOLDER_NAME}' na Sdilenem disku neexistuje, zdroj B vynechan", file=sys.stderr)
        return [], []
    folder_ids = _descendant_folder_ids(cur, root["id"])
    placeholders = ",".join(["%s"] * len(folder_ids))
    cur.execute(
        f"SELECT id, folder_id, filename FROM shared_drive_files "
        f"WHERE folder_id IN ({placeholders}) AND filename LIKE %s",
        tuple(folder_ids) + ("%.fbx",),
    )
    kandidati, chyby = [], []
    for f in cur.fetchall():
        if f["id"] in jiz_zpracovane_soubory:
            continue
        m = UUID_RE.match(f["filename"])
        if not m:
            chyby.append({"shared_drive_file_id": f["id"],
                          "text": f"Neplatný název souboru '{f['filename']}' (Sdílený disk, složka #{f['folder_id']}) - očekáván formát <uuid>.fbx"})
            continue
        uuid = m.group(1).lower()
        kandidati.append({"uuid": uuid, "filename": f["filename"], "folder_id": f["folder_id"],
                          "shared_drive_file_id": f["id"], "fbx_path": None})
    return kandidati, chyby


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    print(f"=== Vandr FBX watcher — {'APPLY' if args.apply else 'DRY-RUN'} ===\n")

    conn = get_conn()
    vysledky = []
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT vandrawee_uuid, shared_drive_file_id FROM vandr_fbx_queue")
            drive_rows = cur.fetchall()
            uz_zpracovano = {r["vandrawee_uuid"] for r in drive_rows if r["vandrawee_uuid"] is not None}
            uz_zpracovane_soubory = {r["shared_drive_file_id"] for r in drive_rows if r["shared_drive_file_id"] is not None}

            # Zdroj A (primarni) PRED zdrojem B (fallback) - pri stejnem
            # UUID z obou zdroju vyhrava A, viz dedup nize.
            kandidati_a = _scan_local_exports()
            kandidati_b, chyby_b = _scan_shared_drive(cur, uz_zpracovane_soubory)
            for chyba in chyby_b:
                vysledky.append({"uuid": None, "filename": chyba["text"], "stav": "chyba", "shop_product_id": None,
                                 "info": chyba["text"], "meta": None, "shared_drive_file_id": chyba["shared_drive_file_id"]})

            kombinovano = {}
            for k in kandidati_a + kandidati_b:
                if k["uuid"] in uz_zpracovano or k["uuid"] in kombinovano:
                    continue
                kombinovano[k["uuid"]] = k
            nove = list(kombinovano.values())

            if not nove and not vysledky:
                print("0 novych .fbx souboru/exportu, konec.")
                return 0

            folder_cache = {}
            for k in nove:
                uuid = k["uuid"]
                sku = f"VD-{uuid}"
                cur.execute("SELECT id, name, active FROM shop_products WHERE sku=%s", (sku,))
                existujici = cur.fetchone()
                if existujici:
                    vysledky.append({**k, "stav": "karta_existovala", "shop_product_id": existujici["id"],
                                     "info": f"Karta {sku} (#{existujici['id']}) už existovala z dřívějšího CSV importu.",
                                     "meta": None})
                    continue
                meta = _lookup_vandr_metadata(uuid)
                if meta and (meta.get("pocet_stran") or 0) >= 2:
                    nazvy = {"left_part_id": "levá", "right_part_id": "pravá", "bulkhead_part_id": "přepážka"}
                    strany_txt = ", ".join(f"{nazvy[n]} {u or '(samostatný model nenalezen)'}"
                                           for n, u in (meta.get("samostatne_strany") or {}).items())
                    vysledky.append({**k, "stav": "chyba", "shop_product_id": None, "meta": None, "kombinace": True,
                                     "info": (f"FBX {uuid} je kombinace více stran v jednom modelu - kartu "
                                              f"NEZAKLÁDÁM (Robert 2026-09-30: kombinace se dělí na samostatné "
                                              f"karty stran). Ve Vandr adminu vyexportovat FBX jednotlivých stran: "
                                              f"{strany_txt}.")})
                    continue
                if meta:
                    draft_name = meta["name"] or f"Vandr sestava – {uuid[:8]} (doplnit název)"
                    popis = (f"nalezeno v lokální vandrawee_work DB: {draft_name}, "
                             f"{meta['price_czk']} Kč, {meta['weight_g']} g" if meta["price_czk"] else
                             f"{draft_name} (bez ceny v lokální DB)")
                else:
                    # Slozka je jen Robertovo vlastni razeni (viz docstring
                    # _folder_path_label), NENI vozidlo - jen diagnosticky
                    # kontext v poznamce, NIKDY soucast nazvu karty.
                    cesta = _folder_path_label(cur, k["folder_id"], folder_cache) if k["folder_id"] else None
                    draft_name = f"Vandr sestava – {uuid[:8]} (doplnit název/cenu)"
                    zdroj_popis = f"složka na disku: {cesta}" if cesta else "export z vandrawee adminu"
                    popis = f"nenalezeno v lokální vandrawee_work DB ({zdroj_popis})"
                vysledky.append({**k, "stav": "karta_zalozena", "shop_product_id": None, "info": draft_name, "meta": meta})
                if not args.apply:
                    print(f"    -> {popis}")

            if not args.apply:
                for v in vysledky:
                    print(f"[{v['stav']}] {v['filename']} -> {v['info']}")
                print("\nDRY-RUN: nic nezapsano.")
                return 0

            for v in vysledky:
                new_pid = v["shop_product_id"]
                if v["stav"] == "karta_zalozena":
                    # Robert 2026-10-05 ("proč jsou některé bez názvu Regálová vestavba?"): starší karty z CSV importu se jmenují
                    # "Regálová vestavba – <vozidlo>", nové z watcheru jen "<vozidlo>" -> stejná předpona (adresa z názvu přes product_slug)
                    nazev_karty = v["info"] if v["info"].startswith(("Regálová vestavba", "Vandr sestava")) else f"Regálová vestavba – {v['info']}"
                    slug = product_slug.slug_for_name(cur, nazev_karty)
                    specs_json = (v["meta"] or {}).get("product_specs_json")
                    slouceno = _slouceny_model(cur, (v["meta"] or {}).get("category_id"), v["info"])           # Ducato / Jumper / Boxer -> sloucena kat. 233 (+ znackova jako sekundarni)
                    cur.execute(
                        "INSERT INTO shop_products (sku, name, slug, active, price_czk_placeholder, weight_g, "
                        "category_id, description, short_description, product_specs_json, supplier_name, "
                        "umisteni_id, price_visible_default) "
                        # bot5, 2026-09-30 (Robert nahlasil pres bot3, overeno primo: 7 karet VW
                        # Crafter L3H3 FWD zalozenych dnes mely price_visible_default=1 misto 0,
                        # takze na eshopu chybel hover efekt - skryta cena + jiny obrazek -, ktery
                        # maji VSECHNY starsi VD-% karty stejne rodiny, viz napr. id 4025/4366-4482
                        # "Regálová vestavba – VW Crafter L3H3 FWD" z 17.-18.9., vsechny s 0) -
                        # sloupec tu chybel uplne, ticha padla na DEFAULT tabulky (1).
                        "VALUES (%s,%s,%s,0,%s,%s,%s,%s,%s,%s,'vanDrawee',%s,0)",
                        (f"VD-{v['uuid']}", nazev_karty, slug,
                         (v["meta"] or {}).get("price_czk"), (v["meta"] or {}).get("weight_g"),
                         slouceno[0] if slouceno else _kategorie_modelu(cur, (v["meta"] or {}).get("category_id"), v["info"]), (v["meta"] or {}).get("description"),
                         (v["meta"] or {}).get("short_description"),
                         json.dumps(specs_json, ensure_ascii=False) if specs_json else None,
                         # WORKFLOW.md pravidlo 51: stitek umisteni pri zalozeni karty, ne az
                         # dodatecnym backfillem - viz scripts/_vandr_umisteni.py.
                         (v["meta"] or {}).get("umisteni_id")),
                    )
                    new_pid = cur.lastrowid
                    v["shop_product_id"] = new_pid
                    if slouceno:
                        cur.execute("INSERT IGNORE INTO shop_product_categories (product_id, category_id) VALUES (%s,%s)", (new_pid, slouceno[1]))
                    _kopiruj_dim_obrazky(cur, new_pid, (v["meta"] or {}).get("dim_images") or [])
                    chybi = []
                    if not v["meta"] or not v["meta"].get("price_czk"):
                        chybi.append("cena (nenalezena ani v lokální vandrawee_work DB)")
                    if not v["meta"] or not v["meta"].get("category_id"):
                        chybi.append("kategorie (značka nerozpoznána nebo mimo mapování ZNACKA_ID_TO_CATEGORY)")
                    if chybi:
                        _zapsat_ukol_na_zed(
                            cur,
                            f"NOVÁ VANDR KARTA #{new_pid}: \"{v['info']}\" založena automaticky z FBX "
                            f"'{v['filename']}'. Chybí: {', '.join(chybi)} - "
                            f"doplň v adminu, karta se aktivuje automaticky, jakmile bude mít cenu I "
                            f"dokončený render (kategorie sama aktivaci neblokuje, ale bez ní karta "
                            f"není nikde v prohlížení webu vidět).",
                        )
                if v.get("kombinace"):
                    # Robert 2026-10-05: karty dělá bot5 (render bot4), bot10 jen předal -> úkol kombinace stran jde na bot5
                    _zapsat_ukol_na_zed(cur, f"VANDR KOMBINACE STRAN: {v['info']}", bot_id="bot5")
                if v["uuid"] is not None or v.get("shared_drive_file_id") is not None:
                    cur.execute(
                        "INSERT INTO vandr_fbx_queue (shared_drive_file_id, vandrawee_uuid, shop_product_id, stav, poznamka) "
                        "VALUES (%s,%s,%s,%s,%s)",
                        (v.get("shared_drive_file_id"), v["uuid"], new_pid, v["stav"], v["info"]),
                    )
                print(f"[{v['stav']}] {v['filename']} -> {v['info']}")
        conn.commit()
    finally:
        conn.close()

    if args.apply and vysledky:
        shrnuti = "\n".join(f"- [{v['stav']}] `{v['filename']}` — {v['info']}" for v in vysledky)
        _log(f"Zpracováno {len(vysledky)} nových FBX/exportů:\n\n{shrnuti}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
