// Genericky finalni assembler pro JEDNU ProAce karoserii - port
// tmp_2026-08-31_vivaro_build_full.js, parametrizovano vysledkem
// proace_run_one.js (step1-7) + height-planner (proace_heights.js).
// Pouziti: node 2026-08-31_proace_full_build.js <runOneResult.json> <out.json>
const fs = require("fs");
const THREE = require("three");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const { loadVehicle } = require("/opt/konfigurator/scripts/2026-08-31_proace_walls.js");
const LEG = require("/opt/konfigurator/scripts/2026-08-31_proace_leg_builder.js");
const { planColumn, diversify, HEIGHTS_DESC } = require("/opt/konfigurator/scripts/2026-08-31_proace_heights.js");
// Volitelna 4. CLI arg = varianta mixu vysek boxu (bot22 2026-09-05). Bez ni default (puvodni chovani).
const HEIGHTS_VARIANT = ({ A: [270, 220, 170, 120], B: [220, 170, 120], C: [170, 120] })[process.argv[4]] || HEIGHTS_DESC;

const KAT = "/opt/konfigurator/webapp/katalog/";
const OBJ7 = KAT + "Object_7.glb";
const ENDCAP = KAT + "product_3071.glb";
const EUROBOX_GLB = { 120: KAT + "product_3788.glb", 170: KAT + "product_3793.glb", 220: KAT + "product_3794.glb", 270: KAT + "product_3795.glb" };
const EUROBOX_PID = { 120: "product_3788", 170: "product_3793", 220: "product_3794", 270: "product_3795" };
const CONNECTOR_POS = { 1: [15, 415], 2: [15, 415, 816], 3: [15, 415, 816, 1217] };
const Q_ALONG_Z = [-0.707107, 0, 0, 0.707107];
const Q_ALONG_X = [0, 0, -0.707107, 0.707107];
const Q_ENDCAP_UP = [0.7071067811865475, 0, 0, 0.7071067811865475];
const CAP_FLANGE_THICKNESS = 3;

