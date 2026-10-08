// Ceska verze mini-shopu Packstations nad SKUTECNYM konfiguratorem stolu (bot8, api/stul_shop.py) - viz bridge.py.
// Spusteni: systemd-run ... api/venv/bin/python3 scripts/2026-10-02_miniweb_frontend_testy/bridge.py scripts/2026-10-02_miniweb_frontend_testy/test_cs_konfigurator.js
const fs = require("fs"), path = require("path");
const { chromium } = require("/opt/konfigurator/node_modules/playwright");
const BASE = process.env.BASE, PID = process.env.PID || "9001";
const SHOTS = process.env.SHOTS || "/tmp";
const ENGLISH = /\b(Cart|Add to|Configuration price|Reset to default|Summary|Worktop|Shop|Contact|Inquiry|excl\.|Loading|Quantity)\b/;
const BRAND = /logiman|vandrawee|logi\s*(?:<[^>]*>\s*)*man\b/i;
let bad = 0, total = 0;
const ok = (c, t) => { total++; if (!c) bad++; console.log(`[${c ? "OK   " : "CHYBA"}] ${t}`); };
const num = s => Number(String(s).replace(/[\s\u00a0]/g, "").replace(/[^\d,.-]/g, "").replace(",", "."));
const norm = s => String(s).replace(/\s+/g, " ").trim();

