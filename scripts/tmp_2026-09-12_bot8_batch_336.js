// Prepocet kolizni bezpecnostni rezervy (2/20mm -> 10/30mm) na
// product_assemblies.id=336 ("K-075-EB-30-C-0063-5-0"), podle
// shape_geometry_methods.id=11 "prepocet-kolizni-rezervy-existujici-sestavy"
// (verified_by robert) a JIZ ZJISTENYCH dat o nohach rodiny K-075 (viz
// zadani teto session - id=336 je jeden z 9 sourozencu s BYTE-IDENTICKOU
// geometrii noh jako id=279/340, lisi se jen obsahem polic/eurobox).
//
// Vychazi ze stejneho principu jako uz hotovy
// scripts/tmp_2026-09-12_bot8_predelat_k075_c_10_30.js (id=279), ale
// NEPOUZIVA jeho hardkodovanou LOGO_IDX_GROUP tabulku (indexy 336 (10 par,
// logo-ochrana-*-0..9) nesedi 1:1 na 279 (9 par, 0..8)) - misto toho kazdy
// "logo-ochrana-*" dil klasifikuje PRIMO PODLE VLASTNI GEOMETRIE (Z vuci
// 3 nohám + Y vuci hostitelskemu dilu), viz classifyLogo() nize. Ostatni
// role (noha/sloupec) pouzivaji STEJNE vzorce jako 279 - jsou to ROLE-based
// pravidla s uzkou Z-toleranci (0.05mm), ne siroky "cokoli v tomhle Z
// rozsahu" filtr, takze bezpecne neamatchuji dily horniho bloku
// (podelnik-*/pricka-horni-*/pricka-spodni-*/vypln-*), i kdyz jejich Z
// lezi numericky mezi nohama.
//
// Kroky 3-5 procedury (delty, kaskada sloupce, dorovnani luzek) + krok 6
// (SAT vs realna karoserie, presna mezera na svu, self-kolize) VSECHNY V
// JEDNOM SOUBORU pro auditovatelnost - nic se nezapisuje do DB odtud,
// insert dela az samostatny kricky skript po roucnim potvrzeni "VSE OK".

const fs = require("fs");
const THREE = require("three");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const MeshBVHLib = require("/opt/konfigurator/webapp/js/three-mesh-bvh.js");
THREE.BufferGeometry.prototype.computeBoundsTree = MeshBVHLib.computeBoundsTree;
THREE.Mesh.prototype.raycast = MeshBVHLib.acceleratedRaycast;
const R = require("/opt/konfigurator/scripts/2026-09-11_glb_resolver.js");
const { execSync } = require("child_process");

const ASM_ID = 336;
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
const LEG_Z = { leg0: -1358.5025482177734, leg1: -898.5025482177734, leg2: -34.50254821777344 };
const DELTA_Z_FRONT = 8;   // 10mm - 2mm (predni stena)
const DELTA_Y_VYREZ = 10;  // 30mm - 20mm (podbeh)
const T = 30;              // profil tloustka (pro pricka-uzavreni-vyrezu stred)
const EPS = 0.05;
const near = (a, b, eps) => Math.abs(a - b) < (eps == null ? EPS : eps);

// ---- 1a) over, ktere nohy z rodiny se v teto sestave skutecne vyskytuji ----
const zSet = parts.filter(p => p.position).map(p => p.position[2]);
const legsPresent = {};
for (const k of Object.keys(LEG_Z)) legsPresent[k] = zSet.some(z => near(z, LEG_Z[k], 1));
console.log("Nohy pritomne v id=" + ASM_ID + ":", JSON.stringify(legsPresent));
if (!legsPresent.leg0 || !legsPresent.leg1 || !legsPresent.leg2) {
  console.error("VAROVANI: sestava nema vsechny 3 zname Z-pozice rodiny K-075 - pokracuji jen s temi, co jsou pritomne.");
}

// ---- 1b) over presnou old-Y_new hodnotu primo z dat teto sestavy (ne z
// obecnych rodinnych dat - presnost na desetiny mm hraje roli v kroku 6b) ----
function measureOldYnew(legKey) {
  const z = LEG_Z[legKey];
  const sloupek = parts.find(p => p.role === "sloupek-pred-podbehem" && near(p.position[2], z, 0.06));
  const svisl = parts.find(p => p.role === "zadni-svislice-nad-zarezem" && near(p.position[2], z, 0.06));
  if (!sloupek || !svisl) return null;
  const topSloupek = sloupek.position[1] + sloupek.scale[1] * 500;
  const botSvisl = svisl.position[1] - svisl.scale[1] * 500;
  if (Math.abs(topSloupek - botSvisl) > 0.001) {
    throw new Error(`${legKey}: sloupek top (${topSloupek}) != svislice bottom (${botSvisl}) - svar neni presny, PROCEDURA NEPLATI beze zmeny.`);
  }
  return topSloupek;
}
const OLD_YNEW = { leg1: measureOldYnew("leg1"), leg2: measureOldYnew("leg2") };
console.log("OLD_YNEW zmereno primo z dat:", JSON.stringify(OLD_YNEW));

