// bot16 2026-09-02 - compute the leg-height fix plan per shape_geometry_methods.id=8
// ("prizpusobeni-vysky-nohy-vysce-dveri") for all eurobox racks with known
// official_door_opening_height_mm. Uses REAL GLB geometry (Box3), not just
// stored role-name strings, per task instructions (role naming varies:
// 'zadni-svislice' generic vs 'zadni-svislice-dolni'/'zadni-svislice-nad-zarezem',
// 'zaslepka' generic vs 'zaslepka-cap'/'zaslepka-predni-svislice'/...).
const fs = require("fs");
const THREE = require("three");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const KAT = "/opt/konfigurator/webapp/katalog/";

const SCRATCH = "/tmp/claude-0/-opt-domeny/40752a20-c083-499a-8fe3-7c39a4eef60b/scratchpad";
const rows = JSON.parse(fs.readFileSync(`${SCRATCH}/rows_full.json`, "utf8"));

const meshCache = {};
function getMesh(id) {
  if (!meshCache[id]) meshCache[id] = parseGlbMesh(KAT + id + ".glb");
  return meshCache[id];
}
function box3For(part) {
  const m = getMesh(part.part_id);
  m.position.set(part.position[0], part.position[1], part.position[2]);
  m.quaternion.set(part.quaternion[0], part.quaternion[1], part.quaternion[2], part.quaternion[3]);
  m.scale.set(part.scale[0], part.scale[1], part.scale[2]);
  m.updateMatrixWorld(true);
  return new THREE.Box3().setFromObject(m);
}
// base (unscaled, unrotated, at origin) Y-span of a part_id - used to derive
// new scale/position analytically instead of re-deriving via search.
const baseLenCache = {};
function baseYLen(part_id) {
  if (baseLenCache[part_id] != null) return baseLenCache[part_id];
  const m = getMesh(part_id);
  m.position.set(0, 0, 0);
  m.quaternion.set(0, 0, 0, 1);
  m.scale.set(1, 1, 1);
  m.updateMatrixWorld(true);
  const b = new THREE.Box3().setFromObject(m);
  const len = b.max.y - b.min.y;
  baseLenCache[part_id] = len;
  return len;
}

const WALL_ROLES = new Set(["cap", "zadni-svislice-dolni", "zadni-svislice-nad-zarezem", "zadni-svislice"]);
const LEG_ROLES = new Set([
  "predni-svislice", "cap", "zadni-svislice-dolni", "zadni-svislice-nad-zarezem", "zadni-svislice",
  "zaslepka-cap", "zaslepka-predni-svislice", "zaslepka-zadni-svislice-dolni",
  "zaslepka-zadni-svislice-nad-zarezem", "zaslepka-zadni-svislice", "zaslepka",
  "sloupek-pred-podbehem", "spojnice-dolni", "spojnice-horni", "spojnice-dolni-kratka",
  "spojnice-horni-uzavreni", "pricka-uzavreni-vyrezu",
]);
const RAIL_ROLE_PREFIXES = ["spojnice-sloupec", "spojnice-col", "nosnik-sloupec", "nosnik-col"];

const TOL = 2; // mm tolerance for "already correct"

const plan = { rows: [] };

