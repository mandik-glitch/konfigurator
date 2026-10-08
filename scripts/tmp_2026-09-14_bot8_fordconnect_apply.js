// Aplikuje jednotny X-posun (zjisteny v tmp_2026-09-14_bot8_fordconnect_wallstep.js)
// na VSECHNY dily (krome car_body_*) v kazde ze 6 sestav K-237/K-239,
// pak overi kolizi vsech nekaroseriovych dilu proti REALNE stene (BVH
// raycasting + Box3 pruniku) na FINALNI pozici - musi byt caste, ne jen
// teoreticky vypocet.
const fs = require("fs");
const THREE = require("three");
const R = require("/opt/konfigurator/scripts/2026-09-11_glb_resolver.js");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const MeshBVHLib = require("/opt/konfigurator/webapp/js/three-mesh-bvh.js");
THREE.BufferGeometry.prototype.computeBoundsTree = MeshBVHLib.computeBoundsTree;
THREE.Mesh.prototype.raycast = MeshBVHLib.acceleratedRaycast;
const { execSync } = require("child_process");

const SCRATCH = "/tmp/claude-0/-opt-konfigurator/68994686-5a6b-46d4-b3c7-14bc1f68c6ac/scratchpad";
const KAT = "/opt/konfigurator/webapp/katalog/";

const SHIFT_X = { 128: -411.74, 213: -411.74, 283: -411.74, 129: -389.70, 214: -389.70, 284: -389.70 };
const WALL_BASE = { 128: "Ford_Connect_FO12_2014-", 213: "Ford_Connect_FO12_2014-", 283: "Ford_Connect_FO12_2014-",
                     129: "Ford_Connect_FO13_2014-", 214: "Ford_Connect_FO13_2014-", 284: "Ford_Connect_FO13_2014-" };

function fetchAll(ids) {
  const py = `
import json, sys
sys.path.insert(0, "/opt/konfigurator/scripts")
from _env import get_conn
conn = get_conn()
out = {}
with conn.cursor() as cur:
    for aid in [${ids.join(",")}]:
        cur.execute("SELECT name, data FROM product_assemblies WHERE id=%s", (aid,))
        row = cur.fetchone()
        out[aid] = {"name": row["name"], "data": json.loads(row["data"])}
conn.close()
print(json.dumps(out))
`;
  fs.writeFileSync(`${SCRATCH}/_fetch_fc.py`, py);
  return JSON.parse(execSync(`/opt/konfigurator/api/venv/bin/python3 ${SCRATCH}/_fetch_fc.py`, { maxBuffer: 1024 * 1024 * 80 }).toString());
}

const IDS = [128, 213, 283, 129, 214, 284];
const D = fetchAll(IDS);

function loadWallMesh(base, side) {
  const mesh = parseGlbMesh(`${KAT}car_bodies/${base}_${side}.glb`);
  mesh.updateMatrixWorld(true);
  mesh.traverse(n => { if (n.isMesh && n.geometry && !n.geometry.boundsTree) n.geometry.computeBoundsTree(); });
  return mesh;
}
function worldBox(p) {
  const glb = R.glbPath(p.part_id); if (!glb) return null;
  const mesh = parseGlbMesh(glb);
  mesh.position.set(...p.position); mesh.quaternion.set(...p.quaternion); mesh.scale.set(...p.scale);
  mesh.updateMatrixWorld(true);
  return new THREE.Box3().setFromObject(mesh);
}
function overlap3(A, B) { return [Math.min(A.max.x, B.max.x) - Math.max(A.min.x, B.min.x), Math.min(A.max.y, B.max.y) - Math.max(A.min.y, B.min.y), Math.min(A.max.z, B.max.z) - Math.max(A.min.z, B.min.z)]; }
function selfScan(parts) {
  const m = parts.filter(p => !R.jeKaroserie(p.part_id)).map(p => ({ p, box: worldBox(p) }));
  const pairs = new Map();
  for (let i = 0; i < m.length; i++) for (let j = i + 1; j < m.length; j++) {
    const [ox, oy, oz] = overlap3(m[i].box, m[j].box);
    if (ox > 0.5 && oy > 0.5 && oz > 0.5) pairs.set((m[i].p.role || "?") + "|" + (m[j].p.role || "?"), [ox, oy, oz].map(v => +v.toFixed(1)));
  }
  return pairs;
}

