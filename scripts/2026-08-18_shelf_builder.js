// Parametrizovaný "shelf builder" - police/regál bez desek, postavený na
// scripts/2026-08-18_scene_geometry_lib.js. Ukázka toho, jak se dá
// knihovna použít pro celou třídu tvarů, ne jen jeden jednorázový test.
//
// Konstrukční konvence (viz VLASTNOSTI_PROFILU.md "Pravidlo profilů"):
// - 4 průběžné nohy, VŠECHNA patra jsou stejná (T-styl, boční/průchozí
//   spoj, rám zkrácený na vnitřní rozpon) - ŽÁDNÉ patro není "cap"
//   (Robert 2026-08-18: "nejvyšší police nemá důvod být jiná než ty
//   spodní... necháváme nohám čela nahoře volné jako vespod").
// - Noha má volné čelo na OBOU koncích (nahoře i dole) - nic ji
//   nezavírá, ani nejvyšší patro.
//
// Použití: `npm install` v ROOTU repa (/opt/konfigurator, ne ve scripts/ -
// viz package.json), pak
//   `node -e "require('./2026-08-18_shelf_builder.js').demo()"`
// nebo požadovat `buildShelf` z vlastního skriptu.
const {
  THREE, baseQuaternion, computeConnectorsLocal, crossAxisHalfWidthTowardDirection,
  worldConnectorsOf, registerJoint, applyLengthScale,
  mkProfileEntry, boxOf, buildRectFrameEntries,
  touchReport, formatTouchReport, fullCollisionCheck, serializeToCustomShapeParts,
} = require("./2026-08-18_scene_geometry_lib.js");

/**
 * opts: {
 *   partId: string (katalogové part_id, musí existovat ve fetch_katalog_parts),
 *   dimX: number (čtvercový průřez profilu, mm - ověř si skutečné
 *         rozměry z .glb, VLASTNOSTI_PROFILU.md 2an krok 2, nehádej),
 *   Lx, Ly: number (vnější půdorys, mm),
 *   levelHeights: number[] (Y-výšky VŠECH pater, vč. nejvyššího),
 *   legOverhang: number (o kolik noha přečnívá NAD nejvyšším patrem -
 *         volný konec; výchozí = stejné jako mezera pod nejnižším patrem),
 * }
 * Vrací { placed, posts, levels } - placed je pole entries pro
 * serializeToCustomShapeParts().
 */
function buildShelf(opts) {
  const { partId, dimX, Lx, Ly, levelHeights, legOverhang } = opts;
  const overhang = legOverhang != null ? legOverhang : (levelHeights[0] || dimX * 3);
  const totalHeight = Math.max(...levelHeights) + overhang;
  const DIM_X = dimX, DIM_Y = 1000, DIM_Z = dimX;

  function mkEntry() { return mkProfileEntry(partId, DIM_X, DIM_Z, DIM_Y); }

  function shiftFrame(frame, y) {
    [frame.entryA, frame.entryB, frame.entryC, frame.entryD].forEach(e => {
      e.object3d.position.y += y;
      e.object3d.updateMatrixWorld(true);
    });
  }

  // "Pravidlo T-styl spoj" (VLASTNOSTI_PROFILU.md) - připojovaný rám se
  // zkracuje o CELOU šířku průchozí nohy (ne jen o půlku), jinak dojde
  // ke skutečnému zanoření (appka to nepozná z pouhého "gap=0 na
  // dotykové ose", je nutné zkontrolovat překryv na všech 3 osách -
  // viz touchReport/isValidFlushTouch v knihovně).
  function buildInnerFrame() {
    const innerLy = Ly - 2 * DIM_X;
    const f = buildRectFrameEntries(mkEntry, innerLy, Lx);
    [f.entryA, f.entryB, f.entryC, f.entryD].forEach(e => {
      e.object3d.position.z += DIM_X;
      e.object3d.updateMatrixWorld(true);
    });
    return f;
  }

  const bottomFrameRef = buildRectFrameEntries(mkEntry, Ly, Lx); // jen pro X/Z odkaz rohu noh
  const cornerSpecs = [
    { entry: bottomFrameRef.entryA, connIdx: 0 },
    { entry: bottomFrameRef.entryA, connIdx: 1 },
    { entry: bottomFrameRef.entryB, connIdx: 0 },
    { entry: bottomFrameRef.entryB, connIdx: 1 },
  ];

  const legVertQuat = baseQuaternion(0, "vertical");
  const posts = [];
  for (let i = 0; i < 4; i++) {
    const spec = cornerSpecs[i];
    const legEntry = mkEntry();
    const obj = legEntry.object3d;
    obj.quaternion.copy(legVertQuat);
    const cornerWorld = worldConnectorsOf(spec.entry)[spec.connIdx];
    const cornerNormalWorld = cornerWorld.normal.clone();
    const legHalf = crossAxisHalfWidthTowardDirection(legEntry.connectorsLocal, obj.quaternion, cornerNormalWorld);
    const xz = cornerWorld.point.clone().addScaledVector(cornerNormalWorld, -legHalf);
    const legL0 = legEntry.connectorsLocal[0].point.distanceTo(legEntry.connectorsLocal[1].point);
    obj.position.set(xz.x, 0, xz.z);
    obj.updateMatrixWorld(true);
    applyLengthScale(legEntry, totalHeight / legL0, 1);
    const bottomNow = worldConnectorsOf(legEntry)[1].point.y;
    obj.position.y += -bottomNow; // volný spodek přesně na Y=0 - noha se zespoda NEUZAVÍRÁ
    obj.updateMatrixWorld(true);
    legEntry.usedConn = new Set([0]);
    legEntry.hiddenEndConn = new Set([0]);
    legEntry.wasAttached = true;
    legEntry.vertical = true;
    posts.push(legEntry);
  }
  // (Konektor 1 - vrchol - zůstává VŽDY volný taky, `legOverhang` mm
  // nad nejvyšším patrem - noha se ani SHORA neuzavírá, viz komentář
  // u funkce výše.)

  const levels = [];
  levelHeights.forEach(h => {
    const f = buildInnerFrame();
    shiftFrame(f, h);
    levels.push(f);
    const specsFor = idx => [
      { entry: f.entryA, connIdx: 0 }, { entry: f.entryA, connIdx: 1 },
      { entry: f.entryB, connIdx: 0 }, { entry: f.entryB, connIdx: 1 },
    ][idx];
    posts.forEach((post, i) => {
      const s = specsFor(i);
      registerJoint(s.entry, s.connIdx, post, 2);
    });
  });

  const allFrameEntries = levels.flatMap(f => [f.entryA, f.entryB, f.entryC, f.entryD]);
  const placed = [...allFrameEntries, ...posts];
  return { placed, posts, levels, cornerSpecs };
}

