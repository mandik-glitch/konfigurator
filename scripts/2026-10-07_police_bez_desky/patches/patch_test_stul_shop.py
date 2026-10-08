#!/usr/bin/env python3
"""Zaplata EXISTUJICIHO testu scripts/2026-10-02_stul_testy/test_stul_shop.py: kontrola 'zapnuti kazde volby ma kladny priplatek' (vsechny volby vypnute, vc. spodnich polic) musi vynechat
novy slot `shelfboard` - bez spodnich polic nic nemeni (cena se nemeni, slot je skryty). Kotvena nahrada.
Pouziti: patch_test_stul_shop.py <vstup test_stul_shop.py> <vystup>"""
import sys

src, dst = sys.argv[1], sys.argv[2]
s = open(src, encoding="utf-8").read()
a = '''if k not in ("socket", "posts", "braces", "drawleft", "ledlight")), f"zapnuti kazde volby (drawleft je zrcadleni, ledlight bez led nic nemeni = cena se nemeni) ma kladny priplatek'''
b = '''if k not in ("socket", "posts", "braces", "drawleft", "ledlight", "shelfboard")), f"zapnuti kazde volby (drawleft je zrcadleni, ledlight bez led a shelfboard bez polic nic nemeni = cena se nemeni) ma kladny priplatek'''
assert s.count(a) == 1, "kotva: %d vyskytu" % s.count(a)
open(dst, "w", encoding="utf-8").write(s.replace(a, b))
print("OK ->", dst)
