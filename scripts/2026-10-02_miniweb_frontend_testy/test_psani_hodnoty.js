// Hodnota, kterou zakaznik PRAVE PISE do pole slideru (udalost input, potvrzeni az change/blur), se nesmi ztratit, kdyz mezitim dorazi odpoved serveru nebo se prekresli stav (applyState): nalez 2026-10-05
// (druhy vypocet auto_on po startu / nacteni modelu zapsal do pole puvodni hodnotu, udalost change uz nenastala a zmena se neodeslala). Deterministicky: input bez change + synteticke prekresleni
// (window.__pdcApplyPatch({}) vola applyState). Nad skutecnym schematem a generatorem (bridge.py, PID = system 30).
const { chromium } = require("/opt/konfigurator/node_modules/playwright");
const BASE = process.env.BASE, PID = process.env.PID;
let bad = 0, total = 0; const ok = (c, t) => { total++; if (!c) bad++; console.log(`[${c ? "OK   " : "CHYBA"}] ${t}`); };
const W = ".pdc-slot[data-slot=w] .pdc-num", R = ".pdc-slot[data-slot=w] .pdc-range";
(async () => {
  const browser = await chromium.launch({ args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
  const page = await (await browser.newContext({ viewport: { width: 1300, height: 900 } })).newPage(); const errs = [];
  page.on("pageerror", e => errs.push(e.message));
  await page.addInitScript(() => { window.__pdcDebug = true; });
  await page.goto(`${BASE}/embed/stul.html?p=${PID}`); await page.locator(W).waitFor({ timeout: 90000 }); await page.locator(".emb-order-btn:not([disabled])").waitFor({ timeout: 90000 }); await page.waitForTimeout(2500);
  const val = () => page.locator(W).inputValue(), selW = () => page.evaluate(() => window.__pdcState.sel.w);
  const w0 = await selW();
  // 1) rozepsane cislo prezije prekresleni
  await page.locator(W).fill("1400");                                         // input bez change (pole zustava s fokusem)
  await page.evaluate(() => window.__pdcApplyPatch({}));                      // applyState(): jako odpoved serveru / nacteni modelu
  ok((await val()) === "1400" && (await selW()) === w0, "W1 rozepsané číslo (1400) přežilo překreslení stavu; výběr se zatím nezměnil (" + w0 + ")");
  // 2) potvrzeni (blur -> change) odesle zmenu a po odpovedi pole ukazuje hodnotu serveru
  await page.locator(W).blur();
  await page.waitForFunction(() => window.__pdcState.sel.w === 1400 && !window.__pdcState.pending, null, { timeout: 60000 });
  ok((await val()) === "1400" && (await selW()) === 1400, "W2 po potvrzení (blur) se hodnota odeslala a pole ukazuje 1400");
  // 3) po potvrzeni uz pole prekreslovani poslouchá (neni "dirty"): zmena vyberu zvenku se v poli ukaze
  await page.evaluate(() => window.__pdcApplyPatch({ w: 1600 })); await page.waitForFunction(() => window.__pdcState.sel.w === 1600 && !window.__pdcState.pending, null, { timeout: 60000 });
  ok((await val()) === "1600", "W3 po potvrzení pole zase sleduje výběr (změna zvenku, např. ze 3D, se v poli ukáže): " + await val());
  // 4) posuvnik: tazeni (input bez change) take neskoci zpet
  await page.evaluate((sel) => { const r = document.querySelector(sel); r.focus(); r.value = "1700"; r.dispatchEvent(new Event("input", { bubbles: true })); }, R);
  await page.evaluate(() => window.__pdcApplyPatch({}));
  ok((await page.locator(R).inputValue()) === "1700" && (await val()) === "1700", "W4 tažení posuvníku (input bez change) nevrátí hodnotu na původní: " + await page.locator(R).inputValue());
  await page.evaluate((sel) => { const r = document.querySelector(sel); r.dispatchEvent(new Event("change", { bubbles: true })); r.blur(); }, R);
  await page.waitForFunction(() => window.__pdcState.sel.w === 1700 && !window.__pdcState.pending, null, { timeout: 60000 });
  ok((await val()) === "1700" && (await selW()) === 1700, "W5 po puštění posuvníku se hodnota potvrdila: 1700");
  // 5) pole, ktere zakaznik opustil bez zmeny (blur), se zase synchronizuje
  await page.locator(W).focus(); await page.locator(W).fill("1234"); await page.locator(W).fill("1700"); await page.locator(W).blur();
  await page.evaluate(() => window.__pdcApplyPatch({ w: 1750 })); await page.waitForFunction(() => window.__pdcState.sel.w === 1750 && !window.__pdcState.pending, null, { timeout: 60000 });
  ok((await val()) === "1750", "W6 pole opuštěné bez změny se po blur zase synchronizuje s výběrem: " + await val());
  ok(!errs.length, "W7 bez JS chyb" + (errs[0] ? " | " + errs[0] : ""));
  await Promise.race([browser.close(), new Promise(r => setTimeout(r, 15000))]); console.log(`\n==> ${total - bad}/${total} kontrol OK`); process.exit(bad ? 1 : 0);
})();
