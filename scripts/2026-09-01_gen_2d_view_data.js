// Generates real Box3-derived top+elevation view data (mandatory 2D verification
// gate, rule 8) for all built vehicle racks, for a consolidated review artifact.
const THREE = require("three");
const fs = require("fs");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");

const KAT = "/opt/konfigurator/webapp/katalog/";
const OBJ7 = KAT + "Object_7.glb";
const ENDCAP = KAT + "product_3071.glb";
const EUROBOX_GLB = { 120: KAT + "product_3788.glb", 170: KAT + "product_3793.glb", 220: KAT + "product_3794.glb", 270: KAT + "product_3795.glb" };
const EUROBOX_PID = { 120: "product_3788", 170: "product_3793", 220: "product_3794", 270: "product_3795" };
function glbFor(id) {
  if (id === "Object_7") return OBJ7;
  if (id === "product_3071") return ENDCAP;
  for (const h in EUROBOX_PID) if (EUROBOX_PID[h] === id) return EUROBOX_GLB[h];
  return null; // car_body_* -> skip (not needed for rack-only 2D check)
}
function classify(p) {
  if (p.part_id === "product_3071") return "endcap";
  if (p.part_id.startsWith("product_37")) {
    for (const h in EUROBOX_PID) if (EUROBOX_PID[h] === p.part_id) return "box" + h;
  }
  if (p.role && p.role.startsWith("nosnik")) return "rail";
  if (p.role && p.role.startsWith("spojnice")) return "connector";
  return "leg";
}

const configs = JSON.parse(fs.readFileSync("/opt/konfigurator/scripts/2026-09-01_vehicle_configs.json", "utf8"));
const out = {};
for (const cfg of configs) {
  const key = cfg.key;
  const p = `/opt/konfigurator/scripts/2026-09-01_final_parts_${key}.json`;
  if (!fs.existsSync(p)) continue;
  const parts = JSON.parse(fs.readFileSync(p, "utf8"));
  const boxes = [];
  for (const part of parts) {
    const glb = glbFor(part.part_id);
    if (!glb) continue;
    const m = parseGlbMesh(glb);
    m.position.set(...part.position); m.quaternion.set(...part.quaternion); m.scale.set(...part.scale);
    m.updateMatrixWorld(true);
    const b = new THREE.Box3().setFromObject(m);
    boxes.push({ type: classify(part), minX: b.min.x, maxX: b.max.x, minY: b.min.y, maxY: b.max.y, minZ: b.min.z, maxZ: b.max.z });
  }
  out[key] = boxes;
  console.log(key, boxes.length, "boxes");
}
fs.writeFileSync("/opt/konfigurator/scripts/2026-09-01_2d_view_data.json", JSON.stringify(out));
