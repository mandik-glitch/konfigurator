#!/usr/bin/env python3
"""
restic_backup.py - PRIRUSTKOVE zalohy projektu na S3 (bot16, 2026-10-02; Robert pres bot3 + prime rozhodnuti v okne: "Jen prirustkove zalohy").

Proc: dnesni denni zaloha (scripts/daily_backup.py) je cely projekt jako jeden tar.gz (~33 GB, roste), takze se kazdou noc znovu zabali a
nahraje vsechno, i kdyz se zmenilo par souboru, a lokalne i na S3 se hromadi dalsi desitky GB denne. restic uklada jen ZMENENE useky souboru
(deduplikace po blocich), kazdy snimek je ale uplny (obnova kteréhokoli dne neni potreba skladat z reti). Sifrovani je ve restic
(AES-256, heslo repozitare v /root/.config/backup-encryption/restic-password, mimo git).

Uloziste: repozitar na STEJNEM S3 pres existujici rclone remote "offsite" (restic -r rclone:...), takze se zadne pristupove udaje nikam
nekopiruji a nectou - rclone pouziva svou konfiguraci. Repozitar je v odlisne predpone (konfigurator-restic/), stare .age objekty se nemeni.

Co se zalohuje (snimky se znackami):
  files - cely /opt/konfigurator BEZ: api/venv, api/step_venv, __pycache__, konfigurator.sock, starych tar zaloh
          (private-files/shared-drive/zaloha_*), a dale nginx/systemd konfigurace projektu
  db    - mysqldump --single-transaction primo do restic (stdin, bez docasneho souboru; heslo pres MYSQL_PWD, ne v prikazove radce)
Mistni kopie: tatez zaloha jde i do mistniho repozitare na VPS (RESTIC_LOCAL_REPOSITORY, vychozi /var/backups/konfigurator-restic-lokalni) a drzi se v nem
jen POSLEDNI 2 DNY (Robert 2026-10-03: "na VPS staci posledni 2 dny, na S3 celek"). S3 repozitar drzi cele schema nize.
Retence (jednou tydne, nedele): 7 dennich, 2 tydenni snimky, zadne mesicni (Robert 2026-10-03: "prijde mi tech zaloh prehnane moc", pak "jeste zkratit") (forget --prune) + kontrola 5 % dat (check --read-data-subset).

Spousteni:
  restic_backup.py              denni beh (files + db, pri nedeli i udrzba)
  restic_backup.py --init       jednorazove vytvori repozitar (NIKDY automaticky - spatna konfigurace by vytvorila repozitar jinde)
  restic_backup.py --status     vypise snimky a velikost repozitare, nic nemeni
  restic_backup.py --maintenance  forget --prune + check hned
Vysledek kazdeho behu jde do tabulky offsite_backup_log (soubor = restic_RRRR-MM-DD), takze je videt v adminu (Prehledy > Zalohy).
Selhani je hlasite: kod != 0, stderr, radek stav=chyba. Nic se nemaze mimo `forget --prune` podle retence vyse.
Testy: scripts/2026-10-02_restic_backup_testy/test_restic_backup.py (mistni repozitar, vymyslena data).
"""
import datetime
import fcntl
import json
import os
import subprocess
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
REPO = os.environ.get("RESTIC_REPOSITORY", "rclone:offsite:zalohy-flotila/konfigurator-restic")
PASSWORD_FILE = os.environ.get("RESTIC_PASSWORD_FILE", "/root/.config/backup-encryption/restic-password")
RCLONE_CONFIG_FILE = os.environ.get("RCLONE_CONFIG", "/root/.config/rclone/rclone.conf")
LOCK_FILE = os.environ.get("RESTIC_BACKUP_LOCK", "/run/restic_backup.lock")
SOURCE_ROOT = os.environ.get("RESTIC_SOURCE_ROOT", PROJECT_ROOT)
EXTRA_PATHS = [p for p in os.environ.get("RESTIC_EXTRA_PATHS", "/etc/nginx/sites-available/konfigurator /etc/systemd/system").split() if p]
EXCLUDES = ("api/venv", "api/step_venv", "__pycache__", "api/konfigurator.sock", "private-files/shared-drive/zaloha_*", "*.tar.gz.age")
KEEP = ("--keep-daily", "7", "--keep-weekly", "2")
CHECK_SUBSET = "5%"
TAG = "konfigurator"
# MISTNI repozitar na VPS (Robert 2026-10-03: "na VPS staci posledni 2 dny, na S3 celek"): stejna data, jen posledni 2 dny; S3 drzi cele schema (KEEP)
LOCAL_REPO = os.environ.get("RESTIC_LOCAL_REPOSITORY", "/var/backups/konfigurator-restic-lokalni")
LOCAL_KEEP = ("--keep-daily", "2")
_repo = REPO


