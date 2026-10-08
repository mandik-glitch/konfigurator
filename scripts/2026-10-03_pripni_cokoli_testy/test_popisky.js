'use strict';
// Popisky v pruhu u okraje (labelLayout 'margin') nad SKUTECNYM modelem: popisek nesmi zakryvat aktivni dily ani bod, kam miri spojnice.
// Pro kazdy cue s kotvou a pro tri velikosti okna (siroke, mobil, nizke siroke) se v polovine cue zmeri obdelnik popisku, obdelnik aktivnich dilu
// (cue.g bez profilu, pokud je i neco jineho) a bod kotvy. GLB=<cesta k stavebnice-demo.glb> (povinne), texty se berou z webapp/pripni-cokoli/texty.json (cs).
const path = require('path'), fs = require('fs');
const { chromium } = require('/opt/konfigurator/node_modules/playwright');
const WEB = '/opt/konfigurator/webapp', NM = '/opt/konfigurator/node_modules/three/', ORIGIN = 'https://v3d.test';
const GLB = process.env.GLB;
if (!GLB) { console.error('nastav GLB=<stavebnice-demo.glb>'); process.exit(2); }
const TEXTS = JSON.parse(fs.readFileSync(path.join(WEB, 'pripni-cokoli/texty.json'), 'utf8')).cs.cues;
const VIEWS = [{ n: 'siroke 1000x750', w: 1000, h: 750 }, { n: 'mobil 390x410', w: 390, h: 410 }, { n: 'nizke siroke 1100x520', w: 1100, h: 520 }];
const out = [];
const ok = (n, c, d) => { out.push(!!c); console.log((c ? 'OK   ' : 'FAIL ') + n + (d !== undefined ? '  ' + JSON.stringify(d).slice(0, 360) : '')); };
(async () => {
  const b = await chromium.launch({ args: ['--host-resolver-rules=MAP * ~NOTFOUND', '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  const errs = [];
  for (const vw of VIEWS) {
    const ctx = await b.newContext({ viewport: { width: vw.w, height: vw.h }, deviceScaleFactor: 1 });
    await ctx.route('**/*', (route) => {
      const u = new URL(route.request().url());
      if (u.origin === 'https://cdn.jsdelivr.net') {
        const f = path.join(NM, u.pathname.replace('/npm/three@0.128.0/', ''));
        return fs.existsSync(f) ? route.fulfill({ contentType: 'application/javascript', body: fs.readFileSync(f) }) : route.fulfill({ status: 404, body: '' });
      }
      if (u.origin !== ORIGIN) return route.fulfill({ status: 404, body: '' });
      if (u.pathname === '/') return route.fulfill({ contentType: 'text/html; charset=utf-8', body: '<!doctype html><meta charset=utf-8><link rel=stylesheet href=/css/v3d.css><style>html,body{margin:0;height:100%}#v{width:100vw;height:100vh}</style><div id=v></div>' });
      if (u.pathname === '/m.glb') return route.fulfill({ contentType: 'model/gltf-binary', body: fs.readFileSync(GLB) });
      const m = /^\/(js\/v3d\/[A-Za-z0-9_.-]+\.js|js\/v3d\/env\/[A-Za-z0-9_.-]+|css\/v3d\.css)$/.exec(u.pathname);
      if (m && fs.existsSync(path.join(WEB, m[1]))) return route.fulfill({ contentType: /\.js$/.test(m[1]) ? 'application/javascript' : (/\.css$/.test(m[1]) ? 'text/css' : 'application/octet-stream'), body: fs.readFileSync(path.join(WEB, m[1])) });
      return route.fulfill({ status: 404, body: '' });
    });
    const page = await ctx.newPage();
    page.on('pageerror', (e) => errs.push(String(e)));
    await page.goto(ORIGIN + '/');
    for (const u of ['build/three.min.js', 'examples/js/controls/OrbitControls.js', 'examples/js/loaders/GLTFLoader.js', 'examples/js/environments/RoomEnvironment.js', 'examples/js/renderers/CSS2DRenderer.js', 'examples/js/shaders/HorizontalBlurShader.js', 'examples/js/shaders/VerticalBlurShader.js'])
      await page.addScriptTag({ url: 'https://cdn.jsdelivr.net/npm/three@0.128.0/' + u });
    await page.addScriptTag({ url: ORIGIN + '/js/v3d/viewer3d.js' });
    await page.addScriptTag({ url: ORIGIN + '/js/v3d/demo-stavebnice.js' });
    const res = await page.evaluate(async (texts) => {
      const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
      const until = async (fn, ms = 20000) => { const t0 = performance.now(); while (performance.now() - t0 < ms) { if (fn()) return true; await sleep(100); } return false; };
      const demo = window.V3D.demoPlugin({ texts, autoplay: false });
      const v = window.V3D.mount(document.getElementById('v'), { modelUrl: '/m.glb', mode: 'real', allowReal: true, hudKoty: false, dims: 0, plugins: [demo.plugin] });
      await v.ready;
      const cv = document.querySelector('.v3d-root canvas'), cr = cv.getBoundingClientRect();
      const rows = [];
      for (const c of demo.cues()) {
        demo.seek((c.t0 + c.t1) / 2);
        const shown = await until(() => { const t = document.querySelector('.v3d-demo-tag'); return t && t.classList.contains('is-on') && getComputedStyle(t).opacity > 0.95; });
        await sleep(150);
        const tag = document.querySelector('.v3d-demo-tag'), dot = document.querySelector('.v3d-demo-ov circle');
        const lay = demo.layout();
        const row = { cue: c.id, shown, mode: lay.mode, colW: lay.colW, bandH: lay.bandH, W: lay.W, H: lay.H };
        if (tag) { const r = tag.getBoundingClientRect(); row.tag = { x0: r.left - cr.left, y0: r.top - cr.top, x1: r.right - cr.left, y1: r.bottom - cr.top }; }
        if (dot) row.dot = { x: +dot.getAttribute('cx'), y: +dot.getAttribute('cy'), vis: dot.getAttribute('visibility') };
        const g = (c.g || []).filter((n, i, a) => n !== 0 || a.length === 1 ? true : false);
        row.parts = g.length && !(g.length === 1 && g[0] === 0) ? demo.screenRect(g) : null;
        rows.push(row);
      }
      v.dispose();
      return rows;
    }, TEXTS);
    ok(vw.n + ': aspon 7 cue (i bez kotvy) s popiskem zmereno', res.length >= 7, res.map((r) => r.cue));
    const exp = vw.w >= 640 && vw.w / vw.h >= 1.1 ? 'side' : 'top';
    ok(vw.n + ': rezim pruhu = ' + exp, res.every((r) => r.mode === exp), res.map((r) => r.mode));
    const inter = (a, b2, m) => a.x0 < b2.x1 + m && a.x1 > b2.x0 - m && a.y0 < b2.y1 + m && a.y1 > b2.y0 - m;
    for (const r of res) {
      ok(vw.n + ' / ' + r.cue + ': popisek je cely v okne', !!r.tag && r.tag.x0 >= 0 && r.tag.y0 >= 0 && r.tag.x1 <= r.W + 0.5 && r.tag.y1 <= r.H + 0.5, r.tag);
      if (r.parts) {
        ok(vw.n + ' / ' + r.cue + ': popisek NEZAKRYVA aktivni dily (rez 4 px)', !inter(r.tag, r.parts, 4), { tag: r.tag, parts: r.parts });
        const free = r.mode === 'side' ? { x0: r.colW, y0: 0, x1: r.W, y1: r.H } : { x0: 0, y0: r.bandH, x1: r.W, y1: r.H };
        const cx = (r.parts.x0 + r.parts.x1) / 2, cy = (r.parts.y0 + r.parts.y1) / 2;
        ok(vw.n + ' / ' + r.cue + ': aktivni dily jsou stredem ve volne plose vedle pruhu', cx >= free.x0 && cx <= free.x1 && cy >= free.y0 && cy <= free.y1, { cx, cy, free });
      }
      if (r.dot && r.dot.vis === 'visible') ok(vw.n + ' / ' + r.cue + ': bod spojnice neni pod popiskem', !(r.dot.x >= r.tag.x0 && r.dot.x <= r.tag.x1 && r.dot.y >= r.tag.y0 && r.dot.y <= r.tag.y1), { dot: r.dot, tag: r.tag });
    }
    await ctx.close();
  }
  ok('bez neodchycenych chyb stranky', errs.length === 0, errs.slice(0, 3));
  await b.close();
  process.exit(out.every(Boolean) ? 0 : 1);
})().catch((e) => { console.error('CHYBA', e); process.exit(2); });
