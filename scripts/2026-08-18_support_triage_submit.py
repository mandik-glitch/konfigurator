"""
Rucni zapis navrhu trideni prichozich e-mailu (Emaily prichozi) -
bot3, 2026-08-18. Viz sql/2026-08-18_support_email_triage.sql +
api/support.py (POST/GET .../triage-runs, PUT .../triage-proposals).

Robert: tlacitko "Tridit" v admin.html zada botovi ukol vytridit
OTEVRENE konverzace v Emaily prichozi a navrhnout, kam kazda dal
patri + co s prilohami. Zadny automaticky AI vola tady NENI - bot si
konverzace precte rucne (viz --list nize) a navrhy zapise timhle
skriptem, cimz se beh preklopi na 'ready_for_review' a Robertovi se v
adminu objevi tabulka k rozhodnuti (schvalit/zamitnout kazdy radek).

Pouziti:
    # 1. najdi cekajici beh (vytvoreny kliknutim na "Tridit" v adminu)
    python3 scripts/2026-08-18_support_triage_submit.py --pending-run

    # 2. vypis otevrene konverzace k posouzeni (customer/subject/telo
    #    poslednich zprav, prilohy)
    python3 scripts/2026-08-18_support_triage_submit.py --list

    # 3. zapis navrhy pro dany beh (JSON pole objektu)
    python3 scripts/2026-08-18_support_triage_submit.py --submit 7 --proposals '[
      {"conversation_id": 42, "destination": "crm", "reasoning": "...", "attachment_note": "..."},
      {"conversation_id": 43, "destination": "doklad", "reasoning": "...",
       "attachment_note": "faktura.pdf je faktura, cutplan.dwg neni",
       "invoice_attachment_filename": "faktura.pdf"},
      ...
    ]'
    # "destination" jedno z: crm, doklad, objednavka, podpora, spam, jine
    # "invoice_attachment_filename" (bot11, 2026-08-19) - jen relevantni
    # pro destination='doklad', pokud ma konverzace vic priloh a jde
    # poznat, KTERA je samotna faktura (viz --list nize, ted uz vypisuje
    # prilohy kazde zpravy) - NENI automaticke rozhodnuti, jen navrh
    # k predvyplneni, admin si v adminu muze pri schvaleni vybrat jinou
    # prilohu nebo zadnou (vizualne pozna fakturu spolehliveji nez bot).
"""
import argparse
import json
import os
import sys

for line in open(os.path.join(os.path.dirname(__file__), "..", "api", ".env")):
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    k, v = line.split("=", 1)
    os.environ.setdefault(k, v)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api"))
import app  # noqa: E402

DESTINATION_LABELS = {
    "crm": "Poptávka (přesunout do CRM)",
    "doklad": "Přijatý doklad (faktura/účtenka)",
    "objednavka": "Objednávka (propojit)",
    "podpora": "Ponechat v Emaily příchozí",
    "spam": "Spam/nesouvisející (navrhuji smazat)",
    "jine": "Nejasné - potřeba ruční posouzení",
}


def cmd_pending_run(cur):
    cur.execute(
        "SELECT id, status, requested_at FROM support_email_triage_runs "
        "WHERE status='pending' ORDER BY id DESC LIMIT 1"
    )
    row = cur.fetchone()
    if not row:
        print("Žádný čekající běh třídění (nikdo zatím neklikl na 'Třídit', nebo jsou všechny zpracované).")
        return
    print(f"Čekající běh id={row['id']} (požádáno {row['requested_at']})")


def cmd_list(cur):
    cur.execute(
        "SELECT id, customer_name, customer_email, email_subject, source, last_message_at "
        "FROM shop_support_conversations WHERE status='open' AND archived=0 "
        "ORDER BY last_message_at DESC"
    )
    convs = cur.fetchall()
    if not convs:
        print("Žádné otevřené konverzace.")
        return
    for c in convs:
        print(f"\n=== id={c['id']} | {c['customer_name'] or c['customer_email']} | {c['source']} | {c['last_message_at']} ===")
        print(f"Předmět: {c['email_subject'] or '(bez předmětu)'}")
        cur.execute(
            "SELECT sender_type, sender_name, body FROM shop_support_messages "
            "WHERE conversation_id=%s ORDER BY id DESC LIMIT 3",
            (c["id"],),
        )
        for m in cur.fetchall():
            body_preview = (m["body"] or "")[:300].replace("\n", " ")
            print(f"  [{m['sender_type']}/{m['sender_name']}] {body_preview}")
        # (bot11, 2026-08-19) - prilohy VSECH prichozich support e-mailu
        # se ted ukladaji PRI SYNCHRONIZACI do shop_support_message_
        # attachments (viz api/support_email_sync.py), takze uz jdou tady
        # vypsat - pri destination='doklad' a vic nez jednou prilohou
        # zapis do --submit i "invoice_attachment_filename" s presnym
        # nazvem souboru, ktery je SKUTECNE faktura (ne treba rezny plan).
        cur.execute(
            "SELECT a.filename, a.content_type FROM shop_support_message_attachments a "
            "JOIN shop_support_messages m ON m.id = a.message_id "
            "WHERE m.conversation_id=%s ORDER BY m.created_at, a.id",
            (c["id"],),
        )
        atts = cur.fetchall()
        if atts:
            print("  Přílohy: " + ", ".join(f"{a['filename']} ({a['content_type'] or '?'})" for a in atts))


def cmd_submit(cur, conn, run_id, proposals):
    cur.execute("SELECT status FROM support_email_triage_runs WHERE id=%s", (run_id,))
    run = cur.fetchone()
    if not run:
        print(f"CHYBA: běh id={run_id} neexistuje.")
        sys.exit(1)
    for p in proposals:
        dest = p.get("destination")
        if dest not in DESTINATION_LABELS:
            print(f"CHYBA: neplatná destinace '{dest}' u konverzace {p.get('conversation_id')}.")
            sys.exit(1)
        cur.execute(
            "INSERT INTO support_email_triage_proposals "
            "(run_id, conversation_id, proposed_destination, destination_label, reasoning, attachment_note, "
            " invoice_attachment_filename) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s)",
            (run_id, p["conversation_id"], dest, DESTINATION_LABELS[dest],
             p.get("reasoning"), p.get("attachment_note"), p.get("invoice_attachment_filename")),
        )
    cur.execute(
        "UPDATE support_email_triage_runs SET status='ready_for_review' WHERE id=%s",
        (run_id,),
    )
    conn.commit()
    print(f"OK - zapsáno {len(proposals)} návrhů pro běh id={run_id}, stav -> ready_for_review.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pending-run", action="store_true")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--submit", type=int, metavar="RUN_ID")
    ap.add_argument("--proposals", type=str, help="JSON pole objektu {conversation_id, destination, reasoning, attachment_note, invoice_attachment_filename?}")
    args = ap.parse_args()

    conn = app.get_conn()
    try:
        with conn.cursor() as cur:
            if args.pending_run:
                cmd_pending_run(cur)
            elif args.list:
                cmd_list(cur)
            elif args.submit:
                if not args.proposals:
                    print("CHYBA: --submit vyžaduje --proposals '<json>'.")
                    sys.exit(1)
                cmd_submit(cur, conn, args.submit, json.loads(args.proposals))
            else:
                ap.print_help()
    finally:
        conn.close()


if __name__ == "__main__":
    main()
