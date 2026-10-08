// ⭐ NOSNY PRODUKCNI SOUBOR (prejmenovano z tmp_2026-09-01_bot16_run_
// pipeline.js 2026-09-12, pres bot3) - PLATI PRO CADDY, FORD CONNECT
// I DOBLO (K-075), navzdory malemu/lokalnimu vzhledu nazvu. Puvodni
// "tmp_" prefix uz jednou zpusobil skoro-smazani jineho zivotne
// duleziteho souboru (tmp_2026-08-31_batch_pipeline.js) pri ukilzu -
// tenhle soubor NEMAZAT, NEPREJMENOVAT ZPET na tmp_. Sourozenci
// 2026-09-01_bot16_leg_builders.js / 2026-09-01_bot16_env_factory.js
// jsou stejne dulezite (require() odsud).
//
// Master pipeline: Caddy/Ford Connect/Doblo, leva stena, euroboxy 30x30.
// bot16 2026-09-01. Loop pres 16 konfigurace (12 distinct karoserii, 4 sdilene
// mezi Caddy/Ford-Connect noveho typu se pouziji 2x - jednou s Caddy nohou
// H=1080, jednou s Ford nohou H=1100).
const THREE = require("three");
const fs = require("fs");
const { makeEnv, KAT } = require("/opt/konfigurator/scripts/2026-09-01_bot16_env_factory.js");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const { T, D, buildPlainWithCap, buildVyrezWithCap, buildFordPlain } = require("/opt/konfigurator/scripts/2026-09-01_bot16_leg_builders.js");

const CARB = KAT + "car_bodies/";
const OBJ7 = KAT + "Object_7.glb";
const ENDCAP = KAT + "product_3071.glb";
const EUROBOX_GLB = { 120: KAT + "product_3788.glb", 170: KAT + "product_3793.glb", 220: KAT + "product_3794.glb", 270: KAT + "product_3795.glb" };
const EUROBOX_PID = { 120: "product_3788", 170: "product_3793", 220: "product_3794", 270: "product_3795" };
const CONNECTOR_POS = { 1: [15, 415], 2: [15, 415, 816], 3: [15, 415, 816, 1217] };
const CLEAR_SPACING = { 1: 430, 2: 832, 3: 1232 };
const WIDTH_TRY_ORDER = [3, 2, 1];
const Q_ALONG_Z = [-0.707107, 0, 0, 0.707107];
const Q_ALONG_X = [0, 0, -0.707107, 0.707107];
const Q_ENDCAP_UP = [0.7071067811865475, 0, 0, 0.7071067811865475];
const CAP_FLANGE_THICKNESS = 3;
const HEIGHTS_DESC = [270, 220, 170, 120];

// `backoffMm` (Robert 2026-09-12, pres bot3, nova paralelni serie "AA-AE":
// "od predni prepazky se po kolizi vracime o 10mm") - vychozi 2 zachovava
// presne dnesni chovani pro VSECHNY tri volani (podlaha/prepazkaB/stenaL
// v runVehicle nize), zmena se predava explicitne JEN pro prepazkaB
// volani nove serie - podlaha a stenaL zustavaji na 2mm.
function stepUntilCollision1D(testFn, dir, maxSteps, label, backoffMm) {
  backoffMm = backoffMm == null ? 2 : backoffMm;
  let start = 0;
  // pokud pocatecni odhad uz koliduje (napr. spatny initial guess kdyz karoserie
  // ma neobvykly Y/Z offset lokalnich souradnic), NEJDRIV uhni v OPACNEM smeru,
  // dokud nejsme cisti - teprve pak zacni normalni kolizni krokovani z cisteho mista.
  if (testFn(start)) {
    let back = 0, cleared = false;
    for (let i = 0; i < maxSteps; i++) {
      back -= dir;
      if (!testFn(back)) { cleared = true; break; }
    }
    if (!cleared) throw new Error(`${label}: pocatecni pozice koliduje a nelze se z ni vyhrabat po ${maxSteps} krocich`);
    start = back;
  }
  let steps = 0, collided = false, val = start;
  while (steps < maxSteps) {
    val += dir; steps++;
    if (testFn(val)) { collided = true; break; }
  }
  if (!collided) throw new Error(`${label}: zadna kolize po ${maxSteps} krocich`);
  const backoffVal = val - dir * backoffMm;
  const stillColliding = testFn(backoffVal);
  if (stillColliding) throw new Error(`${label}: po ${backoffMm}mm zpet stale koliduje`);
  return backoffVal;
}

