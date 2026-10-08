// Batch: doplnit uhelniky na spoje VSECH noh VSECH sestav, kterym chybi
// (bot22, 2026-09-05, Robert: "doplnit uhelnik na nohy sestav").
//
// Pouziva OVERENOU metodu 2026-09-01_uhelniky_leg_joints_lib.js
// (applyUhelnikyToLeg) 1:1 jako scripts/2026-09-01_uhelniky_leg_joints_verify.js
// - zadna nova geometrie, jen aplikace na realne nohy z DB.
//
// IDEMPOTENTNI: noha, ktera uz uhelniky ma (role zacina "uhelnik"), se
// preskoci. READ-ONLY - vysledek jen do --out JSON, nic do DB.
//
// Pouziti: node scripts/2026-09-05_add_uhelniky_all_legs.js <dump.json> [--out navrh.json]

const fs = require("fs");
const THREE = require("three");
const lib = require("./2026-09-01_uhelniky_leg_joints_lib.js");
const KAT = "/opt/konfigurator/webapp/katalog/";
const OBJ7 = KAT + "Object_7.glb";  // profil 30x30 (vsechny eurobox nohy)
const catalog = JSON.parse(fs.readFileSync("/opt/konfigurator/scripts/2026-09-01_uhelnik_catalog.json", "utf8"));

const asmPath = process.argv[2];
const outIdx = process.argv.indexOf("--out");
const outPath = outIdx > 0 ? process.argv[outIdx + 1] : null;
const input = JSON.parse(fs.readFileSync(asmPath, "utf8"));
const rows = input.rows || input;

// profil nohy? (Object_7 svisly/vodorovny clen nohy - NE pricky pater,
// NE nosniky, NE euroboxy, NE zaslepky)
function isLegProfile(p) {
  if (p.part_id !== "Object_7") return false;
  const r = p.role || "";
  if (/^spojnice-(sloupec|col)\d/.test(r)) return false;  // pricka patra
  if (/^nosnik|^eurobox/.test(r)) return false;
  return /svislice|sloupek|spojnice-dolni|spojnice-horni|^cap$|pricka/.test(r);
}

// gap/overlap mereni v rohu - KOPIE z 2026-09-01_uhelniky_leg_joints_verify.js
// (kriterium flush dosednuti: 0=presny dotyk, max odchylka < 1.0mm).
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
  const distToWall = (p) => Math.min(Math.abs(p.dot(n1) - w1), Math.abs(p.dot(n2) - w2));
  return worldFacePts.map(p => distToWall(p));
}

const patched = {};
let nRows = 0, nLegs = 0, nLegsDone = 0, nBrackets = 0, nSkipExisting = 0;
let gMeasured = 0, gMaxAll = 0;
const fails = [];

for (const row of rows) {
  const parts = row.parts || [];
  // seskup profily noh podle Z
  const byZ = {};
  for (const p of parts) {
    if (!p.position) continue;
    if (isLegProfile(p)) { (byZ[Math.round(p.position[2])] ||= []).push(p); }
  }
  // uz existujici uhelniky podle Z
  const uhelZ = new Set();
  for (const p of parts) if (p.position && /^uhelnik/.test(p.role || "")) uhelZ.add(Math.round(p.position[2]));

  const zs = Object.keys(byZ).map(Number).sort((a, b) => a - b);
  if (!zs.length) continue;
  nRows++;
  const nove = [];
  zs.forEach((z, legIdx) => {
    nLegs++;
    // noha uz ma uhelniky (nejblizsi uhelnik do 60mm)? -> preskoc
    if ([...uhelZ].some((uz) => Math.abs(uz - z) <= 60)) { nSkipExisting++; return; }
    const legParts = byZ[z];
    let results, stats, legEntries;
    try {
      legEntries = legParts.map((p, idx) => lib.makeProfileEntry(OBJ7, { ...p, idx, cross_section_mm: [30, 30] }));
      ({ results, stats } = lib.applyUhelnikyToLeg(legEntries, catalog, KAT));
    } catch (e) { fails.push({ id: row.id, z, err: e.message }); return; }
    // OVERENI (stejna kriteria jako verify skript)
    const badNaN = results.filter((r) => r.position.some((v) => !Number.isFinite(v)) || r.quaternion.some((v) => !Number.isFinite(v)));
    const wrongPart = results.filter((r) => r.size_mm != null && r.size_mm !== 30);
    // FLUSH kontrola: kazdy uhelnik musi dosednout na obe steny rohu (< 1mm)
    let maxGap = 0;
    const entriesByIdx = new Map(results.length ? [] : []);
    for (const r of results) {
      const meta = catalog.find((c) => c.part_id === r.part_id);
      if (!meta || !meta.geo_faces) continue;
      const P = legEntries.find((e) => e.idx === r.joint.P_idx);
      const C = legEntries.find((e) => e.idx === r.joint.C_idx);
      const geo = lib.cornerGeometry(P, C);
      if (!geo) continue;
      const dists = measureGapOverlap(r.object3d, meta.geo_faces, geo.P, geo.C, geo.dWall, geo.axisDir, r.joint.side);
      if (dists) { maxGap = Math.max(maxGap, ...dists.map((d) => Math.abs(d))); gMeasured += dists.length; gMaxAll = Math.max(gMaxAll, ...dists.map((d)=>Math.abs(d))); }
    }
    if (!results.length || badNaN.length || wrongPart.length || maxGap >= 1.0) {
      fails.push({ id: row.id, z, placed: results.length, nan: badNaN.length, wrong: wrongPart.length, maxGap: +maxGap.toFixed(3) });
      return;
    }
    for (const r of results) {
      nove.push({
        part_id: r.part_id,
        position: r.position.map((v) => +v.toFixed(4)),
        quaternion: r.quaternion.map((v) => +v.toFixed(6)),
        scale: r.scale ? r.scale.map((v) => +v.toFixed(6)) : [1, 1, 1],
        role: "uhelnik-noha" + legIdx,
      });
    }
    nBrackets += results.length;
    nLegsDone++;
  });
  if (nove.length) patched[row.id] = { id: row.id, name: row.name, add: nove };
}

console.log("=== DOPLNENI UHELNIKU (dry-run) ===");
console.log("sestav s nohama:        " + nRows);
console.log("noh celkem:             " + nLegs);
console.log("  z toho uz melo uhel.: " + nSkipExisting);
console.log("  nove doplneno:        " + nLegsDone);
console.log("uhelniku pridano:       " + nBrackets);
console.log("dotcenych sestav:       " + Object.keys(patched).length);
console.log("selhani:                " + fails.length);
console.log("gap zmereno (ploch):    " + gMeasured + "  | max odchylka od steny: " + gMaxAll.toFixed(4) + " mm");
if (fails.length) fails.slice(0, 10).forEach((f) => console.log("  id=" + f.id + " z=" + f.z + " " + JSON.stringify(f)));
if (outPath) { fs.writeFileSync(outPath, JSON.stringify(patched)); console.log("navrh -> " + outPath + " (NIC DO DB)"); }
