// bot16, 2026-09-02 - "door void" front-leg fix pipeline.
//
// KONTEXT: FO31 (Transit Custom L2) a VW25 (Transporter T7) maji predni
// nohu (a nasledne cely prvni sloupec) postavenou uvnitr OTVORU bocnich
// posuvnych dveri - skutecna dira v _R_D.glb wall meshi (zadny material),
// ne jen "volny prostor" - viz KOMPONENTY_EUROBOXY.md a
// car_body_placement_methods.id=1 (novy klic
// "vylouceni_bocniho_dvernich_otvoru_2026_09_02"). Puvodni
// tmp_2026-08-31_batch_pipeline.js krok STEP1 kotvi anchorZ kolizne
// PROTI PREPAZCE (B stena) - to spolehlive najde konec prepazky, ale
// NEDETEKUJE, ze hned za prepazkou nasleduje otvor dveri (zadna
// kolize = "volno", i kdyz jde o funkcni otvor, ne o skutecny prostor
// pro nohu regalu).
//
// TATO VERZE nahrazuje jen STEP1 (Z-anchor) FIXNI hodnotou odvozenou
// z realneho skenu R_D meshe (mezera >150mm v Y=[200,900] pasmu,
// vzdalenejsi hrana + 30mm rezerva) - kroky 2-7 (max rozpon, sloupcove
// plneni, protazeni vyrez noh, rail floor, fyzicky strop, vyskove
// patrovani) jsou 1:1 PREVZATE z tmp_2026-08-31_batch_pipeline.js beze
// zmeny (stejna metodika, jen jiny vstupni anchor).
const THREE = require("three");
const { buildPlainAtDepth, buildVyrezAtDepth } = require("/opt/konfigurator/scripts/tmp_2026-08-30_build_depth_variants_both.js");

const D = 326, T = 30, H = 1180;
const CAP_H = 260, CUTOUT_H = 395;
const TOP_Y = H - CAP_H; // 920
const CAP_FLANGE_THICKNESS = 3;
const KAT = "/opt/konfigurator/webapp/katalog/";
const ENDCAP = KAT + "product_3071.glb";
const EUROBOX_GLB = { 120: KAT + "product_3788.glb", 170: KAT + "product_3793.glb", 220: KAT + "product_3794.glb", 270: KAT + "product_3795.glb" };
const EUROBOX_PID = { 120: "product_3788", 170: "product_3793", 220: "product_3794", 270: "product_3795" };
const CONNECTOR_POS = { 1: [15, 415], 2: [15, 415, 816], 3: [15, 415, 816, 1217] };
const CLEAR_SPACING = { 1: 430, 2: 832, 3: 1232 };
const WIDTH_TRY_ORDER = [3, 2, 1];
const Q_ALONG_Z = [-0.707107, 0, 0, 0.707107];
const Q_ALONG_X = [0, 0, -0.707107, 0.707107];
const Q_ENDCAP_UP = [0.7071067811865475, 0, 0, 0.7071067811865475];

function stepUntilCollision1D(testFn, dir, maxSteps, label) {
  let steps = 0, collided = false, val = 0;
  while (steps < maxSteps) {
    val += dir; steps++;
    if (testFn(val)) { collided = true; break; }
  }
  if (!collided) throw new Error(`${label}: zadna kolize po ${maxSteps} krocich`);
  const backoffVal = val - dir * 2;
  const stillColliding = testFn(backoffVal);
  if (stillColliding) throw new Error(`${label}: po 2mm zpet stale koliduje`);
  return backoffVal;
}

// ---- detekce dverniho otvoru v _R_D meshi (car_body_placement_methods.id=1,
// klic "vylouceni_bocniho_dvernich_otvoru_2026_09_02"): mezera >150mm mezi
// Z-serazenymi vertexy v Y pasmu [200,900] ----
function detectDoorGap(wallR) {
  const pos = wallR.geometry.attributes.position.array;
  const zs = [];
  for (let i = 0; i < pos.length; i += 3) {
    const y = pos[i + 1], z = pos[i + 2];
    if (y >= 200 && y <= 900) zs.push(z);
  }
  zs.sort((a, b) => a - b);
  const gaps = [];
  for (let i = 1; i < zs.length; i++) {
    const g = zs[i] - zs[i - 1];
    if (g > 150) gaps.push({ near: zs[i - 1], far: zs[i], gap: g });
  }
  return gaps;
}

