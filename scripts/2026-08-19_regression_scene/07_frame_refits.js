const THREE = require("three");
const shared = require("/opt/konfigurator/webapp/js/scene-geometry-shared.js");
const { baseQuaternion, computeConnectorsLocal, crossAxisHalfWidthTowardDirection,
        worldConnectorsOf, attachEntryToParent, applyLengthScale } = shared;
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");

const GLB = "/opt/konfigurator/webapp/katalog/profil_30x30_uzavreny.glb";
const W = 30;
function mkEntry() {
  const obj = parseGlbMesh(GLB);
  return { object3d: obj, connectorsLocal: computeConnectorsLocal(obj) };
}
function boxOf(e) { return new THREE.Box3().setFromObject(e.object3d); }
function touchReport(a, b) {
  const A = boxOf(a), B = boxOf(b);
  const out = {};
  ["x", "y", "z"].forEach(ax => {
    out[ax] = {
      gap: Math.max(A.min[ax] - B.max[ax], B.min[ax] - A.max[ax]),
      overlap: Math.min(A.max[ax], B.max[ax]) - Math.max(A.min[ax], B.min[ax]),
    };
  });
  return out;
}
function fmt(r) { return ["x","y","z"].map(ax => `${ax}:g=${r[ax].gap.toFixed(4)}/o=${r[ax].overlap.toFixed(4)}`).join(" "); }
function isFlush(r, eps) {
  eps = eps == null ? 0.05 : eps;
  const f = ["x","y","z"].filter(ax => Math.abs(r[ax].overlap) <= eps);
  const o = ["x","y","z"].filter(ax => r[ax].overlap > eps);
  return f.length === 1 && o.length === 2;
}
let anyBad = false;
function check(label, a, b) {
  const r = touchReport(a, b);
  const ok = isFlush(r);
  if (!ok) anyBad = true;
  console.log(`  ${ok ? "OK  " : "FAIL"} ${label}: ${fmt(r)}`);
}
function profileLengthAxisWorld(entry) {
  const idxs = [];
  entry.connectorsLocal.forEach((c, i) => { if (c.kind === "end") idxs.push(i); });
  if (idxs.length !== 2) return null;
  const w = worldConnectorsOf(entry);
  return w[idxs[1]].point.clone().sub(w[idxs[0]].point).normalize();
}

// ================== 1) RECT FRAME (buildSquareFrameEntries verna reprodukce) + refitRectFrameEntries ==================
function buildRect() {
  const quatThrough = baseQuaternion(0), quatAttach = baseQuaternion(90);
  const entryA = mkEntry();
  const objA = entryA.object3d;
  objA.quaternion.copy(quatThrough); objA.position.set(0,0,0); objA.updateMatrixWorld(true);
  const L = entryA.connectorsLocal[0].point.distanceTo(entryA.connectorsLocal[1].point);
  const attachDir = entryA.connectorsLocal[1].point.clone().sub(entryA.connectorsLocal[0].point).applyQuaternion(quatAttach).normalize();
  const halfA = crossAxisHalfWidthTowardDirection(entryA.connectorsLocal, objA.quaternion, attachDir);
  const centerDist = L - 2 * halfA;
  const rot0 = entryA.connectorsLocal[0].point.clone().applyQuaternion(quatThrough);
  objA.position.copy(rot0.clone().negate()).addScaledVector(attachDir, halfA);
  objA.updateMatrixWorld(true);
  const entryB = mkEntry();
  entryB.object3d.quaternion.copy(quatThrough);
  entryB.object3d.position.copy(objA.position).addScaledVector(attachDir, centerDist);
  entryB.object3d.updateMatrixWorld(true);
  function placeAttached(endIdx) {
    const entry = mkEntry();
    const obj = entry.object3d;
    obj.quaternion.copy(quatAttach); obj.position.set(0,0,0); obj.updateMatrixWorld(true);
    const wcA = worldConnectorsOf(entryA)[endIdx];
    const otherEnd = 1 - endIdx;
    const outward = entryA.connectorsLocal[endIdx].point.clone().sub(entryA.connectorsLocal[otherEnd].point).applyQuaternion(objA.quaternion).normalize();
    const halfAlong = crossAxisHalfWidthTowardDirection(entry.connectorsLocal, quatAttach, outward);
    const target = wcA.point.clone().addScaledVector(attachDir, halfA).addScaledVector(outward, -halfAlong);
    const rotL = entry.connectorsLocal[0].point.clone().applyQuaternion(quatAttach);
    obj.position.copy(target.clone().sub(rotL)); obj.updateMatrixWorld(true);
    const L0 = entry.connectorsLocal[0].point.distanceTo(entry.connectorsLocal[1].point);
    const targetLen = centerDist - 2 * halfA;
    applyLengthScale(entry, targetLen / L0, 0);
    return entry;
  }
  const entryC = placeAttached(0);
  const entryD = placeAttached(1);
  return { entryA, entryB, entryC, entryD };
}

