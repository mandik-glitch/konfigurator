const fs = require("fs");
const { execSync } = require("child_process");
const LIB = require("/opt/konfigurator/scripts/tmp_2026-09-12_bot8_generic_kolizni_rezerva_lib.js");

const dumpPy = `
import json, pymysql
env = {}
with open("api/.env") as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line: continue
        k, v = line.split("=", 1); env[k.strip()] = v.strip()
conn = pymysql.connect(host=env["DB_HOST"], port=int(env.get("DB_PORT",3306)), user=env["DB_USER"], password=env["DB_PASSWORD"], database=env["DB_NAME"], cursorclass=pymysql.cursors.DictCursor)
cur = conn.cursor()
cur.execute("SELECT id, data FROM product_assemblies WHERE id IN (184,348)")
out = {}
for r in cur.fetchall():
    out[r["id"]] = json.loads(r["data"])["parts"]
conn.close()
print(json.dumps(out))
`;
fs.writeFileSync("/tmp/_dump_184_348.py", dumpPy);
const raw = execSync("api/venv/bin/python3 /tmp/_dump_184_348.py", { cwd: "/opt/konfigurator", maxBuffer: 1024*1024*80 }).toString();
const DB = JSON.parse(raw);
const before = DB[184], after = DB[348];

const T = 30, DELTA_Z = 8, DELTA_Y = 10;
const topo = LIB.detectTopology(before, T);
console.log("Topologie (184):", JSON.stringify(topo.legs.map(l=>({idx:l.idx,z:l.z.toFixed(2),type:l.type,oldYnew:l.oldYnew,isNearWall:l.isNearWall}))));
console.log("Sloupce:", JSON.stringify(topo.columns));

const { parts: mine, log } = LIB.transformAssembly(before, topo, DELTA_Z, DELTA_Y, T);
console.log("Transform log:", JSON.stringify(log));

// compare mine vs after (348) - match by (role, part_id, X) sorted, since indexy se muzou lisit
function key(p){ return (p.role||"")+"|"+p.part_id+"|"+p.position[0].toFixed(1); }
function byKey(parts){ const m={}; for(const p of parts){ const k=key(p); (m[k]=m[k]||[]).push(p);} for(const k in m) m[k].sort((a,b)=>a.position[2]-b.position[2]); return m; }
const mMine = byKey(mine), mRef = byKey(after);
let mismatches=0, checked=0;
const allKeys = new Set([...Object.keys(mMine), ...Object.keys(mRef)]);
for (const k of allKeys) {
  const a = mMine[k]||[], b = mRef[k]||[];
  if (a.length !== b.length) { console.log("COUNT MISMATCH", k, a.length, b.length); mismatches++; continue; }
  for (let i=0;i<a.length;i++) {
    checked++;
    const dp = a[i].position.map((v,idx)=>Math.abs(v-b[i].position[idx]));
    const ds = a[i].scale.map((v,idx)=>Math.abs(v-b[i].scale[idx]));
    if (dp.some(v=>v>0.02) || ds.some(v=>v>0.0002)) {
      console.log("MISMATCH", k, "#"+i, "mine=",a[i].position,a[i].scale,"ref=",b[i].position,b[i].scale);
      mismatches++;
    }
  }
}
console.log(`checked=${checked} mismatches=${mismatches}`);
console.log(mismatches===0 ? "SELF-CHECK OK" : "SELF-CHECK FAILED");
