// 3D prohlizec online nabidky / kontrolni sceny: SYTOST A BARVY MATERIALU v okne "Vzhled nabidek" (bot10, 2026-10-06; Robert: "chci upravit barvy a sytost materialu v 3D pohledu kontrolni sceny / v nabidce").
// SKUTECNA stranka kontrola.html (rezim=nabidka) + SKUTECNY viewer3d.js + env-picker.js v prohlizeci proti falesnemu serveru (GET/PUT /api/public|admin/v3d-vzhled si drzi hodnotu v pameti, nic se nezapisuje).
// Testovaci GLB = vyrob_glb.py (dvoustrane.glb). Kandidat pred nasazenim: WEB_DIR=<prekryv webapp> node test_material_barvy.js
const { chromium } = require("/opt/konfigurator/node_modules/playwright");
const http = require("http"), fs = require("fs"), path = require("path"), os = require("os"), cp = require("child_process");
const REPO = path.resolve(__dirname, "..", ".."), WEB = process.env.WEB_DIR || path.join(REPO, "webapp");
const TMP = fs.mkdtempSync(path.join(os.tmpdir(), "mat_glb_"));
cp.execFileSync(path.join(REPO, "api/venv/bin/python3"), ["-B", path.join(__dirname, "vyrob_glb.py"), TMP], { stdio: ["ignore", "pipe", "inherit"] });
const MIME = { ".html": "text/html; charset=utf-8", ".js": "application/javascript", ".css": "text/css", ".glb": "model/gltf-binary", ".json": "application/json", ".png": "image/png", ".jpg": "image/jpeg", ".hdr": "application/octet-stream", ".svg": "image/svg+xml" };
let store = null, vzhledGet = null; const puts = [];
const server = http.createServer((req, res) => {
  const p = decodeURIComponent(new URL(req.url, "http://x").pathname);
  const J = (st, o) => { res.writeHead(st, { "Content-Type": "application/json" }); res.end(typeof o === "string" ? o : JSON.stringify(o)); };
  let m = /^\/api\/kontrola-scena\/vd\/(\d+)$/.exec(p);
  if (m) return J(200, { product: { id: +m[1], name: "Atrapa karta " + m[1] } });
  if (/^\/api\/kontrola-scena\/v3d\/[\d+]+\.glb$/.test(p)) { res.writeHead(200, { "Content-Type": "model/gltf-binary" }); return res.end(fs.readFileSync(path.join(TMP, "dvoustrane.glb"))); }
  if (p === "/api/public/v3d-vzhled") return J(200, vzhledGet !== null ? vzhledGet : (store || { env: null, alu: null, ao: null, sat: null, barvy: null }));
  if (p === "/api/admin/v3d-vzhled" && req.method === "PUT") {
    let b = ""; req.on("data", (c) => { b += c; }); req.on("end", () => { puts.push(b); const j = JSON.parse(b); store = j === null ? null : Object.assign({ env: null, alu: null, ao: null, sat: null, barvy: null }, j); J(200, store || { env: null, alu: null, ao: null, sat: null, barvy: null }); });
    return;
  }
  if (p.startsWith("/api/")) return J(404, {});
  const f = path.join(WEB, p);
  fs.readFile(f, (e, d) => { if (e) { res.writeHead(404); return res.end("nf"); } res.writeHead(200, { "Content-Type": MIME[path.extname(f)] || "application/octet-stream", "Cache-Control": "no-store" }); res.end(d); });
});
let bad = 0, total = 0;
const t = (name, cond, detail) => { total++; if (!cond) bad++; console.log(`[${cond ? "OK   " : "CHYBA"}] ${name}${!cond && detail !== undefined ? " | " + (typeof detail === "string" ? detail : JSON.stringify(detail)).slice(0, 700) : ""}`); };
const rgb = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
const near = (a, b, tol) => rgb(a).every((v, i) => Math.abs(v - rgb(b)[i]) <= (tol || 1));
const hslS = (h) => { const [r, g, b] = rgb(h).map((v) => v / 255), mx = Math.max(r, g, b), mn = Math.min(r, g, b), l = (mx + mn) / 2; return mx === mn ? 0 : (mx - mn) / (1 - Math.abs(2 * l - 1)); };
(async () => {
  await new Promise((r) => server.listen(0, "127.0.0.1", r));
  const base = "http://127.0.0.1:" + server.address().port;
  const browser = await chromium.launch({ args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
  async function otevri() {
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 }, locale: "cs-CZ" });
    const page = await ctx.newPage(); const errs = [];
    page.on("pageerror", (e) => errs.push(e.message));
    page.on("console", (m) => { if (m.type() === "error" && !/favicon|Failed to load resource/.test(m.text())) errs.push("console: " + m.text()); });
    await page.goto(`${base}/kontrola.html?items=vd:4965+4964&rezim=nabidka`, { waitUntil: "load" });
    await page.waitForFunction(() => /pohyblivých dílů/.test(document.querySelector("#topbar").innerText), null, { timeout: 120000 });
    await page.waitForTimeout(1200);
    return { ctx, page, errs };
  }
  const mat = (page) => page.evaluate(() => window.__v3d.matInfo());
  const otevriPanel = async (page) => { await page.click("#vzhledBtn"); await page.waitForSelector("#vzhledPal .vzh-sw", { timeout: 30000 }); };

  console.log("\n## A) paleta a uprava barvy (kontrolni scena, dvoustranna scena)");
  let c = await otevri();
  let mi = await mat(c.page);
  t("A1 model ma nehlinikove materialy s puvodni barvou (hook matInfo), vychozi stav = puvodni barvy", mi.length >= 4 && mi.every((x) => /^#[0-9a-f]{6}$/.test(x.orig) && near(x.orig, x.now, 1)), mi.slice(0, 3));
  await otevriPanel(c.page);
  const pal = await c.page.evaluate(() => ({ n: document.querySelectorAll("#vzhledPal .vzh-sw").length, hexy: [...document.querySelectorAll("#vzhledPal input[type=color]")].map((i) => i.getAttribute("data-hex") + "=" + i.value), sat: document.getElementById("vzhledSat").value, txt: document.getElementById("vzhledSatTxt").textContent, resety: [...document.querySelectorAll("#vzhledPal .vzh-sw__r")].filter((b) => !b.hidden).length }));
  t("A2 okno Vzhled nabidek ukazuje sekci Materialy: vzorky puvodnich barev (vlastni hex = puvodni), jezdec sytosti 100 %, zadny reset", pal.n >= 2 && pal.n <= 16 && pal.hexy.every((h) => { const [a, b] = h.split("="); return a === b; }) && pal.sat === "100" && /^100 %$/.test(pal.txt) && pal.resety === 0, pal);
  const prvni = await c.page.locator("#vzhledPal input[type=color]").first().getAttribute("data-hex");
  await c.page.locator("#vzhledPal input[type=color]").first().fill("#00ff00"); await c.page.waitForTimeout(500);
  mi = await mat(c.page);
  t("A3 zmena barvy vzorku se hned projevi na vsech materialech teze puvodni barvy; ostatni zustavaji (ziva zmena v 3D)", mi.filter((x) => x.orig === prvni).length >= 1 && mi.filter((x) => x.orig === prvni).every((x) => near(x.now, "#00ff00", 2)) && mi.filter((x) => x.orig !== prvni).every((x) => near(x.now, x.orig, 1)), mi.filter((x) => x.orig === prvni || x.now !== x.orig).slice(0, 4));
  t("A4 u zmeneneho vzorku se ukaze tlacitko Vratit puvodni barvu (↺), u ostatnich ne", await c.page.evaluate(() => [...document.querySelectorAll("#vzhledPal .vzh-sw")].map((r) => !r.querySelector(".vzh-sw__r").hidden).join()) === [true].concat(new Array(pal.n - 1).fill(false)).join());
  await c.page.locator("#vzhledPal .vzh-sw__r").first().click(); await c.page.waitForTimeout(400);
  mi = await mat(c.page);
  t("A5 ↺ vrati puvodni barvu (materialy = puvodni, tlacitko se schova, vzorek ukazuje puvodni hex)", mi.every((x) => near(x.orig, x.now, 1)) && await c.page.evaluate((h) => document.querySelector("#vzhledPal input[type=color]").value === h && document.querySelector("#vzhledPal .vzh-sw__r").hidden, prvni));
  await c.page.locator("#vzhledSat").fill("0"); await c.page.waitForTimeout(500);
  mi = await mat(c.page);
  t("A6 sytost 0 % = vsechny barvy materialu sede (r = g = b), popisek 0 %", mi.every((x) => rgb(x.now).every((v) => Math.abs(v - rgb(x.now)[0]) <= 2)) && await c.page.evaluate(() => document.getElementById("vzhledSatTxt").textContent === "0 %"), mi.slice(0, 3));
  await c.page.locator("#vzhledSat").fill("200"); await c.page.waitForTimeout(500);
  mi = await mat(c.page);
  const sytejsi = mi.filter((x) => hslS(x.now) > hslS(x.orig) + 0.02).length, nesytejsi = mi.filter((x) => hslS(x.now) < hslS(x.orig) - 0.02).length;
  t("A7 sytost 200 % zvysi sytost barevnych materialu a zadnemu ji nesnizi (sede zustanou sede)", sytejsi >= 1 && nesytejsi === 0 && mi.filter((x) => hslS(x.orig) < 0.02).every((x) => hslS(x.now) < 0.05), { sytejsi, nesytejsi });
  await c.page.locator("#vzhledSat").fill("100"); await c.page.waitForTimeout(500);
  mi = await mat(c.page);
  t("A8 sytost zpet na 100 % = puvodni barvy", mi.every((x) => near(x.orig, x.now, 2)));
  t("A9 bez chyb ve strance", c.errs.length === 0, c.errs); await c.ctx.close();

  console.log("\n## B) ulozeni, nacteni a vraceni vychoziho vzhledu");
  c = await otevri(); await otevriPanel(c.page);
  const druha = await c.page.locator("#vzhledPal input[type=color]").nth(1).getAttribute("data-hex");
  await c.page.locator("#vzhledPal input[type=color]").nth(1).fill("#ff0000");
  await c.page.locator("#vzhledSat").fill("150"); await c.page.waitForTimeout(500);
  await c.page.waitForSelector('#vzhledEnv button[data-a="save"]', { timeout: 20000 });
  puts.length = 0;
  await c.page.click('#vzhledEnv button[data-a="save"]'); await c.page.waitForFunction(() => /sytost 150 %/.test(document.getElementById("vzhledInfo").textContent), null, { timeout: 15000 }).catch(() => {});
  const put = puts.length ? JSON.parse(puts[puts.length - 1]) : null;
  t("B1 Ulozit vzhled pro nabidky posle PUT se sytosti a barvami (sat 1,5, barvy {puvodni: #ff0000}) spolu s env / alu / ao", !!put && put.sat === 1.5 && put.barvy && put.barvy[druha] === "#ff0000" && Object.keys(put.barvy).length === 1 && "env" in put && "alu" in put && "ao" in put, put);
  const info = await c.page.evaluate(() => document.getElementById("vzhledInfo").textContent);
  t("B2 ulozene hodnoty se ukazou v textu okna (sytost 150 %, zmenenych barev 1)", /sytost 150 %/.test(info) && /změněných barev 1/.test(info), info);
  await c.ctx.close();
  c = await otevri();
  mi = await mat(c.page);
  t("B3 po novem nacteni stranky se ulozena sytost a barva pouzijou hned pri mountu (bez otevreni okna): barva puvodni druhe palety je #ff0000 (po sytosti 150 % = stale cervena), sytejsi nez puvodni ostatni", mi.filter((x) => x.orig === druha).every((x) => near(x.now, "#ff0000", 3)) && mi.some((x) => hslS(x.now) > hslS(x.orig) + 0.02), mi.filter((x) => x.orig === druha).slice(0, 2));
  await otevriPanel(c.page);
  const nac = await c.page.evaluate((h) => ({ sat: document.getElementById("vzhledSat").value, vz: document.querySelector('#vzhledPal input[data-hex="' + h + '"]').value, reset: !document.querySelector('#vzhledPal input[data-hex="' + h + '"]').parentNode.querySelector(".vzh-sw__r").hidden }), druha);
  t("B4 okno ukaze ulozene hodnoty: jezdec 150, vzorek #ff0000 s tlacitkem ↺", nac.sat === "150" && nac.vz === "#ff0000" && nac.reset, nac);
  puts.length = 0;
  await c.page.click("#vzhledReset"); await c.page.waitForFunction(() => /Vráceno výchozí/.test(document.getElementById("vzhledStav").textContent), null, { timeout: 15000 }).catch(() => {});
  mi = await mat(c.page);
  t("B5 Vratit vychozi vzhled: PUT null, materialy znovu puvodni, jezdec 100 %, zadny reset", puts.length && puts[puts.length - 1] === "null" && mi.every((x) => near(x.orig, x.now, 2)) && await c.page.evaluate(() => document.getElementById("vzhledSat").value === "100" && ![...document.querySelectorAll("#vzhledPal .vzh-sw__r")].some((b) => !b.hidden)));
  t("B6 bez chyb ve strance", c.errs.length === 0, c.errs); await c.ctx.close();

  console.log("\n## C) neplatne hodnoty ze serveru se ignoruji");
  vzhledGet = { env: null, alu: null, ao: null, sat: "moc", barvy: { cervena: "modra", "#12345": "#ffffff", "#aabbcc": 5 } };
  c = await otevri(); mi = await mat(c.page);
  t("C1 neplatna sytost a barvy (text, kratky hex, cislo) viewer zahodi: materialy puvodni, stranka bez chyb", mi.every((x) => near(x.orig, x.now, 1)) && c.errs.length === 0, [mi.slice(0, 2), c.errs]);
  await c.ctx.close();
  vzhledGet = { env: null, alu: null, ao: null, sat: 99, barvy: null };
  c = await otevri(); mi = await mat(c.page);
  t("C2 sytost nad mezi (99) se omezi na 200 % (viewer MAT_SAT_MAX), nespadne", mi.some((x) => hslS(x.now) > hslS(x.orig) + 0.02) && c.errs.length === 0, c.errs);
  await c.ctx.close();

  console.log(`\n${total - bad}/${total} kontrol OK` + (bad ? `; SELHALO ${bad}` : ""));
  await browser.close(); server.close(); fs.rmSync(TMP, { recursive: true, force: true });
  process.exit(bad ? 1 : 0);
})();
