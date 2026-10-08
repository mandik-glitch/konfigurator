const fs = require("fs");
const THREE = require("three");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const MeshBVHLib = require("/opt/konfigurator/webapp/js/three-mesh-bvh.js");
THREE.BufferGeometry.prototype.computeBoundsTree = MeshBVHLib.computeBoundsTree;
THREE.Mesh.prototype.raycast = MeshBVHLib.acceleratedRaycast;
const R = require("/opt/konfigurator/scripts/2026-09-11_glb_resolver.js");
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
cur.execute("SELECT data FROM product_assemblies WHERE id=350")
print(json.dumps(json.loads(cur.fetchone()["data"])["parts"]))
conn.close()
`;
fs.writeFileSync("/tmp/_dump_350.py", dumpPy);
const partsNew = JSON.parse(execSync("api/venv/bin/python3 /tmp/_dump_350.py", { cwd: "/opt/konfigurator", maxBuffer: 1024*1024*40 }).toString());
console.log("dilu nacteno z DB (id=350):", partsNew.length);

const KAT = "/opt/konfigurator/webapp/katalog/";
const BASE = "Citroën_Jumpy_CI19_2016-";
function loadWall(suf) {
  const m = parseGlbMesh(KAT + "car_bodies/" + BASE + suf + ".glb");
  m.material = new THREE.MeshBasicMaterial({ side: THREE.DoubleSide });
  m.updateMatrixWorld(true);
  m.geometry.computeBoundsTree();
  return m;
}
const walls = [loadWall("_L"), loadWall("_R_D"), loadWall("_B")];
function meshWorldEdgeSample(mesh, maxEdges) {
  const geo = mesh.geometry, pos = geo.attributes.position, idx = geo.index;
  const triCount = idx ? idx.count / 3 : pos.count / 3;
  const step = Math.max(1, Math.floor(triCount / (maxEdges / 3)));
  const edges = [];
  const vA = new THREE.Vector3(), vB = new THREE.Vector3(), vC = new THREE.Vector3();
  for (let t = 0; t < triCount; t += step) {
    let ia, ib, ic;
    if (idx) { ia = idx.getX(t * 3); ib = idx.getX(t * 3 + 1); ic = idx.getX(t * 3 + 2); } else { ia = t * 3; ib = t * 3 + 1; ic = t * 3 + 2; }
    vA.fromBufferAttribute(pos, ia).applyMatrix4(mesh.matrixWorld);
    vB.fromBufferAttribute(pos, ib).applyMatrix4(mesh.matrixWorld);
    vC.fromBufferAttribute(pos, ic).applyMatrix4(mesh.matrixWorld);
    edges.push([vA.clone(), vB.clone()], [vB.clone(), vC.clone()], [vC.clone(), vA.clone()]);
  }
  return edges;
}
const raycaster = new THREE.Raycaster();
function collidesWithWallsReal(mesh) {
  const edges = meshWorldEdgeSample(mesh, 300);
  for (const [p0, p1] of edges) {
    const dir = p1.clone().sub(p0), dist = dir.length();
    if (dist < 1e-6) continue;
    dir.normalize();
    raycaster.set(p0, dir); raycaster.far = dist;
    if (raycaster.intersectObjects(walls, false).length) return true;
  }
  return false;
}
function partMesh(p) {
  const glbPath = R.glbPath(p.part_id);
  if (!glbPath) throw new Error("CHYBI GLB pro part_id=" + p.part_id);
  const m = parseGlbMesh(glbPath);
  m.position.set(...p.position);
  m.quaternion.set(...p.quaternion);
  m.scale.set(...p.scale);
  m.updateMatrixWorld(true);
  return m;
}
const testable = partsNew.filter(p => !R.jeKaroserie(p.part_id) && !(p.role || "").startsWith("kontrolni-pomucka"));
let collisions = 0;
for (const p of testable) {
  if (collidesWithWallsReal(partMesh(p))) { collisions++; console.log("KOLIZE:", p.role, p.part_id); }
}
console.log(`SAT (z DB id=350): ${collisions}/${testable.length} koliduje.`);

// gap check
function box(role, zApprox) {
  const cands = testable.filter(p => p.role === role && Math.abs(p.position[2] - zApprox) < 2);
  return cands.map(p => new THREE.Box3().setFromObject(partMesh(p)));
}
const b1 = box("sloupek-pred-podbehem", -260.5)[0];
const b2 = box("zadni-svislice-nad-zarezem", -260.5)[0];
if (b1 && b2) console.log("gap(z DB) =", (b2.min.y - b1.max.y).toFixed(6), "mm");
