// K-020 (VW Caddy Cargo Maxi PHEV, VW32) - regal na euroboxy, leva stena - sdilena knihovna.
// Pravidla: shape_geometry_methods id=1 (prevod 30x30), 2 (hloubka D, prvky u steny kotveny ke stene),
// 3 (ukladani euroboxu do luzek, v14 robert), 4 (zaslepky + uzavreni vyrezu), 5 (sloupce),
// 6 (protazeni vyrezove nohy, v7 robert), 8 (vyska nohy = dvere-30, konec profilu);
// car_body_placement_methods id=1 (kolizni krokovani, max rozpon, podbeh_bez_konce_2026_09_02).
// Noha = custom_shapes 534/535 "Noha.1.Caddy.1080.349.30x30(.vyrez)" prevedena na D=326, H=1092.
// Rezervy: 10mm prepazka, 30mm podbeh (Robert 2026-09-12).
const THREE = require("three");
const { createEngine } = require("/opt/konfigurator/scripts/tmp_2026-08-31_batch_engine.js");

const BASE = "Volkswagen_Caddy_VW32_2021-";
const DOOR_H = 1122;            // karoserie_model_reference.official_door_opening_height_mm (VW32/K-020)
const T = 30;
const D = 326;                  // id=3: hloubka 326 pro 30x30, euroboxy podelne
const D_SRC = 349;              // custom_shapes 534/535
const H = DOOR_H - 30;          // id=8: 1092 (konec profilu)
const TOP_Y = 840;              // horni konec zadni svislice (534/535), id=8 nemeni
const CAP_H = H - TOP_Y;        // 252
const CUTOUT_H = 330;           // 535
// vzdalenosti od steny (id=2: prvky u steny kotveny FIXNE ke stene, nezavisle na D)
const CAP_WALL_NEAR = D_SRC - 260;          // 89 (cap prava hrana 260 v 349)
const SLOUPEK_WALL_NEAR = D_SRC - 270;      // 79 (sloupek prava hrana 270 v 349)
const CAP_X = D - CAP_WALL_NEAR - T / 2;           // stred capu v lokalnim X
const SLOUPEK_X = D - SLOUPEK_WALL_NEAR - T / 2;   // stred sloupku
const PREPAZKA_BACKOFF = 10, PODBEH_CLEARANCE = 30, REAR_BACKOFF = 20, FLOOR_BACKOFF = 2, WALL_BACKOFF = 2;
const CLEAR_SPACING = { 1: 430, 2: 832, 3: 1232 };
const CONNECTOR_POS = { 1: [15, 415], 2: [15, 415, 816], 3: [15, 415, 816, 1217] };
const Q_ALONG_Z = [-0.707107, 0, 0, 0.707107];
const Q_ALONG_X = [0, 0, -0.707107, 0.707107];
const Q_ENDCAP_UP = [0.7071067811865475, 0, 0, 0.7071067811865475];
const CAP_FLANGE = 3;

function part(xC, yC, len, vertical, role) {
  return { part_id: "Object_7", position: [xC, yC, T / 2], quaternion: vertical ? [0, 0, 0, 1] : [0, 0, -0.707107, 0.707107], scale: [1, len / 1000, 1], role };
}
function buildPlain() {
  return [
    part(T / 2, H / 2, H, true, "predni-svislice"),
    part(D - T / 2, TOP_Y / 2, TOP_Y, true, "zadni-svislice-dolni"),
    part(D / 2, T / 2, D - 2 * T, false, "spojnice-dolni"),
    part(D / 2, TOP_Y - T / 2, D - 2 * T, false, "spojnice-horni"),
    part(CAP_X, TOP_Y + CAP_H / 2, CAP_H, true, "cap"),
  ];
}
// vyrezova noha: yNew = spodni konec zadni svislice (id=6), sb = pata sloupku (id=6 aplikovane na sloupek)
// wallNear = vzdalenost blizsi hrany sloupku od steny (vychozi 79 = noha 535); u varianty
// "sloupek az k podlaze" (Robert 2026-09-17) se sloupek odsune od steny, aby obesel podbeh.
function buildVyrez(yNew, sb, wallNear) {
  sb = sb || 0;
  const sloupekX = wallNear == null ? SLOUPEK_X : D - wallNear - T / 2;
  const sloupekLeft = sloupekX - T / 2;
  const parts = [
    part(T / 2, H / 2, H, true, "predni-svislice"),
    part(D / 2, TOP_Y - T / 2, D - 2 * T, false, "spojnice-horni"),
    part(CAP_X, TOP_Y + CAP_H / 2, CAP_H, true, "cap"),
    part(D - T / 2, (yNew + TOP_Y) / 2, TOP_Y - yNew, true, "zadni-svislice-nad-zarezem"),
    part(sloupekX, (sb + yNew) / 2, yNew - sb, true, "sloupek-pred-podbehem"),
    part((T + sloupekLeft) / 2, sb + T / 2, sloupekLeft - T, false, "spojnice-dolni"),
    // id=4 cast B: uzavirací pricka vyrezu - shora na sloupek, od predni svislice k zadni svislici
    part(D / 2, yNew + T / 2, D - 2 * T, false, "pricka-uzavreni-vyrezu"),
  ];
  return parts;
}

