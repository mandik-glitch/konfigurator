// Tlacitko Objednat ve vlozenem generatoru stolu a kosik na product.html nad SKUTECNYM kosikem (api/cart.py + konfigurace_kosik.py) a generatorem - pres bridge_kosik.py
// (vse nad DOCASNYMI tabulkami, zadna data v provozu). Overuje, ze po zapnuti karty (active=1) se stul OPRAVDU prida do kosiku, cena a kod sedi s generatorem, stejny vyber = stejny radek
// (qty 2), jina konfigurace = dalsi radek, neaktivni karta = product_unavailable, a ze kosik skutecna data vykresli (na zakazku, kod, souhrn, doprava).
const { chromium } = require("/opt/konfigurator/node_modules/playwright");
const BASE = process.env.BASE, PID = process.env.PID, PID_N = process.env.PID_NEAKT, OUT = process.env.OUT;
let bad = 0, total = 0; const ok = (c, t) => { total++; if (!c) bad++; console.log(`[${c ? "OK   " : "CHYBA"}] ${t}`); };
const W = ".pdc-slot[data-slot=w] .pdc-num";
(async () => {
  const browser = await chromium.launch({ args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
  const ctx = await browser.newContext({ viewport: { width: 1300, height: 900 } });
  const pg = await ctx.newPage(); const errs = []; pg.on("pageerror", e => errs.push(e.message));
  // po startu se vzpery zapnou SAMY (auto_on, od 2026-10-05 server posila sam a vzpery se vejdou) = druhy vypocet a cena se na okamzik zmeni; cist cenu az po ustaleni
  const settled = async (ctx) => { let last = null, same = 0; for (let i = 0; i < 50 && same < 4; i++) { const t = await ctx.evaluate(() => ((document.querySelector(".emb-price .big") || {}).textContent || "") + "|" + (document.querySelector(".emb-order-btn") || {}).disabled); if (t === last) same++; else { same = 0; last = t; } await new Promise(r => setTimeout(r, 400)); } };
  const ready = async (p) => { await p.locator(".mw-win-stage").waitFor({ timeout: 60000 }); await p.locator(W).waitFor({ timeout: 60000 }); await p.locator(".emb-order-btn:not([disabled])").waitFor({ timeout: 60000 }); await settled(p); };
  const cart = (p) => p.evaluate(() => fetch("/api/cart").then(r => r.json()));
  const cfgRows = (c) => (c.items || []).filter(i => i.made_to_order);
  const digits = (s) => Number(String(s).replace(/[^\d]/g, ""));

  // 1) aktivni karta: Objednat -> radek v kosiku
  await pg.goto(`${BASE}/embed/stul.html?p=${PID}`); await ready(pg);
  const shown = await pg.evaluate(() => ({ net: document.querySelector(".emb-price .big").textContent, kod: (document.querySelector(".emb-price .small:last-child") || {}).textContent || "" }));
  const netShown = digits(shown.net), kodShown = (shown.kod.match(/STL-[0-9A-F]+/) || [""])[0];
  ok((await cart(pg)).items.length === 0, "R0 košík testovacího zákazníka je na začátku prázdný");
  await pg.locator(".emb-order-btn").click();
  await pg.locator(".emb-order-go:not([hidden]), .emb-order-msg.err").first().waitFor({ timeout: 60000 });
  const msg1 = await pg.locator(".emb-order-msg").innerText();
  ok(/Stůl je v košíku/.test(msg1) && await pg.locator(".emb-order-go").isVisible(), "R1 po kliknutí na Objednat se stůl přidá do košíku (skutečný cart.py): „" + msg1 + "“");
  let c1 = await cart(pg), r1 = cfgRows(c1)[0] || {};
  ok(c1.items.length === 1 && r1.made_to_order === true && r1.qty === 1 && r1.stock_qty === null, "R2 v košíku je 1 řádek „na zakázku“ (qty 1, bez skladu)");
  ok(r1.configuration && r1.configuration.valid === true && !r1.configuration.changed && r1.configuration.kod === kodShown && /^STL-/.test(kodShown), "R3 kód konfigurace v košíku = kód v generátoru (" + kodShown + ")");
  ok(Math.round(r1.unit_price_czk) === netShown && netShown > 1000, "R4 cena v košíku (bez DPH) = cena v generátoru: " + r1.unit_price_czk + " vs " + netShown);
  ok(Array.isArray(r1.configuration.summary) && r1.configuration.summary.length > 10 && r1.configuration.summary.every(x => x.label && x.value != null), "R5 řádek nese souhrn voleb (" + (r1.configuration.summary || []).length + " položek)");
  // totéž znovu: stejný výběr = stejný řádek, množství 2
  await pg.locator(".emb-order-btn").click(); await pg.waitForFunction(() => /v košíku/.test(document.querySelector(".emb-order-msg").textContent), null, { timeout: 30000 }); await pg.waitForTimeout(600);
  const c2 = await cart(pg);
  ok(cfgRows(c2).length === 1 && cfgRows(c2)[0].qty === 2, "R6 stejná konfigurace podruhé = stejný řádek, množství 2");
  // jiná konfigurace = další řádek
  await pg.locator(W).fill("1400"); await pg.locator(W).blur(); await pg.waitForTimeout(1500); await pg.locator(".emb-order-btn:not([disabled])").waitFor({ timeout: 60000 });
  await pg.locator(".emb-order-btn").click(); await pg.waitForFunction(() => /v košíku/.test(document.querySelector(".emb-order-msg").textContent), null, { timeout: 30000 }); await pg.waitForTimeout(600);
  const c3 = await cart(pg);
  ok(cfgRows(c3).length === 2 && new Set(cfgRows(c3).map(r => r.configuration.kod)).size === 2, "R7 jiná šířka = druhý řádek s jiným kódem (" + cfgRows(c3).map(r => r.configuration.kod + "×" + r.qty).join(", ") + ")");

  // 2) neaktivni karta (stav pred zapnutim): skutecny backend vrati product_unavailable
  const pn = await ctx.newPage(); await pn.goto(`${BASE}/embed/stul.html?p=${PID_N}`); await ready(pn);
  await pn.locator(".emb-order-btn").click(); await pn.locator(".emb-order-msg.err").waitFor({ timeout: 60000 });
  ok(/zatím nelze objednat online/.test(await pn.locator(".emb-order-msg").innerText()) && !cfgRows(await cart(pn)).some(r => r.product_id === Number(PID_N)), "R8 neaktivní karta: skutečný server odmítne (product_unavailable), do košíku nic nepřibude"); await pn.close();

  // 3) kosik na product.html se skutecnymi daty
  const cp = await ctx.newPage(); const perrs = []; cp.on("pageerror", e => perrs.push(e.message));
  await cp.goto(`${BASE}/product.html?openCart=1`); await cp.waitForSelector(".cart-items-tbl", { timeout: 30000 });
  const rows = await cp.$$eval(".cart-items-tbl tbody tr", trs => trs.map(t => t.innerText.replace(/\s+/g, " ")));
  ok(rows.length === 2 && rows.every(t => /na zakázku/.test(t) && /Kód konfigurace: STL-/.test(t) && !/null|undefined|NaN/.test(t)), "R9 košík ukazuje oba řádky konfigurace „na zakázku“ s kódem, bez null/undefined");
  ok(/Zvolené parametry \(\d+\)/.test(rows[0]), "R10 souhrn voleb je v košíku: " + (rows[0].match(/Zvolené parametry \(\d+\)/) || [""])[0]);
  ok(!(await cp.$eval("#cartStep1Next", e => e.disabled)), "R11 platná konfigurace: Pokračovat je aktivní");
  if (OUT) await cp.screenshot({ path: OUT + "/kosik_realny.png" });
  await cp.click("#cartStep1Next"); await cp.waitForSelector("#cartShipping");
  const toptrans = await cp.$$eval("#cartShipping option", o => o.filter(x => /Toptrans/.test(x.textContent)).map(x => x.value)[0]);
  await cp.selectOption("#cartShipping", toptrans); await cp.waitForTimeout(600);
  const hint = await cp.$eval("#cartShipPriceHint", e => e.textContent), wc = cfgRows(c3)[0].configuration.weight_complete;
  ok(wc === false ? /stanovíme po objednávce podle toho, zda zvolíte montáž/.test(hint) : /zadejte PSČ/.test(hint), "R12 doprava Toptrans u stolu (weight_complete=" + wc + ", server má větev ke schválení): " + hint);
  ok(!errs.length && !perrs.filter(e => !/stock_qty/.test(e)).length, "R13 bez JS chyb v generátoru a v košíku" + ((errs[0] || perrs[0]) ? " | " + (errs[0] || perrs[0]) : ""));
  await browser.close(); console.log(`\n==> ${total - bad}/${total} kontrol OK`); process.exit(bad ? 1 : 0);
})();
