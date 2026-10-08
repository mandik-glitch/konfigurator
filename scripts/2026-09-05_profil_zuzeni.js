// PROFIL ZUZENI KAROSERIE - kde presne je bocni stena v jednotlivych vyskach.
// bot8 2026-09-05.
//
// Robert: "Zacni se zabyvat tim novy postup uceni co se da postavit v horni
// casti regalu v aute prave v te zuzene casti" + "1 moznost je ukladani
// dlouhych predmetu takze to potrebujeme podle toho upravit".
//
//   node scripts/2026-09-05_profil_zuzeni.js <base>            # jeden vuz
//   node scripts/2026-09-05_profil_zuzeni.js <base> --json
//   node scripts/2026-09-05_profil_zuzeni.js --vzorek          # 6 typickych vozu
//
// PROC TENHLE NASTROJ EXISTUJE
// Dosavadni pipeline zna jen JEDNO cislo - "fyzicky strop" (Y, kde sirokou
// sondou pres celou hloubku D poprve nastane kolize; CI25 ~923mm, Vivaro
// 922/924, OP31 927). Regal se pod nim zastavi a nad nim se NESTAVI NIC.
// Jenze ten strop neni strop vozu - je to jen vyska, kde uz se nevejde box
// PRES CELOU HLOUBKU. Bok se ke strese zaklani postupne, takze nad tim
// zbyva realny, jen MELCI prostor. Pro dlouhe predmety (zebrik, trubky,
// listy, profily) ulozene PODELNE je prave tenhle melky, ale pres cele auto
// dlouhy pas idealni.
//
// Merime proto CELOU funkci "kde je stena v dane vysce", ne jeden bod:
//   X_stena(Y) = nejvnitrnejsi bod steny L v danem vyskovem pasmu
//   hloubka(Y) = X_stena(podlaha) - X_stena(Y)   ... o kolik se v te vysce
//                                                    prostor zuzil
//
// METODA: primo z vrcholu GLB steny L (ne kolizni sonda) - je to presnejsi
// a rychlejsi. Kolizni sonda vraci jen prvni Y, kde neco narazi; tady
// potrebujeme celou zavislost.
//
// POZOR na dve veci, obe uz drive stály chybu v tomhle projektu:
//  1) Y se meri RELATIVNE k podlaze daneho GLB (boxL.min.y), ne absolutne.
//     Nektera vozidla maji surovy bbox posunuty (VW31/32: 1641-2881mm misto
//     0-1200mm) - absolutni Y by u nich vyslo nesmyslne.
//  2) Strana steny L se lisi vuz od vozu (mirror). Po 180 flipu je L na
//     zaporne X. "Nejvnitrnejsi" je proto podle znamenka bud max, nebo min.
const fs = require("fs");
const path = require("path");
const THREE = require("three");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const MeshBVHLib = require("/opt/konfigurator/webapp/js/three-mesh-bvh.js");
THREE.BufferGeometry.prototype.computeBoundsTree = MeshBVHLib.computeBoundsTree;
THREE.BufferGeometry.prototype.disposeBoundsTree = MeshBVHLib.disposeBoundsTree;
THREE.Mesh.prototype.raycast = MeshBVHLib.acceleratedRaycast;

const CARB = "/opt/konfigurator/webapp/katalog/car_bodies/";
const Y_KROK = 25;       // vyskovy krok profilu [mm]
const Y_OD = 0;          // od podlahy
const Y_DO = 2200;       // dost vysoko i pro H2/H3 strechy

// Merime RAYCASTEM, ne vrcholy. Prvni pokus sel pres "nejvnitrnejsi vrchol
// steny v danem vyskovem pasmu" a vratil samé nuly: stena "_L" NENI jen bocnice,
// je to CELA leva pulka karoserie vcetne kusu podlahy a strechy, takze
// nejvnitrnejsi vrchol je v kazde vysce osa vozu (X=0). Vodorovny paprsek od
// osy smerem k boku najde skutecny POVRCH bocnice - to je to, o co jde.
function pripravBVH(mesh) {
  mesh.updateMatrixWorld(true);
  mesh.traverse(n => { if (n.isMesh && n.geometry && !n.geometry.boundsTree) n.geometry.computeBoundsTree(); });
  return mesh;
}

