#!/usr/bin/env python3
"""Automat: aktivuje Vandr (vanDrawee) kartu, jakmile ma soucasne cenu
I dokonceny render (bot5, 2026-09-22, navrh bot3, viz
PLAN_TVORBY_SESTAV.md "Vandr sestavy na eshopu").

⚠️ SAMOSTATNA implementace od `scripts/2026-09-16_card_auto_activate.py`
- princip stejny (cena + dokonceny render soucasne = aktivovat), kod
oddeleny od zacatku, jak Robert vyslovne pozadoval (PLAN_TVORBY_
SESTAV.md, "JINE KARTY, JINY MECHANISMUS"). Tenhle skript SAM cte jen
`shop_products`/`product_turntable_frames`, nikdy `product_assemblies`.

OPRAVA 2026-09-23: puvodni predpoklad "Vandr karty NEMAJI product_
assemblies vubec" uz NEPLATI DOSLOVA - bot4 kvuli 3D razitku (Robert:
"3D razitka dodelat zpetne a dopredu") postavil pro kazdou Vandr kartu
"stub" product_assemblies radek (`data.parts` = 1 zastupny
`product_<shop_product_id>` dil MISTO skutecne dekompozice geometrie +
`logo_logiman_cz` razitka - overeno zive na karte 4903/assembly 672,
9 dilu celkem, 8 z nich razitka). `product_turntable_frames.assembly_id`
proto NENI u Vandr karet vzdy NULL, muze byt vyplnena timhle stub ID.
Tenhle skript proto NEFILTRUJE na `assembly_id` vubec (jen
`shop_product_id` - u Vandr karty jednoznacne identifikuje relevantni
snimky, bez ohledu na NULL/vyplnenou hodnotu) - viz `_ma_2_ruzne_rendery`/
`_ma_alespon_1_render`/`_karty_ceka_na_druhou_elevaci`.

Nikdy neaktivuje kartu, ktera uz NEKDY byla aktivni (`activated_at`
IS NOT NULL) - stejna pojistka jako u Logiman varianty (Robertovo
vlastni schvalne stazeni z prodeje se "nevzkrisi"). Vypinac:
app_settings['vandr_card_activate_povoleno'] = '0'.

OPRAVA 2026-09-25 (bot3, karta #4593): "ma aktivni snimek(y)" NESTACILO
- karta se mohla aktivovat s renderem z PRED posledniho prepoctu razitek
(napr. po oprave predniho azimutu pro pravostranne regaly), protoze
`_ma_2_ruzne_rendery`/`_ma_alespon_1_render` kontroluji jen POCET/
ELEVACE aktivnich snimku, ne jejich STARI vuci soucasnym razitkum. Nova
podminka `_render_je_aktualni` (sdileny test s `2026-09-23_vandr_render_
auto_dispatch.py` pres `_vandr_render_otisk.py`) tohle uzavira - viz
tam pro presnou definici a proc NENI duvod k deaktivaci uz aktivnich
karet.

MINIMUM 2 RUZNE RENDERY (Robert pres bot3, 2026-09-22: "minimum k
zalozeni karty jsou 2 ruzne rendery"; upresneno primo: "menim to na 2
otocky, vodorovna a 40 stupnu, azimuty stejne jako 1. vetev") - JEN
Vandr vetev (Robert vyslovne potvrdil, Logiman card_auto_activate.py
zustava na puvodnim "1 kompletni varianta"). `ELEVATIONS=(-40,0,40)` v
api/turntable.py - "vodorovna"=0°, "40 stupnu"=40°. Karta potrebuje
AKTIVNI snimky u OBOU elevaci (0 I 40), ne jen jedne - viz
`_ma_2_ruzne_rendery`.

DOCASNA VYJIMKA PRO PRVNICH 10 KARET (Robert pres bot3, 2026-09-22,
doslova: "abychom vyzkouseli automatiku zakladani karet udelejme karty
zive s 1 renderem, a zbyle se dorenderuji a dohraji az budou zalozeno
aktivnich 10 karet"). Rozklicovano primo s Robertem (AskUserQuestion,
2 otevrene otazky od bot3 - hrozilo vice vykladu):
  (a) automat, ne jednorazova rucni akce - dokud
      COUNT(active VD karet) < `PRVNICH_N_KARET_STACI_1_RENDER` (=10),
      staci k aktivaci LIBOVOLNA 1 aktivni davka (jakakoli elevace,
      `_ma_alespon_1_render`), jakmile pocet dosahne 10, automat SAM
      natrvalo prepne zpet na "2 elevace" (`_ma_2_ruzne_rendery`) pro
      VSECHNY dalsi karty - zadny rucni krok pri prechodu.
  (b) tech prvnich ~10 kart s jen 1 renderem se POZDEJI doplni o
      druhou elevaci ("se dorenderuji a dohraji") - NENI trvala
      vyjimka pro tuhle konkretni desitku, jen docasny stav do
      dorenderovani. Zadne nove sledovaci pole netreba - ktere aktivni
      VD karty jeste nemaji obe elevace jde kdykoli zjistit primo
      dotazem (viz `_karty_ceka_na_druhou_elevaci`), pouzito i pro
      jednorazovy ukol na zed pri prechodu pres prah.

Spousti konfigurator-vandr-card-activate.timer, kazdych 15 minut.
Nic NEMAZE, jen UPDATE shop_products.active/activated_at.

Spusteni NA SERVERU (/opt/konfigurator):
    api/venv/bin/python3 scripts/2026-09-22_vandr_card_activate.py
    api/venv/bin/python3 scripts/2026-09-22_vandr_card_activate.py --apply
"""
import argparse
import datetime
import importlib.util
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _env import get_conn  # noqa: E402
import _vandr_render_otisk  # noqa: E402

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# bot5, 2026-09-24 (Robert pres bot3, URGENTNI: "proc jsou kotovane
# nahledy nastavene jako hlavni nahledovy obrazek" - hlavni nahled ma byt
# snimek z otocky, ne 2D vykres s kotami). Kazda NOVE aktivovana karta
# tim dostane spravny hlavni nahled hned, bez cekani na dalsi rucni beh
# 2026-09-24_vandr_hlavni_nahled_z_otocky.py (viz jeho docstring).
_spec_nahled = importlib.util.spec_from_file_location(
    "vandr_hlavni_nahled_z_otocky",
    os.path.join(REPO_ROOT, "scripts", "2026-09-24_vandr_hlavni_nahled_z_otocky.py"),
)
_vandr_nahled = importlib.util.module_from_spec(_spec_nahled)
_spec_nahled.loader.exec_module(_vandr_nahled)
zajisti_hlavni_nahled_z_otocky = _vandr_nahled.zajisti_hlavni_nahled_z_otocky


