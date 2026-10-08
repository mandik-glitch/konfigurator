"""Vyber stroje pro renderovaci automaty (bot4 2026-09-30).

Robert 2026-09-30 ("Ma automat cilit i na notebook Omen?" - "ano"): automat (nativni
2026-09-14_render_auto_dispatch.py i Vandr 2026-09-23_vandr_render_auto_dispatch.py) smi zaradit ulohu
i na DALSI stroj (notebook s renderovacim agentem), ne jen na vychozi GPU stanici Logiman2.

PRAVIDLO (vyber_stroj_pro_automat):
  * Vychozi stroj (Logiman2) ma prednost: kdyz je online, volny a neprehraty, uloha jde na nej beze
    zmeny (bez --worker), jako dosud.
  * Dalsi stroj POMAHA: uloha jde na nej jen kdyz je vychozi stroj vytizeny (neco na nem bezi nebo ceka),
    prehraty nebo offline - a dalsi stroj je soucasne
      - online (tep do 90 s, agent si chodi pro praci),
      - s agentem, ktery hlasi Blender >= 5.2 (starsi agent/Blender sablonu neprecte, "not a blend file"),
      - volny (nic na nem nebezi ani na nej necha cilenou ulohu - vcetne Robertovych testu),
      - neprehraty (gpu_temp_c pod prahem),
      - bez chyby v poslednich PAUZA_PO_CHYBE_S (selhala-li cilena uloha, stroj si odpocine; stav ulohy
        v `error` zustava videt minimalne hodinu, viz api/blender_render.py::JOB_RETENTION_S).
  * Stroj pro NABIDKY a testy ze sceny (NABIDKY_JMENO, dnes Omen) je pro automat VYHRAZENY a nevybere se nikdy,
    ani kdyz je volny a Logiman2 vytizeny (bot4 2026-10-01, Robert pres bot5: "Online nabidky se musi renderovat
    na Omen"). Proc: nabidku ceka clovek a agent bere ulohy FIFO po jedne - kdyby na stroji bezela otocka na
    desitky minut, nabidka by cekala za ni (nebo spadla na Logiman2, kde ceka za dalsi otockou). Stejna promenna
    jako na serveru (api/render_worker.py::NABIDKY_STROJ): prazdna = stroj neni vyhrazeny a server nabidky
    nesmeruje - jedno nastaveni resi obe strany.
  * Kdyz nic z toho neplati, vysledek je None = vychozi stroj (uloha pocka ve fronte jako dosud).
  * Vypnout notebook pro automat = vypnout jeho agenta (offline stroj se nikdy nevybere).

Cilena uloha (`--worker JMENO` v 2026-09-09_turntable_render.py) se NIKDY neprevezme jinym strojem ani
serverem (CPU) - kdyz se notebook po zarazeni odmlci, server ulohu po 10 min uzavre chybou
(api/render_worker.py::uklidit_mrtve_ulohy_workera) a dalsi beh automatu ji zaradi znovu.

Modul nic nezapisuje ani nemeni: cte jen soubory v private-files/blender-renders (tepy agentu a
*.status.json uloh), stejne jako scripts/2026-09-09_turntable_status.py. Konstanty ONLINE_S/POLL_STALE_S/
prahy se shodou s kodem serveru hlida test_vyber_stroje.py (scripts/2026-09-30_render_panel_testy).
"""
import glob
import json
import os
import re
import time

REPO = os.path.dirname(os.path.abspath(__file__)).rsplit(os.sep + "scripts", 1)[0]
RENDER_OUT_DIR = os.path.join(REPO, "private-files", "blender-renders")

# jmeno vychoziho stroje: stejna promenna a vychozi hodnota jako api/render_worker.py::WORKER_VYCHOZI_JMENO
VYCHOZI_JMENO = (os.environ.get("RENDER_WORKER_VYCHOZI") or "Logiman2").strip() or "Logiman2"
ONLINE_S = 90           # = api/render_worker.py::WORKER_ONLINE_S (tep cerstvejsi nez tohle)
POLL_STALE_S = 180      # = api/render_worker.py::WORKER_POLL_STALE_S (agent si chodi pro praci)
MIN_BLENDER = (5, 2)    # sablona renderu je ulozena v Blenderu 5.2.x; starsi ji neprecte
PRAH_TEPLOTA_C = 80.0   # = _render_health_config.PRAH_GPU_TEPLOTA_C (stejny prah jako teplotni brzda)
PAUZA_PO_CHYBE_S = 3000  # < api/blender_render.py::JOB_RETENTION_S (3600): chybova uloha je po celou pauzu videt
# stroj vyhrazeny pro rendery nabidek a testu ze sceny (automat ho nepouzije): stejna promenna a vychozi hodnota
# jako api/render_worker.py::NABIDKY_STROJ (obe strany berou prostredi z api/.env)
NABIDKY_JMENO = os.environ.get("RENDER_NABIDKY_STROJ", "Omen").strip()


