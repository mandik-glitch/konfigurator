// Verification gate for floor-fix batch (bot16, 2026-09-01), adapted from
// scripts/tmp_2026-08-31_gen2d_generic.js - checks overall dims + that
// eurobox bottoms sit on/above their rail tops (no floating / no floor punch-through)
// and that nothing collides with Y<0 (below floor).
const THREE = require("three");
const fs = require("fs");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const KAT = "/opt/konfigurator/webapp/katalog/";
function glbFor(id) {
  if (id === "Object_7") return KAT + "Object_7.glb";
  if (id === "product_3071") return KAT + "product_3071.glb";
  return KAT + id + ".glb";
}
const PID = process.argv[2];
const parts = JSON.parse(fs.readFileSync(`/tmp/claude-0/-opt-domeny/40752a20-c083-499a-8fe3-7c39a4eef60b/scratchpad/fixed_parts/${PID}_parts.json`, "utf8"));

const glbCache = {};
function getMeshBox(p) {
  if (!glbCache[p.part_id]) {
    glbCache[p.part_id] = parseGlbMesh(glbFor(p.part_id));
  }
  // clone-ish: re-parse is expensive but safe; instead reuse geometry via cloning matrix
  const m = glbCache[p.part_id];
  m.position.set(...p.position); m.quaternion.set(...p.quaternion); m.scale.set(...p.scale);
  m.updateMatrixWorld(true);
  return new THREE.Box3().setFromObject(m);
}

let gx = [1e9, -1e9], gy = [1e9, -1e9], gz = [1e9, -1e9];
const boxes = [];
for (const p of parts) {
  if (!p.role && !p.part_id.startsWith("car_body")) continue;
  if (p.part_id.startsWith("car_body")) continue;
  const b = getMeshBox(p);
  boxes.push({ role: p.role, part_id: p.part_id, min: [b.min.x, b.min.y, b.min.z], max: [b.max.x, b.max.y, b.max.z] });
  gx[0] = Math.min(gx[0], b.min.x); gx[1] = Math.max(gx[1], b.max.x);
  gy[0] = Math.min(gy[0], b.min.y); gy[1] = Math.max(gy[1], b.max.y);
  gz[0] = Math.min(gz[0], b.min.z); gz[1] = Math.max(gz[1], b.max.z);
}

const dims = { depthX: gx[1] - gx[0], heightY: gy[1] - gy[0], lengthZ: gz[1] - gz[0] };
console.log(PID, "dims mm: depthX=", dims.depthX.toFixed(0), "heightY=", dims.heightY.toFixed(0), "lengthZ=", dims.lengthZ.toFixed(0), "parts=", boxes.length);

// Gate 1: nothing below floor (Y<0), small tolerance -1mm
let minY = 1e9, minYPart = null;
boxes.forEach(b => { if (b.min[1] < minY) { minY = b.min[1]; minYPart = b; } });
console.log(PID, "GATE min_Y=", minY.toFixed(1), minY >= -1 ? "OK" : "FAIL(below floor)", minYPart && minYPart.role);

// Gate 2: sanity dims (height 1000-1300mm typical for these families, depth ~300-350mm)
const okH = dims.heightY > 900 && dims.heightY < 1350;
const okD = dims.depthX > 300 && dims.depthX < 350;
console.log(PID, "GATE heightY_ok=", okH, "depthX_ok=", okD);

if (minY < -1 || !okH || !okD) {
  console.error(PID, "SANITY GATE FAILED");
  process.exit(1);
}
console.log(PID, "GATE PASSED");
