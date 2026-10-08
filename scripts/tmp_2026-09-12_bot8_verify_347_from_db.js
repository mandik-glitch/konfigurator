const THREE = require("three");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const MeshBVHLib = require("/opt/konfigurator/webapp/js/three-mesh-bvh.js");
THREE.BufferGeometry.prototype.computeBoundsTree = MeshBVHLib.computeBoundsTree;
THREE.Mesh.prototype.raycast = MeshBVHLib.acceleratedRaycast;
const R = require("/opt/konfigurator/scripts/2026-09-11_glb_resolver.js");
const { execSync } = require("child_process");

const dump = execSync(`api/venv/bin/python3 -c "
import json
env={}
with open('api/.env') as f:
    for line in f:
        line=line.strip()
        if not line or line.startswith('#') or '=' not in line: continue
        k,v=line.split('=',1); env[k.strip()]=v.strip()
import pymysql
conn=pymysql.connect(host=env['DB_HOST'],port=int(env.get('DB_PORT',3306)),user=env['DB_USER'],password=env['DB_PASSWORD'],database=env['DB_NAME'],cursorclass=pymysql.cursors.DictCursor)
with conn.cursor() as cur:
    cur.execute('SELECT data FROM product_assemblies WHERE id=347')
    print(cur.fetchone()['data'])
conn.close()
"`, { cwd: "/opt/konfigurator", maxBuffer: 1024 * 1024 * 50 }).toString();
const parts = JSON.parse(dump).parts;
console.log("parts loaded from DB id=347:", parts.length);

function loadWall(suf) {
  const m = parseGlbMesh("/opt/konfigurator/webapp/katalog/car_bodies/Fiat_Doblo_FI14_2010-2022" + suf + ".glb");
  m.material = new THREE.MeshBasicMaterial({ side: THREE.DoubleSide });
  m.updateMatrixWorld(true); m.geometry.computeBoundsTree();
  return m;
}
const walls = [loadWall("_L"), loadWall("_R_D"), loadWall("_B")];
function partMesh(p) {
  const glbPath = R.glbPath(p.part_id);
  if (!glbPath) return null;
  const m = parseGlbMesh(glbPath);
  m.position.set(...p.position); m.quaternion.set(...p.quaternion); m.scale.set(...p.scale);
  m.updateMatrixWorld(true);
  return m;
}
function edgesOf(mesh, maxEdges) {
  const geo = mesh.geometry, pos = geo.attributes.position, idx = geo.index;
  const triCount = idx ? idx.count / 3 : pos.count / 3;
  const step = Math.max(1, Math.floor(triCount / (maxEdges / 3)));
  const out = []; const vA = new THREE.Vector3(), vB = new THREE.Vector3(), vC = new THREE.Vector3();
  for (let t = 0; t < triCount; t += step) {
    let ia, ib, ic;
    if (idx) { ia = idx.getX(t * 3); ib = idx.getX(t * 3 + 1); ic = idx.getX(t * 3 + 2); } else { ia = t * 3; ib = t * 3 + 1; ic = t * 3 + 2; }
    vA.fromBufferAttribute(pos, ia).applyMatrix4(mesh.matrixWorld);
    vB.fromBufferAttribute(pos, ib).applyMatrix4(mesh.matrixWorld);
    vC.fromBufferAttribute(pos, ic).applyMatrix4(mesh.matrixWorld);
    out.push([vA.clone(), vB.clone()], [vB.clone(), vC.clone()], [vC.clone(), vA.clone()]);
  }
  return out;
}
const rc = new THREE.Raycaster();
function collides(mesh) {
  for (const [p0, p1] of edgesOf(mesh, 300)) {
    const dir = p1.clone().sub(p0), dist = dir.length();
    if (dist < 1e-6) continue; dir.normalize();
    rc.set(p0, dir); rc.far = dist;
    if (rc.intersectObjects(walls, false).length) return true;
  }
  return false;
}
const testable = parts.filter(p => !R.jeKaroserie(p.part_id) && !(p.role || "").startsWith("kontrolni-pomucka"));
let coll = 0; const box3s = [];
for (const p of testable) {
  const glbPath = R.glbPath(p.part_id);
  if (!glbPath) throw new Error("chybi GLB pro " + p.part_id);
  const m = partMesh(p);
  box3s.push({ p, box: new THREE.Box3().setFromObject(m) });
  if (collides(m)) coll++;
}
console.log("SAT po DB round-tripu:", coll, "/", testable.length);

