// bot16 2026-09-02 - assembly step (parts + endcaps + euroboxes + brackets +
// id=8 leg height + full verification) for the "door void" fixed FO31/VW25
// eurobox rack. Consumes the plan produced by tmp_2026-09-02_doorvoid_pipeline.js
// (runPipelineDoorFixed) - legs/columns/step4/step5/step7 - and builds the
// final product_assemblies.data.parts for one chosen box-height composition.
const THREE = require("three");
const fs = require("fs");
const pv = require("/opt/konfigurator/scripts/tmp_2026-09-02_doorvoid_pipeline.js");
const { buildPlainAtDepth, buildVyrezAtDepth } = require("/opt/konfigurator/scripts/tmp_2026-08-30_build_depth_variants_both.js");
const uhelnikLib = require("/opt/konfigurator/scripts/2026-09-01_uhelniky_leg_joints_lib.js");

const { D, T, H, CAP_H, CUTOUT_H, TOP_Y, CAP_FLANGE_THICKNESS, KAT, ENDCAP, EUROBOX_GLB, EUROBOX_PID, CONNECTOR_POS, Q_ALONG_Z, Q_ALONG_X, Q_ENDCAP_UP } = pv;
const HEIGHTS_DESC = [270, 220, 170, 120];
const OBJ7 = KAT + "Object_7.glb";
const uhelnikCatalog = JSON.parse(fs.readFileSync("/opt/konfigurator/scripts/2026-09-01_uhelnik_catalog.json", "utf8"));
// OPRAVA (bug #1, +12mm mezera - viz tmp_2026-08-31_batch_pipeline.js): eurobox
// ma 12mm "nozku" (nesting foot), ktera zapada 12mm POD rail top (viz "-12" v
// pozicovani boxu v assemble() nize). Viditelna vyska boxu nad rail top je
// H_box-12, ne plna deklarovana H_box - pouzito ve planColumn/planColumnFrom/
// validateHeights/assemble nize, aby vsechny zustaly navzajem konzistentni.
// Tenhle soubor je AKTIVNI pipeline pro prubezne stavene Jumpy sestavy - mel
// tutéž chybu zkopirovanou z tmp_2026-08-31_batch_pipeline.js, opraveno
// souběžně (2026-09-03).
const NEST_FOOT = 12;
// OPRAVA (bug #3 "Y-offset regrese", VW31, 2026-09-03, viz tmp_2026-08-31_
// batch_pipeline.js pro plne vysvetleni): dily regalu (cokoliv KROME
// "car_body_*") jsou VZDY v "podlaha=Y0" souradnicich assembly - throw misto
// ticheho zapisu spatnych dat, pokud nekde vyjde mimo rozumne rozmezi. Tenhle
// soubor je AKTIVNI pipeline pro prubezne stavene Jumpy sestavy.
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

