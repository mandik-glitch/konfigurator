// NAVLEK NOHOU (jekl 40x40x2, system 35; bot10 2026-10-05, commit 1f192f9c) ve zakaznickem generatoru (vlozeny embed) - SKUTECNY prohlizec nad skutecnym API (bridge.py: PID35 = system 35):
// dva nove radky `sleeve` (prepinac) a `sleevelen` (posuvnik 200-400 po 10 mm) se vykresli sami podle schematu, texty z API (cesky), vychozi stav (navlek zapnuty, 300 mm, kolecka zakazana s duvodem),
// `sleevelen` se pri vypnutem `sleeve` SCHOVA a po zapnuti vrati s puvodni hodnotou, na 360 a 320 px se radky vejdou bez vodorovneho posunu, prepnuti systemu 35 -> 30 -> 35 radky odebere a vrati.
// Screenshoty (volitelne): SHOT_DIR=<slozka>.
const { chromium } = require("/opt/konfigurator/node_modules/playwright");
const BASE = process.env.BASE, PID35 = process.env.PID35, PID = process.env.PID, SHOT_DIR = process.env.SHOT_DIR || "";
let bad = 0, total = 0; const ok = (c, t) => { total++; if (!c) bad++; console.log(`[${c ? "OK   " : "CHYBA"}] ${t}`); };
const slot = (s) => `.pdc-slot[data-slot=${s}]`;
(async () => {
  const browser = await chromium.launch({ args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] }); const errs = [];
  const open = async (w, pid, mobile) => {
    const ctx = await browser.newContext({ viewport: { width: w, height: 900 }, isMobile: !!mobile, hasTouch: !!mobile }); const pg = await ctx.newPage(); pg.on("pageerror", e => errs.push(e.message));
    await pg.addInitScript(() => { window.__pdcDebug = true; });
    await pg.goto(`${BASE}/embed/stul.html?p=${pid}`); await pg.locator(slot("w")).waitFor({ timeout: 90000 }); await pg.locator(".emb-order-btn:not([disabled])").waitFor({ timeout: 90000 }); await pg.waitForTimeout(3000);
    return { ctx, pg };
  };
  const vis = (pg, s) => pg.locator(slot(s)).isVisible().catch(() => false);
  let { ctx, pg } = await open(1300, PID35);
  ok(await vis(pg, "sleeve") && await vis(pg, "sleevelen"), "N1 u systému 35 jsou vidět oba nové řádky: návlek (přepínač) a délka návleku (posuvník)");
  const txt = async (s) => (await pg.locator(slot(s)).innerText()).replace(/\s+/g, " ").trim();
  const tSleeve = await txt("sleeve"), tLen = await txt("sleevelen");
  ok(tSleeve.length > 3 && !/^sleeve$/i.test(tSleeve) && tLen.length > 3 && !/^sleevelen$/i.test(tLen), "N2 texty řádků jsou z API (česky), ne surové klíče: „" + tSleeve.slice(0, 60) + "“ | „" + tLen.slice(0, 60) + "“");
  const sel0 = await pg.evaluate(() => ({ sleeve: window.__pdcState.sel.sleeve, sleevelen: window.__pdcState.sel.sleevelen, wheels: window.__pdcState.sel.wheels }));
  ok(sel0.sleeve === true && sel0.sleevelen === 300 && sel0.wheels === false, "N3 výchozí výběr systému 35: návlek zapnutý, 300 mm, bez koleček: " + JSON.stringify(sel0));
  const rng = await pg.locator(slot("sleevelen") + " .pdc-range").evaluate(e => ({ min: e.min, max: e.max, step: e.step, value: e.value }));
  ok(Number(rng.min) === 200 && Number(rng.max) === 400 && Number(rng.step) === 10 && Number(rng.value) === 300, "N4 posuvník délky: 200–400 mm po 10 mm, hodnota 300: " + JSON.stringify(rng));
  // modul nedostupnou volbu NEzamyka natvrdo: vypada "nedostupne" (styl pdc-na) a pri pokusu o zapnuti ukaze duvod u radku a hodnotu nezmeni
  const na = async (s) => pg.locator(slot(s) + " label.pd-opt").evaluate(e => ({ na: e.classList.contains("pdc-na"), title: e.getAttribute("title") || "" }));
  const nw = await na("wheels"), nf = await na("feet");
  ok(nw.na && nf.na, "N5 kolečka i patky vypadají při návleku nedostupně (styl pdc-na; důvod ukáže pokus o zapnutí, viz N6)");
  await pg.locator(slot("wheels") + " input[type=checkbox]").click({ force: true }); await pg.waitForTimeout(400);
  const duvod = (await pg.locator(slot("wheels") + " .pdc-err").innerText()).replace(/\s+/g, " ").trim();
  ok(duvod.length > 25 && /návlek/i.test(duvod) && !(await pg.locator(slot("wheels") + " input[type=checkbox]").isChecked()) && (await pg.evaluate(() => window.__pdcState.sel.wheels)) === false, "N6 pokus zapnout kolečka při návleku: důvod je vidět u řádku („" + duvod.slice(0, 90) + "“), volba se nezapnula");
  // vypnuti navleku: delka se schova, kolecka se uvolni; po zapnuti se delka vrati s puvodni hodnotou
  await pg.locator(slot("sleevelen") + " .pdc-num").fill("350"); await pg.locator(slot("sleevelen") + " .pdc-num").blur(); await pg.waitForFunction(() => window.__pdcState.sel.sleevelen === 350 && !window.__pdcState.pending, null, { timeout: 60000 });
  await pg.locator(slot("sleeve") + " input[type=checkbox]").click({ force: true }); await pg.waitForFunction(() => window.__pdcState.sel.sleeve === false && !window.__pdcState.pending, null, { timeout: 60000 });
  ok(!(await vis(pg, "sleevelen")) && await vis(pg, "sleeve"), "N7 po vypnutí návleku se řádek s délkou SCHOVAL (přepínač zůstal)");
  ok(!(await na("wheels")).na, "N8 bez návleku už kolečka nevypadají nedostupně (jdou zapnout)");
  await pg.locator(slot("sleeve") + " input[type=checkbox]").click({ force: true }); await pg.waitForFunction(() => window.__pdcState.sel.sleeve === true && !window.__pdcState.pending, null, { timeout: 60000 });
  await pg.locator(slot("sleevelen")).waitFor({ state: "visible", timeout: 20000 });
  const len2 = await pg.evaluate(() => window.__pdcState.sel.sleevelen);
  ok(await vis(pg, "sleevelen") && (len2 === 350 || len2 === 300), "N9 po zapnutí návleku je délka zase vidět (" + len2 + " mm)");
  if (SHOT_DIR) { await pg.locator(slot("sleeve")).scrollIntoViewIfNeeded(); await pg.screenshot({ path: `${SHOT_DIR}/navlek_desktop.png` }); }
  // prepnuti systemu: v 30 radky nejsou, zpet v 35 jsou
  await Promise.all([pg.waitForURL(new RegExp(`[?&]p=${PID}\\b`), { timeout: 30000 }), pg.locator(".pdc-sys-b[data-system='30']").click()]);
  await pg.locator(slot("w")).waitFor({ timeout: 60000 }); await pg.locator(".emb-order-btn:not([disabled])").waitFor({ timeout: 60000 }); await pg.waitForTimeout(1500);
  ok(await pg.locator(slot("sleeve")).count() === 0 && await pg.locator(slot("sleevelen")).count() === 0, "N10 u systému 30 návlek ve schématu není (řádky se nevykreslí)");
  await Promise.all([pg.waitForURL(new RegExp(`[?&]p=${PID35}\\b`), { timeout: 30000 }), pg.locator(".pdc-sys-b[data-system='35']").click()]);
  await pg.locator(slot("sleeve")).waitFor({ state: "visible", timeout: 60000 });
  ok(await vis(pg, "sleeve") && await vis(pg, "sleevelen"), "N11 zpět na systému 35 jsou oba řádky znovu vidět (výchozí návlek)");
  await ctx.close();
  // uzky telefon
  for (const vw of [360, 320]) {
    ({ ctx, pg } = await open(vw, PID35, true));
    ok(await pg.locator(".mw-win-frame.is-closed").count() === 1 && !(await vis(pg, "sleeve")), "N12a " + vw + " px: okno „Konstrukce“ je na telefonu sbalené (řádky návleku jsou uvnitř, ne vidět)");
    await pg.locator(".mw-win-frame > .mw-win-h").click(); await pg.locator(slot("sleeve")).waitFor({ state: "visible", timeout: 10000 });          // zakaznik okno rozbali
    await pg.locator(slot("sleeve")).scrollIntoViewIfNeeded();
    const fit = await pg.evaluate((sel) => { const r = document.querySelector(sel).getBoundingClientRect(), r2 = document.querySelector(sel.replace("sleeve", "sleevelen")).getBoundingClientRect(); return { l: Math.round(Math.min(r.left, r2.left)), r: Math.round(Math.max(r.right, r2.right)), h1: Math.round(r.height), h2: Math.round(r2.height), vw: window.innerWidth, scrollW: document.documentElement.scrollWidth }; }, slot("sleeve"));
    ok(fit.l >= 0 && fit.r <= fit.vw && fit.scrollW <= fit.vw && fit.h1 > 20 && fit.h2 > 30, "N12b " + vw + " px: oba řádky se vejdou (okraje " + fit.l + "–" + fit.r + " z " + fit.vw + ", bez vodorovného posunu, výšky " + fit.h1 + " / " + fit.h2 + " px)");
    if (SHOT_DIR && vw === 360) await pg.screenshot({ path: `${SHOT_DIR}/navlek_360.png` });
    await ctx.close();
  }
  ok(!errs.length, "N13 bez JS chyb" + (errs[0] ? " | " + errs[0] : ""));
  await Promise.race([browser.close(), new Promise(r => setTimeout(r, 15000))]); console.log(`\n==> ${total - bad}/${total} kontrol OK`); process.exit(bad ? 1 : 0);
})();
