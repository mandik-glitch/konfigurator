"""Admin: katalogové profily - tabulka cena/hmotnost, upload 3D modelu
(FBX/STEP), náhled kvality převodu, refresh ceny/hmotnosti jednotlivě i
hromadně.

Vyčleněno z api/app.py (PLAN_ROZDELENI_BACKENDU.md skupina 11) - čistý
přesun, žádná změna chování/URL. Pomocná funkce
`convert_uploaded_model_to_glb` a `refresh_price_for_row` zůstávají v
app.py, protože je používá i kód mimo tuhle skupinu (auta/karoserie,
skladové karty produktů, price-scraping) - modul si je jen importuje.
"""
import csv
import datetime
import glob
import io
import math
import os
import re
import tempfile

from flask import request, jsonify, Response
from werkzeug.utils import secure_filename

from app import (
    app, get_conn, require_permission, current_user, log_audit,
    fetch_katalog_parts, convert_uploaded_model_to_glb, refresh_price_for_row,
    FBX_UPLOAD_DIR, KATALOG_GLB_DIR, step_convert,
)
from fio_rate import fetch_fio_usd_czk_sell_rate, FIO_RATE_URL


# --- Admin: tabulka cen a hmotnosti profilu (za REFERENCNI delku 1 m) ---
# cfg_dily uz ma sloupce weight_kg_approx / price_czk_approx - protoze vsechny
# alu profily maji katalogovy GLB vzorek standardizovany na 1000 mm, jsou tyto
# sloupce uz fakticky "hodnota pri 1 m delky". Puvodne se plnily jen hrubym
# odhadem z objemu*hustoty (viz convert_fbx_catalog.py); tenhle admin panel
# dovoli Robertovi zadat skutecne hodnoty rucne - appka pak sama dopocitava
# cenu/hmotnost pro jakoukoli jinou delku (viz currentWeightPrice() ve
# webapp/index.html - linearni prepocet podle pomeru aktualni/referencni delky).
#
# DULEZITE (oprava): KAZDE katalogove ID je samostatny radek se svou vlastni
# cenou/hmotnosti - i kdyz nekolik ID sdili stejny nominalni prurez (napr.
# Object_7/8/9 = 30x30), NIKDY se nesmi slucovat do jednoho radku. To byla
# chyba prvni verze teto tabulky (Robert to zamitl - "nemuze mit 1 profil
# vice objektu"). Kazdy Object_X je svuj vlastni fyzicky dil.
# REF_Object_* ID jsou vyrazena - to je jen interni referencni geometrie
# (ukazkovy spoj pouzity pro odvozeni presneho napojeni, viz VLASTNOSTI_
# PROFILU.md sekce 2c), ne skutecny prodejni profil, nema smysl mu cenu zadavat.

# Delka, na kterou jsou katalogove GLB vzorky profilu standardizovane (viz
# komentar vyse) - a zaroven jedine spolehlive rozliseni "prodejny profil"
# od ostatnich alu katalogovych dilu, viz filtr v admin_profily_list().
REFERENCNI_DELKA_MM = 1000.0


@app.get("/api/admin/profily")
@require_permission("ceny_profilu", "zobrazit")
def admin_profily_list():
    parts = fetch_katalog_parts()
    rows = []
    for p in parts:
        if p["layer"] != "alu":
            continue
        if p["id"].startswith("REF_"):
            continue
        if not p["cross_section_mm"] or p["cross_section_mm"][0] is None:
            continue
        # Robert 2026-09-09 ("proc je logo v cenach profilu?????"): do
        # ceniku se dostalo `logo_logiman_cz` - katalogovy dil ochranneho
        # loga, ktere se vklada do sestav. Ma `layer='alu'` zamerne (aby
        # ve scene vypadalo jako hlinik) a zname rozmery, takze obe
        # podminky vyse splnilo a vysvitilo v ceniku jako "profil"
        # 1.39x28 mm.
        #
        # `layer` je VIZUALNI MATERIAL pro scenu, ne priznak "tohle je
        # prodejny profil" - tady se ty dva vyznamy potkaly. Rozhoduje
        # proto REFERENCNI DELKA: tenhle cenik je za METR (Kc/m, kg/m),
        # takze do nej patri jen dil, ktery je jako metrovy referencni kus
        # opravdu zadany. Vsech 22 skutecnych profilu ma dim_y_mm=1000;
        # jediny dil s vrstvou alu, znamymi rozmery a jinou delkou je
        # prave logo (overeno dotazem nad cfg_dily 2026-09-09).
        if p["length_mm"] != REFERENCNI_DELKA_MM:
            continue
        rows.append({
            "id": p["id"],
            "name": p["name"],
            "cross_section_mm": p["cross_section_mm"],
            "length_mm_ref": p["length_mm"],
            "weight_kg_per_m": p["weight_kg_approx"],
            "price_czk_per_m": p["price_czk_approx_PLACEHOLDER"],
            "price_source_url": p.get("price_source_url"),
            "price_per_cut_czk": p.get("price_per_cut_czk"),
            # bot1, 2026-07-27: 5 puvodnich profilu (Object_1/2/7/11/14) uz
            # ma skutecny .glb model nahrany ve 3D scene odjinud (ne pres
            # tenhle FBX upload) - "_PENDING_" prefix v glb_file je jedine
            # rozliseni "meho pripraveny model" vs "zatim placeholder"
            # (Robert: "ty funkcni modely fbx ve scene prece mame").
            "has_scene_model": bool(p.get("file")) and not str(p.get("file")).startswith("_PENDING_"),
            "fbx_original_name": None,
            "fbx_uploaded_at": None,
            "dogus_price_usd": None,
            "dogus_price_usd_fetched_at": None,
            # bot16, 2026-09-24 (Robert pres bot3, pravidlo 52): srovnavaci
            # udaj z verejneho logiman.cz - viz komentar u JOINu nize a u
            # logiman_cz_price_reference tabulky (sql/2026-09-24c_...) proc
            # tohle NENI rozpor s "z logiman uz nic nebudeme tahat" (to
            # pravidlo je o NASI cene, tohle je jen srovnavaci zobrazeni).
            "logiman_sku": None,
            "logiman_price_per_m_czk": None,
            "logiman_product_url": None,
            "logiman_fetched_at": None,
        })
    rows.sort(key=lambda r: (r["cross_section_mm"][0], r["cross_section_mm"][1], r["id"]))

    # Doplnkovy dotaz jen na FBX evidenci (bot1, 2026-07-27) - drzeno oddelene
    # od fetch_katalog_parts(), aby se do te sdilene funkce nezasahovalo.
    # Robert 2026-09-18 ("chci pridat sloupec, primo cenu v USD z Dogus s
    # datem stazeni", pak "ja neco rucne opisu? blazne, kazdy tyden jede
    # smycka na stahovani cen z Dogusu... musi se to udrzovat zive") - ZADNE
    # rucni zadani. LEFT JOIN na shop_products.cfg_dily_id (1:1 vztah,
    # overeno - zadny cfg_dily_id nema vic nez 1 navazany produkt) - stejna
    # denni aktualizovana data, ktera uz shop_products.dogus_list_price_usd
    # ma z scripts/2026-08-09_dogus_price_recompute.py (viz tam - ten sklad
    # cfg_dily.price_czk_approx z TEHOZ behu, tenhle dotaz jen cte navic i
    # USD + price_last_refreshed_at, ne dogus_matched_at - to je jednorazove
    # datum PAROVANI s Dogus katalogem, ne datum posledniho stazeni ceny).
    #
    # bot16, 2026-09-24: druhy LEFT JOIN na logiman_cz_price_reference,
    # parovany PRES sp.sku (Robert: "SKU je parovaci znak") - tabulku plni
    # samostatny periodicky crawl (scripts/2026-09-24_logiman_price_
    # reference_crawl.py), tady se jen CTE uz hotovy vysledek, zadny zivy
    # fetch logiman.cz pri kazdem nacteni teto zalozky.
    if rows:
        ids = [r["id"] for r in rows]
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                placeholders = ",".join(["%s"] * len(ids))
                cur.execute(
                    f"SELECT cd.id, cd.fbx_original_name, cd.fbx_uploaded_at, "
                    f"sp.dogus_list_price_usd, sp.price_last_refreshed_at, sp.sku, "
                    f"lpr.price_per_m_czk AS logiman_price_per_m_czk, "
                    f"lpr.product_url AS logiman_product_url, lpr.fetched_at AS logiman_fetched_at "
                    f"FROM cfg_dily cd LEFT JOIN shop_products sp ON sp.cfg_dily_id = cd.id "
                    f"LEFT JOIN logiman_cz_price_reference lpr ON lpr.sku = sp.sku "
                    f"WHERE cd.id IN ({placeholders})",
                    ids,
                )
                fbx_by_id = {row["id"]: row for row in cur.fetchall()}
        finally:
            conn.close()
        for r in rows:
            info = fbx_by_id.get(r["id"])
            if info:
                r["fbx_original_name"] = info["fbx_original_name"]
                r["fbx_uploaded_at"] = info["fbx_uploaded_at"].isoformat() if info["fbx_uploaded_at"] else None
                r["dogus_price_usd"] = (
                    float(info["dogus_list_price_usd"]) if info["dogus_list_price_usd"] is not None else None
                )
                r["dogus_price_usd_fetched_at"] = (
                    info["price_last_refreshed_at"].isoformat() if info["price_last_refreshed_at"] else None
                )
                r["logiman_sku"] = info["sku"]
                r["logiman_price_per_m_czk"] = (
                    float(info["logiman_price_per_m_czk"]) if info["logiman_price_per_m_czk"] is not None else None
                )
                r["logiman_product_url"] = info["logiman_product_url"]
                r["logiman_fetched_at"] = (
                    info["logiman_fetched_at"].isoformat() if info["logiman_fetched_at"] else None
                )

    return jsonify({"rows": rows})


