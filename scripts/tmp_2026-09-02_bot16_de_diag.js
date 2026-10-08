const THREE = require("three");
const fs = require("fs");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const { createEngine } = require("/opt/konfigurator/scripts/tmp_2026-08-31_batch_engine.js");
const KAT = "/opt/konfigurator/webapp/katalog/";
const EUROBOX_PID = { 120: "product_3788", 170: "product_3793", 220: "product_3794", 270: "product_3795" };
function glbFor(id) { if (id==="Object_7") return KAT+"Object_7.glb"; return KAT+id+".glb"; }
function meshOf(p) {
  const m = parseGlbMesh(glbFor(p.part_id));
  m.position.set(...p.position); m.quaternion.set(...p.quaternion); m.scale.set(...p.scale);
  m.updateMatrixWorld(true);
  return m;
}
const SCRATCH = "/tmp/claude-0/-opt-domeny/40752a20-c083-499a-8fe3-7c39a4eef60b/scratchpad";
const data = JSON.parse(fs.readFileSync(`${SCRATCH}/pa_136.json`, "utf8"));
const parts = data.parts;
const engine = createEngine("Opel_Vivaro_OP31_2020-");

// template box floor0
const boxTemplate = parts.filter(p => p.role === "eurobox-sloupec0-patro0");
console.log("boxTemplate:", boxTemplate.map(p=>p.position));

function newBoxPart(templateBox, hNew, railYCenter) {
  const origCenter = new THREE.Box3().setFromObject(meshOf(templateBox)).getCenter(new THREE.Vector3());
  const newPid = EUROBOX_PID[hNew];
  const probeMesh = parseGlbMesh(glbFor(newPid));
  probeMesh.position.set(0,0,0); probeMesh.quaternion.set(...templateBox.quaternion); probeMesh.scale.set(1,1,1);
  probeMesh.updateMatrixWorld(true);
  const probeBox = new THREE.Box3().setFromObject(probeMesh);
  const probeCenter = probeBox.getCenter(new THREE.Vector3());
  const targetYbottom = railYCenter + 15;
  const position = [origCenter.x - probeCenter.x, targetYbottom - probeBox.min.y - 12, origCenter.z - probeCenter.z];
  return { part_id: newPid, position, quaternion: templateBox.quaternion, scale: [1,1,1], role: "test" };
}

// Reproduce log scenario: railY0=330,H0=220 -> railY1=610,H1=170 -> railY2=840, box height=120 at floor2 (should COLLIDE per log, topBox~975mm)
const railY2 = 840;
const testParts = boxTemplate.map(bt => newBoxPart(bt, 120, railY2));
console.log("testParts positions (should give box top ~975):", testParts.map(p=>p.position));
const g = new THREE.Group();
testParts.forEach(p => g.add(meshOf(p)));
g.updateMatrixWorld(true);
console.log("box3 world:", new THREE.Box3().setFromObject(g));
console.log("collidesWithWalls (expect COLLISION per log):", engine.collidesWithWalls(g));

// Now my E scenario floor3 railY=870, H=120, box top ~1005 (should ALSO collide, worse)
const railY3 = 870;
const testParts3 = boxTemplate.map(bt => newBoxPart(bt, 120, railY3));
const g3 = new THREE.Group();
testParts3.forEach(p => g3.add(meshOf(p)));
g3.updateMatrixWorld(true);
console.log("box3 world (floor3):", new THREE.Box3().setFromObject(g3));
console.log("collidesWithWalls floor3 (expect COLLISION, higher than floor2):", engine.collidesWithWalls(g3));

// Sanity: box top at Y=2000 (WAY above any real roof) - MUST detect collision
const railYHigh = 1900;
const testPartsHigh = boxTemplate.map(bt => newBoxPart(bt, 120, railYHigh));
const gHigh = new THREE.Group();
testPartsHigh.forEach(p => gHigh.add(meshOf(p)));
gHigh.updateMatrixWorld(true);
console.log("box3 world (Y=1900, way above roof):", new THREE.Box3().setFromObject(gHigh));
console.log("collidesWithWalls sanity check (MUST be true):", engine.collidesWithWalls(gHigh));

// test at increasing Y to find where collidesWithWalls (edge-crossing, REAL box mesh) starts triggering
for (let ry = 700; ry <= 1900; ry += 25) {
  const tp = boxTemplate.map(bt => newBoxPart(bt, 120, ry));
  const g = new THREE.Group();
  tp.forEach(p => g.add(meshOf(p)));
  g.updateMatrixWorld(true);
  const c = engine.collidesWithWalls(g);
  if (c) { console.log(`REAL BOX edge-crossing collision first triggers at railY=${ry} (box top ~${ry+15+120})`); break; }
}
