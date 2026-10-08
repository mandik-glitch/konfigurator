// Overeni prestavby product_assemblies.id=332 na 10/30mm (krok 6 procedury
// shape_geometry_methods.id=11): SAT test (hranovy raycasting proti realne
// GLB karoserii, firstHitOnly pres three-mesh-bvh), presna mezera na svarech
// (uz overeno samostatne v batch skriptu - 0.000mm na obou seamech + na
// col0-p0 patre), a self-kolize (Box3 pruniky mezi vsemi pary dilu, mimo
// znama zamerna vnorovani).
//
// part_id -> GLB mapovani POVINNE pres scripts/2026-09-11_glb_resolver.js
// (nikdy naivni odvozeni z part_id - viz hlavicka toho souboru, 3x
// zpusobilo realne chyby v minulosti).
const fs = require("fs");
const THREE = require("three");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const R = require("/opt/konfigurator/scripts/2026-09-11_glb_resolver.js");
const MeshBVHLib = require("/opt/konfigurator/webapp/js/three-mesh-bvh.js");
THREE.BufferGeometry.prototype.computeBoundsTree = MeshBVHLib.computeBoundsTree;
THREE.Mesh.prototype.raycast = MeshBVHLib.acceleratedRaycast;

const SCRATCH = "/tmp/claude-0/-opt-konfigurator/c0c788fb-0783-4d56-adb5-543ba6b0dda8/scratchpad";
const parts = JSON.parse(fs.readFileSync(SCRATCH + "/332_10_30_parts.json", "utf8"));
console.log("Nacteno", parts.length, "dilu (vc. car_body_*), mapa GLB ma", R.velikostMapy(), "zaznamu.");

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

function partMesh(p) {
  const glbPath = R.glbPath(p.part_id);
  if (!glbPath) throw new Error("CHYBI GLB pro part_id=" + p.part_id + " role=" + p.role + " (resolver vratil null)");
  const m = parseGlbMesh(glbPath);
  m.position.set(...p.position);
  m.quaternion.set(...p.quaternion);
  m.scale.set(...p.scale);
  m.updateMatrixWorld(true);
  return m;
}

const raycaster = new THREE.Raycaster();
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
function collidesWithWallsReal(mesh) {
  const edges = meshWorldEdgeSample(mesh, 300);
  for (const [p0, p1] of edges) {
    const dir = p1.clone().sub(p0), dist = dir.length();
    if (dist < 1e-6) continue;
    dir.normalize();
    raycaster.set(p0, dir); raycaster.far = dist; raycaster.firstHitOnly = true;
    if (raycaster.intersectObjects(walls, false).length) return true;
  }
  return false;
}

// ---- 1) SAT test proti realne karoserii: VSECHNY dily krome car_body_*
//      a "kontrolni-pomucka*" (zadny takovy tu neni, ale drzime se litery
//      procedury). ----
const testable = parts.filter(p => !(p.part_id || "").startsWith("car_body_") && !(p.role || "").startsWith("kontrolni-pomucka"));
let collisions = 0;
const collidingList = [];
for (const p of testable) {
  const mesh = partMesh(p);
  if (collidesWithWallsReal(mesh)) { collisions++; collidingList.push({ role: p.role, part_id: p.part_id, position: p.position }); }
}
console.log(`\nSAT TEST: ${collisions}/${testable.length} dilu koliduje s realnou karoserii (${parts.length - testable.length} car_body_* vynechano zamerne).`);
if (collisions) console.log("KOLIDUJICI:", JSON.stringify(collidingList, null, 1));

// ---- 2) Self-kolize: Box3 prusecik mezi VSEMI pary dilu (jina role),
//      preskoc zname vnorovaci prekryvy (eurobox<->nosnik/spojnice,
//      zaslepka<->predni-svislice/cap/zadni-svislice, logo-ochrana-vypln
//      <->profil). Prah ~2000mm3 na OSTATNICH parech. ----
// PRESNE 3 vyjimky z procedury (krok 6c), zadne dalsi:
//   eurobox<->nosnik/spojnice, zaslepka<->predni-svislice/cap/zadni-svislice,
//   logo-ochrana-vypln<->profil (Object_7). Vse ostatni (vc. uhelnik-*,
//   logo-ochrana-logo-*, dvojice mezi sebou) se PLNE testuje.
function isKnownNesting(a, b) {
  const ra = a.role || "", rb = b.role || "";
  const pid_a = a.part_id || "", pid_b = b.part_id || "";
  const startsAny = (r, prefixes) => prefixes.some(pre => r.startsWith(pre));
  const isEurobox = r => startsAny(r, ["eurobox-"]);
  const isNosnikSpojnice = r => startsAny(r, ["nosnik-", "spojnice-"]);
  if ((isEurobox(ra) && isNosnikSpojnice(rb)) || (isEurobox(rb) && isNosnikSpojnice(ra))) return true;

  const isZaslepka = r => startsAny(r, ["zaslepka-"]);
  const isSvisliceCapRole = r => r === "predni-svislice" || r === "cap" || r === "zadni-svislice-dolni" || r === "zadni-svislice-nad-zarezem";
  if ((isZaslepka(ra) && isSvisliceCapRole(rb)) || (isZaslepka(rb) && isSvisliceCapRole(ra))) return true;

  const isLogoVypln = r => startsAny(r, ["logo-ochrana-vypln"]);
  const isProfil = (r, pid) => pid === "Object_7";
  if ((isLogoVypln(ra) && isProfil(rb, pid_b)) || (isLogoVypln(rb) && isProfil(ra, pid_a))) return true;

  return false;
}

const meshCache = testable.map(p => ({ p, box: new THREE.Box3().setFromObject(partMesh(p)) }));
let selfCollisions = 0;
const selfList = [];
const THRESHOLD_MM3 = 2000;
for (let i = 0; i < meshCache.length; i++) {
  for (let j = i + 1; j < meshCache.length; j++) {
    const a = meshCache[i], b = meshCache[j];
    if (a.p.role === b.p.role && a.p.part_id === b.p.part_id) {
      // stejna role/part_id - dva instance stejneho typu (napr dva "cap"),
      // porovnej jen kdyz jsou blizko sebe (jinak zbytecne Box3 volani draha)
    }
    if (!a.box.intersectsBox(b.box)) continue;
    if (isKnownNesting(a.p, b.p)) continue;
    const inter = a.box.clone().intersect(b.box);
    const size = inter.getSize(new THREE.Vector3());
    const vol = size.x * size.y * size.z;
    if (vol > THRESHOLD_MM3) {
      selfCollisions++;
      selfList.push({ a: a.p.role, aPos: a.p.position, b: b.p.role, bPos: b.p.position, overlap_mm: [size.x, size.y, size.z].map(v => +v.toFixed(1)), vol_mm3: Math.round(vol) });
    }
  }
}
console.log(`\nSELF-KOLIZE (Box3, prah ${THRESHOLD_MM3}mm3, zname vnorovaci pary preskoceny): ${selfCollisions} podezrelych paru z ${testable.length * (testable.length - 1) / 2} testovanych paru.`);
if (selfCollisions) console.log(JSON.stringify(selfList, null, 1));

fs.writeFileSync(SCRATCH + "/332_10_30_verify_report.json", JSON.stringify({
  testedCount: testable.length, collisions, collidingList, selfCollisions, selfList,
}, null, 1));
console.log("\nUlozeno:", SCRATCH + "/332_10_30_verify_report.json");
console.log(`\n=== VYSLEDEK: SAT=${collisions} kolizi, SELF=${selfCollisions} podezrelych paru ===`);
