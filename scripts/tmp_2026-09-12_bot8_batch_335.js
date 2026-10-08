// Prepocet kolizni bezpecnostni rezervy (2/20mm -> 10/30mm) sestavy
// product_assemblies.id=335 ("K-075-EB-30-C-0063-4-0 - dve pasma, police
// jen pricky"), podle procedury shape_geometry_methods.id=11
// "prepocet-kolizni-rezervy-existujici-sestavy" (verified_by robert).
//
// Vstupni fakta o rodine K-075 (Fiat Doblo L1H1) dodana zadanim (NEDELA
// se tu zadna nova detekce noh):
//   deltaZ_predni_noha  = +8mm  (10mm - 2mm prepazka)
//   deltaY_vyrezova_noha = +10mm (30mm - 20mm podbeh)
//   3 Z-pozice noh: leg0=-1358.5025482177734 (plna, OBE strany - predni
//     I zadni jsou plne, zadny vyrez), leg1=-898.5025482177734 (predni
//     plna + zadni vyrezova), leg2=-34.50254821777344 (stejne jako leg1).
//   old Y_new (svar sloupek/svislice pred zmenou): leg1=101.50017929077148,
//     leg2=53.500179290771484 (zmereno REALNOU GLB geometrii v predchozim
//     kroku, prevzato jako fakt).
//
// STRUKTURA 335 (overeno primo z data.parts, 124 dilu, viz REPORT na konci):
// dva sloupce/pasma - col0 (mezi leg0 a leg1, 4 patra p0-p3) a col1 (mezi
// leg1 a leg2, 2 patra p0-p1). col1 ma OBA konce na vyrezovych nohach,
// ale leg1 (vyssi Y_new) nezpusobuje viseni (nejnizsi patro col1 je
// vysoko nad seamem) - col0 ANO (viz KROK 4 nize).
//
// KLASIFIKACE JE ROLE+POZICE ZALOZENA, NE PREVZATA Z JINE SESTAVY - 335
// ma jiny pocet pater/jine role (podelnik-celni/zadni-horni/-spodni-0/-1,
// pricka-police/pricka-spodni) nez drivejsi predloha pro id=279
// (tmp_2026-09-12_bot8_predelat_k075_c_10_30.js), proto se tu NEPOUZIVA
// primo, jen jako inspirace metody (frac-interpolace podel Z/Y).

const fs = require("fs");
const path = require("path");

const SRC_PATH = "/tmp/claude-0/-opt-konfigurator/c0c788fb-0783-4d56-adb5-543ba6b0dda8/scratchpad/assembly335.json";
const SRC = JSON.parse(fs.readFileSync(SRC_PATH, "utf8"));
const parts = SRC.parts.map(p => JSON.parse(JSON.stringify(p))); // deep clone

const LEG_Z = { leg0: -1358.5025482177734, leg1: -898.5025482177734, leg2: -34.50254821777344 };
const DELTA_Z = 8;   // 10mm - 2mm
const DELTA_Y = 10;  // 30mm - 20mm
const OLD_YNEW = { leg1: 101.50017929077148, leg2: 53.500179290771484 };
const T = 30;
const EPS_Z_LEG = 0.06; // presne shodne Z (stejne cislo jako zdroj procedury)
const near = (a, b, eps) => Math.abs(a - b) < eps;

function interpZ(oldZ, fixedZ, oldMovingZ, newMovingZ) {
  const frac = (oldZ - fixedZ) / (oldMovingZ - fixedZ);
  return fixedZ + frac * (newMovingZ - fixedZ);
}

// ---------------------------------------------------------------------
// KROK A: najdi patra col0 (nosnik-col0-pN), seradit podle Y, over ze
// index N odpovida poradi (p0 nejnize).
// ---------------------------------------------------------------------
const col0FloorY = {};
for (const p of parts) {
  const m = /^nosnik-col0-p(\d+)$/.exec(p.role || "");
  if (m) {
    const idx = Number(m[1]);
    if (col0FloorY[idx] == null) col0FloorY[idx] = p.position[1];
    else if (Math.abs(col0FloorY[idx] - p.position[1]) > 0.01) {
      throw new Error(`nosnik-col0-p${idx}: nekonzistentni Y mezi instancemi`);
    }
  }
}
const floorIdxSorted = Object.keys(col0FloorY).map(Number).sort((a, b) => a - b);
const N = floorIdxSorted.length;
for (let i = 1; i < N; i++) {
  if (col0FloorY[floorIdxSorted[i]] <= col0FloorY[floorIdxSorted[i - 1]]) {
    throw new Error("nosnik-col0 patra nejsou serazena vzestupne podle Y - predpoklad kroku 5 neplati");
  }
}
console.log("col0 patra (index:Y):", floorIdxSorted.map(i => `p${i}:${col0FloorY[i].toFixed(3)}`).join(", "));

