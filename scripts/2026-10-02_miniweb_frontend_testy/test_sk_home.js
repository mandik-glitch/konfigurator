// Slovenska verze mini-shopu (?lang=sk&demo=1, staff mock): uvod s texty od bot7 pocita z i18n klicu, zadny surovy klic, zadna cestina/znacka.
const fs = require("fs"), http = require("http"), path = require("path");
const { chromium } = require("/opt/konfigurator/node_modules/playwright");
const LIVE = process.env.WEB_OVERRIDE || "/opt/konfigurator/webapp";          // WEB_OVERRIDE: kandidatni kopie statiky (git worktree), jinak zive webapp
const MIME = { ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css", ".json": "application/json" };
const srv = http.createServer((req, res) => {
  const p = new URL(req.url, "http://x").pathname;
  if (p === "/api/auth/me") { res.writeHead(200, { "Content-Type": "application/json" }); return res.end(JSON.stringify({ user: { id: 1, role: "admin", email: "a@b.c" } })); }
  if (p.startsWith("/api/")) { res.writeHead(404); return res.end(); }
  const f = path.join(LIVE, p === "/" ? "/index.html" : p);
  if (f.includes("..") || !fs.existsSync(f) || fs.statSync(f).isDirectory()) { res.writeHead(404); return res.end("nf"); }
  res.writeHead(200, { "Content-Type": MIME[path.extname(f)] || "application/octet-stream" }); fs.createReadStream(f).pipe(res);
});
let bad = 0, total = 0; const ok = (c, t) => { total++; if (!c) bad++; console.log(`[${c ? "OK   " : "CHYBA"}] ${t}`); };
(async () => {
  await new Promise(r => srv.listen(0, "127.0.0.1", r)); const base = "http://127.0.0.1:" + srv.address().port;
  const b = await chromium.launch(); const page = await b.newPage({ viewport: { width: 1280, height: 900 } }); const errs = [];
  page.on("pageerror", e => errs.push(e.message));
  await page.goto(base + "/miniweb/index.html?lang=sk&demo=1&shop=packstations"); await page.waitForSelector(".mw-hero h1");
  const t = await page.locator("body").innerText(), dict = JSON.parse(fs.readFileSync(LIVE + "/miniweb/i18n/sk.json", "utf8"));
  ok(await page.evaluate(() => document.documentElement.lang) === "sk" && (await page.locator(".mw-hero h1").innerText()) === dict["home.h1"], "S1 <html lang=sk>, nadpis úvodu = home.h1 (" + dict["home.h1"] + ")");
  ok(await page.locator(".mw-usp li").count() === 4, "S2 čtyři výhody");
  const faqN = new Set(Object.keys(JSON.parse(fs.readFileSync(path.join(LIVE, "miniweb/i18n/sk.json"), "utf8"))).map(k => (/^faq\.(\d+)\.q(\.multi)?$/.exec(k) || [])[1]).filter(Boolean)).size;          // pocet otazek z i18n (bot7 FAQ doplnuje), ne pevne cislo
  ok(faqN >= 8 && await page.locator("details.mw-faq").count() === faqN, "S3 FAQ: " + faqN + " otázek (počet z i18n sk.json)");
  ok(await page.locator(".mw-cta2").count() === 1 && (await page.locator("ol.mw-steps li strong").first().innerText()) === dict["home.step1.t"], "S4 výzva na konci a kroky bez variant .inquiry (krok 1 = " + dict["home.step1.t"] + ")");
  ok(!/\b(home|faq|nav|pd|cart|co|inq|err|legal|alt)\.[a-z0-9_.]+\b/.test(t.replace(/\S+\.(top|com|cz)\b/g, "")), "S5 na stránce není žádný surový překladový klíč");
  ok(!/konfigur[aá]tor|logiman|vandrawee|ponk/i.test(t), "S6 bez značky, zakázaného slova a slova ‚ponk‘");
  ok(!errs.length, "S7 bez JS chyb" + (errs.length ? " | " + errs[0] : ""));
  await b.close(); srv.close(); console.log(`\n==> ${total - bad}/${total} kontrol OK`); process.exit(bad ? 1 : 0);
})();
