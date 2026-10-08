"""Produktove sestavy (bot7, 2026-08-08) - Robert: "Vytvoř ve scéně nový
panel prakticky kopii panelu vlastní tvary... rozdílem že uložené sestavy
se budou propisovat jako e-shopové položky k prodeji." Struktura i
endpointy 1:1 kopiruji Vlastni tvary (custom_shapes/custom_shape_categories,
viz api/custom_shapes.py) - stejne validatory
(_validate_custom_shape_parts/_validate_custom_shape_relations) se
ZNOVUPOUZIVAJI beze zmeny (jsou obecne, nezavisle na cilove tabulce).
Jediny skutecny rozdil: POST rovnou zaklada NAVRH e-shopove polozky
(shop_products, active=0, bez ceny) a uklada jeji id do
product_assemblies.shop_product_id - admin ho najde v Adminu/Produkty,
dopni cenu/foto/popis/kategorii a rucne aktivuje.

Zrcadleni na Sdileny disk: PUVODNE zde vedome nebylo (na rozdil od
Vlastnich tvaru). Robert 2026-09-09 ("chci zrcadlit produktové sestavy,
které nebudou nezařazené") to zmenil - kazda sestava ma svuj JSON na
disku ve slozce podle ZNACKY vozidla, viz zrcadli_sestavu_na_disk() nize.

Vycleneno z api/app.py (bot13, 2026-09-03, PLAN_ROZDELENI_BACKENDU.md
skupina 9) - cisty presun, zadna zmena chovani/URL.

Pozn.: `_validate_custom_shape_parts`/`_validate_custom_shape_relations`
zustavaji v app.py (sdili je i api/custom_shapes.py, skupina 8) - tenhle
modul si je jen importuje. Naopak `_validate_assembly_bom_and_price`
(+ `_num_or_none`, `ASSEMBLY_BOM_MAX_ROWS`, `ASSEMBLY_PRICE_SUMMARY_FIELDS`)
pouziva jen tenhle modul, presly sem cele.
"""
import json
from datetime import datetime
import os
import re
import sys

from flask import request, jsonify

# text_labels (plovouci 3D popisky - kotovaci sipky/hodnoty apod.) zije
# jen v custom_shapes.py (viz jeho docstring "pouziva jen tenhle modul") -
# custom_shapes se importuje v app.py DRIV nez tenhle modul (skupina 8 pred
# skupinou 9), takze je v okamziku importu uz plne nacteny. bot8 2026-09-12
# (Robert: "chci pridavat mereni primo do modelu sestavy... strojirenske
# koty") - produktove sestavy tuhle funkci Vlastnich tvaru dosud nemely.
from custom_shapes import _validate_custom_shape_text_labels

# Razitkovac zije ve scripts/ (vedle turntable_job.py), protoze ho puvodne
# volal jen render. Od 2026-09-11 ho vola i tenhle modul pri zarazeni sestavy
# do slozky stromu - dovezeme ho odtud, aby existoval v JEDNE kopii. Nazev
# souboru turntable_job.py zacina cislicí, takze ten importovat nejde;
# razitkovac.py naopak ano.
_SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
if _SCRIPTS not in sys.path:
    sys.path.append(_SCRIPTS)
import razitkovac  # noqa: E402
# Kanonicky generator kod_sestavy (bot9/bot8, 2026-09-13, commit 52b30b4b) -
# jediny misto, kde se sklada retezec. Dovezeno stejnym zpusobem jako
# razitkovac vyse (existuje v JEDNE kopii).
from _kod_sestavy import sestavit_kod_sestavy  # noqa: E402

KATALOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "webapp", "katalog")

from app import (
    app,
    get_conn,
    admin_required,
    staff_required,
    require_permission,
    current_user,
    log_audit,
    fetch_katalog_parts,
    _validate_custom_shape_parts,
    _validate_custom_shape_relations,
    _product_slug_for_name,
    verejny_popisek_sestavy,
    PRODUCT_ASSEMBLY_MAX_PARTS,
    DRIVE_FILES_DIR,
)
import kolize_priznak

ASSEMBLY_BOM_MAX_ROWS = 200

# Misto montaze (Robert pres bot16, 2026-09-13, doslova: "vyber montáže
# klientem: v Praze nebo ve Slavičíně, povinný výběr.") - kdyz zakaznik
# zaskrtne montaz (viz montaz_zvolena na shop_cart_items/shop_order_items),
# MUSI navic vybrat KTERE misto. PUVODNE pevna Python konstanta - Robert
# (2026-09-13, po dotazu "jen zobrazit, nebo editovat?"): "Plně editovat"
# -> presunuto do katalogove tabulky `montaz_mista` (viz api/montaz_mista.py,
# admin CRUD + verejny GET /api/montaz-mista), tahle funkce je JEDINE misto,
# ktere na ni sahá primo (cart.py/orders.py ji volaji, nikdy netahaji SQL
# primo, aby zustalo jen jedno misto pravdy pro tvar dat).
def _montaz_mista_map(cur, jen_aktivni=True):
    sql = "SELECT klic, nazev FROM montaz_mista"
    if jen_aktivni:
        sql += " WHERE aktivni=1"
    sql += " ORDER BY sort_order, id"
    cur.execute(sql)
    return {r["klic"]: r["nazev"] for r in cur.fetchall()}

ASSEMBLY_PRICE_SUMMARY_FIELDS = (
    "count", "weight_kg", "material_czk", "cut_czk", "profile_flat_fee_czk",
    "joint_czk", "joint_count", "accessory_czk", "total_czk",
    # Montaz jako nabizena sluzba (TEXT_FILTR.md pravidlo 14a, bot8
    # 2026-09-13, commit 8f2a2bae) - NEpricita se do total_czk, jen
    # dopocitana a vystavena zvlast. Bez techto dvou poli v whitelistu
    # by _validate_assembly_bom_and_price() cokoli scena posle tise
    # zahodila (presne to se delo, viz price_summary vsech sestav
    # karty 3943 - montaz_czk vzdy None i po restartu sluzby).
    "montaz_czk", "montaz_pct_applied",
)


