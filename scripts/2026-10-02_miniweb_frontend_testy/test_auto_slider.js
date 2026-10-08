// Slidery s automatickou hodnotou (bot8: police sh1..sh10): selection[slot] == null -> ukaze options.value + "automaticky", nic se neposila, dokud zakaznik nepohne;
// options.<slot>.hidden === true -> slot se nevykresli ani nejde do shrnuti. Schema i odpoved resolve se nad skutecnym API doplni (server pole nasadi bot8 pozdeji).
const { chromium } = require("/opt/konfigurator/node_modules/playwright");
const BASE = process.env.BASE, PID = process.env.PID || "9001";
let bad = 0, total = 0; const ok = (c, t) => { total++; if (!c) bad++; console.log(`[${c ? "OK   " : "CHYBA"}] ${t}`); };
(async () => {
  const browser = await chromium.launch({ args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
  const page = await (await browser.newContext({ viewport: { width: 1300, height: 900 } })).newPage(); const errs = [], bodies = [];
  page.on("pageerror", e => errs.push(e.message));
  let realServer = false;                                              // server (pracovni strom) uz police sh1..sh10 zna: nic se nedoplnuje, kontroluje se skutecna odpoved
  await page.route("**/api/shop/products/*/configurator*", async (route) => {
    const r = await route.fetch(); const j = await r.json();
    if (j.slots.some(x => x.id === "sh1")) { realServer = true; return route.fulfill({ response: r, json: j }); }
    j.slots.push({ id: "sh1", type: "slider", group: "g_frame", label: "Výška police 1", slider: { min: 100, max: 1200, step: 0.1, unit: "mm" } },
                 { id: "sh2", type: "slider", group: "g_frame", label: "Výška police 2", slider: { min: 100, max: 1200, step: 0.1, unit: "mm" } });
    j.default_selection.sh1 = null; j.default_selection.sh2 = null;
    await route.fulfill({ response: r, json: j });
  });
  await page.route("**/api/shop/configurator/resolve", async (route) => {
    let b = {}; try { b = JSON.parse(route.request().postData() || "{}"); } catch (e) { /* nic */ }
    bodies.push(b);
    if (realServer) return route.fulfill({ response: await route.fetch() });
    const sel = Object.assign({}, b.selection); const sh1 = sel.sh1; delete sel.sh1; delete sel.sh2;                 // skutecny server pole zatim nezna
    const r = await route.fetch({ postData: JSON.stringify(Object.assign({}, b, { selection: sel })) }); const j = await r.json();
    j.selection = Object.assign({}, j.selection, { sh1: sh1 == null ? null : sh1, sh2: null });
    j.options = Object.assign({}, j.options, { sh1: { min: 100, max: 900.5, value: sh1 == null ? 215.5 : sh1, auto: sh1 == null, fits: true }, sh2: { min: 0, max: 0, hidden: true } });
    await route.fulfill({ response: r, json: j });
  });
  await page.goto(`${BASE}/miniweb/legal.html?shop=packstations&lang=cs&demo=1`); await page.waitForTimeout(800);
  await page.evaluate(async (pid) => {
    const load = src => new Promise(ok => { const s = document.createElement("script"); s.src = src; s.onload = ok; document.head.appendChild(s); });
    await load("/js/product-configurator.js"); window.__pdcDebug = true;
    const stage = document.createElement("div"), panelHost = document.createElement("div"); document.body.appendChild(stage); document.body.appendChild(panelHost);
    window.__ctl = await PdConfigurator.init({ product: { id: Number(pid), configurator: { available: true, default_view: "configurator" } }, noTurntable: true, lang: "cs",
      dom: { tabsBefore: null, visual: [], stageHost: stage, panelHost: panelHost }, page: { setPrice() {}, setBuyState() {}, toast() {}, onActivate() {}, track() {} },
      assets: { cssNow: ["/css/product-configurator.css"], css: ["/css/v3d.css"], viewer: "/js/v3d/viewer3d.js" } });
  }, PID);
  await page.waitForSelector(".pdc-slot[data-slot=sh1] .pdc-num", { timeout: 30000 }); await page.waitForTimeout(2500);
  const st = () => page.evaluate(() => ({ v: document.querySelector(".pdc-slot[data-slot=sh1] .pdc-num").value, sh1vis: !document.querySelector(".pdc-slot[data-slot=sh1]").hidden, sh2hid: document.querySelector(".pdc-slot[data-slot=sh2]").hidden,
    auto: (document.querySelector(".pdc-slot[data-slot=sh1] .pdc-auto-note") || {}).textContent, sum: [...document.querySelectorAll(".pdc-summary dt")].map(e => e.textContent + "=" + e.nextSibling.textContent).filter(x => /police/i.test(x)), sel: window.__pdcState.sel.sh1 }));
  let a = await st();
  const optV = await page.evaluate(() => { const o = (window.__pdcState.last.options || {}).sh1; return o ? o.value : null; });
  ok(a.sh1vis && optV != null && Math.abs(Number(a.v) - optV) < 0.06 && /automat/i.test(a.auto || ""), "S1 posuvník police 1 ukáže hodnotu ze serveru (" + optV + ") a poznámku „automaticky“: " + a.v + " | " + a.auto + (realServer ? " [skutečný server]" : " [doplněno testem]"));
  ok(a.sh2hid === true, "S2 neexistující police 2 (options.hidden) se nevykreslí");
  ok(a.sum.length >= 1 && /\(.*automat/i.test(a.sum[0]) && !a.sum.some(x => /police 2/i.test(x)), "S3 shrnutí: police 1 s „automaticky“, police 2 ve shrnutí není: " + a.sum.join(" ; "));
  ok(bodies.length >= 1 && bodies.every(b => b.selection.sh1 == null), "S4 dokud zákazník nepohne, neposílá se číslo (sh1 null/chybí)");
  const lim = await page.evaluate(() => (window.__pdcState.last.options || {}).sh1), want = Math.round((lim.min + 60) * 10) / 10;       // v mezich z options (0,1 mm, bez mrizky 10 mm)
  await page.locator(".pdc-slot[data-slot=sh1] .pdc-num").fill(String(want)); await page.locator(".pdc-slot[data-slot=sh1] .pdc-num").dispatchEvent("change"); await page.waitForTimeout(3000);
  a = await st();
  ok(bodies[bodies.length - 1].selection.sh1 === want && a.sel === want && !a.auto, "S5 po posunutí se pošle zadané číslo " + want + " (bez zaokrouhlení na 10 mm) a poznámka „automaticky“ zmizí: sel=" + a.sel + " auto='" + a.auto + "'");
  await page.locator(".pdc-head .pdc-link").click(); await page.waitForTimeout(3000);
  a = await st();
  ok(a.sel == null && Math.abs(Number(a.v) - optV) < 0.06 && /automat/i.test(a.auto || ""), "S6 Zpět na výchozí vrací automatiku (null): sel=" + a.sel + ", hodnota " + a.v);
  ok(!errs.length, "S7 bez JS chyb" + (errs[0] ? " | " + errs[0] : ""));
  await browser.close(); console.log(`\n==> ${total - bad}/${total} kontrol OK`); process.exit(bad ? 1 : 0);
})();
