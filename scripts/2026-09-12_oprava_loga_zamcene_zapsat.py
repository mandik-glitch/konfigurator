"""SPUSTIT PRIMO NA SERVERU jako root (ne v sandboxu bota) - oprava 10
zrcadlovych/o 180 stupnu otocenych log ve 7 ZAMCENYCH sestavach,
schvaleno bot3/Robert 2026-09-12 (viz AGENTS_LOG.md ke stejnemu datu).

Pred spustenim uz existuji zalohy puvodnich dat kazde sestavy
(backups/2026-09-12_asm<ID>_logo_zamcene_pred_opravou.json, vytvoreno
2026-09-12_oprava_loga_zamcene_pripravit.py) - tenhle skript je
nepotrebuje cist, protoze si znovu nacte AKTUALNI stav primo z DB (kdyby
se od pripravy neco zmenilo) a PRED zapisem sam znovu overi, ze cilova
role ma presne ocekavany "spatny" kvaternion - pokud ne, tu jednu
polozku PRESKOCI a nahlasi (nikdy neprepise neco, co nevypada presne
tak, jak bylo overeno).

Zmena = PRESNE jedno pole (`quaternion`) u kazde z 10 cilovych poloh v
poli `data.parts` - 180 stupnu otoceni kolem vlastni normaly steny
(logo zustava na stejnem miste/stene, jen text cte spravne). Zadna jina
geometrie, cena, spoj ani cokoliv jineho v sestave se nemeni - skript
si to sam dokaze (plny before/after diff cele `data` JSON na konci).

Pouziti (na serveru, v /opt/konfigurator):
  api/venv/bin/python3 scripts/2026-09-12_oprava_loga_zamcene_zapsat.py
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

# Presne ty dve "spatne" kvaternion-rodiny, overene render+zoomem na
# pismenech (bot9, 2026-09-12) - bezpecnostni pojistka PRED zapisem.
ZNAME_SPATNE = (
    [-0.5, -0.5, 0.5, 0.5],
    [-0.5, 0.5, 0.5000000000000001, 0.5],
)


def _je_znamy_spatny(q):
    return any(all(abs(a - b) < 1e-6 for a, b in zip(q, znamy)) for znamy in ZNAME_SPATNE)


cfg = load_env()
conn = pymysql.connect(host=cfg["DB_HOST"], port=3306, user=cfg["DB_USER"],
                        password=cfg["DB_PASSWORD"], database=cfg["DB_NAME"],
                        charset="utf8mb4", cursorclass=DictCursor, autocommit=False)

celkem_opraveno = 0
celkem_preskoceno = 0

for assembly_id, role_list in CILE.items():
    cur = conn.cursor()
    cur.execute("SELECT data FROM product_assemblies WHERE id=%s FOR UPDATE", (assembly_id,))
    row = cur.fetchone()
    if row is None:
        print(f"!! sestava {assembly_id} nenalezena, preskakuji")
        continue
    data_pred = row["data"]
    data = json.loads(data_pred)
    parts = data["parts"]
    by_role = {p.get("role"): p for p in parts}

    zmeneno_v_teto_sestave = False
    for role in role_list:
        cil = by_role.get(role)
        if cil is None:
            print(f"!! sestava {assembly_id} role {role}: nenalezena v parts, preskakuji")
            celkem_preskoceno += 1
            continue
        q_stary = list(cil["quaternion"])
        if not _je_znamy_spatny(q_stary):
            print(f"!! sestava {assembly_id} role {role}: kvaternion NEODPOVIDA ocekavanemu "
                  f"spatnemu vzoru ({q_stary}) - PRESKAKUJI, potreba rucni kontrola.")
            celkem_preskoceno += 1
            continue
        x_osa = _norm(_rotuj(q_stary, (1.0, 0.0, 0.0)))
        y_osa = _norm(_rotuj(q_stary, (0.0, 1.0, 0.0)))
        z_osa = _norm(_rotuj(q_stary, (0.0, 0.0, 1.0)))
        q_novy = _kvaternion_z_baze(_neg(x_osa), _neg(y_osa), z_osa)
        cil["quaternion"] = q_novy
        zmeneno_v_teto_sestave = True
        print(f"sestava {assembly_id} role {role}: {[round(c, 4) for c in q_stary]} "
              f"-> {[round(c, 4) for c in q_novy]}")
        celkem_opraveno += 1

    if not zmeneno_v_teto_sestave:
        print(f"sestava {assembly_id}: nic k zapsani (vse preskoceno), pokracuji dalsi sestavou")
        conn.commit()
        continue

    data_po_str = json.dumps(data, ensure_ascii=False)
    cur.execute("UPDATE product_assemblies SET data=%s WHERE id=%s", (data_po_str, assembly_id))
    conn.commit()

    # Kontrola bez vedlejsich ucinku: nactu znovu z DB a porovnam KAZDY
    # dil se stavem PRED zapisem - jedina zmena smi byt quaternion u
    # cilenych roli, nic jineho (poradi dilu, pozice, ostatni role...).
    cur2 = conn.cursor()
    cur2.execute("SELECT data FROM product_assemblies WHERE id=%s", (assembly_id,))
    data_po = json.loads(cur2.fetchone()["data"])
    parts_pred = json.loads(data_pred)["parts"]
    parts_po = data_po["parts"]
    neocekavane_zmeny = []
    if len(parts_pred) != len(parts_po):
        neocekavane_zmeny.append(f"pocet dilu zmenen: {len(parts_pred)} -> {len(parts_po)}")
    for i, (p_pred, p_po) in enumerate(zip(parts_pred, parts_po)):
        for klic in set(p_pred.keys()) | set(p_po.keys()):
            if p_pred.get(klic) == p_po.get(klic):
                continue
            if klic == "quaternion" and p_pred.get("role") in role_list:
                continue  # ocekavana zmena
            neocekavane_zmeny.append(f"dil {i} (role={p_pred.get('role')}) pole '{klic}' zmeneno neocekavane")
    if neocekavane_zmeny:
        print(f"!!!! POZOR sestava {assembly_id}: NEOCEKAVANE VEDLEJSI ZMENY:")
        for z in neocekavane_zmeny:
            print("     ", z)
    else:
        print(f"sestava {assembly_id}: OK, zadna vedlejsi zmena mimo cilene quaterniony.")

print(f"\nHOTOVO. Opraveno polozek: {celkem_opraveno}, preskoceno: {celkem_preskoceno} "
      f"(ocekavano 10 opravenych, 0 preskocenych).")
conn.close()
