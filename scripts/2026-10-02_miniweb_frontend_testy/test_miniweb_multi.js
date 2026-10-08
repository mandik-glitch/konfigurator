// Texty uvodu SK mini-shopu podle poctu VEREJNYCH produktu (bot7 2026-10-05): 1 produkt = zakladni klic, 2+ = ".multi", 3+ = ".multi3" (prepise i ".multi"; produkty stolu 30, 40 a 35). Overuje klienta
// (miniweb-pages.js P.home: lead, USP, FAQ, pocet karet) i server-side HTML (api/miniweb_seo.py::_varianta) nad skutecnym API a daty (bridge_miniweb.py; verejnost produktu se prepina v DOCASNE kopii pres
// /__bridge/approve?products=1,2,3, ostre tabulky se nemeni). Spusteni: viz bridge_miniweb.py.
const { chromium } = require("/opt/konfigurator/node_modules/playwright");
const fs = require("fs"), path = require("path");
const BASE = process.env.BASE;
const DICT = JSON.parse(fs.readFileSync(path.join(process.env.WEB_OVERRIDE || "/opt/konfigurator/webapp", "miniweb/i18n/sk.json"), "utf8"));
let bad = 0, total = 0; const ok = (c, t) => { total++; if (!c) bad++; console.log(`[${c ? "OK   " : "CHYBA"}] ${t}`); };
const unesc = (s) => String(s).replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&quot;/g, '"').replace(/&#x27;|&#39;/g, "'").replace(/&nbsp;/g, " ").replace(/&amp;/g, "&");
const norm = (s) => String(s).replace(/\s+/g, " ").trim();
(async () => {
  const browser = await chromium.launch(); const ctx = await browser.newContext({ viewport: { width: 1300, height: 900 } }); const errs = [];
  await ctx.route(/pripni-cokoli/, r => r.abort());
  const page = await ctx.newPage(); page.on("pageerror", e => errs.push(e.message));
  for (const [ids, suffix, nazev] of [["1", "", "jeden veřejný produkt (základní klíče)"], ["1,2", ".multi", "dva veřejné produkty (.multi)"], ["1,2,3", ".multi3", "tři veřejné produkty (.multi3 přepíše .multi)"]]) {
    await fetch(`${BASE}/__bridge/approve?products=${ids}`);
    const n = ids.split(",").length;
    const exp = { lead: DICT["home.lead" + suffix], usp: DICT["home.usp2.d" + suffix], faqQ: DICT["faq.2.q" + suffix] };
    if (!exp.lead || !exp.usp || !exp.faqQ) { ok(false, nazev + ": v sk.json chybí klíče varianty " + (suffix || "(základ)")); continue; }
    await page.goto(`${BASE}/miniweb/index.html`); await page.waitForSelector(".mw-card, .mw-hero", { timeout: 30000 }); await page.waitForTimeout(500);
    const cards = await page.locator(".mw-card").count();
    const lead = norm(await page.locator(".mw-hero .mw-lead").innerText()), usp = norm(await page.locator(".mw-usp").innerText()), faq = norm(await page.locator("#faq").innerText());
    ok(cards === n, "M" + n + "a " + nazev + ": na domovské stránce " + cards + " karet");
    ok(lead === norm(exp.lead) && usp.includes(norm(exp.usp)) && faq.includes(norm(exp.faqQ)), "M" + n + "b klient: lead, USP i otázka FAQ 2 odpovídají variantě " + (suffix || "základ") + ": " + lead.slice(0, 70));
    const html = unesc(await (await fetch(`${BASE}/api/miniweb/seo/`)).text());
    ok(norm(html).includes(norm(exp.lead)) && norm(html).includes(norm(exp.usp)) && norm(html).includes(norm(exp.faqQ)), "M" + n + "c server-side HTML (miniweb_seo): lead, USP i FAQ 2 odpovídají variantě " + (suffix || "základ"));
    if (n === 3) ok(!norm(html).includes(norm(DICT["home.lead.multi"])) && !lead.includes(norm(DICT["home.lead.multi"])), "M3d při třech produktech se nepoužije text pro dva (.multi)");
  }
  ok(!errs.length, "X bez JS chyb" + (errs[0] ? " | " + errs[0] : ""));
  await browser.close(); console.log(`\n==> ${total - bad}/${total} kontrol OK`); process.exit(bad ? 1 : 0);
})();
