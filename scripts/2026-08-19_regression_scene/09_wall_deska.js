const THREE = require("three");
const shared = require("/opt/konfigurator/webapp/js/scene-geometry-shared.js");
const { baseQuaternion, computeConnectorsLocal, worldConnectorsOf, isProfilePart } = shared;
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");

const PROFILE_GLB = "/opt/konfigurator/webapp/katalog/profil_30x30_uzavreny.glb";
const DESKA_GLB = "/opt/konfigurator/webapp/katalog/product_3316.glb";

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

const P = { object3d: parseGlbMesh(PROFILE_GLB), connectorsLocal: null };
P.connectorsLocal = computeConnectorsLocal(P.object3d);
P.object3d.quaternion.copy(baseQuaternion(0));
P.object3d.position.set(0, 0, 0);
P.object3d.updateMatrixWorld(true);

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
}

const obj = parseGlbMesh(DESKA_GLB);
const part = { name: "Čtyřcestná spojovací deska 30x30", accessory_conn_enabled: null, attach_offset_mm: 0 };
const accEntry = { part, object3d: obj, connectorsLocal: computeConnectorsLocal(obj, { wallSnap: !isProfilePart(part) }) };

function accessoryThinFaceIdx(accEntry, obj2) {
  const accFaceIdxs = [];
  accEntry.connectorsLocal.forEach((c, i) => { if (c.kind === "face") accFaceIdxs.push(i); });
  if (!accFaceIdxs.length) return null;
  obj2.updateMatrixWorld(true);
  const accWorld = worldConnectorsOf(accEntry);
  const accCenter = new THREE.Box3().setFromObject(obj2).getCenter(new THREE.Vector3());
  let thinFaceIdx = null, thinDist = Infinity;
  accFaceIdxs.forEach(i => {
    const dist = accWorld[i].point.distanceTo(accCenter);
    if (dist < thinDist) { thinDist = dist; thinFaceIdx = i; }
  });
  return thinFaceIdx;
}

const cands = findAccessoryToProfileCandidatesAllSpins(accEntry, P)
  .filter(c => P.connectorsLocal[c.forcedParentConnIdx].kind === "face");
console.log("celkem kandidatu (face-only na profilu):", cands.length);
const geoCands = cands.filter(c => accEntry.connectorsLocal[c.childFaceConnIdx].isGeoFace);
const thinFaceIdx = geoCands.length ? null : accessoryThinFaceIdx(accEntry, obj);
const thinCands = thinFaceIdx != null ? cands.filter(c => c.childFaceConnIdx === thinFaceIdx) : [];
const cand = (geoCands.length ? geoCands : (thinCands.length ? thinCands : cands))[0];
console.log("vybrany kandidat: forcedParentConnIdx=" + cand.forcedParentConnIdx + " childFaceConnIdx=" + cand.childFaceConnIdx + " (accessory connector kind: " + accEntry.connectorsLocal[cand.childFaceConnIdx].kind + ")");
applyFaceToFaceCandidate(cand, accEntry, P);
console.log("vysledny dotyk:", fmt(touchReport(accEntry, P)));
