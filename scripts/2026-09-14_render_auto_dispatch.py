#!/usr/bin/env python3
"""Automat, ktery sam prubezne zarazuje otocne nahledy do renderovaci
fronty - Robert primo, relayovano bot3 2026-09-14: "zajisti kontinualni
renderovani." Do te doby slo zarazeni VZDY jen rucne (bot4 spusti
2026-09-09_turntable_render.py <id> na svuj popud) - dukvod byl WORKFLOW.md
pravidlo 31 (sestavy se casto meni, bot vidouci jen svuj kus to nepozna).
Tenhle automat riziko pokryva jinak: kriterium "pripraveno" NIZE uz samo
vyzaduje schvaleni+kartu+kusovnik+aktualni razitka, takze cokoli, co se
jeste dodelava, kriteriem neprojde.

STAVEBNI KAMENY (nic z tohohle se nevymyslelo znovu):
  * kriteria "pripraveno" jsou PRESNE fazove priznaky dashboardu vyroby
    (PLAN_TVORBY_SESTAV.md, "Kroky vyrobni linky") - `scena_bom`, `schvaleno`,
    `razitka`, `karta` - stejny vypocet jako `api/production_overview.py`
    pouziva pro sloupce "Scéna"/"Razítka" (bot9/bot8 2026-09-11).
  * idempotence/uzavreni radku: `scripts/production_work_claims.py`
    (claim/release/fail_count_of) - PRESNE tentyz mechanismus jako
    `2026-09-11_watchdog_prace.py` (sesterky automat, o krok driv ve
    stejne lince - ten dopocitava kusovnik/cenu, tenhle pak renderuje).
  * samotne zarazeni delegovano na `2026-09-09_turntable_render.py` jako
    subprocess - ten uz resi klic (`_render_klic.py`), sablonu ze
    Sdileneho disku, i SVOJI VLASTNI idempotenci (`_aktivni_uloha_sestavy`).
    Tenhle skript ji nezdvojuje, jen se na jeji vysledek (SystemExit /
    exit kod) spolehne.

HRANICE, KTERE SE NESMI PREKROCIT (mirror `2026-09-11_watchdog_prace.py`,
prizpusobeno rendrum):
  * zadny krok, o kterem rozhoduje clovek/bot4 rucne (VYRAZENE varianty,
    sporne "05/06 uz jsou 03/04 a nemusi se prerenderovat" typ rozhodnuti
    z 2026-09-14 - takove vyjimky reci clovek pres zruseni konkretni ulohy,
    automat je neumi sam rozeznat a nema se o to snazit).
  * strop KROKU_MAX=1 na jedno spusteni - jedna davka je ~20-30 min na
    JEDINE GPU stanici, zadny duvod frontu plnit rychleji, nez ji worker
    stiha vyprazdnovat.
  * vypinac: app_settings['render_auto_dispatch_povoleno'], cte se na
    ZACATKU KAZDEHO behu (oneshot pres timer). Vychozi stav PO NASAZENI
    je VYPNUTO (0/chybi) - zapnuti je samostatny, vedomy krok AZ PO
    kontrole prvniho --dry-run vystupu (stejny postup jako u watchdog_prace,
    "bot4 pri kontrole pred zapnutim").
  * 3 selhani tehoz cile+kroku po sobe = automat to necha byt (fail_count),
    zadna dashboard kolonka pro tenhle konkretni krok zatim NEEXISTUJE
    (na rozdil od bom_backfill) - ke zjisteni zablokovanych cilu zatim
    slouzi primy dotaz do `production_work_claims` (target_type='assembly',
    step_key='render_auto_dispatch'), ne UI. Muze pribyt pozdeji.

ZNAME OMEZENI (zaznamenano cestne, ne schovano):
  * NEDETEKUJE staleness JIZ vyrenderovane sestavy po dodatecne zmene
    geometrie (presne dnesni sitace "dorazova deska" - viz AGENTS_LOG.md
    2026-09-14). `razitka` kriterium nize hlida jen to, ze OTISK sedi na
    DNESNI podobu dat - kdyz se geometrie zmeni A ZAROVEN se ve stejnem
    kroku re-orazitkuje (jak to dnes udelal bot5 u 344/369/370), otisk
    zustane "aktualni" i PRES zmenu, a automat nepozna, ze uz existujici
    aktivni render neodpovida nove geometrii (`rendery` priznak jen ptá,
    jestli NEJAKY aktivni radek existuje, ne jestli sedi na SOUCASNY
    otisk). Bezpecne reseni by vyzadovalo ukladat otisk/hash POUZITY PRI
    RENDERU vedle `product_turntable_frames` (dnes tam neni) - nedelano
    tady narychlo jako neoverena domenka, radeji zapsano jako mezera.
    Do te doby zustava redetekce takove staleness na cloveku/bot4 rucne
    (presne jak probehlo dnes vecer).
  * Nekontroluje, jestli je GPU worker online - `2026-09-09_turntable_render.py`
    zaradi do "waiting_worker" bez ohledu na to, worker sam job vyzvedne
    (nebo ho po hodinach prevezme CPU zachranny mechanismus, viz
    `render_worker.prevzit_opustenou_ulohu`) - netreba to resit dvakrat.

Pouziti:
    api/venv/bin/python3 scripts/2026-09-14_render_auto_dispatch.py            # beh
    api/venv/bin/python3 scripts/2026-09-14_render_auto_dispatch.py --dry-run  # jen vypise kandidaty, nic nezabira/nezaradi
"""
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, "/opt/konfigurator/scripts")
sys.path.insert(0, "/opt/konfigurator/api")

