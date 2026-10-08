"""Prehled postupu tvorby Vandr (vanDrawee) karet v adminu (bot5,
2026-09-23, zadani Robert pres bot3: "udelejme v adminu uplne stejnou
prehledovou tabulku tvorby sestav Vandr, jako ma 1. vetev").

SAMOSTATNY modul, NENI rozsireni `api/production_overview.py` (Robert
vyslovne: princip/vzhled stejny, kod oddeleny - ten cte
`product_assemblies`/`technicky_ok`/faze, ktere Vandr vetev nema/
nepouziva stejne). Sdili se jen `scripts/razitkovac.py::stav_razitek()`
(cisty utilita, ne soucast production_overview.py) - STEJNA funkce jako
pouziva nativni panel, aby "aktualni/zastarala" razitko znamenalo totez
na obou panelech.

Radek = KARTA (`shop_products.sku LIKE 'VD-<uuid>'`) + samostatne radky
pro FBX exporty, ktere jeste zadnou kartu nemaji (watcher jeste
nedobehl/zadny automat karty jeste nezalozil) - at je videt CELY
retezec od zdroje, ne jen uz-zalozene karty (stejna filozofie jako
nativni panel: "musi byt videt rozdelana prace, ne jen hotova").

Faze (bot3 navrh, mapovano na Vandr data):
  1. FBX export       - vandrawee_work.stored_models.fbx_exported_at
                         NENI NULL. CSV-importovane karty (bot7, 321 ks)
                         tudy nikdy nesly (jiny, drivejsi mechanismus) -
                         pocitaji se jako "hotovo" automaticky, karta uz
                         existuje = zdroj byl evidentne v poradku.
  2. Karta zalozena    - shop_products radek existuje.
  3. Cena a kategorie  - price_czk_placeholder I category_id vyplnene.
  4. Razitko           - shop_products.vandr_razitka_glb_otisk proti SOUCASNEMU GLB
                         (scripts/_vandr_razitka_otisk.otisk_glb; stejne rozhodnuti
                         jako render dispatch): zadna, aktualni, zastarala - stejne
                         3 stavy jako nativni panel (2026-10-06 opraveno: drive se
                         cetlo z product_assemblies, ktere Vandr karty nemaji).
  5. Rendery (2 elevace) - product_turntable_frames ma aktivni snimky u
                         OBOU elevaci (0 i 40 - VD_POZADOVANE_ELEVACE, stejne
                         jako scripts/2026-09-22_vandr_card_activate.py).
  6. Web (aktivni)     - shop_products.active=1.
"""
import json
import os
import re
import sys

from flask import jsonify, make_response

from app import app, get_conn, require_permission, staff_required, KATALOG_GLB_DIR

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import razitkovac  # noqa: E402 - sdileny s scripts/razitkovac.py, stejne "aktualni/zastarala" rozhodnuti jako nativni panel
import _vandr_razitka_otisk  # noqa: E402 - otisk GLB + pravidel razitek, STEJNE rozhodnuti jako render dispatch (scripts/2026-09-23_vandr_render_auto_dispatch.py)

try:
    import pymysql
except ImportError:  # pragma: no cover - stejny venv jako zbytek api/, ale fail-safe
    pymysql = None

VD_SKU_RE = re.compile(r"^VD-([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$", re.IGNORECASE)
VD_POZADOVANE_ELEVACE = (0, 40)
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


