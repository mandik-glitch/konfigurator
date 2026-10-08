// Test stranky pro schvalovani textu mini-shopu (mobil): SKUTECNA webapp/miniweb-schvaleni.html (nebo kandidat SCHVALENI_HTML) v Chromiu proti falesnemu serveru (page.route, zadna sit, zadna DB).
// Spusteni: node test_miniweb_schvaleni.js            (konci kodem 0 jen kdyz VSE prosla; snimky obrazovky do SNIMKY_DIR, vychozi scratchpad/tmp)
// Kandidat pred nasazenim: SCHVALENI_HTML=.../miniweb-schvaleni.html node test_miniweb_schvaleni.js
// Cast F: pravni dokumenty (karta, nahled a rozbaleni dlouheho textu, zastupne znacky nejdou schvalit, schvaleni, bezpecne zobrazeni) a mutace stranky (kazda musi test shodit).
const { chromium } = require('/opt/konfigurator/node_modules/playwright-core');
const fs = require('fs');
const os = require('os');
const path = require('path');

const REPO = path.join(__dirname, '../..');
const ZIVA = path.join(REPO, 'webapp/miniweb-schvaleni.html');
const HTML_CESTA = process.env.SCHVALENI_HTML || (fs.existsSync(ZIVA) ? ZIVA : path.join(__dirname, 'nasazeni/miniweb-schvaleni.html'));
const HTML = fs.readFileSync(HTML_CESTA, 'utf8');
const SNIMKY = process.env.SNIMKY_DIR || path.join(os.tmpdir(), 'miniweb_schvaleni_snimky');
fs.mkdirSync(SNIMKY, { recursive: true });
const ORIGIN = 'http://test.local';

const vysl = [];
const over = (nazev, podminka, detail) => {
  vysl.push(!!podminka);
  console.log((podminka ? 'OK   ' : 'FAIL ') + nazev + (podminka ? '' : '  -> ' + JSON.stringify(detail)));
};

let dalsiRev = 1;
const rev = () => (dalsiRev++).toString(16).padStart(16, '0');
function polozka(kind, id, o = {}) {
  return Object.assign({
    kind, id, lang: 'en', family: 'packstations', status: 'draft', slug: kind + '-' + id, sku: kind === 'product' ? 'PS-' + id : null, category: kind === 'product' ? 'Packing stations' : null,
    name: kind + ' ' + id, summary: '', description: '', delivery: '', specs: [], rev: rev(), blocking: [], info: [], active: true, public: false, approved_at: null, updated_at: '2026-10-02 12:00:00',
  }, o);
}
function zakladniData() {
  return {
    shops: [{ storefront_id: 1, slug: 'packstations-en', domain: 'packstations.example.top', status: 'draft', lang: 'en', family: 'packstations', price_mode: 'hidden', inquiry_enabled: true }],
    items: [
      polozka('category', 1, { name: 'Tables', status: 'approved', public: true }),
      polozka('category', 2, { name: 'Packing stations' }),
      polozka('product', 10, { name: 'Packing station PS-120', summary: 'Height-adjustable packing table', description: 'Robust aluminium frame.\n\nSecond paragraph & more.', delivery: '3-4 weeks',
        specs: [{ name: 'Width', value: '1200 mm' }, { name: 'Load', value: '150 kg' }] }),
      polozka('product', 11, { name: 'Table with a brand', description: 'Made by somebody', blocking: ['brand'] }),
      polozka('product', 12, { name: 'Work table WT-100', status: 'approved', description: 'Plain.', public: false, info: ['cleaned'] }),
    ],
  };
}
const spocti = d => { d.langs = [...new Set(d.items.map(i => i.lang))].sort(); d.counts = { draft: d.items.filter(i => i.status === 'draft').length, approved: d.items.filter(i => i.status === 'approved').length, blocked: d.items.filter(i => i.blocking.length).length, public: d.items.filter(i => i.public).length }; return d; };

