"""Automaticky razitkovac zakaznickych obrazku - Robert 2026-09-11 pres
bot3: "nech postavit automaticky razitkovac na vsechny obrazky na webu,
originaly ulozit bokem, aby se razitkovali jak stavajici obrazky tak vsechny
budouci, nech hlida script."

VZHLED (Robert po srovnani dvou nahledu, 2026-09-11): logo se OPAKUJE
DIAGONALNE PRES CELOU PLOCHU (fotobankovy vzor), NE jedno razitko v rohu -
puvodni zadani bylo bot3ovo nedorozumeni, ne Robertovo rozhodnuti. Vyber
svetla/tmava varianta znacky se pocita PRO KAZDY OTISK VE VZORU ZVLAST
(pristup "A adaptivni" z nahledu - Robert ho vybral misto pristupu
"B halo" s jednou variantou + obrysem). ZADNY prah minimalni sirky - u
plosneho vzoru zmizel problem s necitelnosti na malych obrazcich, ktery
prah resil u rohoveho razitka; nestavet ho, dokud se neukaze potreba.

PUVOD, NE CESTA (Robert + bot3, 2026-09-11, potvrzeno 3x behem stejneho
dne): 2D logo NESMI byt na fotkach, ktere nejsou nase - Dogus (628/716
produktu), 77 jinych dodavatelu (TBA, ArcaBox, EUROPLAST...), cokoli
vznikle z renderu (3D razitko uz je v geometrii, 2D navrch by bylo
duplicitni, Robert vyslovne zakazal). Filtr rozhoduje podle DAT (dogus_
stock_code/is_supplier_item na shop_products, puvod v product_usage_
images, created_role/nazev souboru u gallery-items), NE podle toho, ve
ktere slozce soubor lezi - stejny adresar muze obsahovat oboji (viz
gallery/products/, kde 1346 z 1349 souboru vypadlo).

Deleni prace (bot3 2026-09-11): bot9 (tenhle modul - motor), bot10
(napojeni na upload endpointy - VSECHNY pisou do TEHOZ manifestu), bot16
(2D podklad loga - viz LOGO_DIR nize, dorucil 2026-09-11 15:38, 8 PNG +
CTI_MNE.txt na Sdilenem disku, mistni kopie tady).

DVA VSTUPNI BODY, JEDNA SDILENA LOGIKA:
  * orazitkuj_existujici_soubor() - pro hlidaci timer. POZOR (bot10
    2026-09-11): PUT /api/gallery-items/<id> prepina is_public 0->1 PO
    nahrani - "nahraju soukrome, po revizi zverejnim" je BEZNA cesta ke
    vzniku nove verejne fotky, upload-hook ji nikdy nezachyti. U galerii
    proto timer NENI zachranna sit, je to HLAVNI cesta - viz interval v
    deploy/konfigurator-razitkovac-obrazku.timer.
  * orazitkuj_pred_ulozenim() - pro upload endpointy (bot10). Razitko
    NESMI byt podminkou ulozeni - pri jakekoli chybe volajici ulozi
    puvodni obsah sam, jak by delal bez razitkovace. Prijima bytes NEBO
    (bot10/konfigurator-74 2026-09-11, capture bez stropu velikosti)
    cestu k jiz ulozenemu docasnemu souboru - viz docstring funkce.

IDEMPOTENCE (Robertovo pravidlo 2026-09-10: pojistka tam, kde vznika
skoda, ne v planovaci): pred KAZDYM zapisem se spocita SHA256 zdrojovych
bytes a porovna s `stamped_sha256` v manifestu pro tenhle rel_path.
Sedi-li, je soubor uz orazitkovany (soubeh/opakovany beh) - nic se
nedela. Kontrola je UVNITR zapisovaci funkce, ne v CLI/timeru okolo -
druhy planovac ani rucni spusteni ji obejit nemuze.

ZALOHA JAKO DOKONCENY KROK: original se zapise, fsync, precte zpet a
overi kontrolnim souctem DRIV, nez se cokoli zapise na zivou cestu.

ATOMICKY ZAPIS: vysledek jde do docasneho souboru VE STEJNEM adresari a
teprve `os.replace()` ho nahradi na cilove ceste - zadne okno, kdy by
servirovany soubor byl castecne zapsany.
"""
import hashlib
import io
import json
import math
import os
import re
import shutil
import tempfile
from datetime import datetime

from PIL import Image, ImageStat

WEBAPP_ROOT = "/opt/konfigurator/webapp"
BACKUP_ROOT = "/opt/konfigurator/private-files/razitkovac-originaly"
LOGO_DIR = "/opt/konfigurator/scripts/razitkovac_obrazku_logo"
LOGO_LIGHT_DEFAULT = os.path.join(LOGO_DIR, "logo_watermark_light_native_996x139.png")
LOGO_DARK_DEFAULT = os.path.join(LOGO_DIR, "logo_watermark_dark_native_996x139.png")
LOGO_NATIVE_W = 996  # bot16: zadny vektor, NIKDY neupscalovat nad tohle - hlasite (vyjimka v logu), ne tichy oriznuty vysledek
TMP_PREFIX = ".razitko-tmp-"


