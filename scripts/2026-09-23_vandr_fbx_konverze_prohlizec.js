// 2026-09-23_vandr_fbx_konverze_prohlizec.js - jeden krok konverzniho
// automatu: nacte model.fbx pres patchnuty FBXLoader (three.js) v
// headless Chromium a vyexportuje GLB (jeste v METRECH, sanitizace a
// mm-skalovani resi nasledujici kroky v Pythonu - viz README.md ve
// scripts/2026-09-20_vandrawee_real_export/, odkud je cely recept).
//
// Pouziti: node 2026-09-23_vandr_fbx_konverze_prohlizec.js <render3d_url> <out.glb>
// (render3d_url uz musi mit model.fbx na miste, viz orchestrator).
const { chromium } = require('/opt/konfigurator/node_modules/playwright');
const fs = require('fs');

const url = process.argv[2];
const outPath = process.argv[3];

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.goto(url);
  try {
    await page.waitForFunction('window.__RENDER_DONE__ === true', { timeout: 30000 });
  } catch (e) {
    console.log('CHYBA: TIMEOUT');
    await browser.close();
    process.exit(1);
  }
  const debugInfo = await page.evaluate(() => window.__DEBUG__);
  const b64 = await page.evaluate(() => window.__GLB_BASE64__);
  await browser.close();
  if (debugInfo.error || debugInfo.windowError || debugInfo.exportSyncError || debugInfo.packError) {
    console.log('CHYBA: ' + JSON.stringify(debugInfo));
    process.exit(1);
  }
  if (!b64) {
    console.log('CHYBA: zadny GLB nevznikl - ' + JSON.stringify(debugInfo));
    process.exit(1);
  }
  fs.writeFileSync(outPath, Buffer.from(b64, 'base64'));
  console.log('OK ' + JSON.stringify(debugInfo));
})();
