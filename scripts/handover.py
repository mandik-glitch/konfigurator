#!/opt/konfigurator/api/venv/bin/python
"""Předávací zápisník flotily botů v DB (tabulka bot_handover v hlavní DB konfigurátoru).

Účel: nová session (kdekoli, stačí api/.env) si přečte stav práce všech botů bez
čtení dlouhých logů. Jeden řádek = jedno téma jednoho bota.

  scripts/handover.py add  --bot bot5 --project konfigurator --topic "e2e suita" \
        [--status open|done|blocked|info] (--body "text" | --body-file f.md | < stdin)
  scripts/handover.py list [--project P] [--bot B] [--status S] [--since 2026-09-02]
  scripts/handover.py show ID
  scripts/handover.py dump [--project P] [--status S]   # markdown všech (výchozí: open+blocked)
  scripts/handover.py close ID                          # status -> done
"""
import argparse, os, sys, datetime
import pymysql

ENV = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "api", ".env")


def _env():
    out = {}
    for line in open(ENV, encoding="utf-8"):
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def conn():
    e = _env()
    return pymysql.connect(host=e["DB_HOST"], user=e["DB_USER"], password=e["DB_PASSWORD"],
                           database=e["DB_NAME"], port=int(e.get("DB_PORT", 3306)),
                           charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor, autocommit=True)


def cmd_add(a):
    body = a.body
    if a.body_file:
        body = open(a.body_file, encoding="utf-8").read()
    if body is None:
        body = sys.stdin.read()
    body = body.strip()
    if not body:
        sys.exit("prázdné tělo")
    with conn() as c, c.cursor() as cur:
        cur.execute("INSERT INTO bot_handover (bot, project, topic, status, body) VALUES (%s,%s,%s,%s,%s)",
                    (a.bot, a.project, a.topic, a.status, body))
        print(f"OK id={cur.lastrowid}")


def _where(a):
    w, p = [], []
    for col in ("project", "bot", "status"):
        v = getattr(a, col, None)
        if v:
            w.append(f"{col}=%s"); p.append(v)
    if getattr(a, "since", None):
        w.append("created_at>=%s"); p.append(a.since)
    return (" WHERE " + " AND ".join(w)) if w else "", p


def cmd_list(a):
    w, p = _where(a)
    with conn() as c, c.cursor() as cur:
        cur.execute("SELECT id, created_at, bot, project, status, topic, CHAR_LENGTH(body) AS n FROM bot_handover"
                    + w + " ORDER BY id", p)
        for r in cur.fetchall():
            print(f"{r['id']:>4} {r['created_at']:%Y-%m-%d %H:%M} {r['bot']:<6} {r['project']:<13} {r['status']:<7} {r['topic']}  ({r['n']} zn.)")


def cmd_show(a):
    with conn() as c, c.cursor() as cur:
        cur.execute("SELECT * FROM bot_handover WHERE id=%s", (a.id,))
        r = cur.fetchone()
        if not r:
            sys.exit("není")
        print(f"# [{r['id']}] {r['topic']}\n{r['bot']} · {r['project']} · {r['status']} · {r['created_at']:%Y-%m-%d %H:%M}\n\n{r['body']}")


def cmd_dump(a):
    if not a.status:
        a.status = None
    w, p = _where(a)
    if not a.status:
        w = (w + " AND " if w else " WHERE ") + "status IN ('open','blocked','info')"
    with conn() as c, c.cursor() as cur:
        cur.execute("SELECT * FROM bot_handover" + w + " ORDER BY project, bot, id", p)
        rows = cur.fetchall()
    print(f"# Předávka flotily — {datetime.datetime.now():%Y-%m-%d %H:%M} — {len(rows)} záznamů\n")
    for r in rows:
        print(f"## [{r['id']}] {r['project']} / {r['bot']} / {r['status']} — {r['topic']}\n_{r['created_at']:%Y-%m-%d %H:%M}_\n\n{r['body']}\n")


def cmd_close(a):
    with conn() as c, c.cursor() as cur:
        cur.execute("UPDATE bot_handover SET status='done' WHERE id=%s", (a.id,))
        print("OK" if cur.rowcount else "není")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    s = sp.add_parser("add"); s.add_argument("--bot", required=True); s.add_argument("--project", required=True)
    s.add_argument("--topic", required=True); s.add_argument("--status", default="open",
                                                             choices=["open", "done", "blocked", "info"])
    s.add_argument("--body"); s.add_argument("--body-file"); s.set_defaults(f=cmd_add)
    for name, f in (("list", cmd_list), ("dump", cmd_dump)):
        s = sp.add_parser(name)
        for o in ("--project", "--bot", "--status", "--since"):
            s.add_argument(o)
        s.set_defaults(f=f)
    s = sp.add_parser("show"); s.add_argument("id", type=int); s.set_defaults(f=cmd_show)
    s = sp.add_parser("close"); s.add_argument("id", type=int); s.set_defaults(f=cmd_close)
    a = ap.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