def _over_ze_nebezi_pod_rootem():
    """Nalez bot4 pri kontrole pred prvnim ostrym behem: `os.makedirs()`
    (v _zaloha_originalu i orazitkuj_pred_ulozenim) nekontroluje, kdo beh
    spustil. `BACKUP_ROOT` zatim neexistuje - prvni spusteni pod rootem by
    zalozilo adresar, do ktereho pak `www-data` (systemd sluzba) nesmi
    zapsat. PRESNE tohle dnes stalo devadesat minut GPU renderu
    (turntable-frames/3942 vznikl stejnou chybou) a v private-files/ z toho
    zbyly dva root-vlastnene adresare ze starsiho pripadu. Pojistka patri
    sem, kde vznika skoda (Robertovo pravidlo 2026-09-10), ne do disciplíny
    toho, kdo skript spusti."""
    if os.geteuid() == 0:
        raise RuntimeError(
            "Razitkovac se nesmi spoustet pod rootem - vytvoril by soubory/"
            "adresare, do kterych zivá sluzba (www-data) nemuze zapisovat "
            "(presne takhle vznikl dnesni 90minutovy vypadek renderu). "
            "Spust pres: sudo -u www-data api/venv/bin/python3 ...")


def uklid_osirelych_tmp_souboru(zaklad=None):
    """`.razitko-tmp-*` po zabitem behu (SIGKILL mezi zapisem a
    os.replace()) - neskodi (nikdy se neserviruji, zacinaji teckou), ale
    nikdo je bez tohohle neuklidi. Volat na ZACATKU behu, ne na konci -
    konec se nemusi stat (bot4 pri kontrole SIGKILLem nasel jeden takovy
    soubor). Vraci pocet smazanych."""
    zaklad = zaklad or os.path.join(WEBAPP_ROOT, "content-files")
    smazano = 0
    for adresar, _podadresare, soubory in os.walk(zaklad):
        for jmeno in soubory:
            if jmeno.startswith(TMP_PREFIX):
                try:
                    os.remove(os.path.join(adresar, jmeno))
                    smazano += 1
                except OSError:
                    pass
    return smazano


# ---------------------------------------------------------------------
# SOUPIS - RAZITKOVAT/NIKDY/CEKA (bot9 2026-09-11, prubezne potvrzovano
# bot3 behem dne). STAMP_DIRS je jen HRUBY predfiltr podle cesty (levne
# vyradit slozky, kam obrazky vubec nepatri) - o samotnem zarazeni
# konkretniho souboru rozhoduje az je_kandidat_podle_puvodu() nize.
# ---------------------------------------------------------------------
STAMP_DIRS = [
    "content-files/gallery",           # vestavby_dodavek/realizace_stolu vlastni, gallery/products/<id> filtrovano podle produktu
    "content-files/product-usage",     # vetsina Dogus (viz filtr), male mnozstvi vlastnich zustava
    "content-files/homepage-blocks",
    "content-files/sidebar-blocks",
    "content-files/gallery-items",
    # Robert 2026-09-11 (pres bot3, po osobnim prohlednuti kontrolniho
    # listu 675 nahledu): "fotky kategorii aplikovat loga" - "orazitkovat
    # i tak", vc. rozsahleho zapeceneho "LOGIMAN" vodoznaku (bot9 ho nasel
    # ve VELKEM mnozstvi renderu napric kategoriemi, viz AGENTS_LOG) -
    # Robertovo vlastni starsi logo, prekryti novym vzorem NENI
    # prisvojeni, jen vizualni duplicita (na rozdil od vanDrawee, ktera
    # ZUSTAVA VYLOUCENA i tady, viz _je_znamy_kontaminovany_soubor nize).
    "content-files/categories",
    "content-files/kategorie-popisy",
]
# ROZHODNUTO (bylo STAMP_DIRS_CEKA_NA_ROBERTA, bot3 2026-09-11): Robert
# kontrolni list 675 nahledu prohledl a rozhodl orazitkovat vse (viz
# STAMP_DIRS vyse) - tenhle seznam uz nema co obsahovat, zustava jako
# misto pro pripadnou PRISTI cekajici slozku, ne jako mrtvy kod.
STAMP_DIRS_CEKA_NA_ROBERTA = []

