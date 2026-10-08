// Kompletni pipeline (kroky 1-7 + sestaveni + kontroly) pro JEDNU karoserii
// Berlingo/Partner/Trafic, leva stena, noha 30x30 (D=349,T=30).
// Volani: node tmp_2026-08-31_bpt_run_vehicle.js <config.json> <out_prefix>
//
// config: {
//   base, H, tag, legPolicy: "all-plain" | "plain-then-vyrez",
//   wallClearanceArch (jen pro vyrez), heights: [zoznam povolenych vysek uz
//   vybranych pro tento vuz - napln se automaticky pokud chybi]
// }
const fs = require("fs");
const { makeCollisionCtx } = require("/opt/konfigurator/scripts/tmp_2026-08-31_bpt_collision.js");
const LEG = require("/opt/konfigurator/scripts/tmp_2026-08-31_bpt_leg_builder.js");
const THREE = require("three");

const cfgPath = process.argv[2];
const outPrefix = process.argv[3];
const cfg = JSON.parse(fs.readFileSync(cfgPath, "utf8"));
const { base, H, tag, legPolicy, wallClearanceArch } = cfg;
const D = 349, T = 30;
const CONNECTOR_POS = { 1: [15, 415], 2: [15, 415, 816], 3: [15, 415, 816, 1217] };
const CLEAR_SPACING = { 1: 430, 2: 832, 3: 1232 };
const WIDTH_TRY_ORDER = [3, 2, 1];
const Q_ALONG_Z = [-0.707107, 0, 0, 0.707107];
const Q_ALONG_X = [0, 0, -0.707107, 0.707107];
const Q_ENDCAP_UP = [0.7071067811865475, 0, 0, 0.7071067811865475];
const CAP_FLANGE_THICKNESS = 3;
const KAT = "/opt/konfigurator/webapp/katalog/";
const ENDCAP = KAT + "product_3071.glb";
const EUROBOX_GLB = { 120: KAT + "product_3788.glb", 170: KAT + "product_3793.glb", 220: KAT + "product_3794.glb", 270: KAT + "product_3795.glb" };
const EUROBOX_PID = { 120: "product_3788", 170: "product_3793", 220: "product_3794", 270: "product_3795" };

const ctx = makeCollisionCtx(base);
const { collidesWithWalls, buildLegObject, boxL0, boxB0, parseGlbMesh } = ctx;

function stepUntil(testFn, startVal, dir, maxSteps, label) {
  let val = startVal, steps = 0, collided = false;
  while (steps < maxSteps) {
    val += dir; steps++;
    if (testFn(val)) { collided = true; break; }
  }
  if (!collided) throw new Error(`${label}: zadna kolize po ${maxSteps} krocich (od ${startVal})`);
  const backoff = val - dir * 2;
  if (testFn(backoff)) throw new Error(`${label}: po 2mm zpet stale koliduje`);
  return { collisionVal: val, safeVal: backoff, steps };
}

function toWorld(localParts, offsetX, offsetY, anchorZ) {
  return localParts.map(p => ({
    part_id: p.part_id || "Object_7",
    position: [offsetX - p.position[0], p.position[1] + offsetY, anchorZ + p.position[2]],
    quaternion: p.quaternion, scale: p.scale, role: p.role,
  }));
}
function groupAt(localParts, offsetX, offsetY, anchorZ) { return buildLegObject(toWorld(localParts, offsetX, offsetY, anchorZ)); }

function legPartsFor(type, extendedYnew) {
  if (type === "plain") return LEG.buildPlainAtDepth(D, H, T);
  if (extendedYnew != null) return LEG.buildVyrezAtDepthExtended(D, H, extendedYnew, wallClearanceArch, T);
  return LEG.buildVyrezAtDepth(D, H, 300, wallClearanceArch, T); // 300 = docasny odhad pred step4
}