def _fbx_exported_uuids():
    """{uuid: fbx_exported_at_iso} pro VSECHNY stored_models s vyplnenym
    fbx_exported_at (zdroj A watcheru) - i ty, co jeste zadnou kartu
    nemaji. Chyba pripojeni (jiny projekt/DB, muze byt docasne nedostupny)
    se jen tise preskoci, at nespadne cely panel."""
    if pymysql is None:
        return {}
    env = _vandr_env()
    if not env:
        return {}
    try:
        conn = pymysql.connect(
            host=env.get("DB_HOST", "127.0.0.1"), port=int(env.get("DB_PORT", "3306")),
            user=env["DB_USERNAME"], password=env["DB_PASSWORD"],
            database=env.get("DB_VANDRAWEE_WORK_DATABASE", "vandrawee_work"),
            cursorclass=pymysql.cursors.DictCursor,
        )
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT HEX(uuid) AS uuid_hex, fbx_exported_at FROM stored_models "
                    "WHERE fbx_exported_at IS NOT NULL"
                )
                out = {}
                for r in cur.fetchall():
                    h = r["uuid_hex"].lower()
                    uuid = f"{h[0:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"
                    out[uuid] = r["fbx_exported_at"].isoformat() if r["fbx_exported_at"] else None
                return out
        finally:
            conn.close()
    except Exception:  # noqa: BLE001 - sesterska DB, nikdy nesmi shodit nas panel
        return {}


def _ma_2_elevace(cur, karta_id):
    cur.execute(
        "SELECT DISTINCT elevation_deg FROM product_turntable_frames "
        "WHERE shop_product_id=%s AND is_active=1 AND elevation_deg IN (%s,%s)",
        (karta_id, *VD_POZADOVANE_ELEVACE),
    )
    return {r["elevation_deg"] for r in cur.fetchall()}


_OTISK_CACHE = {}          # (cesta, mtime_ns, velikost) -> otisk; GLB se nehashuje pri kazdem nacteni panelu (stovky karet, kazda nekolik MB)


def _otisk_glb_cache(cesta):
    st = os.stat(cesta)
    klic = (cesta, st.st_mtime_ns, st.st_size)
    if klic not in _OTISK_CACHE:
        if len(_OTISK_CACHE) > 2000:
            _OTISK_CACHE.clear()
        _OTISK_CACHE[klic] = _vandr_razitka_otisk.otisk_glb(cesta)
    return _OTISK_CACHE[klic]


def _razitko_stav(cur, karta_id):
    """Stav razitek Vandr karty: "zadna" | "aktualni" | "zastarala". Vandr karty NEMAJI `product_assemblies` (to je nativni vetev) - razitka jsou na karte samotne:
    `shop_products.vandr_razitka_glb_otisk` (otisk GLB + pravidel razitek v okamziku spocitani; NULL = razitka se jeste nepocitala) a aktualni je, kdyz otisk sedi na SOUCASNY
    GLB soubor (stejne rozhodnuti jako `kandidati()` v render dispatchi). Drive se cetlo z product_assemblies a vracelo VZDY "zadna" (panel psal u kazde karty "Ceka na razitko",
    i kdyz ho karta davno mela - nalez bot8 2026-10-06)."""
    cur.execute("SELECT glb_file, vandr_razitka_glb_otisk FROM shop_products WHERE id=%s", (karta_id,))
    row = cur.fetchone()
    if not row or not row["vandr_razitka_glb_otisk"] or not row["glb_file"]:
        return "zadna"
    cesta = os.path.join(KATALOG_GLB_DIR, row["glb_file"])
    try:
        return "aktualni" if _otisk_glb_cache(cesta) == row["vandr_razitka_glb_otisk"] else "zastarala"
    except OSError:                     # GLB soubor chybi na disku: razitka nelze overit -> zastarala (potreba znovu), ne "zadna"
        return "zastarala"


def _dalsi_krok(k):
    if not k["fbx_export"]:
        return "Čeká na FBX export z vandrawee adminu."
    if not k["karta"]:
        return "Čeká na watcher (založení karty) - má běžet automaticky do 15 min."
    if not (k["cena"] and k["kategorie"]):
        chybi = []
        if not k["cena"]:
            chybi.append("cenu")
        if not k["kategorie"]:
            chybi.append("kategorii")
        return f"Doplnit v adminu: {', '.join(chybi)}."
    if not k["glb"]:
        return "Čeká na FBX→GLB konverzi (bot10)."
    if k["razitko"] != "aktualni":
        return "Čeká na razítko (bot4)." if k["razitko"] == "zadna" else "Razítko zastaralé, potřeba přerazítkovat."
    if len(k["elevace"]) < 2:
        chybejici = sorted(set(VD_POZADOVANE_ELEVACE) - k["elevace"])
        return f"Čeká na render (chybí elevace: {', '.join(str(e) + '°' for e in chybejici)})."
    if not k["web"]:
        return "Vše hotovo, čeká na aktivaci (automat běží do 15 min)."
    return "Hotovo, live na webu."


