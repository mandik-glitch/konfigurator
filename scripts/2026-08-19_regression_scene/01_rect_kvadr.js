const fs = require("fs");
const THREE = require("three");
const shared = require("/opt/konfigurator/webapp/js/scene-geometry-shared.js");
const {
  baseQuaternion, computeConnectorsLocal, crossAxisHalfWidthTowardDirection,
  worldConnectorsOf, attachEntryToParent, applyLengthScale, registerJoint,
} = shared;

function parseGlbMesh(path) {
  const buf = fs.readFileSync(path);
  let offset = 12, json = null, binChunk = null;
  while (offset < buf.length) {
    const chunkLen = buf.readUInt32LE(offset);
    const chunkType = buf.readUInt32LE(offset + 4);
    const chunkData = buf.slice(offset + 8, offset + 8 + chunkLen);
    if (chunkType === 0x4e4f534a) json = JSON.parse(chunkData.toString("utf8"));
    else if (chunkType === 0x004e4942) binChunk = chunkData;
    offset += 8 + chunkLen;
  }
  const prim = json.meshes[0].primitives[0];
  const posAccessor = json.accessors[prim.attributes.POSITION];
  const bufferView = json.bufferViews[posAccessor.bufferView];
  const byteOffset = (bufferView.byteOffset || 0) + (posAccessor.byteOffset || 0);
  const positions = new Float32Array(binChunk.buffer, binChunk.byteOffset + byteOffset, posAccessor.count * 3);
  let indices = null;
  if (prim.indices != null) {
    const idxAccessor = json.accessors[prim.indices];
    const idxBufferView = json.bufferViews[idxAccessor.bufferView];
    const idxByteOffset = (idxBufferView.byteOffset || 0) + (idxAccessor.byteOffset || 0);
    const Ctor = idxAccessor.componentType === 5123 ? Uint16Array : Uint32Array;
    indices = new Ctor(binChunk.buffer, binChunk.byteOffset + idxByteOffset, idxAccessor.count);
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  if (indices) geo.setIndex(new THREE.BufferAttribute(indices, 1));
  return new THREE.Mesh(geo);
}

const GLB_PATH = "/opt/konfigurator/webapp/katalog/profil_35x35.glb";
function mkRealEntry() {
  const obj = parseGlbMesh(GLB_PATH);
  return { object3d: obj, connectorsLocal: computeConnectorsLocal(obj) };
}
function boxOf(entry) { return new THREE.Box3().setFromObject(entry.object3d); }
function touchReport(a, b) {
  const A = a.min ? a : boxOf(a), B = b.min ? b : boxOf(b);
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

// ===================== 1) buildSquareFrameEntries (reprodukce, REALNA geometrie) =====================
console.log("=== buildSquareFrameEntries (reálný profil_30x30_uzavreny.glb, L=1000mm nativní) ===");
{
  const reversed = false;
  const quatThrough = baseQuaternion(reversed ? 90 : 0);
  const quatAttach = baseQuaternion(reversed ? 0 : 90);

  const entryA = mkRealEntry();
  const objA = entryA.object3d;
  objA.quaternion.copy(quatThrough);
  objA.position.set(0, 0, 0);
  objA.updateMatrixWorld(true);
  const L = entryA.connectorsLocal[0].point.distanceTo(entryA.connectorsLocal[1].point);

  const attachDir = entryA.connectorsLocal[1].point.clone().sub(entryA.connectorsLocal[0].point).applyQuaternion(quatAttach).normalize();
  const halfA = crossAxisHalfWidthTowardDirection(entryA.connectorsLocal, objA.quaternion, attachDir);
  const halfB = halfA;
  const centerDist = L - halfA - halfB;

  const rotatedConn0A = entryA.connectorsLocal[0].point.clone().applyQuaternion(quatThrough);
  objA.position.copy(rotatedConn0A.clone().negate()).addScaledVector(attachDir, halfA);
  objA.updateMatrixWorld(true);

  const entryB = mkRealEntry();
  const objB = entryB.object3d;
  objB.quaternion.copy(quatThrough);
  objB.position.copy(objA.position).addScaledVector(attachDir, centerDist);
  objB.updateMatrixWorld(true);

  function placeAttached(endIdx) {
    const entry = mkRealEntry();
    const obj = entry.object3d;
    obj.quaternion.copy(quatAttach);
    obj.position.set(0, 0, 0);
    obj.updateMatrixWorld(true);
    const childConnIdx = 0;
    const wcA = worldConnectorsOf(entryA)[endIdx];
    const otherEndIdx = 1 - endIdx;
    const outwardDir = entryA.connectorsLocal[endIdx].point.clone().sub(entryA.connectorsLocal[otherEndIdx].point).applyQuaternion(objA.quaternion).normalize();
    const halfAlongA = crossAxisHalfWidthTowardDirection(entry.connectorsLocal, quatAttach, outwardDir);
    const target = wcA.point.clone().addScaledVector(attachDir, halfA).addScaledVector(outwardDir, -halfAlongA);
    const rotatedLocal = entry.connectorsLocal[childConnIdx].point.clone().applyQuaternion(quatAttach);
    obj.position.copy(target.clone().sub(rotatedLocal));
    obj.updateMatrixWorld(true);
    const L0 = entry.connectorsLocal[0].point.distanceTo(entry.connectorsLocal[1].point);
    const targetLen = centerDist - halfA - halfB;
    if (targetLen && L0) applyLengthScale(entry, targetLen / L0, childConnIdx);
    return entry;
  }
  const entryC = placeAttached(0);
  const entryD = placeAttached(1);

  check("A-C (roh)", entryA, entryC);
  check("C-B (roh)", entryC, entryB);
  check("A-D (roh)", entryA, entryD);
  check("D-B (roh)", entryD, entryB);

  const boxA = boxOf(entryA), boxB = boxOf(entryB), boxC = boxOf(entryC), boxD = boxOf(entryD);
  const allBox = boxA.clone().union(boxB).union(boxC).union(boxD);
  const size = allBox.getSize(new THREE.Vector3());
  console.log(`  vnější rozměr celého rámu: x=${size.x.toFixed(4)} z=${size.z.toFixed(4)} (očekáváno 1000×1000 pro čtverec)`);
}

// ===================== 2) buildKvadrShape (reprodukce, REALNA geometrie) =====================
console.log("\n=== buildKvadrShape (reálný profil, spodní+horní rám + 4 sloupky) ===");
{
  const vertQuat = baseQuaternion(0, "vertical");
  const reversed = false;
  const quatThrough = baseQuaternion(reversed ? 90 : 0);
  const quatAttach = baseQuaternion(reversed ? 0 : 90);

  function buildFrame() {
    const entryA = mkRealEntry();
    const objA = entryA.object3d;
    objA.quaternion.copy(quatThrough);
    objA.position.set(0, 0, 0);
    objA.updateMatrixWorld(true);
    const L = entryA.connectorsLocal[0].point.distanceTo(entryA.connectorsLocal[1].point);
    const attachDir = entryA.connectorsLocal[1].point.clone().sub(entryA.connectorsLocal[0].point).applyQuaternion(quatAttach).normalize();
    const halfA = crossAxisHalfWidthTowardDirection(entryA.connectorsLocal, objA.quaternion, attachDir);
    const halfB = halfA;
    const centerDist = L - halfA - halfB;
    const rotatedConn0A = entryA.connectorsLocal[0].point.clone().applyQuaternion(quatThrough);
    objA.position.copy(rotatedConn0A.clone().negate()).addScaledVector(attachDir, halfA);
    objA.updateMatrixWorld(true);
    const entryB = mkRealEntry();
    const objB = entryB.object3d;
    objB.quaternion.copy(quatThrough);
    objB.position.copy(objA.position).addScaledVector(attachDir, centerDist);
    objB.updateMatrixWorld(true);
    function placeAttached(endIdx) {
      const entry = mkRealEntry();
      const obj = entry.object3d;
      obj.quaternion.copy(quatAttach);
      obj.position.set(0, 0, 0);
      obj.updateMatrixWorld(true);
      const wcA = worldConnectorsOf(entryA)[endIdx];
      const otherEndIdx = 1 - endIdx;
      const outwardDir = entryA.connectorsLocal[endIdx].point.clone().sub(entryA.connectorsLocal[otherEndIdx].point).applyQuaternion(objA.quaternion).normalize();
      const halfAlongA = crossAxisHalfWidthTowardDirection(entry.connectorsLocal, quatAttach, outwardDir);
      const target = wcA.point.clone().addScaledVector(attachDir, halfA).addScaledVector(outwardDir, -halfAlongA);
      const rotatedLocal = entry.connectorsLocal[0].point.clone().applyQuaternion(quatAttach);
      obj.position.copy(target.clone().sub(rotatedLocal));
      obj.updateMatrixWorld(true);
      const L0 = entry.connectorsLocal[0].point.distanceTo(entry.connectorsLocal[1].point);
      const targetLen = centerDist - halfA - halfB;
      if (targetLen && L0) applyLengthScale(entry, targetLen / L0, 0);
      return entry;
    }
    const entryC = placeAttached(0);
    const entryD = placeAttached(1);
    return { entryA, entryB, entryC, entryD };
  }

  const bottom = buildFrame();
  const { entryA, entryB, entryC, entryD } = bottom;
  const bottomEntries = [entryA, entryC, entryB, entryD];

  bottomEntries.forEach(e => {
    const currentBottomY = boxOf(e).min.y;
    e.object3d.position.y -= currentBottomY;
    e.object3d.updateMatrixWorld(true);
  });

  check("dolní rám: A-C", entryA, entryC);
  check("dolní rám: C-B", entryC, entryB);
  check("dolní rám: A-D", entryA, entryD);
  check("dolní rám: D-B", entryD, entryB);

  const cornerSpecs = [
    { entry: entryA, connIdx: 0 }, { entry: entryA, connIdx: 1 },
    { entry: entryB, connIdx: 0 }, { entry: entryB, connIdx: 1 },
  ];
  const posts = [];
  cornerSpecs.forEach((spec, i) => {
    const postEntry = mkRealEntry();
    attachEntryToParent(postEntry, spec.entry, vertQuat, spec.connIdx, 1);
    const cornerNormalWorld = worldConnectorsOf(spec.entry)[spec.connIdx].normal.clone();
    const postHalf = crossAxisHalfWidthTowardDirection(postEntry.connectorsLocal, postEntry.object3d.quaternion, cornerNormalWorld);
    postEntry.object3d.position.addScaledVector(cornerNormalWorld, -postHalf);
    postEntry.object3d.updateMatrixWorld(true);
    check(`sloupek ${i} <-> roh ${spec.entry === entryA ? "A" : "B"}[${spec.connIdx}]`, postEntry, spec.entry);
    posts.push(postEntry);
  });

  const postTopWorld = worldConnectorsOf(posts[0])[0].point;

  const topEntries = bottomEntries.map(be => {
    const obj = parseGlbMesh(GLB_PATH);
    const connectorsLocal = computeConnectorsLocal(obj);
    obj.quaternion.copy(be.object3d.quaternion);
    obj.position.copy(be.object3d.position);
    obj.scale.copy(be.object3d.scale);
    obj.updateMatrixWorld(true);
    const currentBottomY = new THREE.Box3().setFromObject(obj).min.y;
    obj.position.y += (postTopWorld.y - currentBottomY);
    obj.updateMatrixWorld(true);
    return { object3d: obj, connectorsLocal };
  });
  const [topA, topC, topB, topD] = topEntries;
  check("horní rám: A-C", topA, topC);
  check("horní rám: C-B", topC, topB);
  check("horní rám: A-D", topA, topD);
  check("horní rám: D-B", topD, topB);

  posts.forEach((postEntry, i) => {
    const topFrameEntry = i < 2 ? topA : topB;
    check(`sloupek ${i} <-> horní rám (mělo by být plný styk, sloupek "podjíždí" horní rám shora)`, postEntry, topFrameEntry);
  });

  // kolizni kontrola: zadny nesousedici par se nesmi plne prekryvat na vsech 3 osach
  const all = [entryA, entryB, entryC, entryD, ...posts, topA, topB, topC, topD];
  let collisions = 0;
  for (let i = 0; i < all.length; i++) {
    for (let j = i + 1; j < all.length; j++) {
      const bi = boxOf(all[i]), bj = boxOf(all[j]);
      const ox = Math.min(bi.max.x, bj.max.x) - Math.max(bi.min.x, bj.min.x);
      const oy = Math.min(bi.max.y, bj.max.y) - Math.max(bi.min.y, bj.min.y);
      const oz = Math.min(bi.max.z, bj.max.z) - Math.max(bi.min.z, bj.min.z);
      if (ox > 0.01 && oy > 0.01 && oz > 0.01) collisions++;
    }
  }
  console.log(`  plné 3-osé kolize mezi libovolnou dvojicí dílů (bez ohledu na sousednost): ${collisions}`);
}

console.log(`\n${anyBad ? "NALEZEN PROBLÉM (viz FAIL výše)" : "VŠECHNY zkontrolované spoje jsou platný flush styk (1 osa gap=0/overlap=0, 2 osy plný překryv)"}`);
