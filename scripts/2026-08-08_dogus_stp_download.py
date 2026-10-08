"""
Stazeni STP 3D modelu z doguskalip.com.tr (dodavatel) - bot4, 2026-08-08.

Robert: "pozor budeme natahovat i 3D model, maji jej ve formatu stp.,
nekdy tam je jakoby duplicitni takze chceme natahnout vzdy jen prvni
STP soubor, nesrovnalosti opravdi admin dodatecne rucne. po stazeni stp
souborů k nám, musí být zustat u produktů archivované (vyjma profily,
profily stp se vubec stahovat nebudou zatim), ve skladove karte na
zalozce 3D modely, stp zustane, pro transformaci na glb pripravime
nejakou hromadnou akci, ale to bude dalsi orisek, proto do 3D sceny po
importu nesmi zatim zadne nove polozky naskocit".

Prihlaseni: dogus CAD soubory jsou za loginem (viz "Giriş için
tıklayınız" prompt bez prihlaseni). Login = ASP.NET WebForms postback
(__EVENTTARGET=ctl00$ContentPlaceHolder1$lnkLogin) na /giris-yap,
credentials v api/.env (DOGUS_LOGIN_EMAIL/DOGUS_LOGIN_PASSWORD, mimo
git). Po uspesnem loginu se objevi cookie _famname (napr. "Czech
Republic Dealer") a skutecny odkaz na soubor
(/Stuff/GetFile.ashx?pID=<produkt>&v=<verze>, Content-Type:
application/step) misto login-promptu.

Cilove produkty: shop_products.dogus_matched_at IS NOT NULL (jiz
sparovano se SKU, viz 2026-08-08_dogus_pairing_crawl.py) AND
cfg_dily_id IS NULL (= NENI profil - profily maji cfg_dily_id
nastaveny, protoze jsou napojene na 3D scenu, presne rozliseni jiz
pouzivane jinde v kodu, viz "Rozmery pro dopravu" v admin.html) AND
fbx_original_name IS NULL (nechceme prepsat existujici rucni upload -
"nesrovnalosti opravi admin dodatecne rucne" znamena ze admin muze mit
uz neco nahrano rucne, to se NESMI prepsat).

DULEZITE - stejny mechanismus jako rucni upload
(shop_products_fbx_upload v api/app.py), ale BEZ volani
convert_uploaded_model_to_glb() a BEZE ZMENY glb_file/visible_in_scene.
Soubor se ulozi do existujiciho PRODUCT_FBX_UPLOAD_DIR
(webapp/content-files/product_fbx/<id>.step), UPDATE jen
fbx_original_name+fbx_uploaded_at. Skladova karta (zalozka "3D model")
pak automaticky ukaze "⚠ nahráno, zatím se nezobrazuje ve 3D scéně" -
zadna zmena UI kodu potreba.

Pouziti (test na par produktech):
    api/venv/bin/python3 scripts/2026-08-08_dogus_stp_download.py --limit 5

Plny beh:
    api/venv/bin/python3 scripts/2026-08-08_dogus_stp_download.py --apply
"""
import argparse
import http.cookiejar
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

sys.path.insert(0, "/opt/konfigurator/api")

BASE = "https://en.doguskalip.com.tr"
UA = "Mozilla/5.0 (compatible; LogimanKonfiguratorPairingSync/1.0; +https://logiman.cz)"
REQUEST_DELAY_S = 0.4

UPLOAD_DIR = "/opt/konfigurator/webapp/content-files"
PRODUCT_FBX_UPLOAD_DIR = os.path.join(UPLOAD_DIR, "product_fbx")

VIEWSTATE_RE = re.compile(r'id="__VIEWSTATE" value="([^"]*)"')
VIEWSTATEGEN_RE = re.compile(r'id="__VIEWSTATEGENERATOR" value="([^"]*)"')
# Prvni CAD soubor na strance (bez ohledu na variantu/radek) - viz
# rptCADNew repeater, hdnNames_<idx> tesne pred href odkazu na soubor.
# Amp v href je v realne strance syrovy "&", ale HTML by ho mel
# spravne kodovat jako "&amp;" - akceptujeme oboji.
CAD_ENTRY_RE = re.compile(
    r'hdnNames_(\d+)"\s+value="([^"]*)"[\s\S]{0,2000}?href="(/Stuff/GetFile\.ashx\?pID=\d+&(?:amp;)?v=\d+)"'
)


def load_env():
    env = {}
    for line in open("/opt/konfigurator/api/.env"):
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k] = v
    return env


