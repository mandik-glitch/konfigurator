"""
Archiv otocneho nahledu na Sdileny disk (bot16, 2026-09-11; rozhrani
`archivuj_snimek` navrhl bot8; model "koren = aktualni stav" rozhodl
Robert pres bot3 po prvni ostre zkousce).

⚠️ TENHLE SOUBOR JE VYHRADNE NATIVNI VETEV (`product_assemblies`/
`technicky_ok`/`razitkovac.stav_razitek`). Vandr karty (assembly_id=None)
maji VLASTNI gate v samostatnem `vandr_turntable_archiv.py` - `archivuj_
davku()` nize na ne jen deleguje (2026-09-25, bot16/bot4, po bot3 nalezu:
puvodni chybejici branch tady zpusobil, ze se Vandr davky nearchivovaly
VUBEC, tise). Nepridavej sem Vandr-specificke vetve primo - viz WORKFLOW.md
CLAUDE.md bod 6 / pravidlo 49.

Robert: "rendery originalnich schvalených orazitkovaných sestav nech se
ukládají na sdílený disk, nikoli testovací rendery .. ty se mažou." Pak
upresnil casovani: "hotove rendery je musi po jednom hned ukladat do
sdileneho disku" - a nakonec i to, KAM: "otevřu složku a vidím obrázky"
(bot3). Dve urovne (koren = zive, podslozka/<batch> = archiv) byly navrh
pro stroj, ne pro cloveka - prvni ostra davka (334, 2026-09-11) skoncila
tak, ze Robert otevrel koren a byl prazdny, presestoze davka byla
kompletne (a spravne) ulozena o uroven niz.

=== MODEL: KOREN `otocky/` JE VZDY AKTUALNI STAV ===
At obrazky prisly PRUBEZNE (archivuj_snimek) nebo DAVKOU po commitu
(archivuj_davku), konecny stav je STEJNY: v korenove slozce `otocky/`
lezi prave ty snimky, ktere jsou PRAVE TED platne. Kdyz prijde NOVA
kompletni davka, ta STARA se odsune do vlastni podslozky
`otocky/<stary_batch>/` - nezmizi, jen prestane prekazet v korenu.
Nikdy nevznikne druha kopie teho sameho snimku (fyzicky soubor se jen
PRERADI - zmenou `folder_id` v `shared_drive_files` - ne kopiruje).

Jak se pozna, CO aktualne v korenu je (a jestli se ma pri prichodu
NOVYCH dat odsunout): korenova slozka nese `manifest.json` se dvema
stavy:
  {"live": true, ...}                - probihajici render, snimky se
                                        prubezne prepisuji na miste,
                                        NEODSOUVAT (patri k tomu, co prijde)
  {"live": false, "batch": "<id>", ...} - DOKONCENA, komitnuta davka.
                                        Prijde-li NOVA davka s JINYM
                                        `batch`, tahle se cela (vc.
                                        manifestu) odsune do podslozky
                                        pojmenovane podle sveho `batch`.

=== DVE VSTUPNI BRANKY, JEDNO MISTO (koren), SDILENA EVIKACE ===
  archivuj_snimek(...) - JEDEN prave dorenderovany snimek, volat PRUBEZNE
                          (bot8, agent na GPU stanici). Pred prvnim
                          snimkem NOVEHO renderu (koren drzi DOKONCENOU
                          davku, ne "live") nejdriv evikuje tu starou pryc,
                          pak zacne psat do korene s "live": true.
                          Deterministicky nazev (e{el:+03d}_a{az:03d}.jpg),
                          druhy prichod TEHOZ uhlu (retry) PREPISE na
                          miste - to je zamerne "zive" chovani, ne
                          duplikace.
  archivuj_davku(...)   - POJISTKA po uspesnem commitu cele davky. Kdyz
                          koren uz drzi TENTO `batch` (typicky - prubezne
                          ukladani probehlo behem renderu), jen doplni,
                          co pripadne chybi, a manifest prepise na
                          "live": false. Kdyz koren drzi NECO JINEHO
                          (stara davka, nebo progresivni ukladani
                          neprobehlo vubec - napr. stary agent), NEJDRIV
                          to evikuje, pak koren naplni cerstve z
                          `product_turntable_frames`/UPLOAD_DIR.

=== KDY SE ARCHIVUJE (VZDY OBE PODMINKY SOUCASNE) ===
  1. sestava je SCHVALENA (product_assemblies.technicky_ok)
  2. razitka jsou AKTUALNI (razitkovac.stav_razitek == "aktualni",
     ne vlastni predikat - viz scripts/razitkovac.py)
`archivuj_davku` navic pocita s tim, ze davka je KOMPLETNI PRIJATA - to
NEOVERUJE tenhle modul, zarucuje to VOLAJICI tim, ze funkci vola az PO
uspesnem `turntable.commit_batch()`.
Cokoli, co nesplni (1)+(2), je TESTOVACI RENDER a nearchivuje se - obe
funkce se tise vrati se stavem "nema_narok", NENI to chyba. (bot8: jinak
by Robert videl pribyvat snimky renderu, ktery stejne skonci smazany.)

=== KRITICKE: PRUBEZNE ULOZENY SNIMEK NENI PRIJATA DAVKA ===
`archivuj_snimek` NIC NEZAPISUJE do `product_turntable_frames` a nedava
zadny stav "commit" - jen kopiruje bajty na Sdileny disk. Davka se stava
OFICIALNI (zverejnitelnou na e-shopu) VYHRADNE pres `turntable.
commit_batch()`, at uz z prohlizece nebo z `turntable_ingest.py`. Kdyby
se tahle dve pletla, prubezny snimek testovaci/nedokoncene davky by se
mohl zverejnit bez schvaleni ceste davky.

=== JAK VOLAT ===
    import turntable_archiv as ta

    # pri kazdem snimku, jak dorazi z GPU agenta (jen 2048px, jinak no-op):
    ta.archivuj_snimek(assembly_id, elevation_deg, azimuth_deg, tier_px, data)
    # `data` = SUROVE BAJTY JPEGu (agent je posila primo, zadny docasny
    # soubor na serveru v tuhle chvili nemusi existovat)

    # po uspesnem commit_batch()/commit_davku() (kod==200), jako pojistka:
    ta.archivuj_davku(assembly_id, shop_product_id, batch)

Obe vraci {"stav": ..., "popis": "clovekem citelna veta"}. Stavy:
  "ulozeno"/"archivovano"  - zapsano (muze byt 0 novych, kdyz uz vse
                              prislo pruebezne - porad "archivovano")
  "nema_narok"   - sestava neni schvalena/orazitkovana - testovaci render
  "ne_master"    - (jen archivuj_snimek) tier_px != 2048, 1024 se neuklada
  "malo_mista"   - pod MIN_VOLNE_GB volnych na /, NIC se nezapsalo
  "chyba"        - vyjimka; zalogovano, nic navic se nezapsalo

NIKDY NEVYHAZUJE VYJIMKU NAVEN. Selhani archivace NESMI shodit prijeti
snimku ani davky (bot8: kdyz se snimek neposle, render pokracuje dal a
jen se zaloguje). Kazda chyba se zaloguje (`log.exception`) a vrati jako
stav "chyba"; volajici na to nemusi (a nema) reagovat zvlast.

=== KAM SE UKLADA ===
`Produktové sestavy/<Značka>/<jméno sestavy>/otočky/` - STEJNY strom jako
uz existujici zrcadleni JSON sestav (product_assemblies.py::
zrcadli_sestavu_na_disk, SESTAVY_DRIVE_ROOT), jen o dve urovne hloub.
Zamerne NE `<kod_sestavy>` - k 2026-09-11 ma `kod_sestavy` vyplneny jen 7
ze 269 sestav (vzorove Doblo C + 6 sablon), zbylych 262 by nemelo kam.
Jmeno sestavy uz je overeny, funkcni klic - Robert podle nej hleda
existujici JSON mirror ve stejne znacce.

Uvnitr `otocky/`:
  e{el:+03d}_a{az:03d}.jpg + manifest.json   - AKTUALNI stav (viz vyse)
  <stary_batch>/                             - odsunute DRIVEJSI davky,
                                                kazda se svym manifest.json

Ukladaji se jen MASTERY (2048px). 1024px se NEARCHIVUJE - je to odvozeny
nahled (zmenseni mastera), archiv ma drzet original, ne kopii, kterou lze
kdykoli dopocitat.

=== STROP ===
Kdyz je na `/` volno pod `MIN_VOLNE_GB`, NIC SE NEZAPISE - jen hlasity
zaznam do logu. Sdileny disk je jen adresar na TEMZE filesystemu jako
databaze a vsech 6 projektu na VPS - "dochazejici misto" tu neni
kosmeticka vec. Kontroluje se PRI KAZDEM volani (i u archivuj_snimek,
tedy az 81x na davku) - je to jeden `shutil.disk_usage` syscall,
zanedbatelne.
"""
import json
import os
import shutil
from datetime import datetime

