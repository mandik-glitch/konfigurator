// Test "Generatoru stolu" ve scene (webapp/js/scene/stul-konfigurator.js) - bot8, 2026-10-02, prepsano 2026-10-04 na PRIJEMCE konfigurace.
// Panel uz nema vlastni ovladani (Robert 2026-10-03: nic se neduplikuje, jeden modul voleb pro vse) - konfiguraci posila stranka Generator stolu
// (BroadcastChannel "stul-konfigurace" {type:"vloz", query}, nebo /scene.html?stul=<query>); Scena stul vlozi/vymeni.
// Bez prohlizece: soubor se spusti v Node vm proti atrape DOM a atrape sceny (placed, insertCustomShape, ...).
// Odpovedi serveru dela SKUTECNA Python logika (pomocny _odpoved_cli.py = api/stul_konfigurator.py), takze se testuje
// cely retez prijem -> dotaz -> generator -> dily -> vymena ve scene.
//
// Hlida: (1) tvar dotazu, (2) sestaveni panelu (info, otevrit generator, odebrat; zadne volby), (3) vlozeni stolu = jedno volani insertCustomShape inPlace a vlastni dily,
// (4) dalsi konfigurace = vymena JEN vlastnich dilu (cizi obsah sceny zustane), (5) rucni posun stolu prezije vymenu, (6) zmena velikosti pridava dily,
// (7) zastarala odpoved se zahodi, (8) chyba serveru nic nemeni, (9) identita otevrene sestavy a klic F5 se nemeni, priznak undo se vzdy vrati,
// (10) odebrani stolu, (11) prijem BroadcastChannel (+ potvrzeni ack), (12) prijem ?stul= v adrese (pocka na katalog, parametr z adresy pryc, F5 nevlozi znovu).
//
// Spusteni: node scripts/2026-10-02_stul_testy/test_stul_panel.js   (kandidat: STUL_JS=/cesta/stul-konfigurator.js)
const vm = require("vm"), fs = require("fs"), path = require("path"), assert = require("assert"), cp = require("child_process");
const REPO = path.join(__dirname, "..", "..");
const jsFile = process.env.STUL_JS || path.join(REPO, "webapp", "js", "scene", "stul-konfigurator.js");
const src = fs.readFileSync(jsFile, "utf8");
const PY = path.join(REPO, "api", "venv", "bin", "python3");
const CLI = path.join(__dirname, "_odpoved_cli.py");

let passed = 0, failed = 0;
const textOf = el => el.textContent || el.children.map(c => c.textContent).join("\n");
async function test(name, fn) {
  try { await fn(); passed++; console.log("  ok  -", name); }
  catch (e) { failed++; process.exitCode = 1; console.log("FAIL  -", name, "\n       ", e && e.stack ? e.stack.split("\n").slice(0, 3).join("\n        ") : e); }
}

