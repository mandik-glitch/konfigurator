#!/usr/bin/env python3
"""2026-09-09_turntable_render.py - zaradi otocny nahled produktove
sestavy do renderovaci fronty (bot8, Robert 2026-09-09).

Zapisuje POUZE dva soubory do RENDER_OUT_DIR - `<job>.json` (uloha) a
`<job>.status.json` se stavem `waiting_worker`. Vic netreba: agent na
Robertove GPU stanici si ulohu vyzvedne sam pri nejblizsim pollu
(api/render_worker.py::render_worker_poll). Zamerne se tu NEIMPORTUJE
Flask aplikace - skript ma jit spustit i z cronu bez ni.

    api/venv/bin/python3 scripts/2026-09-09_turntable_render.py 134 \
        [--template /cesta/sablona.blend] [--local]

--local  = renderovat na TOMHLE serveru (CPU, hodiny) misto na GPU. Jen
           pro ladeni; stav se nastavi na `queued` a musi se spustit
           blender rucne (vypise se prikaz).

ZARAZENI VYZADUJE KLIC (Robert 2026-09-11: "dej si na renderovaci ulohu
zamek a klíč abys vedel jen ty bot3"). Klic drzi bot3; cesta k nemu je v
promenne prostredi KONFIGURATOR_RENDER_KLIC_SOUBOR. Plati pro VSECHNY
rezimy vcetne --test, --prstenec a --local. Kontrola je hned na zacatku
main(), takze bez klice se nezalozi ani docasny soubor. Podrobne vcetne
toho, co zamek NEPOKRYVA: scripts/_render_klic.py.

Stav ulohy se pak da sledovat v `<job>.status.json`; hotove snimky
najdes v `<job>.frames/`. Prehled celeho procesu: PRODUKTOVE_RENDERY.md.
"""
import argparse
import importlib.util
import json
import glob
import os
import re
import sys
import time
import uuid

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RENDER_OUT_DIR = os.path.join(REPO, "private-files", "blender-renders")
TURNTABLE_SCRIPT = os.path.join(REPO, "api", "blender_render_turntable.py")
DRIVE_FILES_DIR = os.path.join(REPO, "private-files", "shared-drive")
# Rucni celoplosne zastaveni (Robert, 2026-09-25: netmave zbarveni eurobox
# nahledu produktu 3957 proti stejne barve na jinych kartach - "do te doby
# zastav rendery", nez se najde skutecna pricina). Jediny soubor, kontroluje
# ho VSECHNO co zaraduje render (nativni i --shop-product-id/Vandr jdou
# oba pres tento skript jako spolecny bod, viz auto-dispatch subprocess).
# Zamerne NENI v DEPLOY_LOCK.json guardovanych cestach (jen webapp/+api/*.py) -
# smaze/vytvori ho kdokoli primo, bez zamku, aby zastaveni/uvolneni bylo
# okamzite i pro ostatni boty.
RENDER_POZASTAVEN_SOUBOR = os.path.join(REPO, "private-files", "RENDER_POZASTAVEN.json")

# Odolne dohledani souboru na Sdilenem disku (mrtve id -> podle nazvu).
# Modul zamerne neimportuje Flask, takze jde pouzit i odsud, mimo appku.
sys.path.insert(0, os.path.join(REPO, "api"))
import shared_drive_pointer as sdp  # noqa: E402

sys.path.insert(0, os.path.join(REPO, "scripts"))
import _render_klic  # noqa: E402

# DILNA UZ NEEXISTUJE. Robert 2026-09-10: "smazat dilna", "vps_dilna.blend
# smazat at te nenapada tam renderovat". GUI Blender na VPS si driv kazdych
# 10 s ukladal snapshot sceny do vps_dilna.blend a KAZDY render ho bral jako
# sablonu. Ted ma nastaveni renderu jediny zdroj: Robertuv .blend na
# Sdilenem disku, vybrany pres app_settings.render_template_file_id
# (viz sablona_ze_sdileneho_disku nize). Konstanta je zamerne pryc, aby uz
# na tu cestu nikdo nesahl; sluzba blender-gui.service je vypnuta.

# Robert 2026-09-09: "ty do toho porad jebes proto se to zmenilo" - dilna
# na VPS se pri kazdem restartu sluzby prepisovala, takze jeho nastaveni
# nebylo v bezpeci. Tahle slozka je JEHO: ulozi si sem .blend pres
# File > Save As a zadny bot na nej nesaha. Ma PREDNOST pred dilnou.
SABLONA_DIR = os.path.join(REPO, "private-files", "shared-drive-named",
                           "Rendering", "SABLONA")


def sablona_ze_sdileneho_disku():
    """.blend vybrany v `app_settings.render_template_file_id`.

    Robert 2026-09-10: "nastaveni renderu musi byt jako je X30-01 na
    sdilenem disku" + "smazat dilna". Sablona se proto uz nebere z dilny na
    VPS, ale ze Sdileneho disku - stejnym mechanismem jako HDRI mapa,
    tedy ID zaznamu v `shared_drive_files`.

    PROC PRES DB A NE PRES CESTU: odvozeny strom `shared-drive-named` se
    ukazal jako nespolehlivy - 2026-09-10 v nem lezel rozbity symlink
    `X30-1.blend` (cil ze Sdileneho disku zmizel) a soubor
    `X30-1_opraveno.blend`, ktery v databazi vubec nebyl. Podle nazvu v tom
    stromu to vypadalo jako Robertuv soubor, a pritom nebyl. Zdroj pravdy
    je tabulka, ne adresar.

    PROC I PODLE NAZVU (bot9, 2026-09-11): Robert soubor pri kazde uprave
    SMAZE a nahraje novy, takze se `id` meni - 2026-09-10 dvakrat za vecer
    (1784 -> 2058 -> 2064) a pokazde to nekdo musel prepnout rucne. Kdyz je
    `id` mrtve, ukazatel se dohleda podle nazvu a rovnou uzdravi. Kdyz se
    nenajde ani tak, vraci se NENALEZENO a volajici to MUSI ohlasit hlasite;
    drivejsi tiche spadnuti na vestavene vychozi hodnoty bylo horsi nez chyba.

    Vraci (stav, cesta, popis) - viz api/shared_drive_pointer.py.
    """
    return _najdi_na_disku("render_template_file_id", "render_template_file_name")


def _aktivni_uloha_sestavy(assembly_id, shop_product_id=None):
    """Uz ceka/bezi uloha na tuhle sestavu? Vraci (job_id, stav), nebo None.

    Idempotence (bot9, 2026-09-11): bez teto kontroly vyrobi opakovane
    spusteni dve davky nad tymz produktem a ta druha prvni prepise - obe
    pritom stoji hodiny GPU. Za "aktivni" se berou jen stavy, ve kterych si
    ulohu worker jeste muze vzit nebo uz na ni pracuje; hotove, chybne a
    zrusene ulohy prekazet nemaji.

    Vandr karty (bot4 2026-09-23) nemaji assembly_id (None) - shodny None
    by jinak spojil DVA RUZNE Vandr produkty jako "kolizi", takze se v tom
    pripade matchuje podle shop_product_id misto toho."""
    AKTIVNI = ("queued", "waiting_worker", "running")
    try:
        soubory = [f for f in os.listdir(RENDER_OUT_DIR) if f.endswith(".status.json")]
    except OSError:
        return None
    for nazev in sorted(soubory):
        try:
            with open(os.path.join(RENDER_OUT_DIR, nazev), encoding="utf-8") as fh:
                st = json.load(fh)
        except (OSError, ValueError):
            continue        # rozbity/rozepsany stav neblokuje zarazeni
        if st.get("state") not in AKTIVNI:
            continue
        if assembly_id is not None:
            if st.get("assembly_id") == assembly_id:
                return nazev[: -len(".status.json")], st.get("state")
        elif shop_product_id is not None and st.get("assembly_id") is None \
                and st.get("shop_product_id") == shop_product_id:
            return nazev[: -len(".status.json")], st.get("state")
    return None


def _najdi_na_disku(klic_id, klic_nazev):
    """Obal nad shared_drive_pointer.najdi_soubor s vlastnim spojenim."""
    conn = _spojeni()
    if conn is None:
        return sdp.NENALEZENO, None, "nelze se pripojit k databazi"
    try:
        with conn.cursor() as cur:
            vysledek = sdp.najdi_soubor(cur, klic_id, klic_nazev, DRIVE_FILES_DIR)
        conn.commit()   # uzdraveny ukazatel se musi ulozit
        return vysledek
    except Exception as e:
        return sdp.NENALEZENO, None, "chyba pri dohledavani: %s" % e
    finally:
        conn.close()


def _nazev_sablony():
    """Puvodni nazev vybrane sablony (pripravena kopie ma hashovany nazev,
    ktery Robertovi nic nerekne)."""
    _stav, _cesta, popis = sablona_ze_sdileneho_disku()
    return popis or "?"


def sablona_od_roberta():
    """Nejnovejsi .blend, ktery si Robert ulozil do Rendering/SABLONA.

    Zustava jako druha moznost pro pripad, ze si slozku zalozi a bude do ni
    ukladat primo z Blenderu. K 2026-09-10 slozka na disku neexistuje.
    """
    try:
        soubory = [os.path.join(SABLONA_DIR, f) for f in os.listdir(SABLONA_DIR)
                   if f.lower().endswith(".blend")]
    except OSError:
        return None
    soubory = [f for f in soubory if os.path.isfile(f)]
    if not soubory:
        return None
    return max(soubory, key=os.path.getmtime)

# job builder lezi vedle (nazev zacina cislicemi - nejde importovat primo)
_spec = importlib.util.spec_from_file_location(
    "turntable_job", os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                  "2026-09-09_turntable_job.py"))
tj = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tj)


def _najdi_blender():
    """Nejnovejsi nainstalovany Blender (stejna logika jako
    api/blender_render.py::_najdi_blender - tenhle skript zamerne
    neimportuje Flask aplikaci, aby sel pustit i z cronu).

    bot8 2026-09-09: pevna cesta na /opt/blender-official (4.2.9) tise
    rozbijela pripravu sablony - Robert uklada v 5.2.1 a starsi Blender
    novejsi .blend NEOTEVRE. Navenek to vypadalo jen jako "VAROVANI:
    priprava sablony selhala, pouzivam original". Radi se CISELNE:
    retezcove by "official" prebilo "5.2" ('o' > '5').
    """
    kandidati = []
    for cesta in glob.glob("/opt/blender-*/blender"):
        znacka = os.path.basename(os.path.dirname(cesta)).split("-", 1)[1]
        try:
            verze = tuple(int(c) for c in znacka.split("."))
        except ValueError:
            verze = (0,)
        kandidati.append((verze, cesta))
    return max(kandidati)[1] if kandidati else "/usr/bin/blender"


