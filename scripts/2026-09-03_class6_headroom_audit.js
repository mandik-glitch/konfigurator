// Audit: Class 6 (unused vertical headroom above the top shelf).
// For every column of every is_public=1 product_assemblies row, compute:
//   - topOfStack: actual measured top-Y of the highest eurobox in that column
//     (real GLB geometry, position/quaternion/scale applied - never assumed).
//   - physCeil: real collision-stepping ceiling for that column's footprint
//     (X/Z envelope of its own rungs/boxes), swept 1mm at a time from
//     topOfStack upward against the REAL car-body GLB walls, -2mm margin -
//     same method as tmp_2026-08-31_batch_pipeline.js step7.
//   - gap = physCeil - topOfStack. Flag if gap >= 180mm (120 box + 30 gap +
//     30 rail - Robert's exact criterion, 2026-09-02).
//
// Input: scratch/rows/<id>.json (data column dump) + scratch/all_public_rows.tsv
// (id\tname) + scratch/car_bodies.tsv (id\tname\tglb_file).
// Output: JSON report to stdout (redirect to file).
const fs = require("fs");
const path = require("path");
const THREE = require("three");
const { makeCollisionModule } = require("/opt/konfigurator/scripts/2026-09-01_collision_module_factory.js");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");

const SCRATCH = "/tmp/claude-0/-opt-domeny/40752a20-c083-499a-8fe3-7c39a4eef60b/scratchpad";
const KAT = "/opt/konfigurator/webapp/katalog/";

const rowsList = fs.readFileSync(`${SCRATCH}/all_public_rows.tsv`, "utf8").trim().split("\n")
  .map(l => { const [id, ...rest] = l.split("\t"); return { id: Number(id), name: rest.join("\t") }; });

const carBodies = {};
fs.readFileSync(`${SCRATCH}/car_bodies.tsv`, "utf8").trim().split("\n").forEach(l => {
  const [id, name, glb] = l.split("\t");
  carBodies[Number(id)] = { name, glb };
});

