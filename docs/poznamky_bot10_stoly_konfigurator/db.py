"""Jen-cteni DB spojeni (vzor scripts/handover.py conn(), ale bez importu z /opt - zadne .pyc do repa)."""
import sys
sys.dont_write_bytecode = True
import pymysql

ENV = "/opt/konfigurator/api/.env"

def _env():
    out = {}
    for line in open(ENV, encoding="utf-8"):
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip().strip('"').strip("'")
    return out

def ro():
    e = _env()
    c = pymysql.connect(host=e["DB_HOST"], user=e["DB_USER"], password=e["DB_PASSWORD"],
                        database=e["DB_NAME"], port=int(e.get("DB_PORT", 3306)),
                        charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor, autocommit=True)
    cur = c.cursor()
    cur.execute("SET SESSION TRANSACTION READ ONLY")
    return c, cur
