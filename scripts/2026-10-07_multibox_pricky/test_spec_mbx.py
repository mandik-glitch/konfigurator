#!/usr/bin/env python3
"""Test validace multiboxu ve spec v3d (api/v3d_glb.py): validate_spec, spec_pivot_refs, sanitize + final_check na hotovem GLB (bot8, 2026-10-07).
Spusteni: python3 test_spec_mbx.py <cesta_k_api> <slozka_out2_z_build_karty>"""
import copy, os, sys
API, FIX = sys.argv[1], sys.argv[2]
sys.path.insert(0, API)
sys.dont_write_bytecode = True
import v3d_glb  # noqa: E402
bad = total = 0


def t(name, cond, detail=None):
    global bad, total
    total += 1
    bad += 0 if cond else 1
    print("[%s] %s%s" % ("OK   " if cond else "CHYBA", name, "" if cond or detail is None else " | %r" % (detail,)))


def chyba(spec, pivots=None):
    try:
        v3d_glb.validate_spec(spec, pivots)
        return None
    except v3d_glb.V3DError as e:
        return str(e)


raw = open(os.path.join(FIX, "4921.offer.glb"), "rb").read()
spec0 = v3d_glb.embedded_spec(raw)
S = lambda: copy.deepcopy(spec0)
B = lambda: copy.deepcopy(spec0["mbx"][0])

t("vzorovy spec 4921 projde", chyba(S()) is None)
out = v3d_glb.validate_spec(S())
t("mbx se zachova (22 multiboxu + 3 podnosy supliku) a ma kanonicky tvar vcetne skupiny", len(out["mbx"]) == 25 and set(out["mbx"][0]) == {"id", "min", "max", "e", "p", "n", "s", "sk"}, sorted(out["mbx"][0]))
t("skupiny: police (druh 1), 2 vysuvy s multiboxy (druh 2) a 3 sufliky s podnosy (druh 4)", sorted({(b["s"], b["sk"]) for b in out["mbx"]}) == [(1, 1), (2, 2), (3, 4), (4, 2), (5, 4), (6, 4)] and [sum(1 for b in out["mbx"] if b["sk"] == k) for k in (1, 2, 4)] == [8, 14, 3], sorted({(b["s"], b["sk"]) for b in out["mbx"]}))
t("spec bez mbx: ve vystupu klic mbx neni (bajtove stejny jako driv)", "mbx" not in v3d_glb.validate_spec({k: v for k, v in S().items() if k != "mbx"}))
s = S(); s["mbx"] = []
t("prazdne mbx: klic ve vystupu neni", "mbx" not in v3d_glb.validate_spec(s))
t("pivot refs obsahuji mbx.p", {b["p"] for b in out["mbx"]} <= v3d_glb.spec_pivot_refs(out))
t("pivot refs: pivot, na ktery odkazuje JEN mbx, se zahrne", v3d_glb.spec_pivot_refs({"mbx": [{"id": "b01", "p": "p77"}, {"id": "b02", "p": None}]}) == {"p77"})

# povolene volitelne klice g a n, p = null
s = S(); s["mbx"][0]["g"] = "left"; s["mbx"][1]["p"] = None; del s["mbx"][2]["n"]
o = v3d_glb.validate_spec(s)
t("g, p=null a chybejici n jsou platne", o["mbx"][0]["g"] == "left" and o["mbx"][1]["p"] is None and "n" not in o["mbx"][2])

