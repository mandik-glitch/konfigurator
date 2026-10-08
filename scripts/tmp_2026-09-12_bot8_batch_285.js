// Prepocet kolizni bezpecnostni rezervy (2/20mm -> 10/30mm) na
// product_assemblies.id=285 ("Jumpy Crew Cab L2 K-118 C -
// boxy43-220x2-170x2-120x2"), podle shape_geometry_methods.id=11
// "prepocet-kolizni-rezervy-existujici-sestavy" (verified_by robert) a
// JIZ ZJISTENYCH dat o nohach rodiny K-118 (zadani teto ulohy - zadna
// vlastni re-analyza NOH/Z-pozic/old_y_new/wall_x se nedela, jen se
// OVERUJE ze sedi s realnymi daty v id=285).
//
// K-118 MA JINOU TOPOLOGII NEZ K-075 (na kterou uz existuji hotove
// skripty tmp_2026-09-12_bot8_batch_{332..337}.js) - jen 1 sloupec
// ("sloupec0", ne "colN" per-bay), a hlavne: na Z1 (leg1) NENI cely
// uzel cisty "vyrez" jako u K-075 - MA SOUCASNE plnou nohu (role
// predni-svislice + jeji spojnice-dolni/horni + cap, X=-439..-665)
// I vyrezovou nohu (trio zadni-svislice-nad-zarezem/sloupek-pred-
// podbehem/pricka-uzavreni-vyrezu, X=-735..-611) NA STEJNEM Z. Kod
// K-075 skriptu proto NELZE proste zkopirovat - kazda role/dil na Z1
// se musi zaradit zvlast (plna->deltaZ, vyrez->deltaY).
//
// KLASIFIKACE zaslepka/uhelnik-noha1 (ktere role samy o sobe
// nerikaji, ktere noze na Z1 patri) NENI hardcodovana - je OVERENA
// v tomto skriptu geometricky (Box3 realne GLB geometrie, presnost
// dist===0.000mm = fyzicky dotyk) proti baseline (PRED transformaci)
// pozicim vsech "domovskych" dilu obou skupin. Viz sekce 2.
//
// ROZHODNUTA MISTA, kde procedura/zadani nedava jednoznacny navod
// (zapsano at je to auditovatelne, ne skryte v hlave):
//  a) nosnik-sloupec0 PREDNI kolejnice (X=-439, spojuje predni-svislici
//     na leg0 I leg1 - OBE plne, OBE se posouvaji o +deltaZ) -> CELA
//     kolejnice tuhy posun +deltaZ, BEZE ZMENY DELKY (na rozdil od
//     K-075 vzoru, kde nosnik-col0 vzdy REsizuje - tam ale byl VZDY
//     jen JEDEN pohyblivy konec, tady jsou POHYBLIVE OBA).
//  b) nosnik-sloupec0 ZADNI kolejnice (X=-735, spojuje zadni-svislici-
//     dolni@leg0 [plna, hybe se] a zadni-svislici-nad-zarezem@leg1
//     [vyrez, Z FIXNI]) -> STEJNY vzorec jako K-075 nosnik-col0:
//     stred += deltaZ/2, delka -= deltaZ.
//  c) spojnice-sloupec0-patroN (9ks, prickove vzpery MEZI kolejnicemi,
//     nedotykaji se noh primo, jen bocne kolejnic v X - geometricky
//     overeno ze jejich Z-dotyk s obema kolejnicemi NEZAVISI na jejich
//     presne Z pozici, dokud spada do rozsahu kolejnice) -> stred +=
//     deltaZ/2 (stejna konvence jako eurobox, dolni bod (b) procedury).
//  d) eurobox-sloupec0-patroN (6ks) -> stred += deltaZ/2, presne podle
//     procedury ("eurobox-col0-* stred se posune o deltaZ/2 (inter-
//     polace, box je uprostred sloupce)").
//  e) zaslepka na Z1, X=-735 (zaslepka-noha1-zadni): geometricky se
//     dotyka JAK spojnice-horni (plna, top FIXNI vuci vlastnimu
//     posunu +deltaZ) TAK zadni-svislice-nad-zarezem (vyrez, jeji TOP
//     je FIXNI reference resize vzorce id=6 - nehybe se vubec, jen
//     dolni konec/seam roste). Zaslepka sama sedi presne NA fixnim
//     topu zadni-svislice-nad-zarezem (X=-735 presna shoda, ne X=-587
//     spojnice) -> klasifikovana jako VYREZ-strana, ale protoze kryje
//     FIXNI (nehybajici se) konec profilu, NEDOSTAVA deltaY (byla by
//     to chyba - odtrhla by se od topu, ktery se nehybe). Z beze zmeny
//     (netahne se s plnou nohou, protoze jeji vlastni "domovsky" profil
//     je vyrezovy a nemeni Z). VYSLEDEK: tenhle jeden dil zustava
//     UPLNE BEZE ZMENY (Y i Z). Dusledek (mala nova mezera/prekryv
//     vuci spojnice-horni, ktera o deltaZ=8mm odjede) je INHERENTNI
//     dusledek zadani (notes vyslovne rikaji "jeji spojnice/cap" =
//     plna, "jeho zaslepky" = vyrez - a tenhle jeden dil se fyzicky
//     dotyka OBOU), ne chyba tohoto skriptu - zmereno a nahlaseno v
//     kroku 6c (self-kolize), ne umlceno.