NEVER_DIRS = {
    "content-files/og": (
        "CELA slozka je automaticky odvozena cache (api/app.py "
        "_og_image_1200x630_build) - nazev souboru = hash(zdrojova cesta + "
        "mtime + velikost ZDROJE). Kdyz se orazitkuje zdroj, dalsi pozadavek "
        "sam vyrobi NOVY og soubor uz ze zdroje s razitkem. Razitkovat og/ "
        "primo je zbytecne (prepise se) a nebezpecne (rozejde se s "
        "klicovacim schematem, ktere pocita hash ZE ZDROJE, ne z og/ samotne)."
    ),
    "content-files/remeslo-appky-screenshots": (
        "Screenshoty CIZICH aplikaci (bitfaktura, buildo, idoklad...) pro "
        "srovnavac cen v Remeslu - nase razitko na cizi aplikaci by vypadalo "
        "jako privlastneni, ne ochrana vlastniho obsahu."
    ),
    "content-files/turntable-frames": (
        "Rozpracovane mezivysledky otocneho nahledu, ne zakaznicky obsah - "
        "kanonicky vystup je content-files/turntable/. Muze tu byt PRAVE "
        "BEZICI ziva davka (api/turntable.py) - sahnout do ni by ji rozbilo."
    ),
    "content-files/turntable": (
        "Robert 2026-09-11: 'produktove sestavy se nebudou razitkovat "
        "duplicitne 2D to da rozum' - otocny nahled uz nese 3D razitko "
        "primo v geometrii pred renderem, 2D navrch by bylo zbytecne/rusive."
    ),
    "content-files/inquiry-forms": (
        "Produktove ILUSTRACE/ikonky pro volbu vlastnosti v poptavkovem "
        "formulari (napr. 'stul a police oddelene'), ne marketingove fotky "
        "- Robert 2026-09-11 potvrdil vynechat."
    ),
}
# katalog/ (technicke nahledy dilu pro staff-only scenu, rozhodnuto NIKDY
# bot3 2026-09-11) a webapp-urovnova UI grafika (logo-header.png,
# capture-icon-*, textures/) nejsou v zadnem seznamu vubec - nejsou to
# "obrazky na webu" v zakaznickem smyslu, jsou to funkcni prvky aplikace.

# ---------------------------------------------------------------------
# ZNAME "JIZ OZNACENE" FOTOSHOOTY (bot9 2026-09-11, Robertovo rozhodnuti
# pres bot3): "Fotky se zapecenou znackou se vynechaji... uz oznacene
# jsou, takze je nas vzor nechrani vic, jen znecisti."
#
# ZNAME OMEZENI (Robert pres bot3, vyslovne NE tise predpokladat): tohle
# je filtr PODLE JMENA SOUBORU, ne podle puvodu v datech - zadny sloupec
# v shop_gallery_images (ani jinde) neoznacuje "ze ktereho fotoshootu"
# obrazek pochazi, takze neexistuje spolehlivejsi zdroj pravdy. NOVA
# fotka ze stejneho fotoshootu s jinym jmenem tímhle filtrem PROJDE
# NEODHALENA - tohle neni budouci-proof detekce, je to jednorazovy
# vycet z rucni vizualni kontroly (10 kontaktnich archu, bot9 2026-09-11).
# Kdyz se objevi dalsi zapecena znacka mimo tenhle seznam, patri sem
# pridat, ne resit jinde.
#
# "Logiman SSE" balici/expedicni linka - velke "LOGIMAN.CZ" v obraze.
# Jen GALERIJNI soubory (bot3 2026-09-11: tenhle konkretni vycet jmen
# patri jen ke galerijnimu fotoshootu z 2026-09-11, ne vseobecne
# pravidlo). Zapecene "LOGIMAN" nalezene sirsi (categories/kategorie-
# popisy, Robert 2026-09-11 pres bot3) NENI touhle rodinou - je to
# Robertovo VLASTNI starsi logo a ma se prekryt, ne vyradit (viz
# STAMP_DIRS vyse).
ZNAMA_KONTAMINOVANA_JMENA_GALERIE_SSE = (
    "logiman-sse-",
    "balici-ergonomicke-stoly",       # vc. -2 varianty
    "baleni-pack-stations",
    "bublinkova-role-mezi-stoly",
    "expedicni-pracoviste",
    "logiman-alu45-balici-pracoviste",
    "tridici-stoly",
    "vestavba-uzitkova-atypicka",
)
# "vanDrawee" vyjimka ZRUSENA (Robert pres bot3, 2026-09-12): puvodni
# rozhodnuti "vanDrawee zustava, jak je" OBRACENO - "chce vzor i na ne,
# stejny jako na zbytek". Byvaly seznam vzoru (substring "vandrawee" +
# 10 jednotlive potvrzenych bez toho slova ve jmene) viz git historie
# tohohle souboru (commit pred timhle), kdyby se rozhodnuti niekdy
# obratilo znovu. Logiman SSE vyjimka vyse timhle NENI dotcena - je to
# samostatne rozhodnuti.
# Dva jednotlive soubory MIMO zadnou rodinu, kde razitko nedava smysl z
# jineho duvodu (Robert pres bot3 2026-09-11, zatim "drz je mimo davku"
# bez definitivniho rozhodnuti): cizi certifikat/odznak a cizi vodoznak
# treti strany (VEED.IO) - obe jsou v malych CMS blocich, ne v gallery/.
ZNAME_JEDNOTLIVE_VYLOUCENE_SOUBORY = (
    "content-files/homepage-blocks/7_6f9fd1b03683.jpg",  # Dogus Kalip certifikat
    "content-files/sidebar-blocks/1_89a37763acc7.jpg",   # VEED.IO vodoznak
)


