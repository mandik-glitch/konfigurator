// Spot-check other ProAce batch rows for the SAME symptom (both rail levels
// colliding) using each row's OWN correct car body - bot16, 2026-09-01.
const fs = require("fs");
const THREE = require("three");
const { makeCollisionModule } = require("/opt/konfigurator/scripts/2026-09-01_collision_module_factory.js");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const KAT = "/opt/konfigurator/webapp/katalog/";
const SP = "/tmp/claude-0/-opt-domeny/40752a20-c083-499a-8fe3-7c39a4eef60b/scratchpad";

const ROWS = [
  { id: 59, base: "Toyota_Proace_TO08_2020-" },
  { id: 60, base: "Toyota_Proace_TO09_2020-" },
  { id: 61, base: "Toyota_Proace_TO12_2020-" },
  { id: 62, base: "Toyota_Proace_TO17_2020-" },
  { id: 63, base: "Toyota_Proace_TO21_2020-" },
  { id: 65, base: "Toyota_Proace_TO23_2020-" },
];

function glbFor(id) {
  if (id === "Object_7") return KAT + "Object_7.glb";
  if (id === "product_3071") return KAT + "product_3071.glb";
  return KAT + id + ".glb";
}
function meshOf(mod, p) {
  const m = parseGlbMesh(glbFor(p.part_id));
  m.position.set(...p.position); m.quaternion.set(...p.quaternion); m.scale.set(...p.scale);
  m.updateMatrixWorld(true);
  return m;
}

for (const row of ROWS) {
  const mod = makeCollisionModule(KAT + "car_bodies/" + row.base);
  const parts = JSON.parse(fs.readFileSync(`${SP}/pa${row.id}_full_parts.json`, "utf8")).filter(p => !p.part_id.startsWith("car_body_"));
  let hits = 0;
  const bad = [];
  for (const p of parts) {
    const m = meshOf(mod, p);
    if (mod.collidesWithWalls(m)) { hits++; bad.push(p.role); }
  }
  console.log(`id=${row.id} (${row.base}): parts=${parts.length} collisions=${hits}`, hits ? bad : "");
}
