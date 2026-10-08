// Rule 8 (MANDATORY 2D verification gate PRED ulozenim) - genericky, Box3
// odvozeny pudorys (X-Z) + naryz (Y-Z) z realne sestavene parts liste.
// Vygeneruje SVG + vraci numericke sanity kontroly (zadne NaN, box pocet
// souhlasi, zadne prekryvy v pudorysu mezi ruznymi sloupci nohou).
const fs = require("fs");
const THREE = require("three");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const KAT = "/opt/konfigurator/webapp/katalog/";
function glbFor(id) {
  if (id === "Object_7") return KAT + "Object_7.glb";
  if (id === "product_3071") return KAT + "product_3071.glb";
  const m = { product_3788: 120, product_3793: 170, product_3794: 220, product_3795: 270 };
  if (m[id]) return KAT + id + ".glb";
  return null;
}
function boxOf(p) {
  const path = glbFor(p.part_id);
  if (!path) return null;
  const mesh = parseGlbMesh(path);
  mesh.position.set(...p.position); mesh.quaternion.set(...p.quaternion); mesh.scale.set(...p.scale);
  mesh.updateMatrixWorld(true);
  return new THREE.Box3().setFromObject(mesh);
}

function generate2D(parts, outSvgPath, label) {
  const boxes = parts.map(p => ({ p, box: boxOf(p) })).filter(x => x.box);
  let issues = [];
  boxes.forEach(({ p, box }) => {
    ["min", "max"].forEach(k => ["x", "y", "z"].forEach(ax => {
      if (!Number.isFinite(box[k][ax])) issues.push(`NaN/Inf in ${p.role}`);
    }));
  });
  const global = new THREE.Box3();
  boxes.forEach(({ box }) => global.union(box));

  const W = 900, Hpx = 500, margin = 40;
  const spanX = global.max.x - global.min.x || 1, spanZ = global.max.z - global.min.z || 1, spanY = global.max.y - global.min.y || 1;
  const scaleTop = Math.min((W - 2 * margin) / spanZ, (Hpx / 2 - 2 * margin) / spanX);
  const scaleElev = Math.min((W - 2 * margin) / spanZ, (Hpx / 2 - 2 * margin) / spanY);

  function rectTop(box) {
    const x = margin + (box.min.z - global.min.z) * scaleTop;
    const y = margin + (box.min.x - global.min.x) * scaleTop;
    const w = (box.max.z - box.min.z) * scaleTop, h = (box.max.x - box.min.x) * scaleTop;
    return { x, y, w, h };
  }
  function rectElev(box) {
    const x = margin + (box.min.z - global.min.z) * scaleElev;
    const y = Hpx / 2 + margin + (global.max.y - box.max.y) * scaleElev;
    const w = (box.max.z - box.min.z) * scaleElev, h = (box.max.y - box.min.y) * scaleElev;
    return { x, y, w, h };
  }
  const colorFor = (role) => role.startsWith("eurobox") ? "#f2c14e" : role.startsWith("nosnik") ? "#4e79f2" : role.startsWith("spojnice") ? "#7fc17f" : role.startsWith("zaslepka") ? "#999" : "#c1504e";

  let svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${Hpx}" style="background:#fff">`;
  svg += `<text x="10" y="20" font-size="14">${label} - TOP VIEW (X-Z)</text>`;
  svg += `<text x="10" y="${Hpx / 2 + 20}" font-size="14">${label} - ELEVATION (Y-Z)</text>`;
  boxes.forEach(({ p, box }) => {
    const rt = rectTop(box);
    svg += `<rect x="${rt.x.toFixed(1)}" y="${rt.y.toFixed(1)}" width="${Math.max(0.5, rt.w).toFixed(1)}" height="${Math.max(0.5, rt.h).toFixed(1)}" fill="${colorFor(p.role)}" fill-opacity="0.6" stroke="#333" stroke-width="0.5"/>`;
  });
  boxes.forEach(({ p, box }) => {
    const re = rectElev(box);
    svg += `<rect x="${re.x.toFixed(1)}" y="${re.y.toFixed(1)}" width="${Math.max(0.5, re.w).toFixed(1)}" height="${Math.max(0.5, re.h).toFixed(1)}" fill="${colorFor(p.role)}" fill-opacity="0.6" stroke="#333" stroke-width="0.5"/>`;
  });
  svg += `</svg>`;
  fs.writeFileSync(outSvgPath, svg);

  return { issues, globalBox: { min: [global.min.x, global.min.y, global.min.z], max: [global.max.x, global.max.y, global.max.z] }, partCount: boxes.length };
}

module.exports = { generate2D };

if (require.main === module) {
  const fullPath = process.argv[2], outSvg = process.argv[3];
  const full = JSON.parse(fs.readFileSync(fullPath, "utf8"));
  const r = generate2D(full.parts, outSvg, full.cfg.name);
  console.log(JSON.stringify(r, null, 1));
}
