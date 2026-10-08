"""Slouceni zakaznickych 3D modelu nabidky z VICE karet Vandr do jedne sceny (bot10, 2026-10-06; Robert: "chci aby v jedne online nabidce slo nabidnout dohromady levou
stranu, i pravou stranu i prepazku" - karty stran zustavaji samostatne, nabidka je spoji).

Vstup: zakaznicke GLB (kazde z JEDNE karty, uz po v3d_glb.sanitize: uzly n<i>, pivoty p<NN>, materialy m<NN>, popis v3d v scenes[0].extras.v3d). Modely stran jednoho vozu maji
STEJNE souradnice vozu (leva strana x > 0, prava x < 0, prepazka mezi nimi) - stavec je neposouva ani nevycentruje, takze se sloucenim jen spoji uzly, mesh, materialy, accessory a data.
Vystup: jeden GLB (znovu prosel v3d_glb.sanitize = stejna kontrola jako kazdy zakaznicky model) a slouceny spec:
  - pivoty dalsich zdroju se precisluji (p01 -> p<N+01>), id pohybu (m1 -> m<N+1>); kazdy pohyb dostane g = strana zdroje (left | right | bulkhead; viewer podle toho radi tlacitka pohybu do radku
    po stranach, Robert 2026-10-06) a poradove cislo n pohybu se prodluzuje jen v ramci TEZE strany a druhu (druha strana pocita "Suplik 1" znovu od jedne, ve sve rade),
  - box = sjednoceni boxu, front = z PRVNIHO zdroje (levy regal; viewer podle nej pozna strany: pohyby po cele / proti cele -> oboustranna scena), look/u/up musi byt shodne,
  - dims = koty VSECH zdroju za sebou (Robert 2026-10-06: koty se nikdy nedelaji na sestavu jako celek, kazda strana si drzi sve vlastni koty; vazba dims[].p na pivot se precisluje stejne jako pohyby),
  - mbx (multiboxy pro pricky; bot8 2026-10-07) = seznam VSECH zdroju: souradnice beze zmeny, pivot se precisluje stejne jako u pohybu, id b<NN> navazuji (b01 -> b<N+01>), kazdy box dostane
    g = strana zdroje, poradi n navazuje jen v ramci TEZE strany a cisla skupin s (police / sufliky) navazuji mezi zdroji,
  - materialy se NEslucuji (duplicity nevadi, sanitize je prejmenuje m<i>).
Jakakoli nesrovnalost (jiny look/jednotky, zdroj bez specu, prekroceni limitu) = V3DError (ValueError), nikdy tichy neuplny model.

Pouziti: glb, geom = sluc_glb([glb_leva, glb_prava, glb_prepazka], [geom_leva, geom_prava, geom_prepazka], ["left", "right", "bulkhead"]); strany jsou volitelne (bez nich odhad leva/prava z `front` a polohy
boxu, prepazka a nejasne se nehadaji = pohyb bez g); geom je dict ve tvaru geom.json stavece (overall_size, profily, warnings,
ctx_warnings, cache) - jen potrebna pole. Docs: docs/KONTRAKT_NABIDKA_3D.md (5g)."""
import copy
import re

import v3d_glb
from v3d_glb import V3DError

_PIV_RE = re.compile(r"p(\d{1,4})")
_MID_RE = re.compile(r"m(\d{1,4})")
_BID_RE = re.compile(r"b(\d{1,4})")
MAX_ZDROJU = 3
STRANY = ("left", "right", "bulkhead")          # = _SIDES v api/v3d_glb.py (motions[].g)


def _odhad_strany(spec):
    """Leva / prava podle toho, kam miri `front` a na ktere strane osy vozu lezi box zdroje (leva strana x > 0 s front -x, prava x < 0 s front +x); jinak None (nehada se)."""
    try:
        f = spec["front"]
        cx = (spec["box"]["min"][0] + spec["box"]["max"][0]) / 2.0
        if abs(f[0]) >= 0.7 and abs(cx) > 1.0:
            return "left" if cx > 0 else "right"
    except (KeyError, TypeError, IndexError):
        pass
    return None


def _piv_name(n):
    return "p%02d" % n if n < 100 else "p%d" % n


def _spec_of(g, i):
    sc = (g.get("scenes") or [None])[0]
    ex = sc.get("extras") if isinstance(sc, dict) else None
    spec = ex.get("v3d") if isinstance(ex, dict) else None
    if not isinstance(spec, dict):
        raise V3DError("model %d nema popis v3d (scenes[0].extras.v3d) - slucovat jdou jen zakaznicke modely s pohyby" % (i + 1))
    return spec


