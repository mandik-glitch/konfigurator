const THREE = require("three");
const fs = require("fs");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const KAT = "/opt/konfigurator/webapp/katalog/";
function glbFor(id) {
  if (id === "Object_7") return KAT + "Object_7.glb";
  if (id === "product_3071") return KAT + "product_3071.glb";
  if (id === "product_3788") return KAT + "product_3788.glb";
  if (id === "product_3793") return KAT + "product_3793.glb";
  if (id === "product_3794") return KAT + "product_3794.glb";
  if (id === "product_3795") return KAT + "product_3795.glb";
  return null;
}
function colorFor(role, part_id) {
  if (part_id === "product_3795") return { fill: "#c98a3e", stroke: "#8a5a1e" };
  if (part_id === "product_3794") return { fill: "#3e9ac9", stroke: "#1e5a8a" };
  if (part_id === "product_3793") return { fill: "#7ec93e", stroke: "#4a8a1e" };
  if (part_id === "product_3788") return { fill: "#c93e6a", stroke: "#8a1e40" };
  if (part_id === "product_3071") return { fill: "#999", stroke: "#555" };
  if (role.startsWith("nosnik") || role.startsWith("spojnice")) return { fill: "#bbb", stroke: "#777" };
  return { fill: "#5566aa", stroke: "#334477" };
}
const SCALE = 0.22;

const summary = JSON.parse(fs.readFileSync("/opt/konfigurator/scripts/tmp_2026-09-01_bot16_summary.json", "utf8"));
const out = {};
for (const key of Object.keys(summary)) {
  if (!summary[key].ok) continue;
  const rackPath = `/opt/konfigurator/scripts/tmp_2026-09-01_bot16_rack_${key}.json`;
  if (!fs.existsSync(rackPath)) continue;
  const rack = JSON.parse(fs.readFileSync(rackPath, "utf8"));
  const boxes = rack.map(p => {
    const g = glbFor(p.part_id);
    const m = parseGlbMesh(g);
    m.position.set(...p.position); m.quaternion.set(...p.quaternion); m.scale.set(...p.scale);
    m.updateMatrixWorld(true);
    const b = new THREE.Box3().setFromObject(m);
    return { role: p.role, part_id: p.part_id, min: [b.min.x, b.min.y, b.min.z], max: [b.max.x, b.max.y, b.max.z] };
  });
  const xAll = boxes.flatMap(b => [b.min[0], b.max[0]]);
  const yAll = boxes.flatMap(b => [b.min[1], b.max[1]]);
  const zAll = boxes.flatMap(b => [b.min[2], b.max[2]]);
  const xMin = Math.min(...xAll), xMax = Math.max(...xAll);
  const yMin = Math.min(...yAll), yMax = Math.max(...yAll);
  const zMin = Math.min(...zAll), zMax = Math.max(...zAll);

  function svgTop() {
    const w = (zMax - zMin) * SCALE, h = (xMax - xMin) * SCALE;
    let rects = "";
    boxes.forEach(b => {
      const { fill, stroke } = colorFor(b.role, b.part_id);
      const x = (zMax - b.max[2]) * SCALE, y = (xMax - b.max[0]) * SCALE;
      const bw = (b.max[2] - b.min[2]) * SCALE, bh = (b.max[0] - b.min[0]) * SCALE;
      rects += `<rect x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${bw.toFixed(1)}" height="${bh.toFixed(1)}" fill="${fill}" stroke="${stroke}" stroke-width="1" opacity="0.88"/>`;
    });
    return { w, h, rects };
  }
  function svgSide() {
    const w = (zMax - zMin) * SCALE, h = (yMax - yMin) * SCALE;
    let rects = "";
    boxes.forEach(b => {
      const { fill, stroke } = colorFor(b.role, b.part_id);
      const x = (zMax - b.max[2]) * SCALE, y = h - (b.max[1] - yMin) * SCALE;
      const bw = (b.max[2] - b.min[2]) * SCALE, bh = (b.max[1] - b.min[1]) * SCALE;
      rects += `<rect x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${bw.toFixed(1)}" height="${bh.toFixed(1)}" fill="${fill}" stroke="${stroke}" stroke-width="1" opacity="0.88"/>`;
    });
    return { w, h, rects };
  }
  out[key] = { top: svgTop(), side: svgSide(), dims: { widthX: xMax - xMin, lengthZ: zMax - zMin, heightY: yMax - yMin }, boxCount: boxes.length };
  console.log(key, "dims", (xMax - xMin).toFixed(0), (zMax - zMin).toFixed(0), (yMax - yMin).toFixed(0));
}
fs.writeFileSync("/opt/konfigurator/scripts/tmp_2026-09-01_bot16_svg_all.json", JSON.stringify(out));
console.log("done, keys:", Object.keys(out).length);