// ---------------------------------------------------------------------
// KROK 4 (predbezny vypocet, PRED aplikaci step3, protoze Y nejnizsiho
// patra col0 se stepem 3 nemeni - jen Z se hybe u col0 rungu):
// ---------------------------------------------------------------------
const lowestFloorIdx = floorIdxSorted[0];
const bottomEdgeLuzkoOld = col0FloorY[lowestFloorIdx] - 15; // profil 30mm, pulka=15
const newYnewLeg1 = OLD_YNEW.leg1 + DELTA_Y;
const missing = newYnewLeg1 - bottomEdgeLuzkoOld;
console.log(`KROK 4 (col0, opira se o leg1): spodni hrana luzka (p${lowestFloorIdx}) = ${bottomEdgeLuzkoOld.toFixed(6)}, novy Y_new(leg1) = ${newYnewLeg1.toFixed(6)} -> `
  + (missing > 0 ? `VISI VE VZDUCHU o ${missing.toFixed(6)}mm - dorovnani (krok 5) potreba.` : "nevisi, dorovnani neni potreba."));

// col1 kontrola (opira se o leg1 I leg2 - pouzij VYSSI Y_new, tj. leg1):
const col1FloorY = {};
for (const p of parts) {
  const m = /^nosnik-col1-p(\d+)$/.exec(p.role || "");
  if (m) { const idx = Number(m[1]); if (col1FloorY[idx] == null) col1FloorY[idx] = p.position[1]; }
}
const col1LowestIdx = Object.keys(col1FloorY).map(Number).sort((a, b) => a - b)[0];
const col1BottomEdgeOld = col1FloorY[col1LowestIdx] - 15;
console.log(`KROK 4 (col1, opira se o leg1 I leg2, vyssi Y_new=leg1): spodni hrana luzka (p${col1LowestIdx}) = ${col1BottomEdgeOld.toFixed(6)} vs ${newYnewLeg1.toFixed(6)} -> `
  + (col1BottomEdgeOld < newYnewLeg1 ? "VISELO BY - NEOCEKAVANO, over rucne!" : "nevisi, dorovnani neni potreba (jak ocekavano)."));

if (missing <= 0) throw new Error("Neocekavano: col0 podle vypoctu nevisi - over vstupni data pred pokracovanim.");

// shift(patro_i) = missing * (N-1-i)/(N-1), i=0 dole (floorIdxSorted[0])
const colShift = {};
floorIdxSorted.forEach((idx, i) => {
  colShift[idx] = missing * (N - 1 - i) / (N - 1);
});
console.log("KROK 5 dorovnani shift per patro:", floorIdxSorted.map(i => `p${i}=+${colShift[i].toFixed(6)}mm`).join(", "));

// ---------------------------------------------------------------------
// STAMP_HOST: rucne dohledano porovnanim pozice kazdeho
// logo-ochrana-logo-N/vypln-N s realnou geometrii hostitelskeho dilu
// (viz komentare u kazdeho indexu - shoda X/Y/Z s konkretnim dilem,
// tolerance do ~20mm = povrchovy offset nalepky od stredove osy profilu).
// ---------------------------------------------------------------------
const STAMP_HOST = {
  0: { type: "col0zy", floorIdx: 0 },   // na nosnik-col0-p0 (Y=116.5 presna shoda, X~front)
  1: { type: "unchanged" },              // na predni-svislice @ leg1 (X=-387.5, Y v rozsahu vysky)
  2: { type: "unchanged" },              // na predni-svislice @ leg2
  3: { type: "col0z" },                  // na podelnik-celni-spodni-0 (X=-387.5, Z v rozsahu, anchor=leg1)
  4: { type: "col0z_leg2anchor" },       // na podelnik-celni-horni (X=-387.5, Z stred spanu leg0-leg2)
  5: { type: "col0zy", floorIdx: 1 },   // na nosnik-col0-p1 zadni (X~-706.5, Y=384.5 presna shoda)
  6: { type: "seamY_leg2" },             // na zadni-svislice-nad-zarezem @ leg2 (X~-706.5, Y v rozsahu vysky)
  7: { type: "col1" },                   // na nosnik-col1-p1 zadni (Y=713.5 presna shoda)
  8: { type: "col1" },                   // na podelnik-zadni-spodni-1 (X~-636.5, Y=981.5 presna shoda)
  9: { type: "col1" },                   // na nosnik-col1-p0 zadni (X=-706.5 presna shoda)
  10: { type: "leg0" },                  // Z=-1374.2 (leg0 -15.7, povrch. offset), X=-387.5 presna shoda
};

