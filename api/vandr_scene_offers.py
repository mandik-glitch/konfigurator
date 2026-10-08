"""Vytvoreni online nabidky z Vandr (vanDrawee) karty (bot10, 2026-09-28,
Robert pres bot3: "integrace Vandr do online nabidky").

SAMOSTATNY modul (CLAUDE.md bod 6: vanDrawee logika a nase vlastni logika
se NESMI michat v jednom souboru) - pouziva jen DVE sdilene DB-zapisove
funkce ze scene_offers.py (create_scene_offer_row/save_offer_model_bytes)
a jeden novy artisan prikaz na vandrawee strane (vandr:offer-data).

ZMENA 2026-09-28 (Robert primo, ostre: "ty 2D nakresy nemuzes rucne
kreslit!!! jsou spatne ty se musi natahnout jinak hotove z Vandru"):
puvodni verze tohodle modulu si 2D kotovane vykresy POCITALA SAMA
(matplotlib) a 3D pohledy si SAMA RENDEROVALA (Blender/Cycles). OBOJE
PRYC. vanDrawee appka uz pri ulozeni sestavy (StoredModelApiController::
store()) sama vyrobi a ulozi kotovane obrazky (stored_model_parts.
image_2D_with_dim/image_3D_primary/image_3D_secondary,
viz VandrOfferData.php) - tenhle modul uz je jen NACITA z disku
(/opt/vandrawee/web/storage/app/public/...) a strka do nabidky.

Vandr davá JEDEN kombinovany kotovany 2D vykres na dil (ne 3 oddelene
ortogonalni pohledy jako nativni vetev scene.html) - Robert zvolil
(2026-09-28, AskUserQuestion): "upravit nabidku pro Vandr vetev na 1
vykres" - viz offer_options.vandr_single_drawing a webapp/nabidka-
online.html (drawings_vandr slide + buildDeck vetev).

ZNAMY LIMIT: pokud by nekdy mela Vandr sestava VICE nez 1 fyzicky dil
(left_part I right_part soucasne - u obou dnes existujicich karet je jen
left_part), tenhle kod zatim ukaze jen prvni nalezeny (viz _vyber_dil) -
neresi kombinaci vice vykresu do jedne nabidky. Zadny z dosavadnich
zadani to nepotrebuje, ale az bude, potreba rozsirit.

ZNAMY LIMIT 2 (watermark, Robert 2026-09-28: "pouzit hned tak jak jsou"):
obrazky z Vandru nesou viditelny "vanDrawee" watermark (diagonalni text,
u 3D i vypalene do textury podlahy) - vedome NEreseno, Robert zvolil
rychlost pred branding cistotou. Koliduje to s [[feedback_vandrawee_not_
in_czech_text]] (TEXT_FILTR #15) - kdyby se to niekdy melo resit, je to
zmena na strane Vandr exportu (watermark vypnout pri generovani), ne
neco, co da rozumne opravit post-hoc na hotovem PNG.

Overeno rucne na karte #4910 (Ford Transit L3H3 FWD,
vd_export_ford_transit_l3h3_fwd_4155e003.glb) - viz AGENTS_LOG.md.

ZMENA 2026-10-02 (bot10, rozhodnuti bot3 + Robert: 3D scena online nabidky
z Vandr karty - pohyby supliku/dvirek/boxu, kóty, Skutecny/Drateny vzhled).
Zakaznicky 3D model se nove stavi scripts/v3d/offer_model.py::
build_offer_model() (ctx z karty + Vandr komponenty/kusovniku pres
`vandr:offer-data --v3d` -> Blender build na CPU scripts/v3d/vandr_offer_build.py
-> serverova pojistka api/v3d_glb.py (sanitize + final_check) -> cache
private-files/v3d-cache/, klic = hash kodu + dat). Pravidla:
  a) Model se stavi PRED zalozenim nabidky. Selze-li 3D build nebo kontrola
     (nebo Vandr strana nema prikaz s --v3d), nabidka se zalozi DOSAVADNI
     cestou (staticky model z scripts/2026-09-28_vandr_offer_geometry.py, bez
     v3d, stejne jako dnes) a odpoved i zaznam (audit_log, akce v3d_model)
     nesou `v3d: false` + strucny duvod pro admina. 3D NIKDY nezakaze tvorbu
     nabidky. Uspech = `v3d: true`.
  b) Neviditelne forenzni znaceni (api/v3d_mark.py) se zapne JEN kdyz je
     v prostredi procesu V3D_MARK_SECRET (min. delka); bez nej se nic
     neznaci a nic se nehlasi jako stopa (`v3d_znacka: "vypnuto"`). Zadny
     zaloha-klic z FLASK_SECRET_KEY. Klic se v repu nikde neuklada.
  c) Starsi Vandr prikaz bez volby --v3d nehodi 500: opakuje se dosavadni
     volani bez ni a vznikne nabidka se statickym modelem (`v3d_duvod`:
     "Vandr příkaz bez --v3d").
  d) Casovy rozpocet: cely pozadavek max CELKOVY_LIMIT_S = 55 s (gunicorn
     --timeout 60 a nginx 60 s). Build dostane zbytek minus rezervu na
     znaceni/zapis a na staticky model (ten musi jit i po selhani 3D).
     Cache hit = zadny Blender; soubeh dvou pozadavku na stejny klic hlida
     zamek v offer_model (druhy pocka a vezme vysledek z cache).
  f) Okamzity vypinac: soubor private-files/v3d-vypnuto (viz V3D_VYPNUTO_SOUBOR).
  g) Chybejici Vandr OBRAZKY (2D kotovany vykres + 2 3D pohledy; Vandr je generuje jen z Unity klienta, u poloviny karet
     jsou prazdne) NEJSOU duvod ke 400. 3D pohledy: kdyz Vandr obrazek existuje, ma prednost (kombinace povolena), jinak nase
     snimky otocky karty (api/vandr_vykres_nahrada.vyber_snimky_otocky), jinak fotky z galerie karty, jinak stinovane pohledy z
     modelu. 2D KOTOVANY VYKRES se jen PREBIRA z Vandru, NIKDY se nevyrabi (Robert 2026-09-28 a znovu 2026-10-06 pres bot9; 
     fallback vykres_nares se u nabidek uz nepouziva): kdyz ho Vandr nema, vznikne nabidka BEZ stranky Vykresy
     (offer_options.vandr_bez_vykresu, zdroj "chybi", view_narys = zastupny 1x1 PNG); u spolecne nabidky se strana bez vykresu
     z vykresu vynecha. Odpoved ma `obrazky_zdroj` a `poznamka`.
     400 zustava jen pro: karta neexistuje (404), bez GLB, bez ceny, SKU neni VD-, GLB chybi na disku.
  e) Zakaznik dostane JEN to, co prosel v3d_glb.sanitize + final_check
     (jmena jen n/p/m, bez textur, extras jen {g} a scenes[0].extras.v3d);
     uklada se stejnou cestou jako dosud (scene_offers.save_offer_model_bytes)
     a servíruje se tokenem /api/public/offers/<token>/model. Varovani buildu
     (obsahuji unity_id dilu) jdou jen do odpovedi pro admina.
Kontrakt pro bot16/bot5: docs/KONTRAKT_VANDR_NABIDKA_ENDPOINT.md + docs/
KONTRAKT_NABIDKA_3D.md. Na Vandr strane musi byt PRIKAZ s --v3d nasazen
dřív (jinak jen v3d:false s duvodem, nikdy chyba).

ZMENA 2026-10-06 (bot10, Robert: "automatizovat proces bez zasahu rucne botem na kazdou FBX vyexportovanou sestavu"): kontrolni scena
(rezim=nabidka) uz nema cist rucne udelane soubory webapp/katalog/vandr/v3d_nahled/<karta>.glb - dostava model z
GET /api/kontrola-scena/v3d/<karta>.glb (kontrolni_scena_v3d_model: stejny build + cache + pojistka jako nabidka, jen zamestnanci).
"""
import base64
import json
import os
import re
import subprocess
import sys
import tempfile
import time

from flask import Response, abort, jsonify, request

from app import app, get_conn, require_permission, current_user, log_audit, staff_required
import scene_offers

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KATALOG_DIR = os.path.join(REPO_ROOT, "webapp", "katalog")
BLENDER_BIN = "/opt/blender-5.2/blender"
GEOMETRY_SCRIPT = os.path.join(REPO_ROOT, "scripts", "2026-09-28_vandr_offer_geometry.py")
# Uz jen geometrie+cisty GLB export, zadny render - kratsi budget stacil
# uz driv s renderem (~90-100s), bez nej by mel byt radove rychlejsi, ale
# necham rezervu pod gunicorn --timeout 60 (viz konfigurator.service).
BLENDER_TIMEOUT_S = 55

