// Harness pro testy stranky online nabidky "Pricky do multiboxu" (bot8, 2026-10-07): SKUTECNA stranka webapp/nabidka-online.html v headless Chromiu proti FALESNEMU serveru (page.route:
// zadna DB, zadna sit, nic se nezapisuje). Pouziva ho test_page.js (atrapa pluginu + atrapa V3D) a test_page_real.js (skutecny viewer3d.js + skutecny plugin, three z node_modules).
// Odvozeno z scripts/2026-10-06_nabidka_montaz_polozky_testy/harness.js. Zadny fixture v repu: zakaznicka GLB s `mbx` stavi scripts/2026-10-02_v3d_testy/build_karty.py (Blender) do
// <V3D_TEST_OUT>/out2/<karta>.offer.glb a `payload_<karta>.json` (verejny blok offer.pricky) si harness pri startu VYROBI z `spec` toho GLB pres api/nabidka_pricky.payload(spec, CENY, True)
// (testovaci ceny: p186 = id 9001, 39 Kc; p91 = id 9002, 29 Kc; aktivni) do docasne slozky, ktera se po testu smaze.
// Prostredi (vse nepovinne): PRICKY_REPO (koren repa, vychozi ../..), NABIDKA_HTML (kandidat stranky, vychozi <repo>/webapp/nabidka-online.html), PLUGIN_JS (skutecny plugin, vychozi
//   <repo>/webapp/js/v3d/pricky-multibox.js), PRICKY_API (slozka s nabidka_pricky.py a v3d_glb.py, vychozi <repo>/api; kandidat), V3D_TEST_OUT (vychozi <tmp>/v3d_testy), PRICKY_FIX (primo slozka
//   s <karta>.offer.glb, vychozi <V3D_TEST_OUT>/out2), V3D_NODE_MODULES (vychozi /opt/konfigurator/node_modules), THREE_DIR (vychozi <node_modules>/three), PY (python, vychozi python3).
const fs = require('fs');
const os = require('os');
const path = require('path');
const cp = require('child_process');

const HERE = __dirname;
const REPO = process.env.PRICKY_REPO || path.resolve(HERE, '..', '..');
const NODE_MODULES = process.env.V3D_NODE_MODULES || '/opt/konfigurator/node_modules';
const { chromium } = require(path.join(NODE_MODULES, 'playwright-core'));
const NABIDKA_HTML = process.env.NABIDKA_HTML || path.join(REPO, 'webapp', 'nabidka-online.html');
const PLUGIN_JS = process.env.PLUGIN_JS || path.join(REPO, 'webapp', 'js', 'v3d', 'pricky-multibox.js');
const API = process.env.PRICKY_API || path.join(REPO, 'api');
const OUT = process.env.V3D_TEST_OUT || path.join(os.tmpdir(), 'v3d_testy');
const FIX = process.env.PRICKY_FIX || path.join(OUT, 'out2');
const THREE_DIR = process.env.THREE_DIR || path.join(NODE_MODULES, 'three');
const VZOR = path.join(REPO, 'scripts', '2026-10-01_nabidka_tabulka_cen_testy', 'ukazka_nabidky.json');     // skutecna nabidka z DB (sablona; 13 radku, total_price 27 353 Kc bez DPH)
const PNG = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==', 'base64');
const MISTA = [{ klic: 'praha', nazev: 'Praha' }, { klic: 'slavicin', nazev: 'Slavičín' }];
const PLUGIN_FILE = { stub: path.join(HERE, 'stub-pricky.js'), real: PLUGIN_JS };

