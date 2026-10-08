import re, sys, pymysql

env = {}
for line in open("/opt/konfigurator/api/.env"):
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    k, v = line.split("=", 1)
    env[k] = v

sql_path = sys.argv[1]
raw = open(sql_path, encoding="utf-8").read()
lines = [l for l in raw.splitlines() if not l.strip().startswith("--")]
stmts = [s.strip() for s in "\n".join(lines).split(";") if s.strip()]

# POJISTKA (bot14, 2026-08-19): remeslo_* tabulky ziji od presunu Remesla
# ve VLASTNI DB "Remeslnik" (viz REMESLO_KONCEPT.md "Infrastruktura -
# presun na vlastni DB"). Tenhle skript miri napevno na HLAVNI DB (DB_*),
# takze aplikovat pres nej remeslo_* migraci by tise vytvorilo/zmenilo
# tabulku v NEPOUZIVANE kopii - zadna chyba, jen by se to nikde
# neprojevilo. Presne tahle trida tiche chyby uz dnes zasahla 8 skriptu
# ve scripts/ a api/remeslo_voice_worker.py. Radsi hlasite selzeme.
#
# Hleda se remeslo_ jako ODKAZ NA TABULKU (za CREATE TABLE/ALTER TABLE/
# INSERT INTO/FROM/JOIN/UPDATE/DELETE FROM), NE jako libovolny vyskyt
# retezce - jinak by pojistka chybne zablokovala legitimni migraci HLAVNI
# DB, ktera slovo "remeslo_" obsahuje jen jako hodnotu (napr.
# sql/2026-08-19_gallery_items_remeslo_finance_transaction.sql pridava
# 'remeslo_finance_transaction' do ENUM sloupce content_gallery_items,
# coz je tabulka hlavni DB a projit MUSI). Overeno na obou pripadech.
_body_wo_comments = "\n".join(lines)
_table_refs = re.findall(
    r"(?:CREATE\s+TABLE(?:\s+IF\s+NOT\s+EXISTS)?|ALTER\s+TABLE|INSERT\s+(?:IGNORE\s+)?INTO|"
    r"DELETE\s+FROM|UPDATE|FROM|JOIN)\s+`?(remeslo_[a-z_]+)`?",
    _body_wo_comments, re.I)
if _table_refs:
    sys.exit(
        f"ODMITNUTO: {sql_path} pracuje s remeslo_* tabulkami ({', '.join(sorted(set(_table_refs)))}),\n"
        "ktere ziji ve vlastni DB 'Remeslnik', ne v hlavni DB. Pouzij misto toho:\n"
        f"    python api/db_migrate_remeslo.py {sql_path}"
    )

conn = pymysql.connect(
    host=env["DB_HOST"], port=int(env["DB_PORT"]), user=env["DB_USER"],
    password=env["DB_PASSWORD"], database=env["DB_NAME"],
)
try:
    with conn.cursor() as cur:
        for s in stmts:
            print("Executing:", s[:100])
            cur.execute(s)
    conn.commit()
    print("OK - committed")
finally:
    conn.close()
