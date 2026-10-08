#!/bin/bash
# Bezpecny obal nad `systemctl restart konfigurator` (bot15, 2026-09-03,
# Robert pres bot3: "disciplina zamku je porad slabina").
#
# DUVOD: `systemctl restart` nastartuje gunicorn nad tim, co PRAVE LEZI NA
# DISKU, bez ohledu na git. Zamek (DEPLOY_LOCK.json + pre-commit hook)
# chrani jen COMMIT, ne restart - takze restart umi nasadit necommitnutou
# praci, kterou nikdo nasadit nechtel.
#
# SLEPA SKVRNA, KVULI KTERE SE SKRIPT 2026-09-11 PREPSAL:
# puvodni verze rozhodovala JEN podle drzeni zamku - "drzis zamek =
# vsechny spinave guarded soubory jsou tvoje". To neplati. Bot9 v noci
# restartoval, drzel zamek, a skript mu odmavl jednou vetou "restartujes
# s VLASTNIMI necommitnutymi zmenami"; ve skutecnosti v
# api/blender_render_scene.py lezela CIZI rozdelana prace a restart ji
# nasadil naZivo. Nic se nerozbilo, ale nasadilo se neco, co nikdo
# nasadit nechtel - a to je presne ten incident, proti kteremu skript
# vznikl. Nechranil pred nim prave ve chvili, kdy restartuje drzitel
# zamku - tedy v tom NEJCASTEJSIM pripade, protoze zamek si bere kazdy,
# kdo neco meni.
#
# JAK SE TO POZNA TED: git o autorovi NECOMMITNUTE zmeny nevi nic, takze
# se pouziva CAS. DEPLOY_LOCK.json nese `since` (kdy sis zamek vzal).
# Soubor zmeneny PO tom case je skoro jiste tvoje prace; soubor zmeneny
# DRIV je podezrely - lezel tam uz kdyz sis zamek bral.
#
# Je to signal, ne dukaz: bezny postup "nachystam zmenu -> vezmu zamek ->
# commitnu" da mtime PRED zamkem taky. Proto se takovy soubor NEBLOKUJE,
# jen se VYPISE zvlast i s tim, kdo ho naposledy commitnul - a v
# terminalu se skript zepta. Cilem je ROZLISIT, ne zakazat: restart
# aplikace potrebuje behem noci pet botu a prisnost na cokoli spinaveho
# by zastavila praci vsem.
#
# DRUHA SLEPA SKVRNA (bot9, 2026-09-11, nalez bot8): restart tise zabije
# BEZICI LOKALNI RENDER. Lokalni (CPU) render nebezi jako samostatny
# proces, ale UVNITR gunicornu - `systemctl restart` ho tedy sestreli
# spolu se sluzbou. Stalo se to tyz den: uloha skoncila se stavem "Render
# byl preruseny restartem serveru" a prislo se o 13 minut CPU; u plne
# davky (162 snimku) by to byly ~3 hodiny.
#
# Skript proto pred restartem hleda bezici lokalni ulohu a rekne, CO se
# zahazuje - cislo ulohy, sestavu, jak dlouho bezi a kolik snimku uz je
# hotovych. Podle toho jde poznat, jestli se obetuje minuta nebo tri
# hodiny. Poznavaci znamka: lokalni uloha ma ve stavu `pid` a NEMA
# `on_worker` (GPU uloha bezi na Robertove stanici a restart ji nevadi).
#
# Kontrola je zamerne UVNITR funkce restartuj(), ne pred jejim prvnim
# volanim - k restartu vede vic vetvi a takhle nejde zadnou minout.
#
# Pouziti:
#   scripts/restart_konfigurator.sh --tvrdy      # kontrola + TVRDY restart (od 2026-10-05 JEDINA cesta k nemu: holy beh ani neznamy prepinac nic nerestartuje)
#   scripts/restart_konfigurator.sh --help       # vypis pouziti (exit 0); neznamy prepinac = chyba (exit 2), nic se nespusti
#   scripts/restart_konfigurator.sh --tvrdy --force   # preskoci odmitnuti i dotaz
#   scripts/restart_konfigurator.sh --jen-moje   # odmitne, kdyz je tam CIZI soubor
#                                                # (i kdyz drzis zamek)
#   scripts/restart_konfigurator.sh --zkouska    # jen verdikt, nerestartuje
#   scripts/restart_konfigurator.sh --reload     # kontroly + NASAZENI BEZ VYPADKU (gunicorn HUP) misto restartu
#   scripts/restart_konfigurator.sh --planovane  # JEN pro systemd timer konfigurator-nasazeni (0:00 a 12:30)
#   scripts/restart_konfigurator.sh --stav       # kdy pujde kod ven, co ceka, posledni nasazeni, co blokuje
#
# PLANOVANE NASAZENI (bot16, 2026-10-01, Robert pres bot3: "uz me nebavi delat
# restart"): kod z api/*.py jde na ostro 2x denne, v 0:00 a 12:30 (Europe/Prague; nocni termin presunut z 3:30 na pulnoc 2026-10-04, aby nebezel v dobe zaloh),
# BEZ VYPADKU - gunicorn HUP misto restartu (zadny pozadavek nespadne, po dobu
# nabehu ~4 s obsluha jen ceka). Nasazuje se jen COMMITNUTE; necommitnuta zmena
# v api/*.py planovane nasazeni zablokuje a vypise se, ktery soubor to je. Bot
# proto neresetuje ad hoc: commitne a pocka na nejblizsi termin (`--stav` ukaze
# kdy). Logika: scripts/nasazeni.py (cela dokumentace je v jeho hlavicce).
# `--reload` je vyjimka pro NALEHAVOU opravu: stejne kontroly jako restart nize
# (necommitnute, lokalni render), ale misto restartu HUP + kontroly po nasazeni.
# Tvrdy restart (`--tvrdy`) ZUSTAVA pro zmeny, ktere HUP nenacte: api/.env,
# konfigurator.service (parametry gunicornu), zmena venv/Pythonu.
#
# INCIDENT 2026-10-05 10:16 (nalez bot8, bot9): `restart_konfigurator.sh --help` neznamy prepinac IGNOROVAL a provedl TVRDY restart (vypadek ~3 s, nginx 502, zabiti
# bezici lokalni render). Proto: jeden povinny REZIM (--stav, --reload, --planovane, --tvrdy), neznamy prepinac a chybejici rezim koncí chybou (exit 2) bez jakekoli akce.

