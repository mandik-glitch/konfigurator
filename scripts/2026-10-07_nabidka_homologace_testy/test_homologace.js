// Online nabidka: text na konci KAZDE nabidky pro sestavy do aut (Robert 2026-10-07: "Text na konci kazde online nabidky pro sestavy do aut: Zapis do elektronickeho
// technickeho prukazu provadime na zaklade Homologace HP-0579") - bot16. SKUTECNA stranka webapp/nabidka-online.html v Chromiu proti falesnemu serveru (harness bot8).
// Spusteni: node test_homologace.js     Kandidat: NABIDKA_HTML=/cesta/nabidka-online.html node test_homologace.js   (puvodni verze MUSI selhat)
const fs = require('fs');
const path = require('path');
const { otevriNabidku, vzorovaNabidka } = require('../2026-10-06_nabidka_montaz_polozky_testy/harness');
const { nactiGalerie, galerieRoute } = require('../2026-10-07_realizace_foto_testy/harness_realizace');
const KONFIG = JSON.parse(fs.readFileSync(path.join(__dirname, '../2026-10-06_nabidka_cover_testy/fixture_nabidka_z_konfigurace.json'), 'utf8'));
const TEXT = 'Zápis do elektronického technického průkazu provádíme na základě Homologace HP-0579';
const vysl = [];
const over = (nazev, podminka, detail) => { vysl.push(!!podminka); console.log((podminka ? 'OK   ' : 'FAIL ') + nazev + (podminka ? '' : '  -> ' + JSON.stringify(detail))); };
const KLIC = page => page.evaluate(() => (document.querySelector('.slide.active') || { dataset: {} }).dataset.key);
async function naKonec(page) {
  for (let i = 0; i < 12 && (await KLIC(page)) !== 'closing'; i++) { await page.keyboard.press('ArrowRight'); await page.waitForTimeout(450); }
  await page.waitForTimeout(400);
}
const text = page => page.evaluate(() => { const e = document.querySelector('.slide.active .closing-homologace'); if (!e) return null; const r = e.getBoundingClientRect(), c = getComputedStyle(e); return { t: e.textContent.trim(), viditelne: c.display !== 'none' && r.width > 0 && r.height > 0, vOkne: r.left >= 0 && r.right <= innerWidth, posledni: !e.nextElementSibling }; });
const scena = opts => vzorovaNabidka(d => { d.offer_options = Object.assign({}, d.offer_options, opts); return d; });
const pripady = [
  ['sestava do auta (rucni priznak is_vehicle_assembly)', scena({ is_vehicle_assembly: true }), true],
  ['nabidka z Vandr karty (backend posila is_vehicle_assembly)', scena({ is_vehicle_assembly: true, vandr_single_drawing: true }), true],
  ['nabidka ze sceny bez priznaku auta', scena({ is_vehicle_assembly: false }), false],
];
(async () => {
  for (const [nazev, nabidka, ma] of pripady) {
    for (const okno of [{ width: 1920, height: 1080 }, { width: 390, height: 844 }]) {
      const { browser, page, chyby } = await otevriNabidku(Object.assign({}, okno, { nabidka }));
      await naKonec(page);
      const t = await text(page);
      if (ma) over(`${nazev}, ${okno.width} px: na posledni strane je presne zadany text, viditelny a v okne`, t && t.t === TEXT && t.viditelne && t.vOkne, t);
      else over(`${nazev}, ${okno.width} px: text o homologaci tam NENI`, t === null, t);
      if (okno.width === 1920) over(`${nazev}: bez chyb JS`, !chyby || chyby.length === 0, chyby);
      await browser.close();
    }
  }
  {
    const { browser, page } = await otevriNabidku({ width: 1920, height: 1080, nabidka: KONFIG });
    await naKonec(page);
    over('nabidka z konfigurace stolu (neni auto): text o homologaci tam NENI', (await text(page)) === null, await text(page));
    await browser.close();
  }
  // ---- D) S FOTKAMI REALIZACI na zaverecne strane (Robert 2026-10-07 "proc stale neni v online nabidce veta o homologaci": na telefonu ji blok fotek odsunul pod okraj obrazovky / pod spodni listu).
  // Veta musi byt v okne HNED (bez rolovani), nezakryta spodni listou ani plovoucimi tlacitky (Dotaz / WhatsApp) a lezet NAD fotkami; ZIVA galerie (jen cteni) + skutecne soubory fotek.
  {
    const G = await nactiGalerie();
    const vandr = vzorovaNabidka(d => { d.offer_number = 'Logiman0133'; d.offer_options = Object.assign({}, d.offer_options, { vandr_single_drawing: true, is_vehicle_assembly: true }); });
    for (const [w, h] of [[390, 844], [360, 740], [412, 915], [375, 667], [1920, 1080], [1366, 768], [1280, 720]]) {
      const { browser, page } = await otevriNabidku({ width: w, height: h, nabidka: vandr, trasy: async (route) => galerieRoute(route, new URL(route.request().url()), G, {}) });
      await naKonec(page);
      await page.waitForTimeout(1800);                                                                 // fotky se nacitaji line az na cenove strane; cekame na jejich zobrazeni (rozlozeni po nich)
      const m = await page.evaluate(() => {
        const s = document.querySelector('.slide.active'), e = s.querySelector('.closing-homologace'), blok = s.querySelector('#closingRealizace');
        if (!e) return { chybi: true };
        const r = e.getBoundingClientRect(), body = (x, y) => { const el = document.elementFromPoint(x, y); return !!(el && el.closest('.closing-homologace')); };
        const rg = document.createRange(); rg.selectNodeContents(e); const radky = [...rg.getClientRects()].filter(x => x.width > 2), bod = (rc, fx) => body(rc.left + rc.width * fx, rc.top + rc.height / 2);
        return { scrollTop: s.scrollTop, top: Math.round(r.top), bottom: Math.round(r.bottom), okno: innerHeight, fotekViditelne: !!(blok && !blok.hidden),
                 pred: blok ? (e.compareDocumentPosition(blok) & Node.DOCUMENT_POSITION_FOLLOWING) !== 0 : null,
                 nezakryta: radky.length > 0 && [radky[0], radky[radky.length - 1]].every(rc => [0.02, 0.5, 0.98].every(fx => bod(rc, fx))) };          // zacatek, stred i konec PRVNIHO a POSLEDNIHO radku TEXTU (ne boxu)
      });
      over(`D ${w}x${h} s fotkami realizaci: veta o homologaci je v okne hned (bez rolovani), nezakryta listou ani tlacitky, nad fotkami`, !m.chybi && m.fotekViditelne && m.scrollTop === 0 && m.top >= 0 && m.bottom <= m.okno && m.nezakryta && m.pred === true, m);
      await browser.close();
    }
  }
  const ok = vysl.filter(Boolean).length;
  console.log(`\nVYSLEDEK text o homologaci na konci nabidek pro auta: ${ok}/${vysl.length} OK`);
  process.exit(ok === vysl.length ? 0 : 1);
})().catch(e => { console.error('CHYBA TESTU', e); process.exit(2); });
