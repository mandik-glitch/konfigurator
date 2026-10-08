// Prepocet podle nove 25mm bezpecnostni mezery (misto 30mm) - eligibilita
// kroku +50mm ted 75mm (misto 80mm). Kde 75mm dosahneme jen s posunem
// horniho bloku (+17mm, overeny max bezpecny limit), posuneme HB nahoru
// a vymenime prislusny box 120->170mm.
const fs = require("fs");
const THREE = require("three");
const R = require("/opt/konfigurator/scripts/2026-09-11_glb_resolver.js");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");

const D = JSON.parse(fs.readFileSync("/tmp/claude-0/-opt-konfigurator/68994686-5a6b-46d4-b3c7-14bc1f68c6ac/scratchpad/headroom_v2.json", "utf8"));
const SHIFT = 17;
const HB_PREFIXES = ["podelnik-", "pricka-spodni", "pricka-horni", "pricka-police", "vypln-"];
const isHornibBlok = (p) => HB_PREFIXES.some(pre => (p.role || "").startsWith(pre));

function worldBox(p) {
  const glb = R.glbPath(p.part_id); if (!glb) return null;
  const mesh = parseGlbMesh(glb);
  mesh.position.set(p.position[0], p.position[1], p.position[2]);
  mesh.quaternion.set(p.quaternion[0], p.quaternion[1], p.quaternion[2], p.quaternion[3]);
  mesh.scale.set(p.scale[0], p.scale[1], p.scale[2]);
  mesh.updateMatrixWorld(true);
  return new THREE.Box3().setFromObject(mesh);
}
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

const PLAN = {
  369: ["col1"], 370: ["col1"], 379: ["col1"], 380: ["col1"], 385: ["col1"],
  382: ["col0"], 383: ["col0"], 384: ["col0"],
};

const results = [];
for (const [idStr, cols] of Object.entries(PLAN)) {
  const id = Number(idStr);
  const orig = D[id].data.parts;
  const before = scan(orig);

  // 1) posun CELEHO horniho bloku +17mm
  let after = orig.map(p => isHornibBlok(p) ? { ...p, position: [p.position[0], p.position[1] + SHIFT, p.position[2]] } : p);

  // 2) vymena 120->170mm nejvyssiho boxu v cilovem sloupci (spravny 3-osy pivot presun)
  const swapLog = [];
  for (const col of cols) {
    const boxes = after.filter(p => (p.role || "").startsWith("eurobox-" + col)).map(p => ({ p, box: worldBox(p) }));
    const topY = Math.max(...boxes.map(x => x.box.max.y));
    const topRole = boxes.find(x => x.box.max.y === topY).p.role;
    const targets = after.filter(p => p.role === topRole);
    for (const t of targets) {
      const idx = after.indexOf(t);
      const oldBox = worldBox(t);
      const desired = { cx: (oldBox.min.x + oldBox.max.x) / 2, cz: (oldBox.min.z + oldBox.max.z) / 2, minY: oldBox.min.y };
      const off = refOffset("product_3793", t.quaternion, t.scale);
      const newPart = { ...t, part_id: "product_3793", position: [desired.cx - off.cx, desired.minY - off.minY, desired.cz - off.cz] };
      after[idx] = newPart;
      swapLog.push(`${topRole}: ${t.part_id}->product_3793`);
    }
  }

  const afterScan = scan(after);
  const newPairs = [...afterScan.pairs.keys()].filter(k => !before.pairs.has(k));
  console.log(`id=${id} [${cols.join(",")}]: ${swapLog.join("; ")} | kolize pred=${before.n} po=${afterScan.n} nove=${newPairs.length}`);
  for (const k of newPairs) console.log("   ", k, JSON.stringify(afterScan.pairs.get(k).map(v => +v.toFixed(1))));
  results.push({ id, parts: after, ok: newPairs.length === 0, cols });
}
fs.writeFileSync("/tmp/claude-0/-opt-konfigurator/68994686-5a6b-46d4-b3c7-14bc1f68c6ac/scratchpad/recalc25_result.json", JSON.stringify(results));
console.log("\nOK:", results.filter(r => r.ok).length, "/", results.length);
