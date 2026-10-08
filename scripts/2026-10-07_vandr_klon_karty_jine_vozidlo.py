#!/usr/bin/env python3
"""2026-10-07_vandr_klon_karty_jine_vozidlo.py - Vandr karta pro STEJNOU sestavu v JINEM vozidle (bot5, Robert 2026-10-07: "VD-2c24d107-... zprovoznit i pro MAN L3H3";
klik "Nova karta MAN"): VW Crafter a MAN TGE jsou dvojcata (stejna karoserie), sestava je stejna, jina je jen znacka/nazev/kategorie.

CO SKRIPT DELA (jedna transakce; kopie GLB souboru se pri chybe smaze):
  1) novy radek shop_products = KLON zdrojove karty: nove SKU `VD-<nove uuid>` (stejny tvar jako Vandr karty, at je beru automaty razitek / renderu / aktivace), nazev a popisy s novym
     vozidlem, nova adresa (product_slug), kategorie znacky (kdyz neexistuje, zalozi se pod "Vestavby podle vozidla" 267 jen s nazvem - texty pise bot7, ukol na zed), cena a ostatni
     zustavaji; `active` = 0 (pravidlo 54 - aktivuje az automat po cene + kategorii + renderech jako u kazde Vandr karty).
  2) NOVA KOPIE GLB souboru (webapp/katalog/vandr/ - chranena slozka, commit pod DEPLOY_LOCK) - jinak by razitka/render/smazani jedne karty ovlivnily druhou. Razitka a render si
     automaty spocitaji samy (otisky se nekopiruji), predni azimut a hlavni prurez se kopiruji (stejny model).
  3) audit_log + ukol na zed pro bot7 (texty nove kategorie).
  5) MAPOVANI VANDR DAT: klon nema Vandr data pod svym uuid (vandr:offer-data zna jen zdroj) - skript zapise {uuid klonu: uuid zdroje} do private-files/vandr-klony.json
     (cte api/vandr_scene_offers.py::_vandr_uuid_karty), aby sel z klonu udelat online nabidku / kontrolni 3D scenu stejne jako ze zdroje.
  4) HOTOVE RENDERY SE PREBIRAJI (Robert 2026-10-07: "je to tatáž karta jen pro jine auto" - obrazky jsou hotove): kopie otocnych snimku (content-files/turntable-frames/<id>/ + radky
     product_turntable_frames), Vandr 2D nakres a "Nahled sestavy" v galerii, a razitka (json + otisky, platne, protoze GLB je bajt po bajtu stejny) -> automaty nic znovu nerenderuji;
     nahled a kanonicke obrazky pak vyrobi `turntable.regenerate_canonical(<id>)` (pod www-data, viz nize).
CO NEDELA: nekopiruje Vandr data (vandr_stored_model_uuid je unikatni) - nabidka z teto karty nema Vandr 3D data (stejne jako karta #4969).
Pouziti (z roota, ve slozce repa; faze 4 s rendery piš jako www-data, aby nove soubory v content-files mely spravneho vlastnika):
  api/venv/bin/python3 scripts/2026-10-07_vandr_klon_karty_jine_vozidlo.py --zdroj 4967 --vozidlo "MAN TGE L3H3 FWD" --stare-vozidlo "VW Crafter L3H3 FWD" --kategorie "Vestavby pro MAN"            # nahled
  ... --apply
Doplneni renderu k UZ zalozenemu klonu:  systemd-run -p User=www-data -p Group=www-data -p Type=oneshot --wait -p WorkingDirectory=/opt/konfigurator api/venv/bin/python3 \
      scripts/2026-10-07_vandr_klon_karty_jine_vozidlo.py --zdroj 4967 --dopln 4971 --apply          ; potom jako www-data: api/venv/bin/python3 -c 'import app, turntable; turntable.regenerate_canonical(4971)'
"""
import argparse
import json
import os
import re
import shutil
import sys
import uuid as uuid_module

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "api"))
import product_slug  # noqa: E402
import product_duplicate  # noqa: E402

