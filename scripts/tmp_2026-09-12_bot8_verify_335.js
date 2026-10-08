// KROK 6 overeni (procedura shape_geometry_methods.id=11) nad vystupem
// tmp_2026-09-12_bot8_batch_335.js (sestava 335, K-075 Doblo L1H1).
//   a) SAT: hranovy raycast VSECH netriveialnich dilu proti REALNE GLB
//      geometrii karoserie (_L/_R_D/_B) - ocekavano 0 kolizi.
//   b) presna mezera (0.000mm) na kazdem svu, ktery skript posunul/
//      dorovnal.
//   c) self-kolize: Box3 prusecik kazdy-s-kazdym (jina role), preskoc
//      zname vnorovaci prekryvy, u ostatnich cekej 0 nad ~2000mm^3.
// part_id -> GLB VYHRADNE pres scripts/2026-09-11_glb_resolver.js (viz
// hlavicka toho souboru - naivni odvozeni z part_id 3x zpusobilo realne
// chyby v tomto projektu).

const fs = require("fs");
const THREE = require("three");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const R = require("/opt/konfigurator/scripts/2026-09-11_glb_resolver.js");
const MeshBVHLib = require("/opt/konfigurator/webapp/js/three-mesh-bvh.js");
THREE.BufferGeometry.prototype.computeBoundsTree = MeshBVHLib.computeBoundsTree;
THREE.Mesh.prototype.raycast = MeshBVHLib.acceleratedRaycast;

const parts = JSON.parse(fs.readFileSync(__dirname + "/tmp_2026-09-12_bot8_batch_335_parts.json", "utf8"));
const KAT = "/opt/konfigurator/webapp/katalog/";
const BASE = "Fiat_Doblo_FI14_2010-2022";

function loadWall(suf) {
  const m = parseGlbMesh(KAT + "car_bodies/" + BASE + suf + ".glb");
  m.material = new THREE.MeshBasicMaterial({ side: THREE.DoubleSide });
  m.updateMatrixWorld(true);
  m.geometry.computeBoundsTree();
  return m;
}
const walls = [loadWall("_L"), loadWall("_R_D"), loadWall("_B")];

function partMesh(p) {
  if (R.jeKaroserie(p.part_id)) return null;
  const glbPath = R.glbPath(p.part_id);
  if (!glbPath) throw new Error(`CHYBI GLB pro part_id=${p.part_id} (role=${p.role}) - resolver nenasel soubor.`);
  const m = parseGlbMesh(glbPath);
  m.position.set(...p.position);
  m.quaternion.set(...p.quaternion);
  m.scale.set(...p.scale);
  m.updateMatrixWorld(true);
  return m;
}

// ---- a) SAT test proti realne karoserii ----
const excludedRoles = (p) => (p.role || "").startsWith("kontrolni-pomucka");
const testable = parts.filter(p => !R.jeKaroserie(p.part_id) && !excludedRoles(p));

const raycaster = new THREE.Raycaster();
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

let collisions = 0;
const collidingList = [];
const meshByIdx = new Array(parts.length).fill(null);
for (let i = 0; i < parts.length; i++) {
  const p = parts[i];
  if (!testable.includes(p)) continue;
  const mesh = partMesh(p);
  meshByIdx[i] = mesh;
  if (collidesWithWallsReal(mesh)) { collisions++; collidingList.push({ role: p.role, part_id: p.part_id, position: p.position }); }
}
console.log(`a) SAT test: ${collisions}/${testable.length} koliduje s realnou karoserii (z celkem ${parts.length} dilu, ${parts.length - testable.length} vynechano - car_body_*/kontrolni-pomucka).`);
if (collisions) console.log("KOLIDUJICI:", JSON.stringify(collidingList, null, 1));