# Robert, 2026-09-22: "2 ruzne rendery" = 2 ruzne elevace (vodorovna +
# 40°), ne jen 2 nahodne snimky ze stejne otocky.
POZADOVANE_ELEVACE = (0, 40)
# Docasna vyjimka na otestovani cele automatiky - viz docstring modulu.
PRVNICH_N_KARET_STACI_1_RENDER = 10

# bot4, 2026-09-23 (na miste odhaleno pri parovani karet 4902/4904):
# `sku LIKE 'VD-%'` chytalo i rucni testovaci karty mimo watcher
# (napr. `VD-EXPORT-trafic-2f89b425`, `VD-TEST-*`, viz AGENTS_LOG
# 2026-09-19/20) - ty NEMAJI cenu ted, ale kdyby ji nekdy nekdo
# nastavil, tenhle automat by je omylem zverejnil. Presny format
# `VD-<uuid>` (stejny jako scripts/2026-09-22_vandr_fbx_watcher.py::
# UUID_RE), overeno ze skutecne odfiltruje jen ty 4 testovaci SKU
# a zadnou z 323 realnych Vandr karet.
VD_SKU_REGEXP = r"^VD-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"


def _ma_2_ruzne_rendery(cur, karta_id):
    # OPRAVA 2026-09-23: puvodne `AND assembly_id IS NULL` (predpoklad
    # "stary zpusob bez sestavy"). Bot4 misto toho pro razitka postavil
    # skutecnou "stub" product_assemblies radku (data.parts = 1 zastupny
    # `product_<id>` dil + `logo_logiman_cz` razitka, ZADNA dekompozice
    # skutecne geometrie) a frames pisou s touhle `assembly_id` VYPLNENOU
    # (overeno zive na karte 4903/assembly 672). `shop_product_id` sam
    # o sobe kartu jednoznacne identifikuje (1 Vandr karta = nejvyse 1
    # relevantni assembly), takze filtr na assembly_id je tu zbytecny -
    # odstranen, at funguje bez ohledu na NULL/vyplnenou hodnotu.
    cur.execute(
        "SELECT DISTINCT elevation_deg FROM product_turntable_frames "
        "WHERE shop_product_id=%s AND is_active=1 "
        "AND elevation_deg IN (%s,%s)",
        (karta_id, *POZADOVANE_ELEVACE),
    )
    ma = {r["elevation_deg"] for r in cur.fetchall()}
    return set(POZADOVANE_ELEVACE).issubset(ma)


