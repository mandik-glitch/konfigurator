#!/usr/bin/env python3
"""2026-09-24_render_hdri_test_dispatch.py - automat: vyrizuje fronту
`render_hdri_test_requests` (tlacitko "otestovat render" u kazde HDRI
mapy na Sdilenem disku v adminu, Robert pres bot3, 2026-09-24).

PROC SAMOSTATNY AUTOMAT, NE PRIMO V API ENDPOINTU: endpoint
(api/render_hdri.py) bezi jako www-data uvnitr gunicornu a NEMA (schvalne)
pristup k /root/.konfigurator_render_klic (root-only 0600, pravidlo 31 -
"boti bezi jako root, dvere jsou zamcene, okno ne pro web sluzbu"). Web
proto jen VLOZI radek do tabulky, skutecne zarazeni do GPU fronty dela
tenhle root-owned skript - stejny princip jako cela rodina Vandr *_auto_
dispatch.py automatu (web/DB stav -> root cron cte a jedna).

PER-JOB OVERRIDE, NIKDY app_settings: dispatch pouziva --hdri <cesta> na
2026-09-09_turntable_render.py - `app_settings.render_hdri_file_id` (trvala
Robertova volba) se timhle vubec nemeni, presne jak WORKFLOW.md pravidlo
50 vyzaduje (vzniklo prave kvuli tomu, ze bot4 driv omylem zapsal trvalou
volbu primo SQL misto pouziti tohohle mechanismu).

JEDEN SNIMEK (--test) - PREKONANO 2026-09-28, Robert primo: "to tlacitko
v HDRi na spusteni renderu nema spustit celou otocku ale 1 snimek".
Puvodni stav nize zachovan jako historie:

CELA OTOCKA, NE JEDEN SNIMEK (Robert pres bot3, 2026-09-24, oprava
puvodni verze: "Renderovou otočku chci vidět" - "1 otočka" v puvodnim
zadani znamenala CELOU 54snimkovou otocku, ne jeden testovaci --test
snimek): dispatch pouziva --bez-commitu (2026-09-09_turntable_render.py,
NOVY flag, nezavisly na --test/--prstenec) - cela otocka se vyrenderuje
a ulozi (is_active=0), ale NIKDY se neaktivuje/nejde na e-shop, ani kdyz
je testovana karta (4587) sama jinak zivá. To trva desitky minut na
GPU (cela produkcni davka), ne desitky sekund jako drivejsi --test.

DVE FAZE V KAZDEM BEHU (nic neceka synchronne na dokonceni renderu -
dalsi kliknuti Robertem mezitim nesmi cekat ve fronte databazovych
pozadavku):
  A) VSECHNY 'pending' radky: atomicky zabrat (UPDATE ... WHERE
     status='pending', kontrola rowcount==1 - bezpecne i pri prekryvu
     dvou behu timeru), dohledat cestu k HDRI souboru primo v
     shared_drive_files (BEZ "uzdravovaci" logiky shared_drive_pointer -
     tady jde o KONKRETNI kliknuty soubor PRAVE TED, ne o trvaly
     ukazatel), zaradit render (--bez-commitu, cela otocka) a ulozit
     job_id, stav -> 'dispatched'.
  B) VSECHNY 'dispatched' radky: podivat se na .status.json prislusneho
     jobu - state=done -> vybrat JEDEN reprezentativni (predni, elevace
     0) snimek z cele otocky pro rychly nahled/kopii na disk (viz
     _najdi_snimek) a slozit verejnou URL (/content-files/turntable-
     frames/..., viz api/turntable.py hlavicka), stav -> 'done'; navic
     zkopirovat ten snimek na Sdileny disk (Rendering/HDRi/testy, viz
     _kopirovat_na_sdileny_disk - Robert: "chci to prece pristupne na
     disku!!!"); state=error/cancelled -> stav 'error' s popisem; jinak
     (jeste bezi) nechat byt.

Spousti konfigurator-render-hdri-test-dispatch.timer, kazdych ~10s
(OnUnitActiveSec, ne OnCalendar - potrebuje kratky, tesny cyklus na
interaktivni pouziti z adminu, ne 15minutovy vzor zbytku Vandr rodiny).

Spusteni NA SERVERU (/opt/konfigurator):
    api/venv/bin/python3 scripts/2026-09-24_render_hdri_test_dispatch.py
"""
import datetime
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

