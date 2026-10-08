"""
Otocny (sfericky) nahled produktove sestavy pro e-shop (bot16, 2026-09-02).

Robert 2026-09-02: pro produktove sestavy na e-shopu chce misto fotky
otocny nahled generovany primo ze 3D sceny, "k nerozeznani svou kvalitou,
zadne rozmazani". Upresneni tentyz den (pres bot3): nahled je SFERICKY.

ROZSAH DAVKY - JEDINY ZDROJ PRAVDY JSOU KONSTANTY NIZE, ne tenhle text:
ELEVATIONS x AZIMUTHS x TIERS = EXPECTED_FRAME_COUNT. K 2026-09-11 (Robert:
"chci nastavit 30 stupnu na prstenec hned") to je 3 elevace (-40/0/+40) x
9 azimutu (270stupnova vysec po 30 stupnich, DELENA CELOCISELNE - vyjde
±120° kolem predku, ne celych ±135°) x 2 tiery (master 2048x2048 +
1024x1024, CTVEREC - bot3/Robert 2026-09-02, widget je ctvercovy)
= 54 souboru na sestavu, 27 skutecnych renderu (druhy tier je dopocitane
zmenseni, ne dalsi render).
POZOR, tenhle odstavec uz DVAKRAT zastaral a poprve to stalo chybny odhad
casu renderu na dvojnasobek: do 2026-09-11 rano tu stalo "5 prstencu x 36
snimku = 360 souboru" jeste z doby pred zuzenim na 270stupnovou vysec
(drive 0/20/40/60/80, pak -40/-20/0/+20/+40; stara davka 3938 je jeste v
pet-prstencovem rozsahu), pak "3 x 27 x 2 = 162" z doby kroku 10°. Kdyz
meniš ELEVATIONS/AZIMUTHS/TIERS/STEP_DEG, prepiš i sem.
"Stills" (samostatne tesne rendery kanonickych pohledu) uz se NEPOSILAJI -
kanonicke obrazky se berou ze snimku prstence, viz STILL_VIEWS nize.

Snimky vyrabi bud PROHLIZEC admina (scene.html, viz paRenderTurntable*
tam -> /turntable/frames + /turntable/commit), nebo GPU pres vzdaleny
render worker (api/render_worker.py -> api/turntable_ingest.py, ktery
vola tytez funkce `ulozit_snimky`/`commit_batch` primo). Tenhle modul je
uloziste + API + pravidla davky pro OBE cesty.

Rozdeleni:
  * POST /api/product-assemblies/<id>/turntable/frames  (login, vlastnik/admin)
      multipart, pole `batch` (volitelne - prvni volani bez nej dostane nove
      batch id v odpovedi) + soubory pojmenovane `frame_e<elev>_a<azim>_t<tier>`
      (napr. frame_e20_a090_t2048, zaporna elevace frame_e-20_a090_t2048)
      a/nebo `still_<key>` (key z STILL_VIEWS,
      napr. still_hero; presne rozmery podle STILL_VIEWS, jen plna velikost -
      1024 varianty dela server). Snimky prstencu jdou do DB s is_active=0,
      stills jen na disk (<batch>/stills/<key>.jpg + stills.json) - na
      e-shopu se NIC nemeni, dokud neprobehne commit.
  * POST /api/product-assemblies/<id>/turntable/commit  {"batch", "camera"}
      overi kompletnost (EXPECTED_FRAME_COUNT radku + souboru na disku;
      stills se od 2026-09-11 nevyzaduji), zapise camera.json (parametry kamery pro fazi C - skok z
      nahledu do sceny),
      prepne is_active na novou davku; VSECHNY ostatni davky produktu
      (starou aktivni i pripadne nedokoncene) jen DEAKTIVUJE (is_active=0,
      deactivated_at=NOW()). Fyzicke smazani (radky + soubory) az po
      GRACE_HOURS (24 h - bot3/Robert 2026-09-02: navstevnik s otevrenou
      strankou uprostred otacky nema dostat 404 na dalsi snimek hned po
      cizim commitu; widget cte URL z aktivni davky, takze DALSI nacteni
      stranky uz dostane novou davku bez ohledu na grace) - viz
      _sweep_expired_batches, volana z tohoto endpointu i ze
      scripts/turntable_cleanup.py (budouci cron). Atomicka vymena: stara
      sada zustava funkcni po celou grace dobu.
  * GET  /api/shop/products/<id>/turntable  (VEREJNE, cte ho widget na
      strance produktu - kontrakt sladeny s druhym agentem, viz
      _build_public_payload; nemenit tvar bez domluvy).
  * DELETE /api/product-assemblies/<id>/turntable  (login, vlastnik/admin)
      smaze vsechny davky produktu.

Uloziste je ZAMERNE ODDELENE od bezne fotogalerie produktu
(gallery_items.py / content_gallery_items) - tabulka product_turntable_frames
(sql/2026-09-02_product_turntable_frames.sql) + DVA adresare s ruznym
SEO rezimem (bot3/Robert 2026-09-02, "snimky prstencu noindex,
kanonicke pohledy indexovatelne s popisnym nazvem"):
  * snimky prstencu (EXPECTED_FRAME_COUNT JPEGu, cache-bust pres batch v ceste):
      UPLOAD_DIR/turntable-frames/<shop_product_id>/<batch>/<tier>/e<elev:02d>/a<azim:03d>.jpg
    nginx `location ^~ /content-files/turntable-frames/` s
    `X-Robots-Tag: noindex` + `Cache-Control: public, max-age=31536000,
    immutable` (URL se nikdy nemeni pod rukama, nova davka = nove URL).
  * kanonicke staticke obrazky (vyrabi je commit, viz _write_canonical;
    NAZVY ani klice nemenit - bot14 ma na ne navazany JSON-LD/OG/sitemap):
      UPLOAD_DIR/turntable/<slug>/<slug>-zepredu.jpg      hero       (orez snimku prstence, 2048x1536)
      UPLOAD_DIR/turntable/<slug>/<slug>-zepredu-16x9.jpg hero_16x9  (orez tehoz snimku, 1920x1080)
      UPLOAD_DIR/turntable/<slug>/<slug>-bok.jpg          side       (orez, 2048x1536)
      UPLOAD_DIR/turntable/<slug>/<slug>-shora.jpg        top        (orez, 2048x1536)
      (pohled "zezadu" Robert 2026-09-11 ZRUSIL - v 270 stupnove vyseci
       neexistuje a zadni stranu ukazovat nechceme)
      UPLOAD_DIR/turntable/<slug>/<slug>-zepredu-1x1.jpg  BYTE KOPIE snimku prstence HERO_RING
        (2048x2048) = SSR placeholder, MUSI byt pixelove shodny s prvnim
        snimkem widgetu (vychozi pohled = HERO_RING, k 2026-09-11
        el 0 / az FRONT_AZIMUTH_DEG; drive natvrdo el 20 / az 60), aby prechod
        placeholder -> widget nebyl videt; `-1x1-1024` = byte kopie tieru 1024
    Do 2026-09-11 byly kanonicke obrazky SAMOSTATNE rendery s vlastni,
    tesnejsi kamerou (el 20 resp. 60). Robert je zrusil ("vypust hero
    snimek, vymaz, zapomen", "budeme pouzivat pouze snimky z otaceni") -
    nove se orezavaji ze snimku prstence. POZOR, meni to uhel pohledu:
    prstenec ma elevace jen (-40, 0, 40), takze puvodnich 20/60 v nem
    neexistuje a vychozi mapovani miri na nejblizsi dostupnou. Ktery snimek
    slouzi jako ktery pohled urcuje _canonical_ring_source() a da se
    prepsat v app_settings. 1024 varianty (`<slug>-zepredu-1024.jpg`
    1024x768, `-16x9-1024` 1024x576, ...) dela server PIL LANCZOS q92 pro
    `srcset` SSR hero (bot14, LCP na mobilu).
    nginx `location ^~ /content-files/turntable/` BEZ noindex, kratsi
    cache (nazev je stabilni, obsah se pri prerenderu prepise) - tohle
    jsou obrazky, ktere maji byt v Google Images / og:image / SSR (bot14,
    api/products.py, importuje turntable_public_info() nize).
    Seznam kanonickych souboru davky je v <batch>/canonical.json, aby je
    _delete_batches umel uklidit i po zmene slugu produktu.
Metadata (GET vyse) maji Cache-Control: no-cache, aby widget po nove
davce dostal nove URL.

Galerie a thumbnail po commitu (_fill_gallery_and_thumbnail):
  * galerie: nema-li produkt zadnou polozku v content_gallery_items, vlozi
    se hero (still zepredu) jako prvni polozka (sort_order 0, caption
    "<nazev sestavy> - pohled zepredu", soubor v gallery-items/ podle
    konvence gallery_items.py: product-<id>_<slug>-zepredu-<hex8>.jpg).
    Pri prerenderu se nahradi JEN polozka, kterou zalozil turntable
    (id v canonical.json davky, zaloha: prefix `product-<id>_<slug>-
    zepredu-` v nazvu souboru) - rucne nahrane fotky se nikdy nesahaji
    (Robert: fotky realneho produktu maji prednost pred renderem).
  * thumbnail: je-li shop_products.thumbnail_file prazdny, nastavi se na
    "thumbnails/product-<id>.jpg" (1024x768 zmenseny hero v
    KATALOG_THUMBNAIL_DIR - stejny nazev i format jako POST
    /api/catalog-thumbnail v app.py, scene.html si pridava prefix
    "katalog/"). Protoze rucni upload pouziva TENTYZ nazev, pamatuje si
    davka v canonical.json `thumbnail_owned: true` - jen pak se thumbnail
    pri prerenderu prepise; cizi/rucni thumbnail zustava.

Grace period je SCHEMA-TOLERANTNI (bot3/Robert 2026-09-02): kod byl
commitnuty drive, nez sql/2026-09-02_turntable_deactivated_at.sql smela
probehnout na produkci (migrace ceka na Robertovo schvaleni). Dokud
sloupec product_turntable_frames.deactivated_at neexistuje,
_has_deactivated_at_column() to pozna (dotaz do information_schema pri
kazdem commitu/sweepu, ne cachovane) a turntable_commit/_sweep_expired_
batches se chovaji jako PRED touto zmenou - stara davka se smaze OKAMZITE
(+ app.logger.warning). Jakmile migrace probehne, dalsi commit uz grace
period pouzije SAM, bez restartu sluzby.

Aktivace: `import turntable` na konci app.py (po `import products` - jen
kvuli poradi registrace /api/shop/products/* tras, zadny primy import),
hned za nim `import turntable_ingest` (prevzeti renderu z GPU, bez rout -
importuje se kvuli fail-fast pri startu).
"""
import json
import os
import re
import secrets
import shutil
import sys
import time
from io import BytesIO

from flask import request, jsonify
from PIL import Image, UnidentifiedImageError

from app import (app, get_conn, current_user, login_required, log_audit, UPLOAD_DIR,
                 KATALOG_THUMBNAIL_DIR, _slugify, get_setting)
from gallery_items import GALLERY_ITEMS_DIR

# Sjednoceni ramovani nahledu karet (bot4, 2026-09-26, Robert: "stejny
# kabat") - sdileny modul se scripts/2026-09-26_normalizuj_vsechny_
# nahledy.py (jednorazovy davkovy prubeh pres existujici katalog), aby
# NOVE karty vznikaly uz normalizovane stejnym kodem, ne druhou kopii.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
import _thumbnail_normalizace as _thumb_norm  # noqa: E402
# Jednotna dlazdice (bot4, 2026-09-30, Robert "PODRUHE": nahledy karet musi byt vsechny stejne velke a ve
# stejnem formatu) - hlavni (galerijni) nahled karty, ktery ukazuje dlazdice kategorie; viz _nahled_dlazdice.py.
import _nahled_dlazdice as _dlazdice  # noqa: E402

