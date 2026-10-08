// Obecny diagnosticky nastroj: "je tahle karoserie (B/L/R_D trojice)
// pouzitelna jako ODRAZOVA geometrie (cycles_visibility.camera=false,
// odrazy zapnute), a co konkretne v ni chybi?"
//
// Vznik: bot3 2026-09-11, zadani "musime zapracovat na novych verzich
// karoserii, aby se melo svetlo od cehio odrazet a regaly budou hezci" -
// nez se cokoli stavelo, bylo potreba zmerit skutecnou geometrii (karoserie
// se v tomhle projektu stavi CISTE pro kolizni testy noh regalu, ne pro
// render - viz PRODUKTOVE_RENDERY.md/VLASTNOSTI_PROFILU.md, cast
// KAROSERIE_UMISTENI.md), ne odhadovat z pohledu.
//
// Zjisteno nejdriv na BYD_ETP3 + Opel_Vivaro_OP31_2020- (2 ruzne
// platformy), pak potvrzeno `--all` na CELEM katalogu (303/304 zmereno
// bez chyby): normaly jsou pritomne a validni (jednotkova delka, zadne
// NaN), hustota site je na hruby/matny odraz dostatecna (~600-900 tri/m2).
// ALE trojice B/L/R_D NEDAVA uzavreny interier ve SMERU NAHORU: strecha
// (plocha nad nakladovym prostorem) v datech vubec neni - **0/303
// karoserii v celem katalogu** ma "strop" (top-down test, viz
// roofCoverage() nize) pokryty na >=50% delky. Je to systemova
// vlastnost celeho katalogu (viz KAROSERIE_UMISTENI.md), ne vlastnost
// jednoho vozidla - odrazovy plech/rovina misto skutecne strechy je
// proto spravne reseni PRO VSECHNY karoserie, ne jen pro nekolik
// vyjimek.
//
// OPRAVA (bot3/Robert 2026-09-11, po prvnim kole): predni prepazka
// (kabina) NENI chybejici - je to soubor `_B.glb` samotny, celoplosny
// panel pres sirku vozu, vysoky stejne jako bocnice. Generator regalu
// (tmp_2026-08-31_batch_engine.js `dirZtoBulkhead`) se o ni realne
// opira (`stepUntilCollision1D(..., "prepazkaB")`) - to je silnejsi
// dukaz existence nez jakakoli geometricka sonda. Puvodni verze tohohle
// nastroje omylem predpokladala, ze prepazka je VZDY na `zMax` konci
// (max Z) - spatne, u BYD_ETP3 je na `zMin` konci (Z≈-1953..-1519),
// presne tam, kde ji predchozi test jednou zachytil (miss v jinych
// bodech) a bylo to mylne vylozeno jako "jen lem dvernich ramu".
//
// POZOR (bot3 2026-09-11, druhe kolo overeni): NEPLATI domenka, ze
// zdrojove modely nemaji jednotnou orientaci - zmereno na 12 vozidlech
// napric znackami (BYD, Berlingo, Ranger, Crafter, Ducato, Maxus, Ford
// Custom, Hilux, Partner, Kangoo, Movano), prepazka sedi na zapornem
// konci Z **u vsech dvanacti**, zadna vyjimka. `dirZtoBulkhead` v
// generatoru je opatrny kod, ne dukaz o promenlivych datech - z
// existence te vetve se nesmi odvozovat fakt o katalogu. `bulkheadZMM`/
// `bulkheadSide` nize pouzivaji STEJNOU detekcni logiku jako generator
// (konzistentni, nic nestoji), ale NEODVOZUJ z ni zavery o orientaci -
// je to jen opatrny kod, ne dukaz o datech.
//
// Vyska interieru NENI nikde v DB ulozena jako samostatne cislo
// (zadny sloupec car_bodies/car_models, zadna tabulka s "cargo height").
// Nejlepsi dostupna, geometricky podlozena nahrada: NEJVYSSI bod (max Y),
// ktereho dosahne _L nebo _R_D mesh dane karoserie - konzistentni napric
// vsemi 3 dily stejneho vozidla (neni to nahoda jednoho meshe), je to
// primo ve stejne souradnicove soustave jako zbytek sceny (Y=0=podlaha,
// zadny prevod jednotek/vyhledavani navic). POZOR: je to vyska
// NEJVYSSIHO MODELOVANEHO PRVKU (nejspis horni hrana dveni ramu u zadnich
// dveri/kabiny), ne primo zmerena plocha stropu - realny strop se muze
// mirne lisit (typicky vyssi, nikdy ne nizsi). car_models.name obsahuje
// i CELKOVOU VNEJSI vysku vozidla ("... 1875mm (H)"), ale prevod na
// vnitrni vysku nakladoveho prostoru by vyzadoval znat vysku podlahy nad
// zemi + tloustku strechy - zadny z techto dvou udaju v DB neni, takze
// vnejsi H by vnesl VIC neoverenych predpokladu nez primo zmereny bbox.
//
// Pouziti:
//   node scripts/2026-09-11_karoserie_odrazy_audit.js car_bodies/BYD_ETP3
//   node scripts/2026-09-11_karoserie_odrazy_audit.js --all [--csv]   (projede cely katalog, strucny souhrn)
//   node scripts/2026-09-11_karoserie_odrazy_audit.js --json car_bodies/BYD_ETP3   (strojove citelny JSON, 1 radek)
//
// Prejmenovano z tmp_2026-09-11_bot8_... (bot3 2026-09-11: "tmp_ je past"
// - tmp_2026-08-31_batch_pipeline.js je navzdory nazvu ziva hlavni
// pipeline a skoro se omylem smazala jako mrtvy duplikat). Tenhle nastroj
// je obecny a trvaly, ne jednorazovy - proto bez tmp_.
const fs = require("fs");
const THREE = require("three");
const MeshBVHLib = require("/opt/konfigurator/webapp/js/three-mesh-bvh.js");
THREE.BufferGeometry.prototype.computeBoundsTree = MeshBVHLib.computeBoundsTree;
THREE.Mesh.prototype.raycast = MeshBVHLib.acceleratedRaycast;

