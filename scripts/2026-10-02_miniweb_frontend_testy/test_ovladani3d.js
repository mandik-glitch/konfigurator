// Ovladani primo ve 3D v mini-shopu (obecny modul v3d-ovladani.js od bot8) nad SKUTECNYM verejnym resolve (bridge.py): uchyty, tazeni, stitek v mm, nabidka, zvyrazneni panelu.
const { chromium } = require("/opt/konfigurator/node_modules/playwright");
const BASE = process.env.BASE, PID = process.env.PID || "9001";
let bad = 0, total = 0; const ok = (c, t) => { total++; if (!c) bad++; console.log(`[${c ? "OK   " : "CHYBA"}] ${t}`); };
(async () => {
  const browser = await chromium.launch({ args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
  const ctx = await browser.newContext({ viewport: { width: 1400, height: 1000 }, locale: "cs-CZ" });
  const page = await ctx.newPage(); const errs = [];
  page.on("pageerror", e => errs.push(e.message));
  await page.route("**/miniweb/config.cs.json", async (route) => { const r = await route.fetch(); const j = await r.json(); j.configurator_product_id = Number(PID); await route.fulfill({ response: r, json: j }); });
  await page.goto(`${BASE}/miniweb/product.html?shop=packstations&lang=cs&demo=1&id=9001`);
  await page.waitForSelector(".pdc-stage .v3d-root canvas", { timeout: 60000 });
  await page.waitForSelector(".pdc-ov .v3do-h", { timeout: 60000, state: "attached" }).catch(() => {});
  await page.waitForTimeout(2500);
  const hs = await page.evaluate(() => [...document.querySelectorAll(".pdc-ov .v3do-h")].map(h => ({ id: h.id || h.dataset.id || "", cap: (h.querySelector(".cap") || {}).textContent || "", vis: h.offsetParent !== null, r: (r => [Math.round(r.x + r.width / 2), Math.round(r.y + r.height / 2)])(h.getBoundingClientRect()) })));
  ok(hs.length >= 3, "O1 ve 3D jsou uchyty (tahy) z popisu serveru: " + hs.length + " | " + hs.map(h => h.cap).join(" / "));
  ok(await page.evaluate(() => typeof window.V3DOvladani === "object" && !!document.querySelector(".pdc-ov")), "O2 modul ovládání je načtený a vrstva leží uvnitř 3D okna");
  const vis = hs.filter(h => h.vis);
  const width0 = Number(await page.locator(".pdc-slot[data-slot=w] .pdc-num").inputValue());
  const target = vis.find(h => /šířk/i.test(h.cap)) || vis[0];
  if (target) {
    await page.mouse.move(target.r[0], target.r[1]); await page.mouse.down();
    for (let i = 1; i <= 10; i++) await page.mouse.move(target.r[0] + i * 8, target.r[1], { steps: 2 });
    await page.waitForTimeout(500);
    const lbl = await page.evaluate(() => [...document.querySelectorAll(".pdc-ov .v3do-lbl, .pdc-ov .v3do-tip")].filter(l => getComputedStyle(l).display !== "none").map(l => l.textContent).join(" / "));
    ok(/mm/.test(lbl), "O3 při tažení je u úchytu štítek s hodnotou v mm: " + lbl.replace(/\s+/g, " ").slice(0, 90));
    await page.mouse.up(); await page.waitForTimeout(3500);
    const width1 = Number(await page.locator(".pdc-slot[data-slot=w] .pdc-num").inputValue());
    ok(width1 !== width0, "O4 tažení úchytu změnilo hodnotu v panelu (šířka " + width0 + " → " + width1 + " mm; cílový úchyt: " + target.cap + ")");
  } else ok(false, "O3 žádný viditelný úchyt k tažení");
  await page.keyboard.press("Escape");
  // "Pridat vyrez sem": patch zapne vyrez a nastavi jeho polohu - zavisle sloty se nesmi oriznout podle starych mezi (pred zapnutim min = max = 100)
  const p3 = await ctx.newPage(); const e3 = [];
  p3.on("pageerror", e => e3.push(e.message));
  await p3.addInitScript(() => { window.__pdcDebug = true; });
  await p3.route("**/miniweb/config.cs.json", async (route) => { const r = await route.fetch(); const j = await r.json(); j.configurator_product_id = Number(PID); await route.fulfill({ response: r, json: j }); });
  await p3.goto(`${BASE}/miniweb/product.html?shop=packstations&lang=cs&demo=1&id=9001`);
  await p3.waitForFunction(() => typeof window.__pdcApplyPatch === "function" && window.__pdcState && window.__pdcState.last, null, { timeout: 60000 });
  // cekani na USTALENI stavu misto pevnych 3,5 s (pod SwiftShaderem blokuje HDRI/PMREM po prvnim modelu vlakno ~1 s a pevny cas pak nestaci; zavod starsi odpovedi hlida test_patch_zavod.js)
  const ustal = (cond) => p3.waitForFunction(cond, null, { timeout: 40000 }).catch(() => {});
  await p3.evaluate(() => window.__pdcApplyPatch({ w: 2000 })); await ustal(() => !window.__pdcState.pending && window.__pdcState.sel.w === 2000 && window.__pdcState.last.selection && window.__pdcState.last.selection.w === 2000);
  await p3.evaluate(() => window.__pdcApplyPatch({ cut1: true, cut1x: 425, cut1z: 1390 })); await ustal(() => !window.__pdcState.pending && window.__pdcState.sel.cut1 === true && window.__pdcState.last.selection && window.__pdcState.last.selection.cut1 === true);
  const cs = await p3.evaluate(() => ({ x: window.__pdcState.sel.cut1x, z: window.__pdcState.sel.cut1z, on: window.__pdcState.sel.cut1 }));
  ok(cs.on === true && Math.abs(cs.x - 425) <= 5 && Math.abs(cs.z - 1390) <= 5, "O8 patch „Přidat výřez sem“ zapne výřez a uloží místo kliknutí (cut1x " + cs.x + ", cut1z " + cs.z + "), neořízne ho na staré meze 100/100");
  ok(!e3.length, "O9 bez JS chyb u patche" + (e3[0] ? " | " + e3[0] : ""));
  ok(!errs.length, "O5 bez JS chyb" + (errs[0] ? " | " + errs[0] : ""));
  await page.screenshot({ path: (process.env.SHOTS || "/tmp") + "/ovladani3d.png" });
  await browser.close(); console.log(`\n==> ${total - bad}/${total} kontrol OK`); process.exit(bad ? 1 : 0);
})();
