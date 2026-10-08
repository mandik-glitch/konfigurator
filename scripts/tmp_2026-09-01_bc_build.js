// Build variant B (max height diversity) and C (balanced alt) for:
//   Vito MB47 (id=83), Custom FO31 (id=111), Transporter VW25 (id=118), Vivaro OP31 (id=136)
// Legs/rails-X/rails-Z/columns positions stay IDENTICAL to variant A (read straight from
// the saved DB data) - only the per-level box heights (and therefore per-level rail Y
// positions) are replanned. Every candidate plan is validated against the REAL car body
// GLB (collidesWithWalls) - if a candidate's top level collides, it is automatically
// backed off to the next smaller allowed height (maintaining non-increasing order) and
// retried, so we never trust the abstract "railYCenter<=TOP_Y-T/2" formula alone for the
// last (unconstrained-by-rail) level - the real physical ceiling varies a lot per vehicle
// (MB47 real ceiling ~110mm above its RAIL_TOP_MAX; OP31's real ceiling is only ~5mm above
// its RAIL_TOP_MAX - confirmed while building OP31 variant A moments ago).
const THREE = require("three");
const fs = require("fs");
const { createEngine } = require("/opt/konfigurator/scripts/tmp_2026-08-31_batch_engine.js");

const T = 30;
const KAT = "/opt/konfigurator/webapp/katalog/";
const EUROBOX_GLB = { 120: KAT + "product_3788.glb", 170: KAT + "product_3793.glb", 220: KAT + "product_3794.glb", 270: KAT + "product_3795.glb" };
const EUROBOX_PID = { 120: "product_3788", 170: "product_3793", 220: "product_3794", 270: "product_3795" };
const Q_ALONG_Z = [-0.707107, 0, 0, 0.707107];
const HEIGHTS_ALL = [270, 220, 170, 120];

const VEHICLES = {
  MB47: { id: 83, base: "Mercedes_Vito_MB47_2014-", label: "Mercedes Vito MB47 (2014-)" },
  FO31: { id: 111, base: "Ford_Custom_FO31_2023-", label: "Transit Custom L2 FO31" },
  VW25: { id: 118, base: "Volkswagen_Transporter_VW25_2024-", label: "T7 VW25" },
  OP31: { id: 136, base: "Opel_Vivaro_OP31_2020-", label: "Vivaro Electric L1 OP31" },
};

// Proposed (colIdx -> heights array, non-increasing) plans per vehicle/variant.
// Chosen from real budget analysis (see AGENTS_LOG.md bot16 2026-09-01) - genuinely
// different from variant A and from each other; validated (with auto-backoff) below.
const PLANS = {
  MB47: {
    B: { 0: [220, 170, 120], 1: [270, 220] },
    C: { 0: [270, 220], 1: [220, 170, 120] },
  },
  FO31: {
    B: { 0: [270, 220, 120] },
    C: { 0: [220, 170, 120] },
  },
  VW25: {
    B: { 0: [270, 220, 120] },
    C: { 0: [220, 170, 120] },
  },
  OP31: {
    // OP31's real physical ceiling is only ~5mm above RAIL_TOP_MAX (verified while
    // building variant A - step7 physCeil=927 vs RAIL_TOP_MAX=922) - variant A's
    // [270,220] already uses all achievable vertical budget. For B/C we can only
    // realistically vary WHICH 2 heights occupy the 2 achievable levels, not add a 3rd.
    B: { 0: [270, 170] },
    C: { 0: [220, 120] },
  },
};

function glbFor(id) {
  if (id === "Object_7") return KAT + "Object_7.glb";
  if (id === "product_3071") return KAT + "product_3071.glb";
  for (const h in EUROBOX_PID) if (EUROBOX_PID[h] === id) return EUROBOX_GLB[h];
  return null;
}