// ---- vstupy: payloady z GLB karet a z RUCNICH scenaru SPECY (Python, api/nabidka_pricky.payload) v docasne slozce
let _vstupy = null;
// Rucni scenare se supliky / smisenymi skupinami: pole `mbx` jako ve spec v3d (docs/KONTRAKT_NABIDKA_PRICKY.md; mm, Y nahoru), bez GLB. Volitelne `neaktivni` (klice dilu s neaktivni kartou) a `admin` (nahled zamestnance).
// SUP = ocelovy podnos (sk 4): L = sirka (delsi strana), W = hloubka zepredu dozadu, H = vyska; podleZ = delsi strana podel osy Z; MBX = multibox 81 mm vysoky.
const SUP = (id, s, y, L, W, H, podleZ = false) => ({ id, min: [0, y, 0], max: podleZ ? [W, y + H, L] : [L, y + H, W], e: 1, p: null, n: Number(id.slice(1)), s, sk: 4 });
const MBX = (id, s, sk, x, L, W) => ({ id, min: [x, 600, 0], max: [x + L, 681, W], e: 1, p: null, n: Number(id.slice(1)), s, sk });
const SUP6 = [SUP('b01', 1, 0, 443, 384, 137), SUP('b02', 1, 150, 443, 384, 137), SUP('b03', 1, 300, 443, 384, 137), SUP('b04', 1, 450, 695, 384, 137), SUP('b05', 1, 600, 695, 384, 137), SUP('b06', 1, 750, 695, 384, 137)];
const SMISENE = [MBX('b01', 1, 1, 0, 395.5, 186), MBX('b02', 1, 1, 400, 395.5, 186), MBX('b03', 1, 1, 800, 288, 186), MBX('b04', 1, 1, 1100, 395.5, 91), SUP('b05', 2, 0, 443, 384, 137), SUP('b06', 2, 150, 443, 384, 137), SUP('b07', 2, 300, 443, 384, 137)];
const SPECY = {
  sup_dva: { mbx: SUP6.concat([SUP('b07', 2, 0, 950, 384, 101, true), SUP('b08', 2, 150, 950, 384, 137, true), SUP('b09', 2, 300, 950, 384, 210, true)]) },       // 2 skupiny supliku: 6 podnosu (3x 443, 3x 695) a 3 podnosy po 950
  sup_jeden: { mbx: [SUP('b01', 1, 0, 443, 332, 137)] },                                                                                                    // 1 podnos (sety se deduplikuji na bez + plny)
  sup_mix: { mbx: SUP6.concat([SUP('b07', 2, 0, 443, 332, 137)]) },                                                                                         // skupina se vsemi sety + skupina jen s bez / plny
  smisene: { mbx: SMISENE },                                                                                                                                // police multiboxu (4) + supliky (3)
  smisene_skryto: { mbx: SMISENE, neaktivni: ['ps384v137'], admin: true },                                                                                  // totez, karta pricek supliku jeste neni aktivni -> skupina supliku skryto (jen admin)
};
const PY_PAYLOADY = `
import inspect, json, os, re, sys
api, fix, out = sys.argv[1:4]
specy = json.load(open(sys.argv[4], encoding="utf-8")) if len(sys.argv) > 4 else {}
sys.path.insert(0, api); sys.dont_write_bytecode = True
import v3d_glb
import nabidka_pricky as P
V5 = "zapnuto" not in inspect.signature(P.payload).parameters          # v5: payload(spec, ceny, nahled_admin=False); starsi: payload(spec, ceny, zapnuto, nahled_admin=False)
def ceny(neaktivni=()):
    return {k: {"id": 9001 + i, "cena": float(d["cena0"]), "nazev": d["nazev"], "aktivni": k not in neaktivni} for i, (k, d) in enumerate(P.DILY.items())}
def vyrob(spec, neaktivni=(), admin=False):
    c = ceny(neaktivni)
    return P.payload(spec, c, nahled_admin=admin) if V5 else P.payload(spec, c, not admin, admin)
res = {}
def uloz(jmeno, pl):
    json.dump(pl, open(os.path.join(out, "payload_%s.json" % jmeno), "w", encoding="utf-8"), ensure_ascii=False)
    res[jmeno] = [len(pl["skupiny"]), len(pl["boxy"])]
for fn in sorted(os.listdir(fix)):
    m = re.fullmatch(r"(\\d+)\\.offer\\.glb", fn)
    if not m:
        continue
    spec = v3d_glb.embedded_spec(open(os.path.join(fix, fn), "rb").read())
    pl = vyrob(spec) if spec else None
    if pl:
        uloz(m.group(1), pl)
for jmeno, d in sorted(specy.items()):
    pl = vyrob({"mbx": d["mbx"]}, d.get("neaktivni", ()), bool(d.get("admin")))
    if pl:
        uloz(jmeno, pl)
print("PAYLOADY " + json.dumps(res))
`;
function vstupy() {
  if (_vstupy) return _vstupy;
  for (const k of ['4921']) {
    if (!fs.existsSync(path.join(FIX, k + '.offer.glb'))) {
      console.error(`CHYBA: chybi ${path.join(FIX, k + '.offer.glb')} - postav zakaznicka GLB: python3 scripts/2026-10-02_v3d_testy/build_karty.py 4921 4453 (V3D_TEST_OUT=${OUT})`);
      process.exit(2);
    }
  }
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'pricky_page_'));
  process.on('exit', () => { try { fs.rmSync(dir, { recursive: true, force: true }); } catch (e) { /* docasna slozka */ } });
  let karty = {};
  try {
    fs.writeFileSync(path.join(dir, 'specy.json'), JSON.stringify(SPECY));
    const r = cp.execFileSync(process.env.PY || 'python3', ['-B', '-c', PY_PAYLOADY, API, FIX, dir, path.join(dir, 'specy.json')], { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] });
    const m = /^PAYLOADY (.+)$/m.exec(r);
    karty = m ? JSON.parse(m[1]) : {};
  } catch (e) {
    console.error('CHYBA: payload z GLB se nepodarilo vyrobit (' + API + '): ' + ((e.stderr && e.stderr.toString().trim().split('\n').pop()) || e.message));
    process.exit(2);
  }
  if (!karty['4921']) { console.error('CHYBA: 4921.offer.glb nema mbx / payload (postav GLB aktualnim buildem: build_karty.py)'); process.exit(2); }
  _vstupy = { dir, karty };
  return _vstupy;
}
const maKartu = karta => !!vstupy().karty[karta];
const payloadVse = (karta = '4921') => JSON.parse(fs.readFileSync(path.join(vstupy().dir, `payload_${karta}.json`), 'utf8'));          // payload presne tak, jak ho dal server (vc. skupin supliku)
// Zakaznicka GLB z v5 buildu (build_karty.py) maji vedle multiboxu i podnosy supliku (skupiny k:"suplik" s vlastnimi cisly skupin; 4921 = 6 skupin, s3 = suplik). Hlavni scenare testu (s1..s3 = multiboxy)
// potrebuji strukturu nezavislou na generaci GLB, proto payload() vraci jen skupiny multiboxu prejmenovane na s1..sN v poradi; starsi GLB bez supliku beze zmeny. Supliky: scenare SPECY a payloadVse().
function jenMultiboxy(P) {
  const sk = P.skupiny.filter(g => g.k !== 'suplik');
  if (sk.length === P.skupiny.length) return P;
  const mapa = {}, ids = new Set();
  sk.forEach((g, i) => { mapa[g.id] = 's' + (i + 1); g.boxy.forEach(b => ids.add(b)); });
  P.skupiny = sk.map(g => Object.assign(g, { id: mapa[g.id] }));
  P.boxy = P.boxy.filter(b => ids.has(b.id)).map(b => Object.assign(b, { s: mapa[b.s] }));
  const k = new Set(P.boxy.map(b => b.k));
  Object.keys(P.typy).forEach(t => { if (!k.has(t)) delete P.typy[t]; });
  const dil = new Set(Object.values(P.typy).map(t => t.dil));
  P.dily = P.dily.filter(d => dil.has(d.klic));
  P.nahled_admin = P.skupiny.some(g => g.skryto);
  return P;
}
const payload = (karta = '4921') => (/^\d+$/.test(String(karta)) ? jenMultiboxy(payloadVse(karta)) : payloadVse(karta));          // jen GLB karty (cislo); rucni scenare SPECY beze zmeny
const glb = (karta = '4921') => fs.readFileSync(path.join(FIX, `${karta}.offer.glb`));

