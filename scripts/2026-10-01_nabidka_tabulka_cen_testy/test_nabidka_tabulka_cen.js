// Online nabidka - cenova tabulka a celkova cena (Robert 2026-10-01):
//  1) "tabulka cen se nemuzu rolovat, musi byt videt cela"  -> nic nepreteka, vse viditelne, pod 760 px karty,
//  2) "tech sloupcu v cene je moc, neuvadej ceny s DPH vubec v tabulce, az pod tabulkou" -> tabulka ma 6 sloupcu BEZ DPH,
//  3) "hlavni cena celkem ma byt bez DPH" -> banner: hlavni cislo bez DPH, pod nim DPH a "k uhrade vc. DPH",
//  4) "ceny profilu scitane na 1 radek podle prurezu profilu" -> slouceny radek profilu (klik zvyrazni vsechny jeho skupiny),
//  5) "nevidim v nabidce cenu za montaz (a balne)" -> pod tabulkou radek s cenou montaze; balne je radek tabulky (dodava scena).
// SKUTECNA stranka v Chromiu proti falesnemu serveru (harness_nabidka.js), data = skutecna nabidka z DB (ukazka_nabidky.json).
// Spusteni: node test_nabidka_tabulka_cen.js   (konci kodem 0 jen kdyz VSE prosla; SIRKY=390,1440 = jen vybrane sirky)
// Kandidat pred nasazenim: NABIDKA_HTML=/cesta/k/nabidka-online.html node test_nabidka_tabulka_cen.js
// Mutacni kontrola: NABIDKA_HTML=<puvodni verze> musi selhat (9 sloupcu s DPH, hlavni cena vc. DPH, neslouceny profil, bez montaze).
const vm = require('vm');
const fs = require('fs');
const path = require('path');
const { otevriNabidku, naCenovouStranku } = require('./harness_nabidka');
const { vytahniFunkci } = require('../2026-10-01_kotovani_testy/harness_koty');

const vysl = [];
const over = (nazev, podminka, detail) => {
  vysl.push(!!podminka);
  console.log((podminka ? 'OK   ' : 'FAIL ') + nazev + (podminka ? '' : '  -> ' + JSON.stringify(detail)));
};
const norm = s => (s || '').replace(/[  ]/g, ' ').replace(/\s+/g, ' ').trim();
const HTML = fs.readFileSync(process.env.NABIDKA_HTML || path.join(__dirname, '../../webapp/nabidka-online.html'), 'utf8');
const NAB = () => JSON.parse(fs.readFileSync(process.env.OFFER_JSON || path.join(__dirname, 'ukazka_nabidky.json'), 'utf8'));
const SIRKY = (process.env.SIRKY ? process.env.SIRKY.split(',').map(Number)
  : [320, 360, 390, 430, 540, 640, 641, 720, 759, 760, 900, 1024, 1180, 1280, 1440, 1920]);   // SIRKY=390,1440 = rychla kontrola
const POPISKY = ['"Rozměr"', '"Množství"', '"Cena/ks (bez DPH)"', '"Celkem (bez DPH)"'];
const KARTY_DO = 759;   // pod touhle sirkou se radky skladaji do karet

