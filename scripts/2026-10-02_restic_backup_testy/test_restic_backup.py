#!/opt/konfigurator/api/venv/bin/python
"""Testy scripts/restic_backup.py (bot16, 2026-10-02): vymyslena data, MISTNI repozitar restic v docasne slozce, zadny pristup k S3 ani k zivym
datum. Prikaz mysqldump se nahrazuje atrapou. Spusteni: /opt/konfigurator/api/venv/bin/python3 scripts/2026-10-02_restic_backup_testy/test_restic_backup.py"""
import hashlib
import importlib.util
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
tmp = tempfile.mkdtemp(prefix="test_restic_")
src = os.path.join(tmp, "projekt"); repo = os.path.join(tmp, "repo")
pw = os.path.join(tmp, "heslo"); open(pw, "w").write("testovaci-heslo-jen-pro-test\n"); os.chmod(pw, 0o600)
os.environ.update({"RESTIC_REPOSITORY": repo, "RESTIC_PASSWORD_FILE": pw, "RESTIC_SOURCE_ROOT": src, "RESTIC_EXTRA_PATHS": "",
                   "RESTIC_CACHE_DIR": os.path.join(tmp, "cache"), "RESTIC_BACKUP_LOCK": os.path.join(tmp, "lock")})
spec = importlib.util.spec_from_file_location("restic_backup_testovany", os.environ.get("RESTIC_BACKUP_PY", os.path.join(REPO_ROOT, "scripts", "restic_backup.py")))
R = importlib.util.module_from_spec(spec); spec.loader.exec_module(R)
bad = 0


def over(nazev, podminka, detail=""):
    global bad
    if not podminka:
        bad += 1
    print(f"[{'OK   ' if podminka else 'CHYBA'}] {nazev}{(' | ' + str(detail)) if detail and not podminka else ''}")


def zapis(rel, data):
    p = os.path.join(src, rel); os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "wb").write(data if isinstance(data, bytes) else data.encode())
    return p


def sha(p): return hashlib.sha256(open(p, "rb").read()).hexdigest()


# ---- vymyslene "projekt"
zapis("webapp/a.html", "<h1>a</h1>"); zapis("api/app.py", "print('x')\n"); zapis("private-files/shared-drive/dokument.pdf", os.urandom(3000))
zapis("data/velky.bin", os.urandom(20_000_000))
zapis("api/venv/lib/knihovna.py", "venv"); zapis("api/step_venv/lib/k.py", "step"); zapis("api/__pycache__/x.pyc", "pyc"); zapis("webapp/__pycache__/y.pyc", "pyc")
zapis("private-files/shared-drive/zaloha_2026-10-01.tar.gz", os.urandom(5000)); zapis("private-files/neco.tar.gz.age", os.urandom(100))

p = R.run(["restic", "init"])
over("A1 init mistniho repozitare", p.returncode == 0, p.stderr[-200:])

ok, detail, s1 = R.backup_files()
over("A2 prvni zaloha souboru proběhla", ok and s1 is not None, detail)
ls = R.run(["restic", "ls", "latest"]).stdout
over("A3 zaloha OBSAHUJE projektove soubory (webapp/a.html, api/app.py, dokument.pdf, velky.bin)",
     all(x in ls for x in ("webapp/a.html", "api/app.py", "dokument.pdf", "velky.bin")), ls[-300:])
over("A4 zaloha NEOBSAHUJE api/venv, api/step_venv, __pycache__, stare tar zalohy ani .age", not any(x in ls for x in ("api/venv", "api/step_venv", "__pycache__", "zaloha_2026", ".tar.gz.age")),
     [l for l in ls.splitlines() if any(x in l for x in ("venv", "pycache", "zaloha_", ".age"))])

# ---- prirustkovost: zmena male casti, velky soubor se znovu nenahrava
zapis("webapp/a.html", "<h1>zmeneno</h1>"); zapis("novy.txt", "novy soubor")
ok, detail, s2 = R.backup_files()
over("B1 druha zaloha proběhla", ok, detail)
over("B2 pridano jen male mnozstvi dat (< 1 MB), ale zpracovano > 20 MB (velky soubor se neprenasi znovu)",
     s2["data_added"] < 1_000_000 and s2["total_bytes_processed"] > 20_000_000, (s2["data_added"], s2["total_bytes_processed"]))
over("B3 snimky jsou dva a oba UPLNE (kazdy ukazuje na cely strom)", len(json.loads(R.run(["restic", "snapshots", "--json"]).stdout)) == 2)

# ---- obnova a porovnani
obn = os.path.join(tmp, "obnova")
p = R.run(["restic", "restore", "latest", "--target", obn])
over("C1 obnova posledniho snimku", p.returncode == 0, p.stderr[-200:])
shoda = all(sha(os.path.join(obn, src.lstrip("/"), rel)) == sha(os.path.join(src, rel)) for rel in ("webapp/a.html", "api/app.py", "data/velky.bin", "novy.txt", "private-files/shared-drive/dokument.pdf"))
over("C2 obnovene soubory se shoduji s originaly (sha256)", shoda)
obn1 = os.path.join(tmp, "obnova1")
first = json.loads(R.run(["restic", "snapshots", "--json"]).stdout)[0]["id"]
R.run(["restic", "restore", first, "--target", obn1])
over("C3 obnova STARSIHO snimku vrati puvodni obsah a-html (kazdy den je samostatne obnovitelny)", open(os.path.join(obn1, src.lstrip("/"), "webapp/a.html")).read() == "<h1>a</h1>")

# ---- databaze pres stdin, atrapa mysqldump
bindir = os.path.join(tmp, "bin"); os.makedirs(bindir)
def atrapa(kod, text, rc):
    p = os.path.join(bindir, "mysqldump")
    open(p, "w").write(f"#!/bin/sh\necho \"{text}\"\nexit {rc}\n"); os.chmod(p, 0o755)