def sluc_glb(glbs, geoms=None, strany=None):
    """[GLB bytes] (+ [geom dict], + [strana]) -> (GLB bytes, geom dict). Viz modulovy docstring."""
    if not isinstance(glbs, (list, tuple)) or not (2 <= len(glbs) <= MAX_ZDROJU):
        raise V3DError("slucovat lze 2 az %d modelu" % MAX_ZDROJU)
    if geoms is not None and len(geoms) != len(glbs):
        raise V3DError("geom: pocet neodpovida poctu modelu")
    if strany is not None and (not isinstance(strany, (list, tuple)) or len(strany) != len(glbs) or any(x is not None and x not in STRANY for x in strany)):
        raise V3DError("strany: ocekavam seznam o delce poctu modelu s hodnotami %s (nebo None)" % (STRANY,))
    zdroje = []
    for i, data in enumerate(glbs):
        g, bn = v3d_glb.read_glb(data)
        if bn is None or len(g.get("buffers") or []) != 1:
            raise V3DError("model %d: ocekavam presne jeden buffer (GLB s BIN chunkem)" % (i + 1))
        spec = _spec_of(g, i)
        zdroje.append((g, bn, spec))
    s0 = zdroje[0][2]
    for i, (_g, _b, sp) in enumerate(zdroje[1:], 1):
        for k in ("v", "u", "up", "look"):
            if sp.get(k) != s0.get(k):
                raise V3DError("model %d: %s se lisi od prvniho modelu (%r != %r) - nelze sloucit" % (i + 1, k, sp.get(k), s0.get(k)))

    out = {"asset": {"version": "2.0"}, "scene": 0, "scenes": [{"nodes": []}], "nodes": [], "meshes": [], "materials": [], "accessors": [], "bufferViews": []}
    ext = []
    bin_all = bytearray()
    motions, boxes, dims, mbx = [], [], [], []
    max_piv = max_mid = max_bid = max_sk = 0
    max_nb = {}                                  # strana -> nejvyssi n multiboxu dosud
    max_n = {}                                   # (k, sub) -> nejvyssi n dosud
    max_g = -1
    for i, (g, bn, spec) in enumerate(zdroje):
        bl = g["buffers"][0].get("byteLength")
        if type(bl) is not int or bl > len(bn) or "uri" in g["buffers"][0]:
            raise V3DError("model %d: buffer nesedi s BIN chunkem" % (i + 1))
        bin_all += b"\x00" * (-len(bin_all) % 4)
        boff = len(bin_all)
        bin_all += bn[:bl]
        base_bv, base_acc, base_mat, base_mesh, base_node = (len(out[k]) for k in ("bufferViews", "accessors", "materials", "meshes", "nodes"))
        for bv in g.get("bufferViews") or []:
            nb = dict(bv)
            nb["buffer"] = 0
            nb["byteOffset"] = int(bv.get("byteOffset", 0)) + boff
            out["bufferViews"].append(nb)
        for a in g.get("accessors") or []:
            na = dict(a)
            if "sparse" in na:
                raise V3DError("model %d: accessor se sparse se neslucuje" % (i + 1))
            if "bufferView" in na:
                na["bufferView"] = int(na["bufferView"]) + base_bv
            out["accessors"].append(na)
        out["materials"].extend(copy.deepcopy(g.get("materials") or []))
        for m in g.get("meshes") or []:
            nm = copy.deepcopy(m)
            for p in nm.get("primitives") or []:
                p["attributes"] = {k: int(v) + base_acc for k, v in p["attributes"].items()}
                if "indices" in p:
                    p["indices"] = int(p["indices"]) + base_acc
                if "material" in p:
                    p["material"] = int(p["material"]) + base_mat
                if p.get("targets"):
                    raise V3DError("model %d: morph targety se neslucuji" % (i + 1))
            out["meshes"].append(nm)
        # pivoty: precislovani (prvni zdroj beze zmeny)
        piv = {}
        for n in g.get("nodes") or []:
            mt = _PIV_RE.fullmatch(n.get("name") or "")
            if mt:
                piv[n["name"]] = _piv_name(int(mt.group(1)) + max_piv)
        g_off = max_g + 1
        gs = strany[i] if strany is not None else _odhad_strany(spec)          # strana zdroje (viewer: radek tlacitek)
        zdroj_max_g = -1
        for n in g.get("nodes") or []:
            nn = copy.deepcopy(n)
            if "mesh" in nn:
                nn["mesh"] = int(nn["mesh"]) + base_mesh
            if nn.get("children"):
                nn["children"] = [int(c) + base_node for c in nn["children"]]
            if nn.get("name") in piv:
                nn["name"] = piv[nn["name"]]
            ex = nn.get("extras")
            if isinstance(ex, dict) and type(ex.get("g")) is int:
                zdroj_max_g = max(zdroj_max_g, ex["g"])
                nn["extras"] = dict(ex, g=ex["g"] + g_off)
            out["nodes"].append(nn)
        max_g = max(max_g, zdroj_max_g + g_off) if zdroj_max_g >= 0 else max_g
        out["scenes"][0]["nodes"].extend(int(r) + base_node for r in g["scenes"][0].get("nodes") or [])
        for e in g.get("extensionsUsed") or []:
            if e not in ext:
                ext.append(e)
        # pohyby: precislovani id, pivotu a n
        mid_off = max_mid
        nove_n = {}
        for m in spec.get("motions") or []:
            mt = _MID_RE.fullmatch(m.get("id") or "")
            if not mt:
                raise V3DError("model %d: neplatne id pohybu %r" % (i + 1, m.get("id")))
            nm = copy.deepcopy(m)
            nm["id"] = "m%d" % (int(mt.group(1)) + mid_off)
            for s in nm.get("steps") or []:
                if s.get("p") not in piv:
                    raise V3DError("model %d: pohyb %s odkazuje na pivot %r, ktery v modelu neni" % (i + 1, m["id"], s.get("p")))
                s["p"] = piv[s["p"]]
            nm["pick"] = [piv[p] for p in (nm.get("pick") or []) if p in piv]
            fam = (gs, m.get("k"), m.get("sub"))
            if gs is not None:
                nm["g"] = gs
            nm["n"] = int(m["n"]) + max_n.get(fam, 0)
            nove_n[fam] = max(nove_n.get(fam, 0), nm["n"])
            motions.append(nm)
        for fam, v in nove_n.items():
            max_n[fam] = max(max_n.get(fam, 0), v)
        max_mid += max([int(_MID_RE.fullmatch(m["id"]).group(1)) for m in spec.get("motions") or []] or [0])
        max_piv += max([int(_PIV_RE.fullmatch(k).group(1)) for k in piv] or [0])
        for d in spec.get("dims") or []:                         # koty strany: beze zmeny souradnic, jen pivot (je-li) pod novym jmenem
            nd = copy.deepcopy(d)
            if nd.get("p") is not None:
                if nd["p"] not in piv:
                    raise V3DError("model %d: kota odkazuje na pivot %r, ktery v modelu neni" % (i + 1, nd["p"]))
                nd["p"] = piv[nd["p"]]
            dims.append(nd)
        nove_nb = {}
        for b in spec.get("mbx") or []:                          # multiboxy strany: souradnice beze zmeny, pivot pod novym jmenem, id navazuji, strana zdroje
            mt = _BID_RE.fullmatch(b.get("id") or "")
            if not mt:
                raise V3DError("model %d: neplatne id multiboxu %r" % (i + 1, b.get("id")))
            nb = copy.deepcopy(b)
            if nb.get("p") is not None:
                if nb["p"] not in piv:
                    raise V3DError("model %d: multibox %s odkazuje na pivot %r, ktery v modelu neni" % (i + 1, b["id"], nb["p"]))
                nb["p"] = piv[nb["p"]]
            nb["id"] = "b%02d" % (int(mt.group(1)) + max_bid)
            if gs is not None:
                nb["g"] = gs
            if "n" in nb:
                nb["n"] = int(nb["n"]) + max_nb.get(gs, 0)
                nove_nb[gs] = max(nove_nb.get(gs, 0), nb["n"])
            if "s" in nb:                                        # cisla skupin (police / sufliky) navazuji mezi zdroji
                nb["s"] = int(nb["s"]) + max_sk
            mbx.append(nb)
        for gk, v in nove_nb.items():
            max_nb[gk] = max(max_nb.get(gk, 0), v)
        max_bid += max([int(_BID_RE.fullmatch(b["id"]).group(1)) for b in spec.get("mbx") or []] or [0])
        max_sk += max([int(b["s"]) for b in spec.get("mbx") or [] if "s" in b] or [0])
        bx = spec.get("box")
        if not (isinstance(bx, dict) and len(bx.get("min") or []) == 3 and len(bx.get("max") or []) == 3):
            raise V3DError("model %d: spec nema box" % (i + 1))
        boxes.append(bx)
    if len(motions) > 200:
        raise V3DError("slouceny model by mel %d pohybu (max 200)" % len(motions))
    if ext:
        out["extensionsUsed"] = ext
    out["buffers"] = [{"byteLength": len(bin_all)}]
    box = {"min": [min(b["min"][a] for b in boxes) for a in range(3)], "max": [max(b["max"][a] for b in boxes) for a in range(3)]}
    spec = {"v": s0["v"], "u": s0["u"], "up": list(s0["up"]), "front": list(s0["front"]), "box": box, "look": s0["look"], "dims": dims, "motions": motions}
    if mbx:
        spec["mbx"] = mbx
    out["scenes"][0]["extras"] = {"v3d": spec}
    glb = v3d_glb.sanitize(v3d_glb.write_glb(out, bytes(bin_all)), spec)         # stejna pojistka jako kazdy zakaznicky model (neprojde-li, V3DError)
    sp2 = v3d_glb.embedded_spec(glb)
    gm = {"overall_size": [round(sp2["box"]["max"][a] - sp2["box"]["min"][a], 1) for a in range(3)], "profily": [], "warnings": [], "ctx_warnings": [], "cache": {}}
    if geoms:
        for gd in geoms:
            gd = gd or {}
            gm["profily"].extend(gd.get("profily") or [])
            gm["warnings"].extend(gd.get("warnings") or [])
            gm["ctx_warnings"].extend(gd.get("ctx_warnings") or [])
        caches = [(gd or {}).get("cache") or {} for gd in geoms]
        gm["cache"] = {"hit": all(c.get("hit") for c in caches), "verze_buildu": caches[0].get("verze_buildu"), "klice": [c.get("klic") for c in caches]}
    return glb, gm