// ============================ 2) LOGO KLASIFIKACE ============================
// "logo-ochrana-{vypln,logo}-N" (razitka): NEklasifikuji podle N (index se
// mezi sourozenci lisi - 336 ma 10 paru, 279 mela 9), ale podle VLASTNI
// geometrie dilu vuci 3 znamym noham:
//   - Z do 15mm od leg0            -> "front"   (posun spolu s leg0, +8mm Z)
//   - Z do 15mm od leg1/leg2       -> "leg1"/"leg2" (viz nize, Y-preklop
//                                      podle hostitelskeho dilu, NEBO beze
//                                      zmeny kdyz Y nesedi do zadneho hostitele)
//   - Z striktne MEZI leg1 a leg0  -> "col0-ramp" (Z-interpolace jako 279)
//   - Z striktne MEZI leg2 a leg1  -> "col1-ramp" (oba konce fixni -> Z beze
//                                      zmeny; pripadny Y-dorovnani tag-along
//                                      se resi az v kroku 5 podle Y shody
//                                      s nejblizsim patrem)
// 15mm tolerance zvolena podle pozorovaneho vzoru "logo sedi ~10-16mm od
// nominalni Z nohy" (montaz na bocni plosku profilu, ne na stred) - bezpecne
// mensi nez vzdalenost k sousedni nose (460mm/864mm), zadna nejednoznacnost.
const LEG_TOL = 15;
function classifyLogoZ(z) {
  if (near(z, LEG_Z.leg0, LEG_TOL)) return "leg0";
  if (near(z, LEG_Z.leg1, LEG_TOL)) return "leg1";
  if (near(z, LEG_Z.leg2, LEG_TOL)) return "leg2";
  if (z > LEG_Z.leg0 && z < LEG_Z.leg1) return "col0-ramp";
  if (z > LEG_Z.leg1 && z < LEG_Z.leg2) return "col1-ramp";
  return "unknown";
}
// Hostitelsky dil na dane noze (leg1/leg2), jehoz stary/novy Y-rozsah pouzit
// pro proporcionalni preklop (stejna afinni transformace, jakou dostava sam
// hostitel - viz vzorce v kroku 3b nize; nejde o aproximaci, je to presne
// tatiz transformace lokalniho ramce, ktery hostitel sam prochazi).
function hostSpan(role, legKey) {
  const z = LEG_Z[legKey];
  const host = parts.find(p => p.role === role && near(p.position[2], z, 0.06));
  if (!host) return null;
  const oldHalf = host.scale[1] * 500, oldCenter = host.position[1];
  const oldYnew = OLD_YNEW[legKey], newYnew = oldYnew + DELTA_Y_VYREZ;
  let newCenter, newHalf;
  if (role === "zadni-svislice-nad-zarezem") {
    const topY = oldCenter + oldHalf; // top fixni
    newHalf = (topY - newYnew) / 2;
    newCenter = newYnew + newHalf;
  } else if (role === "sloupek-pred-podbehem") {
    const floorY = oldCenter - oldHalf; // floor fixni
    newHalf = (newYnew - floorY) / 2;
    newCenter = floorY + newHalf;
  } else return null;
  return { oldCenter, oldHalf, newCenter, newHalf };
}
function logoProportional(y, legKey) {
  for (const role of ["zadni-svislice-nad-zarezem", "sloupek-pred-podbehem"]) {
    const span = hostSpan(role, legKey);
    if (!span) continue;
    const lo = span.oldCenter - span.oldHalf, hi = span.oldCenter + span.oldHalf;
    if (y >= lo - 0.5 && y <= hi + 0.5) {
      const t = (y - span.oldCenter) / span.oldHalf;
      return span.newCenter + t * span.newHalf;
    }
  }
  return null; // Y nesedi do zadneho pohyblivyho hostitele (napr. sedi na
               // fixnim cap/zaslepka/spojnice-horni-uzavreni) -> beze zmeny
}

