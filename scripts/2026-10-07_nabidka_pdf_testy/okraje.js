// Pouziti: OUT=<slozka> JSONDIR=<slozka s Logiman0133.json> node okraje.js  (papir A4 / Letter / A5 x okraje 0-30 mm x okno desktop / telefon: dosahne obsah uvodni strany pravy okraj papiru? Pri okraji 0 mm je to samo o sobe v poradku - plnoplosna obalka)
// Hleda, pri jakych okrajich / sirce tiskove plochy se uvodni strana PDF orezava (obsah zasahuje az k pravemu okraji papiru). Realna nabidka 0133.
const fs = require('fs'), path = require('path'), cp = require('child_process');
const { otevriNabidku } = require('/opt/konfigurator/scripts/2026-10-06_nabidka_montaz_polozky_testy/harness');
const OUT = process.env.OUT; const nabidka = JSON.parse(fs.readFileSync(path.join(process.env.JSONDIR, 'Logiman0133.json'), 'utf8'));
const PAPIR = [['A4', 'A4'], ['Letter', 'Letter'], ['A5', 'A5']];
(async () => {
  for (const [vp, w, h, mobil] of [['desktop', 1280, 900, false], ['telefon', 412, 915, true]]) {
    const { browser, page } = await otevriNabidku({ width: w, height: h, nabidka, mobil });
    await page.evaluate(() => { window.print = () => {}; });
    await page.click('#btnPdfDownload'); await page.waitForTimeout(200); await page.click('#pdfMenu button[data-pdf="short"]'); await page.waitForTimeout(300);
    await page.emulateMedia({ media: 'print' }); await page.waitForTimeout(800);
    for (const [pn, fmt] of PAPIR) for (const mm of [0, 8, 14.5, 20, 30]) {
      const f = path.join(OUT, `ok_${vp}_${pn}_${mm}.pdf`);
      await page.pdf({ path: f, format: fmt, printBackground: true, margin: { top: mm + 'mm', bottom: mm + 'mm', left: mm + 'mm', right: mm + 'mm' } });
      cp.execSync(`pdftoppm -r 40 -f 1 -l 1 -png "${f}" "${f}.p"`);
      const png = fs.readdirSync(OUT).find(x => x.startsWith(`ok_${vp}_${pn}_${mm}.pdf.p`));
      const r = cp.execSync(`python3 - <<'PY'\nfrom PIL import Image\nim = Image.open("${path.join(OUT, png)}").convert("L"); W, H = im.size\npx = im.load()\nxs = [x for x in range(W) if any(px[x, y] < 245 for y in range(0, min(H, 400)))]\nprint(W, min(xs) if xs else -1, max(xs) if xs else -1)\nPY`).toString().trim();
      const [W, x0, x1] = r.split(' ').map(Number);
      console.log(`${vp} ${pn} okraj ${mm}mm: stranka ${W}px, obsah od ${x0} do ${x1}  -> ${x1 >= W - 1 ? 'ZASAHUJE AZ K PRAVEMU OKRAJI (orez!)' : 'ok (pravy okraj ' + (W - 1 - x1) + 'px)'}`);
      fs.rmSync(path.join(OUT, png)); fs.rmSync(f);
    }
    await browser.close();
  }
})().catch(e => { console.error('CHYBA', e); process.exit(2); });