def _num_or_none(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _eurobox_soucet_czk(bom):
    """Soucet cen vsech euroboxu v kusovniku (Robert 2026-09-13: volba
    "bez boxů" vedle montáže - "při zatržení se odečtou boxy"). Euroboxy
    v BOM se poznaji podle nazvu radku - vzdy zacina "eurobox_" (viz
    generovani nazvu dilu ve scene.html, napr. "eurobox_400x300x220
    (produkt)"). Vraci None, kdyz sestava ZADNE euroboxy neobsahuje
    (odlisit od "obsahuje euroboxy v cene 0 Kc", coz v datech nenastava),
    aby frontend/cart mohl volbu "bez boxů" u takove sestavy vubec
    nenabidnout/ignorovat.
    """
    radky = [
        r for r in (bom or [])
        if isinstance(r, dict) and isinstance(r.get("name"), str) and r["name"].startswith("eurobox_")
    ]
    if not radky:
        return None
    return round(sum((r.get("total") or 0) for r in radky))


def _assembly_price_components(cur, assembly_id, product_id, master_price_placeholder):
    """Cenove slozky KONKRETNI varianty sestavy pro kosik/objednavku -
    Robert 2026-09-13: "vedle výběru montáže, také volbu: bez boxů".

    Overuje, ze `assembly_id` skutecne patri `product_id` (bezpecnostni
    kontrola proti cizimu/cizí kartě naroubovanemu assembly_id z requestu)
    - vraci None, kdyz nesedi/neexistuje, volajici to musi osetrit jako
    chybny vstup (400), NIKDY nepokracovat s domnenkou.

    Vraci {"base_czk", "montaz_czk", "boxy_czk", "kod_sestavy"} - stejny
    "zastupce = rucni price_czk_placeholder, jinak price_summary" princip
    jako `product_assemblies_public()._odvozene_ceny` vyse, jen pro
    interni (prihlasenou) potrebu kosiku/checkoutu, ne pro verejny JSON.
    """
    cur.execute(
        "SELECT id, data, is_master, kod_sestavy FROM product_assemblies "
        "WHERE id=%s AND shop_product_id=%s",
        (assembly_id, product_id),
    )
    r = cur.fetchone()
    if not r:
        return None
    try:
        parsed = json.loads(r["data"]) if r["data"] else {}
    except (ValueError, TypeError):
        parsed = {}
    ps = parsed.get("price_summary") or {}
    montaz = ps.get("montaz_czk")
    if r["is_master"]:
        # OPRAVA (bot5, 2026-10-01): zastupce ma montaz a boxy STEJNE jako kazda jina varianta, jen jeho CENA je
        # price_czk_placeholder karty. Tady drive stalo "montaz/boxy None" - stejny omyl jako v puvodni
        # _odvozene_ceny ve verejnem JSON (opraveno 2026-09-15). product.html ale u zastupce volby montaz/"bez boxu"
        # nabizi (cena na strance je vcetne nich) a kosik/objednavka je tise zahodily: zakaznik videl cenu s montazi,
        # do kosiku sla bez ni.
        base = master_price_placeholder
    else:
        total = ps.get("total_czk")
        base = round(total) if total is not None else None
    return {
        "base_czk": base,
        "montaz_czk": round(montaz) if montaz is not None else None,
        "boxy_czk": _eurobox_soucet_czk(parsed.get("bom")),
        "kod_sestavy": r["kod_sestavy"],
    }


# Robert 2026-08-08 ("do produktové sestavy přineseme i cenu, i kusovník,
# bude vidět v administraci všemi rolemi, nebude vidět na eshopu"): kusovnik
# + cenovy rozpis jsou POCITANE NA KLIENTOVI (viz computeAssemblyBomAndPrice
# ve scene.html - stejny zaklad jako refreshSummary()/generateSceneOffer(),
# server zadnou cenovou logiku nema, presne jako uz existujici scene_offers).
# Validace je proto jen "je to rozumny tvar dat", NE prepocet - stejny
# duveryhodnostni model uz ma scene_offers_create (viz jeho _validate_data_uri
# apod.), server veri tomu, co posle prihlaseny klient z vlastni scény.
def _validate_assembly_bom_and_price(bom_in, price_in):
    clean_bom = []
    if bom_in is not None:
        if not isinstance(bom_in, list):
            return None, None, "Neplatný formát kusovníku."
        if len(bom_in) > ASSEMBLY_BOM_MAX_ROWS:
            return None, None, f"Kusovník má příliš mnoho řádků (max {ASSEMBLY_BOM_MAX_ROWS})."
        for row in bom_in:
            if not isinstance(row, dict):
                return None, None, "Neplatný řádek kusovníku."
            name = row.get("name")
            if not isinstance(name, str) or not name.strip():
                return None, None, "Řádek kusovníku bez názvu."
            clean_bom.append({
                "name": name.strip()[:255],
                "dim": str(row.get("dim") or "-")[:100],
                "qty": int(row.get("qty")) if isinstance(row.get("qty"), (int, float)) and not isinstance(row.get("qty"), bool) else 1,
                "unit_price": _num_or_none(row.get("unit_price")),
                "total": _num_or_none(row.get("total")),
            })

    clean_price = {}
    if price_in is not None:
        if not isinstance(price_in, dict):
            return None, None, "Neplatný formát cenového rozpisu."
        for field in ASSEMBLY_PRICE_SUMMARY_FIELDS:
            v = _num_or_none(price_in.get(field))
            if v is not None:
                clean_price[field] = v

    return clean_bom, clean_price, None


def _generate_assembly_sku(cur, name):
    """Vygeneruje unikatni SKU pro navrh e-shopove polozky ze sestavy -
    admin si ho pak muze v karte produktu prepsat na cokoli smysluplnejsiho,
    tohle je jen bezkolizni vychozi hodnota (shop_products.sku je UNIQUE).

    BEZ PREFIXU "SEST-". Robert 2026-09-11: *"v sku nebude slovo SEST"* -
    kod sestavy je sam o sobe identifikator (napr. `K-075-EB-30`:
    karoserie, typologie, profil) a sluzebni predpona z nej dela neco
    jineho, nez na cem jsme se dohodli. Karta 3942 mela `SEST-K-075-EB-30`
    a opravila se na `K-075-EB-30` (zaloha
    backups/2026-09-11_sku_3942_pred_zmenou.json).

    Nazev sestavy uz kod obsahuje (`K-075-EB-30-C-0063-1-0 - jedno pasmo,
    jen ram`), takze se z nej vezme prave ta kodova cast pred prvni
    pomlckou s mezerou; kdyz nazev kod nema, pouzije se cely prepsany na
    SKU tvar jako driv.
    """
    cela = str(name or "").strip()
    # "<KOD> - <popis>" -> vezmi KOD. Rozhoduje OBSAH (kod nema mezery),
    # ne konkretni format - ten se uz nekolikrat zmenil.
    m = re.match(r"^(\S+)\s+[-–]\s+\S", cela)
    zaklad = m.group(1) if m else cela
    base = re.sub(r"[^a-zA-Z0-9]+", "-", zaklad).strip("-").upper()[:40] or "SESTAVA"
    candidate = base
    n = 1
    while True:
        cur.execute("SELECT id FROM shop_products WHERE sku=%s", (candidate,))
        if not cur.fetchone():
            return candidate
        n += 1
        candidate = f"{base}-{n}"


# --------------------------------------------------------------------
# Odvozeni ZNACKY z nazvu sestavy.
#
# Vyclenil bot8 2026-09-09 z product_assemblies_list() - stejnou znacku
# ted potrebuje i zrcadleni na Sdileny disk (nize), a dve kopie te same
# heuristiky by se rozesly. Nic se nezapisuje do DB, je to jen odvozeni
# pro odpoved a pro nazev slozky.
def nacti_mapy_znacek(cur):
    """(kod K-XXX -> znacka, prefix nazvu modelu -> znacka)"""
    cur.execute("SELECT cm.name AS model, mk.name AS make FROM car_models cm "
                "JOIN car_makes mk ON mk.id=cm.make_id")
    code_to_make, prefix_to_make = {}, {}
    for m in cur.fetchall():
        code = re.search(r"\[(K-\d{3}e?)\]", m["model"] or "")
        if code:
            code_to_make.setdefault(code.group(1), m["make"])
        prefix = (m["model"] or "").split(" [", 1)[0].strip()
        if prefix:
            prefix_to_make.setdefault(prefix, m["make"])
    return code_to_make, prefix_to_make


def znacka_ze_jmena(name, code_to_make, prefix_to_make):
    """Nejdriv kod karoserie ("Jumpy L2 K-123e - boxy..."), pak NEJDELSI
    prefix nazvu modelu ("Proace Long Electric 20- - boxy..." -> Toyota).
    Vraci None, kdyz nesedi ani jedno."""
    nm = name or ""
    code = re.search(r"\bK-\d{3}e?\b", nm)
    if code:
        make = code_to_make.get(code.group(0))
        if make:
            return make
    for prefix in sorted(prefix_to_make, key=len, reverse=True):
        if nm.startswith(prefix):
            return prefix_to_make[prefix]
    return None


# --------------------------------------------------------------------
# ZRCADLENI SESTAV NA SDILENY DISK
#
# Robert 2026-09-09: "chci zrcadlit produktové sestavy, které nebudou
# nezařazené". Vlastni tvary se na disk zrcadli uz davno
# (custom_shapes.py::_mirror_shape_to_drive), sestavy ne - a Robert je na
# disku hledal.
#
# "Nezarazene" tu MUSI zustat prazdne, a to je ta podstatna cast zadani.
# Kategorie sestav (product_assembly_categories) se v praxi nepouzivaji -
# k 2026-09-09 ma VSECH 263 sestav `category_id` i `car_model_id` NULL,
# takze zarazovat podle nich by znamenalo naskladat vsechno do jedne
# hromady. Slozka se proto urcuje podle ZNACKY VOZIDLA odvozene z nazvu
# (`znacka_ze_jmena` vyse) - stejne, jak uz se znacka odvozuje ve vypisu
# sestav. Overeno nad zivymi daty: znacku dostane vsech 263 sestav
# (Ford 55, Peugeot 54, Citroen 45, VW 40, Toyota 26, Mercedes 22,
# Renault 8, Opel 7, Fiat 6), do "Nezarazene" nepada ani jedna.
#
# Kdyby znacka presto nesla odvodit (novy model jeste nezalozeny v
# car_models), soubor se ZAMERNE nezapise vubec a jen se to zaloguje -
# radeji chybejici soubor nez tichy navrat "Nezarazenych", o kterych
# Robert vyslovne rekl, ze je nechce.
SESTAVY_DRIVE_ROOT = "Produktové sestavy"


def _drive_slozka(cur, nazev, parent_id, user_id):
    """Najde nebo zalozi slozku daneho jmena pod danym rodicem."""
    if parent_id is None:
        cur.execute("SELECT id FROM shared_drive_folders "
                    "WHERE parent_folder_id IS NULL AND name=%s", (nazev,))
    else:
        cur.execute("SELECT id FROM shared_drive_folders "
                    "WHERE parent_folder_id=%s AND name=%s", (parent_id, nazev))
    row = cur.fetchone()
    if row:
        return row["id"]
    cur.execute("INSERT INTO shared_drive_folders (parent_folder_id, name, created_by) "
                "VALUES (%s,%s,%s)", (parent_id, nazev, user_id))
    return cur.lastrowid


def zrcadli_sestavu_na_disk(cur, assembly_id, name, payload, user_id,
                            mapy=None):
    """Zapise/aktualizuje JSON export JEDNE sestavy na Sdilenem disku.

    VOLAT VZDY v ramci uz otevrene transakce (tentyz `cur`, zadny vlastni
    get_conn/close) - viz past s tichym rollbackem popsana v
    custom_shapes.py::_mirror_shape_to_drive.

    Vraci id souboru na disku, nebo None kdyz se znacka nepodarilo odvodit.
    """
    code_to_make, prefix_to_make = mapy if mapy else nacti_mapy_znacek(cur)
    znacka = znacka_ze_jmena(name, code_to_make, prefix_to_make)
    if not znacka:
        app.logger.warning(
            "Sestava %s (%r): nelze odvodit znacku, na disk se nezrcadli "
            "(Robert 2026-09-09: zadne 'Nezarazene')", assembly_id, name)
        return None

    koren = _drive_slozka(cur, SESTAVY_DRIVE_ROOT, None, user_id)
    slozka = _drive_slozka(cur, znacka, koren, user_id)

    obsah = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    zobrazeny_nazev = f"{name}.json"[:255]

    cur.execute("SELECT drive_file_id FROM product_assemblies WHERE id=%s", (assembly_id,))
    srow = cur.fetchone()
    stavajici = srow["drive_file_id"] if srow else None
    frow = None
    if stavajici:
        cur.execute("SELECT stored_filename FROM shared_drive_files WHERE id=%s", (stavajici,))
        frow = cur.fetchone()

    if frow:
        with open(os.path.join(DRIVE_FILES_DIR, frow["stored_filename"]), "wb") as fh:
            fh.write(obsah)
        cur.execute("UPDATE shared_drive_files SET folder_id=%s, filename=%s, size_bytes=%s "
                    "WHERE id=%s", (slozka, zobrazeny_nazev, len(obsah), stavajici))
        return stavajici

    ulozeny_nazev = f"{os.urandom(16).hex()}.json"
    with open(os.path.join(DRIVE_FILES_DIR, ulozeny_nazev), "wb") as fh:
        fh.write(obsah)
    cur.execute(
        "INSERT INTO shared_drive_files (folder_id, filename, stored_filename, "
        "content_type, size_bytes, uploaded_by) VALUES (%s,%s,%s,%s,%s,%s)",
        (slozka, zobrazeny_nazev, ulozeny_nazev, "application/json", len(obsah), user_id),
    )
    novy = cur.lastrowid
    cur.execute("UPDATE product_assemblies SET drive_file_id=%s WHERE id=%s", (novy, assembly_id))
    return novy


# INCIDENT 2026-09-16 (bot8): tlacitko "Uloz opravu" (resave_scene) dvakrat
# prepsalo `data` existujici sestavy (#517, #500) obsahem UPLNE JINE sceny -
# frontend chyba (currentAssemblyMeta neoverovalo, ze `placed` porad patri k
# nacteneme ID, opraveno commit 10e51d31), ale zadna zaloha PREDTIM
# neexistovala - `zrcadli_sestavu_na_disk` prepisuje TENTYZ soubor pri kazdem
# volani (mirror aktualniho stavu, ne historie), obnova obou sel jen diky
# nahodne existujici kopii z bot8 vlastni session. Tenhle backup je NEZAVISLY
# na frontendu - i kdyby se frontendova kontrola nekdy obesla (stara zalozka
# v prohlizeci se starym JS, budouci bug...), stara data zustanou zachovana.
# Kazdy resave = 1 NOVY soubor (razitko v nazvu), nic se neprepisuje.
RESAVE_BACKUP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                 "backups", "resave_scene")


def _zaloha_pred_resave(assembly_id, name, stara_data_raw):
    """Ulozi PUVODNI `data` sestavy (jeste jako syrovy JSON retezec ze
    sloupce) na disk, TESNE PRED prepsanim pres "Uloz opravu". Vraci nazev
    souboru. Zamerne NEZACHYCUJE vyjimky - volajici ma selhani zalohy
    povazovat za duvod NEPOKRACOVAT (zaloha je tu proto, aby nikdy nenastala
    situace "prepsano a nejde vratit")."""
    stara_data = json.loads(stara_data_raw) if stara_data_raw else None
    os.makedirs(RESAVE_BACKUP_DIR, exist_ok=True)
    razitko = datetime.now().strftime("%Y-%m-%dT%H-%M-%S.%f")
    nazev = f"{assembly_id}_{razitko}.json"
    with open(os.path.join(RESAVE_BACKUP_DIR, nazev), "w", encoding="utf-8") as fh:
        json.dump({"assembly_id": assembly_id, "name": name, "data": stara_data}, fh, ensure_ascii=False, indent=1)
    return nazev


