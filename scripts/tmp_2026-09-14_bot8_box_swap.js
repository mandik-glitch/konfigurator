// Vymena nejvyssiho eurobxu ve 2. sloupci (col1) za vyssi typ (Robertovo
// zadani). OPRAVENO: pivot vuci realne geometrii je posunuty NEJEN v Y,
// ale i v X/Z, a JINAK pro kazdy SKU (kazdy eurobox GLB ma svuj vlastni,
// nezavisly lokalni pocatek) - puvodni pokus resil jen Y offset a novy box
// tim padem "sklouzl" stranou do noh/leg profilu. Reseni: spocitat u
// KAZDEHO SKU offset (realny stred X, realny stred Z, realny SPODEK Y)
// vuci ulozene position PRI position=[0,0,0] (rigidni transform, na
// position nezavisle), a dosadit tak, aby novy box mel STEJNY realny
// stred X/Z a STEJNY realny spodek Y jako puvodni box na tehoz miste.
const fs = require("fs");
const THREE = require("three");
const R = require("/opt/konfigurator/scripts/2026-09-11_glb_resolver.js");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");

const SCRATCH = "/tmp/claude-0/-opt-konfigurator/68994686-5a6b-46d4-b3c7-14bc1f68c6ac/scratchpad";
const D = JSON.parse(fs.readFileSync(`${SCRATCH}/box_swap_fresh.json`, "utf8"));

const UPGRADE = { product_3788: "product_3793", product_3793: "product_3794" };

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
// offset = (realny stred X, realny stred Z, realny SPODEK Y) - position, pri position=[0,0,0]
// (rigidni transform -> nezavisle na tom, kam se to pak posune)
function refOffset(partId, quat, scale) {
  const b = worldBox({ part_id: partId, position: [0, 0, 0], quaternion: quat, scale });
  return { cx: (b.min.x + b.max.x) / 2, cz: (b.min.z + b.max.z) / 2, minY: b.min.y };
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
  const before = scan(parts);

  const col1 = parts.filter(p => (p.role || "").startsWith("eurobox-col1")).map(p => ({ p, box: worldBox(p) }));
  const maxY = Math.max(...col1.map(x => x.box.max.y));
  const topRole = col1.find(x => x.box.max.y === maxY).p.role;
  const targets = parts.filter(p => p.role === topRole);
  const oldSku = targets[0].part_id;
  const newSku = UPGRADE[oldSku];
  if (!newSku) { console.log(`id=${id}: top role=${topRole} sku=${oldSku} neni v UPGRADE mape`); continue; }

  const after = parts.map(p => p);
  const changed = [];
  for (const t of targets) {
    const idx = after.indexOf(t);
    const oldBox = worldBox(t);
    const desired = { cx: (oldBox.min.x + oldBox.max.x) / 2, cz: (oldBox.min.z + oldBox.max.z) / 2, minY: oldBox.min.y };
    const off = refOffset(newSku, t.quaternion, t.scale);
    const newPos = [desired.cx - off.cx, desired.minY - off.minY, desired.cz - off.cz];
    const newPart = { ...t, part_id: newSku, position: newPos };
    after[idx] = newPart;
    const newBox = worldBox(newPart);
    changed.push({ z: t.position[2], oldBox, newBox });
  }

  const afterScan = scan(after);
  const newPairs = [...afterScan.pairs.keys()].filter(k => !before.pairs.has(k));
  console.log(`id=${id}: ${topRole} ${oldSku}->${newSku} (${targets.length}x)`);
  for (const c of changed) {
    console.log(`   stary X=[${c.oldBox.min.x.toFixed(1)},${c.oldBox.max.x.toFixed(1)}] Y=[${c.oldBox.min.y.toFixed(1)},${c.oldBox.max.y.toFixed(1)}] Z=[${c.oldBox.min.z.toFixed(1)},${c.oldBox.max.z.toFixed(1)}]`);
    console.log(`   novy  X=[${c.newBox.min.x.toFixed(1)},${c.newBox.max.x.toFixed(1)}] Y=[${c.newBox.min.y.toFixed(1)},${c.newBox.max.y.toFixed(1)}] Z=[${c.newBox.min.z.toFixed(1)},${c.newBox.max.z.toFixed(1)}]`);
  }
  console.log(`   kolize pred=${before.n} po=${afterScan.n} nove_pary=${newPairs.length ? JSON.stringify(newPairs) : "zadne"}`);
  if (newPairs.length) { console.log("   STOP - nova kolize, needitovano"); continue; }
  results.push({ id, parts: after, oldSku, newSku, topRole, count: targets.length });
}
fs.writeFileSync(`${SCRATCH}/box_swap_result.json`, JSON.stringify(results));
console.log(`\nCelkem pripraveno k zapisu: ${results.length}/${Object.keys(D).length}`);
