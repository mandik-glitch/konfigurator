// Krok 1: zmerit Y_box_top, spojnice-horni horni hrany per noha, a identifikovat
// nohu u prepazky (car_body_*_B pozice) - vse na REALNE GLB geometrii, POVINNE
// pres scripts/2026-09-11_glb_resolver.js. Zadny zapis, jen mereni + report.
const fs = require("fs");
const THREE = require("three");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const R = require("/opt/konfigurator/scripts/2026-09-11_glb_resolver.js");

const id = process.argv[2];
const SCRATCH = "/tmp/claude-0/-opt-konfigurator/c0c788fb-0783-4d56-adb5-543ba6b0dda8/scratchpad";
const data = JSON.parse(fs.readFileSync(`${SCRATCH}/dumps/${id}.json`, "utf8"));
const parts = data.parts;

function realBox(p) {
  const glbPath = R.glbPath(p.part_id);
  if (!glbPath) throw new Error(`chybi GLB pro part_id=${p.part_id} role=${p.role}`);
  const m = parseGlbMesh(glbPath);
  m.position.set(...p.position);
  m.quaternion.set(...p.quaternion);
  m.scale.set(...p.scale);
  m.updateMatrixWorld(true);
  return new THREE.Box3().setFromObject(m);
}

const hasPodelnik = parts.some(p => String(p.role || "").startsWith("podelnik"));
console.log(`id=${id}: ma podelnik roli (horni blok)? ${hasPodelnik}`);
if (!hasPodelnik) { console.log("NEAPLIKOVATELNE - konec."); process.exit(0); }

// Y_box_top pres VSECHNY eurobox-* v cele sestave
const boxy = parts.filter(p => String(p.role || "").startsWith("eurobox"));
const boxyTop = boxy.map(p => realBox(p).max.y);
const yBoxTop = Math.max(...boxyTop);
console.log(`Y_box_top (max Y pres ${boxy.length} eurobox-* dilu, realna GLB geometrie) = ${yBoxTop.toFixed(4)}`);

// spojnice-horni* (vsechny varianty prefixu) - jedna na kazde noze
const spojnice = parts.filter(p => String(p.role || "").startsWith("spojnice-horni"));
console.log(`\nspojnice-horni* dily (${spojnice.length}):`);
const spojniceInfo = spojnice.map(p => {
  const b = realBox(p);
  return { role: p.role, z: p.position[2], yTop: b.max.y, yBottom: b.min.y };
});
spojniceInfo.sort((a, b) => a.z - b.z);
for (const s of spojniceInfo) {
  console.log(`  role=${s.role.padEnd(24)} Z=${s.z.toFixed(2).padStart(10)} yTop(real)=${s.yTop.toFixed(4)} yBottom(real)=${s.yBottom.toFixed(4)} rezerva_nad_Y_box_top=${(s.yTop - yBoxTop).toFixed(4)}`);
}

// identifikace nohy u prepazky pres car_body_*_B pozici (ne jen odhad)
const carBodyMap = JSON.parse(fs.readFileSync(`${SCRATCH}/car_bodies_map.json`, "utf8"));
const carBodyParts = parts.filter(p => String(p.part_id).startsWith("car_body_"));
console.log(`\ncar_body_* dily v datech (${carBodyParts.length}):`, carBodyParts.map(p => p.part_id));
const bPart = carBodyParts.find(p => (carBodyMap[p.part_id] || "").endsWith("_B.glb"));
if (!bPart) throw new Error("nenalezen car_body_*_B dil v datech - nelze urcit prepazku");
const KAT = "/opt/konfigurator/webapp/katalog/";
const bMesh = parseGlbMesh(KAT + carBodyMap[bPart.part_id]);
bMesh.position.set(...bPart.position);
bMesh.quaternion.set(...bPart.quaternion);
bMesh.scale.set(...bPart.scale);
bMesh.updateMatrixWorld(true);
const bBox = new THREE.Box3().setFromObject(bMesh);
console.log(`\ncar_body_B (${bPart.part_id} -> ${carBodyMap[bPart.part_id]}) real Z rozsah = [${bBox.min.z.toFixed(2)}, ${bBox.max.z.toFixed(2)}]`);

// noha u prepazky = ta s nejmensi vzdalenosti sveho Z od bBox Z-rozsahu (ne jen "prvni v poli")
console.log("\nvzdalenost kazde nohy (spojnice-horni Z) od car_body_B Z-rozsahu:");
for (const s of spojniceInfo) {
  const dist = s.z < bBox.min.z ? bBox.min.z - s.z : (s.z > bBox.max.z ? s.z - bBox.max.z : 0);
  s.distToB = dist;
  console.log(`  role=${s.role.padEnd(24)} Z=${s.z.toFixed(2).padStart(10)} vzdalenost_od_B=${dist.toFixed(2)}mm`);
}
const nohaUPrepazky = spojniceInfo.reduce((a, b) => a.distToB < b.distToB ? a : b);
console.log(`\n=> noha u prepazky (nejblizsi car_body_B): Z=${nohaUPrepazky.z}, role=${nohaUPrepazky.role}`);

console.log("\n=== KVALIFIKACE (noha != prepazka, rezerva >= 30mm) ===");
for (const s of spojniceInfo) {
  const jePrepazka = s.z === nohaUPrepazky.z;
  const rezerva = s.yTop - yBoxTop;
  const kvalifikuje = !jePrepazka && rezerva >= 30 - 1e-9;
  console.log(`  Z=${s.z.toFixed(2).padStart(10)} ${jePrepazka ? "[U PREPAZKY - VYNATO]" : ""} rezerva=${rezerva.toFixed(4)}mm kvalifikuje=${kvalifikuje}`);
}

fs.writeFileSync(`${SCRATCH}/rule10_measure_${id}.json`, JSON.stringify({
  id, hasPodelnik, yBoxTop, spojniceInfo, nohaUPrepazkyZ: nohaUPrepazky.z,
}, null, 1));