const KAT_DIR = "/opt/konfigurator/webapp/katalog/";
const CAR_BODIES_DIR = KAT_DIR + "car_bodies/";

// Rozumne meze pro interiorHeightMM, zjistene 2026-09-11 z --all pruchodu
// celym katalogem (304 karoserii): p5=1220mm, p50=1504mm, p99=2500mm.
// Pod HEIGHT_MIN jsou tahaci vozidla s otevrenou loznou plochou (pickupy -
// Hilux/Ranger/D-Max/Amarok, 520-1074mm - REALNA nizka hodnota, ne vada,
// ale strukturalne jiny typ vozidla nez uzavrena dodavka) a par malych
// osobakem odvozenych modelu (Renault 4, ~960mm). Nad HEIGHT_MAX jen 4
// zaznamy (Ford Custom FO55/FO56, VW Transporter VW42/VW43, "Multicab"/
// "L-Partition" varianty) - POTVRZENA vadna data: interiorHeightMM
// (2500-2900mm) PREKRACUJE vlastni deklarovanou VNEJSI vysku vozidla
// (1978-1981mm v car_models.name) - fyzicky nemozne, nakladovy prostor
// nemuze byt vyssi nez cele vozidlo. FO55/VW42 a FO56/VW43 navic sdileji
// bit-identicke trojuhelnikove pocty napric ruznymi znackami - nejspis
// spatne/sdilene nahrany zdrojovy soubor, ne nezavisle modelovana
// geometrie. Meze jsou vedome SIRSI nez cisty p1-p99 rozsah (aby
// nezachytavaly kazdy maly osobak), cilem je zachytit JEN fyzicky
// nesmyslne hodnoty, ne kazdou odchylku od prumeru.
const HEIGHT_MIN_MM = 700;
const HEIGHT_MAX_MM = 2350;

