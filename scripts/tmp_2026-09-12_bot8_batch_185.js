// Prepocet kolizni bezpecnostni rezervy (2/20mm -> 10/30mm) na
// product_assemblies.id=185 ("Jumpy Crew Cab L3 K-119 A - boxy43-170x3-120x6"),
// podle shape_geometry_methods.id=11 "prepocet-kolizni-rezervy-existujici-sestavy"
// (verified_by robert) a JIZ ZJISTENYCH dat o nohach rodiny K-119 (Citroen
// Jumpy Crew Cab L3 CI19 2016-, car_model_id=43) - viz zadani teto session.
//
// VSTUP (dano zadanim, NEPROVADI se vlastni kolizni analyza noh):
//   deltaZ_predni_noha  = +8mm  (10mm - 2mm prepazka)
//   deltaY_vyrezova_noha = +10mm (30mm - 20mm podbeh)
//   2 Z-pozice noh (NE 3 jako u sesterske rodiny K-075/Doblo):
//     leg0 = -1522.500114440918  ("plain", kotvena k prepazce B, cely blok
//            vc. sloupce se hybe v Z)
//     leg1 =  -260.50011444091797 ("vyrez", nad podbehem, Z fixni, jen Y roste)
//   wall_x (X zadni-svislice-nad-zarezem na leg1) = -736 - potvrzuje, ze jde
//   o stejnou rodinu/geometrii jako u vsech 3 sourozencu (185/216/286).
//
// STRUKTURA 185 (67 dilu, 3x car_body_123/124/125 + 64 geometrickych, nactena
// primo z DB nize) - LISI SE od K-075 sablon (tmp_2026-09-12_bot8_batch_33x.js)
// jak v nazvech roli (zde "sloupec0"/"patroN" misto "col0"/"pN"), tak ve
// STRUKTURE sloupce: misto 1-2 spojnic na sloupec ma KAZDE patro 4 prycne
// "spojnice-sloupec0-patroN" (rovnomerne rozestavene podel cele delky
// nosniku, ne jen 2 kusy u konci) a 3 "eurobox-sloupec0-patroN" (misto 1
// centrovaneho boxu). Kazdy patro ma i 2 "nosnik-sloupec0-patroN" (na
// X=-440 a X=-736, stejne jako K-075 col0).
//
// ⭐ KRITICKY BOD prevzaty ze zadani (potvrzeny primo v datech nize, ne
// slepe prevzaty): na Z=leg1 EXISTUJE i samostatna "predni-svislice"
// (X=-440) + jeji vlastni "spojnice-dolni"(X=-526)/"spojnice-horni"
// (X=-588)/"cap"(X=-666)/"zaslepka"(x3) - VSECHNY tyto zustavaji BEZE ZMENY
// (ani Z, ani Y), presne jako "ostatni leg1 kusy" v K-075 sablone. JEN 3
// jmenovane role vyrezove trojice ("sloupek-pred-podbehem"/"zadni-svislice-
// nad-zarezem"/"pricka-uzavreni-vyrezu") dostavaji Y-posun. Zaslepky na
// leg1 NEJSOU na svaru (zmereno: Y=1193 a Y=924, obe mimo dosah zmeny -
// viz komentar u SEAM_ZASLEPKA_CHECK nize) -> beze zmeny, presne jako u
// jiz overenych K-075 sourozencu (336/337).
//
// SPOJNICE/EUROBOX PODEL NOSNIKU (NOVY PRIPAD, K-075 sablony ho neresily,
// protoze K-075 mela jen 1-2 kusy na patro, vzdy bud presne u nohy nebo
// presne uprostred): u 185 jsou 4 spojnice a 3 eurobox rozmistene podel
// CELE delky "nosnik-sloupec0-patroN" (leg0..leg1 rozpon). Nosnik samotny
// se NEMENI proporcionalne (jeho konec u leg1 je RIGIDNE fixni, konec u
// leg0 se posune o CELOU deltaZ, stred o polovinu, delka se zkrati o
// celou deltaZ - presne vzorec z K-075 sablon, tady beze zmeny principu).
// Spojnice/eurobox VISI na tomhle nosniku v ruznych bodech podel jeho
// delky - aby zustaly prisazene na "svem" miste nosniku (a nevznikla
// mezera/prekryv), aplikuje se STEJNY typ afinni transformace, jakou uz
// K-075 sablona pouziva pro "col0-ramp" logo stampy a "podelnik-*" rampy:
// frac = (z - leg1)/(leg0 - leg1) (0 u leg1, 1 u leg0), newZ = z + frac*deltaZ.
// Odvozeno primo: tohle JE presne stejna transformace, jakou pouziva i
// samotny nosnik vzorec pro svuj stred (frac=0.5 -> +deltaZ/2, shoduje se
// s "center += delta/2" - overeno algebraicky, viz AGENTS_LOG zapis k
// tomuto skriptu). Chyba oproti "presnemu" rigid-endpoint vzorci je v radu
// desetin mm (spojnice/eurobox nejsou kriticke svary podle kroku 6b
// procedury, jen vnitrni vyztuhy/police uvnitr sloupce), zanedbatelne.

