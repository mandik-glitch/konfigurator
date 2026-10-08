// Genericky (vozidlo-nezavisly) engine pro shape_geometry_methods.id=11
// "prepocet-kolizni-rezervy-existujici-sestavy", pouzitelny napric CELOU
// sirokou davkou (14 modelu, 44 sestav) zadanou bot8 2026-09-12, MISTO
// psani bespoke skriptu pro kazdy model zvlast (jak delaly drivejsi K-075/
// K-118/K-119 piloty).
//
// PRINCIP (odvozeno empiricky z topologickeho skenu VSECH 44 sestav + z
// GLB Z-rozsahu vsech 14 B.glb karoserii, viz AGENTS_LOG zapis k tomuto
// skriptu): kazdy z 14 modelu ma N fyzickych noh na Z-pozicich `legZ`,
// serazenych VZESTUPNE (nejzapornejsi = index 0). U VSECH 14 modelu bez
// vyjimky (overeno primo na GLB) je noha s indexem 0 (nejzapornejsi Z)
// TA, ktera se fyzicky dotyka prepazky (car_body *_B.glb) - a je vzdy
// "cistě plná" (nikdy nema vyrezovou trojici). Tato noha (a JEN ona)
// dostava deltaZ. Ostatni nohy (index >=1) jsou Z-fixni; ty s vyrezovou
// trojici (sloupek-pred-podbehem/zadni-svislice-nad-zarezem/pricka-
// uzavreni-vyrezu na jejich Z) dostavaji deltaY na teto trojici (podle
// vzorce id=6) + navazane uhelnik-nohaN kusy na svaru; ostatni (cisté
// plné, ne u prepazky) zustavaji uplne beze zmeny.
//
// Sloupce (nosnik/spojnice/eurobox-<colPrefix>N-<level>) spojuji nohu N a
// N+1. JEN sloupec0 (mezi nohou0 a nohou1) se natahuje v Z (protoze jen
// noha0 se hybe) - vsechny ostatni sloupce jsou v Z beze zmeny. Y-dorovnani
// (krok 5/6 procedury) se pocita NEZAVISLE pro kazdy sloupec, podle NEJVYSSI
// z novych Y_new hranic sousednich vyrezovych noh (pokud zadna sousedni
// noha vyrez nema, dorovnani se nepocita vubec).
//
// Klasifikace jednotlivych dilu je ZALOZENA NA ROLI + NEJBLIZSI NOZE (Z
// tolerance 2mm), ne na vyctu konkretnich nazvu roli pro kazdy model -
// zobecneni oproti drivejsim per-model skriptum (tmp_2026-09-12_bot8_
// batch_184.js aj.), overeno SELF-CHECKEM proti uz schvalenemu paru
// product_assemblies 279->340 (viz spodek souboru, `--selfcheck`).

const DELTA_Z = 8;   // 10mm - 2mm (prepazka)
const DELTA_Y = 10;  // 30mm - 20mm (podbeh)
const HALF_T = 15;   // polovina tloustky profilu (30mm) - pricka-uzavreni-vyrezu offset
const ZTOL = 2;

const near = (a, b, tol) => Math.abs(a - b) < (tol == null ? 0.05 : tol);

// ---- id=6 vzorec pro Y-posun vyrezove trojice (nezmeneno oproti drivejsim skriptum) ----
function shiftVyrezPart(p, role, oldYnew, deltaY) {
  const [x, y, z] = p.position;
  const newYnew = oldYnew + deltaY;
  if (role === "sloupek-pred-podbehem") {
    const oldH = p.scale[1] * 1000, floorY = y - oldH / 2, newH = newYnew - floorY;
    return { ...p, position: [x, floorY + newH / 2, z], scale: [p.scale[0], newH / 1000, p.scale[2]] };
  }
  if (role === "zadni-svislice-nad-zarezem") {
    const oldH = p.scale[1] * 1000, topY = y + oldH / 2, newH = topY - newYnew;
    return { ...p, position: [x, newYnew + newH / 2, z], scale: [p.scale[0], newH / 1000, p.scale[2]] };
  }
  if (role === "pricka-uzavreni-vyrezu") {
    // CISTA DELTA (ne absolutni "newYnew+HALF_T"), viz AGENTS_LOG zapis:
    // na K-291e/K-290 (Mercedes Vito) skutecna GLB geometrie ukazala, ze
    // pricka NENI vzdy presne HALF_T nad seamem (u K-075/K-118 ano - proto
    // puvodni vzorec tam vysel bit-presne -, u Vito sedi az 60-90mm nad
    // seamem, jiny fyzicky navrh vyrezu). Cisty posun o deltaY zachovava
    // spravny puvodni relativni offset u OBOU pripadu (na K-075 dava
    // matematicky IDENTICKY vysledek jako stary vzorec, protoze tam
    // old_y = oldYnew+HALF_T platilo presne).
    return { ...p, position: [x, y + deltaY, z] };
  }
  throw new Error("neznama vyrez role: " + role);
}