const KNOWN = [
  (a, b) => (a.startsWith("eurobox") && (b.startsWith("nosnik") || b.startsWith("spojnice"))) || (b.startsWith("eurobox") && (a.startsWith("nosnik") || a.startsWith("spojnice"))),
  (a, b) => (a.startsWith("zaslepka") && (b === "predni-svislice" || b === "cap" || b === "zadni-svislice-nad-zarezem" || b === "zadni-svislice-dolni")) || (b.startsWith("zaslepka") && (a === "predni-svislice" || a === "cap" || a === "zadni-svislice-nad-zarezem" || a === "zadni-svislice-dolni")),
  (a, b) => (a.startsWith("logo-ochrana-vypln") && !b.startsWith("logo-ochrana")) || (b.startsWith("logo-ochrana-vypln") && !a.startsWith("logo-ochrana")),
  (a, b) => (a.startsWith("logo-ochrana-logo") && !b.startsWith("logo-ochrana")) || (b.startsWith("logo-ochrana-logo") && !a.startsWith("logo-ochrana")),
  (a, b) => (a.startsWith("vypln-") && !b.startsWith("vypln-")) || (b.startsWith("vypln-") && !a.startsWith("vypln-")),
];
function known(a, b) { return KNOWN.some(f => f(a, b)); }
let susp = 0; const list = [];
for (let i = 0; i < box3s.length; i++) for (let j = i + 1; j < box3s.length; j++) {
  const a = box3s[i], b = box3s[j];
  if (a.p.role === b.p.role) continue;
  const ra = a.p.role || "", rb = b.p.role || "";
  if (known(ra, rb)) continue;
  if (!a.box.intersectsBox(b.box)) continue;
  const ix = Math.min(a.box.max.x, b.box.max.x) - Math.max(a.box.min.x, b.box.min.x);
  const iy = Math.min(a.box.max.y, b.box.max.y) - Math.max(a.box.min.y, b.box.min.y);
  const iz = Math.min(a.box.max.z, b.box.max.z) - Math.max(a.box.min.z, b.box.min.z);
  const vol = Math.max(0, ix) * Math.max(0, iy) * Math.max(0, iz);
  if (vol > 2000) { susp++; list.push({ a: ra, b: rb, vol: +vol.toFixed(0) }); }
}
console.log("self-kolize po DB round-tripu:", susp, "/", box3s.length * (box3s.length - 1) / 2);
if (list.length) console.log(JSON.stringify(list, null, 1));

const LEG_Z = { leg1: -898.5025482177734, leg2: -34.50254821777344 };
for (const lk of ["leg1", "leg2"]) {
  const sloupek = parts.find(p => p.role === "sloupek-pred-podbehem" && Math.abs(p.position[2] - LEG_Z[lk]) < 0.05);
  const svisl = parts.find(p => p.role === "zadni-svislice-nad-zarezem" && Math.abs(p.position[2] - LEG_Z[lk]) < 0.05);
  const sBox = new THREE.Box3().setFromObject(partMesh(sloupek));
  const vBox = new THREE.Box3().setFromObject(partMesh(svisl));
  console.log(lk, "gap=", (vBox.min.y - sBox.max.y).toFixed(4), "mm");
}

const fs = require("fs");
fs.writeFileSync("/opt/konfigurator/scripts/tmp_2026-09-12_bot8_verify_347_report.json", JSON.stringify({ satCollisions: coll, tested: testable.length, selfSusp: susp, selfList: list }, null, 1));
