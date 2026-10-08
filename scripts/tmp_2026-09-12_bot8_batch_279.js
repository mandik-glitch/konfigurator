// Prepocet kolizni bezpecnostni rezervy JEDNE existujici sestavy
// (product_assemblies.id=279, K-075-EB-30-C-0063-0-0) podle
// shape_geometry_methods.id=11 "prepocet-kolizni-rezervy-existujici-sestavy"
// (verified_by robert): predni stena 2mm->10mm, podbeh 20mm->30mm.
//
// VSTUP: fresh dump 279 (scripts/tmp_2026-09-12_bot8_dump_279.py ->
// scratchpad/assembly279_fresh.json). VYSTUP: transformovane parts pole +
// verifikacni report (SAT vs realna GLB karoserie + mesh self-kolize).
// NEZAPISUJE do DB - to dela scripts/tmp_2026-09-12_bot8_insert_279.py
// az po tom, co tenhle skript ohlasi 0 kolizi.
//
// Delty jsou PRESNE ARITMETICKE KONSTANTY (krok 1 procedury):
//   deltaZ_predni_noha  = novy_backoff_predni(10) - stary(2)   = +8mm
//   deltaY_vyrezova_noha= novy_backoff_podbeh(30) - stary(20)  = +10mm
//
// Pravidla (ported + doplneno o krok 4/5 "dorovnani luzek", ktery v
// predchozim rozpracovanem pokusu (tmp_2026-09-12_bot8_predelat_k075_c_
// 10_30.js, tato session, nezapsano do DB) chybel - viz KONTROLA NIZE
// proti jiz hotove/schvalene sestave id=340 (stejna karoserie/sloupce,
// jen jiny box-obsah), kde presne tenhle dorovnavaci posun (+10/+6.667/
// +3.333/+0mm na patra col0-p0..p3) uz je aplikovany a schvaleny.

const fs = require("fs");
const path = require("path");
const THREE = require("three");
const MeshBVHLib = require("/opt/konfigurator/webapp/js/three-mesh-bvh.js");
THREE.BufferGeometry.prototype.computeBoundsTree = MeshBVHLib.computeBoundsTree;
THREE.BufferGeometry.prototype.disposeBoundsTree = MeshBVHLib.disposeBoundsTree;
THREE.Mesh.prototype.raycast = MeshBVHLib.acceleratedRaycast;
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const R = require("/opt/konfigurator/scripts/2026-09-11_glb_resolver.js");
const MK = require("/opt/konfigurator/scripts/2026-09-11_mesh_kolize_lib.js");

const SCRATCH = "/tmp/claude-0/-opt-konfigurator/c0c788fb-0783-4d56-adb5-543ba6b0dda8/scratchpad";
const SRC = JSON.parse(fs.readFileSync(SCRATCH + "/assembly279_fresh.json", "utf8"));
const META = SRC.meta;
const DATA = SRC.data;
const partsOrig = DATA.parts;

console.log(`Nacteno id=${META.id} kod_sestavy=${META.kod_sestavy} profil_mm=${META.profil_mm} dilu=${partsOrig.length}`);

// === KROK 2 procedury (POSTUP bod 2): over, ktere leg pozice z VSTUPNICH
// DAT se v teto konkretni sestave skutecne vyskytuji (tolerance ~1mm) ===
const INPUT_LEGS = [
  { z: -1358.5025482177734, type: "plain", old_y_new: null },
  { z: -898.5025482177734, type: "plain", old_y_new: null },
  { z: -898.5025482177734, type: "vyrez", old_y_new: 101.50017929077148 },
  { z: -34.50254821777344, type: "plain", old_y_new: null },
  { z: -34.50254821777344, type: "vyrez", old_y_new: 53.500179290771484 },
];
const near = (a, b, eps) => Math.abs(a - b) < eps;
for (const L of INPUT_LEGS) {
  const hit = partsOrig.some(p => near(p.position[2], L.z, 1));
  console.log(`  leg Z=${L.z.toFixed(3)} type=${L.type}: ${hit ? "PRITOMNA" : "CHYBI"} v id=${META.id}`);
  if (!hit) throw new Error(`Leg Z=${L.z} type=${L.type} z VSTUPNICH DAT v sestave 279 chybi - nutne prehodnotit.`);
}
// Distinct Z (3 legove pozice: leg0/leg1/leg2, Z rostouci)
const LEG_Z = { leg0: -1358.5025482177734, leg1: -898.5025482177734, leg2: -34.50254821777344 };
const OLD_YNEW = { leg1: 101.50017929077148, leg2: 53.500179290771484 };
const DELTA_Z_FRONT = 8;   // 10-2
const DELTA_Y_VYREZ = 10;  // 30-20
const T = META.profil_mm / 2; // 15mm - polovina tloustky profilu (dana metadaty radku, ne natvrdo)
const EPS = 0.01;

