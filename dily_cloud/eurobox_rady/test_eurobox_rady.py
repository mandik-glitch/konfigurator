"""Testy modulu eurobox_rady. Spuštění: python3 test_eurobox_rady.py  (z této složky, nebo jinak)
Bez pytestu, jen asserty. GLB euroboxů se čtou ze ../../webapp/katalog (jen v testech)."""
import copy
import json
import math
import os
import struct
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import eurobox_rady as E  # noqa: E402

KAT = os.path.join(HERE, "..", "..", "webapp", "katalog")
POCET = {"ok": 0}


def ok(podm, zprava=""):
    assert podm, zprava
    POCET["ok"] += 1


def blizko(a, b, tol=1e-3, zprava=""):
    ok(abs(a - b) <= tol, "%s: %r != %r (tol %g)" % (zprava, a, b, tol))


def radek(id_="R", typ="400x300", vyska=170, smer="delka", pocet=3, x=0.0, y=500.0, z=0.0, **kw):
    r = {"id": id_, "typ": typ, "vyska": vyska, "smer": smer, "pocet": pocet, "x": x, "y": y, "z": z}
    r.update(kw)
    return r


def chyby(v, kod=None):
    return [p for p in v["problemy"] if p["uroven"] == "chyba" and (kod is None or p["kod"] == kod)]


def kody(v):
    return {p["kod"] for p in v["problemy"]}


# ---------------------------------------------------------------------------------------------
# GLB (jen v testech)
# ---------------------------------------------------------------------------------------------
def nacti_glb(karta):
    return np.concatenate(nacti_glb_prim(os.path.join(KAT, "product_%d.glb" % karta)))


def nacti_glb_prim(cesta):
    """Trojúhelníky po primitivách (u dílů: jedno těleso = jedna primitiva)."""
    d = open(cesta, "rb").read()
    l = struct.unpack("<I", d[12:16])[0]
    j = json.loads(d[20:20 + l])
    off = 20 + l
    bl = struct.unpack("<I", d[off:off + 4])[0]
    b = d[off + 8:off + 8 + bl]
    out = []
    for m in j["meshes"]:
        for p in m["primitives"]:
            def acc(i):
                a = j["accessors"][i]
                bv = j["bufferViews"][a["bufferView"]]
                n = {"SCALAR": 1, "VEC3": 3}[a["type"]]
                dt = {5126: "<f4", 5123: "<u2", 5125: "<u4"}[a["componentType"]]
                o = bv.get("byteOffset", 0) + a.get("byteOffset", 0)
                st = bv.get("byteStride") or n * np.dtype(dt).itemsize
                return np.ndarray((a["count"], n), dt, b, o, (st, np.dtype(dt).itemsize)).astype(float)
            pos = acc(p["attributes"]["POSITION"])
            idx = acc(p["indices"])[:, 0].astype(int)
            out.append(pos[idx].reshape(-1, 3, 3))
    return out


_GLB = {}


def glb(karta):
    if karta not in _GLB:
        _GLB[karta] = nacti_glb(karta)
    return _GLB[karta]


def kvat_na_matici(q):
    x, y, z, w = q
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def glb_ve_svete(box):
    t = glb(box["part_id"])
    R = kvat_na_matici(box["quaternion"])
    return (t.reshape(-1, 3) @ R.T + np.array(box["position"])).reshape(-1, 3, 3)


_DIR = np.array([0.3711, 0.5173, 0.7691])
_DIR /= np.linalg.norm(_DIR)


def uvnitr_site(tris, P):
    """Sudá-lichá paprskem: body uvnitř uzavřené sítě (dutá nádoba = dutina je VNĚ)."""
    v0 = tris[:, 0]
    e1, e2 = tris[:, 1] - v0, tris[:, 2] - v0
    pv = np.cross(_DIR, e2)
    det = (e1 * pv).sum(1)
    ok_ = np.abs(det) > 1e-12
    idet = np.where(ok_, 1.0 / np.where(ok_, det, 1.0), 0.0)
    res = np.zeros(len(P), bool)
    dx, dy, dz = _DIR
    for i in range(0, len(P), 2000):
        Q = P[i:i + 2000]
        tx, ty, tz = (Q[:, None, k] - v0[None, :, k] for k in range(3))
        u = (tx * pv[None, :, 0] + ty * pv[None, :, 1] + tz * pv[None, :, 2]) * idet
        # q = t x e1
        qx = ty * e1[None, :, 2] - tz * e1[None, :, 1]
        qy = tz * e1[None, :, 0] - tx * e1[None, :, 2]
        qz = tx * e1[None, :, 1] - ty * e1[None, :, 0]
        v = (qx * dx + qy * dy + qz * dz) * idet
        tt = (qx * e2[None, :, 0] + qy * e2[None, :, 1] + qz * e2[None, :, 2]) * idet
        zasah = ok_[None] & (u >= 0) & (v >= 0) & (u + v <= 1) & (tt > 0)
        res[i:i + 2000] = zasah.sum(1) % 2 == 1
    return res


def mrizka_obb(t, krok):
    """Vzorkovací body (středy buněk) uvnitř OBB {stred, osy, pul}."""
    pul = np.array(t["pul"])
    n = np.maximum(1, np.ceil(2 * pul / krok).astype(int))
    osy = [(np.arange(k) + 0.5) / k * 2 - 1 for k in n]
    G = np.stack(np.meshgrid(*osy, indexing="ij"), -1).reshape(-1, 3) * pul
    V = float(np.prod(2 * pul / n))
    return np.array(t["stred"]) + G @ np.array(t["osy"]), V


def mrizka_valec(nz, krok):
    a, b = np.array(nz["a"], float), np.array(nz["b"], float)
    L = np.linalg.norm(b - a)
    ax = (b - a) / L
    p = np.cross(ax, [0, 1, 0])
    p = p / np.linalg.norm(p) if np.linalg.norm(p) > 1e-9 else np.array([0, 0, 1.0])
    q = np.cross(ax, p)
    r = nz["polomer"]
    k = np.arange(-r + krok / 2, r, krok)
    pts = []
    for s in np.arange(krok / 2, L, krok):
        for u in k:
            for v in k:
                if u * u + v * v <= r * r:
                    pts.append(a + ax * s + p * u + q * v)
    return np.array(pts), krok ** 3


def rozsah_osa(t, i):
    """(min, max) tvaru náhrady (kvádr nebo válec) ve světové ose i."""
    c = t["stred"][i]
    if t["typ"] == "valec":
        ax = np.array(t["osa"], float)
        ax /= np.linalg.norm(ax)
        r = abs(ax[i]) * t["delka"] / 2 + t["polomer"] * math.sqrt(max(0.0, 1 - ax[i] ** 2))
    else:
        r = float(sum(abs(np.array(t["osy"])[:, i]) * np.array(t["pul"])))
    return c - r, c + r


def objem_pruniku_s_glb(vysl, krok=3.0, vynech_role=()):
    """Objem (mm3) průniku originální geometrie GLB boxů s náhradami dílů a trubkami."""
    celkem = 0.0
    detaily = []
    dily = []
    for d in vysl["draha"]:
        for p in d["pasy"]:
            for m in p["moduly"]:
                dily.extend(("%s/draha" % d["rada"], t) for t in m["tvary_nahrady"])
    for k in vysl["koncovky"]:
        dily.extend((k["id"], t) for t in k["tvary_nahrady"])
    dily = [(n, t) for n, t in dily if t.get("role") not in vynech_role]
    trubky = [("trubka", n) for n in vysl["nosniky"]]
    for b in vysl["boxy"]:
        if not b.get("part_id"):
            continue
        tris = glb_ve_svete(b)
        lo, hi = tris.reshape(-1, 3).min(0), tris.reshape(-1, 3).max(0)
        for nazev, t in dily:
            if t["typ"] == "valec":
                ax = np.array(t["osa"], float)
                ax /= np.linalg.norm(ax)
                r = np.abs(ax) * t["delka"] / 2 + t["polomer"] * np.sqrt(np.maximum(0.0, 1 - ax ** 2))
                c = np.array(t["stred"])
                if np.any(c - r > hi) or np.any(c + r < lo):
                    continue
                nz = {"a": c - ax * t["delka"] / 2, "b": c + ax * t["delka"] / 2, "polomer": t["polomer"]}
                P, V = mrizka_valec(nz, krok)
            else:
                c, pul = np.array(t["stred"]), np.array(t["pul"])
                r = np.abs(np.array(t["osy"])).T @ pul
                if np.any(c - r > hi) or np.any(c + r < lo):
                    continue
                P, V = mrizka_obb(t, krok)
            m = np.all((P >= lo) & (P <= hi), axis=1)
            if m.any():
                n = int(uvnitr_site(tris, P[m]).sum())
                if n:
                    celkem += n * V
                    detaily.append((b["id"], nazev, n * V))
        for nazev, nz in trubky:
            a_, b_ = np.array(nz["a"]), np.array(nz["b"])
            if np.any(np.minimum(a_, b_) - nz["polomer"] > hi) or np.any(np.maximum(a_, b_) + nz["polomer"] < lo):
                continue
            P, V = mrizka_valec(nz, krok)
            m = np.all((P >= lo) & (P <= hi), axis=1)
            if m.any():
                n = int(uvnitr_site(tris, P[m]).sum())
                if n:
                    celkem += n * V
                    detaily.append((b["id"], nazev, n * V))
    return celkem, detaily


