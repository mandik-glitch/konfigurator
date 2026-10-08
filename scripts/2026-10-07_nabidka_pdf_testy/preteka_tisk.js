// Pouziti: JSONDIR=<slozka s Logiman0133.json> node preteka_tisk.js  (TISKOVY rezim na telefonu: table.items ma min. sirku ~423 px -> scrollWidth 427-428 pri okne 360-412 = stopa k orezu PDF z telefonu; na obrazovce preteceni neni)
// Totez v TISKOVEM rezimu (emulateMedia print) na telefonu: ktere prvky prekracuji sirku okna (scrollWidth 428 pri 412, 427 pri 390)?
const fs = require('fs'), path = require('path');
const { otevriNabidku } = require('/opt/konfigurator/scripts/2026-10-06_nabidka_montaz_polozky_testy/harness');
const nabidka = JSON.parse(fs.readFileSync(path.join(process.env.JSONDIR, 'Logiman0133.json'), 'utf8'));
(async () => {
  for (const [w, h] of [[412, 915], [390, 844], [360, 740]]) {
    const { browser, page } = await otevriNabidku({ width: w, height: h, nabidka, mobil: true });
    await page.evaluate(() => { window.print = () => {}; });
    await page.click('#btnPdfDownload'); await page.waitForTimeout(200); await page.click('#pdfMenu button[data-pdf="short"]'); await page.waitForTimeout(300);
    await page.emulateMedia({ media: 'print' }); await page.waitForTimeout(900);
    const r = await page.evaluate((W) => { const out = []; document.querySelectorAll('body *').forEach(e => { const cs = getComputedStyle(e); if (cs.display === 'none') return; const b = e.getBoundingClientRect(); if (b.width > 0 && b.right > W + 1) out.push({ el: e.tagName.toLowerCase() + (e.id ? '#' + e.id : '') + '.' + String(e.className).replace(/\s+/g, '.').slice(0, 48), w: Math.round(b.width), right: Math.round(b.right), minW: cs.minWidth, pos: cs.position }); }); return { scrollW: document.documentElement.scrollWidth, innerW: innerWidth, kandidati: out.sort((a, b) => b.right - a.right).slice(0, 8) }; }, w);
    console.log(w, JSON.stringify(r));
    await browser.close();
  }
})().catch(e => { console.error('CHYBA', e); process.exit(2); });