// ===================== KROK 1: roh (podlaha+prepazka+stena) =====================
const lx1 = boxL0.max.x, bz1 = boxB0.max.z;
const SEED_BUFFER = cfg.seedBuffer || 150, SEED_Y = cfg.seedY || 200;
let offsetX = lx1 + D + SEED_BUFFER, offsetY = SEED_Y, anchorZ = bz1 + SEED_BUFFER;
const plainParts0 = LEG.buildPlainAtDepth(D, H, T);
if (collidesWithWalls(groupAt(plainParts0, offsetX, offsetY, anchorZ))) throw new Error("SEED_COLLIDES");
{ const r = stepUntil((v) => collidesWithWalls(groupAt(plainParts0, offsetX, offsetY + v, anchorZ)), 0, -1, 3000, "podlaha"); offsetY += r.safeVal; }
{ const r = stepUntil((v) => collidesWithWalls(groupAt(plainParts0, offsetX, offsetY, anchorZ + v)), 0, -1, 4000, "prepazka"); anchorZ += r.safeVal; }
{ const r = stepUntil((v) => collidesWithWalls(groupAt(plainParts0, offsetX + v, offsetY, anchorZ)), 0, -1, 3000, "stena"); offsetX += r.safeVal; }
const step1 = { offsetX, offsetY, anchorZ };
if (collidesWithWalls(groupAt(plainParts0, offsetX, offsetY, anchorZ))) throw new Error("step1 final koliduje");

// ===================== KROK 2: maximalni rozpon (rear boundary) =====================
const probeType0 = legPolicy === "all-plain" ? "plain" : "vyrez";
function rearProbeParts() { return legPartsFor(probeType0, null); }
let rz = anchorZ, steps2 = 0, collZ = null;
while (steps2 < 6000) {
  rz += 1; steps2++;
  if (collidesWithWalls(groupAt(rearProbeParts(), offsetX, offsetY, rz))) { collZ = rz; break; }
}
if (collZ === null) throw new Error("step2: zadna kolize (rear)");
const REAR_ANCHOR_Z = collZ - 20;
if (collidesWithWalls(groupAt(rearProbeParts(), offsetX, offsetY, REAR_ANCHOR_Z))) throw new Error("step2: po 20mm zpet stale koliduje");
const step2 = { REAR_ANCHOR_Z, frontAnchorZ: anchorZ, maxSpan: REAR_ANCHOR_Z - anchorZ };

// ===================== KROK 3: sloupcove plneni =====================
const legs = [{ type: "plain", anchorZ }];
const columns = [];
function wholeAssemblyParts(extraLegParts, extraColParts) {
  let parts = [];
  legs.forEach((leg, i) => { parts.push(...toWorld(legPartsFor(leg.type, leg.Y_new), offsetX, offsetY, leg.anchorZ)); });
  if (extraLegParts) parts.push(...extraLegParts);
  columns.forEach(col => parts.push(...railsAndConnectorsWorld(col)));
  if (extraColParts) parts.push(...extraColParts);
  return parts;
}
function railsAndConnectorsWorld(col) {
  const legFrom = legs[col.legFromIdx], legTo = legs[col.legToIdx];
  const railZFrom = legFrom.anchorZ + T, railZTo = legTo.anchorZ, railLen = railZTo - railZFrom, railZCenter = (railZFrom + railZTo) / 2;
  const crossLen = D - 2 * T, crossXCenter = D / 2;
  const Y = 200 + offsetY;
  const parts = [];
  parts.push({ part_id: "Object_7", position: [offsetX - T / 2, Y, railZCenter], quaternion: Q_ALONG_Z, scale: [1, railLen / 1000, 1] });
  parts.push({ part_id: "Object_7", position: [offsetX - (D - T / 2), Y, railZCenter], quaternion: Q_ALONG_Z, scale: [1, railLen / 1000, 1] });
  CONNECTOR_POS[col.N].forEach(localZ => parts.push({ part_id: "Object_7", position: [offsetX - crossXCenter, Y, railZFrom + localZ], quaternion: Q_ALONG_X, scale: [1, crossLen / 1000, 1] }));
  return parts;
}
function assemblyCollides(extraParts) {
  const all = [...wholeAssemblyParts(), ...(extraParts || [])];
  return collidesWithWalls(buildLegObject(all));
}
let colIdx = 0;
while (true) {
  const lastLeg = legs[legs.length - 1];
  let placed = false;
  for (const N of WIDTH_TRY_ORDER) {
    const clear = CLEAR_SPACING[N];
    const newAnchorZ = lastLeg.anchorZ + T + clear;
    if (newAnchorZ > REAR_ANCHOR_Z) continue;
    // Zkus VZDY nejdriv "plain" (levnejsi/jednodussi dil) - jen pokud to
    // koliduje (skutecny podbeh na tomhle miste), sahni po "vyrez" (pokud
    // to politika vozidla vubec pripousti). Berlingo/Partner ("all-plain")
    // vyrez nikdy nezkousi (uz overeno zadny vyznamny podbeh).
    const typesToTry = legPolicy === "all-plain" ? ["plain"] : ["plain", "vyrez"];
    let candCol = null;
    for (const candLegType of typesToTry) {
      const candidateLeg = { type: candLegType, anchorZ: newAnchorZ };
      legs.push(candidateLeg);
      const cc = { N, legFromIdx: legs.length - 2, legToIdx: legs.length - 1 };
      const railParts = railsAndConnectorsWorld(cc);
      const collides = assemblyCollides(railParts);
      if (!collides) { candCol = cc; break; }
      legs.pop();
    }
    if (candCol) { columns.push(candCol); placed = true; break; }
  }
  if (!placed) break;
  colIdx++;
  if (colIdx > 20) break;
}
const step3 = { legs: JSON.parse(JSON.stringify(legs)), columns: JSON.parse(JSON.stringify(columns)) };