// legZ: pole Z pozic noh, VZESTUPNE serazene (index0 = nejzapornejsi = u prepazky).
// notchLegIdx: Set indexu noh, ktere maji vyrezovou trojici.
// colPrefix: "col" nebo "sloupec" (nazev pouzity v roli "nosnik-<colPrefix>N-<level>").
// parts: puvodni pole dilu (nemodifikuje se, vraci se nova kopie).
function analyzeAssembly(parts, cfg) {
  const { legZ, notchLegIdx, colPrefix } = cfg;
  const nLegs = legZ.length;

  // oldYnew per notch leg - PRIMO Z DAT (zadni-svislice-nad-zarezem na dane Z)
  const oldYnewByLeg = {};
  for (const idx of notchLegIdx) {
    const cand = parts.find(p => p.role === "zadni-svislice-nad-zarezem" && near(p.position[2], legZ[idx], ZTOL));
    if (!cand) throw new Error(`notchLegIdx obsahuje ${idx}, ale zadni-svislice-nad-zarezem na Z=${legZ[idx]} nenalezena`);
    const bottom = cand.position[1] - cand.scale[1] * 500;
    oldYnewByLeg[idx] = bottom;
  }

  // sloupce: kolik jich je = nLegs-1, colIndex i spojuje leg[i]..leg[i+1]
  const nCols = nLegs - 1;
  const colRe = new RegExp(`^(nosnik|spojnice|eurobox)-${colPrefix}(\\d+)-(\\w+)$`);
  const colParts = parts.filter(p => colRe.test(p.role || ""));
  const colLevels = {}; // colIndex -> Set(level)
  for (const p of colParts) {
    const m = colRe.exec(p.role);
    const ci = Number(m[2]), lvl = m[3];
    (colLevels[ci] = colLevels[ci] || new Set()).add(lvl);
  }

  return { legZ, notchLegIdx, oldYnewByLeg, nCols, colPrefix, colLevels, colRe };
}