@app.get("/api/admin/vandr-vyroba/prehled")
@require_permission("dash_vandr_vyroba", "zobrazit")
def vandr_vyroba_prehled():
    fbx_map = _fbx_exported_uuids()

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT sp.id, sp.sku, sp.name, sp.slug, sp.active, sp.price_czk_placeholder, "
                "sp.category_id, sp.activated_at, sp.glb_file, "
                # WORKFLOW.md pravidlo 51 (bot10 2026-09-24): stitek umisteni v aute
                # (RL/RP/RK...), stejny vzor jako product_assemblies (api/product_
                # assemblies.py, commit eb0d7650) - LEFT JOIN, NULL kdyz neurceno.
                "ru.kod AS umisteni_kod, ru.nazev AS umisteni_nazev "
                "FROM shop_products sp LEFT JOIN regal_umisteni ru ON ru.id = sp.umisteni_id "
                "WHERE sp.sku REGEXP %s ORDER BY sp.id DESC",
                (r"^VD-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",),
            )
            karty_rows = cur.fetchall()

            karty_by_uuid = {}
            for row in karty_rows:
                m = VD_SKU_RE.match(row["sku"])
                uuid = m.group(1).lower() if m else None
                elevace = _ma_2_elevace(cur, row["id"])
                karty_by_uuid[uuid] = {
                    "shop_product_id": row["id"], "sku": row["sku"], "name": row["name"],
                    "slug": row["slug"], "web": bool(row["active"]),
                    "cena": row["price_czk_placeholder"] is not None,
                    "cena_czk": float(row["price_czk_placeholder"]) if row["price_czk_placeholder"] is not None else None,       # bot10 2026-10-06: vyber strany spolecne nabidky (kontrola.html) ukazuje cenu karty
                    "kategorie": row["category_id"] is not None,
                    "fbx_export": (uuid in fbx_map) or True,  # karta uz existuje -> zdroj byl v poradku (CSV import i watcher)
                    "fbx_exported_at": fbx_map.get(uuid),
                    "karta": True,
                    # bot3, 2026-09-23: krok PRED razitkem - FBX->GLB
                    # konverze (bot10, ne bot4). Bez GLB nema razitkovac
                    # co spustit, takze "razitko: zadna" samo o sobe
                    # nerozlisi "ceka na GLB" od "ceka na razitko" -
                    # `glb` sloupec to v _dalsi_krok() rozliseni.
                    "glb": row["glb_file"] is not None,
                    "razitko": _razitko_stav(cur, row["id"]),
                    "elevace": elevace,
                    "umisteni_kod": row["umisteni_kod"], "umisteni_nazev": row["umisteni_nazev"],
                }

            # FBX exporty BEZ karty (watcher jeste nedobehl / neco selhalo) -
            # doplnit jako samostatne radky, at je videt cely retezec.
            for uuid, exported_at in fbx_map.items():
                if uuid in karty_by_uuid:
                    continue
                karty_by_uuid[uuid] = {
                    "shop_product_id": None, "sku": f"VD-{uuid}", "name": None, "slug": None,
                    "web": False, "cena": False, "cena_czk": None, "kategorie": False,
                    "fbx_export": True, "fbx_exported_at": exported_at,
                    "karta": False, "glb": False, "razitko": "zadna", "elevace": set(),
                    "umisteni_kod": None, "umisteni_nazev": None,
                }
    finally:
        conn.close()

    kartas = []
    for uuid, k in karty_by_uuid.items():
        out = dict(k)
        out["uuid"] = uuid
        out["elevace"] = sorted(k["elevace"])
        out["dalsi_krok"] = _dalsi_krok(k)
        kartas.append(out)
    kartas.sort(key=lambda k: (k["shop_product_id"] is None, -(k["shop_product_id"] or 0)))

    # Rychly souhrn (kolik karet ceka na ktery krok) - u 323 radku (bot3
    # navrh, overeno zive 2026-09-23) je holy seznam bez souhrnu
    # nepouzitelny na prvni pohled. "ceka_glb"/"ceka_razitko" rozliseny
    # (bot3, 2026-09-23) - bez GLB (bot10) razitkovac (bot4) nema co
    # spustit, jsou to 2 ruzne fronty prace pro 2 ruzne boty.
    souhrn = {
        "celkem": len(kartas), "web": sum(1 for k in kartas if k["web"]),
        "ceka_glb": sum(1 for k in kartas if k["karta"] and k["cena"] and k["kategorie"] and not k["glb"]),
        "ceka_razitko": sum(1 for k in kartas if k["glb"] and k["razitko"] == "zadna"),
        "razitko_zastarala": sum(1 for k in kartas if k["razitko"] == "zastarala"),
        "cheka_render": sum(1 for k in kartas if k["razitko"] == "aktualni" and len(k["elevace"]) < 2),
        "bez_karty": sum(1 for k in kartas if not k["karta"]),
    }

    return jsonify({"kartas": kartas, "pocet": len(kartas), "souhrn": souhrn})


