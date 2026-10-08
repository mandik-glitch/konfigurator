#!/usr/bin/env python3
"""Automat, ktery sam napoji schvalenou sestavu na kartu - a KDYZ
zadna karta pro dane vozidlo/konfiguraci jeste neexistuje, sam ji i
zalozi (bot5, 2026-09-17, Robert pres bot3: "chce automatizovany
proces vystaveni karet pro nove schvalene sestavy - zadny rucni dotaz
jako u ProAce dnes").

Doplnuje `konfigurator-card-auto-activate` (aktivuje kartu, kdyz ma
render) z DRIVEJSI strany retezu: `technicky_ok=1` -> [tenhle skript:
napojeni/zalozeni karty] -> [bot4 render_auto_dispatch: render] ->
[card_auto_activate: aktivace].

⭐ HISTORIE ROZHODNUTI (bot3, 2026-09-17): puvodni verze tohohle
skriptu (viz git historie) zalozeni NOVE karty zamerne NEDELALA sama -
jen zapisovala upozorneni do `bot_ukoly`, protoze zalozeni vyzaduje
nazev/SKU/kategorii/popisky (TEXT_FILTR.md) a volbu master mezi vic
schvalenymi variantami - vyssi riziko nez mechanicke napojeni na uz
existujici kartu. Robert to ROZHODL PRIMO (pres bot3): plnou
automatizaci chce i pro uplne nove vozidlo, riziko prijima vedome
("klidne radsi vratim dodatecne akci zpet"). Zmirnujici okolnost, o
kterou se rozhodnuti opira: i auto-zalozena karta zustava `active=0`,
dokud `card_auto_activate` neuvidi dokonceny render NA STEJNE sestave
- nejhorsi pripad je tedy "neaktivni karta se spatnym nazvem k
oprave", ne "zverejneny spatny produkt".

Mezera<70mm vyjimka (PLAN_TVORBY_SESTAV.md Faze 4, "04"): sestava se
napojenim TRVALE PRESKAKUJE (ne flaguje, ne pripominka priste) -
presna pojistka, ktera 2026-09-17 rano chybela a zpusobila regresi
(viz scripts/2026-09-17_bot5_fix_mezera04_shop_product_id.py).

K-kod: primo `karoserie_kod`, kdyz je vyplneny; jinak fallback stejnou
metodou jako api/production_overview.py::_resolve_vehicle() (dohledani
car_body_<id> dilu v datech sestavy -> car_bodies -> car_models) - viz
ProAce pripad 2026-09-17, kde primy sloupec byl NULL u cele rodiny.
Kdyz K-kod nejde dohledat VUBEC (zadny car_body dil ve scene), sestava
se preskoci a zapise do `bot_ukoly` - tohle NENI "nova karta", je to
chybejici zakladni identita vozidla, automat ji nemuze uhodnout.

⭐ NAZEV/POPIS NOVE KARTY - VYHRADNE ze STRUKTUROVANYCH katalogovych
poli, nikdy parsovanim volneho textu `product_assemblies.name`:
  - vozidlo: `car_models.name` (ocistene o "[K-XXX] — rozmery" pres
    stejny regex jako api/production_overview.py::_clean_vehicle_name,
    "znacka" pres `car_makes.name`, "rok" pres koncove "NN-" v ocistenem
    nazvu -> "(od 20NN)").
  - skladba boxu: `typologie_varianty.nazev` (napr. "220x3-170x2-120x3"
    = strukturovany format "vyska x pocet", oddeleny pomlckou) -
    prevedeno na "3× box výšky 220 mm, 2× 170 mm a 3× 120 mm". POKUD
    format neodpovida ocekavani (parsovani selze), pole zustava bez
    popisu skladby - "radsi chybejici nez uhodnuty".
  - kotveni/montaz: `regal_umisteni.kotveni_zakaznicky`/
    `montaz_zakaznicky` (stejna DB pole, ktera pouziva i verejne API
    `product_assemblies_public()`).
  - kategorie: vzdy `content_categories.id=247` ("Regály do auta") -
    STEJNA hodnota, kterou pouzily VSECHNY karty zalozene rucne tuhle
    session (K-020/K-289/K-170). Nesouvisi s probihajici (pozastavenou)
    diskuzi o 3osé architekture kategorii s bot7 (ktera se tyka
    prestrukturovani VETVE 184 do budoucna, ne existence hodnoty na
    dnesnich kartach) - viz pamet category_149_materials_vs_autovestavby.

⭐ VOLBA MASTER mezi vic soucasne schvalenymi variantami: skore
"kompletnosti" z klicovych slov v `horni_blok_varianty.nazev` (vic
pásem/plna vyplna/police = vyssi skore, "jen ram"/"bez police" = nizsi)
- muj drivejsi rucni odhad (nejbohatsi schvalena varianta) prevedeny
na deterministicke pravidlo. Neni to nevratne rozhodnuti - `is_master`
jde kdykoli prehodit v adminu (auto-sync ceny).

⭐ RAZITKA + KOD_SESTAVY - `_orazitkuj_pri_zarazeni()`/`_dopocti_kod_
sestavy_pri_zarazeni()` (api/product_assemblies.py) jsou CISTE funkce
(cur, assembly_id[, raw_data]), NEZAVISI na `category_id` - volam je
PRIMO po kazdem napojeni (existujici i nove zalozena karta), `category_
id` na existujicich kartach zustava nedotcene.

Vypinac: app_settings['card_auto_link_povoleno'] = '0'.
Spousti konfigurator-card-auto-link.timer, kazdych 15 minut.
"""
import datetime
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _env import get_conn  # noqa: E402

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "api"))
import app  # noqa: E402,F401 - entry point, resolves circular imports drive/documents/scene_offers atd.
from app import _product_slug_for_name  # noqa: E402
from product_assemblies import (  # noqa: E402
    _orazitkuj_pri_zarazeni,
    _dopocti_kod_sestavy_pri_zarazeni,
)

