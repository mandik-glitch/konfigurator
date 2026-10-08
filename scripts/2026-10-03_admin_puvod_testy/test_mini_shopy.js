// Zalozka "Mini-shopy" v admin.html: skutecne soubory, falesne API v tvaru od bot5 (api/miniweb_admin.py).
const fs = require("fs"), http = require("http"), path = require("path");
const { chromium } = require("/opt/konfigurator/node_modules/playwright");
const LIVE = "/opt/konfigurator/webapp";
const MIME = { ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css", ".json": "application/json" };
let perms = { miniweb: true }, puts = [];
const SHOP = { storefront_id: 16, slug: "packstations-sk", name: "Packstations SK", domain: "baliace-stoly.top", lang: "sk", status: "draft", family: "packstations", price_mode: "hidden", currency: "EUR", locale: "sk-SK", accent: "#2dd4bf", countries: ["SK"], margin_pct: null, eur_rate: null, rate_source: "fio", live_rate: 25.1, inquiry_enabled: true, orders_enabled: false, contact: { phone: "", hours: "", use_company: true }, inquiries: 3, orders: 2, orders_to_review: 1 };
const srv = http.createServer((req, res) => {
  const u = new URL(req.url, "http://x"), p = u.pathname, j = (c, o) => { res.writeHead(c, { "Content-Type": "application/json" }); res.end(JSON.stringify(o)); };
  if (p === "/api/auth/me") return j(200, { user: { id: 1, name: "A", email: "a@b.c", role: "manager", permissions: perms, theme_admin: "dark" } });
  if (p === "/api/admin/miniweb/shops" && req.method === "GET") return j(200, { shops: [SHOP] });
  if (p === "/api/admin/miniweb/shops/16" && req.method === "PUT") { let b = ""; req.on("data", c => b += c); req.on("end", () => { const body = JSON.parse(b); puts.push(body); if (body.margin_pct === 999) return j(400, { error: "margin_pct_invalid", field: "margin_pct" }); j(200, { shop: SHOP }); }); return; }
  if (p === "/api/admin/miniweb/inquiries") return j(200, { total: 1, inquiries: [{ id: 5, created_at: "2026-10-03T10:00:00", country: "SK", lang: "sk", name: "Jan", company: "Acme", items: [{}, {}], unread: true }] });
  if (p === "/api/admin/miniweb/orders") return j(200, { total: 1, orders: [{ id: 7, order_number: "2026-0007", status: "nova", created_at: "2026-10-03T11:00:00", customer_name: "Jan", company: "Acme", company_id: "12345678", total_czk: 1000, shipping_review: 1, vat_mode: "standard", is_urgent: 1 }] });
  if (p.startsWith("/api/")) return j(200, {});
  const f = path.join(LIVE, decodeURIComponent(p === "/" ? "/index.html" : p)); if (f.includes("..") || !fs.existsSync(f) || fs.statSync(f).isDirectory()) { res.writeHead(404); return res.end("nf"); }
  res.writeHead(200, { "Content-Type": MIME[path.extname(f)] || "application/octet-stream" }); fs.createReadStream(f).pipe(res);
});
let bad = 0, total = 0; const ok = (c, t) => { total++; if (!c) bad++; console.log(`[${c ? "OK   " : "CHYBA"}] ${t}`); };
(async () => {
  await new Promise(r => srv.listen(0, "127.0.0.1", r)); const base = "http://127.0.0.1:" + srv.address().port;
  const b = await chromium.launch();
  let page = await b.newPage({ viewport: { width: 1500, height: 900 } }); const errs = []; page.on("pageerror", e => errs.push(e.message));
  await page.goto(base + "/admin.html"); await page.waitForTimeout(1500);
  ok(await page.evaluate(() => document.querySelector('.tab-btn[data-tab="miniweb"]').style.display !== "none"), "M1 s právem miniweb je záložka ‚Mini-shopy‘ vidět");
  await page.evaluate(() => document.querySelector('.tab-btn[data-tab="miniweb"]').click()); await page.waitForSelector("#mwShopsList table", { timeout: 8000 });
  const t = await page.locator("#mwShopsList").innerText();
  ok(/baliace-stoly\.top/.test(t) && /koncept/.test(t) && /skryté \(EUR\)/.test(t) && /25\.1 \(Fio\)|25,1 \(Fio\)/.test(t) && /1 ke schválení/.test(t), "M2 seznam shopů: doména, stav, ceny, kurz Fio, objednávky ke schválení");
  await page.evaluate(() => document.querySelector(".mw-edit").click());
  await page.evaluate(() => { document.getElementById("mwfPrice").value = "shown"; document.getElementById("mwfMargin").value = "12"; document.getElementById("mwfRate").value = ""; document.getElementById("mwfOrd").checked = true; });
  await page.evaluate(() => document.getElementById("mwfSave").click()); await page.waitForTimeout(500);
  ok(puts.length === 1 && puts[0].price_mode === "shown" && puts[0].margin_pct === 12 && puts[0].eur_rate === null && puts[0].orders_enabled === true && puts[0].countries === "SK" && !("status" in puts[0]), "M3 uložení: PUT jen z povolených klíčů, kurz prázdný = null (živý Fio), stav se neposílá");
  await page.evaluate(() => { document.getElementById("mwfMargin").value = "999"; }); await page.evaluate(() => document.getElementById("mwfSave").click()); await page.waitForTimeout(400);
  ok(/Marže musí být 0 až 500/.test(await page.locator("#mwfMsg").innerText()), "M4 chyba serveru margin_pct_invalid → česká hláška");
  await page.evaluate(() => document.querySelector('.mw-sub[data-sub="inquiries"]').click()); await page.waitForSelector("#mwInqList table", { timeout: 5000 });
  ok(/Acme/.test(await page.locator("#mwInqList").innerText()), "M5 poptávky shopu");
  await page.evaluate(() => document.querySelector('.mw-sub[data-sub="orders"]').click()); await page.waitForSelector("#mwOrdList table", { timeout: 5000 });
  const ot = await page.locator("#mwOrdList").innerText();
  ok(/2026-0007/.test(ot) && /ke schválení/.test(ot) && /ruční kontrola/.test(ot), "M6 objednávky shopu: číslo, doprava ke schválení, ruční kontrola VIES");
  await page.evaluate(() => document.querySelector('.mw-sub[data-sub="texts"]').click()); await page.waitForTimeout(300);
  ok(await page.evaluate(() => document.getElementById("mwTextsFrame").getAttribute("src")) === "/miniweb-schvaleni.html" && await page.evaluate(() => !document.getElementById("mwSub-texts").hidden), "M6b podzáložka Texty a schvalování vloží stránku schvalování");
  ok(!errs.length, "M7 bez JS chyb" + (errs.length ? " | " + errs[0] : ""));
  await page.close(); perms = { objednavky: true };
  page = await b.newPage({ viewport: { width: 1500, height: 900 } }); await page.goto(base + "/admin.html"); await page.waitForTimeout(1500);
  ok(await page.evaluate(() => document.querySelector('.tab-btn[data-tab="miniweb"]').style.display === "none"), "M8 bez práva miniweb je záložka skrytá");
  await b.close(); srv.close(); console.log(`\n==> ${total - bad}/${total} kontrol OK`); process.exit(bad ? 1 : 0);
})();
