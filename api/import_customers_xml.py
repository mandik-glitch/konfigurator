"""
Jednorazovy import historickych zakazniku z customers.xml (export z
puvodniho e-shopu) - bot3, 2026-07-25.

Kontext: Robert poskytl customers.xml (612 zaznamu). 404 z nich nema
vyplnene FULL_NAME (jen e-mail) a 354 z techto navic nema ani adresu -
podle vzoru registracnich datumu (shluky v prosinci 2021 a jaru 2022,
same zahranicni gmail/yahoo adresy, 0 objednavek) jde nejspis o
spam/falesne registrace z puvodniho systemu. Robert rozhodl (2026-07-25):
importovat jen zaznamy s vyplnenym jmenem I adresou (208 z 612), vytvorit
jim rovnou prihlasovaci ucty (nahodne heslo, zadny automaticky e-mail -
zakaznik si nastavi vlastni pres "Zapomenute heslo"), a skupine
"Autosalon" (v puvodnich datech bez uvedeneho %) nastavit slevu 5 %.

Vyzaduje uz nasazenou migraci sql/2026-07-25_customers_import_prep.sql
(prejmenovani/pridani skupin, nove sloupce note/legacy_guid/
legacy_order_count/legacy_order_value_czk na shop_customers).

Spusteni (na serveru, ve venv s pymysql):
    python3 import_customers_xml.py customers.xml --dry-run   # jen report, nic nezapisuje
    python3 import_customers_xml.py customers.xml             # skutecny import

Idempotence: kazdy import radek nese legacy_guid (CUSTOMER/GUID z XML,
UNIQUE sloupec) - pri opakovanem spusteni uz existujici legacy_guid
preskočí (nevytvori duplicitu).
"""
import os
import sys
import secrets
import xml.etree.ElementTree as ET

import pymysql
from werkzeug.security import generate_password_hash

# Bezpecnost (bot11, 2026-08-18, audit AUDIT_SYSTEM_2026-08-18.md nalez
# 1.6): drivejsi hardcoded DB credentials primo v kodu (trvale v git
# historii). Nacteno z api/.env stejnym zpusobem jako sestersky
# import_logiman_gallery.py (zadny python-dotenv, .env muze obsahovat
# hodnoty s mezerami - parsuje se rucne, jen prvni "=" je oddelovac).
_env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
if os.path.exists(_env_path):
    with open(_env_path, encoding="utf-8") as _f:
        for _line in _f:
            _line = _line.strip()
            if not _line or _line.startswith("#") or "=" not in _line:
                continue
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())


def _require_env(name):
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Chybí povinná env proměnná {name} (viz api/.env).")
    return value


DB_HOST = _require_env("DB_HOST")
DB_USER = _require_env("DB_USER")
DB_PASSWORD = _require_env("DB_PASSWORD")
DB_NAME = _require_env("DB_NAME")


def text(el, tag, default=""):
    if el is None:
        return default
    e = el.find(tag)
    return (e.text or "").strip() if e is not None and e.text else default


def parse_customers(xml_path):
    tree = ET.parse(xml_path)
    root = tree.getroot()
    out = []
    for c in root.findall("CUSTOMER"):
        ba = c.find("BILLING_ADDRESS")
        full_name = text(ba, "FULL_NAME")
        street = text(ba, "STREET")
        if not full_name or not street:
            continue  # Robertovo rozhodnuti: bez jmena+adresy neimportovat

        accounts = c.find("ACCOUNTS")
        acc_list = accounts.findall("ACCOUNT") if accounts is not None else []
        if not acc_list:
            continue
        primary_account = acc_list[0]  # 611/612 ma presne 1 ucet, u vyjimky bereme prvni

        shipping = c.find("SHIPPING_ADDRESSES")
        ship_list = shipping.findall("SHIPPING_ADDRESS") if shipping is not None else []
        delivery_address = None
        if ship_list:
            sa = ship_list[0]
            parts = [
                " ".join(p for p in [text(sa, "STREET"), text(sa, "HOUSE_NUMBER")] if p),
                text(sa, "CITY"),
                text(sa, "ZIP"),
                text(sa, "COUNTRY"),
            ]
            delivery_address = ", ".join(p for p in parts if p) or None

        billing_parts = [
            " ".join(p for p in [street, text(ba, "HOUSE_NUMBER")] if p),
            text(ba, "CITY"),
            text(ba, "ZIP"),
            text(ba, "COUNTRY"),
        ]
        billing_address = ", ".join(p for p in billing_parts if p) or None

        orders = c.find("ORDERS")

        out.append({
            "legacy_guid": text(c, "GUID") or None,
            "customer_group": text(c, "CUSTOMER_GROUP") or None,
            "remark": text(c, "REMARK") or None,
            "full_name": full_name,
            "company_name": text(ba, "COMPANY") or None,
            "ico": text(ba, "COMPANY_ID") or None,
            "dic": text(ba, "VAT_ID") or None,
            "billing_address": billing_address,
            "delivery_address": delivery_address,
            "email": text(primary_account, "EMAIL").strip().lower(),
            "phone": text(primary_account, "PHONE") or None,
            "legacy_order_count": int(text(orders, "TOTAL_ORDER_COUNT") or 0) if orders is not None else 0,
            "legacy_order_value_czk": float(text(orders, "TOTAL_ORDER_VALUE") or 0) if orders is not None else 0.0,
        })
    return out


