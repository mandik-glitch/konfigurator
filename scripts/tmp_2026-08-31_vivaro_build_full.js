// Finalni sestaveni "Regal na euroboxy - Vivaro OP18, leva stena" - kompletni
// geometrie (nohy s endcapy, luzka po patrech, euroboxy 120/220/270mm).
// Vivaro GLB byla TETO session FYZICKY OTOCENA o 180 (viz place_vivaro.js).
// KRITICKY NALEZ: pro stenu na ZAPORNE strane X je treba MIRROR X konvenci
// (worldX = offsetX - localX), jinak vyjde "zadni"(u steny)/"predni"(daleko
// od steny) role leg-dilu OBRACENE nez fyzicka realita - viz step1 skript.
const THREE = require("three");
const fs = require("fs");
const { parseGlbMesh, collidesWithWalls, buildLegObject } = require("/opt/konfigurator/scripts/tmp_2026-08-31_place_vivaro.js");
const { buildPlainAtDepth, buildVyrezAtDepth } = require("/opt/konfigurator/scripts/tmp_2026-08-30_build_depth_variants_both.js");

const step1 = JSON.parse(fs.readFileSync("/opt/konfigurator/scripts/tmp_2026-08-31_vivaro_step1_result.json", "utf8"));
const step3 = JSON.parse(fs.readFileSync("/opt/konfigurator/scripts/tmp_2026-08-31_vivaro_step3_result.json", "utf8"));
const step4 = JSON.parse(fs.readFileSync("/opt/konfigurator/scripts/tmp_2026-08-31_vivaro_step4_result.json", "utf8"));
const step5 = JSON.parse(fs.readFileSync("/opt/konfigurator/scripts/tmp_2026-08-31_vivaro_step5_result.json", "utf8"));
const step7 = JSON.parse(fs.readFileSync("/opt/konfigurator/scripts/tmp_2026-08-31_vivaro_step7_result.json", "utf8"));

const { offsetX, offsetY, D, T, H } = step1;
const CAP_H = 260, CUTOUT_H = 395;
const TOP_Y = H - CAP_H; // 920
const RAIL_CENTER_MAX = TOP_Y - T / 2; // 905 - existujici pravidlo, NEZMENENO, plati pro RAIL
const CAP_FLANGE_THICKNESS = 3;
const KAT = "/opt/konfigurator/webapp/katalog/";
const OBJ7 = KAT + "Object_7.glb";
const ENDCAP = KAT + "product_3071.glb";
const EUROBOX_GLB = { 120: KAT + "product_3788.glb", 170: KAT + "product_3793.glb", 220: KAT + "product_3794.glb", 270: KAT + "product_3795.glb" };
const EUROBOX_PID = { 120: "product_3788", 170: "product_3793", 220: "product_3794", 270: "product_3795" };
const CONNECTOR_POS = { 1: [15, 415], 2: [15, 415, 816], 3: [15, 415, 816, 1217] };
const Q_ALONG_Z = [-0.707107, 0, 0, 0.707107];
const Q_ALONG_X = [0, 0, -0.707107, 0.707107];
const Q_ENDCAP_UP = [0.7071067811865475, 0, 0, 0.7071067811865475];

// Rucne navrzeny plan pater (tmp_2026-08-31_vivaro_plan_levels.js): sloupec0
// (3box, floor=213) 4x120mm (demonstrace: 4. patro topBox=903mm by pod
// STAROU, jen implicitni domnenkou "box nesmi presahnout railYCenter=905/
// railTop=920" bylo na hrane/OK i bez noveho pravidla - viz report pro presne
// cislo fyzickeho stropu 922mm u tohoto sloupce); sloupec1 (2box, floor=318)
// 270+220mm (topBox=898mm). Kombinace pouziva 3 ruzne vysky (120/220/270)
// nekde v cele sestave, nerostouci v kazdem sloupci, diverzifikovane napric
// sloupci (sloupec0 vs sloupec1 ruzna kombinace).
const COLUMN_HEIGHTS = { 0: [120, 120, 120, 120], 1: [270, 220] };

