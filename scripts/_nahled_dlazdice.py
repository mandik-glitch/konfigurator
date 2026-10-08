"""Jednotna dlazdice (nahled) karty: vsechny karty ve STEJNEM formatu a se sestavou STEJNE velkou
(bot4 2026-09-30, Robert 2026-09-25 "PODRUHE": nahledy sestav na kartach musi byt VSECHNY stejne velke a ve
stejnem formatu).

Diagnoza (zmereno 2026-09-30 na skutecnych obrazcich, ktere ukazuji dlazdice kategorii = prvni verejna
polozka galerie): Vandr karty maji surovy snimek otocky 2048x2048 (sestava 40-91 % sirky, rozptyl 51 p.b.),
nativni surovy `hero` 2048x1536 (41-67 %) - dva formaty a velka variabilita, protoze prstencova kamera se
fituje na NEJHORSI uhel otocky. Drivejsi normalizace z 26. 9. (`_thumbnail_normalizace.py`) se tyka jen
`thumbnails/product-<id>.jpg`, ktere dlazdice nepouzivaji.

Tenhle modul z existujiciho snimku (zadny render, zadna GPU) vyrobi ctverec CIL x CIL, kde DELSI STRANA sestavy
(vyska u vysoke/uzke, sirka u dlouhe/siroke) zabira vzdy stejny podil VYPLN ctverce, vycentrovana, s pozadim
dokreslenym stejnym svislym prechodem, jaky na snimku uz je. Proc delsi strana a ne sirka: sestavy maji ruzny
pomer stran (zmereno 0,46 az 1,6 - kratka dodavka je vysoka a uzka, dlouha siroka), "stejna sirka" by vysoke
sestavy vyhnala za okraj; stejna delsi strana drzi vsechny stejne "velke" a zadna nepretece.

DETEKCE SESTAVY (VERZE 2, 2026-09-30) - robustni i pro sirokou sestavu a ignoruje mekky stin podlahy: pozadi kazdeho radku se bere z KRAJNICH sloupcu (sestava se
okraje zdroje nedotyka, TT_MARGIN 1,04 v scripts/2026-09-09_turntable_job.py), ne z medianu radku. Median radku
(metoda z scripts/2026-09-25_zmer_ramovani_nahledu.py a _thumbnail_normalizace.py) selze, kdyz sestava zabira
vic nez polovinu sirky radku - pak pokladá sestavu za pozadi a hlasi "100 % / u hrany". Proto je tu vlastni
detekce a stare meritko se na vysledek nepouziva.

Prah 30 (ne 18) je zamerny: kolem siroke sestavy lezi na podlaze mekky stin/odraz (rozdil 20-28), ktery citlivejsi
prah 18 bral za sestavu a nafoukl obalku az o 27 p.b. (karta 4925: 90 % misto 63 %) - sestava pak na dlazdici vysla
zbytecne mala. Svisle rozmery se mezi prahy lisi nejvyse o 1,8 % vysky (tmave spodky na cerne podlaze prah 30
neuriznul), vodorovne ano. Zmenis-li algoritmus, zvys VERZE - generatory podle ni znovu vyrobi existujici dlazdice.

Kdyz se sestava presto dotyka okraje zdroje (zdroj je orizly), rozsirit pozadi do stran nejde bez rozmazani
okraje; okno se pak omezi na zdroj (sestava bude vetsi nez cilova vyplni, ale nic se nerozmazava).
Nikdy nevyhazuje: bez nalezeneho obsahu vrati puvodni snimek zmenseny na CIL x CIL.
"""
import numpy as np
from PIL import Image

CIL = 1024             # vystup CIL x CIL (dlazdice kategorie je 1:1, zobrazuje se ~300-400 px, 2x retina)
VYPLN = 0.85           # DELSI strana sestavy = 85 % strany ctverce (okraj ~7,5 % z kazde strany)
VERZE = 2              # verze algoritmu; soucast nazvu souboru dlazdice (-t1024v2.jpg), zmena = prepocet vsech
PRAH_ODLISNOSTI = 30   # soucet |RGB - pozadi radku|, nad tim je to sestava (mekky stin podlahy je pod nim)
KRAJ_SLOUPCU = 6       # kolik krajnich sloupcu z kazde strany dava pozadi radku
MIN_PIXELU = 12        # radek/sloupec s mene pixely obsahu je sum, ne sestava
JPEG_KVALITA = 88


