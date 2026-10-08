// Computes the Y-shift fix for the universal 30mm-gap violation found by
// tmp_2026-09-01_bot16_crossbar_gap_audit.js (bot16, 2026-09-01).
//
// Root cause (reverse-engineered from real geometry, see AGENTS_LOG.md):
// the level-spacing formula used to build last night's batch added the
// eurobox's FULL declared height when computing the next level's rail Y,
// but the box's real visible height above the rail top is declared height
// MINUS the ~12mm nesting foot (shape_geometry_methods.id=3, step 4/5) -
// producing a uniform +12mm-too-big gap at EVERY transition. A second,
// separate bug (found in some B/C-variant rows) additionally used the
// WRONG box height for some levels, adding up to +50mm extra on top.
//
// Fix approach (matches task instructions): don't try to "undo" the
// wrong formula. Instead, walk each column bottom-up and, using the
// REAL measured box-top Y of the (already-corrected) level below,
// recompute the correct rail Y for this level = boxTopY_below + 30 + T.
// Shift this level's rails+connectors+its own eurobox rigidly by the
// resulting delta, then continue upward (cascading) - this is correct
// regardless of which of the two bugs (or both) caused a given gap.
//
// Output: JSON [{id, deltas:[{colIdx,patroIdx,delta,partIdx:[...]}], ...}]
// Does NOT write to DB - a separate apply step does that after review.

const fs = require("fs");
const THREE = require("three");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const KAT = "/opt/konfigurator/webapp/katalog/";

const inputPath = process.argv[2];
const rows = JSON.parse(fs.readFileSync(inputPath, "utf8"));

const meshCache = {};
function getBox3(part) {
  if (!meshCache[part.part_id]) meshCache[part.part_id] = parseGlbMesh(KAT + part.part_id + ".glb");
  const m = meshCache[part.part_id];
  m.position.set(part.position[0], part.position[1], part.position[2]);
  m.quaternion.set(part.quaternion[0], part.quaternion[1], part.quaternion[2], part.quaternion[3]);
  m.scale.set(part.scale[0], part.scale[1], part.scale[2]);
  m.updateMatrixWorld(true);
  return new THREE.Box3().setFromObject(m);
}

function round(v, step) { return Math.round(v / step) * step; }

const GAP_TARGET = 30;
const output = { rows: [] };

for (const row of rows) {
  const parts = row.parts;
  const profileParts = [];
  for (let idx = 0; idx < parts.length; idx++) {
    const p = parts[idx];
    if (p.part_id !== "Object_7") continue;
    const box = getBox3(p);
    const dx = box.max.x - box.min.x, dy = box.max.y - box.min.y, dz = box.max.z - box.min.z;
    let dom = "y";
    if (dx >= dy && dx >= dz) dom = "x"; else if (dz >= dy && dz >= dx) dom = "z";
    profileParts.push({ idx, box, dx, dy, dz, dom, cy: (box.min.y + box.max.y) / 2, cz: (box.min.z + box.max.z) / 2 });
  }
  const boxParts = [];
  for (let idx = 0; idx < parts.length; idx++) {
    const p = parts[idx];
    if (!/^product_37(8[0-9]|9[0-9])$/.test(p.part_id)) continue;
    const box = getBox3(p);
    boxParts.push({ idx, box, cz: (box.min.z + box.max.z) / 2 });
  }

  const rails = profileParts.filter(pp => pp.dom === "z" && pp.dz > 100);
  const xrunners = profileParts.filter(pp => pp.dom === "x" && pp.dx > 100);

  const levelMap = new Map();
  for (const r of rails) {
    const key = round(r.cy, 3) + "|" + round(r.box.min.z, 5) + "|" + round(r.box.max.z, 5);
    if (!levelMap.has(key)) levelMap.set(key, []);
    levelMap.get(key).push(r);
  }
  const levels = [];
  for (const members of levelMap.values()) {
    const y = members.reduce((a, b) => a + b.cy, 0) / members.length;
    const zMin = members.reduce((a, b) => Math.min(a, b.box.min.z), Infinity);
    const zMax = members.reduce((a, b) => Math.max(a, b.box.max.z), -Infinity);
    const railBottomY = members.reduce((a, b) => Math.min(a, b.box.min.y), Infinity);
    const railTopY = members.reduce((a, b) => Math.max(a, b.box.max.y), -Infinity);
    const railIdx = members.map(m => m.idx);
    levels.push({ y, zMin, zMax, railBottomY, railTopY, railIdx, T: railTopY - railBottomY });
  }

  const colMap = new Map();
  for (const lv of levels) {
    const key = round(lv.zMin, 8) + "|" + round(lv.zMax, 8);
    if (!colMap.has(key)) colMap.set(key, []);
    colMap.get(key).push(lv);
  }

  const rowOut = { id: row.id, columns: [] };
  let colIdx = 0;
  for (const colLevels of colMap.values()) {
    colLevels.sort((a, b) => a.y - b.y);
    const zMin = colLevels.reduce((a, b) => Math.min(a, b.zMin), Infinity);
    const zMax = colLevels.reduce((a, b) => Math.max(a, b.zMax), -Infinity);

    // attach connectors + boxes to each level
    colLevels.forEach(lv => {
      const conns = xrunners.filter(x => Math.abs(x.cy - lv.y) < 20 && x.cz > lv.zMin + 8 && x.cz < lv.zMax - 8);
      lv.connIdx = conns.map(c => c.idx);
      const boxesHere = boxParts.filter(b => b.cz > lv.zMin - 5 && b.cz < lv.zMax + 5 && b.box.min.y > lv.railTopY - 40 && b.box.min.y < lv.railTopY + 20);
      lv.boxIdx = boxesHere.map(b => b.idx);
      lv.boxTopY = boxesHere.length ? Math.max(...boxesHere.map(b => b.box.max.y)) : null;
    });

    const colOut = { colIdx, zMin, zMax, levels: [] };
    const delta = new Array(colLevels.length).fill(0);
    for (let i = 0; i < colLevels.length - 1; i++) {
      const cur = colLevels[i], next = colLevels[i + 1];
      const curBoxTopShifted = cur.boxTopY == null ? null : cur.boxTopY + delta[i];
      let d = 0, note = "";
      if (curBoxTopShifted == null) {
        note = "NO_BOX_ON_LEVEL_BELOW - cannot compute correct target, delta=0 (manual review needed)";
      } else {
        const correctRailBottom = curBoxTopShifted + GAP_TARGET;
        const correctRailTop = correctRailBottom + next.T;
        d = correctRailTop - next.railTopY;
      }
      delta[i + 1] = d;
      colOut.levels.push({
        patroIdx: i + 1, delta: +d.toFixed(3), note,
        origGap: cur.boxTopY == null ? null : +(next.railBottomY - cur.boxTopY).toFixed(2),
        railIdx: next.railIdx, connIdx: next.connIdx, boxIdx: next.boxIdx,
      });
    }
    // patro0 (index 0) never shifts - record for completeness with delta 0
    colOut.levels.unshift({ patroIdx: 0, delta: 0, note: "base level, unchanged", railIdx: colLevels[0].railIdx, connIdx: colLevels[0].connIdx, boxIdx: colLevels[0].boxIdx });
    rowOut.columns.push(colOut);
    colIdx++;
  }
  output.rows.push(rowOut);
}

console.log(JSON.stringify(output));