# ---------------------------------------------------------------------------------------------
# TESTY
# ---------------------------------------------------------------------------------------------
def test_vodorovna_rada_mezery_a_delka():
    for typ, dl, kr in (("400x300", 400.0, 300.0), ("600x400", 600.0, 400.0)):
        vys = sorted(E.BOXY[typ]["vysky"])
        for smer, a, b in (("delka", dl, kr), ("sirka", kr, dl)):
            for n in (1, 2, 5, 9):
                v = E.postav({"rady": [radek(typ=typ, vyska=vys[0], smer=smer, pocet=n, x=100, y=300, z=50)]})
                ok(not chyby(v), str(chyby(v)))
                bx = v["boxy"]
                ok(len(bx) == n)
                ok(not v["draha"] and not v["koncovky"] and not v["nosniky"], "vodorovná řada nemá dráhy")
                ok(len(v["opory"]) == 1)
                r = v["rady"][0]
                blizko(r["delka_rady_mm"], n * a + (n - 1) * 1.0, 1e-6, "délka řady")
                for i, bb in enumerate(bx):
                    mn, mx = bb["obalka"]["min"], bb["obalka"]["max"]
                    blizko(mx[0] - mn[0], a, 1e-3, "rozměr podél %s %s" % (typ, smer))
                    blizko(mx[2] - mn[2], b, 1e-3, "rozměr napříč")
                    blizko(mx[1] - mn[1], vys[0], 1e-3, "výška")
                    blizko(mn[1], 300, 1e-3)
                    if i:
                        blizko(mn[0] - bx[i - 1]["obalka"]["max"][0], 1.0, 1e-3, "mezera 1 mm")
                op = v["opory"][0]
                blizko(op["max"][0] - op["min"][0], n * a + (n - 1), 1e-2)
                blizko(op["y"], 300)


def test_strop_delky_rady_20_m():
    # výpočet: 400 mm -> 49 boxů (49*400+48 = 19648), 600 mm -> 33 boxů (33*600+32 = 19832)
    ok(E.max_pocet_boxu("400x300", "delka") == 49)
    ok(E.max_pocet_boxu("400x300", "sirka") == 66)      # 300 mm: 66*300+65 = 19865
    ok(E.max_pocet_boxu("600x400", "delka") == 33)
    ok(E.max_pocet_boxu("600x400", "sirka") == 49)      # 400 mm
    ok(E.max_pocet_boxu("400x300", "delka", mezera_mm=5) == 49)
    ok(E.max_pocet_boxu("400x300", "delka", max_delka_mm=1000) == 2)
    for typ in E.BOXY:
        vyska = sorted(E.BOXY[typ]["vysky"])[0]
        for smer in ("delka", "sirka"):
            for sklon in (0, 5):
                nmax = E.max_pocet_boxu(typ, smer)
                a = E.BOXY[typ]["dlouha" if smer == "delka" else "kratka"]
                ok(nmax * a + (nmax - 1) <= 20000 < (nmax + 1) * a + nmax)
                v = E.postav({"rady": [radek(typ=typ, vyska=vyska, smer=smer, pocet=nmax, y=400, sklon_deg=sklon)], "draha": "5275"})
                ok(not chyby(v), "řada na stropu musí projít: %s" % chyby(v))
                ok(v["rady"][0]["max_pocet_boxu"] == nmax)
                ok(v["rady"][0]["delka_rady_mm"] <= 20000)
                v = E.postav({"rady": [radek(typ=typ, vyska=vyska, smer=smer, pocet=nmax + 1, y=400, sklon_deg=sklon)], "draha": "5275"})
                ch = chyby(v, "RADA_PRILIS_DLOUHA")
                ok(len(ch) == 1 and ch[0]["id"] == ["R"], str(v["problemy"]))
                ok(len(v["boxy"]) == nmax + 1, "výstup se vrací i při překročení")
    # vlastní strop a kopie dlouhé řady
    v = E.postav({"rady": [radek(pocet=3, y=0)], "max_delka_rady_mm": 1202})
    ok(not chyby(v, "RADA_PRILIS_DLOUHA"))
    v = E.postav({"rady": [radek(pocet=4, y=0)], "max_delka_rady_mm": 1202})
    ok(chyby(v, "RADA_PRILIS_DLOUHA"))
    s = {"rady": [radek(id_="A", pocet=50, y=400, sklon_deg=5)], "draha": "5275"}
    for kam in ("vedle", "nad"):
        k = E.kopie_rady(s, "A", kam, 30, pocet=2)
        ok(len(k["rady"]) == 3)
        v = E.postav(k)
        ok(sorted(c["id"][0] for c in chyby(v, "RADA_PRILIS_DLOUHA")) == ["A", "A-1", "A-2"], "každá kopie nese chybu")
    s = {"rady": [radek(id_="A", pocet=49, y=400, sklon_deg=5)], "draha": "5275"}
    for kam in ("vedle", "nad"):
        v = E.postav(E.kopie_rady(s, "A", kam, 30, pocet=2))
        ok(not chyby(v), "kopie řady na stropu je v pořádku (%s): %s" % (kam, chyby(v)))


def test_mezera_jina():
    v = E.postav({"rady": [radek(pocet=3, y=0)], "mezera_boxu_mm": 5})
    bx = v["boxy"]
    blizko(bx[1]["obalka"]["min"][0] - bx[0]["obalka"]["max"][0], 5.0)


def test_vsechny_vysky_a_typy():
    for typ in E.BOXY:
        for vyska in E.BOXY[typ]["vysky"]:
            for smer in ("delka", "sirka"):
                for sklon in (0, 6):
                    for dr in ("5275", "5276"):
                        v = E.postav({"rady": [radek(typ=typ, vyska=vyska, smer=smer, pocet=2, y=400)],
                                      "sklon_deg": sklon, "draha": dr})
                        ok(not chyby(v), "%s %s %s %s %s: %s" % (typ, vyska, smer, sklon, dr, chyby(v)))
                        b = v["boxy"][0]
                        if typ == "400x300":
                            ok(b["part_id"] == E.BOXY[typ]["vysky"][vyska]["karta"] and not b["kvadr"])
                        else:
                            ok(b["part_id"] is None and b["kvadr"])
    # nenabízená výška: 270 u 600x400
    v = E.postav({"rady": [radek(typ="600x400", vyska=270)]})
    ok(chyby(v, "NEZNAMA_VYSKA"))
    v = E.postav({"rady": [radek(typ="400x300", vyska=270)]})
    ok(not chyby(v))