function buildVyrezAtDepthExtended(D, Y_new) {
  const base = buildVyrezAtDepth(D);
  const zCenter = T / 2;
  const parts = base.filter(p => !["sloupek-pred-podbehem", "pricka-uzavreni-vyrezu", "zadni-svislice-nad-zarezem"].includes(p.role));
  const orig = base.find(p => p.role === "sloupek-pred-podbehem");
  if (orig) {
    const colX = orig.position[0];
    parts.push({ position: [colX, Y_new / 2, zCenter], quaternion: [0, 0, 0, 1], scale: [1, Y_new / 1000, 1], role: "sloupek-pred-podbehem" });
  }
  const origPricka = base.find(p => p.role === "pricka-uzavreni-vyrezu");
  if (origPricka) {
    parts.push({ position: [origPricka.position[0], Y_new + T / 2, zCenter], quaternion: origPricka.quaternion, scale: origPricka.scale, role: "pricka-uzavreni-vyrezu" });
  }
  const upperLen = TOP_Y - Y_new;
  parts.push({ position: [D - T / 2, (Y_new + TOP_Y) / 2, zCenter], quaternion: [0, 0, 0, 1], scale: [1, upperLen / 1000, 1], role: "zadni-svislice-nad-zarezem" });
  return parts;
}

