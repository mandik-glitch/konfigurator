// Online nabidka z KONFIGURACE sestavy (stul): stranka webapp/nabidka-online.html (bot5, 2026-10-02) - SKUTECNA stranka v Chromiu proti falesnemu serveru (page.route, zadna sit, zadna DB),
// skutecny 3D prohlizec V3D (webapp/js/v3d/viewer3d.js, bot10) a three r128 z node_modules (misto CDN), synteticky GLB (kvadr s v3d spec jako od bot8).
// Cast P  stranka: bez vykresu, 3D okno s V3D, souhrn voleb a seznam dilu bez cen, cislovani, cena, montaz a doprava, zaloha pri selhani modelu a WebGL, tisk, klavesnice, bezpecne vkladani, mobil;
//         starsi nabidky (bez zdroje) beze zmeny; mutace stranky (kazda musi test shodit).
// Spusteni: node test_nabidka_konfigurace_stranka.js            (konci kodem 0 jen kdyz VSE prosla)
// Kandidat pred nasazenim: NABIDKA_HTML=/cesta/k/nabidka-online.html node test_nabidka_konfigurace_stranka.js
const { chromium } = require('/opt/konfigurator/node_modules/playwright-core');
const fs = require('fs');
const os = require('os');
const path = require('path');

const REPO = path.join(__dirname, '../..');
const HTML_CESTA = process.env.NABIDKA_HTML || path.join(REPO, 'webapp/nabidka-online.html');
const HTML = fs.readFileSync(HTML_CESTA, 'utf8');
const UKAZKA = JSON.parse(fs.readFileSync(path.join(REPO, 'scripts/2026-10-01_nabidka_tabulka_cen_testy/ukazka_nabidky.json'), 'utf8'));
const THREE = '/opt/konfigurator/node_modules/three/';
const SNIMKY = process.env.SNIMKY_DIR || path.join(os.tmpdir(), 'nabidka_konfigurace_snimky');
fs.mkdirSync(SNIMKY, { recursive: true });
const PNG = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==', 'base64');

const vysl = [];
const over = (nazev, podminka, detail) => {
  vysl.push(!!podminka);
  console.log((podminka ? 'OK   ' : 'FAIL ') + nazev + (podminka ? '' : '  -> ' + JSON.stringify(detail)));
};
const norm = s => (s || '').replace(/[  ]/g, ' ').replace(/\s+/g, ' ').trim();