zle = {
    "duplicitni id": lambda s: s["mbx"][1].update(id=s["mbx"][0]["id"]),
    "id bez tvaru b<cislo>": lambda s: s["mbx"][0].update(id="box1"),
    "id s diakritikou/mezerou": lambda s: s["mbx"][0].update(id="b 1"),
    "id neni retezec": lambda s: s["mbx"][0].update(id=1),
    "min > max": lambda s: s["mbx"][0].update(min=[1000.0, 0, 0], max=[0, 1, 1]),
    "rozmer vetsi nez 3 m": lambda s: s["mbx"][0].update(max=[s["mbx"][0]["min"][0] + 4000, s["mbx"][0]["max"][1], s["mbx"][0]["max"][2]]),
    "min neni vektor 3": lambda s: s["mbx"][0].update(min=[0, 0]),
    "min obsahuje NaN": lambda s: s["mbx"][0].update(min=[float("nan"), 0, 0]),
    "min obsahuje text": lambda s: s["mbx"][0].update(min=["a", 0, 0]),
    "e = 0": lambda s: s["mbx"][0].update(e=0),
    "e = 2": lambda s: s["mbx"][0].update(e=2),
    "e = 1.0 (float)": lambda s: s["mbx"][0].update(e=1.0),
    "e = true": lambda s: s["mbx"][0].update(e=True),
    "chybi e": lambda s: s["mbx"][0].pop("e"),
    "chybi min": lambda s: s["mbx"][0].pop("min"),
    "cizi klic": lambda s: s["mbx"][0].update(jmeno="Multibox"),
    "p neni pivot": lambda s: s["mbx"][0].update(p="box"),
    "g neplatna": lambda s: s["mbx"][0].update(g="nahoru"),
    "n mimo rozsah": lambda s: s["mbx"][0].update(n=0),
    "n float": lambda s: s["mbx"][0].update(n=1.5),
    "s = 0": lambda s: s["mbx"][0].update(s=0),
    "s nad limit": lambda s: s["mbx"][0].update(s=1000),
    "s float": lambda s: s["mbx"][0].update(s=1.5),
    "s text": lambda s: s["mbx"][0].update(s="police"),
    "sk = 0": lambda s: s["mbx"][0].update(sk=0),
    "sk = 5": lambda s: s["mbx"][0].update(sk=5),
    "sk text (jmeno komponenty)": lambda s: s["mbx"][0].update(sk="police"),
    "mbx neni seznam": lambda s: s.update(mbx={"b01": 1}),
    "polozka neni objekt": lambda s: s["mbx"].append("b99"),
    "vic nez 400 boxu": lambda s: s.update(mbx=[dict(copy.deepcopy(spec0["mbx"][0]), id="b%d" % (i + 1)) for i in range(401)]),
}
for nm, zmena in zle.items():
    s = S()
    zmena(s)
    t("odmitne: %s" % nm, chyba(s) is not None)

for sk_ok in (1, 2, 3, 4):
    s = S()
    s["mbx"][0]["sk"] = sk_ok
    t("sk = %d je platny druh skupiny (1 police, 2 vysuv, 3 samostatne, 4 podnosy ocelovych supliku)" % sk_ok, chyba(s) is None and [b for b in v3d_glb.validate_spec(s)["mbx"] if b["id"] == s["mbx"][0]["id"]][0]["sk"] == sk_ok)

# existence pivotu (kdyz je seznam pivotu zadan)
piv = ({m["steps"][0]["p"] for m in spec0["motions"]} | {st["p"] for m in spec0["motions"] for st in m["steps"]} | {p for m in spec0["motions"] for p in m["pick"]}
       | {b["p"] for b in spec0["mbx"] if b["p"]} | {d["p"] for d in spec0["dims"] if d.get("p")})
t("mbx.p existuje v modelu", chyba(S(), piv) is None)
s = S(); s["mbx"][0]["p"] = "p99"
t("mbx.p neexistujici pivot odmitnut (pri znamych pivotech)", chyba(s, piv) is not None)

# sanitize na hotovem GLB: projde, spec zustane, pozdejsi zmeny hlidaji final_check a sanitize
san = v3d_glb.sanitize(raw, spec0)
es = v3d_glb.embedded_spec(san)
t("sanitize: mbx ve vystupu stejny", es["mbx"] == out["mbx"])
try:
    v3d_glb.final_check(v3d_glb.read_glb(san)[0])
    t("final_check na zakaznickem GLB s mbx", True)
except Exception as e:  # noqa: BLE001
    t("final_check na zakaznickem GLB s mbx", False, str(e)[:200])
g, bn = v3d_glb.read_glb(san)
g["scenes"][0]["extras"]["v3d"]["mbx"][0]["jmeno"] = "Multibox_Arc"
try:
    v3d_glb.final_check(g)
    t("final_check odmitne cizi klic v mbx", False)
except v3d_glb.V3DError:
    t("final_check odmitne cizi klic v mbx", True)
g, bn = v3d_glb.read_glb(san)
g["scenes"][0]["extras"]["v3d"]["mbx"][0]["id"] = "Multibox1"
try:
    v3d_glb.final_check(g)
    t("final_check odmitne zakazany retezec v id", False)
except v3d_glb.V3DError:
    t("final_check odmitne zakazany retezec v id", True)
for nm, mut in (("mbx.p na neexistujici pivot ve zdrojovem spec", lambda sp: sp["mbx"][0].update(p="p99")), ("mbx s e=3", lambda sp: sp["mbx"][0].update(e=3))):
    sp = S()
    mut(sp)
    try:
        v3d_glb.sanitize(raw, sp)
        t("sanitize odmitne: %s" % nm, False)
    except v3d_glb.V3DError:
        t("sanitize odmitne: %s" % nm, True)
import json as _json
txt = _json.dumps(v3d_glb.read_glb(san)[0])
t("v zakaznickem GLB neni zadne jmeno komponenty (Multibox, Police, Vysuv, Suplik, Default)", not any(w in txt for w in ("Multibox", "Police", "Vysuv", "Clone", "Suplik", "suplik", "Default")))
print("\n%d/%d OK" % (total - bad, total))
sys.exit(1 if bad else 0)
