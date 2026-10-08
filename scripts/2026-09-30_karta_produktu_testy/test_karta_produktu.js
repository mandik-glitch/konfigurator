// Test skladove karty produktu (admin): jednotka ceny desky, prepocet ceny, nazev, deska bez 3D modelu, duplikace.
// SKUTECNY admin.html + skripty v Chromiu proti falesnemu serveru (viz harness.js).
// Spusteni: node test_karta_produktu.js   (konci kodem 0 jen kdyz VSE prosla)
// Kandidat pred nasazenim: ADMIN_HTML=... SKLAD_PRODUKTY_JS=... PRODUCTS_PY=... node test_karta_produktu.js
// Vypis chyb stranky: PRINT_ERRORS=1
const { otevriAdmin, otevriKartu } = require('./harness');

const vysl = [];
const over = (nazev, podminka, detail) => {
  vysl.push(!!podminka);
  console.log((podminka ? 'OK   ' : 'FAIL ') + nazev + (podminka ? '' : '  -> ' + JSON.stringify(detail)));
};
const txt = (page, sel) => page.evaluate(s => { const e = document.querySelector(s); return e ? e.textContent.trim().replace(/\s+/g, ' ') : null; }, sel);

(async () => {
  // ---------------------------------------------------------------------------------------------------------
  // A: karta musi ukazovat SKUTECNOU jednotku z DB (endpoint movements `unit` nevraci); cena desky se zadava jen za 1 m²
  // ---------------------------------------------------------------------------------------------------------
  const norm = s => (s || '').replace(/[  ]/g, ' ');
  const pocetRadii = page => page.evaluate(() => document.querySelectorAll('input[name="scfBoardUnit"]').length);
  const zobrazeno = (page, id) => page.evaluate(id => { const e = document.getElementById(id); return !!e && getComputedStyle(e).display !== 'none'; }, id);
  {
    const { browser, page, cols } = await otevriAdmin();
    over('A0 mock movements odpovida skutecnemu SELECTu (sloupce z products.py)', cols.includes('is_board_material') && cols.includes('board_sheet_width_mm'), cols.length);
    await otevriKartu(page, 3671);                                    // DB unit m2
    over('A1 deska 3671 (DB unit m2): popisek ceny je "za 1 m²"', /1 m²/.test(await txt(page, '#scfPriceLabel') || ''), await txt(page, '#scfPriceLabel'));
    over('A2 prepinac jednotky (radio) je pryc: ukaze se "cena se zadava vzdy za 1 m²", nabidka prevodu je skryta',
         (await pocetRadii(page)) === 0 && (await zobrazeno(page, 'scfBoardM2Info')) && !(await zobrazeno(page, 'scfBoardLegacy')), { radii: await pocetRadii(page) });
    await browser.close();
  }
  {
    const { browser, page } = await otevriAdmin();
    await otevriKartu(page, 3539);                                    // starsi deska: unit ks (cena za celou tabuli)
    over('A3 starsi deska PR10 (DB unit ks): popisek "za celou tabuli" (pravdivy) + nabidka prevodu na 1 m²',
         /celou tabuli/.test(await txt(page, '#scfPriceLabel') || '') && (await zobrazeno(page, 'scfBoardLegacy')) && !(await zobrazeno(page, 'scfBoardM2Info'))
         && /Převést na cenu za 1 m²/.test(await txt(page, '#scfBoardToM2Btn') || ''), await txt(page, '#scfPriceLabel'));
    await browser.close();
  }
  {
    const { browser, page } = await otevriAdmin();
    await otevriKartu(page, 5001);
    const cb = await page.evaluate(() => { const c = document.getElementById('scfSoldByMeter'); return c ? c.checked : null; });
    over('A6 zbozi na metry (DB unit m): zatrzitko "prodava se na metry" je zatrzene a popisek "Cena / m"', cb === true && /Cena \/ m \(Kč\)/.test(await txt(page, '#scfPriceLabel') || ''), { cb, label: await txt(page, '#scfPriceLabel') });
    await browser.close();
  }

  // ---------------------------------------------------------------------------------------------------------
  // B: prepocet ceny desky pod polem ceny (co uvidi web a kosik)
  // ---------------------------------------------------------------------------------------------------------
  {
    const { browser, page } = await otevriAdmin();
    await otevriKartu(page, 3671);                                    // m2, 5000, 2070x2800 (5,796 m2)
    const c1 = norm(await txt(page, '#scfPriceConv'));
    over('B1 deska v m²: radek "Web a kosik" ukaze cenu za m² i za celou tabuli (28 980 Kč)',
         /5 000,00 Kč \/ m²/.test(c1) && /28 980,00 Kč/.test(c1) && /2070×2800 mm/.test(c1) && /5,796 m²/.test(c1), c1);
    await page.fill('#scfPrice', '6000');                             // psani ceny prepocita radek hned, bez ulozeni
    const c2 = norm(await txt(page, '#scfPriceConv'));
    over('B2 prepocet se meni uz pri psani ceny (6000 za m² -> 34 776 Kč za tabuli)', /34 776,00 Kč/.test(c2), c2);
    await browser.close();
  }
  {
    const { browser, page } = await otevriAdmin();
    await otevriKartu(page, 3539);                                    // ks, 3093,75, 1250x2500 (3,125 m2)
    const c = norm(await txt(page, '#scfPriceConv'));
    over('B3 starsi deska za tabuli: radek ukaze cenu tabule a dopocet za m² (990,00 Kč / m²)', /3 093,75 Kč/.test(c) && /990,00 Kč \/ m²/.test(c) && /3,125 m²/.test(c), c);
    await browser.close();
  }
  {
    const { browser, page } = await otevriAdmin({ produkty: require('./harness').vychoziProdukty().map(p => p.id === 3539 ? { ...p, board_sheet_width_mm: null, board_sheet_height_mm: null } : p) });
    await otevriKartu(page, 3539);
    over('B7 deska bez rozmeru tabule: radek upozorni, ze cenu nejde prepocitat', /Chybí rozměr tabule/.test(await txt(page, '#scfPriceConv') || ''), await txt(page, '#scfPriceConv'));
    await browser.close();
  }

  // ---------------------------------------------------------------------------------------------------------
  // G: SJEDNOCENI na cenu za 1 m² - prevod starsi desky (cena za tabuli) JEDNIM zapisem
  // ---------------------------------------------------------------------------------------------------------
  {
    const { browser, page, puts, dialogy } = await otevriAdmin();
    await otevriKartu(page, 3539);                                    // 3 093,75 Kč za tabuli 1250x2500 (3,125 m²)
    await page.click('#scfBoardToM2Btn');
    await page.waitForTimeout(300);
    const d = dialogy.find(x => x.typ === 'confirm');
    over('G1 prevod se pta a rika dopad: dosavadni cena tabule, nova cena za 1 m² (990,00 Kč)', d && /3 093,75 Kč/.test(norm(d.text)) && /990,00 Kč/.test(norm(d.text)), dialogy);
    over('G2 po potvrzeni jde JEDEN zapis s jednotkou m2 A prepoctenou cenou (zadny mezistav s chybnou cenou)',
         puts.length === 1 && puts[0].id === 3539 && JSON.stringify(puts[0].body) === JSON.stringify({ unit: 'm2', price_czk_placeholder: 990 }), puts);
    const po = { label: await txt(page, '#scfPriceLabel'), cena: await page.inputValue('#scfPrice'), conv: norm(await txt(page, '#scfPriceConv')),
      info: await zobrazeno(page, 'scfBoardM2Info'), legacy: await zobrazeno(page, 'scfBoardLegacy') };
    over('G3 po prevodu: popisek "za 1 m²", cena 990, radek "Web a kosik" (990,00 Kč / m² = 3 093,75 Kč), nabidka prevodu zmizela',
         /1 m²/.test(po.label) && po.cena === '990' && /990,00 Kč \/ m²/.test(po.conv) && /3 093,75 Kč/.test(po.conv) && po.info && !po.legacy, po);
    await browser.close();
  }
  {
    const { browser, page, puts } = await otevriAdmin({ dialogOdpoved: 'zrusit' });
    await otevriKartu(page, 3539);
    await page.click('#scfBoardToM2Btn'); await page.waitForTimeout(300);
    over('G4 admin prevod zrusi: nic se neulozi, deska zustava s cenou za tabuli', puts.length === 0 && (await zobrazeno(page, 'scfBoardLegacy')) && (await page.inputValue('#scfPrice')) === '3093.75', puts);
    await browser.close();
  }
  {
    const { browser, page, puts, dialogy } = await otevriAdmin({ produkty: require('./harness').vychoziProdukty().map(p => p.id === 3539 ? { ...p, board_sheet_width_mm: null, board_sheet_height_mm: null } : p) });
    await otevriKartu(page, 3539);
    await page.click('#scfBoardToM2Btn'); await page.waitForTimeout(300);
    over('G5 bez formatu tabule se prevod odmitne hlaskou a nic se neulozi', puts.length === 0 && dialogy.some(x => x.typ === 'alert' && /formát tabule/.test(x.text)), { puts, dialogy });
    await browser.close();
  }
  {
    const prod = require('./harness').vychoziProdukty().map(p => p.id === 3671 ? { ...p, unit: 'ks' } : p);   // stav "pred kliknutim": 5 000 Kč za tabuli
    const { browser, page, puts, dialogy } = await otevriAdmin({ produkty: prod });
    await otevriKartu(page, 3671);
    await page.click('#scfBoardToM2Btn'); await page.waitForTimeout(300);
    const d = dialogy.find(x => x.typ === 'confirm');
    over('G6 laminodeska 3671 (5 000 Kč za tabuli 2070×2800): nova cena 862,66 Kč / m², dialog ukazuje zaokrouhlenou cenu tabule 4 999,98 Kč',
         puts.length === 1 && puts[0].body.price_czk_placeholder === 862.66 && puts[0].body.unit === 'm2' && d && /862,66 Kč/.test(norm(d.text)) && /4 999,98 Kč/.test(norm(d.text)), { puts, dialogy });
    await browser.close();
  }
  {
    const { browser, page, dialogy } = await otevriAdmin({ putOdpoved: (pr, body) => body.unit ? { status: 403, body: { error: 'Nemáš oprávnění upravovat produkty.' } } : null });
    await otevriKartu(page, 3539);
    await page.click('#scfBoardToM2Btn'); await page.waitForTimeout(400);
    over('G7 server prevod odmitne: hlaska a karta zustava ve stavu z DB (cena za tabuli, nabidka prevodu)',
         dialogy.some(x => /Nemáš oprávnění/.test(x.text)) && (await page.inputValue('#scfPrice')) === '3093.75' && (await zobrazeno(page, 'scfBoardLegacy')), dialogy);
    await browser.close();
  }

  // ---------------------------------------------------------------------------------------------------------
  // C: priznak "deskovy material" + format tabule musi jit nastavit i u produktu BEZ 3D modelu (laminodeska 4933);
  //    zapnuti desky = jednotka m2 (cena za 1 m²)
  // ---------------------------------------------------------------------------------------------------------
  {
    const { browser, page, puts, dialogy } = await otevriAdmin();
    await otevriKartu(page, 4933);                                    // neni deska, bez GLB, bez rozmeru tabule, cena 4000 za kus
    const vis = await page.evaluate(() => {
      const d = id => { const e = document.getElementById(id); return e ? getComputedStyle(e).display : null; };
      return { cb: !!document.getElementById('scfBoardMaterial'), cbChecked: document.getElementById('scfBoardMaterial') && document.getElementById('scfBoardMaterial').checked,
        unit: d('scfBoardUnitWrap'), sheet: d('scfBoardSheetWrap'), cut: d('scfCuttingKeyWrap'), meter: d('scfSoldByMeterWrap'), barva: !!document.getElementById('scfSceneColor') };
    });
    over('C1 produkt bez GLB: zatrzitko "Deskovy material" existuje a neni zatrzene; blok desky je skryty; barva sceny chybi',
         vis.cb && vis.cbChecked === false && vis.unit === 'none' && vis.sheet === 'none' && vis.cut === 'none' && vis.meter !== 'none' && vis.barva === false, vis);
    await page.click('#scfBoardMaterial');
    await page.waitForTimeout(300);
    const d = dialogy.find(x => x.typ === 'confirm');
    over('C2a zapnuti desky u produktu s cenou se pta: cislo se od ted cte ZA 1 m² (formát tabule zatim chybi)', d && /ZA 1 m²/.test(norm(d.text)) && /formát tabule zatím chybí/.test(norm(d.text)), dialogy);
    const po = await page.evaluate(() => {
      const d = id => getComputedStyle(document.getElementById(id)).display;
      return { info: d('scfBoardM2Info'), legacy: d('scfBoardLegacy'), sheet: d('scfBoardSheetWrap'), cut: d('scfCuttingKeyWrap'), meter: d('scfSoldByMeterWrap'), label: document.getElementById('scfPriceLabel').textContent };
    });
    over('C2b zapnuti: PUT {is_board_material:true, unit:"m2"}, objevi se cena za 1 m² + format tabule, zmizi "na metry", popisek "za 1 m²"',
         puts.some(p => p.id === 4933 && p.body.is_board_material === true && p.body.unit === 'm2') && po.info !== 'none' && po.legacy === 'none' && po.sheet !== 'none' && po.cut !== 'none' && po.meter === 'none' && /1 m²/.test(po.label), { puts, po });
    over('C2c bez formatu tabule radek upozorni, ze cenu tabule nejde spocitat', /Chybí rozměr tabule/.test(await txt(page, '#scfPriceConv') || ''), await txt(page, '#scfPriceConv'));
    await page.fill('#scfBoardSheetWidth', '2070'); await page.dispatchEvent('#scfBoardSheetWidth', 'change');
    await page.fill('#scfBoardSheetHeight', '2800'); await page.dispatchEvent('#scfBoardSheetHeight', 'change');
    await page.waitForTimeout(300);
    const conv = norm(await txt(page, '#scfPriceConv'));
    over('C3 format tabule 2070×2800 se ulozi (2 PUT) a radek ukaze 4 000 Kč / m² = 23 184 Kč za tabuli (cislo se nyni cte za 1 m²)',
         puts.some(p => p.body.board_sheet_width_mm === 2070) && puts.some(p => p.body.board_sheet_height_mm === 2800) && /4 000,00 Kč \/ m²/.test(conv) && /23 184,00 Kč/.test(conv), { puts, conv });
    await browser.close();
  }
  {
    const { browser, page, puts } = await otevriAdmin({ dialogOdpoved: 'zrusit' });
    await otevriKartu(page, 4933);
    await page.click('#scfBoardMaterial'); await page.waitForTimeout(300);
    over('C2d admin zapnuti desky zrusi: nic se neulozi a zatrzitko se vrati', puts.length === 0 && (await page.evaluate(() => document.getElementById('scfBoardMaterial').checked)) === false, puts);
    await browser.close();
  }
  {
    const { browser, page, puts } = await otevriAdmin();
    await otevriKartu(page, 5001);                                    // zbozi na metry (unit m)
    await page.click('#scfBoardMaterial');
    await page.waitForTimeout(300);
    over('C4 zbozi na metry se zapnutim desky prepne na "m2" (deska ma cenu vzdy za 1 m²)', puts.some(p => p.id === 5001 && p.body.is_board_material === true && p.body.unit === 'm2'), puts);
    await browser.close();
  }
  {
    const { browser, page } = await otevriAdmin();
    await otevriKartu(page, 3671);                                    // ma GLB
    over('C5 produkt s GLB: barva sceny zustava', await page.evaluate(() => !!document.getElementById('scfSceneColor')));
    await browser.close();
  }
  {
    const { browser, page, puts, dialogy } = await otevriAdmin();
    await otevriKartu(page, 3671);                                    // deska s cenou za 1 m²
    await page.click('#scfBoardMaterial');                            // vypnout
    await page.waitForTimeout(300);
    const d = dialogy.find(x => x.typ === 'confirm');
    over('C6 vypnuti desky: potvrzeni ("ZA KUS"), PUT {is_board_material:false, unit:"ks"}, blok desky zmizi, popisek "Cena / ks"',
         d && /ZA KUS/.test(norm(d.text)) && puts.some(p => p.id === 3671 && p.body.is_board_material === false && p.body.unit === 'ks')
         && !(await zobrazeno(page, 'scfBoardUnitWrap')) && /Cena \/ ks/.test(await txt(page, '#scfPriceLabel') || ''), { dialogy, puts });
    await browser.close();
  }

  // ---------------------------------------------------------------------------------------------------------
  // D: editovatelny nazev produktu
  // ---------------------------------------------------------------------------------------------------------
  {
    const { browser, page, puts, log, dialogy } = await otevriAdmin();
    await otevriKartu(page, 4933);
    over('D1 v karte je pole Nazev s aktualnim nazvem a pod nim adresa na webu (slug)',
         (await page.inputValue('#scfName')) === 'Laminovaná dřevotříska 18mm' && /laminovana-drevotriska-18mm/.test(await page.evaluate(() => document.getElementById('stockCardHeaderGrid').textContent)), await page.inputValue('#scfName'));
    const seznamPred = log.filter(r => r.startsWith('GET /api/shop/products?')).length;
    await page.fill('#scfName', '  Laminovaná dřevotříska šedá 18 mm  '); await page.dispatchEvent('#scfName', 'change');
    await page.waitForTimeout(400);
    const titulek = await txt(page, '#stockCardTitle');
    const radekSeznamu = await page.evaluate(() => [...document.querySelectorAll('#shopProdTbody tr')].map(tr => tr.textContent).find(t => /Laminodeska\.SEDA\.18/.test(t)) || '');
    over('D2 zmena nazvu: PUT {name} (orezany), titulek karty i radek v seznamu se prepisou, seznam se nacetl znovu',
         puts.some(p => p.id === 4933 && p.body.name === 'Laminovaná dřevotříska šedá 18 mm') && /šedá 18 mm/.test(titulek)
         && /šedá 18 mm/.test(radekSeznamu) && log.filter(r => r.startsWith('GET /api/shop/products?')).length > seznamPred, { puts, titulek, radekSeznamu });
    over('D3 zmena nazvu NEPOSILA slug (adresa produktu se nemeni)', puts.every(p => !('slug' in p.body)), puts);
    await browser.close();
  }
  {
    const { browser, page, puts, dialogy } = await otevriAdmin();
    await otevriKartu(page, 4933);
    await page.fill('#scfName', '   '); await page.dispatchEvent('#scfName', 'change');
    await page.waitForTimeout(300);
    over('D4 prazdny nazev: zadny PUT, hlaska a pole se vrati na puvodni nazev', puts.length === 0 && dialogy.some(d => /nesmí být prázdný/.test(d.text)) && (await page.inputValue('#scfName')) === 'Laminovaná dřevotříska 18mm', { puts, dialogy });
    await browser.close();
  }
  {
    const { browser, page, dialogy } = await otevriAdmin({ putOdpoved: (pr, body) => body.name ? { status: 403, body: { error: 'Nemáš oprávnění upravovat produkty.' } } : null });
    await otevriKartu(page, 4933);
    await page.fill('#scfName', 'Jiný název'); await page.dispatchEvent('#scfName', 'change');
    await page.waitForTimeout(300);
    const titulek = await txt(page, '#stockCardTitle');
    over('D5 server nazev odmitne: hlaska, pole i titulek zustanou na puvodnim nazvu', dialogy.some(d => /Nemáš oprávnění/.test(d.text)) && (await page.inputValue('#scfName')) === 'Laminovaná dřevotříska 18mm' && !/Jiný název/.test(titulek), { dialogy, titulek });
    await browser.close();
  }
  {
    const { browser, page, puts } = await otevriAdmin();
    await otevriKartu(page, 4933);
    await page.fill('#scfName', 'Nový název přes Uložit změny');           // bez change (uzivatel nestihl opustit pole)
    await page.click('#stockCardSave');
    await page.waitForTimeout(400);
    over('D6 tlacitko "Ulozit zmeny" posle i nazev a prepise titulek karty', puts.some(p => p.body.name === 'Nový název přes Uložit změny') && /Nový název přes Uložit změny/.test(await txt(page, '#stockCardTitle') || ''), { puts, titulek: await txt(page, '#stockCardTitle') });
    await browser.close();
  }

  // ---------------------------------------------------------------------------------------------------------
  // E: seznam produktu - cena desky s jednotkou
  // ---------------------------------------------------------------------------------------------------------
  {
    const { browser, page } = await otevriAdmin();
    const radky = await page.evaluate(() => Object.fromEntries([...document.querySelectorAll('#shopProdTbody tr')].map(tr => [tr.children[1].textContent.trim(), tr.children[5].textContent.trim()])));
    over('E1 seznam: cena desky nese jednotku (m² / tabuli), ostatni zbozi zustava holym cislem',
         /5 000 Kč \/ m²/.test(norm(radky['Laminodeska.SEDA.25'])) && /3 093,75 Kč \/ tabuli/.test(norm(radky['PR10'])) && norm(radky['Laminodeska.SEDA.18']) === '4000', radky);
    await browser.close();
  }

  // ---------------------------------------------------------------------------------------------------------
  // F: duplikace produktu (tlacitko v radkovem menu seznamu i v hlavicce karty) + primy odkaz na kartu
  // ---------------------------------------------------------------------------------------------------------
  const kliknutiVMenuSeznamu = async (page, sku, polozka) => {
    await page.evaluate(sku => {
      const tr = [...document.querySelectorAll('#shopProdTbody tr')].find(t => t.children[1] && t.children[1].textContent.trim() === sku);
      tr.querySelector('.row-more-btn').click();
    }, sku);
    await page.evaluate(({ sku, polozka }) => {
      const tr = [...document.querySelectorAll('#shopProdTbody tr')].find(t => t.children[1] && t.children[1].textContent.trim() === sku);
      [...tr.querySelectorAll('.row-more-menu button')].find(b => b.textContent.trim() === polozka).click();
    }, { sku, polozka });
    await page.waitForTimeout(700);
  };
  {
    const { browser, page, posts, dialogy, log } = await otevriAdmin();
    const menuPolozky = await page.evaluate(() => [...document.querySelectorAll('#shopProdTbody tr')][0].querySelectorAll('.row-more-menu button').length
      && [...document.querySelectorAll('#shopProdTbody tr')][0].textContent);
    await kliknutiVMenuSeznamu(page, 'Laminodeska.SEDA.18', 'Duplikovat');
    const d = dialogy.find(x => x.typ === 'confirm');
    over('F1 radkove menu: "Duplikovat" se pta (nazev produktu, NEAKTIVNI, co se nekopiruje) a pak posle POST pro spravny produkt',
         d && /Laminovaná dřevotříska 18mm/.test(d.text) && /NEAKTIVNÍ/.test(d.text) && /Nekopíruje se skladový stav/.test(d.text)
         && posts.length === 1 && posts[0].path === '/api/shop/products/4933/duplicate', { dialogy, posts });
    const radky = await page.evaluate(() => [...document.querySelectorAll('#shopProdTbody tr')].map(t => t.textContent));
    over('F2 po duplikaci se seznam nacte znovu a kopie je v nem', radky.some(t => /4933|Laminodeska\.SEDA\.18-kopie/.test(t) && /\(kopie\)/.test(t)), radky.map(t => t.slice(0, 60)));
    const titulek = await txt(page, '#stockCardTitle');
    const info = await txt(page, '#stockCardCurrent');
    over('F3 rovnou se otevre karta KOPIE (titulek s "(kopie)") a nahore je upozorneni: NEAKTIVNI, co zkontrolovat, co se zkopirovalo',
         /\(kopie\)/.test(titulek || '') && /NEAKTIVNÍ/.test(info || '') && /Zkontroluj název, SKU a kategorii/.test(info || '') && /3 fotek galerie/.test(info || ''), { titulek, info });
    over('F4 otevrena karta kopie je neaktivni (zatrzitko "aktivni" nezatrzene)', (await page.evaluate(() => document.getElementById('scfActive').checked)) === false);
    await browser.close();
  }
  {
    const { browser, page, posts } = await otevriAdmin();
    await otevriKartu(page, 3539);
    over('F5 v hlavicce karty je tlacitko "Duplikovat" vedle "Zobrazit v e-shopu"', /Duplikovat/.test(await txt(page, '#stockCardDuplicateBtn') || '') && !!(await page.$('#stockCardViewShopLink')));
    await page.click('#stockCardDuplicateBtn');
    await page.waitForTimeout(700);
    over('F6 tlacitko v karte: POST pro tuhle kartu a otevre se karta kopie', posts.length === 1 && posts[0].id === 3539 && /\(kopie\)/.test(await txt(page, '#stockCardTitle') || ''), { posts, titulek: await txt(page, '#stockCardTitle') });
    await browser.close();
  }
  {
    const { browser, page, posts } = await otevriAdmin({ dialogOdpoved: 'zrusit' });
    await kliknutiVMenuSeznamu(page, 'PR10', 'Duplikovat');
    over('F7 admin potvrzeni zrusi: zadny POST, nic se nevytvori', posts.length === 0 && !(await page.evaluate(() => document.getElementById('stockCardModal').classList.contains('open'))), posts);
    await browser.close();
  }
  {
    const { browser, page, dialogy } = await otevriAdmin({ duplikatOdpoved: () => ({ status: 403, body: { error: 'Nemáš oprávnění vytvářet produkty.' } }) });
    await kliknutiVMenuSeznamu(page, 'PR10', 'Duplikovat');
    over('F8 server duplikaci odmitne: admin dostane hlasku a karta se neotevre', dialogy.some(x => x.typ === 'alert' && /Nemáš oprávnění vytvářet/.test(x.text))
         && !(await page.evaluate(() => document.getElementById('stockCardModal').classList.contains('open'))), dialogy);
    await browser.close();
  }
  {
    const { browser, page, dialogy } = await otevriAdmin({ duplikatOdpoved: () => ({ status: 404, raw: '<html>Not Found</html>' }) });
    await kliknutiVMenuSeznamu(page, 'PR10', 'Duplikovat');
    over('F9 endpoint jeste neni nasazeny (prosta 404 pred restartem): srozumitelna hlaska, ne ticho', dialogy.some(x => x.typ === 'alert' && /zatím není na serveru nasazená/.test(x.text)), dialogy);
    await browser.close();
  }
  {
    const { browser, page } = await otevriAdmin({ duplikatOdpoved: (id, st) => {
      const z = st.produkty.find(x => x.id === id);
      const n = { ...z, id: st.dalsiId++, sku: z.sku + '-kopie', name: z.name + ' (kopie)', active: 0 };
      st.produkty.push(n);
      return { status: 201, body: { status: 'ok', id: n.id, sku: n.sku, name: n.name, slug: 'x', copied: { categories: 0, images: 1, usage_images: 2, documents: 0, gallery: 1 }, missing_files: 2 } };
    } });
    await kliknutiVMenuSeznamu(page, 'PR10', 'Duplikovat');
    over('F10 kdyz se nektere soubory nepodarilo zkopirovat, upozorneni to rekne', /2 souborů se nepodařilo zkopírovat/.test(await txt(page, '#stockCardCurrent') || ''), await txt(page, '#stockCardCurrent'));
    await browser.close();
  }
  {
    const { browser, page } = await otevriAdmin({ query: '?karta=3671' });
    await page.waitForSelector('#stockCardModal.open', { timeout: 10000 });
    await page.waitForSelector('#scfPrice', { timeout: 5000 });
    over('F11 primy odkaz admin.html?karta=3671 sam otevre skladovou kartu tohoto produktu', /Laminovaná deska šedá 25mm/.test(await txt(page, '#stockCardTitle') || ''), await txt(page, '#stockCardTitle'));
    await browser.close();
  }

  // ---------------------------------------------------------------------------------------------------------
  // H: QA nalez "deska nema cenu za 1 m²" ma v dashboardu akci, ktera otevre kartu dane desky
  // ---------------------------------------------------------------------------------------------------------
  {
    const { browser, page } = await otevriAdmin();
    const akce = await page.evaluate(() => typeof QA_AUDIT_ACTIONS !== 'undefined' && !!QA_AUDIT_ACTIONS.board_price_not_per_m2);
    await page.evaluate(() => QA_AUDIT_ACTIONS.board_price_not_per_m2.open('3539'));
    await page.waitForSelector('#stockCardModal.open', { timeout: 8000 });
    await page.waitForSelector('#scfPrice', { timeout: 5000 });
    over('H1 QA nalez "deska bez ceny za 1 m²" ma v dashboardu akci Opravit, ktera otevre kartu te desky', akce && /Překližka 10 mm/.test(await txt(page, '#stockCardTitle') || ''), { akce, titulek: await txt(page, '#stockCardTitle') });
    await browser.close();
  }

  // ---------------------------------------------------------------------------------------------------------
  // I: adresy (slugy) produktu se tvori STROJOVE - karta ukazuje adresu, po prejmenovani/aktivaci prijde nova ze serveru,
  //    tlacitko "Sjednotit adresy (SEO)" (nahled -> potvrzeni -> provedeni) a prepsani adresy u jednoho produktu
  // ---------------------------------------------------------------------------------------------------------
  const zmenaAdresy = (id, name, old, nova, reason) => ({ id, name, old, new: nova, reason });
  const klikJs = (page, sel) => page.evaluate(sel => document.querySelector(sel).click(), sel);   // i skryty panel (zalozka Produkty)
  {
    const { browser, page } = await otevriAdmin();
    await otevriKartu(page, 4933);
    await page.fill('#scfName', 'Laminovaná dřevotříska šedá 18 mm'); await page.dispatchEvent('#scfName', 'change');
    await page.waitForTimeout(400);
    const hint = await txt(page, '#scfSlugHint');
    over('I1 po prejmenovani server vrati novou adresu a karta ji ukaze (vc. vysvetleni, ze stara se presmeruje)',
         /laminovana-drevotriska-seda-18-mm/.test(hint || '') && /přesměruje \(301\)/.test(hint || ''), hint);
    await browser.close();
  }
  {
    const { browser, page, dialogy, posts } = await otevriAdmin();
    await otevriKartu(page, 4933);
    await page.click('#scfSlugRegen'); await page.waitForTimeout(400);
    over('I2 "Prepsat adresu z nazvu" bez rozdilu: nahled na serveru (jen pro tento produkt) a hlaska, ze neni co menit, nic se neprovede',
         posts.length === 1 && posts[0].body.dry_run === true && JSON.stringify(posts[0].body.ids) === '[4933]' && dialogy.some(d => d.typ === 'alert' && /Není co měnit/.test(d.text)), { posts, dialogy });
    await browser.close();
  }
  {
    const zm = [zmenaAdresy(3671, 'Laminovaná deska šedá 25mm', 'stara-deska-seda', 'laminovana-deska-seda-25mm', 'nesedi')];
    const { browser, page, dialogy, posts } = await otevriAdmin({ slugZmeny: zm });
    await otevriKartu(page, 3671);
    await page.click('#scfSlugRegen'); await page.waitForTimeout(500);
    const d = dialogy.find(x => x.typ === 'confirm');
    over('I3 prepsani adresy u jednoho produktu: potvrzeni ukaze starou a novou adresu a 301, pak jde nahled i provedeni', d && /stara-deska-seda\s+→\s+laminovana-deska-seda-25mm/.test(d.text) && /301/.test(d.text)
         && posts.length === 2 && posts[0].body.dry_run === true && posts[1].body.dry_run === false && JSON.stringify(posts[1].body.ids) === '[3671]', { dialogy, posts });
    over('I3b po provedeni karta ukaze novou adresu', /laminovana-deska-seda-25mm/.test(await txt(page, '#scfSlugHint') || ''), await txt(page, '#scfSlugHint'));
    await browser.close();
  }
  {
    const zm = [zmenaAdresy(4053, 'Regálová vestavba – Peugeot Expert L2', 'regalova-vestavba-peugeot-expert-l2-vandrawee', 'regalova-vestavba-peugeot-expert-l2', 'interni'),
      zmenaAdresy(4134, 'Regálová vestavba – Mercedes Sprinter L2H1', 'regalova-vestavba-mercedes-sprinter-l2h1-vandrawee', 'regalova-vestavba-mercedes-sprinter-l2h1', 'interni'),
      zmenaAdresy(3250, 'Vyrovnávací šroubovací patka M6', 'plastova-patka-m6', 'vyrovnavaci-sroubovaci-patka-m6', 'nesedi')];
    const { browser, page, dialogy, posts } = await otevriAdmin({ slugZmeny: zm });
    over('I4 v Produktech je tlacitko "Sjednotit adresy (SEO)"', /Sjednotit adresy/.test(await txt(page, '#btnNormalizeSlugs') || ''));
    await klikJs(page, '#btnNormalizeSlugs'); await page.waitForTimeout(600);
    const d = dialogy.find(x => x.typ === 'confirm');
    over('I5 hromadne sjednoceni: potvrzeni ukaze pocet, duvody, priklady a 301; nejdriv NAHLED, po potvrzeni provedeni',
         d && /Produktů se změnou adresy: 3/.test(d.text) && /2× obsahuje interní název/.test(d.text) && /1× neodpovídá názvu/.test(d.text) && /301/.test(d.text)
         && /vandrawee\s+→\s+regalova-vestavba-peugeot-expert-l2/.test(d.text) && posts.length === 2 && posts[0].body.dry_run === true && posts[1].body.dry_run === false && !('ids' in posts[1].body), { dialogy, posts });
    over('I6 po provedeni hlaska "Hotovo" s poctem a seznam produktu se nacte znovu', dialogy.some(x => x.typ === 'alert' && /Hotovo: adresa sjednocena u 3 produktů/.test(x.text)), dialogy);
    await browser.close();
  }
  {
    const { browser, page, dialogy, posts } = await otevriAdmin();
    await klikJs(page, '#btnNormalizeSlugs'); await page.waitForTimeout(500);
    over('I7 neni co sjednocovat: srozumitelna hlaska a nic se neprovede (jen nahled)', posts.length === 1 && posts[0].body.dry_run === true && dialogy.some(x => x.typ === 'alert' && /Není co sjednocovat/.test(x.text)), { posts, dialogy });
    await browser.close();
  }
  {
    const zm = [zmenaAdresy(3250, 'Patka M6', 'plastova-patka-m6', 'patka-m6', 'nesedi')];
    const { browser, page, posts } = await otevriAdmin({ slugZmeny: zm, dialogOdpoved: 'zrusit' });
    await klikJs(page, '#btnNormalizeSlugs'); await page.waitForTimeout(500);
    over('I8 admin potvrzeni zrusi: zustane u nahledu, NIC se neprovede', posts.length === 1 && posts[0].body.dry_run === true, posts);
    await browser.close();
  }
  {
    const { browser, page, dialogy } = await otevriAdmin({ normalizeOdpoved: () => ({ status: 404, raw: '<html>Not Found</html>' }) });
    await klikJs(page, '#btnNormalizeSlugs'); await page.waitForTimeout(500);
    over('I9 endpoint jeste neni nasazeny (prosta 404 pred restartem): srozumitelna hlaska, ne ticho', dialogy.some(x => x.typ === 'alert' && /zatím není na serveru nasazené/.test(x.text)), dialogy);
    await browser.close();
  }
  {
    const prod = require('./harness').vychoziProdukty().map(p => p.id === 4933 ? { ...p, active: 0, slug: null } : p);   // neaktivni koncept bez adresy
    const { browser, page, puts } = await otevriAdmin({ produkty: prod });
    await otevriKartu(page, 4933);
    over('I10 produkt bez adresy: karta rika, ze vznikne sama, a nabizi ji vytvorit', /vznikne sama/.test(await txt(page, '#scfSlugHint') || '') && /Vytvořit adresu z názvu/.test(await txt(page, '#scfSlugHint') || ''), await txt(page, '#scfSlugHint'));
    await page.click('#scfActive'); await page.waitForTimeout(400);
    over('I11 aktivace produktu bez adresy: server adresu vytvori a karta ji ukaze', puts.some(p => p.id === 4933 && p.body.active === true) && /laminovana-drevotriska-18mm/.test(await txt(page, '#scfSlugHint') || ''), { puts, hint: await txt(page, '#scfSlugHint') });
    await browser.close();
  }

  {
    const { browser, page } = await otevriAdmin();
    const akce = await page.evaluate(() => typeof QA_AUDIT_ACTIONS !== 'undefined' && !!QA_AUDIT_ACTIONS.product_slug_not_from_name);
    await page.evaluate(() => QA_AUDIT_ACTIONS.product_slug_not_from_name.open('3539'));
    await page.waitForSelector('#stockCardModal.open', { timeout: 8000 });
    await page.waitForSelector('#scfPrice', { timeout: 5000 });
    over('H2 QA nalez "adresa neodpovida nazvu" ma v dashboardu akci Opravit, ktera otevre kartu produktu (tam je "Prepsat adresu z nazvu")',
         akce && /Překližka 10 mm/.test(await txt(page, '#stockCardTitle') || '') && !!(await page.$('#scfSlugRegen')), { akce, titulek: await txt(page, '#stockCardTitle') });
    await browser.close();
  }

  const selhalo = vysl.filter(v => !v).length;
  console.log('\nVYSLEDEK karta produktu: ' + (vysl.length - selhalo) + '/' + vysl.length + ' OK');
  process.exit(selhalo ? 1 : 0);
})().catch(e => { console.log('FAIL vyjimka testu: ' + (e && e.stack || e)); process.exit(1); });