// ---------------------------------------------------------------------
// hlavni pruchod - KROK 3 (delty) + priprava pro KROK 5
// ---------------------------------------------------------------------
const counts = {
  leg0_full_shift: 0, uhelnik0_shift: 0, stamp_leg0: 0,
  col0_floor_nosnik: 0, col0_floor_eurobox: 0,
  col0_floor_spojnice_leg0end: 0, col0_floor_spojnice_leg1end_Yonly: 0,
  col0_resize_podelnik_spodni: 0, col0_resize_podelnik_horni: 0,
  stamp_col0_interp: 0,
  vyrez_sloupek: 0, vyrez_zadni_svislice: 0, vyrez_pricka_uzavreni: 0,
  vyrez_uhelnik_seam: 0, stamp_seamY: 0,
  unchanged: 0,
};
const touched = new Set();

for (const p of parts) {
  const [x, y, z] = p.position;
  const role = p.role || "";

  // (none) = car_body_* -> nikdy se nehybe
  if (!role) { counts.unchanged++; continue; }

  // --- STAMPY (logo-ochrana-logo-N / logo-ochrana-vypln-N) ---
  const stampMatch = /^logo-ochrana-(?:logo|vypln)-(\d+)$/.exec(role);
  if (stampMatch) {
    const idx = Number(stampMatch[1]);
    const host = STAMP_HOST[idx];
    if (!host) throw new Error(`Neznamy stamp index ${idx} (role=${role}) - doplnit STAMP_HOST`);
    if (host.type === "leg0") {
      p.position = [x, y, z + DELTA_Z];
      counts.stamp_leg0++; touched.add(`stamp${idx}:leg0-shift`);
    } else if (host.type === "unchanged" || host.type === "col1") {
      counts.unchanged++; touched.add(`stamp${idx}:${host.type}`);
    } else if (host.type === "col0zy") {
      const newZ = interpZ(z, LEG_Z.leg1, LEG_Z.leg0, LEG_Z.leg0 + DELTA_Z);
      const newY = y + colShift[host.floorIdx];
      p.position = [x, newY, newZ];
      counts.stamp_col0_interp++; touched.add(`stamp${idx}:col0zy-p${host.floorIdx}`);
    } else if (host.type === "col0z") {
      const newZ = interpZ(z, LEG_Z.leg1, LEG_Z.leg0, LEG_Z.leg0 + DELTA_Z);
      p.position = [x, y, newZ];
      counts.stamp_col0_interp++; touched.add(`stamp${idx}:col0z-leg1anchor`);
    } else if (host.type === "col0z_leg2anchor") {
      const newZ = interpZ(z, LEG_Z.leg2, LEG_Z.leg0, LEG_Z.leg0 + DELTA_Z);
      p.position = [x, y, newZ];
      counts.stamp_col0_interp++; touched.add(`stamp${idx}:col0z-leg2anchor`);
    } else if (host.type === "seamY_leg2") {
      // host zadni-svislice-nad-zarezem @ leg2: top fixni, vyska se zkracuje o DELTA_Y
      const hostOldY = 487.5001792907715, hostOldHeight = 868; // leg2 instance (zmereno primo)
      const topY = hostOldY + hostOldHeight / 2;
      const newHeight = hostOldHeight - DELTA_Y;
      const distFromTop = topY - y;
      const newY = topY - distFromTop * (newHeight / hostOldHeight);
      p.position = [x, newY, z];
      counts.stamp_seamY++; touched.add(`stamp${idx}:seamY-leg2`);
    } else {
      throw new Error(`Neosetreny STAMP_HOST.type=${host.type}`);
    }
    continue;
  }

  // --- 1) cokoli presne na Z leg0 (plna noha, OBE strany + spojky mezi
  //        nimi na teto Z) -> cely posun deltaZ, zadny resize ---
  if (near(z, LEG_Z.leg0, EPS_Z_LEG)) {
    p.position = [x, y, z + DELTA_Z];
    counts.leg0_full_shift++; touched.add("leg0-Zmatch:" + role);
    continue;
  }

  // --- 2) uhelnik-noha0 - klasifikovano rolí (Z je posunuta podel
  //        profilu, nesedi presne na LEG_Z.leg0) - cely sloupec leg0 je
  //        tuhy, posouva se jako celek ---
  if (role === "uhelnik-noha0") {
    p.position = [x, y, z + DELTA_Z];
    counts.uhelnik0_shift++; touched.add("uhelnik-noha0");
    continue;
  }

  // --- 3) col0 rungy (nosnik-col0-pN / podelnik-celni-spodni-0 /
  //        podelnik-zadni-spodni-0) - span leg0(hybe se) <-> leg1(fixni)
  //        - stred += deltaZ/2, delka (scale[1]) -= deltaZ. Navic Y
  //        dorovnani (krok 5) jen u nosnik-col0-pN (patro). ---
  {
    const mFloor = /^nosnik-col0-p(\d+)$/.exec(role);
    if (mFloor) {
      const idx = Number(mFloor[1]);
      const newZ = z + DELTA_Z / 2;
      const newLenMm = p.scale[1] * 1000 - DELTA_Z;
      const newY = y + colShift[idx];
      p.position = [x, newY, newZ];
      p.scale = [p.scale[0], newLenMm / 1000, p.scale[2]];
      counts.col0_floor_nosnik++; touched.add(`nosnik-col0-p${idx}`);
      continue;
    }
  }
  if (role === "podelnik-celni-spodni-0" || role === "podelnik-zadni-spodni-0") {
    const newZ = z + DELTA_Z / 2;
    const newLenMm = p.scale[1] * 1000 - DELTA_Z;
    p.position = [x, y, newZ]; // neni "patro" (nosnik/spojnice/eurobox) -> zadne Y dorovnani
    p.scale = [p.scale[0], newLenMm / 1000, p.scale[2]];
    counts.col0_resize_podelnik_spodni++; touched.add(role);
    continue;
  }

  // --- 4) podelnik-celni-horni / podelnik-zadni-horni - span leg0(hybe
  //        se) <-> leg2(fixni), presne centrovano (frac=0.5, protoze
  //        stred spanu leg0..leg2 vychazi presne na jeho Z) ---
  if (role === "podelnik-celni-horni" || role === "podelnik-zadni-horni") {
    const newZ = z + DELTA_Z / 2;
    const newLenMm = p.scale[1] * 1000 - DELTA_Z;
    p.position = [x, y, newZ];
    p.scale = [p.scale[0], newLenMm / 1000, p.scale[2]];
    counts.col0_resize_podelnik_horni++; touched.add(role);
    continue;
  }

  // --- 5) spojnice-col0-pN - KRATKA tuha spojka pri JEDNE konkretni
  //        noze (T mm od ni) - anchor=leg0 dostane CELY deltaZ, anchor=
  //        leg1 zustava v Z beze zmeny. OBĚ instance (bez ohledu na Z-
  //        anchor) dostanou Y dorovnani sveho patra (krok 5). ---
  {
    const mSp = /^spojnice-col0-p(\d+)$/.exec(role);
    if (mSp) {
      const idx = Number(mSp[1]);
      const distToLeg0 = Math.abs(z - LEG_Z.leg0), distToLeg1 = Math.abs(z - LEG_Z.leg1);
      const newZ = distToLeg0 < distToLeg1 ? z + DELTA_Z : z;
      const newY = y + colShift[idx];
      p.position = [x, newY, newZ];
      if (distToLeg0 < distToLeg1) counts.col0_floor_spojnice_leg0end++;
      else counts.col0_floor_spojnice_leg1end_Yonly++;
      touched.add(`spojnice-col0-p${idx}:${distToLeg0 < distToLeg1 ? "leg0end" : "leg1end"}`);
      continue;
    }
  }

  // --- 6) eurobox-col0-pN - stred posunut o deltaZ/2 (procedura
  //        doslovne), + Y dorovnani sveho patra (krok 5, "vsech dilu
  //        daneho patra") ---
  {
    const mEb = /^eurobox-col0-p(\d+)$/.exec(role);
    if (mEb) {
      const idx = Number(mEb[1]);
      const newZ = z + DELTA_Z / 2;
      const newY = y + colShift[idx];
      p.position = [x, newY, newZ];
      counts.col0_floor_eurobox++; touched.add(`eurobox-col0-p${idx}`);
      continue;
    }
  }
  if (role.startsWith("eurobox-col1")) { counts.unchanged++; touched.add(role + "(col1-unaffected)"); continue; }

  // --- 7) vyrezova noha na leg1/leg2 (Z NEMENI SE, jen Y) - 3
  //        jmenovane role z procedury ---
  if (near(z, LEG_Z.leg1, EPS_Z_LEG) || near(z, LEG_Z.leg2, EPS_Z_LEG)) {
    const isLeg1 = near(z, LEG_Z.leg1, EPS_Z_LEG);
    const oldYnew = isLeg1 ? OLD_YNEW.leg1 : OLD_YNEW.leg2;
    const newYnew = oldYnew + DELTA_Y;

    if (role === "sloupek-pred-podbehem") {
      const oldHeight = p.scale[1] * 1000, floorY = y - oldHeight / 2;
      const newHeight = newYnew - floorY;
      p.position = [x, floorY + newHeight / 2, z];
      p.scale = [p.scale[0], newHeight / 1000, p.scale[2]];
      counts.vyrez_sloupek++; touched.add((isLeg1 ? "leg1" : "leg2") + ":" + role);
      continue;
    }
    if (role === "zadni-svislice-nad-zarezem") {
      const oldHeight = p.scale[1] * 1000, topY = y + oldHeight / 2;
      const newHeight = topY - newYnew;
      p.position = [x, newYnew + newHeight / 2, z];
      p.scale = [p.scale[0], newHeight / 1000, p.scale[2]];
      counts.vyrez_zadni_svislice++; touched.add((isLeg1 ? "leg1" : "leg2") + ":" + role);
      continue;
    }
    if (role === "pricka-uzavreni-vyrezu") {
      p.position = [x, newYnew + T / 2, z];
      counts.vyrez_pricka_uzavreni++; touched.add((isLeg1 ? "leg1" : "leg2") + ":" + role);
      continue;
    }
    if (role === "uhelnik-noha1" || role === "uhelnik-noha2") {
      if (near(y, oldYnew, 3) || near(y, oldYnew + 30, 3)) {
        p.position = [x, y + DELTA_Y, z];
        counts.vyrez_uhelnik_seam++; touched.add((isLeg1 ? "leg1" : "leg2") + ":" + role + "(seam)");
      } else {
        counts.unchanged++; touched.add((isLeg1 ? "leg1" : "leg2") + ":" + role + "(unaffected)");
      }
      continue;
    }
    // ostatni dily na Z leg1/leg2 (predni-svislice, cap, spojnice-*,
    // zaslepky mimo seam, podelnik-*-spodni-1, nosnik-col1-p*,
    // pricka-police/spodni-1/2) - beze zmeny (Z i Y)
    counts.unchanged++; touched.add((isLeg1 ? "leg1" : "leg2") + ":" + role + "(unrelated)");
    continue;
  }

  // --- 8) uhelnik-noha1/uhelnik-noha2 - role klasifikace (jejich Z
  //        neni presne na LEG_Z, jsou posunute podel profilu) ---
  if (role === "uhelnik-noha1" || role === "uhelnik-noha2") {
    const oldYnew = role === "uhelnik-noha1" ? OLD_YNEW.leg1 : OLD_YNEW.leg2;
    if (near(y, oldYnew, 3) || near(y, oldYnew + 30, 3)) {
      p.position = [x, y + DELTA_Y, z];
      counts.vyrez_uhelnik_seam++; touched.add(role + "(seam,offZ)");
    } else {
      counts.unchanged++; touched.add(role + "(unaffected,offZ)");
    }
    continue;
  }

  // --- 9) col1 (mezi leg1 a leg2, oba fixni) a vse ostatni -> beze zmeny ---
  counts.unchanged++; touched.add("fallthrough-unchanged:" + role);
}

console.log("\n=== KROK 3-5 SOUHRN ===");
console.log(counts);
const total = Object.values(counts).reduce((a, b) => a + b, 0);
console.log("soucet kategorii:", total, "= pocet dilu:", parts.length, total === parts.length ? "OK" : "!!! NESEDI !!!");
if (total !== parts.length) throw new Error("Soucet zmenenych/nezmenenych kategorii nesedi s poctem dilu - zastavuji, neco je nezachyceno.");

console.log("\nDotcene role/kategorie (" + touched.size + "):");
console.log([...touched].sort().join("\n"));

const OUT_PATH = path.join(__dirname, "tmp_2026-09-12_bot8_batch_335_parts.json");
fs.writeFileSync(OUT_PATH, JSON.stringify(parts));
console.log("\nUlozeno:", OUT_PATH, "(" + parts.length + " dilu)");

// report pro pozdejsi pouziti (kod_sestavy/insert skript + verifikace)
fs.writeFileSync(path.join(__dirname, "tmp_2026-09-12_bot8_batch_335_report.json"), JSON.stringify({
  assembly_id: 335, deltaZ: DELTA_Z, deltaY: DELTA_Y, missing_mm: missing, colShift,
  counts, touchedRoles: [...touched].sort(),
}, null, 1));