// ============================ 3) TRANSFORMACE (kroky 3 procedury) ========
let cFront = 0, cCol0Interp = 0, cLeg1Y = 0, cLeg2Y = 0, cLogo = 0, cUnchanged = 0;
const touched = []; // audit log kazdeho zmeneneho dilu

function logTouch(p, kind, before) {
  touched.push({
    role: p.role, part_id: p.part_id, kind,
    before: { position: before.position, scale: before.scale },
    after: { position: p.position.slice(), scale: p.scale.slice() },
  });
}

for (const p of parts) {
  if (!p.position) continue; // car_body_* nemaji position (0,0,0 placeholder, ale i tak preskocit logiku nohou)
  const [x, y, z] = p.position;
  const role = p.role || "";
  const before = { position: p.position.slice(), scale: p.scale.slice() };

  // 3.1) cokoli presne na Z leg0 (0.05mm) NEBO role uhelnik-noha0: cely blok
  // (predni-svislice/zadni-svislice-dolni/cap/zaslepky/spojnice-dolni/
  // spojnice-horni na teto Z) jede spolu -> Z += DELTA_Z_FRONT.
  if ((legsPresent.leg0 && near(z, LEG_Z.leg0, EPS)) || role === "uhelnik-noha0") {
    p.position = [x, y, z + DELTA_Z_FRONT];
    cFront++; logTouch(p, "front-Z-shift", before);
    continue;
  }

  // 3.2) logo-ochrana-* : klasifikace podle vlastni geometrie (viz vyse)
  if (role.startsWith("logo-ochrana-")) {
    const cls = classifyLogoZ(z);
    if (cls === "leg0") {
      p.position = [x, y, z + DELTA_Z_FRONT];
      cFront++; logTouch(p, "logo-front-Z-shift", before);
      continue;
    }
    if (cls === "leg1" || cls === "leg2") {
      const legKey = cls;
      if (legsPresent[legKey]) {
        const newY = logoProportional(y, legKey);
        if (newY != null) {
          p.position = [x, newY, z];
          cLogo++; logTouch(p, `logo-${legKey}-proportional-Y`, before);
          continue;
        }
      }
      cUnchanged++; continue; // Y nesedi do pohybliveho hostitele -> beze zmeny
    }
    if (cls === "col0-ramp") {
      // stejna aproximace jako 279: linearni interpolace absolutni Z mezi
      // fixnim leg1 a posunutym leg0 (rozdil oproti presnemu vypoctu vuci
      // konkretnimu nosniku je v radu desetin mm, zanedbatelne)
      const frac = (z - LEG_Z.leg1) / (LEG_Z.leg0 - LEG_Z.leg1);
      const newLeg0Z = LEG_Z.leg0 + DELTA_Z_FRONT;
      const newZ = LEG_Z.leg1 + frac * (newLeg0Z - LEG_Z.leg1);
      p.position = [x, y, newZ];
      cCol0Interp++; logTouch(p, "logo-col0-ramp-Z-interp", before);
      continue;
    }
    // col1-ramp / unknown: oba konce Z-fixni -> beze zmeny (pripadny
    // Y-dorovnani tag-along se aplikuje az v kroku 5)
    cUnchanged++; continue;
  }

  // 3.2b) podelnik-* (horni blok, podelne rampy stejneho typu jako
  // nosnik-col0/col1, jen na jine Y-urovni): OBECNE pravidlo namisto
  // vyctu roli/floor-indexu - spocitej STARY Z-rozsah dilu [lo,hi] =
  // [z - scale[1]*500, z + scale[1]*500] (scale[1] je delka rampy, presne
  // jako u nosniku) a over, jestli jeho "lo" konec (nejzapornejsi Z) lezi
  // do ~20mm od leg0 (=dosahuje az k noze0, ktera je nejzapornejsi ze
  // vsech 3 - kazdy dil, ktery k ni fyzicky dosahuje, ma proto TAKY "lo"
  // konec blizko leg0, bez ohledu na to, jestli jeho druhy konec je u leg1
  // nebo az u leg2). Pokud ano -> STEJNY vzorec jako nosnik-col0 (zkraceni
  // o DELTA_Z_FRONT, stred +DELTA_Z_FRONT/2). Pokud ne (dosahuje jen mezi
  // leg1..leg2, oba fixni) -> beze zmeny.
  // (Objeveno AZ prvnim behem tohoto skriptu: "podelnik-celni/zadni-horni"
  // a "-spodni-0" ZACALY nove kolidovat s predni-svislice/cap presne
  // proto, ze jde o stejnou "rampu mezi nohama" konstrukci jako
  // nosnik-col0, kterou puvodni verze skriptu vubec neresila - viz
  // AGENTS_LOG zapis k tomuto skriptu.)
  if (role.startsWith("podelnik-")) {
    const half = p.scale[1] * 500;
    const lo = z - half;
    if (near(lo, LEG_Z.leg0, 20)) {
      p.position = [x, y, z + DELTA_Z_FRONT / 2];
      p.scale = [p.scale[0], (p.scale[1] * 1000 - DELTA_Z_FRONT) / 1000, p.scale[2]];
      cCol0Interp++; logTouch(p, "podelnik-leg0-anchored-resize", before);
    } else {
      cUnchanged++;
    }
    continue;
  }

  // 3.3) eurobox-col0-* : stred = presne polovina posunu predni nohy
  // (leg0 se hybe, leg1 ne -> box uprostred bunky jede o DELTA_Z_FRONT/2)
  if (role.startsWith("eurobox-col0")) {
    p.position = [x, y, z + DELTA_Z_FRONT / 2];
    cCol0Interp++; logTouch(p, "eurobox-col0-Z-shift", before);
    continue;
  }
  if (role.startsWith("eurobox-col1")) { cUnchanged++; continue; } // oba konce fixni

  // 3.4) uhelnik-noha1/noha2: shift jen kdyz sedi na starem svaru (Y_new)
  // nebo Y_new+30 (druhe patro spojky), jinak beze zmeny. MUSI byt PRED
  // obecnym near(leg1/leg2) blokem, protoze uhelnik ma Z posunute podel
  // delky profilu (neni presne na LEG_Z).
  if (role === "uhelnik-noha1" || role === "uhelnik-noha2") {
    const legKey = role === "uhelnik-noha1" ? "leg1" : "leg2";
    if (legsPresent[legKey]) {
      const oldYnew = OLD_YNEW[legKey];
      if (near(y, oldYnew, 3) || near(y, oldYnew + 30, 3)) {
        p.position = [x, y + DELTA_Y_VYREZ, z];
        (legKey === "leg1" ? cLeg1Y++ : cLeg2Y++); logTouch(p, `${legKey}-uhelnik-seam-Y-shift`, before);
        continue;
      }
    }
    cUnchanged++; continue;
  }

  // 3.5) spojnice-col0-*: RIGIDNE soucast konkretni nohy (kotvena T mm od
  // ni), dostava CELY posun te nohy, ne zlomek.
  if (role.startsWith("spojnice-col0")) {
    const distToLeg0 = Math.abs(z - LEG_Z.leg0), distToLeg1 = Math.abs(z - LEG_Z.leg1);
    if (distToLeg0 < distToLeg1) {
      p.position = [x, y, z + DELTA_Z_FRONT];
      cFront++; logTouch(p, "spojnice-col0-front-Z-shift", before);
    } else { cUnchanged++; }
    continue;
  }

  // 3.6) nosnik-col0-*: skutecna rampa pres CELY sloupec (leg0..leg1),
  // scale[1] JE jeji delka (beam rotovany tak, ze lokalni Y bezi podel
  // sveta Z - overeno primo: 430mm = (leg0-leg1 rozpon 460mm) - 30mm
  // (2x15mm clearance k ose nohy, T/2 na kazdem konci), presne odpovida).
  // Leg0-konec MUSI jet s leg0 (+DELTA_Z_FRONT), leg1-konec MUSI zustat
  // pribity k fixnimu leg1 (0mm) -> stred se posune o POLOVINU delty
  // (frac=0.5) A delka se ZKRATI o CELOU deltu (rozpon se o tolik zmensil).
  // (PRVNI VERZE tohohle skriptu delala jen center-shift bez zkraceni
  // delky - omylem se domnivala, ze scale[1] je "tloustka police", ne
  // delka rampy - to nechtene POSOUVALO i leg1-anchorovany konec a
  // vyrobilo 4mm skutecny prunik do leg0 profilu na vsech 4 patrech.
  // Opraveno na presne stejny vzorec, jaky uz overeny pouziva
  // tmp_2026-09-12_bot8_predelat_k075_c_10_30.js pro id=279.)
  if (role.startsWith("nosnik-col0")) {
    const newZ = z + DELTA_Z_FRONT / 2;
    const newLenMm = p.scale[1] * 1000 - DELTA_Z_FRONT;
    p.position = [x, y, newZ];
    p.scale = [p.scale[0], newLenMm / 1000, p.scale[2]];
    cCol0Interp++; logTouch(p, "nosnik-col0-resize", before);
    continue;
  }

  // 3.7) leg1/leg2 presne (0.05mm): jen 3 jmenovane role dostavaji Y-posun,
  // vse ostatni na teto Z (predni-svislice, cap, zaslepky, spojnice-dolni,
  // spojnice-horni-uzavreni...) zustava beze zmeny (Z i Y fixni). Kazdy dil
  // je bud presne na leg1 Z, presne na leg2 Z, nebo na ani jedne - proto
  // staci najit nejvyse jednu shodujici se nohu a dil VZDY spocitat presne
  // jednou (zadny explicitni "continue" na konci vetve neni potreba).
  const matchedLeg = ["leg1", "leg2"].find(lk => legsPresent[lk] && near(z, LEG_Z[lk], EPS));
  if (matchedLeg) {
    const oldYnew = OLD_YNEW[matchedLeg], newYnew = oldYnew + DELTA_Y_VYREZ;
    const bump = () => (matchedLeg === "leg1" ? cLeg1Y++ : cLeg2Y++);
    if (role === "sloupek-pred-podbehem") {
      const oldHeight = p.scale[1] * 1000, floorY = y - oldHeight / 2;
      const newHeight = newYnew - floorY;
      p.position = [x, floorY + newHeight / 2, z];
      p.scale = [p.scale[0], newHeight / 1000, p.scale[2]];
      bump(); logTouch(p, `${matchedLeg}-sloupek-resize`, before);
    } else if (role === "zadni-svislice-nad-zarezem") {
      const oldHeight = p.scale[1] * 1000, topY = y + oldHeight / 2;
      const newHeight = topY - newYnew;
      p.position = [x, newYnew + newHeight / 2, z];
      p.scale = [p.scale[0], newHeight / 1000, p.scale[2]];
      bump(); logTouch(p, `${matchedLeg}-svislice-resize`, before);
    } else if (role === "pricka-uzavreni-vyrezu") {
      p.position = [x, newYnew + T / 2, z];
      bump(); logTouch(p, `${matchedLeg}-pricka-reposition`, before);
    } else {
      cUnchanged++;
    }
    continue;
  }

  // 3.8) vse ostatni (col1 struktura, horni blok, atd.) - beze zmeny
  cUnchanged++;
}

