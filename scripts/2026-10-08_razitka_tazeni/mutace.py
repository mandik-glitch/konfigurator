#!/usr/bin/env python3
"""Mutace zaplat „razitka pri tazeni se hybou s dilem“ (bot8, 2026-10-08): do KANDIDATNIHO stromu (prepare_cand.sh = po patches/*.py) se vnese jedna chyba a test musi selhat.
  S* = server (api/*.py) -> hermeticky test_razitka_tazeni.py;  J* = prohlizec (webapp/js/v3d-ovladani.js) -> test_razitka_tazeni_stranka.js v Chromiu (DB pres systemd-run; pomalejsi).
  mutace.py [-j 4] [--jen S,J]      -> "ZCHYCENO n/m" a seznam prezivsich"""
import concurrent.futures
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
PY = os.path.join(REPO, "api", "venv", "bin", "python3")

MUTACE = [
    ("S1 vodici nepripoji razitka do popisu ovladani", "api/stul_glb.py", 'out["ovladani"]["razitka"] = rz_', "rz_ = rz_"),
    ("S2 dil razitka posunuty o 1", "api/stul_glb.py", 'info_razitek.append({"dil": rz.get("dil"),', 'info_razitek.append({"dil": (rz.get("dil") or 0) + 1,'),
    ("S3 rozsah vyplne posunuty o 1 vrchol", "api/stul_glb.py", 'int(vyplne_rozsahy[k_][0]), int(vyplne_rozsahy[k_][1])]})', 'int(vyplne_rozsahy[k_][0]) + 1, int(vyplne_rozsahy[k_][1])]})'),
    ("S4 index uzlu loga o 1 vedle", "api/stul_glb.py", 'info_razitek.append({"dil": rz.get("dil"), "uzel": len(nodes),', 'info_razitek.append({"dil": rz.get("dil"), "uzel": len(nodes) + 1,'),
    ("S5 verejny popis razitka zahodi", "api/stul_ovladani_verejne.py", 'out["razitka"] = ov["razitka"]', "pass"),
    ("S6 razitka se pripojuji i k modelu bez razitek (stara cache)", "api/stul_glb.py", "rz_ = _RAZITKA_CACHE.get(h) if RAZITKA_VYCHOZI else None", "rz_ = _RAZITKA_CACHE.get(h)"),
    ("S7 razitko nenese dil", "api/stul_razitka.py", '"dil": int(i), ', ""),
    ("S8 cache razitek se pri zasahu nekontroluje", "api/stul_glb.py", " and h in _EXTRA_CACHE and h in _RAZITKA_CACHE:", " and h in _EXTRA_CACHE:"),
    ("J1 posun nehybe razitky", "webapp/js/v3d-ovladani.js", "(L.rig[i] || []).forEach(function (r) { rigMove(r, 1, dx, dy, dz); }); return; }", "return; }"),
    ("J2 razitka se pri kazdem kroku nevraci na vychozi misto (kumuluje se)", "webapp/js/v3d-ovladani.js", "      rigReset(L);\n      L.ops.forEach(function (op) {", "      L.ops.forEach(function (op) {"),
    ("J3 Esc nevraci razitka", "webapp/js/v3d-ovladani.js", "        rigReset(L);\n        Object.keys(L.nodes).forEach(function (k) { L.nodes[k].attr.needsUpdate = true; });", "        Object.keys(L.nodes).forEach(function (k) { L.nodes[k].attr.needsUpdate = true; });"),
    ("J4 vypln drazky se nehybe", "webapp/js/v3d-ovladani.js", "      if (r.v) { a = r.v.nd.attr.array; for (j = r.v.from; j < r.v.to; j += 3) { a[j] += f * dx; a[j + 1] += f * dy; a[j + 2] += f * dz; } }\n", ""),
    ("J5 natahni / roztahni hybe razitky vzdy celou delta (bez pravidla stran)", "webapp/js/v3d-ovladani.js", "            rigMove(r, ff, dx, dy, dz);", "            rigMove(r, 1, dx, dy, dz);"),
]


def spust(arg):
    n, nazev, soubor, stare, nove, koren = arg
    d = os.path.join(koren, f"m{n}")
    env = dict(os.environ, SP=koren, PYTHONDONTWRITEBYTECODE="1")
    subprocess.run([os.path.join(HERE, "prepare_cand.sh"), d], check=True, stdout=subprocess.DEVNULL, env=env)
    p = os.path.join(d, soubor)
    s = open(p, encoding="utf-8").read()
    if s.count(stare) != 1:
        raise SystemExit(f"mutace {nazev}: kotva nalezena {s.count(stare)}x: {stare[:70]!r}")
    open(p, "w", encoding="utf-8").write(s.replace(stare, nove))
    if soubor.startswith("api/"):
        cmd = [PY, os.path.join(HERE, "test_razitka_tazeni.py")]
        env2 = dict(env, STUL_API_OVERRIDE=os.path.join(d, "api"))
        cwd = REPO
    else:
        cmd = ["systemd-run", "--pipe", "--wait", "--quiet", "--property=EnvironmentFile=/opt/konfigurator/api/.env", "--setenv=HOME=/root", "--setenv=PYTHONDONTWRITEBYTECODE=1", f"--working-directory={d}", PY,
               os.path.join(d, "scripts/2026-10-02_stul_testy/_most_stul.py"), os.path.join(HERE, "test_razitka_tazeni_stranka.js"), "4934"]
        env2 = env
        cwd = d
    try:
        rc = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env2, cwd=cwd, timeout=1500).returncode
    except subprocess.TimeoutExpired:
        rc = 124
    return n, nazev, rc != 0


if __name__ == "__main__":
    j = int(sys.argv[sys.argv.index("-j") + 1]) if "-j" in sys.argv else 4
    jen = sys.argv[sys.argv.index("--jen") + 1].split(",") if "--jen" in sys.argv else None
    koren = tempfile.mkdtemp(prefix="mut_razitka_tazeni_")
    try:
        seznam = [(i, *m, koren) for i, m in enumerate(MUTACE, 1) if jen is None or any(m[0].startswith(x) for x in jen)]
        zive = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=j) as ex:
            for n, nazev, zchyceno in ex.map(spust, seznam):
                print(f"{'ZCHYCENO' if zchyceno else 'PREZILA '} {nazev}", flush=True)
                if not zchyceno:
                    zive.append(nazev)
        print(f"\nZCHYCENO {len(seznam) - len(zive)}/{len(seznam)}" + (f"; prezivsi: {zive}" if zive else ""))
        sys.exit(1 if zive else 0)
    finally:
        shutil.rmtree(koren, ignore_errors=True)