def make_session(email, password):
    """Prihlasi se na dogus (ASP.NET postback), vraci opener s cookies."""
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

    req = urllib.request.Request(f"{BASE}/giris-yap", headers={"User-Agent": UA})
    html = opener.open(req, timeout=20).read().decode("utf-8", errors="ignore")
    viewstate = VIEWSTATE_RE.search(html).group(1)
    viewstategen = VIEWSTATEGEN_RE.search(html).group(1)

    form = {
        "__EVENTTARGET": "ctl00$ContentPlaceHolder1$lnkLogin",
        "__EVENTARGUMENT": "",
        "__LASTFOCUS": "",
        "__VIEWSTATE": viewstate,
        "__VIEWSTATEGENERATOR": viewstategen,
        "ctl00$ContentPlaceHolder1$txtEposta": email,
        "ctl00$ContentPlaceHolder1$txtPass": password,
    }
    data = urllib.parse.urlencode(form).encode()
    req2 = urllib.request.Request(f"{BASE}/giris-yap", data=data, headers={
        "User-Agent": UA, "Content-Type": "application/x-www-form-urlencoded",
        "Referer": f"{BASE}/giris-yap",
    })
    opener.open(req2, timeout=20).read()
    time.sleep(REQUEST_DELAY_S)

    if not any(c.name == "_famname" for c in cj):
        raise RuntimeError("Přihlášení na doguskalip se nezdařilo (chybí cookie _famname).")
    return opener


def fetch(opener, url):
    # dogus_url v DB muze obsahovat ne-ASCII znaky ve slugu ("45°", "ø28"
    # - viz oprava 2026-08-10 v 2026-08-08_dogus_pairing_crawl.py, ktera
    # tyhle produkty poprve zacala parovat) - http.client vyzaduje ciste
    # ASCII request-line, jinak UnicodeEncodeError. Stejna oprava jako
    # tam - percent-enkodovat cestu pred requestem.
    parts = urllib.parse.urlsplit(url)
    safe_path = urllib.parse.quote(parts.path, safe="/-_.~")
    url = urllib.parse.urlunsplit((parts.scheme, parts.netloc, safe_path, parts.query, parts.fragment))
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with opener.open(req, timeout=20) as resp:
        html = resp.read().decode("utf-8", errors="ignore")
    time.sleep(REQUEST_DELAY_S)
    return html


def find_first_cad(html):
    """Vraci (name, url) prvniho CAD souboru na strance, nebo None."""
    m = CAD_ENTRY_RE.search(html)
    if not m:
        return None
    _idx, name, href = m.groups()
    return name.strip(), BASE + href.replace("&amp;", "&")


def download_file(opener, url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with opener.open(req, timeout=60) as resp:
        content_type = resp.headers.get("Content-Type", "")
        data = resp.read()
    time.sleep(REQUEST_DELAY_S)
    return data, content_type


def sanitize_filename(name):
    name = re.sub(r'[\\/:*?"<>|]', "_", name).strip()
    return name or "model"


def get_db_conn():
    env = load_env()
    import pymysql
    return pymysql.connect(
        host=env["DB_HOST"], port=int(env["DB_PORT"]), user=env["DB_USER"],
        password=env["DB_PASSWORD"], database=env["DB_NAME"],
        cursorclass=pymysql.cursors.DictCursor,
    )



# Sloupce, ktere se objevuji JEN ve spec tabulce profilu (viz
# SpecTableParser v 2026-08-08_dogus_pairing_crawl.py - profily maji
# External Dimensions/L(mm)/Ix/Iy/Wx/Wy/Area/Mass, spojovaci prvky jen
# Material/Weight). cfg_dily_id IS NULL SAMO O SOBE NESTACI jako filtr
# profilu - objevilo se, ze cast profilovych radku v shop_products
# NEMA cfg_dily_id vyplneny (napr. dosud nenapojene na 3D scenu), takze
# by se stahly i profilove STP navzdory Robertovu zadani ("profily stp
# se vubec stahovat nebudou zatim"). Prvni ostry beh 2026-08-08 stahl
# omylem 10 profilu (SKU 1.1.xx) - dohledano pres tento presny kriterium
# a rucne vraceno zpet (smazan soubor + fbx_original_name/
# fbx_uploaded_at na NULL). Odteď se kontroluje VZDY oboji.
PROFILE_SPEC_KEYS = {"Ix", "Iy", "Wx", "Wy", "External Dimensions"}


def is_profile_specs(specs_json_str):
    if not specs_json_str:
        return False
    try:
        specs = json.loads(specs_json_str)
    except (TypeError, ValueError):
        return False
    return bool(PROFILE_SPEC_KEYS & set(specs.keys()))


def candidate_products(limit=None):
    conn = get_db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                # cfg_dily_id IS NULL zustava jako rychly pre-filtr (nikdy
                # nesprávně nevyloučí skutečný spojovací prvek - jen
                # profily maji cfg_dily_id vubec kdy nastaveny), skutecne
                # rozhodujici je ale is_profile_specs() nize.
                "SELECT id, sku, dogus_url, product_specs_json FROM shop_products "
                "WHERE dogus_matched_at IS NOT NULL AND cfg_dily_id IS NULL "
                "AND fbx_original_name IS NULL AND dogus_url IS NOT NULL "
                "ORDER BY id"
            )
            rows = [r for r in cur.fetchall() if not is_profile_specs(r.get("product_specs_json"))]
            if limit:
                rows = rows[:limit]
            return rows
    finally:
        conn.close()


