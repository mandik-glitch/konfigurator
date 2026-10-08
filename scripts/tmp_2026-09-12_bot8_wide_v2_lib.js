// Sdilena knihovna pro "siroky" prepocet kolizni rezervy (shape_geometry_methods.id=11)
// pro bot8 druhou vlnu modelu (K-007e,K-251,K-008,K-018,K-088,K-094,K-118,K-124,K-163e,
// K-242,K-252e,K-282,K-292 - K-118 uz hotovo drivejsi soubeznou session, viz AGENTS_LOG
// "id=184/215/285 -> 348/353/354").
//
// Postaveno na uz naostro overene tmp_2026-09-12_bot8_wide_common.js (analyzeColumns/
// columnLevels/verifyAssembly znovupouzity beze zmeny), ALE s DVEMA opravami nalezenymi
// pri analyze techto konkretnich 13 modelu:
//   1) "noha u prepazky" NENI vzdy leg0 (na rozdil od tmp_2026-09-12_bot8_generic_kolizni_
//      rezerva_lib.js) - u 5/13 modelu (K-251,K-018,K-094,K-242,K-282) je i nejblizsi noha
//      stovky mm od steny B.glb (zmereno REALNOU GLB geometrii leg-clusteru vs B.glb Box3,
//      ne jen pivot Z) - u tech deltaZ nema zadny geometricky dopad na zadnou nohu.
//   2) vyrezova noha muze chybet cast "sloupek-pred-podbehem" (K-282 posledni noha) - pak
//      se oldYnew pocita jen ze spodni hrany "zadni-svislice-nad-zarezem" (fallback). Pokud
//      takhle vypocteny oldYnew je bezpecne u podlahy (<50mm), znamena to, ze zvyseni
//      rezervy o deltaY by nohu nadzvedlo NAD podlahu bez nahradniho dilu - detekovano a
//      hlaseno jako needsSkip, NEZAPISUJE se (viz AGENTS_LOG zapis k tomuto skriptu).
const fs = require("fs");
const THREE = require("three");
const { parseGlbMesh, glbBoundingBox } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const MeshBVHLib = require("/opt/konfigurator/webapp/js/three-mesh-bvh.js");
THREE.BufferGeometry.prototype.computeBoundsTree = MeshBVHLib.computeBoundsTree;
THREE.Mesh.prototype.raycast = MeshBVHLib.acceleratedRaycast;
const R = require("/opt/konfigurator/scripts/2026-09-11_glb_resolver.js");
const WC = require("/opt/konfigurator/scripts/tmp_2026-09-12_bot8_wide_common.js");

const KAT = "/opt/konfigurator/webapp/katalog/";
const DELTA_Z = 8;
const DELTA_Y = 10;
const near = (a, b, eps) => Math.abs(a - b) < (eps == null ? 1 : eps);

function realParts(parts) {
  return parts.filter(p => !String(p.part_id || "").startsWith("car_body_") && !String(p.role || "").startsWith("kontrolni-pomucka"));
}

// --- noha u prepazky: realna GLB gap mezi leg-clusterem (predni-svislice +-60mm) a B.glb ---
function findWallLegZ(parts, carBodyBase) {
  const bB = glbBoundingBox(KAT + "car_bodies/" + carBodyBase + "_B.glb");
  const frontZs = [...new Set(parts.filter(p => p.role === "predni-svislice").map(p => p.position[2]))].sort((a, b) => a - b);
  const frontZ = frontZs[0];
  const legParts = parts.filter(p => Math.abs(p.position[2] - frontZ) < 60 && !String(p.part_id || "").startsWith("car_body_"));
  let minZ = Infinity;
  for (const p of legParts) {
    const gp = R.glbPath(p.part_id);
    if (!gp) continue;
    const m = parseGlbMesh(gp);
    m.position.set(...p.position); m.quaternion.set(...p.quaternion); m.scale.set(...p.scale);
    m.updateMatrixWorld(true);
    const box = new THREE.Box3().setFromObject(m);
    if (box.min.z < minZ) minZ = box.min.z;
  }
  const gap = minZ - bB.max.z;
  const isNear = Math.abs(gap) < 100;
  return { frontZ, gap, isNear, wallLegZ: isNear ? frontZ : null };
}

