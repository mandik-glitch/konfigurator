#!/opt/konfigurator/api/venv/bin/python
"""Generator vodoznaku do ODVOZENEHO stromu (bot22, 2026-09-04).

Zadani (Robert): vodoznak podle nazvu domeny na vsechny obrazky na webu,
"aby neprekryval uplne obrazek"; upresneno "jeden obrazek 2-3 male loga
poloprusvitne" a "Logo: logiman.cz".

KLICOVE: NEPREPISUJE ORIGINALY. Cte z --src-root a zapisuje do --out-root se
zachovanou relativni cestou. Duvody:
  - zmena domeny = smazat vystupni strom a pregenerovat, ne obnova ze zalohy
  - zadna generacni ztrata kvality v originalech (vodoznak na vodoznaku)
  - odbrandovane storefront domeny mohou dal servirovat CISTY original
    (WORKFLOW.md pravidlo 21 bod 5 zakazuje na nich zminku materske znacky)
Vystupni strom patri MIMO webapp/ - cokoli pod webapp/ je pres catch-all
`location /` verejne na vsech storefront domenach.

TRI PASTI, na ktere generator zamerne dava pozor:
 1. Vetveni podle FORMATU z PIL (im.format), NE podle pripony. Na disku je
    301 souboru .jpeg a 337 souboru pojmenovanych .jpg, ktere jsou ve
    skutecnosti PNG s alfou - vetveni na priponu je mine.
 2. Polarita textu se NEODVOZUJE z prumerneho jasu. 670 souboru ma alfa kanal
    (convert('RGB') dobarvi pruhledno bile a namer i "cistou bilou") a
    webapp/product.html ma prepinatelny motiv, takze tentyz soubor lezi podle
    volby navstevnika na tmavem i svetlem podkladu. Misto toho neutralni bily
    text s tmavou aurou, ktera drzi kontrast sama.
 3. Rozmery v pixelech MUSI zustat shodne se zdrojem - _content_file_dimensions()
    v api/app.py cte width/height do SSR <img> z ORIGINALU; jina velikost = CLS.

Pouziti:
  scripts/watermark_build.py --src-root webapp/content-files --out-root /opt/konfigurator/wm/content-files
  scripts/watermark_build.py --files a.jpg b.jpg --out-root /tmp/ukazka   # vzorek
"""
import argparse
import io
import os
import random
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

FONT = "/usr/share/fonts/truetype/liberation/LiberationSansNarrow-Bold.ttf"
DOMENA = os.environ.get("WATERMARK_DOMAIN", "logiman.cz")

CAP_PCT = 0.022        # vyska pisma jako podil kratsi strany
CAP_MIN = 12           # px - pod tim je text necitelny
MAX_W_PCT = 0.26       # strop sirky znacky vuci sirce obrazku
OPACITY = 0.50         # krytí textu
AURA_PCT = 0.17        # tloustka aury vuci vysce pisma
MIN_SIDE = 420, 200    # pod tim se vodoznak vynechava (text by byl necitelny)
THREE_ABOVE = 600      # px kratsi strany: nad tim vic znacek, pod tim min
# Robert 2026-09-04, upresneno dvakrat: "2 vodoznaky na regal" a "a dva mimo
# regal". Tedy PRESNE 2 + 2. Znacky na produktu nejdou odstranit orezem, aniz
# by se poskodil regal; znacky na pozadi delaji znacku viditelnou.
# Pozice se hledaji z obrazku (maska produktu), ne na pevnem rastru - na
# sferickem renderu zabira regal jen 7-20 % plochy.
SAFE_MARGIN = 0.22     # podil sirky/vysky, ve kterem se znacky mimo produkt NEUMISTUJI (orezova zona)
POCET_NA_PRODUKTU = 2
POCET_MIMO_PRODUKT = 2
POCET_VELKY = POCET_NA_PRODUKTU + POCET_MIMO_PRODUKT
POCET_MALY = POCET_NA_PRODUKTU + POCET_MIMO_PRODUKT