def main():
    if len(sys.argv) < 2:
        print("Pouziti: python3 import_customers_xml.py customers.xml [--dry-run]")
        sys.exit(1)
    xml_path = sys.argv[1]
    dry_run = "--dry-run" in sys.argv[2:]

    records = parse_customers(xml_path)
    print(f"K importu (jmeno+adresa vyplnena): {len(records)} zaznamu")

    conn = pymysql.connect(
        host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=DB_NAME,
        charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor,
    )

    created_accounts = 0
    created_profiles = 0
    skipped_existing_email = []
    skipped_existing_guid = []
    skipped_no_email = 0
    group_cache = {}

    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name FROM shop_customer_groups")
            for row in cur.fetchall():
                group_cache[row["name"]] = row["id"]
        print("Dostupne skupiny v DB:", group_cache)

        for rec in records:
            if not rec["email"]:
                skipped_no_email += 1
                continue

            with conn.cursor() as cur:
                cur.execute("SELECT id FROM app_users WHERE LOWER(email)=%s", (rec["email"],))
                existing_user = cur.fetchone()
                cur.execute("SELECT id FROM shop_customers WHERE legacy_guid=%s", (rec["legacy_guid"],))
                existing_profile = cur.fetchone()

            if existing_profile:
                skipped_existing_guid.append(rec["email"])
                continue
            if existing_user:
                # ucet uz existuje (typicky Robertuv vlastni admin ucet) -
                # nevytvarime duplicitni ucet ani mu nevnucujeme profil
                # zakaznika/slevu - jen zaznamename a preskocime.
                skipped_existing_email.append(rec["email"])
                continue

            group_name = rec["customer_group"]
            group_id = group_cache.get(group_name)

            if dry_run:
                created_accounts += 1
                created_profiles += 1
                continue

            with conn.cursor() as cur:
                random_password = secrets.token_urlsafe(24)
                pw_hash = generate_password_hash(random_password)
                customer_type = "firma" if rec["company_name"] else "osoba"
                # Party model (bot18, 2026-09-05) - stejny jednoduchy
                # insert jako app.py::create_party(), tady jen inline
                # (skript nema Flask kontext, netahat kvuli tomu cely
                # app.py). Zadne fuzzy dohadovani - kazdy novy import
                # radek dostane VLASTNI party, zadne slucovani napric
                # existujicimi ucty.
                cur.execute(
                    "INSERT INTO parties (party_type, full_name, primary_email, primary_phone, ico, dic) "
                    "VALUES (%s,%s,%s,%s,%s,%s)",
                    (customer_type, rec["full_name"], rec["email"], rec["phone"], rec["ico"], rec["dic"]),
                )
                party_id = cur.lastrowid
                cur.execute(
                    "INSERT INTO app_users (email, password_hash, name, role, active, party_id) "
                    "VALUES (%s,%s,%s,'user',1,%s)",
                    (rec["email"], pw_hash, rec["full_name"], party_id),
                )
                user_id = cur.lastrowid
                created_accounts += 1

                cur.execute(
                    "INSERT INTO shop_customers "
                    "(user_id, party_id, customer_type, full_name, company_name, ico, dic, email, phone, "
                    " billing_address, delivery_address, group_id, note, legacy_guid, "
                    " legacy_order_count, legacy_order_value_czk) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (user_id, party_id, customer_type, rec["full_name"], rec["company_name"],
                     rec["ico"], rec["dic"], rec["email"], rec["phone"],
                     rec["billing_address"], rec["delivery_address"], group_id,
                     rec["remark"], rec["legacy_guid"],
                     rec["legacy_order_count"], rec["legacy_order_value_czk"]),
                )
                created_profiles += 1

        if not dry_run:
            conn.commit()
        else:
            conn.rollback()
    finally:
        conn.close()

    print()
    print(f"{'[DRY RUN] ' if dry_run else ''}Vytvoreno uctu: {created_accounts}, profilu: {created_profiles}")
    print(f"Preskoceno (email uz existuje v app_users): {len(skipped_existing_email)} -> {skipped_existing_email}")
    print(f"Preskoceno (legacy_guid jiz importovan drive): {len(skipped_existing_guid)}")
    print(f"Preskoceno (chybi e-mail): {skipped_no_email}")


if __name__ == "__main__":
    main()
