// Test mini-shopu Packstations: skutecne soubory (kandidat), skutecny viewer3d.js a demo modely z disku, jen /api/auth/me je simulovano.
const fs = require("fs");
const http = require("http");
const path = require("path");
const { chromium } = require("/opt/konfigurator/node_modules/playwright");

const HERE = __dirname;
const LIVE = process.env.WEB_OVERRIDE || "/opt/konfigurator/webapp";          // WEB_OVERRIDE: kandidatni kopie statiky (git worktree), jinak zive webapp
const OVERLAYS = [LIVE];            // testuje se to, co je skutecne v repu (webapp/miniweb + webapp/js/product-configurator.js)
const SHOTS = process.env.SHOTS || path.join("/tmp", "miniweb_shots"); fs.mkdirSync(SHOTS, { recursive: true });
const MIME = { ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8", ".json": "application/json", ".glb": "model/gltf-binary", ".svg": "image/svg+xml", ".png": "image/png", ".jpg": "image/jpeg" };
const BRAND = /logiman|konfigur[áa]tor|vandrawee|logi\s*(?:<[^>]*>\s*)*man\b/i;
const CZECH = /[ěščřžýáíéúůťďň]/i;
let user = { id: 1, email: "staff@example.test", role: "admin", name: "Staff" };
const reqs = [];

const server = http.createServer((req, res) => {
  const u = new URL(req.url, "http://x"), p = decodeURIComponent(u.pathname);
  reqs.push(p);
  if (p === "/api/auth/me") { res.writeHead(200, { "Content-Type": "application/json" }); return res.end(JSON.stringify({ user })); }
  if (p.startsWith("/api/")) { res.writeHead(p === "/api/client-errors" ? 204 : 404); return res.end(); }
  for (const root of OVERLAYS) {
    const f = path.join(root, p);
    if (f.startsWith(root) && fs.existsSync(f) && fs.statSync(f).isFile()) { res.writeHead(200, { "Content-Type": MIME[path.extname(f)] || "application/octet-stream", "Cache-Control": "no-store" }); return fs.createReadStream(f).pipe(res); }
  }
  res.writeHead(404); res.end("nf");
});

let bad = 0, total = 0;
const ok = (c, t) => { total++; if (!c) bad++; console.log(`[${c ? "OK   " : "CHYBA"}] ${t}`); };
const norm = s => String(s).replace(/\s+/g, " ").trim();

(async () => {
  await new Promise(r => server.listen(0, "127.0.0.1", r));
  const base = "http://127.0.0.1:" + server.address().port;
  const browser = await chromium.launch({ args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
  async function open(url, opts = {}) {
    const ctx = await browser.newContext(Object.assign({ viewport: { width: 1280, height: 900 }, locale: "en-GB" }, opts.ctx || {}));
    await ctx.route(/pripni-cokoli/, r => r.abort());      // viz poznamka v test_cs_konfigurator.js (Pripni cokoli zdrzuje opusteni stranky pod SwiftShaderem)
    const page = await ctx.newPage(); const errs = [];
    page.on("pageerror", e => errs.push(e.message));
    page.on("console", m => { if (m.type() === "error" && !/Failed to load resource/.test(m.text())) errs.push("console: " + m.text().slice(0, 160)); });
    await page.goto(base + url, { waitUntil: "load" });
    return { ctx, page, errs };
  }
  const text = page => page.locator("body").innerText();

  // ---------- statické kontroly souborů ----------
  const files = []; (function walk(d) { fs.readdirSync(d).forEach(n => { const f = path.join(d, n); fs.statSync(f).isDirectory() ? walk(f) : files.push(f); }); })(path.join(LIVE, "miniweb"));
  const brandHits = files.filter(f => BRAND.test(fs.readFileSync(f, "utf8"))).map(f => path.basename(f));
  ok(!brandHits.length, "S1 žádný soubor mini-shopu neobsahuje jméno značky ani rozdělené logo (" + files.length + " souborů)" + (brandHits.length ? " | " + brandHits : ""));
  const dict = JSON.parse(fs.readFileSync(path.join(LIVE, "miniweb/i18n/en.json"), "utf8"));
  const src = files.filter(f => /\.(js|html)$/.test(f)).map(f => fs.readFileSync(f, "utf8")).join("\n");
  const used = new Set();
  for (const m of src.matchAll(/(?<![A-Za-z0-9_.])(?:MW\.)?t\(\s*["']([a-zA-Z0-9_]+\.[a-zA-Z0-9_.]*[a-zA-Z0-9_])["']/g)) used.add(m[1]);
  for (const m of src.matchAll(/i18n:\s*["']([a-zA-Z0-9_.]+)["']/g)) used.add(m[1]);
  for (const m of src.matchAll(/data-i18n(?:-attr)?="([^"]+)"/g)) m[1].split(";").forEach(x => used.add(x.includes(":") ? x.split(":")[1].trim() : x.trim()));
  for (const m of src.matchAll(/["'](country\.|nav\.|home\.step)["']\s*\+/g)) { /* dynamické klíče se kontrolují níže */ }
  const dyn = ["country.CZ", "country.SK", "country.DE", "country.AT", "country.PL", "home.step1.t", "home.step1.d", "home.step2.t", "home.step2.d", "home.step3.t", "home.step3.d", "legal.terms", "legal.privacy", "legal.returns"];
  dyn.forEach(k => used.add(k));
  const missing = [...used].filter(k => !/^(home\.(why|usp|extras|faq|cta2)|faq\.)/.test(k) && !(k in dict) && !Object.keys(dict).some(x => x.startsWith(k)) && !/^(demo\.|pdc\.)/.test(k));
  ok(!missing.length, "S2 každý překladový klíč použitý v kódu existuje v en.json (" + used.size + " klíčů)" + (missing.length ? " | chybí: " + missing.join(", ") : ""));
  const htmlText = files.filter(f => f.endsWith(".html")).map(f => fs.readFileSync(f, "utf8").replace(/<script[\s\S]*?<\/script>|<style[\s\S]*?<\/style>/g, "")).join("\n");
  const hard = [...htmlText.matchAll(/>([^<>]*[A-Za-z]{2,}[^<>]*)</g)].map(m => m[1].trim()).filter(Boolean);
  ok(!hard.length, "S3 v HTML není žádný pevně zapsaný text (vše přes překladové klíče)" + (hard.length ? " | " + hard.slice(0, 3) : ""));
  ok(!Object.values(dict).some(v => CZECH.test(v)), "S4 překlady v en.json neobsahují české znaky");
  ok(!/innerHTML|outerHTML|document\.write|eval\(/.test(files.filter(f => /miniweb[^/]*\.js$|demo-api\.js$/.test(f)).map(f => fs.readFileSync(f, "utf8")).join("\n")), "S5 kód mini-shopu nepoužívá innerHTML/eval (texty jen přes textContent)");

  // ---------- brána pro staff ----------
  user = null;
  let { ctx, page } = await open("/miniweb/index.html?demo=1");
  await page.waitForSelector(".mw-gate", { timeout: 8000 });
  ok(norm(await page.locator(".mw-gate").innerText()).includes("signed-in staff only") && await page.locator(".mw-hero, .mw-grid").count() === 0, "G1 nepřihlášený: jen hláška a odkaz na přihlášení, žádný obsah");
  ok((await page.locator(".mw-gate a").getAttribute("href")).startsWith("/login.html?next="), "G2 odkaz na přihlášení s návratem na stránku");
  ok(await page.locator('meta[name=robots]').first().getAttribute("content") === "noindex, nofollow", "G3 stránka je noindex");
  await ctx.close();
  user = { id: 2, email: "zakaznik@example.test", role: "user", name: "Customer" };
  ({ ctx, page } = await open("/miniweb/index.html?demo=1"));
  await page.waitForSelector(".mw-gate", { timeout: 8000 });
  ok(norm(await page.locator(".mw-gate").innerText()).includes("not public") && await page.locator(".mw-grid").count() === 0, "G4 běžný zákazník (role user): ‚This preview is not public.‘, žádný obsah");
  await ctx.close();
  user = { id: 1, email: "staff@example.test", role: "admin", name: "Staff" };

  // ---------- úvod ----------
  ({ ctx, page } = await open("/miniweb/index.html?demo=1&shop=packstations&lang=en"));
  await page.waitForSelector(".mw-hero h1");
  const t1 = await text(page);
  ok(norm(await page.locator(".mw-hero h1").innerText()) === "Packing tables and workbenches made to your size" && await page.locator(".mw-card").count() === 1 && await page.locator("ol.mw-steps li").count() === 3, "H1 úvod: nadpis, 1 pilotní stůl, 3 kroky");
  ok(!BRAND.test(t1) && !CZECH.test(t1), "H2 viditelný text úvodu je anglicky a bez značky");
  ok(await page.evaluate(() => document.documentElement.lang) === "en" && (await page.title()).includes("Packing Stations"), "H3 <html lang>, titulek z překladu");
  ok((await page.locator(".mw-card").getAttribute("href")).includes("demo=1") && (await page.locator(".mw-links a").first().getAttribute("href")).includes("shop=packstations"), "H4 odkazy drží parametry shop/lang/demo (výběr obchodu na společné doméně)");
  ok(await page.locator(".mw-staffbar").isVisible(), "H5 pruh ‚Staff preview – not public‘ je vidět");
  // (od 2026-10-04 má en.json bohatý úvod od bot7 = jako SK: strom kategorií se na domovské stránce nekreslí, je na stránce kategorie)
  ok(await page.locator(".mw-tree a").count() === 0, "H6a bohatý úvod (home.h1) nekreslí strom kategorií na domovské stránce");
  await page.goto(`${page.url().split("/miniweb/")[0]}/miniweb/category.html?demo=1&shop=packstations&lang=en`); await page.waitForSelector(".mw-tree a");
  ok(await page.locator(".mw-tree a").count() === 2, "H6 strom kategorií (Tables > Packing stations) je na stránce kategorie");
  await page.screenshot({ path: path.join(SHOTS, "home_desktop.png"), fullPage: true });
  await ctx.close();

  // ---------- kategorie ----------
  ({ ctx, page } = await open("/miniweb/category.html?demo=1&cat=packing-stations"));
  await page.waitForSelector(".mw-grid");
  ok(await page.locator(".mw-side .mw-tree a[aria-current]").count() === 1 && await page.locator(".mw-card").count() === 1, "K1 kategorie: aktivní větev stromu a 1 produkt");
  await ctx.close();

  // ---------- karta stolu s konfigurátorem (skutečný viewer + demo modely z disku) ----------
  ({ ctx, page } = await open("/miniweb/product.html?demo=1&id=9001"));
  const perrs = []; page.on("pageerror", e => perrs.push(e.message));
  await page.waitForSelector(".pdc-panel:not([hidden])", { timeout: 20000 });
  await page.waitForSelector(".pdc-stage .v3d-root canvas", { timeout: 40000 }).catch(() => {});
  await page.waitForTimeout(1500);
  const pt = await page.evaluate(() => { const c = document.body.cloneNode(true); c.querySelectorAll(".v3d-root").forEach(n => n.remove()); return c.innerText; });
  const hudCz = await page.evaluate(() => /[ěščřžýáíéúůťďň]/i.test((document.querySelector(".v3d-root") || { innerText: "" }).innerText));
  ok(!hudCz, "P1b texty uvnitř 3D prohlížeče (HUD) jsou anglicky (V3D labels z i18n v3d.*)");
  const keysMissing = await page.evaluate(() => { const need = (window.V3D && V3D.labelKeys) || []; return need.filter(k => !(window.MW.dict["v3d." + k])); });
  ok(keysMissing.length === 0, "P1c slovník en.json pokrývá všech " + await page.evaluate(() => V3D.labelKeys.length) + " klíčů V3D.labelKeys" + (keysMissing.length ? " | chybí: " + keysMissing : ""));
  const mB = pt.match(BRAND), mC = pt.match(CZECH);
  ok(!mB && !mC, "P1 celá karta včetně panelu konfigurátoru je anglicky a bez značky" + (mB ? " | značka: " + JSON.stringify(pt.slice(Math.max(0, mB.index - 30), mB.index + 30)) : "") + (mC ? " | česky: " + JSON.stringify(pt.slice(Math.max(0, mC.index - 30), mC.index + 30)) : ""));
  ok(norm(await page.locator("#mwPdPrice").innerText()) === "€1,290.00", "P2 cena základní konfigurace z demo pravidel: " + norm(await page.locator("#mwPdPrice").innerText()));
  ok(await page.locator(".pdc-tabs").count() === 0 && await page.locator(".pdc-cta").count() === 0, "P3 bez záložek Otočka/Konfigurátor (mini-shop nemá otočku), konfigurátor je rovnou");
  ok(await page.locator(".pdc-stage .v3d-root canvas").count() === 1, "P4 3D model z disku (demo stůl) se načetl do skutečného prohlížeče");
  ok(!reqs.some(r => /scene\.html/.test(r)), "P5 žádný požadavek na scene.html");
  await page.locator("label.pd-pill:has(input[value=w200])").click();
  await page.waitForTimeout(1200);
  ok(norm(await page.locator("#mwPdPrice").innerText()) === "€1,470.00", "P6 volba +200 mm: cena 1 470 € (1 290 + 180): " + norm(await page.locator("#mwPdPrice").innerText()));
  ok(await page.locator(".pdc-stage .v3d-root").count() === 1, "P7 po výměně modelu je v prohlížeči stále jedna instance (setModel nebo nové připojení)");
  await page.locator("label.pd-pill:has(input[value=steel])").click();
  await page.waitForSelector(".pdc-stage-msg:not([hidden])", { timeout: 5000 }).catch(() => {});
  ok(norm(await page.locator(".pdc-stage-msg").innerText().catch(() => "")) === "Preparing model…", "P8 u nerezové desky ‚Preparing model…‘ (ukázka stavu skládání)");
  await page.waitForSelector(".pdc-stage-msg", { state: "hidden", timeout: 15000 }).catch(() => {});
  const legsNa = await page.locator("label.pd-pill:has(input[value=adjustable])").getAttribute("title");
  ok((legsNa || "").includes("not available with"), "P9 nedostupná kombinace má anglický důvod: " + legsNa);
  await page.locator("label.pd-pill:has(input[value=birch])").click(); await page.waitForTimeout(800);
  await page.locator(".pdc-slot[data-slot=shelf] input").check({ force: true }); await page.waitForTimeout(800);
  await page.locator("#mwQty").fill("2");
  await page.locator("#mwAdd").click();
  ok(norm(await page.locator("#mwPdMsg").innerText()) === "Added to the cart." && await page.locator("#mwCartCount").innerText() === "2", "P10 přidání do košíku: hláška a odznak 2 ks");
  await page.screenshot({ path: path.join(SHOTS, "product_desktop.png"), fullPage: true });
  ok(!perrs.length, "P11 bez JS chyb na kartě" + (perrs.length ? " | " + perrs.join("||") : ""));

  // ---------- košík ----------
  await page.locator(".mw-cart").click();
  await page.waitForSelector(".mw-line");
  const ct = await text(page);
  ok(ct.includes("Packing station PS-120") && ct.includes("Lower shelf") && ct.includes("Birch plywood") && !CZECH.test(ct), "C1 košík: řádek s konfigurací v angličtině");
  const sub = n => n.toLocaleString("en-IE", { style: "currency", currency: "EUR" });
  const lineTotal = (1290 + 180 + 85) * 2;       // vychozi + sirka +200 mm + police, 2 ks
  ok(norm(await page.locator(".mw-row-total").innerText()).includes(sub(lineTotal)), "C2 zboží bez DPH ze serveru (quote.total_goods) = 2 × (1 290 + 180 + 85) = " + sub(lineTotal) + ": " + norm(await page.locator(".mw-row-total").innerText()));
  ok(norm(await page.locator(".mw-totals").innerText()).includes("Prices are shown excl. VAT.") && !/VAT \d/.test(await page.locator(".mw-totals").innerText()), "C3 poznámka o DPH ze serveru, žádné vlastní počítání DPH ani dopravy v prohlížeči");
  ok((await page.locator("#mwCheckout input[name=shipping]").count()) === 2 && /Delivery by agreement/.test(await page.locator("#mwCheckout").innerText()) && /Personal pickup/.test(await page.locator("#mwCheckout").innerText()), "C4 možnosti dopravy dodává server (po dohodě / osobní odběr)");
  await page.locator("#mwCheckout input[name=company]").fill("Test company");
  await page.locator("#mwCountry").selectOption("DE");
  await page.waitForTimeout(300);
  ok(await page.locator("#mwCheckout input[name=vat_id]").evaluate(e => !e.required), "C5 země ≠ CZ: DIČ / IČ DPH zůstává nepovinné (pravidlo mini-shopu, server ho nevyžaduje)");
  ok(await page.locator("#mwCheckout input[name=company]").inputValue() === "Test company", "C6 změna země nesmaže rozepsaný formulář");
  await page.locator("#mwCheckout button[type=submit]").click();
  ok(norm(await page.locator("#mwCoMsg").innerText()) === "Please enter the company registration number.", "C7 chybí IČO: hláška v angličtině");
  await page.locator("#mwCheckout input[name=company_id]").fill("12345678"); await page.locator("#mwCheckout input[name=vat_id]").fill("DE123456789");
  for (const [n, v] of [["name", "Jan Test"], ["email", "jan@example.test"], ["phone", "+420123456789"], ["billing_street", "Main 1"], ["billing_city", "Praha"], ["billing_zip", "11000"]]) await page.locator(`#mwCheckout input[name=${n}]`).fill(v);
  ok(await page.locator("#mwCheckout .mw-delivery-box").isHidden() && /Billing address/.test(await page.locator("#mwCheckout").innerText()), "C7b fakturační adresa + zaškrtnuté ‚Delivery address is the same‘ (dodací pole skrytá)");
  await page.locator("#mwCheckout input[name=delivery_same]").uncheck();
  ok(await page.locator("#mwCheckout .mw-delivery-box").isVisible() && await page.locator("#mwCheckout input[name=delivery_zip]").evaluate(e => e.required), "C7c odškrtnutí: dodací adresa (ulice, město, PSČ) je povinná");
  await page.locator("#mwCheckout input[name=delivery_same]").check();
  await page.locator("#mwCheckout input[name=b2b_confirm]").check(); await page.locator("#mwCheckout input[name=consent]").check();
  await page.locator("#mwCheckout button[type=submit]").click();
  ok(norm(await page.locator("#mwCoMsg").innerText()).startsWith("Demo: the order was not sent"), "C8 demo objednávka: nic se neodesílá, hláška ‚Demo: the order was not sent…‘");
  await page.locator(".mw-line .mw-link").click();
  ok(norm(await page.locator("#mwCartWrap").innerText()).includes("Your cart is empty.") && await page.locator("#mwCartCount").isHidden(), "C9 odebrání položky: prázdný košík, odznak zmizí");
  await ctx.close();

  // ---------- kontakt a právní ----------
  ({ ctx, page } = await open("/miniweb/contact.html?demo=1"));
  await page.waitForSelector(".mw-form");
  await page.locator(".mw-form [name=name]").fill("A"); await page.locator(".mw-form [name=email]").fill("a@example.test"); await page.locator(".mw-form [name=company]").fill("Co"); await page.locator(".mw-form [name=company_id]").fill("12345678"); await page.locator(".mw-form [name=message]").fill("B"); await page.locator(".mw-form [name=b2b_confirm]").check(); await page.locator(".mw-form [name=consent]").check();
  await page.locator(".mw-form button[type=submit]").click(); await page.waitForTimeout(100);
  ok(norm(await page.locator("#mwContactMsg").innerText()) === "Demo: the message was not sent.", "T1 kontakt: demo formulář nic neodesílá");
  await page.goto(base + "/miniweb/legal.html?demo=1"); await page.waitForSelector("h1");
  ok(!/Text to be provided|Returns|Terms and conditions/.test(await text(page)) && !BRAND.test(await text(page)), "T2 právní stránka bez zástupných sekcí a bez značky (údaje prodejce a dokumenty jen ze serveru)");
  await ctx.close();

  // ---------- režimy ze serveru: ceny skryté + poptávkový košík (demo data, konfigurace přepsaná serverem) ----------
  const cfgOver = (over) => async (route) => { const r = await route.fetch(); const j = await r.json(); await route.fulfill({ response: r, json: Object.assign(j, over) }); };
  ({ ctx, page } = await open("/miniweb/index.html?demo=1&shop=packstations", {}));
  await page.close(); page = await ctx.newPage();
  const rerrs = []; page.on("pageerror", e => rerrs.push(e.message));
  await page.route("**/miniweb/config.json", cfgOver({ price_mode: "hidden", inquiry_only: true, checkout_mode: "inquiry" }));
  await page.goto(base + "/miniweb/index.html?demo=1");
  await page.waitForSelector(".mw-card");
  ok(norm(await page.locator(".mw-card .mw-price").innerText()) === "Price on request" && !(await text(page)).includes("€"), "R1 price_mode=hidden: karta ukazuje ‚Price on request‘, nikde cena ani měna");
  ok(norm(await page.locator(".mw-cart").innerText()).startsWith("Inquiry"), "R2 inquiry_only: hlavička říká ‚Inquiry‘ místo ‚Cart‘");
  await page.goto(base + "/miniweb/product.html?demo=1&id=9001");
  await page.waitForSelector(".pdc-panel:not([hidden])", { timeout: 20000 }); await page.waitForTimeout(800);
  ok(norm(await page.locator("#mwPdPrice").innerText()) === "Price on request" && !await page.locator(".pdc-price").isVisible(), "R3 karta: ‚Price on request‘ a skrytý řádek ceny konfigurátoru");
  ok(norm(await page.locator("#mwAdd").innerText()).toLowerCase() === "add to inquiry" && !(await page.locator(".mw-buy").innerText()).includes("excl."), "R4 tlačítko ‚Add to inquiry‘, bez ‚excl. VAT‘");
  await page.locator("label.pd-pill:has(input[value=anthracite])").click(); await page.waitForTimeout(700);
  await page.locator("#mwAdd").click();
  ok(norm(await page.locator("#mwPdMsg").innerText()) === "Added to your inquiry.", "R5 přidání do poptávky");
  await page.goto(base + "/miniweb/cart.html?demo=1"); await page.waitForSelector("#mwInquiry");
  ok(await page.locator("#mwCountry").count() === 0 && !(await text(page)).includes("€") && !/VAT\s+\d/.test(await text(page)) && !/shipping/i.test(await text(page)), "R6 poptávkový košík v demu: bez cen, DPH a dopravy");
  ok(!rerrs.length, "R7 bez JS chyb" + (rerrs.length ? " | " + rerrs.join("||") : ""));
  await ctx.close();

  // ---------- skutečné tvary API (bot5): fake odpovědi přes route, ne demo ----------
  const posts = [];
  const mkApi = async (pg, over) => {
    await pg.route("**/api/miniweb/config*", route => route.fulfill({ json: Object.assign({ shop: "packstations", lang: "en", locale: "en-IE", currency: null, accent: "#2dd4bf", countries: ["CZ", "SK", "DE", "AT", "PL"], contact: { email: "x@example.test", phone: "+421 900 000 000", hours: "" }, price_mode: "hidden", inquiry_only: true, inquiry_enabled: true, alternates: [{ lang: "de", href: "https://de.example.test/" }], preview: true }, over || {}) }));
    await pg.route("**/api/miniweb/legal*", route => route.fulfill({ json: { seller: { name: "Seller Ltd", address: "Street 1, Town", country_code: "CZ", id: "12345678", vat_id: "CZ12345678" }, contact: {}, documents: [{ kind: "terms", title: "Operator and inquiries", body: "Body A\nline two", updated: "2026-10-03" }, { kind: "privacy", title: "", body: "Privacy body" }] } }));
    await pg.route("**/api/miniweb/categories*", route => route.fulfill({ json: { categories: [{ id: 1, parent_id: null, slug: "tables", name: "Tables", count: 1 }] } }));
    await pg.route("**/api/miniweb/products*", route => route.fulfill({ json: { products: [{ id: 5, slug: "t", sku: "PS-120", category_id: 1, name: "Table", summary: "S", description: "A\nB", price_from: null, currency: null, delivery: "D", configurator: { available: false, default_view: "configurator", product_id: null }, specs: [] }], total: 1 } }));
  };
  const seed = JSON.stringify([{ product_id: 5, name: "Table", sku: "PS-120", kod: "PS-ABC123", qty: 2, configuration: { selection: { top: "birch" }, hash: "abc123", rules_version: "v1" }, summary: [{ label: "Worktop", value: "Birch" }] }]);
  const ctx2 = await browser.newContext({ viewport: { width: 1280, height: 900 }, locale: "en-GB" });
  await ctx2.route(/pripni-cokoli/, r => r.abort());
  const pg2 = await ctx2.newPage(); const e2 = []; pg2.on("pageerror", e => e2.push(e.message));
  await pg2.route("**/api/auth/me", route => route.fulfill({ json: { user: { id: 1, email: "s@example.test", role: "admin", name: "S" } } }));
  await mkApi(pg2);
  await pg2.route("**/api/miniweb/inquiry*", async (route) => {
    const body = JSON.parse(route.request().postData() || "{}"); posts.push({ url: route.request().url(), body });
    const n = posts.length - 1;
    if (n === 0) return route.fulfill({ status: 400, json: { error: "email_invalid", field: "email" } });
    if (n === 1) return route.fulfill({ status: 429, json: { error: "rate_limited" } });
    if (n === 2) return route.fulfill({ status: 201, json: { inquiry_id: 0, preview: true } });
    return route.fulfill({ status: 201, json: { status: "ok", inquiry_id: 17 } });
  });
  await pg2.goto(base + "/miniweb/cart.html?shop=packstations&lang=en");
  await pg2.evaluate((v) => sessionStorage.setItem("mw_cart_packstations", v), seed); await pg2.reload();
  await pg2.waitForSelector("#mwInquiry");
  ok(await pg2.locator("#mwCartCount").innerText() === "2" && !(await text(pg2)).includes("€") && await pg2.locator("#mwCountry").count() === 0, "N1 skutečné API (hidden, inquiry_only): poptávkový košík bez cen, součtů a DPH");
  ok(await pg2.evaluate(() => document.querySelector("link[hreflang=de]").href) === "https://de.example.test/", "N2 hreflang sourozenecké jazykové verze ze serverové konfigurace");
  ok((await pg2.locator(".mw-controller").innerText()) === "Personal data controller: Seller Ltd, Street 1, Town.", "N3b poptávkový formulář: správce osobních údajů = prodejce ze serveru (/api/miniweb/legal)");
  ok(!(await text(pg2)).includes("x@example.test"), "N3 e-mail z konfigurace se nikde nezobrazuje (pravidlo: žádný živý e-mail na webu)");
  const f = (n, v) => pg2.locator(`#mwInquiry [name=${n}]`).fill(v);
  await pg2.locator("#mwInquiry button[type=submit]").click();
  ok(norm(await pg2.locator("#mwInqMsg").innerText()) === "Please fill in the required fields." && posts.length === 0, "N4 prázdný formulář: nic se neodešle, hláška");
  await f("name", "Jan"); await f("email", "bad"); await f("message", "Hello");
  const submit = async () => { await pg2.locator("#mwInquiry button[type=submit]").click(); await pg2.waitForTimeout(150); };
  const msg = async () => norm(await pg2.locator("#mwInqMsg").innerText());
  await submit(); ok(await msg() === "Please enter the company name." && posts.length === 0, "N5a bez názvu firmy se neodešle (jen pro podnikatele)");
  await f("company", "Acme s.r.o."); await submit(); ok(await msg() === "Please enter the company registration number." && posts.length === 0, "N5b bez IČO se neodešle");
  await f("company_id", "12345678"); await submit(); ok(await msg() === "Please confirm that you are inquiring on behalf of a business." && posts.length === 0, "N5c bez potvrzení podnikatele se neodešle");
  await pg2.locator("#mwInquiry [name=b2b_confirm]").check(); await submit(); ok(await msg() === "Please tick the consent box." && posts.length === 0, "N5d bez souhlasu se neodešle");
  await pg2.locator("#mwInquiry select[name=country]").selectOption("SK"); await pg2.locator("#mwInquiry [name=consent]").check();
  ok(await pg2.locator("#mwInquiry input[name=vat_id]").evaluate(e => !e.required && e.getAttribute("aria-required") !== "true"), "N5e zahraničí (SK): DIČ / IČ DPH je nepovinné, formulář tím neblokuje");
  await f("vat_id", "SK2020123456"); await pg2.locator("#mwInquiry select[name=country]").selectOption("CZ");
  await pg2.locator("#mwInquiry button[type=submit]").click(); await pg2.waitForTimeout(300);
  ok(posts.length === 1 && norm(await pg2.locator("#mwInqMsg").innerText()) === "Please enter a valid e-mail address.", "N6 serverová chyba email_invalid → přeložená hláška");
  ok(!(await pg2.locator("#mwFooter").innerText()).includes("businesses only") && await pg2.locator("#mwInquiry .mw-b2b").count() === 0, "N6b věta ‚jen pro podnikatele‘ se nezobrazuje (jen firma a IČO jako povinná pole)");
  const p0 = posts[0].body;
  ok(p0.company === "Acme s.r.o." && p0.company_id === "12345678" && p0.vat_id === "SK2020123456" && p0.b2b_confirm === true && p0.consent === true && p0.website === "" && p0.country === "CZ" && p0.items.length === 1 && p0.items[0].product_id === 5 && p0.items[0].qty === 2 && p0.items[0].kod === "PS-ABC123" && p0.items[0].configuration.hash === "abc123" && p0.items[0].summary[0].label === "Worktop", "N7 tělo poptávky: consent, prázdný honeypot, země, položky s kódem, konfigurací a souhrnem");
  ok(!JSON.stringify(p0).match(/unit_net|price|net_total/i) && posts[0].url.includes("shop=packstations") && posts[0].url.includes("lang=en"), "N8 klient neposílá žádnou cenu; shop a jazyk jdou v dotazu (společná doména)");
  await pg2.locator("#mwInquiry button[type=submit]").click(); await pg2.waitForTimeout(300);
  ok(norm(await pg2.locator("#mwInqMsg").innerText()) === "Too many requests. Please wait a few minutes and try again.", "N9 429 rate_limited → přeložená hláška");
  await pg2.locator("#mwInquiry button[type=submit]").click(); await pg2.waitForTimeout(300);
  ok(norm(await pg2.locator("#mwInqMsg").innerText()) === "Preview: the inquiry was checked but not saved." && await pg2.locator("#mwCartCount").innerText() === "2", "N10 náhled konceptu (preview:true): nic se neuloží, košík zůstává");
  await pg2.locator("#mwInquiry button[type=submit]").click(); await pg2.waitForSelector("#mwCartWrap .mw-msg");
  ok(norm(await pg2.locator("#mwCartWrap").innerText()).startsWith("Thank you, your inquiry has been received.") && await pg2.locator("#mwCartCount").isHidden(), "N11 úspěch 201: poděkování a vyprázdněný košík");
  await pg2.goto(base + "/miniweb/contact.html?shop=packstations&lang=en"); await pg2.waitForSelector(".mw-form");
  ok(!(await text(pg2)).includes("x@example.test") && (await text(pg2)).includes("+421 900 000 000") && !(await text(pg2)).includes("To be confirmed") && !(await text(pg2)).includes("Opening hours"), "N12 kontakt: bez e-mailu, telefon jen když je vyplněný, žádné ‚To be confirmed‘ pro prázdné hodiny");
  ok((await pg2.locator(".mw-controller").innerText()) === "Personal data controller: Seller Ltd, Street 1, Town.", "N12b u formuláře je správce osobních údajů = prodejce ze serveru");
  posts.length = 0;
  await pg2.locator(".mw-form [name=name]").fill("Jan"); await pg2.locator(".mw-form [name=email]").fill("j@example.test"); await pg2.locator(".mw-form [name=company]").fill("Acme s.r.o."); await pg2.locator(".mw-form [name=company_id]").fill("12345678"); await pg2.locator(".mw-form [name=message]").fill("Hi"); await pg2.locator(".mw-form [name=b2b_confirm]").check();
  await pg2.locator(".mw-form [name=consent]").check(); await pg2.locator(".mw-form button[type=submit]").click(); await pg2.waitForTimeout(300);
  ok(posts.length === 1 && posts[0].body.items === undefined && posts[0].body.message === "Hi" && posts[0].body.company === "Acme s.r.o." && posts[0].body.company_id === "12345678" && posts[0].body.b2b_confirm === true, "N13 kontaktní formulář = stejná poptávka bez položek");
  await pg2.goto(base + "/miniweb/legal.html?shop=packstations"); await pg2.waitForSelector("h1");
  ok((await text(pg2)).includes("Seller Ltd, Street 1, Town, Company ID: 12345678, VAT ID: CZ12345678") && !(await text(pg2)).includes("x@example.test"), "N14 právní stránka: údaje prodejce ze serveru (id, DIČ), bez e-mailu");
  const lt = await text(pg2);
  ok(lt.includes("Operator and inquiries") && lt.includes("Body A") && lt.includes("line two") && lt.includes("Privacy") && lt.includes("Privacy body") && !/Text to be provided|Returns|Complaints/.test(lt), "N14b právní stránka vykreslí jen dokumenty ze serveru (nadpis z title nebo z klíče legal.privacy), žádné zástupné sekce ani vrácení");
  reqs.length = 0;
  await pg2.goto(base + "/miniweb/category.html?shop=packstations&cat=tables"); await pg2.waitForSelector(".mw-card");
  ok(await pg2.locator(".mw-card").count() === 1, "N15 kategorie: seznam z API");
  await pg2.goto(base + "/miniweb/index.html?shop=packstations&lang=en"); await pg2.waitForSelector(".mw-card");
  ok(await pg2.evaluate(() => Object.keys(MW.dict).filter(k => k.indexOf("demo.") === 0).length) === 0 && !/placeholders|demo/i.test(await pg2.locator("footer, #mwFooter").innerText()), "N19 bez ?demo=1 (skutečné API): žádné ukázkové texty (demo.*) ve slovníku ani poznámka o demu v patičce");
  ok(!e2.length, "N16 bez JS chyb" + (e2.length ? " | " + e2.join("||") : ""));
  // veřejný živý shop: žádná brána, žádný staff pruh
  const ctx3 = await browser.newContext({ locale: "en-GB" }); const pg3 = await ctx3.newPage(); const reqs3 = []; pg3.on("request", q => reqs3.push(new URL(q.url()).pathname));
  await pg3.route("**/api/auth/me", route => route.fulfill({ json: { user: null } })); await mkApi(pg3, { preview: false });
  await pg3.goto(base + "/miniweb/index.html"); await pg3.waitForSelector(".mw-card");
  ok(!reqs3.some(x => /demo-api|auth\/me/.test(x)), "N17b živý shop: nenačítá demo-api.js a neptá se na /api/auth/me (" + reqs3.join(",") + ")");
  ok(await pg3.locator(".mw-gate").count() === 0 && await pg3.locator(".mw-staffbar").count() === 0, "N17 živý shop (preview:false): anonym vidí obsah, žádná brána ani pruh pro staff");
  // koncept pro nepovolaného: server dá 404 → přihlášení
  const ctx4 = await browser.newContext({ locale: "en-GB" }); const pg4 = await ctx4.newPage();
  await pg4.route("**/api/miniweb/config*", route => route.fulfill({ status: 404, json: { error: "shop_not_found" } }));
  await pg4.route("**/api/auth/me", route => route.fulfill({ json: { user: null } }));
  await pg4.goto(base + "/miniweb/index.html"); await pg4.waitForSelector(".mw-gate");
  ok((await text(pg4)).includes("signed-in staff only") && await pg4.locator(".mw-gate a").count() === 1, "N18 server vrátil 404 a nikdo není přihlášen: nabídka přihlášení (obsah se neukáže)");
  await ctx2.close(); await ctx3.close(); await ctx4.close();

  // ---------- mobil ----------
  ({ ctx, page } = await open("/miniweb/product.html?demo=1&id=9001", { ctx: { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, deviceScaleFactor: 2 } }));
  await page.waitForSelector(".pdc-panel:not([hidden])", { timeout: 20000 });
  await page.waitForSelector(".pdc-stage .v3d-root canvas", { timeout: 40000 }).catch(() => {});
  await page.waitForTimeout(800);
  ok(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth), "M1 mobil 390 px: bez vodorovného posunu na kartě");
  const inView = await page.evaluate(() => [".mw-nav", ".pdc-stage", ".pdc-panel", ".mw-buy"].map(s => { const e = document.querySelector(s); if (!e) return [s, null]; const r = e.getBoundingClientRect(); return [s, Math.round(r.left), Math.round(r.right)]; }));
  ok(inView.every(([, l, r]) => l === null || (l >= 0 && r <= 391)), "M2 hlavička, model, panel i nákupní řádek se vejdou do 390 px: " + JSON.stringify(inView));
  ok(await page.evaluate(() => getComputedStyle(document.querySelector(".mw-buy")).position) === "sticky", "M3 cena a ‚Add to cart‘ jsou na mobilu přilepené dole");
  ok(await page.locator(".pdc-lock").isVisible(), "M4 dotykové zařízení: 3D je zamčené (‚Tap to control the 3D view‘), stránka jde posouvat");
  await page.screenshot({ path: path.join(SHOTS, "product_mobile.png") });
  await page.goto(base + "/miniweb/index.html?demo=1"); await page.waitForSelector(".mw-hero");
  ok(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth), "M5 mobil: úvod bez vodorovného posunu");
  await page.screenshot({ path: path.join(SHOTS, "home_mobile.png"), fullPage: true });
  await ctx.close();

  await browser.close(); server.close();
  console.log(`\n==> ${total - bad}/${total} kontrol OK`);
  process.exit(bad ? 1 : 0);
})();