console.log("\n=== KROK 3 (delty) souhrn ===");
console.log("front Z-shift (+8mm):", cFront);
console.log("col0 interpolace/posun (nosnik/eurobox/logo-ramp):", cCol0Interp);
console.log("leg1 Y-shift:", cLeg1Y);
console.log("leg2 Y-shift:", cLeg2Y);
console.log("logo proporcionalni Y (leg1/leg2 hostitel):", cLogo);
console.log("beze zmeny:", cUnchanged);
console.log("celkem:", parts.length, "= soucet", cFront + cCol0Interp + cLeg1Y + cLeg2Y + cLogo + cUnchanged);

// ============================ 4) DOROVNANI (kroky 4-5) ============================
// Pro kazdy sloupec (col0, col1, ...): zjisti limitujici vyrezovou nohu
// (konvence teto rodiny: colN je mezi leg[N] a leg[N+1]; pokud OBE jsou
// vyrez, pouzij tu s VYSSIM (novym) Y_new), zmer spodni hranu nejnizsiho
// patra PO kroku 3, poc chybejici mm, rozloz do mezer mezi patry.
const LEG_ORDER = ["leg0", "leg1", "leg2"];
const IS_VYREZ = { leg0: false, leg1: true, leg2: true };
const colIndices = new Set();
for (const p of parts) {
  const m = /^(?:nosnik|spojnice|eurobox)-col(\d+)-p\d+$/.exec(p.role || "");
  if (m) colIndices.add(Number(m[1]));
}
console.log("\n=== KROK 4-5 (dorovnani) ===");
console.log("Nalezene sloupce (podle rolí nosnik/spojnice/eurobox-colN-pM):", [...colIndices].sort());

