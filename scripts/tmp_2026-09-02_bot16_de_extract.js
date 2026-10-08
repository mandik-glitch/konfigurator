// D/E varianty (jen 120/170/220mm) - bot16, 2026-09-01/09-02
// Krok 1: extrakce realne geometrie (legs, railY, TOP_Y) z variant A vsech 5 vozidel.
const THREE = require("three");
const fs = require("fs");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");

const KAT = "/opt/konfigurator/webapp/katalog/";
const EUROBOX_PID = { 120: "product_3788", 170: "product_3793", 220: "product_3794", 270: "product_3795" };
const PID_TO_H = {}; for (const [h, pid] of Object.entries(EUROBOX_PID)) PID_TO_H[pid] = +h;

function glbFor(id) {
  if (id === "Object_7") return KAT + "Object_7.glb";
  if (id === "product_3071") return KAT + "product_3071.glb";
  return KAT + id + ".glb";
}
function meshOf(p) {
  const m = parseGlbMesh(glbFor(p.part_id));
  m.position.set(...p.position); m.quaternion.set(...p.quaternion); m.scale.set(...p.scale);
  m.updateMatrixWorld(true);
  return m;
}
function box3Of(p) { return new THREE.Box3().setFromObject(meshOf(p)); }

const SCRATCH = "/tmp/claude-0/-opt-domeny/40752a20-c083-499a-8fe3-7c39a4eef60b/scratchpad";
const VEHICLES = [
  { key: "PE25", id: 74 },
  { key: "MB47", id: 83 },
  { key: "FO31", id: 111 },
  { key: "VW25", id: 118 },
  { key: "OP31", id: 136 },
];

for (const v of VEHICLES) {
  const data = JSON.parse(fs.readFileSync(`${SCRATCH}/pa_${v.id}.json`, "utf8"));
  const parts = data.parts;
  console.log(`\n\n########## ${v.key} (id=${v.id}) ##########`);

  // najdi vsechny sloupce
  const colSet = new Set();
  for (const p of parts) {
    const m = /^(?:eurobox|nosnik|spojnice)-(sloupec\d+|col\d+)-(?:patro|p)(\d+)$/.exec(p.role || "");
    if (m) colSet.add(m[1]);
  }
  const cols = [...colSet].sort();
  console.log("sloupce:", cols);

  for (const col of cols) {
    console.log(`\n--- ${v.key} / ${col} ---`);
    // floors
    const floorIdx = new Set();
    for (const p of parts) {
      const m = new RegExp(`^nosnik-${col}-(?:patro|p)(\\d+)$`).exec(p.role || "");
      if (m) floorIdx.add(+m[1]);
    }
    const floors = [...floorIdx].sort((a, b) => a - b);
    const floorInfo = [];
    for (const fIdx of floors) {
      const railRole = `nosnik-${col}-patro${fIdx}`;
      const boxRole = `eurobox-${col}-patro${fIdx}`;
      const rails = parts.filter(p => p.role === railRole);
      const boxes = parts.filter(p => p.role === boxRole);
      const railY = rails[0].position[1];
      const allSameY = rails.every(r => Math.abs(r.position[1] - railY) < 0.01);
      const h = PID_TO_H[boxes[0].part_id];
      floorInfo.push({ fIdx, railY, allSameY, h, boxCount: boxes.length, boxZs: boxes.map(b => b.position[2]) });
    }
    console.log("floors:", floorInfo.map(f => `p${f.fIdx}: railY=${f.railY.toFixed(2)} H=${f.h} n=${f.boxCount} sameY=${f.allSameY}`).join(" | "));

    // real delta check formula
    for (let i = 0; i < floorInfo.length - 1; i++) {
      const a = floorInfo[i], b = floorInfo[i + 1];
      const predicted = a.railY + a.h + 60;
      console.log(`  delta check p${a.fIdx}->p${b.fIdx}: actual=${b.railY.toFixed(2)} predicted(a.railY+H+60)=${predicted.toFixed(2)} diff=${(b.railY - predicted).toFixed(3)}`);
    }

    // najdi nohy ohranicujici tenhle sloupec: pouzij realny Z-rozsah nosniku (bbox)
    const railPartsFloor0 = parts.filter(p => p.role === `nosnik-${col}-patro${floors[0]}`);
    const railBoxes = railPartsFloor0.map(box3Of);
    const zMin = Math.min(...railBoxes.map(b => b.min.z));
    const zMax = Math.max(...railBoxes.map(b => b.max.z));
    console.log(`  nosnik Z-span (col length): [${zMin.toFixed(1)}, ${zMax.toFixed(1)}] = ${(zMax - zMin).toFixed(1)}mm`);

    // legy: vsechny "svislice"-like role s pozici Z blizko zMin nebo zMax (tolerance 60mm - legy jsou o kus vedle rail konce)
    const legRoleRe = /^(predni-svislice|zadni-svislice-dolni|zadni-svislice-nad-zarezem|cap|spojnice-dolni|spojnice-horni|sloupek-pred-podbehem|spojnice-dolni-kratka|pricka-uzavreni-vyrezu)$/;
    const legParts = parts.filter(p => legRoleRe.test(p.role || ""));
    const legZs = [...new Set(legParts.map(p => p.position[2]))].sort((a, b) => a - b);
    console.log("  vsechny leg Z pozice v cele sestave:", legZs.map(z => z.toFixed(1)));

    // legy blizsi k zMin/zMax (do 100mm)
    function legsNear(z0) {
      return legParts.filter(p => Math.abs(p.position[2] - z0) < 100);
    }
    const legsA = legsNear(zMin), legsB = legsNear(zMax);
    console.log(`  legy u zMin(${zMin.toFixed(1)}):`, [...new Set(legsA.map(p => `${p.role}@Z${p.position[2].toFixed(1)}`))]);
    console.log(`  legy u zMax(${zMax.toFixed(1)}):`, [...new Set(legsB.map(p => `${p.role}@Z${p.position[2].toFixed(1)}`))]);

    // TOP_Y = min realny Y-max pres 'zadni-svislice-dolni'/'zadni-svislice-nad-zarezem' z OBOU noh (whichever existuje, vezmi max z obou pro danou nohu = nejvyssi bod te nohy na zadni strane)
    function legTopY(legParts) {
      const relevant = legParts.filter(p => /^zadni-svislice/.test(p.role));
      if (!relevant.length) return null;
      const ys = relevant.map(p => box3Of(p).max.y);
      return Math.max(...ys);
    }
    const topA = legTopY(legsA), topB = legTopY(legsB);
    console.log(`  legA topY(zadni-svislice*)=${topA}, legB topY=${topB}`);
    const TOP_Y = Math.min(...[topA, topB].filter(x => x != null));
    console.log(`  => TOP_Y (min of both legs) = ${TOP_Y}`);
  }
}
