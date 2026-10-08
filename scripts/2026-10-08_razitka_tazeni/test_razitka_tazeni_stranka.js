// Test RAZITEK PRI ZIVEM TAZENI na strance Generator stolu v prohlizeci (bot8, 2026-10-08; Robert: „razitka na generatoru pri tazeni zustavaji na miste“).
// SKUTECNA stranka + SKUTECNY ovladac ve 3D (js/v3d-ovladani.js) nad SKUTECNYM kodem stolu pres most _most_stul.py (zamestnanec, produkt 4934). Spusteni (DB pres systemd-run):
//   systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --setenv=HOME=/root --working-directory=/opt/konfigurator \
//     api/venv/bin/python3 scripts/2026-10-02_stul_testy/_most_stul.py scripts/2026-10-08_razitka_tazeni/test_razitka_tazeni_stranka.js 4934
// (kandidat: spustit _most_stul.py z $CAND/scripts/..., viz prepare_cand.sh)
// Hlida: popis razitek je v popisu ovladani (`razitka`), pri ZIVEM tazeni uchytu se logo (uzel) i vypln (vrcholy v uzlu hlinik) hybou s dilem: u samotneho posunu PRESNE jako dil, u natazeni / roztazeni zustavaji
// u dilu; razitka na dilech, ktere se nehybou, stoji; Esc vraci razitka na puvodni misto; po pusteni prijde presny model s razitky; zadne chyby v konzoli.
const { chromium } = require("/opt/konfigurator/node_modules/playwright");
const BASE = process.env.BASE;
let bad = 0, total = 0;
const t = (name, cond, detail) => { total++; if (!cond) bad++; console.log(`[${cond ? "OK   " : "CHYBA"}] ${name}${!cond && detail !== undefined ? " | " + (typeof detail === "string" ? detail : JSON.stringify(detail)) : ""}`); };
const GLB_RE = /\/api\/shop\/configurator\/glb\//, RES_RE = /\/api\/shop\/configurator\/resolve/;
async function mk(browser) {
  const ctx = await browser.newContext({ viewport: { width: 1400, height: 900 }, locale: "cs-CZ" });
  const page = await ctx.newPage(); const errs = [];
  const trk = { resolve: 0, glb: 0, pending: 0, last: Date.now() };
  page.on("pageerror", e => errs.push(e.message));
  page.on("console", m => { if (m.type() === "error") errs.push("console: " + m.text()); });
  page.on("request", r => { const u = r.url(); if (RES_RE.test(u)) { trk.resolve++; trk.pending++; trk.last = Date.now(); } else if (GLB_RE.test(u)) { trk.glb++; trk.pending++; trk.last = Date.now(); } });
  const done = r => { if (RES_RE.test(r.url()) || GLB_RE.test(r.url())) { trk.pending--; trk.last = Date.now(); } };
  page.on("requestfinished", done); page.on("requestfailed", done);
  return { ctx, page, trk, errs };
}
const idle = async (p, quiet, max) => {                                      // klid: nic nejede a `quiet` ms se nic noveho nezacalo; nejdele `max` ms (zruseny tah muze nechat pocitadlo viset)
  const q = quiet || 1200; await p.page.waitForTimeout(q);
  const t0 = Date.now();
  while (Date.now() - t0 < (max || 90000)) { if (p.trk.pending <= 0 && Date.now() - p.trk.last > q) return; await p.page.waitForTimeout(100); }
};
async function load(p, hash) {
  await p.page.goto(`${BASE}/stul-konfigurator.html?debug=1${hash || ""}`, { waitUntil: "load" });
  await p.page.waitForSelector("#stage .v3d-root canvas", { timeout: 90000 });
  await p.page.waitForFunction(() => { const S = window.__pdcState; return S && S.ov && Object.keys(S.ov.debug().handles).length > 0; }, null, { polling: 200, timeout: 60000 });
  await idle(p, 900);
}
const dbg = page => page.evaluate(() => window.__pdcState.ov.debug());
const hcenter = async (page, id) => { const b = await page.locator("#v3do_" + id).boundingBox(); return { x: b.x + b.width / 2, y: b.y + b.height / 2 }; };
async function dragTo(page, id, dx, dy, hold) {                              // uchop uchyt, tahni o (dx, dy) po krocich, drz; mys zustava stisknuta
  const c = await hcenter(page, id);
  await page.mouse.move(c.x, c.y); await page.mouse.down();
  for (let i = 1; i <= 10; i++) await page.mouse.move(c.x + dx * i / 10, c.y + dy * i / 10);
  await page.waitForTimeout(hold || 600);
  return c;
}
const stavRazitek = page => page.evaluate(() => {
  const ov = window.__pdcState.ov, d = window.__pdcState.last.vodici.ovladani;
  return { razitka: ov.liveRazitka(), boxy: Object.fromEntries([...new Set((d.razitka || []).map(z => z.dil))].map(i => [i, ov.liveBox(i)])) };
});
const rozdil = (a, b) => a.map((v, i) => v - b[i]);
const blizko = (a, b, tol) => a && b && a.every((v, i) => Math.abs(v - b[i]) <= tol);