const fs = require("fs");
const THREE = require("three");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const MeshBVHLib = require("/opt/konfigurator/webapp/js/three-mesh-bvh.js");
THREE.BufferGeometry.prototype.computeBoundsTree = MeshBVHLib.computeBoundsTree;
THREE.Mesh.prototype.raycast = MeshBVHLib.acceleratedRaycast;
const R = require("/opt/konfigurator/scripts/2026-09-11_glb_resolver.js");
const { execSync } = require("child_process");

const ASM_ID = 185;
const OUT_DIR = "/opt/konfigurator/scripts";

// ============================ 0) NACTENI Z DB ============================
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
    cur.execute('SELECT data FROM product_assemblies WHERE id=${ASM_ID}')
    print(cur.fetchone()['data'])
conn.close()
"`, { cwd: "/opt/konfigurator", maxBuffer: 1024 * 1024 * 50 }).toString();
const SRC_DATA = JSON.parse(dump);
const SRC_PARTS = SRC_DATA.parts;
console.log(`Nacteno id=${ASM_ID}: ${SRC_PARTS.length} dilu.`);

const parts = SRC_PARTS.map(p => JSON.parse(JSON.stringify(p))); // deep clone

// ============================ 1) KONSTANTY ============================
const LEG_Z = { leg0: -1522.500114440918, leg1: -260.50011444091797 };
const DELTA_Z_FRONT = 8;   // 10mm - 2mm (predni stena / prepazka B)
const DELTA_Y_VYREZ = 10;  // 30mm - 20mm (podbeh)
const T = 30;              // profil tloustka (pro pricka-uzavreni-vyrezu stred)
const EPS = 0.05;
const near = (a, b, eps) => Math.abs(a - b) < (eps == null ? EPS : eps);

// ---- 1a) over, ktere nohy z rodiny se v teto sestave skutecne vyskytuji ----
const zSet = parts.filter(p => p.position).map(p => p.position[2]);
const legsPresent = {};
for (const k of Object.keys(LEG_Z)) legsPresent[k] = zSet.some(z => near(z, LEG_Z[k], 1));
console.log("Nohy pritomne v id=" + ASM_ID + ":", JSON.stringify(legsPresent));
if (!legsPresent.leg0 || !legsPresent.leg1) {
  console.error("VAROVANI: sestava nema obe zname Z-pozice rodiny K-119 - pokracuji jen s pritomnymi.");
}

// ---- 1b) presna old-Y_new hodnota zmerena PRIMO z dat teto sestavy (ne z
// obecnych rodinnych dat) - top sloupku musi presne sedet na bottom svislice ----
function measureOldYnew() {
  const z = LEG_Z.leg1;
  const sloupek = parts.find(p => p.role === "sloupek-pred-podbehem" && near(p.position[2], z, 0.06));
  const svisl = parts.find(p => p.role === "zadni-svislice-nad-zarezem" && near(p.position[2], z, 0.06));
  if (!sloupek || !svisl) throw new Error("sloupek/svislice na leg1 nenalezeny");
  const topSloupek = sloupek.position[1] + sloupek.scale[1] * 500;
  const botSvisl = svisl.position[1] - svisl.scale[1] * 500;
  if (Math.abs(topSloupek - botSvisl) > 0.001) {
    throw new Error(`sloupek top (${topSloupek}) != svislice bottom (${botSvisl}) - svar neni presny, PROCEDURA NEPLATI beze zmeny.`);
  }
  return topSloupek;
}
const OLD_YNEW = measureOldYnew();
const NEW_YNEW = OLD_YNEW + DELTA_Y_VYREZ;
console.log("OLD_YNEW zmereno primo z dat:", OLD_YNEW, " NEW_YNEW:", NEW_YNEW);

