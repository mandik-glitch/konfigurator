# Vyber stroje pro render automaty (scripts/_render_stroje.py): automat smi zaradit ulohu i na notebook (Omen).
# Bez DB, bez Blenderu, bez site: falesny adresar s tepy agentu a *.status.json v tmp. Overuje kazde rozhodovaci
# pravidlo, hlida SHODU konstant s kodem serveru (kdyz se rozejdou, test selze) a ze oba automaty predaji --worker.
# Spusteni: api/venv/bin/python3 test_vyber_stroje.py   (konci kodem 0 jen kdyz VSE prosla)
import ast
import importlib.util
import json
import os
import re
import sys
import tempfile
import time

REPO = "/opt/konfigurator"
sys.path.insert(0, os.path.join(REPO, "scripts"))
import _render_stroje as S  # noqa: E402
# Testy 1-37 overuji vyber "dalsiho stroje" jako takovy (Omen je v nich obycejny pomocny stroj); vyhrazeni stroje pro
# nabidky ma vlastni cast na konci (38+), kde se NABIDKY_JMENO nastavuje vyslovne.
S.NABIDKY_JMENO = ""

vysl = []


def over(nazev, podminka, detail=None):
    vysl.append(bool(podminka))
    print(("OK   " if podminka else "FAIL ") + nazev + ("" if podminka else "  -> %r" % (detail,)))


T = 1_800_000_000.0   # pevny "ted"
GPU_LAPTOP = "OPTIX: NVIDIA GeForce RTX 4080 Laptop GPU | Blender 5.2.1"
GPU_STANICE = "OPTIX: NVIDIA GeForce RTX 3060 | Blender 5.2.1"


class Adresar:
    """Falesny private-files/blender-renders."""
    def __init__(self):
        self.d = tempfile.mkdtemp(prefix="stroje_test_")

    def tep(self, jmeno, vychozi=False, stari_s=5, poll_stari_s=3, gpu=GPU_LAPTOP, teplota=45.0):
        hb = {"ts": T - stari_s, "name": jmeno, "gpu": gpu, "gpu_temp_c": teplota}
        if poll_stari_s is not None:
            hb["poll_ts"] = T - poll_stari_s
        slug = re.sub(r"[^a-z0-9_-]", "_", jmeno.lower())
        nazev = ".worker_heartbeat.json" if vychozi else ".worker_heartbeat.%s.json" % slug
        with open(os.path.join(self.d, nazev), "w", encoding="utf-8") as fh:
            json.dump(hb, fh)

    def uloha(self, job, **pole):
        with open(os.path.join(self.d, job + ".status.json"), "w", encoding="utf-8") as fh:
            json.dump(pole, fh)


def vyber(a, vyloucene=()):
    return S.vyber_stroj_pro_automat(vyloucene, out_dir=a.d, ted=T)


def svet(omen=True, **kw):
    a = Adresar()
    a.tep("Logiman2", vychozi=True, gpu=GPU_STANICE)
    if omen:
        a.tep("Omen", **kw)
    return a


# --- zakladni chovani -----------------------------------------------------
a = svet()
over("1 vse volne -> vychozi stroj (notebook jen pomaha)", vyber(a)[0] is None, vyber(a))

a = svet()
a.uloha("j1", state="running", on_worker=True, worker_name="Logiman2", job_type="turntable")
over("2 vychozi ma bezici ulohu, notebook volny -> Omen", vyber(a)[0] == "Omen", vyber(a))

a = svet()
a.uloha("j1", state="waiting_worker", job_type="turntable")   # uloha bez cile ceka na vychozi
over("3 vychozi ma cekajici ulohu bez cile -> Omen", vyber(a)[0] == "Omen", vyber(a))

a = svet()
a.uloha("j1", state="running", on_worker=True, job_type="turntable")   # starsi uloha bez worker_name = vychozi
over("4 bezici uloha bez worker_name se pocita vychozimu", vyber(a)[0] == "Omen", vyber(a))

a = Adresar(); a.tep("Logiman2", vychozi=True, stari_s=900, gpu=GPU_STANICE); a.tep("Omen")
over("5 vychozi offline, notebook online -> Omen", vyber(a)[0] == "Omen", vyber(a))

a = Adresar(); a.tep("Logiman2", vychozi=True, gpu=GPU_STANICE, teplota=86.0); a.tep("Omen")
over("6 vychozi prehraty -> Omen pomuze", vyber(a)[0] == "Omen", vyber(a))

