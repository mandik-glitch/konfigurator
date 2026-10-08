// Kompletni prestavba horniho bloku od nuly (Robert: "stare smazme, bude
// to rychlejsi nez opravovani") - smaze VSECHNY podelnik-*/pricka-(spodni|
// horni|police)-*/vypln-* role z A/B sestavy a nahradi 1:1 kopii ze
// spravneho C-vzoru (napárováno podle OBSAHU, ne cisla - A/B a C maji po
// vyrazeni "02-vyztuha" jinou ciselnou radu). Box-specificke dily
// (nosnik-col*/spojnice-col*/eurobox-col*/logo-ochrana*) i noha/leg
// zustavaji VLASTNI (nedotcene) - obsahuji uz opravene 170mm vymeny.
const fs = require("fs");
const THREE = require("three");
const R = require("/opt/konfigurator/scripts/2026-09-11_glb_resolver.js");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");

const D = JSON.parse(fs.readFileSync("/tmp/claude-0/-opt-konfigurator/68994686-5a6b-46d4-b3c7-14bc1f68c6ac/scratchpad/rebuild_hb.json", "utf8"));

const HB_PREFIXES = ["podelnik-", "pricka-spodni", "pricka-horni", "pricka-police", "vypln-"];
const isHornibBlok = (p) => HB_PREFIXES.some(pre => (p.role || "").startsWith(pre));

const PAIRS = [
  { a: 369, b: 370, c: 344, label: "01-ZAKLAD" },
  { a: 382, b: 379, c: 343, label: "02-police-pricky" },
  { a: 383, b: 380, c: 345, label: "03-plne-vyplne-bez-police" },
  { a: 384, b: 385, c: 347, label: "04-plne-vyplne-s-police" },
];

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

const results = [];
for (const { a, b, c, label } of PAIRS) {
  const hbTemplate = D[c].parts.filter(isHornibBlok).map(p => JSON.parse(JSON.stringify(p)));
  console.log(`\n=== varianta ${label} (C=${c}, ${hbTemplate.length} dilu horniho bloku) ===`);
  for (const id of [a, b]) {
    const orig = D[id].parts;
    const removed = orig.filter(isHornibBlok);
    const kept = orig.filter(p => !isHornibBlok(p));
    const after = kept.concat(hbTemplate.map(p => ({ ...p })));

    const before = scan(kept); // srovnej proti stavu BEZ hb vubec, aby vynikly VSECHNY kolize sablony
    const afterScan = scan(after);
    const newPairs = [...afterScan.pairs.keys()].filter(k => !before.pairs.has(k));
    console.log(`id=${id}: odebrano ${removed.length}, pridano ${hbTemplate.length}. dilu ${orig.length}->${after.length}. kolize bez HB=${before.n} s HB=${afterScan.n} nove=${newPairs.length}`);
    for (const k of newPairs) console.log("   ", k, JSON.stringify(afterScan.pairs.get(k).map(v => +v.toFixed(1))));
    results.push({ id, parts: after, ok: newPairs.length === 0, c, removedCount: removed.length, addedCount: hbTemplate.length });
  }
}
fs.writeFileSync("/tmp/claude-0/-opt-konfigurator/68994686-5a6b-46d4-b3c7-14bc1f68c6ac/scratchpad/rebuild_hb_result.json", JSON.stringify(results));
console.log("\nCELKEM OK:", results.filter(r => r.ok).length, "/", results.length);
