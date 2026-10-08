// Reproduce/characterize the pre-existing collision reported in id=64/147/148
// (Proace Long Electric TO23) column0 - bot16, 2026-09-01, audit follow-up.
const fs = require("fs");
const THREE = require("three");
const { makeCollisionModule } = require("/opt/konfigurator/scripts/2026-09-01_collision_module_factory.js");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");

const KAT = "/opt/konfigurator/webapp/katalog/";
const BASE = "/opt/konfigurator/webapp/katalog/car_bodies/Toyota_Proace_TO23_2020-";
const mod = makeCollisionModule(BASE);

const PID = process.argv[2] || "64";
const parts = JSON.parse(fs.readFileSync(`/tmp/claude-0/-opt-domeny/40752a20-c083-499a-8fe3-7c39a4eef60b/scratchpad/pa${PID}_full_parts.json`, "utf8"));

function glbFor(id) {
  if (id === "Object_7") return KAT + "Object_7.glb";
  if (id === "product_3071") return KAT + "product_3071.glb";
  return KAT + id + ".glb";
}

let hits = 0, total = 0;
for (const p of parts) {
  if (!p.role) continue;
  if (!p.role.includes("sloupec0")) {
    // also check legs bounding sloupec0 (any role not sloupec-scoped) separately below
    continue;
  }
  total++;
  const m = parseGlbMesh(glbFor(p.part_id));
  m.position.set(...p.position); m.quaternion.set(...p.quaternion); m.scale.set(...p.scale);
  m.updateMatrixWorld(true);
  const c = mod.collidesWithWalls(m);
  if (c) { hits++; console.log("COLLISION:", p.role, p.part_id, p.position); }
}
console.log(`sloupec0 parts checked=${total} collisions=${hits}`);

// also check the two legs bounding sloupec0 (predni-svislice/zadni-svislice-nad-zarezem etc at relevant Z)
const legRoles = ["predni-svislice","zadni-svislice-dolni","zadni-svislice-nad-zarezem","sloupek-pred-podbehem","pricka-uzavreni-vyrezu","cap"];
let legHits = 0, legTotal = 0;
for (const p of parts) {
  if (!p.role || !legRoles.includes(p.role)) continue;
  legTotal++;
  const m = parseGlbMesh(glbFor(p.part_id));
  m.position.set(...p.position); m.quaternion.set(...p.quaternion); m.scale.set(...p.scale);
  m.updateMatrixWorld(true);
  const c = mod.collidesWithWalls(m);
  if (c) { legHits++; console.log("LEG COLLISION:", p.role, p.part_id, p.position); }
}
console.log(`leg parts checked=${legTotal} collisions=${legHits}`);
