// Step 4 of shape_geometry_methods.id=1 (prevod-profilu-zachovanim-rozmeru):
// touchReport (gap/overlap on all 3 axes) for every lic_peers joint pair,
// verified against REAL Object_7.glb geometry (not just position/scale numbers).
const THREE = require("three");
const fs = require("fs");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");

const OBJECT7 = "/opt/konfigurator/webapp/katalog/Object_7.glb";

function partBox(p) {
  const mesh = parseGlbMesh(OBJECT7);
  mesh.position.set(...p.position);
  mesh.quaternion.set(...p.quaternion);
  mesh.scale.set(...p.scale);
  mesh.updateMatrixWorld(true);
  return new THREE.Box3().setFromObject(mesh);
}

function touchReport(boxA, boxB) {
  const axes = ["x", "y", "z"];
  const report = {};
  for (const ax of axes) {
    const aMin = boxA.min[ax], aMax = boxA.max[ax];
    const bMin = boxB.min[ax], bMax = boxB.max[ax];
    const overlap = Math.min(aMax, bMax) - Math.max(aMin, bMin);
    report[ax] = overlap; // >=0 full overlap of that much, <0 = gap of -overlap
  }
  return report;
}

function verifyShape(label, parts) {
  console.log(`\n=== ${label} (${parts.length} parts) ===`);
  const boxes = parts.map(partBox);
  let allOk = true;
  parts.forEach((p, i) => {
    (p.lic_peers || []).forEach(j => {
      if (j <= i) return; // report each pair once
      const r = touchReport(boxes[i], boxes[j]);
      const axesFlat = Object.entries(r).filter(([ax, v]) => Math.abs(v) < 0.5);
      const ok = axesFlat.length === 1; // exactly one axis at gap/overlap ~0
      if (!ok) allOk = false;
      console.log(`  [${i}]<->[${j}]  x=${r.x.toFixed(2)} y=${r.y.toFixed(2)} z=${r.z.toFixed(2)}  ${ok ? "OK (flush joint)" : "*** SUSPICIOUS ***"}`);
    });
  });
  // also print full bbox per part
  boxes.forEach((b, i) => {
    console.log(`  part[${i}] box: min=(${b.min.x.toFixed(1)},${b.min.y.toFixed(1)},${b.min.z.toFixed(1)}) max=(${b.max.x.toFixed(1)},${b.max.y.toFixed(1)},${b.max.z.toFixed(1)})`);
  });
  console.log(allOk ? "  => ALL JOINTS OK" : "  => SOME JOINTS SUSPICIOUS, review above");
  return allOk;
}

const expertPlain = JSON.parse(fs.readFileSync("/tmp/claude-0/-opt-domeny/40752a20-c083-499a-8fe3-7c39a4eef60b/scratchpad/cs526.json", "utf8")).parts;
const expertVyrez = JSON.parse(fs.readFileSync("/tmp/claude-0/-opt-domeny/40752a20-c083-499a-8fe3-7c39a4eef60b/scratchpad/cs527.json", "utf8")).parts;
const vitoPlain = JSON.parse(fs.readFileSync("/tmp/claude-0/-opt-domeny/40752a20-c083-499a-8fe3-7c39a4eef60b/scratchpad/vito_plain.json", "utf8")).parts;
const vitoVyrez = JSON.parse(fs.readFileSync("/tmp/claude-0/-opt-domeny/40752a20-c083-499a-8fe3-7c39a4eef60b/scratchpad/vito_vyrez.json", "utf8")).parts;

let allOk = true;
allOk &= verifyShape("Expert plain 30x30 (reused Jumpy 526)", expertPlain);
allOk &= verifyShape("Expert vyrez 30x30 (reused Jumpy 527)", expertVyrez);
allOk &= verifyShape("Vito plain 30x30 (new)", vitoPlain);
allOk &= verifyShape("Vito vyrez 30x30 (new)", vitoVyrez);
console.log("\nFINAL:", allOk ? "ALL SHAPES OK" : "REVIEW NEEDED");
