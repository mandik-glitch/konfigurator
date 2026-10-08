# -*- coding: utf-8 -*-
"""
Archiv otočného náhledu na Sdílený disk - VANDR VĚTEV (bot16, 2026-09-25).

SAMOSTATNÝ modul, NENÍ rozšíření `api/turntable_archiv.py` (Robert,
CLAUDE.md bod 6 + WORKFLOW.md pravidlo 49: vanDrawee logika a naše vlastní
logika se NESMÍ míchat v jednom souboru - stejný princip, jaký už používá
`api/vandr_production_overview.py` vůči `api/production_overview.py`).
`api/turntable_archiv.py` řeší jen NATIVNÍ větev (`product_assemblies.
technicky_ok` + `razitkovac.stav_razitek`) - Vandr karty (`shop_products.
sku LIKE 'VD-%'`) takový řádek NEMAJÍ VŮBEC (`assembly_id` je u nich
LEGITIMNĚ `None`, viz komentář `api/render_worker.py` u
`render_worker_tt_frame`/`turntable_ingest.ingest_frames_dir`), takže
nativní `_gate_a_slozka(cur, assembly_id=None)` na nich vždy okamžitě
selže (`SELECT ... WHERE id=NULL` → 0 řádků → "sestava None neexistuje").

**PŘESNĚ TENHLE BUG (zjistil bot3, 2026-09-25) je důvod, proč tenhle
modul vznikl:** archiv byl pro KAŽDOU Vandr kartu TICHO PŘESKAKOVÁN od
zavedení Vandr renderů (2026-09-22/23) až do dneška - `_archivuj_davku()`
vracela `{"stav": "chyba", "popis": "sestava None neexistuje"}` bez
jakéhokoli `log.warning`/`log.error`, takže to nebylo vidět ani v logu.
Ověřeno živě 2026-09-25: 37 aktivních VD-* karet mělo kompletní přijatou
dávku (`product_turntable_frames`, `assembly_id IS NULL`, `is_active=1`),
0 z nich se dostalo do `shared_drive_files` přes tenhle mechanismus.

CO JE JINÉ NEŽ NATIVNÍ VĚTEV
-----------------------------
Nemá smysl "schválení" (`technicky_ok`) - Vandr karty mají místo toho
`shop_products.active`. Nemá smysl `razitkovac.stav_razitek(product_
assemblies.data)` - Vandr geometrie je syrové GLB/FBX bez `data.parts`;
aktuálnost razítek se tu pozná jinak - `scripts/_vandr_render_otisk.py::
render_odpovida_razitkum()` (bot10, 2026-09-25, už existující sdílený
modul - POUŽITO, NENAPSÁNA čtvrtá kopie stejného testu) porovná otisk
`shop_products.vandr_render_razitka_otisk` (zapsaný `turntable_ingest.
_zapsat_render_razitka_otisk` hned po každém úspěšném commitu) se
SOUČASNÝM `vandr_razitka_json`.

CO JE STEJNÉ
------------
Model "kořen složky = aktuální stav", eviction staré dávky do podsložky,
strop volného místa, formát jmen snímků (`e{el:+03d}_a{az:03d}.jpg`) i
zápis souboru (`shared_drive_files`) - to všechno jsou GENERICKÉ utility
bez nativní rozhodovací logiky uvnitř, PRÁVEM znovupoužité přímo z
`turntable_archiv` (`_ulozit_bajty`, `_precti_manifest`,
`_evikuj_pokud_treba`, `_malo_mista`, `_bezne`, konstanty) - stejný
princip, jakým `_vandr_render_otisk.py` sdílí se svým nativním
sourozencem jen ČISTOU utilitu, ne rozhodovací logiku.

KAM SE UKLÁDÁ
--------------
`vanDrawee sestavy/<shop_product_id> - <název karty>/` - PŘESNĚ existující
konvence (Robert, ruční jednorázový import 7 složek 2026-09-23 20:58:22,
ověřeno živě ze `shared_drive_folders`: id 393-399 pod kořenem id=389),
NE nová `<Značka>/<jméno>/otočky/` konvence nativní větve - žádná
podsložka "otočky" navíc, snímky leží PŘÍMO v týhle složce, přesně jako
u těch 7 už existujících.

Těch 7 složek má navíc zvláštnost: obsahují soubory z toho ručního
importu, ale ŽÁDNÝ `manifest.json` (ruční kopie šla mimo tenhle kód).
`_evikuj_rucni_import_pokud_treba()` (níž) je při prvním skutečném zápisu
JEDNORÁZOVĚ odsune do podsložky `pred_2026-09-23_rucni_import/` (přesune,
NESMAŽE) - jinak by `_ulozit_bajty(..., prepsat=False)` u stejně
pojmenovaných úhlů tiše nechal ležet STARÝ (dnes už mimo řídicí kód,
nekontrolovaně stará) snímek a nový by se "jiz_tam_je" zahodil.

KDY SE ARCHIVUJE
-----------------
  1. karta je aktivní (`shop_products.active=1`)
  2. render odpovídá SOUČASNÝM razítkům karty (`render_odpovida_razitkum`)
Chybí-li (1) nebo (2), vrací se "nema_narok" (neschválená karta/zastaralá
dávka, BĚŽNÝ stav) - NENÍ to chyba. Když karta VŮBEC neexistuje
(neplatné `shop_product_id`), je to "chyba" a ZÁROVEŇ se zapíše
`bot_ukoly` (bot_id='bot16') - na rozdíl od "nema_narok" tohle nemůže být
běžný/očekávaný stav a přesně tenhle druh tichého selhání (gate vrátí jen
status, nikdo si nevšimne) způsobil původní bug - viz WORKFLOW.md
pravidlo 52 ("nic se neodkládá", i viditelnost chyby je součást opravy).

ZNÁMÁ SOUVISEJÍCÍ MEZERA, VĚDOMĚ NEŘEŠENA TADY: `api/render_worker.py::
render_worker_tt_frame` (progresivní zápis JEDNOHO snímku běhen renderu,
`turntable_archiv.archivuj_snimek`) volá archiv jen `if assembly_id:` -
pro Vandr (assembly_id vždy None) se progresivní ukládání NIKDY nevolá
(žádné volání `archivuj_snimek`, ani chybové). Tenhle modul řeší jen
POJISTKU PO CELÉ DÁVCE (`archivuj_davku`), která sama o sobě stačí k
tomu, aby se hotové Vandr rendery na disk dostaly (native modul to samé
prohlašuje o sobě - `archivuj_snimek` je jen průběžný náhled pro
kontrolu, ne jediná cesta ven). Živé progresivní zobrazení Vandr snímků
by vyžadovalo úpravu `api/render_worker.py` (sdílený horký kód, aktivně
používaný běžícími GPU joby) - nahlášeno bot4 (`bot_ukoly`) a bot3
(AGENTS_LOG.md), NEimplementováno tady bez koordinace s vlastníkem GPU
pipeline.

JAK VOLAT
---------
Nevolá se přímo zvenčí - `api/turntable_archiv.py::archivuj_davku()` sem
deleguje sama, když `assembly_id is None` (jediné volací místo zůstává
`turntable_ingest.py`, žádná duplicitní integrace).
"""
import json
import os
import sys
from datetime import datetime

