// Hezke adresy v JS (window.MW_BOOT od serveru, api/miniweb_seo.py): odkazy, kategorie podle slugu, produkt podle id a podle slugu (nahled konceptu).
const fs = require("fs"), http = require("http"), path = require("path");
const { chromium } = require("/opt/konfigurator/node_modules/playwright");
const LIVE = process.env.WEB_OVERRIDE || "/opt/konfigurator/webapp";          // WEB_OVERRIDE: kandidatni kopie statiky (git worktree), jinak zive webapp
const MIME = { ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css", ".json": "application/json" };
const srv = http.createServer((req, res) => {
  const p = new URL(req.url, "http://x").pathname;
  if (p === "/api/auth/me") { res.writeHead(200, { "Content-Type": "application/json" }); return res.end(JSON.stringify({ user: { id: 1, role: "admin", email: "a@b.c" } })); }
  if (p.startsWith("/api/")) { res.writeHead(404); return res.end(); }
  const f = path.join(LIVE, p === "/" ? "/index.html" : p);
  if (f.includes("..") || !fs.existsSync(f) || fs.statSync(f).isDirectory()) { res.writeHead(404); return res.end("nf"); }
  res.writeHead(200, { "Content-Type": MIME[path.extname(f)] || "application/octet-stream" }); fs.createReadStream(f).pipe(res);
});
const PATHS = { category: "/kategoria/", product: "/produkt/", contact: "/kontakt", legal: "/pravne-informacie", cart: "/kosik", shop: "/obchod" };
let bad = 0, total = 0; const ok = (c, t) => { total++; if (!c) bad++; console.log(`[${c ? "OK   " : "CHYBA"}] ${t}`); };
async function open(b, url, boot) {
  const page = await b.newPage({ viewport: { width: 1280, height: 900 } }); page.errs = []; page.on("pageerror", e => page.errs.push(e.message));
  if (boot) await page.addInitScript(x => { window.MW_BOOT = x; }, boot);
  await page.goto(url); return page;
}
const hrefs = (page, sel) => page.$$eval(sel, a => a.map(x => x.getAttribute("href")));
(async () => {
  await new Promise(r => srv.listen(0, "127.0.0.1", r)); const base = "http://127.0.0.1:" + srv.address().port;
  const b = await chromium.launch(); const Q = "?lang=sk&demo=1&shop=packstations";
  let page = await open(b, base + "/miniweb/index.html" + Q, { page: "home", pretty: true, paths: PATHS });
  await page.waitForSelector(".mw-hero h1");
  const all = await hrefs(page, "a[href]");
  ok(all.some(h => h.startsWith("/produkt/packing-station-ps120")) && !all.some(h => /product\.html/.test(h)), "L1 karty a tlačítko vedou na /produkt/<slug> (ne product.html)");
  ok(all.includes("/obchod" + Q) || all.some(h => h.startsWith("/obchod")), "L2 menu Obchod → /obchod");
  ok(all.some(h => h.startsWith("/kontakt")) && all.some(h => h.startsWith("/pravne-informacie")) && all.some(h => h.startsWith("/kosik")), "L3 kontakt, právní informace, košík mají hezké adresy");
  ok(all.some(h => /^\/produkt\/[a-z0-9-]+\?.*demo=1/.test(h)), "L4 náhledové parametry (demo/shop/lang) zůstávají za otazníkem");
  ok(!page.errs.length, "L5 bez JS chyb" + (page.errs[0] ? " | " + page.errs[0] : "")); await page.close();

  page = await open(b, base + "/miniweb/index.html" + Q, null); await page.waitForSelector(".mw-hero h1");
  const plain = await hrefs(page, "a[href]");
  ok(plain.some(h => h.startsWith("/miniweb/product.html?")) && plain.some(h => h.startsWith("/miniweb/contact.html")), "L6 bez MW_BOOT zůstávají staré adresy /miniweb/*.html (statický náhled)"); await page.close();

  page = await open(b, base + "/miniweb/index.html" + Q, null); await page.waitForSelector(".mw-hero h1");
  const modes = await page.evaluate(() => [{ checkout_mode: "order", inquiry_only: true }, { checkout_mode: "inquiry", inquiry_only: false }, { inquiry_only: true }, {}].map(c => { MW.cfg = c; return MW.mode().checkout; }));
  ok(modes.join() === "order,inquiry,inquiry,order", "M1 režim pokladny: checkout_mode rozhoduje (order+inquiry_only → order), inquiry_only jen záloha: " + modes.join()); await page.close();

  page = await open(b, base + "/miniweb/category.html" + Q, { page: "category", pretty: true, paths: PATHS, slug: "packing-stations", cat: "packing-stations" });
  await page.waitForSelector(".mw-layout h1");
  const h1 = await page.locator(".mw-layout h1").innerText();
  ok(h1 === "Baliace a pracovné stoly", "K1 kategorie podle slugu z MW_BOOT (bez ?cat=): h1 = " + h1);
  const cat = await hrefs(page, ".mw-tree a");
  ok(cat.length && cat.every(h => h.startsWith("/kategoria/")), "K2 strom kategorií má /kategoria/<slug>"); await page.close();

  page = await open(b, base + "/miniweb/product.html" + Q, { page: "product", pretty: true, paths: PATHS, slug: "packing-station-ps120", id: 9001 });
  await page.waitForSelector("h1");
  ok((await page.locator("h1").first().innerText()).length > 0 && (await page.locator(".mw-crumbs a").first().getAttribute("href")).startsWith("/?"), "P1 produkt podle id z MW_BOOT se vykreslí");
  ok(!page.errs.length, "P2 bez JS chyb" + (page.errs[0] ? " | " + page.errs[0] : "")); await page.close();

  page = await open(b, base + "/miniweb/product.html" + Q, { page: "product", pretty: true, paths: PATHS, slug: "packing-station-ps120" });
  await page.waitForSelector("h1", { timeout: 8000 });
  ok((await page.locator("h1").first().innerText()).length > 0 && !page.errs.length, "P3 koncept: bez id se produkt dohledá podle slugu"); await page.close();
  await b.close(); srv.close(); console.log(`\n==> ${total - bad}/${total} kontrol OK`); process.exit(bad ? 1 : 0);
})();