CATEGORY_ID = 247  # "Regály do auta" - viz docstring
AVAILABILITY_TEXT = "3 - 5 týdnů"

_K_KOD_RE = re.compile(r"\[K-(\d+e?)\]")
_KOD_SUFFIX_RE = re.compile(r"\s*\[K-[^\]]*\]\s*—.*$")
_MODEL_YEAR_RE = re.compile(r"^(.*?)\s+(\d{2})-\s*$")
_BOXY_TOKEN_RE = re.compile(r"^(\d+)x(\d+)$")

# Klicova slova pro odhad "kompletnosti" horniho bloku (vyssi = pravdepodobneji
# bohatsi/reprezentativnejsi varianta pro vychozi obrazek+cenu karty).
_HB_SCORE_KEYWORDS = (
    ("s policí", 5),
    ("dvě pásma", 3),
    ("plné výplně", 2),
    ("jen rám", -3),
    ("bez horních příček", -1),
)


def _extract_k_kod(name):
    if not name:
        return None
    m = _K_KOD_RE.search(name)
    return f"K-{m.group(1)}" if m else None


def _resolve_karoserie_kod(cur, row):
    """`karoserie_kod` primo, kdyz je vyplneny; jinak dohledani pres
    car_body_<id> dil v datech sestavy (stejna metoda jako
    api/production_overview.py::_resolve_vehicle())."""
    if row["karoserie_kod"]:
        return row["karoserie_kod"]
    try:
        data = json.loads(row["data"] or "{}")
    except (TypeError, ValueError):
        return None
    for p in data.get("parts") or []:
        pid = str(p.get("part_id") or "")
        if pid.startswith("car_body_"):
            try:
                car_body_id = int(pid[len("car_body_"):])
            except ValueError:
                continue
            cur.execute(
                "SELECT cm.name AS car_model_name FROM car_bodies cb "
                "JOIN car_models cm ON cm.id = cb.model_id WHERE cb.id=%s",
                (car_body_id,),
            )
            r2 = cur.fetchone()
            if r2:
                kkod = _extract_k_kod(r2["car_model_name"])
                if kkod:
                    return kkod
    return None


def _vehicle_display(cur, karoserie_kod):
    """`car_models`/`car_makes` -> {"make", "model", "year_text"} nebo
    None, kdyz se vozidlo nedohleda. `model`/`year_text` ze strukturovane
    ocisteni `_KOD_SUFFIX_RE` + koncove "NN-" (stejny format napric
    celym katalogem, overeno na K-289/K-020/K-170 tuhle session)."""
    cur.execute(
        "SELECT cm.name, mk.name AS make FROM car_models cm "
        "JOIN car_makes mk ON mk.id = cm.make_id WHERE cm.name LIKE %s",
        (f"%[{karoserie_kod}]%",),
    )
    row = cur.fetchone()
    if not row:
        return None
    cleaned = _KOD_SUFFIX_RE.sub("", row["name"]).strip()
    m = _MODEL_YEAR_RE.match(cleaned)
    if m:
        model, yy = m.group(1).strip(), m.group(2)
        year_text = f"od 20{yy}"
    else:
        model, year_text = cleaned, None
    return {"make": row["make"], "model": model, "year_text": year_text}


