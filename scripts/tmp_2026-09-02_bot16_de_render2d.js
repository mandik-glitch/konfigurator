// 2D top+elevation SVG data pro vsech 10 novych D/E variant (bot16, 2026-09-02).
const THREE = require("three");
const fs = require("fs");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const KAT = "/opt/konfigurator/webapp/katalog/";
function glbFor(id) { if (id === "Object_7") return KAT + "Object_7.glb"; if (id === "product_3071") return KAT + "product_3071.glb"; return KAT + id + ".glb"; }
function meshOf(p) {
  const m = parseGlbMesh(glbFor(p.part_id));
  m.position.set(...p.position); m.quaternion.set(...p.quaternion); m.scale.set(...p.scale);
  m.updateMatrixWorld(true);
  return m;
}
function box3Of(p) { return new THREE.Box3().setFromObject(meshOf(p)); }

const SCRATCH = "/tmp/claude-0/-opt-domeny/40752a20-c083-499a-8fe3-7c39a4eef60b/scratchpad";
const KEYS = ["PE25", "MB47", "FO31", "VW25", "OP31"];
const out = {};
for (const key of KEYS) {
  for (const tag of ["D", "E"]) {
    const parts = JSON.parse(fs.readFileSync(`${SCRATCH}/de_parts_${key}_${tag}.json`, "utf8"));
    const nonCarBody = parts.filter(p => !p.part_id.startsWith("car_body"));
    const boxes = nonCarBody.map(p => {
      const b = box3Of(p);
      return { role: p.role, part_id: p.part_id, min: [b.min.x, b.min.y, b.min.z], max: [b.max.x, b.max.y, b.max.z] };
    });
    out[`${key}_${tag}`] = boxes;
  }
}
fs.writeFileSync(`${SCRATCH}/de_render2d_boxes.json`, JSON.stringify(out));
console.log("hotovo", Object.keys(out).length, "sestav");