_GALERIE_SSE_DIRY = (
    "content-files/gallery/vestavby_dodavek/",
    "content-files/gallery/realizace_stolu/",
)


def _je_znamy_kontaminovany_soubor(rel_path: str) -> bool:
    if rel_path in ZNAME_JEDNOTLIVE_VYLOUCENE_SOUBORY:
        return True
    jmeno = os.path.basename(rel_path).lower()
    if rel_path.startswith(_GALERIE_SSE_DIRY) and any(
            vzor in jmeno for vzor in ZNAMA_KONTAMINOVANA_JMENA_GALERIE_SSE):
        return True
    return False


# Soubory v gallery-items/, ktere jsou KOPIE hero snimku z otocneho
# nahledu (konvence api/turntable.py:106,
# "product-<id>_<slug>-zepredu-<hex8>.jpg") - sdileji osud "nikdy
# duplicitne" jako cela rodina turntable.
GALLERY_ITEM_TURNTABLE_RE = re.compile(r"^product-\d+_.+-zepredu-[0-9a-f]{8}\.")
# Soubory z render_gallery.py (NAZEV_PREFIX="render") - render_gallery.py
# se NEHACKUJE VUBEC (Robert 2026-09-11, stejny duvod jako u turntable/).
GALLERY_ITEM_RENDER_RE = re.compile(r"^product-\d+_render-[0-9a-f]+\.")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# ---------------------------------------------------------------------
# PUVOD - dogus/dodavatel/render (zmereno 2026-09-11, viz hlaseni bot3):
# gallery/products/ 1228 dogus + 63 jiny dodavatel + 55 nenalezeno v DB
# (konzervativne vyrazeno) z 1349; product-usage/ 257 z 263 ma aspon
# jednu vazbu na Dogus produkt (soubor sdileny mezi produkty se POCITA
# jako cizi, i kdyz visi i na vlastnim produktu - bezpecnejsi smer chyby).
# ---------------------------------------------------------------------
def _je_cizi_produkt(cur, product_id: int) -> bool:
    """True = Dogus NEBO jiny dodavatel NEBO produkt uz v DB neexistuje
    (konzervativne - nejde overit, nesahat)."""
    cur.execute(
        "SELECT dogus_stock_code IS NOT NULL AS je_dogus, is_supplier_item "
        "FROM shop_products WHERE id=%s", (product_id,))
    row = cur.fetchone()
    if not row:
        return True
    return bool(row["je_dogus"]) or bool(row["is_supplier_item"])


def _gallery_products_povoleno(cur, rel_path: str) -> bool:
    """content-files/gallery/products/<id>/... - podle vlastnika produktu."""
    m = re.match(r"^content-files/gallery/products/(\d+)/", rel_path)
    if not m:
        return False
    return not _je_cizi_produkt(cur, int(m.group(1)))


def _product_usage_povoleno(cur, rel_path: str) -> bool:
    """content-files/product-usage/<filename> - CIZI, kdyz ma i JEDINOU
    vazbu na Dogus/dodavatelsky produkt (sdileny soubor mezi produkty
    se pocita jako cizi, ne vlastni - bezpecnejsi smer chyby)."""
    filename = os.path.basename(rel_path)
    cur.execute(
        "SELECT sp.dogus_stock_code IS NOT NULL AS je_dogus, sp.is_supplier_item "
        "FROM product_usage_images ui JOIN shop_products sp ON sp.id = ui.product_id "
        "WHERE ui.filename=%s", (filename,))
    rows = cur.fetchall()
    if not rows:
        return True  # soubor uz v product_usage_images neni - nic o puvodu nerika, nechavame projit dal filtry
    return not any(r["je_dogus"] or r["is_supplier_item"] for r in rows)