import _env  # noqa: E402
os.environ.update(_env.load_env())

import app  # noqa: E402,F401 - driv nez production_work_claims (potrebuje app.get_conn)
import production_work_claims as pwc  # noqa: E402
import razitkovac  # noqa: E402
import _render_stroje as stroje  # noqa: E402 - vyber stroje (Logiman2 / notebook), bot4 2026-09-30

HELD_BY = "automat:render_auto_dispatch"
STEP_KEY = "render_auto_dispatch"
KROKU_MAX = 1                  # jedna davka = ~20-30 min na JEDINE GPU stanici
LEASE_SECONDS = 600            # jen na dobu samotneho zarazeni (radove vteriny), ne na cely render
MAX_FAIL = 3

# Zivy DB sloupec (bot8 2026-09-15, ALTER TABLE + zapis, zadano bot3:
# "promitnout do kriteria pripraveno v render_auto_dispatch.py"). Nahrazuje
# drivejsi rucne udrzovany hardcoded RENDER_BLOKOVANE_ID (21 ID, 2026-09-15)
# - ten uz 2026-09-17 nepokryval 6 nove zmerenych sestav (476/480/484/504/
# 508/512, vsechny <70mm), zatimco byly jeste technicky_ok=0 (neskodne), ale
# byla by to ticha mezera, jakmile by je Robert schvalil. Pravidlo: horni
# blok varianty 04 ("dve pasma, plne vyplne, s policí") s mezerou mezi
# prickami/profily pod 70mm se NESMI renderovat ani zobrazit na e-shopu.
# `mezera_police_mm IS NULL` = jeste nezmereno (jina varianta NEBO varianta
# 04 cekajici na zmereni bota8) - NEBLOKUJE, protoze naprosta vetsina sestav
# tohle pole vubec nema a nikdy mit nebude (mereni je specificke jen pro
# variantu 04). Blokuje se jen prokazatelne zmereny podlimitni pripad.
MEZERA_POLICE_LIMIT_MM = 70


def _mezera_ok(mezera_mm):
    return mezera_mm is None or mezera_mm >= MEZERA_POLICE_LIMIT_MM


REPO = "/opt/konfigurator"
RENDER_KLIC_SOUBOR = "/root/.konfigurator_render_klic"
RENDER_SCRIPT = os.path.join(REPO, "scripts/2026-09-09_turntable_render.py")
RENDER_OUT_DIR = os.path.join(REPO, "private-files", "blender-renders")


def povoleno(cur):
    v = app.get_setting(cur, "render_auto_dispatch_povoleno", "0")
    return str(v).strip() == "1"


def _pripraveno(data):
    """Presne kriteria 'scena_bom' + 'razitka' z PLAN_TVORBY_SESTAV.md /
    api/production_overview.py - schvalne stejny vypocet, ne vlastni."""
    bom_ok = bool(data.get("bom")) and (data.get("price_summary") or {}).get("material_czk") is not None
    razitka_ok = razitkovac.stav_razitek(data) == "aktualni"
    return bom_ok, razitka_ok


def _aktivni_joby_podle_sestavy():
    """{assembly_id: True} pro sestavy, ktere uz maji cekajici/bezici
    render job - stejny zdroj jako api/production_overview.py pouziva pro
    sloupec Rendery (cte VSECHNY *.status.json, kazdou chybu jednoho
    souboru jen preskoci)."""
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
            aid = st.get("assembly_id")
            if aid is None:
                continue
            if st.get("state") in ("queued", "waiting_worker", "running"):
                aktivni[aid] = True
        except (OSError, ValueError, TypeError, AttributeError):
            continue
    return aktivni


