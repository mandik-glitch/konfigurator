const fs = require("fs");
const THREE = require("three");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const R = require("/opt/konfigurator/scripts/2026-09-11_glb_resolver.js");
const { loadWalls, partMesh } = require("/opt/konfigurator/scripts/2026-09-12_wide_verify_lib.js");
const { execSync } = require("child_process");

const SCRATCH = "/tmp/claude-0/-opt-konfigurator/68994686-5a6b-46d4-b3c7-14bc1f68c6ac/scratchpad";
const ZASUN = 7, HEIGHT = 130;
const IDS = [394, 398, 402, 406, 410];
const VOZ = { 394: "Citroën_Jumpy_CI13_2016-", 398: "Citroën_Jumpy_CI13_2016-",
              402: "Citroën_Jumpy_CI24_2021-", 406: "Citroën_Jumpy_CI24_2021-", 410: "Citroën_Jumpy_CI24_2021-" };

function box(p) {
  const glb = R.glbPath(p.part_id); if (!glb) return null;
  const m = parseGlbMesh(glb);
  m.position.set(...p.position); m.quaternion.set(...p.quaternion); m.scale.set(...p.scale);
  m.updateMatrixWorld(true);
  return new THREE.Box3().setFromObject(m);
}
function collidesWithWallsReal(mesh, walls) {
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
  fs.writeFileSync(`${SCRATCH}/_fetch_l1_${aid}.py`, py);
  return JSON.parse(execSync(`/opt/konfigurator/api/venv/bin/python3 ${SCRATCH}/_fetch_l1_${aid}.py`, { maxBuffer: 1024 * 1024 * 80 }).toString());
}

for (const aid of IDS) {
  const info = fetchAssembly(aid);
  const podelnik = info.data.parts.find(p => p.role === "podelnik-celni-spodni-0");
  const pb = box(podelnik);
  const bottomY = pb.max.y - ZASUN;
  const centerY = bottomY + HEIGHT / 2;
  const zLen = pb.max.z - pb.min.z;
  const centerZ = (pb.max.z + pb.min.z) / 2;
  const deska = {
    part_id: "product_3950",
    position: [podelnik.position[0], centerY, centerZ],
    quaternion: [0, 0.7071067811865476, 0, 0.7071067811865475],
    scale: [zLen / 1000, HEIGHT / 1000, 1],
    role: "vypln-celo-0",
  };
  const deskaBox = box(deska);

  let hits = [];
  for (const p of info.data.parts) {
    if (R.jeKaroserie(p.part_id)) continue;
    if (p === podelnik) continue;
    const b = box(p);
    if (!b) continue;
    const ox = Math.min(deskaBox.max.x, b.max.x) - Math.max(deskaBox.min.x, b.min.x);
    const oy = Math.min(deskaBox.max.y, b.max.y) - Math.max(deskaBox.min.y, b.min.y);
    const oz = Math.min(deskaBox.max.z, b.max.z) - Math.max(deskaBox.min.z, b.min.z);
    if (ox > 0.5 && oy > 0.5 && oz > 0.5) hits.push({ role: p.role, overlap: [ox, oy, oz].map(v => +v.toFixed(1)) });
  }
  const walls = loadWalls(VOZ[aid]);
  const wallHit = collidesWithWallsReal(partMesh(deska), walls);

  console.log(`id=${aid} ${info.name.slice(0,45)} deskaY=[${bottomY.toFixed(1)},${(bottomY+HEIGHT).toFixed(1)}] kolize_dily=${hits.length} kolize_karoserie=${wallHit}`);
  if (hits.length) console.log("  ", JSON.stringify(hits));

  fs.writeFileSync(`${SCRATCH}/deska_l1_${aid}.json`, JSON.stringify({ ok: hits.length === 0 && !wallHit, deska }));
}
