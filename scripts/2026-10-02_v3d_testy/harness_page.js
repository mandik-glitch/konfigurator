// Harness: navrh vlozeni 3D prohlizece do nabidka-online.html (docs/nabidka-online.snippet.html), bot10, 2026-10-02.
// NEAPLIKUJE nic do repa: bloky snippetu se v pameti vlozi do KOPIE zive stranky (webapp/nabidka-online.html) podle kotev
// a stranka se spusti v Playwright Chromiu:
//  - --host-resolver-rules='MAP * ~NOTFOUND' (nic nesmi ven, nikdy 127.0.0.1), VSE obsluhuje context.route -> fulfill:
//    three r128 z node_modules, viewer3d.js + v3d.css z repa, GLB = skutecny zakaznicky model z buildu (<OUT>/out2/4910.offer.glb)
//    nebo fixtures/native_offer.glb (dosavadni staticky model), API odpovedi podvrzene (zadna DB, zadna ziva nabidka).
//  - WebGL pres SwiftShader. sendBeacon prepsan na zaznam.
// Scenare: 1 model s v3d -> V3D (Skutecny, pohyby, koty, statistiky) | 2 staticky model -> dosavadni kod, V3D se ani nestahuje |
//          3 viewer3d.js nejde nacist -> obrazkova zaloha | 4 poskozeny GLB s v3d -> zaloha | 5 model 404 -> zaloha |
//          6 bez 3D | 7 sipky v cele obrazovce neprepnou slide | 8 sitovy audit (jen povolene hosty) + shoda ?v= hashe.
// Spusteni: node scripts/2026-10-02_v3d_testy/harness_page.js      (exit 1 = neco selhalo; ~3 min, SwiftShader; H_ONLY=7 jen vybrany scenar)
// Prostredi: V3D_TEST_OUT (kde je out2 z build_karty.py), V3D_NODE_MODULES, V3D_PAGE_HTML (jina stranka), V3D_SNIPPET.
'use strict';
const path = require('path');
const fs = require('fs');
const os = require('os');
const crypto = require('crypto');

