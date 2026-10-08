// Prepocet kolizni rezervy sestavy product_assemblies.id=332 (K-075
// "K-075-EB-30-C-0063-1-0 - jedno pasmo, jen ram") na 10/30mm, podle
// shape_geometry_methods.id=11 "prepocet-kolizni-rezervy-existujici-sestavy"
// (verified_by robert) - viz zadani teto session (AGENTS_LOG.md hleda
// "id=332" + "prepocet-kolizni-rezervy" pro plny kontext).
//
// VSTUP: rodina K-075 (Fiat_Doblo_FI14_2010-2022, car_model_id=7) ma 3
// Z-pozice noh: leg0=-1358.503 (POUZE plna strana, cely sloupec se hybe v
// Z), leg1=-898.503 a leg2=-34.503 (OBE zaroven: plna predni-svislice
// [nehybe se] + vyrezova trojice nad podbehem [Y roste o 10mm]).
//
// deltaZ_predni_noha = +8mm (10-2), deltaY_vyrezova_noha = +10mm (30-20) -
// presne aritmeticke konstanty, NE nova kolizni detekce (viz vstupni data
// zadani, potvrzeno diffem 279 vs 340 do posledniho desetinneho mista).
//
// STRUKTURA 332 (nactena primo z DB, 117 dilu, 3 car_body_* + 114
// geometrickych): oproti referencnimu skriptu pro 279 (verze C, jina
// varianta stejne karoserie) obsahuje NAVIC role "podelnik-celni/zadni-
// spodni-{0,1}" (horni ztuzujici pasnice pres cely sloupec, Y=981.5,
// stejne chovani jako nosnik-col0/col1 ale BEZ ucasti na "patro"
// dorovnani) a "pricka-spodni-{0,1,2}" (kratka prycna vzpera NA kazde
// noze, Y~970-981, nezavisla na seamu). Klasifikace kazde role
// zdokumentovana inline u prislusne vetve.
//
// LOGO-OCHRANA (9 paru logo+vypln, indexy 0-8): 332 NEMA stejne fyzicke
// rozlozeni jako 279 (jina varianta, jine LOGO_IDX_GROUP by bylo spatne
// prevzit 1:1) - proto RUCNE premereno z vlastnich dat teto sestavy
// (X/Y/Z kazdeho paru proti nejblizsimu strukturalnimu dilu, viz komentare
// u LOGO_CLASSIFICATION nize). Kazdy zaznam ma poznamku, na cem sedi.

const fs = require("fs");
const THREE = require("three");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
void parseGlbMesh; // pouzito az v overovacim kroku (samostatny soubor), tady jen pro pripadnou sdilenou logiku

const SCRATCH = "/tmp/claude-0/-opt-konfigurator/c0c788fb-0783-4d56-adb5-543ba6b0dda8/scratchpad";
const SRC = JSON.parse(fs.readFileSync(SCRATCH + "/assembly332_full.json", "utf8"));
const parts = SRC.parts.map(p => JSON.parse(JSON.stringify(p))); // deep clone

const LEG_Z = { leg0: -1358.5025482177734, leg1: -898.5025482177734, leg2: -34.50254821777344 };
const DELTA_Z_FRONT = 8;   // 10mm - 2mm (prepazka)
const DELTA_Y_VYREZ = 10;  // 30mm - 20mm (podbeh)
const T = 30;              // tloustka profilu (profil_mm=30 u teto sestavy)
const EPS = 0.05;
const near = (a, b, eps) => Math.abs(a - b) < (eps == null ? EPS : eps);

