#!/usr/bin/env python3
"""
daily_backup.py - denni zaloha kompletniho projektu na Sdileny disk
(bot5, 2026-08-06). Robert: "udelej zalohu kompletniho projektu a
souvisejici veci, uloz do naseho sdileneho disku, je tam nova slozka
zalohy. Sem budeme automaticky delat zalohy celeho systemu, kazdy den."

Co zaloha obsahuje (jeden .tar.gz archiv):
  - cely /opt/konfigurator VC. .git historie, nahranych souboru
    (webapp/content-files - GLB modely, FBX zdroje, obrazky) a
    private-files (CRM prilohy, doklady, Sdileny disk)
  - BEZ: api/venv a api/step_venv (obnovitelne pres pip z
    requirements), __pycache__, unix socket, a PREDCHOZICH zaloh
    (private-files/shared-drive/zaloha_* - jinak by kazda dalsi zaloha
    obsahovala vsechny predchozi a rostla exponencialne)
  - dump kompletni databaze (mysqldump --single-transaction, gzip)
  - systemova konfigurace: nginx site config + vsechny
    konfigurator*.service/.timer systemd jednotky

Ulozeni: primo do uloziste Sdileneho disku (private-files/shared-drive/)
pod NAZVEM zaloha_RRRR-MM-DD.tar.gz (zamerne NE nahodny token jako u
bezneho uploadu - rozpoznatelny nazev umoznuje exclude pattern vyse) +
radek v shared_drive_files ve slozce "Zalohy", takze zaloha jde
stahnout primo z administrace.

Retence (Robert 2026-08-07: "držme zálohy poslední 3 dny každý den
jednu zálohu, týden starou jednu zálohu, 14 dní starou jednu zálohu a
2 měsíce starou") - odstupnovana rotace se 4 sloty:
  - denni: posledni 3 kalendarni dny (vzdy vsechny)
  - tydenni/dvoutydenni/dvoumesicni: po JEDNE zaloze v kazdem slotu

DULEZITE (proc ne proste "kazdy den vyber zalohu nejblize cili N dni"):
prvni verze tehle retence to delala presne takhle ("closest to target"
prepocitane znovu kazdy den ze vseho, co existuje) a v simulaci na
stovky dni dopredu (viz komentar v AGENTS_LOG.md) se ukazalo, ze
dvoumesicni slot takhle nekontrolovane STARNE - kdyz nic lepsiho
neni k dispozici, algoritmus si radeji drzi porad tu samou zalohu
(protoze cim je starsi, tim je "nejblizsi" porovnani se 60 dny porad
jeste vyhodnocovalo jako "nejlepsi dostupna", i kdyz uz jí bylo klidne
100+ dni) - misto stabilnich ~60 dni to umelo driftovat az k
100-110 dnum, nez se konecne vymenila.

Misto toho: explicitni STAVOVA ROTACE (stejny princip jako
logrotate/rsnapshot) - v `app_settings` (klice
backup_retention_<slot>_file/_promo_date, viz RETENTION_TIERS nize) se
pamatuje, ktera konkretni zaloha aktualne obsazuje tydenni/
dvoutydenni/dvoumesicni slot a kdy tam byla naposledy povysena:
  - kazdych 7 dni: aktualne nejstarsi z "dennich" zaloh (ta, co za
    chvili stejne vypadne z 3denniho okna) POVYSI do tydenniho slotu,
    nahrazujic tam predchozi obsah.
  - kazdych 14 dni: obsah tydenniho slotu POVYSI do dvoutydenniho,
    nahrazujic tam predchozi obsah.
  - kazdych 60 dni: obsah dvoutydenniho slotu POVYSI do
    dvoumesicniho, nahrazujic (a mazajic) predchozi obsah.
Kazdy slot tak drzi jen jednu zalohu, jejiz stari kolisa v ohranicenem
rozsahu (tydenni cca 2-8 dni, dvoutydenni cca 2-15, dvoumesicni cca
2-75 dni) - bez neomezeneho driftu, presne overeno simulaci pres
600 dni dopredu.
Pri prvnim spusteni (nebo kdyz zaloha, kterou by mel slot povysit,
jeste neexistuje) se povyseni jednoduse presune na dalsi den - zadna
chyba, jen se slot naplni, az bude na co sahnout.

Spousteni: systemd timer konfigurator-daily-backup.timer (denne 03:30),
rucne: /opt/konfigurator/api/venv/bin/python3 scripts/daily_backup.py

Disk, predsmazani a streamovane sifrovani (bot16, 2026-10-02, Robert pres bot3: disk 95 %, dnesni off-site upload selhal "no space left
on device", protoze se archiv nejdriv cely zasifroval do druheho souboru .age vedle sebe):
  - PREDSMAZANI: pred dumpem a tarem se spocita `keep` pro dnesek (stejna retence jako dosud) a smazou se archivy, ktere by retence stejne
    smazala PO zaloze - jen kdyz maji off-site kopii (offsite_backup_files) a po smazani zustanou aspon 2 denni zalohy (dnes-1, dnes-2).
    Pri jakekoli chybe se nic nemaze.
  - KONTROLA MISTA: volno musi byt >= 1,2x velikost posledni zalohy, jinak se nic nezacne, skript selze nahlas (stderr + radek stav=chyba
    v offsite_backup_log, viditelny v adminu) a nic nevznikne.
  - STREAM: sifrovani jde rovnou do uploadu (age | rclone rcat), zadna druha lokalni kopie .age, takze spicka disku je 1x zaloha misto 2x.
    Puvodni zpusob zustava jako volba (promenna BACKUP_OFFSITE_MODE=file). Velikost nahraneho objektu se po uploadu overuje (age pridava
    pevnou hlavicku a 16 B na kazdy 64 KiB blok), nahrany objekt s vadnou velikosti se smaze a hlasi se chyba.
  - `--dry-run`: vypise plan (co by predem smazal, volno, zda by zaloha zacala), nic nemeni a nastaveni retence vrati zpet.

Off-site kopie (bot17, 2026-09-03, Robertovo rozhodnuti po dotazu bot3 -
Contabo Object Storage, S3-kompatibilni, nezavisle na tomhle VPS): PO
uspesne lokalni zaloze (vc. retence) se hotovy archiv jeste zasifruje
(`age`, asymetricky - jen verejnym klicem z
/root/.config/backup-encryption/age-public-key.txt, privatni klic pro
desifrovani existuje JEN v age-key.txt na tomhle serveru, nikdy
neopousti VPS at uz jde kamkoli) a nahraje pres `rclone` na S3 remote
"offsite" (config /root/.config/rclone/rclone.conf - MIMO git, obsahuje
credentials). Duvod sifrovani: kdyby unikl/byl spatne nastaveny S3
bucket u externiho poskytovatele, obsah zustava neciteny bez privatniho
klice, ktery bucket sam nikdy neobsahuje. NON-FATAL krok - dokud
rclone.conf/credentials nejsou hotove (cekame na Robert/bot3), nebo kdyz
upload jednorazove selze, lokalni zaloha/retence tim NENI ovlivnena, jen
se vypise chyba do stderr (viditelna v `journalctl`).
"""
import datetime
import glob
import gzip
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "api"))

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
DRIVE_DIR = os.path.join(PROJECT_ROOT, "private-files", "shared-drive")
BACKUP_FOLDER_NAME = "Zalohy"
KEEP_DAILY = 3

