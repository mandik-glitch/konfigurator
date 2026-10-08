// Kosik na product.html: radek KONFIGURACE STOLU z generatoru (kontrakt bot5: made_to_order, configuration {valid, changed, kod, summary[], weight_complete}) - odznak "na zakazku",
// kod konfigurace a souhrn voleb, upozorneni na neplatnou/zmenenou konfiguraci (blokuje Pokracovat), doprava Toptrans pri neuplne hmotnosti (nabidne osobni odber, nevola preview).
// SKUTECNY webapp/product.html proti falesnemu API (stejna technika jako admin testy): /api/cart, /api/shipping-methods, /api/payment-methods, /api/auth/me; zadny zapis nikam.
const fs = require("fs"), http = require("http"), path = require("path");
const { chromium } = require("/opt/konfigurator/node_modules/playwright");
const LIVE = process.env.WEB_OVERRIDE || "/opt/konfigurator/webapp";          // WEB_OVERRIDE: kandidatni kopie statiky (git worktree), jinak zive webapp
const MIME = { ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css", ".json": "application/json", ".svg": "image/svg+xml", ".png": "image/png" };
const REG = { id: 1, product_id: 11, name: "Úhelník 30x30", sku: "A.1", qty: 2, active: 1, is_archived: 0, stock_qty: 5, unit_price_czk: 100, price_czk_placeholder: 100, price_basis: "base", line_total_czk: 200, image_url: null };
const SUMMARY = ["Šířka desky|1200 mm", "Hloubka desky|800 mm", "Výška pracovní desky|840 mm", "Přesah desky|30 mm", "Zadní stojky|ano", "Kolečka|ano"].map(x => ({ label: x.split("|")[0], value: x.split("|")[1] }));
const CFG = (over, cfg) => Object.assign({ id: 2, product_id: null, name: "Konfigurovatelný balicí a pracovní stůl – 1200×800 STL-F1DB6B", sku: "STL", qty: 1, active: 1, is_archived: 0, stock_qty: null, made_to_order: true, unit_price_czk: 26947, price_czk_placeholder: 26947, line_total_czk: 26947, image_url: null,
  configuration: Object.assign({ valid: true, changed: false, kod: "STL-F1DB6B", hash: "abc", summary: SUMMARY, weight_kg: null, weight_complete: false, errors: [] }, cfg || {}) }, over || {});
let CART = [], previews = 0, HOST_API = false;                       // HOST_API: server uz ma objednavku stolu hostem / dopravu ke schvaleni (bot5, nasazeni 2026-10-04)
const METHODS = [{ id: 1, name: "Toptrans", price_czk: 0, pricing_mode: "zip_weight" }, { id: 2, name: "Osobní odběr", price_czk: 0 }];
const srv = http.createServer((req, res) => {
  const u = new URL(req.url, "http://x"), p = u.pathname, j = (c, o) => { res.writeHead(c, { "Content-Type": "application/json" }); res.end(JSON.stringify(o)); };
  if (p === "/api/auth/me") return j(200, { user: { id: 7, name: "Zákazník", email: "z@example.test", role: "user", permissions: {} } });
  if (p === "/api/theme-colors") return j(200, { dark: {}, light: {} });
  if (p === "/api/cart") return j(200, { items: CART, subtotal_czk: CART.reduce((a, i) => a + i.line_total_czk, 0), item_count: CART.length, total_qty: CART.reduce((a, i) => a + i.qty, 0) });
  if (p === "/api/shipping-methods") return j(200, { methods: METHODS });
  if (p === "/api/payment-methods") return j(200, { methods: [{ id: 1, name: "Převodem", price_czk: 0 }] });
  if (p === "/api/customer/profile") return j(200, { profile: null });
  if (p === "/api/shop/stul/quote") { res.writeHead(HOST_API ? 400 : 404, { "Content-Type": "application/json" }); return res.end(JSON.stringify({ error: HOST_API ? "items_invalid" : "nf" })); }
  if (p === "/api/shipping-price-preview") { previews++; return j(409, { error: "x", code: "weight_incomplete" }); }
  if (p.startsWith("/api/")) return j(200, {});
  const f = path.join(LIVE, decodeURIComponent(p === "/" ? "/index.html" : p)); if (f.includes("..") || !fs.existsSync(f) || fs.statSync(f).isDirectory()) { res.writeHead(404); return res.end("nf"); }
  res.writeHead(200, { "Content-Type": MIME[path.extname(f)] || "application/octet-stream" }); fs.createReadStream(f).pipe(res);
});
let bad = 0, total = 0; const ok = (c, t) => { total++; if (!c) bad++; console.log(`[${c ? "OK   " : "CHYBA"}] ${t}`); };
(async () => {
  await new Promise(r => srv.listen(0, "127.0.0.1", r)); const base = "http://127.0.0.1:" + srv.address().port;
  const b = await chromium.launch();
  async function open(cart) {
    CART = cart; previews = 0; const ctx = await b.newContext({ viewport: { width: 1300, height: 900 } }); const pg = await ctx.newPage(); pg.errs = []; pg.on("pageerror", e => pg.errs.push(e.message));
    await pg.goto(base + "/product.html?openCart=1"); await pg.waitForSelector(".cart-items-tbl", { timeout: 15000 }); return pg;
  }
  const rowText = (pg, n) => pg.$$eval(".cart-items-tbl tbody tr", (trs, k) => trs[k].innerText.replace(/\s+/g, " "), n);
  // 1) obycejny radek + platna konfigurace s neuplnou hmotnosti
  let pg = await open([REG, CFG()]);
  const r1 = await rowText(pg, 0), r2 = await rowText(pg, 1);
  ok(/na skladu \(5 ks\)/.test(r1) && !/Kód konfigurace/.test(r1), "K1 běžný řádek zůstává beze změny (sklad 5 ks, žádný kód konfigurace)");
  ok(/na zakázku/.test(r2) && !/skladem|null/.test(r2) && /Kód konfigurace: STL-F1DB6B/.test(r2), "K2 řádek konfigurace: „na zakázku“ (ne sklad), kód konfigurace: " + r2.slice(0, 120));
  ok(await pg.$eval("details.ci-cfg-sum summary", e => e.textContent) === "Zvolené parametry (6)", "K3 souhrn voleb je sbalený: „Zvolené parametry (6)“");
  await pg.click("details.ci-cfg-sum summary");
  ok(/Šířka desky\s+1200 mm/.test(await pg.$eval("details.ci-cfg-sum", e => e.innerText.replace(/\n/g, " "))), "K4 po rozbalení jsou vidět zvolené parametry (Šířka desky 1200 mm)");
  ok(!(await pg.$eval("#cartStep1Next", e => e.disabled)), "K5 platná konfigurace: tlačítko Pokračovat je aktivní");
  await pg.click("#cartStep1Next"); await pg.waitForSelector("#cartShipping");
  await pg.selectOption("#cartShipping", "1"); await pg.waitForTimeout(500);
  const hint = await pg.$eval("#cartShipPriceHint", e => e.textContent);
  ok(/zatím nelze spočítat/.test(hint) && /osobní odběr/.test(hint), "K6 Toptrans u stolu s neúplnou hmotností: vysvětlení + nabídka osobního odběru: " + hint);
  await pg.fill("#cartStep2Zip", "11000"); await pg.waitForTimeout(900);
  ok(previews === 0, "K7 pro tuto konfiguraci se doprava Toptrans u serveru vůbec nepočítá (žádný dotaz na náhled, " + previews + ")");
  await pg.selectOption("#cartShipping", "2"); await pg.waitForTimeout(400);
  ok(/Osobní odběr.*zdarma/.test(await pg.$eval("#cartShipPriceHint", e => e.textContent)), "K8 osobní odběr: doprava zdarma, bez výhrad");
  ok(!pg.errs.length, "K9 bez JS chyb" + (pg.errs[0] ? " | " + pg.errs[0] : "")); await pg.context().close();

  // 2) neplatna / zmenena konfigurace blokuje pokracovani
  pg = await open([CFG({}, { valid: false }), CFG({ id: 3 }, { changed: true })]);
  const t1 = await rowText(pg, 0);
  ok(/neplatná konfigurace/.test(t1) && /nakonfigurujte stůl znovu/.test(t1), "K10 neplatná konfigurace: odznak „neplatná konfigurace“ + výzva nakonfigurovat znovu");
  ok(/neplatná konfigurace/.test(await rowText(pg, 1)), "K11 změněná pravidla (changed) se chová stejně");
  ok(await pg.$eval("#cartStep1Next", e => e.disabled) && /není platná/.test(await pg.$eval("#cartStep1Next", e => e.title)), "K12 Pokračovat je zablokované, s vysvětlením v popisku");
  await pg.context().close();

  // 2b) server UZ ma novou vetev (doprava ke schvaleni): veta o doprave po objednavce, hint Toptrans bez "zvolte osobni odber", montaz v radku bez procenta
  HOST_API = true; pg = await open([CFG({ montaz_zvolena: true, montaz_czk: 3234 })]);
  ok(/Cenu dopravy stanovíme po objednávce podle toho, zda zvolíte montáž; uvidíte ji ke schválení před zálohovou fakturou/.test(await pg.$eval(".cart-shipnote", e => e.textContent)), "K15 pod položkami je věta o ceně dopravy po objednávce (jen když server má novou větev)");
  const r15 = await rowText(pg, 0);
  ok(/Včetně montáže: 3\s?234,00\s?Kč bez DPH/.test(r15) && !/%/.test(r15), "K16 řádek stolu ukazuje „Včetně montáže: 3 234,00 Kč bez DPH“ a žádné procento: " + (r15.match(/Včetně montáže[^A-Z]*/) || [""])[0]);
  await pg.click("#cartStep1Next"); await pg.waitForSelector("#cartShipping"); await pg.selectOption("#cartShipping", "1"); await pg.waitForTimeout(500);
  const h15 = await pg.$eval("#cartShipPriceHint", e => e.textContent);
  ok(/stanovíme po objednávce/.test(h15) && !/osobní odběr/.test(h15), "K17 Toptrans u stolu: hint = věta o dopravě po objednávce (ne „zvolte osobní odběr“): " + h15);
  await pg.fill("#cartStep2Zip", "11000"); await pg.waitForTimeout(700);
  ok(previews === 0, "K18 doprava se u serveru dál nepočítá (žádný náhled, " + previews + ")"); await pg.context().close(); HOST_API = false;

  // 3) regrese: kosik jen s obycejnym zbozim - Toptrans pocita dopravu jako dosud
  pg = await open([REG]);
  await pg.click("#cartStep1Next"); await pg.waitForSelector("#cartShipping"); await pg.selectOption("#cartShipping", "1");
  ok(/zadejte PSČ/.test(await pg.$eval("#cartShipPriceHint", e => e.textContent)), "K13 běžný košík: Toptrans vyzve k zadání PSČ jako dosud");
  await pg.fill("#cartStep2Zip", "11000"); await pg.waitForTimeout(1200);
  ok(previews >= 1, "K14 běžný košík: po zadání PSČ se cena dopravy dotazuje na serveru (" + previews + "×)");
  await pg.context().close();
  await b.close(); srv.close(); console.log(`\n==> ${total - bad}/${total} kontrol OK`); process.exit(bad ? 1 : 0);
})();