async function otevri(opts = {}) {
  const stav = { data: spocti(opts.data || zakladniData()), posty: [], pozadavky: [], me: opts.me === undefined ? { status: 200, body: { user: { id: 1, role: 'admin', name: 'Robert' } } } : opts.me,
                 overviewStatus: opts.overviewStatus || 200, postStatus: null, hook: null };
  const browser = await chromium.launch({ args: ['--no-sandbox'] });
  const ctx = await browser.newContext({ viewport: opts.viewport || { width: 390, height: 844 }, isMobile: opts.isMobile !== false, hasTouch: opts.isMobile !== false, colorScheme: opts.colorScheme || 'light', deviceScaleFactor: 2 });
  const page = await ctx.newPage();
  const chyby = [];
  page.on('pageerror', e => chyby.push('pageerror: ' + e.message));
  page.on('console', m => { if (m.type() === 'error') chyby.push('console: ' + m.text()); });
  const neznama = [];
  await page.route('**/*', async route => {
    const u = new URL(route.request().url());
    const cesta = u.pathname, metoda = route.request().method();
    stav.pozadavky.push(metoda + ' ' + cesta);
    const json = (status, body) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });
    if (cesta === '/miniweb-schvaleni.html') return route.fulfill({ status: 200, contentType: 'text/html; charset=utf-8', body: opts.html || HTML });
    if (cesta === '/login.html') return route.fulfill({ status: 200, contentType: 'text/html', body: '<title>login</title>' });
    if (cesta === '/api/auth/me') return json(stav.me.status, stav.me.body);
    if (cesta === '/api/admin/miniweb/overview' && metoda === 'GET') return stav.overviewStatus === 200 ? json(200, spocti(stav.data)) : json(stav.overviewStatus, { error: 'x' });
    if ((cesta === '/api/admin/miniweb/approve' || cesta === '/api/admin/miniweb/unapprove') && metoda === 'POST') {
      const body = JSON.parse(route.request().postData());
      stav.posty.push({ cesta, body });
      if (stav.hook) stav.hook(cesta, body);
      if (stav.postStatus) return json(stav.postStatus, { error: 'x' });
      const out = { status: 'ok', changed: 0, skipped: [] };
      for (const it of body.items) {
        const r = stav.data.items.find(i => i.kind === it.kind && i.id === it.id && i.lang === it.lang);
        const ref = { kind: it.kind, id: it.id, lang: it.lang };
        if (!r) { out.skipped.push({ ...ref, reason: 'not_found' }); continue; }
        if (cesta.endsWith('/approve')) {
          if (r.blocking.length) out.skipped.push({ ...ref, reason: 'blocked' });
          else if (r.rev !== it.rev) out.skipped.push({ ...ref, reason: 'changed' });
          else if (r.status === 'approved') out.skipped.push({ ...ref, reason: 'already' });
          else { r.status = 'approved'; out.changed++; }
        } else if (r.status !== 'approved') out.skipped.push({ ...ref, reason: 'already' });
        else { r.status = 'draft'; out.changed++; }
      }
      const kat = new Set(stav.data.items.filter(i => i.kind === 'category' && i.status === 'approved').map(i => i.lang));
      stav.data.items.forEach(i => { i.public = i.status === 'approved' && (i.kind === 'category' || kat.has(i.lang)); });
      return json(200, out);
    }
    neznama.push(metoda + ' ' + u.href);
    return route.abort();
  });
  await page.goto(ORIGIN + '/miniweb-schvaleni.html');
  return { browser, page, stav, chyby, neznama };
}
const text = (page, sel) => page.evaluate(s => { const e = document.querySelector(s); return e ? e.textContent.trim().replace(/\s+/g, ' ') : null; }, sel);
const vsechnyTexty = page => page.evaluate(() => document.getElementById('app').innerText.replace(/\s+/g, ' '));
const klik = async (page, tvar, jmeno) => { await page.getByRole(tvar, { name: jmeno }).first().click(); };
const pockej = (page, fn, arg) => page.waitForFunction(fn, arg, { timeout: 5000 });
const jmenaKaret = page => page.evaluate(() => [...document.querySelectorAll('article h2')].map(e => e.textContent.trim()));

