// Rule-8 mandatory 2D (top+elevation) verification gate for the 8 new B/C variants.
const THREE = require("three");
const fs = require("fs");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const KAT = "/opt/konfigurator/webapp/katalog/";
function glbFor(id) {
  if (id === "Object_7") return KAT + "Object_7.glb";
  if (id === "product_3071") return KAT + "product_3071.glb";
  if (id.startsWith("car_body_")) return null;
  return KAT + id + ".glb";
}
const KEYS = ["MB47_B", "MB47_C", "FO31_B", "FO31_C", "VW25_B", "VW25_C", "OP31_B", "OP31_C"];
for (const KEY of KEYS) {
  const rackAll = JSON.parse(fs.readFileSync(`/opt/konfigurator/scripts/tmp_2026-09-01_bc_${KEY}_parts.json`, "utf8"));
  const rack = rackAll.filter(p => !p.part_id.startsWith("car_body_"));
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
  const okH = dims.heightY > 1100 && dims.heightY < 1300;
  const okD = dims.depthX > 300 && dims.depthX < 350;
  console.log(KEY, "dims mm:", JSON.stringify(dims), "parts=", boxes.length, "GATE heightY_ok=", okH, "depthX_ok=", okD);
  if (!okH || !okD) { console.error(KEY, "SANITY GATE FAILED"); process.exit(1); }

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
  fs.writeFileSync(`/opt/konfigurator/scripts/tmp_2026-09-01_bc_${KEY}_svg.json`, JSON.stringify({ top, side, dims }, null, 1));
}
console.log("ALL GATES PASSED");
