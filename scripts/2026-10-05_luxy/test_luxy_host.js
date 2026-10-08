// Test POCITADLA LUXU v Generatoru stolu (js/stul-luxy.js + api/stul_osvetleni.py; bot10, 2026-10-05; Robert: "zakomponuj to pocitadlo luxu do generatoru").
// SKUTECNA stranka (zamestnanecky generator i zakaznicky embed) + SKUTECNY viewer3d.js + SKUTECNY GLB a payload ze serveru pres most _most_stul.py (fiktivni karty, nic se nezapisuje):
//   systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --setenv=HOME=/root --setenv=PID40=9877 --setenv=PID35=9878 --working-directory=/opt/konfigurator \
//     api/venv/bin/python3 scripts/2026-10-02_stul_testy/_most_stul.py scripts/2026-10-05_luxy/test_luxy_host.js 4934
// Hlida: skripty pocitadla se nacitaji AZ po zapnuti, cifry v HUD = NEZAVISLY vypocet LuxCore (node) nad tim samym payloadem ze serveru (po vsech zmenach), stupen 33 W / 21 W,
// zmena rozmeru / vypnuti LED / zivé tazeni (cifry se behem tazeni vypnou a vraci s presnym modelem), kompaktni zobrazeni na nizkem platne, embed, mobil, zadne chyby.
const { chromium } = require("/opt/konfigurator/node_modules/playwright");
const path = require("path");
const REPO = path.resolve(__dirname, "..", "..");
const LuxCore = require(path.join(REPO, "webapp/js/lux/lux-core.js")), LuxData = require(path.join(REPO, "webapp/js/lux/lux-data.js"));
const BASE = process.env.BASE, SHOT = process.env.SHOT || "", TYP_SKU = { led_1200: "LED1200" };
let bad = 0, total = 0;
const t = (name, cond, detail) => { total++; if (!cond) bad++; console.log(`[${cond ? "OK   " : "CHYBA"}] ${name}${!cond && detail !== undefined ? " | " + (typeof detail === "string" ? detail : JSON.stringify(detail)) : ""}`); };
const GLB_RE = /\/api\/shop\/configurator\/glb\//, RES_RE = /\/api\/shop\/configurator\/resolve/, LUX_RE = /\/js\/lux\/|\/css\/lux\.css/;
async function mk(browser, w, h) {
  const ctx = await browser.newContext({ viewport: { width: w || 1400, height: h || 900 }, locale: "cs-CZ" });
  await ctx.addInitScript(() => { window.__pdcDebug = true; });
  const page = await ctx.newPage(); const errs = [], luxReq = [], badResp = [];
  const trk = { resolve: 0, pending: 0, last: Date.now() };
  page.on("pageerror", e => errs.push(e.message));
  page.on("response", r => { if (r.status() >= 400) badResp.push(r.status() + " " + r.request().method() + " " + r.url().replace(BASE, "")); });
  page.on("console", m => { if (m.type() === "error" && !/favicon|Failed to load resource/.test(m.text())) errs.push("console: " + m.text()); });
  page.on("request", r => { const u = r.url(); if (LUX_RE.test(u)) luxReq.push(u.replace(BASE, "")); if (RES_RE.test(u)) { trk.resolve++; trk.pending++; trk.last = Date.now(); } else if (GLB_RE.test(u)) { trk.pending++; trk.last = Date.now(); } });
  const done = r => { if (RES_RE.test(r.url()) || GLB_RE.test(r.url())) { trk.pending--; trk.last = Date.now(); } };
  page.on("requestfinished", done); page.on("requestfailed", done);
  return { ctx, page, trk, errs, luxReq, badResp };
}
const idle = async (p, quiet) => {
  const q = quiet || 1200; await p.page.waitForTimeout(q);
  const t0 = Date.now();
  while (Date.now() - t0 < 90000) { if (p.trk.pending <= 0 && Date.now() - p.trk.last > q) return; await p.page.waitForTimeout(100); }
};
async function load(p, pagePath, hash) {
  await p.page.goto(`${BASE}${pagePath}?debug=1${hash || ""}`, { waitUntil: "load" });
  await p.page.waitForSelector(".pdc-stage .v3d-root canvas", { timeout: 90000 });
  await p.page.waitForFunction(() => { const S = window.__pdcState; return S && S.last && S.last.hash && window.__v3d && window.__v3d.state().modelSeq >= 1; }, null, { polling: 200, timeout: 90000 });
  await idle(p, 900);
}
// cislo z HUD ("Průměr: ≈ 1 036 lx" -> 1036)
const hudMean = p => p.page.evaluate(() => { const e = document.querySelector(".lux-hud .lux-main-number"); if (!e) return null; const m = e.textContent.replace(/[\s  ]/g, "").match(/≈(\d+)lx/); return m ? Number(m[1]) : e.textContent; });
const stav = p => p.page.evaluate(() => window.__stulLux ? window.__stulLux._state() : null);
const payloadNow = p => p.page.evaluate(() => { const S = window.__pdcState; return { hash: S.last.hash, o: S.last.vodici && S.last.vodici.osvetleni || null }; });
function vypocet(o, mode) {                                       // NEZAVISLE: LuxCore + katalog LuxData nad payloadem ze serveru (to, co posila resolve)
  const input = { version: o.version, units: o.units, workplane: o.workplane, lights: o.lights.map(g => Object.assign({}, LuxData.selectLight(TYP_SKU[g.typ], mode), g, { dimmingFactor: 1 })) };
  return LuxCore.calculate(input, { allowEstimate: true });
}
const hcenter = async (page, id) => { const b = await page.locator("#v3do_" + id).boundingBox(); return { x: b.x + b.width / 2, y: b.y + b.height / 2 }; };
async function dragTo(page, id, dx, dy, hold) {
  const c = await hcenter(page, id);
  await page.mouse.move(c.x, c.y); await page.mouse.down();
  for (let i = 1; i <= 10; i++) await page.mouse.move(c.x + dx * i / 10, c.y + dy * i / 10);
  await page.waitForTimeout(hold || 600);
}
const overlay = p => p.page.evaluate(() => !!document.querySelector(".lux-overlay"));

