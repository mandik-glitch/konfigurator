// Test SPODNIHO SUPLIKU boxu (s delicimi pricky) na KLIK ve 3D nahledu generatoru stolu (bot10, 2026-10-05; Robert: "nech se 1 suplik z boxu v 3D nahledu otevira na kliknuti, zavira na dalsi kliknuti a tak dokola").
// SKUTECNA stranka + SKUTECNY prohlizec (js/v3d/viewer3d.js) + SKUTECNY GLB ze serveru pres most _most_stul.py (fiktivni karty, nic se nezapisuje):
//   systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --setenv=HOME=/root --setenv=PID40=9877 --setenv=PID35=9878 --working-directory=/opt/konfigurator \
//     api/venv/bin/python3 scripts/2026-10-02_stul_testy/_most_stul.py scripts/2026-10-02_stul_testy/test_stul_suplik_klik.js 4934
// Hlida: model nese pohyb k=drawer (chip v HUD), klik na suplik otevre (t -> 1), dalsi klik zavre (t -> 0), dokola; po zmene rozmeru stolu (nahrani noveho modelu) je suplik zase zavreny
// a pohyb funguje; zive tazeni (sirka stolu i posun boxu) hybe i suplik spolu s boxem (neodtrhne se; sekce 2b od 2026-10-06 - drive to tu jen stalo v zahlavi); bez boxu (suplik vypnuty) zadny pohyb.
const { chromium } = require("/opt/konfigurator/node_modules/playwright");
const BASE = process.env.BASE, SHOT = process.env.SHOT || "";
let bad = 0, total = 0;
const t = (name, cond, detail) => { total++; if (!cond) bad++; console.log(`[${cond ? "OK   " : "CHYBA"}] ${name}${!cond && detail !== undefined ? " | " + (typeof detail === "string" ? detail : JSON.stringify(detail)) : ""}`); };
const GLB_RE = /\/api\/shop\/configurator\/glb\//, RES_RE = /\/api\/shop\/configurator\/resolve/;
async function mk(browser, w, h) {
  const ctx = await browser.newContext({ viewport: { width: w || 1400, height: h || 900 }, locale: "cs-CZ" });
  await ctx.addInitScript(() => { window.__pdcDebug = true; });
  const page = await ctx.newPage(); const errs = [];
  const trk = { pending: 0, last: Date.now() };
  page.on("pageerror", e => errs.push(e.message));
  page.on("console", m => { if (m.type() === "error") errs.push("console: " + m.text()); });
  page.on("request", r => { const u = r.url(); if (RES_RE.test(u) || GLB_RE.test(u)) { trk.pending++; trk.last = Date.now(); } });
  const done = r => { if (RES_RE.test(r.url()) || GLB_RE.test(r.url())) { trk.pending--; trk.last = Date.now(); } };
  page.on("requestfinished", done); page.on("requestfailed", done);
  return { ctx, page, trk, errs };
}
const idle = async (p, quiet) => {
  const q = quiet || 1200; await p.page.waitForTimeout(q);
  const t0 = Date.now();
  while (Date.now() - t0 < 90000) { if (p.trk.pending <= 0 && Date.now() - p.trk.last > q) return; await p.page.waitForTimeout(100); }
};
async function load(p, pagePath, hash) {
  await p.page.goto(`${BASE}${pagePath}?debug=1${hash || ""}`, { waitUntil: "load" });
  await p.page.waitForSelector("#stage .v3d-root canvas", { timeout: 90000 });
  await p.page.waitForFunction(() => { const S = window.__pdcState; return S && S.last && S.last.hash; }, null, { polling: 200, timeout: 60000 });
  await p.page.waitForFunction(() => window.__v3d && window.__v3d.state && window.__v3d.state().modelSeq >= 1, null, { polling: 200, timeout: 90000 });
  await idle(p, 900);
}
const st = p => p.page.evaluate(() => { const s = window.__v3d.state(); return { t: s.t, motions: s.motions, modelSeq: s.modelSeq }; });
// najde na platne bod, ktery trefi suplik (pohyb m1); prohledava mrizku
async function najdiSuplik(p) {
  return p.page.evaluate(() => {
    const c = document.querySelector("#stage .v3d-root canvas"), r = c.getBoundingClientRect();
    const hits = [];
    for (let fy = 0.25; fy <= 0.95; fy += 0.03) for (let fx = 0.1; fx <= 0.95; fx += 0.02) {
      const x = r.left + r.width * fx, y = r.top + r.height * fy, h = window.__v3d.pickInfo(x, y);
      if (h && h.motion === "m1") hits.push([x, y]);
    }
    if (!hits.length) return null;
    const mx = hits.reduce((a, q) => a + q[0], 0) / hits.length, my = hits.reduce((a, q) => a + q[1], 0) / hits.length;
    hits.sort((a, b) => Math.hypot(a[0] - mx, a[1] - my) - Math.hypot(b[0] - mx, b[1] - my));
    return { x: hits[0][0], y: hits[0][1], pocet: hits.length };
  });
}
const cekejT = async (p, cil, ms) => {
  const t0 = Date.now();
  while (Date.now() - t0 < (ms || 6000)) { const s = await st(p); if (Math.abs((s.t.m1 || 0) - cil) < 0.02) return s; await p.page.waitForTimeout(80); }
  return await st(p);
};

