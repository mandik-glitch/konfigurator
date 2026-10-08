#!/usr/bin/env python3
"""2026-09-23_vandr_render_auto_dispatch.py - automat: sam zaradi do
renderovaci fronty Vandr karty s hotovym GLB a AKTUALNIMI razitky, bez
aktivniho renderu.

Robert pres bot3, 2026-09-23: "proc si bot4 nepostavi automatickou
frontu na GPU vetve 2?" - render byl POSLEDNI rucne ovladany kus
retezce watcher -> konverze -> card-activate -> razitka -> RENDER. Do
teto chvile bot4 spoustel 2026-09-09_turntable_render.py --shop-
product-id RUCNE, kartu po karte, na zaklade zprav od bot3 (viz
AGENTS_LOG 2026-09-23, "prasečí rendery" + nasledna oprava algoritmu
razitek + oprava vanDrawee watermarku).

Stejny vzor jako 2026-09-14_render_auto_dispatch.py (nativni vetev,
tam KROKU_MAX/HELD_BY/production_work_claims) a
2026-09-23_vandr_razitka_auto_dispatch.py (sesterky automat o krok
driv ve stejne lince - odtud _env/_conn/_sha256_souboru 1:1) -
samostatny oneshot + systemd timer, ne dalsi vetev v jednom monolitu.

KRITERIUM "pripraveno" (presne 3 casti, bot3 2026-09-23 doslova: "karta
ma GLB + aktualni razitko (podle noveho algoritmu) + zadny aktivni
render"):
  1. glb_file IS NOT NULL (FBX->GLB konverze dobehla,
     2026-09-23_vandr_fbx_konverze_auto_dispatch.py).
  2. vandr_razitka_glb_otisk odpovida SOUCASNEMU obsahu GLB souboru
     (sha256) - PRESNE stejny test jako
     2026-09-23_vandr_razitka_auto_dispatch.py pouziva pro OPACNY
     zaver (tam "otisk nesedi" => potreba orazitkovat; tady "otisk
     SEDI" => razitka jsou aktualni, muze se renderovat). Karta bez
     spocitanych razitek vubec (`vandr_razitka_glb_otisk IS NULL`) NENI
     kandidat - cekej, az ji orazitkuje sesterky automat.
  3. karta NEMA zadnou prave aktivni/cekajici davku rozepsanou v render
     fronte (`*.status.json`) A (NEMA zadny AKTIVNI snimek VUBEC, NEBO
     ma aktivni snimek, jehoz `vandr_render_razitka_otisk` UZ NESEDI
     na soucasny `vandr_razitka_json` - viz OPRAVA STALENESS nize).

Samotne zarazeni delegovano na 2026-09-09_turntable_render.py jako
subprocess (--shop-product-id ID) - ten uz resi render klic
(_render_klic.py), vyber sablony ze Sdileneho disku, i SVOJI VLASTNI
idempotenci (_aktivni_uloha_sestavy, shop_product_id vetev). Tenhle
skript ji NEZDVOJUJE jako jedinou pojistku, jen PREDFILTRUJE kandidaty
o ni (viz _aktivni_joby_podle_shop_product), aby log/fail_count
neplnily pokusy, o kterych uz predem vime, ze narazi na "uz bezi".

STROP 1 KARTA NA BEH (KROKU_MAX=1) - jedina sdilena GPU stanice
"Logiman2" (FIFO, ~20-30 min/plna davka), presne stejne zduvodneni
jako nativni vetev. Bezi NEZAVISLE na 2026-09-14_render_auto_
dispatch.py (nativni fronta) - obe pisou do STEJNE render fronty
(soubory `private-files/blender-renders/*.status.json`), worker je
zpracuje FIFO bez ohledu na puvod, takze dva nezavisle casovace
nekoliduji, jen obe pripadne pridaji nejvyse 1 ulohu za sve okno.

VYPINAC: app_settings['vandr_render_auto_dispatch_povoleno'] = '1'.
Vychozi stav PO NASAZENI je VYPNUTO/chybi - zapnuti je SAMOSTATNY,
vedomy krok az PO kontrole prvniho --dry-run vystupu (stejny postup
jako u vsech predchozich automatu tehle rodiny).

OPRAVA STALENESS (bot4/bot3, 2026-09-23, PO regresi): puvodni verze
tohohle skriptu mela STEJNOU mezeru, jakou 2026-09-14_render_auto_
dispatch.py cestne priznava pro nativni vetev ("NEDETEKUJE staleness
JIZ vyrenderovane sestavy") - a mezera se skutecne projevila: karta
4903 mela aktivni davku z 15:33, PRED velkym prepisem algoritmu
razitek (commit 0786f23d, 19:48), a automat ji navzdy preskakoval,
protoze "uz ma aktivni snimek". Robert primo nahlasil "ma prilis
mnoho razitek" - napravu (rucni re-render) i tenhle mechanismus zavedl
bot4 stejny den, po schvaleni bot3.

Reseni: `api/turntable_ingest.py::_zapsat_render_razitka_otisk()`
zapise pri KAZDEM uspesnem commitu davky otisk (sha256 RAW retezce)
prave aktivniho `vandr_razitka_json` do noveho sloupce
`shop_products.vandr_render_razitka_otisk` (sql/2026-09-23d_shop_
products_vandr_render_otisk.sql). `kandidati()` pak kartu s aktivnim
snimkem povazuje za HOTOVOU jen tehdy, kdyz se tenhle otisk shoduje se
SOUCASNYM `vandr_razitka_json` - jinak (vc. davek z PRED zavedenim
tohohle sloupce, kde je otisk NULL) ji nabidne k prerenderovani znovu.

STALE NEZACHYCUJE ciste kodove opravy renderu (watermark/karoserie
exclusion apod.), kde se ani GLB, ani razitka_json nezmenily - takovou
zmenu nejde odvodit z otisku vstupnich DAT, protoze vstupni data se
nezmenila, zmenil se kod, ktery je zpracovava. Redetekce zustava na
cloveku/bot4 rucne (Robert chce byt sam finalni kontrola, viz
feedback_robert_is_the_qa_gate v pameti) - presne takhle se 2026-09-23
rucne dohledaly a prerenderovaly 4600/4601/4604/4904/4596 vedle 4903.

Nezasahuje do shop_products.active/activated_at (to je
2026-09-22_vandr_card_activate.py, samostatny NASLEDUJICI krok az
POTOM, co render dobehne) ani do product_assemblies (Robert/bot3:
"2. vetev se vepisuje do tabulky pro 1. vetev, to nelze").

Spusteni NA SERVERU (/opt/konfigurator):
    api/venv/bin/python3 scripts/2026-09-23_vandr_render_auto_dispatch.py [--dry-run]
"""
import argparse
import json
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.abspath(__file__)).rsplit(os.sep + "scripts", 1)[0]
KATALOG_DIR = os.path.join(REPO, "webapp", "katalog")
RENDER_SCRIPT = os.path.join(REPO, "scripts", "2026-09-09_turntable_render.py")
RENDER_OUT_DIR = os.path.join(REPO, "private-files", "blender-renders")
RENDER_KLIC_SOUBOR = "/root/.konfigurator_render_klic"

