const { execSync } = require("child_process");
const fs = require("fs");
const R = require("/opt/konfigurator/scripts/2026-09-11_glb_resolver.js");

const dumpPy = `
import json, pymysql
env = {}
with open("/opt/konfigurator/api/.env") as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line: continue
        k, v = line.split("=", 1); env[k.strip()] = v.strip()
conn = pymysql.connect(host=env["DB_HOST"], port=int(env.get("DB_PORT",3306)), user=env["DB_USER"], password=env["DB_PASSWORD"], database=env["DB_NAME"], cursorclass=pymysql.cursors.DictCursor)
cur = conn.cursor()
ids = [101,139,140,161,162,74,149,150,171,136,157,158,179,127,198,268,66,235,305,71,238,308,181,217,287,97,229,299,128,213,283,110,201,271,113,206,276,120,253,323,81,226,296]
cur.execute("SELECT data FROM product_assemblies WHERE id IN (%s)" % ",".join(map(str,ids)))
pids = set()
for r in cur.fetchall():
    d = json.loads(r["data"])
    for p in d["parts"]:
        pids.add(p["part_id"])
conn.close()
print(json.dumps(sorted(pids)))
`;
fs.writeFileSync("/tmp/_partids.py", dumpPy);
const raw = execSync("api/venv/bin/python3 /tmp/_partids.py", { cwd: "/opt/konfigurator" }).toString();
const pids = JSON.parse(raw);
console.log("Distinct part_id count:", pids.length);
let missing = 0;
for (const pid of pids) {
  if (R.jeKaroserie(pid)) { console.log("KAROSERIE (nemelo by tu byt!):", pid); continue; }
  const gp = R.glbPath(pid);
  if (!gp) { console.log("CHYBI GLB MAPOVANI:", pid); missing++; }
}
console.log(missing === 0 ? "VSECHNY part_id maji GLB mapovani." : `${missing} part_id BEZ mapovani!`);
