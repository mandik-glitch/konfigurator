
import pymysql, os
env = {}
for line in open("/opt/konfigurator/api/.env"):
    line = line.strip()
    if line and "=" in line:
        k, v = line.split("=", 1)
        env[k] = v
conn = pymysql.connect(host=env["DB_HOST"], port=int(env["DB_PORT"]), user=env["DB_USER"], password=env["DB_PASSWORD"], database=env["DB_NAME"], charset="utf8mb4")
ids = ['Object_15', 'Object_17', 'Object_18', 'Object_21', 'Object_22', 'Object_25', 'Object_27', 'Object_29', 'Object_31', 'Object_34', 'Object_40']
with conn.cursor() as cur:
    fmt = ",".join(["%s"] * len(ids))
    cur.execute(f"SELECT id, glb_file FROM cfg_dily WHERE id IN ({fmt})", ids)
    rows = cur.fetchall()
    print("Mazu radky:", rows)
    for _id, glb in rows:
        path = "/opt/konfigurator/webapp/katalog/" + glb
        if os.path.exists(path):
            os.remove(path)
            print("smazan soubor:", path)
    cur.execute(f"DELETE FROM cfg_dily WHERE id IN ({fmt})", ids)
conn.commit()
with conn.cursor() as cur:
    cur.execute("SELECT COUNT(*) FROM cfg_dily")
    print("radku zbyva:", cur.fetchone()[0])
conn.close()
