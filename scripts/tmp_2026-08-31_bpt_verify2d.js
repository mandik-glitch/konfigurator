// Krok 8 (MANDATORY GATE): 2D kontrolni mereni pred ulozenim. Pro danou
// sestavu (tmp_out_<tag>_parts.json) spocita SKUTECNY Box3 (real GLB
// geometrie) kazdeho dilu, provede numericke sanity kontroly a vygeneruje
// SVG data (pudorys + naryz) pro vizualni kontrolu. Pokud kterakoli
// kontrola selze, skript skonci chybou (nic se neuklada do DB).
const fs = require("fs");
const THREE = require("three");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const KAT = "/opt/konfigurator/webapp/katalog/";
const EUROBOX_GLB = { product_3788: KAT + "product_3788.glb", product_3793: KAT + "product_3793.glb", product_3794: KAT + "product_3794.glb", product_3795: KAT + "product_3795.glb" };
function glbFor(id) {
  if (id === "Object_7") return KAT + "Object_7.glb";
  if (id === "product_3071") return KAT + "product_3071.glb";
  if (EUROBOX_GLB[id]) return EUROBOX_GLB[id];
  throw new Error("neznamy part_id " + id);
}

const tag = process.argv[2];
const parts = JSON.parse(fs.readFileSync(`/tmp/bpt_out_${tag}_parts.json`, "utf8"));

const boxes = parts.map(p => {
  const m = parseGlbMesh(glbFor(p.part_id));
  m.position.set(...p.position); m.quaternion.set(...p.quaternion); m.scale.set(...p.scale);
  m.updateMatrixWorld(true);
  const b = new THREE.Box3().setFromObject(m);
  return { role: p.role, part_id: p.part_id, min: [b.min.x, b.min.y, b.min.z], max: [b.max.x, b.max.y, b.max.z] };
});

const errors = [];
// 1) zadny NaN/degenerovany box
boxes.forEach(b => {
  if ([...b.min, ...b.max].some(v => !Number.isFinite(v))) errors.push(`NaN box: ${b.role}`);
  if (b.max[0] <= b.min[0] || b.max[1] <= b.min[1] || b.max[2] <= b.min[2]) errors.push(`degenerovany box: ${b.role}`);
});
// 2) vsechny nohy (Object_7 profily) zacinaji na podlaze (min.y ~ floor uroven, tolerance 5mm) - jen predni/zadni svislice
const legBoxes = boxes.filter(b => b.part_id === "Object_7" && /svislice/.test(b.role));
const floorY = Math.min(...legBoxes.map(b => b.min[1]));
legBoxes.forEach(b => { if (b.min[1] - floorY > 5.01) errors.push(`svislice ${b.role} nezacina na podlaze (min.y=${b.min[1].toFixed(1)}, floor=${floorY.toFixed(1)})`); });
// 3) euroboxy nemaji zaporny prekryv mezi sebou v ramci stejneho patra (uz reseno v run_vehicle.js sebekolizni kontrole, tady jen rozmerova kontrola boxu)
const euroBoxes = boxes.filter(b => Object.keys(EUROBOX_GLB).includes(b.part_id));
euroBoxes.forEach(b => {
  const h = b.max[1] - b.min[1];
  if (h < 100 || h > 300) errors.push(`eurobox ${b.role} ma podezrelou vysku ${h.toFixed(1)}mm`);
});
// 4) rack celkova delka (Z) a hloubka (X) v rozumnych mezich (>0, < 6000mm)
const allZ = boxes.flatMap(b => [b.min[2], b.max[2]]);
const allX = boxes.flatMap(b => [b.min[0], b.max[0]]);
const allY = boxes.flatMap(b => [b.min[1], b.max[1]]);
const zMin = Math.min(...allZ), zMax = Math.max(...allZ);
const xMin = Math.min(...allX), xMax = Math.max(...allX);
const yMin = Math.min(...allY), yMax = Math.max(...allY);
const dims = { lengthZ: zMax - zMin, depthX: xMax - xMin, heightY: yMax - yMin };
if (dims.lengthZ <= 0 || dims.lengthZ > 6000) errors.push(`podezrela celkova delka ${dims.lengthZ}`);
if (dims.depthX <= 0 || dims.depthX > 500) errors.push(`podezrela hloubka ${dims.depthX} (ocekavano ~349)`);
if (dims.heightY <= 0 || dims.heightY > 2000) errors.push(`podezrela vyska ${dims.heightY}`);

// SVG data (pudorys Z x X, naryz Z x Y)
const SCALE = 0.3;
function colorFor(role, part_id) {
  if (Object.keys(EUROBOX_GLB).includes(part_id)) return { fill: "#f2c14e", stroke: "#a67c00" };
  if (part_id === "product_3071") return { fill: "#999", stroke: "#555" };
  if (/nosnik|spojnice/.test(role)) return { fill: "#8ecae6", stroke: "#1b6ca8" };
  return { fill: "#adb5bd", stroke: "#495057" };
}
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
  boxes.forEach(b => {
    const { fill, stroke } = colorFor(b.role, b.part_id);
    const x = (b.min[2] - zMin) * SCALE, y = h - (b.max[1] - yMin) * SCALE;
    const bw = (b.max[2] - b.min[2]) * SCALE, bh = (b.max[1] - b.min[1]) * SCALE;
    rects += `<rect x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${bw.toFixed(1)}" height="${bh.toFixed(1)}" fill="${fill}" stroke="${stroke}" stroke-width="1" opacity="0.85"/>`;
  });
  return { w, h, rects };
}
const top = svgTop(), side = svgSide();
const svgDoc = `<svg xmlns="http://www.w3.org/2000/svg" width="${Math.max(top.w, side.w) + 20}" height="${top.h + side.h + 60}">
<text x="5" y="15" font-size="12">Pudorys (top) - ${tag}</text>
<g transform="translate(10,20)">${top.rects}</g>
<text x="5" y="${top.h + 40}" font-size="12">Naryz (side) - ${tag}</text>
<g transform="translate(10,${top.h + 45})">${side.rects}</g>
</svg>`;
fs.writeFileSync(`/tmp/bpt_svg_${tag}.svg`, svgDoc);

const result = { tag, dims, errors, ok: errors.length === 0, boxCount: boxes.length };
fs.writeFileSync(`/tmp/bpt_verify2d_${tag}.json`, JSON.stringify(result, null, 1));
console.log(JSON.stringify(result));
if (errors.length) process.exit(1);
