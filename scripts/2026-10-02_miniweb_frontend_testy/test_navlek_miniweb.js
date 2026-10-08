// NAVLEK NOHOU (jekl 40x40x2, system 35; bot10 1f192f9c) na karte produktu MINI-SHOPU (produkt 3 = system 35) - SKUTECNY front-end nad skutecnym API (bridge_miniweb.py, vsechny tri produkty schvalene v dockasne
// kopii): radky `sleeve` a `sleevelen` se vykresli sami, texty z API v jazyce shopu (SK; EN pri MINIWEB_HOST=<host EN shopu>), `sleevelen` se pri vypnutem navleku schova, na 360 px se okno
// Konstrukce rozbali a radky se vejdou bez vodorovneho posunu. Screenshot (volitelne): SHOT_DIR.
const { chromium } = require("/opt/konfigurator/node_modules/playwright");
const BASE = process.env.BASE, HOST = process.env.HOST || "", SHOT_DIR = process.env.SHOT_DIR || "";
let bad = 0, total = 0; const ok = (c, t) => { total++; if (!c) bad++; console.log(`[${c ? "OK   " : "CHYBA"}] ${t}`); };
const slot = (s) => `.pdc-slot[data-slot=${s}]`;
(async () => {
  await fetch(`${BASE}/__bridge/approve?products=1,2,3`);
  const browser = await chromium.launch({ args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] }); const errs = [];
  const open = async (w, mobile) => {
    const ctx = await browser.newContext({ viewport: { width: w, height: 900 }, isMobile: !!mobile, hasTouch: !!mobile }); await ctx.route(/pripni-cokoli/, r => r.abort());
    const pg = await ctx.newPage(); pg.on("pageerror", e => errs.push(e.message)); await pg.addInitScript(() => { window.__pdcDebug = true; });
    await pg.goto(`${BASE}/miniweb/product.html?id=3`); await pg.locator(slot("w")).waitFor({ state: "attached", timeout: 90000 });
    await pg.waitForFunction(() => document.querySelector("#mwPdPrice") && /\d/.test(document.querySelector("#mwPdPrice").textContent), null, { timeout: 90000 }); await pg.waitForTimeout(2500);
    return { ctx, pg };
  };
  let { ctx, pg } = await open(1300);
  const vis = (s) => pg.locator(slot(s)).isVisible().catch(() => false);
  const txt = async (s) => (await pg.locator(slot(s)).innerText()).replace(/\s+/g, " ").trim();
  ok(await vis("sleeve") && await vis("sleevelen"), "M1 na produktu systému 35 v mini-shopu jsou vidět řádky návleku a jeho délky");
  const tS = await txt("sleeve"), tL = await txt("sleevelen"); const EN = /packing-tables|\.com$/i.test(HOST) || /^en/i.test(await pg.evaluate(() => document.documentElement.lang));
  ok(tS.length > 3 && tL.length > 3 && !/^sleeve(len)?$/i.test(tS) && !/^sleeve(len)?$/i.test(tL), "M2 texty řádků jsou z API (" + (EN ? "anglicky" : "slovensky") + "): „" + tS.slice(0, 70) + "“ | „" + tL.slice(0, 50) + "“");
  ok(EN ? /sleeve|leg/i.test(tS) : /návlek|navlek/i.test(tS), "M3 text přepínače odpovídá jazyku shopu (" + (EN ? "EN" : "SK") + ")");
  await pg.locator(slot("sleeve") + " input[type=checkbox]").click({ force: true }); await pg.waitForFunction(() => window.__pdcState.sel.sleeve === false && !window.__pdcState.pending, null, { timeout: 60000 });
  ok(!(await vis("sleevelen")) && await vis("sleeve"), "M4 po vypnutí návleku se řádek s délkou SCHOVAL");
  await pg.locator(slot("sleeve") + " input[type=checkbox]").click({ force: true }); await pg.waitForFunction(() => window.__pdcState.sel.sleeve === true && !window.__pdcState.pending, null, { timeout: 60000 });
  ok(await vis("sleevelen"), "M5 po zapnutí návleku je délka zase vidět");
  await ctx.close();
  ({ ctx, pg } = await open(360, true));
  ok(await pg.locator(".mw-win-frame.is-closed").count() === 1, "M6 360 px: okno „Konstrukce“ je sbalené");
  await pg.locator(".mw-win-frame > .mw-win-h").click(); await pg.locator(slot("sleeve")).waitFor({ state: "visible", timeout: 10000 }); await pg.locator(slot("sleeve")).scrollIntoViewIfNeeded();
  const fit = await pg.evaluate((sel) => { const a = document.querySelector(sel).getBoundingClientRect(), b = document.querySelector(sel.replace("sleeve", "sleevelen")).getBoundingClientRect(); return { l: Math.round(Math.min(a.left, b.left)), r: Math.round(Math.max(a.right, b.right)), vw: window.innerWidth, sw: document.documentElement.scrollWidth }; }, slot("sleeve"));
  ok(fit.l >= 0 && fit.r <= fit.vw && fit.sw <= fit.vw, "M7 360 px: řádky se vejdou (okraje " + fit.l + "–" + fit.r + " z " + fit.vw + ", bez vodorovného posunu)");
  if (SHOT_DIR) await pg.screenshot({ path: `${SHOT_DIR}/navlek_miniweb_360.png` });
  await ctx.close();
  ok(!errs.length, "M8 bez JS chyb" + (errs[0] ? " | " + errs[0] : ""));
  await Promise.race([browser.close(), new Promise(r => setTimeout(r, 15000))]); console.log(`\n==> ${total - bad}/${total} kontrol OK`); process.exit(bad ? 1 : 0);
})();