set -euo pipefail

REPO_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$REPO_ROOT"

FORCE=0
JEN_MOJE=0
ZKOUSKA=0
RELOAD=0
PLANOVANE=0
STAV=0
TVRDY=0

pouziti() {
  cat <<'USAGE'
Pouziti: scripts/restart_konfigurator.sh <rezim> [modifikatory]

Rezimy (prave JEDEN je povinny - bez nej se NIC nespusti a nic nerestartuje):
  --stav        kdy pujde kod ven, co ceka, posledni nasazeni, co blokuje (jen cteni)
  --reload      nasazeni BEZ vypadku (gunicorn HUP) po kontrolach - pro NALEHAVOU opravu
  --planovane   JEN pro systemd timer konfigurator-nasazeni (0:00 a 12:30)
  --tvrdy       TVRDY restart sluzby: vypadek ~3 s (nginx 502), zabije bezici lokalni render;
                jen pro zmeny, ktere HUP nenacte (api/.env, konfigurator.service, venv)
Modifikatory:
  --zkouska     (nebo --dry-run) jen verdikt kontrol, nic nespusti
  --force       preskoci odmitnuti a dotazy (necommitnute soubory, bezici render)
  --jen-moje    odmitne, kdyz je v guarded souborech CIZI necommitnuta zmena (i kdyz drzis zamek)
  -h, --help    tento vypis (exit 0)
Neznamy prepinac nebo chybejici rezim = chyba (exit 2), nic se nespusti.
USAGE
}

for arg in "$@"; do
  case "$arg" in
    -h|--help) pouziti; exit 0 ;;
    --force) FORCE=1 ;;
    --jen-moje) JEN_MOJE=1 ;;
    --zkouska|--dry-run) ZKOUSKA=1 ;;
    --reload) RELOAD=1 ;;
    --planovane) PLANOVANE=1 ;;
    --stav) STAV=1 ;;
    --tvrdy) TVRDY=1 ;;
    *) echo "CHYBA: neznamy prepinac '$arg' - nic se nespustilo, nic se nerestartovalo." >&2; echo "" >&2; pouziti >&2; exit 2 ;;
  esac