function makeCtx() {
  const engine = createEngine(BASE);
  const { collidesWithWalls, buildLegObject, boxL0, boxB0, mirror, dirZtoBulkhead } = engine;
  const sgn = mirror ? -1 : 1, dirAway = -dirZtoBulkhead;
  const ctx = { engine, collidesWithWalls, buildLegObject, boxL0, boxB0, mirror, dirZtoBulkhead, sgn, dirAway, offsetX: -D / 2, offsetY: boxB0.max.y / 2 - H / 2 };
  ctx.toWorld = (lp, aZ) => lp.map(p => ({ ...p, position: [ctx.offsetX + sgn * p.position[0], p.position[1] + ctx.offsetY, aZ + p.position[2]] }));
  ctx.objOf = parts => buildLegObject(parts);
  ctx.collides = parts => collidesWithWalls(buildLegObject(parts));
  // jeden svisly kus na lokalnim X, Y rozsah [y0,y1], v Z slabu nohy aZ
  ctx.piece = (localX, y0, y1, aZ) => [{ part_id: "Object_7", position: [ctx.offsetX + sgn * localX, (y0 + y1) / 2 + ctx.offsetY, aZ + T / 2], quaternion: [0, 0, 0, 1], scale: [1, (y1 - y0) / 1000, 1] }];
  return ctx;
}

function stepUntilCollision(testFn, dir, maxSteps, label, backoff) {
  let v = 0, hit = false;
  for (let s = 0; s < maxSteps; s++) { v += dir; if (testFn(v)) { hit = true; break; } }
  if (!hit) throw new Error(`${label}: zadna kolize po ${maxSteps} krocich`);
  const back = v - dir * backoff;
  if (testFn(back)) throw new Error(`${label}: po ${backoff}mm zpet stale koliduje`);
  return { value: back, hitAt: v };
}

// STEP 1: plna noha u prepazky - podlaha -> prepazka (10mm) -> stena (2mm)
function placeFrontLeg(ctx) {
  const plain = buildPlain();
  const L = ctx.boxL0;
  let aZ = (L.min.z + L.max.z) / 2 - T / 2;
  if (ctx.collides(ctx.toWorld(plain, aZ))) throw new Error("step1: start koliduje");
  const sY = stepUntilCollision(v => { ctx.offsetY += v; const c = ctx.collides(ctx.toWorld(plain, aZ)); ctx.offsetY -= v; return c; }, -1, 2500, "podlaha", FLOOR_BACKOFF);
  ctx.offsetY += sY.value;
  const sZ = stepUntilCollision(v => ctx.collides(ctx.toWorld(plain, aZ + v)), ctx.dirZtoBulkhead, 3500, "prepazka", PREPAZKA_BACKOFF);
  aZ += sZ.value;
  const sX = stepUntilCollision(v => { ctx.offsetX += v; const c = ctx.collides(ctx.toWorld(plain, aZ)); ctx.offsetX -= v; return c; }, ctx.mirror ? -1 : 1, 2500, "stena", WALL_BACKOFF);
  ctx.offsetX += sX.value;
  return { anchorZ: aZ, prepazkaHitZ: aZ - sZ.value + sZ.hitAt };
}

