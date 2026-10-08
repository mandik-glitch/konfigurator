#!/usr/bin/env python3
"""MUTACE jadra systemu 45 (bot10, 2026-10-07): do KOPIE api/ se vlozi zamerna chyba a `test_s45_jadro.py --rychle` (nebo test regrese / shopu) ji musi zachytit.

  api/venv/bin/python3 -B scripts/2026-10-07_system45/mutace_s45.py [--jen=N,M]      (strom s kodem = api/ vedle tohoto skriptu; kopie je v dockem adresari, nic ziveho se nemeni)
Kazda mutace: (nazev, soubor, puvodni text, novy text, test). Test = jadro | regrese | shop (test_s45_shop.py, DB jen cte) | pravidla (test_s45_pravidla.py, falesna DB). Vysledek: "ZACHYCENA" (test selhal) / "PREZILA" (test prosel = diru v testech)."""
import os
import shutil
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PY = "/opt/konfigurator/api/venv/bin/python3"
MUTACE = [
    ("prah stredni rady 1500 -> 1600", "stul_konfigurator.py", "HLOUBKA_STREDNI_NOHA = 1500.0 ", "HLOUBKA_STREDNI_NOHA = 1600.0 ", "jadro"),
    ("rozsah hloubky 45 jen do 2400", "stul_konfigurator.py", 'rozsah_navic={"hloubka": (400.0, 2500.0)}', 'rozsah_navic={"hloubka": (400.0, 2400.0)}', "jadro"),
    ("stredni noha o 5 mm vedle pulky hloubky", "stul_konfigurator.py", "[x_mid, (top_nej + dolni) / 2.0, zs], delka=top_nej - dolni)", "[x_mid + 5.0, (top_nej + dolni) / 2.0, zs], delka=top_nej - dolni)", "jadro"),
    ("pricka o 10 mm kratsi", "stul_konfigurator.py", "[x_mid, y_u - _P(), (zl + zr) / 2.0], delka=(zr - zl) - _P())", "[x_mid, y_u - _P(), (zl + zr) / 2.0], delka=(zr - zl) - _P() - 10.0)", "jadro"),
    ("pricka ve spatne vysce (pod bocnim pruvlakem o 5 mm vys)", "stul_konfigurator.py", "[x_mid, y_u - _P(), (zl + zr) / 2.0], delka=(zr - zl) - _P())", "[x_mid, y_u - _P() + 5.0, (zl + zr) / 2.0], delka=(zr - zl) - _P())", "jadro"),
    ("brana minimalni delky stredni nohy vypnuta", "stul_konfigurator.py", "- dolni >= MIN_DELKA_STREDNI_NOHY - 0.01)", "- dolni >= -1e9)", "jadro"),
    ("stredni kolecka se nevkladaji", "stul_konfigurator.py", 'clenove[("bok_kolecko", strana)] = _klon(', 'clenove[("bok_kolecko_x", strana)] = _klon(', "jadro"),
    ("system 45 neni oznacen jako hluboky (bez stredni rady)", "stul_konfigurator.py", "SYSTEMY[SYSTEM_45] = dict(SYSTEMY[40], system=SYSTEM_45, hluboky=True,", "SYSTEMY[SYSTEM_45] = dict(SYSTEMY[40], system=SYSTEM_45, hluboky=False,", "jadro"),
    ("rozsah hloubky 40 rozsiren na 2500", "stul_konfigurator.py", 'return {**ROZSAH, **SYSTEMY[system].get("rozsah_navic", {})}', 'return {**ROZSAH, "hloubka": (400.0, 2500.0)}', "jadro"),
    ("45 ma vlastni (jina) sablonu / pravidla: prah podper 45 = 1000", "stul_konfigurator.py", 'PRAVIDLA_SYSTEMU = {s_: pravidla_vychozi(s_) for s_ in SYSTEMY}', 'PRAVIDLA_SYSTEMU = {s_: dict(pravidla_vychozi(s_), hloubka_stredni_profil=(1000.0 if s_ == 45 else 900.0)) for s_ in SYSTEMY}', "jadro"),
    ("info o stredni rade bez poctu pricek", "stul_konfigurator.py", '"pricek": len(urovne_rady)}', '"pricek": 0}', "jadro"),
    ("45 pocita konec nohy jinak (zaslepka vzdy)", "stul_konfigurator.py", 'elif p["patky"]:\n                clenove[("konec", kn)] = _clen(_sd()["patka"]', 'elif False:\n                clenove[("konec", kn)] = _clen(_sd()["patka"]', "jadro"),
    ("regrese: odpoved() meni zaznam systemu 40 (pridany klic)", "stul_konfigurator.py", '"navlek": k in NAVLEK_SYSTEMY, **({"hluboky": True} if v.get("hluboky") else {})}', '"navlek": k in NAVLEK_SYSTEMY, "hluboky": bool(v.get("hluboky"))}', "regrese"),
    ("regrese: system 40 ma jiny prah podper po zavedeni 45", "stul_konfigurator.py", "HLOUBKA_STREDNI_PROFIL = 900 ", "HLOUBKA_STREDNI_PROFIL = 950 ", "regrese"),
    ("API: ulozeni pravidel vraci plochy tvar i kdyz ma 45 zmeny (ztrata hodnot 45)", "stul_api.py", "not any(uloz[str(x)] for x in S.SYSTEMY if x not in S.SYSTEMY_PLOCHA)", "not uloz[str(S.SYSTEM_SSE)]", "pravidla"),
    ("API: staff route pocita cenu podle dilu (45 -> pravidla 40)", "stul_api.py", 'cena_konfigurace(out["dily"], out["parametry"]["system"])', 'cena_konfigurace(out["dily"])', "pravidla"),
    ("shop: cena resolve podle dilu (45 -> pravidla 40)", "stul_shop.py", 'cena = stul_api.cena_konfigurace(gen["dily"], p["system"])\n    kus, cena_celkem = [], None', 'cena = stul_api.cena_konfigurace(gen["dily"])\n    kus, cena_celkem = [], None', "shop"),
    ("shop: posuvnik hloubky pro 45 jen do 1500", "stul_shop.py", 'slider("d", "g_size", S._rozsahy(system)["hloubka"][0], S._rozsahy(system)["hloubka"][1], 10, "mm"),', 'slider("d", "g_size", S.ROZSAH["hloubka"][0], S.ROZSAH["hloubka"][1], 10, "mm"),', "shop"),
    ("shop: normalizace hloubky ořezává 45 na 1500", "stul_shop.py", '"hloubka": _cislo(sel["d"], *S._rozsahy(system)["hloubka"], 800, 10),', '"hloubka": _cislo(sel["d"], *S.ROZSAH["hloubka"], 800, 10),', "shop"),
    ("shop: oznameni o stredni rade noh se nevraci", "stul_shop.py", 'elif inf["kod"] == "stredni_rada_noh":', 'elif inf["kod"] == "stredni_rada_noh_x":', "shop"),
    ("vyrobni list: cislo generatoru 45 chybi", "stul_vyrobni_list.py", '41: "04", 45: "05"}', '41: "04"}', "shop"),
    ("shop: recept 45 se nerozpozna (RECEPTY bez 45)", "stul_shop.py", "RECEPT_SSE: 41, RECEPT_45: 45}", "RECEPT_SSE: 41}", "shop"),
]