# bot16, 2026-10-02 - viz docstring nahore ("Disk, predsmazani a streamovane sifrovani")
MIN_FREE_FACTOR = 1.2          # volno pred zalohou >= 1,2x velikost posledni zalohy (tar ve stagingu, presun na disk je rename)
MIN_DAILY_KEEP = 2             # nikdy nemazat predem, kdyby po smazani zbyly mene nez 2 denni zalohy (dnes-1, dnes-2)
STAGING_BASE = "/var/tmp"
OFFSITE_MODE_DEFAULT = "stream"  # "stream" (age | rclone rcat, bez 2. kopie na disku) | "file" (puvodni: .age vedle archivu)
OFFSITE_MODE_ENV = "BACKUP_OFFSITE_MODE"
RCAT_TIMEOUT_S = 7200
_ARCHIVE_RE = re.compile(r"^zaloha_\d{4}-\d{2}-\d{2}\.tar\.gz$")
AGE_BLOCK = 65536              # age sifruje po 64 KiB blocich, ke kazdemu pricita 16 B tag
AGE_HEADER_B = 184             # fixni hlavicka age pro JEDNOHO prijemce X25519, overeno na skutecnych zalohach 2026-09-15/09-30 (rozdil velikosti presne 184 B)

# Poradi je dulezite - kaskada se vyhodnocuje od nejcastejsiho slotu k
# nejrezavejsimu, at pripadne cerstve povyseni z predchoziho slotu
# stihne jeste ten den propadnout dal (viz _run_retention).
RETENTION_TIERS = (
    # (nazev, interval_dni, zdroj_pro_povyseni)
    # "daily-2" = zaloha z dneska-2 dny (aktualne nejstarsi z denni trojice)
    ("weekly", 7, "daily-2"),
    ("biweekly", 14, "weekly"),
    ("bimonthly", 60, "biweekly"),
)

PROJECT_NAME = "konfigurator"
RCLONE_REMOTE = "offsite"
S3_BUCKET = "zalohy-flotila"
AGE_PUBKEY_FILE = "/root/.config/backup-encryption/age-public-key.txt"
RCLONE_CONFIG_FILE = "/root/.config/rclone/rclone.conf"

