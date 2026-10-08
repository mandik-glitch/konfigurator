// Prepocet kolizni rezervy (2/20mm -> 10/30mm) na product_assemblies.id=286
// (rodina K-119 = Citroen Jumpy Crew Cab L3, karoserie_kod K-119), podle
// procedury shape_geometry_methods.id=11
// "prepocet-kolizni-rezervy-existujici-sestavy".
//
// Vstupni fakta o nohach teto rodiny (dana zadanim - viz task input, family
// K-119, zjisteno predchozim krokem, NEPROVADI se vlastni kolizni re-analyza):
//   leg0 Z=-1522.500114440918   ("plain": predni-svislice + zadni-svislice-dolni + cap + spojnice-dolni/horni)
//   leg1 Z=-260.50011444091797  (predni-svislice PLAIN + vyrezova trojice SOUCASNE na stejnem Z)
//   OLD_YNEW leg1 = 141.00018310546875 (svar sloupek-pred-podbehem / zadni-svislice-nad-zarezem)
//   wall_x (zadni-svislice-nad-zarezem X) = -736
//
// STRUKTURA id=286 OVERENA PRIMO V DB pred pouzitim tohoto skriptu (viz
// grep vypis role+position) - role-nazvy JSOU DOSLOVA STEJNE jako uz drive
// hotova a overena rodina K-118 (product_assemblies.id=184, take Citroen
// Jumpy Crew Cab, jen L2 misto L3): "predni-svislice","spojnice-dolni",
// "spojnice-horni","zadni-svislice-dolni","cap","zaslepka",
// "sloupek-pred-podbehem","pricka-uzavreni-vyrezu","zadni-svislice-nad-zarezem",
// "uhelnik-noha0","uhelnik-noha1","nosnik-sloupec0-patroN",
// "spojnice-sloupec0-patroN","eurobox-sloupec0-patroN" (N=0,1,2). Presne
// stejna topologie: JEDEN sloupec (sloupec0) mezi leg0 a leg1, leg1 nese
// SOUCASNE plnou (predni-svislice) i vyrezovou (trojice) cast na stejnem Z -
// to je presne pripad, ktery uz resi a MA SAMOSTATNE OVERENOU (self-check
// proti hotovemu paru K-075 279->340) genericka funkce transformAssembly()
// v scripts/tmp_2026-09-12_bot8_batch_184.js. Proto ji tady PRIMO
// ZNOVUPOUZIVAM (require), misto psani nove - stejne transform pravidlo:
//   - leg0 (cistse plna, Z=-1522.5): VSECHNY dily s Z na tomto Z (predni-
//     svislice/cap/spojnice-dolni/spojnice-horni/zadni-svislice-dolni/
//     zaslepka) + uhelnik-noha0 (vsech 7, klasifikovano podle role, ne Z) ->
//     cele +deltaZ (8mm).
//   - leg1 (sdileny Z=-260.5): plna cast (predni-svislice/cap/spojnice-dolni/
//     spojnice-horni/zaslepka) NA TOMTO Z zustava BEZE ZMENY (ani Z, ani Y) -
//     empiricky overeno na 279->340 (K-075) i uz aplikovano na 184 (K-118),
//     stejna topologie. Meni se JEN vyrezova trojice (sloupek-pred-podbehem/
//     zadni-svislice-nad-zarezem/pricka-uzavreni-vyrezu) podle vzorce
//     shape_geometry_methods.id=6, a uhelnik-noha1 JEN ty kusy, co sedi na
//     starem svaru (Y=141.0002) nebo +30mm odsazeni (Y=171.0002).
//   - sloupec (nosnik/spojnice/eurobox sloupec0-patroN): rozpeti leg0..leg1,
//     stred +deltaZ/2, nosnik delka -deltaZ, spojnice bud cele +deltaZ
//     (konec u leg0) / beze zmeny Z (konec u leg1) / +deltaZ/2 (stred rozpeti).
//   - krok 4 (dorovnani pater): VYPOCITANO NIZE primo z dat 286 (ne
//     prevzato z 184) - vyslo NENI POTREBA (velka rezerva, viz vystup).
//
// NEZAPISUJE primo do puvodniho radku 286 (nikdy) - vysledek jde vyhradne
// do NOVEHO radku (scripts/tmp_2026-09-12_bot8_insert_286.py, az po zelenem
// verify).

const fs = require("fs");
const THREE = require("three");
const { execSync } = require("child_process");
const { transformAssembly, DELTA_Z, DELTA_Y } = require("./tmp_2026-09-12_bot8_batch_184.js");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const MeshBVHLib = require("/opt/konfigurator/webapp/js/three-mesh-bvh.js");
THREE.BufferGeometry.prototype.computeBoundsTree = MeshBVHLib.computeBoundsTree;
THREE.Mesh.prototype.raycast = MeshBVHLib.acceleratedRaycast;
const R = require("/opt/konfigurator/scripts/2026-09-11_glb_resolver.js");

