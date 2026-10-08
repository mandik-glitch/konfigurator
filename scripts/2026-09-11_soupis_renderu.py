#!/usr/bin/env python3
"""Soupis sad snimku v private-files/blender-renders/ - CO TAM LEZI A CI TO JE.

Robert 2026-09-11: *„rendery originalnich schvalených orazitkovaných sestav
nech se ukládají na sdílený disk, nikoli testovací rendery .. ty se mažou."*
Nez se cokoli smaze, musi byt jasne, co se maze - tenhle skript to zjistuje.
NIC NEMAZE ani nezapisuje.

=== JAK SE POZNA, CI SADA JE ===
Vetsina sad jsou SIROTCI: zustal jen adresar `<job>.frames` a jeho
`manifest.json`, konfigurace ulohy (`<job>.json`) i stav (`<job>.status.json`)
jsou pryc. V manifestu neni id sestavy - ALE je tam `camera.box_min` a
`box_max`, tedy obalka toho, co se renderovalo. Sestava se proto dohleda
POROVNANIM te obalky se skutecnou geometrii sestav v DB (tolerance 1 mm).
Je to mereni, ne odhad; kdyz se shoda nenajde, napise se to a nehada se.

=== PODMINKY ARCHIVACE (Robert, pres bot3 2026-09-11) ===
Na Sdileny disk smi jen sada, u ktere plati VSECHNO SOUCASNE:
  1. sestava je schvalena (`technicky_ok`)
  2. razitka jsou `aktualni` (razitkovac.stav_razitek, ne vlastni predikat)
  3. je to KOMPLETNI prijata davka, ne jednotlive snimky
Cokoli jineho je testovaci render.
"""
import json
import os
import sys

REPO = "/opt/konfigurator"
RENDERS = os.path.join(REPO, "private-files", "blender-renders")
sys.path.insert(0, os.path.join(REPO, "scripts"))
sys.path.insert(0, os.path.join(REPO, "api"))

import _env  # noqa: E402

os.environ.update(_env.load_env())
import pymysql  # noqa: E402
import razitkovac  # noqa: E402

TOL_MM = 1.0


def _obalky_sestav():
    """id sestavy -> (box_min, box_max) ze SKUTECNE GLB geometrie."""
    import subprocess
    kod = r'''
const fs=require("fs");
const R=require("/opt/konfigurator/scripts/2026-09-11_glb_resolver.js");
const {parseGlbMesh}=require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const M=require("/opt/konfigurator/scripts/2026-09-11_mesh_kolize_lib.js");
const vse=JSON.parse(fs.readFileSync(process.argv[2],"utf8"));
const out={};
for(const row of vse){
  const d=typeof row.data==="string"?JSON.parse(row.data):row.data;
  const parts=((d&&d.parts)||[]).filter(p=>p.position);
  let mi=[Infinity,Infinity,Infinity], ma=[-Infinity,-Infinity,-Infinity], n=0;
  for(const p of parts){
    if(R.jeKaroserie(p.part_id)) continue;      // kulisa, nerenderuje se
    const f=R.glbPath(p.part_id); if(!f) continue;
    const g=M.dilVeSvete(f,p,parseGlbMesh); n++;
    for(let a=0;a<3;a++){ if(g.box.min[a]<mi[a])mi[a]=g.box.min[a];
                          if(g.box.max[a]>ma[a])ma[a]=g.box.max[a]; }
  }
  if(n) out[row.id]={min:mi,max:ma,dilu:n};
}
fs.writeFileSync(process.argv[3], JSON.stringify(out));
'''
    import tempfile
    env = _env.load_env()
    c = pymysql.connect(host=env["DB_HOST"], port=int(env["DB_PORT"]), user=env["DB_USER"],
                        password=env["DB_PASSWORD"], database=env["DB_NAME"],
                        cursorclass=pymysql.cursors.DictCursor)
    with c.cursor() as cur:
        cur.execute("SELECT id, name, data, technicky_ok FROM product_assemblies")
        rows = cur.fetchall()
    c.close()
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump([{"id": r["id"], "data": r["data"] if isinstance(r["data"], str) else json.dumps(r["data"])}
                   for r in rows], f)
        vstup = f.name
    vystup = vstup + ".out"
    skript = vstup + ".cjs"
    with open(skript, "w", encoding="utf-8") as f:
        f.write(kod)
    p = subprocess.run(["node", skript, vstup, vystup], capture_output=True, text=True, cwd=REPO)
    if p.returncode != 0:
        raise SystemExit("Nepodarilo se spocitat obalky sestav:\n" + p.stderr[-1500:])
    with open(vystup, encoding="utf-8") as f:
        obalky = json.load(f)
    for c2 in (vstup, vystup, skript):
        if os.path.exists(c2):
            os.unlink(c2)
    return obalky, {r["id"]: r for r in rows}


