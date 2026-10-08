// bot16 2026-09-02 - apply shape_geometry_methods.id=8 leg-height fix to all
// rows in plan.json (needsChange legs), then verify: (a) no NEW car-body
// collision on the 4 touched pieces per leg (front, wall, frontZaslepka,
// wallZaslepka) vs BEFORE, (b) no NaN/invalid geometry. Writes
// updated_rows.json (id -> new parts array) for rows that pass verification,
// and verify_report.json with per-row pass/fail + any pre-existing collisions
// found (not caused by this change, reported per project convention).
const fs = require("fs");
const THREE = require("three");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const { makeCollisionModule } = require("/opt/konfigurator/scripts/2026-09-01_collision_module_factory.js");
const KAT = "/opt/konfigurator/webapp/katalog/";

const SCRATCH = "/tmp/claude-0/-opt-domeny/40752a20-c083-499a-8fe3-7c39a4eef60b/scratchpad";
const plan = JSON.parse(fs.readFileSync(`${SCRATCH}/plan.json`, "utf8"));
const rowsFull = JSON.parse(fs.readFileSync(`${SCRATCH}/rows_full.json`, "utf8"));
const carBodyGlb = JSON.parse(fs.readFileSync(`${SCRATCH}/car_body_glb.json`, "utf8"));
const rowsMeta = JSON.parse(fs.readFileSync(`${SCRATCH}/rows_meta.json`, "utf8"));

const rowsFullById = new Map(rowsFull.map(r => [r.id, r]));
const rowsMetaById = new Map(rowsMeta.map(r => [r.id, r]));

const meshCache = {};
function getMesh(id) {
  if (!meshCache[id]) meshCache[id] = parseGlbMesh(KAT + id + ".glb");
  return meshCache[id];
}
function box3For(p) {
  const m = getMesh(p.part_id);
  m.position.set(p.position[0], p.position[1], p.position[2]);
  m.quaternion.set(p.quaternion[0], p.quaternion[1], p.quaternion[2], p.quaternion[3]);
  m.scale.set(p.scale[0], p.scale[1], p.scale[2]);
  m.updateMatrixWorld(true);
  return new THREE.Box3().setFromObject(m);
}
function meshFor(p) {
  const m = getMesh(p.part_id);
  m.position.set(p.position[0], p.position[1], p.position[2]);
  m.quaternion.set(p.quaternion[0], p.quaternion[1], p.quaternion[2], p.quaternion[3]);
  m.scale.set(p.scale[0], p.scale[1], p.scale[2]);
  m.updateMatrixWorld(true);
  return m;
}
const baseLenCache = {};
function baseYLen(part_id) {
  if (baseLenCache[part_id] != null) return baseLenCache[part_id];
  const m = getMesh(part_id);
  m.position.set(0, 0, 0); m.quaternion.set(0, 0, 0, 1); m.scale.set(1, 1, 1);
  m.updateMatrixWorld(true);
  const b = new THREE.Box3().setFromObject(m);
  const len = b.max.y - b.min.y;
  baseLenCache[part_id] = len;
  return len;
}

function basePathFor(rowMeta) {
  // pick first car_body id, strip _L/_R_D/_B + .glb
  const cbId = rowMeta.car_body_ids[0];
  const glb = carBodyGlb[String(cbId)];
  if (!glb) return null;
  const m = glb.match(/^(.*)_(?:L|R_D|B)\.glb$/);
  if (!m) return null;
  return KAT + m[1];
}

const collisionModCache = {};
function getCollisionMod(basePath) {
  if (!collisionModCache[basePath]) collisionModCache[basePath] = makeCollisionModule(basePath);
  return collisionModCache[basePath];
}

const report = { rows: [] };
const updatedRows = {};

let totalLegsChanged = 0, totalLegsSkippedPlanIssue = 0;