// Ověří kompletní sestavu - vypíše touchReport pro každý sloupek×patro
// (očekáváno: x/z plný překryv = průřez, y gap=0/overlap=0 na
// dotykové rovině) a plný kolizní test. Vrátí počet nalezených
// (nechtěných) kolizí - 0 = OK.
function verifyShelf(shelf) {
  const { placed, posts, levels, cornerSpecs } = shelf;
  const idxOf = new Map(placed.map((e, i) => [e, i]));
  const definedPairs = new Set();
  levels.forEach(f => {
    [[f.entryA, f.entryC], [f.entryC, f.entryB], [f.entryA, f.entryD], [f.entryD, f.entryB]].forEach(([a, b]) => {
      definedPairs.add(`${idxOf.get(a)}-${idxOf.get(b)}`);
    });
    const specsFor = idx => [
      { entry: f.entryA, connIdx: 0 }, { entry: f.entryA, connIdx: 1 },
      { entry: f.entryB, connIdx: 0 }, { entry: f.entryB, connIdx: 1 },
    ][idx];
    posts.forEach((post, i) => definedPairs.add(`${idxOf.get(specsFor(i).entry)}-${idxOf.get(post)}`));
  });
  levels.forEach((f, li) => {
    const specsFor = idx => [
      { entry: f.entryA, connIdx: 0 }, { entry: f.entryA, connIdx: 1 },
      { entry: f.entryB, connIdx: 0 }, { entry: f.entryB, connIdx: 1 },
    ][idx];
    posts.forEach((post, i) => {
      const report = touchReport(specsFor(i).entry, post);
      console.log(`  patro${li + 1} sloupek${i + 1}: ${formatTouchReport(report)}`);
    });
  });
  const collisions = fullCollisionCheck(placed, definedPairs);
  collisions.forEach(c => console.log(`  KOLIZE dil${c.i} x dil${c.j}: ${c.size.map(v => v.toFixed(1)).join("x")}mm`));
  console.log(`  Dílů: ${placed.length} | Kolizí: ${collisions.length === 0 ? "0 (OK)" : collisions.length}`);
  return collisions.length;
}

function demo() {
  const shelf = buildShelf({
    partId: "Object_7", dimX: 30, Lx: 400, Ly: 500,
    levelHeights: [90, 450, 810], legOverhang: 90,
  });
  verifyShelf(shelf);
  return serializeToCustomShapeParts(shelf.placed);
}

module.exports = { buildShelf, verifyShelf, demo };

if (require.main === module) {
  demo();
}
