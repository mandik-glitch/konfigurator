// Regresni test webapp/js/scene/universal-import.js (import objektu FBX ve 3D
// scene) - bot8, 2026-09-30. Hlida invarianty "import NIKDY nemaze scenu"
// (Robert 2026-09-30: "kdyz importuju novy fbx, nesmi se nic ve scene smazat"):
// zadne clearAll(), nahled (dily tmpimport_*) se odstranuje jen sam, novy obsah
// se klade vedle stavajiciho (+X, mezera 300 mm), sceneUndoRestoring obali
// vlozeni (jeden "Krok zpet" vrati cely import), J/Delete patri importu jen
// kdyz nejsou oznacene skutecne dily sceny (+ kazdy test hlida, ze se nikdy
// nezavola clearAll()). 18 testu.
//
// Bez prohlizece: z universal-import.js vyrizne PRESNY text pomocnych funkci
// (podle znackovych komentaru nize) a spusti ho v Node vm proti stubum
// globalu sceny (placed, scene, camera, insertCustomShape, ...).
//
// Spusteni: node scripts/2026-09-30_universal_import_harness.js
//   -> na konci "18 testu proslo" (jinak "FAIL  - ..." a exit 1). Zamerne NENI v
//   scripts/2026-08-19_regression_scene/ (ta ma kontrakt "VSECH 10 SKRIPTU OK").
// Kdy: po KAZDE zmene webapp/js/scene/universal-import.js (a scene.html hacku
//   isImportPreviewEntry). Vazba na zdroj: rezy podle textu "  // --- nahled ve
//   scene: import NIKDY", "  // --- sum = ploche utrzky", "  function
//   getJoinSelection() {", "  async function applyPartsUpdate", "  // J/Delete
//   patri importu". Kdyz je prejmenujes/presunes, test spadne na "marker A/B:
//   ..." - uprav znacky TADY, neobchazej test. Stuby jsou ZJEDNODUSENE: kryji jen
//   to, co testovane funkce volaji; kdyz importer zacne volat novy global sceny,
//   dopln stub. Skutecny prohlizec tohle NENAHRAZUJE (viz skill import-fbx-scena).
const vm = require("vm"), fs = require("fs"), assert = require("assert"), path = require("path");
const src = fs.readFileSync(path.join(__dirname, "..", "webapp", "js", "scene", "universal-import.js"), "utf8");

function between(a, b) {
  const i = src.indexOf(a); if (i < 0) throw new Error("marker A: " + a);
  const j = src.indexOf(b, i + a.length); if (j < 0) throw new Error("marker B: " + b);
  return src.slice(i, j);
}
const helpers = between("  // --- nahled ve scene: import NIKDY", "  // --- sum = ploche utrzky");
const joinSel = between("  function getJoinSelection() {", "  async function applyPartsUpdate");
const kbStart = src.indexOf("  // J/Delete patri importu");
const kbEnd = src.indexOf("\n  });\n", kbStart) + 7;
const keyboard = src.slice(kbStart, kbEnd);
assert(keyboard.includes('document.addEventListener("keydown"'));

const ctx = vm.createContext({ console, setTimeout, Promise, JSON, Set, Map, Number, String, parseInt, Error });

