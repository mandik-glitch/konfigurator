// Koty a prepinac Koty jsou i na VEREJNYCH strankach (mini-shop; stejny modul voleb jako Generator stolu pro zamestnance): Robert 2026-10-05 "prvky napric generatory na vsech mistech: interni ve scene,
// minishopy, iframe na logiman.cz" (bot16; drive bot8 2026-10-05: verejne stranky dims:0 + hudKoty:false, tenhle test se jmenoval test_stul_koty_verejne_bez.js). Model stolu nese koty ve spec v3d,
// modul voleb (product-configurator.js mountOpts) je ukazuje vsude; na uzkem okne (<= 700 px) jsou po nacteni vypnute, prepinac zustava. Siroka sada pres vsechna mista: scripts/2026-10-05_prvky_napric_testy.
// Spusteni (DB pres systemd-run), most mini-shopu od bot16:
//   systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --setenv=HOME=/root --working-directory=/opt/konfigurator \
//     api/venv/bin/python3 scripts/2026-10-02_miniweb_frontend_testy/bridge.py scripts/2026-10-02_stul_testy/test_stul_koty_verejne.js 9001
const { chromium } = require("/opt/konfigurator/node_modules/playwright");
const BASE = process.env.BASE, PID = process.env.PID || "9001";
let bad = 0, total = 0; const ok = (c, t, d) => { total++; if (!c) bad++; console.log(`[${c ? "OK   " : "CHYBA"}] ${t}${!c && d !== undefined ? " | " + JSON.stringify(d) : ""}`); };
async function otevri(browser, w) {
  const ctx = await browser.newContext({ viewport: { width: w, height: 1000 }, locale: "cs-CZ" });
  const page = await ctx.newPage(); const errs = [];
  page.on("pageerror", e => errs.push(e.message));
  await page.addInitScript(() => { window.__pdcDebug = true; });
  await page.route(/pripni-cokoli/, r => r.abort());                       // druhy 3D prvek se tu netestuje (ma vlastni sadu)
  await page.route("**/miniweb/config.cs.json", async (route) => { const r = await route.fetch(); const j = await r.json(); j.configurator_product_id = Number(PID); await route.fulfill({ response: r, json: j }); });
  await page.goto(`${BASE}/miniweb/product.html?shop=packstations&lang=cs&demo=1&id=9001`);
  await page.waitForSelector(".pdc-stage .v3d-root canvas", { timeout: 90000 });
  await page.waitForFunction(() => { const S = window.__pdcState; return S && S.viewer && S.viewer.state && S.viewer.state().ready && !S.viewer.state().loading; }, null, { polling: 300, timeout: 90000 });
  await page.waitForTimeout(1500);
  return { ctx, page, errs };
}
const dom = (page) => page.evaluate(() => {
  const s = window.__pdcState.viewer.state();
  return { dims: s.dims, hudKoty: s.hudKoty, labels: [...document.querySelectorAll(".v3d-dim")].filter(e => e.offsetParent !== null).length, seg: [...document.querySelectorAll('.v3d-hud button[data-grp="dims"]')].filter(b => b.offsetParent !== null).length };
});
(async () => {
  const browser = await chromium.launch({ args: ["--use-gl=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
  const A = await otevri(browser, 1400);
  const st = await dom(A.page);
  ok(st.hudKoty === true && st.dims === 1, "V1 verejna stranka: prepinac Koty je v HUD a koty jsou zapnute (uroven Rozmery)", st);
  ok(st.labels >= 3, "V2 v DOM jsou popisky kot", st);
  ok(st.seg >= 2, "V3 v HUD je viditelny prepinac Koty (Vyp / Rozmery)", st);
  await A.page.click('.v3d-hud button[data-grp="dims"][data-v="0"]'); await A.page.waitForTimeout(500);
  const vyp = await dom(A.page);
  ok(vyp.dims === 0 && vyp.labels === 0, "V3b Vyp: zadna kota neni videt", vyp);
  ok(A.errs.length === 0, "V4 bez chyb JS", A.errs.slice(0, 3));
  await A.ctx.close();
  const B = await otevri(browser, 360);
  const un = await dom(B.page);
  ok(un.hudKoty === true && un.dims === 0 && un.labels === 0 && un.seg >= 1, "V5 uzke okno (360 px): prepinac Koty je, koty jsou po nacteni vypnute (maly nahled by zahltily)", un);
  ok(B.errs.length === 0, "V6 bez chyb JS (uzke okno)", B.errs.slice(0, 3));
  await B.ctx.close();
  await browser.close();
  console.log(`\n==> ${total - bad}/${total} kontrol OK`);
  process.exit(bad ? 1 : 0);
})().catch(e => { console.error("SPADLO", e); process.exit(1); });