# --- notebook neni zpusobily ----------------------------------------------
busy = lambda a: a.uloha("j1", state="running", on_worker=True, worker_name="Logiman2")   # noqa: E731
a = svet(stari_s=600); busy(a)
over("7 notebook offline (stary tep) -> vychozi", vyber(a)[0] is None, vyber(a))

a = svet(poll_stari_s=600); busy(a)
over("8 notebook tepe, ale nebere si praci (zaseknuty) -> vychozi", vyber(a)[0] is None, vyber(a))

a = svet(poll_stari_s=600); busy(a)
a.uloha("j2", state="running", on_worker=True, worker_name="Omen")
over("9 notebook dlouho nepolluje, protoze renderuje = online, ale ma praci -> vychozi", vyber(a)[0] is None, vyber(a))

a = svet(gpu="OPTIX: NVIDIA GeForce RTX 4080 Laptop GPU"); busy(a)
over("10 starsi agent bez verze Blenderu -> vychozi", vyber(a)[0] is None, vyber(a))

a = svet(gpu="OPTIX: NVIDIA GeForce RTX 4080 Laptop GPU | Blender 4.1.0"); busy(a)
r = vyber(a)
over("11 Blender 4.1 (sablona je v 5.2) -> vychozi", r[0] is None and "4.1" in r[1], r)

a = svet(teplota=85.0); busy(a)
over("12 notebook prehraty -> vychozi", vyber(a)[0] is None, vyber(a))

a = svet(); busy(a)
a.uloha("test", state="waiting_worker", target_worker="omen")    # Robertuv test na notebooku ceka (jmeno bez ohledu na velikost pismen)
over("13 na notebook ceka cilena uloha (napr. test) -> neprida dalsi", vyber(a)[0] is None, vyber(a))

a = svet(); busy(a)
a.uloha("e1", state="error", target_worker="Omen", updated=T - 600)
over("14 cilena uloha na notebooku pred 10 min skoncila chybou -> odpociva", vyber(a)[0] is None, vyber(a))

a = svet(); busy(a)
a.uloha("e1", state="error", target_worker="Omen", updated=T - 3300)
over("15 chyba pred 55 min uz notebook neblokuje", vyber(a)[0] == "Omen", vyber(a))

a = svet(); busy(a)
a.uloha("e1", state="error", target_worker="Logiman2", updated=T - 60)
over("16 chyba cilena na JINY stroj notebook neblokuje", vyber(a)[0] == "Omen", vyber(a))

a = svet(); busy(a)
over("17 notebook vyloucen -> vychozi", vyber(a, vyloucene=["OMEN"])[0] is None, vyber(a, ["OMEN"]))

a = svet(); busy(a)
a.uloha("c1", state="done", target_worker="Omen")
a.uloha("c2", state="queued")
over("18 hotove a lokalni (CPU) ulohy se do zatizeni nepocitaji", vyber(a)[0] == "Omen", vyber(a))

# --- dalsi stroje, poradi, odolnost ---------------------------------------
a = svet(); busy(a); a.tep("Studio", gpu=GPU_LAPTOP)
over("19 dva volne stroje -> deterministicky abecedne prvni (Omen)", vyber(a)[0] == "Omen", vyber(a))
a.uloha("j9", state="waiting_worker", target_worker="Omen")
over("20 prvni ma praci -> druhy (Studio)", vyber(a)[0] == "Studio", vyber(a))

a = Adresar()    # zadny tep vubec (prazdny adresar)
over("21 prazdny adresar -> vychozi, bez vyjimky", vyber(a)[0] is None, vyber(a))

a = svet(); busy(a)
open(os.path.join(a.d, "rozbita.status.json"), "w").write("{ nejde to")
open(os.path.join(a.d, ".worker_heartbeat.zly.json"), "w").write("[1,2]")
over("22 poskozene soubory se preskoci", vyber(a)[0] == "Omen", vyber(a))

r = S.vyber_stroj_pro_automat(out_dir="/cesta/ktera/neexistuje", ted=T)
over("23 neexistujici adresar -> vychozi", r[0] is None, r)

# vyjimka uvnitr vyberu nesmi shodit automat
_puvodni = S._vyber
S._vyber = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("bum"))
r = S.vyber_stroj_pro_automat()
S._vyber = _puvodni
over("24 vyjimka uvnitr vyberu -> vychozi + popis chyby", r[0] is None and "bum" in r[1], r)