function profilRaycast(wallL, boxL, mirror, opts) {
  const podlahaY = boxL.min.y;
  const smer = new THREE.Vector3(mirror ? -1 : 1, 0, 0);  // od osy k bocnici
  const raycaster = new THREE.Raycaster();
  raycaster.firstHitOnly = true;
  raycaster.far = 3000;

  // Z vzorky pres uzitecnou delku korby (vynechavame krajni 10 % - tam je
  // prechod do prepazky/zadnich dveri, ne rovny bok)
  const zOd = opts.zOd != null ? opts.zOd : boxL.min.z;
  const zDo = opts.zDo != null ? opts.zDo : boxL.max.z;
  const zRozsah = zDo - zOd;
  const N_Z = 25;
  const zVzorky = [];
  for (let i = 0; i < N_Z; i++) zVzorky.push(zOd + zRozsah * (0.10 + 0.80 * i / (N_Z - 1)));

  const radky = [];
  for (let y = Y_OD; y <= Y_DO; y += Y_KROK) {
    const svet = podlahaY + y;
    if (svet > boxL.max.y) break;
    const vzdalenosti = [];
    for (const z of zVzorky) {
      raycaster.set(new THREE.Vector3(0, svet, z), smer);
      const hit = raycaster.intersectObject(wallL, true);
      if (hit.length) vzdalenosti.push(hit[0].distance);
    }
    if (!vzdalenosti.length) { radky.push({ y, sirka: null, sirkaBezna: null, vzorku: 0 }); continue; }
    // DVE cisla, protoze pro dlouhe predmety znamenaji neco jineho:
    //  - sirka      = NEJMENSI vzdalenost podel delky = nejtesnejsi misto.
    //                 Tohle limituje predmet, ktery ma projit CELOU delkou.
    //  - sirkaBezna = median = jak je na tom bok "obecne".
    // Rozdil mezi nimi = lokalni prekazka (vyztuha, sloupek, kolejnice
    // posuvnych dveri). U Caddy VW21 je nad Y=1000mm jeden bod, kde neco
    // zasahuje 265mm dovnitr, zatimco zbytek delky je volny - dlouha tyc by
    // o to zavadila, kratsi ulozena za tim mistem ne. Proto se hlasi i Z
    // pozice toho nejtesnejsiho mista, at je videt, KDE prekazka je.
    let iMin = 0;
    for (let i = 1; i < vzdalenosti.length; i++) if (vzdalenosti[i] < vzdalenosti[iMin]) iMin = i;
    const serazene = [...vzdalenosti].sort((a, b) => a - b);
    const median = serazene[Math.floor(serazene.length / 2)];
    radky.push({
      y,
      sirka: Math.round(vzdalenosti[iMin] * 10) / 10,
      sirkaBezna: Math.round(median * 10) / 10,
      zNejtesnejsi: Math.round(zVzorky[iMin]),
      vzorku: vzdalenosti.length,
    });
  }
  return radky;
}

