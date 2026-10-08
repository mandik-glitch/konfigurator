// Full re-verification of product_assemblies id=64/147/148 (Proace Long
// Electric 20-, TO22 car body ids 828-830) against the CORRECT car body GLB.
// bot16, 2026-09-01 - correcting a prior audit that tested against the
// WRONG car body (TO23 / ids 831-833) due to a mislabeled verify script.
const fs = require("fs");
const THREE = require("three");
const { makeCollisionModule } = require("/opt/konfigurator/scripts/2026-09-01_collision_module_factory.js");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");

const KAT = "/opt/konfigurator/webapp/katalog/";
const BASE = "/opt/konfigurator/webapp/katalog/car_bodies/Toyota_Proace_TO22_2020-"; // CORRECT body for id=64/147/148
const mod = makeCollisionModule(BASE);

const PID = process.argv[2] || "64";
const SP = "/tmp/claude-0/-opt-domeny/40752a20-c083-499a-8fe3-7c39a4eef60b/scratchpad";
const parts = JSON.parse(fs.readFileSync(`${SP}/pa${PID}_full_parts.json`, "utf8"));

function glbFor(id) {
  if (id.startsWith("car_body_")) return null;
  if (id === "Object_7") return KAT + "Object_7.glb";
  if (id === "product_3071") return KAT + "product_3071.glb";
  return KAT + id + ".glb";
}

function meshOf(p) {
  const path = glbFor(p.part_id);
  if (!path) return null;
  const m = parseGlbMesh(path);
  m.position.set(...p.position); m.quaternion.set(...p.quaternion); m.scale.set(...p.scale);
  m.updateMatrixWorld(true);
  return m;
}

// 1. Car-body collision check on EVERY part (profiles + endcaps + euroboxy)
let hits = 0, checked = 0;
const collidingParts = [];
for (const p of parts) {
  if (p.part_id.startsWith("car_body_")) continue;
  const m = meshOf(p);
  checked++;
  if (mod.collidesWithWalls(m)) { hits++; collidingParts.push({ role: p.role, part_id: p.part_id, position: p.position }); }
}
console.log(`[id=${PID}] car-body collision: parts checked=${checked} collisions=${hits}`);
if (hits) collidingParts.forEach(c => console.log("  COLLISION:", c.role, c.part_id, c.position));

// 2. Self-collision check (profile-profile must not overlap; eurobox/endcap
// nesting on rails/legs allowed - same rule as buildFull step 6)
const realParts = parts.filter(p => !p.part_id.startsWith("car_body_"));
const meshes = realParts.map(meshOf);
let unexpected = 0, expected = 0;
const badPairs = [];
for (let i = 0; i < meshes.length; i++) {
  for (let j = i + 1; j < meshes.length; j++) {
    const A = new THREE.Box3().setFromObject(meshes[i]), B = new THREE.Box3().setFromObject(meshes[j]);
    const ox = Math.min(A.max.x, B.max.x) - Math.max(A.min.x, B.min.x);
    const oy = Math.min(A.max.y, B.max.y) - Math.max(A.min.y, B.min.y);
    const oz = Math.min(A.max.z, B.max.z) - Math.max(A.min.z, B.min.z);
    if (ox > 0.5 && oy > 0.5 && oz > 0.5) {
      const nestOk = realParts[i].part_id !== "Object_7" || realParts[j].part_id !== "Object_7";
      if (nestOk) expected++;
      else { unexpected++; badPairs.push([realParts[i].role, realParts[j].role]); }
    }
  }
}
console.log(`[id=${PID}] self-collision: expected(nesting)=${expected} unexpected(profile-profile)=${unexpected}`);
if (unexpected) badPairs.forEach(p => console.log("  BAD PAIR:", p));

console.log(`[id=${PID}] RESULT: ${hits === 0 && unexpected === 0 ? "PASS" : "FAIL"}`);