const fs = require("fs");
const THREE = require("three");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const MeshBVHLib = require("/opt/konfigurator/webapp/js/three-mesh-bvh.js");
THREE.BufferGeometry.prototype.computeBoundsTree = MeshBVHLib.computeBoundsTree;
THREE.Mesh.prototype.raycast = MeshBVHLib.acceleratedRaycast;
const R = require("/opt/konfigurator/scripts/2026-09-11_glb_resolver.js");
const { execSync } = require("child_process");

const ASM_ID = 285;
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

const partsOrig = SRC_PARTS.map(p => JSON.parse(JSON.stringify(p))); // baseline clone (nemenit)
const parts = SRC_PARTS.map(p => JSON.parse(JSON.stringify(p)));     // pracovni clone (transformovany)

// ============================ 1) KONSTANTY (ze zadani, NEODVOZUJI) =======
const LEG_Z0 = -1170.5000534057617;   // "predni-svislice" plna noha
const LEG_Z1 = -308.5000534057617;    // predni-svislice PLNA + vyrez trio, SOUCASNE
const DELTA_Z = 8;    // 10-2mm (prepazka)
const DELTA_Y = 10;   // 30-20mm (podbeh)
const T = 30;         // profil tloustka (pricka-uzavreni-vyrezu stred)
const EPS = 0.06;
const near = (a, b, eps) => Math.abs(a - b) < (eps == null ? EPS : eps);

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
function box(p) { return new THREE.Box3().setFromObject(partMesh(p)); }
function boxDist(b1, b2) {
  const dx = Math.max(b1.min.x - b2.max.x, b2.min.x - b1.max.x, 0);
  const dy = Math.max(b1.min.y - b2.max.y, b2.min.y - b1.max.y, 0);
  const dz = Math.max(b1.min.z - b2.max.z, b2.min.z - b1.max.z, 0);
  return Math.sqrt(dx * dx + dy * dy + dz * dz);
}

// Over pritomnost noh podle vstupnich dat (Z, tolerance ~1mm)
const zSet = partsOrig.filter(p => p.position).map(p => p.position[2]);
const has = (z) => zSet.some(zz => near(zz, z, 1));
const legsPresent = { leg0_plain: has(LEG_Z0), leg1_plain: has(LEG_Z1), leg1_vyrez: has(LEG_Z1) };
console.log("Nohy pritomne (Z-shoda se vstupnimi daty):", JSON.stringify(legsPresent));
if (!legsPresent.leg0_plain || !legsPresent.leg1_plain) {
  throw new Error("Ocekavane Z pozice noh (Z0/Z1) nenalezeny v id=285 - NEZAPISOVAT, zadani nesedi s realnymi daty.");
}

// ============================ 2) OVERENI old_y_new + klasifikace =========
// Zmerit old_y_new PRIMO z dat (sloupek top vs svislice bottom, presna
// shoda) - kontrola proti vstupnimu udaji 291.0001220703125.
const sloupek1 = partsOrig.find(p => p.role === "sloupek-pred-podbehem" && near(p.position[2], LEG_Z1));
const svisl1 = partsOrig.find(p => p.role === "zadni-svislice-nad-zarezem" && near(p.position[2], LEG_Z1));
if (!sloupek1 || !svisl1) throw new Error("sloupek-pred-podbehem / zadni-svislice-nad-zarezem na Z1 nenalezeny.");
const sloupekTop = sloupek1.position[1] + sloupek1.scale[1] * 500;
const svislBottom = svisl1.position[1] - svisl1.scale[1] * 500;
if (Math.abs(sloupekTop - svislBottom) > 0.001) {
  throw new Error(`sloupek top (${sloupekTop}) != svislice bottom (${svislBottom}) - svar neni presny, PROCEDURA NEPLATI beze zmeny.`);
}
const OLD_YNEW = sloupekTop;
console.log(`OLD_YNEW zmereno z dat: ${OLD_YNEW} (vstup ocekaval 291.0001220703125, shoda=${Math.abs(OLD_YNEW - 291.0001220703125) < 0.001})`);
const NEW_YNEW = OLD_YNEW + DELTA_Y;

