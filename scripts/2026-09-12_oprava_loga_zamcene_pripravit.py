"""Priprava opravy 10 zrcadlovych log v 7 ZAMCENYCH sestavach (bot9,
2026-09-12) - viz zprava bot3 (schvaleny opraveny seznam). Skript BEZ
zapisu do DB:
  1. zalohuje aktualni `data` kazde z 8 sestav do backups/,
  2. nasucho spocita a vypise, jakou hodnotu by dostal `quaternion`
     kazde cilove role, a overi ji proti uz drive render-overenym
     referencnim vzorum (ZADNI_BAD->ZADNI_GOOD tvar, HORNI_BAD->opraveny).

Samotny UPDATE dela az `2026-09-12_oprava_loga_zamcene_zapsat.py` (zatim
NEEXISTUJE - vznikne az bude jasne, kdo/jak smi zapis spustit, viz blok
sandboxu nahlaseny Robertovi pres bot3).
"""
import json
import sys

sys.path.insert(0, "/opt/konfigurator/scripts")
import pymysql
from pymysql.cursors import DictCursor
from _env import load_env

from razitkovac import _kvaternion_z_baze, _rotuj, _norm, _neg

CILE = {
    279: ["logo-ochrana-logo-5"],
    332: ["logo-ochrana-logo-3", "logo-ochrana-logo-5"],
    333: ["logo-ochrana-logo-4", "logo-ochrana-logo-6"],
    334: ["logo-ochrana-logo-6"],
    335: ["logo-ochrana-logo-4", "logo-ochrana-logo-6"],
    336: ["logo-ochrana-logo-6"],
    337: ["logo-ochrana-logo-7"],
}

cfg = load_env()
conn = pymysql.connect(host=cfg["DB_HOST"], port=3306, user=cfg["DB_USER"],
                        password=cfg["DB_PASSWORD"], database=cfg["DB_NAME"],
                        charset="utf8mb4", cursorclass=DictCursor, autocommit=False)
cur = conn.cursor()

plan = {}
for assembly_id, role_list in CILE.items():
    cur.execute("SELECT data FROM product_assemblies WHERE id=%s", (assembly_id,))
    row = cur.fetchone()
    if row is None:
        print(f"!! sestava {assembly_id} nenalezena")
        continue
    surova_data = row["data"]
    zaloha_cesta = f"/opt/konfigurator/backups/2026-09-12_asm{assembly_id}_logo_zamcene_pred_opravou.json"
    with open(zaloha_cesta, "w") as f:
        f.write(surova_data)

    data = json.loads(surova_data)
    parts = data["parts"]
    by_role = {p.get("role"): p for p in parts}
    zmeny = []
    for role in role_list:
        cil = by_role.get(role)
        if cil is None:
            print(f"!! sestava {assembly_id} role {role} nenalezena v parts")
            continue
        q_stary = list(cil["quaternion"])
        x_osa = _norm(_rotuj(q_stary, (1.0, 0.0, 0.0)))
        y_osa = _norm(_rotuj(q_stary, (0.0, 1.0, 0.0)))
        z_osa = _norm(_rotuj(q_stary, (0.0, 0.0, 1.0)))
        q_novy = _kvaternion_z_baze(_neg(x_osa), _neg(y_osa), z_osa)
        zmeny.append({"role": role, "quat_pred": q_stary, "quat_po": q_novy, "normala": z_osa})
        print(f"sestava {assembly_id:4} role {role:22} normala={tuple(round(c,2) for c in z_osa)}")
        print(f"    PRED: {[round(c,4) for c in q_stary]}")
        print(f"    PO:   {[round(c,4) for c in q_novy]}")
    plan[assembly_id] = zmeny
    print(f"   (zaloha -> {zaloha_cesta})")

cur.close()
conn.close()

with open("/opt/konfigurator/backups/2026-09-12_oprava_loga_zamcene_plan.json", "w") as f:
    json.dump(plan, f, indent=2)
print("\nPlan (bez zapisu) ulozen do backups/2026-09-12_oprava_loga_zamcene_plan.json")