def _gallery_items_povoleno(cur, rel_path: str) -> bool:
    zakl = os.path.basename(rel_path)
    if GALLERY_ITEM_TURNTABLE_RE.match(zakl) or GALLERY_ITEM_RENDER_RE.match(zakl):
        return False
    cur.execute(
        "SELECT owner_type, owner_id FROM content_gallery_items WHERE filename=%s",
        (zakl,))
    row = cur.fetchone()
    if not row:
        return True  # neni v DB (osirely soubor) - neni znamy duvod vyradit
    if row["owner_type"] == "product":
        return not _je_cizi_produkt(cur, row["owner_id"])
    # owner_type='category' - Robert primo, 2026-09-15 (pres bot3):
    # "vodoznak má být pouze na fotkach ve fotogaleriích... jen tech
    # ktere nepochazi z dogus webu" - kategorie NEJSOU fotogalerie
    # produktu, takze tady zadny puvod-signal neni potreba hledat, proste
    # NIKDY kandidat (stejne jako content-files/categories/ a kategorie-
    # popisy/ vyse). Puvodne vracelo True ("zadny puvod-signal, tak radsi
    # propustit") - spatna vychozi hodnota, viz komentar u
    # je_kandidat_podle_puvodu().
    return False


def je_kandidat_podle_puvodu(cur, rel_path: str) -> bool:
    """Hlavni rozhodovaci funkce - VOLAT VZDY, i pro soubory mimo
    STAMP_DIRS (nova mista zapisu casem pribyvaji). Vraci False i pro
    cesty, ktere vubec nepatri do zadneho razitkovaneho typu."""
    if not rel_path.startswith("content-files/"):
        return False
    if _je_znamy_kontaminovany_soubor(rel_path):
        return False
    if any(rel_path.startswith(d + "/") for d in NEVER_DIRS):
        return False
    if any(rel_path.startswith(d + "/") for d in STAMP_DIRS_CEKA_NA_ROBERTA):
        return False  # ceka na Robertovo potvrzeni - bot3 2026-09-11
    if not any(rel_path.startswith(d + "/") for d in STAMP_DIRS):
        return False

    # Robert primo, 2026-09-15 (pres bot3), po drivejsim "orazitkovat
    # VSE vc. kategorii" (2026-09-11): "vodoznak má být pouze na fotkach
    # ve fotogaleriích !!!! a to jen tech ktere nepochazi z dogus webu."
    # categories/ (nahledy kategorii) a kategorie-popisy/ (obrazky VLOZENE
    # PRIMO DO TEXTU popisu kategorie) NEJSOU fotogalerie - vzdy False,
    # BEZ OHLEDU na puvod (Dogus/vlastni - na rozdil od gallery/products
    # nize, kde puvod rozhoduje). Puvodni "zadny puvod-signal, tak radsi
    # propustit" (return True nize) byla spatna vychozi hodnota presne
    # pro tenhle pripad - 616 obrazku (89 categories/ + 527 kategorie-
    # popisy/) bylo omylem orazitkovano a obnoveno viz
    # 2026-09-15_obnov_vodoznak_vsechny_kategorie.py +
    # 2026-09-15_obnov_vodoznak_kategorie_popisy.py.
    if rel_path.startswith("content-files/categories/") or rel_path.startswith("content-files/kategorie-popisy/"):
        return False
    if rel_path.startswith("content-files/gallery/products/"):
        return _gallery_products_povoleno(cur, rel_path)
    if rel_path.startswith("content-files/product-usage/"):
        return _product_usage_povoleno(cur, rel_path)
    if rel_path.startswith("content-files/gallery-items/"):
        return _gallery_items_povoleno(cur, rel_path)
    # gallery/vestavby_dodavek, gallery/realizace_stolu, homepage-blocks,
    # sidebar-blocks - zmereno 2026-09-11 jako vlastni (shop_gallery_images.
    # source_url vzdy logiman.cz, 0x dogus), zadna dalsi tabulka k
    # dotazovani neexistuje.
    return True


# ---------------------------------------------------------------------
# KONFIGURACE - VSE parametr (Robert bude ladit, zadny commit kvuli
# kolecku). Vychozi hodnoty = to, co Robert 2026-09-11 vybral po srovnani
# nahledu (pristup "A adaptivni", hustsi, kryti 22 %); mezera_nasobek
# aktualizovana 2026-09-11 na Robertovo "lehce zmensit hustotu o 10%"
# (presny prepocet z 1,4 - viz 2026-09-11_prerazitkuj_vzorek_20_hustota.py).
# ---------------------------------------------------------------------
def nacti_konfiguraci(cur):
    cur.execute("SELECT setting_value FROM app_settings WHERE setting_key=%s",
               ("razitkovac_obrazku_config",))
    row = cur.fetchone()
    cfg = {
        "opacity": 0.22,
        "tile_scale": 0.09,        # sirka JEDNE dlazdice = tolikrat sirka obrazku
        "mezera_nasobek": 1.5016,  # rozestup mezi dlazdicemi = tolikrat sirka dlazdice
        "uhel_deg": -30,
        "posun_licheho_radku": 0.5,
        "logo_version": "bot16-2026-09-11",
    }
    if row and row["setting_value"]:
        try:
            cfg.update(json.loads(row["setting_value"]))
        except (ValueError, TypeError):
            pass
    return cfg