function readGlbFull(glbPath) {
  const buf = fs.readFileSync(glbPath);
  const magic = buf.readUInt32LE(0);
  if (magic !== 0x46546c67) throw new Error(`${glbPath}: neni platny .glb`);
  let offset = 12, json = null, binChunk = null;
  while (offset < buf.length) {
    const chunkLen = buf.readUInt32LE(offset);
    const chunkType = buf.readUInt32LE(offset + 4);
    const chunkData = buf.slice(offset + 8, offset + 8 + chunkLen);
    if (chunkType === 0x4e4f534a) json = JSON.parse(chunkData.toString("utf8"));
    else if (chunkType === 0x004e4942) binChunk = chunkData;
    offset += 8 + chunkLen;
  }
  if (!json || !json.meshes || !json.meshes.length) throw new Error(`${glbPath}: chybi mesh`);
  const prim = json.meshes[0].primitives[0];
  function readAccessor(accIdx) {
    const acc = json.accessors[accIdx];
    const bv = json.bufferViews[acc.bufferView];
    const byteOffset = (bv.byteOffset || 0) + (acc.byteOffset || 0);
    const numComp = { SCALAR: 1, VEC2: 2, VEC3: 3, VEC4: 4 }[acc.type];
    if (acc.componentType === 5126) return new Float32Array(binChunk.buffer, binChunk.byteOffset + byteOffset, acc.count * numComp);
    if (acc.componentType === 5123) return new Uint16Array(binChunk.buffer, binChunk.byteOffset + byteOffset, acc.count * numComp);
    if (acc.componentType === 5125) return new Uint32Array(binChunk.buffer, binChunk.byteOffset + byteOffset, acc.count * numComp);
    throw new Error("neznamy componentType " + acc.componentType);
  }
  const positions = readAccessor(prim.attributes.POSITION);
  const normals = prim.attributes.NORMAL != null ? readAccessor(prim.attributes.NORMAL) : null;
  const indices = prim.indices != null ? readAccessor(prim.indices) : null;
  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  if (normals) geo.setAttribute("normal", new THREE.BufferAttribute(normals, 3));
  if (indices) geo.setIndex(new THREE.BufferAttribute(indices, 1));
  const mesh = new THREE.Mesh(geo, new THREE.MeshBasicMaterial({ side: THREE.DoubleSide }));
  mesh.updateMatrixWorld(true);
  const triCount = indices ? indices.length / 3 : positions.length / 9;
  return { mesh, positions, normals, indices, triCount, fileSize: buf.length, materialCount: (json.materials || []).length };
}

function normalSanity(normals) {
  if (!normals) return { present: false };
  let nanCount = 0, zeroCount = 0, magSum = 0, n = normals.length / 3;
  for (let i = 0; i < n; i++) {
    const x = normals[i * 3], y = normals[i * 3 + 1], z = normals[i * 3 + 2];
    if (Number.isNaN(x) || Number.isNaN(y) || Number.isNaN(z)) { nanCount++; continue; }
    const mag = Math.sqrt(x * x + y * y + z * z);
    if (mag < 1e-6) zeroCount++;
    magSum += mag;
  }
  return { present: true, count: n, nanCount, zeroCount, avgMagnitude: +(magSum / n).toFixed(3) };
}

function bboxOf(positions) {
  let minX = Infinity, minY = Infinity, minZ = Infinity, maxX = -Infinity, maxY = -Infinity, maxZ = -Infinity;
  for (let i = 0; i < positions.length; i += 3) {
    const x = positions[i], y = positions[i + 1], z = positions[i + 2];
    if (x < minX) minX = x; if (x > maxX) maxX = x;
    if (y < minY) minY = y; if (y > maxY) maxY = y;
    if (z < minZ) minZ = z; if (z > maxZ) maxZ = z;
  }
  return { min: [minX, minY, minZ], max: [maxX, maxY, maxZ] };
}

const raycaster = new THREE.Raycaster();
function topDownHitY(walls, x, z, yStart, far) {
  raycaster.set(new THREE.Vector3(x, yStart, z), new THREE.Vector3(0, -1, 0));
  raycaster.far = far;
  const hits = raycaster.intersectObjects(walls, false);
  return hits.length ? +(yStart - hits[0].distance).toFixed(0) : null;
}

// Skenuje strop po cele delce (N bodu podel Z, par bodu podel X) - vraci
// podil bodu, kde top-down paprsek narazi NA NECO VYSOKO (>60% vyskoveho
// rozsahu), tedy kde je "strop-like" pokryti, vs. kolik proste propadne
// az na podlahu (zadna strecha tam neni).
function roofCoverage(walls, xRange, zMin, zMax, yTop, yFloorGuess, samples = 24) {
  let coveredHigh = 0, total = 0;
  const highThresh = yFloorGuess + (yTop - yFloorGuess) * 0.6;
  for (let i = 0; i < samples; i++) {
    const z = zMin + (zMax - zMin) * (i / (samples - 1));
    for (const x of xRange) {
      total++;
      const hitY = topDownHitY(walls, x, z, yTop + 200, 3000);
      if (hitY != null && hitY >= highThresh) coveredHigh++;
    }
  }
  return { coveredHigh, total, pct: +(100 * coveredHigh / total).toFixed(0) };
}

