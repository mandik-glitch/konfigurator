const fs = require("fs");
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

// reimplementace localCorners8/sceneLocalCorners8 (viz scene.html) - shodne
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
function virtualEntry(connectorsLocal) {
  return { connectorsLocal, object3d: new THREE.Object3D() };
}
function outerCornerOfPositionJoin(connectorsLocal, throughQuat, childQuat) {
  const through = virtualEntry(connectorsLocal);
  through.object3d.quaternion.copy(throughQuat);
  through.object3d.position.set(0, 0, 0);
  through.object3d.updateMatrixWorld(true);
  const child = virtualEntry(connectorsLocal);
  attachEntryToParent(child, through, childQuat, null, 0);
  return assemblyOuterCornerMin([
    { connectorsLocal, quat: throughQuat, pos: through.object3d.position },
    { connectorsLocal, quat: childQuat, pos: child.object3d.position },
  ]);
}

// ===================== buildLReversedShape (REALNA geometrie) =====================
console.log("=== buildLReversedShape (reálný profil, obrácený spoj) ===");
{
  const entry2 = mkRealEntry();
  const quatThrough2 = baseQuaternion(90);
  const quatChild1 = baseQuaternion(0);
  entry2.object3d.quaternion.copy(quatThrough2);
  const targetCorner2 = outerCornerOfPositionJoin(entry2.connectorsLocal, quatChild1, quatThrough2);
  const naturalCorner2 = outerCornerOfPositionJoin(entry2.connectorsLocal, quatThrough2, quatChild1);
  entry2.object3d.position.copy(targetCorner2.clone().sub(naturalCorner2));
  entry2.object3d.updateMatrixWorld(true);

  const entry1 = mkRealEntry();
  attachEntryToParent(entry1, entry2, quatChild1, null, 0);

  check("1-2 (roh, obrácený spoj)", entry1, entry2);
  const box1 = boxOf(entry1), box2 = boxOf(entry2);
  const outerMin = box1.clone().union(box2).min;
  console.log(`  skutečný vnější roh sestavy: (${outerMin.x.toFixed(4)}, ${outerMin.y.toFixed(4)}, ${outerMin.z.toFixed(4)}) (očekáváno (0,0,0))`);
}

// ===================== buildSpatialLShape (REALNA geometrie) =====================
console.log("\n=== buildSpatialLShape (reálný profil, roh + svislý sloupek) ===");
{
  const quat1 = baseQuaternion(0);
  const quat2 = baseQuaternion(90);

  const entry1 = mkRealEntry();
  entry1.object3d.quaternion.copy(quat1);
  entry1.object3d.position.set(0, 0, 0);
  entry1.object3d.updateMatrixWorld(true);

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

  const shift = spatialLOuterCornerMin(entry1.connectorsLocal, quat1, quat2).negate();
  entry1.object3d.position.copy(shift);
  entry1.object3d.updateMatrixWorld(true);

  const entry2 = mkRealEntry();
  attachEntryToParent(entry2, entry1, quat2, 0, 0);

  const entry3 = mkRealEntry();
  attachEntryToParent(entry3, entry1, baseQuaternion(0, "vertical"), 0, 1);
  const conn0NormalWorld = worldConnectorsOf(entry1)[0].normal.clone();
  const colHalf = crossAxisHalfWidthTowardDirection(entry3.connectorsLocal, entry3.object3d.quaternion, conn0NormalWorld);
  entry3.object3d.position.addScaledVector(conn0NormalWorld, -colHalf);
  entry3.object3d.updateMatrixWorld(true);

  check("1-2 (vodorovný roh)", entry1, entry2);
  check("1-3 (svislý sloupek, konektor 0)", entry1, entry3);

  const outerMin = boxOf(entry1).clone().union(boxOf(entry2)).union(boxOf(entry3)).min;
  console.log(`  skutečný vnější roh sestavy: (${outerMin.x.toFixed(4)}, ${outerMin.y.toFixed(4)}, ${outerMin.z.toFixed(4)}) (očekáváno (0,0,0))`);
}

console.log(`\n${anyBad ? "NALEZEN PROBLÉM (viz FAIL výše)" : "VŠECHNY zkontrolované spoje jsou platný flush styk"}`);