function makeEnv(opts) {
  opts = opts || {};
  const ids = {};
  class El {
    constructor(tag) {
      this.tag = tag; this.children = []; this.attrs = {}; this.handlers = {}; this.textContent = ""; this.value = ""; this.checked = false; this.disabled = false;
      const st = {};
      Object.defineProperty(st, "cssText", { enumerable: false, get() { return ""; }, set(v) { String(v).split(";").forEach(d => { const i = d.indexOf(":"); if (i > 0) st[d.slice(0, i).trim()] = d.slice(i + 1).trim(); }); } });
      this.style = st;
    }
    setAttribute(k, v) { this.attrs[k] = v; if (k === "id") ids[v] = this; if (k === "value") this.value = String(v); }
    appendChild(c) { this.children.push(c); return c; }
    addEventListener(t, f) { (this.handlers[t] = this.handlers[t] || []).push(f); }
    fire(t) { (this.handlers[t] || []).forEach(f => f({ target: this })); }
    get id() { return this.attrs.id; }
  }
  const section = new El("div"); section.setAttribute("id", "stulKonfSection"); ids.stulKonfSection = section;
  const timers = [];
  const calls = { insert: [], removed: [], auto: 0, floating: [], fetch: [], refreshSummary: 0, released: 0, channels: [], posted: [], postedKanal: [], replaced: [] };
  const docHandlers = {}, winHandlers = {};
  const ctx = {
    console, Promise, Math, Number, String, Object, Array, Set, JSON, Error, encodeURIComponent, URL, URLSearchParams, Date,
    BroadcastChannel: opts.noChannel ? undefined : class { constructor(n) { this.name = n; calls.channels.push(this); } postMessage(m) { calls.posted.push(m); calls.postedKanal.push(this.name); } },
    addEventListener: (t, f) => { (winHandlers[t] = winHandlers[t] || []).push(f); },
    location: { search: opts.search || "", href: "http://x/scene.html" + (opts.search || ""), pathname: "/scene.html", hash: "" },
    history: { replaceState(a, b, u) { calls.replaced.push(u); } },
    open() {},
    document: { readyState: "complete", hidden: !!opts.hidden, title: "Scéna", getElementById: id => ids[id] || null, createElement: t => new El(t), createTextNode: t => { const e = new El("#text"); e.textContent = t; return e; },
      addEventListener: (t, f) => { (docHandlers[t] = docHandlers[t] || []).push(f); } },
    setTimeout: (f) => { timers.push(f); return timers.length; }, clearTimeout: () => {},
    localStorage: (() => { const m = { SCENE_KEY: opts.savedKey || null }; return { getItem: k => m[k] == null ? null : m[k], setItem: (k, v) => { m[k] = v; }, removeItem: k => { delete m[k]; }, _m: m }; })(),
    SCENE_LAST_LOADED_KEY: "SCENE_KEY",
    placed: [], scene: { remove: o => calls.removed.push(o) }, CATALOG: opts.catalogEmpty ? [] : [{ id: "Object_7" }],
    katalogPartById(id) { const v = ctx.CATALOG.find(p => p.id === id); return v || ((opts.neznameDily || []).includes(id) ? undefined : { id }); },            // atrapa katalogu: zna vse krome opts.neznameDily (bot10, 2026-10-08)
    currentAssemblyMeta: opts.meta || null, sceneUndoRestoring: false, sceneGeneration: 1,
    selectedMoveEntries: new Set(), axisMoveSelectedEntries: new Set(), jointGroups: [],
    rebuildOccupiedConnectors() {}, refreshEndpointMarkers() {}, refreshDimLabels() {}, refreshMoveSelectionLabel() {}, refreshMoveAxisButtons() {}, syncCatalogSelectionHighlight() {},
    releaseAllJointsFor() { calls.released++; }, releaseBrokenProfileJoints() {},
    initFloatingShapesWindow: o => calls.floating.push(o),
    applyAutoPlacementOffset(startIdx) { calls.auto++; ctx.placed.slice(startIdx).forEach(e => { e.object3d.position.x += 5000; }); },
    bboxOfEntries(entries) {
      const b = { min: { x: Infinity, y: Infinity, z: Infinity }, isEmpty() { return !entries.length; } };
      entries.forEach(e => { b.min.x = Math.min(b.min.x, e.object3d.position.x); b.min.y = Math.min(b.min.y, e.object3d.position.y); b.min.z = Math.min(b.min.z, e.object3d.position.z); });
      return b;
    },
    async insertCustomShape(shape, o) {
      calls.insert.push({ n: shape.parts.length, opts: o, undoFlag: ctx.sceneUndoRestoring });
      if (opts.insertThrows) throw new Error("insert selhal");
      (opts.vlozitJen != null ? shape.parts.slice(0, opts.vlozitJen) : shape.parts).forEach(p => ctx.placed.push({ part: { id: p.part_id }, spec: p,
        object3d: { position: { x: p.position[0], y: p.position[1], z: p.position[2], set(x, y, z) { this.x = x; this.y = y; this.z = z; }, clone() { return Object.assign({}, this); } }, userData: {} } }));
    },
    fetch: async (url) => {
      calls.fetch.push(url);
      if (opts.fetchHook) { const h = await opts.fetchHook(url); if (h) return h; }
      const q = url.split("?")[1] || "";
      const out = cp.execFileSync(PY, [CLI, q], { encoding: "utf8", maxBuffer: 64 * 1024 * 1024 });
      const data = JSON.parse(out);
      const status = data.__status || 200;
      return { ok: status === 200, status, json: async () => data };
    },
  };
  ctx.window = ctx;
  ctx.window.refreshSummary = () => { calls.refreshSummary++; };
  vm.createContext(ctx);
  vm.runInContext(src, ctx, { filename: "stul-konfigurator.js" });
  const settle = async () => { for (let i = 0; i < 12; i++) await new Promise(r => setImmediate(r)); };
  const runTimers = async () => { while (timers.length) { timers.shift()(); await settle(); } };
  const setHidden = h => { ctx.document.hidden = !!h; (docHandlers.visibilitychange || []).forEach(f => f({})); };           // karta Sceny se skryje / ukaze
  return { ctx, ids, calls, settle, runTimers, El, K: ctx.StulKonf, setHidden, docHandlers, winHandlers };
}