// --- Geometricka klasifikace PLNA/VYREZ pro zaslepka + uhelnik-noha1 na Z1 ---
// (viz komentar v hlavicce souboru - dist===0 = fyzicky dotyk v baseline)
const plnaRoles1 = ["predni-svislice", "spojnice-dolni", "spojnice-horni", "cap"];
const vyrezRoles1 = ["sloupek-pred-podbehem", "zadni-svislice-nad-zarezem", "pricka-uzavreni-vyrezu"];
const plnaHost1 = partsOrig.filter(p => p.position && near(p.position[2], LEG_Z1) && plnaRoles1.includes(p.role));
const vyrezHost1 = partsOrig.filter(p => p.position && near(p.position[2], LEG_Z1) && vyrezRoles1.includes(p.role));

function classifyByTouch(p, tol) {
  const pb = box(p);
  let plnaBest = Infinity, vyrezBest = Infinity, plnaWhich = null, vyrezWhich = null;
  for (const h of plnaHost1) { const d = boxDist(pb, box(h)); if (d < plnaBest) { plnaBest = d; plnaWhich = h.role; } }
  for (const h of vyrezHost1) { const d = boxDist(pb, box(h)); if (d < vyrezBest) { vyrezBest = d; vyrezWhich = h.role; } }
  return { plnaTouch: plnaBest < tol, vyrezTouch: vyrezBest < tol, plnaWhich, vyrezWhich, plnaBest, vyrezBest };
}
// Rozhodovaci pravidlo pro dily, ktere se DOTYKAJI OBOU skupin zaroven
// (fyzicky spojuji plnou a vyrezovou nohu na stejnem Z1):
//  - je-li dil U SVU (Y blizko OLD_YNEW nebo OLD_YNEW+30, presne stejna
//    tolerance jako K-075 vzor) -> procedura rika VYSLOVNE, ze uhelniky
//    "na svu teto [vyrezove] nohy" patri k vyrezove noze -> VYREZ.
//  - jinak (dotyka se obou, ale NENI u svu - typicky floor-level nebo
//    top-level roh, kde je jedna strana FIXNI referenci resize vzorce a
//    druha PLNA/pohybliva) -> nelze jednoznacne priradit bez poskozeni
//    fyzickeho dotyku na jedne strane -> BOUNDARY, zustava BEZE ZMENY
//    (stejne zduvodneni jako zaslepka X=-735, viz hlavicka bod e).
function classifyLeg1(c, y) {
  if (c.plnaTouch && !c.vyrezTouch) return "PLNA";
  if (c.vyrezTouch && !c.plnaTouch) return "VYREZ";
  if (c.plnaTouch && c.vyrezTouch) return (near(y, OLD_YNEW, 3) || near(y, OLD_YNEW + 30, 3)) ? "VYREZ" : "BOUNDARY";
  return "NEITHER";
}

// zaslepka na Z1 (3ks): X=-439 (predni), X=-665 (cap), X=-735 (zadni)
const zaslepky1 = partsOrig.filter(p => p.role === "zaslepka" && near(p.position[2], LEG_Z1));
const zaslepkaClass = new Map();
console.log("\n=== Klasifikace zaslepka @ Z1 (geometricky dotyk, tol=0.05mm) ===");
for (const z of zaslepky1) {
  const c = classifyByTouch(z, 0.05);
  const cls = classifyLeg1(c, z.position[1]);
  zaslepkaClass.set(z, { cls, ...c });
  console.log(`  X=${z.position[0]} Y=${z.position[1].toFixed(1)} -> plna(${c.plnaWhich}:${c.plnaBest.toFixed(3)}) vyrez(${c.vyrezWhich}:${c.vyrezBest.toFixed(3)}) => ${cls}`);
}