function buildVyrezAtDepthExtended(D, Y_new) {
  const base = buildVyrezAtDepth(D);
  const T_ = T;
  const zCenter = T_ / 2;
  const parts = base.filter(p => !["sloupek-pred-podbehem", "pricka-uzavreni-vyrezu", "zadni-svislice-nad-zarezem"].includes(p.role));
  const orig = base.find(p => p.role === "sloupek-pred-podbehem");
  const colX = orig.position[0];
  parts.push({ position: [colX, Y_new / 2, zCenter], quaternion: [0, 0, 0, 1], scale: [1, Y_new / 1000, 1], role: "sloupek-pred-podbehem" });
  const origPricka = base.find(p => p.role === "pricka-uzavreni-vyrezu");
  parts.push({ position: [origPricka.position[0], Y_new + T_ / 2, zCenter], quaternion: origPricka.quaternion, scale: origPricka.scale, role: "pricka-uzavreni-vyrezu" });
  const upperLen = TOP_Y - Y_new;
  parts.push({ position: [D - T_ / 2, (Y_new + TOP_Y) / 2, zCenter], quaternion: [0, 0, 0, 1], scale: [1, upperLen / 1000, 1], role: "zadni-svislice-nad-zarezem" });
  return parts;
}

function legEndcapRoles(type) { return type === "vyrez" ? ["predni-svislice", "zadni-svislice-nad-zarezem", "cap"] : ["predni-svislice", "zadni-svislice-dolni", "cap"]; }
function topEndcapsFor(legParts, roles) {
  return legParts.filter(p => roles.includes(p.role)).map(p => {
    const lenMm = p.scale[1] * 1000;
    const topY = p.position[1] + lenMm / 2 + CAP_FLANGE_THICKNESS;
    return { part_id: "product_3071", position: [p.position[0], topY, p.position[2]], quaternion: Q_ENDCAP_UP, scale: [1, 1, 1], role: "zaslepka-" + p.role };
  });
}

function toWorld(localParts, anchorZ) {
  return localParts.map(p => ({
    part_id: p.part_id || "Object_7",
    position: [offsetX - p.position[0], p.position[1] + offsetY, anchorZ + p.position[2]],
    quaternion: p.quaternion,
    scale: p.scale,
    role: p.role,
  }));
}

// ---------- 1. nohy + endcapy ----------
const legFloor = [];
let allParts = [];
step3.legs.forEach((leg, i) => {
  let localParts;
  if (leg.type === "plain") {
    localParts = buildPlainAtDepth(D);
    legFloor.push(0);
  } else {
    const Y_new = step4[i].Y_new;
    localParts = buildVyrezAtDepthExtended(D, Y_new);
    legFloor.push(Y_new);
  }
  const endcaps = topEndcapsFor(localParts, legEndcapRoles(leg.type));
  allParts.push(...toWorld([...localParts, ...endcaps], leg.anchorZ));
});

// ---------- 2. luzka (rails+connectors) podle LEVEL_PLAN, s NOVYM pravidlem
// prekryvu na TOPmost patro (box smi presahnout 920 az do fyzickeho stropu
// step7.maxSafeBoxTop, RAIL zustava <=905 stred jako drive) ----------
const columnSummaries = [];
step3.columns.forEach((col, colIdx) => {
  const legFrom = step3.legs[col.legFromIdx]; // blize prepazce (nizsi Z)
  const legTo = step3.legs[col.legToIdx];     // dal od prepazky (vyssi Z)
  const floorY = step5[colIdx].finalFloorY;
  const physCeil = step7[colIdx].maxSafeBoxTop;
  const heights = COLUMN_HEIGHTS[colIdx];

  const railZFrom = legFrom.anchorZ + T, railZTo = legTo.anchorZ;
  const railLen = railZTo - railZFrom, railZCenter = (railZFrom + railZTo) / 2;
  const crossLen = D - 2 * T, crossXCenter = D / 2;

  let railTop = floorY + T; // = floor + T (railYCenter = floor+T/2)
  const levels = [];
  heights.forEach((boxH, levelIdx) => {
    const railYCenter = railTop - T / 2;
    if (railYCenter > RAIL_CENTER_MAX + 1e-6) throw new Error(`sloupec ${colIdx} patro ${levelIdx}: rail center ${railYCenter} > ${RAIL_CENTER_MAX} - NEPLATNY (existujici pravidlo, RAIL)`);
    const isTop = levelIdx === heights.length - 1;
    const boxTop = railTop + boxH;
    const limit = isTop ? physCeil : TOP_Y;
    if (boxTop > limit + 1e-6) throw new Error(`sloupec ${colIdx} patro ${levelIdx}: boxTop ${boxTop} > limit ${limit}`);
    levels.push({ railYCenter, boxH, boxTop, overhangsPast920: boxTop > TOP_Y + 1e-6 });
    railTop = railTop + boxH + 30 + T;
  });

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
  columnSummaries.push({ colIdx, N: col.N, floorY, physCeil, levels: levels.length, boxHeights: levels.map(l => l.boxH), topBoxOverhangsPast920: levels[levels.length - 1].overhangsPast920, topBoxTop: levels[levels.length - 1].boxTop, boxesPerLevel: col.N, totalBoxes: col.N * levels.length, railZFrom, railZTo, railLen });
});