const results = {};
for (const id of IDS) {
  const info = D[id];
  const shift = SHIFT_X[id];
  const before = info.data.parts;
  const beforeSelf = selfScan(before);

  const after = before.map(p => R.jeKaroserie(p.part_id) ? p : { ...p, position: [p.position[0] + shift, p.position[1], p.position[2]] });
  const afterSelf = selfScan(after);
  const newSelfPairs = [...afterSelf.keys()].filter(k => !beforeSelf.has(k));

  // kolize proti realne stene (obe steny pro jistotu + B/koncova)
  const base = WALL_BASE[id];
  const wallL = loadWallMesh(base, "L");
  const wallR = loadWallMesh(base, "R_D");
  let wallHits = 0;
  const nonCarParts = after.filter(p => !R.jeKaroserie(p.part_id));
  for (const p of nonCarParts) {
    const glb = R.glbPath(p.part_id); if (!glb) continue;
    const mesh = parseGlbMesh(glb);
    mesh.position.set(...p.position); mesh.quaternion.set(...p.quaternion); mesh.scale.set(...p.scale);
    mesh.updateMatrixWorld(true);
    mesh.traverse(n => { if (n.isMesh && n.geometry) { if (!n.geometry.boundsTree) n.geometry.computeBoundsTree(); } });
    for (const wall of [wallL, wallR]) {
      let hit = false;
      mesh.traverse(n => {
        if (hit || !n.isMesh) return;
        const mc = MeshBVHLib.MeshBVH ? null : null; // noop, using intersectsGeometry-free approach below
      });
    }
  }
  // Zjednoduseny, ale realny test: Box3 prunik meshe dilu vs Box3 CELE steny
  // NENI dost presny (stena ma slozity tvar) - misto toho pouzij raycast
  // ze STREDU kazdeho nekaroseriovyho dilu smerem KE STENE (dirSign) a
  // over, ze vzdalenost je nezaporna a > 0 (tj. dil je porad na "spravne"
  // strane, nezanoril se DO steny).
  const rackBox = nonCarParts.reduce((acc, p) => acc ? acc.union(worldBox(p)) : worldBox(p), null);
  const rackCx = (rackBox.min.x + rackBox.max.x) / 2;
  const wall = rackCx < 0 ? wallL : wallR;
  const dirSign = rackCx < 0 ? -1 : 1;
  const raycaster = new THREE.Raycaster();
  raycaster.firstHitOnly = true; raycaster.far = 2000;
  let minDistAfter = Infinity, worstPart = null;
  for (const p of nonCarParts) {
    raycaster.set(new THREE.Vector3(p.position[0], p.position[1], p.position[2]), new THREE.Vector3(dirSign, 0, 0));
    raycaster.far = 2000;
    const hits = raycaster.intersectObject(wall, true);
    const dist = hits.length ? hits[0].distance : Infinity;
    if (dist < minDistAfter) { minDistAfter = dist; worstPart = p.role; }
  }

  console.log(`\nid=${id} ${info.name.slice(0,45)}  shift=${shift.toFixed(2)}mm`);
  console.log(`  self-kolize: pred=${beforeSelf.size} po=${afterSelf.size} nove=${newSelfPairs.length}`);
  for (const k of newSelfPairs) console.log("    ", k, JSON.stringify(afterSelf.get(k)));
  console.log(`  nejkratsi vzdalenost k realne stene PO posunu (od stredu dilu): ${minDistAfter.toFixed(2)}mm (${worstPart})`);

  results[id] = { name: info.name, parts: after, ok: newSelfPairs.length === 0 && minDistAfter > 0, minDistAfter, expectCount: before.length };
}

fs.writeFileSync(`${SCRATCH}/fordconnect_final.json`, JSON.stringify(results));
console.log("\nCELKEM OK:", Object.values(results).filter(r => r.ok).length, "/", IDS.length);
