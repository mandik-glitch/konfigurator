// Hruby-pak-jemny sken (misto spoleha na drivejsi chybny odhad): zacni na
// PUVODNI (0mm posun) pozici, over ze je bez kolize, pak kroc 10mm smerem
// ke stene dokud nekoliduje, pak zjemni na 1mm v tom useku.
const fs = require("fs");
const R = require("/opt/konfigurator/scripts/2026-09-11_glb_resolver.js");
const { loadWalls, partMesh } = require("/opt/konfigurator/scripts/2026-09-12_wide_verify_lib.js");
const THREE = require("three");
const { execSync } = require("child_process");

const SCRATCH = "/tmp/claude-0/-opt-konfigurator/68994686-5a6b-46d4-b3c7-14bc1f68c6ac/scratchpad";
const WALL_BASE = { 128: "Ford_Connect_FO12_2014-", 129: "Ford_Connect_FO13_2014-" };

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
  fs.writeFileSync(`${SCRATCH}/_fetch_fc3.py`, py);
  return JSON.parse(execSync(`/opt/konfigurator/api/venv/bin/python3 ${SCRATCH}/_fetch_fc3.py`, { maxBuffer: 1024 * 1024 * 80 }).toString());
}

function shiftParts(parts, dx) {
  return parts.map(p => R.jeKaroserie(p.part_id) ? p : { ...p, position: [p.position[0] + dx, p.position[1], p.position[2]] });
}
function collidesWithWallsReal(mesh, walls) {
  const geo = mesh.geometry, pos = geo.attributes.position, idx = geo.index;
  const triCount = idx ? idx.count / 3 : pos.count / 3;
  const maxEdges = 300;
  const step = Math.max(1, Math.floor(triCount / (maxEdges / 3)));
  const vA = new THREE.Vector3(), vB = new THREE.Vector3(), vC = new THREE.Vector3();
  const raycaster = new THREE.Raycaster();
  for (let t = 0; t < triCount; t += step) {
    let ia, ib, ic;
    if (idx) { ia = idx.getX(t * 3); ib = idx.getX(t * 3 + 1); ic = idx.getX(t * 3 + 2); } else { ia = t * 3; ib = t * 3 + 1; ic = t * 3 + 2; }
    vA.fromBufferAttribute(pos, ia).applyMatrix4(mesh.matrixWorld);
    vB.fromBufferAttribute(pos, ib).applyMatrix4(mesh.matrixWorld);
    vC.fromBufferAttribute(pos, ic).applyMatrix4(mesh.matrixWorld);
    for (const [p0, p1] of [[vA, vB], [vB, vC], [vC, vA]]) {
      const dir = p1.clone().sub(p0), dist = dir.length();
      if (dist < 1e-6) continue;
      dir.normalize();
      raycaster.set(p0, dir); raycaster.far = dist;
      if (raycaster.intersectObjects(walls, false).length) return true;
    }
  }
  return false;
}
function anyHit(parts, walls) {
  const testable = parts.filter(p => !R.jeKaroserie(p.part_id) && !(p.role || "").startsWith("kontrolni-pomucka"));
  for (const p of testable) {
    if (collidesWithWallsReal(partMesh(p), walls)) return { hit: true, role: p.role };
  }
  return { hit: false };
}

const D = fetchAll([128, 129]);
const dirBySignOfRackCenter = (parts) => {
  // rychly odhad smeru: prumer X vsech nekaroseriovych dilu
  const xs = parts.filter(p => !R.jeKaroserie(p.part_id)).map(p => p.position[0]);
  const avg = xs.reduce((a, b) => a + b, 0) / xs.length;
  return avg < 0 ? -1 : 1;
};

const finalDx = {};
for (const id of [128, 129]) {
  const base = WALL_BASE[id];
  const walls = loadWalls(base);
  const orig = D[id].data.parts;
  const dir = dirBySignOfRackCenter(orig);
  console.log(`\n=== id=${id} (${base}) smer=${dir} ===`);

  const zero = anyHit(orig, walls);
  console.log("  puvodni (0mm) kolize:", zero.hit, zero.role || "");

  // hruby sken po 10mm
  let coarse = 0;
  let lastSafe = 0;
  while (Math.abs(coarse) < 700) {
    const cand = coarse + dir * 10;
    const r = anyHit(shiftParts(orig, cand), walls);
    if (r.hit) { console.log(`  hruby sken: kolize na ${cand}mm (${r.role})`); break; }
    coarse = cand; lastSafe = cand;
  }
  // jemny sken po 1mm od lastSafe
  let fine = lastSafe;
  let steps = 0;
  while (steps < 15) {
    const cand = fine + dir * 1;
    const r = anyHit(shiftParts(orig, cand), walls);
    if (r.hit) { console.log(`  jemny sken: kolize na ${cand.toFixed(0)}mm (${r.role})`); break; }
    fine = cand; steps++;
  }
  const result = fine - dir * 2;
  const check = anyHit(shiftParts(orig, result), walls);
  console.log(`  VYSLEDEK dx=${result}mm, bez kolize: ${!check.hit}`);
  finalDx[id] = result;
}
fs.writeFileSync(`${SCRATCH}/fordconnect_scan_dx.json`, JSON.stringify(finalDx));
console.log("\n", finalDx);
