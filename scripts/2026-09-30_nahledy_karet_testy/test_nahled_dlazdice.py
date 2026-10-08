# Jednotna dlazdice karty (scripts/_nahled_dlazdice.py): syntetické snimky (svisly gradient + obdelnik = "sestava").
# Bez DB a site. Spusteni: api/venv/bin/python3 test_nahled_dlazdice.py   (konci kodem 0 jen kdyz VSE prosla)
import os
import sys
import tempfile

import numpy as np
from PIL import Image

sys.path.insert(0, "/opt/konfigurator/scripts")
import _nahled_dlazdice as N  # noqa: E402

vysl = []


def over(nazev, podminka, detail=None):
    vysl.append(bool(podminka))
    print(("OK   " if podminka else "FAIL ") + nazev + ("" if podminka else "  -> %r" % (detail,)))


def snimek(w=2048, h=2048, sestava=None, sum_pixely=0, seed=1):
    """Svisly gradient (tmava dole) + obdelnik sestavy (x0, y0, x1, y1) ve svetle seda s jemnou texturou."""
    g = np.linspace(200, 20, h).astype(np.uint8)
    a = np.repeat(g[:, None, None], w, axis=1)
    a = np.repeat(a, 3, axis=2).copy()
    if sestava:
        x0, y0, x1, y1 = sestava
        a[y0:y1, x0:x1] = 235
        a[y0:y1, x0:x1:7] = 90          # "profily"
    rng = np.random.default_rng(seed)
    for _ in range(sum_pixely):
        a[rng.integers(0, h), rng.integers(0, w)] = 255
    return Image.fromarray(a, "RGB")


def obalka(img):
    return N._bbox_sestavy(np.asarray(img).astype(np.int16))


def vypln(img):
    x0, x1, y0, y1 = obalka(img)
    w, h = img.size
    return max((x1 - x0 + 1) / w, (y1 - y0 + 1) / h)


def stred(img):
    x0, x1, y0, y1 = obalka(img)
    w, h = img.size
    return ((x0 + x1) / 2 / w, (y0 + y1) / 2 / h)


# --- ruzne pomery stran -> stejna delsi strana, vycentrovano -------------
pripady = {
    "vysoka a uzka (40 x 88 %)": (600, 130, 1420, 1930),
    "dlouha a siroka (85 x 58 %)": (150, 400, 1890, 1590),
    "skoro ctverec (60 x 60 %)": (400, 400, 1630, 1630),
    "drobna (25 x 30 %)": (800, 800, 1310, 1420),
}
for nazev, bb in pripady.items():
    v = N.sestav_dlazdici(snimek(sestava=bb))
    over("%s: ctverec %d" % (nazev, N.CIL), v.size == (N.CIL, N.CIL), v.size)
    over("%s: delsi strana = %.0f %% (+-1)" % (nazev, N.VYPLN * 100), abs(vypln(v) - N.VYPLN) < 0.01, vypln(v))
    sx, sy = stred(v)
    over("%s: vycentrovano (+-1,5 %%)" % nazev, abs(sx - 0.5) < 0.015 and abs(sy - 0.5) < 0.015, (sx, sy))
    x0, x1, y0, y1 = obalka(v)
    over("%s: nedotyka se okraje" % nazev, x0 > 2 and y0 > 2 and x1 < N.CIL - 3 and y1 < N.CIL - 3, (x0, x1, y0, y1))

# --- pozadi se dokresluje bez stopy ---------------------------------------
v = np.asarray(N.sestav_dlazdici(snimek(sestava=(150, 400, 1890, 1590)))).astype(np.int16)   # siroka: okno je vetsi nez zdroj
okraj = v[:, :40, :]
over("pozadi vlevo je v kazdem radku jednobarevne (bez smear/skoku)", int(np.abs(okraj - okraj[:, :1, :]).max()) <= 3, int(np.abs(okraj - okraj[:, :1, :]).max()))
over("pozadi plynule klesa shora dolu (gradient zustal)", v[5, 5, 0] > v[-5, 5, 0] + 100, (v[5, 5, 0], v[-5, 5, 0]))

# --- jiny format zdroje ---------------------------------------------------
v = N.sestav_dlazdici(snimek(w=1024, h=768, sestava=(300, 120, 700, 660)))
over("zdroj 4:3 -> ctverec, delsi strana 85 %", v.size == (N.CIL, N.CIL) and abs(vypln(v) - N.VYPLN) < 0.012, (v.size, vypln(v)))