// --- legy: Z-klastry "predni-svislice", vyrez detekce + oldYnew (se sloupek-optional fallbackem) ---
function analyzeLegs(parts) {
  const zs = [...new Set(parts.filter(p => p.role === "predni-svislice").map(p => p.position[2]))].sort((a, b) => a - b);
  return zs.map(z => {
    const isPlain = parts.some(p => (p.role === "zadni-svislice-dolni" || p.role === "zadni-svislice") && near(p.position[2], z, 2));
    const sloupek = parts.find(p => p.role === "sloupek-pred-podbehem" && near(p.position[2], z, 2));
    const svisl = parts.find(p => p.role === "zadni-svislice-nad-zarezem" && near(p.position[2], z, 2));
    let oldYnew = null, hasSloupek = !!sloupek, seamGapCheck = null;
    if (svisl) {
      if (sloupek) {
        const topSloupek = sloupek.position[1] + sloupek.scale[1] * 500;
        const botSvisl = svisl.position[1] - svisl.scale[1] * 500;
        seamGapCheck = Math.abs(topSloupek - botSvisl);
        oldYnew = (topSloupek + botSvisl) / 2;
      } else {
        oldYnew = svisl.position[1] - svisl.scale[1] * 500; // fallback: kotvit jen na spodek svislice
      }
    }
    return { z, isPlain, isVyrez: !!svisl, hasSloupek, oldYnew, seamGapCheck };
  });
}

// --- bezpecnostni pojistka: vyrezova noha bez sloupku a s oldYnew blizko podlahy = nebezpecne zvednuti nad podlahu ---
function unsafeFloorLift(legs) {
  return legs.filter(l => l.isVyrez && !l.hasSloupek && l.oldYnew != null && l.oldYnew < 50);
}

function shiftVyrezPart(p, role, oldYnew, deltaY) {
  const [x, y, z] = p.position;
  const newYnew = oldYnew + deltaY;
  if (role === "sloupek-pred-podbehem") {
    const oldH = p.scale[1] * 1000, floorY = y - oldH / 2, newH = newYnew - floorY;
    return { ...p, position: [x, floorY + newH / 2, z], scale: [p.scale[0], newH / 1000, p.scale[2]] };
  }
  if (role === "zadni-svislice-nad-zarezem") {
    const oldH = p.scale[1] * 1000, topY = y + oldH / 2, newH = topY - newYnew;
    return { ...p, position: [x, newYnew + newH / 2, z], scale: [p.scale[0], newH / 1000, p.scale[2]] };
  }
  if (role === "pricka-uzavreni-vyrezu") {
    return { ...p, position: [x, y + deltaY, z] }; // rigidni posun == newYnew+T/2 kdyz byl puvodne presne na sevu (viz hlavicka)
  }
  throw new Error("neznama vyrez role: " + role);
}

const LEG_FRAME_ROLES = new Set([
  "predni-svislice", "cap", "spojnice-dolni", "spojnice-horni", "spojnice-horni-uzavreni",
  "zadni-svislice-dolni", "zadni-svislice", "zaslepka", "zaslepka-predni-svislice",
  "zaslepka-zadni-svislice-dolni", "zaslepka-zadni-svislice",
]);
const VYREZ_ROLES = new Set(["sloupek-pred-podbehem", "zadni-svislice-nad-zarezem", "pricka-uzavreni-vyrezu"]);
const ZTOL_ACCESSORY = 60;