from app import app, get_conn, UPLOAD_DIR, DRIVE_FILES_DIR
from product_assemblies import SESTAVY_DRIVE_ROOT, _drive_slozka, znacka_ze_jmena, nacti_mapy_znacek
from turntable import ELEVATIONS
import razitkovac

# POZOR (nalezeno 2026-09-11 - archivace davky 334 doopravdy probehla, ale
# NEBYLO TO VIDET V ZADNEM LOGU): `logging.getLogger("turntable_archiv")` je
# holy, nikam nenapojeny logger - propaguje se do ROOT loggeru, ktery tenhle
# projekt nikde nekonfiguruje (zadny logging.basicConfig). Python vytiskne
# jen WARNING+ pres "handler posledni zachrany", takze INFO (uspech) zmizi
# VZDY a i ERROR (neuspech) je videt jen nahodou. Cely zbytek projektu proto
# dusledne pouziva `app.logger` (Flask handler, jde do journalctl -u
# konfigurator) - viz api/app.py. `log` nize je alias na nej, ne vlastni
# logger, aby uspech i neuspech byly stejne spolehlive videt.
log = app.logger

MIN_VOLNE_GB = 20
MASTER_TIER = 2048


def _bezne(fn, *a, **kw):
    """Spolecny obal: NIKDY nevyhod vyjimku ven, zaloguj a vrat stav chyba."""
    try:
        return fn(*a, **kw)
    except Exception as e:  # noqa: BLE001 - archivace nesmi shodit prijeti snimku/davky
        log.exception("%s selhalo (args=%s)", fn.__name__, a)
        return {"stav": "chyba", "popis": f"archivace selhala: {e}"}