import pymysql  # venv interpreter (api/venv/bin/python3) uz ma na sys.path

REPO = os.path.dirname(os.path.abspath(__file__)).rsplit(os.sep + "scripts", 1)[0]
RENDER_SCRIPT = os.path.join(REPO, "scripts", "2026-09-09_turntable_render.py")
RENDER_OUT_DIR = os.path.join(REPO, "private-files", "blender-renders")
DRIVE_FILES_DIR = os.path.join(REPO, "private-files", "shared-drive")
CONTENT_FILES_DIR = os.path.join(REPO, "webapp", "content-files")
RENDER_KLIC_SOUBOR = "/root/.konfigurator_render_klic"
JOB_TIMEOUT_S = 90  # jen zarazeni do fronty (subprocess se vrati hned po "ZARAZENO"), ne cekani na render

# Robert 2026-09-24, duraznze: "chci to prece pristupne na disku!!! jako
# vsechno ostatni" - vysledny testovaci snimek se navic (NE MISTO
# content-files kopie, ktera zustava kvuli /content-files/ verejne URL)
# kopiruje do existujici slozky "Rendering / HDRi" (id 45), do
# podslozky "testy" (dohledana/zalozena idempotentne nize).
HDRI_SLOZKA_ID = 45


def _env():
    env = {}
    for line in open(os.path.join(REPO, "api", ".env")):
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k] = v
    return env


def _conn():
    venv_site = glob.glob(os.path.join(REPO, "api", "venv", "lib", "python3.*", "site-packages"))
    if venv_site and venv_site[0] not in sys.path:
        sys.path.insert(0, venv_site[0])
    import pymysql
    env = _env()
    return pymysql.connect(host=env["DB_HOST"], port=int(env.get("DB_PORT", 3306)),
                            user=env["DB_USER"], password=env["DB_PASSWORD"],
                            database=env["DB_NAME"], charset="utf8mb4",
                            cursorclass=pymysql.cursors.DictCursor)


def _cesta_k_hdri(cur, file_id):
    """Primy lookup KONKRETNIHO souboru - zadna "uzdravovaci" logika
    (shared_drive_pointer je pro TRVALY ukazatel, tady jde o soubor,
    ktery Robert prave tuhle chvili klikl)."""
    cur.execute("SELECT stored_filename, filename FROM shared_drive_files WHERE id=%s", (file_id,))
    row = cur.fetchone()
    if not row:
        return None, "soubor id=%s uz na Sdilenem disku neni" % file_id
    cesta = os.path.realpath(os.path.join(DRIVE_FILES_DIR, row["stored_filename"]))
    if not cesta.startswith(os.path.realpath(DRIVE_FILES_DIR)) or not os.path.isfile(cesta):
        return None, "soubor '%s' (id=%s) chybi na disku" % (row["filename"], file_id)
    return cesta, None


def _cesta_k_souboru_podle_jmena(cur, jmeno):
    """Robert 2026-09-28 (prirazeni materialu primo v adminu): knihovna se
    zada JMENEM souboru (ne id) - hleda se NEJPRVE kdekoli na Sdilenem
    disku (posledni nahrany s tim jmenem vyhrava), pak v nasich vlastnich
    testovacich knihovnach mimo disk."""
    cur.execute("SELECT stored_filename FROM shared_drive_files WHERE filename=%s ORDER BY id DESC LIMIT 1", (jmeno,))
    row = cur.fetchone()
    if row:
        cesta = os.path.realpath(os.path.join(DRIVE_FILES_DIR, row["stored_filename"]))
        if os.path.isfile(cesta):
            return cesta
    for kandidat in (
        os.path.join(REPO, "private-files", "alu_test", jmeno),
        os.path.join(REPO, "scripts", "2026-09-21_vd_materialy", jmeno),
    ):
        if os.path.isfile(kandidat):
            return kandidat
    return None



