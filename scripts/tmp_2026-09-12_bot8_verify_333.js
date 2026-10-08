// Overeni prepoctu kolizni rezervy sestavy id=333 (krok 6 procedury
// shape_geometry_methods.id=11): SAT proti realne karoserii, presna
// mezera na dotcenych svarech, self-kolize. POVINNE pouziva
// scripts/2026-09-11_glb_resolver.js pro part_id -> GLB mapovani (zadani).
const fs = require("fs");
const THREE = require("three");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const R = require("/opt/konfigurator/scripts/2026-09-11_glb_resolver.js");
const MeshBVHLib = require("/opt/konfigurator/webapp/js/three-mesh-bvh.js");
THREE.BufferGeometry.prototype.computeBoundsTree = MeshBVHLib.computeBoundsTree;
THREE.Mesh.prototype.raycast = MeshBVHLib.acceleratedRaycast;

const parts = JSON.parse(fs.readFileSync(__dirname + "/tmp_2026-09-12_333_parts_new.json", "utf8"));
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
console.log("Karoserie GLB nactena (_L/_R_D/_B):", walls.map(w => w.geometry.attributes.position.count));

// part_id NENI nazev GLB - POVINNE pres resolver (zadani + 3d-scena-spoje skill).
function partMesh(p) {
  if (R.jeKaroserie(p.part_id)) return null; // "kontrolni-pomucka" role take vynechano nize
  const glbPath = R.glbPath(p.part_id);
  if (!glbPath) throw new Error(`CHYBI GLB pro part_id=${p.part_id} (role=${p.role}) - resolver vratil null.`);
  const m = parseGlbMesh(glbPath);
  m.position.set(...p.position);
  m.quaternion.set(...p.quaternion);
  m.scale.set(...p.scale);
  m.updateMatrixWorld(true);
  return m;
}

const raycaster = new THREE.Raycaster();
function meshWorldEdges(mesh) {
  const geo = mesh.geometry, pos = geo.attributes.position, idx = geo.index;
  const triCount = idx ? idx.count / 3 : pos.count / 3;
  const edges = [];
  const vA = new THREE.Vector3(), vB = new THREE.Vector3(), vC = new THREE.Vector3();
  for (let t = 0; t < triCount; t++) {
    let ia, ib, ic;
    if (idx) { ia = idx.getX(t * 3); ib = idx.getX(t * 3 + 1); ic = idx.getX(t * 3 + 2); } else { ia = t * 3; ib = t * 3 + 1; ic = t * 3 + 2; }
    vA.fromBufferAttribute(pos, ia).applyMatrix4(mesh.matrixWorld);
    vB.fromBufferAttribute(pos, ib).applyMatrix4(mesh.matrixWorld);
    vC.fromBufferAttribute(pos, ic).applyMatrix4(mesh.matrixWorld);
    edges.push([vA.clone(), vB.clone()], [vB.clone(), vC.clone()], [vC.clone(), vA.clone()]);
  }
  return edges;
}
function collidesWithWallsReal(mesh) {
  const edges = meshWorldEdges(mesh);
  for (const [p0, p1] of edges) {
    const dir = p1.clone().sub(p0), dist = dir.length();
    if (dist < 1e-6) continue;
    dir.normalize();
    raycaster.set(p0, dir); raycaster.far = dist;
    raycaster.firstHitOnly = true;
    if (raycaster.intersectObjects(walls, false).length) return true;
  }
  return false;
}

// ---- 6a) SAT proti realne karoserii: VSECHNY dily krome car_body_* a
//      role zacinajici "kontrolni-pomucka" ----
const testable = parts.filter(p => !String(p.part_id).startsWith("car_body_") && !String(p.role || "").startsWith("kontrolni-pomucka"));
let collisions = 0;
const collidingList = [];
const meshCache = [];
for (const p of testable) {
  const mesh = partMesh(p);
  meshCache.push({ p, mesh });
  if (collidesWithWallsReal(mesh)) { collisions++; collidingList.push({ role: p.role, part_id: p.part_id, position: p.position }); }
}
console.log(`\n=== 6a) SAT test proti realne karoserii (${BASE}) ===`);
console.log(`${collisions}/${testable.length} koliduje (z celkem ${parts.length} dilu, ${parts.length - testable.length} car_body_*/kontrolni-pomucka vynechano zamerne).`);
if (collisions) console.log("KOLIDUJICI:", JSON.stringify(collidingList, null, 1));