function runPipelineDoorFixed(engine, opts) {
  opts = opts || {};
  const log = [];
  const P = (...a) => { const s = a.join(" "); log.push(s); if (opts.verbose) console.error(s); };
  const { collidesWithWalls, buildLegObject, boxL0, boxB0, mirror, dirZtoBulkhead } = engine;
  const sgn = mirror ? -1 : +1;

  function toWorld(localParts, offsetX, offsetY, anchorZ) {
    return localParts.map(p => ({
      part_id: p.part_id || "Object_7",
      position: [offsetX + sgn * p.position[0], p.position[1] + offsetY, anchorZ + p.position[2]],
      quaternion: p.quaternion, scale: p.scale, role: p.role,
    }));
  }
  function groupAt(localParts, offsetX, offsetY, anchorZ) { return buildLegObject(toWorld(localParts, offsetX, offsetY, anchorZ)); }

  // ---- DOOR DETECTION + NEW FIXED FRONT ANCHOR (replaces original step1 Z-search) ----
  const gaps = detectDoorGap(engine.wallR);
  if (gaps.length !== 1) throw new Error(`ocekavana presne 1 dverni mezera >150mm, nalezeno ${gaps.length}: ${JSON.stringify(gaps)}`);
  const doorGap = gaps[0];
  const dirAway0 = -dirZtoBulkhead;
  // "far" hrana dveri = ta, ktera je DAL od prepazky ve smeru dirAway0
  const farEdge = dirAway0 > 0 ? doorGap.far : doorGap.near;
  const nearEdge = dirAway0 > 0 ? doorGap.near : doorGap.far;
  const DOOR_CLEARANCE = opts.doorClearance != null ? opts.doorClearance : 30;
  let anchorZ = farEdge + dirAway0 * DOOR_CLEARANCE;
  P(`doorGap near=${nearEdge.toFixed(2)} far=${farEdge.toFixed(2)} width=${doorGap.gap.toFixed(2)} dirAway=${dirAway0} newFrontAnchorZ=${anchorZ.toFixed(2)}`);

  // ---- STEP1 (adapted): floor (Y) + wall (X) collision stepping AT FIXED anchorZ ----
  let offsetX = -D / 2;
  let offsetY = (boxB0.max.y / 2) - H / 2;
  const plainParts0 = buildPlainAtDepth(D);

  if (collidesWithWalls(groupAt(plainParts0, offsetX, offsetY, anchorZ))) {
    throw new Error("step1: pocatecni pozice na novem anchoru jiz koliduje - nutna rucni kontrola");
  }
  const dY = stepUntilCollision1D((v) => collidesWithWalls(groupAt(plainParts0, offsetX, offsetY + v, anchorZ)), -1, 2500, "podlaha");
  offsetY += dY;
  const dX = stepUntilCollision1D((v) => collidesWithWalls(groupAt(plainParts0, offsetX + v, offsetY, anchorZ)), mirror ? -1 : +1, 2500, "stenaL");
  offsetX += dX;
  P(`step1(doorfixed) OK offsetX=${offsetX.toFixed(1)} offsetY=${offsetY.toFixed(1)} anchorZ=${anchorZ.toFixed(1)} mirror=${mirror} dirZtoBulkhead=${dirZtoBulkhead}`);
  const frontAnchorZ = anchorZ;

  // ---- zbytek 1:1 z tmp_2026-08-31_batch_pipeline.js ----
  const dirAway = dirAway0;
  const vyrezPartsProbe = buildVyrezAtDepth(D);
  function groupAtAnchor(localParts, aZ) { return groupAt(localParts, offsetX, offsetY, aZ); }
  const hardEdgeZ = dirAway > 0 ? boxL0.max.z : boxL0.min.z;
  function findNextCollisionZ(fromZ, maxSteps) {
    let steps = 0, z = fromZ;
    while (steps < maxSteps) {
      const next = z + dirAway;
      const pastEdge = dirAway > 0 ? next > hardEdgeZ : next < hardEdgeZ;
      if (pastEdge) return { z: null, hitEdge: true };
      z = next; steps++;
      if (collidesWithWalls(groupAtAnchor(vyrezPartsProbe, z))) return { z, hitEdge: false };
    }
    return { z: null, hitEdge: false };
  }
  let cursor = frontAnchorZ;
  let lastCollisionZ = null;
  let openEndFallback = false;
  const MAXSTEPS2 = 5000, LOOKAHEAD_MAX = 2500, LOOKAHEAD_STEP = 50;
  for (let iter = 0; iter < 10; iter++) {
    const r = findNextCollisionZ(cursor, MAXSTEPS2);
    if (r.z === null) {
      if (r.hitEdge && lastCollisionZ === null) { openEndFallback = true; lastCollisionZ = hardEdgeZ; break; }
      if (lastCollisionZ === null) throw new Error("step2: zadna kolize nalezena (rear boundary)");
      break;
    }
    const collisionZ = r.z;
    lastCollisionZ = collisionZ;
    let resumeZ = null;
    for (let jump = LOOKAHEAD_STEP; jump <= LOOKAHEAD_MAX; jump += LOOKAHEAD_STEP) {
      const testZ = collisionZ + dirAway * jump;
      const pastEdge = dirAway > 0 ? testZ > hardEdgeZ : testZ < hardEdgeZ;
      if (pastEdge) break;
      if (!collidesWithWalls(groupAtAnchor(vyrezPartsProbe, testZ))) { resumeZ = testZ; break; }
    }
    if (resumeZ === null) break;
    const confirm = findNextCollisionZ(resumeZ, MAXSTEPS2);
    if (confirm.z === null) break;
    P(`step2 island: kolize na Z=${collisionZ.toFixed(1)}, uvolneni potvrzeno dal na Z=${resumeZ.toFixed(1)} (dalsi kolize Z=${confirm.z.toFixed(1)}) - pokracuji`);
    cursor = resumeZ;
  }
  const BACKOFF = 20;
  const REAR_ANCHOR_Z = lastCollisionZ - dirAway * BACKOFF;
  if (!openEndFallback && collidesWithWalls(groupAtAnchor(vyrezPartsProbe, REAR_ANCHOR_Z))) throw new Error("step2: po 20mm zpet stale koliduje");
  P(`step2 OK REAR_ANCHOR_Z=${REAR_ANCHOR_Z.toFixed(1)} maxSpan=${Math.abs(REAR_ANCHOR_Z - frontAnchorZ).toFixed(1)} openEndFallback=${openEndFallback}`);

  // OPRAVA (bug #2 "podbeh bez konce", 2026-09-03, sjednoceno z git commit
  // 0ceb07f / bot24 a z tmp_2026-08-31_batch_pipeline.js - viz tam podrobny
  // komentar): kandidatni test "vejde se sem vyrez noha?" driv pouzival
  // RIGIDNI buildVyrezAtDepth(D) s FIXNIM CUTOUT_H, coz zpusobovalo
  // predcasne zastaveni hladoveho planovani sloupcu, kdyz podbeh na dane Z
  // presahl fixni predpoklad designu. Oprava: profil boci (wall-side)
  // strany nohy se prepocita CERSTVE (0..strop sken) na KAZDE kandidatni Z
  // zvlast (shape_geometry_methods.id=6), misto testovani pevneho tvaru.
  function wallPieceAt(aZ, bottomY) {
    const lenY = TOP_Y - bottomY, centerY = (bottomY + TOP_Y) / 2;
    return buildLegObject([{
      position: [offsetX + sgn * (D - T / 2), centerY + offsetY, aZ + T / 2],
      quaternion: [0, 0, 0, 1], scale: [1, lenY / 1000, 1],
    }]);
  }
  function computeYNewWall(aZ) {
    if (!collidesWithWalls(wallPieceAt(aZ, 0))) return 0;
    let collisionBottomY = null;
    for (let bottomY = TOP_Y - 1; bottomY >= 0; bottomY--) {
      if (collidesWithWalls(wallPieceAt(aZ, bottomY))) { collisionBottomY = bottomY; break; }
    }
    if (collisionBottomY === null) return 0;
    return collisionBottomY + 20;
  }
  function legPartsFor(type, yNew) { return type === "vyrez" ? buildVyrezAtDepthExtended(D, yNew != null ? yNew : CUTOUT_H) : buildPlainAtDepth(D); }
  const legs = [{ type: "plain", anchorZ: frontAnchorZ, yNew: null }];
  const columns = [];
  function railsAndConnectorsForColumn(N, legFrom, legTo) {
    const zFromRaw = legFrom.anchorZ + dirAway * T, zToRaw = legTo.anchorZ;
    const railZFrom = Math.min(zFromRaw, zToRaw), railZTo = Math.max(zFromRaw, zToRaw);
    const railLen = railZTo - railZFrom, railZCenter = (railZFrom + railZTo) / 2;
    const crossLen = D - 2 * T, crossXCenter = D / 2;
    const Y = 410;
    const parts = [];
    parts.push({ part_id: "Object_7", position: [offsetX + sgn * (T / 2), Y + offsetY, railZCenter], quaternion: Q_ALONG_Z, scale: [1, railLen / 1000, 1], role: "nosnik" });
    parts.push({ part_id: "Object_7", position: [offsetX + sgn * (D - T / 2), Y + offsetY, railZCenter], quaternion: Q_ALONG_Z, scale: [1, railLen / 1000, 1], role: "nosnik" });
    CONNECTOR_POS[N].forEach(localZ => {
      const zc = railZFrom + (dirAway > 0 ? localZ : (railLen - localZ));
      parts.push({ part_id: "Object_7", position: [offsetX + sgn * crossXCenter, Y + offsetY, zc], quaternion: Q_ALONG_X, scale: [1, crossLen / 1000, 1], role: "spojnice" });
    });
    return { parts, railZFrom, railZTo };
  }
  function wholeAssemblyParts() {
    let parts = [];
    legs.forEach(leg => { parts.push(...toWorld(legPartsFor(leg.type, leg.yNew), offsetX, offsetY, leg.anchorZ)); });
    columns.forEach(col => { parts.push(...railsAndConnectorsForColumn(col.N, legs[col.legFromIdx], legs[col.legToIdx]).parts); });
    return parts;
  }
  function assemblyCollides(extra) { return collidesWithWalls(buildLegObject([...wholeAssemblyParts(), ...(extra || [])])); }
  function determineLegType(anchorZ) {
    const plainParts = toWorld(buildPlainAtDepth(D), offsetX, offsetY, anchorZ);
    return collidesWithWalls(buildLegObject(plainParts)) ? "vyrez" : "plain";
  }

  let colIdx = 0;
  while (true) {
    const lastLeg = legs[legs.length - 1];
    let placed = false;
    for (const N of WIDTH_TRY_ORDER) {
      const clear = CLEAR_SPACING[N];
      const newAnchorZ = lastLeg.anchorZ + dirAway * (T + clear);
      const beyond = dirAway > 0 ? newAnchorZ > REAR_ANCHOR_Z : newAnchorZ < REAR_ANCHOR_Z;
      if (beyond) continue;
      const candidateType = determineLegType(newAnchorZ);
      const candidateYNew = candidateType === "vyrez" ? computeYNewWall(newAnchorZ) : null;
      const candidateLeg = { type: candidateType, anchorZ: newAnchorZ, yNew: candidateYNew };
      const candidateLegParts = toWorld(legPartsFor(candidateType, candidateYNew), offsetX, offsetY, newAnchorZ);
      const railParts = railsAndConnectorsForColumn(N, lastLeg, candidateLeg).parts;
      if (!assemblyCollides([...candidateLegParts, ...railParts])) {
        legs.push(candidateLeg);
        columns.push({ N, legFromIdx: legs.length - 2, legToIdx: legs.length - 1 });
        placed = true;
        break;
      }
    }
    if (!placed) break;
    colIdx++;
    if (colIdx > 20) break;
  }
  P(`step3 OK legs=${legs.length} columns=${columns.length} N=[${columns.map(c => c.N).join(",")}]`);
  if (columns.length === 0) return { ok: false, reason: "zadny sloupec se nevejde", log };

  // Y_new uz spocitan cerstve (computeYNewWall) pri umisteni v STEP3 - tady
  // uz jen znovu overujeme na FINALNI pozici (bezpecnostni sit), misto
  // aby se prepocitaval NAVIC (a jinak/uzeji, jen 0..CUTOUT_H).
  const step4 = {};
  function buildPiece(bottomY, anchorZ) {
    const lenY = TOP_Y - bottomY;
    const centerY = (bottomY + TOP_Y) / 2 + offsetY;
    const xw = offsetX + sgn * (D - T / 2);
    return { part_id: "Object_7", position: [xw, centerY, anchorZ + T / 2], quaternion: [0, 0, 0, 1], scale: [1, lenY / 1000, 1], role: "zadni-svislice-nad-zarezem" };
  }
  legs.forEach((leg, i) => {
    if (leg.type !== "vyrez") return;
    const Y_NEW = leg.yNew;
    if (collidesWithWalls(buildLegObject([buildPiece(Y_NEW, leg.anchorZ)]))) throw new Error(`step4 leg${i}: Y_new=${Y_NEW} koliduje na finalni pozici`);
    step4[i] = { Y_new: Y_NEW };
  });
  P(`step4 OK ${JSON.stringify(step4)}`);

  function columnFloorBase(legFromIdx, legToIdx) {
    const fromV = legs[legFromIdx].type === "vyrez", toV = legs[legToIdx].type === "vyrez";
    if (!fromV && !toV) return 200;
    const vals = [];
    if (fromV) vals.push(step4[legFromIdx].Y_new);
    if (toV) vals.push(step4[legToIdx].Y_new);
    return Math.max(...vals);
  }
  const step5 = {};
  columns.forEach((col, colIdx2) => {
    const legFrom = legs[col.legFromIdx], legTo = legs[col.legToIdx];
    const floorLegBased = columnFloorBase(col.legFromIdx, col.legToIdx);
    let Y0 = floorLegBased + T / 2;
    const railParts0 = railsAndConnectorsForColumn(col.N, legFrom, legTo).parts.map(p => ({ ...p, position: [p.position[0], Y0 + offsetY, p.position[2]] }));
    let finalFloor = floorLegBased;
    if (collidesWithWalls(buildLegObject(railParts0))) {
      let Y = Y0, s = 0, cleared = null;
      while (s < 600) {
        Y += 1; s++;
        const rp = railsAndConnectorsForColumn(col.N, legFrom, legTo).parts.map(p => ({ ...p, position: [p.position[0], Y + offsetY, p.position[2]] }));
        if (!collidesWithWalls(buildLegObject(rp))) { cleared = Y; break; }
      }
      if (cleared === null) throw new Error(`step5 col${colIdx2}: nenalezena bezkolizni pozice`);
      const withMargin = cleared + 20;
      const rpFinal = railsAndConnectorsForColumn(col.N, legFrom, legTo).parts.map(p => ({ ...p, position: [p.position[0], withMargin + offsetY, p.position[2]] }));
      if (collidesWithWalls(buildLegObject(rpFinal))) throw new Error(`step5 col${colIdx2}: i po +20mm koliduje`);
      finalFloor = withMargin - T / 2;
    }
    step5[colIdx2] = { finalFloorY: finalFloor };
  });
  P(`step5 OK ${JSON.stringify(step5)}`);

  const step7 = {};
  columns.forEach((col, colIdx2) => {
    const legFrom = legs[col.legFromIdx], legTo = legs[col.legToIdx];
    const zFromRaw = legFrom.anchorZ + dirAway * T, zToRaw = legTo.anchorZ;
    const zFrom = Math.min(zFromRaw, zToRaw), zTo = Math.max(zFromRaw, zToRaw);
    function slab(y) {
      const geo = new THREE.BoxGeometry(D, 10, zTo - zFrom);
      const mesh = new THREE.Mesh(geo);
      mesh.position.set(offsetX + sgn * (D / 2), y, (zFrom + zTo) / 2);
      mesh.updateMatrixWorld(true);
      return mesh;
    }
    // Start SAFELY nad znamou bezkolizni podlahou tohoto sloupce (ne pevne
    // 900mm jako u puvodniho batch_pipeline.js) - u vozidel/pozic, kde je
    // strop nizsi/blize (jako po presunu za dverni otvor), by 900mm uz
    // mohlo byt UVNITR kolize, coz by dalo nespravny (prilis nizky nebo
    // vubec neplatny) vysledek.
    let y = Math.max(200, step5[colIdx2].finalFloorY + T + 10);
    if (collidesWithWalls(slab(y))) throw new Error(`step7 col${colIdx2}: startovni sonda Y=${y.toFixed(1)} jiz koliduje - sloupec nema zadny bezkolizni prostor nad railem`);
    let s = 0, collisionY = null;
    while (s < 1300) { y += 1; s++; if (collidesWithWalls(slab(y))) { collisionY = y; break; } }
    if (collisionY === null) throw new Error(`step7 col${colIdx2}: zadna kolize do Y=${y}`);
    const safeY = collisionY - 2;
    if (collidesWithWalls(slab(safeY))) throw new Error(`step7 col${colIdx2}: po 2mm zpet stale koliduje`);
    step7[colIdx2] = { maxSafeBoxTop: safeY };
  });
  P(`step7 OK ${JSON.stringify(step7)}`);

  return {
    ok: true, log, offsetX, offsetY, sgn, mirror, dirAway, anchorZFront: frontAnchorZ, REAR_ANCHOR_Z,
    legs, columns, step4, step5, step7,
    D, T, H, CAP_H, CUTOUT_H, TOP_Y, doorGap,
  };
}

module.exports = {
  runPipelineDoorFixed, detectDoorGap, buildVyrezAtDepthExtended,
  D, T, H, CAP_H, CUTOUT_H, TOP_Y, CAP_FLANGE_THICKNESS,
  KAT, ENDCAP, EUROBOX_GLB, EUROBOX_PID, CONNECTOR_POS,
  Q_ALONG_Z, Q_ALONG_X, Q_ENDCAP_UP,
};
