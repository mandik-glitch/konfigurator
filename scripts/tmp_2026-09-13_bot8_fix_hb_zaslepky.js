// Oprava 5 sester (376 B/00, 375 A/01, 377 B/01, 369 A/02-ZAKLAD, 370 B/02-ZAKLAD):
// chybi zaslepka-cap + zaslepka-predni-svislice presne na noze1 (Z=-898.5).
// Sablona (identicka napric C00/C01/C02, overeno): pos=[-636.5,1223,-898.5]
// resp [-387.5,1223,-898.5], quat=[0.7071,0,0,0.7071], scale=[1,1,1].
const fs = require("fs");
const THREE = require("three");
const R = require("/opt/konfigurator/scripts/2026-09-11_glb_resolver.js");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");

const SCRATCH = "/tmp/claude-0/-opt-konfigurator/68994686-5a6b-46d4-b3c7-14bc1f68c6ac/scratchpad";
const D = JSON.parse(fs.readFileSync(`${SCRATCH}/hb_audit_data.json`, "utf8"));

const TEMPLATE = {
  "zaslepka-cap": { part_id: "product_3071", position: [-636.5, 1223, -898.5025482177734], quaternion: [0.7071067811865475, 0, 0, 0.7071067811865475], scale: [1, 1, 1] },
  "zaslepka-predni-svislice": { part_id: "product_3071", position: [-387.5, 1223, -898.5025482177734], quaternion: [0.7071067811865475, 0, 0, 0.7071067811865475], scale: [1, 1, 1] },
};
const TARGETS = [
  { id: 376, label: "B/00" }, { id: 375, label: "A/01" }, { id: 377, label: "B/01" },
  { id: 369, label: "A/02-ZAKLAD" }, { id: 370, label: "B/02-ZAKLAD" },
];

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
function isKnownZaslepkaCase(a, b) {
  const ra = a.role || "", rb = b.role || "";
  return rb === "zaslepka-" + ra || ra === "zaslepka-" + rb;
}

const results = [];
for (const { id, label } of TARGETS) {
  const orig = D[id];
  const missing = ["zaslepka-cap", "zaslepka-predni-svislice"].filter(role =>
    !orig.parts.some(p => p.role === role && Math.abs(p.position[2] - (-898.5)) < 5));
  if (!missing.length) { console.log(`id=${id} (${label}): uz kompletni, preskakuji`); continue; }
  const added = missing.map(role => ({ role, ...JSON.parse(JSON.stringify(TEMPLATE[role])) }));
  const corrected = { ...orig, parts: orig.parts.concat(added) };

  // over: pozice cap/predni-svislice v cilove sestave skutecne sedi na sablonu (stejne X jako u cap/predni-svislice existujicich)
  const existingCap = orig.parts.find(p => p.role === "cap" && Math.abs(p.position[2] - (-898.5)) < 5);
  const existingPS = orig.parts.find(p => p.role === "predni-svislice" && Math.abs(p.position[2] - (-898.5)) < 5);
  if (Math.abs(existingCap.position[0] - (-636.5)) > 1) throw new Error(`id=${id}: cap X neodpovida sablone (${existingCap.position[0]})`);
  if (Math.abs(existingPS.position[0] - (-387.5)) > 1) throw new Error(`id=${id}: predni-svislice X neodpovida sablone (${existingPS.position[0]})`);

  // realna GLB kolizni kontrola: PRED vs PO, jen role-parove vzory, ne cisla
  function scan(parts) {
    const measured = parts.filter(p => !R.jeKaroserie(p.part_id)).map(p => ({ p, box: worldBox(p) }));
    const pairs = new Set(); let n = 0;
    for (let i = 0; i < measured.length; i++) for (let j = i + 1; j < measured.length; j++) {
      const [ox, oy, oz] = overlap3(measured[i].box, measured[j].box);
      if (ox > 0.5 && oy > 0.5 && oz > 0.5) { n++; pairs.add(measured[i].p.role + "|" + measured[j].p.role); }
    }
    return { n, pairs, dilu: measured.length };
  }
  const before = scan(orig.parts);
  const after = scan(corrected.parts);
  const newPairs = [...after.pairs].filter(x => !before.pairs.has(x));
  console.log(`id=${id} (${label}): pridano ${added.length} dilu (${missing.join(", ")}). Kolize pred=${before.n}(${before.dilu}d) po=${after.n}(${after.dilu}d). Nove role-pary: ${newPairs.length ? JSON.stringify(newPairs) : "zadne"}`);
  if (newPairs.length) throw new Error(`id=${id}: NOVY kolizni vzor po pridani - STOP, over rucne.`);

  results.push({ id, label, corrected, addedRoles: missing });
}

fs.writeFileSync(`${SCRATCH}/hb_fix_results.json`, JSON.stringify(results));
console.log(`\nHotovo, ${results.length} sestav pripraveno k zapisu (0 novych kolizi u vsech).`);