// zaznam pro pripadny "seam zaslepka" tag-along check (viz hlavicka) - v
// datech 185 zadna zaslepka na Y blizkem OLD_YNEW/NEW_YNEW NENI (zmereno
// nize, informativni log), takze zadny dil zaslepka nepotrebuje Y-posun.
const seamZaslepky = parts.filter(p => p.role === "zaslepka" && near(p.position[2], LEG_Z.leg1, EPS) && near(p.position[1], OLD_YNEW, 5));
console.log("Zaslepky na leg1 blizko svaru (mely by byt 0):", seamZaslepky.length);

// ============================ 2) TRANSFORMACE (kroky 3 procedury) ========
let cFront = 0, cRampInterp = 0, cLeg1Y = 0, cUnchanged = 0;
const touched = [];
function logTouch(p, kind, before) {
  touched.push({
    role: p.role, part_id: p.part_id, kind,
    before: { position: before.position, scale: before.scale },
    after: { position: p.position.slice(), scale: p.scale.slice() },
  });
}

for (const p of parts) {
  if (!p.position) { continue; } // car_body_* - beze zmeny, mimo pocitadlo
  const [x, y, z] = p.position;
  const role = p.role || "";
  const before = { position: p.position.slice(), scale: p.scale.slice() };

  // 2.1) cely blok leg0 (plain, prepazka B): vse presne na Z leg0 NEBO role
  // uhelnik-noha0 (offset podel delky profilu, klasifikovano rolí) -> Z += delta
  if ((legsPresent.leg0 && near(z, LEG_Z.leg0, EPS)) || role === "uhelnik-noha0") {
    p.position = [x, y, z + DELTA_Z_FRONT];
    cFront++; logTouch(p, "front-leg0-Z-shift", before);
    continue;
  }

  // 2.2) uhelnik-noha1: shift v Y jen kdyz sedi presne na starem svaru
  // (OLD_YNEW) nebo OLD_YNEW+30 (druhe patro spojky), jinak beze zmeny
  // (floor/ceiling kotvene brackety seam vubec necitI). Z se u nich nikdy
  // nemeni (leg1 je Z-fixni). MUSI byt PRED obecnym near(leg1) blokem -
  // uhelnik ma Z posunute podel delky profilu, ne presne na LEG_Z.leg1.
  if (role === "uhelnik-noha1") {
    if (legsPresent.leg1 && (near(y, OLD_YNEW, 3) || near(y, OLD_YNEW + 30, 3))) {
      p.position = [x, y + DELTA_Y_VYREZ, z];
      cLeg1Y++; logTouch(p, "leg1-uhelnik-seam-Y-shift", before);
    } else {
      cUnchanged++;
    }
    continue;
  }

  // 2.3) nosnik-sloupec0-*: skutecna rampa pres CELY sloupec (leg0..leg1).
  // leg1-konec RIGIDNE fixni (0mm), leg0-konec jede s leg0 (+delta) ->
  // stred += delta/2, delka (scale[1]*1000) -= delta. (presne stejny
  // vzorec jako K-075 nosnik-col0, overeny 4x na sourozencich 332-337)
  if (role.startsWith("nosnik-sloupec0")) {
    const newZ = z + DELTA_Z_FRONT / 2;
    const newLenMm = p.scale[1] * 1000 - DELTA_Z_FRONT;
    p.position = [x, y, newZ];
    p.scale = [p.scale[0], newLenMm / 1000, p.scale[2]];
    cRampInterp++; logTouch(p, "nosnik-sloupec0-resize", before);
    continue;
  }

  // 2.4) spojnice-sloupec0-*/eurobox-sloupec0-*: vnitrni prvky rozmistene
  // podel delky nosniku (viz hlavicka - NOVY pripad oproti K-075 sablonam,
  // frac-interpolace Z podle pozice mezi leg1 [fixni] a leg0 [posouvajici
  // se]). Pouze position[2] se meni, X/Y (hloubka/vyska v ramci patra)
  // zustavaji stejne - tyhle dily se v Y/X vuci sloupci nehybou.
  if (role.startsWith("spojnice-sloupec0") || role.startsWith("eurobox-sloupec0")) {
    if (legsPresent.leg0 && legsPresent.leg1) {
      const frac = (z - LEG_Z.leg1) / (LEG_Z.leg0 - LEG_Z.leg1); // 0 u leg1, 1 u leg0
      const newZ = z + frac * DELTA_Z_FRONT;
      p.position = [x, y, newZ];
      cRampInterp++; logTouch(p, role.startsWith("spojnice") ? "spojnice-sloupec0-ramp-Z-interp" : "eurobox-sloupec0-ramp-Z-interp", before);
    } else {
      cUnchanged++;
    }
    continue;
  }

  // 2.5) leg1 presne (0.05mm): jen 3 jmenovane role vyrezove trojice
  // dostavaji Y-posun (podle vzorce id=6). Vse ostatni na teto Z
  // (predni-svislice, spojnice-dolni/-horni, cap, zaslepky) zustava BEZE
  // ZMENY (ani Z, ani Y) - presne podle ⭐ kritickeho bodu ze zadani.
  if (legsPresent.leg1 && near(z, LEG_Z.leg1, EPS)) {
    if (role === "sloupek-pred-podbehem") {
      const oldHeight = p.scale[1] * 1000, floorY = y - oldHeight / 2;
      const newHeight = NEW_YNEW - floorY;
      p.position = [x, floorY + newHeight / 2, z];
      p.scale = [p.scale[0], newHeight / 1000, p.scale[2]];
      cLeg1Y++; logTouch(p, "leg1-sloupek-resize", before);
    } else if (role === "zadni-svislice-nad-zarezem") {
      const oldHeight = p.scale[1] * 1000, topY = y + oldHeight / 2;
      const newHeight = topY - NEW_YNEW;
      p.position = [x, NEW_YNEW + newHeight / 2, z];
      p.scale = [p.scale[0], newHeight / 1000, p.scale[2]];
      cLeg1Y++; logTouch(p, "leg1-svislice-resize", before);
    } else if (role === "pricka-uzavreni-vyrezu") {
      p.position = [x, NEW_YNEW + T / 2, z];
      cLeg1Y++; logTouch(p, "leg1-pricka-reposition", before);
    } else {
      cUnchanged++; // predni-svislice, spojnice-dolni/-horni, cap, zaslepka - beze zmeny
    }
    continue;
  }

  // 2.6) vse ostatni - beze zmeny (nemelo by nic zbyt, ale pro jistotu)
  cUnchanged++;
}

