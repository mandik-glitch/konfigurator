#!/usr/bin/env python3
"""Zpetny backfill shop_products.vandr_hlavni_prurez_mm pro VSECHNY
aktivni Vandr karty (Robert 2026-09-25, pres bot3: sestavy maji na
karte nest graficke stitky - hlavni profil + strana auta; umisteni uz
shop_products.umisteni_id ma, hlavni profil se dosud jen POCITAL za
behu konverze a nikde nezustal).

Prepocitava PRIMO z jiz nasazeneho GLB pres `overit_final_glb()`
(2026-09-23_vandr_fbx_konverze_auto_dispatch.py, import, ne kopie) -
STEJNA funkce, ktera od dnes plni sloupec u NOVYCH karet pri konverzi
(viz `nasad_a_zapis()` tamtez). Bot3 vyslovne: "ať se ukládá hodnota ze
SPRÁVNÉHO výpočtu, ne nový výpočet vedle" - a "pozor na tvůj vlastní
dnešní nález" (dispatch mel do dnesni opravy STARSI regex nez
razitkovac, chybel mu pismenny prefix `SL...` u vodorovnych pricek -
karta #4586 tim dostala falesne (30,30) misto (40,40), viz AGENTS_LOG.md
2026-09-25). Tenhle skript bezi AZ PO te oprave, takze vsech 40 karet
dostane hodnotu ze SPRAVNEHO (opraveneho) vypoctu, ne ze stareho.

Nepocita "odhad z nazvu" ani jinou zkratku - pro kazdou kartu skutecne
znovu naimportuje jeji GLB do Blenderu (presne jako pri konverzi/
overeni), overit_final_glb() zabali (vraci i `prurez=None`, kdyz zadny
NNxNNxLLL kandidat/neni ctvercovy - takove karty se VYPISI jako
CHYBY/NEURCENO, sloupec zustava NULL, ZADNE hadani).

Pouziti (NA SERVERU, /opt/konfigurator):
    api/venv/bin/python3 scripts/2026-09-25_vandr_hlavni_prurez_backfill.py           # dry-run, jen vypis
    api/venv/bin/python3 scripts/2026-09-25_vandr_hlavni_prurez_backfill.py --apply   # skutecny zapis
"""
import argparse
import importlib.util
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
from _env import get_conn  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "vandr_fbx_konverze_auto_dispatch",
    os.path.join(REPO, "scripts", "2026-09-23_vandr_fbx_konverze_auto_dispatch.py"))
_dispatch = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_dispatch)

VD_SKU_REGEXP = r"^VD-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    print(f"=== Vandr hlavni_prurez backfill — {'APPLY' if args.apply else 'DRY-RUN'} ===\n")

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, sku, name, glb_file, vandr_hlavni_prurez_mm FROM shop_products "
                "WHERE sku REGEXP %s AND active=1 ORDER BY id", (VD_SKU_REGEXP,))
            karty = cur.fetchall()
        print("Aktivnich Vandr karet (rozsah backfillu): %d\n" % len(karty))

        rozlozeni = {}
        chyby = []
        for k in karty:
            glb_path = os.path.join(_dispatch.KATALOG_DIR, k["glb_file"])
            if not os.path.isfile(glb_path):
                chyby.append((k["id"], k["sku"], "GLB soubor chybi na disku: %s" % glb_path))
                continue
            ok, hlaseni, prurez = _dispatch.overit_final_glb(glb_path)
            prurez_mm = prurez[0] if prurez and prurez[0] == prurez[1] else None
            if prurez and prurez_mm is None:
                chyby.append((k["id"], k["sku"], "hlavni profil NENI ctvercovy: %s - potreba rucni rozhodnuti formatu" % (prurez,)))
                continue
            if prurez_mm is None:
                chyby.append((k["id"], k["sku"], "zadny NNxNNxLLL kandidat nenalezen (%s)" % hlaseni))
                continue
            rozlozeni[prurez_mm] = rozlozeni.get(prurez_mm, 0) + 1
            puvodni = k["vandr_hlavni_prurez_mm"]
            znacka = "" if puvodni == prurez_mm else " (ZMENA z %s)" % puvodni
            print("  %d %-45s -> %d%s" % (k["id"], k["sku"], prurez_mm, znacka))
            if args.apply:
                with conn.cursor() as cur:
                    n = cur.execute(
                        "UPDATE shop_products SET vandr_hlavni_prurez_mm=%s WHERE id=%s",
                        (prurez_mm, k["id"]))
                if n != 1:
                    chyby.append((k["id"], k["sku"], "UPDATE zapsal %d radku misto 1" % n))
        if args.apply:
            conn.commit()

        print("\nROZLOZENI (hlavni profil mm -> pocet karet): %s" % dict(sorted(rozlozeni.items())))
        print("Soucet karet s urcenym profilem: %d z %d" % (sum(rozlozeni.values()), len(karty)))
        if chyby:
            print("\nCHYBY/NEURCENO (%d) - sloupec zustava NULL, potreba se podivat rucne:" % len(chyby))
            for cid, sku, msg in chyby:
                print("  %d %s: %s" % (cid, sku, msg))
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
