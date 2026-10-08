// Generic per-vehicle eurobox rack builder (LEFT wall), implementing:
//  - car_body_placement_methods.id=1 (kolizni-krokovani, bulkhead-first, MIRROR_X)
//  - shape_geometry_methods.id=5 (regal-sloupcova-struktura, greedy widest-first)
//  - shape_geometry_methods.id=6 (protazeni-zadni-svislice-vyrezove-nohy)
//  - shape_geometry_methods.id=3 (ukladani-euroboxu-do-luzek, vertical tiers)
// Usage: node 2026-09-01_build_vehicle_rack.js <configKey>   (see CONFIGS below)
const THREE = require("three");
const fs = require("fs");
const path = require("path");
const { makeCollisionModule } = require("/opt/konfigurator/scripts/2026-09-01_collision_module_factory.js");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const { T, half, W, buildPlain, buildVyrez, FAMILY } = require("/opt/konfigurator/scripts/2026-09-01_leg_local_shapes.js");

const KAT = "/opt/konfigurator/webapp/katalog/";
const CARB = KAT + "car_bodies/";
const OBJ7 = KAT + "Object_7.glb";
const ENDCAP = KAT + "product_3071.glb";
const EUROBOX_GLB = { 120: KAT + "product_3788.glb", 170: KAT + "product_3793.glb", 220: KAT + "product_3794.glb", 270: KAT + "product_3795.glb" };
const EUROBOX_PID = { 120: "product_3788", 170: "product_3793", 220: "product_3794", 270: "product_3795" };
const CONNECTOR_POS = { 1: [15, 415], 2: [15, 415, 816], 3: [15, 415, 816, 1217] };
const WIDTHS = [1232, 832, 430]; // greedy widest-first
const N_FOR_WIDTH = { 1232: 3, 832: 2, 430: 1 };
const Q_ALONG_Z = [-0.707107, 0, 0, 0.707107];
const Q_ALONG_X = [0, 0, -0.707107, 0.707107];
const Q_ENDCAP_UP = [0.7071067811865475, 0, 0, 0.7071067811865475];
const CAP_FLANGE_THICKNESS = 3;

function stepUntilCollision1D(testFn, dir, maxSteps, backoff) {
  let steps = 0, collided = false, val = 0;
  while (steps < maxSteps) {
    val += dir; steps++;
    if (testFn(val)) { collided = true; break; }
  }
  if (!collided) return null; // no collision within range
  const backoffVal = val - dir * backoff;
  const stillColliding = testFn(backoffVal);
  if (stillColliding) throw new Error(`stepUntilCollision1D: after ${backoff}mm backoff still colliding (val=${backoffVal})`);
  return backoffVal;
}