# --- izolovany sum nenafoukne obalku --------------------------------------
zdroj_cisty = np.asarray(snimek(sestava=(600, 400, 1400, 1700))).astype(np.int16)
zdroj_sum = np.asarray(snimek(sestava=(600, 400, 1400, 1700), sum_pixely=40)).astype(np.int16)
over("40 izolovanych svetlych pixelu obalku ZDROJE neovlivni", N._bbox_sestavy(zdroj_cisty) == N._bbox_sestavy(zdroj_sum), (N._bbox_sestavy(zdroj_cisty), N._bbox_sestavy(zdroj_sum)))
# (obalku VYSTUPU se sumem mereni neda: sum ve vystupu zustava a pri zvetseni se z nej stane skvrna)
vystup_sum = N.sestav_dlazdici(snimek(sestava=(600, 400, 1400, 1700), sum_pixely=40))
vystup_cisty = N.sestav_dlazdici(snimek(sestava=(600, 400, 1400, 1700)))
rozdil = np.abs(np.asarray(vystup_sum).astype(np.int16) - np.asarray(vystup_cisty).astype(np.int16))
over("stejne okno: vystupy se lisi jen v okoli sumu (vetsina pixelu shodna)", float((rozdil.sum(axis=2) > 10).mean()) < 0.01, float((rozdil.sum(axis=2) > 10).mean()))

# --- mekky stin/odraz podlahy kolem siroke sestavy se za sestavu nepocita --------------
def se_stinem(bb):
    a = np.asarray(snimek(sestava=bb)).astype(np.int16).copy()
    x0, y0, x1, y1 = bb
    a[y1 - 140:y1 + 40, 60:1988] = np.clip(a[y1 - 140:y1 + 40, 60:1988] + 8, 0, 255)   # +8 na kanal = soucet 24 (< prah 30)
    return a


bb_siroka = (600, 500, 1450, 1600)
zdroj_bez = np.asarray(snimek(sestava=bb_siroka)).astype(np.int16)
zdroj_stin = se_stinem(bb_siroka)
b0, b1 = N._bbox_sestavy(zdroj_bez), N._bbox_sestavy(zdroj_stin)
over("mekky siroky stin podlahy (rozdil 24) obalku neovlivni (citlivejsi prah by ji nafoukl)", b0 == b1, (b0, b1))
over("verze algoritmu je cislo (soucast nazvu souboru)", isinstance(N.VERZE, int) and N.VERZE >= 2, N.VERZE)

# --- sestava dotykajici se okraje zdroje: nepada, nerozmaze, zustane ctverec
v = N.sestav_dlazdici(snimek(sestava=(0, 300, 2047, 1500)))
over("sestava od okraje k okraji: bez padu, ctverec", v.size == (N.CIL, N.CIL), v.size)

# --- prazdny snimek (jen pozadi) ------------------------------------------
v = N.sestav_dlazdici(snimek())
over("bez sestavy: vrati zmenseny original (ctverec), nepadne", v.size == (N.CIL, N.CIL) and N.zmer_dlazdici(v) is None, v.size)

# --- ulozeni na disk, atomicky, meritko ------------------------------------
with tempfile.TemporaryDirectory() as d:
    zdroj = os.path.join(d, "zdroj.jpg")
    snimek(sestava=(600, 130, 1420, 1930)).save(zdroj, "JPEG", quality=92)
    cil = os.path.join(d, "dlazdice.jpg")
    m = N.uloz_dlazdici(zdroj, cil)
    with Image.open(cil) as im:
        over("uloz_dlazdici: soubor je JPEG %dx%d" % (N.CIL, N.CIL), im.size == (N.CIL, N.CIL) and im.format == "JPEG", (im.size, im.format))
    over("uloz_dlazdici: nezustal .tmp", not os.path.exists(cil + ".tmp"), os.listdir(d))
    over("uloz_dlazdici: vrati zmereni (sirka, vyska, u_kraje)", m is not None and m[1] > 80 and m[2] is False, m)
    over("soubor je maly (< 250 kB) - dlazdice se nacitaji rychle", os.path.getsize(cil) < 250_000, os.path.getsize(cil))

print("\nVYSLEDEK dlazdice: %d/%d OK" % (sum(vysl), len(vysl)))
sys.exit(0 if all(vysl) else 1)
