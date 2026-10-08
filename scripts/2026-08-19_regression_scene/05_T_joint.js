const THREE = require("three");
const shared = require("/opt/konfigurator/webapp/js/scene-geometry-shared.js");
const { baseQuaternion, computeConnectorsLocal, attachEntryToParent } = shared;
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");

const GLB_PATH = "/opt/konfigurator/webapp/katalog/profil_30x30_uzavreny.glb";
function mkRealEntry() {
  const obj = parseGlbMesh(GLB_PATH);
  return { object3d: obj, connectorsLocal: computeConnectorsLocal(obj) };
}
function boxOf(entry) { return new THREE.Box3().setFromObject(entry.object3d); }
function touchReport(a, b) {
  const A = boxOf(a), B = boxOf(b);
  const out = {};
  ["x", "y", "z"].forEach(ax => {
    const gap = Math.max(A.min[ax] - B.max[ax], B.min[ax] - A.max[ax]);
    const overlap = Math.min(A.max[ax], B.max[ax]) - Math.max(A.min[ax], B.min[ax]);
    out[ax] = { gap, overlap };
  });
  return out;
}
function fmt(r) { return ["x", "y", "z"].map(ax => `${ax}:g=${r[ax].gap.toFixed(4)}/o=${r[ax].overlap.toFixed(4)}`).join(" "); }
function isFlush(r, eps) {
  eps = eps == null ? 0.01 : eps;
  const flush = ["x", "y", "z"].filter(ax => Math.abs(r[ax].overlap) <= eps);
  const full = ["x", "y", "z"].filter(ax => r[ax].overlap > eps);
  return flush.length === 1 && full.length === 2;
}

// runAIPlan reprodukce pro shapeSteps("T"):
// step1: attach_to:null, rotation_deg:0  (pruchozi, cely)
// step2: attach_to:1, rotation_deg:90, conn_idx:2  (pripojeny na MID konektor)
const entry1 = mkRealEntry();
const quat1 = baseQuaternion(0);
entry1.object3d.quaternion.copy(quat1);
entry1.object3d.position.set(0, 0, 0);
entry1.object3d.updateMatrixWorld(true);

const entry2 = mkRealEntry();
const quat2 = baseQuaternion(90);
const childConnIdx = 0; // s.orient !== "vertical" => 0
const ok = attachEntryToParent(entry2, entry1, quat2, 2, childConnIdx); // conn_idx:2 = mid
console.log("attach ok:", ok);

const r = touchReport(entry1, entry2);
const flush = isFlush(r);
console.log(`T-spoj (mid konektor, realna geometrie): ${fmt(r)}`);
console.log(flush ? "OK - platny flush styk" : "FAIL - neplatny styk");

// I test T-spoj pro delsi pruchozi profil (T uprostred delky, ne u konce) -
// zkontroluj i to, ze pripojeny dil nezasahuje MIMO pudorys pruchoziho v
// prurezu (uz overeno vyse), a ze skutecne sedi uprostred, ne na kraji.
const w1 = boxOf(entry1);
const w2 = boxOf(entry2);
console.log("entry1 (pruchozi) box:", w1.min, w1.max);
console.log("entry2 (T-pripojeny) box:", w2.min, w2.max);