(async () => {
  const browser = await chromium.launch({ args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });

  console.log("\n## A) zamestnanecky generator (desktop 1400 x 900)");
  const p = await mk(browser);
  await load(p, "/stul-konfigurator.html");
  const bar0 = await p.page.evaluate(() => { const b = document.querySelector(".stl-lux-bar"), c = document.querySelector(".stl-lux-btn"); return b && { hidden: b.hidden, text: c.textContent.trim(), pressed: c.getAttribute("aria-pressed"), modesHidden: b.querySelector(".stl-lux-modes").hidden, inStage: !!b.closest(".pdc-stage") }; });
  t("A1 tlacitko Osvetleni · lux je ve 3D nahledu, nestisknute, stupne skryte", bar0 && !bar0.hidden && bar0.text === "Osvětlení · lux" && bar0.pressed === "false" && bar0.modesHidden && bar0.inStage, bar0);
  t("A2 skripty pocitadla se pred zapnutim NEnacitaji (0 pozadavku na /js/lux/, /css/lux.css)", p.luxReq.length === 0 && !(await overlay(p)), p.luxReq);
  const pl0 = await payloadNow(p);
  t("A3 odpoved ze serveru nese vodici.osvetleni s 1 svitidlem a pracovni rovinou", pl0.o && pl0.o.lights.length === 1 && pl0.o.workplane.widthMm > 1200 && pl0.o.workplane.axisU.join() === "0,0,1", pl0.o && Object.keys(pl0.o));
  await p.page.click(".stl-lux-btn");
  await p.page.waitForSelector(".lux-hud .lux-main-number", { timeout: 30000 });
  await p.page.waitForTimeout(800);
  t("A4 po zapnuti se nacetly 4 soubory pocitadla (css, core, data, plugin) a HUD je videt", p.luxReq.length === 4 && p.luxReq.some(u => /lux-core/.test(u)) && p.luxReq.some(u => /lux\.css/.test(u)) && await overlay(p), p.luxReq);
  const st1 = await stav(p);
  t("A5 stav: zapnuto, bezi, stupen 33W, payload k zobrazenemu modelu", st1.enabled && st1.running && st1.mode === "33W" && st1.payload && st1.shownHash === pl0.hash && !st1.stale, st1);
  let ref = vypocet(pl0.o, "33W");
  t("A6 cifra v HUD = nezavisly vypocet LuxCore nad payloadem ze serveru (33 W: " + Math.round(ref.meanLux) + " lx)", (await hudMean(p)) === Math.round(ref.meanLux), [await hudMean(p), ref.meanLux]);
  t("A7 nad deskou jsou cifry (aspon 1 viditelny stitek, plugin schovava ty, ktere by se prekryvaly) a souhrn nese normy", await p.page.evaluate(() => document.querySelectorAll(".lux-point:not([hidden])").length >= 1 && /EN 12464-1/.test(document.querySelector(".lux-hud").textContent)));
  const modes = await p.page.evaluate(() => [...document.querySelectorAll(".stl-lux-modes button")].map(b => [b.getAttribute("data-mode"), b.textContent, b.getAttribute("aria-pressed")]));
  t("A8 tlacitka stupnu 33 W / 21 W (33 W stisknute)", JSON.stringify(modes) === JSON.stringify([["33W", "33 W", "true"], ["21W", "21 W", "false"]]), modes);
  if (SHOT) await p.page.screenshot({ path: SHOT + "_staff_desktop.png" });
  await p.page.click('.stl-lux-modes button[data-mode="21W"]');
  await p.page.waitForTimeout(500);
  const ref21 = vypocet(pl0.o, "21W");
  t("A9 stupen 21 W: cifra = nezavisly vypocet (" + Math.round(ref21.meanLux) + " lx) a pomer k 33 W = 2600 / 3960", (await hudMean(p)) === Math.round(ref21.meanLux) && Math.abs(ref21.meanLux / ref.meanLux - 2600 / 3960) < 1e-9, [await hudMean(p), ref21.meanLux]);
  t("A10 tlacitko 21 W je stisknute, 33 W ne", await p.page.evaluate(() => document.querySelector('[data-mode="21W"]').getAttribute("aria-pressed") === "true" && document.querySelector('[data-mode="33W"]').getAttribute("aria-pressed") === "false"));
  await p.page.click('.stl-lux-modes button[data-mode="33W"]');
  await p.page.waitForTimeout(400);

  // hover na LED (jen mys): souradnice LED z payloadu promitnute nezavislym prumetem (jako test_stul_host.js), panel s udaji svitidla.
  // Od LED rucne (47061e92) lezi ve STREDU vychoziho svitidla DOM uchyt jeho polohy (#v3do_ledpos1, nad platnem): mys nad nim nedela pointermove na platne, takze se hleda bod
  // na telese svitidla (po jeho delce = osa z), ktery neni pod zadnym uchytem (stred prvni).
  const scr = await p.page.evaluate((o) => {
    const S = window.__pdcState, c = S.viewer.cameraInfo(), L = o.lights[0].housingBoundsMm;
    const cam = new THREE.PerspectiveCamera(c.fov, c.aspect, c.near, c.far); cam.position.fromArray(c.pos); cam.up.fromArray(c.up);
    cam.lookAt(new THREE.Vector3().fromArray(c.target)); cam.updateMatrixWorld(); cam.updateProjectionMatrix();
    const r = document.querySelector(".v3d-stage canvas").getBoundingClientRect();
    for (const f of [0.5, 0.3, 0.7, 0.2, 0.8, 0.4, 0.6, 0.1, 0.9]) {
      const P = [(L[0][0] + L[1][0]) / 2, (L[0][1] + L[1][1]) / 2, L[0][2] + (L[1][2] - L[0][2]) * f];
      const v = new THREE.Vector3(P[0], P[1], P[2]).project(cam), x = r.left + (v.x + 1) / 2 * r.width, y = r.top + (1 - v.y) / 2 * r.height, el = document.elementFromPoint(x, y);
      if (!(el && el.closest && el.closest(".v3do-h"))) return { x, y, f, rect: [r.left, r.top, r.width, r.height] };
    }
    return null;
  }, pl0.o);
  t("A11a na telese svitidla je bod, ktery neni pod uchytem ovladani (pro najeti mysi)", !!scr, scr);
  await p.page.mouse.move(scr.rect[0] + 5, scr.rect[1] + scr.rect[3] - 5); await p.page.waitForTimeout(200);
  await p.page.mouse.move(scr.x, scr.y, { steps: 6 }); await p.page.waitForTimeout(500);
  const panel = await p.page.evaluate(() => { const e = document.querySelector(".lux-hover"); return e && !e.hidden ? e.innerText.replace(/\n+/g, " | ").slice(0, 1500) : null; });
  t("A11 najeti mysi na LED otevre panel svitidla (LEDVANCE, normy)", !!panel && /LEDVANCE/i.test(panel) && /EN 12464-1/.test(panel), panel);
  const pan = await p.page.evaluate(() => { const e = document.querySelector(".lux-hover").getBoundingClientRect(), b = document.querySelector(".stl-lux-bar").getBoundingClientRect(), ov = document.querySelector(".pdc-ov"), dim = document.querySelector(".v3d-dim");
    return { overlayVis: ov && getComputedStyle(ov).visibility, dimVis: dim ? getComputedStyle(dim).visibility : "hidden", panelBottom: Math.round(e.bottom), barTop: Math.round(b.top), cls: document.querySelector(".pdc-stage").classList.contains("stl-lux-panel-open") }; });
  t("A11b dokud je panel otevreny: uchyty a napovedy ovladani ve 3D i kóty jsou skryte a panel nezasahuje pod listu tlacitek", pan.overlayVis === "hidden" && pan.dimVis === "hidden" && pan.cls && pan.panelBottom <= pan.barTop + 1, pan);
  if (SHOT) await p.page.screenshot({ path: SHOT + "_staff_panel.png" });
  await p.page.mouse.move(scr.rect[0] + 5, scr.rect[1] + scr.rect[3] - 5, { steps: 6 }); await p.page.waitForTimeout(500);
  t("A12 odjeti mysi panel zavre a uchyty ovladani jsou zase videt", await p.page.evaluate(() => { const e = document.querySelector(".lux-hover"), ov = document.querySelector(".pdc-ov"); return (!e || e.hidden) && getComputedStyle(ov).visibility === "visible" && !document.querySelector(".pdc-stage").classList.contains("stl-lux-panel-open"); }));

  console.log("\n## B) zmena rozmeru, vypnuti LED, zivé tazeni");
  const hash0 = (await payloadNow(p)).hash;
  await p.page.evaluate(() => { const n = document.querySelector('[data-slot="w"] input[type="number"]'); n.value = "1600"; n.dispatchEvent(new Event("input", { bubbles: true })); n.dispatchEvent(new Event("change", { bubbles: true })); });
  await p.page.waitForFunction(h => window.__pdcState.last.hash !== h && window.__stulLux._state().shownHash === window.__pdcState.last.hash, hash0, { timeout: 60000, polling: 200 });
  await idle(p, 1500);
  const pl1 = await payloadNow(p);
  const ref1 = vypocet(pl1.o, "33W");
  t("B1 po zmene sirky na 1600: nove cifry odpovidaji novemu payloadu (" + Math.round(ref1.meanLux) + " lx), sirka roviny " + pl1.o.workplane.widthMm, (await hudMean(p)) === Math.round(ref1.meanLux) && Math.abs(pl1.o.workplane.widthMm - 1600) < 0.5 && Math.round(ref1.meanLux) !== Math.round(ref.meanLux), [await hudMean(p), ref1.meanLux, pl1.o.workplane.widthMm]);
  t("B2 pocitadlo po vymene modelu bezi (znovu spusteno az po onModel), stupen i zapnuti zachovany", await (async () => { const s = await stav(p); return s.running && s.enabled && s.mode === "33W" && s.shownHash === pl1.hash && !s.stale; })());

  // zive tazeni sirky: cifry se behem tazeni vypnou
  const hidP = (await payloadNow(p)).hash;
  await p.page.waitForFunction(() => window.__pdcState && window.__pdcState.ov && Object.keys(window.__pdcState.ov.debug().handles).length > 0, null, { polling: 200, timeout: 60000 });
  await dragTo(p.page, "w", 90, 0, 900);
  const sd = await stav(p);
  t("B3 behem zziveho tazeni: pocitadlo vypnute (bez prekryvu), stav dragging a stale", sd.dragging && sd.stale && !sd.running && !(await overlay(p)), sd);
  await p.page.mouse.up(); await idle(p, 2000);
  const pl2 = await payloadNow(p), s2 = await stav(p);
  t("B4 po pusteni: presny model ze serveru (nova konfigurace) a cifry zpet", pl2.hash !== hidP && s2.running && !s2.stale && !s2.dragging && s2.shownHash === pl2.hash && await overlay(p), [pl2.hash, hidP, s2]);
  const ref2 = vypocet(pl2.o, "33W");
  t("B5 cifra po tazeni = nezavisly vypocet nad novym payloadem (" + Math.round(ref2.meanLux) + " lx, sirka " + pl2.o.workplane.widthMm + ")", (await hudMean(p)) === Math.round(ref2.meanLux), [await hudMean(p), ref2.meanLux]);
  // Esc behem tazeni: hodnota se vrati, hash stejny jako pred tazenim -> cifry se vrati
  const hE = (await payloadNow(p)).hash;
  await dragTo(p.page, "w", -90, 0, 700);
  const sEd = await stav(p);
  await p.page.keyboard.press("Escape"); await p.page.mouse.up(); await idle(p, 2000);
  const sE = await stav(p), plE = await payloadNow(p);
  t("B6 Esc behem tazeni: pocitadlo bylo vypnute a po zruseni se vraci (hash stejny " + (plE.hash === hE) + ")", sEd.dragging && !sEd.running && plE.hash === hE && sE.running && !sE.stale && await overlay(p), [sEd, sE, plE.hash, hE]);

  // vypnuti LED: lista zmizi, po zapnuti se pocitadlo samo vrati (volba zapnuto zustala)
  await p.page.evaluate(() => { const cb = document.querySelector('[data-slot="led"] input[type="checkbox"]'); if (cb && cb.checked) cb.click(); });
  await p.page.waitForFunction(() => { const s = window.__stulLux._state(); return !s.payload; }, null, { timeout: 60000, polling: 200 });
  await idle(p, 1200);
  const sOff = await stav(p);
  t("B7 LED vypnuta: lista skryta, pocitadlo nebezi, v GLB zadny prekryv, odpoved bez osvetleni", await p.page.evaluate(() => document.querySelector(".stl-lux-bar").hidden === true && !document.querySelector(".lux-overlay") && !window.__pdcState.last.vodici.osvetleni) && !sOff.running && sOff.enabled, sOff);
  await p.page.evaluate(() => { const cb = document.querySelector('[data-slot="led"] input[type="checkbox"]'); if (cb && !cb.checked) cb.click(); });
  await p.page.waitForFunction(() => { const s = window.__stulLux._state(); return s.payload && s.running; }, null, { timeout: 60000, polling: 200 });
  const plOn = await payloadNow(p);
  t("B8 LED znovu zapnuta: pocitadlo se samo vraci a sedi s payloadem", (await hudMean(p)) === Math.round(vypocet(plOn.o, "33W").meanLux), [await hudMean(p)]);
  await p.page.click(".stl-lux-btn"); await p.page.waitForTimeout(400);
  const sFin = await stav(p);
  t("B9 vypnuti tlacitkem: prekryv zmizel, pocitadlo nebezi, tlacitko nestisknute, stupne skryte", !sFin.enabled && !sFin.running && !(await overlay(p)) && await p.page.evaluate(() => document.querySelector(".stl-lux-btn").getAttribute("aria-pressed") === "false" && document.querySelector(".stl-lux-modes").hidden), sFin);
  t("B10 zadne chyby ve strance (desktop)", p.errs.length === 0, p.errs.slice(0, 4));

  console.log("\n## C) zamestnanecky generator na mobilu (390 x 844): nizke platno = kompaktni souhrn");
  const m = await mk(browser, 390, 844);
  await load(m, "/stul-konfigurator.html");
  await m.page.click(".stl-lux-btn");
  await m.page.waitForSelector(".lux-hud .lux-main-number", { timeout: 30000 });
  await m.page.waitForTimeout(800);
  const geo = await m.page.evaluate(() => {
    const st = document.querySelector(".v3d-stage"), h = document.querySelector(".lux-hud").getBoundingClientRect(), b = document.querySelector(".stl-lux-bar").getBoundingClientRect(), s = st.getBoundingClientRect();
    return { compact: st.classList.contains("stl-lux-compact"), stageH: Math.round(s.height), hudBottom: Math.round(h.bottom - s.top), barTop: Math.round(b.top - s.top), barRight: Math.round(s.right - b.right), btn: document.querySelector(".stl-lux-btn").textContent.trim(),
             visibleSmall: [...document.querySelectorAll(".lux-hud small")].filter(e => e.offsetParent).length, hscroll: document.documentElement.scrollWidth > window.innerWidth + 1, barInside: b.left >= s.left - 1 && b.right <= s.right + 1 };
  });
  t("C1 nizke platno: kompaktni souhrn (jen minimum + normy), souhrn nezasahuje pod listu, tlacitko ma kratky popisek Lux", geo.compact && geo.stageH < 320 && geo.visibleSmall <= 2 && geo.hudBottom <= geo.barTop + 1 && geo.btn === "Lux" && !geo.hscroll && geo.barInside, geo);
  if (SHOT) await m.page.screenshot({ path: SHOT + "_staff_mobil.png" });
  t("C2 mobil: cifra = nezavisly vypocet", (await hudMean(m)) === Math.round(vypocet((await payloadNow(m)).o, "33W").meanLux));
  t("C3 mobil: zadne chyby", m.errs.length === 0, m.errs.slice(0, 3));
  await m.ctx.close();

  console.log("\n## D) zakaznicky embed (/embed/stul.html?p=4934)");
  const e = await mk(browser, 1100, 900);
  await load(e, "/embed/stul.html", "&p=4934");
  t("D1 embed: tlacitko je, skripty se nenacitaji dokud se nezapne", await e.page.evaluate(() => !!document.querySelector(".stl-lux-btn") && !document.querySelector(".stl-lux-bar").hidden) && e.luxReq.length === 0, e.luxReq);
  await e.page.click(".stl-lux-btn");
  await e.page.waitForSelector(".lux-hud .lux-main-number", { timeout: 30000 });
  await e.page.waitForTimeout(600);
  const plE2 = await payloadNow(e);
  t("D2 embed: cifra = nezavisly vypocet (" + Math.round(vypocet(plE2.o, "33W").meanLux) + " lx)", (await hudMean(e)) === Math.round(vypocet(plE2.o, "33W").meanLux), await hudMean(e));
  if (SHOT) await e.page.screenshot({ path: SHOT + "_embed_desktop.png" });
  t("D3 embed: zadne chyby ve strance a zadna chybna odpoved (>= 400) se netyka pocitadla (testovaci most nezna HEAD / nektere cesty)", e.errs.length === 0 && !e.badResp.some(u => /lux|stul-luxy/.test(u)), [e.errs.slice(0, 3), e.badResp.slice(0, 6)]);
  await e.ctx.close();

  console.log("\n## E) embed na mobilu (390 x 844)");
  const em = await mk(browser, 390, 844);
  await load(em, "/embed/stul.html", "&p=4934");
  await em.page.click(".stl-lux-btn");
  await em.page.waitForSelector(".lux-hud .lux-main-number", { timeout: 30000 });
  await em.page.waitForTimeout(600);
  const g2 = await em.page.evaluate(() => { const st = document.querySelector(".v3d-stage"), s = st.getBoundingClientRect(), b = document.querySelector(".stl-lux-bar").getBoundingClientRect(), h = document.querySelector(".lux-hud").getBoundingClientRect();
    return { stageH: Math.round(s.height), compact: st.classList.contains("stl-lux-compact"), barInside: b.left >= s.left - 1 && b.right <= s.right + 1 && b.bottom <= s.bottom + 1, hudBottom: Math.round(h.bottom - s.top), barTop: Math.round(b.top - s.top), hscroll: document.documentElement.scrollWidth > window.innerWidth + 1 }; });
  t("E1 embed mobil: lista uvnitr platna, souhrn nad listou, bez horizontalniho posuvu", g2.barInside && g2.hudBottom <= g2.barTop + 1 && !g2.hscroll, g2);
  t("E2 embed mobil: zadne chyby ve strance a zadna chybna odpoved (>= 400) se netyka pocitadla", em.errs.length === 0 && !em.badResp.some(u => /lux|stul-luxy/.test(u)), [em.errs.slice(0, 3), em.badResp.slice(0, 6)]);
  await em.ctx.close();

  await browser.close();
  console.log(`\n${total - bad}/${total} OK`);
  process.exit(bad ? 1 : 0);
})();