def smaz_zrcadlo_sestavy(cur, assembly_id):
    """Smaze soubor sestavy ze Sdileneho disku (vola se pri mazani sestavy,
    aby na disku nezustavaly osirele JSONy). Selhani se ignoruje - smazani
    sestavy nesmi spadnout kvuli uklidu na disku."""
    cur.execute("SELECT drive_file_id FROM product_assemblies WHERE id=%s", (assembly_id,))
    row = cur.fetchone()
    if not row or not row["drive_file_id"]:
        return
    cur.execute("SELECT stored_filename FROM shared_drive_files WHERE id=%s", (row["drive_file_id"],))
    frow = cur.fetchone()
    if frow:
        try:
            os.remove(os.path.join(DRIVE_FILES_DIR, frow["stored_filename"]))
        except OSError:
            pass
    cur.execute("DELETE FROM shared_drive_files WHERE id=%s", (row["drive_file_id"],))


# Typ sestavy (AUTO / STUL_SKLAD / dalsi, tabulka sestava_typ - Robert pres bot3
# 2026-09-26). Pri ulozeni sestavy ze sceny se typ nastavuje VYSLOVNE (hlavicka
# sql/2026-09-26_sestava_typ_tabulka.sql: nikdy se neodvozuje z nullability
# car_model_id) - bot8 2026-10-02: do te doby POST typ vubec nezapisoval a nova
# sestava ze sceny mela sestava_typ_id NULL (vsech 530 stavajicich = AUTO). Kdyz
# klient typ neposle (skripty, stary frontend), plati vychozi AUTO - vestavba do
# vozidla je hlavni linie a odpovida migraci vsech stavajicich sestav.
SESTAVA_TYP_VYCHOZI = "AUTO"


def _sestava_typ_podle_kodu(cur, kod):
    """(id, kod) aktivniho typu sestavy, nebo None (neznamy / neaktivni)."""
    cur.execute("SELECT id, kod FROM sestava_typ WHERE kod=%s AND aktivni=1", (kod,))
    row = cur.fetchone()
    return (row["id"], row["kod"]) if row else None