def test_sklony():
    # malý, střední a velký sklon + hraniční
    for th in (1.0, 3.0, 8.0, 14.0):
        v = E.postav({"rady": [radek(pocet=4, y=500, sklon_deg=th)], "draha": "5276"})
        ok(not chyby(v), str(chyby(v)))
        ok(len(v["nosniky"]) == 2)
        dolni = [n for n in v["nosniky"] if n["role"] == "dolni"][0]
        horni = [n for n in v["nosniky"] if n["role"] == "horni"][0]
        ok(dolni["a"][1] < horni["a"][1], "dolní nosník je níž")
        d = v["draha"][0]
        # rozdíl výšek trubek = vzdálenost trubek * sin(sklon)
        blizko(horni["a"][1] - dolni["a"][1], d["vzdalenost_trubek_mm"] * math.sin(math.radians(th)), 2e-3)
        blizko(horni["a"][0] - dolni["a"][0], d["vzdalenost_trubek_mm"] * math.cos(math.radians(th)), 2e-3)
    v = E.postav({"rady": [radek(y=500, sklon_deg=25)]})
    ok("SKLON_MIMO_ROZSAH" in kody(v))
    v = E.postav({"rady": [radek(y=500, sklon_deg=50)]})
    ok(chyby(v, "SKLON_NEPLATNY"))
    v = E.postav({"rady": [radek(y=500, sklon_deg=-3)]})
    ok(chyby(v, "SKLON_NEPLATNY"))
    # boxy ve skloněné řadě: mezera 1 mm podél sklonu, stejná orientace
    v = E.postav({"rady": [radek(pocet=4, y=500, sklon_deg=10)]})
    r = v["rady"][0]
    d = np.array(r["vektor_podel"])
    for i in range(1, 4):
        dc = np.array(v["boxy"][i]["stred"]) - np.array(v["boxy"][i - 1]["stred"])
        blizko(float(dc @ d), 401.0, 1e-3)
        blizko(float(np.linalg.norm(dc - (dc @ d) * d)), 0.0, 1e-3)
    blizko(r["sklon_deg"], 10.0)


def test_dolni_konec_dolni_nosnik_a_osy():
    for osa in ("x", "z"):
        for nk in ("predek", "zadek"):
            v = E.postav({"rady": [radek(pocet=3, x=1000, y=500, z=1000, sklon_deg=8)], "osa_rady": osa,
                          "nizsi_konec": nk, "draha": "5275"})
            ok(not chyby(v), str(chyby(v)))
            dolni = [n for n in v["nosniky"] if n["role"] == "dolni"][0]
            horni = [n for n in v["nosniky"] if n["role"] == "horni"][0]
            ok(dolni["a"][1] < horni["a"][1], "nižší konec dráhy je na nižším nosníku")
            i = 0 if osa == "x" else 2
            znam = 1 if nk == "predek" else -1
            ok((horni["a"][i] - dolni["a"][i]) * znam > 0, "horní nosník je dál po směru řady")
            # nosníky leží napříč
            j = 2 if osa == "x" else 0
            ok(dolni["a"][j] != dolni["b"][j] and dolni["a"][i] == dolni["b"][i])
            # první box začíná na x/z (u zadek na druhé straně)
            b0 = v["boxy"][0]
            if nk == "predek":
                blizko(b0["obalka"]["min"][i] if osa == "x" else b0["obalka"]["min"][2], 1000, 80)
            ok(v["rady"][0]["nizsi_konec"] == nk)


def test_rozlozeni_podle_zasunuti():
    for dr, delka, u_end, u_tip in (("5275", 271.66, 101.6, 135.83), ("5276", 255.04, 96.5, 127.52)):
        zakl = {"rady": [radek(pocet=5, y=500, sklon_deg=8)], "draha": dr}
        v = E.postav(zakl)
        d = v["draha"][0]
        L = 5 * 400 + 4
        blizko(v["rady"][0]["delka_rady_mm"], L)
        pitch = 2 * u_tip
        blizko(pitch, delka, 0.02, "modul = 2 x vzdálenost špičky ucha")
        m = math.ceil((L - 54.5 - 2 * u_end) / pitch) + 1
        ok(d["moduly_na_pas"] == m, "počet modulů %d != %d" % (d["moduly_na_pas"], m))
        blizko(d["delka_celku_mm"], m * pitch, 1e-2)
        s_bs, s_be = d["telo_od_do_mm"]
        blizko(s_bs, 54.5, 1e-6)                       # příruba prvního modulu 54,5 mm od líce zarážky
        blizko(s_be, 54.5 + 2 * u_end + (m - 1) * pitch, 1e-6)
        ok(s_be >= L and s_be - pitch < L, "poslední modul končí za řadou, o modul méně by nestačilo")
        # trubky: dolní 16,8 mm před zarážkou, horní 16,8 mm za líc horní koncovky (s_be + 54,5)
        blizko(d["vzdalenost_trubek_mm"], (s_be + 54.5 + 16.8) - (-16.8), 1e-6)
        # menší zasunutí => ucho se nedostane do štěrbiny / příruba narazí na konec koncovky
        v1 = E.postav(dict(zakl, zasun_draha_mm=45.0))
        ok(chyby(v1, "ZASUN_MIMO_DRAZKU") or chyby(v1, "KOLIZE"), str(v1["problemy"][:3]))
        v3 = E.postav(dict(zakl, zasun_draha_mm=70.0))
        ok(chyby(v3, "ZASUN_MIMO_DRAZKU"))
        # v rozsahu štěrbiny (Robertových 54 až 55 mm) bez chyb
        for z in (54.3, 54.5, 55.0, 58.0):
            ok(not chyby(E.postav(dict(zakl, zasun_draha_mm=z))), "zasunutí %s" % z)
        # koncovky: dolní 5282, horní 5281, po dvou (2 dráhy)
        role = {(k["role"], k["part_id"]) for k in v["koncovky"]}
        ok(role == {("dolni", 5282), ("horni", 5281)}, str(role))
        ok(len(v["koncovky"]) == 4)
        # odsazení dolní koncovky posune dolní trubku, počet modulů a horní trubku
        vo = E.postav(dict(zakl, odsazeni_koncovky_mm=60.0))
        blizko(vo["draha"][0]["telo_od_do_mm"][0], -60.0 + 54.5, 1e-6)
        ok(vo["draha"][0]["vzdalenost_trubek_mm"] >= d["vzdalenost_trubek_mm"] - 1e-9)


def test_dve_drahy_pod_radou():
    for dr in ("5275", "5276"):
        for smer in ("delka", "sirka"):
            v = E.postav({"rady": [radek(pocet=3, smer=smer, y=500, sklon_deg=7)], "draha": dr})
            ok(not chyby(v), str(chyby(v)))
            d = v["draha"][0]
            ok(len(d["pasy"]) == 2, "2 dráhy pod řadou")
            ok(d["part_id"] == int(dr))
            b = 300.0 if smer == "delka" else 400.0
            blizko(d["pasy"][1]["t"] - d["pasy"][0]["t"], d["roztec_mm"], 1e-6)
            blizko((d["pasy"][1]["t"] + d["pasy"][0]["t"]) / 2, b / 2, 1e-6, "symetricky")
            ok(d["roztec_vychozi"])
    # explicitní rozteč
    v = E.postav({"rady": [radek(pocet=3, y=500, sklon_deg=7)], "roztec_drah_mm": 150, "draha": "5275"})
    blizko(v["draha"][0]["roztec_mm"], 150)
    ok(not chyby(v))
    # rozteč mimo nožku => chyba
    v = E.postav({"rady": [radek(pocet=3, y=500, sklon_deg=7)], "roztec_drah_mm": 500, "draha": "5275"})
    ok(chyby(v, "DRAHA_MIMO_OPORU"))


def test_nozka_je_na_rovine_draze():
    """Z GLB: spodek nožky leží v rovině h=0 řady (horní plocha dráhy), tělo je uvnitř obálky."""
    for vyska, smer, th in ((120, "delka", 8), (170, "sirka", 0), (220, "delka", 12), (270, "sirka", 5), (320, "delka", 3)):
        v = E.postav({"rady": [radek(pocet=2, vyska=vyska, smer=smer, y=700, x=50, z=30, sklon_deg=th)]})
        r = v["rady"][0]
        P0 = np.array(r["zacatek"])
        d, c, n = (np.array(r[k]) for k in ("vektor_podel", "vektor_napric", "vektor_kolmo"))
        a = 400.0 if smer == "delka" else 300.0
        b = 300.0 if smer == "delka" else 400.0
        for i, bb in enumerate(v["boxy"]):
            tris = glb_ve_svete(bb).reshape(-1, 3)
            loc = (tris - P0) @ np.array([d, c, n]).T
            mn, mx = loc.min(0), loc.max(0)
            s0 = i * (a + 1)
            blizko(mn[2], 0.0, 0.02, "spodek nožky na h=0 (%d %s)" % (vyska, smer))
            blizko(mx[2], vyska, 0.02, "horní okraj")
            blizko(mn[0], s0 + 0.5, 0.02, "podél: model 1 mm menší než jmenovitě")
            blizko(mx[0], s0 + a - 0.5, 0.02)
            blizko(mn[1], 0.5, 0.02)
            blizko(mx[1], b - 0.5, 0.02)
            # nožka je dole: nejnižších ~12 mm je užších než tělo
            dolni = loc[loc[:, 2] < 0.2]
            blizko(dolni[:, 1].max() - dolni[:, 1].min(), 266.0 if smer == "delka" else 366.0, 0.05, "nožka napříč")


