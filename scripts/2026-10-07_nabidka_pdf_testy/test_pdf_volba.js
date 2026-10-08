// Online nabidka: PDF jako VOLBA Strucne / Kompletni (bot16, 2026-10-07; Robert: "PDF stazitelnou verzi dejme jako volbu i plnohodnotnou se vsim komplet" a "zase tam chybi montaz KDE
// Praha/Slavicin" + "Vandr nabidka se tvori 2mi cestami - jako 1 strana nebo slozena z vice stran, takze je potreba osetrit vsechna mista"). SKUTECNA stranka webapp/nabidka-online.html
// v Chromiu proti falesnemu serveru (harness bot8; zadna sit, zadna DB). Overuje (A) nabidku voleb u tlacitka PDF (otevrit/zavrit/Escape/klik mimo, volba "short" bez tridy, "full" s body.print-full
// jen po dobu tisku, zbytek po prerusenem tisku nezmeni strucnou verzi), (B) mobil 390 px, (C) SKUTECNE PDF (page.pdf v tiskovem rezimu, pdftotext/pdfimages/pdftoppm) pro nabidku ze sceny, Vandr na
// 1 stranu, Vandr z vice stran, nenabidka do auta a Vandr se slevou a zvolenou montazi: obsah strucne vs kompletni verze, mista montaze Praha / Slavicin, vykresy z Vandru JSOU v obou verzich
// (strucna je driv ve sloupci sbalila na vysku 0), zadna prazdna strana. Kandidat: NABIDKA_HTML=/cesta/nabidka-online.html node test_pdf_volba.js   (puvodni stranka MUSI selhat)
const fs = require('fs'), os = require('os'), path = require('path');
const { execFileSync } = require('child_process');
const { otevriNabidku, vzorovaNabidka } = require('../2026-10-06_nabidka_montaz_polozky_testy/harness');
const vysl = [];
const over = (nazev, podminka, detail) => { vysl.push(!!podminka); console.log((podminka ? 'OK   ' : 'FAIL ') + nazev + (podminka ? '' : '  -> ' + JSON.stringify(detail))); };
const OBR = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAeAAAADwCAMAAADvq0eIAAADAFBMVEX///8WMk/AOSvu8fUAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAPqkzgAAAB8klEQVR42u3VsQEAIAgEMdT9d3YBehFCeZ2fwjiRn96jGwKwDlgHrAPWAeuAdUMA1gHrgHXAOmAdsA4YsA5YB6wD1gHrgHXAuiEA682Bt6t/gAHr/mAdsA5YB6wD1gHrhgCsA9YB64B1wDpg3YMB64B1wDpgHbAOWAcMWJ8MvFz9AwwY8GBgf1vpDhgwYMAGBawD1gHrgHXAgAEDBgxYB6wD1gHrgAEDBgwYsEEB64B1wDpgHTBgwIANClgHrAPWAeuAAQMGDBiwoQHrgHXAOmDAgAEDBmxQwDpgHbAOWAcMGDBgwIB1wDpgHbAOGDBgwIABGxqwDlgHrAMGDBgwYMAGBawD1gHrgHXAgAEDBgxYB6wD1gHrgAEDBgwYsKEB64B1wDpgHTBgwIANClgHrAPWAeuAAQMGDBiwoQHrgHXAOmDAgAEDBmxQwDpgHbAOWAcMGDBgwIB1wDpgHbAOGDBgwIABGxqwDlgHrAMGDBgwYMAGBawD1gHrgHXAgAEDBgxYB6wD1gHrgAEDBpwBu+oHGDDgqcD6790QgHXAOmAdsA5YB6wbArAOWAesA9YB64B1wIB1wDpgHbAOWAesA9YNAVgHrAPWAeuAdcC6BwPWAeuAdcA6YB2wDhiwDlgHrAPWAeuAdcC6IQDrgHXA+tt+ATtuSkXcEOiEAAAAAElFTkSuQmCC', 'base64');
const TMP = fs.mkdtempSync(path.join(os.tmpdir(), 'pdf_volba_'));
const trasy = async (route, { p }) => { if (/\/image\/\w+$/.test(p)) { route.fulfill({ status: 200, contentType: 'image/png', body: OBR }); return true; } return false; };
const sh = (cmd, args) => execFileSync(cmd, args, { encoding: 'utf8', maxBuffer: 80e6 });
const pocetStran = f => parseInt(/Pages:\s+(\d+)/.exec(sh('pdfinfo', [f]))[1], 10);
const text = (f, strana) => sh('pdftotext', strana ? ['-layout', '-f', String(strana), '-l', String(strana), f, '-'] : ['-layout', f, '-']);
const obrazky = (f, n) => sh('pdfimages', ['-list', '-f', String(n), '-l', String(n), f]).split('\n').filter(l => /^\s*\d+\s+\d+\s+image/.test(l)).length;
const stranaS = (f, re) => { const n = pocetStran(f); for (let i = 1; i <= n; i++) if (re.test(text(f, i))) return i; return 0; };
function inkNaStranach(f) {
  const pref = path.join(TMP, 'ink_' + path.basename(f, '.pdf'));
  sh('pdftoppm', ['-r', '20', '-gray', '-png', f, pref]);
  const out = sh('python3', ['-c', 'import glob,sys; from PIL import Image\nfor p in sorted(glob.glob(sys.argv[1]+"-*.png")):\n  im=Image.open(p).convert("L"); h=im.histogram(); t=sum(h); print(round(100.0*(t-sum(h[245:]))/t,2))', pref]);
  return out.trim().split('\n').map(Number);
}
const bezBom = d => { d.items = d.items.map(i => { const { mesh_group, cross_section_mm, drawing_bbox, ...r } = i; return r; }); return d; };       // Vandr polozky nemaji mesh_group (jako ostre 0133)
const KRESBY2 = [{ slot: 'narys', label: 'Levá strana' }, { slot: 'bokorys', label: 'Pravá strana' }];
const SC = [
  { id: 'scena', popis: 'nabidka ze sceny (kusovnik, profily v rezu, ne auto)', nab: () => vzorovaNabidka(), auto: false, kusovnik: true, kresby: 0 },
  { id: 'vandr1', popis: 'Vandr na 1 stranu (jeden vykres)', nab: () => vzorovaNabidka(d => { bezBom(d); d.offer_options = Object.assign({}, d.offer_options, { vandr_single_drawing: true, is_vehicle_assembly: true }); }), auto: true, kusovnik: false, kresby: 1 },
  { id: 'vandrN', popis: 'Vandr slozena z vice stran (2 vykresy)', nab: () => vzorovaNabidka(d => { bezBom(d); d.offer_options = Object.assign({}, d.offer_options, { vandr_single_drawing: true, is_vehicle_assembly: true, vandr_drawings: KRESBY2 }); }), auto: true, kusovnik: false, kresby: 2, popisky: ['Levá strana', 'Pravá strana'] },
  { id: 'vandrSleva', popis: 'Vandr se slevou 10 % a zvolenou montazi ve Slavicine', nab: () => vzorovaNabidka(d => { bezBom(d); d.discount_pct = 10; d.order_prefs = { qty: 1, montaz_zvolena: 1, montaz_misto: 'slavicin', payment_method: 'zaloha', deposit_pct: 70 };
    d.offer_options = Object.assign({}, d.offer_options, { vandr_single_drawing: true, is_vehicle_assembly: true, vandr_drawings: KRESBY2 }); }), auto: true, kusovnik: false, kresby: 2, sleva: true, zvolenoMisto: 'Slavičín' },
];