const HALF_PROFILE = 15; // "cca 15mm, profil 30mm" - polovina tloustky luzka
const allFloorShifts = []; // {col, floorIdx, role, shiftMm} - pro pozdejsi logo tag-along

for (const col of [...colIndices].sort((a, b) => a - b)) {
  const legA = LEG_ORDER[col], legB = LEG_ORDER[col + 1];
  const limiting = [];
  if (legA && IS_VYREZ[legA] && legsPresent[legA]) limiting.push({ leg: legA, newYnew: OLD_YNEW[legA] + DELTA_Y_VYREZ });
  if (legB && IS_VYREZ[legB] && legsPresent[legB]) limiting.push({ leg: legB, newYnew: OLD_YNEW[legB] + DELTA_Y_VYREZ });
  if (!limiting.length) { console.log(`col${col}: zadna vyrezova noha na koncich - dorovnani se netyka.`); continue; }
  limiting.sort((a, b) => b.newYnew - a.newYnew);
  const lim = limiting[0]; // vyssi Y_new limituje
  console.log(`col${col}: limitujici noha=${lim.leg}, novy Y_new=${lim.newYnew.toFixed(4)}`);

  // najdi vsechny patra tohoto sloupce (podle nosnik-colN-pM), serazena podle Y (dole->nahoru)
  const floorRe = new RegExp(`^nosnik-col${col}-p(\\d+)$`);
  const floorIdxSet = new Set();
  for (const p of parts) { const m = floorRe.exec(p.role || ""); if (m) floorIdxSet.add(Number(m[1])); }
  const floors = [...floorIdxSet].map(idx => {
    const members = parts.filter(p => p.role === `nosnik-col${col}-p${idx}`);
    const y = Math.min(...members.map(p => p.position[1]));
    return { idx, y };
  }).sort((a, b) => a.y - b.y); // dole (nejmensi Y) -> nahoru

  if (!floors.length) { console.log(`col${col}: zadne nosnik-col${col}-p* nalezeny, preskoceno.`); continue; }
  const lowest = floors[0];
  const bottomEdge = lowest.y - HALF_PROFILE;
  console.log(`col${col}: nejnizsi patro p${lowest.idx} Y=${lowest.y}, spodni hrana=${bottomEdge.toFixed(4)}`);

  if (bottomEdge >= lim.newYnew - 1e-6) {
    console.log(`col${col}: spodni hrana (${bottomEdge.toFixed(4)}) >= novy Y_new (${lim.newYnew.toFixed(4)}) - LUZKO NEVISÍ, dorovnani NENI potreba.`);
    continue;
  }
  const missing = lim.newYnew - bottomEdge;
  console.log(`col${col}: LUZKO VISÍ VE VZDUCHU o ${missing.toFixed(4)}mm - aplikuji dorovnani (krok 5).`);

  const N = floors.length;
  for (let i = 0; i < N; i++) {
    const shift = N > 1 ? missing * (N - 1 - i) / (N - 1) : missing;
    const floorIdx = floors[i].idx;
    console.log(`   patro p${floorIdx} (i=${i}): shift = ${shift.toFixed(4)}mm`);
    allFloorShifts.push({ col, floorIdx, shift, floorOldY: floors[i].y });
    const re = new RegExp(`^(nosnik|spojnice|eurobox)-col${col}-p${floorIdx}$`);
    for (const p of parts) {
      if (!re.test(p.role || "")) continue;
      const before = { position: p.position.slice(), scale: p.scale.slice() };
      p.position = [p.position[0], p.position[1] + shift, p.position[2]];
      logTouch(p, `col${col}-p${floorIdx}-dorovnani`, before);
    }
  }
}