// Sanity: over Y_new primo v datech (seam sloupek/svislice) - cteni
// existujicich hodnot, ne nova kolizni detekce.
for (const legName of ["leg1", "leg2"]) {
  const z = LEG_Z[legName];
  const sloupek = partsOrig.find(p => p.role === "sloupek-pred-podbehem" && near(p.position[2], z, 0.05));
  const svisl = partsOrig.find(p => p.role === "zadni-svislice-nad-zarezem" && near(p.position[2], z, 0.05));
  const topSloupek = sloupek.position[1] + sloupek.scale[1] * 1000 / 2;
  const botSvisl = svisl.position[1] - svisl.scale[1] * 1000 / 2;
  if (Math.abs(topSloupek - OLD_YNEW[legName]) > 0.01 || Math.abs(botSvisl - OLD_YNEW[legName]) > 0.01) {
    throw new Error(`${legName}: seam v datech (sloupek top=${topSloupek}, svislice bottom=${botSvisl}) nesedi s dodanym OLD_YNEW=${OLD_YNEW[legName]}`);
  }
}
console.log("  Sanity OK: OLD_YNEW.leg1/leg2 odpovidaji realnemu svaru v datech 279.\n");

// === PASS 1: krok 3 procedury - zakladni delty ===
const LOGO_IDX_GROUP = { 0: "col0", 1: "front", 2: "col1", 3: "leg2-fixed", 4: "col0", 5: "front", 6: "col0", 7: "col1", 8: "front" };
function logoGroup(role) {
  const m = /^logo-ochrana-(?:vypln|logo)-(\d+)$/.exec(role);
  return m ? LOGO_IDX_GROUP[Number(m[1])] : null;
}

const parts = partsOrig.map(p => JSON.parse(JSON.stringify(p)));
let cFront = 0, cCol0Interp = 0, cLeg1 = 0, cLeg2 = 0, cUnchanged = 0, cDorovnani = 0;
const touched = new Set();