done
POCET_REZIMU=$((STAV + RELOAD + PLANOVANE + TVRDY))
if [ "$POCET_REZIMU" -eq 0 ]; then
  echo "CHYBA: chybi rezim (--stav, --reload, --planovane nebo --tvrdy) - nic se nespustilo, nic se nerestartovalo." >&2
  echo "       (Od 2026-10-05 holy beh bez prepinace uz NErestartuje; tvrdy restart je vyslovne --tvrdy.)" >&2
  echo "" >&2; pouziti >&2; exit 2
fi
if [ "$POCET_REZIMU" -gt 1 ]; then
  echo "CHYBA: rezimy --stav / --reload / --planovane / --tvrdy se vzajemne vylucuji - nic se nespustilo." >&2
  echo "" >&2; pouziti >&2; exit 2
fi

# Planovane nasazeni a stav bezi cele v scripts/nasazeni.py (vlastni, prisnejsi
# kontroly - viz jeho hlavicka), proto SE PRED interaktivni logikou nize.
NASAZENI_PY="$REPO_ROOT/api/venv/bin/python3"
NASAZENI_SKRIPT="$REPO_ROOT/scripts/nasazeni.py"
if [ "$STAV" = "1" ]; then
  exec "$NASAZENI_PY" "$NASAZENI_SKRIPT" --stav
fi
if [ "$PLANOVANE" = "1" ]; then
  if [ "$ZKOUSKA" = "1" ]; then
    exec "$NASAZENI_PY" "$NASAZENI_SKRIPT" --planovane --zkouska
  fi
  exec "$NASAZENI_PY" "$NASAZENI_SKRIPT" --planovane
fi

# Bezi lokalni (CPU) render, ktery by restart zabil? Viz "DRUHA SLEPA
# SKVRNA" v hlavicce. RENDER_DIR jde prepsat promennou prostredi - jen
# kvuli testovatelnosti teto kontroly bez zasahu do ostre fronty.
zkontroluj_lokalni_render() {
  [ "$FORCE" = "1" ] && return 0
  local RENDER_DIR="${RESTART_RENDER_DIR:-$REPO_ROOT/private-files/blender-renders}"
  local NALEZ
  # Selhani teto kontroly NESMI shodit restart - kdyz stav nejde precist,
  # chovame se, jako by nic nebezelo, a rekneme, ze se to neoverilo.
  NALEZ=$(RENDER_DIR="$RENDER_DIR" python3 - <<'PY' 2>/dev/null || true
import glob, json, os, time

d = os.environ["RENDER_DIR"]
radky = []
for f in sorted(glob.glob(os.path.join(d, "*.status.json"))):
    try:
        with open(f, encoding="utf-8") as fh:
            st = json.load(fh)
    except (OSError, ValueError):
        continue
    # LOKALNI = bezi uvnitr gunicornu (ma pid, nema on_worker).
    # GPU uloha (on_worker) bezi na jine stanici a restart ji nevadi.
    if st.get("state") not in ("running", "queued") or st.get("on_worker"):
        continue
    job = os.path.basename(f)[: -len(".status.json")]
    bezi = ""
    if st.get("started"):
        m = int((time.time() - st["started"]) // 60)
        bezi = " | bezi %d min" % m
    hotovo = ""
    try:
        n = len(glob.glob(os.path.join(d, job + ".frames", "*.jpg")))
        if n:
            hotovo = " | hotovo %d/%s snimku" % (n, st.get("expected_frames") or "?")
    except OSError:
        pass
    radky.append("  %s | sestava %s | stav %s%s%s"
                 % (job[:12], st.get("assembly_id"), st.get("state"), bezi, hotovo))
print("\n".join(radky))
PY
  )

  [ -z "$NALEZ" ] && return 0

  echo "" >&2
  echo "======================================================" >&2
  echo "POZOR: bezi LOKALNI render, ktery restart ZABIJE." >&2
  echo "Lokalni render bezi uvnitr gunicornu, takze ho restart sluzby" >&2
  echo "sestreli i s ni. Prijdes o odpracovany cas, ne jen o frontu:" >&2
  echo "$NALEZ" >&2
  echo "======================================================" >&2

  if [ -t 0 ]; then
    read -r -p "Opravdu restartovat a zahodit to? [a/N] " ODPOVED_RENDER
    case "$ODPOVED_RENDER" in
      a|A|y|Y|ano|ANO) ;;
      *) echo "Restart zrusen." >&2; exit 1 ;;
    esac
  else
    echo "(neinteraktivni beh - pokracuji, ale vis o tom. --force preskoci" >&2
    echo " i tuhle kontrolu.)" >&2
  fi
}

