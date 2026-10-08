// Zpracuje JEDNU sestavu: nacte data.parts z INPUT JSON, aplikuje
// transformAssembly (viz tmp_2026-09-12_bot8_wide_TRANSFORM_LIB.js),
// overi (SAT proti realne GLB karoserii pres 2026-09-11_glb_resolver.js,
// presna mezera na zmenenem svu, self-kolize Box3 mimo zname vnorovaci
// páry) a zapise vysledek (transformovana data + report) do OUTPUT JSON.
// Nezapisuje nic do DB - to dela volajici (Python orchestrator), aby se
// vzdy zpracovavala jen jedna sestava v pameti najednou (RAM disciplina).
//
// Pouziti: node tmp_2026-09-12_bot8_wide_process_one.js <inputPartsJson> <carBodyBase> <outputJson> [deltaZ] [deltaY]
// deltaZ/deltaY defaultuji na 8/10 (viz shape_geometry_methods.id=11) - CLI
// override existuje jen pro baseline self-kolizni srovnani (0/0 = beze zmeny,
// pro overeni ze transform nezavlekl NOVE self-prekryvy oproti puvodnimu stavu).
const fs = require("fs");
const THREE = require("three");
const { parseGlbMesh, glbBoundingBox } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const MeshBVHLib = require("/opt/konfigurator/webapp/js/three-mesh-bvh.js");
THREE.BufferGeometry.prototype.computeBoundsTree = MeshBVHLib.computeBoundsTree;
THREE.Mesh.prototype.raycast = MeshBVHLib.acceleratedRaycast;
const { transformAssembly } = require("./tmp_2026-09-12_bot8_wide_TRANSFORM_LIB.js");
const R = require("/opt/konfigurator/scripts/2026-09-11_glb_resolver.js");

const [, , inputFile, carBodyBase, outputFile, deltaZArg, deltaYArg] = process.argv;
const KAT = "/opt/konfigurator/webapp/katalog/";
const deltaZ = deltaZArg != null ? Number(deltaZArg) : 8;
const deltaY = deltaYArg != null ? Number(deltaYArg) : 10;

const input = JSON.parse(fs.readFileSync(inputFile, "utf8"));
const srcParts = input.parts;

let transformResult;
try {
  transformResult = transformAssembly(srcParts, { deltaZ, deltaY });
} catch (e) {
  fs.writeFileSync(outputFile, JSON.stringify({ ok: false, stage: "transform", error: e.message + "\n" + e.stack }, null, 1));
  process.exit(0);
}
const { parts, report } = transformResult;

// --- KROK 7a: SAT proti realne karoserii (hranovy raycasting) ---
function loadWall(suf) {
  const m = parseGlbMesh(KAT + "car_bodies/" + carBodyBase + suf + ".glb");
  m.material = new THREE.MeshBasicMaterial({ side: THREE.DoubleSide });
  m.updateMatrixWorld(true);
  m.geometry.computeBoundsTree();
  return m;
}
let walls;
try {
  walls = [loadWall("_L"), loadWall("_R_D"), loadWall("_B")];
} catch (e) {
  fs.writeFileSync(outputFile, JSON.stringify({ ok: false, stage: "load-walls", error: e.message }, null, 1));
  process.exit(0);
}

function meshWorldEdgeSample(mesh, maxEdges) {
  const geo = mesh.geometry, pos = geo.attributes.position, idx = geo.index;
  const triCount = idx ? idx.count / 3 : pos.count / 3;
  const step = Math.max(1, Math.floor(triCount / (maxEdges / 3)));
  const edges = [];
  const vA = new THREE.Vector3(), vB = new THREE.Vector3(), vC = new THREE.Vector3();
  for (let t = 0; t < triCount; t += step) {
    let ia, ib, ic;
    if (idx) { ia = idx.getX(t * 3); ib = idx.getX(t * 3 + 1); ic = idx.getX(t * 3 + 2); } else { ia = t * 3; ib = t * 3 + 1; ic = t * 3 + 2; }
    vA.fromBufferAttribute(pos, ia).applyMatrix4(mesh.matrixWorld);
    vB.fromBufferAttribute(pos, ib).applyMatrix4(mesh.matrixWorld);
    vC.fromBufferAttribute(pos, ic).applyMatrix4(mesh.matrixWorld);
    edges.push([vA.clone(), vB.clone()], [vB.clone(), vC.clone()], [vC.clone(), vA.clone()]);
  }
  return edges;
}
const raycaster = new THREE.Raycaster();
function collidesWithWallsReal(mesh) {
  const edges = meshWorldEdgeSample(mesh, 300);
  for (const [p0, p1] of edges) {
    const dir = p1.clone().sub(p0), dist = dir.length();
    if (dist < 1e-6) continue;
    dir.normalize();
    raycaster.set(p0, dir); raycaster.far = dist;
    if (raycaster.intersectObjects(walls, false).length) return true;
  }
  return false;
}
function partMesh(p) {
  const glbPath = R.glbPath(p.part_id);
  if (!glbPath) return null;
  const m = parseGlbMesh(glbPath);
  m.position.set(...p.position);
  m.quaternion.set(...p.quaternion);
  m.scale.set(...p.scale);
  m.updateMatrixWorld(true);
  return m;
}