def _cesta_podle_jmena_conn(conn, jmeno):
    """Vlastni kratky kurzor - volajici (faze A) uz ma svuj `cur` z
    predchoziho `with` bloku ZAVRENY; pouzit ho tady spadlo s "Cursor
    closed" pri prvnim testu s vyplnenou knihovnou (2026-09-28 14:06,
    cely beh timeru padl a radek zustal viset jako 'dispatched')."""
    with conn.cursor() as c:
        return _cesta_k_souboru_podle_jmena(c, jmeno)

def _sestav_material_knihovnu(dvojice):
    """Jedna implementace i s cache: scripts/_render_prirazeni_lib.py::sestav_material_knihovnu (bot4 2026-10-02 - tahle
    kopie delala pro KAZDY test novy 13-25 MB soubor a nikdy ho nesmazala)."""
    import _render_prirazeni_lib as _rpl
    return _rpl.sestav_material_knihovnu(dvojice)


def faze_a_dispatch(conn):
    """Bot4 2026-09-24, nalezeno ostrym pouzitim (Robertuv klik narazil na
    VLASTNI drivejsi testovaci pozadavek na TEZE karte): 2026-09-09_
    turntable_render.py odmita druhou aktivni ulohu nad stejnym produktem
    ("jedna sestava = jedna aktivni uloha") - kdyz vsechny testovaci
    pozadavky miri na JEDNU pevnou testovaci kartu (TEST_RENDER_SHOP_
    PRODUCT_ID), dve rychla kliknuti za sebou by se VZDY srazila. Misto
    tvrdeho selhani se novy pozadavek na uz obsazenou kartu NEDISPATCHUJE
    tenhle beh - zustava 'pending' a zkusi se zas priste (efektivne fronta
    FIFO za scenou, uzivatel jen vidi delsi "renderuje...")."""
    with conn.cursor() as cur:
        try:
            # Nove sloupce (Robert 2026-09-28: prirazeni materialu) - DB
            # migrace bezi mimo tenhle skript (ALTER TABLE, sandbox to bota
            # odmita spustit primo), takze DOKUD Robert prikaz nespusti,
            # tenhle SELECT chybne selhava a MUSI spadnout zpet na puvodni
            # tvar - jinak by kazdych 10s selhal CELY automat (i puvodni,
            # uz zivou funkcnost bez materialu), zjisteno 2026-09-28 ostrym
            # vypadkem hned po prvnim ulozeni tehle zmeny.
            cur.execute("SELECT id, hdri_file_id, shop_product_id, alu_material, alu_knihovna_soubor, "
                        "klt_material, klt_knihovna_soubor, ostatni_knihovna_soubor, cub_seda_tmava_sila, "
                        "alu_ao_sila, hdri_sila, hdri_rotace_deg, nastaveni_json FROM render_hdri_test_requests "
                        "WHERE status='pending' ORDER BY id")
            cekajici = cur.fetchall()
        except pymysql.err.OperationalError as e:
            if e.args and e.args[0] == 1054:  # Unknown column - migrace jeste nebezela
                cur.execute("SELECT id, hdri_file_id, shop_product_id FROM render_hdri_test_requests "
                            "WHERE status='pending' ORDER BY id")
                cekajici = cur.fetchall()
            else:
                raise
    for r in cekajici:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM render_hdri_test_requests "
                        "WHERE status='dispatched' AND shop_product_id=%s AND id!=%s",
                        (r["shop_product_id"], r["id"]))
            if cur.fetchone():
                continue  # jiny test na TEZE karte uz bezi - pockej na dalsi beh timeru

        with conn.cursor() as cur:
            cur.execute("UPDATE render_hdri_test_requests SET status='dispatched' "
                        "WHERE id=%s AND status='pending'", (r["id"],))
            zabrano = cur.rowcount == 1
        conn.commit()
        if not zabrano:
            continue  # jiny beh timeru uz to zabral (prekryv)

        with conn.cursor() as cur:
            cesta, chyba = _cesta_k_hdri(cur, r["hdri_file_id"])
        if chyba:
            _ulozit_chybu(conn, r["id"], chyba)
            print("id=%d CHYBA (pred zarazenim): %s" % (r["id"], chyba))
            continue

        # Prirazeni materialu (Robert 2026-09-28: "primo v tom disku/adminu
        # chci priradovat material") - volitelne, per-job, stejny princip
        # jako HDRI vyse. Kdyz alu i klt miri na RUZNE soubory, slouci se
        # do jedne docasne knihovny (--vd-knihovna umi jen JEDEN soubor).
        material_args = []
        dvojice_knihoven = []
        # Knihovna staci - prazdny nazev materialu = vezme se z knihovny
        # (Robert 2026-09-28 vyplnuje jen Suplik_celo.blend / Multibox.blend).
        import _render_prirazeni_lib as _rp_kn
        _chyba_kn = None
        for _km, _kk, _prep, _popis in (
                ("alu_material", "alu_knihovna_soubor", "--alu-material", "hlinik"),
                ("klt_material", "klt_knihovna_soubor", "--klt-material", "celo supliku")):
            if not r.get(_kk):
                continue
            _cesta_kn = _cesta_podle_jmena_conn(conn, r[_kk])
            if _cesta_kn is None:
                _chyba_kn = "knihovna '%s' (%s) nenalezena" % (r[_kk], _popis)
                break
            _ch = []
            _mat = _rp_kn.urci_material_v_knihovne(r[_kk], _cesta_kn, r.get(_km), _ch)
            if _mat is None:
                _chyba_kn = "; ".join(_ch)
                break
            dvojice_knihoven.append((_mat, _cesta_kn))
            material_args += [_prep, _mat]
        if _chyba_kn:
            _ulozit_chybu(conn, r["id"], _chyba_kn)
            print("id=%d CHYBA (%s)" % (r["id"], _chyba_kn))
            continue
        if r.get("ostatni_knihovna_soubor"):
            # Robert 2026-09-28: "material pro vsechny ostatni typy objektu,
            # ktere pro Vandr cestu pouzivame" - CELA knihovna (ne jeden
            # jmenovany material), sloucena stejnym mechanismem - vsechny
            # jeji VD_ materialy pak najde stavajici jmenna substituce
            # (VD_NAHRADA_PODLE_JMENA) automaticky, zadny novy CLI prepinac.
            ostatni_cesta = _cesta_podle_jmena_conn(conn, r["ostatni_knihovna_soubor"])
            if ostatni_cesta is None:
                _ulozit_chybu(conn, r["id"], "knihovna '%s' (ostatni dily) nenalezena" % r["ostatni_knihovna_soubor"])
                print("id=%d CHYBA (ostatni knihovna nenalezena)" % r["id"])
                continue
            dvojice_knihoven.append(("__ostatni__", ostatni_cesta))
        # Radky tabulky "kazdy material jeden radek" (Robert 2026-09-28),
        # azimut, kryci listy: berou se z OTISKU panelu ulozeneho v radku
        # pozadavku v okamziku kliknuti (Robert 2026-09-29: opakovana
        # kliknuti se zmenenymi parametry = fronta, kazdy test si drzi
        # SVE nastaveni). Radek bez otisku (starsi nez tahle zmena) bere
        # zivy ulozeny stav panelu jako driv. Nikdy nesmi shodit cely beh.
        _ulozene = None
        try:
            import _render_prirazeni_lib as _rp
            _chyby = []
            with conn.cursor() as c2:
                _ulozene = None
                if r.get("nastaveni_json"):
                    try:
                        _ulozene = json.loads(r["nastaveni_json"])
                    except ValueError:
                        _ulozene = None
                    if not isinstance(_ulozene, dict):
                        _ulozit_chybu(conn, r["id"], "otisk nastaveni testu je poskozeny")
                        print("id=%d CHYBA (poskozeny otisk nastaveni)" % r["id"])
                        continue
                if _ulozene is None:
                    _ulozene = _rp.nacti_ulozene_nastaveni(c2)
                _vys = _rp.nahrady_args(c2, _ulozene.get("nahrady"), _chyby)
                # Svetla podle souboru (Robert 2026-09-29, X1_SCENA.blend) -
                # z otisku panelu, stejne jako radky tabulky.
                _sv = _rp.svetla_args(c2, _ulozene, _chyby)
            # "schované krycí lišty" (zatrzitko v panelu, Robert 2026-09-28)
            if _ulozene.get("kryci_listy_skryt"):
                material_args += ["--kryci-listy-pruhledne"]
            # Robert 2026-09-28: nevyplneny radek tabulky = material z modelu
            material_args += ["--vd-puvodni-nevyplnene"]
            # azimut sestavy z panelu (Robert 2026-09-28) - uhel testovaciho
            # snimku, prazdne = zepredu (vychozi --test)
            if _ulozene.get("azimut_deg") not in (None, ""):
                material_args += ["--azimut", str(int(round(float(_ulozene["azimut_deg"]))) % 360)]
            if _vys is None or _sv is None:
                _ulozit_chybu(conn, r["id"], "; ".join(_chyby))
                print("id=%d CHYBA (radky tabulky / svetla): %s" % (r["id"], "; ".join(_chyby)))
                continue
            material_args += _vys[0] + _sv
            dvojice_knihoven += _vys[1]
        except Exception as e:
            if (isinstance(_ulozene, dict) and _ulozene.get("svetla_soubor")
                    and _ulozene.get("svetla_aktivni", True) is not False):
                # test s pozadovanymi svetly se nesmi tise zaradit bez nich
                _ulozit_chybu(conn, r["id"], "svetla / radky tabulky se nepodarilo pripravit: %s" % e)
                print("id=%d CHYBA (svetla, neocekavana vyjimka): %s" % (r["id"], e))
                continue
            print("id=%d VAROVANI: radky tabulky materialu preskoceny (%s)" % (r["id"], e))
        _ch_kol = []
        if not _rp_kn.zkontroluj_kolize_nazvu(dvojice_knihoven, _ch_kol):
            _ulozit_chybu(conn, r["id"], "; ".join(_ch_kol))
            print("id=%d CHYBA (kolize nazvu): %s" % (r["id"], "; ".join(_ch_kol)))
            continue
        if dvojice_knihoven:
            try:
                knihovna = _sestav_material_knihovnu(dvojice_knihoven)
            except Exception as e:
                _ulozit_chybu(conn, r["id"], "sestaveni knihovny materialu selhalo: %s" % e)
                print("id=%d CHYBA (sestaveni knihovny): %s" % (r["id"], e))
                continue
            material_args += ["--vd-knihovna", knihovna]
        if r.get("cub_seda_tmava_sila") is not None:
            material_args += ["--cub-seda-tmava-sila", str(r["cub_seda_tmava_sila"])]
        if r.get("alu_ao_sila") is not None:
            material_args += ["--alu-ao-sila", str(r["alu_ao_sila"])]
        if r.get("hdri_sila") is not None:
            material_args += ["--hdri-sila", str(r["hdri_sila"])]
        if r.get("hdri_rotace_deg") is not None:
            material_args += ["--hdri-rotace-deg", str(r["hdri_rotace_deg"])]

        # Kde renderovat (Robert 2026-09-29): jmeno stroje z otisku panelu,
        # prazdne = vychozi GPU stanice. Cti se primo z otisku (ne z _ulozene),
        # aby vyjimka v bloku tabulky vyse cil tise nezahodila.
        render_na = None
        try:
            _ot = json.loads(r["nastaveni_json"]) if r.get("nastaveni_json") else {}
            if isinstance(_ot, dict) and str(_ot.get("render_na") or "").strip():
                render_na = str(_ot["render_na"]).strip()
        except ValueError:
            pass
        if render_na:
            material_args += ["--worker", render_na]

        env = dict(os.environ)
        env["KONFIGURATOR_RENDER_KLIC_SOUBOR"] = RENDER_KLIC_SOUBOR
        env["BOT_ID"] = "bot4-automat"
        try:
            p = subprocess.run(
                [os.path.join(REPO, "api/venv/bin/python3"), RENDER_SCRIPT,
                 "--shop-product-id", str(r["shop_product_id"]), "--test", "--hdri", cesta]
                + material_args,
                cwd=REPO, capture_output=True, text=True, timeout=JOB_TIMEOUT_S, env=env,
            )
            vystup = (p.stdout or "") + (p.stderr or "")
        except subprocess.TimeoutExpired:
            _ulozit_chybu(conn, r["id"], "zarazeni do fronty prekrocilo %ds" % JOB_TIMEOUT_S)
            print("id=%d CHYBA (timeout pri zarazeni)" % r["id"])
            continue

        m = re.search(r"Uloha ([0-9a-f]{16,40}) pripravena", vystup)
        if p.returncode != 0 or not m:
            if "ODMITNUTO" in vystup and "aktivni uloha" in vystup:
                # Prechodna kolize (jina uloha na TEZE karte, mimo tenhle
                # automat - napr. rucni test) - NENI terminalni chyba,
                # zkusi se znovu priste az ta jina dobehne. Vraceno zpet na
                # 'pending' (bylo 'dispatched' od claimu vyse).
                with conn.cursor() as cur:
                    cur.execute("UPDATE render_hdri_test_requests SET status='pending' WHERE id=%s", (r["id"],))
                conn.commit()
                print("id=%d ODLOZENO (jina aktivni uloha na stejne karte, zkusi se znovu)" % r["id"])
                continue
            _ulozit_chybu(conn, r["id"], "zarazeni selhalo (exit %d): %s" % (p.returncode, vystup.strip()[-500:]))
            print("id=%d CHYBA (zarazeni): %s" % (r["id"], vystup.strip()[-200:]))
            continue

        job_id = m.group(1)
        with conn.cursor() as cur:
            cur.execute("UPDATE render_hdri_test_requests SET job_id=%s WHERE id=%s", (job_id, r["id"]))
        conn.commit()
        print("id=%d ZARAZENO job=%s" % (r["id"], job_id[:12]))