def _body_vzoru(w, h, tile_w, tile_h, mezera_x, mezera_y, uhel_deg, posun_licheho_radku):
    """Body (x,y) ve VYSLEDNEM obrazku, kde ma sedet stred jedne dlazdice -
    diagonalni mrizka: pocita se v otocenem (u,v) prostoru, kazdy bod se
    pak otoci zpet o uhel_deg do souradnic obrazku."""
    theta = math.radians(uhel_deg)
    cos_t, sin_t = math.cos(theta), math.sin(theta)
    krok_u = tile_w + mezera_x
    krok_v = tile_h + mezera_y
    diag = math.hypot(w, h) * 0.75
    body = []
    radek = 0
    v = -diag
    while v <= diag:
        posun = (radek % 2) * posun_licheho_radku * krok_u
        u = -diag + posun
        while u <= diag:
            x = u * cos_t - v * sin_t + w / 2
            y = u * sin_t + v * cos_t + h / 2
            if -tile_w <= x <= w + tile_w and -tile_h <= y <= h + tile_h:
                body.append((x, y))
            u += krok_u
        v += krok_v
        radek += 1
    return body


def _priprav_logo(cesta, sirka_px, opacity):
    with Image.open(cesta) as src:
        logo = src.convert("RGBA")
    if sirka_px > LOGO_NATIVE_W:
        raise ValueError(
            f"pozadovana sirka dlazdice {sirka_px}px presahuje nativni "
            f"rozliseni loga {LOGO_NATIVE_W}px (bez vektoru se neupscaluje) - "
            "sniz tile_scale nebo pockej na vektorovy podklad")
    meritko = sirka_px / logo.width
    vyska_px = max(1, round(logo.height * meritko))
    logo = logo.resize((sirka_px, vyska_px), Image.LANCZOS)
    if opacity < 1.0:
        alfa = logo.getchannel("A").point(lambda a: int(a * opacity))
        logo.putalpha(alfa)
    return logo


def _aplikuj_vzor(im: Image.Image, cfg: dict, logo_light_path: str, logo_dark_path: str) -> Image.Image:
    """Pristup 'A adaptivni' (Robert 2026-09-11): pro KAZDOU dlazdici
    zvlast se zmeri jas podkladu pod ni a vybere se svetla/tmava znacka."""
    zaklad = im.convert("RGBA")
    w, h = zaklad.size
    tile_w = round(w * cfg["tile_scale"])
    logo_l = _priprav_logo(logo_light_path, tile_w, cfg["opacity"])
    logo_d = _priprav_logo(logo_dark_path, tile_w, cfg["opacity"])
    tile_h = logo_l.height
    mezera = tile_w * cfg["mezera_nasobek"]
    uhel = cfg["uhel_deg"]

    logo_l_otoceny = logo_l.rotate(-uhel, expand=True, resample=Image.BICUBIC)
    logo_d_otoceny = logo_d.rotate(-uhel, expand=True, resample=Image.BICUBIC)

    seda = zaklad.convert("L")
    vysledek = zaklad.copy()
    for x, y in _body_vzoru(w, h, tile_w, tile_h, mezera, mezera, uhel, cfg["posun_licheho_radku"]):
        vzorek_box = (max(0, int(x - tile_w / 2)), max(0, int(y - tile_h / 2)),
                     min(w, int(x + tile_w / 2)), min(h, int(y + tile_h / 2)))
        if vzorek_box[2] <= vzorek_box[0] or vzorek_box[3] <= vzorek_box[1]:
            continue
        jas = ImageStat.Stat(seda.crop(vzorek_box)).mean[0]
        logo = logo_d_otoceny if jas >= 128 else logo_l_otoceny
        dest = (round(x - logo.width / 2), round(y - logo.height / 2))
        vysledek.alpha_composite(logo, dest=dest)
    return vysledek.convert("RGB")