function profil(base, opts = {}) {
  const pL = CARB + base + "_L.glb";
  if (!fs.existsSync(pL)) throw new Error(`neexistuje ${pL}`);
  const wallL = pripravBVH(parseGlbMesh(pL));
  const boxL = new THREE.Box3().setFromObject(wallL);
  const lMidX = (boxL.min.x + boxL.max.x) / 2;
  const mirror = lMidX < 0;

  const radky = profilRaycast(wallL, boxL, mirror, opts);
  const merene = radky.filter(r => r.sirka != null);
  if (!merene.length) throw new Error("raycast nic netrefil");

  // referencni polosirka = MAXIMUM v pasmu 300-700mm nad podlahou (tam je bok
  // svisly a nejsirsi; nizko muze zasahovat podbeh, vysoko uz zaklon)
  const zaklad = merene.filter(r => r.y >= 300 && r.y <= 700);
  if (!zaklad.length) throw new Error("zadna data v referencnim pasmu 300-700mm");
  const sirkaRef = Math.max(...zaklad.map(r => r.sirka));

  for (const r of radky) {
    r.zuzeni = r.sirka == null ? null : Math.round((sirkaRef - r.sirka) * 10) / 10;
    if (r.zuzeni != null && r.zuzeni < 0) r.zuzeni = 0;
    r.zuzeniBezne = r.sirkaBezna == null ? null : Math.round((sirkaRef - r.sirkaBezna) * 10) / 10;
    if (r.zuzeniBezne != null && r.zuzeniBezne < 0) r.zuzeniBezne = 0;
    // lokalni prekazka = o kolik je nejtesnejsi misto horsi nez bezny bok
    r.prekazka = (r.sirka == null || r.sirkaBezna == null)
      ? null : Math.round((r.sirkaBezna - r.sirka) * 10) / 10;
  }

  return {
    base, mirror,
    podlahaY: Math.round(boxL.min.y * 10) / 10,
    vyskaKorby: Math.round((boxL.max.y - boxL.min.y) * 10) / 10,
    sirkaRef: Math.round(sirkaRef * 10) / 10,
    radky,
  };
}

function vypis(p) {
  console.log(`\n=== ${p.base} ===`);
  console.log(`  vyska korby (GLB stena L): ${p.vyskaKorby} mm   mirror: ${p.mirror}`);
  console.log(`  referencni polosirka (pasmo 300-700mm): ${p.sirkaRef} mm`);
  console.log(`  ${"Y".padStart(7)}  ${"zuzeni".padStart(8)} ${"bezne".padStart(8)} ${"prekazka".padStart(9)}  profil (# = bezne zuzeni, ! = lokalni prekazka)`);
  for (const r of p.radky) {
    if (r.y < 400) continue;                  // dole je bok svisly, nezajimave
    if (r.sirka == null) { console.log(`  ${String(r.y).padStart(5)} mm  ${"---".padStart(8)}`); continue; }
    const bar = "#".repeat(Math.min(50, Math.round(r.zuzeniBezne / 5)))
              + (r.prekazka >= 20 ? "!".repeat(Math.min(20, Math.round(r.prekazka / 20))) : "");
    const pz = r.prekazka >= 20 ? `${String(r.prekazka).padStart(6)} @Z${r.zNejtesnejsi}` : "     -";
    console.log(`  ${String(r.y).padStart(5)} mm  ${String(r.zuzeni).padStart(6)} mm ${String(r.zuzeniBezne).padStart(6)} mm ${pz.padStart(9)}  ${bar}`);
  }
}

function main() {
  const args = process.argv.slice(2);
  const jsonOut = args.includes("--json");
  if (args.includes("--vzorek")) {
    // typicti zastupci: maly / stredni / velky / vysoka strecha
    const VZOREK = [
      "Citroën_Jumpy_CI25_2021-",
      "Fiat_Ducato_FI08_2014-",
      "Fiat_Scudo_FI20_2022-",
      "Mercedes_Vito_MB18_2014-",
      "Ford_Custom_FO31_2023-",
      "Volkswagen_Caddy_VW21_2021-",
    ];
    const vys = [];
    for (const b of VZOREK) {
      try { const p = profil(b); vys.push(p); if (!jsonOut) vypis(p); }
      catch (e) { console.log(`\n=== ${b} ===\n  PRESKOCENO: ${e.message}`); }
    }
    if (jsonOut) console.log(JSON.stringify(vys, null, 1));
    return;
  }
  const base = args.find(a => !a.startsWith("--"));
  if (!base) { console.error("Zadej base karoserie, napr. Citroën_Jumpy_CI25_2021-  (nebo --vzorek)"); process.exit(1); }
  const p = profil(base);
  if (jsonOut) console.log(JSON.stringify(p, null, 1)); else vypis(p);
}

if (require.main === module) main();
module.exports = { profil };