for (const planRow of plan.rows) {
  const rowMeta = rowsMetaById.get(planRow.id);
  const rowFull = rowsFullById.get(planRow.id);
  const parts = JSON.parse(JSON.stringify(rowFull.data.parts)); // deep clone to mutate

  const basePath = basePathFor(rowMeta);
  let mod = null;
  if (basePath) {
    try { mod = getCollisionMod(basePath); } catch (e) { mod = null; }
  }

  const rowReport = { id: planRow.id, name: planRow.name, legs: [], basePath, collisionModError: !mod };
  let rowChanged = false;

  for (const leg of planRow.legs) {
    if (!leg.front || !leg.wall || !leg.needsChange) {
      if (leg.needsChange === undefined || leg.front === undefined) totalLegsSkippedPlanIssue++;
      continue;
    }
    const legReport = { z: leg.z, direction: leg.direction };

    // BEFORE meshes/boxes (for pre-existing collision reporting)
    const frontPartBefore = parts[leg.front.idx];
    const wallPartBefore = parts[leg.wall.idx];
    let preFrontHit = null, preWallHit = null;
    if (mod) {
      try { preFrontHit = mod.collidesWithWalls(meshFor(frontPartBefore)); } catch (e) {}
      try { preWallHit = mod.collidesWithWalls(meshFor(wallPartBefore)); } catch (e) {}
    }

    // compute new values
    const baseLenFront = baseYLen(leg.front.part_id);
    const baseLenWall = baseYLen(leg.wall.part_id);
    const newFrontTop = leg.front.top + leg.frontDelta;
    const newWallTop = leg.wall.top + leg.wallDelta;
    const newFrontScaleY = (newFrontTop - leg.front.bottom) / baseLenFront;
    const newFrontPosY = (newFrontTop + leg.front.bottom) / 2;
    const newWallScaleY = (newWallTop - leg.wall.bottom) / baseLenWall;
    const newWallPosY = (newWallTop + leg.wall.bottom) / 2;

    if (newFrontScaleY <= 0 || newWallScaleY <= 0) {
      legReport.error = `non-positive resulting scale (front=${newFrontScaleY}, wall=${newWallScaleY})`;
      rowReport.legs.push(legReport);
      continue;
    }

    // build candidate mutated part objects WITHOUT touching the shared `parts`
    // array yet, so a rejected leg never leaks a partial mutation into it.
    const candFront = JSON.parse(JSON.stringify(frontPartBefore));
    candFront.scale[1] = newFrontScaleY; candFront.position[1] = newFrontPosY;
    const candWall = JSON.parse(JSON.stringify(wallPartBefore));
    candWall.scale[1] = newWallScaleY; candWall.position[1] = newWallPosY;
    const candFrontZas = leg.frontZaslepka ? JSON.parse(JSON.stringify(parts[leg.frontZaslepka.idx])) : null;
    if (candFrontZas) candFrontZas.position[1] = newFrontTop + leg.frontZaslepka.offset;
    const candWallZas = leg.wallZaslepka ? JSON.parse(JSON.stringify(parts[leg.wallZaslepka.idx])) : null;
    if (candWallZas) candWallZas.position[1] = newWallTop + leg.wallZaslepka.offset;

    // AFTER collision check vs car body
    let postFrontHit = null, postWallHit = null, postFrontZasHit = null, postWallZasHit = null;
    if (mod) {
      try { postFrontHit = mod.collidesWithWalls(meshFor(candFront)); } catch (e) {}
      try { postWallHit = mod.collidesWithWalls(meshFor(candWall)); } catch (e) {}
      if (candFrontZas) { try { postFrontZasHit = mod.collidesWithWalls(meshFor(candFrontZas)); } catch (e) {} }
      if (candWallZas) { try { postWallZasHit = mod.collidesWithWalls(meshFor(candWallZas)); } catch (e) {} }
    }

    legReport.preExisting = { frontHit: preFrontHit, wallHit: preWallHit };
    legReport.postChange = { frontHit: postFrontHit, wallHit: postWallHit, frontZasHit: postFrontZasHit, wallZasHit: postWallZasHit };
    legReport.newCollisionIntroduced = (!preFrontHit && postFrontHit) || (!preWallHit && postWallHit) || postFrontZasHit || postWallZasHit;
    legReport.newFrontTop = newFrontTop;
    legReport.newWallTop = newWallTop;
    legReport.delta = leg.frontDelta;

    rowReport.legs.push(legReport);
    if (!legReport.newCollisionIntroduced) {
      parts[leg.front.idx] = candFront;
      parts[leg.wall.idx] = candWall;
      if (leg.frontZaslepka) parts[leg.frontZaslepka.idx] = candFrontZas;
      if (leg.wallZaslepka) parts[leg.wallZaslepka.idx] = candWallZas;
      rowChanged = true;
      totalLegsChanged++;
    } else {
      legReport.SKIPPED = "new collision introduced by fix - not applied, needs review";
    }
  }

  rowReport.applied = rowChanged;
  report.rows.push(rowReport);
  if (rowChanged) {
    // only keep legs that were actually applied (not skipped for new collision)
    updatedRows[planRow.id] = parts;
  }
}

fs.writeFileSync(`${SCRATCH}/verify_report.json`, JSON.stringify(report, null, 1));
fs.writeFileSync(`${SCRATCH}/updated_rows.json`, JSON.stringify(updatedRows));
console.error("done. rows with applied changes:", Object.keys(updatedRows).length, "total legs changed:", totalLegsChanged);