// synteticky GLB: kvadr 800 x 840 x 1200 mm (x hloubka, y vyska, z sirka), jeden uzel n0, v3d spec ve scene extras (jako od bot8)
function glbKvadr() {
  const hx = 400, hy = 420, hz = 600;
  const P = [], N = [], I = [];
  const steny = [[[1, 0, 0], [[hx, 0, -hz], [hx, 0, hz], [hx, 2 * hy, hz], [hx, 2 * hy, -hz]]], [[-1, 0, 0], [[-hx, 0, hz], [-hx, 0, -hz], [-hx, 2 * hy, -hz], [-hx, 2 * hy, hz]]],
                 [[0, 1, 0], [[-hx, 2 * hy, -hz], [hx, 2 * hy, -hz], [hx, 2 * hy, hz], [-hx, 2 * hy, hz]]], [[0, -1, 0], [[-hx, 0, hz], [hx, 0, hz], [hx, 0, -hz], [-hx, 0, -hz]]],
                 [[0, 0, 1], [[hx, 0, hz], [-hx, 0, hz], [-hx, 2 * hy, hz], [hx, 2 * hy, hz]]], [[0, 0, -1], [[-hx, 0, -hz], [hx, 0, -hz], [hx, 2 * hy, -hz], [-hx, 2 * hy, -hz]]]];
  steny.forEach(([n, v], i) => { v.forEach(p => { P.push(...p); N.push(...n); }); I.push(i * 4, i * 4 + 1, i * 4 + 2, i * 4, i * 4 + 2, i * 4 + 3); });
  const pos = Buffer.from(new Float32Array(P).buffer), nor = Buffer.from(new Float32Array(N).buffer), idx = Buffer.from(new Uint16Array(I).buffer);
  const blob = Buffer.concat([pos, nor, idx]);
  const spec = { v: 1, u: 'mm', up: [0, 1, 0], front: [-1, 0, 0], box: { min: [-hx, 0, -hz], max: [hx, 2 * hy, hz] }, look: 'nat', dims: [], motions: [] };
  const js = { asset: { version: '2.0' }, scene: 0, scenes: [{ nodes: [0], extras: { v3d: spec } }], nodes: [{ name: 'n0', mesh: 0 }],
               meshes: [{ primitives: [{ attributes: { POSITION: 0, NORMAL: 1 }, indices: 2, material: 0, mode: 4 }] }], materials: [{ pbrMetallicRoughness: { baseColorFactor: [0.6, 0.6, 0.65, 1], metallicFactor: 0.2, roughnessFactor: 0.6 } }],
               accessors: [{ bufferView: 0, componentType: 5126, count: 24, type: 'VEC3', min: [-hx, 0, -hz], max: [hx, 2 * hy, hz] }, { bufferView: 1, componentType: 5126, count: 24, type: 'VEC3' }, { bufferView: 2, componentType: 5123, count: 36, type: 'SCALAR' }],
               bufferViews: [{ buffer: 0, byteOffset: 0, byteLength: pos.length, target: 34962 }, { buffer: 0, byteOffset: pos.length, byteLength: nor.length, target: 34962 }, { buffer: 0, byteOffset: pos.length + nor.length, byteLength: idx.length, target: 34963 }],
               buffers: [{ byteLength: blob.length }] };
  let jb = Buffer.from(JSON.stringify(js));
  jb = Buffer.concat([jb, Buffer.alloc((4 - jb.length % 4) % 4, 0x20)]);
  const bb = Buffer.concat([blob, Buffer.alloc((4 - blob.length % 4) % 4)]);
  const head = Buffer.alloc(12); head.writeUInt32LE(0x46546C67, 0); head.writeUInt32LE(2, 4); head.writeUInt32LE(12 + 8 + jb.length + 8 + bb.length, 8);
  const c1 = Buffer.alloc(8); c1.writeUInt32LE(jb.length, 0); c1.writeUInt32LE(0x4E4F534A, 4);
  const c2 = Buffer.alloc(8); c2.writeUInt32LE(bb.length, 0); c2.writeUInt32LE(0x004E4942, 4);
  return Buffer.concat([head, c1, jb, c2, bb]);
}
const GLB = glbKvadr();

function nabidkaKonfigurace(o = {}) {
  const d = JSON.parse(JSON.stringify(UKAZKA));
  Object.assign(d, {
    offer_number: 'RM0123', source: 'configurator', has_3d_model: true, model_url: '/api/public/offers/TESTTOKEN/model', total_price: 26802, montaz_pct: 10, renders: [],
    items: [{ name: 'Pracovní stůl System 30 – 1200 × 800 × 840 mm (STL-27B047)', dim: '-', qty: '1 ks', unit_price: 26802, total: 26802, product_id: null, weight_kg_total: null }],
    configuration: { kod: 'STL-27B047', summary: [{ label: 'Šířka desky', value: '1200 mm' }, { label: 'Hloubka desky', value: '800 mm' }, { label: 'Výška pracovní desky', value: '840 mm' }, { label: 'LED osvětlení', value: 'ano' }],
                     bom: [{ nazev: 'Profil 30×30', mnozstvi: 4, rozmer: '1200 mm' }, { nazev: 'Pracovní deska', mnozstvi: 1, rozmer: '1200 × 800 mm' }, { nazev: 'Spojka', mnozstvi: 12, rozmer: null }] },
  });
  d.offer_options = Object.assign({}, d.offer_options || {}, { show_qr: true, hide_bom_prices: false, is_vehicle_assembly: false, montaz_pct: 10, hidden_delivery_state: null });
  return Object.assign(d, o);
}

