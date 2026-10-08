// Zpracuje JEDNU sestavu: klasifikace -> transform (deltaZ/deltaY) -> krok5/6
// (visici luzka + dorovnani) -> SAT + seam-gap overeni. Vystup: JSON report +
// (pri uspechu) nove parts ulozene do --out souboru (pro nasledny DB zapis
// samostatnym pythonim skriptem - viz tmp_2026-09-12_bot8_wide_writeback.py).
//
// Pouziti: node tmp_2026-09-12_bot8_wide_process.js <assemblyId> <carBodyBase> <outJsonPath>
const fs = require("fs");
const { execSync } = require("child_process");
const lib = require("./tmp_2026-09-12_bot8_wide_lib.js");

const [, , assemblyIdStr, carBodyBase, outPath] = process.argv;
const assemblyId = Number(assemblyIdStr);
const DELTA_Z = 8, DELTA_Y = 10;

function loadAssembly(id) {
  const dump = execSync(
    `api/venv/bin/python3 scripts/tmp_2026-09-12_bot8_wide_fetch.py ${id}`,
    { cwd: "/opt/konfigurator", maxBuffer: 1024 * 1024 * 80 }
  ).toString();
  return JSON.parse(dump);
}

const raw = loadAssembly(assemblyId);
const parts = lib.realParts(raw);
const carBodyParts = raw.parts.filter(p => String(p.part_id || "").startsWith("car_body_"));

const report = { assemblyId, carBodyBase, partsTotal: parts.length };

const legZ = lib.findLegClusters(parts);
report.legZ = legZ;
if (legZ.length < 2) { report.ok = false; report.error = "min. 2 nohy ocekavano, nalezeno " + legZ.length; fs.writeFileSync(outPath, JSON.stringify(report, null, 1)); console.log(JSON.stringify(report)); process.exit(1); }

const legSets = lib.legRoleSets(parts, legZ);
report.legSets = legSets.map(l => ({ z: +l.z.toFixed(2), hasCutout: l.hasCutout, roles: l.roles }));

const legInfo = legZ.map(z => {
  const p = parts.find(p => p.role === "predni-svislice" && Math.abs(p.position[2] - z) < 5);
  if (!p) throw new Error("chybi predni-svislice pro nohu Z=" + z);
  return { z, x: p.position[0], y: p.position[1] };
});
const { idx: prepazkaIdx, dist, dir, detail } = lib.findPrepazkaLeg(carBodyBase, legInfo);
report.prepazka = { idx: prepazkaIdx, dist: +dist.toFixed(1), dir };
if (prepazkaIdx < 0) { report.ok = false; report.error = "prepazka leg nenalezena"; fs.writeFileSync(outPath, JSON.stringify(report, null, 1)); console.log(JSON.stringify(report)); process.exit(1); }

const cutoutIdxs = legSets.map((l, i) => l.hasCutout ? i : -1).filter(i => i >= 0);
report.cutoutIdxs = cutoutIdxs;

const oldYnew = lib.computeOldYnew(parts, legZ, cutoutIdxs);
report.oldYnew = {};
for (const i of cutoutIdxs) {
  if (!oldYnew[i]) { report.ok = false; report.error = `leg${i}: nepodarilo se spocitat OLD_YNEW`; fs.writeFileSync(outPath, JSON.stringify(report, null, 1)); console.log(JSON.stringify(report)); process.exit(1); }
  report.oldYnew[i] = { yNew: +oldYnew[i].yNew.toFixed(3), T: +oldYnew[i].T.toFixed(1), matchGap: +oldYnew[i].matchGap.toFixed(3), hasSloupek: oldYnew[i].hasSloupek };
  if (oldYnew[i].matchGap > 0.5) { report.ok = false; report.error = `leg${i}: matchGap ${oldYnew[i].matchGap.toFixed(2)}mm > 0.5mm, sloupek/svislice nesedi presne`; fs.writeFileSync(outPath, JSON.stringify(report, null, 1)); console.log(JSON.stringify(report)); process.exit(1); }
}

