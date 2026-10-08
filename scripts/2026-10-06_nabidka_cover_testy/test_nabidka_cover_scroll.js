// Online nabidka: PRVNI STRANA (cover) nesmi mit fantomni rolovaci plochu (bot16, 2026-10-06).
// Robert: "v online nabidce je 1 strana s velkym prazdnym prostorem vespod, kolecko mysi dovoli jit tak ze je videt cela prazdna obrazovka" - "prvni strana".
// PRICINA: skenovaci linka `.cover::after` byla 120px prvek animovany `transform: translateY(-100% .. 2400%)` (az 2880 px dolu); `.cover` je zaroven rolovaci kontejner
// (`.slide { overflow-y:auto }`), takze animovany prvek natahoval rolovaci vysku o tisice px prazdna (a kolecko mysi nepustilo na dalsi stranu, viz slideScrollEdges/wheel).
// OPRAVA: linka se posouva jen pozadim (background-position) uvnitr prvku o velikosti obrazovky (inset:0) a jen na aktivni strane.
// SKUTECNA stranka webapp/nabidka-online.html v Chromiu proti falesnemu serveru (page.route, zadna DB, zadna sit), data = fixture nabidky z konfigurace (kopie Robertovy nabidky) a ukazka_nabidky.json (starsi typ).
// Spusteni: node test_nabidka_cover_scroll.js     Kandidat pred nasazenim: NABIDKA_HTML=/cesta/nabidka-online.html node test_nabidka_cover_scroll.js
const { chromium } = require('/opt/konfigurator/node_modules/playwright-core');
const fs = require('fs');
const path = require('path');

const REPO = path.join(__dirname, '../..');
const WEB = path.join(REPO, 'webapp');
const HTML = fs.readFileSync(process.env.NABIDKA_HTML || path.join(WEB, 'nabidka-online.html'), 'utf8');
const FIXTURY = {
  'z konfigurace': JSON.parse(fs.readFileSync(path.join(__dirname, 'fixture_nabidka_z_konfigurace.json'), 'utf8')),
  'starsi typ (ukazka)': JSON.parse(fs.readFileSync(path.join(REPO, 'scripts/2026-10-01_nabidka_tabulka_cen_testy/ukazka_nabidky.json'), 'utf8')),
};
const PNG = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==', 'base64');
const TYPY = { '.html': 'text/html; charset=utf-8', '.js': 'application/javascript', '.css': 'text/css', '.json': 'application/json', '.svg': 'image/svg+xml', '.png': 'image/png', '.hdr': 'application/octet-stream' };
const vysl = [];
const over = (nazev, podminka, detail) => { vysl.push(!!podminka); console.log((podminka ? 'OK   ' : 'FAIL ') + nazev + (podminka ? '' : '  -> ' + JSON.stringify(detail))); };
const ceka = ms => new Promise(r => setTimeout(r, ms));

// puvodni (chybne) pravidlo pro mutacni zkousku: test musi spadnout, kdyz se vrati
const STARE_KEYFRAMES = '@keyframes hudScan { 0% { transform:translateY(-100%); } 100% { transform:translateY(2400%); } }';
function mutaceStaraLinka(html) {
  let h = html.replace(/@keyframes hudScan \{[^\n]*\}[^\n]*\n/, STARE_KEYFRAMES + '\n');
  h = h.replace(/\.cover::after \{[\s\S]*?\n  \}\n  \.cover\.active::after \{[^\n]*\}/, '.cover::after { content: ""; position: absolute; left: 0; right: 0; height: 120px; pointer-events: none; background: linear-gradient(180deg, transparent 0%, rgba(47,224,122,.09) 45%, transparent 100%); animation: hudScan 8s linear infinite; }');
  return h;
}

async function otevri(browser, html, offer, w, h) {
  const ctx = await browser.newContext({ viewport: { width: w, height: h }, locale: 'cs-CZ' });
  const page = await ctx.newPage(); const chyby = [];
  page.on('pageerror', e => chyby.push(e.message));
  await page.route('**/*', route => {
    const u = new URL(route.request().url());
    if (u.hostname !== 'nab.test') return route.abort();
    const p = u.pathname, json = b => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(b) });
    if (p === '/nabidka-online.html') return route.fulfill({ status: 200, contentType: 'text/html; charset=utf-8', body: html });
    if (p === '/api/public/offers/TESTTOKEN') return json(offer);
    if (p.startsWith('/api/public/offers/TESTTOKEN/image/')) return route.fulfill({ status: 200, contentType: 'image/png', body: PNG });
    if (p.startsWith('/api/public/offers/TESTTOKEN/model')) return route.fulfill({ status: 404, body: 'nf' });
    if (p === '/api/montaz-mista') return json({ mista: [{ klic: 'praha', nazev: 'Praha' }] });
    if (p.startsWith('/api/')) return json({});
    const f = path.join(WEB, p === '/' ? 'index.html' : p);
    if (f.startsWith(WEB) && fs.existsSync(f) && fs.statSync(f).isFile()) return route.fulfill({ status: 200, contentType: TYPY[path.extname(f)] || 'application/octet-stream', body: fs.readFileSync(f) });
    return route.fulfill({ status: 404, body: 'nf' });
  });
  await page.goto('http://nab.test/nabidka-online.html?t=TESTTOKEN', { waitUntil: 'load' });
  await page.waitForSelector('#deck .slide.active', { timeout: 20000 });
  await page.waitForTimeout(600);
  return { ctx, page, chyby };
}
const vyska = page => page.evaluate(() => { const s = document.querySelector('#deck .slide.cover'); return { sh: s.scrollHeight, ch: s.clientHeight, dno: Math.ceil(s.querySelector('.slide-inner').getBoundingClientRect().bottom - s.getBoundingClientRect().top + s.scrollTop) }; });

