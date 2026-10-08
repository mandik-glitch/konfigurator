// Harness online nabidky pro testy montaze a rucnich polozek (bot8, 2026-10-06): SKUTECNA stranka webapp/nabidka-online.html v Chromiu proti FALESNEMU serveru (page.route, zadna
// sit, zadna DB, nic se nezapisuje). Odvozeno z scripts/2026-10-01_nabidka_tabulka_cen_testy/harness_nabidka.js (bot5) - navic: mista montaze (/api/montaz-mista), zachyceni POSTu voleb
// objednavky (order-prefs), vlastni routy (item-image, item-model...) pres `trasy`, kandidat stranky NABIDKA_HTML=/cesta/k/nabidka-online.html.
const { chromium } = require('/opt/konfigurator/node_modules/playwright-core');
const fs = require('fs');
const path = require('path');

const REPO = path.join(__dirname, '../..');
const NABIDKA_HTML = process.env.NABIDKA_HTML || path.join(REPO, 'webapp/nabidka-online.html');
const VZOR = path.join(REPO, 'scripts/2026-10-01_nabidka_tabulka_cen_testy/ukazka_nabidky.json');
const PNG = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==', 'base64');
const MISTA = [{ klic: 'praha', nazev: 'Praha' }, { klic: 'slavicin', nazev: 'Slavičín' }];

function vzorovaNabidka(uprava) {
  const d = JSON.parse(fs.readFileSync(VZOR, 'utf8'));
  return uprava ? uprava(d) || d : d;
}

// trasy(route, {p, m, json}) -> true, kdyz trasu obslouzil
async function otevriNabidku({ width = 1440, height = 900, nabidka = null, mista = MISTA, trasy = null, mobil = false, initScript = null, cdn = false } = {}) {
  const data = nabidka || vzorovaNabidka();
  const chyby = [], posty = [];
  const browser = await chromium.launch({ args: ['--no-sandbox'] });
  const ctx = await browser.newContext({ viewport: { width, height }, hasTouch: !!mobil, isMobile: !!mobil, deviceScaleFactor: 1 });
  const page = await ctx.newPage();
  page.on('pageerror', e => chyby.push(e.message));
  if (initScript) await page.addInitScript(initScript);
  await page.route('**/*', async route => {
    const req = route.request();
    const u = new URL(req.url());
    if (cdn && u.hostname === 'cdn.jsdelivr.net') return route.continue();          // skutecny 3D prohlizec (THREE z CDN) - jen pro vizualni test
    if (u.hostname !== 'nab.test') return route.abort();
    const p = u.pathname, m = req.method();
    const json = (status, body) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });
    if (p === '/nabidka-online.html') return route.fulfill({ status: 200, contentType: 'text/html; charset=utf-8', body: fs.readFileSync(NABIDKA_HTML, 'utf8') });
    if (p === '/api/public/offers/TESTTOKEN' && m === 'GET') return json(200, data);
    if (p === '/api/public/offers/TESTTOKEN/order-prefs' && m === 'POST') { posty.push(JSON.parse(req.postData() || '{}')); return json(200, { status: 'ok' }); }
    if (trasy && await trasy(route, { p, m, json, req })) return;
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
    await page.waitForTimeout(500);
  } catch (e) {
    throw new Error('harness: nabidka se nenacetla. ' + e.message.split('\n')[0] + '\n  chyby stranky: ' + chyby.slice(0, 5).join(' | '));
  }
  return { browser, page, chyby, posty };
}

// proklika "Dalsi" az na stranku s cenovou tabulkou
async function naCenovouStranku(page) {
  for (let i = 0; i < 14; i++) {
    if (await page.evaluate(() => !!document.querySelector('.slide.active table.items'))) break;
    await page.click('#btnNext');
    await page.waitForTimeout(450);
  }
  await page.waitForSelector('.slide.active table.items', { timeout: 5000 });
  await page.waitForTimeout(400);
}

const cislo = s => Number(String(s || '').replace(/[^\d,]/g, '').replace(',', '.'));
module.exports = { otevriNabidku, naCenovouStranku, vzorovaNabidka, MISTA, cislo, PNG };
