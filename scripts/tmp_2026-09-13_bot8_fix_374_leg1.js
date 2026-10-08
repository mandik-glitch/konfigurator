// Oprava sestavy id=374 (Doblo K-075 A, boxy43-270x1-220x1-170x1-120x6):
// druha noha od prepazky (leg1, Z=-898.5) ma spatnou roli/geometrii -
// "zadni-svislice-dolni" (plny profil, jako u nohy0 u prepazky) misto
// spravneho "zadni-svislice-nad-zarezem" (vyrezova noha nad podbehem,
// s pricka-uzavreni-vyrezu + sloupek-pred-podbehem + spojnice-horni-uzavreni
// + vlastni sada uhelniku), chybi cela sada temhle dilum.
//
// Sablona se bere ze sourozence id=346 (jina typologie_varianta, ale
// STEJNA karoserie K-075 + STEJNE typologie_id/umisteni_id => stejne
// X/Z pozice noh, overeno primo v datech), ktery je JIZ technicky_ok=1
// (0 kolizi, Robertem schvaleny).
const fs = require("fs");
const THREE = require("three");
const R = require("/opt/konfigurator/scripts/2026-09-11_glb_resolver.js");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");

const SCRATCH = "/tmp/claude-0/-opt-konfigurator/68994686-5a6b-46d4-b3c7-14bc1f68c6ac/scratchpad";
const DATA = JSON.parse(fs.readFileSync(`${SCRATCH}/346_374_data.json`, "utf8"));
const d346 = DATA["346"];
const d374 = DATA["374"];

const LEG1_Z = -898.5;
const LEG_BUNDLE_ROLES = ["zadni-svislice-nad-zarezem", "zaslepka-zadni-svislice-nad-zarezem",
  "pricka-uzavreni-vyrezu", "sloupek-pred-podbehem", "spojnice-horni-uzavreni", "uhelnik-noha1"];

function partsNearZ(parts, role, z, tol) {
  return parts.filter(p => p.role === role && Math.abs(p.position[2] - z) < tol);
}

let template = [];
for (const role of LEG_BUNDLE_ROLES) {
  const tol = role === "uhelnik-noha1" ? 20 : 5;
  template.push(...partsNearZ(d346.parts, role, LEG1_Z, tol));
}
template = JSON.parse(JSON.stringify(template)); // deep clone

console.log(`=== Sablona z id=346, leg1 (Z=${LEG1_Z}), ${template.length} dilu ===`);
for (const p of template) console.log(`  ${p.role.padEnd(35)} ${String(p.part_id).padEnd(15)} pos=${JSON.stringify(p.position.map(v=>Math.round(v*10)/10))}`);

const WRONG_ROLES = ["zadni-svislice-dolni", "zaslepka-zadni-svislice-dolni"];
const removed = d374.parts.filter(p => WRONG_ROLES.includes(p.role) && Math.abs(p.position[2] - LEG1_Z) < 5);
console.log(`\n=== Odstranuji z id=374 (spatna leg1 varianta), ${removed.length} dilu ===`);
for (const p of removed) console.log(`  ${p.role.padEnd(35)} ${String(p.part_id).padEnd(15)} pos=${JSON.stringify(p.position.map(v=>Math.round(v*10)/10))}`);

const kept = d374.parts.filter(p => !(WRONG_ROLES.includes(p.role) && Math.abs(p.position[2] - LEG1_Z) < 5));
const corrected = kept.concat(template);
console.log(`\nid=374: ${d374.parts.length} dilu -> opraveno ${corrected.length} dilu (${removed.length} odebrano, ${template.length} pridano)`);

// === OVERENI: realna GLB geometrie, world-space Box3, plosny pairwise sken ===
function worldBox(p) {
  const glb = R.glbPath(p.part_id);
  if (!glb) return null;
  const mesh = parseGlbMesh(glb);
  mesh.position.set(p.position[0], p.position[1], p.position[2]);
  mesh.quaternion.set(p.quaternion[0], p.quaternion[1], p.quaternion[2], p.quaternion[3]);
  mesh.scale.set(p.scale[0], p.scale[1], p.scale[2]);
  mesh.updateMatrixWorld(true);
  return new THREE.Box3().setFromObject(mesh);
}

const measured = [];
let skippedKaroserie = 0, skippedNoGlb = 0;
for (const p of corrected) {
  if (R.jeKaroserie(p.part_id)) { skippedKaroserie++; continue; }
  const box = worldBox(p);
  if (!box) { skippedNoGlb++; console.log("CHYBI GLB pro:", p.part_id, p.role); continue; }
  measured.push({ p, box });
}
console.log(`\nZmereno: ${measured.length} dilu (karoserie vyloucena zamerne: ${skippedKaroserie}, chybejici GLB: ${skippedNoGlb})`);
if (skippedNoGlb > 0) { console.error("STOP: nezmeritelny dil - viz pravidlo '0 nalezu musi znamenat zmereno'"); process.exit(1); }

function overlap3(A, B) {
  return [
    Math.min(A.max.x, B.max.x) - Math.max(A.min.x, B.min.x),
    Math.min(A.max.y, B.max.y) - Math.max(A.min.y, B.min.y),
    Math.min(A.max.z, B.max.z) - Math.max(A.min.z, B.min.z),
  ];
}

const EPS = 0.5; // mm
const collisions = [];
for (let i = 0; i < measured.length; i++) {
  for (let j = i + 1; j < measured.length; j++) {
    const [ox, oy, oz] = overlap3(measured[i].box, measured[j].box);
    if (ox > EPS && oy > EPS && oz > EPS) collisions.push({ a: measured[i].p, b: measured[j].p, size: [ox, oy, oz] });
  }
}
console.log(`\nPocet paru zmerenych: ${measured.length * (measured.length - 1) / 2}`);
console.log(`Nalezeno prekryvu (pred filtrem znameho jevu profil+vlastni zaslepka): ${collisions.length}`);

function isKnownZaslepkaCase(a, b) {
  const ra = a.role || "", rb = b.role || "";
  return rb === "zaslepka-" + ra || ra === "zaslepka-" + rb;
}
const real = collisions.filter(c => !isKnownZaslepkaCase(c.a, c.b));
console.log(`Po filtru zname "profil+vlastni zaslepka" (SKILL.md bod 9, odsun~5.25mm): ${real.length}`);
for (const c of real) {
  console.log(`  KOLIZE: ${c.a.role}(${c.a.part_id})@Z=${c.a.position[2]} <-> ${c.b.role}(${c.b.part_id})@Z=${c.b.position[2]}  overlap=[${c.size.map(v => v.toFixed(2))}]`);
}

fs.writeFileSync(`${SCRATCH}/374_corrected.json`, JSON.stringify({ ...d374, parts: corrected }));
console.log(`\nVYSLEDEK: ${real.length === 0 ? "0 novych kolizi - OPRAVA VYPADA BEZPECNE" : "POZOR - najit a vyresit kolize pred zapisem"}`);
console.log("Ulozeno: 374_corrected.json");
