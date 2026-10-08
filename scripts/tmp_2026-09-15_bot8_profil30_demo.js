const fs = require("fs");
const THREE = require("three");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const R = require("/opt/konfigurator/scripts/2026-09-11_glb_resolver.js");
const { loadWalls, partMesh } = require("/opt/konfigurator/scripts/2026-09-12_wide_verify_lib.js");
const { execSync } = require("child_process");

const SCRATCH = "/tmp/claude-0/-opt-konfigurator/68994686-5a6b-46d4-b3c7-14bc1f68c6ac/scratchpad";
const SRC_ID = 414; // Jumpy L2 K-122 A-01
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
  fs.writeFileSync(`${SCRATCH}/_fetch_demo_${aid}.py`, py);
  return JSON.parse(execSync(`/opt/konfigurator/api/venv/bin/python3 ${SCRATCH}/_fetch_demo_${aid}.py`, { maxBuffer: 1024 * 1024 * 80 }).toString());
}

function box(p) {
  const glb = R.glbPath(p.part_id);
  if (!glb) return null;
  const m = parseGlbMesh(glb);
  m.position.set(...p.position); m.quaternion.set(...p.quaternion); m.scale.set(...p.scale);
  m.updateMatrixWorld(true);
  return new THREE.Box3().setFromObject(m);
}

const info = fetchAssembly(SRC_ID);
const parts = info.data.parts;
const podelnik = parts.find(p => p.role === "podelnik-celni-spodni-0");
const pb = box(podelnik);
console.log("podelnik-celni-spodni-0 real box:", JSON.stringify({ min: pb.min, max: pb.max }));

// Object_7 je ctvercovy profil 30x30 (overeno na surove lokalni geometrii,
// bez transformace: size {x:30,y:1000,z:30}) - prurez je VZDY 30x30 bez
// ohledu na natoceni instance, na rozdil od bounding-boxu ROTOVANE instance
// (ten by u podelniku vratil 1224mm - delku, ne prurez).
const SEC = 30;

const topY = pb.max.y;
const centerZ = (pb.max.z + pb.min.z) / 2;
const frontX = podelnik.position[0];

const PROFIL_LEN = 130;
const ROZEK_LEN = 60;

const profil = {
  part_id: "Object_7",
  position: [frontX, topY + PROFIL_LEN / 2, centerZ],
  quaternion: [0, 0, 0, 1],
  scale: [1, PROFIL_LEN / 1000, 1],
  role: "TEST-profil30-demo",
  color_hex: "#1e5fff",
};

// Rozek = kratky pahyl stejneho profilu, kolmo k novemu svislemu kusu,
// polozeny vodorovne na podelniku hned vedle paty profilu (podel Z, ktery
// je smer beh podelniku) - stejna logika jako spojnice-dolni/horni v teto
// sestave, jen orientovany podel Z misto X.
function rozek(signZ) {
  return {
    part_id: "Object_7",
    position: [frontX, topY + SEC / 2, centerZ + signZ * (SEC / 2 + ROZEK_LEN / 2)],
    quaternion: [0.707107, 0, 0, 0.707107], // -90 deg okolo X: lokalni Y (delka) -> world Z
    scale: [1, ROZEK_LEN / 1000, 1],
    role: "TEST-rozek30-demo",
  };
}
const rozek1 = rozek(+1);
const rozek2 = rozek(-1);

const newParts = [profil, rozek1, rozek2];
const boxes = newParts.map(box);
boxes.forEach((b, i) => console.log(newParts[i].role, "box:", JSON.stringify({ min: b.min, max: b.max })));

let hits = [];
for (const np of newParts) {
  const nb = box(np);
  for (const p of parts) {
    if (R.jeKaroserie(p.part_id)) continue;
    const b = box(p);
    if (!b) continue;
    const ox = Math.min(nb.max.x, b.max.x) - Math.max(nb.min.x, b.min.x);
    const oy = Math.min(nb.max.y, b.max.y) - Math.max(nb.min.y, b.min.y);
    const oz = Math.min(nb.max.z, b.max.z) - Math.max(nb.min.z, b.min.z);
    if (ox > 0.5 && oy > 0.5 && oz > 0.5) hits.push({ novy: np.role, s: p.role, overlap: [ox, oy, oz].map(v => +v.toFixed(1)) });
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
for (const np of newParts) {
  console.log(np.role, "kolize karoserie:", collidesWalls(partMesh(np)));
}

fs.writeFileSync(`${SCRATCH}/bot8_profil30_demo_parts.json`, JSON.stringify({ profil, rozek1, rozek2 }, null, 2));
console.log("OK zapsano do scratch");