HELD_BY = "automat:vandr_render_auto_dispatch"
STEP_KEY = "vandr_render_auto_dispatch"
TARGET_TYPE = "shop_product"
KROKU_MAX = 1
LEASE_SECONDS = 600
MAX_FAIL = 3

# Teplotni brzda pri prehrate GPU (Robert 2026-09-25) - prahy/heartbeat
# cteni sdileno s hlidacem zaseknuti pres _render_health_config.py (bot3
# 2026-09-25: "at prahy zijou na jednom miste"), viz tam pro odduvodneni
# cisel i pro NEZASTAVUJE-bezici-render zasadu.

# Presne stejny format jako 2026-09-22_vandr_card_activate.py::VD_SKU_REGEXP
# (a stejny duvod: vyloucit bot4uv rucni testovaci/exportni SKU mimo
# watcher, napr. "VD-EXPORT-trafic-2f89b425", "VD-TEST-*").
VD_SKU_REGEXP = r"^VD-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import production_work_claims as pwc  # noqa: E402
# Bot4 2026-09-24, po naslepo prehlednutem sve otisky (Robert chtel dalsi
# karty aktivni, bot3 nahlasil "0 kandidatu" i kdyz razitka byla evidentne
# cerstva): bot10 2026-09-24 (commit f5f96e7b) zmenil VZOREC otisku na
# sha256(GLB)+PRAVIDLO_VERZE (viz _vandr_razitka_otisk.py - "zmena
# PRAVIDLA rozmisteni sama o sobe zadny prepocet nevyvola" bez toho), a
# napojil ho na 2026-09-23_vandr_razitka_spocitat.py i _auto_dispatch.py.
# Tenhle skript mel vlastni NEZAVISLOU kopii ciste sha256(GLB) (_sha256_
# souboru nize) - VZDY se lisila od noveho ulozeneho otisku, takze
# _porovnani nikdy nesedelo a kandidati() trvale hlasil "cekej na
# razitka automat", i kdyz razitka uz byla presne ta nejnovejsi. Import
# SDILENEHO modulu misto vlastni kopie - stejna trida chyby jako
# _vandr_razitka_otisk.py sam resi pro DVA jine skripty, tady chybel
# treti odberatel.
import _vandr_razitka_otisk  # noqa: E402
import _render_health_config as rhc  # noqa: E402
import _vandr_render_otisk  # noqa: E402
import _render_prirazeni_lib as prirazeni  # noqa: E402
import _render_stroje as stroje  # noqa: E402 - vyber stroje (Logiman2 / notebook), bot4 2026-09-30


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
    import glob
    venv_site = glob.glob(os.path.join(REPO, "api", "venv", "lib", "python3.*", "site-packages"))
    if venv_site and venv_site[0] not in sys.path:
        sys.path.insert(0, venv_site[0])
    import pymysql
    env = _env()
    return pymysql.connect(host=env["DB_HOST"], port=int(env.get("DB_PORT", 3306)),
                            user=env["DB_USER"], password=env["DB_PASSWORD"],
                            database=env["DB_NAME"], charset="utf8mb4",
                            cursorclass=pymysql.cursors.DictCursor)