# --- Vandr zdroj karty (bot5, 2026-10-07: "je to tataz karta jen pro jine auto") ---
# Vandr data (vandr:offer-data) se berou podle uuid ze SKU karty (VD-<uuid>). KLON karty pro jine vozidlo (scripts/2026-10-07_vandr_klon_karty_jine_vozidlo.py) ma vlastni
# SKU, ale stejnou sestavu - jeho Vandr data jsou pod uuid ZDROJOVE karty. Mapovani {uuid klonu: uuid zdroje} drzi soubor private-files/vandr-klony.json (zapisuje klonovaci
# skript; bez DDL, bez nasazeni kodu pri dalsim klonu). Chybi-li soubor / klic, plati uuid ze SKU (dosavadni chovani vsech ostatnich karet).
VANDR_KLONY_SOUBOR = os.path.join(scene_offers.PRIVATE_FILES_DIR, "vandr-klony.json")
_klony_cache = {"mtime": None, "data": {}}


def _vandr_klony():
    try:
        mtime = os.stat(VANDR_KLONY_SOUBOR).st_mtime_ns
    except OSError:
        return {}
    if _klony_cache["mtime"] != mtime:
        try:
            with open(VANDR_KLONY_SOUBOR, encoding="utf-8") as f:
                data = json.load(f)
            _klony_cache["data"] = {str(k).lower(): str(v).lower() for k, v in data.items()} if isinstance(data, dict) else {}
        except (OSError, ValueError):
            app.logger.exception("vandr-klony.json se nepodarilo nacist - pouziji se uuid ze SKU")
            _klony_cache["data"] = {}
        _klony_cache["mtime"] = mtime
    return _klony_cache["data"]


def _vandr_uuid_karty(sku):
    """uuid, pod kterym ma Vandr data karty: zdroj klonu, jinak uuid ze SKU (VD-<uuid>)."""
    uuid = (sku or "")[3:]
    return _vandr_klony().get(uuid.lower(), uuid)


# --- 3D model nabidky (2026-10-02) ---
V3D_SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts", "v3d")
V3D_CACHE_DIR = os.path.join(scene_offers.PRIVATE_FILES_DIR, "v3d-cache")
# Celkovy rozpocet pozadavku pod gunicorn --timeout 60 a nginx proxy_read_timeout
# 60 s (konfigurator.service, vhosty): nic z toho, co nasleduje, ho nesmi prekrocit.
CELKOVY_LIMIT_S = 55
# po buildu: druhy pruchod pojistky, znaceni (zmereno 3-4 s), zapis nabidky a modelu
REZERVA_PO_BUILDU_S = 8
# kdyz 3D selze, musi zbyt cas na dosavadni staticky model (Blender, zmereno ~12 s)
REZERVA_STATICKY_MODEL_S = 20
# nejmensi rozumny cas pro dosavadni staticky model, kdyz uz je rozpocet vycerpany
MIN_STATICKY_TIMEOUT_S = 10
MARK_ENV = "V3D_MARK_SECRET"
# Okamzity vypinac 3D bez nasazeni kodu a bez restartu: existuje-li tenhle soubor, nabidky vznikaji
# dosavadni cestou (v3d:false) - `touch private-files/v3d-vypnuto` / `rm` ho vrati. Jen existence souboru.
V3D_VYPNUTO_SOUBOR = os.path.join(scene_offers.PRIVATE_FILES_DIR, "v3d-vypnuto")

# Soubory karet (snimky otocky, fotky galerie) pod webapp/content-files - jen CTENI (nahradni obrazky nabidky)
CONTENT_FILES_DIR = os.path.join(REPO_ROOT, "webapp", "content-files")

VANDRAWEE_WEB_DIR = "/opt/vandrawee/web"
VANDRAWEE_STORAGE_DIR = "/opt/vandrawee/web/storage/app/public"


def _png_data_uri(raw):
    return "data:image/png;base64," + base64.b64encode(raw).decode("ascii")


# sloupec view_narys je NOT NULL; nabidka bez Vandr vykresu (offer_options.vandr_bez_vykresu - stranka Vykresy se nezobrazuje) tam dostane 1x1 pruhledny PNG
_PRAZDNY_PNG = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="


def _read_vandr_image(relative_path):
    """relative_path = presne hodnota sloupce stored_model_parts.image_*
    (napr. "images/xxx_2d_left_dim.png"), stejna cesta, kterou Laravel
    servíruje verejne pod /storage/<relative_path> - fyzicky na disku
    (stejny VPS, zadna sit/auth potreba) je to primo pod timhle korenem."""
    with open(os.path.join(VANDRAWEE_STORAGE_DIR, relative_path), "rb") as f:
        return f.read()


def _clean_subprocess_env():
    """DULEZITE (skutecny bug nalezeny a opraveny 2026-09-28, bot10):
    subprocess.run() bez `env=` DEDI CELE prostredi tohohle procesu,
    vcetne DB_HOST/DB_PASSWORD z api/.env (EnvironmentFile= v
    konfigurator.service). Laravel cte STEJNA jmena (DB_HOST/DB_PASSWORD)
    ze sveho vlastniho .env, ale process env MA PREDNOST pred .env
    souborem - konfiguratorovo DB_HOST+DB_PASSWORD tak potichu PREPSALY
    vandrawee vlastni hodnoty, Laravel se pripojoval spatnou kombinaci
    (vandrawee DB_USERNAME/DB_DATABASE + konfiguratoruv DB_HOST/PASSWORD)
    a s APP_DEBUG=true vypsal na stdout misto JSON syrovy chybovy dump
    (vc. binarnich bajtu z SQL parametru) - `subprocess.run(text=True)`
    pak spadl na UnicodeDecodeError misto citeho JSONDecodeError, takze
    to na prvni pohled vypadalo jako encoding bug, ne credential leak.
    Kazde volani ciziho procesu (jina appka, jiny projekt) proto MUSI mit
    explicitni uzky env - nikdy spolehat na vychozi dedeni."""
    return {"PATH": os.environ.get("PATH", "/usr/bin:/bin")}


class _VandrBezV3D(RuntimeError):
    """Starsi verze prikazu vandr:offer-data na Vandr strane - nezna volbu --v3d."""


class _V3DNevzniklo(RuntimeError):
    """3D model nevznikl (build, kontrola, znaceni, chybejici modul...). Text je
    DUVOD PRO ADMINA (muze obsahovat jmena dilu z buildu) - nabidka se zalozi
    dosavadni cestou (staticky model) a text jde jen do odpovedi a audit_logu."""


# Symfony/Laravel: `The "--v3d" option does not exist.` (rc 1), kdyz prikaz volbu nema
_NEZNAMA_VOLBA_RE = re.compile(r"--v3d.{0,60}(does not exist|is not defined|not (a )?valid|unknown)"
                               r"|(unknown|unrecognized|unexpected).{0,40}--v3d", re.I | re.S)


def _kratce(text, n=300):
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    return text if len(text) <= n else text[: n - 1] + "…"


def _spust_artisan(argumenty, timeout_s):
    """Jediny misto, kde se spousti `php artisan vandr:offer-data` (testy ho
    nahrazuji). BEZI POD LARAVEL VLASTNIM DB PRIPOJENIM - viz
    _fetch_vandr_offer_data a _clean_subprocess_env (env=)."""
    return subprocess.run(
        ["/usr/bin/php", "artisan", "vandr:offer-data"] + list(argumenty),
        cwd=VANDRAWEE_WEB_DIR, capture_output=True, text=True, timeout=timeout_s,
        env=_clean_subprocess_env(),
    )


