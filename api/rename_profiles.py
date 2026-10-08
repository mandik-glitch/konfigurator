
import pymysql

env = {}
for line in open("/opt/konfigurator/api/.env"):
    line = line.strip()
    if line and "=" in line:
        k, v = line.split("=", 1)
        env[k] = v

conn = pymysql.connect(host=env["DB_HOST"], port=int(env["DB_PORT"]), user=env["DB_USER"], password=env["DB_PASSWORD"], database=env["DB_NAME"], charset="utf8mb4")
with conn.cursor() as cur:
    cur.execute("SELECT id, dim_x_mm, dim_y_mm, dim_z_mm FROM cfg_dily WHERE layer = %s", ("alu",))
    rows = cur.fetchall()
    for _id, x, y, z in rows:
        dims = sorted([float(x), float(y), float(z)])
        cross = dims[:2]
        new_name = f"Profil {cross[0]:.0f}x{cross[1]:.0f}mm"
        cur.execute("UPDATE cfg_dily SET name=%s WHERE id=%s", (new_name, _id))
        print(_id, "->", new_name)
conn.commit()
conn.close()