from app import app, get_conn, UPLOAD_DIR
from product_assemblies import _drive_slozka
from turntable import ELEVATIONS
from turntable_archiv import (
    _ulozit_bajty, _evikuj_pokud_treba, _malo_mista, _bezne, MASTER_TIER,
)

# Sdileny test "sedi render se soucasnymi razitky karty?" - viz hlavicka
# modulu, PROC neni napsana ctvrta kopie stejne logiky.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import _vandr_render_otisk as vro  # noqa: E402 - musi byt az po sys.path.insert

log = app.logger

VANDR_DRIVE_ROOT = "vanDrawee sestavy"
RUCNI_IMPORT_PODSLOZKA = "pred_2026-09-23_rucni_import"


def _zapis_bot_ukol_pokud_novy(cur, text):
    """Stejny idempotentni vzor jako ostatni Vandr automaty (napr.
    2026-09-22_vandr_fbx_watcher.py::_zapis_ukol) - jeden otevreny ukol na
    dany text, aby opakovane volani (retry na kazde davce) nezaplavilo
    bot_ukoly duplicity."""
    cur.execute("SELECT id FROM bot_ukoly WHERE bot_id='bot16' AND hotovo=0 AND text=%s", (text,))
    if cur.fetchone():
        return
    cur.execute("INSERT INTO bot_ukoly (text, bot_id) VALUES (%s, 'bot16')", (text,))


