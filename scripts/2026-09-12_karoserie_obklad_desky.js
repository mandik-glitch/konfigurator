// Obklad karoserie ("desky prekliizky") - Robert 2026-09-12, pres bot3:
// "zkus vyrobit tvary, stejné geometrické platy, kterými jsme jakože
// obložili stěny karoserie a podlahu... ony ty platy překližky se dají
// mírně ohýbat, takže se na tu skutečnou karoserii napasovat" - takze NE
// plocha proloz enim rovinou (zahozeny prvni napad), ale SKUTECNA
// plocha _L/_R_D/_B, odsazena dovnitr (do nakladoveho prostoru) o svou
// tloustku - presne jak realny plat prekliizky prilehne na zakrivenou
// stenu.
//
// Prototyp JEN pro K-075 (Fiat Doblo), Robert vyslovne "zadny katalog,
// jedna karoserie". Zadny vypocet zakriveni/deleni na kusy (Robert:
// "zahod to mereni dvojiho zakriveni... zkus to a uvidis").
//
// Pouziti: node scripts/2026-09-12_karoserie_obklad_desky.js car_bodies/<base> [--json] [--tloustka=4]
const fs = require("fs");
const KAT = "/opt/konfigurator/webapp/katalog/car_bodies/";
const DEFAULT_TLOUSTKA_MM = 4;

function readGlbFull(glbPath) {
  const buf = fs.readFileSync(glbPath);
  let offset = 12, json = null, binChunk = null;
  while (offset < buf.length) {
    const chunkLen = buf.readUInt32LE(offset);
    const chunkType = buf.readUInt32LE(offset + 4);
    const chunkData = buf.slice(offset + 8, offset + 8 + chunkLen);
    if (chunkType === 0x4e4f534a) json = JSON.parse(chunkData.toString("utf8"));
    else if (chunkType === 0x004e4942) binChunk = chunkData;
    offset += 8 + chunkLen;
  }
  const prim = json.meshes[0].primitives[0];
  function readAccessor(accIdx) {
    const acc = json.accessors[accIdx];
    const bv = json.bufferViews[acc.bufferView];
    const byteOffset = (bv.byteOffset || 0) + (acc.byteOffset || 0);
    const numComp = { SCALAR: 1, VEC2: 2, VEC3: 3, VEC4: 4 }[acc.type];
    if (acc.componentType === 5126) return new Float32Array(binChunk.buffer, binChunk.byteOffset + byteOffset, acc.count * numComp);
    if (acc.componentType === 5123) return new Uint16Array(binChunk.buffer, binChunk.byteOffset + byteOffset, acc.count * numComp);
    if (acc.componentType === 5125) return new Uint32Array(binChunk.buffer, binChunk.byteOffset + byteOffset, acc.count * numComp);
    throw new Error("neznamy componentType " + acc.componentType);
  }
  const positions = readAccessor(prim.attributes.POSITION);
  const normals = prim.attributes.NORMAL != null ? readAccessor(prim.attributes.NORMAL) : null;
  const indices = prim.indices != null ? readAccessor(prim.indices) : null;
  return { positions, normals, indices };
}

// Odsazeni KAZDEHO vertexu podel jeho vlastni normaly smerem DOVNITR
// (do nakladoveho prostoru - normala u tehle geometrie miri UZ do
// interieru, overeno mereno 2026-09-11 pri hledani smeru odsazeni pro
// karoserie-odrazy) o `tloustka` mm. Zadne prolozeni rovinou, zadne
// oriznuti - cela skutecna plocha, jen posunuta.
function offsetPanel(glbData, tloustka) {
  const { positions, normals, indices } = glbData;
  if (!normals) throw new Error("chybi NORMAL atribut, nelze odsadit");
  const n = positions.length / 3;
  const outPos = new Float32Array(positions.length);
  for (let i = 0; i < n; i++) {
    outPos[i * 3] = positions[i * 3] + normals[i * 3] * tloustka;
    outPos[i * 3 + 1] = positions[i * 3 + 1] + normals[i * 3 + 1] * tloustka;
    outPos[i * 3 + 2] = positions[i * 3 + 2] + normals[i * 3 + 2] * tloustka;
  }
  const faces = [];
  const triCount = indices ? indices.length / 3 : n / 3;
  for (let t = 0; t < triCount; t++) {
    if (indices) faces.push([indices[t * 3], indices[t * 3 + 1], indices[t * 3 + 2]]);
    else faces.push([t * 3, t * 3 + 1, t * 3 + 2]);
  }
  const r2 = (v) => Math.round(v * 100) / 100; // 0.01mm staci, drzi JSON male
  const verts = [];
  for (let i = 0; i < n; i++) verts.push([r2(outPos[i * 3]), r2(outPos[i * 3 + 1]), r2(outPos[i * 3 + 2])]);
  return { vertCount: n, triCount, verts, faces };
}

const args = process.argv.slice(2);
const asJson = args.includes("--json");
const tloustkaArg = args.find(a => a.startsWith("--tloustka="));
const tloustka = tloustkaArg ? parseFloat(tloustkaArg.split("=")[1]) : DEFAULT_TLOUSTKA_MM;
const baseArg = args.find(a => !a.startsWith("--"));
if (!baseArg) { console.error("Pouziti: node ... car_bodies/<base> [--json] [--tloustka=4]"); process.exit(1); }
const base = baseArg.replace(/^car_bodies\//, "");

let result;
try {
  const panels = {};
  for (const [key, suf] of [["L", "_L"], ["R_D", "_R_D"], ["B", "_B"]]) {
    const glbData = readGlbFull(KAT + base + suf + ".glb");
    panels[key] = offsetPanel(glbData, tloustka);
  }
  result = { ok: true, base, tloustka_mm: tloustka, panels };
} catch (e) {
  result = { ok: false, error: e.message };
}

if (asJson) {
  console.log(JSON.stringify(result));
} else {
  console.log(`\n=== ${base} - obklad, tloustka=${tloustka}mm ===`);
  if (!result.ok) console.log("CHYBA:", result.error);
  else for (const [k, p] of Object.entries(result.panels)) {
    console.log(`  ${k}: ${p.vertCount} vertexu, ${p.triCount} trojuhelniku`);
  }
}