def test_boxy_nakloneny_spolu_s_drahami():
    """Závazné pravidlo: všechny boxy řady jsou nakloněné přesně jako dvojice drah, spodek nožky leží
    v rovině válečků OBOU drah (vzdálenost <= 0,1 mm), nikde mezera ani zanoření. Měří se jen z výstupu
    (kvaterniony, tvary náhrad dráhy) a z GLB, ne z interního rámu řady."""
    for dr in ("5275", "5276"):
        for osa, nk in (("x", "predek"), ("x", "zadek"), ("z", "predek")):
            for smer in ("delka", "sirka"):
                s = {"rady": [radek(id_="A", pocet=4, vyska=220, y=500, x=20, z=40, sklon_deg=7, smer=smer)],
                     "draha": dr, "osa_rady": osa, "nizsi_konec": nk}
                s = E.kopie_rady(s, "A", "vedle", 20)
                s = E.kopie_rady(s, "A", "nad", 100, sklon_deg=11, patro="horni")
                v = E.postav(s)
                ok(not chyby(v), str(chyby(v)))
                dcfg = E.DILY[int(dr)]
                roviny_rad = {}
                for r in v["rady"]:
                    th = math.radians(r["sklon_deg"])
                    ds = [d for d in v["draha"] if d["rada"] == r["id"]][0]
                    ok(len(ds["pasy"]) == 2)
                    # rovina válečků každé dráhy: normála = osa "nahoru" modulu v rámu světa, výška = horní plocha těla
                    roviny = []
                    for p in ds["pasy"]:
                        for m in p["moduly"]:
                            valce = [x for x in m["tvary_nahrady"] if x.get("role") == "valec"]
                            if dr == "5276":
                                ok(len(valce) <= 4)
                            for x in (valce or [m["tvary_nahrady"][0]]):
                                if x["typ"] == "valec":
                                    n = np.array(x["nahoru"])
                                    rov = float(n @ np.array(x["stred"]) + x["polomer"])     # horní hrana válečku
                                else:
                                    n = np.array(x["osy"][2])
                                    rov = float(n @ np.array(x["stred"]) + x["pul"][2])      # horní plocha dráhy
                                ok(n[1] > 0)
                                blizko(math.degrees(math.acos(min(1.0, n[1]))), r["sklon_deg"], 1e-4, "úhel dráhy")
                                roviny.append((n, rov))
                    n0, c0 = roviny[0]
                    roviny_rad[r["id"]] = (r["patro"], n0, c0)
                    for n, c in roviny:
                        blizko(float(np.linalg.norm(n - n0)), 0.0, 1e-6, "obě dráhy a všechny moduly v jedné rovině: normála")
                        blizko(c, c0, 5e-3, "obě dráhy a všechny moduly v jedné rovině: výška")
                    for b in [b for b in v["boxy"] if b["rada"] == r["id"]]:
                        R = kvat_na_matici(b["quaternion"])
                        osa_z_boxu = R[:, 2]      # lokální Z GLB = výška boxu
                        blizko(float(np.linalg.norm(osa_z_boxu - n0)), 0.0, 1e-5, "box je nakloněn přesně jako dráhy")
                        blizko(math.degrees(math.acos(min(1.0, osa_z_boxu[1]))), r["sklon_deg"], 1e-4, "úhel osy boxu")
                        tris = glb_ve_svete(b).reshape(-1, 3)
                        spodek = float((tris @ n0).min())
                        ok(abs(spodek - c0) <= 0.1, "nožka–válečky %.4f mm" % (spodek - c0))
                        # nožka je celá nad rovinou válečků (žádné zanoření) a vodorovná stěna spodku leží v ní
                        ok(spodek - c0 >= -0.1)
                # řady jednoho patra tvoří jednu šikmou rovinu (shodná normála a poloha roviny válečků)
                for p1, n1, c1 in roviny_rad.values():
                    for p2, n2, c2 in roviny_rad.values():
                        if p1 == p2:
                            blizko(float(np.linalg.norm(n1 - n2)), 0.0, 1e-6)
                            blizko(c1, c2, 5e-3, "rovina válečků patra")


KATALOG = os.path.join(HERE, "dily", "katalog")


def mesh_dilu(karta):
    return np.concatenate(nacti_glb_prim(os.path.join(KATALOG, "product_%d.glb" % karta)))


def mesh_ve_svete(tris, pos, quat, scale=(1.0, 1.0, 1.0)):
    R = kvat_na_matici(quat)
    V = tris.reshape(-1, 3) * np.array(scale)
    return (V @ R.T + np.array(pos)).reshape(-1, 3, 3)


def objem_pruniku_siti(A, B, krok=2.0, ramec=None):
    """Objem průniku dvou uzavřených sítí (A, B = pole trojúhelníků). `ramec` = (počátek, matice řádků d,c,n):
    sítě se převedou do rámu řady, kde jsou boxy kvádry (AABB boxu je přesná) - pokud se AABB sítí neprotínají,
    je průnik přesně 0, jinak se objem vzorkuje mřížkou `krok` v průniku AABB."""
    def do_ramce(T):
        if ramec is None:
            return T
        o, U = ramec
        return ((T.reshape(-1, 3) - o) @ U.T).reshape(-1, 3, 3)
    A, B = do_ramce(A), do_ramce(B)
    a, b = A.reshape(-1, 3), B.reshape(-1, 3)
    lo, hi = np.maximum(a.min(0), b.min(0)), np.minimum(a.max(0), b.max(0))
    if np.any(lo >= hi):
        return 0.0
    ax = [np.arange(l + krok / 2, h, krok) for l, h in zip(lo, hi)]
    if any(len(x) == 0 for x in ax):
        return 0.0
    P = np.stack(np.meshgrid(*ax, indexing="ij"), -1).reshape(-1, 3)
    m = uvnitr_site(B, P)
    if not m.any():
        return 0.0
    return float(uvnitr_site(A, P[m]).sum()) * krok ** 3


def objem_obb_v_siti(obb, sit, krok=0.5):
    """Horní odhad průniku kvádru náhrady (OBB z výstupu) s uzavřenou sítí: body kvádru uvnitř sítě."""
    P, V = mrizka_obb(obb, krok)
    lo, hi = sit.reshape(-1, 3).min(0), sit.reshape(-1, 3).max(0)
    m = np.all((P >= lo) & (P <= hi), axis=1)
    return float(uvnitr_site(sit, P[m]).sum()) * V if m.any() else 0.0


