#!/opt/konfigurator/api/venv/bin/python
"""Zapise do DB uhelniky na nohy sestav (bot22, 2026-09-05).

Vstup: navrh z scripts/2026-09-05_add_uhelniky_all_legs.js --out (per id: add[]).
Kazdy uhelnik uz PROSEL geometrickym overenim (flush 0.0mm, 0 kolizi) -
tenhle skript uz nic nepocita, jen zapisuje. Cerstva data cte z DB.

IDEMPOTENTNI: uhelnik se prida jen kdyz na dane Z-pozici nohy jeste zadny
uhelnik (role zacina 'uhelnik') NENI. Bez --apply jen dry-run. S --apply
zapisuje az po ulozeni zalohy PUVODNICH dat do backups/.
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
    ap.add_argument("navrh")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--backup", default="/opt/konfigurator/backups/%s_uhelniky_backup.json" % date.today().isoformat())
    a=ap.parse_args()
    navrh=json.load(open(a.navrh))
    load_env(); sys.path.insert(0,"/opt/konfigurator/api"); os.chdir("/opt/konfigurator/api")
    import app as A
    conn=A.get_conn(); cur=conn.cursor()
    ids=sorted(int(k) for k in navrh)
    cur.execute("SELECT id,name,data FROM product_assemblies WHERE id IN (%s)" % ",".join(map(str,ids)))
    rows={r["id"]:r for r in cur.fetchall()}
    backup={}; updates=[]; n_add=n_skip=0
    for aid in ids:
        r=rows.get(aid)
        if not r: print("id=%s nenalezeno" % aid); continue
        data=json.loads(r["data"]) if isinstance(r["data"],(str,bytes)) else (r["data"] or {})
        parts=data.get("parts") or []
        backup[str(aid)]=copy.deepcopy(data)
        exist_z=[round(p["position"][2]) for p in parts if p.get("position") and (p.get("role") or "").startswith("uhelnik")]
        added=0
        for u in navrh[str(aid)]["add"]:
            z=round(u["position"][2])
            if any(abs(ez-z)<=60 for ez in exist_z): n_skip+=1; continue
            parts.append(u); added+=1; n_add+=1
        if added:
            data["parts"]=parts
            updates.append((aid, json.dumps(data, ensure_ascii=False, separators=(",",":"))))
            print("id=%-4s %-44s +%d uhelniku" % (aid, str(r["name"])[:44], added))
    print("\npridano %d uhelniku, preskoceno %d, dotcenych sestav %d" % (n_add, n_skip, len(updates)))
    if not a.apply:
        print("(DRY-RUN - nic do DB)"); conn.close(); return
    if not updates: print("nic k zapsani"); conn.close(); return
    json.dump(backup, open(a.backup,"w"), ensure_ascii=False)
    print("zaloha -> %s" % a.backup)
    for aid,dj in updates: cur.execute("UPDATE product_assemblies SET data=%s WHERE id=%s",(dj,aid))
    conn.commit(); conn.close()
    print("ZAPSANO do DB: %d sestav" % len(updates))

if __name__=="__main__": main()
