// Pouziti: OUT=<slozka> JSONDIR=<slozka s Logiman0133.json> node rozlozeni_posledni_strany.js  (kde lezi veta o homologaci vuci oknu pri 7 velikostech obrazovky, s fotkami realizaci i bez; bot16 2026-10-07)
// Realna nabidka Logiman0133 + zive fotky: kde na posledni strane lezi veta o homologaci vuci oknu (bez rolovani) pri ruznych velikostech obrazovky.
const fs = require('fs'), path = require('path');
const { otevriNabidku } = require('/opt/konfigurator/scripts/2026-10-06_nabidka_montaz_polozky_testy/harness');
const { nactiGalerie, galerieRoute } = require('/opt/konfigurator/scripts/2026-10-07_realizace_foto_testy/harness_realizace');
const OUT = process.env.OUT; const nabidka = JSON.parse(fs.readFileSync(path.join(process.env.JSONDIR, 'Logiman0133.json'), 'utf8'));
(async () => {
  const G = await nactiGalerie();
  for (const [w, h] of [[1920, 1080], [1536, 864], [1440, 900], [1366, 768], [1280, 720], [390, 844], [360, 740]]) {
    for (const fotky of [true, false]) {
      const { browser, page } = await otevriNabidku({ width: w, height: h, nabidka, trasy: async (route) => fotky ? galerieRoute(route, new URL(route.request().url()), G, {}) : (new URL(route.request().url()).pathname === '/api/gallery' ? (route.fulfill({ status: 500, body: '{}' }), true) : false) });
      for (let i = 0; i < 14; i++) { const k = await page.evaluate(() => (document.querySelector('.slide.active') || { dataset: {} }).dataset.key); if (k === 'closing') break; await page.keyboard.press('ArrowRight'); await page.waitForTimeout(400); }
      await page.waitForTimeout(1800);
      const m = await page.evaluate(() => { const s = document.querySelector('.slide.active'), e = s.querySelector('.closing-homologace'), r = e.getBoundingClientRect(); const rb = s.querySelector('#closingRealizace'); return { slideH: s.clientHeight, slideScrollH: s.scrollHeight, scrolluje: s.scrollHeight > s.clientHeight + 2, vetaTop: Math.round(r.top), vetaBottom: Math.round(r.bottom), okno: innerHeight, vetaVidetBezRolovani: r.bottom <= innerHeight && r.top >= 0, fotekViditelne: rb ? !rb.hidden : null, fotekVyska: rb && !rb.hidden ? Math.round(rb.getBoundingClientRect().height) : 0 }; });
      console.log(`${w}x${h} fotky=${fotky ? 'ANO' : 'NE '}`, JSON.stringify(m));
      if (fotky && (w === 1366 || w === 390 || w === 1920)) await page.screenshot({ path: path.join(OUT, `rozlozeni_${w}.png`) });
      await browser.close();
    }
  }
})().catch(e => { console.error('CHYBA', e); process.exit(2); });