for (const p of parts) {
  if (R.jeKaroserie(p.part_id)) { cUnchanged++; continue; } // car_body_* - nikdy se nehybe
  const [x, y, z] = p.position;
  const role = p.role || "";
  const lg = logoGroup(role);

  if (near(z, LEG_Z.leg0, 0.05) || role === "uhelnik-noha0" || lg === "front") {
    p.position = [x, y, z + DELTA_Z_FRONT]; cFront++; touched.add("front:" + role); continue;
  }
  if (lg === "leg2-fixed") { cUnchanged++; continue; }

  if (role.startsWith("eurobox-col0")) { p.position = [x, y, z + DELTA_Z_FRONT / 2]; cCol0Interp++; touched.add("col0-box:" + role); continue; }
  if (role.startsWith("eurobox-col1")) { cUnchanged++; continue; }

  if (role === "uhelnik-noha1" || role === "uhelnik-noha2") {
    const oldYnew = role === "uhelnik-noha1" ? OLD_YNEW.leg1 : OLD_YNEW.leg2;
    if (near(y, oldYnew, 3) || near(y, oldYnew + 30, 3)) {
      p.position = [x, y + DELTA_Y_VYREZ, z];
      (role === "uhelnik-noha1" ? cLeg1++ : cLeg2++); touched.add(role + "(seam)");
    } else { cUnchanged++; touched.add(role + "(unaffected)"); }
    continue;
  }

  if (role.startsWith("spojnice-col0")) {
    const dLeg0 = Math.abs(z - LEG_Z.leg0), dLeg1 = Math.abs(z - LEG_Z.leg1);
    if (dLeg0 < dLeg1) { p.position = [x, y, z + DELTA_Z_FRONT]; cFront++; touched.add("front-spojnice:" + role); }
    else { cUnchanged++; touched.add("fixed-spojnice:" + role); }
    continue;
  }

  if (role.startsWith("nosnik-col0")) {
    const newZ = z + DELTA_Z_FRONT / 2;
    const newLenMm = p.scale[1] * 1000 - DELTA_Z_FRONT;
    p.position = [x, y, newZ]; p.scale = [p.scale[0], newLenMm / 1000, p.scale[2]];
    cCol0Interp++; touched.add("nosnik-col0-resize:" + role); continue;
  }

  if (lg === "col0") {
    const frac = (z - LEG_Z.leg1) / (LEG_Z.leg0 - LEG_Z.leg1);
    const newLeg0Z = LEG_Z.leg0 + DELTA_Z_FRONT;
    const newZ = LEG_Z.leg1 + frac * (newLeg0Z - LEG_Z.leg1);
    p.position = [x, y, newZ]; cCol0Interp++; touched.add("col0-logo-interp:" + role); continue;
  }

  if (near(z, LEG_Z.leg1, 0.05) || near(z, LEG_Z.leg2, 0.05)) {
    const isLeg1 = near(z, LEG_Z.leg1, 0.05);
    const oldYnew = isLeg1 ? OLD_YNEW.leg1 : OLD_YNEW.leg2;
    const newYnew = oldYnew + DELTA_Y_VYREZ;
    if (role === "sloupek-pred-podbehem") {
      const oldHeight = p.scale[1] * 1000, floorY = y - oldHeight / 2;
      const newHeight = newYnew - floorY;
      p.position = [x, floorY + newHeight / 2, z]; p.scale = [p.scale[0], newHeight / 1000, p.scale[2]];
      (isLeg1 ? cLeg1++ : cLeg2++); touched.add((isLeg1 ? "leg1" : "leg2") + ":" + role); continue;
    }
    if (role === "zadni-svislice-nad-zarezem") {
      const oldHeight = p.scale[1] * 1000, topY = y + oldHeight / 2;
      const newHeight = topY - newYnew;
      p.position = [x, newYnew + newHeight / 2, z]; p.scale = [p.scale[0], newHeight / 1000, p.scale[2]];
      (isLeg1 ? cLeg1++ : cLeg2++); touched.add((isLeg1 ? "leg1" : "leg2") + ":" + role); continue;
    }
    if (role === "pricka-uzavreni-vyrezu") {
      // T zde uz je polovina tloustky profilu (profil_mm/2=15) - pricka
      // sedi stredem 15mm nad svarem (puvodni skript pocital s T=30 plnou
      // tloustkou a delil "T/2"; se stejnym vyslednym cislem 15mm).
      p.position = [x, newYnew + T, z];
      (isLeg1 ? cLeg1++ : cLeg2++); touched.add((isLeg1 ? "leg1" : "leg2") + ":" + role); continue;
    }
    cUnchanged++; continue;
  }

  cUnchanged++;
}

console.log("PASS1 (krok 3 - zakladni delty):");
console.log("  front-leg Z-shift (+8mm):", cFront);
console.log("  col0 interpolace (Z, +8/2 nebo frakce):", cCol0Interp);
console.log("  leg1 seam (+10mm Y nebo rescale):", cLeg1);
console.log("  leg2 seam (+10mm Y nebo rescale):", cLeg2);
console.log("  beze zmeny:", cUnchanged);
console.log("  soucet:", cFront + cCol0Interp + cLeg1 + cLeg2 + cUnchanged, "= celkem", parts.length);

// === PASS 2: krok 4+5 procedury - "dorovnani luzek" ===
// Sloupce = po sobe jdouci dvojice noh (Z rostouci): col0=(leg0,leg1), col1=(leg1,leg2).
const COLUMNS = [
  { name: "col0", legA: "leg0", legB: "leg1", vyrezLegs: ["leg1"] },
  { name: "col1", legA: "leg1", legB: "leg2", vyrezLegs: ["leg1", "leg2"] },
];

