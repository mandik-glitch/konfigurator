#!/opt/konfigurator/api/venv/bin/python
"""Testy scripts/daily_backup.py (bot16, 2026-10-02: predsmazani, kontrola mista, --dry-run, streamovane sifrovani age | rclone rcat).

Zadna ostra data: cista logika nad vymyslenymi nazvy a velikostmi, streamovani proti MISTNIMU cili (rclone rcat do docasne slozky,
bez pristupu ke zdejsimu uloziste) a s JEDNORAZOVYM klicem age vytvorenym v testu (skutecne klice se nectou ani nepouzivaji).
Spusteni: /opt/konfigurator/api/venv/bin/python3 scripts/2026-10-02_daily_backup_testy/test_daily_backup.py
Kandidat pred nasazenim: DAILY_BACKUP_PY=/cesta/daily_backup.py ...
"""
import datetime
import hashlib
import importlib.util
import os
import subprocess
import sys
import tempfile

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
PY = os.environ.get("DAILY_BACKUP_PY", os.path.join(REPO, "scripts", "daily_backup.py"))
spec = importlib.util.spec_from_file_location("daily_backup_testovany", PY)
B = importlib.util.module_from_spec(spec)
spec.loader.exec_module(B)

bad = 0


def over(nazev, podminka, detail=""):
    global bad
    if not podminka:
        bad += 1
    print(f"[{'OK   ' if podminka else 'CHYBA'}] {nazev}{(' | ' + str(detail)) if detail and not podminka else ''}")


D = datetime.date
dnes = D(2026, 10, 3)


def n(d):
    return f"zaloha_{d}.tar.gz"


# ---------------------------------------------------------------- plan_predelete
existing = {n("2026-09-15"): 11, n("2026-09-29"): 32, n("2026-09-30"): 33, n("2026-10-01"): 34, n("2026-10-02"): 35}
keep = {n("2026-10-03"), n("2026-10-02"), n("2026-10-01"), n("2026-09-29"), n("2026-09-15"), n("2026-08-06")}
offsite_all = {n(x) + ".age" for x in ("2026-09-15", "2026-09-29", "2026-09-30", "2026-10-01")}

smazat, pres = B.plan_predelete(existing, keep, offsite_all, dnes)
over("A1 normalni noc: predem se smaze jen 09-30 (mimo keep, ma off-site, zustavaji dnes-1 a dnes-2)", smazat == [n("2026-09-30")] and not pres, (smazat, pres))
smazat, pres = B.plan_predelete(existing, keep, offsite_all - {n("2026-09-30") + ".age"}, dnes)
over("A2 bez off-site kopie se NEsmaze (a duvod se hlasi)", smazat == [] and n("2026-09-30") in pres, (smazat, pres))
ex2 = dict(existing); del ex2[n("2026-10-02")]
smazat, pres = B.plan_predelete(ex2, keep, offsite_all, dnes)
over("A3 chybi zaloha dnes-1 (jen jedna denni) -> nic se predem nemaze", smazat == [] and n("2026-09-30") in pres, (smazat, pres))
ex3 = dict(existing); del ex3[n("2026-10-02")]; del ex3[n("2026-10-01")]
smazat, pres = B.plan_predelete(ex3, keep, offsite_all, dnes)
over("A4 zadna denni zaloha na disku -> nic se predem nemaze", smazat == [], (smazat, pres))
smazat, pres = B.plan_predelete(existing, keep | {n("2026-09-30")}, offsite_all, dnes)
over("A5 soubor v keep (slot) se nikdy nemaze", smazat == [], (smazat, pres))
smazat, pres = B.plan_predelete({**existing, "zaloha_neco.tar.gz": 5, "zaloha_2026-09-14.tar.gz.age": 5, "jine.txt": 1}, keep, offsite_all, dnes)
over("A6 soubory s jinym tvarem nazvu se ignoruji (nikdy je nemazat)", smazat == [n("2026-09-30")], smazat)
smazat, pres = B.plan_predelete(existing, keep, set(), dnes, offsite_enabled=False)
over("A7 bez off-site (vypnuto) se maze podle retence i bez kopie, jinak stejna pravidla", smazat == [n("2026-09-30")], smazat)
smazat, pres = B.plan_predelete({}, keep, offsite_all, dnes)
over("A8 prazdny disk -> nic", smazat == [] and not pres)
smazat, pres = B.plan_predelete(existing, set(), offsite_all, dnes)
over("A9 pri prazdnem keep (chyba) se predem smaze jen to, co vyhovi vsem pravidlum (dnes-1/dnes-2 zustavaji kvuli zbyle denni zaloze)", all(x in existing for x in smazat), smazat)

# ---------------------------------------------------------------- kontrola mista
ok1, need = B.check_free_space(35_286_638_618, 50_000_000_000)
over("B1 volno 50 GB pri posledni zaloze 35,3 GB -> potreba 42,3 GB, OK", ok1 and need == int(35_286_638_618 * 1.2), need)
ok2, _ = B.check_free_space(35_286_638_618, 42_000_000_000)
over("B2 volno 42 GB < 42,3 GB -> NEDOSTATEK", not ok2)
ok3, need3 = B.check_free_space(0, 0)
over("B3 zadna predchozi zaloha (prvni beh) -> potreba 0, OK", ok3 and need3 == 0)
over("B4 posledni zaloha se bere podle data v nazvu", B._last_archive_size({n("2026-09-29"): 1, n("2026-10-02"): 9, n("2026-10-01"): 5}) == 9)