// ===== PRESNA KOPIE refitRectFrameEntries (scene.html 22133-22182) =====
function refitRectFrameEntries(frameMeta, newLy, newLx) {
  const { entryA, entryB, entryC, entryD } = frameMeta;
  const localLenA = entryA.connectorsLocal[0].point.distanceTo(entryA.connectorsLocal[1].point);
  const localLenB = entryB.connectorsLocal[0].point.distanceTo(entryB.connectorsLocal[1].point);
  const localLenC = entryC.connectorsLocal[0].point.distanceTo(entryC.connectorsLocal[1].point);
  const localLenD = entryD.connectorsLocal[0].point.distanceTo(entryD.connectorsLocal[1].point);
  const wcA0 = worldConnectorsOf(entryA)[0].point.clone();
  const yDir = worldConnectorsOf(entryA)[1].point.clone().sub(wcA0).normalize();
  const xDir = worldConnectorsOf(entryB)[0].point.clone().sub(wcA0).normalize();
  const half = crossAxisHalfWidthTowardDirection(entryA.connectorsLocal, entryA.object3d.quaternion, xDir);
  if (newLy != null) {
    applyLengthScale(entryA, newLy / localLenA, 0);
    applyLengthScale(entryB, newLy / localLenB, 0);
  }
  {
    const wcA1 = worldConnectorsOf(entryA)[1].point;
    const halfD = crossAxisHalfWidthTowardDirection(entryD.connectorsLocal, entryD.object3d.quaternion, yDir);
    const target = wcA1.clone().addScaledVector(xDir, half).addScaledVector(yDir, -halfD);
    const beforeD0 = worldConnectorsOf(entryD)[0].point.clone();
    const delta = target.clone().sub(beforeD0);
    entryD.object3d.position.add(delta);
    entryD.object3d.updateMatrixWorld(true);
  }
  if (newLx != null) {
    const newCenterDist = newLx - 2 * half;
    entryB.object3d.position.copy(entryA.object3d.position).addScaledVector(xDir, newCenterDist);
    entryB.object3d.updateMatrixWorld(true);
    const newLenCD = newCenterDist - 2 * half;
    applyLengthScale(entryC, newLenCD / localLenC, 0);
    applyLengthScale(entryD, newLenCD / localLenD, 0);
  }
}
// ===== konec presne kopie =====

console.log("=== RECT FRAME refit 1000x1000 -> 800x600 (realna geometrie) ===");
const rect = buildRect();
refitRectFrameEntries(rect, 800, 600);
check("A-C", rect.entryA, rect.entryC);
check("C-B", rect.entryC, rect.entryB);
check("A-D", rect.entryA, rect.entryD);
check("D-B", rect.entryD, rect.entryB);
{
  const box = new THREE.Box3();
  [rect.entryA, rect.entryB, rect.entryC, rect.entryD].forEach(e => box.union(boxOf(e)));
  const s = box.getSize(new THREE.Vector3());
  console.log(`  vnejsi rozmer po refitu: x=${s.x.toFixed(4)} z=${s.z.toFixed(4)} (ocekavano 600 x 800)`);
  if (Math.abs(s.x - 600) > 0.05 || Math.abs(s.z - 800) > 0.05) { anyBad = true; console.log("  FAIL - rozmer nesedi"); }
}

