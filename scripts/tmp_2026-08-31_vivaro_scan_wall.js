const fs = require("fs");
const { collidesWithWalls, buildLegObject } = require("/opt/konfigurator/scripts/tmp_2026-08-31_place_vivaro.js");
const { buildVyrezAtDepth, buildPlainAtDepth } = require("/opt/konfigurator/scripts/tmp_2026-08-30_build_depth_variants_both.js");

const step1 = JSON.parse(fs.readFileSync("/opt/konfigurator/scripts/tmp_2026-08-31_vivaro_step1_result.json", "utf8"));
const { offsetX, offsetY, D, T } = step1;

function toWorld(parts, anchorZ) {
  return parts.map(p => ({
    part_id: "Object_7",
    position: [offsetX - p.position[0], p.position[1] + offsetY, anchorZ + p.position[2]],
    quaternion: p.quaternion,
    scale: p.scale,
    role: p.role,
  }));
}
const vyrezParts = buildVyrezAtDepth(D);
const plainParts = buildPlainAtDepth(D);
function vyrezAt(anchorZ) { return buildLegObject(toWorld(vyrezParts, anchorZ)); }
function plainAt(anchorZ) { return buildLegObject(toWorld(plainParts, anchorZ)); }

console.log("scan VYREZ leg (coarse 10mm) from anchorZ=-2373 (bulkhead) up to +150 (open end):");
let zones = [];
let prev = null;
for (let z = -2373; z <= 150; z += 10) {
  const c = collidesWithWalls(vyrezAt(z));
  if (prev === null || c !== prev) { zones.push({ z, collides: c }); prev = c; }
}
console.log(JSON.stringify(zones, null, 1));

console.log("\nscan PLAIN leg (coarse 10mm) same range, for comparison:");
let zones2 = [];
prev = null;
for (let z = -2373; z <= 150; z += 10) {
  const c = collidesWithWalls(plainAt(z));
  if (prev === null || c !== prev) { zones2.push({ z, collides: c }); prev = c; }
}
console.log(JSON.stringify(zones2, null, 1));
