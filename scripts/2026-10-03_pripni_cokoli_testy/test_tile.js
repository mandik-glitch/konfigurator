'use strict';
// Prvek "Pripni cokoli" pro mrizku karty (webapp/js/pripni-cokoli-tile.js): vlozeni jednim volanim, jazyk, akcent, kroky, ovladani, selhani, uklid, bez znacky.
// GLB=<stavebnice-demo.glb> (vychozi: webapp/pripni-cokoli/stavebnice-demo.glb). Offline (SwiftShader).
const path = require('path'), fs = require('fs');
const { chromium } = require('/opt/konfigurator/node_modules/playwright');
const WEB = '/opt/konfigurator/webapp', NM = '/opt/konfigurator/node_modules/three/', ORIGIN = 'https://shop.test';
const GLB = process.env.GLB || path.join(WEB, 'pripni-cokoli/stavebnice-demo.glb');
const TEXTY = JSON.parse(fs.readFileSync(path.join(WEB, 'pripni-cokoli/texty.json'), 'utf8'));
const out = [];
const APPROVED_TEXTY = JSON.stringify(Object.assign({}, TEXTY, { _profily: Object.assign({}, TEXTY._profily, { '30x30-d8': Object.assign({}, TEXTY._profily['30x30-d8'], { zive: true }) }) }));   // simulace schvaleneho registru (zive:true)
const UNAPPROVED_TEXTY = JSON.stringify(Object.assign({}, TEXTY, { _profily: Object.assign({}, TEXTY._profily, { '30x30-d8': Object.assign({}, TEXTY._profily['30x30-d8'], { zive: false }) }) }));   // simulace NEschvalene varianty (pravidlo 60); zivy registr je od 2026-10-04 schvaleny (Robert, Johnova v5)
const ok = (n, c, d) => { out.push(!!c); console.log((c ? 'OK   ' : 'FAIL ') + n + (d !== undefined ? '  ' + JSON.stringify(d).slice(0, 300) : '')); };
const until = async (page, fn, ms = 30000) => { const t0 = Date.now(); while (Date.now() - t0 < ms) { if (await page.evaluate(fn)) return true; await new Promise((r) => setTimeout(r, 150)); } return false; };
(async () => {
  const b = await chromium.launch({ args: ['--host-resolver-rules=MAP * ~NOTFOUND', '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  const ctx = await b.newContext({ viewport: { width: 700, height: 900 }, deviceScaleFactor: 1 });
  const ext = [], seen = [], errs = [];
  await ctx.route('**/*', (route) => {
    const u = new URL(route.request().url());
    if (u.origin === 'https://cdn.jsdelivr.net') {
      const f = path.join(NM, u.pathname.replace('/npm/three@0.128.0/', ''));
      return fs.existsSync(f) ? route.fulfill({ contentType: 'application/javascript', body: fs.readFileSync(f) }) : route.fulfill({ status: 404, body: '' });
    }
    if (u.origin !== ORIGIN) { ext.push(u.href); return route.fulfill({ status: 404, body: '' }); }
    seen.push(u.pathname);
    if (u.pathname === '/') return route.fulfill({ contentType: 'text/html; charset=utf-8', body: '<!doctype html><meta charset=utf-8><body style="margin:0;background:#111"><div style="display:grid;grid-template-columns:360px 1fr;gap:12px;padding:12px"><div id="a"></div><div id="b"></div></div>' });
    if (u.pathname === '/pripni-cokoli/stavebnice-demo.glb') return route.fulfill({ contentType: 'model/gltf-binary', body: fs.readFileSync(GLB) });
    if (u.pathname === '/pripni-cokoli-schvaleno/texty.json') return route.fulfill({ contentType: 'application/json', body: APPROVED_TEXTY });
    if (u.pathname === '/pripni-cokoli-neschvaleno/texty.json') return route.fulfill({ contentType: 'application/json', body: UNAPPROVED_TEXTY });
    if (u.pathname === '/pripni-cokoli-neschvaleno/stavebnice-demo.glb') return route.fulfill({ contentType: 'model/gltf-binary', body: fs.readFileSync(GLB) });
    if (u.pathname === '/pripni-cokoli-neschvaleno/stavebnice-demo-30x30.glb') return route.fulfill({ contentType: 'model/gltf-binary', body: fs.readFileSync(path.join(WEB, 'pripni-cokoli/stavebnice-demo-30x30.glb')) });
    if (u.pathname === '/pripni-cokoli-schvaleno/stavebnice-demo.glb') return route.fulfill({ contentType: 'model/gltf-binary', body: fs.readFileSync(GLB) });
    if (u.pathname === '/pripni-cokoli-schvaleno/stavebnice-demo-30x30.glb') return route.fulfill({ contentType: 'model/gltf-binary', body: fs.readFileSync(path.join(WEB, 'pripni-cokoli/stavebnice-demo-30x30.glb')) });
    if (u.pathname === '/pripni-cokoli/stavebnice-demo-30x30.glb') return route.fulfill({ contentType: 'model/gltf-binary', body: fs.readFileSync(path.join(WEB, 'pripni-cokoli/stavebnice-demo-30x30.glb')) });
    const m = /^\/(js\/v3d\/[A-Za-z0-9_.-]+\.js|js\/v3d\/env\/[A-Za-z0-9_.-]+|css\/v3d\.css|js\/pripni-cokoli-tile\.js|pripni-cokoli\/texty\.json)$/.exec(u.pathname);   // jako whitelist mini-shopu
    if (m && fs.existsSync(path.join(WEB, m[1]))) return route.fulfill({ contentType: /\.js$/.test(m[1]) ? 'application/javascript' : (/\.json$/.test(m[1]) ? 'application/json' : (/\.css$/.test(m[1]) ? 'text/css' : 'application/octet-stream')), body: fs.readFileSync(path.join(WEB, m[1])) });
    return route.fulfill({ status: 404, body: '' });
  });
  const page = await ctx.newPage();
  page.on('pageerror', (e) => errs.push(String(e)));
  await page.goto(ORIGIN + '/');
  await page.addStyleTag({ url: ORIGIN + '/css/v3d.css' });
  await page.addScriptTag({ url: ORIGIN + '/js/pripni-cokoli-tile.js' });
  // 1) vlozeni jednim volanim (anglicky, tyrkysovy akcent, kroky); viewer a plugin si prvek nacte sam
  const r1 = await page.evaluate(async () => {
    const c = await window.PripniCokoliTile.mount(document.getElementById('a'), { lang: 'en', accent: '#14b8a6', steps: true });
    window.__c = c;
    return { hasCtl: !!c && typeof c.destroy === 'function', viewer: !!window.V3D && !!window.V3D.demoPlugin };
  });
  ok('mount jednim volanim: viewer i plugin se nacetly sami, ovladac s destroy()', r1.hasCtl && r1.viewer, r1);
  await until(page, () => document.querySelector('#a .v3d-demo-tag') && /\w/.test(document.querySelector('#a .v3d-demo-tag').textContent), 60000);
  const r2 = await page.evaluate(() => ({ cap: document.querySelector('#a .v3d-demo-tag').textContent, capEl: !!document.querySelector('#a .pct-cap'), chips: [...document.querySelectorAll('#a .pct-chip')].map((x) => x.textContent.trim()),
    h: document.querySelector('#a .pct-view').getBoundingClientRect().height, w: document.querySelector('#a .pct-view').getBoundingClientRect().width, sw: document.documentElement.scrollWidth, iw: innerWidth, canvas: !!document.querySelector('#a canvas') }));
  const enCues = Object.values(TEXTY.en.cues);
  ok('anglicky popisek v 3D z texty.json (en), 3D platno v prvku, titulek pod prvkem se nezobrazuje (caption:false)', enCues.includes(r2.cap) && r2.canvas && !r2.capEl, r2.cap);
  ok('kroky (steps:true): aspon 3 tlacitka s anglickymi popisky, pomer 4:3, bez horizontalniho scrollu', r2.chips.length >= 3 && /Profile|Slot nut|Rotating|Anything/.test(r2.chips.join(' ')) && Math.abs(r2.w / r2.h - 4 / 3) < 0.05 && r2.sw <= r2.iw, r2);
  // 2) uzke policko (360 px): popisky nahore (pruh), akcent z options
  await until(page, () => document.querySelector('#a .v3d-demo-tag'), 40000);
  const r3 = await page.evaluate(() => { const t = document.querySelector('#a .v3d-demo-tag'), ov = document.querySelector('#a .v3d-demo-ov'); return { tag: !!t, topMode: !!ov && ov.classList.contains('top'), border: t ? getComputedStyle(t).borderTopColor : null }; });
  ok('na uzkem policku (360 px) je popisek v pruhu nahore a ma barvu akcentu #14b8a6', r3.tag && r3.topMode && r3.border === 'rgb(20, 184, 166)', r3);
  // 3) ovladani: pauza / pokracovat / od zacatku; kliknuti na krok jede dal
  const lab = () => page.evaluate(() => document.querySelector('#a .pct-btn').getAttribute('aria-label'));
  const l0 = await lab(); await page.click('#a .pct-btn'); const l1 = await lab(); await page.click('#a .pct-btn'); const l2 = await lab();
  ok('tlacitko pauza/prehrat meni popisek (Pause -> Play -> Pause)', l0 === 'Pause' && l1 === 'Play' && l2 === 'Pause', [l0, l1, l2]);
  await page.click('#a .pct-chip:nth-child(2)'); await new Promise((r) => setTimeout(r, 500));
  const r4 = await page.evaluate(() => ({ lab: document.querySelector('#a .pct-btn').getAttribute('aria-label'), on: [...document.querySelectorAll('#a .pct-chip.on')].map((x) => x.textContent.trim()) }));
  ok('klik na krok 2: animace jede dal (tlacitko Pause) a krok je zvyrazneny', r4.lab === 'Pause' && r4.on.length === 1, r4);
  // 4) siroke policko vedle: jazyk mimo seznam -> cestina; popisky vlevo (side)
  await page.evaluate(async () => { document.getElementById('b').style.width = '900px'; await window.PripniCokoliTile.mount(document.getElementById('b'), { lang: 'de' }); });
  await until(page, () => document.querySelector('#b .v3d-demo-tag') && /\w/.test(document.querySelector('#b .v3d-demo-tag').textContent), 60000);
  const r5 = await page.evaluate(() => ({ cap: document.querySelector('#b .v3d-demo-tag').textContent }));
  const csCues = Object.values(TEXTY.cs.cues);
  ok('jazyk mimo aktivni (de) = cestina (de/pl jsou vypnute do overeni)', csCues.includes(r5.cap), r5.cap);
  await until(page, () => document.querySelector('#b .v3d-demo-ov'), 40000);
  const r5b = await page.evaluate(() => { const ov = document.querySelector('#b .v3d-demo-ov'); return { cls: ov ? ov.className : '', w: document.querySelector('#b .pct-view').getBoundingClientRect().width }; });
  ok('na sirokem policku (nad 640 px) jsou popisky vlevo (side)', /side/.test(r5b.cls) || r5b.w < 640, r5b);
  // 4b) automaticke parovani podle profilu generatoru + vypnuta (neschvalena) varianta 30x30 (pravidlo 60): na zive se pro profil 30 nic neukaze; po schvaleni (zive:true) se sama sparuje
  const seen0 = seen.length;
  const rp = await page.evaluate(async () => {
    const h1 = document.createElement('div'); h1.style.width = '360px'; document.body.appendChild(h1);
    const NESCHV = { assetBase: '/pripni-cokoli-neschvaleno/' };
    const c1 = await window.PripniCokoliTile.mount(h1, { profile: 'Stůl systém 30 SP002', lang: 'cs', assetBase: NESCHV.assetBase });
    const h2 = document.createElement('div'); h2.style.width = '360px'; document.body.appendChild(h2);
    const c2 = await window.PripniCokoliTile.mount(h2, { profile: '45x45' });
    const h3 = document.createElement('div'); h3.style.width = '360px'; document.body.appendChild(h3);
    const c3 = await window.PripniCokoliTile.mount(h3, { profile: '40x40', lang: 'cs' });
    return { c1: c1 === null, empty1: h1.children.length === 0, c2: c2 === null, empty2: h2.children.length === 0, c3: !!c3,
      s30: await window.PripniCokoliTile.supports('30x30', NESCHV), s45: await window.PripniCokoliTile.supports('45x45'), s40: await window.PripniCokoliTile.supports('40x40'), sobj: await window.PripniCokoliTile.supports('Object_7', NESCHV) };
  });
  ok('NESCHVALENA varianta 30x30 (zive:false v simulovanem registru, pravidlo 60): "Stůl systém 30 SP002" -> mount vrati null a policko je prazdne, model 30x30 se nenacita; supports(30x30, Object_7) = false', rp.c1 && rp.empty1 && !rp.s30 && !rp.sobj && !seen.slice(seen0).some((p) => /30x30/.test(p)), rp);
  ok('profil bez animace (45x45) = null a prazdne policko; profil 40x40 se sparuje a supports(40x40) = true, supports(45x45) = false', rp.c2 && rp.empty2 && rp.c3 && rp.s40 && !rp.s45, rp);
  const seen1 = seen.length;
  const ra = await page.evaluate(async () => {
    const h = document.createElement('div'); h.style.width = '360px'; document.body.appendChild(h);
    const c = await window.PripniCokoliTile.mount(h, { profile: 'Stůl systém 30 SP002', lang: 'cs' });
    return { c: !!c, s30: await window.PripniCokoliTile.supports('30x30'), s30sim: await window.PripniCokoliTile.supports('30x30', { assetBase: '/pripni-cokoli-schvaleno/' }) };
  });
  await until(page, () => [...document.querySelectorAll('.v3d-demo-tag')].some((t) => /30×30/.test(t.textContent)), 60000);
  const tag30 = await page.evaluate(() => [...document.querySelectorAll('.v3d-demo-tag')].map((t) => t.textContent).find((s) => /30×30/.test(s)) || null);
  ok('ZIVY registr je schvaleny (Robert 2026-10-04, Johnova v5): "Stůl systém 30 SP002" se sam spáruje s animací 30x30: stahne se /pripni-cokoli/stavebnice-demo-30x30.glb, první věta je o profilu 30×30 a supports(30x30) = true (i v simulaci zive:true)', ra.c && ra.s30 && ra.s30sim && seen.slice(seen1).some((p) => /stavebnice-demo-30x30\.glb$/.test(p)) && !!tag30, { ra, tag30 });
  // 5) selhani: neexistujici assetBase = hlaska a skryte ovladani
  const r6 = await page.evaluate(async () => { const h = document.createElement('div'); document.body.appendChild(h); h.style.width = '360px';
    await window.PripniCokoliTile.mount(h, { assetBase: '/nic/' }); return { failed: !!h.querySelector('.pct.failed'), cap: h.querySelector('.pct-cap').textContent, ctl: getComputedStyle(h.querySelector('.pct-ctl')).display }; });
  ok('neexistujici assetBase: prvek hlasi chybu textem a skryje ovladani', r6.failed && r6.cap.length > 3 && r6.ctl === 'none', r6);
  // 6) uklid
  const r7 = await page.evaluate(() => { window.__c.destroy(); return { left: document.getElementById('a').children.length, ov: document.querySelectorAll('#a .v3d-demo-ov, #a .v3d-demo-tag').length }; });
  ok('destroy() uklidi prvek z policka', r7.left === 0 && r7.ov === 0, r7);
  // 7) bez znacky a jen povolene cesty (whitelist mini-shopu)
  const BRAND = /logiman|dogus|doguskalip|vandr|vanDrawee/i;
  const files = ['js/pripni-cokoli-tile.js', 'js/v3d/demo-stavebnice.js', 'pripni-cokoli/texty.json'].map((f) => [f, fs.readFileSync(path.join(WEB, f), 'utf8')]);
  const glbStr = fs.readFileSync(GLB).toString('latin1');
  const hits = files.filter(([, s]) => BRAND.test(s)).map(([f]) => f).concat(BRAND.test(glbStr) ? ['stavebnice-demo.glb'] : []);
  ok('bez znacky: v prvku, pluginu, texty.json ani v GLB neni Logiman/Dogus/Vandr', hits.length === 0, hits);
  const allowed = /^\/(js\/v3d\/|css\/v3d\.css|js\/pripni-cokoli-tile\.js|pripni-cokoli(-schvaleno|-neschvaleno)?\/(texty\.json|stavebnice-demo(-30x30)?\.glb)|nic\/|$)/;
  const bad = [...new Set(seen.filter((p) => !allowed.test(p)))];
  ok('prvek sahne jen na cesty: /js/v3d/*, /css/v3d.css, /js/pripni-cokoli-tile.js, /pripni-cokoli/texty.json a stavebnice-demo.glb / -30x30.glb (schema-*.svg nepotrebuje)', bad.length === 0, bad);
  ok('zadne pozadavky ven (jen three z CDN)', ext.length === 0, ext);
  ok('bez neodchycenych chyb stranky', errs.length === 0, errs.slice(0, 3));
  await b.close();
  process.exit(out.every(Boolean) ? 0 : 1);
})().catch((e) => { console.error('CHYBA', e); process.exit(2); });