# ---------------------------------------------------------------------
# OCHRANA GLB SOUBORU (bot5, 2026-09-23, bot3 nalez): setupProductGallery3D
# v webapp/product.html nabizi interaktivni 3D prohlizec u KAZDEHO
# produktu s vyplnenym glb_file - u nativnich sestav se tomu predchazi
# tim, ze glb_file se NIKDY nenastavuje na kartu s napojenou sestavou
# (jen na jednotlive katalogove dily, viz overeno 2026-09-23: 0 z 12
# nativnich sestav ma glb_file, 713 katalogovych dilu ano). U Vandr
# karet ale glb_file JE cela sestava (bot10ova FBX->GLB konverze) -
# stejne "verejne jen otocka" pravidlo jako u nativnich sestav
# (project_ochrana_3d_modelu_sestav.md) se na ne muselo zapomenout
# vztahnout od zacatku.
#
# `/katalog/` je nginx staticky alias BEZ jakekoli kontroly (Flask o
# tom nevi) - presunuti souboru mimo primy dosah nestaci, dokud by
# zustaly jen v podslozce pod stejnym aliasem. RESENI je STEJNE jako
# uz existujici ochrana `car_bodies/` (viz api/cars.py::car_body_file,
# "@staff_required" + X-Accel-Redirect na `internal;` nginx location) -
# stejny, uz jednou over eny vzor, jen jina slozka/prefix.
#
# Soubory presunuty z `webapp/katalog/*.glb` (verejne) do
# `webapp/katalog/vandr/*.glb` (chranene, viz nginx `location
# /katalog/vandr/`) - `shop_products.glb_file` u Vandr karet ma proto
# ted prefix "vandr/" (zpetne doplneno primo v DB), na ktery
# `initProductViewer3D` v product.html reaguje volanim TETO chranene
# cesty misto primeho `/katalog/`.
VANDR_GLB_DIR = os.path.realpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "webapp", "katalog", "vandr")
)
VANDR_GLB_XACCEL_PREFIX = "/_vandr_glb_internal/"


@app.get("/api/vandr-glb-file/<path:fname>")
@staff_required
def vandr_glb_file(fname):
    from urllib.parse import quote

    cesta = os.path.realpath(os.path.join(VANDR_GLB_DIR, fname))
    if not cesta.startswith(VANDR_GLB_DIR + os.sep):
        return jsonify({"error": "neplatna cesta"}), 400
    if not fname.lower().endswith(".glb") or not os.path.isfile(cesta):
        return jsonify({"error": "nenalezeno"}), 404

    rel = os.path.relpath(cesta, VANDR_GLB_DIR)
    resp = make_response("")
    resp.headers["X-Accel-Redirect"] = VANDR_GLB_XACCEL_PREFIX + quote(rel)
    resp.headers["Content-Type"] = "model/gltf-binary"
    resp.headers["Cache-Control"] = "private, max-age=3600"
    return resp