(async () => {
  // ---------------------------------------------------------------- A) brana
  {
    const t = await otevri({ me: { status: 401, body: { user: null } } });
    await pockej(t.page, () => document.querySelector('a.btn'));
    const odkaz = await t.page.evaluate(() => document.querySelector('a.btn').getAttribute('href'));
    over('A1 neprihlaseny: vyzva k prihlaseni s odkazem /login.html?next=/miniweb-schvaleni.html, prehled se vubec nenacita', /Přihlásit se/.test(await vsechnyTexty(t.page)) && odkaz === '/login.html?next=%2Fminiweb-schvaleni.html'
         && !t.stav.pozadavky.includes('GET /api/admin/miniweb/overview'), { odkaz, p: t.stav.pozadavky });
    await t.browser.close();
  }
  {
    const t = await otevri({ me: { status: 200, body: { user: { id: 2, role: 'manager' } } } });
    await pockej(t.page, () => document.querySelector('.msg'));
    over('A2 prihlaseny bez role admin: srozumitelna hlaska, prehled se nenacita, zadna tlacitka schvaleni', /jen administrátor/.test(await vsechnyTexty(t.page)) && !t.stav.pozadavky.includes('GET /api/admin/miniweb/overview')
         && (await t.page.$$('button')).length === 0, t.stav.pozadavky);
    await t.browser.close();
  }
  // ---------------------------------------------------------------- B) prehled
  {
    const t = await otevri();
    await pockej(t.page, () => document.querySelector('article'));
    const vse = await vsechnyTexty(t.page);
    const nahled = await t.page.evaluate(() => [...document.querySelectorAll('a.btn')].map(a => a.getAttribute('href')));
    over('B1 prehled: nazev stranky, shop (domena, koncept, bez cen), odkaz na nahled se shop/lang/drafts, vysvetleni ze schvaleni shop nezverejnuje',
         (await text(t.page, 'h1')) === 'Schvalování textů shopu' && /packstations\.example\.top/.test(vse) && /koncept/.test(vse) && /bez cen/.test(vse) && nahled.includes('/miniweb/index.html?shop=packstations-en&lang=en&drafts=1')
         && /zákazníkům se nic neukazuje/.test(vse) && /shop se spouští zvlášť/.test(await text(t.page, 'p.muted')), vse.slice(0, 300));
    over('B2 vychozi filtr "Čeká na schválení": jen navrhy (kategorie, 2 produkty), schvaleny produkt a kategorie se neukazuji; pocty ve filtrech 3 / 2 / 5',
         JSON.stringify(await jmenaKaret(t.page)) === JSON.stringify(['Packing stations', 'Packing station PS-120', 'Table with a brand']) && /Čeká na schválení \(3\)/.test(vse) && /Schváleno \(2\)/.test(vse) && /Vše \(5\)/.test(vse), await jmenaKaret(t.page));
    const ps = await t.page.evaluate(() => { const a = [...document.querySelectorAll('article')].find(x => x.querySelector('h2').textContent === 'Packing station PS-120'); return { t: a.innerText.replace(/\s+/g, ' '), pre: getComputedStyle(a.querySelector('.desc')).whiteSpace, tlac: [...a.querySelectorAll('button')].map(b => b.textContent.trim()) }; });
    over('B3 karta produktu: kod, kategorie, souhrn, popis s odstavci (white-space pre-line), dodani, parametry; tlacitko Schvalit', /PS-10/.test(ps.t) && /Packing stations/.test(ps.t) && /Height-adjustable packing table/.test(ps.t) && /Dodání: 3-4 weeks/.test(ps.t) && /Width 1200 mm/.test(ps.t)
         && ps.pre === 'pre-line' && JSON.stringify(ps.tlac) === JSON.stringify(['Schválit']), ps);
    const br = await t.page.evaluate(() => { const a = [...document.querySelectorAll('article')].find(x => x.querySelector('h2').textContent === 'Table with a brand'); return { t: a.innerText.replace(/\s+/g, ' '), tlac: a.querySelectorAll('button').length, cls: a.className }; });
    over('B4 text se znackou: "Nelze schválit", vysvetleni co s tim, ZADNE tlacitko schvaleni', /Nelze schválit/.test(br.t) && /značku nebo dodavatele/.test(br.t) && br.tlac === 0 && /is-blocked/.test(br.cls), br);
    await klik(t.page, 'button', /Schváleno \(2\)/);
    const sch = await t.page.evaluate(() => [...document.querySelectorAll('article')].map(a => ({ n: a.querySelector('h2').textContent, t: a.innerText.replace(/\s+/g, ' '), tlac: [...a.querySelectorAll('button')].map(b => b.textContent.trim()) })));
    over('B5 filtr "Schváleno": tabulky s "Vrátit do návrhu"; schválený produkt, který zatím není veřejný, nese upozornění na nadřazené kategorie; schválená kategorie ho nemá',
         sch.length === 2 && sch.every(s => JSON.stringify(s.tlac) === JSON.stringify(['Vrátit do návrhu'])) && /nebylo veřejné/.test(sch.find(s => s.n === 'Work table WT-100').t) && !/nebylo veřejné/.test(sch.find(s => s.n === 'Tables').t)
         && /vyčištěno|odstraněno HTML/.test(sch.find(s => s.n === 'Work table WT-100').t), sch);
    over('B6 stranka nema horizontalni posun, zadna chyba v konzoli a zadny neznamy pozadavek', await t.page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth) && t.chyby.length === 0 && t.neznama.length === 0, { chyby: t.chyby, neznama: t.neznama });
    await t.browser.close();
  }
  // ---------------------------------------------------------------- C) schvaleni
  {
    const t = await otevri();
    await pockej(t.page, () => document.querySelector('article'));
    const cil = t.stav.data.items.find(i => i.id === 10);
    await t.page.evaluate(() => { [...document.querySelectorAll('article')].find(x => x.querySelector('h2').textContent === 'Packing station PS-120').querySelector('button.primary').click(); });
    await pockej(t.page, () => document.querySelector('.msg'));
    over('C1 Schvalit u jedne karty: odejde PRESNE tato polozka s otiskem, ktery stranka videla (kind, id, lang, rev), a nic jineho; po obnoveni karta z navrhu zmizi a je hlaska "Schváleno: 1 text."',
         t.stav.posty.length === 1 && t.stav.posty[0].cesta === '/api/admin/miniweb/approve' && JSON.stringify(t.stav.posty[0].body) === JSON.stringify({ items: [{ kind: 'product', id: 10, lang: 'en', rev: cil.rev }] })
         && /Schváleno: 1 text\./.test(await text(t.page, '.msg')) && !(await jmenaKaret(t.page)).includes('Packing station PS-120') && /Čeká na schválení \(2\)/.test(await vsechnyTexty(t.page)), { posty: t.stav.posty, karty: await jmenaKaret(t.page) });
    await t.browser.close();
  }
  {
    const t = await otevri();
    await pockej(t.page, () => document.querySelector('article'));
    await klik(t.page, 'button', /Schválit všechny návrhy \(2\)/);
    const potvrzeni = await vsechnyTexty(t.page);
    const postyPred = t.stav.posty.length;
    over('C2 "Schválit všechny": nejdriv DVOUKROKOVE potvrzeni (kolik textu, v jakem jazyce, kdy je zakaznici uvidi), zatim se nic neodeslalo; pocet = jen schvalitelne (2, bez textu se znackou)',
         /Opravdu schválit 2 texty v jazyce EN/.test(potvrzeni) && /po spuštění shopu/.test(potvrzeni) && postyPred === 0, potvrzeni.slice(0, 400));
    await klik(t.page, 'button', /Zrušit/);
    over('C3 Zrusit: potvrzeni zmizi, nic se neodeslalo, tlacitko "Schválit všechny" je zpet', t.stav.posty.length === 0 && /Schválit všechny návrhy \(2\)/.test(await vsechnyTexty(t.page)), t.stav.posty);
    await klik(t.page, 'button', /Schválit všechny návrhy \(2\)/);
    await klik(t.page, 'button', /Ano, schválit/);
    await pockej(t.page, () => document.querySelector('.msg'));
    over('C4 po potvrzeni odejde JEDEN pozadavek s presne schvalitelnymi polozkami (kategorie 2 a produkt 10, ne text se znackou), hlaska "Schváleno: 2 texty."',
         t.stav.posty.length === 1 && JSON.stringify(t.stav.posty[0].body.items.map(i => i.id).sort()) === JSON.stringify([10, 2]) && !t.stav.posty[0].body.items.some(i => i.id === 11) && /Schváleno: 2 texty\./.test(await text(t.page, '.msg')), t.stav.posty);
    await t.browser.close();
  }
  {
    const t = await otevri();
    await pockej(t.page, () => document.querySelector('article'));
    t.stav.hook = () => { const r = t.stav.data.items.find(i => i.id === 10); r.rev = rev(); r.description = 'Zmeneno po zobrazeni'; };           // import zmeni text, nez Robert klikne
    await t.page.evaluate(() => { [...document.querySelectorAll('article')].find(x => x.querySelector('h2').textContent === 'Packing station PS-120').querySelector('button.primary').click(); });
    await pockej(t.page, () => document.querySelector('.msg'));
    const msg = await text(t.page, '.msg');
    const karta = await t.page.evaluate(() => [...document.querySelectorAll('article')].find(x => x.querySelector('h2').textContent === 'Packing station PS-120').innerText);
    t.stav.hook = null;
    await t.page.evaluate(() => { [...document.querySelectorAll('article')].find(x => x.querySelector('h2').textContent === 'Packing station PS-120').querySelector('button.primary').click(); });
    await pockej(t.page, () => /Schváleno: 1 text/.test(document.querySelector('.msg').textContent));
    over('C5 text se mezitim zmenil: NESCHVALI se, stranka to rekne ("mezitím změnil ... Zkontrolujte nové znění"), nacte nove zneni a po druhem kliknuti se schvali s novym otiskem',
         /mezitím změnil/.test(msg) && /Zkontrolujte nové znění/.test(msg) && /Zmeneno po zobrazeni/.test(karta) && t.stav.posty.length === 2 && t.stav.posty[1].body.items[0].rev === t.stav.data.items.find(i => i.id === 10).rev, { msg, posty: t.stav.posty });
    await t.browser.close();
  }
  {
    const t = await otevri();
    await pockej(t.page, () => document.querySelector('article'));
    t.stav.postStatus = 500;
    await t.page.evaluate(() => { [...document.querySelectorAll('article')].find(x => x.querySelector('h2').textContent === 'Packing station PS-120').querySelector('button.primary').click(); });
    await pockej(t.page, () => document.querySelector('.msg.bad'));
    over('C6 chyba serveru pri schvaleni: hlaska "nic se nezměnilo", karta zustane v navrzich a tlacitko je opet pouzitelne', /nic se nezměnilo/.test(await text(t.page, '.msg')) && (await jmenaKaret(t.page)).includes('Packing station PS-120')
         && await t.page.evaluate(() => ![...document.querySelectorAll('article button')].some(b => b.disabled)), await jmenaKaret(t.page));
    t.stav.postStatus = 401;
    await t.page.evaluate(() => { [...document.querySelectorAll('article')].find(x => x.querySelector('h2').textContent === 'Packing station PS-120').querySelector('button.primary').click(); });
    await pockej(t.page, () => /vypršelo/.test(document.querySelector('.msg').textContent));
    over('C7 vyprsene prihlaseni (401 pri schvaleni): hlaska, ze je treba se prihlasit znovu', /přihlaste se znovu/.test(await text(t.page, '.msg')), await text(t.page, '.msg'));
    await t.browser.close();
  }
  {
    const t = await otevri();
    await pockej(t.page, () => document.querySelector('article'));
    t.stav.postStatus = null;
    await klik(t.page, 'button', /Schváleno \(2\)/);
    await t.page.evaluate(() => { [...document.querySelectorAll('article')].find(x => x.querySelector('h2').textContent === 'Work table WT-100').querySelector('button').click(); });
    await pockej(t.page, () => document.querySelector('.msg'));
    over('C8 "Vrátit do návrhu": odejde zadost bez otisku (kind, id, lang), hlaska "Vráceno do návrhu: 1 text.", polozka je znovu mezi navrhy', t.stav.posty.length === 1 && t.stav.posty[0].cesta === '/api/admin/miniweb/unapprove'
         && JSON.stringify(t.stav.posty[0].body) === JSON.stringify({ items: [{ kind: 'product', id: 12, lang: 'en' }] }) && /Vráceno do návrhu: 1 text\./.test(await text(t.page, '.msg')), t.stav.posty);
    await t.browser.close();
  }
  // ---------------------------------------------------------------- D) bezpecnost zobrazeni, jazyky, prazdne stavy
  {
    const d = zakladniData();
    d.items.push(polozka('product', 20, { name: '<img src=x onerror="window.__xss=1">Evil', summary: '<script>window.__xss=2</script>', description: '"><svg onload=window.__xss=3>', specs: [{ name: '<b>n</b>', value: '<iframe src="javascript:window.__xss=4"></iframe>' }] }));
    const t = await otevri({ data: d });
    await pockej(t.page, () => document.querySelector('article'));
    const x = await t.page.evaluate(() => ({ xss: window.__xss, img: document.querySelectorAll('#app img, #app svg, #app iframe, #app script').length, jmeno: [...document.querySelectorAll('article h2')].map(e => e.textContent).find(s => /Evil/.test(s)) }));
    over('D1 obsah z databaze se vklada JEN jako text: HTML ve jmene, souhrnu, popisu i parametrech se zobrazi doslova, nic se nespusti a v DOM nevznikne zadny img, svg, iframe ani script', x.xss === undefined && x.img === 0 && x.jmeno.startsWith('<img src=x'), x);
    await t.browser.close();
  }
  {
    const d = zakladniData();
    d.items.push(polozka('product', 30, { lang: 'de', name: 'Packstation PS-120' }), polozka('product', 31, { lang: 'de', name: 'Arbeitstisch' }));
    const t = await otevri({ data: d });
    await pockej(t.page, () => document.querySelector('article'));
    const zalozky = await t.page.evaluate(() => [...document.querySelectorAll('[aria-label="Jazyk"] button')].map(b => b.textContent + ':' + b.getAttribute('aria-pressed')));
    const en = await jmenaKaret(t.page);
    await klik(t.page, 'button', /^DE$/);
    const de = await jmenaKaret(t.page);
    await klik(t.page, 'button', /Schválit všechny návrhy \(2\)/);
    await klik(t.page, 'button', /Ano, schválit/);
    await pockej(t.page, () => document.querySelector('.msg'));
    over('D2 vice jazyku: zalozky EN a DE (vychozi EN), kazdy jazyk ukazuje jen sve texty, hromadne schvaleni posle jen polozky zvoleneho jazyka',
         JSON.stringify(zalozky) === JSON.stringify(['DE:false', 'EN:true']) && en.length === 3 && JSON.stringify(de) === JSON.stringify(['Packstation PS-120', 'Arbeitstisch']) && t.stav.posty.length === 1
         && t.stav.posty[0].body.items.every(i => i.lang === 'de') && t.stav.posty[0].body.items.length === 2, { zalozky, en, de, posty: t.stav.posty });
    await t.browser.close();
  }
  {
    const t = await otevri({ data: { shops: [], items: [] } });
    await pockej(t.page, () => document.querySelector('.empty'));
    over('D3 prazdny stav: vysvetleni ze texty se nahravaji importem jako navrhy; zadna tlacitka', /Zatím tu nejsou žádné texty/.test(await vsechnyTexty(t.page)) && /Zatím není založený žádný shop/.test(await vsechnyTexty(t.page)) && (await t.page.$$('button')).length === 0, await vsechnyTexty(t.page));
    await t.browser.close();
  }
  {
    const t = await otevri({ overviewStatus: 500 });
    await pockej(t.page, () => document.querySelector('.msg.bad'));
    t.stav.overviewStatus = 200;
    await klik(t.page, 'button', /Zkusit znovu/);
    await pockej(t.page, () => document.querySelector('article'));
    over('D4 chyba nacteni prehledu: hlaska a tlacitko "Zkusit znovu", po nem se prehled nacte', (await jmenaKaret(t.page)).length === 3, await jmenaKaret(t.page));
    await t.browser.close();
  }
  // ---------------------------------------------------------------- E) vzhled: mobil, dlouhe texty, tmavy rezim, kontrast
  const kontrast = (a, b) => {
    const rgb = s => s.match(/\d+(\.\d+)?/g).slice(0, 3).map(Number);
    const lum = ([r, g, bl]) => { const f = c => { c /= 255; return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4); }; return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(bl); };
    const [l1, l2] = [lum(rgb(a)), lum(rgb(b))].sort((x, y) => y - x);
    return (l1 + 0.05) / (l2 + 0.05);
  };
  for (const [nazev, vp, mobil, schema] of [['mobil-svetly-360', { width: 360, height: 740 }, true, 'light'], ['mobil-tmavy-390', { width: 390, height: 844 }, true, 'dark'], ['pocitac-1100', { width: 1100, height: 800 }, false, 'light']]) {
    const d = zakladniData();
    d.items.push(polozka('product', 40, { name: 'Dlouhy_nazev_bez_mezer_' + 'W'.repeat(70), summary: 'S'.repeat(90), description: 'Radek 1\nRadek 2\n\n' + 'x'.repeat(120), specs: [{ name: 'N'.repeat(60), value: 'V'.repeat(80) }] }));
    const t = await otevri({ data: d, viewport: vp, isMobile: mobil, colorScheme: schema });
    await pockej(t.page, () => document.querySelector('article'));
    const m = await t.page.evaluate(() => {
      const c = document.querySelector('article'), tl = [...document.querySelectorAll('button, a.btn')];
      const cs = getComputedStyle(c), body = getComputedStyle(document.body), h2 = getComputedStyle(c.querySelector('h2')), mut = document.querySelector('p.muted');
      const dvojice = [...document.querySelectorAll('.chip.warn, .chip.bad, .chip.ok, .note:not(.info), .msg')].map(e => { const s = getComputedStyle(e); return [s.color, s.backgroundColor]; }).filter(x => !/rgba\(.*, 0\)$/.test(x[1]));
      return { dvojice, sirka: document.documentElement.scrollWidth <= window.innerWidth, minV: Math.min(...tl.map(b => b.getBoundingClientRect().height)), minS: Math.min(...tl.map(b => b.getBoundingClientRect().width)),
               textKarta: [h2.color, cs.backgroundColor], textTelo: [body.color, body.backgroundColor], tlumeny: [getComputedStyle(mut).color, body.backgroundColor], pocet: tl.length };
    });
    await t.page.screenshot({ path: path.join(SNIMKY, nazev + '.png'), fullPage: true });
    over(`E-${nazev}: bez horizontalniho posunu i s dlouhymi slovy, vsechna tlacitka aspon 44 px vysoka, kontrast textu, tlumeneho textu, stitku a upozorneni aspon 4.5, bez chyb v konzoli`,
         m.sirka && m.minV >= 44 && m.minS >= 44 && kontrast(m.textKarta[0], m.textKarta[1]) >= 4.5 && kontrast(m.tlumeny[0], m.tlumeny[1]) >= 4.5 && m.dvojice.length >= 2 && m.dvojice.every(x => kontrast(x[0], x[1]) >= 4.5) && t.chyby.length === 0 && t.neznama.length === 0, { m, chyby: t.chyby, k: kontrast(m.textKarta[0], m.textKarta[1]), kt: kontrast(m.tlumeny[0], m.tlumeny[1]) });
    await t.browser.close();
  }
  // ---------------------------------------------------------------- F) pravni dokumenty
  const DLOUHY = 'Prvý odsek obchodných podmienok. '.repeat(30) + '\n\nDruhý odsek.';
  function dokData() {
    const d = { shops: zakladniData().shops, items: [
      polozka('document', 50, { slug: 'terms', name: 'Obchodné podmienky', description: DLOUHY }),
      polozka('document', 51, { slug: 'privacy', name: 'Ochrana osobných údajov', description: 'Krátky text o údajoch.' }),
      polozka('document', 52, { slug: 'returns', name: 'Vrátenie tovaru', description: 'Tovar [DOPLNIŤ: lehota] dní.', blocking: ['placeholder'] }),
      polozka('document', 53, { slug: 'shipping', name: '<img src=x onerror="window.__xss=9">Doprava', description: '<script>window.__xss=8</script>text', status: 'approved', public: true }),
    ].map(i => Object.assign(i, { lang: 'sk', sku: null, category: null })) };
    return d;
  }
  async function kontrolaDokumentu(html) {
    const t = await otevri({ data: dokData(), html });
    await pockej(t.page, () => document.querySelector('article'));
    const karta = n => t.page.evaluate(nn => { const a = [...document.querySelectorAll('article')].find(x => x.querySelector('h2').textContent === nn); return a ? { t: a.innerText.replace(/\s+/g, ' '), tlac: [...a.querySelectorAll('button')].map(b => b.textContent.trim()), details: a.querySelectorAll('details').length, cls: a.className } : null; }, n);
    const dlouhy = await karta('Obchodné podmienky');
    const kratky = await karta('Ochrana osobných údajov');
    const zastupny = await karta('Vrátenie tovaru');
    const r = { chipy: !!dlouhy && /Dokument/.test(dlouhy.t) && /Obchodní podmínky/.test(dlouhy.t) && /Ochrana osobních údajů/.test(kratky.t) && /Vrácení zboží/.test(zastupny.t) };
    r.nahled = !!dlouhy && dlouhy.details === 1 && /Zobrazit celé znění \(\d+ znaků\)/.test(dlouhy.t) && /…/.test(dlouhy.t) && kratky.details === 0 && !/…/.test(kratky.t);
    const pred = await t.page.evaluate(() => [...document.querySelectorAll('article')].find(x => x.querySelector('h2').textContent === 'Obchodné podmienky').querySelectorAll('.desc').length);
    await t.page.evaluate(() => { [...document.querySelectorAll('article')].find(x => x.querySelector('h2').textContent === 'Obchodné podmienky').querySelector('details > summary').click(); });
    r.rozbaleni = await t.page.evaluate(() => { const a = [...document.querySelectorAll('article')].find(x => x.querySelector('h2').textContent === 'Obchodné podmienky'); const d = a.querySelector('details'); return d.open && d.querySelector('.desc').textContent.includes('Druhý odsek.') && getComputedStyle(d.querySelector('.desc')).whiteSpace === 'pre-line'; });
    r.sirka = await t.page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth);
    if (!html) await t.page.screenshot({ path: path.join(SNIMKY, 'dokumenty-mobil.png'), fullPage: true });
    r.zastupny = !!zastupny && /Nelze schválit/.test(zastupny.t) && /\[DOPLNIŤ\] nebo \[OVERIŤ\]/.test(zastupny.t) && /finální verzí/.test(zastupny.t) && zastupny.tlac.length === 0 && /is-blocked/.test(zastupny.cls);
    r.hromadne = /Schválit všechny návrhy \(2\)/.test(await vsechnyTexty(t.page));
    await t.page.evaluate(() => { [...document.querySelectorAll('article')].find(x => x.querySelector('h2').textContent === 'Ochrana osobných údajov').querySelector('button.primary').click(); });
    await pockej(t.page, () => document.querySelector('.msg'));
    r.schvaleni = t.stav.posty.length === 1 && JSON.stringify(t.stav.posty[0].body) === JSON.stringify({ items: [{ kind: 'document', id: 51, lang: 'sk', rev: t.stav.posty[0].body.items[0].rev }] }) && t.stav.posty[0].body.items[0].rev === t.stav.data.items.find(i => i.id === 51).rev
      && /Schváleno: 1 text\./.test(await text(t.page, '.msg'));
    await klik(t.page, 'button', /Schváleno \(2\)/);
    const sch = await t.page.evaluate(() => [...document.querySelectorAll('article')].map(a => ({ n: a.querySelector('h2').textContent, t: a.innerText.replace(/\s+/g, ' ') })));
    const x = await t.page.evaluate(() => ({ xss: window.__xss, nebezpecne: document.querySelectorAll('#app img, #app svg, #app iframe, #app script').length }));
    r.bezpecne = x.xss === undefined && x.nebezpecne === 0 && sch.some(s => /^<img src=x onerror="window\.__xss=9">Doprava$/.test(s.n)) && sch.every(s => !/nebylo veřejné/.test(s.t));
    r.bezchyb = t.chyby.length === 0 && t.neznama.length === 0;
    await t.browser.close();
    return r;
  }
  const mutuj = (stare, nove) => { if (!HTML.includes(stare)) throw new Error('mutace: kotva nenalezena: ' + stare.slice(0, 60)); return HTML.replace(stare, nove); };
  const rF = await kontrolaDokumentu(null);
  over('F1 dokument: karta nese stitek Dokument a cesky nazev druhu (podminky, soukromi, vraceni), dlouhy text ma nahled s "…" a rozbaleni "Zobrazit celé znění (N znaků)" (zachovane odstavce), kratky text bez rozbaleni, zadny horizontalni posun',
       rF.chipy && rF.nahled && rF.rozbaleni && rF.sirka, rF);
  over('F2 dokument se zastupnymi znackami [DOPLNIT]/[OVERIT]: "Nelze schválit" s vysvetlenim (nahradit finalni verzi po kontrole pravnikem), zadne tlacitko; hromadne schvaleni pocita jen schvalitelne (2); schvaleni dokumentu posle kind document, id, jazyk a otisk, ktery stranka videla',
       rF.zastupny && rF.hromadne && rF.schvaleni, rF);
  over('F3 text dokumentu z databaze se vklada JEN jako text (HTML ve nazvu i textu doslova, zadny img/svg/iframe/script), schvaleny dokument nenese upozorneni na kategorie, zadna chyba v konzoli ani neznamy pozadavek', rF.bezpecne && rF.bezchyb, rF);
  const mutace = {
    'bez nahledu a rozbaleni (cely text rovnou)': [mutuj('if (long) c.appendChild(h("details"', 'if (false) c.appendChild(h("details"'), 'nahled'],
    'bez vysvetleni zastupnych znacek': [mutuj('i.blocking.indexOf("placeholder") >= 0', 'false'), 'zastupny'],
    'bez ceskych nazvu druhu dokumentu': [mutuj('DOC[i.slug] || i.slug', 'i.slug'), 'chipy'],
    'vkladani nazvu jako HTML': [mutuj('c.appendChild(h("h2", { text: i.name || "(bez názvu)" }));', 'var hh = h("h2"); hh.innerHTML = i.name || "(bez názvu)"; c.appendChild(hh);'), 'bezpecne'],
  };
  for (const [popis, [html, klic]] of Object.entries(mutace)) {
    let r;
    try { r = await kontrolaDokumentu(html); } catch (e) { r = { [klic]: false, chyba: String(e).slice(0, 80) }; }
    over('FM mutace stranky: ' + popis + ' - test ji musi zachytit (kontrola "' + klic + '" selze)', r[klic] === false, r);
  }
  const ok = vysl.filter(Boolean).length;
  console.log(`\nVYSLEDEK stranka schvalovani textu mini-shopu: ${ok}/${vysl.length} OK (snimky: ${SNIMKY})`);
  process.exit(ok === vysl.length ? 0 : 1);
})().catch(e => { console.error('CHYBA TESTU:', e); process.exit(2); });
