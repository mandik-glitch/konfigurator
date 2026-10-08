"""SPUSTIT PRIMO NA SERVERU jako root (ne v sandboxu bota) - oprava 10
zrcadlovych/o 180 stupnu otocenych log v NASTUPNICKYCH sestavach 341-347
(K-075 rodina, produkt 3942, ZIVY e-shop - technicky_ok=1, is_public=1).

Puvodnich 7 "zamcenych" sestav (279, 332, 333, 334, 335, 336, 337), pro
ktere byl urcen puvodni scripts/2026-09-12_oprava_loga_zamcene_zapsat.py,
Robert 2026-09-12 odpoledne SMAZAL (duplicita v kategorii vedle novych
10/30mm nahrad) - tenhle skript je NAHRAZUJE, cili na ta puvodni ID uz
nespoustet (neexistuji).

Parovani puvodni->nastupce OVERENO PRIMO v AGENTS_LOG.md (bot8, radky
29061 a 29176, doslovna citace "sjednoceno se vsemi sourozenci teto
session: 332->342/333->344/334->341/335->343/336->345/279->346" + 337
dohledano stejnym zpusobem o par radku dal -> 347), NE prevzato z
odhadu - puvodni odhad (bot3, "341<->279 atd.") byl nespravny.

Nezavisle ZNOVU OVERENO na aktualnich datech (bot9, 2026-09-12): kazda
z 10 cilovych poloh ma presne stejnou "spatnou" (0.5,0.5,0.5,0.5)/
(-0.5,0.5,0.5,0.5)-rodinu kvaternionu jako jeji puvodni predek, presne
stejny pocet a stejne role u kazde sestavy - shoduje se s tim, ze jde o
geometricky odvozene kopie, ktere bug zdedily beze zmeny.

Pred zapisem skript sam znovu overi (na CERSTVE nactenych datech, ne na
zaloze), ze cilova role ma presne ocekavany "spatny" kvaternion - pokud
ne, tu polozku PRESKOCI a nahlasi. Zmena = PRESNE jedno pole
(`quaternion`) na kazde z 10 cilovych poloh - zadna jina geometrie/cena/
spoj se nemeni, skript si to sam dokaze plnym before/after diffem.

Zalohy puvodnich dat: backups/2026-09-12_asm<ID>_logo_nastupce_pred_opravou.json

Pouziti (na serveru, v /opt/konfigurator):
  api/venv/bin/python3 scripts/2026-09-12_oprava_loga_nastupci_zapsat.py
"""
import json
import sys

sys.path.insert(0, "/opt/konfigurator/scripts")
import pymysql
from pymysql.cursors import DictCursor
from _env import load_env

from razitkovac import _kvaternion_z_baze, _rotuj, _norm, _neg

CILE = {
    346: ["logo-ochrana-logo-5"],                                    # nastupce 279
    342: ["logo-ochrana-logo-3", "logo-ochrana-logo-5"],              # nastupce 332
    344: ["logo-ochrana-logo-4", "logo-ochrana-logo-6"],              # nastupce 333
    341: ["logo-ochrana-logo-6"],                                     # nastupce 334
    343: ["logo-ochrana-logo-4", "logo-ochrana-logo-6"],              # nastupce 335
    345: ["logo-ochrana-logo-6"],                                     # nastupce 336
    347: ["logo-ochrana-logo-7"],                                     # nastupce 337
}

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
                continue
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