// ---- b) presna mezera na dotcenych svarech ----
function box3Of(idx) {
  const mesh = meshByIdx[idx] || partMesh(parts[idx]);
  return new THREE.Box3().setFromObject(mesh);
}
function findOne(pred) {
  const idx = parts.findIndex(pred);
  if (idx < 0) throw new Error("Dil nenalezen pro gap-check: " + pred.toString());
  return idx;
}
function gapReport(label, idxA, idxB, axis, expectTouchDir) {
  // axis: 'y' nebo 'z'. expectTouchDir: 'A_min_touches_B_max' | 'A_max_touches_B_min'
  const a = box3Of(idxA), b = box3Of(idxB);
  let gap;
  if (expectTouchDir === "A_min_touches_B_max") gap = a.min[axis] - b.max[axis];
  else gap = b.min[axis] - a.max[axis];
  console.log(`b) ${label}: mezera = ${gap.toFixed(6)}mm ${Math.abs(gap) < 0.01 ? "OK (0.000mm)" : "!!! MIMO TOLERANCI !!!"}`);
  return gap;
}

const gaps = [];
// b1) col0 dorovnane patro p0 (nosnik-col0-p0, predni X=-387.5) vs sloupek-pred-podbehem @ leg1 (novy top)
gaps.push(gapReport(
  "col0 p0 (nosnik, X=-387.5) SPODEK vs sloupek-pred-podbehem@leg1 VRCH",
  findOne(p => p.role === "nosnik-col0-p0" && Math.abs(p.position[0] - (-387.5)) < 1),
  findOne(p => p.role === "sloupek-pred-podbehem" && Math.abs(p.position[2] - (-898.5025482177734)) < 1),
  "y", "A_min_touches_B_max"
));
gaps.push(gapReport(
  "col0 p0 (nosnik, X=-706.5) SPODEK vs sloupek-pred-podbehem@leg1 VRCH",
  findOne(p => p.role === "nosnik-col0-p0" && Math.abs(p.position[0] - (-706.5)) < 1),
  findOne(p => p.role === "sloupek-pred-podbehem" && Math.abs(p.position[2] - (-898.5025482177734)) < 1),
  "y", "A_min_touches_B_max"
));

// b2) leg0-strana rigidnich rungu (nosnik-col0-p0..p3, podelnik-celni-
//     spodni-0/zadni-spodni-0, podelnik-celni-horni/zadni-horni) vs
//     predni-svislice@leg0 (nova poloha) - overit ze zustaly flush po
//     zkraceni. predni-svislice@leg0 X=-387.5, zadni-svislice-dolni@leg0
//     X=-706.5 - obe strany noh0.
const legIdxFront = findOne(p => p.role === "predni-svislice" && Math.abs(p.position[2] - (-1350.5025482177734)) < 1);
const legIdxBack = findOne(p => p.role === "zadni-svislice-dolni" && Math.abs(p.position[2] - (-1350.5025482177734)) < 1);
for (const pN of [0, 1, 2, 3]) {
  gaps.push(gapReport(
    `nosnik-col0-p${pN} (X=-387.5) vs predni-svislice@leg0 (nova Z)`,
    findOne(p => p.role === `nosnik-col0-p${pN}` && Math.abs(p.position[0] - (-387.5)) < 1),
    legIdxFront, "z", "A_min_touches_B_max"
  ));
  gaps.push(gapReport(
    `nosnik-col0-p${pN} (X=-706.5) vs zadni-svislice-dolni@leg0 (nova Z)`,
    findOne(p => p.role === `nosnik-col0-p${pN}` && Math.abs(p.position[0] - (-706.5)) < 1),
    legIdxBack, "z", "A_min_touches_B_max"
  ));
}
gaps.push(gapReport("podelnik-celni-spodni-0 vs predni-svislice@leg0", findOne(p => p.role === "podelnik-celni-spodni-0"), legIdxFront, "z", "A_min_touches_B_max"));
gaps.push(gapReport("podelnik-zadni-spodni-0 vs zadni-svislice-dolni@leg0", findOne(p => p.role === "podelnik-zadni-spodni-0"), legIdxBack, "z", "A_min_touches_B_max"));
gaps.push(gapReport("podelnik-celni-horni vs predni-svislice@leg0", findOne(p => p.role === "podelnik-celni-horni"), legIdxFront, "z", "A_min_touches_B_max"));
gaps.push(gapReport("podelnik-zadni-horni vs zadni-svislice-dolni@leg0", findOne(p => p.role === "podelnik-zadni-horni"), legIdxBack, "z", "A_min_touches_B_max"));

