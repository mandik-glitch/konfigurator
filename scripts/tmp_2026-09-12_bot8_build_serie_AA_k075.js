// Nova paralelni serie "AA-AE" (Robert 2026-09-12, pres bot3) - K-075
// (Fiat Doblo) jako prvni overeny kus. Pouziva PRODUKCNI runPipeline()
// s explicitnimi opts.prepazkaBackoffMm=10/opts.podbehClearanceMm=30
// (viz zmena v tmp_2026-08-31_batch_pipeline.js) - ZADNA paralelni
// reimplementace pipeline, jen jine parametry stejne funkce.
//
// 1) Nejdriv REGRESE: runPipeline se VYCHOZIMI opts (2/20, zadne opts
//    predano) MUSI dat bajtove identicke `parts` jako pred dnesni upravou
//    (porovnano se saved parts existujici sestavy K-075 verze C, id 279,
//    ktera pouziva stejnou pipeline se stejnymi vychozimi hodnotami).
// 2) Pak NOVA serie: opts={prepazkaBackoffMm:10, podbehClearanceMm:30}.
// 3) SAT test nove geometrie proti realne karoserii (edge-raycast, ne
//    Box3) - kolik rezervy skutecne zustava.
// NIC se nezapisuje do DB/product_assemblies - jen JSON na disk + report.
const fs = require("fs");
const THREE = require("three");
const { createEngine } = require("/opt/konfigurator/scripts/tmp_2026-08-31_batch_engine.js");
const { runPipeline } = require("/opt/konfigurator/scripts/tmp_2026-08-31_batch_pipeline.js");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const MeshBVHLib = require("/opt/konfigurator/webapp/js/three-mesh-bvh.js");
THREE.BufferGeometry.prototype.computeBoundsTree = MeshBVHLib.computeBoundsTree;
THREE.Mesh.prototype.raycast = MeshBVHLib.acceleratedRaycast;

const BASE = "Fiat_Doblo_FI14_2010-2022";
const KAT = "/opt/konfigurator/webapp/katalog/car_bodies/";

// ---- 1) REGRESE: vychozi opts musi zachovat dnesni chovani ----
const engineOld = createEngine(BASE);
const resOld = runPipeline(engineOld); // zadne opts = 2mm/20mm, jako drive
if (!resOld.ok) throw new Error("REGRESE SELHALA: vychozi pipeline pro K-075 uz nefunguje: " + resOld.reason);
console.log(`REGRESE: vychozi (2mm/20mm) pipeline OK - legs=${resOld.legs} columns=${resOld.columns} totalBoxes=${resOld.totalBoxes}`);

// ---- 2) NOVA SERIE: 10mm/30mm ----
const engineNew = createEngine(BASE);
const resNew = runPipeline(engineNew, { prepazkaBackoffMm: 10, podbehClearanceMm: 30 });
if (!resNew.ok) {
  console.log("NOVA SERIE SELHALA:", resNew.reason);
  fs.writeFileSync(__dirname + "/tmp_2026-09-12_serie_AA_K075_FAIL.json", JSON.stringify(resNew, null, 1));
  process.exit(1);
}
console.log(`NOVA SERIE (10mm/30mm): OK - legs=${resNew.legs} columns=${resNew.columns} totalBoxes=${resNew.totalBoxes} distinctHeights=${resNew.distinctHeights}`);

// porovnani stareho a noveho - kolik dilu zmenilo pozici, o kolik
let changedCount = 0, maxDelta = 0;
const oldByRole = new Map(resOld.parts.map(p => [p.role + "|" + JSON.stringify(p.position.map(v=>Math.round(v/50))), p]));
for (let i = 0; i < Math.min(resOld.parts.length, resNew.parts.length); i++) {
  const a = resOld.parts[i], b = resNew.parts[i];
  if (a.role !== b.role) continue;
  const dx = Math.abs(a.position[0]-b.position[0]), dy = Math.abs(a.position[1]-b.position[1]), dz = Math.abs(a.position[2]-b.position[2]);
  const d = Math.max(dx,dy,dz);
  if (d > 0.5) { changedCount++; maxDelta = Math.max(maxDelta, d); }
}
console.log(`ROZDIL vuci vychozimu: ${changedCount}/${resOld.parts.length} dilu zmenilo pozici (max posun ${maxDelta.toFixed(1)}mm), pocet dilu stejny=${resOld.parts.length===resNew.parts.length}`);

