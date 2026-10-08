// Pouziti: OUT=<slozka> JSONDIR=<slozka s Logiman0133.json> node tisk_telefon.js  (Robert 2026-10-07 "pdf ke stazeni orezava uvodni text": tisk jako na telefonu, na vysku, ruzne okraje; vysledek = prehled prvnich stran; v headless Chromiu se orez NEZREPRODUKOVAL)
// Reprodukce Robertova "PDF ke stazeni orezava uvodni text": realna nabidka 0133 (verejny JSON z ziveho API), tlacitko PDF -> Strucne/Kompletni -> tisk jako na telefonu (na vysku, ruzne sirky, ruzne okraje).
const fs = require('fs'), path = require('path'), cp = require('child_process');
const { chromium } = require('/opt/konfigurator/node_modules/playwright-core');
const { otevriNabidku } = require('/opt/konfigurator/scripts/2026-10-06_nabidka_montaz_polozky_testy/harness');
const OUT = process.env.OUT; const nabidka = JSON.parse(fs.readFileSync(path.join(process.env.JSONDIR, 'Logiman0133.json'), 'utf8'));
const varianty = [
  { id: 'desktop1280_okraje8', w: 1280, h: 900, mobil: false, margin: { top: '10mm', bottom: '10mm', left: '8mm', right: '8mm' } },
  { id: 'telefon412_okraje10', w: 412, h: 915, mobil: true, margin: { top: '10mm', bottom: '10mm', left: '10mm', right: '10mm' } },
  { id: 'telefon412_bez_okraju', w: 412, h: 915, mobil: true, margin: { top: '0', bottom: '0', left: '0', right: '0' } },
  { id: 'telefon390_okraje15', w: 390, h: 844, mobil: true, margin: { top: '15mm', bottom: '15mm', left: '15mm', right: '15mm' } },
];
(async () => {
  for (const v of varianty) {
    const { browser, page } = await otevriNabidku({ width: v.w, height: v.h, nabidka, mobil: v.mobil });
    await page.evaluate(() => { window.print = () => { window.__tisk = [...document.body.classList]; }; });
    await page.click('#btnPdfDownload').catch(async () => { await page.evaluate(() => document.querySelector('#btnPdfDownload').click()); });
    await page.waitForTimeout(200);
    await page.click('#pdfMenu button[data-pdf="short"]'); await page.waitForTimeout(300);
    await page.emulateMedia({ media: 'print' }); await page.waitForTimeout(800);
    const f = path.join(OUT, v.id + '.pdf');
    await page.pdf({ path: f, format: 'A4', printBackground: true, margin: v.margin });
    const sirky = await page.evaluate(() => ({ scrollW: document.documentElement.scrollWidth, innerW: innerWidth, naj: [...document.querySelectorAll('.cover, .cover *')].map(e => ({ t: (e.className || e.tagName).toString().slice(0, 30), r: Math.round(e.getBoundingClientRect().right) })).sort((a, b) => b.r - a.r).slice(0, 3) }));
    cp.execSync(`pdftoppm -r 60 -f 1 -l 1 -png "${f}" "${path.join(OUT, v.id)}"`);
    console.log(v.id, JSON.stringify(sirky), cp.execSync(`pdfinfo "${f}" | grep -E "Pages|Page size"`).toString().replace(/\s+/g, ' '));
    await browser.close();
  }
})().catch(e => { console.error('CHYBA', e); process.exit(2); });
