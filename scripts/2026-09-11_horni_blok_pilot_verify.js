// Nezavisle all-pairs overeni vysledku 2026-09-05_horni_ram.js (bot10,
// zadani bot8 2026-09-11 - "nepouzivej naivni odvozeni <part_id>.glb").
// Replikuje METODIKU bot8 pouzitou na referencni sestave 337: VSECHNY
// dvojice dilu ve vysledne (upravene) sestave, box-overlap na realne
// GLB geometrii, klasifikace nalezu podle presne mm hodnoty nejmensi
// osy (7.000mm = navrhovy ZASUN do drazky, ne kolize; cokoli jineho
// >1mm = k prozkoumani).
const fs = require("fs");
const path = require("path");
const THREE = require("three");
const { parseGlbMesh } = require("./2026-08-19_glb_real_geometry.js");

const KATALOG_DIR = "/opt/konfigurator/webapp/katalog";
// Kompletni, overene mapovani pro celou tuhle produktovou rodinu (viz
// 2026-09-11 joint-count prace + car_bodies pro car_body_*).
const GLB_MAP = {
  "Object_7": "Object_7.glb",
  "product_3045": "product_2895.glb",
  "product_3071": "product_3071.glb",
  "product_3788": "product_3788.glb",
  "product_3793": "product_3793.glb",
  "product_3794": "product_3794.glb",
  "product_3795": "product_3795.glb",
  "product_3939": "deska_mdf_seda_8.glb",
};

const [, , resultPath] = process.argv;
const result = JSON.parse(fs.readFileSync(resultPath, "utf8"));
const parts = result.upraveneParts.filter(p => !String(p.part_id).startsWith("car_body_"));

const geoCache = new Map();
function getGeo(glbFile) {
  if (!geoCache.has(glbFile)) {
    const file = path.join(KATALOG_DIR, glbFile);
    geoCache.set(glbFile, fs.existsSync(file) ? parseGlbMesh(file).geometry : null);
  }
  return geoCache.get(glbFile);
}

const boxes = [];
const missing = new Set();
parts.forEach(p => {
  const glb = GLB_MAP[p.part_id];
  if (!glb) { missing.add(p.part_id); return; }
  const geo = getGeo(glb);
  if (!geo) { missing.add(p.part_id + " (" + glb + " chybi na disku)"); return; }
  const obj = new THREE.Mesh(geo);
  obj.position.fromArray(p.position);
  obj.quaternion.fromArray(p.quaternion);
  obj.scale.fromArray(p.scale || [1, 1, 1]);
  obj.updateMatrixWorld(true);
  boxes.push({ role: p.role || p.part_id, box: new THREE.Box3().setFromObject(obj) });
});

if (missing.size) console.log("POZOR - nenamapovane part_id (vypadly z kontroly):", [...missing]);

let pairsCompared = 0;
const findings = []; // [role_a, role_b, [px,py,pz], minAxis]
for (let i = 0; i < boxes.length; i++) {
  for (let j = i + 1; j < boxes.length; j++) {
    pairsCompared++;
    const A = boxes[i].box, B = boxes[j].box;
    const px = Math.min(A.max.x, B.max.x) - Math.max(A.min.x, B.min.x);
    const py = Math.min(A.max.y, B.max.y) - Math.max(A.min.y, B.min.y);
    const pz = Math.min(A.max.z, B.max.z) - Math.max(A.min.z, B.min.z);
    if (px <= 0 || py <= 0 || pz <= 0) continue; // netykaji se vubec
    const minAxis = Math.min(px, py, pz);
    if (minAxis <= 1.0) continue; // <=1mm neni nalez (numericka tolerance)
    findings.push({ a: boxes[i].role, b: boxes[j].role, prunik: [px, py, pz].map(v => Math.round(v * 1000) / 1000), minAxis: Math.round(minAxis * 1000) / 1000 });
  }
}

console.log(`dilu porovnavano: ${boxes.length} (${missing.size} nenamapovano)`);
console.log(`paru porovnano: ${pairsCompared}`);
console.log(`nalezu >1mm: ${findings.length}`);

const byMinAxis = new Map();
findings.forEach(f => { byMinAxis.set(f.minAxis, (byMinAxis.get(f.minAxis) || 0) + 1); });
console.log("rozpis podle nejmensi osy (mm -> pocet):");
[...byMinAxis.entries()].sort((a, b) => a[0] - b[0]).forEach(([mm, n]) => console.log(`  ${mm.toFixed(3)} mm : ${n}x`));

const neocekavane = findings.filter(f => Math.abs(f.minAxis - 7) > 0.05);
console.log(`\nnalezy MIMO ocekavany zasun 7.000mm: ${neocekavane.length}`);
neocekavane.forEach(f => console.log(`  ${f.a} x ${f.b} : min=${f.minAxis}mm  prunik=[${f.prunik}]`));