// jedno mereni cenove stranky (volat v kontextu stranky)
const MERENI = () => {
  const slide = document.querySelector('.slide.active');
  const wrap = slide.querySelector('.items-scroll'), t = slide.querySelector('table.items');
  const vw = innerWidth;
  const radky = [...t.querySelectorAll('tbody tr')].filter(tr => getComputedStyle(tr).display !== 'none');
  const bunky = radky.flatMap(tr => [...tr.children]);
  const mimo = bunky.filter(td => { const r = td.getBoundingClientRect(); return r.width > 0 && (r.left < -0.5 || r.right > vw + 0.5); }).length;
  const thead = t.querySelector('thead');
  const karty = getComputedStyle(thead).display === 'none';
  const th = [...thead.querySelectorAll('th')];
  const thMimo = karty ? 0 : th.filter(h => { const r = h.getBoundingClientRect(); return r.left < -0.5 || r.right > vw + 0.5; }).length;
  const r = t.getBoundingClientRect();
  const prvni = radky[0];
  return {
    vw, preteka: document.documentElement.scrollWidth > vw + 1, slidePreteka: slide.scrollWidth > slide.clientWidth + 1,
    wrapPreteka: wrap.scrollWidth > wrap.clientWidth + 1, vlevo: Math.round(r.left), vpravo: Math.round(r.right), sirka: Math.round(r.width),
    mimo, thMimo, karty, pocetTh: th.length, bunekNaRadek: prvni.children.length, radku: radky.length,
    popisky: karty ? [...prvni.children].slice(2).map(td => getComputedStyle(td, '::before').content) : null,
    celkemPrvniRadek: prvni.children[5] ? prvni.children[5].textContent.trim() : null,
    pocetTrid: document.querySelectorAll('.slide-inner-price').length, mezeraVpravo: Math.round(vw - r.right),
  };
};

