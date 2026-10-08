// Blok "Priklady nasich realizaci" v ONLINE NABIDCE (bot16, 2026-10-07; Robert: "v kazde sestave do aut i stolu a v online nabidce musi byt ukazana realna fotografie 4ks a odkaz na fotogalerii, ty 4 fotky se musi
// tocit, kolovat, tzn v kazde nabidce budou jine"). SKUTECNA stranka webapp/nabidka-online.html v Chromiu (harness bot8), ZIVA galerie (read-only) + skutecne soubory fotek z disku, zadne zapisy.
// Nabidka pro AUTO (vc. Vandr) = fotogalerie vestaveb, stul z generatoru (kod STL-) = fotogalerie stolu, ostatni nabidky (scena, dopravnik DOP-) BEZ bloku; fotky se nacitaji line (az na cenove / zaverecne
// strance), tisk: strucne PDF bez fotek, kompletni PDF s nimi (tisk pocka na nacteni). Kandidat: NABIDKA_HTML=/cesta/nabidka-online.html node test_realizace_nabidka.js   (puvodni stranka MUSI selhat)
const fs = require('fs'), path = require('path'), os = require('os');
const { execFileSync } = require('child_process');
const { otevriNabidku, vzorovaNabidka } = require('../2026-10-06_nabidka_montaz_polozky_testy/harness');
const { nactiGalerie, galerieRoute } = require('./harness_realizace');
const vysl = [];
const over = (nazev, podminka, detail) => { vysl.push(!!podminka); console.log((podminka ? 'OK   ' : 'FAIL ') + nazev + (podminka ? '' : '  -> ' + JSON.stringify(detail).slice(0, 400))); };
const KLIC = page => page.evaluate(() => (document.querySelector('.slide.active') || { dataset: {} }).dataset.key);
const TMP = fs.mkdtempSync(path.join(os.tmpdir(), 'rf_nab_'));
const sh = (cmd, args) => execFileSync(cmd, args, { encoding: 'utf8', maxBuffer: 80e6 });