def povoleno(cur):
    cur.execute("SELECT setting_value FROM app_settings WHERE setting_key='vandr_render_auto_dispatch_povoleno'")
    row = cur.fetchone()
    return bool(row) and str(row["setting_value"]).strip() == "1"


def _aktivni_joby_podle_shop_product():
    """{shop_product_id: True} pro Vandr karty, ktere uz maji cekajici/
    bezici render job - stejny zdroj (RENDER_OUT_DIR/*.status.json) jako
    2026-09-14_render_auto_dispatch.py::_aktivni_joby_podle_sestavy, jen
    klicovano `shop_product_id` misto `assembly_id` (Vandr joby maji
    assembly_id=None, viz build_job_vandr() v 2026-09-09_turntable_job.py)."""
    aktivni = {}
    try:
        names = os.listdir(RENDER_OUT_DIR)
    except OSError:
        return aktivni
    for fname in names:
        if not fname.endswith(".status.json"):
            continue
        try:
            with open(os.path.join(RENDER_OUT_DIR, fname), "r", encoding="utf-8") as f:
                st = json.load(f)
            if not isinstance(st, dict):
                continue
            spid = st.get("shop_product_id")
            if spid is None:
                continue
            if st.get("state") in ("queued", "waiting_worker", "running"):
                aktivni[spid] = True
        except (OSError, ValueError, TypeError, AttributeError):
            continue
    return aktivni


