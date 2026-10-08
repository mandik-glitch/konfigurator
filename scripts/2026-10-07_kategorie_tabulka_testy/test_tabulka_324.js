// NAHLED tabulky a filtru kategorie #324 "Valeckove dopravniky" (bot16, 2026-10-07; Robert pres bot9: "chce to stitky pro rychle filtrovani podle delky ... neni prijemne koukat na desitky stejnych obrazku").
// SKUTECNA stranka webapp/nahled-tabulka/dopravniky-324.html v Chromiu; data jsou ZIVA z e-shopu (jedno GET na zacatku testu: /api/shop/products?category_id=324&page_size=100&include=specs), zbytek
// serveru je maketa (page.route; zadne zapisy, zadna DB). Ocekavane hodnoty si test pocita z tech samych zivych dat NEZAVISLE na kodu stranky. Snimky: SNIMKY=<slozka>.
// Spusteni: node test_tabulka_324.js     Kandidat: NAHLED_HTML=/cesta/dopravniky-324.html node test_tabulka_324.js   (mutace: mutace_tabulka_324.py - kazda musi test shodit)
const { chromium } = require('/opt/konfigurator/node_modules/playwright-core');
const https = require('https'), fs = require('fs'), path = require('path');
const REPO = path.join(__dirname, '../..');
const HTML = process.env.NAHLED_HTML || path.join(REPO, 'webapp/nahled-tabulka/dopravniky-324.html');
const SNIMKY = process.env.SNIMKY || '';
const ZIVE = 'https://autovestavby.logiman.cz/api/shop/products?category_id=324&page_size=100&include=specs';
const vysl = [];
const over = (nazev, podminka, detail) => { vysl.push(!!podminka); console.log((podminka ? 'OK   ' : 'FAIL ') + nazev + (podminka ? '' : '  -> ' + JSON.stringify(detail).slice(0, 400))); if (!podminka && process.env.STOP_NA_PRVNI_CHYBE) process.exit(1); };       // STOP_NA_PRVNI_CHYBE=1: rychla mutacni kontrola
const stahniBuf = url => new Promise((res, rej) => https.get(url, r => { const b = []; r.on('data', c => b.push(c)); r.on('end', () => res({ st: r.statusCode, ct: r.headers['content-type'] || 'image/png', body: Buffer.concat(b) })); }).on('error', rej));
const stahni = url => new Promise((res, rej) => https.get(url, r => { let b = ''; r.on('data', c => b += c); r.on('end', () => { try { res(JSON.parse(b)); } catch (e) { rej(e); } }); }).on('error', rej));
const num = v => parseFloat(String(v).replace(',', '.').replace(/[^\d.]/g, ''));
const TYPL = { 'Ocel': 'Ocelový', 'Hliník hladký': 'Hliníkový', 'Hliník vroubkovaný': 'Hliníkový vroubkovaný' };      // zobrazované názvy typu válečku (bot7 2026-10-07); ve specs a v adrese zůstává původní hodnota
const plVar = n => n + ' ' + (n === 1 ? 'varianta' : (n >= 2 && n <= 4 ? 'varianty' : 'variant'));

