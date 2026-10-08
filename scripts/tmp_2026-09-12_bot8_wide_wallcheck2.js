// Presnejsi mereni "je noha u prepazky?" nez hruba AABB Z-range kontrola
// (ta u K-019 dala DVE nohy v rozsahu, protoze B.glb neni tenka deska ale
// objemnejsi kus karoserie). Misto AABB pocitame REALNOU vzdalenost od
// stredu nohy (predni-svislice pozice) ke skutecnemu povrchu B.glb meshe
// pomoci raycastingu (stejny pristup jako collidesWithWallsReal ve
// verify skriptech, jen misto binarni kolize vraci vzdalenost).
const fs = require("fs");
const THREE = require("three");
const { parseGlbMesh } = require("./2026-08-19_glb_real_geometry.js");
const MeshBVHLib = require("../webapp/js/three-mesh-bvh.js");
THREE.BufferGeometry.prototype.computeBoundsTree = MeshBVHLib.computeBoundsTree;
THREE.Mesh.prototype.raycast = MeshBVHLib.acceleratedRaycast;
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
fs.writeFileSync("/tmp/_dump_repr3.py", dumpPy);
const raw = execSync("api/venv/bin/python3 /tmp/_dump_repr3.py", { cwd: "/opt/konfigurator", maxBuffer: 1024 * 1024 * 80 }).toString();
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

function loadWallMesh(base) {
  const m = parseGlbMesh(KAT + "car_bodies/" + base + "_B.glb");
  m.material = new THREE.MeshBasicMaterial({ side: THREE.DoubleSide });
  m.updateMatrixWorld(true);
  m.geometry.computeBoundsTree();
  return m;
}

const raycaster = new THREE.Raycaster();
raycaster.far = 3000;
function distToWallSurface(wallMesh, origin, dir) {
  raycaster.set(origin, dir);
  raycaster.far = 3000;
  const hits = raycaster.intersectObject(wallMesh, false);
  return hits.length ? hits[0].distance : null;
}

for (const id of Object.keys(models)) {
  const base = models[id];
  const wall = loadWallMesh(base);
  console.log("====", id, DB[id].name);
  const legParts = DB[id].parts.filter(p => p.role === 'predni-svislice');
  const legZs = [...new Set(legParts.map(p => p.position[2]))].sort((a, b) => a - b);
  for (const z of legZs) {
    const p = legParts.find(pp => pp.position[2] === z);
    const origin = new THREE.Vector3(p.position[0], p.position[1], p.position[2]);
    const dNeg = distToWallSurface(wall, origin, new THREE.Vector3(0, 0, -1));
    const dPos = distToWallSurface(wall, origin, new THREE.Vector3(0, 0, 1));
    console.log(`   leg Z=${z.toFixed(2)} X=${p.position[0].toFixed(1)} Y=${p.position[1].toFixed(1)}  ray(-Z)hit=${dNeg==null?'null':dNeg.toFixed(2)}  ray(+Z)hit=${dPos==null?'null':dPos.toFixed(2)}`);
  }
}