// uhelnik-noha1 (12ks)
const uhelniky1 = partsOrig.filter(p => p.role === "uhelnik-noha1");
const uhelnikClass = new Map();
console.log("\n=== Klasifikace uhelnik-noha1 @ Z1 (geometricky dotyk, tol=0.05mm) ===");
for (const u of uhelniky1) {
  const c = classifyByTouch(u, 0.05);
  const cls = classifyLeg1(c, u.position[1]);
  uhelnikClass.set(u, { cls, ...c });
  console.log(`  X=${u.position[0].toFixed(1)} Y=${u.position[1].toFixed(1)} Z=${u.position[2].toFixed(1)} -> plna(${c.plnaWhich}:${c.plnaBest.toFixed(3)}) vyrez(${c.vyrezWhich}:${c.vyrezBest.toFixed(3)}) => ${cls}`);
}
const nPlna = [...uhelnikClass.values()].filter(v => v.cls === "PLNA").length;
const nVyrez = [...uhelnikClass.values()].filter(v => v.cls === "VYREZ").length;
const nBoundary = [...uhelnikClass.values()].filter(v => v.cls === "BOUNDARY").length;
const nOther = uhelniky1.length - nPlna - nVyrez - nBoundary;
console.log(`uhelnik-noha1 souhrn: PLNA=${nPlna} VYREZ=${nVyrez} BOUNDARY=${nBoundary} jine=${nOther} (celkem ${uhelniky1.length})`);
if (nOther > 0) throw new Error(`uhelnik-noha1: ${nOther} dilu se nepodarilo jednoznacne zaradit (NEITHER) - NEZAPISOVAT.`);

// zaslepka X=-735 @ Z1 je ocekavany BOUNDARY-pripad (viz hlavicka) - over to explicitne
const zas735 = zaslepky1.find(z => near(z.position[0], -735, 1));
if (!zas735 || zaslepkaClass.get(zas735).cls !== "BOUNDARY") {
  throw new Error("Ocekavany BOUNDARY-pripad (zaslepka X=-735 @ Z1, kryje fixni top zadni-svislice-nad-zarezem I dotyka se spojnice-horni) nenalezen presne jak predpokladano - zkontroluj rucne pred zapisem.");
}
console.log("\nOK: zaslepka X=-735 @ Z1 potvrzena jako ocekavany hranicni pripad (BOUNDARY) -> zustava BEZE ZMENY (viz hlavicka, bod e).");

// ============================ 3) TRANSFORMACE (kroky 3 procedury) ========
let cLeg0 = 0, cLeg1Plna = 0, cLeg1Vyrez = 0, cRailFront = 0, cRailBack = 0,
    cSpojSloupec = 0, cEurobox = 0, cBoundaryUnchanged = 0, cUnchanged = 0;
const touched = [];
function logTouch(p, kind, before) {
  touched.push({ role: p.role, part_id: p.part_id, kind, before: { position: before.position, scale: before.scale }, after: { position: p.position.slice(), scale: p.scale.slice() } });
}

// mapovani baseline-object -> pracovni-object (podle indexu v poli, poradi zachovano)
const idxOfOrig = new Map(partsOrig.map((p, i) => [p, i]));
const uhelnikClassByIdx = new Map([...uhelnikClass.entries()].map(([p, v]) => [idxOfOrig.get(p), v]));
const zaslepkaClassByIdx = new Map([...zaslepkaClass.entries()].map(([p, v]) => [idxOfOrig.get(p), v]));

