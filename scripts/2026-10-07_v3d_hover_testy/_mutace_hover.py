#!/usr/bin/env python3
"""Mutacni kontrola testu vyzvy ke kliknuti (bot10, 2026-10-07): do kopie kandidatniho vieweru vlozi vzdy jednu chybu a overi, ze test_hover_pobidka.js ji CHYTI (exit != 0).
Pouziti: _mutace_hover.py <prekryv webapp (kandidat, adresar s webapp/js/v3d/viewer3d.js)> [pocet paralelnich behu, vychozi 2]. Vyrobi kopie prekryvu (cp -a, symlinky zustavaji) v tmp a smaze je."""
import os, shutil, subprocess, sys, tempfile, concurrent.futures as cf
HERE = os.path.dirname(os.path.abspath(__file__))
CAND = os.path.abspath(sys.argv[1])
PAR = int(sys.argv[2]) if len(sys.argv) > 2 else 2
VIEWER = os.path.join(CAND, "webapp", "js", "v3d", "viewer3d.js")
src = open(VIEWER, encoding="utf-8").read()
# (nazev, oddil testu, stary text, novy text)
MUT = [
    ("bez vyzvy: hoverShow se nevola", "A", "if (opts.hoverHint === true) hoverShow(hoverMotionOf(h));", "/* mutace */"),
    ("text vzdy 'otevrete' (zavreny/otevreny)", "A", "var act = L.hover_close;\n      if (targetOf(id) < 0.5) {", "var act = L.hover_open;\n      if (targetOf(id) < 0.5) {"),
    ("bez textu strany", "A", "if (m.g && L['side_' + m.g]) name += ' · ' + L['side_' + m.g];", "/* mutace */"),
    ("box na vysuvu bez nazvu vysuvu", "A", "act = dep ? (L.hover_open + ': ' + motionLabel(motionById[dep], L)) : L.hover_open;", "act = L.hover_open;"),
    ("otaceni modelu prepocitava vyzvu na stare poloze (hoverBtn se nikdy nenastavi)", "A", ["if (e.pointerType === 'mouse') hoverBtn = e.buttons > 0;", "if (e.pointerType === 'mouse') hoverBtn = true;"], ["/* mutace */", "/* mutace */"]),
    ("tah nezrusi vyzvu", "A", "tap = null; logTap('drag'); clearHover(); }", "tap = null; logTap('drag'); }"),
    ("odjeti z platna vyzvu neschova", "A", "hoverPtr = null; clearHover(); } });", "hoverPtr = null; } });"),
    ("popisek zachytava mys (bez pointer-events)", "A", "hoverTip = el('div', 'v3d-tip');", "hoverTip = el('div', 'v3d-tip'); hoverTip.style.pointerEvents = 'auto';"),
    ("drateny vzhled ma podsviceni", "A", "if (!id || st.mode !== 'real' || !model) return;", "if (!id || !model) return;"),
    ("prepnuti vzhledu vyzvu neuklidi", "D", "    function applyMode(mode) {\n      clearHover();\n", "    function applyMode(mode) {\n"),
    ("dotyk spousti vyzvu", "C", "if (e.pointerType === 'mouse') { hoverBtn = false; hoverPtr = { x: e.clientX, y: e.clientY }; hoverSchedule(); }", "{ hoverBtn = false; hoverPtr = { x: e.clientX, y: e.clientY }; hoverSchedule(); }"),
    ("bez dovyhodnoceni posledni polohy mysi (kurzor ruka)", "D", "hoverSchedule(true); }   // popisek jede", "}   // popisek jede"),
    ("snimek nema uklid podsviceni", "D", "            clearHover();                                                                              // snimek bez podsviceni dilu pod mysi\n", ""),
    ("vymena modelu neuklidi vyzvu (ani v installModel, ani v applyMode)", "D", ["      clearHover();                                                // podsviceni a popisek patri starému modelu\n", "    function applyMode(mode) {\n      clearHover();\n"], ["", "    function applyMode(mode) {\n"]),
    ("podsviti se vsechny meshe, ne jen najety dil", "A", "if (!o.visible || motionOfMesh(o).motion !== id) return;", "if (!o.visible) return;"),
    ("hoverHint ignorovan (vyzva vzdy zapnuta)", "D", "if (opts.hoverHint === true) hoverShow(hoverMotionOf(h));", "hoverShow(hoverMotionOf(h));"),
]