def _zapis_offsite_log(env, soubor, velikost_b, remote_cesta, stav, detail=None,
                        remote_objektu_celkem=None, remote_bytu_celkem=None):
    """Zaznam pokusu o offsite upload pro admin prehled (Robert pres
    bot3, 2026-09-13 - "at se kvuli tomu nemusi prihlasovat na Contabo",
    viz sql/2026-09-13_offsite_backup_log.sql). VOLA SE JEN Z upload_offsite(),
    ktery uz je celý obalený vlastnim try/except - tahle funkce navic
    NIKDY nesmi shodit ANI upload_offsite() samotny, natoz cely denni
    backup (proto vlastni try/except tady znovu, i kdyz uz jeden je o
    uroven vys - DB zapis je čiste "navic", zadny duvod, aby chyba v nem
    (napr. vypadek DB) znicila neco, co uz je jinak hotove)."""
    try:
        conn = db_connect(env)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO offsite_backup_log "
                    "(soubor, velikost_b, remote_cesta, stav, detail, remote_objektu_celkem, remote_bytu_celkem) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s)",
                    (soubor, velikost_b, remote_cesta, stav, detail, remote_objektu_celkem, remote_bytu_celkem),
                )
            conn.commit()
        finally:
            conn.close()
    except Exception as e:
        print(f"OFF-SITE LOG: zapis do DB selhal (neni to fatalni, jen chybi v adminu): {e}", file=sys.stderr)


def _rclone_seznam_souboru():
    """`rclone lsjson` na cely projektovy adresar remote - Robert
    upresnil ("má zde být výpis uložených souborů záloh z uloziste S3,
    ne samotne soubory, jen seznam"): admin prehled chce SKUTECNY seznam
    toho, co na S3 je (ne jen pocet/soucet), viz
    sql/2026-09-13_offsite_backup_files.sql. Vraci list [{"soubor":...,
    "velikost_b":...,"zmeneno_at": iso-string nebo None}, ...], nebo None
    pri jakekoli chybe - cist se sem chodi JEN po uspesnem uploadu (uz
    vime, ze pripojeni funguje), takze chyba tady uz je jen kosmeticka
    (chybejici seznam v adminu), ne duvod cokoli hlasit jako selhani
    zalohy."""
    try:
        remote_dir = f"{RCLONE_REMOTE}:{S3_BUCKET}/{PROJECT_NAME}/"
        p = subprocess.run(
            ["rclone", "lsjson", remote_dir, "--config", RCLONE_CONFIG_FILE,
             "--contimeout", "30s", "--timeout", "60s"],
            capture_output=True, text=True, timeout=120,
        )
        if p.returncode != 0:
            return None
        polozky = json.loads(p.stdout)
        return [
            {"soubor": it["Name"], "velikost_b": it["Size"], "zmeneno_at": it.get("ModTime")}
            for it in polozky if not it.get("IsDir")
        ]
    except Exception:
        return None


def _sync_offsite_files(env, soubory):
    """Prepise offsite_backup_files aktualnim seznamem (DELETE + INSERT,
    ne jen pridavani) - at tabulka odrazi i pripadne rucni smazani na
    strane S3, ne jen prirustky. Vlastni try/except (stejny duvod jako u
    _zapis_offsite_log) - chyba tady nesmi shodit nic dalsiho."""
    if soubory is None:
        return
    try:
        conn = db_connect(env)
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM offsite_backup_files")
                for it in soubory:
                    zmeneno = None
                    if it.get("zmeneno_at"):
                        try:
                            zmeneno = datetime.datetime.fromisoformat(
                                it["zmeneno_at"].replace("Z", "+00:00")
                            ).strftime("%Y-%m-%d %H:%M:%S")
                        except ValueError:
                            zmeneno = None
                    cur.execute(
                        "INSERT INTO offsite_backup_files (soubor, velikost_b, zmeneno_at) VALUES (%s,%s,%s)",
                        (it["soubor"], it["velikost_b"], zmeneno),
                    )
            conn.commit()
        finally:
            conn.close()
    except Exception as e:
        print(f"OFF-SITE SOUBORY: sync seznamu do DB selhal (neni to fatalni): {e}", file=sys.stderr)