@app.get("/api/product-assemblies/typy")
@staff_required
def product_assemblies_typy():
    """Aktivni typy sestav pro vyber ve scene pri ukladani (scene.html, panel Produktove
    sestavy). Jen cteni; sprava typu je v adminu (/api/admin/sestava-typ, jen admin)."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT kod, nazev FROM sestava_typ WHERE aktivni=1 ORDER BY sort_order, id")
            typy = [{"kod": r["kod"], "nazev": r["nazev"]} for r in cur.fetchall()]
    finally:
        conn.close()
    return jsonify({"typy": typy, "vychozi": SESTAVA_TYP_VYCHOZI})


@app.get("/api/product-assemblies")
@staff_required
def product_assemblies_list():
    user = current_user()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT pa.id, pa.name, pa.category_id, pa.data, pa.created_by, pa.is_public, "
                "pa.technicky_ok, pa.technicky_ok_at, pa.is_master, "
                "pa.kolize_pocet, pa.kolize_checked_at, "
                "pa.prepazka_rezerva_mm, pa.podbeh_rezerva_mm, "
                "pa.shop_product_id, pa.created_at, pa.resi_se_at, pa.dodatek, mk.name AS make, "
                # bot8 2026-09-24, WORKFLOW.md pravidlo 51 (Robert: "kazda sestava
                # do auta musi nest stitek na jakou stranu auta je navrzena") -
                # stitek se ma zobrazovat v prehledu sestav i v detailu, takze ho
                # lehka odpoved musi nest. Zadny novy mechanismus: cteme existujici
                # `umisteni_id` -> ciselnik `regal_umisteni`.
                "ru.kod AS umisteni_kod, ru.nazev AS umisteni_nazev "
                "FROM product_assemblies pa "
                "LEFT JOIN car_models cm ON cm.id=pa.car_model_id "
                "LEFT JOIN car_makes mk ON mk.id=cm.make_id "
                "LEFT JOIN regal_umisteni ru ON ru.id=pa.umisteni_id "
                "WHERE pa.is_public=1 OR pa.created_by=%s ORDER BY pa.created_at DESC",
                (user["id"],),
            )
            rows = cur.fetchall()
            # Znacka pro sestavy bez car_model_id (Robert 2026-09-03 "seradit
            # podle znacky a abecedne"): odvodi se jen pro odpoved z nazvu
            # sestavy - vlastni karoserie kod ("Jumpy L2 K-123e - boxy...",
            # bot8 2026-09-06 zmena formatu) nebo prefix nazvu modelu
            # ("Proace Long Electric 20- - boxy..."), nic se do DB nezapisuje.
            code_to_make, prefix_to_make = {}, {}
            if any(not r["make"] for r in rows):
                code_to_make, prefix_to_make = nacti_mapy_znacek(cur)
    finally:
        conn.close()
    result = []
    for r in rows:
        try:
            parsed = json.loads(r["data"])
        except (ValueError, TypeError):
            parsed = {}
        make = r["make"] or znacka_ze_jmena(r["name"], code_to_make, prefix_to_make)
        result.append({
            "id": r["id"],
            "name": r["name"],
            "category_id": r["category_id"],
            "make": make,
            # NULL = sestava stitek nema. Scena to MUSI zobrazit jako
            # "neurceno", ne jako prazdno - pravidlo 51 rika, ze sestava
            # bez stitku neni hotova.
            "umisteni_kod": r["umisteni_kod"],
            "umisteni_nazev": r["umisteni_nazev"],
            # bot8 2026-09-17 (Robert: "produktove sestavy na cteni trva
            # desitky vterin, nemuze se pri otevirani okna nacitat veskera
            # geometrie"): `parts`/`join_groups`/`frame_groups`/`text_labels`
            # ZAMERNE VYNECHANY - u ~390 sestav to bylo 7.5 MB JSON jen na
            # otevreni stromu, kdy se z nich reálně cetlo jen id/nazev/
            # priznaky nize. Plna geometrie KONKRETNI sestavy se ted tahne
            # az pri jejim otevreni pres uz existujici GET /api/product-
            # assemblies/lookup?assembly=<id> (viz webapp/scene.html
            # insertCustomShape - lazy fetch, cachuje se do PRODUCT_
            # ASSEMBLIES[i] pro pristi otevreni beze zmeny). Klic `parts`
            # v odpovedi zamerne CHYBI (ne `[]`) - klient timhle pozna
            # "jeste nenacteno" od "genuinely 0 dilu".
            "is_public": bool(r["is_public"]),
            # Robert 2026-09-11: "zatrzitko na kazdy radek ktere znamena moje
            # schvaleni sestavy po technicke strance jak vypada, cena se bude
            # resit zvlast". NEZAMENOVAT s category_id != NULL, ktere sestavu
            # pousti k renderum a publikaci (WORKFLOW.md pravidlo 24) - tohle
            # je schvaleni SKLADBY DILU, nic vic.
            "technicky_ok": bool(r["technicky_ok"]),
            "technicky_ok_at": r["technicky_ok_at"].isoformat() if r["technicky_ok_at"] else None,
            # Priznak koliznich uhelniku - scena z nej dela CERVENY NAZEV
            # (Robert 2026-09-11: "oznac mi ve scene ty sestavy resp jejich
            # nazev cervenou barvou"). Posilaji se DVE veci, protoze jedna
            # nestaci: `kolize_pocet` je None, kdyz se sestava NIKDY nemerila,
            # a to se nesmi zobrazit stejne jako zmerena nula. Detail
            # (`kolize_detail`) se sem NEPOSILA, do popisku staci pocet.
            "kolize_pocet": r["kolize_pocet"],
            "kolize_checked_at": r["kolize_checked_at"].isoformat() if r["kolize_checked_at"] else None,
            # Fronta ke schvalovani ve scene (Robert 2026-09-11, pres bot3):
            # varovne priznaky u jedne sestavy, at Robert nezjisti az po
            # otevreni, ze ji stejne schvalit nemuze. Jen bool/stav, ne
            # cela pole (bom/price_summary) - ta uz jsou velka sama o sobe.
            "razitka_stav": razitkovac.stav_razitek(parsed),
            "has_bom": bool(parsed.get("bom")),
            # POZOR: `price_summary` umi byt ulozene jako JSON null (ne jen
            # chybejici klic) - mazaci/prestavbove skripty ho tak nastavuji
            # zamerne, kdyz zmena poctu dilu udela stary kusovnik neplatnym
            # (viz scripts/2026-09-11_prestavba_vito_clenene_nohy.py apod.).
            # `.get("price_summary", {})` na to nestaci: default `{}` se
            # pouzije jen kdyz klic CHYBI, ne kdyz je hodnota `None` - u 18
            # sestav v DB je prave `None`, takze `.get(...)` na nem spadlo
            # (2026-09-11, tenhle radek shodil CELY `/api/product-assemblies`
            # kazde sestave, ne jen te s null). `or {}` opravuje totez jako
            # uz drive na radku "price_summary": parsed.get(...) or {} nize.
            "has_price": (parsed.get("price_summary") or {}).get("material_czk") is not None,
            "is_master": bool(r["is_master"]),
            "mine": r["created_by"] == user["id"],
            "shop_product_id": r["shop_product_id"],
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            # bot8 2026-09-17 (Robert: "davej mi sestavy aktualne ktere resime
            # vzdy nahoru") - scena z toho sklada skupinu "Aktualne resime"
            # uplne nahore v panelu, nejnovejsi prvni. NULL = neresi se.
            "resi_se_at": r["resi_se_at"].isoformat() if r["resi_se_at"] else None,
            # bot8 2026-09-17 (Robert: "v radcich chci videt take cislovani
            # preulozenych sestav") - pocet preulozeni pod stejnym ID ("Ulozit
            # opravu" zvedne dodatek o 1), posledni segment kod_sestavy.
            "dodatek": r["dodatek"] or 0,
            # Stitek serie (Robert 2026-09-12, pres bot3: paralelni serie
            # regalu se stejnym receptem, jinou kolizni rezervou - "10-30mm
            # od kolize" mist dosavadnich 2/20mm). ZADNY samostatny textovy
            # sloupec (bot3: "riziko rozjeti cisla/textu") - stitek se skladá
            # AZ pri zobrazeni z tehle dvou cisel, viz fmtSerieStitek()
            # nize/ve vyroba-sestav.js. Existujicich 269 ma obe pole VYPLNENA
            # (2/20, zpetne dopocteno bot8 2026-09-12) - NULL tady tedy
            # neznamena "puvodni serie", ale "jeste nezpracovano".
            "prepazka_rezerva_mm": r["prepazka_rezerva_mm"],
            "podbeh_rezerva_mm": r["podbeh_rezerva_mm"],
        })
    return jsonify({"status": "ok", "assemblies": result})


# bot16 2026-09-02 (faze C "Prezentace sestavy ze sceny"): dohledani JEDNE
# sestavy pro otevreni sceny v pohledu ze zakreslene pripominky
# (webapp/scene.html?assembly=<id>|product=<shop_products.id>&view=...).
# Proc samostatny endpoint a ne filtr klienta nad GET /api/product-assemblies:
# (a) seznam vyse vraci jen verejne + vlastni sestavy - admin, ktery
# pripominku resi, ale sestavu nezalozil a ta neni verejna, by ji v nem
# nenasel; (b) scena nemusi cekat, az se nacte cely seznam (stovky sestav
# s daty dilu), staci ji katalog. Viditelnost: verejna NEBO vlastni NEBO
# admin. `product=` -> nejnovejsi sestava podle id (vazba je 1:1, vyjimecne
# vic sestav na produkt). Tvar polozky = 1:1 jako v seznamu vyse (scena ji
# preda do insertCustomShape beze zmeny) + car_model_id (jen informativne,
# panel sestav karoserii pri vkladani nenacita a scena tady taky ne).
@app.get("/api/product-assemblies/lookup")
@staff_required
def product_assembly_lookup():
    user = current_user()
    assembly_id = request.args.get("assembly", type=int)
    product_id = request.args.get("product", type=int)
    if not assembly_id and not product_id:
        return jsonify({"error": "Chybí parametr assembly nebo product."}), 400
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            if assembly_id:
                cur.execute(
                    "SELECT id, name, category_id, car_model_id, data, created_by, is_public, shop_product_id, created_at "
                    "FROM product_assemblies WHERE id=%s",
                    (assembly_id,),
                )
            else:
                cur.execute(
                    "SELECT id, name, category_id, car_model_id, data, created_by, is_public, shop_product_id, created_at "
                    # Robert 2026-09-10: "schvalovali jsme si neco ve scene a do
                    # skladove karty si dal zase cosi jineho". Bylo tu
                    # `ORDER BY id DESC` - tedy NEJNOVEJSI navazana sestava.
                    # Dokud mela karta navazanou jedinou, nebylo to poznat;
                    # jakmile k ni pribyly varianty, prehodil se 3D nahled v
                    # karte na tu s NEJVYSSIM id (u Dobla C na 6/6, ktera ma
                    # navic dve zname kolize) misto na tu zakladni, kterou
                    # Robert schvaloval ve scene.
                    # Nove NEJSTARSI = zakladni sestava produktu. Varianty
                    # se do karty dostanou jako zalozky (viz by-product,
                    # ktery vraci vsechny), ne tichou zmenou hlavniho nahledu.
                    "FROM product_assemblies WHERE shop_product_id=%s ORDER BY id LIMIT 1",
                    (product_id,),
                )
            row = cur.fetchone()
    finally:
        conn.close()
    if not row:
        if assembly_id:
            return jsonify({"error": f"Sestava #{assembly_id} neexistuje (mohla být smazána)."}), 404
        return jsonify({"error": f"K produktu #{product_id} není uložená žádná produktová sestava."}), 404
    if not (row["is_public"] or row["created_by"] == user["id"] or user.get("role") == "admin"):
        return jsonify({"error": "K této sestavě nemáš přístup (není veřejná a nezaložil/a jsi ji)."}), 403
    try:
        parsed = json.loads(row["data"])
    except (ValueError, TypeError):
        parsed = {}
    return jsonify({"status": "ok", "assembly": {
        "id": row["id"],
        "name": row["name"],
        "category_id": row["category_id"],
        "car_model_id": row["car_model_id"],
        "parts": parsed.get("parts") or [],
        "join_groups": parsed.get("join_groups") or [],
        "frame_groups": parsed.get("frame_groups") or [],
        "text_labels": parsed.get("text_labels") or [],
        "is_public": bool(row["is_public"]),
        "mine": row["created_by"] == user["id"],
        "shop_product_id": row["shop_product_id"],
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
    }})


@app.post("/api/product-assemblies")
@staff_required
def product_assemblies_create():
    body = request.get_json(silent=True) or {}
    name = (body.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Vyplň název sestavy."}), 400
    if len(name) > 255:
        return jsonify({"error": "Název je příliš dlouhý."}), 400
    katalog_parts = fetch_katalog_parts()
    valid_part_ids = {p["id"] for p in katalog_parts}
    clean_parts, err = _validate_custom_shape_parts(body.get("parts"), valid_part_ids, max_parts=PRODUCT_ASSEMBLY_MAX_PARTS)
    if err:
        return jsonify({"error": err}), 400
    clean_join_groups, clean_frame_groups, err = _validate_custom_shape_relations(
        body.get("join_groups"), body.get("frame_groups"), len(clean_parts), clean_parts
    )
    if err:
        return jsonify({"error": err}), 400
    clean_bom, clean_price_summary, err = _validate_assembly_bom_and_price(body.get("bom"), body.get("price_summary"))
    if err:
        return jsonify({"error": err}), 400
    clean_text_labels, err = _validate_custom_shape_text_labels(body.get("text_labels"))
    if err:
        return jsonify({"error": err}), 400
    user = current_user()
    is_public = 1 if user and user["role"] == "admin" else 0
    category_id = body.get("category_id")
    if category_id is not None:
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM product_assembly_categories WHERE id=%s", (category_id,))
                if not cur.fetchone():
                    return jsonify({"error": "Kategorie neexistuje."}), 400
        finally:
            conn.close()
    typ_kod = str(body.get("sestava_typ") or SESTAVA_TYP_VYCHOZI).strip()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            typ = _sestava_typ_podle_kodu(cur, typ_kod)
    finally:
        conn.close()
    if not typ:
        return jsonify({"error": f"Neznámý nebo neaktivní typ sestavy „{typ_kod}“."}), 400
    sestava_typ_id, typ_kod = typ
    payload = {
        "parts": clean_parts, "join_groups": clean_join_groups, "frame_groups": clean_frame_groups,
        "bom": clean_bom, "price_summary": clean_price_summary, "text_labels": clean_text_labels,
    }
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            # Navrh e-shopove polozky NEJDRIV (potrebujeme jeji id do
            # product_assemblies.shop_product_id) - neaktivni, bez ceny,
            # admin dodela zbytek v karte produktu (Sklad).
            sku = _generate_assembly_sku(cur, name)
            # slug hned pri vzniku (bot15, 2026-09-02) - viz _unique_product_slug.
            cur.execute(
                "INSERT INTO shop_products (sku, name, slug, unit, active) VALUES (%s,%s,%s,%s,0)",
                (sku, name, _product_slug_for_name(cur, name), "ks"),
            )
            shop_product_id = cur.lastrowid
            cur.execute(
                "INSERT INTO product_assemblies (name, category_id, sestava_typ_id, data, created_by, is_public, shop_product_id) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s)",
                (name, category_id, sestava_typ_id, json.dumps(payload), user["id"] if user else None, is_public, shop_product_id),
            )
            new_id = cur.lastrowid
            # Zrcadlo na Sdilenem disku - v TEZE transakci (Robert
            # 2026-09-09). Selhani zrcadleni nesmi shodit ulozeni sestavy,
            # proto vlastni try: sestava je to podstatne, soubor doplnek.
            try:
                zrcadli_sestavu_na_disk(cur, new_id, name, payload,
                                        user["id"] if user else None)
            except Exception:  # noqa: BLE001
                app.logger.exception("Sestava %s: zrcadleni na disk selhalo", new_id)
            # Priznak koliznich uhelniku (cerveny nazev ve scene + sloupec v
            # prehledove tabulce). TADY je jedine misto v celem API, kde
            # `product_assemblies.data` vznika - scena pri ulozeni zaklada
            # NOVOU sestavu, starou neupravuje - takze staci jeden hacek.
            # ~0.16 s, viz api/kolize_priznak.py.
            #
            # Vlastni try ze stejneho duvodu jako u zrcadleni: sestava je to
            # podstatne, priznak doplnek. Kdyz prepocet selze, priznak
            # zustane NULL = "nemereno" - a to se v UI NIKDY nezobrazuje
            # zelene, takze selhani nevyrobi falesne cistou sestavu.
            try:
                kolize_priznak.prepocti(cur, [new_id], app.logger)
            except Exception:  # noqa: BLE001
                app.logger.exception("Sestava %s: prepocet priznaku kolizi selhal", new_id)
        conn.commit()
    finally:
        conn.close()
    log_audit(user["id"], "create", "product_assembly", new_id, f"{name} (navrh produktu #{shop_product_id}, typ {typ_kod})")
    return jsonify({"status": "ok", "id": new_id, "is_public": bool(is_public), "shop_product_id": shop_product_id,
                    "sestava_typ": typ_kod})


@app.delete("/api/product-assemblies/<int:assembly_id>")
@staff_required
def product_assemblies_delete(assembly_id):
    # Mazani smi jen vlastnik, admin smi cokoli - stejna logika jako u
    # Vlastnich tvaru. Navazana e-shopova polozka (shop_products) se
    # ZAMERNE NEMAZE - uz na ni muze byt realna cena/foto/objednavky,
    # smazani jen SABLONY sestavy ji nesmi vzit s sebou (FK je ON DELETE
    # SET NULL, viz sql/2026-08-08_product_assemblies.sql).
    user = current_user()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT created_by FROM product_assemblies WHERE id=%s", (assembly_id,))
            row = cur.fetchone()
            if not row:
                return jsonify({"error": "Sestava neexistuje."}), 404
            if user["role"] != "admin" and row["created_by"] != user["id"]:
                return jsonify({"error": "Tuto sestavu nemůžeš smazat, není tvoje."}), 403
            # Uklid zrcadla na disku PRED smazanim radku - potom uz by
            # nebylo kde najit drive_file_id (viz smaz_zrcadlo_sestavy).
            try:
                smaz_zrcadlo_sestavy(cur, assembly_id)
            except Exception:  # noqa: BLE001 - uklid nesmi zablokovat mazani
                app.logger.exception("Sestava %s: uklid zrcadla na disku selhal", assembly_id)
            cur.execute("DELETE FROM product_assemblies WHERE id=%s", (assembly_id,))
        conn.commit()
    finally:
        conn.close()
    return jsonify({"status": "ok"})


def _orazitkuj_pri_zarazeni(cur, assembly_id, raw_data):
    """Propise ochranna razitka do dat sestavy. Vraci popis pro odpoved/audit.

    NIKDY nevyhodi vyjimku ven: zarazeni do slozky je operace uzivatele a
    nesmi selhat kvuli razitkum. Kdyz se razitkovat neda (sestava nema
    role-tagovane dily, takze nejde urcit predni strana, nebo chybi .glb),
    zarazeni PROBEHNE a duvod se vrati volajicimu - lepe zarazena sestava
    bez razitek a hlaska nez odmitnute zarazeni.
    """
    try:
        data = json.loads(raw_data) if raw_data else {}
    except (ValueError, TypeError):
        return "razítka přeskočena: data sestavy nejdou přečíst"
    try:
        # Uz aktualni razitka = zadny zapis. `prerazitkuj` by vratilo data
        # nezmenena, ale i tak by slo o zbytecny UPDATE celeho `data` blobu
        # (stovky kB) pri kazdem preraceni mezi slozkami.
        if razitkovac.stav_razitek(data) == "aktualni":
            return "razítka už jsou aktuální - beze změny"
        # Presne rozmery vc. produktu (eurobox aj.) pro blokovaci/exponovani
        # kontrolu razitek - bez tohohle padaji VSECHNY product_* dily na
        # hruby odhad ROZMER_NEZNAMY (viz razitkovac.rozmery_z_katalogu).
        rozmery = razitkovac.rozmery_z_katalogu(cur, KATALOG_DIR)
        nova, zprava = razitkovac.prerazitkuj(data, assembly_id, KATALOG_DIR, rozmery=rozmery)
    except Exception:
        app.logger.exception("razitkovani sestavy %s selhalo", assembly_id)
        return "razítka přeskočena: razítkovač skončil chybou (viz log)"
    if nova is None:
        return "razítka přeskočena: %s" % zprava
    cur.execute("UPDATE product_assemblies SET data=%s WHERE id=%s",
                (json.dumps(nova, ensure_ascii=False), assembly_id))
    return zprava


def _dopocti_kod_sestavy_pri_zarazeni(cur, assembly_id):
    """Dopocte a zapise `kod_sestavy`, kdyz uz jsou zname vsechna zdrojova
    pole. Vraci novy kod (pro hlasku/audit), nebo None (bez zmeny).

    Robert 2026-09-13 pres bot9/bot3 ("automatizovat generovani kodu SKU
    zaroven, kdyz se sestava razitkuje 3D-logem"): dosud jen rucni beh
    `scripts/_kod_sestavy.py`. Napojeno na STEJNOU udalost jako razitkovani
    (`_orazitkuj_pri_zarazeni` vyse) - prechod `category_id NULL -> slozka`
    v `product_assemblies_update()`.

    ⚠️ ZAMERNE VOLANO NEZAVISLE na tom, jestli razitkovani realne probehlo,
    ne uvnitr jeho "uz aktualni" vetve. Navrh (bot9) umistoval dopocet
    kodu vedle UPDATE ... SET data=... uvnitr razitkovaci vetve - jenze
    `kod_sestavy` na stavu razitek vubec nezavisi (zavisi na karoserii/
    umisteni/typologii/profilu/verzi...), zavisely by tedy na sobe dve
    nesouvisejici veci. Sestava PREREAZOVANA MEZI SLOZKAMI podruhe ma
    razitka uz aktualni (ta vetev se preskoci - viz `stav_razitek`), ale
    mezitim mohla dostat nove vyplnene pole (napr. umisteni) - kdyby kod
    visel na razitkovaci vetvi, nikdy by se nedopocital. Obe akce (razitka,
    kod) zustavaji NEZAVISLE, jen sdileji SPOUSTEC (prvni/dalsi zarazeni).

    Stejna bezpecnostni zasada jako u razitek: NIKDY nevyhodi vyjimku ven,
    zarazeni nesmi selhat kvuli dopoctu kodu. Kdyz cokoli z zdrojovych poli
    chybi, generator vrati None - to NENI chyba (WORKFLOW.md: "radsi
    chybejici nez uhodnuty"), jen se kod nedopocita, ticha nula v odpovedi.
    """
    try:
        cur.execute(
            """
            SELECT pa.karoserie_kod, pa.profil_mm, pa.verze, pa.dodatek,
                   pa.kod_sestavy AS stary,
                   ru.kod AS umisteni_kod, rt.kod AS typologie_kod,
                   tv.kod AS varianta_kod, hb.kod AS horni_blok_kod
            FROM product_assemblies pa
            LEFT JOIN regal_umisteni ru ON ru.id = pa.umisteni_id
            LEFT JOIN regal_typologie rt ON rt.id = pa.typologie_id
            LEFT JOIN typologie_varianty tv ON tv.id = pa.typologie_varianta_id
            LEFT JOIN horni_blok_varianty hb ON hb.id = pa.horni_blok_varianta_id
            WHERE pa.id=%s
            """,
            (assembly_id,),
        )
        r = cur.fetchone()
        if not r:
            return None
        novy = sestavit_kod_sestavy(
            karoserie_kod=r["karoserie_kod"], umisteni_kod=r["umisteni_kod"],
            typologie_kod=r["typologie_kod"], profil_mm=r["profil_mm"],
            verze=r["verze"], varianta_kod=r["varianta_kod"],
            horni_blok_kod=r["horni_blok_kod"], dodatek=r["dodatek"],
        )
    except Exception:
        app.logger.exception("dopocet kod_sestavy pro sestavu %s selhal", assembly_id)
        return None
    if novy is None or novy == r["stary"]:
        return None
    cur.execute("UPDATE product_assemblies SET kod_sestavy=%s WHERE id=%s", (novy, assembly_id))
    return novy


@app.put("/api/product-assemblies/<int:assembly_id>")
@staff_required
def product_assemblies_update(assembly_id):
    """Prerazeni do jine kategorie a/nebo technicke schvaleni sestavy."""
    user = current_user()
    body = request.get_json(silent=True) or {}
    if ("category_id" not in body and "technicky_ok" not in body and "is_master" not in body
            and "resave_scene" not in body and "resi_se" not in body):
        return jsonify({"error": "Nic ke změně."}), 400
    category_id = body.get("category_id")
    razitka_zprava = None
    novy_kod_sestavy = None
    nova_cena_karty = None
    resave_info = None
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT name, created_by, category_id, data, shop_product_id, technicky_ok "
                        "FROM product_assemblies WHERE id=%s",
                        (assembly_id,))
            row = cur.fetchone()
            if not row:
                return jsonify({"error": "Sestava neexistuje."}), 404
            if user["role"] != "admin" and row["created_by"] != user["id"]:
                return jsonify({"error": "Tuto sestavu nemůžeš upravit, není tvoje."}), 403
            # bot8 2026-09-17 (Robert: "davej mi sestavy aktualne ktere resime
            # vzdy nahoru") - pripnuti/odepnuti do skupiny "Aktualne resime"
            # (resi_se_at). Kontrola role PRED ostatnimi vetvemi, at 403
            # nenastane az po castecne provedenych zmenach v tomtez requestu.
            if "resi_se" in body:
                if user["role"] != "admin":
                    return jsonify({"error": "Připnout nebo odepnout sestavu smí jen admin."}), 403
                cur.execute("UPDATE product_assemblies SET resi_se_at=%s WHERE id=%s",
                            (datetime.now() if body.get("resi_se") else None, assembly_id))
            # bot8 2026-09-15 (Robert: "funkce ve scene, ktera preulozi sestavu
            # pod stejnym ID, za ucelem drobne rucni opravy adminem, po ulozeni
            # oznacit v poslednim segmentu [dodatek] o +1 vyssim cislem"):
            # DOSUD zadna cesta v API nepresepisovala `product_assemblies.data`
            # existujiciho radku - ulozeni ze sceny vzdy zakladalo NOVY radek
            # (viz komentar u product_assemblies_create, "TADY je jedine misto,
            # kde data vznika"). Tenhle blok je prvni vyjimka, proto vyslovne
            # jen pro admina (ne tvurce sestavy jako ostatni vetve tady) a
            # jasne oddelena od schvalovani/zarazeni - je to cisty prepis dat
            # PRI ZACHOVANI ID, ne zmena stavu.
            if body.get("resave_scene"):
                if user["role"] != "admin":
                    return jsonify({"error": "Přeuložení opravy smí udělat jen admin."}), 403
                katalog_parts = fetch_katalog_parts()
                valid_part_ids = {p["id"] for p in katalog_parts}
                clean_parts, err = _validate_custom_shape_parts(
                    body.get("parts"), valid_part_ids, max_parts=PRODUCT_ASSEMBLY_MAX_PARTS)
                if err:
                    return jsonify({"error": err}), 400
                clean_join_groups, clean_frame_groups, err = _validate_custom_shape_relations(
                    body.get("join_groups"), body.get("frame_groups"), len(clean_parts), clean_parts)
                if err:
                    return jsonify({"error": err}), 400
                clean_bom, clean_price_summary, err = _validate_assembly_bom_and_price(
                    body.get("bom"), body.get("price_summary"))
                if err:
                    return jsonify({"error": err}), 400
                clean_text_labels, err = _validate_custom_shape_text_labels(body.get("text_labels"))
                if err:
                    return jsonify({"error": err}), 400
                payload = {
                    "parts": clean_parts, "join_groups": clean_join_groups, "frame_groups": clean_frame_groups,
                    "bom": clean_bom, "price_summary": clean_price_summary, "text_labels": clean_text_labels,
                }
                # Zaloha PUVODNICH dat PRED prepsanim (viz komentar u
                # _zaloha_pred_resave vyse) - schvalne se nezachytava vyjimka,
                # selhani zalohy ma prepsani zastavit, ne se tise preskocit.
                try:
                    _zaloha_pred_resave(assembly_id, row["name"], row["data"])
                except Exception:  # noqa: BLE001
                    app.logger.exception("Sestava %s: zaloha pred prepsanim SELHALA, oprava NEPROVEDENA", assembly_id)
                    return jsonify({"error": "Přeuložení zastaveno: nepodařilo se zálohovat původní data "
                                              "(bezpečnostní pojistka). Zkuste to prosím znovu."}), 500
                cur.execute(
                    "UPDATE product_assemblies SET data=%s, dodatek=dodatek+1 WHERE id=%s",
                    (json.dumps(payload), assembly_id),
                )
                # kod_sestavy s NOVYM (uz inkrementovanym) dodatkem - stejne
                # segmenty jako _dopocti_kod_sestavy_pri_zarazeni, ale ten
                # dodatek nemeni, jen dopocitava chybejici kod ze stavajicich
                # sloupcu; tady potrebujeme vzit CERSTVOU hodnotu PO UPDATE.
                cur.execute(
                    """
                    SELECT pa.karoserie_kod, pa.profil_mm, pa.verze, pa.dodatek,
                           ru.kod AS umisteni_kod, rt.kod AS typologie_kod,
                           tv.kod AS varianta_kod, hb.kod AS horni_blok_kod
                    FROM product_assemblies pa
                    LEFT JOIN regal_umisteni ru ON ru.id = pa.umisteni_id
                    LEFT JOIN regal_typologie rt ON rt.id = pa.typologie_id
                    LEFT JOIN typologie_varianty tv ON tv.id = pa.typologie_varianta_id
                    LEFT JOIN horni_blok_varianty hb ON hb.id = pa.horni_blok_varianta_id
                    WHERE pa.id=%s
                    """,
                    (assembly_id,),
                )
                r2 = cur.fetchone()
                novy_kod_po_oprave = sestavit_kod_sestavy(
                    karoserie_kod=r2["karoserie_kod"], umisteni_kod=r2["umisteni_kod"],
                    typologie_kod=r2["typologie_kod"], profil_mm=r2["profil_mm"],
                    verze=r2["verze"], varianta_kod=r2["varianta_kod"],
                    horni_blok_kod=r2["horni_blok_kod"], dodatek=r2["dodatek"],
                )
                if novy_kod_po_oprave:
                    cur.execute("UPDATE product_assemblies SET kod_sestavy=%s WHERE id=%s",
                                (novy_kod_po_oprave, assembly_id))
                # Zrcadlo na disk + priznak koliznich uhelniku - stejny
                # best-effort vzor jako product_assemblies_create (selhani
                # doplnku nesmi shodit ulozeni opravy samotne).
                try:
                    zrcadli_sestavu_na_disk(cur, assembly_id, row["name"], payload, user["id"] if user else None)
                except Exception:  # noqa: BLE001
                    app.logger.exception("Sestava %s: zrcadleni na disk (oprava) selhalo", assembly_id)
                try:
                    kolize_priznak.prepocti(cur, [assembly_id], app.logger)
                except Exception:  # noqa: BLE001
                    app.logger.exception("Sestava %s: prepocet priznaku kolizi (oprava) selhal", assembly_id)
                resave_info = {"dodatek": r2["dodatek"], "kod_sestavy": novy_kod_po_oprave}
            if category_id is not None:
                cur.execute("SELECT id FROM product_assembly_categories WHERE id=%s", (category_id,))
                if not cur.fetchone():
                    return jsonify({"error": "Kategorie neexistuje."}), 400
            if "category_id" in body:
                cur.execute("UPDATE product_assemblies SET category_id=%s WHERE id=%s",
                            (category_id, assembly_id))
                # ⭐ SPOUSTEC RAZITKOVANI (Robert 2026-09-11 pres bot3: "melo by
                # se stat hned poté co sestava opustí stav ve scéně nezařazeno
                # a přechází do konkretní složky stromu"). "Nezarazena" =
                # category_id IS NULL, takze spoustec je prechod NULL -> slozka.
                #
                # ZAMERNE NE `technicky_ok`: schvalovani a zarazovani jsou od
                # 2026-09-11 dve ruzne veci a razitka visi na zarazeni.
                #
                # Razitka se tim dostanou i do 3D sceny a do modelu, ktery
                # odchazi nepřihlášenému prijemci nabidky - do teto zmeny
                # vznikala jen v renderovaci uloze, takze geometrie ven sla
                # NEORAZITKOVANA.
                #
                # Idempotenci i poznani zastaralych razitek resi otisk uvnitr
                # `prerazitkuj` - opakovane zarazeni ani preraceni mezi
                # slozkami druhou sadu nevyrobi (slozka do otisku nevstupuje).
                if row["category_id"] is None and category_id is not None:
                    razitka_zprava = _orazitkuj_pri_zarazeni(cur, assembly_id, row["data"])
                    # ⭐ SPOUSTEC DOPOCTU kod_sestavy (Robert 2026-09-13 pres
                    # bot9/bot3: "automatizovat generovani kodu SKU zaroven,
                    # kdyz se sestava razitkuje 3D-logem") - stejna udalost
                    # jako razitkovani vyse, ale NEZAVISLA na tom, jestli
                    # razitka realne prebehla (viz komentar u funkce, proc
                    # NEviset na razitkovaci vetvi).
                    novy_kod_sestavy = _dopocti_kod_sestavy_pri_zarazeni(cur, assembly_id)
            if "technicky_ok" in body:
                # Kdo a kdy schvalil se drzi kvuli dohledatelnosti - pri
                # odskrtnuti se razitko maze, aby nezustalo viset u sestavy,
                # ktera uz schvalena neni.
                ok = 1 if body.get("technicky_ok") else 0
                cur.execute(
                    "UPDATE product_assemblies SET technicky_ok=%s, "
                    "technicky_ok_at=%s, technicky_ok_by=%s WHERE id=%s",
                    (ok, datetime.now() if ok else None, user["id"] if ok else None, assembly_id))
                # ⭐ ROZSIRENI SPOUSTECE RAZITKOVANI/SKU na schvaleni (Robert
                # 2026-09-15: "potrebujes mit script ktery automaticky
                # orazitkuje a opatri SKU schvalenou sestavu adminem
                # (zatrzitkem ve scene)"). Puvodni spoustec (2026-09-11, viz
                # komentar u "category_id" vyse) byl ZAMERNE jen zarazeni do
                # slozky, ne technicky_ok - schvalovani/zarazovani jsou dve
                # ruzne veci (pravidlo 24). Tohle NENAHRAZUJE puvodni spoustec,
                # PRIDAVA druhou cestu ke stejnemu vysledku: schvalena-ale-
                # nezarazena sestava (legitimni stav dle pravidla 24) tak
                # dostane razitka/SKU uz pri schvaleni, nemusi cekat na
                # zarazeni. Podminka na PRECHOD (0/NULL -> 1), ne na hodnotu,
                # stejny vzor jako `row["category_id"] is None and category_id
                # is not None` vyse - zbytecne nespousti audit log pri kazdem
                # znovu-ulozeni uz schvalene sestavy. Obe funkce jsou
                # idempotentni (otisk uvnitr `prerazitkuj`), takze kdyby uz
                # razitka/kod existovaly z drivejsiho zarazeni, druhe volani
                # (`if not razitka_zprava`/`if not novy_kod_sestavy`) je
                # jednoducha pojistka proti prepsani zpravy z prvniho volani,
                # kdyby v JEDNOM requestu prisly OBE zmeny najednou.
                if ok and not row["technicky_ok"]:
                    if not razitka_zprava:
                        razitka_zprava = _orazitkuj_pri_zarazeni(cur, assembly_id, row["data"])
                    if not novy_kod_sestavy:
                        novy_kod_sestavy = _dopocti_kod_sestavy_pri_zarazeni(cur, assembly_id)
            if "is_master" in body:
                # Zastupce karty pro prehled eshopu (Robert 2026-09-11: "cena
                # sestavy kterou vzdy urcim ja u kazde karty") - PRAVE JEDNA
                # sestava na shop_product_id smi mit is_master=1. DB to
                # nevynucuje (viz komentar v migraci), takze pri nastaveni
                # na 1 se ostatni navazane sestavy rucne vynuluji ve STEJNE
                # transakci - jinak by dve "zastupujici" sestavy tise
                # existovaly vedle sebe a verejne API by muselo hadat.
                chce_master = 1 if body.get("is_master") else 0
                if chce_master and row["shop_product_id"]:
                    cur.execute(
                        "UPDATE product_assemblies SET is_master=0 WHERE shop_product_id=%s AND id != %s",
                        (row["shop_product_id"], assembly_id))
                cur.execute("UPDATE product_assemblies SET is_master=%s WHERE id=%s", (chce_master, assembly_id))
                # ⭐ AUTO-SYNC ceny karty s novym zastupcem (Robert 2026-09-13,
                # doslova: "u doblo L1 aktivni K-075 C musi byt hlavnim
                # obrazkem, cenou a SKU ohvezdickovana sestava" - skutecny
                # nalez: prehozeni hvezdicky na jinou sestavu drive NECHAVALO
                # `shop_products.price_czk_placeholder` na stare hodnote
                # puvodniho zastupce, karta pak ukazovala cenu, ktera
                # neodpovidala tomu, co rika zastupce v DB). Kdyz se nastavuje
                # NOVY zastupce, cena karty se OKAMZITE prepocita z jeho
                # `price_summary.total_czk` - zadny rucni skript priste.
                if chce_master and row["shop_product_id"]:
                    try:
                        novy_data = json.loads(row["data"]) if row["data"] else {}
                    except (ValueError, TypeError):
                        novy_data = {}
                    total = (novy_data.get("price_summary") or {}).get("total_czk")
                    if total is not None:
                        nova_cena_karty = round(total)
                        cur.execute(
                            "UPDATE shop_products SET price_czk_placeholder=%s WHERE id=%s",
                            (nova_cena_karty, row["shop_product_id"]),
                        )
        conn.commit()
    finally:
        conn.close()
    # Do auditu i do odpovedi: razitkovani i dopocet kodu jsou zmeny DAT
    # sestavy vyvolane jinou akci (zarazenim), takze by jinak probehly
    # neviditelne.
    odpoved = {"status": "ok"}
    if resave_info:
        log_audit(user["id"], "assembly_resave", "product_assembly", assembly_id,
                  f"ruční oprava přeuložena, dodatek -> {resave_info['dodatek']}"
                  + (f", kod_sestavy -> {resave_info['kod_sestavy']}" if resave_info["kod_sestavy"] else ""))
        odpoved["resave"] = resave_info
    if razitka_zprava:
        log_audit(user["id"], "assembly_razitka", "product_assembly", assembly_id, razitka_zprava)
        odpoved["razitka"] = razitka_zprava
    if novy_kod_sestavy:
        log_audit(user["id"], "assembly_kod_sestavy", "product_assembly", assembly_id,
                  f"kod_sestavy dopocten pri zarazeni: {novy_kod_sestavy}")
        odpoved["kod_sestavy"] = novy_kod_sestavy
    if nova_cena_karty is not None:
        log_audit(user["id"], "assembly_master_cena", "product_assembly", assembly_id,
                  f"novy zastupce -> cena karty prepoctena na {nova_cena_karty} Kc")
        odpoved["price_czk_placeholder"] = nova_cena_karty
    return jsonify(odpoved)


# Robert 2026-08-08 ("do produktové sestavy přineseme i cenu, i kusovník,
# bude vidět v administraci všemi rolemi, nebude vidět na eshopu"): DEDIKOVANY
# staff-scoped endpoint pro skladovou kartu produktu (admin.html), NE
# rozsireni GET /api/shop/products/<id> - ten je VEREJNY (napaje i verejnou
# stranku product.html, viz shop_products_get nize) a cokoliv v jeho odpovedi
# je videt i nepřihlášenému zákazníkovi. @require_permission("sklad_karty",
# "zobrazit") = viditelne KAZDE roli, ktera vubec smi na skladove karty v
# adminu (admin/manager/skladnik/ucetni/sklad - viz role_permissions), presne
# "vsemi rolemi" z Robertova zadani. Na rozdil od /api/product-assemblies
# (GET) NEFILTRUJE podle is_public/created_by - admin/sklad personál musi
# videt kusovnik KAZDE sestavy navazane na produkt, ne jen svoje/verejne.
# (bot16, 2026-09-29: sekce prejmenovana z "produkty_sklad" pri
# granularnim deleni, viz AGENTS_LOG.md.)
@app.get("/api/admin/product-assemblies/by-product/<int:shop_product_id>")
@require_permission("sklad_karty", "zobrazit")
def product_assembly_by_product(shop_product_id):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            # Robert 2026-09-10: "chceme tam mit vsechny ty varianty ktere
            # sme resili 1-6/6" + "az si udelaji dalsi varianty, pridaji se".
            # Jedna karta muze mit navazanych VIC sestav - kazda je jedna
            # varianta (jedna zalozka). Schema to dovoluje: shop_product_id
            # nema UNIQUE, jen KEY + FK ON DELETE SET NULL.
            #
            # Zpetna kompatibilita: pole "assembly" (jedna sestava) zustava,
            # aby stavajici volajici v adminu fungovali beze zmeny - vraci se
            # v nem NEJSTARSI navazana sestava, tedy ta zakladni. Nove pole
            # "assemblies" nese VSECHNY, serazene podle id (poradi vzniku =
            # poradi zalozek).
            cur.execute(
                "SELECT id, name, data, created_at FROM product_assemblies "
                # RAZENI PODLE KODU, ne podle poradi vzniku (Robert,
                # 2026-09-12: "proc nejsou serazeny podle kodu abecedne?").
                # Sestavy vznikaly na preskacku, takze `ORDER BY id` davalo
                # posledni segment kodu v poradi 3,1,4,2,5,0,6 - v seznamu
                # variant to vypadalo nahodne. Kod je pritom smysluplna osa:
                # posledni segment je provedeni horniho bloku 0..6.
                #
                # `kod_sestavy IS NULL` az na konec: kod se negeneruje, dokud
                # admin nevyplni `profil_mm` ("radsi chybejici nez uhodnuty"),
                # takze dnes ho nemaji napr. sestavy Jumpy. Ty si mezi sebou
                # udrzi poradi vzniku, coz u nich vychazi na verze A, B, C.
                "WHERE shop_product_id=%s "
                "ORDER BY kod_sestavy IS NULL, kod_sestavy, id",
                (shop_product_id,),
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    if not rows:
        return jsonify({"assembly": None, "assemblies": []})

    def _serial(row):
        try:
            parsed = json.loads(row["data"])
        except (ValueError, TypeError):
            parsed = {}
        return {
            "id": row["id"],
            "name": row["name"],
            "parts_count": len(parsed.get("parts") or []),
            "bom": parsed.get("bom") or [],
            "price_summary": parsed.get("price_summary") or {},
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        }

    vse = [_serial(r) for r in rows]
    # ZAKLADNI sestava je dal NEJSTARSI navazana, NE prvni v seznamu.
    # Drive to bylo totez (razeni bylo podle id), od zmeny razeni vyse uz
    # ne - a nesmi se to splest: puvodni vada, kvuli ktere "nejstarsi =
    # zakladni" vzniklo, byla prave ta, ze karta ukazovala jinou sestavu,
    # nez se schvalovalo (viz PLAN_TVORBY_SESTAV.md, faze 3). Razeni je
    # vec zobrazeni, volba zastupce vec vyznamu - nesmi na sobe viset.
    zakladni = min(vse, key=lambda a: a["id"])
    return jsonify({"assembly": zakladni, "assemblies": vse})


@app.get("/api/shop/products/<int:shop_product_id>/assemblies")
def product_assemblies_public(shop_product_id):
    """VEREJNE (bez auth) - varianty sestavy pro produktovou stranku.

    Robert 2026-09-10: *"kdo stavi ten detail produktove sestavy na webu?
    postavit"*. Jedna skladova karta muze mit navazanych vic sestav a kazda
    je jedna varianta.

    ZMENA 2026-09-11 (Robert, po prvnim skutecnem pripade s rozdilnymi
    cenami 24-32 tis. Kc na jedne karte): *"posuvník mění celý kusovník a
    tím i cenu"* - puvodni pravidlo "prepina POUZE obrazkem" uz NEPLATI,
    cena jde ven spolu s obrazkem. Kusovnik (rozpis dilu) ale VEREJNE
    NEJDE DAL - Robert vyslovne: *"Jen cena, kusovník zůstává vnitřní."*
    Rozpis prozrazuje konstrukci skoro jako geometrie.

    Co se tu ZAMERNE NEVRACI a proc:
      * `data` (geometrie dilu) - ochrana 3D modelu sestav (Robert
        2026-09-06: verejne jde ven jen otocka, zadna geometrie).
      * `bom` (kusovnik) - viz vyse, zustava vyhradne v adminu.
    `price_czk` je VYJIMKA z pravidla "cena nejde ven" u `bom`/
    `price_summary` - je to jen FINALNI cislo (bez rozpisu), zastupci
    (`is_master`) beri cenu z `shop_products.price_czk_placeholder`
    (rucne nastavena Robertem), ostatni varianty z `price_summary.
    total_czk`.

    OPRAVA KOMENTARE (bot5, 2026-09-12): stalo tu "bez marze, protoze
    zadna neni nikde nastavena (koeficient konfiguratoru je 1.0)". UZ TO
    NEPLATI a byl to nebezpecny omyl ke zdedeni - `app_settings.
    scene_price_coefficient` (2026-09-12: 1.4, od 2026-09-25: 1.25; od
    2026-10-01 jen na profily a produkty z Dogusu, viz katalog() v app.py)
    je marze a v `price_summary` UZ JE ZAPECENA. Overeno na datech 2026-09-12
    (sestavy 347/348): kusova polozka se zakladni cenou 5 Kc ma v
    kusovniku 7 Kc a polozka za 17 Kc ma 24 Kc - pomer 1.400.
    Koeficient se aplikuje jednou, v `/api/katalog` (viz `katalog()` v
    app.py), tedy uz v cenach dilu, ze kterych se kusovnik pocita.
    **Nenasobit ho tady podruhe** - presne pred tim varuje i
    `price_summary.scene_price_coefficient_applied` (otisk pro davkove
    prepocty, viz admin_settings.py). Kdo by veril puvodnimu komentari,
    pripocetl by marzi jeste jednou a zakaznik by platil 1.96x naklad.
    """
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            # ⭐ DVOJI OCHRANA (bot5, 2026-09-16, navazuje na nalez z handoveru
            # + bot9 navrh v PLAN_TVORBY_SESTAV.md, komit 43acc130): tenhle
            # endpoint je VEREJNY BEZ AUTH a byl jedinou vrstvou ochrany
            # disciplina "neaktivovat kartu/nenapojovat neschvalenou sestavu
            # predcasne" - zadny filtr tu samotny SQL nemel. Overeno naziv:
            # neaktivni karta (active=0, cekajici na render) svoje sestavy
            # klidne vracela vcetne ceny/vahy/kod_sestavy komukoli, kdo znal
            # ID. Ted DVE nezavisle podminky primo v dotazech:
            #   1) shop_products.active=1 - karta jeste neni "na prodej"
            #   2) product_assemblies.technicky_ok=1 - sestava jeste neprosla
            #      geometrickou kontrolou (viz vsechny predchozi nalezy v
            #      teto session: horni_blok "00" vyjimka, Ford Connect,
            #      Vito Compact - vsude se sestava napojovala na kartu AZ po
            #      technicky_ok=1, tohle to jen vynucuje i v kodu, ne jen
            #      v disciplina bota, ktery kartu zaklada).
            # Interni preview VSECH variant (vc. neschvalenych) ma svoji
            # VLASTNI, staff-only cestu - /api/admin/product-assemblies/
            # by-product/<id> (require_permission produkty_sklad/zobrazit) -
            # tenhle verejny endpoint pro to nikdy nebyl urceny (jediny
            # volajici je webapp/product.html).
            cur.execute("SELECT price_czk_placeholder FROM shop_products WHERE id=%s AND active=1", (shop_product_id,))
            sp = cur.fetchone()
            if not sp:
                return jsonify({"assemblies": []})
            master_price = sp["price_czk_placeholder"]
            cur.execute(
                # Stejne razeni jako v adminu vyse (podle kodu, ne podle
                # poradi vzniku) - zakaznik na posuvniku by jinak jezdil po
                # provedenich v nahodnem poradi. Zastupce se tu nebere podle
                # poradi, ale podle `is_master`, takze zmena razeni nic
                # jineho neovlivnuje.
                # LEFT JOIN na katalogove dimenze (TEXT_FILTR.md pravidlo 13:
                # "popisy jsou dynamické podle vybrané sestavy") - zakaznicky
                # text se pise JEDNOU na katalogovou variantu
                # (horni_blok_varianty/typologie_varianty.popis_zakaznicky),
                # ne na kazdou sestavu zvlast, viz komentar u sestaveni JSON
                # nize.
                "SELECT pa.id, pa.name, pa.data, pa.is_master, pa.kod_sestavy, pa.verze, "
                "hb.popis_zakaznicky AS popis_horni_blok, "
                "hb.kod AS horni_blok_kod, hb.nazev AS horni_blok_nazev, "
                "tv.nazev AS typologie_nazev, "
                "ru.kotveni_zakaznicky AS kotveni_umisteni, "
                "ru.montaz_zakaznicky AS montaz_umisteni "
                "FROM product_assemblies pa "
                "LEFT JOIN horni_blok_varianty hb ON hb.id = pa.horni_blok_varianta_id "
                "LEFT JOIN typologie_varianty tv ON tv.id = pa.typologie_varianta_id "
                # Montaz zavisi na UMISTENI (kam se regal kotvi), NE na
                # horni bloku/typologii (co je nad euroboxy) - overeno
                # bot8 na 12 sestavach postavenych od nuly: kotevni body na
                # patach nohou vysly identicke napric vsemi horni-blok
                # variantami. Samostatny JOIN, samostatna kategorie textu.
                "LEFT JOIN regal_umisteni ru ON ru.id = pa.umisteni_id "
                "WHERE pa.shop_product_id=%s AND pa.technicky_ok=1 "
                "ORDER BY pa.kod_sestavy IS NULL, pa.kod_sestavy, pa.id",
                (shop_product_id,),
            )
            rows = cur.fetchall()
            if not rows:
                return jsonify({"assemblies": []})
            # Ktere varianty uz maji aktivni davku otocky. Jeden dotaz pro
            # vsechny - ne N dotazu v cyklu.
            cur.execute(
                "SELECT DISTINCT assembly_id FROM product_turntable_frames "
                "WHERE shop_product_id=%s AND is_active=1 AND assembly_id IS NOT NULL",
                (shop_product_id,),
            )
            s_otockou = {r["assembly_id"] for r in cur.fetchall()}
    finally:
        conn.close()
    def _odvozene_ceny(r):
        # Jedno spolecne mesto pro vsechny ceny odvozene z `data` (JSON) -
        # drive se `data` parsovalo 2x (_price_for/_montaz_for) zvlast,
        # ted jednou. `price_czk`/`montaz_cena_czk`/`boxy_cena_czk` jsou
        # VZDY "jen finalni cislo, ne rozpis" (Robert: "Jen cena, kusovník
        # zůstává vnitřní.") - `bom` samotny se dal NEVRACI.
        #
        # `weight_kg`/`montaz_cena_czk`/`boxy_cena_czk` (bot5, 2026-09-15)
        # se NA ROZDIL od `price_czk` NEROZLISUJI podle is_master - puvodni
        # komentar tady tvrdil "zastupce nema zadnou zapecenou
        # price_summary", coz neplati (overeno primo v datech, napr.
        # sestava 344/master ma price_summary.weight_kg=18.996 i
        # montaz_czk=4875 uplne normalne spocitane, bom obsahuje realne
        # euroboxy) - zastupce JE realna sestava jako kterakoli jina, jen
        # jeho CENA se schvalne prebira rucne (price_czk_placeholder).
        # Puvodni "vsechno kromě ceny na null" u zastupce zpusobovalo
        # skutecny bug (Robert pres bot3, 2026-09-15: "okno pro pridavani
        # sluzeb chybi, pri urcitych polohach posuvniku zmizel") - montaz/
        # boxy zmizely presne jen pro tu jednu variantu, ktera je zrovna
        # zastupcem, misto aby se chovaly stejne jako u vsech ostatnich.
        try:
            parsed = json.loads(r["data"]) if r["data"] else {}
        except (ValueError, TypeError):
            parsed = {}
        ps = parsed.get("price_summary") or {}
        weight = ps.get("weight_kg")
        montaz = ps.get("montaz_czk")
        boxy = _eurobox_soucet_czk(parsed.get("bom"))
        if r["is_master"]:
            price = master_price
        else:
            total = ps.get("total_czk")
            price = round(total) if total is not None else None
        return {
            "price_czk": price,
            "montaz_cena_czk": round(montaz) if montaz is not None else None,
            "boxy_cena_czk": boxy,
            "weight_kg": round(weight, 1) if weight is not None else None,
        }

    return jsonify({"assemblies": [
        {
            # `verejny_popisek_sestavy` ORezava kod karoserie a interni
            # poznamky - viz jeji komentar v app.py. Syrovy `r["name"]` se
            # tudy posilal do 2026-09-12 a unikal jim (nalezl bot3 pri
            # zapnuti karet 3943/3944/3945).
            "id": r["id"], "name": verejny_popisek_sestavy(r["name"]),
            "has_turntable": r["id"] in s_otockou,
            "is_master": bool(r["is_master"]),
            # Strukturovane osy pro dvouposuvnikovy vyber (Robert
            # 2026-09-14: "myslel jsem ze na horni blok bude jeden
            # posuvnik a na varianty ABC bude druhy posuvnik") - `verze`
            # (A/B/C...) je skladba boxu, `horni_blok_kod`/`_nazev` je
            # provedeni nad euroboxy. Stejna kategorie pole jako uz
            # existujici `kod_sestavy` nize (strukturovany identifikator,
            # ne marketingovy text) - NEOREZAVAT verejny_popisek_sestavy.
            "verze": r["verze"],
            "horni_blok_kod": r["horni_blok_kod"],
            "horni_blok_nazev": r["horni_blok_nazev"],
            "typologie_nazev": r["typologie_nazev"],
            # `montaz_cena_czk` (TEXT_FILTR.md pravidlo 14a) - cena montaze
            # jako VOLITELNE nabizene sluzby, NENI soucasti `price_czk`
            # nize. Jmenovano "_cena_" a ne `montaz_czk`, aby se to nepletlo
            # s `montaz_varianty` nize (to je POPISNY text o zpusobu
            # montaze, tohle je CISLO).
            # `boxy_cena_czk` (Robert 2026-09-13: volba "bez boxů" vedle
            # montáže - "při zatržení se odečtou boxy") - soucet cen
            # radku eurobox_* v kusovniku, JE soucasti `price_czk` (na
            # rozdil od montaze) - odectena se az na zaklade volby
            # zakaznika, viz cart.py/_eurobox_soucet_czk. `None`, kdyz
            # sestava zadne euroboxy neobsahuje (frontend pak checkbox
            # "bez boxů" vubec nenabidne).
            **_odvozene_ceny(r),
            # `kod_sestavy` (Robert 2026-09-13: "na detailu se musí zobrazovat
            # aktuální SKU vyobrazené sestavy") - ZAMERNE NEOREZANO
            # `verejny_popisek_sestavy()`, na rozdil od `name` vyse. Tenhle
            # kod NENI marketingovy text/popis - je to STRUKTUROVANY
            # produktovy kod (stejna kategorie pole jako uz existujici
            # `shop_products.sku`, ktery se na teto strance dnes zobrazuje
            # jako "Kód produktu" a K-XXX uz obsahuje). Pravidlo 25 (K-XXX
            # nepatri do zakaznickeho TEXTU) mirilo na popisna/marketingova
            # pole (nazev, popis) - kod produktu je jina kategorie, jeho
            # ucel je prave byt strukturovanym identifikatorem.
            "kod_sestavy": r["kod_sestavy"],
            # `popis_varianty` (TEXT_FILTR.md pravidlo 13, 2026-09-13) -
            # PUVODNE slozeno ze dvou katalogovych vet (konfigurace boxu +
            # horni blok). Robert 2026-09-14: "v beznem textu popisu
            # detailu nechci popisovat boxy ale at jsou pocty a velikosti
            # v dynamicke tabulce" - vetu o poctech/velikostech boxu
            # (typologie_varianty.popis_zakaznicky) uz sem NEDAVAT, misto
            # ni frontend stavi tabulku primo z `typologie_nazev` (viz
            # nize - strukturovany format "220x3-170x3-120x2", jeden
            # katalogovy zdroj pro obojí). Zustava jen veta o hornim bloku.
            "popis_varianty": r["popis_horni_blok"] or "",
            # `montaz_varianty` (TEXT_FILTR.md pravidla 12+13, doplneno
            # 2026-09-13: "Stejné pravidlo platí i pro popis ohledně
            # montáže.") - ZAMERNE SAMOSTATNE pole, ne slite do
            # `popis_varianty` vyse: montaz je vlastni oddil (pravidlo 12),
            # ne soucast obecneho popisu. Skladany zdroj je taky jiny -
            # `regal_umisteni`, ne katalog horniho bloku/typologie (viz JOIN
            # vyse a jeho komentar proc).
            # `kotveni_varianty` (TEXT_FILTR.md pravidlo 14b, doplneno
            # 2026-09-13: "Kotvení je vlastní oddělená, dynamická část
            # popisu"). Stejny zdroj jako montaz_varianty (`regal_umisteni`,
            # oboji zavisi na umisteni, ne na hornim bloku), ale VLASTNI
            # pole - kotveni (KAM se pripevnuje) a montaz (JAK se montuje,
            # vc. vrtani/homologace) jsou dva samostatne oddily na strance.
            "kotveni_varianty": r["kotveni_umisteni"],
            "montaz_varianty": r["montaz_umisteni"],
        }
        for r in rows
    ]})


def _build_product_assembly_category_tree(cur):
    cur.execute(
        "SELECT id, parent_id, name, sort_order FROM product_assembly_categories "
        "ORDER BY parent_id IS NULL DESC, sort_order, name"
    )
    rows = cur.fetchall()
    by_parent = {}
    for r in rows:
        by_parent.setdefault(r["parent_id"], []).append(r)

    def build(parent_id):
        return [
            {"id": r["id"], "name": r["name"], "sort_order": r["sort_order"], "children": build(r["id"])}
            for r in by_parent.get(parent_id, [])
        ]

    return build(None)


@app.get("/api/product-assembly-categories")
@staff_required
def product_assembly_categories_list():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            tree = _build_product_assembly_category_tree(cur)
    finally:
        conn.close()
    return jsonify({"tree": tree})


@app.post("/api/product-assembly-categories")
@admin_required
def product_assembly_categories_create():
    body = request.get_json(silent=True) or {}
    name = (body.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Vyplň název kategorie."}), 400
    parent_id = body.get("parent_id")
    user = current_user()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            if parent_id is not None:
                cur.execute("SELECT id FROM product_assembly_categories WHERE id=%s", (parent_id,))
                if not cur.fetchone():
                    return jsonify({"error": "Nadřazená kategorie neexistuje."}), 400
            cur.execute(
                "INSERT INTO product_assembly_categories (parent_id, name, created_by) VALUES (%s,%s,%s)",
                (parent_id, name, user["id"]),
            )
            new_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()
    log_audit(user["id"], "create", "product_assembly_category", new_id, name)
    return jsonify({"status": "ok", "id": new_id}), 201


@app.put("/api/product-assembly-categories/<int:cat_id>")
@admin_required
def product_assembly_categories_update(cat_id):
    user_id = current_user()["id"]
    body = request.get_json(silent=True) or {}
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM product_assembly_categories WHERE id=%s", (cat_id,))
            if not cur.fetchone():
                return jsonify({"error": "Kategorie neexistuje."}), 404
            fields, params = [], []
            if "name" in body:
                name = (body.get("name") or "").strip()
                if not name:
                    return jsonify({"error": "Vyplň název kategorie."}), 400
                fields.append("name=%s"); params.append(name)
            if "parent_id" in body:
                new_parent = body.get("parent_id")
                if new_parent is not None:
                    cur.execute("SELECT id FROM product_assembly_categories WHERE id=%s", (new_parent,))
                    if not cur.fetchone():
                        return jsonify({"error": "Nadřazená kategorie neexistuje."}), 400
                    cur.execute("SELECT id, parent_id FROM product_assembly_categories")
                    parent_of = {r["id"]: r["parent_id"] for r in cur.fetchall()}
                    walker, seen = new_parent, set()
                    while walker is not None:
                        if walker == cat_id:
                            return jsonify({"error": "Nelze přesunout kategorii do sebe/vlastního podstromu."}), 400
                        if walker in seen:
                            break
                        seen.add(walker)
                        walker = parent_of.get(walker)
                fields.append("parent_id=%s"); params.append(new_parent)
            if "sort_order" in body:
                try:
                    sort_order = int(body.get("sort_order") or 0)
                except (TypeError, ValueError):
                    return jsonify({"error": "Neplatné pořadí."}), 400
                fields.append("sort_order=%s"); params.append(sort_order)
            if not fields:
                return jsonify({"error": "Nic ke změně."}), 400
            params.append(cat_id)
            cur.execute(f"UPDATE product_assembly_categories SET {', '.join(fields)} WHERE id=%s", params)
        conn.commit()
    finally:
        conn.close()
    log_audit(user_id, "update", "product_assembly_category", cat_id, ", ".join(fields))
    return jsonify({"status": "ok"})


@app.delete("/api/product-assembly-categories/<int:cat_id>")
@admin_required
def product_assembly_categories_delete(cat_id):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM product_assembly_categories WHERE id=%s", (cat_id,))
            if not cur.fetchone():
                return jsonify({"error": "Kategorie neexistuje."}), 404
            cur.execute("DELETE FROM product_assembly_categories WHERE id=%s", (cat_id,))
        conn.commit()
    finally:
        conn.close()
    log_audit(current_user()["id"], "delete", "product_assembly_category", cat_id, None)
    return jsonify({"status": "ok"})