def kandidati(cur):
    """Sestavy pripravene na render a jeste bez aktivni davky. Vraci
    [(id, name), ...] serazene podle id (deterministicke poradi mezi
    behy - ne nutne 'nejstarsi prvni', ale STEJNE poradi porad dokola,
    dokud se seznam nezmeni)."""
    cur.execute(
        "SELECT id, name, data, mezera_police_mm FROM product_assemblies "
        "WHERE technicky_ok=1 AND shop_product_id IS NOT NULL ORDER BY id"
    )
    radky = cur.fetchall()
    ids = [r["id"] for r in radky]
    if not ids:
        return []
    ph = ",".join(["%s"] * len(ids))
    cur.execute(
        f"SELECT assembly_id, COUNT(*) n FROM product_turntable_frames "
        f"WHERE assembly_id IN ({ph}) AND is_active=1 GROUP BY assembly_id", ids)
    ma_render = {r["assembly_id"] for r in cur.fetchall() if r["n"] > 0}
    ma_aktivni_job = _aktivni_joby_podle_sestavy()

    ven = []
    for r in radky:
        if r["id"] in ma_render or r["id"] in ma_aktivni_job or not _mezera_ok(r["mezera_police_mm"]):
            continue
        try:
            data = json.loads(r["data"]) if r["data"] else {}
        except (TypeError, ValueError):
            continue
        bom_ok, razitka_ok = _pripraveno(data)
        if bom_ok and razitka_ok:
            ven.append((r["id"], r["name"]))
    return ven


def zarad_render(assembly_id, cil=None):
    """Zarad otocny nahled do fronty - deleguje CELOU logiku (klic,
    sablona, vlastni idempotence) na 2026-09-09_turntable_render.py.
    Vraci (ok: bool, poznamka: str). ZADNE dalsi CLI prepinace - cisty
    zapis podle vychozich admin nastaveni, zadne rucni doladovani jako u
    jednorazovych lidskych davek (napr. --hdri-rotace-deg pro sjednoceni
    vzhledu jedne konkretni karty).

    `cil` (bot4 2026-09-30, Robert: automat smi i na notebook): jmeno stroje z
    _render_stroje.vyber_stroj_pro_automat(); None = vychozi GPU stanice (bez --worker)."""
    env = dict(os.environ)
    env["KONFIGURATOR_RENDER_KLIC_SOUBOR"] = RENDER_KLIC_SOUBOR
    env["BOT_ID"] = "bot4-automat"
    p = subprocess.run(
        [os.path.join(REPO, "api/venv/bin/python3"), RENDER_SCRIPT, str(assembly_id)]
        + (["--worker", cil] if cil else []),
        cwd=REPO, capture_output=True, text=True, timeout=120, env=env,
    )
    vystup = (p.stdout or "") + (p.stderr or "")
    if p.returncode == 0 and "ZARAZENO do fronty" in vystup:
        return True, vystup.strip()[-300:]
    return False, ("zarazeni selhalo (exit %d): %s" % (p.returncode, vystup.strip()[-300:]))


def main():
    dry = "--dry-run" in sys.argv

    conn = app.get_conn()
    try:
        with conn.cursor() as cur:
            if not dry and not povoleno(cur):
                print("render_auto_dispatch_povoleno != '1' - automat vypnuty, konci.")
                return 0
            kand = kandidati(cur)
    finally:
        conn.close()

    print("kandidatu na render: %d" % len(kand))
    if dry:
        for aid, name in kand[:10]:
            print("  [nahled] id=%-5s %s" % (aid, name[:70]))
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

    zpracovano = 0
    for assembly_id, name in kand:
        if zpracovano >= KROKU_MAX:
            print("strop %d kroku dosazen, koncim - dalsi beh prijde od casovace." % KROKU_MAX)
            break

        conn = app.get_conn()
        try:
            with conn.cursor() as cur:
                if pwc.blokovano(cur, "assembly", assembly_id, STEP_KEY, MAX_FAIL):
                    continue  # po MAX_FAIL selhanich pocka (30 min ... 24 h) a zkusi znovu - NE navzdy (bot4 2026-09-30)
                zabrano = pwc.claim(cur, "assembly", assembly_id, STEP_KEY, HELD_BY, LEASE_SECONDS)
            conn.commit()
        finally:
            conn.close()
        if not zabrano:
            continue

        zpracovano += 1
        t0 = time.time()
        cil, cil_popis = stroje.vyber_stroj_pro_automat()
        print("stroj: %s (%s)" % (cil or "vychozi", cil_popis))
        try:
            ok, poznamka = zarad_render(assembly_id, cil)
        except Exception as e:  # sirokz zachyt ZAMERNE - selhani se ma zapsat, ne shodit cely beh
            ok, poznamka = False, "vyjimka: %s" % e

        conn = app.get_conn()
        try:
            with conn.cursor() as cur:
                pwc.release(cur, "assembly", assembly_id, STEP_KEY, HELD_BY,
                           "hotovo" if ok else "chyba", poznamka)
            conn.commit()
        finally:
            conn.close()
        print("id=%-5s %-45s %-6s (%.1fs) [na: %s] %s"
              % (assembly_id, name[:45], "ZARAZENO" if ok else "CHYBA", time.time() - t0, cil or "vychozi", poznamka))

    print("\nzpracovano kroku: %d" % zpracovano)
    return 0


if __name__ == "__main__":
    sys.exit(main())