def test_katalog_glb_rozmery_a_stredy():
    """Katalogové GLB dílů: rozměr = zadání, střed obálky v počátku (změřeno, ne předpokládáno)."""
    hotovo = {5275: E.DILY[5275], 5276: E.DILY[5276], 5281: E.KONCOVKY[5281], 5282: E.KONCOVKY[5282]}
    for karta, cfg in hotovo.items():
        V = mesh_dilu(karta).reshape(-1, 3)
        mn, mx = V.min(0), V.max(0)
        for i in range(3):
            blizko(mx[i] - mn[i], cfg["rozmer_glb"][i], 0.015, "rozměr %d osa %d" % (karta, i))
            blizko((mx[i] + mn[i]) / 2, 0.0, 0.015, "střed obálky %d osa %d" % (karta, i))
    V = mesh_dilu(3673).reshape(-1, 3)
    mn, mx = V.min(0), V.max(0)
    ok(np.allclose(mx - mn, (28.0, 1000.0, 28.0), atol=0.02) and np.allclose((mx + mn) / 2, 0.0, atol=0.02), "trubka 3673")
    # 5276 z katalogu = 5276 ze STEPu od Roberta (stejná obálka; jiné sítění: vrcholy do 1,5 mm)
    S = np.concatenate(nacti_glb_prim(os.path.join(HERE, "dily", "5276.glb"))).reshape(-1, 3)
    K = mesh_dilu(5276).reshape(-1, 3)
    ok(np.allclose(S.max(0) - S.min(0), K.max(0) - K.min(0), atol=0.02))
    Ku, Su = np.unique(K.round(3), axis=0), np.unique(S.round(3), axis=0)
    d = np.concatenate([np.linalg.norm(Ku[i:i + 400, None] - Su[None], axis=2).min(1) for i in range(0, len(Ku), 400)])
    ok(d.max() < 1.6, "vrcholy katalogu a STEPu se liší nejvýš o %.2f mm" % d.max())


def test_konstanty_dilu_proti_meshi():
    # --- dráhy: ucho, příruba, rovina válečků --------------------------------------------------------
    for karta in (5275, 5276):
        c = E.DILY[karta]
        V = mesh_dilu(karta).reshape(-1, 3)
        i_u, i_v, i_w = c["osy"]["podel"], c["osy"]["nahoru"], c["osy"]["napric"]
        u, v_, w = V[:, i_u], V[:, i_v], V[:, i_w]
        ucho = V[(np.abs(u) > c["u_koncova_plocha"] + 1.5) & (v_ > c["v_ucho0"] - 0.05) & (v_ < c["v_ucho0"] + 1.55)]
        ok(len(ucho) > 20)
        blizko(ucho[:, i_v].min(), c["v_ucho0"], 0.01, "spodek ucha %d" % karta)
        blizko(ucho[:, i_v].max(), c["v_ucho0"] + 1.5, 0.01, "horní plocha ucha %d" % karta)
        blizko(np.abs(ucho[:, i_u]).max(), c["u_spicka"], 0.02, "špička ucha %d" % karta)
        blizko(np.abs(ucho[:, i_w]).max(), 17.15 if karta == 5275 else 17.45, 0.1, "šířka ucha %d" % karta)
        # kolizní náhrady obklopují ucho (kvádr "ucho" z DILY)
        for t_ in c["tvary"]:
            if t_[0] == "obb" and t_[1] == "ucho":
                lo, hi = np.array(t_[2]), np.array(t_[3])
                s_ = np.sign(lo[i_u] + hi[i_u])
                U = ucho[np.sign(ucho[:, i_u]) == s_]
                ok(np.all(U >= lo - 0.06) and np.all(U <= hi + 0.06), "kvádr ucha obsahuje ucho %d" % karta)
        # horní okraj válečků (bez disku a uch) = rovina; sítění smí ubrat < 0,2 mm
        telo = V[(np.abs(u) < c["u_koncova_plocha"] - 3.0)]
        if karta == 5276:
            telo = telo[telo[:, i_w] < c["kolo_w"][1] - 0.01]
        blizko(telo[:, i_v].max(), c["v_rovina"], 0.2, "horní okraj válečků %d" % karta)
    D = mesh_dilu(5276).reshape(-1, 3)
    disk = D[D[:, 0] > 9.8]
    blizko(disk[:, 1].max(), 30.865, 0.2, "horní okraj disku 5276")
    blizko(disk[:, 1].max() - E.DILY[5276]["v_rovina"], 14.5, 0.2, "disk přečnívá váleček o 14,5 mm")
    # --- koncovky ------------------------------------------------------------------------------------
    for karta in (5282, 5281):
        c = E.KONCOVKY[karta]
        V = mesh_dilu(karta).reshape(-1, 3)
        blizko(V[:, 2].max(), c["z_konec"], 0.02, "otevřený konec kapsy")
        zaklad = V[(V[:, 2] > 0) & (V[:, 1] < c["y_zaklad_horni"] + 0.01)]
        blizko(zaklad[:, 1].max(), c["y_zaklad_horni"], 0.02, "horní plocha základny")
        # kvádry náhrad obsahují všechny vrcholy (kromě štěrbiny, ta je uvnitř základny)
        lo = np.min([np.array(t_[2]) for t_ in c["tvary"]], axis=0)
        hi = np.max([np.array(t_[3]) for t_ in c["tvary"]], axis=0)
        ok(np.all(V >= lo - 0.07) and np.all(V <= hi + 0.07), "kvádry náhrad obsahují mesh koncovky %d" % karta)
    S = mesh_dilu(5282).reshape(-1, 3)
    stop = S[S[:, 1] > 0]
    blizko(stop[:, 2].max(), E.KONCOVKY[5282]["z_lic_zarazky"], 0.02, "líc zarážky")
    blizko(stop[:, 1].max(), 27.87, 0.02, "horní okraj zarážky")
    # --- hák: trubka Ø28 se zaklapne s přesahem ~0,2 mm na stranu (plech je pružný) ------------------
    for karta in (5282, 5281):
        c = E.KONCOVKY[karta]
        sit = mesh_dilu(karta)
        zt, yt = c["z_trubka"], c["y_trubka"]
        vol = 0.0
        dv = 0.1 * 0.1 * 1.0
        for z0, z1 in ((zt - 14.0 - 0.6, zt - 13.0), (zt + 13.0, zt + 14.0 + 0.6)):
            zs = np.arange(z0 + 0.05, z1, 0.1)
            ys = np.arange(yt - 14.0 + 0.05, yt + 14.0, 0.1)
            xs = np.arange(-16.5, 16.6, 1.0)
            P = np.stack(np.meshgrid(xs, ys, zs, indexing="ij"), -1).reshape(-1, 3)
            vnitr = (P[:, 1] - yt) ** 2 + (P[:, 2] - zt) ** 2 < 14.0 ** 2
            P = P[vnitr]
            vol += float(uvnitr_site(sit, P).sum()) * dv
        ok(5.0 < vol < 100.0, "přesah háku s trubkou %.1f mm3 (očekáváno ~40)" % vol)
        # strop háku: trubka se dotýká stropu, nic nad ním
        ys = np.arange(yt + 13.9, yt + 14.4, 0.05)
        ok(not uvnitr_site(sit, np.array([[0.3, y, zt] for y in ys[ys < yt + 14.0 - 1e-6]])).any(), "mezi trubkou a stropem háku není plech")


def sestava_mesh(v, r_id=None):
    """Světové sítě dílů řady z výstupu postav(): moduly dráhy, koncovky, trubky, boxy a rám řady."""
    r = v["rady"][0] if r_id is None else [x for x in v["rady"] if x["id"] == r_id][0]
    out = {"moduly": [], "koncovky": [], "trubky": [], "boxy": []}
    base = {5275: mesh_dilu(5275), 5276: mesh_dilu(5276), 5281: mesh_dilu(5281), 5282: mesh_dilu(5282)}
    for d in v["draha"]:
        if d["rada"] != r["id"]:
            continue
        for pas in d["pasy"]:
            for m in pas["moduly"]:
                out["moduly"].append((pas["index"], m["index"], mesh_ve_svete(base[m["part_id"]], m["position"], m["quaternion"]), m))
    for k in v["koncovky"]:
        if k["rada"] == r["id"]:
            out["koncovky"].append((k["role"], k["pas"], mesh_ve_svete(base[k["part_id"]], k["position"], k["quaternion"]), k))
    tr = mesh_dilu(3673)
    for n in v["nosniky"]:
        if r["id"] in n["rady"]:
            out["trubky"].append((n["role"], mesh_ve_svete(tr, n["position"], n["quaternion"], n["scale"]), n))
    for b in v["boxy"]:
        if b["rada"] == r["id"]:
            out["boxy"].append(glb_ve_svete(b))
    ramec = (np.array(r["zacatek"]), np.array([r["vektor_podel"], r["vektor_napric"], r["vektor_kolmo"]]))
    return out, ramec