def maska_produktu(im, prah=26, sirka=256):
    """Hruba maska "kde je produkt" - pixely dost odlisne od pozadi.

    Robert 2026-09-04: "minimalne dva vodoznaky musi byt na samotnem produktu
    navzdycky na samotnem regalu produktu, takze jich tam potrebujeme vic."
    Znacka na prazdnem pozadi jde trivialne odstranit (klonovaci razitko,
    orez) a produkt nechrani - musi lezet PRES regal.

    Pozadi se bere jako median rohu (rendery ze sceny maji svetle, temer
    jednolite pozadi). Pro fotky, kde je obsah po celem obrazku, vyjde maska
    skoro cela - kod se tim degraduje na puvodni chovani, coz je v poradku.
    """
    m = im.convert("RGB")
    r = sirka / m.width
    mw, mh = sirka, max(1, int(m.height * r))
    m = m.resize((mw, mh), Image.NEAREST)
    px = m.load()
    k = max(2, mw // 24)
    rohy = []
    for cx, cy in ((0, 0), (mw - k, 0), (0, mh - k), (mw - k, mh - k)):
        for dx in range(k):
            for dy in range(k):
                rohy.append(px[cx + dx, cy + dy])
    bg = tuple(sorted(c[i] for c in rohy)[len(rohy) // 2] for i in range(3))
    mask = [[0] * mw for _ in range(mh)]
    for y in range(mh):
        row = mask[y]
        for x in range(mw):
            c = px[x, y]
            if abs(c[0]-bg[0]) + abs(c[1]-bg[1]) + abs(c[2]-bg[2]) > prah * 3:
                row[x] = 1
    return mask, mw, mh


# Puvodni jednoducha nabidka (bot22, 2026-09-04, pred Robertovym
# upresnenim "2 na produktu + 2 mimo") - 3 znacky pevne po uhloprice
# (2 pro mensi obrazky). Ponechano jako pojmenovana varianta A pro
# rychle srovnani s aktualnim 2+2 algoritmem (varianta B) - viz
# `polohy()` nize, ktera pro fallback (mask se nenajde) pouziva totez.
ZALOHA_DIAGONALA_3 = [(0.12, 0.20), (0.38, 0.56), (0.64, 0.89)]
ZALOHA_DIAGONALA_2 = [(0.16, 0.28), (0.56, 0.76)]


def _farthest_spread(kandidati, pocet, mind, rnd, seed_body=None):
    """Vybere az `pocet` bodu z `kandidati` (list (x,y)) rozlozenych PO
    PLOSE, ne shluknutych v jednom rohu - a >= `mind` od sebe i od
    `seed_body` (uz drive umistene znacky, napr. na produktu, kdyz se
    ted vybiraji ty mimo produkt).

    OPRAVA (bot15, 2026-09-05, nález bot8 tentýž den měřením na 300
    souborech): původní `polohy()` řadila kandidáty `sort(reverse=True)`
    nad `(skore, x, y)` - u shodného skóre (typicky stovky až tisíce
    kandidátů se skóre 1.0 na běžné fotce) rozhodovalo o pořadí MAXIMÁLNÍ
    x/y, takže výběr byl SYSTEMATICKY tlačen k pravému/dolnímu okraji
    (47,6 % obrázků mělo značku na fx > 0,80). Tahle funkce netřídí podle
    souřadnic vůbec: první bod je náhodný (seed odvozený z obrázku -
    stejný soubor = stejný výsledek, ne jiný při každém běhu), každý další
    je ten NEJVZDÁLENĚJŠÍ od už vybraných (farthest-point sampling) - to
    zaručuje rozprostření po celé kvalifikující ploše bez preference
    žádného rohu.
    """
    seed_body = list(seed_body or [])
    zbyva = list(kandidati)
    rnd.shuffle(zbyva)
    vybrane = []
    while zbyva and len(vybrane) < pocet:
        referencni = seed_body + vybrane
        if not referencni:
            vybrane.append(zbyva.pop())
            continue
        best_i, best_d = 0, -1.0
        for i, (x, y) in enumerate(zbyva):
            d = min(((x - px) ** 2 + (y - py) ** 2) ** 0.5 for px, py in referencni)
            if d > best_d:
                best_d, best_i = d, i
        if best_d < mind:
            break
        vybrane.append(zbyva.pop(best_i))
    return vybrane


def polohy(w, h, n, im=None, tw=None, th=None):
    """Pozice znacek. Kdyz je znam obrazek, hleda mista NA PRODUKTU.

    Vraci seznam (fx, fy) jako podil sirky/vysky = levy horni roh znacky.
    """
    zaloha3 = ZALOHA_DIAGONALA_3
    zaloha2 = ZALOHA_DIAGONALA_2
    if im is None or tw is None:
        return zaloha3 if n == 3 else zaloha2
    try:
        mask, mw, mh = maska_produktu(im)
    except Exception:
        return zaloha3 if n == 3 else zaloha2

    # integralni obraz -> rychle skore libovolneho obdelniku
    ii = [[0] * (mw + 1) for _ in range(mh + 1)]
    for y in range(mh):
        radek = 0
        for x in range(mw):
            radek += mask[y][x]
            ii[y + 1][x + 1] = ii[y][x + 1] + radek
    def skore(x0, y0, x1, y1):
        x0 = max(0, min(mw, x0)); x1 = max(0, min(mw, x1))
        y0 = max(0, min(mh, y0)); y1 = max(0, min(mh, y1))
        if x1 <= x0 or y1 <= y0:
            return 0.0
        s = ii[y1][x1] - ii[y0][x1] - ii[y1][x0] + ii[y0][x0]
        return s / float((x1 - x0) * (y1 - y0))

    bw = max(2, int(tw * mw / float(w)))
    bh = max(2, int(th * mh / float(h)))
    kand = []
    krok = max(2, min(bw, bh) // 2)
    for y in range(0, mh - bh, krok):
        for x in range(0, mw - bw, krok):
            kand.append((skore(x, y, x + bw, y + bh), x, y))

    # seed odvozeny z obrazku (stejny soubor = stejny vysledek, ne
    # nahodny pri kazdem behu) - sdileny pro NA PRODUKTU i MIMO PRODUKT.
    seed = (mw * 7349 + mh * 13711 + int(sum(sum(r) for r in mask))) & 0xFFFFFFFF
    rnd = random.Random(seed)
    mind = max(bw, bh) * 1.6

    # (1) NA REGALU - znacka musi lezet vetsinou na produktu. Progresivni
    # uvolnovani prahu skore (misto jednoho pevneho 0.55 s tvrdym pádem
    # na genericky fallback), at se skutecne umistenych znacek na
    # produktu nevzda kvuli tomu, ze produkt zabira jen mensi/tenci
    # plochu - drivejsi verze v tomhle pripade vratila 0 znacek na
    # produktu u 15,2 % korpusu (fallback `zalohaN` je pevna uhloprickova
    # pozice, ktera produkt vubec nemusi trefit).
    na_produktu = []
    for prah in (0.55, 0.40, 0.25, 0.12):
        kandidati = [(x, y) for sc, x, y in kand if sc >= prah]
        vybrane = _farthest_spread(kandidati, POCET_NA_PRODUKTU, mind, rnd)
        if len(vybrane) > len(na_produktu):
            na_produktu = vybrane
        if len(na_produktu) >= POCET_NA_PRODUKTU:
            break
    if not na_produktu:          # produkt se vubec nenasel (degenerovana maska)
        return zaloha3 if n == 3 else zaloha2

    # (2) MIMO REGAL - na cistem pozadi, rozlozene po plose i od znacek
    # na produktu (stejna `_farthest_spread`, jen jine kandidaty a
    # postupne uvolnovany min. rozestup).
    # Robert 2026-09-04: "k nicemu jsou loga na krajich, to si kazdy orezne."
    # Znacky mimo regal proto smi lezet jen ve VNITRNI zone - kdo je chce
    # odriznout, musi oriznout i podstatnou cast obrazku vcetne produktu.
    okx, oky = SAFE_MARGIN * mw, SAFE_MARGIN * mh
    volne = [(x, y) for sc, x, y in kand
             if sc <= 0.03
             and x >= okx and y >= oky
             and x + bw <= mw - okx and y + bh <= mh - oky]
    if len(volne) < POCET_MIMO_PRODUKT:            # ve vnitrni zone neni cisté pozadi
        volne = [(x, y) for sc, x, y in kand if sc <= 0.03]
    mimo = []
    if volne:
        diag = (mw ** 2 + mh ** 2) ** 0.5
        # zkousej od velkeho rozestupu dolu, at znacky nesednou k sobe
        for podil in (0.45, 0.35, 0.25, 0.18, 0.0):
            odstup = max(mind, diag * podil)
            vybrane = _farthest_spread(volne, POCET_MIMO_PRODUKT, odstup, rnd, seed_body=na_produktu)
            if len(vybrane) > len(mimo):
                mimo = vybrane
            if len(mimo) >= POCET_MIMO_PRODUKT:
                break

    return [(x / float(mw), y / float(mh)) for x, y in na_produktu + mimo]


def vodoznak(im, domena=DOMENA, mista=None):
    """mista=None: pozice se hledaji algoritmem (polohy()). Muze byt
    predana i primo (napr. ZALOHA_DIAGONALA_3 pro srovnani "puvodni
    jednoduche" varianty se stejnou kresbou textu/aury/krytí) - pouzito
    pri porovnavacich nahledech, produkcni beh (zpracuj()) mista vzdy
    necha None."""
    w, h = im.size
    kratsi = min(w, h)
    cap = max(CAP_MIN, int(round(kratsi * CAP_PCT)))
    font = ImageFont.truetype(FONT, cap)
    # strop sirky - u dlouhych domen zmensi pismo, ne orizne text
    tw = font.getbbox(domena)[2] - font.getbbox(domena)[0]
    if tw > w * MAX_W_PCT:
        cap = max(CAP_MIN, int(cap * (w * MAX_W_PCT) / tw))
        font = ImageFont.truetype(FONT, cap)
    bb = font.getbbox(domena)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]

    if mista is None:
        n = POCET_VELKY if kratsi >= THREE_ABOVE else POCET_MALY
        mista = polohy(w, h, n, im, tw, th)
    vrstva = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(vrstva)
    aura = max(1, int(round(cap * AURA_PCT)))
    for fx, fy in mista:
        x = int(fx * w)
        y = int(fy * h)
        x = min(max(x, aura), w - tw - aura)
        y = min(max(y, aura), h - th - aura)
        # aura opacne polarity drzi kontrast na svetlem i tmavem podkladu
        d.text((x - bb[0], y - bb[1]), domena, font=font,
               fill=(0, 0, 0, int(255 * OPACITY * 0.55)),
               stroke_width=aura, stroke_fill=(0, 0, 0, int(255 * OPACITY * 0.55)))
    vrstva = vrstva.filter(ImageFilter.GaussianBlur(radius=max(1, aura * 0.6)))
    d2 = ImageDraw.Draw(vrstva)
    for fx, fy in mista:
        x = int(fx * w)
        y = int(fy * h)
        x = min(max(x, aura), w - tw - aura)
        y = min(max(y, aura), h - th - aura)
        d2.text((x - bb[0], y - bb[1]), domena, font=font,
                fill=(255, 255, 255, int(255 * OPACITY)))

    zaklad = im.convert("RGBA")
    out = Image.alpha_composite(zaklad, vrstva)
    return out


def zpracuj(src, dst):
    with Image.open(src) as im:
        fmt = im.format                     # POZOR: format, ne pripona
        puvodni = im.size
        ma_alfu = im.mode in ("RGBA", "LA", "P") and "transparency" in im.info or im.mode in ("RGBA", "LA")
        exif = im.info.get("exif")
        icc = im.info.get("icc_profile")
        if min(puvodni) < MIN_SIDE[1] or max(puvodni) < MIN_SIDE[0]:
            return "preskoceno-male"
        out = vodoznak(im)

    if out.size != puvodni:
        raise RuntimeError("rozmer se zmenil: %s -> %s" % (puvodni, out.size))

    os.makedirs(os.path.dirname(dst), exist_ok=True)
    kw = {}
    if exif:
        kw["exif"] = exif
    if icc:
        kw["icc_profile"] = icc
    if fmt == "PNG":
        out.save(dst, "PNG", optimize=True, **kw)
    elif fmt == "WEBP":
        out.save(dst, "WEBP", quality=92, method=4, **kw)
    else:                                    # JPEG i vse ostatni rastrove
        if ma_alfu:
            plocha = Image.new("RGB", out.size, (255, 255, 255))
            plocha.paste(out, mask=out.split()[3])
            out = plocha
        else:
            out = out.convert("RGB")
        out.save(dst, "JPEG", quality=92, subsampling=1, progressive=True, **kw)
    return "ok"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src-root")
    ap.add_argument("--out-root", required=True)
    ap.add_argument("--files", nargs="*", help="konkretni soubory (vzorek) misto celeho stromu")
    ap.add_argument("--limit", type=int)
    a = ap.parse_args()

    prace = []
    if a.files:
        for f in a.files:
            prace.append((f, os.path.join(a.out_root, os.path.basename(f))))
    else:
        if not a.src_root:
            ap.error("bez --files je potreba --src-root")
        for root, _dirs, files in os.walk(a.src_root):
            for f in files:
                if os.path.splitext(f)[1].lower() not in (".jpg", ".jpeg", ".png", ".webp"):
                    continue
                s = os.path.join(root, f)
                prace.append((s, os.path.join(a.out_root, os.path.relpath(s, a.src_root))))
    if a.limit:
        prace = prace[:a.limit]

    stats = {}
    for s, d in prace:
        try:
            v = zpracuj(s, d)
        except Exception as e:
            v = "chyba: %s" % e
            print("  CHYBA %s: %s" % (s, e), file=sys.stderr)
        stats[v.split(":")[0]] = stats.get(v.split(":")[0], 0) + 1
    print("zpracovano %d souboru: %s" % (len(prace), stats))


if __name__ == "__main__":
    main()
