// Vodorovne rezy karoserii = podklad pro "obrys podlahy auta" ve sferickych
// pohledech (Robert, 2026-09-04: "pod regalama minimalne podlahu, soucasti
// sferickych pohledu bude obrys podlahy auta"; obrys se ma teprve
// nadefinovat podle navrhu).
//
// PROC REZ A NE HOTOVA GEOMETRIE: karoserie v katalogu NEMA podlahu jako
// mesh - kazde auto ma jen tri dily (_L leva stena, _R_D prava stena+dvere,
// _B celni prepazka). Obrys podlahy se proto musi ODVODIT, a jedina poctiva
// cesta je rez skutecnou geometrii sten.
//
// Skript spocita prusecik trojuhelniku vsech tri sten s VODOROVNOU rovinou
// Y=h pro nekolik vysek h a vypise segmenty v pudorysu (X,Z v mm).
// Ruzne vysky davaji ruzne kandidaty na "obrys":
//   h maly (5-20mm)   - obrys tesne nad podlahou = skutecna pouzitelna plocha
//   h stredni (300mm) - uz zahrnuje vybouleni podbehu kola
//   h velky (600mm+)  - obrys ve vysce regalu, podbeh uz zpravidla konci
//
// READ-ONLY. Nic nemeni, jen mer i a vypisuje.
//
// Pouziti:
//   node scripts/2026-09-04_floor_outline_sections.js <base> [--heights 5,150,300,600] [--out out.json]
//   (base = nazev bez pripony, napr. "Opel_Vivaro_OP18_2019-")

const fs = require("fs");
const THREE = require("/opt/konfigurator/node_modules/three");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");

const KAT = "/opt/konfigurator/webapp/katalog/car_bodies/";
const base = process.argv[2];
const hIdx = process.argv.indexOf("--heights");
const HEIGHTS = hIdx > 0 ? process.argv[hIdx + 1].split(",").map(Number) : [5, 150, 300, 600];
const outIdx = process.argv.indexOf("--out");
const outPath = outIdx > 0 ? process.argv[outIdx + 1] : null;

if (!base) { console.error("usage: node 2026-09-04_floor_outline_sections.js <base> [--heights a,b] [--out f.json]"); process.exit(2); }

// prusecik jednoho trojuhelniku s rovinou y=h -> usecka (nebo nic)
function triPlane(a, b, c, h) {
  const pts = [];
  const edges = [[a, b], [b, c], [c, a]];
  for (const [p, q] of edges) {
    const dp = p.y - h, dq = q.y - h;
    if ((dp > 0 && dq > 0) || (dp < 0 && dq < 0)) continue;
    if (dp === 0 && dq === 0) continue;          // hrana lezi v rovine - preskoc
    const t = dp / (dp - dq);
    if (!isFinite(t)) continue;
    pts.push([p.x + (q.x - p.x) * t, p.z + (q.z - p.z) * t]);
  }
  if (pts.length < 2) return null;
  return [pts[0][0], pts[0][1], pts[1][0], pts[1][1]];
}

function sectionOf(mesh, h) {
  const geo = mesh.geometry;
  const pos = geo.attributes.position;
  const idx = geo.index;
  const triCount = idx ? idx.count / 3 : pos.count / 3;
  const vA = new THREE.Vector3(), vB = new THREE.Vector3(), vC = new THREE.Vector3();
  const segs = [];
  for (let t = 0; t < triCount; t++) {
    let ia, ib, ic;
    if (idx) { ia = idx.getX(t * 3); ib = idx.getX(t * 3 + 1); ic = idx.getX(t * 3 + 2); }
    else { ia = t * 3; ib = t * 3 + 1; ic = t * 3 + 2; }
    vA.fromBufferAttribute(pos, ia).applyMatrix4(mesh.matrixWorld);
    vB.fromBufferAttribute(pos, ib).applyMatrix4(mesh.matrixWorld);
    vC.fromBufferAttribute(pos, ic).applyMatrix4(mesh.matrixWorld);
    const s = triPlane(vA, vB, vC, h);
    if (s) segs.push(s.map((v) => +v.toFixed(1)));
  }
  return segs;
}

const casti = ["_L", "_R_D", "_B"];
const meshe = {};
for (const c of casti) {
  const f = KAT + base + c + ".glb";
  if (!fs.existsSync(f)) { console.error("chybi " + f); continue; }
  const m = parseGlbMesh(f);
  m.updateMatrixWorld(true);
  meshe[c] = m;
}
if (!Object.keys(meshe).length) { console.error("zadny GLB pro " + base); process.exit(1); }

const vysledek = { base, rezy: [] };
console.log("karoserie: " + base);
for (const h of HEIGHTS) {
  const perCast = {};
  let vse = [];
  for (const c of Object.keys(meshe)) {
    const segs = sectionOf(meshe[c], h);
    perCast[c] = segs;
    vse = vse.concat(segs);
  }
  // rozsah pudorysu
  const xs = vse.flatMap((s) => [s[0], s[2]]), zs = vse.flatMap((s) => [s[1], s[3]]);
  const rec = {
    h,
    segmentu: vse.length,
    per_cast: Object.fromEntries(Object.entries(perCast).map(([k, v]) => [k, v.length])),
    rozsah_x: xs.length ? [Math.min(...xs), Math.max(...xs)] : null,
    rozsah_z: zs.length ? [Math.min(...zs), Math.max(...zs)] : null,
    sirka: xs.length ? +(Math.max(...xs) - Math.min(...xs)).toFixed(0) : null,
    delka: zs.length ? +(Math.max(...zs) - Math.min(...zs)).toFixed(0) : null,
    segmenty: vse,
  };
  vysledek.rezy.push(rec);
  console.log("  h=" + String(h).padStart(4) + "mm  segmentu=" + String(vse.length).padStart(5) +
    "  sirka=" + String(rec.sirka).padStart(5) + "mm  delka=" + String(rec.delka).padStart(5) + "mm" +
    "  (L=" + rec.per_cast._L + " R_D=" + rec.per_cast._R_D + " B=" + (rec.per_cast._B ?? 0) + ")");
}
if (outPath) { fs.writeFileSync(outPath, JSON.stringify(vysledek)); console.log("JSON -> " + outPath); }