def test_sestava_na_meshich():
    """Zero-objem kontroly na skutečných sítích: ucho x koncovka, moduly mezi sebou, dráha x box, koncovka x box,
    trubka x všechno kromě vlastního háku. Ucho 5275 je 1 mm nad válečky a stěny kapsy 5282 přečnívají rovinu válečků."""
    for dr in ("5276", "5275"):
        for odsaz in (0.0, 60.0):
            v = E.postav({"rady": [radek(pocet=2, vyska=170, y=500, sklon_deg=8)], "draha": dr, "odsazeni_koncovky_mm": odsaz})
            ok(not chyby(v), str(chyby(v)))
            S, ramec = sestava_mesh(v)
            # (1) ucho dráhy leží v kapse koncovky: objem kvádru ucha uvnitř meshe koncovky = 0 (kontakt na základně, vůle 0,35 mm ke stěnám)
            for role, pas, kt, k in S["koncovky"]:
                mod = [m for (p_, j_, mt, m) in S["moduly"] if p_ == pas and (j_ == 1 if role == "dolni" else j_ == len(v["draha"][0]["pasy"][0]["moduly"]))][0]
                for t_ in mod["tvary_nahrady"]:
                    if t_["role"] == "ucho":
                        zs = np.array(t_["stred"]) - np.array(k["position"])
                        # ucho je u koncovky jen jedním koncem: počítáme jen ucho, které je blíž koncovce
                        if np.linalg.norm(np.array(t_["stred"]) - np.array(k["position"])) > 120:
                            continue
                        ob = objem_obb_v_siti(t_, kt, 0.5)
                        ok(ob <= 5.0, "ucho %s v koncovce %s: %.2f mm3 (ucho má ~1500 mm3)" % (dr, role, ob))
            # (2) moduly mezi sebou (ucho na ucho): jen dotyk
            for pas in (1, 2):
                ms = [mt for (p_, j_, mt, m) in S["moduly"] if p_ == pas]
                for a_, b_ in zip(ms, ms[1:]):
                    blizko(objem_pruniku_siti(a_, b_, 3.0, ramec), 0.0, 1e-9, "sousední moduly")
            # (3) dráha x box
            for (p_, j_, mt, m) in S["moduly"][:6]:
                for bx in S["boxy"]:
                    vol = objem_pruniku_siti(bx, mt, 3.0, ramec)
                    if dr == "5276":
                        blizko(vol, 0.0, 1e-9, "5276 x box")
                    else:
                        ok(vol <= 1.2 * 2 * 34.0 * 34.0 * 1.0, "ucho 5275 pod boxem: %.0f mm3" % vol)   # ucho 34 x 34 x 1 mm nad válečky
            # (4) koncovka x box: nenulový jen u dolní koncovky přímo pod předkem boxu
            for role, pas, kt, k in S["koncovky"]:
                vol = sum(objem_pruniku_siti(bx, kt, 2.0, ramec) for bx in S["boxy"])
                if role == "dolni" and odsaz == 0.0:
                    ok(vol > 100.0, "dolní koncovka %s pod předkem boxu: %.0f mm3" % (dr, vol))
                else:
                    blizko(vol, 0.0, 1e-9, "koncovka %s x box (odsazení %s)" % (role, odsaz))
            # (5) trubka x box, trubka x dráha: nic (AABB v rámu řady jsou oddělené)
            for role, tt, n in S["trubky"]:
                for bx in S["boxy"]:
                    blizko(objem_pruniku_siti(bx, tt, 3.0, ramec), 0.0, 1e-9, "trubka x box")
                for (p_, j_, mt, m) in S["moduly"]:
                    blizko(objem_pruniku_siti(mt, tt, 3.0, ramec), 0.0, 1e-9, "trubka x dráha")
    # kalibrace měřidla: box posunutý o 10 mm do válečků dává nenulový objem
    v = E.postav({"rady": [radek(pocet=1, vyska=120, y=500, sklon_deg=8)], "draha": "5276", "odsazeni_koncovky_mm": 60.0})
    S, ramec = sestava_mesh(v)
    n = np.array(v["rady"][0]["vektor_kolmo"])
    bx = S["boxy"][0] - 10.0 * n
    tot = sum(objem_pruniku_siti(bx, mt, 3.0, ramec) for (_, _, mt, _) in S["moduly"])
    ok(tot > 1000.0, "měřidlo musí zachytit box zaražený do válečků (%.0f)" % tot)


def test_disky_drahy_5276():
    """Rozteč drah a disky 5276: box mezi disky, disk přečnívá váleček o 14,5 mm."""
    for smer in ("delka", "sirka"):
        for typ in E.BOXY:
            for osa, nk in (("x", "predek"), ("x", "zadek"), ("z", "predek")):
                vyska = sorted(E.BOXY[typ]["vysky"])[1]
                v = E.postav({"rady": [radek(typ=typ, vyska=vyska, smer=smer, pocet=3, y=500, x=30, z=70, sklon_deg=9)],
                              "draha": "5276", "osa_rady": osa, "nizsi_konec": nk})
                ok(not chyby(v), str(chyby(v)))
                b_ = (E.BOXY[typ]["kratka"] if smer == "delka" else E.BOXY[typ]["dlouha"])
                ds = v["draha"][0]
                blizko(ds["roztec_mm"], b_ - 2 * (9.88 - 1.0), 1e-6, "rozteč = b − 2·(9,88 − vůle)")
                ac = 2 if osa == "x" else 0
                z0 = v["boxy"][0]["obalka"]["min"][ac]
                z1 = v["boxy"][0]["obalka"]["max"][ac]
                for k, pas in enumerate(ds["pasy"]):
                    for m in pas["moduly"]:
                        valce = [x for x in m["tvary_nahrady"] if x["typ"] == "valec"]
                        ok([x["role"] for x in valce].count("valec") == 3 and [x["role"] for x in valce].count("disk") == 3)
                        for x in valce:
                            if x["role"] == "disk":
                                blizko(x["polomer"], 28.0, 1e-9)
                                blizko(x["delka"], 2.4, 1e-6)
                                lo, hi = rozsah_osa(x, ac)
                                if k == 0:
                                    ok(hi <= z0 - 1.0 + 1e-3, "disk vlevo vně boxu")
                                else:
                                    ok(lo >= z1 + 1.0 - 1e-3, "disk vpravo vně boxu")
                            else:
                                blizko(x["polomer"], 13.5, 1e-9)
                                blizko(x["delka"], 21.8, 1e-6)
                        dsk = [x for x in valce if x["role"] == "disk"][0]
                        val = [x for x in valce if x["role"] == "valec"][0]
                        n_ = np.array(dsk["nahoru"])
                        blizko(float(n_ @ np.array(dsk["stred"]) + dsk["polomer"]) - float(n_ @ np.array(val["stred"]) + val["polomer"]), 14.5, 1e-6)
                if typ == "400x300":
                    ok(any("3.8 mm" in p["text"] for p in v["problemy"] if p["kod"] == "OPORA_NOZKY_MALA"), str(v["problemy"]))
                else:
                    ok("OPORA_NOZKY_MALA" not in kody(v))       # kvádr bez nožky: válečky jsou celé pod boxem
    v = E.postav({"rady": [radek(pocet=2, y=500, sklon_deg=9)], "draha": "5276", "disk_vule_mm": 3})
    blizko(v["draha"][0]["roztec_mm"], 300 - 2 * (9.88 - 3.0), 1e-6)
    ok(not chyby(v), str(chyby(v)))
    # příliš malá rozteč: disky pod boxem = kolize
    v = E.postav({"rady": [radek(pocet=2, y=500, sklon_deg=9)], "draha": "5276", "roztec_drah_mm": 250})
    ok(chyby(v, "KOLIZE"))
    # box nad kapsou dolní koncovky: varování; od 54,3 mm odsazení už ne
    v = E.postav({"rady": [radek(pocet=2, y=500, sklon_deg=9)], "draha": "5276"})
    ok("BOX_NAD_KONCOVKOU" in kody(v))
    v = E.postav({"rady": [radek(pocet=2, y=500, sklon_deg=9)], "draha": "5276", "odsazeni_koncovky_mm": 54.3})
    ok("BOX_NAD_KONCOVKOU" not in kody(v), str(v["problemy"]))
    v = E.postav({"rady": [radek(pocet=2, y=500, sklon_deg=9)], "draha": "5275"})
    ok("UCHO_NAD_ROVINOU" in kody(v))


