'use strict';
// Snimky stranky Pripni cokoli nad zadanym GLB v ruznych casech (?autoplay=0&t=): jen pro vlastni kontrolu. node snimky_casu.js <glb> <vystup_prefix> t1,t2,...
const path = require('path'), fs = require('fs');
const { chromium } = require('/opt/konfigurator/node_modules/playwright');
const WEB = '/opt/konfigurator/webapp', NM = '/opt/konfigurator/node_modules/three/', ORIGIN = 'https://pc.test';
const GLB = process.argv[2], PFX = process.argv[3], TS = (process.argv[4] || '0').split(',').map(Number);
const W = parseInt(process.env.W || '900', 10), H = parseInt(process.env.H || '800', 10);
(async () => {
  const b = await chromium.launch({ args: ['--host-resolver-rules=MAP * ~NOTFOUND', '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  const ctx = await b.newContext({ viewport: { width: W, height: H }, deviceScaleFactor: 1 });
  const errs = [];
  await ctx.route('**/*', (route) => {
    const u = new URL(route.request().url());
    if (u.origin === 'https://cdn.jsdelivr.net') {
      const f = path.join(NM, u.pathname.replace('/npm/three@0.128.0/', ''));
      return fs.existsSync(f) ? route.fulfill({ contentType: 'application/javascript', body: fs.readFileSync(f) }) : route.fulfill({ status: 404, body: '' });
    }
    if (u.origin !== ORIGIN) return route.fulfill({ status: 404, body: '' });
    let p = u.pathname; if (p === '/') p = '/pripni-cokoli.html';
    if (p === '/pripni-cokoli/stavebnice-demo.glb') return route.fulfill({ contentType: 'model/gltf-binary', body: fs.readFileSync(GLB) });
    const f = path.join(WEB, p);
    if (!f.startsWith(WEB) || !fs.existsSync(f) || fs.statSync(f).isDirectory()) return route.fulfill({ status: 404, body: '' });
    const ct = { '.js': 'application/javascript', '.css': 'text/css', '.html': 'text/html; charset=utf-8', '.json': 'application/json', '.glb': 'model/gltf-binary' }[path.extname(f)] || 'application/octet-stream';
    return route.fulfill({ contentType: ct, body: fs.readFileSync(f) });
  });
  for (const t of TS) {
    const page = await ctx.newPage();
    page.on('pageerror', (e) => errs.push(String(e)));
    page.on('console', (m) => { if (m.type() === 'error') errs.push(m.text()); });
    await page.goto(ORIGIN + '/pripni-cokoli.html?lang=cs&autoplay=0&t=' + t + '&ao=vyp');
    await page.waitForSelector('body.ready, body.failed', { timeout: 60000 }).catch(() => {});
    await new Promise((r) => setTimeout(r, 2500));
    const info = await page.evaluate(() => ({ failed: document.body.classList.contains('failed'), cap: document.getElementById('pcCap').textContent, chips: [...document.querySelectorAll('#pcSteps .chip')].map((c) => c.textContent.trim()) }));
    await page.screenshot({ path: PFX + '_t' + String(t).replace('.', '_') + '.png' });
    console.log('t=' + t, JSON.stringify(info).slice(0, 220));
    await page.close();
  }
  console.log('chyby:', JSON.stringify(errs.slice(0, 4)));
  await b.close();
})().catch((e) => { console.error('CHYBA', e); process.exit(2); });
