const fs = require("fs");
const THREE = require("three");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const R = require("/opt/konfigurator/scripts/2026-09-11_glb_resolver.js");
const { loadWalls, partMesh } = require("/opt/konfigurator/scripts/2026-09-12_wide_verify_lib.js");
const { execSync } = require("child_process");

const SCRATCH = "/tmp/claude-0/-opt-konfigurator/68994686-5a6b-46d4-b3c7-14bc1f68c6ac/scratchpad";
const AID = 471;
const VOZ = "Citroën_Jumpy_CI14_2016-";

function fetchAssembly(aid) {
  const py = `
import sys, json
sys.path.insert(0, "/opt/konfigurator/scripts")
from _env import get_conn
conn = get_conn()
with conn.cursor() as cur:
    cur.execute("SELECT name, data FROM product_assemblies WHERE id=%s", (${aid},))
    row = cur.fetchone()
conn.close()
print(json.dumps({"name": row["name"], "data": json.loads(row["data"])}))
`;
  fs.writeFileSync(`${SCRATCH}/_fetch_rozek_${aid}.py`, py);
  return JSON.parse(execSync(`/opt/konfigurator/api/venv/bin/python3 ${SCRATCH}/_fetch_rozek_${aid}.py`, { maxBuffer: 1024 * 1024 * 80 }).toString());
}

function box(p) {
  const glb = R.glbPath(p.part_id);
  if (!glb) return null;
  const m = parseGlbMesh(glb);
  m.position.set(...p.position); m.quaternion.set(...p.quaternion); m.scale.set(...p.scale);
  m.updateMatrixWorld(true);
  return new THREE.Box3().setFromObject(m);
}
function quatFromBasis(xDir, yDir, zDir) {
  const m = new THREE.Matrix4().makeBasis(
    new THREE.Vector3(...xDir), new THREE.Vector3(...yDir), new THREE.Vector3(...zDir)
  );
  const q = new THREE.Quaternion().setFromRotationMatrix(m);
  return [q.x, q.y, q.z, q.w];
}

const info = fetchAssembly(AID);
const parts = info.data.parts;
const profil = parts.find(p => p.role === "TEST-profil30-demo");
const profilX = profil.position[0];
const podelnikTopY = profil.position[1] - (profil.scale[1] * 1000) / 2; // spodek profilu = vrsek podelniku
const profilZmin = profil.position[2] - 15, profilZmax = profil.position[2] + 15; // 30mm prurez

// Bracket #1: +Z strana profilu, rameno podel +Z, rameno nahoru podel +Y
const q1 = quatFromBasis([0, 0, 1], [0, -1, 0], [1, 0, 0]);
const rozek1 = {
  part_id: "product_3176",
  position: [profilX - 18.5, podelnikTopY, profilZmax],
  quaternion: q1,
  scale: [1, 1, 1],
  role: "TEST-rozek40spojka-demo",
};
// Bracket #2: -Z strana profilu, zrcadlove (rameno podel -Z)
const q2 = quatFromBasis([0, 0, -1], [0, -1, 0], [-1, 0, 0]);
const rozek2 = {
  part_id: "product_3176",
  position: [profilX + 18.5, podelnikTopY, profilZmin],
  quaternion: q2,
  scale: [1, 1, 1],
  role: "TEST-rozek40spojka-demo",
};

const b1 = box(rozek1), b2 = box(rozek2);
console.log("rozek1 box:", JSON.stringify({ min: b1.min, max: b1.max }));
console.log("rozek2 box:", JSON.stringify({ min: b2.min, max: b2.max }));

// kolize s ostatnimi dily (krome profilu/podelniku samotnych, se kterymi
// se ma spojka logicky dotykat)
const oldStubs = new Set(parts.filter(p => p.role === "TEST-rozek30-demo").map(p => JSON.stringify(p)));
const others = parts.filter(p => !R.jeKaroserie(p.part_id) && !oldStubs.has(JSON.stringify(p)));
let hits = [];
for (const nb of [b1, b2]) {
  for (const p of others) {
    if (p.role === "TEST-profil30-demo") continue; // ocekavany dotyk
    const b = box(p);
    if (!b) continue;
    const ox = Math.min(nb.max.x, b.max.x) - Math.max(nb.min.x, b.min.x);
    const oy = Math.min(nb.max.y, b.max.y) - Math.max(nb.min.y, b.min.y);
    const oz = Math.min(nb.max.z, b.max.z) - Math.max(nb.min.z, b.min.z);
    if (ox > 1 && oy > 1 && oz > 1) hits.push({ s: p.role, overlap: [ox, oy, oz].map(v => +v.toFixed(1)) });
  }
}
console.log("kolize s jinymi dily (mimo profil/podelnik):", hits.length, JSON.stringify(hits));

const walls = loadWalls(VOZ);
function collidesWalls(mesh) {
  const geo = mesh.geometry, pos = geo.attributes.position, idx = geo.index;
  const triCount = idx ? idx.count / 3 : pos.count / 3;
  const vA = new THREE.Vector3(), vB = new THREE.Vector3(), vC = new THREE.Vector3();
  const rc = new THREE.Raycaster();
  for (let t = 0; t < triCount; t++) {
    let ia, ib, ic;
    if (idx) { ia = idx.getX(t * 3); ib = idx.getX(t * 3 + 1); ic = idx.getX(t * 3 + 2); } else { ia = t * 3; ib = t * 3 + 1; ic = t * 3 + 2; }
    vA.fromBufferAttribute(pos, ia).applyMatrix4(mesh.matrixWorld);
    vB.fromBufferAttribute(pos, ib).applyMatrix4(mesh.matrixWorld);
    vC.fromBufferAttribute(pos, ic).applyMatrix4(mesh.matrixWorld);
    for (const [p0, p1] of [[vA, vB], [vB, vC], [vC, vA]]) {
      const dir = p1.clone().sub(p0), dist = dir.length();
      if (dist < 1e-6) continue;
      dir.normalize(); rc.set(p0, dir); rc.far = dist;
      if (rc.intersectObjects(walls, false).length) return true;
    }
  }
  return false;
}
console.log("rozek1 kolize karoserie:", collidesWalls(partMesh(rozek1)));
console.log("rozek2 kolize karoserie:", collidesWalls(partMesh(rozek2)));

fs.writeFileSync(`${SCRATCH}/rozek3176_parts.json`, JSON.stringify({ rozek1, rozek2 }, null, 2));
console.log("OK zapsano");