@app.get("/api/admin/profily/fio-rate")
@require_permission("ceny_profilu", "zobrazit")
def admin_profily_fio_rate():
    """Živý kurz USD/CZK Fio banka "Devizové kurzy, Prodej" - bot16,
    2026-09-24 (Robert přes bot3, WORKFLOW.md pravidlo 52 "nic se
    neodkládá"): nový sloupec "Cena v Kč (živý kurz)" v záložce Ceny
    profilů (webapp/admin/js/ceny.js) hned vedle "Cena USD (Dogus)".

    NENÍ totéž jako `shop_products.dogus_price_rate_used` - ten je kurz
    POUŽITÝ PŘI POSLEDNÍM TÝDENNÍM PŘEPOČTU (neděle 3:20,
    scripts/2026-08-09_dogus_price_recompute.py), tedy historická
    hodnota. Tenhle endpoint vrací AKTUÁLNÍ kurz stažený PRÁVĚ TEĎ (při
    každém volání znovu, žádné cachování na serveru) - stejnou funkcí
    (`fio_rate.fetch_fio_usd_czk_sell_rate`), kterou používá i denní
    skript, aby definice "devize prodej" nikdy nedrifitovala mezi
    oběma místy.

    WORKFLOW.md pravidlo 9 - ŽÁDNÝ fallback na starou/odhadnutou
    hodnotu: když živý fetch selže, vrací se `rate: null` + `error`
    (HTTP 502), frontend to MUSÍ zobrazit jako "kurz nedostupný", ne
    dopočítat se starým číslem."""
    fetched_at = datetime.datetime.utcnow().isoformat() + "Z"
    try:
        rate = fetch_fio_usd_czk_sell_rate()
    except Exception as e:
        return jsonify({
            "rate": None,
            "fetched_at": fetched_at,
            "source_url": FIO_RATE_URL,
            "error": str(e),
        }), 502
    return jsonify({
        "rate": rate,
        "fetched_at": fetched_at,
        "source_url": FIO_RATE_URL,
        "error": None,
    })


# --- Admin: Dogus cena na e-shopu vs. živý vzorec, rozdělené na 3 sekce ---
# Robert pres bot3 (2026-09-24), navazuje primo na sloupec
# content_categories.dogus_sale_unit (viz sql/2026-09-24e_..., FINALNI
# pevna klasifikace - "podle DOGUS SEKCE, zadne odvozovani") a na
# scripts/2026-08-09_dogus_price_recompute.py (TYDENNI skript, ktery
# tenhle vzorec skutecne pouziva a zapisuje do
# shop_products.price_czk_placeholder). Tahle admin zalozka NIC
# NEZAPISUJE (cisté READ-ONLY porovnani) - jen ukazuje, u kterych
# polozek by se PRAVE TED (se ZIVYM kurzem Fio, ne historickym
# shop_products.dogus_price_rate_used z posledniho nedelniho behu)
# spocitala jina cena, nez jakou ma e-shop ulozenou.
#
# Puvodni zadani chtelo JEDNU tabulku s filtrem podle zarazeni - Robert
# pres bot3 to zmenil na TRI SAMOSTATNE SEKCE (tyc_3m / metraz / kus),
# kazda s vlastnim vzorcem "na prvni pohled" a vlastnim nezavislym
# filtrem "jen kde se lisi" - viz webapp/admin/js/dogus-vzorec.js.
#
# JEDNO MISTO PRAVDY PRO VZOREC (_dogus_formula_kc nize) - pouziva ho
# jak JSON endpoint (admin_dogus_cena_vzorec), tak CSV export
# (admin_dogus_cena_vzorec_export), aby se definice nikdy nerozjely
# mezi zobrazenim a exportem (stejny princip jako fio_rate.py).
_DOGUS_VZOREC_SECTIONS = ("tyc_3m", "metraz", "kus")


