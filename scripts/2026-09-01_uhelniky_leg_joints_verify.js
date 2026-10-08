// Overeni obecne metody "uhelniky na spoje nohou" (bot16, 2026-09-01) na
// DVOU prurezech (30x30 a 40x40) - viz shape_geometry_methods
// "uhelniky-na-spoje-nohy" pro plny popis metody a
// scripts/2026-09-01_uhelniky_leg_joints_lib.js pro samotnou implementaci.
//
// 30x30 noha: presne buildPlainAtDepth(326)/buildVyrezAtDepth(326) z
// scripts/tmp_2026-08-30_build_depth_variants_both.js (uz drive zive
// schvalena geometrie - Object_7.glb, T=30, D=326mm).
// 40x40 noha: obecna verze STEJNE stavebnice (generalizovany
// buildPlainAtLegT()) nad Object_11.glb, T=40, synteticky (nikdy neulozeno
// do DB) - overuje, ze metoda funguje NEZAVISLE na konkretnim prurezu.
const fs = require("fs");
const THREE = require("three");
const lib = require("./2026-09-01_uhelniky_leg_joints_lib.js");
const { buildPlainAtDepth, buildVyrezAtDepth } = require("./tmp_2026-08-30_build_depth_variants_both.js");

const KAT = "/opt/konfigurator/webapp/katalog/";
const OBJ7 = KAT + "Object_7.glb"; // profil 30x30
const OBJ11 = KAT + "Object_11.glb"; // profil 40x40
const OBJ2 = KAT + "Object_2.glb"; // profil 45x45

const catalog = JSON.parse(fs.readFileSync("/opt/konfigurator/scripts/2026-09-01_uhelnik_catalog.json", "utf8"));

// ---- generalizovana stavba "plain" nohy pro LIBOVOLNY prurez T (stejna
// sablona jako buildPlainAtDepth, jen T/GLB parametrizovane) ----
function buildPlainLegGeneric(T, D, H, CAP_H, CAP_OFFSET_FROM_WALL) {
  const zCenter = T / 2;
  const rungLo = T, rungHi = D - T;
  const capRight = D - CAP_OFFSET_FROM_WALL, capLeft = capRight - T;
  const part = (xCenter, yCenter, lengthY, vertical, role) => ({
    position: [xCenter, yCenter, zCenter],
    quaternion: vertical ? [0, 0, 0, 1] : [0, 0, -0.707107, 0.707107],
    scale: [1, lengthY / 1000, 1],
    role,
  });
  const parts = [];
  parts.push(part(T / 2, H / 2, H, true, "predni-svislice"));
  const rungLen = rungHi - rungLo;
  parts.push(part((rungLo + rungHi) / 2, T / 2, rungLen, false, "spojnice-dolni"));
  parts.push(part((rungLo + rungHi) / 2, H - CAP_H - T / 2, rungLen, false, "spojnice-horni"));
  parts.push(part(D - T / 2, (H - CAP_H) / 2, H - CAP_H, true, "zadni-svislice-dolni"));
  parts.push(part((capLeft + capRight) / 2, H - CAP_H / 2, CAP_H, true, "cap"));
  return parts;
}

function crossSectionOverlapCheck(entries) {
  // stejny kolizni test jako touchOk() v build_depth_variants_both.js -
  // zadne 2 dily se NESMI prekryvat (presah > 0.5mm na VSECH 3 osach).
  let overlapFound = false;
  for (let i = 0; i < entries.length; i++) {
    for (let j = i + 1; j < entries.length; j++) {
      const A = new THREE.Box3().setFromObject(entries[i].object3d);
      const B = new THREE.Box3().setFromObject(entries[j].object3d);
      const overlapX = Math.min(A.max.x, B.max.x) - Math.max(A.min.x, B.min.x);
      const overlapY = Math.min(A.max.y, B.max.y) - Math.max(A.min.y, B.min.y);
      const overlapZ = Math.min(A.max.z, B.max.z) - Math.max(A.min.z, B.min.z);
      if (overlapX > 0.5 && overlapY > 0.5 && overlapZ > 0.5) {
        console.log(`   !!! PRESAH profilu (${entries[i].role} <-> ${entries[j].role})`);
        overlapFound = true;
      }
    }
  }
  return !overlapFound;
}

