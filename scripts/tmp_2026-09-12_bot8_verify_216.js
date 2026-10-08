// Krok 6 procedury prepocet-kolizni-rezervy-existujici-sestavy pro id=216
// (K-119, verze B): a) SAT test (hranovy raycasting) VSECH dilu (krome
// car_body_*/kontrolni-pomucka) proti REALNE GLB geometrii karoserie K-119
// (Citroen Jumpy CI19 2016-, _L/_R_D/_B) - ocekava se 0 kolizi.
// b) presna mezera (0.000mm) na svaru, ktery jsem posunul (sloupek-pred-
// podbehem top vs zadni-svislice-nad-zarezem bottom) + kontrola, ze
// nejnizsi patro sloupce nevisi ve vzduchu.
// c) self-kolize - Box3 prusecik mezi VSEMI pary dilu ruzne role, preskoc
// zname vnorovaci prekryvy, porovna s baseline (PUVODNI netransformovana
// 216 data), aby se odlisily NOVE kolize od uz existujicich prekryvu.
const fs = require("fs");
const THREE = require("three");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const MeshBVHLib = require("/opt/konfigurator/webapp/js/three-mesh-bvh.js");
THREE.BufferGeometry.prototype.computeBoundsTree = MeshBVHLib.computeBoundsTree;
THREE.Mesh.prototype.raycast = MeshBVHLib.acceleratedRaycast;
const R = require("/opt/konfigurator/scripts/2026-09-11_glb_resolver.js");
const { execSync } = require("child_process");

const partsNew = JSON.parse(fs.readFileSync(__dirname + "/tmp_2026-09-12_216_parts_new.json", "utf8"));
console.log("Mapa GLB nactena, zaznamu:", R.velikostMapy());

const dumpPy = `
import json, pymysql
env = {}
with open("api/.env") as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line: continue
        k, v = line.split("=", 1); env[k.strip()] = v.strip()
conn = pymysql.connect(host=env["DB_HOST"], port=int(env.get("DB_PORT",3306)), user=env["DB_USER"], password=env["DB_PASSWORD"], database=env["DB_NAME"], cursorclass=pymysql.cursors.DictCursor)
cur = conn.cursor()
cur.execute("SELECT data FROM product_assemblies WHERE id=216")
print(json.dumps(json.loads(cur.fetchone()["data"])["parts"]))
conn.close()
`;
fs.writeFileSync("/tmp/_dump_216orig.py", dumpPy);
const partsOrig = JSON.parse(execSync("api/venv/bin/python3 /tmp/_dump_216orig.py", { cwd: "/opt/konfigurator", maxBuffer: 1024 * 1024 * 40 }).toString());

const KAT = "/opt/konfigurator/webapp/katalog/";
const BASE = "Citroën_Jumpy_CI19_2016-";
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

// ---- a) SAT proti realne karoserii (na NOVYCH datech) ----
const testable = partsNew.filter(p => !R.jeKaroserie(p.part_id) && !(p.role || "").startsWith("kontrolni-pomucka"));
let collisions = 0;
const collidingList = [];
const meshCache = [];
for (const p of testable) {
  const mesh = partMesh(p);
  meshCache.push({ p, mesh });
  if (collidesWithWallsReal(mesh)) { collisions++; collidingList.push({ role: p.role, part_id: p.part_id, position: p.position }); }
}
console.log(`\nSAT test: ${collisions}/${testable.length} koliduje s realnou karoserii (z celkem ${partsNew.length} dilu, ${partsNew.length - testable.length} car_body_*/pomucka vynechano).`);
if (collisions) console.log("KOLIDUJICI:", JSON.stringify(collidingList, null, 1));

