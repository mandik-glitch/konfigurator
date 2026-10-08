// Kontroly panelu "Rendering -> HDRi": vyber svetel ze souboru (zatrzitka), hlaseni neplatneho
// ulozeneho vyberu, poradi/souboj ukladani, XSS ve jmenech svetel. Bez DB a site (viz harness.js).
// Spusteni: node test_panel_svetla.js   (konci kodem 0 jen kdyz VSE prosla)
const H = require('./harness');
let vysl = [];
const over = (nazev, podminka, detail) => { vysl.push([nazev, !!podminka]); console.log((podminka ? 'OK   ' : 'FAIL ') + nazev + (podminka ? '' : '  -> ' + JSON.stringify(detail))); };

(async () => {
  // H: zakladni vyber - vychozi 2 nejsilnejsi, nacteni NIC neuklada, klik pridava a uklada
  let { browser, page } = await H.otevri({ svetla_soubor: 'X1_SCENA.blend', svetla_aktivni: true, aktivni_pro_automat: true });
  await H.wait(page, 200);
  let i = await H.info(page);
  let s = await H.server(page);
  over('H1 vychozi = Light + Spot.001', JSON.stringify(i.seznam) === JSON.stringify(['[x] Light', '[ ] Spot', '[x] Spot.001', '[ ] Spot.002']), i.seznam);
  over('H2 samotne nacteni panelu nic neulozi (puts=0)', s.puts === 0, s);
  await H.klikSvetlo(page, 'Spot'); await H.wait(page, 100);
  s = await H.server(page);
  over('H3 klik pridal svetlo a ulozil', JSON.stringify(s.state.svetla_vybrana) === JSON.stringify(['Light', 'Spot', 'Spot.001']), s.state);
  await browser.close();

  // A: neplatny ulozeny vyber -> varovani; po Ulozit zmizi a server drzi vychozi
  ({ browser, page } = await H.otevri({ svetla_soubor: 'X1_PREJMENOVANO.blend', svetla_aktivni: true, svetla_vybrana: ['Light', 'Spot.001'], aktivni_pro_automat: true }));
  await H.wait(page, 200);
  i = await H.info(page);
  over('A1 varovani ve stavu automatu', /NEZAŘAZUJE/.test(i.stav), i.stav);
  over('A1 poznamka u seznamu', i.pozn.some(t => /už v souboru neplatí/.test(t)), i.pozn);
  await page.evaluate(() => document.getElementById('matPrirazeniUlozit').click());
  await H.wait(page, 200);
  i = await H.info(page);
  s = await H.server(page);
  over('A2 po Ulozit varovani zmizelo', !/NEZAŘAZUJE/.test(i.stav), i.stav);
  over('A2 po Ulozit poznamka zmizela', !i.pozn.some(t => /už v souboru neplatí/.test(t)), i.pozn);
  over('A2 server drzi platny vyber', JSON.stringify(s.state.svetla_vybrana) === JSON.stringify(['Light', 'Spot.003']), s.state);
  await browser.close();

  // B: stare API bez pole vychozi -> hlasita chyba, ne "0 ze 4"
  ({ browser, page } = await H.otevri({ svetla_soubor: 'X1_SCENA.blend', svetla_aktivni: true }, { bezVychozi: true }));
  await H.wait(page, 200);
  i = await H.info(page);
  over('B hlasita chyba o API', /API neumí výběr světel/.test(i.info), i.info);
  over('B seznam skryty', i.seznamDisplay === 'none' && i.seznam.length === 0, i);
  await browser.close();

  // C: hlaska o poslednim svetle se po case vrati na pocet
  ({ browser, page } = await H.otevri({ svetla_soubor: 'X1_SCENA.blend', svetla_aktivni: true, svetla_vybrana: ['Light'] }));
  await H.wait(page, 200);
  await H.klikSvetlo(page, 'Light'); await H.wait(page, 50);
  i = await H.info(page);
  over('C1 hlaska', /Aspoň jedno/.test(i.info), i.info);
  await H.wait(page, 3300);
  i = await H.info(page);
  over('C2 po case zpet pocet', /ZAPNUTO — 1 ze 4/.test(i.info), i.info);
  await browser.close();

  // D: souboj PUTu - prvni zpozdeny, server musi skoncit s poslednim vyberem
  ({ browser, page } = await H.otevri({ svetla_soubor: 'X1_SCENA.blend', svetla_aktivni: true, svetla_vybrana: ['Light', 'Spot.001'] },
    { putDelaySrc: 'telo.svetla_vybrana.length === 3 ? 300 : 0' }));
  await H.wait(page, 200);
  await H.klikSvetlo(page, 'Spot'); await H.wait(page, 30);
  await H.klikSvetlo(page, 'Spot.002'); await H.wait(page, 900);
  const sd = await H.server(page);
  over('D server drzi posledni vyber (4 svetla), puts=2', JSON.stringify(sd.state.svetla_vybrana) === JSON.stringify(['Light', 'Spot', 'Spot.001', 'Spot.002']) && sd.puts === 2, sd);
  await browser.close();

  // E: zmena souboru - behem cteni je stary seznam skryty
  ({ browser, page } = await H.otevri({ svetla_soubor: 'X1_SCENA.blend', svetla_aktivni: true, svetla_vybrana: ['Light', 'Spot.002'] }, { delay: { 'Y.blend': 600 } }));
  await H.wait(page, 200);
  await H.zmenSoubor(page, 'Y.blend'); await H.wait(page, 100);
  i = await H.info(page);
  over('E1 behem cteni seznam prazdny', i.seznam.length === 0 && /čtu soubor/.test(i.info), i);
  await H.wait(page, 900);
  i = await H.info(page);
  over('E2 po nacteni seznam Y', i.seznam.length === 3, i);
  await browser.close();

  // F: zapnuti fajky s neplatnym ulozenym vyberem uz projde
  ({ browser, page } = await H.otevri({ svetla_soubor: 'X1_PREJMENOVANO.blend', svetla_aktivni: false, svetla_vybrana: ['Light', 'Spot.001'], aktivni_pro_automat: true }));
  await H.wait(page, 200);
  await H.klikAktivni(page); await H.wait(page, 400);
  i = await H.info(page);
  const sf = await H.server(page);
  over('F zapnuto a ulozeno', sf.state.svetla_aktivni === true && /uloženo/.test(i.ulozStav), { i, sf });
  over('F server ma platny vyber', JSON.stringify(sf.state.svetla_vybrana) === JSON.stringify(['Light', 'Spot.003']), sf.state);
  await browser.close();

  // G: zvlastni jmena svetel (HTML, uvozovky) se nevykonaji a neroznou ulozeni
  ({ browser, page } = await H.otevri({ svetla_soubor: 'XSS.blend', svetla_aktivni: true, aktivni_pro_automat: true }));
  await H.wait(page, 200);
  over('G1 zadne XSS', (await page.evaluate(() => window.__xss || 0)) === 0);
  over('G2 zadny img element', (await page.evaluate(() => document.querySelectorAll('#matPrirazeniSvetlaSeznam img, #matPrirazeniAutomatStav img').length)) === 0);
  await H.klikSvetlo(page, 'Svetlo čřž'); await H.wait(page, 100);
  i = await H.info(page);
  const sg = await H.server(page);
  over('G3 ulozeno i se zvlastnimi jmeny', /uloženo/.test(i.ulozStav) && sg.state.svetla_vybrana.length === 3, { i, sg });
  await browser.close();

  const selhalo = vysl.filter(v => !v[1]).length;
  console.log('\nVYSLEDEK panel: ' + (vysl.length - selhalo) + '/' + vysl.length + ' OK');
  process.exit(selhalo ? 1 : 0);
})();
