"""Přehled/pipeline všech backendových modulů systému (Robert přes
bot3, 2026-08-26) - přímý vzor: stejná funkce postavená o pár hodin
dřív pro sesterský projekt /opt/toscanaccio (api/system_pipeline.py
tam, commit af9b964) - STEJNÝ vizuální/koncepční styl (stavové
pilulky + karty/řetězce), jen s registrem přizpůsobeným modulům
Konfigurátoru (~30 modulů importovaných na konci api/app.py, ne
zvlášť v _boot.py jako Toscanaccio).

Moduly, které na sebe reálně navazují (výstup jednoho je vstup
druhého - podle skutečných importů/komentářů u `import X` v api/app.py,
ne vymyšlené), tvoří PIPELINE_GROUPS níže - zbytek jsou samostatné
karty (STANDALONE_MODULES). Zdůvodnění KAŽDÉ pipeline:

  - katalog→objednávkový tok: gallery_items (fotogalerie u produktu,
    api/app.py komentář "products MUSI byt az po gallery_items") ->
    products (katalog+sklad) -> cart -> orders (checkout z košíku) ->
    documents (proforma/faktura při objednávce) -> emails (doklady/
    potvrzení se posílají e-mailem)
  - poptávky→CRM→nabídky: inquiries (veřejný formulář "Poptávám stůl"
    zapisuje PŘÍMO do crm_leads se source='web', viz inquiries.py
    komentář "zrcadli crm.find_or_create_lead()") -> crm (poptávky/
    leady) -> quotes ("crm.py na nej primo vola", nabídka se tvoří z
    konkrétního leadu)
  - render pipeline: hdri (environment mapy, soubory) ->
    rendering_settings (výběr aktivní HDRI/PBR složky ze Sdíleného
    disku pro nabídky) -> blender_render (server-side render podle
    zvolených nastavení) -> render_worker (vzdálený GPU worker, který
    render skutečně provede - čte frontu z blender_render.RENDER_OUT_DIR)
  - import noh z FBX: leg_fbx_import (hromadný import + rozklad na
    profily) -> dimension_match_fbx (rozklad/párování podle rozměru -
    navazující přístup ke stejnému typu dat)
  - Řemeslo: JEDNOMODULOVÁ skupina (ne standalone karta) - Robert
    výslovně chtěl "viditelné/samostatné místo, ať je jasně vidět jako
    svoje odlišná oblast, ne schovaný mezi ostatními" (srovnávač cen
    materiálu, remeslo.py/REMESLO_KONCEPT.md - úplně jiná doména než
    zbytek e-shopu).

Zvažované, ale ZÁMĚRNĚ NErozkreslené jako pipeline (jen kódové sdílení
helperů, ne skutečný datový tok - viz komentáře u importů v api/app.py
"pouziva helpery z..."): drive/incoming_documents/scene_offers -
ponechány jako samostatné karty s poznámkou v popisu, kam reálně
navazují, ať je vidět, že to bylo zváženo, ne přehlédnuto.

Endpoint (GET /api/admin/system-pipeline) prochází MODULE_REGISTRY,
každý modul zvlášť v try/except (pád jednoho nikdy nesundá zbytek).
"""
import os
import json
from datetime import datetime

from flask import jsonify

from app import app, get_conn, require_permission

KATALOG_GLB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "webapp", "katalog")
HDRI_DIR = os.path.join(KATALOG_GLB_DIR, "hdri")
PRIVATE_FILES_DIR = os.environ.get("PRIVATE_FILES_DIR", "/opt/konfigurator/private-files")
RENDER_OUT_DIR = os.path.join(PRIVATE_FILES_DIR, "blender-renders")
WORKER_HEARTBEAT_PATH = os.path.join(RENDER_OUT_DIR, ".worker_heartbeat.json")


def _iso(v):
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.isoformat()
    return str(v)


def _check_table(cur, table, ts_columns=("updated_at", "created_at")):
    """`table` je vzdy natvrdo zapsana konstanta z MODULE_REGISTRY
    nize, nikdy vstup od uzivatele - f-string interpolace jmena
    tabulky je tu bezpecna (zadne SQL injection riziko)."""
    cur.execute(f"SELECT COUNT(*) AS c FROM {table}")
    count = cur.fetchone()["c"]
    last_activity = None
    for col in ts_columns:
        try:
            cur.execute(f"SELECT MAX({col}) AS m FROM {table}")
            m = cur.fetchone()["m"]
            if m:
                last_activity = _iso(m)
                break
        except Exception:
            continue
    return {"status": "ok", "metric": f"{count} záznamů", "last_activity": last_activity}


