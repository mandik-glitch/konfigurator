// Krok 6 procedury prepocet-kolizni-rezervy-existujici-sestavy pro id=334:
// a) SAT test (hranovy raycasting) VSECH dilu (krome car_body_*/kontrolni-pomucka)
//    proti REALNE GLB geometrii karoserie (_L/_R_D/_B) - ocekava se 0 kolizi.
// b) presna mezera (0.000mm) na kazdem posunutem/dorovnanem svu (Box3 min/max).
// c) self-kolize - Box3 prusecik mezi VSEMI pary dilu ruzne role, preskoc
//    zname vnorovaci prekryvy (eurobox<->nosnik/spojnice, zaslepka<->profil,
//    logo-ochrana-vypln<->profil), u ostatnich cekej 0 prekryvu nad ~2000mm3.
const fs = require("fs");
const THREE = require("three");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const MeshBVHLib = require("/opt/konfigurator/webapp/js/three-mesh-bvh.js");
THREE.BufferGeometry.prototype.computeBoundsTree = MeshBVHLib.computeBoundsTree;
THREE.Mesh.prototype.raycast = MeshBVHLib.acceleratedRaycast;
const R = require("/opt/konfigurator/scripts/2026-09-11_glb_resolver.js");

const parts = JSON.parse(fs.readFileSync(__dirname + "/tmp_2026-09-12_334_parts_new.json", "utf8"));
console.log("Mapa GLB nactena, zaznamu:", R.velikostMapy());

const KAT = "/opt/konfigurator/webapp/katalog/";
const BASE = "Fiat_Doblo_FI14_2010-2022";
function loadWall(suf) {
  const m = parseGlbMesh(KAT + "car_bodies/" + BASE + suf + ".glb");
  m.material = new THREE.MeshBasicMaterial({ side: THREE.DoubleSide });
  m.updateMatrixWorld(true);
  m.geometry.computeBoundsTree();
  return m;
}
const walls = [loadWall("_L"), loadWall("_R_D"), loadWall("_B")];

function meshWorldEdgeSample(mesh, maxEdges) {
  const geo = mesh.geometry, pos = geo.attributes.position, idx = geo.index;
  const triCount = idx ? idx.count / 3 : pos.count / 3;
  const step = Math.max(1, Math.floor(triCount / (maxEdges / 3)));
  const edges = [];
  const vA = new THREE.Vector3(), vB = new THREE.Vector3(), vC = new THREE.Vector3();
  for (let t = 0; t < triCount; t += step) {
    let ia, ib, ic;
    if (idx) { ia = idx.getX(t * 3); ib = idx.getX(t * 3 + 1); ic = idx.getX(t * 3 + 2); } else { ia = t * 3; ib = t * 3 + 1; ic = t * 3 + 2; }
    vA.fromBufferAttribute(pos, ia).applyMatrix4(mesh.matrixWorld);
    vB.fromBufferAttribute(pos, ib).applyMatrix4(mesh.matrixWorld);
    vC.fromBufferAttribute(pos, ic).applyMatrix4(mesh.matrixWorld);
    edges.push([vA.clone(), vB.clone()], [vB.clone(), vC.clone()], [vC.clone(), vA.clone()]);
  }
  return edges;
}
const raycaster = new THREE.Raycaster();
function collidesWithWallsReal(mesh) {
  const edges = meshWorldEdgeSample(mesh, 300);
  for (const [p0, p1] of edges) {
    const dir = p1.clone().sub(p0), dist = dir.length();
    if (dist < 1e-6) continue;
    dir.normalize();
    raycaster.set(p0, dir); raycaster.far = dist;
    if (raycaster.intersectObjects(walls, false).length) return true;
  }
  return false;
}

function partMesh(p) {
  const glbPath = R.glbPath(p.part_id);
  if (!glbPath) throw new Error("CHYBI GLB pro part_id=" + p.part_id + " role=" + p.role);
  const m = parseGlbMesh(glbPath);
  m.position.set(...p.position);
  m.quaternion.set(...p.quaternion);
  m.scale.set(...p.scale);
  m.updateMatrixWorld(true);
  return m;
}

// ---- a) SAT proti realne karoserii ----
const testable = parts.filter(p => !R.jeKaroserie(p.part_id) && !(p.role || "").startsWith("kontrolni-pomucka"));
let collisions = 0;
const collidingList = [];
const meshCache = [];
for (const p of testable) {
  const mesh = partMesh(p);
  meshCache.push({ p, mesh });
  if (collidesWithWallsReal(mesh)) { collisions++; collidingList.push({ role: p.role, part_id: p.part_id, position: p.position }); }
}
console.log(`\nSAT test: ${collisions}/${testable.length} koliduje s realnou karoserii (z celkem ${parts.length} dilu, ${parts.length - testable.length} car_body_*/pomucka vynechano).`);
if (collisions) console.log("KOLIDUJICI:", JSON.stringify(collidingList, null, 1));

