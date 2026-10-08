// Pouziti: OUT=<slozka> JSONDIR=<slozka s <cislo>.json z verejny_json.py> CISLO=Logiman0133 node realna_nabidka.js  (veta o homologaci na posledni strane, na obrazovce i v PDF; bot16 2026-10-07)
// Realna nabidka Logiman0133 (verejny JSON z ziveho API, jen cteni) v SKUTECNE strance webapp/nabidka-online.html: veta o homologaci na posledni strane + v PDF.
const fs = require('fs'), path = require('path'), cp = require('child_process');
const { otevriNabidku } = require('/opt/konfigurator/scripts/2026-10-06_nabidka_montaz_polozky_testy/harness');
const OUT = process.env.OUT, CISLO = process.env.CISLO || 'Logiman0133';
const nabidka = JSON.parse(fs.readFileSync(path.join(process.env.JSONDIR, CISLO + '.json'), 'utf8'));
const TEXT = 'Zápis do elektronického technického průkazu provádíme na základě Homologace HP-0579';
(async () => {
  for (const okno of [{ width: 1920, height: 1080, k: 'd' }, { width: 390, height: 844, k: 'm' }]) {
    const { browser, page, chyby } = await otevriNabidku({ width: okno.width, height: okno.height, nabidka });
    const stranky = await page.evaluate(() => [...document.querySelectorAll('.slide')].map(s => s.dataset.key));
    let klic = null;
    for (let i = 0; i < 20; i++) { klic = await page.evaluate(() => (document.querySelector('.slide.active') || { dataset: {} }).dataset.key); if (klic === 'closing') break; await page.keyboard.press('ArrowRight'); await page.waitForTimeout(450); }
    await page.waitForTimeout(800);
    const info = await page.evaluate(() => { const e = document.querySelector('.slide.active .closing-homologace'); const s = document.querySelector('.slide.active'); const r = e && e.getBoundingClientRect(); return { aktivni: s && s.dataset.key, veta: e ? e.textContent : null, viditelna: !!(r && r.width > 0 && r.height > 0), vOkne: !!(r && r.bottom <= innerHeight + 1 && r.top >= 0), textSlideDlouhy: s ? s.innerText.length : 0, opts: (window.currentOffer && window.currentOffer.offer_options && window.currentOffer.offer_options.is_vehicle_assembly) }; }).catch(e => ({ chyba: String(e) }));
    console.log(JSON.stringify({ okno: okno.k, stranky, klic, info, chyby: (chyby || []).slice(0, 3) }));
    await page.screenshot({ path: path.join(OUT, `realna_${CISLO}_${okno.k}.png`) });
    if (okno.k === 'd') {
      for (const [nazev, fn] of [['strucne', 'tiskPdf'], ['kompletni', 'tiskPlny']]) {
        const ex = await page.evaluate(n => typeof window[n], fn);
        const f = path.join(OUT, `realna_${CISLO}_${nazev}.pdf`);
        try {
          await page.evaluate(n => { document.body.classList.toggle('print-full', n === 'tiskPlny'); }, fn);
          await page.emulateMedia({ media: 'print' }); await page.pdf({ path: f, format: 'A4', landscape: true, printBackground: true });
          await page.emulateMedia({ media: 'screen' }); await page.evaluate(() => document.body.classList.remove('print-full'));
          const txt = cp.execSync(`pdftotext "${f}" - 2>/dev/null`).toString();
          console.log(JSON.stringify({ pdf: nazev, funkce: ex, vetaVPdf: txt.includes('Homologace HP-0579'), stranOdhad: (cp.execSync(`pdfinfo "${f}" | grep Pages`).toString().trim()) }));
        } catch (e) { console.log('PDF chyba', nazev, String(e).slice(0, 120)); }
      }
    }
    await browser.close();
  }
})().catch(e => { console.error('CHYBA', e); process.exit(2); });
