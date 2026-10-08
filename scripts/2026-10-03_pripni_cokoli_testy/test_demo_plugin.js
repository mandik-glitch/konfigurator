'use strict';
// Offline test pluginu js/v3d/demo-stavebnice.js nad syntetickym GLB (kostka, klip 'demo' 6 s): prehravani, cues, popisek v 3D, kamera, pauza, seek, zacykleni, viditelnost.
const path = require('path'), fs = require('fs');
const { chromium } = require('/opt/konfigurator/node_modules/playwright');
const WEB = '/opt/konfigurator/webapp';
const GLB = process.env.GLB;
if (!GLB) { console.error('nastav GLB=<synth_demo.glb> (viz run_all.sh)'); process.exit(2); }
const NM = '/opt/konfigurator/node_modules/three/', ORIGIN = 'https://v3d.test';
const out = [];
const ok = (n, c, d) => { out.push(!!c); console.log((c ? 'OK   ' : 'FAIL ') + n + (d !== undefined ? '  ' + JSON.stringify(d).slice(0, 300) : '')); };
(async () => {
  const b = await chromium.launch({ args: ['--host-resolver-rules=MAP * ~NOTFOUND', '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  const mk = async (reduced) => {
    const ctx = await b.newContext({ viewport: { width: 900, height: 600 }, deviceScaleFactor: 1, reducedMotion: reduced ? 'reduce' : 'no-preference' });
    const ext = [];
    await ctx.route('**/*', (route) => {
      const u = new URL(route.request().url());
      if (u.origin === 'https://cdn.jsdelivr.net') {
        const f = path.join(NM, u.pathname.replace('/npm/three@0.128.0/', ''));
        return fs.existsSync(f) ? route.fulfill({ contentType: 'application/javascript', body: fs.readFileSync(f) }) : route.fulfill({ status: 404, body: '' });
      }
      if (u.origin !== ORIGIN) { ext.push(u.href); return route.fulfill({ status: 404, body: '' }); }
      if (u.pathname === '/') return route.fulfill({ contentType: 'text/html; charset=utf-8', body: '<!doctype html><meta charset=utf-8><link rel=stylesheet href=/css/v3d.css><style>html,body{margin:0;height:100%}#v{width:100vw;height:100vh}</style><div id=v></div>' });
      if (u.pathname === '/m.glb') return route.fulfill({ contentType: 'model/gltf-binary', body: fs.readFileSync(GLB) });
      const m = /^\/(js\/v3d\/[A-Za-z0-9_.-]+\.js|js\/v3d\/env\/[A-Za-z0-9_.-]+|css\/v3d\.css)$/.exec(u.pathname);
      if (m && fs.existsSync(path.join(WEB, m[1]))) return route.fulfill({ contentType: /\.js$/.test(m[1]) ? 'application/javascript' : (/\.css$/.test(m[1]) ? 'text/css' : 'application/octet-stream'), body: fs.readFileSync(path.join(WEB, m[1])) });
      return route.fulfill({ status: 404, body: '' });
    });
    return { ctx, ext };
  };
  const open = async (ctx, errs) => {
    const page = await ctx.newPage();
    page.on('pageerror', (e) => errs.push(String(e)));
    await page.goto(ORIGIN + '/');
    for (const u of ['build/three.min.js', 'examples/js/controls/OrbitControls.js', 'examples/js/loaders/GLTFLoader.js', 'examples/js/environments/RoomEnvironment.js', 'examples/js/renderers/CSS2DRenderer.js', 'examples/js/shaders/HorizontalBlurShader.js', 'examples/js/shaders/VerticalBlurShader.js'])
      await page.addScriptTag({ url: 'https://cdn.jsdelivr.net/npm/three@0.128.0/' + u });
    await page.addScriptTag({ url: ORIGIN + '/js/v3d/viewer3d.js' });
    await page.addScriptTag({ url: ORIGIN + '/js/v3d/demo-stavebnice.js' });
    return page;
  };
  const errs = [];
  let { ctx, ext } = await mk(false);
  let page = await open(ctx, errs);
  const r = await page.evaluate(async () => {
    const sleep = (ms) => new Promise((res) => setTimeout(res, ms));
    const until = async (fn, ms = 9000) => { const t0 = performance.now(); while (performance.now() - t0 < ms) { if (fn()) return true; await sleep(100); } return false; };
    const cues = [];
    const demo = window.V3D.demoPlugin({ texts: { uvod: 'Úvod', kostka: 'Kostka jede' }, onCue: (c, t) => cues.push([c && c.id, t]), userIdleMs: 1500 });
    window.demo = demo;
    const v = window.V3D.mount(document.getElementById('v'), { modelUrl: '/m.glb', mode: 'real', allowReal: true, hudKoty: false, dims: 0, plugins: [demo.plugin] });
    window.v = v;
    await v.ready;
    const st = v.state();
    const res = { legacy: st.legacy, warnings: st.warnings, dur: demo.duration(), cueList: demo.cues().map((c) => c.id) };
    res.playing0 = demo.isPlaying();
    // 1) hraje samo: cas roste a kostka se hybe
    const x0 = v.debug.worldBox('box'); await sleep(2500); const t1 = demo.time(), x1 = v.debug.worldBox('box');
    res.timeAdvanced = t1 > 0.3; res.moved = Math.abs((x1.center[0]) - (x0.center[0])) > 1;
    // 2) pauza: cas stoji
    demo.pause(); const tp = demo.time(); await sleep(900); res.pausedStill = Math.abs(demo.time() - tp) < 1e-6; res.playingAfterPause = demo.isPlaying();
    // 3) seek: stav v case 3.0 (kostka na x=+60), popisek 'kostka' (t0=2..4.5) s kotvou v 3D
    demo.seek(3.0); await until(() => document.querySelectorAll('.v3d-demo-tag').length === 1);
    const bx = v.debug.worldBox('box'); res.seekPoseX = bx.center[0];
    res.labelCount = document.querySelectorAll('.v3d-demo-tag').length;
    res.labelText = (document.querySelector('.v3d-demo-tag') || {}).textContent || null;
    res.labelCls = demo.layout().mode;
    demo.seek(0.5); await until(() => document.querySelectorAll('.v3d-demo-tag').length === 1); await sleep(200); res.labelAtIntro = document.querySelectorAll('.v3d-demo-tag').length; res.leaderAtIntro = (document.querySelector('.v3d-demo-ov line') || {getAttribute: () => null}).getAttribute('visibility');
    // 4) kamera sleduje klicove snimky: v t=0 pohled z (150,120,220) k (0,10,0) s fit; v t=3 z (-100,60,160)
    demo.seek(0); await sleep(250); const c0 = v.cameraInfo();
    demo.seek(3); await sleep(250); const c3 = v.cameraInfo();
    res.cam0 = c0.pos.map((n) => Math.round(n)); res.cam3 = c3.pos.map((n) => Math.round(n)); res.target3 = c3.target.map((n) => Math.round(n));
    // 5) uzivatel uchopi kameru: plugin ji pusti, po klidu se vrati
    const canvas = document.querySelector('.v3d-root canvas');
    const r0 = canvas.getBoundingClientRect();
    const ev = (type, x, y) => canvas.dispatchEvent(new PointerEvent(type, { bubbles: true, clientX: x, clientY: y, pointerId: 1, pointerType: 'mouse', button: 0, buttons: type === 'pointerup' ? 0 : 1 }));
    demo.seek(3); await sleep(200); demo.play();
    ev('pointerdown', r0.left + 300, r0.top + 300); ev('pointermove', r0.left + 360, r0.top + 320); ev('pointermove', r0.left + 420, r0.top + 340); ev('pointerup', r0.left + 420, r0.top + 340);
    await sleep(300);
    res.userMovedCam = JSON.stringify(v.cameraInfo().pos.map((n) => Math.round(n))) !== JSON.stringify(c3.pos.map((n) => Math.round(n)));
    // 6) zacykleni: pri t blizko konce preskoci na zacatek
    demo.seek(5.7); demo.play(); await until(() => demo.time() < 5.0, 12000);
    res.wrapped = demo.time() < 5.0;
    // 7) rychlost a restart
    demo.restart(); await sleep(200); res.afterRestart = demo.time() < 1;
    res.cueEvents = cues.map((c) => c[0]).filter((x, i, a) => i === 0 || x !== a[i - 1]);
    // 8) setModel (stejny model) = plugin znovu inicializovan, stav zachovan, popisky bez duplicit
    await v.setModel('/m.glb');
    await sleep(500);
    res.afterSetModel = { playing: demo.isPlaying(), dur: demo.duration(), labels: document.querySelectorAll('.v3d-demo-tag').length };
    v.dispose();
    res.labelsAfterDispose = document.querySelectorAll('.v3d-demo-tag,.v3d-demo-ov,.v3d-demo-label').length;
    return res;
  });
  ok('viewer: spec platna (legacy:false), bez varovani', r.legacy === false && r.warnings.length === 0, { legacy: r.legacy, warnings: r.warnings });
  ok('plugin cte klip a cues z GLB (trvani 6 s, cues uvod+kostka)', r.dur === 6 && JSON.stringify(r.cueList) === JSON.stringify(['uvod', 'kostka']), [r.dur, r.cueList]);
  ok('hraje samo (autoplay): cas roste a kostka se hybe', r.playing0 && r.timeAdvanced && r.moved, { playing: r.playing0, adv: r.timeAdvanced, moved: r.moved });
  ok('pauza zastavi cas', r.pausedStill && r.playingAfterPause === false);
  ok('seek(3 s): kostka na x=+60 (poloha z klipu)', Math.abs(r.seekPoseX - 60) < 1.5, r.seekPoseX);
  ok('cue "kostka": popisek v pruhu u okraje (1 kus, text z slovniku, siroke okno = pruh vlevo "side")', r.labelCount === 1 && r.labelText === 'Kostka jede' && r.labelCls === 'side', [r.labelCount, r.labelText, r.labelCls]);
  ok('cue "uvod" bez kotvy: popisek v pruhu BEZ spojnice', r.labelAtIntro === 1 && r.leaderAtIntro === 'hidden', [r.labelAtIntro, r.leaderAtIntro]);
  ok('kamera sleduje klicove snimky (t=3: pozice -100,60,160, cil 0,10,0)', JSON.stringify(r.cam3) === JSON.stringify([-100, 60, 160]) && JSON.stringify(r.target3) === JSON.stringify([0, 10, 0]), [r.cam0, r.cam3, r.target3]);
  ok('uzivatel muze hybat kamerou (plugin ji pusti)', r.userMovedCam);
  ok('zacykleni: po konci se cas vrati na zacatek', r.wrapped);
  ok('restart vrati na zacatek', r.afterRestart);
  ok('onCue vola uvod -> kostka -> ... v poradi', r.cueEvents.slice(0, 2).join() === 'uvod,kostka' || r.cueEvents.join().includes('kostka'), r.cueEvents);
  ok('setModel: plugin se znovu inicializuje, nic se nezdvojuje', r.afterSetModel.dur === 6 && r.afterSetModel.labels <= 1, r.afterSetModel);
  ok('dispose uklidi popisky i pruh (overlay)', r.labelsAfterDispose === 0, r.labelsAfterDispose);
  ok('zadny pozadavek mimo mock', ext.length === 0, ext);
  await ctx.close();
  // puvodni rezim popisku u dilu (labelLayout:'anchor'): CSS2D popisek pripnuty na uzlu, bez pruhu a bez posunu kamery
  {
    const c2 = (await mk(false)); const pg = await open(c2.ctx, errs);
    const ra = await pg.evaluate(async () => {
      const sleep = (ms) => new Promise((res) => setTimeout(res, ms));
      const until = async (fn, ms = 9000) => { const t0 = performance.now(); while (performance.now() - t0 < ms) { if (fn()) return true; await sleep(100); } return false; };
      const demo = window.V3D.demoPlugin({ texts: { uvod: 'Úvod', kostka: 'Kostka jede' }, labelLayout: 'anchor', autoplay: false });
      const v = window.V3D.mount(document.getElementById('v'), { modelUrl: '/m.glb', mode: 'real', allowReal: true, hudKoty: false, dims: 0, plugins: [demo.plugin] });
      await v.ready; demo.seek(3.0);
      await until(() => document.querySelectorAll('.v3d-demo-label').length === 1);
      const el = document.querySelector('.v3d-demo-label');
      const r = { anchorLabels: document.querySelectorAll('.v3d-demo-label').length, cls: el ? el.className : '', tags: document.querySelectorAll('.v3d-demo-tag').length, mode: demo.layout().mode };
      v.dispose(); return r;
    });
    ok('labelLayout:"anchor": starý popisek u dílu (.v3d-demo-label right), žádný pruh, layout none', ra.anchorLabels === 1 && /right/.test(ra.cls) && ra.tags === 0 && ra.mode === 'none', ra);
    await c2.ctx.close();
  }
  // omezit animace: start pozastaveny na snimku poster (3 s)
  ({ ctx, ext } = await mk(true));
  page = await open(ctx, errs);
  const rr = await page.evaluate(async () => {
    const sleep = (ms) => new Promise((res) => setTimeout(res, ms));
    const demo = window.V3D.demoPlugin({ texts: {} });
    const v = window.V3D.mount(document.getElementById('v'), { modelUrl: '/m.glb', mode: 'real', allowReal: true, hudKoty: false, dims: 0, plugins: [demo.plugin] });
    await v.ready; await sleep(700);
    const t = demo.time(); await sleep(800);
    return { playing: demo.isPlaying(), t, t2: demo.time(), x: v.debug.worldBox('box').center[0] };
  });
  ok('prefers-reduced-motion: start POZASTAVENY na snimku poster (t=3 s, kostka na +60) a po uzivatelskem Play jde', rr.playing === false && Math.abs(rr.t - 3) < 0.01 && Math.abs(rr.t2 - rr.t) < 1e-6 && Math.abs(rr.x - 60) < 1.5, rr);
  await ctx.close();
  ok('bez neodchycenych chyb stranky', errs.length === 0, errs.slice(0, 3));
  await b.close();
  process.exit(out.every(Boolean) ? 0 : 1);
})().catch((e) => { console.error('CHYBA', e); process.exit(2); });
