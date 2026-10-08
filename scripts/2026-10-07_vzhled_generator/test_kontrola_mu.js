// Test rezimu `mu:<adresa modelu>` + `embed=1` v kontrolni scene (kontrola.html; bot10, 2026-10-07; Robert: "to nema byt jen v jedne karte, ale automaticky v kazde", "at se to negeneruje
// porad dokola, muze to byt propojene do generatoru stolu a tam to muze sidlit"): okno Vzhled online nabidek nad modelem ZADANYM ADRESOU (GLB generatoru stolu), nic se nestavi na serveru; v embed
// rezimu (iframe v generatoru) bez horniho popisku. SKUTECNY prohlizec + SKUTECNY viewer3d.js a env-picker.js, server je ATRAPA (GET /api/public/v3d-vzhled, PUT /api/admin/v3d-vzhled, GLB generatoru).
//   node scripts/2026-10-07_vzhled_generator/test_kontrola_mu.js      (WEB_DIR=<prekryv webapp> = kandidat pred nasazenim; KONTROLA_HTML=<cesta> = kandidat stranky)
const { chromium } = require("/opt/konfigurator/node_modules/playwright");
const http = require("http"), fs = require("fs"), path = require("path");
const WEB = process.env.WEB_DIR || "/opt/konfigurator/webapp";
const LIVE = "/opt/konfigurator/webapp";                                   // modely (katalog) a velke soubory se berou z ziveho stromu, kdyz v prekryvu nejsou
const over = {};
if (process.env.KONTROLA_HTML) over["/kontrola.html"] = process.env.KONTROLA_HTML;
const MIME = { ".html": "text/html; charset=utf-8", ".js": "application/javascript", ".css": "text/css", ".glb": "model/gltf-binary", ".json": "application/json", ".png": "image/png", ".jpg": "image/jpeg", ".hdr": "application/octet-stream" };
const TOKEN = "eyJiIjowLCJkIjoyMDAwfQ.abcdef0123456789";                    // fiktivni token (server je atrapa; tvar jako /api/shop/configurator/glb/<token>)
const MODEL_URL = "/api/shop/configurator/glb/" + TOKEN;
let bad = 0, total = 0;
const t = (name, cond, detail) => { total++; if (!cond) bad++; console.log(`[${cond ? "OK   " : "CHYBA"}] ${name}${!cond && detail !== undefined ? " | " + (typeof detail === "string" ? detail : JSON.stringify(detail)) : ""}`); };

let ulozeno = { env: null, alu: null, ao: null };
const puts = [], pozadavky = [];
const server = http.createServer((req, res) => {
  const u = new URL(req.url, "http://x"), p = decodeURIComponent(u.pathname);
  pozadavky.push(req.method + " " + p);
  const json = (st, o) => { res.writeHead(st, { "Content-Type": "application/json" }); res.end(JSON.stringify(o)); };
  if (p === "/api/public/v3d-vzhled" && req.method === "GET") return json(200, ulozeno);
  if (p === "/api/admin/v3d-vzhled" && req.method === "PUT") {
    let body = ""; req.on("data", (c) => { body += c; }); req.on("end", () => { puts.push(body); const b = JSON.parse(body); ulozeno = b === null ? { env: null, alu: null, ao: null } : Object.assign({ env: null, alu: null, ao: null }, b); json(200, ulozeno); });
    return;
  }
  if (p === MODEL_URL) { res.writeHead(200, { "Content-Type": "model/gltf-binary" }); return res.end(fs.readFileSync(path.join(LIVE, "katalog/vandr/v3d_nahled/4918.glb"))); }
  if (p.startsWith("/api/")) return json(404, { error: "atrapa" });
  const f = over[p] || path.join(WEB, p);
  const cesty = [f, path.join(LIVE, p)];
  for (const c of cesty) { try { if (fs.statSync(c).isFile()) { res.writeHead(200, { "Content-Type": MIME[path.extname(c)] || "application/octet-stream", "Cache-Control": "no-store" }); return res.end(fs.readFileSync(c)); } } catch (e) { /* dalsi */ } }
  res.writeHead(404); res.end("nenalezeno");
});
const pockejModel = (page) => page.waitForFunction(() => window.__v3d && window.__v3d.state && window.__v3d.state().ready, null, { timeout: 90000, polling: 150 });          // v embed rezimu je popisek skryty -> spolehat jen na stav vieweru

