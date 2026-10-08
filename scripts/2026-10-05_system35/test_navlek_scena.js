// Navlek nohou (jekl 40x40x2, system 35) a "Vlozit do Sceny" (bot10, 2026-10-05): navlek a jeho zaslepka NEJSOU v katalogu Sceny - insertCustomShape by pri neznamem dilu prerusil vkladani
// (alert + nedokoncena sestava), proto je prijemce stolu (webapp/js/scene/stul-konfigurator.js) pred vlozenim odfiltruje a PREPOCITA indexy `lic_peers` a `attached_to.prof` ostatnich dilu.
// Bez prohlizece (Node + vm, atrapa sceny jako v test_stul_panel.js); odpovedi serveru dela SKUTECNA Python logika (_odpoved_cli.py = api/stul_konfigurator.py).
// Spusteni: node scripts/2026-10-05_system35/test_navlek_scena.js   (kandidat: STUL_JS=/cesta/stul-konfigurator.js)
const vm = require("vm"), fs = require("fs"), path = require("path"), assert = require("assert"), cp = require("child_process");
const REPO = path.join(__dirname, "..", "..");
const jsFile = process.env.STUL_JS || path.join(REPO, "webapp", "js", "scene", "stul-konfigurator.js");
const src = fs.readFileSync(jsFile, "utf8");
const PY = path.join(REPO, "api", "venv", "bin", "python3");
const CLI = path.join(REPO, "scripts", "2026-10-02_stul_testy", "_odpoved_cli.py");

let passed = 0, failed = 0;
async function test(name, fn) {
  try { await fn(); passed++; console.log("  ok  -", name); }
  catch (e) { failed++; process.exitCode = 1; console.log("FAIL  -", name, "\n       ", e && e.stack ? e.stack.split("\n").slice(0, 3).join("\n        ") : e); }
}

function makeEnv() {
  const ids = {};
  class El {
    constructor(tag) { this.tag = tag; this.children = []; this.attrs = {}; this.handlers = {}; this.textContent = ""; this.value = ""; this.checked = false; this.disabled = false; this.style = {}; }
    setAttribute(k, v) { this.attrs[k] = v; if (k === "id") ids[v] = this; }
    appendChild(c) { this.children.push(c); return c; }
    addEventListener(t, f) { (this.handlers[t] = this.handlers[t] || []).push(f); }
    get id() { return this.attrs.id; }
  }
  const section = new El("div"); section.setAttribute("id", "stulKonfSection"); ids.stulKonfSection = section;
  const calls = { insert: [] };
  const ctx = {
    console, Promise, Math, Number, String, Object, Array, Set, JSON, Error, encodeURIComponent, URL, URLSearchParams, Date,
    BroadcastChannel: class { constructor() {} postMessage() {} },
    location: { search: "", href: "http://x/scene.html", pathname: "/scene.html", hash: "" }, history: { replaceState() {} }, open() {},
    document: { readyState: "complete", getElementById: id => ids[id] || null, createElement: t => new El(t), createTextNode: t => { const e = new El("#text"); e.textContent = t; return e; }, addEventListener() {} },
    setTimeout: () => 1, clearTimeout: () => {},
    localStorage: (() => { const m = {}; return { getItem: k => m[k] == null ? null : m[k], setItem: (k, v) => { m[k] = v; }, removeItem: k => { delete m[k]; } }; })(),
    SCENE_LAST_LOADED_KEY: "SCENE_KEY", placed: [], scene: { remove() {} }, CATALOG: [{ id: "Object_7" }], currentAssemblyMeta: null, sceneUndoRestoring: false, sceneGeneration: 1,
    selectedMoveEntries: new Set(), axisMoveSelectedEntries: new Set(), jointGroups: [],
    rebuildOccupiedConnectors() {}, refreshEndpointMarkers() {}, refreshDimLabels() {}, refreshMoveSelectionLabel() {}, refreshMoveAxisButtons() {}, syncCatalogSelectionHighlight() {},
    releaseAllJointsFor() {}, releaseBrokenProfileJoints() {}, initFloatingShapesWindow() {}, applyAutoPlacementOffset() {},
    bboxOfEntries(entries) { const b = { min: { x: Infinity, y: Infinity, z: Infinity }, isEmpty() { return !entries.length; } }; return b; },
    async insertCustomShape(shape, o) {
      calls.insert.push({ n: shape.parts.length, parts: shape.parts, opts: o });
      shape.parts.forEach(p => ctx.placed.push({ part: { id: p.part_id }, spec: p, object3d: { position: { x: p.position[0], y: p.position[1], z: p.position[2], set() {}, clone() { return {}; } }, userData: {} } }));
    },
  };
  ctx.window = ctx;
  ctx.window.refreshSummary = () => {};
  vm.createContext(ctx);
  vm.runInContext(src, ctx, { filename: "stul-konfigurator.js" });
  return { ctx, calls, K: ctx.StulKonf };
}

