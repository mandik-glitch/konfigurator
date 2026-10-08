"""_thumbnail_normalizace.py - jednotne ramovani nahledu karet (bot4,
2026-09-26, Robert: "vsechny rendery musi mit stejny kabat").

Diagnoza (bot3, scripts/2026-09-25_zmer_ramovani_nahledu.py): sestava na
nahledu karty zabira 28-100 % sirky ramu podle karty, protoze prstencova
kamera se fituje na NEJHORSI uhel cele otocky (spravne pro otacivy
widget), ale karta ukazuje CELNI uhel - u kazde sestavy jinak daleko od
toho nejhorsiho. `api/turntable.py` pak dela jen `img.thumbnail()` z
"hero" kanonickeho obrazku - zadna normalizace, dedi se cizi ramovani.

Tenhle modul dopocita OBSAH (median radku - pozadi je svisly gradient,
viz PRODUKTOVE_RENDERY.md) a preskaluje/dokresli tak, aby sestava
zabirala VZDY stejny podil sirky vystupniho ramu, s pozadim dokresleny
stejnym svislym prechodem, jaky uz na snimku je - zadny render v
Blenderu, cisty PIL post-process existujiciho souboru.

POZOR na past (bot3): `hero`/`thumbnails/product-*.jpg` uz muze mit
SMEAR artefakt z `_na_kanonicky_pomer()` (roztazeny okrajovy sloupec,
kdyz se sestava dotykala hrany ctverce pred prevodem na 4:3) - detekce
obsahu na TÉTO vrstve pak nemuze rozeznat smear od skutecneho obsahu.
Proto `najdi_cisty_zdroj()` prednostne hleda cisty ctvercovy `hero_1x1`
(zadny 4:3 prevod, zadny smear) a na primy thumbnail sahne az kdyz
hero_1x1 pro dany produkt neexistuje (typicky starsi 480x480 karty,
ktere skrz `_na_kanonicky_pomer()` s CIL_POMEREM=1:1 stejne nikdy
neprosly zadnym roztazenim - viz vypocet v turntable.py, ctverec->ctverec
je no-op).
"""
import glob
import os

import numpy as np
from PIL import Image

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KATALOG_THUMBNAIL_DIR = os.path.join(REPO, "webapp", "katalog", "thumbnails")
CANONICAL_DIR = os.path.join(REPO, "webapp", "content-files", "turntable")

PRAH_ODLISNOSTI = 18  # stejny prah jako scripts/2026-09-25_zmer_ramovani_nahledu.py
CIL_W, CIL_H = 1024, 768
CIL_VYPLN = 0.48  # sestava = 48 % sirky ramu, konzistentni napric katalogem.
# POZOR (bot4, 2026-09-26): musi zustat pod 0.50 - pri sirsim vyplni
# zabira sestava ve SVYCH nejsirsich radcich (napr. horizontalni horni
# traverza pres celou sirku regalu) vic nez polovinu sirky snimku, a
# median-pres-radek detekce obsahu (stejna metoda jako scripts/2026-
# 09-25_zmer_ramovani_nahledu.py) pak v TECH radcich zamenuje OBSAH za
# "pozadi" (median uz neni pozadi, kdyz ho je min nez polovina) - vysledny
# snimek vypada vizualne cistě, ale meritko ho falesne ohodnoti jako
# "100 % - u hrany". 48 % drzi i nejsirsi radek sestavy pod hranici 50 %.


def _maska_obsahu(arr):
    """arr: (h, w, 3) int16. Vraci bool masku (h, w) - True = obsah."""
    pozadi = np.median(arr, axis=1, keepdims=True)
    return np.abs(arr - pozadi).sum(axis=2) > PRAH_ODLISNOSTI


def _bbox_z_masky(maska):
    ys, xs = np.where(maska)
    if len(xs) == 0:
        return None
    return int(xs.min()), int(xs.max()), int(ys.min()), int(ys.max())