def _klic(jmeno):
    return (jmeno or "").strip().lower()


def _cti_json(cesta):
    try:
        with open(cesta, "r", encoding="utf-8") as fh:
            d = json.load(fh)
        return d if isinstance(d, dict) else None
    except (OSError, ValueError):
        return None


def nacti_stavy_uloh(out_dir=None):
    """[stav, ...] vsech *.status.json (poskozene/necitelne se preskoci)."""
    out_dir = out_dir or RENDER_OUT_DIR
    stavy = []
    try:
        names = os.listdir(out_dir)
    except OSError:
        return stavy
    for n in names:
        if n.endswith(".status.json"):
            st = _cti_json(os.path.join(out_dir, n))
            if st:
                stavy.append(st)
    return stavy


def _verze_blenderu(gpu):
    """(major, minor) z retezce `... | Blender 5.2.1` v `gpu` tepu agenta, jinak None."""
    m = re.search(r"Blender\s+(\d+)\.(\d+)", gpu or "")
    return (int(m.group(1)), int(m.group(2))) if m else None


def patri_stroji(st, jmeno, je_vychozi):
    """Zabira uloha `st` (cekajici nebo bezici na workerovi) stroj `jmeno`? Stejna pravidla jako server:
    uloha s cilem jde JEN tomu stroji, uloha bez cile JEN vychozimu; bezici se pozna podle worker_name
    (chybejici = vychozi stroj, starsi ulohy)."""
    stav = st.get("state")
    if stav == "waiting_worker":
        cil = st.get("target_worker")
        return (_klic(cil) == _klic(jmeno)) if cil else je_vychozi
    if stav == "running" and st.get("on_worker"):
        wn = st.get("worker_name")
        return (_klic(wn) == _klic(jmeno)) if wn else je_vychozi
    return False


def zatizeni(jmeno, je_vychozi, stavy):
    return sum(1 for st in stavy if patri_stroji(st, jmeno, je_vychozi))


def je_vyhrazen(jmeno):
    """Je stroj vyhrazeny pro nabidky a testy ze sceny? (vychozi stroj nikdy: ten je pro produkci)"""
    return bool(NABIDKY_JMENO) and _klic(jmeno) == _klic(NABIDKY_JMENO) and _klic(jmeno) != _klic(VYCHOZI_JMENO)


def posledni_chyba_ts(jmeno, stavy):
    """Cas poslednich chybove ukoncene ulohy CILENE na tenhle stroj (0 = zadna)."""
    t = 0.0
    for st in stavy:
        if st.get("state") == "error" and _klic(st.get("target_worker")) == _klic(jmeno):
            t = max(t, float(st.get("updated") or 0))
    return t