function baseForCarBodyId(id) {
  const rec = carBodies[id];
  if (!rec) return null;
  let f = rec.glb.replace(/^car_bodies\//, "");
  f = f.replace(/_B_wall\.glb$/, "").replace(/_B\.glb$/, "").replace(/_R_D\.glb$/, "").replace(/_L\.glb$/, "");
  return f;
}
function vendorCodeForCarBodyId(id) {
  const rec = carBodies[id];
  if (!rec) return null;
  const m = rec.name.match(/\[vendor (\w+)\]/i);
  return m ? m[1] : null;
}
const karoserieRef = {};
fs.readFileSync(`${SCRATCH}/karoserie_ref.tsv`, "utf8").trim().split("\n").forEach(l => {
  const [code, cargoH, doorH] = l.split("\t");
  karoserieRef[code] = { cargoH: cargoH === "NULL" ? null : Number(cargoH), doorH: doorH === "NULL" ? null : Number(doorH) };
});

const collisionModCache = {};
function getCollisionModule(base) {
  if (collisionModCache[base]) return collisionModCache[base];
  try {
    const mod = makeCollisionModule(KAT + "car_bodies/" + base);
    collisionModCache[base] = mod;
    return mod;
  } catch (e) {
    collisionModCache[base] = { error: e.message };
    return collisionModCache[base];
  }
}

const meshCache = {};
function loadMesh(partId) {
  if (meshCache[partId]) return meshCache[partId];
  let p;
  if (partId === "Object_7") p = KAT + "Object_7.glb";
  else if (partId.startsWith("product_")) p = KAT + partId + ".glb";
  else return null;
  try {
    const m = parseGlbMesh(p);
    meshCache[partId] = m;
    return m;
  } catch (e) {
    return null;
  }
}

function worldBox3(part) {
  const src = loadMesh(part.part_id);
  if (!src) return null;
  const mesh = src.clone();
  mesh.geometry = src.geometry; // share geometry, just re-transform
  mesh.position.set(part.position[0], part.position[1], part.position[2]);
  mesh.quaternion.set(part.quaternion[0], part.quaternion[1], part.quaternion[2], part.quaternion[3]);
  mesh.scale.set(part.scale[0], part.scale[1], part.scale[2]);
  mesh.updateMatrixWorld(true);
  return new THREE.Box3().setFromObject(mesh);
}

// Extract column tag from role, handling both "sloupecN"/"patroM" and
// "colN"/"pM" naming conventions seen across sessions.
function colTagOf(role) {
  if (!role) return null;
  let m = role.match(/sloupec(\d+)/) || role.match(/col(\d+)/);
  return m ? Number(m[1]) : null;
}
function patroTagOf(role) {
  if (!role) return null;
  let m = role.match(/patro(\d+)/) || role.match(/-p(\d+)$/);
  return m ? Number(m[1]) : null;
}
function isBoxRole(role) { return role && role.startsWith("eurobox"); }
function isRailRole(role) { return role && role.startsWith("nosnik"); }

const EUROBOX_HEIGHT_BY_PID = { product_3788: 120, product_3793: 170, product_3794: 220, product_3795: 270, product_3796: 320 };

const report = [];
for (const row of rowsList) {
  const rowFile = `${SCRATCH}/rows/${row.id}.json`;
  let data;
  try { data = JSON.parse(fs.readFileSync(rowFile, "utf8")); } catch (e) { report.push({ id: row.id, name: row.name, error: "no data: " + e.message }); continue; }
  const parts = data.parts || [];
  const carBodyIds = [...new Set(parts.filter(p => p.part_id.startsWith("car_body_")).map(p => Number(p.part_id.slice("car_body_".length))))];
  if (carBodyIds.length === 0) { report.push({ id: row.id, name: row.name, error: "no car_body ref" }); continue; }
  const base = baseForCarBodyId(carBodyIds[0]);
  if (!base) { report.push({ id: row.id, name: row.name, error: "car_body id not found: " + carBodyIds[0] }); continue; }
  const mod = getCollisionModule(base);
  if (mod.error) { report.push({ id: row.id, name: row.name, base, error: "collision module: " + mod.error }); continue; }
  let edCode = vendorCodeForCarBodyId(carBodyIds[0]);
  if (!edCode) {
    // Older car_bodies rows have no "[vendor XX]" tag in their name at all -
    // fall back to extracting the code token directly from the assembly name
    // (e.g. "Berlingo CI03 - boxy..." -> CI03).
    const m = row.name.match(/\b([A-Z]{2}\d{2})\b/);
    if (m) edCode = m[1];
  }
  const ref = edCode ? karoserieRef[edCode] : null;
  const cargoFallbackCeil = (ref && ref.cargoH) ? ref.cargoH - 30 : null;

  // group parts by column tag
  const columns = {};
  for (const p of parts) {
    const c = colTagOf(p.role);
    if (c === null) continue;
    if (!columns[c]) columns[c] = [];
    columns[c].push(p);
  }
  const colResults = [];
  for (const colIdx of Object.keys(columns).map(Number).sort((a, b) => a - b)) {
    const colParts = columns[colIdx];
    const boxParts = colParts.filter(p => isBoxRole(p.role));
    const railParts = colParts.filter(p => isRailRole(p.role));
    if (boxParts.length === 0 || railParts.length === 0) { colResults.push({ colIdx, error: "no box/rail parts" }); continue; }
    // topmost patro
    const maxPatro = Math.max(...boxParts.map(p => patroTagOf(p.role)).filter(x => x !== null));
    const topBoxParts = boxParts.filter(p => patroTagOf(p.role) === maxPatro);
    let topOfStack = -Infinity, boxHeightTop = null;
    for (const bp of topBoxParts) {
      const b3 = worldBox3(bp);
      if (!b3) continue;
      if (b3.max.y > topOfStack) topOfStack = b3.max.y;
      const pid = bp.part_id;
      if (EUROBOX_HEIGHT_BY_PID[pid]) boxHeightTop = EUROBOX_HEIGHT_BY_PID[pid];
    }
    if (!isFinite(topOfStack)) { colResults.push({ colIdx, error: "could not measure top box" }); continue; }
    // column footprint (X/Z) from ALL rail+box parts in this column, real geometry
    let xMin = Infinity, xMax = -Infinity, zMin = Infinity, zMax = -Infinity;
    for (const p of colParts) {
      const b3 = worldBox3(p);
      if (!b3) continue;
      xMin = Math.min(xMin, b3.min.x); xMax = Math.max(xMax, b3.max.x);
      zMin = Math.min(zMin, b3.min.z); zMax = Math.max(zMax, b3.max.z);
    }
    if (!isFinite(xMin)) { colResults.push({ colIdx, error: "no footprint" }); continue; }
    // physCeil: slab spans full footprint, sweep up from topOfStack
    function slab(y) {
      const geo = new THREE.BoxGeometry(Math.max(1, xMax - xMin), 10, Math.max(1, zMax - zMin));
      const mesh = new THREE.Mesh(geo);
      mesh.position.set((xMin + xMax) / 2, y, (zMin + zMax) / 2);
      mesh.updateMatrixWorld(true);
      return mesh;
    }
    let y = topOfStack, steps = 0, collisionY = null;
    const MAXSTEPS = 3000;
    let physCeil, ceilSource;
    if (mod.collidesWithWalls(slab(y))) {
      // The conservative full-footprint slab already touches the real car body
      // AT the currently-built top (e.g. wheel-arch bulge intruding into this
      // column's footprint, or the leg was already extended to the real roof
      // by earlier id=8/id=6 work). Either way: no usable extra headroom here.
      physCeil = topOfStack; ceilSource = "already_at_or_over_slab_ceiling";
    } else {
      while (steps < MAXSTEPS) {
        y += 1; steps++;
        if (mod.collidesWithWalls(slab(y))) { collisionY = y; break; }
      }
      if (collisionY !== null) {
        physCeil = collisionY - 2; ceilSource = "glb_collision";
      } else if (cargoFallbackCeil !== null) {
        // GLB walls for this model don't include a modeled roof/ceiling surface
        // (raycast probe found nothing within reach) - fall back to the
        // official cargo_height_mm (karoserie_model_reference) minus a 30mm
        // safety margin, same convention as shape_geometry_methods.id=8.
        physCeil = cargoFallbackCeil; ceilSource = "cargo_height_fallback";
      } else {
        colResults.push({ colIdx, error: `no collision found within ${MAXSTEPS}mm above topOfStack and no cargo_height_mm fallback available`, topOfStack });
        continue;
      }
    }
    const gap = physCeil - topOfStack;
    colResults.push({ colIdx, topOfStack: Math.round(topOfStack * 10) / 10, physCeil: Math.round(physCeil * 10) / 10, gap: Math.round(gap * 10) / 10, ceilSource, maxPatro, boxHeightTop, flagged: gap >= 180 });
  }
  report.push({ id: row.id, name: row.name, base, columns: colResults });
  process.stderr.write(`done id=${row.id} ${row.name}\n`);
}
console.log(JSON.stringify(report, null, 1));