# Suchy beh: projde celou kontrolu a vypise verdikt, ale NErestartuje.
# Diky nemu jde skript overit i ve chvili, kdy na disku lezi rozdelana
# prace, kterou nasadit nechceme.
restartuj() {
  zkontroluj_lokalni_render
  if [ "$ZKOUSKA" = "1" ]; then
    if [ "$RELOAD" = "1" ]; then
      echo "[zkouska] reload (bez vypadku) by probehl (bez --zkouska)" >&2
    else
      echo "[zkouska] restart by probehl (bez --zkouska)" >&2
    fi
    exit 0
  fi
  if [ "$RELOAD" = "1" ]; then
    # Kontroly vyse (necommitnute, lokalni render) uz probehly a volajici se
    # rozhodl -> nasazeni.py bezi s --force (kontroly nedela podruhe), ale
    # preflight, HUP, kontroly po nasazeni a zapis do deploy_runs zustavaji.
    exec "$NASAZENI_PY" "$NASAZENI_SKRIPT" --rucni --force
  fi
  if [ "$TVRDY" != "1" ]; then echo "INTERNI CHYBA: tvrdy restart bez --tvrdy - nic se nerestartovalo." >&2; exit 2; fi
  echo "TIP: tohle je TVRDY restart a kratky vypadek (nginx vraci 502). Nasazeni BEZ vypadku: --reload." >&2
  echo "     Bezne se nasazuje samo 2x denne (0:00 a 12:30); kdy pujde tvuj commit ven, ukaze --stav." >&2
  exec sudo systemctl restart konfigurator
}

# jen SLEDOVANE (tracked) soubory - untracked (??) je v tomhle repu
# chronicky velka hromada binarnich assetu (webapp/katalog/*.glb...),
# co nikdy nebyly pridane do gitu a nesouvisi s kodovou zmenou; kdyby
# se pocitaly, kontrola by blokovala furt, ne jen pri skutecne kolizi.
GUARDED_DIRTY=$(git status --porcelain -- webapp/ 'api/*.py' 2>/dev/null | grep -v '^??' || true)

if [ -z "$GUARDED_DIRTY" ]; then
  restartuj
fi

# Klasifikace spinavych souboru: TVOJE (zmenene po vzeti zamku) vs CIZI
# (lezely tam uz driv). Vraci shell promenne k eval.
eval "$(BOT_ID="${BOT_ID:-}" python3 - <<'PY'
import json, os, subprocess, shlex, datetime

def sh(v):
    return shlex.quote(str(v))

me = os.environ.get("BOT_ID") or ""
held_by, since_epoch = "", None
try:
    with open("DEPLOY_LOCK.json") as f:
        d = json.load(f)
    held_by = d.get("held_by") or ""
    since = d.get("since")
    if since:
        # ISO 8601 s offsetem ("2026-09-11T01:02:03+02:00")
        since_epoch = datetime.datetime.fromisoformat(since).timestamp()
except Exception:
    pass

out = subprocess.run(["git", "status", "--porcelain", "--", "webapp/", "api/*.py"],
                     capture_output=True, text=True).stdout