function transformParts(parts, legs, wallLegZ, columns) {
  const vyrezLegs = legs.filter(l => l.isVyrez);
  const log = { wallLegRigid: 0, vyrezShift: 0, vyrezAssocShift: 0, colWallEnd: 0, colWallMid: 0,
    colOtherEnd: 0, colOtherMid: 0, dorovnani: 0, unaffected: 0 };

  const dorovnaniByCol = {};
  for (const col of columns) {
    const levels = WC.columnLevels(parts, col.prefix);
    if (!levels.length) continue;
    const legLow = legs.find(l => near(l.z, col.zLow));
    const legHigh = legs.find(l => near(l.z, col.zHigh));
    let bindingYNew = null;
    for (const leg of [legLow, legHigh]) {
      if (leg && leg.isVyrez && leg.oldYnew != null) {
        const yNew = leg.oldYnew + DELTA_Y;
        if (bindingYNew == null || yNew > bindingYNew) bindingYNew = yNew;
      }
    }
    if (bindingYNew == null) continue;
    const level0 = levels[0];
    const nosnikRe0 = new RegExp(`^nosnik-${col.prefix}-${level0}$`);
    const level0Parts = parts.filter(p => nosnikRe0.test(p.role || ""));
    const floorEdge = Math.min(...level0Parts.map(p => p.position[1])) - 15;
    const deficit = bindingYNew - floorEdge;
    if (deficit > 0.01) dorovnaniByCol[col.prefix] = { levels, deficit };
  }
  function dorovnaniShift(colPrefix, level) {
    const d = dorovnaniByCol[colPrefix];
    if (!d) return 0;
    const N = d.levels.length, i = d.levels.indexOf(level);
    if (i < 0) return 0;
    // N=1: jedine patro je soucasne nejnizsi i nejvyssi - zadna mezera k rozlozeni,
    // musi pohltit cely deficit (SAT overeni proti strese/karoserii je konecny rozhodci).
    if (N === 1) return d.deficit;
    return d.deficit * (N - 1 - i) / (N - 1);
  }

  const nosnikRe = /^nosnik-([\w]+)-([\w]+)$/;
  const spojniceRe = /^spojnice-([\w]+)-([\w]+)$/;
  const euroboxRe = /^eurobox-([\w]+)-([\w]+)$/;

  const out = [];
  for (const orig of parts) {
    const p = JSON.parse(JSON.stringify(orig));
    const role = p.role || "";
    const [x, y, z] = p.position;

    if (String(p.part_id || "").startsWith("car_body_")) { out.push(p); continue; }

    if (VYREZ_ROLES.has(role)) {
      const leg = vyrezLegs.find(l => near(z, l.z, 2));
      if (leg && leg.oldYnew != null) { out.push(shiftVyrezPart(p, role, leg.oldYnew, DELTA_Y)); log.vyrezShift++; continue; }
    }

    if (/^zaslepka-zadni-svislice-nad-zarezem/.test(role) || /^uhelnik-/.test(role) || /^zaslepka-sloupek-pred-podbehem/.test(role)) {
      const leg = vyrezLegs.find(l => near(z, l.z, ZTOL_ACCESSORY));
      if (leg && leg.oldYnew != null) {
        if (near(y, leg.oldYnew, 3) || near(y, leg.oldYnew + 30, 3)) {
          out.push({ ...p, position: [x, y + DELTA_Y, z] }); log.vyrezAssocShift++; continue;
        }
        if (wallLegZ != null && near(z, wallLegZ, ZTOL_ACCESSORY) && /^uhelnik-/.test(role)) {
          out.push({ ...p, position: [x, y, z + DELTA_Z] }); log.wallLegRigid++; continue;
        }
        out.push(p); log.unaffected++; continue;
      }
    }

    if (wallLegZ != null && near(z, wallLegZ, LEG_FRAME_ROLES.has(role) ? 1 : ZTOL_ACCESSORY)) {
      if (LEG_FRAME_ROLES.has(role) || /^uhelnik-/.test(role) || /^zaslepka/.test(role)) {
        out.push({ ...p, position: [x, y, z + DELTA_Z] }); log.wallLegRigid++; continue;
      }
    }

    if (LEG_FRAME_ROLES.has(role)) {
      const leg = legs.find(l => near(z, l.z, 2));
      if (leg) { out.push(p); log.unaffected++; continue; }
    }

    let m = nosnikRe.exec(role) || euroboxRe.exec(role);
    if (m) {
      const [, col, level] = m;
      const colDef = columns.find(c => c.prefix === col);
      const isNosnik = nosnikRe.test(role);
      const dy = dorovnaniShift(col, level);
      if (colDef && wallLegZ != null && near(colDef.zLow, wallLegZ)) {
        const newScale = isNosnik ? [p.scale[0], p.scale[1] - DELTA_Z / 1000, p.scale[2]] : p.scale;
        out.push({ ...p, position: [x, y + dy, z + DELTA_Z / 2], scale: newScale }); log.colWallMid++; continue;
      }
      out.push({ ...p, position: [x, y + dy, z] }); log.colOtherMid++; continue;
    }
    m = spojniceRe.exec(role);
    if (m) {
      const [, col, level] = m;
      const colDef = columns.find(c => c.prefix === col);
      const dy = dorovnaniShift(col, level);
      const isWallCol = colDef && wallLegZ != null && near(colDef.zLow, wallLegZ);
      if (!isWallCol) { out.push({ ...p, position: [x, y + dy, z] }); log.colOtherEnd++; continue; }
      const NEAR_LEG_TOL = 60;
      const distWall = Math.abs(z - colDef.zLow);
      const distOther = Math.abs(z - colDef.zHigh);
      if (distWall < NEAR_LEG_TOL) { out.push({ ...p, position: [x, y + dy, z + DELTA_Z] }); log.colWallEnd++; continue; }
      if (distOther < NEAR_LEG_TOL) { out.push({ ...p, position: [x, y + dy, z] }); log.colWallEnd++; continue; }
      out.push({ ...p, position: [x, y + dy, z + DELTA_Z / 2] }); log.colWallMid++; continue;
    }

    out.push(p); log.unaffected++;
  }
  Object.keys(dorovnaniByCol).length && (log.dorovnani = Object.entries(dorovnaniByCol).map(([k, v]) => `${k}:${v.deficit.toFixed(3)}mm/${v.levels.length}patra`));
  return { parts: out, log };
}

