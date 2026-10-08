// Poradi nacitani na karte produktu mini-shopu (bot16 2026-10-04, nalez bot8: "model na baliace-stoly.top se nacita dlouho"): nad SKUTECNYM verejnym API (bridge.py).
// Hlida: (N1) dlazdice Pripni cokoli (druhy 3D prohlizec) se spusti AZ po prvnim zobrazeni modelu stolu; (N2) skripty 3D prohlizece (viewer + three z CDN) se stahuji PARALELNE,
// ne jeden po druhem; (N3) hotovy model stolu se z site stahne JEDNOU (predstazeni po resolve + GLTFLoader z mezipameti); (N4) preload v hlavicce stranky souhlasi s tim, co stranka
// opravdu nacita (zadny skript se nestahuje dvakrat, zadny preload nepropadne); (N5) kdyz se volby nenactou, dlazdice se presto nacte (brana se nezasekne).
const { chromium } = require("/opt/konfigurator/node_modules/playwright");
const BASE = process.env.BASE, PID = process.env.PID || "9001";
let bad = 0, total = 0; const ok = (c, t) => { total++; if (!c) bad++; console.log(`[${c ? "OK   " : "CHYBA"}] ${t}`); };
const DEP = /three\.min\.js|OrbitControls\.js|GLTFLoader\.js|RoomEnvironment\.js|CSS2DRenderer\.js|HorizontalBlurShader\.js|VerticalBlurShader\.js|RGBELoader\.js|\/v3d\/viewer3d\.js|v3d-ovladani\.js/;
const URL_PRODUKT = `${BASE}/miniweb/product.html?shop=packstations&lang=cs&demo=1&id=${PID}`;
const ARGS = ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"];

// otevre stranku a zaznamena casovou osu pozadavku (Playwright) + stazeni ze site (CDP: mezipamet se nepocita)
async function otevri(browser, opts) {
  const ctx = await browser.newContext({ viewport: { width: 1300, height: 2600 } });     // vysoke okno: dlazdice je v dosahu hned (jinak by ji zdrzelo i samotne lenive spusteni pri doskrolovani)
  if (opts && opts.zrusVolby) await ctx.route(/\/api\/shop\/products\/[^/]+\/configurator(\?|$)/, r => r.abort());
  const pg = await ctx.newPage(); const errs = []; pg.on("pageerror", e => errs.push(e.message));
  const cons = []; pg.on("console", m => { if (m.type() === "warning" || m.type() === "error") cons.push(m.text()); });
  const cdp = await ctx.newCDPSession(pg); await cdp.send("Network.enable");
  const id2url = {}, enc = {}, cache = new Set(), start = {}, konec = {}; const t0 = Date.now();
  cdp.on("Network.requestWillBeSent", e => { id2url[e.requestId] = e.request.url; if (start[e.request.url] == null) start[e.request.url] = Date.now() - t0; });
  cdp.on("Network.requestServedFromCache", e => cache.add(e.requestId));
  cdp.on("Network.loadingFinished", e => { enc[e.requestId] = e.encodedDataLength; konec[id2url[e.requestId]] = Date.now() - t0; });
  const stazeni = (re) => Object.keys(id2url).filter(id => re.test(id2url[id]) && !cache.has(id) && (enc[id] || 0) > 0).length;
  await pg.goto(URL_PRODUKT, { waitUntil: "domcontentloaded" });
  return { ctx, pg, errs, cons, start, konec, stazeni, id2url, t0 };
}
const zavri = (b) => Promise.race([b.close(), new Promise(r => setTimeout(r, 15000))]);   // dlazdice pod SwiftShaderem zdrzuje opusteni stranky
const prvni = (o, re) => { const k = Object.keys(o).filter(u => re.test(u)); return k.length ? Math.min(...k.map(u => o[u])) : null; };

