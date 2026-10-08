"""Jednorazova oprava sestavy 340 (NEZAMCENA) - jedno zrcadlove/o 180 stupnu
otocene logo (role logo-ochrana-logo-5), zjisteno OPRAVENYM plosnym scanem
2026-09-12 (bot9). Predchozi hruby scan oznacoval za spatne role -4 a -6,
ale ty maji presne kvaternion jiz drive render+zoomem overene jako SPRAVNY
(zadniGOOD) - opraveny predikat + primo overene kvaterniony z DB potvrzuji,
ze spatne je jen role -5 (kvaternion bit-presne odpovida drive zoomem
overenemu zadniBAD vzorku).

Oprava = 180 stupnu otoceni loga kolem VLASTNI outward normaly (lokalni Z),
tedy stejna normala (logo poletí porad na stejne misto/stenu), jen spravny
smer cteni textu. Priamy JSON patch na product_assemblies.data, NIKDY pres
scene.html (viz WORKFLOW.md zamek/scena pravidla - tohle je nezamcena
sestava, ale i tak zadna geometrie se neuklada pres scenu).

Zaloha puvodnich dat: backups/2026-09-12_asm340_logo5_pred_opravou.json
"""
import json
import sys

sys.path.insert(0, "/opt/konfigurator/scripts")
import pymysql
from pymysql.cursors import DictCursor
from _env import load_env

from razitkovac import _kvaternion_z_baze, _rotuj, _norm, _neg

ASSEMBLY_ID = 340
ROLE = "logo-ochrana-logo-5"

cfg = load_env()
conn = pymysql.connect(host=cfg["DB_HOST"], port=3306, user=cfg["DB_USER"],
                        password=cfg["DB_PASSWORD"], database=cfg["DB_NAME"],
                        charset="utf8mb4", cursorclass=DictCursor, autocommit=False)
cur = conn.cursor()
cur.execute("SELECT data FROM product_assemblies WHERE id=%s FOR UPDATE", (ASSEMBLY_ID,))
row = cur.fetchone()
data = json.loads(row["data"])
parts = data["parts"]

cil = None
for p in parts:
    if p.get("role") == ROLE:
        cil = p
        break
if cil is None:
    raise SystemExit(f"role {ROLE} v sestave {ASSEMBLY_ID} nenalezena")

q_stary = list(cil["quaternion"])
x_osa = _norm(_rotuj(q_stary, (1.0, 0.0, 0.0)))
y_osa = _norm(_rotuj(q_stary, (0.0, 1.0, 0.0)))
z_osa = _norm(_rotuj(q_stary, (0.0, 0.0, 1.0)))
q_novy = _kvaternion_z_baze(_neg(x_osa), _neg(y_osa), z_osa)

print("PRED: ", q_stary)
print("PO:   ", q_novy)
print("normala (nezmenena):", z_osa)

cil["quaternion"] = q_novy

cur.execute("UPDATE product_assemblies SET data=%s WHERE id=%s",
            (json.dumps(data, ensure_ascii=False), ASSEMBLY_ID))
conn.commit()
print("HOTOVO - ulozeno.")
cur.close()
conn.close()