def nacti_stroje(out_dir=None, ted=None, stavy=None):
    """Vsechny znamé stroje: [{jmeno, vychozi, online, duvod, blender, teplota_c, gpu}], vychozi prvni.
    `online` stejne jako api/render_worker.py::stav_workeru (tep cerstvy A agent si chodi pro praci,
    nebo prave renderuje)."""
    out_dir = out_dir or RENDER_OUT_DIR
    ted = time.time() if ted is None else ted
    stavy = nacti_stavy_uloh(out_dir) if stavy is None else stavy
    soubory = [(os.path.join(out_dir, ".worker_heartbeat.json"), True)]
    for cesta in sorted(glob.glob(os.path.join(out_dir, ".worker_heartbeat.*.json"))):
        soubory.append((cesta, False))
    stroje, videna = [], set()
    for cesta, vychozi in soubory:
        hb = _cti_json(cesta) or {}
        jmeno = VYCHOZI_JMENO if vychozi else (hb.get("name") or "").strip()
        if not jmeno or _klic(jmeno) in videna:
            continue
        if not vychozi and _klic(jmeno) == _klic(VYCHOZI_JMENO):
            continue   # tep vychoziho stroje pod jinym souborem - ignorovat
        videna.add(_klic(jmeno))
        online, duvod = True, None
        if not hb:
            online, duvod = False, "nikdy se nepripojil"
        elif ted - float(hb.get("ts") or 0) >= ONLINE_S:
            online, duvod = False, "nehlasi se %d min" % max(1, int((ted - float(hb.get("ts") or 0)) // 60))
        else:
            od = hb.get("poll_ts") or hb.get("poll_missing_since") or 0
            if od and ted - float(od) > POLL_STALE_S:
                bezi = any(st.get("state") == "running" and st.get("on_worker")
                           and (_klic(st.get("worker_name")) == _klic(jmeno)
                                or (vychozi and not st.get("worker_name"))) for st in stavy)
                if not bezi:
                    online, duvod = False, "agent tepe, ale nebere si praci (zaseknuty)"
        teplota = hb.get("gpu_temp_c")
        try:
            teplota = float(teplota) if teplota is not None else None
        except (TypeError, ValueError):
            teplota = None
        stroje.append({"jmeno": jmeno, "vychozi": vychozi, "online": online, "duvod": duvod,
                       "blender": _verze_blenderu(hb.get("gpu")), "teplota_c": teplota, "gpu": hb.get("gpu")})
    return stroje


def vyber_stroj_pro_automat(vyloucene=(), out_dir=None, ted=None):
    """(cil, popis): cil = jmeno stroje pro `--worker`, nebo None = vychozi stroj (bez --worker).
    Nikdy nevyhodi vyjimku - kdykoli se neco pokazi, vychozi stroj (chovani jako pred tim)."""
    try:
        return _vyber(vyloucene, out_dir, ted)
    except Exception as e:   # noqa: BLE001 - vyber stroje nesmi shodit automat
        return None, "%s (vyber dalsiho stroje selhal: %s)" % (VYCHOZI_JMENO, e)


def _vyber(vyloucene, out_dir, ted):
    ted = time.time() if ted is None else ted
    stavy = nacti_stavy_uloh(out_dir)
    stroje = nacti_stroje(out_dir, ted, stavy)
    vyl = {_klic(v) for v in (vyloucene or ())}
    vychozi = next((s for s in stroje if s["vychozi"]), None)
    vychozi_horky = bool(vychozi and vychozi["online"] and vychozi["teplota_c"] is not None
                         and vychozi["teplota_c"] >= PRAH_TEPLOTA_C)
    vychozi_volny = bool(vychozi and vychozi["online"] and not vychozi_horky
                         and zatizeni(vychozi["jmeno"], True, stavy) == 0)
    volne, duvody = [], []
    for s in stroje:
        if s["vychozi"]:
            continue
        j = s["jmeno"]
        if _klic(j) in vyl:
            duvody.append("%s: vyloucen" % j)
        elif je_vyhrazen(j):
            duvody.append("%s: vyhrazen pro nabidky a testy ze sceny" % j)
        elif not s["online"]:
            duvody.append("%s: offline (%s)" % (j, s["duvod"]))
        elif s["blender"] is None or s["blender"] < MIN_BLENDER:
            duvody.append("%s: agent nehlasi Blender >= %d.%d (%s)" % (
                j, MIN_BLENDER[0], MIN_BLENDER[1],
                "%d.%d" % s["blender"] if s["blender"] else "starsi agent bez verze"))
        elif s["teplota_c"] is not None and s["teplota_c"] >= PRAH_TEPLOTA_C:
            duvody.append("%s: prehraty (%.0f C)" % (j, s["teplota_c"]))
        elif zatizeni(j, False, stavy) > 0:
            duvody.append("%s: ma praci" % j)
        elif ted - posledni_chyba_ts(j, stavy) < PAUZA_PO_CHYBE_S:
            duvody.append("%s: odpociva po chybe ulohy" % j)
        else:
            volne.append(s)
    if not volne:
        return None, "%s%s" % (VYCHOZI_JMENO, (" (dalsi stroje: " + "; ".join(duvody) + ")") if duvody else "")
    if vychozi_volny:
        return None, "%s je volny, notebook jen pomaha, kdyz je vytizeny" % VYCHOZI_JMENO
    nejlepsi = sorted(volne, key=lambda s: _klic(s["jmeno"]))[0]
    if not vychozi or not vychozi["online"]:
        proc = "%s je offline" % VYCHOZI_JMENO
    elif vychozi_horky:
        proc = "%s je prehraty (%.0f C)" % (VYCHOZI_JMENO, vychozi["teplota_c"])
    else:
        proc = "%s je vytizeny" % VYCHOZI_JMENO
    return nejlepsi["jmeno"], "%s volny a pomaha, protoze %s" % (nejlepsi["jmeno"], proc)


def popis_stroju(out_dir=None, ted=None):
    """Radky pro vypis (dry-run automatu): stav kazdeho znameho stroje."""
    ted = time.time() if ted is None else ted
    stavy = nacti_stavy_uloh(out_dir)
    radky = []
    for s in nacti_stroje(out_dir, ted, stavy):
        radky.append("%s%s: %s, prace %d%s%s%s" % (
            s["jmeno"], " (vychozi)" if s["vychozi"] else "", "online" if s["online"] else "offline (%s)" % s["duvod"],
            zatizeni(s["jmeno"], s["vychozi"], stavy),
            ", Blender %d.%d" % s["blender"] if s["blender"] else ", Blender neznamy",
            ", %.0f C" % s["teplota_c"] if s["teplota_c"] is not None else "",
            ", VYHRAZEN pro nabidky a testy (automat ho nepouzije)" if je_vyhrazen(s["jmeno"]) else ""))
    return radky


if __name__ == "__main__":     # rucni diagnostika: python3 scripts/_render_stroje.py
    for r in popis_stroju():
        print(r)
    cil, popis = vyber_stroj_pro_automat()
    print("automat by ted zaradil na: %s (%s)" % (cil or VYCHOZI_JMENO + " [vychozi, bez --worker]", popis))
