#!/usr/bin/env node
'use strict';
// Snimek 3D modelu (GLB) z prohlizece viewer3d.js - HEADLESS na serveru, bez site (bot10, 2026-10-03).
// Ucel: skutecny obrazek produktu (napr. vychozi konfigurace stolu) misto ikony na prehledu mini-shopu / v nabidce.
// Pouziva stejny prohlizec jako zakaznik (webapp/js/v3d/viewer3d.js, `v.snapshot()`), tedy stejne HDRI (tlumene), kovy, AO a stin.
//
//   node scripts/2026-10-03_snimek_modelu.js --glb model.glb --out obr.jpg [--w 1200] [--h 900] [--pohled iso]
//        [--pozadi '#0f1722'] [--ao stredni] [--hlinik puvodni] [--okraj 0.06] [--kvalita 0.92] [--ssaa 2]
//
//   --glb      vstupni GLB (napr. z /api/shop/configurator/glb/<token> nebo z api/stul_shop.glb_bytes)
//   --out      vystup; priponou .jpg/.jpeg = JPEG, .png = PNG (PNG s --pozadi none zustane pruhledny)
//   --w --h    rozmer vysledku v px (vychozi 1200x900); renderuje se ssaa-krat vetsi a zmensi (hladke hrany)
//   --pohled   iso (vychozi, 3/4 shora) | front | side | top
//   --pozadi   barva pozadi '#rrggbb' (vychozi tmava #0f1722) nebo 'none' (jen PNG)
//   --ao       vyp | jemne | stredni (vychozi) | silne
//   --hlinik   puvodni (vychozi) | satin | matny | eloxovany | bez   (varianta vzhledu hliniku, viz viewer)
//   --okraj    automaticky orez na obsah: vysledek vyplni vyst. obrazek s okrajem (podil rozmeru, vychozi 0.06, 0 = bez orezu,
//              ramovani podle prohlizece); stejne vyplneni u ruznych produktu = jednotne dlazdice
//   --ssaa     nasobek rozliseni pri renderu (1-3, vychozi 2)
// Bez kot, bez HUD a bez textu: snimek cte jen platno WebGL; kota se nestavi (dims:0). Ochranne logo ve snimku je jen tehdy, kdyz je v GLB.
// Chyby jsou HLASITE (kod != 0): chybejici HDRI/AO se nepreskakuje (obrazek by vypadal jinak nez na webu).
// Vsechno bezi offline (MAP * ~NOTFOUND): three r128 z node_modules, viewer a HDRI z webapp/js/v3d (zivy repo).
const path = require('path');
const fs = require('fs');
let chromium;
try { ({ chromium } = require('/opt/konfigurator/node_modules/playwright')); } catch (e) { ({ chromium } = require('playwright')); }

const REPO = path.resolve(__dirname, '..');
const WEBAPP = path.join(REPO, 'webapp');
const NM = path.join(REPO, 'node_modules', 'three');
const ORIGIN = 'https://snap.local';
const DEPS = ['build/three.min.js', 'examples/js/controls/OrbitControls.js', 'examples/js/loaders/GLTFLoader.js', 'examples/js/environments/RoomEnvironment.js',
  'examples/js/renderers/CSS2DRenderer.js', 'examples/js/shaders/HorizontalBlurShader.js', 'examples/js/shaders/VerticalBlurShader.js'];