def _zaloha_originalu(rel_path: str, data: bytes) -> tuple[str, str]:
    """Zapise ORIGINAL bokem, overi fsync+zpetnym cactenim+kontrolnim
    souctem. Vraci (absolutni_cesta_zalohy, sha256). Vyhodi vyjimku, kdyz
    overeni neprojde - volajici pak NESMI pokracovat k zapisu na zivou cestu."""
    backup_path = os.path.join(BACKUP_ROOT, rel_path)
    os.makedirs(os.path.dirname(backup_path), exist_ok=True)
    sha = _sha256(data)
    if os.path.exists(backup_path):
        with open(backup_path, "rb") as f:
            existujici = f.read()
        if _sha256(existujici) != sha:
            raise RuntimeError(
                f"zaloha {backup_path} uz existuje s JINYM obsahem - "
                "nesahat, rozhodnout rucne")
        return backup_path, sha
    with open(backup_path, "wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    with open(backup_path, "rb") as f:
        zpet = f.read()
    if _sha256(zpet) != sha:
        try:
            os.remove(backup_path)
        except OSError:
            pass
        raise RuntimeError(f"zaloha {backup_path} se neshoduje po zpetnem cteni")
    return backup_path, sha


def _sha256_souboru(cesta: str) -> str:
    h = hashlib.sha256()
    with open(cesta, "rb") as f:
        for kus in iter(lambda: f.read(1 << 20), b""):
            h.update(kus)
    return h.hexdigest()


def _zaloha_originalu_z_cesty(rel_path: str, zdrojova_cesta: str) -> tuple[str, str]:
    """Stejne zaruky jako `_zaloha_originalu` (fsync + zpetne cteni +
    kontrolni soucet DRIV nez zivy zapis), ale STREAMOVANE z existujiciho
    souboru na disku - pro `orazitkuj_pred_ulozenim(zdroj=<cesta>)`, viz
    duvod tam (bot10/konfigurator-74 2026-09-11: capture upload nema
    zadny strop velikosti, nucet volajiciho drzet cely obsah v jedne
    bytes promenne jen kvuli tomuto hooku by zbytecne zdvojnasobilo
    pametovy narok)."""
    backup_path = os.path.join(BACKUP_ROOT, rel_path)
    os.makedirs(os.path.dirname(backup_path), exist_ok=True)
    sha = _sha256_souboru(zdrojova_cesta)
    if os.path.exists(backup_path):
        if _sha256_souboru(backup_path) != sha:
            raise RuntimeError(
                f"zaloha {backup_path} uz existuje s JINYM obsahem - "
                "nesahat, rozhodnout rucne")
        return backup_path, sha
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(backup_path), prefix=TMP_PREFIX)
    try:
        with os.fdopen(fd, "wb") as dst, open(zdrojova_cesta, "rb") as src:
            shutil.copyfileobj(src, dst)
            dst.flush()
            os.fsync(dst.fileno())
        os.replace(tmp, backup_path)
    except Exception:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise
    if _sha256_souboru(backup_path) != sha:
        try:
            os.remove(backup_path)
        except OSError:
            pass
        raise RuntimeError(f"zaloha {backup_path} se neshoduje po zpetnem cteni")
    return backup_path, sha


def _zapis_manifest(cur, rel_path, backup_path, original_sha, stamped_sha, cfg):
    """Kazdy zapis = 'live soubor je PRAVE TED otisknuty timhle vysledkem'
    - `reverted_at` se proto VZDY vynuluje (i pri UPDATE existujiciho
    radku), jinak by po `_zapis_obnoveni()` a naslednem znovu-otisknuti
    zustal rad ek nespravne oznaceny jako 'vraceny na original' (bot3
    2026-09-11)."""
    cur.execute(
        "INSERT INTO image_watermark_manifest "
        "(rel_path, original_backup_path, original_sha256, stamped_sha256, "
        " stamped_at, reverted_at, params_json, logo_version) "
        "VALUES (%s,%s,%s,%s,%s,NULL,%s,%s) "
        "ON DUPLICATE KEY UPDATE "
        "original_backup_path=VALUES(original_backup_path), "
        "original_sha256=VALUES(original_sha256), "
        "stamped_sha256=VALUES(stamped_sha256), "
        "stamped_at=VALUES(stamped_at), reverted_at=NULL, "
        "params_json=VALUES(params_json), "
        "logo_version=VALUES(logo_version)",
        (rel_path, backup_path, original_sha, stamped_sha,
         datetime.now(), json.dumps(cfg, ensure_ascii=False), cfg["logo_version"]),
    )


def _zapis_obnoveni(cur, rel_path):
    """Volat PO fyzickem obnoveni live souboru na original (napr.
    Robertovo rozhodnuti vyradit fotoshoot z davky, 2026-09-11) - bez
    tohohle by radek v manifestu dal tvrdil (pres `stamped_sha256`), ze
    soubor je otisknuty, i kdyz na disku lezi original. Historie
    (original_sha256/stamped_sha256/params_json z posledniho otisku)
    se zachovava, jen `reverted_at` rika, ze AKTUALNE otisknuty NENI -
    bot3 2026-09-11: 'neni to historie, je to nepravdive tvrzeni o
    aktualnim stavu', pokud se nerozlisi."""
    cur.execute(
        "UPDATE image_watermark_manifest SET reverted_at=%s WHERE rel_path=%s",
        (datetime.now(), rel_path),
    )


def _jiz_orazitkovano(cur, rel_path, sha_zdroje):
    cur.execute("SELECT stamped_sha256, reverted_at FROM image_watermark_manifest WHERE rel_path=%s",
               (rel_path,))
    row = cur.fetchone()
    # reverted_at IS NOT NULL => live soubor je (podle DB) vraceny na
    # original, NIKDY se nema povazovat za "uz otisknuty" - i kdyby
    # nejaky budouci kod zkontroloval jen existenci radku, ne shodu SHA.
    return bool(row) and row["reverted_at"] is None and row["stamped_sha256"] == sha_zdroje


