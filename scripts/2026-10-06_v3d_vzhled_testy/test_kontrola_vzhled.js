// Test okna "Vzhled nabidek" v kontrolni scene (kontrola.html?rezim=nabidka; bot10, 2026-10-06; Robert: "potrebuju upravovat materialy v online nabidce a hdri, tzn v kontrolni scene").
// SKUTECNY prohlizec + SKUTECNY viewer3d.js a env-picker.js, SKUTECNA zakaznicka GLB (webapp/katalog/vandr/v3d_nahled/4918, 4921); server je ATRAPA (trasy /api/kontrola-scena/...,
// GET /api/public/v3d-vzhled, PUT /api/admin/v3d-vzhled - ty ma vlastni test_vzhled_api.py / test_kontrola_route.py).
//   node scripts/2026-10-06_v3d_vzhled_testy/test_kontrola_vzhled.js        (KONTROLA_HTML=<cesta> = kandidat stranky; SHOT=<predpona> ulozi snimky)
const { chromium } = require("/opt/konfigurator/node_modules/playwright");
const http = require("http"), fs = require("fs"), path = require("path");
const WEB = process.env.WEB_DIR || "/opt/konfigurator/webapp", SHOT = process.env.SHOT || "";          // kandidat pred nasazenim: WEB_DIR=<prekryv webapp>
const over = {};
if (process.env.KONTROLA_HTML) over["/kontrola.html"] = process.env.KONTROLA_HTML;
const MIME = { ".html": "text/html; charset=utf-8", ".js": "application/javascript", ".css": "text/css", ".glb": "model/gltf-binary", ".json": "application/json", ".png": "image/png", ".jpg": "image/jpeg", ".hdr": "application/octet-stream" };
const GLB = { 4965: "4918", 4964: "4921" };
let bad = 0, total = 0;
const t = (name, cond, detail) => { total++; if (!cond) bad++; console.log(`[${cond ? "OK   " : "CHYBA"}] ${name}${!cond && detail !== undefined ? " | " + (typeof detail === "string" ? detail : JSON.stringify(detail)) : ""}`); };

let ulozeno = { env: null, alu: null, ao: null };           // "DB" atrapy
let rezimGet = "ok", rezimPut = "ok";                       // ok | chyba (GET: 500; PUT: 403 / 400 / 500)
const puts = [];
const server = http.createServer((req, res) => {
  const u = new URL(req.url, "http://x"), p = decodeURIComponent(u.pathname);
  const json = (st, o) => { res.writeHead(st, { "Content-Type": "application/json" }); res.end(JSON.stringify(o)); };
  if (p === "/api/public/v3d-vzhled" && req.method === "GET") return rezimGet === "ok" ? json(200, ulozeno) : (rezimGet === "404" ? (res.writeHead(404, { "Content-Type": "text/html" }), res.end("<h1>404</h1>")) : json(500, { error: "boom" }));
  if (p === "/api/admin/v3d-vzhled" && req.method === "PUT") {
    let body = ""; req.on("data", (c) => { body += c; }); req.on("end", () => {
      puts.push({ ct: req.headers["content-type"], body });
      if (rezimPut === "403") return json(403, { error: "Nedostatecna opravneni.", code: "forbidden" });
      if (rezimPut === "400") return json(400, { error: "env.strength 9 je mimo rozsah 0,1 az 3" });
      if (rezimPut === "500") { res.writeHead(500, { "Content-Type": "text/html" }); return res.end("<h1>500</h1>"); }
      const b = JSON.parse(body);
      ulozeno = b === null ? { env: null, alu: null, ao: null } : { env: b.env || null, alu: b.alu || null, ao: b.ao || null };
      return json(200, ulozeno);
    });
    return;
  }
  let m = /^\/api\/kontrola-scena\/vd\/(\d+)$/.exec(p);
  if (m) return json(200, { product: { id: +m[1], name: "Atrapa karta " + m[1] } });
  m = /^\/api\/kontrola-scena\/v3d\/(\d+)\.glb$/.exec(p);
  if (m && GLB[+m[1]]) { res.writeHead(200, { "Content-Type": "model/gltf-binary", "X-V3D-Cache": "miss" }); return res.end(fs.readFileSync(path.join(WEB, "katalog/vandr/v3d_nahled", GLB[+m[1]] + ".glb"))); }
  const f = over[p] || path.join(WEB, p);
  if (!over[p] && !path.resolve(f).startsWith(WEB)) { res.writeHead(403); return res.end(); }
  fs.readFile(f, (e, d) => { if (e) { res.writeHead(404); return res.end("nenalezeno"); } res.writeHead(200, { "Content-Type": MIME[path.extname(f)] || "application/octet-stream", "Cache-Control": "no-store" }); res.end(d); });
});
const stavVieweru = (page) => page.evaluate(() => { const s = window.__v3d ? window.__v3d.state() : null; if (!s) return null; const c = s.envCfg || { hdri: 'crossfit', strength: 0.6, rot_deg: 0, hemi: 0 }; return { alu: s.alu, ao: s.ao, env: c, envVar: s.env }; });
const pockejModel = (page, n) => page.waitForFunction((x) => /pohyblivých dílů/.test(document.querySelector("#topbar").innerText) && (!x || document.querySelector("#topbar").innerText.includes("karta " + x)), n, { timeout: 90000, polling: 150 });