function args() {
  const o = { w: 1200, h: 900, pohled: 'iso', pozadi: '#0f1722', ao: 'stredni', hlinik: 'puvodni', kvalita: 0.92, ssaa: 2, okraj: 0.06 };
  const a = process.argv.slice(2);
  for (let i = 0; i < a.length; i++) {
    const k = a[i].replace(/^--/, '');
    if (!/^--/.test(a[i]) || i + 1 >= a.length) die('neplatny argument: ' + a[i], 2);
    const v = a[++i];
    if (k === 'glb' || k === 'out') o[k] = v;
    else if (k === 'w' || k === 'h' || k === 'ssaa') o[k] = parseInt(v, 10);
    else if (k === 'kvalita' || k === 'okraj') o[k] = parseFloat(v);
    else if (['pohled', 'pozadi', 'ao', 'hlinik'].includes(k)) o[k] = v;
    else die('neznamy argument --' + k, 2);
  }
  if (!o.glb || !o.out) die('chybi --glb nebo --out (viz hlavicka souboru)', 2);
  if (!fs.existsSync(o.glb)) die('GLB neexistuje: ' + o.glb, 2);
  if (!(o.w >= 100 && o.w <= 4000 && o.h >= 100 && o.h <= 4000)) die('--w/--h mimo 100-4000', 2);
  if (!(o.ssaa >= 1 && o.ssaa <= 3)) die('--ssaa mimo 1-3', 2);
  if (!(o.okraj >= 0 && o.okraj <= 0.3)) die('--okraj mimo 0-0.3', 2);
  if (!['iso', 'front', 'side', 'top'].includes(o.pohled)) die('--pohled: iso|front|side|top', 2);
  if (!['vyp', 'jemne', 'stredni', 'silne'].includes(o.ao)) die('--ao: vyp|jemne|stredni|silne', 2);
  if (!['puvodni', 'satin', 'matny', 'eloxovany', 'bez'].includes(o.hlinik)) die('--hlinik: puvodni|satin|matny|eloxovany|bez', 2);
  if (!(o.pozadi === 'none' || /^#[0-9a-fA-F]{6}$/.test(o.pozadi))) die("--pozadi: '#rrggbb' nebo 'none'", 2);
  o.typ = /\.png$/i.test(o.out) ? 'image/png' : (/\.jpe?g$/i.test(o.out) ? 'image/jpeg' : null);
  if (!o.typ) die('--out musi koncit .jpg/.jpeg/.png', 2);
  if (o.typ === 'image/jpeg' && o.pozadi === 'none') die('JPEG nemuze byt pruhledny (pouzij .png nebo barvu)', 2);
  return o;
}
function die(msg, code) { console.error('CHYBA: ' + msg); process.exit(code || 1); }
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

(async () => {
  const o = args();
  const t0 = Date.now();
  const glb = fs.readFileSync(o.glb);
  const browser = await chromium.launch({ args: ['--host-resolver-rules=MAP * ~NOTFOUND', '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  try {
    const ctx = await browser.newContext({ viewport: { width: o.w, height: o.h }, deviceScaleFactor: o.ssaa });
    const ven = [];
    await ctx.route('**/*', (route) => {
      const u = new URL(route.request().url());
      if (u.origin === 'https://cdn.jsdelivr.net') {
        const f = path.join(NM, u.pathname.replace('/npm/three@0.128.0/', ''));
        return fs.existsSync(f) && f.startsWith(NM) ? route.fulfill({ contentType: 'application/javascript', body: fs.readFileSync(f) }) : route.fulfill({ status: 404, body: '' });
      }
      if (u.origin !== ORIGIN) { ven.push(u.href); return route.fulfill({ status: 404, body: '' }); }
      if (u.pathname === '/') return route.fulfill({ contentType: 'text/html; charset=utf-8', body: '<!doctype html><meta charset=utf-8><link rel=stylesheet href=/css/v3d.css><style>html,body{margin:0;height:100%;overflow:hidden}#v{width:100vw;height:100vh}</style><div id=v></div>' });
      if (u.pathname === '/m.glb') return route.fulfill({ contentType: 'model/gltf-binary', body: glb });
      const m = /^\/(js\/v3d\/viewer3d\.js|css\/v3d\.css|js\/v3d\/env\/[A-Za-z0-9_.-]+)$/.exec(u.pathname);
      if (m) {
        const f = path.join(WEBAPP, m[1]);
        if (fs.existsSync(f)) return route.fulfill({ contentType: /\.js$/.test(f) ? 'application/javascript' : (/\.css$/.test(f) ? 'text/css' : 'application/octet-stream'), body: fs.readFileSync(f) });
      }
      return route.fulfill({ status: 404, body: '' });
    });
    const page = await ctx.newPage();
    const chyby = [];
    page.on('pageerror', (e) => chyby.push(String(e)));
    await page.goto(ORIGIN + '/');
    for (const u of DEPS) await page.addScriptTag({ url: 'https://cdn.jsdelivr.net/npm/three@0.128.0/' + u });
    await page.addScriptTag({ url: ORIGIN + '/js/v3d/viewer3d.js' });
    const stav = await page.evaluate(async (c) => {
      const a = window.V3D.mount(document.getElementById('v'), { modelUrl: '/m.glb', mode: 'real', allowReal: true, dims: 0, hudKoty: false, aoVariant: c.ao, aluVariant: c.hlinik });
      window.__a = a;
      await a.ready;
      a.setView(c.pohled);
      for (let i = 0; i < 200 && !a.state().envHdriLoaded; i++) await new Promise((r) => setTimeout(r, 100));
      await new Promise((r) => setTimeout(r, 1200));
      const s = a.state();
      return { env: s.env, hdri: s.envHdriLoaded, ao: s.ao, aoActive: s.aoActive, aoSupported: s.aoSupported, legacy: s.legacy, warnings: s.warnings, version: window.V3D.version };
    }, o);
    if (!stav.hdri) die('HDRI prostredi se nenacetlo (' + JSON.stringify(stav.warnings) + ') - obrazek by vypadal jinak nez na webu', 3);
    if (o.ao !== 'vyp' && !stav.aoActive) die('AO neni aktivni (aoSupported=' + stav.aoSupported + ') - nastav --ao vyp nebo oprav prostredi', 4);
    if (stav.legacy) die('GLB nema v3d popis (legacy model); snimek by nemel pohyby/stin jako web', 5);
    const dataUrl = await page.evaluate(async (c) => {
      const bg = c.pozadi === 'none' ? null : c.pozadi;
      if (!(c.okraj > 0)) return window.__a.snapshot({ width: c.w, type: c.typ, quality: c.kvalita, background: bg || undefined });
      // orez na obsah: pruhledny snimek platna (pixely platna, nezmenseny) -> obdelnik, kde je model (alfa > 40; slaby okraj stinu se ignoruje)
      // -> vycentrovat do vystupu w x h s okrajem, vyplnit pozadim
      const src = await window.__a.snapshot({ type: 'image/png' });
      const img = new Image(); img.src = src; await img.decode();
      const t = document.createElement('canvas'); t.width = img.naturalWidth; t.height = img.naturalHeight;
      const tg = t.getContext('2d'); tg.drawImage(img, 0, 0);
      const d = tg.getImageData(0, 0, t.width, t.height).data;
      let x0 = t.width, y0 = t.height, x1 = -1, y1 = -1;
      for (let y = 0; y < t.height; y++) for (let x = 0; x < t.width; x++) if (d[(y * t.width + x) * 4 + 3] > 40) { if (x < x0) x0 = x; if (x > x1) x1 = x; if (y < y0) y0 = y; if (y > y1) y1 = y; }
      if (x1 < 0) throw new Error('snimek je prazdny (model neni videt)');
      const bw = x1 - x0 + 1, bh = y1 - y0 + 1;
      const k = Math.min(c.w * (1 - 2 * c.okraj) / bw, c.h * (1 - 2 * c.okraj) / bh);
      const dw = Math.round(bw * k), dh = Math.round(bh * k);
      const out = document.createElement('canvas'); out.width = c.w; out.height = c.h;
      const og = out.getContext('2d');
      og.imageSmoothingEnabled = true; og.imageSmoothingQuality = 'high';
      if (bg) { og.fillStyle = bg; og.fillRect(0, 0, c.w, c.h); }
      og.drawImage(t, x0, y0, bw, bh, Math.round((c.w - dw) / 2), Math.round((c.h - dh) / 2), dw, dh);
      return out.toDataURL(c.typ, c.kvalita);
    }, o);
    const m = /^data:(image\/(?:png|jpeg));base64,(.+)$/.exec(dataUrl);
    if (!m) die('snapshot() nevratil obrazek', 6);
    const buf = Buffer.from(m[2], 'base64');
    fs.mkdirSync(path.dirname(path.resolve(o.out)), { recursive: true });
    fs.writeFileSync(o.out, buf);
    if (chyby.length) console.error('POZOR: chyby stranky: ' + chyby.slice(0, 3).join(' | '));
    if (ven.length) die('pokus o spojeni mimo mock: ' + ven.slice(0, 3).join(', '), 7);
    console.log(JSON.stringify({ out: o.out, bytes: buf.length, typ: m[1], zadano: [o.w, o.h], pohled: o.pohled, pozadi: o.pozadi, okraj: o.okraj, ao: stav.ao, hlinik: o.hlinik, env: stav.env, viewer: stav.version, ms: Date.now() - t0 }));
  } finally {
    await browser.close();
  }
})().catch((e) => { console.error('CHYBA: ' + (e && e.message || e)); process.exit(1); });
