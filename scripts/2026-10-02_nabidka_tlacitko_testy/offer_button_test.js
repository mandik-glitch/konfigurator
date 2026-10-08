// Test admin-only tlacitka "Vytvorit online nabidku" na SKUTECNE webapp/product.html (falesne API, kontrakt docs/KONTRAKT_VANDR_NABIDKA_ENDPOINT.md).
const fs = require("fs"), http = require("http"), path = require("path");
const { chromium } = require("/opt/konfigurator/node_modules/playwright");
const LIVE = process.env.WEB_DIR || "/opt/konfigurator/webapp", FIX = n => JSON.parse(fs.readFileSync(path.join(__dirname, "fixtures", n + ".json"), "utf8"));
const MIME = { ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css", ".json": "application/json", ".png": "image/png", ".jpg": "image/jpeg", ".svg": "image/svg+xml" };
const st = { user: null, sku: "VD-1234", glb: "x.glb", price: 5000, canOffer: undefined, offerStatus: 201, offerDelay: 300, posts: [], v3d: undefined };
let bad = 0, total = 0;
const ok = (c, t) => { total++; if (!c) bad++; console.log(`[${c ? "OK   " : "CHYBA"}] ${t}`); };
const send = (res, code, obj) => { res.writeHead(code, { "Content-Type": "application/json", "Cache-Control": "no-store" }); res.end(JSON.stringify(obj)); };

const srv = http.createServer(async (req, res) => {
  const p = new URL(req.url, "http://x").pathname;
  if (p.startsWith("/api/")) {
    if (p === "/api/auth/me") return st.user ? send(res, 200, { user: st.user }) : send(res, 401, { user: null });
    if (p === "/api/cart") return send(res, 200, { items: [], total_qty: 0 });
    if (p === "/api/categories") return send(res, 200, FIX("categories"));
    if (p.startsWith("/api/theme-colors")) return send(res, 200, FIX("themecolors"));
    if (p === "/api/public/pd-desc-opacity") return send(res, 200, FIX("descopacity"));
    if (p === "/api/public/cat-tree-colors") return send(res, 200, FIX("cattree"));
    if (p === "/api/montaz-mista") return send(res, 200, FIX("montaz"));
    if (p === "/api/sidebar-blocks") return send(res, 200, FIX("sidebar"));
    if (p.startsWith("/api/track/") || p === "/api/client-errors") { res.writeHead(204); return res.end(); }
    if (p === "/api/shop/products/4903") { const d = FIX("product"); Object.assign(d.product, { sku: st.sku, glb_file: st.glb, price_czk_placeholder: st.price }); if (st.canOffer !== undefined) d.product.can_create_offer = st.canOffer; return send(res, 200, d); }
    if (p === "/api/shop/products/4903/turntable") return send(res, 200, FIX("turntable"));
    if (p === "/api/shop/products/4903/assemblies") return send(res, 200, FIX("assemblies"));
    if (p === "/api/admin/vandr-vyroba/4903/nabidka" && req.method === "POST") {
      st.posts.push(p);
      return setTimeout(() => {
        if (st.offerStatus === 201) return send(res, 201, Object.assign({ status: "ok", offer_id: 123, offer_number: "N-2026-0123", online_url: "/nabidka-online.html?t=abc123", rozmer_mm: [1, 2, 3], pocet_profilu: 40, vandr_car_name: "Ford Transit" }, st.v3d || {}));
        return send(res, st.offerStatus, { error: st.offerStatus === 403 ? "Nemáte oprávnění k této akci." : "Karta ještě nemá hotový 3D model (konverze nedoběhla)." });
      }, st.offerDelay);
    }
    return send(res, 404, { error: "mock " + p });
  }
  const f = path.join(LIVE, decodeURIComponent(p === "/" ? "/index.html" : p));
  if (f.includes("..") || !fs.existsSync(f) || fs.statSync(f).isDirectory()) { res.writeHead(404); return res.end("nf"); }
  res.writeHead(200, { "Content-Type": MIME[path.extname(f)] || "application/octet-stream" }); fs.createReadStream(f).pipe(res);
});

(async () => {
  await new Promise(r => srv.listen(0, "127.0.0.1", r));
  const base = "http://127.0.0.1:" + srv.address().port;
  const browser = await chromium.launch({ args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
  const admin = (perm) => ({ id: 1, name: "A", email: "a@example.test", role: "admin", permissions: perm === undefined ? { sdileny_disk: true } : perm, theme_shop: "dark" });
  async function open(over) {
    Object.assign(st, { user: admin(), sku: "VD-1234", glb: "x.glb", price: 5000, canOffer: undefined, offerStatus: 201, offerDelay: 300, posts: [], v3d: undefined }, over || {});
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 1000 }, locale: "cs-CZ", permissions: ["clipboard-read", "clipboard-write"] });
    const page = await ctx.newPage(); const errs = [];
    page.on("pageerror", e => errs.push(e.message));
    await page.route(/\/track\.js/, r => r.abort());
    await page.goto(base + "/product.html?id=4903", { waitUntil: "load" });
    await page.waitForFunction(() => document.getElementById("pdSku") && document.getElementById("pdSku").textContent, null, { timeout: 20000 }).catch(() => {});
    await page.waitForTimeout(500);
    return { ctx, page, errs };
  }
  const vis = async (page) => !(await page.locator("#pdAdminOffer").isHidden());

  let c = await open();
  ok(await vis(c.page), "T1 admin s právem sdileny_disk u Vandr karty (VD-, cena): admin pruh s tlačítkem je vidět");
  ok((await c.page.locator("#pdOfferBtn").innerText()) === "Vytvořit online nabídku", "T2 text tlačítka ‚Vytvořit online nabídku‘");
  const nextTo = await c.page.evaluate(() => { const a = document.getElementById("pdAdminOffer").getBoundingClientRect(), b = document.getElementById("pdAddCartBtn").getBoundingClientRect(); return a.top >= b.bottom - 2 && a.top - b.bottom < 160; });
  ok(nextTo, "T3 pruh je hned pod blokem ceny a ‚Do košíku‘");
  const spol = await c.page.evaluate(() => { const a = document.getElementById("pdOfferSpol"); if (!a) return null; const r = a.getBoundingClientRect(), m = document.getElementById("pdOfferBtn").getBoundingClientRect();
    return { vidim: !a.hidden && r.width > 0, text: a.textContent.trim(), href: a.getAttribute("href"), target: a.target, rel: a.rel, vedleTlacitka: Math.abs(r.top - m.top) < 30 || r.top >= m.bottom - 2 }; });
  ok(!!spol && spol.vidim && spol.text === "Společná nabídka…" && spol.vedleTlacitka, "T23 u Vandr karty je vedle tlačítka odkaz ‚Společná nabídka…‘ (sloučení levé + pravé strany + přepážky)" + (spol ? "" : " | odkaz chybí"));
  ok(!!spol && spol.href === "/kontrola.html?items=vd:4903&rezim=nabidka" && spol.target === "_blank" && /noopener/.test(spol.rel), "T24 odkaz vede do kontrolní scény v režimu nabídky s touto kartou (nový panel, noopener): " + JSON.stringify(spol && [spol.href, spol.target, spol.rel]));
  const vzh = await c.page.evaluate(() => { const a = document.getElementById("pdOfferVzhled"); if (!a) return null; const r = a.getBoundingClientRect(); return { vidim: !a.hidden && r.width > 0, text: a.textContent.trim(), href: a.getAttribute("href"), target: a.target, rel: a.rel }; });
  ok(!!vzh && vzh.vidim && vzh.text === "Vzhled online nabídek…", "T25 u Vandr karty je i samostatný odkaz ‚Vzhled online nabídek…‘ (Robert: ‚kde je odkaz do kontrolní scény?‘; vzhled neplatí jen pro společné nabídky)" + (vzh ? "" : " | odkaz chybí"));
  ok(!!vzh && vzh.href === "/kontrola.html?items=vd:4903&rezim=nabidka&vzhled=1" && vzh.target === "_blank" && /noopener/.test(vzh.rel), "T26 odkaz vede do kontrolní scény s touto kartou a s otevřeným oknem Vzhled nabídek (&vzhled=1): " + JSON.stringify(vzh && [vzh.href, vzh.target, vzh.rel]));
  await c.page.locator("#pdOfferBtn").click();
  ok(await c.page.locator("#pdOfferConfirm").isVisible() && st.posts.length === 0, "T4 první klik jen zeptá (‚Vytvořit novou online nabídku z této karty?‘), nic se neodeslalo");
  await c.page.locator("#pdOfferNo").click();
  ok(await c.page.locator("#pdOfferBtn").isVisible() && !(await c.page.locator("#pdOfferConfirm").isVisible()), "T5 ‚Zrušit‘ vrátí tlačítko, nic se neodeslalo (" + st.posts.length + " požadavků)");
  await c.page.locator("#pdOfferBtn").click(); await c.page.locator("#pdOfferYes").click();
  ok(await c.page.locator("#pdOfferYes").isDisabled() && /Sestavuji nabídku/.test(await c.page.locator("#pdOfferStatus").innerText()), "T6 po potvrzení je tlačítko zamčené a ukazuje se ‚Sestavuji nabídku…‘");
  await c.page.locator("#pdOfferYes").click({ force: true }).catch(() => {});
  await c.page.waitForFunction(() => /vytvořena/.test(document.getElementById("pdOfferStatus").textContent), null, { timeout: 10000 }).catch(() => {});
  ok(st.posts.length === 1, "T7 dvojklik neodešle druhý požadavek (celkem " + st.posts.length + " POST)");
  const txt = await c.page.locator("#pdOfferStatus").innerText();
  ok(/Nabídka N-2026-0123 vytvořena/.test(txt) && (await c.page.locator("#pdOfferStatus a").getAttribute("href")) === base + "/nabidka-online.html?t=abc123", "T8 po úspěchu: číslo nabídky a odkaz s doplněným originem");
  ok(await c.page.locator("#pdOfferBtn").isHidden(), "T9 hlavní tlačítko se hned nenabízí znovu");
  ok(await c.page.locator("#pdOfferSpol").isVisible(), "T9b odkaz ‚Společná nabídka…‘ zůstává nabídnutý i po vytvoření nabídky z jedné karty");
  await c.page.locator("#pdOfferStatus button", { hasText: "Kopírovat odkaz" }).click(); await c.page.waitForTimeout(300);
  ok((await c.page.evaluate(() => navigator.clipboard.readText()).catch(() => "")) === base + "/nabidka-online.html?t=abc123", "T10 ‚Kopírovat odkaz‘ zkopíruje plný odkaz");
  await c.page.locator("#pdOfferStatus button", { hasText: "Vytvořit další" }).click();
  ok(await c.page.locator("#pdOfferBtn").isVisible(), "T11 ‚Vytvořit další z této karty‘ vrátí tlačítko");
  ok(!c.errs.length, "T12 bez JS chyb" + (c.errs.length ? " | " + c.errs.join("||") : ""));
  await c.page.screenshot({ path: process.env.SHOT || "/tmp/offer_btn.png", clip: { x: 640, y: 60, width: 640, height: 640 } }).catch(() => {});
  await c.ctx.close();

  c = await open({ v3d: { obrazky_zdroj: { narys: "nahrada", view3d: "kombinace" }, poznamka: "Vandr nemá obrázky, použity naše náhledy: kótovaný výkres vyrobil server z 3D modelu." } });
  await c.page.locator("#pdOfferBtn").click(); await c.page.locator("#pdOfferYes").click();
  await c.page.waitForFunction(() => /vytvořena/.test(document.getElementById("pdOfferStatus").textContent), null, { timeout: 10000 }).catch(() => {});
  const t13 = await c.page.locator("#pdOfferStatus").innerText();
  ok(/Obrázky: náhrada - výkres z našeho 3D modelu, 3D pohledy: jeden z Vandru, jeden náš\./.test(t13) && /Vandr nemá obrázky, použity naše náhledy/.test(t13), "T13a obrazky_zdroj + poznamka: krátká česká poznámka pod odkazem (náhrada z našich snímků)");
  await c.ctx.close();
  c = await open({ v3d: { obrazky_zdroj: { narys: "vandr", view3d: "vandr" } } });
  await c.page.locator("#pdOfferBtn").click(); await c.page.locator("#pdOfferYes").click();
  await c.page.waitForFunction(() => /vytvořena/.test(document.getElementById("pdOfferStatus").textContent), null, { timeout: 10000 }).catch(() => {});
  ok(/Obrázky: všechny z Vandru\./.test(await c.page.locator("#pdOfferStatus").innerText()), "T13b všechny obrázky z Vandru: ‚Obrázky: všechny z Vandru.‘");
  await c.ctx.close();

  c = await open({ offerStatus: 400 });
  await c.page.locator("#pdOfferBtn").click(); await c.page.locator("#pdOfferYes").click();
  await c.page.waitForFunction(() => /nemá hotový/.test(document.getElementById("pdOfferStatus").textContent), null, { timeout: 10000 }).catch(() => {});
  ok((await c.page.locator("#pdOfferStatus").innerText()).includes("Karta ještě nemá hotový 3D model (konverze nedoběhla).") && await c.page.locator("#pdOfferBtn").isVisible(), "T13 chyba 400: text z endpointu beze změny, tlačítko zase použitelné");
  await c.ctx.close();

  c = await open({ v3d: { v3d: false, v3d_duvod: "model bez pohyblivých dílů", v3d_varovani: ["w1", "w2"] } });
  await c.page.locator("#pdOfferBtn").click(); await c.page.locator("#pdOfferYes").click();
  await c.page.waitForFunction(() => /vytvořena/.test(document.getElementById("pdOfferStatus").textContent), null, { timeout: 10000 }).catch(() => {});
  const t14 = await c.page.locator("#pdOfferStatus").innerText();
  ok(/3D pohyby v nabídce nejsou \(model bez pohyblivých dílů\)/.test(t14) && /Varování \(admin\): w1 \| w2/.test(t14), "T14 v3d:false a v3d_varovani se ukážou jako poznámka (zpětně kompatibilní pole)");
  await c.ctx.close();

  // Vzhled online nabidek (Robert 2026-10-07: "to nema byt jen v jedne karte, ale automaticky v kazde"): odkaz #pdOfferVzhled je v SAMOSTATNEM admin pruhu #pdAdminVzhled, nezavisle na tom, zda jde z karty udelat nabidku;
  // vidi ho kazdy ADMIN u kazde karty (Vandr karta -> kontrolni scena s jejim modelem, jina -> generator stolu s oknem Vzhled), ostatni ne.
  const VZH_VANDR = "/kontrola.html?items=vd:4903&rezim=nabidka&vzhled=1", VZH_JINA = "/stul-konfigurator-40.html?vzhled=1";
  const hidden = [
    ["T15 zákazník (bez přihlášení)", { user: null }, null],
    ["T16 role user bez práv", { user: { id: 2, name: "U", email: "u@example.test", role: "user", permissions: null, theme_shop: "dark" } }, null],
    ["T17 staff bez práva sdileny_disk", { user: admin({ sdileny_disk: false, cenik: true }) }, VZH_VANDR],
    ["T18 karta bez VD- v SKU (např. konfigurovatelný stůl)", { sku: "STUL.SYSTEM30.KONF" }, VZH_JINA],
    ["T20 karta bez ceny", { price: null }, VZH_VANDR],
    ["T21 server říká can_create_offer.ok = false", { canOffer: { ok: false, duvod: "GLB soubor chybí na disku" } }, VZH_VANDR],
  ];
  for (const [name, over, vzhHref] of hidden) {
    c = await open(over);
    ok(!(await vis(c.page)) && await c.page.locator("#pdOfferSpol").isHidden(), name + ": admin pruh nabídky i odkaz Společná nabídka jsou skryté");
    const v = await c.page.evaluate(() => { const a = document.getElementById("pdOfferVzhled"), bx = document.getElementById("pdAdminVzhled"); const r = a ? a.getBoundingClientRect() : null; return { vidim: !!a && !!bx && !bx.hidden && r.width > 0, href: a && a.getAttribute("href"), target: a && a.target }; });
    if (vzhHref === null) ok(!v.vidim, name + ": odkaz Vzhled online nabídek je skrytý (jen admin)");
    else ok(v.vidim && v.href === vzhHref && v.target === "_blank", name + ": admin vidí odkaz Vzhled online nabídek i když z karty nejde udělat nabídku, vede na " + vzhHref + " " + JSON.stringify(v));
    await c.ctx.close();
  }
  c = await open({ glb: null });
  ok(await vis(c.page), "T19 API u Vandr karet glb_file schválně vrací null (ochrana modelu) - tlačítko se proto neskrývá, GLB hlídá endpoint (400 s hláškou)"); await c.ctx.close();
  c = await open({ sku: "STUL.SYSTEM30.KONF", canOffer: { ok: true, duvod: "" } });
  ok(await vis(c.page), "T22 server říká can_create_offer.ok = true: rozhoduje server, ne SKU"); await c.ctx.close();

  await browser.close(); srv.close();
  console.log(`\n==> ${total - bad}/${total} kontrol OK`);
  process.exit(bad ? 1 : 0);
})();