for (const col of COLUMNS) {
  const rx = new RegExp(`^nosnik-${col.name}-p(\\d+)$`);
  const floors = new Map(); // pIndex -> [parts]
  for (const p of parts) {
    const m = rx.exec(p.role);
    if (m) { const i = Number(m[1]); if (!floors.has(i)) floors.set(i, []); floors.get(i).push(p); }
  }
  if (floors.size === 0 || col.vyrezLegs.length === 0) continue;
  const N = Math.max(...floors.keys()) + 1;
  if (floors.size !== N) throw new Error(`${col.name}: nosnik patra nejsou souvisla 0..N-1 (nalezeno ${[...floors.keys()]})`);

  const limitingYnew = Math.max(...col.vyrezLegs.map(lg => OLD_YNEW[lg] + DELTA_Y_VYREZ));
  const p0 = floors.get(0)[0];
  const bottomEdge = p0.position[1] - T;
  const missing = limitingYnew - bottomEdge;
  console.log(`\n${col.name}: N=${N} pater, limitujici Y_new=${limitingYnew.toFixed(3)}, spodni hrana nejnizsiho patra=${bottomEdge.toFixed(3)}, chybi=${missing.toFixed(3)}mm`);
  if (missing <= EPS) { console.log(`  -> zadne dorovnani (luzko NEVISI ve vzduchu).`); continue; }

  // Baseline Y kazdeho patra PRED dorovnanim - pouzije se k dohledani
  // razitek (logo-ochrana-*), ktera na dane patro fyzicky sedi (nalezeno
  // krokem 6c: logo-ochrana-vypln-4/0/6 maji Y IDENTICKE s nosnik-col0-
  // p0/p1/p2 - 0.00001mm rozdil, tedy montovane primo na tu listu, ne na
  // svislici). Musi se posunout spolu s patrem, jinak zustanou pozadu a
  // po zvednuti nosniku do nich narazi (viz self-kolize v prvnim behu).
  const floorBaselineY = new Map();
  for (const [i, ps] of floors) floorBaselineY.set(i, ps[0].position[1]);
  const LOGO_TOL = 1; // mm - "stejne Y" tolerance pro parovani razitka<->patro
  const logoMatches = new Map(); // part -> tier i
  if (col.name === "col0") {
    for (const p of parts) {
      if (logoGroup(p.role) !== "col0") continue;
      let bestI = -1, bestD = Infinity;
      for (const [i, y] of floorBaselineY) {
        const d = Math.abs(p.position[1] - y);
        if (d < bestD) { bestD = d; bestI = i; }
      }
      if (bestD <= LOGO_TOL) logoMatches.set(p, bestI);
    }
  }

  const shiftFor = (i) => N === 1 ? missing : missing * (N - 1 - i) / (N - 1);
  for (let i = 0; i < N; i++) {
    const sh = shiftFor(i);
    // VSECHNY dily tohoto patra (nosnik + spojnice + eurobox), ne jen nosnik
    const reRole = new RegExp(`^(nosnik|spojnice|eurobox)-${col.name}-p${i}$`);
    let n = 0;
    for (const p of parts) {
      if (reRole.test(p.role)) { p.position = [p.position[0], p.position[1] + sh, p.position[2]]; n++; }
    }
    for (const [p, ti] of logoMatches) {
      if (ti !== i) continue;
      p.position = [p.position[0], p.position[1] + sh, p.position[2]];
      n++; touched.add("col0-logo-tier-dorovnani:" + p.role);
    }
    console.log(`  patro p${i}: shift=+${sh.toFixed(4)}mm, dilu=${n}`);
    cDorovnani += n;
  }
}
console.log("\nCelkem dilu upravenych dorovnanim (krok 4/5):", cDorovnani);