for (const row of rows) {
  const parts = row.data.parts || [];
  const H_target = row.door_height_mm - 30;
  const rowOut = { id: row.id, name: row.name, legacy_vendor_code: row.legacy_vendor_code,
    door_height_mm: row.door_height_mm, H_target, legs: [], issues: [] };

  // index parts with their array index (needed to write back later)
  const indexed = parts.map((p, idx) => ({ p, idx }));

  // 1) group leg-relevant parts by exact Z (position[2]) - front & wall pieces of
  // the same leg share identical Z in this dataset (verified by inspection).
  const legRoleParts = indexed.filter(({ p }) => LEG_ROLES.has(p.role));
  const zGroups = new Map();
  for (const item of legRoleParts) {
    const z = item.p.position[2];
    const key = z.toFixed(3);
    if (!zGroups.has(key)) zGroups.set(key, []);
    zGroups.get(key).push(item);
  }

  for (const [zKey, items] of zGroups.entries()) {
    const legOut = { z: parseFloat(zKey), issues: [] };

    const fronts = items.filter(it => it.p.role === "predni-svislice" && it.p.part_id === "Object_7");
    if (fronts.length !== 1) {
      legOut.issues.push(`expected exactly 1 predni-svislice, found ${fronts.length}`);
      rowOut.legs.push(legOut);
      continue;
    }
    const front = fronts[0];

    const wallCands = items.filter(it => WALL_ROLES.has(it.p.role) && it.p.part_id === "Object_7");
    if (wallCands.length === 0) {
      legOut.issues.push("no wall-side candidate piece (cap/zadni-svislice*) found");
      rowOut.legs.push(legOut);
      continue;
    }
    // compute real top/bottom for each candidate
    for (const c of wallCands) {
      const b = box3For(c.p);
      c._top = b.max.y; c._bottom = b.min.y;
    }
    let wall;
    const capCands = wallCands.filter(c => c.p.role === "cap");
    if (capCands.length >= 1) {
      if (capCands.length > 1) legOut.issues.push(`multiple 'cap' pieces (${capCands.length}) in same leg - using highest`);
      wall = capCands.reduce((a, b) => (b._top > a._top ? b : a));
    } else {
      wall = wallCands.reduce((a, b) => (b._top > a._top ? b : a));
    }

    const frontBox = box3For(front.p);
    const frontTop = frontBox.max.y, frontBottom = frontBox.min.y;
    const wallTop = wall._top, wallBottom = wall._bottom;

    if (Math.abs(frontBottom) > TOL) legOut.issues.push(`predni-svislice bottom not at floor: ${frontBottom.toFixed(2)}`);

    legOut.leg_type = (items.some(it => ["sloupek-pred-podbehem", "pricka-uzavreni-vyrezu", "zadni-svislice-nad-zarezem"].includes(it.p.role))) ? "vyrez" : "plain";
    legOut.front = { idx: front.idx, role: front.p.role, part_id: front.p.part_id, top: frontTop, bottom: frontBottom, scale: front.p.scale.slice(), position: front.p.position.slice() };
    legOut.wall = { idx: wall.idx, role: wall.p.role, part_id: wall.p.part_id, top: wallTop, bottom: wallBottom, scale: wall.p.scale.slice(), position: wall.p.position.slice() };

    // find matching zaslepka (endcap) for front & wall: same leg group, part_id product_3071,
    // matching X (within 5mm), Y close to current top (within 20mm).
    function findZaslepka(parentTop, parentX) {
      const cands = items.filter(it => it.p.part_id === "product_3071" &&
        Math.abs(it.p.position[0] - parentX) < 5 &&
        Math.abs(it.p.position[1] - parentTop) < 20);
      return cands.length ? cands[0] : null;
    }
    const frontZas = findZaslepka(frontTop, front.p.position[0]);
    const wallZas = findZaslepka(wallTop, wall.p.position[0]);
    if (!frontZas) legOut.issues.push("no matching zaslepka found for predni-svislice top");
    if (!wallZas) legOut.issues.push("no matching zaslepka found for wall-top piece");
    legOut.frontZaslepka = frontZas ? { idx: frontZas.idx, offset: frontZas.p.position[1] - frontTop } : null;
    legOut.wallZaslepka = wallZas ? { idx: wallZas.idx, offset: wallZas.p.position[1] - wallTop } : null;

    // needed change?
    const frontDelta = H_target - frontTop;
    const wallDelta = H_target - wallTop;
    legOut.frontDelta = frontDelta;
    legOut.wallDelta = wallDelta;
    legOut.needsChange = Math.abs(frontDelta) > TOL || Math.abs(wallDelta) > TOL;
    legOut.direction = legOut.needsChange ? ((frontDelta > 0 || wallDelta > 0) ? "extend" : "shorten") : "none";

    // lůžko / rail containment check for this leg's column (id=6 interaction):
    // find rails (spojnice-sloupecN-patroN / spojnice-colN-pN / nosnik-*) whose Z falls
    // within [zMin,zMax] of this leg's own footprint band (nearby Z, +-30mm) - approximate
    // by checking rails near this leg's Z (rails span a column of TWO legs, so also check
    // the opposite-leg zGroup at compute-row level below). Store raw candidate list; the
    // row-level pass below groups legs into columns and checks the topmost rail vs new leg top.
    rowOut.legs.push(legOut);
  }

  // 2) group legs into columns (a column spans 2 legs at its two ends) using the
  // same z-clustering idea as tmp_2026-09-01_bot16_crossbar_gap_audit.js: rails
  // (spojnice-sloupecN-patroN/spojnice-colN-pN/nosnik-*) have a Z-span [zMin,zMax]
  // matching two leg Z's (within ~10mm). For each column, find topmost rail Y and
  // compare against the MIN of the two legs' new tops (a rail needs a real leg
  // profile under each end).
  const railParts = indexed.filter(({ p }) => RAIL_ROLE_PREFIXES.some(pref => p.role && p.role.startsWith(pref)));
  const legZs = rowOut.legs.filter(l => !l.issues.length).map(l => l.z);
  const railInfo = [];
  for (const { p } of railParts) {
    let b;
    try { b = box3For(p); } catch (e) { continue; }
    railInfo.push({ role: p.role, cz: p.position[2], top: b.max.y, bottom: b.min.y });
  }
  for (const legOut of rowOut.legs) {
    if (legOut.issues.length) continue;
    // rails whose z is close to this leg's z (within 20mm) belong to a column this leg supports
    const nearbyRails = railInfo.filter(r => Math.abs(r.cz - legOut.z) < 400); // generous: column can span up to ~400mm from a leg's Z on either side is NOT right; use exact rail-Z proximity instead below
  }
  // Simpler/more precise: match rails to the two nearest leg Z's that bracket the rail's cz
  // (rails' own cz recorded above is a crossbar/runner MIDPOINT along the column span, not
  // useful for bracketing). Fall back to: for each leg, find rails landing within 15mm of
  // this leg's Z (crossbar connectors project close to each leg at the column ends) - use
  // the crossbar_gap_audit convention: level Z-span end coordinates match leg Z's closely.
  for (const legOut of rowOut.legs) {
    if (legOut.issues.length || !legOut.needsChange) continue;
    if (legOut.direction !== "shorten") continue; // extending never causes a containment problem
    const newFrontTop = legOut.front.top + legOut.frontDelta;
    const newWallTop = legOut.wall.top + legOut.wallDelta;
    const newLegTop = Math.min(newFrontTop, newWallTop);
    const topmostRail = railInfo.filter(r => Math.abs(r.cz - legOut.z) < 15).sort((a, b) => b.top - a.top)[0];
    if (topmostRail && topmostRail.top > newLegTop + TOL) {
      legOut.issues.push(`LUZKO CONTAINMENT VIOLATION: shortening leg to ${newLegTop.toFixed(1)} would leave rail (${topmostRail.role}) top at ${topmostRail.top.toFixed(1)} sticking out above the leg`);
      rowOut.issues.push(legOut.issues[legOut.issues.length - 1] + ` (z=${legOut.z})`);
    }
  }

  plan.rows.push(rowOut);
}

fs.writeFileSync(`${SCRATCH}/plan.json`, JSON.stringify(plan, null, 0));
console.error("wrote plan.json, rows:", plan.rows.length);
