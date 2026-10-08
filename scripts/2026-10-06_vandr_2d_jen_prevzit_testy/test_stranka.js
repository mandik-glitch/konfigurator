// Vandr 2D vykresy se JEN PREBIRAJI, nikdy nevyrabi (bot5, 2026-10-06, Robert pres bot9): stranka online nabidky z Vandr karty BEZ Vandr vykresu (offer_options.vandr_bez_vykresu) nema stranku Vykresy
// a cisluje se o jedna mene; nabidka s vykresem ji ma beze zmeny; SPOLECNA nabidka s jednou stranou bez vykresu ukaze jen vykresy stran, ktere ho maji (i JEDEN). SKUTECNA stranka v Chromiu proti
// falesnemu serveru (harness bot8: scripts/2026-10-06_nabidka_montaz_polozky_testy/harness.js), nic se nezapisuje.
// Spusteni: node test_stranka.js     Kandidat: NABIDKA_HTML=/cesta/k/nabidka-online.html node test_stranka.js
const { otevriNabidku, vzorovaNabidka } = require('../2026-10-06_nabidka_montaz_polozky_testy/harness');
const vysl = [];
const over = (nazev, podminka, detail) => { vysl.push(!!podminka); console.log((podminka ? 'OK   ' : 'FAIL ') + nazev + (podminka ? '' : '  -> ' + JSON.stringify(detail))); };
const klice = page => page.evaluate(() => [...document.querySelectorAll('.slide')].map(s => s.dataset.key));
const cisla = page => page.evaluate(() => [...document.querySelectorAll('.slide .slide-title .num')].map(e => e.textContent.trim()));
const nadpisy = page => page.evaluate(() => [...document.querySelectorAll('.slide[data-key="drawings_vandr"] .slide-title h2')].map(e => e.textContent.trim()));
const vandr = (opts, upr) => vzorovaNabidka(d => { d.offer_options = Object.assign({}, d.offer_options, { vandr_single_drawing: true }, opts); if (upr) upr(d); return d; });

(async () => {
  // 1) Vandr nabidka z karty S vykresem: stranka Vykresy (drawings_vandr), cislovani beze zmeny
  let { browser, page, chyby } = await otevriNabidku({ nabidka: vandr({}) });
  let k = await klice(page);
  over('V1 Vandr nabidka s vykresem: je stranka drawings_vandr, zadne drawings_1/2', k.includes('drawings_vandr') && !k.includes('drawings_1') && !k.includes('drawings_2'), k);
  const c1 = await cisla(page);
  over('V2 cislovani s vykresem: 01 (resi), 02 (vykres)', c1.includes('01') && c1.includes('02'), c1);
  await browser.close();

  // 2) Vandr nabidka z karty BEZ Vandr vykresu: zadna stranka Vykresy, zadny nahradni vykres
  ({ browser, page, chyby } = await otevriNabidku({ nabidka: vandr({ vandr_bez_vykresu: true }) }));
  k = await klice(page);
  over('V3 Vandr nabidka bez vykresu: NENI drawings_vandr ani drawings_1/2 (Vykresy se nevyrabi)', !k.includes('drawings_vandr') && !k.includes('drawings_1') && !k.includes('drawings_2'), k);
  over('V4 zbyle stranky jsou (cover, 3D, cena, zaver) a stranka nespadne', k.includes('cover') && k.includes('pricing') && chyby.length === 0, [k, chyby.slice(0, 2)]);
  const c3 = await cisla(page);
  over('V5 cislovani bez vykresu o jedna mene: je 01, 02 (3D / cena), zadne preskoceni (neni 05)', c3.includes('01') && c3.includes('02') && !c3.includes('05'), c3);
  await browser.close();

  // 3) SPOLECNA nabidka: jedna strana ma vykres (1 polozka vandr_drawings) - stranka ukaze jen ji, s popiskem strany
  ({ browser, page, chyby } = await otevriNabidku({ nabidka: vandr({ vandr_drawings: [{ slot: 'narys', label: 'Pravá strana' }] }) }));
  k = await klice(page);
  const popisky = await page.evaluate(() => [...document.querySelectorAll('.slide[data-key="drawings_vandr"] .view-card')].map(c => c.textContent.replace(/\s+/g, ' ').trim()));
  over('V6 spolecna nabidka s jednim vykresem (druha strana ho ve Vandru nema): stranka Vykresy ma 1 kartu s popiskem "Pravá strana"', k.includes('drawings_vandr') && popisky.length === 1 && /Pravá strana/.test(popisky[0]), [k, popisky]);
  await browser.close();

  // 4) SPOLECNA nabidka se dvema vykresy beze zmeny
  ({ browser, page, chyby } = await otevriNabidku({ nabidka: vandr({ vandr_drawings: [{ slot: 'narys', label: 'Levá strana' }, { slot: 'bokorys', label: 'Pravá strana' }] }) }));
  const dva = await page.evaluate(() => [...document.querySelectorAll('.slide[data-key="drawings_vandr"] .view-card img')].map(i => i.dataset.view));
  over('V7 spolecna nabidka se dvema vykresy: 2 karty (narys, bokorys), bez chyb', dva.length === 2 && dva[0] === 'narys' && dva[1] === 'bokorys' && chyby.length === 0, [dva, chyby.slice(0, 2)]);
  await browser.close();

  // 5) NE-Vandr nabidka (scena) beze zmeny: drawings_1 + drawings_2, priznak vandr_bez_vykresu se bez vandr_single_drawing nepouzije
  ({ browser, page, chyby } = await otevriNabidku({ nabidka: vzorovaNabidka(d => { d.offer_options = Object.assign({}, d.offer_options, { vandr_bez_vykresu: true }); return d; }) }));
  k = await klice(page);
  over('V8 nabidka ze sceny: stranky Vykresy (drawings_1 + drawings_2) zustavaji i s "divokym" vandr_bez_vykresu bez vandr_single_drawing', k.includes('drawings_1') && k.includes('drawings_2') && !k.includes('drawings_vandr'), k);
  await browser.close();

  const ok = vysl.filter(Boolean).length;
  console.log(`\nVYSLEDEK Vandr 2D jen prevzit - stranka: ${ok}/${vysl.length} OK`);
  process.exit(ok === vysl.length ? 0 : 1);
})().catch(e => { console.error('TEST SPADL:', e); process.exit(2); });