def _atomicky_zapis(cesta: str, data: bytes):
    adresar = os.path.dirname(cesta)
    fd, tmp = tempfile.mkstemp(dir=adresar, prefix=TMP_PREFIX)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, cesta)
    except Exception:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


def _zpracuj(im, puvodni_format, cfg):
    logo_light = cfg.get("logo_light_path", LOGO_LIGHT_DEFAULT)
    logo_dark = cfg.get("logo_dark_path", LOGO_DARK_DEFAULT)
    vysledek = _aplikuj_vzor(im, cfg, logo_light, logo_dark)
    buf = io.BytesIO()
    vysledek.save(buf, format=puvodni_format if puvodni_format in ("JPEG", "PNG") else "JPEG",
                  quality=92)
    return buf.getvalue()


def orazitkuj_existujici_soubor(cur, abs_path: str, rel_path: str, cfg=None) -> str:
    """Pro hlidaci timer - soubor uz je na zive ceste `abs_path`. Vraci
    'hotovo' | 'jiz_orazitkovano' | 'vyrazeno_puvodem'."""
    _over_ze_nebezi_pod_rootem()
    if not je_kandidat_podle_puvodu(cur, rel_path):
        return "vyrazeno_puvodem"
    cfg = cfg or nacti_konfiguraci(cur)
    with open(abs_path, "rb") as f:
        zive_bytes = f.read()
    sha_zdroje = _sha256(zive_bytes)
    if _jiz_orazitkovano(cur, rel_path, sha_zdroje):
        return "jiz_orazitkovano"

    backup_path, original_sha = _zaloha_originalu(rel_path, zive_bytes)

    with Image.open(abs_path) as im:
        im.load()
        stamped_bytes = _zpracuj(im, im.format, cfg)
    stamped_sha = _sha256(stamped_bytes)

    _atomicky_zapis(abs_path, stamped_bytes)
    with open(abs_path, "rb") as f:
        po_zapisu = f.read()
    if _sha256(po_zapisu) != stamped_sha:
        raise RuntimeError(f"{abs_path}: zapis se neshoduje po zpetnem cteni")

    _zapis_manifest(cur, rel_path, backup_path, original_sha, stamped_sha, cfg)
    return "hotovo"


def orazitkuj_pred_ulozenim(cur, zdroj, abs_path: str, rel_path: str, cfg=None) -> bool:
    """Pro upload endpointy (bot10): `zdroj` JESTE NEBYL zapsan na
    `abs_path`. `zdroj` je BUD `bytes` (puvodni rozhrani), NEBO `str` -
    cesta k JIZ ULOZENEMU docasnemu souboru (bot10/konfigurator-74
    2026-09-11: capture upload nema zadny strop velikosti - Flask
    MAX_CONTENT_LENGTH nenastaveno, nginx client_max_body_size 1G -
    nutit volajiciho drzet cely obsah v jedne bytes promenne jen kvuli
    tomuto hooku by zbytecne zdvojnasobilo pametovy narok; cesta se
    hashuje/zalohuje STREAMOVANE, nikdy se necte cela najednou).
    True = `abs_path` uz obsahuje orazitkovanou verzi, volajici NEMA
    delat svuj vlastni zapis. False (nebo vyjimka, kterou volajici
    odchyti) = nic se nezapsalo, volajici ulozi `zdroj` sam (bytes
    rovnou, cestu premisti/zkopiruje na `abs_path` sam)."""
    _over_ze_nebezi_pod_rootem()
    if not je_kandidat_podle_puvodu(cur, rel_path):
        return False
    cfg = cfg or nacti_konfiguraci(cur)

    ze_souboru = isinstance(zdroj, str)
    sha_zdroje = _sha256_souboru(zdroj) if ze_souboru else _sha256(zdroj)
    if _jiz_orazitkovano(cur, rel_path, sha_zdroje):
        return False

    if ze_souboru:
        backup_path, original_sha = _zaloha_originalu_z_cesty(rel_path, zdroj)
        with Image.open(zdroj) as im:
            im.load()
            stamped_bytes = _zpracuj(im, im.format, cfg)
    else:
        backup_path, original_sha = _zaloha_originalu(rel_path, zdroj)
        with Image.open(io.BytesIO(zdroj)) as im:
            im.load()
            stamped_bytes = _zpracuj(im, im.format, cfg)
    stamped_sha = _sha256(stamped_bytes)

    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    _atomicky_zapis(abs_path, stamped_bytes)
    with open(abs_path, "rb") as f:
        po_zapisu = f.read()
    if _sha256(po_zapisu) != stamped_sha:
        raise RuntimeError(f"{abs_path}: zapis se neshoduje po zpetnem cteni")

    _zapis_manifest(cur, rel_path, backup_path, original_sha, stamped_sha, cfg)
    return True