// ---- stuby globalu sceny (top-level let/const/function jako v ostre scene) ----
vm.runInContext(`
  var window = globalThis;
  let placed = [];
  const selectedMoveEntries = new Set();
  var axisMoveSelectedEntries = new Set();
  let jointGroups = [];
  let currentAssemblyMeta = null;
  let sceneUndoRestoring = false;
  let sceneGeneration = 0;
  const SCENE_LAST_LOADED_KEY = "konfSceneLastLoadedAssembly";
  const __store = {};
  const localStorage = { getItem: k => (k in __store ? __store[k] : null), setItem: (k, v) => { __store[k] = String(v); }, removeItem: k => { delete __store[k]; } };
  let paintHoverEntry = null, paintHoverMesh = null;
  let dragState = null;
  var axisMoveDragState = null;
  var rotateActive = false;
  const scene = { removed: [], remove(o) { this.removed.push(o); } };
  const camera = { position: { x: 0, add(v) { this.x += v.x; } } };
  const controls = { target: { x: 0, add(v) { this.x += v.x; } }, updates: 0, update() { this.updates++; } };
  class Vector3 { constructor(x = 0) { this.x = x; } clone() { return new Vector3(this.x); } sub(v) { this.x -= v.x; return this; } add(v) { this.x += v.x; return this; } }
  const THREE = { Vector3 };
  const counters = { rebuildOcc: 0, endpoints: 0, dim: 0, summary: 0, selLabel: 0, axisBtn: 0, axisLabel: 0, syncHl: 0, releaseAll: [], releaseBroken: [] };
  const __forbidden = { clearAll: 0 };   // NENI v counters - reset() ty nuluje
  function clearAll() { __forbidden.clearAll++; }   // import ho NIKDY nesmi zavolat (kontroluje obal test())
  function rebuildOccupiedConnectors() { counters.rebuildOcc++; }
  function refreshEndpointMarkers() { counters.endpoints++; }
  function refreshDimLabels() { counters.dim++; }
  function refreshMoveSelectionLabel() { counters.selLabel++; }
  function refreshMoveAxisButtons() { counters.axisBtn++; }
  function refreshAxisMoveLabel() { counters.axisLabel++; }
  function syncCatalogSelectionHighlight() { counters.syncHl++; }
  function releaseAllJointsFor(e) { counters.releaseAll.push(e.part.id); }
  function releaseBrokenProfileJoints(e) { counters.releaseBroken.push(e.part.id); return 0; }
  function isImportPreviewEntry(e) { return !!(e && e.part && String(e.part.id).startsWith("tmpimport_")); }
  // zjednoduseny model Kroku zpet (stejna logika slotu jako captureSceneSnapshotForUndo)
  const undo = { slot: null, cur: null, steps: 0 };
  function refreshSummary() {
    counters.summary++;
    if (sceneUndoRestoring) return;
    const sig = JSON.stringify(placed.filter(e => !isImportPreviewEntry(e)).map(e => [e.part.id, e.object3d.position.x]));
    if (undo.cur && sig === undo.cur.sig) return;
    undo.slot = undo.cur; undo.cur = { sig }; undo.steps++;
  }
  function mkEntry(id, x, w) {
    return { part: { id }, w: w || 100, object3d: { position: new Vector3(x), userData: { basePos: new Vector3(x) } } };
  }
  function box(entries) { let mn = Infinity, mx = -Infinity; entries.forEach(e => { mn = Math.min(mn, e.object3d.position.x - e.w / 2); mx = Math.max(mx, e.object3d.position.x + e.w / 2); }); return { mn, mx }; }
  function bboxOfEntries(entries) { const b = box(entries); return { isEmpty() { return !entries.length; }, getCenter(t) { t.x = (b.mn + b.mx) / 2; return t; } }; }
  function applyAutoPlacementOffset(startIdx) {
    const ex = placed.slice(0, startIdx), ad = placed.slice(startIdx);
    if (!ex.length || !ad.length) return;
    const d = box(ex).mx - box(ad).mn + 300;
    ad.forEach(e => { e.object3d.position.x += d; });
  }
  async function insertCustomShape(shape, opts) {
    const myGen = sceneGeneration;
    const parts = shape.parts || [];
    if (!parts.length) return;
    currentAssemblyMeta = { id: shape.id == null ? null : shape.id, name: shape.name, source: shape.__source || null };
    if (shape.__persist) localStorage.setItem(SCENE_LAST_LOADED_KEY, "persisted:" + shape.id);
    for (const p of parts) {
      await new Promise(r => setTimeout(r, 2));
      if (sceneGeneration !== myGen) return;
      if (shape.__failAt === p.part_id) throw new Error("nacteni dilu selhalo");
      placed.push(mkEntry(p.part_id, p.x, p.w));
    }
    rebuildOccupiedConnectors(); refreshEndpointMarkers(); refreshDimLabels(); refreshSummary();
  }
`, ctx);