function auditVehicle(base, verbose) {
  const parts = {};
  for (const suf of ["_B", "_L", "_R_D"]) {
    const p = CAR_BODIES_DIR + base + suf + ".glb";
    if (!fs.existsSync(p)) return { base, ok: false, error: `chybi ${suf}.glb` };
    parts[suf] = readGlbFull(p);
  }
  const wallMeshes = [parts["_B"].mesh, parts["_L"].mesh, parts["_R_D"].mesh];
  wallMeshes.forEach(m => m.geometry.computeBoundsTree());

  const bboxL = bboxOf(parts["_L"].positions);
  const bboxR = bboxOf(parts["_R_D"].positions);
  const bboxB = bboxOf(parts["_B"].positions);
  const yTop = Math.max(bboxL.max[1], bboxR.max[1]);
  const yFloor = Math.min(bboxL.min[1], bboxR.min[1]);
  const zMin = Math.min(bboxL.min[2], bboxR.min[2]);
  const zMax = Math.max(bboxL.max[2], bboxR.max[2]);
  const xMin = Math.min(bboxL.min[0], bboxR.min[0]);
  const xMax = Math.max(bboxL.max[0], bboxR.max[0]);

  // Stejna detekcni logika jako generator (tmp_2026-08-31_batch_engine.js
  // `dirZtoBulkhead`) - POROVNA se stred _B proti stredu _L na ose Z,
  // misto pevneho predpokladu "zMax = predek". Zmereno na 12 vozidlech
  // (bot3 2026-09-11): prepazka sedi na zapornem konci VZDY - tahle
  // detekce tedy prakticky vzdy vrati "zMin", ale pouziva se dal (je
  // konzistentni s generatorem a nic nestoji), ne proto, ze by katalog
  // mel promenlivou orientaci.
  const bMidZ = (bboxB.min[2] + bboxB.max[2]) / 2;
  const lMidZ = (bboxL.min[2] + bboxL.max[2]) / 2;
  const bulkheadSide = bMidZ > lMidZ ? "zMax" : "zMin";
  const bulkheadZMM = +(bulkheadSide === "zMax" ? zMax : zMin).toFixed(1);

  const rc = roofCoverage(wallMeshes, [-100, 100], zMin, zMax, yTop, yFloor);

  const nsL = normalSanity(parts["_L"].normals);
  const nsR = normalSanity(parts["_R_D"].normals);
  const nsB = normalSanity(parts["_B"].normals);
  const normalsOk = nsL.present && nsR.present && nsB.present && nsL.nanCount === 0 && nsR.nanCount === 0 && nsB.nanCount === 0;

  const interiorHeightMM = Math.round(yTop - yFloor);
  const heightPlausible = interiorHeightMM >= HEIGHT_MIN_MM && interiorHeightMM <= HEIGHT_MAX_MM;

  const result = {
    base,
    ok: true,
    triCounts: { B: parts["_B"].triCount, L: parts["_L"].triCount, R_D: parts["_R_D"].triCount },
    normalsOk,
    interiorHeightMM,
    heightPlausible,
    heightBoundsMM: { min: HEIGHT_MIN_MM, max: HEIGHT_MAX_MM },
    interiorLengthMM: Math.round(zMax - zMin),
    widthMM: Math.round(xMax - xMin),
    zMinMM: +zMin.toFixed(1),
    zMaxMM: +zMax.toFixed(1),
    bulkheadSide, // "zMin" nebo "zMax" - na ktere strane lezi _B (prepazka), viz komentar nahore
    bulkheadZMM, // Z souradnice prepazky - REALNA geometrie, nestavet nahradni rovinu
    roofCoveragePct: rc.pct, // % bodu podel delky, kde "strop" neco vysoko zachyti
    hasRoof: rc.pct >= 50, // hruby prah - pod 50% je strecha jen zlomek delky, ne skutecny strop
  };
  if (verbose) {
    console.log(`\n=== ${base} ===`);
    console.log(`  trojuhelniky: B=${result.triCounts.B} L=${result.triCounts.L} R_D=${result.triCounts.R_D}`);
    console.log(`  normaly OK: ${normalsOk} (L: nan=${nsL.nanCount} avgMag=${nsL.avgMagnitude}, R_D: nan=${nsR.nanCount} avgMag=${nsR.avgMagnitude})`);
    console.log(`  interior vyska (max Y modelovane geometrie nad podlahou Y=0): ${result.interiorHeightMM}mm ${heightPlausible ? "" : `- MIMO ROZUMNE MEZE [${HEIGHT_MIN_MM},${HEIGHT_MAX_MM}]!`}`);
    console.log(`  interior delka (Z rozsah): ${result.interiorLengthMM}mm (Z=${result.zMinMM}..${result.zMaxMM}), sirka: ${result.widthMM}mm`);
    console.log(`  prepazka B na strane ${result.bulkheadSide} (Z=${result.bulkheadZMM}) - REALNA geometrie, existuje`);
    console.log(`  "strop" pokryti po delce: ${rc.coveredHigh}/${rc.total} bodu (${rc.pct}%) ${result.hasRoof ? "-> STRECHA JE (aspon useky)" : "-> STRECHA CHYBI (jen zlomek delky - jedina skutecne chybejici plocha)"}`);
  }
  return result;
}

