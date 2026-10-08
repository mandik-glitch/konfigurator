const THREE = require("three");
const fs = require("fs");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const KAT = "/opt/konfigurator/webapp/katalog/";
function glbFor(id) {
  if (id === "Object_7") return KAT + "Object_7.glb";
  if (id === "product_3071") return KAT + "product_3071.glb";
  const map = { product_3788: 120, product_3793: 170, product_3794: 220, product_3795: 270 };
  if (map[id]) return KAT + id + ".glb";
  throw new Error("unk " + id);
}
const rack = JSON.parse(fs.readFileSync("/opt/konfigurator/scripts/tmp_2026-08-31_vivaro_full_rack.json", "utf8"));
const boxes = rack.map(p => {
  const m = parseGlbMesh(glbFor(p.part_id));
  m.position.set(...p.position); m.quaternion.set(...p.quaternion); m.scale.set(...p.scale);
  m.updateMatrixWorld(true);
  const b = new THREE.Box3().setFromObject(m);
  return { role: p.role, part_id: p.part_id, min: [b.min.x, b.min.y, b.min.z], max: [b.max.x, b.max.y, b.max.z] };
});
fs.writeFileSync("/opt/konfigurator/scripts/tmp_2026-08-31_vivaro_rack_boxes.json", JSON.stringify(boxes, null, 1));

const zAll = boxes.map(b => [b.min[2], b.max[2]]).flat();
const xAll = boxes.map(b => [b.min[0], b.max[0]]).flat();
const yAll = boxes.map(b => [b.min[1], b.max[1]]).flat();
const zMin = Math.min(...zAll), zMax = Math.max(...zAll);
const xMin = Math.min(...xAll), xMax = Math.max(...xAll);
const yMin = Math.min(...yAll), yMax = Math.max(...yAll);

const EUROBOX_COLOR = { product_3788: ["--c-box-120", "--c-box-120-line"], product_3793: ["--c-box-170", "--c-box-170-line"], product_3794: ["--c-box-220", "--c-box-220-line"], product_3795: ["--c-box-270", "--c-box-270-line"] };
function colorFor(role, part_id) {
  if (EUROBOX_COLOR[part_id]) return { fill: `var(${EUROBOX_COLOR[part_id][0]})`, stroke: `var(${EUROBOX_COLOR[part_id][1]})` };
  if (part_id === "product_3071") return { fill: "var(--c-cap)", stroke: "var(--c-cap-line)" };
  if (role.startsWith("nosnik") || role.startsWith("spojnice")) return { fill: "var(--c-rail)", stroke: "var(--c-rail-line)" };
  return { fill: "var(--c-leg)", stroke: "var(--c-leg-line)" };
}
const SCALE = 0.42;
function svgTop() {
  const w = (zMax - zMin) * SCALE, h = (xMax - xMin) * SCALE;
  let rects = "";
  boxes.forEach(b => {
    const { fill, stroke } = colorFor(b.role, b.part_id);
    const x = (b.min[2] - zMin) * SCALE, y = (b.min[0] - xMin) * SCALE;
    const bw = (b.max[2] - b.min[2]) * SCALE, bh = (b.max[0] - b.min[0]) * SCALE;
    rects += `<rect x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${bw.toFixed(1)}" height="${bh.toFixed(1)}" fill="${fill}" stroke="${stroke}" stroke-width="1" opacity="0.85"/>`;
  });
  return { w, h, rects };
}
function svgSide() {
  const w = (zMax - zMin) * SCALE, h = (yMax - yMin) * SCALE;
  let rects = "";
  // hranice fyzickeho stropu (920mm stary limit, cervene precerknute; skutecny fyzicky strop cca 922-924)
  const y920 = h - (920 - yMin) * SCALE;
  boxes.forEach(b => {
    const { fill, stroke } = colorFor(b.role, b.part_id);
    const x = (b.min[2] - zMin) * SCALE, y = h - (b.max[1] - yMin) * SCALE;
    const bw = (b.max[2] - b.min[2]) * SCALE, bh = (b.max[1] - b.min[1]) * SCALE;
    rects += `<rect x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${bw.toFixed(1)}" height="${bh.toFixed(1)}" fill="${fill}" stroke="${stroke}" stroke-width="1" opacity="0.85"/>`;
  });
  rects += `<line x1="0" y1="${y920.toFixed(1)}" x2="${w.toFixed(1)}" y2="${y920.toFixed(1)}" stroke="var(--c-ceiling-line)" stroke-width="1.5" stroke-dasharray="6 4"/>`;
  return { w, h, rects };
}
const top = svgTop(), side = svgSide();
fs.writeFileSync("/opt/konfigurator/scripts/tmp_2026-08-31_vivaro_svg_data.json", JSON.stringify({ top, side, dims: { widthX: xMax - xMin, lengthZ: zMax - zMin, heightY: yMax - yMin } }, null, 1));
console.log("hotovo", { widthX: xMax - xMin, lengthZ: zMax - zMin, heightY: yMax - yMin });
