// Okno "Pripni cokoli" (zivy 3D prvek bot10) na karte stolu v mini-shopu: nacte se az pri doskrolovani, ma verzi v URL, nevytvari JS chyby.
const fs = require("fs"), http = require("http"), path = require("path");
const { chromium } = require("/opt/konfigurator/node_modules/playwright");
const LIVE = process.env.WEB_OVERRIDE || "/opt/konfigurator/webapp";          // WEB_OVERRIDE: kandidatni kopie statiky (git worktree), jinak zive webapp
const MIME = { ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css", ".json": "application/json", ".glb": "model/gltf-binary", ".jpg": "image/jpeg" };
const PROD = { id: 1, slug: "stol", sku: "S1", category_id: 1, name: "Stôl", summary: "s", description: "Popis.", price_from: null, currency: "EUR", delivery: "", configurator: { available: true, product_id: 4934 }, specs: [], profil_mm: 30 };
const hits = [];
const srv = http.createServer((req, res) => {
  const p = new URL(req.url, "http://x").pathname, j = (o, c) => { res.writeHead(c || 200, { "Content-Type": "application/json" }); res.end(JSON.stringify(o)); };
  hits.push(req.url);
  if (p === "/api/miniweb/config") return j({ shop: "t", lang: "sk", currency: "EUR", accent: "#2dd4bf", countries: ["SK"], contact: {}, price_mode: "shown", checkout_mode: "order", preview: false, alternates: [] });
  if (p === "/api/miniweb/categories") return j({ categories: [] });
  if (p === "/api/miniweb/products/1") return j({ product: PROD });
  if (p === "/api/miniweb/products/2") return j({ product: Object.assign({}, PROD, { id: 2, slug: "stol45", profil_mm: 45 }) });
  if (p.startsWith("/api/")) return j({}, 404);
  const f = path.join(LIVE, p === "/" ? "/index.html" : p);
  if (f.includes("..") || !fs.existsSync(f) || fs.statSync(f).isDirectory()) { res.writeHead(404); return res.end("nf"); }
  res.writeHead(200, { "Content-Type": MIME[path.extname(f)] || "application/octet-stream" }); fs.createReadStream(f).pipe(res);
});
let bad = 0, total = 0; const ok = (c, t) => { total++; if (!c) bad++; console.log(`[${c ? "OK   " : "CHYBA"}] ${t}`); };
(async () => {
  await new Promise(r => srv.listen(0, "127.0.0.1", r)); const base = "http://127.0.0.1:" + srv.address().port;
  const b = await chromium.launch({ args: ["--use-gl=swiftshader", "--enable-webgl", "--ignore-gpu-blocklist"] });
  const page = await b.newPage({ viewport: { width: 1280, height: 700 } }); const errs = [];
  page.on("pageerror", e => errs.push(e.message));
  await page.goto(base + "/miniweb/product.html?id=1"); await page.waitForSelector(".mw-win-attach");
  ok(await page.locator(".mw-win-attach").count() === 1 && (await page.locator(".mw-win-attach .mw-win-h").innerText()).toLowerCase().includes("pripni čokoľvek"), "T1 karta stolu má okno ‚Pripni čokoľvek‘");
  await page.waitForTimeout(500);
  ok(!hits.some(u => u.includes("pripni-cokoli-tile.js")) || await page.evaluate(() => document.querySelector(".mw-win-attach").getBoundingClientRect().top < window.innerHeight + 400), "T2 skript prvku se netáhne dřív, než je okno blízko obrazovky");
  await page.locator(".mw-win-attach").scrollIntoViewIfNeeded(); await page.waitForTimeout(2500);
  ok(hits.some(u => /pripni-cokoli-tile\.js\?v=[0-9a-f]{10}/.test(u)), "T3 po doskrolování se skript načte s verzí ?v=<hash> (cache Cloudflare)");
  await page.waitForSelector(".mw-win-attach canvas", { timeout: 30000 }).catch(() => {});
  ok(await page.locator(".mw-win-attach canvas").count() >= 1, "T4 prvek vytvořil 3D plátno");
  ok(hits.some(u => u.includes("/pripni-cokoli/texty.json")) && hits.some(u => /stavebnice-demo(-30x30)?\.glb/.test(u)), "T5 prvek si načetl texty a model ze své složky");
  ok(hits.some(u => u.includes("stavebnice-demo-30x30.glb")), "T8 profil 30x30 z produktu → animace 30×30 (model stavebnice-demo-30x30.glb)");
  const txt = await page.locator(".mw-win-attach").innerText();
  ok(!/logiman|konfigur[aá]tor|vandr/i.test(txt), "T6 v textu prvku není značka ani zakázané slovo");
  const p2 = await b.newPage(); await p2.goto(base + "/miniweb/product.html?id=2"); await p2.waitForSelector(".mw-win-attach", { state: "attached" });
  // (bot16 2026-10-05: profil bez schvalene animace se pozna z registru texty.json PREDEM (PdcLayout.attachWindow) - okno se vubec neukaze, dric se zobrazovalo a za ~100 ms schovavalo; test jen pocka na DOM a overi, ze zustalo schovane)
  await p2.waitForSelector(".mw-win-attach", { state: "hidden", timeout: 20000 }).catch(() => {}); await p2.waitForTimeout(3000);
  ok(await p2.locator(".mw-win-attach").isHidden(), "T9 profil bez animace (45x45): okno se schová, nikdy se neukáže animace jiného profilu");
  ok(!errs.length, "T7 bez JS chyb" + (errs[0] ? " | " + errs[0] : ""));
  await b.close(); srv.close(); console.log(`\n==> ${total - bad}/${total} kontrol OK`); process.exit(bad ? 1 : 0);
})();