def test_kolize_glb_objem_pruniku():
    spec = {"rady": [radek(id_="A", pocet=3, vyska=220, y=500, sklon_deg=8)]}
    spec = E.kopie_rady(spec, "A", "vedle", 20)
    spec["rady"][1]["smer"] = "delka"
    for dr in ("5275", "5276"):
        for sm in ("delka", "sirka"):
            s = copy.deepcopy(spec)
            s["draha"] = dr
            s["odsazeni_koncovky_mm"] = 60.0     # box nad kapsou dolní koncovky: viz test_sestava_na_meshich
            for r in s["rady"]:
                r["smer"] = sm
            if sm == "sirka":
                s = E.kopie_rady({"rady": [s["rady"][0]], "draha": dr, "odsazeni_koncovky_mm": 60.0}, "A", "vedle", 20)
            v = E.postav(s)
            ok(not chyby(v), str(chyby(v)))
            obj, det = objem_pruniku_s_glb(v, vynech_role=("ucho",))     # ucho 5275 je 1 mm nad válečky (viz ODVOZENI.md)
            ok(obj <= 1000.0, "objem průniku GLB s dráhami/plechy/trubkami %.1f mm3: %s" % (obj, det[:3]))
            blizko(obj, 0.0, 1e-9, "objem průniku má být 0 (dotyk)")
    # kontrola metody: box zasunutý o 10 mm do dráhy dává nenulový objem (měřidlo funguje)
    v = E.postav({"rady": [radek(id_="A", pocet=1, vyska=120, y=500, sklon_deg=8)], "draha": "5275"})
    v2 = copy.deepcopy(v)
    bb = v2["boxy"][0]
    n = np.array(v2["rady"][0]["vektor_kolmo"])
    bb["position"] = list(np.array(bb["position"]) - 10.0 * n)
    obj2, _ = objem_pruniku_s_glb(v2)
    ok(obj2 > 1000.0, "měřidlo průniku musí zaznamenat posunutý box (%.1f)" % obj2)


def test_kopie_vedle():
    spec = {"rady": [radek(id_="A", pocet=4, vyska=220, y=500, sklon_deg=8, patro="P")], "draha": "5276"}
    for mez in (0, 1, 20, 150):
        s = E.kopie_rady(spec, "A", "vedle", mez, pocet=3)
        ok(len(s["rady"]) == 4)
        ok(len(spec["rady"]) == 1, "původní spec se nemění")
        v = E.postav(s)
        ok(not chyby(v), str(chyby(v)))
        ok({r["patro"] for r in v["rady"]} == {"P"})
        # čistá vzdálenost (konstrukce) mezi sousedními řadami = mezera: z obálek boxů a rozsahu drah
        ext = []
        for r in v["rady"]:
            ds = [d for d in v["draha"] if d["rada"] == r["id"]][0]
            ks = [k for k in v["koncovky"] if k["rada"] == r["id"]]
            tv_all = [t for k in ks for t in k["tvary_nahrady"]] + \
                [t for p in ds["pasy"] for m in p["moduly"] for t in m["tvary_nahrady"]]
            ac_lo = min(rozsah_osa(t, 2)[0] for t in tv_all)
            ac_hi = max(rozsah_osa(t, 2)[1] for t in tv_all)
            bxs = [b for b in v["boxy"] if b["rada"] == r["id"]]
            ac_lo = min(ac_lo, min(b["obalka"]["min"][2] for b in bxs))
            ac_hi = max(ac_hi, max(b["obalka"]["max"][2] for b in bxs))
            ext.append((ac_lo, ac_hi))
        for i in range(3):
            blizko(ext[i + 1][0] - ext[i][1], mez, 1e-3, "čistá mezera řad vedle sebe")
        # společný dolní nosník, horní podle délky řady (stejné délky => 1 horní)
        ok(sum(1 for n in v["nosniky"] if n["role"] == "dolni") == 1)
        ok(sum(1 for n in v["nosniky"] if n["role"] == "horni") == 1)
    # řady různé délky => jeden dolní, různé horní nosníky
    s = E.kopie_rady(spec, "A", "vedle", 20, pocet=2)
    s["rady"][1]["pocet"] = 2
    v = E.postav(s)
    ok(not chyby(v), str(chyby(v)))
    ok(sum(1 for n in v["nosniky"] if n["role"] == "dolni") == 1)
    ok(sum(1 for n in v["nosniky"] if n["role"] == "horni") == 2)
    dol = [n for n in v["nosniky"] if n["role"] == "dolni"][0]
    ok(set(dol["rady"]) == {"A", "A-1", "A-2"})
    # osa z
    sz = {"rady": [radek(id_="A", pocet=3, x=0, y=500, z=0, sklon_deg=8)], "osa_rady": "z", "draha": "5275"}
    s = E.kopie_rady(sz, "A", "vedle", 30)
    ok(s["rady"][1]["x"] > 300 and s["rady"][1]["z"] == 0, "při ose z se kopíruje v x")
    ok(not chyby(E.postav(s)))


def test_kopie_nad_a_patra_ruzny_sklon():
    base = {"rady": [radek(id_="A", pocet=4, vyska=170, y=300, sklon_deg=6, patro="dolni")], "draha": "5276"}
    base = E.kopie_rady(base, "A", "vedle", 20)
    for mez in (30, 80, 200):
        for sk in (None, 6, 12, 0):
            s = E.kopie_rady(base, "A", "nad", mez, sklon_deg=sk)
            v = E.postav(s)
            ok(not chyby(v), "mezera %s sklon %s: %s" % (mez, sk, chyby(v)))
            pat = {r["patro"] for r in v["rady"]}
            ok(len(pat) == 2)
            nahore = [p for p in pat if p != "dolni"][0]
            g = [m for m in v["mezery_pater"] if m["dole"] == "dolni" and m["nahore"] == nahore]
            ok(len(g) == 1, str(v["mezery_pater"]))
            # přesnost vzorkování: chyba <= krok*tan(sklon)
            tol = 2.0 * math.tan(math.radians(max(6, sk or 0))) + 0.01
            ok(abs(g[0]["mezera_mm"] - mez) <= tol, "mezera pater %s vs %s" % (g[0]["mezera_mm"], mez))
            if sk is not None:
                ok(any(r["sklon_deg"] == sk for r in v["rady"] if r["patro"] == nahore))
    # min_vyska_patra: posun dá požadovanou mezeru
    s = E.kopie_rady(base, "A", "nad", 50, sklon_deg=14)
    nahore = [r for r in s["rady"] if r["patro"] != "dolni"][0]["patro"]
    info = E.min_vyska_patra(s, "dolni", nahore, 120)
    ok(info["mezera_ted_mm"] is not None)
    for r in s["rady"]:
        if r["patro"] == nahore:
            r["y"] = info["y_min"][r["id"]]
    v = E.postav(s)
    g = [m for m in v["mezery_pater"] if m["dole"] == "dolni"][0]
    ok(abs(g["mezera_mm"] - 120) <= 2.0 * math.tan(math.radians(14)) + 0.01)
    # malá mezera => varování
    s = E.kopie_rady(base, "A", "nad", 3, sklon_deg=14)
    v = E.postav(s)
    ok("MALA_MEZERA_PATER" in kody(v))
    # více kopií nad sebou
    s = E.kopie_rady(base, "A", "nad", 60, pocet=3)
    v = E.postav(s)
    ok(not chyby(v), str(chyby(v)))
    ok(len({r["patro"] for r in v["rady"]}) == 4)
    ys = sorted({r["zacatek"][1] for r in v["rady"]})
    ok(len(ys) == 4 and all(b > a for a, b in zip(ys, ys[1:])))
    # sklon u kopie vedle zakázán
    try:
        E.kopie_rady(base, "A", "vedle", 10, sklon_deg=5)
        ok(False, "má selhat")
    except ValueError:
        ok(True)


