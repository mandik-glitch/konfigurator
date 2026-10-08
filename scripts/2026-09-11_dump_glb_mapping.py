#!/usr/bin/env python3
"""Vygeneruje mapu `part_id -> nazev GLB souboru` z `shop_products.glb_file`.

PROC EXISTUJE: `part_id` NENI nazev GLB souboru. Vetsina produktu se sice
renderuje z `product_<id>.glb`, ale CTYRI ne (stav 2026-09-11):
    product_3045 -> product_2895        (uhelnik 30x30)
    product_3539 -> pr10
    product_3671 -> deska_lam_seda_25
    product_3939 -> deska_mdf_seda_8    (MDF deska)
Kdo si nazev souboru odvodi z part_id, u techhle ctyr nenajde nic -
`parseGlbMesh` vrati null, dil se z kontroly TISE vypadne a vysledek vypada
cistse, nez je. Tahle trida chyby uz udelala skodu dvakrat:
  2026-09-05  kolizni kontrola uhelniku merila `product_3045.glb`, ktery
              neexistuje -> "0 kolizi" bylo falesne, do produkce se zapsalo
              33 realnych kolizi (viz AGENTS_LOG.md, oprava rollbackem)
  2026-09-11  tyz filtr mel natvrdo jen JEDEN zaznam v GLBMAP, takze MDF
              desky (`product_3939`) se do kolizi nezapocitavaly vubec
Obecne pravidlo je zapsane v AGENTS_LOG.md 2026-09-05: geometricka/kolizni
kontrola MUSI mapovat pres `shop_products.glb_file`, nikdy nehadat.

Vystup: scripts/2026-09-11_glb_mapping.json (cte ho
scripts/2026-09-05_filter_uhelniky_collisions.cjs). Pust znovu, kdyz v
katalogu pribude dil nebo se zmeni glb_file.
"""
import json
import os
import sys

sys.path.insert(0, "/opt/konfigurator/scripts")

import _env  # noqa: E402
import pymysql  # noqa: E402

VYSTUP = "/opt/konfigurator/scripts/2026-09-11_glb_mapping.json"


def main():
    env = _env.load_env()
    conn = pymysql.connect(
        host=env["DB_HOST"], port=int(env["DB_PORT"]), user=env["DB_USER"],
        password=env["DB_PASSWORD"], database=env["DB_NAME"],
        cursorclass=pymysql.cursors.DictCursor,
    )
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, glb_file FROM shop_products "
                "WHERE glb_file IS NOT NULL AND glb_file <> ''"
            )
            mapa = {f"product_{r['id']}": r["glb_file"].replace(".glb", "")
                    for r in cur.fetchall()}
    finally:
        conn.close()

    if not mapa:
        print("CHYBA: z DB neprisel ani jeden produkt s glb_file - NEZAPISUJI "
              "(prazdna mapa je horsi nez zadna, viz hlavicka).", file=sys.stderr)
        return 1

    odlisne = {k: v for k, v in mapa.items() if v != k}
    data = {
        "_popis": "part_id -> nazev GLB souboru bez pripony, z shop_products.glb_file. "
                  "NEHADAT z part_id - viz AGENTS_LOG.md 2026-09-05 a hlavicka "
                  "scripts/2026-09-11_dump_glb_mapping.py.",
        "_vygenerovano": __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "_pocet": len(mapa),
        "_odlisne_od_part_id": odlisne,
        "mapa": mapa,
    }
    with open(VYSTUP, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.flush()
        os.fsync(f.fileno())

    print(f"produktu s GLB: {len(mapa)}  -> {VYSTUP}")
    print(f"z toho s ODLISNYM nazvem souboru nez part_id: {len(odlisne)}")
    for k, v in sorted(odlisne.items()):
        print(f"   {k:16} -> {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
