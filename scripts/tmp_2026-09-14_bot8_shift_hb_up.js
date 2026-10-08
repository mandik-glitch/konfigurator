// Posun CELEHO horniho bloku (spodni + horni pasmo, vsechny podelniky/
// pricky/vyplne vc. dorazu) nahoru o SHIFT mm jako TUHY presun (jen
// position.y += SHIFT, zadna zmena scale/quaternion - vsechny vnitrni
// vztahy uvnitr bloku zustavaji stejne). Cil: vytvorit dost mista nad
// nejvyssim boxem 2. sloupce PRED opakovanym pokusem o vymenu za vyssi
// box (Robert: min. 30mm mezera nad boxem).
const fs = require("fs");
const THREE = require("three");
const R = require("/opt/konfigurator/scripts/2026-09-11_glb_resolver.js");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");

const SCRATCH = "/tmp/claude-0/-opt-konfigurator/68994686-5a6b-46d4-b3c7-14bc1f68c6ac/scratchpad";
const D = JSON.parse(fs.readFileSync(`${SCRATCH}/hb_shift_fresh.json`, "utf8"));
const SHIFT = 20;

const HB_PREFIXES = ["podelnik-", "pricka-spodni", "pricka-horni", "pricka-police", "vypln-"];
const isHornibBlok = (p) => HB_PREFIXES.some(pre => (p.role || "").startsWith(pre));

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
for (const id of Object.keys(D).map(Number)) {
  const parts = D[id].parts;
  const hbRoles = new Set(parts.filter(isHornibBlok).map(p => p.role));
  console.log(`id=${id}: posunuji role: ${[...hbRoles].sort().join(", ")}`);
  const before = scan(parts);
  const after = parts.map(p => isHornibBlok(p) ? { ...p, position: [p.position[0], p.position[1] + SHIFT, p.position[2]] } : p);
  const afterScan = scan(after);
  const newPairs = [...afterScan.pairs.keys()].filter(k => !before.pairs.has(k));
  console.log(`   kolize pred=${before.n} po=${afterScan.n} nove_pary=${newPairs.length ? JSON.stringify(newPairs) : "zadne"}`);
  for (const k of newPairs) console.log("      ", k, JSON.stringify(afterScan.pairs.get(k).map(v => +v.toFixed(1))));
  results.push({ id, parts: after, ok: newPairs.length === 0 });
}
fs.writeFileSync(`${SCRATCH}/hb_shift_result.json`, JSON.stringify(results));
console.log("\nOK:", results.filter(r => r.ok).length, "/", results.length);