def mutuj(a, b):
    """a, b: retezec nebo seznam retezcu (vice nahrad najednou); kazda kotva musi byt ve vieweru PRAVE jednou."""
    out = src
    for x, y in zip(a if isinstance(a, list) else [a], b if isinstance(b, list) else [b]):
        if out.count(x) != 1:
            return None, "KOTVA nenalezena (%d): %s" % (out.count(x), x[:50])
        out = out.replace(x, y)
    return out, None


def run(i, m):
    name, part, a, b = m
    mut, chyba = mutuj(a, b)
    if mut is None:
        return (i, name, None, chyba)
    d = tempfile.mkdtemp(prefix="mut_hover_")
    try:
        subprocess.check_call(["cp", "-a", CAND, d + "/c"])
        open(os.path.join(d, "c", "webapp", "js", "v3d", "viewer3d.js"), "w", encoding="utf-8").write(mut)
        env = dict(os.environ, WEB_DIR=os.path.join(d, "c", "webapp"), H_ONLY=part, SHOTS=os.path.join(d, "shots"))
        r = subprocess.run(["node", os.path.join(HERE, "test_hover_pobidka.js")], env=env, capture_output=True, text=True, timeout=900)
        fails = [l[:110] for l in r.stdout.splitlines() if l.startswith("[CHYBA]")]
        return (i, name, r.returncode != 0, "; ".join(f[8:60] for f in fails[:3]))
    finally:
        shutil.rmtree(d, ignore_errors=True)


if os.environ.get("MUT_ONLY"):         # jen vybrane mutace podle poradi v seznamu, napr. MUT_ONLY=5,10
    _idx = {int(x) for x in os.environ["MUT_ONLY"].split(",")}
    MUT = [x for i, x in enumerate(MUT) if i + 1 in _idx]

if os.environ.get("MUT_DRY"):          # jen kontrola, ze kazda kotva je ve vieweru prave jednou
    for i, (name, part, a_, b_) in enumerate(MUT):
        print("%2d %-80s %s" % (i + 1, name, mutuj(a_, b_)[1] or "ok"))
    sys.exit(0)

def zaklad(part):
    """Nemutovany kandidat musi projit (jinak by kazda mutace vypadala jako 'chycena')."""
    env = dict(os.environ, WEB_DIR=os.path.join(CAND, "webapp"), H_ONLY=part, SHOTS=tempfile.mkdtemp(prefix="mut_hover_shots_"))
    r = subprocess.run(["node", os.path.join(HERE, "test_hover_pobidka.js")], env=env, capture_output=True, text=True, timeout=900)
    shutil.rmtree(env["SHOTS"], ignore_errors=True)
    return part, r.returncode, [l[:140] for l in r.stdout.splitlines() if l.startswith("[CHYBA]")]


with cf.ThreadPoolExecutor(PAR) as ex:
    zakl = list(ex.map(zaklad, sorted({x[1] for x in MUT})))
for part, rc, fails in zakl:
    print("ZAKLAD oddil %s: %s" % (part, "OK" if rc == 0 else "SELHAL " + "; ".join(fails[:3])), flush=True)
if any(rc != 0 for _, rc, _ in zakl):
    print("Nemutovany test selhava - mutace nema smysl vyhodnocovat.")
    sys.exit(2)

bad = 0
with cf.ThreadPoolExecutor(PAR) as ex:
    for i, name, caught, info in ex.map(lambda t: run(*t), list(enumerate(MUT))):
        ok = caught is True
        bad += 0 if ok else 1
        print(("CHYCENO " if ok else "NECHYCENO ") + "%2d %s | %s" % (i + 1, name, info), flush=True)
print("%d/%d mutaci chyceno" % (len(MUT) - bad, len(MUT)))
sys.exit(1 if bad else 0)