# snimky prstencu (noindex, immutable) vs. kanonicke obrazky (indexovatelne)
# - dva sourozenecke adresare, aby se nginx hlavicky neprekryvaly
FRAMES_SUBDIR = "turntable-frames"
CANONICAL_SUBDIR = "turntable"
TURNTABLE_DIR = os.path.join(UPLOAD_DIR, FRAMES_SUBDIR)
CANONICAL_DIR = os.path.join(UPLOAD_DIR, CANONICAL_SUBDIR)
os.makedirs(TURNTABLE_DIR, exist_ok=True)
os.makedirs(CANONICAL_DIR, exist_ok=True)
# Robert 2026-09-06 (ochrana 3D modelu sestav): "predni" smer regalu v
# souradnicich render riggu (scene.html paRenderTurntable). PUVODNE pevna
# konstanta pro VSECHNY sestavy - bot8 2026-09-06 (Robert: "opet to mas
# renderovane zezadu", sestava 190/K-123e horni ram+MDF vysla zmerenim ze
# skutecne geometrie na az=90, presny OPAK ostatnich Jumpy sestav na
# az=270): kazda sestava ma sve VLASTNI predni smer podle toho, jakym
# skriptem/session byla postavena (napr. zrcadlova leva/prava varianta -
# Robert: "celo regalu leveho se musi renderovat z prave strany, a
# obracene") - jedna globalni konstanta NEMUZE byt spravna pro vsechny.
# FRONT_AZIMUTH_DEG zustava jako VYCHOZI hodnota (kdyz klient nepošle
# vlastni `front_azimuth_deg` - stary klient, nebo sestava bez role tagu
# k automatickemu vypoctu), skutecny pouzity smer se ted pocita za behu
# (_azimuths_for_front/_canonical_views_for_front) a uklada per-davka do
# canonical.json (`front_azimuth_deg`), ZADNA zmena schematu DB netreba.
# Definovano PRED CANONICAL_VIEWS/STILL_VIEWS, protoze na nej odkazuji.
FRONT_AZIMUTH_DEG = 270
TURNTABLE_URL_PREFIX = "/content-files/"
STEP_DEG = 30  # 2026-09-11 pozdeji, Robert primo: "chci nastavit 30 stupnu na prstenec hned" (bylo 10)
# Robert 2026-09-06 (ochrana 3D modelu sestav - viz AGENTS_LOG.md
# "Ochrana 3D modelu sestav: 3 stupne", project_ochrana_3d_modelu_
# sestav.md): zuzeno z puvodnich 5 prstencu x 360 stupnu na 3 prstence x
# 270 stupnu vysec - regal se ve skutecnosti pozoruje jen zepredu/z boku
# (stoji u steny auta, zezadu neni co videt - Robert: "nepotrebujeme
# videt regal zezadu"), min dat = min extrahovatelne geometrie i min
# prenosu. Puvodni (0,20,40,60,80) pak (-40,-20,0,20,40) driv v tomto
# souboru - historie zachovana v git logu, ne v kodu.
ARC_DEG = 270  # vysec kolem prednim azimutem - vynechava 90 stupnu okolo zadni strany
_arc_half_steps = (ARC_DEG // STEP_DEG) // 2  # 4 (270/30/2, zaokrouhleno dolu -> vysledna vysec je jen ±120°, ne ±135°)


def _azimuths_for_front(front):
    """Mnozina povolenych/ocekavanych azimutu pro danou PREDNI stranu (viz
    komentar u FRONT_AZIMUTH_DEG - front uz neni globalni konstanta, kazda
    davka/sestava ho muze mit jiny)."""
    return tuple(sorted((front + STEP_DEG * i) % 360 for i in range(-_arc_half_steps, _arc_half_steps + 1)))


# ---------------------------------------------------------------------------
# KANONICKE POHLEDY SE BEROU Z PRSTENCE (Robert 2026-09-11)
#
# Robert: "vypust hero snimek, vymaz, zapomen", "budeme pouzivat pouze
# snimky z otaceni", "prevezmou se z otackovych snimku ktere urcim".
#
# Do 2026-09-11 se peti kanonickych pohledu renderovalo SAMOSTATNE (klient
# scene.html::ttStillsForFront + renderovaci pipeline) s vlastni, tesnejsi
# kamerou. Nove se uz nerenderuji vubec - kazdy pohled je OREZ nekstereho
# snimku prstence.
#
# POZOR, TOHLE MENI UHEL POHLEDU: stills se renderovaly na elevaci 20
# (hero/side) resp. 60 (top), jenze prstenec ma jen (-40, 0, 40). Tyhle
# elevace v nem NEEXISTUJI, takze prevzeti NENI bezeztratove - vychozi
# hodnoty nize miri na NEJBLIZSI elevaci, ktera v prstenci je (20 -> 0,
# 60 -> 40). Robert si je muze prenastavit, viz nize.
#
# Azimut se drzi jako ODCHYLKA od predniho azimutu davky, ne absolutne -
# kazda sestava ma svuj vlastni "predek" (viz FRONT_AZIMUTH_DEG).
CANONICAL_SUFFIX = {
    "hero": "zepredu",
    "side": "bok",
    "top": "shora",
    "hero_16x9": "zepredu-16x9",
}
# klic -> (elevace, odchylka azimutu od predku). Prepsatelne v DB, viz
# _canonical_ring_source().
CANONICAL_RING_SOURCE_DEFAULT = {
    "hero": (0, 0),
    "side": (0, 90),
    "top": (40, 0),
    "hero_16x9": (0, 0),
}
# cilovy pomer stran kanonickeho obrazku (orez ze ctvercoveho snimku
# prstence). Zustava stejny jako mely puvodni stills, aby se konzumentum
# (JSON-LD/OG/sitemap/galerie) nezmenil tvar pod rukama.
CANONICAL_ASPECT = {
    "hero": (2048, 1536),
    "side": (2048, 1536),
    "top": (2048, 1536),
    "hero_16x9": (1920, 1080),
}
CANONICAL_RING_SOURCE_KEY = "turntable_canonical_ring_source"


def _canonical_ring_source():
    """{klic: (elevace, odchylka_azimutu)} - ze ktereho snimku prstence se
    bere ktery kanonicky pohled.

    Robert 2026-09-11: "prevezmou se z otackovych snimku KTERE URCIM" -
    proto se to nedrzi natvrdo v kodu, ale da se prepsat v
    `app_settings.turntable_canonical_ring_source` (JSON
    {"hero": {"el": 0, "az": 0}, ...}). Nesmyslna hodnota se schvalne
    chova jako vychozi - obrazky produktu nesmi spadnout na tom, ze je
    v nastaveni preklep (stejny princip jako get_scene_price_coefficient).

    Validuje se, ze elevace i vysledny azimut v prstenci SKUTECNE existuji;
    jinak by commit tise vyrobil pohled bez zdroje.
    """
    vychozi = dict(CANONICAL_RING_SOURCE_DEFAULT)
    conn = None
    try:
        conn = get_conn()
        with conn.cursor() as cur:
            raw = get_setting(cur, CANONICAL_RING_SOURCE_KEY, None)
    except Exception:
        return vychozi
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
    if not raw:
        return vychozi
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return vychozi
    if not isinstance(data, dict):
        return vychozi
    out = {}
    for klic, (el_def, az_def) in CANONICAL_RING_SOURCE_DEFAULT.items():
        v = data.get(klic)
        el, az = el_def, az_def
        if isinstance(v, dict):
            try:
                el_n, az_n = int(v.get("el", el_def)), int(v.get("az", az_def)) % 360
                # musi existovat v prstenci, jinak by pohled nemel zdroj
                if el_n in ELEVATIONS and (az_n % STEP_DEG) == 0 and abs(az_n if az_n <= 180 else az_n - 360) <= _arc_half_steps * STEP_DEG:
                    el, az = el_n, az_n
            except (TypeError, ValueError):
                pass
        out[klic] = (el, az)
    return out


def _canonical_views_for_front(front, source=None):
    """Kanonicke pohledy pro danou predni stranu.

    Robert 2026-09-11 ZRUSIL pohled "zezadu": prstenec je 270 stupnova
    vysec a zadnich 90 stupnu zamerne vynechava (ochrana 3D modelu), takze
    se zezadu nema z ceho vzit - a ukazovat zadni stranu stejne nechceme.
    Klice ostatnich pohledu zustavaji KONTRAKT (JSON-LD/OG/sitemap).

    `source` = mapa z _canonical_ring_source(); kdyz se nepreda, pouziji
    se VYCHOZI hodnoty bez sahnuti do DB - dulezite, protoze tahle funkce
    se vola i na urovni modulu (CANONICAL_VIEWS nize), kde jeste neexistuji
    ELEVATIONS ani spojeni do databaze.
    """
    zdroj = CANONICAL_RING_SOURCE_DEFAULT if source is None else source
    vyhled = {}
    for klic, (el, az_off) in zdroj.items():
        vyhled[klic] = (CANONICAL_SUFFIX[klic], el, (front + az_off) % 360)
    return vyhled


# kanonicke pohledy (bot3/Robert 2026-09-02): klic -> (pripona nazvu,
# elevace, azimut). Klice i pripony jsou KONTRAKT (bot14 JSON-LD/OG/sitemap).
# bot8 2026-09-06: azimuty prepocitany na FRONT_AZIMUTH_DEG (puvodni "hero"
# az=60 byl ve skutecnosti pohled ZEZADU, viz KAROSERIE_UMISTENI.md).
# Nazvy klicu/pripon jsou porad kontrakt, KONKRETNI azimut uz se pocita
# per-davka (_canonical_views_for_front) - tohle zustava jen vychozi/fallback.
CANONICAL_VIEWS = _canonical_views_for_front(FRONT_AZIMUTH_DEG)
# stills = samostatne tesne rendery z klienta: klic -> (pripona, el, az, (w, h))
# (rozmery se overuji proti skutecnemu JPEGu; hero_16x9 je vlastni render,
# ne orez). hero_1x1 tu neni - je to byte kopie snimku prstence HERO_RING.
# ZASTARALE od 2026-09-11 (Robert: "budeme pouzivat pouze snimky z otaceni").
# Kanonicke obrazky uz se z techhle stillu NEVYRABEJI - berou se z prstence,
# viz CANONICAL_RING_SOURCE_DEFAULT / _write_canonical. Tabulka zustava JEN
# proto, aby upload endpoint nerozbil starsi klienty, kteri stills posilaji
# dal: prijmou se, ulozi na disk a dal se ignoruji. "back" je pryc uplne -
# Robert ten pohled zrusil.
STILL_VIEWS = {
    "hero": ("zepredu", 0, FRONT_AZIMUTH_DEG, (2048, 1536)),
    "side": ("bok", 0, (FRONT_AZIMUTH_DEG + 90) % 360, (2048, 1536)),
    "top": ("shora", 40, FRONT_AZIMUTH_DEG, (2048, 1536)),
    "hero_16x9": ("zepredu-16x9", 0, FRONT_AZIMUTH_DEG, (1920, 1080)),
}
HERO_RING = (0, FRONT_AZIMUTH_DEG)  # (el, az) prvniho snimku widgetu = zdroj hero_1x1
CANONICAL_JPEG_QUALITY = 92
CANONICAL_SMALL_W = 1024  # srcset varianta kazdeho kanonickeho obrazku (klic `<key>_1024`)
STILLS_SUBDIR = "stills"  # <batch>/stills/<key>.jpg + <batch>/stills.json
GRACE_HOURS = 24  # stara (deaktivovana) davka zmizi fyzicky az po tolika hodinach
ORPHAN_DAYS = 7  # rozpracovana (nikdy neaktivovana) davka bez commitu se uklidi po tolika dnech

ELEVATIONS = (-40, 0, 40)
DEFAULT_ELEVATION = 0
# FRONT_AZIMUTH_DEG definovan vyse (pred CANONICAL_VIEWS/STILL_VIEWS).
DEFAULT_AZIMUTH = FRONT_AZIMUTH_DEG  # vychozi pohled widgetu = hero = zepredu (fallback bez ulozeneho front_azimuth_deg)
AZIMUTHS = _azimuths_for_front(FRONT_AZIMUTH_DEG)  # vychozi/zpetne kompatibilni sada (fallback)
ASPECT = (1, 1)
# tier_px -> (sirka, vyska) - overuje se proti SKUTECNYM rozmerum JPEGu,
# ne jen proti tomu, co klient tvrdi v nazvu pole.
TIERS = {2048: (2048, 2048), 1024: (1024, 1024)}
EXPECTED_FRAME_COUNT = len(ELEVATIONS) * len(AZIMUTHS) * len(TIERS)  # 162
# 3 elevace x 27 azimutu (270 stupnu po 10) x 2 velikosti = 162.
# Do 2026-09-11 tu stal komentar "# 360" - byl ZASTARALY jeste z doby
# pred zuzenim na 270 stupnovou vysec a svedl uz jeden odhad casu renderu
# na dvojnasobek. Cislo se pocita, komentar je jen kontrola.
# Limity velikosti jednoho souboru: JPEG q0.92 ctvercoveho masteru realne
# ~100-250 kB (jednobarevne pozadi), tier 1024 ~30-80 kB, stills ~150-300 kB
# - 6 MB / 2 MB / 4 MB je bezpecna rezerva (4:3 melo 4 / 1.5 MB, ctverec
# ma o 33 % vic pixelu), ne tesny strop.
MAX_BYTES = {2048: 6 * 1024 * 1024, 1024: 2 * 1024 * 1024}
MAX_STILL_BYTES = 4 * 1024 * 1024
MAX_FILES_PER_REQUEST = 48
FIELD_RE = re.compile(r"^frame_e(-?\d{1,2})_a(\d{1,3})_t(\d{4})$")
STILL_FIELD_RE = re.compile(r"^still_([a-z0-9_]{1,32})$")
BATCH_RE = re.compile(r"^[0-9]{14}-[0-9a-f]{12}$")


def _new_batch_id():
    return time.strftime("%Y%m%d%H%M%S") + "-" + secrets.token_hex(6)


def _frame_rel_path(shop_product_id, batch, tier, elev, azim):
    # e00/e20/... ; zaporna elevace -> e-20/e-40 (f"{-20:02d}" == "-20")
    return f"{FRAMES_SUBDIR}/{shop_product_id}/{batch}/{tier}/e{elev:02d}/a{azim:03d}.jpg"


def _batch_dir(shop_product_id, batch):
    return os.path.join(TURNTABLE_DIR, str(shop_product_id), batch)


def _load_assembly_for_user(assembly_id):
    """Sestava + kontrola prav (vlastnik nebo admin - stejna logika jako
    DELETE /api/product-assemblies v app.py). Vraci (row, error_response)."""
    user = current_user()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name, created_by, shop_product_id FROM product_assemblies WHERE id=%s", (assembly_id,))
            row = cur.fetchone()
    finally:
        conn.close()
    if not row:
        return None, (jsonify({"error": "Sestava neexistuje."}), 404)
    if row["created_by"] != user["id"] and user["role"] != "admin":
        return None, (jsonify({"error": "Nemáš oprávnění k této sestavě."}), 403)
    if not row["shop_product_id"]:
        return None, (jsonify({"error": "Sestava nemá navázaný e-shopový produkt."}), 400)
    return row, None


def _validate_jpeg(raw, expected_size):
    """JPEG magic + skutecne dekodovani PIL + PRESNE rozmery (tuple w, h).
    Vraci (width, height) nebo vyhodi ValueError s hlaskou pro klienta."""
    if len(raw) < 4 or raw[0] != 0xFF or raw[1] != 0xD8 or raw[2] != 0xFF:
        raise ValueError("Soubor není JPEG (chybí FFD8 hlavička).")
    try:
        img = Image.open(BytesIO(raw))
        img.verify()
        fmt, size = img.format, img.size
    except (UnidentifiedImageError, OSError, ValueError):
        raise ValueError("Soubor není platný JPEG.")
    if fmt != "JPEG":
        raise ValueError("Soubor není JPEG.")
    if tuple(size) != tuple(expected_size):
        raise ValueError(f"Snímek má {size[0]}x{size[1]} px, očekávám {expected_size[0]}x{expected_size[1]}.")
    return size


def _still_rel_path(shop_product_id, batch, key):
    return f"{FRAMES_SUBDIR}/{shop_product_id}/{batch}/{STILLS_SUBDIR}/{key}.jpg"


def zkontroluj_snimek(pole, cti, azimuths_ok):
    """`frame_e00_a090_t2048` + cteci funkce -> (elev, azim, tier, raw, w, h).

    Vyclenil bot8 2026-09-11: uplne stejnou kontrolu potrebuje upload z
    prohlizece (nazev je pole formulare, `cti` je fs.read) i ingest z GPU
    (nazev je soubor bez .jpg) - viz turntable_ingest.py. `cti(n)` se vola
    az po urceni tieru a ZAMERNE si rekne o max+1 bajt, aby se velky soubor
    nikdy nenacetl cely do pameti. ValueError nese hlasku pro klienta.
    """
    m = FIELD_RE.match(pole)
    if not m:
        raise ValueError(f"Neznámé pole souboru '{pole}' (očekávám frame_e<elev>_a<azim>_t<tier> nebo still_<key>).")
    elev, azim, tier = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if elev not in ELEVATIONS:
        raise ValueError(f"Neplatná elevace {elev} (povoleno {list(ELEVATIONS)}).")
    if azim not in azimuths_ok:
        raise ValueError(f"Neplatný azimut {azim} (0..350 po {STEP_DEG}).")
    if tier not in TIERS:
        raise ValueError(f"Neplatný tier {tier} (povoleno {sorted(TIERS)}).")
    raw = cti(MAX_BYTES[tier] + 1)
    if len(raw) > MAX_BYTES[tier]:
        raise ValueError(f"Snímek {pole} je příliš velký (max {MAX_BYTES[tier] // 1024} kB).")
    try:
        w, h = _validate_jpeg(raw, TIERS[tier])
    except ValueError as e:
        raise ValueError(f"{pole}: {e}")
    return elev, azim, tier, raw, w, h


def ulozit_snimky(shop_product_id, assembly_id, batch, items):
    """Zapis zvalidovanych snimku prstence na disk + do DB (is_active=0).

    `items` = seznam (elev, azim, tier, raw, w, h) ze `zkontroluj_snimek`.
    Vraci (seznam popisu ulozenych, celkovy pocet radku davky v DB).
    Vyclenil bot8 2026-09-11, aby ingest z GPU zapisoval TIMTO kodem, ne
    treti kopii tehoz INSERTu.
    """
    ulozene = []
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            for elev, azim, tier, raw, w, h in items:
                rel = _frame_rel_path(shop_product_id, batch, tier, elev, azim)
                abs_path = os.path.join(UPLOAD_DIR, rel)
                os.makedirs(os.path.dirname(abs_path), exist_ok=True)
                with open(abs_path, "wb") as fh:
                    fh.write(raw)
                # ON DUPLICATE KEY: opakovane nahrani tehoz snimku (retry po
                # chybe site) proste prepise soubor i radek, zadny 409.
                cur.execute(
                    "INSERT INTO product_turntable_frames "
                    "(shop_product_id, assembly_id, batch, elevation_deg, azimuth_deg, tier_px, filename, width_px, height_px, bytes, is_active) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,0) "
                    "ON DUPLICATE KEY UPDATE filename=VALUES(filename), width_px=VALUES(width_px), "
                    "height_px=VALUES(height_px), bytes=VALUES(bytes), created_at=CURRENT_TIMESTAMP",
                    (shop_product_id, assembly_id, batch, elev, azim, tier, rel, w, h, len(raw)),
                )
                ulozene.append({"elevation": elev, "azimuth": azim, "tier": tier, "bytes": len(raw)})
            cur.execute(
                "SELECT COUNT(*) AS n FROM product_turntable_frames WHERE shop_product_id=%s AND batch=%s",
                (shop_product_id, batch),
            )
            total = cur.fetchone()["n"]
        conn.commit()
    finally:
        conn.close()
    return ulozene, total


@app.post("/api/product-assemblies/<int:assembly_id>/turntable/frames")
@login_required
def turntable_frames_upload(assembly_id):
    row, err = _load_assembly_for_user(assembly_id)
    if err:
        return err
    shop_product_id = row["shop_product_id"]
    batch = (request.form.get("batch") or "").strip()
    if batch and not BATCH_RE.match(batch):
        return jsonify({"error": "Neplatné batch id."}), 400
    if not batch:
        batch = _new_batch_id()

    # bot8 2026-09-06 (viz komentar u FRONT_AZIMUTH_DEG): klient (scene.html)
    # spocita PREDNI azimut TETO KONKRETNI sestavy (z role tagu predni-
    # svislice/cap, kdyz jsou k dispozici) a posle ho tu. Ulozeno do batch
    # metadat, aby ho commit nasel i kdyz ho klient na commit nepošle znovu.
    #
    # POVINNY od 2026-09-11 (bot8 na pokyn bota3). Do te doby se pri chybejici
    # hodnote tise dosadil globalni fallback 270 - jenze GPU renderuje kazdou
    # sestavu s jejim VLASTNIM prednim azimutem (manifesty uloh maji 90) a
    # dosazena 270 by znamenala uplne jinou vysec: commit by pak hlasil 54 ze
    # 162 snimku chybejicich, i kdyz by davka byla kompletni. Tise dosazena
    # spatna hodnota je horsi nez odmitnuty request - front musi poslat ten,
    # kdo snimky vyrobil, protoze jen on vi, kam se kamera divala.
    front_raw = request.form.get("front_azimuth_deg")
    if front_raw is None:
        return jsonify({"error": "Chybí front_azimuth_deg - přední azimut musí poslat ten, kdo snímky vyrobil "
                                 "(scéna i GPU ho znají), server ho nedosazuje."}), 400
    try:
        front = int(front_raw) % 360
    except ValueError:
        return jsonify({"error": "Neplatný front_azimuth_deg."}), 400
    if front % STEP_DEG != 0:
        return jsonify({"error": f"front_azimuth_deg musí být násobek {STEP_DEG}."}), 400
    os.makedirs(_batch_dir(shop_product_id, batch), exist_ok=True)  # prvni request nove davky jeste nema adresar
    # Jeden chunk nesmi davku prepnout na jinou vysec nez predchozi chunky -
    # azimuts_ok se od front odvozuje, takze by v jedne davce vznikla smes
    # dvou ruznych sad azimutu a commit by ji nemel jak posoudit.
    drive = (_read_batch_json(shop_product_id, batch, "front.json") or {}).get("front_azimuth_deg")
    if drive is not None and int(drive) % 360 != front:
        return jsonify({"error": f"Dávka {batch} běží s předním azimutem {int(drive)}°, "
                                 f"tenhle požadavek posílá {front}° - jedna dávka = jeden přední azimut."}), 409
    azimuths_ok = _azimuths_for_front(front)
    _write_batch_json(shop_product_id, batch, "front.json", {"front_azimuth_deg": front})

    # Nejdriv VSECHNO zvalidovat do pameti, teprve pak zapisovat - jedna
    # vadna polozka v davce = cely request odmitnut, klient ji posle znovu
    # celou (jednodussi nez castecne uspechy).
    items = []
    still_items = []
    files = list(request.files.items(multi=True))
    if not files:
        return jsonify({"error": "Žádné soubory."}), 400
    if len(files) > MAX_FILES_PER_REQUEST:
        return jsonify({"error": f"Příliš mnoho souborů v jednom požadavku (max {MAX_FILES_PER_REQUEST})."}), 400
    for field, fs in files:
        sm = STILL_FIELD_RE.match(field)
        if sm:
            key = sm.group(1)
            if key not in STILL_VIEWS:
                return jsonify({"error": f"Neznámý still '{key}' (povoleno {sorted(STILL_VIEWS)})."}), 400
            raw = fs.read(MAX_STILL_BYTES + 1)
            if len(raw) > MAX_STILL_BYTES:
                return jsonify({"error": f"Still {field} je příliš velký (max {MAX_STILL_BYTES // 1024} kB)."}), 400
            try:
                w, h = _validate_jpeg(raw, STILL_VIEWS[key][3])
            except ValueError as e:
                return jsonify({"error": f"{field}: {e}"}), 400
            still_items.append((key, raw, w, h))
            continue
        try:
            items.append(zkontroluj_snimek(field, fs.read, azimuths_ok))
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

    saved = []
    stills_total = 0
    if still_items:
        # stills nejsou v DB (nejsou soucasti sfericke mrizky) - jen soubory
        # + stills.json v adresari davky; opakovane nahrani prepise
        os.makedirs(os.path.join(_batch_dir(shop_product_id, batch), STILLS_SUBDIR), exist_ok=True)
        meta = _read_batch_json(shop_product_id, batch, "stills.json") or {}
        for key, raw, w, h in still_items:
            rel = _still_rel_path(shop_product_id, batch, key)
            with open(os.path.join(UPLOAD_DIR, rel), "wb") as fh:
                fh.write(raw)
            meta[key] = {"filename": rel, "width": w, "height": h, "bytes": len(raw)}
            saved.append({"still": key, "bytes": len(raw)})
        _write_batch_json(shop_product_id, batch, "stills.json", meta)
        stills_total = len(meta)
    ulozene, total = ulozit_snimky(shop_product_id, assembly_id, batch, items)
    saved.extend(ulozene)
    return jsonify({
        "status": "ok", "batch": batch, "shop_product_id": shop_product_id,
        "saved": saved, "batch_total": total, "expected_total": EXPECTED_FRAME_COUNT,
        "stills_total": stills_total, "expected_stills": len(STILL_VIEWS),
    })


def _validate_camera(cam):
    """Parametry kamery z klienta (pro fazi C - scena z nich postavi
    identickou kameru). Jen cisla/pole cisel, nic se nevykonava - ale
    nechceme ukladat libovolny JSON blob, tak omezime tvar i velikost."""
    if cam is None:
        return None
    if not isinstance(cam, dict):
        raise ValueError("camera musí být objekt.")
    out = {}
    for key in ("center", "up"):
        v = cam.get(key)
        if v is not None:
            if not (isinstance(v, list) and len(v) == 3 and all(isinstance(x, (int, float)) for x in v)):
                raise ValueError(f"camera.{key} musí být [x,y,z].")
            out[key] = [float(x) for x in v]
    for key in ("distance", "fov", "margin", "bounding_radius", "aspect"):
        v = cam.get(key)
        if v is not None:
            if not isinstance(v, (int, float)):
                raise ValueError(f"camera.{key} musí být číslo.")
            out[key] = float(v)
    for key in ("bbox_min", "bbox_max"):
        v = cam.get(key)
        if v is not None:
            if not (isinstance(v, list) and len(v) == 3 and all(isinstance(x, (int, float)) for x in v)):
                raise ValueError(f"camera.{key} musí být [x,y,z].")
            out[key] = [float(x) for x in v]
    if isinstance(cam.get("formula"), str) and len(cam["formula"]) <= 300:
        out["formula"] = cam["formula"]
    if isinstance(cam.get("supersample"), int) and 1 <= cam["supersample"] <= 4:
        out["supersample"] = cam["supersample"]
    if isinstance(cam.get("render_ms"), (int, float)):
        out["render_ms"] = float(cam["render_ms"])
    # shadow (parametry kontaktniho stinu render passu) a stills (kamera
    # kazdeho stillu: elevation/azimuth/distance/center/width/height/...) -
    # jen ploche slovniky cisel / kratkych poli cisel, max 16 klicu
    if isinstance(cam.get("shadow"), dict):
        out["shadow"] = _numeric_dict(cam["shadow"], "camera.shadow")
    if isinstance(cam.get("stills"), dict):
        stills = {}
        for k, v in cam["stills"].items():
            if k not in STILL_VIEWS:
                raise ValueError(f"camera.stills.{k}: neznámý still.")
            if not isinstance(v, dict):
                raise ValueError(f"camera.stills.{k} musí být objekt.")
            stills[k] = _numeric_dict(v, f"camera.stills.{k}")
        out["stills"] = stills
    return out


def _numeric_dict(d, label):
    if len(d) > 16:
        raise ValueError(f"{label}: příliš mnoho klíčů.")
    out = {}
    for k, v in d.items():
        if not (isinstance(k, str) and re.match(r"^[a-z_][a-z0-9_]{0,31}$", k)):
            raise ValueError(f"{label}: neplatný klíč.")
        if isinstance(v, bool):
            raise ValueError(f"{label}.{k} musí být číslo nebo pole čísel.")
        if isinstance(v, (int, float)):
            out[k] = float(v)
        elif isinstance(v, list) and 1 <= len(v) <= 4 and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in v):
            out[k] = [float(x) for x in v]
        else:
            raise ValueError(f"{label}.{k} musí být číslo nebo pole čísel.")
    return out


