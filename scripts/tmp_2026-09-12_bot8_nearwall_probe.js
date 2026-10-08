// Zjisti, ktera noha (index) je SKUTECNE nejbliz car_body_B.glb (bulkhead)
// - ne jen bounding-box Z rozsah (ten je u nekterych karoserii siroky a
// zavadejici, viz K-020/Caddy), ale mesh-presna vzdalenost profilu nohy
// k B stene, mereno na "predni-svislice" dilu kazde nohy.
const fs = require("fs");
const THREE = require("three");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const KAT = "/opt/konfigurator/webapp/katalog/";

function nearestDistToMesh(partMesh, wallMesh, samples) {
  // vzorkuj body na povrchu partMesh (world), pro kazdy najdi nejblizsi vertex wallMesh (hruba aproximace, staci na porovnani "ktera noha je blizc")
  const geo = partMesh.geometry, pos = geo.attributes.position;
  const wgeo = wallMesh.geometry, wpos = wgeo.attributes.position;
  let minD = Infinity;
  const step = Math.max(1, Math.floor(pos.count / samples));
  const v = new THREE.Vector3(), wv = new THREE.Vector3();
  // pro rychlost: predpocitej world-space wall vertices jednou (volajici muze cachovat), tady jen naivne
  const wpts = [];
  const wstep = Math.max(1, Math.floor(wpos.count / 3000));
  for (let i = 0; i < wpos.count; i += wstep) {
    wv.fromBufferAttribute(wpos, i).applyMatrix4(wallMesh.matrixWorld);
    wpts.push(wv.clone());
  }
  for (let i = 0; i < pos.count; i += step) {
    v.fromBufferAttribute(pos, i).applyMatrix4(partMesh.matrixWorld);
    for (const wp of wpts) {
      const d = v.distanceTo(wp);
      if (d < minD) minD = d;
    }
  }
  return minD;
}

const CASES = [
  { code: "K-020", base: "car_bodies/Volkswagen_Caddy_VW32_2021-", legZ: [-1874.9876823425293, -1414.9876823425293, -954.9876823425293, -220.9876823425293], legX: 15 /* T/2 approx local X, corrected below via real data */ },
];

const env = {};
require("fs").readFileSync("/opt/konfigurator/api/.env","utf8").split("\n").forEach(l=>{l=l.trim(); if(!l||l.startsWith("#")||!l.includes("=")) return; const [k,...r]=l.split("="); env[k.trim()]=r.join("=").trim();});

const { execSync } = require("child_process");
const dumpPy = `
import json, pymysql
env = ${JSON.stringify(env)}
conn = pymysql.connect(host=env["DB_HOST"], port=int(env.get("DB_PORT",3306)), user=env["DB_USER"], password=env["DB_PASSWORD"], database=env["DB_NAME"], cursorclass=pymysql.cursors.DictCursor)
cur = conn.cursor()
cur.execute("SELECT data FROM product_assemblies WHERE id=198")
d = json.loads(cur.fetchone()["data"])
parts = [p for p in d["parts"] if p.get("role")=="predni-svislice"]
print(json.dumps(parts))
`;
fs.writeFileSync("/tmp/_k020_legs.py", dumpPy);
const raw = execSync("api/venv/bin/python3 /tmp/_k020_legs.py").toString();
const legParts = JSON.parse(raw);
console.log("predni-svislice parts (K-020, id=198):", legParts.length);
legParts.sort((a,b)=>a.position[2]-b.position[2]);

const B = parseGlbMesh(KAT + "car_bodies/Volkswagen_Caddy_VW32_2021-_B.glb");
B.updateMatrixWorld(true);
const OBJ7 = KAT + "Object_7.glb";

legParts.forEach((p, i) => {
  const m = parseGlbMesh(OBJ7);
  m.position.set(...p.position); m.quaternion.set(...p.quaternion); m.scale.set(...p.scale);
  m.updateMatrixWorld(true);
  const d = nearestDistToMesh(m, B, 60);
  console.log(`leg idx=${i} Z=${p.position[2].toFixed(1)} nearest-dist-to-B=${d.toFixed(2)}mm`);
});
