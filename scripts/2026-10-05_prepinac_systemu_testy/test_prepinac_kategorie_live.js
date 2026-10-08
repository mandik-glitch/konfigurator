// Prepinac systemu stolu 30 / 35 / 40 na ZIVYCH strankach kategorii (206 "Lehky balici stul system 30", 312 "Ergonomicky balici stul system 35" a 311 "Robustni balici stul system 40"; bot16 2026-10-05, Robert: "prepinac dame klientovi").
// Jen CTE (otevre stranky, pocita generator pres verejne API, nic nezapisuje; kazde nacteni stranky je jako navsteva). Spusteni:  node scripts/2026-10-05_prepinac_systemu_testy/test_prepinac_kategorie_live.js
// Promenna BASE (vychozi https://autovestavby.logiman.cz). Overuje: iframe generatoru ma prepinac, klik prepne CELOU stranku na kategorii druheho systemu (nadpis, adresa) a vezme s sebou vyber.
const { chromium } = require("/opt/konfigurator/node_modules/playwright");
const BASE = process.env.BASE || "https://autovestavby.logiman.cz";
let bad = 0, total = 0; const ok = (c, t) => { total++; if (!c) bad++; console.log(`[${c ? "OK   " : "CHYBA"}] ${t}`); };
const W = ".pdc-slot[data-slot=w] .pdc-num";
(async () => {
  const browser = await chromium.launch({ args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
  const ctx = await browser.newContext({ viewport: { width: 1400, height: 1000 } }); const errs = [];
  const pg = await ctx.newPage(); pg.on("pageerror", e => errs.push(e.message));
  const frameOf = async () => {
    const h = await pg.waitForSelector("#catGeneratorFrame", { state: "attached", timeout: 60000 }); const f = await h.contentFrame();
    await f.locator(W).waitFor({ timeout: 120000 }); await f.locator(".emb-order-btn:not([disabled])").waitFor({ timeout: 120000 }); return f;
  };
  const nadpis = () => pg.locator("#catTitle").innerText();

  await pg.goto(`${BASE}/lehky-balici-stul-system-30`, { waitUntil: "domcontentloaded" });
  let f = await frameOf();
  ok((await nadpis()).includes("system 30") && await f.locator(".pdc-sys-b").count() === 3, "K1 kategorie systém 30: v generátoru je přepínač systému (" + (await nadpis()) + ")");
  ok((await f.locator(".pdc-sys-b[data-system='30']").getAttribute("aria-pressed")) === "true", "K2 zvolený je systém 30");
  await f.locator(W).fill("1700"); await f.locator(W).blur(); await pg.waitForTimeout(2500);
  await Promise.all([pg.waitForURL(/ergonomicky-balici-stul-system-35/, { timeout: 30000 }), f.locator(".pdc-sys-b[data-system='35']").click()]);
  f = await frameOf();
  ok(/system 35/i.test(await nadpis()) && /p=4955/.test(f.url()) && (await f.locator(W).inputValue()) === "1700", "K2b klik přepnul CELOU stránku na kategorii „Ergonomický balicí stůl system 35“ (karta 4955), šířka 1700 se přenesla: " + await nadpis());
  await Promise.all([pg.waitForURL(/robustni-balici-stul-system-40/, { timeout: 30000 }), f.locator(".pdc-sys-b[data-system='40']").click()]);
  f = await frameOf();
  ok((await nadpis()).includes("system 40"), "K3 klik přepnul CELOU stránku na kategorii „Robustní balicí stůl system 40“: " + await nadpis());
  ok(/p=4954/.test(f.url()) && (await f.locator(".pdc-sys-b[data-system='40']").getAttribute("aria-pressed")) === "true", "K4 generátor v nové stránce je systém 40 (karta 4954)");
  ok((await f.locator(W).inputValue()) === "1700", "K5 stejný výběr: šířka 1700 se přenesla: " + await f.locator(W).inputValue());
  await Promise.all([pg.waitForURL(/lehky-balici-stul-system-30/, { timeout: 30000 }), f.locator(".pdc-sys-b[data-system='30']").click()]);
  f = await frameOf();
  ok((await nadpis()).includes("system 30") && (await f.locator(W).inputValue()) === "1700", "K6 zpět na kategorii systému 30, šířka 1700 zůstala");
  const ctyri = errs.filter(e => !/Failed to load resource/.test(e));
  ok(!ctyri.length, "K7 bez JS chyb na stránce kategorie" + (ctyri[0] ? " | " + ctyri[0] : ""));
  await Promise.race([browser.close(), new Promise(r => setTimeout(r, 15000))]); console.log(`\n==> ${total - bad}/${total} kontrol OK`); process.exit(bad ? 1 : 0);
})();
