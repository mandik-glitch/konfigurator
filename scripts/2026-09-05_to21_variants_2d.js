// TO21 - narys (Y-Z) 3 variant mixu vysek boxu z REALNE GLB geometrie.
// Pro kazdou variantu: Box3 kazdeho dilu -> SVG narys s kotami vysek.
// bot22 2026-09-05. Vystup: JSON s {variant: {svg, summary}} na stdout-file.
const fs = require("fs");
const THREE = require("three");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const KAT = "/opt/konfigurator/webapp/katalog/";
const BOXH = { product_3788: 120, product_3793: 170, product_3794: 220, product_3795: 270 };
function glbFor(id) {
  if (id === "Object_7") return KAT + "Object_7.glb";
  if (id === "product_3071") return KAT + "product_3071.glb";
  if (BOXH[id]) return KAT + id + ".glb";
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
function roleClass(role) {
  if (role.startsWith("eurobox")) return "box";
  if (role.startsWith("nosnik") || role.startsWith("spojnice-sloupec")) return "rail";
  if (role.includes("svislice") || role.includes("sloupek")) return "leg";
  if (role.includes("cap")) return "cap";
  if (role.includes("pricka") || role.startsWith("spojnice-")) return "leg";
  if (role.includes("zaslepka")) return "cap";
  return "other";
}
const COL = { box: "#e8a13a", rail: "#5b6b7a", leg: "#39424c", cap: "#8a97a4", other: "#c8cdd2" };

function buildSvg(parts, label) {
  const items = parts.map(p => ({ p, box: boxOf(p) })).filter(x => x.box && isFinite(x.box.min.y));
  let minZ = Infinity, maxZ = -Infinity, minY = Infinity, maxY = -Infinity;
  items.forEach(({ box }) => { minZ = Math.min(minZ, box.min.z); maxZ = Math.max(maxZ, box.max.z); minY = Math.min(minY, box.min.y); maxY = Math.max(maxY, box.max.y); });
  const padL = 70, padR = 20, padT = 30, padB = 40;
  const spanZ = maxZ - minZ, spanY = maxY - minY;
  const scale = 620 / spanZ;               // px per mm (fit width)
  const Wpx = padL + spanZ * scale + padR;
  const Hpx = padT + spanY * scale + padB;
  // narys: Z vodorovne (delka auta), Y svisle (nahoru). SVG y roste dolu -> flip.
  const X = z => padL + (z - minZ) * scale;
  const Yp = y => padT + (maxY - y) * scale;
  let s = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${Wpx.toFixed(0)} ${Hpx.toFixed(0)}" width="100%" style="max-width:${Wpx.toFixed(0)}px">`;
  s += `<rect x="0" y="0" width="${Wpx.toFixed(0)}" height="${Hpx.toFixed(0)}" fill="#fbfbf9"/>`;
  // podlaha (spodni hrana)
  s += `<line x1="${padL}" y1="${Yp(minY).toFixed(1)}" x2="${(Wpx-padR).toFixed(1)}" y2="${Yp(minY).toFixed(1)}" stroke="#bbb" stroke-width="1"/>`;
  // dily zezadu dopredu: leg/cap/rail pak box (box navrch, poloprusvitny)
  const order = { leg: 0, cap: 1, rail: 2, other: 1, box: 3 };
  items.sort((a, b) => order[roleClass(a.p.role)] - order[roleClass(b.p.role)]);
  items.forEach(({ p, box }) => {
    const cls = roleClass(p.role);
    const x = X(box.min.z), y = Yp(box.max.y), w = (box.max.z - box.min.z) * scale, h = (box.max.y - box.min.y) * scale;
    const op = cls === "box" ? 0.55 : 0.9;
    s += `<rect x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${Math.max(1, w).toFixed(1)}" height="${Math.max(1, h).toFixed(1)}" fill="${COL[cls]}" fill-opacity="${op}" stroke="#2a2f34" stroke-width="0.6"/>`;
    if (cls === "box") {
      const bh = BOXH[p.part_id];
      if (w > 26 && h > 16) s += `<text x="${(x + w / 2).toFixed(1)}" y="${(y + h / 2 + 5).toFixed(1)}" font-size="13" font-family="system-ui" text-anchor="middle" fill="#4a2f00" font-weight="600">${bh}</text>`;
    }
  });
  // kota celkove vysky vpravo
  s += `<text x="8" y="${padT + 4}" font-size="11" fill="#666">mm</text>`;
  s += `</svg>`;
  return { svg: s, minY, maxY, minZ, maxZ };
}

const varData = {};
for (const V of ["A", "B", "C"]) {
  const d = JSON.parse(fs.readFileSync(`/tmp/to21_var_${V}.json`, "utf8"));
  const { svg, minY, maxY } = buildSvg(d.parts, V);
  const boxes = d.parts.filter(p => (p.role || "").startsWith("eurobox"));
  const heights = boxes.map(p => BOXH[p.part_id]).sort((a, b) => b - a);
  const cnt = {}; heights.forEach(h => cnt[h] = (cnt[h] || 0) + 1);
  varData[V] = {
    svg,
    totalBoxes: d.totalBoxes,
    distinctHeights: d.distinctHeights,
    unexpected: d.unexpected, badPairs: (Array.isArray(d.badPairs) ? d.badPairs.length : d.badPairs),
    columnSummaries: d.columnSummaries.map(c => ({ col: c.colIdx, N: c.N, boxHeights: c.boxHeights })),
    heightCounts: cnt,
    heightMm: Math.round(maxY - minY),
  };
}
fs.writeFileSync("/tmp/to21_variants_2d.json", JSON.stringify(varData, null, 1));
console.log("OK - narysy vygenerovany:", Object.keys(varData).map(v => `${v}(${varData[v].totalBoxes}box, ${varData[v].heightMm}mm, kolize=${varData[v].unexpected})`).join("  "));