def _fetch_vandr_offer_data(uuid, v3d=False, timeout_s=30):
    """Zavola `php artisan vandr:offer-data <uuid> [--v3d]` (viz app/Console/
    Commands/VandrOfferData.php ve vandrawee repu) - BEZI POD LARAVEL
    VLASTNIM DB PRIPOJENIM. konfigurator_app DB user NEMA (a nema mit)
    GRANT na vandrawee_work schema - primy cross-db SELECT z konfiguratoru
    overene vraci "command denied" (bot10, 2026-09-28). Subprocess misto
    noveho DB pripojeni = zadne nove credentials nikde nepribyvaji -
    ale viz _clean_subprocess_env() proc `env=` MUSI byt explicitni.
    --v3d (2026-10-02): navic klic "v3d" (komponenty, kusovnik, pozice) pro
    ctx 3D modelu - jeden beh prikazu misto dvou; klice car_name/parts jsou
    beze zmeny. Starsi prikaz bez volby -> _VandrBezV3D (volajici zopakuje
    volani bez --v3d)."""
    proc = _spust_artisan([uuid] + (["--v3d"] if v3d else []), timeout_s)
    if proc.returncode != 0:
        vystup = proc.stdout + proc.stderr
        if v3d and _NEZNAMA_VOLBA_RE.search(vystup):
            raise _VandrBezV3D("Vandr příkaz bez --v3d")
        raise RuntimeError(("vandr:offer-data selhalo: %s" % vystup)[-1000:])
    return json.loads(proc.stdout)


def _nacti_vandr_data(uuid, t_start=None):
    """-> (vandr_data, v3d_duvod). v3d_duvod != None = data jsou bez klice v3d
    (dosavadni vystup prikazu), 3D se pak nestavi a nabidka vznikne se statickym
    modelem. Chyba i dosavadniho volani = vyjimka (volajici vrati 500 jako dosud).
    Casovy limit (TimeoutExpired) se neopakuje; druhe volani dostane nejvyse tolik
    casu, aby celkovy pozadavek (55 s) mel po nem jeste rezervu na staticky model."""
    try:
        return _fetch_vandr_offer_data(uuid, v3d=True), None
    except _VandrBezV3D as e:
        duvod = str(e)
    except subprocess.TimeoutExpired:
        raise
    except (RuntimeError, ValueError) as e:
        duvod = "Vandr příkaz s --v3d selhal: %s" % _kratce(e)
    zbyva = CELKOVY_LIMIT_S - REZERVA_STATICKY_MODEL_S - (time.time() - (t_start or time.time()))
    return _fetch_vandr_offer_data(uuid, v3d=False, timeout_s=max(5, min(30, zbyva))), duvod


def _vyber_dil(parts):
    """Prvni existujici fyzicky dil sestavy - viz ZNAMY LIMIT v modulovem
    docstringu (nereesi kombinaci vice dilu do jedne nabidky)."""
    for key in ("left_part", "right_part", "bulkhead_part"):
        if parts.get(key):
            return parts[key]
    return None


def can_create_offer(karta_row, katalog_dir=None):
    """(ok, duvod) - smi se z teto karty vytvorit online nabidka? JEDINE misto
    pravidla (endpoint nize i staff JSON produktu pro tlacitko v UI, bot16):
    SKU zacina `VD-`, `glb_file` je vyplneny a soubor existuje v katalogu,
    `price_czk_placeholder` neni NULL. Cista funkce (jen cte disk), bez DB.
    karta_row = radek shop_products (dict: sku, glb_file, price_czk_placeholder).
    duvod = ceska veta pro admina (presne tytez texty jako endpoint vraci v HTTP
    400), None kdyz ok. Poradi kontrol je zamerne stejne jako dosud."""
    if not karta_row:
        return False, "Karta neexistuje."
    if not karta_row.get("glb_file"):
        return False, "Karta ještě nemá hotový 3D model (konverze nedoběhla)."
    if karta_row.get("price_czk_placeholder") is None:
        return False, "Karta ještě nemá cenu."
    if not (karta_row.get("sku") or "").startswith("VD-"):
        return False, "SKU karty neodpovídá formátu VD-<uuid> - není to Vandr karta."
    if not os.path.isfile(os.path.join(katalog_dir or KATALOG_DIR, karta_row["glb_file"])):
        return False, "GLB soubor chybí na disku: %s" % karta_row["glb_file"]
    return True, None


def _run_blender_geometry(glb_path, geom_json_path, clean_glb_path, timeout_s=BLENDER_TIMEOUT_S):
    proc = subprocess.run(
        [BLENDER_BIN, "-b", "-P", GEOMETRY_SCRIPT, "--", glb_path, geom_json_path, clean_glb_path],
        capture_output=True, text=True, timeout=timeout_s,
        env=_clean_subprocess_env(),
    )
    if proc.returncode != 0 or "GEOM_OK" not in proc.stdout:
        raise RuntimeError(("Blender geometrie selhala: %s" % (proc.stdout + proc.stderr))[-2000:])


def _staticky_model(glb_path, t_start):
    """DOSAVADNI cesta (bez 3D): Blender geometrie + cisty GLB bez karoserie ->
    (clean_glb_bytes, geom). Chyby (TimeoutExpired/RuntimeError) vola volajici
    jako dosud (500). Blender dostane zbytek celkoveho limitu (nejvyse puvodnich
    55 s, nejmene MIN_STATICKY_TIMEOUT_S)."""
    timeout_s = int(max(MIN_STATICKY_TIMEOUT_S, min(BLENDER_TIMEOUT_S, CELKOVY_LIMIT_S + 2 - (time.time() - t_start))))
    with tempfile.TemporaryDirectory(prefix="vandr_offer_") as tmp:
        geom_json_path = os.path.join(tmp, "geom.json")
        clean_glb_path = os.path.join(tmp, "clean.glb")
        _run_blender_geometry(glb_path, geom_json_path, clean_glb_path, timeout_s)
        with open(geom_json_path, encoding="utf-8") as f:
            geom = json.load(f)
        with open(clean_glb_path, "rb") as f:
            clean_glb_bytes = f.read()
    return clean_glb_bytes, geom


def _offer_model():
    """scripts/v3d/offer_model.py - import AZ pri pouziti: chybejici nebo
    vadny modul shodi jen 3D cast (v3d:false), ne start celeho API ani tvorbu
    nabidky. offer_model/build_ctx pri importu nastavi sys.dont_write_bytecode
    (zadny __pycache__ do scripts/) - pro gunicorn proces se po importu
    vraci puvodni hodnota."""
    if V3D_SCRIPTS_DIR not in sys.path:
        sys.path.insert(0, V3D_SCRIPTS_DIR)
    puvodni = sys.dont_write_bytecode
    try:
        import offer_model
    finally:
        sys.dont_write_bytecode = puvodni
    return offer_model


