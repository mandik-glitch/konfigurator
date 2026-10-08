// QA: vzpera 45 st. v katalogu Sceny (webapp/js/scene/catalog-panels.js: BRACE_DEFS / buildBraceShape) - vypise tvary pro ruzne delky jako JSON;
// geometrii (zasunuti spojek do profilu, zrcadlovost, souosost) overuje scripts/qa/catalog_brace_shape.py nad SKUTECNYMI sitemi dilu. (bot8, 2026-10-03)
const fs = require("fs"), path = require("path");
const src = fs.readFileSync(process.env.CATALOG_PANELS_SRC || path.join(__dirname, "..", "..", "webapp", "js", "scene", "catalog-panels.js"), "utf8");
const a = src.indexOf("const BRACE_MIN_MM"), b = src.indexOf("function insertBraceFromCatalog");
if (a < 0 || b < 0) { console.log(JSON.stringify({ error: "BRACE_DEFS/buildBraceShape v catalog-panels.js chybi" })); process.exit(2); }
const mod = new Function(src.slice(a, b) + "\nreturn { BRACE_DEFS, BRACE_MIN_MM, BRACE_MAX_MM, buildBraceShape };")();
const out = { min: mod.BRACE_MIN_MM, max: mod.BRACE_MAX_MM, shapes: [], rejected: [] };
for (const sys of Object.keys(mod.BRACE_DEFS)) {
  for (const L of [100, 101, 300, 777, 1000]) out.shapes.push({ sys, L, shape: mod.buildBraceShape(sys, L) });
  for (const L of [0, 99, 1001, NaN, 5000]) out.rejected.push({ sys, L, shape: mod.buildBraceShape(sys, L) });
}
out.badSys = mod.buildBraceShape("99", 300);
console.log(JSON.stringify(out));