for (let i = 0; i < parts.length; i++) {
  const p = parts[i];
  if (!p.position) { cUnchanged++; continue; }
  const [x, y, z] = p.position;
  const role = p.role || "";
  const before = { position: p.position.slice(), scale: p.scale.slice() };

  // --- LEG0 (Z0): VSE co je presne na Z0, plus uhelnik-noha0 (offset Z) ---
  if (near(z, LEG_Z0) || role === "uhelnik-noha0") {
    p.position = [x, y, z + DELTA_Z];
    cLeg0++; logTouch(p, "leg0-plna-Z-shift", before);
    continue;
  }

  // --- LEG1 (Z1): rozdelit na PLNA / VYREZ / hranicni pripad ---
  // uhelnik-noha1 ma Z posunute az o 14mm (uhelnik je pripevneny na CELE
  // profilu, ne v jeho ose) - stejne jako uhelnik-noha0 u leg0 - takze
  // se musi chytit podle ROLE, ne podle Z-tolerance EPS.
  if (near(z, LEG_Z1) || role === "uhelnik-noha1") {
    if (plnaRoles1.includes(role)) {
      p.position = [x, y, z + DELTA_Z];
      cLeg1Plna++; logTouch(p, "leg1-plna-Z-shift", before);
      continue;
    }
    if (role === "sloupek-pred-podbehem") {
      const oldHeight = p.scale[1] * 1000, floorY = y - oldHeight / 2;
      const newHeight = NEW_YNEW - floorY;
      p.position = [x, floorY + newHeight / 2, z];
      p.scale = [p.scale[0], newHeight / 1000, p.scale[2]];
      cLeg1Vyrez++; logTouch(p, "leg1-vyrez-sloupek-resize", before);
      continue;
    }
    if (role === "zadni-svislice-nad-zarezem") {
      const oldHeight = p.scale[1] * 1000, topY = y + oldHeight / 2;
      const newHeight = topY - NEW_YNEW;
      p.position = [x, NEW_YNEW + newHeight / 2, z];
      p.scale = [p.scale[0], newHeight / 1000, p.scale[2]];
      cLeg1Vyrez++; logTouch(p, "leg1-vyrez-svislice-resize", before);
      continue;
    }
    if (role === "pricka-uzavreni-vyrezu") {
      p.position = [x, NEW_YNEW + T / 2, z];
      cLeg1Vyrez++; logTouch(p, "leg1-vyrez-pricka-reposition", before);
      continue;
    }
    if (role === "zaslepka") {
      const cls = zaslepkaClassByIdx.get(i);
      if (cls.cls === "BOUNDARY") { cBoundaryUnchanged++; continue; } // zaslepka X=-735, viz hlavicka
      if (cls.cls === "PLNA") { p.position = [x, y, z + DELTA_Z]; cLeg1Plna++; logTouch(p, "leg1-plna-zaslepka-Z-shift", before); continue; }
      if (cls.cls === "VYREZ") { p.position = [x, y + DELTA_Y, z]; cLeg1Vyrez++; logTouch(p, "leg1-vyrez-zaslepka-Y-shift", before); continue; }
      throw new Error("zaslepka @ Z1 s neocekavanou klasifikaci");
    }
    if (role === "uhelnik-noha1") {
      const cls = uhelnikClassByIdx.get(i);
      if (cls.cls === "BOUNDARY") { cBoundaryUnchanged++; continue; } // viz hlavicka bod e - floor/top-level roh sdileny obema skupinami
      if (cls.cls === "PLNA") { p.position = [x, y, z + DELTA_Z]; cLeg1Plna++; logTouch(p, "leg1-plna-uhelnik-Z-shift", before); continue; }
      if (cls.cls === "VYREZ") { p.position = [x, y + DELTA_Y, z]; cLeg1Vyrez++; logTouch(p, "leg1-vyrez-uhelnik-Y-shift", before); continue; }
      throw new Error("uhelnik-noha1 s neocekavanou klasifikaci");
    }
    // nemelo by nastat - vsechny role na Z1 jsou pokryte vyse
    throw new Error(`Neocekavana role na Z1: ${role}`);
  }

  // --- SLOUPEC0: nosnik (kolejnice), spojnice (prickove vzpery), eurobox ---
  if (role.startsWith("nosnik-sloupec0")) {
    if (near(x, -439, 1)) {
      // PREDNI kolejnice: oba konce (predni-svislice@leg0 I @leg1) jsou PLNA
      // a hybou se stejne o +DELTA_Z -> tuhy posun, delka beze zmeny.
      p.position = [x, y, z + DELTA_Z];
      cRailFront++; logTouch(p, "nosnik-front-rigid-Z-shift", before);
    } else if (near(x, -735, 1)) {
      // ZADNI kolejnice: konec u leg0 (plna) se hybe, konec u leg1
      // (vyrez, zadni-svislice-nad-zarezem) je Z-fixni -> resize.
      const newLenMm = p.scale[1] * 1000 - DELTA_Z;
      p.position = [x, y, z + DELTA_Z / 2];
      p.scale = [p.scale[0], newLenMm / 1000, p.scale[2]];
      cRailBack++; logTouch(p, "nosnik-back-resize", before);
    } else {
      throw new Error(`nosnik-sloupec0 s neocekavanym X=${x}`);
    }
    continue;
  }
  if (role.startsWith("spojnice-sloupec0")) {
    // prickove vzpery MEZI kolejnicemi - dotyk s obema kolejnicemi je
    // nezavisly na presnem Z (overeno geometricky, viz hlavicka bod c) ->
    // stred += deltaZ/2 (stejna konvence jako eurobox nize).
    p.position = [x, y, z + DELTA_Z / 2];
    cSpojSloupec++; logTouch(p, "spojnice-sloupec0-center-shift", before);
    continue;
  }
  if (role.startsWith("eurobox-sloupec0")) {
    p.position = [x, y, z + DELTA_Z / 2];
    cEurobox++; logTouch(p, "eurobox-center-shift", before);
    continue;
  }

  cUnchanged++;
}

