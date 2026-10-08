// Audit script (bot16, 2026-09-01): scan all is_public=1 product_assemblies
// eurobox racks for two structural defects Robert reported ("stale jsou tam
// nedokonalosti, nekde chybi pricky, nekde jsem videl vetsi mezeru nez
// 30mm"):
//   (a) missing crossbar (spojnice) connectors at a shelf level
//   (b) gap between a box top and the next level's rail bottom != 30mm
// Uses REAL geometry (Box3 from actual GLB parts via parseGlbMesh), not
// stored role/name fields, per task instructions - roles vary in naming
// convention across last night's batch-agents.
//
// Input: JSON file [{id, parts:[...]}, ...] (one entry per product_assemblies row)
// Output: JSON report to stdout.

const fs = require("fs");
const THREE = require("three");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const KAT = "/opt/konfigurator/webapp/katalog/";

const inputPath = process.argv[2];
const rows = JSON.parse(fs.readFileSync(inputPath, "utf8"));

const meshCache = {};
function getBox3(part) {
  if (!meshCache[part.part_id]) {
    meshCache[part.part_id] = parseGlbMesh(KAT + part.part_id + ".glb");
  }
  const m = meshCache[part.part_id];
  m.position.set(part.position[0], part.position[1], part.position[2]);
  m.quaternion.set(part.quaternion[0], part.quaternion[1], part.quaternion[2], part.quaternion[3]);
  m.scale.set(part.scale[0], part.scale[1], part.scale[2]);
  m.updateMatrixWorld(true);
  return new THREE.Box3().setFromObject(m);
}

function round(v, step) {
  return Math.round(v / step) * step;
}

// Expected crossbar count for a column of clear span S (mm), per
// shape_geometry_methods.id=3 rule: first/last connector 15mm from rail
// ends (T/2), internal connectors every ~401mm. Generalizes beyond the 3
// canonical spans (430/832/1232 -> 2/3/4) to any span.
function expectedConnCount(span) {
  return Math.max(2, Math.round((span - 30) / 401) + 1);
}

function expectedOffsets(span) {
  const n = expectedConnCount(span);
  const offs = [15];
  for (let i = 1; i < n - 1; i++) offs.push(round(15 + i * ((span - 30) / (n - 1)), 1));
  if (n > 1) offs.push(span - 15);
  return offs;
}

const report = { rows: [] };

