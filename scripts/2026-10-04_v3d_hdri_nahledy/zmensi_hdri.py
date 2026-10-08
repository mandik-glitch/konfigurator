#!/opt/konfigurator/api/venv/bin/python
"""Zmenseni HDRI z knihovny Sdileneho disku (slozka "HDRi", id 45) na 1024x512 Radiance .hdr pro nahled v prohlizeci (bot10, 2026-10-04).

Proc: admin v generatoru stolu meni HDRI zivym nahledem (viewer3d.js, env/*.hdr). Puvodni soubory maji 24-102 MB, do prohlizece se nehodi.
Postup: ctene RGBE (Radiance .hdr, rle i flat) -> prumerovani po blocich (plocha, zachova energii, zadny aliasing slunce) -> zapis RGBE s RLE
(literal runs, platne i pro three RGBELoader). Jen numpy. Vstup se bere z DB (id souboru -> stored_filename) jen pro CTENI; nic se nezapisuje do DB ani na disk
mimo --out. EXR (crossfit_gym_2k.exr) tenhle skript necte (env/crossfit_1024.hdr uz existuje).
  api/venv/bin/python -B scripts/2026-10-04_v3d_hdri_nahledy/zmensi_hdri.py --out webapp/js/v3d/env [--jen tv_studio]
  api/venv/bin/python -B scripts/2026-10-04_v3d_hdri_nahledy/zmensi_hdri.py --out webapp/js/v3d/env --nahledy
    (viewer 1.10.0: z hotovych <klic>_1024.hdr v --out udela <klic>_256.hdr = 256x128, 33-133 kB; viewer je pouzije jako rychly nahled prostredi, dokud se stahuje velke HDRI az po prvnim modelu;
     prumerovani po blocich zachova energii - stredni jas stejny; zadna DB)
"""
import argparse, os, struct, sys
import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, 'scripts'))
sys.dont_write_bytecode = True
ZDROJE = [  # klic, id souboru na Sdilenem disku, vystup
    ('tv_studio', 4044, 'tv_studio_1024.hdr'),
    ('berg_inner', 5661, 'berg_inner_1024.hdr'),
    ('teufelsberg', 5612, 'teufelsberg_1024.hdr'),
]
W_OUT, H_OUT = 1024, 512
W_LO, H_LO = 256, 128
KLICE = ['crossfit', 'tv_studio', 'berg_inner', 'teufelsberg']       # = HDRI_LIBRARY ve viewer3d.js


def read_rgbe(path):
    with open(path, 'rb') as f:
        data = f.read()
    pos = 0
    hdr = []
    while True:
        e = data.index(b'\n', pos); line = data[pos:e]; pos = e + 1
        if line == b'':
            break
        hdr.append(line)
    e = data.index(b'\n', pos); res = data[pos:e].decode().split(); pos = e + 1
    assert res[0] in ('-Y', '+Y') and res[2] in ('+X', '-X'), res
    H, W = int(res[1]), int(res[3])
    img = np.zeros((H, W, 4), np.uint8)
    for y in range(H):
        if W >= 8 and W < 32768 and data[pos] == 2 and data[pos + 1] == 2 and not (data[pos + 2] & 0x80):
            assert (data[pos + 2] << 8 | data[pos + 3]) == W
            pos += 4
            for c in range(4):
                x = 0
                while x < W:
                    n = data[pos]; pos += 1
                    if n > 128:
                        n -= 128; img[y, x:x + n, c] = data[pos]; pos += 1
                    else:
                        img[y, x:x + n, c] = np.frombuffer(data, np.uint8, n, pos); pos += n
                    x += n
        else:                                           # nekomprimovany radek
            img[y] = np.frombuffer(data, np.uint8, W * 4, pos).reshape(W, 4); pos += W * 4
    return img, W, H


def to_float(img):
    e = img[..., 3].astype(np.int32)
    f = np.where(e > 0, np.ldexp(1.0, e - 136), 0.0).astype(np.float32)   # 2^(e-128) / 256
    return img[..., :3].astype(np.float32) * f[..., None]


def downscale(rgb, W, H):
    fy, fx = rgb.shape[0] // H, rgb.shape[1] // W
    assert rgb.shape[0] == H * fy and rgb.shape[1] == W * fx, (rgb.shape, W, H)
    return rgb.reshape(H, fy, W, fx, 3).mean(axis=(1, 3))


def write_rgbe(path, rgb):
    H, W, _ = rgb.shape
    m = rgb.max(axis=2)
    e = np.where(m > 1e-32, np.ceil(np.log2(np.maximum(m, 1e-32))), -128).astype(np.int32)
    scale = np.where(m > 1e-32, np.ldexp(1.0, -e) * 256.0, 0.0).astype(np.float32)
    mant = np.clip(np.floor(rgb * scale[..., None]), 0, 255).astype(np.uint8)
    out = bytearray(b'#?RADIANCE\nFORMAT=32-bit_rle_rgbe\n\n-Y %d +X %d\n' % (H, W))
    for y in range(H):
        out += bytes([2, 2, W >> 8, W & 255])
        planes = [mant[y, :, 0], mant[y, :, 1], mant[y, :, 2], np.clip(e[y] + 128, 0, 255).astype(np.uint8)]
        for pl in planes:
            for x in range(0, W, 128):
                chunk = pl[x:x + 128]
                out.append(len(chunk)); out += chunk.tobytes()
    with open(path, 'wb') as fh:
        fh.write(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('--jen', default=None)
    ap.add_argument('--nahledy', action='store_true', help='z <klic>_1024.hdr v --out vyrobi <klic>_256.hdr (nahled pro rychle prvni vykresleni)')
    a = ap.parse_args()
    if a.nahledy:
        for key in KLICE:
            if a.jen and a.jen != key:
                continue
            src, dst = os.path.join(a.out, key + '_1024.hdr'), os.path.join(a.out, key + '_%d.hdr' % W_LO)
            img, W, H = read_rgbe(src)
            rgb = downscale(to_float(img), W_LO, H_LO)
            write_rgbe(dst, rgb)
            print('%-12s %dx%d -> %dx%d  max %.2f  prumer %.4f  %d B' % (key, W, H, W_LO, H_LO, rgb.max(), rgb.mean(), os.path.getsize(dst)))
        return
    from _env import get_conn
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            for key, fid, outname in ZDROJE:
                if a.jen and a.jen != key:
                    continue
                cur.execute("SELECT filename, stored_filename FROM shared_drive_files WHERE id=%s", (fid,))
                r = cur.fetchone()
                if not r:
                    print('CHYBI soubor id', fid); continue
                src = os.path.join(REPO, 'private-files', 'shared-drive', r['stored_filename'])
                img, W, H = read_rgbe(src)
                rgb = downscale(to_float(img), W_OUT, H_OUT)
                dst = os.path.join(a.out, outname)
                write_rgbe(dst, rgb)
                print('%-12s %s %dx%d -> %s %dx%d  max %.2f  prumer %.3f  %d B' % (key, r['filename'], W, H, outname, W_OUT, H_OUT, rgb.max(), rgb.mean(), os.path.getsize(dst)))
    finally:
        conn.close()


if __name__ == '__main__':
    main()