// ---- testovany kod: presny text z universal-import.js uvnitr strict IIFE ----
vm.runInContext(`
  const TMP_PREFIX = "tmpimport_";
  const state = { token: "tok", parts: [], building: false };
  const __catalog = { adds: 0, removes: 0 };
  function addTmpCatalogRows(parts) { __catalog.adds++; }
  function removeTmpCatalogRows() { __catalog.removes++; }
  function tmpPartsShape(parts) { return { name: "nahled importu", parts: parts.map(p => ({ part_id: TMP_PREFIX + p.i, x: p.x, w: p.w })) }; }
  const __doc = { handlers: {}, addEventListener(t, f) { this.handlers[t] = f; }, querySelectorAll() { return []; } };
  const __calls = { join: 0, remove: 0 };
  const T = (function () {
    "use strict";
    const document = __doc;
    const groups = [];
    function joinSelected() { __calls.join++; }
    function removeSelected() { __calls.remove++; }
${helpers}
${joinSel}
${keyboard}
    return { setGroups(a) { groups.length = 0; a.forEach(x => groups.push(x)); }, isTmpEntry, showPreview, hidePreview, addFinalShape, removeTmpEntries, addShapeToScene, getJoinSelection, sceneSelectionKinds, isTypingField, queueSceneOp };
  })();
`, ctx);

const run = (code) => vm.runInContext(code, ctx);
const reset = () => run(`
  placed.length = 0; selectedMoveEntries.clear(); axisMoveSelectedEntries.clear(); jointGroups = [];
  currentAssemblyMeta = null; sceneUndoRestoring = false; sceneGeneration = 0;
  Object.keys(__store).forEach(k => delete __store[k]);
  scene.removed.length = 0; dragState = null; axisMoveDragState = null; rotateActive = false; paintHoverEntry = null;
  undo.slot = null; undo.cur = null; undo.steps = 0; state.parts = []; state.token = "tok";
  Object.keys(counters).forEach(k => { counters[k] = Array.isArray(counters[k]) ? [] : 0; });
  controls.updates = 0; camera.position.x = 0; controls.target.x = 0; __calls.join = 0; __calls.remove = 0;
  __doc.querySelectorAll = () => []; T.setGroups([]);
  refreshSummary();
`);
const ids = () => run(`placed.map(e => e.part.id).join(",")`);
const xs = () => run(`placed.map(e => e.object3d.position.x).join(",")`);

let passed = 0;
async function test(name, fn) {
  reset();
  try {
    await fn();
    assert.strictEqual(run(`__forbidden.clearAll`), 0, "import zavolal clearAll() - nikdy nesmi mazat scenu");
    passed++; console.log("  ok  -", name);
  }
  catch (e) { console.log("FAIL  -", name, "\n       ", e.message); process.exitCode = 1; }
}

