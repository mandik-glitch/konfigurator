"""#374: nahrazuje "vyrez" konstrukci prostredni nohy (Z=-898.5) presnou
kopii profilu z prvni ("prepazkove") nohy (Z=-1350.5) - Robert: "más jen
udelat stejne profily jako jsou na prvni prepazkove noze... aplikovat na
prostredni noze u kraje podbehu ty profily vymenit".

ODSTRANUJE (vyrez-specificke, Z=-898.5): predni-svislice (zkracena),
cap (zkraceny), zadni-svislice-nad-zarezem, sloupek-pred-podbehem,
zaslepka-zadni-svislice-nad-zarezem, spojnice-horni-uzavreni,
spojnice-dolni, pricka-uzavreni-vyrezu (8 dilu - zadny z nich prvni noha
nema, jsou to vyrez-specificke propojky/zavery, ktere po odstraneni
sloupku/zadni-svislice-nad-zarezem nemaji ceho se drzet).
Take 12x uhelnik-noha1 na teto Z (vazany na STAROU geometrii, po zmene
nohy uz nesedi - potrebuji samostatny prepocet, NEODSTRANUJE se jinam).

PRIDAVA (kopie z prvni nohy, jen Z zmeneno na -898.5): predni-svislice,
zadni-svislice-dolni, cap + 3x zaslepka (6 dilu).

Zaloha PRED zapisem."""
import copy
import json
import os
import sys

sys.path.insert(0, "/opt/konfigurator/scripts")
from _env import get_conn  # noqa: E402

AID = 374
Z_STARE = -1350.5025482177734  # prvni ("prepazkova") noha - zdroj kopie
Z_NOVE = -898.5025482177734    # prostredni noha - cil

ODSTRANIT_ROLE = {
    "predni-svislice", "cap", "zadni-svislice-nad-zarezem", "sloupek-pred-podbehem",
    "zaslepka-zadni-svislice-nad-zarezem", "spojnice-horni-uzavreni",
    "spojnice-dolni", "pricka-uzavreni-vyrezu",
}
KOPIROVAT_ROLE = {"predni-svislice", "zadni-svislice-dolni", "cap",
                   "zaslepka-predni-svislice", "zaslepka-zadni-svislice-dolni", "zaslepka-cap"}


def main():
    dry = "--dry-run" in sys.argv
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name, data FROM product_assemblies WHERE id=%s", (AID,))
            row = cur.fetchone()
            d = json.loads(row["data"])
            parts = d["parts"]

            # 1) zdrojove dily z prvni nohy (presna Z shoda)
            zdroj = [p for p in parts
                     if p.get("role") in KOPIROVAT_ROLE and abs(p["position"][2] - Z_STARE) < 1]
            print(f"Zdrojovych dilu z prvni nohy (Z={Z_STARE:.1f}): {len(zdroj)}")
            for p in zdroj:
                print("  ", p["role"], p["position"])
            assert len(zdroj) == 6, f"cekano 6 zdrojovych dilu, mam {len(zdroj)}"

            # 2) odstranit vyrez-specificke dily na prostredni noze (presna Z shoda)
            pred = len(parts)
            odstraneno_uhelniku = sum(
                1 for p in parts
                if p.get("role") == "uhelnik-noha1" and abs(p["position"][2] - Z_NOVE) < 20
            )
            parts = [p for p in parts if not (
                p.get("role") in ODSTRANIT_ROLE and abs(p["position"][2] - Z_NOVE) < 1
            )]
            parts = [p for p in parts if not (
                p.get("role") == "uhelnik-noha1" and abs(p["position"][2] - Z_NOVE) < 20
            )]
            odstraneno = pred - len(parts)
            print(f"Odstraneno dilu: {odstraneno} (z toho {odstraneno_uhelniku} uhelniku-noha1)")

            # 3) pridat kopie z prvni nohy, jen Z zmenene
            nove = []
            for p in zdroj:
                np_ = copy.deepcopy(p)
                np_["position"][2] = Z_NOVE
                nove.append(np_)
            parts.extend(nove)
            print(f"Pridano dilu: {len(nove)}")

            d["parts"] = parts
            d["bom"] = []
            d["price_summary"] = None

            print(f"\nCelkem dilu: {pred} -> {len(parts)}")

            if not dry:
                os.makedirs("/opt/konfigurator/backups/2026-09-13_swap_stredni_noha_374", exist_ok=True)
                with open("/opt/konfigurator/backups/2026-09-13_swap_stredni_noha_374/pred_zapisem.json", "w", encoding="utf-8") as f:
                    json.dump(row, f, ensure_ascii=False, indent=1, default=str)
                cur.execute(
                    "UPDATE product_assemblies SET data=%s, kolize_pocet=NULL, kolize_checked_at=NULL WHERE id=%s",
                    (json.dumps(d, ensure_ascii=False), AID),
                )
                conn.commit()
                print("\nCOMMIT hotovy. Zaloha: backups/2026-09-13_swap_stredni_noha_374/pred_zapisem.json")
                print(f"POZOR: {odstraneno_uhelniku} uhelniku-noha1 odstraneno bez nahrady - "
                      "potrebuji samostatny prepocet (applyUhelnikyToLeg) pred schvalenim.")
            else:
                print("\nDRY-RUN, nic nezapsano.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
