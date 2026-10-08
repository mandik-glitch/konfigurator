// Znovupoužitelná knihovna pro ověřování geometrie spojů profilů ve 3D
// scéně - viz VLASTNOSTI_PROFILU.md ("Pravidlo profilů - žádné
// zanoření...") a .claude/skills/3d-scena-spoje/SKILL.md.
//
// bot8 2026-08-19 ("silná varianta B se sdílenými daty"): funkce v sekci
// "CORE" už nejsou kopie - jsou requirovány přímo z
// webapp/js/scene-geometry-shared.js, což je STEJNÝ soubor, který
// webapp/scene.html načítá přes <script src>. Jeden zdroj pravdy pro
// prohlížeč i pro tenhle Node.js ověřovací nástroj - žádná ruční
// synchronizace dvou kopií.
//
// Použití: `npm install` v ROOTU repa (/opt/konfigurator, ne ve scripts/ -
// viz package.json), pak `node -e "require('./2026-08-18_scene_geometry_
// lib.js')"` nebo requirovat z vlastního skriptu (viz 2026-08-18_shelf_
// builder.js pro příklad).
const THREE = require("three");
const {
  LENGTH_TILT, baseQuaternion, dominantWallCoord, computeConnectorsLocal,
  crossAxisHalfWidthTowardDirection, worldConnectorsOf, firstFreeConnectorIndex,
  linkJointPeers, isProfilePart, attachEntryToParent, registerJoint, applyLengthScale,
} = require("../webapp/js/scene-geometry-shared.js");

// ===================== HELPERS (nové, ne ze scene.html) =====================

// Vytvoří "entry" pro profil - box aproximace jeho reálného GLB (platí
// přesně pro extrudované profily, ověř si skutečné rozměry přímo z
// .glb - viz VLASTNOSTI_PROFILU.md 2an krok 2, NEHÁDEJ).
function mkProfileEntry(partId, dimX, dimZ, dimY) {
  const geo = new THREE.BoxGeometry(dimX, dimY || 1000, dimZ);
  const obj = new THREE.Mesh(geo);
  return { part_id: partId, object3d: obj, connectorsLocal: computeConnectorsLocal(obj) };
}

function boxOf(entry) {
  return new THREE.Box3().setFromObject(entry.object3d);
}

// Uzavřený obdélníkový rám (zobecněná buildSquareFrameEntries ze
// scene.html - Ly = délka A/B, Lx = rozestup/druhý vnější rozměr).
// mkEntry(): tovární funkce vracející nový entry stejného profilu
// (volá se opakovaně pro A/B/C/D).
function buildRectFrameEntries(mkEntry, Ly, Lx) {
  const quatThrough = baseQuaternion(0);
  const quatAttach = baseQuaternion(90);
  const entryA = mkEntry();
  const objA = entryA.object3d;
  objA.quaternion.copy(quatThrough);
  objA.position.set(0, 0, 0);
  objA.updateMatrixWorld(true);
  const L0 = entryA.connectorsLocal[0].point.distanceTo(entryA.connectorsLocal[1].point);
  const attachDir = entryA.connectorsLocal[1].point.clone().sub(entryA.connectorsLocal[0].point).applyQuaternion(quatAttach).normalize();
  const halfA = crossAxisHalfWidthTowardDirection(entryA.connectorsLocal, objA.quaternion, attachDir);
  const halfB = halfA;
  const centerDist = Lx - halfA - halfB;
  const rotatedConn0A = entryA.connectorsLocal[0].point.clone().applyQuaternion(quatThrough);
  objA.position.copy(rotatedConn0A.clone().negate()).addScaledVector(attachDir, halfA);
  objA.updateMatrixWorld(true);
  applyLengthScale(entryA, Ly / L0, 0);
  const connA0World = worldConnectorsOf(entryA)[0].point.clone();
  const entryB = mkEntry();
  const objB = entryB.object3d;
  objB.quaternion.copy(quatThrough);
  objB.position.copy(connA0World).addScaledVector(attachDir, centerDist).sub(rotatedConn0A);
  objB.updateMatrixWorld(true);
  applyLengthScale(entryB, Ly / L0, 0);
  function placeAttached(endIdx) {
    const entry = mkEntry();
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
    const L0c = entry.connectorsLocal[0].point.distanceTo(entry.connectorsLocal[1].point);
    const targetLen = centerDist - halfA - halfB;
    if (targetLen && L0c) applyLengthScale(entry, targetLen / L0c, childConnIdx);
    entry.usedConn = new Set([0, 1]);
    entry.hiddenEndConn = new Set([0, 1]);
    entry.wasAttached = true;
    return entry;
  }
  const entryC = placeAttached(0);
  const entryD = placeAttached(1);
  entryA.usedConn = new Set([0, 1]);
  entryB.usedConn = new Set([0, 1]);
  entryA.wasThrough = true;
  entryB.wasThrough = true;
  registerJoint(entryA, 0, entryC, 0);
  registerJoint(entryC, 1, entryB, 0);
  registerJoint(entryA, 1, entryD, 0);
  registerJoint(entryD, 1, entryB, 1);
  return { entryA, entryB, entryC, entryD };
}

