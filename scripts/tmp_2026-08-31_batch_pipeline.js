// Generic eurobox-rack pipeline (bot16, 2026-08-31) - parametrizovana verze
// Vivaro OP18 pilotniho postupu (tmp_2026-08-31_vivaro_step1..7 + build_full),
// pouzita davkove pro Ford Custom/Transit Custom (13 modelu) a VW Transporter
// T6/T7 (9 modelu). Kazdy krok = FRESH kolizni krokovani proti REALNE GLB
// geometrii daneho vozidla (zadne cislo prevzate z jineho modelu).
const THREE = require("three");
const fs = require("fs");
const { buildPlainAtDepth, buildVyrezAtDepth } = require("/opt/konfigurator/scripts/tmp_2026-08-30_build_depth_variants_both.js");
// OPRAVA (bug #4 "noha v otvoru bocnich posuvnych dveri", 2026-09-03,
// sjednoceno z tmp_2026-09-02_doorvoid_pipeline.js/tmp_2026-09-02_jumpy_
// pipeline.js, kde uz existovalo, ale POUZE pro FO31/VW25/Jumpy): tenhle
// PUVODNI/sdileny pipeline soubor (pořád pouzivany pro VSECHNY ostatni
// vozidla, viz TASKS.md "Audit zbylych ~113 eurobox regálů") dosud VUBEC
// nekontroloval, jestli noha nekonci uvnitr skutecneho otvoru bocnich
// posuvnych dveri v _R_D.glb (zadny material = "volno" pro kolizni test,
// i kdyz jde o funkcni otvor, ne o skutecny prostor pro nohu regalu).
// confirmDoorGaps = robustni verze (vertex-density heuristika + realny
// koliznim probe test proti falesnym pozitivum na sparse/velkoplosnych
// panelech), viz car_body_placement_methods.id=1 klic
// "vylouceni_bocniho_dvernich_otvoru_2026_09_02".
const { confirmDoorGaps } = require("/opt/konfigurator/scripts/tmp_2026-09-02_bot25_confirm_doorgap.js");

const D = 326, T = 30, H = 1180;
const CAP_H = 260, CUTOUT_H = 395;
const TOP_Y = H - CAP_H; // 920
const CAP_FLANGE_THICKNESS = 3;
const KAT = "/opt/konfigurator/webapp/katalog/";
const ENDCAP = KAT + "product_3071.glb";
const EUROBOX_GLB = { 120: KAT + "product_3788.glb", 170: KAT + "product_3793.glb", 220: KAT + "product_3794.glb", 270: KAT + "product_3795.glb" };
const EUROBOX_PID = { 120: "product_3788", 170: "product_3793", 220: "product_3794", 270: "product_3795" };
const CONNECTOR_POS = { 1: [15, 415], 2: [15, 415, 816], 3: [15, 415, 816, 1217] };
const CLEAR_SPACING = { 1: 430, 2: 832, 3: 1232 };
const WIDTH_TRY_ORDER = [3, 2, 1];
const Q_ALONG_Z = [-0.707107, 0, 0, 0.707107];
const Q_ALONG_X = [0, 0, -0.707107, 0.707107];
const Q_ENDCAP_UP = [0.7071067811865475, 0, 0, 0.7071067811865475];

// OPRAVA (bug #3 "Y-offset regrese", VW31, 2026-09-03): explicitni sanity-
// check pro sdileny zapisovy kod - dily regalu (nohy/boxy/ramy, cokoliv
// KROME "car_body_*") jsou VZDY ve vlastnich "podlaha=Y0" souradnicich
// assembly, offset karoserie (interni normalizace raw GLB pro kolizni testy)
// se na ne NIKDY nesmi propsat. Misto ticheho zapisu spatnych dat (VW31:
// nohy/boxy na Y~1650mm, "regal leti nad podlahou") throw hned pri sestaveni.
const RACK_Y_MIN = -500, RACK_Y_MAX = 2500;
function assertSaneRackYPositions(parts) {
  for (const p of parts) {
    if ((p.part_id || "").startsWith("car_body_")) continue;
    const y = p.position && p.position[1];
    if (typeof y !== "number" || !isFinite(y) || y < RACK_Y_MIN || y > RACK_Y_MAX) {
      throw new Error(`assertSaneRackYPositions: dil "${p.role || p.part_id}" ma Y=${y} mimo rozumne rozmezi [${RACK_Y_MIN},${RACK_Y_MAX}] - pravdepodobne uniklý offset karoserie do dat regalu`);
    }
  }
}

// `backoffMm` (Robert 2026-09-12, pres bot3, nova paralelni serie regalu
// "AA-AE": "od predni prepazky se po kolizi vracime o 10mm" - vychozi 2
// zachovava presne dnesni chovani pro VSECHNY tri volani teto funkce
// (podlaha/prepazkaB/stenaL), zmena se predava explicitne JEN pro
// prepazkaB volani nove serie (viz opts.prepazkaBackoffMm v runPipeline
// nize) - podlaha a stenaL zustavaji na 2mm, Robert mluvil vyhradne o
// prepazce.
function stepUntilCollision1D(testFn, dir, maxSteps, label, backoffMm) {
  backoffMm = backoffMm == null ? 2 : backoffMm;
  let steps = 0, collided = false, val = 0;
  while (steps < maxSteps) {
    val += dir; steps++;
    if (testFn(val)) { collided = true; break; }
  }
  if (!collided) throw new Error(`${label}: zadna kolize po ${maxSteps} krocich`);
  const backoffVal = val - dir * backoffMm;
  const stillColliding = testFn(backoffVal);
  if (stillColliding) throw new Error(`${label}: po ${backoffMm}mm zpet stale koliduje`);
  return backoffVal;
}