// === KONTROLA proti jiz schvalene sestave id=340 (stejna karoserie/
// sloupce, jina napln polic) - kde matchuje presne (role,X,part_id), musi
// sedet delta na 0.01mm. Cisty sanity check navic, NENI soucast procedury,
// ale je zdarma a odhaluje regresi drive (viz hlavicka souboru). ===
if (fs.existsSync(SCRATCH + "/a340_full.json")) {
  const ref = JSON.parse(fs.readFileSync(SCRATCH + "/a340_full.json", "utf8")).data.parts;
  const key = p => p.role + "|" + p.position[0].toFixed(1) + "|" + p.part_id;
  const map = new Map();
  for (const p of ref) { const k = key(p); if (!map.has(k)) map.set(k, []); map.get(k).push(p); }
  const usedIdx = new Map();
  let checked = 0, mismatches = 0;
  for (let idx = 0; idx < partsOrig.length; idx++) {
    const orig = partsOrig[idx], now = parts[idx];
    if (R.jeKaroserie(orig.part_id)) continue;
    const k = key(orig);
    const cands = map.get(k) || [];
    if (!cands.length) continue; // 340 ma jina zahrada (napr eurobox obsah) - preskoc, neni referencni
    let used = usedIdx.get(k) || new Set();
    let bestI = -1, bestDist = Infinity;
    for (let i = 0; i < cands.length; i++) {
      if (used.has(i)) continue;
      const dz = Math.abs(cands[i].position[2] - orig.position[2]);
      if (dz < bestDist) { bestDist = dz; bestI = i; }
    }
    if (bestI < 0) continue;
    used.add(bestI); usedIdx.set(k, used);
    const c = cands[bestI];
    checked++;
    const dY = Math.abs(now.position[1] - c.position[1]);
    const dZ = Math.abs(now.position[2] - c.position[2]);
    if (dY > 0.02 || dZ > 0.02) {
      // VYJIMKA: logo-ochrana-{vypln,logo}-{0,4,6} (col0, tier-attached -
      // viz krok 6c nize). id=340 tyhle 3 razitka NEPOSOUVA s patrem, a
      // proto ma s prislusnym nosnikem REALNOU mesh-presnou self-kolizi
      // (overeno primo, viz AGENTS_LOG zapis k tomuto skriptu) - technicky_ok
      // u 340 je 0 (nikdy neproslo touhle kontrolou). Tenhle skript logo
      // posouva SPOLU s patrem prave proto, aby ta kolize u 279 nevznikla -
      // ocekavany, zduvodneny rozdil od 340, ne bug.
      if (/^logo-ochrana-(vypln|logo)-[046]$/.test(orig.role)) {
        console.log(`  (ocekavany rozdil vs id=340 - oprava jeho self-kolize) role=${orig.role} part=${orig.part_id} myY=${now.position[1].toFixed(3)} ref340Y=${c.position[1].toFixed(3)}`);
        continue;
      }
      mismatches++;
      console.log(`  MISMATCH vs id=340: role=${orig.role} part=${orig.part_id} myY=${now.position[1].toFixed(3)} ref340Y=${c.position[1].toFixed(3)} myZ=${now.position[2].toFixed(3)} ref340Z=${c.position[2].toFixed(3)}`);
    }
  }
  console.log(`\nKontrola proti id=340: ${checked} dilu srovnatelnych, ${mismatches} neocekavanych neshod (tol 0.02mm; 6 razitek u tier p0/p1/p2 se OCEKAVANE lisi, viz vyse).`);
  if (mismatches > 0) throw new Error(`${mismatches} dilu nesedi proti jiz schvalene referenci id=340 - NEZAPISOVAT, opravit vypocet.`);
} else {
  console.log("\n(Reference id=340 neni v scratchpad - kontrola preskocena.)");
}

fs.writeFileSync(SCRATCH + "/assembly279_transformed_parts.json", JSON.stringify(parts));
console.log("\nUlozeno:", SCRATCH + "/assembly279_transformed_parts.json");

// === KROK 6 procedury - OVERENI ===
console.log("\n=== KROK 6a: SAT hranovy raycast vsech dilu proti REALNE GLB karoserii ===");
const CAR_BODY_BASE = "car_bodies/Fiat_Doblo_FI14_2010-2022";
function wallMeshes() {
  const L = parseGlbMesh(R.KAT + CAR_BODY_BASE + "_L.glb");
  const Rd = parseGlbMesh(R.KAT + CAR_BODY_BASE + "_R_D.glb");
  const B = parseGlbMesh(R.KAT + CAR_BODY_BASE + "_B.glb");
  [L, Rd, B].forEach(m => { m.updateMatrixWorld(true); m.geometry.computeBoundsTree(); });
  return [L, Rd, B];
}
const walls = wallMeshes();

