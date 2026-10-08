// Prepocet kolizni bezpecnostni rezervy (2/20mm -> 10/30mm) na
// product_assemblies.id=285, podle shape_geometry_methods.id=11.
//
// DRUHY POKUS (v2) - PRVNI POKUS (tmp_2026-09-12_bot8_batch_285.js, jehoz
// vysledek id=352 byl smazan) odvozoval transform VLASTNI geometrickou
// analyzou (Box3 dotykove testy) a dosel k zavěru, ze na leg1 (sdilene Z)
// "plna" cast (predni-svislice/cap/spojnice-dolni/spojnice-horni/zaslepka)
// dostava +deltaZ. Behem prace se ale nasel JINY bot8 beh VE STEJNE
// session (scripts/tmp_2026-09-12_bot8_batch_184.js, uz 4x naostro pouzity
// -> 184→348, 185→349, 216→350, 286→351), ktery ma OBECNOU funkci
// transformAssembly() KALIBROVANOU empirickym self-checkem proti SKUTECNE
// existujici, uz drive schvalene sesterske dvojici K-075 279(2/20mm)->
// 340(10/30mm) - a ten dochazi k OPACNEMU zaveru: na sdilenem Z zustava
// CELA "plna" cast (vsech 5 roli, VCETNE zaslepky) BEZE ZMENY (ani Z ani
// Y), protoze se fyzicky nedotyka prepazky B (jen leg0 se ji dotyka).
// Vlastni empiricke overeni (tento skript, sekce SELF-CHECK-2) potvrzuje:
// v1 obsahovala skutečnou chybu - uniformni +deltaZ/2 na VSECHNY
// spojnice-sloupec0-patroN (misto spravneho diskretniho pravidla "blizko
// pohyblive nohy=cele deltaZ / blizko fixni nohy=beze zmeny / uprostred=
// polovina") posunula jednu vzperu o 4mm blize k pricka-uzavreni-vyrezu a
// VYROBILA falesnou 8778mm3 self-kolizi, kterou pak v1 "opravovala"
// rozsirenim dorovnani - patchovala tak DUSLEDEK vlastni chyby, ne
// skutecny problem procedury. Pod spravnym (4x jinde uz overenym) modelem
// dorovnani NENI potreba vubec (presne jako u 184/215 - stejna rodina,
// identicka geometrie noh).
//
// Proto: misto dalsi vlastni derivace se ZNOVUPOUZIVA uz 4x overena
// genericka transformAssembly() z tmp_2026-09-12_bot8_batch_184.js
// (require, ne kopie) - presne podle zavedene konvence teto davky.

const fs = require("fs");
const THREE = require("three");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const MeshBVHLib = require("/opt/konfigurator/webapp/js/three-mesh-bvh.js");
THREE.BufferGeometry.prototype.computeBoundsTree = MeshBVHLib.computeBoundsTree;
THREE.Mesh.prototype.raycast = MeshBVHLib.acceleratedRaycast;
const R = require("/opt/konfigurator/scripts/2026-09-11_glb_resolver.js");
const { execSync } = require("child_process");
const { transformAssembly, DELTA_Z, DELTA_Y } = require("/opt/konfigurator/scripts/tmp_2026-09-12_bot8_batch_184.js");

const ASM_ID = 285;
const OUT_DIR = "/opt/konfigurator/scripts";

