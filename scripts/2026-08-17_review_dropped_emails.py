"""
Rucni review e-mailu, ktere sync (support_email_sync.py) vyhodnotil
jako "jine" a nesouvisejici s eshopem (viz email_review_queue,
sql/2026-08-17_email_review_queue.sql) - bot8, 2026-08-17.

Robert (pres bot3): "nepotrebuju to delat zive, staci kdyz to udelame
obcas v ramci teto komunikace" - zadna automaticka LLM klasifikace na
pozadi, misto toho tenhle skript kdykoliv vypise nove polozky k
rucnimu posouzeni (spam/newsletter necham byt, skutecnou poptavku/
doklad rucne dopisi do prislusne tabulky a radek oznacim precteno).

Pouziti:
    python3 scripts/2026-08-17_review_dropped_emails.py            # vypis nove polozky
    python3 scripts/2026-08-17_review_dropped_emails.py --all      # vypis vsechny (i uz precteno)
    python3 scripts/2026-08-17_review_dropped_emails.py --mark 12,13,14   # oznaci precteno (bez presunu)
"""
import os
import sys

for line in open(os.path.join(os.path.dirname(__file__), "..", "api", ".env")):
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    k, v = line.split("=", 1)
    os.environ[k] = v

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api"))
import app  # noqa: E402


def main():
    args = sys.argv[1:]
    conn = app.get_conn()
    try:
        with conn.cursor() as cur:
            if "--mark" in args:
                ids = args[args.index("--mark") + 1].split(",")
                ids = [int(i) for i in ids if i.strip()]
                cur.executemany(
                    "UPDATE email_review_queue SET review_status='precteno', reviewed_at=NOW() WHERE id=%s",
                    [(i,) for i in ids],
                )
                conn.commit()
                print(f"Oznaceno jako precteno: {len(ids)} polozek.")
                return
            if "--all" in args:
                cur.execute("SELECT * FROM email_review_queue ORDER BY received_at DESC LIMIT 200")
            else:
                cur.execute(
                    "SELECT * FROM email_review_queue WHERE review_status='nove' "
                    "ORDER BY received_at DESC LIMIT 200"
                )
            rows = cur.fetchall()
    finally:
        conn.close()

    if not rows:
        print("Nic k review - fronta je prazdna.")
        return

    print(f"{len(rows)} polozek k rucnimu posouzeni:\n")
    for r in rows:
        print(f"[{r['id']}] {r['received_at']}  {r['source_name'] or ''} <{r['source_email']}>")
        print(f"    Predmet: {r['subject'] or '(bez predmetu)'}")
        preview = (r["body_text"] or "").strip().replace("\n", " ")[:200]
        print(f"    Text:    {preview}")
        print()
    print("Oznaceni jako precteno (nic z toho neni skutecna poptavka/doklad):")
    print(f"    python3 {sys.argv[0]} --mark {','.join(str(r['id']) for r in rows)}")


if __name__ == "__main__":
    main()
