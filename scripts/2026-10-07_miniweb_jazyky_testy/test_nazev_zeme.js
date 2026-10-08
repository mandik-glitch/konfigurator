// Mini-shop: nazev zeme bez prekladoveho klice (country.<ISO>) se bere z prohlizece v jazyce shopu (Intl.DisplayNames) - dalsi shop (HU, ...) nepotrebuje preklad kazde zeme (bot16, 2026-10-07).
// Skutecne soubory (WEB_OVERRIDE = kandidat, jinak zive webapp), jen /api/auth/me je simulovano (demo rezim je pro staff). Existujici klice (country.CZ ...) se NEMENI.
const fs = require("fs"), http = require("http"), path = require("path");
const { chromium } = require("/opt/konfigurator/node_modules/playwright");
const LIVE = process.env.WEB_OVERRIDE || "/opt/konfigurator/webapp";
const MIME = { ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8", ".json": "application/json", ".svg": "image/svg+xml", ".glb": "model/gltf-binary", ".png": "image/png", ".jpg": "image/jpeg" };
const server = http.createServer((req, res) => {
  const p = decodeURIComponent(new URL(req.url, "http://x").pathname);
  if (p === "/api/auth/me") { res.writeHead(200, { "Content-Type": "application/json" }); return res.end(JSON.stringify({ user: { id: 1, email: "staff@example.test", role: "admin", name: "Staff" } })); }
  if (p.startsWith("/api/")) { res.writeHead(404); return res.end(); }
  const f = path.join(LIVE, p);
  if (f.startsWith(LIVE) && fs.existsSync(f) && fs.statSync(f).isFile()) { res.writeHead(200, { "Content-Type": MIME[path.extname(f)] || "application/octet-stream", "Cache-Control": "no-store" }); return fs.createReadStream(f).pipe(res); }
  res.writeHead(404); res.end("nf");
});
let bad = 0, total = 0;
const ok = (c, t, d) => { total++; if (!c) bad++; console.log(`[${c ? "OK   " : "CHYBA"}] ${t}${c ? "" : "  -> " + JSON.stringify(d)}`); };
(async () => {
  await new Promise(r => server.listen(0, "127.0.0.1", r));
  const base = "http://127.0.0.1:" + server.address().port;
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1200, height: 800 } });
  await ctx.route(/pripni-cokoli/, r => r.abort());
  const page = await ctx.newPage(); const errs = [];
  page.on("pageerror", e => errs.push(e.message));
  await page.goto(base + "/miniweb/index.html?demo=1&shop=packstations&lang=en", { waitUntil: "load" });
  await page.waitForSelector(".mw-hero h1", { timeout: 15000 });
  const t = await page.evaluate(() => {
    const out = {};
    out.cz = MW.t("country.CZ"); out.pl = MW.t("country.PL");
    const jaz = l => { MW.cfg.lang = l; return { hu: MW.t("country.HU"), at: MW.t("country.AT"), ro: MW.t("country.RO"), xx: MW.t("country.XX"), jinak: MW.t("country.hu"), klic: MW.t("nav.home") }; };
    out.en = jaz("en"); out.sk = jaz("sk"); out.de = jaz("de"); out.hu = jaz("hu");
    out.bez = (function () { const d = MW.dict; MW.dict = {}; MW.cfg.lang = "de"; const v = MW.t("country.HU"); MW.dict = d; return v; })();
    return out;
  });
  ok(t.cz === "Czech Republic" && t.pl === "Poland", "Z1 existující klíče country.* v en.json se nemění (CZ = „Czech Republic“, PL = „Poland“)", t);
  ok(t.en.hu === "Hungary" && t.en.ro === "Romania", "Z2 en: HU a RO bez klíče = Hungary, Romania z prohlížeče", t.en);
  ok(t.sk.hu === "Maďarsko" && t.de.hu === "Ungarn" && t.hu.hu === "Magyarország", "Z3 podle jazyka shopu: sk Maďarsko, de Ungarn, hu Magyarország", [t.sk.hu, t.de.hu, t.hu.hu]);
  ok(t.hu.at === "Austria" && t.sk.at === "Austria", "Z4 klíč, který slovník má (AT), se nikdy nepřepisuje jménem z prohlížeče (zůstává „Austria“ ze slovníku, i když cfg.lang je hu/sk)", [t.hu.at, t.sk.at]);
  ok(t.en.xx === "country.XX" && t.en.jinak === "country.hu" && t.en.klic === "Home", "Z5 neznámý kód (XX) a špatný tvar klíče zůstávají jako klíč; ostatní klíče beze změny", t.en);
  ok(t.bez === "Ungarn", "Z6 bez jakéhokoli slovníku (MW.dict prázdný) se HU v jazyce de přeloží z prohlížeče", t.bez);
  ok(!errs.length, "Z7 bez chyb JS", errs.slice(0, 2));
  await browser.close(); server.close();
  console.log(`\nVYSLEDEK nazev zeme bez klice: ${total - bad}/${total} OK`);
  process.exit(bad ? 1 : 0);
})().catch(e => { console.error("TEST SPADL:", e); process.exit(2); });