def _over_zakaznicky_glb(raw):
    """Jedina brana zakaznickeho GLB: v3d_glb.sanitize (spec vlozeny v GLB,
    scenes[0].extras.v3d) + final_check vystupu + limit velikosti. Vraci
    vycisteny GLB (to, co se smi ulozit); ValueError = nesmi se ulozit. Vola se
    na vystup buildu i z cache (soubor v cache se neveri) a znovu tesne pred
    ulozenim (po znaceni)."""
    import v3d_glb
    spec = v3d_glb.embedded_spec(raw)
    if not isinstance(spec, dict):
        raise v3d_glb.V3DError("GLB nema popis v3d (scenes[0].extras.v3d)")
    out = v3d_glb.sanitize(raw, spec)
    gltf, _bin = v3d_glb.read_glb(out)
    v3d_glb.final_check(gltf)
    if len(out) > scene_offers.MAX_MODEL_BYTES:
        raise v3d_glb.V3DError("model je po kontrole prilis velky (%.1f MB, max %d MB)"
                               % (len(out) / 1048576.0, scene_offers.MAX_MODEL_BYTES // (1024 * 1024)))
    return out


def _zahod_cache(geom):
    """Model z cache (nebo prave sestaveny) neprosel kontrolou - soubor v cache je
    poskozeny nebo podvrzeny. Polozku smazat, aby ji dalsi pozadavek postavil znovu
    (jinak by 3D u teto karty zustalo vypnute az do zmeny kodu/dat). Jmeno klice se
    pred pouzitim overi (zadne cesty)."""
    klic = ((geom or {}).get("cache") or {}).get("klic")
    if not isinstance(klic, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,200}", klic) or ".." in klic:
        return
    for pripona in (".glb", ".json"):
        try:
            os.remove(os.path.join(V3D_CACHE_DIR, klic + pripona))
        except OSError:
            pass
    app.logger.warning("v3d-cache: polozka %s neprosla kontrolou a byla smazana", klic)


def _postav_v3d_model(shop_product_id, vandr_data, t_start):
    """Build (nebo cache) + kontrola zakaznickeho GLB PRED zalozenim nabidky.
    -> (offer_glb_bytes, geom). Chyba = _V3DNevzniklo(duvod pro admina).
    DB: spojeni jen na SELECTy (karta, panel materialu) a zavre se (rollback) hned
    po buildu, pred zapisem nabidky."""
    try:
        om = _offer_model()
    except Exception as e:
        app.logger.exception("scripts/v3d/offer_model.py nejde nacist")
        raise _V3DNevzniklo("modul scripts/v3d/offer_model.py nejde načíst (%s: %s)" % (type(e).__name__, _kratce(e)))
    zbyva_s = CELKOVY_LIMIT_S - REZERVA_PO_BUILDU_S - REZERVA_STATICKY_MODEL_S - (time.time() - t_start)
    conn = get_conn()
    try:
        offer_glb, geom = om.build_offer_model(
            shop_product_id, conn, V3D_CACHE_DIR, vandr_fetch=lambda _uuid: vandr_data,
            celkovy_limit_s=max(zbyva_s, 0.0))
    except om.V3DBuildError as e:
        raise _V3DNevzniklo(_kratce(e, 600))
    except Exception as e:
        app.logger.exception("Vandr nabidka z karty %s: neocekavana chyba 3D modelu", shop_product_id)
        raise _V3DNevzniklo("neočekávaná chyba 3D modelu (%s: %s)" % (type(e).__name__, _kratce(e)))
    finally:
        try:
            conn.close()
        except Exception:
            app.logger.exception("zavreni spojeni po 3D buildu selhalo")
    if not (isinstance(geom, dict) and isinstance(geom.get("overall_size"), list) and len(geom["overall_size"]) == 3
            and isinstance(geom.get("profily"), list)):
        _zahod_cache(geom)
        raise _V3DNevzniklo("geom.json z buildu/cache je neúplný (chybí overall_size nebo profily)")
    try:
        offer_glb = _over_zakaznicky_glb(offer_glb)
    except ValueError as e:
        _zahod_cache(geom)
        raise _V3DNevzniklo("3D model neprošel kontrolou: %s" % _kratce(e, 600))
    except Exception as e:
        _zahod_cache(geom)
        app.logger.exception("kontrola 3D modelu spadla")
        raise _V3DNevzniklo("kontrola 3D modelu spadla (%s: %s)" % (type(e).__name__, _kratce(e)))
    return offer_glb, geom


_znacka_vypnuto_zalogovano = False


def _znackovaci_klic():
    """-> (bytes | None, varovani | None). None = znaceni VYPNUTO: V3D_MARK_SECRET
    neni v prostredi procesu (nebo je kratky). Zadna nahradni hodnota (napr. z
    FLASK_SECRET_KEY) - bez klice se nic neznaci a nic se nehlasi jako stopa."""
    global _znacka_vypnuto_zalogovano
    hodnota = (os.environ.get(MARK_ENV) or "").strip()
    varovani = None
    klic = None
    if hodnota:
        try:
            import v3d_mark
            klic = v3d_mark.get_secret(env={MARK_ENV: hodnota})
        except ImportError:
            raise                       # klic je, ale modul znaceni nejde nacist = chyba, ne mlcky bez znacky
        except ValueError as e:
            varovani = "Neviditelné značení vypnuto: %s" % e
    if klic is None and not _znacka_vypnuto_zalogovano:
        _znacka_vypnuto_zalogovano = True
        app.logger.warning("3D nabidky: neviditelne znaceni modelu je VYPNUTO (%s)",
                           "klic V3D_MARK_SECRET je neplatny" if hodnota else "V3D_MARK_SECRET neni nastaven")
    return klic, varovani


def _oznac_model(offer_glb, offer_id):
    """-> (bytes, stav, varovani). stav "zapnuto" | "vypnuto". Se zapnutym znacenim
    nejde-li model oznacit (nebo modul chybi) = _V3DNevzniklo (nabidka pak dostane
    staticky model): znaceny model je pozadavek, nikdy se tise neulozi bez znacky."""
    try:
        klic, varovani = _znackovaci_klic()
    except ImportError as e:
        raise _V3DNevzniklo("modul značení (api/v3d_mark.py) nejde načíst: %s" % _kratce(e))
    if klic is None:
        return offer_glb, "vypnuto", varovani
    try:
        import v3d_mark
        return v3d_mark.mark(offer_glb, int(offer_id), klic), "zapnuto", None
    except ValueError as e:
        raise _V3DNevzniklo("model nejde označit číslem nabídky: %s" % _kratce(e, 600))
    except Exception as e:
        app.logger.exception("v3d_mark.mark spadlo (nabidka id=%s)", offer_id)
        raise _V3DNevzniklo("značení modelu spadlo (%s: %s)" % (type(e).__name__, _kratce(e)))


def _vykres_modul():
    """api/vandr_vykres_nahrada.py - import az pri pouziti (numpy + PIL se nacitaji jen kdyz je nahrada potreba)."""
    import vandr_vykres_nahrada
    return vandr_vykres_nahrada


def _data_uri_obrazku(raw):
    """PNG a JPEG beze zmeny, jiny format (webp...) pres PIL na JPEG; nic vetsiho nez strop scene_offers (6 MB)."""
    if raw[:8] == b"\x89PNG\r\n\x1a\n":
        mime = "png"
    elif raw[:3] == b"\xff\xd8\xff":
        mime = "jpeg"
    else:
        mime = None
    if mime is None or len(raw) > scene_offers.MAX_IMAGE_BYTES:
        import io
        from PIL import Image
        im = Image.open(io.BytesIO(raw)).convert("RGB")
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=90)
        raw, mime = buf.getvalue(), "jpeg"
        if len(raw) > scene_offers.MAX_IMAGE_BYTES:
            raise ValueError("obrazek je i po prevodu na JPEG prilis velky")
    return "data:image/%s;base64,%s" % (mime, base64.b64encode(raw).decode("ascii"))


def _soubor_content(rel):
    """cesta k souboru pod CONTENT_FILES_DIR (jen uvnitr nej) nebo None, kdyz neexistuje"""
    if not isinstance(rel, str) or not rel:
        return None
    base = os.path.realpath(CONTENT_FILES_DIR)
    cesta = os.path.realpath(os.path.join(base, rel.lstrip("/")))
    if not cesta.startswith(base + os.sep) or not os.path.isfile(cesta):
        return None
    return cesta


def _cti_soubor(cesta):
    with open(cesta, "rb") as f:
        return f.read()


def _snimky_otocky(shop_product_id, front_az):
    """-> {"a": (bajty, popis), "b": (...)} ze snimku otocky karty (product_turntable_frames), nebo None."""
    vykres = _vykres_modul()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT elevation_deg, azimuth_deg, tier_px, filename, bytes FROM product_turntable_frames "
                        "WHERE shop_product_id=%s AND is_active=1", (shop_product_id,))
            radky = cur.fetchall()
    finally:
        conn.close()
    vyber = vykres.vyber_snimky_otocky(radky, front_az, existuje=lambda f: _soubor_content(f) is not None)
    if not vyber:
        return None
    return {slot: (_cti_soubor(_soubor_content(r["filename"])),
                   "snímek otočky (elevace %d°, azimut %d°)" % (int(r["elevation_deg"]), int(r["azimuth_deg"])))
            for slot, r in vyber.items()}


def _fotky_galerie(shop_product_id, kolik):
    """prvni `kolik` existujicich fotek z galerie karty: [(bajty, popis)] (content_gallery_items verejne, pak shop_product_images)"""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT filename FROM content_gallery_items WHERE owner_type='product' AND owner_id=%s AND is_public=1 "
                        "ORDER BY sort_order, id", (shop_product_id,))
            rel = ["gallery-items/%s" % r["filename"] for r in cur.fetchall()]
            cur.execute("SELECT filename FROM shop_product_images WHERE product_id=%s ORDER BY sort_order, id", (shop_product_id,))
            rel += ["gallery/%s" % r["filename"] for r in cur.fetchall()]
    finally:
        conn.close()
    out = []
    for r in rel:
        cesta = _soubor_content(r)
        if cesta:
            out.append((_cti_soubor(cesta), "fotka z galerie karty"))
            if len(out) >= kolik:
                break
    return out


