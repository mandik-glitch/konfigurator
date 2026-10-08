// Harness online nabidky (webapp/nabidka-online.html): SKUTECNA stranka v Chromiu proti falesnemu serveru (page.route, zadna sit,
// zadna DB). Data nabidky se berou ze souboru (OFFER_JSON, ve stejnem tvaru jako GET /api/public/offers/<token>), ostatni
// endpointy vraci prazdne odpovedi. Kandidat pred nasazenim: NABIDKA_HTML=/cesta/k/nabidka-online.html
const { chromium } = require('/opt/konfigurator/node_modules/playwright-core');
const fs = require('fs');
const path = require('path');

const REPO = path.join(__dirname, '../..');
const NABIDKA_HTML = process.env.NABIDKA_HTML || path.join(REPO, 'webapp/nabidka-online.html');
const OFFER_JSON = process.env.OFFER_JSON || path.join(__dirname, 'ukazka_nabidky.json');
// 1x1 sedy PNG (obrazky nabidky - pro rozlozeni stranky nezalezi na obsahu)
const PNG = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==', 'base64');

async function otevriNabidku({ width = 1440, height = 900, nabidka = null, mobil = false, obrazky = null } = {}) {
  const data = nabidka || JSON.parse(fs.readFileSync(OFFER_JSON, 'utf8'));
  const chyby = [];
  const browser = await chromium.launch({ args: ['--no-sandbox'] });
  const ctx = await browser.newContext({ viewport: { width, height }, hasTouch: !!mobil, isMobile: !!mobil, deviceScaleFactor: 1 });
  const page = await ctx.newPage();
  page.on('pageerror', e => chyby.push(e.message));
  await page.route('**/*', async route => {
    const req = route.request();
    const u = new URL(req.url());
    if (u.hostname !== 'nab.test') return route.abort();
    const p = u.pathname, m = req.method();
    const json = (status, body) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });
    if (p === '/nabidka-online.html') return route.fulfill({ status: 200, contentType: 'text/html; charset=utf-8', body: fs.readFileSync(NABIDKA_HTML, 'utf8') });
    if (p === '/api/public/offers/TESTTOKEN' && m === 'GET') return json(200, data);
    const mImg = /^\/api\/public\/offers\/TESTTOKEN\/image\/([a-z0-9_]+)$/.exec(p);
    if (mImg && obrazky && obrazky[mImg[1]]) return route.fulfill({ status: 200, contentType: 'image/png', body: fs.readFileSync(obrazky[mImg[1]]) });   // skutecne vykresy (volitelne)
    if (/^\/api\/public\/offers\/TESTTOKEN\/(image|render)\//.test(p)) return route.fulfill({ status: 200, contentType: 'image/png', body: PNG });
    if (p === '/api/theme-colors') return json(200, { light: {}, dark: {} });
    if (p === '/api/montaz-mista') return json(200, { mista: [] });
    if (p.startsWith('/api/')) return json(200, m === 'GET' ? {} : { status: 'ok' });
    return route.fulfill({ status: 404, body: '' });
  });
  await page.goto('http://nab.test/nabidka-online.html?t=TESTTOKEN');
  try {
    await page.waitForSelector('#deck.show', { timeout: 15000 });
    await page.waitForTimeout(500);
  } catch (e) {
    throw new Error('harness: nabidka se nenacetla. ' + e.message.split('\n')[0] + '\n  chyby stranky: ' + chyby.slice(0, 5).join(' | '));
  }
  return { browser, page, chyby };
}

// proklika "Dalsi" az na stranku s cenovou tabulkou
async function naCenovouStranku(page) {
  for (let i = 0; i < 12; i++) {
    if (await page.evaluate(() => !!document.querySelector('.slide.active table.items'))) break;
    await page.click('#btnNext');
    await page.waitForTimeout(450);
  }
  await page.waitForSelector('.slide.active table.items', { timeout: 5000 });
  await page.waitForTimeout(400);
}

module.exports = { otevriNabidku, naCenovouStranku };
