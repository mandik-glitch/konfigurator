const THREE = require("three");
const shared = require("/opt/konfigurator/webapp/js/scene-geometry-shared.js");
const {
  baseQuaternion, computeConnectorsLocal, crossAxisHalfWidthTowardDirection,
  worldConnectorsOf, attachEntryToParent,
} = shared;
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
  eps = eps == null ? 0.01 : eps;
  const flush = ["x", "y", "z"].filter(ax => Math.abs(r[ax].overlap) <= eps);
  const full = ["x", "y", "z"].filter(ax => r[ax].overlap > eps);
  return flush.length === 1 && full.length === 2;
}
let anyBad = false;
function check(label, a, b) {
  const r = touchReport(a, b);
  const ok = isFlush(r);
  if (!ok) anyBad = true;
  console.log(`  ${ok ? "OK  " : "FAIL"} ${label}: ${fmt(r)}`);
}

// verne reprodukovano ze scene.html buildSpatialLReversedShape (4363-4408)
const quat1 = baseQuaternion(0);
const quat2 = baseQuaternion(90);

const entry2 = mkRealEntry();
entry2.object3d.quaternion.copy(quat2);
entry2.object3d.position.set(0, 0, 0);
entry2.object3d.updateMatrixWorld(true);

// spatialLOuterCornerMin - stejna reprodukce jako u nereverzovane varianty
function virtualEntry(connectorsLocal) { return { connectorsLocal, object3d: new THREE.Object3D() }; }
function localCorners8(connectorsLocal) {
  const center = connectorsLocal[0].point.clone().add(connectorsLocal[1].point).multiplyScalar(0.5);
  const lengthVec = connectorsLocal[0].point.clone().sub(center);
  const cross = connectorsLocal.crossAxesLocal;
  const out = [];
  [1, -1].forEach(sL => [1, -1].forEach(sA => [1, -1].forEach(sB => {
    out.push(center.clone().addScaledVector(lengthVec, sL).addScaledVector(cross[0].dir, sA * cross[0].halfWidth).addScaledVector(cross[1].dir, sB * cross[1].halfWidth));
  })));
  return out;
}
function assemblyOuterCornerMin(parts) {
  const min = new THREE.Vector3(Infinity, Infinity, Infinity);
  parts.forEach(p => {
    localCorners8(p.connectorsLocal).forEach(c => {
      const wc = c.clone().multiply(p.scale || new THREE.Vector3(1, 1, 1)).applyQuaternion(p.quat).add(p.pos);
      min.min(wc);
    });
  });
  return min;
}
function spatialLOuterCornerMin(connectorsLocal, throughQuat, attachQuat) {
  const through = virtualEntry(connectorsLocal);
  through.object3d.quaternion.copy(throughQuat);
  through.object3d.position.set(0, 0, 0);
  through.object3d.updateMatrixWorld(true);
  const attached = virtualEntry(connectorsLocal);
  attachEntryToParent(attached, through, attachQuat, 0, 0);
  const column = virtualEntry(connectorsLocal);
  attachEntryToParent(column, through, baseQuaternion(0, "vertical"), 0, 1);
  const conn0NormalWorld = worldConnectorsOf(through)[0].normal.clone();
  const colHalf = crossAxisHalfWidthTowardDirection(column.connectorsLocal, column.object3d.quaternion, conn0NormalWorld);
  column.object3d.position.addScaledVector(conn0NormalWorld, -colHalf);
  column.object3d.updateMatrixWorld(true);
  return assemblyOuterCornerMin([
    { connectorsLocal, quat: through.object3d.quaternion, pos: through.object3d.position },
    { connectorsLocal, quat: attached.object3d.quaternion, pos: attached.object3d.position },
    { connectorsLocal, quat: column.object3d.quaternion, pos: column.object3d.position },
  ]);
}

const shift = spatialLOuterCornerMin(entry2.connectorsLocal, quat2, quat1).negate();
entry2.object3d.position.copy(shift);
entry2.object3d.updateMatrixWorld(true);

const entry1 = mkRealEntry();
attachEntryToParent(entry1, entry2, quat1, 0, 0);

const entry3 = mkRealEntry();
attachEntryToParent(entry3, entry2, baseQuaternion(0, "vertical"), 0, 1);
const conn0NormalWorld = worldConnectorsOf(entry2)[0].normal.clone();
const colHalf = crossAxisHalfWidthTowardDirection(entry3.connectorsLocal, entry3.object3d.quaternion, conn0NormalWorld);
entry3.object3d.position.addScaledVector(conn0NormalWorld, -colHalf);
entry3.object3d.updateMatrixWorld(true);

console.log("=== buildSpatialLReversedShape (reálný profil s pivot-offsetem) ===");
check("2-1 (vodorovný roh, obrácené role)", entry2, entry1);
check("2-3 (svislý sloupek, konektor 0)", entry2, entry3);
const outerMin = boxOf(entry1).clone().union(boxOf(entry2)).union(boxOf(entry3)).min;
console.log(`  vnější roh (jen informativně, viz Robertovo "nezáleží na absolutní pozici"): (${outerMin.x.toFixed(4)}, ${outerMin.y.toFixed(4)}, ${outerMin.z.toFixed(4)})`);
console.log(`\n${anyBad ? "NALEZEN PROBLÉM" : "OK - platný flush styk"}`);
