#!/usr/bin/env python3
"""Detailní IoU pro pohled shora (c01): tmavé prvky (černé rukojeť a západky + šedý rám madla) a bílé logo, render ořezaný na obrys (srovnani/2329206/shora.png).
Použití: python3 -I detaily_2329206.py foto_c01.jpg render_shora.png   (fotografie se jen čte)"""
import sys, numpy as np
from PIL import Image
f = np.asarray(Image.open(sys.argv[1]).convert('RGB')).astype(int)
r = np.asarray(Image.open(sys.argv[2]).convert('RGB').resize((f.shape[1], f.shape[0]))).astype(int)
def dark(a): return (a.max(axis=2) < 90) & (abs(a[:, :, 0] - a[:, :, 1]) < 40)
# logo: bílé v oblasti loga; okno madla (bílé nahoře) se nezapočítá
def white(a): m = a.min(axis=2) > 185; m[:300] = False; return m
for n, fn in (('tmavé prvky (rukojeť, západky, rám)', dark), ('bílé logo', white)):
    a, b = fn(f), fn(r); print('%s: IoU %.3f (foto %d px, model %d px)' % (n, (a & b).sum() / max(1, (a | b).sum()), a.sum(), b.sum()))