def _dogus_formula_kc(sale_unit, usd, rate, coef):
    """Vraci (zaokrouhlena_cena_kc, text_vypoctu) - PRESNE stejny vzorec
    jako scripts/2026-08-09_dogus_price_recompute.py (viz tam pro
    historii rozhodnuti), jen s libovolnym (typicky ZIVYM) kurzem misto
    kurzu ulozeneho pri poslednim dennim behu.

    DULEZITE (bot3/Robert, 2026-09-24, WORKFLOW.md pravidlo 9 prepsano
    commitem 00d84d68): "cele koruny vzdy nahoru" plati pro VSECHNY tri
    skupiny stejne, tyc_3m NENI vyjimka s round(). Puvodni verze tady
    mela round() pro tyc_3m - byla to MOJE chyba proti aktualnimu
    pravidlu, ne bug ve skriptu. Sjednoceni je zamer, needit zpatky."""
    raw = usd * rate * coef
    if sale_unit == "tyc_3m":
        raw_tyc = raw * 3.0
        final = math.ceil(raw_tyc)
        text = (
            f"{usd:.2f} $ × {rate:.3f} Kč/$ × {coef:.2f} × 3 = {raw_tyc:.2f} Kč → ↑{final} Kč"
            " (1 ks = tyč 3 m)"
        )
        return final, text
    if sale_unit == "metraz":
        final = math.ceil(raw)
        text = f"{usd:.2f} $ × {rate:.3f} Kč/$ × {coef:.2f} = {raw:.2f} Kč/m → ↑{final} Kč/m"
        return final, text
    # "kus" - vsechno ostatni (DEFAULT), viz sql/2026-09-24e_...
    final = math.ceil(raw)
    text = f"{usd:.2f} $ × {rate:.3f} Kč/$ × {coef:.2f} = {raw:.2f} Kč → ↑{final} Kč"
    return final, text


