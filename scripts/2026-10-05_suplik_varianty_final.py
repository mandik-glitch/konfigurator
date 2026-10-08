#!/usr/bin/env python3
"""KONECNE modely ocelovych supliku s 1 a 3 supliky pro katalog (bot8, 2026-10-05; kandidaty udelala bot5: scripts/2026-10-05_bot5_suplik_varianty.py).

Robert 2026-10-05 (skutecne vnejsi vysky od dodavatele): 1 suplik 180 mm (SKU Suplik.ocel.440136, 3 900 Kc bez DPH), 2 supliky 280 mm (Dvojsuplik.ocel.440137, karta 4930, model v katalogu),
3 supliky 450 mm (Trojsuplik.ocel.440138, 5 900 Kc bez DPH). Kandidati bot5 maji odvozene vysky 185,4 / 280,2 / 374,9 mm (rozteč 94,73 mm), proto se tady jen
SVISLE (lokalni osa Z modelu, 565 x 583,1 x vyska) prepocitaji na skutecnou vysku:
  * vsechny vrcholy: z' = z_horni - (z_horni - z) * k, k = pozadovana vyska / vyska kandidata (rovnomerne protazeni / stlaceni; zamek, celo a koleje se protahnou stejne),
  * HORNI plocha zustava ve STEJNE lokalni vysce jako u zavreneho product_4930 (z = 907,5 mm): box visi na pricich pod pracovni deskou svym vrchem, takze generator ma pro vsechny
    tri boxy stejnou polohu dilu a rozdil je jen to, jak hluboko pod pricky box sahá,
  * normaly: (nx, ny, nz / k) normalizovane (inverzne transponovana matice nerovnomerneho meritka).
Vystup `product_<id>.glb` (jeden mesh bez materialu jako product_4930.glb) do zadane slozky; id karet se zada argumentem (karty zaklada scripts/2026-10-05_suplik_karty.py).

  api/venv/bin/python3 scripts/2026-10-05_suplik_varianty_final.py --id1 4956 --id3 4957 [--vystup webapp/katalog]
"""
import argparse
import json
import os
import shutil
import struct
import sys
import tempfile

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "api"))
import stul_glb as G  # noqa: E402
import stul_konfigurator as S  # noqa: E402

KANDIDATI = os.path.join(ROOT, "backups", "2026-10-05_suplik_varianty")
VYSKY = {1: 180.0, 3: 450.0}                 # skutecne vnejsi vysky (mm), Robert 2026-10-05
Z_HORNI = 907.5                              # lokalni horni plocha zavreneho product_4930 (S.ZAVRENY_BBOX)


def nacti_kandidata(n):
    """(pos, nrm, tri) kandidata pro n supliku (uz zavreny model: _zavri_suplik ho nemeni)."""
    tmp = tempfile.mkdtemp()
    try:
        shutil.copy(os.path.join(KANDIDATI, f"suplik_{n}_zavreny_kandidat.glb"), os.path.join(tmp, "product_4930.glb"))
        puvodni = S.KATALOG_DIR
        S.KATALOG_DIR = tmp
        G._MESH_CACHE.pop("product_4930", None)
        try:
            return G.nacti_mesh("product_4930")
        finally:
            S.KATALOG_DIR = puvodni
            G._MESH_CACHE.pop("product_4930", None)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def preved_na_vysku(pos, nrm, vyska):
    """Svisle prepocita model na `vyska` mm (viz hlavicka): horni plocha na Z_HORNI, normaly inverzne transponovane."""
    p = pos.astype(np.float64)
    z_hor = float(p[:, 2].max())
    k = vyska / (z_hor - float(p[:, 2].min()))
    p[:, 2] = Z_HORNI - (z_hor - p[:, 2]) * k
    n = nrm.astype(np.float64).copy()
    n[:, 2] /= k
    ln = np.linalg.norm(n, axis=1, keepdims=True)
    ln[ln == 0] = 1.0
    return p.astype(np.float32), (n / ln).astype(np.float32), k


def zapis_glb(cesta, pos, nrm, tri):
    pos, nrm = pos.astype("<f4"), nrm.astype("<f4")
    idx = tri.astype("<u4").ravel()
    b_idx, b_pos, b_nrm = idx.tobytes(), pos.tobytes(), nrm.tobytes()
    binc = b_idx + b_pos + b_nrm
    js = {"scene": 0, "scenes": [{"nodes": [0]}], "asset": {"version": "2.0", "generator": "bot8 suplik_varianty_final (z kandidata bot5, odvozeno z product_4930)"},
          "accessors": [{"componentType": 5125, "type": "SCALAR", "bufferView": 0, "count": int(len(idx)), "max": [int(idx.max())], "min": [int(idx.min())]},
                        {"componentType": 5126, "type": "VEC3", "byteOffset": 0, "bufferView": 1, "count": int(len(pos)), "max": [float(v) for v in pos.max(0)], "min": [float(v) for v in pos.min(0)]},
                        {"componentType": 5126, "type": "VEC3", "byteOffset": 0, "bufferView": 2, "count": int(len(nrm)), "max": [1.0, 1.0, 1.0], "min": [-1.0, -1.0, -1.0]}],
          "meshes": [{"name": "geometry_0", "extras": {}, "primitives": [{"attributes": {"POSITION": 1, "NORMAL": 2}, "indices": 0, "mode": 4}]}],
          "nodes": [{"name": "world", "children": [1]}, {"name": "geometry_0", "mesh": 0}],
          "bufferViews": [{"buffer": 0, "byteOffset": 0, "byteLength": len(b_idx)}, {"buffer": 0, "byteOffset": len(b_idx), "byteLength": len(b_pos)},
                          {"buffer": 0, "byteOffset": len(b_idx) + len(b_pos), "byteLength": len(b_nrm)}],
          "buffers": [{"byteLength": len(binc)}]}
    j = json.dumps(js, separators=(",", ":")).encode()
    j += b" " * (-len(j) % 4)
    binc += b"\0" * (-len(binc) % 4)
    with open(cesta, "wb") as f:
        f.write(struct.pack("<III", 0x46546C67, 2, 12 + 8 + len(j) + 8 + len(binc)))
        f.write(struct.pack("<II", len(j), 0x4E4F534A) + j)
        f.write(struct.pack("<II", len(binc), 0x004E4942) + binc)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--id1", type=int, required=True, help="id karty boxu s 1 supliky")
    ap.add_argument("--id3", type=int, required=True, help="id karty boxu s 3 supliky")
    ap.add_argument("--vystup", default=os.path.join(ROOT, "webapp", "katalog"))
    a = ap.parse_args()
    os.makedirs(a.vystup, exist_ok=True)
    for n, pid in ((1, a.id1), (3, a.id3)):
        pos, nrm, tri = nacti_kandidata(n)
        pos2, nrm2, k = preved_na_vysku(pos, nrm, VYSKY[n])
        lo, hi = pos2.min(axis=0), pos2.max(axis=0)
        cesta = os.path.join(a.vystup, f"product_{pid}.glb")
        zapis_glb(cesta, pos2, nrm2, tri)
        print(f"{n} supliku -> {cesta}: {len(tri)} trojuhelniku, rozmer {hi[0] - lo[0]:.1f} x {hi[1] - lo[1]:.1f} x {hi[2] - lo[2]:.1f} mm, lokalne z {lo[2]:.1f}..{hi[2]:.1f} (k = {k:.4f})")


if __name__ == "__main__":
    main()
