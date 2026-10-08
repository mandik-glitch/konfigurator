// Admin: detail online nabidky - "Volby klienta" ukazuji i pocet kusu, zvolenou montaz a MISTO montaze Praha / Slavicin (bot16, 2026-10-07; Robert: "zase tam chybi montaz KDE Praha/Slavicin").
// SKUTECNY webapp/admin.html + vsechny webapp/admin/js/*.js v Chromiu proti falesnemu serveru (page.route, zadna sit ani DB): openOnlineOfferStats() nad odpovedi /stats.
// Kandidat pred nasazenim: ADMIN_HTML=... CRM_NABIDKY_JS=... node test_admin_volby_js.js   (puvodni crm-nabidky.js MUSI selhat)
const { chromium } = require('/opt/konfigurator/node_modules/playwright-core');
const fs = require('fs');
const path = require('path');

const REPO = path.join(__dirname, '../..');
const ADMIN_HTML = process.env.ADMIN_HTML || path.join(REPO, 'webapp/admin.html');
const JS_DIR = path.join(REPO, 'webapp/admin/js');
const PREPIS = { 'crm-nabidky.js': process.env.CRM_NABIDKY_JS };
const vysl = [];
const over = (nazev, podminka, detail) => { vysl.push(!!podminka); console.log((podminka ? 'OK   ' : 'FAIL ') + nazev + (podminka ? '' : '  -> ' + JSON.stringify(detail))); };

const QUILL_ATRAPA = `
  window.Quill = function Quill() {};
  Quill.__icons = {};
  Quill.import = function (n) { return n === 'ui/icons' ? Quill.__icons : class BlockEmbed { static create() { return document.createElement('div'); } }; };
  Quill.register = function () {};
`;

