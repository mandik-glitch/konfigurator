// Okno "Vzhled nabidek" v kontrolni scene: PRIDANI HDRI ZE SDILENEHO DISKU (viewer 1.15.0 + kontrola.html; bot10, 2026-10-07; Robert: "moznost pridat dalsi hdri ze sdileneho disku").
// SKUTECNA stranka kontrola.html (rezim=nabidka) + SKUTECNY viewer3d.js + env-picker.js v prohlizeci proti falesnemu serveru (zdroje, import, mazani, GET/PUT vzhledu, soubory HDRI; nic se nezapisuje).
// Doplnena HDRI se v atrape servíruji ze souboru knihovny (tv_studio_1024/256.hdr - platne RGBE), takze viewer opravdu nacte a pouzije "nove" prostredi.
// Kandidat pred nasazenim: WEB_DIR=<prekryv webapp> node test_env_import_ui.js
const { chromium } = require("/opt/konfigurator/node_modules/playwright");
const http = require("http"), fs = require("fs"), path = require("path"), os = require("os"), cp = require("child_process");
const REPO = path.resolve(__dirname, "..", ".."), WEB = process.env.WEB_DIR || path.join(REPO, "webapp");
const TMP = fs.mkdtempSync(path.join(os.tmpdir(), "envui_glb_"));
cp.execFileSync(path.join(REPO, "api/venv/bin/python3"), ["-B", path.join(REPO, "scripts/2026-10-06_v3d_rady_testy/vyrob_glb.py"), TMP], { stdio: ["ignore", "pipe", "inherit"] });
const ENVDIR = path.join(REPO, "webapp/js/v3d/env");
const MIME = { ".html": "text/html; charset=utf-8", ".js": "application/javascript", ".css": "text/css", ".glb": "model/gltf-binary", ".json": "application/json", ".png": "image/png", ".jpg": "image/jpeg", ".hdr": "application/octet-stream", ".svg": "image/svg+xml" };
const BUILTIN = ["crossfit", "tv_studio", "berg_inner", "teufelsberg", "mistnost"];
const DEF = { env: null, alu: null, ao: null, sat: null, barvy: null, lesk: null, alu_cfg: null, ao_cfg: null };
let store = null, extra = [], zdroje = [], importChyba = null, importZpozdeni = 0, smazChyba = null, zdrojeChyba = null, hdriExtraGet = null;
const log = []; const puts = [];
const server = http.createServer((req, res) => {
  const p = decodeURIComponent(new URL(req.url, "http://x").pathname);
  log.push(req.method + " " + p);
  const J = (st, o) => { res.writeHead(st, { "Content-Type": "application/json" }); res.end(typeof o === "string" ? o : JSON.stringify(o)); };
  const body = (cb) => { let b = ""; req.on("data", (c) => { b += c; }); req.on("end", () => cb(b)); };
  let m = /^\/api\/kontrola-scena\/vd\/(\d+)$/.exec(p);
  if (m) return J(200, { product: { id: +m[1], name: "Atrapa karta " + m[1] } });
  if (/^\/api\/kontrola-scena\/v3d\/[\d+]+\.glb$/.test(p)) { res.writeHead(200, { "Content-Type": "model/gltf-binary" }); return res.end(fs.readFileSync(path.join(TMP, "dvoustrane.glb"))); }
  if (p === "/api/public/v3d-vzhled") return J(200, Object.assign({}, store || DEF, { hdri_extra: hdriExtraGet || extra.map((z) => ({ key: z.key, label: z.label, mul0: z.mul0, rot0_deg: 0, url: "/api/public/v3d-env/" + z.key + "_1024.hdr", lo: "/api/public/v3d-env/" + z.key + "_256.hdr" })) }));
  if (p === "/api/admin/v3d-vzhled" && req.method === "PUT") return body((b) => {
    puts.push(b); const j = JSON.parse(b);
    if (j && j.env && !BUILTIN.concat(extra.map((z) => z.key)).includes(j.env.hdri)) return J(400, { error: "env.hdri musi byt jedno z: " + BUILTIN.join(", ") });
    store = j === null ? null : Object.assign({}, DEF, j); J(200, store || DEF);
  });
  if (p === "/api/admin/v3d-env/zdroje") {
    if (zdrojeChyba) return J(zdrojeChyba.status, { error: zdrojeChyba.error });
    return J(200, { max: 12, pocet: extra.length, max_zdroj_mb: 150, zdroje: zdroje.filter((z) => !extra.some((e) => e.source_id === z.id)), extra: extra.map((z) => ({ key: z.key, label: z.label, mul0: z.mul0, source_name: z.source_name, created: "2026-10-07 12:00" })) });
  }
  if (p === "/api/admin/v3d-env/import" && req.method === "POST") return body((b) => {
    const j = JSON.parse(b); puts.push("IMPORT " + b);
    const z = zdroje.find((x) => x.id === j.file_id);
    const dokonci = () => {
      if (importChyba) return J(importChyba.status, { error: importChyba.error });
      if (!z) return J(404, { error: "Soubor na Sdíleném disku nenalezen." });
      const key = z.filename.toLowerCase().replace(/_\d+k\.hdr$/, "").replace(/[^a-z0-9]+/g, "_");
      const polozka = { key, label: j.label || z.navrh_label, mul0: 0.8, source_id: z.id, source_name: z.filename };
      extra.push(polozka);
      J(200, { ok: true, polozka: { key, label: polozka.label, mul0: 0.8, rot0_deg: 0, url: "/api/public/v3d-env/" + key + "_1024.hdr", lo: "/api/public/v3d-env/" + key + "_256.hdr" } });
    };
    importZpozdeni ? setTimeout(dokonci, importZpozdeni) : dokonci();
  });
  m = /^\/api\/admin\/v3d-env\/([a-z0-9_]+)$/.exec(p);
  if (m && req.method === "DELETE") {
    puts.push("DELETE " + m[1]);
    if (smazChyba) return J(smazChyba.status, { error: smazChyba.error });
    if (store && store.env && store.env.hdri === m[1]) return J(409, { error: "Tohle HDRI je uložené ve vzhledu nabídek – nejdřív ulož jiné HDRI (nebo vrať výchozí vzhled)." });
    extra = extra.filter((z) => z.key !== m[1]); return J(200, { ok: true });
  }
  m = /^\/api\/public\/v3d-env\/([a-z0-9_]+)_(1024|256)\.hdr$/.exec(p);
  if (m) { if (!extra.some((z) => z.key === m[1]) && !(hdriExtraGet || []).some((z) => z.key === m[1])) { res.writeHead(404); return res.end("nf"); } res.writeHead(200, { "Content-Type": "application/octet-stream" }); return res.end(fs.readFileSync(path.join(ENVDIR, "tv_studio_" + m[2] + ".hdr"))); }
  if (p.startsWith("/api/")) return J(404, {});
  const f = path.join(WEB, p);
  fs.readFile(f, (e, d) => { if (e) { res.writeHead(404); return res.end("nf"); } res.writeHead(200, { "Content-Type": MIME[path.extname(f)] || "application/octet-stream", "Cache-Control": "no-store" }); res.end(d); });
});
let bad = 0, total = 0;
const t = (name, cond, detail) => { total++; if (!cond) bad++; console.log(`[${cond ? "OK   " : "CHYBA"}] ${name}${!cond && detail !== undefined ? " | " + (typeof detail === "string" ? detail : JSON.stringify(detail)).slice(0, 700) : ""}`); };
const RESET = () => { store = null; extra = []; puts.length = 0; log.length = 0; importChyba = null; importZpozdeni = 0; smazChyba = null; zdrojeChyba = null; hdriExtraGet = null; zdroje = [
  { id: 11, filename: "Old_Hall_4k.hdr", size_bytes: 25000000, folder: "Rendering / HDRi", moc_velke: false, navrh_label: "Old hall" },
  { id: 12, filename: "obri_16k.hdr", size_bytes: 400000000, folder: "Rendering / HDRi", moc_velke: true, navrh_label: "Obri" },
  { id: 13, filename: "Sky_2k.hdr", size_bytes: 6000000, folder: "Kořen disku", moc_velke: false, navrh_label: "Sky" }]; };
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
    await page.waitForTimeout(1200);
    return { ctx, page, errs };
  }
  const otevriPanel = async (page) => { await page.click("#vzhledBtn"); await page.waitForSelector("#vzhledPal .vzh-sw", { timeout: 30000 }); await page.waitForSelector("#vzhledEnv select", { timeout: 30000 }); };
  const optPicker = (page) => page.evaluate(() => [...document.querySelectorAll("#vzhledEnv select option")].map((o) => o.value + "=" + o.textContent));
  const stav = (page) => page.evaluate(() => { const s = window.__v3d.state(); return { env: s.env, hdri: s.envCfg && s.envCfg.hdri }; });
  const cekej = (page, fn, arg) => page.waitForFunction(fn, arg, { timeout: 20000, polling: 100 }).catch(() => {});

  console.log("\n## A) pridani HDRI ze Sdileneho disku");
  RESET();
  let c = await otevri();
  await otevriPanel(c.page);
  t("A1 tlacitko 'Pridat HDRI ze Sdileneho disku' je vidět (server zna nova pole), dialog je zavreny", await c.page.evaluate(() => { const b = document.getElementById("vzhledImportBtn"), x = document.getElementById("vzhledImportBox"); return getComputedStyle(b).display !== "none" && x.hidden; }));
  await c.page.click("#vzhledImportBtn");
  await cekej(c.page, () => document.querySelectorAll("#vzhledImportSel option").length >= 2);
  const sel = await c.page.evaluate(() => ({ opts: [...document.querySelectorAll("#vzhledImportSel option")].map((o) => ({ v: o.value, t: o.textContent, d: o.disabled })), val: document.getElementById("vzhledImportSel").value, lab: document.getElementById("vzhledImportLabel").value, go: document.getElementById("vzhledImportGo").disabled }));
  t("A2 seznam souboru: 3 polozky se slozkou a velikosti, 16k je neaktivni 'moc velke', predvybran prvni pouzitelny, nazev predvyplnen, Pridat aktivni", sel.opts.length === 3 && /Rendering \/ HDRi \/ Old_Hall_4k\.hdr \(24 MB\)/.test(sel.opts[0].t) && sel.opts[1].d && /moc velké/.test(sel.opts[1].t) && !sel.opts[0].d && sel.val === "11" && sel.lab === "Old hall" && !sel.go, sel);
  await c.page.selectOption("#vzhledImportSel", "13");
  t("A3 zmena souboru predvyplni nazev podle nej", (await c.page.inputValue("#vzhledImportLabel")) === "Sky");
  await c.page.selectOption("#vzhledImportSel", "11");
  await c.page.fill("#vzhledImportLabel", "Stará hala");
  importZpozdeni = 600;
  await c.page.click("#vzhledImportGo");
  await c.page.waitForTimeout(250);
  t("A4 behem prevodu je videt hlaska a tlacitko je neaktivni", await c.page.evaluate(() => /Převádím HDRI/.test(document.getElementById("vzhledImportSt").textContent) && document.getElementById("vzhledImportGo").disabled));
  await cekej(c.page, () => /Přidáno/.test(document.getElementById("vzhledImportSt").textContent));
  t("A5 POST import nese {file_id: 11, label: 'Stará hala'}", puts.includes('IMPORT {"file_id":11,"label":"Stará hala"}'), puts);
  const op = await optPicker(c.page);
  t("A6 seznam HDRI v okne obsahuje nove HDRI 'Stará hala' (pred volbou Mistnost)", op.includes("old_hall=Stará hala") && op.indexOf("old_hall=Stará hala") < op.findIndex((x) => x.startsWith("mistnost=")), op);
  await cekej(c.page, () => window.__v3d.state().envCfg && window.__v3d.state().envCfg.hdri === "old_hall");
  let st = await stav(c.page);
  t("A7 nove HDRI se hned ukaze v nahledu (viewer: prostredi custom, hdri old_hall) a vybrane je i v seznamu", st.env === "custom" && st.hdri === "old_hall" && (await c.page.inputValue("#vzhledEnv select")) === "old_hall", st);
  await c.page.waitForTimeout(1500);
  t("A8 viewer opravdu stahl velke HDRI z /api/public/v3d-env/ (explicitni volba prostredi pousti plne HDRI hned, nahled _256 netreba)", log.includes("GET /api/public/v3d-env/old_hall_1024.hdr"), log.filter((x) => /v3d-env/.test(x)));
  const seznam = await c.page.evaluate(() => [...document.querySelectorAll("#vzhledImportSeznam .vzh-imp-it")].map((r) => r.textContent.replace(/\s+/g, " ").trim()));
  t("A9 pod dialogem je seznam doplnenych HDRI s nazvem zdroje a tlacitkem Smazat; nabidka zdroju uz neobsahuje pridany soubor", seznam.length === 1 && /Stará hala \(Old_Hall_4k\.hdr\)\s*Smazat/.test(seznam[0]) && (await c.page.evaluate(() => [...document.querySelectorAll("#vzhledImportSel option")].map((o) => o.value))).join() === "12,13", seznam);
  t("A10 stranka bez chyb v konzoli", c.errs.length === 0, c.errs);

  console.log("\n## B) ulozeni a nacteni pri otevreni");
  await c.page.getByRole("button", { name: "Uložit vzhled pro nabídky" }).click();
  for (let i = 0; i < 100 && !puts.some((x) => /"hdri":"old_hall"/.test(x)); i++) await c.page.waitForTimeout(100);
  t("B1 PUT vzhledu nese env.hdri 'old_hall' (server ho prijal: klic je v evidenci)", !!store && store.env && store.env.hdri === "old_hall", puts.filter((x) => !/IMPORT/.test(x)));
  await c.ctx.close();
  log.length = 0;
  c = await otevri();
  await otevriPanel(c.page);
  await c.page.waitForTimeout(1500);
  st = await stav(c.page);
  const op2 = await optPicker(c.page);
  t("B2 po obnoveni stranky: server vraci hdri_extra, viewer se otevre s ulozenym HDRI old_hall (prostredi custom) a seznam ho nabizi", st.env === "custom" && st.hdri === "old_hall" && op2.includes("old_hall=Stará hala"), { st, op2 });
  t("B2b pri otevreni viewer stahne nejdriv maly nahled _256, po modelu velke _1024 (stejne jako u vestavenych HDRI)", log.includes("GET /api/public/v3d-env/old_hall_256.hdr") && log.includes("GET /api/public/v3d-env/old_hall_1024.hdr"), log.filter((x) => /v3d-env/.test(x)));
  t("B3 nacteni bez chyb v konzoli", c.errs.length === 0, c.errs);

  console.log("\n## C) mazani");
  await c.page.click("#vzhledImportBtn");
  await cekej(c.page, () => document.querySelectorAll("#vzhledImportSeznam [data-smazat]").length === 1);
  await c.page.click('#vzhledImportSeznam [data-smazat="old_hall"]');
  await cekej(c.page, () => /uložené ve vzhledu/.test(document.getElementById("vzhledImportSt").textContent));
  t("C1 HDRI ulozene ve vzhledu nabidek nejde smazat: zobrazi se veta ze serveru, polozka zustane", await c.page.evaluate(() => /uložené ve vzhledu nabídek/.test(document.getElementById("vzhledImportSt").textContent) && document.querySelectorAll("#vzhledImportSeznam [data-smazat]").length === 1 && document.getElementById("vzhledImportSt").classList.contains("err")));
  await c.page.getByRole("button", { name: "Vrátit výchozí vzhled" }).click();
  for (let i = 0; i < 100 && store !== null; i++) await c.page.waitForTimeout(100);
  await c.page.click('#vzhledImportSeznam [data-smazat="old_hall"]');
  await cekej(c.page, () => /Smazáno/.test(document.getElementById("vzhledImportSt").textContent));
  t("C2 po vraceni vychoziho vzhledu jde smazat: 'Smazano', seznam doplnenych je prazdny, soubor je zase v nabidce zdroju", await c.page.evaluate(() => document.querySelectorAll("#vzhledImportSeznam [data-smazat]").length === 0 && /Smazáno: Stará hala/.test(document.getElementById("vzhledImportSt").textContent) && [...document.querySelectorAll("#vzhledImportSel option")].some((o) => o.value === "11")));
  t("C3 DELETE odeslan na spravny klic", puts.filter((x) => x === "DELETE old_hall").length === 2, puts);
  await c.ctx.close();

  console.log("\n## D) chyby");
  RESET(); importChyba = { status: 400, error: "Převod HDRI selhal: HDRI musi byt equirectangular 2:1 (tohle je 3072x1024)" };
  c = await otevri(); await otevriPanel(c.page);
  await c.page.click("#vzhledImportBtn"); await cekej(c.page, () => document.querySelectorAll("#vzhledImportSel option").length >= 2);
  await c.page.click("#vzhledImportGo");
  await cekej(c.page, () => /equirectangular/.test(document.getElementById("vzhledImportSt").textContent));
  t("D1 chyba importu: ukaze se ceska veta ze serveru (cervene), tlacitko Pridat je zase aktivni, seznam HDRI se nezmenil", await c.page.evaluate(() => /equirectangular 2:1/.test(document.getElementById("vzhledImportSt").textContent) && document.getElementById("vzhledImportSt").classList.contains("err") && !document.getElementById("vzhledImportGo").disabled && ![...document.querySelectorAll("#vzhledEnv select option")].some((o) => /old/.test(o.value))));
  t("D2 po chybe nic nezustalo v knihovne vieweru", (await optPicker(c.page)).length === 5);
  await c.ctx.close();
  RESET(); zdrojeChyba = { status: 403, error: "Nemate opravneni k teto akci." };
  c = await otevri(); await otevriPanel(c.page);
  await c.page.click("#vzhledImportBtn");
  await cekej(c.page, () => /oprávnění|opravneni/.test(document.getElementById("vzhledImportSt").textContent));
  t("D3 bez opravneni (403): hlaska u dialogu, zbytek okna Vzhled nabidek funguje dal", await c.page.evaluate(() => document.getElementById("vzhledImportSt").classList.contains("err") && document.querySelectorAll("#vzhledEnv select option").length === 5), await c.page.evaluate(() => document.getElementById("vzhledImportSt").textContent));
  await c.ctx.close();
  RESET(); zdroje = [];
  c = await otevri(); await otevriPanel(c.page);
  await c.page.click("#vzhledImportBtn");
  await cekej(c.page, () => /Nahraj \.hdr/.test(document.getElementById("vzhledImportSt").textContent));
  t("D4 na Sdilenem disku neni zadny novy .hdr: napoveda 'Nahraj .hdr...', Pridat neaktivni", await c.page.evaluate(() => /Nahraj \.hdr na Sdílený disk/.test(document.getElementById("vzhledImportSt").textContent) && document.getElementById("vzhledImportGo").disabled));
  await c.ctx.close();

  console.log("\n## E) neplatne hdri_extra ze serveru: viewer je zahodi, stranka nespadne");
  RESET();
  hdriExtraGet = [{ key: "dobre", label: "Dobré", mul0: 1.1, rot0_deg: 10, url: "/api/public/v3d-env/dobre_1024.hdr", lo: "/api/public/v3d-env/dobre_256.hdr" },
    { key: "cizi", label: "Cizi", mul0: 1, rot0_deg: 0, url: "https://evil.example/x_1024.hdr", lo: null }, { key: "Velke", label: "V", mul0: 1, url: "/api/public/v3d-env/velke_1024.hdr" },
    { key: "crossfit", label: "Prepis", mul0: 1, url: "/api/public/v3d-env/crossfit_1024.hdr" }, { key: "mistnost", label: "M", mul0: 1, url: "/api/public/v3d-env/mistnost_1024.hdr" },
    { key: "bezurl", label: "B", mul0: 1 }, "text", null, { key: "trav", label: "T", mul0: 1, url: "/api/public/v3d-env/../../etc/passwd" }, { key: "lo_cizi", label: "L", mul0: 1, url: "/api/public/v3d-env/lo_cizi_1024.hdr", lo: "//evil.example/a.hdr" }];
  c = await otevri(); await otevriPanel(c.page);
  const op3 = await optPicker(c.page);
  t("E1 do knihovny se dostane jen 'dobre' (cizi URL, velka pismena, vestavene a duplicitni klice, chybejici URL, pruchod adresari se zahodi)", op3.join("|") === "crossfit=Crossfit gym (HDRI karet)|tv_studio=TV studio|berg_inner=Berg inner|teufelsberg=Teufelsberg lookout|dobre=Dobré|mistnost=Místnost (bez HDRI)", op3);
  t("E2 stranka bez chyb v konzoli", c.errs.length === 0, c.errs);
  await c.ctx.close();

  console.log(`\n${total - bad}/${total} kontrol OK` + (bad ? `; SELHALO ${bad}` : ""));
  await browser.close(); server.close(); fs.rmSync(TMP, { recursive: true, force: true });
  process.exit(bad ? 1 : 0);
})();
