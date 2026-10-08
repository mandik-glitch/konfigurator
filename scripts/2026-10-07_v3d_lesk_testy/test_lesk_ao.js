// 3D prohlizec online nabidky / kontrolni sceny: ODLESKY A AO v okne "Vzhled nabidek" (viewer 1.14.0; bot10, 2026-10-07; Robert: "reseni odlesku materialu, jejich AO").
// SKUTECNA stranka kontrola.html (rezim=nabidka) + SKUTECNY viewer3d.js + env-picker.js v prohlizeci proti falesnemu serveru (GET/PUT /api/public|admin/v3d-vzhled si drzi hodnotu v pameti, nic se nezapisuje).
// Testuje: lesk u kazde barvy materialu (drsnost = puvodni^lesk), odlesky a matnost hliniku (nasobky varianty), sila a dosah AO (nasobky varianty), ulozeni (PUT), nacteni pri mountu, neplatne hodnoty, reset.
// Kandidat pred nasazenim: WEB_DIR=<prekryv webapp> node test_lesk_ao.js
const { chromium } = require("/opt/konfigurator/node_modules/playwright");
const http = require("http"), fs = require("fs"), path = require("path"), os = require("os"), cp = require("child_process");
const REPO = path.resolve(__dirname, "..", ".."), WEB = process.env.WEB_DIR || path.join(REPO, "webapp");
const TMP = fs.mkdtempSync(path.join(os.tmpdir(), "lesk_glb_"));
cp.execFileSync(path.join(REPO, "api/venv/bin/python3"), ["-B", path.join(REPO, "scripts/2026-10-06_v3d_rady_testy/vyrob_glb.py"), TMP], { stdio: ["ignore", "pipe", "inherit"] });
const MIME = { ".html": "text/html; charset=utf-8", ".js": "application/javascript", ".css": "text/css", ".glb": "model/gltf-binary", ".json": "application/json", ".png": "image/png", ".jpg": "image/jpeg", ".hdr": "application/octet-stream", ".svg": "image/svg+xml" };
const DEF = { env: null, alu: null, ao: null, sat: null, barvy: null, lesk: null, alu_cfg: null, ao_cfg: null };
let store = null, vzhledGet = null, stareApi = false; const puts = [];        // stareApi = server pred nasazenim: GET bez lesk / alu_cfg / ao_cfg / hdri_extra, PUT s nimi = 400
const STARE = ["lesk", "alu_cfg", "ao_cfg"];
const server = http.createServer((req, res) => {
  const p = decodeURIComponent(new URL(req.url, "http://x").pathname);
  const J = (st, o) => { res.writeHead(st, { "Content-Type": "application/json" }); res.end(typeof o === "string" ? o : JSON.stringify(o)); };
  let m = /^\/api\/kontrola-scena\/vd\/(\d+)$/.exec(p);
  if (m) return J(200, { product: { id: +m[1], name: "Atrapa karta " + m[1] } });
  if (/^\/api\/kontrola-scena\/v3d\/[\d+]+\.glb$/.test(p)) { res.writeHead(200, { "Content-Type": "model/gltf-binary" }); return res.end(fs.readFileSync(path.join(TMP, "dvoustrane.glb"))); }
  if (p === "/api/public/v3d-vzhled") {
    const z = Object.assign({}, vzhledGet !== null ? vzhledGet : (store || DEF));
    if (stareApi) { STARE.forEach((k) => delete z[k]); return J(200, z); }
    return J(200, Object.assign({ hdri_extra: [] }, z));
  }
  if (p === "/api/admin/v3d-vzhled" && req.method === "PUT") {
    let b = ""; req.on("data", (c) => { b += c; }); req.on("end", () => {
      puts.push(b); const j = JSON.parse(b);
      if (stareApi && j && STARE.some((k) => k in j)) return J(400, { error: "neznamy klic " + STARE.find((k) => k in j) });
      store = j === null ? null : Object.assign({}, DEF, j); J(200, store || DEF);
    });
    return;
  }
  if (p.startsWith("/api/")) return J(404, {});
  const f = path.join(WEB, p);
  fs.readFile(f, (e, d) => { if (e) { res.writeHead(404); return res.end("nf"); } res.writeHead(200, { "Content-Type": MIME[path.extname(f)] || "application/octet-stream", "Cache-Control": "no-store" }); res.end(d); });
});
let bad = 0, total = 0;
const t = (name, cond, detail) => { total++; if (!cond) bad++; console.log(`[${cond ? "OK   " : "CHYBA"}] ${name}${!cond && detail !== undefined ? " | " + (typeof detail === "string" ? detail : JSON.stringify(detail)).slice(0, 700) : ""}`); };
const blizko = (a, b, tol) => Math.abs(a - b) <= (tol === undefined ? 0.011 : tol);
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
    await page.waitForFunction(() => window.__v3d && window.__v3d.state().ready, null, { timeout: 60000 });
    await page.waitForTimeout(1500);
    return { ctx, page, errs };
  }
  const mat = (page) => page.evaluate(() => window.__v3d.matInfo());
  const alu = (page) => page.evaluate(() => window.__v3d.aluInfo());
  const aov = (page) => page.evaluate(() => window.__v3d.aoValues());
  const otevriPanel = async (page) => { await page.click("#vzhledBtn"); await page.waitForSelector("#vzhledPal .vzh-sw", { timeout: 30000 }); };
  const nastav = async (page, sel, v) => { await page.locator(sel).fill(String(v)); await page.waitForTimeout(350); };
  const hudAO = async (page, k) => { await page.click(`[data-grp="ao"][data-v="${k}"]`); await page.waitForTimeout(500); };
  const hudAlu = async (page, k) => { await page.click(`[data-grp="alu"][data-v="${k}"]`); await page.waitForTimeout(500); };
  const ulozPut = async (page) => { const n = puts.length; await page.getByRole("button", { name: "Uložit vzhled pro nabídky" }).click(); await page.waitForFunction((n) => true, n); for (let i = 0; i < 100 && puts.length === n; i++) await page.waitForTimeout(100); return puts.length > n ? JSON.parse(puts[puts.length - 1]) : null; };

  console.log("\n## A) lesk materialu (posuvnik u kazde barvy)");
  let c = await otevri();
  await otevriPanel(c.page);
  const mi0 = await mat(c.page);
  const hex = mi0.find((x) => typeof x.rough0 === "number" && x.rough0 > 0.05 && x.rough0 < 0.95);
  t("A1 model ma nehlinikove materialy s puvodni drsnosti (hook matInfo rough0), vychozi drsnost = puvodni", !!hex && mi0.every((x) => x.rough0 === null || blizko(x.rough, x.rough0, 0.001)), mi0.slice(0, 3));
  const radky = await c.page.evaluate(() => [...document.querySelectorAll("#vzhledPal .vzh-sw")].map((r) => ({ hex: r.querySelector("input[type=color]").getAttribute("data-hex"), gl: r.querySelector(".vzh-gl input").value, txt: r.querySelector(".vzh-gl b").textContent, rst: r.querySelector(".vzh-gl__r").hidden })));
  t("A2 u kazde barvy je posuvnik Lesk 100 % bez tlacitka ↺", radky.length >= 2 && radky.every((r) => r.gl === "100" && r.txt === "100 %" && r.rst), radky.slice(0, 3));
  const selG = `#vzhledPal input[data-gloss="${hex.orig}"]`;
  await nastav(c.page, selG, 0);
  let mi = await mat(c.page);
  t("A3 lesk 0 % = mat: materialy teto barvy maji drsnost 1, ostatni beze zmeny", mi.filter((x) => x.orig === hex.orig).every((x) => blizko(x.rough, 1)) && mi.filter((x) => x.orig !== hex.orig).every((x) => x.rough0 === null || blizko(x.rough, x.rough0, 0.001)), mi.slice(0, 4));
  t("A3b u zmeneneho lesku se ukaze ↺ a popisek 0 %", await c.page.evaluate((s) => { const i = document.querySelector(s); return !i.closest(".vzh-gl").querySelector(".vzh-gl__r").hidden && i.closest(".vzh-gl").querySelector("b").textContent === "0 %"; }, selG));
  await nastav(c.page, selG, 200);
  mi = await mat(c.page);
  const ocek2 = Math.max(0.02, Math.pow(Math.max(hex.rough0, 0.02), 2));
  t("A4 lesk 200 %: drsnost = puvodni^2 (" + hex.rough0 + " -> " + ocek2.toFixed(3) + ")", mi.filter((x) => x.orig === hex.orig).every((x) => blizko(x.rough, ocek2)), mi.filter((x) => x.orig === hex.orig));
  await nastav(c.page, selG, 50);
  mi = await mat(c.page);
  const ocek05 = Math.pow(hex.rough0, 0.5);
  t("A5 lesk 50 %: drsnost = puvodni^0,5 (matnejsi nez puvodni)", mi.filter((x) => x.orig === hex.orig).every((x) => blizko(x.rough, ocek05) && x.rough > hex.rough0), { ocek05, mi: mi.filter((x) => x.orig === hex.orig) });
  await c.page.locator(selG).locator("xpath=ancestor::label").locator(".vzh-gl__r").click(); await c.page.waitForTimeout(350);
  mi = await mat(c.page);
  t("A6 ↺ vrati puvodni lesk (drsnost = puvodni, posuvnik 100 %, tlacitko schovano)", mi.every((x) => x.rough0 === null || blizko(x.rough, x.rough0, 0.001)) && await c.page.evaluate((s) => { const i = document.querySelector(s); return i.value === "100" && i.closest(".vzh-gl").querySelector(".vzh-gl__r").hidden; }, selG));
  await nastav(c.page, selG, 0);
  await c.page.locator("#vzhledSat").fill("150"); await c.page.waitForTimeout(350);
  mi = await mat(c.page);
  t("A7 lesk a sytost se nerusi (sytost 150 % meni barvu, lesk 0 % drsnost zustava 1)", mi.filter((x) => x.orig === hex.orig).every((x) => blizko(x.rough, 1)) && mi.some((x) => x.orig !== x.now), mi.slice(0, 3));
  await c.page.locator("#vzhledSat").fill("100"); await nastav(c.page, selG, 100);

  console.log("\n## B) hlinik: odlesky (sila odrazu) a matnost");
  let a0 = await alu(c.page);
  t("B1 model ma hlinikove materialy (hook aluInfo), vychozi drsnost = puvodni", a0.length >= 1 && a0.every((x) => blizko(x.rough, x.rough0, 0.001)), a0.slice(0, 2));
  await nastav(c.page, "#vzhledAluRefl", 50);
  let a1 = await alu(c.page);
  t("B2 odlesky 50 %: sila odrazu (envMapIntensity) hliniku klesne na polovinu, drsnost beze zmeny", a1.every((x, i) => blizko(x.env, a0[i].env * 0.5, Math.max(0.01, a0[i].env * 0.03)) && blizko(x.rough, a0[i].rough, 0.001)), { a0: a0.slice(0, 2), a1: a1.slice(0, 2) });
  await nastav(c.page, "#vzhledAluRefl", 100); await nastav(c.page, "#vzhledAluRough", 150);
  a1 = await alu(c.page);
  t("B3 matnost 150 %: drsnost hliniku x1,5 (nejvyse 1), sila odrazu beze zmeny", a1.every((x, i) => blizko(x.rough, Math.min(1, a0[i].rough * 1.5)) && blizko(x.env, a0[i].env, Math.max(0.01, a0[i].env * 0.03))), { a0: a0.slice(0, 2), a1: a1.slice(0, 2) });
  t("B3b popisky posuvniku: Hlinik odlesky 100 %, matnost 150 %", await c.page.evaluate(() => document.getElementById("vzhledAluReflTxt").textContent === "100 %" && document.getElementById("vzhledAluRoughTxt").textContent === "150 %"));
  await nastav(c.page, "#vzhledAluRough", 100);
  await hudAlu(c.page, "satin");
  const sat0 = await alu(c.page);
  t("B4 varianta Satenovy bez posuvniku: drsnost 0,45", sat0.every((x) => blizko(x.rough, 0.45, 0.001)), sat0.slice(0, 2));
  await nastav(c.page, "#vzhledAluRefl", 50); await nastav(c.page, "#vzhledAluRough", 150);
  const sat1 = await alu(c.page);
  t("B5 posuvniky jsou NASOBKY varianty: Satenovy x matnost 1,5 = drsnost 0,675, odrazy na polovinu", sat1.every((x, i) => blizko(x.rough, 0.675, 0.002) && blizko(x.env, sat0[i].env * 0.5, Math.max(0.01, sat0[i].env * 0.03))), { sat0: sat0.slice(0, 2), sat1: sat1.slice(0, 2) });
  await hudAlu(c.page, "puvodni"); await nastav(c.page, "#vzhledAluRefl", 100); await nastav(c.page, "#vzhledAluRough", 100);
  a1 = await alu(c.page);
  t("B6 vse zpet na 100 % a Dnesni: hlinik jako puvodne", a1.every((x, i) => blizko(x.rough, a0[i].rough, 0.001) && blizko(x.env, a0[i].env, Math.max(0.01, a0[i].env * 0.03))), { a0: a0.slice(0, 2), a1: a1.slice(0, 2) });

  console.log("\n## C) AO: sila a dosah (nasobky varianty)");
  let st = await c.page.evaluate(() => window.__v3d.state());
  if (st.ao === "vyp") await hudAO(c.page, "stredni");
  await hudAO(c.page, "stredni");
  let ao = await aov(c.page);
  t("C1 AO Stredni bez posuvniku: sila 0,4, dosah 8 mm; posuvniky aktivni", ao.variant === "stredni" && blizko(ao.k, 0.4, 0.001) && blizko(ao.r, 8, 0.001) && !(await c.page.evaluate(() => document.getElementById("vzhledAoK").disabled)), ao);
  await nastav(c.page, "#vzhledAoK", 150); await nastav(c.page, "#vzhledAoR", 200);
  ao = await aov(c.page);
  t("C2 sila 150 %, dosah 200 %: k = 0,6, r = 16", blizko(ao.k, 0.6, 0.001) && blizko(ao.r, 16, 0.001) && ao.cfg && ao.cfg.k === 1.5 && ao.cfg.r === 2, ao);
  await hudAO(c.page, "silne");
  ao = await aov(c.page);
  t("C3 posuvniky jsou nasobky varianty: Silne (0,7 / 24) x 1,5 / 2 = 1,05 / 48", ao.variant === "silne" && blizko(ao.k, 1.05, 0.001) && blizko(ao.r, 48, 0.001), ao);
  await nastav(c.page, "#vzhledAoK", 0);
  ao = await aov(c.page);
  t("C4 sila 0 % = AO bez ucinku (k = 0), stranka bez chyby", blizko(ao.k, 0, 0.001) && c.errs.length === 0, [ao, c.errs]);
  await hudAO(c.page, "vyp"); await c.page.waitForTimeout(900);
  t("C5 AO Vyp: posuvniky AO jsou neaktivni (sedive) s napovedou", await c.page.evaluate(() => document.getElementById("vzhledAoK").disabled && document.getElementById("vzhledAoR").disabled && /AO je vypnuté/.test(document.getElementById("vzhledAoK").title)));
  await hudAO(c.page, "stredni"); await c.page.waitForTimeout(900);
  t("C6 AO zase zapnute: posuvniky se odemknou a drzi hodnoty (sila 0 %, dosah 200 %)", await c.page.evaluate(() => !document.getElementById("vzhledAoK").disabled && document.getElementById("vzhledAoK").value === "0" && document.getElementById("vzhledAoR").value === "200"));
  await nastav(c.page, "#vzhledAoK", 150);

  console.log("\n## D) ulozeni (PUT) a souhrn");
  await nastav(c.page, selG, 50); await nastav(c.page, "#vzhledAluRefl", 80); await nastav(c.page, "#vzhledAluRough", 120);
  let body = await ulozPut(c.page);
  t("D1 PUT nese lesk {barva: 0,5}, alu_cfg {refl 0,8, rough 1,2}, ao_cfg {k 1,5, r 2} + alu a ao varianty", !!body && body.lesk && body.lesk[hex.orig] === 0.5 && Object.keys(body.lesk).length === 1 && body.alu_cfg && body.alu_cfg.refl === 0.8 && body.alu_cfg.rough === 1.2 && body.ao_cfg && body.ao_cfg.k === 1.5 && body.ao_cfg.r === 2 && body.ao === "stredni" && body.alu === "puvodni", body);
  await c.page.waitForTimeout(500);
  const info = await c.page.evaluate(() => document.getElementById("vzhledInfo").textContent);
  t("D2 souhrn 'Ulozeno pro nabidky' ukazuje lesk, odlesky hliniku a AO", /lesk materiálů: 1 změn/.test(info) && /hliník odlesky 80 %, matnost 120 %/.test(info) && /AO síla 150 %, dosah 200 %/.test(info), info);
  await nastav(c.page, selG, 100); await nastav(c.page, "#vzhledAluRefl", 100); await nastav(c.page, "#vzhledAluRough", 100); await nastav(c.page, "#vzhledAoK", 100); await nastav(c.page, "#vzhledAoR", 100);
  body = await ulozPut(c.page);
  t("D3 vsechny posuvniky na 100 % = PUT s lesk / alu_cfg / ao_cfg null (vychozi)", !!body && body.lesk === null && body.alu_cfg === null && body.ao_cfg === null, body);
  t("D4 stranka bez chyb v konzoli", c.errs.length === 0, c.errs);
  await c.ctx.close();

  console.log("\n## E) nacteni ulozeneho vzhledu pri mountu (kontrolni scena)");
  vzhledGet = Object.assign({}, DEF, { ao: "jemne", lesk: { [hex.orig]: 0.5 }, alu_cfg: { refl: 0.6, rough: 1.3 }, ao_cfg: { k: 1.2, r: 2 } });
  c = await otevri();
  mi = await mat(c.page); a1 = await alu(c.page); ao = await aov(c.page);
  t("E1 ulozeny lesk se pouzije hned po otevreni: drsnost = puvodni^0,5", mi.filter((x) => x.orig === hex.orig).every((x) => blizko(x.rough, Math.pow(hex.rough0, 0.5))), mi.filter((x) => x.orig === hex.orig));
  t("E2 ulozene odlesky hliniku se pouziji: matnost x1,3, odrazy x0,6", a1.every((x, i) => blizko(x.rough, Math.min(1, a0[i].rough * 1.3)) && blizko(x.env, a0[i].env * 0.6, Math.max(0.01, a0[i].env * 0.04))), { a0: a0.slice(0, 2), a1: a1.slice(0, 2) });
  t("E3 ulozene AO se pouzije: Jemne (0,25 / 8) x 1,2 / 2 = 0,3 / 16", ao.variant === "jemne" && blizko(ao.k, 0.3, 0.001) && blizko(ao.r, 16, 0.001), ao);
  await otevriPanel(c.page);
  const pos = await c.page.evaluate((s) => ({ g: document.querySelector(s).value, refl: document.getElementById("vzhledAluRefl").value, rough: document.getElementById("vzhledAluRough").value, k: document.getElementById("vzhledAoK").value, r: document.getElementById("vzhledAoR").value }), selG);
  t("E4 posuvniky v okne ukazuji ulozene hodnoty (lesk 50, odlesky 60, matnost 130, AO sila 120, dosah 200)", pos.g === "50" && pos.refl === "60" && pos.rough === "130" && pos.k === "120" && pos.r === "200", pos);
  await c.page.getByRole("button", { name: "Vrátit výchozí vzhled" }).click();
  for (let i = 0; i < 100 && !(store === null); i++) await c.page.waitForTimeout(100);
  await c.page.waitForTimeout(800);
  mi = await mat(c.page); a1 = await alu(c.page); ao = await aov(c.page);
  const pos2 = await c.page.evaluate((s) => ({ g: document.querySelector(s).value, refl: document.getElementById("vzhledAluRefl").value, k: document.getElementById("vzhledAoK").value }), selG);
  t("E5 Vratit vychozi vzhled: lesk, hlinik i AO zpet (drsnost puvodni, odrazy puvodni, AO sila a dosah varianty), posuvniky 100 %", mi.every((x) => x.rough0 === null || blizko(x.rough, x.rough0, 0.001)) && a1.every((x, i) => blizko(x.rough, a0[i].rough, 0.001) && blizko(x.env, a0[i].env, Math.max(0.01, a0[i].env * 0.04))) && ao.cfg === null && pos2.g === "100" && pos2.refl === "100" && pos2.k === "100", { mi: mi.slice(0, 2), a1: a1.slice(0, 2), ao, pos2 });
  t("E6 stranka bez chyb v konzoli", c.errs.length === 0, c.errs);
  await c.ctx.close();

  console.log("\n## F) neplatne ulozene hodnoty: viewer je omezi nebo zahodi, stranka nespadne");
  vzhledGet = Object.assign({}, DEF, { lesk: { [hex.orig]: 99, zle: 1, "#112233": "x" }, alu_cfg: { refl: "x", rough: 99 }, ao_cfg: { k: 99, r: -5 } });
  c = await otevri();
  mi = await mat(c.page); a1 = await alu(c.page); ao = await aov(c.page);
  t("F1 lesk nad mez (99) se omezi na 200 % (drsnost = puvodni^2), text a necislo se zahodi", mi.filter((x) => x.orig === hex.orig).every((x) => blizko(x.rough, Math.max(0.02, Math.pow(hex.rough0, 2)))), mi.filter((x) => x.orig === hex.orig));
  t("F2 hlinik: text (refl) = 100 %, matnost 99 -> omezena na 200 %", a1.every((x, i) => blizko(x.rough, Math.min(1, a0[i].rough * 2)) && blizko(x.env, a0[i].env, Math.max(0.01, a0[i].env * 0.04))), { a0: a0.slice(0, 2), a1: a1.slice(0, 2) });
  t("F3 AO: sila 99 -> 200 %, dosah -5 -> 25 % (omezeno na meze), stranka bez chyb", ao.cfg && ao.cfg.k === 2 && ao.cfg.r === 0.25 && c.errs.length === 0, [ao, c.errs]);
  await c.ctx.close();
  vzhledGet = null;

  console.log("\n## G) server pred nasazenim (stary): nova cast okna je schovana a ulozeni nese jen stara pole (staticke soubory jsou zive driv nez api/*.py)");
  stareApi = true; store = null;
  c = await otevri();
  await otevriPanel(c.page);
  const sch = await c.page.evaluate(() => { const vis = (e) => !!e && getComputedStyle(e).display !== "none"; return { lesk: vis(document.getElementById("vzhledLesk")), gl: [...document.querySelectorAll("#vzhledPal .vzh-gl")].some(vis), imp: vis(document.getElementById("vzhledImport")), trida: document.getElementById("vzhledPanel").classList.contains("nove-api"), sat: vis(document.getElementById("vzhledSat")), picker: !!document.querySelector("#vzhledEnv select") }; });
  t("G1 stary server: sekce Odlesky a AO, lesk u barev i pridani HDRI jsou schovane; sytost a vyber HDRI zustavaji", !sch.lesk && !sch.gl && !sch.imp && !sch.trida && sch.sat && sch.picker, sch);
  const nb = puts.length;
  const telo = await ulozPut(c.page);
  t("G2 stary server: ulozeni neposle lesk / alu_cfg / ao_cfg (server by je odmitl) a projde", !!telo && puts.length === nb + 1 && !STARE.some((k) => k in telo) && "env" in telo && await c.page.evaluate(() => /Uloženo/.test(document.getElementById("vzhledEnv").innerText)), telo);
  t("G3 stranka bez chyb v konzoli", c.errs.length === 0, c.errs);
  await c.ctx.close();
  stareApi = false;

  console.log(`\n${total - bad}/${total} kontrol OK` + (bad ? `; SELHALO ${bad}` : ""));
  await browser.close(); server.close(); fs.rmSync(TMP, { recursive: true, force: true });
  process.exit(bad ? 1 : 0);
})();