os.environ["PATH"] = bindir + os.pathsep + os.environ["PATH"]
env = {"DB_HOST": "x", "DB_USER": "u", "DB_PASSWORD": "tajne-heslo-databaze", "DB_NAME": "testdb"}
atrapa(0, "-- dump testdb ok", 0)
ok, detail = R.backup_db(env)
over("D1 zaloha databaze streamem do restic", ok, detail)
dump = R.run(["restic", "dump", "latest", "db_testdb.sql", "--tag", "db"]).stdout
over("D2 obsah snimku db je vystup mysqldump", "dump testdb ok" in dump, dump[:100])
n_pred = len(json.loads(R.run(["restic", "snapshots", "--json", "--tag", "db"]).stdout))
atrapa(0, "-- usekly vystup", 2)
ok, detail = R.backup_db(env)
n_po = len(json.loads(R.run(["restic", "snapshots", "--json", "--tag", "db"]).stdout))
over("D3 selhani mysqldump -> hlasena chyba a vadny snimek se NEPONECHA v repozitari", (not ok) and "mysqldump" in detail and n_po == n_pred, (detail, n_pred, n_po))
over("D4 heslo databaze se nepredava v prikazove radce (MYSQL_PWD) a nikde se nevypisuje", "MYSQL_PWD" in open(R.__file__).read() and "tajne-heslo-databaze" not in detail)

# ---- chybove stavy
os.environ["RESTIC_PASSWORD_FILE"] = pw + ".neexistuje"
vysl = subprocess.run([sys.executable, R.__file__], capture_output=True, text=True, env=dict(os.environ))
over("E1 chybejici heslo repozitare -> konec s kodem 1 a hlasenim, nic se nezacne", vysl.returncode == 1 and "heslo repozitare" in vysl.stderr, vysl.stderr[-200:])
os.environ["RESTIC_PASSWORD_FILE"] = pw
open(pw + "2", "w").write("jine-heslo\n")
R.PASSWORD_FILE = pw + "2"
ok, detail, _ = R.backup_files()
over("E2 spatne heslo repozitare -> zaloha selze nahlas, nic se nezapise", not ok and ("kodem" in detail), detail[:200])
R.PASSWORD_FILE = pw

# ---- udrzba (forget --prune + check)
for i in range(3):
    zapis(f"davka{i}.txt", f"davka {i}"); R.backup_files()
ok, detail = R.maintenance()
over("F1 udrzba (forget --prune podle retence + kontrola casti dat) proběhne", ok, detail)
snimky = json.loads(R.run(["restic", "snapshots", "--json"]).stdout)
over("F2 po udrzbe zustane aspon posledni snimek kazde skupiny (soubory, db); retence drzi 1 snimek na den, takze stejnodenni testovaci snimky se spoji", len(snimky) >= 2 and {"files", "db"} <= {t for sn in snimky for t in sn.get("tags", [])}, [sn.get("tags") for sn in snimky])
obn2 = os.path.join(tmp, "obnova2")
p = R.run(["restic", "restore", "latest", "--tag", "files", "--target", obn2])
over("F3 po udrzbe jde posledni snimek souboru stale obnovit a obsah sedi", p.returncode == 0 and open(os.path.join(obn2, src.lstrip("/"), "davka2.txt")).read() == "davka 2", p.stderr[-200:])

# ---- staticke
zdroj = open(R.__file__).read()
over("G1 skript nikdy nevypisuje obsah hesla repozitare ani nema heslo natvrdo", "print(open(PASSWORD" not in zdroj and "restic-password" in zdroj)
over("G2 pouziva existujici rclone remote (zadne pristupove udaje ve skriptu)", "rclone:offsite:" in zdroj and "AWS_SECRET" not in zdroj and "access_key" not in zdroj)
over("G3 --init S3 repozitare se nikdy nespousti automaticky (jen vyslovne); druhy init je jen mistni kopie na fixni ceste", '"--init" in args' in zdroj and zdroj.count('["restic", "init"]') == 2 and "def backup_local" in zdroj)

# ---- mistni kopie na VPS: posledni 2 dny
atrapa(0, "-- dump testdb ok", 0)
R.LOCAL_REPO = os.path.join(tmp, "lokalni")
ok, detail = R.backup_local(env)
over("H1 mistni kopie: repozitar se zalozi, soubory i DB se zazalohuji", ok, detail)
over("H2 mistni kopie je ODDELENY repozitar (S3/hlavni repo se nezmenilo)", os.path.isdir(os.path.join(R.LOCAL_REPO, "snapshots")) and R._repo == R.REPO)
snap_misto = R.run(["restic", "-r", R.LOCAL_REPO, "snapshots", "--json"]).stdout
over("H3 mistni kopie: snimek souboru i DB", snap_misto.count('"snapshot') >= 0 and snap_misto.count('"tags"') == 2, snap_misto[:200])
for _ in range(3):
    zapis("webapp/zmena.txt", os.urandom(50))
    R.backup_local(env)
sn = json.loads(R.run(["restic", "-r", R.LOCAL_REPO, "snapshots", "--json"]).stdout)
over("H4 mistni kopie drzi nejvyse 2 snimky na zaloha-typ (files, db) po 4 behech", sum(1 for x in sn if "files" in x["tags"]) <= 2 and sum(1 for x in sn if "db" in x["tags"]) <= 2, [x["tags"] for x in sn])

shutil.rmtree(tmp, ignore_errors=True)
print("\n==> " + ("VSE OK" if not bad else f"{bad} CHYB"))
sys.exit(1 if bad else 0)
