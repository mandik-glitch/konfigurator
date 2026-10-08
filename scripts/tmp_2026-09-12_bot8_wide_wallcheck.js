// Krok 1 (task step 3): empiricky urcit, ktera noha kazdeho z 13 modelu je
// "u prepazky" (nejblizsi realny Z-rozsah car_body_B.glb) - deltaZ dostava
// JEN tahle noha. Nehadat z textu procedury, merit primo na GLB geometrii.
const fs = require("fs");
const THREE = require("three");
const { parseGlbMesh } = require("./2026-08-19_glb_real_geometry.js");
const { execSync } = require("child_process");

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
ids = [126,118,94,125,72,76,185,188,104,114,109,119,82]
cur.execute("SELECT id, name, data FROM product_assemblies WHERE id IN (%s)" % ",".join(map(str,ids)))
out = {}
for r in cur.fetchall():
    d = json.loads(r["data"])
    out[r["id"]] = {"name": r["name"], "parts": d["parts"]}
conn.close()
print(json.dumps(out))
`;
fs.writeFileSync("/tmp/_dump_repr2.py", dumpPy);
const raw = execSync("api/venv/bin/python3 /tmp/_dump_repr2.py", { cwd: "/opt/konfigurator", maxBuffer: 1024 * 1024 * 80 }).toString();
const DB = JSON.parse(raw);

const KAT = "/opt/konfigurator/webapp/katalog/";
const models = {
  126: "Volkswagen_Caddy_VW31_2021-",
  118: "Volkswagen_Transporter_VW25_2024-",
  94:  "Citroën_Berlingo_CI17_2019-",
  125: "Volkswagen_Caddy_VW22_2021-",
  72:  "Peugeot_Expert_PE20_2016-",
  76:  "Peugeot_Expert_PE27_2021-",
  185: "Citroën_Jumpy_CI19_2016-",
  188: "Citroën_Jumpy_CI26_2021-",
  104: "Renault_Trafic_RE29_2026-",
  114: "Ford_Custom_FO47_2023-",
  109: "Ford_Custom_FO28_2012-2023",
  119: "Volkswagen_Transporter_VW27_2024-",
  82:  "Mercedes_Vito_MB46_2014-",
};

for (const id of Object.keys(models)) {
  const base = models[id];
  const bPath = KAT + "car_bodies/" + base + "_B.glb";
  const m = parseGlbMesh(bPath);
  m.updateMatrixWorld(true);
  const box = new THREE.Box3().setFromObject(m);
  console.log("====", id, DB[id].name);
  console.log("  B.glb Z range:", box.min.z.toFixed(2), box.max.z.toFixed(2));
  const legZs = [...new Set(DB[id].parts.filter(p => p.role === 'predni-svislice').map(p => p.position[2]))].sort((a, b) => a - b);
  for (const z of legZs) {
    const dist = (z < box.min.z) ? (box.min.z - z) : (z > box.max.z ? (z - box.max.z) : 0);
    console.log("   leg Z=", z.toFixed(2), " distToWall=", dist.toFixed(2));
  }
}
