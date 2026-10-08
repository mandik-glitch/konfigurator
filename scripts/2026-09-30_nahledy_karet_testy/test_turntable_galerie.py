# api/turntable.py::_fill_gallery_and_thumbnail: hlavni (galerijni) nahled karty po commitu davky je JEDNOTNA DLAZDICE
# (ctverec, stejne velka sestava), ne surovy 4:3 hero (bot4 2026-09-30). Falesny kurzor + dočasne slozky: zadna DB,
# zadne skutecne soubory v content-files. Importuje aplikaci (Flask) kvuli modulu turntable - env z api/.env nacte
# scripts/_env.py stejne jako casovace automatu.
# Spusteni: api/venv/bin/python3 test_turntable_galerie.py   (konci kodem 0 jen kdyz VSE prosla)
import os
import sys
import tempfile

sys.path.insert(0, "/opt/konfigurator/scripts")
sys.path.insert(0, "/opt/konfigurator/api")
import _env  # noqa: E402
os.environ.update(_env.load_env())

import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402
import turntable as T  # noqa: E402

vysl = []


def over(nazev, podminka, detail=None):
    vysl.append(bool(podminka))
    print(("OK   " if podminka else "FAIL ") + nazev + ("" if podminka else "  -> %r" % (detail,)))


def snimek(w, h, sestava):
    g = np.linspace(200, 20, h).astype(np.uint8)
    a = np.repeat(np.repeat(g[:, None, None], w, axis=1), 3, axis=2).copy()
    x0, y0, x1, y1 = sestava
    a[y0:y1, x0:x1] = 235
    a[y0:y1, x0:x1:7] = 90
    return Image.fromarray(a, "RGB")


class FakeCur:
    def __init__(self):
        self.sql = []
        self.lastrowid = 7

    def execute(self, sql, params=()):
        self.sql.append((" ".join(sql.split()), params))
        self._posl = " ".join(sql.split())

    def fetchone(self):
        p = self._posl
        if p.startswith("SELECT id, filename FROM content_gallery_items"):
            return None                               # zadna polozka zalozena turntablem
        if p.startswith("SELECT 1 FROM content_gallery_items"):
            return None                               # prazdna galerie
        if p.startswith("SELECT thumbnail_file FROM shop_products"):
            return {"thumbnail_file": ""}
        return None


with tempfile.TemporaryDirectory() as tmp:
    galerie = os.path.join(tmp, "gallery-items"); os.makedirs(galerie)
    thumbs = os.path.join(tmp, "thumbs"); os.makedirs(thumbs)
    T.GALLERY_ITEMS_DIR = galerie
    T.KATALOG_THUMBNAIL_DIR = thumbs
    # hero = surovy 4:3 (sestava uprostred), hero_1x1 = cisty ctverec (vyska 88 %, sirka 40 %: vysoka sestava)
    hero = os.path.join(tmp, "hero.jpg"); snimek(2048, 1536, (620, 100, 1420, 1440)).save(hero, "JPEG", quality=92)
    hero11 = os.path.join(tmp, "hero_1x1.jpg"); snimek(2048, 2048, (600, 130, 1420, 1930)).save(hero11, "JPEG", quality=92)

    cur = FakeCur()
    pridano, thumb, marks, disk = T._fill_gallery_and_thumbnail(cur, 99999, "Testovaci sestava", "testovaci-sestava", None, {},
                                                               hero_abs=hero, hero_1x1_abs=hero11)
    soubory = os.listdir(galerie)
    over("galerie: zalozena jedna polozka", pridano and len(soubory) == 1, (pridano, soubory))
    with Image.open(os.path.join(galerie, soubory[0])) as im:
        over("galerijni nahled je ctverec %d x %d (ne 4:3)" % (T._dlazdice.CIL, T._dlazdice.CIL), im.size == (T._dlazdice.CIL, T._dlazdice.CIL), im.size)
        import _nahled_dlazdice as N
        m = N.zmer_dlazdici(im)
        over("delsi strana sestavy = 85 % (+-1,5)", m and abs(max(m[0], m[1]) - 85.0) < 1.5, m)
    over("nazev souboru drzi konvenci product-<id>_<slug>-zepredu-<hex>.jpg", soubory[0].startswith("product-99999_testovaci-sestava-zepredu-") and soubory[0].endswith(".jpg"), soubory)
    over("INSERT do content_gallery_items s timhle souborem",
         any(s.startswith("INSERT INTO content_gallery_items") and soubory[0] in (p or ()) for s, p in cur.sql), [s for s, _ in cur.sql][:3])
    over("soubor je v seznamu zapsanych (uklid pri rollbacku)", os.path.join(galerie, soubory[0]) in disk["written"], disk)
    over("thumbnail se dela jako dosud (samostatne, 1024x768)", thumb and os.path.isfile(os.path.join(thumbs, "product-99999.jpg")), os.listdir(thumbs))

    # hero_1x1 chybi -> zdroj je hero (4:3); stale ctverec a bez padu
    for f in os.listdir(galerie): os.remove(os.path.join(galerie, f))
    cur = FakeCur()
    T._fill_gallery_and_thumbnail(cur, 99998, "B", "b", None, {}, hero_abs=hero, hero_1x1_abs=None)
    f2 = os.listdir(galerie)
    with Image.open(os.path.join(galerie, f2[0])) as im:
        over("bez hero_1x1: dlazdice z hero (4:3) je take ctverec", im.size == (T._dlazdice.CIL, T._dlazdice.CIL), im.size)

    # selhani post-processu -> galerie nezustane bez obrazku (puvodni kopie hero)
    for f in os.listdir(galerie): os.remove(os.path.join(galerie, f))
    puvodni = T._dlazdice.uloz_dlazdici
    T._dlazdice.uloz_dlazdici = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("simulovana chyba"))
    try:
        cur = FakeCur()
        pridano, *_ = T._fill_gallery_and_thumbnail(cur, 99997, "C", "c", None, {}, hero_abs=hero, hero_1x1_abs=hero11)
    finally:
        T._dlazdice.uloz_dlazdici = puvodni
    f3 = os.listdir(galerie)
    over("selhani dlazdice: polozka presto vznikla", pridano and len(f3) == 1, (pridano, f3))
    with open(os.path.join(galerie, f3[0]), "rb") as a, open(hero, "rb") as b:
        over("selhani dlazdice: fallback = kopie puvodniho hero", a.read() == b.read())

print("\nVYSLEDEK galerie turntable: %d/%d OK" % (sum(vysl), len(vysl)))
sys.exit(0 if all(vysl) else 1)
