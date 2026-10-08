"""Spolecne pomucky testu 'spodni police BEZ DESKY' (bot8, 2026-10-07; Robert: "spodni police nech ma volbu byt bez desky, jen profily / ram").

  * import generatoru z adresare `STUL_API_OVERRIDE` (kandidatni / zakladni strom ve scratchpadu), jinak z api/ v repu; DB se v techto testech NEPOUZIVA (pymysql.connect zakazano,
    falesne prostredi), cena a shop vrstva maji vlastni test (test_police_bez_desky_shop.py, DB jen cte);
  * mrizka konfiguraci (system x sirka x hloubka x police x stredni opora + vyrezy + prislusenstvi + SSE) a otisky vysledku (zlaty otisk PRED zavedenim volby).
"""
import hashlib
import itertools
import json
import os
import sys
import threading

sys.dont_write_bytecode = True                       # kandidatni / zakladni strom nesmi psat bajtkod do zivych adresaru (__pycache__ je v nich sdileny symlinkem)
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
API = os.environ.get("STUL_API_OVERRIDE") or os.path.join(REPO, "api")
HERE = os.path.dirname(os.path.abspath(__file__))
GOLDEN = os.path.join(HERE, "golden_head.json")


def nacti_generator(hermeticky=True):
    """Importuje app + generator (S), GLB (G), koty (K). hermeticky=True: falesne prostredi a zakazane pripojeni k DB (testy bez DB); False: prostredi z EnvironmentFile (systemd-run)."""
    if hermeticky:
        import pymysql
        for k, v in {"FLASK_SECRET_KEY": "selftest-secret", "DB_HOST": "selftest.invalid", "DB_PORT": "3306", "DB_USER": "selftest", "DB_PASSWORD": "selftest", "DB_NAME": "selftest"}.items():
            os.environ[k] = v
        pymysql.connect = lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("test: pripojeni k DB zakazano"))
    os.chdir(REPO)
    orig = threading.Thread.start
    threading.Thread.start = lambda self, *a, **k: None if self.name == "render-dozorce" else orig(self, *a, **k)
    try:
        sys.path.insert(0, API)
        sys.path.insert(0, os.path.join(REPO, "scripts"))
        import app  # noqa: F401
        import stul_glb as G
        import stul_konfigurator as S
        import stul_koty as K
    finally:
        threading.Thread.start = orig
    S.nastav_pravidla({})                                   # ziva pravidla stolu (DB) test neovlivni
    return S, G, K


def zaokr(o, nd=3):
    if isinstance(o, float):
        return round(o, nd)
    if isinstance(o, dict):
        return {str(k): zaokr(v, nd) for k, v in sorted(o.items(), key=lambda kv: str(kv[0]))}
    if isinstance(o, (list, tuple)):
        return [zaokr(v, nd) for v in o]
    if hasattr(o, "tolist"):
        return zaokr(o.tolist(), nd)
    return o