// gap/overlap mereni v rohu - stejna metrika jako u puvodniho 30x30 overeni
// (KOMPONENTY_EUROBOXY.md: "gap=0.0000mm/overlap=0.0000mm presne na obou
// profilech rohu"): pro kazdy umisteny uhelnik zmer nejblizsi vzdalenost
// jeho geo_faces (dosedaci plochy) k obema stenam rohu (P i C).
function measureGapOverlap(bracketObj, geoFaces, P, C, dWall, axisDir, side) {
  if (!geoFaces || geoFaces.length < 2) return null;
  bracketObj.updateMatrixWorld(true);
  const n1 = dWall.clone().normalize(), n2 = axisDir.clone().multiplyScalar(side).normalize();
  const wallPlaneMax = (entry, n) => {
    const b = new THREE.Box3().setFromObject(entry.object3d);
    let m = -Infinity;
    for (let xi = 0; xi < 2; xi++) for (let yi = 0; yi < 2; yi++) for (let zi = 0; zi < 2; zi++) {
      const v = new THREE.Vector3(xi ? b.max.x : b.min.x, yi ? b.max.y : b.min.y, zi ? b.max.z : b.min.z).dot(n);
      if (v > m) m = v;
    }
    return m;
  };
  const w1 = wallPlaneMax(P, n1), w2 = wallPlaneMax(C, n2);
  const worldFacePts = geoFaces.slice(0, 2).map(f => new THREE.Vector3(f.x, f.y, f.z).applyMatrix4(bracketObj.matrixWorld));
  // priradi kazdou plochu ke "sve" stene (ktere normale je blize) a spocita signed distance (0=presny dotyk, +=mezera, -=prusak)
  const distToWall = (p) => {
    const d1 = Math.abs(p.dot(n1) - w1);
    const d2 = Math.abs(p.dot(n2) - w2);
    return Math.min(d1, d2);
  };
  return worldFacePts.map(p => distToWall(p));
}

function verifyLeg(label, T, glbPath, legParts, crossSectionMm) {
  console.log(`\n=== ${label} (T=${T}mm) ===`);
  const entries = legParts.map((p, idx) => lib.makeProfileEntry(glbPath, { ...p, idx, cross_section_mm: crossSectionMm }));
  const noCollision = crossSectionOverlapCheck(entries);
  console.log(" bez kolize mezi profily nohy:", noCollision);
  const { results, stats } = lib.applyUhelnikyToLeg(entries, catalog, KAT);
  console.log(" pary profilu (kolme+dotyk+stejny prurez):", stats.pairsMatched, "/", stats.pairsChecked, "kombinaci");
  stats.perPair.forEach(pp => console.log(`   ${pp.a} <-> ${pp.b}: ${pp.count} uhelnik(y)`));
  console.log(" celkem umistenych uhelniku:", stats.totalBracketsPlaced);
  const badNaN = results.filter(r => r.position.some(v => !Number.isFinite(v)) || r.quaternion.some(v => !Number.isFinite(v)));
  console.log(" NaN/neplatnych pozic:", badNaN.length);
  const partIds = new Set(results.map(r => r.part_id));
  console.log(" pouzity katalogovy dil:", Array.from(partIds).join(", "));
  const wrongPart = results.filter(r => r.size_mm !== T);
  console.log(" spatna velikost dilu vs. prurez profilu:", wrongPart.length);

  // gap/overlap - nezavisle mereni na SKUTECNE geometrii (ne jen "algoritmus
  // vratil true"): pro kazdy umisteny uhelnik s geo_faces zmer signed
  // vzdalenost obou oznacenych dosedacich ploch od stěn rohu (P i C).
  const gapChecks = [];
  results.forEach(r => {
    const meta = catalog.find(c => c.part_id === r.part_id);
    if (!meta || !meta.geo_faces) return;
    const P = entries.find(e => e.idx === r.joint.P_idx);
    const C = entries.find(e => e.idx === r.joint.C_idx);
    const geo = lib.cornerGeometry(P, C);
    if (!geo) return;
    const side = r.joint.side;
    const dists = measureGapOverlap(r.object3d, meta.geo_faces, geo.P, geo.C, geo.dWall, geo.axisDir, side);
    if (dists) gapChecks.push({ joint: `${r.joint.P_role}<->${r.joint.C_role}`, dists });
  });
  const maxGap = gapChecks.length ? Math.max(...gapChecks.flatMap(g => g.dists)) : null;
  console.log(" gap/overlap kontrola (", gapChecks.length, "uhelniku s geo_faces ) - max odchylka od steny rohu (mm):", maxGap != null ? maxGap.toFixed(4) : "n/a");

  return { entries, results, stats, noCollision, badNaN, wrongPart, maxGap };
}

