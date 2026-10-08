// Online nabidka: banner "Celkova cena (bez DPH)" - popisek a hlavni cena jsou JEDEN radek a STEJNE pismo, obojí zelene (bot16, 2026-10-06).
// Robert: "je matouci, zda je zelena cena bez DPH. Musi byt i leva cast zelena, ktere se to tyka, a nejlepe na stejnem radku stejnym pismem".
// PUVODNE: popisek byl sedy 13px bezpatkove pismo vlevo nahore, cena velka zelena mono vpravo uprostred vysky -> nebylo poznat, ze zelena castka je bez DPH.
// SKUTECNA stranka webapp/nabidka-online.html v Chromiu proti falesnemu serveru (harness_nabidka.js z testu tabulky cen, page.route, zadna DB/sit).
// Spusteni:  node test_nabidka_cena_banner.js    (SIRKY=390,1400 = jen vybrane sirky)
// Kandidat pred nasazenim: NABIDKA_HTML=/cesta/nabidka-online.html node test_nabidka_cena_banner.js
// Mutacni kontrola: NABIDKA_HTML=<puvodni verze> MUSI selhat (sedy popisek jinym pismem, ne na jednom radku s cenou).
const fs = require('fs');
const path = require('path');
const { otevriNabidku, naCenovouStranku } = require('../2026-10-01_nabidka_tabulka_cen_testy/harness_nabidka');

const UKAZKA = JSON.parse(fs.readFileSync(path.join(__dirname, '../2026-10-01_nabidka_tabulka_cen_testy/ukazka_nabidky.json'), 'utf8'));
const KONFIG = JSON.parse(fs.readFileSync(path.join(__dirname, '../2026-10-06_nabidka_cover_testy/fixture_nabidka_z_konfigurace.json'), 'utf8'));
const SIRKY = process.env.SIRKY ? process.env.SIRKY.split(',').map(Number)
  : [320, 360, 390, 430, 540, 640, 641, 720, 768, 900, 1024, 1280, 1400, 1920, 2560];
const ZELENA = 'rgb(47, 224, 122)';                  // --accent-glow
const vysl = [];
const over = (nazev, podminka, detail) => { vysl.push(!!podminka); console.log((podminka ? 'OK   ' : 'FAIL ') + nazev + (podminka ? '' : '  -> ' + JSON.stringify(detail))); };
const norm = s => (s || '').replace(/[  ]/g, ' ').replace(/\s+/g, ' ').trim();

// mereni banneru (bezi ve strance)
const MERENI = () => {
  const b = document.querySelector('.slide.active .total-banner');
  const label = b.querySelector('.label'), val = b.querySelector('#totalBannerValue');
  const det = b.querySelector('#totalBannerDetail'), vat = b.querySelector('#totalBannerVat');
  const cs = e => getComputedStyle(e);
  const radky = e => { const r = document.createRange(); r.selectNodeContents(e); return [...r.getClientRects()].filter(x => x.width > 0 && x.height > 0); };
  const lr = radky(label), vr = radky(val);
  const topL = Math.min(...lr.map(x => x.top));
  const prvniL = lr.filter(x => Math.abs(x.top - topL) < 2);        // 1. radek popisku (bez dalsich radku po zalomeni)
  const bb = b.getBoundingClientRect(), vb = val.getBoundingClientRect(), lb = label.getBoundingClientRect();
  const pad = parseFloat(cs(b).paddingRight) || 0;
  const mainEl = b.querySelector('.total-banner-main');
  const mainB = mainEl ? mainEl.getBoundingClientRect() : null;
  const f = e => ({ fam: cs(e).fontFamily, w: cs(e).fontWeight, size: cs(e).fontSize, color: cs(e).color, stin: cs(e).textShadow });
  const detViditelny = cs(det).display !== 'none', db = det.getBoundingClientRect(), tb = vat.getBoundingClientRect();
  return {
    vw: innerWidth, popisek: label.textContent.replace(/\s+/g, ' ').trim(), hodnota: val.textContent.trim(),
    fL: f(label), fV: f(val), fD: f(det), fT: f(vat),
    radekL: { top: Math.min(...prvniL.map(x => x.top)), bottom: Math.max(...prvniL.map(x => x.bottom)) },
    radekV: { top: Math.min(...vr.map(x => x.top)), bottom: Math.max(...vr.map(x => x.bottom)) },
    radkuPopisku: new Set(lr.map(x => Math.round(x.top))).size,
    popisekPravy: Math.max(...lr.map(x => x.right)), hodnotaLevy: vb.left, hodnotaPravy: vb.right,
    bannerPravy: bb.right - pad, bannerPreteka: b.scrollWidth > b.clientWidth + 1, strankaPreteka: document.documentElement.scrollWidth > innerWidth + 1,
    popisekLevy: lb.left, mainDole: mainB ? mainB.bottom : lb.bottom,
    detViditelny, detNahore: db.top, detLevy: db.left, vatNahore: tb.top, vatLevy: tb.left,
    detPravy: db.right, vatPravy: tb.right, bannerVyska: bb.height,
  };
};