def _upload_offsite_soubor(archive_path, archive_name, env=None):
    """PUVODNI zpusob (rezim "file"): archiv se zasifruje do druheho souboru .age vedle sebe a ten se nahraje (potrebuje na disku
    navic misto jako cela zaloha). Sifrovana off-site kopie hotoveho archivu - viz docstring nahore.
    Zamerne NIKDY nevyhazuje vyjimku ven - selhani tohohle kroku nesmi
    shodit zbytek skriptu (lokalni zaloha uz je v tu chvili hotova)."""
    try:
        if not os.path.isfile(RCLONE_CONFIG_FILE):
            print(f"OFF-SITE UPLOAD PRESKOCEN: {RCLONE_CONFIG_FILE} zatim neexistuje (ceka se na Contabo credentials).", file=sys.stderr)
            if env:
                _zapis_offsite_log(env, archive_name, None, None, "preskoceno", "rclone.conf zatim neexistuje")
            return
        if not os.path.isfile(AGE_PUBKEY_FILE):
            print(f"OFF-SITE UPLOAD PRESKOCEN: {AGE_PUBKEY_FILE} chybi.", file=sys.stderr)
            if env:
                _zapis_offsite_log(env, archive_name, None, None, "preskoceno", "age-public-key.txt chybi")
            return
        velikost_b = os.path.getsize(archive_path) if os.path.isfile(archive_path) else None
        with open(AGE_PUBKEY_FILE) as f:
            pubkey = f.read().strip()
        encrypted_path = archive_path + ".age"
        try:
            p = subprocess.run(
                ["age", "-r", pubkey, "-o", encrypted_path, archive_path],
                capture_output=True, text=True, timeout=1800,
            )
            if p.returncode != 0:
                print(f"OFF-SITE UPLOAD CHYBA: sifrovani selhalo: {p.stderr[:500]}", file=sys.stderr)
                if env:
                    _zapis_offsite_log(env, archive_name, velikost_b, None, "chyba", "sifrovani selhalo: " + p.stderr[:500])
                return
            remote_path = f"{RCLONE_REMOTE}:{S3_BUCKET}/{PROJECT_NAME}/{archive_name}.age"
            p = subprocess.run(
                ["rclone", "copyto", encrypted_path, remote_path,
                 "--config", RCLONE_CONFIG_FILE,
                 # Explicitni site timeouty - bez nich umi rclone na
                 # nedostupnem/spatne nakonfigurovanem endpointu viset
                 # klidne desitky minut (zivě overeno pri testu s
                 # neplatnym endpointem, bot17 2026-09-03), coz by
                 # blokovalo cely denni backup skript zbytecne dlouho.
                 "--contimeout", "30s", "--timeout", "120s",
                 "--retries", "3", "--low-level-retries", "3"],
                capture_output=True, text=True, timeout=5400,
            )
            if p.returncode != 0:
                print(f"OFF-SITE UPLOAD CHYBA: rclone selhal: {p.stderr[:500]}", file=sys.stderr)
                if env:
                    _zapis_offsite_log(env, archive_name, velikost_b, remote_path, "chyba", "rclone selhal: " + p.stderr[:500])
                return
            print(f"OFF-SITE UPLOAD OK: {remote_path}")
            if env:
                soubory = _rclone_seznam_souboru()
                pocet = len(soubory) if soubory is not None else None
                bajty = sum(it["velikost_b"] for it in soubory) if soubory is not None else None
                _zapis_offsite_log(env, archive_name, velikost_b, remote_path, "ok", None, pocet, bajty)
                _sync_offsite_files(env, soubory)
        finally:
            try:
                os.remove(encrypted_path)
            except OSError:
                pass
    except Exception as e:
        print(f"OFF-SITE UPLOAD CHYBA (neocekavana): {e}", file=sys.stderr)
        if env:
            _zapis_offsite_log(env, archive_name, None, None, "chyba", f"neocekavana chyba: {e}")