console.log("\n=== KROK 3 (delty) souhrn ===");
console.log("leg0 (plna, Z-shift):", cLeg0);
console.log("leg1 plna (Z-shift):", cLeg1Plna);
console.log("leg1 vyrez (Y-resize/shift):", cLeg1Vyrez);
console.log("nosnik predni kolejnice (rigid Z-shift):", cRailFront);
console.log("nosnik zadni kolejnice (resize):", cRailBack);
console.log("spojnice-sloupec0 (center-shift):", cSpojSloupec);
console.log("eurobox (center-shift):", cEurobox);
console.log("hranicni pripad beze zmeny (zaslepka X=-735@Z1):", cBoundaryUnchanged);
console.log("beze zmeny (car_body_* atd.):", cUnchanged);
const totalAccounted = cLeg0 + cLeg1Plna + cLeg1Vyrez + cRailFront + cRailBack + cSpojSloupec + cEurobox + cBoundaryUnchanged + cUnchanged;
console.log("celkem:", parts.length, "= soucet", totalAccounted);
if (totalAccounted !== parts.length) throw new Error("Soucet klasifikovanych dilu nesedi s celkovym poctem - NEZAPISOVAT.");

// ============================ 4) DOROVNANI (kroky 4-5 procedury) =========
console.log("\n=== KROK 4-5 (dorovnani) ===");
const HALF_PROFILE = 15;
const floorRe = /^nosnik-sloupec0-p(?:atro)?(\d+)$/;
const floorIdxSet = new Set();
for (const p of parts) { const m = floorRe.exec(p.role || ""); if (m) floorIdxSet.add(Number(m[1])); }
const floors = [...floorIdxSet].map(idx => {
  const members = parts.filter(p => p.role === `nosnik-sloupec0-patro${idx}`);
  const y = Math.min(...members.map(p => p.position[1]));
  return { idx, y };
}).sort((a, b) => a.y - b.y);
console.log("Patra sloupce0 (idx, Y):", JSON.stringify(floors));
const lowest = floors[0];
const bottomEdge = lowest.y - HALF_PROFILE;
// Procedura (krok 4) rika porovnat spodni hranu luzka se "zmenenym Y_new
// prislusne vyrezove nohy" - ale tenhle konkretni sloupec ma NAVIC
// "pricka-uzavreni-vyrezu" (diagonalni vyplnovy dil uzaviraji zarez), ktery
// fyzicky saha VYS nez holy seam Y_new (o T/2 nad Y_new stred, tedy az T
// nad Y_new na horni hrane) A KRYJE CELOU SIRKU SLOUPCE (X=-720..-454,
// presne tam, kde sedi i nosnik/spojnice-sloupec0). Holy Y_new by tedy
// tenhle skutecny dil ignoroval a "LUZKO NEVISI" by bylo falesne pozitivni
// (viz KROK 6c - primo zmereny prekryv pricka<->spojnice-sloupec0-patro0,
// 8778mm3, kdyz se limit bral jen jako Y_new). Limit proto rozsiren na
// SKUTECNY horni okraj pricky (zmereny Box3 PO transformaci, ne odhad) -
// to NENI numericky trik, je to oprava neuplneho kriteria kroku 4 podle
// realne geometrie, kterou uz mame k dispozici (Box3 stejnym zpusobem
// jako krok 6b/6c).
const prickaAfter = parts.find(p => p.role === "pricka-uzavreni-vyrezu" && near(p.position[2], LEG_Z1));
const prickaTopMeasured = box(prickaAfter).max.y;
const limitY = Math.max(NEW_YNEW, prickaTopMeasured);
console.log(`Nejnizsi patro p${lowest.idx}: Y=${lowest.y}, spodni hrana=${bottomEdge.toFixed(4)}mm. Y_new(leg1)=${NEW_YNEW.toFixed(4)}mm, pricka-uzavreni-vyrezu horni hrana (zmereno)=${prickaTopMeasured.toFixed(4)}mm -> limit=${limitY.toFixed(4)}mm.`);
let allFloorShifts = [];
if (bottomEdge >= limitY - 1e-6) {
  console.log(`Spodni hrana (${bottomEdge.toFixed(4)}) >= limit (${limitY.toFixed(4)}) - LUZKO NEVISÍ, dorovnani NENI potreba.`);
} else {
  const missing = limitY - bottomEdge;
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
      const before = { position: p.position.slice(), scale: p.scale.slice() };
      p.position = [p.position[0], p.position[1] + shift, p.position[2]];
      logTouch(p, `sloupec0-p${floorIdx}-dorovnani`, before);
    }
  }
}

fs.writeFileSync(`${OUT_DIR}/tmp_2026-09-12_bot8_batch_285_parts.json`, JSON.stringify(parts));
fs.writeFileSync(`${OUT_DIR}/tmp_2026-09-12_bot8_batch_285_touched.json`, JSON.stringify(touched, null, 1));
console.log(`\nUlozeno: tmp_2026-09-12_bot8_batch_285_parts.json (${parts.length} dilu), touched.json (${touched.length} zmenenych zaznamu).`);