function kontrola(popis, m, sirka, cekejMalyPopisek) {
  const ctx = `${popis} ${sirka}px`;
  over(`A1 ${ctx}: popisek i hlavni cena maji stejne pismo (rodina, tloustka) a obojí je zelene`, m.fL.fam === m.fV.fam && m.fL.w === m.fV.w && m.fL.color === ZELENA && m.fV.color === ZELENA && m.fL.stin === m.fV.stin, { fL: m.fL, fV: m.fV });
  over(`A1b ${ctx}: stejna velikost pisma popisku a ceny`, m.fL.size === m.fV.size, { fL: m.fL.size, fV: m.fV.size });
  over(`A2 ${ctx}: popisek a cena jsou na jednom radku (1. radek popisku a cena ve stejne vysce)`, Math.abs(m.radekL.top - m.radekV.top) <= 1.5 && Math.abs(m.radekL.bottom - m.radekV.bottom) <= 1.5, { L: m.radekL, V: m.radekV });
  // od 900 px (sloupec nabidky >= 714 px) se popisek vejde na jeden radek v kazdem beznem monospace pismu (0,55-0,62 em); mezi 641 a 899 px (cenova stranka ma 72px okraje pro sipky)
  // a na telefonech se muze zalomit na "Celkova cena" / "(bez DPH)" - cena ale vzdy zustane u 1. radku (A2) a popisek se nikdy nerozpadne na vic nez 2 radky (320 px: 3)
  if (sirka >= 900) over(`A3 ${ctx}: na siroke obrazovce je popisek na JEDNOM radku`, m.radkuPopisku === 1, m.radkuPopisku);
  else over(`A3 ${ctx}: popisek se zalomi nejvyse na ${sirka <= 320 ? 3 : 2} radky (Celkova cena / (bez DPH)), cena zustane u 1. radku`, m.radkuPopisku <= (sirka <= 320 ? 3 : 2), m.radkuPopisku);
  over(`A4 ${ctx}: nic nepreteka (banner, stranka) a popisek se nepreleza s cenou, cena je uvnitr banneru`, !m.bannerPreteka && !m.strankaPreteka && m.popisekPravy <= m.hodnotaLevy + 0.5 && m.hodnotaPravy <= m.bannerPravy + 1, { pp: m.popisekPravy, hl: m.hodnotaLevy, hp: m.hodnotaPravy, bp: m.bannerPravy, bp2: m.bannerPreteka, sp: m.strankaPreteka });
  over(`A5 ${ctx}: rozpis (DPH, k uhrade vc. DPH) je POD radkem popisek+cena, zarovnany vlevo s popiskem, a NENI zeleny`, m.vatNahore >= m.mainDole - 1 && Math.abs(m.vatLevy - m.popisekLevy) <= 1 && (!m.detViditelny || (m.detNahore >= m.mainDole - 1 && Math.abs(m.detLevy - m.popisekLevy) <= 1)) && m.fT.color !== ZELENA && m.fD.color !== ZELENA, { m: { mainDole: m.mainDole, vatNahore: m.vatNahore, vatLevy: m.vatLevy, popisekLevy: m.popisekLevy, colT: m.fT.color, colD: m.fD.color } });
  over(`A6 ${ctx}: text popisku zustal "Celková cena (bez DPH)"`, m.popisek === 'Celková cena (bez DPH)', m.popisek);
}