for (const row of rows) {
  const parts = row.parts;
  const profileParts = [];
  for (let idx = 0; idx < parts.length; idx++) {
    const p = parts[idx];
    if (p.part_id !== "Object_7") continue;
    let box;
    try {
      box = getBox3(p);
    } catch (e) {
      continue;
    }
    const dx = box.max.x - box.min.x, dy = box.max.y - box.min.y, dz = box.max.z - box.min.z;
    let dom = "y";
    if (dx >= dy && dx >= dz) dom = "x";
    else if (dz >= dy && dz >= dx) dom = "z";
    profileParts.push({
      idx, p, box, dx, dy, dz, dom,
      cx: (box.min.x + box.max.x) / 2,
      cy: (box.min.y + box.max.y) / 2,
      cz: (box.min.z + box.max.z) / 2,
    });
  }

  // Eurobox parts (actual real geometry, top surface = box.max.y)
  const boxParts = [];
  for (let idx = 0; idx < parts.length; idx++) {
    const p = parts[idx];
    if (!/^product_37(8[0-9]|9[0-9])$/.test(p.part_id)) continue;
    let box;
    try {
      box = getBox3(p);
    } catch (e) {
      continue;
    }
    boxParts.push({
      idx, p, box,
      cx: (box.min.x + box.max.x) / 2,
      cz: (box.min.z + box.max.z) / 2,
      dy: box.max.y - box.min.y,
    });
  }

  // rails: dominant Z, length > 100mm (excludes leg verticals & short bits)
  const rails = profileParts.filter(pp => pp.dom === "z" && pp.dz > 100);
  // x-runners: dominant X, length > 100mm (shelf crossbars + leg-internal spojnice-dolni/horni)
  const xrunners = profileParts.filter(pp => pp.dom === "x" && pp.dx > 100);

  // group rails into "levels": same Y band (round 3mm) + same Z-span (round 5mm at each end)
  const levelMap = new Map();
  for (const r of rails) {
    const key = round(r.cy, 3) + "|" + round(r.box.min.z, 5) + "|" + round(r.box.max.z, 5);
    if (!levelMap.has(key)) levelMap.set(key, []);
    levelMap.get(key).push(r);
  }
  const levels = [];
  for (const [key, members] of levelMap.entries()) {
    const y = members.reduce((a, b) => a + b.cy, 0) / members.length;
    const zMin = members.reduce((a, b) => Math.min(a, b.box.min.z), Infinity);
    const zMax = members.reduce((a, b) => Math.max(a, b.box.max.z), -Infinity);
    const railBottomY = members.reduce((a, b) => Math.min(a, b.box.min.y), Infinity);
    const railTopY = members.reduce((a, b) => Math.max(a, b.box.max.y), -Infinity);
    levels.push({ y, zMin, zMax, span: zMax - zMin, railBottomY, railTopY, railCount: members.length, members });
  }

  // group levels into columns by (zMin,zMax) rounded to 5mm cluster
  const colMap = new Map();
  for (const lv of levels) {
    const key = round(lv.zMin, 8) + "|" + round(lv.zMax, 8);
    if (!colMap.has(key)) colMap.set(key, []);
    colMap.get(key).push(lv);
  }

  const rowReport = { id: row.id, columns: [], violations: [] };
  let colIdx = 0;
  for (const [key, colLevels] of colMap.entries()) {
    colLevels.sort((a, b) => a.y - b.y);
    const zMin = colLevels.reduce((a, b) => Math.min(a, b.zMin), Infinity);
    const zMax = colLevels.reduce((a, b) => Math.max(a, b.zMax), -Infinity);
    const span = zMax - zMin;
    const expected = expectedConnCount(span);
    const colReport = { colIdx, zMin, zMax, span, expectedConn: expected, levels: [] };

    colLevels.forEach((lv, patroIdx) => {
      // actual crossbars: x-runner centered in Y at this level, cz strictly inside (zMin,zMax) margin 8mm
      const conns = xrunners.filter(x => Math.abs(x.cy - lv.y) < 20 && x.cz > lv.zMin + 8 && x.cz < lv.zMax - 8);
      const connOffsets = conns.map(c => +(c.cz - lv.zMin).toFixed(1)).sort((a, b) => a - b);
      const expOffs = expectedOffsets(lv.span);

      // box(es) sitting on this level: cz within [zMin,zMax], box bottom near railTopY (within 40mm, nesting -12mm)
      const boxesHere = boxParts.filter(b => b.cz > lv.zMin - 5 && b.cz < lv.zMax + 5 && b.box.min.y > lv.railTopY - 40 && b.box.min.y < lv.railTopY + 20);
      const boxTopY = boxesHere.length ? Math.max(...boxesHere.map(b => b.box.max.y)) : null;

      const lvReport = {
        patroIdx, y: lv.y, zMin: lv.zMin, zMax: lv.zMax, span: lv.span,
        railBottomY: lv.railBottomY, railTopY: lv.railTopY, railCount: lv.railCount,
        expectedConn: expectedConnCount(lv.span), actualConn: conns.length,
        connOffsets, expOffsets: expOffs,
        nBoxes: boxesHere.length, boxTopY,
      };
      colReport.levels.push(lvReport);

      if (lv.railCount !== 2) {
        rowReport.violations.push({ type: "rail_count_anomaly", colIdx, patroIdx, railCount: lv.railCount });
      }
      if (conns.length < expectedConnCount(lv.span)) {
        rowReport.violations.push({
          type: "missing_crossbar", colIdx, patroIdx,
          expected: expectedConnCount(lv.span), actual: conns.length,
          missing: expectedConnCount(lv.span) - conns.length,
          span: lv.span, y: lv.y, zMin: lv.zMin, zMax: lv.zMax,
          connOffsets, expOffsets: expOffs,
        });
      }
    });

    // gap check between consecutive levels
    for (let i = 0; i < colReport.levels.length - 1; i++) {
      const cur = colReport.levels[i], next = colReport.levels[i + 1];
      if (cur.boxTopY == null) {
        rowReport.violations.push({ type: "no_box_for_gap_check", colIdx, patroIdx: i });
        continue;
      }
      const gap = next.railBottomY - cur.boxTopY;
      if (Math.abs(gap - 30) > 1) {
        rowReport.violations.push({
          type: "gap_violation", colIdx, fromPatro: i, toPatro: i + 1,
          gap: +gap.toFixed(2), boxTopY: cur.boxTopY, nextRailBottomY: next.railBottomY,
        });
      }
    }

    rowReport.columns.push(colReport);
    colIdx++;
  }

  report.rows.push(rowReport);
}

console.log(JSON.stringify(report));
