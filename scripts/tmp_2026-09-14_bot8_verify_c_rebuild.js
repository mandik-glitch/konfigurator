// Kolizni overeni pro prestavbu C-02/04/05/06 (344/343/345/347) podle
// receptu shape_geometry_methods.id=13 - srovnava PRED (puvodni cely
// seznam dilu) vs PO (kept + nove dily z receptu) na REALNE GLB geometrii.
const fs = require("fs");
const THREE = require("three");
const R = require("/opt/konfigurator/scripts/2026-09-11_glb_resolver.js");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");

const SCRATCH = "/tmp/claude-0/-opt-konfigurator/68994686-5a6b-46d4-b3c7-14bc1f68c6ac/scratchpad";
const P = JSON.parse(fs.readFileSync(`${SCRATCH}/c_rebuild_payload.json`, "utf8"));

function worldBox(p) {
  const glb = R.glbPath(p.part_id); if (!glb) return null;
  const mesh = parseGlbMesh(glb);
  mesh.position.set(p.position[0], p.position[1], p.position[2]);
  mesh.quaternion.set(p.quaternion[0], p.quaternion[1], p.quaternion[2], p.quaternion[3]);
  mesh.scale.set(p.scale[0], p.scale[1], p.scale[2]);
  mesh.updateMatrixWorld(true);
  return new THREE.Box3().setFromObject(mesh);
}
function overlap3(A, B) { return [Math.min(A.max.x, B.max.x) - Math.max(A.min.x, B.min.x), Math.min(A.max.y, B.max.y) - Math.max(A.min.y, B.min.y), Math.min(A.max.z, B.max.z) - Math.max(A.min.z, B.min.z)]; }
function scan(parts) {
  const m = parts.filter(p => !R.jeKaroserie(p.part_id)).map(p => ({ p, box: worldBox(p) }));
  const pairs = new Map(); let n = 0;
  for (let i = 0; i < m.length; i++) for (let j = i + 1; j < m.length; j++) {
    const [ox, oy, oz] = overlap3(m[i].box, m[j].box);
    if (ox > 0.5 && oy > 0.5 && oz > 0.5) { n++; pairs.set(m[i].p.role + "|" + m[j].p.role, [ox, oy, oz]); }
  }
  return { n, pairs };
}

let allOk = true;
const results = {};
for (const [idStr, info] of Object.entries(P)) {
  const id = Number(idStr);
  const kept = info.after_parts.filter(p => !info.new_hb_roles.includes(p.role));
  const after = info.after_parts;
  const before = scan(kept); // baseline BEZ hb vubec - odhali VSECHNY kolize nove sablony
  const afterScan = scan(after);
  const newPairs = [...afterScan.pairs.keys()].filter(k => !before.pairs.has(k));
  console.log(`\n=== id=${id} (varianta ${info.label}) ===`);
  console.log(`dilu: ${after.length}  kolize bez-hb=${before.n} s-hb=${afterScan.n} nove=${newPairs.length}`);
  for (const k of newPairs) console.log("   ", k, JSON.stringify(afterScan.pairs.get(k).map(v => +v.toFixed(1))));
  const ok = newPairs.length === 0;
  if (!ok) allOk = false;
  results[id] = { label: info.label, ok, parts: after };
}
fs.writeFileSync(`${SCRATCH}/c_rebuild_verified.json`, JSON.stringify(results));
console.log("\nCELKEM OK:", Object.values(results).filter(r => r.ok).length, "/", Object.keys(results).length);
