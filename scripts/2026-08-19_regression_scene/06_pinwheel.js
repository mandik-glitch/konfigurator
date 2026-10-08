const THREE = require("three");
const shared = require("/opt/konfigurator/webapp/js/scene-geometry-shared.js");
const { baseQuaternion, computeConnectorsLocal, attachEntryToParent, worldConnectorsOf, registerJoint } = shared;
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");

const GLB_PATH = "/opt/konfigurator/webapp/katalog/profil_30x30_uzavreny.glb";
function mkRealEntry() {
  const obj = parseGlbMesh(GLB_PATH);
  return { object3d: obj, connectorsLocal: computeConnectorsLocal(obj) };
}
function boxOf(entry) { return new THREE.Box3().setFromObject(entry.object3d); }
function touchReport(a, b) {
  const A = boxOf(a), B = boxOf(b);
  const out = {};
  ["x", "y", "z"].forEach(ax => {
    const gap = Math.max(A.min[ax] - B.max[ax], B.min[ax] - A.max[ax]);
    const overlap = Math.min(A.max[ax], B.max[ax]) - Math.max(A.min[ax], B.min[ax]);
    out[ax] = { gap, overlap };
  });
  return out;
}
function fmt(r) { return ["x", "y", "z"].map(ax => `${ax}:g=${r[ax].gap.toFixed(4)}/o=${r[ax].overlap.toFixed(4)}`).join(" "); }
function isFlush(r, eps) {
  eps = eps == null ? 0.05 : eps;
  const flush = ["x", "y", "z"].filter(ax => Math.abs(r[ax].overlap) <= eps);
  const full = ["x", "y", "z"].filter(ax => r[ax].overlap > eps);
  return flush.length === 1 && full.length === 2;
}
function findFreeEndIdx(entry) {
  if (!entry.usedConn) entry.usedConn = new Set();
  for (let i = 0; i < entry.connectorsLocal.length; i++) {
    if (entry.connectorsLocal[i].kind === "end" && !entry.usedConn.has(i)) return i;
  }
  return -1;
}

// ===== buildSquarePinwheelFrameEntries (verne opsano, 4607-4670) =====
const entry1 = mkRealEntry();
entry1.object3d.quaternion.copy(baseQuaternion(0));
entry1.object3d.position.set(0, 0, 0);
entry1.object3d.updateMatrixWorld(true);

const entry2 = mkRealEntry();
attachEntryToParent(entry2, entry1, baseQuaternion(90), 1, 0);
const entry3 = mkRealEntry();
attachEntryToParent(entry3, entry2, baseQuaternion(180), null, 0);
const entry4 = mkRealEntry();
attachEntryToParent(entry4, entry3, baseQuaternion(270), null, 0);

const idx4 = findFreeEndIdx(entry4);
const idx1 = findFreeEndIdx(entry1);
console.log("volny konec entry4 idx:", idx4, "volny konec entry1 idx:", idx1);

if (idx4 >= 0 && idx1 >= 0) {
  const w4 = worldConnectorsOf(entry4)[idx4];
  const w1 = worldConnectorsOf(entry1)[idx1];
  const dist = w4.point.distanceTo(w1.point);
  console.log(`SKUTECNA vzdalenost mezi volnym koncem dilu4 a dilu1 (mela by byt ~0, jinak smycka NEuzavira): ${dist.toFixed(4)}mm`);
  console.log("  entry4 volny konektor point:", w4.point);
  console.log("  entry1 volny konektor point:", w1.point);
  registerJoint(entry4, idx4, entry1, idx1);
}

console.log("");
console.log("=== Spoje v retezu (1-2, 2-3, 3-4) ===");
["1-2", "2-3", "3-4"].forEach((label, i) => {
  const pairs = [[entry1, entry2], [entry2, entry3], [entry3, entry4]];
  const [a, b] = pairs[i];
  const r = touchReport(a, b);
  console.log(`  ${label}: ${fmt(r)} ${isFlush(r) ? "OK" : "FAIL"}`);
});

console.log("");
console.log("=== Spoj 4-1 (uzavirajici roh smycky - KRITICKY test) ===");
const r41 = touchReport(entry4, entry1);
console.log(`  4-1: ${fmt(r41)} ${isFlush(r41) ? "OK" : "FAIL - SMYCKA SE NEUZAVIRA PRESNE"}`);

// kompletni kolizni kontrola
const all = [entry1, entry2, entry3, entry4];
let collisions = 0;
for (let i = 0; i < all.length; i++) for (let j = i + 1; j < all.length; j++) {
  if ((i === 0 && j === 3)) continue; // sousedi v kruhu (4-1), uz zkontrolovano vyse
  if (j === i + 1) continue; // sousedi v retezu
  const bi = boxOf(all[i]), bj = boxOf(all[j]);
  const ox = Math.min(bi.max.x, bj.max.x) - Math.max(bi.min.x, bj.min.x);
  const oy = Math.min(bi.max.y, bj.max.y) - Math.max(bi.min.y, bj.min.y);
  const oz = Math.min(bi.max.z, bj.max.z) - Math.max(bi.min.z, bj.min.z);
  if (ox > 0.01 && oy > 0.01 && oz > 0.01) { collisions++; console.log(`  KOLIZE mezi dilem ${i+1} a ${j+1}`); }
}
console.log("nesousedni kolize:", collisions);
