// Modul voleb (product-configurator.js) bez stranky mini-shopu - hooky pro dalsi stranky (stranka zamestnancu): onResolved, onSelection, initialSelection,
// radek povoleneho rozsahu pod posuvnikem. Nad SKUTECNYM verejnym API (bridge.py).
const { chromium } = require("/opt/konfigurator/node_modules/playwright");
const BASE = process.env.BASE, PID = process.env.PID || "9001";
let bad = 0, total = 0; const ok = (c, t) => { total++; if (!c) bad++; console.log(`[${c ? "OK   " : "CHYBA"}] ${t}`); };
(async () => {
  const browser = await chromium.launch({ args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
  const page = await (await browser.newContext({ viewport: { width: 1300, height: 900 } })).newPage(); const errs = [];
  page.on("pageerror", e => errs.push(e.message));
  const bodies = []; page.on("request", r => { if (r.method() === "POST" && /configurator\/resolve/.test(r.url())) { try { bodies.push(JSON.parse(r.postData())); } catch (e) { /* nic */ } } });
  await page.addInitScript(() => {                                     // zachytit volby V3D.mount (envConfig ze schematu)
    let _v; Object.defineProperty(window, "V3D", { configurable: true, set(v) { _v = v; }, get() {            // mount se pridava az po prirazeni V3D: obalit pri prvnim cteni, az kdy existuje
      if (_v && _v.mount && !_v.__w) { const m = _v.mount; _v.mount = function (el, o) { window.__mountOpts = o; return m.apply(this, arguments); }; _v.__w = 1; }
      return _v; } });
  });
  await page.route("**/api/shop/products/*/configurator*", async (route) => { const r = await route.fetch(); const j = await r.json(); j.env = { hdri: "testovaci_hdri", strength: 1.25, rot_deg: 30, hemi: 0.4 }; await route.fulfill({ response: r, json: j }); });
  await page.goto(`${BASE}/miniweb/legal.html?shop=packstations&lang=cs&demo=1`); await page.waitForTimeout(800);
  const res = await page.evaluate(async (pid) => {
    const load = src => new Promise(ok => { const s = document.createElement("script"); s.src = src; s.onload = ok; document.head.appendChild(s); });
    await load("/js/product-configurator.js");
    const stage = document.createElement("div"), panelHost = document.createElement("div"); document.body.appendChild(stage); document.body.appendChild(panelHost);
    window.__log = { resolved: 0, sel: [], hash: null, hasStaffKey: null, price: null };
    const ctl = await PdConfigurator.init({
      product: { id: Number(pid), configurator: { available: true, default_view: "configurator" } }, noTurntable: true, lang: "cs",
      initialSelection: { w: 1500, cut1: true, nonexistent_slot: 5 }, resolveExtra: { staff: true, product_id: 1, vlastni_priznak: "x" },
      dom: { tabsBefore: null, visual: [], stageHost: stage, panelHost: panelHost },
      page: { setPrice: p => { window.__log.price = p; }, setBuyState: () => {}, toast: () => {}, onActivate: () => {}, track: () => {},
              onResolved: r => { window.__log.resolved++; window.__log.hash = r.hash; }, onSelection: s => { window.__log.sel.push(s); }, onViewer: v => { window.__log.viewer = !!v; window.__log.viewerRef = v; } },
      assets: { cssNow: ["/css/product-configurator.css"], css: ["/css/v3d.css"], viewer: "/js/v3d/viewer3d.js" }
    });
    window.__ctl = ctl;
    return !!ctl;
  }, PID);
  await page.waitForSelector(".pdc-slot[data-slot=w] .pdc-num", { timeout: 30000 });
  await page.waitForTimeout(1500);
  const st = await page.evaluate(() => ({ w: document.querySelector(".pdc-slot[data-slot=w] .pdc-num").value, cut1: document.querySelector(".pdc-slot[data-slot=cut1] input[type=checkbox]").checked, log: window.__log,
    notes: [...document.querySelectorAll(".pdc-range-note")].map(n => n.textContent).filter(Boolean) }));
  ok(res === true, "H0 modul se inicializuje v bezokenním režimu (stageHost + panelHost) na vlastní stránce");
  ok(st.w === "1500" && st.cut1 === true, "H1 initialSelection se použije (šířka 1500, výřez 1 zapnutý; neznámý slot se ignoruje): w=" + st.w + ", cut1=" + st.cut1);
  ok(st.log.resolved >= 1 && /^[0-9a-f]{6,}$/.test(String(st.log.hash || "")), "H2 page.onResolved dostane celou odpověď (hash " + st.log.hash + ", volání " + st.log.resolved + ")");
  ok(st.log.sel.length >= 1 && st.log.sel[st.log.sel.length - 1].w === 1500, "H3 page.onSelection dostane potvrzený výběr po resolve");
  ok(st.notes.length >= 1 && /\d/.test(st.notes[0]), "H4 pod posuvníkem je řádek povoleného rozsahu, kde je užší než ve schématu: " + st.notes.slice(0, 2).join(" | "));
  ok(bodies.length >= 1 && bodies.every(b => b.staff === true && b.vlastni_priznak === "x" && String(b.product_id) === String(PID)), "H6 ctx.resolveExtra se přidá do těla resolve, product_id přepsat nejde: " + JSON.stringify(bodies[0] || {}).slice(0, 120));
  await page.waitForFunction(() => window.__log.viewer === true, null, { timeout: 60000 }).catch(() => {});
  const ev = await page.evaluate(() => ({ viewerHook: window.__log.viewer, same: window.__ctl.viewer() === window.__log.viewerRef && !!window.__ctl.viewer(), env: window.__mountOpts && window.__mountOpts.envConfig, envCtl: window.__ctl.envConfig && window.__ctl.envConfig() }));
  ok(ev.viewerHook === true && ev.same, "H7 page.onViewer dostane prohlížeč a ctl.viewer() vrací týž");
  ok(ev.env && ev.env.hdri === "testovaci_hdri" && ev.env.strength === 1.25, "H8 schema.env se předá do V3D.mount jako envConfig: " + JSON.stringify(ev.env));
  ok(ev.envCtl && ev.envCtl.hdri === "testovaci_hdri" && ev.envCtl.strength === 1.25, "H9 ctl.envConfig() vrací uložené prostředí hlavního prohlížeče (hostitel ho může dát dalšímu 3D prvku, HDR se nestahuje podruhé): " + JSON.stringify(ev.envCtl));
  ok(!errs.length, "H5 bez JS chyb" + (errs[0] ? " | " + errs[0] : ""));
  await browser.close(); console.log(`\n==> ${total - bad}/${total} kontrol OK`); process.exit(bad ? 1 : 0);
})();
