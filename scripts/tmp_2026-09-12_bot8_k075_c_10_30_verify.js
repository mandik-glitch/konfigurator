// Overeni prestavby K-075 "verze C" na 10/30mm (viz
// tmp_2026-09-12_bot8_predelat_k075_c_10_30.js): SAT test proti realne
// karoserii, self-kolizni test, touchReport na dotcenych spojich.
const fs = require("fs");
const THREE = require("three");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const lib = require("/opt/konfigurator/scripts/2026-08-18_scene_geometry_lib.js");
const MeshBVHLib = require("/opt/konfigurator/webapp/js/three-mesh-bvh.js");
THREE.BufferGeometry.prototype.computeBoundsTree = MeshBVHLib.computeBoundsTree;
THREE.Mesh.prototype.raycast = MeshBVHLib.acceleratedRaycast;

const parts = JSON.parse(fs.readFileSync(__dirname + "/tmp_2026-09-12_k075_c_10_30_parts.json", "utf8"));
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

// part_id NENI nazev GLB (⭐ pravidlo z 3d-scena-spoje skillu) - mapuj VZDY
// pres DB (shop_products.glb_file pro "product_*", cfg_dily.glb_file pro
// vse ostatni krome "Object_7"/karoserie).
const { execSync } = require("child_process");
const uniqueIds = [...new Set(parts.map(p => p.part_id).filter(id => id !== "Object_7" && !id.startsWith("car_body_")))];
const productIds = uniqueIds.filter(id => id.startsWith("product_")).map(id => id.replace("product_", ""));
const otherIds = uniqueIds.filter(id => !id.startsWith("product_"));
const pyScript = `
import json, pymysql
env = {}
with open("api/.env") as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line: continue
        k, v = line.split("=", 1); env[k.strip()] = v.strip()
conn = pymysql.connect(host=env["DB_HOST"], port=int(env.get("DB_PORT",3306)), user=env["DB_USER"], password=env["DB_PASSWORD"], database=env["DB_NAME"], cursorclass=pymysql.cursors.DictCursor)
out = {}
with conn.cursor() as cur:
    ids = ${JSON.stringify(productIds)}
    if ids:
        cur.execute("SELECT id, glb_file FROM shop_products WHERE id IN (%s)" % ",".join(ids))
        for r in cur.fetchall(): out["product_" + str(r["id"])] = r["glb_file"]
    other = ${JSON.stringify(otherIds)}
    if other:
        fmt = ",".join(["%s"] * len(other))
        cur.execute("SELECT id, glb_file FROM cfg_dily WHERE id IN (%s)" % fmt, other)
        for r in cur.fetchall(): out[r["id"]] = r["glb_file"]
conn.close()
print(json.dumps(out))
`;
fs.writeFileSync("/tmp/_glb_lookup.py", pyScript);
const GLB_MAP = JSON.parse(execSync("api/venv/bin/python3 /tmp/_glb_lookup.py", { cwd: "/opt/konfigurator" }).toString());
console.log("GLB mapa nactena z DB pro", Object.keys(GLB_MAP).length, "unikatnich part_id (z", uniqueIds.length, "pozadovanych) + Object_7 natvrdo.");
const missingMap = uniqueIds.filter(id => !GLB_MAP[id]);
if (missingMap.length) throw new Error("Chybi DB mapovani glb_file pro: " + JSON.stringify(missingMap));

function glbPathFor(partId) {
  if (partId.startsWith("car_body_")) return null; // karoserie sama, vynechano zamerne
  if (partId === "Object_7") return KAT + "Object_7.glb";
  const glbFile = GLB_MAP[partId];
  return KAT + glbFile;
}

function partMesh(p) {
  const glbPath = glbPathFor(p.part_id);
  if (!glbPath) return null;
  if (!fs.existsSync(glbPath)) { throw new Error("CHYBI GLB: " + glbPath + " (part_id=" + p.part_id + ", role=" + p.role + ")"); }
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
    raycaster.set(p0, dir); raycaster.far = dist;
    if (raycaster.intersectObjects(walls, false).length) return true;
  }
  return false;
}

// ---- 1) SAT proti realne karoserii, VSECHNY nekaroseriove dily ----
const testable = parts.filter(p => !p.part_id.startsWith("car_body_"));
let collisions = 0;
const collidingList = [];
let measured = 0;
for (const p of testable) {
  const mesh = partMesh(p);
  measured++;
  if (collidesWithWallsReal(mesh)) { collisions++; collidingList.push({ role: p.role, part_id: p.part_id, position: p.position }); }
}
console.log(`SAT test: ${collisions}/${measured} koliduje s realnou karoserii (z celkem ${parts.length} dilu, ${parts.length - testable.length} car_body_* vynechano zamerne).`);
if (collisions) console.log("KOLIDUJICI:", JSON.stringify(collidingList, null, 1));

// ---- 2) self-kolize (kazdy dil proti kazdemu jinemu, jen profily Object_7 - BVH-friendly, zaslepky/uhelniky/euroboxy vynechany kvuli znamemu jevu #9 z 3d-scena-spoje skillu - cep v dutine) ----
const profileParts = testable.filter(p => p.part_id === "Object_7");
let selfCollisions = 0;
const selfList = [];
const meshCache = profileParts.map(p => ({ p, mesh: partMesh(p) }));
for (let i = 0; i < meshCache.length; i++) {
  for (let j = i + 1; j < meshCache.length; j++) {
    const a = meshCache[i], b = meshCache[j];
    // rychly bbox predfiltr
    const ba = new THREE.Box3().setFromObject(a.mesh), bb = new THREE.Box3().setFromObject(b.mesh);
    if (!ba.intersectsBox(bb)) continue;
    const inter = ba.clone().intersect(bb);
    const size = inter.getSize(new THREE.Vector3());
    // pokud se prekryvaji na VSECH 3 osach o vic nez 3mm, je to podezrele (mozna platny T-styl dosed, mozna kolize) - vypsat k rucnimu posouzeni
    if (size.x > 3 && size.y > 3 && size.z > 3) {
      selfCollisions++;
      selfList.push({ a: a.p.role, b: b.p.role, overlap_mm: [size.x, size.y, size.z].map(v => +v.toFixed(1)) });
    }
  }
}
console.log(`\nSelf-prekryv (Box3, jen profil-profil Object_7, práh 3mm na vsech osach): ${selfCollisions} podezrelych paru z ${profileParts.length} profilu (${profileParts.length * (profileParts.length - 1) / 2} paru testovano).`);
if (selfCollisions) console.log(JSON.stringify(selfList, null, 1));

fs.writeFileSync(__dirname + "/tmp_2026-09-12_k075_c_10_30_verify_report.json", JSON.stringify({
  measured, collisions, collidingList, selfCollisions, selfList, testedPairs: profileParts.length * (profileParts.length - 1) / 2,
}, null, 1));
console.log("\nUlozeno: tmp_2026-09-12_k075_c_10_30_verify_report.json");
