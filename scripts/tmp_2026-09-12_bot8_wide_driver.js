// Driver: pro dany karoserie_kod + seznam id spocita legs/columns na KAZDE
// sestave zvlast (box-skladba se lisi, skelet noh/sloupcu by mel byt
// shodny - overuje se), aplikuje transformAssemblyGeneric, spusti
// verifikaci (SAT + self-kolize) a vypise vysledek. NEZAPISUJE do DB -
// jen priprava + report, zápis dela az samostatny insert/update skript
// po rucni kontrole vystupu.
const fs = require("fs");
const C = require("./tmp_2026-09-12_bot8_wide_common.js");

const MODEL = process.argv[2]; // napr. "K-021"
const IDS = process.argv.slice(3).map(Number);
const CFG = require("./tmp_2026-09-12_bot8_wide_configs.js")[MODEL];
const CAR_BODY_BASE = CFG.carBodyBase;

const DB = C.dbFetchAssemblies(IDS);
const results = {};
for (const id of IDS) {
  const row = DB[id];
  const parts = row.data.parts;
  const legs = C.analyzeLegs(parts);
  const legZs = legs.map(l => l.z);
  const columns = C.analyzeColumns(parts, legZs);
  // empiricky overeno (wallcheck2.js, raycasting na realny povrch B.glb): noha s
  // nejnizsim Z je VZDY radove blize prepazce (16-86mm) nez ostatni (250-2400mm+),
  // AZ NA T7 (K-284/K-286, config.noWallLeg=true) - tam ani nejblizsi noha neni
  // blizko (950-1900mm), takze deltaZ tam nema zadny leg k aplikaci (viz configs.js).
  const wallLegZ = CFG.noWallLeg ? null : legs[0].z;

  const { parts: newParts, log, dorovnaniByCol } = C.transformAssemblyGeneric(parts, { legs, wallLegZ, columns });
  const verify = C.verifyAssembly(newParts, CAR_BODY_BASE);

  results[id] = { name: row.name, legs, columns, log, dorovnaniByCol, verify, newPartsCount: newParts.length, origPartsCount: parts.length };
  fs.writeFileSync(`/opt/konfigurator/scripts/tmp_2026-09-12_bot8_wide_out_${id}.json`, JSON.stringify(newParts));

  console.log(`==== ${id} (${row.name}) ====`);
  console.log("  legs:", legs.map(l => `Z=${l.z.toFixed(1)}${l.isVyrez ? '[vyrez,oldYnew=' + l.oldYnew.toFixed(2) + ',gap=' + l.gap.toFixed(3) + ']' : l.isPlain ? '[plain]' : '[?]'}`).join(", "));
  console.log("  columns:", columns.map(c => `${c.prefix}(${c.zLow.toFixed(1)}..${c.zHigh.toFixed(1)})`).join(", "));
  console.log("  wallLegZ:", wallLegZ == null ? "null (zadna noha neni u prepazky)" : wallLegZ.toFixed(1));
  console.log("  transform log:", JSON.stringify(log));
  console.log("  dorovnaniByCol:", JSON.stringify(dorovnaniByCol));
  console.log(`  VERIFY: SAT collisions=${verify.satCollisions}/${verify.checked} (skipped ${verify.skipped}), self-collisions(susp)=${verify.selfSusp}`);
  if (verify.satCollisions) console.log("    SAT DETAIL:", JSON.stringify(verify.satDetail));
  if (verify.selfSusp) console.log("    SELF DETAIL:", JSON.stringify(verify.selfDetail));
}
fs.writeFileSync(`/opt/konfigurator/scripts/tmp_2026-09-12_bot8_wide_report_${MODEL}.json`, JSON.stringify(results, (k,v)=>k==='verify'?{satCollisions:v.satCollisions,skipped:v.skipped,satDetail:v.satDetail,selfSusp:v.selfSusp,selfDetail:v.selfDetail,checked:v.checked}:v, 2));
console.log("\nHOTOVO - report ulozen, newParts JSON ulozeny per-id.");