(async () => {
  const stav = { stats: null };
  const chyby = [];
  const browser = await chromium.launch({ args: ['--no-sandbox'] });
  const page = await browser.newPage({ viewport: { width: 1400, height: 1000 } });
  page.on('pageerror', e => chyby.push(e.message));
  page.on('dialog', d => d.accept());
  await page.route('**/*', async route => {
    const req = route.request();
    const u = new URL(req.url());
    if (u.hostname === 'cdn.jsdelivr.net' && /quill@1\.3\.7\/dist\/quill\.min\.js$/.test(u.pathname)) return route.fulfill({ status: 200, contentType: 'application/javascript', body: QUILL_ATRAPA });
    if (u.hostname === 'cdn.jsdelivr.net' && /\.css$/.test(u.pathname)) return route.fulfill({ status: 200, contentType: 'text/css', body: '' });
    if (u.hostname !== 'admin.test') return route.abort();
    const p = u.pathname, m = req.method();
    const json = (status, body) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });
    if (p === '/admin.html') return route.fulfill({ status: 200, contentType: 'text/html; charset=utf-8', body: fs.readFileSync(ADMIN_HTML, 'utf8') });
    const mJs = /^\/admin\/js\/([A-Za-z0-9_.-]+\.js)$/.exec(p);
    if (mJs) {
      const cesta = PREPIS[mJs[1]] || path.join(JS_DIR, mJs[1]);
      if (!fs.existsSync(cesta)) return route.fulfill({ status: 404, body: 'nenalezeno' });
      return route.fulfill({ status: 200, contentType: 'application/javascript; charset=utf-8', body: fs.readFileSync(cesta, 'utf8') });
    }
    if (p === '/api/auth/me') return json(200, { user: { id: 1, role: 'admin', name: 'Test Admin', email: 'test@lokalni', theme_admin: 'dark', permissions: {} } });
    if (p === '/api/admin/field-labels') return json(200, { labels: {}, options: {} });
    if (p === '/api/admin/scene-offers/777/stats' && m === 'GET') return json(200, stav.stats);
    if (p.startsWith('/api/')) return json(200, m === 'GET' ? {} : { status: 'ok' });
    return route.fulfill({ status: 404, body: '' });
  });

  await page.goto('http://admin.test/admin.html');
  try {
    await page.waitForFunction(() => typeof openOfferEditModal === 'function' && typeof currentOnlineOfferId !== 'undefined', null, { timeout: 15000 });
  } catch (e) {
    console.log('FAIL admin se nenacetl: ' + e.message.split('\n')[0] + ' | chyby: ' + chyby.slice(0, 3).join(' | '));
    process.exit(1);
  }
  await page.waitForTimeout(500);

  const statistiky = prefs => ({ offer_number: 'Logiman0200', by_ip: [], by_page: [], by_click: [], acceptance: null, declines: [], notes: [], order_prefs: prefs });
  const T = { shipping_method: 'vlastni', payment_method: 'zaloha', deposit_pct: 70, delivery_state: null, delivery_zip: null, toptrans_price_czk: null, updated_at: '2026-10-07T18:00:00' };
  const otevri = async prefs => {
    stav.stats = statistiky(prefs); chyby.length = 0;
    await page.evaluate(() => openOnlineOfferStats(777)); await page.waitForTimeout(200);
    return page.evaluate(() => { const e = document.getElementById('onlineOfferStatsOrderPrefs'); return { text: e.textContent.replace(/\s+/g, ' ').trim(), html: e.innerHTML }; });
  };
  let o = await otevri([{ ...T, qty: 3, montaz_zvolena: true, montaz_misto: 'slavicin', montaz_misto_label: 'Slavičín' }]);
  over('A1 zvolena montaz ve Slavicine: radek voleb klienta obsahuje "Montáž – Slavičín" a "3 ks"', /Montáž – Slavičín/.test(o.text) && /3 ks/.test(o.text), o.text);
  over('A2 zbyle volby zustavaji (odvoz, zalohova platba 70 %)', /Vlastní odvoz/.test(o.text) && /Zálohová platba 70 %/.test(o.text), o.text);
  o = await otevri([{ ...T, qty: 1, montaz_zvolena: true, montaz_misto: 'praha', montaz_misto_label: 'Praha' }]);
  over('A3 montaz v Praze, 1 ks: "Montáž – Praha", pocet kusu se pri 1 ks neuvadi', /Montáž – Praha/.test(o.text) && !/ ks\b/.test(o.text.replace(/Vlastní odvoz/, '')), o.text);
  o = await otevri([{ ...T, qty: 1, montaz_zvolena: false, montaz_misto: null, montaz_misto_label: null }]);
  over('A4 montaz nezvolena: v radku zadna montaz', !/Montáž/.test(o.text), o.text);
  o = await otevri([{ ...T }]);
  over('A5 starsi API (odpoved bez poli qty / montaz_*): nic nespadne a zadna montaz se neukaze', !/Montáž|\d ks/.test(o.text) && /Vlastní odvoz/.test(o.text) && chyby.length === 0, { text: o.text, chyby });
  o = await otevri([{ ...T, qty: 2, montaz_zvolena: true, montaz_misto: 'x', montaz_misto_label: null }]);
  over('A6 misto bez popisku (smazane misto): ukaze se klic', /Montáž – x/.test(o.text), o.text);
  o = await otevri([{ ...T, qty: 2, montaz_zvolena: true, montaz_misto: 'x', montaz_misto_label: '<img src=x onerror="window.__xss=1">' }]);
  over('A7 popisek mista je escapovany (zadne HTML z dat)', !/<img/i.test(o.html) && await page.evaluate(() => !window.__xss), o.html);
  o = await otevri([{ ...T, qty: 1, montaz_zvolena: true, montaz_misto: 'praha', montaz_misto_label: 'Praha' }, { ...T, shipping_method: 'toptrans', payment_method: 'dobirka', deposit_pct: null, qty: 4, montaz_zvolena: false, montaz_misto: null, montaz_misto_label: null, updated_at: '2026-10-07T17:00:00' }]);
  over('A8 vice navstevniku: kazdy radek ma sve vlastni volby (prvni s montazi v Praze, druhy s Toptrans, 4 ks a bez montaze)', /Montáž – Praha/.test(o.text) && /Toptrans/.test(o.text) && /4 ks/.test(o.text) && (o.text.match(/Montáž/g) || []).length === 1, o.text);
  over('A9 bez JS chyb', chyby.filter(e => !/loadOnlineOffersList/.test(e)).length === 0, chyby);
  await browser.close();
  const ok = vysl.filter(Boolean).length;
  console.log(`\nVYSLEDEK admin - volby klienta (montaz, misto, ks): ${ok}/${vysl.length} OK`);
  process.exit(ok === vysl.length ? 0 : 1);
})().catch(e => { console.error('TEST SPADL:', e.message); process.exit(2); });