(async () => {
  console.log("=== import nikdy nemaze scenu: harness ===");

  await test("A: prazdna scena - nahled na puvodnich souradnicich, hidePreview vse uklidi vcetne meta", async () => {
    run(`state.parts = [{i:0,x:0,w:100},{i:1,x:200,w:100},{i:2,x:400,w:100}];`);
    const baseA = run(`undo.steps`);
    await run(`T.showPreview({pan:true})`);
    assert.strictEqual(ids(), "tmpimport_0,tmpimport_1,tmpimport_2");
    assert.strictEqual(xs(), "0,200,400", "v prazdne scene se nic neposouva");
    assert.strictEqual(run(`controls.updates`), 0, "kamera se v prazdne scene nehybe");
    assert.strictEqual(run(`currentAssemblyMeta && currentAssemblyMeta.name`), "nahled importu");
    assert.strictEqual(run(`undo.steps`), baseA, "nahled nevytvari krok zpet");
    assert.strictEqual(run(`sceneUndoRestoring`), false);
    await run(`T.hidePreview()`);
    assert.strictEqual(ids(), "");
    assert.strictEqual(run(`currentAssemblyMeta`), null, "meta nahledu se po odebrani uvolni");
    assert.strictEqual(run(`undo.steps`), baseA);
  });

  await test("B: scena s realnym obsahem - nic se nesmaze, nahled vedle (+X), meta i F5 klic zustanou", async () => {
    run(`placed.push(mkEntry("product_1", 0, 100), mkEntry("product_2", 500, 100));
         selectedMoveEntries.add(placed[0]);
         currentAssemblyMeta = { id: 572, name: "Stul", source: "product_assembly" };
         localStorage.setItem(SCENE_LAST_LOADED_KEY, "orig-key");
         refreshSummary();`);
    const real0 = run(`placed[0]`), real1 = run(`placed[1]`);
    run(`state.parts = [{i:0,x:0,w:100},{i:1,x:200,w:100}];`);
    const baseB = run(`undo.steps`);
    await run(`T.showPreview({pan:true})`);
    assert.strictEqual(ids(), "product_1,product_2,tmpimport_0,tmpimport_1");
    assert.strictEqual(run(`placed[0]`), real0); assert.strictEqual(run(`placed[1]`), real1);
    assert.strictEqual(xs().split(",").slice(0, 2).join(","), "0,500", "realne dily se nepohly");
    const tmpX = run(`placed.slice(2).map(e => e.object3d.position.x)`);
    // existujici max = 550, pridany min = -50 => posun 550 + 50 + 300 = 900
    assert.deepStrictEqual(Array.from(tmpX), [900, 1100]);
    assert.strictEqual(run(`placed[2].object3d.userData.basePos.x`), 900, "basePos obnoven pro rozlozeny pohled");
    assert.strictEqual(run(`currentAssemblyMeta.id`), 572, "identita otevrene sestavy nezmenena");
    assert.strictEqual(run(`localStorage.getItem(SCENE_LAST_LOADED_KEY)`), "orig-key");
    assert.strictEqual(run(`selectedMoveEntries.has(placed[0])`), true, "realny vyber zustal");
    assert.strictEqual(run(`undo.steps`), baseB, "nahled nevytvari krok zpet ani vedle realneho obsahu");
    assert.ok(run(`controls.updates`) >= 1, "prvni nahled presunul pohled");
    assert.ok(run(`controls.target.x`) > 500, "pohled na nahled");
    assert.deepStrictEqual(Array.from(run(`counters.releaseBroken`)), ["tmpimport_0", "tmpimport_1"]);
    await run(`T.hidePreview()`);
    assert.strictEqual(ids(), "product_1,product_2");
    assert.strictEqual(run(`currentAssemblyMeta.id`), 572);
    assert.strictEqual(run(`selectedMoveEntries.size`), 1);
    assert.strictEqual(run(`undo.steps`), baseB);
  });

  await test("C2: stejne jako C, bez pocitani odstranenych (jen vysledny stav)", async () => {
    run(`placed.push(mkEntry("product_1", 0, 100)); refreshSummary();`);
    run(`state.parts = [{i:0,x:0,w:100},{i:1,x:200,w:100},{i:2,x:400,w:100}];`);
    const p1 = run(`T.showPreview()`);
    run(`state.parts = [{i:0,x:0,w:100},{i:3,x:200,w:100}];`);
    const p2 = run(`T.showPreview()`);
    run(`state.parts = [{i:0,x:0,w:100},{i:3,x:200,w:100},{i:4,x:300,w:100}];`);
    const p3 = run(`T.showPreview()`);
    await Promise.all([p1, p2, p3]);
    assert.strictEqual(ids(), "product_1,tmpimport_0,tmpimport_3,tmpimport_4");
    assert.strictEqual(run(`placed.filter(T.isTmpEntry).length`), 3);
  });

  await test("D: odebrani nahledu cisti JEN dily nahledu z vyberu/skupin/hover; realny vyber zustane", async () => {
    run(`placed.push(mkEntry("product_1", 0, 100)); refreshSummary(); state.parts = [{i:0,x:0,w:100},{i:1,x:200,w:100}];`);
    await run(`T.showPreview()`);
    run(`selectedMoveEntries.add(placed[0]); selectedMoveEntries.add(placed[1]); axisMoveSelectedEntries.add(placed[2]);
         jointGroups = [new Set([placed[0], placed[1]]), new Set([placed[1], placed[2]]), new Set([placed[2], placed[1]])];
         paintHoverEntry = placed[1];`);
    const c0 = run(`counters.selLabel`);
    await run(`T.hidePreview()`);
    assert.strictEqual(ids(), "product_1");
    assert.strictEqual(run(`selectedMoveEntries.size`), 1);
    assert.strictEqual(run(`selectedMoveEntries.has(placed[0])`), true);
    assert.strictEqual(run(`axisMoveSelectedEntries.size`), 0);
    assert.strictEqual(run(`jointGroups.length`), 0, "skupiny s mene nez 2 cleny zrusene");
    assert.strictEqual(run(`paintHoverEntry`), null);
    assert.ok(run(`counters.selLabel`) > c0, "stitek vyberu prepocten");
    assert.deepStrictEqual(Array.from(run(`counters.releaseAll`)).sort(), ["tmpimport_0", "tmpimport_1"]);
  });

  await test("E: finalni tvar vedle obsahu - jeden krok zpet, meta+F5 klic zachovany, vysledek true", async () => {
    run(`placed.push(mkEntry("product_1", 0, 100)); currentAssemblyMeta = {id: 9, name: "Puvodni", source: "custom_shape"};
         localStorage.setItem(SCENE_LAST_LOADED_KEY, "orig"); refreshSummary();`);
    const baseE = run(`undo.steps`);
    const r = await run(`T.addFinalShape({ id: 77, name: "Novy", __persist: true, __source: "custom_shape", parts: [{part_id:"product_50", x:0, w:100},{part_id:"product_51", x:150, w:100}] })`);
    assert.strictEqual(r, true);
    assert.strictEqual(ids(), "product_1,product_50,product_51");
    assert.strictEqual(xs(), "0,400,550", "posun = 50 (hrana existujiciho) + 50 + 300 = 400");
    assert.strictEqual(run(`currentAssemblyMeta.id`), 9);
    assert.strictEqual(run(`localStorage.getItem(SCENE_LAST_LOADED_KEY)`), "orig");
    assert.strictEqual(run(`undo.steps`), baseE + 1, "presne jeden krok zpet");
    assert.strictEqual(run(`undo.slot.sig.includes("product_50")`), false, "slot = stav pred importem");
    assert.strictEqual(run(`undo.cur.sig.includes("product_51")`), true);
    assert.strictEqual(run(`sceneUndoRestoring`), false);
    assert.strictEqual(run(`placed[1].object3d.userData.basePos.x`), 400);
  });

  await test("E2: finalni tvar do PRAZDNE sceny - puvodni chovani (identita noveho tvaru, F5 klic, bez posunu)", async () => {
    const r = await run(`T.addFinalShape({ id: 77, name: "Novy", __persist: true, __source: "custom_shape", parts: [{part_id:"product_50", x:0, w:100}] })`);
    assert.strictEqual(r, false);
    assert.strictEqual(xs(), "0");
    assert.strictEqual(run(`currentAssemblyMeta.id`), 77);
    assert.strictEqual(run(`localStorage.getItem(SCENE_LAST_LOADED_KEY)`), "persisted:77");
  });

  await test("E3: vlozeni bez puvodniho F5 klice - klic se po vlozeni vedle obsahu zase odstrani", async () => {
    run(`placed.push(mkEntry("product_1", 0, 100)); refreshSummary();`);
    await run(`T.addFinalShape({ id: 77, name: "Novy", __persist: true, parts: [{part_id:"product_50", x:0, w:100}] })`);
    assert.strictEqual(run(`localStorage.getItem(SCENE_LAST_LOADED_KEY)`), null);
    assert.strictEqual(run(`currentAssemblyMeta`), null, "puvodne zadna otevrena sestava -> zadna ani ted");
  });

  await test("F: chyba pri nacitani dilu - flag se vrati, meta obnovena, fronta jede dal", async () => {
    run(`placed.push(mkEntry("product_1", 0, 100)); currentAssemblyMeta = {id: 9, name: "P", source: "x"}; refreshSummary();`);
    let threw = false;
    try { await run(`T.addFinalShape({ id: 5, name: "Vadny", parts: [{part_id:"a", x:0, w:10},{part_id:"b", x:20, w:10}], __failAt: "b" })`); }
    catch (e) { threw = true; assert.ok(/selhalo/.test(e.message)); }
    assert.ok(threw, "chyba se propaguje volajicimu (try/catch v build)");
    assert.strictEqual(run(`sceneUndoRestoring`), false);
    assert.strictEqual(run(`currentAssemblyMeta.id`), 9);
    run(`state.parts = [{i:0,x:0,w:100}];`);
    await run(`T.showPreview()`);   // fronta nezustala zablokovana
    assert.ok(ids().includes("tmpimport_0"));
  });

  await test("G: behem vkladani uzivatel scenu vymaze (sceneGeneration) - zadny posun, vysledek false, flag vracen", async () => {
    run(`placed.push(mkEntry("product_1", 0, 100)); refreshSummary();`);
    const pr = run(`T.addFinalShape({ id: 5, name: "X", parts: [{part_id:"a", x:0, w:10},{part_id:"b", x:20, w:10}] })`);
    await new Promise(r => setTimeout(r, 1));
    run(`sceneGeneration++; placed.length = 0;`);   // clearAll()
    const r = await pr;
    assert.strictEqual(r, false);
    assert.strictEqual(run(`sceneUndoRestoring`), false);
  });

  await test("H: getJoinSelection bere JEN dily nahledu z vyberu sceny (realne ne)", async () => {
    run(`placed.push(mkEntry("product_1", 0, 100)); refreshSummary(); state.parts = [{i:0,x:0,w:100},{i:7,x:200,w:100}];`);
    run(`placed.push(mkEntry("profil_20x80", -300, 100));`);   // id po orezu prefixu = "80" (past: realny dil nesmi dat index 80)
    await run(`T.showPreview()`);
    run(`selectedMoveEntries.add(placed[0]); selectedMoveEntries.add(placed[1]); selectedMoveEntries.add(placed[3]); axisMoveSelectedEntries.add(placed[2]);`);
    assert.deepStrictEqual(Array.from(run(`T.getJoinSelection()`)), [0, 7]);
    const k = run(`T.sceneSelectionKinds()`);
    assert.strictEqual(k.real, true); assert.strictEqual(k.tmp, true);
  });

  await test("I: prvni nahled vedle obsahu posune pohled; prepocet bez pan ho nehybe", async () => {
    run(`placed.push(mkEntry("product_1", 0, 100)); refreshSummary(); state.parts = [{i:0,x:0,w:100}];`);
    await run(`T.showPreview()`);
    assert.strictEqual(run(`controls.updates`), 0);
    await run(`T.showPreview({pan:true})`);
    assert.strictEqual(run(`controls.updates`), 1);
  });

  // ---- klavesy ----
  function key(k, opts) {
    const o = Object.assign({ key: k, ctrlKey: false, metaKey: false, altKey: false, target: { tagName: "BODY", closest: () => null }, prevented: 0, stopped: 0 }, opts || {});
    o.preventDefault = () => { o.prevented++; }; o.stopPropagation = () => { o.stopped++; };
    return o;
  }
  const fire = (ev) => { global.__ev = ev; ctx.__ev = ev; run(`__doc.handlers.keydown(__ev)`); return ev; };
  const setup = async (realSel, tmpSel, tmpChecked) => {
    run(`placed.push(mkEntry("product_1", 0, 100)); refreshSummary(); state.parts = [{i:0,x:0,w:100},{i:1,x:200,w:100}];`);
    await run(`T.showPreview()`);
    if (realSel) run(`selectedMoveEntries.add(placed[0]);`);
    if (tmpSel) run(`selectedMoveEntries.add(placed[1]);`);
    if (tmpChecked) run(`__doc.querySelectorAll = () => [{ dataset: { key: "k" }, querySelector: () => ({ checked: true }) }]; T.setGroups([{ key: "k", members: [0, 1] }]);`);
  };

  await test("K1: skutecny dil ve scene vybran, dily importu NE -> J/Delete patri scene (import nezasahuje)", async () => {
    await setup(true, false, false);
    ["Delete", "j"].forEach(k => { const ev = fire(key(k)); assert.strictEqual(ev.prevented, 0); assert.strictEqual(ev.stopped, 0); });
    assert.strictEqual(run(`__calls.join + __calls.remove`), 0);
  });

  await test("K2: vybrany dil importu ve scene -> import zpracuje klavesu a zastavi scenu", async () => {
    await setup(false, true, false);
    const ev = fire(key("Delete"));
    assert.strictEqual(ev.prevented, 1); assert.strictEqual(ev.stopped, 1);
    assert.strictEqual(run(`__calls.remove`), 1);
    const ev2 = fire(key("J"));
    assert.strictEqual(run(`__calls.join`), 1); assert.strictEqual(ev2.stopped, 1);
  });

  await test("K3: smiseny vyber (realny + dil importu) -> import zpracuje JEN sve, scena Delete nedostane", async () => {
    await setup(true, true, false);
    const ev = fire(key("Delete"));
    assert.strictEqual(ev.stopped, 1); assert.strictEqual(run(`__calls.remove`), 1);
  });

  await test("K4: realny vyber + zaskrtnute radky importu, fokus MIMO panel -> klavesa patri scene", async () => {
    const s = await setup(true, false, true);
    const ev = fire(key("Delete"));
    assert.strictEqual(ev.stopped, 0); assert.strictEqual(run(`__calls.remove`), 0);
  });

  await test("K5: stejne, ale fokus UVNITR panelu importu -> import zpracuje (zaskrtnute radky)", async () => {
    await setup(true, false, true);
    const ev = fire(key("Delete", { target: { tagName: "BUTTON", closest: (sel) => (/universalImportSection/.test(sel) ? {} : null) } }));
    assert.strictEqual(ev.stopped, 1); assert.strictEqual(run(`__calls.remove`), 1);
  });

  await test("K6: pisu do textoveho pole / tahnu dil / Ctrl / bez tokenu -> import nereaguje", async () => {
    await setup(false, true, false);
    [
      key("Delete", { target: { tagName: "INPUT", type: "text", closest: () => null } }),
      key("Delete", { target: { tagName: "TEXTAREA", closest: () => null } }),
      key("j", { target: { tagName: "SELECT", closest: () => null } }),
      key("Delete", { ctrlKey: true }),
    ].forEach(ev => { fire(ev); assert.strictEqual(ev.prevented, 0); });
    run(`dragState = {}`); let ev = fire(key("Delete")); assert.strictEqual(ev.prevented, 0); run(`dragState = null`);
    run(`axisMoveDragState = {}`); ev = fire(key("Delete")); assert.strictEqual(ev.prevented, 0); run(`axisMoveDragState = null`);
    run(`rotateActive = true`); ev = fire(key("Delete")); assert.strictEqual(ev.prevented, 0); run(`rotateActive = false`);
    run(`state.token = null`); ev = fire(key("Delete")); assert.strictEqual(ev.prevented, 0);
    assert.strictEqual(run(`__calls.join + __calls.remove`), 0);
    // checkbox / tlacitko / SELECT pri Delete fokus neberou klavesam -> zpracuje
    run(`state.token = "tok"`);
    ev = fire(key("Delete", { target: { tagName: "INPUT", type: "checkbox", closest: () => null } })); assert.strictEqual(ev.stopped, 1);
    ev = fire(key("Delete", { target: { tagName: "SELECT", closest: () => null } })); assert.strictEqual(ev.stopped, 1);
  });

  await test("K7: nic neoznaceno (zadne dily importu) -> klavesa propada scene", async () => {
    await setup(false, false, false);
    const ev = fire(key("Delete")); assert.strictEqual(ev.prevented, 0); assert.strictEqual(ev.stopped, 0);
  });

  // ---- skupiny a vyber karty (bot8, 2026-10-01): presny text funkci z panelu ----
  const groupSync = between('  // --- skupina = "jedno mapovani pro vsechny"', "  function groupOfPart(i)");
  const candidates = between("  function catalogCandidates(q) {", "  function wireSearch(");
  const gctx = vm.createContext({ Object });
  vm.runInContext(`
    const TMP_PREFIX = "tmpimport_";
    const state = { decisions: {} };
    let groups = [];
    let saves = 0;
    function scheduleDraftSave() { saves++; }
    let CATALOG = [];
    ${groupSync}
    ${candidates}
  `, gctx);
  const g = (code) => vm.runInContext(code, gctx);

  await test("G1: skupina ×2 - clen bez rozhodnuti prevezme rozhodnuti skupiny (perfopanel #30)", async () => {
    g(`state.decisions = { 29: { action: "existing", part_id: "product_4931" } };
       groups = [{ rep: { i: 29 }, members: [29, 30] }, { rep: { i: 5 }, members: [5, 6] }]; saves = 0;`);
    assert.strictEqual(g(`syncGroupDecisions()`), true);
    assert.strictEqual(g(`state.decisions[30] && state.decisions[30].part_id`), "product_4931");
    assert.strictEqual(g(`state.decisions[30] === state.decisions[29]`), false, "kopie, ne sdileny objekt");
    assert.strictEqual(g(`5 in state.decisions || 6 in state.decisions`), false, "skupina bez rozhodnuti zustava skip");
    assert.strictEqual(g(`saves`), 1);
    // rozhodnuti jen u clena (ne u reprezentanta) se taky rozsiri; vlastni rozhodnuti clena zustava
    g(`state.decisions = { 6: { action: "new", sku: "X.DIL-006" }, 30: { action: "existing", part_id: "product_1" },
                           29: { action: "existing", part_id: "product_4931" } };`);
    g(`syncGroupDecisions()`);
    assert.strictEqual(g(`state.decisions[5].sku`), "X.DIL-006");
    assert.strictEqual(g(`state.decisions[30].part_id`), "product_1");
    assert.strictEqual(g(`syncGroupDecisions()`), false, "druhe volani nic nemeni");
  });

  await test("G2: vyber karty nenabizi karty bez 3D modelu (_PENDING_) ani bez souboru", async () => {
    g(`CATALOG = [
        { id: "profil_25x25", name: "Profil 25x25mm", file: "katalog/_PENDING_profil_25x25.glb?v=1" },
        { id: "Object_7", name: "Profil 30x30mm", file: "katalog/Object_7.glb?v=1" },
        { id: "product_5", name: "Profil bez modelu", file: null },
        { id: "tmpimport_3", name: "Profil nahled", file: "x.glb" }];`);
    assert.strictEqual(g(`catalogCandidates("profil").map(p => p.id).join(",")`), "Object_7");
  });

  await test("G3: merge-small nejdriv rozsiri rozhodnuti skupin (drobne cleny skupiny se neprilepi)", async () => {
    const body = between("  async function mergeSmall(quiet) {", "    try {");
    const iSync = body.indexOf("syncGroupDecisions()"), iSmall = body.indexOf("smallIds()");
    assert(iSync > 0 && iSmall > 0 && iSync < iSmall, "syncGroupDecisions() musi byt pred smallIds()");
    assert(body.indexOf("buildGroups()") >= 0 && body.indexOf("buildGroups()") < iSync, "buildGroups() pred syncGroupDecisions()");
  });

  await test("G4: skupina s ruznymi rozhodnutimi se pozna (panel to hlasi)", async () => {
    g(`state.decisions = { 1: { action: "new", sku: "X.DIL-000" }, 2: { action: "new", sku: "X.DIL-002" } };
       groups = [{ rep: { i: 1 }, members: [1, 2] }];`);
    assert.strictEqual(g(`groupDecisionsMixed(groups[0])`), 2);
    g(`state.decisions[2] = { action: "new", sku: "X.DIL-000" };`);
    assert.strictEqual(g(`groupDecisionsMixed(groups[0])`), 0);
    g(`delete state.decisions[2];`);
    assert.strictEqual(g(`groupDecisionsMixed(groups[0])`), 2, "prirazeno vs. preskocit = ruzne");
  });

  console.log(passed + " testu proslo" + (process.exitCode ? " - NEKTERE SELHALY" : ""));
})();