def _nahradni_3d_pohledy(shop_product_id, front_az, sloty, model_glb):
    """-> ({slot: data URI}, [popis]) pro chybejici sloty ("a" = zepredu doprava, "b" = zepredu doleva). Poradi zdroju:
    snimky otocky -> fotky galerie -> stinovany pohled z modelu."""
    vykres = _vykres_modul()
    hotovo, popisy = {}, []
    try:
        snimky = _snimky_otocky(shop_product_id, front_az)
    except Exception:
        app.logger.exception("nahradni 3D pohledy: snimky otocky karty %s nejdou nacist", shop_product_id)
        snimky = None
    if snimky:
        for slot in sloty:
            hotovo[slot] = _data_uri_obrazku(snimky[slot][0])
            popisy.append(snimky[slot][1])
    else:
        try:
            fotky = _fotky_galerie(shop_product_id, len(sloty))
        except Exception:
            app.logger.exception("nahradni 3D pohledy: galerie karty %s nejde nacist", shop_product_id)
            fotky = []
        for slot, (raw, popis) in zip(sloty, fotky):
            hotovo[slot] = _data_uri_obrazku(raw)
            popisy.append(popis)
    zbyva = [s for s in sloty if s not in hotovo]
    if zbyva:
        az0 = front_az if front_az is not None else vykres.predni_azimut_deg(model_glb)
        for slot in zbyva:
            png = vykres.pohled_z_modelu(model_glb, (az0 + (35.0 if slot == "a" else -35.0)) % 360.0, vykres.CILOVA_ELEVACE_DEG)
            hotovo[slot] = "data:image/png;base64," + base64.b64encode(png).decode("ascii")
            popisy.append("pohled z modelu")
    return hotovo, popisy


def _dopln_obrazky(shop_product_id, karta, part, model_glb):
    """Obrazky nabidky. Kotovany 2D vykres (`narys`) se JEN PREBIRA z Vandru, nikdy ho nevyrabime (Robert 2026-10-06: "Vandr 2D pohledy se nevyrabi, jen se prejimaji"):
    kdyz ho Vandr u karty nema (prazdna cesta nebo soubor mimo disk), `views` klic `narys` NEOBSAHUJE, zdroj["narys"] = "chybi" a nabidka vznikne BEZ stranky Vykresy
    (volajici nastavi offer_options.vandr_bez_vykresu a do sloupce view_narys da prazdny zastupny obrazek). 3D pohledy (view3d_a/b): Vandr, kde existuji, jinak nahrada
    (snimky otocky -> fotky galerie -> pohled z modelu) - to jsou 3D nahledy, ne 2D vykres.
    -> (views, obrazky_zdroj, poznamka | None, rozmery | None; rozmery je dnes vzdy None - nic uz se z modelu nekotuje)."""
    klice = (("narys", "image_2d_with_dim"), ("view3d_a", "image_3d_primary"), ("view3d_b", "image_3d_secondary"))
    vandr, nenalezeno = {}, []
    for klic, sloupec in klice:
        rel = (part or {}).get(sloupec)
        if not rel:
            vandr[klic] = None
            continue
        try:
            vandr[klic] = _read_vandr_image(rel)
        except OSError:
            vandr[klic] = None
            nenalezeno.append(klic)
    views, popis_casti = {}, []
    zdroj = {"narys": "vandr", "view3d": "vandr"}
    front_az = karta.get("vandr_predni_azimut_deg")
    front_az = float(front_az) if front_az is not None else None
    if vandr["narys"] is not None:
        views["narys"] = _png_data_uri(vandr["narys"])
    else:
        zdroj["narys"] = "chybi"
    sloty = [s for s, k in (("a", "view3d_a"), ("b", "view3d_b")) if vandr[k] is None]
    for s, k in (("a", "view3d_a"), ("b", "view3d_b")):
        if vandr[k] is not None:
            views[k] = _png_data_uri(vandr[k])
    if sloty:
        nahr, popisy = _nahradni_3d_pohledy(shop_product_id, front_az, sloty, model_glb)
        for s in sloty:
            views["view3d_" + s] = nahr[s]
        zdroj["view3d"] = "nahrada" if len(sloty) == 2 else "kombinace"
        popis_casti.append("3D pohledy: " + ", ".join(popisy))
    poznamka = None
    if zdroj["narys"] == "chybi":
        poznamka = "Vandr u karty nemá kótovaný 2D výkres - nabídka je bez stránky Výkresy (2D se jen přebírá z Vandru, nevyrábí se)."
        if "narys" in nenalezeno:
            poznamka += " (Výkres byl ve Vandru uveden, ale soubor chybí na disku.)"
    if popis_casti:
        poznamka = ((poznamka + " ") if poznamka else "") + "Vandr nemá všechny 3D obrázky, použity naše náhledy: " + "; ".join(popis_casti) + "."
        if [k for k in nenalezeno if k != "narys"]:
            poznamka += " (Vandr obrázek byl uveden, ale soubor chybí na disku: %s.)" % ", ".join(k for k in nenalezeno if k != "narys")
    return views, zdroj, poznamka, None


def _zaznam_v3d(user_id, offer_id, **udaje):
    """audit_log (action v3d_model): v3d true/false, verze buildu, duvod, znacka.
    Bez migrace schematu; nikdy neshodi odpoved."""
    try:
        log_audit(user_id, "v3d_model", "scene_offer", offer_id, udaje)
    except Exception:
        app.logger.exception("zapis audit_log (v3d_model) nabidky id=%s selhal", offer_id)


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------
# SPOLECNA NABIDKA z vice karet (leva + prava + prepazka) a kontrolni scena s modelem na pozadani (bot10, 2026-10-06)
# Robert: "chci aby v jedne online nabidce slo nabidnout dohromady levou stranu, i pravou stranu i prepazku" + "automatizovat proces bez zasahu rucne botem na kazdou FBX".
# Karty stran zustavaji samostatne (kazda ma svoji cenu a Vandr data); nabidka je spoji: kazda karta se postavi sama (stejny build + cache jako nabidka z jedne karty), zakaznicke
# GLB se slouci v api/v3d_merge.py (stejne souradnice vozu: leva strana x > 0, prava x < 0) a spec/pohyby se precisluji. Kontrolni scena ukaze totez pres vd:<a>+<b>+<c>.
# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------
SPOLECNA_MAX = 3
_IDS_RE = re.compile(r"\d{1,9}(?:\+\d{1,9}){0,%d}" % (SPOLECNA_MAX - 1))
_STRANY_PORADI = ("left", "right", "bulkhead")
_STRANY_NAZEV = {"left": "Levá strana", "right": "Pravá strana", "bulkhead": "Přepážka"}
_VIEW_SLOTY = ("narys", "bokorys", "pudorys")                  # sloty obrazku nabidky, do kterych jde po jednom vykresu strany (offer_options.vandr_drawings)


class _Chyba(Exception):
    """Odmitnuti pozadavku: HTTP status + cesky text pro zamestnance (u vice karet s predponou "Karta <id>: ")."""

    def __init__(self, status, text):
        super().__init__(text)
        self.status, self.text = status, text


def _chyba_json(e):
    return jsonify({"error": e.text}), e.status


def _ids_z_cesty(ids):
    """"4962+4963+4925" -> [4962, 4963, 4925]; neplatny tvar -> None (404), duplicita -> _Chyba 400."""
    if not _IDS_RE.fullmatch(ids or ""):
        return None
    out = [int(x) for x in ids.split("+")]
    if len(set(out)) != len(out):
        raise _Chyba(400, "Stejná karta je v seznamu víckrát.")
    return out


