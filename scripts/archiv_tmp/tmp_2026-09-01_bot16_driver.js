const fs = require("fs");
const { configs } = require("/opt/konfigurator/scripts/tmp_2026-09-01_bot16_configs.js");
const { runVehicle } = require("/opt/konfigurator/scripts/tmp_2026-09-01_bot16_run_pipeline.js");

const only = process.argv[2]; // volitelny filtr na jeden klic pro debug
const results = {};
const columnSummariesAll = {};
for (const cfg of configs) {
  if (only && cfg.key !== only) continue;
  console.log(`\n########## ${cfg.key} (${cfg.bodyPrefix}) ##########`);
  try {
    const r = runVehicle(cfg);
    results[cfg.key] = r;
    r.log.forEach(l => console.log("  " + l));
    if (r.ok) {
      console.log(`  => OK: ${r.totalBoxes} boxu, ${r.columns.length} sloupcu, vysky ${r.distinctHeights}`);
      fs.writeFileSync(`/opt/konfigurator/scripts/tmp_2026-09-01_bot16_rack_${cfg.key}.json`, JSON.stringify(r.allParts, null, 1));
      columnSummariesAll[cfg.key] = r.columnSummaries;
    } else {
      console.log(`  => NEVEJDE SE (${r.reason})`);
    }
  } catch (e) {
    console.log("  => CHYBA:", e.message);
    results[cfg.key] = { ok: false, reason: "exception:" + e.message, cfg };
  }
}
const summary = Object.fromEntries(Object.entries(results).map(([k, v]) => [k, {
  ok: v.ok, reason: v.reason,
  columns: v.ok ? v.columns.length : undefined,
  totalBoxes: v.ok ? v.totalBoxes : undefined,
  distinctHeights: v.ok ? v.distinctHeights : undefined,
  legs: v.ok ? v.legs.length : undefined,
}]));
fs.writeFileSync("/opt/konfigurator/scripts/tmp_2026-09-01_bot16_summary.json", JSON.stringify(summary, null, 1));
fs.writeFileSync("/opt/konfigurator/scripts/tmp_2026-09-01_bot16_column_summaries.json", JSON.stringify(columnSummariesAll, null, 1));
console.log("\n\n=== SUMMARY ===");
console.log(JSON.stringify(summary, null, 1));