def _boxy_popis(nazev):
    """'220x3-170x2-120x3' -> '3× box výšky 220 mm, 2× 170 mm a 3× 120 mm'.
    None, kdyz format neodpovida ocekavani - "radsi chybejici nez
    uhodnuty", zadny hadany text do popisu karty."""
    if not nazev:
        return None
    tokeny = []
    for chunk in nazev.split("-"):
        m = _BOXY_TOKEN_RE.match(chunk.strip())
        if not m:
            return None
        tokeny.append((m.group(1), m.group(2)))
    if not tokeny:
        return None
    casti = []
    for i, (vyska, pocet) in enumerate(tokeny):
        casti.append(f"{pocet}× box výšky {vyska} mm" if i == 0 else f"{pocet}× {vyska} mm")
    return casti[0] if len(casti) == 1 else ", ".join(casti[:-1]) + " a " + casti[-1]


def _hb_completeness_score(nazev):
    if not nazev:
        return -99
    n = nazev.lower()
    return sum(bod for klic, bod in _HB_SCORE_KEYWORDS if klic in n)


def _log(zprava):
    print(zprava)
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    entry = f"\n## card-auto-link (automaticky, scripts/2026-09-17_card_auto_link.py) — {ts}\n\n{zprava}\n"
    try:
        with open(os.path.join(REPO_ROOT, "AGENTS_LOG.md"), "a", encoding="utf-8") as f:
            f.write(entry)
    except OSError as e:
        print(f"[card-auto-link] zapis do AGENTS_LOG.md selhal: {e}", file=sys.stderr)


_TEMPLATE_APPROVAL_TAG = "[AUTO_TEMPLATE_APPROVAL:typologie_kod={kod}]"


def _typologie_ma_schvalenou_sablonu(cur, typologie_kod):
    """Bot9/bot3, 2026-09-17 (Robertovo primo upresneni): vizualni
    schvaleni auto-zalozenych karet se dela JEDNOU ZA TYPOLOGII, ne za
    kazdou kartu. Schvaleni = otevreny "na zed" ukol se strukturovanym
    tagem [AUTO_TEMPLATE_APPROVAL:typologie_kod=X] oznaceny Robertem
    jako hotovo (existujici admin UI Boti > Úkoly na zeď - zadna nova
    obrazovka)."""
    tag = _TEMPLATE_APPROVAL_TAG.format(kod=typologie_kod)
    cur.execute(
        "SELECT id FROM bot_ukoly WHERE bot_id='bot5' AND hotovo=1 AND text LIKE %s LIMIT 1",
        (f"%{tag}%",),
    )
    return cur.fetchone() is not None


def _pocet_auto_zalozenych_karet_typologie(cur, typologie_id):
    cur.execute(
        "SELECT COUNT(*) AS c FROM shop_products WHERE zalozeno_automaticky_typologie_id=%s",
        (typologie_id,),
    )
    return cur.fetchone()["c"]


def _zapsat_ukol_na_zed(cur, text):
    """`bot_ukoly` (bot_id='bot5') - jen kdyz NEEXISTUJE uz otevreny
    (hotovo=0) zaznam se STEJNYM textem (pojistka proti spamu)."""
    cur.execute("SELECT id FROM bot_ukoly WHERE bot_id='bot5' AND hotovo=0 AND text=%s", (text,))
    if cur.fetchone():
        return False
    cur.execute("INSERT INTO bot_ukoly (text, bot_id) VALUES (%s, 'bot5')", (text,))
    return True


def _oznac_a_napoj(cur, r, karta_id, sku_prefix):
    """Napoji sestavu na kartu + spusti razitka/kod_sestavy. Spolecne
    pro "existujici karta" i "nove zalozena karta" vetev."""
    cur.execute("UPDATE product_assemblies SET shop_product_id=%s WHERE id=%s", (karta_id, r["id"]))
    razitka_zprava = _orazitkuj_pri_zarazeni(cur, r["id"], r["data"])
    novy_kod = _dopocti_kod_sestavy_pri_zarazeni(cur, r["id"])
    return razitka_zprava, novy_kod


