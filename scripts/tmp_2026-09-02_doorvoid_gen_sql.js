const fs = require("fs");
const SCRATCH = "/tmp/claude-0/-opt-domeny/40752a20-c083-499a-8fe3-7c39a4eef60b/scratchpad";
const data = JSON.parse(fs.readFileSync(`${SCRATCH}/doorvoid_build_all_result.json`, "utf8"));

const ROW_MAP = {
  FO31: {
    carBody: [272, 270, 271],
    namePrefix: "Transit Custom L2 FO31",
    rows: { A: { pa: 111, sp: 3861, letter: "" }, B: { pa: 153, sp: 3903, letter: " B" }, C: { pa: 154, sp: 3904, letter: " C" }, D: { pa: 175, sp: 3925, letter: " D" }, E: { pa: 176, sp: 3926, letter: " E" } },
  },
  VW25: {
    carBody: [899, 897, 898],
    namePrefix: "T7 VW25",
    rows: { A: { pa: 118, sp: 3868, letter: "" }, B: { pa: 155, sp: 3905, letter: " B" }, C: { pa: 156, sp: 3906, letter: " C" }, D: { pa: 177, sp: 3927, letter: " D" }, E: { pa: 178, sp: 3928, letter: " E" } },
  },
};

function boxSuffix(columnSummaries) {
  // columnSummaries[0].boxHeights = per-level heights (descending); N = boxes per level.
  // Vice pater se stejnou vyskou (napr. E-varianta 120/120/120) se SECTOU do
  // jednoho poctu (boxy43-120x9), ne vypisou opakovane (boxy43-120x3-120x3-120x3).
  const cs = columnSummaries[0];
  const N = cs.N;
  const counts = new Map();
  cs.boxHeights.forEach(h => counts.set(h, (counts.get(h) || 0) + N));
  return [...counts.entries()].sort((a, b) => b[0] - a[0]).map(([h, n]) => `${h}x${n}`).join("-");
}

function sqlEscape(s) {
  return s.replace(/\\/g, "\\\\").replace(/'/g, "\\'");
}

const NOTE_TEMPLATE = (vKey, variantKey, doorGap, doorClear) => sqlEscape(
  `bot16 2026-09-02 - OPRAVA kriticke chyby: predni noha (a cely 1. sloupec) puvodni konstrukce ` +
  `sedela uvnitr skutecneho otvoru bocnich posuvnych dveri v _R_D.glb (mezera bez materialu Z=[${doorGap.near.toFixed(1)},${doorGap.far.toFixed(1)}], ` +
  `sirka ${doorGap.gap.toFixed(1)}mm, zjisteno skenem vertexu Y=[200,900]). Cela sestava (nohy/nosniky/spojnice/boxy/uhelniky/zaslepky) prestavena od noveho ` +
  `predniho kotevniho bodu = konec dvernich otvoru + ${doorClear}mm rezerva, smerem k realne zadni kolizi karoserie (skutecne kolizni krokovani, ne konstanta). ` +
  `Aplikovano shape_geometry_methods.id=1(prevod)/3(luzka)/4(zaslepky)/5(sloupce)/6(protazeni vyrez)/7(uhelniky)/8(vyska nohy dle vysky dveri). ` +
  `Overeno: 0 kolizi s realnou karoserii, 0 neocekavanych self-kolizi, nezavisly druhy pruchod na fresh ulozenych datech (ne z pameti behu skriptu), ` +
  `2D dimenzni pohled (Box3 ze skutecne GLB geometrie). Varianta ${variantKey}. verified_by numericky bot16, NE 'robert' - ceka na Robertovo vizualni potvrzeni ve scene.`
);

let sql = [];
for (const [vKey, vData] of Object.entries(data)) {
  const map = ROW_MAP[vKey];
  for (const [variantKey, variant] of Object.entries(vData.variants)) {
    const row = map.rows[variantKey];
    const carBodyParts = map.carBody.map(id => ({ part_id: `car_body_${id}` }));
    const fullParts = [...carBodyParts, ...variant.parts.map(({ position, quaternion, scale, role, part_id }) => ({ part_id, position, quaternion, scale, role }))];
    const dataObj = {
      parts: fullParts,
      join_groups: [],
      frame_groups: [],
      bom: [],
      price_summary: {},
      _note: NOTE_TEMPLATE(vKey, variantKey, vData.doorGap, 30),
    };
    const dataJson = sqlEscape(JSON.stringify(dataObj));
    const suffix = boxSuffix(variant.columnSummaries);
    const newName = `${map.namePrefix}${row.letter} - boxy43-${suffix}`;
    const newNameEsc = sqlEscape(newName);
    sql.push(`UPDATE product_assemblies SET data='${dataJson}', name='${newNameEsc}' WHERE id=${row.pa};`);
    sql.push(`UPDATE shop_products SET name='${newNameEsc}' WHERE id=${row.sp};`);
    console.log(`${vKey} ${variantKey}: pa=${row.pa} sp=${row.sp} newName="${newName}" parts=${fullParts.length}`);
  }
}

fs.writeFileSync(`${SCRATCH}/doorvoid_update.sql`, sql.join("\n") + "\n");
console.log("\nSQL written to", `${SCRATCH}/doorvoid_update.sql`, "statements:", sql.length);