(async () => {
  // ---- A) nabidka s jednou polozkou (starsi typ, skutecna data z DB): vsechny sirky
  console.log('== A) prochazka sirkami (ukazka z DB)');
  for (const w of SIRKY) {
    const mobil = w <= 640;
    const { browser, page, chyby } = await otevriNabidku({ width: w, height: mobil ? 844 : 900, mobil, nabidka: JSON.parse(JSON.stringify(UKAZKA)) });
    await naCenovouStranku(page);
    kontrola('ukazka', await page.evaluate(MERENI), w);
    over(`A0 ukazka ${w}px: zadne chyby JS ve strance`, chyby.length === 0, chyby.slice(0, 2));
    await browser.close();
  }

  // ---- B) nabidka z konfigurace (montaz, mnozstvi): zivy prepocet pri zmene mnozstvi drzi stejny radek
  console.log('== B) zivy prepocet (nabidka z konfigurace): zmena mnozstvi');
  for (const w of [1400, 390]) {
    const mobil = w <= 640;
    const { browser, page } = await otevriNabidku({ width: w, height: mobil ? 844 : 900, mobil, nabidka: JSON.parse(JSON.stringify(KONFIG)) });
    await naCenovouStranku(page);
    const pred = await page.evaluate(MERENI);
    kontrola('konfigurace', pred, w);
    await page.fill('#qtyInput', '3'); await page.dispatchEvent('#qtyInput', 'change'); await page.waitForTimeout(500);
    const po = await page.evaluate(MERENI);
    const detail = await page.evaluate(() => document.getElementById('totalBannerDetail').textContent);
    over(`B1 konfigurace ${w}px: po zmene mnozstvi na 3 ks se cena prepocitala (${pred.hodnota} -> ${po.hodnota}) a rozpis ukazuje "3 ks"`, po.hodnota !== pred.hodnota && /3 ks/.test(detail), { pred: pred.hodnota, po: po.hodnota, detail });
    kontrola('konfigurace po zmene mnozstvi', po, w);
    await browser.close();
  }

  // ---- C) nejhorsi pripad: velka cena a dlouhy rozpis na uzkem telefonu
  console.log('== C) velka cena + dlouhy rozpis na uzkych telefonech');
  // realna velka cena (7 mist, 1 234 568 Kc) a krajni pripad (8 mist, 12 345 678 Kc): nic nepreteka, cena zustava u 1. radku popisku
  for (const w of [320, 360, 390]) {
    for (const [nazev, cena, maxRadku] of [['7 mist', '1 234 568 Kč', w <= 320 ? 3 : 2], ['8 mist (krajni pripad)', '12 345 678 Kč', 3]]) {
      const { browser, page } = await otevriNabidku({ width: w, height: 800, mobil: true, nabidka: JSON.parse(JSON.stringify(KONFIG)) });
      await naCenovouStranku(page);
      await page.evaluate(c => {
        document.getElementById('totalBannerValue').textContent = c;
        document.getElementById('totalBannerDetail').textContent = '3 ks × 12 345 678 Kč bez DPH 37 037 034 Kč + doprava (Toptrans) bez DPH 1 234 Kč + montáž bez DPH 4 444 444 Kč';
        document.getElementById('totalBannerVat').textContent = 'DPH 21 % 8 888 888 Kč · k úhradě vč. DPH 53 888 888 Kč';
      }, cena);
      await page.waitForTimeout(200);
      const m = await page.evaluate(MERENI);
      over(`C1 ${w}px, cena ${nazev} (${cena}): popisek i cena u sebe na 1. radku, nic nepreteka, popisek max ${maxRadku} radky, obojí zelene`, Math.abs(m.radekL.top - m.radekV.top) <= 1.5 && !m.bannerPreteka && !m.strankaPreteka && m.popisekPravy <= m.hodnotaLevy + 0.5 && m.hodnotaPravy <= m.bannerPravy + 1 && m.radkuPopisku <= maxRadku && m.fL.color === ZELENA && m.fV.color === ZELENA, { L: m.radekL, V: m.radekV, radku: m.radkuPopisku, pp: m.popisekPravy, hl: m.hodnotaLevy, hp: m.hodnotaPravy, bp: m.bannerPravy, byt: m.bannerPreteka, str: m.strankaPreteka });
      await browser.close();
    }
  }

  // ---- D) tisk (A4): stejny radek, nic nepreteka
  console.log('== D) tisk (A4 794 px)');
  {
    const { browser, page } = await otevriNabidku({ width: 794, height: 1123, nabidka: JSON.parse(JSON.stringify(KONFIG)) });
    await naCenovouStranku(page);
    await page.emulateMedia({ media: 'print' }); await page.waitForTimeout(400);
    const m = await page.evaluate(MERENI);
    over('D1 tisk: popisek i cena zelene, stejne pismo, na jednom radku, nic nepreteka', m.fL.fam === m.fV.fam && m.fL.color === ZELENA && m.fV.color === ZELENA && Math.abs(m.radekL.top - m.radekV.top) <= 1.5 && !m.bannerPreteka && m.popisekPravy <= m.hodnotaLevy + 0.5 && m.hodnotaPravy <= m.bannerPravy + 1, m);
    await browser.close();
  }

  console.log(`\nVYSLEDEK banner celkove ceny: ${vysl.filter(Boolean).length}/${vysl.length} OK`);
  process.exit(vysl.every(Boolean) ? 0 : 1);
})().catch(e => { console.error('CHYBA TESTU:', e.message); process.exit(2); });
