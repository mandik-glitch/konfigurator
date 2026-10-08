const fs = require("fs");
const THREE = require("three");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const R = require("/opt/konfigurator/scripts/2026-09-11_glb_resolver.js");
const { loadWalls, partMesh } = require("/opt/konfigurator/scripts/2026-09-12_wide_verify_lib.js");
const { execSync } = require("child_process");

const SCRATCH = "/tmp/claude-0/-opt-konfigurator/68994686-5a6b-46d4-b3c7-14bc1f68c6ac/scratchpad";
const AID = 472;
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
  fs.writeFileSync(`${SCRATCH}/_fetch_sipka_${aid}.py`, py);
  return JSON.parse(execSync(`/opt/konfigurator/api/venv/bin/python3 ${SCRATCH}/_fetch_sipka_${aid}.py`, { maxBuffer: 1024 * 1024 * 80 }).toString());
}
function box(p) {
  const glb = R.glbPath(p.part_id);
  if (!glb) return null;
  const m = parseGlbMesh(glb);
  m.position.set(...p.position); m.quaternion.set(...p.quaternion); m.scale.set(...p.scale);
  m.updateMatrixWorld(true);
  return new THREE.Box3().setFromObject(m);
}

const info = fetchAssembly(AID);
const parts = info.data.parts;
const podelnik = parts.find(p => p.role === "podelnik-celni-spodni-0");
const celoA = parts.find(p => p.role === "vypln-celo-0-a");
const celoB = parts.find(p => p.role === "vypln-celo-0-b");

const QUAT = [0, 0.7071067811865476, 0, 0.7071067811865475]; // stejna orientace jako vypln-celo (local X->world -Z, local Z(tenka)->world X)
const WINDOW_Z = podelnik.position[2]; // stred puvodniho okna, nezavisle na aktualni nahodne pozici panelu
const FRONT_X_OFFSET = 15; // mm, kousek pred plochou celo/podelniku smerem k divakovi (+X)

const sipkaA = {
  part_id: "sipka_posuvne_celo",
  position: [podelnik.position[0] + FRONT_X_OFFSET, celoA.position[1], WINDOW_Z],
  quaternion: QUAT,
  scale: [1, 1, 1],
  role: "TEST-sipka-posuvne-celo-a",
};
const sipkaB = {
  part_id: "sipka_posuvne_celo",
  position: [podelnik.position[0] + FRONT_X_OFFSET, celoB.position[1], WINDOW_Z],
  quaternion: QUAT,
  scale: [1, 1, 1],
  role: "TEST-sipka-posuvne-celo-b",
};

const bA = box(sipkaA), bB = box(sipkaB);
console.log("sipkaA box:", JSON.stringify({ min: bA.min, max: bA.max }));
console.log("sipkaB box:", JSON.stringify({ min: bB.min, max: bB.max }));

let hits = [];
for (const s of [sipkaA, sipkaB]) {
  const sb = box(s);
  for (const p of parts) {
    if (R.jeKaroserie(p.part_id)) continue;
    const b = box(p);
    if (!b) continue;
    const ox = Math.min(sb.max.x, b.max.x) - Math.max(sb.min.x, b.min.x);
    const oy = Math.min(sb.max.y, b.max.y) - Math.max(sb.min.y, b.min.y);
    const oz = Math.min(sb.max.z, b.max.z) - Math.max(sb.min.z, b.min.z);
    if (ox > 0.5 && oy > 0.5 && oz > 0.5) hits.push({ s: s.role, o: p.role, overlap: [ox, oy, oz].map(v => +v.toFixed(1)) });
  }
}
console.log("kolize s dily:", hits.length, JSON.stringify(hits));

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
console.log("sipkaA kolize karoserie:", collidesWalls(partMesh(sipkaA)));
console.log("sipkaB kolize karoserie:", collidesWalls(partMesh(sipkaB)));

fs.writeFileSync(`${SCRATCH}/sipka_parts.json`, JSON.stringify({ sipkaA, sipkaB }, null, 2));
console.log("OK zapsano");
