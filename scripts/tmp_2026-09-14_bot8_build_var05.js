// Sestaveni nove varianty "05" (A i B) = presna kopie horniho bloku C-06
// (id=347, "dve pasma, plne vyplne, s policí" - nejbohatsi provedeni,
// katalogovy typ horni_blok_varianty.id=7/kod=06) + vlastni box-specificke
// dily A/B donora (383/380, jejich "04" - stejny box layout jako vsechny
// ostatni horni_blok varianty teze verze/typologie_varianta).
const fs = require("fs");
const THREE = require("three");
const R = require("/opt/konfigurator/scripts/2026-09-11_glb_resolver.js");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");

const SCRATCH = "/tmp/claude-0/-opt-konfigurator/68994686-5a6b-46d4-b3c7-14bc1f68c6ac/scratchpad";
const D = JSON.parse(fs.readFileSync(`${SCRATCH}/var05_new.json`, "utf8"));

const BOX_PREFIXES = ["nosnik-col", "spojnice-col", "eurobox-col", "logo-ochrana"];
const isBoxSpecific = (p) => BOX_PREFIXES.some(pre => (p.role || "").startsWith(pre)) || R.jeKaroserie(p.part_id);

function build(donorId, refId) {
  const donor = D[donorId].parts;
  const ref = D[refId].parts;
  const boxParts = donor.filter(isBoxSpecific);
  const skeletonParts = ref.filter(p => !isBoxSpecific(p));
  // sanity: zadna box-role v ref skeletonu, zadna skeleton-role v donor boxParts (kontrola disjunktnosti)
  const skelRoles = new Set(skeletonParts.map(p => p.role));
  const boxRoles = new Set(boxParts.map(p => p.role));
  for (const r of skelRoles) if (boxRoles.has(r)) throw new Error("kolize rolí mezi skeletonem a boxem: " + r);
  return boxParts.concat(skeletonParts);
}

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
function overlap3(A, B) {
  return [Math.min(A.max.x, B.max.x) - Math.max(A.min.x, B.min.x), Math.min(A.max.y, B.max.y) - Math.max(A.min.y, B.min.y), Math.min(A.max.z, B.max.z) - Math.max(A.min.z, B.min.z)];
}
function scan(parts) {
  const m = parts.filter(p => !R.jeKaroserie(p.part_id)).map(p => ({ p, box: worldBox(p) }));
  const pairs = new Map(); let n = 0;
  for (let i = 0; i < m.length; i++) for (let j = i + 1; j < m.length; j++) {
    const [ox, oy, oz] = overlap3(m[i].box, m[j].box);
    if (ox > 0.5 && oy > 0.5 && oz > 0.5) { n++; pairs.set(m[i].p.role + "|" + m[j].p.role, [ox, oy, oz]); }
  }
  return { n, pairs, dilu: m.length };
}

// referencni "zname" prekryvy = presne ty, co uz existuji v 347 samotne
// (schvalena C-06) - pouzijeme JI jako zdroj pravdy misto rucniho seznamu.
const refScan347 = scan(D[347].parts);
function isKnownFrom347(key, val) {
  if (!refScan347.pairs.has(key)) return false;
  const ref = refScan347.pairs.get(key);
  return Math.abs(val[0] - ref[0]) < 1 && Math.abs(val[1] - ref[1]) < 1 && Math.abs(val[2] - ref[2]) < 1;
}

const CONFIGS = [
  { label: "A-05", donor: 383, out: null },
  { label: "B-05", donor: 380, out: null },
];
for (const cfg of CONFIGS) {
  const parts = build(cfg.donor, 347);
  const s = scan(parts);
  const unknown = [];
  for (const [k, v] of s.pairs) {
    // vynech prekryvy, ktere existuji i UVNITR samotneho donoru (383/380) uz predtim - nejsou nove zpusobene timhle sestavenim
    if (!isKnownFrom347(k, v)) unknown.push([k, v]);
  }
  console.log(`${cfg.label}: dilu=${parts.length} kolizi_celkem=${s.n} neznamych=${unknown.length}`);
  for (const [k, v] of unknown) console.log("   NEZNAMY:", k, JSON.stringify(v.map(x => +x.toFixed(1))));
  cfg.out = { parts, ok: unknown.length === 0, dilu: parts.length };
}
fs.writeFileSync(`${SCRATCH}/var05_build.json`, JSON.stringify(CONFIGS));