KATALOG_DIR = os.path.join(REPO, "webapp", "katalog")
UPLOAD_DIR = os.environ.get("CONTENT_UPLOAD_DIR", "/opt/konfigurator/webapp/content-files")
FRAMES_PODADRESAR = "turntable-frames"
PRIVATE_FILES_DIR = os.environ.get("PRIVATE_FILES_DIR", os.path.join(REPO, "private-files"))
KLONY_SOUBOR = os.path.join(PRIVATE_FILES_DIR, "vandr-klony.json")      # {uuid klonu: uuid zdroje} - cte api/vandr_scene_offers.py::_vandr_uuid_karty
GALERIE_DIR = os.path.join(UPLOAD_DIR, "gallery-items")
RODIC_VOZIDLA = 267          # "Vestavby podle vozidla"
VD_SKU_RE = re.compile(r"^VD-([0-9a-f]{8})-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE)
# z RESET_NULL se NEresetuje: predni azimut a hlavni prurez (stejny model -> stejne hodnoty); vse ostatni z RESET_NULL ano
ZACHOVAT = ("vandr_predni_azimut_deg", "vandr_hlavni_prurez_mm")


class Chyba(Exception):
    pass


def _nahrad(text, stare, nove):
    return text.replace(stare, nove) if isinstance(text, str) else text


def zapis_mapovani(klon_sku, zdroj_sku, soubor=KLONY_SOUBOR):
    """Prida {uuid klonu: uuid zdroje} do souboru mapovani (atomicky: tmp + replace, cteni pro vsechny). Vraci cele mapovani."""
    m_k, m_z = VD_SKU_RE.match(klon_sku or ""), VD_SKU_RE.match(zdroj_sku or "")
    if not m_k or not m_z:
        raise Chyba(f"SKU klonu/zdroje nema tvar VD-<uuid>: {klon_sku} / {zdroj_sku}")
    klon_uuid, zdroj_uuid = klon_sku[3:].lower(), zdroj_sku[3:].lower()
    data = {}
    if os.path.exists(soubor):
        with open(soubor, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise Chyba(f"{soubor} nema tvar objektu")
    data[klon_uuid] = data.get(zdroj_uuid, zdroj_uuid)          # klon klonu se rozbali na puvodni zdroj
    os.makedirs(os.path.dirname(soubor), exist_ok=True)
    tmp = soubor + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1, sort_keys=True)
    os.chmod(tmp, 0o644)
    os.replace(tmp, soubor)
    return data


def prevezmi_nahled(cur, zdroj_id, klon_id, katalog_dir=KATALOG_DIR):
    """Nahled karty (shop_products.thumbnail_file, soubor v katalog/thumbnails/): kopie souboru zdroje pod nazvem klonu + zapis sloupce. Nic neprepisuje (klon uz nahled ma = nic).
    -> cesta noveho souboru | None. Nekomituje."""
    cur.execute("SELECT id, thumbnail_file FROM shop_products WHERE id IN (%s,%s)", (zdroj_id, klon_id))
    sp = {r["id"]: r for r in cur.fetchall()}
    z, k = sp.get(zdroj_id), sp.get(klon_id)
    if not z or not k:
        raise Chyba("zdroj nebo klon neexistuje")
    if not z["thumbnail_file"] or k["thumbnail_file"]:
        return None
    m = re.match(rf"^(?P<adr>[a-z_]+)/product-{zdroj_id}(?P<pr>\.[A-Za-z0-9]+)$", z["thumbnail_file"])
    if not m:
        raise Chyba(f"nahled zdroje '{z['thumbnail_file']}' nema tvar <adresar>/product-{zdroj_id}.<pripona>")
    novy_rel = f"{m.group('adr')}/product-{klon_id}{m.group('pr')}"
    src, dst = os.path.join(katalog_dir, z["thumbnail_file"]), os.path.join(katalog_dir, novy_rel)
    if not os.path.isfile(src):
        raise Chyba(f"soubor nahledu zdroje chybi: {src}")
    if os.path.exists(dst):
        raise Chyba(f"soubor nahledu klonu uz existuje: {dst}")
    shutil.copyfile(src, dst)
    cur.execute("UPDATE shop_products SET thumbnail_file=%s WHERE id=%s AND thumbnail_file IS NULL", (novy_rel, klon_id))
    cur.execute("SELECT thumbnail_file FROM shop_products WHERE id=%s", (klon_id,))
    if cur.fetchone()["thumbnail_file"] != novy_rel:
        os.remove(dst)
        raise Chyba("zapis nahledu klonu selhal")
    return dst


def prevezmi_rendery(cur, zdroj_id, klon_id, upload_dir=UPLOAD_DIR):
    """Hotove rendery zdrojove karty -> klon (stejna sestava, stejny GLB): snimky otocky (soubory + radky), razitka (json + otisky), "Nahled sestavy" v galerii (kdyz klon nema).
    Nekomituje; pri chybe smaze nove soubory a vyhodi vyjimku (volajici dela rollback). -> dict {snimku, galerie_nahled, razitka}"""
    frames_src = os.path.join(upload_dir, FRAMES_PODADRESAR, str(zdroj_id))
    frames_dst = os.path.join(upload_dir, FRAMES_PODADRESAR, str(klon_id))
    cur.execute("SELECT * FROM product_turntable_frames WHERE shop_product_id=%s AND is_active=1 ORDER BY id", (zdroj_id,))
    radky = cur.fetchall()
    if not radky:
        raise Chyba(f"zdrojova karta {zdroj_id} nema aktivni snimky otocky")
    cur.execute("SELECT COUNT(*) AS n FROM product_turntable_frames WHERE shop_product_id=%s", (klon_id,))
    if cur.fetchone()["n"]:
        raise Chyba(f"klon {klon_id} uz ma snimky otocky - neprepisuji")
    if not os.path.isdir(frames_src):
        raise Chyba(f"adresar snimku zdroje chybi: {frames_src}")
    if os.path.exists(frames_dst):
        raise Chyba(f"cilovy adresar snimku uz existuje: {frames_dst}")
    cur.execute("SELECT * FROM shop_products WHERE id IN (%s,%s)", (zdroj_id, klon_id))
    sp = {r["id"]: r for r in cur.fetchall()}
    if zdroj_id not in sp or klon_id not in sp:
        raise Chyba("zdroj nebo klon neexistuje")
    zdroj, klon = sp[zdroj_id], sp[klon_id]
    if not zdroj["glb_file"] or not klon["glb_file"]:
        raise Chyba("zdroj i klon musi mit GLB")
    nove_soubory = []
    try:
        shutil.copytree(frames_src, frames_dst)
        for r in radky:
            novy = {k: v for k, v in r.items() if k not in ("id",)}
            novy["shop_product_id"] = klon_id
            novy["filename"] = (r["filename"] or "").replace(f"{FRAMES_PODADRESAR}/{zdroj_id}/", f"{FRAMES_PODADRESAR}/{klon_id}/", 1)
            if novy["filename"] == r["filename"]:
                raise Chyba(f"cesta snimku {r['filename']} nema tvar {FRAMES_PODADRESAR}/{zdroj_id}/...")
            sl = list(novy.keys())
            cur.execute("INSERT INTO product_turntable_frames (" + ",".join(f"`{c}`" for c in sl) + ") VALUES (" + ",".join(["%s"] * len(sl)) + ")", [novy[c] for c in sl])
        # razitka: GLB je bajt po bajtu stejny -> json i otisky platne (render dispatch pak vidi aktualni render a nerenderuje znovu)
        cur.execute("UPDATE shop_products SET vandr_razitka_json=%s, vandr_razitka_glb_otisk=%s, vandr_razitka_hotovo_at=%s, vandr_render_razitka_otisk=%s WHERE id=%s",
                    (zdroj["vandr_razitka_json"], zdroj["vandr_razitka_glb_otisk"], zdroj["vandr_razitka_hotovo_at"], zdroj["vandr_render_razitka_otisk"], klon_id))
        cur.execute("SELECT vandr_razitka_json, vandr_razitka_glb_otisk, vandr_razitka_hotovo_at, vandr_render_razitka_otisk FROM shop_products WHERE id=%s", (klon_id,))
        kontrola = cur.fetchone()          # rowcount UPDATE by u uz shodnych hodnot byl 0 - overuje se vysledek
        if not kontrola or any(kontrola[c] != zdroj[c] for c in ("vandr_razitka_json", "vandr_razitka_glb_otisk", "vandr_razitka_hotovo_at", "vandr_render_razitka_otisk")):
            raise Chyba("razitka klonu po UPDATE nesedi se zdrojem")
        # "Nahled sestavy" v galerii
        cur.execute("SELECT * FROM content_gallery_items WHERE owner_type='product' AND owner_id=%s AND source_url IS NULL AND caption='Náhled sestavy' ORDER BY id LIMIT 1", (zdroj_id,))
        nahled = cur.fetchone()
        cur.execute("SELECT COUNT(*) AS n FROM content_gallery_items WHERE owner_type='product' AND owner_id=%s AND caption='Náhled sestavy'", (klon_id,))
        galerie = 0
        if nahled and not cur.fetchone()["n"]:
            nove_jmeno = nahled["filename"].replace(f"product-{zdroj_id}_", f"product-{klon_id}_", 1)
            if nove_jmeno == nahled["filename"]:
                raise Chyba(f"nazev nahledu {nahled['filename']} nema tvar product-{zdroj_id}_...")
            gdir = os.path.join(upload_dir, "gallery-items")
            shutil.copyfile(os.path.join(gdir, nahled["filename"]), os.path.join(gdir, nove_jmeno))
            nove_soubory.append(os.path.join(gdir, nove_jmeno))
            novy = {k: v for k, v in nahled.items() if k not in ("id", "created_at")}
            novy["owner_id"], novy["filename"] = klon_id, nove_jmeno
            sl = list(novy.keys())
            cur.execute("INSERT INTO content_gallery_items (" + ",".join(f"`{c}`" for c in sl) + ") VALUES (" + ",".join(["%s"] * len(sl)) + ")", [novy[c] for c in sl])
            galerie = 1
        cur.execute("SELECT COUNT(*) AS n FROM product_turntable_frames WHERE shop_product_id=%s AND is_active=1", (klon_id,))
        if cur.fetchone()["n"] != len(radky):
            raise Chyba("pocet nakopirovanych snimku nesedi")
        cur.execute("INSERT INTO audit_log (user_id, action, entity_type, entity_id, detail) VALUES (NULL,'update','shop_product',%s,%s)",
                    (klon_id, f"prevzate hotove rendery z karty {zdroj_id}: {len(radky)} snimku otocky, razitka, nahled v galerii (Robert 2026-10-07: tatez karta pro jine auto)"))
    except BaseException:
        shutil.rmtree(frames_dst, ignore_errors=True)
        for f in nove_soubory:
            try:
                os.remove(f)
            except OSError:
                pass
        raise
    return {"snimku": len(radky), "galerie_nahled": galerie, "razitka": bool(zdroj["vandr_razitka_glb_otisk"]), "frames_dst": frames_dst, "nove_soubory": nove_soubory}


def klonuj(cur, zdroj_id, vozidlo, stare_vozidlo, kategorie_nazev, katalog_dir=KATALOG_DIR, rodic_kategorie=RODIC_VOZIDLA, nova_uuid=None, galerie_dir=GALERIE_DIR, s_rendery=True, upload_dir=UPLOAD_DIR, povol_stejny_nazev=False):
    """-> dict s vysledkem (id, sku, glb_file, kategorie_id, kategorie_nova, nazev). Nic nekomituje; kopie GLB souboru se vraci v 'glb_cesta' (volajici ji pri rollbacku smaze)."""
    cur.execute("SELECT * FROM shop_products WHERE id=%s", (zdroj_id,))
    z = cur.fetchone()
    if not z:
        raise Chyba(f"zdrojova karta {zdroj_id} neexistuje")
    if not VD_SKU_RE.match(z["sku"] or ""):
        raise Chyba(f"zdrojova karta {zdroj_id} neni Vandr karta (SKU {z['sku']})")
    if not z["glb_file"] or not os.path.isfile(os.path.join(katalog_dir, z["glb_file"])):
        raise Chyba(f"zdrojova karta nema GLB na disku ({z['glb_file']})")
    if stare_vozidlo not in (z["name"] or ""):
        raise Chyba(f"nazev zdrojove karty '{z['name']}' neobsahuje '{stare_vozidlo}' - zkontroluj --stare-vozidlo")
    nazev = _nahrad(z["name"], stare_vozidlo, vozidlo)
    cur.execute("SELECT id FROM shop_products WHERE name=%s", (nazev,))
    if cur.fetchone() and not povol_stejny_nazev:
        # Vandr karty maji stejny nazev pro vice stran/provedeni (napr. 21 karet "Crafter L3H3 FWD", rozlisuje je umisteni RL/RP a adresa) - pak --povol-stejny-nazev
        raise Chyba(f"karta '{nazev}' uz existuje - nezaklada se podruhe (stejny nazev u dalsi strany/provedeni: --povol-stejny-nazev)")
    # kategorie znacky
    cur.execute("SELECT id FROM content_categories WHERE parent_id=%s AND name=%s", (rodic_kategorie, kategorie_nazev))
    k = cur.fetchone()
    kategorie_nova = k is None
    if k:
        kat_id = k["id"]
    else:
        slug_k = product_slug.slugify(kategorie_nazev)
        cur.execute("SELECT id FROM content_categories WHERE slug=%s", (slug_k,))
        if cur.fetchone():
            raise Chyba(f"adresa kategorie '{slug_k}' je uz obsazena jinou kategorii")
        cur.execute("SELECT COALESCE(MAX(sort_order), 0) + 1 AS n FROM content_categories WHERE parent_id=%s", (rodic_kategorie,))
        poradi = cur.fetchone()["n"]
        cur.execute("INSERT INTO content_categories (parent_id, name, slug, sort_order, is_visible, nav_label) VALUES (%s,%s,%s,%s,1,%s)",
                    (rodic_kategorie, kategorie_nazev, slug_k, poradi, kategorie_nazev))
        kat_id = cur.lastrowid
    # dokumenty se nekopiruji (u Vandr karet nejsou); fotogalerie ANO (Vandr 2D nakres s kotami + "Nahled sestavy" = stejna sestava)
    cur.execute("SELECT COUNT(*) AS d FROM shop_product_documents WHERE product_id=%s", (zdroj_id,))
    if cur.fetchone()["d"]:
        raise Chyba("zdrojova karta ma dokumenty - skript je nekopiruje, doresit rucne")
    # nove SKU + GLB
    uid = nova_uuid or str(uuid_module.uuid4())
    sku = f"VD-{uid}"
    glb_novy = f"vandr/vd_export_{re.sub(r'[^a-z0-9]+', '_', product_slug.slugify(nazev)).strip('_')}_{uid[:8]}.glb"
    glb_cesta = os.path.join(katalog_dir, glb_novy)
    if os.path.exists(glb_cesta):
        raise Chyba(f"GLB {glb_novy} uz existuje")
    shutil.copyfile(os.path.join(katalog_dir, z["glb_file"]), glb_cesta)
    res = rendery = None
    try:
        # jadro = otestovana duplikace produktu (neaktivni kopie, vynulovane identity/razitka/render, kopie obrazku z importu); pak se kopii dodaji Vandr udaje
        res = product_duplicate.duplicate_product(cur, zdroj_id, slug_for_name=lambda c, n: product_slug.slug_for_name(c, n), created_by=None, created_role=None,
                                                  gallery_dir=galerie_dir, docs_dir=os.path.join(katalog_dir, "_zadne_dokumenty"))
        novy_id = res["id"]
        cur.execute("SELECT filename FROM content_gallery_items WHERE owner_type='product' AND owner_id=%s", (novy_id,))
        galerie_soubory = [g["filename"] for g in cur.fetchall()]
        n = cur.execute(
            "UPDATE shop_products SET sku=%s, name=%s, slug=%s, description=%s, short_description=%s, category_id=%s, glb_file=%s, thumbnail_file=NULL, "
            "vandr_predni_azimut_deg=%s, vandr_hlavni_prurez_mm=%s, active=0 WHERE id=%s",
            (sku, nazev, product_slug.slug_for_name(cur, nazev, novy_id), _nahrad(z["description"], stare_vozidlo, vozidlo), _nahrad(z["short_description"], stare_vozidlo, vozidlo),
             kat_id, glb_novy, z.get("vandr_predni_azimut_deg"), z.get("vandr_hlavni_prurez_mm"), novy_id))
        if n != 1:
            raise Chyba(f"UPDATE klonu zmenil {n} radku (ocekavan 1)")
        cur.execute("INSERT INTO audit_log (user_id, action, entity_type, entity_id, detail) VALUES (NULL,'create','shop_product',%s,%s)",
                    (novy_id, f"klon Vandr karty {zdroj_id} pro vozidlo '{vozidlo}' (Robert 2026-10-07), SKU {sku}, kategorie {kat_id}{' (nove zalozena)' if kategorie_nova else ''}, neaktivni"))
        rendery = prevezmi_rendery(cur, zdroj_id, novy_id, upload_dir=upload_dir) if s_rendery else None
        if s_rendery:
            nahled_soubor = prevezmi_nahled(cur, zdroj_id, novy_id, katalog_dir=katalog_dir)
            if nahled_soubor:
                rendery["nove_soubory"].append(nahled_soubor)
        if kategorie_nova:
            cur.execute("INSERT INTO bot_ukoly (text, bot_id) VALUES (%s,'bot7')",
                        (f"NOVÁ KATEGORIE #{kat_id} \"{kategorie_nazev}\" (pod Vestavby podle vozidla) je založená BEZ textů (Robert 2026-10-07: sestava VW Crafter L3H3 FWD i pro MAN TGE L3H3, karta #{novy_id}) - "
                         f"doplň popisný text a SEO podle TEXT_FILTR.md, až bude karta aktivní.",))
    except BaseException:
        if os.path.exists(glb_cesta):
            os.remove(glb_cesta)
        for f in (res or {}).get("created_files", []) + ((rendery or {}).get("nove_soubory", [])):
            try:
                os.remove(f)
            except OSError:
                pass
        if rendery:
            shutil.rmtree(rendery["frames_dst"], ignore_errors=True)
        raise
    slug = None
    return {"id": novy_id, "sku": sku, "nazev": nazev, "glb_file": glb_novy, "glb_cesta": glb_cesta, "galerie_soubory": galerie_soubory, "rendery": rendery, "zdroj_sku": z["sku"], "kategorie_id": kat_id, "kategorie_nova": kategorie_nova, "slug": product_slug.slug_for_name(cur, nazev, novy_id)}


def _uklid_kopie(vys_rendery, galerie_soubory=(), glb_cesta=None):
    """smaze fyzicke kopie z nahledu (--apply nebylo): snimky otocky, galerie, GLB"""
    if vys_rendery:
        shutil.rmtree(vys_rendery["frames_dst"], ignore_errors=True)
        for f in vys_rendery["nove_soubory"]:
            try:
                os.remove(f)
            except OSError:
                pass
    for f in galerie_soubory:
        try:
            os.remove(os.path.join(GALERIE_DIR, f))
        except OSError:
            pass
    if glb_cesta and os.path.exists(glb_cesta):
        os.remove(glb_cesta)


def _chown_www(cesty):
    """nove soubory v content-files maji patrit www-data (jako ostatni; aplikace do nich pise); root-vlastnene by pozdejsi zapis aplikace zablokovaly"""
    try:
        import pwd
        uid, gid = pwd.getpwnam("www-data").pw_uid, pwd.getpwnam("www-data").pw_gid
    except KeyError:
        return
    for c in cesty:
        if os.path.isdir(c):
            os.chown(c, uid, gid)
            for koren, adresare, soubory in os.walk(c):
                for n in adresare + soubory:
                    os.chown(os.path.join(koren, n), uid, gid)
        elif os.path.exists(c):
            os.chown(c, uid, gid)


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--zdroj", type=int, required=True)
    ap.add_argument("--vozidlo")
    ap.add_argument("--stare-vozidlo")
    ap.add_argument("--kategorie")
    ap.add_argument("--dopln", type=int, help="jen doplnit hotove rendery k UZ zalozenemu klonu (id klonu)")
    ap.add_argument("--dopln-mapovani", type=int, help="jen zapsat mapovani Vandr dat (uuid klonu -> uuid zdroje) k UZ zalozenemu klonu (id klonu)")
    ap.add_argument("--dopln-nahled", type=int, help="jen doplnit nahled karty (thumbnail) k UZ zalozenemu klonu (id klonu)")
    ap.add_argument("--povol-stejny-nazev", action="store_true", help="povolit nazev, ktery uz ma jina karta (dalsi strana/provedeni stejneho vozidla; adresu rozlisi product_slug)")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args(argv)
    from _env import get_conn
    conn = get_conn()
    cur = conn.cursor()
    try:
        if a.dopln_mapovani:
            cur.execute("SELECT id, sku FROM shop_products WHERE id IN (%s,%s)", (a.zdroj, a.dopln_mapovani))
            sk = {r["id"]: r["sku"] for r in cur.fetchall()}
            if a.zdroj not in sk or a.dopln_mapovani not in sk:
                raise Chyba("zdroj nebo klon neexistuje")
            print("mapovani:", sk[a.dopln_mapovani], "->", sk[a.zdroj])
            if a.apply:
                print("ZAPSANO do", KLONY_SOUBOR, ":", zapis_mapovani(sk[a.dopln_mapovani], sk[a.zdroj]))
            else:
                print("(nahled - nic nezapsano; spust s --apply)")
            return 0
        if a.dopln_nahled:
            dst = prevezmi_nahled(cur, a.zdroj, a.dopln_nahled)
            print("nahled:", dst)
            if not a.apply:
                conn.rollback()
                if dst:
                    os.remove(dst)
                print("(nahled - nic nezapsano; spust s --apply)")
                return 0
            conn.commit()
            if dst:
                print("ZAPSANO. Soubor nahledu ke commitu (katalog je chranena slozka - pod DEPLOY_LOCK, explicitni cesta):", dst)
            return 0
        if a.dopln:
            r = prevezmi_rendery(cur, a.zdroj, a.dopln)
            print("rendery:", {k: v for k, v in r.items() if k not in ("nove_soubory",)})
            if not a.apply:
                conn.rollback()
                _uklid_kopie(r)
                print("(nahled - nic nezapsano, kopie souboru smazany; spust s --apply)")
                return 0
            conn.commit()
            _chown_www([r["frames_dst"]] + r["nove_soubory"])
            print("ZAPSANO. Dale: kanonicke obrazky a nahled -> jako www-data: api/venv/bin/python3 -c 'import app, turntable; turntable.regenerate_canonical(%d)'" % a.dopln)
            return 0
        if not (a.vozidlo and a.stare_vozidlo and a.kategorie):
            ap.error("--vozidlo, --stare-vozidlo a --kategorie jsou povinne (kdyz neni --dopln)")
        vys = klonuj(cur, a.zdroj, a.vozidlo, a.stare_vozidlo, a.kategorie, povol_stejny_nazev=a.povol_stejny_nazev)
        print(json.dumps({k: v for k, v in vys.items() if k not in ("glb_cesta", "galerie_soubory", "rendery")}, ensure_ascii=False), "| galerie:", vys["galerie_soubory"],
              "| rendery:", {k: v for k, v in (vys["rendery"] or {}).items() if k != "nove_soubory"})
        if not a.apply:
            conn.rollback()
            _uklid_kopie(vys["rendery"], vys["galerie_soubory"], vys["glb_cesta"])
            print("(nahled - nic nezapsano, kopie souboru smazany; spust s --apply)")
            return 0
        conn.commit()
        zapis_mapovani(vys["sku"], vys["zdroj_sku"])
        _chown_www([os.path.join(GALERIE_DIR, f) for f in vys["galerie_soubory"]] + ([vys["rendery"]["frames_dst"]] + vys["rendery"]["nove_soubory"] if vys["rendery"] else []))
        print("ZAPSANO. GLB ke commitu (pod DEPLOY_LOCK, explicitni cesta):", vys["glb_cesta"])
        print("Dale: kanonicke obrazky a nahled -> jako www-data: api/venv/bin/python3 -c 'import app, turntable; turntable.regenerate_canonical(%d)'" % vys["id"])
        return 0
    except Chyba as e:
        conn.rollback()
        print("ZASTAVENO, nic se nezapsalo:", e)
        return 2
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
