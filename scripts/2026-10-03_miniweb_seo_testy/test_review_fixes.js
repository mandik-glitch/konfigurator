// Opravy podle externi kontroly (docs/kontrola_openai1_minishop_2026-10-03.md): #6 DIC nepovinne, #12 preview objednavky + parametry shopu, #13 zeme v kontaktu, #15 poskozeny kosik.
const fs = require("fs"), http = require("http"), path = require("path");
const { chromium } = require("/opt/konfigurator/node_modules/playwright");
const LIVE = process.env.WEB_OVERRIDE || "/opt/konfigurator/webapp";          // WEB_OVERRIDE: kandidatni kopie statiky (git worktree), jinak zive webapp
const MIME = { ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css", ".json": "application/json" };
const posts = [];
const srv = http.createServer((req, res) => {
  const u = new URL(req.url, "http://x"), p = u.pathname, j = (o, c) => { res.writeHead(c || 200, { "Content-Type": "application/json" }); res.end(JSON.stringify(o)); };
  if (req.method === "POST") { let b = ""; req.on("data", c => b += c); req.on("end", () => { posts.push({ path: p, q: u.search, body: b ? JSON.parse(b) : {} });
    if (p === "/api/miniweb/quote") return j({ currency: "EUR", lines: [{ net_total: 1000 }], subtotal: 1000, total_goods: 1000, shipping_options: [{ id: "quote", label: "Doprava", net: null }], vat: {}, notes: [] });
    if (p === "/api/miniweb/orders") return j({ reference: "", status: "received", preview: true }, 201);
    if (p === "/api/miniweb/inquiry") return j({ status: "ok", preview: true }, 201);
    return j({}, 404); }); return; }
  if (p === "/api/miniweb/config") return j({ shop: "t", lang: "sk", currency: "EUR", countries: ["SK", "CZ"], contact: {}, price_mode: "shown", checkout_mode: "order", preview: false, alternates: [] });
  if (p === "/api/miniweb/legal") return j({ seller: { name: "Firma s.r.o.", address: "Ulica 1" }, contact: {}, documents: [] });
  if (p.startsWith("/api/")) return j({}, 404);
  const f = path.join(LIVE, p === "/" ? "/index.html" : p);
  if (f.includes("..") || !fs.existsSync(f) || fs.statSync(f).isDirectory()) { res.writeHead(404); return res.end("nf"); }
  res.writeHead(200, { "Content-Type": MIME[path.extname(f)] || "application/octet-stream" }); fs.createReadStream(f).pipe(res);
});
let bad = 0, total = 0; const ok = (c, t) => { total++; if (!c) bad++; console.log(`[${c ? "OK   " : "CHYBA"}] ${t}`); };
(async () => {
  await new Promise(r => srv.listen(0, "127.0.0.1", r)); const base = "http://127.0.0.1:" + srv.address().port;
  const b = await chromium.launch(); const ctx = await b.newContext({ viewport: { width: 1280, height: 900 } });
  const mk = async (url, cart) => { const pg = await ctx.newPage(); pg.errs = []; pg.on("pageerror", e => pg.errs.push(e.message)); await pg.addInitScript(c => { try { sessionStorage.setItem("mw_cart_abc", c); } catch (e) {} }, cart); await pg.goto(base + url); return pg; };

  // #15 poskozeny kosik
  for (const bad_ of ["null", "{}", "[null,5,{\"qty\":\"x\"}]", "\"text\"", "{not json"]) {
    const pg = await mk("/miniweb/cart.html?shop=abc&lang=sk", bad_); await pg.waitForSelector("main#mwMain > *", { timeout: 8000 }).catch(() => {});
    await pg.waitForTimeout(400);
    ok(!pg.errs.length && (await pg.locator("#mwMain").innerText()).length > 0, "K15 poškozený košík " + bad_ + ": stránka nastartuje bez JS chyby" + (pg.errs[0] ? " | " + pg.errs[0] : "")); await pg.close();
  }
  // #6 + #12: objednavka ve verzi s preview
  const item = JSON.stringify([{ product_id: 1, name: "Stôl", sku: "S1", qty: 1, configuration: { selection: {}, rules_version: "1", hash: "h" }, summary: [] }]);
  let pg = await mk("/miniweb/cart.html?shop=abc&lang=sk", item); await pg.waitForSelector("#mwCheckout", { timeout: 8000 });
  await pg.waitForTimeout(600);
  const q = posts.filter(x => x.path === "/api/miniweb/quote")[0];
  ok(q && /shop=abc/.test(q.q) && /lang=sk/.test(q.q), "O12a kalkulace posílá shop a jazyk v adrese: " + (q && q.q));
  const f = { company: "Firma", company_id: "12345678", name: "Jan", email: "a@b.cz", phone: "123", billing_street: "U 1", billing_city: "Mesto", billing_zip: "81101" };
  for (const k in f) await pg.fill(`#mwCheckout input[name=${k}]`, f[k]);
  ok(await pg.locator("#mwCheckout input[name=vat_id]").evaluate(e => !e.required), "D6 DIČ / IČ DPH není povinné ani pro Slovensko");
  await pg.locator("#mwCheckout input[name=b2b_confirm]").check(); await pg.locator("#mwCheckout input[name=consent]").check();
  await pg.locator("#mwCheckout button[type=submit]").click(); await pg.waitForTimeout(900);
  const o = posts.filter(x => x.path === "/api/miniweb/orders")[0];
  ok(o && /shop=abc/.test(o.q) && /lang=sk/.test(o.q), "O12b objednávka posílá shop a jazyk v adrese a prošla i bez DIČ: " + (o && o.q));
  ok((await pg.evaluate(() => sessionStorage.getItem("mw_cart_abc"))).includes("Stôl") && await pg.locator("#mwCheckout").count() === 1, "O12c odpověď preview: košík zůstává, formulář zůstává");
  ok(/Náhľad|neuložila/.test(await pg.locator("#mwCoMsg").innerText()), "O12d zobrazí se hlášení náhledu, ne ‚objednávku sme prijali‘: " + (await pg.locator("#mwCoMsg").innerText())); await pg.close();
  // #13 kontakt: vice zemi
  pg = await mk("/miniweb/contact.html?shop=abc&lang=sk", "[]"); await pg.waitForSelector("form select[name=country]", { timeout: 8000 }).catch(() => {});
  ok(await pg.locator("form select[name=country]").count() === 1, "K13a kontaktní formulář nabízí výběr země u obchodu s více zeměmi");
  for (const [k, v] of [["name", "Jan"], ["email", "a@b.cz"], ["company", "Firma"], ["company_id", "12345678"]]) await pg.fill(`form input[name=${k}]`, v);
  await pg.fill("form textarea[name=message]", "Dotaz"); await pg.selectOption("form select[name=country]", "CZ");
  await pg.locator("form input[name=b2b_confirm]").check(); await pg.locator("form input[name=consent]").check();
  await pg.locator("form button[type=submit]").click(); await pg.waitForTimeout(800);
  const iq = posts.filter(x => x.path === "/api/miniweb/inquiry")[0];
  ok(iq && iq.body.country === "CZ", "K13b dotaz posílá zvolenou zemi: " + (iq && iq.body.country)); await pg.close();
  await b.close(); srv.close(); console.log(`\n==> ${total - bad}/${total} kontrol OK`); process.exit(bad ? 1 : 0);
})();