(async () => {
  await new Promise((r) => server.listen(0, "127.0.0.1", r));
  const base = "http://127.0.0.1:" + server.address().port;
  const browser = await chromium.launch({ args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 }, locale: "cs-CZ" });
  const page = await ctx.newPage();
  const errs = [];
  page.on("pageerror", (e) => errs.push(e.message));
  page.on("console", (m) => { if (m.type() === "error" && !/favicon|Failed to load resource/.test(m.text())) errs.push("console: " + m.text()); });
  const otevri = async (query) => { puts.length = 0; await page.goto(`${base}/kontrola.html?${query}`, { waitUntil: "load" }); };
  const hud = (skupina, klic) => page.click(`.v3d-seg[aria-label="${skupina}"] .v3d-b[data-v="${klic}"]`);

  console.log("\n## 1) ulozeny vzhled se pouzije pri otevreni, okno Vzhled nabidek");
  ulozeno = { env: { hdri: "tv_studio", strength: 1.2, rot_deg: 30, hemi: 0.2 }, alu: "satin", ao: "silne" }; rezimGet = "ok"; rezimPut = "ok";
  await otevri("items=vd:4965,vd:4964&rezim=nabidka");
  await pockejModel(page);
  t("1a tlacitko Vzhled nabidek je videt, okno zavrene", await page.evaluate(() => { const b = document.querySelector("#vzhledBtn"), p = document.querySelector("#vzhledPanel"); return !b.hidden && b.getBoundingClientRect().width > 40 && p.hidden && b.getAttribute("aria-expanded") === "false"; }));
  let st = await stavVieweru(page);
  t("1b viewer dostal ulozeny vzhled: hlinik Satenovy, AO Silne, HDRI TV studio 1,2 / 30 / 0,2", st && st.alu === "satin" && st.ao === "silne" && st.env.hdri === "tv_studio" && st.env.strength === 1.2 && st.env.rot_deg === 30 && st.env.hemi === 0.2, st);
  await page.click("#vzhledBtn");
  await page.waitForSelector("#vzhledEnv .v3d-envp", { timeout: 20000 });
  const panel = await page.evaluate(() => ({ otevreno: !document.querySelector("#vzhledPanel").hidden, exp: document.querySelector("#vzhledBtn").getAttribute("aria-expanded"),
    hdri: document.querySelector("#vzhledEnv select").value, info: document.querySelector("#vzhledInfo").innerText, volby: [...document.querySelectorAll("#vzhledEnv select option")].map((o) => o.value) }));
  t("1c okno otevrene, picker ma HDRI z ulozeneho vzhledu a knihovnu (crossfit, tv_studio, berg_inner, teufelsberg, mistnost)", panel.otevreno && panel.exp === "true" && panel.hdri === "tv_studio" && panel.volby.join() === "crossfit,tv_studio,berg_inner,teufelsberg,mistnost", panel);
  t("1d souhrn: 'Uloženo pro nabídky: HDRI TV studio ... hliník Saténový · AO Silné' a 'Právě nastaveno v náhledu: hliník Saténový · AO Silné'", /Uloženo pro nabídky: HDRI TV studio, síla 1,2, natočení 30°, světlo shora 0,2 · hliník Saténový · AO Silné/.test(panel.info) && /Právě nastaveno v náhledu: hliník Saténový · AO Silné/.test(panel.info), panel.info);
  if (SHOT) await page.screenshot({ path: SHOT + "_panel.png" });

  console.log("\n## 2) uprava a ulozeni (HDRI z okna + hlinik a AO z HUD)");
  await hud("Hliník", "eloxovany");
  await hud("AO", "jemne");
  await page.selectOption("#vzhledEnv select", "berg_inner");
  await page.waitForTimeout(500);
  await page.evaluate(() => { const r = document.querySelector("#vzhledEnv input[type=range][id$='s']"); r.value = "0.9"; r.dispatchEvent(new Event("input", { bubbles: true })); r.dispatchEvent(new Event("change", { bubbles: true })); });
  await page.waitForTimeout(500);
  t("2a okno rika 'Právě nastaveno v náhledu: hliník Eloxovaný (polomatný) · AO Jemné' (obnovuje se samo)", await page.waitForFunction(() => /hliník Eloxovaný \(polomatný\) · AO Jemné/.test(document.querySelector("#vzhledInfo").innerText), null, { timeout: 5000 }).then(() => true, () => false), await page.evaluate(() => document.querySelector("#vzhledInfo").innerText));
  await page.click("#vzhledEnv [data-a=save]");
  await page.waitForFunction(() => /Uloženo:/.test(document.querySelector("#vzhledEnv .st").textContent), null, { timeout: 8000 }).catch(() => {});
  t("2b PUT /api/admin/v3d-vzhled: JSON {env, alu, ao, sat, barvy} z okna a HUD (sytost a barvy nezmenene = null)", puts.length === 1 && /json/.test(puts[0].ct) && JSON.stringify(JSON.parse(puts[0].body)) === JSON.stringify({ env: { hdri: "berg_inner", strength: 0.9, rot_deg: 30, hemi: 0.2 }, alu: "eloxovany", ao: "jemne", sat: null, barvy: null }), puts.map((x) => x.body));
  t("2c hlaska 'Uloženo: ... zákazníci ve všech online nabídkách' a souhrn ulozeneho vzhledu se obnovil", await page.evaluate(() => /Uloženo: HDRI, hliník, AO, sytost i barvy materiálů uvidí zákazníci/.test(document.querySelector("#vzhledEnv .st").textContent) && /Uloženo pro nabídky: HDRI Berg inner, síla 0,9, natočení 30°, světlo shora 0,2 · hliník Eloxovaný \(polomatný\) · AO Jemné · sytost výchozí · změněných barev 0/.test(document.querySelector("#vzhledInfo").innerText)), await page.evaluate(() => [document.querySelector("#vzhledEnv .st").textContent, document.querySelector("#vzhledInfo").innerText]));
  t("2d 'DB' atrapy drzi novy vzhled", ulozeno.alu === "eloxovany" && ulozeno.ao === "jemne" && ulozeno.env.hdri === "berg_inner", ulozeno);

  console.log("\n## 3) prepnuti na dalsi kartu: rozdelany vzhled se prenese, okno se napoji na novy prohlizec");
  await hud("Hliník", "matny");                                   // zmena BEZ ulozeni
  await page.selectOption("#vzhledEnv select", "teufelsberg");
  await page.waitForTimeout(400);
  await page.click("#nextBtn");
  await pockejModel(page, 4964);
  await page.waitForTimeout(800);
  st = await stavVieweru(page);
  t("3a nova karta ma rozdelany vzhled: hlinik Matny, AO Jemne, HDRI Teufelsberg (ne ulozene Berg inner)", st && st.alu === "matny" && st.ao === "jemne" && st.env.hdri === "teufelsberg", st);
  t("3b okno zustalo otevrene a picker ukazuje HDRI Teufelsberg; ulozeny vzhled je porad Berg inner", await page.evaluate(() => !document.querySelector("#vzhledPanel").hidden && document.querySelector("#vzhledEnv select").value === "teufelsberg" && /HDRI Berg inner/.test(document.querySelector("#vzhledInfo").innerText)));
  t("3c zadny dalsi PUT (zmeny bez tlacitka se neukladaji)", puts.length === 1, puts.length);

  console.log("\n## 4) chyby ukladani se ukazou nahlas, nic se neprepise");
  const pred = JSON.stringify(ulozeno);
  for (const [mod, ocek] of [["403", /Nedostatecna opravneni\./], ["400", /env\.strength 9 je mimo rozsah/], ["500", /HTTP 500/]]) {
    rezimPut = mod; puts.length = 0;
    await page.click("#vzhledEnv [data-a=save]");
    await page.waitForFunction(() => /Uložení se nepovedlo/.test(document.querySelector("#vzhledEnv .st").textContent), null, { timeout: 8000 }).catch(() => {});
    const txt = await page.evaluate(() => document.querySelector("#vzhledEnv .st").textContent);
    t(`4${mod} PUT ${mod}: okno ukaze 'Uložení se nepovedlo: <duvod ze serveru>'`, ocek.test(txt) && /Uložení se nepovedlo/.test(txt), txt);
  }
  t("4d po chybach je ulozeny vzhled beze zmeny", JSON.stringify(ulozeno) === pred);
  rezimPut = "ok";

  console.log("\n## 5) vratit vychozi vzhled");
  puts.length = 0;
  await page.click("#vzhledReset");
  await page.waitForFunction(() => /Vráceno výchozí/.test(document.querySelector("#vzhledStav").textContent), null, { timeout: 8000 }).catch(() => {});
  t("5a PUT s telem null a stavovy radek 'Vráceno výchozí'", puts.length === 1 && puts[0].body === "null" && /Vráceno výchozí/.test(await page.evaluate(() => document.querySelector("#vzhledStav").textContent)), puts);
  st = await stavVieweru(page);
  t("5b nahled je na vychozim vzhledu: hlinik Dnesni (lesklý kov), AO Vyp, HDRI Crossfit 0,6", st && st.alu === "puvodni" && st.ao === "vyp" && st.env.hdri === "crossfit" && st.env.strength === 0.6, st);
  t("5c ulozeno = vychozi a souhrn 'výchozí vzhled'", JSON.stringify(ulozeno) === JSON.stringify({ env: null, alu: null, ao: null }) && /Uloženo pro nabídky: výchozí vzhled/.test(await page.evaluate(() => document.querySelector("#vzhledInfo").innerText)));
  await page.click("#vzhledZavrit");
  t("5d okno se zavre tlacitkem Zavrit", await page.evaluate(() => document.querySelector("#vzhledPanel").hidden && document.querySelector("#vzhledBtn").getAttribute("aria-expanded") === "false"));

  console.log("\n## 6) bez API (pred nasazenim / chyba): stranka funguje s vychozim vzhledem");
  for (const mod of ["404", "500"]) {
    rezimGet = mod;
    await otevri("items=vd:4965&rezim=nabidka");
    await pockejModel(page);
    st = await stavVieweru(page);
    t(`6${mod} GET vzhledu ${mod}: model se ukaze, vychozi vzhled (AO Stredni z HUD pro kontrolu, HDRI Crossfit), tlacitko je videt`, st && st.env.hdri === "crossfit" && (await page.evaluate(() => !document.querySelector("#vzhledBtn").hidden)), st);
  }
  rezimGet = "ok";

  console.log("\n## 7) ostatni rezimy beze zmeny");
  await otevri("items=cs:1&rezim=nabidka");
  await page.waitForTimeout(600);
  t("7a nativni polozky: tlacitko Vzhled nabidek se neukazuje (zadny viewer)", await page.evaluate(() => document.querySelector("#vzhledBtn").hidden));
  await otevri("rezim=param&model=plato_vysuvne");
  await page.waitForTimeout(800);
  t("7b rezim=param: tlacitko ani okno vzhledu se neukazuje", await page.evaluate(() => document.querySelector("#vzhledBtn").hidden && document.querySelector("#vzhledPanel").hidden));
  t("7c zadne chyby ve strance (JS)", errs.length === 0, errs.slice(0, 4));
  await browser.close(); server.close();
  console.log(`\n${total - bad}/${total} kontrol OK` + (bad ? `; SELHALO ${bad}` : ""));
  process.exit(bad ? 1 : 0);
})().catch((e) => { console.error(e); process.exit(2); });