def _read_batch_json(shop_product_id, batch, name):
    path = os.path.join(_batch_dir(shop_product_id, batch), name)
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def _write_batch_json(shop_product_id, batch, name, data):
    with open(os.path.join(_batch_dir(shop_product_id, batch), name), "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1)


def _product_slug(cur, shop_product_id):
    cur.execute("SELECT slug, name FROM shop_products WHERE id=%s", (shop_product_id,))
    row = cur.fetchone() or {}
    slug = _slugify(row.get("slug") or "")
    if not slug or slug == "kategorie":  # _slugify fallback pro prazdny vstup
        slug = f"product-{shop_product_id}"
    return slug, row.get("name") or ""


def _canonical_abs(rel):
    """Absolutni cesta kanonickeho souboru z canonical.json. `rel` pochazi
    ze souboru na disku (ne z DB), proto se pred kazdym mazanim overuje:
    musi zacinat `<CANONICAL_SUBDIR>/` a realpath musi lezet uvnitr
    CANONICAL_DIR - jinak warning do logu a None (bot3 c, 2026-09-02)."""
    if not isinstance(rel, str) or not rel.startswith(CANONICAL_SUBDIR + "/"):
        app.logger.warning("turntable: kanonicka cesta mimo %s/ ignorovana: %r", CANONICAL_SUBDIR, rel)
        return None
    root = os.path.realpath(CANONICAL_DIR)
    abs_path = os.path.realpath(os.path.join(UPLOAD_DIR, rel))
    if not abs_path.startswith(root + os.sep):
        app.logger.warning("turntable: kanonicka cesta vede mimo %s, ignorovana: %r", root, rel)
        return None
    return abs_path


def _remove_canonical(rel):
    """Smaze jeden kanonicky soubor (jen pres _canonical_abs). Chybejici
    soubor neni chyba; jina OSError jen warning. Vraci True, kdyz smazal."""
    abs_path = _canonical_abs(rel)
    if not abs_path:
        return False
    try:
        os.remove(abs_path)
        return True
    except FileNotFoundError:
        return False
    except OSError as e:
        app.logger.warning("turntable: nelze smazat kanonicky soubor %s: %s", rel, e)
        return False


def _rmdir_canonical_dirs(rels):
    """Uklidi PRAZDNE slug adresare kanonickych souboru (po smazani
    produktu / zmene slugu). Nikdy nesaha na CANONICAL_DIR samotny."""
    root = os.path.realpath(CANONICAL_DIR)
    dirs = {os.path.dirname(a) for a in (_canonical_abs(r) for r in rels) if a}
    for d in dirs - {root}:
        try:
            os.rmdir(d)
        except OSError:
            pass


def _na_kanonicky_pomer(img, cil_w, cil_h):
    """Ctvercovy snimek prstence -> kanonicky pomer stran BEZ ztraty obsahu.

    OREZ NA VYSKU BY SESTAVU URIZNUL. Zmereno 2026-09-11 na skutecnem
    snimku prstence (sestava 333, e0/a090, 2048x2048): objekt vcetne stinu
    je 1584 px vysoky, kdezto orez na 4:3 ze ctverce 2048 dava jen 1536 -
    dole by zmizelo 56 px regalu. Kamera prstence je totiz nastavena tak,
    aby se sestava vesla do CTVERCE z nejhorsiho uhlu cele otocky, takze
    svisle zabira skoro cely ram a neni kde brat.

    Rozsiruje se proto do STRAN. Pozadi je ciste SVISLY prechod (overeno na
    temze snimku: leva a prava hrana se v zadnem radku nelisi vic nez o
    4/255, prumerne 0.8), takze dopocitane pruhy vznikne roztazenim krajnich
    sloupcu - vizualne nerozeznatelne od skutecneho renderu a hlavne se
    neztrati ani pixel sestavy.

    Kdyby byl cilovy pomer UZSI nez ctverec, orezava se na sirku (tam se
    nic ztratit nemuze, sestava ma po stranach rezervu).
    """
    w, h = img.size
    cilova_sirka = round(h * cil_w / cil_h)
    if cilova_sirka <= w:
        levy = (w - cilova_sirka) // 2
        out = img.crop((levy, 0, levy + cilova_sirka, h))
    else:
        pad_l = (cilova_sirka - w) // 2
        pad_p = cilova_sirka - w - pad_l
        out = Image.new("RGB", (cilova_sirka, h))
        if pad_l:
            out.paste(img.crop((0, 0, 1, h)).resize((pad_l, h)), (0, 0))
        if pad_p:
            out.paste(img.crop((w - 1, 0, w, h)).resize((pad_p, h)), (pad_l + w, 0))
        out.paste(img, (pad_l, 0))
    if out.size != (cil_w, cil_h):
        out = out.resize((cil_w, cil_h), Image.LANCZOS)
    return out


def _write_canonical(shop_product_id, batch, frames, slug, marks=None, staged=None, front=None, assembly_id=None):
    """Kanonicke obrazky aktivni davky -> CANONICAL_DIR/<slug>/<slug>-<pohled>.jpg
    (nebo CANONICAL_DIR/<slug>/<assembly_id>/<slug>-<pohled>.jpg, viz `assembly_id` nize):
      * 4 kanonicke pohledy (hero, side, top, hero_16x9) - OREZ snimku
        prstence na cilovy pomer stran, 1024 varianta PIL LANCZOS q92.
        Ktery snimek prstence slouzi jako ktery pohled urcuje
        _canonical_ring_source() (prepsatelne v app_settings). Pohled
        "zezadu" Robert 2026-09-11 zrusil.
      * hero_1x1 - byte kopie snimku prstence HERO_RING tier 2048 a
        hero_1x1_1024 byte kopie tieru 1024 (pixelove shodne s widgetem,
        zadne PIL).
    Samostatne renderovane stills se od 2026-09-11 NEPOUZIVAJI (Robert:
    "budeme pouzivat pouze snimky z otaceni") - kdyz je klient posle,
    ulozi se, ale kanonicky obrazek z nich nevznikne.
    Zapis pres docasny soubor + os.replace, aby crawler/SSR nikdy nedostal
    rozepsany JPEG. `marks` (gallery_item_id, thumbnail_owned) se ulozi do
    canonical.json vedle {slug, files}. Vraci dict {klic: rel_path} (bez
    URL prefixu).
    `staged` (dict, bot3 d 2026-09-02): rezim pro turntable_commit - soubory
    se NEprepisuji na miste, ale zapisou vedle jako `<cil>.staged` a do
    staged["files"] se ulozi dvojice (staged_abs, final_abs) a do
    staged["by_key"] mapa klic -> staged cesta; meta jde i do
    staged["meta"]. Volajici po commitu DB zavola
    _promote_staged (os.replace na finalni nazvy), pri chybe
    _discard_staged - live kanonicke soubory se tak zmeni jen kdyz commit
    prosel. Bez `staged` (regenerate_canonical) se pise rovnou.
    `front` (bot8 2026-09-06): predni azimut TETO davky (viz komentar u
    FRONT_AZIMUTH_DEG) - kdyz neni zadan, pouzije se globalni fallback.

    `assembly_id` (bot8 2026-09-14, produkcni bug na karte 3943 - viz
    AGENTS_LOG a scripts/tmp_2026-09-13_bot8_fix_canonical_3943_344.py,
    jednorazova zachrana pred timhle skutecnym fixem): cesta zavisela
    VYHRADNE na slugu produktu, ne na sestave - kdyz jedna skladova
    karta ma navazano vic sestav/variant (`shop_product_id` sdileny),
    KAZDY commit prepsal STEJNE soubory na disku bez ohledu na to, ktera
    sestava renderovala. Zakaznikovi pak posuvnik ukazoval spravny
    popis/SKU (ten se cte z DB per assembly_id), ale render odpovidal
    poslednimu KOMUKOLI commitnutemu, ne vybrane variante. Kdyz je
    `assembly_id` zadano, kazda sestava dostane VLASTNI podadresar -
    zadna dalsi kolize mezi variantami stejne karty. `None` (vychozi)
    zachovava puvodni plochou cestu - pro naprostou vetsinu produktu
    (1 sestava = 1 karta) se nic nemeni, zadna migrace potreba."""
    front = FRONT_AZIMUTH_DEG if front is None else front
    hero_ring = (0, front)
    canonical_views = _canonical_views_for_front(front, _canonical_ring_source())
    by_key = {(f["elevation_deg"], f["azimuth_deg"], f["tier_px"]): f for f in frames}
    rel_dir = f"{slug}/{assembly_id}" if assembly_id is not None else slug
    out_dir = os.path.join(CANONICAL_DIR, rel_dir)
    os.makedirs(out_dir, exist_ok=True)
    files = {}

    def _final(key, dst):
        # cil zapisu: naostro, nebo (staged) vedle finalniho nazvu;
        # staged["by_key"][klic] = staged cesta (volajici potrebuje hero
        # jeste pred promote - kopie do galerie, thumbnail)
        if staged is None:
            return dst
        staged.setdefault("files", []).append((dst + ".staged", dst))
        staged.setdefault("by_key", {})[key] = dst + ".staged"
        return dst + ".staged"

    def _place(key, fname, write_fn, small_fn=None):
        dst = _final(key, os.path.join(out_dir, fname))
        tmp = dst + ".tmp"
        write_fn(tmp)
        os.replace(tmp, dst)
        files[key] = f"{CANONICAL_SUBDIR}/{rel_dir}/{fname}"
        # varianta 1024 px sirky ke KAZDEMU kanonickemu obrazku (bot3
        # 2026-09-02, pro srcset "1024w, 2048w" SSR hero) - stejny pomer
        # stran; bud dodany zapis (byte kopie tieru 1024 u hero_1x1), nebo
        # LANCZOS z prave zapsaneho plneho souboru
        small_name = fname[:-4] + f"-{CANONICAL_SMALL_W}.jpg"
        small_dst = _final(f"{key}_{CANONICAL_SMALL_W}", os.path.join(out_dir, small_name))
        small_tmp = small_dst + ".tmp"
        if small_fn:
            small_fn(small_tmp)
        else:
            with Image.open(dst) as im:
                im = im.convert("RGB")
                w, h = im.size
                small = im.resize((CANONICAL_SMALL_W, round(h * CANONICAL_SMALL_W / w)), Image.LANCZOS)
                small.save(small_tmp, "JPEG", quality=CANONICAL_JPEG_QUALITY, optimize=True)
        os.replace(small_tmp, small_dst)
        files[f"{key}_{CANONICAL_SMALL_W}"] = f"{CANONICAL_SUBDIR}/{rel_dir}/{small_name}"

    def _copy(src_abs):
        return lambda tmp: shutil.copyfile(src_abs, tmp)

    # Kanonicke pohledy se VZDY berou z prstence (Robert 2026-09-11:
    # "budeme pouzivat pouze snimky z otaceni"). Samostatne renderovane
    # stills se uz nepouzivaji ani kdyz je klient posle - drive mely
    # prednost, ted se ignoruji, aby vysledek nezavisel na tom, jestli je
    # zrovna nekdo nahral.
    #
    # Snimek prstence je CTVERCOVY (2048x2048), kdezto kanonicky obrazek ma
    # mit pomer stran, na ktery jsou navazani konzumenti (4:3, resp. 16:9 u
    # hero_16x9). Prepocet dela _na_kanonicky_pomer() - ROZSIRUJE do stran,
    # neorezava na vysku, protoze orez by sestavu uriznul (zmereno).
    chybi_zdroj = []
    z_prstence = 0
    for key, (suffix, elev, azim) in canonical_views.items():
        src = by_key.get((elev, azim, 2048))
        if not src:
            chybi_zdroj.append(f"{key}(e{elev}/a{azim:03d})")
            continue
        src_abs = os.path.join(UPLOAD_DIR, src["filename"])
        cil_w, cil_h = CANONICAL_ASPECT[key]
        with Image.open(src_abs) as img:
            vyrez = _na_kanonicky_pomer(img.convert("RGB"), cil_w, cil_h)
        _place(key, f"{slug}-{suffix}.jpg",
               lambda tmp, im=vyrez: im.save(tmp, "JPEG", quality=CANONICAL_JPEG_QUALITY, optimize=True))
        z_prstence += 1
    if chybi_zdroj:
        # Nemelo by nastat - commit kontroluje uplnost prstence driv. Kdyby
        # presto, je lepsi to mit videt v logu nez tise vyrobit produkt bez
        # og:image.
        print(f"turntable: davka {batch} nema v prstenci zdroj pro {', '.join(chybi_zdroj)}")
    ring_full = by_key.get(hero_ring + (2048,))
    ring_small = by_key.get(hero_ring + (CANONICAL_SMALL_W,))
    if ring_full:
        hero_suffix = canonical_views["hero"][0]
        _place("hero_1x1", f"{slug}-{hero_suffix}-1x1.jpg", _copy(os.path.join(UPLOAD_DIR, ring_full["filename"])),
               small_fn=_copy(os.path.join(UPLOAD_DIR, ring_small["filename"])) if ring_small else None)
    meta = {"slug": slug, "files": files, "canonical_z_prstence": z_prstence,
            "front_azimuth_deg": front}
    for k in ("gallery_item_id", "thumbnail_owned"):
        if marks and marks.get(k) is not None:
            meta[k] = marks[k]
    if staged is not None:
        staged["meta"] = meta
    # canonical.json davky se pise i ve staged rezimu (lezi v adresari davky,
    # pro web je videt az kdyz je davka aktivni): kdyby proces spadl mezi
    # commitem DB a _promote_staged, ma aktivni davka aspon platne URL na
    # dosavadni (stare) kanonicke soubory misto zadneho hero; .staged
    # soubory vedle nich prepise pristi commit/regenerate_canonical.
    _write_batch_json(shop_product_id, batch, "canonical.json", meta)
    return files


def _promote_staged(staged):
    """Po uspesnem commitu DB: staged kanonicke soubory atomicky prejmenovat
    na finalni nazvy (os.replace = prepis na miste, zadne okno bez hero)."""
    for tmp, dst in staged.get("files", []):
        os.replace(tmp, dst)


def _discard_staged(staged, extra_files=()):
    """Pri chybe pred/pri commitu: staged soubory (a pripadne dalsi nove
    zapsane, napr. kopie hero do galerie) smazat, live soubory zustavaji."""
    for path in [tmp for tmp, _dst in staged.get("files", [])] + list(extra_files):
        try:
            os.remove(path)
        except OSError:
            pass


def regenerate_canonical(shop_product_id, assembly_id=None):
    """Idempotentne prepise kanonicke obrazky (vc. 1024 variant) z AKTIVNI
    davky produktu - bez prerenderu, jen ze snimku prstence davky
    (od 2026-09-11; stills se uz nepouzivaji, viz _write_canonical).
    Pouziti: po zmene sady kanonickych variant (jednorazove z
    `api/venv/bin/python -c 'import app, turntable; turntable.regenerate_
    canonical(ID)'` s nactenym .env, pod www-data) nebo po zmene slugu.
    Stare soubory pod jinym slugem uklidi podle predchoziho canonical.json,
    znacky vlastnictvi galerie/thumbnailu zachova.

    `assembly_id` (bot8 2026-09-14, viz _write_canonical): kdyz je zadano,
    prepocita JEN tuhle jednu sestavu (jeji vlastni podadresar). Kdyz
    NENI zadano (puvodni chovani, zpetne kompatibilni CLI vyvolani z
    docstringu vyse), a produkt ma navazanych VIC ruznych sestav (sdilena
    karta), prepocita se KAZDA z nich zvlast (jinak by se stejnym bugem,
    ktery tahle zmena opravuje, prepsal sdileny slot jen z nahodne
    jedne) - vraci pak {assembly_id: {klic: rel_path}}. Pro produkt s
    JEDNOU sestavou (bezny pripad) vraci primo {klic: rel_path} jako
    drive, zadna zmena chovani/navratove hodnoty.
    Vraci None, kdyz produkt aktivni davku nema."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            sql = ("SELECT batch, elevation_deg, azimuth_deg, tier_px, filename, bytes, created_at, assembly_id "
                   "FROM product_turntable_frames WHERE shop_product_id=%s AND is_active=1")
            params = [shop_product_id]
            if assembly_id is not None:
                sql += " AND assembly_id=%s"
                params.append(assembly_id)
            cur.execute(sql, tuple(params))
            all_frames = cur.fetchall()
            if not all_frames:
                return None
            slug, _name = _product_slug(cur, shop_product_id)
    finally:
        conn.close()

    distinct_assemblies = sorted({f["assembly_id"] for f in all_frames}, key=lambda v: (v is None, v))
    single = assembly_id is not None or len(distinct_assemblies) <= 1

    def _regen_one(aid, frames):
        batch = frames[0]["batch"]
        prev_meta = _read_batch_json(shop_product_id, batch, "canonical.json") or {}
        prev = prev_meta.get("files") or {}
        front = prev_meta.get("front_azimuth_deg")
        if front is None:
            front = (_read_batch_json(shop_product_id, batch, "front.json") or {}).get("front_azimuth_deg", FRONT_AZIMUTH_DEG)
        # produkt s JEDNOU sestavou drzi puvodni plochou cestu (aid=None
        # -> _write_canonical), aby se ~230 bezne 1:1 produktum nezmenila
        # zadna URL bez duvodu; teprve VIC sestav na jedne karte potrebuje
        # rozliseni podadresarem.
        files = _write_canonical(shop_product_id, batch, frames, slug, marks=prev_meta, front=front,
                                  assembly_id=None if single else aid)
        stale = set(prev.values()) - set(files.values())
        for rel in stale:
            _remove_canonical(rel)
        _rmdir_canonical_dirs(stale)
        return files

    if single:
        aid = distinct_assemblies[0] if distinct_assemblies else None
        return _regen_one(aid, all_frames)

    by_assembly = {}
    for aid in distinct_assemblies:
        by_assembly[aid] = _regen_one(aid, [f for f in all_frames if f["assembly_id"] == aid])
    return by_assembly


def _prev_marks(shop_product_id, batches):
    """Znacky vlastnictvi (gallery_item_id, thumbnail_owned) z canonical.json
    predchozich davek produktu - cist PRED jejich smazanim."""
    marks = {}
    for b in batches:
        meta = _read_batch_json(shop_product_id, b, "canonical.json") or {}
        for k in ("gallery_item_id", "thumbnail_owned"):
            if meta.get(k) is not None and marks.get(k) is None:
                marks[k] = meta[k]
    return marks


def _uloz_galerijni_dlazdici(hero_abs, hero_1x1_abs, cil):
    """Hlavni (galerijni) nahled karty = JEDNOTNA DLAZDICE (ctverec, sestava stejne velka), ne surovy 4:3 hero
    (bot4 2026-09-30, Robert 2026-09-25 "PODRUHE": nahledy musi byt vsechny stejne velke a ve stejnem formatu -
    dlazdice kategorie bere prvni verejnou polozku galerie). Zdroj = cisty ctvercovy hero_1x1 (kdyz je), jinak
    hero. Kdyz post-process z jakehokoli duvodu selze, galerie nesmi zustat bez obrazku - spadne na puvodni kopii
    surove hero (jako pred 2026-09-30)."""
    zdroj = hero_1x1_abs if hero_1x1_abs and os.path.isfile(hero_1x1_abs) else hero_abs
    try:
        _dlazdice.uloz_dlazdici(zdroj, cil)
    except Exception:  # noqa: BLE001 - nahled nesmi shodit commit davky
        app.logger.exception("turntable: jednotna dlazdice selhala (%s), kopiruji surovy hero", zdroj)
        shutil.copyfile(hero_abs, cil)


def _fill_gallery_and_thumbnail(cur, shop_product_id, assembly_name, slug, hero_rel, prev_marks, hero_abs=None, hero_1x1_abs=None, disk=None):
    """Galerie + thumbnail produktu po commitu. Zasada: turntable smi
    prepsat JEN to, co sam zalozil (Robert: fotky realneho produktu maji
    prednost pred renderem):
      * galerie: existuje-li polozka zalozena turntablem (id z
        canonical.json predchozi davky, zaloha: nazev souboru s prefixem
        `product-<id>_<slug>-zepredu-`), nahradi se jeji soubor novym hero
        (nove hex jmeno = cache-bust, stary soubor smazan, radek/poradi
        zustava); jinak se hero vlozi JEN do uplne prazdne galerie;
      * thumbnail: prazdny -> nastavi se; "thumbnails/product-<id>.jpg" a
        predchozi davka ho vlastnila (thumbnail_owned) -> prepise se;
        cokoli jineho zustava.
    Vraci (gallery_added, thumbnail_set, marks, disk) - marks do
    canonical.json; disk = {"written": [abs...], "remove_after_commit":
    [abs...]} pro volajiciho: nove zapsane soubory smazat pri chybe
    transakce, stary soubor galerie smazat az PO commitu (bot3 d
    2026-09-02 - drive se mazal uvnitr transakce, po rollbacku by radek
    ukazoval na neexistujici soubor). `hero_abs` = staged cesta hero,
    kdyz kanonicke soubory jeste nejsou na finalnich nazvech. `disk` lze
    predat zvenku (plni se prubezne), aby volajici znal zapsane soubory i
    kdyz tahle funkce vyhodi vyjimku uprostred."""
    if hero_abs is None:
        hero_abs = os.path.join(UPLOAD_DIR, hero_rel) if hero_rel else None
    marks = {"gallery_item_id": None, "thumbnail_owned": False}
    if disk is None:
        disk = {"written": [], "remove_after_commit": []}
    if not hero_abs or not os.path.isfile(hero_abs):
        return False, False, marks, disk
    gallery_added = thumbnail_set = False
    prev_marks = prev_marks or {}

    # --- galerie ---
    owned = None
    if prev_marks.get("gallery_item_id"):
        cur.execute("SELECT id, filename FROM content_gallery_items WHERE id=%s AND owner_type='product' AND owner_id=%s",
                    (prev_marks["gallery_item_id"], shop_product_id))
        owned = cur.fetchone()
    if not owned:
        # zaloha pro davky bez znacky: konvence nazvu, kterou pouziva jen turntable
        prefix = f"product-{shop_product_id}_{slug}-zepredu-"
        cur.execute("SELECT id, filename FROM content_gallery_items WHERE owner_type='product' AND owner_id=%s "
                    "AND filename LIKE %s ORDER BY id LIMIT 1",
                    (shop_product_id, prefix.replace("_", "\\_") + "%"))
        owned = cur.fetchone()
    caption = (f"{assembly_name} - pohled zepředu" if assembly_name else "pohled zepředu")[:255]
    # konvence nazvu souboru podle gallery_items.py: <owner_type>-<owner_id>_<base>-<hex>.<ext>
    stored = f"product-{shop_product_id}_{slug}-zepredu-{os.urandom(4).hex()}.jpg"
    if owned:
        _uloz_galerijni_dlazdici(hero_abs, hero_1x1_abs, os.path.join(GALLERY_ITEMS_DIR, stored))
        disk["written"].append(os.path.join(GALLERY_ITEMS_DIR, stored))
        cur.execute("UPDATE content_gallery_items SET filename=%s, caption=%s WHERE id=%s", (stored, caption, owned["id"]))
        if owned["filename"] and owned["filename"] != stored:
            disk["remove_after_commit"].append(os.path.join(GALLERY_ITEMS_DIR, os.path.basename(owned["filename"])))
        marks["gallery_item_id"] = owned["id"]
        gallery_added = True
    else:
        cur.execute("SELECT 1 FROM content_gallery_items WHERE owner_type='product' AND owner_id=%s LIMIT 1", (shop_product_id,))
        if not cur.fetchone():
            _uloz_galerijni_dlazdici(hero_abs, hero_1x1_abs, os.path.join(GALLERY_ITEMS_DIR, stored))
            disk["written"].append(os.path.join(GALLERY_ITEMS_DIR, stored))
            cur.execute(
                "INSERT INTO content_gallery_items (owner_type, owner_id, filename, caption, sort_order, is_public) "
                "VALUES ('product', %s, %s, %s, 0, 1)",
                (shop_product_id, stored, caption),
            )
            marks["gallery_item_id"] = cur.lastrowid
            gallery_added = True

    # --- thumbnail ---
    cur.execute("SELECT thumbnail_file FROM shop_products WHERE id=%s", (shop_product_id,))
    row = cur.fetchone()
    thumb_name = f"product-{shop_product_id}.jpg"
    current = ((row or {}).get("thumbnail_file") or "").strip()
    if row is not None and (not current or (current == f"thumbnails/{thumb_name}" and prev_marks.get("thumbnail_owned"))):
        # Sjednocene ramovani (bot4, 2026-09-26) - JEN z cisteho ctvercoveho
        # hero_1x1 (zadny 4:3 smear z _na_kanonicky_pomer). Nalezeno bot3
        # 2026-09-26 (karta 4444): kdyz hero_1x1_abs chybi (zatim nevyjasnena
        # mezera v Vandr ingestu - viz AGENTS_LOG), normalizace na SMICHANEM
        # zdroji (hero_abs) selze stejne jako puvodni bug (smear vypada jako
        # obsah az k okraji, detekce ho neumi odlisit). Radeji bezpecny pad
        # na PUVODNI chovani (proste zmenseni, stary vzhled) nez novy kod,
        # ktery na spatnem zdroji tise vyrobi falesne "spravny" vysledek.
        if hero_1x1_abs and os.path.exists(hero_1x1_abs):
            img = _thumb_norm.normalizuj(hero_1x1_abs)
        else:
            with Image.open(hero_abs) as img:
                img = img.convert("RGB")
                img.thumbnail((1024, 768), Image.LANCZOS)
        tmp = os.path.join(KATALOG_THUMBNAIL_DIR, thumb_name + ".tmp")
        img.save(tmp, "JPEG", quality=CANONICAL_JPEG_QUALITY, optimize=True)
        os.replace(tmp, os.path.join(KATALOG_THUMBNAIL_DIR, thumb_name))
        cur.execute("UPDATE shop_products SET thumbnail_file=%s WHERE id=%s", (f"thumbnails/{thumb_name}", shop_product_id))
        marks["thumbnail_owned"] = True
        thumbnail_set = True
    elif current == f"thumbnails/{thumb_name}" and prev_marks.get("thumbnail_owned"):
        marks["thumbnail_owned"] = True
    return gallery_added, thumbnail_set, marks, disk


def _delete_batches(shop_product_id, batches, keep_canonical=()):
    """Smaze radky i adresare uvedenych davek + jejich kanonicke obrazky
    (podle canonical.json davky), krome cest v keep_canonical - ty prave
    prepsala nova aktivni davka (stejny slug => stejne nazvy). Soubory az
    PO radcich (kdyby smazani souboru selhalo, zustane jen sirotci
    adresar, ne radek ukazujici na neexistujici soubor)."""
    if not batches:
        return
    keep = set(keep_canonical)
    canon_paths = set()
    for b in batches:
        meta = _read_batch_json(shop_product_id, b, "canonical.json") or {}
        canon_paths.update((meta.get("files") or {}).values())
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            for b in batches:
                cur.execute("DELETE FROM product_turntable_frames WHERE shop_product_id=%s AND batch=%s", (shop_product_id, b))
        conn.commit()
    finally:
        conn.close()
    for b in batches:
        shutil.rmtree(_batch_dir(shop_product_id, b), ignore_errors=True)
    for rel in canon_paths - keep:
        _remove_canonical(rel)
    # prazdne adresare (produkt po posledni davce, slug po zmene slugu) uklidit
    try:
        os.rmdir(os.path.join(TURNTABLE_DIR, str(shop_product_id)))
    except OSError:
        pass
    _rmdir_canonical_dirs(canon_paths - keep)


def purge_product_files(shop_product_id):
    """Uklid disku po smazani PRODUKTU (products.py DELETE + bulk-delete,
    bot3 2026-09-02): radky product_turntable_frames uz smazal FK CASCADE,
    ale na disku zustaval <FRAMES_SUBDIR>/<pid>/ se vsemi davkami a
    kanonicke obrazky <CANONICAL_SUBDIR>/<slug>/. Kanonicke cesty se
    berou z canonical.json VSECH davek produktu (slug se mohl mezi davkami
    zmenit), proto se ctou PRED rmtree. Best-effort: chyby jen loguje,
    nikdy nevyhazuje - volat az PO uspesnem commitu DB (soubor bez radku
    je sirotek, radek bez souboru je rozbity produkt)."""
    product_dir = os.path.join(TURNTABLE_DIR, str(shop_product_id))
    if not os.path.isdir(product_dir):
        return
    try:
        batches = [b for b in os.listdir(product_dir) if BATCH_RE.match(b)]
    except OSError as e:
        app.logger.warning("turntable purge: produkt %s - nelze cist %s: %s", shop_product_id, product_dir, e)
        return
    canon_paths = set()
    for b in batches:
        meta = _read_batch_json(shop_product_id, b, "canonical.json") or {}
        canon_paths.update((meta.get("files") or {}).values())
    errors = []
    shutil.rmtree(product_dir, onerror=lambda _fn, p, exc: errors.append(f"{p}: {exc[1]}"))
    removed = sum(1 for rel in canon_paths if _remove_canonical(rel))
    _rmdir_canonical_dirs(canon_paths)  # slug adresar jen kdyz uz je prazdny
    if errors:
        app.logger.warning("turntable purge: produkt %s - %d davek, %d kanonickych souboru, CHYBY: %s",
                           shop_product_id, len(batches), removed, "; ".join(errors[:5]))
    else:
        app.logger.info("turntable purge: produkt %s - smazano %d davek + %d kanonickych souboru",
                        shop_product_id, len(batches), removed)


def _current_canonical_values(shop_product_id):
    """Cesty kanonickych souboru AKTIVNI davky produktu - pouziva se jako
    keep_canonical pri sweepu, protoze aktivni davka uz nemusi byt ta, co
    byla aktivni v okamziku, kdy se prave mazana davka deaktivovala (mezi
    tim mohl probehnout dalsi commit)."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT batch FROM product_turntable_frames WHERE shop_product_id=%s AND is_active=1 LIMIT 1",
                (shop_product_id,),
            )
            row = cur.fetchone()
    finally:
        conn.close()
    if not row:
        return set()
    meta = _read_batch_json(shop_product_id, row["batch"], "canonical.json") or {}
    return set((meta.get("files") or {}).values())