def _sestav_popis_karty(vehicle, box_popisy, kotveni_text, montaz_text):
    vehicle_label = vehicle["make"] + " " + vehicle["model"]
    if vehicle["year_text"]:
        vehicle_label += f" ({vehicle['year_text']})"
    if len(box_popisy) == 1:
        skladba_veta = f"Aktuální skladba: {box_popisy[0]}."
    elif len(box_popisy) == 2:
        skladba_veta = f"Na výběr jsou dvě skladby euroboxů: {box_popisy[0]}; nebo {box_popisy[1]}."
    else:
        skladba_veta = f"Na výběr je {len(box_popisy)} skladeb euroboxů: " + "; nebo ".join(box_popisy) + "."
    kotveni_montaz = " ".join(x for x in (kotveni_text, montaz_text) if x)
    description = (
        f"Hliníkový regálový systém do nákladového prostoru {vehicle_label}. {skladba_veta}\n\n"
        "Rozměry nejsou dané. Každý díl jde posunout, zvětšit nebo vynechat na milimetr "
        "přesně tak, aby sestava seděla na vaše kufry a nářadí.\n\n"
        f"{kotveni_montaz}"
    )
    short_description = f"Hliníkový regál na euroboxy na míru pro {vehicle_label}"
    short_description += ", na výběr více skladeb boxů." if len(box_popisy) > 1 else f", {box_popisy[0]}."
    meta_title = f"Regál na euroboxy do {vehicle['make']} {vehicle['model']}"
    meta_description = (
        f"Hliníkový regál na euroboxy do {vehicle_label}. "
        + ("Více skladeb boxů na výběr. " if len(box_popisy) > 1 else "")
        + "Stavíme na míru na milimetr podle toho, co v autě vozíte."
    )
    name = f"Regál na euroboxy – {vehicle_label}"
    return {
        "name": name, "description": description, "short_description": short_description,
        "meta_title": meta_title, "meta_description": meta_description,
    }