def main():
    obalky, sestavy = _obalky_sestav()
    stav_raz = {}
    for i, r in sestavy.items():
        d = json.loads(r["data"]) if isinstance(r["data"], str) else r["data"]
        stav_raz[i] = razitkovac.stav_razitek(d)

    sady = sorted(d for d in os.listdir(RENDERS) if d.endswith(".frames"))
    print(f"sad v {RENDERS}: {len(sady)}\n")
    radky = []
    for sada in sady:
        cesta = os.path.join(RENDERS, sada)
        job = sada[: -len(".frames")]
        soubory = os.listdir(cesta)
        masteru = len([f for f in soubory if f.endswith("_t2048.jpg")])
        odvoz = len([f for f in soubory if f.endswith("_t1024.jpg")])
        stills = len([f for f in soubory if f.startswith("still_")])
        velikost = sum(os.path.getsize(os.path.join(cesta, f)) for f in soubory)

        # ci to je - napred ze stavu ulohy, kdyz zbyl; jinak podle obalky
        asm, jak = None, "-"
        st_path = os.path.join(RENDERS, job + ".status.json")
        if os.path.exists(st_path):
            try:
                asm = (json.load(open(st_path, encoding="utf-8")) or {}).get("assembly_id")
                jak = "stav úlohy"
            except (ValueError, OSError):
                pass
        if asm is None:
            man = os.path.join(cesta, "manifest.json")
            if os.path.exists(man):
                try:
                    cam = (json.load(open(man, encoding="utf-8")) or {}).get("camera") or {}
                    bmin, bmax = cam.get("box_min"), cam.get("box_max")
                    if bmin and bmax:
                        # Presna shoda; kdyz neni, vypise se NEJBLIZSI sestava
                        # i s odchylkou. Sestavy se od tech renderu menily
                        # (dnes se z nich mazaly horni bloky), takze "nesedi"
                        # samo o sobe neni odpoved - odchylka rekne, jestli
                        # jde o tutez sestavu v jine podobe, nebo o jinou.
                        nej = None
                        for sid, o in obalky.items():
                            odch = max(max(abs(o["min"][a] - bmin[a]),
                                           abs(o["max"][a] - bmax[a])) for a in range(3))
                            if nej is None or odch < nej[1]:
                                nej = (int(sid), odch)
                        if nej and nej[1] <= TOL_MM:
                            asm, jak = nej[0], "obálka kamery (přesně)"
                        elif nej:
                            asm, jak = nej[0], "nejbližší obálka, odchylka %.0f mm" % nej[1]
                            if nej[1] > 500:
                                asm, jak = None, "žádná blízká sestava (nejblíž #%d, %.0f mm)" % nej
                except (ValueError, OSError):
                    jak = "manifest nečitelný"
            else:
                jak = "bez manifestu"

        s = sestavy.get(asm) if asm else None
        radky.append({
            "job": job, "masteru": masteru, "odvozenin": odvoz, "stills": stills,
            "kB": round(velikost / 1024), "assembly_id": asm, "jak": jak,
            "presne": jak.startswith("stav") or "přesně" in jak,
            "nazev": (s["name"] if s else None),
            "technicky_ok": bool(s["technicky_ok"]) if s else None,
            "razitka": stav_raz.get(asm) if asm else None,
        })

    print(f"{'úloha':<34}{'mast':>5}{'1024':>5}{'stil':>5}{'kB':>7}  sestava / jak dohledána")
    for r in radky:
        kdo = f"#{r['assembly_id']} {(r['nazev'] or '')[:34]}" if r["assembly_id"] else r["jak"]
        print(f"{r['job']:<34}{r['masteru']:>5}{r['odvozenin']:>5}{r['stills']:>5}{r['kB']:>7}  {kdo}")

    UPLNA = 81
    hotove = [r for r in radky if r["masteru"] >= UPLNA]
    kandidati = [r for r in hotove if r["technicky_ok"] and r["razitka"] == "aktualni"]
    print("\n" + "=" * 78)
    print(f"masterů celkem na disku: {sum(r['masteru'] for r in radky)}"
          f"  (úplná dávka = {UPLNA} masterů)")
    print(f"sad s ÚPLNOU dávkou:     {len(hotove)}")
    print(f"z toho schválených a s aktuálními razítky (ARCHIVOVAT): {len(kandidati)}")
    dohledano = len([r for r in radky if r["assembly_id"]])
    print(f"sad dohledaných k sestavě: {dohledano} z {len(radky)}")
    print(f"velikost všech sad: {round(sum(r['kB'] for r in radky) / 1024, 1)} MB")
    if kandidati:
        print("\nK ARCHIVACI (NEMAZAT):")
        for r in kandidati:
            print(f"  {r['job']}  #{r['assembly_id']} {r['nazev']}")
    else:
        print("\nŽádná sada nesplňuje podmínky archivace -> podle Robertova pravidla")
        print("jsou to všechno testovací rendery.")
    ven = os.path.join(REPO, "backups", "2026-09-11_soupis_renderu.json")
    os.makedirs(os.path.dirname(ven), exist_ok=True)
    with open(ven, "w", encoding="utf-8") as f:
        json.dump({"radky": radky, "uplna_davka_masteru": UPLNA}, f, ensure_ascii=False, indent=1)
        f.flush()
        os.fsync(f.fileno())
    print(f"\nsoupis -> {ven}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