(async () => {
  const browser = await chromium.launch({ args: ARGS });
  // ---- beh 1: bez zasahu
  const A = await otevri(browser);
  await A.pg.waitForFunction(() => document.querySelector(".mw-win-stage canvas, .pdc-stage canvas"), null, { timeout: 90000 });
  const cekej = async (cond, ms) => { const t = Date.now(); while (Date.now() - t < ms) { if (cond()) return true; await A.pg.waitForTimeout(150); } return false; };
  const glbRe = /\/configurator\/glb\//;
  await cekej(() => prvni(A.konec, glbRe) != null, 60000);
  const tileRe = /pripni-cokoli-tile\.js/;
  const tileDosel = await cekej(() => prvni(A.start, tileRe) != null, 40000);
  const tGlbKonec = prvni(A.konec, glbRe), tTile = prvni(A.start, tileRe);
  ok(tGlbKonec != null, "N0 model stolu se stáhl (GLB hotový za " + tGlbKonec + " ms)");
  ok(tileDosel && tTile >= tGlbKonec - 5, "N1 skript dlaždice Připni cokoli se začal stahovat AŽ po stažení modelu stolu (dlaždice " + tTile + " ms, model hotový " + tGlbKonec + " ms)");
  const depStart = Object.keys(A.start).filter(u => DEP.test(u)).map(u => A.start[u]);
  ok(depStart.length >= 8, "N2a viewer a závislosti three se načítají (" + depStart.length + " skriptů)");
  const rozptyl = Math.max(...depStart) - Math.min(...depStart);
  ok(rozptyl < 250, "N2 skripty 3D prohlížeče se stahují PARALELNĚ: všechny začnou během " + rozptyl + " ms (po jednom by to bylo stovky ms)");
  const nGlb = A.stazeni(glbRe);
  ok(nGlb === 1, "N3 model stolu se ze sítě stáhne jednou (předstažení + GLTFLoader z mezipaměti): " + nGlb + "×");
  const hrefs = await A.pg.$$eval("link[rel=preload][as=script]", l => l.map(x => x.href));
  ok(hrefs.length >= 8, "N4a stránka má preload skriptů 3D prohlížeče (" + hrefs.length + ")");
  const nepouzite = hrefs.filter(h => A.start[h] == null);
  const dvakrat = hrefs.filter(h => Object.keys(A.id2url).filter(id => A.id2url[id] === h).length > 1 && A.stazeni(new RegExp(h.replace(/[.*+?^${}()|[\]\\\/]/g, "\\$&"))) > 1);
  const preloadVarovani = A.cons.filter(t => /preload/i.test(t));
  ok(!nepouzite.length && !dvakrat.length, "N4 preload souhlasí s požadavky stránky (nepoužité: " + (nepouzite.join(", ") || "žádné") + "; staženo dvakrát: " + (dvakrat.join(", ") || "žádné") + ")");
  ok(!preloadVarovani.length, "N4b prohlížeč nehlásí nepoužitý preload" + (preloadVarovani[0] ? " | " + preloadVarovani[0].slice(0, 160) : ""));
  const chyb = A.errs.filter(e => !/Failed to load resource/.test(e));
  ok(!chyb.length, "N6 bez JS chyb na stránce" + (chyb[0] ? " | " + chyb[0] : ""));
  await A.pg.close({ runBeforeUnload: false }).catch(() => {}); await A.ctx.close().catch(() => {});

  // ---- beh 2: volby se nenactou (API selze) -> dlazdice se presto nacte, brana se nezasekne
  const B = await otevri(browser, { zrusVolby: true });
  const t = Date.now(); let tile2 = null;
  while (Date.now() - t < 30000) { tile2 = prvni(B.start, tileRe); if (tile2 != null) break; await B.pg.waitForTimeout(150); }
  ok(tile2 != null && tile2 < 12000, "N5 když se volby nenačtou, dlážice se přesto načte (za " + tile2 + " ms, ne až po záložním limitu)");
  await B.pg.close({ runBeforeUnload: false }).catch(() => {}); await B.ctx.close().catch(() => {});
  await zavri(browser); console.log(`\n==> ${total - bad}/${total} kontrol OK`); process.exit(bad ? 1 : 0);
})();