console.log("\n=== KROK 3 (delty) souhrn ===");
console.log("front leg0 Z-shift (+8mm):", cFront);
console.log("ramp interpolace (nosnik/spojnice/eurobox):", cRampInterp);
console.log("leg1 Y-shift (trio + uhelnik):", cLeg1Y);
console.log("beze zmeny:", cUnchanged);
const withPos = parts.filter(p => p.position).length;
console.log("celkem s pozici:", withPos, "= soucet", cFront + cRampInterp + cLeg1Y + cUnchanged);

// ============================ 3) KROK 4-5: DOROVNANI ============================
console.log("\n=== KROK 4-5 (dorovnani) ===");
const HALF_PROFILE = 15;
const allFloorShifts = [];
const floorRe = /^nosnik-sloupec0-patro(\d+)$/;
const floorIdxSet = new Set();
for (const p of parts) { const m = floorRe.exec(p.role || ""); if (m) floorIdxSet.add(Number(m[1])); }
const floors = [...floorIdxSet].map(idx => {
  const members = parts.filter(p => p.role === `nosnik-sloupec0-patro${idx}`);
  const y = Math.min(...members.map(p => p.position[1]));
  return { idx, y };
}).sort((a, b) => a.y - b.y);
console.log("Nalezena patra sloupce0 (podle nosnik-sloupec0-patroN):", floors.map(f => `p${f.idx}(Y=${f.y})`).join(", "));