const DEF = "sirka=1280&hloubka=800&vyska=840&police=1&kolecka=1&panely=1&led=1&suplik=1&elektrozlab=1&drzak_pet=1&suplik_posun=0";
(async () => {
  console.log("1) panel");
  await test("T1 fetchConfig: GET /api/stul/konfigurace?<query> se stejnou session", async () => {
    const e = makeEnv();
    await e.K.fetchConfig(DEF);
    assert.strictEqual(e.calls.fetch.length, 1);
    assert.strictEqual(e.calls.fetch[0], "/api/stul/konfigurace?" + DEF);
  });
  await test("T2 sestavení panelu: jen informace, 'Otevřít generátor' a 'Odebrat'; žádné volby, žádný dotaz při otevření", async () => {
    const { ids, calls, K } = makeEnv();
    assert.ok(ids.stulKonfOpenBtn && ids.stulKonfRemoveBtn && ids.stulKonfStatus && ids.stulKonfProblems && ids.stulKonfInfo);
    assert.ok(!Object.keys(ids).some(k => /^stulKonf_/.test(k)), "žádné vlastní ovládací prvky: " + Object.keys(ids).filter(k => /^stulKonf_/.test(k)));
    assert.ok(!ids.stulKonfInsertBtn && !ids.stulKonfResetBtn, "žádné tlačítko 'Vložit'/'Výchozí' (vkládá generátor)");
    assert.strictEqual(calls.floating.length, 1);
    assert.strictEqual(calls.floating[0].sectionId, "stulKonfSection");
    assert.strictEqual(calls.fetch.length, 0, "při otevření scény se nic nevolá");
    assert.strictEqual(calls.channels.length, 2, "naslouchá na dvou kanálech: veřejném a soukromém (id této karty Scény)");
    assert.strictEqual(calls.channels[0].name, "stul-konfigurace");
    assert.ok(/^[a-z0-9]{8,}$/.test(K.sceneId), "karta Scény má vlastní id: " + K.sceneId);
    assert.strictEqual(calls.channels[1].name, "stul-konfigurace-" + K.sceneId);
  });

  console.log("2) vložení a výměna ve scéně");
  await test("T3 vloz(): jedno insertCustomShape inPlace, vlastní díly, bez problémů, undo příznak vrácen", async () => {
    const e = makeEnv({ meta: { id: 7 }, savedKey: "{\"id\":7}" });
    assert.strictEqual(await e.K.vloz(DEF), true);
    assert.strictEqual(e.calls.insert.length, 1);
    assert.strictEqual(JSON.stringify(e.calls.insert[0].opts), JSON.stringify({ inPlace: true }));
    const n = e.calls.insert[0].n;
    assert.ok(n >= 50, "díly: " + n);
    assert.strictEqual(e.calls.insert[0].undoFlag, true, "během vložení je sceneUndoRestoring = true");
    assert.strictEqual(e.ctx.sceneUndoRestoring, false, "po vložení false");
    assert.strictEqual(e.ctx.placed.length, n);
    assert.strictEqual(e.K.state.own.length, n);
    assert.strictEqual(e.K.state.query, DEF);
    assert.ok(e.ids.stulKonfProblems.textContent.startsWith("✔"), "bez problémů: " + e.ids.stulKonfProblems.textContent);
    assert.ok(/spojů profilů/.test(e.ids.stulKonfStatus.textContent), e.ids.stulKonfStatus.textContent);
    assert.strictEqual(JSON.stringify(e.ctx.currentAssemblyMeta), JSON.stringify({ id: 7 }), "identita otevřené sestavy se nemění");
    assert.strictEqual(e.ctx.localStorage._m.SCENE_KEY, "{\"id\":7}", "klíč obnovy po F5 se nemění");
  });
  await test("T4 další konfigurace: vymění JEN vlastní díly, cizí obsah zůstane, přibydou střední nohy", async () => {
    const e = makeEnv();
    e.ctx.placed.push({ part: { id: "cizi" }, object3d: { position: { x: 1, y: 2, z: 3 }, userData: {} } });
    await e.K.vloz(DEF);
    const n1 = e.K.state.own.length;
    assert.strictEqual(e.ctx.placed.length, 1 + n1);
    assert.ok(e.calls.auto >= 1, "první vložení vedle cizího obsahu = automatické umístění");
    await e.K.vloz(DEF.replace("sirka=1280", "sirka=2000") + "&stredni_opora=noha");          // stredni NOHY (u 2000 s panelem by `auto` zvolilo vestaveny ram)
    assert.strictEqual(e.ctx.placed[0].part.id, "cizi", "cizí díl zůstal a je první");
    const n2 = e.K.state.own.length;
    assert.ok(n2 > n1, "po rozšíření na 2000 mm přibyly díly (střední nohy místo panelu, který se mezi ně nevejde): " + n1 + " -> " + n2);
    assert.strictEqual(e.ctx.placed.length, 1 + n2);
    assert.strictEqual(e.calls.removed.length, n1, "odebráno právě " + n1 + " vlastních dílů");
    assert.ok(e.ids.stulKonfProblems.textContent.startsWith("✔"), e.ids.stulKonfProblems.textContent);
    await e.K.vloz(DEF);
    assert.strictEqual(e.ctx.placed.length, 1 + n1, "zpět na 1280 mm = původní počet dílů");
  });
  await test("T5 ruční posun stolu přežije výměnu (zachová se poloha)", async () => {
    const e = makeEnv();
    await e.K.vloz(DEF);
    e.ctx.placed.forEach(p => { p.object3d.position.x += 1000; p.object3d.position.z -= 250; });
    await e.K.vloz(DEF.replace("vyska=840", "vyska=900"));
    const leg = e.ctx.placed.find(p => p.part.id === "Object_7" && Math.abs(p.spec.position[0] - (-126.4805)) < 0.01 && Math.abs(p.spec.position[2] - (-407.3711)) < 0.01);
    assert.ok(leg, "noha FL nalezena");
    assert.ok(Math.abs(leg.object3d.position.x - (leg.spec.position[0] + 1000)) < 1e-6, "x posunuto o +1000: " + leg.object3d.position.x);
    assert.ok(Math.abs(leg.object3d.position.z - (leg.spec.position[2] - 250)) < 1e-6, "z posunuto o -250");
  });
  await test("T6 příznak undo se vrátí i když vložení selže", async () => {
    const e = makeEnv({ insertThrows: true });
    assert.strictEqual(await e.K.vloz(DEF), false);
    assert.strictEqual(e.ctx.sceneUndoRestoring, false);
    assert.ok(e.ids.stulKonfStatus.textContent.includes("Vložení do scény selhalo"), e.ids.stulKonfStatus.textContent);
  });
  await test("T6b katalog dílů se ještě nenačetl: nic se nevloží a ukáže se hláška", async () => {
    const e = makeEnv({ catalogEmpty: true });
    assert.strictEqual(await e.K.vloz(DEF), false);
    assert.strictEqual(e.calls.insert.length, 0);
    assert.ok(e.ids.stulKonfStatus.textContent.includes("Katalog dílů se ještě načítá"), e.ids.stulKonfStatus.textContent);
  });

  await test("T6c díl stolu, který katalog Scény nezná (patka M8 3251 má visible_in_scene=0): doplní se z karty produktu a stůl se vloží CELÝ", async () => {
    const karta = { product: { id: 3251, name: "Vyrovnávací šroubovací patka M8", sku: "2.3.002.0845", glb_file: "product_3251.glb", color_hex: null, unit: "ks", weight_g: 44, price_czk_placeholder: "34.00", category_id: 202, stock_qty: 0 } };
    const e = makeEnv({ neznameDily: ["product_3251"], fetchHook: async (url) => url === "/api/shop/products/3251" ? { ok: true, status: 200, json: async () => karta } : null });
    const q = DEF.replace("kolecka=1", "kolecka=0") + "&patky=1";
    assert.strictEqual(await e.K.vloz(q), true, e.ids.stulKonfStatus.textContent);
    const radky = e.ctx.CATALOG.filter(p => p.id === "product_3251");
    assert.strictEqual(radky.length, 1, "díl doplněn do CATALOG právě jednou");
    const r = radky[0];
    assert.ok(/^katalog\/product_3251\.glb\?v=/.test(r.file) && r.visible_in_scene === false && r.source === "product" && r.layer === "produkt" && r.shop_product_id === 3251 && r.sku === "2.3.002.0845" && r.price_czk === 34 && r.weight_kg === 0.044, JSON.stringify(r));
    assert.strictEqual(e.calls.insert.length, 1);
    assert.strictEqual(e.calls.insert[0].n, e.ctx.placed.length, "vloženy všechny díly");
    assert.ok(e.ctx.placed.some(p => p.part.id === "product_3251"), "patky jsou ve scéně");
    assert.strictEqual(e.calls.fetch.filter(u => u.startsWith("/api/shop/products/")).length, 1, "karta jen jednou");
    assert.strictEqual(await e.K.vloz(q), true);                                                         // druhé vložení: díl už v katalogu je, karta se znovu nečte
    assert.strictEqual(e.calls.fetch.filter(u => u.startsWith("/api/shop/products/")).length, 1, "karta se znovu nečte");
  });
  await test("T6d díl, který katalog nezná a karta ho nemá (404): stůl se NEVLOŽÍ napůl, hláška jmenuje díl", async () => {
    const e = makeEnv({ neznameDily: ["product_3251"], fetchHook: async (url) => url.startsWith("/api/shop/products/") ? { ok: false, status: 404, json: async () => ({ error: "Produkt neexistuje." }) } : null });
    assert.strictEqual(await e.K.vloz(DEF.replace("kolecka=1", "kolecka=0") + "&patky=1"), false);
    assert.strictEqual(e.calls.insert.length, 0, "nic se nevkládalo");
    assert.strictEqual(e.ctx.placed.length, 0);
    assert.ok(/product_3251/.test(e.ids.stulKonfStatus.textContent) && /nevkládá/.test(e.ids.stulKonfStatus.textContent), e.ids.stulKonfStatus.textContent);
    assert.strictEqual(e.K.state.inserted, false);
  });
  await test("T6e vložilo se méně dílů, než stůl má (insertCustomShape se zastavil): vlastní díly se odeberou, stůl není napůl, undo příznak vrácen", async () => {
    const e = makeEnv({ vlozitJen: 5 });
    assert.strictEqual(await e.K.vloz(DEF), false);
    assert.strictEqual(e.ctx.placed.length, 0, "napůl vložené díly ze scény pryč");
    assert.strictEqual(e.K.state.inserted, false);
    assert.strictEqual(e.ctx.sceneUndoRestoring, false);
    assert.ok(/vložilo se jen 5 z \d+ dílů/.test(e.ids.stulKonfStatus.textContent), e.ids.stulKonfStatus.textContent);
  });

  console.log("3) problémy, chyby, zastaralé odpovědi");
  await test("T7 kolize po POSUNU šuplíků se ukáže jako problém (stůl se vloží kvůli diagnostice)", async () => {
    const e = makeEnv();
    await e.K.vloz(DEF.replace("suplik_posun=0", "suplik_posun=70"));       // šuplíky posunuté do pravé nohy
    assert.ok(textOf(e.ids.stulKonfProblems).startsWith("⚠"), textOf(e.ids.stulKonfProblems));
    assert.strictEqual(e.calls.insert.length, 1, "vloženo i s problémem");
  });
  await test("T8 zastaralá odpověď se zahodí (rychlé po sobě jdoucí konfigurace)", async () => {
    let release = null;
    const e = makeEnv({ fetchHook: (url) => url.includes("sirka=1500&") ? new Promise(res => { release = () => res(null); }) : null });
    const p1 = e.K.vloz(DEF.replace("sirka=1280", "sirka=1500"));                 // čeká na odpověď
    await e.settle();
    await e.K.vloz(DEF.replace("sirka=1280", "sirka=1300"));                      // novější, dokončí se hned
    assert.strictEqual(e.K.state.data.parametry.sirka, 1300);
    release(); assert.strictEqual(await p1, false, "opožděná odpověď nic nevrací");
    assert.strictEqual(e.K.state.data.parametry.sirka, 1300, "opožděná odpověď 1500 se nezobrazila");
    assert.strictEqual(e.K.state.query, DEF.replace("sirka=1280", "sirka=1300"));
  });
  await test("T9 chyba serveru (400) nic nemění a ukáže se červeně", async () => {
    const e = makeEnv();
    await e.K.vloz(DEF);
    const n = e.ctx.placed.length;
    assert.strictEqual(await e.K.vloz(DEF.replace("sirka=1280", "sirka=100")), false);        // mimo rozsah -> server 400
    assert.ok(e.ids.stulKonfStatus.textContent.startsWith("Chyba:"), e.ids.stulKonfStatus.textContent);
    assert.strictEqual(e.ids.stulKonfStatus.style.color, "#e08080");
    assert.strictEqual(e.ctx.placed.length, n, "scéna beze změny");
  });

  console.log("4) odebrání");
  await test("T10 'Odebrat stůl' smaže jen vlastní díly", async () => {
    const e = makeEnv();
    e.ctx.placed.push({ part: { id: "cizi" }, object3d: { position: { x: 0, y: 0, z: 0 }, userData: {} } });
    await e.K.vloz(DEF);
    assert.ok(e.ctx.placed.length > 1);
    e.ids.stulKonfRemoveBtn.fire("click"); await e.settle();
    assert.strictEqual(e.ctx.placed.length, 1);
    assert.strictEqual(e.ctx.placed[0].part.id, "cizi");
    assert.strictEqual(e.K.state.inserted, false);
  });

  console.log("5) příjem z generátoru");
  await test("T11 zpráva z BroadcastChannel vloží stůl a odpoví ack; cizí/neúplné zprávy ignoruje", async () => {
    const e = makeEnv();
    const bc = e.calls.channels[0];
    bc.onmessage({ data: { type: "ack", ok: true } });                           // vlastní odpověď jiné Scény - ignorovat
    bc.onmessage({ data: { type: "vloz" } });                                    // bez dotazu
    bc.onmessage({ data: null });
    await e.settle();
    assert.strictEqual(e.calls.insert.length, 0);
    assert.strictEqual(e.calls.posted.length, 0);
    bc.onmessage({ data: { type: "vloz", query: DEF } }); await e.settle();
    assert.strictEqual(e.calls.insert.length, 1);
    assert.strictEqual(JSON.stringify(e.calls.posted), JSON.stringify([{ type: "ack", ok: true }]));
    bc.onmessage({ data: { type: "vloz", query: DEF.replace("sirka=1280", "sirka=100") } }); await e.settle();
    assert.strictEqual(JSON.stringify(e.calls.posted[1]), JSON.stringify({ type: "ack", ok: false }), "chyba = ack ok:false");
  });
  await test("T11b ping generátoru: Scéna se ohlásí pongem (id, viditelnost, poslední použití) a nic nevkládá; ping bez req se ignoruje", async () => {
    const e = makeEnv();
    const bc = e.calls.channels[0];
    bc.onmessage({ data: { type: "ping" } });
    bc.onmessage({ data: { type: "ping", req: 5 } });
    await e.settle();
    assert.strictEqual(e.calls.posted.length, 0);
    bc.onmessage({ data: { type: "ping", req: "r1" } });
    await e.settle();
    assert.strictEqual(e.calls.posted.length, 1);
    const m = e.calls.posted[0];
    assert.strictEqual(JSON.stringify(Object.keys(m).sort()), JSON.stringify(["aktivni", "id", "req", "type", "viditelna"]));
    assert.strictEqual(m.type, "pong"); assert.strictEqual(m.req, "r1"); assert.strictEqual(m.id, e.K.sceneId); assert.strictEqual(m.viditelna, true);
    assert.ok(typeof m.aktivni === "number" && Math.abs(Date.now() - m.aktivni) < 60000);
    assert.strictEqual(e.calls.postedKanal[0], "stul-konfigurace", "pong jde na veřejný kanál");
    assert.strictEqual(e.calls.insert.length, 0, "ping nic nevkládá");
    e.winHandlers.pointerdown[0]({});                                           // uživatel klikl do Scény: čas posledního použití se obnoví
    bc.onmessage({ data: { type: "ping", req: "r2" } }); await e.settle();
    assert.ok(e.calls.posted[1].aktivni >= m.aktivni);
  });
  await test("T11c soukromý kanál: vloz s req vloží stůl a odpoví ackem {req, ok, viditelna, vymena, zprava}; bez req / dotazu ignoruje; druhé vložení = výměna", async () => {
    const e = makeEnv();
    const pc = e.calls.channels[1];
    pc.onmessage({ data: { type: "vloz", query: DEF } });                          // bez req
    pc.onmessage({ data: { type: "vloz", req: "a" } });                            // bez dotazu
    pc.onmessage({ data: { type: "ack", req: "a", ok: true } });
    pc.onmessage({ data: null });
    await e.settle();
    assert.strictEqual(e.calls.insert.length, 0);
    assert.strictEqual(e.calls.posted.length, 0);
    pc.onmessage({ data: { type: "vloz", query: DEF, req: "a" } }); await e.settle();
    assert.strictEqual(e.calls.insert.length, 1);
    assert.strictEqual(JSON.stringify(e.calls.posted), JSON.stringify([{ type: "ack", req: "a", ok: true, viditelna: true, vymena: false, zprava: "" }]));
    assert.strictEqual(e.calls.postedKanal[0], "stul-konfigurace-" + e.K.sceneId, "ack jde na soukromý kanál");
    pc.onmessage({ data: { type: "vloz", query: DEF, req: "b" } }); await e.settle();
    assert.strictEqual(JSON.stringify(e.calls.posted[1]), JSON.stringify({ type: "ack", req: "b", ok: true, viditelna: true, vymena: true, zprava: "" }), "druhé vložení je výměna");
  });
  await test("T11d vložení selže: ack nese ok:false a TEXT hlášení Scény (panel Generátor stolu bývá zavřený); starý protokol dál jen {ok:false}", async () => {
    const e = makeEnv();
    const pc = e.calls.channels[1];
    pc.onmessage({ data: { type: "vloz", query: DEF.replace("sirka=1280", "sirka=100"), req: "x" } }); await e.settle();
    const m = e.calls.posted[0];
    assert.strictEqual(m.ok, false); assert.strictEqual(m.req, "x"); assert.strictEqual(m.vymena, false);
    assert.ok(/^Chyba: /.test(m.zprava) && m.zprava.length <= 240, "text chyby: " + m.zprava);
    assert.strictEqual(e.K.state.inserted, false);
  });
  await test("T11e záložní cesta generátoru v2 (veřejný kanál, vloz s req): odpověď s req na VEŘEJNÉM kanálu; bez req = starý protokol {type:'ack', ok}", async () => {
    const e = makeEnv();
    const bc = e.calls.channels[0];
    bc.onmessage({ data: { type: "vloz", query: DEF, req: "z", v: 2 } }); await e.settle();
    assert.strictEqual(JSON.stringify(e.calls.posted[0]), JSON.stringify({ type: "ack", req: "z", ok: true, viditelna: true, vymena: false, zprava: "" }));
    assert.strictEqual(e.calls.postedKanal[0], "stul-konfigurace");
    bc.onmessage({ data: { type: "vloz", query: DEF } }); await e.settle();
    assert.strictEqual(JSON.stringify(e.calls.posted[1]), JSON.stringify({ type: "ack", ok: true }), "starý protokol beze změny");
  });
  await test("T11f dva požadavky těsně po sobě: první přebije druhý – první ack ok:false s důvodem, druhý ok:true", async () => {
    const e = makeEnv();
    const pc = e.calls.channels[1];
    pc.onmessage({ data: { type: "vloz", query: DEF, req: "p1" } });
    pc.onmessage({ data: { type: "vloz", query: DEF.replace("sirka=1280", "sirka=1500"), req: "p2" } });
    await e.settle();
    const a1 = e.calls.posted.find(m => m.req === "p1"), a2 = e.calls.posted.find(m => m.req === "p2");
    assert.ok(a1 && a1.ok === false && a1.zprava === "vložení přebil novější požadavek z generátoru", JSON.stringify(a1));
    assert.ok(a2 && a2.ok === true, JSON.stringify(a2));
    assert.strictEqual(e.calls.insert.length, 1, "vložil se jen novější");
  });
  await test("T11g skrytá karta Scény: pong viditelna:false; po vložení má titul „● “ a ack viditelna:false; po zobrazení značka zmizí", async () => {
    const e = makeEnv({ hidden: true });
    e.calls.channels[0].onmessage({ data: { type: "ping", req: "h" } }); await e.settle();
    assert.strictEqual(e.calls.posted[0].viditelna, false);
    e.calls.channels[1].onmessage({ data: { type: "vloz", query: DEF, req: "h" } }); await e.settle();
    assert.strictEqual(e.calls.posted[1].viditelna, false);
    assert.strictEqual(e.ctx.document.title, "● Scéna");
    e.calls.channels[1].onmessage({ data: { type: "vloz", query: DEF, req: "h2" } }); await e.settle();
    assert.strictEqual(e.ctx.document.title, "● Scéna", "značka se nenásobí");
    e.setHidden(false);
    assert.strictEqual(e.ctx.document.title, "Scéna", "po zobrazení karty značka zmizí");
    e.setHidden(true);
    assert.strictEqual(e.ctx.document.title, "Scéna", "samotné skrytí titul nemění");
    e.winHandlers.focus[0]({});
    assert.strictEqual(e.ctx.document.title, "Scéna");
  });
  await test("T12 bez BroadcastChannel (starý prohlížeč) se Scéna načte bez chyby", async () => {
    const e = makeEnv({ noChannel: true });
    assert.ok(e.ids.stulKonfOpenBtn, "panel stojí");
  });
  await test("T13 ?stul=<query> v adrese: počká na katalog, vloží stůl, parametr z adresy odstraní (F5 nevloží znovu)", async () => {
    const e = makeEnv({ search: "?stul=" + encodeURIComponent(DEF) + "&x=1", catalogEmpty: true });
    assert.strictEqual(e.calls.replaced.length, 1, "adresa upravena hned");
    assert.ok(!e.calls.replaced[0].includes("stul="), e.calls.replaced[0]);
    assert.ok(e.calls.replaced[0].includes("x=1"), "ostatní parametry zůstanou: " + e.calls.replaced[0]);
    await e.settle();
    assert.strictEqual(e.calls.insert.length, 0, "katalog ještě není");
    assert.strictEqual(e.calls.fetch.length, 0);
    e.ctx.CATALOG.push({ id: "Object_7" });
    await e.runTimers();
    assert.strictEqual(e.calls.insert.length, 1, "po načtení katalogu se stůl vloží");
    assert.strictEqual(e.K.state.query, DEF);
  });
  await test("T14 bez ?stul= se při otevření scény nic nevkládá", async () => {
    const e = makeEnv({ search: "?x=1" });
    await e.settle();
    assert.strictEqual(e.calls.insert.length, 0);
    assert.strictEqual(e.calls.replaced.length, 0);
  });

  console.log("\n" + passed + " testů prošlo" + (failed ? ", " + failed + " SELHALO" : ""));
})();