def _bbox_sestavy(arr):
    """(x0, x1, y0, y1) obalky sestavy v poli (h, w, 3) int16, nebo None."""
    kraj = np.concatenate([arr[:, :KRAJ_SLOUPCU, :], arr[:, -KRAJ_SLOUPCU:, :]], axis=1)
    pozadi = np.median(kraj, axis=1, keepdims=True)
    maska = np.abs(arr - pozadi).sum(axis=2) > PRAH_ODLISNOSTI
    # radek/sloupec patri sestave, az kdyz v nem svitilo aspon MIN_PIXELU pixelu - izolovany sum (JPEG, jemny
    # stin) jinak nafoukne obalku o desitky pixelu (nalezeno na karte 4528: 79 % misto 85 % po normalizaci)
    sloupce = np.where(maska.sum(axis=0) >= MIN_PIXELU)[0]
    radky = np.where(maska.sum(axis=1) >= MIN_PIXELU)[0]
    if len(sloupce) == 0 or len(radky) == 0:
        return None
    return int(sloupce.min()), int(sloupce.max()), int(radky.min()), int(radky.max())


def sestav_dlazdici(img, cil=CIL, vypln=VYPLN):
    """PIL.Image (libovolny format) -> PIL.Image RGB cil x cil. Viz hlavicka modulu."""
    img = img.convert("RGB")
    arr = np.asarray(img).astype(np.int16)
    h, w, _ = arr.shape
    bbox = _bbox_sestavy(arr)
    if bbox is None:
        return img.resize((cil, cil), Image.LANCZOS)
    x0, x1, y0, y1 = bbox
    bw, bh = x1 - x0 + 1, y1 - y0 + 1
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    strana = max(bw, bh) / vypln
    dotyka_okraje = x0 <= 1 or x1 >= w - 2
    if dotyka_okraje:
        strana = min(strana, float(min(w, h)))        # nerozsirovat pozadi, sestava je orizla zdrojem
    strana = max(strana, 2.0)
    # okno [ox, ox+strana) x [oy, oy+strana) ve zdrojovych souradnicich; u orizle sestavy se posune dovnitr zdroje
    ox, oy = cx - strana / 2.0, cy - strana / 2.0
    if dotyka_okraje:
        ox = min(max(ox, 0.0), max(0.0, w - strana))
        oy = min(max(oy, 0.0), max(0.0, h - strana))
    ix0, iy0 = int(round(ox)), int(round(oy))
    n = int(round(strana))
    # doplneni pozadi mimo zdroj = opakovani krajniho radku/sloupce (pozadi je svisly gradient, takze prodlouzeni
    # doprava/doleva je bez stopy a nahore/dole plynule navazuje na plochy konec gradientu)
    pad_l, pad_t = max(0, -ix0), max(0, -iy0)
    pad_r, pad_b = max(0, ix0 + n - w), max(0, iy0 + n - h)
    src = np.asarray(img)
    if pad_l or pad_t or pad_r or pad_b:
        src = np.pad(src, ((pad_t, pad_b), (pad_l, pad_r), (0, 0)), mode="edge")
    sx0, sy0 = ix0 + pad_l, iy0 + pad_t
    vyrez = src[sy0:sy0 + n, sx0:sx0 + n]
    return Image.fromarray(vyrez, "RGB").resize((cil, cil), Image.LANCZOS)


def uloz_dlazdici(zdroj_cesta, cil_cesta, **kw):
    """Nacte zdroj, vyrobi dlazdici a ulozi JPEG (atomicky pres .tmp). Vraci (sirka_pct, vyska_pct) sestavy ve
    vystupu (kontrola), nebo None kdyz se obsah nenasel."""
    import os
    with Image.open(zdroj_cesta) as im:
        vystup = sestav_dlazdici(im, **kw)
    tmp = cil_cesta + ".tmp"
    vystup.save(tmp, "JPEG", quality=JPEG_KVALITA, optimize=True, progressive=True)
    os.replace(tmp, cil_cesta)
    return zmer_dlazdici(vystup)


def zmer_dlazdici(img):
    """(sirka_pct, vyska_pct, u_kraje) sestavy ve VYSTUPNI dlazdici (stejna robustni detekce). None bez obsahu."""
    arr = np.asarray(img.convert("RGB")).astype(np.int16)
    b = _bbox_sestavy(arr)
    if b is None:
        return None
    h, w, _ = arr.shape
    x0, x1, y0, y1 = b
    return (100.0 * (x1 - x0 + 1) / w, 100.0 * (y1 - y0 + 1) / h, bool(x0 <= 1 or x1 >= w - 2 or y0 <= 1 or y1 >= h - 2))