// limitujici noha: jedina vyrezova noha pritomna je leg1
const limitingYnew = NEW_YNEW;
if (!floors.length) {
  console.log("Zadna patra nenalezena - dorovnani se netyka.");
} else {
  const lowest = floors[0];
  const bottomEdge = lowest.y - HALF_PROFILE;
  console.log(`Nejnizsi patro p${lowest.idx} Y=${lowest.y}, spodni hrana=${bottomEdge.toFixed(4)}, limitujici novy Y_new(leg1)=${limitingYnew.toFixed(4)}`);
  if (bottomEdge >= limitingYnew - 1e-6) {
    console.log(`Spodni hrana (${bottomEdge.toFixed(4)}) >= novy Y_new (${limitingYnew.toFixed(4)}) - LUZKO NEVISÍ, dorovnani NENI potreba.`);
  } else {
    const missing = limitingYnew - bottomEdge;
    console.log(`LUZKO VISÍ VE VZDUCHU o ${missing.toFixed(4)}mm - aplikuji dorovnani (krok 5).`);
    const N = floors.length;
    for (let i = 0; i < N; i++) {
      const shift = N > 1 ? missing * (N - 1 - i) / (N - 1) : missing;
      const floorIdx = floors[i].idx;
      console.log(`   patro p${floorIdx} (i=${i}): shift = ${shift.toFixed(4)}mm`);
      allFloorShifts.push({ floorIdx, shift, floorOldY: floors[i].y });
      const re = new RegExp(`^(nosnik|spojnice|eurobox)-sloupec0-patro${floorIdx}$`);
      for (const p of parts) {
        if (!re.test(p.role || "")) continue;
        const b2 = { position: p.position.slice(), scale: p.scale.slice() };
        p.position = [p.position[0], p.position[1] + shift, p.position[2]];
        logTouch(p, `patro${floorIdx}-dorovnani`, b2);
      }
    }
  }
}

fs.writeFileSync(`${OUT_DIR}/tmp_2026-09-12_bot8_batch_185_parts.json`, JSON.stringify(parts));
fs.writeFileSync(`${OUT_DIR}/tmp_2026-09-12_bot8_batch_185_touched.json`, JSON.stringify(touched, null, 1));
console.log(`\nUlozeno: tmp_2026-09-12_bot8_batch_185_parts.json (${parts.length} dilu), touched.json (${touched.length} zmenenych zaznamu).`);

// ============================ 4) KROK 6: OVERENI ============================
console.log("\n\n=== KROK 6a: SAT test proti realne karoserii ===");
const KAT = "/opt/konfigurator/webapp/katalog/";
function loadWall(suf) {
  const m = parseGlbMesh(KAT + "car_bodies/Citroën_Jumpy_CI19_2016-" + suf + ".glb");
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
  if (!glbPath) return null;
  const m = parseGlbMesh(glbPath);
  m.position.set(...p.position);
  m.quaternion.set(...p.quaternion);
  m.scale.set(...p.scale);
  m.updateMatrixWorld(true);
  return m;
}

const testable = parts.filter(p => !String(p.part_id || "").startsWith("car_body_") && !String(p.role || "").startsWith("kontrolni-pomucka"));
let satCollisions = 0, satSkipped = 0;
const satList = [];
const meshCache = [];
for (const p of testable) {
  if (R.jeKaroserie(p.part_id)) { satSkipped++; continue; }
  const glbPath = R.glbPath(p.part_id);
  if (!glbPath) { throw new Error("CHYBI GLB mapovani pro part_id=" + p.part_id + " role=" + p.role + " - NEZAPISOVAT, mereni by bylo nedoveryhodne."); }
  const mesh = partMesh(p);
  meshCache.push({ p, mesh });
  if (collidesWithWallsReal(mesh)) { satCollisions++; satList.push({ role: p.role, part_id: p.part_id, position: p.position }); }
}
console.log(`SAT: ${satCollisions}/${meshCache.length} koliduje s realnou karoserii (GLB mapa ${R.velikostMapy()} zaznamu, ${testable.length - meshCache.length} preskoceno jako karoserie).`);
if (satCollisions) console.log("KOLIDUJICI:", JSON.stringify(satList, null, 1));