// ---- b) presna mezera na svaru, ktery jsem posunul (leg1 vyrez) ----
function box(role, zApprox, xApprox) {
  const cands = meshCache.filter(({ p }) => p.role === role && (zApprox == null || Math.abs(p.position[2] - zApprox) < 2) && (xApprox == null || Math.abs(p.position[0] - xApprox) < 2));
  return cands.map(({ p, mesh }) => ({ p, box: new THREE.Box3().setFromObject(mesh) }));
}
const LEG1_Z = -260.50011444091797;
console.log("\n--- presna mezera na posunutem svaru (0.000mm ocekavano) ---");
let seamGapOk = null;
{
  const sloupek = box("sloupek-pred-podbehem", LEG1_Z)[0];
  const svislice = box("zadni-svislice-nad-zarezem", LEG1_Z)[0];
  if (sloupek && svislice) {
    const gap = svislice.box.min.y - sloupek.box.max.y;
    seamGapOk = Math.abs(gap) < 1e-3;
    console.log("leg1 seam: sloupek.top=" + sloupek.box.max.y.toFixed(6) + " svislice.bottom=" + svislice.box.min.y.toFixed(6) + " gap=" + gap.toFixed(6) + "mm");
  } else console.log("leg1 seam: DILY NENALEZENY (sloupek=" + !!sloupek + " svislice=" + !!svislice + ")");
}
{
  const nosnikP0front = box("nosnik-sloupec0-patro0", null, -439)[0];
  const nosnikP0back = box("nosnik-sloupec0-patro0", null, -735)[0];
  const svislice = box("zadni-svislice-nad-zarezem", LEG1_Z)[0];
  for (const [label, n] of [["front(X=-439)", nosnikP0front], ["back(X=-735)", nosnikP0back]]) {
    if (n && svislice) {
      const gap = n.box.min.y - svislice.box.min.y;
      console.log(`sloupec0-patro0 ${label} vs leg1 novy seam: nosnik.bottom=${n.box.min.y.toFixed(4)} leg1.seam=${svislice.box.min.y.toFixed(4)} gap=${gap.toFixed(4)}mm (>=0 = OK, nevisi ve vzduchu)`);
    }
  }
}

// ---- c) self-kolize (Box3, vsechny pary ruzne role, preskoc zname vnorovaci prekryvy) ----
function isKnownNesting(a, b) {
  const ra = a.role || "", rb = b.role || "";
  const rules = [
    [/^eurobox-/, /^(nosnik|spojnice)-/],
    [/^zaslepka$/, /^(predni-svislice|zadni-svislice|cap|sloupek-pred-podbehem)/],
    [/^uhelnik-/, /^(nosnik|spojnice|predni-svislice|zadni-svislice|sloupek-pred-podbehem|cap)/],
  ];
  for (const [ra_, rb_] of rules) {
    if ((ra_.test(ra) && rb_.test(rb)) || (ra_.test(rb) && rb_.test(ra))) return true;
  }
  return false;
}
function selfCollide(parts, label) {
  console.log(`\n--- self-kolize (${label}, Box3, prah 2000mm3 mimo zname vnorovaci pary) ---`);
  const testableL = parts.filter(p => !R.jeKaroserie(p.part_id) && !(p.role || "").startsWith("kontrolni-pomucka"));
  const cache = testableL.map(p => ({ p, box: new THREE.Box3().setFromObject(partMesh(p)) }));
  let susp = 0;
  const list = [];
  for (let i = 0; i < cache.length; i++) {
    for (let j = i + 1; j < cache.length; j++) {
      const a = cache[i], b = cache[j];
      if (a.p.role === b.p.role) continue;
      if (isKnownNesting(a.p, b.p)) continue;
      if (!a.box.intersectsBox(b.box)) continue;
      const ix = Math.min(a.box.max.x, b.box.max.x) - Math.max(a.box.min.x, b.box.min.x);
      const iy = Math.min(a.box.max.y, b.box.max.y) - Math.max(a.box.min.y, b.box.min.y);
      const iz = Math.min(a.box.max.z, b.box.max.z) - Math.max(a.box.min.z, b.box.min.z);
      const vol = Math.max(0, ix) * Math.max(0, iy) * Math.max(0, iz);
      if (vol > 2000) {
        susp++;
        list.push({ a: a.p.role, aX: a.p.position[0], aZ: a.p.position[2], b: b.p.role, bX: b.p.position[0], bZ: b.p.position[2], vol: +vol.toFixed(0), overlap_mm: [ix, iy, iz].map(v => +v.toFixed(1)) });
      }
    }
  }
  console.log(`podezrelych Box3 prekryvu (vol>2000mm3): ${susp} z ${cache.length * (cache.length - 1) / 2} paru testovano.`);
  if (susp) console.log(JSON.stringify(list, null, 1));
  return { susp, list };
}
const baseline = selfCollide(partsOrig, "PUVODNI 216 - baseline");
const after = selfCollide(partsNew, "NOVA (prepocitana) data");

const newProblems = after.list.filter(x => !baseline.list.some(b => b.a === x.a && b.b === x.b && b.aX === x.aX && b.bX === x.bX));
console.log(`\nNOVE self-kolize zpusobene transformem (nebyly v baseline): ${newProblems.length}`);
if (newProblems.length) console.log(JSON.stringify(newProblems, null, 1));

fs.writeFileSync(__dirname + "/tmp_2026-09-12_216_verify_report.json", JSON.stringify({
  testedParts: testable.length, collisions, collidingList, seamGapOk,
  baselineSelfSusp: baseline.susp, afterSelfSusp: after.susp, newProblems,
}, null, 1));
console.log("\nUlozeno: tmp_2026-09-12_216_verify_report.json");
