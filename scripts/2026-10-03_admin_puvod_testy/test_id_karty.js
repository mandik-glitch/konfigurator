// Cislo karty (shop_products.id) v adminu: sloupec ID v seznamu produktu + hlavicka skladove karty, klik kopiruje (Robert 2026-10-04 pres bot9).
const fs = require("fs"), http = require("http"), path = require("path");
const { chromium } = require("/opt/konfigurator/node_modules/playwright");
const LIVE = "/opt/konfigurator/webapp";
const MIME = { ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css", ".json": "application/json" };
const P = (id, name) => ({ id, sku: "2.1.21." + id, name, category_id: 263, unit: "ks", price_czk_placeholder: 12, stock_qty: 0, min_stock: null, max_stock: null, active: 1, is_archived: 0 });
const PRODUCTS = [P(4935, "Šroub se šestihrannou hlavou M4x8"), P(4936, "Šroub se šestihrannou hlavou M4x10")];
const srv = http.createServer((req, res) => {
  const u = new URL(req.url, "http://x"), p = u.pathname, j = (c, o) => { res.writeHead(c, { "Content-Type": "application/json" }); res.end(JSON.stringify(o)); };
  if (p === "/api/auth/me") return j(200, { user: { id: 1, name: "A", email: "a@b.c", role: "admin", permissions: {}, theme_admin: "dark" } });
  if (p === "/api/shop/products") return j(200, { products: PRODUCTS, total: 2, page: 1, page_size: 50, pages: 1 });
  if (/^\/api\/shop\/products\/\d+$/.test(p)) return j(200, { product: PRODUCTS.find(x => "/api/shop/products/" + x.id === p) || PRODUCTS[0] });
  if (p.startsWith("/api/")) return j(200, {});
  const f = path.join(LIVE, decodeURIComponent(p === "/" ? "/index.html" : p)); if (f.includes("..") || !fs.existsSync(f) || fs.statSync(f).isDirectory()) { res.writeHead(404); return res.end("nf"); }
  res.writeHead(200, { "Content-Type": MIME[path.extname(f)] || "application/octet-stream" }); fs.createReadStream(f).pipe(res);
});
let bad = 0, total = 0; const ok = (c, t) => { total++; if (!c) bad++; console.log(`[${c ? "OK   " : "CHYBA"}] ${t}`); };
(async () => {
  await new Promise(r => srv.listen(0, "127.0.0.1", r)); const base = "http://127.0.0.1:" + srv.address().port;
  const b = await chromium.launch(); const ctx = await b.newContext({ viewport: { width: 1500, height: 900 } });
  await ctx.grantPermissions(["clipboard-read", "clipboard-write"], { origin: base });
  const page = await ctx.newPage(); const errs = [];
  page.on("pageerror", e => errs.push(e.message));
  await page.goto(base + "/admin.html"); await page.waitForTimeout(1500);
  await page.evaluate(() => document.querySelector('.tab-btn[data-tab="shop"]').click()); await page.waitForSelector("#shopProdTbody .card-id-chip", { timeout: 8000 });
  const heads = await page.$$eval("#shopProdTbl thead th", t => t.map(x => x.textContent.trim()));
  ok(heads[1] === "ID" && heads[2] === "SKU", "I1 seznam produktů má sloupec ID hned za výběrem a před SKU: " + heads.slice(0, 4).join(" | "));
  const chips = await page.$$eval("#shopProdTbody .card-id-chip", c => c.map(x => x.textContent));
  ok(JSON.stringify(chips) === JSON.stringify(["#4935", "#4936"]), "I2 u každého řádku je číslo karty: " + chips.join(", "));
  await page.locator("#shopProdTbody .card-id-chip").first().click(); await page.waitForTimeout(300);
  ok(await page.evaluate(() => navigator.clipboard.readText()) === "4935", "I3 klik na číslo ho zkopíruje do schránky (jen číslo, bez #)");
  await page.evaluate(() => [...document.querySelectorAll("#shopProdTbody tr")][0].querySelectorAll("button")[1].click()); // tlacitko "Karta"
  await page.waitForFunction(() => document.querySelector("#stockCardIdHost .card-id-chip"), null, { timeout: 8000 }).catch(() => {});
  const hid = await page.$eval("#stockCardIdHost", e => e.textContent).catch(() => "");
  ok(hid === "#4935", "I4 hlavička otevřené skladové karty ukazuje její číslo: " + hid);
  const realErrs = errs.filter(e => !/stock_qty/.test(e));   // falešný server nevrací data skladové karty (stock_qty) - chyba z atrapy, ne ze stránky
  ok(!realErrs.length, "I5 bez JS chyb ze změny" + (realErrs[0] ? " | " + realErrs[0] : ""));
  await b.close(); srv.close(); console.log(`\n==> ${total - bad}/${total} kontrol OK`); process.exit(bad ? 1 : 0);
})();