def _dogus_vzorec_fetch_rows(category_id=None):
    """category_id nepovinny filtr - pouziva ho jen CSV export (nize), aby
    export presne odpovidal filtru "Kategorie" zvolenemu v UI
    (webapp/admin/js/dogus-vzorec.js). Hlavni JSON endpoint filtr
    NEPOSILA (vraci vzdy VSECHNY radky) - filtrovani/strankovani tabulky
    resi frontend nad jednou cache, viz komentar u admin_dogus_cena_vzorec()."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            where = "WHERE p.active=1 AND p.is_archived=0 AND p.dogus_url IS NOT NULL"
            params = []
            if category_id:
                where += " AND p.category_id=%s"
                params.append(category_id)
            # bot16, 2026-09-24 (Robert pres bot3, pravidlo 52): LEFT JOIN na
            # logiman_cz_price_export - JEDNORAZOVY Robertuv xlsx import (viz
            # sql/2026-09-24f_..., NENI totez jako prubezne crawlovana
            # logiman_cz_price_reference pouzita v zalozce "Ceny profilu",
            # viz komentar u te tabulky proc jsou zamerne oddelene).
            cur.execute(
                "SELECT p.id, p.sku, p.name, p.slug, p.category_id, c.name AS category_name, "
                "c.dogus_sale_unit, c.dogus_price_coefficient, "
                "p.dogus_list_price_usd, p.dogus_price_rate_used, p.dogus_url, "
                "p.price_czk_placeholder, p.price_last_refreshed_at, "
                "lpe.price_czk AS logiman_export_price_czk, lpe.product_name AS logiman_export_name, "
                "lpe.imported_at AS logiman_export_imported_at "
                "FROM shop_products p JOIN content_categories c ON c.id = p.category_id "
                "LEFT JOIN logiman_cz_price_export lpe ON lpe.sku = p.sku "
                + where +
                " ORDER BY c.dogus_sale_unit, p.category_id, p.name",
                params,
            )
            return cur.fetchall()
    finally:
        conn.close()


# bot16, 2026-09-24 (Robert pres bot3, pravidlo 52) - prah pro rozliseni
# "logiman.cz cena vypada jako za CELOU 3m tyc" vs "cena vypada jako za
# 1 m" u METRAZOVYCH polozek (tesneni apod.). Robert/bot3 rucne overili
# priklady: 7 z 39 metrazovych polozek (kryci listy, U listy) ma pomer
# logiman_cena / nase_cena_za_m v rozmezi 2.76-2.95 (= cena za CELOU tyc
# 3m, kterou logiman.cz u techhle konkretnich produktu prodava), zbylych
# 32 (tesneni) ma pomer 0.69-1.54 (= cena SKUTECNE za 1 m). Mezi obema
# skupinami je v datech CISTA MEZERA (zadna polozka nema pomer mezi 1.54
# a 2.76) - prah 2.15 (stred te mezery) je proto spolehlivy, overeny
# primo na datech, NE naslepo prevzaty odhad "kolem 3". Blizsi pomer k
# primemu 1:1 (misto k 1:3) NENI spolehlivy diskriminator sam o sobe -
# 2 z 32 "za metr" polozek maji pomer 1.54, jejich pomer/3 (0.51) je
# NAHODOU blizsi 1 nez primy pomer (0.54 od 1) - proto se NEPOUZIVA
# "ktery pomer je blize 1", ale pevny prah na PRIMEM pomeru.
_METRAZ_ROD_RATIO_THRESHOLD = 2.15


def _logiman_export_diff(actual_price, logiman_price):
    """(diff_kc, diff_pct) - STEJNA konvence jako uz existujici formula-diff
    (dogusVzorecDiffCellHtml v JS), ALE zamerne S JINOU BAZI procenta:
    tady je baze cena logiman.cz (ne nase vlastni cena) - "o kolik % jsme
    drazsi/levnejsi NEZ logiman.cz", overeno primo proti bot3 zadanym
    medianum (tyc_3m +10.8 %, kus -5.1 %) - s bazi "nase cena" by vysla
    jina cisla. Kdyz je logiman_price 0, procento se nepocita (deleni 0)."""
    if actual_price is None or logiman_price is None:
        return None, None
    diff_kc = actual_price - logiman_price
    diff_pct = (diff_kc / logiman_price * 100) if logiman_price else None
    return diff_kc, diff_pct


def _logiman_export_metraz_info(actual_per_m, logiman_price):
    """Pro metrazove polozky vraci VSECHNY slozky, ze kterych si Robert
    sam muze udelat obrazek - viz komentar u _METRAZ_ROD_RATIO_THRESHOLD
    a WORKFLOW.md/zadani bot3 "nekolabovat do jedne odpovedi". Nikdy
    nevraci jen jedno "spravne" cislo."""
    our_x3 = actual_per_m * 3 if actual_per_m is not None else None
    ratio_direct = None
    if actual_per_m and logiman_price is not None:
        ratio_direct = logiman_price / actual_per_m if actual_per_m else None
    basis_guess = None
    if ratio_direct is not None:
        basis_guess = "per_3m_rod" if ratio_direct > _METRAZ_ROD_RATIO_THRESHOLD else "per_meter"
    diff_kc_per_m, diff_pct_per_m = _logiman_export_diff(actual_per_m, logiman_price)
    diff_kc_x3, diff_pct_x3 = _logiman_export_diff(our_x3, logiman_price)
    return {
        "our_price_per_m_czk": actual_per_m,
        "our_price_x3_czk": our_x3,
        "ratio_logiman_to_our_per_m": ratio_direct,
        "basis_guess": basis_guess,
        "diff_per_m_kc": diff_kc_per_m, "diff_per_m_pct": diff_pct_per_m,
        "diff_x3_kc": diff_kc_x3, "diff_x3_pct": diff_pct_x3,
    }


@app.get("/api/admin/dogus-cena-vzorec")
@require_permission("dogus_cena", "zobrazit")
def admin_dogus_cena_vzorec():
    """Vsechny Dogus-parovane polozky (598 celkem, 597 s dogus cenou; WHERE stejne jako denni
    prepocet), rozdelene do 3 sekci podle content_categories.dogus_sale_unit
    (bot5, viz sql/2026-09-24e_...). `rate` (zivy kurz Fio, frontend ho
    ziska jednou z GET /api/admin/profily/fio-rate a posle sem jako
    query parametr - NEstahuje se tady znovu, WORKFLOW.md "jednou za
    nacteni stranky, ne za radek") - kdyz chybi/neni cislo, radky se
    vrati BEZ spocitane ceny/rozdilu (frontend to zobrazi jako "kurz
    nedostupny", stejne jako existujici sloupec v Cenach profilu).

    bot16, 2026-09-24 (pravidlo 52, dokonceni zadani): kazdy radek navic
    nese srovnani s `logiman_cz_price_export` (Robertuv jednorazovy xlsx
    import, viz sql/2026-09-24f_...) - `logiman_export_price_czk` +
    rozdil. Metrazova sekce ma navic `logiman_metraz_info` (obe baze -
    za 1 m i za celou tyc 3 m - viz _logiman_export_metraz_info). Navic
    vraci `unmatched` (SKU parovani v obou smerech, viz
    _logiman_export_unmatched)."""
    rate = request.args.get("rate", type=float)
    rows = _dogus_vzorec_fetch_rows()

    sections = {k: [] for k in _DOGUS_VZOREC_SECTIONS}
    for r in rows:
        sale_unit = r["dogus_sale_unit"] if r["dogus_sale_unit"] in sections else "kus"
        usd = float(r["dogus_list_price_usd"]) if r["dogus_list_price_usd"] is not None else None
        coef = float(r["dogus_price_coefficient"]) if r["dogus_price_coefficient"] is not None else None
        actual = float(r["price_czk_placeholder"]) if r["price_czk_placeholder"] is not None else None
        formula_czk, calc_text, differs = None, None, None
        if usd is not None and coef is not None and rate:
            formula_czk, calc_text = _dogus_formula_kc(sale_unit, usd, rate, coef)
            if actual is not None:
                differs = round(actual) != formula_czk

        logiman_export_price = (
            float(r["logiman_export_price_czk"]) if r["logiman_export_price_czk"] is not None else None
        )
        logiman_export_diff_kc, logiman_export_diff_pct = _logiman_export_diff(actual, logiman_export_price)
        row_out = {
            "id": r["id"], "sku": r["sku"], "name": r["name"], "slug": r["slug"],
            "category_id": r["category_id"], "category_name": r["category_name"],
            "dogus_url": r["dogus_url"],
            "dogus_list_price_usd": usd, "coefficient": coef,
            "dogus_price_rate_used": (
                float(r["dogus_price_rate_used"]) if r["dogus_price_rate_used"] is not None else None
            ),
            "actual_price_czk": actual,
            "price_last_refreshed_at": (
                r["price_last_refreshed_at"].isoformat() if r["price_last_refreshed_at"] else None
            ),
            "formula_price_czk": formula_czk, "formula_calc_text": calc_text, "differs": differs,
            "logiman_export_price_czk": logiman_export_price,
            "logiman_export_name": r["logiman_export_name"],
            "logiman_export_imported_at": (
                r["logiman_export_imported_at"].isoformat() if r["logiman_export_imported_at"] else None
            ),
            "logiman_export_diff_kc": logiman_export_diff_kc,
            "logiman_export_diff_pct": logiman_export_diff_pct,
        }
        if sale_unit == "metraz":
            row_out["logiman_metraz_info"] = _logiman_export_metraz_info(actual, logiman_export_price)
        sections[sale_unit].append(row_out)
    return jsonify({
        "sections": sections, "fio_rate_used": rate,
        "unmatched": _logiman_export_unmatched(),
    })


def _logiman_export_unmatched():
    """Parovani SKU logiman_cz_price_export <-> nas aktivni/zarazeny katalog
    OBEMA smery (Robert/bot3, pravidlo 52 - "76 v souboru co nemame" a "84
    co mame a v souboru neni" jsou NEZAVISLE zajimava cisla, nemazat je
    tise, ukazat). Stejna definice "nas aktivni katalog" jako pouziva
    hlavni prehled (`p.active=1 AND p.is_archived=0`, JOIN na
    content_categories - produkt bez zarazene kategorie se do porovnani
    nezapocitava, presne overeno proti bot3 zadanym cislum 540/76/84)."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT lpe.sku, lpe.product_name, lpe.price_czk "
                "FROM logiman_cz_price_export lpe "
                "WHERE NOT EXISTS ("
                "  SELECT 1 FROM shop_products p JOIN content_categories c ON c.id = p.category_id"
                "  WHERE p.sku = lpe.sku AND p.active=1 AND p.is_archived=0"
                ") ORDER BY lpe.sku"
            )
            file_only = [
                {"sku": r["sku"], "name": r["product_name"],
                 "price_czk": float(r["price_czk"]) if r["price_czk"] is not None else None}
                for r in cur.fetchall()
            ]
            cur.execute(
                "SELECT p.id, p.sku, p.name, p.slug, c.name AS category_name, p.dogus_url IS NOT NULL AS has_dogus "
                "FROM shop_products p JOIN content_categories c ON c.id = p.category_id "
                "WHERE p.active=1 AND p.is_archived=0 "
                "AND NOT EXISTS (SELECT 1 FROM logiman_cz_price_export lpe WHERE lpe.sku = p.sku) "
                "ORDER BY c.name, p.name"
            )
            catalog_only = [
                {"id": r["id"], "sku": r["sku"], "name": r["name"], "slug": r["slug"],
                 "category_name": r["category_name"], "has_dogus": bool(r["has_dogus"])}
                for r in cur.fetchall()
            ]
    finally:
        conn.close()
    return {
        "file_not_in_catalog_count": len(file_only), "file_not_in_catalog": file_only,
        "catalog_not_in_file_count": len(catalog_only), "catalog_not_in_file": catalog_only,
    }


@app.get("/api/admin/dogus-cena-vzorec/export.csv")
@require_permission("dogus_cena", "zobrazit")
def admin_dogus_cena_vzorec_export():
    """CSV export presne toho, co admin zrovna vidi (kazda ze 3 sekci ma
    vlastni nezavisly filtr "jen kde se lisi", proto only_diff_<sekce>
    zvlast pro kazdou) - jeden sloupec "sekce" navic, aby rozliseni
    prezilo i mimo admin UI (Robert pres bot3, 2026-09-24)."""
    rate = request.args.get("rate", type=float)
    only_diff = {
        "tyc_3m": request.args.get("only_diff_tyc_3m") == "1",
        "metraz": request.args.get("only_diff_metraz") == "1",
        "kus": request.args.get("only_diff_kus") == "1",
    }
    section_label = {"tyc_3m": "Tyče 3 m", "metraz": "Metráž", "kus": "Kusové položky"}
    category_id = request.args.get("category_id", type=int)
    rows = _dogus_vzorec_fetch_rows(category_id)

    output = io.StringIO()
    writer = csv.writer(output)
    # bot16, 2026-09-24 (dokoncenim uz existujici WIP - doplneny sloupce
    # chybejici oproti puvodnimu zadani "kompletni cenik vcetne prepoctu a
    # financi ceny"): dogus_url (odkaz na dodavatelskou stranku), datum
    # stazeni USD ceny (shop_products.price_last_refreshed_at, aktualizuje
    # se VE STEJNEM UPDATE jako dogus_list_price_usd - viz recompute
    # skript), kurz POUZITY PRI POSLEDNIM TYDENNIM PREPOCTU (jiny udaj nez
    # "kurz_fio_zivy" = aktualni kurz pouzity PRAVE PRO TENHLE export) a
    # rozdil v procentech (vedle uz existujiciho rozdil_kc).
    writer.writerow([
        "sekce", "id", "sku", "dogus_url", "nazev", "kategorie", "dogus_usd",
        "dogus_usd_stazeno_at", "kurz_fio_zivy", "koeficient", "vzorec_kc",
        "cena_eshop_kc", "kurz_pri_poslednim_dennim_prepoctu", "rozdil_kc",
        "rozdil_pct", "lisi_se",
        # bot16, 2026-09-24 (pravidlo 52) - srovnani s Robertovym jednorazovym
        # xlsx exportem logiman.cz (logiman_cz_price_export, viz
        # sql/2026-09-24f_...). U metraze navic DVE baze (za 1 m / za celou
        # tyc 3 m), viz _logiman_export_metraz_info - rozdil_kc/rozdil_pct u
        # metraze je vzdy vuci bazi "za 1 m", sloupce metraz_* ukazuji obe
        # varianty zvlast, aby se nic neschovalo do jednoho cisla.
        "logiman_cz_export_cena_kc", "logiman_cz_export_rozdil_kc", "logiman_cz_export_rozdil_pct",
        "metraz_nase_cena_x3_kc", "metraz_rozdil_x3_kc", "metraz_rozdil_x3_pct", "metraz_odhad_baze",
    ])
    n = 0
    for r in rows:
        sale_unit = r["dogus_sale_unit"] if r["dogus_sale_unit"] in only_diff else "kus"
        usd = float(r["dogus_list_price_usd"]) if r["dogus_list_price_usd"] is not None else None
        coef = float(r["dogus_price_coefficient"]) if r["dogus_price_coefficient"] is not None else None
        actual = float(r["price_czk_placeholder"]) if r["price_czk_placeholder"] is not None else None
        rate_used = float(r["dogus_price_rate_used"]) if r["dogus_price_rate_used"] is not None else None
        fetched_at = r["price_last_refreshed_at"].isoformat() if r["price_last_refreshed_at"] else None
        formula_czk, differs, diff_kc, diff_pct = None, None, None, None
        if usd is not None and coef is not None and rate:
            formula_czk, _ = _dogus_formula_kc(sale_unit, usd, rate, coef)
            if actual is not None:
                differs = round(actual) != formula_czk
                diff_kc = actual - formula_czk
                diff_pct = (diff_kc / actual * 100) if actual else None
        if only_diff.get(sale_unit) and not differs:
            continue

        logiman_export_price = (
            float(r["logiman_export_price_czk"]) if r["logiman_export_price_czk"] is not None else None
        )
        logiman_export_diff_kc, logiman_export_diff_pct = _logiman_export_diff(actual, logiman_export_price)
        metraz_x3_kc, metraz_x3_diff_kc, metraz_x3_diff_pct, metraz_basis = "", "", "", ""
        if sale_unit == "metraz":
            info = _logiman_export_metraz_info(actual, logiman_export_price)
            metraz_x3_kc = info["our_price_x3_czk"] if info["our_price_x3_czk"] is not None else ""
            metraz_x3_diff_kc = info["diff_x3_kc"] if info["diff_x3_kc"] is not None else ""
            metraz_x3_diff_pct = f"{info['diff_x3_pct']:.1f}" if info["diff_x3_pct"] is not None else ""
            metraz_basis = info["basis_guess"] or ""

        n += 1
        writer.writerow([
            section_label[sale_unit], r["id"], r["sku"], r["dogus_url"] or "", r["name"], r["category_name"],
            usd if usd is not None else "", fetched_at or "", rate if rate else "",
            coef if coef is not None else "",
            formula_czk if formula_czk is not None else "",
            actual if actual is not None else "",
            rate_used if rate_used is not None else "",
            diff_kc if diff_kc is not None else "",
            f"{diff_pct:.1f}" if diff_pct is not None else "",
            ("ano" if differs else ("ne" if differs is not None else "")),
            logiman_export_price if logiman_export_price is not None else "",
            logiman_export_diff_kc if logiman_export_diff_kc is not None else "",
            f"{logiman_export_diff_pct:.1f}" if logiman_export_diff_pct is not None else "",
            metraz_x3_kc, metraz_x3_diff_kc, metraz_x3_diff_pct, metraz_basis,
        ])
    log_audit(current_user()["id"], "export", "shop_product", None, f"Dogus cena vs. vzorec: {n} položek")
    return Response(
        output.getvalue(), mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=dogus_cena_vs_vzorec.csv"},
    )


@app.post("/api/admin/step-quality-preview")
@require_permission("sklad_karty", "upravit")
def admin_step_quality_preview():
    """Nahled velikosti (kB) pro 3 stupne kvality prevodu STEP->GLB, PRED
    skutecnym nahranim - bot2, 2026-08-04. Robert: "potrebujeme pridat do
    skladovych karet, zatrzitkovac hned vedle nacteni 3D modelu, ma to
    byt vyber kvality 3D modelu... zaroven tam uvadejme velikost kB".
    Soubor se ulozi jen DOCASNE (smaze se hned po vygenerovani nahledu,
    viz step_convert.preview_step_qualities) - nic se nezapisuje do DB
    ani neprepisuje zadny existujici model/GLB. Jen pro .stp/.step - FBX
    pipeline zadnou volbu kvality nema."""
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify({"error": "Chybí soubor."}), 400
    safe_name = secure_filename(f.filename)
    src_ext = os.path.splitext(safe_name)[1].lower()
    if src_ext not in (".stp", ".step"):
        return jsonify({"error": "Náhled kvality je dostupný jen pro STEP soubory (.stp/.step)."}), 400
    if step_convert is None:
        return jsonify({"error": "Převodní modul (step_convert) není na serveru dostupný."}), 500

    with tempfile.TemporaryDirectory(prefix="step_preview_upload_") as td:
        tmp_step = os.path.join(td, safe_name)
        f.save(tmp_step)
        # bot16 2026-09-03 (revize bot3): vzdy jen JEDEN nahled naraz (3x
        # OpenCascade proces ~1 GB RAM) - flock napric gunicorn workery,
        # viz step_convert.step_convert_slot(); obsazeno = 409 bez cekani.
        try:
            with step_convert.step_convert_slot():
                qualities = step_convert.preview_step_qualities(tmp_step)
        except step_convert.StepConvertBusy:
            return jsonify({"error": "Server právě zpracovává jiný převod, zkus to za chvíli."}), 409

    return jsonify({"status": "ok", "qualities": qualities})

@app.post("/api/admin/profily/<pid>/fbx-upload")
@require_permission("ceny_profilu", "vytvorit")
def admin_profily_fbx_upload(pid):
    """Nahrani FBX 3D modelu k existujicimu radku ceniku (cfg_dily.id) - bot1,
    2026-07-27. Robert: "sem budu davat fbx modely techto novych profilu a
    musim je k tem v ceniku navazat", pak doplnil: "jakmile se fbx modely
    nahrajou supni je do sceny do katalogu". Soubor se uklada pod
    jednoznacnym nazvem <id>.fbx (prepise pripadny predchozi upload pro
    stejne ID). Hned po ulozeni se AUTOMATICKY zkusi prevod na GLB
    (fbx_convert.convert_single_fbx) - pri uspechu se rovnou prepise
    cfg_dily.glb_file (misto _PENDING_ placeholderu) a nastavi
    visible_in_scene=1, takze profil se OKAMZITE objevi ve 3D scene bez
    dalsiho zasahu. Pri selhani prevodu (poskozeny/nepodporovany FBX,
    zadna pouzitelna geometrie...) zustane surovy FBX i tak ulozeny a
    fbx_original_name/fbx_uploaded_at aktualizovane - jen se
    glb_file/visible_in_scene NEMENI, takze profil dal zustane skryty ve
    scene, dokud nedorazi opraveny soubor. Chyba prevodu NIKDY neshodi
    samotny upload (stejny princip failure-safe jako u support_ai.py)."""
    admin = current_user()
    parts = fetch_katalog_parts()
    valid_ids = {p["id"] for p in parts if p["layer"] == "alu" and not p["id"].startswith("REF_")}
    if pid not in valid_ids:
        return jsonify({"error": "Neznámé ID profilu."}), 404

    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify({"error": "Chybí soubor."}), 400
    safe_name = secure_filename(f.filename)
    src_ext = os.path.splitext(safe_name)[1].lower()
    if src_ext not in (".fbx", ".stp", ".step"):
        return jsonify({"error": "Očekávám soubor .fbx, .stp nebo .step."}), 400

    dest_path = os.path.join(FBX_UPLOAD_DIR, f"{pid}{src_ext}")
    f.save(dest_path)

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE cfg_dily SET fbx_original_name=%s, fbx_uploaded_at=NOW() WHERE id=%s",
                (safe_name, pid),
            )
        conn.commit()
    finally:
        conn.close()
    log_audit(admin["id"], "upload", "profil_fbx", None, f"{pid}: {safe_name}")

    conversion = {"attempted": True, "success": False, "error": None}
    glb_dest = os.path.join(KATALOG_GLB_DIR, f"{pid}.glb")
    ok, info = convert_uploaded_model_to_glb(dest_path, glb_dest)
    conversion["success"] = ok
    conversion["error"] = info.get("error")
    if ok:
        conn2 = get_conn()
        try:
            with conn2.cursor() as cur:
                cur.execute(
                    "UPDATE cfg_dily SET glb_file=%s, visible_in_scene=1 WHERE id=%s",
                    (f"{pid}.glb", pid),
                )
            conn2.commit()
        finally:
            conn2.close()
        log_audit(admin["id"], "convert", "profil_model_to_glb", None, f"{pid}: OK ({src_ext}, {info.get('vertices')}v/{info.get('faces', info.get('triangles_after_simplify'))}f)")
    else:
        log_audit(admin["id"], "convert", "profil_model_to_glb", None, f"{pid}: SELHALO ({src_ext}) - {info.get('error')}")

    return jsonify({
        "status": "ok",
        "id": pid,
        "fbx_original_name": safe_name,
        "conversion": conversion,
    })