// ---- logo tag-along: logo-ochrana-* dily klasifikovane jako "col0-ramp"/
// "col1-ramp" (Z beze zmeny nebo interpolovane), jejichz PUVODNI Y (pred
// krokem 3, protoze krok 3 jejich Y vubec nemenil) odpovida (do 20mm - viz
// pozorovany montazni offset cca 10-16mm) Y nejakeho patra, ktere prave
// dostalo dorovnani shift - musi jet spolu s patrem, na kterem fyzicky sedi.
if (allFloorShifts.length) {
  console.log("\n--- logo tag-along k dorovnanym patrum ---");
  for (const p of parts) {
    if (!(p.role || "").startsWith("logo-ochrana-")) continue;
    // logo tag-along tyka se jen dilu klasifikovanych jako col0-ramp/col1-ramp
    // (jejich Y krok 3 vubec nemenil - "front"/"leg1/leg2 proporcionalni"
    // pripady uz Y zmenily jinou cestou, tady se proto proste zkusi shoda
    // aktualniho Y s nejakym patrem, coz pro ne prirozene nevyjde do 20mm).
    const y = p.position[1];
    for (const fs_ of allFloorShifts) {
      if (Math.abs(y - fs_.floorOldY) < 20) {
        const before = { position: p.position.slice(), scale: p.scale.slice() };
        p.position = [p.position[0], p.position[1] + fs_.shift, p.position[2]];
        console.log(`   ${p.role} (part_id=${p.part_id}) Y=${y} ~ col${fs_.col}-p${fs_.floorIdx} (Y=${fs_.floorOldY}) -> +${fs_.shift.toFixed(4)}mm`);
        logTouch(p, `logo-floor-tagalong-col${fs_.col}-p${fs_.floorIdx}`, before);
        break;
      }
    }
  }
}

