// Karta konfigurovatelneho stolu s GENERATOREM primo na strance (Robert 2026-10-05: "dokonceni karty stolu pro generator 40"): /produkt/pracovni-stul-system-40-konfigurovatelny a
// /produkt/pracovni-stul-system-30-konfigurovatelny. Nad skutecnymi daty karet 4934 / 4954 (bridge.py s BRIDGE_CARDS=real: schema.systems = skutecne karty; DB se jen cte) a kandidatni
// nebo zivou statikou. Overuje: misto "Bez fotky / Cena na dotaz" je generator ve 3D, drobenka a "Zpet do kategorie" vedou do kategorie 311 / 206 (karta nema category_id),
// prepinac systemu prejde na kartu druheho systemu a vezme vyber, bezny produkt zustava beze zmeny.
const { chromium } = require("/opt/konfigurator/node_modules/playwright");
const BASE = process.env.BASE;
let bad = 0, total = 0; const ok = (c, t) => { total++; if (!c) bad++; console.log(`[${c ? "OK   " : "CHYBA"}] ${t}`); };
const W = ".pdc-slot[data-slot=w] .pdc-num";
const S40 = "/produkt/pracovni-stul-system-40-konfigurovatelny", S30 = "/produkt/pracovni-stul-system-30-konfigurovatelny";
(async () => {
  const browser = await chromium.launch({ args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
  const ctx = await browser.newContext({ viewport: { width: 1400, height: 1100 } }); const errs = [];
  const pg = await ctx.newPage(); pg.on("pageerror", e => errs.push(e.message));
  const frameOf = async () => {
    const h = await pg.waitForSelector("#pdGeneratorFrame", { state: "attached", timeout: 60000 }); const f = await h.contentFrame();
    await f.locator(W).waitFor({ timeout: 120000 }); await f.locator(".emb-order-btn:not([disabled])").waitFor({ timeout: 120000 }); return f;
  };
  await pg.goto(BASE + S40, { waitUntil: "domcontentloaded" });
  let f = await frameOf();
  ok(/p=4954/.test(f.url()) && await f.locator(".pdc-sys-b").count() === 3, "K1 karta systému 40: na stránce je generátor (karta 4954) s přepínačem tří systémů");
  ok(!(await pg.locator("#pdBuyRow").isVisible()) && !(await pg.locator("#pdGalleryMain").isVisible()), "K2 „Bez fotky“ a „Cena na dotaz“ (nákupní sloupec) jsou nahrazené generátorem");
  const kr = (await pg.locator("#breadcrumb").innerText()).replace(/\s+/g, " ");
  ok(/Robustní balicí stůl system 40/.test(kr), "K3 drobenka vede přes kategorii „Robustní balicí stůl system 40“: " + kr);
  ok((await pg.locator("#pdBackLink").getAttribute("href")) === "/category.html?id=311", "K4 „Zpět do kategorie“ vede do kategorie 311: " + await pg.locator("#pdBackLink").getAttribute("href"));
  ok((await pg.locator("#pdTitle").innerText()).includes("systém 40"), "K5 nadpis karty: " + await pg.locator("#pdTitle").innerText());
  ok(await pg.locator("#pdGeneratorFrame").evaluate(e => e.getBoundingClientRect().height) > 500, "K6 generátor má použitelnou výšku");

  // prepinac systemu: stejny vyber na karte druheho systemu
  await f.locator(W).fill("1700"); await f.locator(W).blur(); await pg.waitForTimeout(2500);
  await Promise.all([pg.waitForURL(/pracovni-stul-system-30-konfigurovatelny/, { timeout: 30000 }), f.locator(".pdc-sys-b[data-system='30']").click()]);
  f = await frameOf();
  ok((await pg.locator("#pdTitle").innerText()).includes("systém 30") && !/p=4954/.test(f.url()), "K7 přepínač přešel na KARTU systému 30: " + await pg.locator("#pdTitle").innerText());
  ok((await f.locator(W).inputValue()) === "1700", "K8 stejný výběr: šířka 1700 se přenesla: " + await f.locator(W).inputValue());
  ok((await pg.locator("#pdBackLink").getAttribute("href")) === "/category.html?id=206", "K9 karta systému 30 vede zpět do kategorie 206");
  await Promise.all([pg.waitForURL(/pracovni-stul-system-40-konfigurovatelny/, { timeout: 30000 }), f.locator(".pdc-sys-b[data-system='40']").click()]);
  f = await frameOf();
  ok((await f.locator(W).inputValue()) === "1700" && /p=4954/.test(f.url()), "K10 zpět na kartu systému 40, šířka 1700 zůstala");

  // treti system: karta 4955 (system 35), kategorie 312 "Ergonomicky balici stul system 35"
  await Promise.all([pg.waitForURL(/pracovni-stul-system-35-konfigurovatelny/, { timeout: 30000 }), f.locator(".pdc-sys-b[data-system='35']").click()]);
  f = await frameOf();
  ok((await pg.locator("#pdTitle").innerText()).includes("systém 35") && /p=4955/.test(f.url()), "K14 přepínač přešel na KARTU systému 35: " + await pg.locator("#pdTitle").innerText());
  ok((await f.locator(W).inputValue()) === "1700" && (await f.locator(".pdc-sys-b[data-system='35']").getAttribute("aria-pressed")) === "true", "K15 stejný výběr: šířka 1700 se přenesla na kartu systému 35");
  ok((await pg.locator("#pdBackLink").getAttribute("href")) === "/category.html?id=312", "K16 karta systému 35 vede zpět do kategorie 312: " + await pg.locator("#pdBackLink").getAttribute("href"));
  const kr35 = (await pg.locator("#breadcrumb").innerText()).replace(/\s+/g, " ");
  ok(/Ergonomický balicí stůl system 35/.test(kr35), "K17 drobenka vede přes kategorii „Ergonomický balicí stůl system 35“: " + kr35);
  await Promise.all([pg.waitForURL(/pracovni-stul-system-40-konfigurovatelny/, { timeout: 30000 }), f.locator(".pdc-sys-b[data-system='40']").click()]);
  f = await frameOf();
  ok((await f.locator(W).inputValue()) === "1700" && /p=4954/.test(f.url()), "K18 ze systému 35 rovnou na 40: šířka 1700 zůstala");

  // odkaz na ulozenou konfiguraci (?ulozena=<token>) se preda generatoru v iframe
  const pg4 = await ctx.newPage(); pg4.on("pageerror", e => errs.push(e.message));
  await pg4.goto(BASE + S40 + "?ulozena=AAAAAAAAAAAAAAAAAAAAAA", { waitUntil: "domcontentloaded" });
  const h4 = await pg4.waitForSelector("#pdGeneratorFrame", { state: "attached", timeout: 60000 });
  ok(/[?&]ulozena=AAAAAAAAAAAAAAAAAAAAAA/.test(await h4.getAttribute("src")), "K13 token z adresy karty (?ulozena=…) se předá generátoru v iframe: " + (await h4.getAttribute("src")).replace(/.*\?/, "?").slice(0, 90));
  await pg4.close();

  // bezny produkt: bez generatoru
  const pg2 = await ctx.newPage(); pg2.on("pageerror", e => errs.push(e.message));
  await pg2.goto(BASE + "/product.html?id=1", { waitUntil: "domcontentloaded" }); await pg2.waitForTimeout(6000);
  ok(await pg2.locator("#pdGeneratorFrame").count() === 0, "K11 běžný produkt (id 1) generátor nemá");
  const chyby = errs.filter(e => !/Failed to load resource/.test(e));
  ok(!chyby.length, "K12 bez JS chyb" + (chyby[0] ? " | " + chyby[0] : ""));
  await Promise.race([browser.close(), new Promise(r => setTimeout(r, 15000))]); console.log(`\n==> ${total - bad}/${total} kontrol OK`); process.exit(bad ? 1 : 0);
})();