function meshWorldEdges(mesh, maxEdges) {
  const geo = mesh.geometry, pos = geo.attributes.position, idx = geo.index;
  const triCount = idx ? idx.count / 3 : pos.count / 3;
  const step = Math.max(1, Math.floor(triCount / (maxEdges / 3)));
  const edges = [];
  const vA = new THREE.Vector3(), vB = new THREE.Vector3(), vC = new THREE.Vector3();
  for (let t = 0; t < triCount; t += step) {
    let ia, ib, ic;
    if (idx) { ia = idx.getX(t * 3); ib = idx.getX(t * 3 + 1); ic = idx.getX(t * 3 + 2); }
    else { ia = t * 3; ib = t * 3 + 1; ic = t * 3 + 2; }
    vA.fromBufferAttribute(pos, ia).applyMatrix4(mesh.matrixWorld);
    vB.fromBufferAttribute(pos, ib).applyMatrix4(mesh.matrixWorld);
    vC.fromBufferAttribute(pos, ic).applyMatrix4(mesh.matrixWorld);
    edges.push([vA.clone(), vB.clone()], [vB.clone(), vC.clone()], [vC.clone(), vA.clone()]);
  }
  return edges;
}
const raycaster = new THREE.Raycaster();
raycaster.firstHitOnly = true;
function collidesWithWalls(mesh) {
  for (const [p0, p1] of meshWorldEdges(mesh, 400)) {
    const dir = p1.clone().sub(p0), dist = dir.length();
    if (dist < 1e-6) continue;
    dir.normalize(); raycaster.set(p0, dir); raycaster.far = dist;
    if (raycaster.intersectObjects(walls, false).length) return true;
  }
  return false;
}

const measurable = parts.filter(p => !R.jeKaroserie(p.part_id) && !String(p.role || "").startsWith("kontrolni-pomucka"));
let satCollisions = 0;
const satHits = [];
const glbCache = new Map();
for (const p of measurable) {
  const gp = R.glbPath(p.part_id);
  if (!gp) throw new Error(`glb_resolver nenasel GLB pro part_id=${p.part_id} (role=${p.role}) - nemerit tise, oprav mapu.`);
  let base = glbCache.get(gp);
  if (!base) { base = parseGlbMesh(gp); glbCache.set(gp, base); }
  const mesh = base.clone();
  mesh.geometry = base.geometry;
  mesh.position.set(...p.position);
  mesh.quaternion.set(...p.quaternion);
  mesh.scale.set(...p.scale);
  mesh.updateMatrixWorld(true);
  if (collidesWithWalls(mesh)) { satCollisions++; satHits.push({ role: p.role, part_id: p.part_id, position: p.position }); }
}
console.log(`Zmereno ${measurable.length} dilu (z ${parts.length}, karoserie/pomucky vyloucene) proti karoserii ${CAR_BODY_BASE}.`);
console.log(`SAT kolize s karoserii: ${satCollisions}`);
if (satCollisions) satHits.forEach(h => console.log("  KOLIDUJE:", h.role, h.part_id, h.position));

console.log("\n=== KROK 6b: presna mezera na kazdem posunutem/dorovnanem svu (musi byt 0.000mm) ===");
function box3World(p) {
  const gp = R.glbPath(p.part_id);
  let base = glbCache.get(gp);
  if (!base) { base = parseGlbMesh(gp); glbCache.set(gp, base); }
  const mesh = base.clone(); mesh.geometry = base.geometry;
  mesh.position.set(...p.position); mesh.quaternion.set(...p.quaternion); mesh.scale.set(...p.scale);
  mesh.updateMatrixWorld(true);
  return new THREE.Box3().setFromObject(mesh);
}
let seamFail = 0;
for (const legName of ["leg1", "leg2"]) {
  const z = LEG_Z[legName];
  const sloupek = parts.find(p => p.role === "sloupek-pred-podbehem" && near(p.position[2], z, 0.05));
  const svisl = parts.find(p => p.role === "zadni-svislice-nad-zarezem" && near(p.position[2], z, 0.05));
  const bSloupek = box3World(sloupek), bSvisl = box3World(svisl);
  const gap = bSvisl.min.y - bSloupek.max.y;
  console.log(`  ${legName} seam sloupek/svislice: mezera = ${gap.toFixed(4)}mm`);
  if (Math.abs(gap) > 0.02) { seamFail++; console.log(`    !! MIMO TOLERANCI (ocekavano 0.000mm)`); }
}
// col0 dorovnani seam: nosnik-col0-p0 spodni hrana vs leg1 nove Y_new (bod, ne dil-dil svar,
// ale porovnatelne s presnosti na 0.02mm - po dorovnani ma byt >= 0, typicky presne 0)
{
  const p0 = parts.find(p => p.role === "nosnik-col0-p0");
  const bottom = p0.position[1] - T;
  const limitingYnew = OLD_YNEW.leg1 + DELTA_Y_VYREZ;
  const gap = bottom - limitingYnew;
  console.log(`  col0 nejnizsi patro (p0) spodni hrana vs leg1 Y_new: mezera = ${gap.toFixed(4)}mm`);
  if (gap < -0.02) { seamFail++; console.log(`    !! LUZKO PORAD VISI VE VZDUCHU`); }
}
console.log(`Sviry mimo toleranci: ${seamFail}`);