# ---------------------------------------------------------------------------------------------------------------- bot16 2026-10-02
def expected_age_size(n):
    """Velikost age souboru pro n bajtu vstupu: pevna hlavicka + 16 B tag na kazdy 64 KiB blok. Konstanta hlavicky se pri testu odvodi ze
    skutecnych zaloh (3 dvojice lokalni/off-site velikost z offsite_backup_files); do ni se pri kontrole pripocita tolerance 1 KiB."""
    blocks = -(-n // AGE_BLOCK) if n else 1
    return n + 16 * blocks + (AGE_HEADER_B if AGE_HEADER_B is not None else 0)


def _stream_upload(archive_path, remote_path, pubkey, rclone_config, rclone_extra=None):
    """age -r KLIC < archiv | rclone rcat REMOTE - bez lokalni kopie .age. -> (ok, detail). Kontroluje navratove kody OBOU procesu
    (usekly proud by rclone jinak ulozil jako hotovy objekt, kdyby age spadl uprostred)."""
    err_file = tempfile.TemporaryFile()
    try:
        with open(archive_path, "rb") as src:
            age = subprocess.Popen(["age", "-r", pubkey], stdin=src, stdout=subprocess.PIPE, stderr=err_file)
            cmd = ["rclone", "rcat", remote_path, "--config", rclone_config,
                   "--contimeout", "30s", "--timeout", "120s", "--low-level-retries", "3",
                   "--s3-chunk-size", "64M", "--s3-upload-concurrency", "2"] + list(rclone_extra or [])
            rc = subprocess.Popen(cmd, stdin=age.stdout, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            age.stdout.close()
            try:
                _, rc_err = rc.communicate(timeout=RCAT_TIMEOUT_S)
            except subprocess.TimeoutExpired:
                rc.kill(); age.kill()
                rc.communicate(); age.wait()
                return False, f"prenos trval dele nez {RCAT_TIMEOUT_S} s a byl prerusen"
            age_rc = age.wait()
        err_file.seek(0)
        age_err = err_file.read().decode(errors="replace")[:500]
    finally:
        err_file.close()
    if rc.returncode != 0:
        return False, f"rclone rcat skoncil kodem {rc.returncode}: {(rc_err or b'').decode(errors='replace')[:500]} (age kod {age_rc}: {age_err})"
    if age_rc != 0:
        return False, f"sifrovani (age) skoncilo kodem {age_rc}: {age_err}"
    return True, None


def _rclone_smaz_objekt(remote_path):
    """Smaze JEDEN nahrany objekt (nas vlastni, prave vznikly, vadny) - nikdy nic jineho."""
    try:
        p = subprocess.run(["rclone", "deletefile", remote_path, "--config", RCLONE_CONFIG_FILE,
                            "--contimeout", "30s", "--timeout", "60s"], capture_output=True, text=True, timeout=180)
        return p.returncode == 0
    except Exception:
        return False


def _upload_offsite_stream(archive_path, archive_name, env=None):
    """Rezim "stream": sifrovani rovnou do uploadu, overeni velikosti objektu. NIKDY nevyhazuje vyjimku ven (viz upload_offsite)."""
    try:
        if not os.path.isfile(RCLONE_CONFIG_FILE):
            print(f"OFF-SITE UPLOAD PRESKOCEN: {RCLONE_CONFIG_FILE} zatim neexistuje (ceka se na Contabo credentials).", file=sys.stderr)
            if env:
                _zapis_offsite_log(env, archive_name, None, None, "preskoceno", "rclone.conf zatim neexistuje")
            return
        if not os.path.isfile(AGE_PUBKEY_FILE):
            print(f"OFF-SITE UPLOAD PRESKOCEN: {AGE_PUBKEY_FILE} chybi.", file=sys.stderr)
            if env:
                _zapis_offsite_log(env, archive_name, None, None, "preskoceno", "age-public-key.txt chybi")
            return
        velikost_b = os.path.getsize(archive_path) if os.path.isfile(archive_path) else None
        with open(AGE_PUBKEY_FILE) as f:
            pubkey = f.read().strip()
        remote_path = f"{RCLONE_REMOTE}:{S3_BUCKET}/{PROJECT_NAME}/{archive_name}.age"
        ok, detail = _stream_upload(archive_path, remote_path, pubkey, RCLONE_CONFIG_FILE)
        if not ok:
            print(f"OFF-SITE UPLOAD CHYBA (stream): {detail}", file=sys.stderr)
            _rclone_smaz_objekt(remote_path)       # nedokonceny objekt by vypadal jako hotova kopie
            if env:
                _zapis_offsite_log(env, archive_name, velikost_b, remote_path, "chyba", "stream selhal: " + detail[:480])
            return
        soubory = _rclone_seznam_souboru()
        if soubory is None:
            soubory = _rclone_seznam_souboru()
        nalez = [it for it in (soubory or []) if it["soubor"] == archive_name + ".age"]
        if not nalez:
            print("OFF-SITE UPLOAD CHYBA (stream): nahrany objekt se nepodarilo overit (v seznamu na S3 neni).", file=sys.stderr)
            if env:
                _zapis_offsite_log(env, archive_name, velikost_b, remote_path, "chyba", "objekt po nahrani nenalezen v seznamu na S3 (nelze overit velikost)")
            return
        mela_byt = expected_age_size(velikost_b)
        if abs(nalez[0]["velikost_b"] - mela_byt) > 1024:
            print(f"OFF-SITE UPLOAD CHYBA (stream): velikost nahraneho objektu {nalez[0]['velikost_b']} B nesedi (cekano {mela_byt} B), objekt se maze.", file=sys.stderr)
            _rclone_smaz_objekt(remote_path)
            if env:
                _zapis_offsite_log(env, archive_name, velikost_b, remote_path, "chyba",
                                   f"velikost objektu {nalez[0]['velikost_b']} B nesedi (cekano {mela_byt} B), objekt smazan")
            return
        print(f"OFF-SITE UPLOAD OK (stream): {remote_path} ({nalez[0]['velikost_b']} B)")
        if env:
            _zapis_offsite_log(env, archive_name, velikost_b, remote_path, "ok", None, len(soubory), sum(it["velikost_b"] for it in soubory))
            _sync_offsite_files(env, soubory)
    except Exception as e:
        print(f"OFF-SITE UPLOAD CHYBA (neocekavana, stream): {e}", file=sys.stderr)
        if env:
            _zapis_offsite_log(env, archive_name, None, None, "chyba", f"neocekavana chyba: {e}")


def upload_offsite(archive_path, archive_name, env=None):
    """Off-site upload podle rezimu (BACKUP_OFFSITE_MODE: stream | file, vychozi OFFSITE_MODE_DEFAULT). NIKDY nevyhazuje vyjimku ven."""
    mode = (os.environ.get(OFFSITE_MODE_ENV) or OFFSITE_MODE_DEFAULT).strip().lower()
    print(f"OFF-SITE rezim: {mode}")
    if mode == "stream":
        return _upload_offsite_stream(archive_path, archive_name, env)
    return _upload_offsite_soubor(archive_path, archive_name, env)


# ---------------------------------------------------------------------------------------------------------------- predsmazani a misto
def _free_bytes(*paths):
    return min(shutil.disk_usage(p).free for p in paths if os.path.isdir(p))


def _archives_on_disk(drive_dir=None):
    """{nazev: velikost} pro zaloha_RRRR-MM-DD.tar.gz ve slozce Sdileneho disku (jen presne tenhle tvar nazvu)."""
    out = {}
    for p in glob.glob(os.path.join(drive_dir or DRIVE_DIR, "zaloha_*.tar.gz")):
        name = os.path.basename(p)
        if _ARCHIVE_RE.match(name):
            out[name] = os.path.getsize(p)
    return out


def _last_archive_size(archives):
    names = sorted(archives)      # ISO datum se radi abecedne
    return archives[names[-1]] if names else 0


def check_free_space(last_size, free):
    """-> (ok, potreba_bajtu). Zaloha potrebuje v nejhorsim zhruba tolik, kolik zabrala posledni, plus 20 % rezerva."""
    need = int(last_size * MIN_FREE_FACTOR)
    return free >= need, need


def plan_predelete(existing, keep, offsite_files, today, offsite_enabled=True):
    """Co se smi smazat PRED novou zalohou. -> (smazat: list, preskocit: {nazev: duvod}).
    existing: {nazev: velikost} na disku, keep: nazvy, ktere retence pro dnesek necha, offsite_files: nazvy z offsite_backup_files (s .age).
    Pravidla: jen archivy mimo keep; jen s off-site kopii (kdyz je off-site zapnuty); nic, kdyby po smazani zbyly mene nez
    MIN_DAILY_KEEP denni zalohy (dnes-1, dnes-2); nikdy soubor, ktery neodpovida tvaru zaloha_RRRR-MM-DD.tar.gz."""
    kandidati = sorted(n for n in existing if n not in keep and _ARCHIVE_RE.match(n))
    predchozi = {f"zaloha_{(today - datetime.timedelta(days=i)).isoformat()}.tar.gz" for i in range(1, MIN_DAILY_KEEP + 1)}
    if kandidati and sum(1 for n in predchozi if n in existing) < MIN_DAILY_KEEP:
        return [], {n: f"na disku je mene nez {MIN_DAILY_KEEP} denni zalohy (dnes-1, dnes-2)" for n in kandidati}
    smazat, preskocit = [], {}
    for n in kandidati:
        if offsite_enabled and (n + ".age") not in offsite_files:
            preskocit[n] = "nema off-site kopii v offsite_backup_files"
        else:
            smazat.append(n)
    return smazat, preskocit


def preflight(env, today_date, dry_run):
    """Pred dumpem a tarem: predsmazani + kontrola mista. V ostrem behu smaze, co plan dovoli; v dry-run nic nemeni (rollback). -> dict."""
    conn = db_connect(env)
    smazano, preskoceno, smazat, keep = [], {}, [], None
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM shared_drive_folders WHERE parent_folder_id IS NULL AND name=%s", (BACKUP_FOLDER_NAME,))
            row = cur.fetchone()
            folder_id = row["id"] if row else None
            existing = _archives_on_disk()
            if folder_id is not None:
                keep = _run_retention(cur, folder_id, today_date)       # stejna retence jako po zaloze (promovani slotu je idempotentni)
                cur.execute("SELECT soubor FROM offsite_backup_files")
                offsite = {r["soubor"] for r in cur.fetchall()}
                enabled = os.path.isfile(RCLONE_CONFIG_FILE) and os.path.isfile(AGE_PUBKEY_FILE)
                smazat, preskoceno = plan_predelete(existing, keep, offsite, today_date, enabled)
                if smazat and not dry_run:
                    for n in smazat:
                        try:
                            os.remove(os.path.join(DRIVE_DIR, n))
                        except OSError as e:
                            print(f"PREDSMAZANI: {n} se nepodarilo smazat ({e}), pokracuji bez nej", file=sys.stderr)
                            continue
                        cur.execute("DELETE FROM shared_drive_files WHERE folder_id=%s AND stored_filename=%s", (folder_id, n))
                        smazano.append(n)
                        print(f"PREDSMAZANI: smazana {n} (stejne by ji retence smazala po zaloze, ma off-site kopii)")
            if dry_run:
                conn.rollback()
            else:
                conn.commit()
    finally:
        conn.close()
    free = _free_bytes(DRIVE_DIR, STAGING_BASE)
    if dry_run:
        free += sum(existing[n] for n in smazat)      # co by se uvolnilo
    ok, need = check_free_space(_last_archive_size(existing), free)
    return {"existing": existing, "keep": keep, "smazat": smazat, "smazano": smazano, "preskoceno": preskoceno, "free": free, "need": need,
            "ok": ok, "last_size": _last_archive_size(existing)}


def _gib(n):
    return f"{n / 2 ** 30:.1f} GiB"


def _vypis_preflight(pf, dry_run):
    print("PREFLIGHT: archivy na disku: " + (", ".join(f"{n} ({_gib(s)})" for n, s in sorted(pf["existing"].items())) or "zadne"))
    print("PREFLIGHT: retence necha: " + (", ".join(sorted(pf["keep"])) if pf["keep"] is not None else "(slozka Zalohy v DB neexistuje - nic se nemaze)"))
    if dry_run:
        print("PREFLIGHT: predem by smazal: " + (", ".join(pf["smazat"]) or "nic"))
    for n, d in sorted(pf["preskoceno"].items()):
        print(f"PREFLIGHT: NEsmaze {n}: {d}")
    print(f"PREFLIGHT: volno {_gib(pf['free'])}{' (po predsmazani)' if dry_run else ''}, potreba {_gib(pf['need'])} "
          f"({MIN_FREE_FACTOR}x posledni zalohy {_gib(pf['last_size'])}) -> " + ("OK" if pf["ok"] else "NEDOSTATEK MISTA"))


def _fail_space(env, archive_name, pf):
    msg = (f"zaloha NESPUSTENA: volno {_gib(pf['free'])} je mene nez potreba {_gib(pf['need'])} "
           f"({MIN_FREE_FACTOR}x posledni zalohy {_gib(pf['last_size'])}); nic se nezacalo a nic dalsiho se nesmazalo")
    print("CHYBA: " + msg, file=sys.stderr)
    _zapis_offsite_log(env, archive_name, None, None, "chyba", msg)
    sys.exit(1)


def load_env():
    env = {}
    with open(os.path.join(PROJECT_ROOT, "api", ".env")) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k] = v
    return env

def db_connect(env):
    import pymysql
    return pymysql.connect(
        host=env["DB_HOST"], port=int(env.get("DB_PORT", 3306)),
        user=env["DB_USER"], password=env["DB_PASSWORD"], database=env["DB_NAME"],
        charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor,
    )

def _get_setting(cur, key):
    cur.execute("SELECT setting_value FROM app_settings WHERE setting_key=%s", (key,))
    row = cur.fetchone()
    return row["setting_value"] if row else None

def _set_setting(cur, key, value):
    cur.execute(
        "INSERT INTO app_settings (setting_key, setting_value) VALUES (%s,%s) "
        "ON DUPLICATE KEY UPDATE setting_value=%s",
        (key, value, value),
    )

def _run_retention(cur, folder_id, today):
    """Odstupnovana rotace (viz docstring nahore) - vraci mnozinu
    nazvu souboru (zaloha_RRRR-MM-DD.tar.gz), ktere se maji ponechat."""
    daily_keep = {f"zaloha_{(today - datetime.timedelta(days=i)).isoformat()}.tar.gz" for i in range(KEEP_DAILY)}

    cur.execute(
        "SELECT stored_filename FROM shared_drive_files WHERE folder_id=%s AND stored_filename LIKE 'zaloha\\_%%'",
        (folder_id,),
    )
    existing_filenames = {r["stored_filename"] for r in cur.fetchall()}

    slot_file = {}  # nazev slotu -> aktualni obsah (nazev souboru)
    for name, _interval, _source in RETENTION_TIERS:
        slot_file[name] = _get_setting(cur, f"backup_retention_{name}_file")

    for name, interval_days, source in RETENTION_TIERS:
        promo_key = f"backup_retention_{name}_promo_date"
        last_promo = _get_setting(cur, promo_key)
        due = last_promo is None or (today - datetime.date.fromisoformat(last_promo)).days >= interval_days
        if not due:
            continue
        if source == "daily-2":
            candidate = f"zaloha_{(today - datetime.timedelta(days=2)).isoformat()}.tar.gz"
        else:
            candidate = slot_file.get(source)
        if not candidate or candidate not in existing_filenames:
            continue  # jeste neni na co sahnout, zkusi se znovu zitra
        slot_file[name] = candidate
        _set_setting(cur, f"backup_retention_{name}_file", candidate)
        _set_setting(cur, promo_key, today.isoformat())

    keep = set(daily_keep)
    keep.update(f for f in slot_file.values() if f)
    return keep

def main():
    # Robert 2026-10-03 ("nastavit takto, zbytek mazat"): nocni zaloha je PRIRUSTKOVA (scripts/restic_backup.py, snimky na S3, retence 7 dni + 2 tydny);
    # stejny casovac konfigurator-daily-backup.timer ji jen spousti. Puvodni plny tar.gz + age zustava jako BACKUP_MODE=tar (rucni nouzova cesta).
    if os.environ.get("BACKUP_MODE", "restic") == "restic" and "--dry-run" not in sys.argv[1:]:
        restic = os.path.join(os.path.dirname(os.path.abspath(__file__)), "restic_backup.py")
        sys.exit(subprocess.run([sys.executable, restic] + sys.argv[1:]).returncode)
    env = load_env()
    dry_run = "--dry-run" in sys.argv[1:]
    today = datetime.date.today().isoformat()
    archive_name = f"zaloha_{today}.tar.gz"
    final_path = os.path.join(DRIVE_DIR, archive_name)

    # bot16, 2026-10-02: predsmazani + kontrola mista PRED dumpem a tarem (viz docstring nahore)
    pf = preflight(env, datetime.date.fromisoformat(today), dry_run)
    _vypis_preflight(pf, dry_run)
    if dry_run:
        print("DRY-RUN: nic se nezmenilo, retence se vratila zpet. " + ("Zaloha by zacala." if pf["ok"] else "Zaloha by NEZACALA (malo mista)."))
        sys.exit(0 if pf["ok"] else 2)
    if not pf["ok"]:
        _fail_space(env, archive_name, pf)

    with tempfile.TemporaryDirectory(prefix="konf_backup_", dir="/var/tmp") as staging:
        # 1) dump databaze (gzip)
        dump_path = os.path.join(staging, f"db_{env['DB_NAME']}_{today}.sql.gz")
        dump_cmd = [
            "mysqldump", "--single-transaction", "--quick", "--no-tablespaces",
            "--default-character-set=utf8mb4",
            "-h", env["DB_HOST"], "-P", env.get("DB_PORT", "3306"),
            "-u", env["DB_USER"], "-p" + env["DB_PASSWORD"], env["DB_NAME"],
        ]
        with gzip.open(dump_path, "wb") as gz:
            p = subprocess.Popen(dump_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            shutil.copyfileobj(p.stdout, gz)
            _, err = p.communicate(timeout=1800)
            if p.returncode != 0:
                print(f"CHYBA: mysqldump selhal: {err.decode(errors='replace')[:500]}", file=sys.stderr)
                sys.exit(1)
        print(f"DB dump: {os.path.getsize(dump_path) / 1e6:.1f} MB")

        # 2) systemova konfigurace
        cfg_dir = os.path.join(staging, "system-config")
        os.makedirs(cfg_dir, exist_ok=True)
        for src in (["/etc/nginx/sites-available/konfigurator"]
                    + glob.glob("/etc/systemd/system/konfigurator*")):
            if os.path.isfile(src):
                shutil.copy2(src, os.path.join(cfg_dir, os.path.basename(src)))

        # 3) tar archiv (docasne ve stagingu, pak presun na Sdileny disk)
        tmp_archive = os.path.join(staging, archive_name)
        tar_cmd = [
            "tar", "czf", tmp_archive,
            "--exclude=konfigurator/api/venv",
            "--exclude=konfigurator/api/step_venv",
            "--exclude=__pycache__",
            "--exclude=konfigurator/api/konfigurator.sock",
            # predchozi zalohy (soubor prave vznikajici je ve stagingu, ne tady)
            "--exclude=konfigurator/private-files/shared-drive/zaloha_*",
            "-C", os.path.dirname(PROJECT_ROOT), "konfigurator",
            "-C", staging, os.path.basename(dump_path), "system-config",
        ]
        p = subprocess.run(tar_cmd, capture_output=True, text=True, timeout=3600)
        # tar vraci 1 pri "file changed as we read it" (zivy system) - to
        # neni fatalni; fatalni je jen rc >= 2
        if p.returncode >= 2:
            print(f"CHYBA: tar selhal (rc={p.returncode}): {p.stderr[:500]}", file=sys.stderr)
            sys.exit(1)
        size = os.path.getsize(tmp_archive)
        print(f"Archiv: {size / 1e6:.1f} MB")

        os.makedirs(DRIVE_DIR, exist_ok=True)
        shutil.move(tmp_archive, final_path)
        shutil.chown(final_path, "www-data", "www-data")

    # 4) registrace na Sdilenem disku + retence
    conn = db_connect(env)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM shared_drive_folders WHERE parent_folder_id IS NULL AND name=%s",
                (BACKUP_FOLDER_NAME,),
            )
            row = cur.fetchone()
            if row:
                folder_id = row["id"]
            else:
                cur.execute(
                    "INSERT INTO shared_drive_folders (parent_folder_id, name, created_by) VALUES (NULL,%s,NULL)",
                    (BACKUP_FOLDER_NAME,),
                )
                folder_id = cur.lastrowid

            # stejny den znovu = nahradit (zadne duplicitni radky)
            cur.execute(
                "SELECT id FROM shared_drive_files WHERE folder_id=%s AND stored_filename=%s",
                (folder_id, archive_name),
            )
            existing = cur.fetchone()
            if existing:
                cur.execute(
                    "UPDATE shared_drive_files SET size_bytes=%s, created_at=NOW() WHERE id=%s",
                    (size, existing["id"]),
                )
            else:
                cur.execute(
                    "INSERT INTO shared_drive_files (folder_id, filename, stored_filename, content_type, size_bytes, uploaded_by) "
                    "VALUES (%s,%s,%s,'application/gzip',%s,NULL)",
                    (folder_id, archive_name, archive_name, size),
                )

            # retence: odstupnovana rotace (viz docstring nahore)
            today_date = datetime.date.fromisoformat(today)
            keep_filenames = _run_retention(cur, folder_id, today_date)

            cur.execute(
                "SELECT id, stored_filename FROM shared_drive_files "
                "WHERE folder_id=%s AND stored_filename LIKE 'zaloha\\_%%'",
                (folder_id,),
            )
            for old in cur.fetchall():
                if old["stored_filename"] in keep_filenames:
                    continue
                path = os.path.join(DRIVE_DIR, old["stored_filename"])
                try:
                    os.remove(path)
                except OSError:
                    pass
                cur.execute("DELETE FROM shared_drive_files WHERE id=%s", (old["id"],))
                print(f"Retence: smazana stara zaloha {old['stored_filename']}")
        conn.commit()
    finally:
        conn.close()

    print(f"HOTOVO: {archive_name} ({size / 1e6:.1f} MB) ve slozce '{BACKUP_FOLDER_NAME}' na Sdilenem disku")

    upload_offsite(final_path, archive_name, env)

if __name__ == "__main__":
    main()
