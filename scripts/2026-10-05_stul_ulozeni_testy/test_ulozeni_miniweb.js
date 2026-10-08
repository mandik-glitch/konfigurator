// "Ulozit konfiguraci" na karte produktu SK mini-shopu (Robert 2026-10-05) - SKUTECNY front-end nad skutecnym backendem (api/stul_ulozeni.py) a docasnymi tabulkami (bridge_miniweb.py;
// registry a DNS podstrcene, zadny e-mail). Overuje: tlacitko a formular slovensky s odkazem na ochranu udaju, overeni slovenskeho ICO v registru RPO, slovensky telefon (0903 -> +421903),
// ulozeni, odkaz pro navrat, obnoveni, odkaz na konfiguraci JINEHO systemu (prejde na druhy produkt shopu) a ze kosik s konfiguraci drzi jen relace (sessionStorage).
const { chromium } = require("/opt/konfigurator/node_modules/playwright");
const BASE = process.env.BASE;
let bad = 0, total = 0; const ok = (c, t) => { total++; if (!c) bad++; console.log(`[${c ? "OK   " : "CHYBA"}] ${t}`); };
const W = ".pdc-slot[data-slot=w] .pdc-num";
const reg = (q) => fetch(`${BASE}/__bridge/registry?${q}`).then(r => r.json());
const dbg = () => fetch(`${BASE}/__bridge/ulozeni`).then(r => r.json());
(async () => {
  const browser = await chromium.launch({ args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
  const ctx = await browser.newContext({ viewport: { width: 1300, height: 1100 } }); await ctx.route(/pripni-cokoli/, r => r.abort());
  const errs = [], pg = await ctx.newPage(); pg.on("pageerror", e => errs.push(e.message));
  page_ready = async (p) => { await p.locator(W).waitFor({ timeout: 90000 }); await p.waitForFunction(() => document.querySelector("#mwPdPrice") && /\d/.test(document.querySelector("#mwPdPrice").textContent), null, { timeout: 90000 }); };
  await reg("ares=ok&rpo=ok&doh=ok&dig=ok");
  await pg.goto(`${BASE}/miniweb/product.html?id=1`); await page_ready(pg);
  await pg.locator(".pdc-save:not([hidden])").waitFor({ timeout: 30000 });
  ok((await pg.locator(".pdc-save-btn").innerText()) === "Uložiť konfiguráciu" || /Uložiť/.test(await pg.locator(".pdc-save-btn").innerText()), "S1 tlačidlo je slovensky: " + await pg.locator(".pdc-save-btn").innerText());
  await pg.locator(W).fill("1600"); await pg.locator(W).blur(); await pg.waitForTimeout(2200);
  await pg.locator(".pdc-save-btn").click();
  const sp = await pg.locator(".pdc-save-consent a").count() ? await pg.locator(".pdc-save-consent a").first().getAttribute("href") : null;
  ok(sp && /legal/.test(sp), "S2 souhlas odkazuje na stránku s ochranou osobných údajov: " + sp);
  await pg.locator("#pdcSave_ico").fill("35 757 442"); await pg.locator("#pdcSave_email").fill("obchod@example.sk"); await pg.locator("#pdcSave_phone").fill("0903 123 456"); await pg.locator("#pdcSave_consent").check();
  await reg("rpo=none");
  await pg.locator(".pdc-save-go").click(); await pg.locator("#pdcSaveErr_ico:not(:empty)").waitFor({ timeout: 15000 });
  ok(/nenašlo|nenašiel|nenájdené|nenašlo/i.test(await pg.locator("#pdcSaveErr_ico").innerText()), "S3 IČO, které slovenský registr (RPO) nezná: " + await pg.locator("#pdcSaveErr_ico").innerText());
  await reg("rpo=ok");
  await pg.locator(".pdc-save-go").click(); await pg.locator(".pdc-save-done:not([hidden])").waitFor({ timeout: 20000 });
  const link = await pg.locator(".pdc-save-link").inputValue();
  ok(/[?&]ulozena=[A-Za-z0-9_-]{22}/.test(link) && /id=1/.test(link), "S4 uloženo, odkaz drží stránku produktu i token: " + link.replace(BASE, ""));
  const d = await dbg(), r0 = d.saved[0] || {};
  ok(d.saved.length === 1 && r0.country === "SK" && r0.phone === "+421903123456" && r0.ico === "35757442" && r0.karta_id === 4934 && /baliace-stoly/.test(r0.shop_host || ""), "S5 na serveru: země SK, telefon +421903123456, IČO 35757442, karta 4934, host shopu " + r0.shop_host);
  // obnoveni a odkaz na jiny system
  const p2 = await ctx.newPage(); p2.on("pageerror", e => errs.push(e.message));
  await p2.goto(link); await page_ready(p2); await p2.locator(".pdc-save-notice:not([hidden])").waitFor({ timeout: 20000 });
  ok((await p2.locator(W).inputValue()) === "1600" && /načítan/.test(await p2.locator(".pdc-save-notice").innerText()), "S6 odkaz vrátí uloženou konfiguráciu (šírka 1600) a zobrazí zprávu: " + await p2.locator(".pdc-save-notice").innerText());
  const p3 = await ctx.newPage(); p3.on("pageerror", e => errs.push(e.message));
  const tok = link.match(/ulozena=([A-Za-z0-9_-]{22})/)[1];
  await p3.goto(`${BASE}/miniweb/product.html?id=2&ulozena=${tok}`); await page_ready(p3);
  ok(/id=1/.test(p3.url()) && (await p3.locator(W).inputValue()) === "1600", "S7 token systému 30 otevřený na produktu systému 40 přesměruje na produkt systému 30 s uloženou konfigurací: " + p3.url().replace(BASE, ""));
  // kosik s konfiguraci jen v relaci
  await p3.locator("#mwAdd").click(); await p3.waitForTimeout(500);
  const ulozeni = await p3.evaluate(() => ({ ls: Object.keys(localStorage).filter(k => k.indexOf("mw_cart_") === 0), ss: Object.keys(sessionStorage).filter(k => k.indexOf("mw_cart_") === 0) }));
  ok(!ulozeni.ls.length && ulozeni.ss.length === 1, "S8 košík s konfiguráciou je v sessionStorage (zmizí po zatvorení prehliadača), v localStorage nie: " + JSON.stringify(ulozeni));
  await p3.evaluate(() => localStorage.setItem("mw_cart_stary", "[]")); await p3.reload(); await page_ready(p3);
  ok(await p3.evaluate(() => localStorage.getItem("mw_cart_stary") === null), "S9 starý košík z localStorage (přežil by zavření prohlížeče) se při načtení smaže");
  // stara stranka (zmena pravidel generatoru): 409 rules_changed -> text pdc.rulesChanged slovensky, nacteni noveho schematu, druhy pokus projde
  const p4 = await ctx.newPage(); p4.on("pageerror", e => errs.push(e.message));
  let stale = true, resolves = 0;
  await p4.route("**/configurator/ulozit", async (route) => { if (stale) { stale = false; const b = JSON.parse(route.request().postData()); b.configuration.rules_version = "stara-verze"; return route.continue({ postData: JSON.stringify(b) }); } return route.continue(); });
  p4.on("request", r => { if (/configurator\/resolve/.test(r.url()) && r.method() === "POST") resolves++; });
  await p4.goto(`${BASE}/miniweb/product.html?id=1`); await page_ready(p4); await p4.locator(".pdc-save:not([hidden])").waitFor({ timeout: 30000 });
  await p4.locator(".pdc-save-btn").click();
  await p4.locator("#pdcSave_ico").fill("35757442"); await p4.locator("#pdcSave_email").fill("obchod@example.sk"); await p4.locator("#pdcSave_phone").fill("0903 123 456"); await p4.locator("#pdcSave_consent").check();
  const rz0 = resolves;
  await p4.locator(".pdc-save-go").click(); await p4.locator(".pdc-save-status.is-bad").waitFor({ timeout: 15000 });
  await p4.waitForTimeout(1500);
  const hl = await p4.locator(".pdc-save-status").innerText();
  ok(/možnosti sa zmenili/.test(hl) && resolves > rz0 && await p4.locator(".pdc-save-form").isVisible(), "S10 409 rules_changed: hláška „" + hl + "“, modul načítal nové schéma (resolve +" + (resolves - rz0) + "), formulár zostal vyplnený");
  await p4.locator(".pdc-save-go").click(); await p4.locator(".pdc-save-done:not([hidden])").waitFor({ timeout: 20000 });
  ok((await dbg()).saved.length === 2, "S11 po načítaní novej schémy druhé uloženie prejde (na serveri 2 záznamy)");
  ok(!errs.length, "X bez JS chyb" + (errs[0] ? " | " + errs[0] : ""));
  await Promise.race([browser.close(), new Promise(r => setTimeout(r, 15000))]); console.log(`\n==> ${total - bad}/${total} kontrol OK`); process.exit(bad ? 1 : 0);
})();