def _check_aggregate_tables(cur, tables):
    for t in tables:
        cur.execute(f"SELECT 1 FROM {t} LIMIT 1")
    return {"status": "ok", "metric": f"agreguje {len(tables)} tabulek jiných modulů", "last_activity": None}


def _check_files(dir_path, unit_label):
    if not os.path.isdir(dir_path):
        return {"status": "unknown", "metric": "adresář zatím neexistuje (nic nebylo nahráno)", "last_activity": None}
    files = [os.path.join(dir_path, n) for n in os.listdir(dir_path) if os.path.isfile(os.path.join(dir_path, n))]
    if not files:
        return {"status": "ok", "metric": f"0 {unit_label}", "last_activity": None}
    newest = max(files, key=os.path.getmtime)
    return {
        "status": "ok",
        "metric": f"{len(files)} {unit_label}",
        "last_activity": datetime.fromtimestamp(os.path.getmtime(newest)).isoformat(),
    }


def _check_render_jobs():
    """blender_render - kazdy render job pise <job>.status.json do
    RENDER_OUT_DIR (viz blender_render.py) - pocet takovych souboru +
    mtime nejnovejsiho je zivy obraz "kolik renderu, kdy naposledy"."""
    if not os.path.isdir(RENDER_OUT_DIR):
        return {"status": "unknown", "metric": "adresář zatím neexistuje (žádný render neproběhl)", "last_activity": None}
    jobs = [f for f in os.listdir(RENDER_OUT_DIR) if f.endswith(".status.json")]
    if not jobs:
        return {"status": "ok", "metric": "0 renderů zatím", "last_activity": None}
    newest = max((os.path.join(RENDER_OUT_DIR, f) for f in jobs), key=os.path.getmtime)
    return {"status": "ok", "metric": f"{len(jobs)} render jobů", "last_activity": datetime.fromtimestamp(os.path.getmtime(newest)).isoformat()}


def _check_render_worker():
    """render_worker.py sam nema DB tabulku - vzdaleny GPU worker
    (Robertuv notebook) posila heartbeat soubor (jmeno+GPU+timestamp),
    viz render_worker.py _HEARTBEAT_PATH. Stary heartbeat (>10 min) =
    "unknown" (worker pravdepodobne offline), ne "error" - je to
    normalni stav, kdyz worker zrovna nebezi."""
    if not os.path.exists(WORKER_HEARTBEAT_PATH):
        return {"status": "unknown", "metric": "worker se zatím nikdy nepřihlásil", "last_activity": None}
    with open(WORKER_HEARTBEAT_PATH, encoding="utf-8") as f:
        data = json.load(f)
    ts = data.get("ts")
    age_min = (datetime.now().timestamp() - ts) / 60 if ts else None
    online = age_min is not None and age_min < 10
    return {
        "status": "ok" if online else "unknown",
        "metric": f"{data.get('name', '?')} ({data.get('gpu', '?')}) - {'online' if online else 'offline'}",
        "last_activity": datetime.fromtimestamp(ts).isoformat() if ts else None,
    }


def _check_inquiries(cur):
    """inquiries.py nema vlastni tabulku - kazda verejna poptavka se
    zapisuje rovnou do crm_leads (source='web', viz inquiries.py
    komentar "zrcadli crm.find_or_create_lead()... se source='web'
    odliseni"). Vlastni metrika = jen podmnozina se source='web', ne
    cely crm_leads (ten uz je metrikou modulu crm)."""
    cur.execute("SELECT COUNT(*) AS c FROM crm_leads WHERE source='web'")
    count = cur.fetchone()["c"]
    cur.execute("SELECT MAX(created_at) AS m FROM crm_leads WHERE source='web'")
    m = cur.fetchone()["m"]
    return {"status": "ok", "metric": f"{count} poptávek", "last_activity": _iso(m)}


def _check_rendering_settings(cur):
    cur.execute(
        "SELECT setting_key, setting_value FROM app_settings WHERE setting_key IN "
        "('rendering_hdri_folder_id', 'rendering_pbr_folder_id')"
    )
    rows = {r["setting_key"]: r["setting_value"] for r in cur.fetchall()}
    hdri_set = bool(rows.get("rendering_hdri_folder_id"))
    pbr_set = bool(rows.get("rendering_pbr_folder_id"))
    parts = []
    if hdri_set:
        parts.append("HDRI složka nastavena")
    if pbr_set:
        parts.append("PBR složka nastavena")
    return {"status": "ok", "metric": ", ".join(parts) if parts else "žádná složka zatím nenastavena", "last_activity": None}