// ===================== OVĚŘENÍ (VLASTNOSTI_PROFILU.md "Pravidlo profilů") =====================
//
// KRITICKÉ poučení (2026-08-18, zapsáno po Robertem odhalené chybě):
// mezera/překryv = 0 NA DOTYKOVÉ OSE nestačí jako důkaz platného spoje.
// Musí se zkontrolovat překryv na VŠECH 3 osách zvlášť - platný spoj =
// PŘESNĚ JEDNA osa s gap=0/overlap=0 (dotyková rovina) A ZBÝVAJÍCÍ DVĚ
// osy s PLNÝM překryvem (menší čelo celé uvnitř většího). Report
// vrací i "gap" i "overlap" pro každou osu - u zdravého spoje je vždy
// přesně jedna osa s overlap≈0/gap≈0 a zbylé dvě s velkým kladným
// overlapem (žádná z nich negativní ani nulová).
function touchReport(entryOrBoxA, entryOrBoxB) {
  const A = entryOrBoxA.object3d ? boxOf(entryOrBoxA) : entryOrBoxA;
  const B = entryOrBoxB.object3d ? boxOf(entryOrBoxB) : entryOrBoxB;
  const out = {};
  ["x", "y", "z"].forEach(ax => {
    const gap = Math.max(A.min[ax] - B.max[ax], B.min[ax] - A.max[ax]);
    const overlap = Math.min(A.max[ax], B.max[ax]) - Math.max(A.min[ax], B.min[ax]);
    out[ax] = { gap, overlap };
  });
  return out;
}

function formatTouchReport(report) {
  return ["x", "y", "z"].map(ax => `${ax}:g=${report[ax].gap.toFixed(3)}/o=${report[ax].overlap.toFixed(3)}`).join(" ");
}

// true, pokud report odpovídá "zdravému" plochému spoji (přesně 1 osa
// flush do `eps` mm, zbylé 2 osy s plným - kladným - prekryvem).
function isValidFlushTouch(report, eps) {
  eps = eps == null ? 0.05 : eps;
  const axes = ["x", "y", "z"];
  const flushAxes = axes.filter(ax => Math.abs(report[ax].overlap) <= eps);
  const overlapAxes = axes.filter(ax => report[ax].overlap > eps);
  return flushAxes.length === 1 && overlapAxes.length === 2;
}

// Kompletní kolizní test pole "placed" entries - vypíše/vrátí seznam
// dvojic, které se PLNĚ překrývají na všech 3 osách zároveň (skutečná
// kolize/zanoření), s výjimkou dvojic uvedených v `definedPairs`
// (Set řetězců "i-j", i<j, indexy do `placed`).
function fullCollisionCheck(placed, definedPairs) {
  definedPairs = definedPairs || new Set();
  const collisions = [];
  for (let i = 0; i < placed.length; i++) {
    for (let j = i + 1; j < placed.length; j++) {
      if (definedPairs.has(`${i}-${j}`) || definedPairs.has(`${j}-${i}`)) continue;
      const A = boxOf(placed[i]), B = boxOf(placed[j]);
      const ox = Math.min(A.max.x, B.max.x) - Math.max(A.min.x, B.min.x);
      const oy = Math.min(A.max.y, B.max.y) - Math.max(A.min.y, B.min.y);
      const oz = Math.min(A.max.z, B.max.z) - Math.max(A.min.z, B.min.z);
      if (ox > 0.01 && oy > 0.01 && oz > 0.01) {
        collisions.push({ i, j, size: [ox, oy, oz] });
      }
    }
  }
  return collisions;
}

// Serializace pole entries do formátu sloupce custom_shapes.data (viz
// VLASTNOSTI_PROFILU.md 2j/2an a api/app.py _validate_custom_shape_parts).
function serializeToCustomShapeParts(list) {
  const idxOf = new Map(list.map((e, i) => [e, i]));
  return list.map(entry => {
    const obj = entry.object3d;
    const r6 = v => Math.round(v * 1e6) / 1e6;
    const out = {
      part_id: entry.part_id,
      position: [r6(obj.position.x), r6(obj.position.y), r6(obj.position.z)],
      quaternion: [r6(obj.quaternion.x), r6(obj.quaternion.y), r6(obj.quaternion.z), r6(obj.quaternion.w)],
      scale: [r6(obj.scale.x), r6(obj.scale.y), r6(obj.scale.z)],
    };
    if (entry.usedConn && entry.usedConn.size) out.used_conn = [...entry.usedConn].sort();
    if (entry.jointCount) out.joint_count = entry.jointCount;
    if (entry.hiddenEndConn && entry.hiddenEndConn.size) out.hidden_end_conn = [...entry.hiddenEndConn];
    if (entry.wasThrough) out.was_through = true;
    if (entry.wasAttached) out.was_attached = true;
    if (entry.vertical) out.vertical = true;
    if (entry.licPeers && entry.licPeers.size) {
      out.lic_peers = [...entry.licPeers].map(p => idxOf.get(p)).filter(v => v !== undefined).sort((a, b) => a - b);
    }
    return out;
  });
}

module.exports = {
  THREE,
  LENGTH_TILT, baseQuaternion, dominantWallCoord, computeConnectorsLocal,
  crossAxisHalfWidthTowardDirection, worldConnectorsOf, firstFreeConnectorIndex,
  linkJointPeers, isProfilePart, registerJoint, attachEntryToParent, applyLengthScale,
  mkProfileEntry, boxOf, buildRectFrameEntries,
  touchReport, formatTouchReport, isValidFlushTouch, fullCollisionCheck,
  serializeToCustomShapeParts,
};
