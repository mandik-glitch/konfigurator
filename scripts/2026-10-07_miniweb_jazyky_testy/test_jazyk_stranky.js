// Mini-shop: JAZYKOVA USPLNOST frontendu pro libovolny jazyk (sk, en, de, hu, ...) - bot16, 2026-10-07 (Robert: anglicky 1:1 se slovenskym, kopie nemecky a madarsky).
// Skutecne soubory webapp/miniweb (WEB_OVERRIDE = kandidat), skutecny viewer, jen /api/auth/me simulovano (demo rezim je pro staff). Test NEPOCITA s konkretnimi slovy, jen se
// strukturou: kazdy jazyk musi mit stejne klice jako slovensky referencni slovnik (vc. .multi/.multi3), stejne {placeholdery}, jen znaky sve abecedy a zadne holé klice na strankach.
// Spusteni: node test_jazyk_stranky.js            (vsechny jazyky s i18n/<jazyk>.json krome cs)    JAZYKY=de,hu node test_jazyk_stranky.js     REF=sk (vychozi referencni jazyk)
const fs = require("fs"), http = require("http"), path = require("path");
const { chromium } = require("/opt/konfigurator/node_modules/playwright");

const LIVE = process.env.WEB_OVERRIDE || "/opt/konfigurator/webapp";
const REF = process.env.REF || "sk";
const I18N = path.join(LIVE, "miniweb", "i18n");
const JAZYKY = (process.env.JAZYKY ? process.env.JAZYKY.split(",") : fs.readdirSync(I18N).filter(f => /^[a-z]{2}\.json$/.test(f)).map(f => f.slice(0, 2)).filter(l => l !== "cs")).filter(l => l !== REF || process.env.JAZYKY);
const MIME = { ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8", ".json": "application/json", ".glb": "model/gltf-binary", ".svg": "image/svg+xml", ".png": "image/png", ".jpg": "image/jpeg" };
const BRAND = /logiman|konfigur[áa]tor|vandrawee|logi\s*(?:<[^>]*>\s*)*man\b/i;
// povolene znaky podle jazyka (ASCII + interpunkce + typograficke znaky + vlastni abeceda); cokoli jineho = chyba (typicky cesko-slovenska diakritika v de/hu/en)
const BEZ_DIAKRITIKY = " -~\\u00A0\\u00AB\\u00BB\\u2010-\\u2027\\u2030-\\u205E\\u20AC\\u2122\\u00B0\\u00B1\\u00D7\\u00B7\\u00A9\\u00AE\\u2190-\\u21FF\\u2713\\u2715\\u00BD\\u00BC\\u2022\\u25A0-\\u25FF\\u2600-\\u27BF\\uD800-\\uDFFF";
const ABECEDA = {
  en: "", de: "\u00E4\u00F6\u00FC\u00C4\u00D6\u00DC\u00DF", hu: "\u00E1\u00E9\u00ED\u00F3\u00F6\u0151\u00FA\u00FC\u0171\u00C1\u00C9\u00CD\u00D3\u00D6\u0150\u00DA\u00DC\u0170",
  sk: "\u00E1\u00E4\u010D\u010F\u00E9\u00ED\u013E\u013A\u0148\u00F3\u00F4\u0155\u0161\u0165\u00FA\u00FD\u017E\u00C1\u00C4\u010C\u010E\u00C9\u00CD\u013D\u0139\u0147\u00D3\u00D4\u0154\u0160\u0164\u00DA\u00DD\u017D",
  cs: "\u00E1\u010D\u010F\u00E9\u011B\u00ED\u0148\u00F3\u0159\u0161\u0165\u00FA\u016F\u00FD\u017E\u00C1\u010C\u010E\u00C9\u011A\u00CD\u0147\u00D3\u0158\u0160\u0164\u00DA\u016E\u00DD\u017D",
};
const MIMO = lang => new RegExp("[^\\n\\r\\t" + BEZ_DIAKRITIKY + (ABECEDA[lang] || "") + "]");
const vysl = []; let bad = 0, total = 0;
const ok = (c, t, d) => { total++; if (!c) bad++; console.log(`[${c ? "OK   " : "CHYBA"}] ${t}${c ? "" : "  -> " + JSON.stringify(d).slice(0, 400)}`); };

const server = http.createServer((req, res) => {
  const p = decodeURIComponent(new URL(req.url, "http://x").pathname);
  if (p === "/api/auth/me") { res.writeHead(200, { "Content-Type": "application/json" }); return res.end(JSON.stringify({ user: { id: 1, email: "staff@example.test", role: "admin", name: "Staff" } })); }
  if (p.startsWith("/api/")) { res.writeHead(p === "/api/client-errors" ? 204 : 404); return res.end(); }
  const f = path.join(LIVE, p);
  if (f.startsWith(LIVE) && fs.existsSync(f) && fs.statSync(f).isFile()) { res.writeHead(200, { "Content-Type": MIME[path.extname(f)] || "application/octet-stream", "Cache-Control": "no-store" }); return fs.createReadStream(f).pipe(res); }
  res.writeHead(404); res.end("nf");
});
const nacti = f => JSON.parse(fs.readFileSync(f, "utf8"));
const placeholdery = s => (String(s).match(/\{[A-Za-z0-9_]+\}/g) || []).sort().join("");

(async () => {
  const ref = nacti(path.join(I18N, REF + ".json"));
  const files = []; (function walk(d) { fs.readdirSync(d).forEach(n => { const f = path.join(d, n); fs.statSync(f).isDirectory() ? walk(f) : files.push(f); }); })(path.join(LIVE, "miniweb"));
  const zdroj = files.filter(f => /\.(js|html)$/.test(f)).map(f => fs.readFileSync(f, "utf8")).join("\n");
  const brandHits = files.filter(f => BRAND.test(fs.readFileSync(f, "utf8"))).map(f => path.basename(f));
  ok(!brandHits.length, "S1 žádný soubor mini-shopu neobsahuje jméno značky ani rozdělené logo (" + files.length + " souborů)", brandHits);
  const htmlText = files.filter(f => f.endsWith(".html")).map(f => fs.readFileSync(f, "utf8").replace(/<script[\s\S]*?<\/script>|<style[\s\S]*?<\/style>/g, "")).join("\n");
  const hard = [...htmlText.matchAll(/>([^<>]*[A-Za-z]{2,}[^<>]*)</g)].map(m => m[1].trim()).filter(Boolean);
  ok(!hard.length, "S2 v HTML není žádný pevně zapsaný text (vše přes překladové klíče)", hard.slice(0, 3));
  console.log("== jazyky:", JAZYKY.join(", ") || "(žádné)", "| referenční:", REF);
  if (!JAZYKY.length) { console.log("žádný jazyk ke kontrole"); process.exit(bad ? 1 : 0); }

  await new Promise(r => server.listen(0, "127.0.0.1", r));
  const base = "http://127.0.0.1:" + server.address().port;
  const browser = await chromium.launch({ args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });

  for (const lang of JAZYKY) {
    console.log("==== jazyk " + lang);
    const f = path.join(I18N, lang + ".json");
    if (!fs.existsSync(f)) { ok(false, `J1 ${lang}: soubor i18n/${lang}.json existuje`, f); continue; }
    const d = nacti(f);
    const chybi = Object.keys(ref).filter(k => !(k in d)), navic = Object.keys(d).filter(k => !(k in ref));
    // klic navic je v poradku jen jako volitelna varianta (napr. home.step3.*.inquiry v en) - hlasime je, ale neselhava
    ok(!chybi.length, `J1 ${lang}: slovník má všech ${Object.keys(ref).length} klíčů referenčního ${REF}.json` + (chybi.length ? ` | chybí ${chybi.length}: ${chybi.slice(0, 12).join(", ")}` : ""), chybi.slice(0, 40));
    if (navic.length) console.log(`       (info: ${lang}.json má ${navic.length} klíčů navíc oproti ${REF}: ${navic.slice(0, 6).join(", ")})`);
    const phRozdil = Object.keys(d).filter(k => k in ref && placeholdery(d[k]) !== placeholdery(ref[k]));
    ok(!phRozdil.length, `J2 ${lang}: stejné {placeholdery} jako ${REF}.json u všech klíčů`, phRozdil.slice(0, 10).map(k => [k, ref[k], d[k]]));
    const prazdne = Object.keys(d).filter(k => typeof d[k] !== "string" || (!String(d[k]).trim() && String(ref[k] || "").trim()));       // prazdny prekladovy retezec je v poradku jen tam, kde je prazdny i v referenci
    ok(!prazdne.length, `J3 ${lang}: žádný prázdný překlad (kromě klíčů prázdných i v ${REF}.json)`, prazdne.slice(0, 10));
    const re = MIMO(lang);
    const zleZnaky = Object.entries(d).filter(([k, v]) => re.test(String(v))).map(([k, v]) => [k, (String(v).match(re) || [])[0], String(v).slice(0, 50)]);
    ok(!zleZnaky.length, `J4 ${lang}: překlady obsahují jen znaky abecedy jazyka (žádná cizí diakritika)`, zleZnaky.slice(0, 8));
    ok(!Object.values(d).some(v => BRAND.test(String(v))), `J5 ${lang}: překlady bez značky`, Object.entries(d).filter(([k, v]) => BRAND.test(String(v))).slice(0, 4));
    // pouzite klice v kodu
    const used = new Set();
    for (const m of zdroj.matchAll(/(?<![A-Za-z0-9_.])(?:MW\.)?t\(\s*["']([a-zA-Z0-9_]+\.[a-zA-Z0-9_.]*[a-zA-Z0-9_])["']/g)) used.add(m[1]);
    for (const m of zdroj.matchAll(/i18n:\s*["']([a-zA-Z0-9_.]+)["']/g)) used.add(m[1]);
    for (const m of zdroj.matchAll(/data-i18n(?:-attr)?="([^"]+)"/g)) m[1].split(";").forEach(x => used.add(x.includes(":") ? x.split(":")[1].trim() : x.trim()));
    const nenalezeno = [...used].filter(k => !/^(home\.(why|usp|extras|faq|cta2)|faq\.)/.test(k) && !/^(demo\.|pdc\.)/.test(k) && !(k in d) && !Object.keys(d).some(x => x.startsWith(k)));
    ok(!nenalezeno.length, `J6 ${lang}: každý klíč použitý v kódu existuje ve slovníku (${used.size} klíčů)`, nenalezeno.slice(0, 10));

    // ---- stranky v demo rezimu s timto jazykem (config.<lang>.json a demo.<lang>.json se, kdyz chybi, dodaji z anglickych/vychozich)
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 }, locale: lang });
    await ctx.route(/pripni-cokoli/, r => r.abort());
    await ctx.route(new RegExp(`/miniweb/config\\.${lang}\\.json`), async r => {
      const real = path.join(LIVE, "miniweb", `config.${lang}.json`);
      const j = fs.existsSync(real) ? nacti(real) : Object.assign(nacti(path.join(LIVE, "miniweb", "config.json")), { lang, locale: lang + "-" + lang.toUpperCase() });
      await r.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(j) });
    });
    const errs = [];
    const page = await ctx.newPage();
    page.on("pageerror", e => errs.push(e.message));
    page.on("console", m => { if (m.type() === "error" && !/Failed to load resource/.test(m.text())) errs.push("console: " + m.text().slice(0, 140)); });
    const holyKlic = /^[a-z][a-z0-9_]*(\.[a-z0-9_]+)+$/;
    for (const [nazev, url, sel] of [["domů", "/miniweb/index.html?demo=1&shop=packstations&lang=" + lang, ".mw-hero h1, .mw-grid"], ["kategorie", "/miniweb/category.html?demo=1&shop=packstations&lang=" + lang, ".mw-tree a, .mw-grid"], ["košík", "/miniweb/cart.html?demo=1&shop=packstations&lang=" + lang, "main"], ["kontakt", "/miniweb/contact.html?demo=1&shop=packstations&lang=" + lang, ".mw-form"], ["právní", "/miniweb/legal.html?demo=1&shop=packstations&lang=" + lang, "h1"]]) {
      await page.goto(base + url, { waitUntil: "load" });
      await page.waitForSelector(sel, { timeout: 20000 }).catch(() => {});
      await page.waitForTimeout(500);
      const r = await page.evaluate(() => ({
        lang: document.documentElement.lang, text: document.body.innerText, title: document.title,
        holeKlice: [...document.querySelectorAll("body *")].filter(e => e.children.length === 0 && e.textContent).map(e => e.textContent.trim()).filter(t => /^[a-z][a-z0-9_]*(\.[a-z0-9_]+)+$/.test(t)).slice(0, 5),
      }));
      ok(r.lang === lang, `D ${lang} ${nazev}: <html lang="${lang}">`, r.lang);
      ok(!r.holeKlice.length, `D ${lang} ${nazev}: na stránce nejsou holé překladové klíče (chybějící překlad)`, r.holeKlice);
      const cizi = MIMO(lang).test(r.text.replace(/[\u0300-\u036f]/g, "") ) ? (r.text.match(MIMO(lang)) || [])[0] : null;
      ok(!cizi && !BRAND.test(r.text), `D ${lang} ${nazev}: viditelný text jen v abecedě jazyka a bez značky`, cizi ? [cizi, r.text.slice(Math.max(0, r.text.indexOf(cizi) - 30), r.text.indexOf(cizi) + 30)] : "značka");
      if (nazev === "domů") ok(r.title.length > 3 && !holyKlic.test(r.title), `D ${lang}: titulek stránky z překladu`, r.title);
    }
    // karta produktu: V3D HUD slovnik + zeme
    await page.goto(base + "/miniweb/product.html?demo=1&id=9001&shop=packstations&lang=" + lang, { waitUntil: "load" });
    await page.waitForSelector(".pdc-panel:not([hidden])", { timeout: 25000 }).catch(() => {});
    await page.waitForTimeout(800);
    const p = await page.evaluate(() => ({ chybiHud: ((window.V3D && V3D.labelKeys) || []).filter(k => !MW.dict["v3d." + k]), zeme: (MW.cfg.countries || []).map(c => [c, MW.t("country." + c)]), text: (() => { const c = document.body.cloneNode(true); c.querySelectorAll(".v3d-root").forEach(n => n.remove()); return c.innerText; })() }));
    ok(!p.chybiHud.length, `D ${lang} produkt: slovník pokrývá všech V3D.labelKeys (HUD 3D prohlížeče)`, p.chybiHud);
    ok(p.zeme.every(([c, n]) => n && n !== "country." + c), `D ${lang} produkt: každá země shopu má název (slovník nebo prohlížeč)`, p.zeme);
    const cizi2 = (p.text.match(MIMO(lang)) || [])[0];
    ok(!cizi2, `D ${lang} produkt: panel konfigurátoru (bez 3D HUD) je jen v abecedě jazyka`, cizi2 && [cizi2, p.text.slice(Math.max(0, p.text.indexOf(cizi2) - 40), p.text.indexOf(cizi2) + 40)]);
    ok(!errs.length, `D ${lang}: bez JS chyb`, errs.slice(0, 3));
    await ctx.close();
  }
  await browser.close(); server.close();
  console.log(`\nVYSLEDEK jazyková úplnost frontendu mini-shopu: ${total - bad}/${total} OK`);
  process.exit(bad ? 1 : 0);
})().catch(e => { console.error("TEST SPADL:", e); process.exit(2); });