// ---------- 3. eurobox presne umisteni (dynamicky probe) ----------
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

// ---------- 4. kontrola kolize s karoserii (jen Object_7 profily) ----------
const profileParts = allParts.filter(p => p.part_id === "Object_7");
const group = buildLegObject(profileParts);
const carCollisionProfiles = collidesWithWalls(group);
console.log("Profily koliduji s karoserii Vivaro?", carCollisionProfiles);

// take euroboxy - kriticke kvuli NOVEMU pravidlu prekryvu (box_top muze byt >920,
// musi byt overeno primo proti realne karoserii, ne jen proti nohy-based limitu)
function meshOf(p) { const m = parseGlbMesh(glbFor(p.part_id)); m.position.set(...p.position); m.quaternion.set(...p.quaternion); m.scale.set(...p.scale); m.updateMatrixWorld(true); return m; }
function glbFor(id) {
  if (id === "Object_7") return OBJ7;
  if (id === "product_3071") return ENDCAP;
  for (const h in EUROBOX_PID) if (EUROBOX_PID[h] === id) return EUROBOX_GLB[h];
  return null;
}
const euroboxParts = allParts.filter(p => p.part_id.startsWith("product_37"));
let euroboxCarCollision = false;
euroboxParts.forEach(p => {
  const grp = new THREE.Group(); grp.add(meshOf(p)); grp.updateMatrixWorld(true);
  if (collidesWithWalls(grp)) { euroboxCarCollision = true; console.log("EUROBOX koliduje s karoserii:", p.role, p.position); }
});
console.log("Nektery eurobox koliduje s karoserii?", euroboxCarCollision);

if (carCollisionProfiles || euroboxCarCollision) {
  const bad = [];
  profileParts.forEach((p, i) => { if (collidesWithWalls(buildLegObject([p]))) bad.push({ i, role: p.role, position: p.position, scale: p.scale }); });
  console.log("JEDNOTLIVE kolidujici profily:", JSON.stringify(bad, null, 1));
  throw new Error("KOLIZE s karoserii - zastavuji");
}

// ---------- 5. self-kolize ----------
const meshes = allParts.map(meshOf);
let unexpected = 0, expected = 0;
for (let i = 0; i < meshes.length; i++) for (let j = i + 1; j < meshes.length; j++) {
  const A = new THREE.Box3().setFromObject(meshes[i]), B = new THREE.Box3().setFromObject(meshes[j]);
  const ox = Math.min(A.max.x, B.max.x) - Math.max(A.min.x, B.min.x);
  const oy = Math.min(A.max.y, B.max.y) - Math.max(A.min.y, B.min.y);
  const oz = Math.min(A.max.z, B.max.z) - Math.max(A.min.z, B.min.z);
  if (ox > 0.5 && oy > 0.5 && oz > 0.5) {
    const nestOk = allParts[i].part_id !== "Object_7" || allParts[j].part_id !== "Object_7";
    if (nestOk) expected++;
    else { unexpected++; console.log("NEOCEKAVANY presah:", allParts[i].role, "<->", allParts[j].role, ox.toFixed(1), oy.toFixed(1), oz.toFixed(1)); }
  }
}
console.log("presahy ocekavane(nesting)=", expected, "NEOCEKAVANE=", unexpected, "celkem dilu=", allParts.length);
if (unexpected > 0) throw new Error("neocekavana self-kolize");

// ---------- 6. souhrn ----------
console.log("\n=== SOUHRN SLOUPCU ===");
columnSummaries.forEach(c => console.log(c));
const totalBoxes = columnSummaries.reduce((s, c) => s + c.totalBoxes, 0);
const distinctHeights = new Set(columnSummaries.flatMap(c => c.boxHeights));
console.log("CELKEM EUROBOXU:", totalBoxes, " DISTINCT VYSKY:", [...distinctHeights]);
console.log("CELKEM NOH:", step3.legs.length);

const clean = allParts.map(({ _pending, ...rest }) => rest);
fs.writeFileSync("/opt/konfigurator/scripts/tmp_2026-08-31_vivaro_full_rack.json", JSON.stringify(clean, null, 1));
fs.writeFileSync("/opt/konfigurator/scripts/tmp_2026-08-31_vivaro_column_summary.json", JSON.stringify(columnSummaries, null, 1));
console.log("\nulozeno. celkem dilu=", clean.length);
