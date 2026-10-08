// Kontrolní náhled složeného GLB v KANDIDÁTNÍM prohlížeči v3d (viewer3d.js z v3d/webapp, ne živý) - Playwright Chromium bez sítě
// (stejný princip jako v3d/tests/harness_viewer.js: žádný požadavek nesmí ven, vše z lokálních souborů, three r128 z node_modules).
// Použití: node viewer_smoke.js out/shape577_export.glb [ven_prefix]   -> shots/<prefix>_{iso,front,side,top}.png + výpis stavu
'use strict';
const path = require('path'), fs = require('fs');
const { chromium } = require('/opt/konfigurator/node_modules/playwright');
const K = __dirname;
const S = '/tmp/claude-0/-opt-konfigurator/3a4f3da8-6534-422d-a853-fe8654c9f7d6/scratchpad/v3d';
const ORIGIN = 'https://v3d.test';
const glb = path.resolve(process.argv[2]);
const prefix = process.argv[3] || 'stul';
const SHOTS = path.join(K, 'shots'); fs.mkdirSync(SHOTS, { recursive: true });
const MAP = [
  ['https://cdn.jsdelivr.net/npm/three@0.128.0/', '/opt/konfigurator/node_modules/three/'],
  [ORIGIN + '/js/v3d/', path.join(S, 'webapp/js/v3d/')],
  [ORIGIN + '/css/', path.join(S, 'webapp/css/')],
  [ORIGIN + '/model/', path.dirname(glb) + '/'],
  [ORIGIN + '/tests/', path.join(S, 'tests/')],
];
const CT = { '.js': 'application/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8', '.html': 'text/html; charset=utf-8', '.glb': 'model/gltf-binary', '.json': 'application/json' };
(async () => {
  const browser = await chromium.launch({ args: ['--host-resolver-rules=MAP * ~NOTFOUND', '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
  const ctx = await browser.newContext({ viewport: { width: 1100, height: 760 }, deviceScaleFactor: 1 });
  const external = [];
  await ctx.route('**/*', async route => {
    const url = route.request().url().split('#')[0];
    const hit = MAP.find(([p]) => url.startsWith(p));
    if (!hit) { external.push(url); return route.abort(); }
    const rel = decodeURIComponent(url.slice(hit[0].length).split('?')[0]);
    const file = path.resolve(hit[1], rel);
    if (!file.startsWith(path.resolve(hit[1])) || !fs.existsSync(file)) return route.fulfill({ status: 404, body: 'nf' });
    return route.fulfill({ status: 200, contentType: CT[path.extname(file)] || 'application/octet-stream', body: fs.readFileSync(file) });
  });
  const page = await ctx.newPage();
  const errors = [];
  page.on('console', m => { if (m.type() === 'error') errors.push('console: ' + m.text()); });
  page.on('pageerror', e => errors.push('pageerror: ' + e.message));
  // viewer_test.html načítá /fixtures/<glb>.glb -> přemapuj na /model/ stejným jménem
  const base = path.basename(glb, '.glb');
  await ctx.route(ORIGIN + '/fixtures/*', async route => {
    const f = path.join(path.dirname(glb), path.basename(new URL(route.request().url()).pathname));
    return route.fulfill({ status: 200, contentType: 'model/gltf-binary', body: fs.readFileSync(f) });
  });
  await page.goto(ORIGIN + '/tests/viewer_test.html?glb=' + encodeURIComponent(base) + '&allowReal=1');
  const ok = await page.evaluate(() => window.__t.ready);
  const err = await page.evaluate(() => window.__t.err);
  const s = await page.evaluate(() => window.__v3d.state());
  console.log('nacteno:', ok, err || '', '| legacy:', s.legacy, '| mode:', s.mode, '| dims:', s.dims, '| warnings:', JSON.stringify(s.warnings));
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  for (const v of ['iso', 'front', 'side', 'top']) {
    await page.evaluate(vv => window.__t.api.setView(vv), v);
    await sleep(1200);
    await page.screenshot({ path: path.join(SHOTS, prefix + '_' + v + '.png') });
  }
  const labels = await page.evaluate(() => window.__v3d.dimsLabels());
  console.log('kóty:', JSON.stringify(labels), '| externí požadavky (zablokované):', external.length, '| chyby:', JSON.stringify(errors));
  await browser.close();
})().catch(e => { console.error(e); process.exit(1); });
