#!/usr/bin/env python3
"""
dimension_match_fbx_to_custom_shape.py - bot4, 2026-08-09.

Robert: "když nahraju fbx model k produktu... potřebuju aby rozeznal
jednotlivé díly, tuto proceduru jsme v minulosti zapsali, najdi to" -
navazuje na "Hotová sestava SSE" (AGENTS_LOG 2026-07-25, later smazáno -
"SSE sestavu smaz", 2026-08-04) a na api/leg_fbx_import.py (2026-08-06,
stejný princip, ale rozpoznává profily podle NÁZVU meshe ve tvaru
"<W>x<D>x<délka>", ne podle geometrie - nepoužitelné pro FBX bez
takhle pojmenovaných meshů, jako je "Dvojstůl Tchibo").

Co tenhle skript dělá: vezme SUROVÝ (nepřevedený) FBX soubor (typicky
`webapp/content-files/product_fbx/<product_id>.fbx`, uložený při
uploadu k produktu - viz PRODUCT_FBX_UPLOAD_DIR v api/app.py), rozebere
ho na jednotlivá CAD tělesa a KAŽDÉ porovná rozměrem (ne názvem) proti
katalogu hliníkových profilů (cfg_dily) - shoda průřezu (šířka×hloubka)
v toleranci pár mm = rozpoznaný profil. Nerozpoznaná tělesa (šrouby,
desky, plasty, konektory bez uložených rozměrů v katalogu - viz
AGENTS_LOG "Spojky/příslušenství nemají žádné rozměrové údaje") se
PŘESKAKUJÍ, stejně jako u leg_fbx_import.py ("stačí jen hliníková
kostra").

Výstup: JEDEN custom_shapes záznam (is_public=1) - vlastní tvar
sestavený z rozpoznaných profilů se správnou pozicí/rotací/scale,
vložitelný do scény přes normální panel "Vlastní tvary". ŽÁDNÉ nové
tlačítko/kód ve scene.html (Robert 2026-08-04 dal jasně najevo, že
podobný natvrdo zadrátovaný "vlož celou sestavu" mechanismus nechce).

Souřadnicová konvence (ověřeno na Dvojstůl Tchibo, stejná jako
leg_fbx_import.py): FBX Z-up (výška podél Z) -> scene Y-up
(scene_x=fbx_y, scene_y=fbx_z, scene_z=fbx_x). Před použitím na JINÉM
zdroji (jiný CAD nástroj/export) tuhle konvenci OVĚŘIT, ne předpokládat
- viz _verify_axis_hint().

Pouziti:
    cd /opt/konfigurator/api && set -a && source .env && set +a
    ../api/venv/bin/python3 ../scripts/dimension_match_fbx_to_custom_shape.py \\
        --fbx ../webapp/content-files/product_fbx/3672.fbx \\
        --name "Dvojstůl Tchibo - hliníková kostra" \\
        --tolerance 2.0

    (spouští se z api/, protože potřebuje import z app.py/leg_fbx_import.py
    a env proměnné DB připojení z api/.env - viz api/.env, žádný
    python-dotenv, jen skutečné env vars jako u gunicorn/systemd)
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "api"))

# bot6, 2026-08-09 (Robert: "tak tento script uloz pod tlacitkem Prevod do
# skladovych karet"): jadro (match_meshes/build_parts) presunuto do
# api/dimension_match_fbx.py, aby ho sdilel i novy endpoint
# POST /api/shop/products/<id>/decompose-fbx - tenhle skript je ted jen
# tenky CLI wrapper nad stejnou logikou (zadna duplicita).
from dimension_match_fbx import match_meshes, build_parts  # noqa: E402
from leg_fbx_import import _catalog_profiles_by_cross_section  # noqa: E402
from app import get_conn, CUSTOM_SHAPE_MAX_PARTS  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fbx", required=True, help="cesta k surovemu FBX souboru")
    ap.add_argument("--name", required=True, help="nazev noveho custom_shapes zaznamu")
    ap.add_argument("--tolerance", type=float, default=2.0, help="tolerance shody prurezu v mm (vychozi 2.0)")
    ap.add_argument("--dry-run", action="store_true", help="jen vypsat vysledek klasifikace, neukladat do DB")
    args = ap.parse_args()

    catalog = _catalog_profiles_by_cross_section()
    if not catalog:
        print("V katalogu není žádný použitelný profil (GLB, centrovaný počátek).", file=sys.stderr)
        sys.exit(1)

    profile_meshes, total = match_meshes(args.fbx, catalog, args.tolerance)
    print(f"celkem teles ve FBX: {total}")
    print(f"rozpoznano jako katalogovy profil: {len(profile_meshes)}")
    from collections import Counter
    for cross, cnt in Counter(p["cross"] for p in profile_meshes).most_common():
        print(f"  {cross[0]:.0f}x{cross[1]:.0f}: {cnt}x")

    if not profile_meshes:
        print("Žádný kus se neshoduje s katalogovým profilem - nic k uložení.", file=sys.stderr)
        sys.exit(1)
    if len(profile_meshes) > CUSTOM_SHAPE_MAX_PARTS:
        print(f"Rozpoznáno {len(profile_meshes)} dílů, limit vlastního tvaru je {CUSTOM_SHAPE_MAX_PARTS} - "
              f"zvyš toleranci naopak snížit, nebo rozděl na víc tvarů (mimo rozsah tohoto skriptu).", file=sys.stderr)
        sys.exit(1)

    parts, dims = build_parts(profile_meshes, catalog)
    print(f"rozmery sestavy (mm): sirka(X)={dims['width_x']} vyska(Y)={dims['height_y']} hloubka(Z)={dims['depth_z']}")

    if args.dry_run:
        print(json.dumps(parts, indent=1, ensure_ascii=False))
        return

    data = {"parts": parts, "join_groups": [], "frame_groups": []}
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO custom_shapes (name, data, created_by, is_public) VALUES (%s,%s,NULL,1)",
                (args.name, json.dumps(data, ensure_ascii=False)),
            )
            new_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()
    print(f"ulozeno jako custom_shapes id={new_id} (is_public=1, viditelne v panelu Vlastni tvary vsem)")


if __name__ == "__main__":
    main()