def _ma_alespon_1_render(cur, karta_id):
    cur.execute(
        "SELECT COUNT(*) AS n FROM product_turntable_frames "
        "WHERE shop_product_id=%s AND is_active=1",
        (karta_id,),
    )
    return cur.fetchone()["n"] > 0


def _render_je_aktualni(cur, karta_id):
    """NALEZ 2026-09-25 (bot3, karta #4593 - Mercedes Sprinter L2H2,
    PRAVY regal aktivovan se STARYMA snimky levostranneho azimutu,
    protoze `_ma_2_ruzne_rendery`/`_ma_alespon_1_render` vyse kontroluji
    jen POCET/ELEVACE aktivnich snimku, ne jestli patri k SOUCASNYM
    razitkum karty). Test sdileny s `2026-09-23_vandr_render_auto_
    dispatch.py::kandidati()` pres `_vandr_render_otisk.py` (bot3: "at
    ten test zije na jednom miste, ne treti kopie", stejny vzor jako uz
    `_render_health_config.py`) - NIKDY nepsat druhou nezavislou
    sha256() tady, i kdyby to vypadalo jako 2 radky navic.

    `False` u karty BEZ zapsaneho otisku vubec (davka z doby PRED timhle
    mechanismem) je SPRAVNE chovani pro AKTIVACI (jeste nevim, ze render
    sedi, tak neaktivuji) - tenhle skript navic processes VYHRADNE
    kandidaty s `active=0`, zadnou uz aktivni kartu se stejnym NULL
    otiskem nikdy znovu neposuzuje ani nedeaktivuje (pravidlo 54)."""
    cur.execute(
        "SELECT vandr_razitka_json, vandr_render_razitka_otisk "
        "FROM shop_products WHERE id=%s",
        (karta_id,),
    )
    r = cur.fetchone()
    return bool(r) and _vandr_render_otisk.render_odpovida_razitkum(
        r["vandr_razitka_json"], r["vandr_render_razitka_otisk"])


def _pocet_aktivnich_vandr_karet(cur):
    cur.execute("SELECT COUNT(*) AS n FROM shop_products WHERE sku REGEXP %s AND active=1", (VD_SKU_REGEXP,))
    return cur.fetchone()["n"]


def _karty_ceka_na_druhou_elevaci(cur):
    """Aktivni VD karty, ktere jeste NEMAJI obe pozadovane elevace -
    pouzito pri prechodu pres PRVNICH_N_KARET_STACI_1_RENDER, aby
    Robert mel jasny seznam, co jeste treba dorenderovat/dohrat."""
    cur.execute(
        "SELECT sp.id, sp.sku, sp.name, "
        "  (SELECT COUNT(DISTINCT f.elevation_deg) FROM product_turntable_frames f "
        "   WHERE f.shop_product_id=sp.id AND f.is_active=1 "
        "   AND f.elevation_deg IN (%s,%s)) AS elevace_pocet "
        "FROM shop_products sp WHERE sp.sku REGEXP %s AND sp.active=1 "
        "HAVING elevace_pocet < 2",
        (*POZADOVANE_ELEVACE, VD_SKU_REGEXP),
    )
    return cur.fetchall()


def _zapsat_ukol_na_zed(cur, text):
    cur.execute("SELECT id FROM bot_ukoly WHERE bot_id='bot5' AND hotovo=0 AND text=%s", (text,))
    if cur.fetchone():
        return False
    cur.execute("INSERT INTO bot_ukoly (text, bot_id) VALUES (%s, 'bot5')", (text,))
    return True


