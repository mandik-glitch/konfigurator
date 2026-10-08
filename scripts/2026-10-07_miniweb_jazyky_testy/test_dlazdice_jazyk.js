// Jazyk dlazdice "Pripni cokoli" v mini-shopech/generatorech je DATA (bot16, 2026-10-07; Robert: kopie shopu v nemcine a madarstine).
// Dosud `PdcLayout.attachWindow` (webapp/js/pdc-layout.js) propoustelo jen /^(cs|sk|en)$/ a vsechno ostatni mapovalo na "en" - nemecky a madarsky shop by ukazal anglickou dlazdici,
// i kdyz texty.json ma `de`/`hu` a `_aktivni` je zapina. Nove se jazyk bere z `_aktivni` v /pripni-cokoli/texty.json (stejny soubor cte prvek, se stejnym ?v=); jazyk mimo seznam -> "en",
// registr se nenacetl (404, rozbity JSON) -> dosavadni trojice cs/sk/en. Test: skutecny pdc-layout.js + skutecny texty.json v Chromiu, dlazdice (3D) je nahrazena stubem, ktery jen zapise
// `opts.lang`, takze se nepouziva WebGL ani sit. Kandidat: WEB_OVERRIDE=<kopie webapp>. Spusteni: node scripts/2026-10-07_miniweb_jazyky_testy/test_dlazdice_jazyk.js
const fs = require("fs"), http = require("http"), path = require("path");
const { chromium } = require("/opt/konfigurator/node_modules/playwright");
const WEB = process.env.WEB_OVERRIDE || "/opt/konfigurator/webapp";
const REAL = fs.readFileSync(path.join(WEB, "pripni-cokoli/texty.json"), "utf8");
const AKTIVNI = JSON.parse(REAL)._aktivni || [];
let bad = 0, total = 0;
const ok = (c, t, d) => { total++; if (!c) bad++; console.log(`[${c ? "OK   " : "CHYBA"}] ${t}${!c && d !== undefined ? " | " + (typeof d === "string" ? d : JSON.stringify(d)) : ""}`); };
const MIME = { ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8", ".json": "application/json", ".svg": "image/svg+xml" };
let texty = { mode: "real" }, tileMode = "ok";
const STUB = () => `window.PripniCokoliTile = { mount: function (el, opts) { (window.__mounts = window.__mounts || []).push({ lang: opts.lang, profile: opts.profile }); ${tileMode === "reject" ? 'return Promise.reject(new Error("mount selhal"));' : "return Promise.resolve(null);"} } };`;
const server = http.createServer((req, res) => {
  const p = decodeURIComponent(new URL(req.url, "http://x").pathname);
  const send = (code, type, body) => { res.writeHead(code, { "Content-Type": type, "Cache-Control": "no-store" }); res.end(body); };
  if (p === "/__t.html") return send(200, MIME[".html"], '<!doctype html><html><body><script src="/js/pdc-layout.js"></script></body></html>');
  if (p === "/js/pripni-cokoli-tile.js") return send(200, MIME[".js"], STUB());
  if (p === "/pripni-cokoli/texty.json") {
    if (texty.mode === "real") return send(200, MIME[".json"], REAL);
    if (texty.mode === "404") return send(404, "text/plain", "nf");
    if (texty.mode === "garbage") return send(200, MIME[".json"], "{ tohle neni json");
    return send(200, MIME[".json"], JSON.stringify(texty.obj));
  }
  const f = path.join(WEB, p);
  if (f.startsWith(WEB) && fs.existsSync(f) && fs.statSync(f).isFile()) return send(200, MIME[path.extname(f)] || "application/octet-stream", fs.readFileSync(f));
  send(404, "text/plain", "nf");
});

async function scenar(browser, base, nazev, nastaveni, jazyky, ocekavane) {
  texty = nastaveni.texty || { mode: "real" }; tileMode = nastaveni.tile || "ok";
  const ctx = await browser.newContext(), page = await ctx.newPage(), errs = [];
  page.on("pageerror", e => errs.push(e.message));
  await page.goto(base + "/__t.html");
  const vysl = [];
  for (let i = 0; i < jazyky.length; i++) {
    const r = await page.evaluate(([lang, v]) => new Promise(resolve => {
      const box = document.createElement("div"), body = document.createElement("div"); box.appendChild(body); document.body.appendChild(box);
      const before = (window.__mounts || []).length;
      window.PdcLayout.attachWindow({ box, body }, { lang, tileUrl: "/js/pripni-cokoli-tile.js?v=t" + v, gate: { after: f => f(), unlock: () => {} } });
      let n = 0; const iv = setInterval(() => {
        n++; const m = window.__mounts || [];
        if (m.length > before) { clearInterval(iv); setTimeout(() => resolve({ lang: m[m.length - 1].lang, hidden: box.hidden }), 150); }
        else if (n > 60) { clearInterval(iv); resolve({ lang: null, hidden: box.hidden }); }
      }, 100);
    }), [jazyky[i], i + 1]);
    vysl.push(r);
  }
  await ctx.close();
  jazyky.forEach((j, i) => ok(vysl[i].lang === ocekavane[i], `${nazev}: jazyk shopu ${JSON.stringify(j)} -> dlazdice ${JSON.stringify(ocekavane[i])}`, vysl[i].lang));
  ok(errs.length === 0, `${nazev}: bez neodchycenych chyb stranky`, errs);
  return vysl;
}

(async () => {
  await new Promise(r => server.listen(0, "127.0.0.1", r));
  const base = "http://127.0.0.1:" + server.address().port;
  const browser = await chromium.launch();
  const J = ["cs", "sk", "en", "de", "hu", "pl", "xx", "", undefined, "de-DE", "DE"];
  // 1) skutecny texty.json: kazdy aktivni jazyk si dlazdici nese, ostatni anglicky
  const exp1 = J.map(j => { const l = String(j || "en").slice(0, 2); return AKTIVNI.includes(l) ? l : "en"; });
  await scenar(browser, base, "S1 skutecny texty.json (_aktivni=" + AKTIVNI.join(",") + ")", {}, J, exp1);
  // 2) pevne _aktivni se de a hu: nemecky a madarsky shop = vlastni jazyk dlazdice, pl (neaktivni) anglicky
  const reg = Object.assign(JSON.parse(REAL), { _aktivni: ["cs", "en", "sk", "de", "hu"] });
  await scenar(browser, base, "S2 _aktivni cs,en,sk,de,hu", { texty: { mode: "obj", obj: reg } }, ["de", "hu", "pl", "sk", "de-AT", "hu-HU"], ["de", "hu", "en", "sk", "de", "hu"]);
  // 3) registr se nenacetl (404) nebo je rozbity: dosavadni trojice cs/sk/en, nemecky -> anglicky
  await scenar(browser, base, "S3 texty.json 404", { texty: { mode: "404" } }, ["cs", "sk", "en", "de", "hu"], ["cs", "sk", "en", "en", "en"]);
  await scenar(browser, base, "S4 texty.json rozbity JSON", { texty: { mode: "garbage" } }, ["cs", "sk", "en", "de"], ["cs", "sk", "en", "en"]);
  // 4) novy jazyk jen v datech (pl): zadna zmena kodu
  const regPl = Object.assign(JSON.parse(REAL), { _aktivni: ["cs", "pl"] });
  await scenar(browser, base, "S5 _aktivni cs,pl (novy jazyk jen v datech)", { texty: { mode: "obj", obj: regPl } }, ["pl", "cs", "de", "en"], ["pl", "cs", "en", "en"]);
  // 5) selhani dlazdice (mount odmitne): okno se skryje, zadna neodchycena chyba
  const v = await scenar(browser, base, "S6 mount dlazdice selze", { tile: "reject" }, ["de"], [exp1[3]]);
  ok(v[0].hidden === true, "S6: okno dlazdice se po selhani mount skryje (box.hidden)", v[0]);
  await browser.close(); server.close();
  console.log(`\n==> ${total - bad}/${total} kontrol OK`);
  process.exit(bad ? 1 : 0);
})().catch(e => { console.error("CHYBA TESTU", e); process.exit(2); });
