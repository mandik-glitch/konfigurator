// Stitky na kartach mini-shopu (pravidlo z category.html hlavniho e-shopu): drazka z groove_family, profil z profil_mm, dodani z rozsahu tydnu v delivery.
const fs = require("fs"), http = require("http"), path = require("path");
const { chromium } = require("/opt/konfigurator/node_modules/playwright");
const LIVE = process.env.WEB_OVERRIDE || "/opt/konfigurator/webapp";          // WEB_OVERRIDE: kandidatni kopie statiky (git worktree), jinak zive webapp
const MIME = { ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css", ".json": "application/json", ".jpg": "image/jpeg" };
const P = (id, o) => Object.assign({ id, slug: "p" + id, sku: "S" + id, category_id: 1, name: "Stôl " + id, summary: "s", description: "", price_from: null, currency: "EUR", delivery: "", configurator: { available: false }, specs: [] }, o);
const PRODUCTS = [P(1, { image_url: "/miniweb/img/produkt-4934.jpg", groove_family: "8", cross_section_label: "30×30", profil_mm: 30, delivery: "Vyrába sa na objednávku. Dodacia lehota je 3–5 týždňov." }),
  P(2, { groove_family: "6,8,10", delivery: "Dodáme do týždňa." }), P(3, {}), P(4, { groove_family: "x;<b>", profil_mm: null, delivery: "Delivery in 4 - 6 weeks." })];
const srv = http.createServer((req, res) => {
  const p = new URL(req.url, "http://x").pathname, j = (o) => { res.writeHead(200, { "Content-Type": "application/json" }); res.end(JSON.stringify(o)); };
  if (p === "/api/miniweb/config") return j({ shop: "t", lang: "sk", currency: "EUR", countries: ["SK"], contact: {}, price_mode: "shown", checkout_mode: "order", preview: false, alternates: [] });
  if (p === "/api/miniweb/categories") return j({ categories: [{ id: 1, parent_id: null, slug: "c", name: "C", count: 4 }] });
  if (p === "/api/miniweb/products") return j({ products: PRODUCTS, total: 4 });
  if (p.startsWith("/api/")) { res.writeHead(404); return res.end("{}"); }
  const f = path.join(LIVE, p === "/" ? "/index.html" : p);
  if (f.includes("..") || !fs.existsSync(f) || fs.statSync(f).isDirectory()) { res.writeHead(404); return res.end("nf"); }
  res.writeHead(200, { "Content-Type": MIME[path.extname(f)] || "application/octet-stream" }); fs.createReadStream(f).pipe(res);
});
let bad = 0, total = 0; const ok = (c, t) => { total++; if (!c) bad++; console.log(`[${c ? "OK   " : "CHYBA"}] ${t}`); };
(async () => {
  await new Promise(r => srv.listen(0, "127.0.0.1", r)); const base = "http://127.0.0.1:" + srv.address().port;
  const b = await chromium.launch(); const page = await b.newPage({ viewport: { width: 1280, height: 900 } }); const errs = []; page.on("pageerror", e => errs.push(e.message));
  await page.goto(base + "/miniweb/category.html"); await page.waitForSelector(".mw-card");
  const cards = await page.$$eval(".mw-card", cs => cs.map(c => ({ badges: [...c.querySelectorAll(".mw-badges .mw-badge")].map(x => x.textContent), profil: (c.querySelector(".mw-badge-profil") || {}).textContent || null })));
  ok(JSON.stringify(cards[0].badges) === JSON.stringify(["Drážka 8 mm", "Dodanie 3–5 týždňov"]), "B1 karta 1: ‚Drážka 8 mm‘ + ‚Dodanie 3–5 týždňov‘ (rozsah z delivery): " + cards[0].badges.join(" | "));
  ok(cards[0].profil === "30×30" && cards[1].profil === null, "B2 profil 30×30 je štítek v obrázku karty 1 (jen tam, kde je profil_mm): " + cards[0].profil);
  ok(JSON.stringify(cards[1].badges) === JSON.stringify(["Drážka 6 mm", "Drážka 8 mm", "Drážka 10 mm"]), "B3 ‚6,8,10‘ = tři štítky drážky, delivery bez rozsahu = žádný štítek dodání");
  ok(cards[2].badges.length === 0 && cards[2].profil === null, "B4 produkt bez dat nemá žádný štítek (ani prázdný)");
  ok(JSON.stringify(cards[3].badges) === JSON.stringify(["Dodanie 4–6 týždňov"]), "B5 neplatná drážka se nezobrazí; rozsah 4 - 6 weeks se přečte: " + cards[3].badges.join(" | "));
  ok(await page.locator(".mw-badges:empty").evaluateAll(es => es.every(e => getComputedStyle(e).display === "none")), "B6 prázdný blok štítků nezabírá místo");
  const css = await page.$eval(".mw-badge-groove", e => { const s = getComputedStyle(e); return { b: s.borderTopColor, c: s.color }; });
  ok(css.b === css.c && css.c !== "rgb(0, 0, 0)", "B7 štítek používá akcentovou barvu z tokenů mini-shopu: " + css.c);
  ok(!errs.length, "B8 bez JS chyb" + (errs[0] ? " | " + errs[0] : ""));
  await b.close(); srv.close(); console.log(`\n==> ${total - bad}/${total} kontrol OK`); process.exit(bad ? 1 : 0);
})();