def save_result(product_id, original_name):
    """Presne mirror shop_products_fbx_upload() krok "uloz metadata" -
    ZADNA konverze, ZADNA zmena glb_file/visible_in_scene (viz docstring
    vyse - Robert: "do 3D sceny po importu nesmi zatim zadne nove
    polozky naskocit")."""
    conn = get_db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE shop_products SET fbx_original_name=%s, fbx_uploaded_at=NOW() WHERE id=%s",
                (original_name, product_id),
            )
        conn.commit()
    finally:
        conn.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, default=None, help="Omezit na prvnich N produktu (test).")
    ap.add_argument("--apply", action="store_true",
                     help="Skutecne stahovat a zapisovat do DB. Bez teto volby jen READ-ONLY dry-run "
                          "(vypise, co by se stahlo, nic nestahuje ani nezapisuje).")
    ap.add_argument("--out", default="/tmp/dogus_stp_report.json")
    args = ap.parse_args()

    env = load_env()
    products = candidate_products(limit=args.limit)
    print(f"Kandidatu na stazeni STP: {len(products)}", file=sys.stderr)

    if not products:
        print("Nic ke stazeni.", file=sys.stderr)
        return

    opener = make_session(env["DOGUS_LOGIN_EMAIL"], env["DOGUS_LOGIN_PASSWORD"])
    print("Přihlášení na doguskalip OK.", file=sys.stderr)

    os.makedirs(PRODUCT_FBX_UPLOAD_DIR, exist_ok=True)

    downloaded, no_cad, errors = [], [], []
    for i, p in enumerate(products, 1):
        try:
            html = fetch(opener, p["dogus_url"])
        except Exception as e:
            print(f"[{i}/{len(products)}] CHYBA fetch {p['sku']}: {e}", file=sys.stderr)
            errors.append({"id": p["id"], "sku": p["sku"], "error": str(e)})
            continue
        cad = find_first_cad(html)
        if not cad:
            no_cad.append({"id": p["id"], "sku": p["sku"]})
            print(f"[{i}/{len(products)}] {p['sku']}: žádný CAD soubor na stránce", file=sys.stderr)
            continue
        name, file_url = cad
        if not args.apply:
            print(f"[{i}/{len(products)}] (dry-run) {p['sku']}: stáhl bych „{name}“ z {file_url}", file=sys.stderr)
            downloaded.append({"id": p["id"], "sku": p["sku"], "name": name, "url": file_url})
            continue
        try:
            data, content_type = download_file(opener, file_url)
        except Exception as e:
            print(f"[{i}/{len(products)}] CHYBA download {p['sku']}: {e}", file=sys.stderr)
            errors.append({"id": p["id"], "sku": p["sku"], "error": str(e)})
            continue
        ext = ".step" if "step" in content_type.lower() else ".stp"
        dest_path = os.path.join(PRODUCT_FBX_UPLOAD_DIR, f"{p['id']}{ext}")
        with open(dest_path, "wb") as f:
            f.write(data)
        os.chown(dest_path, os.stat(PRODUCT_FBX_UPLOAD_DIR).st_uid, os.stat(PRODUCT_FBX_UPLOAD_DIR).st_gid)
        original_name = sanitize_filename(name) + ext
        save_result(p["id"], original_name)
        downloaded.append({"id": p["id"], "sku": p["sku"], "name": original_name, "size": len(data)})
        print(f"[{i}/{len(products)}] {p['sku']}: staženo „{original_name}“ ({len(data)} B)", file=sys.stderr)

    report = {
        "mode": "apply" if args.apply else "dry-run",
        "candidates": len(products),
        "downloaded": len(downloaded),
        "no_cad": len(no_cad),
        "errors": len(errors),
        "downloaded_items": downloaded,
        "no_cad_items": no_cad,
        "error_items": errors,
    }
    with open(args.out, "w") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(json.dumps({k: v for k, v in report.items() if not k.endswith("_items")}, ensure_ascii=False, indent=2))
    print(f"\nPlny report: {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