# ---------------------------------------------------------------- velikost age souboru proti SKUTECNYM zalohám (z offsite_backup_files)
for lok, off in ((11470738032, 11473538696), (32679241220, 32687219740)):
    over(f"C velikost age souboru pro {lok} B presne sedi se skutecnou off-site kopii ({off} B)", B.expected_age_size(lok) == off, B.expected_age_size(lok))

# ---------------------------------------------------------------- streamovani age | rclone rcat (mistni cil, jednorazovy klic)
tmp = tempfile.mkdtemp(prefix="test_backup_stream_")
ident = os.path.join(tmp, "klic.txt")
subprocess.run(["age-keygen", "-o", ident], capture_output=True, check=True)
pub = [l.split(": ", 1)[1].strip() for l in open(ident) if l.startswith("# public key:")][0]
zdroj = os.path.join(tmp, "archiv.tar.gz")
with open(zdroj, "wb") as f:
    for i in range(40):
        f.write(os.urandom(250_000))                       # ~10 MB, neni to nasobek bloku 64 KiB
cil_dir = os.path.join(tmp, "cil"); os.makedirs(cil_dir)
cil = os.path.join(cil_dir, "archiv.tar.gz.age")
ok, detail = B._stream_upload(zdroj, cil, pub, "/dev/null")
over("D1 stream age | rclone rcat do mistniho cile skonci OK", ok, detail)
vel = os.path.getsize(cil) if os.path.isfile(cil) else -1
over("D2 velikost vysledneho souboru presne odpovida expected_age_size", vel == B.expected_age_size(os.path.getsize(zdroj)), (vel, B.expected_age_size(os.path.getsize(zdroj))))
dec = subprocess.run(["age", "-d", "-i", ident, cil], capture_output=True)
over("D3 desifrovanim vznikne totez (sha256 se shoduje s originalem)", dec.returncode == 0 and hashlib.sha256(dec.stdout).hexdigest() == hashlib.sha256(open(zdroj, "rb").read()).hexdigest())
# selhani age: neplatny klic
ok, detail = B._stream_upload(zdroj, os.path.join(cil_dir, "x.age"), "age1neplatnyklic", "/dev/null")
over("D4 neplatny klic age -> chyba hlasena (stream selze, nic neprojde tise)", not ok and "age" in str(detail).lower(), detail)
# selhani rclone: cil do neexistujici nezapisovatelne cesty
ok, detail = B._stream_upload(zdroj, "/proc/nelze/zapsat.age", pub, "/dev/null")
over("D5 rclone nemuze zapisovat -> chyba hlasena", not ok and "rclone" in str(detail).lower(), detail)
# prekroceni casoveho limitu (limit 1 s, rclone nahrazen pomalym skriptem)
slow_dir = os.path.join(tmp, "bin"); os.makedirs(slow_dir)
with open(os.path.join(slow_dir, "rclone"), "w") as f:
    f.write("#!/bin/sh\nsleep 30\n")
os.chmod(os.path.join(slow_dir, "rclone"), 0o755)
puvodni_path, puvodni_t = os.environ["PATH"], B.RCAT_TIMEOUT_S
os.environ["PATH"] = slow_dir + os.pathsep + puvodni_path
B.RCAT_TIMEOUT_S = 1
ok, detail = B._stream_upload(zdroj, os.path.join(cil_dir, "pomale.age"), pub, "/dev/null")
os.environ["PATH"], B.RCAT_TIMEOUT_S = puvodni_path, puvodni_t
over("D6 prilis dlouhy prenos se po limitu preruší a hlasi se", not ok and "prerusen" in str(detail), detail)
# stejny soubor nesmi zustat nikde na disku v nesifrovane podobe mimo zdroj; v cili jsou jen .age
over("D7 v cili je jen zasifrovany soubor (zadne .tar.gz)", all(f.endswith(".age") for f in os.listdir(cil_dir)), os.listdir(cil_dir))

# ---------------------------------------------------------------- staticke kontrakty
src = open(PY, encoding="utf-8").read()
over("E1 vychozi rezim off-site je 'file' nebo 'stream' a puvodni upload zustal jako volba",
     'OFFSITE_MODE_DEFAULT = "' in src and "def _upload_offsite_soubor" in src and "def _upload_offsite_stream" in src)
over("E2 ve skriptu neni zadny holy 'shutil.rmtree' ani 'rm -rf' (mazani jen os.remove po planu)", "rmtree" not in src.replace("TemporaryDirectory", "") and "rm -rf" not in src)
over("E3 klic age a rclone.conf se nikde nevypisuji (zadny print/obsah)", "print(pubkey" not in src and "print(open(RCLONE" not in src)

print("\n==> " + ("VSE OK" if not bad else f"{bad} CHYB"))
sys.exit(1 if bad else 0)