def _log(zprava):
    print(zprava)
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    entry = f"\n## vandr-card-activate (automaticky, scripts/2026-09-22_vandr_card_activate.py) — {ts}\n\n{zprava}\n"
    try:
        with open(os.path.join(REPO_ROOT, "AGENTS_LOG.md"), "a", encoding="utf-8") as f:
            f.write(entry)
    except OSError as e:
        print(f"[vandr-card-activate] zapis do AGENTS_LOG.md selhal: {e}", file=sys.stderr)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    print(f"=== Vandr card activate — {'APPLY' if args.apply else 'DRY-RUN'} ===\n")

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT setting_value FROM app_settings WHERE setting_key='vandr_card_activate_povoleno'")
            row = cur.fetchone()
            if row and row["setting_value"] == "0":
                print("[vandr-card-activate] vypnuto (app_settings.vandr_card_activate_povoleno=0)")
                return 0

            # bot10, 2026-10-01 (WORKFLOW.md pravidlo 51 + Robert 2026-09-30
            # "rozdelit na 2 karty"): karta bez stitku strany (umisteni_id)
            # nesmi jit ven - typicky kombinace leve+prave strany v jednom
            # modelu (#4366, #4917), ktera se deli na samostatne karty stran.
            # Archivovana karta taky ne.
            cur.execute(
                "SELECT id, sku FROM shop_products "
                "WHERE sku REGEXP %s AND active=0 AND activated_at IS NULL "
                "AND price_czk_placeholder IS NOT NULL AND (umisteni_id IS NULL OR is_archived=1)",
                (VD_SKU_REGEXP,),
            )
            blokovane = cur.fetchall()
            if blokovane:
                print(f"[vandr-card-activate] {len(blokovane)} karet NEaktivuji - chybi stitek strany "
                      f"(umisteni_id) nebo jsou archivovane: "
                      + ", ".join(f"#{b['id']} {b['sku']}" for b in blokovane))
            cur.execute(
                "SELECT id, sku, name FROM shop_products "
                "WHERE sku REGEXP %s AND active=0 AND activated_at IS NULL "
                "AND price_czk_placeholder IS NOT NULL "
                "AND umisteni_id IS NOT NULL AND is_archived=0",
                (VD_SKU_REGEXP,),
            )
            kandidati = cur.fetchall()
            if not kandidati:
                print("[vandr-card-activate] 0 kandidatu (bez ceny nebo uz aktivni/drive aktivovano), konec")
                return 0

            pocet_pred = _pocet_aktivnich_vandr_karet(cur)
            pocet_aktivnich = pocet_pred

            aktivovano, aktivovano_docasne = [], []
            for k in kandidati:
                docasna_vyjimka = pocet_aktivnich < PRVNICH_N_KARET_STACI_1_RENDER
                ma_render = _ma_alespon_1_render(cur, k["id"]) if docasna_vyjimka else _ma_2_ruzne_rendery(cur, k["id"])
                if not ma_render:
                    continue
                if not _render_je_aktualni(cur, k["id"]):
                    print(f"[vandr-card-activate] {k['id']} {k['sku']} ma aktivni snimek(y), "
                          f"ale neodpovidaji soucasnym razitkum (vandr_render_razitka_otisk "
                          f"nesedi/chybi) - cekam na cerstvy render, nazatim NEaktivuji")
                    continue
                if args.apply:
                    cur.execute(
                        "UPDATE shop_products SET active=1, activated_at=NOW() WHERE id=%s",
                        (k["id"],),
                    )
                    stav_nahledu, detail_nahledu = zajisti_hlavni_nahled_z_otocky(cur, k["id"], sku=k["sku"], apply=True)
                    if stav_nahledu == "chyba":
                        print(f"[vandr-card-activate] POZOR: hlavni nahled z otocky se nepodarilo nastavit pro {k['id']} {k['sku']}: {detail_nahledu}")
                pocet_aktivnich += 1
                aktivovano.append(k)
                if docasna_vyjimka:
                    aktivovano_docasne.append(k)
                znacka = " [DOČASNÁ VÝJIMKA: jen 1 render]" if docasna_vyjimka else ""
                print(f"[vandr-card-activate] {'AKTIVOVANO' if args.apply else '(by se aktivovalo)'} {k['id']} {k['sku']} - {k['name']}{znacka}")

            # Prechod pres prah PRVNE v tomhle behu - jednorazovy ukol na
            # zed se seznamem VSECH aktivnich karet, co jeste nemaji obe
            # elevace (ne jen tech aktivovanych prave TEHLE behem).
            prah_prekrocen_ted = args.apply and pocet_pred < PRVNICH_N_KARET_STACI_1_RENDER <= pocet_aktivnich
            if prah_prekrocen_ted:
                ceka = _karty_ceka_na_druhou_elevaci(cur)
                if ceka:
                    seznam_ceka = "\n".join(f"- {r['id']} `{r['sku']}` — {r['name']}" for r in ceka)
                    _zapsat_ukol_na_zed(
                        cur,
                        f"VANDR: dosaženo {pocet_aktivnich} aktivních karet, automat přepnul zpět na "
                        f"'2 elevace' (docasna vyjimka na test automatiky skoncila). Tyhle karty byly "
                        f"aktivovany jen s 1 renderem - je potreba dorenderovat/dohrat druhou elevaci "
                        f"(Robert: \"se dorenderuji a dohraji\"):\n\n{seznam_ceka}",
                    )
        if args.apply:
            conn.commit()
    finally:
        conn.close()

    if args.apply and aktivovano:
        seznam = "\n".join(
            f"- {k['id']} `{k['sku']}` — {k['name']}" + (" [dočasná výjimka: 1 render]" if k in aktivovano_docasne else "")
            for k in aktivovano
        )
        _log(f"Aktivováno {len(aktivovano)} Vandr karet:\n\n{seznam}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