// nabidka z karty Vandr s 3D modelem a offer.pricky (uprava(d) smi menit libovolna pole); pricky: null = bez offer.pricky
function nabidka({ karta = '4921', pricky, uprava } = {}) {
  const d = JSON.parse(fs.readFileSync(VZOR, 'utf8'));
  d.has_3d_model = true; d.model_url = '/api/public/offers/TESTTOKEN/model'; d.source = null; d.order_prefs = null;
  d.offer_options = Object.assign({}, d.offer_options, { show_qr: true, is_vehicle_assembly: true });
  d.montaz_pct = 10;
  if (pricky !== null) d.pricky = pricky || payload(karta);
  if (uprava) uprava(d);
  return d;
}

// atrapa V3D (rizena z testu): mount zaznamena volani, zavola opts.plugins s falesnym ctx a (pokud window.__v3dAuto !== false) hned dokonci `ready`; window.__v3dChyba = true ready odmitne
const V3D_STUB = `
  window.__v3d = { calls: [], pluginErr: null };
  window.__v3dPlay = [];                                  // zaznam volani viewer.play / playAll: {fn, id, dir, t}; window.__v3dPlayChyba = true: play vyhodi vyjimku; window.__v3dBezPlay = true: viewer play/playAll nema
  window.V3D = { deps: [], isFullscreen: function () { return false; }, mount: function (el, o) {
    var c = { o: o, el: el };
    c.ready = new Promise(function (res, rej) { c.res = res; c.rej = rej; });
    window.__v3d.calls.push(c);
    var ctx = { THREE: {}, scene: {}, model: {}, requestRender: function () {}, onFrame: function () { return function () {}; }, setAnimating: function () {}, state: function () { return { mode: 'real' }; } };
    var ends = [];
    (o.plugins || []).forEach(function (f) { try { var e = f(ctx); if (typeof e === 'function') ends.push(e); } catch (x) { window.__v3d.pluginErr = String(x); } });
    if (window.__v3dAuto !== false) setTimeout(function () { if (window.__v3dChyba) c.rej(new Error('test')); else c.res(); }, 0);
    var api = { ready: c.ready, dispose: function () { ends.forEach(function (f) { f(); }); }, state: function () { return { mode: 'real' }; },
      play: function (id, dir) { window.__v3dPlay.push({ fn: 'play', id: id, dir: dir, t: performance.now() }); if (window.__v3dPlayChyba) throw new Error('test play'); return true; },
      playAll: function (dir) { window.__v3dPlay.push({ fn: 'playAll', dir: dir, t: performance.now() }); return true; } };
    if (window.__v3dBezPlay) { delete api.play; delete api.playAll; }
    return api;
  } };
`;