// ---- b) presna mezera na dotcenych svarech ----
function box(role, zApprox, xApprox) {
  const cands = meshCache.filter(({ p }) => p.role === role && (zApprox == null || Math.abs(p.position[2] - zApprox) < 2) && (xApprox == null || Math.abs(p.position[0] - xApprox) < 2));
  return cands.map(({ p, mesh }) => ({ p, box: new THREE.Box3().setFromObject(mesh) }));
}
console.log("\n--- presne mezery na dotcenych svarech (0.000mm ocekavano) ---");
const seamChecks = [
  { z: -898.5, label: "leg1 seam (sloupek top vs svislice bottom)" },
  { z: -34.5, label: "leg2 seam" },
];
for (const { z, label } of seamChecks) {
  const sloupek = box("sloupek-pred-podbehem", z)[0];
  const svislice = box("zadni-svislice-nad-zarezem", z)[0];
  if (sloupek && svislice) {
    const gap = svislice.box.min.y - sloupek.box.max.y;
    console.log(label + ": sloupek.top=" + sloupek.box.max.y.toFixed(4) + " svislice.bottom=" + svislice.box.min.y.toFixed(4) + " gap=" + gap.toFixed(4) + "mm");
  } else console.log(label + ": DILY NENALEZENY (sloupek=" + !!sloupek + " svislice=" + !!svislice + ")");
}
// col0 nejnizsi patro (nosnik-col0-p0, x=-706.5, drzi se o leg1) vs leg1 novy Y_new (svislice.bottom)
{
  const nosnikP0 = box("nosnik-col0-p0", null, -706.5)[0];
  const svislice = box("zadni-svislice-nad-zarezem", -898.5)[0];
  if (nosnikP0 && svislice) {
    const gap = nosnikP0.box.min.y - svislice.box.min.y;
    console.log("col0-p0 (dorovnano) vs leg1 novy seam: nosnik.bottom=" + nosnikP0.box.min.y.toFixed(4) + " leg1.seam(svislice.bottom)=" + svislice.box.min.y.toFixed(4) + " gap=" + gap.toFixed(4) + "mm (>=0 = OK, nevisi ve vzduchu)");
  } else console.log("col0-p0 seam check: DILY NENALEZENY");
}

// ---- c) self-kolize (Box3, vsechny pary ruzne role, preskoc zname vnorovaci prekryvy) ----
console.log("\n--- self-kolize (Box3, prah 2000mm3 mimo zname vnorovaci pary) ---");
function isKnownNesting(a, b) {
  const ra = a.role || "", rb = b.role || "";
  const pair = [ra, rb].sort().join("|");
  const rules = [
    [/^eurobox-/, /^(nosnik|spojnice)-/],
    [/^zaslepka-/, /^(predni-svislice|zadni-svislice|cap|sloupek-pred-podbehem)/],
    [/^logo-ochrana-vypln-/, /^(predni-svislice|zadni-svislice|cap|sloupek-pred-podbehem|nosnik|spojnice|podelnik|pricka)/],
    [/^logo-ochrana-logo-/, /^(predni-svislice|zadni-svislice|cap|sloupek-pred-podbehem|nosnik|spojnice|podelnik|pricka)/],
    [/^uhelnik-/, /^(nosnik|spojnice|predni-svislice|zadni-svislice|sloupek-pred-podbehem|podelnik|pricka)/],
  ];
  for (const [ra_, rb_] of rules) {
    if ((ra_.test(ra) && rb_.test(rb)) || (ra_.test(rb) && rb_.test(ra))) return true;
  }
  return false;
}
let selfSusp = 0;
const selfList = [];
const cache = meshCache.map(({ p, mesh }) => ({ p, box: new THREE.Box3().setFromObject(mesh) }));
for (let i = 0; i < cache.length; i++) {
  for (let j = i + 1; j < cache.length; j++) {
    const a = cache[i], b = cache[j];
    if (a.p.role === b.p.role) continue; // stejna role muze legitimne sousedit (2 instance vedle sebe)
    if (isKnownNesting(a.p, b.p)) continue;
    if (!a.box.intersectsBox(b.box)) continue;
    const ix = Math.min(a.box.max.x, b.box.max.x) - Math.max(a.box.min.x, b.box.min.x);
    const iy = Math.min(a.box.max.y, b.box.max.y) - Math.max(a.box.min.y, b.box.min.y);
    const iz = Math.min(a.box.max.z, b.box.max.z) - Math.max(a.box.min.z, b.box.min.z);
    const vol = Math.max(0, ix) * Math.max(0, iy) * Math.max(0, iz);
    if (vol > 2000) {
      selfSusp++;
      selfList.push({ a: a.p.role, b: b.p.role, vol: +vol.toFixed(0), overlap_mm: [ix, iy, iz].map(v => +v.toFixed(1)) });
    }
  }
}
console.log(`podezrelych Box3 prekryvu (vol>2000mm3): ${selfSusp} z ${cache.length * (cache.length - 1) / 2} paru testovano.`);
if (selfSusp) console.log(JSON.stringify(selfList, null, 1));

fs.writeFileSync(__dirname + "/tmp_2026-09-12_334_verify_report.json", JSON.stringify({
  testedParts: testable.length, collisions, collidingList, selfSusp, selfList,
}, null, 1));
console.log("\nUlozeno: tmp_2026-09-12_334_verify_report.json");