function odpoved(q) { return JSON.parse(cp.execFileSync(PY, [CLI, q], { encoding: "utf8", maxBuffer: 64 * 1024 * 1024 })); }
const NAV = new Set(["jekl_40x40x2", "jekl_zaslepka_40"]);

(async () => {
  const e = makeEnv();
  assert.ok(e.K && typeof e.K.shapeFromData === "function", "StulKonf.shapeFromData existuje");
  const data = odpoved("system=35&navlek=1&navlek_delka=300");
  const dataSirokyStul = odpoved("system=35&navlek=1&navlek_delka=250&sirka=2000&stredni_opora=noha&hloubka=1000");
  const data30 = odpoved("system=30");
  const data35bez = odpoved("system=35");

  for (const [nazev, d] of [["vychozi stul 35 s navlekem 300", data], ["siroky stul 35 (stredni nohy) s navlekem 250, hloubka 1000", dataSirokyStul]]) {
    await test(`${nazev}: navlek a zaslepky jsou pryc, ostatni dily zustaly v poradi`, async () => {
      const nav = d.dily.filter(x => NAV.has(x.part_id)).length;
      assert.ok(nav >= 8, "data nesou navlek a zaslepky: " + nav);
      const s = e.K.shapeFromData(d);
      assert.strictEqual(s.parts.length, d.dily.length - nav);
      assert.ok(!s.parts.some(x => NAV.has(x.part_id)));
      assert.strictEqual(JSON.stringify(s.parts.map(x => x.part_id)), JSON.stringify(d.dily.filter(x => !NAV.has(x.part_id)).map(x => x.part_id)));
      assert.ok(s.name.indexOf("systém 35") > 0 && s.name.indexOf("03") > 0, s.name);
    });
    await test(`${nazev}: indexy lic_peers a attached_to.prof ukazuji na STEJNE dily jako pred odfiltrovanim`, async () => {
      const s = e.K.shapeFromData(d);
      const stare = [];                                   // nove poradi -> puvodni index
      d.dily.forEach((x, i) => { if (!NAV.has(x.part_id)) stare.push(i); });
      let kontrol = 0;
      s.parts.forEach((p, n) => {
        const orig = d.dily[stare[n]];
        const peersOrig = (orig.lic_peers || []).filter(j => !NAV.has(d.dily[j].part_id)).map(j => stare.indexOf(j));
        assert.strictEqual(JSON.stringify(p.lic_peers || []), JSON.stringify(orig.lic_peers ? peersOrig : (p.lic_peers || [])));
        (p.lic_peers || []).forEach(j => { assert.ok(j >= 0 && j < s.parts.length, "index lic_peers v rozsahu"); assert.strictEqual(s.parts[j].part_id, d.dily[stare[j]].part_id); kontrol++; });
        if (orig.attached_to) {
          assert.ok(p.attached_to && p.attached_to.prof >= 0 && p.attached_to.prof < s.parts.length);
          assert.strictEqual(s.parts[p.attached_to.prof].part_id, d.dily[orig.attached_to.prof].part_id);
          assert.strictEqual(p.attached_to.parent_conn, orig.attached_to.parent_conn);
          kontrol++;
        }
      });
      assert.ok(kontrol > 20, "zkontrolovano vazeb: " + kontrol);
    });
    await test(`${nazev}: puvodni data se nemeni`, async () => {
      const kopie = JSON.stringify(d.dily);
      e.K.shapeFromData(d);
      assert.strictEqual(JSON.stringify(d.dily), kopie);
    });
  }
  await test("system 30 a 35 bez navleku: dily beze zmeny (stejne pole, zadna kopie)", async () => {
    assert.strictEqual(e.K.shapeFromData(data30).parts, data30.dily);
    assert.strictEqual(e.K.shapeFromData(data35bez).parts, data35bez.dily);
  });
  await test("souhrn: u navleku poznamka, ze se do Sceny nevklada; jinak beze zmeny", async () => {
    assert.ok(e.K.summaryText(data).indexOf("návlek nohou se do Scény nevkládá") > 0, e.K.summaryText(data));
    assert.ok(e.K.summaryText(data35bez).indexOf("návlek") < 0);
    assert.ok(e.K.summaryText(data).indexOf((data.dily.length - 8) + " dílů") > 0);
  });
  await test("applyToScene: do sceny jde stul BEZ navleku (insertCustomShape dostane jen znamé díly)", async () => {
    const env = makeEnv();
    await env.K.applyToScene(data);
    assert.strictEqual(env.calls.insert.length, 1);
    assert.strictEqual(env.calls.insert[0].n, data.dily.length - 8);
    assert.ok(!env.calls.insert[0].parts.some(x => NAV.has(x.part_id)));
    assert.strictEqual(JSON.stringify(env.calls.insert[0].opts), JSON.stringify({ inPlace: true }));
  });
  console.log(`\n${passed} testů prošlo` + (failed ? `, ${failed} SELHALO` : ""));
})();