// v3d: 'stub' (atrapa V3D) | 'real' (skutecny viewer3d.js z repa, three z THREE_DIR, vyzaduje gl:true); plugin: 'stub' | 'real' | '404'; model: 'glb' | '404'
async function otevri({ width = 1440, height = 900, data = null, mista = MISTA, mobil = false, init = [], v3d = 'stub', plugin = 'stub', model = 'glb', karta = '4921', gl = false, ls = null } = {}) {
  const d = data || nabidka({ karta });
  const chyby = [], konzole = [], qr = [], accepts = [], posty = [], urls = [];
  const browser = await chromium.launch({ args: gl ? ['--no-sandbox', '--use-gl=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] : ['--no-sandbox'] });
  const ctx = await browser.newContext({ viewport: { width, height }, hasTouch: !!mobil, isMobile: !!mobil, deviceScaleFactor: 1 });
  const page = await ctx.newPage();
  page.on('pageerror', e => chyby.push(e.message));
  page.on('console', m => { if (m.type() === 'error' || m.type() === 'warning') konzole.push(m.type() + ': ' + m.text()); });
  const skripty = [];
  // pocatecni obsah localStorage jen pri PRVNIM nacteni karty (priznak v sessionStorage), aby reload netestoval uz prepsane hodnoty
  if (ls !== null) skripty.push(`try { if (!sessionStorage.getItem('__ls_init')) { sessionStorage.setItem('__ls_init', '1'); localStorage.setItem('pricky:TESTTOKEN', ${JSON.stringify(typeof ls === 'string' ? ls : JSON.stringify(ls))}); } } catch (e) {}`);
  if (v3d === 'stub') skripty.push(V3D_STUB);
  [].concat(init).forEach(s => skripty.push(typeof s === 'function' ? `(${s.toString()})()` : s));
  if (skripty.length) await page.addInitScript(skripty.join('\n;\n'));
  await page.route('**/*', async route => {
    const req = route.request();
    const u = new URL(req.url());
    if (u.hostname === 'cdn.jsdelivr.net') {                                             // three r128 pro skutecny viewer: z node_modules (stejna verze jako CDN), jinak ze site
      const m = /^\/npm\/three@0\.128\.0\/(.+)$/.exec(u.pathname);
      const f = m && path.join(THREE_DIR, m[1]);
      if (gl && f && fs.existsSync(f)) return route.fulfill({ status: 200, contentType: 'text/javascript', body: fs.readFileSync(f) });
      return gl ? route.continue() : route.abort();
    }
    if (u.hostname !== 'nab.test') return route.abort();
    const p = u.pathname, m = req.method();
    urls.push(m + ' ' + p);
    const json = (status, body) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });
    if (p === '/nabidka-online.html') return route.fulfill({ status: 200, contentType: 'text/html; charset=utf-8', body: fs.readFileSync(NABIDKA_HTML, 'utf8') });
    if (p === '/api/public/offers/TESTTOKEN' && m === 'GET') return json(200, d);
    if (p === '/api/public/offers/TESTTOKEN/order-prefs' && m === 'POST') { posty.push(JSON.parse(req.postData() || '{}')); return json(200, { status: 'ok' }); }
    if (p === '/api/public/offers/TESTTOKEN/model') return model === 'glb' ? route.fulfill({ status: 200, contentType: 'model/gltf-binary', body: glb(karta) }) : route.fulfill({ status: 404, body: '' });
    if (p === '/api/public/offers/TESTTOKEN/payment-qr') { qr.push(u.search); return route.fulfill({ status: 200, contentType: 'image/png', body: PNG }); }
    if (p === '/api/public/offers/TESTTOKEN/accept' && m === 'POST') { accepts.push(JSON.parse(req.postData() || '{}')); return json(201, { status: 'ok', order_number: 'OB-1' }); }
    if (p === '/js/v3d/pricky-multibox.js') {
      if (plugin === '404') return route.fulfill({ status: 404, body: '' });
      return route.fulfill({ status: 200, contentType: 'text/javascript', body: fs.readFileSync(PLUGIN_FILE[plugin], 'utf8') });
    }
    if (/^\/api\/public\/offers\/TESTTOKEN\/(image|render)\//.test(p)) return route.fulfill({ status: 200, contentType: 'image/png', body: PNG });
    if (p === '/api/theme-colors') return json(200, { light: {}, dark: {} });
    if (p === '/api/montaz-mista') return json(200, { mista });
    if (p.startsWith('/api/')) return json(200, m === 'GET' ? {} : { status: 'ok' });
    if (p.startsWith('/js/') || p.startsWith('/css/') || p.startsWith('/katalog/')) {
      const f = path.join(REPO, 'webapp', p);
      if (fs.existsSync(f)) return route.fulfill({ status: 200, contentType: p.endsWith('.js') ? 'text/javascript' : p.endsWith('.css') ? 'text/css' : 'application/octet-stream', body: fs.readFileSync(f) });
    }
    return route.fulfill({ status: 404, body: '' });
  });
  await page.goto('http://nab.test/nabidka-online.html?t=TESTTOKEN');
  try {
    await page.waitForSelector('#deck.show', { timeout: 15000 });
    await page.waitForTimeout(400);
  } catch (e) {
    throw new Error('harness: nabidka se nenacetla. ' + e.message.split('\n')[0] + ' | chyby stranky: ' + chyby.slice(0, 5).join(' | '));
  }
  return { browser, page, ctx, chyby, konzole, qr, accepts, posty, urls, data: d };
}

// prochazeni slidu tlacitky Dalsi / Predchozi (i zpet)
async function naSlide(page, klic) {
  for (let i = 0; i < 16; i++) {
    const smer = await page.evaluate(k => {
      const kl = [...document.querySelectorAll('.slide')].map(s => s.dataset.key), cil = kl.indexOf(k), akt = kl.indexOf(document.querySelector('.slide.active').dataset.key);
      return cil < 0 ? null : (cil === akt ? 0 : (cil > akt ? 1 : -1));
    }, klic);
    if (smer === null) break;
    if (smer === 0) { await page.waitForTimeout(120); return; }
    await page.click(smer > 0 ? '#btnNext' : '#btnPrev');
    await page.waitForTimeout(160);
  }
  throw new Error('slide ' + klic + ' nenalezen');
}
// primy skok na slide pres tecku navigace (nepruchazi mezilehlymi slidy, takze nespusti nacitani 3D)
async function skocNaSlide(page, klic) {
  const idx = await page.evaluate(k => [...document.querySelectorAll('.slide')].findIndex(s => s.dataset.key === k), klic);
  if (idx < 0) throw new Error('slide ' + klic + ' nenalezen');
  await page.evaluate(i => document.querySelector(`#dots .dot[data-index="${i}"]`).click(), idx);          // tecky jsou na uzkem displeji skryte - programovy klik
  await page.waitForTimeout(250);
}
// slide 3D + pockat na sekci priccek (nebo na to, ze se neukaze)
async function na3D(page, cekejPanel = true) {
  await naSlide(page, 'view_3d');
  if (cekejPanel) await page.waitForSelector('#prickyPanel:not([hidden]) .pr-card', { timeout: 20000 });          // za zatizeni (load 40+) trva stazeni modelu a sestaveni sceny dele nez 8 s
  else {                                                                   // bez cekani na panel: aspon pockat, az se zavola V3D.mount (atrapa V3D; za zatizeni trva nacteni modelu a viewer3d.js dele nez 0,7 s)
    await page.waitForFunction(() => !window.__v3d || !Array.isArray(window.__v3d.calls) || window.__v3d.calls.length > 0, null, { timeout: 8000 }).catch(() => {});
    await page.waitForTimeout(700);
  }
}
const naCeny = page => naSlide(page, 'pricing');
const cislo = s => Number(String(s || '').replace(/[^\d,.-]/g, '').replace(',', '.'));
const norm = s => String(s || '').replace(/[  ]/g, ' ').replace(/\s+/g, ' ').trim();

module.exports = { otevri, nabidka, payload, payloadVse, maKartu, SPECY, glb, naSlide, skocNaSlide, na3D, naCeny, cislo, norm, V3D_STUB, MISTA, PNG, REPO, NABIDKA_HTML, PLUGIN_JS, API, FIX, THREE_DIR, NODE_MODULES };