(async () => {
  // ---- A) prochazka sirkami: nic nepreteka a nerolueje se, vse viditelne, popisky v kartach, odsazeni od sipek
  for (const w of SIRKY) {
    const mobil = w <= 640;
    const { browser, page, chyby } = await otevriNabidku({ width: w, height: mobil ? 844 : 900, mobil });
    await naCenovouStranku(page);
    const m = await page.evaluate(MERENI);
    const stol = m.karty ? 'karty' : 'tabulka';
    over(`A ${w}px (${stol}): nic nepreteka a nerolueje se (strana, slide, obal)`, !m.preteka && !m.slidePreteka && !m.wrapPreteka, m);
    over(`A ${w}px: vsechny bunky vsech radku jsou uvnitr obrazovky`, m.mimo === 0 && m.thMimo === 0, { mimo: m.mimo, thMimo: m.thMimo, vlevo: m.vlevo, vpravo: m.vpravo });
    over(`A ${w}px: rozlozeni odpovida sirce (do ${KARTY_DO} px karty, jinak tabulka)`, m.karty === (w <= KARTY_DO), { karty: m.karty });
    if (!m.karty) over(`A ${w}px: tabulka ma 6 sloupcu (polozka, rozmer, mnozstvi, cena/ks, celkem - vse BEZ DPH)`, m.pocetTh === 6 && m.bunekNaRadek === 6, m);
    else over(`A ${w}px: u hodnot jsou popisky (Rozmer, Mnozstvi, Cena/ks, Celkem), hlavicka je skryta`, JSON.stringify(m.popisky) === JSON.stringify(POPISKY), m.popisky);
    over(`A ${w}px: "Celkem" prvniho radku je 1 152 Kc (bez DPH)`, norm(m.celkemPrvniRadek) === '1 152 Kč', m.celkemPrvniRadek);
    if (w >= 641) over(`A ${w}px: obsah nezasahuje pod sipky navigace (odsazeni >= 68 px z obou stran)`, m.vlevo >= 68 && m.mezeraVpravo >= 68, { vlevo: m.vlevo, mezeraVpravo: m.mezeraVpravo });
    over(`A ${w}px: sirsi sloupec jen na cenove strance (1 prvek .slide-inner-price), bez JS chyb`, m.pocetTrid === 1 && chyby.length === 0, { trid: m.pocetTrid, chyby: chyby.slice(0, 2) });
    await browser.close();
  }

  // ---- B) obsah cenove stranky: zadne ceny s DPH v tabulce, banner BEZ DPH, DPH a "k uhrade" pod tabulkou, montaz, slouceny profil
  {
    const { browser, page, chyby } = await otevriNabidku({ width: 1440, height: 900 });
    await naCenovouStranku(page);
    const o = await page.evaluate(() => {
      const t = document.querySelector('.slide.active table.items');
      const txt = e => e ? e.textContent.replace(/[  ]/g, ' ').replace(/\s+/g, ' ').trim() : null;
      const radky = [...t.querySelectorAll('tbody tr')].filter(tr => getComputedStyle(tr).display !== 'none');
      const prof = radky.find(tr => /^Profil 30x30mm/.test(txt(tr.children[1])));
      const soucetCelkem = radky.reduce((s, tr) => s + (parseFloat((txt(tr.children[5]) || '').replace(/[^\d]/g, '')) || 0), 0);
      return {
        hlavicky: [...t.querySelectorAll('thead th')].map(txt),
        trida: ['it-price-vat', 'it-vat', 'it-total-vat'].map(c => t.querySelectorAll('td.' + c).length),
        textTabulky: txt(t),
        label: txt(document.querySelector('.total-banner .label')), hodnota: txt(document.getElementById('totalBannerValue')),
        detail: txt(document.getElementById('totalBannerDetail')), detailViditelny: getComputedStyle(document.getElementById('totalBannerDetail')).display !== 'none',
        vat: txt(document.getElementById('totalBannerVat')), montaz: txt(document.getElementById('montazInfo')),
        profil: prof ? { bunky: [...prof.children].map(txt), skupiny: prof.dataset.group, trida: prof.className } : null,
        profilRadku: radky.filter(tr => /^Profil 30x30mm/.test(txt(tr.children[1]))).length,
        pocetRadku: radky.length, soucetCelkem,
        bannerPoTabulce: document.querySelector('.slide.active .items-scroll').compareDocumentPosition(document.querySelector('.slide.active .total-banner')) & Node.DOCUMENT_POSITION_FOLLOWING,
      };
    });
    over('B1 tabulka nema zadny sloupec s DPH (hlavicky jen bez DPH, zadne bunky it-price-vat / it-vat / it-total-vat)',
         o.hlavicky.length === 6 && o.hlavicky.every(h => !/vč\.\s*DPH/i.test(h) && h !== 'DPH') && o.trida.every(n => n === 0), o);
    over('B2 hlavicky: Polozka, Rozmer, Mnozstvi, Cena/ks (bez DPH), Celkem (bez DPH)',
         JSON.stringify(o.hlavicky.slice(1)) === JSON.stringify(['Položka', 'Rozměr', 'Množství', 'Cena/ks (bez DPH)', 'Celkem (bez DPH)']), o.hlavicky);
    over('B3 v tabulce se nikde neobjevi cena s DPH (napr. 1 394 Kc = 1 152 x 1,21 u prvni polozky)', !/1 394/.test(o.textTabulky), null);
    over('B4 hlavni cena celkem v banneru je BEZ DPH: popisek "Celkova cena (bez DPH)", hodnota 27 353 Kc', o.label === 'Celková cena (bez DPH)' && o.hodnota === '27 353 Kč', { label: o.label, hodnota: o.hodnota });
    over('B5 pod hlavni cenou je DPH a castka k uhrade vc. DPH: "DPH 21 % 5 744 Kc · k uhrade vc. DPH 33 097 Kc"', o.vat === 'DPH 21 % 5 744 Kč · k úhradě vč. DPH 33 097 Kč', o.vat);
    over('B6 bez dopravy/montaze/vice kusu se rozpis "zbozi bez DPH ..." neopakuje (prazdny, skryty)', o.detail === '' && !o.detailViditelny, { detail: o.detail, viditelny: o.detailViditelny });
    over('B7 banner je POD tabulkou', !!o.bannerPoTabulce, null);
    over('B8 radky profilu jsou slouceny do JEDNOHO radku na prurez: "Profil 30x30mm (alu)", celkem 17,5 m, 18 ks, 5 627 Kc (soucet 6 puvodnich radku)',
         o.profilRadku === 1 && o.profil && JSON.stringify(o.profil.bunky.slice(1)) === JSON.stringify(['Profil 30x30mm (alu)', 'celkem 17,5 m', '18 ks', '', '5 627 Kč']), o.profil);
    over('B9 pocet radku tabulky: 18 puvodnich polozek - 5 slucenych profilu = 13', o.pocetRadku === 13, o.pocetRadku);
    over('B10 soucet sloupce "Celkem" v tabulce = hlavni cena v banneru (27 353 Kc) - slouceni nic neztratilo', o.soucetCelkem === 27353, o.soucetCelkem);
    over('B11 slouceny radek nese vsech 6 skupin pro zvyrazneni ve 3D (data-group "2,3,4,5,6,7") a je klikaci', o.profil && o.profil.skupiny === '2,3,4,5,6,7' && /bom-row/.test(o.profil.trida), o.profil);
    over('B12 pod tabulkou je cena montaze vcetne sazby (volitelna sluzba, neni v cene): 20 % z 27 353 = 5 471 Kc bez DPH / 6 619 Kc vc. DPH',
         o.montaz === 'Montáž 20 % z ceny (volitelná služba, není v ceně): 5 471 Kč bez DPH / 6 619 Kč vč. DPH', o.montaz);
    over('B13 bez JS chyb', chyby.length === 0, chyby.slice(0, 2));
    // klik na slouceny radek zvyrazni vsech 6 skupin (chipy kusovniku na strance 3D) a druhy klik je vypne
    const klik = await page.evaluate(async () => {
      const aktivni = () => [...document.querySelectorAll('.bom-chip.active')].map(c => c.dataset.group);
      const tr = [...document.querySelectorAll('.slide.active tr.bom-row')].find(r => r.dataset.group.includes(','));
      const jedna = [...document.querySelectorAll('.slide.active tr.bom-row')].find(r => r.dataset.group === '0');
      tr.scrollIntoView({ block: 'center' });
      tr.click(); await new Promise(r => setTimeout(r, 200));
      const po1 = { radek: tr.classList.contains('active'), chipy: aktivni() };
      tr.click(); await new Promise(r => setTimeout(r, 200));
      const po2 = { radek: tr.classList.contains('active'), chipy: aktivni() };
      jedna.click(); await new Promise(r => setTimeout(r, 200));
      const po3 = { radek: jedna.classList.contains('active'), chipy: aktivni(), slouceny: tr.classList.contains('active') };
      return { po1, po2, po3 };
    });
    over('B14 klik na slouceny radek profilu zvyrazni vsech 6 skupin, druhy klik je vypne',
         klik.po1.radek && JSON.stringify(klik.po1.chipy.sort()) === JSON.stringify(['2', '3', '4', '5', '6', '7']) && !klik.po2.radek && klik.po2.chipy.length === 0, klik);
    over('B15 klik na obycejny radek (jedna skupina) funguje jako driv a slouceny radek zustane vypnuty', klik.po3.radek && JSON.stringify(klik.po3.chipy) === JSON.stringify(['0']) && !klik.po3.slouceny, klik);
    await browser.close();
  }

  // ---- C) svisle rolovani slidu funguje a posledni radek i cena jsou dosazitelne; hlavicka tabulky drzi nahore
  for (const [w, h, mobil] of [[1440, 900, false], [1024, 768, false], [768, 1024, false], [390, 844, true]]) {
    const { browser, page } = await otevriNabidku({ width: w, height: h, mobil });
    await naCenovouStranku(page);
    const pred = await page.evaluate(() => { const s = document.querySelector('.slide.active'); return { top: s.scrollTop, max: s.scrollHeight - s.clientHeight }; });
    await page.mouse.move(w / 2, h / 3);
    await page.mouse.wheel(0, 300);
    await page.waitForTimeout(350);
    const st = await page.evaluate(() => {
      const s = document.querySelector('.slide.active'), t = s.querySelector('table.items'), th = t.querySelector('thead th');
      const karty = getComputedStyle(t.querySelector('thead')).display === 'none';
      return { scrollTop: s.scrollTop, slideTop: Math.round(s.getBoundingClientRect().top), thTop: karty ? null : Math.round(th.getBoundingClientRect().top), karty };
    });
    over(`C ${w}px: slide se svisle rolovat kolem (kolecko mysi) - je co rolovat (${pred.max} px) a posune se`, pred.max > 0 && st.scrollTop > 0, { pred, st });
    if (!st.karty) over(`C ${w}px: hlavicka tabulky zustava nahore pri rolovani (sticky)`, Math.abs(st.thTop - st.slideTop) <= 2, st);
    await page.mouse.wheel(0, 20000);
    await page.waitForTimeout(400);
    const dno = await page.evaluate(() => {
      const s = document.querySelector('.slide.active'), sb = s.getBoundingClientRect();
      const banner = s.querySelector('.total-banner').getBoundingClientRect(), montaz = s.querySelector('#montazInfo').getBoundingClientRect();
      return { banner: Math.round(banner.bottom), montaz: Math.round(montaz.bottom), slideSpodek: Math.round(sb.bottom) };
    });
    over(`C ${w}px: po doroloovani je videt celkova cena i radek s montazi`, dno.banner <= dno.slideSpodek + 1 && dno.montaz <= dno.slideSpodek + 1, dno);
    await browser.close();
  }

  // ---- D) tisk zustava beze zmeny: tabulka (NE karty - ty jsou jen pro obrazovku, @media screen) se vsemi 6 sloupci
  {
    const { browser, page } = await otevriNabidku({ width: 1440, height: 900 });
    await naCenovouStranku(page);
    await page.emulateMedia({ media: 'print' });
    await page.setViewportSize({ width: 794, height: 1123 });
    await page.waitForTimeout(300);
    const m = await page.evaluate(MERENI);
    over('D tisk: tabulka (ne karty), 6 sloupcu v hlavicce i v radcich, nic nevybiha z papiru', !m.karty && m.pocetTh === 6 && m.bunekNaRadek === 6 && m.vpravo <= 795 && m.thMimo === 0, m);
    over('D tisk: sirsi sloupec cenove strany se v tisku neuplatni (padding/max-width z tiskoveho pravidla)', m.vlevo <= 8, m);
    await browser.close();
  }

  // ---- E) varianta bez cen v kusovniku (hide_bom_prices): 4 sloupce; radek dopravy; balne jako radek tabulky
  for (const [w, mobil] of [[1440, false], [768, false], [390, true]]) {
    const nab = NAB();
    nab.offer_options = Object.assign({}, nab.offer_options, { hide_bom_prices: true });
    const { browser, page, chyby } = await otevriNabidku({ width: w, height: 900, mobil, nabidka: nab });
    await naCenovouStranku(page);
    const m = await page.evaluate(MERENI);
    over(`E ${w}px bez cen v kusovniku: 4 sloupce, nic nepreteka a vse je videt`, m.bunekNaRadek === 4 && !m.preteka && !m.wrapPreteka && m.mimo === 0 && chyby.length === 0, m);
    await browser.close();
  }
  {
    const nab = NAB();
    nab.items.push({ name: 'Balné (3 %)', dim: '-', qty: '-', unit_price: null, total: 820, cross_section_mm: null, layer: null, mesh_group: null, product_id: null });
    nab.total_price += 820;
    nab.offer_options = Object.assign({}, nab.offer_options, { is_vehicle_assembly: false });
    const { browser, page, chyby } = await otevriNabidku({ width: 1440, height: 900, nabidka: nab });
    await naCenovouStranku(page);
    const o = await page.evaluate(() => {
      const txt = e => e ? e.textContent.replace(/[  ]/g, ' ').replace(/\s+/g, ' ').trim() : null;
      const t = document.querySelector('.slide.active table.items');
      const radky = [...t.querySelectorAll('tbody tr')].filter(tr => getComputedStyle(tr).display !== 'none');
      const balne = radky.find(tr => /^Balné/.test(txt(tr.children[1])));
      return { balne: balne ? [...balne.children].map(txt) : null, hodnota: txt(document.getElementById('totalBannerValue')), vat: txt(document.getElementById('totalBannerVat')), montaz: txt(document.getElementById('montazInfo')) };
    });
    over('E1 radek "Balne (3 %)" (dodava scena do novych nabidek) je normalni radek tabulky se svou cenou bez DPH', o.balne && o.balne[1] === 'Balné (3 %)' && o.balne[5] === '820 Kč', o);
    over('E2 balne je v hlavni cene (27 353 + 820 = 28 173 Kc bez DPH, vc. DPH 34 089 Kc) a montaz se pocita z ceny vc. balneho (20 % = 5 635 Kc)',
         o.hodnota === '28 173 Kč' && /k úhradě vč\. DPH 34 089 Kč/.test(o.vat) && /5 635 Kč bez DPH/.test(o.montaz), o);
    over('E3 bez JS chyb', chyby.length === 0, chyby.slice(0, 2));
    // radek dopravy: zobrazi se az pri zvolene doprave, ma jen 6 bunek a vejde se na obrazovku
    const dop = await page.evaluate(() => {
      const r = document.getElementById('deliveryRow');
      r.style.display = '';
      const vw = innerWidth, rc = r.getBoundingClientRect();
      return { bunek: r.children.length, vpravo: Math.round(rc.right), vw, ids: ['deliveryRowPriceVat', 'deliveryRowVat', 'deliveryRowTotalVat'].map(i => !!document.getElementById(i)) };
    });
    over('E4 radek dopravy: 6 bunek (bez DPH sloupcu), vejde se na obrazovku', dop.bunek === 6 && dop.vpravo <= dop.vw && dop.ids.every(x => x === false), dop);
    await browser.close();
  }

  // ---- F) jednotkove testy pomocnych funkci z nabidka-online.html (skutecny zdroj, atrapy jen pro formatovani)
  {
    const ctx = vm.createContext({
      Number, Math, String, parseInt, parseFloat, Array, Map, Object, Set, Intl,
      fmtCzk: v => (v == null ? '' : Math.round(v) + ' Kč'), fmtNetGross: v => `${Math.round(v)} bez / ${Math.round(v * 1.21)} s`,
      effectiveQty: p => (p && p.qty) || 1,
    });
    vm.runInContext(vytahniFunkci(HTML, 'pricingRowsOf') + '\n' + vytahniFunkci(HTML, 'montazJeVolba') + '\n' + vytahniFunkci(HTML, 'montazInfoText') + '\n' + vytahniFunkci(HTML, 'discountPctOf') + '\n' + vytahniFunkci(HTML, 'goodsNetAfterDiscount'), ctx);          // montazJeVolba: bot8 2026-10-06; discountPctOf/goodsNetAfterDiscount: sleva (bot16 2026-10-07) - montazInfoText pocita z ceny po sleve
    const prof = (len, qty, total, cs = [30, 30], name = 'Profil 30x30mm (alu)', g = 1) => ({ name, dim: len + ' mm', qty: qty + ' ks', unit_price: Math.round(total / qty), total, cross_section_mm: cs, layer: 'alu', mesh_group: g });
    const radky = ctx.pricingRowsOf([prof(1000, 2, 400, undefined, undefined, 1), prof(500, 4, 600, undefined, undefined, 2), prof(800, 1, 300, [40, 40], 'Profil 40x40mm (alu)', 3),
                                     { name: 'Deska', dim: '800 × 1200 mm', qty: '1 ks', unit_price: 1152, total: 1152, cross_section_mm: [null, null], layer: 'produkt', mesh_group: 4 },
                                     { name: 'Cena řezů', dim: '-', qty: '18 ks', unit_price: null, total: 900, cross_section_mm: null, layer: null, mesh_group: null }]);
    over('F1 pricingRowsOf: 2 delky 30x30 se slouci (6 ks, 4 m, 1000 Kc), 40x40 (jedna polozka), deska a sluzba zustanou',
         radky.length === 4 && radky[0].merged && radky[0].qty === 6 && radky[0].lenMm === 4000 && radky[0].total === 1000 && radky[0].groups.join() === '1,2'
         && !radky[1].merged && radky[1].it.name === 'Profil 40x40mm (alu)' && radky[2].it.name === 'Deska' && radky[3].it.name === 'Cena řezů' && radky[3].groups.length === 0, radky.map(r => r.merged ? 'sloucene' : r.it.name));
    const nerozpoznatelne = ctx.pricingRowsOf([prof(1000, 2, 400), { name: 'Profil 30x30mm (alu)', dim: '-', qty: '1 ks', unit_price: 5, total: 5, cross_section_mm: [30, 30], layer: 'alu', mesh_group: 9 }]);
    over('F2 pricingRowsOf: polozka bez rozpoznatelne delky se nesluci (zustane samostatna, nic se neztrati)', nerozpoznatelne.length === 2 && !nerozpoznatelne[0].merged && nerozpoznatelne[1].it.total === 5, nerozpoznatelne.length);
    over('F3 pricingRowsOf: prazdny/chybejici seznam nespadne', ctx.pricingRowsOf(undefined).length === 0 && ctx.pricingRowsOf([]).length === 0, null);
    const nab = { montaz_pct: 20, total_price: 10000, offer_options: {} };
    over('F4 montazInfoText: bezna nabidka -> "Montaz 20 % z ceny (volitelna sluzba, neni v cene)" s cenou 2 000 bez / 2 420 s', ctx.montazInfoText(nab, {}) === 'Montáž 20 % z ceny (volitelná služba, není v ceně): 2000 bez / 2420 s', ctx.montazInfoText(nab, {}));
    over('F5 montazInfoText: nabidka sestavy do auta -> "(volitelna sluzba, volba nize)"; po zvoleni montaze radek zmizi (je v souctu)',
         /volba níže/.test(ctx.montazInfoText({ ...nab, offer_options: { is_vehicle_assembly: true } }, {})) && ctx.montazInfoText({ ...nab, offer_options: { is_vehicle_assembly: true } }, { montaz_zvolena: true }) === '', null);
    over('F6 montazInfoText: bez procenta montaze nic, pri vice kusech spravne (2 ks -> 4 000)', ctx.montazInfoText({ ...nab, montaz_pct: 0 }, {}) === '' && /^Montáž.*4000 bez/.test(ctx.montazInfoText(nab, { qty: 2 })), ctx.montazInfoText(nab, { qty: 2 }));
  }

  // ---- G) sazba montaze zvolena pri vytvoreni nabidky (backend posila offer.montaz_pct = vlastni sazba nabidky, jinak ziva vychozi)
  {
    const zakl = NAB();
    const text = page => page.evaluate(() => (document.getElementById('montazInfo').textContent || '').replace(/[\u00a0\u202f]/g, ' ').replace(/\s+/g, ' ').trim());
    {
      const { browser, page, chyby } = await otevriNabidku({ width: 1440, height: 900, nabidka: { ...zakl, montaz_pct: 12.5 } });
      await naCenovouStranku(page);
      const o = await page.evaluate(() => ({ t: (document.getElementById('montazInfo').textContent || '').replace(/[\u00a0\u202f]/g, ' ').replace(/\s+/g, ' ').trim(),
        hlavni: document.getElementById('totalBannerValue').textContent.replace(/[\u00a0\u202f]/g, ' ').trim() }));
      over('G1 zvolena sazba 12,5 %: pod cenou "Montaz 12,5 % z ceny ...", castka 12,5 % z 27 353 = 3 419 Kc bez DPH / 4 137 Kc vc. DPH',
           o.t === 'Montáž 12,5 % z ceny (volitelná služba, není v ceně): 3 419 Kč bez DPH / 4 137 Kč vč. DPH', o.t);
      over('G2 hlavni cena celkem se montazi (volitelna sluzba) nemeni: 27 353 Kc bez DPH', o.hlavni === '27 353 Kč', o.hlavni);
      over('G3 bez JS chyb', chyby.length === 0, chyby.slice(0, 2));
      await browser.close();
    }
    {
      const { browser, page } = await otevriNabidku({ width: 1440, height: 900, nabidka: { ...zakl, montaz_pct: 0 } });
      await naCenovouStranku(page);
      const o = await page.evaluate(() => { const e = document.getElementById('montazInfo'); return { t: e.textContent.trim(), viditelne: getComputedStyle(e).display !== 'none' }; });
      over('G4 sazba 0 (bez montaze): pod cenou zadny radek montaze (prazdny a skryty)', o.t === '' && !o.viditelne, o);
      await browser.close();
    }
    {
      // sestava do auta + vlastni sazba 15 %: tlacitko "Montaz (+...)" se pocita z 15 %, po zvoleni je montaz v souctu banneru
      const { browser, page, chyby } = await otevriNabidku({ width: 1440, height: 900, nabidka: { ...zakl, montaz_pct: 15, offer_options: { ...(zakl.offer_options || {}), is_vehicle_assembly: true, montaz_pct: 15 } } });
      await naCenovouStranku(page);
      const pred = await page.evaluate(() => ({ tl: document.getElementById('montazOnBtn') ? document.getElementById('montazOnBtn').textContent.replace(/[\u00a0\u202f]/g, ' ').trim() : null,
        hlavni: document.getElementById('totalBannerValue').textContent.replace(/[\u00a0\u202f]/g, ' ').trim(), info: document.getElementById('montazInfo').textContent.replace(/[\u00a0\u202f]/g, ' ').replace(/\s+/g, ' ').trim() }));
      over('G5 sestava do auta, sazba 15 %: tlacitko "Montaz (+4 103 Kc bez DPH / 4 965 Kc vc. DPH)" (15 % z 27 353 = 4 102,95; x 1,21 = 4 964,57)',
           pred.tl === 'Montáž (+4 103 Kč bez DPH / 4 965 Kč vč. DPH)', pred);
      over('G6 pred zvolenim montaze je v radku pod cenou "Montaz 15 % z ceny (volitelna sluzba, volba nize)" a hlavni cena je beze zmeny',
           /^Montáž 15 % z ceny \(volitelná služba, volba níže\): 4 103 Kč bez DPH/.test(pred.info) && pred.hlavni === '27 353 Kč', pred);
      await page.evaluate(() => { document.getElementById('montazOnBtn').scrollIntoView({ block: 'center' }); });
      await page.click('#montazOnBtn');
      await page.waitForTimeout(300);
      const po = await page.evaluate(() => ({ hlavni: document.getElementById('totalBannerValue').textContent.replace(/[\u00a0\u202f]/g, ' ').trim(),
        vat: document.getElementById('totalBannerVat').textContent.replace(/[\u00a0\u202f]/g, ' ').trim(), detail: document.getElementById('totalBannerDetail').textContent.replace(/[\u00a0\u202f]/g, ' ').trim(),
        info: document.getElementById('montazInfo').textContent.trim() }));
      over('G7 po zvoleni montaze: hlavni cena 27 353 + 4 102,95 = 31 456 Kc bez DPH (15 %, ne vychozich 20 %), k uhrade vc. DPH 38 062 Kc, radek montaze zmizi',
           po.hlavni === '31 456 Kč' && /k úhradě vč\. DPH 38 062 Kč/.test(po.vat) && /montáž bez DPH 4 103 Kč/.test(po.detail) && po.info === '', po);
      over('G8 bez JS chyb (sestava do auta)', chyby.length === 0, chyby.slice(0, 2));
      await browser.close();
    }
  }

  const ok = vysl.filter(Boolean).length;
  console.log(`\nVYSLEDEK online nabidka - cenova tabulka a celkova cena: ${ok}/${vysl.length} OK`);
  process.exit(ok === vysl.length ? 0 : 1);
})().catch(e => { console.error('TEST SPADL:', e.message); process.exit(2); });