def _najdi_nebo_zaloz_slozku_karty(cur, koren, shop_product_id, nazev):
    """Najde slozku karty pod korenem podle PREFIXU `"<id> - "`, NE podle
    presne shody celeho jmena (na rozdil od genericke `_drive_slozka`).
    Duvod (zjisteno zive 2026-09-25 na kartach 4903/4904): jmeno karty
    (`shop_products.name`) se muze po ZALOZENI slozky zmenit (napr.
    doplneni "(rozvor XXXX mm)" adminem/watcherem) - presne-jmenne
    hledani by pak zalozilo DRUHOU slozku pro tutez kartu a puvodni i s
    Robertovymi rucne nahranymi snimky by osirela/zustala neviditelna.
    ID v prefixu je stabilni klic (SKU/nazev nejsou), presne jako u
    ostatnich cislovanych karet v projektu (WORKFLOW.md - "SKU, ne
    nazvy"). Kdyz uz slozka existuje se STARYM jmenem, dorovna se na
    aktualni (`UPDATE ... SET name=`, soubory uvnitr se netykaji)."""
    prefix = f"{shop_product_id} - "
    cur.execute("SELECT id, name FROM shared_drive_folders WHERE parent_folder_id=%s AND name LIKE %s",
               (koren, prefix + "%"))
    cilovy_nazev = f"{shop_product_id} - {nazev}"[:255]
    for r in cur.fetchall():
        if r["name"].startswith(prefix):
            if r["name"] != cilovy_nazev:
                cur.execute("UPDATE shared_drive_folders SET name=%s WHERE id=%s", (cilovy_nazev, r["id"]))
                log.warning("archiv otočky (Vandr): složka karty %s přejmenována %r -> %r "
                           "(karta se od založení složky přejmenovala)",
                           shop_product_id, r["name"], cilovy_nazev)
            return r["id"]
    cur.execute("INSERT INTO shared_drive_folders (parent_folder_id, name, created_by) VALUES (%s,%s,%s)",
               (koren, cilovy_nazev, None))
    return cur.lastrowid


def _gate_a_slozka_vandr(cur, shop_product_id):
    """Vandr obdoba nativni `turntable_archiv._gate_a_slozka` - viz
    hlavicka modulu, proc samostatna funkce/soubor. Vraci
    (chyba_dict, None, None) NEBO (None, nazev_karty, slozka_id)."""
    cur.execute(
        "SELECT id, sku, name, active, vandr_razitka_json, vandr_render_razitka_otisk "
        "FROM shop_products WHERE id=%s", (shop_product_id,))
    row = cur.fetchone()
    if not row:
        text = (f"archiv otočky (Vandr): karta #{shop_product_id} v shop_products "
                 "neexistuje, ale dávka pro ni byla přijata (product_turntable_frames) "
                 "- zkontroluj volajícího (turntable_ingest.py/render_worker.py).")
        log.error(text)
        _zapis_bot_ukol_pokud_novy(cur, text)
        return {"stav": "chyba", "popis": f"karta {shop_product_id} neexistuje"}, None, None
    if not row["active"]:
        return {"stav": "nema_narok", "popis": "karta není aktivní"}, None, None
    if not vro.render_odpovida_razitkum(row["vandr_razitka_json"], row["vandr_render_razitka_otisk"]):
        log.warning("archiv otočky (Vandr) PŘESKOČEN - karta %s (%r) je aktivní, ale render "
                    "neodpovídá současným razítkům karty (otisk se neshoduje)",
                    shop_product_id, row["name"])
        return ({"stav": "nema_narok", "popis": "render neodpovídá aktuálním razítkům karty"},
                None, None)

    koren = _drive_slozka(cur, VANDR_DRIVE_ROOT, None, None)
    slozka = _najdi_nebo_zaloz_slozku_karty(cur, koren, shop_product_id, row["name"])
    return None, row["name"], slozka


def _evikuj_rucni_import_pokud_treba(cur, slozka):
    """Bootstrap případ SPECIFICKY pro těch 7 složek z ručního importu
    2026-09-23 20:58:22 (viz hlavička modulu) - mají soubory, ale ŽÁDNÝ
    manifest.json. `_evikuj_pokud_treba` (sdílená s nativní větví) tohle
    nepokrývá (počítá s tím, že složka BUĎ je prázdná, NEBO manifest z
    TÉHOŽ mechanismu už má). Když složka má aspoň jeden soubor, ale žádný
    manifest.json, CELÝ obsah přesune (nesmaže) do podsložky
    `pred_2026-09-23_rucni_import/` - další zápis pak píše do čistého
    kořene. Idempotentní: podruhé už složka manifest má (píše ho každý
    úspěšný zápis dávky), takže se druhé volání ihned vrátí False."""
    cur.execute("SELECT id FROM shared_drive_files WHERE folder_id=%s AND filename='manifest.json'",
               (slozka,))
    if cur.fetchone():
        return False
    cur.execute("SELECT id FROM shared_drive_files WHERE folder_id=%s LIMIT 1", (slozka,))
    if not cur.fetchone():
        return False  # prazdna slozka (nova karta), neni co evikovat

    cur.execute("SELECT id FROM shared_drive_folders WHERE parent_folder_id=%s AND name=%s",
               (slozka, RUCNI_IMPORT_PODSLOZKA))
    r = cur.fetchone()
    if r:
        stara_slozka = r["id"]
    else:
        cur.execute("INSERT INTO shared_drive_folders (parent_folder_id, name, created_by) VALUES (%s,%s,%s)",
                   (slozka, RUCNI_IMPORT_PODSLOZKA, None))
        stara_slozka = cur.lastrowid
    cur.execute("UPDATE shared_drive_files SET folder_id=%s WHERE folder_id=%s", (stara_slozka, slozka))
    log.warning("archiv otočky (Vandr): složka %s měla soubory bez manifestu (ruční import "
               "2026-09-23) - přesunuty do podsložky %s, kořen teď čistý pro aktuální dávku",
               slozka, RUCNI_IMPORT_PODSLOZKA)
    return True