const SCRATCH = "/tmp/claude-0/-opt-konfigurator/c0c788fb-0783-4d56-adb5-543ba6b0dda8/scratchpad";
const near = (a, b, eps) => Math.abs(a - b) < (eps == null ? 0.05 : eps);

// ---- nacti data primo z DB (cerstve, ne z cache) ----
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
cur.execute("SELECT data FROM product_assemblies WHERE id=286")
print(json.dumps(json.loads(cur.fetchone()["data"])["parts"]))
conn.close()
`;
fs.writeFileSync("/tmp/_dump_286.py", dumpPy);
const parts286 = JSON.parse(execSync("api/venv/bin/python3 /tmp/_dump_286.py", { cwd: "/opt/konfigurator", maxBuffer: 1024 * 1024 * 40 }).toString());
console.log("Nacteno primo z DB, dilu:", parts286.length);

const LEG_Z = { leg0: -1522.500114440918, leg1: -260.50011444091797 };
const OLD_YNEW_LEG1 = 141.00018310546875;

// ---- krok 2 procedury: over, ktere nohy z rodinnych dat se v 286 SKUTECNE vyskytuji ----
const has = (role, z) => parts286.some(p => p.role === role && near(p.position[2], z, 1));
console.log("\n=== Krok 2: overeni pritomnosti noh (tolerance 1mm) ===");
console.log("leg0 (plain, Z=" + LEG_Z.leg0 + ") - predni-svislice pritomna:", has("predni-svislice", LEG_Z.leg0));
console.log("leg0 - zadni-svislice-dolni pritomna:", has("zadni-svislice-dolni", LEG_Z.leg0));
console.log("leg1 (vyrez, Z=" + LEG_Z.leg1 + ") - predni-svislice (plna cast) pritomna:", has("predni-svislice", LEG_Z.leg1));
console.log("leg1 - sloupek-pred-podbehem pritomen:", has("sloupek-pred-podbehem", LEG_Z.leg1));
console.log("leg1 - zadni-svislice-nad-zarezem pritomna:", has("zadni-svislice-nad-zarezem", LEG_Z.leg1));
console.log("leg1 - pricka-uzavreni-vyrezu pritomna:", has("pricka-uzavreni-vyrezu", LEG_Z.leg1));

// ---- krok 4: over jestli je potreba dorovnani pater ----
const nosnikPatro0 = parts286.filter(p => p.role === "nosnik-sloupec0-patro0");
const floorEdge = Math.min(...nosnikPatro0.map(p => p.position[1])) - 15; // polovina tloustky profilu 30mm
const newYnewLeg1 = OLD_YNEW_LEG1 + DELTA_Y;
const visiVeVzduchu = floorEdge < newYnewLeg1;
console.log("\n=== Krok 4: dorovnani pater ===");
console.log(`spodni hrana nejnizsiho patra (nosnik-sloupec0-patro0): floorEdge=${floorEdge}mm`);
console.log(`novy Y_new nohy1 (vyrezova, po +${DELTA_Y}mm): ${newYnewLeg1}mm`);
console.log(`visi_ve_vzduchu = ${visiVeVzduchu} (floorEdge < newYnewLeg1) -> ${visiVeVzduchu ? "DOROVNANI POTREBA (krok 5)" : "dorovnani NENI potreba"}`);
const dorovnaniOverride = visiVeVzduchu ? null : 0;

// ---- krok 3-5: aplikuj transform (genericka funkce prevzata z 184, viz hlavicka) ----
const cfg = {
  legZ0: LEG_Z.leg0,
  sharedLegs: [{ z: LEG_Z.leg1, uhelnikRole: "uhelnik-noha1", oldYnew: OLD_YNEW_LEG1 }],
  colPrefix: "sloupec0",
  dorovnaniOverride,
};
const { parts: partsNew, log } = transformAssembly(parts286, cfg);
console.log("\n=== Transform log ===");
console.log(JSON.stringify(log, null, 1));
console.log("celkem dilu:", parts286.length, "-> vystup:", partsNew.length);
if (partsNew.length !== parts286.length) throw new Error("POCET DILU NESEDI - STOP");

fs.writeFileSync(SCRATCH + "/assembly286_parts_new.json", JSON.stringify(partsNew));
console.log("\nUlozeno: assembly286_parts_new.json");

// ============================================================
// KROK 6: OVERENI (POVINNE)
// ============================================================
console.log("\n\n=== KROK 6: OVERENI ===");

const KAT = "/opt/konfigurator/webapp/katalog/";
const BASE = "Citroën_Jumpy_CI19_2016-"; // POZOR: CI19, ne CI18 (jiny Jumpy model) - viz task input notes
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
const testable = partsNew.filter(p => !R.jeKaroserie(p.part_id) && !(p.role || "").startsWith("kontrolni-pomucka"));
let collisions = 0;
const collidingList = [];
const meshCache = [];
for (const p of testable) {
  const mesh = partMesh(p);
  meshCache.push({ p, mesh });
  if (collidesWithWallsReal(mesh)) { collisions++; collidingList.push({ role: p.role, part_id: p.part_id, position: p.position }); }
}
console.log(`\n--- a) SAT test (hranovy raycasting proti realne GLB karoserii ${BASE}) ---`);
console.log(`${collisions}/${testable.length} koliduje (z celkem ${partsNew.length} dilu, ${partsNew.length - testable.length} car_body_*/pomucka vynechano).`);
if (collisions) console.log("KOLIDUJICI:", JSON.stringify(collidingList, null, 1));

// ---- b) presna mezera na posunutem svaru (leg1 vyrez) ----
function box(role, zApprox, xApprox) {
  const cands = meshCache.filter(({ p }) => p.role === role && (zApprox == null || Math.abs(p.position[2] - zApprox) < 2) && (xApprox == null || Math.abs(p.position[0] - xApprox) < 2));
  return cands.map(({ p, mesh }) => ({ p, box: new THREE.Box3().setFromObject(mesh) }));
}
console.log("\n--- b) presna mezera na posunutem svaru (0.000mm ocekavano) ---");
let seamGap = null;
{
  const sloupek = box("sloupek-pred-podbehem", LEG_Z.leg1)[0];
  const svislice = box("zadni-svislice-nad-zarezem", LEG_Z.leg1)[0];
  if (sloupek && svislice) {
    seamGap = svislice.box.min.y - sloupek.box.max.y;
    console.log("leg1 seam: sloupek.top=" + sloupek.box.max.y.toFixed(6) + " svislice.bottom=" + svislice.box.min.y.toFixed(6) + " gap=" + seamGap.toFixed(6) + "mm");
  } else {
    console.log("leg1 seam: DILY NENALEZENY (sloupek=" + !!sloupek + " svislice=" + !!svislice + ")");
  }
}
{
  const nosnikP0front = box("nosnik-sloupec0-patro0", null, -439)[0];
  const nosnikP0back = box("nosnik-sloupec0-patro0", null, -735)[0];
  const svislice = box("zadni-svislice-nad-zarezem", LEG_Z.leg1)[0];
  for (const [label, n] of [["front(X=-439)", nosnikP0front], ["back(X=-735)", nosnikP0back]]) {
    if (n && svislice) {
      const gap = n.box.min.y - svislice.box.min.y;
      console.log(`sloupec0-patro0 ${label} vs leg1 novy seam: nosnik.bottom=${n.box.min.y.toFixed(4)} leg1.seam=${svislice.box.min.y.toFixed(4)} gap=${gap.toFixed(4)}mm (>=0 = OK, nevisi ve vzduchu)`);
    }
  }
}

// ---- c) self-kolize - Box3, baseline (puvodni 286) vs po transformaci ----
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
  console.log(`\n--- c) self-kolize (${label}, Box3, prah 2000mm3 mimo zname vnorovaci pary) ---`);
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
const baseline = selfCollide(parts286, "PUVODNI 286 - baseline");
const after = selfCollide(partsNew, "NOVA (prepocitana) data");
const newProblems = after.list.filter(x => !baseline.list.some(b => b.a === x.a && b.b === x.b && b.aX === x.aX && b.bX === x.bX));
console.log(`\nNOVE self-kolize zpusobene transformem (nebyly v baseline): ${newProblems.length}`);
if (newProblems.length) console.log(JSON.stringify(newProblems, null, 1));

// ---- verdikt ----
const seamOk = seamGap != null && Math.abs(seamGap) < 0.001;
const verdict = (collisions === 0 && seamOk && newProblems.length === 0) ? "OK" : "FAIL";
console.log(`\n=== VERDIKT: ${verdict} (sat_collisions=${collisions}, seam_gap=${seamGap}, new_self_collisions=${newProblems.length}) ===`);

fs.writeFileSync(SCRATCH + "/assembly286_verify_report.json", JSON.stringify({
  assembly_id: 286,
  verdict,
  sat_collisions: collisions,
  collidingList,
  seam_gap_mm: seamGap,
  baselineSelfSusp: baseline.susp,
  afterSelfSusp: after.susp,
  newProblems,
  dorovnani_needed: visiVeVzduchu,
  transform_log: log,
}, null, 1));
console.log("\nUlozeno: assembly286_verify_report.json");
