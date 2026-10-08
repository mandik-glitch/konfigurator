// Vlozitelny generator stolu (webapp/embed/stul.html): vysoke 3D okno (~65 % okna rodice, min. 560 px; na mobilu podle sirky), mrizka oken od 720 px, tlacitko Objednat
// (POST /api/cart/items, kontrakt bot5: {product_id, qty:1, configuration:{selection, rules_version}}, cena se neposila), volitelna MONTAZ (castka od serveru, zakaznik BEZ procenta),
// objednavka HOSTA bez registrace (stul-embed-objednavka.js: souhrn z quote, udaje, doprava, odeslani) a navrat z prihlaseni (rozdelana konfigurace).
// Beha nad SKUTECNYM verejnym API generatoru (bridge.py); kosik, /api/auth/me, /api/shop/stul/quote a /order se mockuji pres route (zadny zapis do DB; skutecny backend hosta overuje
// test_embed_host_realny.js pres bridge_kosik.py). Rodice: stejny origin (kategorie 206) a cizi (https://www.logiman.cz).
const { chromium } = require("/opt/konfigurator/node_modules/playwright");
const BASE = process.env.BASE, PID = process.env.PID || "9001";
let bad = 0, total = 0; const ok = (c, t) => { total++; if (!c) bad++; console.log(`[${c ? "OK   " : "CHYBA"}] ${t}`); };
const W = ".pdc-slot[data-slot=w] .pdc-num";
// maketa POST /api/shop/stul/quote (tvar dle api/stul_objednavka_host.py): stul 26 947 Kc bez DPH, montaz 12 % = 3 234 Kc, DPH 21 %
function quoteBody(items, zip, o) {
  const lines = items.map(it => ({ product_id: it.product_id, name: "Konfigurovatelný balicí a pracovní stůl", qty: it.qty, made_to_order: true, stock_qty: null, unit_price_czk: 26947, line_total_czk: 26947 * it.qty,
    unit_price_with_vat_czk: 32605.87, line_total_with_vat_czk: Math.round(26947 * it.qty * 121) / 100, montaz_zvolena: !!it.montaz, montaz_czk: it.montaz ? 3234 : null, montaz_total_czk: it.montaz ? 3234 * it.qty : null,
    montaz_czk_with_vat: it.montaz ? 3913.14 : null, montaz_total_with_vat_czk: it.montaz ? Math.round(3234 * it.qty * 121) / 100 : null,
    configuration: { valid: !(o && o.invalid), changed: false, kod: "STL-TEST01", hash: "h" + JSON.stringify(it.configuration.selection).length, selection: it.configuration.selection, rules_version: it.configuration.rules_version,
                     summary: [{ label: "Šířka desky", value: String((it.configuration.selection || {}).w) + " mm" }, { label: "Kolečka", value: "ano" }], errors: [], weight_kg: null, weight_complete: false } }));
  const goods = lines.reduce((a, l) => a + l.line_total_czk, 0), mont = lines.reduce((a, l) => a + (l.montaz_total_czk || 0), 0), net = goods + mont, amount = Math.round(net * 21) / 100;
  return { currency: "CZK", prices_include_vat: false, valid: !(o && o.invalid), lines, subtotal_goods_czk: goods, subtotal_montaz_czk: mont, subtotal_czk: net, vat: { rate: 21, amount, total_with_vat: Math.round((net + amount) * 100) / 100 },
    shipping_options: [{ id: "toptrans", label: "Doprava Toptrans", net: null, estimated: true, reason: "weight_incomplete" }, { id: "quote", label: "Doprava po dohodě (cenu upřesníme)", net: null }, { id: "pickup", label: "Osobní odběr", net: 0 }],
    notes: ["vat_excluded", "shipping_to_be_confirmed", "proforma_after_shipping_confirmation"] };
}