@app.post("/api/admin/profily/new")
@require_permission("ceny_profilu", "vytvorit")
def admin_profily_create_new():
    """Novy katalogovy dil (Robert 2026-08-06: rucni skladani slozitejsich
    noh z profilovych dilu v custom_shapes "melo chyby" - misto skladani
    zkusit primo naimportovat hotovy 3D model cele nohy najednou).
    Na rozdil od /fbx-upload vyse (jen NAHRAZUJE model EXISTUJICIMU
    radku) tenhle rovnou ZAKLADA novy radek cfg_dily - "most do sceny/
    tvaru": po uspesnem prevodu se novy dil chova UPLNE stejne jako
    kterykoli jiny profil v katalogu (viditelny ve scene, konektory se
    pocitaji automaticky z geometrie stejnou funkci computeConnectorsLocal()
    jako u vsech ostatnich dilu - viz scene.html) - da se tedy normalne
    oznacit ve scene a Ctrl+S ulozit do Vlastnich tvaru (custom_shapes)
    presne jako drivejsi rucne skladane nohy, jen bez rucniho skladani
    z jednotlivych profilovych kousku.
    POZOR (predano dal Robertovi pri prvnim vyzkouseni): auto-detekce
    konektoru je jen geometricka heuristika (nejdelsi osa bounding-boxu =
    konce) navrzena pro rovne tyckovite profily - u slozitejsiho tvaru
    (napr. "schodova" konstrukce s odsazenym sloupkem) nemusi sedet
    presne tam, kde je fyzicky napojovaci bod. Nutne rucne zkontrolovat
    po vlozeni do sceny, ne jen duverovat automatu."""
    admin = current_user()
    name = (request.form.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Vyplň název dílu."}), 400
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify({"error": "Chybí soubor."}), 400
    safe_name = secure_filename(f.filename)
    src_ext = os.path.splitext(safe_name)[1].lower()
    if src_ext not in (".fbx", ".stp", ".step"):
        return jsonify({"error": "Očekávám soubor .fbx, .stp nebo .step."}), 400

    base_id = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") or "dil"
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            pid = base_id
            n = 1
            while True:
                cur.execute("SELECT id FROM cfg_dily WHERE id=%s", (pid,))
                if not cur.fetchone():
                    break
                n += 1
                pid = f"{base_id}_{n}"
            # glb_file je NOT NULL bez defaultu - "_PENDING_" placeholder,
            # dokud neprobehne prevod (stejna konvence jako jinde v tomhle
            # souboru, viz komentar u has_scene_model v admin.html).
            cur.execute(
                "INSERT INTO cfg_dily (id, name, layer, glb_file, visible_in_scene) VALUES (%s,%s,'alu',%s,0)",
                (pid, name, "_PENDING_"),
            )
        conn.commit()
    finally:
        conn.close()

    dest_path = os.path.join(FBX_UPLOAD_DIR, f"{pid}{src_ext}")
    f.save(dest_path)
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE cfg_dily SET fbx_original_name=%s, fbx_uploaded_at=NOW() WHERE id=%s",
                (safe_name, pid),
            )
        conn.commit()
    finally:
        conn.close()
    log_audit(admin["id"], "create", "profil_novy_dil", None, f"{pid}: {name}")

    conversion = {"attempted": True, "success": False, "error": None}
    glb_dest = os.path.join(KATALOG_GLB_DIR, f"{pid}.glb")
    ok, info = convert_uploaded_model_to_glb(dest_path, glb_dest)
    conversion["success"] = ok
    conversion["error"] = info.get("error")
    if ok:
        conn2 = get_conn()
        try:
            with conn2.cursor() as cur:
                cur.execute("UPDATE cfg_dily SET glb_file=%s, visible_in_scene=1 WHERE id=%s", (f"{pid}.glb", pid))
            conn2.commit()
        finally:
            conn2.close()
        log_audit(admin["id"], "convert", "profil_model_to_glb", None, f"{pid}: OK ({src_ext})")
    else:
        log_audit(admin["id"], "convert", "profil_model_to_glb", None, f"{pid}: SELHALO ({src_ext}) - {info.get('error')}")

    return jsonify({
        "status": "ok", "id": pid, "name": name,
        "fbx_original_name": safe_name, "conversion": conversion,
    }), 201

