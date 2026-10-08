const fs = require("fs");
const { createEngine } = require("/opt/konfigurator/scripts/tmp_2026-08-31_batch_engine.js");
const { runPipeline } = require("/opt/konfigurator/scripts/tmp_2026-08-31_batch_pipeline.js");

const VEHICLES = [
  // Ford Custom / Transit Custom
  { key: "FO10", carId: 254, base: "Ford_Custom_FO10_2012-2023", label: "Custom FO10" },
  { key: "FO11", carId: 257, base: "Ford_Custom_FO11_2012-2023", label: "Custom FO11" },
  { key: "FO21", carId: 260, base: "Ford_Custom_FO21_2012-2023", label: "Custom FO21" },
  { key: "FO27", carId: 263, base: "Ford_Custom_FO27_2012-2023", label: "Custom FO27" },
  { key: "FO28", carId: 266, base: "Ford_Custom_FO28_2012-2023", label: "Custom FO28" },
  { key: "FO29", carId: 269, base: "Ford_Custom_FO29_2012-2023", label: "Custom FO29" },
  { key: "FO31", carId: 272, base: "Ford_Custom_FO31_2023-", label: "Transit Custom L2 FO31" },
  { key: "FO38", carId: 275, base: "Ford_Custom_FO38_2023-", label: "Custom FO38" },
  { key: "FO39", carId: 278, base: "Ford_Custom_FO39_2023-", label: "Custom FO39" },
  { key: "FO47", carId: 281, base: "Ford_Custom_FO47_2023-", label: "E-Transit Custom L1 FO47" },
  { key: "FO48", carId: 284, base: "Ford_Custom_FO48_2023-", label: "E-Transit Custom L2 FO48" },
  { key: "FO55", carId: 287, base: "Ford_Custom_FO55_2023-", label: "Custom FO55" },
  { key: "FO56", carId: 290, base: "Ford_Custom_FO56_2023-", label: "Custom FO56" },
  // VW Transporter T6/T7
  { key: "VW11", carId: 890, base: "Volkswagen_Transporter_VW11_2003-2023", label: "Transporter T6 VW11" },
  { key: "VW12", carId: 893, base: "Volkswagen_Transporter_VW12_2003-2023", label: "Transporter T6 VW12" },
  { key: "VW15", carId: 896, base: "Volkswagen_Transporter_VW15_2003-2023", label: "Transporter T6 VW15" },
  { key: "VW25", carId: 899, base: "Volkswagen_Transporter_VW25_2024-", label: "Transporter T7 VW25" },
  { key: "VW27", carId: 902, base: "Volkswagen_Transporter_VW27_2024-", label: "Transporter T7 VW27" },
  { key: "VW29", carId: 905, base: "Volkswagen_Transporter_VW29_2024-", label: "Transporter T7 TwinCab VW29" },
  { key: "VW30", carId: 908, base: "Volkswagen_Transporter_VW30_2024-", label: "Transporter T7 TwinCab VW30" },
  { key: "VW42", carId: 911, base: "Volkswagen_Transporter_VW42_2024-", label: "Transporter T7 VW42" },
  { key: "VW43", carId: 914, base: "Volkswagen_Transporter_VW43_2024-", label: "Transporter T7 VW43" },
];

const only = process.argv[2] ? process.argv[2].split(",") : null;
const results = {};
for (const v of VEHICLES) {
  if (only && !only.includes(v.key)) continue;
  console.log(`\n########## ${v.key} (${v.label}) ##########`);
  try {
    const engine = createEngine(v.base);
    console.log(`  mirror=${engine.mirror} dirZtoBulkhead=${engine.dirZtoBulkhead}`);
    const res = runPipeline(engine);
    if (res.ok) {
      console.log(`  OK: legs=${res.legs} columns=${res.columns} totalBoxes=${res.totalBoxes} distinctHeights=${res.distinctHeights}`);
      results[v.key] = { ok: true, vehicle: v, summary: { legs: res.legs, columns: res.columns, totalBoxes: res.totalBoxes, distinctHeights: res.distinctHeights, columnSummaries: res.columnSummaries } };
      fs.writeFileSync(`/opt/konfigurator/scripts/tmp_2026-08-31_batch_${v.key}_parts.json`, JSON.stringify(res.parts, null, 0));
    } else {
      console.log(`  NOTHING FITS / FAIL: ${res.reason}`);
      results[v.key] = { ok: false, vehicle: v, reason: res.reason, log: res.log };
    }
  } catch (e) {
    console.log(`  ERROR: ${e.message}`);
    results[v.key] = { ok: false, vehicle: v, reason: "EXCEPTION: " + e.message };
  }
}
fs.writeFileSync("/opt/konfigurator/scripts/tmp_2026-08-31_batch_results.json", JSON.stringify(results, null, 1));
console.log("\n\n=== SUMMARY ===");
for (const k in results) {
  const r = results[k];
  console.log(k, r.ok ? `OK boxes=${r.summary.totalBoxes} heights=${r.summary.distinctHeights}` : `FAIL: ${r.reason}`);
}