over("25 verze Blenderu se cte z retezce agenta", S._verze_blenderu(GPU_STANICE) == (5, 2) and S._verze_blenderu("x") is None and S._verze_blenderu(None) is None)

# --- hlidani shody konstant s kodem serveru ------------------------------
def konst(soubor, nazev):
    m = re.search(r"^%s\s*=\s*([0-9.]+)" % re.escape(nazev), open(os.path.join(REPO, soubor), encoding="utf-8").read(), re.M)
    return float(m.group(1)) if m else None

over("26 ONLINE_S = WORKER_ONLINE_S serveru", konst("api/render_worker.py", "WORKER_ONLINE_S") == S.ONLINE_S, konst("api/render_worker.py", "WORKER_ONLINE_S"))
over("27 POLL_STALE_S = WORKER_POLL_STALE_S serveru", konst("api/render_worker.py", "WORKER_POLL_STALE_S") == S.POLL_STALE_S, konst("api/render_worker.py", "WORKER_POLL_STALE_S"))
over("28 prah teploty = teplotni brzda (_render_health_config)", konst("scripts/_render_health_config.py", "PRAH_GPU_TEPLOTA_C") == S.PRAH_TEPLOTA_C, konst("scripts/_render_health_config.py", "PRAH_GPU_TEPLOTA_C"))
over("29 pauza po chybe < doba uchovani stavu (chybova uloha je po celou pauzu videt)", S.PAUZA_PO_CHYBE_S < konst("api/blender_render.py", "JOB_RETENTION_S"), konst("api/blender_render.py", "JOB_RETENTION_S"))
m = re.search(r'WORKER_VYCHOZI_JMENO\s*=\s*os\.environ\.get\("RENDER_WORKER_VYCHOZI",\s*"([^"]+)"\)', open(os.path.join(REPO, "api/render_worker.py"), encoding="utf-8").read())
over("30 vychozi jmeno stroje = WORKER_VYCHOZI_JMENO serveru", m and m.group(1) == S.VYCHOZI_JMENO, m and m.group(1))

# --- zive cteni (jen cteni) nesmi spadnout -------------------------------
try:
    zive = S.popis_stroju()
    over("31 cteni zive fronty bez vyjimky", isinstance(zive, list) and zive and "Logiman2" in zive[0], zive)
except Exception as e:   # noqa: BLE001
    over("31 cteni zive fronty bez vyjimky", False, repr(e))

# --- oba automaty predaji --worker --------------------------------------
class Proc:
    returncode = 0
    stdout = "ZARAZENO do fronty"
    stderr = ""


def zachyt(fn, *args):
    zachyceno = []

    class FakeSubprocess:
        @staticmethod
        def run(argv, **kw):
            zachyceno.append(list(argv))
            return Proc()
    fn.__globals__["subprocess"] = FakeSubprocess
    try:
        return fn(*args), zachyceno
    finally:
        fn.__globals__.pop("subprocess", None)


# Vandr: modul se importuje (nepripojuje DB pri importu); _conn se nahradi atrapou bez panelu
spec = importlib.util.spec_from_file_location("vd", os.path.join(REPO, "scripts/2026-09-23_vandr_render_auto_dispatch.py"))
vd = importlib.util.module_from_spec(spec); spec.loader.exec_module(vd)


class FakeCur:
    def execute(self, *a, **k): pass
    def fetchone(self): return None


class FakeConn:
    def cursor(self):
        class X:
            def __enter__(s): return FakeCur()
            def __exit__(s, *a): return False
        return X()
    def close(self): pass


vd._conn = lambda: FakeConn()
vd_subprocess_puvodni = vd.subprocess
(ok, _), argv = zachyt(vd.zarad_render, 4601, "Omen")
over("32 Vandr automat: zarad_render(id, 'Omen') -> --worker Omen", ok and argv and argv[0][-2:] == ["--worker", "Omen"] and "--shop-product-id" in argv[0], argv)
(ok, _), argv = zachyt(vd.zarad_render, 4601)
over("33 Vandr automat: bez cile zadne --worker", ok and argv and "--worker" not in argv[0], argv)
(ok, _), argv = zachyt(vd.zarad_render, 4601, None)
over("34 Vandr automat: cil=None zadne --worker", ok and argv and "--worker" not in argv[0], argv)