@app.delete("/api/admin/profily/<pid>")
@require_permission("ceny_profilu", "smazat")
def admin_profily_delete(pid):
    # Robert 2026-08-09 ("dej v levem katalogu sceny moznost smazani
    # polozky") - primo z leveho stromoveho katalogu sceny (viz
    # scene.html makePartButton) jde smazat spatne/testovaci katalogovy
    # dil (napr. "rrrrr"/"tchibo_dvojstul", drive rucne mazane primo v
    # DB). Blokovano, pokud je dil navazany na aktivni shop_products
    # kartu (cfg_dily_id) - nejdriv zrusit vazbu tam, jinak by produkt
    # ztratil merne udaje (viz _effective_unit_price/cfg_dily JOIN).
    admin = current_user()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT name, glb_file, thumbnail_file, fbx_original_name FROM cfg_dily WHERE id=%s", (pid,))
            row = cur.fetchone()
            if not row:
                return jsonify({"error": "Díl neexistuje."}), 404
            cur.execute("SELECT COUNT(*) c FROM shop_products WHERE cfg_dily_id=%s", (pid,))
            linked = cur.fetchone()["c"]
            if linked:
                return jsonify({"error": f"Díl je navázán na {linked} produkt(y) na skladě - "
                                          f"nejdřív zruš vazbu na skladové kartě, pak smaž znovu."}), 400
            cur.execute("DELETE FROM cfg_dily WHERE id=%s", (pid,))
        conn.commit()
    finally:
        conn.close()

    for fname in (row.get("glb_file"), row.get("thumbnail_file")):
        if not fname:
            continue
        try:
            os.remove(os.path.join(KATALOG_GLB_DIR, fname.split("?")[0]))
        except OSError:
            pass
    if row.get("fbx_original_name"):
        for src in glob.glob(os.path.join(FBX_UPLOAD_DIR, f"{pid}.*")):
            try:
                os.remove(src)
            except OSError:
                pass

    log_audit(admin["id"], "delete", "profil", None, f"{pid}: {row['name']}")
    return jsonify({"status": "ok"})