(async () => {
  const browser = await chromium.launch({ args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
  async function newCtx(width, height, mock) {
    const ctx = await browser.newContext({ viewport: { width, height } });
    mock = mock || {}; ctx.mock = mock; ctx.cartPosts = []; ctx.resolves = 0;
    mock.cart = mock.cart || { status: 201, body: { items: [], total_qty: 1 } }; mock.auth = mock.auth || { status: 401, body: { user: null } };
    mock.quote = mock.quote || {}; mock.order = mock.order || { status: 201 }; ctx.quoteCalls = []; ctx.orderPosts = [];
    await ctx.route("**/api/shop/stul/quote", async (route) => {
      const body = JSON.parse(route.request().postData() || "{}"); ctx.quoteCalls.push(body);
      if (mock.quote.noMontaz && (body.items || []).some(i => i.montaz)) return route.fulfill({ status: 409, contentType: "application/json", body: JSON.stringify({ error: "montaz_unavailable" }) });
      if (mock.quote.status) return route.fulfill({ status: mock.quote.status, contentType: "application/json", body: JSON.stringify(mock.quote.body || {}) });
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(quoteBody(body.items || [], body.delivery_zip, mock.quote)) });
    });
    await ctx.route("**/api/shop/stul/order", async (route) => {
      const body = JSON.parse(route.request().postData() || "{}"); ctx.orderPosts.push(body);
      const q = quoteBody(body.items || [], null), net = q.subtotal_czk;
      await route.fulfill({ status: mock.order.status, contentType: "application/json", body: JSON.stringify(mock.order.body || { reference: "OBJ-TEST-1", status: "received", total: { net, currency: "CZK", rate: 21, amount: q.vat.amount, total_with_vat: q.vat.total_with_vat }, shipping: { id: body.shipping, net: null, review: true }, payment: null, next: "proforma_after_shipping_confirmation", idempotent_replay: false }) });
    });
    await ctx.route("**/api/cart/items", async (route) => {
      if (route.request().method() !== "POST") return route.continue();
      ctx.cartPosts.push(JSON.parse(route.request().postData() || "{}"));
      await route.fulfill({ status: mock.cart.status, contentType: "application/json", body: JSON.stringify(mock.cart.body) });
    });
    await ctx.route("**/api/auth/me", (route) => route.fulfill({ status: mock.auth.status, contentType: "application/json", body: JSON.stringify(mock.auth.body) }));
    ctx.on("request", (r) => { if (/\/resolve/.test(r.url()) && r.method() === "POST") ctx.resolves++; });
    return ctx;
  }
  const ready = async (fr) => { await fr.locator(".mw-win-stage").waitFor({ timeout: 40000 }); await fr.locator(W).waitFor({ timeout: 40000 }); await fr.locator(".emb-order-btn:not([disabled])").waitFor({ timeout: 40000 }); };
  const parentHtml = (src, w) => `<!doctype html><title>rodic</title><body style="margin:0"><iframe id="f" src="${src}" style="width:${w}px;height:700px;border:0"></iframe><script>window.__m=[];addEventListener("message",e=>{if(e.data&&e.data.type)window.__m.push(e.data.type)})</script>`;
  async function framed(ctx, url, src, w) { const pg = await ctx.newPage(); pg.errs = []; pg.on("pageerror", e => pg.errs.push(e.message)); await pg.route(url, r => r.fulfill({ status: 200, contentType: "text/html; charset=utf-8", body: parentHtml(src, w) })); await pg.goto(url); return pg; }
  const stageH = (fr) => fr.locator(".pdc-stage").evaluate(e => Math.round(e.getBoundingClientRect().height));
  const rects = (fr) => fr.locator("body").evaluate(() => { const o = {}; document.querySelectorAll(".mw-win").forEach(e => { const r = e.getBoundingClientRect(); o[e.dataset.win] = { top: Math.round(r.top), left: Math.round(r.left), w: Math.round(r.width), closed: e.classList.contains("is-closed"), hidden: e.hidden }; }); return o; });

  // ---- 1) samostatne (siroke okno 1300x900): vysoke 3D okno, tlacitko Objednat v okne ceny
  let ctx = await newCtx(1300, 900);
  let pg = await ctx.newPage(); pg.errs = []; pg.on("pageerror", e => pg.errs.push(e.message));
  await pg.goto(`${BASE}/embed/stul.html?p=${PID}`); await ready(pg);
  ok((await stageH(pg)) >= 560, "V1 3D okno je vysoké (samostatně, výchozí): " + await stageH(pg) + " px");
  const btn = await pg.locator(".mw-win-price .emb-order-btn").evaluate(e => ({ t: e.textContent, vis: e.getBoundingClientRect().height > 40, w: Math.round(e.getBoundingClientRect().width) }));
  ok(btn.t === "Objednat" && btn.vis, "V2 tlačítko Objednat je v okně ceny, výrazné (výška > 40 px, šířka " + btn.w + " px)");
  let R = await rects(pg);
  ok(R.dim && R.frame && R.extras && Math.abs(R.dim.top - R.frame.top) <= 2 && Math.abs(R.frame.top - R.extras.top) <= 2 && !R.dim.closed && !R.frame.closed, "V3 od 900 px jsou okna voleb ve 3 sloupcích vedle sebe a otevřená");
  ok(R.sum && R.sum.left === R.price.left && R.sum.top > R.price.top, "V4 shrnutí voleb je ve sloupci pod cenou");
  await pg.close(); await ctx.close();

  // ---- 2) vlozene ze STEJNEHO webu (kategorie 206): vyska 3D okna z vysky okna rodice, uzky iframe 880 px = 2 sloupce, otevrena okna
  ctx = await newCtx(1300, 900);
  pg = await framed(ctx, `${BASE}/rodic.html`, `/embed/stul.html?p=${PID}&vh=900`, 880);
  let fr = pg.frameLocator("#f"); await ready(fr);
  const cssVar = await pg.frames().find(f => f.url().includes("/embed/stul.html")).evaluate(() => document.documentElement.style.getPropertyValue("--emb-stage-h"));
  ok(cssVar === "585px" && (await stageH(fr)) >= 585, "V5 výška 3D okna = 65 % výšky okna rodice (900 → " + cssVar + "), skutečně " + await stageH(fr) + " px");
  R = await rects(fr);
  ok(Math.abs(R.dim.top - R.frame.top) <= 2 && R.dim.left < R.frame.left && R.frame.left > 300 && !R.dim.closed && !R.frame.closed && !R.extras.closed, "V6 v iframe 880 px jsou okna ve 2 sloupcích a otevřená (ne mobilní skládací)");
  ok(R.stage.w > 500 && R.price.left > R.stage.left + R.stage.w - 5, "V7 cena a objednávka jsou vpravo od 3D okna (3D " + R.stage.w + " px)");
  // zmena velikosti okna rodice -> zprava stul-embed-viewport
  await pg.evaluate(() => document.getElementById("f").contentWindow.postMessage({ type: "stul-embed-viewport", height: 1200 }, location.origin)); await pg.waitForTimeout(400);
  const css2 = await pg.frames().find(f => f.url().includes("/embed/stul.html")).evaluate(() => document.documentElement.style.getPropertyValue("--emb-stage-h"));
  ok(css2 === "780px", "V8 zpráva stul-embed-viewport od rodiče přepočítá výšku 3D okna (1200 → " + css2 + ")");
  await pg.evaluate(() => document.getElementById("f").contentWindow.postMessage({ type: "stul-embed-theme", theme: "light", accent: "#ff0000" }, location.origin)); await pg.waitForTimeout(300);
  const look = await pg.frames().find(f => f.url().includes("/embed/stul.html")).evaluate(() => [document.documentElement.getAttribute("data-theme"), document.documentElement.style.getPropertyValue("--accent")]);
  ok(look[0] === "light" && look[1] === "#ff0000", "V9 zpráva stul-embed-theme od rodiče přepne motiv a akcent: " + look.join(" "));

  // ---- 3) Objednat: kontrakt POST /api/cart/items, potvrzeni, odkaz do kosiku, odznak (zprava rodici), reset po zmene voleb
  await fr.locator(".emb-order-btn").click();
  await fr.locator(".emb-order-go:not([hidden])").waitFor({ timeout: 20000 });
  const post = ctx.cartPosts[0] || {};
  ok(ctx.cartPosts.length === 1 && post.product_id === Number(PID) && post.qty === 1 && post.lang === "cs", "O1 jeden POST /api/cart/items s product_id " + post.product_id + ", qty 1, lang cs");
  ok(post.configuration && typeof post.configuration.selection === "object" && Object.keys(post.configuration.selection).length > 10 && /\S/.test(post.configuration.rules_version || ""), "O2 configuration = {selection (" + Object.keys((post.configuration || {}).selection || {}).length + " voleb), rules_version}");
  ok(!("price" in post) && !("unit_price_czk" in post) && !("hash" in post.configuration) && !("kod" in post.configuration) && !("price" in post.configuration), "O3 klient neposílá cenu, hash ani kód (server je spočítá znovu)");
  const goInfo = await fr.locator(".emb-order-go").evaluate(e => ({ href: e.getAttribute("href"), target: e.getAttribute("target"), vis: !e.hidden }));
  ok(goInfo.href === "/product.html?openCart=1" && goInfo.target === "_top" && goInfo.vis, "O4 po přidání: odkaz „Pokračovat k objednávce“ vede do košíku (cílem je celé okno, protože rodič je náš web)");
  ok(/Stůl je v košíku/.test(await fr.locator(".emb-order-msg").innerText()), "O5 potvrzení „Stůl je v košíku“");
  await pg.waitForTimeout(300);
  ok((await pg.evaluate(() => window.__m)).includes("stul-embed-cart-added"), "O6 rodič dostal zprávu stul-embed-cart-added (aktualizace odznaku košíku)");
  await fr.locator(W).fill("1400"); await fr.locator(W).blur();
  await fr.locator(".emb-order-go[hidden]").waitFor({ state: "attached", timeout: 20000 }); await pg.waitForTimeout(500);
  ok((await fr.locator(".emb-order-go").evaluate(e => e.hidden)) && !/Stůl je v košíku/.test(await fr.locator(".emb-order-msg").innerText()), "O7 po změně voleb potvrzení „v košíku“ zmizí (další Objednat přidá novou konfiguraci)");
  await pg.close(); await ctx.close();

  // ---- 4) chyby kosiku: product_unavailable (karta jeste neni aktivni), rules_changed (znovu resolve), jina chyba
  ctx = await newCtx(1300, 900, { cart: { status: 400, body: { error: "x", code: "product_unavailable" } } });
  pg = await ctx.newPage(); await pg.goto(`${BASE}/embed/stul.html?p=${PID}`); await ready(pg);
  await pg.locator(".emb-order-btn").click(); await pg.locator(".emb-order-msg.err").waitFor({ timeout: 20000 });
  const un = await pg.locator(".emb-order-msg").evaluate(e => ({ t: e.textContent, href: (e.querySelector("a") || {}).href || "" }));
  ok(/zatím nelze objednat online/.test(un.t) && /\/poptavka-stul\.html$/.test(un.href), "E1 product_unavailable: srozumitelná hláška + odkaz Poptat stůl na míru (" + un.href.replace(/^https?:\/\/[^/]+/, "") + ")");
  ok(!(await pg.locator(".emb-order-btn").isDisabled()), "E2 po chybě je tlačítko zase použitelné");
  const r0 = ctx.resolves; ctx.mock.cart = { status: 409, body: { error: "x", code: "rules_changed" } };
  await pg.locator(".emb-order-btn").click(); await pg.waitForFunction(() => /Pravidla generátoru/.test(document.querySelector(".emb-order-msg").textContent), null, { timeout: 20000 }); await pg.waitForTimeout(800);
  ok(ctx.resolves > r0, "E3 rules_changed: hláška a nový resolve konfigurace (" + r0 + " → " + ctx.resolves + ")");
  ctx.mock.cart = { status: 500, body: {} };
  await pg.locator(".emb-order-btn").click(); await pg.waitForFunction(() => /Nepodařilo se uložit/.test(document.querySelector(".emb-order-msg").textContent), null, { timeout: 20000 });
  ok(true, "E4 neznámá chyba serveru → obecná hláška, žádný pád"); await pg.close(); await ctx.close();

  // ---- 5) nepřihlášený: 401 -> objednávka HOSTA (panel místo výzvy k přihlášení); "Máte účet?" uloží rozdělanou konfiguraci i volbu montáže; po návratu (přihlášený) se obnoví a SAMA přidá do košíku
  ctx = await newCtx(1300, 900, { cart: { status: 401, body: { code: "unauthorized", error: "Neprihlaseno." } } });
  pg = await ctx.newPage(); await pg.goto(`${BASE}/embed/stul.html?p=${PID}`); await ready(pg);
  await pg.locator(W).fill("1400"); await pg.locator(W).blur(); await pg.waitForTimeout(1500); await pg.locator(".emb-order-btn:not([disabled])").waitFor({ timeout: 30000 });
  await pg.locator("#embMontaz").waitFor({ timeout: 20000 }); await pg.locator("#embMontaz").check();
  await pg.locator(".emb-order-btn").click(); await pg.locator(".emb-co:not([hidden])").waitFor({ timeout: 20000 });
  ok(await pg.locator(".emb-order-login").isHidden() && await pg.locator(".mw-pdg").evaluate(e => e.hidden), "P1 401: nepřihlášeného už nic nevyzývá k přihlášení – otevře se objednávka hosta místo generátoru");
  const acc = await pg.locator(".emb-co-account").evaluate(e => ({ href: e.getAttribute("href"), target: e.getAttribute("target"), t: e.textContent }));
  ok(/^\/login\.html\?next=/.test(acc.href) && decodeURIComponent(acc.href).includes("/embed/stul.html?p=" + PID) && acc.target === "_self" && /Máte účet/.test(acc.t), "P1b „Máte účet? Přihlásit se“ vede na /login.html?next=<tato stránka>");
  await Promise.all([pg.waitForURL(/login\.html/, { timeout: 20000 }), pg.locator(".emb-co-account").click()]);
  const stored = await pg.evaluate(() => JSON.parse(sessionStorage.getItem("stulEmbedPending") || "null"));
  ok(stored && stored.pid === PID && stored.selection && stored.selection.w === 1400 && stored.montaz === true, "P2 po kliknutí se rozdělaná konfigurace uložila (šířka " + (stored && stored.selection && stored.selection.w) + ", montáž " + (stored && stored.montaz) + ")");
  ctx.mock.auth = { status: 200, body: { user: { id: 7, email: "z@example.test", role: "user" } } }; ctx.mock.cart = { status: 201, body: { items: [] } }; ctx.cartPosts.length = 0;
  await pg.goto(`${BASE}/embed/stul.html?p=${PID}`); await pg.locator(".emb-order-go:not([hidden])").waitFor({ timeout: 40000 });
  ok(ctx.cartPosts.length === 1 && ctx.cartPosts[0].configuration.selection.w === 1400 && ctx.cartPosts[0].montaz_zvolena === true, "P3 po návratu z přihlášení se konfigurace obnovila (šířka 1400, montáž) a SAMA se přidala do košíku (1 POST s montaz_zvolena)");
  ok(/Po přihlášení jsme vaši konfiguraci uložili/.test(await pg.locator(".emb-order-msg").innerText()) && (await pg.locator(W).inputValue()) === "1400", "P4 hláška o uložení po přihlášení, ve formuláři zůstává 1400");
  ok((await pg.evaluate(() => sessionStorage.getItem("stulEmbedPending"))) === null, "P5 rozdělaná konfigurace se po uložení do košíku smazala (žádné opakování)");
  await pg.reload(); await ready(pg); await pg.waitForTimeout(1500);
  ok(ctx.cartPosts.length === 1, "P6 další načtení stránky nepřidá nic dalšího");
  await pg.close();
  // nepřihlášený po návratu: obnoví volby, ale nic nepřidá a nic si dál nepamatuje
  const pg2 = await ctx.newPage(); ctx.mock.auth = { status: 401, body: { user: null } };
  await pg2.goto(`${BASE}/embed/stul.html?p=${PID}`); await pg2.evaluate(() => sessionStorage.setItem("stulEmbedPending", JSON.stringify({ pid: location.search.match(/p=(\d+)/)[1], selection: { w: 1300 }, ts: Date.now() })));
  ctx.cartPosts.length = 0; await pg2.reload(); await ready(pg2); await pg2.waitForTimeout(1200);
  ok(ctx.cartPosts.length === 0 && (await pg2.evaluate(() => sessionStorage.getItem("stulEmbedPending"))) === null, "P7 nepřihlášený po návratu: nic se nepřidá a rozdělaná konfigurace se zapomene");
  await pg2.close();
  // po prihlaseni karta jeste neni zapnuta (product_unavailable): hlaska, rozdelana konfigurace se smaze a pokus se nezopakuje pri dalsim nacteni
  ctx.mock.auth = { status: 200, body: { user: { id: 7 } } }; ctx.mock.cart = { status: 400, body: { error: "x", code: "product_unavailable" } };
  const pg3 = await ctx.newPage(); await pg3.goto(`${BASE}/embed/stul.html?p=${PID}`); await pg3.evaluate(() => sessionStorage.setItem("stulEmbedPending", JSON.stringify({ pid: location.search.match(/p=(\d+)/)[1], selection: { w: 1300 }, ts: Date.now() })));
  ctx.cartPosts.length = 0; await pg3.reload(); await pg3.locator(".emb-order-msg.err").waitFor({ timeout: 40000 });
  ok(ctx.cartPosts.length === 1 && /nelze objednat online/.test(await pg3.locator(".emb-order-msg").innerText()) && (await pg3.evaluate(() => sessionStorage.getItem("stulEmbedPending"))) === null, "P8 po přihlášení: karta ještě není zapnutá → hláška, rozdělaná konfigurace se smaže");
  await pg3.reload(); await ready(pg3); await pg3.waitForTimeout(1200);
  ok(ctx.cartPosts.length === 1, "P9 automatický pokus se při dalším načtení neopakuje"); await pg3.close(); await ctx.close();

  // ---- 5b) server jeste nema API hosta (pred nasazenim): puvodni vyzva k prihlaseni, zadna rozbita objednavka
  ctx = await newCtx(1300, 900, { cart: { status: 401, body: { code: "unauthorized" } }, quote: { status: 404, body: {} } });
  pg = await ctx.newPage(); await pg.goto(`${BASE}/embed/stul.html?p=${PID}`); await ready(pg); await pg.waitForTimeout(1200);
  ok(await pg.locator(".emb-montaz").isHidden(), "N1 bez API hosta na serveru se zatržítko Montáž neukazuje");
  await pg.locator(".emb-order-btn").click(); await pg.locator(".emb-order-login:not([hidden])").waitFor({ timeout: 20000 });
  ok(await pg.locator(".emb-co:not([hidden])").count() === 0 && /přihlaste/.test(await pg.locator(".emb-order-msg").innerText()) && /^\/login\.html\?next=/.test(await pg.locator(".emb-order-login").getAttribute("href")),
     "N2 bez API hosta: původní výzva „Přihlásit se a pokračovat“, objednávka hosta se neotevře"); await pg.close(); await ctx.close();

  // ---- 5c) objednavka hosta: dalsi scenare (maketa quote/order): mnozstvi, zpet/dokoncit, firma a fakturacni adresa, chyby serveru
  ctx = await newCtx(1300, 900, { cart: { status: 401, body: { code: "unauthorized" } } });
  pg = await ctx.newPage(); pg.errs = []; pg.on("pageerror", e => pg.errs.push(e.message)); await pg.goto(`${BASE}/embed/stul.html?p=${PID}`); await ready(pg);
  await pg.locator(".emb-order-btn").click(); await pg.locator(".emb-co-line").waitFor({ timeout: 20000 }); await pg.locator(".emb-co-totals .emb-co-row").first().waitFor({ timeout: 20000 });
  ok(await pg.locator("#embMontaz").count() === 1 && await pg.locator(".emb-co-montaz input").count() === 1 && !(await pg.locator(".emb-co-montaz input").isChecked()), "G1 montáž je volitelná: v objednávce je nezaškrtnutá, jde zapnout");
  const q0 = ctx.quoteCalls.length; await pg.locator(".emb-co-line-r input[type=number]").fill("2"); await pg.locator(".emb-co-line-r input[type=number]").blur();
  await pg.waitForFunction(() => /53 894/.test(document.querySelector(".emb-co-totals").innerText.replace(/\s/g, " ").replace(/\u00a0/g, " ")) || /53894/.test(document.querySelector(".emb-co-totals").innerText.replace(/\D/g, "")), null, { timeout: 20000 });
  ok(ctx.quoteCalls.length > q0 && ctx.quoteCalls[ctx.quoteCalls.length - 1].items[0].qty === 2, "G2 změna množství na 2 znovu přepočítá souhrn na serveru (53 894 Kč bez DPH)");
  await pg.locator(".emb-co-montaz input").check(); await pg.waitForFunction(() => /Montáž bez DPH/.test(document.querySelector(".emb-co-totals").innerText), null, { timeout: 20000 });
  ok(ctx.quoteCalls[ctx.quoteCalls.length - 1].items[0].montaz === true && /6 468/.test((await pg.locator(".emb-co-totals").innerText()).replace(/[\s\u00a0]/g, " ")), "G3 zapnutí montáže v objednávce: dotaz s montaz:true, řádek Montáž 6 468 Kč (2 ks)");
  await pg.locator(".emb-co-head button").click();
  ok(await pg.locator(".emb-co").isHidden() && await pg.locator(".mw-pdg").isVisible() && /dokončit objednávku \(1\)/i.test(await pg.locator(".emb-order-finish").innerText()), "G4 „Zpět k úpravě stolu“ vrátí generátor, tlačítko „Dokončit objednávku (1)“ zůstává");
  await pg.locator(".emb-order-finish").click(); await pg.locator(".emb-co:not([hidden])").waitFor({ timeout: 10000 });
  ok(await pg.locator(".emb-co-line").count() === 1 && await pg.locator(".emb-co-line-r input[type=number]").inputValue() === "2", "G5 „Dokončit objednávku“ znovu otevře košík hosta (1 řádek, 2 ks) i bez dalšího klikání na Objednat");
  // firma, IČO, jina fakturacni adresa
  await pg.fill("#embCo_name", "Jana Nováková"); await pg.fill("#embCo_email", "jana@example.test"); await pg.fill("#embCo_phone", "603111222");
  await pg.fill("#embCo_d_street", "Dodací 1"); await pg.fill("#embCo_d_city", "Brno"); await pg.fill("#embCo_d_zip", "60200"); await pg.locator("#embCo_consent").check();
  await pg.fill("#embCo_company", "Test s.r.o."); await pg.locator("#embCo_company_id").waitFor({ timeout: 5000 });
  await pg.locator("#embCo_billing_same").uncheck(); await pg.locator(".emb-co-submit:not([disabled])").waitFor({ timeout: 20000 }); await pg.locator(".emb-co-submit").click(); await pg.waitForTimeout(400);
  const e5 = await pg.locator(".emb-co-err:not([hidden])").allInnerTexts();
  ok(!e5.some(t => /IČO/.test(t)) && e5.some(t => /ulici/.test(t)) && ctx.orderPosts.length === 0, "G6 firma BEZ IČO je v pořádku (IČO je nepovinné, spotřebitel ho nemá); jiná fakturační adresa bez údajů: chyby jen u fakturační adresy, nic se neodeslalo");
  await pg.fill("#embCo_company_id", "12345678"); await pg.fill("#embCo_vat_id", "CZ12345678"); await pg.fill("#embCo_b_street", "Fakturační 5"); await pg.fill("#embCo_b_city", "Ostrava"); await pg.fill("#embCo_b_zip", "70200");
  // chyba serveru s polem: PSC
  ctx.mock.order = { status: 400, body: { error: "zip_invalid", field: "delivery.zip" } };
  await pg.locator(".emb-co-submit").click(); await pg.waitForFunction(() => /PSČ/.test(document.querySelector("#embCo_d_zip").parentElement.innerText), null, { timeout: 20000 });
  const bo = ctx.orderPosts[0] || {};
  ok(bo.company === "Test s.r.o." && bo.company_id === "12345678" && bo.vat_id === "CZ12345678" && bo.billing && bo.billing.same === undefined && bo.billing.street === "Fakturační 5" && bo.billing.city === "Ostrava" && bo.billing.zip === "70200" && bo.items[0].montaz === true && bo.items[0].qty === 2,
     "G7 tělo: firma + IČO + DIČ, jiná fakturační adresa, položka 2 ks s montáží");
  await pg.fill("#embCo_company_id", ""); await pg.fill("#embCo_vat_id", ""); const nPost = ctx.orderPosts.length;
  await pg.locator(".emb-co-submit:not([disabled])").waitFor({ timeout: 20000 }); await pg.locator(".emb-co-submit").click(); await pg.waitForFunction((n) => true, nPost); await pg.waitForTimeout(600);
  const bo2 = ctx.orderPosts[ctx.orderPosts.length - 1] || {};
  ok(ctx.orderPosts.length === nPost + 1 && bo2.company === "Test s.r.o." && bo2.company_id === undefined && bo2.vat_id === undefined, "G7b firma bez IČO a DIČ se odešle bez nich (nepovinné): company_id/vat_id v těle nejsou");
  await pg.fill("#embCo_company_id", "12345678"); await pg.fill("#embCo_vat_id", "CZ12345678");
  ok(!(await pg.locator(".emb-co-done").isVisible()) && /PSČ/.test(await pg.locator("#embCo_d_zip").evaluate(e => e.parentElement.innerText)), "G8 chyba serveru s polem (zip_invalid, delivery.zip) se ukáže u PSČ, formulář zůstane");
  // zmena ceny: 409 price_changed -> hlaska a novy souhrn
  ctx.mock.order = { status: 409, body: { error: "price_changed", current_total_net: 31000 } }; const qn = ctx.quoteCalls.length;
  await pg.locator(".emb-co-submit").click(); await pg.waitForFunction(() => /Cena se mezitím změnila/.test(document.querySelector(".emb-co-msg").textContent), null, { timeout: 20000 });
  ok(/31 000/.test((await pg.locator(".emb-co-msg").innerText()).replace(/[\s\u00a0]/g, " ")) && ctx.quoteCalls.length > qn, "G9 price_changed: hláška s novou cenou a nový souhrn ze serveru");
  ctx.mock.order = { status: 429, body: { error: "too_many_orders" } };
  await pg.locator(".emb-co-submit:not([disabled])").waitFor({ timeout: 20000 }); await pg.locator(".emb-co-submit").click(); await pg.waitForFunction(() => /příliš mnoho objednávek/.test(document.querySelector(".emb-co-msg").textContent), null, { timeout: 20000 });
  ctx.mock.order = { status: 500, body: {} };
  await pg.locator(".emb-co-submit:not([disabled])").waitFor({ timeout: 20000 }); await pg.locator(".emb-co-submit").click(); await pg.waitForFunction(() => /Na naší straně|nepodařilo odeslat/.test(document.querySelector(".emb-co-msg").textContent), null, { timeout: 20000 });
  ok(true, "G10 limit objednávek a chyba serveru mají srozumitelné hlášky, formulář zůstane vyplněný (" + await pg.locator("#embCo_name").inputValue() + ")");
  ok(!/obchodními podmínkami/.test(await pg.locator("#embCo_consent").evaluate(e => e.parentElement.innerText)) && /Souhlasím se zpracováním osobních údajů/.test(await pg.locator("#embCo_consent").evaluate(e => e.parentElement.innerText)),
     "G10b dokud stránky podmínek neexistují (404), zůstává dočasné znění souhlasu bez odkazů");
  ok((await pg.locator(".emb-co-submit").innerText()).toLowerCase() === "objednávka zavazující k platbě" && (await pg.locator(".emb-co-submit").getAttribute("class")).includes("mw-btn"), "G13 tlačítko odeslání výslovně říká „Objednávka zavazující k platbě“ (§ 1827 OZ)");
  const lp = await pg.locator(".emb-co-lineprice").first().innerText();
  ok(/bez DPH/.test(lp) && /s DPH/.test(lp), "G14 cena řádku je vždy bez DPH i s DPH: " + lp.replace(/\s+/g, " "));
  ok(/Celkem bez DPH/.test(await pg.locator(".emb-co-totals").innerText()) && /Celkem s DPH/.test(await pg.locator(".emb-co-totals").innerText()), "G15 součty ukazují bez DPH i s DPH");
  ok(!pg.errs.length, "G11 bez JS chyb v objednávce hosta" + (pg.errs[0] ? " | " + pg.errs[0] : "")); await pg.close(); await ctx.close();

  // ---- 5d) stranky podminek a ochrany udaju existuji -> souhlas s odkazy (nove znění bot7), odkazy do noveho panelu
  ctx = await newCtx(1300, 900, { cart: { status: 401, body: { code: "unauthorized" } } });
  await ctx.route(/\/(obchodni-podminky|ochrana-osobnich-udaju)$/, r => r.fulfill({ status: 200, contentType: "text/html", body: "<!doctype html><title>x</title>" }));
  pg = await ctx.newPage(); await pg.goto(`${BASE}/embed/stul.html?p=${PID}`); await ready(pg);
  await pg.locator(".emb-order-btn").click(); await pg.locator(".emb-co-line").waitFor({ timeout: 20000 }); await pg.waitForTimeout(500);
  const cl = await pg.locator("#embCo_consent").evaluate(e => ({ t: e.parentElement.innerText.replace(/\s+/g, " ").trim(), links: [...e.parentElement.querySelectorAll("a")].map(a => [a.getAttribute("href"), a.getAttribute("target"), a.textContent]) }));
  ok(cl.t === "Souhlasím s obchodními podmínkami a beru na vědomí zásady ochrany osobních údajů." && JSON.stringify(cl.links) === JSON.stringify([["/obchodni-podminky", "_blank", "obchodními podmínkami"], ["/ochrana-osobnich-udaju", "_blank", "zásady ochrany osobních údajů"]]),
     "G12 stránky existují: souhlas „Souhlasím s obchodními podmínkami a beru na vědomí zásady ochrany osobních údajů.“ s odkazy do nového panelu: " + cl.t);
  await pg.close(); await ctx.close();

  // ---- 6) CIZI rodic (www.logiman.cz): odkazy do noveho panelu (stranka rodice zustane), objednavka funguje i tam
  ctx = await newCtx(1300, 900);
  await ctx.route("https://embed.test/**", async (route) => { const u = new URL(route.request().url()); if (/\/api\/(cart\/items|auth\/me|shop\/stul\/(quote|order))/.test(u.pathname)) return route.fallback(); await route.fulfill({ response: await route.fetch({ url: BASE + u.pathname + u.search }) }); });
  pg = await framed(ctx, "https://www.logiman.cz/stul.html", `https://embed.test/embed/stul.html?p=${PID}`, 1100);
  fr = pg.frameLocator("#f"); await ready(fr);
  await fr.locator(".emb-order-btn").click(); await fr.locator(".emb-order-go:not([hidden])").waitFor({ timeout: 20000 });
  const tg = await fr.locator(".emb-order-go").evaluate(e => e.getAttribute("target"));
  ok(tg === "_blank" && ctx.cartPosts.length === 1, "C1 cizí rodič (www.logiman.cz): odkaz do košíku se otevírá v novém panelu, objednávka funguje");
  await pg.close(); await ctx.close();

  // ---- 7) mobil 390 px: jeden sloupec, 3D okno podle sirky, cena hned pod 3D, shrnuti az na konci
  ctx = await newCtx(390, 844);
  pg = await framed(ctx, `${BASE}/rodic.html`, `/embed/stul.html?p=${PID}&vh=844`, 360);
  fr = pg.frameLocator("#f"); await ready(fr);
  R = await rects(fr); const sh = await stageH(fr);
  ok(sh >= 480 && sh <= 640, "M1 mobil: 3D okno " + sh + " px (rozmezí 480–640 podle šířky)");
  ok(R.price.top > R.stage.top + 400 && R.price.top < R.dim.top && R.sum.top > R.dim.top, "M2 mobil: cena hned pod 3D oknem, shrnutí až za volbami");
  ok(R.dim.left === R.stage.left && !R.dim.closed && R.frame.closed, "M3 mobil: skládací okna, otevřené jen Rozměry");
  const bw = await fr.locator(".emb-order-btn").evaluate(e => Math.round(e.getBoundingClientRect().width));
  ok(bw > 250, "M4 mobil: tlačítko Objednat přes celou šířku okna (" + bw + " px)");
  ok(!pg.errs.length, "M5 žádné JS chyby na straně rodiče" + (pg.errs[0] ? " | " + pg.errs[0] : ""));
  await pg.close(); await ctx.close();

  await browser.close(); console.log(`\n==> ${total - bad}/${total} kontrol OK`); process.exit(bad ? 1 : 0);
})();