# _check_remeslo_module() odstraněno (bot3, 2026-09-07, plná separace
# Řemesla - viz AGENTS_LOG.md) - Řemeslo je teď samostatný projekt
# /opt/remeslo s vlastním system-pipeline přehledem, tahle dlaždice
# tu duplikovala cizí monitoring přes zbytkové spojení na Forpsi.


MODULE_REGISTRY = {
    "customers": ("Zákazníci", "Evidence zákazníků (fakturační profil).",
                  lambda cur: _check_table(cur, "shop_customers")),
    "documents": ("Doklady", "Zálohová faktura, VDD, faktura, dodací list.",
                  lambda cur: _check_table(cur, "shop_documents")),
    "purchase_orders": ("Nákupní objednávky", "Nákupní objednávky u dodavatelů (Dogus aj.) - návazně na sklad v modulu Produkty.",
                         lambda cur: _check_table(cur, "shop_purchase_orders")),
    "emails": ("E-maily odchozí", "Historie e-mailů (musí běžet až po Dokladech).",
               lambda cur: _check_table(cur, "shop_emails")),
    "system_emails": ("Systémové e-maily", "Fronta systémových e-mailů (ověření registrace apod.) čekajících na schválení.",
                       lambda cur: _check_table(cur, "system_emails")),
    "gallery": ("Fotogalerie realizací", "Fotogalerie realizací.",
                lambda cur: _check_table(cur, "shop_gallery_images")),
    "gallery_items": ("Fotogalerie (polymorfní)", "Fotogalerie připojitelná ke kategorii nebo produktu.",
                       lambda cur: _check_table(cur, "content_gallery_items")),
    "products": ("Produkty", "Katalog e-shopu + skladové pohyby.",
                 lambda cur: _check_table(cur, "shop_products")),
    "orders": ("Objednávky", "Checkout nad katalogem shop_products.",
               lambda cur: _check_table(cur, "shop_orders")),
    "cart": ("Košík", "Persistentní košík zákazníka.",
             lambda cur: _check_table(cur, "shop_cart_items", ("added_at",))),
    "support": ("E-maily příchozí / podpora", "Živý chat podpory + příchozí e-maily.",
                lambda cur: _check_table(cur, "shop_support_conversations")),
    "cutting": ("Řezné plány (demo)", "Náhled řezných plánů pro přířezy profilů.",
                lambda cur: _check_table(cur, "shop_cutting_plan_units")),
    "crm": ("CRM / poptávky", "Evidence poptávek a leadů.",
            lambda cur: _check_table(cur, "crm_leads")),
    "quotes": ("Nabídky", "Obchodní cenové nabídky (tvoří se z CRM leadů).",
               lambda cur: _check_table(cur, "crm_quotes")),
    "drive": ("Sdílený disk", "Náhrada sdílených složek Google Drive - helpery znovupoužité v Nabídkách/Přijatých dokladech/Nabídce ze scény.",
              lambda cur: _check_table(cur, "shared_drive_files")),
    "incoming_documents": ("Přijaté doklady", "Schvalovací fronta přijatých dokladů/faktur z e-mailu (používá helpery z Nabídek/Disku).",
                            lambda cur: _check_table(cur, "incoming_documents")),
    "approvals": ("Schvalování", "Agregovaný přehled \"Ke schválení\" pro dashboard - nemá vlastní data.",
                  lambda cur: _check_aggregate_tables(cur, ["shop_reorder_items", "shop_purchase_orders", "shop_orders", "shop_documents", "incoming_documents", "crm_quotes"])),
    "scene_offers": ("Nabídka ze scény", "Tlačítko \"Nabídka\" v 3D scéně - používá helpery z Dokladů/Nabídek/Disku.",
                      lambda cur: _check_table(cur, "scene_offers")),
    "fleet": ("Kniha jízd", "Evidence jízd vozového parku.",
              lambda cur: _check_table(cur, "fleet_trips")),
    "leg_fbx_import": ("Import noh z FBX", "Hromadný import FBX noh s rozkladem na profily.",
                        lambda cur: _check_table(cur, "custom_shape_categories")),
    "dimension_match_fbx": ("Rozměrové párování FBX", "Rozklad FBX na profily podle rozměru - zapisuje do stejné tabulky vlastních tvarů jako Import noh.",
                             lambda cur: _check_table(cur, "custom_shapes")),
    "hdri": ("HDRI mapy", "Správa HDRI environmentálních map pro 3D scénu - souborový storage, ne DB.",
             lambda cur: _check_files(HDRI_DIR, "HDRI souborů")),
    "rendering_settings": ("Nastavení renderu", "Výběr aktivní HDRI/PBR složky ze Sdíleného disku pro nabídky - 2 klíče v app_settings, žádná vlastní tabulka.",
                            _check_rendering_settings),
    "blender_render": ("Server-side render", "Render sestavy Blenderem/Cycles - souborová fronta jobů (RENDER_OUT_DIR), ne DB.",
                        lambda cur: _check_render_jobs()),
    "render_worker": ("GPU render worker", "Vzdálený GPU worker (Robertův notebook) - stav podle heartbeat souboru, ne DB.",
                       lambda cur: _check_render_worker()),
    "inquiries": ("Veřejná poptávka \"Poptávám stůl\"", "Veřejný formulář - zapisuje rovnou do CRM leadů (source='web'), přílohy přes helper z Nabídek.",
                  _check_inquiries),
    "qa_audit": ("QA panel", "Kontrola kvality - živé odchylky na dashboardu.",
                 lambda cur: _check_table(cur, "qa_reported_tasks")),
    "bank_statements": ("Bankovní výpisy (FIO)", "Párování plateb - při shodě VS automaticky vystaví VDD v modulu Doklady (jen u platby předem).",
                         lambda cur: _check_table(cur, "bank_transactions")),
    "tracking": ("Anonymní tracking", "Anonymní geo/page-view tracking návštěvníků.",
                 # OPRAVA (bot10, 2026-08-26) - skutecny sloupec je "den",
                 # ne "day" (viz tracking.py INSERT do page_views_daily) -
                 # spatny nazev delal last_activity vzdy None, i kdyz modul
                 # zive sbira data (_check_table chybu tise polykala).
                 lambda cur: _check_table(cur, "page_views_daily", ("den",))),
}