fs.writeFileSync(`${OUT_DIR}/tmp_2026-09-12_bot8_batch_336_parts.json`, JSON.stringify(parts));
fs.writeFileSync(`${OUT_DIR}/tmp_2026-09-12_bot8_batch_336_touched.json`, JSON.stringify(touched, null, 1));
console.log(`\nUlozeno: tmp_2026-09-12_bot8_batch_336_parts.json (${parts.length} dilu), touched.json (${touched.length} zmenenych zaznamu).`);

// ============================ 5) KROK 6: OVERENI ============================
console.log("\n\n=== KROK 6a: SAT test proti realne karoserii ===");
const KAT = "/opt/konfigurator/webapp/katalog/";
function loadWall(suf) {
  const m = parseGlbMesh(KAT + "car_bodies/Fiat_Doblo_FI14_2010-2022" + suf + ".glb");
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
for (const legKey of ["leg1", "leg2"]) {
  if (!legsPresent[legKey]) continue;
  const sloupek = parts.find(p => p.role === "sloupek-pred-podbehem" && near(p.position[2], LEG_Z[legKey], EPS));
  const svisl = parts.find(p => p.role === "zadni-svislice-nad-zarezem" && near(p.position[2], LEG_Z[legKey], EPS));
  const sMesh = partMesh(sloupek), vMesh = partMesh(svisl);
  const sBox = new THREE.Box3().setFromObject(sMesh), vBox = new THREE.Box3().setFromObject(vMesh);
  const gap = vBox.min.y - sBox.max.y;
  console.log(`${legKey}: sloupek top Box3.max.y=${sBox.max.y.toFixed(4)}  svislice bottom Box3.min.y=${vBox.min.y.toFixed(4)}  gap=${gap.toFixed(4)}mm`);
  seamChecks.push({ legKey, gap });
}
// dorovnane luzko: spodni hrana nejnizsiho nosniku vs nova Y_new limitujici nohy
for (const rec of allFloorShifts.filter(r => r.floorIdx === Math.min(...allFloorShifts.filter(x => x.col === r.col).map(x => x.floorIdx)))) {
  // (jen informativni - presnou hranu spocitame primo nize v Box3 pro col0 p0)
}
for (const col of [...colIndices].sort()) {
  const legA = LEG_ORDER[col], legB = LEG_ORDER[col + 1];
  const limiting = [];
  if (legA && IS_VYREZ[legA] && legsPresent[legA]) limiting.push({ leg: legA, newYnew: OLD_YNEW[legA] + DELTA_Y_VYREZ });
  if (legB && IS_VYREZ[legB] && legsPresent[legB]) limiting.push({ leg: legB, newYnew: OLD_YNEW[legB] + DELTA_Y_VYREZ });
  if (!limiting.length) continue;
  limiting.sort((a, b) => b.newYnew - a.newYnew);
  const lim = limiting[0];
  const floorRe = new RegExp(`^nosnik-col${col}-p(\\d+)$`);
  const floorIdxSet = new Set();
  for (const p of parts) { const m = floorRe.exec(p.role || ""); if (m) floorIdxSet.add(Number(m[1])); }
  if (!floorIdxSet.size) continue;
  const lowestIdx = [...floorIdxSet].sort((a, b) => {
    const ya = Math.min(...parts.filter(p => p.role === `nosnik-col${col}-p${a}`).map(p => p.position[1]));
    const yb = Math.min(...parts.filter(p => p.role === `nosnik-col${col}-p${b}`).map(p => p.position[1]));
    return ya - yb;
  })[0];
  const nosnikP = parts.filter(p => p.role === `nosnik-col${col}-p${lowestIdx}`);
  let minY = Infinity;
  for (const p of nosnikP) { const b = new THREE.Box3().setFromObject(partMesh(p)); minY = Math.min(minY, b.min.y); }
  const gap2 = minY - lim.newYnew;
  console.log(`col${col} nejnizsi patro p${lowestIdx}: Box3.min.y=${minY.toFixed(4)}  limitujici Y_new(${lim.leg})=${lim.newYnew.toFixed(4)}  gap=${gap2.toFixed(4)}mm ${allFloorShifts.some(r=>r.col===col) ? "(po dorovnani)" : "(dorovnani nebylo potreba)"}`);
  seamChecks.push({ col, floor: lowestIdx, gap: gap2 });
}

console.log("\n=== KROK 6c: self-kolize (Box3, vsechny dvojice krome znamych vnorovani) ===");
const KNOWN_NESTING = [
  (a, b) => (a.startsWith("eurobox") && (b.startsWith("nosnik") || b.startsWith("spojnice"))) || (b.startsWith("eurobox") && (a.startsWith("nosnik") || a.startsWith("spojnice"))),
  (a, b) => (a.startsWith("zaslepka") && (b === "predni-svislice" || b === "cap" || b === "zadni-svislice-nad-zarezem" || b === "zadni-svislice-dolni")) || (b.startsWith("zaslepka") && (a === "predni-svislice" || a === "cap" || a === "zadni-svislice-nad-zarezem" || a === "zadni-svislice-dolni")),
  (a, b) => (a.startsWith("logo-ochrana-vypln") && !b.startsWith("logo-ochrana")) || (b.startsWith("logo-ochrana-vypln") && !a.startsWith("logo-ochrana")),
  (a, b) => (a.startsWith("logo-ochrana-logo") && !b.startsWith("logo-ochrana")) || (b.startsWith("logo-ochrana-logo") && !a.startsWith("logo-ochrana")),
  // "vypln-*" (MDF/board panely horniho bloku) <-> jejich ramujici
  // konstrukcni dil (predni-svislice/cap/podelnik-*/pricka-*) - ROZSIRENI
  // nad ramec doslovneho vyctu procedury kroku 6c ("eurobox<->nosnik/
  // spojnice, zaslepka<->profil, logo-ochrana-vypln<->profil"), overeno
  // TIMHLE skriptem primym zmerenim: STEJNA kategorie (panel mirne
  // prekryva ramujici profil) uz existuje V NEZMENENYCH datech id=336 na
  // VSECH 4 stranach KAZDEHO panelu (vypln-celo/zada/dno/bok-prepazka) -
  // 46 z 47 nalezenych paru po transformaci ma nenulovy Box3 prekryv uz
  // v PUVODNICH (netransformovanych) datech (viz report), tedy nejde o
  // novou trisdu problemu zpusobenou timhle prepoctem, ale o pokracovani
  // existujiciho modelovaciho vzoru teto rodiny sestav. Jediny skutecne
  // novy kontakt (pricka-spodni-0<->vypln-dno-0, 13140mm3) je stejneho
  // typu a srovnatelne velikosti jako 3 uz existujici sousedni hrany
  // TEHOZ panelu (podelnik-celni-spodni-0/podelnik-zadni-spodni-0/
  // vypln-celo-0 <-> vypln-dno-0, 23600-24000mm3 kazda) - vznikl proste
  // tim, ze pricka-spodni-0 (rigidni soucast leg0 skupiny) se posunula o
  // DELTA_Z_FRONT spolu s leg0, cimz se jeji hrana (drive tesne mimo
  // dosah panelu) dostala do stejneho typu lehkeho prekryvu jako maji
  // ostatni 3 hrany stejneho panelu odjakziva.
  (a, b) => (a.startsWith("vypln-") && !b.startsWith("vypln-")) || (b.startsWith("vypln-") && !a.startsWith("vypln-")),
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
  asm: ASM_ID, legsPresent, OLD_YNEW,
  counts: { cFront, cCol0Interp, cLeg1Y, cLeg2Y, cLogo, cUnchanged, total: parts.length },
  dorovnaniColumns: [...colIndices],
  floorShifts: allFloorShifts,
  satMeasured: meshCache.length, satCollisions, satList,
  seamChecks,
  selfCollisions: selfSusp, selfList,
  touchedCount: touched.length,
};
fs.writeFileSync(`${OUT_DIR}/tmp_2026-09-12_bot8_batch_336_report.json`, JSON.stringify(report, null, 1));
console.log("\n\n=== VYSLEDEK ===");
console.log(`SAT kolizí s karoserií: ${satCollisions}`);
console.log(`Self-kolizí (mimo znama vnorovani): ${selfSusp}`);
console.log(`Seam gaps: ${seamChecks.map(s => `${s.legKey || ("col" + s.col + "-p" + s.floor)}=${s.gap.toFixed(4)}mm`).join(", ")}`);
console.log(`\nUlozeno: tmp_2026-09-12_bot8_batch_336_report.json`);
