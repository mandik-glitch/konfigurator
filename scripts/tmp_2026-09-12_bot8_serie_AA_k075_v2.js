// Nova serie "AA-AE" K-075 (Fiat Doblo) - SPRAVNY soubor tentokrat
// (2026-09-01_bot16_run_pipeline.js, ne batch_pipeline.js). cfg
// odvozeno PRIMO ze skutecnych ulozenych dat (custom_shapes 536/537
// "Noha.1.Fiat_Doblo.H1.1180.349.30x30[.vyrez]"), ne odhadnuto:
// H=1180, CAP_H=260 (z 536), CUTOUT_H_design=440, colRight_design=215,
// capRight=334 (z 537 - shodne s D-T/2=349-15=334, overeno).
const fs = require("fs");
const THREE = require("three");
const { runVehicle } = require("/opt/konfigurator/scripts/2026-09-01_bot16_run_pipeline.js");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const MeshBVHLib = require("/opt/konfigurator/webapp/js/three-mesh-bvh.js");
THREE.BufferGeometry.prototype.computeBoundsTree = MeshBVHLib.computeBoundsTree;
THREE.Mesh.prototype.raycast = MeshBVHLib.acceleratedRaycast;

const BASE = "Fiat_Doblo_FI14_2010-2022";
const KAT = "/opt/konfigurator/webapp/katalog/";

const baseCfg = {
  bodyPrefix: BASE,
  H: 1180, CAP_H: 260,
  CUTOUT_H_design: 440, colRight_design: 215, capRight: 334,
  hasVyrez: true,
};

// ---- 1) REGRESE: vychozi (2mm/20mm), zadne opts ----
const resOld = runVehicle({ ...baseCfg });
if (!resOld.ok) {
  console.log("REGRESE SELHALA:", resOld.reason, "\nlog:", (resOld.log||[]).join("\n"));
  process.exit(1);
}
console.log(`REGRESE OK (2mm/20mm): ${JSON.stringify({legs: resOld.legs, columns: resOld.columns})}`, "\n", (resOld.log||[]).slice(-6).join("\n"));

// ---- 2) NOVA SERIE: 10mm/30mm ----
const resNew = runVehicle({ ...baseCfg, prepazkaBackoffMm: 10, podbehClearanceMm: 30 });
if (!resNew.ok) {
  console.log("NOVA SERIE SELHALA:", resNew.reason, "\nlog:", (resNew.log||[]).join("\n"));
  process.exit(1);
}
console.log(`NOVA SERIE OK (10mm/30mm): legs=${resNew.legs} columns=${resNew.columns}`);
console.log((resNew.log||[]).join("\n"));

const partsOld = resOld.allParts, partsNew = resNew.allParts;
console.log(`\npocet dilu: stary=${partsOld.length} novy=${partsNew.length}`);

// ---- 3) SAT test nove geometrie proti realne karoserii ----
function loadWall(suf) {
  const m = parseGlbMesh(KAT + "car_bodies/" + BASE + suf + ".glb");
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
  const glbPath = KAT + (p.part_id || "Object_7") + ".glb";
  const m = parseGlbMesh(glbPath);
  m.position.set(...p.position);
  m.quaternion.set(...p.quaternion);
  m.scale.set(...p.scale);
  m.updateMatrixWorld(true);
  return m;
}
let satCollisions = 0;
const satResults = [];
for (const p of partsNew) {
  const mesh = partMesh(p);
  const hit = collidesWithWallsReal(mesh);
  if (hit) { satCollisions++; satResults.push({ role: p.role, position: p.position }); }
}
console.log(`\nSAT TEST (edge-raycast, realna GLB geometrie, VSECHNY dily): ${satCollisions}/${partsNew.length} koliduje.`);
if (satCollisions > 0) console.log("KOLIDUJICI:", JSON.stringify(satResults, null, 1));

fs.writeFileSync(__dirname + "/tmp_2026-09-12_serie_AA_K075_parts.json", JSON.stringify(partsNew, null, 0));
fs.writeFileSync(__dirname + "/tmp_2026-09-12_serie_AA_K075_summary.json", JSON.stringify({
  base: BASE, prepazkaBackoffMm: 10, podbehClearanceMm: 30,
  legs: resNew.legs, columns: resNew.columns, partsCount: partsNew.length, satCollisions,
  cfg: baseCfg,
}, null, 1));
console.log("\nUlozeno: tmp_2026-09-12_serie_AA_K075_parts.json, tmp_2026-09-12_serie_AA_K075_summary.json");
