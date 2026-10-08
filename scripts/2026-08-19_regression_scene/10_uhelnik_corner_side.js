const THREE = require("three");
const shared = require("/opt/konfigurator/webapp/js/scene-geometry-shared.js");
const {
  baseQuaternion, computeConnectorsLocal, crossAxisHalfWidthTowardDirection,
  worldConnectorsOf, attachEntryToParent, isProfilePart,
} = shared;
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");

const PROFILE_GLB = "/opt/konfigurator/webapp/katalog/profil_30x30_uzavreny.glb";
const UHELNIK_GLB = "/opt/konfigurator/webapp/katalog/product_2895.glb";
const ENABLED_FACES = [1, 5]; // accessory_conn_enabled z DB
const LEARNED_POSE = { face: 1, q: [0.49999999999999994, 0.49999999999999994, -0.5000000000000001, -0.5] };
const ATTACH_OFFSET_MM = 0;

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

// ---- 2 reálné profily tvořící roh (jako Tvar L / roh regálu) ----
function mkProfEntry() {
  const obj = parseGlbMesh(PROFILE_GLB);
  return { part: { length_mm: 1000, cross_section_mm: [30, 30] }, object3d: obj, connectorsLocal: computeConnectorsLocal(obj) };
}
const quatThrough = baseQuaternion(0);
const quatAttach = baseQuaternion(90);
const P = mkProfEntry(); // "pruchozi" - stena, na kterou uhelnik sedne
P.object3d.quaternion.copy(quatThrough);
P.object3d.position.set(0, 0, 0);
P.object3d.updateMatrixWorld(true);
const C = mkProfEntry(); // kolmy dil, celo na stene P
attachEntryToParent(C, P, quatAttach, null, 0);
console.log("roh profilu P<->C:", fmt(touchReport(P, C)), "(kontrola: sam roh musi byt flush)");

// ---- reprodukce uhelnikAutPlaceForPair geometrie (osa P + interval C) ----
const endIdxs = [];
P.connectorsLocal.forEach((cn, i) => { if (cn.kind === "end") endIdxs.push(i); });
const wP = worldConnectorsOf(P);
const axisA = wP[endIdxs[0]].point.clone();
const axisVecFull = wP[endIdxs[1]].point.clone().sub(axisA);
const L = axisVecFull.length();
const axisDir = axisVecFull.clone().normalize();
const cBox = boxOf(C);
let mn = Infinity, mx = -Infinity;
for (let xi = 0; xi < 2; xi++) for (let yi = 0; yi < 2; yi++) for (let zi = 0; zi < 2; zi++) {
  const corner = new THREE.Vector3(xi ? cBox.max.x : cBox.min.x, yi ? cBox.max.y : cBox.min.y, zi ? cBox.max.z : cBox.min.z);
  const tt = corner.clone().sub(axisA).dot(axisDir);
  if (tt < mn) mn = tt;
  if (tt > mx) mx = tt;
}
const cCenter = cBox.getCenter(new THREE.Vector3());
const tC = cCenter.clone().sub(axisA).dot(axisDir);
const foot = axisA.clone().addScaledVector(axisDir, tC);
const dWall = cCenter.clone().sub(foot).normalize();

// ---- reálná geometrie úhelníku, connectorsLocal s wallSnap (partConnectorOpts) ----
function mkUhelnikEntry() {
  const obj = parseGlbMesh(UHELNIK_GLB);
  const part = { name: "Úhelníková spojka 30x30", accessory_conn_enabled: ENABLED_FACES, attach_offset_mm: ATTACH_OFFSET_MM };
  return { part, object3d: obj, connectorsLocal: computeConnectorsLocal(obj, { wallSnap: !isProfilePart(part) }) };
}