def _gate_a_slozka(cur, assembly_id):
    """Overi (1) schvaleno (2) razitka aktualni a najde/zalozi cilovou
    slozku `otocky` pro tuhle sestavu. Vraci (chyba_dict, None, None, None, None)
    NEBO (None, znacka, jmeno_sestavy, slozka_otocky_id, stav_razitek)."""
    cur.execute("SELECT id, name, data, technicky_ok FROM product_assemblies WHERE id=%s", (assembly_id,))
    row = cur.fetchone()
    if not row:
        return {"stav": "chyba", "popis": f"sestava {assembly_id} neexistuje"}, None, None, None, None
    if not row["technicky_ok"]:
        return {"stav": "nema_narok", "popis": "sestava není technicky schválená"}, None, None, None, None
    d = json.loads(row["data"]) if isinstance(row["data"], str) else row["data"]
    stav_raz = razitkovac.stav_razitek(d)
    if stav_raz != "aktualni":
        # "neni technicky schvalena" vyse ticho zustava (testovaci rendery na
        # neschvalenych sestavach jsou bezny/ocekavany sum). TOHLE ale ne -
        # schvalena sestava se zastaralymi razitky NENI test, je to anomalie
        # (bot4 2026-09-11: gate ji propousti stejne tise jako test, coz jde
        # snadno prehlednout - build_job() to sice hlasi, ale jen do vystupu
        # jedne konkretni ulohy, ne sem, kde se to da najit napric vsemi).
        log.warning("archiv otočky PŘESKOČEN - sestava %s (%r) je schválená, "
                    "ale razítka nejsou aktuální (stav: %s)", assembly_id, row["name"], stav_raz)
        return ({"stav": "nema_narok", "popis": f"razítka nejsou aktuální (stav: {stav_raz})"},
                None, None, None, None)

    code_to_make, prefix_to_make = nacti_mapy_znacek(cur)
    znacka = znacka_ze_jmena(row["name"], code_to_make, prefix_to_make)
    if not znacka:
        return {"stav": "chyba", "popis": f"nelze odvodit značku z názvu {row['name']!r}"}, None, None, None, None
    koren = _drive_slozka(cur, SESTAVY_DRIVE_ROOT, None, None)
    slozka_znacky = _drive_slozka(cur, znacka, koren, None)
    slozka_sestavy = _drive_slozka(cur, row["name"][:255], slozka_znacky, None)
    slozka_otocky = _drive_slozka(cur, "otočky", slozka_sestavy, None)
    return None, znacka, row["name"], slozka_otocky, stav_raz