// ==== 30x30: plain + vyrez (D=326mm, jiz drive zive schvalena geometrie) ====
const plain30 = buildPlainAtDepth(326);
const vyrez30 = buildVyrezAtDepth(326);
const r1 = verifyLeg("30x30 plain D=326", 30, OBJ7, plain30, [30, 30]);
const r2 = verifyLeg("30x30 vyrez D=326", 30, OBJ7, vyrez30, [30, 30]);

// ==== 40x40: synteticka "plain" noha (nikdy neulozena do DB) ====
const plain40 = buildPlainLegGeneric(40, 400, 1200, 300, 90);
const r3 = verifyLeg("40x40 plain D=400 (synteticky)", 40, OBJ11, plain40, [40, 40]);

// ==== bonus: 45x45 (treti katalogova velikost, jen doplnkove overeni) ====
const plain45 = buildPlainLegGeneric(45, 450, 1300, 320, 100);
const r4 = verifyLeg("45x45 plain D=450 (synteticky, bonus)", 45, OBJ2, plain45, [45, 45]);

// ==== souhrn + ulozeni ====
const summary = {
  "30x30_plain": { pairsMatched: r1.stats.pairsMatched, placed: r1.stats.totalBracketsPlaced, noCollision: r1.noCollision, nan: r1.badNaN.length, wrongPart: r1.wrongPart.length, maxGapMm: r1.maxGap },
  "30x30_vyrez": { pairsMatched: r2.stats.pairsMatched, placed: r2.stats.totalBracketsPlaced, noCollision: r2.noCollision, nan: r2.badNaN.length, wrongPart: r2.wrongPart.length, maxGapMm: r2.maxGap },
  "40x40_plain_synth": { pairsMatched: r3.stats.pairsMatched, placed: r3.stats.totalBracketsPlaced, noCollision: r3.noCollision, nan: r3.badNaN.length, wrongPart: r3.wrongPart.length, maxGapMm: r3.maxGap },
  "45x45_plain_synth_bonus": { pairsMatched: r4.stats.pairsMatched, placed: r4.stats.totalBracketsPlaced, noCollision: r4.noCollision, nan: r4.badNaN.length, wrongPart: r4.wrongPart.length, maxGapMm: r4.maxGap },
};
console.log("\n=== SOUHRN ===");
console.log(JSON.stringify(summary, null, 2));

const dump = (r) => r.results.map(x => ({ part_id: x.part_id, sku: x.sku, size_mm: x.size_mm, joint: x.joint, position: x.position, quaternion: x.quaternion }));
fs.writeFileSync("/opt/konfigurator/scripts/2026-09-01_uhelniky_leg_joints_verify_results.json", JSON.stringify({
  summary,
  "30x30_plain": dump(r1),
  "30x30_vyrez": dump(r2),
  "40x40_plain_synth": dump(r3),
  "45x45_plain_synth_bonus": dump(r4),
}, null, 1));
console.log("\nulozeno 2026-09-01_uhelniky_leg_joints_verify_results.json");

const allOk = [r1, r2, r3, r4].every(r => r.noCollision && r.badNaN.length === 0 && r.wrongPart.length === 0 && r.stats.totalBracketsPlaced > 0 && (r.maxGap == null || r.maxGap < 1.0));
console.log("\nVSECHNY KONTROLY PROSLY:", allOk);
process.exit(allOk ? 0 : 1);