def main():
    conn = get_conn()
    napojeno = []
    zalozeno = []
    nove_ukoly = []
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT setting_value FROM app_settings WHERE setting_key='card_auto_link_povoleno'")
            row = cur.fetchone()
            if row and row["setting_value"] == "0":
                print("[card-auto-link] vypnuto (app_settings.card_auto_link_povoleno=0)")
                return 0

            cur.execute(
                "SELECT pa.id, pa.name, pa.data, pa.karoserie_kod, pa.profil_mm, "
                "       pa.horni_blok_varianta_id, pa.typologie_varianta_id, "
                "       ru.kod AS umisteni_kod, rt.id AS typologie_id, rt.kod AS typologie_kod, "
                "       hb.kod AS hb_kod, hb.nazev AS hb_nazev, "
                "       ru.kotveni_zakaznicky, ru.montaz_zakaznicky, "
                "       pa.mezera_police_mm "
                "FROM product_assemblies pa "
                "LEFT JOIN regal_umisteni ru ON ru.id=pa.umisteni_id "
                "LEFT JOIN regal_typologie rt ON rt.id=pa.typologie_id "
                "LEFT JOIN horni_blok_varianty hb ON hb.id=pa.horni_blok_varianta_id "
                "WHERE pa.technicky_ok=1 AND pa.shop_product_id IS NULL"
            )
            kandidati = cur.fetchall()
            if not kandidati:
                print("[card-auto-link] 0 kandidatu, konec")
                return 0

            # --- 1. pruchod: filtr (mezera-04, chybejici metadata) + vypocet SKU ---
            resolvene = []
            for r in kandidati:
                if r["hb_kod"] == "04" and r["mezera_police_mm"] is not None and r["mezera_police_mm"] < 70:
                    print(f"[card-auto-link] preskoceno (04, mezera={r['mezera_police_mm']}mm<70) "
                          f"id={r['id']} ({r['name']})")
                    continue
                karoserie_kod = _resolve_karoserie_kod(cur, r)
                if not (karoserie_kod and r["umisteni_kod"] and r["typologie_kod"] and r["profil_mm"]):
                    text = (f"Sestava id={r['id']} ({r['name']}) je technicky_ok, ale chybi "
                            f"metadata pro SKU (karoserie_kod={karoserie_kod}, "
                            f"umisteni={r['umisteni_kod']}, typologie={r['typologie_kod']}, "
                            f"profil_mm={r['profil_mm']}) - card_auto_link ji nedokaze napojit.")
                    if _zapsat_ukol_na_zed(cur, text):
                        nove_ukoly.append(text)
                    continue
                sku_prefix = f"{karoserie_kod}-{r['umisteni_kod']}-{r['typologie_kod']}-{r['profil_mm']}"
                resolvene.append((sku_prefix, karoserie_kod, r))

            # --- 2. pruchod: seskup podle SKU prefixu, napoj/zaloz kartu ---
            skupiny = {}
            for sku_prefix, karoserie_kod, r in resolvene:
                skupiny.setdefault(
                    sku_prefix,
                    {"karoserie_kod": karoserie_kod, "typologie_id": r["typologie_id"],
                     "typologie_kod": r["typologie_kod"], "rows": []},
                )["rows"].append(r)

            for sku_prefix, skupina in skupiny.items():
                cur.execute("SELECT id, active FROM shop_products WHERE sku=%s", (sku_prefix,))
                karta = cur.fetchone()

                if karta:
                    for r in skupina["rows"]:
                        razitka_zprava, novy_kod = _oznac_a_napoj(cur, r, karta["id"], sku_prefix)
                        napojeno.append({
                            "id": r["id"], "name": r["name"], "karta_id": karta["id"], "sku": sku_prefix,
                            "razitka": razitka_zprava, "kod_sestavy": novy_kod,
                        })
                        print(f"[card-auto-link] NAPOJENO id={r['id']} ({r['name']}) -> karta {karta['id']} "
                              f"({sku_prefix}) | razitka: {razitka_zprava} | kod_sestavy: {novy_kod}")
                    continue

                # Zadna karta neexistuje - ZALOZ (Robert primo, 2026-09-17,
                # pres bot3: plna automatizace, riziko prijima vedome) -
                # ALE jen kdyz je auto-zalozeni pro tuhle TYPOLOGII uz
                # jednou vizualne schvalene, nebo je tohle genuinne
                # UPLNE PRVNI auto-zalozena karta teto typologie (tu
                # zalozit vzdy - je to prave ona, co Robert bude
                # schvalovat). Bot9/bot3, 2026-09-17 (Robertovo primo
                # upresneni k tomuhle skriptu).
                pocet_auto = _pocet_auto_zalozenych_karet_typologie(cur, skupina["typologie_id"])
                if pocet_auto > 0 and not _typologie_ma_schvalenou_sablonu(cur, skupina["typologie_kod"]):
                    text = (f"Karta {sku_prefix} ČEKÁ na vizuální schválení šablony typologie "
                            f"'{skupina['typologie_kod']}' - první auto-založená karta téhle typologie "
                            f"ještě nebyla schválená (viz otevřený úkol se stejným tagem). Jakmile ho "
                            f"označíš jako hotovo, tahle i další karty stejné typologie se založí "
                            f"automaticky.")
                    if _zapsat_ukol_na_zed(cur, text):
                        nove_ukoly.append(text)
                    print(f"[card-auto-link] BLOKOVÁNO (čeká na schválení šablony typologie "
                          f"'{skupina['typologie_kod']}') - {sku_prefix}")
                    continue
                je_prvni_auto_karta_typologie = pocet_auto == 0

                vehicle = _vehicle_display(cur, skupina["karoserie_kod"])
                if not vehicle:
                    text = (f"Nova karta chybi pro {sku_prefix}, ale vozidlo se nedohledalo v car_models "
                            f"(karoserie_kod={skupina['karoserie_kod']}) - card_auto_link nemuze sestavit "
                            f"nazev/popis, potreba rucni zalozeni.")
                    if _zapsat_ukol_na_zed(cur, text):
                        nove_ukoly.append(text)
                    continue

                box_popisy = []
                for r in skupina["rows"]:
                    if r["typologie_varianta_id"]:
                        cur.execute("SELECT nazev FROM typologie_varianty WHERE id=%s", (r["typologie_varianta_id"],))
                        tv = cur.fetchone()
                        popis = _boxy_popis(tv["nazev"]) if tv else None
                        if popis and popis not in box_popisy:
                            box_popisy.append(popis)
                if not box_popisy:
                    box_popisy = ["konfigurace euroboxů podle zvolené varianty"]

                kotveni_text = skupina["rows"][0]["kotveni_zakaznicky"]
                montaz_text = skupina["rows"][0]["montaz_zakaznicky"]
                texty = _sestav_popis_karty(vehicle, box_popisy, kotveni_text, montaz_text)
                slug = _product_slug_for_name(cur, texty["name"])

                cur.execute(
                    "INSERT INTO shop_products "
                    "(category_id, zalozeno_automaticky_typologie_id, sku, name, slug, description, "
                    " short_description, meta_title, meta_description, unit, availability_text, "
                    " price_visible_default, hover_show_price, hover_show_availability, active) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,0)",
                    (CATEGORY_ID, skupina["typologie_id"], sku_prefix, texty["name"], slug,
                     texty["description"], texty["short_description"], texty["meta_title"],
                     texty["meta_description"], "ks", AVAILABILITY_TEXT, 1, 1, 0),
                )
                karta_id = cur.lastrowid

                if je_prvni_auto_karta_typologie:
                    tag = _TEMPLATE_APPROVAL_TAG.format(kod=skupina["typologie_kod"])
                    schvaleni_text = (
                        f"VIZUÁLNÍ SCHVÁLENÍ ŠABLONY: karta {karta_id} (SKU {sku_prefix}) je PRVNÍ "
                        f"automaticky založená karta typologie '{skupina['typologie_kod']}'. Zkontroluj "
                        f"vzhled/strukturu (název, popis, kategorie) v adminu a označ tenhle úkol jako "
                        f"HOTOVO, až souhlasíš - další karty STEJNÉ typologie se pak zakládají "
                        f"automaticky bez čekání na další schválení. {tag}"
                    )
                    _zapsat_ukol_na_zed(cur, schvaleni_text)
                    print(f"[card-auto-link] PRVNÍ auto-karta typologie '{skupina['typologie_kod']}' "
                          f"- zapsán úkol na zeď (čeká na vizuální schválení šablony)")

                # Master = nejvyssi "kompletnost" hb_nazev, tie-break nejnizsi id.
                master_row = max(skupina["rows"], key=lambda r: (_hb_completeness_score(r["hb_nazev"]), -r["id"]))

                master_price = None
                for r in skupina["rows"]:
                    is_master = 1 if r["id"] == master_row["id"] else 0
                    razitka_zprava, novy_kod = _oznac_a_napoj(cur, r, karta_id, sku_prefix)
                    cur.execute("UPDATE product_assemblies SET is_master=%s WHERE id=%s", (is_master, r["id"]))
                    if is_master:
                        try:
                            data = json.loads(r["data"] or "{}")
                        except (TypeError, ValueError):
                            data = {}
                        master_price = (data.get("price_summary") or {}).get("total_czk")
                    napojeno.append({
                        "id": r["id"], "name": r["name"], "karta_id": karta_id, "sku": sku_prefix,
                        "razitka": razitka_zprava, "kod_sestavy": novy_kod,
                    })

                if master_price is not None:
                    cur.execute("UPDATE shop_products SET price_czk_placeholder=%s WHERE id=%s",
                                (round(master_price), karta_id))

                zalozeno.append({
                    "karta_id": karta_id, "sku": sku_prefix, "name": texty["name"],
                    "pocet_sestav": len(skupina["rows"]), "master_id": master_row["id"],
                    "price": round(master_price) if master_price is not None else None,
                })
                print(f"[card-auto-link] ZALOZENA KARTA {karta_id} ({sku_prefix}) '{texty['name']}' - "
                      f"{len(skupina['rows'])} sestav, master={master_row['id']}, "
                      f"cena={round(master_price) if master_price is not None else 'N/A'}")
        conn.commit()
    finally:
        conn.close()

    if napojeno:
        seznam = "\n".join(
            f"- id={n['id']} `{n['sku']}` -> karta {n['karta_id']} — {n['name']}"
            f" (kód: {n['kod_sestavy'] or 'nedopočítán'})"
            for n in napojeno
        )
        zprava = f"Napojeno {len(napojeno)} sestav na karty:\n\n{seznam}"
        if zalozeno:
            zprava += "\n\nZ toho NOVĚ ZALOŽENÉ karty (active=0, čekají na render):\n\n" + "\n".join(
                f"- karta {z['karta_id']} `{z['sku']}` — {z['name']} "
                f"({z['pocet_sestav']} sestav, master={z['master_id']}, cena={z['price']} Kč)"
                for z in zalozeno
            )
        _log(zprava)
    if nove_ukoly:
        print(f"[card-auto-link] {len(nove_ukoly)} novy(ch) ukol(u) na zed (bot_ukoly, bot_id=bot5)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
