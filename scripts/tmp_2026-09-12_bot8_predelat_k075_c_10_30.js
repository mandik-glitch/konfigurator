// Predelani K-075 Doblo L1 "verze C" (product_assemblies.id=279, ZAKAZ
// PRESAVE od 2026-09-11 - viz AGENTS_LOG.md ~radek 28001) na novou
// bezpecnostni podminku (predni stena 2mm->10mm, podbeh 20mm->30mm).
//
// PRINCIP (bez znovu-hledani sloupcu/typu noh - zachovava PRESNE strukturu
// 279): backoff se v kolizni-krokovani (car_body_placement_methods.id=1,
// shape_geometry_methods.id=6) VZDY aplikuje AZ PO nalezeni "bottomY_kolize"/
// kolizniho bodu 1mm krokovanim - ten bod je NEZAVISLY na zvolenem
// backoffu. Proto:
//   deltaZ_predni_noha = novy_backoff_predni(10) - stary_backoff_predni(2) = +8mm
//   deltaY_vyrezova_noha = novy_backoff_podbeh(30) - stary_backoff_podbeh(20) = +10mm
// (presna aritmeticka konstanta, ne odhad) - odvozeno a zdokumentovano
// primo v teto session, viz AGENTS_LOG.md zapis k tomuto skriptu.
//
// 279 ma 3 nohy: leg0 (Z=-1358.5, "plain", nejblize prepazce B) je jedina,
// co se hybe v Z. leg1 (Z=-898.5) a leg2 (Z=-34.5) jsou "vyrez" (podbeh) -
// jejich Z se NEMENI, meni se jen Y_new (vyska prechodu sloupek/svislice).
//
// NEZAPISUJE se do product_assemblies.id=279 (ani zadneho z 28 zakazanych
// ID) - vysledek jde VYHRADNE do noveho custom_shapes radku.

const fs = require("fs");
const THREE = require("three");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const MeshBVHLib = require("/opt/konfigurator/webapp/js/three-mesh-bvh.js");
THREE.BufferGeometry.prototype.computeBoundsTree = MeshBVHLib.computeBoundsTree;
THREE.Mesh.prototype.raycast = MeshBVHLib.acceleratedRaycast;

const SRC = JSON.parse(fs.readFileSync("/tmp/claude-0/-opt-konfigurator/c0c788fb-0783-4d56-adb5-543ba6b0dda8/scratchpad/assembly279.json", "utf8"));
const parts = SRC.parts.map(p => JSON.parse(JSON.stringify(p))); // deep clone, nemenime SRC

const LEG_Z = { leg0: -1358.5025482177734, leg1: -898.5025482177734, leg2: -34.50254821777344 };
const DELTA_Z_FRONT = 8;     // 10mm - 2mm
const DELTA_Y_VYREZ = 10;    // 30mm - 20mm
const EPS = 0.01;
const near = (a, b, eps) => Math.abs(a - b) < (eps == null ? EPS : eps);

// Presne zmerene stare Y_new (seam sloupek<->zadni-svislice-nad-zarezem),
// zmereno primo z dat 279 (viz AGENTS_LOG zapis):
const OLD_YNEW = { leg1: 101.5001792907715, leg2: 53.50017929077148 };
const T = 30; // profil tloustka

// logo-ochrana-{vypln,logo}-N: N zjisteno RUCNE zmerenim skutecne Z
// kazdeho indexu v 279 (viz AGENTS_LOG zapis) - Z talovance je nespolehliva
// (logo-8 sedi -15.7mm od leg0, vypln-8 jen -10mm - ruzny offset stejne
// dvojice), index sam je ale jednoznacny a stabilni.
const LOGO_IDX_GROUP = { 0: "col0", 1: "front", 2: "col1", 3: "leg2-fixed", 4: "col0", 5: "front", 6: "col0", 7: "col1", 8: "front" };
function logoGroup(role) {
  const m = /^logo-ochrana-(?:vypln|logo)-(\d+)$/.exec(role);
  return m ? LOGO_IDX_GROUP[Number(m[1])] : null;
}

let countFrontShift = 0, countCol0Interp = 0, countLeg1Y = 0, countLeg2Y = 0, countUnchanged = 0;
const touchedRoles = new Set();