def kopie():
    tmp = tempfile.mkdtemp(prefix="mutace_s45_")
    shutil.copytree(os.path.join(REPO, "api"), os.path.join(tmp, "api"), symlinks=True, ignore=shutil.ignore_patterns("__pycache__", "venv", "*.sock", "*.pid", ".env", ".env.*", "*.log"))          # zivy api/ ma unixovy socket a .env (tajemstvi se do kopie nekopiruji)
    for x in ("scripts", "webapp"):
        os.symlink(os.path.join(REPO, x), os.path.join(tmp, x))
    return tmp


def main():
    jen = None
    for a in sys.argv[1:]:
        if a.startswith("--jen="):
            jen = {int(x) for x in a[6:].split(",")}
    zachyceno = prezilo = 0
    for i, (nazev, soubor, puv, nov, test) in enumerate(MUTACE, 1):
        if jen and i not in jen:
            continue
        tmp = kopie()
        try:
            cesta = os.path.join(tmp, "api", soubor)
            s = open(cesta, encoding="utf-8").read()
            if s.count(puv) != 1:
                print(f"[{i:2}] CHYBA MUTACE: kotva {s.count(puv)}x: {nazev}")
                continue
            open(cesta, "w", encoding="utf-8").write(s.replace(puv, nov))
            skript = {"jadro": ["test_s45_jadro.py", "--rychle"], "regrese": ["test_s45_regrese.py", "HEAD"], "shop": ["test_s45_shop.py"], "pravidla": ["test_s45_pravidla.py"]}[test]
            prikaz = [PY, "-B", os.path.join(tmp, "scripts", "2026-10-07_system45", skript[0])] + skript[1:]
            if test in ("shop", "pravidla"):                       # DB testy: prihlasovaci udaje pres systemd (jen cte)
                prikaz = ["systemd-run", "--pipe", "--wait", "--quiet", "--property=EnvironmentFile=/opt/konfigurator/api/.env", "--setenv=HOME=/root", "--working-directory=" + tmp] + prikaz
            r = subprocess.run(prikaz, capture_output=True, text=True, timeout=1800)
            ok = r.returncode != 0
            zachyceno += ok
            prezilo += not ok
            print(f"[{i:2}] {'ZACHYCENA' if ok else 'PREZILA  '} {nazev}  ({test}, rc={r.returncode})", flush=True)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    print(f"\nzachyceno {zachyceno}, prezilo {prezilo} z {zachyceno + prezilo}")
    sys.exit(1 if prezilo else 0)


main()