// ---- Zjisti oldYnew (svar sloupek/svislice) ZIVE z dat teto sestavy, ne
//      z hardkodovane konstanty - robustnejsi (samostatne overitelne). ----
function findOldYnew(legZ) {
  const sloupek = parts.find(p => p.role === "sloupek-pred-podbehem" && near(p.position[2], legZ, 0.05));
  const svislice = parts.find(p => p.role === "zadni-svislice-nad-zarezem" && near(p.position[2], legZ, 0.05));
  const ySloupekTop = sloupek.position[1] + sloupek.scale[1] * 1000 / 2;
  const ySvisliceBottom = svislice.position[1] - svislice.scale[1] * 1000 / 2;
  if (Math.abs(ySloupekTop - ySvisliceBottom) > 0.01) {
    throw new Error(`Svar na Z=${legZ} neni presny: sloupek top=${ySloupekTop}, svislice bottom=${ySvisliceBottom}`);
  }
  return ySloupekTop;
}
const OLD_YNEW = { leg1: findOldYnew(LEG_Z.leg1), leg2: findOldYnew(LEG_Z.leg2) };
const NEW_YNEW = { leg1: OLD_YNEW.leg1 + DELTA_Y_VYREZ, leg2: OLD_YNEW.leg2 + DELTA_Y_VYREZ };
console.log("OLD_YNEW zive zmereno:", OLD_YNEW, " -> NEW_YNEW:", NEW_YNEW);

// ---- Dorovnani (krok 4-5): col0 se opira o leg1 (jedina vyrezova noha na
//      jeho koncich - leg0 je plna, nema Y_new vubec). Spocitej chybejici
//      mm na nejnizsim patre col0 (nosnik-col0-p0) a rozloz do N=4 pater. ----
const col0Floors = ["p0", "p1", "p2", "p3"];
const nosnikCol0P0 = parts.find(p => p.role === "nosnik-col0-p0");
const bottomEdgeP0 = nosnikCol0P0.position[1] - T / 2;
const missingMm = NEW_YNEW.leg1 - bottomEdgeP0;
console.log(`Krok 4: col0 nejnizsi patro (nosnik-col0-p0) bottom edge=${bottomEdgeP0}, limitujici Y_new(leg1)=${NEW_YNEW.leg1} -> chybejici=${missingMm.toFixed(4)}mm`);
if (missingMm <= 0) {
  console.log("-> zadne dorovnani neni potreba (luzko nevisi ve vzduchu).");
}
const N = col0Floors.length;
function dorovnaniShift(floorIdx) {
  if (missingMm <= 0) return 0;
  return missingMm * (N - 1 - floorIdx) / (N - 1);
}
const COL0_SHIFT = { 0: dorovnaniShift(0), 1: dorovnaniShift(1), 2: dorovnaniShift(2), 3: dorovnaniShift(3) };
console.log("Krok 5: dorovnani shift per patro col0:", COL0_SHIFT);

// col1: over, jestli taky potrebuje dorovnani (opira se o leg1 A leg2 -
// pouzij VYSSI Y_new = leg1). Pokud bottom edge nejnizsiho patra col1 uz je
// nad limitem, dorovnani se NEAPLIKUJE (potvrzeno vypoctem nize).
const nosnikCol1P0 = parts.find(p => p.role === "nosnik-col1-p0");
const col1BottomEdge = nosnikCol1P0.position[1] - T / 2;
const col1Limit = Math.max(NEW_YNEW.leg1, NEW_YNEW.leg2);
console.log(`Kontrola col1: nejnizsi patro bottom edge=${col1BottomEdge}, limit=${col1Limit} -> ${col1BottomEdge >= col1Limit ? "OK, bez dorovnani" : "PROBLEM - potreba dorovnani!"}`);
if (col1BottomEdge < col1Limit) throw new Error("col1 potrebuje dorovnani - skript to nepodporuje, nutna revize!");

