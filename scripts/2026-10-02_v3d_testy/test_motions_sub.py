#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Testy druhu boxu (motions[].sub) v scripts/v3d/vandr_motions.py (Robert 2026-10-02): sub z kusovniku /
materialu / typu komponenty a cislovani n po druhu (u boxu po druhu boxu).

Spusteni:  api/venv/bin/python3 scripts/2026-10-02_v3d_testy/test_motions_sub.py     (numpy; bez Blenderu - Detekce se sklada nad atrapou api)

Pokryva jen cisty kod modulu (sub_boxu(), kusovnik(), vysledek()); skutecna detekce nad modelem se
kontroluje stavbou 7 karet (rebuild.py) a harnessem (scenar H: sub z kusovniku ctx, druhy boxu po kartach).
"""
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))      # koren repa
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.join(ROOT, "scripts", "v3d"))
sys.path.insert(0, os.path.join(ROOT, "api"))

import vandr_motions as VM  # noqa: E402


class Api:
    ctx = {"komponenty": [], "pohyby_vychozi": {}}
    components = []


class Dil:
    """Atrapa skorepiny boxu: role + rodiny materialu."""

    def __init__(self, role="", rod=()):
        self.role = role
        self.rod = list(rod)


def det():
    return VM.Detekce(Api())


def kus(*uids):
    return VM.Detekce.kusovnik({"dily": [{"unity_id": u, "pocet": 1} for u in uids]})


class TestSub(unittest.TestCase):
    def test_zdroje_se_shoduji(self):
        d = det()
        for uid, bom, role, rod, want in (
                ("Vysuv.KLT3.147.1357.459.closed", ("BOX.KLT.400x300x147",), "blueklt", ["blue klt"], "klt"),
                ("Vysuv.Multibox.8.1357.459.closed", ("Multibox.396x186",), "multiboxarc", ["blue klt"], "multibox"),
                ("Police.Multibox.6.1057.459", ("Multibox.396x186", "Multibox.396x93"), "multiboxarc", ["multibox"], "multibox"),
                ("Vysuv.Eurobox.4.3212.942.349", ("Box.grey.300.200.120",), "darkgreybin", ["box tmava"], "eurobox"),
                ("Box.police.6407x2.1357.459", ("Box.grey.600x400x78",), "darkgreybin", [], "eurobox")):
            with self.subTest(uid=uid):
                sub, zdroje = d.sub_boxu(uid, kus(*bom), Dil(role, rod))
                self.assertEqual(sub, want)
                self.assertEqual(zdroje["typ_komponenty"] in (None, want), True)
        self.assertEqual(d.typove, {})          # zadne varovani

    def test_jeden_zdroj_staci(self):
        d = det()
        self.assertEqual(d.sub_boxu("Neco.1", kus("BOX.KLT.400x300x147"), Dil("", []))[0], "klt")                      # jen kusovnik
        self.assertEqual(d.sub_boxu("Neco.1", kus(), Dil("multiboxarc", []))[0], "multibox")                           # jen role
        self.assertEqual(d.sub_boxu("Vysuv.Eurobox.1", kus(), Dil("", []))[0], "eurobox")                              # jen typ komponenty
        self.assertEqual(d.sub_boxu("Neco.1", kus(), Dil("", ["multibox"]))[0], "multibox")                            # jen rodina (slabsi zdroj)
        self.assertEqual(d.typove, {})

    def test_spor_nebo_nic_vynecha_sub_s_varovanim(self):
        for uid, bom, role in (("Vysuv.KLT3.147", ("Multibox.396x186",), "blueklt"),                  # role x kusovnik
                               ("Vysuv.Multibox.8", ("BOX.KLT.400x300x147",), "multiboxarc"),          # typ x kusovnik
                               ("Police.Multibox.6", ("Multibox.396x186",), "blueklt"),                # typ+kusovnik x role
                               ("Neco.1", (), ""),                                                     # zadny zdroj
                               ("Neco.1", ("BOX.KLT.400x300x147", "Multibox.396x186"), "")):           # kusovnik s 2 druhy, bez dalsiho zdroje
            with self.subTest(uid=uid, role=role):
                d = det()
                sub, _z = d.sub_boxu(uid, kus(*bom), Dil(role, []))
                self.assertIsNone(sub)
                self.assertEqual(len(d.typove), 1)

    def test_kusovnik_typy(self):
        k = kus("BOX.KLT.400x300x147", "Box.grey.300.200.120", "Multibox.396x186", "Pojezdy.450.53.100kg.gtv", "Pant_45x30")
        self.assertEqual(k["box_typy"], {"klt", "eurobox", "multibox"})
        self.assertEqual(k["boxy"], 3)
        self.assertEqual(kus("45x45x1267_Zx2")["box_typy"], set())


class TestCislovani(unittest.TestCase):
    @staticmethod
    def mot(k, sub=None):
        m = {"k": k, "steps": [{"p": "p1", "op": "T", "ax": [0, 0, 1], "v": 1, "ms": 1}], "pick": ["p1"]}
        if sub:
            m["sub"] = sub
        return m

    def test_n_po_druhu_a_druhu_boxu_poradi_vystupu(self):
        d = det()
        # (klic razeni, druh, pohyb): zamerne promichane poradi vkladani
        for klic, k, m in (((0, 2, 0, 0), "box", self.mot("box", "klt")),
                           ((0, 1, 0, 0), "drawer", self.mot("drawer")),
                           ((0, 1, 0, 5), "drawer", self.mot("drawer")),
                           ((0, 3, 0, 0), "box", self.mot("box", "klt")),
                           ((0, 0, 0, 0), "box", self.mot("box", "multibox")),
                           ((0, 4, 0, 0), "box", self.mot("box", "klt")),
                           ((0, 7, 0, 0), "box", self.mot("box")),
                           ((1, 0, 0, 0), "door", self.mot("door")),
                           ((0, 5, 0, 0), "box", self.mot("box", "eurobox")),
                           ((0, 6, 0, 0), "box", self.mot("box", "eurobox")),
                           ((0, 0, 1, 0), "box", self.mot("box", "multibox"))):
            d.motions.append((klic, k, m))
        out = d.vysledek()["motions"]
        tab = [(m["k"], m.get("sub"), m["n"]) for m in out]
        self.assertEqual(tab, [
            ("drawer", None, 1), ("drawer", None, 2),                          # druh, pozice v ramu cela
            ("door", None, 1),
            ("box", "multibox", 1), ("box", "multibox", 2),                    # boxy v poradi pozice, n po druhu boxu
            ("box", "klt", 1), ("box", "klt", 2), ("box", "klt", 3),
            ("box", "eurobox", 1), ("box", "eurobox", 2),
            ("box", None, 1)])                                                 # druh nelze urcit = "Box 1"
        self.assertEqual(d.vysledek()["motions"], out)                         # deterministicky

    def test_bez_sub_n_po_druzich_jako_dosud(self):
        d = det()
        for i, k in enumerate(("drawer", "box", "drawer", "box", "door")):
            d.motions.append(((0, i, 0, 0), k, self.mot(k)))
        out = d.vysledek()["motions"]
        self.assertEqual([(m["k"], m["n"]) for m in out], [("drawer", 1), ("drawer", 2), ("door", 1), ("box", 1), ("box", 2)])
        for m in out:
            self.assertNotIn("sub", m)


if __name__ == "__main__":
    unittest.main(verbosity=2)
