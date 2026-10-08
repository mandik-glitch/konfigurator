import sys, json
sys.path.insert(0, "/opt/konfigurator/scripts")
from _env import get_conn

NEW_PARTS = json.load(open(
    "/tmp/claude-0/-opt-konfigurator/68994686-5a6b-46d4-b3c7-14bc1f68c6ac/scratchpad/bot8_profil30_demo_parts.json"
))

conn = get_conn()
with conn.cursor() as cur:
    cur.execute("SELECT * FROM product_assemblies WHERE id=414")
    src = cur.fetchone()

data = json.loads(src["data"])
data["parts"].append(NEW_PARTS["profil"])
data["parts"].append(NEW_PARTS["rozek1"])
data["parts"].append(NEW_PARTS["rozek2"])
# bom/price_summary v data jsou z 414 (bez noveho kusu) - test kopie neni pro
# prodej/cenu, jen pro vizualni oznaceni, necham je beze zmeny.

new_name = "🔧TEST bot8 - profil 30x30 130mm + 2 rožky (modře) - kopie K-122 A-01"

with conn.cursor() as cur:
    cur.execute(
        """
        INSERT INTO product_assemblies
            (name, category_id, car_model_id, karoserie_kod, typologie_id, umisteni_id,
             profil_mm, verze, typologie_varianta_id, horni_blok_varianta_id, dodatek,
             kod_sestavy, prepazka_rezerva_mm, podbeh_rezerva_mm, data, created_by,
             is_public, technicky_ok, is_master)
        VALUES (%s, NULL, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                NULL, %s, %s, %s, NULL, 0, 0, 0)
        """,
        (
            new_name, src["car_model_id"], src["karoserie_kod"], src["typologie_id"], src["umisteni_id"],
            src["profil_mm"], src["verze"], src["typologie_varianta_id"], src["horni_blok_varianta_id"], src["dodatek"],
            src["prepazka_rezerva_mm"], src["podbeh_rezerva_mm"], json.dumps(data, ensure_ascii=False),
        ),
    )
    new_id = cur.lastrowid
conn.commit()
conn.close()
print("novy_id=", new_id, "celkem_dilu=", len(data["parts"]))