console.log("\n=== KROK 6b: presna mezera na kazdem posunutem/dorovnanem svu ===");
const seamChecks = [];
{
  const sloupek = parts.find(p => p.role === "sloupek-pred-podbehem" && near(p.position[2], LEG_Z.leg1, EPS));
  const svisl = parts.find(p => p.role === "zadni-svislice-nad-zarezem" && near(p.position[2], LEG_Z.leg1, EPS));
  const sMesh = partMesh(sloupek), vMesh = partMesh(svisl);
  const sBox = new THREE.Box3().setFromObject(sMesh), vBox = new THREE.Box3().setFromObject(vMesh);
  const gap = vBox.min.y - sBox.max.y;
  console.log(`leg1 (sloupek/svislice svar): sloupek top Box3.max.y=${sBox.max.y.toFixed(4)}  svislice bottom Box3.min.y=${vBox.min.y.toFixed(4)}  gap=${gap.toFixed(4)}mm`);
  seamChecks.push({ seam: "leg1-sloupek-svislice", gap, requireZero: true });
}
if (floors.length) {
  const lowestIdx = floors[0].idx;
  const nosnikP = parts.filter(p => p.role === `nosnik-sloupec0-patro${lowestIdx}`);
  let minY = Infinity;
  for (const p of nosnikP) { const b = new THREE.Box3().setFromObject(partMesh(p)); minY = Math.min(minY, b.min.y); }
  const gap2 = minY - limitingYnew;
  console.log(`nejnizsi patro p${lowestIdx}: Box3.min.y=${minY.toFixed(4)}  limitujici Y_new(leg1)=${limitingYnew.toFixed(4)}  gap=${gap2.toFixed(4)}mm ${allFloorShifts.length ? "(po dorovnani)" : "(dorovnani nebylo potreba - jen informativni clearance, NENI to svar vyzadujici 0.000mm, proto se nepocita do gaps_bad)"}`);
  // Tenhle zaznam je "0mm pozadovana mezera" JEN pokud doslo k dorovnani
  // (krok 5) - jinak jde jen o informativni clearance (luzko proste sedi
  // vysoko nad novou Y_new, zadna zmena se na nem neprovadela), takze ho
  // do "requireZero" seznamu (gaps_bad) NEPOCITAME kdyz dorovnani nebehelo.
  seamChecks.push({ seam: `patro${lowestIdx}-vs-leg1-Ynew`, gap: gap2, requireZero: allFloorShifts.length > 0 });
}
// leg0-konec nosniku vs predni-svislice (T-styl dosed, musi zustat 0mm i po zkraceni)
{
  const svislice = parts.find(p => p.role === "predni-svislice" && near(p.position[2], LEG_Z.leg0 + DELTA_Z_FRONT, EPS));
  const nosnik440 = parts.find(p => p.role === "nosnik-sloupec0-patro0" && near(p.position[0], -440, 1));
  if (svislice && nosnik440) {
    const svBox = new THREE.Box3().setFromObject(partMesh(svislice));
    const noBox = new THREE.Box3().setFromObject(partMesh(nosnik440));
    // nosnik bezi podel Z, "leg0" konec je min.z (nejzapornejsi)
    const gap3 = svBox.max.z - noBox.min.z; // svislice profil konci na max.z smerem k noze? over obema smery
    console.log(`leg0-konec nosnik-sloupec0-patro0(X=-440) vs predni-svislice(leg0): svislice Box3 z=[${svBox.min.z.toFixed(4)},${svBox.max.z.toFixed(4)}]  nosnik Box3 z=[${noBox.min.z.toFixed(4)},${noBox.max.z.toFixed(4)}]`);
    const gapReal = Math.max(svBox.min.z, noBox.min.z) > Math.min(svBox.max.z, noBox.max.z)
      ? (svBox.min.z - noBox.max.z >= 0 ? svBox.min.z - noBox.max.z : noBox.min.z - svBox.max.z)
      : -(Math.min(svBox.max.z, noBox.max.z) - Math.max(svBox.min.z, noBox.min.z)); // zaporne = prekryv
    console.log(`   gap/prekryv (zaporne=prekryv) = ${gapReal.toFixed(4)}mm`);
    seamChecks.push({ seam: "leg0-nosnik-vs-svislice", gap: gapReal, requireZero: true });
  }
}