function planColumn(floorY, physCeil, mixed) {
  // DULEZITA OPRAVA oproti puvodnimu tmp_2026-08-31_batch_pipeline.js:
  // tam se behem hladoveho patrovani kontrolovalo VZDY jen TOP_Y (920mm,
  // joint-containment nosniku), fyzicky strop (physCeil) se resil AZ
  // dodatecne pro POSLEDNI patro ("presah boxu pres railTOP_Y je OK, box
  // sam neni strukturalne nesen shora"). To predpokladalo physCeil>=TOP_Y
  // (u vsech dosavadnich vozidel/pozic pravda). Po presunu za dverni
  // otvor u FO31/VW25 vysel physCeil<TOP_Y (strop je NIZ nez standardni
  // 920mm limit) - v tom pripade je physCeil TVRDSI limit uz i pro
  // NEPOSLEDNI patra (rail samotny bez boxu prekazku nemusi cit, ale box
  // NA railu uz by realne kolidoval se strechou). Oprava: kazde patro
  // (vc. neposledniho) respektuje efektivni limit min(TOP_Y, physCeil).
  const effLimit = Math.min(TOP_Y, physCeil);
  let railTop = floorY + T;
  const heights = [];
  if (mixed) {
    let hi = 0;
    while (true) {
      let placedH = null, placedK = null;
      for (let k = hi; k < HEIGHTS_DESC.length; k++) {
        const boxH = HEIGHTS_DESC[k];
        const top = railTop + (boxH - NEST_FOOT);
        if (top <= effLimit + 1e-6) { placedH = boxH; placedK = k; break; }
      }
      if (placedH === null) break;
      hi = Math.min(placedK + 1, HEIGHTS_DESC.length - 1);
      heights.push(placedH);
      railTop = railTop + (placedH - NEST_FOOT) + 30 + T;
    }
  } else {
    while (railTop + (120 - NEST_FOOT) <= effLimit + 1e-6) { heights.push(120); railTop = railTop + (120 - NEST_FOOT) + 30 + T; }
  }
  // "presah boxu pres TOP_Y" upgrade jen dava smysl kdyz physCeil>TOP_Y
  // (tj. je co vyuzit navic) - jinak (nas pripad, physCeil<=TOP_Y) je
  // effLimit uz to jedine relevantni omezeni a zadny upgrade neni mozny.
  // OPRAVA (bot25, 2026-09-02, viz planColumnFrom nize pro plne vysvetleni):
  // upgrade nesmi porusit nerostouci posloupnost vuci predchozimu patru -
  // ztraceny gate z puvodniho tmp_2026-08-31_batch_pipeline.js (`!mixed`)
  // zpusobil na Jumpy (physCeil 923-927mm, tesne NAD TOP_Y=920mm) [220,170]
  // -> [220,270] regresi (nalezeno na CI13).
  if (physCeil > TOP_Y && heights.length > 0) {
    const prevH = heights.length >= 2 ? heights[heights.length - 2] : Infinity;
    const beforeTopRailTop = railTop - ((heights[heights.length - 1] - NEST_FOOT) + 30 + T);
    for (const boxH of HEIGHTS_DESC) {
      if (boxH < heights[heights.length - 1]) break;
      if (boxH > prevH) continue;
      if (beforeTopRailTop + (boxH - NEST_FOOT) <= physCeil + 1e-6) { heights[heights.length - 1] = boxH; break; }
    }
  } else if (physCeil > TOP_Y && heights.length === 0 && floorY + T + (120 - NEST_FOOT) <= physCeil + 1e-6) {
    for (const boxH of HEIGHTS_DESC) {
      if (floorY + T + (boxH - NEST_FOOT) <= physCeil + 1e-6) { heights.push(boxH); break; }
    }
  }
  return heights;
}