const arg = process.argv[2];
if (!arg || arg === "--all") {
  const bases = [...new Set(fs.readdirSync(CAR_BODIES_DIR)
    .filter(f => /_(B|L|R_D)\.glb$/.test(f))
    .map(f => f.replace(/_(B|L|R_D)\.glb$/, "")))];
  console.log(`Skenuji ${bases.length} karoserii v katalogu...`);
  const rows = [];
  for (const base of bases) {
    try { rows.push(auditVehicle(base, false)); }
    catch (e) { rows.push({ base, ok: false, error: e.message }); }
  }
  const ok = rows.filter(r => r.ok);
  const withRoof = ok.filter(r => r.hasRoof);
  const implausible = ok.filter(r => !r.heightPlausible);
  console.log(`\nHotovo: ${ok.length}/${rows.length} zmereno bez chyby.`);
  console.log(`Strecha (>=50% delky pokryto vysoko): ${withRoof.length}/${ok.length} karoserii.`);
  console.log(`Interior vyska: min=${Math.min(...ok.map(r=>r.interiorHeightMM))}mm, max=${Math.max(...ok.map(r=>r.interiorHeightMM))}mm`);
  console.log(`Mimo rozumne meze [${HEIGHT_MIN_MM},${HEIGHT_MAX_MM}]mm: ${implausible.length}/${ok.length} - ${implausible.map(r=>`${r.base}(${r.interiorHeightMM}mm)`).join(", ") || "zadna"}`);
  const errs = rows.filter(r => !r.ok);
  if (errs.length) console.log(`\nChyby (${errs.length}): ${errs.map(r=>`${r.base}: ${r.error}`).join(" | ")}`);
  if (process.argv.includes("--csv")) {
    console.log("\nbase;interiorHeightMM;heightPlausible;interiorLengthMM;widthMM;bulkheadSide;bulkheadZMM;roofCoveragePct;hasRoof;triB;triL;triR_D;normalsOk");
    ok.forEach(r => console.log(`${r.base};${r.interiorHeightMM};${r.heightPlausible};${r.interiorLengthMM};${r.widthMM};${r.bulkheadSide};${r.bulkheadZMM};${r.roofCoveragePct};${r.hasRoof};${r.triCounts.B};${r.triCounts.L};${r.triCounts.R_D};${r.normalsOk}`));
  }
} else if (arg === "--json") {
  // Strojove citelny vystup pro scripts/2026-09-09_turntable_job.py
  // (resolve_karoserie_odrazy) - JEDNO cislo na radek stdout, zadny
  // dalsi text. Chyba/mimo-meze se hlasi v samotnem JSONu (ok/error/
  // heightPlausible), ne vyjimkou - volajici rozhoduje o fallbacku.
  const base = (process.argv[3] || "").replace(/^car_bodies\//, "");
  if (!base) { console.log(JSON.stringify({ ok: false, error: "chybi jmeno karoserie (2. argument)" })); process.exit(1); }
  let result;
  try { result = auditVehicle(base, false); }
  catch (e) { result = { base, ok: false, error: e.message }; }
  console.log(JSON.stringify(result));
} else {
  const base = arg.replace(/^car_bodies\//, "");
  const result = auditVehicle(base, true);
  if (!result.ok) console.error(`CHYBA (${base}): ${result.error}`);
}