// --- presna kontrola sevu (sloupek top vs svislice bottom == 0) + hanging shelf check ---
function seamAndShelfCheck(newParts, legs, columns) {
  const problems = [];
  for (const leg of legs) {
    if (!leg.isVyrez || !leg.hasSloupek) continue;
    const sloupek = newParts.find(p => p.role === "sloupek-pred-podbehem" && near(p.position[2], leg.z, 2));
    const svisl = newParts.find(p => p.role === "zadni-svislice-nad-zarezem" && near(p.position[2], leg.z, 2));
    if (!sloupek || !svisl) { problems.push(`leg z=${leg.z}: chybi sloupek/svisl po transformu`); continue; }
    const topSloupek = sloupek.position[1] + sloupek.scale[1] * 500;
    const botSvisl = svisl.position[1] - svisl.scale[1] * 500;
    const gap = botSvisl - topSloupek;
    if (Math.abs(gap) > 0.02) problems.push(`leg z=${leg.z}: seam gap=${gap.toFixed(4)}mm (ocekavano 0)`);
  }
  for (const col of columns) {
    const legLow = legs.find(l => near(l.z, col.zLow));
    const legHigh = legs.find(l => near(l.z, col.zHigh));
    const vyrez = [legLow, legHigh].filter(l => l && l.isVyrez && l.oldYnew != null);
    if (!vyrez.length) continue;
    const limitYnew = Math.max(...vyrez.map(l => l.oldYnew + DELTA_Y));
    const levels = WC.columnLevels(newParts, col.prefix);
    if (!levels.length) continue;
    const nosnikRe0 = new RegExp(`^nosnik-${col.prefix}-${levels[0]}$`);
    const level0Parts = newParts.filter(p => nosnikRe0.test(p.role || ""));
    const floorEdge = Math.min(...level0Parts.map(p => p.position[1])) - 15;
    const gap = floorEdge - limitYnew;
    if (gap < -0.02) problems.push(`col ${col.prefix}: nejnizsi patro visi ${(-gap).toFixed(3)}mm pod newYnew`);
  }
  return problems;
}

// --- Kompletni pipeline pro jednu sestavu: transform + overeni (baseline i po zmene) ---
function runAssembly(dataParts, carBodyBase, wallLegZOverride) {
  const parts = realParts(dataParts);
  const legs = analyzeLegs(parts);
  const wallInfo = wallLegZOverride !== undefined ? { wallLegZ: wallLegZOverride } : findWallLegZ(parts, carBodyBase);
  const columns = WC.analyzeColumns(parts, legs.map(l => l.z));
  const unsafe = unsafeFloorLift(legs);
  if (unsafe.length) {
    return { ok: false, reason: `vyrezova noha bez sloupku a oldYnew=${unsafe[0].oldYnew.toFixed(2)}mm (blizko podlahy) na Z=${unsafe[0].z.toFixed(1)} - deltaY by nohu nadzvedl nad podlahu bez nahradniho dilu`, legs, columns, wallInfo };
  }
  const { parts: newParts, log } = transformParts(parts, legs, wallInfo.wallLegZ, columns);
  const problems = seamAndShelfCheck(newParts, legs, columns);
  const baseline = WC.verifyAssembly(parts, carBodyBase);
  const after = WC.verifyAssembly(newParts, carBodyBase);
  const newSelfCollisions = Math.max(0, after.selfSusp - baseline.selfSusp);
  const ok = problems.length === 0 && after.satCollisions === 0 && after.skipped === 0 && newSelfCollisions === 0;
  return {
    ok, reason: ok ? null : `problems=${JSON.stringify(problems)} satCollisions=${after.satCollisions} skipped=${after.skipped} baselineSelf=${baseline.selfSusp} afterSelf=${after.selfSusp}`,
    legs, columns, wallInfo, log, problems, baseline, after, newParts,
  };
}

module.exports = {
  KAT, DELTA_Z, DELTA_Y, near, realParts, findWallLegZ, analyzeLegs, unsafeFloorLift,
  transformParts, seamAndShelfCheck, runAssembly,
  analyzeColumns: WC.analyzeColumns, columnLevels: WC.columnLevels, verifyAssembly: WC.verifyAssembly,
};