class _PozadiGradient:
    """Y -> barva pozadi. Dve urovne spolehlivosti (bot4, 2026-09-26,
    nalezeno na karte VD Transporter T6 L1 - viditelny tmavsi pruh v
    dokresleny casti pozadi):

    1) PRIMY VZOREK po sloupcich MIMO bbox obsahu (x0/x1 jsou GLOBALNI
       pres cely snimek, takze sloupce [0,x0) resp. (x1,w) jsou
       zarucene bez obsahu pro KAZDY radek) - presne skutecna barva
       tohohle radku, zadna interpolace. Pokryje drtivou vetsinu radku,
       protoze bbox skoro nikdy nesahá k OBEMA hranam soucasne.
    2) Fallback jen pro radky, kde obsah sahá k OBEMA hranam zaroven
       (bbox pres celou sirku) - NEJBLIZSI bezpecny radek (zadny obsah
       nikde v cele sirce), ne linearni interpolace mezi vzdalenymi
       body: gradient ma EASE tvar (viz _pozadi_node() v api/
       blender_render_turntable.py), rovna primka mezi dvema vzdalenymi
       body by uprostred vysla viditelne mimo skutecnou krivku."""

    def __init__(self, arr, maska, bbox):
        h, w, _ = arr.shape
        x0, x1, _, _ = bbox
        if x0 > 0:
            self._primy = np.median(arr[:, 0:x0], axis=1)
        elif x1 < w - 1:
            self._primy = np.median(arr[:, x1 + 1:w], axis=1)
        else:
            self._primy = None

        radek_ma_obsah = maska.any(axis=1)
        bezpecne_y = np.where(~radek_ma_obsah)[0]
        if len(bezpecne_y) == 0:
            barva = np.median(arr.reshape(-1, 3), axis=0)
            self._body_y = np.array([0])
            self._body_barva = barva.reshape(1, 3)
        else:
            self._body_y = bezpecne_y
            self._body_barva = np.median(arr[bezpecne_y], axis=1)

    def _interpolovany(self, y):
        """Linearni interpolace mezi dvema nejblizsimi bezpecnymi radky -
        ne "nejblizsi soused": ten na dlouhem useku (obsah pres celou
        sirku desitky/stovky radku, typicky cela vyska sestavy) vyrabi
        VIDITELNY OSTRY SKOK uprostred useku misto hladkeho prechodu -
        horsi vada nez mirne nepresny odstin, ktery linearni verze muze
        mit (bot4, 2026-09-26, nalezeno na stejne karte pri prvni
        oprave)."""
        by = self._body_y
        bc = self._body_barva
        if y <= by[0]:
            return bc[0]
        if y >= by[-1]:
            return bc[-1]
        i = np.searchsorted(by, y)
        y0, y1 = by[i - 1], by[i]
        c0, c1 = bc[i - 1], bc[i]
        if y1 == y0:
            return c0
        t = (y - y0) / (y1 - y0)
        return c0 + (c1 - c0) * t

    def barva(self, y):
        yi = int(round(y))
        if self._primy is not None and 0 <= yi < self._primy.shape[0]:
            return self._primy[yi]
        return self._interpolovany(y)


def najdi_cisty_zdroj(cur, shop_product_id, thumb_path):
    """Vrati (cesta, je_ctverec) - prednostne cisty hero_1x1 (bez smear
    artefaktu), jinak primo existujici thumbnail soubor."""
    cur.execute("SELECT slug FROM shop_products WHERE id=%s", (shop_product_id,))
    row = cur.fetchone()
    slug = (row or {}).get("slug")
    if slug:
        vzory = [
            os.path.join(CANONICAL_DIR, slug, f"{slug}-zepredu-1x1.jpg"),
        ]
        vzory += glob.glob(os.path.join(CANONICAL_DIR, slug, "*", f"{slug}-zepredu-1x1.jpg"))
        vzory += glob.glob(os.path.join(CANONICAL_DIR, slug, "*-1x1.jpg"))
        for cesta in vzory:
            if os.path.exists(cesta):
                return cesta, True
    return thumb_path, False


def normalizuj(zdroj_path, cil_w=CIL_W, cil_h=CIL_H, cil_vypln=CIL_VYPLN):
    """Nacte zdroj_path, vrati PIL.Image (RGB, cil_w x cil_h) se sestavou
    zabirajici cil_vypln podilu sirky a konzistentnim pozadim. Nikdy
    nevyhazuje - kdyz se obsah nenajde (prazdny/vadny snimek), vrati proste
    zmeny-velikosti puvodni obrazek (zadna normalizace, ale taky zadny pad)."""
    with Image.open(zdroj_path) as im:
        img = im.convert("RGB")
        arr = np.asarray(img).astype(np.int16)

    h, w, _ = arr.shape
    maska = _maska_obsahu(arr)
    bbox = _bbox_z_masky(maska)
    if bbox is None:
        return img.resize((cil_w, cil_h), Image.LANCZOS)
    gradient = _PozadiGradient(arr, maska, bbox)

    x0, x1, y0, y1 = bbox
    content_w = x1 - x0 + 1
    content_h = y1 - y0 + 1
    cx = (x0 + x1) / 2.0
    cy = (y0 + y1) / 2.0

    aspect = cil_w / cil_h
    window_w = content_w / cil_vypln
    window_h = window_w / aspect
    if content_h / window_h > cil_vypln:
        window_h = content_h / cil_vypln
        window_w = window_h * aspect

    window_w = max(window_w, 1.0)
    window_h = max(window_h, 1.0)

    out = Image.new("RGB", (int(round(window_w)), int(round(window_h))))
    out_arr = np.zeros((out.size[1], out.size[0], 3), dtype=np.uint8)

    win_x0 = cx - window_w / 2.0
    win_y0 = cy - window_h / 2.0

    for oy in range(out.size[1]):
        src_y = win_y0 + oy
        out_arr[oy, :, :] = gradient.barva(src_y)

    out = Image.fromarray(out_arr, "RGB")
    paste_x = int(round(-win_x0))
    paste_y = int(round(-win_y0))
    out.paste(img, (paste_x, paste_y))

    if out.size != (cil_w, cil_h):
        out = out.resize((cil_w, cil_h), Image.LANCZOS)
    return out