const deltaZLeg = dir > 0 ? DELTA_Z : -DELTA_Z;
const config = { legZ, prepazkaIdx, deltaZ: deltaZLeg, cutoutIdxs, oldYnew, deltaY: DELTA_Y };
let { parts: newParts, report: classifyReport } = lib.transformParts(parts, config);
report.classify = classifyReport;
// Pokryti je strukturalne zarucene (kazdy vstupni dil produkuje presne 1 vystupni),
// tady jen over, ze se pocet dilu behem transformace neztratil/nezdvojil.
if (newParts.length !== parts.length) { report.ok = false; report.error = `pocet dilu po transformaci nesedi: ${newParts.length} != ${parts.length}`; fs.writeFileSync(outPath, JSON.stringify(report, null, 1)); console.log(JSON.stringify(report)); process.exit(1); }

// Krok 5+6: visici luzka + dorovnani
const hangs = lib.checkHangingShelves(newParts, config);
report.hangingCheck = hangs.map(h => ({ ...h, lowestPatroY: +h.lowestPatroY.toFixed(2), newYnew: +h.newYnew.toFixed(2), gap: +h.gap.toFixed(2) }));
report.dorovnani = [];
for (const h of hangs) {
  if (h.gap < 0) {
    if (h.colIdx == null) { report.ok = false; report.error = `sloupec ${JSON.stringify(h.colBetween)} visi (gap=${h.gap.toFixed(2)}mm) ale nepodarilo se zjistit colIdx pro dorovnani`; fs.writeFileSync(outPath, JSON.stringify(report, null, 1)); console.log(JSON.stringify(report)); process.exit(1); }
    const shortfall = -h.gap;
    const res = lib.applyDorovnani(newParts, h.colIdx, shortfall);
    report.dorovnani.push({ colIdx: h.colIdx, shortfall: +shortfall.toFixed(2), touched: res.touched, patra: res.patra, note: res.note || null });
    if (!res.touched) { report.ok = false; report.error = `dorovnani sloupec ${h.colIdx}: 0 dilu dotceno (shortfall=${shortfall.toFixed(2)}mm)`; fs.writeFileSync(outPath, JSON.stringify(report, null, 1)); console.log(JSON.stringify(report)); process.exit(1); }
  }
}
// znovu zkontroluj po dorovnani
if (report.dorovnani.length) {
  const hangs2 = lib.checkHangingShelves(newParts, config);
  report.hangingCheckAfterDorovnani = hangs2.map(h => ({ ...h, lowestPatroY: +h.lowestPatroY.toFixed(2), newYnew: +h.newYnew.toFixed(2), gap: +h.gap.toFixed(2) }));
  if (hangs2.some(h => h.gap < -0.5)) { report.ok = false; report.error = "po dorovnani porad visi: " + JSON.stringify(hangs2.filter(h => h.gap < -0.5)); fs.writeFileSync(outPath, JSON.stringify(report, null, 1)); console.log(JSON.stringify(report)); process.exit(1); }
}

// Krok 7: SAT + seam gap
const fullNewParts = newParts.concat(carBodyParts);
const sat = lib.satVerify(newParts, carBodyBase);
report.sat = { collisions: sat.collisions, skipped: sat.skipped, total: sat.total, selfSusp: sat.selfSusp, collided: sat.collided.slice(0, 20), susp: sat.susp.slice(0, 20) };
if (sat.collisions > 0) { report.ok = false; report.error = `SAT: ${sat.collisions} kolizi proti realne karoserii`; fs.writeFileSync(outPath, JSON.stringify(report, null, 1)); console.log(JSON.stringify(report)); process.exit(1); }

report.ok = true;
raw.parts = fullNewParts;
fs.writeFileSync(outPath, JSON.stringify({ report, data: raw }, null, 1));
console.log(JSON.stringify(report));
