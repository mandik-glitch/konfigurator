// Mereni nacitani 3D modelu stolu (bot16 2026-10-04, nalez bot8: "model na baliace-stoly.top se nacita dlouho"): casova osa pozadavku a okamzik, kdy je model v prohlizeci.
// Neni to test (nic nehlida), jen mereni pro srovnani PRED/PO upravach: node pres bridge.py, vypise tabulku (ms od zahajeni navigace). Cisla jsou z headless SwiftShaderu (bez GPU),
// takze absolutne nadsazena; pozor na poradi a mezery mezi pozadavky.
const { chromium } = require("/opt/konfigurator/node_modules/playwright");
const BASE = process.env.BASE, PID = process.env.PID || "9001";
(async () => {
  const runs = [];
  for (let i = 0; i < (Number(process.env.RUNS) || 3); i++) {
    const browser = await chromium.launch({ args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
    const ctx = await browser.newContext({ viewport: { width: 1300, height: Number(process.env.VYSKA) || 900 }, bypassCSP: true }); const pg = await ctx.newPage();
    await pg.addInitScript(() => { window.__pdcDebug = true; });
    if (process.env.THROTTLE) {                                           // THROTTLE=1: mobilni sit (RTT 100 ms, 5 Mb/s dolu) - na VPS je sit prakticky okamzita a rozdily se ztraceji
      const cdp = await ctx.newCDPSession(pg); await cdp.send("Network.enable");
      await cdp.send("Network.emulateNetworkConditions", { offline: false, latency: 100, downloadThroughput: 5 * 1024 * 1024 / 8, uploadThroughput: 2 * 1024 * 1024 / 8 });
    }
    const ev = []; let t0 = 0;
    pg.on("request", r => { const u = r.url(); if (/three\.min|OrbitControls|GLTFLoader|RoomEnvironment|CSS2DRenderer|BlurShader|RGBELoader|viewer3d|v3d-ovladani|\/configurator(\?|$)|configurator\/resolve|configurator\/glb|\.hdr|pripni|stavebnice|tile\.js/.test(u)) ev.push({ t: Date.now(), k: "start", u }); });
    pg.on("requestfinished", r => { const u = r.url(); if (/three\.min|OrbitControls|GLTFLoader|RoomEnvironment|CSS2DRenderer|BlurShader|RGBELoader|viewer3d|v3d-ovladani|\/configurator(\?|$)|configurator\/resolve|configurator\/glb|\.hdr|pripni|stavebnice|tile\.js/.test(u)) ev.push({ t: Date.now(), k: "end", u }); });
    t0 = Date.now();
    const url = process.env.PAGE === "product" ? `${BASE}/miniweb/product.html?shop=packstations&lang=cs&demo=1&id=${PID}` : `${BASE}/embed/stul.html?p=${PID}`;     // PAGE=product: karta produktu v mini-shopu (s dlazdici Pripni cokoli)
    await pg.goto(url, { waitUntil: "domcontentloaded" });
    await pg.waitForFunction(() => window.__pdcState && window.__pdcState.modelHash, null, { timeout: 120000 }); const tModel = Date.now() - t0;
    if (process.env.PAGE === "product") await pg.waitForTimeout(Number(process.env.PO_MODELU_MS) || 4000);
    const short = u => u.replace(/^https?:\/\/[^/]+/, "").replace(/\?.*$/, "").split("/").slice(-2).join("/").slice(0, 38);
    const rows = ev.map(e => ({ ms: e.t - t0, k: e.k, u: short(e.u) })).sort((a, b) => a.ms - b.ms);
    runs.push({ tModel, rows }); await Promise.race([browser.close(), new Promise(r => setTimeout(r, 15000))]);
  }
  const best = runs.reduce((a, b) => (a.tModel <= b.tModel ? a : b));
  console.log("Casy do zobrazeni modelu (ms):", runs.map(r => r.tModel).join(", "), "| nejlepsi beh – casova osa:");
  const ends = {}; best.rows.forEach(r => { if (r.k === "end") ends[r.u] = r.ms; });
  best.rows.filter(r => r.k === "start").forEach(r => console.log(String(r.ms).padStart(6) + " ms  start " + r.u.padEnd(40) + (ends[r.u] != null ? " konec " + ends[r.u] + " ms" : "")));
})();