def kandidati(cur):
    """Vraci [(id, sku, name), ...] serazene podle id - Vandr karty s
    hotovym GLB, AKTUALNIMI razitky (otisk sedi), bez jiz bezici/cekajici
    davky, a BUD bez aktivniho snimku vubec, NEBO s aktivnim snimkem,
    jehoz `vandr_render_razitka_otisk` UZ NEODPOVIDA soucasnemu
    `vandr_razitka_json` (bot4/bot3 2026-09-23, po regresi na karte
    4903 - "ma aktivni snimek" uz NENI samo o sobe duvod preskocit,
    kdyz ten snimek byl vyrenderovan s jinymi razitky nez jsou ted v DB;
    viz sql/2026-09-23d_shop_products_vandr_render_otisk.sql).

    Docasna POJISTKA RL (bot3/Robert 2026-09-24, pravidlo 52) - preskakovat
    vse krome umisteni_id='RL', dokud predni azimut renderu padal na
    globalni fallback 270 bez ohledu na stranu regalu - ODSTRANENA
    2026-09-24 po bot10ove oprave (commit 62020052+e3458e46,
    build_job_vandr() ted cte shop_products.vandr_predni_azimut_deg
    spocitany PER KARTA); overeno primo (sloupec existuje, RL->270,
    RP->90, obema RP kartam 4593/4903 uz vynulovany vandr_render_
    razitka_otisk, takze je tahle funkce sama spravne nabidne k
    prerenderovani)."""
    cur.execute(
        "SELECT id, sku, name, glb_file, vandr_razitka_glb_otisk, "
        "vandr_razitka_json, vandr_render_razitka_otisk "
        "FROM shop_products WHERE sku REGEXP %s AND glb_file IS NOT NULL "
        "AND vandr_razitka_glb_otisk IS NOT NULL ORDER BY id",
        (VD_SKU_REGEXP,),
    )
    radky = cur.fetchall()
    if not radky:
        return [], 0, []
    celkem = len(radky)

    ids = [r["id"] for r in radky]
    ph = ",".join(["%s"] * len(ids))
    cur.execute(
        f"SELECT shop_product_id, COUNT(*) n FROM product_turntable_frames "
        f"WHERE shop_product_id IN ({ph}) AND is_active=1 GROUP BY shop_product_id", ids)
    ma_render = {r["shop_product_id"] for r in cur.fetchall() if r["n"] > 0}
    ma_aktivni_job = _aktivni_joby_podle_shop_product()

    ven = []
    chybejici_soubor = []
    for r in radky:
        if r["id"] in ma_aktivni_job:
            continue
        if r["id"] in ma_render:
            if _vandr_render_otisk.render_odpovida_razitkum(r["vandr_razitka_json"], r["vandr_render_razitka_otisk"]):
                continue  # aktivni snimek uz sedi na soucasna razitka - hotovo
            # jinak: ma aktivni snimek, ale zastaraly (nebo bez zapsaneho
            # otisku vubec, davka z doby PRED timhle mechanismem) - pokracuj
            # jako kdyby zadny nemela.
        glb_path = os.path.join(KATALOG_DIR, r["glb_file"])
        if not os.path.isfile(glb_path):
            chybejici_soubor.append((r["id"], r["glb_file"]))
            continue
        if _vandr_razitka_otisk.otisk_glb(glb_path) != r["vandr_razitka_glb_otisk"]:
            continue  # razitka NEODPOVIDAJI soucasnemu GLB+pravidlu (stary otisk) - cekej na sesterky automat
        ven.append((r["id"], r["sku"], r["name"]))
    return ven, celkem, chybejici_soubor