(async () => {
  const live = await stahni(ZIVE);
  const P = live.products.map(p => ({ id: p.id, slug: p.slug, typ: p.specs['Typ válečku'], sirka: num(p.specs['Roller length']), delka: num(p.specs['Conveyor Length']), net: p.price_czk_placeholder, prumer: p.specs['Roller'] }));
  over('0 zive API: 78 produktu kategorie 324 se specs (typ, sirka, delka, cena)', live.total === P.length && P.length >= 70 && P.every(p => p.typ && p.sirka > 0 && p.delka > 0 && p.net > 0), { total: live.total, n: P.length });
  const co = (f) => P.filter(f).length;
  const html = fs.readFileSync(HTML, 'utf8');
  const zapisy = [], chyby = [];
  async function otevri({ width = 1440, height = 900, strankovat = 0, query = '', mobil = false, pozdeji = null } = {}) {
    const browser = await chromium.launch({ args: ['--no-sandbox'] });
    const ctx = await browser.newContext({ viewport: { width, height }, hasTouch: !!mobil, isMobile: !!mobil });
    const page = await ctx.newPage();
    page.on('pageerror', e => chyby.push(e.message));
    const pozadavky = [];
    await page.route('**/*', async route => {
      const req = route.request(), u = new URL(req.url());
      if (u.hostname !== 'dop.test') return route.abort();
      pozadavky.push(req.method() + ' ' + u.pathname + u.search);
      if (req.method() !== 'GET') zapisy.push(req.method() + ' ' + u.pathname);
      const json = (b, st = 200) => route.fulfill({ status: st, contentType: 'application/json', body: JSON.stringify(b) });
      if (u.pathname === '/nahled-tabulka/dopravniky-324.html') return route.fulfill({ status: 200, contentType: 'text/html; charset=utf-8', body: html });
      if (u.pathname === '/css/brand-logo.css') return route.fulfill({ status: 200, contentType: 'text/css', body: fs.readFileSync(path.join(REPO, 'webapp/css/brand-logo.css')) });
      if (u.pathname === '/api/theme-colors') return json({ light: {}, dark: {} });
      if (u.pathname === '/api/shop/products') {
        if (pozdeji === 'chyba') return json({ error: 'x' }, 500);
        const page = parseInt(u.searchParams.get('page') || '1', 10), ps = strankovat || 100;
        return json({ page, page_size: ps, total: live.total, products: live.products.slice((page - 1) * ps, page * ps) });
      }
      if (u.pathname.startsWith('/content-files/')) {
        if (SNIMKY) { try { const im = await stahniBuf('https://autovestavby.logiman.cz' + u.pathname); return route.fulfill({ status: im.st, contentType: im.ct, body: im.body }); } catch (e) { /* maketa nize */ } }      // snimky: skutecne obrazky z e-shopu
        return route.fulfill({ status: 200, contentType: 'image/png', body: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==', 'base64') });
      }
      return route.fulfill({ status: 404, body: '' });
    });
    await page.goto('http://dop.test/nahled-tabulka/dopravniky-324.html' + query);
    if (pozdeji !== 'chyba') await page.waitForSelector('#result table.dop, #result .cards, #result .state', { timeout: 15000 });
    else await page.waitForSelector('#result .state', { timeout: 15000 });
    return { browser, page, pozadavky };
  }
  const radky = page => page.evaluate(() => [...document.querySelectorAll('#result table.dop tbody tr')].map(r => ({ id: +r.dataset.id, txt: r.textContent.replace(/\s+/g, ' ').trim(), href: (r.querySelector('a.btn-detail') || {}).getAttribute && r.querySelector('a.btn-detail').getAttribute('href') })));
  const pocet = page => page.evaluate(() => document.getElementById('count').textContent.trim());
  const chip = (page, skup, val) => page.locator(`fieldset[data-group="${skup}"] button.chip[data-val="${val}"]`);
  const chipN = async (page, skup, val) => parseInt(await chip(page, skup, val).locator('.n').textContent(), 10);

  // ---- A) zakladni nacteni
  {
    const { browser, page, pozadavky } = await otevri();
    const r = await radky(page);
    over('A1 vychozi zobrazeni je TABULKA a ma 78 radku (kazda varianta jeden radek)', r.length === P.length && await page.evaluate(() => document.getElementById('viewTabulka').getAttribute('aria-pressed') === 'true'), { radku: r.length });
    over('A2 pocet nalezenych: "Nalezeno 78 z 78 variant"', (await pocet(page)) === `Nalezeno ${P.length} z ${P.length} variant`, await pocet(page));
    over('A3 v zahlavi je JEDEN maly obrazek a v tabulce zadne obrazky radku', await page.evaluate(() => document.querySelectorAll('#heroImg img').length === 1 && document.querySelectorAll('#result table img').length === 0), null);
    over('A4 sloupce tabulky: Typ valecku, O valecku, Sirka (mm), Delka (m), Cena bez DPH, Cena s DPH, (Detail)', await page.evaluate(() => [...document.querySelectorAll('table.dop thead th')].map(t => t.textContent.trim()).join('|').replace(/[▲▼↕]/g, '')) === 'Typ válečku|Ø válečku|Šířka (mm)|Délka (m)|Cena bez DPH|Cena s DPH|Detail', null);
    const p0 = P[0], r0 = r.find(x => x.id === p0.id);
    over('A5 prvni varianta ukazuje typ, rozmery a ceny bez i s DPH (21 %)', r0 && r0.txt.includes(TYPL[p0.typ]) && r0.txt.includes(`${p0.sirka} mm`) && /1\s?m/.test(r0.txt) && r0.txt.replace(/\s/g, '').includes(Math.round(p0.net).toLocaleString('cs-CZ').replace(/\s/g, '') + 'Kč') && r0.txt.replace(/\s/g, '').includes(Math.round(p0.net * 1.21).toLocaleString('cs-CZ').replace(/\s/g, '') + 'Kč'), r0);
    over('A6 kazdy radek ma odkaz Detail na /produkt/<slug> (78 ruznych)', r.every(x => x.href && x.href.startsWith('/produkt/')) && new Set(r.map(x => x.href)).size === P.length && P.every(p => r.find(x => x.id === p.id).href === '/produkt/' + encodeURIComponent(p.slug)), r.slice(0, 2));
    over('A7 stranka jen cte: zadny POST/PUT/DELETE, jen GET na stranku, css, produkty a barvy', zapisy.length === 0 && pozadavky.every(x => /^GET (\/nahled-tabulka|\/css\/|\/api\/shop\/products|\/api\/theme-colors|\/content-files\/)/.test(x)), { zapisy, pozadavky: pozadavky.slice(0, 8) });
    over('A8 bez JS chyb', chyby.length === 0, chyby);
    if (SNIMKY) await page.screenshot({ path: path.join(SNIMKY, 'desktop_vychozi.png'), fullPage: false });
    await browser.close();
  }
  // ---- B) filtry: AND mezi skupinami, OR uvnitr, pocty u stitku, zruseni
  {
    const { browser, page } = await otevri();
    await chip(page, 'delka', 2000).click();
    let r = await radky(page);
    over('B1 delka 2 m: pocet radku = pocet variant s delkou 2000 mm', r.length === co(p => p.delka === 2000) && (await pocet(page)).startsWith(`Nalezeno ${r.length} z`), { r: r.length, ocek: co(p => p.delka === 2000) });
    over('B2 stitek "2 m" je zmacknuty (aria-pressed) a tlacitko Zrusit filtry se ukazalo', await chip(page, 'delka', 2000).getAttribute('aria-pressed') === 'true' && await page.locator('#resetBtn').isVisible(), null);
    await chip(page, 'delka', 3000).click();
    r = await radky(page);
    over('B3 OR uvnitr skupiny: delka 2 m + 3 m = varianty s 2000 NEBO 3000', r.length === co(p => p.delka === 2000 || p.delka === 3000), { r: r.length });
    await chip(page, 'typ', 'Ocel').click();
    r = await radky(page);
    over('B4 AND mezi skupinami: (2 m nebo 3 m) a Ocel', r.length === co(p => (p.delka === 2000 || p.delka === 3000) && p.typ === 'Ocel') && r.every(x => x.txt.includes('Ocelový')), { r: r.length });
    await chip(page, 'sirka', 590).click();
    r = await radky(page);
    over('B5 tri skupiny najednou: + sirka 590', r.length === co(p => (p.delka === 2000 || p.delka === 3000) && p.typ === 'Ocel' && p.sirka === 590), { r: r.length });
    // pocty u stitku se ridi ostatnimi filtry (fasetove): u skupiny Typ ma "Hlinik hladky" pocet pri (2 m nebo 3 m) a sirka 590
    const ocekHH = co(p => (p.delka === 2000 || p.delka === 3000) && p.sirka === 590 && p.typ === 'Hliník hladký');
    over('B6 pocet u stitku se pocita pri ostatnich filtrech (Hlinik hladky pri 2/3 m a sirce 590)', (await chipN(page, 'typ', 'Hliník hladký')) === ocekHH, { n: await chipN(page, 'typ', 'Hliník hladký'), ocek: ocekHH });
    over('B7 stitek s nulovym poctem je ztlumeny (aria-disabled) a klik na nej nic nezmeni', await (async () => {
      const kandidat = await page.evaluate(() => [...document.querySelectorAll('button.chip[aria-disabled="true"]')].map(b => b.closest('fieldset').dataset.group + '|' + b.dataset.val)[0]);
      if (!kandidat) return true;
      const [g, v] = kandidat.split('|'); const pred = (await radky(page)).length; await chip(page, g, v).click(); return (await radky(page)).length === pred && await chip(page, g, v).getAttribute('aria-pressed') === 'false';
    })(), null);
    await page.locator('#resetBtn').click();
    r = await radky(page);
    over('B8 Zrusit filtry vrati vsech 78 a schova tlacitko, vsechny stitky nezmacknute', r.length === P.length && !(await page.locator('#resetBtn').isVisible()) && await page.evaluate(() => document.querySelectorAll('button.chip[aria-pressed="true"]').length === 0), { r: r.length });
    // fasetove ztlumeni: po vyberu typu maji sirky, ktere dany typ nema, pocet 0 a jsou aria-disabled
    {
      const typy = [...new Set(P.map(p => p.typ))], sirky = [...new Set(P.map(p => p.sirka))];
      const par = typy.map(t => [t, sirky.find(sx => !co(p => p.typ === t && p.sirka === sx))]).find(x => x[1] != null);
      if (par) { await chip(page, 'typ', par[0]).click(); over(`B9 po vyberu typu "${par[0]}" je sirka ${par[1]} mm (kterou tento typ nema) ztlumena s poctem 0`, await chip(page, 'sirka', par[1]).getAttribute('aria-disabled') === 'true' && (await chipN(page, 'sirka', par[1])) === 0, par); const predN = (await radky(page)).length; await chip(page, 'sirka', par[1]).click({ force: true });
        over(`B9b klik na ztlumeny stitek (sirka ${par[1]} mm) nic nezmeni: stejny pocet radku, stitek nezmacknuty`, (await radky(page)).length === predN && await chip(page, 'sirka', par[1]).getAttribute('aria-pressed') === 'false', { predN, po: (await radky(page)).length });
        await page.locator('#resetBtn').click(); }
      else over('B9 (data nemaji kombinaci typ x sirka bez variant)', true);
    }
    over('B10 bez JS chyb', chyby.length === 0, chyby);
    await browser.close();
  }
  // ---- C) razeni
  {
    const { browser, page } = await otevri();
    const ceny = async () => (await page.evaluate(() => [...document.querySelectorAll('#result table.dop tbody tr td.cena')].map(t => parseInt(t.textContent.replace(/\D/g, ''), 10))));
    await page.locator('table.dop thead th button', { hasText: 'Cena bez DPH' }).click();
    let c = await ceny();
    over('C1 klik na zahlavi Cena bez DPH: vzestupne a aria-sort=ascending', c.length === P.length && c.every((v, i) => !i || c[i - 1] <= v) && await page.locator('table.dop thead th[aria-sort="ascending"]').count() === 1, c.slice(0, 5));
    await page.locator('table.dop thead th button', { hasText: 'Cena bez DPH' }).click();
    c = await ceny();
    over('C2 druhy klik: sestupne a aria-sort=descending', c.every((v, i) => !i || c[i - 1] >= v) && await page.locator('table.dop thead th[aria-sort="descending"]').count() === 1, c.slice(0, 5));
    await page.selectOption('#sortSel', 'delka:desc');
    let d = await page.evaluate(() => [...document.querySelectorAll('#result table.dop tbody tr td:nth-child(4)')].map(t => parseFloat(t.textContent.replace(',', '.'))));
    over('C3 vyber Delka od nejdelsi: prvni jsou 6 m, posledni 1 m', d[0] === 6 && d[d.length - 1] === 1 && d.every((v, i) => !i || d[i - 1] >= v), d.slice(0, 3));
    await page.selectOption('#sortSel', 'sirka:asc');
    const s = await page.evaluate(() => [...document.querySelectorAll('#result table.dop tbody tr td:nth-child(3)')].map(t => parseInt(t.textContent.replace(/\D/g, ''), 10)));
    over('C4 vyber Sirka od nejuzsi: 290 mm prvni, 990 mm posledni, neklesajici', s[0] === 290 && s[s.length - 1] === 990 && s.every((v, i) => !i || s[i - 1] <= v), s.slice(0, 3));
    await page.selectOption('#sortSel', 'vychozi:asc');
    const r = await radky(page);
    over('C5 Vychozi razeni = poradi katalogu (stejne jako API)', r.every((x, i) => x.id === P[i].id), r.slice(0, 2));
    await page.selectOption('#sortSel', 'cena:asc'); await chip(page, 'typ', 'Ocel').click();
    c = await ceny();
    over('C6 razeni se drzi i po zmene filtru (Ocel, cena vzestupne)', c.length === co(p => p.typ === 'Ocel') && c.every((v, i) => !i || c[i - 1] <= v), c.length);
    await browser.close();
  }
  // ---- D) karty, adresa, stranky, chyba, tema
  {
    let { browser, page } = await otevri();
    await page.locator('#viewKarty').click();
    over('D1 Karty: 78 karet s malym obrazkem a odkazem Detail; Tabulka se vrati', await page.evaluate(() => document.querySelectorAll('#result .dcard').length === 78 && document.querySelectorAll('#result .dcard a.btn-detail').length === 78 && document.querySelectorAll('#result .dcard img').length === 78), null);
    await page.locator('#viewTabulka').click();
    over('D2 zpet na Tabulku: 78 radku', (await radky(page)).length === P.length, null);
    await chip(page, 'delka', 4000).click(); await chip(page, 'typ', 'Ocel').click(); await page.selectOption('#sortSel', 'cena:desc');
    const url = await page.evaluate(() => location.search);
    over('D3 filtry a razeni se propisuji do adresy (sdilitelny odkaz)', /delka=4000/.test(url) && /typ=Ocel/.test(url) && /razeni=cena%3Adesc/.test(url), url);
    await browser.close();
    ({ browser, page } = await otevri({ query: url }));
    const r = await radky(page);
    over('D4 otevreni odkazu s filtry: stejny vysledek (Ocel, 4 m, cena sestupne) a zmacknute stitky', r.length === co(p => p.delka === 4000 && p.typ === 'Ocel') && await chip(page, 'delka', 4000).getAttribute('aria-pressed') === 'true' && await chip(page, 'typ', 'Ocel').getAttribute('aria-pressed') === 'true', { r: r.length });
    await browser.close();
    ({ browser, page } = await otevri({ query: '?zobrazeni=karty&delka=1000' }));
    over('D5 odkaz ?zobrazeni=karty&delka=1000: karty, jen 1 m', await page.evaluate(() => document.querySelectorAll('#result .dcard').length) === co(p => p.delka === 1000), null);
    await browser.close();
    ({ browser, page } = await otevri({ strankovat: 40 }));
    over('D6 API vraci po 40 radcich: stranka nacte vsechny strany (78)', (await radky(page)).length === P.length, null);
    await browser.close();
    ({ browser, page } = await otevri({ pozdeji: 'chyba' }));
    over('D7 chyba API: srozumitelna hlaska a tlacitko Zkusit znovu, bez padu', await page.evaluate(() => /nepodařilo načíst/.test(document.getElementById('result').textContent) && !!document.querySelector('#result button')), chyby);
    await browser.close();
    {
      const typy = [...new Set(P.map(p => p.typ))], sirky = [...new Set(P.map(p => p.sirka))]; let nula = null;
      for (const t of typy) for (const sx of sirky) if (!nula && !co(p => p.typ === t && p.sirka === sx)) nula = [t, sx];
      over('D8a data maji aspon jednu kombinaci typ x sirka bez variant (test prazdneho stavu)', !!nula, null);
      if (nula) {
        ({ browser, page } = await otevri({ query: `?typ=${encodeURIComponent(nula[0])}&sirka=${nula[1]}` }));
        const txt = await page.evaluate(() => document.getElementById('result').textContent);
        over('D8b prazdny vysledek (adresa s kombinaci bez variant): hlaska "Zadna varianta neodpovida" a pocet 0', /Žádná varianta neodpovídá/.test(txt) && (await pocet(page)).startsWith('Nalezeno 0 z'), txt.slice(0, 80));
        await page.locator('#result button').click();
        over('D8c tlacitko Zrusit filtry v prazdnem stavu vrati vsech 78 variant', (await radky(page)).length === P.length, null);
        await browser.close();
      }
    }
    ({ browser, page } = await otevri());
    const pred = await page.evaluate(() => document.documentElement.getAttribute('data-theme') || 'dark');
    await page.locator('#themeBtn').click();
    const po = await page.evaluate(() => document.documentElement.getAttribute('data-theme'));
    over('D9 prepnuti motivu zmeni data-theme jen lokalne (zadny zapis na server)', po && po !== pred && zapisy.length === 0, { pred, po, zapisy });
    await browser.close();
  }
  // ---- F) texty podle kontroly bot7 (2026-10-07)
  {
    const { browser, page } = await otevri();
    const legendy = await page.evaluate(() => [...document.querySelectorAll('#filters fieldset legend')].map(l => l.textContent.trim()));
    over('F1 skupiny filtru: Delka dopravniku / Sirka dopravniku (delka valecku) / Typ valecku', JSON.stringify(legendy) === JSON.stringify(['Délka dopravníku', 'Šířka dopravníku (délka válečku)', 'Typ válečku']), legendy);
    const stitkyTyp = await page.evaluate(() => [...document.querySelectorAll('fieldset[data-group="typ"] button.chip')].map(b => [b.dataset.val, b.textContent.replace(/\d+$/, '').trim()]));
    over('F2 stitky typu valecku: Ocelovy / Hlinikovy / Hlinikovy vroubkovany (hodnota ve specs beze zmeny jako data-val)', stitkyTyp.length === 3 && stitkyTyp.every(([raw, txt]) => TYPL[raw] === txt), stitkyTyp);
    const text = await page.evaluate(() => document.body.innerText);
    over('F3 nikde se nezobrazuje puvodni "Hlinik hladky" ani samostatne "Ocel"', !/Hliník hladký/.test(text) && !/\bOcel\b/.test(text) && /Ocelový/.test(text) && /Hliníkový vroubkovaný/.test(text), text.match(/Hliník hladký|\bOcel\b/g));
    over('F4 poznamka pod tabulkou presne podle bot7', (await page.evaluate(() => document.querySelector('.note').textContent.trim())) === 'Ceny jsou uvedeny bez DPH; cena s DPH je vypočtena se sazbou 21 %. Šířka odpovídá délce válečku, délka je délka dopravníku.', null);
    // skloňování počtu u štítků: 1 varianta, 2-4 varianty, 0 a 5+ variant (aria-label u čísla) - napříč několika stavy filtrů
    const videno = new Set(); let spatne = [];
    const sber = async () => { const v = await page.evaluate(() => [...document.querySelectorAll('button.chip .n')].map(n => [parseInt(n.textContent, 10), n.getAttribute('aria-label')])); v.forEach(([n, a]) => { videno.add(n === 1 ? '1' : n >= 2 && n <= 4 ? '2-4' : n === 0 ? '0' : '5+'); if (a !== plVar(n)) spatne.push([n, a]); }); };
    await sber(); await chip(page, 'delka', 2000).click(); await sber(); await chip(page, 'sirka', 290).click(); await sber(); await chip(page, 'typ', 'Ocel').click(); await sber();
    await page.locator('#resetBtn').click(); await chip(page, 'typ', 'Hliník hladký').click(); await sber();          // stav s nulovými počty (šířka 990 mm tento typ nemá)
    over('F5 aria-label poctu u stitku: 1 varianta / 2-4 varianty / 0 a 5+ variant (videno: ' + [...videno].sort().join(', ') + ')', spatne.length === 0 && ['1', '2-4', '5+', '0'].every(k => videno.has(k)), { spatne: spatne.slice(0, 4), videno: [...videno] });
    await page.locator('#resetBtn').click();
    const a0 = await page.evaluate(() => document.querySelector('#result table.dop tbody tr a.btn-detail').getAttribute('aria-label'));
    const pp = P[0];
    over('F6 aria-label tlacitka Detail: "Detail produktu: <typ>, sirka N mm, delka X m"', a0 === `Detail produktu: ${TYPL[pp.typ]}, šířka ${pp.sirka} mm, délka ${pp.delka / 1000} m`, a0);
    over('F7 na pocitaci je jednotka jen v zahlavi (bunky Sirka a Delka bez viditelne jednotky), na mobilu viz E', await page.evaluate(() => [...document.querySelectorAll('td .u')].every(u => getComputedStyle(u).display === 'none') && document.querySelector('td.c-sirka').textContent.replace(/\s/g, '').endsWith('mm')), null);
    await browser.close();
  }
  // ---- E) mobil 390 px
  {
    const { browser, page } = await otevri({ width: 390, height: 844, mobil: true });
    const m = await page.evaluate(() => ({ sirkaDok: document.documentElement.scrollWidth, okno: innerWidth, thead: getComputedStyle(document.querySelector('table.dop thead')).display, filtry: document.getElementById('filtersBox').open, detail: [...document.querySelectorAll('#result a.btn-detail')].slice(0, 3).map(a => Math.round(a.getBoundingClientRect().height)) }));
    over('E1 mobil 390: bez vodorovneho posunu, zahlavi tabulky skryte (radky jako karty), filtry sbalene', m.sirkaDok <= m.okno && m.thead === 'none' && m.filtry === false, m);
    over('E2 mobil: tlacitko Detail je dost velke k poklepani (>= 36 px)', m.detail.length === 3 && m.detail.every(h => h >= 36), m.detail);
    const kk = await page.evaluate(() => { const r = document.querySelector('#result table.dop tbody tr'), t = r.querySelector('td.c-typ').getBoundingClientRect(), c = r.querySelector('td.cena').getBoundingClientRect(); return { vyska: Math.round(r.getBoundingClientRect().height), typY: Math.round(t.top), cenaY: Math.round(c.top), cenaVpravo: Math.round(c.right) <= innerWidth }; });
    over('E2b mobil: radek je uspornou kartou - typ a cena v prvnim radku, celkova vyska do 170 px', kk.vyska <= 170 && Math.abs(kk.typY - kk.cenaY) <= 8 && kk.cenaVpravo, kk);
    over('E2c mobil: u hodnot Sirka a Delka je videt jednotka (mm, m), protoze zahlavi tabulky je skryte', await page.evaluate(() => [...document.querySelectorAll('#result tbody tr:first-child td .u')].length === 2 && [...document.querySelectorAll('#result tbody tr:first-child td .u')].every(u => getComputedStyle(u).display === 'inline')), null);
    await page.locator('#filtersBox > summary').tap();
    over('E3 mobil: klepnuti na Filtry rozbali stitky', await page.evaluate(() => document.getElementById('filtersBox').open && document.querySelectorAll('button.chip').length >= 10), null);
    await chip(page, 'delka', 3000).tap();
    over('E4 mobil: stitek filtruje a pocet sedi', (await radky(page)).length === co(p => p.delka === 3000), null);
    if (SNIMKY) { await page.screenshot({ path: path.join(SNIMKY, 'mobil_filtry.png') }); await page.locator('#filtersBox > summary').tap(); await page.waitForTimeout(150); await page.screenshot({ path: path.join(SNIMKY, 'mobil_radky.png') }); }
    over('E5 mobil: bez JS chyb', chyby.length === 0, chyby);
    await browser.close();
  }
  // ---- snimky desktop s filtrem
  if (SNIMKY) {
    const { browser, page } = await otevri();
    await chip(page, 'delka', 2000).click(); await chip(page, 'delka', 3000).click(); await chip(page, 'typ', 'Ocel').click();
    await page.screenshot({ path: path.join(SNIMKY, 'desktop_filtr.png') });
    await page.locator('#viewKarty').click(); await page.waitForTimeout(300); await page.screenshot({ path: path.join(SNIMKY, 'desktop_karty.png') });
    await browser.close();
  }
  const ok = vysl.filter(Boolean).length;
  console.log(`\nVYSLEDEK tabulka a filtry kategorie 324 (nahled): ${ok}/${vysl.length} OK`);
  process.exit(ok === vysl.length ? 0 : 1);
})().catch(e => { console.error('CHYBA TESTU', e); process.exit(2); });