@app.post("/api/admin/profily")
@require_permission("ceny_profilu", "vytvorit")
def admin_profily_save():
    body = request.get_json(silent=True) or {}
    updates = body.get("updates") or []
    if not isinstance(updates, list) or not updates:
        return jsonify({"error": "Chybi 'updates' (seznam radku ke ulozeni)."}), 400

    parts = fetch_katalog_parts()
    valid_ids = {p["id"] for p in parts if p["layer"] == "alu" and not p["id"].startswith("REF_")}

    conn = get_conn()
    saved = 0
    try:
        with conn.cursor() as cur:
            for u in updates:
                pid = u.get("id")
                if pid not in valid_ids:
                    continue
                weight = u.get("weight_kg_per_m")
                price = u.get("price_czk_per_m")
                cut_price = u.get("price_per_cut_czk")
                weight = float(weight) if weight not in (None, "") else None
                price = float(price) if price not in (None, "") else None
                cut_price = float(cut_price) if cut_price not in (None, "") else None
                cur.execute(
                    "UPDATE cfg_dily SET weight_kg_approx=%s, price_czk_approx=%s, price_per_cut_czk=%s WHERE id=%s",
                    [weight, price, cut_price, pid],
                )
                saved += 1
        conn.commit()
    finally:
        conn.close()
    return jsonify({"status": "ok", "rows_saved": saved})

