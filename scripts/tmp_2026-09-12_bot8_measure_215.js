// Prubezny diagnosticky skript (NE finalni transform) - meri skutecne Box3
// extenty ambiguich dilu sestavy 215 (cap/spojnice-dolni/spojnice-horni/
// zaslepka), aby se zjistilo, KTEROU stranu (predni X=-439, ci zadni
// X=-735/-611) skutecne premostuji, pred napsanim transformacniho pravidla.
const fs = require("fs");
const THREE = require("three");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");

const parts = JSON.parse(fs.readFileSync("/tmp/claude-0/-opt-konfigurator/c0c788fb-0783-4d56-adb5-543ba6b0dda8/scratchpad/215_parts.json", "utf8"));
const R = require("/opt/konfigurator/scripts/2026-09-11_glb_resolver.js");

function meshFor(p) {
  const gp = R.glbPath(p.part_id);
  const m = parseGlbMesh(gp);
  m.position.set(...p.position);
  m.quaternion.set(...p.quaternion);
  m.scale.set(...p.scale);
  m.updateMatrixWorld(true);
  return m;
}

const targetRoles = ["cap", "spojnice-dolni", "spojnice-horni", "zaslepka"];
for (const p of parts) {
  if (!targetRoles.includes(p.role)) continue;
  const m = meshFor(p);
  const box = new THREE.Box3().setFromObject(m);
  console.log(p.role.padEnd(16), "Z=" + p.position[2].toFixed(1).padStart(10),
    "X world[min,max]=[" + box.min.x.toFixed(1) + "," + box.max.x.toFixed(1) + "]",
    "Y[min,max]=[" + box.min.y.toFixed(1) + "," + box.max.y.toFixed(1) + "]",
    "Z[min,max]=[" + box.min.z.toFixed(1) + "," + box.max.z.toFixed(1) + "]");
}
