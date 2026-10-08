// Sloupec "Puvod" + filtr v prehledu objednavek (webapp/admin.html + admin/js/objednavky-doklady.js): skutecne soubory, falesne API.
const fs = require("fs"), http = require("http"), path = require("path");
const { chromium } = require("/opt/konfigurator/node_modules/playwright");
const LIVE = "/opt/konfigurator/webapp";
const MIME = { ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css", ".json": "application/json" };
let lastOrdersUrl = ""; const shipPosts = [];
const srv = http.createServer((req, res) => {
  const u = new URL(req.url, "http://x"), p = u.pathname;
  if (p.startsWith("/api/")) {
    if (p === "/api/auth/me") { res.writeHead(200, { "Content-Type": "application/json" }); return res.end(JSON.stringify({ user: { id: 1, name: "A", email: "a@example.test", role: "admin", permissions: new Proxy({}, { get: () => true }), theme_admin: "dark" } })); }
    if (p === "/api/admin/orders/2/shipping") { let b = ""; req.on("data", c => b += c); req.on("end", () => { shipPosts.push(JSON.parse(b)); res.writeHead(200, { "Content-Type": "application/json" }); res.end(JSON.stringify({ status: "ok", approved: JSON.parse(b).approve, shipping_price_czk: JSON.parse(b).shipping_price_czk, total_czk: 5000, proforma: JSON.parse(b).approve ? { id: 9, document_number: "ZF-2026-0001", amount_due_czk: 5000 } : null })); }); return; }
    if (p === "/api/admin/orders/2") { res.writeHead(200, { "Content-Type": "application/json" }); return res.end(JSON.stringify({ order: { id: 2, order_number: "2026-0002", customer_name: "B", status: "nova", status_label: "Nová", total_czk: 200, items: [], created_at: "2026-10-03T11:00:00", order_host: "baliace-stoly.top", order_lang: "sk", shipping_review: 1, vat_mode: "standard", vat_check: "vies_unavailable", admin_note: "[EUR-SNAPSHOT {\"goods_eur\": 1290, \"rate\": 25.1, \"margin_pct\": 10, \"shipping_eur\": null}]" } })); }
    if (p === "/api/admin/orders") { lastOrdersUrl = req.url; res.writeHead(200, { "Content-Type": "application/json" });
      return res.end(JSON.stringify({ orders: [
        { id: 1, order_number: "2026-0001", customer_name: "A", total_czk: 100, status: "nova", status_label: "Nová", created_at: "2026-10-03T10:00:00", invoices: [] },
        { id: 2, order_number: "2026-0002", customer_name: "B", total_czk: 200, status: "nova", status_label: "Nová", created_at: "2026-10-03T11:00:00", invoices: [], order_host: "www.baliace-stoly.top", order_lang: "sk" },
        { id: 3, order_number: "2026-0003", customer_name: "C", total_czk: 300, status: "nova", status_label: "Nová", created_at: "2026-10-03T12:00:00", invoices: [], origin_label: "packing-tables.top · en" } ],
        counts: { all: 3 }, total: 3, page: 1, page_size: 25, origins: [{ key: "eshop", label: "e-shop" }, { key: "baliace-stoly.top", label: "baliace-stoly.top · sk" }] })); }
    res.writeHead(200, { "Content-Type": "application/json" }); return res.end("{}");
  }
  const f = path.join(LIVE, decodeURIComponent(p === "/" ? "/index.html" : p));
  if (f.includes("..") || !fs.existsSync(f) || fs.statSync(f).isDirectory()) { res.writeHead(404); return res.end("nf"); }
  res.writeHead(200, { "Content-Type": MIME[path.extname(f)] || "application/octet-stream" }); fs.createReadStream(f).pipe(res);
});
let bad = 0, total = 0;
const ok = (c, t) => { total++; if (!c) bad++; console.log(`[${c ? "OK   " : "CHYBA"}] ${t}`); };
(async () => {
  await new Promise(r => srv.listen(0, "127.0.0.1", r));
  const base = "http://127.0.0.1:" + srv.address().port;
  const b = await chromium.launch(); const page = await b.newPage({ viewport: { width: 1400, height: 900 } }); const errs = [];
  page.on("pageerror", e => errs.push(e.message));
  await page.goto(base + "/admin.html"); await page.waitForTimeout(1500);
  await page.evaluate(() => loadOrders()); await page.waitForSelector("#ordersTbody tr.order-row", { state: "attached", timeout: 10000 });
  const heads = await page.locator("#ordersTblHeadRow th").allInnerTexts();
  ok(heads.includes("Původ") && heads.indexOf("Původ") === heads.indexOf("Číslo") + 1, "P1 hlavička obsahuje sloupec ‚Původ‘ hned za ‚Číslo‘");
  const cells = await page.locator("#ordersTbody tr.order-row td:nth-child(3)").allInnerTexts();
  ok(cells.join("|") === "e-shop|baliace-stoly.top · sk|packing-tables.top · en", "P2 původ: e-shop / host + jazyk / hotový popisek ze serveru: " + cells.join("|"));
  ok((await page.locator("#orderFilterOrigin option").allInnerTexts()).join("|") === "Původ: vše|e-shop|baliace-stoly.top · sk", "P3 filtr původu se naplní z odpovědi API");
  await page.evaluate(() => { document.getElementById("orderFilterOrigin").value = "baliace-stoly.top"; document.getElementById("orderSearchApply").click(); }); await page.waitForTimeout(500);
  ok(/[?&]origin=baliace-stoly\.top/.test(lastOrdersUrl), "P4 filtr posílá ?origin=… na API");
  await page.evaluate(() => document.getElementById("orderSearchReset").click()); await page.waitForTimeout(500);
  ok(!/origin=/.test(lastOrdersUrl), "P5 Reset vše filtr původu zruší");
  await page.evaluate(() => renderShippingReview({ id: 2, shipping_review: 1, vat_mode: "standard", vat_check: "vies_unavailable", order_host: "baliace-stoly.top", order_lang: "sk", admin_note: '[EUR-SNAPSHOT {"goods_eur": 1290, "rate": 25.1, "margin_pct": 10, "shipping_eur": null}]' }));
  const sr = await page.locator("#orderShippingReview").innerText();
  ok(/Doprava ke schválení/.test(sr) && /Zboží 1\s?290 €/.test(sr) && /VIES nedostupné/.test(sr) && await page.locator("#orderShipVatOk").count() === 1, "P6a panel Doprava ke schválení: snímek EUR, kontrola VAT a zaškrtávátko ruční kontroly při nedostupném VIES");
  await page.evaluate(() => { document.getElementById("orderShipPrice").value = "450"; document.getElementById("orderShipVatOk").checked = true; document.getElementById("orderShipSave").click(); }); await page.waitForTimeout(500);
  ok(shipPosts.length === 1 && shipPosts[0].shipping_price_czk === 450 && shipPosts[0].approve === false && shipPosts[0].vat_ok === true, "P6b Uložit: POST /shipping {shipping_price_czk 450, approve false, vat_ok true}");
  await page.evaluate(() => renderShippingReview({ id: 2, shipping_review: 0 }));
  ok(await page.locator("#orderShippingReview").isHidden(), "P6c objednávka bez shipping_review panel nemá");
  // objednavka HLAVNIHO e-shopu (host i prihlaseny; bot5 2026-10-04): jiny popis, bez EUR snimku a bez kontroly VAT cisla, stejna tlacitka a stejne API
  await page.evaluate(() => renderShippingReview({ id: 5, shipping_review: 1, vat_mode: "standard", vat_check: "none", order_host: "autovestavby.logiman.cz", order_lang: "cs", shipping_price_czk: 0,
    admin_note: "Objednávka HOSTA bez účtu z autovestavby.logiman.cz (hlavní e-shop). Zboží 26947 Kč, montáž 3234 Kč bez DPH, DPH CZ 21 %. [ORDER-FP abc]" }));
  const mr = await page.locator("#orderShippingReview").innerText();
  ok(/objednávka hlavního e-shopu: autovestavby\.logiman\.cz · cs/.test(mr) && /Montáž – kód/.test(mr) && !/Snímek EUR|VIES|kontrola VAT/.test(mr) && await page.locator("#orderShipVatOk").count() === 0 && await page.locator("#orderShipApprove").count() === 1,
     "P7a host z hlavního e-shopu: popis ‚objednávka hlavního e-shopu‘, řádek Montáž, bez EUR snímku a VAT kontroly, tlačítka Uložit/Schválit zůstávají");
  await page.evaluate(() => renderShippingReview({ id: 6, shipping_review: 1, order_host: null, shipping_price_czk: 0, vat_mode: "standard", vat_check: "none", admin_note: "" }));
  ok(/objednávka hlavního e-shopu: e-shop/.test(await page.locator("#orderShippingReview").innerText()), "P7b přihlášený zákazník hlavního e-shopu (order_host NULL): ‚objednávka hlavního e-shopu: e-shop‘");
  await page.evaluate(() => renderShippingReview({ id: 2, shipping_review: 1, vat_mode: "standard", vat_check: "vies_unavailable", order_host: "baliace-stoly.top", order_lang: "sk", admin_note: '[EUR-SNAPSHOT {"goods_eur": 1290, "rate": 25.1, "margin_pct": 12}]' }));
  ok(/z mini-shopu: baliace-stoly\.top · sk/.test(await page.locator("#orderShippingReview").innerText()) && await page.locator("#orderShipVatOk").count() === 1, "P7c mini-shop objednávka zůstává beze změny (popis, EUR snímek, VAT kontrola)");
  await page.evaluate(() => renderShippingReview({ id: 2, shipping_review: 0 }));
  ok(!errs.length, "P6 bez JS chyb" + (errs.length ? " | " + errs.slice(0, 2).join("||") : ""));
  await b.close(); srv.close();
  console.log(`\n==> ${total - bad}/${total} kontrol OK`); process.exit(bad ? 1 : 0);
})();
