#!/opt/konfigurator/api/venv/bin/python
"""Oprava: doplnit chybejici position/quaternion/scale dilum car_body u sestav,
kde chybi (bot22, 2026-09-05). Bez nich insertCustomShape ve scene padne na
'partSpec.position is undefined' UVNITR loader.load callbacku (async, mimo
try/catch) -> Uncaught (in promise), vlozeni sestavy do sceny tise zamrzne.

Pre-existing bug (2 modely FO31/VW25, prestavba 2026-09-01) - NE souvisi s
uhelniky. Vsech 112 funkcnich sestav ma car_body v IDENTITE (pos [0,0,0],
quat [0,0,0,1], scale [1,1,1]) - GLB karoserie je uz v absolutnich
souradnicich. Doplni se tedy tytez hodnoty.

Bez --apply jen dry-run. S --apply zapisuje az po zaloze do backups/.
"""
import argparse, copy, json, os, sys
from datetime import date

def load_env():
    for line in open("/opt/konfigurator/api/.env"):
        line=line.strip()
        if line and not line.startswith("#") and "=" in line:
            k,v=line.split("=",1); os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--backup", default="/opt/konfigurator/backups/%s_carbody_position_backup.json" % date.today().isoformat())
    a=ap.parse_args()
    load_env(); sys.path.insert(0,"/opt/konfigurator/api"); os.chdir("/opt/konfigurator/api")
    import app as A
    conn=A.get_conn(); cur=conn.cursor()
    cur.execute("SELECT id,name,data FROM product_assemblies")
    backup={}; updates=[]; n_fix=0
    for r in cur.fetchall():
        d=json.loads(r["data"]) if isinstance(r["data"],(str,bytes)) else (r["data"] or {})
        parts=d.get("parts") or []
        fixed=0
        for p in parts:
            if (p.get("part_id") or "").startswith("car_body") and not p.get("position"):
                p["position"]=[0,0,0]; p["quaternion"]=[0,0,0,1]; p["scale"]=[1,1,1]; fixed+=1
        if fixed:
            backup[str(r["id"])]=None  # zaloha se udela z ORIGINALU nize
            updates.append((r["id"], r["name"], fixed, json.dumps(d, ensure_ascii=False, separators=(",",":"))))
            n_fix+=fixed
            print("id=%-4s %-40s doplneno position %d car_body" % (r["id"], str(r["name"])[:40], fixed))
    print("\ndoplneno %d car_body dilu v %d sestavach" % (n_fix, len(updates)))
    if not a.apply:
        print("(DRY-RUN - nic do DB)"); conn.close(); return
    if not updates: print("nic k oprave"); conn.close(); return
    # zaloha ORIGINALU (pred zapisem) - znovu nacti cerstve
    cur.execute("SELECT id,data FROM product_assemblies WHERE id IN (%s)" % ",".join(str(u[0]) for u in updates))
    for r in cur.fetchall():
        backup[str(r["id"])]=json.loads(r["data"]) if isinstance(r["data"],(str,bytes)) else r["data"]
    json.dump(backup, open(a.backup,"w"), ensure_ascii=False); print("zaloha -> %s" % a.backup)
    for aid,name,fx,dj in updates: cur.execute("UPDATE product_assemblies SET data=%s WHERE id=%s",(dj,aid))
    conn.commit(); conn.close()
    print("ZAPSANO: %d sestav" % len(updates))

if __name__=="__main__": main()