// bot25, 2026-09-02 - stejne jako planColumn(mixed=true), ale zacina cyklus
// HEIGHTS_DESC od LIBOVOLNEHO indexu startIdx (ne vzdy od 0/270mm) - pouzito
// pro krizovou diverzifikaci NAPRIC sloupci (kazdy sloupec zacne jinou
// vyskou), aby CELA sestava (ne jen jeden sloupec) splnila pravidlo >=3
// distinct vysek (shape_geometry_methods.id=3, "diverzifikace_napric_sloupci").
function planColumnFrom(floorY, physCeil, startIdx) {
  const effLimit = Math.min(TOP_Y, physCeil);
  let railTop = floorY + T;
  const heights = [];
  let hi = startIdx;
  while (true) {
    let placedH = null, placedK = null;
    for (let k = hi; k < HEIGHTS_DESC.length; k++) {
      const boxH = HEIGHTS_DESC[k];
      const top = railTop + (boxH - NEST_FOOT);
      if (top <= effLimit + 1e-6) { placedH = boxH; placedK = k; break; }
    }
    if (placedH === null) break;
    hi = Math.min(placedK + 1, HEIGHTS_DESC.length - 1);
    heights.push(placedH);
    railTop = railTop + (placedH - NEST_FOOT) + 30 + T;
  }
  // OPRAVA (bot25, 2026-09-02): puvodni tmp_2026-08-31_batch_pipeline.js
  // gatoval tenhle "upgrade posledniho patra" blok za "!mixed" (diverzita ma
  // prednost pred cistym poctem - nesmi se prepsat zpet na vetsi box, kdyz
  // diverzifikace zamerne zvolila mensi). tmp_2026-09-02_doorvoid_assemble.js
  // (FO31/VW25) tenhle gate ZTRATIL - nevadilo to tam, protoze FO31/VW25 mely
  // OBA physCeil<TOP_Y (upgrade blok se nikdy nespustil). U Jumpy je physCeil
  // (923-927mm) TESNE NAD TOP_Y=920mm - upgrade blok SE spusti a bez gatu
  // prepise posledni patro na vetsi box, i kdyz by tim porusil nerostouci
  // posloupnost (napr. [220,170] -> [220,270], zjisteno na CI13). OPRAVA:
  // upgrade smi zvetsit posledni patro jen pokud (a) je to jedine patro
  // (zadna predchozi vyska, o kterou by se mohla "otrit"), NEBO (b) novy box
  // porad zustane <= predposledniho patra (monotonie zachovana).
  if (physCeil > TOP_Y && heights.length > 0) {
    const prevH = heights.length >= 2 ? heights[heights.length - 2] : Infinity;
    const beforeTopRailTop = railTop - ((heights[heights.length - 1] - NEST_FOOT) + 30 + T);
    for (const boxH of HEIGHTS_DESC) {
      if (boxH < heights[heights.length - 1]) break;
      if (boxH > prevH) continue; // nesmi porusit nerostouci posloupnost vuci predchozimu patru
      if (beforeTopRailTop + (boxH - NEST_FOOT) <= physCeil + 1e-6) { heights[heights.length - 1] = boxH; break; }
    }
  } else if (physCeil > TOP_Y && heights.length === 0 && floorY + T + (120 - NEST_FOOT) <= physCeil + 1e-6) {
    for (const boxH of HEIGHTS_DESC) {
      if (floorY + T + (boxH - NEST_FOOT) <= physCeil + 1e-6) { heights.push(boxH); break; }
    }
  }
  return heights;
}

// validate an explicit heights array against floor/ceil/non-increasing rules
function validateHeights(heights, floorY, physCeil) {
  if (heights.length === 0) return { ok: true, note: "empty" };
  for (let i = 1; i < heights.length; i++) if (heights[i] > heights[i - 1]) return { ok: false, reason: `patro${i} (${heights[i]}) > patro${i - 1} (${heights[i - 1]}) - musi byt nerostouci` };
  let railTop = floorY + T;
  for (let i = 0; i < heights.length; i++) {
    const isLast = i === heights.length - 1;
    const top = railTop + (heights[i] - NEST_FOOT);
    // neposledni patro: vzdy TOP_Y (joint-containment nosniku). Posledni
    // patro: physCeil OBECNE, ALE nikdy mene prisne nez min(TOP_Y,physCeil)
    // - pokud physCeil<TOP_Y (nas pripad), je physCeil tvrdsi limit uz
    // pro vsechna patra (viz planColumn oprava vyse), ne jen posledni.
    const limit = isLast ? physCeil : Math.min(TOP_Y, physCeil);
    if (top > limit + 1e-6) return { ok: false, reason: `patro${i} top=${top.toFixed(1)} presahuje limit ${limit.toFixed(1)} (${isLast ? "physCeil" : "min(TOP_Y,physCeil)"})` };
    railTop = railTop + (heights[i] - NEST_FOOT) + 30 + T;
  }
  return { ok: true };
}

function legPartsFor(type) { return type === "vyrez" ? buildVyrezAtDepth(D) : buildPlainAtDepth(D); }

