// Prida dorazovou desku (vypln-bok-prepazka) do 6 Jumpy sestav (K-118/
// K-119, kod="02"), pravidlo odvozene z realne Doblo-369 geometrie:
//   spodek desky = realny vrchol pricka-spodni-0 - 7mm (zasun)
//   vrch desky   = realny spodek zaslepky (na te same noze) - 11mm
//   sirka desky  = vzdalenost stred-stred predni-svislice/cap - 2*8mm
const fs = require("fs");
const THREE = require("three");
const R = require("/opt/konfigurator/scripts/2026-09-11_glb_resolver.js");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const SCRATCH = "/tmp/claude-0/-opt-konfigurator/68994686-5a6b-46d4-b3c7-14bc1f68c6ac/scratchpad";
const D = JSON.parse(fs.readFileSync(`${SCRATCH}/jumpy_raw.json`, "utf8"));

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
  const pairs = new Map();
  for (let i = 0; i < m.length; i++) for (let j = i + 1; j < m.length; j++) {
    const [ox, oy, oz] = overlap3(m[i].box, m[j].box);
    if (ox > 0.5 && oy > 0.5 && oz > 0.5) pairs.set((m[i].p.role || "?") + "|" + (m[j].p.role || "?"), [ox, oy, oz].map(v => +v.toFixed(1)));
  }
  return pairs;
}

const ZASUN = 7, TOP_CLEAR = 11, SIDE_ZASUN = 8;

const results = {};
for (const [idStr, info] of Object.entries(D)) {
  const id = Number(idStr);
  const parts = info.parts;
  const pricka = parts.find(p => p.role === "pricka-spodni-0");
  const z = pricka.position[2];
  const atZ = parts.filter(p => Math.abs(p.position[2] - z) < 1 && !R.jeKaroserie(p.part_id));
  const predni = atZ.find(p => p.role === "predni-svislice");
  const cap = atZ.find(p => p.role === "cap");
  const zaslepky = atZ.filter(p => p.part_id === "product_3071")
    .map(p => ({ p, box: worldBox(p) }))
    .sort((a, b) => b.box.max.y - a.box.max.y).slice(0, 2); // 2 nejvyssi (na predni-svislice/cap konci)

  const prickaBox = worldBox(pricka);
  const zaslepkaMinY = Math.min(...zaslepky.map(z => z.box.min.y));
  const bottomY = prickaBox.max.y - ZASUN;
  const topY = zaslepkaMinY - TOP_CLEAR;
  const height = topY - bottomY;

  const xMid = (predni.position[0] + cap.position[0]) / 2;
  const width = Math.abs(cap.position[0] - predni.position[0]) - 2 * SIDE_ZASUN;

  const deska = {
    role: "vypln-bok-prepazka", part_id: "product_3939",
    position: [xMid, (bottomY + topY) / 2, z],
    quaternion: [0, 0, 0, 1],
    scale: [width / 1000, height / 1000, 1],
  };

  const before = scan(parts);
  const after = parts.concat([deska]);
  const afterScan = scan(after);
  const newPairs = [...afterScan.keys()].filter(k => !before.has(k));
  const realNew = newPairs.filter(k => {
    const s = [...afterScan.get(k)].sort((a, b) => a - b);
    return !(s[0] >= 7 && s[0] <= 11 && s[1] >= 7 && s[1] <= 11); // razitko-v-drazce vzor
  });

  console.log(`\nid=${id} ${info.name.slice(0, 50)}`);
  console.log(`  predni.x=${predni.position[0]} cap.x=${cap.position[0]} z=${z}`);
  console.log(`  pricka top=${prickaBox.max.y.toFixed(2)} zaslepka min=${zaslepkaMinY.toFixed(2)}`);
  console.log(`  deska: X=${xMid} Y=[${bottomY.toFixed(2)},${topY.toFixed(2)}] (vyska=${height.toFixed(2)}) sirka=${width.toFixed(2)} Z=${z}`);
  console.log(`  kolize: pred=${before.size} po=${afterScan.size} nove=${newPairs.length} skutecne_nove=${realNew.length}`);
  for (const k of realNew) console.log("     ", k, JSON.stringify(afterScan.get(k)));

  results[id] = { name: info.name, parts: after, ok: realNew.length === 0, deska, expectCount: parts.length };
}
fs.writeFileSync(`${SCRATCH}/jumpy_deska_result.json`, JSON.stringify(results));
console.log("\nCELKEM OK:", Object.values(results).filter(r => r.ok).length, "/", Object.keys(results).length);