console.log("\n=== KROK 6c: self-kolize (Box3, vsechny dvojice krome znamych vnorovani) ===");
const KNOWN_NESTING = [
  (a, b) => (a.startsWith("eurobox") && (b.startsWith("nosnik") || b.startsWith("spojnice"))) || (b.startsWith("eurobox") && (a.startsWith("nosnik") || a.startsWith("spojnice"))),
  (a, b) => (a.startsWith("zaslepka") && (b === "predni-svislice" || b === "cap" || b === "zadni-svislice-nad-zarezem" || b === "zadni-svislice-dolni")) || (b.startsWith("zaslepka") && (a === "predni-svislice" || a === "cap" || a === "zadni-svislice-nad-zarezem" || a === "zadni-svislice-dolni")),
  (a, b) => (a.startsWith("logo-ochrana-vypln") && !b.startsWith("logo-ochrana")) || (b.startsWith("logo-ochrana-vypln") && !a.startsWith("logo-ochrana")),
  (a, b) => (a.startsWith("logo-ochrana-logo") && !b.startsWith("logo-ochrana")) || (b.startsWith("logo-ochrana-logo") && !a.startsWith("logo-ochrana")),
];
function isKnownNesting(a, b) { return KNOWN_NESTING.some(f => f(a, b)); }

let selfSusp = 0;
const selfList = [];
const box3s = meshCache.map(({ p, mesh }) => ({ p, box: new THREE.Box3().setFromObject(mesh) }));
for (let i = 0; i < box3s.length; i++) {
  for (let j = i + 1; j < box3s.length; j++) {
    const a = box3s[i], b = box3s[j];
    if (a.p.role === b.p.role) continue;
    const ra = a.p.role || "", rb = b.p.role || "";
    if (isKnownNesting(ra, rb)) continue;
    if (!a.box.intersectsBox(b.box)) continue;
    const ix = Math.min(a.box.max.x, b.box.max.x) - Math.max(a.box.min.x, b.box.min.x);
    const iy = Math.min(a.box.max.y, b.box.max.y) - Math.max(a.box.min.y, b.box.min.y);
    const iz = Math.min(a.box.max.z, b.box.max.z) - Math.max(a.box.min.z, b.box.min.z);
    const vol = Math.max(0, ix) * Math.max(0, iy) * Math.max(0, iz);
    if (vol > 2000) {
      selfSusp++;
      selfList.push({ a: ra, b: rb, vol: +vol.toFixed(0) });
      console.log(`   Box3 prekryv: ${ra} <-> ${rb}  vol=${vol.toFixed(0)}mm3`);
    }
  }
}
console.log(`podezrelych Box3 prekryvu (vol>2000mm3, mimo znama vnorovani, mimo stejnou roli): ${selfSusp} z ${box3s.length * (box3s.length - 1) / 2} paru`);

const report = {
  asm: ASM_ID, legsPresent, OLD_YNEW, NEW_YNEW,
  counts: { cFront, cRampInterp, cLeg1Y, cUnchanged, total: withPos },
  floorShifts: allFloorShifts,
  satMeasured: meshCache.length, satCollisions, satList,
  seamChecks,
  self_collisions: selfSusp, selfList,
  touchedCount: touched.length,
  gaps_bad: seamChecks.filter(s => s.requireZero && Math.abs(s.gap) > 0.001).length,
};
fs.writeFileSync(`${OUT_DIR}/tmp_2026-09-12_bot8_batch_185_report.json`, JSON.stringify(report, null, 1));
console.log("\n\n=== VYSLEDEK ===");
console.log(`SAT kolizí s karoserií: ${satCollisions}`);
console.log(`Self-kolizí (mimo znama vnorovani): ${selfSusp}`);
console.log(`Seam gaps: ${seamChecks.map(s => `${s.seam}=${s.gap.toFixed(4)}mm`).join(", ")}`);
console.log(`Gaps mimo toleranci (0.001mm): ${report.gaps_bad}`);
console.log(`\nUlozeno: tmp_2026-09-12_bot8_batch_185_report.json`);