// ---- Rucne premerena klasifikace 9 logo/vypln paru (index -> popis +
//      transformace). Kazdy zaznam zduvodnen porovnanim X/Y/Z proti
//      nejblizsimu strukturalnimu dilu (viz hlavicka souboru). ----
const LOGO_CLASS = {
  0: { note: "col1-p0 (Y=445.5=nosnik-col1-p0), predni strana", z: "none", y: "none" },
  1: { note: "leg1 Z exakt, X~-387.5 = mount na predni-svislice (plna, nehybe se)", z: "none", y: "none" },
  2: { note: "col0 zone (Z~-1160), Y=770.5=nosnik-col0-p3 (predni strana)", z: "col0-frac", y: "col0-floor", floor: 3 },
  3: { note: "col0 zone (Z~-1104), Y~991-997~podelnik-celni-spodni-0 (Y=981.5, horni pasnice, NENI patro)", z: "col0-frac", y: "none" },
  4: { note: "col1-p0 (Y=445.5=nosnik-col1-p0), zadni strana", z: "none", y: "none" },
  5: { note: "leg1 Z exakt, X~-706.5+16 = mount na zadni-svislice-nad-zarezem (vyrezova, hybe se s nohou)", z: "none", y: "vyrez-leg1" },
  6: { note: "col0 zone (Z~-1103), Y=770.5=nosnik-col0-p3 (zadni strana, X~-706.5+16)", z: "col0-frac", y: "col0-floor", floor: 3 },
  7: { note: "col0 zone (Z~-1075), Y~101-106~nosnik-col0-p0 (Y=116.5, nejnizsi patro)", z: "col0-frac", y: "col0-floor", floor: 0 },
  8: { note: "leg0 zone (Z~-1368 az -1374), X=-706.5 = mount na zadni-svislice-dolni (plna, cely sloupec se hybe)", z: "leg0-full", y: "none" },
};

let counts = { leg0Full: 0, uhelnikNoha0: 0, uhelnikNoha1Seam: 0, uhelnikNoha1Fixed: 0, uhelnikNoha2Seam: 0, uhelnikNoha2Fixed: 0,
  spojniceCol0: 0, nosnikCol0: 0, podelnik0: 0, euroboxCol0: 0, col1Unchanged: 0, leg1Vyrez: 0, leg2Vyrez: 0,
  leg1Other: 0, leg2Other: 0, logo: 0, carBody: 0, unclassified: 0 };
const touched = [];