function extractStructure(parts) {
  const carBodyParts = parts.filter(p => p.part_id && p.part_id.startsWith("car_body_"));
  const legParts = parts.filter(p => p.role && !/sloupec\d+-patro\d+/.test(p.role) && !(p.part_id || "").startsWith("car_body_"));
  const backPosts = parts.filter(p => p.role === "zadni-svislice-dolni" || p.role === "zadni-svislice-nad-zarezem");
  const RAIL_TOP_MAX = Math.max(...backPosts.map(p => p.position[1] + p.scale[1] * 500));
  const colSet = new Set();
  parts.forEach(p => { const m = p.role && p.role.match(/^(?:nosnik|spojnice|eurobox)-sloupec(\d+)-patro(\d+)/); if (m) colSet.add(Number(m[1])); });
  const columns = [...colSet].sort((a, b) => a - b).map(colIdx => {
    const nosnik0 = parts.filter(p => p.role === `nosnik-sloupec${colIdx}-patro0`);
    const spojnice0 = parts.filter(p => p.role === `spojnice-sloupec${colIdx}-patro0`);
    const railXs = [...new Set(nosnik0.map(p => p.position[0]))];
    const railZCenter = nosnik0[0].position[2];
    const railLen = nosnik0[0].scale[1] * 1000;
    const connZs = spojnice0.map(p => p.position[2]).sort((a, b) => a - b);
    const N = connZs.length - 1;
    const floorY = nosnik0[0].position[1] - T / 2;
    return { colIdx, N, railXs, railZCenter, railLen, connZs, floorY };
  });
  return { carBodyParts, legParts, RAIL_TOP_MAX, columns };
}

// OPRAVA (bug #1, +12mm mezera - viz tmp_2026-08-31_batch_pipeline.js): eurobox
// ma 12mm "nozku" (nesting foot), ktera zapada 12mm POD rail top - viditelna
// vyska boxu nad rail top je H_box-12, ne plna deklarovana H_box. Pouziti plne
// h davalo kazde mezere +12mm navic (viz KOMPONENTY_EUROBOXY.md "Univerzalni
// +12mm chyba").
const NEST_FOOT = 12;
function computeLevels(floorY, heights, RAIL_TOP_MAX) {
  let railTop = floorY + T;
  const levels = [];
  for (const h of heights) {
    if (railTop > RAIL_TOP_MAX + 1e-6) throw new Error(`railTop ${railTop} exceeds RAIL_TOP_MAX ${RAIL_TOP_MAX} (h=${h})`);
    levels.push({ railYCenter: railTop - T / 2, boxH: h });
    railTop = railTop + (h - NEST_FOOT) + 30 + T;
  }
  return levels;
}

function buildColumnParts(col, heights, RAIL_TOP_MAX) {
  const levels = computeLevels(col.floorY, heights, RAIL_TOP_MAX);
  const [xA, xB] = col.railXs;
  const crossXCenter = (xA + xB) / 2;
  const crossLen = Math.abs(xA - xB) - 2 * T; // matches D-2T formula (railXs are outer rail centers)
  const parts = [];
  levels.forEach((level, levelIdx) => {
    const Y = level.railYCenter;
    parts.push({ part_id: "Object_7", position: [xA, Y, col.railZCenter], quaternion: Q_ALONG_Z, scale: [1, col.railLen / 1000, 1], role: `nosnik-sloupec${col.colIdx}-patro${levelIdx}` });
    parts.push({ part_id: "Object_7", position: [xB, Y, col.railZCenter], quaternion: Q_ALONG_Z, scale: [1, col.railLen / 1000, 1], role: `nosnik-sloupec${col.colIdx}-patro${levelIdx}` });
    col.connZs.forEach(z => {
      parts.push({ part_id: "Object_7", position: [crossXCenter, Y, z], quaternion: [0, 0, -0.707107, 0.707107], scale: [1, crossLen / 1000, 1], role: `spojnice-sloupec${col.colIdx}-patro${levelIdx}` });
    });
    for (let i = 0; i < col.connZs.length - 1; i++) {
      parts.push({
        part_id: EUROBOX_PID[level.boxH], position: [0, 0, 0], quaternion: Q_ALONG_Z, scale: [1, 1, 1], role: `eurobox-sloupec${col.colIdx}-patro${levelIdx}`,
        _pending: { slotZFrom: col.connZs[i], slotZTo: col.connZs[i + 1], railYCenter: Y, boxH: level.boxH, crossXCenter },
      });
    }
  });
  return { parts, levels };
}