def _nacti_karty(ids, vyzaduj_cenu):
    """[karta_row] v poradi ids po kontrole (existuje, VD-, GLB na disku, u nabidky i cena). Pri chybe _Chyba; u vice karet s predponou "Karta <id>: "."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            rows = []
            for i in ids:
                cur.execute("SELECT id, name, sku, description, glb_file, price_czk_placeholder, vandr_predni_azimut_deg FROM shop_products WHERE id=%s", (i,))
                rows.append(cur.fetchone())
    finally:
        conn.close()
    pred = lambda i: "" if len(ids) == 1 else "Karta %d: " % i
    for i, r in zip(ids, rows):
        if not r:
            raise _Chyba(404, pred(i) + "Karta neexistuje.")
        if not (r.get("sku") or "").startswith("VD-"):
            raise _Chyba(400, pred(i) + "SKU karty neodpovídá formátu VD-<uuid> - není to Vandr karta.")
        if not r.get("glb_file"):
            raise _Chyba(400, pred(i) + "Karta ještě nemá hotový 3D model (konverze nedoběhla).")
        if not os.path.isfile(os.path.join(KATALOG_DIR, r["glb_file"])):
            raise _Chyba(400, pred(i) + "GLB soubor chybí na disku: %s" % r["glb_file"])
        if vyzaduj_cenu and r.get("price_czk_placeholder") is None:
            raise _Chyba(400, pred(i) + "Karta ještě nemá cenu.")
    return rows


def _nacti_data_karet(rows, t_start):
    """Vandr data (s klicem v3d) pro kazdou kartu; chyba = _Chyba 502."""
    out = []
    for r in rows:
        try:
            vandr_data, v3d_duvod = _nacti_vandr_data(_vandr_uuid_karty(r["sku"]), t_start)
        except (subprocess.TimeoutExpired, RuntimeError, ValueError) as e:
            raise _Chyba(502, "Načtení dat z Vandru selhalo: %s" % e)
        if v3d_duvod is not None:
            raise _Chyba(502, "3D model nevznikl: %s" % v3d_duvod)
        out.append(vandr_data)
    return out


def _strana_karty(data):
    """Jedina strana (left|right|bulkhead), kterou karta ve Vandr datech ma; jinak None."""
    st = [k for k in _STRANY_PORADI if ((data.get("v3d") or {}).get("strany") or {}).get(k)]
    return st[0] if len(st) == 1 else None


def _over_spolecnou(rows, datas):
    """Karty patri do jedne nabidky, kdyz jsou pro TOTEZ vozidlo a kazda ma JINOU jedinou stranu. -> strany (v poradi karet); jinak _Chyba 400."""
    jmena = {(d.get("car_name") or "").strip() for d in datas}
    if len(jmena) > 1:
        raise _Chyba(400, "Karty jsou pro různá vozidla (%s) – do společné nabídky patří jen karty téhož vozu." % ", ".join(sorted(j or "?" for j in jmena)))
    strany = []
    for r, d in zip(rows, datas):
        s = _strana_karty(d)
        if s is None:
            raise _Chyba(400, "Karta %d nemá jednu určitou stranu (levá / pravá / přepážka) – do společné nabídky patří karty jednotlivých stran, ne kombinace." % r["id"])
        strany.append(s)
    for i in range(len(strany)):
        for j in range(i + 1, len(strany)):
            if strany[i] == strany[j]:
                raise _Chyba(400, "Karty %d a %d jsou obě %s – vybírá se po jedné z každé strany." % (rows[i]["id"], rows[j]["id"], _STRANY_NAZEV[strany[i]].lower()))
    return strany


def _serad_podle_stran(rows, datas, strany):
    """Kanonicky poradi leva, prava, prepazka (front a cislovani pohybu se berou z prvniho = leveho regalu)."""
    idx = sorted(range(len(rows)), key=lambda i: _STRANY_PORADI.index(strany[i]))
    return [rows[i] for i in idx], [datas[i] for i in idx], [strany[i] for i in idx]


def _postav_spolecny_model(rows, datas, t_start):
    """Kazda karta se postavi sama (cache sdilena s nabidkou z jedne karty), pak se zakaznicka GLB slouci. -> (glb, geom, casti [(glb_i, geom_i)]); chyba = _Chyba 500."""
    casti = []
    for r, d in zip(rows, datas):
        try:
            casti.append(_postav_v3d_model(r["id"], d, t_start))
        except _V3DNevzniklo as e:
            raise _Chyba(500, "3D model nevznikl%s: %s" % ("" if len(rows) == 1 else " (karta %d)" % r["id"], e))
    if len(casti) == 1:
        return casti[0][0], casti[0][1], casti
    try:
        import v3d_merge
        # strany (left/right/bulkhead) pro motions[].g (bot10 2026-10-06); starsi v3d_merge bez parametru `strany` = odhad podle front
        import inspect
        kw = {"strany": [_strana_karty(d) for d in datas]} if "strany" in inspect.signature(v3d_merge.sluc_glb).parameters else {}
        glb, geom = v3d_merge.sluc_glb([c[0] for c in casti], [c[1] for c in casti], **kw)
    except ImportError as e:
        app.logger.exception("api/v3d_merge.py nejde nacist")
        raise _Chyba(500, "3D model nevznikl: modul slučování modelů nejde načíst (%s)" % _kratce(e))
    except ValueError as e:
        raise _Chyba(500, "3D model nevznikl: sloučení modelů stran selhalo: %s" % _kratce(e, 400))
    return glb, geom, casti


@app.get("/api/kontrola-scena/v3d/<ids>.glb")
@staff_required
def kontrolni_scena_v3d_model(ids):
    """KONTROLNI SCENA (rezim=nabidka): zakaznicky 3D model s pohyby z Vandr karty postaveny NA POZADANI (bot10, 2026-10-06;
    Robert: "automatizovat proces bez zasahu rucne botem na kazdou FBX vyexportovanou sestavu"). Stejny build + cache
    (private-files/v3d-cache, SDILENA s vytvorenim nabidky - pozdejsi nabidka z karty je pak bez Blenderu) + serverova pojistka
    (v3d_glb.sanitize + final_check) jako pri zalozeni nabidky, jen bez nabidky a bez forenzniho znaceni (odpoved jen pro
    zamestnance). Drive se model pro kontrolu delal rucne skriptem do webapp/katalog/vandr/v3d_nahled/<karta>.glb (7 karet).
    Nic se nezapisuje do DB ani do audit_logu. Cena karty se nevyzaduje (na rozdil od nabidky): kontroluje se jen model.
    `ids` = jedna karta (`4965`) NEBO vice karet stran jednoho vozu spojenych plusem (`4962+4963+4925`, max 3): ukaze se slouceny model, jaky dostane zakaznik ve
    spolecne nabidce (leva + prava + prepazka v jedne scene). Chyba = JSON {"error": cesky text pro zamestnance} (HTTP 4xx/5xx), NIKDY tichy nahradni model."""
    t_start = time.time()
    try:
        seznam = _ids_z_cesty(ids)
        if seznam is None:
            abort(404)
        rows = _nacti_karty(seznam, vyzaduj_cenu=False)
        if os.path.exists(V3D_VYPNUTO_SOUBOR):
            raise _Chyba(503, "3D model je vypnutý souborem private-files/v3d-vypnuto (smazáním souboru se zapne).")
        datas = _nacti_data_karet(rows, t_start)
        if len(rows) > 1:
            strany = _over_spolecnou(rows, datas)
            rows, datas, strany = _serad_podle_stran(rows, datas, strany)
        offer_glb, geom, casti = _postav_spolecny_model(rows, datas, t_start)
    except _Chyba as e:
        return _chyba_json(e)
    resp = Response(offer_glb, mimetype="model/gltf-binary")
    resp.headers["Cache-Control"] = "private, no-store"
    resp.headers["X-V3D-Cache"] = "hit" if all((((c[1] or {}).get("cache") or {}).get("hit")) for c in casti) else "miss"
    resp.headers["X-V3D-Warnings"] = str(sum(len((c[1] or {}).get("warnings") or []) + len((c[1] or {}).get("ctx_warnings") or []) for c in casti))
    resp.headers["X-V3D-Karty"] = "+".join(str(r["id"]) for r in rows)
    return resp


@app.post("/api/admin/vandr-vyroba/nabidka-spolecna")
@require_permission("sdileny_disk", "zobrazit")
def vandr_vyroba_vytvorit_spolecnou_nabidku():
    """SPOLECNA online nabidka z 2-3 karet Vandr stejneho vozu, kazda JINA strana (leva / prava / prepazka); telo {"karty": [id, id, (id)]}. Jedna nabidka: radek ceny za kazdou
    kartu + celkem, jedna 3D scena se vsemi stranami (pohyby vsech dilu), kotovany vykres ke kazde strane (offer_options.vandr_drawings). Odpoved 201 jako u nabidky z jedne karty +
    `karty`, `strany`. Pro rozdil od nabidky z jedne karty se BEZ 3D nezaklada (staticky model slouceneho setu neexistuje): kdyz se kterakoli karta nepostavi nebo sloucení selze,
    vrati se chyba s duvodem a nic nevznikne (kazda uspesne postavena karta zustava v cache, dalsi pokus je rychlejsi)."""
    t_start = time.time()
    user = current_user()
    body = request.get_json(silent=True) if request.is_json else None
    karty = body.get("karty") if isinstance(body, dict) else None
    if not (isinstance(karty, list) and 2 <= len(karty) <= SPOLECNA_MAX and all(type(x) is int and x > 0 for x in karty)):
        return jsonify({"error": "Tělo musí být {\"karty\": [id, id]} (2 až %d různé karty)." % SPOLECNA_MAX}), 400
    if len(set(karty)) != len(karty):
        return jsonify({"error": "Stejná karta je v seznamu víckrát."}), 400
    try:
        rows = _nacti_karty(karty, vyzaduj_cenu=True)
        if os.path.exists(V3D_VYPNUTO_SOUBOR):
            raise _Chyba(503, "3D model je vypnutý souborem private-files/v3d-vypnuto - společná nabídka se bez 3D nezakládá.")
        datas = _nacti_data_karet(rows, t_start)
        strany = _over_spolecnou(rows, datas)
        rows, datas, strany = _serad_podle_stran(rows, datas, strany)
        t_v3d = time.time()
        offer_glb, geom, casti = _postav_spolecny_model(rows, datas, t_start)
        v3d_ms = int(round((time.time() - t_v3d) * 1000))
        # --- obrazky: kazda karta svuj kotovany vykres JEN z Vandru (strana bez nej se vynecha); 3D pohledy z prvni (leve) karty
        views, zdroje, poznamky, kresby = {}, [], [], []
        for i, (st, r, d, c) in enumerate(zip(strany, rows, datas, casti)):
            try:
                v_i, zdroj_i, pozn_i, _rozm = _dopln_obrazky(r["id"], r, _vyber_dil(d.get("parts") or {}), c[0])
            except Exception as e:
                app.logger.exception("Spolecna nabidka, karta %s: obrazky nevznikly", r["id"])
                raise _Chyba(500, "Obrázky nabídky nevznikly (karta %d: %s: %s). Nabídka nevznikla." % (r["id"], type(e).__name__, _kratce(e)))
            if "narys" in v_i:                       # strana bez Vandr vykresu se z vykresu VYNECHA (nevyrabi se), sloty se prideluji jen stranam s vykresem
                slot = _VIEW_SLOTY[len(kresby)]
                views[slot] = v_i["narys"]
                kresby.append({"slot": slot, "label": _STRANY_NAZEV[st]})
            if i == 0:
                views["view3d_a"], views["view3d_b"] = v_i["view3d_a"], v_i["view3d_b"]
            zdroje.append(zdroj_i)
            if pozn_i:
                poznamky.append("%s: %s" % (_STRANY_NAZEV[st], pozn_i))
    except _Chyba as e:
        return _chyba_json(e)
    # --- radky nabidky: jedna polozka za kartu (popis produktu + umisteni + SKU), cena = soucet
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            umisteni = {}
            for r in rows:
                cur.execute("SELECT ru.nazev AS nazev FROM shop_products sp LEFT JOIN regal_umisteni ru ON ru.id = sp.umisteni_id WHERE sp.id=%s", (r["id"],))
                x = cur.fetchone()
                umisteni[r["id"]] = (x or {}).get("nazev")
    finally:
        conn.close()
    items, total = [], 0.0
    for st, r in zip(strany, rows):
        cena = float(r["price_czk_placeholder"])
        total += cena
        popis = r["description"] or r["name"]
        items.append({"name": "%s – %s (%s)" % (popis, umisteni.get(r["id"]) or _STRANY_NAZEV[st], r["sku"]), "qty": 1, "unit_price": cena, "total": cena})
    offer_options = {**scene_offers.OFFER_OPTIONS_DEFAULT, "vandr_single_drawing": True, "hidden_payment_method": "dobirka"}   # ID karet v offer_options NEjsou (verejny JSON nabidky; jsou v audit_logu `karty`)
    if kresby:
        offer_options["vandr_drawings"] = kresby
    else:                                                                       # zadna ze stran nema Vandr vykres: nabidka bez stranky Vykresy (nic se nevyrabi)
        offer_options["vandr_bez_vykresu"] = True
        views["narys"] = _PRAZDNY_PNG
    offer_id, offer_number, view_token = scene_offers.create_scene_offer_row(items, total, views, None, None, None, offer_options, user["id"])
    # --- model k nabidce po znaceni a posledni kontrole (fail closed: neprosel-li, nabidka zustane bez 3D a odpoved to rekne)
    znacka, varovani_znacky, v3d_duvod, model_bytes = "vypnuto", None, None, None
    try:
        model_bytes, znacka, varovani_znacky = _oznac_model(offer_glb, offer_id)
        model_bytes = _over_zakaznicky_glb(model_bytes)
    except Exception as e:
        v3d_duvod = e.args[0] if isinstance(e, _V3DNevzniklo) else "3D model neprošel poslední kontrolou (%s: %s)" % (type(e).__name__, _kratce(e))
        if not isinstance(e, (ValueError, _V3DNevzniklo)):
            app.logger.exception("Spolecna nabidka %s: neocekavana chyba pri koncove kontrole 3D modelu", offer_number)
        app.logger.warning("Spolecna nabidka %s: 3D model se neulozil (v3d:false): %s", offer_number, v3d_duvod)
        model_bytes = None
    if model_bytes is not None:
        model_err = scene_offers.save_offer_model_bytes(offer_id, model_bytes, user["id"] if user else None)
        if model_err:
            app.logger.warning("Spolecna nabidka %s: ulozeni 3D modelu selhalo: %s", offer_number, model_err)
            v3d_duvod = "uložení 3D modelu selhalo: %s" % _kratce(model_err)
            model_bytes = None
    v3d_ok = model_bytes is not None
    cache = (geom.get("cache") or {}) if v3d_ok else {}
    varovani = (list(geom.get("warnings") or []) + list(geom.get("ctx_warnings") or [])) if v3d_ok else []
    if varovani_znacky:
        varovani.append(varovani_znacky)
    build = cache.get("verze_buildu") if v3d_ok else None
    _zaznam_v3d(user["id"] if user else None, offer_id, v3d=v3d_ok, build=build, duvod=None if v3d_ok else _kratce(v3d_duvod, 200), znacka=znacka if v3d_ok else None,
                cache_hit=cache.get("hit") if v3d_ok else None, ms=v3d_ms, varovani=len(varovani), obrazky=zdroje, karty=[r["id"] for r in rows], strany=strany)
    return jsonify({
        "status": "ok", "offer_id": offer_id, "offer_number": offer_number, "online_url": "/nabidka-online.html?t=%s" % view_token,
        "rozmer_mm": [round(x, 1) for x in geom["overall_size"]], "pocet_profilu": len(geom["profily"]), "vandr_car_name": datas[0].get("car_name"),
        "karty": [r["id"] for r in rows], "strany": strany, "cena_celkem": round(total, 2),
        "v3d": v3d_ok, "v3d_duvod": None if v3d_ok else v3d_duvod, "v3d_varovani": varovani, "v3d_ms": v3d_ms, "v3d_cache": cache.get("hit") if v3d_ok else None,
        "v3d_build": build, "v3d_znacka": znacka if v3d_ok else None, "obrazky_zdroj": zdroje, "poznamka": " ".join(poznamky) or None,
    }), 201


@app.post("/api/admin/vandr-vyroba/<int:shop_product_id>/nabidka")
@require_permission("sdileny_disk", "zobrazit")
def vandr_vyroba_vytvorit_nabidku(shop_product_id):
    """Postavi kompletni online nabidku (3D model bez karoserie + 1
    kotovany 2D vykres + 2 3D pohledy - VSE prevzate z Vandru, nic
    dopocitane - + 1-radkovy kusovnik s cenou karty) primo z jiz
    nasazeneho katalogoveho GLB Vandr karty. Zadny predchozi krok
    (razitka/render/aktivace) neni podminkou - nabidka je nezavisla na
    tom, jestli je karta uz `active=1` na webu.

    3D (2026-10-02): zakaznicky model s pohyby (viz docstring modulu) se
    postavi PRED zalozenim nabidky; kdyz nevznikne, nabidka vznikne dosavadni
    cestou a odpoved ma v3d:false + v3d_duvod. Odpoved 201 viz
    docs/KONTRAKT_VANDR_NABIDKA_ENDPOINT.md (pole v3d* pribyla zpetne
    kompatibilne)."""
    t_start = time.time()
    user = current_user()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, name, sku, description, glb_file, price_czk_placeholder, vandr_predni_azimut_deg "
                "FROM shop_products WHERE id=%s",
                (shop_product_id,),
            )
            karta = cur.fetchone()
    finally:
        conn.close()

    if not karta:
        return jsonify({"error": "Karta neexistuje."}), 404
    ok, duvod_ne = can_create_offer(karta)
    if not ok:
        return jsonify({"error": duvod_ne}), 400
    uuid = _vandr_uuid_karty(karta["sku"])

    glb_path = os.path.join(KATALOG_DIR, karta["glb_file"])

    try:
        vandr_data, v3d_duvod = _nacti_vandr_data(uuid, t_start)
    except (subprocess.TimeoutExpired, RuntimeError, ValueError) as e:
        return jsonify({"error": "Načtení dat z Vandru selhalo: %s" % e}), 500

    part = _vyber_dil(vandr_data.get("parts") or {})     # None = Vandr nema zadny dil -> bez Vandr obrazku (2D vykres chybi, 3D pohledy nahradou)

    # --- 3D model (cache/build + kontrola) PRED nabidkou; neuspech = dosavadni cesta
    offer_glb, geom = None, None
    t_v3d = time.time()
    if v3d_duvod is None and os.path.exists(V3D_VYPNUTO_SOUBOR):
        v3d_duvod = "3D model je vypnutý souborem private-files/v3d-vypnuto (smazáním souboru se zapne)"
    if v3d_duvod is None:
        try:
            offer_glb, geom = _postav_v3d_model(shop_product_id, vandr_data, t_start)
        except _V3DNevzniklo as e:
            v3d_duvod = str(e)
    if offer_glb is None:
        app.logger.warning("Vandr nabidka z karty %s: bez 3D modelu (v3d:false): %s", shop_product_id, v3d_duvod)
    v3d_ms = int(round((time.time() - t_v3d) * 1000))
    static_glb = None
    if offer_glb is None:
        try:
            static_glb, geom = _staticky_model(glb_path, t_start)
        except (subprocess.TimeoutExpired, RuntimeError) as e:
            return jsonify({"error": "Výpočet geometrie selhal: %s" % e}), 500

    # --- obrazky nabidky: Vandr, kde existuji; 3D pohledy jinak nahrada, 2D vykres se nevyrabi (nikdy 400; viz modulovy docstring g)
    try:
        views, obrazky_zdroj, obrazky_poznamka, obrazky_rozmery = _dopln_obrazky(
            shop_product_id, karta, part, offer_glb if offer_glb is not None else static_glb)
    except Exception as e:
        app.logger.exception("Vandr nabidka z karty %s: nahradni obrazky nevznikly", shop_product_id)
        return jsonify({"error": "Obrázky nabídky nevznikly (Vandr je nemá a náhradu se nepodařilo vyrobit: %s: %s). "
                                 "Nabídka nevznikla." % (type(e).__name__, _kratce(e))}), 500

    price = float(karta["price_czk_placeholder"])
    # Robert primo, 2026-09-28 ("Vandr sestavy maji kody, nemuze tam byt
    # polozka jen karoserie"): `karta["name"]` je jen identifikace VOZU
    # ("Ford Transit L3H3 FWD"), ne popis PRODUKTU - polozka by pak
    # vypadala, jako by se prodavala karoserie auta. Popis produktu
    # (shop_products.description, napr. "Hlinikova regalova vestavba do
    # nakladoveho prostoru...") + SKU kod misto toho.
    item_name = "%s (%s)" % (karta["description"] or karta["name"], karta["sku"])
    items = [{"name": item_name, "qty": 1, "unit_price": price, "total": price}]
    # Robert primo, 2026-09-28 ("Vadr sestavy doprodavame... nelze
    # dobirka, pouze zalohove platby min 50%"): hidden_payment_method
    # vynuti jedinou moznost "zaloha" (viz forcedPaymentMethod v
    # nabidka-online.html) - existujici 50-100% posuvnik zalohy uz sam
    # o sobe ma podlahu 50%, zadny dalsi fixed_deposit_pct netreba.
    offer_options = {
        **scene_offers.OFFER_OPTIONS_DEFAULT,
        "vandr_single_drawing": True,
        "hidden_payment_method": "dobirka",
    }
    if "narys" not in views:        # Vandr u karty nema kotovany 2D vykres: nabidka BEZ stranky Vykresy, 2D se nevyrabi (Robert 2026-10-06)
        offer_options["vandr_bez_vykresu"] = True
        views["narys"] = _PRAZDNY_PNG

    offer_id, offer_number, view_token = scene_offers.create_scene_offer_row(
        items, price, views, None, None, None, offer_options, user["id"],
    )

    # --- model k nabidce: v3d (po znaceni a posledni kontrole), jinak dosavadni staticky
    znacka, varovani_znacky = "vypnuto", None
    model_bytes = static_glb
    if offer_glb is not None:
        try:
            model_bytes, znacka, varovani_znacky = _oznac_model(offer_glb, offer_id)
            model_bytes = _over_zakaznicky_glb(model_bytes)
        except Exception as e:
            # po zalozeni nabidky uz jen zalozni vetev: dosavadni staticky model (fail closed - nikdy se
            # neulozi model, ktery neprosel kontrolou nebo nejde oznacit, kdyz je znaceni zapnute)
            if isinstance(e, _V3DNevzniklo):
                v3d_duvod = e.args[0]
            else:
                v3d_duvod = "3D model neprošel poslední kontrolou (%s: %s)" % (type(e).__name__, _kratce(e))
                if not isinstance(e, ValueError):
                    app.logger.exception("Vandr nabidka %s: neocekavana chyba pri koncove kontrole 3D modelu", offer_number)
            app.logger.warning("Vandr nabidka %s: 3D model se neulozil (v3d:false): %s", offer_number, v3d_duvod)
            offer_glb = model_bytes = None
        if offer_glb is None:
            try:
                static_glb, geom = _staticky_model(glb_path, t_start)
            except (subprocess.TimeoutExpired, RuntimeError) as e:
                return jsonify({"error": "Nabídka %s vznikla, ale 3D model se neuložil: výpočet geometrie selhal: %s"
                                         % (offer_number, e),
                                "offer_id": offer_id, "offer_number": offer_number}), 500
            model_bytes, znacka = static_glb, "vypnuto"
    model_err = scene_offers.save_offer_model_bytes(offer_id, model_bytes, user["id"] if user else None)
    if model_err:
        app.logger.warning("Vandr nabidka %s: ulozeni 3D modelu selhalo: %s", offer_number, model_err)

    v3d_ok = offer_glb is not None
    cache = (geom.get("cache") or {}) if v3d_ok else {}
    varovani = (list(geom.get("warnings") or []) + list(geom.get("ctx_warnings") or [])) if v3d_ok else []
    if varovani_znacky:
        varovani.append(varovani_znacky)
    build = cache.get("verze_buildu") if v3d_ok else None
    _zaznam_v3d(user["id"] if user else None, offer_id, v3d=v3d_ok, build=build,
                duvod=None if v3d_ok else _kratce(v3d_duvod, 200),
                znacka=znacka if v3d_ok else None, cache_hit=cache.get("hit") if v3d_ok else None, ms=v3d_ms,
                varovani=len(varovani), obrazky=obrazky_zdroj)

    return jsonify({
        "status": "ok",
        "offer_id": offer_id,
        "offer_number": offer_number,
        "online_url": "/nabidka-online.html?t=%s" % view_token,
        "rozmer_mm": [round(x, 1) for x in geom["overall_size"]],
        "pocet_profilu": len(geom["profily"]),
        "vandr_car_name": vandr_data.get("car_name"),
        # 3D (2026-10-02, zpetne kompatibilni prirustek, viz docs/KONTRAKT_NABIDKA_3D.md)
        "v3d": v3d_ok,
        "v3d_duvod": None if v3d_ok else v3d_duvod,
        "v3d_varovani": varovani,            # jen pro admina: obsahuje jmena dilu z buildu, do GLB nejdou
        "v3d_ms": v3d_ms,
        "v3d_cache": cache.get("hit") if v3d_ok else None,
        "v3d_build": build,
        "v3d_znacka": znacka if v3d_ok else None,
        # obrazky nabidky (2026-10-02): "vandr" = z Vandru, "nahrada" = nase (vykres z modelu, snimky otocky/galerie/model),
        # view3d muze byt i "kombinace" (jeden Vandr, druhy nahrada). poznamka = text pro admina, kdyz sla o nahradu.
        "obrazky_zdroj": obrazky_zdroj,
        "poznamka": obrazky_poznamka,
        # rozmery (mm) z nahradniho vykresu = skutecny produkt BEZ podlahy/loga; jen kdyz narys vyrobil server
        "obrazky_rozmery_mm": obrazky_rozmery,
    }), 201
