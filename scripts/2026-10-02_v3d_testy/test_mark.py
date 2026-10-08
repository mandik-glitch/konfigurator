#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Testy forenzni znacky api/v3d_mark.py (+ CLI scripts/v3d/v3d_mark_detect.py).

Spusteni:  api/venv/bin/python3 scripts/2026-10-02_v3d_testy/test_mark.py            (vse, ~ 6-10 min)
           MARK_FAST=1 api/venv/bin/python3 scripts/2026-10-02_v3d_testy/test_mark.py    (bez node/Blender a bez registrace s originalem; vychozi v run_all.sh)
           MARK_TABLE=<soubor.json> ...                          (ulozi tabulku odolnosti)
Potrebuje numpy + scipy (venv); node (three r128 z /opt/konfigurator/node_modules) a
Blender (/opt/blender-5.2/blender, jen -b, CPU) pro skupinu TestExterni.

Vstupy: <OUT>/out2/<karta>.offer.glb (zakaznicky model po v3d_glb.sanitize, vyrobi build_karty.py; adresar lze zmenit
MARK_CARDS=...), fixtures/native_offer.glb (nativni export, uzly s maticemi) a synteticke GLB
z tests/_mark_attacks.py. Zadne zapisy mimo <OUT>/mark/.

Geometrie (posun vrcholu, AABB, objem) se meri VLASTNIM kodem (test_sanitize.py: radkove matice,
kvaternion zvlast), ne funkcemi modulu, aby modul nemohl potvrdit sam sebe.

