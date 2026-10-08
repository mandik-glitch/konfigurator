#!/usr/bin/env python3
"""Robert pres bot3, 2026-09-30: "vandr vestavby uz muzeme michat do
stejnych kategorii s prvni vetvi - nebudou se radit jen pod vyrobni
znacku (napr. VW), ale zaroven do spravne kategorie konkretni
karoserie." 104 aktivnich Vandr (SKU 'VD-%') produktu ma dnes primarni
category_id jen na urovni znacky (269 Fiat, 270 Mercedes...) - tenhle
skript je preradi na existujici/nove listove kategorie konkretni
karoserie pod "Vestavby podle vozidla" (267).

Zdroj karoserie: shop_products.product_specs_json -> klic "Nohy" nese
presny kod nohy z geometrickeho katalogu (stejna konvence jako
custom_shapes, napr. "Noha.1.Ford.Connect.H1.1100.349") - SPOLEHLIVEJSI
nez parsovani volneho textu nazvu produktu (bot3 nalez: product_assemblies
pres shop_product_id nefunguje, 0 shod). Dva sporne pripady (Ford
Connect vs. existujici kat. 280 "Ford Transit Connect"; Ford Transit
Custom vs. existujici kat. 293 "Ford Custom") potvrzeny bot8 (karoserie
expert) jako DVE RUZNA auta, obe uz maji kategorii - zadne nove
zalozeni pro ne.

Mechanismus prirazeni: ZMENA PRIMARNI category_id (ne shop_product_
categories sekundarni) - pravidlo 52 (kategorie dedi produkty z
potomku) zajisti, ze produkt zustane viditelny i pod znackovou
kategorii automaticky. Vlastni rozhodnuti (bot3 nabidl obe moznosti,
zadny primy VD precedens k nalezeni - jediny existujici precedens
sekundarnich vazeb na tyhle leaf kategorie jsou JINE produkty,
"Regal na euroboxy" K-XXX-RL-EB-30, jejichz PRAVY domov je kategorie
247 Regaly do auta, ne znacka - strukturalne odlisna situace).

Zaloha PRED zmenou: backups/2026-09-30_vandr_karoserie_kategorie_pred_zmenou.json
(jiz zapsana, primary category_id vsech 104 + vsechny sekundarni vazby).

Pouziti:
    python3 scripts/2026-09-30_vandr_karoserie_kategorie.py            # dry-run
    python3 scripts/2026-09-30_vandr_karoserie_kategorie.py --apply    # zapis
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _env import get_conn  # noqa: E402

APPLY = "--apply" in sys.argv

# Nove listove kategorie: (klic_pro_mapovani, parent_id, nazev, slug, sort_order)
NEW_CATEGORIES = [
    ("Ducato", 269, "Vestavby pro Fiat Ducato", "vestavby-pro-fiat-ducato", 1),
    ("Sprinter", 270, "Vestavby pro Mercedes Sprinter", "vestavby-pro-mercedes-sprinter", 1),
    ("Crafter", 271, "Vestavby pro Volkswagen Crafter", "vestavby-pro-volkswagen-crafter", 1),
    ("Transporter.T6", 271, "Vestavby pro Volkswagen Transporter", "vestavby-pro-volkswagen-transporter", 2),
    ("Ford.Transit", 279, "Vestavby pro Ford Transit", "vestavby-pro-ford-transit", 2),
    ("Master", 285, "Vestavby pro Renault Master", "vestavby-pro-renault-master", 0),
    ("Trafic", 285, "Vestavby pro Renault Trafic", "vestavby-pro-renault-trafic", 1),
    ("Movano", 286, "Vestavby pro Opel Movano", "vestavby-pro-opel-movano", 0),
    ("Vivaro", 286, "Vestavby pro Opel Vivaro", "vestavby-pro-opel-vivaro", 1),
    ("Iveco", 287, "Vestavby pro Iveco Daily", "vestavby-pro-iveco-daily", 0),
    ("Peugeot.Expert", 288, "Vestavby pro Peugeot Expert", "vestavby-pro-peugeot-expert", 0),
]

# Existujici kategorie, kam se preradi bez zalozeni noveho (leg-token -> id).
EXISTING_MAP = {
    "Jumpy": 272,
    "Vito": 283,
    "Caddy": 284,
    "Ford.Connect": 280,
    "Ford.Custom": 293,
    "ProAce": 294,
}

# Produkty s obecnou/univerzalni nohou (S40.prepazka...) bez autospecifickeho
# kodu - dorazeno rucne podle jednoznacneho nazvu produktu (zadny z nich
# neni mezi spornymi pripady vyse).
MANUAL_OVERRIDE_BY_PRODUCT_ID = {
    4319: "ProAce",       # Toyota ProAce L1
    4440: "Caddy",        # VW Caddy L2
    4441: "Caddy",        # VW Caddy L2
    4592: "Transporter.T6",  # VW Transporter T6 L2
}

LEG_PATTERN = re.compile(r"Noha\.\d+\.(.+?)\.(?:FWD\.)?H\d")


def leg_token(specs_json):
    if not specs_json:
        return None
    try:
        specs = json.loads(specs_json)
    except (ValueError, TypeError):
        return None
    nohy = specs.get("Nohy", "")
    m = LEG_PATTERN.search(nohy)
    if not m:
        return None
    token = m.group(1)
    # normalizace RWD varianty na zakladni model (Sprinter.RWD -> Sprinter atd.)
    token = re.sub(r"\.RWD$", "", token)
    return token


def main():
    conn = get_conn()
    cur = conn.cursor()

    # 1) Zjisti/zaloz nove kategorie, sestav leg_token -> category_id mapu.
    token_to_catid = dict(EXISTING_MAP)
    for token, parent_id, name, slug, sort_order in NEW_CATEGORIES:
        cur.execute("SELECT id FROM content_categories WHERE slug=%s", (slug,))
        row = cur.fetchone()
        if row:
            print(f"  kategorie '{name}' uz existuje (id={row['id']}), pouzivam")
            token_to_catid[token] = row["id"]
            continue
        if not APPLY:
            print(f"  (dry-run) kategorie '{name}' (slug={slug}, parent={parent_id}) by se vytvorila")
            token_to_catid[token] = None
            continue
        cur.execute(
            "INSERT INTO content_categories (parent_id, name, slug, sort_order, is_visible, nav_label) "
            "VALUES (%s,%s,%s,%s,1,%s)",
            (parent_id, name, slug, sort_order, name),
        )
        new_id = cur.lastrowid
        token_to_catid[token] = new_id
        print(f"  kategorie '{name}' vytvorena, id={new_id}")

    # 2) Nacti vsechny aktivni VD produkty, urci cilovou kategorii.
    cur.execute(
        "SELECT id, sku, name, category_id, product_specs_json FROM shop_products "
        "WHERE sku LIKE 'VD-%%' AND active=1 AND is_archived=0 ORDER BY id"
    )
    products = cur.fetchall()
    plan = []
    unresolved = []
    for p in products:
        token = MANUAL_OVERRIDE_BY_PRODUCT_ID.get(p["id"]) or leg_token(p["product_specs_json"])
        target_id = token_to_catid.get(token) if token else None
        if target_id is None:
            unresolved.append((p["id"], p["name"], token))
            continue
        if target_id != p["category_id"]:
            plan.append((p["id"], p["sku"], p["name"], p["category_id"], target_id, token))

    print(f"\nCelkem aktivnich VD produktu: {len(products)}")
    print(f"K preřazeni (zmena category_id): {len(plan)}")
    print(f"Nevyreseno (chybi token/mapovani): {len(unresolved)}")
    for pid, name, token in unresolved:
        print(f"  NEVYRESENO: {pid} | {name} | token={token}")

    if not APPLY:
        print("\n(dry-run - nic nezapsano, spust s --apply)")
        for pid, sku, name, old_cat, new_cat, token in plan[:15]:
            print(f"  {pid} {name[:50]:<50} {old_cat} -> {new_cat} (token={token})")
        if len(plan) > 15:
            print(f"  ... a dalsich {len(plan) - 15}")
        return

    for pid, sku, name, old_cat, new_cat, token in plan:
        cur.execute("UPDATE shop_products SET category_id=%s WHERE id=%s", (new_cat, pid))
    conn.commit()
    print(f"\nPrerazeno {len(plan)} produktu, zapsano a commitnuto.")


if __name__ == "__main__":
    main()