(async () => {
  const browser = await chromium.launch({ args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  const VIEWPORTY = [[1400, 900], [1920, 950], [2560, 1300], [390, 800]];

  console.log('== A) rolovaci plocha prvni strany je po CELY cyklus animace (8 s) stejna a konci u obsahu');
  for (const [nazevF, offer] of Object.entries(FIXTURY)) {
    for (const [w, h] of VIEWPORTY) {
      const { ctx, page, chyby } = await otevri(browser, HTML, offer, w, h);
      const v = [];
      for (let i = 0; i < 20; i++) { v.push(await vyska(page)); await ceka(450); }
      const sh = v.map(x => x.sh), dno = Math.max(v[0].dno, v[0].ch);                  // plocha = obsah, nebo aspon vyska okna (kratka strana)
      over(`A ${nazevF} ${w}x${h}: scrollHeight 1. strany se behem 9 s nemeni (min ${Math.min(...sh)}, max ${Math.max(...sh)}) a nepresahuje obsah / vysku okna (${dno})`, Math.max(...sh) - Math.min(...sh) <= 1 && Math.max(...sh) <= dno + 2, { sh: sh.join(','), dno });
      over(`A ${nazevF} ${w}x${h}: zadne chyby JS ve strance`, chyby.length === 0, chyby.slice(0, 2));
      await ctx.close();
    }
  }

  console.log('== B) skenovaci linka zustala (animace bezi na aktivni strane, jen pozadim; na skryte strane nebezi)');
  {
    const { ctx, page } = await otevri(browser, HTML, FIXTURY['z konfigurace'], 1920, 950);
    const a1 = await page.evaluate(() => { const s = document.querySelector('#deck .slide.cover'), c = getComputedStyle(s, '::after'); return { jmeno: c.animationName, poz: c.backgroundPosition, pos: c.position, vyska: c.height, aktivni: s.classList.contains('active') }; });
    await ceka(900);
    const a2 = await page.evaluate(() => getComputedStyle(document.querySelector('#deck .slide.cover'), '::after').backgroundPosition);
    over('B aktivni 1. strana: animace hudScan bezi a linka se posouva (background-position se meni)', a1.aktivni && a1.jmeno === 'hudScan' && a1.poz !== a2, { a1, a2 });
    over('B pseudoprvek ma velikost obrazovky (inset:0, ne 120 px s transformem)', a1.pos === 'absolute' && parseInt(a1.vyska, 10) >= 800, a1);
    await page.keyboard.press('ArrowRight'); await ceka(900);
    const b = await page.evaluate(() => getComputedStyle(document.querySelector('#deck .slide.cover'), '::after').animationName);
    over('B po prechodu na dalsi stranu animace na skryte titulni strane nebezi (zadna prace navic)', b === 'none', b);
    await page.keyboard.press('ArrowLeft'); await ceka(900);
    over('B po navratu na 1. stranu animace bezi znovu', (await page.evaluate(() => getComputedStyle(document.querySelector('#deck .slide.cover'), '::after').animationName)) === 'hudScan');
    await ctx.close();
  }

  console.log('== C) kolecko mysi: kratka prvni strana pusti na dalsi stranu hned (nebo po dorolovani vlastniho obsahu), ne po prazdne obrazovce');
  for (const [nazevF, offer] of Object.entries(FIXTURY)) {
    for (const [w, h] of [[2560, 1300], [1920, 950]]) {
      const { ctx, page } = await otevri(browser, HTML, offer, w, h);
      await page.mouse.move(w / 2, h / 2);
      const info0 = await vyska(page); const potrebnoRoli = info0.sh > info0.ch ? Math.ceil((info0.sh - info0.ch) / 400) : 0;
      let udalosti = 0, idx = 0;
      for (let i = 0; i < 6 && idx === 0; i++) {
        await page.mouse.wheel(0, 400); udalosti++; await ceka(900);
        idx = await page.evaluate(() => [...document.querySelectorAll('#deck .slide')].findIndex(s => s.classList.contains('active')));
      }
      over(`C ${nazevF} ${w}x${h}: dalsi stranu otevre ${udalosti}. kolecko (vlastni obsah vyzaduje ${potrebnoRoli} + 1 prechod)`, idx === 1 && udalosti <= potrebnoRoli + 1, { udalosti, idx, info0 });
      await ctx.close();
    }
  }

  console.log('== D) mutace stranky: stara skenovaci linka (transform) - test ji MUSI zachytit');
  {
    const mut = mutaceStaraLinka(HTML);
    over('D mutace byla opravdu aplikovana (stranka obsahuje translateY(2400%))', mut !== HTML && /translateY\(2400%\)/.test(mut));
    const { ctx, page } = await otevri(browser, mut, FIXTURY['z konfigurace'], 1920, 950);
    const sh = [];
    for (let i = 0; i < 20; i++) { sh.push((await vyska(page)).sh); await ceka(450); }
    over('D se starou linkou by kontrola A selhala (rolovaci vyska kolisa: min ' + Math.min(...sh) + ', max ' + Math.max(...sh) + ')', Math.max(...sh) - Math.min(...sh) > 300, sh);
    await ctx.close();
  }

  await browser.close();
  console.log(`\nVYSLEDEK prvni strana online nabidky: ${vysl.filter(Boolean).length}/${vysl.length} OK`);
  process.exit(vysl.every(Boolean) ? 0 : 1);
})();