// ===================== KROK 4: rozsireni vyrez noh (Y_new) =====================
const TOP_Y = H; // zadny cap v teto sablone - horni limit je proste H
legs.forEach((leg, i) => {
  if (leg.type !== "vyrez") return;
  const X_WORLD = offsetX - (D - T / 2);
  function buildPiece(bottomY, az) {
    const lenY = TOP_Y - bottomY, centerY = (bottomY + TOP_Y) / 2 + offsetY;
    return { part_id: "Object_7", position: [X_WORLD, centerY, az + T / 2], quaternion: [0, 0, 0, 1], scale: [1, lenY / 1000, 1] };
  }
  let collisionBottomY = null;
  const CUTOUT_GUESS_MAX = 500;
  for (let bottomY = CUTOUT_GUESS_MAX; bottomY >= 0; bottomY--) {
    if (collidesWithWalls(buildLegObject([buildPiece(bottomY, leg.anchorZ)]))) { collisionBottomY = bottomY; break; }
  }
  if (collisionBottomY === null) collisionBottomY = 0;
  const Y_NEW = collisionBottomY + 20;
  if (collidesWithWalls(buildLegObject([buildPiece(Y_NEW, leg.anchorZ)]))) throw new Error(`leg[${i}] step4: po 20mm zpet stale koliduje`);
  // Pojistka: pokud vyjde Y_new mensi nez T, "sloupek-pred-podbehem" +
  // "pricka-uzavreni-vyrezu" by se geometricky prekryvaly se "spojnice-
  // dolni" (floor-level rung, Y 0..T) - v takovem pripade tu ve
  // skutecnosti zadny vyznamny podbeh neni (plain by tu take prosel),
  // noha se preklopi na "plain".
  if (Y_NEW < T) { leg.type = "plain"; } else { leg.Y_new = Y_NEW; }
});
const step4 = legs.map((l, i) => ({ i, type: l.type, Y_new: l.Y_new }));

// ===================== KROK 5: nosnik floor pres cely rozpon sloupce =====================
function legFloorOf(i) { return legs[i].type === "plain" ? 0 : legs[i].Y_new; }
columns.forEach((col, colIdx2) => {
  const legFrom = legs[col.legFromIdx], legTo = legs[col.legToIdx];
  const floorLegBased = Math.max(legFloorOf(col.legFromIdx), legFloorOf(col.legToIdx));
  const railZFrom = legFrom.anchorZ + T, railZTo = legTo.anchorZ, railLen = railZTo - railZFrom, railZCenter = (railZFrom + railZTo) / 2;
  const crossLen = D - 2 * T, crossXCenter = D / 2;
  function railPartsAt(Y) {
    const parts = [];
    parts.push({ part_id: "Object_7", position: [offsetX - T / 2, Y + offsetY, railZCenter], quaternion: Q_ALONG_Z, scale: [1, railLen / 1000, 1] });
    parts.push({ part_id: "Object_7", position: [offsetX - (D - T / 2), Y + offsetY, railZCenter], quaternion: Q_ALONG_Z, scale: [1, railLen / 1000, 1] });
    CONNECTOR_POS[col.N].forEach(localZ => parts.push({ part_id: "Object_7", position: [offsetX - crossXCenter, Y + offsetY, railZFrom + localZ], quaternion: Q_ALONG_X, scale: [1, crossLen / 1000, 1] }));
    return parts;
  }
  let finalFloor = floorLegBased;
  const railYCenterCandidate0 = floorLegBased + T / 2;
  if (collidesWithWalls(buildLegObject(railPartsAt(railYCenterCandidate0)))) {
    let Y = railYCenterCandidate0, steps = 0, cleared = null;
    while (steps < 800) { Y += 1; steps++; if (!collidesWithWalls(buildLegObject(railPartsAt(Y)))) { cleared = Y; break; } }
    if (cleared === null) throw new Error(`sloupec ${colIdx2}: step5 nenalezeno`);
    const withMargin = cleared + 20;
    if (collidesWithWalls(buildLegObject(railPartsAt(withMargin)))) throw new Error("step5: i po +20mm koliduje");
    finalFloor = withMargin - T / 2;
  }
  col.finalFloorY = finalFloor;
});
const step5 = columns.map((c, i) => ({ i, finalFloorY: c.finalFloorY }));