def _has_deactivated_at_column():
    """Zjisti (dotazem, ZAMERNE necachovane napevno - viz nize), jestli uz
    probehla sql/2026-09-02_turntable_deactivated_at.sql. Docasna opatrnost
    (bot3/Robert 2026-09-02): tenhle modul zavadi grace period drive, nez
    migrace smela probehnout (zablokoval ji auto-mode klasifikator, ceka na
    Robertovo schvaleni) - kdyby mezitim nekdo restartoval
    konfigurator.service z jineho duvodu (guardovany api/app.py), novy kod
    nesmi spadnout na chybejicim sloupci. Az migrace probehne, DALSI
    volani uz vrati True samo, bez restartu - proto se sloupec overuje
    znovu pri kazdem commitu/sweepu, ne jen jednou pri importu."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM information_schema.columns WHERE table_schema=DATABASE() "
                "AND table_name='product_turntable_frames' AND column_name='deactivated_at'"
            )
            return cur.fetchone() is not None
    finally:
        conn.close()


def _sweep_expired_batches(shop_product_id=None):
    """Fyzicky smaze davky, ktere jsou neaktivni A deaktivovane pred vice
    nez GRACE_HOURS hodinami (grace period - viz hlavicka modulu a
    turntable_commit). Bezpecne volat kdykoli, i bez argumentu (globalni
    sweep pro scripts/turntable_cleanup.py, budouci cron) - projde vsechny
    produkty naraz. Kanonicke soubory aktualne aktivni davky produktu se
    nikdy nesmazou (keep_canonical z _current_canonical_values, POCITANE
    ZNOVU pro kazdy produkt - viz jeji docstring). Bez sloupce
    deactivated_at (migrace jeste neprobehla) je no-op - viz
    _has_deactivated_at_column. Vraci {shop_product_id: [smazany batch, ...]}."""
    if not _has_deactivated_at_column():
        app.logger.warning(
            "turntable: _sweep_expired_batches preskoceno - chybi sloupec "
            "product_turntable_frames.deactivated_at (spust sql/2026-09-02_turntable_deactivated_at.sql)"
        )
        return {}
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            # Dve skupiny: (1) deaktivovane pred vice nez GRACE_HOURS,
            # (2) pojistka - rozpracovane davky, ktere se nikdy nestaly
            # aktivnimi (deactivated_at IS NULL) a jsou starsi nez
            # ORPHAN_DAYS dnu (opusteny upload; bot3 revize 2026-09-02).
            expired_cond = (
                "is_active=0 AND ("
                "(deactivated_at IS NOT NULL AND deactivated_at < DATE_SUB(NOW(), INTERVAL %s HOUR)) "
                "OR (deactivated_at IS NULL AND created_at < DATE_SUB(NOW(), INTERVAL %s DAY)))"
            )
            if shop_product_id is not None:
                cur.execute(
                    "SELECT DISTINCT shop_product_id, batch FROM product_turntable_frames "
                    "WHERE shop_product_id=%s AND " + expired_cond,
                    (shop_product_id, GRACE_HOURS, ORPHAN_DAYS),
                )
            else:
                cur.execute(
                    "SELECT DISTINCT shop_product_id, batch FROM product_turntable_frames WHERE " + expired_cond,
                    (GRACE_HOURS, ORPHAN_DAYS),
                )
            rows = cur.fetchall()
    finally:
        conn.close()
    by_product = {}
    for r in rows:
        by_product.setdefault(r["shop_product_id"], []).append(r["batch"])
    deleted = {}
    for pid, batches in by_product.items():
        _delete_batches(pid, batches, keep_canonical=_current_canonical_values(pid))
        deleted[pid] = batches
    return deleted


@app.post("/api/product-assemblies/<int:assembly_id>/turntable/commit")
@login_required
def turntable_commit(assembly_id):
    row, err = _load_assembly_for_user(assembly_id)
    if err:
        return err
    shop_product_id = row["shop_product_id"]
    body = request.get_json(silent=True) or {}
    batch = (body.get("batch") or "").strip()
    if not BATCH_RE.match(batch):
        return jsonify({"error": "Neplatné batch id."}), 400
    try:
        camera = _validate_camera(body.get("camera"))
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    # bot8 2026-09-06 (viz FRONT_AZIMUTH_DEG): predni azimut TETO davky -
    # ze zadosti (klient ho posila stejne jako pri uploadu), jinak z
    # front.json ulozeneho pri prvnim uploadu, jinak globalni fallback.
    front_raw = body.get("front_azimuth_deg")
    if front_raw is not None:
        try:
            front = int(front_raw) % 360
        except (TypeError, ValueError):
            return jsonify({"error": "Neplatný front_azimuth_deg."}), 400
    else:
        front = (_read_batch_json(shop_product_id, batch, "front.json") or {}).get("front_azimuth_deg", FRONT_AZIMUTH_DEG)

    payload, kod = commit_batch(assembly_id, shop_product_id, batch, camera, front,
                                current_user()["id"])
    return jsonify(payload), kod


def commit_batch(assembly_id, shop_product_id, batch, camera, front, user_id):
    """Vlastni prace commitu davky - BEZ Flasku, bez prihlaseni, bez parsovani.

    Vyclenil bot8 2026-09-11, aby davku mohl commitnout i INGEST z GPU
    (api/turntable_ingest.py). Do te doby volal /turntable/commit VYHRADNE
    webapp/scene.html, takze render na GPU skoncil jako soubory ve slozce a
    nikam se nezapsal - 40 hotovych sad a v product_turntable_frames nula
    radku. Navenek to vypadalo jako uspech (status `done`), coz je horsi nez
    chyba.

    Vraci (payload, http_kod) - volajici si z toho udela odpoved, nebo si to
    precte primo. Kontrola uplnosti davky, deaktivace starych davek i zapis
    kanonickych obrazku zustavaji beze zmeny; presunul se JEN kod, chovani ne.
    """
    azimuths_ok = _azimuths_for_front(front)

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT elevation_deg, azimuth_deg, tier_px, filename, bytes FROM product_turntable_frames "
                "WHERE shop_product_id=%s AND batch=%s",
                (shop_product_id, batch),
            )
            frames = cur.fetchall()
    finally:
        conn.close()
    have = {(f["elevation_deg"], f["azimuth_deg"], f["tier_px"]) for f in frames}
    missing = [
        f"e{e:02d}/a{a:03d}/{t}" for e in ELEVATIONS for a in azimuths_ok for t in TIERS if (e, a, t) not in have
    ]
    if missing:
        return ({
            "error": f"Dávka není kompletní - chybí {len(missing)} z {EXPECTED_FRAME_COUNT} snímků.",
            "missing": missing[:40], "missing_count": len(missing),
        }, 409)
    lost = [f["filename"] for f in frames if not os.path.isfile(os.path.join(UPLOAD_DIR, f["filename"]))]
    if lost:
        return ({"error": f"Na disku chybí {len(lost)} souborů dávky (např. {lost[0]}) - nahraj dávku znovu."}, 409)
    # Robert 2026-09-11: "budeme pouzivat pouze snimky z otaceni". Davka uz
    # NEMUSI mit samostatne vyrenderovane staticke pohledy - kanonicke
    # obrazky se orezavaji z prstence (viz _write_canonical). Do 2026-09-11
    # tu byla kontrola missing_stills, ktera davku bez nich odmitla s 409;
    # ta by ted zablokovala kazdou davku, protoze klient uz stills posilat
    # nema. stills_meta se cte dal jen kvuli poctu do reportu.
    stills_meta = _read_batch_json(shop_product_id, batch, "stills.json") or {}

    if camera is not None:
        _write_batch_json(shop_product_id, batch, "camera.json", camera)

    has_grace_column = _has_deactivated_at_column()

    # Poradi zapisu (bot3 d, 2026-09-02): kanonicke soubory se behem
    # transakce zapisou jen jako `.staged` vedle finalnich nazvu, na
    # finalni nazvy se prejmenuji (os.replace, na miste) az PO commitu; pri
    # jakekoli chybe se staged soubory + nova kopie hero v galerii smazou a
    # live soubory zustanou beze zmeny. Stary soubor galerie se maze az po
    # commitu. Thumbnail (thumbnails/product-<id>.jpg, stejny nazev) se
    # prepisuje na miste - radek na nej ukazuje pred i po, rollback tam
    # necha jen novejsi obrazek.
    staged = {"files": [], "meta": None}
    disk = {"written": [], "remove_after_commit": []}
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            slug, _product_name = _product_slug(cur, shop_product_id)
            # ⭐ OPRAVA (bot8 2026-09-11, nalezeno pri zachrane davky 334):
            # _fill_gallery_and_thumbnail nize pouzivala `row["name"]`, ale
            # `row` v teto funkci NIKDY nebyla definovana - `commit_batch`
            # ji nemela odkud dostat. Puvodne (pred vyclenenim commit_batch
            # z Flask routy, viz 173451c7) slo o radek nactenou v AUTH
            # prologu ROUTY (_load_assembly_for_user), ktery ale do
            # vycleneneho tela nikdy neprosel - zustal jen phantom nazev
            # promenne. Vsimla si toho az PRVNI REALNA davka, protoze
            # dosavadni testy (commit=False rezim, mockovany commit_batch)
            # tenhle konkretni radek nikdy nespustily. `assembly_name` chce
            # jmeno SESTAVY (viz caption "<jmeno> - pohled zepredu"), ne
            # produktu - odtud samostatny SELECT, ne recyklace _product_name.
            cur.execute("SELECT name FROM product_assemblies WHERE id=%s", (assembly_id,))
            _row = cur.fetchone()
            assembly_name = _row["name"] if _row else None
            cur.execute(
                "SELECT DISTINCT batch FROM product_turntable_frames WHERE shop_product_id=%s AND batch<>%s",
                (shop_product_id, batch),
            )
            old_batches = [r["batch"] for r in cur.fetchall()]
            # Davky, ktere byly aktivni PRED timto commitem - jedine, ktere
            # se bez sloupce deactivated_at smi fyzicky smazat (viz nize).
            # Ostatni v old_batches muzou byt ROZPRACOVANE uploady jineho
            # admina (is_active=0, jeste necommitnute) - ty se mazat nesmi
            # (bot3 revize 2026-09-02, handover #13 bod 11).
            # bot5/bot4/bot3 nalez, 2026-09-12 (produkcni bug, realny
            # zakaznicky dopad na sdilene karty jako 3943): chybel
            # assembly_id filtr - komitnuti JEDNE sestavy deaktivovalo
            # otocky VSECH sestav sdilejicich stejny shop_product_id
            # (sjednocena produktova karta). `<=>` (NULL-safe rovnost) mist
            # obycejneho `=`, protoze starsi davky maji assembly_id NULL -
            # obycejne `=` by je z filtru tise vyradilo.
            cur.execute(
                "SELECT DISTINCT batch FROM product_turntable_frames "
                "WHERE shop_product_id=%s AND batch<>%s AND is_active=1 AND (assembly_id <=> %s)",
                (shop_product_id, batch, assembly_id),
            )
            prev_active = [r["batch"] for r in cur.fetchall()]
            prev_marks = _prev_marks(shop_product_id, old_batches)
            # kanonicke obrazky (stejne nazvy jako u stare davky => po
            # commitu prepis na miste, zadne okno bez hero) - zatim staged
            canonical = _write_canonical(shop_product_id, batch, frames, slug, marks=prev_marks, staged=staged, front=front, assembly_id=assembly_id)
            staged_hero = staged.get("by_key", {}).get("hero")
            staged_hero_1x1 = staged.get("by_key", {}).get("hero_1x1")
            cur.execute(
                "UPDATE product_turntable_frames SET is_active=0 "
                "WHERE shop_product_id=%s AND is_active=1 AND (assembly_id <=> %s)",
                (shop_product_id, assembly_id),
            )
            cur.execute(
                "UPDATE product_turntable_frames SET is_active=1 WHERE shop_product_id=%s AND batch=%s",
                (shop_product_id, batch),
            )
            # Stare davky jen DEAKTIVOVAT (is_active=0 vyse) + oznacit cas -
            # fyzicke smazani az po GRACE_HOURS, viz _sweep_expired_batches
            # nize. "AND deactivated_at IS NULL" = nedokoncene pokusy z pred
            # touto zmenou (nebo davky, co uz cekaji z minula) si drzi svuj
            # puvodni cas, nezacinaji odpocet znovu. Bez sloupce (migrace
            # jeste neprobehla) se preskakuje - viz has_grace_column nize.
            # bot4, 2026-09-12/13, treti vyskyt stejneho vzoru (po
            # is_active=0 UPDATE a prev_active SELECT vyse): `old_batches`
            # zamerne ZUSTAVA neomezena na assembly_id (viz _prev_marks
            # o par radku vyse - ta musi videt VSECHNY davky produktu, ne
            # jen teto sestavy, protoze gallery_item_id "vlastnictvi" muze
            # patrit jine sestave, ktera si hero slot zabrala driv). Tenhle
            # UPDATE ale smi razitkovat deactivated_at JEN na davkach, co
            # tenhle commit OPRAVDU prave deaktivoval (viz is_active=0
            # UPDATE vyse, stejny assembly_id filtr) - bez nej si aktivni
            # davky JINYCH sestav (spravne porad is_active=1) odnesly
            # falesny deactivated_at, cimz by pri jejich skutecne
            # deaktivaci v budoucnu dostaly zkracenou/spatnou grace lhutu
            # (podminka "deactivated_at IS NULL" uz by je neprelozila).
            if old_batches and has_grace_column:
                placeholders = ",".join(["%s"] * len(old_batches))
                cur.execute(
                    f"UPDATE product_turntable_frames SET deactivated_at=NOW() "
                    f"WHERE shop_product_id=%s AND batch IN ({placeholders}) "
                    f"AND deactivated_at IS NULL AND (assembly_id <=> %s)",
                    (shop_product_id, *old_batches, assembly_id),
                )
            gallery_added, thumbnail_set, marks, disk = _fill_gallery_and_thumbnail(
                cur, shop_product_id, assembly_name, slug, canonical.get("hero"), prev_marks,
                hero_abs=staged_hero, hero_1x1_abs=staged_hero_1x1, disk=disk)
        conn.commit()
    except Exception:
        _discard_staged(staged, disk["written"])
        raise
    finally:
        conn.close()
    _promote_staged(staged)
    for path in disk["remove_after_commit"]:
        try:
            os.remove(path)
        except OSError:
            pass
    # canonical.json nove davky az ted (po commitu DB, at sedi id polozky
    # galerie) vc. znacek vlastnictvi
    meta = staged.get("meta") or {"slug": slug, "files": canonical}
    meta.update(marks)
    _write_batch_json(shop_product_id, batch, "canonical.json", meta)
    if has_grace_column:
        # Fyzicke smazani jen davek, ktere jsou neaktivni uz vice nez
        # GRACE_HOURS - stara davka prave deaktivovana vyse tak prezije az
        # do nejblizsiho dalsiho commitu (nebo scripts/turntable_cleanup.py).
        deleted_batches = _sweep_expired_batches(shop_product_id).get(shop_product_id, [])
    else:
        # Migrace jeste neprobehla (sql/2026-09-02_turntable_deactivated_at.sql)
        # - zadny grace: OKAMZITE smaz jen davky, ktere byly pred timto
        # commitem aktivni (prev_active). Rozpracovane davky (is_active=0,
        # nikdy necommitnute - typicky cizi upload prave ted) zustavaji;
        # uklidi je az _sweep_expired_batches po migraci (pojistka 7 dnu).
        # Az sloupec pribude, dalsi commit uz grace period pouzije sam, bez
        # restartu (viz _has_deactivated_at_column).
        app.logger.warning(
            "turntable: grace period preskoceno pro produkt %s - chybi sloupec "
            "product_turntable_frames.deactivated_at (spust sql/2026-09-02_turntable_deactivated_at.sql), "
            "drive aktivni davky mazu okamzite (%d), rozpracovane necham (%d)",
            shop_product_id, len(prev_active), len(old_batches) - len(prev_active),
        )
        _delete_batches(shop_product_id, prev_active, keep_canonical=canonical.values())
        deleted_batches = prev_active
    total_bytes = sum(f["bytes"] for f in frames)
    stills_bytes = sum(int(v.get("bytes") or 0) for v in stills_meta.values())
    log_audit(
        user_id, "turntable_commit", "shop_product", shop_product_id,
        f"sestava #{assembly_id} batch {batch}, {len(frames)} souboru, {total_bytes // 1024} kB, "
        f"stills: {len(stills_meta)} ({stills_bytes // 1024} kB), "
        f"deaktivovano davek: {len(old_batches)}, "
        f"fyzicky smazano ({'grace ' + str(GRACE_HOURS) + 'h' if has_grace_column else 'OKAMZITE, migrace chybi'}): {len(deleted_batches)}, "
        f"kanonicke: {len(canonical)} ({slug}), "
        f"galerie doplnena/nahrazena: {int(gallery_added)}, thumbnail nastaven: {int(thumbnail_set)}",
    )
    return ({
        "status": "ok", "batch": batch, "shop_product_id": shop_product_id,
        "frames": len(frames), "total_bytes": total_bytes, "stills": len(stills_meta), "stills_bytes": stills_bytes,
        "deactivated_batches": old_batches,
        "deleted_batches": deleted_batches,
        "canonical": {k: TURNTABLE_URL_PREFIX + v for k, v in canonical.items()},
        "gallery_added": gallery_added, "thumbnail_set": thumbnail_set,
    }, 200)



@app.delete("/api/product-assemblies/<int:assembly_id>/turntable")
@login_required
def turntable_delete(assembly_id):
    row, err = _load_assembly_for_user(assembly_id)
    if err:
        return err
    shop_product_id = row["shop_product_id"]
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT DISTINCT batch FROM product_turntable_frames WHERE shop_product_id=%s", (shop_product_id,))
            batches = [r["batch"] for r in cur.fetchall()]
    finally:
        conn.close()
    _delete_batches(shop_product_id, batches)
    log_audit(current_user()["id"], "turntable_delete", "shop_product", shop_product_id, f"sestava #{assembly_id}, davek: {len(batches)}")
    return jsonify({"status": "ok", "deleted_batches": batches})


def _build_public_payload(frames, camera, canonical, front=None):
    """PRESNY KONTRAKT pro widget na strance produktu (druhy agent, 2026-09-02;
    ctvercova verze + default_azimuth bot3 tentyz den):
    Cisla NIZE JSOU JEN PRIKLAD, ne kontrakt - skutecny pocet azimutu/
    elevaci/tieru VZDY urcuje odpoved samotna (rings/frames/tiers pole), NE
    tenhle text. Tenhle priklad uz DVAKRAT zastaral, kdyz nekdo cetl "27"/
    "10" jako pevne cislo misto ilustrace - proto zamerne BEZ konkretnich
    poctu v komentarich k polim, jen tvar.
    {"available": true, "step_deg": STEP_DEG, "elevations": list(ELEVATIONS),
     "default_elevation": 0, "default_azimuth": FRONT_AZIMUTH_DEG, "aspect": [1,1],
     "batch": "...", "rendered_at": "ISO", "tiers": sorted(TIERS),
     "rings": [{"elevation": el, "frames": [{"azimuth": az, "urls": {"1024": "/...", "2048": "/..."},
                                             "bytes": {"1024": N, "2048": N}} for az in AZIMUTHS]}
               for el in ELEVATIONS],
     "hero_url": "/content-files/turntable/<slug>/<slug>-zepredu-1x1.jpg", "hero_width": 2048, "hero_height": 2048,
     "hero_srcset": "<hero_1x1_1024> 1024w, <hero_url> 2048w",
     "canonical": {"hero": url, "hero_1x1": url, "hero_16x9": url, "side": url, "top": url,
                   "hero_1024": url, "hero_1x1_1024": url, "hero_16x9_1024": url,
                   "side_1024": url, "top_1024": url}}
    ("back"/"back_1024" uz NEEXISTUJE - Robert ten pohled 2026-09-11 zrusil,
     v 270stupnove vyseci neni z ceho ho prevzit.)
    hero_url = SSR placeholder pod widgetem = byte kopie snimku prstence
    el default_elevation / az default_azimuth (widget ho prekryje beze
    skoku); canonical["hero"] atd. jsou OREZY SNIMKU PRSTENCE (4:3 / 16:9)
    pro JSON-LD/OG/galerii (bot14) - do 2026-09-11 to byly samostatne tesne
    stills, ty uz se nerenderuji (WORKFLOW.md pravidlo 29). hero_url/
    hero_srcset jsou null, kdyz kanonicke soubory chybi. `camera` navic
    (aditivni, pro fazi C - skok z nahledu do sceny; camera.stills zustava
    v odpovedi kvuli starym davkam, u novych je prazdne)."""
    by_ring = {}
    rendered_at = None
    batch = None
    for f in frames:
        batch = f["batch"]
        if rendered_at is None or f["created_at"] > rendered_at:
            rendered_at = f["created_at"]
        ring = by_ring.setdefault(f["elevation_deg"], {})
        fr = ring.setdefault(f["azimuth_deg"], {"azimuth": f["azimuth_deg"], "urls": {}, "bytes": {}})
        fr["urls"][str(f["tier_px"])] = TURNTABLE_URL_PREFIX + f["filename"]
        fr["bytes"][str(f["tier_px"])] = f["bytes"]
    rings = [
        {"elevation": e, "frames": [ring[a] for a in sorted(ring)]}
        for e, ring in sorted(by_ring.items())
    ]
    payload = {
        "available": True,
        "step_deg": STEP_DEG,
        "elevations": [r["elevation"] for r in rings],
        "default_elevation": DEFAULT_ELEVATION if DEFAULT_ELEVATION in by_ring else rings[0]["elevation"],
        "default_azimuth": front if front is not None else DEFAULT_AZIMUTH,
        "aspect": list(ASPECT),
        "batch": batch,
        "rendered_at": rendered_at.isoformat() if rendered_at else None,
        "tiers": sorted(TIERS),
        "rings": rings,
        "hero_url": canonical.get("hero_1x1"),
        "hero_width": TIERS[2048][0] if canonical.get("hero_1x1") else None,
        "hero_height": TIERS[2048][1] if canonical.get("hero_1x1") else None,
        "hero_srcset": (
            f"{canonical['hero_1x1_1024']} 1024w, {canonical['hero_1x1']} 2048w"
            if canonical.get("hero_1x1") and canonical.get("hero_1x1_1024") else None
        ),
        "canonical": canonical,
    }
    if camera:
        payload["camera"] = _verejna_kamera(camera)
    return payload


# Pole kamery, ktera smi ven. BILA LISTINA, ne mazani cernych ovci -
# kdyz nekdo do kamery pridá dalsi pole, NEUNIKNE samo od sebe.
#
# Robert 2026-09-06 rozhodl tri stupne ochrany 3D modelu: verejne jde ven
# JEN otocka, zadna geometrie. Payload ale vydaval `bbox_min`/`bbox_max`
# (presne vnejsi rozmery sestavy v mm) a `bounding_radius` (polomer obalove
# koule) - tedy presne tu informaci, kterou razitkovani na snimcich chrani.
# Kdo je ma, nepotrebuje nic odmerovat z obrazku. Nalezeno 2026-09-11.
#
# Faze C (skok z nahledu do sceny) cte z kamery VYHRADNE center, distance,
# fov a aspect - overeno ve scene.html (vetev kind === "turntable"), zadne
# jine pole se nedotkne. Bila listina ji tedy nerozbiji.
#
# POCTIVE RECENO: `distance` se pocita tak, aby se sestava vesla do zaberu,
# takze s jeji velikosti koreluje - uplne se velikost utajit neda, dokud ma
# skok do sceny fungovat. Rozdil je v tom, ze tohle je odhad, kdezto
# bbox byly presne rozmery.
VEREJNA_POLE_KAMERY = ("center", "distance", "fov", "aspect")


def _verejna_kamera(cam):
    """Kamera orezana na to, co potrebuje faze C - viz VEREJNA_POLE_KAMERY."""
    if not isinstance(cam, dict):
        return None
    return {k: cam[k] for k in VEREJNA_POLE_KAMERY if k in cam}


def turntable_public_info(cur, shop_product_id, assembly_id=None):
    """Cista funkce pro SSR produktove stranky (bot14, api/products.py ji
    importuje: `from turntable import turntable_public_info`) - vraci
    PRESNE to, co GET /api/shop/products/<id>/turntable, tj. bud
    {"available": False} nebo plny kontrakt vc. hero_url/canonical/camera.
    Nezaklada ani nezavira spojeni - dostane otevreny kurzor volajiciho.

    `assembly_id` (bot8 2026-09-10, Robert: "kdo stavi ten detail produktove
    sestavy na webu? postavit") omezi vyber na JEDNU navazanou sestavu.
    Jedna skladova karta muze mit navazanych vic sestav a kazda je jedna
    varianta - bez tohohle filtru by prepinac variant na produktove strance
    dostal vzdycky tutez (nejstarsi aktivni) davku. Bez parametru se chova
    presne jako driv, takze SSR v api/products.py se nemeni.

    bot4 nalez 2026-09-14 (produkcni bug na karte 3943): DALSI volajici
    (api/storefront_pages.py OG obrazek na listing/kategorii, 2 mista)
    volaji BEZ assembly_id - bez rozliseni pak `frames[0]` bez ORDER BY
    per-assembly vybiral NAHODNOU/nedeterministickou variantu z NEKOLIKA
    smichanych sestav najednou. Ted (bot8): kdyz assembly_id neni zadano
    A produkt ma navic aktivnich sestav, predresi se na tu s
    `product_assemblies.is_master=1` (fallback na nejmensi assembly_id,
    kdyby master nebyl nastaveny) - stejna volba, jakou uz drive delala
    produktova detail-stranka jako svou vychozi pozici posuvniku."""
    if assembly_id is None:
        cur.execute(
            "SELECT DISTINCT f.assembly_id, COALESCE(a.is_master, 0) AS is_master "
            "FROM product_turntable_frames f LEFT JOIN product_assemblies a ON a.id = f.assembly_id "
            "WHERE f.shop_product_id=%s AND f.is_active=1 AND f.assembly_id IS NOT NULL "
            "ORDER BY is_master DESC, f.assembly_id ASC LIMIT 1",
            (shop_product_id,),
        )
        _pref = cur.fetchone()
        if _pref:
            assembly_id = _pref["assembly_id"]
    sql = ("SELECT batch, elevation_deg, azimuth_deg, tier_px, filename, bytes, created_at "
           "FROM product_turntable_frames WHERE shop_product_id=%s AND is_active=1")
    params = [shop_product_id]
    if assembly_id is not None:
        sql += " AND assembly_id=%s"
        params.append(assembly_id)
    sql += " ORDER BY elevation_deg, azimuth_deg, tier_px"
    cur.execute(sql, tuple(params))
    frames = cur.fetchall()
    if not frames:
        return {"available": False}
    batch = frames[0]["batch"]
    camera = _read_batch_json(shop_product_id, batch, "camera.json")
    canon_meta = _read_batch_json(shop_product_id, batch, "canonical.json") or {}
    # jen soubory, ktere na disku opravdu jsou - SSR nesmi vystavit 404 v og:image.
    # Kanonicke nazvy jsou STABILNI (<slug>-<pohled>.jpg se pri novem commitu
    # prepise na miste, aby SSR hero nikdy nemel diru), nginx je cachuje s
    # max-age=86400 -> bez cache-busteru by prohlizec/CDN den ukazoval stary
    # render. `?v=<mtime>` (bot3 c, 2026-09-02) se zmeni pri kazdem prepsani
    # (novy commit i regenerate_canonical); vsichni konzumenti (widget
    # findFrameByUrl/heroSrcsetW, OG, JSON-LD) porovnavaji jen pathname.
    canonical = {}
    for k, rel in (canon_meta.get("files") or {}).items():
        try:
            mtime = int(os.stat(os.path.join(UPLOAD_DIR, rel)).st_mtime)
        except OSError:
            continue
        canonical[k] = f"{TURNTABLE_URL_PREFIX}{rel}?v={mtime}"
    front = canon_meta.get("front_azimuth_deg")
    return _build_public_payload(frames, camera if isinstance(camera, dict) else None, canonical, front=front)


@app.get("/api/shop/products/<int:shop_product_id>/turntable")
def turntable_public_get(shop_product_id):
    # VEREJNE (bez auth) - cte ho produktova stranka e-shopu.
    #
    # POZOR, drivejsi zneni tohohle komentare tvrdilo "nevraci nic
    # citliveho: jen URL verejne servirovanych JPEGu + geometrii kamery".
    # To NEPLATILO - "geometrie kamery" nesla `bbox_min`/`bbox_max`
    # (presne vnejsi rozmery sestavy v mm) a `bounding_radius`. Od
    # 2026-09-11 jde ven jen bila listina poli, viz _verejna_kamera().
    #
    # ?assembly=<id> vybere jednu z navazanych sestav (= jednu variantu),
    # viz turntable_public_info. Neplatna hodnota se ignoruje, aby si
    # stranka podstrcenym parametrem nemohla vynutit chybu.
    try:
        assembly_id = int(request.args["assembly"]) if request.args.get("assembly") else None
    except (TypeError, ValueError):
        assembly_id = None
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            payload = turntable_public_info(cur, shop_product_id, assembly_id)
    finally:
        conn.close()
    resp = jsonify(payload)
    resp.headers["Cache-Control"] = "no-cache"
    return resp
