// bot24 2026-09-02. Oprava: VW21/VW22/VW31/VW32 (Caddy Cargo/Cargo Maxi (PHEV))
// zadni noha se driv zastavovala predcasne, protoze kolizni krokovani REAR_ANCHOR_Z
// (tmp_2026-09-01_bot16_run_pipeline.js step2) testovalo CELOU "vyrez" nohu s
// PEVNYM design CUTOUT_H (330mm) - jakmile podbeh kola prekrocil 330mm hloubky,
// spodni dil "sloupek-pred-podbehem" (ktery vzdy sahal az k podlaze, Y=[0,330])
// zkolidoval s podbehem a pipeline to vyhodnotila jako "konec vozidla", i kdyz
// podbeh ve skutecnosti pokracoval dal (Robert: "musí pokraCOVAT PRES PODBĚH
// DOZADU, i když podběh nekončí").
//
// Oprava = shape_geometry_methods.id=6 (protazeni-zadni-svislice-vyrezove-nohy)
// aplikovane ADAPTIVNE na KAZDOU kandidatni Z-pozici vyrez nohy behem hladoveho
// planovani sloupcu (ne jen jednou na konci): pro danou Z se vzdy cerstve
// spocita Y_new_wall (kam nejniz muze sahat "zadni-svislice-nad-zarezem", X
// blizko stene) A pripadne i vlastni protazeni "sloupek-pred-podbehem" (pokud by
// i ten kolidoval na svem [0,Y_new_wall] rozsahu - stejny princip aplikovany
// podruhe, tentokrat na sloupek misto zadni svislice). Nova pricka
// "pricka-uzavreni-vyrezu" (shape_geometry_methods.id=4) uzavira sev.
const THREE = require("three");
const fs = require("fs");
const { makeEnv, KAT } = require("/opt/konfigurator/scripts/2026-09-01_bot16_env_factory.js");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const { T, D, buildPlainWithCap } = require("/opt/konfigurator/scripts/2026-09-01_bot16_leg_builders.js");

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
const Q_ENDCAP_DOWN = [-0.7071067811865475, 0, 0, 0.7071067811865475];
const CAP_FLANGE_THICKNESS = 3;

const CADDY = { H: 1080, CAP_H: 240, capRight: 260, CUTOUT_H_design: 330, colRight_design: 270 };

function stepUntilCollision1D(testFn, dir, maxSteps, label) {
  let start = 0;
  if (testFn(start)) {
    let back = 0, cleared = false;
    for (let i = 0; i < maxSteps; i++) { back -= dir; if (!testFn(back)) { cleared = true; break; } }
    if (!cleared) throw new Error(`${label}: initial collides, cannot escape`);
    start = back;
  }
  let steps = 0, collided = false, val = start;
  while (steps < maxSteps) { val += dir; steps++; if (testFn(val)) { collided = true; break; } }
  if (!collided) throw new Error(`${label}: no collision after ${maxSteps} steps`);
  const backoffVal = val - dir * 2;
  if (testFn(backoffVal)) throw new Error(`${label}: still colliding 2mm back`);
  return backoffVal;
}

function part(xCenter, yCenter, lengthY, vertical, zCenter, role) {
  return { position: [xCenter, yCenter, zCenter], quaternion: vertical ? [0, 0, 0, 1] : [0, 0, -0.707107, 0.707107], scale: [1, lengthY / 1000, 1], role };
}

