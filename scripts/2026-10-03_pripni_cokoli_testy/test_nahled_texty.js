'use strict';
// Texty NAHLEDU (pravidlo 60): pripni-cokoli.html?nahled=<id> nacte volitelny nahled/<id>/texty.json a prida/prepise texty (popisky novych kroku navrhu externiho bota);
// zivy registr texty.json se nemeni a bez ?nahled= se nic z nahledu nenacita. SKUTECNY model nahledu spoj-sroubem-v1 (bot10, 2026-10-04; model od externiho bota Johna, 30x30).
// Offline (SwiftShader), nic nezapisuje. Spusteni: node test_nahled_texty.js   (bez GLB v env: modely jdou z webapp/pripni-cokoli/); jina verze nahledu: NAHLED_ID=spoj-sroubem-v2 node test_nahled_texty.js
// (casy kroku se berou z cue v GLB nahledu - verze maji ruzne casovani; bot10 2026-10-05)
const path = require('path'), fs = require('fs');
const { chromium } = require('/opt/konfigurator/node_modules/playwright');
const WEB = '/opt/konfigurator/webapp', NM = '/opt/konfigurator/node_modules/three/', ORIGIN = 'https://pc.test';
const ID = process.env.NAHLED_ID || 'spoj-sroubem-v1';
const cueMid = (id) => {                                    // stred cue `id` z extras.demo.cues v GLB nahledu (s) - verze maji ruzne casovani
  const d = fs.readFileSync(path.join(WEB, 'pripni-cokoli/nahled', ID, 'stavebnice-demo-30x30.glb'));
  const js = JSON.parse(d.slice(20, 20 + d.readUInt32LE(12)).toString('utf8')), c = js.scenes[0].extras.demo.cues.find((x) => x.id === id);
  if (!c) throw new Error('v GLB nahledu ' + ID + ' neni cue ' + id);
  return Math.round(((c.t0 + c.t1) / 2) * 10) / 10;
};
const out = [];
const ok = (n, c, d) => { out.push(!!c); console.log((c ? 'OK   ' : 'FAIL ') + n + (d !== undefined ? '  ' + JSON.stringify(d).slice(0, 300) : '')); };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
(async () => {
  if (!fs.existsSync(path.join(WEB, 'pripni-cokoli/nahled', ID, 'stavebnice-demo-30x30.glb'))) { console.error('chybi nahled ' + ID); process.exit(2); }
  const b = await chromium.launch({ args: ['--host-resolver-rules=MAP * ~NOTFOUND', '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  const errs = [], ext = [];
  let reqs = [];
  const ctx = await b.newContext({ viewport: { width: 1000, height: 900 }, deviceScaleFactor: 1 });
  await ctx.route('**/*', (route) => {
    const u = new URL(route.request().url());
    if (u.origin === 'https://cdn.jsdelivr.net') {
      const f = path.join(NM, u.pathname.replace('/npm/three@0.128.0/', ''));
      return fs.existsSync(f) ? route.fulfill({ contentType: 'application/javascript', body: fs.readFileSync(f) }) : route.fulfill({ status: 404, body: '' });
    }
    if (u.origin !== ORIGIN) { ext.push(u.href); return route.fulfill({ status: 404, body: '' }); }
    reqs.push(u.pathname);
    let p = u.pathname; if (p === '/') p = '/pripni-cokoli.html';
    const f = path.join(WEB, p);
    if (!f.startsWith(WEB) || !fs.existsSync(f) || fs.statSync(f).isDirectory()) return route.fulfill({ status: 404, body: '' });
    const ct = { '.js': 'application/javascript', '.css': 'text/css', '.html': 'text/html; charset=utf-8', '.json': 'application/json', '.glb': 'model/gltf-binary', '.svg': 'image/svg+xml', '.hdr': 'application/octet-stream' }[path.extname(f)] || 'application/octet-stream';
    return route.fulfill({ contentType: ct, body: fs.readFileSync(f) });
  });
  const open = async (query, waitCap) => {
    reqs = [];
    const page = await ctx.newPage();
    page.on('pageerror', (e) => errs.push(String(e)));
    await page.goto(ORIGIN + '/pripni-cokoli.html' + query);
    await page.waitForSelector('body.ready, body.failed', { timeout: 60000 }).catch(() => {});
    if (waitCap) {                                  // pod zatizenim stroje bezi prehravani pomalu: cekat na podminku
      for (let i = 0; i < 60; i++) { const c = await page.evaluate(() => document.getElementById('pcCap').textContent); if (waitCap.test(c)) break; await sleep(500); }
    }
    return page;
  };
  const info = (page) => page.evaluate(() => ({ ready: document.body.classList.contains('ready'), failed: document.body.classList.contains('failed'), banner: (document.querySelector('.pc-preview') || {}).textContent || '',
    chips: [...document.querySelectorAll('#pcSteps .chip')].map((c) => c.textContent.trim()), cap: document.getElementById('pcCap').textContent, title: document.title }));

  // 1) nahled s vlastnimi texty, cesky: novy krok "Spoj šroubem" a titulek nove casti animace (t=21 s = cue spoj_zavit)
  let page = await open('?profil=30&nahled=' + ID + '&lang=cs&t=' + cueMid('spoj_zavit') + '&autoplay=0', /vyřezaný závit/);
  let r = await info(page);
  ok('nahled: stranka se nacetla, oranzove upozorneni "NÁHLED ' + ID + '"', r.ready && !r.failed && r.banner.indexOf('NÁHLED ' + ID) === 0, [r.ready, r.banner.slice(0, 40)]);
  ok('nahled: tlacitka kroku maji novy krok "Spoj šroubem" (z nahled/<id>/texty.json)', r.chips.length === 5 && /5\s+Spoj šroubem/.test(r.chips[4]), r.chips);
  ok('nahled: popisek nove casti animace (cue spoj_zavit) je z nahledovych textu', /V čele nového profilu je vyřezaný závit/.test(r.cap), r.cap);
  ok('nahled: stranka si vyzadala nahled/' + ID + '/texty.json a model nahledu', reqs.some((p) => p === '/pripni-cokoli/nahled/' + ID + '/texty.json') && reqs.some((p) => p === '/pripni-cokoli/nahled/' + ID + '/stavebnice-demo-30x30.glb'), reqs.filter((p) => /nahled/.test(p)));
  await page.close();
  // 2) jine jazyky z teze sady (en, sk): popisek nove casti (t=47 = spoj_otvor) a nazev kroku
  page = await open('?profil=30&nahled=' + ID + '&lang=en&t=' + cueMid('spoj_otvor') + '&autoplay=0', /access hole/);
  r = await info(page);
  ok('nahled en: popisek "Open an access hole…" a krok "Screw connection"', /Open an access hole/.test(r.cap) && /Screw connection/.test(r.chips.join('|')), [r.cap, r.chips]);
  await page.close();
  page = await open('?profil=30&nahled=' + ID + '&lang=sk&t=' + cueMid('spoj_dotazeni') + '&autoplay=0', /dlhým imbusom/);
  r = await info(page);
  ok('nahled sk: popisek "…dlhým imbusom." a krok "Spoj skrutkou"', /dlhým imbusom/.test(r.cap) && /Spoj skrutkou/.test(r.chips.join('|')), [r.cap, r.chips]);
  await page.close();
  // 3) bez ?nahled= se nic z nahledu nenacita (zive texty a model beze zmeny)
  page = await open('?lang=cs&autoplay=0');
  r = await info(page);
  ok('bez ?nahled=: zadny pozadavek na nahled/ a zadne upozorneni', reqs.filter((p) => /nahled/.test(p)).length === 0 && r.banner === '' && r.ready, [reqs.filter((p) => /nahled/.test(p)), r.banner]);
  ok('bez ?nahled=: zive kroky bez "Spoj šroubem" (registr texty.json beze zmeny)', !r.chips.some((c) => /Spoj šroubem/.test(c)), r.chips);
  await page.close();
  // 4) nahled bez vlastnich textu (v5): nacte se normalne s zivymi texty; neplatne id se ignoruje (zadny pozadavek ven z nahled/, bez upozorneni)
  page = await open('?profil=30&nahled=v5&lang=cs&autoplay=0');
  r = await info(page);
  ok('nahled bez texty.json (v5): stranka se nacte, upozorneni je, kroky zive (bez "Spoj šroubem")', r.ready && r.banner.indexOf('NÁHLED v5') === 0 && !r.chips.some((c) => /Spoj šroubem/.test(c)), [r.ready, r.banner.slice(0, 20), r.chips]);
  await page.close();
  page = await open('?profil=30&nahled=..%2F..%2Fx&lang=cs&autoplay=0');
  r = await info(page);
  ok('neplatne id nahledu se ignoruje (zadny pozadavek na nahled/, bez upozorneni)', reqs.filter((p) => /nahled/.test(p)).length === 0 && r.banner === '', [reqs.filter((p) => /nahled/.test(p)), r.banner]);
  await page.close();
  ok('bez neodchycenych chyb a bez pozadavku ven', errs.length === 0 && ext.length === 0, { errs: errs.slice(0, 2), ext: ext.slice(0, 2) });
  await b.close();
  process.exit(out.every(Boolean) ? 0 : 1);
})().catch((e) => { console.error('CHYBA', e); process.exit(2); });
