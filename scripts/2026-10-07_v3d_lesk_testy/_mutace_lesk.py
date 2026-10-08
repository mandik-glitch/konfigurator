#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Mutacni kontrola test_lesk_ao.js (bot10, 2026-10-07): do kopie kandidatniho prekryvu webapp vlozi vzdy jednu chybu do viewer3d.js nebo kontrola.html a overi, ze test SELZE.
Nejdriv se overi, ze NEMUTOVANY prekryv projde (jinak by kazda mutace vypadala jako chycena). Pouziti: _mutace_lesk.py <prekryv (adresar s webapp/js/v3d/viewer3d.js a webapp/kontrola.html)> [paralelne, vychozi 2]
Prekryv se kopiruje cp -a (symlinky zustavaji, soubory se kopiruji); do repa se nezapisuje."""
import concurrent.futures as cf
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
CAND = os.path.abspath(sys.argv[1])
PAR = int(sys.argv[2]) if len(sys.argv) > 2 else 2
VJ = os.path.join(CAND, "webapp", "js", "v3d", "viewer3d.js")
KH = os.path.join(CAND, "webapp", "kontrola.html")
V = open(VJ, encoding="utf-8").read()
K = open(KH, encoding="utf-8").read()
# (nazev, "v" | "k", kotva, nahrada)
MUT = [
    ("lesk: spatny vzorec (nasobek misto mocniny)", "v", "Math.min(1, Math.max(0.02, Math.pow(Math.max(r0, 0.02), gl)))", "Math.min(1, Math.max(0.02, Math.max(r0, 0.02) * gl))"),
    ("lesk plati pro vsechny materialy, ne podle barvy", "v", "var gl = cfg ? cfg.gloss[srgbHexOfBase(b)] : undefined;", "var gl = cfg ? cfg.gloss[Object.keys(cfg.gloss)[0]] : undefined;"),
    ("hlinik: odrazy se neuplatni", "v", "(a.p ? a.p.e : 1) * (st.aluCfg ? st.aluCfg.refl : 1)", "(a.p ? a.p.e : 1)"),
    ("hlinik: matnost se neuplatni", "v", "(p ? p.r : o.r) * (st.aluCfg ? st.aluCfg.rough : 1)", "(p ? p.r : o.r)"),
    ("AO: sila se neuplatni", "v", "k: p.k * (st.aoCfg ? st.aoCfg.k : 1)", "k: p.k"),
    ("AO: dosah se neuplatni", "v", "r: p.r * (st.aoCfg ? st.aoCfg.r : 1)", "r: p.r"),
    ("setAluConfig neprepocita hlinik", "v", "if (st.ready) { applyAlu(); applyMatLook(); kick(); } return api.getAluConfig(); }", "if (st.ready) { kick(); } return api.getAluConfig(); }"),
    ("normMatCfg zahodi lesk", "v", "if (g !== 1) { gloss[s] = g; gn++; }", "if (false) { gloss[s] = g; gn++; }"),
    ("lesk se neomezuje na mez", "v", "g = clampNum(g, 1, 0, GLOSS_MAX);", "g = Number(g);"),
    ("↺ u lesku nic nevraci", "k", 'glR.addEventListener("click", () => { glIn.value = "100"; glT.textContent = "100 %"; glR.hidden = true; vzhledMatNastav((cfg) => { if (cfg.gloss) delete cfg.gloss[p.hex]; }); });', 'glR.addEventListener("click", () => { glIn.value = "100"; glT.textContent = "100 %"; glR.hidden = true; });'),
    ("probe vzdy zapnuty (stary server ukaze novou cast)", "k", 'vzhledNoveApi = !!(j && typeof j === "object" && "lesk" in j && "hdri_extra" in j);', "vzhledNoveApi = true;"),
    ("ulozeni vzdy nese nova pole (stary server odmitne)", "k", "if (vzhledNoveApi) Object.assign(telo,", "if (true) Object.assign(telo,"),
    ("posuvniky AO se pri vypnutem AO nezamykaji", "k", "vzhledAoK.disabled = vyp; vzhledAoR.disabled = vyp;", "vzhledAoK.disabled = false; vzhledAoR.disabled = false;"),
    ("posuvnik lesku uklada dvojnasobek", "k", "else cfg.gloss[p.hex] = v; });", "else cfg.gloss[p.hex] = v * 2; });"),
    ("vychozi vzhled nevrati hlinik a AO", "k", "if (api.resetAluConfig) { api.resetAluConfig(); api.resetAoConfig(); }", ""),
    ("posuvnik odrazu hliniku neposila zmenu vieweru", "k", "if (api && typeof api.setAluConfig === \"function\") api.setAluConfig(", "if (false) api.setAluConfig("),
]


def mutuj(kde, a, b):
    z = V if kde == "v" else K
    if z.count(a) != 1:
        return None, "KOTVA nalezena %d x: %s" % (z.count(a), a[:50])
    return z.replace(a, b), None


def spust(cil_dir, env_extra=None):
    env = dict(os.environ, WEB_DIR=os.path.join(cil_dir, "webapp"))
    r = subprocess.run(["node", os.path.join(HERE, "test_lesk_ao.js")], env=env, capture_output=True, text=True, timeout=1200)
    return r.returncode, [l[:120] for l in r.stdout.splitlines() if l.startswith("[CHYBA]")]


def mut(i):
    nazev, kde, a, b = MUT[i]
    novy, chyba = mutuj(kde, a, b)
    if novy is None:
        return i, nazev, None, chyba
    d = tempfile.mkdtemp(prefix="mutace_lesk_")
    try:
        subprocess.check_call(["cp", "-a", CAND, d + "/c"])
        open(os.path.join(d, "c", "webapp", "js", "v3d", "viewer3d.js") if kde == "v" else os.path.join(d, "c", "webapp", "kontrola.html"), "w", encoding="utf-8").write(novy)
        rc, fails = spust(os.path.join(d, "c"))
        return i, nazev, rc != 0, "; ".join(f[8:70] for f in fails[:2]) or ("pad testu (exit %d)" % rc)
    finally:
        shutil.rmtree(d, ignore_errors=True)


if os.environ.get("MUT_DRY"):
    for i, (n, kde, a, b) in enumerate(MUT):
        print("%2d %-55s %s" % (i + 1, n, mutuj(kde, a, b)[1] or "ok"))
    sys.exit(0)
rc0, f0 = spust(CAND)
print("ZAKLAD (nemutovany prekryv): %s" % ("OK" if rc0 == 0 else "SELHAL " + "; ".join(f0[:3])), flush=True)
if rc0 != 0:
    print("Nemutovany test selhava - mutace nema smysl vyhodnocovat.")
    sys.exit(2)
bad = 0
with cf.ThreadPoolExecutor(PAR) as ex:
    for i, nazev, ok, info in ex.map(mut, range(len(MUT))):
        bad += 0 if ok else 1
        print(("chyceno  " if ok else "!!! NECHYCENO ") + "| %2d %s | %s" % (i + 1, nazev, info), flush=True)
print("\n%d mutaci, chyceno %d, nechyceno/chyba pripravy %d" % (len(MUT), len(MUT) - bad, bad))
sys.exit(1 if bad else 0)