def _ulozit_chybu(conn, request_id, text):
    with conn.cursor() as cur:
        cur.execute("UPDATE render_hdri_test_requests SET status='error', error_text=%s WHERE id=%s",
                    (text, request_id))
    conn.commit()


def _predni_azimut_z_jobu(job_id):
    """--bez-commitu dela CELOU otocku (54 snimku, Robert 2026-09-24:
    "Renderovou otočku chci vidět") - z ni vybirame JEDEN reprezentativni
    (predni, elevace 0) snimek pro rychly nahled/kopii na disk; cela
    davka zustava na disku vedle nej (prohlizec/pripadny widget umi
    sahnout na kteroukoli). Predni azimut je ulozeny primo v konfiguraci
    ulohy (ne v .status.json) - viz 2026-09-09_turntable_job.py."""
    try:
        with open(os.path.join(RENDER_OUT_DIR, "%s.json" % job_id), encoding="utf-8") as fh:
            return json.load(fh).get("front_azimuth_deg")
    except (OSError, ValueError, TypeError):
        return None


def _najdi_snimek(shop_product_id, batch, job_id):
    """Najde JEDEN reprezentativni snimek (predni, elevace 0, nejvetsi
    tier) z cele otocky na disku. Vraci (verejna_url, lokalni_cesta) -
    viz api/turntable.py hlavicka pro tvar verejne cesty."""
    zaklad = os.path.join(CONTENT_FILES_DIR, "turntable-frames", str(shop_product_id), batch)
    front = _predni_azimut_z_jobu(job_id)
    if front is not None:
        presne = glob.glob(os.path.join(zaklad, "2048", "e00", "a%03d.jpg" % front))
        if presne:
            rel = os.path.relpath(presne[0], CONTENT_FILES_DIR)
            return "/content-files/" + rel.replace(os.sep, "/"), presne[0]
    # Zaloha, kdyby presny azimut nesedel (zaokrouhleni na STEP_DEG) -
    # jakykoli snimek elevace 0 v nejvetsim tieru je rozumny nahled.
    nalezene = sorted(glob.glob(os.path.join(zaklad, "2048", "e00", "*.jpg")))
    if not nalezene:
        nalezene = sorted(glob.glob(os.path.join(zaklad, "*", "*", "*.jpg")))
    if not nalezene:
        return None, None
    rel = os.path.relpath(nalezene[0], CONTENT_FILES_DIR)
    return "/content-files/" + rel.replace(os.sep, "/"), nalezene[0]


