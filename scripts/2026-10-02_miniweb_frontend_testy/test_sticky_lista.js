// STICKY CENOVA LISTA na telefonu (mini-shop, karta produktu): lista (cena, mnozstvi, Do kosiku, montaz) nesmi zakryvat vic nez ~40 % obrazovky 360x640 a formular "Ulozit konfiguraci" nesmi byt UVNITR ni
// (mereni 2026-10-05: 375 px = 59 %, po otevreni formulare 836 px = 131 % obrazovky). Komponenta Ulozit ma vlastni nesticky okno (na desktopu pod cenou, na mobilu v toku nad listou) a po otevreni se
// formular odscrolluje nahoru obrazovky. Nad skutecnym front-endem a API (bridge_miniweb.py, SK mini-shop).
const { chromium } = require("/opt/konfigurator/node_modules/playwright");
const BASE = process.env.BASE;
let bad = 0, total = 0; const ok = (c, t) => { total++; if (!c) bad++; console.log(`[${c ? "OK   " : "CHYBA"}] ${t}`); };
(async () => {
  const browser = await chromium.launch({ args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] }); const errs = [];
  const open = async (w, h, mobile) => {
    const ctx = await browser.newContext({ viewport: { width: w, height: h }, isMobile: !!mobile, hasTouch: !!mobile }); await ctx.route(/pripni-cokoli/, r => r.abort());
    const pg = await ctx.newPage(); pg.on("pageerror", e => errs.push(e.message));
    await pg.goto(`${BASE}/miniweb/product.html?id=1`); await pg.locator(".pdc-slot[data-slot=w]").waitFor({ state: "attached", timeout: 90000 });
    await pg.waitForFunction(() => document.querySelector("#mwPdPrice") && /\d/.test(document.querySelector("#mwPdPrice").textContent), null, { timeout: 90000 }); await pg.waitForTimeout(3000);
    return { ctx, pg };
  };
  const rect = (pg, sel) => pg.evaluate((s) => { const e = document.querySelector(s); if (!e) return null; const r = e.getBoundingClientRect(), cs = getComputedStyle(e); return { top: Math.round(r.top), bottom: Math.round(r.bottom), h: Math.round(r.height), pos: cs.position, vh: window.innerHeight, hidden: e.hidden || cs.display === "none" }; }, sel);
  // ---- telefon 360x640
  let { ctx, pg } = await open(360, 640, true);
  await pg.evaluate(() => window.scrollTo(0, 500)); await pg.waitForTimeout(400);
  let bar = await rect(pg, ".mw-win-price");
  ok(bar.pos === "sticky" && bar.h <= bar.vh * 0.4, "S1 sticky lista ceny na 360×640 má " + bar.h + " px = " + Math.round(bar.h / bar.vh * 100) + " % obrazovky (limit 40 %)");
  ok(await pg.locator(".mw-win-price .pdc-save").count() === 0 && await pg.locator(".mw-win-save .pdc-save").count() === 1, "S2 komponenta Uložit konfiguráciu je v samostatném okně, ne ve sticky liště ceny");
  const order = await pg.evaluate(() => { const o = (s) => Number(getComputedStyle(document.querySelector(s)).order); return { save: o(".mw-win-save"), price: o(".mw-win-price") }; });
  ok(order.save < order.price && (await rect(pg, ".mw-win-save")).hidden === false, "S3 na telefonu je okno Uložit v toku PŘED sticky lištou (CSS order " + order.save + " < " + order.price + ") a je vidět");
  await pg.locator(".pdc-save-btn").scrollIntoViewIfNeeded(); await pg.locator(".pdc-save-btn").click(); await pg.waitForTimeout(1500);
  bar = await rect(pg, ".mw-win-price");
  ok(bar.pos === "sticky" && bar.h <= bar.vh * 0.4, "S4 po otevření formuláře Uložit zůstává lišta ceny stejně vysoká (" + bar.h + " px = " + Math.round(bar.h / bar.vh * 100) + " %, formulář ji nezvětšil)");
  const ico = await pg.locator("#pdcSave_ico").boundingBox();
  ok(ico && ico.y >= 0 && ico.y + ico.height <= bar.top + 2, "S5 po otevření je první pole formuláře (IČO) vidět NAD sticky lištou (pole " + Math.round(ico.y) + "–" + Math.round(ico.y + ico.height) + ", lišta od " + bar.top + ")");
  await pg.locator("#pdcSave_consent").scrollIntoViewIfNeeded(); await pg.evaluate(() => window.scrollBy(0, 200)); await pg.waitForTimeout(500);
  const go = await pg.locator(".pdc-save-go").boundingBox(), bar2 = await rect(pg, ".mw-win-price");
  ok(go && go.y >= 0 && go.y + go.height <= 640, "S6 tlačítko odeslání formuláře je po doscrollování dosažitelné (y " + Math.round(go.y) + ")");
  await ctx.close();
  // ---- desktop 1300x900: okno Ulozit pod cenou v postrannim sloupci, cena nesticky
  ({ ctx, pg } = await open(1300, 900, false));
  const pr = await rect(pg, ".mw-win-price"), sv = await rect(pg, ".mw-win-save");
  ok(pr.pos !== "sticky" && !sv.hidden && sv.top >= pr.bottom - 1 && sv.top <= pr.bottom + 40, "S7 desktop: okno Uložit je HNED pod cenou v postranním sloupci (cena " + pr.top + "–" + pr.bottom + ", Uložit od " + sv.top + "), cena není sticky");
  await ctx.close();
  ok(!errs.length, "S8 bez JS chyb" + (errs[0] ? " | " + errs[0] : ""));
  await Promise.race([browser.close(), new Promise(r => setTimeout(r, 15000))]); console.log(`\n==> ${total - bad}/${total} kontrol OK`); process.exit(bad ? 1 : 0);
})();