(async () => {
  const browser = await chromium.launch({ args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
  const p = await mk(browser);
  await load(p, "#w=2000&d=800");
  const pg = p.page;
  const nactiInfo = () => pg.evaluate(() => {
    const d = window.__pdcState.last.vodici.ovladani, host = new Set((d.razitka || []).map(z => z.dil));
    return { n: (d.razitka || []).length, razitka: d.razitka || [], tahy: d.tahy.filter(x => x.zive && x.zive.length && x.osa).map(x => ({ id: x.id, osa: x.osa, ops: x.zive.map(o => o.op), jenPosun: x.zive.every(o => o.op === "posun"), hosty: [...new Set(x.zive.flatMap(o => o.ix))].filter(i => host.has(i)) })) };
  });
  let info = await nactiInfo();
  t("A1 popis ovladani ma razitka (aspon 5)", info.n >= 5, info.n);
  const ps = await stavRazitek(pg);
  t("A2 razitka v nactenem modelu: kazde ma logo (uzel) i vypln (teziste vrcholu)", ps.razitka.length === info.n && ps.razitka.every(z => z.logo && z.vypln && z.logo.every(Number.isFinite) && z.vypln.every(Number.isFinite)), ps.razitka.slice(0, 2));
  t("A3 logo a vypln jednoho razitka jsou u sebe (<= 30 mm)", ps.razitka.every(z => Math.hypot(...rozdil(z.logo, z.vypln)) <= 30), ps.razitka.slice(0, 2));

  // ---- B) samotny posun: razitka na hybanych dilech jedou PRESNE s dilem (po kazdem pokusu se cte aktualni model: zruseny pokus ho za zateze nemusi vratit hned)
  const dirs4 = (px) => [[px, 0], [-px, 0], [0, px], [0, -px]];
  info = await nactiInfo();
  const posun0 = info.tahy.find(x => x.jenPosun && x.hosty.length > 0);
  t("B0 existuje tah jen s posunem, ktery hybe dily s razitky", !!posun0, info.tahy.map(x => [x.id, x.ops.join("+"), x.hosty.length]));
  if (posun0) {
    let hotovo = false;
    for (const [dx, dy] of dirs4(60)) {
      await idle(p, 800, 6000);
      const infoA = await nactiInfo(), posun = infoA.tahy.find(x => x.id === posun0.id);
      if (!posun || !posun.hosty.length) continue;
      const pred = await stavRazitek(pg), r_pred = p.trk.resolve, g_pred = p.trk.glb;          // zruseny pokus muze po case vyvolat dotaz na server: pocitadla se berou az po klidu, tesne pred tahem
      await dragTo(pg, posun.id, dx, dy, 500);
      const dd = await dbg(pg), po = await stavRazitek(pg);
      const dh = po.razitka.length === pred.razitka.length ? posun.hosty.map(i => Math.hypot(...rozdil(po.boxy[i].mean, pred.boxy[i].mean))) : [0];
      if (!(dd.drag && dd.drag.live && Math.max(...dh) > 5)) { await pg.keyboard.press("Escape"); await pg.mouse.up(); await pg.waitForTimeout(300); continue; }
      hotovo = true;
      t("B1 tah " + posun.id + " (jen posun) hybe dily s razitky: dil se pohnul (smer " + JSON.stringify([dx, dy]) + ")", true);
      const chyby = [], stoji = [];
      infoA.razitka.forEach((z, k) => {
        const a = pred.razitka[k], b = po.razitka[k];
        if (posun.hosty.includes(z.dil)) {
          const d = rozdil(po.boxy[z.dil].mean, pred.boxy[z.dil].mean);
          if (!blizko(rozdil(b.logo, a.logo), d, 0.02) || !blizko(rozdil(b.vypln, a.vypln), d, 0.02)) chyby.push([z.dil, rozdil(b.logo, a.logo), d]);
        } else if (!blizko(b.logo, a.logo, 1e-6) || !blizko(b.vypln, a.vypln, 1e-6)) stoji.push(z.dil);
      });
      t("B2 logo i vypln se pohnou PRESNE jako dil, na kterem sedi (" + posun.hosty.length + " hostitelu)", chyby.length === 0, chyby.slice(0, 3));
      t("B3 razitka na dilech, ktere se nehybou, stoji", stoji.length === 0, stoji);
      t("B4 behem tazeni nejde dotaz na server (zive: ani resolve, ani novy GLB)", p.trk.resolve === r_pred && p.trk.glb === g_pred && dd.drag && dd.drag.live === true, [p.trk.resolve - r_pred, p.trk.glb - g_pred, dd.drag]);
      await pg.keyboard.press("Escape"); await pg.mouse.up(); await pg.waitForTimeout(500);
      const zpet = await stavRazitek(pg);
      t("B5 Esc vrati razitka na puvodni misto", zpet.razitka.length === pred.razitka.length && infoA.razitka.every((z, k) => blizko(zpet.razitka[k].logo, pred.razitka[k].logo, 1e-4) && blizko(zpet.razitka[k].vypln, pred.razitka[k].vypln, 1e-4)), zpet.razitka.slice(0, 2));
      break;
    }
    if (!hotovo) t("B1 tah " + posun0.id + " (jen posun): nepodarilo se vyvolat zive tazeni, ktere pohne dilem s razitky", false);
  }
  await pg.keyboard.press("Escape"); await pg.mouse.up(); await idle(p, 1200);

  // ---- C) natazeni / roztazeni: razitka zustavaji u dilu (do 5 mm od jeho obalky); tahy mirne (10 - 150 mm), jinak by se profil zkratil pod delku loga a razitko by uz nemelo kde sedet
  for (const idTahu of ["h", "w", "d"]) {
    let ok = false;
    for (const px of [30, 15]) {
      for (const [dx, dy] of dirs4(px)) {
        await idle(p, 800, 6000);
        const infoA = await nactiInfo(), nat = infoA.tahy.find(x => x.id === idTahu && !x.jenPosun && x.hosty.length > 0);
        if (!nat) continue;
        const pred = await stavRazitek(pg);
        await dragTo(pg, nat.id, dx, dy, 450);
        const dd = await dbg(pg), s = await stavRazitek(pg);
        if (s.razitka.length !== pred.razitka.length) { await pg.keyboard.press("Escape"); await pg.mouse.up(); await pg.waitForTimeout(300); continue; }
        const kl = dd.drag && dd.drag.cur ? Object.keys(dd.drag.cur)[0] : null;
        const delta = kl ? Math.abs(dd.drag.cur[kl] - dd.drag.start[kl]) : 0;
        const pohnute = infoA.razitka.filter((z, k) => Math.hypot(...rozdil(s.razitka[k].logo, pred.razitka[k].logo)) > 3).length;
        if (dd.drag && dd.drag.live && delta >= 10 && delta <= 150 && pohnute > 0) {
          ok = true;
          const mimo = infoA.razitka.filter((z, k) => {
            if (!nat.hosty.includes(z.dil)) return false;
            const b = s.boxy[z.dil], l = s.razitka[k].logo;
            return !l.every((v, i) => v >= b.min[i] - 5 && v <= b.max[i] + 5);
          });
          t("C1 tah " + nat.id + " (" + nat.ops.join("+") + ", zmena " + delta.toFixed(0) + " mm): razitka se pohnula (" + pohnute + ") a na dilech, ktere se hybou, zustala u nich (<= 5 mm od obalky dilu)", mimo.length === 0, mimo.slice(0, 3));
          // NEZAVISLA vyroba: razitko drzi vzdalenost od konce dilu na SVE strane (vuci stredu dilu podel osy tahu): ocekavany posun = posun TOHO konce dilu (z vrcholu dilu pred / po), u stredu prumer obou konci
          const c = nat.osa.map(Math.abs).indexOf(Math.max(...nat.osa.map(Math.abs)));
          if (Math.max(...nat.osa.map(Math.abs)) > 0.99) {
            const odchylky = [];
            infoA.razitka.forEach((z, k) => {
              if (!nat.hosty.includes(z.dil)) return;
              const b0 = pred.boxy[z.dil], b1 = s.boxy[z.dil], u0 = pred.razitka[k].logo[c], st0 = (b0.min[c] + b0.max[c]) / 2;
              const dMin = b1.min[c] - b0.min[c], dMax = b1.max[c] - b0.max[c];
              const ocek = u0 > st0 + 0.05 ? dMax : (u0 < st0 - 0.05 ? dMin : (dMin + dMax) / 2), skut = s.razitka[k].logo[c] - u0;
              if (Math.abs(skut - ocek) > 0.5) odchylky.push([z.dil, +skut.toFixed(2), +ocek.toFixed(2)]);
            });
            t("C2 tah " + nat.id + ": razitko drzi vzdalenost od konce dilu na sve strane (posun podel osy = posun toho konce dilu, tolerance 0,5 mm)", odchylky.length === 0, odchylky.slice(0, 4));
          }
          break;
        }
        await pg.keyboard.press("Escape"); await pg.mouse.up(); await pg.waitForTimeout(300);
      }
      if (ok) break;
    }
    if (!ok) t("C0 tah " + idTahu + ": nepodarilo se vyvolat mirne zive tazeni s pohybem razitek", false);
    await pg.keyboard.press("Escape"); await pg.mouse.up(); await idle(p, 1200);
  }

  // ---- D) pusteni: prijde presny model s razitky
  const r0 = p.trk.resolve, g0 = p.trk.glb;
  info = await nactiInfo();
  const tah = info.tahy.find(x => x.id === "w") || info.tahy[0];
  await dragTo(pg, tah.id, 60, 0, 400);
  await pg.mouse.up(); await idle(p, 1800);
  const konec = await pg.evaluate(() => ({ n: ((window.__pdcState.last.vodici.ovladani || {}).razitka || []).length, zive: window.__pdcState.ov.liveRazitka().length, drag: window.__pdcState.ov.debug().drag }));
  t("D1 po pusteni prisel presny model (nove resolve + GLB) a ma razitka", p.trk.resolve > r0 && p.trk.glb > g0 && konec.n >= 3 && konec.zive === konec.n && konec.drag === null, [p.trk.resolve - r0, p.trk.glb - g0, konec]);
  t("D2 bez chyb v konzoli", p.errs.length === 0, p.errs.slice(0, 3));
  await browser.close();
  console.log(`\nvysledek: ${total - bad}/${total} OK`);
  process.exit(bad ? 1 : 0);
})().catch(e => { console.log("CHYBA test spadl:", e && e.stack || e); process.exit(1); });