def _najdi_nebo_zaloz_slozku_testy(cur):
    cur.execute("SELECT id FROM shared_drive_folders WHERE parent_folder_id=%s AND name='testy'",
                (HDRI_SLOZKA_ID,))
    row = cur.fetchone()
    if row:
        return row["id"]
    cur.execute("INSERT INTO shared_drive_folders (parent_folder_id, name) VALUES (%s, 'testy')",
                (HDRI_SLOZKA_ID,))
    return cur.lastrowid


def _kopirovat_na_sdileny_disk(conn, local_path, shop_product_id, hdri_filename):
    """Robert 2026-09-24: "chci to prece pristupne na disku!!! jako
    vsechno ostatni" - PRIDAT kopii vysledneho snimku do Sdileneho disku
    (content-files kopie s verejnou URL zustava, tohle je navic), stejny
    vzor jako scripts/2026-08-10_otisk_logiman_cz_to_shared_drive.py
    (nahodny hex nazev na disku, chown www-data, radek v shared_drive_
    files). Vraci id noveho radku, nebo None pri chybe (NIKDY nezhazuje
    vyjimku - tohle je doplnkova pohodlnost, ne funkcni jadro testu)."""
    try:
        hdri_zaklad = re.sub(r"[^a-zA-Z0-9_-]+", "_", os.path.splitext(hdri_filename)[0])
        znacka = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        display_name = "%s_%s_%s.jpg" % (shop_product_id, hdri_zaklad, znacka)
        token = os.urandom(16).hex()
        stored_filename = "%s.jpg" % token
        dest = os.path.join(DRIVE_FILES_DIR, stored_filename)
        shutil.copyfile(local_path, dest)
        os.chown(dest, 33, 33)  # www-data:www-data, stejne jako ostatni Sdileny disk uploady
        size_bytes = os.path.getsize(dest)
        with conn.cursor() as cur:
            folder_id = _najdi_nebo_zaloz_slozku_testy(cur)
            cur.execute(
                "INSERT INTO shared_drive_files (folder_id, filename, stored_filename, content_type, size_bytes, uploaded_by) "
                "VALUES (%s,%s,%s,%s,%s,%s)",
                (folder_id, display_name, stored_filename, "image/jpeg", size_bytes, None),
            )
            file_id = cur.lastrowid
        conn.commit()
        return file_id
    except OSError as e:
        print("VAROVANI: kopie na Sdileny disk se nepodarila (%s) - test samotny je porad OK, "
              "jen chybi kopie navic." % e)
        return None