// ===================== KROK 7: fyzicky strop kazdeho sloupce (siroka sonda) =====================
function fullDepthSlab(y, zFrom, zTo) {
  const geo = new THREE.BoxGeometry(D, 10, zTo - zFrom);
  const mesh = new THREE.Mesh(geo);
  mesh.position.set(offsetX - D / 2, y, (zFrom + zTo) / 2);
  mesh.updateMatrixWorld(true);
  return mesh;
}
columns.forEach((col, colIdx2) => {
  const legFrom = legs[col.legFromIdx], legTo = legs[col.legToIdx];
  const zFrom = legFrom.anchorZ + T, zTo = legTo.anchorZ;
  let y = col.finalFloorY + offsetY + 100, steps = 0, collisionY = null;
  while (steps < 1500) { y += 1; steps++; if (collidesWithWalls(fullDepthSlab(y, zFrom, zTo))) { collisionY = y; break; } }
  if (collisionY === null) throw new Error(`sloupec ${colIdx2}: step7 zadna kolize`);
  const safeY = collisionY - 2;
  if (collidesWithWalls(fullDepthSlab(safeY, zFrom, zTo))) throw new Error("step7: po 2mm zpet stale koliduje");
  col.physCeil = safeY - offsetY; // relativni k noze (bez offsetY), aby slo porovnat s TOP_Y
});
const step7 = columns.map((c, i) => ({ i, physCeil: c.physCeil }));

// ===================== VYSKOVY PLAN =====================
const ALLOWED_H = [120, 170, 220, 270];
// Rail/luzko containment: railTop (=cursor+T) musi byt <= TOP_Y (H, profil
// tady nikdy nezkracujeme - viz bpt_leg_builder.js, zadny cap). Box na
// NE-poslednim patre musi zustat celý pod TOP_Y (boxTop<=TOP_Y); poslednimu
// (nejvyssimu) patru pravidlo 7 dovoluje boxTop az do fyzickeho stropu
// (physCeil, skutecna kolize s karoserii), pokud se tam vetsi box vejde.
// Preferuj DIVERZITU (pravidlo 6: aspon 3 ze 4 povolenych vysek NEKDE v
// cele sestave) - cykluj sestupne 270/220/170/120, dal opakuj nejmensi
// (120), dokud se vejde. Nerostouci odshora dolu splneno automaticky
// (cyklus je uz sestupny). Kdyby se ani 120 uz nevesel jako DALSI patro,
// konci se - ale pokud by SE vesel vetsi box nez dalsi v cyklu (hodne
// volneho mista), preferuj presto cyklus (diverzita) pred maximalnim
// vyuzitim jedno-vyskou - to je zamerne, viz pravidlo 6.
const DESCENDING_CYCLE = [270, 220, 170, 120];
function planColumnStrict(floorY, topLimit) {
  let levels = [];
  let cursor = floorY;
  let cycleIdx = 0;
  while (true) {
    const h = DESCENDING_CYCLE[Math.min(cycleIdx, DESCENDING_CYCLE.length - 1)];
    const railTop = cursor + T;
    const boxTop = railTop + h;
    if (railTop > topLimit + 1e-6 || boxTop > topLimit + 1e-6) break;
    levels.push(h);
    cursor = cursor + T + h + 30;
    cycleIdx++;
    if (levels.length > 8) break;
  }
  return levels;
}
columns.forEach(col => {
  let levels = planColumnStrict(col.finalFloorY, H);
  // Bonus (pravidlo 7): zkus poslednimu patru dat vetsi box, pokud se vejde
  // pod fyzicky strop (physCeil) - rail zustava na stejnem miste (<=H),
  // jen BOX presahuje az k physCeil.
  if (levels.length > 0) {
    const cursorBeforeLast = col.finalFloorY + levels.slice(0, -1).reduce((s, h) => s + T + h + 30, 0);
    const railTopLast = cursorBeforeLast + T;
    const monotoneCeiling = levels.length >= 2 ? levels[levels.length - 2] : 999;
    const biggerOptions = ALLOWED_H.filter(h => h >= levels[levels.length - 1] && h <= monotoneCeiling).sort((a, b) => b - a);
    for (const h of biggerOptions) {
      if (railTopLast + h <= col.physCeil + 1e-6) { levels[levels.length - 1] = h; break; }
    }
  }
  col.heights = levels;
});

