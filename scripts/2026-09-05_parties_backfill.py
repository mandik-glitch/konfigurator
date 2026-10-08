#!/usr/bin/env python3
"""Party model - jednorazovy backfill (bot18, 2026-09-05, Robert pres
bot3). Zaklada `parties` radky pro existujici identity a propojuje je
VYHRADNE po tvrde, uz existujici FK - zadne fuzzy e-mail/jmeno+telefon
slucovani napric ruznymi ucty (Robertovo vyslovne rozhodnuti, konkretni
priklad: jeho vlastni 2 ucty admin/remeslnik zustavaji ZAMERNE
oddelene).

Poradi (musi byt presne tohle, kazdy dalsi krok stavi na FK z
predchoziho):
  1. app_users (mimo @test.local testovaci ucty) -> nova party kazdemu
     radku, zadne slucovani.
  2. shop_customers -> party_id PREVEZME od sveho app_users (pres
     uz existujici user_id FK), zaroven obohati party o ico/dic/
     customer_type (party_type), co app_users nema.
  3. crm_leads S vyplnenym customer_id -> party_id PREVEZME od sveho
     shop_customers. crm_leads BEZ customer_id zustavaji party_id=NULL
     (zadna nova party, zadne dohadovani - schvaleno bot3 2026-09-05).
  4. shop_orders S vyplnenym user_id -> party_id PREVEZME od sveho
     app_users. Zive overeno pred psanim (2026-09-05): 0/39 objednavek
     ma user_id vyplneny (vsechny historicke/hostovske) - tenhle krok
     tedy dnes NIC nezmeni, jen je pripraveny pro budouci objednavky.

Pouziti:
  scripts/2026-09-05_parties_backfill.py            (dry-run)
  scripts/2026-09-05_parties_backfill.py --apply    (skutecny zapis)
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "api"))
import pymysql


def get_conn():
    return pymysql.connect(
        host=os.environ["DB_HOST"], user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"], database=os.environ["DB_NAME"],
        cursorclass=pymysql.cursors.DictCursor,
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    conn = get_conn()
    cur = conn.cursor()

    # --- 1. app_users -> nova party kazdemu (mimo testovaci ucty) ---
    cur.execute("SELECT id, email, name, party_id FROM app_users WHERE party_id IS NULL ORDER BY id")
    users = cur.fetchall()
    users_to_link = [u for u in users if not (u["email"] or "").endswith("@test.local")]
    users_skipped_test = [u for u in users if u not in users_to_link]

    print(f"app_users bez party_id: {len(users)} (z toho {len(users_skipped_test)} testovacich, "
          f"preskoceno - {[u['email'] for u in users_skipped_test]})")
    print(f"  -> {len(users_to_link)} dostane novou party")

    # --- 2. shop_customers -> party_id od sveho app_users (hard FK) ---
    cur.execute(
        "SELECT c.id, c.user_id, c.customer_type, c.ico, c.dic, c.phone, c.full_name, c.party_id, "
        "       u.party_id AS user_party_id "
        "FROM shop_customers c LEFT JOIN app_users u ON u.id = c.user_id"
    )
    customers = cur.fetchall()
    print(f"\nshop_customers celkem: {len(customers)}")
    for c in customers:
        print(f"  id={c['id']} user_id={c['user_id']} customer_type={c['customer_type']} "
              f"party_id={c['party_id']} (bude prevzato od app_users.party_id az bude zalozena)")

    # --- 3. crm_leads ---
    cur.execute("SELECT id, customer_id, party_id FROM crm_leads ORDER BY id")
    leads = cur.fetchall()
    leads_with_customer = [l for l in leads if l["customer_id"] is not None]
    leads_without_customer = [l for l in leads if l["customer_id"] is None]
    print(f"\ncrm_leads celkem: {len(leads)} - {len(leads_with_customer)} s customer_id (dostanou party_id), "
          f"{len(leads_without_customer)} bez customer_id (ZUSTANOU nenapojene, zadna nova party)")

    # --- 4. shop_orders ---
    cur.execute("SELECT COUNT(*) AS n FROM shop_orders WHERE user_id IS NOT NULL AND party_id IS NULL")
    orders_to_link = cur.fetchone()["n"]
    cur.execute("SELECT COUNT(*) AS n FROM shop_orders")
    orders_total = cur.fetchone()["n"]
    print(f"\nshop_orders celkem: {orders_total}, s user_id (dostanou party_id): {orders_to_link}")

    if not args.apply:
        print("\nDRY-RUN - zadny zapis.")
        conn.close()
        return

    # Zaloha pred zapisem (jen dotcene sloupce, tabulky jsou male).
    backup = {
        "app_users": [{"id": u["id"], "party_id": u["party_id"]} for u in users],
        "shop_customers": [{"id": c["id"], "party_id": c["party_id"]} for c in customers],
        "crm_leads": [{"id": l["id"], "party_id": l["party_id"]} for l in leads],
    }
    backup_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "backups", "2026-09-05_parties_backfill_pred_zapisem.json",
    )
    with open(backup_path, "w", encoding="utf-8") as f:
        json.dump(backup, f, ensure_ascii=False, indent=2, default=str)
    print(f"\nzaloha ulozena: {backup_path}")

    # 1. app_users
    for u in users_to_link:
        cur.execute(
            "INSERT INTO parties (party_type, full_name, primary_email) VALUES ('osoba', %s, %s)",
            (u["name"], u["email"]),
        )
        party_id = cur.lastrowid
        cur.execute("UPDATE app_users SET party_id=%s WHERE id=%s", (party_id, u["id"]))
    print(f"1. zapsano {len(users_to_link)} novych parties + app_users.party_id")

    # 2. shop_customers (cte cerstve app_users.party_id, ktere jsme prave zapsali)
    cur.execute(
        "UPDATE shop_customers c JOIN app_users u ON u.id = c.user_id "
        "SET c.party_id = u.party_id "
        "WHERE c.party_id IS NULL AND u.party_id IS NOT NULL"
    )
    n_customers = cur.rowcount
    # Obohaceni party o udaje, ktere app_users nema (ico/dic/typ/telefon) -
    # jen tam, kde party dane pole jeste nema (nikdy neprepisuje).
    cur.execute(
        "UPDATE parties p JOIN shop_customers c ON c.party_id = p.id "
        "SET p.party_type = c.customer_type, "
        "    p.ico = COALESCE(p.ico, c.ico), "
        "    p.dic = COALESCE(p.dic, c.dic), "
        "    p.primary_phone = COALESCE(p.primary_phone, c.phone) "
        "WHERE c.customer_type IS NOT NULL"
    )
    print(f"2. propojeno {n_customers} shop_customers.party_id, obohaceno {cur.rowcount} parties o ico/dic/typ")

    # 3. crm_leads - jen tam, kde uz existuje tvrda FK na shop_customers
    cur.execute(
        "UPDATE crm_leads l JOIN shop_customers c ON c.id = l.customer_id "
        "SET l.party_id = c.party_id "
        "WHERE l.party_id IS NULL AND c.party_id IS NOT NULL"
    )
    print(f"3. propojeno {cur.rowcount} crm_leads.party_id (jen s existujicim customer_id)")

    # 4. shop_orders - jen tam, kde uz existuje tvrda FK na app_users
    cur.execute(
        "UPDATE shop_orders o JOIN app_users u ON u.id = o.user_id "
        "SET o.party_id = u.party_id "
        "WHERE o.party_id IS NULL AND u.party_id IS NOT NULL"
    )
    print(f"4. propojeno {cur.rowcount} shop_orders.party_id (jen s existujicim user_id)")

    conn.commit()
    print("\ncommit proveden.")
    conn.close()

    # Overeni CERSTVYM SELECTEM z NOVEHO spojeni.
    conn2 = get_conn()
    cur2 = conn2.cursor()
    errors = []

    cur2.execute(
        "SELECT COUNT(*) AS n FROM app_users WHERE party_id IS NULL AND email NOT LIKE '%@test.local'"
    )
    n = cur2.fetchone()["n"]
    if n:
        errors.append(f"{n} netestovacich app_users bez party_id")

    cur2.execute(
        "SELECT COUNT(*) AS n FROM shop_customers c JOIN app_users u ON u.id=c.user_id "
        "WHERE u.party_id IS NOT NULL AND (c.party_id IS NULL OR c.party_id != u.party_id)"
    )
    n = cur2.fetchone()["n"]
    if n:
        errors.append(f"{n} shop_customers s nesedicim/chybejicim party_id vuci svemu app_users")

    cur2.execute(
        "SELECT COUNT(*) AS n FROM crm_leads l JOIN shop_customers c ON c.id=l.customer_id "
        "WHERE c.party_id IS NOT NULL AND (l.party_id IS NULL OR l.party_id != c.party_id)"
    )
    n = cur2.fetchone()["n"]
    if n:
        errors.append(f"{n} crm_leads s nesedicim/chybejicim party_id vuci svemu shop_customers")

    cur2.execute("SELECT COUNT(*) AS n FROM crm_leads WHERE customer_id IS NULL AND party_id IS NOT NULL")
    n = cur2.fetchone()["n"]
    if n:
        errors.append(f"{n} crm_leads BEZ customer_id ale S party_id (nemelo by vzniknout - zadne nove party)")

    print(f"\nOVERENI (cerstve spojeni): {len(errors)} nesrovnalosti.")
    for e in errors:
        print("  NESEDI:", e)
    if errors:
        sys.exit(2)
    conn2.close()


if __name__ == "__main__":
    main()