def test_kopie_nad_pojmenovane_patro_a_vedle_v_nem():
    s = {"rady": [radek(id_="A", pocet=3, y=300, sklon_deg=6, patro="dolni")], "draha": "5275"}
    s = E.kopie_rady(s, "A", "vedle", 20)
    s = E.kopie_rady(s, "A", "nad", 80, sklon_deg=12, patro="horni")
    s = E.kopie_rady(s, "A-2", "vedle", 20)
    v = E.postav(s)
    ok(not chyby(v), str(chyby(v)))
    pat = {}
    for r in v["rady"]:
        pat.setdefault(r["patro"], []).append(r)
    ok(sorted(pat) == ["dolni", "horni"] and len(pat["dolni"]) == 2 and len(pat["horni"]) == 2)
    ok({r["sklon_deg"] for r in pat["horni"]} == {12.0} and {r["sklon_deg"] for r in pat["dolni"]} == {6.0})
    ok(len({r["zacatek"][1] for r in pat["horni"]}) == 1, "řady horního patra mají stejnou výšku")
    g = v["mezery_pater"][0]
    ok(abs(g["mezera_mm"] - 80) <= 2 * math.tan(math.radians(12)) + 0.01)
    ok(sum(1 for n in v["nosniky"] if n["role"] == "dolni" and n["patro"] == "horni") == 1)
    try:
        E.kopie_rady(s, "A", "nad", 10, patro="horni")
        ok(False)
    except ValueError:
        ok(True)


def test_patra_ruzny_sklon_ze_specu():
    spec = {"rady": [radek(id_="A", y=300, pocet=3, patro="p1"), radek(id_="B", y=900, pocet=3, patro="p2"),
                     radek(id_="C", y=1500, pocet=2, patro="p3", sklon_deg=11)],
            "sklon_deg": 5, "patra": {"p2": {"sklon_deg": 9}}, "draha": "5275"}
    v = E.postav(spec)
    ok(not chyby(v), str(chyby(v)))
    sk = {r["id"]: r["sklon_deg"] for r in v["rady"]}
    ok(sk == {"A": 5.0, "B": 9.0, "C": 11.0}, str(sk))
    # patro, jehož řady nesedí (různá výška) => varování
    spec2 = {"rady": [radek(id_="A", y=300, patro="p"), radek(id_="B", y=350, z=500, patro="p")], "sklon_deg": 5}
    ok("PATRO_NESEDI" in kody(E.postav(spec2)))


def test_kolize_se_hlasi():
    # dvě řady přes sebe
    v = E.postav({"rady": [radek(id_="A", y=500, sklon_deg=8), radek(id_="B", y=520, sklon_deg=8)]})
    ok(chyby(v, "KOLIZE"))
    # box ve vodorovné řadě přes jinou řadu
    v = E.postav({"rady": [radek(id_="A", y=100), radek(id_="B", y=150)]})
    ok(chyby(v, "KOLIZE"))
    # rozumná sestava bez kolize
    # (dráha 5276 přečnívá bok boxu o 11,6 mm, proto se sousední řada nesmí klást na 320 mm; správně přes kopie_rady)
    v = E.postav({"rady": [radek(id_="A", y=300, sklon_deg=8), radek(id_="B", y=300, z=320, sklon_deg=8)], "draha": "5276"})
    ok(chyby(v, "KOLIZE"), "dráhy sousedních řad vedle sebe na 320 mm se dotýkají")
    v = E.postav(E.kopie_rady({"rady": [radek(id_="A", y=300, sklon_deg=8)], "draha": "5276"}, "A", "vedle", 5))
    ok(not chyby(v, "KOLIZE"), str(chyby(v)))
    # podlaha
    v = E.postav({"rady": [radek(y=10, sklon_deg=8)]})
    ok("POD_PODLAHOU" in kody(v))


def test_nosniky_obsahuji_rozpeti():
    for dr, delta in (("5275", 17.63 - 17.12), ("5276", 16.365 - 11.665)):
        v = E.postav({"rady": [radek(id_="A", pocet=3, y=500, sklon_deg=8)], "presah_nosniku_mm": 25, "draha": dr})
        for n in v["nosniky"]:
            ok(n["polomer"] == 14.0 and n["part_id"] == 3673)
            ok(n["a"][0] == n["b"][0] and n["a"][1] == n["b"][1])
            # rozpětí pokrývá koncovky (šířka 38,4 mm) + přesah
            d = v["draha"][0]
            t0, t1 = d["pasy"][0]["t"] - 19.2 - 25, d["pasy"][1]["t"] + 19.2 + 25
            blizko(n["a"][2], t0, 5e-3)
            blizko(n["b"][2], t1, 5e-3)
            # trubka 3673 (válec Ø28 délky 1000, osa Y): měřítko Y = délka / 1000, osa Y modelu leží na ose nosníku
            L_ = float(np.linalg.norm(np.array(n["b"]) - np.array(n["a"])))
            blizko(n["scale"][1], L_ / 1000.0, 2e-6)
            R = kvat_na_matici(n["quaternion"])
            ax = (np.array(n["b"]) - np.array(n["a"])) / L_
            blizko(float(np.linalg.norm(R[:, 1] - ax)), 0.0, 1e-5)
            blizko(float(np.linalg.norm(np.array(n["position"]) - (np.array(n["a"]) + np.array(n["b"])) / 2)), 0.0, 5e-3)
        # osa trubky v rámu řady: dolní s = -16,8 před zarážkou, h = 10,75 - delta nad rovinou válečků (hák 5282/5281 změřený na GLB)
        r = v["rady"][0]
        P0, n_, d_ = (np.array(r[k]) for k in ("zacatek", "vektor_kolmo", "vektor_podel"))
        dolni = [n for n in v["nosniky"] if n["role"] == "dolni"][0]
        horni = [n for n in v["nosniky"] if n["role"] == "horni"][0]
        h_t = 10.75 - delta
        s_be = v["draha"][0]["telo_od_do_mm"][1]
        for nos, s_t in ((dolni, -16.8), (horni, s_be + 54.5 + 16.8)):
            bod = P0 + s_t * d_ + h_t * n_
            blizko(nos["a"][0], bod[0], 5e-3)
            blizko(nos["a"][1], bod[1], 5e-3)
        # trubka je nad rovinou válečků (osa 6 mm / 10,2 mm), tedy nad spodkem nožky boxu, ale před zarážkou
        ok(h_t > 0)


def test_deterministicke_a_json():
    spec = {"rady": [radek(id_="A", pocet=4, y=500, sklon_deg=8)], "draha": "5276"}
    spec = E.kopie_rady(spec, "A", "vedle", 20, 2)
    a = json.dumps(E.postav(spec), sort_keys=True)
    b = json.dumps(E.postav(copy.deepcopy(spec)), sort_keys=True)
    ok(a == b)
    json.loads(a)
    # quaterniony jsou jednotkové
    v = json.loads(a)
    for lst in (v["boxy"], v["koncovky"]):
        for o in lst:
            blizko(sum(x * x for x in o["quaternion"]), 1.0, 2e-3)
    for d in v["draha"]:
        for p in d["pasy"]:
            for m in p["moduly"]:
                blizko(sum(x * x for x in m["quaternion"]), 1.0, 2e-3)
    ok(set(v) >= {"boxy", "draha", "koncovky", "nosniky", "rozmery", "problemy", "parametry", "opory"})
    ok(v["parametry"]["zasun_draha_mm"] == 54.5 and v["parametry"]["draha"] == "5276")


def test_rozmery_obsahuji_vse():
    v = E.postav({"rady": [radek(id_="A", pocet=3, y=500, sklon_deg=8)], "draha": "5275"})
    mn, mx = v["rozmery"]["min"], v["rozmery"]["max"]
    for b in v["boxy"]:
        ok(all(b["obalka"]["min"][i] >= mn[i] - 1e-6 and b["obalka"]["max"][i] <= mx[i] + 1e-6 for i in range(3)))
    for n in v["nosniky"]:
        ok(n["a"][1] - 14 >= mn[1] - 1e-6)
        ok(min(n["a"][0], n["b"][0]) - 14 >= mn[0] - 1e-6)


def main():
    testy = [(k, f) for k, f in sorted(globals().items()) if k.startswith("test_") and callable(f)]
    for k, f in testy:
        f()
        print("OK  ", k)
    print("Všech %d testů prošlo (%d kontrol)." % (len(testy), POCET["ok"]))


if __name__ == "__main__":
    main()