// id=6 fresh na dane Z: nejnizsi Y zadni svislice (+30 podbeh) a pata sloupku (+30)
function yNewWallAt(ctx, aZ) {
  if (!ctx.collides(ctx.piece(D - T / 2, 0, TOP_Y, aZ))) return 0;
  for (let b = TOP_Y - 1; b >= 0; b--) if (ctx.collides(ctx.piece(D - T / 2, b, TOP_Y, aZ))) return b + PODBEH_CLEARANCE;
  return 0;
}
function sloupekBottomAt(ctx, aZ, yNew) {
  if (yNew <= 0) return 0;
  if (!ctx.collides(ctx.piece(SLOUPEK_X, 0, yNew, aZ))) return 0;
  for (let b = yNew - 1; b >= 0; b--) if (ctx.collides(ctx.piece(SLOUPEK_X, b, yNew, aZ))) return b + PODBEH_CLEARANCE;
  return 0;
}
// Varianta "clenita noha se spodnim zadnim profilem az k podlaze" (Robert 2026-09-17):
// sloupek [0, yNew] se odsouva od steny po 1mm, dokud nekoliduje, pak +30mm rezerva od podbehu.
// Vraci vzdalenost blizsi hrany sloupku od steny, nebo null (spodni spojnice by nemela delku).
function sloupekKPodlazeWallNear(ctx, aZ, yNew) {
  const maxWallNear = D - 2 * T - 1; // spojnice-dolni mezi predni svislici a sloupkem musi mit delku > 0
  for (let w = SLOUPEK_WALL_NEAR; w <= maxWallNear; w++) {
    if (!ctx.collides(ctx.piece(D - w - T / 2, 0, yNew, aZ))) {
      const wr = w === SLOUPEK_WALL_NEAR ? w : w + PODBEH_CLEARANCE;
      if (wr > maxWallNear) return null;
      if (ctx.collides(ctx.piece(D - wr - T / 2, 0, yNew, aZ))) return null;
      return { wallNear: wr, prvniVolna: w };
    }
  }
  return null;
}
// existence probe (podbeh_bez_konce): pas pod TOP_Y u steny + cap + predni svislice (vsechny fixni kusy)
function existenceCollides(ctx, aZ) {
  return ctx.collides(ctx.piece(D - T / 2, TOP_Y - 40, TOP_Y, aZ)) || ctx.collides(ctx.piece(CAP_X, TOP_Y, H, aZ)) || ctx.collides(ctx.piece(T / 2, 0, H, aZ));
}
// typ nohy + adaptace na dane Z; null = noha tu nejde postavit
function legAt(ctx, aZ) {
  if (!ctx.collides(ctx.toWorld(buildPlain(), aZ))) return { type: "plain", anchorZ: aZ, yNew: null, sb: 0 };
  if (existenceCollides(ctx, aZ)) return null;
  const yNew = yNewWallAt(ctx, aZ);
  // yNew=0 pri kolizi plne nohy = prekazka neni u steny, vyrez nepomuze.
  // Horni mez TOP_Y-2T: pricka uzavreni vyrezu (yNew..yNew+T) se nesmi protnout se spojnici horni (TOP_Y-T..TOP_Y).
  if (yNew <= 0 || yNew > TOP_Y - 2 * T) return null;
  // 1) clenita noha s podperou zespodu (sloupek na vychozi vzdalenosti od steny, pata nad podbehem)
  const sb = sloupekBottomAt(ctx, aZ, yNew);
  if (yNew - sb >= T && !ctx.collides(ctx.toWorld(buildVyrez(yNew, sb), aZ))) {
    return { type: "vyrez", anchorZ: aZ, yNew, sb };
  }
  // 2) kdyz podpera zespodu nejde, zkusit sloupek k podlaze (odsunuty od steny) - pozice se nezahazuje predcasne
  const r = sloupekKPodlazeWallNear(ctx, aZ, yNew);
  if (r) {
    const leg = { type: "vyrez", anchorZ: aZ, yNew, sb: 0, wallNear: r.wallNear, sloupekPrvniVolna: r.prvniVolna };
    if (!ctx.collides(ctx.toWorld(legParts(leg), aZ))) return leg;
  }
  return null;
}
function legParts(leg) { return leg.type === "plain" ? buildPlain() : buildVyrez(leg.yNew, leg.sb, leg.wallNear); }

function railsFor(ctx, N, legFrom, legTo, railYCenter, colIdx, levelIdx) {
  // Platek nohy je vzdy [anchorZ, anchorZ+T] (bez ohledu na smer k prepazce), mezera mezi nohama je tedy
  // [mensi anchorZ + T, vetsi anchorZ]. (Drivejsi zapis legFrom.anchorZ + dirAway*T platil jen pro dirAway=+1.)
  const zFrom = Math.min(legFrom.anchorZ, legTo.anchorZ) + T, zTo = Math.max(legFrom.anchorZ, legTo.anchorZ);
  const len = zTo - zFrom, zc = (zFrom + zTo) / 2;
  const suf = colIdx == null ? "" : `-sloupec${colIdx}-patro${levelIdx}`;
  const y = railYCenter + ctx.offsetY;
  const parts = [
    { part_id: "Object_7", position: [ctx.offsetX + ctx.sgn * (T / 2), y, zc], quaternion: Q_ALONG_Z, scale: [1, len / 1000, 1], role: "nosnik" + suf },
    { part_id: "Object_7", position: [ctx.offsetX + ctx.sgn * (D - T / 2), y, zc], quaternion: Q_ALONG_Z, scale: [1, len / 1000, 1], role: "nosnik" + suf },
  ];
  // koty spojnic od zacatku nosniku = od nohy blize prepazce (legFrom)
  const conn = CONNECTOR_POS[N].map(lz => ctx.dirAway > 0 ? zFrom + lz : zTo - lz);
  conn.forEach(z => parts.push({ part_id: "Object_7", position: [ctx.offsetX + ctx.sgn * (D / 2), y, z], quaternion: Q_ALONG_X, scale: [1, (D - 2 * T) / 1000, 1], role: "spojnice" + suf }));
  return { parts, zFrom, zTo, len, connZ: conn };
}

module.exports = {
  BASE, DOOR_H, T, D, H, TOP_Y, CAP_H, CUTOUT_H, CAP_X, SLOUPEK_X, CAP_WALL_NEAR, SLOUPEK_WALL_NEAR,
  PREPAZKA_BACKOFF, PODBEH_CLEARANCE, REAR_BACKOFF, CLEAR_SPACING, CONNECTOR_POS, Q_ALONG_Z, Q_ALONG_X, Q_ENDCAP_UP, CAP_FLANGE,
  buildPlain, buildVyrez, sloupekKPodlazeWallNear, makeCtx, stepUntilCollision, placeFrontLeg, yNewWallAt, sloupekBottomAt, existenceCollides, legAt, legParts, railsFor,
};