async function otevri({ nabidka = nabidkaKonfigurace(), width = 1440, height = 900, mobil = false, html = HTML, model = 'ok', webgl = true, tisk = false } = {}) {
  const chyby = [], pozadavky = [];
  const browser = await chromium.launch({ args: ['--no-sandbox', ...(webgl ? ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] : ['--disable-gpu', '--disable-3d-apis', '--disable-webgl'])] });
  const ctx = await browser.newContext({ viewport: { width, height }, hasTouch: !!mobil, isMobile: !!mobil, deviceScaleFactor: 1 });
  const page = await ctx.newPage();
  page.on('pageerror', e => chyby.push('pageerror: ' + e.message));
  await page.route('**/*', async route => {
    const req = route.request();
    const u = new URL(req.url());
    const p = u.pathname, m = req.method();
    pozadavky.push(m + ' ' + p + (u.search || ''));
    const json = (status, body) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });
    if (u.hostname === 'cdn.jsdelivr.net') {
      const mm = /^\/npm\/three@0\.128\.0\/(.+)$/.exec(p);
      const f = mm && path.join(THREE, mm[1]);
      if (f && fs.existsSync(f)) return route.fulfill({ status: 200, contentType: 'application/javascript', body: fs.readFileSync(f) });
      return route.abort();
    }
    if (u.hostname !== 'nab.test') return route.abort();
    if (p === '/nabidka-online.html') return route.fulfill({ status: 200, contentType: 'text/html; charset=utf-8', body: html });
    if (p === '/js/v3d/viewer3d.js') return route.fulfill({ status: 200, contentType: 'application/javascript', body: fs.readFileSync(path.join(REPO, 'webapp/js/v3d/viewer3d.js')) });
    if (p === '/css/v3d.css') return route.fulfill({ status: 200, contentType: 'text/css', body: fs.readFileSync(path.join(REPO, 'webapp/css/v3d.css')) });
    if (p === '/api/public/offers/TESTTOKEN' && m === 'GET') return json(200, nabidka);
    if (p === '/api/public/offers/TESTTOKEN/model') return model === 'ok' ? route.fulfill({ status: 200, contentType: 'model/gltf-binary', body: GLB }) : route.fulfill({ status: 404, body: '' });
    if (/^\/api\/public\/offers\/TESTTOKEN\/(image|render)\//.test(p)) return route.fulfill({ status: 200, contentType: 'image/png', body: PNG });
    if (p === '/api/theme-colors') return json(200, { light: {}, dark: {} });
    if (p === '/api/montaz-mista') return json(200, { mista: [] });
    if (p.startsWith('/api/')) return json(200, m === 'GET' ? {} : { status: 'ok' });
    return route.fulfill({ status: 404, body: '' });
  });
  if (tisk) await page.emulateMedia({ media: 'print' });
  await page.goto('http://nab.test/nabidka-online.html?t=TESTTOKEN');
  await page.waitForSelector('#deck.show', { timeout: 15000 });
  await page.waitForTimeout(400);
  return { browser, page, chyby, pozadavky };
}
async function naStranku(page, klic) {
  for (let i = 0; i < 12; i++) {
    if (await page.evaluate(k => { const s = document.querySelector('.slide.active'); return s && s.dataset.key === k; }, klic)) return;
    await page.click('#btnNext');
    await page.waitForTimeout(450);
  }
  throw new Error('stranka ' + klic + ' nenalezena');
}
const klice = page => page.evaluate(() => [...document.querySelectorAll('.slide')].map(s => s.dataset.key));
const pockej = (page, fn, arg, ms = 12000) => page.waitForFunction(fn, arg, { timeout: ms });