# bot16, 2026-09-24 (Robert pres bot3, pravidlo 52): "POST /api/admin/
# profily/<pid>/refresh" (tlacitko "Obnovit z e-shopu" v radku Ceny
# profilu) smazano - Robert: "obnovit z eshopu nechapu a nechci to tam
# uz, smazat". Overeno gre-pem pred smazanim, ze zadny jiny kod na
# tenhle endpoint nevolal (webapp/admin/js/ceny.js::refreshPriceRow()
# byl JEDINY volajici) - hromadne "Obnovit vse"/"Obnovit vybrane"
# tlacitka (refresh-all/bulk-refresh nize) volaji primo Python funkci
# refresh_price_for_row(), ne tenhle HTTP endpoint, takze zustavaji
# funkcni beze zmeny.

@app.put("/api/admin/profily/<pid>/color")
@require_permission("ceny_profilu", "upravit")
def admin_profily_set_color(pid):
    """Robert 2026-08-11 ("tato barva se priradi natrvalo k danemu ID
    objektu i po zavreni browseru"): vychozi barva profilu ve 3D scene.
    Protejsek pro produkty uz existuje (PUT /api/shop/products/<id>
    s color_hex). Prazdna hodnota = zrusit barvu (NULL)."""
    body = request.get_json(silent=True) or {}
    color = (body.get("color_hex") or "").strip() or None
    if color and not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
        return jsonify({"error": "Neplatná barva (očekávám #rrggbb)."}), 400
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE cfg_dily SET color_hex=%s WHERE id=%s", (color, pid))
        conn.commit()
    finally:
        conn.close()
    return jsonify({"status": "ok"})

@app.put("/api/admin/profily/<pid>/source")
@require_permission("ceny_profilu", "upravit")
def admin_profily_set_source(pid):
    body = request.get_json(silent=True) or {}
    url = (body.get("price_source_url") or "").strip() or None
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE cfg_dily SET price_source_url=%s WHERE id=%s", (url, pid))
        conn.commit()
    finally:
        conn.close()
    return jsonify({"status": "ok"})

@app.post("/api/admin/profily/refresh-all")
@require_permission("ceny_profilu", "upravit")
def admin_profily_refresh_all():
    conn = get_conn()
    results = []
    try:
        with conn.cursor() as cur:
            # Robert 2026-08-08: "z logiman uz nic nebudeme tahat" - cena i
            # hmotnost uz nezavisi na price_source_url vubec - "vsechny"
            # tedy znamena VSECHNY radky, ne jen ty s vyplnenou URL.
            #
            # POZOR (bot16, 2026-09-24, at se tohle pravidlo nikdy neprecte
            # spatne): tenhle zakaz mluvi o NASI VLASTNI prodejni cene/
            # hmotnosti - tu uz pocitame z Dogus (viz WORKFLOW.md bod 9),
            # ne z logiman.cz. Novy srovnavaci sloupec "Cena logiman.cz"
            # (viz LEFT JOIN logiman_cz_price_reference v admin_profily_
            # list() vyse) tohle pravidlo NEPORUSUJE ani nerusi - je to
            # CISTE READ-ONLY referencni udaj k porovnani vedle nasi ceny,
            # nikdy vstup do vypoctu nase ceny/hmotnosti.
            cur.execute("SELECT id FROM cfg_dily")
            rows = cur.fetchall()
            for row in rows:
                results.append(refresh_price_for_row(cur, row["id"]))
        conn.commit()
    finally:
        conn.close()
    return jsonify({"results": results})

@app.post("/api/admin/profily/bulk-refresh")
@require_permission("ceny_profilu", "upravit")
def admin_profily_bulk_refresh():
    """Nacte ceny/hmotnosti jen u VYBRANYCH profilu (na rozdil od
    refresh-all, ktery dela uplne vsechny). Zadne bulk-delete pro tuhle
    tabulku - radky jsou odvozene z katalogu 3D dilu (fetch_katalog_parts),
    nejde je nezavisle smazat/vytvorit, jen refreshovat cenu/hmotnost.
    Id profilu jsou STRING (napr. "Object_7"), ne int - nelze pouzit
    parse_bulk_ids() (ta dela int(i)), proto lokalni validace."""
    body = request.get_json(silent=True) or {}
    ids = body.get("ids") or []
    if not isinstance(ids, list) or not ids:
        return jsonify({"error": "Vyber alespoň jednu položku."}), 400
    conn = get_conn()
    results = []
    try:
        with conn.cursor() as cur:
            for pid in ids:
                cur.execute("SELECT id FROM cfg_dily WHERE id=%s", (pid,))
                row = cur.fetchone()
                if not row:
                    results.append({"id": pid, "status": "error", "error": "Profil neexistuje."})
                    continue
                # Robert 2026-08-08: "z logiman uz nic nebudeme tahat", viz
                # stejna poznamka u refresh-all/refresh_price_for_row.
                results.append(refresh_price_for_row(cur, pid))
        conn.commit()
    finally:
        conn.close()
    return jsonify({"results": results})