def restic_env():
    env = dict(os.environ)
    env["RESTIC_REPOSITORY"] = _repo
    env["RESTIC_PASSWORD_FILE"] = PASSWORD_FILE
    env["RCLONE_CONFIG"] = RCLONE_CONFIG_FILE
    env["RESTIC_CACHE_DIR"] = os.environ.get("RESTIC_CACHE_DIR", "/var/cache/restic")
    return env


def files_command(source_root=None, extra=None):
    """Prikaz restic backup pro soubory (bez zapisu, jen sestaveni - testovatelne)."""
    root = source_root or SOURCE_ROOT
    cmd = ["restic", "backup", "--json", "--tag", TAG, "--tag", "files",]
    for e in EXCLUDES:
        cmd += ["--exclude", e]
    cmd.append(root)
    cmd += [p for p in (extra if extra is not None else EXTRA_PATHS) if os.path.exists(p)]
    return cmd


def parse_summary(stdout):
    """Posledni zprava typu summary z `restic backup --json` -> dict nebo None."""
    summary = None
    for line in stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            continue
        if msg.get("message_type") == "summary":
            summary = msg
    return summary


def load_env_file():
    env = {}
    with open(os.path.join(PROJECT_ROOT, "api", ".env")) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k] = v
    return env


def zapis_log(env, nazev, stav, detail, velikost_b=None):
    """Radek do offsite_backup_log (admin Prehledy > Zalohy). Nikdy nevyhodi vyjimku ven."""
    try:
        import pymysql
        conn = pymysql.connect(host=env["DB_HOST"], port=int(env.get("DB_PORT", 3306)), user=env["DB_USER"], password=env["DB_PASSWORD"],
                               database=env["DB_NAME"], charset="utf8mb4")
        try:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO offsite_backup_log (soubor, velikost_b, remote_cesta, stav, detail) VALUES (%s,%s,%s,%s,%s)",
                            (nazev, velikost_b, REPO, stav, (detail or "")[:900]))
            conn.commit()
        finally:
            conn.close()
    except Exception as e:
        print(f"LOG: zapis do DB selhal (neni fatalni): {e}", file=sys.stderr)


def run(cmd, **kw):
    return subprocess.run(cmd, env=restic_env(), capture_output=True, text=True, **kw)


def backup_files():
    p = run(files_command(), timeout=6 * 3600)
    s = parse_summary(p.stdout)
    # restic: 0 = ok, 3 = hotovo, ale nektere soubory nesly precist (zivy system) - varovani, ne selhani
    if p.returncode not in (0, 3) or s is None:
        return False, f"restic backup (soubory) skoncil kodem {p.returncode}: {(p.stderr or p.stdout)[-500:]}", None
    detail = (f"soubory: snimek {s.get('snapshot_id', '?')[:8]}, novych {s.get('files_new')}, zmenenych {s.get('files_changed')}, "
              f"pridano {s.get('data_added', 0) / 1e6:.0f} MB, celkem zpracovano {s.get('total_bytes_processed', 0) / 1e9:.1f} GB"
              + (" (nektere soubory se nepodarilo precist, rc=3)" if p.returncode == 3 else ""))
    return True, detail, s


def backup_db(env):
    dump_cmd = ["mysqldump", "--single-transaction", "--quick", "--no-tablespaces", "--default-character-set=utf8mb4",
                "-h", env["DB_HOST"], "-P", env.get("DB_PORT", "3306"), "-u", env["DB_USER"], env["DB_NAME"]]
    dump_env = dict(os.environ, MYSQL_PWD=env["DB_PASSWORD"])      # heslo ne v prikazove radce (ps)
    restic_cmd = ["restic", "backup", "--json", "--tag", TAG, "--tag", "db", "--stdin", "--stdin-filename", f"db_{env['DB_NAME']}.sql"]
    dump = subprocess.Popen(dump_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=dump_env)
    rs = subprocess.Popen(restic_cmd, stdin=dump.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=restic_env(), text=True)
    dump.stdout.close()
    out, err = rs.communicate(timeout=3600)
    dump_err = dump.stderr.read().decode(errors="replace")[:300]
    dump_rc = dump.wait()
    if dump_rc != 0:
        # usekly vypis by restic ulozil jako uspesny snimek - smazat ho, at neni v repozitari jako "platna" zaloha
        s = parse_summary(out)
        if s and s.get("snapshot_id"):
            run(["restic", "forget", s["snapshot_id"]])
        return False, f"mysqldump skoncil kodem {dump_rc}: {dump_err}; snimek db zrusen"
    s = parse_summary(out)
    if rs.returncode != 0 or s is None:
        return False, f"restic backup (db) skoncil kodem {rs.returncode}: {(err or out)[-400:]}"
    return True, f"db: snimek {s.get('snapshot_id', '?')[:8]}, pridano {s.get('data_added', 0) / 1e6:.1f} MB"