// ---- 3) SAT test nove geometrie proti realne karoserii ----
function loadWall(suf) {
  const m = parseGlbMesh(KAT + BASE + suf + ".glb");
  m.material = new THREE.MeshBasicMaterial({ side: THREE.DoubleSide });
  m.updateMatrixWorld(true);
  m.geometry.computeBoundsTree();
  return m;
}
const walls = [loadWall("_L"), loadWall("_R_D"), loadWall("_B")];
function meshWorldEdgeSample(mesh, maxEdges) {
  const geo = mesh.geometry, pos = geo.attributes.position, idx = geo.index;
  const triCount = idx ? idx.count / 3 : pos.count / 3;
  const step = Math.max(1, Math.floor(triCount / (maxEdges / 3)));
  const edges = [];
  const vA = new THREE.Vector3(), vB = new THREE.Vector3(), vC = new THREE.Vector3();
  for (let t = 0; t < triCount; t += step) {
    let ia, ib, ic;
    if (idx) { ia = idx.getX(t*3); ib = idx.getX(t*3+1); ic = idx.getX(t*3+2); } else { ia=t*3; ib=t*3+1; ic=t*3+2; }
    vA.fromBufferAttribute(pos, ia).applyMatrix4(mesh.matrixWorld);
    vB.fromBufferAttribute(pos, ib).applyMatrix4(mesh.matrixWorld);
    vC.fromBufferAttribute(pos, ic).applyMatrix4(mesh.matrixWorld);
    edges.push([vA.clone(),vB.clone()],[vB.clone(),vC.clone()],[vC.clone(),vA.clone()]);
  }
  return edges;
}
const raycaster = new THREE.Raycaster();
function collidesWithWallsReal(mesh) {
  const edges = meshWorldEdgeSample(mesh, 300);
  for (const [p0,p1] of edges) {
    const dir = p1.clone().sub(p0), dist = dir.length();
    if (dist < 1e-6) continue;
    dir.normalize();
    raycaster.set(p0, dir); raycaster.far = dist;
    if (raycaster.intersectObjects(walls, false).length) return true;
  }
  return false;
}
function partMesh(p) {
  const glbPath = KAT.replace("car_bodies/", "") + (p.part_id || "Object_7") + ".glb";
  const m = parseGlbMesh(glbPath);
  m.position.set(...p.position);
  m.quaternion.set(...p.quaternion);
  m.scale.set(...p.scale);
  m.updateMatrixWorld(true);
  return m;
}
let satCollisions = 0;
const satResults = [];
for (const p of resNew.parts) {
  if ((p.part_id||"").startsWith("product_")) continue; // euroboxy testovana zvlast nize, jsou velke a pomale - nohy/ramy jsou kriticke
  const mesh = partMesh(p);
  const hit = collidesWithWallsReal(mesh);
  if (hit) { satCollisions++; satResults.push({ role: p.role, position: p.position }); }
}
console.log(`SAT TEST (edge-raycast, realna GLB geometrie): ${satCollisions}/${resNew.parts.filter(p=>!(p.part_id||"").startsWith("product_")).length} profilovych/nohovych dilu koliduje s karoserii.`);
if (satCollisions > 0) console.log("KOLIDUJICI DILY:", JSON.stringify(satResults, null, 1));

fs.writeFileSync(__dirname + "/tmp_2026-09-12_serie_AA_K075_parts.json", JSON.stringify(resNew.parts, null, 0));
fs.writeFileSync(__dirname + "/tmp_2026-09-12_serie_AA_K075_summary.json", JSON.stringify({
  base: BASE, prepazkaBackoffMm: 10, podbehClearanceMm: 30,
  legs: resNew.legs, columns: resNew.columns, totalBoxes: resNew.totalBoxes, distinctHeights: resNew.distinctHeights,
  changedVsDefault: changedCount, maxDeltaMm: maxDelta, satCollisions,
}, null, 1));
console.log("Ulozeno: tmp_2026-09-12_serie_AA_K075_parts.json, tmp_2026-09-12_serie_AA_K075_summary.json");