// ============================ 0) NACTENI Z DB ============================
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
cur.execute("SELECT data FROM product_assemblies WHERE id=${ASM_ID}")
print(json.dumps(json.loads(cur.fetchone()["data"])["parts"]))
conn.close()
`;
fs.writeFileSync("/tmp/_dump_285orig.py", dumpPy);
const partsOrig = JSON.parse(execSync("api/venv/bin/python3 /tmp/_dump_285orig.py", { cwd: "/opt/konfigurator", maxBuffer: 1024 * 1024 * 40 }).toString());
console.log(`Nacteno id=${ASM_ID}: ${partsOrig.length} dilu.`);

const LEG_Z0 = -1170.5000534057617;
const LEG_Z1 = -308.5000534057617;
const OLD_YNEW = 291.0001220703125;
const near = (a, b, eps) => Math.abs(a - b) < (eps == null ? 0.05 : eps);

console.log("leg0 pritomen?", partsOrig.some(p => p.role === "predni-svislice" && near(p.position[2], LEG_Z0, 1)));
console.log("leg1 plna pritomna?", partsOrig.some(p => p.role === "predni-svislice" && near(p.position[2], LEG_Z1, 1)));
console.log("leg1 vyrez pritomen?", partsOrig.some(p => p.role === "sloupek-pred-podbehem" && near(p.position[2], LEG_Z1, 1)));

// over old_y_new primo z dat 285 (nezavisle na hodnote pouzite pro 184)
const sloupek1 = partsOrig.find(p => p.role === "sloupek-pred-podbehem" && near(p.position[2], LEG_Z1, 1));
const svisl1 = partsOrig.find(p => p.role === "zadni-svislice-nad-zarezem" && near(p.position[2], LEG_Z1, 1));
const sloupekTop = sloupek1.position[1] + sloupek1.scale[1] * 500;
const svislBottom = svisl1.position[1] - svisl1.scale[1] * 500;
if (Math.abs(sloupekTop - svislBottom) > 0.001) throw new Error("svar neni presny v 285 datech");
console.log(`OLD_YNEW zmereno primo z 285: ${sloupekTop} (ocekavano ${OLD_YNEW}, shoda=${Math.abs(sloupekTop - OLD_YNEW) < 0.001})`);

// krok 4: over jestli je potreba dorovnani
const nosnikPatro0 = partsOrig.filter(p => p.role === "nosnik-sloupec0-patro0");
const floorEdge = Math.min(...nosnikPatro0.map(p => p.position[1])) - 15;
const newYnewLeg1 = OLD_YNEW + DELTA_Y;
console.log(`krok4: floorEdge patro0 = ${floorEdge}, newYnewLeg1 = ${newYnewLeg1}, visi_ve_vzduchu=${floorEdge < newYnewLeg1}`);
const dorovnaniOverride = (floorEdge < newYnewLeg1) ? null : 0;

const cfg285 = {
  legZ0: LEG_Z0,
  sharedLegs: [{ z: LEG_Z1, uhelnikRole: "uhelnik-noha1", oldYnew: OLD_YNEW }],
  colPrefix: "sloupec0",
  dorovnaniOverride,
};

const { parts: result285, log: log285 } = transformAssembly(partsOrig, cfg285);
console.log("log (285):", JSON.stringify(log285));
console.log("celkem dilu:", partsOrig.length, "-> vystup:", result285.length);
if (result285.length !== partsOrig.length) throw new Error("pocet dilu nesedi po transformu");

fs.writeFileSync(`${OUT_DIR}/tmp_2026-09-12_285_parts_new.json`, JSON.stringify(result285));
console.log("Ulozeno: tmp_2026-09-12_285_parts_new.json");

// ============================ KROK 6: OVERENI (stejna metoda jako verify_184.js) ====
const KAT = "/opt/konfigurator/webapp/katalog/";
const BASE = "Citroën_Jumpy_CI18_2016-";
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

console.log("\n=== KROK 6a: SAT test proti realne karoserii ===");
const testable = result285.filter(p => !R.jeKaroserie(p.part_id) && !(p.role || "").startsWith("kontrolni-pomucka"));
let collisions = 0;
const collidingList = [];
const meshCache = [];
for (const p of testable) {
  const mesh = partMesh(p);
  meshCache.push({ p, mesh });
  if (collidesWithWallsReal(mesh)) { collisions++; collidingList.push({ role: p.role, part_id: p.part_id, position: p.position }); }
}
console.log(`SAT: ${collisions}/${testable.length} koliduje s realnou karoserii (z celkem ${result285.length} dilu).`);
if (collisions) console.log("KOLIDUJICI:", JSON.stringify(collidingList, null, 1));

console.log("\n=== KROK 6b: presna mezera na posunutem svaru ===");
function box(role, zApprox, xApprox) {
  const cands = meshCache.filter(({ p }) => p.role === role && (zApprox == null || Math.abs(p.position[2] - zApprox) < 2) && (xApprox == null || Math.abs(p.position[0] - xApprox) < 2));
  return cands.map(({ p, mesh }) => ({ p, box: new THREE.Box3().setFromObject(mesh) }));
}
const seamChecks = [];
{
  const sloupek = box("sloupek-pred-podbehem", LEG_Z1)[0];
  const svislice = box("zadni-svislice-nad-zarezem", LEG_Z1)[0];
  const gap = svislice.box.min.y - sloupek.box.max.y;
  console.log("leg1 seam: sloupek.top=" + sloupek.box.max.y.toFixed(6) + " svislice.bottom=" + svislice.box.min.y.toFixed(6) + " gap=" + gap.toFixed(6) + "mm");
  seamChecks.push({ seam: "leg1-sloupek-svislice", gap });
}
{
  const nosnikP0front = box("nosnik-sloupec0-patro0", null, -439)[0];
  const nosnikP0back = box("nosnik-sloupec0-patro0", null, -735)[0];
  const svislice = box("zadni-svislice-nad-zarezem", LEG_Z1)[0];
  for (const [label, n] of [["front(X=-439)", nosnikP0front], ["back(X=-735)", nosnikP0back]]) {
    if (n && svislice) {
      const gap = n.box.min.y - svislice.box.min.y;
      console.log(`sloupec0-patro0 ${label} vs leg1 novy seam: nosnik.bottom=${n.box.min.y.toFixed(4)} leg1.seam=${svislice.box.min.y.toFixed(4)} gap=${gap.toFixed(4)}mm (>=0 = OK)`);
      seamChecks.push({ seam: `sloupec0-patro0-${label}-vs-leg1`, gap });
    }
  }
}

console.log("\n=== KROK 6c: self-kolize (Box3, prah 2000mm3, zname vnorovaci pary preskoceny) ===");
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
  console.log(`--- self-kolize (${label}) ---`);
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
        list.push({ a: a.p.role, aX: a.p.position[0], aZ: a.p.position[2], b: b.p.role, bX: b.p.position[0], bZ: b.p.position[2], vol: +vol.toFixed(0) });
      }
    }
  }
  console.log(`podezrelych Box3 prekryvu (vol>2000mm3): ${susp} z ${cache.length * (cache.length - 1) / 2} paru.`);
  if (susp) console.log(JSON.stringify(list, null, 1));
  return { susp, list };
}
const baseline = selfCollide(partsOrig, "PUVODNI 285 - baseline");
const after = selfCollide(result285, "NOVA (prepocitana) data");
const newProblems = after.list.filter(x => !baseline.list.some(b => b.a === x.a && b.b === x.b && b.aX === x.aX && b.bX === x.bX));
console.log(`\nNOVE self-kolize zpusobene transformem: ${newProblems.length}`);
if (newProblems.length) console.log(JSON.stringify(newProblems, null, 1));

const report = {
  testedParts: testable.length, collisions, collidingList,
  seamChecks,
  baselineSelfSusp: baseline.susp, afterSelfSusp: after.susp, newProblems,
  log285, dorovnaniOverride,
};
fs.writeFileSync(`${OUT_DIR}/tmp_2026-09-12_285_verify_report.json`, JSON.stringify(report, null, 1));
console.log("\n=== VYSLEDEK ===");
console.log(`SAT kolizí: ${collisions}, self-kolizí po transformu: ${after.susp} (novych: ${newProblems.length}), seam gaps: ${seamChecks.map(s => s.seam + "=" + s.gap.toFixed(4)).join(", ")}`);
console.log("\nUlozeno: tmp_2026-09-12_285_verify_report.json");