// ===================== SESTAVENI CELE GEOMETRIE =====================
let allParts = [];
const legEndcapRolesFor = (type) => type === "vyrez" ? ["predni-svislice", "zadni-svislice-nad-zarezem"] : ["predni-svislice", "zadni-svislice"];
legs.forEach((leg) => {
  const localParts = legPartsFor(leg.type, leg.Y_new);
  const endcaps = localParts.filter(p => legEndcapRolesFor(leg.type).includes(p.role)).map(p => {
    const lenMm = p.scale[1] * 1000;
    const topY = p.position[1] + lenMm / 2 + CAP_FLANGE_THICKNESS;
    return { part_id: "product_3071", position: [p.position[0], topY, p.position[2]], quaternion: Q_ENDCAP_UP, scale: [1, 1, 1], role: "zaslepka-" + p.role };
  });
  allParts.push(...toWorld([...localParts, ...endcaps], offsetX, offsetY, leg.anchorZ));
});

const columnSummaries = [];
columns.forEach((col, colIdx2) => {
  const legFrom = legs[col.legFromIdx], legTo = legs[col.legToIdx];
  const railZFrom = legFrom.anchorZ + T, railZTo = legTo.anchorZ, railLen = railZTo - railZFrom, railZCenter = (railZFrom + railZTo) / 2;
  const crossLen = D - 2 * T, crossXCenter = D / 2;
  let railTop = col.finalFloorY + T;
  const levels = [];
  col.heights.forEach((boxH, levelIdx) => {
    const railYCenter = railTop - T / 2;
    const isTop = levelIdx === col.heights.length - 1;
    const boxTop = railTop + boxH;
    levels.push({ railYCenter, boxH, boxTop });
    railTop = railTop + boxH + 30 + T;
  });
  levels.forEach((level, levelIdx) => {
    const Y = level.railYCenter;
    allParts.push({ part_id: "Object_7", position: [offsetX - T / 2, Y + offsetY, railZCenter], quaternion: Q_ALONG_Z, scale: [1, railLen / 1000, 1], role: `nosnik-sloupec${colIdx2}-patro${levelIdx}` });
    allParts.push({ part_id: "Object_7", position: [offsetX - (D - T / 2), Y + offsetY, railZCenter], quaternion: Q_ALONG_Z, scale: [1, railLen / 1000, 1], role: `nosnik-sloupec${colIdx2}-patro${levelIdx}` });
    CONNECTOR_POS[col.N].forEach(localZ => allParts.push({ part_id: "Object_7", position: [offsetX - crossXCenter, Y + offsetY, railZFrom + localZ], quaternion: Q_ALONG_X, scale: [1, crossLen / 1000, 1], role: `spojnice-sloupec${colIdx2}-patro${levelIdx}` }));
    const positions = CONNECTOR_POS[col.N];
    for (let i = 0; i < positions.length - 1; i++) {
      allParts.push({ part_id: EUROBOX_PID[level.boxH], position: [0, 0, 0], quaternion: Q_ALONG_Z, scale: [1, 1, 1], role: `eurobox-sloupec${colIdx2}-patro${levelIdx}`,
        _pending: { slotZFrom: railZFrom + positions[i], slotZTo: railZFrom + positions[i + 1], railYCenter: Y + offsetY, boxH: level.boxH } });
    }
  });
  columnSummaries.push({ colIdx: colIdx2, N: col.N, floorY: col.finalFloorY, physCeil: col.physCeil, heights: col.heights, boxesPerLevel: col.N, totalBoxes: col.N * col.heights.length, railZFrom, railZTo, railLen });
});