BLENDER_BIN = _najdi_blender()
PRIPRAV_SKRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "2026-09-09_vps_dilna", "priprav_sablonu.py")


def _spojeni():
    """Spojeni do DB pres pymysql. Tenhle skript zamerne NEIMPORTUJE Flask
    aplikaci, aby sel spustit i z cronu."""
    try:
        import pymysql
    except ImportError:
        return None
    env = {}
    try:
        with open(os.path.join(REPO, "api", ".env"), encoding="utf-8") as fh:
            for radek in fh:
                radek = radek.strip()
                if radek and not radek.startswith("#") and "=" in radek:
                    k, v = radek.split("=", 1)
                    env[k] = v
    except OSError:
        return None
    try:
        return pymysql.connect(
            host=env.get("DB_HOST", "127.0.0.1"), port=int(env.get("DB_PORT", 3306)),
            user=env.get("DB_USER", ""), password=env.get("DB_PASSWORD", ""),
            database=env.get("DB_NAME", ""), cursorclass=pymysql.cursors.DictCursor)
    except Exception:
        return None


# _nastaveni() a _soubor_sdileneho_disku() odsud zmizely (bot9, 2026-09-11):
# obe delaly presne to, co ted resi api/shared_drive_pointer.py, jen bez
# dohledani podle nazvu. Dve cesty k temuz ukazateli by se rozesly.


def vybrane_hdri():
    """Cesta k HDRI mape, kterou si Robert vybral v administraci
    (Sdileny disk -> u .hdr/.exr souboru tlacitko "pouzit pro render"),
    nebo nic nevybrano = pouzije se ta, kterou ma ulozenou ve svem .blend.
    Ulozeno v app_settings pod klicem render_hdri_file_id, viz
    api/render_hdri.py.

    Stejna odolnost jako u sablony (bot9, 2026-09-11): kdyz je `id` mrtve,
    dohleda se podle nazvu a ukazatel se uzdravi.

    Vraci (stav, cesta, popis) - viz api/shared_drive_pointer.py.
    """
    return _najdi_na_disku("render_hdri_file_id", "render_hdri_file_name")


# Robert 2026-09-28: "modern_buildings < zakaz pouzivani" - tahle HDRI se
# nesmi pouzit pro ZADNY render (automat, test, --hdri), ani kdyby ji nekdo
# znovu nahral na Sdileny disk. Soubor tam lezi pod hashem, proto se
# kontroluje i puvodni nazev ze shared_drive_files.
ZAKAZANE_HDRI = ("modern_buildings",)


def zkontroluj_zakazanou_hdri(cesta, popis=None):
    """SystemExit, kdyz je `cesta` (nebo jeji puvodni nazev na Sdilenem
    disku) zakazana HDRI mapa."""
    if not cesta:
        return
    jmena = [os.path.basename(cesta), popis or ""]
    conn = _spojeni()
    if conn is None:
        raise SystemExit("Nelze overit, jestli HDRI %s neni zakazana (databaze nedostupna)." % cesta)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT filename FROM shared_drive_files WHERE stored_filename=%s",
                        (os.path.basename(cesta),))
            jmena += [r["filename"] for r in cur.fetchall()]
    finally:
        conn.close()
    for jmeno in jmena:
        if any(z in (jmeno or "").lower() for z in ZAKAZANE_HDRI):
            raise SystemExit("HDRI %s je ZAKAZANA (Robert 2026-09-28: modern_buildings "
                             "se nesmi pouzivat). Render se nespousti." % jmeno)


def vychozi_hdri_rotace_deg():
    """Trvale nastaveny vychozi uhel rotace HDRI (stupne, kolem svisle
    Z osy), nebo None = zadny (world se neotaci, puvodni chovani).
    Ulozeno v app_settings pod klicem render_hdri_rotace_deg, viz
    api/render_hdri.py::render_hdri_rotace_set.

    bot16, 2026-09-12 (zadani bot3/bot4): Robert potvrdil "120 stupnu je
    od ted preferovany uhel pro vsechny dalsi sestavy" - bot4 to do ted
    resil rucne (--hdri-rotace-deg 120 u kazdeho renderu zvlast). Tohle
    je ten trvaly vychozi zdroj, --hdri-rotace-deg na prikazove radce ho
    porad muze pro JEDNU davku prebit (viz priprav_sablonu nize), stejny
    vzor jako --hdri vuci vybrane_hdri().
    """
    conn = _spojeni()
    if conn is None:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT setting_value FROM app_settings WHERE setting_key='render_hdri_rotace_deg'")
            row = cur.fetchone()
        if not row or row["setting_value"] in (None, ""):
            return None
        try:
            return float(row["setting_value"])
        except (TypeError, ValueError):
            return None
    finally:
        conn.close()


def _seznam_obrazku_z_tabulky():
    """JSON {nazev_souboru: plna_cesta} pro dohledani CHYBEJICICH obrazku
    sablony - postaveny z tabulky `shared_drive_files`, ne z adresare.

    Robert 2026-09-11: *"HDRI mas ve sdilenem disku tak si to udelas sam"*.
    Priprava sablony (priprav_sablonu.py) hledala nahrady jen prochazenim
    odvozeneho stromu `shared-drive-named/`, a ten je nespolehlivy - tyz
    den v nem lezel rozbity symlink `canary_wharf_4k.exr` na blob, ktery
    uz neexistoval. Zdroj pravdy je tabulka; adresar zustava jako zaloha
    (jsou v nem i rucni kopie, ktere v tabulce nejsou - dnes prave
    `docklands_01_4k.hdr` a `crossfit_gym_2k.exr`, na ktere X30-1 odkazuje).

    Vraci cestu k docasnemu souboru, nebo None (pak jede jen adresar).
    """
    conn = _spojeni()
    if conn is None:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT filename, stored_filename FROM shared_drive_files "
                        "WHERE LOWER(filename) LIKE '%.hdr' OR LOWER(filename) LIKE '%.exr' "
                        "OR LOWER(filename) LIKE '%.jpg' OR LOWER(filename) LIKE '%.jpeg' "
                        "OR LOWER(filename) LIKE '%.png' OR LOWER(filename) LIKE '%.tif' "
                        "OR LOWER(filename) LIKE '%.tiff'")
            radky = cur.fetchall()
    except Exception:
        return None
    finally:
        conn.close()
    mapa = {}
    for r in radky:
        mapa.setdefault(r["filename"], os.path.join(
            REPO, "private-files", "shared-drive", r["stored_filename"]))
    if not mapa:
        return None
    cesta = os.path.join(RENDER_OUT_DIR, "_obrazky_disku.json")
    os.makedirs(RENDER_OUT_DIR, exist_ok=True)
    tmp = cesta + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(mapa, fh, ensure_ascii=False)
    os.replace(tmp, cesta)
    return cesta


def priprav_sablonu(path, hdri_override=None, hdri_rotace_deg=None):
    """Sablona s CHYBEJICIMI obrazky by na GPU stanici vyrenderovala
    fialovou (Blender uklada jen cestu k obrazku, ne obrazek). Robertuv
    X30-1.blend odkazuje na jeho stary notebook - proto se chybejici
    obrazky dohledaji podle nazvu na Sdilenem disku, prepoji a zabali.

    Robertuv ORIGINAL se nikdy nemeni (jeho pravidlo) - vyrabi se kopie
    vedle, v RENDER_OUT_DIR. Kopie se pouzije znovu, dokud je novejsi nez
    zdroj, takze se 67MB soubor nepreklada u kazde ulohy.

    `hdri_override` (bot3, 2026-09-12): jednorazova HDRI cesta pro TUHLE
    davku, misto ctení z app_settings.render_hdri_file_id. Nic neuklada,
    nic v administraci nemeni - kdyz Robert chce novou mapu natrvalo,
    porad se prepina tam (viz --hdri v argparse nize).

    `hdri_rotace_deg` (bot16, 2026-09-12, zadani Robert pres bot3): jednorazovy
    uhel (stupne, kolem svisle Z osy) pro TUHLE davku - kdyz je None (nebylo
    predano, tj. --hdri-rotace-deg na prikazove radce chybi), pouzije se
    TRVALY vychozi uhel z app_settings (vychozi_hdri_rotace_deg(), stejny
    princip jako `hdri_override` vuci vybrane_hdri() o par radku vyse).
    Aplikuje se i kdyz se HDRI soubor sam nemeni (rotace stavajici mapy
    sablony).
    """
    import hashlib
    import subprocess
    if hdri_rotace_deg is None:
        hdri_rotace_deg = vychozi_hdri_rotace_deg()  # muze zustat None (nic trvale nenastaveno)
    if hdri_override:
        stav_hdri, hdri, popis_hdri = None, hdri_override, hdri_override
    else:
        # Vybrana HDRI je soucasti klice - jinak by se po prepnuti mapy
        # vratila kopie "z drivejska" s tou starou a Robert by videl, ze se
        # jeho volba neprojevila.
        stav_hdri, hdri, popis_hdri = vybrane_hdri()
        # Vybrana HDRI je nastavena, ale nedohledatelna = renderovat dal by tise
        # pouzilo mapu z .blend a Robert by videl, ze se jeho volba neprojevila
        # (presne ten druh tiche chyby, kvuli kteremu tahle vetev vznikla).
        if stav_hdri == sdp.NENALEZENO:
            raise SystemExit("HDRI mapa vybrana v administraci nejde dohledat: %s" % popis_hdri)
    zkontroluj_zakazanou_hdri(hdri, popis_hdri)
    seznam = _seznam_obrazku_z_tabulky()
    # Uhel je soucasti klice ze stejneho duvodu jako HDRI o par radku vyse -
    # jinak by ruzne uhly na stejne sablone+HDRI sdilely jednu (spatne
    # otocenou) "z drivejska" kopii.
    klic = hashlib.sha1(("%s|%s|%s" % (os.path.abspath(path), hdri or "", hdri_rotace_deg or 0)).encode()).hexdigest()[:12]
    hotovo = os.path.join(RENDER_OUT_DIR, "sablona_%s.blend" % klic)
    if os.path.exists(hotovo) and os.path.getmtime(hotovo) >= os.path.getmtime(path):
        return hotovo, "z drivejska"
    os.makedirs(RENDER_OUT_DIR, exist_ok=True)
    if hdri_override:
        print("  HDRI override (jednorazove, --hdri): %s" % os.path.basename(hdri))
    elif hdri:
        print("  HDRI podle vyberu v administraci: %s" % os.path.basename(hdri))
    if hdri_rotace_deg:
        print("  HDRI rotace (jednorazove, --hdri-rotace-deg): %.1f stupnu" % hdri_rotace_deg)
    if stav_hdri == sdp.UZDRAVENO:
        print("  POZOR: %s" % popis_hdri)
    try:
        out = subprocess.run([BLENDER_BIN, "-b", "-noaudio", path,
                              "-P", PRIPRAV_SKRIPT, "--", hotovo, hdri or "", seznam or "",
                              str(hdri_rotace_deg) if hdri_rotace_deg else ""],
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             text=True, timeout=900).stdout
    except Exception as e:
        print("  VAROVANI: pripravu sablony nelze spustit (%r), pouzivam original" % e)
        return path, "neupraveno"
    souhrn = next((l for l in out.splitlines() if l.startswith("SOUHRN")), "")
    if "PRIPRAVENO" not in out or not os.path.exists(hotovo):
        print("  VAROVANI: priprava sablony selhala, pouzivam original")
        return path, "neupraveno"
    try:
        os.chmod(hotovo, 0o644)
    except OSError:
        pass
    return hotovo, souhrn or "doplneno"


