// Zavod "starsi odpoved prepise patch ze 3D" (bot16 2026-10-04, nalez bot10: test_ovladani3d O8 pod novym viewerem namatkou 100/100): patch z ovladani ve 3D (applyOvPatch, napr.
// "Pridat vyrez sem") nastavi vyber hned a dotaz na server odesle az po 250 ms. Kdyz v tom okne dorazi odpoved STARSIHO dotazu (zmena sirky, ktera jeste letela), modul ji prijal
// a prepsal patch jejim vyberem (S.sel = r.selection) - patch se ztratil (vyrez zpet na 100/100). Panelova cesta (setValue) to hlidala (S.commitPending), 3D cesta ne.
// Test odpoved prvniho dotazu ZADRZI a pusti ji presne v okne mezi patchem a odeslanim jeho dotazu - deterministicky, bez zavislosti na rychlosti stroje.
const { chromium } = require("/opt/konfigurator/node_modules/playwright");
const BASE = process.env.BASE, PID = process.env.PID;
let bad = 0, total = 0; const ok = (c, t) => { total++; if (!c) bad++; console.log(`[${c ? "OK   " : "CHYBA"}] ${t}`); };
(async () => {
  const browser = await chromium.launch({ args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
  const ctx = await browser.newContext({ viewport: { width: 1300, height: 900 } });
  await ctx.route(/pripni-cokoli/, r => r.abort());
  const page = await ctx.newPage(); const errs = []; page.on("pageerror", e => errs.push(e.message));
  await page.addInitScript(() => { window.__pdcDebug = true; });
  let hold = false, release = null, held = null;               // hold = zadrz odpoved NEXT dotazu na resolve; release() ji pusti
  await page.route("**/miniweb/config.cs.json", async (route) => { const r = await route.fetch(); const j = await r.json(); j.configurator_product_id = Number(PID); await route.fulfill({ response: r, json: j }); });
  await page.route("**/api/shop/configurator/resolve", async (route) => {
    if (!hold) return route.continue();
    hold = false; const resp = await route.fetch();
    await held; await route.fulfill({ response: resp });
  });
  await page.goto(`${BASE}/miniweb/product.html?shop=packstations&lang=cs&demo=1&id=9001`);
  await page.waitForFunction(() => typeof window.__pdcApplyPatch === "function" && window.__pdcState && window.__pdcState.last && !window.__pdcState.pending, null, { timeout: 60000 });
  const stav = () => page.evaluate(() => ({ pending: window.__pdcState.pending, w: window.__pdcState.sel.w, on: window.__pdcState.sel.cut1, x: window.__pdcState.sel.cut1x, z: window.__pdcState.sel.cut1z }));

  // A: zmena sirky (dotaz odejde po 250 ms, odpoved zadrzime)
  hold = true; held = new Promise(res => { release = res; });          // release existuje hned (ne az po route.fetch): pod zatezi by ho test volal driv, nez by ho handler vytvoril
  const reqA = page.waitForRequest(r => /configurator\/resolve/.test(r.url()) && r.method() === "POST", { timeout: 20000 });
  await page.evaluate(() => window.__pdcApplyPatch({ w: 2000 })); await reqA;
  await page.waitForFunction(() => true); await page.waitForTimeout(100);
  // B: patch ze 3D ("Pridat vyrez sem") - nastavi vyber HNED; a v ten samy okamzik pustime zadrzenou odpoved A (dorazi pred odeslanim dotazu B)
  await page.evaluate(() => window.__pdcApplyPatch({ cut1: true, cut1x: 425, cut1z: 1390 }));
  const hned = await stav();
  ok(hned.on === true && hned.x === 425, "Z1 patch ze 3D nastavil vyber hned (výřez zapnut, cut1x " + hned.x + ", cut1z " + hned.z + ")");
  release();
  await page.waitForTimeout(80);                                // odpoved A je zpracovana (dotaz B jeste neodesel: debounce 250 ms)
  const po = await stav();
  ok(po.on === true && Math.abs(po.x - 425) <= 5 && Math.abs(po.z - 1390) <= 5, "Z2 starší odpověď (změna šířky) NEPŘEPSALA patch ze 3D: výřez " + po.on + ", cut1x " + po.x + ", cut1z " + po.z);
  // nakonec: dotaz B se odesle, server vybere potvrdi a pripadne orizne; vyber ma zustat patchnuty
  await page.waitForFunction(() => !window.__pdcState.pending && window.__pdcState.sel.w === 2000 && window.__pdcState.sel.cut1 === true, null, { timeout: 30000 }).catch(() => {});
  const konec = await stav();
  ok(konec.w === 2000 && konec.on === true && Math.abs(konec.x - 425) <= 5 && Math.abs(konec.z - 1390) <= 5, "Z3 po ustálení: šířka 2000, výřez zapnut na " + konec.x + " / " + konec.z + " (server potvrdil)");
  ok(!errs.length, "Z4 bez JS chyb" + (errs[0] ? " | " + errs[0] : ""));
  await Promise.race([browser.close(), new Promise(r => setTimeout(r, 15000))]); console.log(`\n==> ${total - bad}/${total} kontrol OK`); process.exit(bad ? 1 : 0);
})();
