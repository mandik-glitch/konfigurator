"""png_jpg.py - prevod renderu z PNG (s alfou) na JPEG (bez alfy).

Robert 2026-09-09: "otočný náhled proč nemůže být jpg?" -> "tak udelej
prevadec z png na jpg".

Proc to vubec je: HDRI mapa se od 2026-09-09 skryva pred kamerou
(PRODUKTOVE_RENDERY.md pravidlo 11), takze render vychazi jako PNG s
PRUHLEDNYM pozadim - mapa dal sviti a zrcadli se, ale fotka nabrezi za
sestavou uz neni. JPEG ale alfu NEUMI a pri primem ulozeni by z
pruhledneho pozadi udelal CERNE. Prevod proto neni "jen ulozit jinak":
pruhledne misto se musi nejdriv PODLOZIT barvou (compositing), teprve
pak zplostit do JPEGu.

Tim odpada puvodni falesne dilema "bud JPEG, nebo skryte pozadi" -
otocny nahled muze zustat JPEG a HDRI pozadi pritom videt nebude.

Pouziti z kodu:
    import png_jpg
    png_jpg.png_na_jpg("render.png", "render.jpg")                  # bila
    png_jpg.png_na_jpg("render.png", pozadi=(20, 22, 26))           # tmava
    png_jpg.png_na_jpg("render.png", pozadi=png_jpg.parse_barva("#f5f5f5"))

Davkove z prikazove radky: scripts/png_na_jpg.py (obal nad timhle
modulem, umi soubor i cely adresar).
"""
import os

from PIL import Image

BILA = (255, 255, 255)

# 92 = stejna kvalita, jakou uz pouziva otocny nahled
# (blender_render_turntable.py, JOB["jpeg_quality"]) - at se snimky z
# obou cest vizualne nelisi.
VYCHOZI_KVALITA = 92

POJMENOVANE_BARVY = {
    "bila": (255, 255, 255),
    "bílá": (255, 255, 255),
    "cerna": (0, 0, 0),
    "černá": (0, 0, 0),
    "seda": (240, 240, 240),
    "šedá": (240, 240, 240),
}


def parse_barva(text):
    """'#RRGGBB' / '#RGB' / 'bílá' / '240,240,240' -> (r, g, b).

    Vyhazuje ValueError na necem, co barva neni - volajici tak dostane
    srozumitelnou chybu misto tise dosazene bile.
    """
    if text is None:
        return BILA
    if isinstance(text, (tuple, list)):
        if len(text) != 3:
            raise ValueError("Barva musí mít tři složky (r, g, b).")
        return tuple(max(0, min(255, int(x))) for x in text)
    s = str(text).strip().lower()
    if s in POJMENOVANE_BARVY:
        return POJMENOVANE_BARVY[s]
    if s.startswith("#"):
        h = s[1:]
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        if len(h) != 6:
            raise ValueError(f"Neplatná hex barva: {text}")
        try:
            return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
        except ValueError:
            raise ValueError(f"Neplatná hex barva: {text}")
    if "," in s:
        casti = [c.strip() for c in s.split(",")]
        if len(casti) != 3:
            raise ValueError(f"Neplatná barva: {text}")
        try:
            return tuple(max(0, min(255, int(c))) for c in casti)
        except ValueError:
            raise ValueError(f"Neplatná barva: {text}")
    raise ValueError(f"Neznámá barva: {text}")


def png_na_jpg(zdroj, cil=None, pozadi=BILA, kvalita=VYCHOZI_KVALITA):
    """Prevede obrazek na JPEG. Vraci cestu k vyslednemu souboru.

    `pozadi` je barva, kterou se PODLOZI pruhledna mista. U neprusvitneho
    obrazku se neuplatni vubec (jen se prekoduje).
    """
    if cil is None:
        koren, _ = os.path.splitext(zdroj)
        cil = koren + ".jpg"

    with Image.open(zdroj) as im:
        # Paletove PNG s pruhlednosti (mode "P" + tRNS) alfu taky ma, jen
        # ji nemá v kanalu - prevod na RGBA ji zviditelni. Bez tohohle
        # kroku by se u nej pruhlednost tise ztratila na cernou.
        if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info):
            im = im.convert("RGBA")
            podklad = Image.new("RGB", im.size, tuple(pozadi))
            # alpha_composite pracuje nad premultiplied alfou spravne i na
            # polopruhlednych okrajich (antialiasing hran sestavy) - proste
            # `paste` bez masky by je vyrobilo jako tvrde zubate obrysy.
            podklad.paste(im, mask=im.split()[-1])
            vysledek = podklad
        else:
            vysledek = im.convert("RGB")

        vysledek.save(
            cil, "JPEG",
            quality=int(kvalita),
            optimize=True,
            # 4:4:4 - zadne podvzorkovani barev. Produktovy render ma ostre
            # hrany hliniku proti jednolitemu pozadi a vychozi 4:2:0 kolem
            # nich dela barevne trepeni.
            subsampling=0,
            progressive=True,
        )
    return cil


def prevod_slozky(adresar, pozadi=BILA, kvalita=VYCHOZI_KVALITA, smazat_png=False):
    """Prevede vsechny .png v adresari (nerekurzivne). Vraci seznam dvojic
    (zdroj, cil) uspesne prevedenych souboru."""
    hotovo = []
    for nazev in sorted(os.listdir(adresar)):
        if not nazev.lower().endswith(".png"):
            continue
        zdroj = os.path.join(adresar, nazev)
        if not os.path.isfile(zdroj):
            continue
        cil = png_na_jpg(zdroj, pozadi=pozadi, kvalita=kvalita)
        if smazat_png:
            os.remove(zdroj)
        hotovo.append((zdroj, cil))
    return hotovo