function assemble(plan, heightsPerColumn, opts) {
  opts = opts || {};
  const { legs, columns, step4, step5, step7, offsetX, offsetY, sgn, dirAway, collidesWithWalls, buildLegObject, parseGlbMesh } = plan;
  function toWorld(localParts, anchorZ) {
    return localParts.map(p => ({
      part_id: p.part_id || "Object_7",
      position: [offsetX + sgn * p.position[0], p.position[1] + offsetY, anchorZ + p.position[2]],
      quaternion: p.quaternion, scale: p.scale, role: p.role,
    }));
  }
  function legEndcapRoles(type) { return type === "vyrez" ? ["predni-svislice", "zadni-svislice-nad-zarezem", "cap"] : ["predni-svislice", "zadni-svislice-dolni", "cap"]; }
  function topEndcapsFor(legParts, roles) {
    return legParts.filter(p => roles.includes(p.role)).map(p => {
      const lenMm = p.scale[1] * 1000;
      const topY = p.position[1] + lenMm / 2 + CAP_FLANGE_THICKNESS;
      return { part_id: "product_3071", position: [p.position[0], topY, p.position[2]], quaternion: Q_ENDCAP_UP, scale: [1, 1, 1], role: "zaslepka" };
    });
  }

  let allParts = [];
  const legEntriesForBrackets = []; // per-leg world part specs (for id=7 corner brackets)
  legs.forEach((leg, i) => {
    let localParts = leg.type === "plain" ? buildPlainAtDepth(D) : pv.buildVyrezAtDepthExtended(D, step4[i].Y_new);
    const world = toWorld(localParts, leg.anchorZ);
    const endcaps = topEndcapsFor(world, legEndcapRoles(leg.type));
    allParts.push(...world, ...endcaps);
    legEntriesForBrackets.push({ legIdx: i, type: leg.type, worldParts: world });
  });

  const columnSummaries = [];
  columns.forEach((col, colIdx) => {
    const legFrom = legs[col.legFromIdx], legTo = legs[col.legToIdx];
    const floorY = step5[colIdx].finalFloorY;
    const physCeil = step7[colIdx].maxSafeBoxTop;
    const heights = heightsPerColumn[colIdx];
    const v = validateHeights(heights, floorY, physCeil);
    if (!v.ok) throw new Error(`sloupec${colIdx} neplatna skladba vysek: ${v.reason}`);
    // OPRAVA (bot25, 2026-09-02) - viz tmp_2026-09-02_jumpy_pipeline.js
    // railsAndConnectorsForColumn pro plne vysvetleni: puvodni vzorec platil
    // jen pro dirAway=+1, pro dirAway=-1 pohltil cely legTo dovnitr railu.
    const zFromRaw = legFrom.anchorZ + T / 2 + dirAway * T / 2, zToRaw = legTo.anchorZ + T / 2 - dirAway * T / 2;
    const railZFrom = Math.min(zFromRaw, zToRaw), railZTo = Math.max(zFromRaw, zToRaw);
    const railLen = railZTo - railZFrom, railZCenter = (railZFrom + railZTo) / 2;
    const crossLen = D - 2 * T, crossXCenter = D / 2;

    let railTop = floorY + T;
    const levels = [];
    heights.forEach((boxH) => {
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
      const sortedPos = positions.slice().sort((a, b) => a - b);
      sortedPos.forEach(localZ => {
        allParts.push({ part_id: "Object_7", position: [offsetX + sgn * crossXCenter, Y + offsetY, railZFrom + localZ], quaternion: Q_ALONG_X, scale: [1, crossLen / 1000, 1], role: `spojnice-sloupec${colIdx}-patro${levelIdx}` });
      });
      for (let i = 0; i < sortedPos.length - 1; i++) {
        allParts.push({
          part_id: EUROBOX_PID[level.boxH], position: [0, 0, 0], quaternion: Q_ALONG_Z, scale: [1, 1, 1], role: `eurobox-sloupec${colIdx}-patro${levelIdx}`,
          _pending: { slotZFrom: railZFrom + sortedPos[i], slotZTo: railZFrom + sortedPos[i + 1], railYCenter: Y + offsetY, boxH: level.boxH },
        });
      }
    });
    columnSummaries.push({ colIdx, N: col.N, floorY, physCeil, levels: levels.length, boxHeights: levels.map(l => l.boxH), totalBoxes: col.N * levels.length, railZFrom, railZTo });
  });

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

  // ---- id=7 uhelniky na spojich noh (per leg, na jiz WORLD-pozicovanych dilech) ----
  let bracketStats = [];
  legEntriesForBrackets.forEach(({ legIdx, worldParts }) => {
    const entries = worldParts.map((p, idx) => uhelnikLib.makeProfileEntry(OBJ7, { ...p, idx, cross_section_mm: [T, T] }));
    const { results, stats } = uhelnikLib.applyUhelnikyToLeg(entries, uhelnikCatalog, KAT);
    results.forEach(r => allParts.push({ part_id: r.part_id, position: r.position, quaternion: r.quaternion, scale: [1, 1, 1], role: `uhelnik-noha${legIdx}` }));
    bracketStats.push({ legIdx, placed: stats.totalBracketsPlaced, pairsMatched: stats.pairsMatched, pairsChecked: stats.pairsChecked });
  });

  // ---- kontrola kolize s karoserii: profily ----
  const profileParts = allParts.filter(p => p.part_id === "Object_7");
  const badProfiles = [];
  profileParts.forEach((p) => { if (collidesWithWalls(buildLegObject([p]))) badProfiles.push({ role: p.role, position: p.position }); });

  function glbFor(id) {
    if (id === "Object_7") return OBJ7;
    if (id === "product_3071") return ENDCAP;
    for (const h in EUROBOX_PID) if (EUROBOX_PID[h] === id) return EUROBOX_GLB[h];
    // uhelnik part ids come from catalog (product_XXXX)
    const meta = uhelnikCatalog.find(c => c.part_id === id);
    if (meta) return KAT + meta.glb_file;
    return null;
  }
  function meshOf(p) { const m = parseGlbMesh(glbFor(p.part_id)); m.position.set(...p.position); m.quaternion.set(...p.quaternion); m.scale.set(...p.scale); m.updateMatrixWorld(true); return m; }

  const nonProfileCollidable = allParts.filter(p => p.part_id !== "Object_7");
  const badOther = [];
  nonProfileCollidable.forEach(p => {
    const grp = new THREE.Group(); grp.add(meshOf(p)); grp.updateMatrixWorld(true);
    if (collidesWithWalls(grp)) badOther.push({ role: p.role, part_id: p.part_id });
  });

  // self-kolize (stejna metrika jako batch_pipeline.js), krome ocekavanych
  // nestingu: eurobox/zaslepka do profilu, uhelnik do profilu (roh).
  const meshes = allParts.map(meshOf);
  let unexpected = 0;
  const unexpectedDetails = [];
  for (let i = 0; i < meshes.length; i++) for (let j = i + 1; j < meshes.length; j++) {
    const A = new THREE.Box3().setFromObject(meshes[i]), B = new THREE.Box3().setFromObject(meshes[j]);
    const ox = Math.min(A.max.x, B.max.x) - Math.max(A.min.x, B.min.x);
    const oy = Math.min(A.max.y, B.max.y) - Math.max(A.min.y, B.min.y);
    const oz = Math.min(A.max.z, B.max.z) - Math.max(A.min.z, B.min.z);
    if (ox > 0.5 && oy > 0.5 && oz > 0.5) {
      const bothProfile = allParts[i].part_id === "Object_7" && allParts[j].part_id === "Object_7";
      const isUhelnik = allParts[i].role.startsWith("uhelnik") || allParts[j].role.startsWith("uhelnik");
      const nestOk = !bothProfile || isUhelnik;
      if (!nestOk) { unexpected++; unexpectedDetails.push([allParts[i].role, allParts[j].role]); }
    }
  }

  const clean = allParts.map(({ _pending, ...rest }) => rest);
  assertSaneRackYPositions(clean);
  const totalBoxes = columnSummaries.reduce((s, c) => s + c.totalBoxes, 0);
  const distinctHeights = [...new Set(columnSummaries.flatMap(c => c.boxHeights))].sort((a, b) => b - a);

  return {
    ok: badProfiles.length === 0 && badOther.length === 0 && unexpected === 0,
    badProfiles, badOther, unexpected, unexpectedDetails,
    parts: clean, columnSummaries, totalBoxes, distinctHeights, bracketStats,
    legsMeta: legs.map(l => ({ anchorZ: l.anchorZ, type: l.type })),
  };
}