def archivuj_davku_vandr(shop_product_id, batch):
    """Vandr pojistka po commitu - volaná z `turntable_archiv.
    archivuj_davku()`, když `assembly_id is None` (== Vandr karta). Stejné
    volací rozhraní jako nativní funkce (návratový tvar {"stav", "popis"}),
    jen jiný gate a jiná cílová složka - viz hlavička modulu."""
    return _bezne(_archivuj_davku_vandr, shop_product_id, batch)


def _archivuj_davku_vandr(shop_product_id, batch):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            chyba, jmeno, slozka = _gate_a_slozka_vandr(cur, shop_product_id)
            if chyba:
                # POZOR: bez tohohle commitu by `_zapis_bot_ukol_pokud_novy`
                # (volana uvnitr gate na "karta neexistuje") zustala jen v
                # transakci a `finally: conn.close()` ji tise rollbackla
                # (get_conn()/close() = rollback, viz pooled_conn_rollback_
                # trap) - presne "gate vrati status, nikdo si nevsimne"
                # bug, kteremu se tenhle bot_ukoly zapis snazi predejit.
                conn.commit()
                return chyba

            volne_gb = _malo_mista()
            if volne_gb is not None:
                log.error("archiv otočky (Vandr) PŘESKOČEN (dávka) - na / zbývá jen %.1f GB, "
                         "shop_product=%s batch=%s", volne_gb, shop_product_id, batch)
                return {"stav": "malo_mista", "popis": f"jen {volne_gb:.1f} GB volných na /, nezapisuji"}

            cur.execute(
                "SELECT elevation_deg, azimuth_deg, filename, bytes FROM product_turntable_frames "
                "WHERE shop_product_id=%s AND batch=%s AND tier_px=%s AND is_active=1 AND assembly_id IS NULL",
                (shop_product_id, batch, MASTER_TIER))
            mastery = cur.fetchall()
            if not mastery:
                return {"stav": "chyba", "popis": "v DB nejsou žádné aktivní mastery pro tuhle dávku "
                                                   "(voláno před commitem?)"}

            _evikuj_rucni_import_pokud_treba(cur, slozka)
            _evikuj_pokud_treba(cur, slozka, batch)

            nove, jiz_bylo, chybi_na_disku = 0, 0, []
            for f in mastery:
                zdroj = os.path.join(UPLOAD_DIR, f["filename"])
                if not os.path.isfile(zdroj):
                    chybi_na_disku.append(zdroj)
                    continue
                zobrazeny = f"e{f['elevation_deg']:+03d}_a{f['azimuth_deg']:03d}.jpg"
                with open(zdroj, "rb") as fh:
                    data = fh.read()
                vysl = _ulozit_bajty(cur, slozka, zobrazeny, data, "image/jpeg", prepsat=False)
                if vysl == "jiz_tam_je":
                    jiz_bylo += 1
                else:
                    nove += 1

            _ulozit_bajty(cur, slozka, "manifest.json", json.dumps({
                "live": False, "vandr": True, "shop_product_id": shop_product_id,
                "assembly_name": jmeno, "batch": batch, "elevations": list(ELEVATIONS),
                "master_tier_px": MASTER_TIER, "pocet_snimku": len(mastery),
                "prijato": datetime.now().isoformat(),
            }, ensure_ascii=False, indent=2).encode("utf-8"), "application/json", prepsat=True)
        conn.commit()
    finally:
        conn.close()

    if chybi_na_disku:
        log.error("archiv otočky (Vandr) shop_product=%s batch=%s: %s souborů chybí na disku "
                  "(DB je zná): %s", shop_product_id, batch, len(chybi_na_disku), chybi_na_disku[:3])
    log.warning("archiv otočky (Vandr) OK (dávka): shop_product=%s batch=%s -> %s nových, %s už "
               "bylo, do %s/%s/", shop_product_id, batch, nove, jiz_bylo, VANDR_DRIVE_ROOT,
               f"{shop_product_id} - {jmeno}")
    return {"stav": "archivovano",
            "popis": f"{nove} nově zapsáno, {jiz_bylo} už bylo"
                    + (f", {len(chybi_na_disku)} chybí na disku" if chybi_na_disku else "")}
