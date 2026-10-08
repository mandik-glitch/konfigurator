#!/usr/bin/env python3
# Prestavba horniho bloku C-02/C-04/C-05/C-06 (344/343/345/347) presne podle
# noveho zapsaneho postupu shape_geometry_methods.id=13 (Robert 2026-09-14:
# "udelat proste nove horni bloky varianty doblo C" - podle stejneho receptu,
# ktery ted plati pro A/B, aby cela K-075 rodina byla jednotna). Zaloha
# hotova (backups/2026-09-14_doblo_c_pred_novym_hornim_blokem.json).
import sys, json
sys.path.insert(0, "/opt/konfigurator/scripts")
from _env import get_conn

HB_PREFIXES = ("podelnik-", "pricka-spodni", "pricka-horni", "pricka-police", "vypln-")
def is_hb(p):
    return (p.get("role") or "").startswith(HB_PREFIXES)

TARGETS = {344: "01", 343: "02", 345: "03", 347: "04"}

conn = get_conn()
try:
    with conn.cursor() as cur:
        cur.execute("SELECT definition FROM shape_geometry_methods WHERE id=13")
        recipe = json.loads(cur.fetchone()["definition"])

        current = {}
        for aid in TARGETS:
            cur.execute("SELECT data FROM product_assemblies WHERE id=%s", (aid,))
            current[aid] = json.loads(cur.fetchone()["data"])

    out = {}
    for aid, label in TARGETS.items():
        d = current[aid]
        old_hb = [p for p in d["parts"] if is_hb(p)]
        kept = [p for p in d["parts"] if not is_hb(p)]
        new_hb = [dict(p) for p in recipe["varianty"][label]["dily"]]
        after = kept + new_hb
        out[aid] = {
            "label": label, "kept_count": len(kept),
            "old_hb_count": len(old_hb), "new_hb_count": len(new_hb),
            "old_hb_roles": sorted(p["role"] for p in old_hb),
            "new_hb_roles": sorted(p["role"] for p in new_hb),
            "after_parts": kept + new_hb,
        }
        print(f"id={aid} (C-{label}... viz nazev): {len(d['parts'])} -> {len(after)} dilu "
              f"(hb {len(old_hb)} -> {len(new_hb)})")
        old_set, new_set = set(out[aid]["old_hb_roles"]), set(out[aid]["new_hb_roles"])
        if old_set != new_set:
            print("   role ODEBRANE:", sorted(old_set - new_set))
            print("   role PRIDANE :", sorted(new_set - old_set))
        else:
            print("   stejna sada roli jako drive (ocekavano u 03/04)")

    with open("/tmp/claude-0/-opt-konfigurator/68994686-5a6b-46d4-b3c7-14bc1f68c6ac/scratchpad/c_rebuild_payload.json", "w") as f:
        json.dump(out, f, ensure_ascii=False)
    print("\npayload ulozen pro dalsi kolizni overeni.")
finally:
    conn.close()