def zarad_render(shop_product_id, cil=None):
    """Zarad Vandr render do fronty - deleguje CELOU logiku (klic,
    sablona, VLASTNI idempotence) na 2026-09-09_turntable_render.py,
    presne jako 2026-09-14_render_auto_dispatch.py::zarad_render dela
    pro nativni vetev. Vraci (ok: bool, poznamka: str).

    Prirazeni materialu/HDRi (Robert 2026-09-28: zatrzitko "platne i pro
    automatickou linku renderu" v adminu) - VOLITELNY prekryv, ctenej
    pokazde znovu z app_settings (nikdy necachovan, aby zmena zatrzitka
    zabrala hned na PRISTIM kroku automatu, ne az po restartu procesu).
    Chybejici/necitelne nastaveni nebo vypadek DB ~= prazdny seznam = beze
    zmeny. ZAPNUTE nastaveni, ktere neodpovida realite (nenalezeny soubor,
    svetlo, material), ale `PrirazeniNeplatne` - render se pak NEZARADI a
    chyba se zapise ke kroku (neshoda = hlasita chyba, ne tichy render bez
    prepisu panelu).

    `cil` (bot4 2026-09-30, Robert: automat smi i na notebook): jmeno stroje z
    _render_stroje.vyber_stroj_pro_automat(); None = vychozi GPU stanice (bez --worker)."""
    material_args = []
    try:
        conn2 = _conn()
        try:
            with conn2.cursor() as cur2:
                material_args = prirazeni.nacti_nastaveni_pro_automat(cur2)
        finally:
            conn2.close()
    except prirazeni.PrirazeniNeplatne as e:
        return False, "prirazeni v panelu je neplatne (automat nezarazuje, oprav panel): %s" % e
    except Exception as e:
        print("PRIRAZENI PRO AUTOMAT: chyba pripojeni (%s) - render pokracuje bez prepisu" % e)
    env = dict(os.environ)
    env["KONFIGURATOR_RENDER_KLIC_SOUBOR"] = RENDER_KLIC_SOUBOR
    env["BOT_ID"] = "bot4-automat"
    p = subprocess.run(
        [os.path.join(REPO, "api/venv/bin/python3"), RENDER_SCRIPT,
         "--shop-product-id", str(shop_product_id)] + material_args
        + (["--worker", cil] if cil else []),
        cwd=REPO, capture_output=True, text=True, timeout=120, env=env,
    )
    vystup = (p.stdout or "") + (p.stderr or "")
    if p.returncode == 0 and "ZARAZENO do fronty" in vystup:
        return True, vystup.strip()[-300:]
    return False, ("zarazeni selhalo (exit %d): %s" % (p.returncode, vystup.strip()[-300:]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    conn = _conn()
    try:
        with conn.cursor() as cur:
            if not a.dry_run and not povoleno(cur):
                print("vandr_render_auto_dispatch_povoleno != '1' - automat vypnuty, konci.")
                return 0
            kand, zkontrolovano, chybejici_soubor = kandidati(cur)
    finally:
        conn.close()

    print("ZKONTROLOVANO karet (VD-<uuid>, glb+otisk vyplneny): %d" % zkontrolovano)
    if chybejici_soubor:
        print("POZOR - glb_file zapsany v DB, ale soubor na disku chybi: %d: %s"
              % (len(chybejici_soubor), chybejici_soubor))
    print("kandidatu na render: %d" % len(kand))

    if a.dry_run:
        for pid, sku, name in kand[:10]:
            print("  [nahled] id=%-5s %s - %s" % (pid, sku, name[:60]))
        if len(kand) > 10:
            print("  ... a dalsich %d" % (len(kand) - 10))
        for radek in stroje.popis_stroju():
            print("  [stroj] " + radek)
        _cil, _popis = stroje.vyber_stroj_pro_automat()
        print("  [stroj] dalsi zarazeni by slo na: %s (%s)" % (_cil or "vychozi, bez --worker", _popis))
        print("--dry-run: nic se nezabira ani nezarazuje.")
        return 0

    if not kand:
        return 0

    # Stroj, na ktery uloha pujde (bot4 2026-09-30): vychozi GPU stanice, nebo - kdyz je vytizena/prehrata/
    # offline - volny notebook. Teplotni brzda nize se tyka VYCHOZIHO stroje; kdyz je prehraty a uloha by
    # stejne sla na notebook, brzda nebrzdi (notebook ma vlastni prah uvnitr vyberu).
    cil, cil_popis = stroje.vyber_stroj_pro_automat()
    print("stroj: %s (%s)" % (cil or "vychozi", cil_popis))
    teplota = rhc.gpu_teplota_c()
    if cil is None and teplota is not None and teplota >= rhc.PRAH_GPU_TEPLOTA_C:
        print("GPU (Logiman2) ma %.1f C (prah %.1f C) - preskakuji tenhle cyklus, "
              "at si vydechne. Bezici render (pokud nejaky je) se NEZASTAVUJE, "
              "jen se nezahajuje dalsi. Dalsi pokus za 5 min." % (teplota, rhc.PRAH_GPU_TEPLOTA_C))
        return 0

    zpracovano = 0
    for shop_product_id, sku, name in kand:
        if zpracovano >= KROKU_MAX:
            print("strop %d kroku dosazen, koncim - dalsi beh prijde od casovace." % KROKU_MAX)
            break

        conn = _conn()
        try:
            with conn.cursor() as cur:
                if pwc.blokovano(cur, TARGET_TYPE, shop_product_id, STEP_KEY, MAX_FAIL):
                    continue  # po MAX_FAIL selhanich pocka (30 min ... 24 h) a zkusi znovu - NE navzdy (bot4 2026-09-30)
                zabrano = pwc.claim(cur, TARGET_TYPE, shop_product_id, STEP_KEY, HELD_BY, LEASE_SECONDS)
            conn.commit()
        finally:
            conn.close()
        if not zabrano:
            continue

        zpracovano += 1
        try:
            ok, poznamka = zarad_render(shop_product_id, cil)
        except Exception as e:  # sirok zachyt ZAMERNE - selhani se ma zapsat, ne shodit cely beh
            ok, poznamka = False, "vyjimka: %s" % e

        conn = _conn()
        try:
            with conn.cursor() as cur:
                pwc.release(cur, TARGET_TYPE, shop_product_id, STEP_KEY, HELD_BY,
                           "hotovo" if ok else "chyba", poznamka)
            conn.commit()
        finally:
            conn.close()
        print("id=%-5s %-20s %-45s %-6s [na: %s] %s"
              % (shop_product_id, sku, name[:45], "ZARAZENO" if ok else "CHYBA", cil or "vychozi", poznamka))

    print("\nzpracovano kroku: %d" % zpracovano)
    return 0


if __name__ == "__main__":
    sys.exit(main())