(async () => {
  const browser = await chromium.launch({ args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
  console.log("\n## 1) vychozi stul 30 (box s 2 supliky): pohyb v modelu, klik otevre, dalsi klik zavre, dokola");
  const p = await mk(browser);
  await load(p, "/stul-konfigurator.html", "");
  let s = await st(p);
  t("1a model nese jeden pohyb: suplik (k=drawer), zavreny (t = 0)", s.motions.length === 1 && s.motions[0].k === "drawer" && s.motions[0].id === "m1" && (s.t.m1 || 0) === 0, s);
  const chip = await p.page.evaluate(() => { const b = document.querySelector('#stage [data-motion="m1"]'); return b ? { text: b.textContent.trim(), pressed: b.getAttribute("aria-pressed") } : null; });
  t("1b v HUD je tlacitko (chip) supliku, nestisknute", chip && chip.pressed === "false" && /uplík|rawer|uflad/i.test(chip.text), chip);
  let bod = await najdiSuplik(p);
  t("1c na platne je bod, ktery trefi suplik (pickInfo.motion = m1)", !!bod && bod.pocet >= 2, bod);
  if (SHOT) await p.page.screenshot({ path: SHOT + "_zavreny.png" });
  for (let kolo = 1; kolo <= 3; kolo++) {
    bod = await najdiSuplik(p);
    await p.page.mouse.click(bod.x, bod.y);
    s = await cekejT(p, 1);
    t(`1d kolo ${kolo}: klik na suplik ho otevre (t = 1)`, Math.abs((s.t.m1 || 0) - 1) < 0.02, s.t);
    if (kolo === 1 && SHOT) await p.page.screenshot({ path: SHOT + "_otevreny.png" });
    bod = await najdiSuplik(p);
    t(`1e kolo ${kolo}: otevreny suplik jde porad trefit (zavreni)`, !!bod, bod);
    if (!bod) break;
    await p.page.mouse.click(bod.x, bod.y);
    s = await cekejT(p, 0);
    t(`1f kolo ${kolo}: dalsi klik ho zavre (t = 0)`, Math.abs(s.t.m1 || 0) < 0.02, s.t);
  }
  // chip: stisk otevre a dalsi stisk zavre
  await p.page.click('#stage [data-motion="m1"]');
  s = await cekejT(p, 1);
  const pr1 = await p.page.evaluate(() => document.querySelector('#stage [data-motion="m1"]').getAttribute("aria-pressed"));
  t("1g tlacitko v HUD otevre suplik (t = 1, aria-pressed = true)", Math.abs((s.t.m1 || 0) - 1) < 0.02 && pr1 === "true", [s.t, pr1]);
  await p.page.click('#stage [data-motion="m1"]');
  s = await cekejT(p, 0);
  t("1h dalsi stisk tlacitka ho zavre (t = 0)", Math.abs(s.t.m1 || 0) < 0.02, s.t);
  t("1i zadne chyby ve strance", p.errs.length === 0, p.errs.slice(0, 3));

  console.log("\n## 2) zmena rozmeru (novy model): suplik je zase zavreny a pohyb funguje");
  await p.page.click('#stage [data-motion="m1"]');
  await cekejT(p, 1);
  const seq0 = (await st(p)).modelSeq;
  await p.page.evaluate(() => { const n = document.querySelector('[data-slot="w"] input[type="number"]'); n.value = "1400"; n.dispatchEvent(new Event("input", { bubbles: true })); n.dispatchEvent(new Event("change", { bubbles: true })); });
  await p.page.waitForFunction(seq => window.__v3d && window.__v3d.state().modelSeq > seq, seq0, { timeout: 60000, polling: 200 });
  await idle(p, 1500);
  s = await st(p);
  t("2a po zmene sirky je v novem modelu suplik zavreny (t = 0) a pohyb existuje", s.motions.length === 1 && Math.abs(s.t.m1 || 0) < 0.02, s);
  bod = await najdiSuplik(p);
  t("2b i v novem modelu jde suplik trefit", !!bod, bod);
  await p.page.mouse.click(bod.x, bod.y);
  s = await cekejT(p, 1);
  t("2c klik v novem modelu suplik otevre", Math.abs((s.t.m1 || 0) - 1) < 0.02, s.t);
  t("2d zadne chyby po zmene rozmeru", p.errs.length === 0, p.errs.slice(0, 3));

  console.log("\n## 2b) ZIVE TAZENI (sirka stolu, posun boxu): suplik se hybe spolu s boxem, neodtrhne se (Robert 2026-10-06: 'suplik se pri tazeni prodluzovani stolu rozbiji')");
  const relZ = (page, i) => page.evaluate(i => {                       // stred vrcholu TELA skrine (zive cteny z attributu) a stred vrcholu supliku (vlastni uzel pod pivotem p1)
    const lb = window.__pdcState.ov.liveBox(i);
    if (!lb) return null;
    let pos = null;
    window.__v3d.model().traverse(n => { if (!pos && n.name === "p1") { const m = n.isMesh ? n : n.children.find(c => c.isMesh); if (m) pos = m.geometry.attributes.position.array; } });
    if (!pos) return null;
    const sum = [0, 0, 0]; for (let j = 0; j < pos.length; j += 3) { sum[0] += pos[j]; sum[1] += pos[j + 1]; sum[2] += pos[j + 2]; }
    const n = pos.length / 3;
    return { casing: lb.mean, drawer: [sum[0] / n, sum[1] / n, sum[2] / n] };
  }, i);
  for (const [popis, handle, dx, minMm] of [["tazeni sirky stolu (uchyt w) o +110 px", "w", 110, 100], ["posun boxu po sirce (uchyt boxpos) o -60 px", "boxpos", -60, 30]]) {
    const pz = await mk(browser);
    if (process.env.MUTACE_BEZ_EXTRA) await pz.ctx.route("**/api/shop/configurator/resolve", async r => {          // MUTACE (self-kontrola testu): server "zapomene" predat zive_rozsahy_extra = presne puvodni chyba; test MUSI padnout (Z1, Z3)
      const resp = await r.fetch(); const j = await resp.json();
      if (j.vodici && j.vodici.ovladani) delete j.vodici.ovladani.zive_rozsahy_extra;
      r.fulfill({ response: resp, body: JSON.stringify(j) });
    });
    if (process.env.MUTACE_KLIENT_BEZ_EXTRA) await pz.ctx.route(/\/js\/v3d-ovladani\.js/, async r => {          // MUTACE (self-kontrola testu): klient dalsi rozsahy dilu (suplik) nehybe; test MUSI padnout (Z3)
      const resp = await r.fetch(); const js = (await resp.text()).replace("((extra && extra[i]) || []).forEach(", "([]).forEach(");
      r.fulfill({ response: resp, body: js });
    });
    await load(pz, "/stul-konfigurator.html", "#w=1200&d=800&h=840");
    const idx = await pz.page.evaluate(() => { const ex = window.__pdcState.last.vodici.ovladani.zive_rozsahy_extra; return ex ? Object.keys(ex).map(Number) : null; });
    t(`Z1 (${popis}) verejny resolve nese zive_rozsahy_extra pro dil boxu (suplik je vlastni uzel; bez toho se pri tazeni odtrhne od boxu)`, !!idx && idx.length === 1, idx);
    if (idx && idx.length === 1) {
      const r0 = await relZ(pz.page, idx[0]);
      const hb = await pz.page.locator("#v3do_" + handle).boundingBox();
      const cx = hb.x + hb.width / 2, cy = hb.y + hb.height / 2;
      await pz.page.mouse.move(cx, cy); await pz.page.mouse.down();
      for (let i = 1; i <= 10; i++) await pz.page.mouse.move(cx + dx * i / 10, cy);
      await pz.page.waitForTimeout(800);
      const r1 = await relZ(pz.page, idx[0]);
      const dCas = r0 && r1 ? r1.casing.map((v, k) => v - r0.casing[k]) : null, dDr = r0 && r1 ? r1.drawer.map((v, k) => v - r0.drawer[k]) : null;
      t(`Z2 (${popis}) behem tazeni se box posunul o aspon ${minMm} mm (tazeni opravdu probehlo)`, !!dCas && Math.hypot(...dCas) >= minMm, dCas);
      t(`Z3 (${popis}) suplik se behem tazeni posunul STEJNE jako telo boxu (rozdil < 0,5 mm na kazde ose) - neodtrhne se`, !!dCas && dCas.every((v, k) => Math.abs(v - dDr[k]) < 0.5), { dCas, dDr });
      await pz.page.mouse.up();
      await idle(pz, 1500);
      const s2 = await st(pz);
      t(`Z4 (${popis}) po pusteni se nacte novy model a suplik jde otevrit (pohyb existuje, zavreny)`, s2.motions.length === 1 && Math.abs(s2.t.m1 || 0) < 0.02, s2);
    }
    t(`Z5 (${popis}) bez chyb ve strance`, pz.errs.length === 0, pz.errs.slice(0, 3));
    await pz.ctx.close();
  }

  console.log("\n## 3) bez boxu (suplik vypnuty): zadny pohyb");
  await p.page.evaluate(() => { const cb = document.querySelector('[data-slot="drawers"] input[type="checkbox"]'); if (cb && cb.checked) cb.click(); });
  const seq1 = (await st(p)).modelSeq;
  await p.page.waitForFunction(seq => window.__v3d.state().modelSeq > seq, seq1, { timeout: 60000, polling: 200 }).catch(() => {});
  await idle(p, 1500);
  s = await st(p);
  t("3a bez supliku model nema zadny pohyb a v HUD neni tlacitko supliku", s.motions.length === 0 && !(await p.page.$('#stage [data-motion="m1"]')), s.motions);
  await browser.close();
  console.log(`\n${total - bad}/${total} OK`);
  process.exit(bad ? 1 : 0);
})();