def faze_b_dokoncit(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT id, job_id, shop_product_id, hdri_filename FROM render_hdri_test_requests "
                    "WHERE status='dispatched' AND job_id IS NOT NULL ORDER BY id")
        rozdelane = cur.fetchall()
    for r in rozdelane:
        status_path = os.path.join(RENDER_OUT_DIR, "%s.status.json" % r["job_id"])
        try:
            with open(status_path, encoding="utf-8") as fh:
                st = json.load(fh)
        except (OSError, ValueError):
            continue  # jeste nevznikl / prave se zapisuje, zkusi se priste
        stav = st.get("state")
        if stav in ("done",):
            batch = st.get("ingest_batch")
            url, local_path = _najdi_snimek(r["shop_product_id"], batch, r["job_id"]) if batch else (None, None)
            if not url:
                _ulozit_chybu(conn, r["id"], "render dobehl, ale snimek se nepodarilo najit na disku (batch=%s)" % batch)
                print("id=%d CHYBA (snimek nenalezen, batch=%s)" % (r["id"], batch))
                continue
            drive_file_id = _kopirovat_na_sdileny_disk(conn, local_path, r["shop_product_id"], r["hdri_filename"])
            with conn.cursor() as cur:
                cur.execute("UPDATE render_hdri_test_requests SET status='done', frame_url=%s, drive_file_id=%s "
                            "WHERE id=%s", (url, drive_file_id, r["id"]))
            conn.commit()
            print("id=%d HOTOVO %s (disk id=%s)" % (r["id"], url, drive_file_id))
        elif stav in ("error", "cancelled"):
            _ulozit_chybu(conn, r["id"], st.get("error") or ("render skoncil se stavem %s" % stav))
            print("id=%d CHYBA (render): %s" % (r["id"], st.get("error")))
        # jinak (queued/waiting_worker/running) - necha se byt, zkusi se priste


def main():
    conn = _conn()
    try:
        faze_a_dispatch(conn)
        faze_b_dokoncit(conn)
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