// OPRAVA (bug #5 "noha zaborena do podlahoveho hrbu podbehu", MB47,
// 2026-09-03): "sloupek-pred-podbehem" driv VZDY sahal az na Y=0 (predpoklad
// rovne podlahy), bez ohledu na to, jestli realna podlaha na JEHO KONKRETNI
// X/Z pozici uz taky nezacala stoupat (podbeh muze zasahovat i 124mm od steny,
// kde sloupek stoji, ne jen u samotne steny, kde stoji "zadni-svislice-nad-
// zarezem" - tu resi jen computeYNewWall vyse). Novy volitelny parametr
// `sloupekBottom` (0 = puvodni chovani, beze zmeny) dovoluje zvednout i patu
// sloupku, pokud si volajici tenhle floor kolizne overil (viz
// computeSloupekBottom nize, pouzito v runPipeline STEP3/4).
function buildVyrezAtDepthExtended(D, Y_new, sloupekBottom) {
  sloupekBottom = sloupekBottom || 0;
  const base = buildVyrezAtDepth(D);
  const zCenter = T / 2;
  const parts = base.filter(p => !["sloupek-pred-podbehem", "pricka-uzavreni-vyrezu", "zadni-svislice-nad-zarezem", "spojnice-dolni"].includes(p.role));
  const orig = base.find(p => p.role === "sloupek-pred-podbehem");
  if (orig && Y_new - sloupekBottom > 1) {
    const colX = orig.position[0];
    parts.push({ position: [colX, sloupekBottom + (Y_new - sloupekBottom) / 2, zCenter], quaternion: [0, 0, 0, 1], scale: [1, (Y_new - sloupekBottom) / 1000, 1], role: "sloupek-pred-podbehem" });
  }
  const origSpojniceDolni = base.find(p => p.role === "spojnice-dolni");
  if (origSpojniceDolni) {
    if (sloupekBottom > 1) {
      // sloupek uz nedosahuje na podlahu - spodni spojnice (predni svislice
      // <-> pata sloupku) by na puvodni (podlahove) vysce visela do podbehu -
      // posun na novou (zvednutou) patu sloupku, stejny princip jako u
      // "pricka-uzavreni-vyrezu" nahore.
      parts.push({ position: [origSpojniceDolni.position[0], sloupekBottom + T / 2, origSpojniceDolni.position[2]], quaternion: origSpojniceDolni.quaternion, scale: origSpojniceDolni.scale, role: "spojnice-dolni" });
    } else {
      parts.push(origSpojniceDolni);
    }
  }
  const origPricka = base.find(p => p.role === "pricka-uzavreni-vyrezu");
  if (origPricka) {
    parts.push({ position: [origPricka.position[0], Y_new + T / 2, zCenter], quaternion: origPricka.quaternion, scale: origPricka.scale, role: "pricka-uzavreni-vyrezu" });
  }
  const upperLen = TOP_Y - Y_new;
  parts.push({ position: [D - T / 2, (Y_new + TOP_Y) / 2, zCenter], quaternion: [0, 0, 0, 1], scale: [1, upperLen / 1000, 1], role: "zadni-svislice-nad-zarezem" });
  return parts;
}