# Skutecne funkcni/datove navaznosti (viz modulovy docstring vys pro
# zduvodneni KAZDE z nich).
PIPELINE_GROUPS = [
    ("Katalog → objednávkový tok", ["gallery_items", "products", "cart", "orders", "documents", "emails"]),
    ("Poptávky → CRM → nabídky", ["inquiries", "crm", "quotes"]),
    ("Render (nabídky ve scéně)", ["hdri", "rendering_settings", "blender_render", "render_worker"]),
    ("Import noh z FBX", ["leg_fbx_import", "dimension_match_fbx"]),
    # Jednomodulova skupina - Robert vyslovne chtel "viditelne/
    # samostatne misto" pro Remeslo, ne schovane mezi standalone
    # kartami (uplne jina domena nez zbytek e-shopu).
    ("Řemeslo (samostatná oblast)", ["remeslo"]),
]

_grouped_keys = {k for _, keys in PIPELINE_GROUPS for k in keys}
STANDALONE_MODULES = [k for k in MODULE_REGISTRY if k not in _grouped_keys]


def _module_status(cur, key):
    label, description, check_fn = MODULE_REGISTRY[key]
    if check_fn is None:
        return {"key": key, "label": label, "description": description, "status": "static", "metric": None, "last_activity": None}
    try:
        result = check_fn(cur)
        return {"key": key, "label": label, "description": description, **result}
    except Exception as e:
        return {"key": key, "label": label, "description": description, "status": "error", "metric": str(e), "last_activity": None}


@app.get("/api/admin/system-pipeline")
@require_permission("nastaveni", "zobrazit")
def admin_system_pipeline():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            pipelines = [
                {"label": label, "modules": [_module_status(cur, k) for k in keys]}
                for label, keys in PIPELINE_GROUPS
            ]
            standalone = [_module_status(cur, k) for k in STANDALONE_MODULES]
    finally:
        conn.close()
    all_modules = [m for p in pipelines for m in p["modules"]] + standalone
    counts = {"ok": 0, "error": 0, "static": 0, "unknown": 0}
    for m in all_modules:
        counts[m["status"]] = counts.get(m["status"], 0) + 1
    return jsonify({
        "pipelines": pipelines,
        "standalone": standalone,
        "total_modules": len(all_modules),
        "status_counts": counts,
    })