function buildFull(step, columnsLevelsOverride) {
  const { cfg, offsetX, offsetY, legs, columns, yNewByLeg, floorByCol, ceilByCol, TOP_Y } = step;
  const { D, H, T, CUTOUT_H, CAP_H } = cfg;
  const opts = { T, CAP_H };
  const V = loadVehicle(cfg.base);

  function toWorld(localParts, anchorZ) {
    return localParts.map(p => ({
      part_id: p.part_id || "Object_7",
      position: [offsetX - p.position[0], p.position[1] + offsetY, anchorZ + p.position[2]],
      quaternion: p.quaternion, scale: p.scale, role: p.role,
    }));
  }

  // 1. nohy + endcapy
  //
  // POZOR (bot8, 2026-09-11, nalezeno pri opravach 9 sestav se zanorenim):
  // TAHLE FUNKCE NEGENERUJE UHELNIKY (rohove spojky noha<->kolejnicka,
  // role "uhelnik-nohaN", part_id product_3045). `result.parts` ma jen
  // profily (Object_7) + endcapy (product_3071) + eurobox/nosnik/spojnice.
  // Uhelniky se pridavaji AZ POTOM, samostatnym prochodem pres
  // `2026-09-01_uhelniky_leg_joints_lib.js::applyUhelnikyToLeg()` (viz
  // 2026-09-05_add_uhelniky_all_legs.js pro hotovy vzor volani - seskupi
  // profily nohy podle Z, zavola applyUhelnikyToLeg na kazdou nohu).
  // Kdyz pouzijes vystup teto funkce primo (bez tohohle dalsiho kroku),
  // sestava bude geometricky OK, ale bude chybet cely uhelnikovy hardware -
  // presne tenhle omyl se stal v prvnim pokusu o opravu 59/60/63/64.
  let allParts = [];
  legs.forEach((leg, i) => {
    let localParts;
    if (leg.type === "plain") localParts = LEG.buildPlainAtDepth(D, H, opts);
    else localParts = LEG.buildVyrezAtDepthExtended(D, H, CUTOUT_H, yNewByLeg[i], opts);
    const roles = LEG.legEndcapRoles(leg.type);
    const endcaps = LEG.topEndcapsFor(localParts, roles, CAP_FLANGE_THICKNESS);
    allParts.push(...toWorld([...localParts, ...endcaps], leg.anchorZ));
  });

  // 2. height plan per column (+diversity pass napric sloupci)
  //
  // `columnsLevelsOverride` (bot8 2026-09-11, zadani bot3): planColumn()+
  // diversify() jsou "na kazde patro nejvyssi vyska co se vejde", ne
  // "vyrob presne tenhle mix" (overeno spustenim, viz komentar u
  // planColumnExact() v 2026-08-31_proace_heights.js). Kdyz existujici
  // B/C/D/E varianta potrebuje PRESNE predepsanou skladbu (napr. po
  // oprave karoserie), volajici ji spocita sam pres planColumnExact() a
  // preda sem hotovou - tahle funkce uz nic nevybira, jen ji pouzije.
  const columnsLevels = columnsLevelsOverride
    || columns.map((col, ci) => planColumn(floorByCol[ci], TOP_Y, ceilByCol[ci], T, HEIGHTS_VARIANT));
  if (!columnsLevelsOverride) {
    const limits = columns.map((col, ci) => ({ TOP_Y, physCeil: ceilByCol[ci] }));
    diversify(columnsLevels, limits, HEIGHTS_VARIANT);
  }

  // 3. rails/connectors/euroboxy per column/level
  const columnSummaries = [];
  columns.forEach((col, colIdx) => {
    const legFrom = legs[col.legFromIdx], legTo = legs[col.legToIdx];
    const railZFrom = legFrom.anchorZ + T, railZTo = legTo.anchorZ;
    const railLen = railZTo - railZFrom, railZCenter = (railZFrom + railZTo) / 2;
    const crossLen = D - 2 * T, crossXCenter = D / 2;
    const levels = columnsLevels[colIdx];
    levels.forEach((level, levelIdx) => {
      const Y = level.railYCenter;
      allParts.push({ part_id: "Object_7", position: [offsetX - T / 2, Y + offsetY, railZCenter], quaternion: Q_ALONG_Z, scale: [1, railLen / 1000, 1], role: `nosnik-sloupec${colIdx}-patro${levelIdx}` });
      allParts.push({ part_id: "Object_7", position: [offsetX - (D - T / 2), Y + offsetY, railZCenter], quaternion: Q_ALONG_Z, scale: [1, railLen / 1000, 1], role: `nosnik-sloupec${colIdx}-patro${levelIdx}` });
      CONNECTOR_POS[col.N].forEach(localZ => {
        allParts.push({ part_id: "Object_7", position: [offsetX - crossXCenter, Y + offsetY, railZFrom + localZ], quaternion: Q_ALONG_X, scale: [1, crossLen / 1000, 1], role: `spojnice-sloupec${colIdx}-patro${levelIdx}` });
      });
      const positions = CONNECTOR_POS[col.N];
      for (let i = 0; i < positions.length - 1; i++) {
        allParts.push({
          part_id: EUROBOX_PID[level.boxH], position: [0, 0, 0], quaternion: Q_ALONG_Z, scale: [1, 1, 1], role: `eurobox-sloupec${colIdx}-patro${levelIdx}`,
          _pending: { slotZFrom: railZFrom + positions[i], slotZTo: railZFrom + positions[i + 1], railYCenter: Y + offsetY, boxH: level.boxH },
        });
      }
    });
    columnSummaries.push({ colIdx, N: col.N, floorY: floorByCol[colIdx], physCeil: ceilByCol[colIdx], levels: levels.length, boxHeights: levels.map(l => l.boxH), totalBoxes: col.N * levels.length, railZFrom, railZTo, railLen });
  });

  // 4. eurobox presne umisteni (dynamicky probe, ruzne pivoty dle product 3793!)
  const probeCache = {};
  function probeFor(h) {
    if (probeCache[h]) return probeCache[h];
    const m = parseGlbMesh(EUROBOX_GLB[h]);
    m.position.set(0, 0, 0); m.quaternion.set(...Q_ALONG_Z); m.scale.set(1, 1, 1);
    m.updateMatrixWorld(true);
    const b = new THREE.Box3().setFromObject(m);
    const center = [(b.min.x + b.max.x) / 2, (b.min.y + b.max.y) / 2, (b.min.z + b.max.z) / 2];
    return (probeCache[h] = { box: b, center });
  }
  const targetXcenter = offsetX - D / 2;
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

  // 5. kontrola kolize s karoserii (profily)
  const profileParts = allParts.filter(p => p.part_id === "Object_7");
  const carCollisionProfiles = V.collidesWithWalls(V.buildLegObject(profileParts));

  function glbFor(id) {
    if (id === "Object_7") return OBJ7;
    if (id === "product_3071") return ENDCAP;
    for (const h in EUROBOX_PID) if (EUROBOX_PID[h] === id) return EUROBOX_GLB[h];
    return null;
  }
  function meshOf(p) { const m = parseGlbMesh(glbFor(p.part_id)); m.position.set(...p.position); m.quaternion.set(...p.quaternion); m.scale.set(...p.scale); m.updateMatrixWorld(true); return m; }
  const euroboxParts = allParts.filter(p => p.part_id.startsWith("product_37"));
  let euroboxCarCollision = false;
  const badEurobox = [];
  euroboxParts.forEach(p => {
    const grp = new THREE.Group(); grp.add(meshOf(p)); grp.updateMatrixWorld(true);
    if (V.collidesWithWalls(grp)) { euroboxCarCollision = true; badEurobox.push({ role: p.role, position: p.position }); }
  });

  // 6. self-kolize (jen presah, ne dotyk)
  const meshes = allParts.map(meshOf);
  let unexpected = 0, expected = 0;
  const badPairs = [];
  for (let i = 0; i < meshes.length; i++) for (let j = i + 1; j < meshes.length; j++) {
    const A = new THREE.Box3().setFromObject(meshes[i]), B = new THREE.Box3().setFromObject(meshes[j]);
    const ox = Math.min(A.max.x, B.max.x) - Math.max(A.min.x, B.min.x);
    const oy = Math.min(A.max.y, B.max.y) - Math.max(A.min.y, B.min.y);
    const oz = Math.min(A.max.z, B.max.z) - Math.max(A.min.z, B.min.z);
    if (ox > 0.5 && oy > 0.5 && oz > 0.5) {
      // OPRAVA (bot8 2026-09-11, nalezeno pri nezavislem overeni fronty ke
      // schvalovani - Robert pres bot3): puvodni pravidlo "nestOk = aspon
      // jedna strana neni Object_7" bylo moc siroke. Melo zachytit JEN dva
      // SKUTECNE zamerne prekryvy:
      //   (a) zaslepka (product_3071) nasazena DO sveho hostitelskeho
      //       profilu (predni-svislice/cap/zadni-svislice-*) - navrzeny
      //       tesny prekryv, spravne "expected"
      //   (b) eurobox (product_37xx) vuci VLASTNI kolejnicce (nosnik-*/
      //       spojnice-sloupec*) - noha/patka boxu zasahuje do kolejnicky
      //       podle designu, taky spravne "expected"
      // Misto toho ale osvobodilo KAZDY par, kde aspon jedna strana neni
      // Object_7 - vcetne eurobox vuci NOZE (predni-svislice/spojnice-horni/
      // zadni-svislice-nad-zarezem/pricka-uzavreni-vyrezu), coz NIKDY
      // zamerene nebylo. Presne timhle dirou proslo 9 sestav (5 Proace + 4
      // Peugeot e-Expert L1/PE25) se skutecnym zanorenim euroboxu do nohy -
      // vsechny mely `ok: true` pri vlozeni do DB, protoze tenhle test je
      // nikdy nezachytil.
      const A_ = allParts[i], B_ = allParts[j];
      const jeZaslepka = (p) => p.part_id === "product_3071";
      const jeEurobox = (p) => p.part_id.startsWith("product_37") && p.part_id !== "product_3071";
      const jeKolejnicka = (p) => p.role.startsWith("nosnik-") || p.role.startsWith("spojnice-sloupec");
      const nestOk =
        (jeZaslepka(A_) && B_.part_id === "Object_7") || (jeZaslepka(B_) && A_.part_id === "Object_7") ||
        (jeEurobox(A_) && jeKolejnicka(B_)) || (jeEurobox(B_) && jeKolejnicka(A_));
      if (nestOk) expected++;
      else { unexpected++; badPairs.push([allParts[i].role, allParts[j].role]); }
    }
  }

  const clean = allParts.map(({ _pending, ...rest }) => rest);
  const totalBoxes = columnSummaries.reduce((s, c) => s + c.totalBoxes, 0);
  const distinctHeights = [...new Set(columnSummaries.flatMap(c => c.boxHeights))];

  return {
    ok: !carCollisionProfiles && !euroboxCarCollision && unexpected === 0,
    carCollisionProfiles, euroboxCarCollision, badEurobox, unexpected, badPairs, expected,
    parts: clean, columnSummaries, totalBoxes, distinctHeights, legCount: legs.length,
    cfg,
  };
}

module.exports = { buildFull };

if (require.main === module) {
  const stepPath = process.argv[2], outPath = process.argv[3];
  const step = JSON.parse(fs.readFileSync(stepPath, "utf8"));
  const result = buildFull(step);
  fs.writeFileSync(outPath, JSON.stringify(result, null, 1));
  console.log(step.cfg.name, "-> ok=", result.ok, "boxes=", result.totalBoxes, "heights=", result.distinctHeights, "dily=", result.parts.length);
  if (!result.ok) console.log("  carCollisionProfiles=", result.carCollisionProfiles, "euroboxCarCollision=", result.euroboxCarCollision, "unexpected=", result.unexpected, result.badPairs, result.badEurobox);
}
