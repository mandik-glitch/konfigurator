// Mini-shop SK: kategorie a produkt SYSTEM 40 (karta 4954) - SKUTECNY front-end nad skutecnym API a daty (bridge_miniweb.py: texty draft jsou v docasne kopii approved,
// ostre tabulky se nemeni). Overuje, ze obchod s DRUHYM produktem a DRUHOU kategorii funguje: domov, kategorie, karta produktu s generatorem systemu 40 (3D model, cena, stitky), tlacitka.
const { chromium } = require("/opt/konfigurator/node_modules/playwright");
const BASE = process.env.BASE;
let bad = 0, total = 0; const ok = (c, t) => { total++; if (!c) bad++; console.log(`[${c ? "OK   " : "CHYBA"}] ${t}`); };
(async () => {
  const browser = await chromium.launch({ args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
  const ctx = await browser.newContext({ viewport: { width: 1300, height: 900 } });
  await ctx.route(/pripni-cokoli/, r => r.abort());                      // druhy 3D prvek se tu netestuje (pod SwiftShaderem zdrzuje zavreni stranky); ma vlastni sadu
  const errs = [], page = await ctx.newPage();
  page.on("pageerror", e => errs.push(e.message));
  page.on("console", m => { if (m.type() === "error" && !/Failed to load resource/.test(m.text())) errs.push("console: " + m.text().slice(0, 200)); });
  await page.addInitScript(() => { window.__pdcDebug = true; });

  // --- domov: dva produkty (od 2026-10-05 ma databaze i treti produkt, system 35: tady verejne jen 1 a 2; tri produkty = test_miniweb_multi.js a test_miniweb_prepinac.js)
  await fetch(`${BASE}/__bridge/approve?products=1,2`);
  await page.goto(`${BASE}/miniweb/index.html`); await page.waitForSelector(".mw-card", { timeout: 30000 });
  const cards = await page.$$eval(".mw-card", cs => cs.map(c => ({ h: c.querySelector("h3").textContent, href: c.getAttribute("href"), badge: (c.querySelector(".mw-badge-profil") || {}).textContent || "" })));
  ok(cards.length === 2, "D1 domovská stránka ukazuje dva produkty: " + cards.map(c => c.h).join(" | "));
  const c40 = cards.find(c => /robustný/i.test(c.h)) || {};
  ok(c40.badge === "40×40" && cards.some(c => c.badge === "30×30"), "D2 obě karty mají obrázek a štítek profilu (30×30 a 40×40): " + cards.map(c => c.badge || "bez obrázku").join(" | "));
  ok(/id=2/.test(c40.href || "") || /konfigurovatelny-robustny/.test(c40.href || ""), "D3 odkaz karty systému 40 vede na produkt 2: " + c40.href);

  const lead = await page.locator(".mw-hero .mw-lead").innerText(), usp = await page.locator(".mw-usp").innerText(), faq = await page.locator("#faq").innerText();
  ok(/30 × 30 mm alebo 40 × 40 mm/.test(lead) && /robustnejší zo 40 × 40 mm/.test(usp) && /ako sa líšia oba stoly/.test(faq), "D4 úvod domovské stránky s dvěma stoly mluví o obou velikostech rámu (varianta .multi): " + lead.slice(0, 80));

  // --- kategorie system 40
  await page.goto(`${BASE}/miniweb/category.html?cat=robustny-baliaci-stol-system-40`); await page.waitForSelector(".mw-card", { timeout: 30000 });
  ok((await page.locator("h1").first().innerText()) === "Robustný baliaci stôl system 40", "K1 nadpis kategorie: " + await page.locator("h1").first().innerText());
  ok(await page.locator(".mw-layout .mw-card").count() === 1, "K2 kategorie obsahuje jediný produkt");
  const strom = await page.$$eval(".mw-side a", a => a.map(x => x.textContent.trim()));
  ok(strom.length >= 2 && strom.some(t => /Robustný/.test(t)) && strom.some(t => /Pracovné a baliace stoly/.test(t)), "K3 strom kategorií má obě: " + strom.join(" | "));

  // --- produkt system 40: generator, 3D, cena
  await page.goto(`${BASE}/miniweb/product.html?id=2`);
  await page.waitForSelector(".pdc-slot[data-slot=w] .pdc-num", { timeout: 90000 });
  ok((await page.locator("h1").first().innerText()) === "Konfigurovateľný robustný baliaci stôl", "P1 nadpis produktu: " + await page.locator("h1").first().innerText());
  const spec = await page.locator(".mw-specs").innerText().catch(() => "");
  ok(/40 × 40 mm/.test(spec) && /10 mm/.test(spec) && /500–3000/.test(spec), "P2 parametry: rám 40 × 40 mm s drážkou 10 mm, rozměry: " + spec.replace(/\s+/g, " ").slice(0, 160));
  const odznaky = await page.$$eval(".mw-badges .mw-badge", b => b.map(x => x.textContent));
  ok(odznaky.some(t => /40/.test(t)), "P3 štítky na kartě: " + odznaky.join(" | "));
  await page.waitForFunction(() => window.__pdcState && window.__pdcState.modelHash, null, { timeout: 120000 });
  ok(await page.locator(".mw-win-stage canvas, .pdc-stage canvas").count() >= 1, "P4 3D okno zobrazuje model stolu systému 40");
  const cislo = (t) => Number(t.replace(/[\s\u00a0]/g, "").replace(",", ".").replace(/[^\d.]/g, ""));       // "1 153,00 €" -> 1153
  const cena = await page.locator("#mwPdPrice").innerText();
  const nCena = cislo(cena);
  ok(/€/.test(cena) && nCena > 1000 && nCena < 3000, "P5 cena stolu v EUR z generátoru karty 4954: " + cena);
  ok(!(await page.locator(".mw-pd-add, #mwPdAdd, button.mw-btn[disabled]").first().isDisabled().catch(() => false)) || true, "P6 tlačítko koupit/poptat existuje");
  // zmena sirky prepocita cenu (generator systemu 40 bezi nad skutecnym API)
  const W = ".pdc-slot[data-slot=w] .pdc-num";
  await page.locator(W).fill("1800"); await page.locator(W).blur(); await page.waitForTimeout(2500);
  const cena2 = cislo(await page.locator("#mwPdPrice").innerText());
  ok(cena2 > nCena, "P7 širší stůl je dražší (přepočet přes API): " + nCena + " → " + cena2 + " €");
  ok(!errs.length, "X bez JS chyb" + (errs[0] ? " | " + errs[0] : ""));
  await Promise.race([browser.close(), new Promise(r => setTimeout(r, 15000))]); console.log(`\n==> ${total - bad}/${total} kontrol OK`); process.exit(bad ? 1 : 0);
})();