// ================== 2) PINWHEEL (verna reprodukce) + refitPinwheelFrameEntries ==================
function findFreeEndIdx(entry) {
  if (!entry.usedConn) entry.usedConn = new Set();
  for (let i = 0; i < entry.connectorsLocal.length; i++) {
    if (entry.connectorsLocal[i].kind === "end" && !entry.usedConn.has(i)) return i;
  }
  return -1;
}
function buildPinwheel() {
  const e1 = mkEntry();
  e1.object3d.quaternion.copy(baseQuaternion(0));
  e1.object3d.position.set(0,0,0);
  e1.object3d.updateMatrixWorld(true);
  const e2 = mkEntry(); attachEntryToParent(e2, e1, baseQuaternion(90), 1, 0);
  const e3 = mkEntry(); attachEntryToParent(e3, e2, baseQuaternion(180), null, 0);
  const e4 = mkEntry(); attachEntryToParent(e4, e3, baseQuaternion(270), null, 0);
  // kotva na vnejsi roh (presne jako produkce)
  const all = [e1, e2, e3, e4];
  const box = new THREE.Box3();
  all.forEach(e => box.union(boxOf(e)));
  const shift = new THREE.Vector3(-box.min.x, 0, -box.min.z);
  all.forEach(e => { e.object3d.position.add(shift); e.object3d.updateMatrixWorld(true); });
  return { entryA: e1, entryB: e3, entryC: e2, entryD: e4 };
}
// ===== PRESNE KOPIE pinwheelFrameAxes/currentPinwheelFrameDims/refitPinwheelFrameEntries =====
function pinwheelFrameAxes(frameMeta) {
  const { entryA, entryC } = frameMeta;
  const uDir = profileLengthAxisWorld(entryA);
  const vDir = profileLengthAxisWorld(entryC);
  if (!uDir || !vDir) return null;
  const dom = d => {
    const a = [Math.abs(d.x), Math.abs(d.y), Math.abs(d.z)];
    return ["x","y","z"][a.indexOf(Math.max(...a))];
  };
  const uAxis = dom(uDir), vAxis = dom(vDir);
  if (uAxis === vAxis) return null;
  return { uAxis, vAxis };
}
function currentPinwheelFrameDims(frameMeta) {
  const ax = pinwheelFrameAxes(frameMeta);
  if (!ax) return { Ly: 0, Lx: 0 };
  const box = new THREE.Box3();
  [frameMeta.entryA, frameMeta.entryB, frameMeta.entryC, frameMeta.entryD].forEach(e => box.union(new THREE.Box3().setFromObject(e.object3d)));
  return { Ly: box.max[ax.uAxis] - box.min[ax.uAxis], Lx: box.max[ax.vAxis] - box.min[ax.vAxis] };
}
function refitPinwheelFrameEntries(frameMeta, newLy, newLx) {
  const { entryA, entryB, entryC, entryD } = frameMeta;
  const ax = pinwheelFrameAxes(frameMeta);
  if (!ax) return;
  const all = [entryA, entryB, entryC, entryD];
  const boxOfE = e => new THREE.Box3().setFromObject(e.object3d);
  const outer = new THREE.Box3();
  all.forEach(e => outer.union(boxOfE(e)));
  const cur = currentPinwheelFrameDims(frameMeta);
  const Ly = newLy != null ? newLy : cur.Ly;
  const Lx = newLx != null ? newLx : cur.Lx;
  const bA = boxOfE(entryA);
  const w = bA.max[ax.vAxis] - bA.min[ax.vAxis];
  if (!(w > 0) || !(Ly > w) || !(Lx > w)) return;
  const u0 = outer.min[ax.uAxis], v0 = outer.min[ax.vAxis];
  const setLen = (entry, targetLen) => {
    const localLen = entry.connectorsLocal[0].point.distanceTo(entry.connectorsLocal[1].point);
    if (localLen > 0 && targetLen > 0) applyLengthScale(entry, targetLen / localLen, 0);
    entry.object3d.updateMatrixWorld(true);
  };
  setLen(entryA, Ly - w);
  setLen(entryB, Ly - w);
  setLen(entryC, Lx - w);
  setLen(entryD, Lx - w);
  const place = (entry, uMin, vMin) => {
    entry.object3d.updateMatrixWorld(true);
    const b = boxOfE(entry);
    const d = new THREE.Vector3();
    d[ax.uAxis] = (u0 + uMin) - b.min[ax.uAxis];
    d[ax.vAxis] = (v0 + vMin) - b.min[ax.vAxis];
    entry.object3d.position.add(d);
    entry.object3d.updateMatrixWorld(true);
  };
  place(entryA, w, 0);
  place(entryC, Ly - w, w);
  place(entryB, 0, Lx - w);
  place(entryD, 0, 0);
}
// ===== konec presnych kopii =====

console.log("");
console.log("=== PINWHEEL refit -> 800x600 (realna geometrie) ===");
const pin = buildPinwheel();
const before = currentPinwheelFrameDims(pin);
console.log(`  pred refitem: Ly=${before.Ly.toFixed(4)} Lx=${before.Lx.toFixed(4)}`);
refitPinwheelFrameEntries(pin, 800, 600);
// sousedni pary ve vetrniku: A(=1)-C(=2), C(=2)-B(=3), B(=3)-D(=4), D(=4)-A(=1)
check("A-C (1-2)", pin.entryA, pin.entryC);
check("C-B (2-3)", pin.entryC, pin.entryB);
check("B-D (3-4)", pin.entryB, pin.entryD);
check("D-A (4-1)", pin.entryD, pin.entryA);
{
  const after = currentPinwheelFrameDims(pin);
  console.log(`  po refitu: Ly=${after.Ly.toFixed(4)} Lx=${after.Lx.toFixed(4)} (ocekavano 800 x 600)`);
  if (Math.abs(after.Ly - 800) > 0.05 || Math.abs(after.Lx - 600) > 0.05) { anyBad = true; console.log("  FAIL - rozmer nesedi"); }
  // kolize nesousednich (A-B a C-D)
  [["A-B", pin.entryA, pin.entryB], ["C-D", pin.entryC, pin.entryD]].forEach(([l, a, b]) => {
    const bi = boxOf(a), bj = boxOf(b);
    const ox = Math.min(bi.max.x,bj.max.x)-Math.max(bi.min.x,bj.min.x);
    const oy = Math.min(bi.max.y,bj.max.y)-Math.max(bi.min.y,bj.min.y);
    const oz = Math.min(bi.max.z,bj.max.z)-Math.max(bi.min.z,bj.min.z);
    if (ox > 0.01 && oy > 0.01 && oz > 0.01) { anyBad = true; console.log(`  KOLIZE ${l}`); }
  });
}

console.log(`\n${anyBad ? "NALEZEN PROBLEM" : "VSE OK"}`);
