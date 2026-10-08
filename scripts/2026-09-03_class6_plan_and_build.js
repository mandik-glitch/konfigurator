// Class 6 fix: add missing shelves (patra) above the top of each flagged
// column, using the exact same construction convention as the rest of the
// catalog (rails/connectors copied from the existing top patro just shifted
// in Y, box position derived from the real GLB pivot via the established
// formula: ty = railYcenter + T/2 - probeLocalMinY - 12).
//
// Reads scratch/rows/<id>.json (fresh dump), the class6 audit report, and
// writes a plan + new `data.parts` per row to scratch/class6_fix/<id>.json
// (NOT written to DB by this script - a separate step does the DB write
// after review).
const fs = require("fs");
const THREE = require("three");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");

const SCRATCH = "/tmp/claude-0/-opt-domeny/40752a20-c083-499a-8fe3-7c39a4eef60b/scratchpad";
const KAT = "/opt/konfigurator/webapp/katalog/";
const T = 30;
const HEIGHT_ORDER = [270, 220, 170, 120];
const PID_BY_HEIGHT = { 270: "product_3795", 220: "product_3794", 170: "product_3793", 120: "product_3788", 320: "product_3796" };
const HEIGHT_BY_PID = { product_3795: 270, product_3794: 220, product_3793: 170, product_3788: 120, product_3796: 320 };

const audit = JSON.parse(fs.readFileSync(`${SCRATCH}/class6_full3.json`, "utf8"));

// Manual overrides: { "<rowId>_<colIdx>": [heights to add, in order] }
// id=59: Robert explicitly asked for a 170mm box here ("dej mu euroboxy
// 170mm") - but precise measurement shows only 145mm of usable budget
// (gap 205mm - 60mm mandatory rail+clearance overhead), so 170mm would
// physically collide with the real roof by ~25mm. Using 120mm instead
// (the largest that actually fits) - documented as a deviation from
// Robert's literal instruction, flagged for his decision in TASKS.md.
const OVERRIDES = {};

function localMinYAfterQuat(pid, quat) {
  const mesh = parseGlbMesh(KAT + pid + ".glb");
  mesh.position.set(0, 0, 0);
  mesh.quaternion.set(quat[0], quat[1], quat[2], quat[3]);
  mesh.scale.set(1, 1, 1);
  mesh.updateMatrixWorld(true);
  const box = new THREE.Box3().setFromObject(mesh);
  return box.min.y;
}

function planColumnAdditions(topHeight, budget) {
  const plan = [];
  let h = topHeight, b = budget;
  while (true) {
    // largest available height <= h (non-increasing rule) that fits in b
    const candidate = HEIGHT_ORDER.find(x => x <= h && x + 60 <= b);
    if (!candidate) break;
    plan.push(candidate);
    b -= (candidate + 60);
    h = candidate;
  }
  return plan;
}

fs.mkdirSync(`${SCRATCH}/class6_fix`, { recursive: true });
const results = [];
for (const row of audit) {
  if (row.error) continue;
  const flaggedCols = (row.columns || []).filter(c => c.flagged);
  if (flaggedCols.length === 0) continue;
  const data = JSON.parse(fs.readFileSync(`${SCRATCH}/rows/${row.id}.json`, "utf8"));
  const parts = data.parts;
  const rowPlan = { id: row.id, name: row.name, columns: [] };

  for (const col of flaggedCols) {
    const colIdx = col.colIdx;
    const colRe = new RegExp(`(sloupec${colIdx}|col${colIdx})(?!\\d)`);
    const colParts = parts.filter(p => colRe.test(p.role || ""));
    const boxParts = colParts.filter(p => (p.role || "").startsWith("eurobox"));
    const railParts = colParts.filter(p => (p.role || "").startsWith("nosnik"));
    const connParts = colParts.filter(p => /^spojnice/.test(p.role || ""));
    function patroOf(role) { const m = role.match(/patro(\d+)/) || role.match(/-p(\d+)$/); return m ? Number(m[1]) : null; }
    const maxPatro = Math.max(...boxParts.map(p => patroOf(p.role)));
    const topBoxParts = boxParts.filter(p => patroOf(p.role) === maxPatro);
    const topRailParts = railParts.filter(p => patroOf(p.role) === maxPatro);
    const topConnParts = connParts.filter(p => patroOf(p.role) === maxPatro);
    const topHeight = HEIGHT_BY_PID[topBoxParts[0].part_id];
    // naming convention used for THIS row (sloupecN/patroM vs colN/pM)
    const useSloupec = /sloupec\d+/.test(topBoxParts[0].role);
    function roleName(kind, patro) { return useSloupec ? `${kind}-sloupec${colIdx}-patro${patro}` : `${kind}-col${colIdx}-p${patro}`; }

    const overrideKey = `${row.id}_${colIdx}`;
    const plan = OVERRIDES[overrideKey] || planColumnAdditions(topHeight, col.gap);
    if (plan.length === 0) { rowPlan.columns.push({ colIdx, note: "flagged but planner found nothing to add (unexpected)", gap: col.gap }); continue; }

    const newParts = [];
    let railCenterY = topRailParts[0].position[1]; // all rail parts in a patro share Y
    let curTopHeight = topHeight;
    let patroCursor = maxPatro;
    const addedHeights = [];
    for (const H of plan) {
      patroCursor += 1;
      const newRailCenterY = railCenterY + curTopHeight + 30 + T;
      // rails: copy each existing top-rail part, shift Y
      for (const rp of topRailParts) {
        newParts.push({ part_id: rp.part_id, position: [rp.position[0], newRailCenterY, rp.position[2]], quaternion: rp.quaternion, scale: rp.scale, role: roleName("nosnik", patroCursor) });
      }
      // connectors (spojnice): copy, shift Y
      for (const cp of topConnParts) {
        newParts.push({ part_id: cp.part_id, position: [cp.position[0], newRailCenterY, cp.position[2]], quaternion: cp.quaternion, scale: cp.scale, role: roleName("spojnice", patroCursor) });
      }
      // boxes: same X/Z as topmost existing boxes, new part_id for height H,
      // Y computed via the established pivot formula.
      const newPid = PID_BY_HEIGHT[H];
      for (const bp of topBoxParts) {
        const localMinY = localMinYAfterQuat(newPid, bp.quaternion);
        const ty = newRailCenterY + T / 2 - localMinY - 12;
        newParts.push({ part_id: newPid, position: [bp.position[0], ty, bp.position[2]], quaternion: bp.quaternion, scale: bp.scale, role: roleName("eurobox", patroCursor) });
      }
      addedHeights.push(H);
      railCenterY = newRailCenterY;
      curTopHeight = H;
    }
    rowPlan.columns.push({ colIdx, gapBefore: col.gap, addedHeights, newTopOfStack: railCenterY + T / 2 + curTopHeight, physCeil: col.physCeil, newPartsCount: newParts.length });
    parts.push(...newParts);
  }
  data.parts = parts;
  fs.writeFileSync(`${SCRATCH}/class6_fix/${row.id}.json`, JSON.stringify(data));
  results.push(rowPlan);
}
console.log(JSON.stringify(results, null, 1));
