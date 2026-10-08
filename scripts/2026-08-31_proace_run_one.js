// Genericky pipeline pro JEDNU ProAce karoserii - port kroku 1-7 z Vivaro
// pilotu (tmp_2026-08-31_vivaro_step1..step7 + build_full), parametrizovano
// D/H/T/CUTOUT_H per vehicle misto natvrdo Vivaro cisel. Pouziti:
//   node 2026-08-31_proace_run_one.js <config.json> <output.json>
const fs = require("fs");
const THREE = require("three");
const { loadVehicle } = require("/opt/konfigurator/scripts/2026-08-31_proace_walls.js");
const LEG = require("/opt/konfigurator/scripts/2026-08-31_proace_leg_builder.js");

const SPANS = { 1: 430, 2: 832, 3: 1232 };
const CONNECTOR_POS = { 1: [15, 415], 2: [15, 415, 816], 3: [15, 415, 816, 1217] };
const Q_ALONG_Z = [-0.707107, 0, 0, 0.707107];
const Q_ALONG_X = [0, 0, -0.707107, 0.707107];
const CAP_FLANGE_THICKNESS = 3;

function runOne(cfg) {
  const { base, D, H, T, CUTOUT_H, CAP_H } = cfg;
  const V = loadVehicle(base);
  if (!V.mirror) throw new Error(`${cfg.name}: ocekavany mirror=true (L na zaporne X), ale zmereno mirror=false - konvence se lisi, potreba rucni kontrola`);

  const opts = { T, CAP_H };
  const TOP_Y = H - CAP_H;

  // Bezpecnostni envelope (nalez CI24/CI25 pilotu, bot16 2026-08-31):
  // MIMO modelovany rozsah steny L v ose Z vraci collidesWithWalls VZDY
  // "nekoliduje" (edge-raycasting nema do ceho narazit) - FALESNE BEZPECNE.
  // Bez tohohle vsechny kolizni kroky (1,2,3,4,5,7) mohou utect do
  // nesmyslnych souradnic. Rezerva 5mm od skutecnych okraju steny L.
  const VALID_Z_MIN = V.boxL0.min.z + 5, VALID_Z_MAX = V.boxL0.max.z - 5;
  function zWithinEnvelope(zLo, zHi) { return zLo >= VALID_Z_MIN && zHi <= VALID_Z_MAX; }

  function toWorld(localParts, offsetX, offsetY, anchorZ) {
    return localParts.map(p => ({
      part_id: p.part_id || "Object_7",
      position: [offsetX - p.position[0], p.position[1] + offsetY, anchorZ + p.position[2]],
      quaternion: p.quaternion, scale: p.scale, role: p.role,
    }));
  }
  function groupAt(localParts, offsetX, offsetY, anchorZ) { return V.buildLegObject(toWorld(localParts, offsetX, offsetY, anchorZ)); }

  // ---- STEP 1: leg0 (plain) placement - podlaha -> prepazka B -> stena L ----
  const plainLocal = LEG.buildPlainAtDepth(D, H, opts);
  // pocatecni hruby odhad: stred sirky karoserie mezi L a R_D, kousek pred
  // koncem prepazky B (jeji lic je min Z, protoze B je na velke zaporne Z).
  let offsetX = -D / 2; // stred karoserie ~ X=0 (overeno na vsech 19 - L/R_D symetricke kolem X=0)
  let offsetY = V.boxL0.min.y + 20; // par mm nad podlahou, doladi floor krok
  // start bezpecne UVNITR cargo prostoru: zivě overeno na TO07, ze L.min.z
  // (-1915) NENI lic prepazky (leg tam uz koliduje s B/podlahovym schodem
  // pred prepazkou - L mesh zjevne pokracuje az do kabiny/podbehu za
  // skutecnou prepazkou) - realny zacatek cargo prostoru je az u B.max.z
  // (rubova/cargo strana prepazky, blize otevrenemu konci). Start 150mm za
  // touhle hranicí smerem do cargo prostoru, pak kroky najdou skutecnou
  // kolizi s prepazkou.
  let anchorZ = V.boxB0.max.z + 150 - T / 2;

  function stepUntilCollision1D(testFn, dir, maxSteps, label) {
    let steps = 0, collided = false, val = 0;
    while (steps < maxSteps) {
      val += dir; steps++;
      if (testFn(val)) { collided = true; break; }
    }
    if (!collided) throw new Error(`${label}: zadna kolize po ${maxSteps} krocich`);
    const backoffVal = val - dir * 2;
    if (testFn(backoffVal)) throw new Error(`${label}: po 2mm zpet stale koliduje`);
    return backoffVal;
  }

  const dY = stepUntilCollision1D(v => V.collidesWithWalls(groupAt(plainLocal, offsetX, offsetY + v, anchorZ)), -1, 3000, "podlaha");
  offsetY += dY;
  const dZ = stepUntilCollision1D(v => V.collidesWithWalls(groupAt(plainLocal, offsetX, offsetY, anchorZ + v)), -1, 4000, "prepazka B");
  anchorZ += dZ;
  const dX = stepUntilCollision1D(v => V.collidesWithWalls(groupAt(plainLocal, offsetX + v, offsetY, anchorZ)), -1, 3000, "stena L");
  offsetX += dX;

  if (V.collidesWithWalls(groupAt(plainLocal, offsetX, offsetY, anchorZ))) throw new Error("leg0 finalni pozice koliduje - neocekavane");

  // ---- STEP 2: rear boundary (max span) pomoci vyrez sondy ----
  const vyrezLocalDefault = LEG.buildVyrezAtDepth(D, H, CUTOUT_H, opts);
  function vyrezGroupAt(aZ) { return groupAt(vyrezLocalDefault, offsetX, offsetY, aZ); }
  let z = anchorZ, steps2 = 0, collisionZ = null;
  while (steps2 < 5000) { z += 1; steps2++; if (V.collidesWithWalls(vyrezGroupAt(z))) { collisionZ = z; break; } }
  if (collisionZ === null) throw new Error("rear boundary: zadna kolize nalezena");
  const REAR_ANCHOR_Z = collisionZ - 20;
  if (V.collidesWithWalls(vyrezGroupAt(REAR_ANCHOR_Z))) throw new Error("rear boundary: po 20mm zpet stale koliduje");

  // ---- STEP 3: column fill, greedy nejsirsi-nejdriv, cela sestava kolize ----
  const legs = [{ type: "plain", anchorZ }];
  const columns = [];
  function legPartsFor(type) { return type === "vyrez" ? vyrezLocalDefault : plainLocal; }
  function railsAndConnectorsForColumn(N, legFrom, legTo, Y) {
    const railZFrom = legFrom.anchorZ + T, railZTo = legTo.anchorZ;
    const railLen = railZTo - railZFrom, railZCenter = (railZFrom + railZTo) / 2;
    const crossLen = D - 2 * T, crossXCenter = D / 2;
    const parts = [];
    parts.push({ part_id: "Object_7", position: [offsetX - T / 2, Y + offsetY, railZCenter], quaternion: Q_ALONG_Z, scale: [1, railLen / 1000, 1], role: "nosnik" });
    parts.push({ part_id: "Object_7", position: [offsetX - (D - T / 2), Y + offsetY, railZCenter], quaternion: Q_ALONG_Z, scale: [1, railLen / 1000, 1], role: "nosnik" });
    CONNECTOR_POS[N].forEach(localZ => {
      parts.push({ part_id: "Object_7", position: [offsetX - crossXCenter, Y + offsetY, railZFrom + localZ], quaternion: Q_ALONG_X, scale: [1, crossLen / 1000, 1], role: "spojnice" });
    });
    return parts;
  }
  function wholeAssemblyParts() {
    let parts = [];
    legs.forEach(leg => parts.push(...toWorld(legPartsFor(leg.type), offsetX, offsetY, leg.anchorZ)));
    columns.forEach(col => parts.push(...railsAndConnectorsForColumn(col.N, legs[col.legFromIdx], legs[col.legToIdx], 410)));
    return parts;
  }
  function assemblyCollides(extra) { return V.collidesWithWalls(V.buildLegObject([...wholeAssemblyParts(), ...(extra || [])])); }

  let colIdx = 0;
  while (colIdx < 20) {
    const lastLeg = legs[legs.length - 1];
    let placed = false;
    for (const N of [3, 2, 1]) {
      const clear = SPANS[N];
      const newAnchorZ = lastLeg.anchorZ + T + clear;
      if (newAnchorZ > REAR_ANCHOR_Z) continue;
      const candidateLeg = { type: "vyrez", anchorZ: newAnchorZ };
      const candidateParts = toWorld(legPartsFor("vyrez"), offsetX, offsetY, newAnchorZ);
      const railParts = railsAndConnectorsForColumn(N, lastLeg, candidateLeg, 410);
      if (!assemblyCollides([...candidateParts, ...railParts])) {
        legs.push(candidateLeg);
        columns.push({ N, legFromIdx: legs.length - 2, legToIdx: legs.length - 1 });
        placed = true;
        break;
      }
    }
    if (!placed) break;
    colIdx++;
  }

  if (columns.length === 0) {
    return { ok: false, reason: "no_column_fits", offsetX, offsetY, anchorZ0: anchorZ, REAR_ANCHOR_Z, cfg };
  }

  // ---- STEP 4: vyrez extension (Y_new) per vyrez leg, fresh 1mm stepping ----
  const X_WORLD_WALL = offsetX - (D - T / 2);
  function buildUpperPiece(bottomY, aZ) {
    const lenY = TOP_Y - bottomY;
    return { part_id: "Object_7", position: [X_WORLD_WALL, (bottomY + TOP_Y) / 2 + offsetY, aZ + T / 2], quaternion: [0, 0, 0, 1], scale: [1, lenY / 1000, 1], role: "zadni-svislice-nad-zarezem" };
  }
  const yNewByLeg = {};
  legs.forEach((leg, i) => {
    if (leg.type !== "vyrez") return;
    let collisionBottomY = null;
    for (let bottomY = CUTOUT_H - 1; bottomY >= 0; bottomY--) {
      if (V.collidesWithWalls(V.buildLegObject([buildUpperPiece(bottomY, leg.anchorZ)]))) { collisionBottomY = bottomY; break; }
    }
    if (collisionBottomY === null) collisionBottomY = 0;
    const Y_NEW = collisionBottomY + 20;
    if (V.collidesWithWalls(V.buildLegObject([buildUpperPiece(Y_NEW, leg.anchorZ)]))) throw new Error(`leg[${i}]: Y_new po 20mm zpet stale koliduje`);
    yNewByLeg[i] = Y_NEW;
  });

  // ---- STEP 5: rail floor per column, fresh stepping nahoru pokud leg-based floor koliduje ----
  function legFloorOf(i) { return legs[i].type === "plain" ? 0 : yNewByLeg[i]; }
  const floorByCol = {};
  columns.forEach((col, ci) => {
    const legFrom = legs[col.legFromIdx], legTo = legs[col.legToIdx];
    const floorLegBased = Math.max(legFloorOf(col.legFromIdx), legFloorOf(col.legToIdx));
    let finalFloor = floorLegBased;
    const testRail = (Y) => V.collidesWithWalls(V.buildLegObject(railsAndConnectorsForColumn(col.N, legFrom, legTo, Y)));
    if (testRail(floorLegBased + T / 2)) {
      let Y = floorLegBased + T / 2, steps = 0, cleared = null;
      while (steps < 800) { Y += 1; steps++; if (!testRail(Y)) { cleared = Y; break; } }
      if (cleared === null) throw new Error(`sloupec ${ci}: nenalezen bezkolizni rail floor`);
      const withMargin = cleared + 20;
      if (testRail(withMargin)) throw new Error(`sloupec ${ci}: i po +20mm rail koliduje`);
      finalFloor = withMargin - T / 2;
    }
    floorByCol[ci] = finalFloor;
  });

  // ---- STEP 7 (ceiling probe per column, cela hloubka D) ----
  function fullDepthSlab(y, zFrom, zTo) {
    const geo = new THREE.BoxGeometry(D, 10, zTo - zFrom);
    const mesh = new THREE.Mesh(geo);
    mesh.position.set(offsetX - D / 2, y, (zFrom + zTo) / 2);
    mesh.updateMatrixWorld(true);
    return mesh;
  }
  const ceilByCol = {};
  columns.forEach((col, ci) => {
    const legFrom = legs[col.legFromIdx], legTo = legs[col.legToIdx];
    const zFrom = legFrom.anchorZ + T, zTo = legTo.anchorZ;
    let y = floorByCol[ci] + 50, steps = 0, collisionY = null;
    const maxProbe = TOP_Y + 400;
    while (steps < 2000 && y < maxProbe) { y += 1; steps++; if (V.collidesWithWalls(fullDepthSlab(y, zFrom, zTo))) { collisionY = y; break; } }
    if (collisionY === null) collisionY = maxProbe;
    ceilByCol[ci] = collisionY - 2;
  });

  return {
    ok: true, cfg, offsetX, offsetY, anchorZ0: anchorZ, REAR_ANCHOR_Z,
    legs, columns, yNewByLeg, floorByCol, ceilByCol, TOP_Y,
  };
}

module.exports = { runOne };

if (require.main === module) {
  const cfgPath = process.argv[2], outPath = process.argv[3];
  const cfg = JSON.parse(fs.readFileSync(cfgPath, "utf8"));
  const result = runOne(cfg);
  fs.writeFileSync(outPath, JSON.stringify(result, null, 1));
  console.log(cfg.name, "->", result.ok ? `${result.columns.length} sloupcu, ${result.legs.length} noh` : result.reason);
}
