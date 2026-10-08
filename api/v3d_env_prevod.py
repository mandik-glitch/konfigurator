#!/usr/bin/env python3
"""Prevod HDRI (Radiance .hdr, equirectangular 2:1) na dve verze pro online nabidky: <klic>_1024.hdr (1024x512) a <klic>_256.hdr (256x128; rychly nahled, viz viewer3d.js
opts.envEager) + vypocet normalizace jasu mul0 (bot10, 2026-10-07; Robert: "moznost pridat dalsi hdri ze sdileneho disku").

Bezi v PODPROCESU (api/v3d_env_import.py), protoze 8k vstup chce ~1,2 GB RAM a nema to blokovat ani ohrozit worker API. Zadny flask, zadna DB, jen numpy (+ Pillow pro zmenseni
na nenasobek). Pouziti:
  api/venv/bin/python -B api/v3d_env_prevod.py --src <soubor.hdr> --out <slozka> --key <klic> --ref <crossfit_1024.hdr>
vypise na posledni radek stdout JSON {w, h, mul0, mean, max, bytes_1024, bytes_256}; pri chybe napise cesky duvod na stderr a skonci s kodem 2 (nic nezapisuje mimo --out).

Postup stejny jako scripts/2026-10-04_v3d_hdri_nahledy/zmensi_hdri.py (cteni RGBE rle i flat -> prumerovani po blocich v linearni radianci, zachova energii, zadny aliasing slunce ->
zapis RGBE s RLE literal runs, platne pro three RGBELoader); pro stejny vstup je vystup byte po bytu shodny. mul0 = (stredni jas crossfit_1024.hdr) / (stredni jas nove HDRI): sila 1 ve
vieweru pak dava zhruba stejne svetlo jako HDRI karet (u tri rucne zmerenych HDRI knihovny to vychazi do 5 % od drivejsich hodnot 0,53 / 1,44 / 0,89)."""
import argparse
import json
import os
import sys

import numpy as np

sys.dont_write_bytecode = True
W_OUT, H_OUT = 1024, 512
W_LO, H_LO = 256, 128
W_MAX = 8192                   # vstup siroky nejvyse 8192 px (pamet ~1,2 GB); 16k soubory se musi predtim zmensit
MUL0_MEZE = (0.05, 20.0)


class Chyba(ValueError):
    """Ocekavana chyba vstupu - zprava je cesky a jde primo uzivateli."""


def read_rgbe(path, w_max=W_MAX, w_min=W_OUT):
    """Radiance .hdr (rle i flat, '-Y h +X w', '+Y h +X w') -> (uint8 [H, W, 4], W, H). Chyba = Chyba(cesky duvod)."""
    try:
        with open(path, "rb") as f:
            data = f.read()
    except OSError as e:
        raise Chyba("soubor nejde precist: %s" % e)
    if not (data.startswith(b"#?RADIANCE") or data.startswith(b"#?RGBE")):
        raise Chyba("soubor neni Radiance .hdr (chybi hlavicka #?RADIANCE)")
    try:
        pos = 0
        fmt_ok = True                                   # radek FORMAT= nemusi byt (Radiance vychozi je rgbe); je-li, musi to byt 32-bit_rle_rgbe
        while True:
            e = data.index(b"\n", pos)
            if e - pos > 4096:
                raise Chyba("poskozena hlavicka .hdr")
            line = data[pos:e]
            pos = e + 1
            if line.startswith(b"FORMAT="):
                fmt_ok = line.strip() == b"FORMAT=32-bit_rle_rgbe"
            if line == b"":
                break
            if pos > 65536:
                raise Chyba("poskozena hlavicka .hdr")
        if not fmt_ok:
            raise Chyba("nepodporovany format .hdr (potrebuji FORMAT=32-bit_rle_rgbe)")
        e = data.index(b"\n", pos)
        res = data[pos:e].decode("ascii", "replace").split()
        pos = e + 1
        if len(res) != 4 or res[0] not in ("-Y", "+Y") or res[2] != "+X":
            raise Chyba("nepodporovana orientace obrazu v .hdr (%s)" % " ".join(res))
        H, W = int(res[1]), int(res[3])
    except ValueError as e:
        if isinstance(e, Chyba):
            raise
        raise Chyba("poskozena hlavicka .hdr")
    if W < 64 or H < 32 or W != 2 * H:
        raise Chyba("HDRI musi byt equirectangular 2:1 (tohle je %dx%d)" % (W, H))
    if W > w_max:
        raise Chyba("HDRI je moc velke (%d px na sirku, nejvyse %d) - zmensi ho a zkus znovu" % (W, w_max))
    if W < w_min:
        raise Chyba("HDRI je moc male (%d px na sirku, aspon %d)" % (W, w_min))
    img = np.zeros((H, W, 4), np.uint8)
    try:
        for y in range(H):
            if 8 <= W < 32768 and data[pos] == 2 and data[pos + 1] == 2 and not (data[pos + 2] & 0x80):
                if (data[pos + 2] << 8 | data[pos + 3]) != W:
                    raise Chyba("poskozeny radek v .hdr")
                pos += 4
                for c in range(4):
                    x = 0
                    while x < W:
                        n = data[pos]
                        pos += 1
                        if n > 128:
                            n -= 128
                            if x + n > W:
                                raise Chyba("poskozeny radek v .hdr")
                            img[y, x:x + n, c] = data[pos]
                            pos += 1
                        else:
                            if n == 0 or x + n > W or pos + n > len(data):
                                raise Chyba("poskozeny radek v .hdr")
                            img[y, x:x + n, c] = np.frombuffer(data, np.uint8, n, pos)
                            pos += n
                        x += n
            else:                                       # nekomprimovany radek
                if pos + W * 4 > len(data):
                    raise Chyba("soubor .hdr je useknuty")
                img[y] = np.frombuffer(data, np.uint8, W * 4, pos).reshape(W, 4)
                pos += W * 4
    except IndexError:
        raise Chyba("soubor .hdr je useknuty")
    if res[0] == "+Y":
        img = img[::-1].copy()
    return img, W, H