function runVehicle(cfg) {
  const log = [];
  const env = makeEnv(cfg.bodyPrefix);
  const { collidesWithWalls, buildLegObject, boxL0 } = env;
  const H = CADDY.H, CAP_H = CADDY.CAP_H, capRight = CADDY.capRight, colRight = CADDY.colRight_design;
  const TOP_Y = H - CAP_H;
  const colLeft = colRight - T;

  function toWorld(localParts, offsetX, offsetY, anchorZ) {
    return localParts.map(p => ({ part_id: p.part_id || "Object_7", position: [offsetX - p.position[0], p.position[1] + offsetY, anchorZ + p.position[2]], quaternion: p.quaternion, scale: p.scale, role: p.role }));
  }
  function groupAt(localParts, offsetX, offsetY, anchorZ) { return buildLegObject(toWorld(localParts, offsetX, offsetY, anchorZ)); }

  // STEP1 (unchanged, front plain leg: floor -> partition B -> wall L)
  const plainParts0 = buildPlainWithCap({ H, CAP_H, capRight });
  let offsetX = -D / 2;
  let offsetY = ((boxL0.min.y + boxL0.max.y) / 2) - H / 2;
  let anchorZ = ((boxL0.min.z + boxL0.max.z) / 2) - T / 2;
  offsetY += stepUntilCollision1D(v => collidesWithWalls(groupAt(plainParts0, offsetX, offsetY + v, anchorZ)), -1, 3000, "floor");
  anchorZ += stepUntilCollision1D(v => collidesWithWalls(groupAt(plainParts0, offsetX, offsetY, anchorZ + v)), -1, 5000, "partitionB");
  offsetX += stepUntilCollision1D(v => collidesWithWalls(groupAt(plainParts0, offsetX + v, offsetY, anchorZ)), -1, 3000, "wallL");
  const frontAnchorZ = anchorZ;
  log.push(`step1: offsetX=${offsetX.toFixed(2)} offsetY=${offsetY.toFixed(2)} frontAnchorZ=${frontAnchorZ.toFixed(2)}`);

  // ---- helpers: fresh (per-Z) vyrez adaptation, method id=6 applied to BOTH
  // "zadni-svislice-nad-zarezem" (wall-side) and, if needed, "sloupek-pred-podbehem".
  function wallPieceAt(z, bottomY) {
    const lenY = TOP_Y - bottomY, centerY = (bottomY + TOP_Y) / 2;
    return buildLegObject([{ position: [offsetX - (D - T / 2), centerY + offsetY, z + T / 2], quaternion: [0, 0, 0, 1], scale: [1, lenY / 1000, 1] }]);
  }
  // cheap existence probe: thin near-ceiling band on the wall-side X position -
  // a true rear structural wall blocks it, the wheel-arch floor bump does not
  // (it never rises anywhere near TOP_Y). Used only to search cheaply for the
  // true rear boundary; the real Y_new_wall is always computed via the full
  // 0..TOP_Y scan (adaptVyrezAt) at whatever Z is finally chosen.
  function wallBandProbe(z) {
    const yLen = 40, yCenter = TOP_Y - yLen / 2;
    return buildLegObject([{ position: [offsetX - (D - T / 2), yCenter + offsetY, z + T / 2], quaternion: [0, 0, 0, 1], scale: [1, yLen / 1000, 1] }]);
  }
  // cheap existence check used ONLY for the 1mm stepping search: near-ceiling
  // wall-side band (floor/wheel-arch true-wall detector) OR the fixed "cap"
  // piece (H-CAP_H..H at capRight) - found empirically (VW22/VW32) that the
  // ROOF/D-pillar area can start colliding independently of the floor arch,
  // well before the wall-side band would; both must stay clear.
  function capPieceAt(z) {
    return buildLegObject([{ position: [offsetX - (capRight - T / 2), (H - CAP_H / 2) + offsetY, z + T / 2], quaternion: [0, 0, 0, 1], scale: [1, CAP_H / 1000, 1] }]);
  }
  function predniPieceAt(z) {
    return buildLegObject([{ position: [offsetX - T / 2, H / 2 + offsetY, z + T / 2], quaternion: [0, 0, 0, 1], scale: [1, H / 1000, 1] }]);
  }
  function existenceProbeCollides(z) { return collidesWithWalls(wallBandProbe(z)) || collidesWithWalls(capPieceAt(z)) || collidesWithWalls(predniPieceAt(z)); }
  function sloupekPieceAt(z, bottomY, topY) {
    const lenY = topY - bottomY, centerY = (bottomY + topY) / 2;
    return buildLegObject([{ position: [offsetX - (colLeft + T / 2), centerY + offsetY, z + T / 2], quaternion: [0, 0, 0, 1], scale: [1, lenY / 1000, 1] }]);
  }
  // returns null if no valid adaptation exists at this Z (true rear wall reached)
  function adaptVyrezAt(z) {
    let collisionBottomY = null;
    for (let bY = TOP_Y - 1; bY >= 0; bY--) { if (collidesWithWalls(wallPieceAt(z, bY))) { collisionBottomY = bY; break; } }
    const Y_NEW_WALL = collisionBottomY === null ? 0 : collisionBottomY + 20;
    if (Y_NEW_WALL >= TOP_Y - 5) return null; // essentially no usable wall-side member left -> true rear boundary
    if (collidesWithWalls(wallPieceAt(z, Y_NEW_WALL))) return null;
    let sloupekBottom = 0;
    if (Y_NEW_WALL > 0 && collidesWithWalls(sloupekPieceAt(z, 0, Y_NEW_WALL))) {
      let cB = null;
      for (let bY = Y_NEW_WALL - 1; bY >= 0; bY--) { if (collidesWithWalls(sloupekPieceAt(z, bY, Y_NEW_WALL))) { cB = bY; break; } }
      sloupekBottom = cB === null ? 0 : cB + 20;
      if (sloupekBottom >= Y_NEW_WALL - 5) return null; // sloupek degenerates to nothing usable -> treat whole column as infeasible here
      if (collidesWithWalls(sloupekPieceAt(z, sloupekBottom, Y_NEW_WALL))) return null;
    }
    return { Y_NEW_WALL, sloupekBottom };
  }
  function buildVyrezPartsAdaptive(adapt) {
    const { Y_NEW_WALL, sloupekBottom } = adapt;
    const zL = D - T, pR = T;
    const parts = [
      part(T / 2, H / 2, H, true, T / 2, "predni-svislice"),
      part((pR + zL) / 2, (H - CAP_H) - T / 2, zL - pR, false, T / 2, "spojnice-horni-uzavreni"),
      part(capRight - T / 2, H - CAP_H / 2, CAP_H, true, T / 2, "cap"),
      part(D - T / 2, Y_NEW_WALL + (TOP_Y - Y_NEW_WALL) / 2, TOP_Y - Y_NEW_WALL, true, T / 2, "zadni-svislice-nad-zarezem"),
      part((pR + zL) / 2, Y_NEW_WALL + T / 2, zL - pR, false, T / 2, "pricka-uzavreni-vyrezu"),
    ];
    if (Y_NEW_WALL - sloupekBottom > 1) {
      parts.push(part(colLeft + T / 2, sloupekBottom + (Y_NEW_WALL - sloupekBottom) / 2, Y_NEW_WALL - sloupekBottom, true, T / 2, "sloupek-pred-podbehem"));
      parts.push(part((pR + colLeft) / 2, sloupekBottom + T / 2, colLeft - pR, false, T / 2, "spojnice-dolni"));
    }
    return parts;
  }

  function legPartsFor(type, z) {
    if (type === "plain") return { parts: buildPlainWithCap({ H, CAP_H, capRight }), adapt: null };
    const adapt = adaptVyrezAt(z);
    if (!adapt) return null;
    return { parts: buildVyrezPartsAdaptive(adapt), adapt };
  }

  // ---- STEP3: greedy multi-column fill, generous outer bound (real physical
  // end of modelled geometry + margin) - the ADAPTIVE vyrez test itself is now
  // the arbiter of "does this candidate fit", not a separately pre-computed cap.
  const searchCapZ = boxL0.max.z + 300;
  const legs = [{ type: "plain", anchorZ: frontAnchorZ, adapt: null }];
  const columns = [];
  function partsToWorldFor(leg) {
    const r = legPartsFor(leg.type, leg.anchorZ);
    return toWorld(r.parts, offsetX, offsetY, leg.anchorZ);
  }
  function railsForColumn(N, legFrom, legTo) {
    const railZFrom = legFrom.anchorZ + T, railZTo = legTo.anchorZ;
    const railLen = railZTo - railZFrom, railZCenter = (railZFrom + railZTo) / 2;
    // Probe height for the "can a column exist here at all" candidate test:
    // near-ceiling (TOP_Y-50), NOT a fixed low height - a fixed low probe
    // (e.g. 400mm) falsely collides with the (possibly much higher) wheel-arch
    // floor along a long rail span, exactly the bug this fix addresses. The
    // REAL per-level rail height is determined later (step5/patra planning).
    const crossLen = D - 2 * T, crossXCenter = D / 2, Y = offsetY + TOP_Y - 50;
    const parts = [];
    parts.push({ position: [offsetX - T / 2, Y, railZCenter], quaternion: Q_ALONG_Z, scale: [1, railLen / 1000, 1] });
    parts.push({ position: [offsetX - (D - T / 2), Y, railZCenter], quaternion: Q_ALONG_Z, scale: [1, railLen / 1000, 1] });
    CONNECTOR_POS[N].forEach(lz => parts.push({ position: [offsetX - crossXCenter, Y, railZFrom + lz], quaternion: Q_ALONG_X, scale: [1, crossLen / 1000, 1] }));
    return parts;
  }
  function wholeAssemblyParts(extraLeg, extraRailParts) {
    let parts = [];
    legs.forEach(l => parts.push(...partsToWorldFor(l)));
    columns.forEach(c => parts.push(...railsForColumn(c.N, legs[c.legFromIdx], legs[c.legToIdx])));
    if (extraLeg) parts.push(...partsToWorldFor(extraLeg));
    if (extraRailParts) parts.push(...extraRailParts);
    return parts;
  }
  // Two-phase fill: (A) PLAIN legs only, widest column first - efficient use of
  // the flat floor, matches existing convention elsewhere in the codebase.
  // (B) once plain no longer fits (floor starts rising - wheel arch begins),
  // switch to ADAPTIVE "vyrez" legs, but try the NARROWEST column first (N=1)
  // instead of widest-first: a wide (1232mm) jump greedily consumes the ENTIRE
  // remaining arch depth in one bound (as first observed - it skips straight to
  // the rear wall and leaves only 1 usable box level), which wastes the newly
  // gained length instead of using it (Robert's ask: "využij nově získanou
  // délku"). Narrowest-first lets more, shorter arch-side columns subdivide the
  // space, each with its own (higher) floor closer to what's actually needed
  // at that Z, giving more total boxes and more distinct heights.
  function tryPhase(typeList, widthOrder) {
    let placedAny = false;
    let colIdx = 0;
    while (colIdx < 20) {
      const lastLeg = legs[legs.length - 1];
      let placed = false;
      outer:
      for (const N of widthOrder) {
        const newAnchorZ = lastLeg.anchorZ + T + CLEAR_SPACING[N];
        if (newAnchorZ > searchCapZ) continue;
        for (const type of typeList) {
          const built = legPartsFor(type, newAnchorZ);
          if (!built) { if (process.env.DEBUG_BOT24) log.push(`  cand N=${N} type=${type} z=${newAnchorZ.toFixed(1)}: no-adapt`); continue; }
          const candidateLeg = { type, anchorZ: newAnchorZ, adapt: built.adapt };
          const railParts = railsForColumn(N, lastLeg, candidateLeg);
          const candWorld = toWorld(built.parts, offsetX, offsetY, newAnchorZ);
          const assembly = buildLegObject([...wholeAssemblyParts(null, railParts), ...candWorld]);
          const coll = collidesWithWalls(assembly);
          if (process.env.DEBUG_BOT24) log.push(`  cand N=${N} type=${type} z=${newAnchorZ.toFixed(1)}: collide=${coll} adapt=${JSON.stringify(built.adapt)}`);
          if (!coll) {
            legs.push(candidateLeg);
            columns.push({ N, legFromIdx: legs.length - 2, legToIdx: legs.length - 1 });
            placed = true; placedAny = true; break outer;
          }
        }
      }
      if (!placed) break;
      colIdx++;
    }
    return placedAny;
  }
  tryPhase(["plain"], WIDTH_TRY_ORDER);
  log.push(`phaseA (plain): legs=${legs.length} columns=${JSON.stringify(columns.map(c => c.N))} lastAnchorZ=${legs[legs.length - 1].anchorZ.toFixed(2)}`);
  tryPhase(["vyrez"], [1, 2, 3]);
  log.push(`phaseB (vyrez): legs=${legs.length} columns=${JSON.stringify(columns.map(c => c.N))} lastAnchorZ=${legs[legs.length - 1].anchorZ.toFixed(2)}`);
  log.push(`step3: legs=${legs.length} columns=${JSON.stringify(columns.map(c => c.N))} lastAnchorZ=${legs[legs.length - 1].anchorZ.toFixed(2)}`);
  if (columns.length === 0) return { ok: false, reason: "no-columns", log, cfg };

  // ---- STEP3b: extend the LAST column's rear leg to the true rear collision
  // boundary (car_body_placement_methods.id=1 "max_rozpon_nohou": step 1mm at a
  // time until collision, then back 20mm) - discrete CLEAR_SPACING widths
  // (430/832/1232mm) used by the greedy fill above rarely land exactly on the
  // true structural limit, so this recovers whatever length remains unused.
  {
    const lastCol = columns[columns.length - 1];
    const legFromIdx = lastCol.legFromIdx, legToIdx = lastCol.legToIdx;
    const legFrom = legs[legFromIdx];
    const N = lastCol.N;
    // Cheap search first (single near-ceiling-band collision test per 1mm step,
    // same probe used for the true-rear-boundary search above) - avoids calling
    // the expensive full 0..TOP_Y adaptVyrezAt scan on every one of up to ~2000
    // 1mm steps. Only the FINAL candidate position gets the full adaptation.
    let z = legs[legToIdx].anchorZ;
    let steps = 0;
    while (steps < 2000) {
      const zTry = z + 1;
      if (zTry > searchCapZ) break; // never step past the modelled vehicle geometry
      if (existenceProbeCollides(zTry)) break;
      z = zTry; steps++;
    }
    log.push(`step3b: cheap search stopped at z=${z.toFixed(2)} steps=${steps}`);
    if (steps > 0) {
      const zBack = z - 20;
      const built = legPartsFor("vyrez", zBack);
      log.push(`step3b: zBack=${zBack.toFixed(2)} built=${!!built}`);
      if (built) {
        const fullAssemblyColl = (() => {
          const candidateLeg2 = { type: "vyrez", anchorZ: zBack, adapt: built.adapt };
          const railParts2 = railsForColumn(N, legFrom, candidateLeg2);
          const candWorld2 = toWorld(built.parts, offsetX, offsetY, zBack);
          const priorParts2 = [];
          legs.forEach((l, i) => { if (i !== legToIdx) priorParts2.push(...partsToWorldFor(l)); });
          columns.forEach((c, ci) => { if (ci !== columns.length - 1) priorParts2.push(...railsForColumn(c.N, legs[c.legFromIdx], legs[c.legToIdx])); });
          return collidesWithWalls(buildLegObject([...priorParts2, ...railParts2, ...candWorld2]));
        })();
        log.push(`step3b: fullAssemblyCollides=${fullAssemblyColl} adapt=${JSON.stringify(built.adapt)}`);
      }
      if (built) {
        const candidateLeg = { type: "vyrez", anchorZ: zBack, adapt: built.adapt };
        const railParts = railsForColumn(N, legFrom, candidateLeg);
        const candWorld = toWorld(built.parts, offsetX, offsetY, zBack);
        const priorParts = [];
        legs.forEach((l, i) => { if (i !== legToIdx) priorParts.push(...partsToWorldFor(l)); });
        columns.forEach((c, ci) => { if (ci !== columns.length - 1) priorParts.push(...railsForColumn(c.N, legs[c.legFromIdx], legs[c.legToIdx])); });
        const assembly = buildLegObject([...priorParts, ...railParts, ...candWorld]);
        if (!collidesWithWalls(assembly)) {
          legs[legToIdx] = candidateLeg;
          log.push(`step3b: extended last leg to ${zBack.toFixed(2)}`);
        }
      }
    }
  }
  log.push(`step3b result: lastAnchorZ=${legs[legs.length - 1].anchorZ.toFixed(2)}`);

  // ---- STEP5: rail floor fresh per column (leg-based + full-span check)
  function legFloorOf(leg) { return leg.type === "plain" ? 0 : leg.adapt.sloupekBottom < 1 ? leg.adapt.Y_NEW_WALL === 0 ? 0 : Math.min(leg.adapt.sloupekBottom, leg.adapt.Y_NEW_WALL) : leg.adapt.sloupekBottom; }
  // simpler & correct: leg floor = lowest Y at which a full-depth rail/box could rest without hitting this leg's own missing-material gap = max needed clearance = Y at which BOTH sloupek (if present) and predni already stand = sloupekBottom (0 if plain or sloupek reaches floor)
  function legFloorOf2(leg) { if (leg.type === "plain") return 0; return leg.adapt.sloupekBottom; }
  const step5 = {};
  columns.forEach((col, ci) => {
    const legFrom = legs[col.legFromIdx], legTo = legs[col.legToIdx];
    const floorLegBased = Math.max(legFloorOf2(legFrom), legFloorOf2(legTo));
    let Y = floorLegBased + T / 2;
    function railsAt(Yc) {
      const railZFrom = legFrom.anchorZ + T, railZTo = legTo.anchorZ;
      const railLen = railZTo - railZFrom, railZCenter = (railZFrom + railZTo) / 2;
      const crossLen = D - 2 * T, crossXCenter = D / 2;
      const parts = [];
      parts.push({ position: [offsetX - T / 2, Yc + offsetY, railZCenter], quaternion: Q_ALONG_Z, scale: [1, railLen / 1000, 1] });
      parts.push({ position: [offsetX - (D - T / 2), Yc + offsetY, railZCenter], quaternion: Q_ALONG_Z, scale: [1, railLen / 1000, 1] });
      CONNECTOR_POS[col.N].forEach(lz => parts.push({ position: [offsetX - crossXCenter, Yc + offsetY, railZFrom + lz], quaternion: Q_ALONG_X, scale: [1, crossLen / 1000, 1] }));
      return parts;
    }
    let finalFloor = floorLegBased;
    if (collidesWithWalls(buildLegObject(railsAt(Y)))) {
      let steps = 0, cleared = null;
      while (steps < 1200) { Y += 1; steps++; if (!collidesWithWalls(buildLegObject(railsAt(Y)))) { cleared = Y; break; } }
      if (cleared === null) throw new Error(`step5 col${ci}: no clear position found`);
      const withMargin = cleared + 20;
      if (collidesWithWalls(buildLegObject(railsAt(withMargin)))) throw new Error(`step5 col${ci}: still colliding after +20`);
      finalFloor = withMargin - T / 2;
    }
    step5[ci] = { finalFloorY: finalFloor };
  });
  log.push(`step5: ${JSON.stringify(step5)}`);

  // ---- STEP7: ceiling per column (full-depth slab sonda)
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
    if (collisionY === null) { safeY = (boxL0.max.y - 20) - offsetY; }
    else { safeY = collisionY - 2; if (collidesWithWalls(slab(safeY))) throw new Error(`step7 col${ci}: still colliding`); }
    step7[ci] = { maxSafeBoxTop: safeY };
  });
  log.push(`step7: ${JSON.stringify(step7)}`);

  // ---- patra planning (unchanged logic from run_pipeline.js)
  function railCollidesAt(legFrom, legTo, N, Y) {
    const railZFrom = legFrom.anchorZ + T, railZTo = legTo.anchorZ;
    const railZCenter = (railZFrom + railZTo) / 2, railLen = railZTo - railZFrom;
    const crossLen = D - 2 * T, crossXCenter = D / 2;
    const parts = [];
    parts.push({ position: [offsetX - T / 2, Y + offsetY, railZCenter], quaternion: Q_ALONG_Z, scale: [1, railLen / 1000, 1] });
    parts.push({ position: [offsetX - (D - T / 2), Y + offsetY, railZCenter], quaternion: Q_ALONG_Z, scale: [1, railLen / 1000, 1] });
    CONNECTOR_POS[N].forEach(lz => parts.push({ position: [offsetX - crossXCenter, Y + offsetY, railZFrom + lz], quaternion: Q_ALONG_X, scale: [1, crossLen / 1000, 1] }));
    return collidesWithWalls(buildLegObject(parts));
  }
  function planColumn(col, floor, physCeil, preferDiversity) {
    const legFrom = legs[col.legFromIdx], legTo = legs[col.legToIdx];
    const railMax = TOP_Y - T / 2;
    const TOP_Y_LIMIT = TOP_Y;
    const candidates = [[270,220,170,120],[270,220,170],[270,220,120],[220,170,120],[270,170,120],[270,220],[220,170],[270,120],[120,120,120,120],[270],[220],[170],[120]];
    let best = null;
    for (const seq of candidates) {
      let railTop = floor + T; const levels = [];
      let bad = false;
      for (let i = 0; i < seq.length; i++) {
        const railYCenter = railTop - T / 2;
        if (railYCenter > railMax + 1e-6) { bad = true; break; }
        if (railCollidesAt(legFrom, legTo, col.N, railYCenter)) { bad = true; break; }
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
      const better = preferDiversity ? (distinctCount > bestDistinct || (distinctCount === bestDistinct && levels.length > best.levels.length)) : (levels.length > best.levels.length || (levels.length === best.levels.length && distinctCount > bestDistinct));
      if (better) best = { seq, levels };
    }
    return best;
  }
  function tryPlanAll(preferDiversity) {
    const plans = columns.map((col, ci) => planColumn(col, step5[ci].finalFloorY, step7[ci].maxSafeBoxTop, preferDiversity));
    if (plans.some(p => !p)) return null;
    return plans;
  }
  let columnPlans = tryPlanAll(false);
  if (!columnPlans) return { ok: false, reason: "no-level-plan", log, cfg };
  let allHeights = new Set(columnPlans.flatMap(p => p.levels.map(l => l.boxH)));
  if (allHeights.size < 3) {
    const alt = tryPlanAll(true);
    if (alt) { const altHeights = new Set(alt.flatMap(p => p.levels.map(l => l.boxH))); if (altHeights.size > allHeights.size) { columnPlans = alt; allHeights = altHeights; } }
  }
  log.push(`plan_levels: ${JSON.stringify(columnPlans.map(p => p.seq))} distinctHeights=${[...allHeights]}`);

  // ---- BUILD FULL: nohy + zaslepky (vc. noveho spodniho zaslepky pro zvednuty sloupek) + patra
  let allParts = [];
  legs.forEach((leg, i) => {
    const built = legPartsFor(leg.type, leg.anchorZ);
    const localParts = built.parts;
    const topRoles = leg.type === "vyrez" ? ["predni-svislice", "zadni-svislice-nad-zarezem", "cap"] : ["predni-svislice", "zadni-svislice-dolni", "cap"];
    const endcaps = [];
    localParts.filter(p => topRoles.includes(p.role)).forEach(p => {
      const lenMm = p.scale[1] * 1000;
      const topY = p.position[1] + lenMm / 2 + CAP_FLANGE_THICKNESS;
      endcaps.push({ part_id: "product_3071", position: [p.position[0], topY, p.position[2]], quaternion: Q_ENDCAP_UP, scale: [1, 1, 1], role: "zaslepka-" + p.role });
    });
    if (leg.type === "vyrez" && leg.adapt.sloupekBottom > 1) {
      const sloupek = localParts.find(p => p.role === "sloupek-pred-podbehem");
      if (sloupek) {
        const lenMm = sloupek.scale[1] * 1000;
        const bottomY = sloupek.position[1] - lenMm / 2 - CAP_FLANGE_THICKNESS;
        endcaps.push({ part_id: "product_3071", position: [sloupek.position[0], bottomY, sloupek.position[2]], quaternion: Q_ENDCAP_DOWN, scale: [1, 1, 1], role: "zaslepka-sloupek-pred-podbehem-dolni" });
      }
    }
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
        allParts.push({ part_id: EUROBOX_PID[level.boxH], position: [0, 0, 0], quaternion: Q_ALONG_Z, scale: [1, 1, 1], role: `eurobox-col${ci}-p${li}`, _pending: { slotZFrom: railZFrom + positions[i], slotZTo: railZFrom + positions[i + 1], railYCenter: Y + offsetY, boxH: level.boxH } });
      }
    });
    columnSummaries.push({ ci, N: col.N, legFromZ: legFrom.anchorZ, legToZ: legTo.anchorZ, levels: plan.levels.length, heights: plan.levels.map(l => l.boxH), totalBoxes: col.N * plan.levels.length });
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

  // verification: profiles vs body
  const profileParts = allParts.filter(p => p.part_id === "Object_7");
  if (collidesWithWalls(buildLegObject(profileParts))) {
    const bad = profileParts.filter(p => collidesWithWalls(buildLegObject([p])));
    return { ok: false, reason: "profile-collision", log, cfg, bad: bad.map(p => ({ role: p.role, position: p.position, scale: p.scale })) };
  }
  function glbFor(id) { if (id === "Object_7") return OBJ7; if (id === "product_3071") return ENDCAP; for (const h in EUROBOX_PID) if (EUROBOX_PID[h] === id) return EUROBOX_GLB[h]; return null; }
  function meshOf(p) { const m = parseGlbMesh(glbFor(p.part_id)); m.position.set(...p.position); m.quaternion.set(...p.quaternion); m.scale.set(...p.scale); m.updateMatrixWorld(true); return m; }
  const euroboxParts = allParts.filter(p => p.part_id.startsWith("product_37"));
  for (const p of euroboxParts) { const grp = new THREE.Group(); grp.add(meshOf(p)); grp.updateMatrixWorld(true); if (collidesWithWalls(grp)) return { ok: false, reason: "eurobox-collision:" + p.role, log, cfg }; }
  const endcapParts = allParts.filter(p => p.part_id === "product_3071");
  for (const p of endcapParts) { const grp = new THREE.Group(); grp.add(meshOf(p)); grp.updateMatrixWorld(true); if (collidesWithWalls(grp)) return { ok: false, reason: "endcap-collision:" + p.role, log, cfg }; }
  const meshes = allParts.map(meshOf);
  let unexpected = 0, unexpectedDetail = [];
  for (let i = 0; i < meshes.length; i++) for (let j = i + 1; j < meshes.length; j++) {
    const A = new THREE.Box3().setFromObject(meshes[i]), B = new THREE.Box3().setFromObject(meshes[j]);
    const ox = Math.min(A.max.x,B.max.x)-Math.max(A.min.x,B.min.x), oy = Math.min(A.max.y,B.max.y)-Math.max(A.min.y,B.min.y), oz = Math.min(A.max.z,B.max.z)-Math.max(A.min.z,B.min.z);
    if (ox > 0.5 && oy > 0.5 && oz > 0.5) {
      const nestOk = (allParts[i].part_id !== "Object_7" || allParts[j].part_id !== "Object_7");
      if (!nestOk) { unexpected++; unexpectedDetail.push([allParts[i].role, allParts[j].role]); }
    }
  }
  if (unexpected > 0) return { ok: false, reason: `self-collision(${unexpected})`, log, cfg, unexpectedDetail };

  const totalBoxes = columnSummaries.reduce((s,c)=>s+c.totalBoxes,0);
  const distinctHeights = new Set(columnSummaries.flatMap(c=>c.heights));
  log.push(`BUILD OK: totalBoxes=${totalBoxes} distinctHeights=${[...distinctHeights]} legs=${legs.length} columns=${columns.length}`);

  const clean = allParts.map(({_pending, ...rest}) => rest);
  return { ok: true, cfg, log, allParts: clean, legs: legs.map(l=>({type:l.type, anchorZ:l.anchorZ, adapt:l.adapt})), columns, columnSummaries, totalBoxes, distinctHeights: [...distinctHeights], offsetX, offsetY, D, T, H };
}

module.exports = { runVehicle, CADDY };

if (require.main === module) {
  const which = process.argv[2];
  const CONFIGS = {
    VW21: { bodyPrefix: "Volkswagen_Caddy_VW21_2021-" },
    VW22: { bodyPrefix: "Volkswagen_Caddy_VW22_2021-" },
    VW31: { bodyPrefix: "Volkswagen_Caddy_VW31_2021-" },
    VW32: { bodyPrefix: "Volkswagen_Caddy_VW32_2021-" },
  };
  const res = runVehicle(CONFIGS[which]);
  console.log(res.log.join("\n"));
  console.log("ok:", res.ok, "reason:", res.reason);
  if (res.ok) {
    console.log("columnSummaries:", JSON.stringify(res.columnSummaries, null, 1));
    console.log("legs:", JSON.stringify(res.legs, null, 1));
    fs.writeFileSync(`/tmp/claude-0/-opt-domeny/40752a20-c083-499a-8fe3-7c39a4eef60b/scratchpad/bot24_${which}_result.json`, JSON.stringify(res, null, 1));
  } else {
    console.log(JSON.stringify(res, null, 1));
  }
}