const probeCache = {};
function probeFor(engine, h) {
  if (probeCache[h]) return probeCache[h];
  const m = engine.parseGlbMesh(EUROBOX_GLB[h]);
  m.position.set(0, 0, 0); m.quaternion.set(...Q_ALONG_Z); m.scale.set(1, 1, 1);
  m.updateMatrixWorld(true);
  const b = new THREE.Box3().setFromObject(m);
  const center = [(b.min.x + b.max.x) / 2, (b.min.y + b.max.y) / 2, (b.min.z + b.max.z) / 2];
  return (probeCache[h] = { box: b, center });
}
function placeEuroboxes(engine, parts) {
  parts.forEach(p => {
    if (!p._pending) return;
    const { slotZFrom, slotZTo, railYCenter, boxH, crossXCenter } = p._pending;
    const probe = probeFor(engine, boxH);
    const targetZcenter = (slotZFrom + slotZTo) / 2;
    const targetYbottom = railYCenter + T / 2;
    p.position = [crossXCenter - probe.center[0], targetYbottom - probe.box.min.y - 12, targetZcenter - probe.center[2]];
    p.quaternion = [...Q_ALONG_Z];
    delete p._pending;
  });
}
function meshOf(engine, p) {
  const m = engine.parseGlbMesh(glbFor(p.part_id));
  m.position.set(...p.position); m.quaternion.set(...p.quaternion); m.scale.set(...p.scale);
  m.updateMatrixWorld(true);
  return m;
}

function tryBuildColumnWithBackoff(engine, col, heights, RAIL_TOP_MAX, legParts, log) {
  let h = heights.slice();
  while (h.length > 0) {
    let colResult;
    try { colResult = buildColumnParts(col, h, RAIL_TOP_MAX); }
    catch (e) { log.push(`col${col.colIdx} heights=${JSON.stringify(h)}: rail-limit violated (${e.message}) - dropping last level`); h.pop(); continue; }
    const parts = colResult.parts.map(p => ({ ...p }));
    placeEuroboxes(engine, parts);
    // test ONLY this column's boxes + rails vs real car body (cheap, isolates the top level)
    const profileGroup = new THREE.Group();
    parts.filter(p => p.part_id === "Object_7").forEach(p => profileGroup.add(meshOf(engine, p)));
    profileGroup.updateMatrixWorld(true);
    const railsCollide = engine.collidesWithWalls(profileGroup);
    const boxGroup = new THREE.Group();
    parts.filter(p => p.part_id.startsWith("product_37")).forEach(p => boxGroup.add(meshOf(engine, p)));
    boxGroup.updateMatrixWorld(true);
    const boxesCollide = engine.collidesWithWalls(boxGroup);
    if (!railsCollide && !boxesCollide) { log.push(`col${col.colIdx} heights=${JSON.stringify(h)}: OK (no car-body collision)`); return { parts: colResult.parts, heights: h }; }
    log.push(`col${col.colIdx} heights=${JSON.stringify(h)}: COLLISION (rails=${railsCollide} boxes=${boxesCollide}) - reducing top level and retrying`);
    // reduce the top (last) level to the next smaller allowed height; if already smallest, drop it
    const lastH = h[h.length - 1];
    const idx = HEIGHTS_ALL.indexOf(lastH);
    if (idx < HEIGHTS_ALL.length - 1) h[h.length - 1] = HEIGHTS_ALL[idx + 1];
    else h.pop();
  }
  log.push(`col${col.colIdx}: no level fits at all (unexpected) - column empty`);
  return { parts: [], heights: [] };
}

function selfCollisionCheck(engine, partsIn) {
  const meshes = partsIn.map(p => meshOf(engine, p));
  let unexpected = 0;
  const pairs = [];
  for (let i = 0; i < meshes.length; i++) for (let j = i + 1; j < meshes.length; j++) {
    const A = new THREE.Box3().setFromObject(meshes[i]), B = new THREE.Box3().setFromObject(meshes[j]);
    const ox = Math.min(A.max.x, B.max.x) - Math.max(A.min.x, B.min.x);
    const oy = Math.min(A.max.y, B.max.y) - Math.max(A.min.y, B.min.y);
    const oz = Math.min(A.max.z, B.max.z) - Math.max(A.min.z, B.min.z);
    if (ox > 0.5 && oy > 0.5 && oz > 0.5) {
      const nestOk = partsIn[i].part_id !== "Object_7" || partsIn[j].part_id !== "Object_7";
      if (!nestOk) { unexpected++; pairs.push([partsIn[i].role, partsIn[j].role]); }
    }
  }
  return { unexpected, pairs };
}

