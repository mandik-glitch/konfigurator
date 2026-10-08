"""Zapise 5 novych radku pro Doblo K-075 B (verze B) - horni blok kody
00/01/03/04/05 (kod 02 = ZAKLAD uz existuje jako id=370). Kod 06
VYNECHAN - horni_ram.js na nem hlasi 2 kolize (vypln-bok-prepazka vs
pricka-spodni-0/pricka-police-0), nedoreseno.

Vstup: /tmp/.../scratchpad/doblo_b_00_base.json (kod 00, rucne odvozeno
odebranim 9 horni-blok dilu z id=370) + hb_{01,03,04,05}_b_out.json
(vystup scripts/2026-09-05_horni_ram.js, pole "upraveneParts" = KOMPLETNI
novy seznam dilu).

Zaloha PRED zapisem: backups/2026-09-13_doblo_b_horni_bloky/pred_zapisem_370.json
(primy SELECT * z id=370 pred timhle skriptem).
"""
import json
import sys

sys.path.insert(0, "/opt/konfigurator/scripts")
from _env import get_conn  # noqa: E402
from _kod_sestavy import sestavit_kod_sestavy  # noqa: E402

SCRATCH = "/tmp/claude-0/-opt-konfigurator/c0c788fb-0783-4d56-adb5-543ba6b0dda8/scratchpad"

TEMPLATE_ID = 370  # zdroj vseho krome parts/name/kod_sestavy/horni_blok_varianta_id

ROWS = [
    # (horni_blok_varianta_id, nazev_popis_nebo_None, zdroj_parts_json_nebo_"00base")
    (1, None, "00base"),  # kod 00 - bez bloku, jmeno bez popisu bloku (boxy43-...)
    (2, "jedno pásmo, jen rám", "hb_01_b_out.json"),
    (4, "dvě pásma, jen rám, bez polic", "hb_03_b_out.json"),
    (5, "dvě pásma, police jen příčky", "hb_04_b_out.json"),
    (6, "dvě pásma, plné výplně, bez police", "hb_05_b_out.json"),
]
HB_KOD = {1: "00", 2: "01", 4: "03", 5: "04", 6: "05"}
BOX_SPEC_NAME = "boxy43-120x11"

conn = get_conn()
try:
    with conn.cursor() as cur:
        cur.execute("""SELECT category_id, car_model_id, karoserie_kod, typologie_id, umisteni_id,
                              profil_mm, verze, typologie_varianta_id, prepazka_rezerva_mm,
                              podbeh_rezerva_mm, is_public, technicky_ok, is_master, created_by,
                              shop_product_id, data
                       FROM product_assemblies WHERE id=%s""", (TEMPLATE_ID,))
        tmpl = cur.fetchone()
        tmpl_data = json.loads(tmpl["data"])

        new_ids = []
        for horni_blok_varianta_id, popis, zdroj in ROWS:
            if zdroj == "00base":
                parts = json.load(open(f"{SCRATCH}/doblo_b_00_base.json"))["parts"]
                name = f"Doblo K-075 B - {BOX_SPEC_NAME} [10/30mm od kolize]"
            else:
                out = json.load(open(f"{SCRATCH}/{zdroj}"))
                assert len(out["kolize"]) == 0, f"{zdroj}: kolize nejsou 0!"
                assert len(out["kolizeKaroserie"]) == 0, f"{zdroj}: kolizeKaroserie nejsou 0!"
                assert len(out.get("panelyMaloDrzene", [])) == 0, f"{zdroj}: panelyMaloDrzene nejsou 0!"
                parts = out["upraveneParts"]
                name = f"Doblo K-075 B - {popis} [10/30mm od kolize]"

            hb_kod = HB_KOD[horni_blok_varianta_id]
            kod_sestavy = sestavit_kod_sestavy(
                karoserie_kod=tmpl["karoserie_kod"], umisteni_kod="RL", typologie_kod="EB",
                profil_mm=tmpl["profil_mm"], verze=tmpl["verze"],
                varianta_kod=f"{tmpl['typologie_varianta_id']:04d}",
                horni_blok_kod=hb_kod, dodatek=0,
            )

            data = {
                "parts": parts,
                "join_groups": tmpl_data.get("join_groups", []),
                "frame_groups": tmpl_data.get("frame_groups", []),
                "bom": [],
                "price_summary": None,
                "_note": tmpl_data.get("_note", ""),
            }

            cur.execute("""INSERT INTO product_assemblies
                (name, category_id, car_model_id, karoserie_kod, typologie_id, umisteni_id,
                 profil_mm, verze, typologie_varianta_id, horni_blok_varianta_id, dodatek,
                 kod_sestavy, prepazka_rezerva_mm, podbeh_rezerva_mm, data, is_public,
                 technicky_ok, is_master, created_by, shop_product_id)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (name, tmpl["category_id"], tmpl["car_model_id"], tmpl["karoserie_kod"],
                 tmpl["typologie_id"], tmpl["umisteni_id"], tmpl["profil_mm"], tmpl["verze"],
                 tmpl["typologie_varianta_id"], horni_blok_varianta_id, 0,
                 kod_sestavy, tmpl["prepazka_rezerva_mm"], tmpl["podbeh_rezerva_mm"],
                 json.dumps(data, ensure_ascii=False), tmpl["is_public"],
                 0, 0, None, None))
            new_id = cur.lastrowid
            new_ids.append(new_id)
            print(f"id={new_id}  hb_kod={hb_kod}  dilu={len(parts)}  kod_sestavy={kod_sestavy}  name={name}")

        conn.commit()
        print("\nZapsano, novych ID:", new_ids)
finally:
    conn.close()
