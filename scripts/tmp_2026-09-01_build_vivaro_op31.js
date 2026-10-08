// Build Vivaro OP31 (2020- Electric L1) eurobox rack, variant A, from scratch.
// Reuses the generalized batch engine/pipeline built for Ford Custom/Transit Custom +
// VW Transporter (tmp_2026-08-31_batch_engine.js / _pipeline.js), which is itself the
// parametrized version of the Vivaro OP18 pilot recipe. OP31 shares the SAME shared
// leg design (D=326,T=30,H=1180,CAP_H=260,CUTOUT_H=395) that OP18/Jumpy/Expert/ProAce/
// Custom/Transporter all share (confirmed byte-identical custom_shapes across the
// family in prior sessions) - engine+pipeline independently measure/verify OP31's own
// real GLB geometry (bbox, mirror, dirZtoBulkhead, all collision stepping) fresh, no
// numbers carried over from OP18.
const fs = require("fs");
const { createEngine } = require("/opt/konfigurator/scripts/tmp_2026-08-31_batch_engine.js");
const { runPipeline } = require("/opt/konfigurator/scripts/tmp_2026-08-31_batch_pipeline.js");

const base = "Opel_Vivaro_OP31_2020-";
const engine = createEngine(base);
console.log(JSON.stringify({
  mirror: engine.mirror, dirZtoBulkhead: engine.dirZtoBulkhead,
  boxL0: engine.boxL0, boxB0: engine.boxB0,
}, null, 2));

const result = runPipeline(engine);
fs.writeFileSync("/opt/konfigurator/scripts/tmp_2026-09-01_op31_variantA_result.json", JSON.stringify(result, null, 2));
console.log(result.log.join("\n"));
console.log("ok=" + result.ok);
if (result.ok) {
  console.log("totalBoxes=" + result.totalBoxes + " distinctHeights=" + result.distinctHeights + " legs=" + result.legs + " columns=" + result.columns);
  console.log("columnSummaries=" + JSON.stringify(result.columnSummaries));
} else {
  console.log("reason=" + result.reason);
}
