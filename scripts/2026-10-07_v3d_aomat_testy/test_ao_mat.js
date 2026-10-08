// 3D prohlizec online nabidky / kontrolni sceny: AO PO KOMPONENTECH + AUTOMATICKE UKLADANI vzhledu (viewer 1.16.0; bot10, 2026-10-07).
// Robert: "nenasel jsem AO pro jednotlive komponenty, jen pro hlinikove profily, doplnit" + "upravy barev a lesku chci aby se ulozily i pro ostatni dalsi nabidky".
// SKUTECNA stranka kontrola.html (rezim=nabidka) + SKUTECNY viewer3d.js + env-picker.js v prohlizeci proti falesnemu serveru (GET/PUT /api/public|admin/v3d-vzhled; nic se nezapisuje).
// A) pixely: vaha AO materialu (matConfig.ao podle puvodni barvy) a hliniku (aluConfig.ao) tmavne / zesvetli JEN dily teto barvy (snimky snapshot() proti sobe, purpurova barva jako maska)
// B) posuvniky AO u kazde barvy a Hlinik - AO v okne Vzhled nabidek  C) automaticke ukladani (debounce, jedno PUT, poradi, chyba, tlacitko Ulozit, zavreni stranky)
// D) server bez ao_mat (pred nasazenim): nahled ano, PUT bez novych klicu  E) ulozene upravy barev mimo scenu (seznam + Zrusit)  F) nacteni ulozeneho pri otevreni
// Kandidat pred nasazenim: WEB_DIR=<prekryv webapp> node test_ao_mat.js
const { chromium } = require("/opt/konfigurator/node_modules/playwright");
const http = require("http"), fs = require("fs"), path = require("path"), os = require("os"), cp = require("child_process");
const REPO = path.resolve(__dirname, "..", ".."), WEB = process.env.WEB_DIR || path.join(REPO, "webapp");
const OVERRIDE = JSON.parse(process.env.WEB_OVERRIDE || "{}");       // {"/js/v3d/viewer3d.js": "/tmp/rozbity.js"}: mutacni skript podstrcuje rozbite soubory
const ONLY = (process.env.ONLY || "ABCDEFG").toUpperCase();               // podmnozina oddilu, napr. ONLY=AB
const TMP = fs.mkdtempSync(path.join(os.tmpdir(), "aomat_glb_"));
cp.execFileSync(path.join(REPO, "api/venv/bin/python3"), ["-B", path.join(REPO, "scripts/2026-10-06_v3d_rady_testy/vyrob_glb.py"), TMP], { stdio: ["ignore", "pipe", "inherit"] });
const MIME = { ".html": "text/html; charset=utf-8", ".js": "application/javascript", ".css": "text/css", ".glb": "model/gltf-binary", ".json": "application/json", ".png": "image/png", ".jpg": "image/jpeg", ".hdr": "application/octet-stream", ".svg": "image/svg+xml" };
const DEF2 = { env: null, alu: null, ao: null, sat: null, barvy: null, lesk: null, ao_mat: null, alu_cfg: null, ao_cfg: null };
const S = { level: 2, store: null, putDelay: 0, putFail: null, inflight: 0, inflightMax: 0, puts: [] };       // level 2 = server s ao_mat, 1 = bez ao_mat (pred nasazenim), 0 = bez lesku a hdri_extra (uplne stary)
const trim = (o) => { const z = Object.assign({}, o); if (S.level < 2) delete z.ao_mat; if (S.level < 1) { delete z.lesk; delete z.alu_cfg; delete z.ao_cfg; } return z; };
const server = http.createServer((req, res) => {
  const p = decodeURIComponent(new URL(req.url, "http://x").pathname);
  const J = (st, o) => { res.writeHead(st, { "Content-Type": "application/json" }); res.end(typeof o === "string" ? o : JSON.stringify(o)); };
  let m = /^\/api\/kontrola-scena\/vd\/(\d+)$/.exec(p);
  if (m) return J(200, { product: { id: +m[1], name: "Atrapa karta " + m[1] } });
  if (/^\/api\/kontrola-scena\/v3d\/[\d+]+\.glb$/.test(p)) { res.writeHead(200, { "Content-Type": "model/gltf-binary" }); return res.end(fs.readFileSync(path.join(TMP, "dvoustrane.glb"))); }
  if (p === "/api/public/v3d-vzhled") { const z = trim(Object.assign({}, DEF2, S.store || {})); if (S.level >= 1) z.hdri_extra = []; return J(200, z); }
  if (p === "/api/admin/v3d-vzhled" && req.method === "PUT") {
    let b = ""; req.on("data", (c) => { b += c; }); req.on("end", () => {
      const j = JSON.parse(b); S.puts.push({ t: Date.now(), body: j, keepalive: req.headers["content-length"] }); S.inflight++; S.inflightMax = Math.max(S.inflightMax, S.inflight);
      setTimeout(() => {
        S.inflight--;
        if (S.putFail) return J(S.putFail.status, { error: S.putFail.error });
        const nove = j && ((S.level < 2 && (("ao_mat" in j) || (j.alu_cfg && "ao" in j.alu_cfg))) || (S.level < 1 && ["lesk", "alu_cfg", "ao_cfg"].some((k) => k in j)));
        if (nove) return J(400, { error: "neznamy klic (stary server)" });
        S.store = j === null ? null : Object.assign({}, DEF2, j, j.alu_cfg ? { alu_cfg: Object.assign({ refl: 1, rough: 1, ao: 1 }, j.alu_cfg) } : {});
        J(200, trim(S.store || DEF2));
      }, S.putDelay);
    });
    return;
  }
  if (p.startsWith("/api/")) return J(404, {});
  const f = OVERRIDE[p] || path.join(WEB, p);
  fs.readFile(f, (e, d) => { if (e) { res.writeHead(404); return res.end("nf"); } res.writeHead(200, { "Content-Type": MIME[path.extname(f)] || "application/octet-stream", "Cache-Control": "no-store" }); res.end(d); });
});
let bad = 0, total = 0;
const t = (name, cond, detail) => { total++; if (!cond) bad++; console.log(`[${cond ? "OK   " : "CHYBA"}] ${name}${!cond && detail !== undefined ? " | " + (typeof detail === "string" ? detail : JSON.stringify(detail)).slice(0, 900) : ""}`); };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const blizko = (a, b, tol) => Math.abs(a - b) <= (tol === undefined ? 0.011 : tol);
(async () => {
  await new Promise((r) => server.listen(0, "127.0.0.1", r));
  const base = "http://127.0.0.1:" + server.address().port;
  const browser = await chromium.launch({ args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
  async function otevri(extra) {
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 }, locale: "cs-CZ" });
    await ctx.addInitScript(() => {          // jen test: verejne API instance prohlizece (V3D.mount vraci api, stranka ho drzi v uzaveru) -> window.__api
      let V;
      const zachyt = (o) => { let fn; Object.defineProperty(o, "mount", { configurable: true, enumerable: true, get() { return fn; }, set(f) { fn = typeof f === "function" ? function () { const a = f.apply(this, arguments); window.__api = a; return a; } : f; } }); };
      Object.defineProperty(window, "V3D", { configurable: true, get() { return V; }, set(o) { V = o; if (o && typeof o === "object") zachyt(o); } });
    });
    const page = await ctx.newPage(); const errs = [];
    page.on("pageerror", (e) => errs.push(e.message));
    page.on("console", (m) => { if (m.type() === "error" && !/favicon|Failed to load resource/.test(m.text())) errs.push("console: " + m.text()); });
    await page.goto(`${base}/kontrola.html?items=vd:4965+4964&rezim=nabidka${extra || ""}`, { waitUntil: "load" });
    await page.waitForFunction(() => /pohyblivých dílů/.test(document.querySelector("#topbar").innerText), null, { timeout: 120000 });
    await page.waitForFunction(() => window.__v3d && window.__v3d.state().ready, null, { timeout: 60000 });
    await page.waitForTimeout(1500);
    return { ctx, page, errs };
  }
  const mat = (page) => page.evaluate(() => window.__v3d.matInfo());
  const alu = (page) => page.evaluate(() => window.__v3d.aluInfo());
  const aov = (page) => page.evaluate(() => window.__v3d.aoValues());
  const matCfg = (page) => page.evaluate(() => window.__api.getMatConfig());
  const otevriPanel = async (page) => { await page.click("#vzhledBtn"); await page.waitForSelector("#vzhledPal .vzh-sw", { timeout: 30000 }); };
  const nastav = async (page, sel, v) => { await page.locator(sel).fill(String(v)); await page.waitForTimeout(250); };
  const hudAO = async (page, k) => { await page.click(`[data-grp="ao"][data-v="${k}"]`); await page.waitForTimeout(500); };
  const cekejPut = async (n, ms) => { for (let i = 0; i < Math.ceil((ms || 4000) / 50) && S.puts.length < n; i++) await sleep(50); return S.puts.length >= n; };
  const autoSt = (page) => page.evaluate(() => { const e = document.getElementById("vzhledAutoSt"); return { txt: e.textContent, cls: e.className }; });

  // ---------- pomocnici pro snimky (v prohlizeci; snapshot() kresli presne to, co vidi zakaznik, vc. AO)
  const pripravSnimky = (page) => page.evaluate(() => {
    window.__T = {
      snaps: {},
      async snap(name) {
        const url = await window.__api.snapshot({ width: 480 });
        await new Promise((res) => { const im = new Image(); im.onload = () => { const c = document.createElement("canvas"); c.width = im.width; c.height = im.height; const g = c.getContext("2d"); g.drawImage(im, 0, 0); window.__T.snaps[name] = { w: c.width, h: c.height, d: g.getImageData(0, 0, c.width, c.height).data }; res(); }; im.src = url; });
        return true;
      },
      zmeny(a, b, tol) {        // pixely, ktere se mezi snimky lisi o vic nez tol (nejvetsi rozdil kanalu); prumerny jas v a / v b
        const A = this.snaps[a].d, B = this.snaps[b].d; let n = 0, la = 0, lb = 0;
        for (let i = 0; i < A.length; i += 4) {
          const dm = Math.max(Math.abs(A[i] - B[i]), Math.abs(A[i + 1] - B[i + 1]), Math.abs(A[i + 2] - B[i + 2]));
          if (dm > (tol == null ? 2 : tol)) { n++; la += A[i] + A[i + 1] + A[i + 2]; lb += B[i] + B[i + 1] + B[i + 2]; }
        }
        return { n, lumA: n ? la / n / 3 : 0, lumB: n ? lb / n / 3 : 0 };
      },
      vMasce(a, b, mag) {       // kolik pixelu zmenenych mezi a a b je v snimku mag purpurovych (R a B vyrazne nad G)
        const A = this.snaps[a].d, B = this.snaps[b].d, M = this.snaps[mag].d; let n = 0, vMag = 0;
        for (let i = 0; i < A.length; i += 4) {
          const dm = Math.max(Math.abs(A[i] - B[i]), Math.abs(A[i + 1] - B[i + 1]), Math.abs(A[i + 2] - B[i + 2]));
          if (dm > 2) { n++; if (M[i] > 30 && M[i] > M[i + 1] * 1.8 && M[i + 2] > M[i + 1] * 1.8) vMag++; }
        }
        return { n, vMag };
      },
      prunik(a1, b1, a2, b2) {  // kolik pixelu se zmenilo v obou dvojicich snimku zaroven
        const A1 = this.snaps[a1].d, B1 = this.snaps[b1].d, A2 = this.snaps[a2].d, B2 = this.snaps[b2].d; let n1 = 0, n2 = 0, both = 0;
        for (let i = 0; i < A1.length; i += 4) {
          const d1 = Math.max(Math.abs(A1[i] - B1[i]), Math.abs(A1[i + 1] - B1[i + 1]), Math.abs(A1[i + 2] - B1[i + 2])) > 2;
          const d2 = Math.max(Math.abs(A2[i] - B2[i]), Math.abs(A2[i + 1] - B2[i + 1]), Math.abs(A2[i + 2] - B2[i + 2])) > 2;
          if (d1) n1++; if (d2) n2++; if (d1 && d2) both++;
        }
        return { n1, n2, both };
      },
    };
  });
  const snap = (page, name) => page.evaluate((n) => window.__T.snap(n), name);
  const zmeny = (page, a, b) => page.evaluate(([x, y]) => window.__T.zmeny(x, y), [a, b]);
  const nastavMat = (page, cfg) => page.evaluate((c) => { window.__api.setMatConfig(c); return window.__api.getMatConfig(); }, cfg);

  let c = null;
  if (ONLY.includes("A")) {
  console.log("\n## A) vaha AO materialu a hliniku (pixely)");
  S.level = 2; S.store = null;
  c = await otevri();
  await hudAO(c.page, "silne");
  await pripravSnimky(c.page);
  let ao = await aov(c.page);
  t("A0 AO Silne je zapnute, bez vah: zadny vahovy pruchod (wPasses 0, wMeshes 0)", ao.variant === "silne" && ao.wPasses === 0 && ao.wMeshes === 0, ao);
  await snap(c.page, "zaklad"); await snap(c.page, "zaklad2");
  let z = await zmeny(c.page, "zaklad", "zaklad2");
  t("A1 stejny stav = stejny snimek (kresleni je deterministicke, AO se nemeni)", z.n === 0, z);
  ao = await aov(c.page);
  t("A1b bez vah se po snimcich stale nekresli vahovy pruchod (aoValues.wPasses 0)", ao.wPasses === 0, ao);
  const mi0 = await mat(c.page);
  t("A2 vsechny materialy maji vahu 1 (matInfo.aoW) i hlinik (aluInfo.aoW)", mi0.length >= 3 && mi0.every((x) => x.aoW === 1) && (await alu(c.page)).every((x) => x.aoW === 1), mi0.slice(0, 3));
  const pocty = {}; mi0.forEach((x) => { pocty[x.orig] = (pocty[x.orig] || 0) + 1; });
  const kandidati = Object.keys(pocty).sort((a, b) => pocty[b] - pocty[a]).slice(0, 6);
  let X = null, zX = null;
  for (const h of kandidati) {                                       // barva, jejiz AO je v obraze videt (cerna AO neukaze)
    await nastavMat(c.page, { ao: { [h]: 0 } }); await snap(c.page, "w0_" + h);
    const r = await zmeny(c.page, "zaklad", "w0_" + h);
    if (!zX || r.n > zX.n) { X = h; zX = r; }
  }
  t("A3 vaha 0 u nejake barvy (" + X + ") zmeni obraz (aspon 150 pixelu) a zesvetli ho (bez AO jsou dily svetlejsi)", !!X && zX.n >= 150 && zX.lumB > zX.lumA, { X, zX });
  ao = await aov(c.page);
  t("A3b kreslil se vahovy pruchod (wPasses >= 1) a vahu ma aspon jeden mesh (wMeshes >= 1)", ao.wPasses >= 1 && ao.wMeshes >= 1, ao);
  await nastavMat(c.page, { colors: { [X]: "#ff00ff" } }); await snap(c.page, "purpur");
  const mk = await c.page.evaluate(([a, b]) => window.__T.vMasce(a, b, "purpur"), ["zaklad", "w0_" + X]);
  t("A4 zmenily se JEN dily teto barvy: >= 90 % zmenenych pixelu lezi na dilech, ktere jsou v purpurovem snimku purpurove (" + mk.vMag + " z " + mk.n + ")", mk.n > 0 && mk.vMag / mk.n >= 0.9, mk);
  await nastavMat(c.page, { ao: { [X]: 2 } }); await snap(c.page, "w2");
  const z2 = await zmeny(c.page, "zaklad", "w2");
  t("A5 vaha 2 (dvojnasobna AO) obraz ztmavi (" + z2.n + " px, jas " + z2.lumA.toFixed(1) + " -> " + z2.lumB.toFixed(1) + ")", z2.n >= 100 && z2.lumB < z2.lumA, z2);
  await nastavMat(c.page, { ao: { [X]: 1 } }); await snap(c.page, "w1");
  const z1 = await zmeny(c.page, "zaklad", "w1");
  t("A6 vaha 1 = beze zmeny: snimek je stejny jako zaklad (zadne zbytky vahoveho pruchodu)", z1.n === 0, z1);
  const cfgNic = await nastavMat(c.page, { ao: { "#123456": 0 } }); const wp = (await aov(c.page)).wPasses;
  await snap(c.page, "cizi"); const zc = await zmeny(c.page, "zaklad", "cizi");
  t("A7 vaha u barvy, ktera v modelu neni: obraz beze zmeny a vahovy pruchod se nekresli (wMeshes 0)", zc.n === 0 && (await aov(c.page)).wMeshes === 0 && (await aov(c.page)).wPasses === wp && cfgNic.ao["#123456"] === 0, { zc, ao: await aov(c.page) });
  await nastavMat(c.page, null);
  await c.page.evaluate(() => window.__api.setAluConfig({ ao: 0 })); await snap(c.page, "alu0");
  const za = await zmeny(c.page, "zaklad", "alu0");
  t("A8 hlinik: aluConfig.ao 0 zesvetli hlinikove profily (" + za.n + " px), aluInfo.aoW = 0", za.n >= 150 && za.lumB > za.lumA && (await alu(c.page)).every((x) => x.aoW === 0), za);
  const pr = await c.page.evaluate(([a, b, c2, d]) => window.__T.prunik(a, b, c2, d), ["zaklad", "alu0", "zaklad", "w0_" + X]);
  t("A9 zmeny od hliniku a od barvy " + X + " jsou na ruznych dilech (prunik " + pr.both + " z " + Math.min(pr.n1, pr.n2) + " px, nejvyse 10 %)", pr.n1 > 0 && pr.n2 > 0 && pr.both <= 0.1 * Math.min(pr.n1, pr.n2), pr);
  await c.page.evaluate(() => window.__api.setAluConfig({ ao: 2 })); await snap(c.page, "alu2");
  const za2 = await zmeny(c.page, "zaklad", "alu2");
  t("A10 hlinik: aluConfig.ao 2 ztmavi hlinik (jas " + za2.lumA.toFixed(1) + " -> " + za2.lumB.toFixed(1) + ")", za2.n >= 100 && za2.lumB < za2.lumA, za2);
  await c.page.evaluate(() => window.__api.resetAluConfig()); await snap(c.page, "alu1");
  t("A11 resetAluConfig: snimek jako zaklad", (await zmeny(c.page, "zaklad", "alu1")).n === 0);
  // AO vypnute: vahy se ignoruji a model se kresli normalne
  await hudAO(c.page, "vyp"); await snap(c.page, "vyp0");
  await nastavMat(c.page, { ao: { [X]: 0 } }); const wp2 = (await aov(c.page)).wPasses; await snap(c.page, "vyp1");
  t("A12 AO vypnute: vahy se ignoruji (snimek stejny, vahovy pruchod se nekresli)", (await zmeny(c.page, "vyp0", "vyp1")).n === 0 && (await aov(c.page)).wPasses === wp2, await aov(c.page));
  await hudAO(c.page, "silne"); await nastavMat(c.page, null); await snap(c.page, "zpet");
  t("A13 po zapnuti AO a zruseni vah: snimek jako puvodni zaklad (materialy meshu se po vahovem pruchodu vzdy vrati)", (await zmeny(c.page, "zaklad", "zpet")).n === 0);
  await hudAO(c.page, "vyp"); await snap(c.page, "vyp2");
  t("A13b model bez AO po vsech zasazich vypada jako na zacatku (zadny prosakly vahovy material)", (await zmeny(c.page, "vyp0", "vyp2")).n === 0);
  await hudAO(c.page, "silne");
  // normalizace v prohlizeci
  const n1 = await nastavMat(c.page, { ao: { "#ABCDEF": 99, "#112233": -5, zle: 1, "#445566": "x", "#778899": 1, "#aabbcc": 0.456 } });
  t("A14 setMatConfig.ao: hex male, 99 -> 2, -5 -> 0, spatny klic / text se zahodi, 1 se zahodi, zaokrouhleni na 2 mista", JSON.stringify(n1.ao) === JSON.stringify({ "#abcdef": 2, "#112233": 0, "#aabbcc": 0.46 }), n1);
  const n2 = await c.page.evaluate(() => { window.__api.setAluConfig({ ao: 5 }); return window.__api.getAluConfig(); });
  t("A15 setAluConfig.ao 5 -> 2 (strop), ostatni klice beze zmeny", n2.ao === 2 && n2.refl === 1 && n2.rough === 1, n2);
  await c.page.evaluate(() => window.__api.resetAluConfig()); await nastavMat(c.page, null);
  const n3 = await c.page.evaluate(() => ({ m: window.__api.getMatConfig(), a: window.__api.getAluConfig() }));
  t("A16 vychozi getMatConfig / getAluConfig: ao = {} / 1", JSON.stringify(n3.m.ao) === "{}" && n3.a.ao === 1, n3);
  const pal = await c.page.evaluate(() => window.__api.materialPalette());
  t("A17 materialPalette nese ao (vychozi 1) u kazde barvy", pal.length >= 2 && pal.every((p) => p.ao === 1), pal.slice(0, 2));
  t("A18 bez chyb v konzoli", c.errs.length === 0, c.errs);
  await c.ctx.close();

  }
  if (ONLY.includes("B")) {
  console.log("\n## B) posuvniky AO u kazde barvy a Hlinik - AO v okne Vzhled nabidek");
  S.level = 2; S.store = null; S.puts.length = 0;
  c = await otevri();
  await otevriPanel(c.page);
  const radky = await c.page.evaluate(() => [...document.querySelectorAll("#vzhledPal .vzh-sw")].map((r) => ({ hex: r.querySelector("input[type=color]").getAttribute("data-hex"), ao: (r.querySelector("input[data-ao]") || {}).value, txt: r.querySelector(".vzh-gl--ao b") && r.querySelector(".vzh-gl--ao b").textContent, lab: r.querySelector(".vzh-gl--ao span") && r.querySelector(".vzh-gl--ao span").textContent, rst: r.querySelector(".vzh-gl--ao .vzh-gl__r") && !r.querySelector(".vzh-gl--ao .vzh-gl__r").hidden, viditelne: !!(r.querySelector(".vzh-gl--ao") && r.querySelector(".vzh-gl--ao").offsetParent) })));
  t("B1 u kazde barvy je posuvnik AO 100 % (popisek AO), bez tlacitka ↺ a viditelny", radky.length >= 2 && radky.every((r) => r.ao === "100" && r.txt === "100 %" && r.lab === "AO" && !r.rst && r.viditelne), radky.slice(0, 3));
  const hexB = radky[0].hex, selAo = `#vzhledPal input[data-ao="${hexB}"]`;
  let st = await c.page.evaluate(() => window.__v3d.state());
  t("B1b AO je ve scene zapnute (kontrolni scena ma vychozi Stredni), posuvniky jsou aktivni", st.ao !== "vyp" && !(await c.page.evaluate((s) => document.querySelector(s).disabled, selAo)), st.ao);
  await nastav(c.page, selAo, 0);
  let mi = await mat(c.page);
  t("B2 AO 0 % u barvy " + hexB + ": matInfo.aoW = 0 jen u jejich materialu, ostatni 1; getMatConfig().ao = {" + hexB + ": 0}", mi.filter((x) => x.orig === hexB).every((x) => x.aoW === 0) && mi.filter((x) => x.orig !== hexB).every((x) => x.aoW === 1) && (await matCfg(c.page)).ao[hexB] === 0, mi.slice(0, 3));
  t("B2b popisek 0 % a tlacitko ↺ je videt", await c.page.evaluate((s) => { const l = document.querySelector(s).closest(".vzh-gl"); return l.querySelector("b").textContent === "0 %" && !l.querySelector(".vzh-gl__r").hidden; }, selAo));
  await nastav(c.page, selAo, 150);
  t("B3 AO 150 %: aoW = 1,5", (await mat(c.page)).filter((x) => x.orig === hexB).every((x) => blizko(x.aoW, 1.5)));
  await c.page.locator(selAo).locator("xpath=ancestor::label").locator(".vzh-gl__r").click(); await c.page.waitForTimeout(300);
  t("B4 ↺ vrati AO 100 % (aoW 1, posuvnik 100 %, tlacitko schovano, cfg bez klice)", (await mat(c.page)).every((x) => x.aoW === 1) && await c.page.evaluate((s) => { const i = document.querySelector(s); return i.value === "100" && i.closest(".vzh-gl").querySelector(".vzh-gl__r").hidden; }, selAo) && !((await matCfg(c.page)).ao || {})[hexB]);
  await nastav(c.page, "#vzhledAluAo", 30);
  t("B5 Hlinik - AO 30 %: aluInfo.aoW 0,3, getAluConfig().ao 0,3, popisek 30 %", (await alu(c.page)).every((x) => blizko(x.aoW, 0.3)) && blizko((await c.page.evaluate(() => window.__api.getAluConfig())).ao, 0.3) && await c.page.evaluate(() => document.getElementById("vzhledAluAoTxt").textContent === "30 %"));
  const hl = await c.page.evaluate(() => [...document.querySelectorAll("#vzhledLesk .vzh-sat span")].map((x) => x.textContent));
  t("B6 popisky: Hlinik - odlesky / matnost / AO a AO celkove - sila / dosah (jasne rozlisene od AO po komponentech)", ["Hliník – odlesky", "Hliník – matnost", "Hliník – AO", "AO celkově – síla", "AO celkově – dosah"].every((x) => hl.includes(x)), hl);
  await nastav(c.page, "#vzhledAluAo", 100);
  await hudAO(c.page, "vyp");
  await c.page.waitForTimeout(800);
  const dis = await c.page.evaluate(() => ({ r: [...document.querySelectorAll("#vzhledPal [data-ao]")].every((x) => x.disabled), alu: document.getElementById("vzhledAluAo").disabled, k: document.getElementById("vzhledAoK").disabled }));
  t("B7 AO vypnute v rohu 3D: vsechny posuvniky AO (u barev, hlinik, celkove) jsou neaktivni", dis.r && dis.alu && dis.k, dis);
  await hudAO(c.page, "stredni"); await c.page.waitForTimeout(800);
  t("B8 po zapnuti AO jsou zase aktivni", await c.page.evaluate(() => [...document.querySelectorAll("#vzhledPal [data-ao]")].every((x) => !x.disabled) && !document.getElementById("vzhledAluAo").disabled));
  t("B9 bez chyb v konzoli", c.errs.length === 0, c.errs);
  await c.ctx.close();

  }
  if (ONLY.includes("C")) {
  console.log("\n## C) automaticke ukladani pro vsechny nabidky");
  S.level = 2; S.store = { env: null, alu: "satin", ao: "jemne" }; S.puts.length = 0; S.putDelay = 0; S.putFail = null;
  c = await otevri();
  await otevriPanel(c.page);
  const hx = (await c.page.evaluate(() => [...document.querySelectorAll("#vzhledPal .vzh-sw")].map((r) => r.querySelector("input[type=color]").getAttribute("data-hex"))));
  t("C0 pri otevreni okna se nic neuklada (zadne PUT bez zmeny)", S.puts.length === 0 && (await autoSt(c.page)).txt === "");
  await hudAO(c.page, "silne");                                      // HUD (hlinik / AO varianta) se NEuklada samo
  const t0 = Date.now();
  await nastav(c.page, `#vzhledPal input[data-ao="${hx[0]}"]`, 40);
  await nastav(c.page, `#vzhledPal input[data-gloss="${hx[0]}"]`, 20);
  await nastav(c.page, `#vzhledPal input[data-ao="${hx[1]}"]`, 160);
  await nastav(c.page, "#vzhledAluAo", 70);
  const s1 = await autoSt(c.page);
  t("C1 hned po zmene: hlaska 'Změny se uloží za chvilku' a zatim zadne PUT", /uloží za chvilku/.test(s1.txt) && S.puts.length === 0, { s1, puts: S.puts.length });
  const prislo = await cekejPut(1, 4000);
  await sleep(500);
  t("C2 po chvilce prijde PRAVE JEDNO PUT (ctyri zmeny v rychlem sledu se spojily)", prislo && S.puts.length === 1, S.puts.length);
  const b = (S.puts[0] || {}).body || {};
  t("C3 PUT nese barvy materialu: lesk " + hx[0] + " = 0,2 a ao_mat {" + hx[0] + " 0,4; " + hx[1] + " 1,6}, alu_cfg.ao 0,7", b.lesk && blizko(b.lesk[hx[0]], 0.2) && b.ao_mat && blizko(b.ao_mat[hx[0]], 0.4) && blizko(b.ao_mat[hx[1]], 1.6) && b.alu_cfg && blizko(b.alu_cfg.ao, 0.7), b);
  t("C4 ukladani na pozadi NEmeni ulozene HDRI a volbu hliniku / AO z rohu 3D (alu 'satin', ao 'jemne' zustaly, i kdyz je v nahledu AO Silne)", b.alu === "satin" && b.ao === "jemne" && b.env === null, { alu: b.alu, ao: b.ao, env: b.env });
  const s2 = await autoSt(c.page);
  t("C5 hlaska 'Uloženo pro všechny nabídky (cas)' v zelene (ok)", /^Uloženo pro všechny nabídky \(\d/.test(s2.txt) && /ok/.test(s2.cls), s2);
  t("C6 ulozena hodnota na serveru se prenesla do okna: 'Uloženo pro nabídky: ... AO materiálů: 2 změn ... AO 70 %'", await c.page.evaluate(() => /AO materiálů: 2 změn/.test(document.getElementById("vzhledInfo").textContent) && /AO 70 %/.test(document.getElementById("vzhledInfo").textContent)), await c.page.evaluate(() => document.getElementById("vzhledInfo").textContent));
  t("C6b mezi zmenou a PUT ubehlo aspon 800 ms (debounce), ne vic nez ~4 s", S.puts[0].t - t0 >= 800 && S.puts[0].t - t0 < 4500, S.puts[0].t - t0);
  // poradi: pomale PUT + dalsi zmena behem nej
  S.putDelay = 700; S.puts.length = 0; S.inflightMax = 0;
  await nastav(c.page, "#vzhledSat", 130);
  await cekejPut(1, 3000);
  await sleep(150);                                                  // PUT 1 je rozdelane (server ceka 700 ms)
  await nastav(c.page, `#vzhledPal input[data-ao="${hx[1]}"]`, 20);
  await cekejPut(2, 6000); await sleep(1000);
  t("C7 zmena behem pomaleho ukladani: druhe PUT jde AZ po prvnim (nikdy dve naraz) a ulozi nejnovejsi stav (AO " + hx[1] + " = 0,2, sytost 1,3)", S.puts.length === 2 && S.inflightMax === 1 && S.puts[1].body.ao_mat && blizko(S.puts[1].body.ao_mat[hx[1]], 0.2) && blizko(S.puts[1].body.sat, 1.3), { n: S.puts.length, max: S.inflightMax, b: (S.puts[1] || {}).body });
  S.putDelay = 0;
  // chyba serveru
  S.puts.length = 0; S.putFail = { status: 400, error: "ao_mat: hodnota musi byt cislo 0 az 2 (1 = beze zmeny)" };
  await nastav(c.page, `#vzhledPal input[data-ao="${hx[1]}"]`, 90);
  await cekejPut(1, 4000); await sleep(400);
  const se = await autoSt(c.page);
  t("C8 chyba serveru (400): cervena hlaska 'Neuloženo: <duvod ze serveru>'", /^Neuloženo: ao_mat: hodnota/.test(se.txt) && /err/.test(se.cls), se);
  S.putFail = null; S.puts.length = 0;
  await nastav(c.page, `#vzhledPal input[data-ao="${hx[1]}"]`, 95);
  await cekejPut(1, 4000); await sleep(400);
  const so = await autoSt(c.page);
  t("C9 dalsi zmena po chybe se zase ulozi (zelena hlaska)", S.puts.length === 1 && /^Uloženo pro všechny nabídky/.test(so.txt) && /ok/.test(so.cls), { puts: S.puts.length, so });
  // tlacitko Ulozit vzhled pro nabidky uklada vsechno (HDRI + HUD varianty) a ruší cekajici ukladani
  S.puts.length = 0;
  await nastav(c.page, `#vzhledPal input[data-ao="${hx[1]}"]`, 55);
  await c.page.getByRole("button", { name: "Uložit vzhled pro nabídky" }).click();
  await cekejPut(1, 4000); await sleep(1500);
  const bt = (S.puts[0] || {}).body || {};
  t("C10 tlacitko Ulozit: PUT nese vse vcetne volby z rohu 3D (ao 'silne') a prave zmenene AO " + hx[1] + " = 0,55; po nem uz nic nedobiha (pocet PUT 1)", S.puts.length === 1 && bt.ao === "silne" && bt.ao_mat && blizko(bt.ao_mat[hx[1]], 0.55), { n: S.puts.length, bt });
  t("C10b po ulozeni tlacitkem hlaska 'Uloženo pro všechny nabídky'", /^Uloženo pro všechny nabídky/.test((await autoSt(c.page)).txt), await autoSt(c.page));
  // zavreni stranky: cekajici zmena se posle hned (pagehide), ne az po 900 ms
  S.puts.length = 0;
  await c.page.locator(`#vzhledPal input[data-ao="${hx[1]}"]`).fill("35");
  await c.page.evaluate(() => window.dispatchEvent(new Event("pagehide")));
  const hned = await cekejPut(1, 500);
  t("C11 zavreni stranky (pagehide) s neulozenou zmenou: PUT odejde hned, bez cekani na debounce", hned && blizko(S.puts[0].body.ao_mat[hx[1]], 0.35), { hned, b: (S.puts[0] || {}).body });
  await sleep(1200);
  t("C11b po tom uz se nic nedoposila (jedno PUT)", S.puts.length === 1, S.puts.length);
  // reset
  S.puts.length = 0;
  await nastav(c.page, `#vzhledPal input[data-ao="${hx[0]}"]`, 10);
  await c.page.getByRole("button", { name: "Vrátit výchozí vzhled" }).click();
  await sleep(1800);
  t("C12 Vratit vychozi vzhled hned po zmene: ulozi se JEN null (cekajici ukladani na pozadi se zrusi) a hlaska ukladani zmizi", S.puts.length === 1 && S.puts[0].body === null && (await autoSt(c.page)).txt === "", { puts: S.puts.map((p) => p.body), st: await autoSt(c.page) });
  t("C13 bez chyb v konzoli", c.errs.length === 0, c.errs);
  await c.ctx.close();

  }
  if (ONLY.includes("D")) {
  console.log("\n## D) server pred nasazenim ao_mat (GET bez ao_mat): nahled ano, PUT bez novych klicu");
  S.level = 1; S.store = { env: null, alu: "satin", ao: "jemne" }; S.puts.length = 0; S.putFail = null;
  c = await otevri();
  await otevriPanel(c.page);
  const vz = await c.page.evaluate(() => ({ nove: document.getElementById("vzhledPanel").classList.contains("nove-api"), aoMat: document.getElementById("vzhledPanel").classList.contains("ao-mat-api"), poznamka: getComputedStyle(document.getElementById("vzhledAoNote")).display, rows: document.querySelectorAll("#vzhledPal [data-ao]").length }));
  t("D1 server bez ao_mat: AO u barev je v okne (nahled), je videt poznamka 'zatim jen nahled', panel ma nove-api ale ne ao-mat-api", vz.nove && !vz.aoMat && vz.poznamka === "block" && vz.rows >= 2, vz);
  const hd = (await c.page.evaluate(() => [...document.querySelectorAll("#vzhledPal .vzh-sw")].map((r) => r.querySelector("input[type=color]").getAttribute("data-hex"))))[0];
  await nastav(c.page, `#vzhledPal input[data-ao="${hd}"]`, 0);
  t("D2 nahled funguje i bez serveru (aoW = 0)", (await mat(c.page)).filter((x) => x.orig === hd).every((x) => x.aoW === 0));
  await nastav(c.page, "#vzhledAluAo", 20); await nastav(c.page, `#vzhledPal input[data-gloss="${hd}"]`, 10);
  await cekejPut(1, 4000); await sleep(400);
  const bd = (S.puts[0] || {}).body || {};
  t("D3 PUT nese lesk, ale NE ao_mat a alu_cfg.ao (stary server by je odmitl 400): ulozi se bez chyby (hlaska Uloženo)", S.puts.length === 1 && !("ao_mat" in bd) && !(bd.alu_cfg && "ao" in bd.alu_cfg) && bd.lesk && blizko(bd.lesk[hd], 0.1) && /^Uloženo pro všechny nabídky/.test((await autoSt(c.page)).txt), { bd, st: await autoSt(c.page) });
  t("D4 bez chyb v konzoli", c.errs.length === 0, c.errs);
  await c.ctx.close();
  S.level = 0; S.store = null; S.puts.length = 0;
  c = await otevri();
  await otevriPanel(c.page);
  const v0 = await c.page.evaluate(() => ({ nove: document.getElementById("vzhledPanel").classList.contains("nove-api"), aoVid: !!document.querySelector("#vzhledPal .vzh-gl--ao").offsetParent, lesk: !!document.getElementById("vzhledLesk").offsetParent }));
  t("D5 uplne stary server (GET bez lesku): AO i lesk u barev a sekce Hlinik jsou schovane (nove-api chybi)", !v0.nove && !v0.aoVid && !v0.lesk, v0);
  await nastav(c.page, "#vzhledSat", 120); await cekejPut(1, 4000); await sleep(300);
  const b0 = (S.puts[0] || {}).body || {};
  t("D6 PUT uplne stareho serveru nese jen stara pole (zadny lesk / alu_cfg / ao_cfg / ao_mat)", S.puts.length === 1 && !["lesk", "alu_cfg", "ao_cfg", "ao_mat"].some((k) => k in b0) && blizko(b0.sat, 1.2), b0);
  await c.ctx.close();

  }
  if (ONLY.includes("E")) {
  console.log("\n## E) ulozene upravy barev, ktere v teto scene nejsou");
  S.level = 2; S.puts.length = 0;
  S.store = { env: null, alu: null, ao: null, barvy: { "#abcdef": "#123456" }, lesk: { "#abcdef": 0 }, ao_mat: { "#fedcba": 0.5 } };
  c = await otevri();
  await otevriPanel(c.page);
  const mm = await c.page.evaluate(() => { const d = document.getElementById("vzhledMimo"); return { hidden: d.hidden, sum: document.getElementById("vzhledMimoSum").textContent, items: [...d.querySelectorAll(".vzh-mimo-it span")].map((x) => x.textContent) }; });
  t("E1 uloz. upravy barev mimo scenu jsou videt: 'Uloženo i pro barvy, které v této scéně nejsou (2)' s popisem barva + lesk a AO", !mm.hidden && /\(2\)/.test(mm.sum) && mm.items.some((x) => /#abcdef/.test(x) && /#123456/.test(x) && /lesk 0 %/.test(x)) && mm.items.some((x) => /#fedcba/.test(x) && /AO 50 %/.test(x)), mm);
  t("E1b seznam je sbaleny (jen radek s poctem), rozbali se kliknutim na nej", !(await c.page.evaluate(() => document.getElementById("vzhledMimo").open)));
  await c.page.click("#vzhledMimoSum");
  await c.page.locator('#vzhledMimo button[data-mimo="#abcdef"]').click();
  await cekejPut(1, 4000); await sleep(300);
  const mm2 = await c.page.evaluate(() => ({ sum: document.getElementById("vzhledMimoSum").textContent, n: document.querySelectorAll("#vzhledMimo .vzh-mimo-it").length }));
  const be = (S.puts[0] || {}).body || {};
  t("E2 Zrusit u #abcdef: v seznamu zbyde 1, PUT uz barvu ani lesk #abcdef nenese a AO #fedcba zustalo", mm2.n === 1 && /\(1\)/.test(mm2.sum) && !(be.barvy && be.barvy["#abcdef"]) && !(be.lesk && be.lesk["#abcdef"]) && be.ao_mat && be.ao_mat["#fedcba"] === 0.5, { mm2, be });
  await c.page.locator('#vzhledMimo button[data-mimo="#fedcba"]').click();
  await sleep(300);
  t("E3 po zruseni posledni polozky se seznam schova", await c.page.evaluate(() => document.getElementById("vzhledMimo").hidden));
  t("E4 bez chyb v konzoli", c.errs.length === 0, c.errs);
  await c.ctx.close();

  }
  if (ONLY.includes("F")) {
  console.log("\n## F) ulozeny stav se po otevreni nacte (jina scena / jina nabidka dostane totez)");
  S.level = 2; S.puts.length = 0;
  const ulozeno = { env: null, alu: null, ao: "stredni", ao_mat: {}, alu_cfg: { refl: 1, rough: 1, ao: 0.4 } };
  c = await otevri();
  const hF = (await mat(c.page)).map((x) => x.orig)[0];
  ulozeno.ao_mat[hF] = 0.25;
  await c.ctx.close();
  S.store = ulozeno;
  c = await otevri();
  const mf = await mat(c.page), cf = await matCfg(c.page), af = await alu(c.page);
  t("F1 ulozene AO po komponentech se uplatni pri otevreni: aoW " + hF + " = 0,25, hlinik 0,4, ostatni barvy 1", mf.filter((x) => x.orig === hF).every((x) => blizko(x.aoW, 0.25)) && mf.filter((x) => x.orig !== hF).every((x) => x.aoW === 1) && af.every((x) => blizko(x.aoW, 0.4)) && blizko(cf.ao[hF], 0.25), { cf, af: af.slice(0, 2) });
  await otevriPanel(c.page);
  t("F2 posuvniky v okne ukazuji ulozene hodnoty (barva 25 %, Hlinik - AO 40 %)", await c.page.evaluate((h) => document.querySelector(`#vzhledPal input[data-ao="${h}"]`).value === "25" && document.getElementById("vzhledAluAo").value === "40", hF));
  t("F3 pri samotnem otevreni okna se nic neuklada", S.puts.length === 0, S.puts.length);
  t("F4 bez chyb v konzoli", c.errs.length === 0, c.errs);
  await c.ctx.close();

  }
  if (ONLY.includes("G")) {
  console.log("\n## G) odkaz z karty Vandr ('Vzhled online nabidek...'): ?vzhled=1 otevre okno Vzhled nabidek samo");
  S.level = 2; S.store = null; S.puts.length = 0;
  c = await otevri("&vzhled=1");
  await c.page.waitForSelector("#vzhledPal .vzh-sw", { timeout: 30000 });
  t("G1 s ?vzhled=1 je okno Vzhled nabidek po nacteni modelu OTEVRENE (tlacitko aria-expanded = true, panel viditelny, barvy nactene)", await c.page.evaluate(() => !document.getElementById("vzhledPanel").hidden && document.getElementById("vzhledBtn").getAttribute("aria-expanded") === "true" && document.querySelectorAll("#vzhledPal .vzh-sw").length >= 2));
  await c.page.click("#vzhledBtn"); await c.page.waitForTimeout(400);
  t("G2 okno jde normalne zavrit (a samo se znovu neotevre)", await c.page.evaluate(() => document.getElementById("vzhledPanel").hidden));
  t("G3 samotne otevreni okna nic neuklada", S.puts.length === 0, S.puts.length);
  t("G4 bez chyb v konzoli", c.errs.length === 0, c.errs);
  await c.ctx.close();
  c = await otevri("");
  await c.page.waitForTimeout(800);
  t("G5 bez ?vzhled=1 zustava okno zavrene (jako dosud)", await c.page.evaluate(() => document.getElementById("vzhledPanel").hidden && document.getElementById("vzhledBtn").getAttribute("aria-expanded") === "false"));
  await c.ctx.close();
  }
  await browser.close(); server.close();
  console.log(`\nVYSLEDEK: ${total - bad} z ${total} OK` + (bad ? `, ${bad} CHYB` : ""));
  process.exit(bad ? 1 : 0);
})().catch((e) => { console.error(e); process.exit(2); });
