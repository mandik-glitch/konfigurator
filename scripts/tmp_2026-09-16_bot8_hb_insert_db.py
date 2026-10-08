import json, sys
sys.path.insert(0, "/opt/konfigurator/scripts")
from _env import get_conn

SCRATCH = "/tmp/claude-0/-opt-konfigurator/68994686-5a6b-46d4-b3c7-14bc1f68c6ac/scratchpad"
SRC_IDS = [int(x) for x in sys.argv[1:]]

conn = get_conn()
new_ids = []
with conn.cursor() as cur:
    for aid in SRC_IDS:
        inserts = json.load(open(f"{SCRATCH}/hb_insert_payload_{aid}.json"))
        for ins in inserts:
            data = {"parts": ins["parts"], "join_groups": [], "frame_groups": [], "bom": [], "price_summary": None}
            cur.execute(
                """INSERT INTO product_assemblies
                    (name, category_id, car_model_id, karoserie_kod, typologie_id, umisteni_id,
                     profil_mm, verze, typologie_varianta_id, horni_blok_varianta_id, dodatek,
                     prepazka_rezerva_mm, podbeh_rezerva_mm, mezera_police_mm, data, created_by,
                     is_public, technicky_ok, is_master)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NULL,1,0,0)""",
                (
                    "🟠 " + ins["name"], None, ins["car_model_id"], ins["karoserie_kod"],
                    ins["typologie_id"], ins["umisteni_id"], ins["profil_mm"], ins["verze"],
                    ins["typologie_varianta_id"], ins["horni_blok_varianta_id"], ins["dodatek"],
                    ins["prepazka_rezerva_mm"], ins["podbeh_rezerva_mm"], ins.get("mezera_police_mm"),
                    json.dumps(data, ensure_ascii=False),
                ),
            )
            new_ids.append(cur.lastrowid)
conn.commit()
conn.close()
print("nove_id=", new_ids)