function runPipeline(engine, opts) {
  opts = opts || {};
  // Nova paralelni serie "AA-AE" (Robert 2026-09-12, pres bot3) - vychozi
  // hodnoty PRESNE zachovavaji dnesni chovani vsech existujicich 269
  // sestav (2mm/20mm), nova hodnota se predava jen explicitne z volajiciho
  // (viz scripts/tmp_2026-09-12_bot8_build_serie_AA.js).
  const prepazkaBackoffMm = opts.prepazkaBackoffMm == null ? 2 : opts.prepazkaBackoffMm;
  const podbehClearanceMm = opts.podbehClearanceMm == null ? 20 : opts.podbehClearanceMm;
  const log = [];
  const P = (...a) => log.push(a.join(" "));
  const { collidesWithWalls, buildLegObject, boxL0, boxB0, mirror, dirZtoBulkhead } = engine;
  const sgn = mirror ? -1 : +1; // worldX = offsetX + sgn*localX

  function toWorld(localParts, offsetX, offsetY, anchorZ) {
    return localParts.map(p => ({
      part_id: p.part_id || "Object_7",
      position: [offsetX + sgn * p.position[0], p.position[1] + offsetY, anchorZ + p.position[2]],
      quaternion: p.quaternion, scale: p.scale, role: p.role,
    }));
  }
  function groupAt(localParts, offsetX, offsetY, anchorZ) { return buildLegObject(toWorld(localParts, offsetX, offsetY, anchorZ)); }

  // ---- STEP 1: prvni (plain) noha - podlaha -> prepazka B -> stena L ----
  const cargoZlo = boxL0.min.z, cargoZhi = boxL0.max.z;
  let offsetX = -D / 2;
  let offsetY = (boxB0.max.y / 2) - H / 2;
  let anchorZ = (cargoZlo + cargoZhi) / 2 - T / 2;
  const plainParts0 = buildPlainAtDepth(D);

  if (collidesWithWalls(groupAt(plainParts0, offsetX, offsetY, anchorZ))) {
    throw new Error("step1: pocatecni pozice jiz koliduje - vozidlo pravdepodobne prilis male, nutna rucni kontrola");
  }
  const dY = stepUntilCollision1D((v) => collidesWithWalls(groupAt(plainParts0, offsetX, offsetY + v, anchorZ)), -1, 2500, "podlaha");
  offsetY += dY;
  const dZ = stepUntilCollision1D((v) => collidesWithWalls(groupAt(plainParts0, offsetX, offsetY, anchorZ + v)), dirZtoBulkhead, 3500, "prepazkaB", prepazkaBackoffMm);
  anchorZ += dZ;
  const dX = stepUntilCollision1D((v) => collidesWithWalls(groupAt(plainParts0, offsetX + v, offsetY, anchorZ)), mirror ? -1 : +1, 2500, "stenaL");
  offsetX += dX;
  P(`step1 OK offsetX=${offsetX.toFixed(1)} offsetY=${offsetY.toFixed(1)} anchorZ=${anchorZ.toFixed(1)} mirror=${mirror} dirZtoBulkhead=${dirZtoBulkhead}`);

  // ---- STEP 1b: vyloucit otvor bocnich posuvnych dveri (bug #4, viz import
  // vyse) - sken _R_D meshe na mezeru >150mm v Y=[200,900], KAZDA nalezena
  // mezera navic potvrzena realnym koliznim probe testem (odlisi skutecny
  // otvor od sparse/velkoplosneho panelu s malo vertexy). Pokud predni noha
  // (u prepazky) zasahuje do potvrzene mezery, posun ji za jeji vzdalenejsi
  // hranu + 30mm rezerva - stejny princip jako u ostatnich noh v STEP 3 nize.
  const dirAwayProbe = -dirZtoBulkhead;
  const doorGapCheck = confirmDoorGaps(engine, (cargoZlo + cargoZhi) / 2);
  const doorGaps = doorGapCheck.confirmed;
  P(`doorGapScan rawFound=${doorGapCheck.gapsRaw.length} CONFIRMED_real=${doorGaps.length} falsePositives=${doorGapCheck.rejected.length}`);
  const DOOR_CLEARANCE = 30;
  function overlapsAnyDoorGap(zLo, zHi) {
    for (const g of doorGaps) {
      const gLo = Math.min(g.near, g.far) - DOOR_CLEARANCE, gHi = Math.max(g.near, g.far) + DOOR_CLEARANCE;
      if (zLo <= gHi && zHi >= gLo) return g;
    }
    return null;
  }
  let frontAnchorZ = anchorZ; // predni noha zabira world Z in [frontAnchorZ, frontAnchorZ+T]
  const frontHit = overlapsAnyDoorGap(frontAnchorZ, frontAnchorZ + T);
  if (frontHit) {
    const farEdge = dirAwayProbe > 0 ? frontHit.far : frontHit.near;
    frontAnchorZ = farEdge + dirAwayProbe * DOOR_CLEARANCE;
    P(`step1b: predni noha zasahovala do dverni mezery (near=${frontHit.near.toFixed(1)} far=${frontHit.far.toFixed(1)}) - presunuto na anchorZ=${frontAnchorZ.toFixed(1)}`);
    if (collidesWithWalls(groupAt(plainParts0, offsetX, offsetY, frontAnchorZ))) throw new Error("step1b: novy anchor po posunu od dverni mezery jiz koliduje");
  }

  // ---- STEP 2: max rozpon - krokovat DAL od prepazky (opacny smer) 1mm do kolize,
  // 20mm zpet. Podbeh muze byt IZOLOVANY OSTROV (car_body_placement_methods.id=1 /
  // shape_geometry_methods.id=5 "pokracovani_pres_podbeh_k_realne_zadni_hranici") -
  // pri prvni kolizi se NEZASTAVUJEME, zkusime "preskocit" dal (lookahead) a pokud
  // se tam probe znovu uvolni, pokracujeme az k SKUTECNE posledni kolizi (fyzicky
  // roh/konec vozu), ne jen k prvnimu lokalnimu podbehu. Tenhle mechanismus
  // (island-lookahead na RIGIDNIM vyrez probe) zustava BEZE ZMENY - je to
  // samostatny, jinde uz osvedceny fix (napr. FO11, viz KAROSERIE_UMISTENI.md
  // "podbeh jako izolovany ostrov UPROSTRED korby") pro urceni VNEJSI hranice
  // rozpetí. Bug #2 ("podbeh bez konce", VW21/22/31/32, git commit 0ceb07f,
  // bot24) je JINY, konkretnejsi problem - viz oprava v STEP 3 nize.
  const dirAway = -dirZtoBulkhead;
  const vyrezPartsProbe = buildVyrezAtDepth(D);
  function groupAtAnchor(localParts, aZ) { return groupAt(localParts, offsetX, offsetY, aZ); }
  // Fyzicka hranice MODELOVANE geometrie steny L (dirAway smerem) - pokud
  // kolize neni nalezena ani zde, jde o vuz s rovnobeznymi stenami az k
  // plne OTEVRENEMU konci (zadny sloupek/roh, na ktery by raycasting narazil -
  // typicky kratsi Kombi/crew-van varianty) - v tom pripade je skutecnou
  // hranici primo konec modelovane geometrie, ne kolize.
  const hardEdgeZ = dirAway > 0 ? boxL0.max.z : boxL0.min.z;
  function findNextCollisionZ(fromZ, maxSteps) {
    let steps = 0, z = fromZ;
    while (steps < maxSteps) {
      const next = z + dirAway;
      const pastEdge = dirAway > 0 ? next > hardEdgeZ : next < hardEdgeZ;
      if (pastEdge) return { z: null, hitEdge: true };
      z = next; steps++;
      if (collidesWithWalls(groupAtAnchor(vyrezPartsProbe, z))) return { z, hitEdge: false };
    }
    return { z: null, hitEdge: false };
  }
  let cursor = frontAnchorZ;
  let lastCollisionZ = null;
  let openEndFallback = false;
  const MAXSTEPS2 = 5000, LOOKAHEAD_MAX = 2500, LOOKAHEAD_STEP = 50;
  for (let iter = 0; iter < 10; iter++) {
    const r = findNextCollisionZ(cursor, MAXSTEPS2);
    if (r.z === null) {
      if (r.hitEdge && lastCollisionZ === null) {
        // zadna kolize v CELE modelovane delce vozu - pouzij hranu modelu jako limit
        openEndFallback = true;
        lastCollisionZ = hardEdgeZ;
        break;
      }
      if (lastCollisionZ === null) throw new Error("step2: zadna kolize nalezena (rear boundary)");
      break; // za posledni potvrzenou kolizi uz neni nic - konec (byl to skutecny konec, ne ostrov)
    }
    const collisionZ = r.z;
    lastCollisionZ = collisionZ;
    let resumeZ = null;
    for (let jump = LOOKAHEAD_STEP; jump <= LOOKAHEAD_MAX; jump += LOOKAHEAD_STEP) {
      const testZ = collisionZ + dirAway * jump;
      const pastEdge = dirAway > 0 ? testZ > hardEdgeZ : testZ < hardEdgeZ;
      if (pastEdge) break;
      if (!collidesWithWalls(groupAtAnchor(vyrezPartsProbe, testZ))) { resumeZ = testZ; break; }
    }
    if (resumeZ === null) break; // zadne dalsi uvolneni v dohledu - tohle je skutecny konec
    // OVER, ze za resumeZ jeste skutecne existuje DALSI kolize (realna geometrie
    // vozu pokracuje) - jinak resumeZ uz je MIMO vuz (otevrene dvere/prazdny
    // prostor) a puvodni collisionZ byl skutecny konec, ne ostrov.
    const confirm = findNextCollisionZ(resumeZ, MAXSTEPS2);
    if (confirm.z === null) break; // resumeZ byl uz za koncem vozu - collisionZ je finalni
    P(`step2 island: kolize na Z=${collisionZ.toFixed(1)}, uvolneni potvrzeno dal na Z=${resumeZ.toFixed(1)} (dalsi kolize Z=${confirm.z.toFixed(1)}) - pokracuji`);
    cursor = resumeZ;
  }
  const BACKOFF = openEndFallback ? 20 : 20;
  const REAR_ANCHOR_Z = lastCollisionZ - dirAway * BACKOFF;
  if (!openEndFallback && collidesWithWalls(groupAtAnchor(vyrezPartsProbe, REAR_ANCHOR_Z))) throw new Error("step2: po 20mm zpet stale koliduje");
  P(`step2 OK REAR_ANCHOR_Z=${REAR_ANCHOR_Z.toFixed(1)} maxSpan=${Math.abs(REAR_ANCHOR_Z - frontAnchorZ).toFixed(1)} openEndFallback=${openEndFallback}`);

  // ---- STEP 3: sloupcove plneni, hladove nejsirsi-nejdriv, cela sestava ----
  //
  // OPRAVA (bug #2 "podbeh bez konce", 2026-09-03, sjednoceno z git commit
  // 0ceb07f / bot24, ktery tuhle opravu zavedl jen ve svem samostatnem
  // Caddy-specifickem skriptu): kandidatni test "vejde se sem vyrez noha?"
  // driv pouzival RIGIDNI buildVyrezAtDepth(D) s FIXNIM CUTOUT_H - spodni
  // dil "sloupek-pred-podbehem" tak VZDY sahal az k Y=0 na FIXNI hloubce
  // (D-WALL_CLEARANCE_ARCH), takze jakmile podbeh na dane Z presahl i tuhle
  // fixni polohu, kandidat se ZAMITL cely (i kdyz by se tam po protazeni
  // vesel), a hladove planovani sloupcu se KVULI TOMU predcasne zastavilo
  // (`if (!placed) break;`), i kdyz REAR_ANCHOR_Z (viz STEP2) dovoloval
  // pokracovat dal. Metodika shape_geometry_methods.id=6 rika: profil boci
  // (wall-side) strany nohy se ma prepocitat CERSTVE (0..strop sken) na
  // KAZDE kandidatni Z zvlast - tenhle vypocet uz driv delal jen az
  // dodatecne STEP 4 (PO umisteni), ted se pouziva uz PRI ROZHODOVANI,
  // jestli noha na danou Z pozici vubec patri (buildVyrezAtDepthExtended
  // s cerstvym Y_new misto rigidniho CUTOUT_H).
  function wallPieceAt(aZ, bottomY) {
    const lenY = TOP_Y - bottomY, centerY = (bottomY + TOP_Y) / 2;
    return buildLegObject([{
      position: [offsetX + sgn * (D - T / 2), centerY + offsetY, aZ + T / 2],
      quaternion: [0, 0, 0, 1], scale: [1, lenY / 1000, 1],
    }]);
  }
  function computeYNewWall(aZ) {
    // levny zkraceny test: pokud ANI cela vyska [0,TOP_Y] nekoliduje, neni
    // tu zadna prekazka a neni co pocitat (bezny pripad na rovne podlaze).
    if (!collidesWithWalls(wallPieceAt(aZ, 0))) return 0;
    let collisionBottomY = null;
    for (let bottomY = TOP_Y - 1; bottomY >= 0; bottomY--) {
      if (collidesWithWalls(wallPieceAt(aZ, bottomY))) { collisionBottomY = bottomY; break; }
    }
    if (collisionBottomY === null) return 0; // zadna kolize na cele vysce - podlaha je tu cista
    return collisionBottomY + podbehClearanceMm;
  }
  // OPRAVA (bug #5 "noha zaborena do podlahoveho hrbu podbehu", MB47,
  // 2026-09-03, sjednoceno z bot24 caddy fix `sloupekPieceAt`): stejny
  // princip jako computeYNewWall vyse, ale na X pozici SLOUPKU (D-
  // WALL_CLEARANCE_ARCH-T/2, 124mm od steny), ne na wall-side X - podbeh
  // muze zasahovat i tady, ne jen primo u steny. Driv se pata sloupku VZDY
  // predpokladala na Y=0 (rovna podlaha), i kdyz realna podlaha uz na jeho
  // konkretni X/Z pozici zacala stoupat (30mm zaboreni na MB47).
  const sloupekColX = (buildVyrezAtDepth(D).find(p => p.role === "sloupek-pred-podbehem") || {}).position;
  function sloupekPieceAt(aZ, bottomY, topY) {
    if (!sloupekColX) return { updateMatrixWorld() {}, traverse() {} }; // D <= WALL_CLEARANCE_ARCH+2T: sloupek neexistuje
    const lenY = topY - bottomY, centerY = (bottomY + topY) / 2;
    return buildLegObject([{
      position: [offsetX + sgn * sloupekColX[0], centerY + offsetY, aZ + T / 2],
      quaternion: [0, 0, 0, 1], scale: [1, lenY / 1000, 1],
    }]);
  }
  function computeSloupekBottom(aZ, yNewWall) {
    if (!sloupekColX || yNewWall <= 0) return 0;
    if (!collidesWithWalls(sloupekPieceAt(aZ, 0, yNewWall))) return 0; // podlaha tu je cista, pata muze zustat na 0
    let collisionBottomY = null;
    for (let bottomY = yNewWall - 1; bottomY >= 0; bottomY--) {
      if (collidesWithWalls(sloupekPieceAt(aZ, bottomY, yNewWall))) { collisionBottomY = bottomY; break; }
    }
    if (collisionBottomY === null) return 0;
    return Math.min(collisionBottomY + podbehClearanceMm, yNewWall - 1);
  }
  function legPartsFor(type, yNew, sloupekBottom) { return type === "vyrez" ? buildVyrezAtDepthExtended(D, yNew != null ? yNew : CUTOUT_H, sloupekBottom) : buildPlainAtDepth(D); }
  const legs = [{ type: "plain", anchorZ: frontAnchorZ, yNew: null, sloupekBottom: 0 }];
  const columns = [];
  function railsAndConnectorsForColumn(N, legFrom, legTo) {
    const zFromRaw = legFrom.anchorZ + dirAway * T, zToRaw = legTo.anchorZ;
    const railZFrom = Math.min(zFromRaw, zToRaw), railZTo = Math.max(zFromRaw, zToRaw);
    const railLen = railZTo - railZFrom, railZCenter = (railZFrom + railZTo) / 2;
    const crossLen = D - 2 * T, crossXCenter = D / 2;
    const Y = 410;
    const parts = [];
    parts.push({ part_id: "Object_7", position: [offsetX + sgn * (T / 2), Y + offsetY, railZCenter], quaternion: Q_ALONG_Z, scale: [1, railLen / 1000, 1], role: "nosnik" });
    parts.push({ part_id: "Object_7", position: [offsetX + sgn * (D - T / 2), Y + offsetY, railZCenter], quaternion: Q_ALONG_Z, scale: [1, railLen / 1000, 1], role: "nosnik" });
    CONNECTOR_POS[N].forEach(localZ => {
      const zc = railZFrom + (dirAway > 0 ? localZ : (railLen - localZ));
      parts.push({ part_id: "Object_7", position: [offsetX + sgn * crossXCenter, Y + offsetY, zc], quaternion: Q_ALONG_X, scale: [1, crossLen / 1000, 1], role: "spojnice" });
    });
    return { parts, railZFrom, railZTo };
  }
  function wholeAssemblyParts() {
    let parts = [];
    legs.forEach(leg => { parts.push(...toWorld(legPartsFor(leg.type, leg.yNew, leg.sloupekBottom), offsetX, offsetY, leg.anchorZ)); });
    columns.forEach(col => { parts.push(...railsAndConnectorsForColumn(col.N, legs[col.legFromIdx], legs[col.legToIdx]).parts); });
    return parts;
  }
  function assemblyCollides(extra) { return collidesWithWalls(buildLegObject([...wholeAssemblyParts(), ...(extra || [])])); }

  // Typ nohy se NESMI urcovat podle poradi (viz car_body_placement_methods.id=1
  // "podbeh_muze_byt_izolovany_ostrov_2026_08_31") - test se skutecnou kolizi
  // PLNE nohy na dane Z pozici: pokud plna noha nekoliduje, pouzij ji (jednodussi,
  // zadny podbeh tam neni); jen pokud plna koliduje, pouzij vyrez (s naslednym
  // fresh protazenim v kroku 4).
  function determineLegType(anchorZ) {
    const plainParts = toWorld(buildPlainAtDepth(D), offsetX, offsetY, anchorZ);
    return collidesWithWalls(buildLegObject(plainParts)) ? "vyrez" : "plain";
  }

  let colIdx = 0;
  while (true) {
    const lastLeg = legs[legs.length - 1];
    let placed = false;
    for (const N of WIDTH_TRY_ORDER) {
      const clear = CLEAR_SPACING[N];
      const newAnchorZ = lastLeg.anchorZ + dirAway * (T + clear);
      const beyond = dirAway > 0 ? newAnchorZ > REAR_ANCHOR_Z : newAnchorZ < REAR_ANCHOR_Z;
      if (beyond) continue;
      // bug #4: zamitni kandidatni nohu, pokud by jeji Z-slab spadl do
      // potvrzene dverni mezery (viz STEP 1b vyse) - platí pro KAZDOU nohu,
      // ne jen prvni.
      if (overlapsAnyDoorGap(Math.min(newAnchorZ, newAnchorZ + T), Math.max(newAnchorZ, newAnchorZ + T))) continue;
      const candidateType = determineLegType(newAnchorZ);
      const candidateYNew = candidateType === "vyrez" ? computeYNewWall(newAnchorZ) : null;
      const candidateSloupekBottom = candidateType === "vyrez" ? computeSloupekBottom(newAnchorZ, candidateYNew) : 0;
      const candidateLeg = { type: candidateType, anchorZ: newAnchorZ, yNew: candidateYNew, sloupekBottom: candidateSloupekBottom };
      const candidateLegParts = toWorld(legPartsFor(candidateType, candidateYNew, candidateSloupekBottom), offsetX, offsetY, newAnchorZ);
      const railParts = railsAndConnectorsForColumn(N, lastLeg, candidateLeg).parts;
      if (!assemblyCollides([...candidateLegParts, ...railParts])) {
        legs.push(candidateLeg);
        columns.push({ N, legFromIdx: legs.length - 2, legToIdx: legs.length - 1 });
        placed = true;
        break;
      }
    }
    if (!placed) break;
    colIdx++;
    if (colIdx > 20) break;
  }
  P(`step3 OK legs=${legs.length} columns=${columns.length} N=[${columns.map(c => c.N).join(",")}]`);
  if (columns.length === 0) {
    return { ok: false, reason: "zadny sloupec se nevejde (jen 1 predni noha, nulovy rozpon pro luzko)", log };
  }

  // ---- STEP 4: protazeni vyrez noh ----
  // OPRAVA (bug #2): Y_new uz byl spocitan CERSTVE (fresh 0..TOP_Y sken,
  // computeYNewWall) v okamziku umisteni kazde nohy v STEP 3 - tady uz jen
  // znovu overujeme (bezpecnostni sit), ze na FINALNI pozici porad plati, misto
  // aby se prepocitaval NAVIC (a jinak/uzeji, jen 0..CUTOUT_H) - dve nezavisle
  // implementace stejneho vypoctu by se casem mohly rozejit.
  function buildPiece(bottomY, anchorZ) {
    const lenY = TOP_Y - bottomY;
    const centerY = (bottomY + TOP_Y) / 2 + offsetY;
    const xw = offsetX + sgn * (D - T / 2);
    return { part_id: "Object_7", position: [xw, centerY, anchorZ + T / 2], quaternion: [0, 0, 0, 1], scale: [1, lenY / 1000, 1], role: "zadni-svislice-nad-zarezem" };
  }
  const step4 = {};
  legs.forEach((leg, i) => {
    if (leg.type !== "vyrez") return;
    const Y_NEW = leg.yNew;
    if (collidesWithWalls(buildLegObject([buildPiece(Y_NEW, leg.anchorZ)]))) throw new Error(`step4 leg${i}: Y_new=${Y_NEW} koliduje na finalni pozici`);
    step4[i] = { Y_new: Y_NEW, sloupekBottom: leg.sloupekBottom || 0 };
  });
  P(`step4 OK ${JSON.stringify(step4)}`);

  // ---- STEP 5: rail floor pres celý span (fresh krokovani nahoru) ----
  // Pravidlo 5 (shape_geometry_methods.id=3, plna_noha_bez_podbehu_floor_200mm):
  // sloupec BEZ zadne vyrez nohy na obou koncich ma floor VZDY 200mm (prakticka
  // konstanta, ne geometricky odvozeny limit). Sloupec s alespon jednou vyrez
  // nohou pouziva jeji skutecne (kolizne zjistene) Y_new.
  function columnFloorBase(legFromIdx, legToIdx) {
    const fromV = legs[legFromIdx].type === "vyrez", toV = legs[legToIdx].type === "vyrez";
    if (!fromV && !toV) return 200;
    const vals = [];
    if (fromV) vals.push(step4[legFromIdx].Y_new);
    if (toV) vals.push(step4[legToIdx].Y_new);
    return Math.max(...vals);
  }
  const step5 = {};
  columns.forEach((col, colIdx) => {
    const legFrom = legs[col.legFromIdx], legTo = legs[col.legToIdx];
    const floorLegBased = columnFloorBase(col.legFromIdx, col.legToIdx);
    let Y0 = floorLegBased + T / 2;
    const railParts0 = railsAndConnectorsForColumn(col.N, legFrom, legTo).parts.map(p => ({ ...p, position: [p.position[0], Y0 + offsetY, p.position[2]] }));
    let finalFloor = floorLegBased;
    if (collidesWithWalls(buildLegObject(railParts0))) {
      let Y = Y0, s = 0, cleared = null;
      while (s < 600) {
        Y += 1; s++;
        const rp = railsAndConnectorsForColumn(col.N, legFrom, legTo).parts.map(p => ({ ...p, position: [p.position[0], Y + offsetY, p.position[2]] }));
        if (!collidesWithWalls(buildLegObject(rp))) { cleared = Y; break; }
      }
      if (cleared === null) throw new Error(`step5 col${colIdx}: nenalezena bezkolizni pozice`);
      const withMargin = cleared + 20;
      const rpFinal = railsAndConnectorsForColumn(col.N, legFrom, legTo).parts.map(p => ({ ...p, position: [p.position[0], withMargin + offsetY, p.position[2]] }));
      if (collidesWithWalls(buildLegObject(rpFinal))) throw new Error(`step5 col${colIdx}: i po +20mm koliduje`);
      finalFloor = withMargin - T / 2;
    }
    step5[colIdx] = { finalFloorY: finalFloor };
  });
  P(`step5 OK ${JSON.stringify(step5)}`);

  // ---- STEP 7: strop (fresh, cela hloubka D sonda) ----
  const step7 = {};
  columns.forEach((col, colIdx) => {
    const legFrom = legs[col.legFromIdx], legTo = legs[col.legToIdx];
    const zFromRaw = legFrom.anchorZ + dirAway * T, zToRaw = legTo.anchorZ;
    const zFrom = Math.min(zFromRaw, zToRaw), zTo = Math.max(zFromRaw, zToRaw);
    function slab(y) {
      const geo = new THREE.BoxGeometry(D, 10, zTo - zFrom);
      const mesh = new THREE.Mesh(geo);
      mesh.position.set(offsetX + sgn * (D / 2), y, (zFrom + zTo) / 2);
      mesh.updateMatrixWorld(true);
      return mesh;
    }
    let y = 900, s = 0, collisionY = null;
    while (s < 500) {
      y += 1; s++;
      if (collidesWithWalls(slab(y))) { collisionY = y; break; }
    }
    if (collisionY === null) throw new Error(`step7 col${colIdx}: zadna kolize do Y=${y}`);
    const safeY = collisionY - 2;
    if (collidesWithWalls(slab(safeY))) throw new Error(`step7 col${colIdx}: po 2mm zpet stale koliduje`);
    step7[colIdx] = { maxSafeBoxTop: safeY };
  });
  P(`step7 OK ${JSON.stringify(step7)}`);

  // ---- vyska pater: >=3 z {120,170,220,270} pres celou sestavu, nerostouci na sloupec ----
  // OPRAVA (bug #1, +12mm mezera): eurobox ma 12mm "nozku" (nesting foot), ktera
  // zapada 12mm POD rail top (viz probeFor/eurobox pozicovani nize, "-12" ve
  // vzorci Y). Viditelna vyska boxu NAD rail top je tedy H_box-12, NE plna
  // deklarovana H_box - pouziti plne H_box v kroku dalsiho patra davalo KAZDE
  // mezere +12mm navic (nalezeno retroaktivne v datech noc 2026-08-31/09-01,
  // kaskadovy prepocet 115 radku - viz KOMPONENTY_EUROBOXY.md "Univerzalni
  // +12mm chyba"). Spravny vzorec: Y_rail_top(N+1) = Y_rail_top(N) +
  // (H_box(N)-12) + 30mm(mezera) + T(30mm, tloustka railu).
  const NEST_FOOT = 12;
  const HEIGHTS_DESC = [270, 220, 170, 120];
  function planColumn(floorY, physCeil, mixed) {
    let railTop = floorY + T;
    const heights = [];
    if (mixed) {
      let hi = 0;
      while (true) {
        const isFirst = heights.length === 0;
        // zkus sestupne od aktualni pozice v HEIGHTS_DESC
        let placedH = null, placedK = null;
        for (let k = hi; k < HEIGHTS_DESC.length; k++) {
          const boxH = HEIGHTS_DESC[k];
          const top = railTop + (boxH - NEST_FOOT);
          if (top <= TOP_Y + 1e-6) { placedH = boxH; placedK = k; break; }
        }
        if (placedH === null) break;
        // pokrocit na dalsi (mensi) vysku pristi patro, dokud nedojdeme na nejmensi
        // (120) - zajisti DIVERZITU (>=3 z 4 vysek) misto opakovani stejne vysky.
        hi = Math.min(placedK + 1, HEIGHTS_DESC.length - 1);
        heights.push(placedH);
        railTop = railTop + (placedH - NEST_FOOT) + 30 + T;
      }
    } else {
      while (railTop + (120 - NEST_FOOT) <= TOP_Y + 1e-6) { heights.push(120); railTop = railTop + (120 - NEST_FOOT) + 30 + T; }
    }
    // top level: zkus vymenit posledni box za vetsi, pokud physCeil dovoli (pravidlo 7 -
    // presah) - JEN pro NE-mixed (uniformni max-pocet) sloupce: diverzita (pravidlo 6,
    // "diverzita ma prednost pred cistym poctem") se timhle NESMI prepsat zpet na
    // uniformni vysku u sloupce, ktery ji zamerne zavadi.
    if (!mixed && heights.length > 0) {
      const beforeTopRailTop = railTop - ((heights[heights.length - 1] - NEST_FOOT) + 30 + T);
      for (const boxH of HEIGHTS_DESC) {
        if (boxH < heights[heights.length - 1]) break;
        if (beforeTopRailTop + (boxH - NEST_FOOT) <= physCeil + 1e-6) { heights[heights.length - 1] = boxH; break; }
      }
    } else if (heights.length === 0 && floorY + T + (120 - NEST_FOOT) <= physCeil + 1e-6) {
      // ani jedno normalni patro se nevejde pod TOP_Y, ale pod physCeil ano - 1 patro
      for (const boxH of HEIGHTS_DESC) {
        if (floorY + T + (boxH - NEST_FOOT) <= physCeil + 1e-6) { heights.push(boxH); break; }
      }
    }
    return heights;
  }
  const columnHeights = columns.map((col, i) => planColumn(step5[i].finalFloorY, step7[i].maxSafeBoxTop, i === columns.length - 1));
  let distinct = new Set(columnHeights.flat());
  if (distinct.size < 3 && columns.length >= 1) {
    // force mixed na VSECH sloupcich dokud nemame >=3 distinct (best-effort)
    for (let i = 0; i < columns.length && distinct.size < 3; i++) {
      columnHeights[i] = planColumn(step5[i].finalFloorY, step7[i].maxSafeBoxTop, true);
      distinct = new Set(columnHeights.flat());
    }
  }
  P(`heights OK ${JSON.stringify(columnHeights)} distinct=${[...distinct]}`);

  if (columnHeights.every(h => h.length === 0)) {
    return { ok: false, reason: "sloupce nalezeny, ale zadne patro se pod zadny strop nevejde", log };
  }

  // ---- sestaveni vsech dilu (nohy+endcapy, nosniky+spojnice, euroboxy+endcapy) ----
  function legEndcapRoles(type) { return type === "vyrez" ? ["predni-svislice", "zadni-svislice-nad-zarezem", "cap"] : ["predni-svislice", "zadni-svislice-dolni", "cap"]; }
  function topEndcapsFor(legParts, roles) {
    return legParts.filter(p => roles.includes(p.role)).map(p => {
      const lenMm = p.scale[1] * 1000;
      const topY = p.position[1] + lenMm / 2 + CAP_FLANGE_THICKNESS;
      return { part_id: "product_3071", position: [p.position[0], topY, p.position[2]], quaternion: Q_ENDCAP_UP, scale: [1, 1, 1], role: "zaslepka" };
    });
  }
  let allParts = [];
  legs.forEach((leg, i) => {
    let localParts = leg.type === "plain" ? buildPlainAtDepth(D) : buildVyrezAtDepthExtended(D, step4[i].Y_new, step4[i].sloupekBottom);
    const world = toWorld(localParts, offsetX, offsetY, leg.anchorZ);
    const endcaps = topEndcapsFor(world, legEndcapRoles(leg.type));
    allParts.push(...world, ...endcaps);
  });

  const columnSummaries = [];
  columns.forEach((col, colIdx) => {
    const legFrom = legs[col.legFromIdx], legTo = legs[col.legToIdx];
    const floorY = step5[colIdx].finalFloorY;
    const physCeil = step7[colIdx].maxSafeBoxTop;
    const heights = columnHeights[colIdx];
    const zFromRaw = legFrom.anchorZ + dirAway * T, zToRaw = legTo.anchorZ;
    const railZFrom = Math.min(zFromRaw, zToRaw), railZTo = Math.max(zFromRaw, zToRaw);
    const railLen = railZTo - railZFrom, railZCenter = (railZFrom + railZTo) / 2;
    const crossLen = D - 2 * T, crossXCenter = D / 2;

    let railTop = floorY + T;
    const levels = [];
    heights.forEach((boxH, levelIdx) => {
      const railYCenter = railTop - T / 2;
      const boxTop = railTop + (boxH - NEST_FOOT);
      levels.push({ railYCenter, boxH, boxTop });
      railTop = railTop + (boxH - NEST_FOOT) + 30 + T;
    });

    levels.forEach((level, levelIdx) => {
      const Y = level.railYCenter;
      allParts.push({ part_id: "Object_7", position: [offsetX + sgn * (T / 2), Y + offsetY, railZCenter], quaternion: Q_ALONG_Z, scale: [1, railLen / 1000, 1], role: `nosnik-sloupec${colIdx}-patro${levelIdx}` });
      allParts.push({ part_id: "Object_7", position: [offsetX + sgn * (D - T / 2), Y + offsetY, railZCenter], quaternion: Q_ALONG_Z, scale: [1, railLen / 1000, 1], role: `nosnik-sloupec${colIdx}-patro${levelIdx}` });
      const positions = CONNECTOR_POS[col.N].map(z => dirAway > 0 ? z : (railLen - z));
      positions.slice().sort((a, b) => a - b).forEach(localZ => {
        allParts.push({ part_id: "Object_7", position: [offsetX + sgn * crossXCenter, Y + offsetY, railZFrom + localZ], quaternion: Q_ALONG_X, scale: [1, crossLen / 1000, 1], role: `spojnice-sloupec${colIdx}-patro${levelIdx}` });
      });
      const sortedPos = positions.slice().sort((a, b) => a - b);
      for (let i = 0; i < sortedPos.length - 1; i++) {
        allParts.push({
          part_id: EUROBOX_PID[level.boxH], position: [0, 0, 0], quaternion: Q_ALONG_Z, scale: [1, 1, 1], role: `eurobox-sloupec${colIdx}-patro${levelIdx}`,
          _pending: { slotZFrom: railZFrom + sortedPos[i], slotZTo: railZFrom + sortedPos[i + 1], railYCenter: Y + offsetY, boxH: level.boxH },
        });
      }
    });
    columnSummaries.push({ colIdx, N: col.N, floorY, physCeil, levels: levels.length, boxHeights: levels.map(l => l.boxH), totalBoxes: col.N * levels.length, railZFrom, railZTo });
  });

  // eurobox presne umisteni (dynamicky probe stred/min.y kazdeho GLB)
  const probeCache = {};
  function probeFor(h) {
    if (probeCache[h]) return probeCache[h];
    const m = engine.parseGlbMesh(EUROBOX_GLB[h]);
    m.position.set(0, 0, 0); m.quaternion.set(...Q_ALONG_Z); m.scale.set(1, 1, 1);
    m.updateMatrixWorld(true);
    const b = new THREE.Box3().setFromObject(m);
    const center = [(b.min.x + b.max.x) / 2, (b.min.y + b.max.y) / 2, (b.min.z + b.max.z) / 2];
    return (probeCache[h] = { box: b, center });
  }
  const targetXcenter = offsetX + sgn * (D / 2);
  allParts.forEach(p => {
    if (!p._pending) return;
    const { slotZFrom, slotZTo, railYCenter, boxH } = p._pending;
    const probe = probeFor(boxH);
    const targetZcenter = (slotZFrom + slotZTo) / 2;
    const targetYbottom = railYCenter + T / 2;
    p.position = [targetXcenter - probe.center[0], targetYbottom - probe.box.min.y - 12, targetZcenter - probe.center[2]];
    p.quaternion = [...Q_ALONG_Z];
    delete p._pending;
  });

  // ---- kontrola kolize s karoserii: profily ----
  const profileParts = allParts.filter(p => p.part_id === "Object_7");
  if (collidesWithWalls(buildLegObject(profileParts))) {
    const bad = [];
    profileParts.forEach((p) => { if (collidesWithWalls(buildLegObject([p]))) bad.push({ role: p.role, position: p.position }); });
    return { ok: false, reason: "KOLIZE profilu s karoserii po sestaveni: " + JSON.stringify(bad).slice(0, 500), log };
  }
  // euroboxy
  function glbFor(id) {
    if (id === "Object_7") return KAT + "Object_7.glb";
    if (id === "product_3071") return ENDCAP;
    for (const h in EUROBOX_PID) if (EUROBOX_PID[h] === id) return EUROBOX_GLB[h];
    return null;
  }
  function meshOf(p) { const m = engine.parseGlbMesh(glbFor(p.part_id)); m.position.set(...p.position); m.quaternion.set(...p.quaternion); m.scale.set(...p.scale); m.updateMatrixWorld(true); return m; }
  const euroboxParts = allParts.filter(p => p.part_id.startsWith("product_37"));
  for (const p of euroboxParts) {
    const grp = new THREE.Group(); grp.add(meshOf(p)); grp.updateMatrixWorld(true);
    if (collidesWithWalls(grp)) return { ok: false, reason: "EUROBOX koliduje s karoserii: " + p.role, log };
  }

  // self-kolize
  const meshes = allParts.map(meshOf);
  let unexpected = 0;
  const unexpectedDetails = [];
  for (let i = 0; i < meshes.length; i++) for (let j = i + 1; j < meshes.length; j++) {
    const A = new THREE.Box3().setFromObject(meshes[i]), B = new THREE.Box3().setFromObject(meshes[j]);
    const ox = Math.min(A.max.x, B.max.x) - Math.max(A.min.x, B.min.x);
    const oy = Math.min(A.max.y, B.max.y) - Math.max(A.min.y, B.min.y);
    const oz = Math.min(A.max.z, B.max.z) - Math.max(A.min.z, B.min.z);
    if (ox > 0.5 && oy > 0.5 && oz > 0.5) {
      const nestOk = allParts[i].part_id !== "Object_7" || allParts[j].part_id !== "Object_7";
      if (!nestOk) { unexpected++; unexpectedDetails.push([allParts[i].role, allParts[j].role]); }
    }
  }
  if (unexpected > 0) return { ok: false, reason: "neocekavana self-kolize: " + JSON.stringify(unexpectedDetails).slice(0, 500), log };

  const clean = allParts.map(({ _pending, ...rest }) => rest);
  // OPRAVA (bug #3 "Y-offset regrese", VW31, 2026-09-03): sanity-check pred
  // zapisem - dily regalu (cokoliv KROME part_id zacinajiciho "car_body_")
  // jsou VZDY ve vlastnich "podlaha=Y0" souradnicich assembly a nikdy nesmi
  // vyjit mimo rozumne rozmezi. U VW31 vysly nohy/boxy/ramy na Y~1650mm
  // (misto ocekavaneho ~0-1200mm), protoze GLB karoserie ma neobvykly raw
  // Y-bbox (1641-2881 misto typickych 0-1200) - throw misto ticheho zapisu
  // spatnych dat, i kdyz presna prvotni pricina (chybejici normalizace
  // raw-GLB souradnic v createEngine, viz TASKS.md) zustava otevrena.
  assertSaneRackYPositions(clean);
  const totalBoxes = columnSummaries.reduce((s, c) => s + c.totalBoxes, 0);
  const distinctHeights = [...new Set(columnSummaries.flatMap(c => c.boxHeights))].sort((a, b) => b - a);
  P(`FINAL OK totalBoxes=${totalBoxes} distinctHeights=${distinctHeights} legs=${legs.length} columns=${columns.length}`);

  return {
    ok: true, parts: clean, columnSummaries, totalBoxes, distinctHeights,
    legs: legs.length, columns: columns.length, offsetX, offsetY, mirror, dirZtoBulkhead,
    D, T, H, log,
  };
}

module.exports = { runPipeline, D, T, H, assertSaneRackYPositions };