TestOdolnost + TestExterni plni TABULKU ODOLNOSTI (MARK_TABLE): kazdy radek ma PREDEPSANY vysledek
(detekce ano/ne) - i omezeni (radky s "ne") jsou testy: kdyby je schema nekdy zvladlo, test selze
a je potreba upravit dokumentaci v docstringu v3d_mark.py.
"""

import glob
import json
import math
import os
import re
import subprocess
import sys
import tempfile
import unittest

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _cesty as CE  # noqa: E402
ROOT = CE.REPO
for _p in (os.path.join(ROOT, "api"), HERE, os.path.join(ROOT, "scripts", "v3d")):
    sys.path.insert(0, _p)

import v3d_glb  # noqa: E402
import v3d_mark as M  # noqa: E402
import _mark_attacks as A  # noqa: E402
import test_sanitize as TS  # noqa: E402  (nezavisla geometrie)

SECRET = b"v3d-mark-test-secret-0123456789abcdef"
FAST = os.environ.get("MARK_FAST") == "1"
NODE = "/usr/bin/node" if os.path.exists("/usr/bin/node") else None
BLENDER = "/opt/blender-5.2/blender" if os.path.exists("/opt/blender-5.2/blender") else None
TMP = os.path.join(CE.OUT, "mark")
os.makedirs(TMP, exist_ok=True)


def _card_dir():
    for d in (os.environ.get("MARK_CARDS"), os.path.join(CE.OUT, "out2")):
        if d and glob.glob(os.path.join(d, "*.offer.glb")):
            return d
    return None


CARD_DIR = _card_dir()
CARDS = sorted(os.path.basename(p).split(".")[0] for p in glob.glob(os.path.join(CARD_DIR or "/nonexistent", "*.offer.glb")))
TABLE = []
_cache = {}


def card_glb(k):
    with open(os.path.join(CARD_DIR, "%s.offer.glb" % k), "rb") as fh:
        return fh.read()


def card_id(k):
    return 2000 + CARDS.index(k)


def marked(k):
    """Oznaceny model karty k (s verify=True - overeni uvnitr mark()), cache."""
    if k not in _cache:
        _cache[k] = M.mark_report(card_glb(k), card_id(k), SECRET)
    return _cache[k]


def native_sanitized():
    with open(os.path.join(CE.FIX, "native_offer.glb"), "rb") as fh:
        return v3d_glb.sanitize(fh.read(), None)


def row(skupina, test, ocekavano, ziskano, jistota=None, poznamka=""):
    TABLE.append({"skupina": skupina, "test": test, "ocekavano": ocekavano, "ziskano": ziskano,
                  "jistota": jistota, "poznamka": poznamka})


def det(glb, oid, original=None, kandidati=None, frames=True):
    """(nalezeno?, report) - nalezeno = detekce vratila PRESNE oid."""
    P = M.world_points(glb)
    Po = M.world_points(original) if original is not None else None
    r = M.detect_points(P, SECRET, kandidati, Po, frames=frames)
    return r["offer_id"] == oid, r


def need(test, cond, why):
    if not cond:
        test.skipTest(why)


class Base(unittest.TestCase):
    def setUp(self):
        need(self, CARDS, "<OUT>/out2/<karta>.offer.glb neni k dispozici (build_karty.py)")


# ---------------------------------------------------------------------------
# Jadro: znaceni, cteni, pojistka
# ---------------------------------------------------------------------------

class TestJadro(Base):
    def test_roundtrip_vsechny_karty(self):
        for k in CARDS:
            with self.subTest(karta=k):
                out, rep = marked(k)
                r = M.detect_report(out, SECRET)
                self.assertEqual(r["offer_id"], card_id(k))
                self.assertGreater(r["jistota"], 1 - 1e-8)
                self.assertEqual(r["rezim"], "bez originalu")
                self.assertEqual(r["flips"], 0)
                self.assertEqual(M.detect(out, SECRET)[0], card_id(k))
                self.assertGreater(rep["marked"] / rep["vertices"], 0.6)      # vetsina vrcholu nese znacku (4453: 68 %)
                self.assertTrue(rep["sanitize_idempotent"])

    def test_ruzna_cisla_nabidek(self):
        k = CARDS[0]
        d = card_glb(k)
        outs = {}
        for oid in (0, 1, 2, 4711, 65535, 2 ** 31, 2 ** 32 - 1):
            outs[oid] = M.mark(d, oid, SECRET)
            self.assertEqual(M.detect(outs[oid], SECRET)[0], oid, oid)
        self.assertEqual(len(set(outs.values())), len(outs), "ruzne nabidky = ruzne soubory")

    def test_deterministicke_a_klic(self):
        k = CARDS[-1]
        d = card_glb(k)
        a = M.mark(d, 99, SECRET)
        self.assertEqual(a, M.mark(d, 99, SECRET), "stejny vstup+id+klic = stejne bajty")
        b = M.mark(d, 99, b"jiny-tajny-klic-0123456789abcdef")
        self.assertNotEqual(a, b)
        self.assertEqual(M.detect(a, SECRET)[0], 99)
        self.assertEqual(M.detect(b, b"jiny-tajny-klic-0123456789abcdef")[0], 99)
        self.assertEqual(M.detect(a, b"jiny-tajny-klic-0123456789abcdef"), (None, 0.0), "cizi klic znacku necte")
        self.assertEqual(M.detect(b, SECRET), (None, 0.0))

    def test_secret_a_argumenty(self):
        d = card_glb(CARDS[0])
        for bad in (-1, 2 ** 32, 1.5, "7", None, True):
            with self.assertRaises((ValueError, TypeError), msg=repr(bad)):
                M.mark(d, bad, SECRET)
        with self.assertRaises(ValueError):
            M.mark(d, 1, b"kratky")
        with self.assertRaises(ValueError):
            M.mark(d, 1, "retezec-misto-bajtu-0123456789abcdef")
        with self.assertRaises(v3d_glb.V3DError):
            M.mark(b"glTF" + b"\x00" * 40, 1, SECRET)
        # get_secret: env > odvozeny z FLASK_SECRET_KEY > chyba
        hexs = "ab" * 32
        self.assertEqual(M.get_secret({"V3D_MARK_SECRET": hexs}, "flask"), bytes.fromhex(hexs))
        self.assertEqual(M.get_secret({"V3D_MARK_SECRET": "x" * 20}, None), b"x" * 20)
        self.assertEqual(M.get_secret({}, "flask-klic"), M.derive_secret("flask-klic"))
        self.assertEqual(M.derive_secret("flask-klic"), M.derive_secret(b"flask-klic"))
        self.assertNotEqual(M.derive_secret("a"), M.derive_secret("b"))
        with self.assertRaises(ValueError):
            M.get_secret({}, None)
        with self.assertRaises(ValueError):
            M.get_secret({"V3D_MARK_SECRET": "kratky"}, "flask")

    def test_posun_vrcholu_pod_0_05_mm(self):
        """Posun kazdeho vrcholu ve SVETOVYCH souradnicich (vlastni kod: radkove matice, kvaternion)."""
        for k in CARDS:
            with self.subTest(karta=k):
                out, rep = marked(k)
                before = world_vertices(card_glb(k))
                after = world_vertices(out)
                self.assertEqual(len(before), len(after))
                shift = np.linalg.norm(after - before, axis=1)
                self.assertLess(shift.max(), 0.05)
                self.assertLess(shift.max(), M.DELTA / 2 + 1e-3)
                self.assertAlmostEqual(shift.max(), rep["max_shift_mm"], delta=2e-4)
                frac = float(np.mean(shift > 0))
                self.assertGreater(frac, 0.6)
                row("neviditelnost", "max posun vrcholu %s" % k, "< 0.05 mm", "%.4f mm" % shift.max(),
                    poznamka="rms %.4f mm, %.0f %% vrcholu posunuto" % (math.sqrt(float(np.mean(shift ** 2))), 100 * frac))

    def test_meni_se_jen_position_a_minmax(self):
        for k in CARDS:
            with self.subTest(karta=k):
                out, _ = marked(k)
                g0, b0 = v3d_glb.read_glb(card_glb(k))
                g1, b1 = v3d_glb.read_glb(out)
                # JSON: jen min/max accessoru
                c0, c1 = json.loads(json.dumps(g0)), json.loads(json.dumps(g1))
                mm0 = [(a.get("min"), a.get("max")) for a in c0["accessors"]]
                for a in c0["accessors"] + c1["accessors"]:
                    a.pop("min", None)
                    a.pop("max", None)
                self.assertEqual(c0, c1, "JSON se lisi mimo min/max")
                # min/max accessoru POSITION = presne min/max dat; ostatni accessory (indices, NORMAL) bajt po bajtu
                pos_acc = {p["attributes"]["POSITION"] for m in g1["meshes"] for p in m["primitives"]}
                for i, a in enumerate(g1["accessors"]):
                    if i in pos_acc:
                        P = np.array(TS.positions(g1, b1, i), dtype=np.float32)
                        self.assertEqual(a["min"], [float(x) for x in P.min(0)])
                        self.assertEqual(a["max"], [float(x) for x in P.max(0)])
                    else:
                        self.assertEqual(TS.accessor_bytes(g0, b0, i), TS.accessor_bytes(g1, b1, i), "accessor %d" % i)
                        self.assertEqual((a.get("min"), a.get("max")), mm0[i])
                # topologie: pocet trojuhelniku a indexy
                self.assertEqual(tri_count(g0), tri_count(g1))
                self.assertEqual(len(b0), len(b1[:len(b0)]))

    def test_projde_pojistkou_a_je_idempotentni(self):
        for k in CARDS:
            with self.subTest(karta=k):
                out, _ = marked(k)
                spec = v3d_glb.embedded_spec(out)
                g, b = v3d_glb.read_glb(out)
                v3d_glb.final_check(g)
                v3d_glb.check_structure(g, b)
                v3d_glb.check_bin(g, b)
                again = v3d_glb.sanitize(out, spec)
                self.assertEqual(again, out, "sanitize(mark(x)) == mark(x) (bajty)")
                self.assertEqual(M.detect(again, SECRET)[0], card_id(k))
                # poradi opacne: mark(sanitize(x)) == sanitize(mark(x)) pro cele pipeline
                self.assertEqual(M.mark(v3d_glb.sanitize(card_glb(k), spec), card_id(k), SECRET, verify=False), out)

    def test_nativni_fixtura_s_maticemi(self):
        d = native_sanitized()
        out, rep = M.mark_report(d, 31415, SECRET)
        self.assertEqual(M.detect(out, SECRET)[0], 31415)
        self.assertLess(rep["max_shift_mm"], 0.05)
        self.assertTrue(rep["sanitize_idempotent"])
        w0, w1 = world_vertices(d), world_vertices(out)
        self.assertLess(np.linalg.norm(w1 - w0, axis=1).max(), 0.05)

    def test_uzly_s_rotaci_meritkem_a_zrcadlenim(self):
        for nodes in ([{"translation": [10, 20, 30], "rotation": [0.2, 0.3, 0.1, 0.9327], "scale": [1.0, 2.0, 0.5]}],
                      [{"translation": [10, 20, 30], "scale": [-1, 1, 1]}], [{}]):
            with self.subTest(uzel=nodes[0]):
                d = A.synth_glb(8000, 1, nodes)
                out, rep = M.mark_report(d, 5, SECRET)
                self.assertEqual(M.detect(out, SECRET)[0], 5)
                w0, w1 = world_vertices(d), world_vertices(out)
                self.assertLess(np.linalg.norm(w1 - w0, axis=1).max(), 0.05)

    def test_sdileny_mesh_se_neoznaci(self):
        """Mesh pouzity dvema uzly s ruznou polohou nejde oznacit ve svetove soustave -> preskoci se, bez dat chyba."""
        d = A.synth_glb(8000, 1, [{}, {"translation": [500, 0, 0]}])
        with self.assertRaises(v3d_glb.V3DError) as cm:
            M.mark(d, 5, SECRET)
        self.assertIn("POSITION accessor", str(cm.exception))
        # stejna transformace obou uzlu = jeden accessor, oznaci se
        d2 = A.synth_glb(8000, 1, [{}, {}])
        self.assertEqual(M.detect(M.mark(d2, 5, SECRET), SECRET)[0], 5)

    def test_maly_model_se_odmitne(self):
        d = A.synth_glb(300, 2)
        with self.assertRaises(v3d_glb.V3DError) as cm:
            M.mark(d, 5, SECRET)
        self.assertIn("prilis maly", str(cm.exception))

    def test_dvojite_znaceni(self):
        k = CARDS[2]
        out, _ = marked(k)
        self.assertEqual(M.mark(out, card_id(k), SECRET), out, "stejne id = beze zmeny")
        with self.assertRaises(v3d_glb.V3DError) as cm:
            M.mark(out, card_id(k) + 1, SECRET)
        self.assertIn("uz nese znacku", str(cm.exception))

    def test_bez_znacky_nic_nenajde(self):
        """Nemarkovane karty, cizi klic, nahodna mracna bodu: nikdy platny kod (falesne pozitivni)."""
        for k in CARDS:
            self.assertEqual(M.detect(card_glb(k), SECRET), (None, 0.0), k)
            out, _ = marked(k)
            self.assertEqual(M.detect(out, b"cizi-klic-0123456789abcdef-0123"), (None, 0.0), k)
        rng = np.random.RandomState(0)
        for i in range(40):
            P = rng.uniform(-1500, 2000, (20000, 3))
            self.assertIsNone(M.detect_points(P, SECRET, frames=(i < 4))["offer_id"], i)
        # zaokrouhlene (mrizkove) body - nejhorsi pripad pro kvantizaci
        g = np.mgrid[0:60, 0:60, 0:10].reshape(3, -1).T.astype(float) * 0.5
        self.assertIsNone(M.detect_points(g, SECRET)["offer_id"])

    def test_kandidati_matched_filter(self):
        """Pri hodne poskozenem modelu (hard-dekod neprojde kontrolou) pomuze seznam kandidatu."""
        need(self, "4918" in CARDS, "karta 4918 chybi")
        k = "4918"
        out, _ = marked(k)
        # prah hard-dekodu je u kazdeho buildu karty trochu jiny (4918 starsi build 0.034 mm, build s dorazy dvirek 0.036 mm):
        # hleda se nejnizsi sum (krok 0.001 mm), pri kterem hard-dekod bez kandidatu uz neprojde, a tam musi kandidati fungovat
        sigma = bad = None
        for i in range(0, 9):
            sigma = round(0.034 + 0.001 * i, 3)
            bad = A.add_noise(out, sigma)
            ok0, r0 = det(bad, card_id(k))
            if not ok0:
                break
        self.assertFalse(ok0, "hard-dekod bez kandidatu vydrzi i sum 0.042 mm - zkontrolovat tabulku odolnosti v docstringu v3d_mark.py")
        ok1, r1 = det(bad, card_id(k), kandidati=range(1, 6000))
        self.assertTrue(ok1, "kandidati nepomohli pri sumu %.3f mm" % sigma)
        self.assertEqual(r1["mode"], "kandidat")
        self.assertGreater(r1["jistota"], 1 - 1e-6)
        row("sum", "gauss %.3f mm, s kandidaty (matched filter)" % sigma, "ano", "ano" if ok1 else "ne", r1["jistota"],
            "bez kandidatu ne")
        # spatny seznam kandidatu nesmi dat falesny nalez
        ok2, r2 = det(bad, 7, kandidati=range(1, 6000))
        self.assertFalse(ok2)
        # kandidati nejsou potreba pri platnem kodu a nic nemeni
        good = marked(k)[0]
        self.assertEqual(M.detect(good, SECRET, kandidati=[1, 2, 3])[0], card_id(k))


# ---------------------------------------------------------------------------
# Neviditelnost: AABB, objem, kóty, trojuhelniky, nacteni three
# ---------------------------------------------------------------------------

class TestNeviditelnost(Base):
    def test_aabb_objem_koty_trojuhelniky(self):
        for k in CARDS:
            with self.subTest(karta=k):
                d0, (d1, rep) = card_glb(k), marked(k)
                w0, w1 = world_vertices(d0), world_vertices(d1)
                lo0, hi0, lo1, hi1 = w0.min(0), w0.max(0), w1.min(0), w1.max(0)
                daabb = float(max(np.abs(lo1 - lo0).max(), np.abs(hi1 - hi0).max()))
                self.assertLessEqual(daabb, 0.05)
                g0, b0 = v3d_glb.read_glb(d0)
                g1, b1 = v3d_glb.read_glb(d1)
                self.assertEqual(tri_count(g0), tri_count(g1))
                v0, v1 = mesh_volume(g0, b0), mesh_volume(g1, b1)
                rel = abs(v1 - v0) / abs(v0)
                self.assertLess(rel, 5e-4, "objem %.1f -> %.1f mm3" % (v0, v1))
                a0, a1 = mesh_area(g0, b0), mesh_area(g1, b1)
                # kóty L1 ze spec: delka usecky a-b vs rozmer AABB modelu podel osy kóty
                spec = v3d_glb.embedded_spec(d1)
                ex = []
                for dm in spec["dims"]:
                    if dm["l"] != 1:
                        continue
                    ax = int(np.argmax(np.abs(np.array(dm["b"]) - np.array(dm["a"]))))
                    e0, e1 = hi0[ax] - lo0[ax], hi1[ax] - lo1[ax]
                    self.assertLessEqual(abs(e1 - e0), 0.1)
                    if abs((e0 % 1.0) - 0.5) > 0.1:                 # mimo hranici zaokrouhleni
                        self.assertEqual(round(e0), round(e1), "kota L1 po zaokrouhleni")
                    ex.append((dm["t"], round(float(e0), 2), round(float(e1), 2)))
                bx = spec["box"]
                dev0 = max(max(abs(bx["min"][i] - lo0[i]), abs(bx["max"][i] - hi0[i])) for i in range(3))
                dev1 = max(max(abs(bx["min"][i] - lo1[i]), abs(bx["max"][i] - hi1[i])) for i in range(3))
                self.assertLessEqual(dev1, dev0 + 0.05 + 1e-6)
                self.assertLessEqual(dev1, 0.1 + 1e-6, "spec.box vs model po znaceni <= 0.1 mm")
                row("neviditelnost", "karta %s: AABB / objem / plocha / trojuhelniky" % k, "beze zmeny (v toleranci)",
                    "dAABB %.3f mm, dV %.4f %%, dS %.4f %%, trojuhelniku %d=%d" % (
                        daabb, 100 * rel, 100 * abs(a1 - a0) / a0, tri_count(g0), tri_count(g1)),
                    poznamka="spec.box vs model %.3f -> %.3f mm; koty L1 (text, rozmer pred/po) %s" % (dev0, dev1, ex))

    @unittest.skipUnless(NODE, "node neni")
    def test_three_r128_nacte_a_aabb_dilu_sedi(self):
        for k in CARDS[:3]:
            with self.subTest(karta=k):
                d1, _ = marked(k)
                p0, p1 = os.path.join(TMP, "%s_pred.glb" % k), os.path.join(TMP, "%s_po.glb" % k)
                for p, d in ((p0, card_glb(k)), (p1, d1)):
                    with open(p, "wb") as fh:
                        fh.write(d)
                r0, r1 = three_check(p0), three_check(p1)
                self.assertTrue(r0["ok"] and r1["ok"], (r0, r1))
                self.assertEqual(r0["names"], r1["names"])
                self.assertEqual(r0["sceneUserData"], r1["sceneUserData"])
                self.assertEqual(len(r0["prims"]), len(r1["prims"]))
                dev = max(max(abs(a - b) for a, b in zip(x, y)) for x, y in zip(r0["prims"], r1["prims"]))
                self.assertLessEqual(dev, 0.05 + 1e-3, "AABB mesh objektu v three")


# ---------------------------------------------------------------------------
# Odolnost (tabulka)
# ---------------------------------------------------------------------------

def _rows_blind(test, skupina, nazev, fn, cards, expect=True, original=False, frames=True, only_note=""):
    """Spusti utok fn(glb)->glb na kartach; prescribed vysledek expect (detekce presneho id)."""
    got_all = []
    for k in cards:
        out, _ = marked(k)
        att = fn(out)
        att = att[0] if isinstance(att, tuple) else att
        ok, r = det(att, card_id(k), original=card_glb(k) if original else None, frames=frames)
        got_all.append((k, ok, r["jistota"] if ok else 0.0, r.get("rezim"), r["cells"], round(r["mean_abs_vote"], 2)))
    n_ok = sum(1 for g in got_all if g[1])
    res = "ano %d/%d" % (n_ok, len(got_all)) if n_ok else "ne 0/%d" % len(got_all)
    row(skupina, nazev, "(zavisi na karte)" if expect is None else ("ano" if expect else "ne"), res,
        min(g[2] for g in got_all) if n_ok == len(got_all) else None,
        only_note or "; ".join("%s:%s/%d bunek" % (g[0], "ano" if g[1] else "ne", g[4]) for g in got_all[:3]))
    for g in got_all:
        if expect is not None:
            test.assertEqual(g[1], expect, "%s: %s karta %s (%s)" % (skupina, nazev, g[0], g))


class TestOdolnost(Base):
    def test_a_float32_zapis(self):
        _rows_blind(self, "a) ulozeni", "float32 round-trip souradnic (cteni+zapis)", A.float32_roundtrip, CARDS)

    def test_d_zaokrouhleni(self):
        for st in (0.01, 0.02, 0.05):
            _rows_blind(self, "d) zaokrouhleni", "zaokrouhleni na %g mm (bez originalu)" % st,
                        lambda g, st=st: A.round_local(g, st), CARDS)
        _rows_blind(self, "d) zaokrouhleni", "zaokrouhleni na 0.1 mm (bez originalu) - ZNAME OMEZENI",
                    lambda g: A.round_local(g, 0.1), CARDS, expect=False)

    def test_d_zaokrouhleni_s_originalem(self):
        need(self, not FAST, "MARK_FAST")
        for st in (0.1, 0.2):
            _rows_blind(self, "d) zaokrouhleni", "zaokrouhleni na %g mm + original (registrace)" % st,
                        lambda g, st=st: A.round_local(g, st), CARDS[:2], original=True, frames=False)

    def test_f_sum(self):
        for sg in (0.005, 0.01, 0.02, 0.03):
            _rows_blind(self, "f) sum", "gauss sigma %g mm (bez originalu)" % sg,
                        lambda g, sg=sg: A.add_noise(g, sg), CARDS)
        _rows_blind(self, "f) sum", "rovnomerny sum +-0.01 mm (bez originalu)",
                    lambda g: A.add_noise(g, 0.01, "uniform"), CARDS)
        _rows_blind(self, "f) sum", "gauss sigma 0.04 mm (bez originalu) - ZNAME OMEZENI",
                    lambda g: A.add_noise(g, 0.04), CARDS, expect=False)

    def test_f_sum_s_originalem(self):
        need(self, not FAST, "MARK_FAST")
        for sg, exp in ((0.04, True), (0.06, None), (0.1, False)):      # 0.06: 4918 ano (1 oprava bitu), 4453 ne
            _rows_blind(self, "f) sum", "gauss sigma %g mm + original" % sg,
                        lambda g, sg=sg: A.add_noise(g, sg), CARDS[:2], expect=exp, original=True, frames=False)

    def test_e_orez(self):
        need(self, "4918" in CARDS, "karta 4918 chybi")
        k = "4918"
        for f in (0.5, 0.2):
            _rows_blind(self, "e) orez", "ponechano %d %% dilu (nahodne, seed 3)" % (100 * f),
                        lambda g, f=f: A.keep_meshes(g, f)[0], CARDS)
        # extremni orez: vysledek zavisi na tom, kolik vrcholu zbylych dilu je (>= ~100 bunek)
        for seed, exp in ((12, True), (11, False)):
            out, _ = marked(k)
            gl, kept, total = A.keep_meshes(out, 0.03, seed=seed)
            ok, r = det(gl, card_id(k))
            row("e) orez", "ponechany %d z %d dilu (karta %s, seed %d)" % (kept, total, k, seed),
                "ano" if exp else "ne", "ano" if ok else "ne", r["jistota"] if ok else None,
                "%d unikatnich bunek (potreba >= 72, spolehlive >= ~200)" % r["cells"])
            self.assertEqual(ok, exp, (seed, r["cells"]))

    def test_c_rigidni_transformace(self):
        need(self, not FAST, "MARK_FAST")
        tfs = [
            ("posun (100,-50,30)", A.similarity(1, None, (100, -50, 30)), False),
            ("meritko x0.001 (mm -> m) kolem pocatku", A.similarity(0.001), True),
            ("meritko x25.4 kolem pocatku", A.similarity(25.4), True),
            ("otoceni 90 st. kolem X (Y-up -> Z-up)", A.similarity(1, A.rot_axis((1, 0, 0), 90)), True),
            ("otoceni 37 st. kolem Y + posun", A.similarity(1, A.rot_axis((0, 1, 0), 37), (500, 0, -300)), False),
            ("otoceni (1,2,3) 71 st. + meritko 1.3 + posun", A.similarity(1.3, A.rot_axis((1, 2, 3), 71), (10, 20, 30)), False),
        ]
        for k in CARDS[:2]:
            out, _ = marked(k)
            for name, tf, blind_ok in tfs:
                for how, fn in (("upecene do vrcholu", A.bake), ("uzel nad scenou", A.wrap_root)):
                    glb = fn(out, tf)
                    ok_b, rb = det(glb, card_id(k))
                    ok_o, ro = det(glb, card_id(k), original=card_glb(k), frames=False)
                    row("c) rigidni transformace", "%s, %s [%s]" % (name, how, k),
                        "bez originalu %s / s originalem ano" % ("ano" if blind_ok else "ne"),
                        "bez originalu %s / s originalem %s" % ("ano" if ok_b else "ne", "ano" if ok_o else "ne"),
                        ro["jistota"] if ok_o else None,
                        ("soustava %s" % {kk: vv for kk, vv in (rb.get("soustava") or {}).items() if kk != "otoceni"})
                        if ok_b and rb.get("soustava") else "")
                    self.assertEqual(ok_b, blind_ok, (name, how, k, rb["cells"]))
                    self.assertTrue(ok_o, (name, how, k, ro.get("registrace")))

    def test_c_orez_a_transformace(self):
        need(self, not FAST, "MARK_FAST")
        tf = A.similarity(1.0, A.rot_axis((1, 2, 3), 71), (10, 20, 30))
        for kk in ("4918", "4453"):
            if kk not in CARDS:
                continue
            out, _ = marked(kk)
            for f, exp in ((0.8, True), (0.5, None)):
                gl = A.bake(A.keep_meshes(out, f, seed=4)[0], tf)
                ok, r = det(gl, card_id(kk), original=card_glb(kk), frames=False)
                row("c) rigidni transformace", "orez na %d %% dilu + otoceni + posun, s originalem [%s]" % (100 * f, kk),
                    "ano" if exp else "(zavisi na karte; PCA registrace predpoklada cely model)", "ano" if ok else "ne",
                    r["jistota"] if ok else None,
                    "registrace: %s" % (r.get("registrace") if not isinstance(r.get("registrace"), dict) else "ok"))
                if exp is not None:
                    self.assertEqual(ok, exp, (kk, f, r.get("registrace")))


# ---------------------------------------------------------------------------
# Externi nastroje: three r128 (node), Blender (CPU)
# ---------------------------------------------------------------------------

def run_three(src, dst, *extra):
    r = subprocess.run([NODE, os.path.join(HERE, "_three_roundtrip.js"), src, dst] + list(extra),
                       capture_output=True, text=True, timeout=300)
    res = json.loads(r.stdout)
    if not res.get("ok"):
        raise AssertionError("three: %s" % res)
    with open(dst, "rb") as fh:
        return fh.read()


@unittest.skipIf(FAST, "MARK_FAST")
class TestExterni(Base):
    @unittest.skipUnless(NODE, "node neni")
    def test_a_three_loader_exporter(self):
        for k in CARDS[:3]:
            out, _ = marked(k)
            src = os.path.join(TMP, "%s_src.glb" % k)
            with open(src, "wb") as fh:
                fh.write(out)
            rt = run_three(src, os.path.join(TMP, "%s_three.glb" % k))
            ok, r = det(rt, card_id(k))
            row("a) ulozeni", "three r128 GLTFLoader -> GLTFExporter [%s]" % k, "ano", "ano" if ok else "ne",
                r["jistota"] if ok else None, "%d bunek" % r["cells"])
            self.assertTrue(ok, k)
            # scena zmensena v three (uzel nad modelem, vrcholy beze zmeny)
            rt2 = run_three(src, os.path.join(TMP, "%s_three_s.glb" % k), "--scale", "0.001")
            ok2, r2 = det(rt2, card_id(k))
            row("c) rigidni transformace", "three: scene.scale=0.001 + export [%s]" % k,
                "ano (hledani jednotek)", "ano" if ok2 else "ne", r2["jistota"] if ok2 else None,
                "soustava %s" % ({kk: vv for kk, vv in (r2.get("soustava") or {}).items() if kk != "otoceni"}))
            self.assertTrue(ok2, k)
            rt3 = run_three(src, os.path.join(TMP, "%s_three_t.glb" % k), "--translate", "100,-20,5",
                            "--rot-x-deg", "33")
            ok3, r3 = det(rt3, card_id(k))
            ok3o, r3o = det(rt3, card_id(k), original=card_glb(k), frames=False)
            row("c) rigidni transformace", "three: scene.position + rotation.x 33 st. + export [%s]" % k,
                "bez originalu ne / s originalem ano", "bez originalu %s / s originalem %s" % (
                    "ano" if ok3 else "ne", "ano" if ok3o else "ne"), r3o["jistota"] if ok3o else None)
            self.assertFalse(ok3)
            self.assertTrue(ok3o, k)

    @unittest.skipUnless(BLENDER, "Blender neni")
    def test_b_blender(self):
        for k in CARDS[:2]:
            out, _ = marked(k)
            src = os.path.join(TMP, "%s_bl_src.glb" % k)
            dst = os.path.join(TMP, "bl_%s" % k)
            with open(src, "wb") as fh:
                fh.write(out)
            r = subprocess.run([BLENDER, "-b", "--factory-startup", "--python",
                                os.path.join(HERE, "_blender_mark_convert.py"), "--", src, dst],
                               capture_output=True, text=True, timeout=900,
                               env={"PATH": os.environ.get("PATH", ""), "HOME": TMP})
            done = re.search(r"CONVERT_DONE (.*)", r.stdout)
            self.assertIsNotNone(done, (r.stdout[-500:], r.stderr[-500:]))
            self.assertEqual(set(done.group(1).split()), {"glb_rt", "glb_zup", "obj", "fbx", "stl", "join", "merge01",
                                                          "merge_big", "origin_geom", "decimate"}, r.stdout[-800:])
            Po = M.world_points(card_glb(k))
            cases = [
                ("GLB -> Blender -> GLB (Y-up)", "glb_rt.glb", True, False),
                ("GLB -> Blender -> OBJ (svetove souradnice, vychozi osy)", "obj.obj", True, False),
                ("GLB -> Blender -> FBX -> Blender -> GLB", "fbx_rt.glb", True, False),
                ("Blender: Join (Ctrl+J) vsech dilu -> GLB", "join_glb.glb", True, False),
                ("Blender: Join + Merge by Distance 0.0001", "merge01_glb.glb", True, False),
                ("Blender: Join + Merge by Distance 0.1 mm", "merge_big_glb.glb", True, False),
                ("Blender: Origin to Geometry -> GLB", "origin_geom_glb.glb", True, False),
                ("Blender: Decimate 0.5 (collapse) -> GLB", "decimate_glb.glb", True, False),
                ("GLB -> Blender -> GLB se Z-up (export_yup=False)", "glb_zup.glb", True, True),
                ("GLB -> Blender -> STL (Z-up, binarni)", "stl.stl", True, True),
            ]
            for name, fn, expect, frame_search in cases:
                p = os.path.join(dst, fn)
                if fn.endswith(".obj"):
                    P = M.points_from_obj(open(p, "rb").read())
                elif fn.endswith(".stl"):
                    P = M.points_from_stl(open(p, "rb").read())
                else:
                    P = M.world_points(open(p, "rb").read())
                rb = M.detect_points(P, SECRET)
                ok = rb["offer_id"] == card_id(k)
                ro = M.detect_points(P, SECRET, original_points=Po, frames=False)
                ok_o = ro["offer_id"] == card_id(k)
                row("b) prevod pres Blender (CPU)", "%s [%s]" % (name, k), "ano", "bez originalu %s / s originalem %s" % (
                    "ano" if ok else "ne", "ano" if ok_o else "ne"), rb["jistota"] if ok else None,
                    ("nalezeno hledanim jednotek/otoceni" if rb.get("soustava") else "v soustave souboru"))
                self.assertTrue(ok, (k, name, rb["cells"], rb["mean_abs_vote"]))
                self.assertEqual(bool(rb.get("soustava")), frame_search, (k, name))
                self.assertTrue(ok_o, (k, name))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

class _Cur:
    def __init__(self, rows, log):
        self.rows, self.log, self.last = rows, log, None

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params=()):
        self.log.append((sql, params))
        assert sql.lstrip().upper().startswith("SELECT"), "CLI smi jen SELECT"
        self.last = (sql, params)

    def fetchall(self):
        return [{"id": i} for i in sorted(self.rows)]

    def fetchone(self):
        return self.rows.get(self.last[1][0])


class _Conn:
    def __init__(self, rows):
        self.rows, self.log, self.closed = rows, [], False

    def cursor(self):
        return _Cur(self.rows, self.log)

    def close(self):
        self.closed = True


class TestCLI(Base):
    def setUp(self):
        super().setUp()
        import v3d_mark_detect as CLI
        self.CLI = CLI

    def run_cli(self, args, rows=None):
        import io
        conn = _Conn(rows or {})
        out = io.StringIO()
        rc = self.CLI.hlavni(args + ["--secret-hex", SECRET.hex()], conn_factory=lambda: conn, out=out)
        return rc, out.getvalue(), conn

    def test_nalezeno_a_radek_nabidky(self):
        k = CARDS[1]
        p = os.path.join(TMP, "cli_%s.glb" % k)
        with open(p, "wb") as fh:
            fh.write(marked(k)[0])
        row_db = {card_id(k): {"id": card_id(k), "offer_number": "26-0042", "customer_name": "Test s.r.o.",
                               "created_at": "2026-10-01 12:00:00", "expires_at": "2026-10-31", "is_active": 1,
                               "view_3d_model": "abc.glb", "drive_model_file_id": 7, "items": "[...]"}}
        rc, text, conn = self.run_cli([p], row_db)
        self.assertEqual(rc, 0, text)
        self.assertIn("id=%d" % card_id(k), text)
        self.assertIn("26-0042", text)
        self.assertNotIn("items", text)
        self.assertTrue(conn.closed)
        self.assertTrue(all(s.lstrip().upper().startswith("SELECT") for s, _ in conn.log))
        # bez DB
        rc, text, conn = self.run_cli([p, "--no-db"])
        self.assertEqual(rc, 0)
        self.assertEqual(conn.log, [])
        # json
        rc, text, _ = self.run_cli([p, "--no-db", "--json"])
        j = json.loads(text)
        self.assertTrue(j["nalezeno"])
        self.assertEqual(j["offer_id"], card_id(k))

    def test_nenalezeno_a_kandidati_z_db(self):
        k = CARDS[1]
        p = os.path.join(TMP, "cli_unmarked_%s.glb" % k)
        with open(p, "wb") as fh:
            fh.write(card_glb(k))
        rc, text, conn = self.run_cli([p], {5: {}, 6: {}})
        self.assertEqual(rc, 1)
        self.assertIn("NENALEZENA", text)
        self.assertIn("kandidatu 2", text)
        self.assertTrue(any("SELECT id FROM scene_offers" in s for s, _ in conn.log))
        # chybny vstup
        rc, text, _ = self.run_cli([os.path.join(TMP, "neexistuje.glb"), "--no-db"])
        self.assertEqual(rc, 2)

    def test_obj_a_original(self):
        need(self, not FAST, "MARK_FAST")
        k = CARDS[1]
        P = A.bake(marked(k)[0], A.similarity(1, A.rot_axis((0, 1, 0), 30), (50, 0, 0)))
        pts = M.world_points(P)
        po = os.path.join(TMP, "cli_%s.obj" % k)
        with open(po, "w") as fh:
            fh.write("".join("v %.6f %.6f %.6f\n" % tuple(q) for q in pts))
        orig = os.path.join(TMP, "cli_%s_orig.glb" % k)
        with open(orig, "wb") as fh:
            fh.write(card_glb(k))
        rc, text, _ = self.run_cli([po, "--no-db"])
        self.assertEqual(rc, 1)
        rc, text, _ = self.run_cli([po, "--no-db", "--original", orig])
        self.assertEqual(rc, 0, text)
        self.assertIn("id=%d" % card_id(k), text)

    def test_secret_zdroje(self):
        CLI = self.CLI
        self.assertEqual(CLI.nacti_secret(env={"V3D_MARK_SECRET": "ab" * 32}), bytes.fromhex("ab" * 32))
        self.assertEqual(CLI.nacti_secret(env={"FLASK_SECRET_KEY": "fk"}), M.derive_secret("fk"))
        with tempfile.NamedTemporaryFile("w", suffix=".env", delete=False) as fh:
            fh.write("DB_PASSWORD=nikdy\nFLASK_SECRET_KEY=\"z-env-souboru\"\n")
        try:
            self.assertEqual(CLI.nacti_secret(env={}, env_path=fh.name), M.derive_secret("z-env-souboru"))
        finally:
            os.unlink(fh.name)
        with self.assertRaises(ValueError):
            CLI.nacti_secret(env={}, env_path="/neexistuje/.env")


# ---------------------------------------------------------------------------
# Nezavisle pomucky (vlastni geometrie)
# ---------------------------------------------------------------------------

def world_vertices(glb):
    """Svetove vrcholy vsech primitiv (v poradi uzlu), pocitane pres test_sanitize.m_node/xform."""
    g, raw = v3d_glb.read_glb(glb)
    b = raw or b""
    out = []

    def walk(i, pm):
        n = g["nodes"][i]
        m = TS.m_mul(pm, TS.m_node(n))
        if "mesh" in n:
            for p in g["meshes"][n["mesh"]]["primitives"]:
                P = np.array(TS.positions(g, b, p["attributes"]["POSITION"]), dtype=np.float64)
                M3 = np.array([row_[:3] for row_ in m[:3]])
                t = np.array([row_[3] for row_ in m[:3]])
                out.append(P @ M3.T + t)
        for c in n.get("children", []):
            walk(c, m)

    for r in g["scenes"][g.get("scene", 0)]["nodes"]:
        walk(r, TS.m_ident())
    return np.concatenate(out)


def _tris(g, b):
    """[(world vrcholy [n,3], indexy [t,3])] - pro objem/plochu (vlastni transformace)."""
    out = []

    def walk(i, pm):
        n = g["nodes"][i]
        m = TS.m_mul(pm, TS.m_node(n))
        if "mesh" in n:
            for p in g["meshes"][n["mesh"]]["primitives"]:
                P = np.array(TS.positions(g, b, p["attributes"]["POSITION"]), dtype=np.float64)
                M3 = np.array([row_[:3] for row_ in m[:3]])
                t = np.array([row_[3] for row_ in m[:3]])
                W = P @ M3.T + t
                a = g["accessors"][p["indices"]]
                v = g["bufferViews"][a["bufferView"]]
                dt = {5121: "<u1", 5123: "<u2", 5125: "<u4"}[a["componentType"]]
                ix = np.frombuffer(b, dtype=dt, count=a["count"], offset=v.get("byteOffset", 0) + a.get("byteOffset", 0))
                out.append((W, ix.reshape(-1, 3).astype(np.int64)))
        for c in n.get("children", []):
            walk(c, m)

    for r in g["scenes"][g.get("scene", 0)]["nodes"]:
        walk(r, TS.m_ident())
    return out


def tri_count(g):
    return sum(g["accessors"][p["indices"]]["count"] // 3 for m in g["meshes"] for p in m["primitives"])


def mesh_volume(g, b):
    v = 0.0
    for W, ix in _tris(g, b):
        a, bb, c = W[ix[:, 0]], W[ix[:, 1]], W[ix[:, 2]]
        v += float(np.einsum("ij,ij->i", a, np.cross(bb, c)).sum() / 6.0)
    return v


def mesh_area(g, b):
    s = 0.0
    for W, ix in _tris(g, b):
        a, bb, c = W[ix[:, 0]], W[ix[:, 1]], W[ix[:, 2]]
        s += float(0.5 * np.linalg.norm(np.cross(bb - a, c - a), axis=1).sum())
    return s


def three_check(path):
    r = subprocess.run([NODE, os.path.join(HERE, "three_check.js"), path], capture_output=True, text=True, timeout=120)
    return json.loads(r.stdout)


def tabulka_text():
    lines = []
    for r in TABLE:
        lines.append("| %s | %s | %s | %s | %s | %s |" % (
            r["skupina"], r["test"], r["ocekavano"], r["ziskano"],
            "" if r["jistota"] is None else "%.10f" % r["jistota"], r["poznamka"]))
    return "\n".join(lines)


def tearDownModule():
    path = os.environ.get("MARK_TABLE")
    if path and TABLE:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(TABLE, fh, ensure_ascii=False, indent=1)
    if TABLE and os.environ.get("MARK_PRINT") == "1":
        print("\n" + tabulka_text())


if __name__ == "__main__":
    unittest.main(verbosity=2)
