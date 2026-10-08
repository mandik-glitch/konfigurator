'use strict';
// Offline test haceku opts.plugins (viewer 1.8.0): ctx, onFrame, setAnimating, ukonceni pri setModel/dispose, odolnost proti vyjimkam.
const path = require('path'), fs = require('fs');
const { chromium } = require('/opt/konfigurator/node_modules/playwright');
const VIEWER = process.env.VIEWER || '/opt/konfigurator/webapp/js/v3d/viewer3d.js';
const GLB_A = '/opt/konfigurator/webapp/katalog/vandr/v3d_nahled/4918.glb', GLB_B = '/opt/konfigurator/webapp/katalog/vandr/v3d_nahled/4594.glb';
const NM = '/opt/konfigurator/node_modules/three/', ORIGIN = 'https://v3d.test';
const out = [];
const ok = (n, c, d) => { out.push(!!c); console.log((c ? 'OK   ' : 'FAIL ') + n + (d !== undefined ? '  ' + JSON.stringify(d).slice(0, 300) : '')); };
(async () => {
  const b = await chromium.launch({ args: ['--host-resolver-rules=MAP * ~NOTFOUND', '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  const ctx = await b.newContext({ viewport: { width: 900, height: 600 }, deviceScaleFactor: 1 });
  const ext = [];
  await ctx.route('**/*', (route) => {
    const u = new URL(route.request().url());
    if (u.origin === 'https://cdn.jsdelivr.net') {
      const f = path.join(NM, u.pathname.replace('/npm/three@0.128.0/', ''));
      return fs.existsSync(f) ? route.fulfill({ contentType: 'application/javascript', body: fs.readFileSync(f) }) : route.fulfill({ status: 404, body: '' });
    }
    if (u.origin !== ORIGIN) { ext.push(u.href); return route.fulfill({ status: 404, body: '' }); }
    if (u.pathname === '/') return route.fulfill({ contentType: 'text/html; charset=utf-8', body: '<!doctype html><meta charset=utf-8><link rel=stylesheet href=/css/v3d.css><style>html,body{margin:0;height:100%}#v{width:100vw;height:100vh}</style><div id=v></div>' });
    if (u.pathname === '/js/v3d/viewer3d.js') return route.fulfill({ contentType: 'application/javascript', body: fs.readFileSync(VIEWER) });
    if (u.pathname.startsWith('/js/v3d/env/')) return route.fulfill({ contentType: 'application/octet-stream', body: fs.readFileSync('/opt/konfigurator/webapp' + u.pathname) });
    if (u.pathname === '/css/v3d.css') return route.fulfill({ contentType: 'text/css', body: fs.readFileSync('/opt/konfigurator/webapp/css/v3d.css') });
    if (u.pathname === '/a.glb') return route.fulfill({ contentType: 'model/gltf-binary', body: fs.readFileSync(GLB_A) });
    if (u.pathname === '/b.glb') return route.fulfill({ contentType: 'model/gltf-binary', body: fs.readFileSync(GLB_B) });
    return route.fulfill({ status: 404, body: '' });
  });
  const errs = [];
  const page = await ctx.newPage();
  page.on('pageerror', (e) => errs.push(String(e)));
  await page.goto(ORIGIN + '/');
  for (const u of ['build/three.min.js', 'examples/js/controls/OrbitControls.js', 'examples/js/loaders/GLTFLoader.js', 'examples/js/environments/RoomEnvironment.js', 'examples/js/renderers/CSS2DRenderer.js', 'examples/js/shaders/HorizontalBlurShader.js', 'examples/js/shaders/VerticalBlurShader.js'])
    await page.addScriptTag({ url: 'https://cdn.jsdelivr.net/npm/three@0.128.0/' + u });
  await page.addScriptTag({ url: ORIGIN + '/js/v3d/viewer3d.js' });
  const r = await page.evaluate(async () => {
    const sleep = (ms) => new Promise((res) => setTimeout(res, ms));
    const log = { calls: 0, ends: 0, keys: null, frames: 0, throwFrames: 0, gltfAnims: null, hasGltfScene: false, sameModel: null };
    let ctxSaved = null, off = null;
    const plugin = (c) => {
      log.calls++; ctxSaved = c; log.keys = Object.keys(c).sort();
      log.hasGltfScene = !!(c.gltf && c.gltf.scene); log.sameModel = c.model === c.gltf.scene; log.gltfAnims = (c.gltf.animations || []).length;
      off = c.onFrame((t) => { log.frames++; if (log.frames % 5 === 0) { log.throwFrames++; throw new Error('plugin frame chyba'); } });
      return () => { log.ends++; };
    };
    const badPlugin = () => { throw new Error('plugin init chyba'); };
    const a = window.V3D.mount(document.getElementById('v'), { modelUrl: '/a.glb', mode: 'real', allowReal: true, plugins: [badPlugin, plugin, 'neni-funkce'] });
    await a.ready;
    const afterReady = { calls: log.calls, warn: a.state().warnings.filter((w) => /plugin/.test(w)) };
    // 1) bez setAnimating: snimky jen na vyzadani (smycka nebezi sama)
    await sleep(500);
    const idleFrames = log.frames;
    await sleep(500);
    const idleAfter = log.frames;
    // 2) setAnimating(true): plynula smycka
    ctxSaved.setAnimating(true);
    const f0 = log.frames; await sleep(2500); const f1 = log.frames;
    ctxSaved.setAnimating(false);
    await sleep(700); const f2 = log.frames; await sleep(1500); const f3 = log.frames;
    const renderedFrames = a.debug.info().frames;
    // 3) setModel: stary plugin ukoncen, novy zavolan
    await a.setModel('/b.glb');
    const afterSet = { calls: log.calls, ends: log.ends };
    // 4) dispose: plugin ukoncen
    a.dispose();
    const afterDispose = { ends: log.ends };
    return { log, afterReady, anim: { idle: idleAfter - idleFrames, run: f1 - f0, stopped: f3 - f2 }, afterSet, afterDispose, renderedFrames };
  });
  ok('plugin zavolan po ready, kontext ma ocekavane klice', r.afterReady.calls === 1 && ['THREE', 'camera', 'container', 'controls', 'gltf', 'labels', 'model', 'onFrame', 'renderer', 'requestRender', 'root', 'scene', 'setAnimating', 'stage', 'state'].every((k) => r.log.keys.includes(k)), r.log.keys);
  ok('gltf v kontextu nese scenu a model === gltf.scene', r.log.hasGltfScene && r.log.sameModel === true);
  ok('vyjimka pri inicializaci jednoho pluginu je jen varovani (viewer funguje, dalsi plugin bezi)', r.afterReady.warn.length === 1 && /init chyba/.test(r.afterReady.warn[0]), r.afterReady.warn);
  ok('bez setAnimating zadna nepretrzita smycka (idle snimky po 500 ms je <= 1)', r.anim.idle <= 1, r.anim);
  ok('setAnimating(true): snimky bezi nepretrzite (>= 3 za 2,5 s; SwiftShader kresli ~2-6 fps, na GPU 60)', r.anim.run >= 3, r.anim);
  ok('setAnimating(false): smycka se zastavi', r.anim.stopped <= 2, r.anim);
  ok('vyjimka v onFrame nezastavi vykreslovani', r.log.throwFrames > 0 && r.renderedFrames > r.log.throwFrames, { vyjimek: r.log.throwFrames, snimku: r.renderedFrames });
  ok('setModel: stary plugin ukoncen (ends=1) a novy zavolan (calls=2)', r.afterSet.calls === 2 && r.afterSet.ends === 1, r.afterSet);
  ok('dispose: plugin ukoncen (ends=2)', r.afterDispose.ends === 2, r.afterDispose);
  ok('zadny pozadavek mimo mock', ext.length === 0, ext);
  ok('bez neodchycenych chyb stranky', errs.length === 0, errs.slice(0, 3));
  await b.close();
  process.exit(out.every(Boolean) ? 0 : 1);
})().catch((e) => { console.error('CHYBA', e); process.exit(2); });