# Nativni automat: modul importuje celou aplikaci (Flask), proto se z nej vezme JEN funkce zarad_render (AST)
zdroj = open(os.path.join(REPO, "scripts/2026-09-14_render_auto_dispatch.py"), encoding="utf-8").read()
uzel = next(n for n in ast.parse(zdroj).body if isinstance(n, ast.FunctionDef) and n.name == "zarad_render")
ns = {"os": os, "REPO": REPO, "RENDER_SCRIPT": "SKRIPT.py", "RENDER_KLIC_SOUBOR": "/klic", "subprocess": None}
exec(compile(ast.Module([uzel], []), "zarad_render", "exec"), ns)
(ok, _), argv = zachyt(ns["zarad_render"], 333, "Omen")
over("35 nativni automat: zarad_render(id, 'Omen') -> --worker Omen", ok and argv and argv[0][-2:] == ["--worker", "Omen"] and "333" in argv[0], argv)
(ok, _), argv = zachyt(ns["zarad_render"], 333)
over("36 nativni automat: bez cile zadne --worker", ok and argv and "--worker" not in argv[0], argv)
over("37 oba automaty volaji vyber stroje pred zarazenim",
     "vyber_stroj_pro_automat()" in zdroj
     and "vyber_stroj_pro_automat()" in open(os.path.join(REPO, "scripts/2026-09-23_vandr_render_auto_dispatch.py"), encoding="utf-8").read())

# --- stroj vyhrazeny pro nabidky a testy ze sceny (bot4 2026-10-01) ---------------------------------------------
zdroj_server = open(os.path.join(REPO, "api/render_worker.py"), encoding="utf-8").read()
zdroj_stroje = open(os.path.join(REPO, "scripts/_render_stroje.py"), encoding="utf-8").read()
vzor = r'NABIDKY_(?:STROJ|JMENO)\s*=\s*os\.environ\.get\("RENDER_NABIDKY_STROJ",\s*"([^"]*)"\)'
ms, mz = re.search(vzor, zdroj_server), re.search(vzor, zdroj_stroje)
over("38 stejna promenna a vychozi stroj pro nabidky na serveru a v automatu", ms and mz and ms.group(1) == mz.group(1) == "Omen", (ms and ms.group(1), mz and mz.group(1)))

S.NABIDKY_JMENO = "Omen"
a = svet(); busy(a)
r = vyber(a)
over("39 Omen vyhrazen pro nabidky: ani volny a pri vytizene Logiman2 ho automat nevezme", r[0] is None and "vyhrazen" in r[1], r)

a = Adresar(); a.tep("Logiman2", vychozi=True, stari_s=900, gpu=GPU_STANICE); a.tep("Omen")
over("40 ani kdyz je Logiman2 offline (automat pocka na Logiman2)", vyber(a)[0] is None, vyber(a))

a = svet(); busy(a)
S.NABIDKY_JMENO = "omen"
over("41 velikost pismen nevadi", vyber(a)[0] is None, vyber(a))
S.NABIDKY_JMENO = "Omen"

a = svet(); busy(a); a.tep("Studio", gpu=GPU_LAPTOP)
over("42 jiny pomocny stroj se vybere normalne (vyhrazeni plati jen pro stroj nabidek)", vyber(a)[0] == "Studio", vyber(a))

S.NABIDKY_JMENO = ""
a = svet(); busy(a)
over("43 NABIDKY_JMENO prazdne = nic vyhrazeno, Omen pomaha jako driv", vyber(a)[0] == "Omen", vyber(a))

S.NABIDKY_JMENO = "Logiman2"
a = svet(); busy(a)
over("44 vyhrazeny = vychozi stroj je omyl v nastaveni a nic nemeni (Omen pomaha dal)", vyber(a)[0] == "Omen", vyber(a))

S.NABIDKY_JMENO = "Omen"
a = svet()
radky = S.popis_stroju(out_dir=a.d, ted=T)
over("45 vypis strojů znaci vyhrazeny stroj", any(r.startswith("Omen") and "VYHRAZEN" in r for r in radky) and not any(r.startswith("Logiman2") and "VYHRAZEN" in r for r in radky), radky)
S.NABIDKY_JMENO = ""

print("\nVYSLEDEK vyber stroje: %d/%d OK" % (sum(vysl), len(vysl)))
sys.exit(0 if all(vysl) else 1)