def _malo_mista():
    volne_gb = shutil.disk_usage("/").free / 1e9
    if volne_gb < MIN_VOLNE_GB:
        return volne_gb
    return None


def _ulozit_bajty(cur, folder_id, zobrazeny_nazev, data, content_type, prepsat):
    """Zapise `data` (bytes) do slozky `folder_id` pod jmenem
    `zobrazeny_nazev`. Kdyz uz tam soubor tehoz jmena je:
      prepsat=True  - PREPISE obsah na miste (stejny `stored_filename`)
      prepsat=False - NIC nedela, vrati "jiz_tam_je" (idempotence)
    Vraci "zapsano" | "prepsano" | "jiz_tam_je".

    ZNAME RIZIKO, VEDOME NEOPRAVENO (bot4 2026-09-11): SELECT->INSERT
    nize nema unikatni klic na (folder_id, filename) - mezi SELECT a
    INSERT muze v principu vlezt jiny soubezny pokus o TENTYZ uhel a
    zalozit dva radky pro jeden snimek. Dnes se to nemuze stat, protoze
    agent nema opakovani pri chybe (jeden snimek = jeden POST, bez
    retry) - kdyby nekdo retry pridal, tohle uz neplati a chce to
    resit (unikatni index, nebo INSERT ... ON DUPLICATE KEY)."""
    cur.execute("SELECT id, stored_filename FROM shared_drive_files WHERE folder_id=%s AND filename=%s",
               (folder_id, zobrazeny_nazev))
    stary = cur.fetchone()
    if stary and not prepsat:
        return "jiz_tam_je"
    ulozeny = stary["stored_filename"] if stary else f"{os.urandom(16).hex()}.{zobrazeny_nazev.rsplit('.', 1)[-1]}"
    with open(os.path.join(DRIVE_FILES_DIR, ulozeny), "wb") as fh:
        fh.write(data)
    if stary:
        cur.execute("UPDATE shared_drive_files SET size_bytes=%s WHERE id=%s", (len(data), stary["id"]))
        return "prepsano"
    cur.execute(
        "INSERT INTO shared_drive_files (folder_id, filename, stored_filename, content_type, "
        "size_bytes, uploaded_by) VALUES (%s,%s,%s,%s,%s,%s)",
        (folder_id, zobrazeny_nazev, ulozeny, content_type, len(data), None))
    return "zapsano"