const probeCache = {};
function probeFor(h) {
  if (probeCache[h]) return probeCache[h];
  const m = parseGlbMesh(EUROBOX_GLB[h]);
  m.position.set(0, 0, 0); m.quaternion.set(...Q_ALONG_Z); m.scale.set(1, 1, 1); m.updateMatrixWorld(true);
  const b = new THREE.Box3().setFromObject(m);
  const center = [(b.min.x + b.max.x) / 2, (b.min.y + b.max.y) / 2, (b.min.z + b.max.z) / 2];
  return (probeCache[h] = { box: b, center });
}
const targetXcenter = offsetX - D / 2;
allParts.forEach(p => {
  if (!p._pending) return;
  const { slotZFrom, slotZTo, railYCenter, boxH } = p._pending;
  const probe = probeFor(boxH);
  const targetZcenter = (slotZFrom + slotZTo) / 2;
  const targetYbottom = railYCenter + T / 2;
  p.position = [targetXcenter - probe.center[0], targetYbottom - probe.box.min.y - 12, targetZcenter - probe.center[2]];
  p.quaternion = [...Q_ALONG_Z];
  delete p._pending;
});

// ===================== KONTROLY =====================
function glbFor(id) {
  if (id === "Object_7") return KAT + "Object_7.glb";
  if (id === "product_3071") return ENDCAP;
  for (const h in EUROBOX_PID) if (EUROBOX_PID[h] === id) return EUROBOX_GLB[h];
  return null;
}
function meshOf(p) { const m = parseGlbMesh(glbFor(p.part_id)); m.position.set(...p.position); m.quaternion.set(...p.quaternion); m.scale.set(...p.scale); m.updateMatrixWorld(true); return m; }

const profileParts = allParts.filter(p => p.part_id === "Object_7");
const carCollisionProfiles = collidesWithWalls(buildLegObject(profileParts));
let euroboxCarCollision = false;
const badEurobox = [];
allParts.filter(p => p.part_id.startsWith("product_37")).forEach(p => {
  const grp = new THREE.Group(); grp.add(meshOf(p)); grp.updateMatrixWorld(true);
  if (collidesWithWalls(grp)) { euroboxCarCollision = true; badEurobox.push(p.role); }
});
let badProfiles = [];
if (carCollisionProfiles) profileParts.forEach((p, i) => { if (collidesWithWalls(buildLegObject([p]))) badProfiles.push({ role: p.role, position: p.position }); });

const meshesAll = allParts.map(meshOf);
let unexpected = 0;
const badPairs = [];
for (let i = 0; i < meshesAll.length; i++) for (let j = i + 1; j < meshesAll.length; j++) {
  const A = new THREE.Box3().setFromObject(meshesAll[i]), B = new THREE.Box3().setFromObject(meshesAll[j]);
  const ox = Math.min(A.max.x, B.max.x) - Math.max(A.min.x, B.min.x);
  const oy = Math.min(A.max.y, B.max.y) - Math.max(A.min.y, B.min.y);
  const oz = Math.min(A.max.z, B.max.z) - Math.max(A.min.z, B.min.z);
  if (ox > 0.5 && oy > 0.5 && oz > 0.5) {
    const nestOk = allParts[i].part_id !== "Object_7" || allParts[j].part_id !== "Object_7";
    if (!nestOk) { unexpected++; badPairs.push([allParts[i].role, allParts[j].role]); }
  }
}

const totalBoxes = columnSummaries.reduce((s, c) => s + c.totalBoxes, 0);
const distinctHeights = new Set(columnSummaries.flatMap(c => c.heights));

const result = {
  tag, base, H, D, T, step1, step2, step3: { legsCount: legs.length, columnsCount: columns.length }, step4, step5, step7,
  columnSummaries, totalBoxes, distinctHeights: [...distinctHeights],
  ok: !carCollisionProfiles && !euroboxCarCollision && unexpected === 0,
  carCollisionProfiles, euroboxCarCollision, badEurobox, badProfiles, unexpectedSelfCollisions: unexpected, badPairs,
};
fs.writeFileSync(`${outPrefix}_result.json`, JSON.stringify(result, null, 1));
fs.writeFileSync(`${outPrefix}_parts.json`, JSON.stringify(allParts.map(({ _pending, ...r }) => r), null, 1));
console.log(JSON.stringify(result));