def to_float(img):
    e = img[..., 3].astype(np.int32)
    f = np.where(e > 0, np.ldexp(1.0, e - 136), 0.0).astype(np.float32)   # 2^(e-128) / 256
    return img[..., :3].astype(np.float32) * f[..., None]


def resize_area(rgb, W, H):
    """Plosne prumerovani na W x H. Cele nasobky = bloky; jinak Pillow BOX po kanalech (float 'F')."""
    h0, w0 = rgb.shape[0], rgb.shape[1]
    if h0 % H == 0 and w0 % W == 0:
        fy, fx = h0 // H, w0 // W
        return rgb.reshape(H, fy, W, fx, 3).mean(axis=(1, 3), dtype=np.float32)
    from PIL import Image
    out = np.empty((H, W, 3), np.float32)
    for c in range(3):
        out[..., c] = np.asarray(Image.fromarray(np.ascontiguousarray(rgb[..., c]), "F").resize((W, H), Image.BOX), np.float32)
    return out


def write_rgbe(path, rgb):
    H, W, _ = rgb.shape
    m = rgb.max(axis=2)
    e = np.where(m > 1e-32, np.ceil(np.log2(np.maximum(m, 1e-32))), -128).astype(np.int32)
    scale = np.where(m > 1e-32, np.ldexp(1.0, -e) * 256.0, 0.0).astype(np.float32)
    mant = np.clip(np.floor(rgb * scale[..., None]), 0, 255).astype(np.uint8)
    out = bytearray(b"#?RADIANCE\nFORMAT=32-bit_rle_rgbe\n\n-Y %d +X %d\n" % (H, W))
    for y in range(H):
        out += bytes([2, 2, W >> 8, W & 255])
        planes = [mant[y, :, 0], mant[y, :, 1], mant[y, :, 2], np.clip(e[y] + 128, 0, 255).astype(np.uint8)]
        for pl in planes:
            for x in range(0, W, 128):
                chunk = pl[x:x + 128]
                out.append(len(chunk))
                out += chunk.tobytes()
    with open(path, "wb") as fh:
        fh.write(out)


def mean_lum(rgb):
    return float((0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]).mean())


def prevod(src, out_dir, key, ref):
    """Vyrobi <out_dir>/<key>_1024.hdr a _256.hdr; vraci slovnik se statistikou a mul0."""
    os.makedirs(out_dir, exist_ok=True)
    img, W, H = read_rgbe(src)
    rgb = resize_area(to_float(img), W_OUT, H_OUT)
    del img
    if not np.isfinite(rgb).all():
        raise Chyba("HDRI obsahuje neplatne hodnoty")
    lum = mean_lum(rgb)
    if lum <= 1e-9:
        raise Chyba("HDRI je cerna (nulovy jas)")
    rimg, _, _ = read_rgbe(ref, w_max=W_OUT, w_min=W_OUT)
    lum_ref = mean_lum(to_float(rimg))
    mul0 = round(min(MUL0_MEZE[1], max(MUL0_MEZE[0], lum_ref / lum)), 3)
    p1, p2 = os.path.join(out_dir, "%s_%d.hdr" % (key, W_OUT)), os.path.join(out_dir, "%s_%d.hdr" % (key, W_LO))
    write_rgbe(p1, rgb)
    lo = resize_area(rgb, W_LO, H_LO)               # nahled z 1024 (stejne jako zmensi_hdri.py --nahledy)
    write_rgbe(p2, lo)
    return {"w": W, "h": H, "mul0": mul0, "mean": round(lum, 5), "max": round(float(rgb.max()), 3), "bytes_1024": os.path.getsize(p1), "bytes_256": os.path.getsize(p2)}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--key", required=True)
    ap.add_argument("--ref", required=True, help="crossfit_1024.hdr - referencni jas (mul0 = jas reference / jas HDRI)")
    a = ap.parse_args(argv)
    try:
        vysl = prevod(a.src, a.out, a.key, a.ref)
    except Chyba as e:
        sys.stderr.write(str(e) + "\n")
        return 2
    except MemoryError:
        sys.stderr.write("na prevod HDRI nestaci pamet - zmensi soubor a zkus znovu\n")
        return 2
    print(json.dumps(vysl))
    return 0


if __name__ == "__main__":
    sys.exit(main())
