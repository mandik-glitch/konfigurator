#!/usr/bin/env python3
"""Plánované nasazení API musí poznat COMMIT SAMOTNÉHO datového souboru jazyka `api/jazyky/<jazyk>.json` (bot16, 2026-10-07).

Past: `scripts/nasazeni.py` i panel `api/deploy_runs.py` sledovaly jen `api/*.py`; serverová sada nového jazyka (`api/jazyky/de.json`, `hu.json`) se čte při STARTU API,
takže commit jen JSON bez dalšího `api/*.py` by hlásil „nic nenasazovat“ a sada by se do produkce dostala až náhodou. Test zkopíruje kandidáty do dočasného git repa a ověří
`commity_od` + `necommitnute_api` (nasazeni.py) a `_ceka` + `_necommitnute` (deploy_runs.py): JSON sady se počítá, README ve stejné složce, podadresáře a venv ne, `api/*.py` dál ano.
Nic se nespouští ani nerestartuje, nesahá na živé repo ani DB (stub aplikace). Spuštění (kandidát = strom s upraveným nasazeni.py / deploy_runs.py, výchozí je živý):
  STROM=<strom> api/venv/bin/python3 scripts/2026-10-07_miniweb_jazyky_testy/test_nasazeni_jazyky.py"""
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import types

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
STROM = os.path.abspath(os.environ.get("STROM") or REPO)
vysl = []


def over(nazev, podminka, detail=None):
    vysl.append(bool(podminka))
    print(("OK   " if podminka else "FAIL ") + nazev + ("" if podminka else "  -> " + repr(detail)[:400]))


T0 = 1_700_000_000
tmp = tempfile.mkdtemp(prefix="nasazeni_jazyky_")


def git(*a, datum=None):
    env = dict(os.environ, GIT_CONFIG_GLOBAL="/dev/null", GIT_CONFIG_SYSTEM="/dev/null")
    if datum:
        env["GIT_AUTHOR_DATE"] = env["GIT_COMMITTER_DATE"] = "%d +0000" % datum
    r = subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "-C", tmp] + list(a), capture_output=True, text=True, env=env)
    if r.returncode != 0:
        raise RuntimeError("git %s: %s" % (" ".join(a), r.stderr))
    return r.stdout


def zapis(cesta, text):
    p = os.path.join(tmp, cesta)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "w", encoding="utf-8").write(text)


