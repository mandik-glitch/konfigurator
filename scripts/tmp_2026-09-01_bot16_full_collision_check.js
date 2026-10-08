// Verifies, for ALL 93 audited rows, that applying the planned gap-fix
// (tmp_2026-09-01_bot16_gap_fix_compute.js output) does not introduce any
// NEW car-body collision, and reports any PRE-EXISTING collision found
// (before the fix) so it can be cross-checked against what parallel
// sessions reported (e.g. id=103/141/142 Trafic RE28 patro4).
const fs = require("fs");
const THREE = require("three");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const { makeCollisionModule } = require("/opt/konfigurator/scripts/2026-09-01_collision_module_factory.js");
const KAT = "/opt/konfigurator/webapp/katalog/";

const SCRATCH = "/tmp/claude-0/-opt-domeny/40752a20-c083-499a-8fe3-7c39a4eef60b/scratchpad";
const rows = JSON.parse(fs.readFileSync(`${SCRATCH}/all_rows.json`, "utf8"));
const plan = JSON.parse(fs.readFileSync(`${SCRATCH}/gap_fix.json`, "utf8"));
const rowBase = JSON.parse(fs.readFileSync(`${SCRATCH}/row_carbody_base.json`, "utf8"));

const meshCache = {};
function getMesh(p) {
  if (!meshCache[p.part_id]) meshCache[p.part_id] = parseGlbMesh(KAT + p.part_id + ".glb");
  return meshCache[p.part_id];
}
const collisionModCache = {};
function getCollisionMod(basePath) {
  if (!collisionModCache[basePath]) collisionModCache[basePath] = makeCollisionModule(KAT + basePath);
  return collisionModCache[basePath];
}

const results = [];
for (const row of rows) {
  const basePath = rowBase[String(row.id)];
  if (!basePath) { results.push({ id: row.id, error: "no basePath" }); continue; }
  let mod;
  try { mod = getCollisionMod(basePath); } catch (e) { results.push({ id: row.id, error: "collision module load failed: " + e.message }); continue; }

  const parts = row.parts.map(p => ({ ...p, position: [...p.position] }));

  function checkAll() {
    let cc = 0; const hits = [];
    for (const p of parts) {
      if (p.part_id.startsWith("car_body")) continue;
      const m = getMesh(p);
      m.position.set(p.position[0], p.position[1], p.position[2]);
      m.quaternion.set(p.quaternion[0], p.quaternion[1], p.quaternion[2], p.quaternion[3]);
      m.scale.set(p.scale[0], p.scale[1], p.scale[2]);
      m.updateMatrixWorld(true);
      if (mod.collidesWithWalls(m)) { cc++; hits.push(p.role || p.part_id); }
    }
    return { cc, hits };
  }

  const before = checkAll();

  const rowPlan = plan.rows.find(r => r.id === row.id);
  let anyShift = false;
  if (rowPlan) {
    for (const col of rowPlan.columns) {
      for (const lv of col.levels) {
        if (Math.abs(lv.delta) < 1e-6) continue;
        anyShift = true;
        for (const idx of [...lv.railIdx, ...lv.connIdx, ...lv.boxIdx]) {
          parts[idx].position[1] += lv.delta;
        }
      }
    }
  }
  const after = checkAll();

  results.push({
    id: row.id, anyShift,
    before_collisions: before.cc, before_hits: before.hits,
    after_collisions: after.cc, after_hits: after.hits,
    NEW_COLLISION: after.cc > before.cc,
  });
  process.stderr.write(`row ${row.id} done: before=${before.cc} after=${after.cc}\n`);
}

fs.writeFileSync(`${SCRATCH}/full_collision_check.json`, JSON.stringify(results, null, 1));
const newCollisions = results.filter(r => r.NEW_COLLISION);
const preExisting = results.filter(r => r.before_collisions > 0);
const stillColliding = results.filter(r => r.after_collisions > 0);
console.log("rows checked:", results.length);
console.log("rows with NEW collision introduced by fix:", newCollisions.length, newCollisions.map(r => r.id));
console.log("rows with pre-existing collision (before fix):", preExisting.length, preExisting.map(r => r.id));
console.log("rows STILL colliding after fix:", stillColliding.length, stillColliding.map(r => r.id));
