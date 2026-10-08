// Diagnosticky prubeh (BEZ zapisu) pro jednu sestavu - over topologii, urci prepazka/cutout
// nohy, spocitej OLD_YNEW, over pokryti klasifikace (kazdy dil musi spadnout do presne
// jedne kategorie) a zkontroluj visici luzka PO simulovane aplikaci delty.
const fs = require("fs");
const lib = require("./tmp_2026-09-12_bot8_wide_lib.js");

const [, , dataPath, carBodyBase] = process.argv;
const DELTA_Z = 8, DELTA_Y = 10;

const raw = JSON.parse(fs.readFileSync(dataPath, "utf8"));
const parts = lib.realParts(raw);
console.log("dilu (bez karoserie/pomucek):", parts.length);

const legZ = lib.findLegClusters(parts);
console.log("\nNohy (Z, vzestupne):", legZ.map(z => z.toFixed(2)));

const legSets = lib.legRoleSets(parts, legZ);
legSets.forEach((l, i) => console.log(` leg${i} Z=${l.z.toFixed(2)} cutout=${l.hasCutout} role=[${l.roles.join(",")}]`));

const wallBB = lib.wallBBox(carBodyBase);
console.log("\nWall B celkovy bbox Z-range (jen orientacne):", wallBB.min.z.toFixed(1), "..", wallBB.max.z.toFixed(1));

const legInfo = legZ.map(z => {
  const p = parts.find(p => p.role === "predni-svislice" && Math.abs(p.position[2] - z) < 5);
  return { z, x: p.position[0], y: p.position[1] };
});
const { idx: prepazkaIdx, dist, dir, detail } = lib.findPrepazkaLeg(carBodyBase, legInfo);
console.log("Mistni test kazde nohy (X/Y-pasmo dane nohy):");
for (const d of detail) console.log(`  leg${d.i}: n=${d.n} localWallZ=[${d.minZ?.toFixed(1)},${d.maxZ?.toFixed(1)}] dist=${d.d?.toFixed(1)} dir=${d.dir > 0 ? "+Z" : "-Z"}`);
console.log(`Prepazka leg = leg${prepazkaIdx} (Z=${legZ[prepazkaIdx].toFixed(2)}, dist k B=${dist.toFixed(1)}mm, smer=${dir > 0 ? "+Z" : "-Z"})`);
if (legSets[prepazkaIdx].hasCutout) console.log("!! POZOR: prepazka leg je SOUCASNE cutout leg - neobvykle, over rucne.");

const cutoutIdxs = legSets.map((l, i) => l.hasCutout ? i : -1).filter(i => i >= 0);
console.log("Cutout nohy:", cutoutIdxs.join(","));

const oldYnew = lib.computeOldYnew(parts, legZ, cutoutIdxs);
for (const i of cutoutIdxs) {
  const v = oldYnew[i];
  if (!v) { console.log(`!! leg${i}: NEPODARILO SE spocitat OLD_YNEW (chybi sloupek/svislice?)`); continue; }
  console.log(`leg${i} OLD_YNEW=${v.yNew.toFixed(3)} T(odvozeno)=${v.T.toFixed(1)} matchGap(sloupek.top vs svislice.bottom)=${v.matchGap.toFixed(3)}mm ${v.matchGap > 0.5 ? "!! NESEDI presne" : "OK"}`);
}

const deltaZLeg = dir > 0 ? DELTA_Z : -DELTA_Z;
const config = { legZ, prepazkaIdx, deltaZ: deltaZLeg, cutoutIdxs, oldYnew, deltaY: DELTA_Y };
const { parts: newParts, report } = lib.transformParts(parts, config);
console.log("\nKlasifikace dilu:", JSON.stringify(report));
console.log("soucet:", report.legOwned + report.spanningPlain + report.spanningNosnik + report.seamShift + report.unchanged, "= ma byt", parts.length, "(POZOR: legOwned+seamShift se muze prekryvat u stejneho dilu, soucet muze byt > parts.length)");

const hangs = lib.checkHangingShelves(newParts, config);
console.log("\nKontrola visicich luzek (krok 5):");
for (const h of hangs) {
  console.log(`  cutout leg${h.cutoutLeg}, sloupec mezi legy [${h.colBetween}]: nejnizsi patro Y=${h.lowestPatroY.toFixed(2)}, novy Y_new=${h.newYnew.toFixed(2)}, gap=${h.gap.toFixed(2)}mm ${h.gap < 0 ? "!! VISI - potreba dorovnani" : "OK"}`);
}
if (!hangs.length) console.log("  (zadny sloupec sousedici s cutout nohou nenalezen, nebo cutout nohy nejsou)");

fs.writeFileSync(dataPath.replace(/\.json$/, "_NEW.json"), JSON.stringify({ parts: newParts.concat(raw.parts.filter(p => String(p.part_id || "").startsWith("car_body_"))) }));
console.log("\nUlozeno (docasny nahled):", dataPath.replace(/\.json$/, "_NEW.json"));
