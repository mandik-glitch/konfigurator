// Harness panelu Prehledy > John: SKUTECNY webapp/admin.html + vsechny skripty z webapp/admin/js/ v Chromiu proti falesnemu serveru (page.route, zadna sit, zadna DB),
// stejny princip jako scripts/2026-09-30_karta_produktu_testy/harness.js. Falesny je i /nahled-john/prace.json (stav.prace) a /api/admin/john/stav (stav.live).
// Kandidat pred nasazenim (nic se nezapise do zivych souboru):  ADMIN_HTML=<kandidat>/admin.html JS_DIR=<kandidat>/js node test_john_panel.js
const { chromium } = require('/opt/konfigurator/node_modules/playwright');
const fs = require('fs');
const path = require('path');

const REPO = path.join(__dirname, '../..');
const ADMIN_HTML = process.env.ADMIN_HTML || path.join(REPO, 'webapp/admin.html');
const JS_DIR = process.env.JS_DIR || path.join(REPO, 'webapp/admin/js');
const QUILL_ATRAPA = `window.Quill = function Quill() {}; Quill.__icons = {}; Quill.import = function (n) { return n === 'ui/icons' ? Quill.__icons : class BlockEmbed { static create() { return document.createElement('div'); } }; }; Quill.register = function () {};`;

// opts: { user: {role, permissions, name}, prace, live, viewport: {width,height}, interval (ms, window.__johnInterval), hash }
//   prace: objekt (200 JSON) | {__status: 404|500} | {__raw: "text"} ;  live: objekt (200) | {__status: 404|403}
async function otevriAdmin(opts) {
  opts = opts || {};
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: opts.viewport || { width: 1300, height: 900 }, locale: 'cs-CZ' });
  const page = await ctx.newPage();
  const chyby = [], pozadavky = { prace: 0, live: 0 };
  const stav = { prace: opts.prace === undefined ? null : opts.prace, live: opts.live === undefined ? { __status: 404 } : opts.live, lastModified: opts.lastModified || null };
  page.on('pageerror', e => chyby.push(String(e.message)));
  page.on('console', m => { if (m.type() === 'error' && !/Failed to load resource/.test(m.text())) chyby.push('console: ' + m.text().slice(0, 200)); });
  await page.addInitScript(i => { if (i) window.__johnInterval = i; window.__marker = 'ziva'; }, opts.interval || 0);
  await page.route('**/*', async route => {
    const req = route.request(), u = new URL(req.url());
    if (u.hostname === 'cdn.jsdelivr.net' && /quill@1\.3\.7\/dist\/quill\.min\.js$/.test(u.pathname)) return route.fulfill({ status: 200, contentType: 'application/javascript', body: QUILL_ATRAPA });
    if (u.hostname === 'cdn.jsdelivr.net' && /\.css$/.test(u.pathname)) return route.fulfill({ status: 200, contentType: 'text/css', body: '' });
    if (u.hostname !== 'admin.test') return route.abort();
    const p = u.pathname, m = req.method();
    const json = (status, body, hdr) => route.fulfill({ status, contentType: 'application/json', headers: hdr || {}, body: JSON.stringify(body) });
    if (p === '/admin.html') return route.fulfill({ status: 200, contentType: 'text/html; charset=utf-8', body: fs.readFileSync(ADMIN_HTML, 'utf8') });
    const mJs = /^\/admin\/js\/([A-Za-z0-9_.-]+\.js)$/.exec(p);
    if (mJs) {
      const cesta = path.join(JS_DIR, mJs[1]);
      if (!fs.existsSync(cesta)) return route.fulfill({ status: 404, body: 'nenalezeno' });
      return route.fulfill({ status: 200, contentType: 'application/javascript; charset=utf-8', body: fs.readFileSync(cesta, 'utf8') });
    }
    if (p === '/nahled-john/prace.json') {
      pozadavky.prace++;
      const v = stav.prace;
      if (v && v.__status) return route.fulfill({ status: v.__status, contentType: 'text/plain', body: 'x' });
      if (v && v.__raw !== undefined) return route.fulfill({ status: 200, contentType: 'application/json', body: v.__raw });
      if (v === null) return route.fulfill({ status: 404, contentType: 'text/plain', body: 'nenalezeno' });
      return json(200, v, stav.lastModified ? { 'Last-Modified': stav.lastModified } : {});
    }
    if (p === '/api/admin/john/stav') {
      pozadavky.live++;
      const v = stav.live;
      if (v && v.__status) return json(v.__status, { error: 'x' });
      return json(200, v);
    }
    if (p === '/api/auth/me') return json(200, { user: Object.assign({ id: 1, role: 'admin', name: 'Test Admin', email: 'test@lokalni', theme_admin: 'dark', permissions: {}, active: 1 }, opts.user || {}) });
    if (p === '/api/admin/field-labels') return json(200, { labels: {}, options: {} });
    if (p === '/api/gallery-items') return json(200, { items: [] });
    if (p.startsWith('/api/')) return json(200, m === 'GET' ? {} : { status: 'ok' });
    return route.fulfill({ status: 404, body: '' });
  });
  await page.goto('http://admin.test/admin.html' + (opts.hash || ''));
  await page.waitForFunction(() => typeof ADMIN_USER !== 'undefined' && !!ADMIN_USER, null, { timeout: 20000 });
  return { browser, page, stav, chyby, pozadavky, zavri: () => browser.close() };
}
module.exports = { otevriAdmin };
