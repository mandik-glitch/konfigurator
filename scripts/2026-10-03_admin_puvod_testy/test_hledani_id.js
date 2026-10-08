// Hledani podle ID karty v adminu produktu (Robert 2026-10-04 pres bot9: "nejde hledat podle ID karty"): pole "ID karty" (4934 / #4934), #4934 v poli pro nazev,
// presna karta bez ohledu na ostatni filtry (archivovana, neaktivni), hlasky u neexistujici/neplatne hodnoty, navrat k bezne tabulce. SKUTECNY admin.html + sklad-produkty.js
// proti falesnemu API (seznam filtruje q/sku/archived jako server; detail /api/shop/products/<id> vraci i neaktivni a archivovane jako pro staff).
const fs = require("fs"), http = require("http"), path = require("path");
const { chromium } = require("/opt/konfigurator/node_modules/playwright");
const LIVE = "/opt/konfigurator/webapp";
const MIME = { ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css", ".json": "application/json" };
const P = (id, name, extra) => Object.assign({ id, sku: "2.1.21." + id, name, category_id: 263, unit: "ks", price_czk_placeholder: 12, stock_qty: 0, min_stock: null, max_stock: null, active: 1, is_archived: 0 }, extra || {});
const PRODUCTS = [P(4934, "Konfigurovatelný balicí a pracovní stůl", { active: 0 }), P(4935, "Šroub se šestihrannou hlavou M4x8"), P(4936, "Šroub se šestihrannou hlavou M4x10"), P(4001, "Starý archivovaný profil", { is_archived: 1, active: 0 })];
const calls = [];
const srv = http.createServer((req, res) => {
  const u = new URL(req.url, "http://x"), p = u.pathname, j = (c, o) => { res.writeHead(c, { "Content-Type": "application/json" }); res.end(JSON.stringify(o)); };
  if (p === "/api/auth/me") return j(200, { user: { id: 1, name: "A", email: "a@b.c", role: "admin", permissions: {}, theme_admin: "dark" } });
  if (p === "/api/shop/products") {
    calls.push("LIST " + u.search); const q = (u.searchParams.get("q") || "").toLowerCase(), sku = (u.searchParams.get("sku") || "").toLowerCase(), arch = u.searchParams.get("archived") === "1";
    const rows = PRODUCTS.filter(x => (arch ? x.is_archived : !x.is_archived) && (!q || x.name.toLowerCase().includes(q) || x.sku.toLowerCase().includes(q)) && (!sku || x.sku.toLowerCase().includes(sku)));
    return j(200, { products: rows, total: rows.length, page: 1, page_size: 50, pages: 1 });
  }
  const m = /^\/api\/shop\/products\/(\d+)$/.exec(p);
  if (m) { calls.push("DETAIL " + m[1]); const x = PRODUCTS.find(y => y.id === Number(m[1])); return x ? j(200, { product: x }) : j(404, { error: "Produkt neexistuje." }); }
  if (p.startsWith("/api/")) return j(200, {});
  const f = path.join(LIVE, decodeURIComponent(p === "/" ? "/index.html" : p)); if (f.includes("..") || !fs.existsSync(f) || fs.statSync(f).isDirectory()) { res.writeHead(404); return res.end("nf"); }
  res.writeHead(200, { "Content-Type": MIME[path.extname(f)] || "application/octet-stream" }); fs.createReadStream(f).pipe(res);
});
let bad = 0, total = 0; const ok = (c, t) => { total++; if (!c) bad++; console.log(`[${c ? "OK   " : "CHYBA"}] ${t}`); };
(async () => {
  await new Promise(r => srv.listen(0, "127.0.0.1", r)); const base = "http://127.0.0.1:" + srv.address().port;
  const b = await chromium.launch(); const ctx = await b.newContext({ viewport: { width: 1500, height: 900 } });
  const page = await ctx.newPage(); const errs = []; page.on("pageerror", e => errs.push(e.message));
  await page.goto(base + "/admin.html"); await page.waitForTimeout(1500);
  await page.evaluate(() => document.querySelector('.tab-btn[data-tab="shop"]').click()); await page.waitForSelector("#shopProdTbody .card-id-chip", { timeout: 8000 });
  const chips = async () => (await page.$$eval("#shopProdTbody .card-id-chip", c => c.map(x => x.textContent))).join(",");
  const err = () => page.$eval("#shopProdErr", e => e.textContent);
  const set = async (sel, v) => { calls.length = 0; await page.fill(sel, v); await page.waitForTimeout(700); };

  ok(await page.$("#shopProdIdSearch") !== null && /ID karty/.test(await page.$eval("#shopProdIdSearch", e => e.placeholder)), "H1 vedle názvu a SKU je pole „Hledat podle ID karty…“");
  ok(await chips() === "#4934,#4935,#4936", "H2 výchozí seznam (aktivní i neaktivní, bez archivovaných): " + await chips());

  await set("#shopProdIdSearch", "4934");
  ok(await chips() === "#4934" && calls.includes("DETAIL 4934") && !calls.some(c => c.startsWith("LIST")), "H3 zadám 4934 → najde přesně kartu #4934 (i neaktivní), seznam se nedotazuje");
  await set("#shopProdIdSearch", "#4935");
  ok(await chips() === "#4935", "H4 zadám #4935 (s mřížkou) → karta #4935");
  await set("#shopProdIdSearch", " 4001 ");
  ok(await chips() === "#4001", "H5 archivovaná karta se najde, i když není zapnuté „zobrazit archivované“: " + await chips());
  await set("#shopProdIdSearch", "9999");
  ok(await chips() === "" && /9999 neexistuje/.test(await err()), "H6 neexistující ID → prázdná tabulka a hláška: " + await err());
  await set("#shopProdIdSearch", "abc");
  ok(await chips() === "" && /ID karty je číslo/.test(await err()) && !calls.length, "H7 neplatná hodnota → hláška, žádný dotaz na server: " + await err());

  await set("#shopProdIdSearch", "4936"); await page.check("#shopSelectAll"); await page.waitForTimeout(200);
  ok(await page.evaluate(() => [...shopSelectedIds].join(",")) === "4936", "H8 výběr „vybrat vše“ při hledání podle ID označí jen tu jednu kartu");

  await set("#shopProdIdSearch", "");
  ok(await chips() === "#4934,#4935,#4936" && (await err()) === "" && calls.some(c => c.startsWith("LIST")), "H9 po smazání ID se vrátí běžný seznam a hláška zmizí");
  await set("#shopProdSearch", "#4934");
  ok(await chips() === "#4934" && calls.includes("DETAIL 4934"), "H10 #4934 napsané do pole pro název také hledá kartu podle ID");
  await set("#shopProdSearch", "Šroub");
  ok(await chips() === "#4935,#4936" && calls.some(c => c.startsWith("LIST") && /q=%C5%A0roub/.test(c)), "H11 běžné hledání podle názvu funguje beze změny");
  await set("#shopProdSearch", ""); await set("#shopProdSkuSearch", "4936");
  ok(await chips() === "#4936", "H12 hledání podle SKU funguje beze změny");
  ok(!errs.length, "H13 bez JS chyb" + (errs[0] ? " | " + errs[0] : ""));
  await b.close(); srv.close(); console.log(`\n==> ${total - bad}/${total} kontrol OK`); process.exit(bad ? 1 : 0);
})();
