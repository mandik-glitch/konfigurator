"""Odvozeni 'Doblo K-075 A' kod 00 (bez hor. bloku) a 01 (jedno pasmo, jen ram)
z JIZ HOTOVE a overene sestavy id=369 (kod 02, ZAKLAD) odectenim rolí, ktere
horni blok pridal - presne stejna struktura potvrzena na verzi C (346=00,
342=01, 344=02): kod 01 = 00 + podelnik(4)+pricka-spodni(3); kod 02 = 01 +
vypln-dno(2). Overeno diffem poctu roli 134(2/20mm,bez bloku) vs 369(10/30mm,
02) - presne tehle 9 roli chybi v 134 a nic jineho, tedy 369 minus tehle 9 =
bezpecny 00 zaklad (pozice zbylych dilu jsou UZ overene 0-kolizni z puvodniho
zapisu 369, odecitani dilu nemuze vyrobit novou kolizi).

Zdroj: id=369 ("Doblo K-075 A - jedno pásmo, rám + dna [ZÁKLAD] [10/30mm od
kolize]"). NIC se v 369 NEMENI - jen se cte.
"""
import json
import sys

sys.path.insert(0, "/opt/konfigurator/scripts")
from _env import get_conn  # noqa: E402
from _kod_sestavy import sestavit_kod_sestavy  # noqa: E402

SRC_ID = 369
VYPLN_DNO_ROLES = {"vypln-dno-0", "vypln-dno-1"}
HORNI_BLOK_ROLES = VYPLN_DNO_ROLES | {
    "podelnik-celni-spodni-0", "podelnik-celni-spodni-1",
    "podelnik-zadni-spodni-0", "podelnik-zadni-spodni-1",
    "pricka-spodni-0", "pricka-spodni-1", "pricka-spodni-2",
}

conn = get_conn()
with conn.cursor() as cur:
    cur.execute("SELECT * FROM product_assemblies WHERE id=%s", (SRC_ID,))
    src = cur.fetchone()
    src_data = json.loads(src["data"])
    parts = src_data["parts"]

    role_counts = {}
    for p in parts:
        role_counts[p.get("role")] = role_counts.get(p.get("role"), 0) + 1
    for r in HORNI_BLOK_ROLES:
        assert role_counts.get(r) == 1, f"ocekavano presne 1x role {r}, nalezeno {role_counts.get(r)}"
    print(f"Zdroj {SRC_ID}: {len(parts)} dilu, {len(HORNI_BLOK_ROLES)} roli k odstraneni potvrzeno pritomnych presne 1x.")

    def bez_roli(vyloucit):
        return [p for p in parts if p.get("role") not in vyloucit]

    varianty = {
        "00": {"vyloucit": HORNI_BLOK_ROLES, "hbv_id": 1, "nazev_blok": None},
        "01": {"vyloucit": VYPLN_DNO_ROLES, "hbv_id": 2, "nazev_blok": "jedno pásmo, jen rám"},
    }

    vlozeno = []
    for kod, spec in varianty.items():
        new_parts = bez_roli(spec["vyloucit"])
        expected = len(parts) - len(spec["vyloucit"])
        assert len(new_parts) == expected, f"kod {kod}: cekano {expected} dilu, je {len(new_parts)}"

        kod_sestavy = sestavit_kod_sestavy(
            karoserie_kod=src["karoserie_kod"], umisteni_kod="RL", typologie_kod="EB",
            profil_mm=src["profil_mm"], verze=src["verze"],
            varianta_kod=f"{src['typologie_varianta_id']:04d}",
            horni_blok_kod=kod, dodatek=0,
        )
        if spec["nazev_blok"]:
            name = f"Doblo K-075 A - {spec['nazev_blok']} [10/30mm od kolize]"
        else:
            name = "Doblo K-075 A - boxy43-270x1-220x1-170x1-120x6 [10/30mm od kolize]"

        new_data = {
            "parts": new_parts,
            "join_groups": src_data.get("join_groups", []),
            "frame_groups": src_data.get("frame_groups", []),
            "bom": [],
            "price_summary": None,
            "_note": (
                f"bot8 (subagent) 2026-09-13: odvozeno od id={SRC_ID} odectenim roli "
                f"{sorted(spec['vyloucit'])} (presna shoda se strukturou overenou na verzi C, "
                f"346=00/342=01/344=02). Zbyle dily beze zmeny pozice - jiz overene 0-kolizni "
                f"v puvodnim zapisu id={SRC_ID} (viz jeho _note, SAT test 0/101 kolizi). "
                f"bom/price_summary nedopocitano (ceka na katalogovy prepocet)."
            ),
        }

        cur.execute(
            """INSERT INTO product_assemblies
               (name, category_id, car_model_id, karoserie_kod, typologie_id, umisteni_id,
                profil_mm, verze, typologie_varianta_id, horni_blok_varianta_id, dodatek,
                kod_sestavy, prepazka_rezerva_mm, podbeh_rezerva_mm, is_public, technicky_ok,
                is_master, data)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (name, src["category_id"], src["car_model_id"], src["karoserie_kod"],
             src["typologie_id"], src["umisteni_id"], src["profil_mm"], src["verze"],
             src["typologie_varianta_id"], spec["hbv_id"], 0, kod_sestavy,
             src["prepazka_rezerva_mm"], src["podbeh_rezerva_mm"], src["is_public"], 0, 0,
             json.dumps(new_data, ensure_ascii=False)),
        )
        new_id = cur.lastrowid
        vlozeno.append((new_id, kod, name, len(new_parts)))
        print(f"Vlozeno id={new_id} kod={kod} dilu={len(new_parts)} kod_sestavy={kod_sestavy} name={name}")

    conn.commit()

print("\nHOTOVO:", vlozeno)
conn.close()