try:
    git("init", "-q")
    zapis("api/app.py", "# app\n")
    zapis("api/jazyky.py", "# loader\n")
    zapis("api/jazyky/README.md", "# jazyky\n")
    zapis("api/venv/lib/x.py", "# venv\n")
    for k in ("scripts", "api"):
        os.makedirs(os.path.join(tmp, k), exist_ok=True)
    shutil.copy(os.path.join(STROM, "scripts", "nasazeni.py"), os.path.join(tmp, "scripts", "nasazeni.py"))
    shutil.copy(os.path.join(STROM, "api", "deploy_runs.py"), os.path.join(tmp, "api", "deploy_runs.py"))
    git("add", "-A")
    git("commit", "-q", "-m", "zaklad", datum=T0)
    zapis("api/jazyky/de.json", '{"lang": "de"}\n')
    git("add", "-A"); git("commit", "-q", "-m", "A: sada de (jen JSON)", datum=T0 + 100)
    zapis("api/jazyky/README.md", "# jazyky 2\n")
    git("add", "-A"); git("commit", "-q", "-m", "B: jen README ve slozce jazyku", datum=T0 + 200)
    zapis("api/sub/x.py", "# podadresar\n")
    git("add", "-A"); git("commit", "-q", "-m", "C: podadresar api/sub", datum=T0 + 300)
    zapis("api/app.py", "# app 2\n")
    git("add", "-A"); git("commit", "-q", "-m", "D: api/app.py", datum=T0 + 400)
    zapis("api/jazyky/hu.json", '{"lang": "hu"}\n')
    git("add", "-A"); git("commit", "-q", "-m", "E: sada hu (jen JSON)", datum=T0 + 500)
    zapis("api/venv/lib/x.py", "# venv 2\n")
    git("add", "-A"); git("commit", "-q", "-m", "F: venv", datum=T0 + 600)

    # --- scripts/nasazeni.py (REPO se bere z umisteni souboru = dočasné repo)
    spec = importlib.util.spec_from_file_location("nasazeni_kandidat", os.path.join(tmp, "scripts", "nasazeni.py"))
    N = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(N)
    over("N0 kandidát nasazeni.py pracuje nad dočasným repem", os.path.realpath(N.REPO) == os.path.realpath(tmp), N.REPO)
    predmety = [c["predmet"] for c in N.commity_od(T0 + 50)]
    over("N1 commit jen s api/jazyky/de.json se počítá jako čekající změna", "A: sada de (jen JSON)" in predmety, predmety)
    over("N2 commit jen s api/jazyky/hu.json se počítá", "E: sada hu (jen JSON)" in predmety, predmety)
    over("N3 api/app.py dál ano", "D: api/app.py" in predmety, predmety)
    over("N4 README ve složce jazyků, podadresář api/sub a venv se NEpočítají", not any(p.startswith(("B:", "C:", "F:")) for p in predmety), predmety)
    over("N5 filtr času: od T0+450 zbývá jen sada hu", [c["predmet"] for c in N.commity_od(T0 + 450)] == ["E: sada hu (jen JSON)"], N.commity_od(T0 + 450))

    # --- necommitnute zmeny
    zapis("api/jazyky/pl.json", '{"lang": "pl"}\n')                    # nový, neverzovaný
    zapis("api/jazyky/de.json", '{"lang": "de", "x": 1}\n')            # upravený verzovaný
    zapis("api/jazyky/README.md", "# jazyky 3\n")                      # README se neblokuje
    zapis("api/sub/x.py", "# zmena podadresare\n")
    zapis("api/app.py", "# app 3\n")
    cesty = sorted(c for _, c in N.necommitnute_api())
    over("N6 necommitnuté sady jazyků (nová i upravená) a api/app.py blokují nasazení, README a podadresář ne", cesty == ["api/app.py", "api/jazyky/de.json", "api/jazyky/pl.json"], cesty)
    git("checkout", "-q", "--", ".")
    os.remove(os.path.join(tmp, "api/jazyky/pl.json"))
    over("N7 po úklidu nic nečeká na commit", N.necommitnute_api() == [], N.necommitnute_api())

    # --- api/deploy_runs.py (panel Nasazení serveru): stub aplikace, git funkce nad dočasným repem
    stub = types.ModuleType("app")
    class _A:
        def get(self, *a, **k):
            return lambda f: f
        post = put = route = get
    stub.app = _A()
    stub.get_conn = lambda *a, **k: None
    stub.require_permission = lambda *a, **k: (lambda f: f)
    sys.modules["app"] = stub
    spec2 = importlib.util.spec_from_file_location("deploy_runs_kandidat", os.path.join(tmp, "api", "deploy_runs.py"))
    D = importlib.util.module_from_spec(spec2)
    spec2.loader.exec_module(D)
    over("D0 kandidát deploy_runs.py pracuje nad dočasným repem", os.path.realpath(D.REPO) == os.path.realpath(tmp), D.REPO)
    pred2 = [c["predmet"] for c in D._ceka(T0 + 50)]
    over("D1 panel počítá commit jen s JSON sadou (de, hu) a api/*.py, ne README / podadresář / venv",
         pred2 == predmety and "A: sada de (jen JSON)" in pred2 and "E: sada hu (jen JSON)" in pred2 and not any(p.startswith(("B:", "C:", "F:")) for p in pred2), pred2)
    zapis("api/jazyky/pl.json", '{"lang": "pl"}\n')
    zapis("api/jazyky/README.md", "# jazyky 4\n")
    zapis("api/sub/x.py", "# zmena podadresare 2\n")
    soubory = sorted(r["soubor"] for r in D._necommitnute())
    over("D2 panel ukáže necommitnutou sadu jazyka (nová), README ani podadresář ne", soubory == ["api/jazyky/pl.json"], soubory)
finally:
    shutil.rmtree(tmp, ignore_errors=True)

ok = sum(vysl)
print("\nVYSLEDEK nasazeni sleduje datove sady jazyku (%s): %d/%d OK" % ("živý strom" if STROM == REPO else STROM, ok, len(vysl)))
sys.exit(0 if ok == len(vysl) else 1)