// ---- kontroly stranky (znovu pouzity pro mutace): vraci objekt booleanu
async function kontrola(html) {
  const r = {};
  const t = await otevri({ html });
  r.klice = JSON.stringify(await klice(t.page)) === JSON.stringify(['cover', 'view_3d', 'pricing', 'closing']);
  await naStranku(t.page, 'view_3d');
  const panel = await t.page.evaluate(() => {
    const p = document.getElementById('bomList');
    return p ? { text: norm(p.textContent), chipy: document.querySelectorAll('.bom-chip').length, dt: [...p.querySelectorAll('dt')].map(e => e.textContent), dd: [...p.querySelectorAll('dd')].map(e => e.textContent), li: [...p.querySelectorAll('li')].map(e => norm(e.textContent)),
                 zobrazen: getComputedStyle(p).display !== 'none', cislo: document.querySelector('.slide.active .slide-title .num').textContent } : null;
    function norm(s) { return (s || '').replace(/[  ]/g, ' ').replace(/\s+/g, ' ').trim(); }
  });
  r.panel = !!panel && panel.zobrazen && /Zvolená konfigurace/.test(panel.text) && /Kód STL-27B047/.test(panel.text) && /Z čeho se skládá/.test(panel.text) && panel.chipy === 0
    && JSON.stringify(panel.dt) === JSON.stringify(['Šířka desky', 'Hloubka desky', 'Výška pracovní desky', 'LED osvětlení']) && panel.dd[0] === '1200 mm' && panel.li.length === 3 && /Profil 30×30 × 4/.test(panel.li[0]) && /1200 mm/.test(panel.li[0])
    && !/Kč/.test(panel.text) && panel.cislo === '02';
  try {
    await pockej(t.page, () => { const c = document.getElementById('viewer3dContainer'); return c && getComputedStyle(c).display !== 'none' && c.querySelector('canvas'); }, null, 20000);
    r.v3d = await t.page.evaluate(() => { const c = document.getElementById('viewer3dContainer'), f = document.getElementById('viewer3dFallback'); return !!c.querySelector('canvas') && getComputedStyle(f).display === 'none' && window.V3D && typeof window.V3D.mount === 'function'; })
      && t.pozadavky.some(x => /^GET \/js\/v3d\/viewer3d\.js\?v=[0-9a-f]{10}$/.test(x)) && t.pozadavky.some(x => /^GET \/css\/v3d\.css\?v=[0-9a-f]{10}$/.test(x)) && t.pozadavky.some(x => x === 'GET /api/public/offers/TESTTOKEN/model');
  } catch (e) { r.v3d = false; r.v3dChyba = String(e).slice(0, 120); }
  await t.page.screenshot({ path: path.join(SNIMKY, 'nabidka-konfigurace-3d.png') });
  if (html === HTML) { const el = await t.page.$('#bomList'); if (el) await el.screenshot({ path: path.join(SNIMKY, 'nabidka-konfigurace-panel.png') }); }
  r.bezChyb = t.chyby.length === 0;
  r.chyby = t.chyby.slice(0, 3);
  r.sipky = await (async () => {                          // sipky nad celoobrazovkovym prohlizecem neprepinaji stranky
    const idx = () => t.page.evaluate(() => [...document.querySelectorAll('.slide')].findIndex(s => s.classList.contains('active')));
    const pred = await idx();
    await t.page.evaluate(() => { window.V3D.isFullscreen = () => true; });
    await t.page.keyboard.press('ArrowRight'); await t.page.waitForTimeout(400);
    const behem = await idx();
    await t.page.evaluate(() => { window.V3D.isFullscreen = () => false; });
    await t.page.keyboard.press('ArrowRight'); await t.page.waitForTimeout(500);
    return behem === pred && (await idx()) === pred + 1;
  })();
  await t.browser.close();
  // zaloha: model neexistuje (404)
  const f = await otevri({ html, model: 'chyba' });
  await naStranku(f.page, 'view_3d');
  try {
    await pockej(f.page, () => /nepodařilo načíst/.test((document.getElementById('viewer3dHint') || {}).textContent || ''), null, 20000);
    r.zaloha = await f.page.evaluate(() => { const c = document.getElementById('viewer3dContainer'), fb = document.getElementById('viewer3dFallback'); return getComputedStyle(c).display === 'none' && getComputedStyle(fb).display !== 'none' && fb.querySelectorAll('img').length === 2; });
  } catch (e) { r.zaloha = false; }
  await f.browser.close();
  // zaloha: WebGL neni
  const w = await otevri({ html, webgl: false });
  await naStranku(w.page, 'view_3d');
  try {
    await pockej(w.page, () => /nepodařilo načíst/.test((document.getElementById('viewer3dHint') || {}).textContent || ''), null, 20000);
    r.bezWebgl = await w.page.evaluate(() => getComputedStyle(document.getElementById('viewer3dFallback')).display !== 'none');
  } catch (e) { r.bezWebgl = false; r.bezWebglChyba = String(e).slice(0, 100); }
  await w.browser.close();
  // bezpecne vkladani textu z nabidky
  const x = await otevri({ html, nabidka: nabidkaKonfigurace({ configuration: { kod: '<b>K</b>', summary: [{ label: '<img src=x onerror="window.__xss=1">L', value: '<script>window.__xss=2</script>V' }], bom: [{ nazev: '<svg onload=window.__xss=3>', mnozstvi: '<i>1</i>', rozmer: '<u>r</u>' }] } }) });
  await naStranku(x.page, 'view_3d');
  const xs = await x.page.evaluate(() => ({ xss: window.__xss, nebezpecne: document.querySelectorAll('#bomList img, #bomList svg, #bomList script, #bomList i, #bomList u, #bomList b').length, text: document.getElementById('bomList').textContent }));
  r.bezpecne = xs.xss === undefined && xs.nebezpecne === 0 && /<img src=x/.test(xs.text) && /<svg onload/.test(xs.text);
  await x.browser.close();
  return r;
}

