// Robert: "C uz neni vzor. Vzorem pro horni bloky A/B jsou samotne horni
// bloky A/B, ale PRED aplikaci podminky mezery 25mm a vymeny boxu. Vymeny
// boxu ponechame, horni bloky chceme stejne jake byly pred upravou boxu."
//
// => vratit presne inverzni transformaci k 25mm_recalc.js: odecist 17mm
// od Y u vsech podelnik-*/pricka-(spodni|horni|police)-*/vypln-* casti
// (to je JEDINA zmena, kterou tenkrat dostaly - box swap se tyka
// eurobox-*/nosnik-col*/spojnice-col*/logo-ochrana* roli, ktere
// isHornibBlok() vubec nezachytava, takze box swap zustava nedotceny).
// Pak explicitne premerit mezeru nad prave vymenenym boxem v cilovem
// sloupci - 25mm pravidlo muze byt po vraceni HB dolu ohrozeno.
const fs = require("fs");
const THREE = require("three");
const R = require("/opt/konfigurator/scripts/2026-09-11_glb_resolver.js");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");

const SCRATCH = "/tmp/claude-0/-opt-konfigurator/68994686-5a6b-46d4-b3c7-14bc1f68c6ac/scratchpad";
const D = JSON.parse(fs.readFileSync(`${SCRATCH}/current_8.json`, "utf8"));
const SHIFT = 17;
const HB_PREFIXES = ["podelnik-", "pricka-spodni", "pricka-horni", "pricka-police", "vypln-"];
const isHornibBlok = (p) => HB_PREFIXES.some(pre => (p.role || "").startsWith(pre));

const PLAN = {
  369: ["col1"], 370: ["col1"], 379: ["col1"], 380: ["col1"], 385: ["col1"],
  382: ["col0"], 383: ["col0"], 384: ["col0"],
};

function worldBox(p) {
  const glb = R.glbPath(p.part_id); if (!glb) return null;
  const mesh = parseGlbMesh(glb);
  mesh.position.set(p.position[0], p.position[1], p.position[2]);
  mesh.quaternion.set(p.quaternion[0], p.quaternion[1], p.quaternion[2], p.quaternion[3]);
  mesh.scale.set(p.scale[0], p.scale[1], p.scale[2]);
  mesh.updateMatrixWorld(true);
  return new THREE.Box3().setFromObject(mesh);
}
function overlap3(A, B) { return [Math.min(A.max.x, B.max.x) - Math.max(A.min.x, B.min.x), Math.min(A.max.y, B.max.y) - Math.max(A.min.y, B.min.y), Math.min(A.max.z, B.max.z) - Math.max(A.min.z, B.min.z)]; }
function scan(parts) {
  const m = parts.filter(p => !R.jeKaroserie(p.part_id)).map(p => ({ p, box: worldBox(p) }));
  const pairs = new Map(); let n = 0;
  for (let i = 0; i < m.length; i++) for (let j = i + 1; j < m.length; j++) {
    const [ox, oy, oz] = overlap3(m[i].box, m[j].box);
    if (ox > 0.5 && oy > 0.5 && oz > 0.5) { n++; pairs.set(m[i].p.role + "|" + m[j].p.role, [ox, oy, oz]); }
  }
  return { n, pairs };
}
function headroomForCol(parts, col) {
  const boxes = parts.filter(p => (p.role || "").startsWith("eurobox-" + col)).map(p => ({ p, box: worldBox(p) }));
  if (!boxes.length) return null;
  const topEntry = boxes.reduce((best, x) => (x.box.max.y > (best ? best.box.max.y : -Infinity) ? x : best), null);
  const zLo = topEntry.box.min.z - 0.5, zHi = topEntry.box.max.z + 0.5, xLo = topEntry.box.min.x - 0.5, xHi = topEntry.box.max.x + 0.5;
  let ceiling = Infinity, ceilPart = null;
  for (const p of parts) {
    if (!/spodni|vypln-dno/.test(p.role || "")) continue;
    const b = worldBox(p); if (!b) continue;
    if (b.min.y < topEntry.box.max.y - 0.5) continue;
    const zOv = Math.min(b.max.z, zHi) - Math.max(b.min.z, zLo);
    const xOv = Math.min(b.max.x, xHi) - Math.max(b.min.x, xLo);
    if (zOv <= 0 || xOv <= 0) continue;
    if (b.min.y < ceiling) { ceiling = b.min.y; ceilPart = p.role; }
  }
  return { sku: topEntry.p.part_id, topY: topEntry.box.max.y, ceiling, ceilPart, gap: ceiling - topEntry.box.max.y };
}

const results = [];
for (const [idStr, cols] of Object.entries(PLAN)) {
  const id = Number(idStr);
  const current = D[id].data.parts; // shifted + box-swapped (live)
  const reverted = current.map(p => isHornibBlok(p) ? { ...p, position: [p.position[0], p.position[1] - SHIFT, p.position[2]] } : p);

  const beforeScan = scan(current);
  const afterScan = scan(reverted);
  const newPairs = [...afterScan.pairs.keys()].filter(k => !beforeScan.pairs.has(k));

  console.log(`\n=== id=${id} ${D[id].name} ===`);
  console.log(`kolize: se-shiftem(current)=${beforeScan.n} po-vraceni(reverted)=${afterScan.n} nove=${newPairs.length}`);
  for (const k of newPairs) console.log("   NOVA KOLIZE:", k, JSON.stringify(afterScan.pairs.get(k).map(v => +v.toFixed(1))));

  for (const col of cols) {
    const hCurrent = headroomForCol(current, col);
    const hReverted = headroomForCol(reverted, col);
    console.log(`  ${col}: se-shiftem gap=${hCurrent.gap.toFixed(1)}mm (${hCurrent.sku}, strop=${hCurrent.ceilPart})  ->  po-vraceni gap=${hReverted.gap.toFixed(1)}mm (${hReverted.sku}, strop=${hReverted.ceilPart}) ${hReverted.gap < 25 ? "  <<< POD 25mm!" : "  OK (>=25mm)"}`);
  }

  results.push({ id, name: D[id].name, parts: reverted, collisionsOk: newPairs.length === 0, cols, headroom: Object.fromEntries(cols.map(c => [c, headroomForCol(reverted, c).gap])) });
}
fs.writeFileSync(`${SCRATCH}/revert_hb_result.json`, JSON.stringify(results));
console.log("\nCELKEM bez novych kolizi:", results.filter(r => r.collisionsOk).length, "/", results.length);
console.log("CELKEM se zachovanou mezerou >=25mm:", results.filter(r => Object.values(r.headroom).every(g => g >= 25)).length, "/", results.length);
