// Harness zalozky Prodej > E-maily ucetni: SKUTECNY webapp/admin.html + vsechny skripty z webapp/admin/js/ v Chromiu proti falesnemu serveru (page.route, zadna sit, zadna DB),
// stejny princip jako scripts/2026-10-06_john_panel_testy/harness.js. Falesne je GET /api/admin/ucetni-emaily a PUT /api/admin/ucetni-emaily/<kod> (stav.typy, stav.puts).
// Kandidat pred nasazenim (nic se nezapise do zivych souboru):  ADMIN_HTML=<kandidat>/admin.html JS_DIR=<kandidat>/js node test_ucetni_emaily_panel.js
const { chromium } = require('/opt/konfigurator/node_modules/playwright');
const fs = require('fs');
const path = require('path');

const REPO = path.join(__dirname, '../..');
const ADMIN_HTML = process.env.ADMIN_HTML || path.join(REPO, 'webapp/admin.html');
const JS_DIR = process.env.JS_DIR || path.join(REPO, 'webapp/admin/js');
const QUILL_ATRAPA = `window.Quill = function Quill() {}; Quill.__icons = {}; Quill.import = function (n) { return n === 'ui/icons' ? Quill.__icons : class BlockEmbed { static create() { return document.createElement('div'); } }; }; Quill.register = function () {};`;

const TYPY = () => [
  { kod: 'invoice', nazev: 'Faktura - Daňový doklad', smer: 'vydany', adresy: [], aktivni: false, poznamka: '', upraveno: null, upravil: null },
  { kod: 'proforma_invoice', nazev: 'Zálohová faktura', smer: 'vydany', adresy: [], aktivni: false, poznamka: '', upraveno: null, upravil: null },
  { kod: 'payment_tax_document', nazev: 'Daňový doklad k přijaté platbě', smer: 'vydany', adresy: [], aktivni: false, poznamka: '', upraveno: null, upravil: null },
  { kod: 'credit_note', nazev: 'Dobropis', smer: 'vydany', adresy: [], aktivni: false, poznamka: '', upraveno: null, upravil: null },
  { kod: 'delivery_note', nazev: 'Dodací list', smer: 'vydany', adresy: [], aktivni: false, poznamka: '', upraveno: null, upravil: null },
  { kod: 'prijaty_doklad', nazev: 'Přijaté doklady (od dodavatelů)', smer: 'prijaty', adresy: [], aktivni: false, poznamka: '', upraveno: null, upravil: null },
];

// opts: { user: {role, permissions, name}, typy, zapojeno, emails (odpoved GET /api/admin/emails), get: {__status}|{__raw}|{__abort}|{__body}, viewport, hash, putHandler(kod, body, stav) -> {status, body}|undefined, putDelay (ms) }
async function otevriAdmin(opts) {
  opts = opts || {};
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: opts.viewport || { width: 1300, height: 900 }, locale: 'cs-CZ' });
  const page = await ctx.newPage();
  const chyby = [], pozadavky = { get: 0, put: 0 };
  const stav = { typy: opts.typy || TYPY(), zapojeno: opts.zapojeno === true, max: 5, get: opts.get || null, puts: [], emailsDotazy: [], putHandler: opts.putHandler || null, putDelay: opts.putDelay || 0, dialogy: [] };
  page.on('pageerror', e => chyby.push(String(e.message)));
  page.on('console', m => { if (m.type() === 'error' && !/Failed to load resource/.test(m.text())) chyby.push('console: ' + m.text().slice(0, 200)); });
  page.on('dialog', d => { stav.dialogy.push({ typ: d.type(), text: d.message() }); if (stav.dialogOdpoved === false) d.dismiss(); else d.accept(); });
  await page.route('**/*', async route => {
    const req = route.request(), u = new URL(req.url());
    if (u.hostname === 'cdn.jsdelivr.net' && /quill@1\.3\.7\/dist\/quill\.min\.js$/.test(u.pathname)) return route.fulfill({ status: 200, contentType: 'application/javascript', body: QUILL_ATRAPA });
    if (u.hostname === 'cdn.jsdelivr.net' && /\.css$/.test(u.pathname)) return route.fulfill({ status: 200, contentType: 'text/css', body: '' });
    if (u.hostname !== 'admin.test') return route.abort();
    const p = u.pathname, m = req.method();
    const json = (status, body) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });
    if (p === '/admin.html') return route.fulfill({ status: 200, contentType: 'text/html; charset=utf-8', body: fs.readFileSync(ADMIN_HTML, 'utf8') });
    const mJs = /^\/admin\/js\/([A-Za-z0-9_.-]+\.js)$/.exec(p);
    if (mJs) {
      const cesta = path.join(JS_DIR, mJs[1]);
      if (!fs.existsSync(cesta)) return route.fulfill({ status: 404, body: 'nenalezeno' });
      return route.fulfill({ status: 200, contentType: 'application/javascript; charset=utf-8', body: fs.readFileSync(cesta, 'utf8') });
    }
    if (p === '/api/admin/ucetni-emaily' && m === 'GET') {
      pozadavky.get++;
      const g = stav.get;
      if (g && g.__abort) return route.abort('failed');
      if (g && g.__status) return json(g.__status, { error: 'x' });
      if (g && g.__raw !== undefined) return route.fulfill({ status: 200, contentType: 'application/json', body: g.__raw });
      if (g && g.__body !== undefined) return json(200, g.__body);
      return json(200, { typy: JSON.parse(JSON.stringify(stav.typy)), max_adres: stav.max, odesilani_zapojeno: stav.zapojeno });
    }
    if (p === '/api/admin/emails' && m === 'GET') { stav.emailsDotazy.push(u.search); return json(200, opts.emails || { emails: [], counts: { all: 0 }, status_counts: {}, total: 0, page: 1, page_size: 50 }); }
    const mP = /^\/api\/admin\/ucetni-emaily\/([A-Za-z0-9_%-]+)$/.exec(p);
    if (mP && m === 'PUT') {
      pozadavky.put++;
      const kod = decodeURIComponent(mP[1]);
      let body = null; try { body = JSON.parse(req.postData() || 'null'); } catch (e) { /* nic */ }
      stav.puts.push({ kod, body, ctype: req.headers()['content-type'] || '' });
      if (stav.putDelay) await new Promise(r => setTimeout(r, stav.putDelay));
      if (stav.putHandler) { const x = stav.putHandler(kod, body, stav); if (x) return x.abort ? route.abort('failed') : (x.raw !== undefined ? route.fulfill({ status: x.status, contentType: 'text/html', body: x.raw }) : json(x.status, x.body)); }
      const t = stav.typy.find(x => x.kod === kod);
      if (!t) return json(404, { error: 'typ_neznamy', message: 'Neznámý typ dokladu.' });
      const adresy = []; ((body && body.adresy) || []).forEach(a => { a = String(a).trim().toLowerCase(); if (a && adresy.indexOf(a) < 0) adresy.push(a); });
      Object.assign(t, { adresy, aktivni: !!(body && body.aktivni), poznamka: String((body && body.poznamka) || ''), upraveno: new Date().toISOString(), upravil: 'Test Admin' });
      return json(200, { ok: true, radek: JSON.parse(JSON.stringify(t)) });
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
module.exports = { otevriAdmin, TYPY };