// ---- shape_geometry_methods.id=8 (prizpusobeni-vysky-nohy-vysce-dveri) ----
// Protahuje "predni-svislice" a "cap" (wall-side top kus, pritomny u OBOU
// typu nohy - plain i vyrez, viz buildPlainAtDepth/buildVyrezAtDepthExtended)
// KAZDE nohy smerem nahoru, realnym 1mm kolizni krokovanim (20mm odskok),
// az na min(realny bezkolizni strop, H_cil = official_door_opening_height_mm-30).
// Zaslepka (endcap) na dane roli se posune na novy top+3mm (flange).
function applyDoorHeightRule(parts, legsMeta, doorHeightMm, engine) {
  const H_CIL = doorHeightMm - 30;
  const { collidesWithWalls, buildLegObject } = engine;
  const changes = [];
  legsMeta.forEach((leg, legIdx) => {
    const legZ = leg.anchorZ + T / 2;
    ["predni-svislice", "cap"].forEach(role => {
      const piece = parts.find(p => p.role === role && Math.abs(p.position[2] - legZ) < 1);
      if (!piece) return;
      const lenMm = piece.scale[1] * 1000;
      const bottomY = piece.position[1] - lenMm / 2;
      const currentTop = piece.position[1] + lenMm / 2;
      if (currentTop >= H_CIL - 1e-6) return; // uz na/nad cilem (nemuze byt, ale pro jistotu)
      function topCollides(topY) {
        const test = { ...piece, position: [piece.position[0], (bottomY + topY) / 2, piece.position[2]], scale: [1, (topY - bottomY) / 1000, 1] };
        return collidesWithWalls(buildLegObject([test]));
      }
      let y = currentTop, collisionY = null, steps = 0;
      while (y < H_CIL + 25 && steps < 4000) {
        y += 1; steps++;
        if (topCollides(y)) { collisionY = y; break; }
      }
      let newTop;
      if (collisionY === null) {
        newTop = H_CIL; // zadna kolize az do cile - protahni presne na H_cil
      } else {
        newTop = Math.min(H_CIL, collisionY - 20);
      }
      if (newTop <= currentTop + 1e-6) return; // zadny zisk
      if (topCollides(newTop)) throw new Error(`applyDoorHeightRule leg${legIdx} ${role}: newTop=${newTop} stale koliduje`);
      piece.position = [piece.position[0], (bottomY + newTop) / 2, piece.position[2]];
      piece.scale = [1, (newTop - bottomY) / 1000, 1];
      // najdi odpovidajici zaslepku (stejne X/Z, role=zaslepka) a posun na novy top+3mm
      const zaslepka = parts.find(p => p.role === "zaslepka" && Math.abs(p.position[0] - piece.position[0]) < 1 && Math.abs(p.position[2] - piece.position[2]) < 1);
      if (zaslepka) zaslepka.position = [zaslepka.position[0], newTop + CAP_FLANGE_THICKNESS, zaslepka.position[2]];
      changes.push({ legIdx, role, oldTop: currentTop, newTop, H_CIL, collisionY });
    });
  });
  return changes;
}

module.exports = { assemble, planColumn, planColumnFrom, validateHeights, legPartsFor, applyDoorHeightRule, HEIGHTS_DESC };