def fp(o):
    return hashlib.sha256(json.dumps(zaokr(o, 6), sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()[:20]


PRIDANE_PARAMETRY_OVLADANI = ("police_deska", "led_delka", "led_pocet", "led_z1", "led_z2", "led_z3", "led_z4")      # police_deska = tato volba; led_delka = volba delky svitidla LED (commit LED 600, 2026-10-08): obe pridavaji parametr do `param` a polozky do nabidky


def bez_nove_volby_ovladani(ov):
    """Ovladani ve 3D bez PRIDANYCH prvku nove volby (parametr `police_deska` v `param` casti a polozka nabidky, ktera ho nastavuje; po commitu LED 600 stejne `led_delka` - polozky 'Zvolit LED N mm'):
    tvar, ktery mel vystup pred zavedenim obou voleb (zlaty otisk PRED zavedenim `police_deska`; LED prirustek dalsi vrstvy se z nej odfiltruje stejne jako ve vlastni regresi LED)."""
    ov = json.loads(json.dumps(zaokr(ov)))
    for c in ov.get("casti", []):
        c["param"] = [q for q in c.get("param", []) if q not in PRIDANE_PARAMETRY_OVLADANI]
        c["menu"] = [m for m in c.get("menu", []) if not any(k in (m.get("nastav") or {}) for k in PRIDANE_PARAMETRY_OVLADANI) and m.get("text") != "Přidat svítidlo LED"]
    # rucni svitidla LED (2026-10-08): casti jednotlivych svitidel led_<k> a jejich tahy led_z<k> jsou dalsi prirustek (nabidka "Přidat svítidlo LED" se ve vypnutem stavu pozna podle textu)
    ov["casti"] = [c for c in ov.get("casti", []) if not (str(c.get("id", "")).startswith("led_") and str(c.get("id", ""))[4:].isdigit())]
    ov["tahy"] = [t for t in ov.get("tahy", []) if not (str(t.get("id", "")).startswith("led_z") and str(t.get("id", ""))[5:].isdigit())]
    return ov


def mrizka():
    """Konfigurace zlateho otisku (bez parametru police_deska): vychozi chovani musi zustat beze zmeny."""
    for system, sirka, hloubka, police, opora, vyska in itertools.product((30, 35, 40, 45), (1280, 1700, 2100, 2800), (800, 1000, 1600), (0, 1, 2, 3), ("auto", "noha", "ram"), (840, 1150)):
        yield dict(system=system, sirka=sirka, hloubka=hloubka, police=police, stredni_opora=opora, vyska=vyska)         # vyska 1150: vic polic se vejde (840 = jedna)
    for system, sirka, police, vyrez_police in itertools.product((30, 40, 45), (1280, 2100), (0, 1, 2), (True, False)):         # vyrez 1 (a 2) s policí pod vyrezem a bez ni
        yield dict(system=system, sirka=sirka, police=police, vyrez1=True, vyrez1_police=vyrez_police, vyrez2=(sirka > 2000), vyrez2_police=(sirka > 2000 and vyrez_police))
    for system in (30, 35, 40, 45):
        for police in (1, 2):
            yield dict(system=system, police=police, suplik=False)
            yield dict(system=system, police=police, suplik_pocet=3)
            yield dict(system=system, police=police, kolecka=False, patky=True)
            yield dict(system=system, police=police, stojky=False)
            yield dict(system=system, police=police, panely=False, led=False)
            yield dict(system=system, police=police, vzpery=True)
            yield dict(system=system, police=police, vyska=500)
            yield dict(system=system, police=police, vyska=1000, hloubka=1200 if system == 45 else 1000, sirka=2400)
    yield dict(system=30, police=2, police_h1=150.0, police_h2=120.0)
    yield dict(system=40, police=3, police_h1=140.0, police_h2=130.0, police_h3=110.0, sirka=2200)
    yield dict(system=35, navlek=True, police=1)
    yield dict(system=35, navlek=True, police=2, vyska=800)
    yield dict(system=45, hloubka=2400, sirka=2900, police=3, stredni_opora="ram")
    for sirka, police in itertools.product((1600, 2000, 2400), (0, 1)):
        yield dict(system=41, sirka=sirka, police=police)


def shoduje(ted, z):
    """Otisk shodny se zlatym; klice, ktere jsou u `ted` None, se nesrovnavaji: hash stolu, kde drive vznikalo vic svitidel automaticky (ted se `led_pocet` > 1 nese v hashi), a nahled zive tazeni sirky 2347-2446 mm."""
    vynech = {k for k, v in ted.items() if v is None}
    return {k: v for k, v in ted.items() if k not in vynech} == {k: v for k, v in z.items() if k not in vynech}


def klic_konfigurace(p):
    return json.dumps(p, sort_keys=True)


def stary_pocet(S):
    """Od 2026-10-08 je pocet svitidel LED RUCNI (`led_pocet`, vychozi 1). Zlaty otisk je z doby, kdy se svitidla na sirokych stolech pridavala sama (= nejvic, co se vejde): `led_pocet` na nejvic dava
    PRESNE drivejsi model (hash se u takovych stolu lisi - nese klic poctu)."""
    return {"led_pocet": S.LED_MAX} if hasattr(S, "LED_MAX") else {}


def vysledek(S, p):
    """sestav_stul + kompletni sada otisku. Chybu generatoru (StulChyba, napr. hloubka mimo rozsah systemu) zaznamena jako 'err:<kod>'.
    Od 2026-10-08 je pocet svitidel LED RUCNI (`led_pocet`, vychozi 1): zlaty otisk je z doby, kdy se svitidla na sirokych stolech pridavala sama (= nejvic, co se vejde), proto se pocet zadava na nejvic."""
    try:
        return S.sestav_stul(**{**stary_pocet(S), **p})
    except S.StulChyba as e:
        return "err:" + str(getattr(e, "kod", "?"))


def otisky(S, G, K, r, klice_param=None):
    """Otisky vsech casti vysledku generatoru, ktere se po zavedeni volby (s vychozi hodnotou) NESMI zmenit. `klice_param` = klice parametru v dobe zlateho otisku (jine pozdejsi parametry
    jinych funkci se do otisku `parametry` nepocitaji - zlaty otisk hlida jen to, co se pri zavedeni volby nesmi zmenit)."""
    if isinstance(r, str):
        return {"chyba": r}
    par = {k: v for k, v in r["parametry"].items() if k != "police_deska" and (klice_param is None or k in klice_param)}
    out = {"hash": None if r["parametry"].get("led_pocet", 1) > 1 else G.kanonicky_hash(r["parametry"]), "parametry": fp(par), "dily": fp(r["dily"]), "klice": fp(r["klice"]), "spoje": fp(r["spoje"]), "problemy": fp(r["problemy"]),
           "problemu": len(r["problemy"]), "pocet_spoju": r["pocet_spoju"], "dilu": len(r["dily"]), "rozmery": fp(r["rozmery"]),
           "ostatni": fp({k: r.get(k) for k in ("info", "odebrano", "nabidky_odebrani", "police_meze", "max_polic", "vyrezy", "loz", "panely_info", "suplik_meze", "pet_meze", "stojky_meze", "navlek_meze", "vzpera_meze") if k in r})}
    out["entries"] = fp(S.entries_pro_cenu(r["dily"]))
    try:
        out["vypis"] = fp(S.vyrobni_vypis(r))
    except Exception as e:                                    # noqa: BLE001
        out["vypis"] = "chyba:" + type(e).__name__
    try:
        out["koty"] = fp(K.koty(r))
    except Exception as e:                                    # noqa: BLE001
        out["koty"] = "chyba:" + type(e).__name__
    try:
        out["ovladani"] = fp(bez_nove_volby_ovladani(S.ovladani_3d(r)))
        if 2347 <= r["parametry"]["sirka"] <= 2446 and r["parametry"].get("led") and hasattr(S, "LED_MAX"):
            out["ovladani"] = None       # NAHLED zive tazeni sirky se meri sondou (+-100 / +-30 mm): u sirky 2347-2446 mm sonda +100 uz neprekroci prah 2447 mm (drive tam pribyvalo 2. svitidlo) a opre se o jiny krok
    except Exception as e:                                    # noqa: BLE001
        out["ovladani"] = "chyba:" + type(e).__name__
    return out