(async () => {
  const r = await kontrola(HTML);
  over('P1 nabidka z konfigurace nema technicke vykresy: stranky jen cover, view_3d, pricing, closing', r.klice, r);
  over('P2 3D stranka: vlevo panel "Zvolená konfigurace" s kodem, souhrnem voleb (nazev, hodnota) a seznamem dilu (nazev x mnozstvi, rozmer) BEZ cen a bez klikaci chipu; cislo stranky 02', r.panel, r);
  over('P3 V3D se nacte a namontuje (viewer3d.js a v3d.css s libovolnym pinem ?v=, model pres /model): v okne je canvas, staticke snimky skryte', r.v3d, r);
  over('P4 zadna chyba stranky pri nacteni 3D prohlizece (konzole, vyjimky)', r.bezChyb, r.chyby);
  over('P5 selhani modelu (404) = tichy navrat ke statickym snimkum a hlaska "3D model se nepodařilo načíst", okno skryte, stranka jede dal', r.zaloha, r);
  over('P6 prohlizec bez WebGL = stejna zaloha (snimky), stranka nespadne', r.bezWebgl, r);
  over('P7 sipky na klavesnici neprepinaji stranky nabidky, dokud je V3D na cele obrazovce; jinak ano', r.sipky, r);
  over('P8 data z nabidky (kod, volby, dily) se vkladaji JEN jako text (zadny img, svg, script ani format. znacky, nic se nespusti)', r.bezpecne, r);

  // ---- cenova stranka a doprava
  {
    const t = await otevri();
    await naStranku(t.page, 'pricing');
    const c = await t.page.evaluate(() => {
      const tx = e => e ? e.textContent.replace(/[  ]/g, ' ').replace(/\s+/g, ' ').trim() : null;
      const tab = document.querySelector('.slide.active table.items');
      const radky = [...tab.querySelectorAll('tbody tr')].filter(tr => getComputedStyle(tr).display !== 'none');
      return { cislo: tx(document.querySelector('.slide.active .slide-title .num')), radku: radky.length, prvni: tx(radky[0]), hlavicky: [...tab.querySelectorAll('thead th')].map(tx), banner: tx(document.getElementById('totalBannerValue')), montaz: tx(document.getElementById('montazInfo')),
               dodani: tx(document.getElementById('orderOpts')), bomRadky: document.querySelectorAll('tr.bom-row').length };
    });
    over('P9 cenova stranka: jeden radek (stul s kodem), cena 26 802 Kc bez DPH, cislo stranky 03, montaz jako informace pod tabulkou (10 %), zadny klikaci radek kusovniku', c.cislo === '03' && c.radku === 1 && /STL-27B047/.test(c.prvni) && /26 802 Kč/.test(c.prvni) && /26 802/.test(c.banner)
         && /Montáž/.test(c.montaz || '') && /Smontov|Rozlož|rozlož/.test(c.dodani || '') && c.bomRadky === 0, c);
    await t.browser.close();
  }
  {
    const t = await otevri({ nabidka: nabidkaKonfigurace({ montaz_pct: 0, offer_options: Object.assign({}, nabidkaKonfigurace().offer_options, { montaz_pct: 0, hidden_delivery_state: 'smontovano' }) }) });
    await naStranku(t.page, 'pricing');
    const c = await t.page.evaluate(() => { const o = document.getElementById('orderOpts'); return { dodani: o ? o.innerText.replace(/\s+/g, ' ') : null, tlacitka: o ? [...o.querySelectorAll('button')].map(b => b.textContent.trim()) : [], montaz: (document.getElementById('montazInfo') || {}).textContent }; });
    over('P10 do zahranici (montaz 0, hidden_delivery_state smontovano): zakaznikovi se nabidne jen rozlozeny stul, zadna montaz', c.tlacitka.every(x => !/Smontov/i.test(x)) && !/Montáž.*Kč/.test(norm(c.montaz || '')) && !/Smontovan/.test(c.dodani || ''), c);
    await t.browser.close();
  }
  // ---- tisk: staticke snimky misto zivého okna
  {
    const t = await otevri({ tisk: true });
    const m = await t.page.evaluate(() => ({ okno: getComputedStyle(document.getElementById('viewer3dContainer')).display, zaloha: getComputedStyle(document.getElementById('viewer3dFallback')).display, panel: getComputedStyle(document.getElementById('bomList')).display }));
    over('P11 tisk: zive 3D okno a panel se vypousti, misto nich staticke snimky (viewer3dFallback)', m.okno === 'none' && m.zaloha === 'flex' && m.panel === 'none', m);
    await t.browser.close();
  }
  // ---- mobil: sloupec, nic nepreteka
  {
    const t = await otevri({ width: 390, height: 844, mobil: true });
    await naStranku(t.page, 'view_3d');
    await t.page.waitForTimeout(1500);
    const m = await t.page.evaluate(() => { const l = document.getElementById('view3dLayout'); return { sloupec: getComputedStyle(l).flexDirection, preteka: document.documentElement.scrollWidth > innerWidth + 1, slide: document.querySelector('.slide.active').scrollWidth > document.querySelector('.slide.active').clientWidth + 1 }; });
    await t.page.screenshot({ path: path.join(SNIMKY, 'nabidka-konfigurace-mobil.png') });
    over('P12 mobil 390 px: panel nad oknem (sloupec), nic nepreteka, bez chyb', m.sloupec === 'column' && !m.preteka && !m.slide && t.chyby.length === 0, { m, chyby: t.chyby });
    await t.browser.close();
  }
  // ---- starsi nabidka (bez zdroje) beze zmeny
  {
    const t = await otevri({ nabidka: Object.assign(JSON.parse(JSON.stringify(UKAZKA)), { source: null, configuration: null }) });
    const k = await klice(t.page);
    await naStranku(t.page, 'view_3d');
    await t.page.waitForTimeout(1200);
    const v3d = t.pozadavky.filter(x => /\/js\/v3d\/|\/css\/v3d/.test(x));
    const stary = await t.page.evaluate(() => ({ chipy: document.querySelectorAll('.bom-chip').length, cfg: !!document.querySelector('.cfg-title') }));
    over('P13 starsi nabidka ze sceny (source null) beze zmeny: vykresy jsou v sade stranek, V3D se vubec nenacita, panel s klikacimi chipy kusovniku', k.includes('drawings_1') && k.includes('drawings_2') && v3d.length === 0 && stary.chipy > 0 && !stary.cfg, { k, v3d, stary });
    await t.browser.close();
  }
  {
    // P14 nabidka z konfigurace S kotovanymi vykresy ze sceny (offer.configuration.vykresy): stranky Vykresy jsou zpet, cislovani odpovida nabidkam ze sceny (vykresy 02, 3D 03, cena 04)
    const nab = nabidkaKonfigurace(); nab.configuration.vykresy = true;
    const t = await otevri({ nabidka: nab });
    const k = await klice(t.page);
    const cisla = {};
    for (const kl of ['drawings_1', 'view_3d', 'pricing']) { await naStranku(t.page, kl); cisla[kl] = await t.page.evaluate(() => document.querySelector('.slide.active .slide-title .num').textContent); }
    const obr = await t.page.evaluate(() => [...document.querySelectorAll('.slide[data-key="drawings_1"] img')].map(i => i.getAttribute('src')));
    over('P14 nabidka z konfigurace S vykresy ze sceny: sada stranek cover, drawings_1, drawings_2, view_3d, pricing, closing; cislovani 02 (vykresy), 03 (3D), 04 (cena); vykresy se nacitaji pres token; V3D dal funguje',
      JSON.stringify(k) === JSON.stringify(['cover', 'drawings_1', 'drawings_2', 'view_3d', 'pricing', 'closing']) && cisla.drawings_1 === '02' && cisla.view_3d === '03' && cisla.pricing === '04'
      && obr.length >= 1 && obr.every(s => /\/api\/public\/offers\/TESTTOKEN\/image\//.test(s)) && t.chyby.length === 0 && t.pozadavky.some(x => /\/js\/v3d\/viewer3d\.js/.test(x)), { k, cisla, obr, chyby: t.chyby });
    await t.browser.close();
  }
  // ---- mutace stranky
  const mutuj = (stare, nove) => { if (!HTML.includes(stare)) throw new Error('mutace: kotva nenalezena: ' + stare.slice(0, 60)); return HTML.replace(stare, nove); };
  const mutace = {
    'bez vyrazeni vykresu u konfigurace': [mutuj('PAGES = PAGES.filter(k => k !== "drawings_1" && k !== "drawings_2");', 'void 0;'), 'klice'],
    'bez V3D (vlastni vetev initViewer3d)': [mutuj('if (offer.source === "configurator") return initViewerV3d(offer);', 'void 0;'), 'v3d'],
    'bez zalohy pri selhani': [mutuj('onError: fail,', 'onError: () => {},'), 'zaloha'],
    'vkladani nazvu a hodnot jako HTML': [mutuj('<dt>${escapeHtml(s.label)}</dt><dd>${escapeHtml(s.value)}</dd>', '<dt>${s.label}</dt><dd>${s.value}</dd>'), 'bezpecne'],
    'bez ochrany klavesnice': [mutuj('if (window.V3D && typeof window.V3D.isFullscreen === "function" && window.V3D.isFullscreen()) return;', ''), 'sipky'],
    'panel s cenami dilu misto neutralniho seznamu (bez nazvu dilu)': [mutuj('<li>${escapeHtml(b.nazev)} × ${escapeHtml(b.mnozstvi)}', '<li>${escapeHtml(b.nazev)}${escapeHtml(b.cena)} ×'), 'panel'],
  };
  for (const [popis, [html, klic]] of Object.entries(mutace)) {
    let m;
    try { m = await kontrola(html); } catch (e) { m = { [klic]: false, chyba: String(e).slice(0, 80) }; }
    over('PM mutace stranky: ' + popis + ' - test ji musi zachytit (kontrola "' + klic + '" selze)', m[klic] === false, m);
  }
  const ok = vysl.filter(Boolean).length;
  console.log(`\nVYSLEDEK nabidka z konfigurace, stranka: ${ok}/${vysl.length} OK (snimky: ${SNIMKY})`);
  process.exit(ok === vysl.length ? 0 : 1);
})().catch(e => { console.error('CHYBA TESTU:', e); process.exit(2); });
