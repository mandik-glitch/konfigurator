// bot25, 2026-09-02 - eurobox rack pipeline pro celou rodinu Citroen/e-Jumpy
// (CI13/14/15/18/19/24/25/26). Postaveno na uz existujicich, opravenych
// stavebnich blocich (viz KOMPONENTY_EUROBOXY.md, WORKFLOW.md task brief):
//  - STEP1 (predni noha u prepazky): STANDARDNI bulkhead-kolizni varianta
//    (1:1 z tmp_2026-08-31_batch_pipeline.js: stred nakladoveho prostoru ->
//    podlaha -> prepazka B -> stena L), PROTOZE zadny z 8 Jumpy R_D meshu
//    nema dverni "vylouceni_bocniho_dvernich_otvoru" bug (overeno nize,
//    detectDoorGap na kazdem vozidle pred stavbou - viz report).
//  - Bezpecnostni sit navic (rule A z zadani): i kdyz Jumpy nemá tenhle bug,
//    KAZDA dalsi noha (STEP3 sloupcove plneni) se navic overuje proti
//    detekovanym dvernim mezerám (kdyby nejaka existovala) - candidate se
//    zamitne, pokud by jeho Z-slab spadl do detekovane mezery, i kdyz
//    kolizni test samotny (chybejici material) by to jinak nechal projit.
//  - STEP2 (max rozpon) - island-aware (car_body_placement_methods.id=1,
//    "pokracovani_pres_podbeh") 1:1 z batch_pipeline.js/doorvoid_pipeline.js
//    (identicky kod v obou).
//  - STEP4 (protazeni vyrez nohy), STEP5 (rail floor pres cely rozpon),
//    STEP7 (fyzicky strop) - POUZITA NOVEJSI/bezpecnejsi varianta ze
//    tmp_2026-09-02_doorvoid_pipeline.js (STEP7 start Y odvozeny z
//    finalFloorY místo pevneho 900, robustnejsi pro nizsi stropy).
// Vystup ma STEJNY tvar jako runPipelineDoorFixed() v doorvoid_pipeline.js,
// takze se dá primo pouzit s tmp_2026-09-02_doorvoid_assemble.js::assemble/
// planColumn/validateHeights/applyDoorHeightRule beze zmeny (uz obsahuji
// opravu min(TOP_Y,physCeil) na VSECH patrech + id=7 uhelniky + id=8 vyska
// nohy podle dveri).
const THREE = require("three");
const { buildPlainAtDepth, buildVyrezAtDepth } = require("/opt/konfigurator/scripts/tmp_2026-08-30_build_depth_variants_both.js");
const { detectDoorGap, buildVyrezAtDepthExtended, D, T, H, CAP_H, CUTOUT_H, TOP_Y, CAP_FLANGE_THICKNESS, KAT, ENDCAP, EUROBOX_GLB, EUROBOX_PID, CONNECTOR_POS, Q_ALONG_Z, Q_ALONG_X, Q_ENDCAP_UP } = require("/opt/konfigurator/scripts/tmp_2026-09-02_doorvoid_pipeline.js");
const { confirmDoorGaps } = require("/opt/konfigurator/scripts/tmp_2026-09-02_bot25_confirm_doorgap.js");

const CLEAR_SPACING = { 1: 430, 2: 832, 3: 1232 };
const WIDTH_TRY_ORDER = [3, 2, 1];

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