async function pdf(sc, rezim, sirka = 1280) {
  const { browser, page, chyby } = await otevriNabidku({ width: sirka, height: 900, nabidka: sc.nab(), trasy });
  await page.evaluate(() => { window.__tisk = []; window.print = () => { window.__tisk.push([...document.body.classList]); }; });
  await page.click('#btnPdfDownload'); await page.waitForTimeout(150);
  await page.click(`#pdfMenu button[data-pdf="${rezim}"]`); await page.waitForTimeout(250);
  const tisk = await page.evaluate(() => window.__tisk);
  await page.emulateMedia({ media: 'print' });
  await page.waitForTimeout(700);
  const f = path.join(TMP, `${sc.id}_${rezim}.pdf`);
  await page.pdf({ path: f, format: 'A4', printBackground: true, margin: { top: '10mm', bottom: '10mm', left: '8mm', right: '8mm' } });
  await browser.close();
  return { f, chyby, tisk };
}

(async () => {
  // ---- A) nabidka voleb u tlacitka PDF (desktop)
  {
    const { browser, page, chyby } = await otevriNabidku({ width: 1440, height: 900, trasy });
    await page.evaluate(() => { window.__tisk = []; window.print = () => { window.__tisk.push([...document.body.classList]); }; });
    const stavMenu = () => page.evaluate(() => { const m = document.getElementById('pdfMenu'); const r = m.getBoundingClientRect(); return { show: m.classList.contains('show'), viditelne: getComputedStyle(m).display !== 'none' && r.height > 0, vOkne: r.left >= 0 && r.right <= innerWidth && r.top >= 0 && r.bottom <= innerHeight, polozky: [...m.querySelectorAll('button')].map(b => b.textContent.replace(/\s+/g, ' ').trim()) }; });
    over('A1 tlacitko PDF je v liste a nabidka voleb je na zacatku zavrena', await page.evaluate(() => { const b = document.getElementById('btnPdfDownload'); return b && getComputedStyle(b).display !== 'none'; }) && !(await stavMenu()).viditelne, await stavMenu());
    await page.click('#btnPdfDownload'); await page.waitForTimeout(150);
    let m = await stavMenu();
    over('A2 klik na PDF otevre nabidku se dvema volbami "Strucne PDF" a "Kompletni PDF", cela v okne', m.viditelne && m.vOkne && m.polozky.length === 2 && /^Stručné PDF/.test(m.polozky[0]) && /^Kompletní PDF/.test(m.polozky[1]), m);
    await page.mouse.click(300, 300); await page.waitForTimeout(100);
    over('A3 klik mimo nabidku ji zavre', !(await stavMenu()).viditelne);
    await page.click('#btnPdfDownload'); await page.keyboard.press('Escape'); await page.waitForTimeout(100);
    over('A4 Escape nabidku zavre', !(await stavMenu()).viditelne);
    await page.click('#btnPdfDownload'); await page.click('#btnPdfDownload'); await page.waitForTimeout(100);
    over('A5 druhy klik na PDF nabidku zavre (prepinac)', !(await stavMenu()).viditelne);
    await page.click('#btnPdfDownload'); await page.click('#pdfMenu button[data-pdf="short"]'); await page.waitForTimeout(150);
    let t = await page.evaluate(() => window.__tisk);
    over('A6 "Strucne PDF": tisk se spusti prave jednou BEZ tridy print-full a nabidka se zavre', t.length === 1 && !t[0].includes('print-full') && !(await stavMenu()).viditelne, t);
    await page.click('#btnPdfDownload'); await page.click('#pdfMenu button[data-pdf="full"]'); await page.waitForTimeout(150);
    t = await page.evaluate(() => window.__tisk);
    over('A7 "Kompletni PDF": tisk se spusti s tridou print-full', t.length === 2 && t[1].includes('print-full'), t);
    over('A8 po tisku (udalost afterprint) se trida print-full sundá', await page.evaluate(() => { window.dispatchEvent(new Event('afterprint')); return !document.body.classList.contains('print-full'); }));
    await page.click('#btnPdfDownload'); await page.click('#pdfMenu button[data-pdf="full"]'); await page.waitForTimeout(100);
    await page.click('#btnPdfDownload'); await page.click('#pdfMenu button[data-pdf="short"]'); await page.waitForTimeout(150);
    t = await page.evaluate(() => window.__tisk);
    over('A9 kompletni tisk bez afterprint (preruseny) a hned "Strucne": strucna verze tridu print-full NEMA', t.length === 4 && !t[3].includes('print-full'), t);
    over('A10 bez JS chyb', chyby.length === 0, chyby);
    await browser.close();
  }
  // ---- B) mobil 390 px
  {
    const { browser, page, chyby } = await otevriNabidku({ width: 390, height: 800, mobil: true, trasy });
    await page.evaluate(() => { window.__tisk = []; window.print = () => { window.__tisk.push([...document.body.classList]); }; });
    await page.tap('#btnPdfDownload'); await page.waitForTimeout(200);
    const m = await page.evaluate(() => { const e = document.getElementById('pdfMenu'); const r = e.getBoundingClientRect(); return { viditelne: r.height > 0, vOkne: r.left >= 0 && r.right <= innerWidth && r.top >= 0 && r.bottom <= innerHeight, sirka: Math.round(r.width), tlacitka: [...e.querySelectorAll('button')].map(b => Math.round(b.getBoundingClientRect().height)) }; });
    over('B1 mobil 390 px: nabidka voleb je cela v okne a obe volby jsou videt', m.viditelne && m.vOkne && m.tlacitka.length === 2 && m.tlacitka.every(h => h >= 36), m);
    await page.tap('#pdfMenu button[data-pdf="full"]'); await page.waitForTimeout(150);
    over('B2 mobil: klepnuti na "Kompletni PDF" spusti tisk s print-full', (await page.evaluate(() => window.__tisk)).some(c => c.includes('print-full')));
    over('B3 mobil: bez JS chyb', chyby.length === 0, chyby);
    await browser.close();
  }
  // ---- C) skutecna PDF
  for (const sc of SC) {
    console.log('== ' + sc.id + ': ' + sc.popis);
    const s = await pdf(sc, 'short'), f = await pdf(sc, 'full');
    const ns = pocetStran(s.f), nf = pocetStran(f.f), ts = text(s.f), tf = text(f.f);
    over(`C ${sc.id}: oba tisky byly spusteny spravnou tridou a bez JS chyb`, s.tisk.length === 1 && !s.tisk[0].includes('print-full') && f.tisk.length === 1 && f.tisk[0].includes('print-full') && !s.chyby.length && !f.chyby.length, { s: s.tisk, f: f.tisk, chyby: s.chyby.concat(f.chyby) });
    over(`C ${sc.id}: v obou PDF je cena (CELKOVA CENA), cenova tabulka a zaver (strucne ${ns} str., kompletni ${nf} str.)`, [ts, tf].every(x => /CELKOVÁ CENA/.test(x) && /Cenová nabídka/.test(x) && /Děkujeme za poptávku/.test(x)) && nf >= ns && ns <= 5 && nf <= 9, { ns, nf });
    over(`C ${sc.id}: hint "klikneme / najetim mysi" se v papirovych verzich netiskne`, ![ts, tf].some(x => /klikněte pro zvýraznění|Najetím myší/.test(x)), null);
    over(`C ${sc.id}: zadna prazdna strana (kazda ma aspon 0,3 % tisku) ve strucnem ani kompletnim PDF`, inkNaStranach(s.f).every(v => v > 0.3) && inkNaStranach(f.f).every(v => v > 0.3), { s: inkNaStranach(s.f), f: inkNaStranach(f.f) });
    over(`C ${sc.id}: volby objednavky ("Vase volby k objednavce") jsou JEN v kompletnim PDF`, /Vaše volby k objednávce/.test(tf) && !/Vaše volby k objednávce/.test(ts), { s: /Vaše volby/.test(ts), f: /Vaše volby/.test(tf) });
    if (sc.kusovnik) {
      over(`C ${sc.id}: kompletni PDF ma Kusovnik a Profily v rezu, strucne ne`, /KUSOVNÍK|Kusovník/.test(tf) && /Profily v řezu/i.test(tf) && !/Profily v řezu/i.test(ts), { kus: /Kusovník/i.test(tf), rez: /Profily v řezu/i.test(tf), rezStr: /Profily v řezu/i.test(ts) });
      over(`C ${sc.id}: kompletni PDF je delsi nez strucne (${ns} < ${nf})`, nf > ns, { ns, nf });
    } else {
      over(`C ${sc.id}: prazdny kusovnik (Vandr polozky nemaji mesh_group) se v kompletnim PDF netiskne`, !/KUSOVNÍK|Kusovník/i.test(tf), null);
    }
    if (sc.kresby) {
      const pf = stranaS(f.f, /Technick[ýé] výkres/), ps = stranaS(s.f, /Technick[ýé] výkres/);
      over(`C ${sc.id}: vykresy z Vandru JSOU ve strucnem i kompletnim PDF (${sc.kresby}x obrazek na strane s nadpisem Technicke vykresy)`, ps > 0 && pf > 0 && obrazky(s.f, ps) >= sc.kresby && obrazky(f.f, pf) >= sc.kresby, { ps, pf, obrS: ps && obrazky(s.f, ps), obrF: pf && obrazky(f.f, pf) });
      for (const pop of (sc.popisky || [])) over(`C ${sc.id}: popisek vykresu "${pop}" je v obou PDF`, ts.includes(pop) && tf.includes(pop), null);
    }
    if (sc.auto) {
      over(`C ${sc.id}: sestava do auta - strucne PDF rika, ze montaz je mozna v Praze / Slavicine`, /(Montáž je možná v místech: Praha \/ Slavičín|Zvolená montáž: .*Praha \/ Slavičín)/.test(ts.replace(/\s+/g, ' ')), ts.replace(/\s+/g, ' ').match(/Montáž[^.]{0,120}/g));
      over(`C ${sc.id}: sestava do auta - kompletni PDF ma radek "Misto montaze" s Praha i Slavicin (v obrazovce skryty do zvoleni montaze)`, /Místo montáže\s+Praha\s+Slavičín/.test(tf), tf.match(/Místo montáže[^\n]*/g));
      over(`C ${sc.id}: sestava do auta - v obou PDF je text o homologaci HP-0579`, /Homologace HP-0579/.test(ts) && /Homologace HP-0579/.test(tf), null);
    } else {
      over(`C ${sc.id}: ne auto - zadna veta o mistech montaze ani radek Misto montaze`, !/Montáž je možná v místech/.test(ts) && !/Místo montáže/.test(tf), null);
    }
    if (sc.sleva) {
      over(`C ${sc.id}: radek "Sleva 10 %" je v obou PDF`, /Sleva 10 %/.test(ts) && /Sleva 10 %/.test(tf), null);
      over(`C ${sc.id}: zvolena montaz "${sc.zvolenoMisto}" je ve strucnem PDF jmenem`, new RegExp('Zvolená montáž: ' + sc.zvolenoMisto).test(ts), ts.replace(/\s+/g, ' ').match(/Montáž[^.]{0,100}/g));
    }
  }
  fs.rmSync(TMP, { recursive: true, force: true });
  const ok = vysl.filter(Boolean).length;
  console.log(`\nVYSLEDEK PDF jako volba (strucne / kompletni): ${ok}/${vysl.length} OK`);
  process.exit(ok === vysl.length ? 0 : 1);
})().catch(e => { console.error('CHYBA TESTU', e); process.exit(2); });