// ---- findAccessoryToProfileCandidates (verne opsano) ----
function findAccessoryToProfileCandidates(accEntry, profEntry) {
  const candidates = [];
  const enabledList = Array.isArray(accEntry.part.accessory_conn_enabled) ? accEntry.part.accessory_conn_enabled : null;
  const profWorld = worldConnectorsOf(profEntry);
  profWorld.forEach((pc, pIdx) => {
    if (pc.kind !== "face" && pc.kind !== "end") return;
    accEntry.connectorsLocal.forEach((cc, cIdx) => {
      if (cc.kind !== "face" && cc.kind !== "end") return;
      if (enabledList && !cc.isGeoFace && !enabledList.includes(cIdx)) return;
      const targetDir = pc.normal.clone().negate();
      const localDir = cc.normal.clone().normalize();
      const quat = new THREE.Quaternion().setFromUnitVectors(localDir, targetDir.normalize());
      candidates.push({ type: "accessory-face", forcedParentConnIdx: pIdx, childFaceConnIdx: cIdx, option: { quat } });
    });
  });
  return candidates;
}
function findAccessoryToProfileCandidatesAllSpins(accEntry, profEntry) {
  const base = findAccessoryToProfileCandidates(accEntry, profEntry);
  const out = [];
  base.forEach(c => {
    const localDir = accEntry.connectorsLocal[c.childFaceConnIdx].normal.clone().normalize();
    for (let spin = 0; spin < 4; spin++) {
      const spinQuat = new THREE.Quaternion().setFromAxisAngle(localDir, spin * Math.PI / 2);
      const quat = c.option.quat.clone().multiply(spinQuat);
      out.push({ ...c, spinIndex: spin, option: { quat } });
    }
  });
  return out;
}
function uhelnikCornerFrameQuat(axisDir, side, dWall) {
  const u = axisDir.clone().multiplyScalar(side).normalize();
  const w = new THREE.Vector3().crossVectors(u, dWall).normalize();
  const n2 = new THREE.Vector3().crossVectors(w, u).normalize();
  const m = new THREE.Matrix4().makeBasis(u, n2, w);
  return new THREE.Quaternion().setFromRotationMatrix(m);
}
function uhelnikAutPoseCandidates(accEntry, P, dWall) {
  return findAccessoryToProfileCandidatesAllSpins(accEntry, P).filter(c => {
    const pc = worldConnectorsOf(P)[c.forcedParentConnIdx];
    return pc && pc.kind === "face" && pc.normal.dot(dWall) > 0.7;
  });
}
function applyFaceToFaceCandidate(candidate, childEntry, parentEntry) {
  const quat = candidate.option.quat;
  childEntry.object3d.quaternion.copy(quat);
  childEntry.object3d.position.set(0, 0, 0);
  childEntry.object3d.updateMatrixWorld(true);
  const parentFaceWorld = worldConnectorsOf(parentEntry)[candidate.forcedParentConnIdx];
  const childFaceLocal = childEntry.connectorsLocal[candidate.childFaceConnIdx];
  const rotatedLocalPoint = childFaceLocal.point.clone().applyQuaternion(quat);
  const pos = parentFaceWorld.point.clone().sub(rotatedLocalPoint);
  childEntry.object3d.position.copy(pos);
  childEntry.object3d.updateMatrixWorld(true);
  return true;
}
function uhelnikAutAlignAxial(accEntry, axisA, axisDir, L, t, side) {
  accEntry.object3d.updateMatrixWorld(true);
  const bb = boxOf(accEntry);
  if (bb.isEmpty()) return false;
  let m0 = Infinity, m1 = -Infinity;
  for (let xi = 0; xi < 2; xi++) for (let yi = 0; yi < 2; yi++) for (let zi = 0; zi < 2; zi++) {
    const corner = new THREE.Vector3(xi ? bb.max.x : bb.min.x, yi ? bb.max.y : bb.min.y, zi ? bb.max.z : bb.min.z);
    const tt = corner.clone().sub(axisA).dot(axisDir);
    if (tt < m0) m0 = tt;
    if (tt > m1) m1 = tt;
  }
  const w = m1 - m0;
  let target0;
  if (side > 0) { if (t + w > L + 1) return false; target0 = t; }
  else { if (t - w < -1) return false; target0 = t - w; }
  accEntry.object3d.position.addScaledVector(axisDir, target0 - m0);
  accEntry.object3d.updateMatrixWorld(true);
  return true;
}
function applyAttachTeachOffset(accEntry, connIdx, offMm) {
  if (!offMm) return;
  accEntry.object3d.updateMatrixWorld(true);
  const n = worldConnectorsOf(accEntry)[connIdx].normal.clone().normalize();
  accEntry.object3d.position.addScaledVector(n, offMm);
  accEntry.object3d.updateMatrixWorld(true);
}
function uhelnikAutPlaceOne(accEntry, P, dWall, axisA, axisDir, L, t, side, pose) {
  let cands = uhelnikAutPoseCandidates(accEntry, P, dWall);
  if (!cands.length) { console.log("  ZADNI kandidati!"); return false; }
  const F = uhelnikCornerFrameQuat(axisDir, side, dWall);
  const qRel = new THREE.Quaternion(pose.q[0], pose.q[1], pose.q[2], pose.q[3]);
  const target = F.clone().multiply(qRel);
  let pool = cands.filter(c => c.childFaceConnIdx === pose.face);
  if (!pool.length) pool = cands;
  const localToC = new THREE.Vector3(-1, 0, 0).applyQuaternion(qRel.clone().invert());
  const toC = axisDir.clone().multiplyScalar(-side);
  let bestDot = -Infinity, bestAng = Infinity, cand = pool[0];
  pool.forEach(c => {
    const d = localToC.clone().applyQuaternion(c.option.quat).dot(toC);
    const ang = c.option.quat.angleTo(target);
    if (d > bestDot + 1e-4 || (Math.abs(d - bestDot) <= 1e-4 && ang < bestAng)) { bestDot = d; bestAng = ang; cand = c; }
  });
  applyFaceToFaceCandidate(cand, accEntry, P);
  if (!uhelnikAutAlignAxial(accEntry, axisA, axisDir, L, t, side)) { console.log("  alignAxial selhalo (nevejde se z teto strany)"); return false; }
  applyAttachTeachOffset(accEntry, cand.childFaceConnIdx, ATTACH_OFFSET_MM);
  return true;
}

console.log("");
// Pouze side=1 - v teto 2-profilove testovaci sestave strana -1 LEGITIMNE
// nema kam (alignAxial spravne odmitne, "nevejde se z teto strany") - to
// neni chyba matematiky, jen artefakt maleho rigu. Plny obourohovy pripad
// pokryva realna scena s delsimi profily.
console.log("=== Umisteni uhelniku (side=1), realna geometrie + naucena poza z DB ===");
{
  const accEntry = mkUhelnikEntry();
  const ok = uhelnikAutPlaceOne(accEntry, P, dWall, axisA, axisDir, L, mx, 1, LEARNED_POSE);
  if (!ok) {
    console.log("FAIL: umisteni side=1 selhalo");
  } else {
    const rP = touchReport(accEntry, P), rC = touchReport(accEntry, C);
    console.log("  vs P (stenovy profil): " + fmt(rP));
    console.log("  vs C (kolmy profil):   " + fmt(rC));
    const flushP = Math.abs(rP.x.gap) < 0.01 && Math.abs(rP.x.overlap) < 0.01;
    const flushC = Math.abs(rC.z.gap) < 0.01 && Math.abs(rC.z.overlap) < 0.01;
    console.log(flushP && flushC ? "VSE OK - uhelnik dosedl flush na oba profily" : "FAIL - dotyk neni flush");
  }
}