function runPipelineJumpy(engine, opts) {
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

  // ---- rule (A): sken dvernich mezer v _R_D meshi (Y=[200,900] pasmo, mezera >150mm) ----
  // POZOR: detectDoorGap() samotna je JEN vertex-density heuristika (hleda
  // mezery mezi Z-serazenymi vertexy) - muze davat FALESNE POZITIVA na
  // meshich s ridkou/velkoplochou triangulaci (velky plochy panel = malo
  // vertexu, ale porad SOLIDNI material, trojuhelnik "premosti" mezeru).
  // KAZDY kandidat se proto navic overuje SKUTECNYM koliznim probe testem
  // (confirmDoorGaps - 1mm stepping ke stene na 3 vyskach, porovnano se
  // sousednimi Z pozicemi) - jen POTVRZENE (real:true) mezery se pouziji.
  const cargoZlo0 = boxL0.min.z, cargoZhi0 = boxL0.max.z;
  const refZ0 = (cargoZlo0 + cargoZhi0) / 2;
  const doorGapCheck = confirmDoorGaps(engine, refZ0);
  const doorGaps = doorGapCheck.confirmed;
  P(`doorGapScan rawFound=${doorGapCheck.gapsRaw.length} CONFIRMED_real=${doorGaps.length} falsePositives=${doorGapCheck.rejected.length}`);
  doorGapCheck.rejected.forEach(g => P(`  false-positive (vertex-sparsity, wall actually solid): near=${g.near.toFixed(1)} far=${g.far.toFixed(1)} width=${g.gap.toFixed(1)} midDepths=${JSON.stringify(g.midDepths)}`));
  doorGaps.forEach(g => P(`  CONFIRMED REAL door void: near=${g.near.toFixed(1)} far=${g.far.toFixed(1)} width=${g.gap.toFixed(1)}`));

  // ---- STEP1: standardni bulkhead-anchor (1:1 tmp_2026-08-31_batch_pipeline.js) ----
  const cargoZlo = boxL0.min.z, cargoZhi = boxL0.max.z;
  let offsetX = -D / 2;
  let offsetY = (boxB0.max.y / 2) - H / 2;
  let anchorZ = (cargoZlo + cargoZhi) / 2 - T / 2;
  const plainParts0 = buildPlainAtDepth(D);

  if (collidesWithWalls(groupAt(plainParts0, offsetX, offsetY, anchorZ))) {
    throw new Error("step1: pocatecni pozice jiz koliduje - nutna rucni kontrola");
  }
  const dY = stepUntilCollision1D((v) => collidesWithWalls(groupAt(plainParts0, offsetX, offsetY + v, anchorZ)), -1, 2500, "podlaha");
  offsetY += dY;
  const dZ = stepUntilCollision1D((v) => collidesWithWalls(groupAt(plainParts0, offsetX, offsetY, anchorZ + v)), dirZtoBulkhead, 3500, "prepazkaB");
  anchorZ += dZ;
  const dX = stepUntilCollision1D((v) => collidesWithWalls(groupAt(plainParts0, offsetX + v, offsetY, anchorZ)), mirror ? -1 : +1, 2500, "stenaL");
  offsetX += dX;
  P(`step1 OK offsetX=${offsetX.toFixed(1)} offsetY=${offsetY.toFixed(1)} anchorZ=${anchorZ.toFixed(1)} mirror=${mirror} dirZtoBulkhead=${dirZtoBulkhead}`);

  const dirAway = -dirZtoBulkhead;
  const DOOR_CLEARANCE = 30;
  function overlapsAnyDoorGap(zLo, zHi) {
    for (const g of doorGaps) {
      const gLo = Math.min(g.near, g.far) - DOOR_CLEARANCE, gHi = Math.max(g.near, g.far) + DOOR_CLEARANCE;
      if (zLo <= gHi && zHi >= gLo) return g;
    }
    return null;
  }
  // predni noha zabira world Z in [anchorZ, anchorZ+T] (local z in [0,T])
  let frontAnchorZ = anchorZ;
  const frontHit = overlapsAnyDoorGap(frontAnchorZ, frontAnchorZ + T);
  if (frontHit) {
    const farEdge = dirAway > 0 ? frontHit.far : frontHit.near;
    frontAnchorZ = farEdge + dirAway * DOOR_CLEARANCE;
    P(`step1b: predni noha zasahovala do dverni mezery (near=${frontHit.near.toFixed(1)} far=${frontHit.far.toFixed(1)}) - presunuto na anchorZ=${frontAnchorZ.toFixed(1)}, znovu over floor/wall`);
    if (collidesWithWalls(groupAt(plainParts0, offsetX, offsetY, frontAnchorZ))) throw new Error("step1b: novy anchor po posunu od dverni mezery jiz koliduje");
  }

  // ---- STEP2: max rozpon, island-aware (1:1 z batch_pipeline.js/doorvoid_pipeline.js) ----
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

  // ---- STEP3: sloupcove plneni, hladove nejsirsi-nejdriv, cela sestava; +
  // rule-A bezpecnostni sit: candidate leg se navic zamitne, kdyby jeho
  // Z-slab spadl do jakekoli detekovane dverni mezery (i kdyby samotny
  // kolizni test s chybejicim materialem nic nenasel). ----
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
    // OPRAVA (bot25, 2026-09-02): puvodni vzorec "legFrom.anchorZ + dirAway*T"
    // + "legTo.anchorZ" (beze zmeny) je SPRAVNY jen pro dirAway=+1 (kde
    // legFrom's away-face = anchorZ+T a legTo's bulkhead-face = anchorZ,
    // presne jak overeno na CI14/CI25). Pro dirAway=-1 (napr. CI15/18/19/
    // 24/26 - stena na druhe strane) je to OBRACENE: legFrom's away-face =
    // anchorZ (BEZ posunu) a legTo's bulkhead-face = anchorZ+T (S POSUNEM) -
    // puvodni vzorec by pak cely legTo (delky T) POHLTIL dovnitr railu
    // (skutecna self-kolize, nalezeno na CI15/18/19/24/26). Obecny (funguje
    // pro OBE znamenka dirAway, redukuje se na puvodni vzorec pro dirAway=+1):
    const legFromAwayEdge = legFrom.anchorZ + T / 2 + dirAway * T / 2;
    const legToBulkheadEdge = legTo.anchorZ + T / 2 - dirAway * T / 2;
    const railZFrom = Math.min(legFromAwayEdge, legToBulkheadEdge), railZTo = Math.max(legFromAwayEdge, legToBulkheadEdge);
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

  const doorGapRejections = [];
  let colIdx = 0;
  while (true) {
    const lastLeg = legs[legs.length - 1];
    let placed = false;
    for (const N of WIDTH_TRY_ORDER) {
      const clear = CLEAR_SPACING[N];
      const newAnchorZ = lastLeg.anchorZ + dirAway * (T + clear);
      const beyond = dirAway > 0 ? newAnchorZ > REAR_ANCHOR_Z : newAnchorZ < REAR_ANCHOR_Z;
      if (beyond) continue;
      const legZlo = Math.min(newAnchorZ, newAnchorZ + T), legZhi = Math.max(newAnchorZ, newAnchorZ + T);
      const doorHit = overlapsAnyDoorGap(legZlo, legZhi);
      if (doorHit) { doorGapRejections.push({ N, newAnchorZ, doorHit }); continue; }
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
  P(`step3 OK legs=${legs.length} columns=${columns.length} N=[${columns.map(c => c.N).join(",")}] doorGapRejections=${doorGapRejections.length}`);
  if (columns.length === 0) return { ok: false, reason: "zadny sloupec se nevejde", log };

  // ---- STEP4: protazeni vyrez noh ----
  // Y_new uz spocitan cerstve (computeYNewWall) pri umisteni v STEP3 - tady
  // uz jen znovu overujeme na FINALNI pozici (bezpecnostni sit), misto
  // aby se prepocitaval NAVIC (a jinak/uzeji, jen 0..CUTOUT_H).
  const step4 = {};
  function buildPiece(bottomY, anchorZv) {
    const lenY = TOP_Y - bottomY;
    const centerY = (bottomY + TOP_Y) / 2 + offsetY;
    const xw = offsetX + sgn * (D - T / 2);
    return { part_id: "Object_7", position: [xw, centerY, anchorZv + T / 2], quaternion: [0, 0, 0, 1], scale: [1, lenY / 1000, 1], role: "zadni-svislice-nad-zarezem" };
  }
  legs.forEach((leg, i) => {
    if (leg.type !== "vyrez") return;
    const Y_NEW = leg.yNew;
    if (collidesWithWalls(buildLegObject([buildPiece(Y_NEW, leg.anchorZ)]))) throw new Error(`step4 leg${i}: Y_new=${Y_NEW} koliduje na finalni pozici`);
    step4[i] = { Y_new: Y_NEW };
  });
  P(`step4 OK ${JSON.stringify(step4)}`);

  // ---- STEP5: rail floor pres cely rozpon (identicke oběma zdrojum) ----
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

  // ---- STEP7: strop, START odvozeny z finalFloorY (bezpecnejsi nez pevne 900 - doorvoid_pipeline.js varianta) ----
  const step7 = {};
  columns.forEach((col, colIdx2) => {
    const legFrom = legs[col.legFromIdx], legTo = legs[col.legToIdx];
    // stejna oprava dirAway sign jako v railsAndConnectorsForColumn vyse
    const zFromRaw = legFrom.anchorZ + T / 2 + dirAway * T / 2, zToRaw = legTo.anchorZ + T / 2 - dirAway * T / 2;
    const zFrom = Math.min(zFromRaw, zToRaw), zTo = Math.max(zFromRaw, zToRaw);
    function slab(y) {
      const geo = new THREE.BoxGeometry(D, 10, zTo - zFrom);
      const mesh = new THREE.Mesh(geo);
      mesh.position.set(offsetX + sgn * (D / 2), y, (zFrom + zTo) / 2);
      mesh.updateMatrixWorld(true);
      return mesh;
    }
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
    D, T, H, CAP_H, CUTOUT_H, TOP_Y, doorGaps, doorGapRejections, frontDoorFix: !!frontHit,
    doorGapRaw: doorGapCheck.gapsRaw, doorGapFalsePositives: doorGapCheck.rejected,
  };
}

module.exports = {
  runPipelineJumpy, detectDoorGap,
  D, T, H, CAP_H, CUTOUT_H, TOP_Y, CAP_FLANGE_THICKNESS,
  KAT, ENDCAP, EUROBOX_GLB, EUROBOX_PID, CONNECTOR_POS,
  Q_ALONG_Z, Q_ALONG_X, Q_ENDCAP_UP,
};