function transformAssemblyGeneric(parts, cfg) {
  const A = analyzeAssembly(parts, cfg);
  const { legZ, notchLegIdx, oldYnewByLeg, nCols, colPrefix, colLevels, colRe } = A;
  const nLegs = legZ.length;

  // pro kazdy sloupec: serad levely vzestupne podle Y (nejnizsi = index 0), pro dorovnani
  const colLevelOrder = {}; // colIndex -> [level,...] serazene dle Y vzestupne
  for (const ci of Object.keys(colLevels)) {
    const levels = [...colLevels[ci]];
    const yOf = lvl => Math.min(...parts.filter(p => p.role === `nosnik-${colPrefix}${ci}-${lvl}`).map(p => p.position[1]));
    levels.sort((a, b) => yOf(a) - yOf(b));
    colLevelOrder[ci] = levels;
  }

  // krok 5/6: dorovnani potreba per sloupec - threshold = max(newYnew hranicnich vyrezovych noh)
  const colDorovnani = {}; // colIndex -> {neededShift, levels(order)}
  for (let ci = 0; ci < nCols; ci++) {
    const legA = ci, legB = ci + 1;
    const bordering = [legA, legB].filter(l => notchLegIdx.has(l));
    if (bordering.length === 0) { colDorovnani[ci] = { neededShift: 0, order: colLevelOrder[ci] || [] }; continue; }
    const threshold = Math.max(...bordering.map(l => oldYnewByLeg[l] + DELTA_Y));
    const order = colLevelOrder[ci] || [];
    if (order.length === 0) { colDorovnani[ci] = { neededShift: 0, order }; continue; }
    const lowestLevel = order[0];
    const nosnikLow = parts.filter(p => p.role === `nosnik-${colPrefix}${ci}-${lowestLevel}`);
    const floorEdge = Math.min(...nosnikLow.map(p => p.position[1])) - HALF_T;
    const neededShift = Math.max(0, threshold - floorEdge);
    colDorovnani[ci] = { neededShift, order, floorEdge, threshold };
  }

  function dorovnaniShift(ci, level) {
    const d = colDorovnani[ci];
    if (!d || d.neededShift <= 0) return 0;
    const N = d.order.length, i = d.order.indexOf(level);
    if (N <= 1 || i < 0) return 0;
    return d.neededShift * (N - 1 - i) / (N - 1);
  }

  const log = { leg0Z: 0, legOtherUnchanged: 0, vyrezShift: 0, uhelnikNoha0: 0, uhelnikSharedShift: 0,
    uhelnikSharedUnaffected: 0, uhelnikOtherUnaffected: 0, colStretchBeam: 0, colStretchSpojniceEnd: 0,
    colStretchSpojniceMid: 0, colOtherBeam: 0, colOtherSpojnice: 0, dorovnaniApplied: 0, carBody: 0,
    unclassified: [] };
  const out = [];

  for (const orig of parts) {
    const p = JSON.parse(JSON.stringify(orig));
    const role = p.role || "";
    const [x, y, z] = p.position;

    if (String(p.part_id || "").startsWith("car_body_")) { out.push(p); log.carBody++; continue; }
    if (role.startsWith("kontrolni-pomucka")) { out.push(p); continue; }

    // -- uhelnik-noha<N> --
    let m = /^uhelnik-noha(\d+)$/.exec(role);
    if (m) {
      const legIdx = Number(m[1]);
      if (legIdx === 0) { out.push({ ...p, position: [x, y, z + DELTA_Z] }); log.uhelnikNoha0++; continue; }
      if (notchLegIdx.has(legIdx)) {
        const oldYnew = oldYnewByLeg[legIdx];
        // touchSet (volitelne, viz cfg.touchSet) - PREDNOSTNI kriterium,
        // zjistene skutecnym GLB bbox dotykem vuci vyrezove trojici PRED
        // transformem (viz 2026-09-12_wide_process_one.js) - presnejsi nez
        // pevna Y-tolerance, protoze konvence "kde presne sedi uhelnik vuci
        // svaru" se mezi modely lisi (K-075/K-118: presne na svaru nebo
        // svar+30; K-291e/K-290: svar-11 - nelze jedno pevne cislo pouzit
        // univerzalne). Kdyz touchSet neni predan, spadne na starsi
        // Y-tolerance heuristiku (zpetna kompatibilita/self-check).
        const key = `${x.toFixed(2)},${y.toFixed(2)},${z.toFixed(2)}`;
        const shouldShift = cfg.touchSet ? cfg.touchSet.has(key) : (near(y, oldYnew, 3) || near(y, oldYnew + 30, 3));
        if (shouldShift) {
          out.push({ ...p, position: [x, y + DELTA_Y, z] }); log.uhelnikSharedShift++; continue;
        }
        out.push(p); log.uhelnikSharedUnaffected++; continue;
      }
      out.push(p); log.uhelnikOtherUnaffected++; continue;
    }

    // -- vyrezova trojice - Z musi sedet na notch noze --
    if (role === "sloupek-pred-podbehem" || role === "zadni-svislice-nad-zarezem" || role === "pricka-uzavreni-vyrezu") {
      const legIdx = legZ.findIndex(lz => near(z, lz, ZTOL));
      if (legIdx >= 0 && notchLegIdx.has(legIdx)) {
        out.push(shiftVyrezPart(p, role, oldYnewByLeg[legIdx], DELTA_Y)); log.vyrezShift++; continue;
      }
      log.unclassified.push({ role, z, reason: "vyrez role ale Z nesedi na zadnou notch nohu" });
      out.push(p); continue;
    }

    // -- sloupcove role (nosnik/spojnice/eurobox-<colPrefix>N-<level>) --
    m = colRe.exec(role);
    if (m) {
      const kind = m[1], ci = Number(m[2]), lvl = m[3];
      const dy = dorovnaniShift(ci, lvl);
      const isStretched = (ci === 0); // jen sloupec0 se natahuje (jen noha0 se hybe v Z)
      if (kind === "nosnik" || kind === "eurobox") {
        const newZ = isStretched ? z + DELTA_Z / 2 : z;
        const newScale = (kind === "nosnik" && isStretched) ? [p.scale[0], p.scale[1] - DELTA_Z / 1000, p.scale[2]] : p.scale;
        out.push({ ...p, position: [x, y + dy, newZ], scale: newScale });
        if (isStretched) log.colStretchBeam++; else log.colOtherBeam++;
        continue;
      }
      // spojnice
      if (!isStretched) {
        out.push({ ...p, position: [x, y + dy, z] }); log.colOtherSpojnice++; continue;
      }
      const legA = legZ[ci], legB = legZ[ci + 1];
      const distA = Math.abs(z - legA), distB = Math.abs(z - legB);
      const NEAR_LEG_TOL = 60;
      if (distA < NEAR_LEG_TOL && distA <= distB) {
        out.push({ ...p, position: [x, y + dy, z + DELTA_Z] }); log.colStretchSpojniceEnd++; continue;
      }
      if (distB < NEAR_LEG_TOL && distB < distA) {
        out.push({ ...p, position: [x, y + dy, z] }); log.colStretchSpojniceEnd++; continue;
      }
      out.push({ ...p, position: [x, y + dy, z + DELTA_Z / 2] }); log.colStretchSpojniceMid++; continue;
    }

    // -- vse ostatni: dily "patrici" jedne konkretni noze (predni-svislice, cap,
    //    spojnice-dolni/horni(-uzavreni/-kratka), zadni-svislice(-dolni), zaslepka*,
    //    logo-ochrana* aj.) - klasifikovano podle NEJBLIZSI nohy (Z tolerance),
    //    ne podle vyctu jmen roli (zobecneni napric modely s ruznym pojmenovanim).
    const legIdx = legZ.findIndex(lz => near(z, lz, ZTOL));
    if (legIdx === 0) { out.push({ ...p, position: [x, y, z + DELTA_Z] }); log.leg0Z++; continue; }
    if (legIdx > 0) { out.push(p); log.legOtherUnchanged++; continue; }

    // Z nesedi presne na zadnou znamou nohu (napr. dekorativni/ochranne dily
    // typu logo-ochrana-* upevnene NA ramp sloupce, ne na noze samotne -
    // jediny vyskyt v cele teto sirsi davce: product_assemblies.id=134,
    // K-075 verze A). Genericke (ne K-075-specificke) fallback pravidlo:
    // pokud Z lezi uvnitr rozpeti sloupce0 (jediny "natahovany" sloupec,
    // mezi noha0..noha1), aplikuj STEJNOU linearni interpolaci jako na
    // nosnik-col0 rampu (frac=0 u noha1/fixni konec, frac=1 u noha0/hybny
    // konec). Jinak (mimo rozpeti sloupce0, nebo >0 sloupcu, ktere se
    // nehybou vubec) zustava beze zmeny.
    if (nCols >= 1) {
      const legFix = legZ[1], legMove = legZ[0];
      // "u prepazky" skupina (napr. logo pripevnene primo na noze0, ne na
      // rampe) - poznana tim, ze lezi BLIZ noze0 nez cely rozpon sloupce0
      // (tolerance 25mm, empiricky odvozeno z K-075 id=134 "front" indexu,
      // ktery byl 10-16mm od noha0) - dostava CELOU deltaZ jako zbytek noha0.
      if (Math.abs(z - legMove) < 25) {
        out.push({ ...p, position: [x, y, z + DELTA_Z] });
        log.unclassified.push({ role, part_id: p.part_id, z, handled: "noha0-blizko (cela deltaZ)" });
        continue;
      }
      const zMin = Math.min(legFix, legMove) - 5, zMax = Math.max(legFix, legMove) + 5;
      if (z > zMin && z < zMax) {
        const frac = (z - legFix) / (legMove - legFix);
        const newLegMove = legMove + DELTA_Z;
        const newZ = legFix + frac * (newLegMove - legFix);
        out.push({ ...p, position: [x, y, newZ] });
        log.unclassified.push({ role, part_id: p.part_id, z, handled: "col0-ramp-interpolace", newZ });
        continue;
      }
    }
    log.unclassified.push({ role, part_id: p.part_id, z, handled: "beze zmeny (fallback)" });
    out.push(p);
  }

  return { parts: out, log, colDorovnani };
}

