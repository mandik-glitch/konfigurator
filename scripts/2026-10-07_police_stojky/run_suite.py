#!/usr/bin/env python3
"""Spusti NEBROWSEROVE kroky sady scripts/2026-10-02_stul_testy/run_all.sh (+ dalsi sady) nad danym korenem repa (zivy /opt/konfigurator nebo kandidatni repo z prepare_cand.sh) paralelne.
  run_suite.py <koren repa> <vystupni slozka> [-j 4] [--jen cislo,cislo]  -> pro kazdy krok <cislo>.log a souhrn "kroky: rc"
Prikazy se berou z run_all.sh (radky `echo "== N/M ..."; PRIKAZ | tail -3`), preskoci se `node`, Playwright (.js) a kroky, ktere potrebuji prohlizec; `--working-directory=/opt/konfigurator` se nahradi korenem."""
import concurrent.futures
import os
import re
import subprocess
import sys

REPO0 = "/opt/konfigurator"


def kroky(koren):
    out = []
    for r in open(os.path.join(REPO0, "scripts/2026-10-02_stul_testy/run_all.sh"), encoding="utf-8"):
        m = re.match(r'echo "== (\d+)/\d+ (.*?)"; (.*?) \| tail', r)
        if not m:
            continue
        n, popis, cmd = int(m.group(1)), m.group(2), m.group(3)
        if "node " in cmd or ".js" in cmd:
            continue
        cmd = cmd.replace("--working-directory=/opt/konfigurator", f"--working-directory={koren}")
        out.append((n, popis, cmd))
    return out


def spust(arg):
    koren, slozka, (n, popis, cmd) = arg
    with open(os.path.join(slozka, f"{n:02d}.log"), "w", encoding="utf-8") as f:
        try:
            p = subprocess.run(cmd, shell=True, cwd=koren, stdout=f, stderr=subprocess.STDOUT, timeout=1500)
            rc = p.returncode
        except subprocess.TimeoutExpired:
            rc = 124
    return n, popis, rc


if __name__ == "__main__":
    koren, slozka = sys.argv[1], sys.argv[2]
    j = int(sys.argv[sys.argv.index("-j") + 1]) if "-j" in sys.argv else 4
    jen = {int(x) for x in sys.argv[sys.argv.index("--jen") + 1].split(",")} if "--jen" in sys.argv else None
    os.makedirs(slozka, exist_ok=True)
    seznam = [(koren, slozka, k) for k in kroky(koren) if jen is None or k[0] in jen]
    with concurrent.futures.ThreadPoolExecutor(max_workers=j) as ex:
        for n, popis, rc in ex.map(spust, seznam):
            print(f"krok {n:2d} rc={rc} {popis[:100]}", flush=True)
