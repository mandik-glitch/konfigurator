// Ploche vystrihove vzory dilu obkladu ("jak by lezely na stole pred
// montazi") - Robert 2026-09-12, pres bot3: "Nechci vidět render chci
// vidět geometrii... Obrysy těch dílů jako souřadnice... Rozvinuté do
// roviny... Do JSON, ať to můžu vykreslit."
//
// Pro kazdy dil (podlaha, L, R_D, B): vnejsi obrys jako pole 2D bodu v
// mm. Podlaha uz je rovinna (vodorovny rez, viz 2026-09-11_karoserie_
// podlaha_obrys.js, znovupouzito). Steny/prepazka NEJSOU rozvinute
// (geodesicky) - proste PROMITNUTY na dominantni rovinu (Robert: "když
// nepůjde rozvinout do roviny bez deformace, prostě ho promítni a jdi
// dál"), zadna analyza zakriveni.
//
// Otvory (dvereni, podbeh) se NEPODARILO ziskat hranicni-hranovou
// technikou - _L/_R_D/_B jsou uzavrene (watertight) 2-manifoldy, zadna
// volna hrana v nich neexistuje (overeno primo, ne predpoklad). Vnejsi
// obrys je proto KONVEXNI OBAL vsech vertexu (stejna technika jako
// podlaha), `holes` zustava prazdne - viz komentar u flattenPanel().
//
// Prototyp jen pro K-075. Pouziti:
//   node scripts/2026-09-12_karoserie_ploche_vzory.js car_bodies/<base> [-o vystup.json]
const fs = require("fs");
const path = require("path");
const KAT = "/opt/konfigurator/webapp/katalog/car_bodies/";
const { computeOutline, convexHull } = require("./2026-09-11_karoserie_podlaha_obrys.js");

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
  const indices = prim.indices != null ? readAccessor(prim.indices) : null;
  const triCount = indices ? indices.length / 3 : positions.length / 9;
  const faces = [];
  for (let t = 0; t < triCount; t++) {
    faces.push(indices ? [indices[t * 3], indices[t * 3 + 1], indices[t * 3 + 2]] : [t * 3, t * 3 + 1, t * 3 + 2]);
  }
  return { positions, faces };
}

// POZOR - zjisteno pri stavbe: _L/_R_D/_B jsou UZAVRENE (watertight)
// 2-manifoldy - KAZDA hrana site patri PRESNE DVEMA trojuhelnikum, na
// vsech urovnich zaokrouhleni (overeno 0-3 des. mist). Zadna volna
// hranicni hrana nikde neexistuje, tedy ani kolem pripadneho dvereniho
// otvoru - neni to chyba klicovani podle pozice, je to fakt o datech.
// Boundary-edge technika (funkcni pro plocha rezy jinde v projektu) tu
// proto NEJDE POUZIT k nalezeni otvoru ani obrysu. Misto toho: vnejsi
// obrys = KONVEXNI OBAL vsech vertexu (stejna technika jako podlaha),
// otvory se NEDETEKUJI (prazdny seznam) - Robert: "co nesedne, uvidíme
// na výkresu", tohle je presne ten pripad.
function flattenPanel(base, suf) {
  const { positions } = readGlbFull(KAT + base + suf + ".glb");
  const n = positions.length / 3;
  let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity, minZ = Infinity, maxZ = -Infinity;
  for (let i = 0; i < n; i++) {
    const x = positions[i * 3], y = positions[i * 3 + 1], z = positions[i * 3 + 2];
    if (x < minX) minX = x; if (x > maxX) maxX = x;
    if (y < minY) minY = y; if (y > maxY) maxY = y;
    if (z < minZ) minZ = z; if (z > maxZ) maxZ = z;
  }
  const spread = { x: maxX - minX, y: maxY - minY, z: maxZ - minZ };
  const dropAxis = spread.x <= spread.y && spread.x <= spread.z ? "x" : (spread.y <= spread.z ? "y" : "z");
  const [ax1, ax2] = ["x", "y", "z"].filter(a => a !== dropAxis);
  const idx = { x: 0, y: 1, z: 2 };
  const pts2d = [];
  for (let i = 0; i < n; i++) pts2d.push([positions[i * 3 + idx[ax1]], positions[i * 3 + idx[ax2]]]);
  const outer = convexHull(pts2d);
  return { axes: [ax1, ax2], droppedAxis: dropAxis, outer, holes: [], holesNote: "nedetekovano - karoserie je uzavreny 2-manifold, zadna volna hrana k nalezeni" };
}

const args = process.argv.slice(2);
const baseArg = args.find(a => !a.startsWith("-"));
const outIdx = args.indexOf("-o");
const outFile = outIdx >= 0 ? args[outIdx + 1] : null;
if (!baseArg) { console.error("Pouziti: node ... car_bodies/<base> [-o vystup.json]"); process.exit(1); }
const base = baseArg.replace(/^car_bodies\//, "");

const floorRaw = computeOutline(base);
const floorMain = floorRaw.loops[0];

const result = {
  base,
  units: "mm",
  note: "steny/prepazka jsou PROMITNUTE (ne geodesicky rozvinute) - viz axes/droppedAxis u kazdeho dilu",
  panels: {
    podlaha: { axes: ["x", "z"], outer: floorMain.points, holes: [] },
    L: flattenPanel(base, "_L"),
    R_D: flattenPanel(base, "_R_D"),
    B: flattenPanel(base, "_B"),
  },
};

const outPath = outFile || path.join("/tmp", `${base.replace(/\//g, "_")}_ploche_vzory.json`);
fs.writeFileSync(outPath, JSON.stringify(result));
console.log(outPath);
for (const [k, p] of Object.entries(result.panels)) {
  console.log(`  ${k}: osy=${p.axes.join(",")}, vnejsi obrys=${p.outer.length} bodu, otvory=${p.holes.length} (${p.holes.map(h => h.length + "b").join(", ")})`);
}
