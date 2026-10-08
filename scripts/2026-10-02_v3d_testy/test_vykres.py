#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Testy api/vandr_vykres_nahrada.py (nahradni obrazky nabidky, 2026-10-02): kotovany 2D vykres z GLB, pohled z modelu, vyber
dvou snimku otocky. Bez DB, bez siete.

Spusteni: /opt/konfigurator/api/venv/bin/python scripts/2026-10-02_v3d_testy/test_vykres.py
Vstupy: <OUT>/out2/<karta>.offer.glb + <OUT>/out/<karta>.json (build_karty.py = zakaznicke v3d modely 7 karet a jejich geom.json),
        staticke GLB karet 4053 a 4482 (dosavadni Blender krok scripts/2026-09-28_vandr_offer_geometry.py, jen -b na CPU;
        postavi se jednou do <OUT>/static, kdyz chybi katalogove GLB nebo Blender, test se preskoci).

ROZMERY: cislo v obrazku se porovnava (a) s geom.json buildu (overall_size = [osa X, osa Z, osa Y] z vsech vrcholu, tedy stejne
cislo jako `rozmer_mm` odpovedi endpointu), (b) s NEZAVISLYM vypoctem AABB z GLB (vlastni kod testu: cteni accessoru, matice
uzlu, bez funkci modulu), (c) s rozmerem siluety v pixelech (rozliseni ~2,5 mm/px, tolerance 2 px).
"""
import json
import math
import os
import re
import struct
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True
import _cesty as CE  # noqa: E402
import _fakes as F  # noqa: E402

sys.path.insert(0, os.path.join(CE.REPO, "api"))
import vandr_vykres_nahrada as V  # noqa: E402

try:
    import numpy as np
    from PIL import Image
    import io
    HAVE = True
except ImportError:                                           # pragma: no cover
    HAVE = False

OUT2 = os.path.join(CE.OUT, "out2")
OUT1 = os.path.join(CE.OUT, "out")


# ---------------------------------------------------------------------------
# vyber_snimky_otocky (cista funkce)
# ---------------------------------------------------------------------------

def radky(azimuty, elevace=(-40, 0, 40), tiery=((1024, 95000), (2048, 300000))):
    out = []
    for e in elevace:
        for a in azimuty:
            for t, b in tiery:
                out.append({"elevation_deg": e, "azimuth_deg": a, "tier_px": t, "bytes": b,
                            "filename": "turntable-frames/1/b/%d/e%02d/a%03d.jpg" % (t, e, a)})
    return out


AZ_4482 = [0, 30, 150, 180, 210, 240, 270, 300, 330]
AZ_4053 = [0, 30, 60, 90, 120, 150, 180, 210, 330]


class TestVyberSnimku(unittest.TestCase):
    def az_el(self, r):
        return (r["azimuth_deg"], r["elevation_deg"], r["tier_px"])

    def test_karta_4482_predni_270(self):
        v = V.vyber_snimky_otocky(radky(AZ_4482), 270)
        self.assertEqual(self.az_el(v["a"]), (300, 0, 2048))          # 270 + 35 = 305 -> 300
        self.assertEqual(self.az_el(v["b"]), (240, 0, 2048))          # 270 - 35 = 235 -> 240

    def test_karta_4053_predni_90(self):
        v = V.vyber_snimky_otocky(radky(AZ_4053), 90)
        self.assertEqual(self.az_el(v["a"]), (120, 0, 2048))          # 125 -> 120
        self.assertEqual(self.az_el(v["b"]), (60, 0, 2048))           # 55 -> 60

    def test_predni_0_obchazi_nulu(self):
        v = V.vyber_snimky_otocky(radky(list(range(0, 360, 30))), 0)
        self.assertEqual((v["a"]["azimuth_deg"], v["b"]["azimuth_deg"]), (30, 330))      # 35 -> 30, -35 -> 325 -> 330

    def test_velky_soubor_mensi_tier(self):
        v = V.vyber_snimky_otocky(radky(AZ_4482, tiery=((1024, 95000), (2048, 2 * 1024 * 1024))), 270)
        self.assertEqual((v["a"]["tier_px"], v["b"]["tier_px"]), (1024, 1024))

    def test_jen_mensi_tier_nez_1024(self):
        v = V.vyber_snimky_otocky(radky(AZ_4482, tiery=((512, 20000),)), 270)
        self.assertEqual(v["a"]["tier_px"], 512)                       # nic lepsiho neni

    def test_elevace_nejblizsi_17_5(self):
        self.assertEqual(V.vyber_snimky_otocky(radky(AZ_4482, elevace=(-40, 0, 40)), 270)["a"]["elevation_deg"], 0)       # 17,5 vs 22,5
        self.assertEqual(V.vyber_snimky_otocky(radky(AZ_4482, elevace=(0, 20, 40)), 270)["a"]["elevation_deg"], 20)
        self.assertEqual(V.vyber_snimky_otocky(radky(AZ_4482, elevace=(15, 20)), 270)["a"]["elevation_deg"], 20)           # shoda -> vyssi
        self.assertEqual(V.vyber_snimky_otocky(radky(AZ_4482, elevace=(-40, 40)), 270)["a"]["elevation_deg"], 40)

    def test_soubor_chybi_dalsi_kandidat(self):
        chybi = {r["filename"] for r in radky(AZ_4482) if r["azimuth_deg"] == 300}
        v = V.vyber_snimky_otocky(radky(AZ_4482), 270, existuje=lambda f: f not in chybi)
        self.assertEqual(v["a"]["azimuth_deg"], 330)                   # 300 chybi (vsechny tiery), nejblizsi dalsi k 305 je 330
        self.assertEqual(v["b"]["azimuth_deg"], 240)
        # chybi jen tier 2048 -> pouzije se 1024 (soubory se kontroluji po jednom)
        chybi2 = {r["filename"] for r in radky(AZ_4482) if r["azimuth_deg"] == 300 and r["tier_px"] == 2048}
        v2 = V.vyber_snimky_otocky(radky(AZ_4482), 270, existuje=lambda f: f not in chybi2)
        self.assertEqual((v2["a"]["azimuth_deg"], v2["a"]["tier_px"]), (300, 1024))

    def test_chybi_vse_na_elevaci_zkusi_jinou(self):
        chybi = {r["filename"] for r in radky(AZ_4482) if r["elevation_deg"] == 0}
        v = V.vyber_snimky_otocky(radky(AZ_4482), 270, existuje=lambda f: f not in chybi)
        self.assertEqual(v["a"]["elevation_deg"], 40)

    def test_a_ruzne_od_b(self):
        v = V.vyber_snimky_otocky(radky([270, 300]), 270)               # k 235 i 305 je nejblizsi 270/300; b nesmi byt stejny snimek
        self.assertNotEqual(v["a"]["azimuth_deg"], v["b"]["azimuth_deg"])
        self.assertEqual((v["a"]["azimuth_deg"], v["b"]["azimuth_deg"]), (300, 270))

    def test_nic_nebo_malo(self):
        self.assertIsNone(V.vyber_snimky_otocky([], 270))
        self.assertIsNone(V.vyber_snimky_otocky(radky(AZ_4482), None))
        self.assertIsNone(V.vyber_snimky_otocky(radky([270]), 270))     # jen jeden azimut: dva ruzne pohledy nejsou
        self.assertIsNone(V.vyber_snimky_otocky([{"nic": 1}], 270))


# ---------------------------------------------------------------------------
# vykres_nares / pohled_z_modelu
# ---------------------------------------------------------------------------

def nezavisla_aabb(glb, vynechat_pomucky):
    """AABB (min, max) svetovych vrcholu z GLB - VLASTNI kod testu (nezavisly na modulu): JSON + BIN, matice uzlu, kvaternion
    zvlast; vynechat_pomucky = uzly/mesh/materialy jmenem logo/podlaha/fixarea/... (presna shoda po odstraneni (Clone) a cisel)."""
    off, js, bn = 12, None, None
    while off + 8 <= len(glb):
        ln, ct = struct.unpack_from("<II", glb, off)
        c = glb[off + 8: off + 8 + ln]
        if ct == 0x4E4F534A:
            js = json.loads(c.decode())
        elif ct == 0x004E4942:
            bn = c
        off += 8 + ln
    pom = re.compile(r"logo|podlaha|fixarea(_?red)?|legsbox|legshoverbox|karoserie|"
                     r"(top|bottom|side|front|back|left|right)?(drilling)?dimensions?", re.I)

    def je_pom(nm):
        if not isinstance(nm, str) or not vynechat_pomucky:
            return False
        s = re.sub(r"\((clone|instance)\)", "", nm, flags=re.I).strip()
        s = re.sub(r"([._\- ]*\d+)+$", "", s)
        return bool(pom.fullmatch(s))

    def mat(n):
        if "matrix" in n:
            m = [n["matrix"][i::4] for i in range(4)]
            return m
        t, q, s = n.get("translation", [0, 0, 0]), n.get("rotation", [0, 0, 0, 1]), n.get("scale", [1, 1, 1])
        x, y, z, w = q
        r = [[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
             [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
             [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]]
        return [[r[i][0] * s[0], r[i][1] * s[1], r[i][2] * s[2], t[i]] for i in range(3)] + [[0, 0, 0, 1]]

    def mm(a, b):
        return [[sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)] for i in range(4)]
    lo, hi = [1e18] * 3, [-1e18] * 3
    nodes = js["nodes"]
    stack = [(i, [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]) for i in js["scenes"][js.get("scene", 0)]["nodes"]]
    while stack:
        i, par = stack.pop()
        n = nodes[i]
        if je_pom(n.get("name")):
            continue
        M = mm(par, mat(n))
        stack += [(c, M) for c in n.get("children", [])]
        if "mesh" not in n or je_pom(js["meshes"][n["mesh"]].get("name")):
            continue
        for p in js["meshes"][n["mesh"]]["primitives"]:
            if "material" in p and je_pom(js["materials"][p["material"]].get("name")):
                continue
            a = js["accessors"][p["attributes"]["POSITION"]]
            bv = js["bufferViews"][a["bufferView"]]
            base = bv.get("byteOffset", 0) + a.get("byteOffset", 0)
            stride = bv.get("byteStride", 12)
            used = None
            if "indices" in p:                    # jen skutecne pouzite vrcholy (jako trojuhelniky)
                ia = js["accessors"][p["indices"]]
                ib = js["bufferViews"][ia["bufferView"]]
                fmt = {5121: "B", 5123: "H", 5125: "I"}[ia["componentType"]]
                sz = struct.calcsize(fmt)
                ioff = ib.get("byteOffset", 0) + ia.get("byteOffset", 0)
                used = set(struct.unpack_from("<" + fmt, bn, ioff + k * sz)[0] for k in range(ia["count"] // 3 * 3))
            for k in (used if used is not None else range(a["count"])):
                x, y, z = struct.unpack_from("<3f", bn, base + k * stride)
                for j in range(3):
                    v = M[j][0] * x + M[j][1] * y + M[j][2] * z + M[j][3]
                    lo[j], hi[j] = min(lo[j], v), max(hi[j], v)
    return lo, hi


@unittest.skipUnless(HAVE, "chybi numpy/PIL")
class TestVykres(unittest.TestCase):
    karty = []

    @classmethod
    def setUpClass(cls):
        cls.karty = sorted(f.split(".")[0] for f in os.listdir(OUT2)) if os.path.isdir(OUT2) else []
        cls.karty = [k for k in cls.karty if os.path.exists(os.path.join(OUT1, k + ".json"))]

    def glb(self, k):
        with open(os.path.join(OUT2, k + ".offer.glb"), "rb") as f:
            return f.read()

    def front(self, k):
        return F.ctx_fixture(k)["vandr_predni_azimut_deg"]

    def need_karty(self):
        if not self.karty:
            self.skipTest("chybi <OUT>/out2 (build_karty.py)")

    def test_rozmery_geom_nezavisly_vypocet_a_silueta_u_7_karet(self):
        self.need_karty()
        for k in self.karty:
            with self.subTest(karta=k):
                glb = self.glb(k)
                t = time.time()
                png, info = V.vykres_nares(glb, self.front(k))
                self.assertLess(time.time() - t, 4.0, "vykres ma byt do 3-4 s")
                with open(os.path.join(OUT1, k + ".json")) as fh:
                    geom = json.load(fh)
                X, Z, Y = geom["overall_size"]          # rozmer_mm = [osa X, osa Z, osa Y]
                fx, fz = info["front"]
                osa_x_je_hloubka = abs(fx) > abs(fz)
                sirka_geom, hloubka_geom = (Z, X) if osa_x_je_hloubka else (X, Z)
                self.assertLessEqual(abs(info["sirka_mm"] - sirka_geom), 1, (k, info["sirka_mm"], sirka_geom))
                self.assertLessEqual(abs(info["hloubka_mm"] - hloubka_geom), 1, (k, info["hloubka_mm"], hloubka_geom))
                self.assertLessEqual(abs(info["vyska_mm"] - Y), 1, (k, info["vyska_mm"], Y))
                # nezavisly vypocet z GLB (vlastni kod testu)
                lo, hi = nezavisla_aabb(glb, vynechat_pomucky=True)
                ext = [hi[j] - lo[j] for j in range(3)]
                s2, h2 = (ext[2], ext[0]) if osa_x_je_hloubka else (ext[0], ext[2])
                self.assertLessEqual(abs(info["sirka_mm"] - s2), 1)
                self.assertLessEqual(abs(info["hloubka_mm"] - h2), 1)
                self.assertLessEqual(abs(info["vyska_mm"] - ext[1]), 1)
                self.assertEqual(info["front_zdroj"], "spec")

    def test_vzhled_obrazku_a_koty(self):
        self.need_karty()
        k = self.karty[0]
        png, info = V.vykres_nares(self.glb(k), self.front(k))
        im = Image.open(io.BytesIO(png))
        self.assertEqual(im.size, (1600, 1000))
        self.assertEqual(im.mode, "RGB")
        a = np.asarray(im).astype(int)
        self.assertEqual(tuple(a[2, 2]), (255, 255, 255))                       # bile pozadi
        sedy = (a[:, :, 0] == a[:, :, 1]) & (a[:, :, 1] == a[:, :, 2])
        self.assertGreater(int((sedy & (a[:, :, 0] >= 190) & (a[:, :, 0] <= 240)).sum()), 50000)    # svetle seda plocha
        self.assertGreater(int((sedy & (a[:, :, 0] <= 60)).sum()), 1000)                              # tmavy obrys
        modra = (a[:, :, 2] > a[:, :, 0] + 40)
        self.assertGreater(int(modra.sum()), 1500)                               # kotovaci cary a texty
        # pocet kot = 4 (sirka, vyska v narysu; hloubka, vyska v bokorysu) a texty jen povolene
        cisla = [t for t in info["texty"] if re.fullmatch(r"\d+ mm", t)]
        self.assertEqual((info["pocet_kot"], len(cisla)), (4, 4))
        self.assertEqual(sorted(cisla)[0:0], [])
        self.assertEqual(set(info["texty"]) - set(cisla), {"Nárys", "Bokorys", "Rozměry sestavy v mm"})
        self.assertEqual(sorted(int(c.split()[0]) for c in cisla),
                         sorted([info["sirka_mm"], info["vyska_mm"], info["hloubka_mm"], info["vyska_mm"]]))

    def test_silueta_v_pixelech_odpovida_rozmerum(self):
        self.need_karty()
        for k in self.karty[:3]:
            with self.subTest(karta=k):
                png, info = V.vykres_nares(self.glb(k), self.front(k))
                a = np.asarray(Image.open(io.BytesIO(png))).astype(int)
                sedy = (a[:, :, 0] == a[:, :, 1]) & (a[:, :, 1] == a[:, :, 2]) & (a[:, :, 0] < 250)
                sedy[:100, :] = False                                            # titulky Narys / Bokorys
                sedy[935:, :] = False                                            # poznamka dole
                s = info["mm_na_px"]
                lev = sedy[:, : int(1600 * 0.66)]                               # narys
                ys, xs = np.nonzero(lev)
                self.assertLessEqual(abs((xs.max() - xs.min() + 1) * s - info["sirka_mm"]), 2.5 * s)
                self.assertLessEqual(abs((ys.max() - ys.min() + 1) * s - info["vyska_mm"]), 2.5 * s)
                prav = sedy[:, int(1600 * 0.66):]
                ys2, xs2 = np.nonzero(prav)
                # bokorys: stiny podepisu (cisla v kote jsou modra, ne seda), vyska stejna, hloubka sedi
                self.assertLessEqual(abs((xs2.max() - xs2.min() + 1) * s - info["hloubka_mm"]), 2.5 * s)

    def test_deterministicky_a_bez_metadat(self):
        self.need_karty()
        k = self.karty[-1]
        glb = self.glb(k)
        p1, i1 = V.vykres_nares(glb, self.front(k))
        p2, i2 = V.vykres_nares(glb, self.front(k))
        self.assertEqual(p1, p2)
        chunks = []
        off = 8
        while off < len(p1):
            ln = struct.unpack_from(">I", p1, off)[0]
            chunks.append(p1[off + 4: off + 8])
            off += 12 + ln
        self.assertFalse({b"tEXt", b"iTXt", b"zTXt", b"eXIf"} & set(chunks), chunks)
        ctx = F.ctx_fixture(k)
        unity = {x["unity_id"] for x in ctx["komponenty"]} | {d["unity_id"] for x in ctx["komponenty"] for d in x["dily"]}
        for u in unity:
            self.assertNotIn(u.encode(), p1)
            self.assertFalse([t for t in i1["texty"] if u in t])
        for t in i1["texty"]:
            self.assertIsNone(re.search(r"vandr|logo|clone|unity", t, re.I))

    def test_bez_front_pouzije_azimut_nebo_odhad(self):
        self.need_karty()
        k = self.karty[0]
        glb = self.glb(k)
        _p, i0 = V.vykres_nares(glb, self.front(k))
        # spec.front ma prednost pred azimutem z DB (kdyby se lisily, plati to, co postavil build)
        _p, i1 = V.vykres_nares(glb, (self.front(k) + 90) % 360)
        self.assertEqual((i1["front_zdroj"], i1["front"]), ("spec", i0["front"]))
        self.assertEqual(i1["sirka_mm"], i0["sirka_mm"])

    def test_pohled_z_modelu(self):
        self.need_karty()
        k = self.karty[0]
        glb = self.glb(k)
        t = time.time()
        png = V.pohled_z_modelu(glb, (self.front(k) + 35) % 360, 17.5)
        self.assertLess(time.time() - t, 4.0)
        im = Image.open(io.BytesIO(png))
        self.assertEqual(im.size, (1280, 960))
        a = np.asarray(im).astype(int)
        self.assertEqual(tuple(a[2, 2]), (255, 255, 255))
        self.assertGreater(int((a[:, :, 0] < 250).sum()), 30000)                  # model je videt
        self.assertEqual(png, V.pohled_z_modelu(glb, (self.front(k) + 35) % 360, 17.5))
        self.assertNotEqual(png, V.pohled_z_modelu(glb, (self.front(k) - 35) % 360, 17.5))
        az = V.predni_azimut_deg(glb, None)
        self.assertLess(abs(((az - self.front(k) + 180) % 360) - 180), 1.0)

    def test_necitelny_glb(self):
        for bad in (b"", b"neni glb", b"glTF" + b"\x00" * 30):
            with self.assertRaises(V.VykresChyba):
                V.vykres_nares(bad, 270)


@unittest.skipUnless(HAVE and os.path.exists(CE.BLENDER), "chybi numpy/PIL/Blender")
class TestStatickyModel(unittest.TestCase):
    """DOSAVADNI staticky GLB (Blender geometrie bez v3d) jeste obsahuje logo a podlahu: vykres je nesmi ukazat ani zapocitat."""
    KARTY = {"4053": ("vandr/vd_export_regalova_vestavba_peugeot_expert_l2_4d7c063e.glb", 90),
             "4482": ("vandr/vd_export_regalova_vestavba_vw_crafter_l3h3_fwd_f543dc7a.glb", 270)}

    @classmethod
    def staticky(cls, k):
        glb_file, _az = cls.KARTY[k]
        zdroj = os.path.join(CE.KATALOG, glb_file)
        if not os.path.isfile(zdroj):
            return None
        d = os.path.join(CE.OUT, "static")
        os.makedirs(d, exist_ok=True)
        out, geom = os.path.join(d, k + ".glb"), os.path.join(d, k + ".geom.json")
        if not (os.path.exists(out) and os.path.exists(geom)):
            import subprocess
            gs = os.path.join(CE.REPO, "scripts", "2026-09-28_vandr_offer_geometry.py")
            if not os.path.exists(gs):
                gs = "/opt/konfigurator/scripts/2026-09-28_vandr_offer_geometry.py"
            r = subprocess.run([CE.BLENDER, "-b", "-P", gs, "--", zdroj, geom, out], capture_output=True, text=True, timeout=120,
                               env={"PATH": os.environ.get("PATH", "/usr/bin:/bin")})
            if "GEOM_OK" not in r.stdout:
                return None
        return open(out, "rb").read(), json.load(open(geom))

    def test_bez_loga_a_podlahy_rozmery_nezavisle_overene(self):
        for k, (_f, az) in self.KARTY.items():
            with self.subTest(karta=k):
                st = self.staticky(k)
                if st is None:
                    self.skipTest("staticky GLB karty %s nejde postavit (katalog/Blender)" % k)
                glb, geom = st
                png, info = V.vykres_nares(glb, az)
                self.assertEqual(info["front_zdroj"], "azimut")
                lo, hi = nezavisla_aabb(glb, vynechat_pomucky=True)
                lo2, hi2 = nezavisla_aabb(glb, vynechat_pomucky=False)
                ext = [hi[j] - lo[j] for j in range(3)]
                ext_vse = [hi2[j] - lo2[j] for j in range(3)]
                fx, fz = info["front"]
                hlou = abs(fx) > abs(fz)
                self.assertLessEqual(abs(info["sirka_mm"] - (ext[2] if hlou else ext[0])), 1)
                self.assertLessEqual(abs(info["hloubka_mm"] - (ext[0] if hlou else ext[2])), 1)
                self.assertLessEqual(abs(info["vyska_mm"] - ext[1]), 1)
                # dosavadni overall_size (geom.json) = AABB VSEHO vcetne loga/podlahy
                self.assertLessEqual(abs(geom["overall_size"][0] - ext_vse[0]), 1)
                self.assertLessEqual(abs(geom["overall_size"][1] - ext_vse[2]), 1)
                # model skutecne nese pomucky (jinak by test nic neprokazoval) a vykres je nema
                g, _b = V._read_glb(glb)
                pom = [n["name"] for n in g["nodes"] if V._pomucka(n.get("name"))]
                self.assertTrue(pom, "staticky GLB ma obsahovat logo/podlahu")
                T_vse = sum(1 for _ in pom)
                self.assertGreater(T_vse, 0)
                self.assertLessEqual(info["sirka_mm"], max(ext_vse[0], ext_vse[2]) + 1)
                self.assertLessEqual(info["hloubka_mm"], min(ext_vse[0], ext_vse[2]) + 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