const HERE = __dirname;
const REPO = path.resolve(HERE, '..', '..');
const LIVE = '/opt/konfigurator';
const OUT = process.env.V3D_TEST_OUT || path.join(os.tmpdir(), 'v3d_testy');
const NM = process.env.V3D_NODE_MODULES || path.join(LIVE, 'node_modules');
const { chromium } = require(path.join(NM, 'playwright'));
const THREE_DIR = path.join(NM, 'three') + path.sep;
const firstExisting = (...c) => c.filter(Boolean).find(p => fs.existsSync(p));
const F = {
  page: firstExisting(process.env.V3D_PAGE_HTML, path.join(REPO, 'webapp/nabidka-online.html'), path.join(LIVE, 'webapp/nabidka-online.html')),
  viewerJs: firstExisting(process.env.VIEWER_JS, path.join(REPO, 'webapp/js/v3d/viewer3d.js'), path.join(LIVE, 'webapp/js/v3d/viewer3d.js')),
  viewerCss: firstExisting(process.env.V3D_CSS, path.join(REPO, 'webapp/css/v3d.css'), path.join(LIVE, 'webapp/css/v3d.css')),
  snippet: firstExisting(process.env.V3D_SNIPPET, path.join(REPO, 'docs/nabidka-online.snippet.html')),
  clientErrors: firstExisting(path.join(REPO, 'webapp/js/client-errors.js'), path.join(LIVE, 'webapp/js/client-errors.js')),
  envHdr: firstExisting(path.join(REPO, 'webapp/js/v3d/env/crossfit_1024.hdr'), path.join(LIVE, 'webapp/js/v3d/env/crossfit_1024.hdr')),
  envHdr256: firstExisting(path.join(REPO, 'webapp/js/v3d/env/crossfit_256.hdr'), path.join(LIVE, 'webapp/js/v3d/env/crossfit_256.hdr')),     // maly nahled HDRI (viewer3d.js 1.10.0: velke HDRI az po prvnim modelu)
  legacyGlb: path.join(HERE, 'fixtures/native_offer.glb'),
  v3dGlb: path.join(OUT, 'out2/4910.offer.glb'),
};
const ORIGIN = 'https://autovestavby.logiman.cz';
const INTEGROVANA = /function modelMaV3d\(/.test(fs.readFileSync(F.page, 'utf-8'));
const TOKEN = 'HARNESSTOKEN';
const PNG1 = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==', 'base64');
const sha10 = f => crypto.createHash('sha256').update(fs.readFileSync(f)).digest('hex').slice(0, 10);
const motionsOfGlb = f => { const b = fs.readFileSync(f); const js = JSON.parse(b.slice(20, 20 + b.readUInt32LE(12)).toString('utf-8')); return js.scenes[0].extras.v3d.motions.length; };

const results = [];
const requests = [];
let current = '';
function check(name, ok, detail) {
  results.push({ scen: current, name, ok: !!ok, detail });
  console.log((ok ? '  OK   ' : '  FAIL ') + name + (detail !== undefined && !ok ? '  ' + (typeof detail === 'string' ? detail : JSON.stringify(detail)).slice(0, 700) : ''));
}
const sleep = ms => new Promise(r => setTimeout(r, ms));
async function waitFor(page, fn, arg, timeout = 20000) {
  const t0 = Date.now();
  while (Date.now() - t0 < timeout) {
    try { if (await page.evaluate(fn, arg)) return true; } catch (e) { /* navigace */ }
    await sleep(80);
  }
  return false;
}

// ------------------------------------------------------------------ snippet -> kopie stranky
function applySnippet(html, snippet) {
  const blocks = {};
  snippet.replace(/<!--BLOCK (\w+)-->\n?([\s\S]*?)<!--\/BLOCK-->/g, (_m, name, body) => { blocks[name] = body.replace(/\n+$/, '\n'); return ''; });
  for (const k of ['css', 'funkce', 'hacek', 'klavesy']) if (!blocks[k]) throw new Error('snippet nema blok ' + k);
  const once = (anchor) => {
    const n = html.split(anchor).length - 1;
    if (n !== 1) throw new Error('kotva se ve strance vyskytuje ' + n + 'x (ma 1x): ' + JSON.stringify(anchor));
    return anchor;
  };
  const A = {
    css: '  #viewer3dHint { text-align: center; font-size: 12px; color: var(--muted); margin-top: 10px; }\n',
    funkce: '  let viewer3dAttempted = false;\n',
    hacek: '    viewer3dAttempted = true;\n',
    klavesy: '  document.addEventListener("keydown", e => {\n',
  };
  html = html.replace(once(A.css), () => A.css + blocks.css);
  html = html.replace(once(A.funkce), () => blocks.funkce + A.funkce);
  html = html.replace(once(A.hacek), () => A.hacek + blocks.hacek);
  html = html.replace(once(A.klavesy), () => A.klavesy + blocks.klavesy);
  return html;
}

// ------------------------------------------------------------------ mock server
function offerJson(o) {
  const items = o.items || [{ name: 'Hliníková regálová vestavba (VD-harness)', qty: 1, unit_price: 100000, total: 100000 }];
  return JSON.stringify({
    offer_number: 'HARNESS-1', total_price: 100000, editable_text: { popis: 'Harness popis.', patka: 'Patka.' },
    customer_name: 'Harness s.r.o.', created_at: '2026-10-01T10:00:00', expires_at: '2026-10-31T00:00:00',
    pages: ['cover', 'drawings_1', 'drawings_2', 'view_3d', 'pricing', 'closing'],
    image_urls: {}, renders: [], has_3d_model: o.has3d !== false, model_url: o.has3d === false ? null : `/api/public/offers/${TOKEN}/model`,
    has_ghost_views: false, accepted: null, declined: null, revision_number: 1, last_edited_at: null,
    supplier: { name: 'Logiman', street: 'Ulice 1', city: 'Město', ico: '123', dic: 'CZ123', email: 'x@example.invalid', phone: '+420 000' },
    pdf_url: null, payment_qr_url: `/api/public/offers/${TOKEN}/payment-qr`, order_prefs: null, markups: [], viewer_role: 'client',
    hdri: null, montaz_pct: 0, items, offer_options: o.offer_options || { vandr_single_drawing: true },
  });
}

async function setupContext(browser, opts) {
  const ctx = await browser.newContext({ viewport: opts.viewport || { width: 1366, height: 900 } });
  await ctx.addInitScript(() => {
    window.__beacons = [];
    navigator.sendBeacon = function (url, data) {
      const rec = { url: String(url), body: null };
      window.__beacons.push(rec);
      try { if (data && data.text) data.text().then(t => { try { rec.body = JSON.parse(t); } catch (e) { rec.body = t; } }); } catch (e) { /* */ }
      return true;
    };
  });
  const pageSrc = fs.readFileSync(F.page, 'utf-8');
  // od 2026-10-06 je integrace PRIMO ve strance (modelMaV3d v nabidka-online.html) -> test bezi nad stránkou samotnou; starsi stranka bez ni dostane snippet
  const pageHtml = INTEGROVANA ? pageSrc : applySnippet(pageSrc, fs.readFileSync(F.snippet, 'utf-8'));
  await ctx.route('**/*', async route => {
    const req = route.request();
    const u = new URL(req.url());
    const rec = { scen: current, method: req.method(), host: u.hostname, path: u.pathname, query: u.search, status: null };
    requests.push(rec);
    const ful = (status, contentType, body, headers) => { rec.status = status; return route.fulfill({ status, contentType, body, headers }); };
    if (u.hostname === 'cdn.jsdelivr.net' && u.pathname.startsWith('/npm/three@0.128.0/')) {
      const f = path.join(THREE_DIR, u.pathname.slice('/npm/three@0.128.0/'.length));
      if (f.startsWith(THREE_DIR) && fs.existsSync(f)) return ful(200, 'application/javascript', fs.readFileSync(f));
      return ful(404, 'text/plain', 'nf');
    }
    if (u.hostname !== 'autovestavby.logiman.cz') { rec.status = 'abort'; return route.abort(); }
    const p = u.pathname;
    if (req.method() !== 'GET') {
      if (p === `/api/public/offers/${TOKEN}/view`) return ful(200, 'application/json', '{"view_id":77}');
      return ful(200, 'application/json', '{}');
    }
    if (p === '/nabidka-online.html') return ful(200, 'text/html; charset=utf-8', pageHtml);
    if (p === '/js/v3d/viewer3d.js') {
      if (opts.viewerFails) return ful(500, 'text/plain', 'atrapa: viewer nejde nacist');
      return ful(200, 'application/javascript; charset=utf-8', fs.readFileSync(F.viewerJs));
    }
    if (p === '/css/v3d.css') return ful(200, 'text/css; charset=utf-8', fs.readFileSync(F.viewerCss));
    if (/^\/js\/v3d\/env\/[a-z_0-9]+\.hdr$/.test(p) && p !== '/js/v3d/env/crossfit_1024.hdr' && p !== '/js/v3d/env/crossfit_256.hdr') {       // dalsi HDRI z knihovny (vzhled nabidek, scenar 9)
      const hf = path.join(path.dirname(F.envHdr), path.basename(p));
      return fs.existsSync(hf) ? ful(200, 'application/octet-stream', fs.readFileSync(hf)) : ful(404, 'text/plain', 'nf');
    }
    if (p === '/api/public/v3d-vzhled') {          // vzhled online nabidek (HDRI, hlinik, AO) ulozeny adminem v kontrolni scene (bot10 2026-10-06); opts.vzhled: null = API tu neni (404 HTML), nezadano = nic neulozeno
      const v = opts.vzhled === undefined ? { status: 200, body: { env: null, alu: null, ao: null } } : opts.vzhled;       // vychozi = API nasazene, nic neulozeno; vzhled: null = API tu jeste neni (404 HTML)
      if (!v) return ful(404, 'text/html', '<h1>404</h1>');
      if (v.delay) await sleep(v.delay);
      try {
        if (v.raw !== undefined) return ful(v.status, 'application/json', v.raw);
        return ful(v.status, 'application/json', JSON.stringify(v.body));
      } catch (e) { return; }                     // pozadavek mezitim zrusen (casovy limit stranky)
    }
    if (/^\/api\/public\/v3d-env\/[a-z0-9_]+_(1024|256)\.hdr$/.test(p)) {          // HDRI doplnena ze Sdileneho disku (viewer 1.15.0, hdri_extra): v atrape stejne soubory jako knihovna
      const sz = /_(1024|256)\.hdr$/.exec(p)[1];
      return ful(200, 'application/octet-stream', fs.readFileSync(path.join(path.dirname(F.envHdr), 'tv_studio_' + sz + '.hdr')));
    }
    if (p === '/js/v3d/env/crossfit_1024.hdr') return ful(200, 'application/octet-stream', fs.readFileSync(F.envHdr));   // prostredi prohlizece (staticky soubor z repa)
    if (p === '/js/v3d/env/crossfit_256.hdr') return ful(200, 'application/octet-stream', fs.readFileSync(F.envHdr256));   // nahled prostredi (1.10.0: nejdriv 256, velke 1024 az po modelu)
    if (p === '/js/client-errors.js') return ful(200, 'application/javascript; charset=utf-8', F.clientErrors ? fs.readFileSync(F.clientErrors) : '');
    if (p === `/api/public/offers/${TOKEN}`) return ful(200, 'application/json', offerJson(opts.offer || {}));
    if (p === '/track.js') return ful(200, 'application/javascript', '/* harness */');
    if (p === '/api/theme-colors') return ful(200, 'application/json', '{}');
    if (p === '/api/montaz-mista') return ful(200, 'application/json', '{"mista":[]}');
    if (p === `/api/public/offers/${TOKEN}/payment-qr`) return ful(200, 'image/png', PNG1);
    if (p === `/api/public/offers/${TOKEN}/model`) {
      if (!opts.glb || !fs.existsSync(opts.glb)) return ful(404, 'application/json', '{"error":"nenalezeno"}');
      const data = typeof opts.glbBytes === 'function' ? opts.glbBytes(fs.readFileSync(opts.glb)) : fs.readFileSync(opts.glb);
      return ful(200, 'model/gltf-binary', data, { 'Cache-Control': 'private, no-cache', ETag: '"harness"', 'X-Content-Type-Options': 'nosniff' });
    }
    if (p.startsWith(`/api/public/offers/${TOKEN}/image/`)) return ful(200, 'image/png', PNG1);
    rec.unknown = true;
    return ful(404, 'application/json', '{}');
  });
  return ctx;
}
async function openPage(ctx) {
  const page = await ctx.newPage();
  const errors = [];
  page.on('pageerror', e => errors.push('pageerror: ' + String(e).slice(0, 300)));
  page.on('console', msg => { if (msg.type() === 'error') errors.push('console.error: ' + msg.text().slice(0, 300)); });
  await page.goto(`${ORIGIN}/nabidka-online.html?t=${TOKEN}`, { waitUntil: 'domcontentloaded' });
  return { page, errors };
}
const slideState = () => {
  const slides = [...document.querySelectorAll('#deck .slide')];
  const act = slides.findIndex(s => s.classList.contains('active'));
  const c = document.getElementById('viewer3dContainer');
  return { act, n: slides.length, on3d: !!(c && c.closest('.slide.active')), fs: !!(window.V3D && window.V3D.isFullscreen && window.V3D.isFullscreen()) };
};
async function goto3d(page) {
  await page.waitForSelector('#deck .slide', { state: 'attached', timeout: 20000 });
  for (let i = 0; i < 10; i++) {
    const s = await page.evaluate(slideState);
    if (s.on3d) break;
    await page.keyboard.press('ArrowRight');
    await sleep(250);
  }
  return page.evaluate(slideState);
}
const beacons = page => page.evaluate(() => window.__beacons.map(b => b.body && (b.body.target || b.body.event_type)).filter(Boolean));
const mine = () => requests.filter(r => r.scen === current);

// ------------------------------------------------------------------ scenare
async function s1_v3d(browser) {
  current = '1 model s v3d -> sdileny prohlizec';
  console.log('\n== ' + current);
  const ctx = await setupContext(browser, { glb: F.v3dGlb });
  const { page, errors } = await openPage(ctx);
  const s0 = await goto3d(page);
  check('stranka 3D pohledy aktivni', s0.on3d, s0);
  const ready = await waitFor(page, () => !!(window.__v3d && window.__v3d.state().ready));
  check('V3D namountovany a model hotovy', ready, await page.evaluate(() => window.__v3d && window.__v3d.state().error));
  const st = await page.evaluate(() => {
    const s = window.__v3d.state();
    const fb = document.getElementById('viewer3dFallback');
    const hint = document.getElementById('viewer3dHint');
    const seg = document.querySelector('.v3d-seg[aria-label="Vzhled"]');
    return { legacy: s.legacy, mode: s.mode, allowReal: s.allowReal, dims: s.dims, motions: s.motions.length, warnings: s.warnings,
      roots: document.querySelectorAll('#viewer3dContainer .v3d-root').length, canvases: document.querySelectorAll('#viewer3dContainer canvas').length,
      chips: document.querySelectorAll('.v3d-chips .v3d-chip').length, fbHidden: getComputedStyle(fb).display === 'none',
      hintHidden: !hint || getComputedStyle(hint).display === 'none', container: getComputedStyle(document.getElementById('viewer3dContainer')).display,
      modeSegVisible: !!seg && !seg.hidden && seg.offsetParent !== null, bomShow: document.getElementById('bomList').classList.contains('show') };
  });
  check('spec v3d -> Skutecny vzhled, prepinac Vzhled videt, koty uroven 1', !st.legacy && st.mode === 'real' && st.allowReal && st.modeSegVisible && st.dims === 1, st);
  const ocekPohybu = motionsOfGlb(F.v3dGlb);
  check('pohyby: ' + ocekPohybu + ' (podle spec v modelu) a cipy pohybu v HUD', ocekPohybu > 0 && st.motions === ocekPohybu && st.chips >= ocekPohybu, { motions: st.motions, chips: st.chips, ocekavano: ocekPohybu });
  check('jeden prohlizec, obrazkova zaloha i stara napoveda skryte, kontejner zobrazen', st.roots === 1 && st.fbHidden && st.hintHidden && st.container === 'block', st);
  check('popis v3d bez varovani prohlizece', st.warnings.length === 0, st.warnings);
  const modelReq = mine().filter(r => r.path.endsWith('/model'));
  check('model se stahl JEDNOU (V3D dostal arrayBuffer, zadne druhe stazeni)', modelReq.length === 1, modelReq.length);
  check('stahl se V3D (viewer3d.js, v3d.css) a jeho staticke prostredi /js/v3d/env/crossfit_1024.hdr; zadne HDRI z /katalog/hdri/ (dnes az 23,6 MB)',
        ['/js/v3d/viewer3d.js', '/css/v3d.css', '/js/v3d/env/crossfit_1024.hdr'].every(x => mine().some(r => r.path === x && r.status === 200))
        && !mine().some(r => /\/katalog\/hdri\//.test(r.path)), mine().map(r => r.path));
  const chip = await page.$('.v3d-chips .v3d-chip[data-motion]');
  const mid = await chip.getAttribute('data-motion');
  await chip.click();
  const anim = await waitFor(page, id => window.__v3d.state().t[id] === 1, mid, 8000);
  check('cip pohybu otevre dil (' + mid + ')', anim);
  await page.click('.v3d-seg[aria-label="Vzhled"] .v3d-b[data-v="wire"]');
  await sleep(300);
  check('prepnuti na Drateny', (await page.evaluate(() => window.__v3d.state().mode)) === 'wire');
  await page.click('.v3d-seg[aria-label="Vzhled"] .v3d-b[data-v="real"]');
  await sleep(300);
  await page.click('.v3d-seg--views .v3d-b[data-v="front"]');
  await sleep(700);
  const bc = await beacons(page);
  check('statistiky pres trackClick: v3d_anim, v3d_mode, v3d_view (vsechny v CLICK_TARGETS)', ['v3d_anim', 'v3d_mode', 'v3d_view'].every(k => bc.indexOf(k) >= 0), bc);
  const hud = await page.evaluate(() => {
    const out = [];
    document.querySelectorAll('.v3d-root .v3d-tl button, .v3d-root .v3d-tr button, .v3d-root .v3d-br button').forEach(b => {
      if (b.offsetParent === null) return;
      const r = b.getBoundingClientRect();
      const pts = [[r.left + r.width / 2, r.top + r.height / 2], [r.left + 5, r.top + 5], [r.right - 5, r.bottom - 5]];
      const bad = pts.filter(([x, y]) => { const e = document.elementFromPoint(x, y); return !(e && (e === b || b.contains(e))); });
      if (bad.length) out.push(b.textContent.trim() || b.getAttribute('aria-label'));
    });
    return out;
  });
  check('zadne tlacitko HUD nezakryva pevny prvek stranky (bubliny chatu) - 1366x900', hud.length === 0, hud);
  try { await page.screenshot({ path: path.join(OUT, 'harness_page_v3d.png'), timeout: 60000 }); } catch (e) { console.log('  INFO snimek obrazovky se nepodaril (SwiftShader): ' + String(e).slice(0, 80)); }
  check('bez chyb v konzoli', errors.length === 0, errors);
  await ctx.close();
}

async function s2_static(browser) {
  current = '2 staticky model (v3d:false) -> dosavadni zobrazeni';
  console.log('\n== ' + current);
  const ctx = await setupContext(browser, { glb: F.legacyGlb });
  const { page, errors } = await openPage(ctx);
  const s0 = await goto3d(page);
  check('stranka 3D pohledy aktivni', s0.on3d, s0);
  const ok = await waitFor(page, () => {
    const c = document.getElementById('viewer3dContainer');
    return !!(c && c.querySelector('canvas') && getComputedStyle(c).display === 'block');
  });
  const st = await page.evaluate(() => ({
    roots: document.querySelectorAll('.v3d-root').length, canvases: document.querySelectorAll('#viewer3dContainer canvas').length,
    v3dCanvas: document.querySelectorAll('.v3d-canvas').length, fbHidden: getComputedStyle(document.getElementById('viewer3dFallback')).display === 'none',
    hint: !!document.getElementById('viewer3dHint') && getComputedStyle(document.getElementById('viewer3dHint')).display !== 'none',
    three: !!window.THREE, v3d: !!window.V3D && typeof window.V3D.mount === 'function' }));
  check('dosavadni vestavěný prohlizec: platno v kontejneru, zadny V3D root', ok && st.canvases === 1 && st.roots === 0 && st.v3dCanvas === 0, st);
  check('obrazkova zaloha skryta, stara napoveda zustava (dosavadni chovani)', st.fbHidden && st.hint, st);
  check('V3D (viewer3d.js, v3d.css) se pro staticky model vubec nestahuje', st.v3d === false && !mine().some(r => r.path === '/js/v3d/viewer3d.js' || r.path === '/css/v3d.css'), mine().map(r => r.path));
  check('model se stahl dvakrat (kontrola formatu + dosavadni nacteni; druhe je v prohlizeci 304 pres ETag)', mine().filter(r => r.path.endsWith('/model')).length === 2);
  check('bez chyb v konzoli', errors.length === 0, errors);
  await ctx.close();
}

async function s3_viewer_fails(browser) {
  current = '3 viewer3d.js nejde nacist -> obrazkova zaloha';
  console.log('\n== ' + current);
  const ctx = await setupContext(browser, { glb: F.v3dGlb, viewerFails: true });
  const { page, errors } = await openPage(ctx);
  await goto3d(page);
  const ok = await waitFor(page, () => {
    const c = document.getElementById('viewer3dContainer');
    return c && c.style.display === 'none' && getComputedStyle(document.getElementById('viewer3dFallback')).display !== 'none';
  }, null, 20000);
  const st = await page.evaluate(() => ({ roots: document.querySelectorAll('.v3d-root').length, hint: getComputedStyle(document.getElementById('viewer3dHint')).display }));
  check('kontejner pryc, ploche obrazky zpet, zadny prohlizec', ok && st.roots === 0, st);
  check('bez pageerror (jen console.warn; 500 skriptu je v konzoli jako resource error)', errors.filter(e => e.startsWith('pageerror')).length === 0, errors);
  await ctx.close();
}

async function s4_broken_v3d_glb(browser) {
  current = '4 poskozeny GLB se spec v3d -> zaloha';
  console.log('\n== ' + current);
  // spec zustane (JSON chunk), BIN useknout -> GLTFLoader/V3D odmitne
  const trunc = b => { const dv = new DataView(b.buffer, b.byteOffset, b.byteLength); const len0 = dv.getUint32(12, true); return b.subarray(0, 20 + len0 + 16); };
  const ctx = await setupContext(browser, { glb: F.v3dGlb, glbBytes: trunc });
  const { page, errors } = await openPage(ctx);
  await goto3d(page);
  const ok = await waitFor(page, () => {
    const c = document.getElementById('viewer3dContainer');
    return c && c.style.display === 'none' && getComputedStyle(document.getElementById('viewer3dFallback')).display !== 'none';
  }, null, 25000);
  const st = await page.evaluate(() => ({ roots: document.querySelectorAll('.v3d-root').length }));
  check('kontejner pryc, ploche obrazky zpet, V3D uklizen (dispose)', ok && st.roots === 0, st);
  check('bez pageerror', errors.filter(e => e.startsWith('pageerror')).length === 0, errors);
  await ctx.close();
}

async function s5_model_404(browser) {
  current = '5 model 404 -> zaloha (dosavadni chovani)';
  console.log('\n== ' + current);
  const ctx = await setupContext(browser, { glb: '/neexistuje.glb' });
  const { page, errors } = await openPage(ctx);
  await goto3d(page);
  const ok = await waitFor(page, () => {
    const c = document.getElementById('viewer3dContainer');
    return c && c.style.display === 'none' && getComputedStyle(document.getElementById('viewer3dFallback')).display !== 'none';
  }, null, 15000);
  check('kontejner pryc, ploche obrazky zpet', ok);
  check('bez pageerror', errors.filter(e => e.startsWith('pageerror')).length === 0, errors);
  await ctx.close();
}

async function s6_no3d(browser) {
  current = '6 nabidka bez 3D modelu';
  console.log('\n== ' + current);
  const ctx = await setupContext(browser, { offer: { has3d: false } });
  const { page } = await openPage(ctx);
  await page.waitForSelector('#deck .slide', { state: 'attached', timeout: 20000 });
  for (let i = 0; i < 3; i++) { await page.keyboard.press('ArrowRight'); await sleep(250); }
  await sleep(500);
  const st = await page.evaluate(() => ({ cont: !!document.getElementById('viewer3dContainer'), three: !!window.THREE, v3d: !!window.V3D }));
  check('bez 3D: zadny kontejner, three.js ani V3D se nestahuje', !st.cont && !st.three && !st.v3d, st);
  await ctx.close();
}

async function s7_fullscreen_keys(browser) {
  current = '7 sipky v cele obrazovce neprepnou slide';
  console.log('\n== ' + current);
  const ctx = await setupContext(browser, { glb: F.v3dGlb });
  const { page } = await openPage(ctx);
  await goto3d(page);
  await waitFor(page, () => !!(window.__v3d && window.__v3d.state().ready));
  const a0 = (await page.evaluate(slideState)).act;
  await page.click('.v3d-b[data-act="fs"]');
  await sleep(500);
  const fs1 = await page.evaluate(() => window.V3D.isFullscreen());
  await page.keyboard.press('ArrowRight');
  await sleep(500);
  const a1 = (await page.evaluate(slideState)).act;
  check('prohlizec je na cele obrazovce (Fullscreen API nebo CSS zaloha)', fs1);
  check('ArrowRight na cele obrazovce slide neprepne', a1 === a0, { a0, a1 });
  await page.click('.v3d-b[data-act="fs"]');
  await sleep(500);
  await page.keyboard.press('ArrowRight');
  await sleep(700);
  const a2 = (await page.evaluate(slideState)).act;
  check('po opusteni cele obrazovky sipky slidy prepinaji dal', a2 === a0 + 1, { a0, a2 });
  await ctx.close();
}

async function s10_vice_vykresu(browser) {
  current = '10 spolecna nabidka: vykres ke kazde strane';
  console.log('\n== ' + current);
  const tri = [{ slot: 'narys', label: 'Levá strana' }, { slot: 'bokorys', label: 'Pravá strana' }, { slot: 'pudorys', label: 'Přepážka' }];
  const slide = () => { const a = document.querySelector('#deck .slide.active'); const g = a && a.querySelector('.views-grid'); return a ? { h2: (a.querySelector('h2') || {}).textContent, trida: g && g.className, karet: a.querySelectorAll('.view-card').length,
    titulky: [...a.querySelectorAll('.view-card .caption')].map(c => c.childNodes[0].textContent), obr: [...a.querySelectorAll('.view-card img')].map(i => i.getAttribute('src').split('/').pop()),
    pretece: a.scrollWidth > a.clientWidth + 2 || document.documentElement.scrollWidth > window.innerWidth + 2, injekce: a.querySelectorAll('.view-card img[onerror], .view-card script').length } : null; };
  for (const [nazev, kresby, ocekKaret, viewport] of [['2 vykresy (leva + prava)', tri.slice(0, 2), 2, undefined], ['3 vykresy (leva + prava + prepazka)', tri, 3, undefined], ['3 vykresy na mobilu 390 px', tri, 3, { width: 390, height: 844 }]]) {
    const ctx = await setupContext(browser, { glb: F.v3dGlb, viewport, offer: { offer_options: { vandr_single_drawing: true, vandr_drawings: kresby, vandr_cards: [1, 2, 3].slice(0, ocekKaret) } } });
    const { page, errors } = await openPage(ctx);
    await page.waitForSelector('#deck .slide', { state: 'attached', timeout: 20000 });
    await page.keyboard.press('ArrowRight'); await sleep(500);
    const st = await page.evaluate(slide);
    check(nazev + ': stranka "Technicke vykresy", ' + ocekKaret + ' karty vedle sebe (views-grid-multi), popisky stran a spravne obrazky',
          st && st.h2 === 'Technické výkresy' && /views-grid-multi/.test(st.trida) && st.karet === ocekKaret && JSON.stringify(st.titulky) === JSON.stringify(kresby.map(d => d.label)) && JSON.stringify(st.obr) === JSON.stringify(kresby.map(d => d.slot)), st);
    check(nazev + ': nic nepreteka do strany, bez chyb', st && !st.pretece && errors.filter(e => e.startsWith('pageerror')).length === 0, [st && st.pretece, errors]);
    if (!viewport) { try { await page.screenshot({ path: path.join(OUT, 'harness_page_vykresy_' + ocekKaret + '.png'), timeout: 60000 }); } catch (e) { /* SwiftShader */ } }
    await ctx.close();
  }
  {   // bez vandr_drawings = dosavadni jeden vykres
    const ctx = await setupContext(browser, { glb: F.v3dGlb, offer: { offer_options: { vandr_single_drawing: true } } });
    const { page } = await openPage(ctx);
    await page.waitForSelector('#deck .slide', { state: 'attached', timeout: 20000 });
    await page.keyboard.press('ArrowRight'); await sleep(500);
    const st = await page.evaluate(slide);
    check('bez vandr_drawings (jedna karta): dosavadni jeden vykres (views-grid-single, "Technicky vykres", obrazek narys)', st && st.h2 === 'Technický výkres' && /views-grid-single/.test(st.trida) && st.karet === 1 && st.obr[0] === 'narys', st);
    await ctx.close();
  }
  // bot5 2026-10-06 (vandr_bez_vykresu, sanitizer 1-3 vykresy): strana bez Vandr vykresu se z vandr_drawings vynecha, takze i JEDINA polozka je platna a ukaze se jako jedna karta s popiskem strany
  for (const [nazev, oo] of [['jedna polozka v vandr_drawings', { vandr_single_drawing: true, vandr_drawings: [tri[0]] }],
                             ['neplatne sloty se zahodi (zustane jedna platna)', { vandr_single_drawing: true, vandr_drawings: [tri[0], { slot: '../x', label: 'x' }, null, 5] }]]) {
    const ctx = await setupContext(browser, { glb: F.v3dGlb, offer: { offer_options: oo } });
    const { page } = await openPage(ctx);
    await page.waitForSelector('#deck .slide', { state: 'attached', timeout: 20000 });
    await page.keyboard.press('ArrowRight'); await sleep(500);
    const st = await page.evaluate(slide);
    check(nazev + ': jedna karta se strankou "Technicke vykresy" a popiskem strany (views-grid-multi, obrazek narys)', st && st.h2 === 'Technické výkresy' && /views-grid-multi/.test(st.trida) && st.karet === 1 && st.obr[0] === 'narys' && st.titulky[0] === 'Levá strana', st);
    await ctx.close();
  }
  {   // popisek strany se vklada jako TEXT (ne HTML)
    const ctx = await setupContext(browser, { glb: F.v3dGlb, offer: { offer_options: { vandr_single_drawing: true, vandr_drawings: [{ slot: 'narys', label: '<img src=x onerror=alert(1)>Levá' }, tri[1]] } } });
    const { page } = await openPage(ctx);
    await page.waitForSelector('#deck .slide', { state: 'attached', timeout: 20000 });
    await page.keyboard.press('ArrowRight'); await sleep(500);
    const st = await page.evaluate(slide);
    check('popisek strany se vklada jako text, zadny vlozeny prvek', st && st.injekce === 0 && st.titulky[0] === '<img src=x onerror=alert(1)>Levá', st);
    await ctx.close();
  }
}

async function s9_vzhled(browser) {
  current = '9 ulozeny vzhled nabidek (HDRI, hlinik, AO, sytost a barvy materialu) se pouzije';
  console.log('\n== ' + current);
  const look = { env: { hdri: 'tv_studio', strength: 1.2, rot_deg: 30, hemi: 0.2 }, alu: 'satin', ao: 'silne' };
  const stav = page => page.evaluate(() => { const s = window.__v3d.state(); return { alu: s.alu, ao: s.ao, env: s.env, cfg: s.envCfg }; });
  {
    const ctx = await setupContext(browser, { glb: F.v3dGlb, vzhled: { status: 200, body: look } });
    const { page, errors } = await openPage(ctx);
    await goto3d(page);
    const ready = await waitFor(page, () => !!(window.__v3d && window.__v3d.state().ready));
    const st = ready ? await stav(page) : null;
    check('a) viewer dostal ulozeny vzhled: hlinik Satenovy, AO Silne, HDRI TV studio 1,2 / 30 / 0,2', st && st.alu === 'satin' && st.ao === 'silne' && st.env === 'custom'
      && st.cfg && st.cfg.hdri === 'tv_studio' && st.cfg.strength === 1.2 && st.cfg.rot_deg === 30 && st.cfg.hemi === 0.2, st);
    for (let i = 0; i < 100 && !mine().some(r => /tv_studio_1024/.test(r.path) && r.status === 200); i++) await sleep(100);       // velke HDRI se taha az po zobrazeni modelu (viewer 1.10.0)
    check('a) vzhled se stahl JEDNOU z /api/public/v3d-vzhled', mine().filter(r => r.path === '/api/public/v3d-vzhled').length === 1, mine().map(r => r.path));
    check('a) HDRI TV studio (maly nahled i velke) se nacetlo', mine().some(r => /tv_studio_256/.test(r.path) && r.status === 200) && mine().some(r => /tv_studio_1024/.test(r.path) && r.status === 200), mine().map(r => r.path).filter(x => /hdr/.test(x)));
    check('a) model stale JEDNOU a bez chyb v konzoli', mine().filter(r => r.path.endsWith('/model')).length === 1 && errors.length === 0, errors);
    await ctx.close();
  }
  {   // d) sytost a barvy materialu (viewer 1.12.0, bot10 2026-10-07): stranka je z GET /api/public/v3d-vzhled preda jako matConfig; neplatne hodnoty viewer zahodi
    const mat = page => page.evaluate(() => window.__v3d.matInfo());
    const rgbOf = h => [1, 3, 5].map(i => parseInt(h.slice(i, i + 2), 16));
    const blizko = (x, y, tol) => rgbOf(x).every((v, i) => Math.abs(v - rgbOf(y)[i]) <= (tol || 2));
    const rozptyl = h => Math.max(...rgbOf(h)) - Math.min(...rgbOf(h));       // kolik ma barva barevnosti (0 = seda)
    const oteviri = async vzhled => {
      const ctx = await setupContext(browser, { glb: F.v3dGlb, vzhled });
      const { page, errors } = await openPage(ctx);
      await goto3d(page);
      const ready = await waitFor(page, () => !!(window.__v3d && window.__v3d.state().ready));
      return { ctx, page, errors, mi: ready ? await mat(page) : [] };
    };
    const zaklad = await oteviri({ status: 200, body: { env: null, alu: null, ao: null, sat: null, barvy: null } });
    const mi0 = zaklad.mi, orig = mi0.length ? (mi0.find(x => rozptyl(x.orig) > 30) || mi0[0]).orig : null;       // nahradi se BAREVNY material (zmena tak nejde splest s "uz bylo seda")
    check('d) bez ulozene sytosti a barev: nehlinikove materialy maji puvodni barvy (hook matInfo)', mi0.length >= 1 && mi0.every(x => blizko(x.orig, x.now, 1)), mi0.slice(0, 3));
    await zaklad.ctx.close();
    if (orig) {
      const nula = await oteviri({ status: 200, body: { env: null, alu: null, ao: null, sat: 0, barvy: null } });
      check('d) ulozena sytost 0 %: vsechny barvy materialu na strance jsou sede (r = g = b), pritom model ma barevne materialy', nula.mi.some(x => rozptyl(x.orig) > 30) && nula.mi.every(x => rgbOf(x.now).every(v => Math.abs(v - rgbOf(x.now)[0]) <= 2)), nula.mi.slice(0, 3));
      check('d) ulozena sytost: stranka bez chyb v konzoli', nula.errors.length === 0, nula.errors);
      await nula.ctx.close();
      const barva = await oteviri({ status: 200, body: { env: null, alu: null, ao: null, sat: null, barvy: { [orig]: '#00ff00' } } });
      const stejna = barva.mi.filter(x => x.orig === orig), jina = barva.mi.filter(x => x.orig !== orig);
      check('d) ulozena nahrada barvy ' + orig + ' -> #00ff00: materialy s touto puvodni barvou jsou zelene, ostatni beze zmeny', stejna.length >= 1 && stejna.every(x => blizko(x.now, '#00ff00', 2)) && jina.every(x => blizko(x.orig, x.now, 1)), barva.mi.slice(0, 4));
      check('d) ulozena nahrada barvy: stranka bez chyb v konzoli', barva.errors.length === 0, barva.errors);
      await barva.ctx.close();
      const spatna = await oteviri({ status: 200, body: { env: null, alu: null, ao: null, sat: 'moc', barvy: { cervena: '#fff', '#112233': 'zelena', [orig]: 12 } } });
      check('d) neplatna sytost a barvy (text, kratky hex, cislo): materialy zustanou puvodni a stranka nespadne', spatna.mi.length >= 1 && spatna.mi.every(x => blizko(x.orig, x.now, 1)) && spatna.errors.filter(e => e.startsWith('pageerror')).length === 0, { mi: spatna.mi.slice(0, 3), err: spatna.errors });
      await spatna.ctx.close();
    }
  }
  {   // e) odlesky, hlinik a AO z API (viewer 1.14.0, bot10 2026-10-07): stranka je preda jako matConfig.gloss / aluConfig / aoConfig
    const alu = page => page.evaluate(() => window.__v3d.aluInfo()), matI = page => page.evaluate(() => window.__v3d.matInfo()), aov = page => page.evaluate(() => window.__v3d.aoValues());
    const open = async vz => { const ctx = await setupContext(browser, { glb: F.v3dGlb, vzhled: vz }); const o = await openPage(ctx); await goto3d(o.page); await waitFor(o.page, () => !!(window.__v3d && window.__v3d.state().ready)); await sleep(500); return Object.assign({ ctx }, o); };
    const nove = { env: null, alu: null, ao: null, sat: null, barvy: null, lesk: null, alu_cfg: null, ao_cfg: null, hdri_extra: [] };
    const z0 = await open({ status: 200, body: nove });
    const m0 = await matI(z0.page), a0 = await alu(z0.page);
    const hexL = (m0.find(x => typeof x.rough0 === 'number' && x.rough0 > 0.05 && x.rough0 < 0.95) || {}).orig;
    await z0.ctx.close();
    const z1 = await open({ status: 200, body: Object.assign({}, nove, { ao: 'jemne', lesk: { [hexL]: 0 }, alu_cfg: { refl: 0.5, rough: 1.5 }, ao_cfg: { k: 2, r: 0.5 } }) });
    const m1 = await matI(z1.page), a1 = await alu(z1.page), ao1 = await aov(z1.page);
    check('e) ulozeny lesk 0 % (mat): materialy teto barvy maji drsnost 1, ostatni beze zmeny', !!hexL && m1.filter(x => x.orig === hexL).every(x => Math.abs(x.rough - 1) < 0.011) && m1.filter(x => x.orig !== hexL).every(x => x.rough0 === null || Math.abs(x.rough - x.rough0) < 0.002), m1.slice(0, 3));
    check('e) ulozene odlesky hliniku (odrazy 50 %, matnost 150 %): envMapIntensity pulka, drsnost x1,5', a1.length >= 1 && a1.every((x, i) => Math.abs(x.env - a0[i].env * 0.5) <= Math.max(0.01, a0[i].env * 0.04) && Math.abs(x.rough - Math.min(1, a0[i].rough * 1.5)) < 0.011), { a0: a0.slice(0, 2), a1: a1.slice(0, 2) });
    check('e) ulozene AO: Jemne (0,25 / 8) x sila 2 x dosah 0,5 = 0,5 / 4', ao1.variant === 'jemne' && Math.abs(ao1.k - 0.5) < 0.001 && Math.abs(ao1.r - 4) < 0.001, ao1);
    await z1.ctx.close();
    const z2 = await open({ status: 200, body: Object.assign({}, nove, { lesk: { [hexL]: 99, zle: 1 }, alu_cfg: { refl: 'x', rough: 99 }, ao_cfg: { k: 99, r: -5 } }) });
    const a2 = await alu(z2.page), ao2 = await aov(z2.page), m2 = await matI(z2.page);
    check('e) neplatne hodnoty (lesk 99, text, mimo meze): viewer je omezi (lesk 200 %, matnost 200 %, AO sila 200 % / dosah 25 %), stranka bez pageerror', m2.filter(x => x.orig === hexL).every(x => Math.abs(x.rough - Math.max(0.02, Math.pow(x.rough0, 2))) < 0.011) && a2.every((x, i) => Math.abs(x.rough - Math.min(1, a0[i].rough * 2)) < 0.011) && ao2.cfg && ao2.cfg.k === 2 && ao2.cfg.r === 0.25 && z2.errors.filter(e => e.startsWith('pageerror')).length === 0, { m2: m2.slice(0, 2), a2: a2.slice(0, 2), ao2, err: z2.errors });
    await z2.ctx.close();
  }
  {   // f) HDRI doplnena ze Sdileneho disku (viewer 1.15.0): stranka je pripoji do knihovny pred mountem a pouzije ulozene prostredi s jejim klicem
    const sky = { key: 'sky', label: 'Sky', mul0: 1.2, rot0_deg: 15, url: '/api/public/v3d-env/sky_1024.hdr', lo: '/api/public/v3d-env/sky_256.hdr' };
    const ctx = await setupContext(browser, { glb: F.v3dGlb, vzhled: { status: 200, body: { env: { hdri: 'sky', strength: 1, rot_deg: 0, hemi: 0.2 }, alu: null, ao: null, sat: null, barvy: null, lesk: null, alu_cfg: null, ao_cfg: null, hdri_extra: [sky] } } });
    const { page, errors } = await openPage(ctx);
    await goto3d(page);
    const ready = await waitFor(page, () => !!(window.__v3d && window.__v3d.state().ready));
    for (let i = 0; i < 100 && !mine().some(r => /sky_1024/.test(r.path) && r.status === 200); i++) await sleep(100);
    const st = ready ? await page.evaluate(() => { const s = window.__v3d.state(); return { env: s.env, hdri: s.envCfg && s.envCfg.hdri, hemi: s.envCfg && s.envCfg.hemi }; }) : null;
    check('f) ulozene prostredi s klicem doplneneho HDRI se pouzije (prostredi custom, hdri sky, svetlo shora 0,2)', st && st.env === 'custom' && st.hdri === 'sky' && st.hemi === 0.2, st);
    check('f) viewer stahl nahled i velke HDRI z /api/public/v3d-env/ (200) a model je videt bez chyb', mine().some(r => /sky_256/.test(r.path) && r.status === 200) && mine().some(r => /sky_1024/.test(r.path) && r.status === 200) && errors.length === 0, { req: mine().map(r => r.path).filter(x => /v3d-env/.test(x)), errors });
    await ctx.close();
    const ctx2 = await setupContext(browser, { glb: F.v3dGlb, vzhled: { status: 200, body: { env: { hdri: 'sky', strength: 1, rot_deg: 0, hemi: 0 }, alu: null, ao: null, hdri_extra: [{ key: 'sky', label: 'Sky', mul0: 1, url: 'https://evil.example/sky_1024.hdr' }, { key: 'Velke', url: '/api/public/v3d-env/velke_1024.hdr' }, 'text', null] } } });
    const o2 = await openPage(ctx2);
    await goto3d(o2.page);
    const rdy2 = await waitFor(o2.page, () => !!(window.__v3d && window.__v3d.state().ready));
    const st2 = rdy2 ? await o2.page.evaluate(() => { const s = window.__v3d.state(); return { cfg: s.envCfg, alu: s.alu }; }) : null;
    check('f) neplatne hdri_extra (cizi adresa, velka pismena, nesmysly): zahodi se, ulozene prostredi s neznamym klicem = vychozi vzhled, bez pageerror', st2 && !st2.cfg && o2.errors.filter(e => e.startsWith('pageerror')).length === 0 && !mine().some(r => /evil\.example/.test(r.host + r.path)), { st2, err: o2.errors });
    await ctx2.close();
  }
  {   // h) AO po komponentech (viewer 1.16.0, bot10 2026-10-07): stranka preda ao_mat jako matConfig.ao a alu_cfg.ao jako aluConfig.ao
    const matI = page => page.evaluate(() => window.__v3d.matInfo()), aluI = page => page.evaluate(() => window.__v3d.aluInfo()), aov = page => page.evaluate(() => window.__v3d.aoValues());
    const open = async vz => { const ctx = await setupContext(browser, { glb: F.v3dGlb, vzhled: vz }); const o = await openPage(ctx); await goto3d(o.page); await waitFor(o.page, () => !!(window.__v3d && window.__v3d.state().ready)); await sleep(700); return Object.assign({ ctx }, o); };
    const nove = { env: null, alu: null, ao: null, sat: null, barvy: null, lesk: null, ao_mat: null, alu_cfg: null, ao_cfg: null, hdri_extra: [] };
    const z0 = await open({ status: 200, body: nove });
    const m0 = await matI(z0.page);
    const hexA = (m0.find(x => typeof x.rough0 === 'number') || m0[0] || {}).orig;
    await z0.ctx.close();
    const z1 = await open({ status: 200, body: Object.assign({}, nove, { ao: 'silne', ao_mat: { [hexA]: 0.3 }, alu_cfg: { refl: 1, rough: 1, ao: 1.5 } }) });
    const m1 = await matI(z1.page), a1 = await aluI(z1.page), ao1 = await aov(z1.page);
    check('h) ulozene AO po komponentech: materialy barvy ' + hexA + ' maji vahu AO 0,3, ostatni 1, hlinik 1,5', !!hexA && m1.filter(x => x.orig === hexA).every(x => Math.abs(x.aoW - 0.3) < 0.011) && m1.filter(x => x.orig !== hexA).every(x => x.aoW === 1) && a1.length >= 1 && a1.every(x => Math.abs(x.aoW - 1.5) < 0.011), { m1: m1.slice(0, 3), a1: a1.slice(0, 2) });
    check('h) pri zapnutem AO (Silne z API) se kresli vahovy pruchod (wMeshes >= 1, wPasses >= 1) a stranka je bez chyb v konzoli', ao1.variant === 'silne' && ao1.wMeshes >= 1 && ao1.wPasses >= 1 && z1.errors.length === 0, { ao1, err: z1.errors });
    await z1.ctx.close();
    const z2 = await open({ status: 200, body: Object.assign({}, nove, { ao: 'jemne', ao_mat: { [hexA]: 99, zle: 1, '#112233': 'x' }, alu_cfg: { ao: -3 } }) });
    const m2 = await matI(z2.page), a2 = await aluI(z2.page);
    check('h) neplatne AO (99, text, spatny klic, alu -3): viewer je omezi (barva 2, hlinik 0), ostatni 1, stranka bez pageerror', m2.filter(x => x.orig === hexA).every(x => x.aoW === 2) && m2.filter(x => x.orig !== hexA).every(x => x.aoW === 1) && a2.every(x => x.aoW === 0) && z2.errors.filter(e => e.startsWith('pageerror')).length === 0, { m2: m2.slice(0, 3), a2: a2.slice(0, 2), err: z2.errors });
    await z2.ctx.close();
    const bez = Object.assign({}, nove); delete bez.ao_mat;
    const z3 = await open({ status: 200, body: Object.assign(bez, { ao: 'silne' }) });
    const m3 = await matI(z3.page), a3 = await aluI(z3.page), ao3 = await aov(z3.page);
    check('h) server bez ao_mat (pred nasazenim): vsechny vahy 1, zadny vahovy pruchod, AO Silne jede jako drive', m3.every(x => x.aoW === 1) && a3.every(x => x.aoW === 1) && ao3.variant === 'silne' && ao3.wMeshes === 0 && ao3.wPasses === 0 && z3.errors.length === 0, { ao3, err: z3.errors });
    await z3.ctx.close();
  }
  {   // g) vyzva ke kliknuti pri najeti mysi (viewer 1.13.0, hoverHint): stranka nabidky ji ma zapnutou
    const ctx = await setupContext(browser, { glb: F.v3dGlb });
    const { page, errors } = await openPage(ctx);
    await goto3d(page);
    const ready = await waitFor(page, () => !!(window.__v3d && window.__v3d.state().ready));
    await sleep(800);
    const id = ready ? await page.evaluate(() => { const m = window.__v3d.state().motions[0]; return m && m.id; }) : null;
    const pt = id ? await page.evaluate((id) => window.__v3d.pickPoint(id), id) : null;
    let h = null;
    if (pt) { await page.mouse.move(pt.x - 12, pt.y - 12, { steps: 2 }); await page.mouse.move(pt.x, pt.y, { steps: 3 }); await sleep(700); h = await page.evaluate(() => window.__v3d.hoverInfo()); }
    check('g) stranka nabidky ma zapnutou vyzvu ke kliknuti (hoverHint): najeti na pohyblivy dil ukaze "Kliknutím otevřete", podsviti dil a kurzor je ruka', !!h && h.on && /Kliknutím otevřete/.test(h.act) && h.overlays >= 1 && h.cursor === 'pointer' && errors.length === 0, { h, errors });
    await ctx.close();
  }
  for (const [nazev, v] of [['API neexistuje (404 HTML)', null], ['500', { status: 500, body: { error: 'x' } }], ['vadne JSON', { status: 200, raw: '{nejson' }],
                            ['pole misto objektu', { status: 200, body: [1, 2] }], ['neplatne hodnoty (alu/ao nezname)', { status: 200, body: { env: null, alu: 'zlaty', ao: 'extra' } }]]) {
    const ctx = await setupContext(browser, { glb: F.v3dGlb, vzhled: v });
    const { page, errors } = await openPage(ctx);
    await goto3d(page);
    const ready = await waitFor(page, () => !!(window.__v3d && window.__v3d.state().ready));
    const st = ready ? await stav(page) : null;
    check('b) ' + nazev + ': model se ukaze s VYCHOZIM vzhledem (hlinik Dnesni, AO Vyp, bez vlastniho prostredi)', st && st.alu === 'puvodni' && st.ao === 'vyp' && !st.cfg, st);
    check('b) ' + nazev + ': bez pageerror', errors.filter(e => e.startsWith('pageerror')).length === 0, errors);
    await ctx.close();
  }
  if (!process.env.H_NO_TIMING) {      // H_NO_TIMING=1: bez kontroly casu (pri velke zatezi stroje - mutacni skripty - by hlidani 12 s selhalo bez souvislosti s kodem)
    const ctx = await setupContext(browser, { glb: F.v3dGlb, vzhled: { status: 200, body: look, delay: 6000 } });
    const { page } = await openPage(ctx);
    const t0 = Date.now();
    await goto3d(page);
    const ready = await waitFor(page, () => !!(window.__v3d && window.__v3d.state().ready), null, 30000);
    const ms = Date.now() - t0, st = ready ? await stav(page) : null;
    check('c) pomale API (6 s): stranka nepocka dele nez cca 3 s limit (viewer hotovy do 12 s od otevreni, vychozi vzhled)', ready && ms < 12000 && st.alu === 'puvodni' && !st.cfg, { ms, st });
    await ctx.close();
  }
}

function s8_audit() {
  current = '8 audit (sit, hash)';
  console.log('\n== ' + current);
  const hosty = [...new Set(requests.map(r => r.host))];
  check('requesty jen na autovestavby.logiman.cz a cdn.jsdelivr.net (three r128 z node_modules), nic ven', hosty.every(h => ['autovestavby.logiman.cz', 'cdn.jsdelivr.net'].includes(h)), hosty);
  check('zadny request nebyl abortovan (kazda zavislost byla obslouzena atrapou)', !requests.some(r => r.status === 'abort'), requests.filter(r => r.status === 'abort').map(r => r.host + r.path).slice(0, 5));
  const sn = INTEGROVANA ? fs.readFileSync(F.page, 'utf-8') : fs.readFileSync(F.snippet, 'utf-8');
  const hJs = (/viewer3d\.js\?v=([0-9a-f]{10})/.exec(sn) || [])[1], hCss = (/v3d\.css\?v=([0-9a-f]{10})/.exec(sn) || [])[1];
  check('?v= hash viewer3d.js ve strance/snippetu odpovida souboru (' + hJs + ')', hJs === sha10(F.viewerJs), { snippet: hJs, soubor: sha10(F.viewerJs) });
  check('?v= hash v3d.css ve strance/snippetu odpovida souboru (' + hCss + ')', hCss === sha10(F.viewerCss), { snippet: hCss, soubor: sha10(F.viewerCss) });
  const neznama = requests.filter(r => r.unknown && !/favicon/.test(r.path)).map(r => r.path);
  console.log('  INFO nezname cesty (404 atrapou, jen pro prehled): ' + JSON.stringify([...new Set(neznama)]).slice(0, 300));
}

(async () => {
  for (const [k, v] of Object.entries({ page: F.page, viewerJs: F.viewerJs, viewerCss: F.viewerCss, snippet: INTEGROVANA ? true : F.snippet })) {
    if (!v) { console.error('chybi vstup: ' + k); process.exit(2); }
  }
  console.log('stranka: ' + F.page + (INTEGROVANA ? '  (integrace PRIMO ve strance)' : '  (starsi stranka: aplikuji snippet)'));
  if (!fs.existsSync(F.v3dGlb)) { console.error('chybi ' + F.v3dGlb + ' (spustte build_karty.py)'); process.exit(2); }
  const browser = await chromium.launch({ args: ['--host-resolver-rules=MAP * ~NOTFOUND', '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
  try {
    const only = (process.env.H_ONLY || '123456789A').split('');      // podmnozina scenaru, napr. H_ONLY=7
    if (only.includes('1')) await s1_v3d(browser);
    if (only.includes('2')) await s2_static(browser);
    if (only.includes('3')) await s3_viewer_fails(browser);
    if (only.includes('4')) await s4_broken_v3d_glb(browser);
    if (only.includes('5')) await s5_model_404(browser);
    if (only.includes('6')) await s6_no3d(browser);
    if (only.includes('7')) await s7_fullscreen_keys(browser);
    if (only.includes('9')) await s9_vzhled(browser);
    if (only.includes('A')) await s10_vice_vykresu(browser);
    if (only.includes('8')) s8_audit();
  } catch (e) {
    check('harness dobehl bez vyjimky', false, String(e && e.stack || e).slice(0, 900));
  }
  await browser.close();
  const bad = results.filter(r => !r.ok);
  console.log('\nHARNESS STRANKY: ' + results.length + ' kontrol, ' + bad.length + ' selhalo');
  bad.forEach(r => console.log('  FAIL [' + r.scen + '] ' + r.name));
  process.exit(bad.length ? 1 : 0);
})();