const badGaps = gaps.filter(g => Math.abs(g) >= 0.01);
console.log(`\nb) SOUHRN: ${gaps.length} svaru zmereno, ${badGaps.length} mimo toleranci 0.01mm.`);

// ---- c) self-kolize (Box3, kazdy s kazdym jine role, preskoc zname vnorovaci pary) ----
function isNestingPair(rA, rB) {
  const pair = [rA, rB].sort().join("|");
  const rules = [
    (a, b) => a.startsWith("eurobox") && (b.startsWith("nosnik") || b.startsWith("spojnice")),
    (a, b) => a.startsWith("zaslepka") && (b === "predni-svislice" || b === "cap" || b === "zadni-svislice-nad-zarezem" || b === "zadni-svislice-dolni"),
    (a, b) => a.startsWith("logo-ochrana-vypln") && (b === "predni-svislice" || b === "zadni-svislice-nad-zarezem" || b.startsWith("nosnik") || b.startsWith("podelnik")),
  ];
  for (const r of rules) { if (r(rA, rB) || r(rB, rA)) return true; }
  return false;
}
let selfCollisions = 0;
const selfList = [];
const cache = testable.map((p) => ({ p, mesh: partMesh(p) }));
for (let i = 0; i < cache.length; i++) {
  for (let j = i + 1; j < cache.length; j++) {
    const a = cache[i], b = cache[j];
    if (a.p.role === b.p.role) continue; // stejna role - typicky sourozenecke dily (uhelniky, zaslepky), neresime tady
    if (isNestingPair(a.p.role || "", b.p.role || "")) continue;
    const ba = new THREE.Box3().setFromObject(a.mesh), bb = new THREE.Box3().setFromObject(b.mesh);
    if (!ba.intersectsBox(bb)) continue;
    const inter = ba.clone().intersect(bb);
    const size = inter.getSize(new THREE.Vector3());
    const vol = size.x * size.y * size.z;
    if (vol > 2000) {
      selfCollisions++;
      selfList.push({ a: a.p.role, b: b.p.role, overlap_mm: [size.x, size.y, size.z].map(v => +v.toFixed(2)), vol_mm3: +vol.toFixed(0) });
    }
  }
}
console.log(`\nc) Self-prekryv (Box3, kazdy s kazdym jina role, znamé vnorovaci pary preskoceny, prah 2000mm^3): ${selfCollisions} nalezu z ${cache.length * (cache.length - 1) / 2} paru.`);
if (selfCollisions) console.log(JSON.stringify(selfList, null, 1));

fs.writeFileSync(__dirname + "/tmp_2026-09-12_bot8_verify_335_report.json", JSON.stringify({
  sat_tested: testable.length, sat_collisions: collisions, collidingList,
  gaps_tested: gaps.length, gaps_bad: badGaps.length, gaps,
  self_pairs_tested: cache.length * (cache.length - 1) / 2, self_collisions: selfCollisions, selfList,
}, null, 1));
console.log("\nUlozeno: tmp_2026-09-12_bot8_verify_335_report.json");

const overallOk = collisions === 0 && badGaps.length === 0 && selfCollisions === 0;
console.log("\n=== VYSLEDEK:", overallOk ? "VSE V PORADKU" : "PROBLEM NALEZEN", "===");
process.exit(overallOk ? 0 : 1);