console.log("\n=== KROK 6c: self-kolize (mesh-presny SAT, preskoc zname vnorovaci prekryvy) ===");
function isKnownNesting(a, b) {
  const roles = [a.role, b.role];
  const has = (re) => roles.some(r => re.test(r || ""));
  if (has(/^eurobox-/) && has(/^(nosnik|spojnice)-/)) return true;
  if (has(/^zaslepka-/) && has(/^(predni-svislice|cap|zadni-svislice|sloupek-pred-podbehem)/)) return true;
  if (has(/^logo-ochrana-vypln-/) && (has(/^(predni-svislice|zadni-svislice|sloupek-pred-podbehem|cap)/))) return true;
  return false;
}
const measurableSelf = measurable.filter(p => p.part_id !== "car_body_15");
const dils = measurableSelf.map(p => {
  const gp = R.glbPath(p.part_id);
  return { p, D: MK.dilVeSvete(gp, p, parseGlbMesh) };
});
let selfCollisions = 0, testedPairs = 0;
const selfHits = [];
for (let i = 0; i < dils.length; i++) {
  for (let j = i + 1; j < dils.length; j++) {
    const A = dils[i], B = dils[j];
    if (A.p.role === B.p.role && A.p.part_id === B.p.part_id) { /* stejny typ, muze byt symetricky par - porovnej stejne */ }
    const bov = MK.prekryvBoxu(A.D.box, B.D.box);
    if (Math.min(...bov) <= 0.05) continue; // broad phase
    testedPairs++;
    const k = MK.kolize(A.D, B.D, 0.05, false);
    if (!k.koliduje) continue;
    const vol = k.oblast[0] * k.oblast[1] * k.oblast[2];
    if (isKnownNesting(A.p, B.p)) continue; // znama vnorovaci geometrie
    if (vol <= 2000) continue; // pod prahem
    selfCollisions++;
    selfHits.push({ a: A.p.role, aId: A.p.part_id, b: B.p.role, bId: B.p.part_id, oblast: k.oblast, odsun: k.odsun });
  }
}
console.log(`Testovano ${testedPairs} dvojic (po broad-phase), self-kolizi nad 2000mm3 (mimo zname vnoreni): ${selfCollisions}`);
if (selfCollisions) selfHits.forEach(h => console.log("  SELF-KOLIZE:", h.a, h.aId, "<->", h.b, h.bId, "oblast", h.oblast, "odsun", h.odsun));

const report = {
  assembly_id: META.id,
  measured: measurable.length,
  sat_collisions: satCollisions,
  sat_hits: satHits,
  seam_fail: seamFail,
  self_tested_pairs: testedPairs,
  self_collisions: selfCollisions,
  self_hits: selfHits,
  verdict: (satCollisions === 0 && seamFail === 0 && selfCollisions === 0) ? "OK" : "BLOCKED",
};
fs.writeFileSync(SCRATCH + "/assembly279_verify_report.json", JSON.stringify(report, null, 1));
console.log("\n=== VERDIKT:", report.verdict, "===");
console.log("Report:", SCRATCH + "/assembly279_verify_report.json");
