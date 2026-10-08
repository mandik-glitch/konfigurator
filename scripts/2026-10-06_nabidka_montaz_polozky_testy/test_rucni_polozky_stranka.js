// RUCNI POLOZKY v online nabidce - verejna stranka (bot8, 2026-10-06; Robert: admin pripise do nabidky polozku z katalogu s 3D modelem / volny text s 1-2 obrazky a cenou).
// SKUTECNA stranka webapp/nabidka-online.html v Chromiu proti falesnemu serveru (harness.js), nic se nezapisuje. Hlida: radky rucnich polozek v cenove tabulce (mnozstvi "N ks", cena,
// cislovani), karty "Doplnujici polozky" pod tabulkou (popis s zalomenim radku, 1-2 obrazky, 3D model), zvetseni obrazku (klik / Esc), odkaz "podrobnosti", 3D model se nacte AZ kdyz je karta
// videt (V3D.mount s adresou modelu polozky), polozka bez popisu / obrazku / modelu karty nema, nabidka bez rucnich polozek beze zmeny, uzka obrazovka bez horizontalniho posunu.
// Spusteni: node test_rucni_polozky_stranka.js     Kandidat: NABIDKA_HTML=/cesta/k/nabidka-online.html node ...     Vizualni test se skutecnym 3D: CDN=1 SNIMKY=/cesta node ...
const fs = require('fs');
const path = require('path');
const { otevriNabidku, naCenovouStranku, vzorovaNabidka, PNG } = require('./harness');
const vysl = [];
const over = (nazev, podminka, detail) => { vysl.push(!!podminka); console.log((podminka ? 'OK   ' : 'FAIL ') + nazev + (podminka ? '' : '  -> ' + JSON.stringify(detail))); };
const K1 = 'polozka_900101_0123456789abcdef.png', K2 = 'polozka_900101_fedcba9876543210.jpg';
const GLB = path.join(__dirname, '../../webapp/katalog/product_3091.glb');
const TEXT = { name: 'Zaměření a doprava', dim: '1× výjezd', qty: '2 ks', unit_price: 1500, total: 3000, manual: { typ: 'text', popis: 'Zaměření u zákazníka\nvčetně fotodokumentace', obrazky: [K1, K2] } };
const KAT = { name: 'Záslepka 40x40 S10', dim: '40 × 40 mm', qty: '8 ks', unit_price: 5, total: 40, product_id: 3091, layer: 'produkt', manual: { typ: 'katalog', popis: 'Černá, plast, S10', model: true } };
const BEZ = { name: 'Příplatek za expres', dim: '', qty: '1 ks', unit_price: 500, total: 500, manual: { typ: 'text', popis: '' } };
const STUB_V3D = () => { window.__v3dCalls = []; window.V3D = { mount(el, o) { window.__v3dCalls.push({ url: o.modelUrl, mode: o.mode, allowReal: o.allowReal, hudKoty: o.hudKoty, hudDock: o.hudDock, dims: o.dims, cls: el.className }); return { dispose() {} }; }, deps: [] }; };
const trasy = async (route, { p, m, json }) => {
  if (/\/item-image\//.test(p)) { await route.fulfill({ status: 200, contentType: p.endsWith('.jpg') ? 'image/jpeg' : 'image/png', body: PNG }); return true; }
  if (/\/item-model\/3091$/.test(p)) { await route.fulfill({ status: 200, contentType: 'model/gltf-binary', body: fs.readFileSync(GLB) }); return true; }
  return false;
};
const nabidka = () => vzorovaNabidka(d => { d.order_prefs = null; d.items = d.items.concat([TEXT, KAT, BEZ]); d.total_price = d.total_price + 3000 + 40 + 500; });
const radky = () => [...document.querySelectorAll('.slide.active table.items tbody tr')].map(tr => [...tr.children].map(td => td.textContent.replace(/\s+/g, ' ').trim()));

(async () => {
  let { browser, page, chyby } = await otevriNabidku({ nabidka: nabidka(), trasy, initScript: STUB_V3D });
  const volani0 = await page.evaluate(() => window.__v3dCalls.length);
  over('P0 dokud zakaznik neprekliknul na cenu, se 3D model polozky NEnacita (karta neni videt)', volani0 === 0, volani0);
  await naCenovouStranku(page);
  await page.waitForTimeout(600);
  let r = await page.evaluate(radky);
  const i0 = r.findIndex(x => x[1].startsWith('Zaměření a doprava'));
  const cislo = i => String(i + 1).padStart(2, '0');
  over('P1 rucni radky jsou v cenove tabulce hned za obycejnymi (cisla navazuji), mnozstvi "N ks", cena a celkem', i0 === 13 && r[i0][0] === cislo(i0) && r[i0][3] === '2 ks' && /1[  ]?500/.test(r[i0][4]) && /3[  ]?000/.test(r[i0][5])
     && r[i0 + 1][1].startsWith('Záslepka 40x40 S10') && r[i0 + 1][0] === cislo(i0 + 1) && r[i0 + 1][3] === '8 ks' && r[i0 + 2][1].startsWith('Příplatek za expres') && r[i0 + 2][0] === cislo(i0 + 2) && r[i0 + 2][3] === '1 ks', r.slice(i0 - 1, i0 + 4));
  over('P2 radky s kartou maji odkaz "podrobnosti", radek bez popisu / obrazku / modelu ne', i0 >= 0 && /podrobnosti/.test(r[i0][1]) && /podrobnosti/.test(r[i0 + 1][1]) && !/podrobnosti/.test(r[i0 + 2][1]) && !r.slice(0, i0).some(x => /podrobnosti/.test(x[1])), [r[i0][1], r[i0 + 1][1], r[i0 + 2][1]]);
  const karty = await page.evaluate(() => [...document.querySelectorAll('#manualItems .manual-card')].map(c => ({ id: c.id, cislo: c.querySelector('.mi-no').textContent, nazev: c.querySelector('figcaption span:last-child').textContent, popis: c.querySelector('.mi-popis') && c.querySelector('.mi-popis').innerText,
    imgs: [...c.querySelectorAll('.mi-imgs img')].map(i => i.getAttribute('src')), model: c.querySelector('.mi-3d') && c.querySelector('.mi-3d').dataset.model })));
  over('P3 pod tabulkou je "Doplnujici polozky" se 2 kartami (volny text a katalog; polozka bez obsahu karty nema), cisla = cisla radku', karty.length === 2 && karty[0].cislo === cislo(i0) && karty[1].cislo === cislo(i0 + 1) && karty[0].nazev === 'Zaměření a doprava' && karty[1].nazev === 'Záslepka 40x40 S10', karty);
  over('P4 karta volneho textu: popis se zalomenim radku, 2 obrazky s adresou pres token nabidky, zadny 3D model', karty[0].popis === 'Zaměření u zákazníka\nvčetně fotodokumentace' && JSON.stringify(karty[0].imgs) === JSON.stringify([`/api/public/offers/TESTTOKEN/item-image/${K1}`, `/api/public/offers/TESTTOKEN/item-image/${K2}`]) && !karty[0].model, karty[0]);
  over('P5 karta z katalogu: 3D kontejner s adresou modelu polozky, popis, zadne obrazky', karty[1].model === '/api/public/offers/TESTTOKEN/item-model/3091' && karty[1].popis === 'Černá, plast, S10' && karty[1].imgs.length === 0, karty[1]);
  const poloha = await page.evaluate(() => { const e = document.querySelector('.mi-3d'); const r = e.getBoundingClientRect(); return { top: r.top, vh: innerHeight }; });
  const volaniPred = await page.evaluate(() => window.__v3dCalls.length);
  over('P6a 3D karta je pod okrajem obrazovky a model se zatim NEnacetl (nacita se az kdyz je videt)', poloha.top > poloha.vh && volaniPred === 0, { poloha, volaniPred });
  await page.evaluate(() => document.querySelector('.mi-3d').scrollIntoView({ block: 'center' }));
  await page.waitForTimeout(700);
  const volani = await page.evaluate(() => window.__v3dCalls);
  over('P6 po doscrollovani se 3D model nacte JEDNOU: V3D.mount s adresou modelu, mode real, bez kot, tlacitka nad platnem', volani.length === 1 && volani[0].url === '/api/public/offers/TESTTOKEN/item-model/3091' && volani[0].mode === 'real' && volani[0].allowReal === true && volani[0].hudKoty === false && volani[0].hudDock === 'top', volani);
  await page.evaluate(() => document.querySelector('.slide.active').scrollTo(0, 0)); await page.waitForTimeout(200);
  await page.evaluate(() => document.querySelector('.mi-3d').scrollIntoView({ block: 'center' })); await page.waitForTimeout(500);
  over('P6b opakovane zobrazeni karty model nenacita znovu (porad 1 volani)', (await page.evaluate(() => window.__v3dCalls.length)) === 1, null);

  // zvetseni obrazku
  await page.click('#manualItems .mi-imgs img');
  await page.waitForTimeout(200);
  let lb = await page.evaluate(() => { const b = document.getElementById('miLightbox'); return b && { show: b.classList.contains('show'), src: b.querySelector('img').getAttribute('src'), disp: getComputedStyle(b).display }; });
  over('P7 klik na obrazek ho otevre ve zvetsenem okne (stejna adresa)', lb && lb.show && lb.disp === 'flex' && lb.src.endsWith(K1), lb);
  await page.keyboard.press('Escape');
  lb = await page.evaluate(() => document.getElementById('miLightbox').classList.contains('show'));
  over('P8 Esc okno zavre', lb === false, lb);
  await page.click('#manualItems .mi-imgs img'); await page.click('#miLightbox');
  over('P9 klik do okna ho zavre', await page.evaluate(() => !document.getElementById('miLightbox').classList.contains('show')), null);

  // odkaz "podrobnosti"
  await page.evaluate(() => document.querySelector('.slide.active').scrollTo(0, 0));
  await page.click('a.mi-link[data-mi="2"]');
  await page.waitForTimeout(900);
  const vid = await page.evaluate(() => { const c = document.getElementById('mi-2').getBoundingClientRect(); return c.top >= 0 && c.bottom <= innerHeight + 2; });
  over('P10 odkaz "podrobnosti" doroluje na kartu polozky', vid, null);
  over('P11 bez chyb ve strance', chyby.length === 0, chyby.slice(0, 3));
  await browser.close();

  // ---- text z formulare se nikdy nevklada jako HTML (nazev, popis), obrazky nejvyse 2 i kdyz je v ulozenych datech vic
  const ZLY = { name: '<img src=x onerror="window.__xss=1">Název', dim: '', qty: '1 ks', unit_price: 1, total: 1, manual: { typ: 'text', popis: '<b>tučně</b><img src=x onerror="window.__xss=2"><script>window.__xss=3</script>', obrazky: [K1, K2, K1, K2] } };
  ({ browser, page, chyby } = await otevriNabidku({ nabidka: vzorovaNabidka(d => { d.order_prefs = null; d.items = d.items.concat([ZLY]); }), trasy, initScript: STUB_V3D }));
  await naCenovouStranku(page);
  await page.waitForTimeout(500);
  const xss = await page.evaluate(() => ({ flag: window.__xss, popis: document.querySelector('.manual-card .mi-popis').textContent, nazev: document.querySelector('.manual-card figcaption span:last-child').textContent, obr: document.querySelectorAll('.manual-card .mi-imgs img').length,
    vTabulce: [...document.querySelectorAll('.slide.active table.items tbody tr')].pop().textContent.includes('<img') }));
  over('P16 nazev a popis se vkladaji jako TEXT (zadne vykonani, znacky zustavaji videt jako text)', xss.flag === undefined && xss.popis.startsWith('<b>tučně</b><img') && xss.nazev.startsWith('<img src=x'), xss);
  over('P17 obrazku se zobrazi nejvyse 2, i kdyz je v datech vic', xss.obr === 2, xss.obr);
  await browser.close();

  // ---- nabidka bez rucnich polozek: beze zmeny
  ({ browser, page, chyby } = await otevriNabidku({ nabidka: vzorovaNabidka(d => { d.order_prefs = null; }), trasy, initScript: STUB_V3D }));
  await naCenovouStranku(page);
  const x = await page.evaluate(() => ({ karty: !!document.getElementById('manualItems'), radku: document.querySelectorAll('.slide.active table.items tbody tr').length, odkazy: document.querySelectorAll('a.mi-link').length, qty: document.querySelector('.slide.active table.items td.it-qty').textContent }));
  over('P12 nabidka bez rucnich polozek: zadna sekce "Doplnujici polozky", zadne odkazy, puvodni zapis mnozstvi ("1 ks")', !x.karty && x.odkazy === 0 && x.qty === '1 ks', x);
  await browser.close();

  // ---- uzka obrazovka
  ({ browser, page, chyby } = await otevriNabidku({ width: 390, height: 844, mobil: true, nabidka: nabidka(), trasy, initScript: STUB_V3D }));
  await naCenovouStranku(page);
  await page.waitForTimeout(500);
  const m = await page.evaluate(() => { const g = document.querySelector('.manual-grid'), c = [...document.querySelectorAll('.manual-card')].map(e => e.getBoundingClientRect());
    return { preteka: document.documentElement.scrollWidth > innerWidth + 1, kartaVpravo: Math.max(...c.map(r => r.right)), vw: innerWidth, sloupcu: new Set(c.map(r => Math.round(r.left))).size, kart: c.length }; });
  over('P13 uzka obrazovka (390 px): stranka se neposouva do strany, karty pod sebou v 1 sloupci a vejdou se', !m.preteka && m.kartaVpravo <= m.vw + 1 && m.sloupcu === 1 && m.kart === 2, m);
  over('P14 bez chyb ve strance (mobil)', chyby.length === 0, chyby.slice(0, 3));
  await browser.close();

  // ---- skutecny 3D prohlizec (jen kdyz CDN=1): vizualni kontrola orientace a velikosti modelu z katalogu
  if (process.env.CDN) {
    ({ browser, page, chyby } = await otevriNabidku({ nabidka: nabidka(), trasy, cdn: true }));
    await naCenovouStranku(page);
    await page.evaluate(() => document.querySelector('.mi-3d').scrollIntoView({ block: 'center' }));          // 3D se nacita az kdyz je karta videt
    await page.waitForTimeout(8000);
    const c = await page.evaluate(() => { const el = document.querySelector('.mi-3d'); const cv = el && el.querySelector('canvas'); return { fail: el && el.classList.contains('mi-3d-fail'), canvas: !!cv, w: cv && cv.clientWidth, h: cv && cv.clientHeight }; });
    over('P15 skutecny V3D: 3D model polozky z katalogu se vykresli (platno nenulove velikosti, kontejner nezmizel)', c.canvas && !c.fail && c.w > 100 && c.h > 100, c);
    if (process.env.SNIMKY) { fs.mkdirSync(process.env.SNIMKY, { recursive: true }); await page.locator('#manualItems').screenshot({ path: path.join(process.env.SNIMKY, 'rucni_polozky_karty.png') }); }
    await browser.close();
  }
  const ok = vysl.filter(Boolean).length;
  console.log(`\nVYSLEDEK rucni polozky v online nabidce - stranka: ${ok}/${vysl.length} OK`);
  process.exit(ok === vysl.length ? 0 : 1);
})().catch(e => { console.error('TEST SPADL:', e); process.exit(2); });