const allResults = {};
for (const [vkey, vcfg] of Object.entries(VEHICLES)) {
  const data = JSON.parse(fs.readFileSync(`/tmp/claude-0/-opt-domeny/40752a20-c083-499a-8fe3-7c39a4eef60b/scratchpad/data/pa_${vcfg.id}.json`, "utf8"));
  const struct = extractStructure(data.parts);
  const engine = createEngine(vcfg.base);
  console.log(`\n########## ${vkey} (id=${vcfg.id}) RAIL_TOP_MAX=${struct.RAIL_TOP_MAX.toFixed(1)} columns=${struct.columns.length} ##########`);

  for (const variantLetter of ["B", "C"]) {
    const plan = PLANS[vkey][variantLetter];
    const log = [];
    let allParts = [...struct.carBodyParts, ...struct.legParts];
    const columnFinal = [];
    for (const col of struct.columns) {
      const wanted = plan[col.colIdx];
      const { parts, heights } = tryBuildColumnWithBackoff(engine, col, wanted, struct.RAIL_TOP_MAX, struct.legParts, log);
      const p2 = parts.map(p => ({ ...p }));
      placeEuroboxes(engine, p2);
      allParts.push(...p2);
      columnFinal.push({ colIdx: col.colIdx, N: col.N, heights });
    }
    // full-assembly checks
    const profileGroup = new THREE.Group();
    allParts.filter(p => p.part_id === "Object_7").forEach(p => profileGroup.add(meshOf(engine, p)));
    profileGroup.updateMatrixWorld(true);
    const legsCollide = engine.collidesWithWalls(profileGroup);
    const boxGroup = new THREE.Group();
    allParts.filter(p => p.part_id.startsWith("product_37")).forEach(p => boxGroup.add(meshOf(engine, p)));
    boxGroup.updateMatrixWorld(true);
    const boxesCollide = engine.collidesWithWalls(boxGroup);
    const selfCheckParts = allParts.filter(p => !(p.part_id || "").startsWith("car_body_"));
    const self = selfCollisionCheck(engine, selfCheckParts);
    const totalBoxes = columnFinal.reduce((s, c) => s + c.N * c.heights.length, 0);
    const distinct = [...new Set(columnFinal.flatMap(c => c.heights))];
    const nonIncreasingOk = columnFinal.every(c => c.heights.every((h, i) => i === 0 || h <= c.heights[i - 1]));
    const summary = { vkey, variant: variantLetter, columnFinal, totalBoxes, distinct, nonIncreasingOk, legsCollide, boxesCollide, unexpectedSelfCollisions: self.unexpected, unexpectedPairs: self.pairs };
    console.log(`--- ${vkey} variant ${variantLetter} ---`);
    console.log(JSON.stringify(summary, null, 1));
    log.forEach(l => console.log("  " + l));
    const ok = !legsCollide && !boxesCollide && self.unexpected === 0 && nonIncreasingOk && distinct.length >= Math.min(3, HEIGHTS_ALL.length);
    summary.ok = ok;
    if (!ok) console.log(`  *** ${vkey} ${variantLetter}: distinct=${distinct.length} (rule >=3 may be genuinely infeasible - see log) legsCollide=${legsCollide} boxesCollide=${boxesCollide} self=${self.unexpected} ***`);
    const clean = allParts.map(({ _pending, ...rest }) => rest);
    fs.writeFileSync(`/opt/konfigurator/scripts/tmp_2026-09-01_bc_${vkey}_${variantLetter}_parts.json`, JSON.stringify(clean, null, 1));
    allResults[`${vkey}_${variantLetter}`] = summary;
  }
}
fs.writeFileSync("/opt/konfigurator/scripts/tmp_2026-09-01_bc_all_summary.json", JSON.stringify(allResults, null, 1));
console.log("\nDONE.");