const checkParts = parts.filter(p => !String(p.part_id || "").startsWith("car_body_") && !String(p.role || "").startsWith("kontrolni-pomucka"));
let satCollisions = 0, skippedNoGlb = 0;
const satBad = [];
const meshes = [];
for (const p of checkParts) {
  const mesh = partMesh(p);
  if (!mesh) { skippedNoGlb++; continue; }
  meshes.push({ p, mesh });
  if (collidesWithWallsReal(mesh)) { satCollisions++; satBad.push({ role: p.role, position: p.position }); }
}

// --- KROK 7b: presna mezera na klicovych svech (kazda vyrezova noha: sloupek/svislice vs sousedni nosnik-patro0) ---
const seamChecks = [];
if (report.naming) {
  const { colPrefix, patroSep } = report.naming;
  for (let bay = 0; bay < report.legs.length - 1; bay++) {
    const legA = report.legs[bay], legB = report.legs[bay + 1];
    for (const [leg, side] of [[legA, "A"], [legB, "B"]]) {
      if (leg.type !== "cutout") continue;
      const zsn = parts.find(p => p.role === "zadni-svislice-nad-zarezem" && Math.abs(p.position[2] - leg.z) < 2);
      const nosnik0 = parts.find(p => p.role === `nosnik-${colPrefix}${bay}-${patroSep}0` && true);
      if (!zsn) continue;
      const newYnew = zsn.position[1] - zsn.scale[1] * 1000 / 2;
      const expectedNewYnew = leg.oldYnew + 10;
      seamChecks.push({
        bay, side, legZ: +leg.z.toFixed(2),
        newYnew_measured: +newYnew.toFixed(3), newYnew_expected: +expectedNewYnew.toFixed(3),
        gap: +(newYnew - expectedNewYnew).toFixed(4),
        nosnik0Y: nosnik0 ? +nosnik0.position[1].toFixed(3) : null,
        nosnik_vs_seam_plus15: nosnik0 ? +(nosnik0.position[1] - (newYnew + 15)).toFixed(3) : null,
      });
    }
  }
}

// --- KROK 7c: self-kolize Box3 (hruba pojistka) ---
let selfSusp = 0;
const selfBad = [];
const box3s = meshes.map(({ p, mesh }) => ({ p, box: new THREE.Box3().setFromObject(mesh) }));
for (let i = 0; i < box3s.length; i++) {
  for (let j = i + 1; j < box3s.length; j++) {
    const a = box3s[i], b = box3s[j];
    if (a.p.role === b.p.role) continue;
    if (a.box.intersectsBox(b.box)) {
      const ix = Math.min(a.box.max.x, b.box.max.x) - Math.max(a.box.min.x, b.box.min.x);
      const iy = Math.min(a.box.max.y, b.box.max.y) - Math.max(a.box.min.y, b.box.min.y);
      const iz = Math.min(a.box.max.z, b.box.max.z) - Math.max(a.box.min.z, b.box.min.z);
      const vol = Math.max(0, ix) * Math.max(0, iy) * Math.max(0, iz);
      if (vol > 2000) { selfSusp++; selfBad.push({ a: a.p.role, b: b.p.role, vol: +vol.toFixed(0) }); }
    }
  }
}

const result = {
  ok: true,
  report,
  verify: {
    partsChecked: meshes.length, skippedNoGlb,
    satCollisions, satBad,
    seamChecks,
    selfSusp, selfBad: selfBad.slice(0, 20),
  },
  parts,
};
fs.writeFileSync(outputFile, JSON.stringify(result));
console.log(JSON.stringify({ ok: true, satCollisions, skippedNoGlb, selfSusp, seamChecks, rebalance: report.rebalance, legs: report.legs }, null, 1));