function buildRack(cfg) {
  const fam = FAMILY[cfg.family];
  const { H, CAP_H, CUTOUT_H, uskok, capOffsetFromW, hasBottomCrossVyrez } = fam;
  const mod = makeCollisionModule(CARB + cfg.base);
  const { collidesWithWalls, boxL0, boxB0 } = mod;

  function toWorld(localParts, offsetX, offsetY, anchorZ) {
    return localParts.map(p => ({
      part_id: p.part_id || "Object_7",
      position: [offsetX - p.position[0], p.position[1] + offsetY, anchorZ + p.position[2]],
      quaternion: p.quaternion, scale: p.scale, role: p.role,
    }));
  }
  function legGroup(parts) { return mod.buildLegObject(parts); }

  // ---------- STAGE 1: bulkhead-first single (plain) leg placement ----------
  const cargoZmin = boxB0.max.z; // near face of bulkhead (closest to cargo, very negative Z)
  const cargoZmax = boxL0.max.z; // open end (small/positive Z)
  const cargoZmid = (cargoZmin + cargoZmax) / 2;
  let offsetX = -W / 2;
  let offsetY = 600 - H / 2;
  let anchorZ = cargoZmid - T / 2;

  const plainLocal = buildPlain(H, CAP_H, capOffsetFromW);
  function groupAt(ox, oy, az, localParts) { return legGroup(toWorld(localParts, ox, oy, az)); }

  const dY = stepUntilCollision1D((v) => collidesWithWalls(groupAt(offsetX, offsetY + v, anchorZ, plainLocal)), -1, 3000, 2);
  if (dY == null) throw new Error("floor: no collision found (start too high?)");
  offsetY += dY;

  const dZ = stepUntilCollision1D((v) => collidesWithWalls(groupAt(offsetX, offsetY, anchorZ + v, plainLocal)), -1, 4000, 2);
  if (dZ == null) throw new Error("bulkhead: no collision found");
  anchorZ += dZ;

  const dX = stepUntilCollision1D((v) => collidesWithWalls(groupAt(offsetX + v, offsetY, anchorZ, plainLocal)), -1, 2000, 2);
  if (dX == null) throw new Error("wall: no collision found");
  offsetX += dX;

  const leg0 = { anchorZ, type: "plain" };

  // ---------- STAGE 2: rear max boundary (sanity ceiling, 20mm backoff) ----------
  const dRear = stepUntilCollision1D((v) => collidesWithWalls(groupAt(offsetX, offsetY, anchorZ + T + v, plainLocal)), 1, 6000, 20);
  const rearLimitZ = dRear == null ? null : anchorZ + T + dRear;

  // ---------- STAGE 3: greedy widest-first column fill ----------
  const legs = [leg0];
  const columns = [];
  const vyrezLocalBase = buildVyrez(H, CAP_H, CUTOUT_H, uskok, capOffsetFromW, hasBottomCrossVyrez);
  let currentZ = anchorZ + T; // far edge of last leg

  function assembledLegsGroup(legList) {
    const allParts = [];
    legList.forEach(l => {
      const lp = l.type === "plain" ? plainLocal : vyrezLocalBase;
      allParts.push(...toWorld(lp, offsetX, offsetY, l.anchorZ));
    });
    return legGroup(allParts);
  }

  // Real physical end of the vehicle body (open rear edge of the L side panel
  // mesh) - beyond this there is no wall geometry left to collide with, so the
  // pure collidesWithWalls() test alone can never terminate the greedy loop.
  const REAR_PHYSICAL_LIMIT_Z = cargoZmax - 5; // small margin back from the very open edge

  let guard = 0;
  while (guard++ < 20) {
    let placed = false;
    for (const width of WIDTHS) {
      const candidateAnchorZ = currentZ + width;
      if (candidateAnchorZ + T > REAR_PHYSICAL_LIMIT_Z) continue; // past the real end of the vehicle body
      for (const candidateType of ["plain", "vyrez"]) {
        const lp = candidateType === "plain" ? plainLocal : vyrezLocalBase;
        const testLegs = [...legs, { anchorZ: candidateAnchorZ, type: candidateType }];
        if (!collidesWithWalls(assembledLegsGroup(testLegs))) {
          legs.push({ anchorZ: candidateAnchorZ, type: candidateType });
          columns.push({ legFromIdx: legs.length - 2, legToIdx: legs.length - 1, width, N: N_FOR_WIDTH[width] });
          currentZ = candidateAnchorZ + T;
          placed = true;
          break;
        }
      }
      if (placed) break;
    }
    if (!placed) break;
  }

  if (columns.length === 0) {
    return { key: cfg.key, ok: false, reason: "no column fits past first leg", offsetX, offsetY, leg0 };
  }

  // ---------- STAGE 4: protazeni zadni svislice for every vyrez leg ----------
  const legExtensions = {}; // legIdx -> Y_new
  legs.forEach((leg, idx) => {
    if (leg.type !== "vyrez") return;
    // fresh 1mm collision stepping: hold top fixed at CUTOUT_H..(H-CAP_H) segment's
    // bottom edge, push it down from CUTOUT_H, testing ONLY that single profile segment.
    function segAt(bottomY) {
      const topY = H - CAP_H;
      const lenMm = topY - bottomY;
      const seg = [{ position: [W - half, (bottomY + topY) / 2, half], quaternion: [0, 0, 0, 1], scale: [1, lenMm / 1000, 1] }];
      return legGroup(toWorld(seg, offsetX, offsetY, leg.anchorZ));
    }
    let bottomY = CUTOUT_H, collided = false, steps = 0;
    while (steps < CUTOUT_H - 5) {
      bottomY -= 1; steps++;
      if (collidesWithWalls(segAt(bottomY))) { collided = true; break; }
    }
    if (!collided) { legExtensions[idx] = 0; return; } // no gain found, keep base CUTOUT_H
    const Y_new = bottomY + 20;
    if (collidesWithWalls(segAt(Y_new))) { legExtensions[idx] = 0; return; }
    legExtensions[idx] = Math.max(0, Y_new); // absolute Y, will compare vs base CUTOUT_H below
  });

  function vyrezLocalFor(legIdx) {
    const yNew = legExtensions[legIdx];
    if (!yNew || yNew >= CUTOUT_H) return vyrezLocalBase; // no improvement
    return buildVyrez(H, CAP_H, yNew, uskok, capOffsetFromW, false).map(p => p.role === "sloupek-pred-podbehem" ? { ...p } : p);
    // Note: sloupek-pred-podbehem in buildVyrez already spans [0,CUTOUT_H] using the
    // passed CUTOUT_H param, and zadni-svislice-nad-zarezem spans [CUTOUT_H,H-CAP_H] -
    // reusing buildVyrez(yNew) directly gives exactly the extended/shortened pair.
  }

  // ---------- STAGE 5: rail floor per column (leg-based + full-span verification) ----------
  const TOP_Y = H - CAP_H;
  const RAIL_CENTER_MAX = TOP_Y - T / 2;
  const columnPlans = columns.map((col, colIdx) => {
    const legFrom = legs[col.legFromIdx], legTo = legs[col.legToIdx];
    const floorFrom = legFrom.type === "vyrez" ? (legExtensions[col.legFromIdx] || CUTOUT_H) : 200; // rule 5: plain-bounded => 200mm fixed
    const floorTo = legTo.type === "vyrez" ? (legExtensions[col.legToIdx] || CUTOUT_H) : 200;
    let floorY = Math.max(floorFrom, floorTo, 200);
    const railZFrom = legFrom.anchorZ + T, railZTo = legTo.anchorZ;
    const railZCenter = (railZFrom + railZTo) / 2, railLen = railZTo - railZFrom;
    const crossLen = W - 2 * T, crossXCenter = W / 2;
    function railGroupAt(y) {
      const parts = [
        { position: [half, y + T / 2, railZCenter], quaternion: Q_ALONG_Z, scale: [1, railLen / 1000, 1] }, // near-front rail (local x=T/2 -> handled by offsetX mapping below)
      ];
      // build directly in world coords (rails are symmetric so express world X directly)
      return legGroup([
        { part_id: "Object_7", position: [offsetX - half, y + offsetY + T / 2, railZCenter], quaternion: Q_ALONG_Z, scale: [1, railLen / 1000, 1] },
        { part_id: "Object_7", position: [offsetX - (W - half), y + offsetY + T / 2, railZCenter], quaternion: Q_ALONG_Z, scale: [1, railLen / 1000, 1] },
      ]);
    }
    // fresh full-span collision check/adjust (KOMPONENTY_EUROBOXY.md CI25 lesson)
    let guardY = 0;
    while (collidesWithWalls(railGroupAt(floorY)) && guardY++ < 500) floorY += 1;
    if (guardY > 0) floorY += 20; // extra buffer matching 20mm-backoff convention, then re-verify
    while (collidesWithWalls(railGroupAt(floorY)) && guardY++ < 600) floorY += 1;
    return { colIdx, legFromIdx: col.legFromIdx, legToIdx: col.legToIdx, N: col.N, floorY, railZFrom, railZTo, railZCenter, railLen, crossLen, crossXCenter };
  });

  // ---------- STAGE 6: vertical tiers (diversified heights) ----------
  const HEIGHT_CYCLE = [270, 220, 170, 120];
  const columnLevels = columnPlans.map((cp, colIdx) => {
    let railTop = cp.floorY + T;
    const levels = [];
    let cycleStart = colIdx % HEIGHT_CYCLE.length;
    let hIdx = cycleStart;
    while (true) {
      const railYCenter = railTop - T / 2;
      if (railYCenter > RAIL_CENTER_MAX + 1e-6) break;
      const boxH = HEIGHT_CYCLE[Math.min(hIdx, HEIGHT_CYCLE.length - 1)]; // never wrap back up (must stay non-increasing)
      const boxTop = railTop + boxH;
      const physCeil = H; // absolute leg top; door height (1220/1261) not limiting here
      if (boxTop > physCeil + 1e-6) break;
      levels.push({ railYCenter, boxH, boxTop });
      railTop = railTop + boxH + 30 + T;
      hIdx++;
      if (levels.length > 6) break;
    }
    return { colIdx, levels };
  });

  return {
    key: cfg.key, ok: true, family: cfg.family, base: cfg.base,
    offsetX, offsetY, H, CAP_H, CUTOUT_H, uskok, capOffsetFromW,
    legs, columns, legExtensions, columnPlans, columnLevels, rearLimitZ,
  };
}

module.exports = { buildRack };

if (require.main === module) {
  const key = process.argv[2];
  const cfgPath = process.argv[3] || "/opt/konfigurator/scripts/2026-09-01_vehicle_configs.json";
  const configs = JSON.parse(fs.readFileSync(cfgPath, "utf8"));
  const cfg = configs.find(c => c.key === key);
  if (!cfg) throw new Error("unknown key " + key);
  const t0 = Date.now();
  let result;
  try {
    result = buildRack(cfg);
  } catch (e) {
    result = { key, ok: false, error: e.message, stack: e.stack };
  }
  result.elapsedMs = Date.now() - t0;
  const outPath = `/opt/konfigurator/scripts/2026-09-01_result_${key}.json`;
  fs.writeFileSync(outPath, JSON.stringify(result, null, 1));
  console.log(key, "->", result.ok ? `OK ${result.columns.length} columns` : `FAIL: ${result.reason || result.error}`, `(${result.elapsedMs}ms)`);
}
