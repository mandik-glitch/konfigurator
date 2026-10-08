import json
env = {}
with open("api/.env") as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip()
import pymysql
conn = pymysql.connect(host=env["DB_HOST"], port=int(env.get("DB_PORT", 3306)), user=env["DB_USER"],
                        password=env["DB_PASSWORD"], database=env["DB_NAME"], cursorclass=pymysql.cursors.DictCursor)
with conn.cursor() as cur:
    cur.execute("SELECT data FROM product_assemblies WHERE id=352")
    print(cur.fetchone()["data"])
conn.close()