function legPartsFor(cfg, type, overrides) {
  if (cfg.family === "ford") return buildFordPlain({ H: cfg.H });
  if (type === "plain") return buildPlainWithCap({ H: cfg.H, CAP_H: cfg.CAP_H, capRight: cfg.capRight });
  return buildVyrezWithCap({ H: cfg.H, CAP_H: cfg.CAP_H, capRight: cfg.capRight, CUTOUT_H: (overrides && overrides.CUTOUT_H) || cfg.CUTOUT_H_design, colRight: cfg.colRight_design });
}

function runVehicle(cfg) {
  const log = [];
  // Nova paralelni serie "AA-AE" (Robert 2026-09-12, pres bot3) - vychozi
  // hodnoty PRESNE zachovavaji dnesni chovani vsech existujicich sestav
  // (2mm/20mm), nova hodnota se predava explicitne jen z volajiciho
  // (cfg.prepazkaBackoffMm/cfg.podbehClearanceMm). `podbehClearanceMm`
  // se pouziva na DVOU mistech (STEP4 noha, STEP5 nosniky sloupce) -
  // ROZHODNUTI bot3 2026-09-12 ("obe reagujou na kolizi s podbehem,
  // nesourodost 30/20 vedle sebe bych neumel zduvodnit"), NE zmereny
  // fakt o dvou oddelenych mechanismech - kdyby se ukazalo, ze Robert
  // mysli jen nohu, je to jednoradkova zmena rozdelit je zpet.
  const prepazkaBackoffMm = cfg.prepazkaBackoffMm == null ? 2 : cfg.prepazkaBackoffMm;
  const podbehClearanceMm = cfg.podbehClearanceMm == null ? 20 : cfg.podbehClearanceMm;
  try {
  const env = makeEnv(cfg.bodyPrefix);
  const { collidesWithWalls, buildLegObject, boxL0, boxB0 } = env;

  function toWorld(localParts, offsetX, offsetY, anchorZ) {
    return localParts.map(p => ({
      part_id: p.part_id || "Object_7",
      position: [offsetX - p.position[0], p.position[1] + offsetY, anchorZ + p.position[2]],
      quaternion: p.quaternion, scale: p.scale, role: p.role,
    }));
  }
  function groupAt(localParts, offsetX, offsetY, anchorZ) { return buildLegObject(toWorld(localParts, offsetX, offsetY, anchorZ)); }

  // ---- STEP 1: predni (plain) noha - podlaha -> prepazka B -> stena L ----
  const plainParts0 = legPartsFor(cfg, "plain");
  let offsetX = -D / 2;
  let offsetY = ((boxL0.min.y + boxL0.max.y) / 2) - cfg.H / 2;
  let anchorZ = ((boxL0.min.z + boxL0.max.z) / 2) - T / 2;

  const dY = stepUntilCollision1D(v => collidesWithWalls(groupAt(plainParts0, offsetX, offsetY + v, anchorZ)), -1, 3000, "podlaha");
  offsetY += dY;
  const dZ = stepUntilCollision1D(v => collidesWithWalls(groupAt(plainParts0, offsetX, offsetY, anchorZ + v)), -1, 5000, "prepazkaB", prepazkaBackoffMm);
  anchorZ += dZ;
  const dX = stepUntilCollision1D(v => collidesWithWalls(groupAt(plainParts0, offsetX + v, offsetY, anchorZ)), -1, 3000, "stenaL");
  offsetX += dX;
  log.push(`step1 OK: offsetX=${offsetX.toFixed(1)} offsetY=${offsetY.toFixed(1)} anchorZ=${anchorZ.toFixed(1)}`);
  const frontAnchorZ = anchorZ;

  // ---- STEP 2: max rozpon (vyrez pokud existuje, jinak plain) krokovani dozadu.
  // Karoserie je FLIPNUTA (prepazka B na velke ZAPORNE Z) - "dozadu" (smerem
  // k otevrenemu konci) je ROSTOUCI Z (stejna konvence jako Vivaro po flipu).
  const reachParts = cfg.hasVyrez ? legPartsFor(cfg, "vyrez") : plainParts0;
  // horni mez hledani: realny konec modelovane karoserie (boxL0.max.z) + rezerva -
  // nektere starsi GLB modely nemaji uzavreny zadni roh (otevrena zadni brana bez
  // modelovaneho ramu), takze kolizni sonda by jinak bezela donekonecna.
  const searchCapZ = boxL0.max.z + 300;
  let z2 = frontAnchorZ, steps2 = 0, coll2 = null;
  while (steps2 < 6000 && z2 < searchCapZ) { z2 += 1; steps2++; if (collidesWithWalls(groupAt(reachParts, offsetX, offsetY, z2))) { coll2 = z2; break; } }
  let REAR_ANCHOR_Z;
  if (coll2 === null) {
    // FALLBACK: zadny modelovany zadni roh nalezen do konce steny L - pouzij
    // realny konec karoserie (boxL0.max.z) jako fyzickou hranici, s rezervou T+20mm.
    REAR_ANCHOR_Z = boxL0.max.z - T - 20;
    log.push(`step2 FALLBACK (zadna kolize do Z=${searchCapZ.toFixed(0)} - karoserie nema modelovany zadni roh): REAR_ANCHOR_Z=${REAR_ANCHOR_Z.toFixed(1)} (= konec steny L ${boxL0.max.z.toFixed(1)} - T - 20)`);
  } else {
    REAR_ANCHOR_Z = coll2 - 20;
    if (collidesWithWalls(groupAt(reachParts, offsetX, offsetY, REAR_ANCHOR_Z))) throw new Error("step2: po 20mm zpet stale koliduje");
  }
  log.push(`step2 OK: REAR_ANCHOR_Z=${REAR_ANCHOR_Z.toFixed(1)} maxSpan=${(REAR_ANCHOR_Z - frontAnchorZ).toFixed(1)}`);

  // ---- STEP 3: hladove plneni sloupcu (nejsirsi-nejdriv, plain preferovane) ----
  const legs = [{ type: "plain", anchorZ: frontAnchorZ }];
  const columns = [];
  function partsToWorldFor(type, anchorZ, overrides) { return toWorld(legPartsFor(cfg, type, overrides), offsetX, offsetY, anchorZ); }
  function railsForColumn(N, legFrom, legTo) {
    // legFrom = blize prepazce (NIZSI Z, karoserie flipnuta), legTo = dal (VYSSI Z)
    const railZFrom = legFrom.anchorZ + T, railZTo = legTo.anchorZ;
    const railLen = railZTo - railZFrom, railZCenter = (railZFrom + railZTo) / 2;
    const crossLen = D - 2 * T, crossXCenter = D / 2, Y = offsetY + 400;
    const parts = [];
    parts.push({ part_id: "Object_7", position: [offsetX - T / 2, Y, railZCenter], quaternion: Q_ALONG_Z, scale: [1, railLen / 1000, 1], role: "probe-rail" });
    parts.push({ part_id: "Object_7", position: [offsetX - (D - T / 2), Y, railZCenter], quaternion: Q_ALONG_Z, scale: [1, railLen / 1000, 1], role: "probe-rail" });
    CONNECTOR_POS[N].forEach(lz => parts.push({ part_id: "Object_7", position: [offsetX - crossXCenter, Y, railZFrom + lz], quaternion: Q_ALONG_X, scale: [1, crossLen / 1000, 1], role: "probe-conn" }));
    return parts;
  }
  function wholeAssemblyParts(extraLeg, extraRailParts) {
    let parts = [];
    legs.forEach(l => parts.push(...partsToWorldFor(l.type, l.anchorZ)));
    columns.forEach(c => parts.push(...railsForColumn(c.N, legs[c.legFromIdx], legs[c.legToIdx])));
    if (extraLeg) parts.push(...partsToWorldFor(extraLeg.type, extraLeg.anchorZ));
    if (extraRailParts) parts.push(...extraRailParts);
    return parts;
  }
  const TYPE_TRY = cfg.hasVyrez ? ["plain", "vyrez"] : ["plain"];
  // `forcedColumnWidths` (Robert 2026-09-12, pres bot3, nova serie "AA-AE"
  // - "regál na celou stěnu auta"): vychozi (undefined) NEMENI zavedene
  // hladove "nejsirsi-nejdriv" hledani ani o radek. Kdyz je zadano (pole N
  // hodnot), vynecha se hledani poradi a pouzije se PRESNE tahle sekvence -
  // POUZE proto, aby nova serie replikovala STEJNOU skladbu sloupcu jako
  // existujici K-075 varianta C (sestava 279, N=[1,2]), kde se ukazalo, ze
  // hladovy vyber je citlivy na ~15mm rozdil v rekonstruovanem cfg (na
  // hranici REAR_ANCHOR_Z) a bez vynuceni vychazi jinak (jen 1 sloupec
  // misto 2) - kolizni kontrola KAZDEHO sloupce se presto provadi beze
  // zmeny, vynucene poradi zadnou kolizi neobchazi, jen neprohledava
  // alternativy.
  const forcedColumnWidths = cfg.forcedColumnWidths || null;
  let colIdx = 0;
  while (colIdx < 20) {
    if (forcedColumnWidths && colIdx >= forcedColumnWidths.length) break;
    const lastLeg = legs[legs.length - 1];
    let placed = false;
    const widthsToTry = forcedColumnWidths ? [forcedColumnWidths[colIdx]] : WIDTH_TRY_ORDER;
    outer:
    for (const N of widthsToTry) {
      const newAnchorZ = lastLeg.anchorZ + T + CLEAR_SPACING[N];
      if (!forcedColumnWidths && newAnchorZ > REAR_ANCHOR_Z + 500) continue;
      for (const type of TYPE_TRY) {
        const candidateLeg = { type, anchorZ: newAnchorZ };
        const railParts = railsForColumn(N, lastLeg, candidateLeg);
        const assembly = buildLegObject([...wholeAssemblyParts(candidateLeg, railParts)]);
        if (!collidesWithWalls(assembly)) {
          legs.push(candidateLeg);
          columns.push({ N, legFromIdx: legs.length - 2, legToIdx: legs.length - 1 });
          placed = true; break outer;
        }
      }
    }
    if (!placed) {
      if (forcedColumnWidths) throw new Error(`forcedColumnWidths[${colIdx}]=${forcedColumnWidths[colIdx]}: zadny typ (plain/vyrez) nekoliduje - vynucena sirka se sem nevejde`);
      break;
    }
    colIdx++;
  }
  log.push(`step3 OK: legs=${legs.length} columns=${columns.length} ${JSON.stringify(columns.map(c => c.N))}`);
  if (columns.length === 0) { log.push("NIC SE NEVEJDE (0 sloupcu)"); return { ok: false, reason: "no-columns", log, cfg }; }

  // ---- STEP 4: vyrez protazeni (FRESH per-vehicle, pro kazdou vyrez nohu) ----
  const vyrezYnew = {};
  legs.forEach((leg, i) => {
    if (leg.type !== "vyrez") return;
    const CAP_H = cfg.CAP_H, TOP_Y = cfg.H - CAP_H;
    const CUTOUT_H_START = cfg.CUTOUT_H_design;
    function buildPiece(bottomY) {
      const lenY = TOP_Y - bottomY, centerY = (bottomY + TOP_Y) / 2;
      return { part_id: "Object_7", position: [offsetX - (D - T / 2), centerY + offsetY, leg.anchorZ + T / 2], quaternion: [0, 0, 0, 1], scale: [1, lenY / 1000, 1], role: "zadni-svislice-nad-zarezem-probe" };
    }
    let collisionBottomY = null;
    for (let bY = CUTOUT_H_START - 1; bY >= 0; bY--) {
      if (collidesWithWalls(buildLegObject([buildPiece(bY)]))) { collisionBottomY = bY; break; }
    }
    const Y_NEW = (collisionBottomY === null) ? 0 : collisionBottomY + podbehClearanceMm;
    if (collidesWithWalls(buildLegObject([buildPiece(Y_NEW)]))) throw new Error(`step4 leg[${i}]: po ${podbehClearanceMm}mm zpet stale koliduje`);
    vyrezYnew[i] = Y_NEW;
    log.push(`step4 leg[${i}] anchorZ=${leg.anchorZ.toFixed(1)}: Y_new=${Y_NEW} (design start ${CUTOUT_H_START})`);
  });

  // ---- STEP 5: rail floor fresh kontrola per sloupec ----
  function legFloorOf(i) { return legs[i].type === "plain" ? 0 : vyrezYnew[i]; }
  const step5 = {};
  columns.forEach((col, ci) => {
    const legFrom = legs[col.legFromIdx], legTo = legs[col.legToIdx];
    const floorLegBased = Math.max(legFloorOf(col.legFromIdx), legFloorOf(col.legToIdx));
    let Y = floorLegBased + T / 2;
    function railsAt(Yc) {
      const railZFrom = legFrom.anchorZ + T, railZTo = legTo.anchorZ;
      const railLen = railZTo - railZFrom, railZCenter = (railZFrom + railZTo) / 2;
      const crossLen = D - 2 * T, crossXCenter = D / 2;
      const parts = [];
      parts.push({ part_id: "Object_7", position: [offsetX - T / 2, Yc + offsetY, railZCenter], quaternion: Q_ALONG_Z, scale: [1, railLen / 1000, 1], role: "r" });
      parts.push({ part_id: "Object_7", position: [offsetX - (D - T / 2), Yc + offsetY, railZCenter], quaternion: Q_ALONG_Z, scale: [1, railLen / 1000, 1], role: "r" });
      CONNECTOR_POS[col.N].forEach(lz => parts.push({ part_id: "Object_7", position: [offsetX - crossXCenter, Yc + offsetY, railZFrom + lz], quaternion: Q_ALONG_X, scale: [1, crossLen / 1000, 1], role: "c" }));
      return parts;
    }
    let finalFloor = floorLegBased;
    if (collidesWithWalls(buildLegObject(railsAt(Y)))) {
      let steps = 0, cleared = null;
      while (steps < 800) { Y += 1; steps++; if (!collidesWithWalls(buildLegObject(railsAt(Y)))) { cleared = Y; break; } }
      if (cleared === null) throw new Error(`step5 col${ci}: nenalezena bezkolizni pozice`);
      const withMargin = cleared + podbehClearanceMm;
      if (collidesWithWalls(buildLegObject(railsAt(withMargin)))) throw new Error(`step5 col${ci}: i po +${podbehClearanceMm} koliduje`);
      finalFloor = withMargin - T / 2;
    }
    step5[ci] = { finalFloorY: finalFloor };
  });
  log.push(`step5 OK: ${JSON.stringify(step5)}`);

  // ---- STEP 7: strop (cela hloubka D sonda) per sloupec ----
  const step7 = {};
  columns.forEach((col, ci) => {
    const legFrom = legs[col.legFromIdx], legTo = legs[col.legToIdx];
    const zFrom = legFrom.anchorZ + T, zTo = legTo.anchorZ;
    function slab(y) {
      const geo = new THREE.BoxGeometry(D, 10, zTo - zFrom);
      const mesh = new THREE.Mesh(geo);
      mesh.position.set(offsetX - D / 2, y, (zFrom + zTo) / 2);
      mesh.updateMatrixWorld(true);
      return mesh;
    }
    let y = step5[ci].finalFloorY + T / 2, steps = 0, collisionY = null;
    while (steps < 2800) { y += 1; steps++; if (collidesWithWalls(slab(y))) { collisionY = y; break; } }
    let safeY;
    if (collisionY === null) {
      // FALLBACK: nektere starsi GLB modely nemaji modelovanou strechu (jen boky+
      // podlaha+prepazka) - sonda nikdy nekoliduje. Pouzij REALNOU vysku bocni steny
      // (boxL0.max.y, jeji vlastni bounding box) jako fyzicky bezpecny strop misto
      // vyhozeni chyby - je to skutecna zmerenа geometrie vozidla, ne odhad.
      safeY = (boxL0.max.y - 20) - offsetY;
      log.push(`step7 col${ci} FALLBACK (zadna kolize do local y=${y} - karoserie nema modelovanou strechu): maxSafeBoxTop=${safeY.toFixed(1)} (= vrsek steny L bbox ${boxL0.max.y.toFixed(1)} - 20mm - offsetY)`);
    } else {
      safeY = collisionY - 2;
      if (collidesWithWalls(slab(safeY))) throw new Error(`step7 col${ci}: 2mm zpet stale koliduje`);
    }
    step7[ci] = { maxSafeBoxTop: safeY };
  });
  log.push(`step7 OK: ${JSON.stringify(step7)}`);

  // ---- vyska pater (nerostouci, co nejvic pater, diverzifikace napric sestavou) ----
  // KAZDA uroven se overuje REALNOU kolizi nosniku proti karoserii (ne jen
  // numerickym stropem) - stena/strecha se muze prohybat v ruznych vyskach.
  function railCollidesAt(legFrom, legTo, N, Y) {
    const railZFrom = legFrom.anchorZ + T, railZTo = legTo.anchorZ;
    const railZCenter = (railZFrom + railZTo) / 2, railLen = railZTo - railZFrom;
    const crossLen = D - 2 * T, crossXCenter = D / 2;
    const parts = [];
    parts.push({ part_id: "Object_7", position: [offsetX - T / 2, Y + offsetY, railZCenter], quaternion: Q_ALONG_Z, scale: [1, railLen / 1000, 1], role: "r" });
    parts.push({ part_id: "Object_7", position: [offsetX - (D - T / 2), Y + offsetY, railZCenter], quaternion: Q_ALONG_Z, scale: [1, railLen / 1000, 1], role: "r" });
    CONNECTOR_POS[N].forEach(lz => parts.push({ part_id: "Object_7", position: [offsetX - crossXCenter, Y + offsetY, railZFrom + lz], quaternion: Q_ALONG_X, scale: [1, crossLen / 1000, 1], role: "c" }));
    return collidesWithWalls(buildLegObject(parts));
  }
  function planColumn(col, floor, physCeil, preferDiversity) {
    const legFrom = legs[col.legFromIdx], legTo = legs[col.legToIdx];
    const RAIL_CENTER_MAX = (cfg.H - cfg.CAP_H) - T / 2;
    const railMax = cfg.family === "ford" ? cfg.H - T / 2 : RAIL_CENTER_MAX;
    const TOP_Y_LIMIT = cfg.family === "ford" ? cfg.H : (cfg.H - cfg.CAP_H);
    const candidates = [[270,220,170,120],[270,220,170],[270,220,120],[220,170,120],[270,170,120],[270,220],[220,170],[270,120],[120,120,120,120],[270],[220],[170],[120]];
    let best = null;
    for (const seq of candidates) {
      let railTop = floor + T; const levels = [];
      let bad = false;
      for (let i = 0; i < seq.length; i++) {
        const railYCenter = railTop - T / 2;
        if (railYCenter > railMax + 1e-6) { bad = true; break; }
        if (railCollidesAt(legFrom, legTo, col.N, railYCenter)) { bad = true; break; } // REALNA kolize nosniku
        const isTop = i === seq.length - 1;
        const boxTop = railTop + seq[i];
        const limit = isTop ? physCeil : TOP_Y_LIMIT;
        if (boxTop > limit + 1e-6) { bad = true; break; }
        levels.push({ railYCenter, boxH: seq[i], boxTop });
        railTop = railTop + seq[i] + 30 + T;
      }
      if (levels.length === 0) continue;
      const distinctCount = new Set(levels.map(l => l.boxH)).size;
      if (!best) { best = { seq, levels }; continue; }
      const bestDistinct = new Set(best.levels.map(l => l.boxH)).size;
      const better = preferDiversity
        ? (distinctCount > bestDistinct || (distinctCount === bestDistinct && levels.length > best.levels.length))
        : (levels.length > best.levels.length || (levels.length === best.levels.length && distinctCount > bestDistinct));
      if (better) best = { seq, levels };
    }
    return best;
  }
  function tryPlanAll(preferDiversity) {
    const plans = columns.map((col, ci) => planColumn(col, step5[ci].finalFloorY, step7[ci].maxSafeBoxTop, preferDiversity));
    if (plans.some(p => !p)) return null;
    return plans;
  }
  // pravidlo (shape_geometry_methods.id=3, vyklad_seznamu_povolenych_vysek): alespon
  // 3 ze 4 vysek NEKDE v cele sestave. Zkus nejdriv rezim "co nejvic pater", a pokud
  // to nedava dost diverzity, prepni na rezim "co nejvic ruznych vysek".
  let columnPlans = tryPlanAll(false);
  if (!columnPlans) { log.push("nektery sloupec nema zadnou validni vysku patra"); return { ok: false, reason: "no-level-plan", log, cfg }; }
  let allHeights = new Set(columnPlans.flatMap(p => p.levels.map(l => l.boxH)));
  if (allHeights.size < 3) {
    const alt = tryPlanAll(true);
    if (alt) {
      const altHeights = new Set(alt.flatMap(p => p.levels.map(l => l.boxH)));
      if (altHeights.size > allHeights.size) { columnPlans = alt; allHeights = altHeights; }
    }
  }
  log.push(`plan_levels: ${JSON.stringify(columnPlans.map(p => p.seq))} distinctHeights=${[...allHeights]}`);

  // ---- BUILD FULL: nohy+endcapy, patra (rail+conn+eurobox), verifikace ----
  let allParts = [];
  legs.forEach((leg, i) => {
    let localParts;
    if (leg.type === "plain") localParts = legPartsFor(cfg, "plain");
    else localParts = legPartsFor(cfg, "vyrez", { CUTOUT_H: vyrezYnew[i] });
    const roles = leg.type === "vyrez" ? ["predni-svislice", "zadni-svislice-nad-zarezem", "cap"] : (cfg.family === "ford" ? ["predni-svislice", "zadni-svislice"] : ["predni-svislice", "zadni-svislice-dolni", "cap"]);
    const endcaps = localParts.filter(p => roles.includes(p.role)).map(p => {
      const lenMm = p.scale[1] * 1000;
      const topY = p.position[1] + lenMm / 2 + CAP_FLANGE_THICKNESS;
      return { part_id: "product_3071", position: [p.position[0], topY, p.position[2]], quaternion: Q_ENDCAP_UP, scale: [1, 1, 1], role: "zaslepka-" + p.role };
    });
    allParts.push(...toWorld([...localParts, ...endcaps], offsetX, offsetY, leg.anchorZ));
  });

  const columnSummaries = [];
  columns.forEach((col, ci) => {
    const legFrom = legs[col.legFromIdx], legTo = legs[col.legToIdx];
    const railZFrom = legFrom.anchorZ + T, railZTo = legTo.anchorZ;
    const railLen = railZTo - railZFrom, railZCenter = (railZFrom + railZTo) / 2;
    const crossLen = D - 2 * T, crossXCenter = D / 2;
    const plan = columnPlans[ci];
    plan.levels.forEach((level, li) => {
      const Y = level.railYCenter;
      allParts.push({ part_id: "Object_7", position: [offsetX - T / 2, Y + offsetY, railZCenter], quaternion: Q_ALONG_Z, scale: [1, railLen / 1000, 1], role: `nosnik-col${ci}-p${li}` });
      allParts.push({ part_id: "Object_7", position: [offsetX - (D - T / 2), Y + offsetY, railZCenter], quaternion: Q_ALONG_Z, scale: [1, railLen / 1000, 1], role: `nosnik-col${ci}-p${li}` });
      CONNECTOR_POS[col.N].forEach(lz => allParts.push({ part_id: "Object_7", position: [offsetX - crossXCenter, Y + offsetY, railZFrom + lz], quaternion: Q_ALONG_X, scale: [1, crossLen / 1000, 1], role: `spojnice-col${ci}-p${li}` }));
      const positions = CONNECTOR_POS[col.N];
      for (let i = 0; i < positions.length - 1; i++) {
        allParts.push({ part_id: EUROBOX_PID[level.boxH], position: [0, 0, 0], quaternion: Q_ALONG_Z, scale: [1, 1, 1], role: `eurobox-col${ci}-p${li}`,
          _pending: { slotZFrom: railZFrom + positions[i], slotZTo: railZFrom + positions[i + 1], railYCenter: Y + offsetY, boxH: level.boxH } });
      }
    });
    columnSummaries.push({ ci, N: col.N, levels: plan.levels.length, heights: plan.levels.map(l => l.boxH), totalBoxes: col.N * plan.levels.length });
  });

  const probeCache = {};
  function probeFor(h) {
    if (probeCache[h]) return probeCache[h];
    const m = parseGlbMesh(EUROBOX_GLB[h]); m.position.set(0,0,0); m.quaternion.set(...Q_ALONG_Z); m.scale.set(1,1,1); m.updateMatrixWorld(true);
    const b = new THREE.Box3().setFromObject(m);
    return (probeCache[h] = { box: b, center: [(b.min.x+b.max.x)/2,(b.min.y+b.max.y)/2,(b.min.z+b.max.z)/2] });
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

  // verifikace: profily vs karoserie
  const profileParts = allParts.filter(p => p.part_id === "Object_7");
  if (collidesWithWalls(buildLegObject(profileParts))) {
    const bad = profileParts.filter(p => collidesWithWalls(buildLegObject([p])));
    return { ok: false, reason: "profile-collision", log, cfg, bad: bad.map(p => ({ role: p.role, position: p.position, scale: p.scale })) };
  }
  function glbFor(id) { if (id === "Object_7") return OBJ7; if (id === "product_3071") return ENDCAP; for (const h in EUROBOX_PID) if (EUROBOX_PID[h] === id) return EUROBOX_GLB[h]; return null; }
  function meshOf(p) { const m = parseGlbMesh(glbFor(p.part_id)); m.position.set(...p.position); m.quaternion.set(...p.quaternion); m.scale.set(...p.scale); m.updateMatrixWorld(true); return m; }
  const euroboxParts = allParts.filter(p => p.part_id.startsWith("product_37"));
  for (const p of euroboxParts) {
    const grp = new THREE.Group(); grp.add(meshOf(p)); grp.updateMatrixWorld(true);
    if (collidesWithWalls(grp)) return { ok: false, reason: "eurobox-collision:" + p.role, log, cfg };
  }
  // self-kolize (neocekavane presahy mimo nesting Object_7<->neco)
  const meshes = allParts.map(meshOf);
  let unexpected = 0;
  for (let i = 0; i < meshes.length; i++) for (let j = i + 1; j < meshes.length; j++) {
    const A = new THREE.Box3().setFromObject(meshes[i]), B = new THREE.Box3().setFromObject(meshes[j]);
    const ox = Math.min(A.max.x,B.max.x)-Math.max(A.min.x,B.min.x), oy = Math.min(A.max.y,B.max.y)-Math.max(A.min.y,B.min.y), oz = Math.min(A.max.z,B.max.z)-Math.max(A.min.z,B.min.z);
    if (ox > 0.5 && oy > 0.5 && oz > 0.5) {
      const nestOk = allParts[i].part_id !== "Object_7" || allParts[j].part_id !== "Object_7";
      if (!nestOk) unexpected++;
    }
  }
  if (unexpected > 0) return { ok: false, reason: `self-collision(${unexpected})`, log, cfg };

  const totalBoxes = columnSummaries.reduce((s,c)=>s+c.totalBoxes,0);
  const distinctHeights = new Set(columnSummaries.flatMap(c=>c.heights));
  log.push(`BUILD OK: totalBoxes=${totalBoxes} distinctHeights=${[...distinctHeights]} legs=${legs.length} columns=${columns.length}`);

  const clean = allParts.map(({_pending, ...rest}) => rest);
  return { ok: true, cfg, log, allParts: clean, legs, columns, columnSummaries, totalBoxes, distinctHeights: [...distinctHeights], offsetX, offsetY, D, T, H: cfg.H };
  } catch (e) {
    return { ok: false, reason: "exception:" + e.message, log, cfg };
  }
}

module.exports = { runVehicle };