// ---- 6b) presna mezera (0.000mm) na dotcenych svarech ----
console.log("\n=== 6b) presna mezera na dotcenych svarech ===");
function box3Of(role, matcher) {
  const found = parts.filter(p => p.role === role && matcher(p));
  return found.map(p => {
    const mesh = partMesh(p);
    const box = new THREE.Box3().setFromObject(mesh);
    return { p, box };
  });
}
const LEG_Z = { leg0: -1358.5025482177734, leg1: -898.5025482177734, leg2: -34.50254821777344 };
const near = (a, b, eps) => Math.abs(a - b) < (eps == null ? 0.5 : eps);
let seamFail = 0;
for (const legKey of ["leg1", "leg2"]) {
  const z = LEG_Z[legKey];
  const sloupek = box3Of("sloupek-pred-podbehem", p => near(p.position[2], z, 1))[0];
  const svislice = box3Of("zadni-svislice-nad-zarezem", p => near(p.position[2], z, 1))[0];
  const gap = svislice.box.min.y - sloupek.box.max.y;
  console.log(`${legKey}: sloupek top(real bbox)=${sloupek.box.max.y.toFixed(6)}, svislice bottom(real bbox)=${svislice.box.min.y.toFixed(6)}, gap=${gap.toFixed(6)}mm`);
  if (Math.abs(gap) > 0.001) { seamFail++; console.log(`  !!! NENI 0.000mm presne !!!`); }
}
// col0 dorovnani svar: nosnik-col0-p0 (nejnizsi patro) spodni hrana vs vyrezova noha leg1 (zadni-svislice-nad-zarezem spodek == nova Y_new)
{
  const nosnikP0List = parts.filter(p => p.role === "nosnik-col0-p0");
  for (const np0 of nosnikP0List) {
    const mesh = partMesh(np0);
    const box = new THREE.Box3().setFromObject(mesh);
    const svislice = box3Of("zadni-svislice-nad-zarezem", p => near(p.position[2], LEG_Z.leg1, 1))[0];
    const gap = box.min.y - svislice.box.min.y;
    console.log(`col0 nosnik-col0-p0 (X=${np0.position[0]}): bottom(real bbox)=${box.min.y.toFixed(6)}, vyrez-leg1 svislice bottom(real bbox)=${svislice.box.min.y.toFixed(6)}, gap=${gap.toFixed(6)}mm`);
    if (Math.abs(gap) > 0.001) { seamFail++; console.log(`  !!! NENI 0.000mm presne !!!`); }
  }
}
console.log(seamFail === 0 ? "VSECHNY dotcene svary presne 0.000mm." : `${seamFail} svaru NENI presnych!`);

// ---- 6c) self-kolize (Box3 pruseciky mezi VSEMI pary ruzne role, preskoc
//      znama vnorovaci prekryti) ----
console.log("\n=== 6c) self-kolize (Box3, vsechny pary ruzne role) ===");
const KNOWN_NEST = [
  [/^eurobox-/, /^(nosnik|spojnice)-/],
  [/^zaslepka-/, /^(predni-svislice|cap|zadni-svislice)/],
  [/^logo-ochrana-vypln-/, /.*/], // vypln (podklad loga) vnorena do profilu - znamy jev
  // vypln-dno (MDF deska dna) vlozena/dosedajici na podelnik-*-spodni rámy
  // z obou stran (7-8mm presah na hranach) - OVERENO, ze existuje UZ V
  // PUVODNIM (netransformovanem) 333 datech beze zmeny (viz AGENTS_LOG /
  // session poznamky), tedy nejde o dusledek teto transformace.
  [/^vypln-dno-/, /^podelnik-/],
];
function isKnownNest(roleA, roleB) {
  for (const [ra, rb] of KNOWN_NEST) {
    if ((ra.test(roleA) && rb.test(roleB)) || (ra.test(roleB) && rb.test(roleA))) return true;
  }
  return false;
}
let selfCollisions = 0;
const selfList = [];
const boxCache = testable.map((p, i) => ({ p, box: new THREE.Box3().setFromObject(meshCache[i].mesh) }));
for (let i = 0; i < boxCache.length; i++) {
  for (let j = i + 1; j < boxCache.length; j++) {
    const a = boxCache[i], b = boxCache[j];
    if (a.p.role === b.p.role) continue; // stejna role = ocekavane sousedstvi (napr. dva uhelniky vedle sebe)
    if (isKnownNest(a.p.role || "", b.p.role || "")) continue;
    if (!a.box.intersectsBox(b.box)) continue;
    const inter = a.box.clone().intersect(b.box);
    const size = inter.getSize(new THREE.Vector3());
    const vol = size.x * size.y * size.z;
    if (vol > 2000) {
      selfCollisions++;
      selfList.push({ a: a.p.role, aId: a.p.part_id, b: b.p.role, bId: b.p.part_id, overlap_mm: [size.x, size.y, size.z].map(v => +v.toFixed(2)), vol_mm3: +vol.toFixed(0) });
    }
  }
}
console.log(`${selfCollisions} podezrelych paru (prah 2000mm3) z ${boxCache.length} dilu (${boxCache.length * (boxCache.length - 1) / 2} paru testovano, znama vnorovani preskocena).`);
if (selfCollisions) console.log(JSON.stringify(selfList, null, 1));

fs.writeFileSync(__dirname + "/tmp_2026-09-12_333_verify_report.json", JSON.stringify({
  totalParts: parts.length, testableParts: testable.length, collisions, collidingList,
  seamFail, selfCollisions, selfList,
}, null, 1));
console.log("\nUlozeno: scripts/tmp_2026-09-12_333_verify_report.json");
console.log("\n=== SOUHRN ===");
console.log(`SAT kolize s karoserii: ${collisions}`);
console.log(`Svary mimo 0.000mm: ${seamFail}`);
console.log(`Self-kolize (>2000mm3, neznama): ${selfCollisions}`);