for (const p of parts) {
  const role = p.role;
  const partId = p.part_id || "";
  if (partId.startsWith("car_body_")) { counts.carBody++; continue; }
  const [x, y, z] = p.position;

  // ---- LOGO/VYPLN: podle rucne klasifikace indexu ----
  const mLogo = /^logo-ochrana-(?:vypln|logo)-(\d+)$/.exec(role);
  if (mLogo) {
    const idx = Number(mLogo[1]);
    const cls = LOGO_CLASS[idx];
    if (!cls) throw new Error("Neklasifikovany logo index " + idx);
    let nz = z, ny = y;
    if (cls.z === "leg0-full") nz = z + DELTA_Z_FRONT;
    else if (cls.z === "col0-frac") {
      const frac = (z - LEG_Z.leg1) / (LEG_Z.leg0 - LEG_Z.leg1);
      nz = z + frac * DELTA_Z_FRONT;
    }
    if (cls.y === "vyrez-leg1") ny = y + DELTA_Y_VYREZ;
    else if (cls.y === "col0-floor") ny = y + COL0_SHIFT[cls.floor];
    p.position = [x, ny, nz];
    counts.logo++;
    touched.push({ role, idx, note: cls.note, dz: (nz - z).toFixed(3), dy: (ny - y).toFixed(3) });
    continue;
  }

  // ---- uhelnik-noha0: cely s leg0, plny deltaZ (role-based, Z je offset o par mm od leg0) ----
  if (role === "uhelnik-noha0") {
    p.position = [x, y, z + DELTA_Z_FRONT];
    counts.uhelnikNoha0++;
    continue;
  }

  // ---- uhelnik-noha1/noha2: jen ty na seamu (Y blizko OLD_YNEW nebo OLD_YNEW+T) dostanou deltaY ----
  if (role === "uhelnik-noha1" || role === "uhelnik-noha2") {
    const legKey = role === "uhelnik-noha1" ? "leg1" : "leg2";
    const oldYnew = OLD_YNEW[legKey];
    if (near(y, oldYnew, 3) || near(y, oldYnew + T, 3)) {
      p.position = [x, y + DELTA_Y_VYREZ, z];
      if (legKey === "leg1") counts.uhelnikNoha1Seam++; else counts.uhelnikNoha2Seam++;
    } else {
      if (legKey === "leg1") counts.uhelnikNoha1Fixed++; else counts.uhelnikNoha2Fixed++;
    }
    continue;
  }

  // ---- spojnice-col0-pN: Z podle ktereho konce je kotvena (leg0+T rigidne
  //      s leg0 / leg1-T rigidne s leg1), Y VZDY podle dorovnani jejiho patra
  //      (je soucasti roviny dane patro, musi zustat vodorovna). ----
  const mSpCol0 = /^spojnice-col0-p(\d)$/.exec(role);
  if (mSpCol0) {
    const floor = Number(mSpCol0[1]);
    let nz = z;
    if (near(z, LEG_Z.leg0 + T, 1)) nz = z + DELTA_Z_FRONT;      // rigidni s leg0
    else if (near(z, LEG_Z.leg1 - T, 1)) nz = z;                  // rigidni s leg1, fixni
    else throw new Error("spojnice-col0 na neocekavanem Z: " + z);
    const ny = y + COL0_SHIFT[floor];
    p.position = [x, ny, nz];
    counts.spojniceCol0++;
    continue;
  }

  // ---- nosnik-col0-pN: rigidni rozpon leg0<->leg1, stred+deltaZ/2, delka-deltaZ, Y+dorovnani patra ----
  const mNoCol0 = /^nosnik-col0-p(\d)$/.exec(role);
  if (mNoCol0) {
    const floor = Number(mNoCol0[1]);
    const newLenMm = p.scale[1] * 1000 - DELTA_Z_FRONT;
    p.position = [x, y + COL0_SHIFT[floor], z + DELTA_Z_FRONT / 2];
    p.scale = [p.scale[0], newLenMm / 1000, p.scale[2]];
    counts.nosnikCol0++;
    continue;
  }

  // ---- podelnik-celni/zadni-spodni-0: stejny rigidni rozpon jako nosnik-col0,
  //      ALE neni to cislovane patro -> ZADNE dorovnani (jen Z-treatment). ----
  if (role === "podelnik-celni-spodni-0" || role === "podelnik-zadni-spodni-0") {
    const newLenMm = p.scale[1] * 1000 - DELTA_Z_FRONT;
    p.position = [x, y, z + DELTA_Z_FRONT / 2];
    p.scale = [p.scale[0], newLenMm / 1000, p.scale[2]];
    counts.podelnik0++;
    continue;
  }

  // ---- eurobox-col0-pN: stred+deltaZ/2 (flat, dle procedury), Y+dorovnani patra ----
  const mEbCol0 = /^eurobox-col0-p(\d)$/.exec(role);
  if (mEbCol0) {
    const floor = Number(mEbCol0[1]);
    p.position = [x, y + COL0_SHIFT[floor], z + DELTA_Z_FRONT / 2];
    counts.euroboxCol0++;
    continue;
  }

  // ---- col1 vetev (nosnik/spojnice/eurobox/podelnik-*-spodni-1): oba
  //      konce (leg1,leg2) fixni v Z, dorovnani NENI potreba (overeno vyse)
  //      -> kompletne beze zmeny. ----
  if (/^(nosnik|spojnice|eurobox)-col1-p\d$/.test(role) || role === "podelnik-celni-spodni-1" || role === "podelnik-zadni-spodni-1") {
    counts.col1Unchanged++;
    continue;
  }

  // ---- leg0 Z-exakt: cely sloupec (plna strana + zadni plna strana +
  //      brzdy/zaslepky/cap na tomhle Z) jede spolu, plny deltaZ. ----
  if (near(z, LEG_Z.leg0, EPS)) {
    p.position = [x, y, z + DELTA_Z_FRONT];
    counts.leg0Full++;
    continue;
  }

  // ---- leg1 Z-exakt: 3 vyrezove role dostanou presny prepocet vysky
  //      (vzorec id=6), pricka-uzavreni-vyrezu se posune na novy svar,
  //      vse ostatni na tomhle Z (predni-svislice, cap, zaslepky,
  //      spojnice-horni-uzavreni, spojnice-dolni, pricka-spodni-1) beze zmeny. ----
  if (near(z, LEG_Z.leg1, EPS)) {
    const newYnew = NEW_YNEW.leg1;
    if (role === "sloupek-pred-podbehem") {
      const oldH = p.scale[1] * 1000, floorY = y - oldH / 2, newH = newYnew - floorY;
      p.position = [x, floorY + newH / 2, z]; p.scale = [p.scale[0], newH / 1000, p.scale[2]];
      counts.leg1Vyrez++; continue;
    }
    if (role === "zadni-svislice-nad-zarezem") {
      const oldH = p.scale[1] * 1000, topY = y + oldH / 2, newH = topY - newYnew;
      p.position = [x, newYnew + newH / 2, z]; p.scale = [p.scale[0], newH / 1000, p.scale[2]];
      counts.leg1Vyrez++; continue;
    }
    if (role === "pricka-uzavreni-vyrezu") {
      p.position = [x, newYnew + T / 2, z];
      counts.leg1Vyrez++; continue;
    }
    counts.leg1Other++; continue;
  }

  // ---- leg2 Z-exakt: totez jako leg1 ----
  if (near(z, LEG_Z.leg2, EPS)) {
    const newYnew = NEW_YNEW.leg2;
    if (role === "sloupek-pred-podbehem") {
      const oldH = p.scale[1] * 1000, floorY = y - oldH / 2, newH = newYnew - floorY;
      p.position = [x, floorY + newH / 2, z]; p.scale = [p.scale[0], newH / 1000, p.scale[2]];
      counts.leg2Vyrez++; continue;
    }
    if (role === "zadni-svislice-nad-zarezem") {
      const oldH = p.scale[1] * 1000, topY = y + oldH / 2, newH = topY - newYnew;
      p.position = [x, newYnew + newH / 2, z]; p.scale = [p.scale[0], newH / 1000, p.scale[2]];
      counts.leg2Vyrez++; continue;
    }
    if (role === "pricka-uzavreni-vyrezu") {
      p.position = [x, newYnew + T / 2, z];
      counts.leg2Vyrez++; continue;
    }
    counts.leg2Other++; continue;
  }

  console.warn("!!! NEKLASIFIKOVANO:", role, partId, [x, y, z]);
  counts.unclassified++;
}

console.log("\n=== SOUHRN ===");
console.log(JSON.stringify(counts, null, 1));
const total = Object.values(counts).reduce((a, b) => a + b, 0);
console.log(`celkem klasifikovano: ${total} / ${parts.length}`);
if (total !== parts.length) throw new Error("Soucet neodpovida poctu dilu!");
if (counts.unclassified > 0) throw new Error("Existuji neklasifikovane dily - STOP.");

console.log("\nDotcene logo/vypln piny:");
for (const t of touched) console.log(" ", JSON.stringify(t));

fs.writeFileSync(SCRATCH + "/332_10_30_parts.json", JSON.stringify(parts));
fs.writeFileSync(SCRATCH + "/332_10_30_meta.json", JSON.stringify({
  OLD_YNEW, NEW_YNEW, missingMm, COL0_SHIFT, counts,
}, null, 1));
console.log("\nUlozeno:", SCRATCH + "/332_10_30_parts.json (" + parts.length + " dilu),", SCRATCH + "/332_10_30_meta.json");