moje, cizi = [], []
for radek in out.splitlines():
    if not radek or radek.startswith("??"):
        continue
    cesta = radek[3:]
    if " -> " in cesta:          # prejmenovani: "R  stare -> nove"
        cesta = cesta.split(" -> ", 1)[1]
    cesta = cesta.strip().strip('"')
    try:
        mtime = os.path.getmtime(cesta)
    except OSError:
        # smazany soubor - autorstvi nepoznam, radsi mezi podezrele
        cizi.append((cesta, None, ""))
        continue
    # Kdo soubor naposledy commitnul - neni to autor rozdelane zmeny, ale
    # pomuze poznat, ci prace to nejspis je.
    try:
        posledni = subprocess.run(
            ["git", "log", "-1", "--format=%an", "--", cesta],
            capture_output=True, text=True, timeout=5).stdout.strip()
    except Exception:
        posledni = ""
    if since_epoch is not None and held_by and held_by == me and mtime >= since_epoch:
        moje.append((cesta, mtime, posledni))
    else:
        cizi.append((cesta, mtime, posledni))

def formatuj(polozky):
    radky = []
    for cesta, mtime, posledni in polozky:
        cas = datetime.datetime.fromtimestamp(mtime).strftime("%H:%M:%S") if mtime else "(smazan)"
        kdo = (" - naposledy commitnul: %s" % posledni) if posledni else ""
        radky.append("  %-46s zmeneno %s%s" % (cesta, cas, kdo))
    return "\n".join(radky)

print("HELD_BY=%s" % sh(held_by))
print("SINCE_HUMAN=%s" % sh(
    datetime.datetime.fromtimestamp(since_epoch).strftime("%H:%M:%S") if since_epoch else ""))
print("POCET_MOJE=%s" % sh(len(moje)))
print("POCET_CIZI=%s" % sh(len(cizi)))
print("SEZNAM_MOJE=%s" % sh(formatuj(moje)))
print("SEZNAM_CIZI=%s" % sh(formatuj(cizi)))
PY
)"

ME="${BOT_ID:-}"

# Vsechno spinave vzniklo az po vzeti zamku a zamek je tvuj -> tvoje prace.
if [ "$POCET_CIZI" = "0" ]; then
  echo "UPOZORNENI: restartujes s vlastnimi necommitnutymi zmenami (zamek '$ME' od $SINCE_HUMAN):" >&2
  echo "$SEZNAM_MOJE" >&2
  restartuj
fi

# Neco tam lezelo uz pred zamkem (nebo zamek nedrzis ty).
echo "" >&2
echo "======================================================" >&2
echo "POZOR: mezi necommitnutymi zmenami je prace, ktera podle vseho NENI tvoje" >&2
echo "(BOT_ID='${ME:-<chybi>}', zamek drzi: '${HELD_BY:-<nikdo>}'${SINCE_HUMAN:+ od $SINCE_HUMAN})." >&2
echo "" >&2
echo "Zmenene UZ PRED tim, nez sis vzal zamek (nebo bez zamku):" >&2
echo "$SEZNAM_CIZI" >&2
if [ "$POCET_MOJE" != "0" ]; then
  echo "" >&2
  echo "Tvoje vlastni (zmenene az po vzeti zamku):" >&2
  echo "$SEZNAM_MOJE" >&2
fi
echo "" >&2
echo "Restart nasadi VSECHNO vyse na zivou sluzbu, vcetne ciziho." >&2
echo "Cas zmeny je jen VODITKO - kdyz sis soubor upravil jeste pred" >&2
echo "vzetim zamku, vyjde taky jako 'cizi'. Podivej se na 'git diff'," >&2
echo "jestli to poznavas." >&2
echo "======================================================" >&2

if [ "$JEN_MOJE" = "1" ]; then
  echo "RESTART ODMITNUT (--jen-moje)." >&2
  exit 1
fi

if [ "$FORCE" = "1" ]; then
  echo "Pokracuji pres --force." >&2
  restartuj
fi

# V terminalu se zeptej; v neinteraktivnim behu (bot, cron) NEBLOKUJ -
# restart aplikace potrebuje behem noci pet botu a odmitnuti by zastavilo
# praci vsem. Varovani vyse uz proslo do logu, takze je dohledatelne.
if [ -t 0 ]; then
  read -r -p "Restartovat i tak? [a/N] " ODPOVED
  case "$ODPOVED" in
    a|A|y|Y|ano|ANO) ;;
    *) echo "Restart zrusen." >&2; exit 1 ;;
  esac
else
  echo "(neinteraktivni beh - pokracuji, ale vis o tom. Kdyz chces tvrde" >&2
  echo " odmitnuti, spust s --jen-moje.)" >&2
fi

restartuj