for (const p of parts) {
  const [x, y, z] = p.position;
  const role = p.role || "";
  const lg = logoGroup(role);

  // 1) leg0 (predni, plain) - presne na Z leg0, NEBO uhelnik-noha0 (offset
  //    podel delky profilu, klasifikovano podle role, ne podle Z), NEBO
  //    logo-ochrana s indexem patricim leg0 (viz LOGO_IDX_GROUP)
  if (near(z, LEG_Z.leg0, 0.05) || role === "uhelnik-noha0" || lg === "front") {
    p.position = [x, y, z + DELTA_Z_FRONT];
    countFrontShift++;
    touchedRoles.add("front:" + role);
    continue;
  }
  if (lg === "leg2-fixed") { countUnchanged++; touchedRoles.add("leg2-logo-unaffected:" + role); continue; }

  // 1b) eurobox-col0-*/eurobox-col1-* - KLASIFIKOVANO VYHRADNE PODLE ROLE,
  //     ne podle position.z: eurobox ma po -90 rotaci pivot posunuty mimo
  //     nominalni rozsah sveho sloupce (napr. eurobox-col1-p0 vysel na
  //     Z=-1061, coz numericky spada do "col0" okna, presto patri do col1
  //     a NESMI se hnout). col0 box je strukturalne stredovany v ramci
  //     sve bunky (nosnik/spojnice tam sedi vzdy presne na stredu Z), tedy
  //     posun = presne polovina posunu prednI nohy (leg0 se hybe, leg1 ne).
  //     col1 box je mezi leg1/leg2, oba fixni -> zadny posun.
  if (role.startsWith("eurobox-col0")) {
    p.position = [x, y, z + DELTA_Z_FRONT / 2];
    countCol0Interp++; touchedRoles.add("col0-box:" + role); continue;
  }
  if (role.startsWith("eurobox-col1")) {
    countUnchanged++; touchedRoles.add("col1-box:" + role + "(unaffected)"); continue;
  }

  // 2b) uhelnik-noha1/noha2 - klasifikovano podle ROLE (jejich Z neni
  //     presne rovna Z nohy, jsou posunute podel delky profilu) - shift
  //     jen kdyz sedi na starem seamu (Y_new) nebo Y_new+30 (typicky
  //     odsazeni druheho patra spojky), jinak beze zmeny (top/floor
  //     kotvene brackety seam vubec necitI). MUSI byt PRED cislenym
  //     krokem "2" (numericka Z-interpolace) - noha1 ma Z v numerickem
  //     rozsahu col0, ale patri sem podle role, ne podle Z.
  if (role === "uhelnik-noha1" || role === "uhelnik-noha2") {
    const oldYnew = role === "uhelnik-noha1" ? OLD_YNEW.leg1 : OLD_YNEW.leg2;
    if (near(y, oldYnew, 3) || near(y, oldYnew + 30, 3)) {
      p.position = [x, y + DELTA_Y_VYREZ, z];
      (role === "uhelnik-noha1" ? countLeg1Y++ : countLeg2Y++);
      touchedRoles.add(role + "(seam)");
    } else {
      countUnchanged++;
      touchedRoles.add(role + "(unaffected)");
    }
    continue;
  }

  // 2a) spojnice-col0-pN - KRATKY prycny spoj (delka D-2T, nemeni se),
  //     kotveny T mm od JEDNE konkretni nohy (zmereno: -1328.5=leg0+T,
  //     -928.5=leg1-T) - NENI to bod na "protahujici se" rampe, je RIGIDNE
  //     soucasti FRAME konkretni nohy. Musi dostat CELY posun te nohy
  //     (ne zlomek), jinak vznikne mezera/prekryv vuci noze samotne
  //     (presne tohle zpusobilo 16 falesnych self-prekryvu v prvni verzi
  //     tohohle skriptu - viz AGENTS_LOG zapis).
  if (role.startsWith("spojnice-col0")) {
    const distToLeg0 = Math.abs(z - LEG_Z.leg0), distToLeg1 = Math.abs(z - LEG_Z.leg1);
    if (distToLeg0 < distToLeg1) { p.position = [x, y, z + DELTA_Z_FRONT]; countFrontShift++; touchedRoles.add("front-spojnice:" + role); }
    else { countUnchanged++; touchedRoles.add("fixed-spojnice:" + role); }
    continue;
  }

  // 2b2) nosnik-col0-pN - SKUTECNA rampa přes CELÝ sloupec (zmereno: spojuje
  //      leg0+T/2 .. leg1-T/2, delka=presne rozpon-T), centrovana presne v
  //      polovine rozponu - stred se posune o polovinu DELTA_Z_FRONT (jako
  //      linearni interpolace, frac=0.5 presne) A DELKA (scale.y) se
  //      zkrati o CELY DELTA_Z_FRONT (rozpon se zmensil o tolik).
  if (role.startsWith("nosnik-col0")) {
    const newZ = z + DELTA_Z_FRONT / 2;
    const newLenMm = p.scale[1] * 1000 - DELTA_Z_FRONT;
    p.position = [x, y, newZ];
    p.scale = [p.scale[0], newLenMm / 1000, p.scale[2]];
    countCol0Interp++;
    touchedRoles.add("nosnik-col0-resize:" + role);
    continue;
  }

  // 2c) logo-ochrana stampy MONTOVANE NA nosnik (idx 0,4,6 - lg==="col0")
  //     - sedi niekde podel delky rampy, ne presne ve stredu; aproximace:
  //     stejna linearni interpolace jako drive (frac dle absolutni Z mezi
  //     fixnim leg1 a posunutym leg0) - PRESNE by se melo pocitat relativne
  //     k nosniku, ale rozdil je v radu desetin mm na 8mm celkove zmene,
  //     zanedbatelne vuci realne velikosti stampu. Oznaceno v hlaseni jako
  //     aproximace.
  if (lg === "col0") {
    const frac = (z - LEG_Z.leg1) / (LEG_Z.leg0 - LEG_Z.leg1); // 0 u leg1, 1 u leg0
    const newLeg0Z = LEG_Z.leg0 + DELTA_Z_FRONT;
    const newZ = LEG_Z.leg1 + frac * (newLeg0Z - LEG_Z.leg1);
    p.position = [x, y, newZ];
    countCol0Interp++;
    touchedRoles.add("col0-logo-approx:" + role);
    continue;
  }

  // 3) leg1 vyrezova noha - jen role vazane na cutout seam Y_new
  if (near(z, LEG_Z.leg1, 0.05)) {
    const oldYnew = OLD_YNEW.leg1, newYnew = oldYnew + DELTA_Y_VYREZ;
    if (role === "sloupek-pred-podbehem") {
      // span [floor, Y_new] -> [floor, novy Y_new]; floor = stary spodek = y - scale.y/2*1000... presneji: stary bottom = position.y - height/2
      const oldHeight = p.scale[1] * 1000, floorY = y - oldHeight / 2;
      const newHeight = newYnew - floorY;
      p.position = [x, floorY + newHeight / 2, z];
      p.scale = [p.scale[0], newHeight / 1000, p.scale[2]];
      countLeg1Y++; touchedRoles.add("leg1:" + role); continue;
    }
    if (role === "zadni-svislice-nad-zarezem") {
      const oldHeight = p.scale[1] * 1000, topY = y + oldHeight / 2;
      const newHeight = topY - newYnew;
      p.position = [x, newYnew + newHeight / 2, z];
      p.scale = [p.scale[0], newHeight / 1000, p.scale[2]];
      countLeg1Y++; touchedRoles.add("leg1:" + role); continue;
    }
    if (role === "pricka-uzavreni-vyrezu") {
      p.position = [x, newYnew + T / 2, z];
      countLeg1Y++; touchedRoles.add("leg1:" + role); continue;
    }
    // ostatni leg1 kusy (predni-svislice, cap, spojnice-*, zaslepky
    // nezavisle na seamu, top-kotvene zaslepky, brackety mimo seam) -
    // beze zmeny (Z i Y se u nich nemeni)
    countUnchanged++; continue;
  }

  // 4) leg2 vyrezova noha - stejne jako leg1
  if (near(z, LEG_Z.leg2, 0.05) || near(z, LEG_Z.leg2 + 10, 0.5) /* logo-3 offset +10 */) {
    const oldYnew = OLD_YNEW.leg2, newYnew = oldYnew + DELTA_Y_VYREZ;
    if (role === "sloupek-pred-podbehem") {
      const oldHeight = p.scale[1] * 1000, floorY = y - oldHeight / 2;
      const newHeight = newYnew - floorY;
      p.position = [x, floorY + newHeight / 2, z];
      p.scale = [p.scale[0], newHeight / 1000, p.scale[2]];
      countLeg2Y++; touchedRoles.add("leg2:" + role); continue;
    }
    if (role === "zadni-svislice-nad-zarezem") {
      const oldHeight = p.scale[1] * 1000, topY = y + oldHeight / 2;
      const newHeight = topY - newYnew;
      p.position = [x, newYnew + newHeight / 2, z];
      p.scale = [p.scale[0], newHeight / 1000, p.scale[2]];
      countLeg2Y++; touchedRoles.add("leg2:" + role); continue;
    }
    if (role === "pricka-uzavreni-vyrezu") {
      p.position = [x, newYnew + T / 2, z];
      countLeg2Y++; touchedRoles.add("leg2:" + role); continue;
    }
    countUnchanged++; continue;
  }

  // 5) col1 (mezi leg1 a leg2, oba fixni v Z) a vse ostatni - beze zmeny
  countUnchanged++;
}

console.log("front-leg shift (+8mm Z):", countFrontShift);
console.log("col0 interpolace:", countCol0Interp);
console.log("leg1 seam shift (+10mm Y):", countLeg1Y);
console.log("leg2 seam shift (+10mm Y):", countLeg2Y);
console.log("beze zmeny:", countUnchanged);
console.log("celkem:", parts.length, "= soucet", countFrontShift + countCol0Interp + countLeg1Y + countLeg2Y + countUnchanged);
console.log("\nDotcene role:", [...touchedRoles].sort().join(", "));

fs.writeFileSync(__dirname + "/tmp_2026-09-12_k075_c_10_30_parts.json", JSON.stringify(parts));
console.log("\nUlozeno: tmp_2026-09-12_k075_c_10_30_parts.json (" + parts.length + " dilu)");