def _precti_manifest(cur, folder_id):
    """Precte manifest.json dane slozky, nebo None kdyz chybi/je necitelny."""
    cur.execute("SELECT stored_filename FROM shared_drive_files WHERE folder_id=%s AND filename='manifest.json'",
               (folder_id,))
    r = cur.fetchone()
    if not r:
        return None
    try:
        with open(os.path.join(DRIVE_FILES_DIR, r["stored_filename"]), encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def _evikuj_pokud_treba(cur, slozka_otocky, novy_batch):
    """Jadro modelu "koren = aktualni stav" - sdilene OBEMA vstupnimi
    brankami. Precte manifest korenove slozky; kdyz ukazuje na DOKONCENOU
    davku RUZNOU od `novy_batch`, cely obsah korene (vcetne manifestu)
    PRERADI (UPDATE folder_id, zadne kopirovani souboru) do vlastni
    podslozky pojmenovane podle te stare davky. Po evikaci je koren
    logicky prazdny (zadny radek uz na nej neukazuje).

    Kdyz manifest chybi, ukazuje "live": true (probihajici render - patri
    k tomu, co prijde), nebo uz ukazuje na `novy_batch` samotny (uz se
    to jednou evikovalo/naplnilo), NIC se nedeje.

    `novy_batch=None` znamena "pisu live, bez znameho batch id" (volani z
    archivuj_snimek) - eviknu cokoli DOKONCENEHO, at uz ma jakekoli
    `batch`. Vraci True, kdyz k evikaci doslo."""
    manifest = _precti_manifest(cur, slozka_otocky)
    if not manifest or manifest.get("live"):
        return False
    stary_batch = manifest.get("batch")
    if not stary_batch or stary_batch == novy_batch:
        return False

    cur.execute("SELECT id FROM shared_drive_folders WHERE parent_folder_id=%s AND name=%s",
               (slozka_otocky, stary_batch))
    r = cur.fetchone()
    if r:
        stara_slozka = r["id"]
    else:
        cur.execute("INSERT INTO shared_drive_folders (parent_folder_id, name, created_by) VALUES (%s,%s,%s)",
                   (slozka_otocky, stary_batch, None))
        stara_slozka = cur.lastrowid
    cur.execute("UPDATE shared_drive_files SET folder_id=%s WHERE folder_id=%s", (stara_slozka, slozka_otocky))
    log.warning("archiv otočky: dávka %s odsunuta z kořene do podsložky (nahrazena %s)",
               stary_batch, novy_batch or "živým renderem")
    return True


# ============================================================
# PRUBEZNE, PO JEDNOM SNIMKU (bot8, GPU agent)
# ============================================================

def archivuj_snimek(assembly_id, elevation_deg, azimuth_deg, tier_px, data):
    """Ulozi JEDEN prave dorenderovany master snimek do korenove slozky
    `otocky/` - viz hlavicka modulu ("koren = aktualni stav"). Kdyz koren
    drzi DOKONCENOU davku (jinou nez ta, co prave vznika), nejdriv ji
    evikuje do podslozky, pak zacne psat live.

    Deterministicky nazev `e{el:+03d}_a{az:03d}.jpg` - druhy prichod
    TEHOZ uhlu (retry) obsah PREPISE, nevyrobi druhy soubor.
    `data` = surove bajty JPEGu."""
    return _bezne(_archivuj_snimek, assembly_id, elevation_deg, azimuth_deg, tier_px, data)


def _archivuj_snimek(assembly_id, elevation_deg, azimuth_deg, tier_px, data):
    if tier_px != MASTER_TIER:
        return {"stav": "ne_master", "popis": f"tier {tier_px}px se neukládá, jen {MASTER_TIER}px"}

    volne_gb = _malo_mista()
    if volne_gb is not None:
        log.error("archiv otočky PŘESKOČEN (snímek) - na / zbývá jen %.1f GB (limit %s GB), "
                 "assembly=%s e=%s a=%s", volne_gb, MIN_VOLNE_GB, assembly_id, elevation_deg, azimuth_deg)
        return {"stav": "malo_mista", "popis": f"jen {volne_gb:.1f} GB volných na /, nezapisuji"}

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            chyba, znacka, jmeno, slozka_otocky, stav_raz = _gate_a_slozka(cur, assembly_id)
            if chyba:
                return chyba
            _evikuj_pokud_treba(cur, slozka_otocky, None)
            zobrazeny = f"e{elevation_deg:+03d}_a{azimuth_deg:03d}.jpg"
            vysl = _ulozit_bajty(cur, slozka_otocky, zobrazeny, data, "image/jpeg", prepsat=True)
            # "live" manifest - jen kdyz jeste neexistuje/neni "live" (at se
            # nezapisuje 81x na davku, staci jednou pri prvnim snimku).
            m = _precti_manifest(cur, slozka_otocky)
            if not m or not m.get("live"):
                _ulozit_bajty(cur, slozka_otocky, "manifest.json", json.dumps({
                    "live": True, "assembly_id": assembly_id, "assembly_name": jmeno,
                    "razitka_stav": stav_raz, "master_tier_px": MASTER_TIER,
                    "zahajeno": datetime.now().isoformat(),
                }, ensure_ascii=False, indent=2).encode("utf-8"), "application/json", prepsat=True)
        conn.commit()
    finally:
        conn.close()
    return {"stav": "ulozeno", "popis": f"e{elevation_deg:+03d}/a{azimuth_deg:03d} {vysl}"}


# ============================================================
# POJISTKA PO PRIJETI CELE DAVKY
# ============================================================

def archivuj_davku(assembly_id, shop_product_id, batch):
    """Zapise VSECHNY mastery prijate davky do korenove slozky `otocky/`
    (model "koren = aktualni stav", viz hlavicka modulu) + `manifest.json`
    s `"live": false, "batch": <tenhle batch>`.

    Kdyz koren uz drzi TENTO batch (progresivni ukladani behem renderu
    probehlo), jen doplni, co pripadne chybi. Kdyz drzi NECO JINEHO
    (starsi davka, nebo se progresivne neukladalo vubec), nejdriv to
    evikuje do podslozky `otocky/<stary_batch>/`, pak koren naplni
    cerstve z `product_turntable_frames`/UPLOAD_DIR.

    `assembly_id is None` => Vandr karta (bot4/bot16, 2026-09-25) - NEMA
    `product_assemblies` radek, takze nativni gate nize by vzdy selhal
    ("sestava None neexistuje", tise, presne tenhle bug bot3 nasel). Vandr
    ma VLASTNI gate/slozku (jina pravidla: `shop_products.active` +
    `_vandr_render_otisk.render_odpovida_razitkum` misto `technicky_ok` +
    `razitkovac.stav_razitek`) v SAMOSTATNEM souboru `vandr_turntable_
    archiv.py` (Robertovo pravidlo: vanDrawee a nativni logika se nesmi
    michat v jednom souboru) - tady je jen delegace, zadna Vandr logika."""
    if assembly_id is None:
        import vandr_turntable_archiv as vta
        return vta.archivuj_davku_vandr(shop_product_id, batch)
    return _bezne(_archivuj_davku, assembly_id, shop_product_id, batch)


def _archivuj_davku(assembly_id, shop_product_id, batch):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            chyba, znacka, jmeno, slozka_otocky, stav_raz = _gate_a_slozka(cur, assembly_id)
            if chyba:
                return chyba

            volne_gb = _malo_mista()
            if volne_gb is not None:
                log.error("archiv otočky PŘESKOČEN (dávka) - na / zbývá jen %.1f GB (limit %s GB), "
                         "assembly=%s batch=%s", volne_gb, MIN_VOLNE_GB, assembly_id, batch)
                return {"stav": "malo_mista", "popis": f"jen {volne_gb:.1f} GB volných na /, nezapisuji"}

            # ---- mastery davky z DB (uz PRIJATE, po commit_batch) ----
            cur.execute(
                "SELECT elevation_deg, azimuth_deg, filename, bytes FROM product_turntable_frames "
                "WHERE shop_product_id=%s AND batch=%s AND tier_px=%s AND is_active=1",
                (shop_product_id, batch, MASTER_TIER))
            mastery = cur.fetchall()
            if not mastery:
                return {"stav": "chyba", "popis": "v DB nejsou žádné aktivní mastery pro tuhle dávku "
                                                   "(voláno před commitem?)"}

            _evikuj_pokud_treba(cur, slozka_otocky, batch)

            nove, jiz_bylo, chybi_na_disku = 0, 0, []
            for f in mastery:
                zdroj = os.path.join(UPLOAD_DIR, f["filename"])
                if not os.path.isfile(zdroj):
                    chybi_na_disku.append(zdroj)
                    continue
                zobrazeny = f"e{f['elevation_deg']:+03d}_a{f['azimuth_deg']:03d}.jpg"
                with open(zdroj, "rb") as fh:
                    data = fh.read()
                vysl = _ulozit_bajty(cur, slozka_otocky, zobrazeny, data, "image/jpeg", prepsat=False)
                if vysl == "jiz_tam_je":
                    jiz_bylo += 1
                else:
                    nove += 1

            _ulozit_bajty(cur, slozka_otocky, "manifest.json", json.dumps({
                "live": False, "assembly_id": assembly_id, "assembly_name": jmeno,
                "shop_product_id": shop_product_id, "batch": batch,
                "razitka_stav": stav_raz, "elevations": list(ELEVATIONS),
                "master_tier_px": MASTER_TIER, "pocet_snimku": len(mastery),
                "prijato": datetime.now().isoformat(),
            }, ensure_ascii=False, indent=2).encode("utf-8"), "application/json", prepsat=True)
        conn.commit()
    finally:
        conn.close()

    if chybi_na_disku:
        log.error("archiv otočky assembly=%s batch=%s: %s souborů chybí na disku (DB je zná): %s",
                  assembly_id, batch, len(chybi_na_disku), chybi_na_disku[:3])
    # `log.warning`, ne `log.info` - `app.logger` ma efektivni uroven
    # WARNING (Flask vychozi), INFO by tise zmizelo (viz AGENTS_LOG.md
    # 2026-09-11, davka 334). Bezi jen 1x na davku, nezaplavi log.
    log.warning("archiv otočky OK (dávka): assembly=%s batch=%s -> %s nových, %s už bylo, do "
               "%s/%s/%s/otočky/", assembly_id, batch, nove, jiz_bylo,
               SESTAVY_DRIVE_ROOT, znacka, jmeno)
    return {"stav": "archivovano",
            "popis": f"{nove} nově zapsáno, {jiz_bylo} už bylo"
                    + (f", {len(chybi_na_disku)} chybí na disku" if chybi_na_disku else "")}
