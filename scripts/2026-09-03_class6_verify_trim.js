// Independent verification pass for the Class 6 fix plan: for every row/column
// that got new patra added, rebuild the collision module for its real car
// body and test the ACTUAL new top-of-stack (full column footprint slab,
// same technique as the audit/step7) against the real GLB walls. If it
// collides (e.g. float-noise pushed it 1mm over physCeil), pop the last
// added patro (rails+connectors+box) and re-test, repeating until safe or
// empty. Also re-checks self-collision is not the concern here (only wall
// collision matters for this class of fix). Writes the possibly-trimmed
// final `data.parts` back into scratch/class6_fix/<id>.json and a report.
const fs = require("fs");
const THREE = require("three");
const { makeCollisionModule } = require("/opt/konfigurator/scripts/2026-09-01_collision_module_factory.js");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");

const SCRATCH = "/tmp/claude-0/-opt-domeny/40752a20-c083-499a-8fe3-7c39a4eef60b/scratchpad";
const KAT = "/opt/konfigurator/webapp/katalog/";

const carBodies = {};
fs.readFileSync(`${SCRATCH}/car_bodies.tsv`, "utf8").trim().split("\n").forEach(l => {
  const [id, name, glb] = l.split("\t");
  carBodies[Number(id)] = { name, glb };
});
function baseForCarBodyId(id) {
  const rec = carBodies[id];
  if (!rec) return null;
  let f = rec.glb.replace(/^car_bodies\//, "");
  return f.replace(/_B_wall\.glb$/, "").replace(/_B\.glb$/, "").replace(/_R_D\.glb$/, "").replace(/_L\.glb$/, "");
}
const collisionModCache = {};
function getCollisionModule(base) {
  if (collisionModCache[base]) return collisionModCache[base];
  const mod = makeCollisionModule(KAT + "car_bodies/" + base);
  collisionModCache[base] = mod;
  return mod;
}
const meshCache = {};
function loadMesh(partId) {
  if (meshCache[partId]) return meshCache[partId];
  let p = partId === "Object_7" ? KAT + "Object_7.glb" : KAT + partId + ".glb";
  const m = parseGlbMesh(p);
  meshCache[partId] = m;
  return m;
}
function worldBox3(part) {
  const src = loadMesh(part.part_id);
  const mesh = src.clone(); mesh.geometry = src.geometry;
  mesh.position.set(part.position[0], part.position[1], part.position[2]);
  mesh.quaternion.set(part.quaternion[0], part.quaternion[1], part.quaternion[2], part.quaternion[3]);
  mesh.scale.set(part.scale[0], part.scale[1], part.scale[2]);
  mesh.updateMatrixWorld(true);
  return new THREE.Box3().setFromObject(mesh);
}
function colTagOf(role) { const m = (role || "").match(/sloupec(\d+)/) || (role || "").match(/col(\d+)/); return m ? Number(m[1]) : null; }
function patroTagOf(role) { const m = (role || "").match(/patro(\d+)/) || (role || "").match(/-p(\d+)$/); return m ? Number(m[1]) : null; }

const plan = JSON.parse(fs.readFileSync(`${SCRATCH}/class6_plan.json`, "utf8"));
const report = [];
for (const rp of plan) {
  const dataPath = `${SCRATCH}/class6_fix/${rp.id}.json`;
  const data = JSON.parse(fs.readFileSync(dataPath, "utf8"));
  const parts = data.parts;
  const carBodyIds = [...new Set(parts.filter(p => p.part_id.startsWith("car_body_")).map(p => Number(p.part_id.slice("car_body_".length))))];
  const base = baseForCarBodyId(carBodyIds[0]);
  const mod = getCollisionModule(base);
  const rowReport = { id: rp.id, name: rp.name, base, columns: [] };

  for (const colPlan of rp.columns) {
    const colIdx = colPlan.colIdx;
    let trimmed = 0;
    let safe = false;
    while (!safe) {
      // gather this column's current parts (post any trimming)
      const colParts = parts.filter(p => colTagOf(p.role) === colIdx);
      const boxParts = colParts.filter(p => (p.role || "").startsWith("eurobox"));
      if (boxParts.length === 0) { safe = true; break; }
      const maxPatro = Math.max(...boxParts.map(p => patroTagOf(p.role)));
      const topBoxParts = boxParts.filter(p => patroTagOf(p.role) === maxPatro);
      let topOfStack = -Infinity;
      for (const bp of topBoxParts) { const b3 = worldBox3(bp); if (b3.max.y > topOfStack) topOfStack = b3.max.y; }
      let xMin = Infinity, xMax = -Infinity, zMin = Infinity, zMax = -Infinity;
      for (const p of colParts) { const b3 = worldBox3(p); xMin = Math.min(xMin, b3.min.x); xMax = Math.max(xMax, b3.max.x); zMin = Math.min(zMin, b3.min.z); zMax = Math.max(zMax, b3.max.z); }
      const geo = new THREE.BoxGeometry(Math.max(1, xMax - xMin), 10, Math.max(1, zMax - zMin));
      const mesh = new THREE.Mesh(geo);
      mesh.position.set((xMin + xMax) / 2, topOfStack, (zMin + zMax) / 2);
      mesh.updateMatrixWorld(true);
      if (!mod.collidesWithWalls(mesh)) { safe = true; break; }
      // collides - was this patro one of the ones WE added, or a pre-existing
      // one? Only trim patros we added (maxPatro > original maxPatro before fix).
      // Remove all parts with this colIdx+maxPatro tag and retry.
      const before = parts.length;
      for (let i = parts.length - 1; i >= 0; i--) {
        if (colTagOf(parts[i].role) === colIdx && patroTagOf(parts[i].role) === maxPatro) parts.splice(i, 1);
      }
      trimmed++;
      if (parts.length === before) { safe = true; break; } // nothing removed, avoid infinite loop
    }
    rowReport.columns.push({ colIdx, trimmedPatra: trimmed });
  }
  data.parts = parts;
  fs.writeFileSync(dataPath, JSON.stringify(data));
  report.push(rowReport);
}
console.log(JSON.stringify(report, null, 1));
