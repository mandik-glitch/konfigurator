"""Testy scripts/nasazeni.py po incidentu 2026-10-02: okno nasazeni, blokace opakovani po varovani, detekce padu arbitra v journalu.
Bez DB a bez systemd (DB je podvrzena). Spusteni: api/venv/bin/python3 scripts/2026-10-02_gunicorn_incident_testy/test_nasazeni_okno.py"""
import datetime
import importlib.util
import os
import sys
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, "scripts"))
spec = importlib.util.spec_from_file_location("nasazeni", os.path.join(REPO, "scripts", "nasazeni.py"))
N = importlib.util.module_from_spec(spec); spec.loader.exec_module(N)
TZ = ZoneInfo("Europe/Prague")
bad = 0
def ok(c, t):
    global bad
    bad += (not c); print("[%s] %s" % ("OK   " if c else "CHYBA", t))
def ts(y, mo, d, h, mi, s=0): return datetime.datetime(y, mo, d, h, mi, s, tzinfo=TZ).timestamp()

# --- okno_od: patri cas do okna 00:00 nebo 12:30 (nocni termin od 2026-10-04 v pulnoci; drive 03:30)
f = lambda *a: N.okno_od(ts(*a)).strftime("%d.%m. %H:%M")
ok(f(2026, 10, 2, 17, 37) == "02.10. 12:30", "17:37 patří do okna 12:30 téhož dne")
ok(f(2026, 10, 2, 12, 30) == "02.10. 12:30" and f(2026, 10, 2, 12, 29, 59) == "02.10. 00:00", "hranice 12:30:00 už je nové okno, 12:29:59 ještě staré")
ok(f(2026, 10, 2, 0, 1) == "02.10. 00:00" and f(2026, 10, 1, 23, 59, 59) == "01.10. 12:30", "00:01 patří do půlnočního okna téhož dne, 23:59:59 ještě do okna 12:30 předchozího dne")
ok(f(2026, 10, 2, 0, 0) == "02.10. 00:00" and f(2026, 10, 2, 3, 30) == "02.10. 00:00", "hranice 00:00 (v 03:30 už se nic nenasazuje, je to stále půlnoční okno)")

# --- varovani_v_okne s podvrzenou DB
class Cur:
    def __init__(self, row): self.row = row; self.sql = None
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def execute(self, sql, p=None): self.sql = sql
    def fetchone(self): return self.row
class Conn:
    def __init__(self, row): self.row = row
    def cursor(self): return Cur(self.row)
    def close(self): pass
def with_row(row, now):
    N.db_conn = lambda: Conn(row)
    N.BEZ_DB = False
    return N.varovani_v_okne(now)
now = ts(2026, 10, 2, 17, 50)
r = with_row({"id": 10, "status": "varovani", "t": ts(2026, 10, 2, 17, 37, 28), "reason": "x"}, now)
ok(r and r["id"] == 10 and r["kdy"] == "17:37", "varování #10 v 17:37 blokuje další automat v 17:50 (stejné okno)")
ok(with_row({"id": 10, "status": "varovani", "t": ts(2026, 10, 2, 17, 37, 28), "reason": ""}, ts(2026, 10, 3, 0, 0, 1)) is None, "o půlnočním termínu příštího dne se znovu nasazuje (nové okno)")
ok(with_row({"id": 9, "status": "ok", "t": ts(2026, 10, 2, 17, 10), "reason": ""}, now) is None, "po úspěšném běhu nic neblokuje")
ok(with_row({"id": 9, "status": "selhalo", "t": ts(2026, 10, 2, 17, 10), "reason": ""}, now) is None, "po selhání se chování nemění (blokuje jen varování)")
ok(with_row(None, now) is None, "prázdná historie nic neblokuje")
ok(with_row((10, "varovani", ts(2026, 10, 2, 17, 37), "r"), now) is not None, "funguje i s běžným (ne slovníkovým) kurzorem")
N.db_conn = lambda: (_ for _ in ()).throw(RuntimeError("db dole"))
ok(N.varovani_v_okne(now) is None, "chyba DB nasazení neblokuje")
N.BEZ_DB = True
ok(N.varovani_v_okne(now) is None, "NASAZENI_BEZ_DB=1 (zkušební režim) nic neblokuje")

# --- detekce padu arbitra: skutecny vypis z journalu incidentu
INC = """[2026-10-02 17:37:37 +0200] [1727851] [ERROR] Worker (pid:4005972) was sent SIGTERM!
--- Logging error ---
[2026-10-02 17:37:37 +0200] [1727851] [ERROR] Unhandled exception in main loop
RuntimeError: reentrant call inside <_io.BufferedWriter name='<stderr>'>
[2026-10-02 17:37:51 +0200] [4040001] [INFO] Booting worker with pid: 4040002"""
class FakeSl:
    def journal(self, od, do=None): return INC if do is None else ""
j = N.zkontroluj_journal(FakeSl(), 0)
ok(len(j["arbiter_pad"]) == 2 and "Unhandled exception in main loop" in j["arbiter_pad"][0], "journal incidentu 17:37 je rozpoznán jako pád arbitra")
class FakeSl2(FakeSl):
    def journal(self, od, do=None): return "[INFO] Handling signal: hup\n[INFO] Worker exiting (pid: 1)" if do is None else ""
ok(N.zkontroluj_journal(FakeSl2(), 0)["arbiter_pad"] == [], "normální HUP pád arbitra nehlásí")
print("\n==> %s" % ("VŠE OK" if not bad else "%d CHYB" % bad))
sys.exit(1 if bad else 0)