def _write_status(job, **fields):
    fields.setdefault("updated", time.time())
    path = os.path.join(RENDER_OUT_DIR, "%s.status.json" % job)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(fields, fh, ensure_ascii=False)
    os.replace(tmp, path)


def main():
    ap = argparse.ArgumentParser(description="Zaradi otocny nahled sestavy do fronty")
    ap.add_argument("assembly_id", type=int, nargs="?", default=None,
                    help="product_assemblies.id (nativni Logiman sestavy) - "
                         "nepovinne, kdyz je zadano --shop-product-id (Vandr)")
    ap.add_argument("--shop-product-id", type=int, default=None, metavar="ID",
                    help="Vandr karta (shop_products.sku LIKE 'VD-%%') - misto "
                         "pozicniho assembly_id, ZADNY product_assemblies radek "
                         "se nepouziva (bot4 2026-09-23, viz build_job_vandr()).")
    ap.add_argument("--template", default=None,
                    help="jina .blend sablona nez ta vybrana na Sdilenem disku")
    ap.add_argument("--samples", type=int, default=None, metavar="N",
                    help="vynuti pocet Cycles vzorku jen pro TUHLE davku, misto "
                         "app_settings.render_samples - pro rychlou diagnostiku "
                         "(napr. 'je scena jen pomala na pripravu, nebo fakt zaseknuta' "
                         "- bot4 2026-09-12). Nic v administraci netrvale nemeni.")
    ap.add_argument("--hdri", default=None, metavar="CESTA",
                    help="vynuti konkretni HDRI mapu (cesta k .hdr/.exr) jen pro TUHLE "
                         "davku, misto ctení app_settings.render_hdri_file_id. Nic v "
                         "administraci netrvale nemeni - pro trvalou zmenu vychozi mapy "
                         "pouzij vyber v admin oknu renderu (PUT /api/admin/render-hdri).")
    ap.add_argument("--hdri-rotace-deg", type=float, default=None, metavar="STUPNE",
                    dest="hdri_rotace_deg",
                    help="otoc HDRI mapu kolem svisle (Z) osy o zadany pocet stupnu, "
                         "jen pro TUHLE davku (Robert pres bot3 2026-09-12: chce "
                         "zkusit natoceni po 30 stupnich, 12 pozic 0-330). Vklada/pouziva "
                         "Mapping uzel mezi Texture Coordinate (Generated) a Environment "
                         "Texture teto sablony - viz priprav_sablonu.py. Nic v "
                         "administraci netrvale nemeni.")
    ap.add_argument("--hdri-sila", type=float, default=None, metavar="NASOBEK",
                    dest="hdri_sila",
                    help="Robert 2026-09-20 (vanDrawee, 'porad prilis svetla'): "
                         "vynasobi silu World Background uzlu (vychozi sablony "
                         "1.0) timhle cislem, jen pro TUHLE davku. Nic v "
                         "administraci netrvale nemeni.")
    ap.add_argument("--bez-sablony", "--bez-dilny", action="store_true", dest="bez_dilny",
                    help="zadna sablona - renderovat s vestavenymi vychozimi "
                         "hodnotami Blenderu (--bez-dilny je stary nazev teze volby)")
    ap.add_argument("--local", action="store_true", help="renderovat na serveru (CPU), ne na GPU")
    ap.add_argument("--worker", default=None, metavar="JMENO",
                    help="bot4 2026-09-29 (Robert: renderovat i u nej na notebooku): jmeno "
                         "stroje (hostname agenta), na kterem se ma uloha vyrenderovat. "
                         "Bez tohohle jde uloha na vychozi GPU stanici. Uloha s cilem se "
                         "NIKDY neprevezme jinym strojem ani serverem - ceka na nej.")
    ap.add_argument("--jen-hdri", action="store_true", dest="jen_hdri",
                    help="Robert 2026-09-20 (vanDrawee): odstranit vsechna svetla "
                         "ze sablony (SUN/area/point), osvetleni jen z HDRI world")
    ap.add_argument("--alu-realny", action="store_true", dest="alu_realny",
                    help="Robert 2026-09-26 ('hlinik reanejsi'): hlinik vsude (nase "
                         "profily i Vandr) pouzije ORIGINALNI material ze sablony "
                         "s velikosti zrna a reliefu prepocitanou pro milimetrovou "
                         "scenu (sablona je v metrech). Vychozi stav VYPNUTO. "
                         "Zrno a relief ladi --alu-tile-mm a --alu-disp-mult.")
    ap.add_argument("--alu-tile-mm", type=float, default=None, metavar="MM", dest="alu_tile_mm",
                    help="delka strany jednoho opakovani textury hliniku v mm "
                         "(jen s --alu-realny; bez zadani 40 = dnesni hodnota, "
                         "Robertova sablona ma 0.5)")
    ap.add_argument("--alu-disp-mult", type=float, default=None, metavar="NASOBEK", dest="alu_disp_mult",
                    help="nasobek sily reliefu hliniku (jen s --alu-realny; 1000 "
                         "prepocte metrovou sablonu na milimetrovou scenu)")
    ap.add_argument("--cycles-robert", action="store_true", dest="cycles_robert",
                    help="Robert 2026-09-26: nastaveni Cycles z jeho Blenderu - sablona ho uz "
                         "nese skoro cele, lisi se jen glossy odrazy (4 misto 5) a clamp "
                         "indirect (10 misto 0). Jen pro testy. Vychozi VYPNUTO.")
    ap.add_argument("--alu-uv-mm", type=float, default=None, metavar="MM", dest="alu_uv_mm",
                    help="Robert 2026-09-26 ('Alumi2 nema meritko'): hlinikovym dilum dat "
                         "kubicke UV se SKUTECNOU velikosti vzoru MM milimetru na jedno "
                         "opakovani (misto promitani/nesmyslnych UV), aby meritko i normalova "
                         "mapa (kartacovani) fungovaly stejne jako v Blenderu. Jen s "
                         "--alu-material. Vychozi VYPNUTO.")
    ap.add_argument("--hdri-azimut-pomer", type=float, default=None, metavar="POMER", dest="hdri_azimut_pomer",
                    help="Robert 2026-09-27: 'HDRI tocime lehce mensim krokem jako azimuty' - "
                         "HDRI se otaci SPOLU s kamerou na kazdem snimku otocky (ne staticky "
                         "pro celou davku), o POMER * krok kamery (1.0 = stejny krok jako "
                         "kamera, 0.5 = poloviční). Pri prednim pohledu (front_azimuth_deg) "
                         "beze zmeny. Vychozi 0.0 (HDRI staticke, dnesni chovani).")
    ap.add_argument("--kryci-listy-debug", action="store_true", dest="kryci_listy_debug",
                    help="DOCASNE ladici: obarvi kryci listy jasnou magentou (emise), aby "
                         "bylo videt presne kde na snimku jsou. Jen pro hledani, nepouzivat "
                         "produkcne. Vychozi VYPNUTO.")
    ap.add_argument("--kryci-listy-pruhledne", action="store_true", dest="kryci_listy_pruhledne",
                    help="Robert 2026-09-27: 'sedy material na krycich listach je flekaty, "
                         "drsny... kdyz dam pruhlednost 100%% nebudou videt a bude tam stin' - "
                         "kryci listy v drazce profilu (Vandr) dostanou uplne pruhledny material "
                         "(Alpha=0) misto sede barvy. Vychozi VYPNUTO (zustavaji sede).")
    ap.add_argument("--vd-puvodni-nevyplnene", action="store_true", dest="vd_puvodni_nevyplnene",
                    help="Robert 2026-09-28: 'nevyplnene materialy nech se nasadi puvodni co si "
                         "nese objekt sebou' - Vandr dily bez radku v tabulce prirazeni si necha "
                         "material z modelu (zadna vychozi VD_ nahrada, hlinik ze sablony jen kdyz "
                         "je vyplneny radek hliniku). Pridava ho tabulka prirazeni sama.")
    ap.add_argument("--alu-ao-sila", type=float, default=None, metavar="0-1", dest="alu_ao_sila",
                    help="Robert 2026-09-27: 'drazky by mely byt tmavsi, rohy a zakouti take "
                         "jakoby ve stinu' - prida Ambient Occlusion do hlinikoveho materialu "
                         "(0 = beze zmeny, 1 = plny efekt). Na rozdil od key_svetlo funguje "
                         "stejne na kazdem snimku otocky, ne jen z jednoho uhlu. Vychozi VYPNUTO.")
    ap.add_argument("--alu-ao-vzdalenost-mm", type=float, default=None, metavar="MM", dest="alu_ao_vzdalenost_mm",
                    help="jen s --alu-ao-sila: jak daleko AO 'vidi' (vychozi 8 mm - hloubka "
                         "typicke drazky profilu). Vetsi cislo = tmavne i sirsi/hlubsi zakouti.")
    ap.add_argument("--plast-svetly-tmava-sila", type=float, default=None, metavar="0-1", dest="plast_svetly_tmava_sila",
                    help="ztmavi material plast_svetly (kryci listy v drazce, #666c73) - jen kdyz "
                         "NEJSOU schovane pres --kryci-listy-pruhledne, jinak neni na cem videt "
                         "efekt. 0 = beze zmeny, 1 = cerna. Vychozi VYPNUTO.")
    ap.add_argument("--cub-seda-tmava-sila", type=float, default=None, metavar="0-1", dest="cub_seda_tmava_sila",
                    help="Robert 2026-09-28 (test HDRi 'telocvicna'): 'hlinik je hezky, ale sedy "
                         "plast nam zbelal' - to je material 'CUB seda (Instance)*' (#bbbbbb v "
                         "GLB, viditelny sedy panel), NE plast_svetly (ten je jen na schovanych "
                         "krycich listach). Ztmavi nasobenim barvy cislem (1-sila), 0 = beze "
                         "zmeny, 1 = cerna. Vychozi VYPNUTO.")
    ap.add_argument("--key-svetlo-jen-alu", action="store_true", dest="key_svetlo_jen_alu",
                    help="jen s --key-svetlo: svetlo sviti VYHRADNE na hlinikove dily (Blender "
                         "light linking), desky/boxy/ostatni material timhle svetlem nesviceny. "
                         "Robert 2026-09-27: 'bila deska a bile drazky nejsou akceptovatelne'. "
                         "Vychozi VYPNUTO (svetlo sviti na vsechno jako driv).")
    ap.add_argument("--key-svetlo-elevace", type=float, default=None, metavar="STUPNE", dest="key_svetlo_elevace",
                    help="jen s --key-svetlo: elevace svetla vuci cili (vychozi 55 = skoro "
                         "shora). Nizsi cislo = vic ze strany, min na vodorovne plochy.")
    ap.add_argument("--key-svetlo-azimut-posun", type=float, default=None, metavar="STUPNE", dest="key_svetlo_azimut_posun",
                    help="jen s --key-svetlo: posun azimutu svetla vuci kamere (vychozi -57).")
    ap.add_argument("--key-svetlo-polomer", type=float, default=None, metavar="NASOBEK", dest="key_svetlo_polomer",
                    help="jen s --key-svetlo: nasobek velikosti zdroje (vychozi 1.0). Mensi "
                         "cislo = ostrejsi, koncentrovanejsi odlesk pri stejnem vykonu; vetsi "
                         "= mekci, rozlity.")
    ap.add_argument("--plosna-svetla", type=int, default=None, metavar="POCET", dest="plosna_svetla",
                    help="Robert 2026-09-26: pridat POCET plosnych svetel v NAHODNEM smeru "
                         "(elevace 25-70, azimut 0-360, pevne ve svete), spise slabsi. "
                         "Jen pro A/B testy jednoho snimku. Vychozi VYPNUTO.")
    ap.add_argument("--plosna-sila", type=float, default=None, metavar="NASOBEK", dest="plosna_sila",
                    help="sila plosnych svetel (vychozi 0.3 = slabsi; 1.0 ~ ekvivalent bodoveho "
                         "svetla z Robertovy zkusebni sceny)")
    ap.add_argument("--plosna-seed", type=int, default=None, metavar="CISLO", dest="plosna_seed",
                    help="seminko nahody pro smer plosnych svetel (vychozi 7)")
    ap.add_argument("--key-svetlo", type=float, default=None, metavar="NASOBEK", dest="key_svetlo",
                    help="Robert 2026-09-26 (hlinik 'malo kovovy'): pridat bodove svetlo "
                         "jako v jeho zkusebni scene (1000 W, ~7.2x polomer sestavy, 57 st. "
                         "vedle kamery, 55 st. nad cilem, vykon skalovan podle velikosti "
                         "sestavy). NASOBEK 1.0 = ekvivalent jeho scene. Jen pro A/B testy "
                         "jednoho snimku. Vychozi VYPNUTO.")
    ap.add_argument("--svetla-blend", default=None, metavar="SOUBOR.blend", dest="svetla_blend",
                    help="Robert 2026-09-29 ('nastaveni svetel podle nejakeho souboru', "
                         "X1_SCENA.blend): osvetleni = svetla z tohoto .blend (bodova/spot/"
                         "plosna/slunce) misto vestavenych i sablonovych. Poloha a vykon se "
                         "prepocitaji na velikost sestavy (1 jednotka souboru = polomer "
                         "sestavy), svetla se otaceji s kamerou. HDRI/world zustava z panelu.")
    ap.add_argument("--svetla-jen", action="append", default=None, metavar="JMENO", dest="svetla_jen",
                    help="jen s --svetla-blend: pouzit JEN svetlo tohoto jmena (lze opakovat); "
                         "bez prepinace se pouziji vsechna svetla souboru. Svetlo, ktere v "
                         "souboru neni, je chyba.")
    ap.add_argument("--svetla-sila", type=float, default=None, metavar="NASOBEK", dest="svetla_sila",
                    help="jen s --svetla-blend: nasobek vykonu vsech svetel (vychozi 1.0)")
    ap.add_argument("--svetla-meritko", type=float, default=None, metavar="NASOBEK", dest="svetla_meritko",
                    help="jen s --svetla-blend: nasobek vzdalenosti/velikosti svetel vuci "
                         "sestave (vychozi 1.0; vykon se skaluje tak, aby ozareni zustalo)")
    ap.add_argument("--alu-material", default=None, metavar="JMENO", dest="alu_material",
                    help="Robert 2026-09-26 ('zkus jiny nez Sandblasted'): jmeno JINEHO "
                         "hlinikoveho materialu z VD_ knihovny (viz --vd-knihovna) misto "
                         "'Sandblasted aluminium', pro nase profily i Vandr. Jen pro "
                         "A/B testy jednoho snimku. Vychozi VYPNUTO.")
    ap.add_argument("--vd-knihovna", default=None, metavar="CESTA", dest="vd_knihovna",
                    help="Jina knihovna VD_ materialu (.blend) nez vychozi vd_materialy.blend "
                         "- jen pro testy (napr. knihovna s ALUTEST_* materialy). Soubor "
                         "musi byt citelny pro www-data (server ho posila workeru).")
    ap.add_argument("--klt-material", default=None, metavar="JMENO", dest="klt_material",
                    help="Robert 2026-09-28 ('Blue_GloPLA.blend, aplikuj na celo supliku'): "
                         "jmeno materialu z VD_ knihovny (--vd-knihovna) misto puvodniho "
                         "'blue KLT' na supliku/KLT boxu. Jen pro A/B testy. Vychozi VYPNUTO.")
    ap.add_argument("--vd-nahrada", action="append", default=None, metavar="RODINA[@TYP]=MATERIAL",
                    dest="vd_nahrada",
                    help="Robert 2026-09-28 ('každý materiál udělej jeden řádek'): rodina "
                         "materialu Vandr GLB (napr. 'CUB seda', 'blue KLT', 'black' - jmeno "
                         "bez '(Instance).NNN') -> material z --vd-knihovna. Volitelne @TYP = jen "
                         "dily daneho typu (multibox, vysuvklt, boxpolice, suplik... viz "
                         "_render_prirazeni_lib.TYPY_DILU). Lze vicekrat.")
    ap.add_argument("--vd-role", action="append", default=None, metavar="ROLE[@TYP]=MATERIAL",
                    dest="vd_role",
                    help="Robert 2026-09-28 ('v různých sestavách mají multiboxy různý materiál'): "
                         "ROLE dilu = skupina primo nad dilem v exportu (klic jen pismena, napr. "
                         "multiboxarc, drawer, darkgreybin, blueklt, plastgr) -> material z "
                         "--vd-knihovna; ma prednost pred --vd-nahrada. @TYP = jen v danem typu "
                         "komponenty. Lze vicekrat.")
    ap.add_argument("--klt-debug", action="store_true", dest="klt_debug",
                    help="docasna jasna barva (jina pro kazdy objekt) na vsechny 'blue KLT' "
                         "dily, at jde v renderu rozeznat cast od casti (hledani 'ktery kus "
                         "je opravdu celo supliku'). DOCASNE, jen pro hledani.")
    ap.add_argument("--razitka-json", default=None, metavar="CESTA", dest="razitka_json",
                    help="bot10 2026-09-24: JEN s --shop-product-id. Soubor se seznamem razitkovych "
                         "dilu (stejny tvar jako shop_products.vandr_razitka_json), ktery se pouzije "
                         "MISTO DB - nahledy navrhu razitek bez zapisu do DB (vandr-render-dispatch "
                         "timer by jinak pustil ostry render neschvaleneho navrhu).")
    ap.add_argument("--glb-override", default=None, metavar="CESTA", dest="glb_override",
                    help="bot4 2026-10-08: JEN s --shop-product-id. GLB MISTO katalogoveho (karty stolu z generatoru: model S razitky).")
    ap.add_argument("--predni-azimut", type=float, default=None, metavar="STUPNE", dest="predni_azimut",
                    help="bot4 2026-10-08: s --glb-override otockovy azimut cela (z extras.v3d.front).")
    ap.add_argument("--vd-tint", action="append", default=None, metavar="SHODA:#rrggbb:MIX",
                    dest="vd_tint",
                    help="Robert 2026-09-23 (vanDrawee, 'kazdy testovaci render ponese "
                         "material hliniku/cela suplíku/vyplne'): pro material, jehoz "
                         "jmeno obsahuje SHODA (case-insensitive, stejny podretezec jako "
                         "'alu'/'tyrkys'/'klt'/'cub'/... v blender_render_turntable.py), "
                         "smicha jeho puvodni barvu/texturu se zadanym #rrggbb v pomeru "
                         "MIX (0=beze zmeny, 1=cista cilova barva). Zadne z realnych VD_/"
                         "ALU materialu nemaji hotovou druhou variantu (overeno primo v "
                         ".blend souborech) - tohle je jednorazovy prekryv PRO TUHLE "
                         "davku, nic v knihovne na disku se netrvale nemeni. Lze zadat "
                         "vicekrat (ruzne SHODA).")
    ap.add_argument("--test", action="store_true",
                    help="JEN JEDEN snimek na ladeni sceny/sablony. Od pravidla "
                         "29 je to TOTEZ co --prstenec (hero still uz neexistuje).")
    ap.add_argument("--prstenec", action="store_true",
                    help="JEN JEDEN snimek Z OTACECI SADY (ctvercovy master "
                         "prstence, predni azimut) misto plnych 162")
    ap.add_argument("--jen-vodorovne", action="store_true", dest="jen_vodorovne",
                    help="Robert 2026-09-27: 'zatim budeme delat jenom vodorovne "
                         "rendery' - CELA otocka (vsechny azimuty), ale jen "
                         "elevace 0 (horni/dolni pohledy vynechany). Na rozdil "
                         "od --elevace (jen pro --test/--prstenec) funguje i pro "
                         "plnou davku a prepocitava expected_frames.")
    ap.add_argument("--bez-commitu", action="store_true", dest="bez_commitu",
                    help="CELA otocka (54 snimku), ale NEZAKTIVUJE davku - "
                         "snimky se ulozi jako is_active=0, presne jako u "
                         "--test/--prstenec, jen bez omezeni na 1 snimek. "
                         "Robert 2026-09-24 ('Renderovou otočku chci vidět "
                         "pro ten tv'): admin tlacitko 'otestovat render' "
                         "potrebuje CELOU otocku k prohlednuti, ne jen 1 "
                         "snimek, ale zaroven nesmi tise prepsat zivou "
                         "galerii testovane (mozna uz aktivni) karty - "
                         "predtim slo jedno bez druheho (jeden_snimek a "
                         "ingest_bez_commitu byly natvrdo svazane).")
    ap.add_argument("--elevace", type=int, default=None,
                    help="--prstenec bere DEFAULTNE prostredni elevaci (0) - "
                         "timhle se da vybrat jina (napr. -40), aby slo "
                         "jednim snimkem overit opravu specifickou pro "
                         "konkretni pohled. Musi byt hodnota, kterou ma "
                         "sestava v ELEVATIONS (viz api/turntable.py).")
    ap.add_argument("--azimut", type=int, default=None, metavar="STUPNE",
                    help="--prstenec bere DEFAULTNE azimut nejblizsi PREDNIMU "
                         "pohledu sestavy - timhle se da vybrat jiny (napr. "
                         "290), pro porovnani nekolika uhlu stejne sestavy "
                         "(Robert 2026-09-21: 'jeste o dalsi 2 pohledy po "
                         "20 stupnich'). Pouzije se PRESNE zadany uhel (Robert "
                         "2026-09-28), prevzeti ho prijme jen u jednosnimkoveho "
                         "testu, ktery se nikdy neaktivuje.")
    # ONLINE NABIDKA (bot4 2026-10-01): jeden snimek z ZAPISU DILU sceny stejnou cestou jako karta, viz
    # 2026-09-09_turntable_job.py::build_job_nabidka. Spousti to JEN API (api/nabidka_kartova_cesta.py), ne boti.
    ap.add_argument("--nabidka-dily", default=None, metavar="SOUBOR.json", dest="nabidka_dily",
                    help="Rezim ONLINE NABIDKY: JSON seznam dilu ze sceny (part_id/position/quaternion/scale). "
                         "Vyrenderuje se JEDEN snimek (--nabidka-azimut/--nabidka-elevace) a vysledek je PNG "
                         "<job>.png k nabidce, ne davka otocky. Z API (env KONFIGURATOR_NABIDKA_Z_API=1) bez klice "
                         "a pauzy jako POST /api/admin/blender-render (viz scripts/_render_klic.py, 'CO ZAMEK NEPOKRYVA'); "
                         "jinak (bot) jako kazde zarazeni: renderovaci klic + pauza.")
    ap.add_argument("--nabidka-azimut", type=float, default=None, metavar="STUPNE", dest="nabidka_azimut",
                    help="Azimut kamery ve KONVENCI SCENY (camera_azimuth_deg), jen s --nabidka-dily.")
    ap.add_argument("--nabidka-elevace", type=float, default=None, metavar="STUPNE", dest="nabidka_elevace",
                    help="Elevace kamery nad vodorovnou rovinou, jen s --nabidka-dily.")
    ap.add_argument("--nabidka-job", default=None, metavar="ID32", dest="nabidka_job",
                    help="ID ulohy prideleni API (32 hex), aby ho API znalo hned; jinak se vygeneruje.")
    ap.add_argument("--nabidka-uzivatel", type=int, default=None, metavar="ID", dest="nabidka_uzivatel",
                    help="user_id do stavu ulohy (kdo smi ulohu rusit, viz _may_control_job).")
    ap.add_argument("--prevod", default=None, metavar="AgX|Filmic|Standard",
                    help="Vynuti barevny prevod (view_transform) misto "
                         "toho, co ma sablona - viz api/blender_render_"
                         "turntable.py, komentar 'BAREVNY PREVOD'. Bez "
                         "tehle volby se nic nemeni (chovani jako driv). "
                         "Robert 2026-09-11: chce videt AgX/Filmic/Standard "
                         "vedle sebe na tomtez snimku - spustit stejnym "
                         "prikazem 3x s ruznou hodnotou.")
    ap.add_argument("--bg-top", default=None, metavar="#rrggbb",
                    help="Vynuti horni barvu gradientu pozadi (JOB['bg_color']) "
                         "misto TT_BG_COLOR z 2026-09-09_turntable_job.py - "
                         "pro srovnavaci snimky variant bez trvale zmeny "
                         "vychoziho nastaveni (stejny vzor jako --prevod).")
    ap.add_argument("--bg-bottom", default=None, metavar="#rrggbb",
                    help="Totez pro spodni barvu gradientu (JOB['bg_color_bottom']).")
    ap.add_argument("--odrazna-deska", action="store_true",
                    help="Zapne pokusnou odraznou desku nad sestavou (JOB['odrazna_deska']) - "
                         "neviditelna pro kameru, jen pro odlesky, zvlnena, bez stinu, rotuje "
                         "s kamerou po prstenci. Vychozi stav je VYPNUTO. Priznak jde i do "
                         "manifest.json, aby slo zpetne poznat, ktery snimek ji mel zapnutou.")
    ap.add_argument("--odrazna-deska-sklon", type=float, default=None, metavar="STUPNE",
                    help="Elevace desky nad sestavou ve stupnich (vychozi 55 v render "
                         "skriptu) - fotoatelierovy uhel 'shora napred', ne primo nad hlavou.")
    ap.add_argument("--odrazna-deska-vzdalenost", type=float, default=None, metavar="FAKTOR",
                    help="Vzdalenost desky od stredu sestavy jako nasobek MAX_DIM sestavy "
                         "(vychozi 1.3).")
    ap.add_argument("--odrazna-deska-svit", type=float, default=None, metavar="SILA",
                    help="Sila vlastniho emisniho svitu desky (Principled Emission Strength, "
                         "vychozi 3.0) - deska musi svitit, jinak nema co odrazet (jen "
                         "prostredi HDRI). Moc vysoka hodnota by mohla presvitit HDRI.")
    ap.add_argument("--karoserie-odrazy", action="store_true",
                    help="Zapne SKUTECNOU karoserii (podlaha+boky+prepazka, z auta ktere "
                         "sestava patri) jako hlinikovy odrazovy povrch - neviditelna pro "
                         "kameru, bez stinu, jen v odleskach (JOB['karoserie_odrazy']). "
                         "Kdyz se karoserie k sestave nenajde nebo je zmerena vyska "
                         "implausible, potichu (ale hlasite v logu) spadne na chovani bez "
                         "ni. Robert 2026-09-11 pres bot3: 'souhlasim s pouzitim karoserie "
                         "na odrazy... muze mit klidne hlinik jako material'. Vychozi VYPNUTO.")
    ap.add_argument("--karoserie-odrazy-drsnost", type=float, default=None, metavar="ROUGHNESS",
                    help="Drsnost (Principled BSDF Roughness, 0=zrcadlo..1=matny) hlinikoveho "
                         "materialu karoserie (vychozi 0.3 v render skriptu - viditelny, ale "
                         "ne oslnivy odraz, realny interier je lakovany plech ne zrcadlo). "
                         "Robert: 'kdyby vyslo prilis zrcadlove, budeme to ladit cislem'.")
    ap.add_argument("--karoserie-podlaha", action="store_true",
                    help="Zapne podlahu jako obrysovou linku vyříznutou z karoserie "
                         "(JOB['karoserie_podlaha'], data z JOB['podlaha_obrys'] - vodorovny "
                         "rez kousek nad podlahou karoserie, hlavni obrys jako konvexni "
                         "obal). PROTOTYP jen pro K-075 (Fiat Doblo) - u jinych vozidel "
                         "'podlaha_obrys.ok' bude False a prepinac se tise (ale hlasite v "
                         "logu) neuplatni. Na rozdil od --karoserie-odrazy je VIDITELNA pro "
                         "kameru (ma byt videt, ne jen v odleskach) a materiál je matny "
                         "(Robert: 'podlaha dodávky je překližka nebo plech s protiskluzem, "
                         "ne zrcadlo'). Robert 2026-09-11 pres bot3, vychozi VYPNUTO.")
    a = ap.parse_args()
    if a.worker and a.local:
        ap.error("--worker a --local nejdou dohromady (cil je GPU stroj, --local je CPU serveru)")
    if a.svetla_jen and not a.svetla_blend:
        ap.error("--svetla-jen vyzaduje --svetla-blend (jinak by se vyber svetel tise ignoroval)")
    nabidka = bool(a.nabidka_dily)
    if nabidka:
        if a.nabidka_azimut is None or a.nabidka_elevace is None:
            ap.error("--nabidka-dily vyzaduje --nabidka-azimut a --nabidka-elevace")
        if a.nabidka_job is not None and not re.fullmatch(r"[0-9a-f]{32}", a.nabidka_job):
            ap.error("--nabidka-job: ocekavam 32 hex znaku")
        if a.assembly_id is not None or a.shop_product_id is not None or a.test or a.prstenec or a.local:
            ap.error("--nabidka-dily nejde kombinovat s assembly_id/--shop-product-id/--test/--prstenec/--local")
    elif a.nabidka_azimut is not None or a.nabidka_elevace is not None or a.nabidka_job or a.nabidka_uzivatel is not None:
        ap.error("--nabidka-azimut/-elevace/-job/-uzivatel patri jen k --nabidka-dily")

    # ---- ZAMEK: bez klice se nezaradi NIC -------------------------------
    # Musi byt PRVNI vec po parsovani argumentu. Nize uz skript sahá do DB,
    # kopiruje sablonu do RENDER_OUT_DIR a zaklada docasne soubory - kdyby
    # se kontrola delala az pred zapisem stavu, odmitnuty beh by po sobe
    # nechal odpad. Plati pro vsechny rezimy vcetne --test/--prstenec/--local
    # (duvod, proc i pro ne, je v hlavicce scripts/_render_klic.py).
    nabidka_api = nabidka and os.environ.get("KONFIGURATOR_NABIDKA_Z_API") == "1"
    if nabidka_api:
        # Online nabidku zaraduje API na zadani uzivatele z prohlizece (stejna vrstva jako POST /api/admin/blender-render,
        # ktera je zamerne nezamcena) - ani klic, ani pauza se na ni nevztahuji (jen s env KONFIGURATOR_NABIDKA_Z_API=1, nastavuje API).
        klic_otisk, kdo = None, "api-nabidka"
    else:
        # vcetne --nabidka-dily mimo API (bot4 2026-10-07: rendery produktu bez obrazku, Robertuv pokyn): jen drzitel klice a pauza plati
        klic_otisk = _render_klic.over_klic("zařazení otočky do renderovací fronty")
        kdo = _render_klic.kdo_zaradil()

    # ---- POZASTAVENO: Robert 2026-09-25 -------------------------------
    # "to neakceptuju jako vysvětlení, zjisti proc je to tmavsí, do té
    # deby zastav rendery" + "vsechny rendery musi mít stejný kabát nemuze
    # být každý jinak" - dokud se nenajde skutecna pricina ruzneho vzhledu
    # (produkt 3957 tmavsi nez sousedni karty se stejnym color_hex), nove
    # rendery se nezaraduji vubec. Kontrola AZ PO klici (klic hlida KDO smi
    # renderovat, tohle hlida JESTLI se sma renderovat vubec cokoli prave
    # ted) - odstranit smazanim RENDER_POZASTAVEN_SOUBOR, az bude pricina
    # jasna a pripadne oprava sjednocujici vzhled hotova.
    # VYJIMKA jen pro JEDNOSNIMKOVY test bot4 (Robert 2026-09-26, vyslovne
    # "Ano, pust testy hliniku" na dotaz, zda smi bot4 upravit zamek tak, ze
    # propusti jen jeho jednosnimkove testy; pauza sama zustava): drive se
    # pauza pro test ZVEDALA smazanim souboru a automat se do toho okna
    # vklouzl (14:40:07 vznikla ostra otocka VW Transporter T6 L1, 54
    # snimku, proti Robertovu "zastavit rendery"). Misto zvedani pauzy proto
    # projde JEN volani, ktere je zaroven (a) --test/--prstenec = 1 snimek
    # bez commitu, (b) od bot4 a (c) s RENDER_POZASTAVEN_VYJIMKA=jen-test.
    # Automat ani zadna dalsi cesta tuhle promennou nenastavuje, takze pro ne
    # pauza plati beze zmeny.
    _vyjimka_test = (os.environ.get("RENDER_POZASTAVEN_VYJIMKA") == "jen-test"
                     and (a.test or a.prstenec) and kdo == "bot4")
    # DRUHA VYJIMKA (Robert 2026-09-27, prime a opakovane zadani: "Dej mi ty
    # vole tuhle otočku hned delej" / "vyrabime otocky jen vodorovne material
    # Alu my dva 1" [= Alumi2]) - CELA otocka smi projit pauzou, ale jen kdyz
    # je zaroven (a) --jen-vodorovne (horni/dolni pohledy vynechany, viz
    # duvod u toho prepinace), (b) --bez-commitu (NEAKTIVUJE zadnou zivou
    # kartu - stejna zakladni bezpecnostni vlastnost jako u jen-test), (c)
    # od bot4 a (d) s RENDER_POZASTAVEN_VYJIMKA=jen-vodorovne. Narocnejsi
    # (54-snimkovy) beh nez jednosnimkovy test, proto samostatny, uzsi
    # prepinac - nezamenovat s jen-test.
    _vyjimka_vodorovne = (os.environ.get("RENDER_POZASTAVEN_VYJIMKA") == "jen-vodorovne"
                          and a.jen_vodorovne and a.bez_commitu and kdo == "bot4")
    if os.path.exists(RENDER_POZASTAVEN_SOUBOR) and _vyjimka_test:
        print("POZOR: rendery jsou POZASTAVENY, tenhle jednosnimkovy test (bot4) "
              "projde vyjimkou RENDER_POZASTAVEN_VYJIMKA=jen-test. Pauza dal plati.")
    if os.path.exists(RENDER_POZASTAVEN_SOUBOR) and _vyjimka_vodorovne:
        print("POZOR: rendery jsou POZASTAVENY, tato vodorovna otocka bez commitu (bot4) "
              "projde vyjimkou RENDER_POZASTAVEN_VYJIMKA=jen-vodorovne. Pauza dal plati.")
    if os.path.exists(RENDER_POZASTAVEN_SOUBOR) and not (nabidka_api or _vyjimka_test or _vyjimka_vodorovne):
        with open(RENDER_POZASTAVEN_SOUBOR, encoding="utf-8") as fh:
            _pozastaveno = json.load(fh)
        raise SystemExit(
            "ODMITNUTO: rendery jsou docasne POZASTAVENY (%s).\n"
            "Duvod: %s\n"
            "Zrusit pozastaveni smazanim %s, az bude pricina objasnena." % (
                _pozastaveno.get("od", "?"), _pozastaveno.get("duvod", "?"),
                RENDER_POZASTAVEN_SOUBOR))

    # --test byl driv "jeden HERO still" a --prstenec "jeden snimek prstence" -
    # dva ruzne jedno-snimkove rezimy. WORKFLOW.md pravidlo 29 stills zrusilo,
    # takze hero uz neni z ceho udelat a oba rezimy splynuly v jeden.
    # (bot9, 2026-09-11: predchozi commit 629db00d vyprazdnil stills a tim
    # --test rozbil - `cfg["stills"][0]` padalo na IndexError a i kdyby
    # neslo, uloha by mela nula snimku. Zachyceno hned, nic se nerenderovalo.)
    if a.test:
        a.prstenec = True
    jeden_snimek = a.test or a.prstenec

    if a.template and not os.path.exists(a.template):
        raise SystemExit("Sablona %s neexistuje." % a.template)
    if a.hdri and not os.path.exists(a.hdri):
        raise SystemExit("HDRI %s neexistuje." % a.hdri)
    zkontroluj_zakazanou_hdri(a.hdri)
    sablona_zdroj = None
    if not a.template and not a.bez_dilny:
        # 1) sablona vybrana na Sdilenem disku (app_settings) - hlavni cesta
        stav_sablony, a.template, popis_sablony = sablona_ze_sdileneho_disku()
        # Sablona JE vybrana, ale nedohledatelna -> koncime hlasite.
        # Drive se v tomhle pripade tise propadlo na vestavene vychozi
        # hodnoty a render vypadal, ze probehl v poradku (bot8: stalo se
        # 2026-09-10 dvakrat za vecer po vymene souboru).
        if stav_sablony == sdp.NENALEZENO:
            raise SystemExit(
                "Sablona renderu vybrana v administraci nejde dohledat: %s\n"
                "Render se ZASTAVUJE - jinak by tise pouzil vestavene vychozi "
                "hodnoty misto Robertova nastaveni. Vyber sablonu znovu na "
                "Sdilenem disku." % popis_sablony)
        if stav_sablony == sdp.UZDRAVENO:
            print("POZOR: %s" % popis_sablony)
        sablona_zdroj = "Sdileny disk" if a.template else None
        # 2) jinak slozka Rendering/SABLONA, pokud si ji Robert zalozi
        if not a.template:
            a.template = sablona_od_roberta()
            sablona_zdroj = "Rendering/SABLONA" if a.template else None
        # Dilna na VPS uz se NEPOUZIVA (Robert 2026-09-10: "smazat dilna") -
        # nastaveni renderu ma jediny zdroj, a tim je Robertuv .blend na
        # Sdilenem disku. Kdyby zadny nebyl, renderuje se s vestavenymi
        # vychozimi hodnotami a skript to nize vypise.
    sablona_pozn = None
    # Vyresit uhel JEDNOU tady (ne az uvnitr priprav_sablonu) - hlavni
    # duvod: admin panel "detail aktualne zpracovavane ulohy" (bot4,
    # 2026-09-12) potrebuje vedet, jaky uhel se OPRAVDU pouzil (vc.
    # trvaleho vychoziho z administrace), ne jen jestli byl na prikazove
    # radce explicitni --hdri-rotace-deg.
    hdri_rotace_deg_pouzita = a.hdri_rotace_deg if a.hdri_rotace_deg is not None else vychozi_hdri_rotace_deg()
    if a.template:
        a.template, sablona_pozn = priprav_sablonu(a.template, hdri_override=a.hdri,
                                                    hdri_rotace_deg=hdri_rotace_deg_pouzita)

    if not nabidka and (a.assembly_id is None) == (a.shop_product_id is None):
        raise SystemExit("Zadej PRAVE JEDNO z: assembly_id (nativni Logiman) "
                         "nebo --shop-product-id (Vandr), ne oboje ani zadne.")

    job = a.nabidka_job or uuid.uuid4().hex
    out_dir = os.path.join(RENDER_OUT_DIR, "%s.frames" % job)
    if nabidka:
        try:
            with open(a.nabidka_dily, encoding="utf-8") as fh:
                dily_nabidky = json.load(fh)
            cfg = tj.build_job_nabidka(dily_nabidky, out_dir, a.nabidka_azimut, a.nabidka_elevace)
        except (tj.NabidkaNeniKartovaCesta, OSError, ValueError) as e:
            # Navratovy kod 3 + radek NABIDKA_NEJDE: API pozna "nejde kartovou cestou" a spadne na starou cestu (GLB).
            print("NABIDKA_NEJDE: %s" % e)
            sys.exit(3)
        cfg["ucel"] = "nabidka"
        cfg["nabidka_vystup"] = os.path.join(RENDER_OUT_DIR, "%s.png" % job)
    elif a.shop_product_id is not None:
        # Vandr karta - zadny product_assemblies radek, viz build_job_vandr().
        # "vyzadovat_produkt" tu nedava smysl (shop_product_id uz je zadany
        # primo), jeden_snimek/commit rozliseni resi dal stejny kod jako
        # u nativni cesty (ingest_bez_commitu).
        razitka_override = None
        if a.razitka_json:
            with open(a.razitka_json, encoding="utf-8") as fh:
                razitka_override = json.load(fh)
            if not isinstance(razitka_override, list):
                raise SystemExit("--razitka-json musi obsahovat JSON seznam razitkovych dilu.")
        cfg = tj.build_job_vandr(a.shop_product_id, out_dir, razitka_override=razitka_override,
                                 glb_override=a.glb_override,
                                 predni_azimut_override=(int(round(a.predni_azimut)) % 360 if a.predni_azimut is not None else None))
    else:
        # Zkusebni jeden snimek se k produktu commitnout nedá, takze u nej
        # navazany produkt nevyzadujeme (viz tj.build_job).
        cfg = tj.build_job(a.assembly_id, out_dir, vyzadovat_produkt=not jeden_snimek)
    cfg["job_type"] = "turntable"
    if a.jen_vodorovne:
        # Robert 2026-09-27: "zatim budeme delat jenom vodorovne rendery" -
        # horni/dolni elevace (kamera shora/zdola do vnitrku polic) jsou
        # prirozene tmave (overeno: i BEZ nasich uprav, jen fyzika uhlu
        # pohledu) a zatim se neresi. Na rozdil od --elevace (jen pro
        # jednosnimkovy test/prstenec) tohle omezuje CELOU otocku (vsechny
        # azimuty) na jedinou elevaci 0 - prepocita i ocekavany pocet
        # snimku, aby souhlasil se skutecnym poctem vyrenderovanych.
        cfg["elevations"] = [0] if 0 in cfg["elevations"] else cfg["elevations"][:1]
        cfg["expected_frames"] = len(cfg["elevations"]) * len(cfg["azimuths"]) * len(cfg["tiers"])
        print("JEN VODOROVNE: elevace omezena na %s, ocekavano %d snimku"
              % (cfg["elevations"], cfg["expected_frames"]))
    if a.samples is not None:
        cfg["samples"] = max(1, min(4096, a.samples))
    if a.prevod:
        cfg["view_transform"] = a.prevod
    if a.bg_top:
        cfg["bg_color"] = a.bg_top
    if a.bg_bottom:
        cfg["bg_color_bottom"] = a.bg_bottom
    if a.odrazna_deska:
        cfg["odrazna_deska"] = True
    if a.odrazna_deska_sklon is not None:
        cfg["odrazna_deska_sklon_el"] = a.odrazna_deska_sklon
    if a.odrazna_deska_vzdalenost is not None:
        cfg["odrazna_deska_vzdalenost_faktor"] = a.odrazna_deska_vzdalenost
    if a.odrazna_deska_svit is not None:
        cfg["odrazna_deska_svit"] = a.odrazna_deska_svit
    if a.karoserie_odrazy:
        cfg["karoserie_odrazy"] = True
    if a.karoserie_odrazy_drsnost is not None:
        cfg["karoserie_odrazy_drsnost"] = a.karoserie_odrazy_drsnost
    if a.karoserie_podlaha:
        cfg["karoserie_podlaha"] = True
    if a.jen_hdri:
        cfg["jen_hdri"] = True
    if a.alu_realny:
        cfg["alu_realny"] = True
    if a.alu_tile_mm is not None:
        cfg["alu_tile_mm"] = a.alu_tile_mm
    if a.alu_disp_mult is not None:
        cfg["alu_disp_mult"] = a.alu_disp_mult
    if a.vd_tint:
        prekryvy = []
        for zaznam in a.vd_tint:
            try:
                shoda, hexc, mix = zaznam.split(":")
                if not hexc.startswith("#") or len(hexc) != 7:
                    raise ValueError("hex musi byt ve tvaru #rrggbb")
                prekryvy.append({"match": shoda.lower(), "hex": hexc, "mix": float(mix)})
            except ValueError as e:
                raise SystemExit("--vd-tint '%s' neplatny (cekam SHODA:#rrggbb:MIX): %s" % (zaznam, e))
        cfg["vd_tint_overrides"] = prekryvy
    if a.hdri_sila is not None:
        cfg["hdri_sila"] = a.hdri_sila
    if a.prstenec:
        # Robert 2026-09-10: "nechci to hero ale snimek z otaceci sady".
        # Hero je TESNY fit (2048x1536, vlastni vzdalenost kamery), kdezto
        # prstenec je ctvercovy master 2048x2048 s JEDNOU vzdalenosti pro
        # celou sadu - jinak by se sestava mezi snimky "nadechovala". Kdo
        # posuzuje, jak bude vypadat otocny widget, musi videt prstenec.
        # Bereme prostredni elevaci (vodorovny pohled) a PREDNI azimut.
        # POZOR: `azimuths[0]` NENI predni pohled - azimuths_for_front()
        # vraci setrideny vyctu uhlu, ne seznam zacinajici predkem.
        # U sestavy 279 je azimuths[0]=0, ale front_azimuth_deg=90, takze
        # prvni pokus vyrenderoval regal zboku (chyceno 2026-09-10).
        # Bereme proto ten uhel ze sady, ktery je PREDNIMU nejblizsi.
        elev = list(cfg["elevations"])
        if a.elevace is not None:
            if a.elevace not in elev:
                raise SystemExit("--elevace %s neni v ELEVATIONS teto sestavy (%s)."
                                 % (a.elevace, elev))
            el0 = a.elevace
        else:
            el0 = 0 if 0 in elev else elev[len(elev) // 2]
        cil = a.azimut if a.azimut is not None else cfg["front_azimuth_deg"]
        cil = cil % 360

        def _odchylka(az):
            d = abs((az % 360) - cil) % 360
            return min(d, 360 - d)

        if a.azimut is not None:
            # Robert 2026-09-28: "musi udelat uhel jaky mu napisu" - PRESNE
            # zadany uhel. Prevzeti snimku ho prijme jen u tohohle
            # jednosnimkoveho testu (ingest_libovolny_azimut nize, davka se
            # nikdy neaktivuje), otocka dal jen uhly ze sady.
            az0 = cil
        else:
            az0 = min(cfg["azimuths"], key=_odchylka)
        cfg["elevations"] = [el0]
        cfg["azimuths"] = [az0]
        cfg["stills"] = []
        cfg["expected_frames"] = len(cfg["tiers"])
    if a.template:
        cfg["template_blend"] = os.path.abspath(a.template)
    # VD_ material knihovna (bot4 2026-09-21, nativni_material vetev/
    # vanDrawee) - jen kdyz uloha ma aspon jeden takovy dil, at se
    # normalni katalogove ulohy (~748 produktu) nezatezuji prenosem
    # navic. Server-lokalni cesta, worker si ji stahne pres novy
    # vd_materialy_url (viz api/render_worker.py render_worker_tt_job).
    if any(pt.get("nativni_material") for pt in (cfg.get("parts") or [])):
        vd_lib = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "2026-09-21_vd_materialy", "vd_materialy.blend")
        if os.path.exists(vd_lib):
            cfg["vd_materialy_blend"] = vd_lib
    if a.vd_knihovna:
        if not os.path.exists(a.vd_knihovna):
            raise SystemExit("--vd-knihovna: soubor %s neexistuje" % a.vd_knihovna)
        vlastni = os.path.abspath(a.vd_knihovna)
        vychozi = cfg.get("vd_materialy_blend")
        if vychozi and os.path.abspath(vychozi) != vlastni:
            # Robert 2026-09-28 "posrals multiboxy": drive tady vlastni
            # knihovna vychozi vd_materialy.blend NAHRAZOVALA - vsechny
            # ostatni Vandr dily (Multibox VD_KLT_MODRA, VD_CUB_SEDA,
            # VD_BLACK, VD_CHROME, ...) pak spadly na surove glTF barvy.
            # Ted se vzdy SLOUCI (vychozi + vlastni do jedne docasne).
            import _render_prirazeni_lib as _rp
            cfg["vd_materialy_blend"] = _rp.sestav_material_knihovnu(
                [("vychozi", os.path.abspath(vychozi)), ("vlastni", vlastni)])
            print("  VD knihovna: vychozi + %s (slouceno)" % os.path.basename(vlastni))
        else:
            cfg["vd_materialy_blend"] = vlastni
    if a.vd_nahrada:
        nahrady = []
        for polozka in a.vd_nahrada:
            levo, sep, mat = polozka.partition("=")
            rodina, _zav, typ = levo.partition("@")   # RODINA@TYP_DILU (typ volitelny)
            if not sep or not rodina.strip() or not mat.strip():
                raise SystemExit("--vd-nahrada: ocekavam RODINA[@TYP]=MATERIAL, dostal '%s'" % polozka)
            nahrady.append([rodina.strip(), mat.strip(), typ.strip()])
        cfg["vd_nahrady"] = nahrady
    if a.vd_role:
        role = []
        for polozka in a.vd_role:
            levo, sep, mat = polozka.partition("=")
            ro, _zav, typ = levo.partition("@")
            if not sep or not ro.strip() or not mat.strip():
                raise SystemExit("--vd-role: ocekavam ROLE[@TYP]=MATERIAL, dostal '%s'" % polozka)
            role.append([ro.strip().lower(), mat.strip(), typ.strip().lower()])
        cfg["vd_role"] = role
    if a.alu_material:
        cfg["alu_material"] = a.alu_material
    if a.alu_uv_mm is not None:
        cfg["alu_uv_mm"] = a.alu_uv_mm
    if a.cycles_robert:
        cfg["cycles_robert"] = True
    if a.svetla_blend:
        import _render_prirazeni_lib as _rp_sv
        _sv = _rp_sv.svetla_v_souboru(os.path.abspath(a.svetla_blend))
        if not _sv or not _sv.get("svetla"):
            raise SystemExit("--svetla-blend: v souboru '%s' nejsou zadna svetla viditelna v renderu "
                             "(nebo ho nejde precist)." % a.svetla_blend)
        if a.svetla_jen:
            _jmena = [sv["jmeno"] for sv in _sv["svetla"]]
            _chybi = [j for j in a.svetla_jen if j not in _jmena]
            if _chybi:
                raise SystemExit("--svetla-jen: svetlo '%s' v souboru '%s' neni (jsou tam: %s)."
                                 % ("', '".join(_chybi), a.svetla_blend, ", ".join(_jmena)))
            _sv = dict(_sv, svetla=[sv for sv in _sv["svetla"] if sv["jmeno"] in a.svetla_jen])
        cfg["svetla"] = _sv
        cfg["svetla_soubor"] = os.path.basename(a.svetla_blend)
        if a.svetla_sila is not None:
            cfg["svetla_sila"] = a.svetla_sila
        if a.svetla_meritko is not None:
            cfg["svetla_meritko"] = a.svetla_meritko
        print("SVETLA: %d svetel (%s) ze souboru %s (kamera souboru %s st.)"
              % (len(_sv["svetla"]), ", ".join(sv["jmeno"] for sv in _sv["svetla"]),
                 os.path.basename(a.svetla_blend),
                 "?" if _sv.get("kamera_azimut_deg") is None else "%.0f" % _sv["kamera_azimut_deg"]))
    if a.key_svetlo is not None:
        cfg["key_svetlo"] = a.key_svetlo
    if a.key_svetlo_polomer is not None:
        cfg["key_svetlo_polomer"] = a.key_svetlo_polomer
    if a.hdri_azimut_pomer is not None:
        cfg["hdri_azimut_pomer"] = a.hdri_azimut_pomer
    if a.kryci_listy_debug:
        cfg["kryci_listy_debug"] = True
    if a.klt_material:
        cfg["klt_material"] = a.klt_material
    if a.klt_debug:
        cfg["klt_debug"] = True
    if a.kryci_listy_pruhledne:
        cfg["kryci_listy_pruhledne"] = True
    if a.vd_puvodni_nevyplnene:
        cfg["vd_puvodni_nevyplnene"] = True
    if a.alu_ao_sila is not None:
        cfg["alu_ao_sila"] = a.alu_ao_sila
    if a.alu_ao_vzdalenost_mm is not None:
        cfg["alu_ao_vzdalenost_mm"] = a.alu_ao_vzdalenost_mm
    if a.plast_svetly_tmava_sila is not None:
        cfg["plast_svetly_tmava_sila"] = a.plast_svetly_tmava_sila
    if a.cub_seda_tmava_sila is not None:
        cfg["cub_seda_tmava_sila"] = a.cub_seda_tmava_sila
    if a.key_svetlo_jen_alu:
        cfg["key_svetlo_jen_alu"] = True
    if a.key_svetlo_elevace is not None:
        cfg["key_svetlo_elevace"] = a.key_svetlo_elevace
    if a.key_svetlo_azimut_posun is not None:
        cfg["key_svetlo_azimut_posun"] = a.key_svetlo_azimut_posun
    if a.plosna_svetla:
        cfg["plosna_svetla"] = a.plosna_svetla
    if a.plosna_sila is not None:
        cfg["plosna_sila"] = a.plosna_sila
    if a.plosna_seed is not None:
        cfg["plosna_seed"] = a.plosna_seed

    os.makedirs(RENDER_OUT_DIR, exist_ok=True)
    # POZOR: adresar pro snimky ZAMERNE nezakladame. Tenhle skript bezi
    # jako root, ale vysledek do nej zapisuje Flask aplikace jako
    # www-data - root-owned adresar by jí zpusobil
    # PermissionError na manifest.json (realne chyceno 2026-09-09, uloha
    # skoncila HTTP 500 a hotovy GPU render se ztratil). Adresar si
    # vyrobi az server sam (render_worker_tt_result), pod spravnym
    # uzivatelem; rodicovsky RENDER_OUT_DIR uz www-data patri.
    # ---- POJISTKY PRED ZARAZENIM (bot9, 2026-09-11) --------------------
    # Duvod: pad skriptu ZA `_write_status()` nechal ve fronte ulohu, kterou
    # nikdo neuklidil - worker si ji vzal, nevyrenderoval nic a davka se
    # tvarila jako probehla. Chyceno naostro tyz den: pad --test na
    # IndexError zanechal ulohu s expected_frames=0. Poradi je proto ted
    # OBRACENE: napred se vsechno postavi, zkontroluje a vypise, a teprve
    # jako POSLEDNI krok se uloha zaradi do fronty.

    # 1) Uloha bez snimku nema smysl a nikdy mit nebude - pojistka patri
    #    sem, kde skoda vznika, ne do workeru.
    if not cfg["expected_frames"]:
        raise SystemExit(
            "ODMITNUTO: uloha by mela 0 snimku (expected_frames=0), takze by "
            "worker nevyrenderoval nic a davka by se pritom tvarila jako "
            "probehla. Zadna uloha nezarazena.")

    # 2) Idempotence - na jednu sestavu jen jedna aktivni uloha. Jinak by
    #    opakovane spusteni vyrobilo dve davky nad tymz produktem a ta
    #    druha by prvni prepsala.
    kolize = None if nabidka else _aktivni_uloha_sestavy(cfg["assembly_id"], cfg.get("shop_product_id"))
    if kolize:
        raise SystemExit(
            "ODMITNUTO: na sestavu/produkt %s uz ceka/bezi uloha %s (stav: %s). "
            "Jedna sestava = jedna aktivni uloha. Kdyz je ta stara k nicemu, "
            "zrus ji (stav 'cancelled' v %s.status.json) a spust znovu."
            % (cfg["assembly_id"] or cfg.get("shop_product_id"), kolize[0], kolize[1], kolize[0]))

    cfg_path = os.path.join(RENDER_OUT_DIR, "%s.json" % job)
    with open(cfg_path, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh, ensure_ascii=False)

    print("Uloha %s pripravena" % job)
    print("  sestava   : %s (%s)" % (cfg["assembly_id"], cfg["assembly_name"]))
    print("  produkt   : %s" % cfg["shop_product_id"])
    print("  dilu      : %d" % len(cfg["parts"]))
    if cfg["missing_parts"]:
        print("  CHYBI     : %s" % cfg["missing_parts"])
    if a.prstenec:
        mt = max(int(k) for k in cfg["tiers"])
        w, h = cfg["tiers"][str(mt)]
        print("  REZIM     : PRSTENEC - jen 1 snimek z otaceci sady "
              "(el %d / az %d, %dx%d)"
              % (cfg["elevations"][0], cfg["azimuths"][0], w, h))
    else:
        print("  snimku    : %d prstence + %d stills" % (cfg["expected_frames"], len(cfg["stills"])))
    if sablona_zdroj:
        print("  sablona   : TVOJE z %s (%s)" % (sablona_zdroj, _nazev_sablony()))
    else:
        print("  sablona   : %s" % (cfg.get("template_blend") or "(zadna - vestavene vychozi hodnoty)"))
    if sablona_pozn:
        print("  obrazky   : %s" % sablona_pozn)
    print("  vystup    : %s" % out_dir)

    # ---- ZARAZENI DO FRONTY = POSLEDNI KROK ----------------------------
    # Od teto chvile uloha existuje pro workera. Cokoli spadne potom, musi
    # ji oznacit jako chybnou - lezici `waiting_worker` je presne ta zombie,
    # kvuli ktere tahle cast vznikla.
    try:
        _write_status(job, state=("queued" if a.local else "waiting_worker"),
                      queued_at=time.time(), job_type="turntable",
                      **({"target_worker": a.worker.strip()} if (a.worker or "").strip() else {}),
                      # Kdo ulohu zaradil a jakym klicem. `render_klic_otisk`
                      # NENI overeni spravnosti (spravnou hodnotu tenhle kod
                      # nezna a znat nema) - je to zaznam, podle ktereho bot3
                      # pozna, ze nekdo pouzil jiny soubor nez jeho.
                      zaradil=kdo, render_klic_otisk=klic_otisk,
                      assembly_id=cfg["assembly_id"], assembly_name=cfg["assembly_name"],
                      shop_product_id=cfg["shop_product_id"],
                      expected_frames=cfg["expected_frames"],
                      expected_stills=len(cfg["stills"]),
                      # bot16, 2026-09-12 (bot4 zadani) - "detail aktualne
                      # zpracovavane ulohy": samples jen kdyz byl explicitne
                      # prepnuty (--samples), jinak chybi (bezny beh pouziva
                      # app_settings.render_samples, ne tohle pole).
                      samples=cfg.get("samples"),
                      hdri_rotace_deg=hdri_rotace_deg_pouzita,
                      # bot8 2026-09-11 (bot3): jednosnimkovy rezim (--test/
                      # --prstenec) skoncil VZDY jako "error", i kdyz render
                      # i snimky prosly v poradku - `expected_frames` si sam
                      # zapsal 2 (pocet tieru jednoho snimku), ale zaverecny
                      # commit v render_worker_tt_result pocitá s CELOU
                      # otockou (api/turntable.py EXPECTED_FRAME_COUNT=54) a
                      # odmitne to jako "neuplnou davku". Zkusebni snimek
                      # nepatri do galerie - je to podklad k rozhodnuti, ne
                      # vystup. `ingest_bez_commitu=True` (existujici
                      # mechanismus, driv jen rucni pro "uz vyrenderovano,
                      # jeste neschvaleno") prinuti render_worker_tt_result
                      # zapsat snimky (is_active=0) a NEZKOUSET commit vubec -
                      # stav skonci "done"+commit_pending, ne "error". Od
                      # 2026-09-24 i --bez-commitu samostatne (CELA otocka,
                      # porad bez aktivace - viz help textu vyse).
                      ingest_bez_commitu=jeden_snimek or a.bez_commitu,
                      # presny azimut z panelu (Robert 2026-09-28) - prevzeti
                      # ho prijme jen u jednoho testovaciho snimku bez commitu
                      ingest_libovolny_azimut=bool(jeden_snimek and a.azimut is not None),
                      **({"ucel": "nabidka", "user_id": a.nabidka_uzivatel} if nabidka else {}))
        print("\nZARAZENO do fronty.")
        if a.local:
            print("Lokalni render (CPU, hodiny) - spust:")
            print("  /opt/blender-5.2/blender -b -noaudio %s-P %s -- %s"
                  % ((cfg["template_blend"] + " ") if cfg.get("template_blend") else "",
                     TURNTABLE_SCRIPT, cfg_path))
        else:
            print("Ceka na GPU workera (stav: waiting_worker). Sleduj:")
            print("  cat %s/%s.status.json" % (RENDER_OUT_DIR, job))
    except BaseException as e:      # i KeyboardInterrupt/SystemExit - zombie nesmi zustat
        _write_status(job, state="error",
                      error="Zarazovani ulohy selhalo po zapisu stavu: %r" % (e,))
        raise


if __name__ == "__main__":
    main()
