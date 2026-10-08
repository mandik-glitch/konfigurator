// Generator stolu SYSTEM 45 ("Robustni") napasovany na kategorii 330 "Robustni balici stul system 45" a na kartu #5353 (bot16, 2026-10-08; Robert: "sem napasovat generator stolu system 45",
// adresa /robustni-balici-stul-system-45). SKUTECNE stranky v Chromiu (swiftshader WebGL) proti ZIVEMU webu (API, embed generator, karta #5353 jen CTENI - nic se nezapisuje, nic se neobjednava);
// kandidat sablon pred nasazenim: CAT_HTML=<category.html> PROD_HTML=<product.html> (dokument stranky se podstrci mistnim souborem, vse ostatni jde na zivy web). Puvodni sablony MUSI selhat.
// Spusteni: node scripts/2026-10-08_system45_kategorie_testy/test_s45_kategorie.js     BASE=https://autovestavby.logiman.cz (vychozi)
const { chromium } = require("/opt/konfigurator/node_modules/playwright");
const fs = require("fs");
const BASE = process.env.BASE || "https://autovestavby.logiman.cz";
const CAT_HTML = process.env.CAT_HTML, PROD_HTML = process.env.PROD_HTML;
let bad = 0, total = 0; const ok = (c, t) => { total++; if (!c) bad++; console.log(`[${c ? "OK   " : "CHYBA"}] ${t}`); };
const W = ".pdc-slot[data-slot=w] .pdc-num";
const SLUG = { 206: "lehky-balici-stul-system-30", 312: "ergonomicky-balici-stul-system-35", 311: "robustni-balici-stul-system-40", 330: "robustni-balici-stul-system-45" };
(async () => {
  const browser = await chromium.launch({ args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
  const ctx = await browser.newContext({ viewport: { width: 1400, height: 1000 } }); const errs = [];
  // kandidat sablon: dokument stranky (SSR z ziveho webu) se zachova a jen se v nem vymeni blok `const CATEGORY_GENERATORS = {...};` / `const PRODUCT_GENERATORS = {...};` za blok z kandidatni sablony
  const blokRe = jmeno => new RegExp("const " + jmeno + " = \\{[\\s\\S]*?\\n\\};");
  const blokZ = (soubor, jmeno) => { const m = blokRe(jmeno).exec(fs.readFileSync(soubor, "utf8")); if (!m) throw new Error("blok " + jmeno + " nenalezen v " + soubor); return m[0]; };
  const catBlok = CAT_HTML ? blokZ(CAT_HTML, "CATEGORY_GENERATORS") : null, prodBlok = PROD_HTML ? blokZ(PROD_HTML, "PRODUCT_GENERATORS") : null;
  if (catBlok || prodBlok) await ctx.route("**/*", async route => {
    const r = route.request(); const u = new URL(r.url());
    const jeKat = Object.values(SLUG).some(sl => u.pathname === "/" + sl), jeKarta = u.pathname === "/produkt/pracovni-stul-system-45-konfigurovatelny";
    if (u.origin === BASE && r.resourceType() === "document" && ((catBlok && jeKat) || (prodBlok && jeKarta))) {
      const resp = await route.fetch(); let body = await resp.text();
      const re = blokRe(jeKat ? "CATEGORY_GENERATORS" : "PRODUCT_GENERATORS");
      if (!re.test(body)) throw new Error("v zivem dokumentu chybi blok generatoru: " + u.pathname);
      body = body.replace(re, () => (jeKat ? catBlok : prodBlok));
      return route.fulfill({ response: resp, body });
    }
    return route.continue();
  });
  const pg = await ctx.newPage(); pg.on("pageerror", e => errs.push(e.message));
  const frameOf = async (sel = "#catGeneratorFrame") => {
    const h = await pg.waitForSelector(sel, { state: "attached", timeout: 60000 }); const f = await h.contentFrame();
    await f.locator(W).waitFor({ timeout: 120000 }); await f.locator(".emb-order-btn:not([disabled])").waitFor({ timeout: 120000 }); return f;
  };
  const nadpis = () => pg.locator("#catTitle").innerText();

  // K0 kontrola postupu: kategorie systemu 40 (puvodni, funguje) ma generator, ostatni nesmi byt dotcena
  await pg.goto(`${BASE}/${SLUG[311]}`, { waitUntil: "domcontentloaded" });
  let f = await frameOf();
  ok(/p=4954/.test(f.url()) && await f.locator(".pdc-sys-b[data-system='40']").getAttribute("aria-pressed") === "true", "K0 kategorie systém 40 beze změny: generátor s kartou 4954");
  ok(await f.locator(".pdc-sys-b[data-system='45']").count() === 1, "K0b v přepínači systémů generátoru je tlačítko „45“ (server ho nabízí, karta #5353 je aktivní)");

  // K1 kategorie 330 = systém 45
  await pg.goto(`${BASE}/${SLUG[330]}`, { waitUntil: "domcontentloaded" });
  const vid = await pg.waitForSelector("#catGenerator", { state: "visible", timeout: 40000 }).then(() => true).catch(() => false);          // blok je od zacatku v DOM (display:none), ukaze se az po odpovedi API kategorie
  ok(vid, "K1 na stránce „Robustní balicí stůl system 45“ je viditelný generátor stolu (blok #catGenerator)");
  if (vid) {
    f = await frameOf();
    ok(/p=5353/.test(f.url()), "K2 iframe generátoru je karta 5353 (systém 45): " + f.url().replace(/theme=.*/, ""));
    ok((await pg.locator("#catGeneratorFrame").getAttribute("title")) === "Generátor stolu – systém 45", "K3 titulek iframe „Generátor stolu – systém 45“");
    ok((await nadpis()).includes("system 45"), "K4 nadpis kategorie zůstává „" + (await nadpis()) + "“ (texty kategorie se nesahají)");
    ok(await f.locator(".pdc-sys-b[data-system='45']").getAttribute("aria-pressed") === "true", "K5 v přepínači je zvolený systém 45");
    const hl = await f.locator(".pdc-slot[data-slot=d] .pdc-num").first().inputValue().catch(() => null);
    ok(hl !== null, "K6 generátor 45 ukazuje pole hloubky (hluboký stůl; hodnota " + hl + ")");
    // K7 prepnuti 45 -> 40 a zpet s prenosem vyberu
    await f.locator(W).fill("1700"); await f.locator(W).blur(); await pg.waitForTimeout(2500);
    await Promise.all([pg.waitForURL(/robustni-balici-stul-system-40/, { timeout: 30000 }), f.locator(".pdc-sys-b[data-system='40']").click()]);
    f = await frameOf();
    ok(/system 40/i.test(await nadpis()) && /p=4954/.test(f.url()) && (await f.locator(W).inputValue()) === "1700", "K7 přepínač 45 → 40 přešel na kategorii systému 40 a vzal šířku 1700");
    await Promise.all([pg.waitForURL(/robustni-balici-stul-system-45/, { timeout: 30000 }), f.locator(".pdc-sys-b[data-system='45']").click()]);
    f = await frameOf();
    ok(/system 45/i.test(await nadpis()) && /p=5353/.test(f.url()) && (await f.locator(W).inputValue()) === "1700", "K8 přepínač 40 → 45 přešel na kategorii systému 45 (dřív tlačítko nic neudělalo) a vzal šířku 1700");
  }
  // K13 hloubka az 2500 mm (smysl systemu 45): v e-shopove vrstve (embed) musi jit nastavit hloubka nad 1500. (Server resolve vracel `options.d.max = 1500` - S.ROZSAH misto S._rozsahy(system) v api/stul_shop.py;
  // opraveno bot10 927929f0, nasazeno 2026-10-08 13:36.) Napoveda "Povoleno od .. do .. mm" se u systemu 45 neukazuje, pokud limit odpovida rozsahu posuvniku; hlavni je, ze hodnota drzi a nic neoreze na 1500.
  await pg.goto(`${BASE}/${SLUG[330]}`, { waitUntil: "domcontentloaded" });
  if (await pg.waitForSelector("#catGenerator", { state: "visible", timeout: 40000 }).then(() => true).catch(() => false)) {
    f = await frameOf(); const D = ".pdc-slot[data-slot=d] .pdc-num";
    await f.locator(D).fill("2000"); await f.locator(D).blur(); await pg.waitForTimeout(5000);
    const v2000 = await f.locator(D).inputValue(), napoveda = (await f.locator(".pdc-slot[data-slot=d]").innerText()).replace(/\s+/g, " ").trim();
    await f.locator(D).fill("2500"); await f.locator(D).blur(); await pg.waitForTimeout(5000);
    const v2500 = await f.locator(D).inputValue();
    ok(v2000 === "2000" && v2500 === "2500" && !/do 1500 mm/.test(napoveda), "K13 hloubka 2000 a 2500 mm jde v generátoru systému 45 nastavit (hluboký stůl až 2500): " + v2000 + " / " + v2500 + ", nápověda „" + napoveda + "“");
  }
  // K9 karta #5353: generator misto fotky, zpet do kategorie 330
  await pg.goto(`${BASE}/produkt/pracovni-stul-system-45-konfigurovatelny`, { waitUntil: "domcontentloaded" });
  const kv = await pg.waitForSelector("#pdGeneratorFrame", { state: "attached", timeout: 40000 }).then(() => true).catch(() => false);
  ok(kv, "K9 karta „Pracovní stůl systém 45 – konfigurovatelný“: místo fotky a ceny je generátor");
  if (kv) {
    f = await frameOf("#pdGeneratorFrame");
    ok(/p=5353/.test(f.url()) && await f.locator(".pdc-sys-b[data-system='45']").getAttribute("aria-pressed") === "true", "K10 karta 5353: v iframe je generátor systému 45 (karta 5353, v přepínači zvolený systém 45)");
    const kr = (await pg.locator("#breadcrumb").innerText()).replace(/\s+/g, " ");
    ok(/Robustní balicí stůl system 45/.test(kr) && (await pg.locator("#pdBackLink").getAttribute("href")) === "/category.html?id=330", "K10b drobenka vede přes kategorii „Robustní balicí stůl system 45“ a „Zpět do kategorie“ do kategorie 330: " + kr + " | " + (await pg.locator("#pdBackLink").getAttribute("href")));
    ok(!(await pg.locator("#pdBuyRow").isVisible()) && !(await pg.locator("#pdGalleryMain").isVisible()), "K10c „Bez fotky“ a nákupní sloupec jsou nahrazené generátorem");
  }
  // K11 ostatni kategorie bez generatoru
  await pg.goto(`${BASE}/category.html?id=184`, { waitUntil: "domcontentloaded" }); await pg.waitForTimeout(4000);
  ok(!(await pg.locator("#catGenerator").isVisible().catch(() => false)), "K11 jiná kategorie (184 Vestavby) generátor nemá");
  const chyby = errs.filter(e => !/Failed to load resource/.test(e));
  ok(!chyby.length, "K12 bez JS chyb" + (chyby[0] ? " | " + chyby[0] : ""));
  await Promise.race([browser.close(), new Promise(r => setTimeout(r, 15000))]); console.log(`\n==> ${total - bad}/${total} kontrol OK`); process.exit(bad ? 1 : 0);
})().catch(e => { console.error("CHYBA TESTU", e); process.exit(2); });