(async () => {
  await new Promise((r) => server.listen(0, "127.0.0.1", r));
  const base = "http://127.0.0.1:" + server.address().port;
  const browser = await chromium.launch({ args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
  const ctx = await browser.newContext({ viewport: { width: 1000, height: 760 }, locale: "cs-CZ" });
  const page = await ctx.newPage();
  const errs = [];
  page.on("pageerror", (e) => errs.push(e.message));
  page.on("console", (m) => { if (m.type() === "error" && !/favicon|Failed to load resource/.test(m.text())) errs.push("console: " + m.text()); });
  const otevri = async (query) => { puts.length = 0; pozadavky.length = 0; await page.goto(`${base}/kontrola.html?${query}`, { waitUntil: "load" }); };
  const enc = encodeURIComponent(MODEL_URL);

  console.log("\n## 1) mu:<adresa> v rezimu nabidka (bez embed): model z adresy, okno Vzhled se otevre samo (vzhled=1)");
  await otevri(`items=mu:${enc}&rezim=nabidka&vzhled=1`);
  await pockejModel(page);
  await page.waitForFunction(() => !document.querySelector("#vzhledPanel").hidden, null, { timeout: 20000 }).catch(() => {});
  await page.waitForFunction(() => /pohyblivých dílů/.test(document.querySelector("#topbar").innerText), null, { timeout: 20000 }).catch(() => {});
  const s1 = await page.evaluate(() => ({ top: document.querySelector("#topbar").innerText, btn: !document.querySelector("#vzhledBtn").hidden, panel: !document.querySelector("#vzhledPanel").hidden, embed: document.body.classList.contains("embed"), status: document.querySelector("#status").innerText }));
  t("1a model se nacetl z adresy generatoru (popisek 'model z generatoru stolu', pohyblive dily)", /model z generátoru stolu/.test(s1.top) && /pohyblivých dílů/.test(s1.top), s1.top);
  t("1b tlacitko Vzhled nabidek je videt a okno se otevrelo samo (&vzhled=1)", s1.btn && s1.panel, s1);
  t("1c bez embed=1 neni trida embed a popisek je videt", !s1.embed && (await page.evaluate(() => getComputedStyle(document.querySelector("#topbar")).display)) !== "none");
  t("1d model se bere PRIMO ze zadane adresy; server nic nestavi (zadny GET /api/kontrola-scena/...)", pozadavky.includes("GET " + MODEL_URL) && !pozadavky.some((x) => /\/api\/kontrola-scena\//.test(x)), pozadavky.filter((x) => /api\//.test(x)));
  t("1e okno ma paletu barev modelu a posuvniky (sytost, hlinik, AO)", await page.evaluate(() => document.querySelectorAll("#vzhledPal input[type=color]").length >= 1 && !!document.querySelector("#vzhledSat") && !!document.querySelector("#vzhledAluRefl")));

  console.log("\n## 2) uprava barvy se ulozi sama pro vsechny nabidky (PUT /api/admin/v3d-vzhled po ~1 s)");
  await page.evaluate(() => { const i = document.querySelector("#vzhledPal input[type=color]"); i.value = "#123456"; i.dispatchEvent(new Event("input", { bubbles: true })); });
  await page.waitForFunction(() => /Uloženo pro všechny nabídky/.test(document.querySelector("#vzhledAutoSt").textContent), null, { timeout: 8000 }).catch(() => {});
  const b = puts.length ? JSON.parse(puts[puts.length - 1]) : null;
  t("2a zmena barvy se ulozila sama (PUT s barvami)", puts.length >= 1 && b && b.barvy && Object.values(b.barvy).includes("#123456"), puts);
  t("2b hlaska 'Uloženo pro všechny nabídky'", await page.evaluate(() => /Uloženo pro všechny nabídky/.test(document.querySelector("#vzhledAutoSt").textContent)));

  console.log("\n## 3) embed=1 (iframe v generatoru): bez horniho popisku, okno Vzhled viditelne");
  await otevri(`items=mu:${enc}&rezim=nabidka&embed=1&vzhled=1`);
  await pockejModel(page);
  await page.waitForFunction(() => !document.querySelector("#vzhledPanel").hidden, null, { timeout: 20000 }).catch(() => {});
  const s3 = await page.evaluate(() => { const p = document.querySelector("#vzhledPanel").getBoundingClientRect(), bt = document.querySelector("#vzhledBtn").getBoundingClientRect(); return { embed: document.body.classList.contains("embed"), top: getComputedStyle(document.querySelector("#topbar")).display,
    panelVidim: p.width > 200 && p.top >= 0 && p.bottom <= innerHeight + 1, btnVidim: bt.width > 40 && bt.top >= 0, btnNadPanelem: bt.bottom <= p.top + 2, otevreno: !document.querySelector("#vzhledPanel").hidden }; });
  t("3a trida embed, horni popisek skryty", s3.embed && s3.top === "none", s3);
  t("3b okno Vzhled je otevrene a cele v okne; tlacitko Vzhled zustava videt nad nim", s3.otevreno && s3.panelVidim && s3.btnVidim && s3.btnNadPanelem, s3);
  t("3c viewer ma platno pres cele okno a bezi (model nacten)", await page.evaluate(() => { const c = document.querySelector("#viewer canvas"); return !!c && c.getBoundingClientRect().width >= innerWidth - 2 && window.__v3d.state().ready; }));

  console.log("\n## 4) neplatne adresy modelu se zahodi (jen /api/shop/configurator/glb/<token>)");
  for (const [popis, adresa] of [["jina cesta", "/etc/passwd"], ["plna adresa", "https://example.com/x.glb"], ["pruchod adresari", "/api/shop/configurator/glb/../../etc/passwd"], ["jiny api prefix", "/api/kontrola-scena/v3d/4965.glb"], ["prazdna", ""]]) {
    await otevri(`items=mu:${encodeURIComponent(adresa)}&rezim=nabidka`);
    await page.waitForTimeout(600);
    const st = await page.evaluate(() => ({ status: document.querySelector("#status").innerText, v3d: !!window.__v3d }));
    t(`4 ${popis} (${adresa || "—"}): ${"Neplatný formát ?items="} a viewer se nespustil, zadny pozadavek na model`, /Neplatný formát \?items=/.test(st.status) && !st.v3d && !pozadavky.some((x) => /glb|\.glb/.test(x)), [st, pozadavky.filter((x) => /api\//.test(x))]);
  }
  await otevri(`items=mu:${enc}`);                                             // bez rezim=nabidka se mu: nepripousti
  await page.waitForTimeout(600);
  t("4 mu: bez rezim=nabidka se zahodi (stary rezim zna jen cs / pa / vd)", /Neplatný formát \?items=/.test(await page.evaluate(() => document.querySelector("#status").innerText)));

  console.log("\n## 5) stare polozky jinak beze zmeny (vd: stale tlacitko Vzhled, nativni polozky stale bez nej)");
  await otevri("items=vd:4965&rezim=nabidka");
  await page.waitForTimeout(800);
  t("5a vd:<karta> v rezimu nabidka stale ukazuje tlacitko Vzhled nabidek", await page.evaluate(() => !document.querySelector("#vzhledBtn").hidden));

  t("zadne chyby ve strance ani v konzoli", errs.length === 0, errs.slice(0, 4));
  await browser.close(); server.close();
  console.log(`\n==> ${total - bad}/${total} kontrol OK`);
  process.exit(bad ? 1 : 0);
})().catch((e) => { console.error("TEST SPADL:", e); process.exit(2); });