// ============================ 5) KROK 6: OVERENI ============================
console.log("\n\n=== KROK 6a: SAT test proti realne karoserii ===");
const KAT = "/opt/konfigurator/webapp/katalog/";
function loadWall(suf) {
  const m = parseGlbMesh(KAT + "car_bodies/Citroën_Jumpy_CI18_2016-" + suf + ".glb");
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

const testable = parts.filter(p => !String(p.part_id || "").startsWith("car_body_") && !String(p.role || "").startsWith("kontrolni-pomucka"));
let satCollisions = 0;
const satList = [];
const meshCache = [];
for (const p of testable) {
  if (R.jeKaroserie(p.part_id)) continue;
  const glbPath = R.glbPath(p.part_id);
  if (!glbPath) throw new Error("CHYBI GLB mapovani pro part_id=" + p.part_id + " role=" + p.role + " - NEZAPISOVAT, mereni by bylo nedoveryhodne.");
  const mesh = partMesh(p);
  meshCache.push({ p, mesh });
  if (collidesWithWallsReal(mesh)) { satCollisions++; satList.push({ role: p.role, part_id: p.part_id, position: p.position }); }
}
console.log(`SAT: ${satCollisions}/${meshCache.length} koliduje s realnou karoserii (GLB mapa ${R.velikostMapy()} zaznamu).`);
if (satCollisions) console.log("KOLIDUJICI:", JSON.stringify(satList, null, 1));

console.log("\n=== KROK 6b: presna mezera na kazdem posunutem/dorovnanem svu ===");
const seamChecks = [];
{
  const sloupekN = parts.find(p => p.role === "sloupek-pred-podbehem" && near(p.position[2], LEG_Z1));
  const svislN = parts.find(p => p.role === "zadni-svislice-nad-zarezem" && near(p.position[2], LEG_Z1));
  const sBox = box(sloupekN), vBox = box(svislN);
  const gap = vBox.min.y - sBox.max.y;
  console.log(`leg1 seam: sloupek top Box3.max.y=${sBox.max.y.toFixed(4)}  svislice bottom Box3.min.y=${vBox.min.y.toFixed(4)}  gap=${gap.toFixed(4)}mm`);
  seamChecks.push({ seam: "leg1-sloupek-svislice", gap });
}
{
  const nosnikP = parts.filter(p => p.role === `nosnik-sloupec0-patro${lowest.idx}`);
  let minY = Infinity;
  for (const p of nosnikP) { const b = box(p); minY = Math.min(minY, b.min.y); }
  const gap2 = minY - NEW_YNEW;
  console.log(`sloupec0 nejnizsi patro p${lowest.idx}: Box3.min.y=${minY.toFixed(4)}  Y_new(leg1)=${NEW_YNEW.toFixed(4)}  gap=${gap2.toFixed(4)}mm ${allFloorShifts.length ? "(po dorovnani)" : "(dorovnani nebylo potreba)"}`);
  seamChecks.push({ seam: `sloupec0-p${lowest.idx}-floor-vs-leg1`, gap: gap2 });
}

console.log("\n=== KROK 6c: self-kolize (Box3, vsechny dvojice krome znamych vnorovani) ===");
const KNOWN_NESTING = [
  (a, b) => (a.startsWith("eurobox") && (b.startsWith("nosnik") || b.startsWith("spojnice"))) || (b.startsWith("eurobox") && (a.startsWith("nosnik") || a.startsWith("spojnice"))),
  (a, b) => (a === "zaslepka" && ["predni-svislice", "cap", "zadni-svislice-nad-zarezem", "zadni-svislice-dolni", "sloupek-pred-podbehem"].includes(b)) || (b === "zaslepka" && ["predni-svislice", "cap", "zadni-svislice-nad-zarezem", "zadni-svislice-dolni", "sloupek-pred-podbehem"].includes(a)),
];
function isKnownNesting(a, b) { return KNOWN_NESTING.some(f => f(a, b)); }

function computeSelfCollisions(partsArr, label) {
  const testableL = partsArr.filter(p => !String(p.part_id || "").startsWith("car_body_") && !String(p.role || "").startsWith("kontrolni-pomucka") && !R.jeKaroserie(p.part_id));
  const box3s = [];
  for (const p of testableL) {
    const glbPath = R.glbPath(p.part_id);
    if (!glbPath) throw new Error("CHYBI GLB mapovani (self-kolize, " + label + ") pro part_id=" + p.part_id + " role=" + p.role);
    box3s.push({ p, box: box(p) });
  }
  const susp = [];
  for (let i = 0; i < box3s.length; i++) {
    for (let j = i + 1; j < box3s.length; j++) {
      const a = box3s[i], b = box3s[j];
      if (a.p.role === b.p.role && a.p.position[0] === b.p.position[0] && a.p.position[2] === b.p.position[2]) continue; // stejny dil, jina instance jinde
      const ra = a.p.role || "", rb = b.p.role || "";
      if (isKnownNesting(ra, rb)) continue;
      if (!a.box.intersectsBox(b.box)) continue;
      const ix = Math.min(a.box.max.x, b.box.max.x) - Math.max(a.box.min.x, b.box.min.x);
      const iy = Math.min(a.box.max.y, b.box.max.y) - Math.max(a.box.min.y, b.box.min.y);
      const iz = Math.min(a.box.max.z, b.box.max.z) - Math.max(a.box.min.z, b.box.min.z);
      const vol = Math.max(0, ix) * Math.max(0, iy) * Math.max(0, iz);
      if (vol > 2000) susp.push({ a: ra, aId: a.p.part_id, aPos: a.p.position, b: rb, bId: b.p.part_id, bPos: b.p.position, vol: +vol.toFixed(0) });
    }
  }
  return { count: susp.length, list: susp, total: box3s.length };
}

console.log("\n--- BASELINE (puvodni, NEtransformovana data 285) ---");
const baselineSelf = computeSelfCollisions(partsOrig, "baseline");
console.log(`baseline self-kolize: ${baselineSelf.count} z ${baselineSelf.total * (baselineSelf.total - 1) / 2} paru`);
for (const x of baselineSelf.list) console.log(`   BASELINE  ${x.a}(${x.aId}) <-> ${x.b}(${x.bId})  vol=${x.vol}mm3`);

console.log("\n--- PO TRANSFORMACI ---");
const afterSelf = computeSelfCollisions(parts, "after");
console.log(`po transformaci self-kolize: ${afterSelf.count} z ${afterSelf.total * (afterSelf.total - 1) / 2} paru`);
for (const x of afterSelf.list) console.log(`   AFTER     ${x.a}(${x.aId}) <-> ${x.b}(${x.bId})  vol=${x.vol}mm3`);

function pairKey(x) { return [x.a, x.b].sort().join("|"); }
const baseMap = new Map();
for (const x of baselineSelf.list) baseMap.set(pairKey(x) + "#" + x.aId + "#" + x.bId, x.vol);
const newOrGrown = [];
for (const x of afterSelf.list) {
  const key = pairKey(x) + "#" + x.aId + "#" + x.bId;
  const baseVol = baseMap.has(key) ? baseMap.get(key) : null;
  if (baseVol == null) newOrGrown.push({ ...x, baseVol: null, status: "NOVY (nebyl v baseline)" });
  else if (x.vol > baseVol + 500) newOrGrown.push({ ...x, baseVol, status: "ZVETSENY oproti baseline" });
}
console.log(`\nPáry NOVE nebo VYRAZNE ZVETSENE transformaci: ${newOrGrown.length}`);
for (const x of newOrGrown) console.log(`   ${x.status}: ${x.a}(${x.aId}) <-> ${x.b}(${x.bId})  baseline=${x.baseVol}  po=${x.vol}mm3`);

const report = {
  asm: ASM_ID, legsPresent, OLD_YNEW, NEW_YNEW,
  counts: { cLeg0, cLeg1Plna, cLeg1Vyrez, cRailFront, cRailBack, cSpojSloupec, cEurobox, cBoundaryUnchanged, cUnchanged, total: parts.length },
  dorovnaniNeeded: allFloorShifts.length > 0, floorShifts: allFloorShifts,
  satMeasured: meshCache.length, satCollisions, satList,
  seamChecks,
  baselineSelfCollisions: baselineSelf.count, baselineSelfList: baselineSelf.list,
  afterSelfCollisions: afterSelf.count, afterSelfList: afterSelf.list,
  newOrGrownSelfCollisions: newOrGrown.length, newOrGrownList: newOrGrown,
  touchedCount: touched.length,
};
fs.writeFileSync(`${OUT_DIR}/tmp_2026-09-12_bot8_batch_285_report.json`, JSON.stringify(report, null, 1));
console.log("\n\n=== VYSLEDEK ===");
console.log(`SAT kolizí s karoserií: ${satCollisions}`);
console.log(`Self-kolizí PO transformaci (mimo znama vnorovani): ${afterSelf.count} (z toho NOVYCH/ZVETSENYCH: ${newOrGrown.length})`);
console.log(`Seam gaps: ${seamChecks.map(s => `${s.seam}=${s.gap.toFixed(4)}mm`).join(", ")}`);
console.log(`\nUlozeno: tmp_2026-09-12_bot8_batch_285_report.json`);