def maintenance():
    run(["restic", "unlock"], timeout=600)                 # zastaraly zamek po prerusenem behu (proces uz neexistuje) by zablokoval udrzbu; unlock bez --remove-all maze jen zastarale (2026-10-04)
    f = run(["restic", "forget", "--prune", "--tag", TAG] + list(KEEP), timeout=6 * 3600)
    if f.returncode != 0:
        return False, f"forget --prune selhal (rc={f.returncode}): {(f.stderr or f.stdout)[-400:]}"
    c = run(["restic", "check", f"--read-data-subset={CHECK_SUBSET}"], timeout=6 * 3600)
    if c.returncode != 0:
        return False, f"check selhal (rc={c.returncode}): {(c.stderr or c.stdout)[-400:]}"
    return True, f"udrzba OK (retence 7 dni + 2 tydny, kontrola {CHECK_SUBSET} dat)"


def backup_local(env):
    """Stejna zaloha do mistniho repozitare na VPS + udrzba na posledni 2 dny (kazdou noc, je to mistni disk). -> (ok, detail)."""
    global _repo
    if not LOCAL_REPO:
        return True, "mistni kopie vypnuta"
    prev, _repo = _repo, LOCAL_REPO
    try:
        os.makedirs(LOCAL_REPO, exist_ok=True)
        if run(["restic", "cat", "config"]).returncode != 0:          # mistni repozitar jeste neexistuje: zalozit (fixni cesta, ne S3)
            i = run(["restic", "init"])
            if i.returncode != 0:
                return False, f"mistni repozitar: init selhal: {(i.stderr or i.stdout)[-300:]}"
        ok_f, d_f, _s = backup_files()
        ok_d, d_d = backup_db(env)
        if not (ok_f and ok_d):
            return False, f"mistni kopie: {d_f} | {d_d}"
        f = run(["restic", "forget", "--prune", "--tag", TAG] + list(LOCAL_KEEP), timeout=3600)
        if f.returncode != 0:
            return False, f"mistni kopie: forget --prune selhal: {(f.stderr or f.stdout)[-300:]}"
        return True, "mistni kopie VPS OK (posledni 2 dny)"
    finally:
        _repo = prev


def main():
    args = sys.argv[1:]
    if not os.path.isfile(PASSWORD_FILE):
        print(f"CHYBA: chybi heslo repozitare {PASSWORD_FILE}", file=sys.stderr)
        sys.exit(1)
    lock = open(LOCK_FILE, "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print("CHYBA: jiny beh restic_backup.py uz bezi", file=sys.stderr)
        sys.exit(1)
    if "--init" in args:
        p = run(["restic", "init"])
        print(p.stdout + p.stderr)
        sys.exit(p.returncode)
    if "--status" in args:
        p = run(["restic", "snapshots", "--compact"])
        print(p.stdout + p.stderr)
        st = run(["restic", "stats", "--mode", "raw-data"])
        print(st.stdout + st.stderr)
        sys.exit(p.returncode)
    if "--maintenance" in args:
        ok, detail = maintenance()
        print(detail)
        sys.exit(0 if ok else 1)

    try:
        env = load_env_file()
    except OSError as e:
        print(f"CHYBA: nelze nacist api/.env: {e}", file=sys.stderr)
        sys.exit(1)
    today = datetime.date.today()
    nazev = f"restic_{today.isoformat()}"
    chyby = []
    ok_f, d_f, _s = backup_files()
    print(("OK    " if ok_f else "CHYBA ") + d_f)
    ok_d, d_d = backup_db(env)
    print(("OK    " if ok_d else "CHYBA ") + d_d)
    detail = f"{d_f} | {d_d}"
    stav = "ok" if (ok_f and ok_d) else "chyba"
    if ok_f and ok_d:                                     # mistni kopie na VPS (posledni 2 dny); chyba tady se hlasi, S3 zaloha ale platí
        ok_l, d_l = backup_local(env)
        print(("OK    " if ok_l else "CHYBA ") + d_l)
        detail += " | " + d_l
        if not ok_l:
            stav = "chyba"
    if today.weekday() == 6 and ok_f and ok_d:           # nedele: udrzba (retence + kontrola casti dat)
        ok_m, d_m = maintenance()
        print(("OK    " if ok_m else "CHYBA ") + d_m)
        detail += " | " + d_m
        stav = "ok" if ok_m else "chyba"
    zapis_log(env, nazev, stav, detail)
    sys.exit(0 if stav == "ok" else 1)


if __name__ == "__main__":
    main()