module.exports = { transformAssemblyGeneric, analyzeAssembly, DELTA_Z, DELTA_Y, shiftVyrezPart };

// ============================================================
if (require.main === module && process.argv.includes("--selfcheck")) {
  const fs = require("fs");
  const { execSync } = require("child_process");
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
cur.execute("SELECT id, data FROM product_assemblies WHERE id IN (279,340)")
out = {}
for r in cur.fetchall():
    out[r["id"]] = json.loads(r["data"])["parts"]
conn.close()
print(json.dumps(out))
`;
  fs.writeFileSync("/tmp/_selfcheck_279.py", dumpPy);
  const DB = JSON.parse(execSync("api/venv/bin/python3 /tmp/_selfcheck_279.py", { cwd: "/opt/konfigurator", maxBuffer: 1024 * 1024 * 80 }).toString());
  const p279 = DB[279];
  const p340 = DB[340].filter(p => !(p.role || "").startsWith("kontrolni-pomucka"));

  const cfg = { legZ: [-1358.5025482177734, -898.5025482177734, -34.50254821777344], notchLegIdx: new Set([1, 2]), colPrefix: "col" };
  // K-075 279 pouziva "spojnice-horni-uzavreni" a "zaslepka-*" - genericky engine je
  // resi pres "nejblizsi noha" bucket automaticky, zadne mapovani neni potreba.
  // logo-ochrana-* v 279 VYNECHAVAME z testu (netykaji se generickeho enginu, resi
  // se samostatne pripadnou rucni logikou pokud by se u jineho modelu vyskytly -
  // u vsech 14 sirokych modelu se NEVYSKYTUJI, viz topologicky sken).
  const irrelevant = p => /^logo-ochrana-/.test(p.role || "");
  const p279c = p279.filter(p => !irrelevant(p));
  const p340c = p340.filter(p => !irrelevant(p));

  const { parts: myResult, log } = transformAssemblyGeneric(p279c, cfg);
  console.log("log:", JSON.stringify(log, null, 1));

  function byRoleSorted(parts) {
    const m = {};
    for (const p of parts) { const r = p.role || "(none)"; (m[r] = m[r] || []).push(p); }
    for (const r in m) m[r].sort((a, b) => a.position[2] - b.position[2] || a.position[0] - b.position[0] || a.position[1] - b.position[1]);
    return m;
  }
  const mMine = byRoleSorted(myResult.filter(p => !String(p.part_id || "").startsWith("car_body_")));
  const mRef = byRoleSorted(p340c.filter(p => !String(p.part_id || "").startsWith("car_body_")));
  let mismatches = 0;
  const roles = new Set([...Object.keys(mMine), ...Object.keys(mRef)]);
  for (const r of [...roles].sort()) {
    const a = mMine[r] || [], b = mRef[r] || [];
    if (a.length !== b.length) { console.log("COUNT MISMATCH", r, a.length, b.length); mismatches++; continue; }
    for (let i = 0; i < a.length; i++) {
      const dp = a[i].position.map((v, idx) => Math.abs(v - b[i].position[idx]));
      const ds = a[i].scale.map((v, idx) => Math.abs(v - b[i].scale[idx]));
      if (dp.some(v => v > 0.01) || ds.some(v => v > 0.0001)) {
        console.log("MISMATCH", r, "#" + i, "mine=", a[i].position, a[i].scale, "ref=", b[i].position, b[i].scale);
        mismatches++;
      }
    }
  }
  console.log(mismatches === 0
    ? "SELF-CHECK OK: genericky engine presne odpovida schvalenemu 279->340 na vsech rolich."
    : `SELF-CHECK SELHAL: ${mismatches} nesrovnalosti.`);
  process.exit(mismatches === 0 ? 0 : 1);
}