(async () => {
  const G = await nactiGalerie();
  const vandr = (cislo, extra = {}) => vzorovaNabidka(d => { d.offer_number = cislo; d.offer_options = Object.assign({}, d.offer_options, { vandr_single_drawing: true, is_vehicle_assembly: true }, extra); });
  const stul = (cislo, kod) => vzorovaNabidka(d => { d.offer_number = cislo; d.source = 'configurator'; d.configuration = { kod, qty: 1, delivery_country: 'CZ', souhrn: [], bom: [] }; });
  async function otevri(nabidka, opt = {}) {
    const pozadavky = [];
    const r = await otevriNabidku({ width: opt.sirka || 1280, height: 900, nabidka, trasy: async (route, { p }) => {
      if (p === '/api/gallery') pozadavky.push(Date.now());
      if (p === '/js/realizace-foto.js' && process.env.RF_JS) { route.fulfill({ status: 200, contentType: 'text/javascript', body: fs.readFileSync(process.env.RF_JS) }); return true; }          // kandidat modulu pred nasazenim
      return galerieRoute(route, new URL(route.request().url()), G, opt);
    } });
    r.pozadavky = pozadavky; return r;
  }
  async function naStranku(page, klic) { for (let i = 0; i < 14 && (await KLIC(page)) !== klic; i++) { await page.keyboard.press('ArrowRight'); await page.waitForTimeout(450); } await page.waitForTimeout(900); }
  const blok = page => page.evaluate(() => {
    const w = document.getElementById('closingRealizace'); if (!w) return { existuje: false };
    const imgs = [...w.querySelectorAll('.rf-foto img')], a = w.querySelector('a.rf-link');
    return { existuje: true, skryty: w.hidden, viditelny: !w.hidden && getComputedStyle(w).display !== 'none' && w.getBoundingClientRect().height > 0, nadpis: (w.querySelector('h3') || {}).textContent, fotek: imgs.length, nactene: imgs.filter(i => i.complete && i.naturalWidth > 0).length, ids: [...w.querySelectorAll('.rf-foto')].map(b => b.dataset.rfId).join(','), odkaz: a && { href: a.getAttribute('href'), text: a.textContent.trim(), target: a.target }, pred: (() => { const h = document.querySelector('.closing .closing-homologace'); return h ? (w.compareDocumentPosition(h) & Node.DOCUMENT_POSITION_PRECEDING) !== 0 : null; })() };
  });

  // ---- A) nabidka pro auto (Vandr) = vestavby; lina nacitani
  let { browser, page, chyby, pozadavky } = await otevri(vandr('Logiman0133'));
  over('A1 po otevreni nabidky (uvodni strana) se galerie NENACITA (prvni zobrazeni se nezpomaluje)', pozadavky.length === 0, pozadavky.length);
  await naStranku(page, 'pricing');
  over('A2 pri vstupu na cenovou stranku se galerie nacte dopredu (aby zaver nebyl prazdny)', pozadavky.length >= 1, pozadavky.length);
  await naStranku(page, 'closing');
  let b = await blok(page);
  over('A3 Vandr nabidka: na zaverecne strane je blok "Priklady nasich realizaci", 4 REALNE fotky vestaveb se nacetly a odkaz na fotogalerii vestaveb', b.viditelny && b.nadpis === 'Příklady našich realizací' && b.fotek === 4 && b.nactene === 4 && b.odkaz && b.odkaz.href === '/realizace.html?category=vestavby_dodavek' && b.odkaz.text === 'Zobrazit fotogalerii vestaveb →' && b.odkaz.target === '_blank', b);
  over('A4 veta o homologaci je NAD blokem fotek (Robert: musi byt videt hned, ne pod fotkami; blok fotek je az za ni)', b.pred === true, b.pred);
  const setA = b.ids;
  // lightbox na strance nabidky: sipky patri lightboxu, nepřepínají stránky
  await page.locator('#closingRealizace .rf-foto').first().click();
  await page.keyboard.press('ArrowLeft'); await page.waitForTimeout(300);
  const behem = await KLIC(page);
  await page.keyboard.press('Escape'); await page.waitForTimeout(300);
  over('A5 lightbox v nabidce: sipka doleva behem zvetseni NEPREPNE stranku nabidky (zustava "closing"), po Esc se zavre', behem === 'closing' && !(await page.evaluate(() => document.querySelector('.rf-lb').classList.contains('rf-open'))), behem);
  await page.keyboard.press('ArrowLeft'); await page.waitForTimeout(700);
  over('A6 po zavreni lightboxu sipky zase prepinaji stranky nabidky', (await KLIC(page)) !== 'closing', await KLIC(page));
  if (process.env.SNIMKY) { await page.keyboard.press('ArrowRight'); await page.waitForTimeout(900); await page.screenshot({ path: path.join(process.env.SNIMKY, 'nabidka_auto_zaver.png') }); }
  over('A7 bez JS chyb', chyby.length === 0, chyby.slice(0, 3));
  await browser.close();

  // ---- B) jina nabidka = jine fotky; stul z generatoru = fotogalerie stolu
  ({ browser, page } = await otevri(vandr('Logiman0140')));
  await naStranku(page, 'closing'); b = await blok(page);
  over('B1 JINA nabidka (Logiman0140) ma JINE 4 fotky nez Logiman0133 (kazda nabidka jine)', b.fotek === 4 && b.ids !== setA, [setA, b.ids]);
  await browser.close();
  ({ browser, page, chyby } = await otevri(stul('Logiman0141', 'STL-ABCDEF')));
  await naStranku(page, 'closing'); b = await blok(page);
  over('B2 stul z generatoru (kod STL-): blok s 4 fotkami STOLU a odkazem na fotogalerii stolu', b.viditelny && b.fotek === 4 && b.nactene === 4 && b.odkaz.href === '/realizace.html?category=realizace_stolu' && b.odkaz.text === 'Zobrazit fotogalerii stolů →', b);
  if (process.env.SNIMKY) await page.screenshot({ path: path.join(process.env.SNIMKY, 'nabidka_stul_zaver.png') });
  await browser.close();

  // ---- C) nabidky bez bloku
  for (const [nazev, nab] of [['nabidka ze sceny (ne auto, ne stul)', vzorovaNabidka()], ['dopravnik z generatoru (kod DOP-)', stul('Logiman0142', 'DOP-123456')]]) {
    let { browser: br, page: pg, pozadavky: pz } = await otevri(nab);
    await naStranku(pg, 'closing'); const bb = await blok(pg);
    over(`C ${nazev}: BEZ bloku realizaci a galerie se vubec nenacita`, !bb.existuje && pz.length === 0, [bb, pz.length]);
    await br.close();
  }

  // ---- D) chyba galerie = blok se nezobrazi, nabidka funguje
  ({ browser, page, chyby } = await otevri(vandr('Logiman0143'), { galerieChyba: true }));
  await naStranku(page, 'closing'); b = await blok(page);
  over('D galerie nedostupna (500): blok zustane skryty, zaver nabidky (kontakty, homologace) funguje', b.existuje && b.skryty && (await page.locator('.closing .closing-homologace').count()) === 1 && chyby.length === 0, [b, chyby.slice(0, 2)]);
  await browser.close();

  // ---- E) PDF: strucne bez fotek, kompletni s fotkami; tisk pocka na nacteni obrazku
  for (const rezim of ['short', 'full']) {
    ({ browser, page } = await otevri(vandr('Logiman0133'), { zpozdeniObrazku: 350 }));
    await page.evaluate(() => { window.__tisk = []; window.print = () => { window.__tisk.push({ trida: [...document.body.classList], nactene: [...document.querySelectorAll('#closingRealizaceBody img')].filter(i => i.complete && i.naturalWidth > 0).length, vsech: document.querySelectorAll('#closingRealizaceBody img').length }); }; });
    await page.click('#btnPdfDownload'); await page.click(`#pdfMenu button[data-pdf="${rezim}"]`);
    await page.waitForTimeout(rezim === 'full' ? 2500 : 400);
    const t = await page.evaluate(() => window.__tisk);
    if (rezim === 'full') over('E1 kompletni PDF: tisk se spusti AZ po nacteni vsech 4 fotek (v okamziku tisku jsou nactene 4 z 4)', t.length === 1 && t[0].trida.includes('print-full') && t[0].vsech === 4 && t[0].nactene === 4, t);
    else over('E2 strucne PDF: tisk hned, bez tridy print-full', t.length === 1 && !t[0].trida.includes('print-full'), t);
    await page.emulateMedia({ media: 'print' }); await page.waitForTimeout(500);
    const f = path.join(TMP, rezim + '.pdf');
    await page.pdf({ path: f, format: 'A4', printBackground: true, margin: { top: '10mm', bottom: '10mm', left: '8mm', right: '8mm' } });
    const text = sh('pdftotext', ['-layout', f, '-']);
    if (rezim === 'full') {
      const n = parseInt(/Pages:\s+(\d+)/.exec(sh('pdfinfo', [f]))[1], 10); let stranaP = 0;
      for (let i = 1; i <= n; i++) if (/Příklady našich realizací/.test(sh('pdftotext', ['-f', String(i), '-l', String(i), f, '-']))) stranaP = i;
      const obr = stranaP ? sh('pdfimages', ['-list', '-f', String(stranaP), '-l', String(stranaP), f]).split('\n').filter(l => /^\s*\d+\s+\d+\s+image/.test(l)).length : 0;
      over('E3 kompletni PDF obsahuje "Priklady nasich realizaci", odkaz "Zobrazit fotogalerii vestaveb" a na teto strane >= 4 obrazky (fotky)', stranaP > 0 && /Zobrazit fotogalerii vestaveb/.test(text) && obr >= 4, { stranaP, obr });
    } else over('E4 strucne PDF zustava strucne: bez bloku realizaci a bez fotek', !/Příklady našich realizací|Zobrazit fotogalerii/.test(text), text.slice(-300));
    await browser.close();
  }
  fs.rmSync(TMP, { recursive: true, force: true });
  const ok = vysl.filter(Boolean).length;
  console.log(`\nVYSLEDEK realizace v online nabidce: ${ok}/${vysl.length} OK`);
  process.exit(ok === vysl.length ? 0 : 1);
})().catch(e => { console.error('TEST SPADL:', e); process.exit(2); });
