// Generic 2D (top+elevation) verification generator - rule 8 mandatory gate
// before any product_assemblies insert. Usage: node this.js <VEHICLE_KEY>
const THREE = require("three");
const fs = require("fs");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const KAT = "/opt/konfigurator/webapp/katalog/";
function glbFor(id) {
  if (id === "Object_7") return KAT + "Object_7.glb";
  if (id === "product_3071") return KAT + "product_3071.glb";
  return KAT + id + ".glb";
}
const KEY = process.argv[2];
const rack = JSON.parse(fs.readFileSync(`/opt/konfigurator/scripts/tmp_2026-08-31_batch_${KEY}_parts.json`, "utf8"));
const boxes = rack.map(p => {
  const m = parseGlbMesh(glbFor(p.part_id));
  m.position.set(...p.position); m.quaternion.set(...p.quaternion); m.scale.set(...p.scale);
  m.updateMatrixWorld(true);
  const b = new THREE.Box3().setFromObject(m);
  return { role: p.role, part_id: p.part_id, min: [b.min.x, b.min.y, b.min.z], max: [b.max.x, b.max.y, b.max.z] };
});
let gx = [1e9, -1e9], gy = [1e9, -1e9], gz = [1e9, -1e9];
boxes.forEach(b => {
  gx[0] = Math.min(gx[0], b.min[0]); gx[1] = Math.max(gx[1], b.max[0]);
  gy[0] = Math.min(gy[0], b.min[1]); gy[1] = Math.max(gy[1], b.max[1]);
  gz[0] = Math.min(gz[0], b.min[2]); gz[1] = Math.max(gz[1], b.max[2]);
});
const dims = { depthX: gx[1] - gx[0], heightY: gy[1] - gy[0], lengthZ: gz[1] - gz[0] };
console.log(KEY, "dims mm: depthX=", dims.depthX.toFixed(0), "heightY=", dims.heightY.toFixed(0), "lengthZ=", dims.lengthZ.toFixed(0), "parts=", boxes.length);

function colorFor(role, part_id) {
  if (part_id.startsWith("product_37")) return { fill: "#f6c453", stroke: "#8a5a00" };
  if (part_id === "product_3071") return { fill: "#bcd4e6", stroke: "#2b5f81" };
  if (role.startsWith("nosnik") || role.startsWith("spojnice")) return { fill: "#9fd3a4", stroke: "#2f6b36" };
  return { fill: "#c9c9c9", stroke: "#555" };
}
const SCALE = 0.25;
function svgTop() {
  const w = dims.lengthZ * SCALE, h = dims.depthX * SCALE;
  let rects = "";
  boxes.forEach(b => {
    const { fill, stroke } = colorFor(b.role, b.part_id);
    const x = (gz[1] - b.max[2]) * SCALE, y = (b.min[0] - gx[0]) * SCALE;
    const bw = (b.max[2] - b.min[2]) * SCALE, bh = (b.max[0] - b.min[0]) * SCALE;
    rects += `<rect x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${bw.toFixed(1)}" height="${bh.toFixed(1)}" fill="${fill}" stroke="${stroke}" stroke-width="1" opacity="0.85"/>`;
  });
  return { w, h, rects };
}
function svgSide() {
  const w = dims.lengthZ * SCALE, h = dims.heightY * SCALE;
  let rects = "";
  boxes.forEach(b => {
    const { fill, stroke } = colorFor(b.role, b.part_id);
    const x = (gz[1] - b.max[2]) * SCALE, y = h - (b.max[1] - gy[0]) * SCALE;
    const bw = (b.max[2] - b.min[2]) * SCALE, bh = (b.max[1] - b.min[1]) * SCALE;
    rects += `<rect x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${bw.toFixed(1)}" height="${bh.toFixed(1)}" fill="${fill}" stroke="${stroke}" stroke-width="1" opacity="0.85"/>`;
  });
  return { w, h, rects };
}
const top = svgTop(), side = svgSide();
fs.writeFileSync(`/opt/konfigurator/scripts/tmp_2026-08-31_batch_${KEY}_svg.json`, JSON.stringify({ top, side, dims }, null, 1));

// sanity gate: rozumne rozmery (vyska ~1170-1190mm, hloubka ~320-330mm)
const okH = dims.heightY > 1100 && dims.heightY < 1250;
const okD = dims.depthX > 300 && dims.depthX < 350;
console.log(KEY, "GATE heightY_ok=", okH, "depthX_ok=", okD);
if (!okH || !okD) { console.error(KEY, "SANITY GATE FAILED"); process.exit(1); }