(async () => {
  const browser = await chromium.launch({ args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 }, locale: "cs-CZ" });
  // Pripni cokoli (druhy 3D prvek, od 2026-10-04 na zivo) tu nezkousime: pod programovym vykreslovanim (SwiftShader) zdrzuje opusteni stranky; testy se ho netykaji (ma vlastni sadu)
  await ctx.route(/pripni-cokoli/, r => r.abort());
  const page = await ctx.newPage(); const errs = [], reqs = [];
  page.on("pageerror", e => errs.push(e.message));
  page.on("console", m => { if (m.type() === "error" && !/Failed to load resource/.test(m.text())) errs.push("console: " + m.text().slice(0, 200)); });
  page.on("request", r => reqs.push(new URL(r.url()).pathname));
  // ladici hook vieweru zakazan: znacka musi fungovat pres oficialni API kamery (viewer 1.6.0 cameraInfo/onCamera)
  await page.addInitScript(() => { Object.defineProperty(window, "__v3d", { configurable: true, get() { return undefined; }, set() { } }); });
  await page.route("**/miniweb/config.cs.json", async (route) => { const r = await route.fetch(); const j = await r.json(); j.configurator_product_id = Number(PID); await route.fulfill({ response: r, json: j }); });

  await page.goto(`${BASE}/miniweb/index.html?shop=packstations&lang=cs&demo=1`);
  await page.waitForSelector(".mw-hero h1");
  const home = await page.locator("body").innerText();
  ok(await page.evaluate(() => document.documentElement.lang) === "cs" && norm(await page.locator(".mw-hero h1").innerText()) === "Navrhněte si vlastní balicí stůl", "H1 úvod česky, <html lang=cs>");
  ok(!ENGLISH.test(home) && !BRAND.test(home), "H2 úvod bez angličtiny a bez značky");
  ok(norm(await page.locator(".mw-card .mw-price").innerText()) === "Cena podle konfigurace", "H3 karta v seznamu: ‚Cena podle konfigurace‘ (cena až v konfigurátoru)");
  ok(norm(await page.locator(".mw-cart").innerText()).startsWith("Poptávka"), "H4 hlavička: ‚Poptávka‘ (inquiry_only)");

  await page.locator(".mw-card").click();
  await page.waitForSelector(".pdc-panel:not([hidden])", { timeout: 30000 });
  await page.waitForSelector(".pdc-stage .v3d-root canvas", { timeout: 60000 }).catch(() => {});
  await page.waitForFunction(() => /\d/.test(document.getElementById("mwPdPrice").textContent), null, { timeout: 30000 });
  await page.waitForTimeout(1500);
  const price = async () => num(await page.locator("#mwPdPrice").innerText());
  const waitPriceChange = async (from) => { await page.waitForFunction(([id, f]) => { const n = Number(document.getElementById(id).textContent.replace(/[\s\u00a0]/g, "").replace(/[^\d,.-]/g, "").replace(",", ".")); return n && n !== f; }, ["mwPdPrice", from], { timeout: 20000 }).catch(() => {}); };
  const settle = async () => { let last = null, same = 0; for (let i = 0; i < 60 && same < 4; i++) { const t = await page.locator("#mwPdPrice").innerText(); if (t === last) same++; else { same = 0; last = t; } await page.waitForTimeout(400); } };       // po startu a po "Zpet na vychozi" se vzpery zapnou SAMY (auto_on) = druhy vypocet; cenu cist az po ustaleni
  await settle();
  const P0 = await price();
  const pt = await page.evaluate(() => { const c = document.body.cloneNode(true); c.querySelectorAll(".v3d-root").forEach(n => n.remove()); return c.innerText; });
  ok(/Kč/.test(await page.locator("#mwPdPrice").innerText()) && P0 > 1000, "P1 cena základní konfigurace ze skutečného ceníku: " + norm(await page.locator("#mwPdPrice").innerText()));
  ok(!ENGLISH.test(pt) && !BRAND.test(pt), "P2 celá karta včetně panelu konfigurátoru česky a bez značky" + (ENGLISH.test(pt) ? " | " + pt.match(ENGLISH)[0] : ""));
  ok(norm(await page.locator(".mw-buy-price").innerText()).includes("bez DPH"), "P3 cena je ‚bez DPH‘");
  ok(await page.locator(".pdc-stage .v3d-root canvas").count() === 1, "P4 3D model stolu (skládaný serverem, podepsaný odkaz) se načetl do prohlížeče");
  const hud = await page.evaluate(() => (document.querySelector(".v3d-root") || { innerText: "" }).innerText);
  ok(/Zepředu/.test(hud) && !/\bFront\b/.test(hud), "P5 HUD prohlížeče česky (výchozí texty vieweru)");
  ok(await page.locator(".pdc-slot[data-slot=w] .pdc-num").count() === 1 && await page.locator(".pdc-slot[data-slot=led] input[type=checkbox]").count() === 1, "P6 panel: slidery rozměrů a přepínače příslušenství ze schématu serveru");
  ok(await page.locator(".pdc-slot[data-slot=mid]").isHidden(), "Z1 zamčený posuvník (střední noha u stolu do 1500 mm: min = max) se neukazuje");
  ok(await page.locator(".pdc-slot[data-slot=cut1w]").count() === 1 && await page.locator(".pdc-slot[data-slot=cut1w]").isHidden(), "Z2 rozměry výřezu 1 jsou skryté, dokud je výřez vypnutý");
  await page.evaluate(() => { const w = document.querySelector(".mw-win-adv"); if (w && w.classList.contains("is-closed")) w.querySelector(".mw-win-fold").click(); });   // okno Výřezy a ložiska je ve výchozím stavu sbalené
  await page.locator(".pdc-slot[data-slot=cut1] input[type=checkbox]").check({ force: true });
  await page.waitForFunction(() => { const e = document.querySelector(".pdc-slot[data-slot=cut1w]"); return e && !e.hidden; }, null, { timeout: 15000 }).catch(() => {});
  ok(await page.locator(".pdc-slot[data-slot=cut1w]").isVisible(), "Z3 po zapnutí výřezu 1 se objeví jeho posuvníky (šířka…)");
  const dts = async () => (await page.locator(".pdc-summary dt").allInnerTexts()).join(" | ");
  ok(await page.locator(".pdc-slot[data-slot=cut2]").isVisible() && await page.locator(".pdc-slot[data-slot=cut2w]").isHidden() && await page.locator(".pdc-slot[data-slot=cut3]").isHidden(), "Z4 při zapnutém výřezu 1 je vidět volba Výřez 2, ale ne jeho rozměry ani Výřez 3");
  ok(/výřezu 1/i.test(await dts()) && !/výřezu [23]|Výřez 3|pod výřezem [23]/i.test(await dts()), "Z5 shrnutí ukazuje rozměry výřezu 1 (je zapnutý), rozměry výřezu 2 a 3 ne: " + await dts().then(t => t.match(/[^|]*výřez[^|]*/gi)));
  await page.locator(".pdc-slot[data-slot=cut1] input[type=checkbox]").uncheck({ force: true }); await page.waitForTimeout(1500);
  ok(await page.locator(".pdc-slot[data-slot=cut2]").isHidden() && await page.locator(".pdc-slot[data-slot=cut1shelf]").isHidden() && await page.locator(".pdc-slot[data-slot=cut1w]").isHidden(), "Z6 bez výřezu 1: ani Výřez 2, ani police a rozměry výřezu 1 se neukazují");
  ok(!/výřezu|Výřez 2|Výřez 3|pod výřezem/i.test(await dts()), "Z7 shrnutí bez výřezu 1 neobsahuje žádné informace o výřezech (jen případně řádek Výřez 1: ne): " + await dts().then(t => t.match(/[^|]*výřez[^|]*/gi)));
  ok(!reqs.some(r => /scene\.html|\/api\/stul\//.test(r)) && reqs.some(r => /\/api\/shop\/configurator\/glb\//.test(r)), "P7 model jde přes veřejný podepsaný odkaz (ne scéna, ne staff routa)");

  await page.locator(".pdc-slot[data-slot=w] .pdc-num").fill("1800"); await page.locator(".pdc-slot[data-slot=w] .pdc-num").dispatchEvent("change");
  await waitPriceChange(P0); const P1 = await price();
  ok(P1 > P0, "P8 šířka 1800 mm zdraží: " + P0 + " → " + P1 + " Kč");
  await page.locator(".pdc-slot[data-slot=mid]").waitFor({ state: "visible", timeout: 20000 }).catch(() => {});       // slot se ukaze az s odpovedi serveru (options.mid 9–91 %)
  ok(await page.locator(".pdc-slot[data-slot=mid]").isVisible() && /1500|střední/i.test(await page.locator(".pdc-slot[data-slot=mid]").innerText()), "P9 nad 1500 mm je vidět volba střední nohy (nápověda z pravidel)");
  // --- tazeni stredni nohy v 3D
  await page.evaluate(() => window.scrollTo(0, 0)); await page.waitForTimeout(300);   // v mřížce oken je 3D nahoře a volby pod ním: po práci s volbami se vrátit k modelu
  // Stredni noha: jen obecne male ikony ve 3D z popisu ovladani (tah "mid", v3d-ovladani.js); vlastni velky uchyt .pdc-handle byl 2026-10-04 smazan
  await page.waitForTimeout(2500);
  const hbN = await page.evaluate(() => { const h = document.querySelector('.pdc-ov .v3do-h[data-tah="mid"]'), r = h.getBoundingClientRect(), s = document.querySelector(".pdc-stage").getBoundingClientRect(); return { x: r.x + r.width / 2, y: r.y + r.height / 2, in: r.x > s.x && r.x < s.x + s.width && r.y > s.y && r.y < s.y + s.height }; });
  ok(hbN.in && await page.locator(".pdc-handle").count() === 0, "D1 střední noha: malá ikona z popisu ovládání je uvnitř 3D okna a starý velký úchyt už neexistuje");
  const midA = Number(await page.locator(".pdc-slot[data-slot=mid] .pdc-num").inputValue());
  await page.mouse.move(hbN.x, hbN.y); await page.mouse.down();
  for (let i = 1; i <= 10; i++) await page.mouse.move(hbN.x + i * 10, hbN.y, { steps: 2 });
  await page.waitForTimeout(400);
  const tipTxt = await page.evaluate(() => [...document.querySelectorAll(".pdc-ov .v3do-lbl, .pdc-ov .v3do-tip")].filter(l => getComputedStyle(l).display !== "none").map(l => l.textContent).join(" / "));
  await page.mouse.up(); await page.waitForTimeout(2500);
  const midB = Number(await page.locator(".pdc-slot[data-slot=mid] .pdc-num").inputValue());
  ok(/od levé nohy/.test(tipTxt), "D2 při tažení štítek ve 3D ukazuje mm od levé nohy: " + tipTxt.replace(/\s+/g, " ").slice(0, 100));
  ok(midB !== midA, "D3 tažení ikony střední nohy posune slot mid (" + midA + " → " + midB + " %)");
  await waitPriceChange(0).catch(() => {});
  const led = page.locator(".pdc-slot[data-slot=led] input[type=checkbox]");
  await page.waitForTimeout(3500); const P1b = await price();   // po rozšíření na 1800 mm se vzpěry zapnou samy (auto_on) a cena se ještě změní: porovnávat až s ustálenou
  await led.uncheck({ force: true }); await waitPriceChange(P1b); const P2 = await price();
  ok(P2 < P1b, "P10 vypnutí LED osvětlení zlevní: " + P1b + " → " + P2 + " Kč");
  await page.locator(".pdc-head .pdc-link").click(); await waitPriceChange(P2); await settle();
  ok(await price() === P0, "P11 ‚Zpět na výchozí‘ vrátí původní cenu " + P0);
  await page.locator(".pdc-slot[data-slot=w] .pdc-num").fill("1800"); await page.locator(".pdc-slot[data-slot=w] .pdc-num").dispatchEvent("change"); await waitPriceChange(P0); await page.waitForTimeout(800);
  await page.screenshot({ path: path.join(SHOTS, "cs_product_desktop.png"), fullPage: true });
  ok(norm(await page.locator("#mwAdd").innerText()).toLowerCase() === "přidat do poptávky", "P12 tlačítko ‚Přidat do poptávky‘");
  await page.locator("#mwAdd").click();
  ok(norm(await page.locator("#mwPdMsg").innerText()) === "Přidáno do poptávky." && await page.locator("#mwCartCount").innerText() === "1", "P13 přidání do poptávky");

  await page.locator(".mw-cart").click(); await page.waitForSelector("#mwInquiry");
  const ct = await page.locator("body").innerText();
  ok(/Šířka desky|1800/.test(ct) && !ENGLISH.test(ct), "C1 poptávka obsahuje souhrn konfigurace česky");
  ok(await page.locator("#mwInquiry select[name=country] option").count() === 2, "C2 země: Česko, Slovensko; věta jen pro podnikatele u formuláře");
  await page.locator("#mwInquiry [name=name]").fill("Jan"); await page.locator("#mwInquiry [name=email]").fill("jan@example.test");
  await page.locator("#mwInquiry [name=company]").fill("Test s.r.o."); await page.locator("#mwInquiry [name=company_id]").fill("12345678");
  await page.locator("#mwInquiry [name=b2b_confirm]").check(); await page.locator("#mwInquiry [name=consent]").check();
  await page.locator("#mwInquiry button[type=submit]").click();
  ok(norm(await page.locator("#mwInqMsg").innerText()) === "Ukázka: poptávka se neodeslala.", "C3 náhled: poptávka se nikam neodesílá");
  ok(!errs.length, "E1 bez JS chyb a chyb konzole" + (errs.length ? " | " + errs.slice(0, 3).join(" || ") : ""));

  // --- automaticke odebrani nevejdouciho se prislusenstvi, navrh rozsireni stolu, nabidky odebrani po kolizi (API 2026-10-02.5)
  const p2 = await ctx.newPage(); const e2 = [];
  p2.on("pageerror", e => e2.push(e.message));
  await p2.route("**/miniweb/config.cs.json", async (route) => { const r = await route.fetch(); const j = await r.json(); j.configurator_product_id = Number(PID); await route.fulfill({ response: r, json: j }); });
  await p2.goto(`${BASE}/miniweb/product.html?shop=packstations&lang=cs&demo=1&id=9001`);
  await p2.waitForSelector(".pdc-panel:not([hidden])", { timeout: 30000 });
  const pr2 = async () => num(await p2.locator("#mwPdPrice").innerText());
  await p2.waitForFunction(() => /\d/.test(document.getElementById("mwPdPrice").textContent), null, { timeout: 30000 });
  const Q0 = await pr2();
  const setNum = async (slot, v) => { const i = p2.locator(`.pdc-slot[data-slot=${slot}] .pdc-num`); await i.fill(String(v)); await i.dispatchEvent("change"); };
  await setNum("w", 700);
  await p2.waitForFunction(() => document.querySelectorAll(".pdc-notice-item").length >= 3, null, { timeout: 20000 }).catch(() => {});
  const items = await p2.locator(".pdc-notice-item").allInnerTexts();
  ok(items.length >= 3 && items.every(t => t.startsWith("Automaticky odebráno")), "A1 šířka 700 mm: server sám odebral nevejdoucí příslušenství a UI to oznámilo (" + items.length + " oznámení)");
  ok(!(await p2.locator(".pdc-slot[data-slot=led] input[type=checkbox]").isChecked()) && !(await p2.locator(".pdc-slot[data-slot=panels] input[type=checkbox]").isChecked()), "A2 přepínače LED a panely jsou po odebrání vypnuté (efektivní výběr ze serveru)");
  ok(await pr2() < Q0, "A3 cena po odebrání příslušenství klesla: " + Q0 + " → " + await pr2() + " Kč");
  const sug = p2.locator(".pdc-slot[data-slot=led] .pdc-suggest-btn");
  ok(await sug.isVisible() && /Roztáhnout stůl na šířku \d+ mm a zapnout/.test(await sug.innerText()), "A4 u zakázané LED je návrh: ‚" + norm(await sug.innerText().catch(() => "")) + "‘");
  await sug.click();
  await p2.waitForFunction(() => Number(document.querySelector(".pdc-slot[data-slot=w] .pdc-num").value) >= 1200, null, { timeout: 20000 }).catch(() => {});
  await p2.waitForTimeout(800);
  ok(Number(await p2.locator(".pdc-slot[data-slot=w] .pdc-num").inputValue()) >= 1200 && await p2.locator(".pdc-slot[data-slot=led] input[type=checkbox]").isChecked(), "A5 klik na návrh roztáhne stůl a zapne LED (šířka " + await p2.locator(".pdc-slot[data-slot=w] .pdc-num").inputValue() + " mm)");
  await setNum("w", 1800); await p2.waitForTimeout(1200);
  // Server (bot8 2026-10-03) už kolize sám řeší automatickým odebráním a přesnými mezemi, takže "nabídka odebrat" by se z živých dat nevyvolala:
  // chování UI na offers[] se ověřuje na podstrčené odpovědi (šířka 1800 + šuplíky → valid:false s nabídkou; po odebrání šuplíků jde odpověď ze serveru beze změny)
  await p2.route("**/api/shop/configurator/resolve", async (route) => {
    let b = {}; try { b = JSON.parse(route.request().postData() || "{}"); } catch (e) { /* nic */ }
    const sel = b.selection || {}, r = await route.fetch();
    if (sel.w === 1800 && sel.drawers) {
      const j = await r.json(); j.valid = false;
      j.offers = [{ action: "remove", slot: "drawers", label: "Odebrat šuplíky", message: "Šuplíky se při těchto rozměrech nevejdou." }];
      j.errors = [{ slot: "drawers", message: "Šuplíky se při těchto rozměrech nevejdou." }];
      return route.fulfill({ response: r, json: j });
    }
    return route.fulfill({ response: r });
  });
  await setNum("w", 1600); await p2.waitForTimeout(1500); await setNum("w", 1800); await p2.waitForTimeout(1800);
  const offer = p2.locator(".pdc-offer-btn", { hasText: "Odebrat šuplíky" });
  await offer.first().waitFor({ timeout: 20000 }).catch(() => {});                 // odpoved na w=1800 muze pri zatizeni serveru trvat dele nez pevne cekani
  const hadOffer = await offer.count();
  ok(hadOffer === 1 && !(await p2.locator("#mwAdd").isEnabled()), "A6 kolize po posunu šuplíků: nabídka ‚Odebrat šuplíky‘ a tlačítko do poptávky je zakázané");
  if (hadOffer) { await offer.click(); await p2.waitForFunction(() => document.querySelector("#mwAdd") && !document.querySelector("#mwAdd").disabled, null, { timeout: 20000 }).catch(() => {}); }
  ok(!(await p2.locator(".pdc-slot[data-slot=drawers] input[type=checkbox]").isChecked()) && await p2.locator("#mwAdd").isEnabled(), "A7 po kliknutí se šuplíky odeberou a konfigurace je zase platná");
  ok(!e2.length, "A8 bez JS chyb" + (e2.length ? " | " + e2.join("||") : ""));
  await p2.screenshot({ path: path.join(SHOTS, "cs_notices.png") });

  const m = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, deviceScaleFactor: 2, locale: "cs-CZ" });
  await m.route(/pripni-cokoli/, r => r.abort());
  const mp = await m.newPage();
  await mp.route("**/miniweb/config.cs.json", async (route) => { const r = await route.fetch(); const j = await r.json(); j.configurator_product_id = Number(PID); await route.fulfill({ response: r, json: j }); });
  await mp.goto(`${BASE}/miniweb/product.html?shop=packstations&lang=cs&demo=1&id=9001`);
  await mp.waitForSelector(".pdc-panel:not([hidden])", { timeout: 30000 }); await mp.waitForSelector(".pdc-stage .v3d-root canvas", { timeout: 60000 }).catch(() => {}); await mp.waitForTimeout(1200);
  ok(await mp.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth), "M1 mobil 390 px: bez vodorovného posunu");
  const hudOk = await mp.evaluate(() => { const cv = document.querySelector(".pdc-stage .v3d-root canvas").getBoundingClientRect(); const bs = [...document.querySelectorAll(".v3d-root button")].filter(b => b.offsetParent && !b.classList.contains("v3d-chip")); return { n: bs.length, over: bs.filter(b => { const r = b.getBoundingClientRect(); return r.bottom > cv.top + 1 && r.top < cv.bottom - 1; }).length }; });
  ok(hudOk.n > 3 && hudOk.over === 0, "M2 mobil: tlačítka HUD vieweru (bez čipů pohyblivých dílů, ty leží nad plátnem ze záměru) jsou v pruhu nad plátnem (hudDock top), nezakrývají model (" + hudOk.n + " tlačítek, " + hudOk.over + " přes plátno)");
  await mp.locator(".pdc-slot[data-slot=w] .pdc-num").fill("1800"); await mp.locator(".pdc-slot[data-slot=w] .pdc-num").dispatchEvent("change");
  await mp.waitForTimeout(3000);
  const mobHandles = await mp.evaluate(() => {                                   // vlastni uchyt stredni nohy (stary server) nebo obecne male ikony z popisu ovladani (novy server)
    const cv = document.querySelector(".pdc-stage .v3d-root canvas").getBoundingClientRect();
    const hs = [...document.querySelectorAll(".pdc-ov .v3do-h")].filter(h => getComputedStyle(h).display !== "none");
    return { n: hs.length, outside: hs.filter(h => { const r = h.getBoundingClientRect(); return r.x < cv.x - 5 || r.x + r.width > cv.x + cv.width + 5 || r.y < cv.y - 5 || r.y + r.height > cv.y + cv.height + 5; }).length };
  });
  ok(mobHandles.n >= 1 && mobHandles.outside === 0, "M3 mobil: úchyty ve 3D (" + mobHandles.n + ") jsou celé uvnitř plátna s dokovaným HUD");
  await mp.screenshot({ path: path.join(SHOTS, "cs_product_mobile.png") });
  await browser.close();
  console.log(`\n==> ${total - bad}/${total} kontrol OK`);
  process.exit(bad ? 1 : 0);
})();
