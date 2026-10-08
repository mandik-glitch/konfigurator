// Panel Prehledy > John (admin/js/prehledy-john.js; bot16 2026-10-06, Robert pres bot9: "chci Johnovu praci videt primo v adminu v nejakem panelu, tam se bude vse aktualizovat").
// SKUTECNY admin.html + admin/js proti falesnemu serveru (harness.js). Kandidat pred nasazenim:
//   ADMIN_HTML=<kandidat>/admin.html JS_DIR=<kandidat>/js node scripts/2026-10-06_john_panel_testy/test_john_panel.js
const { otevriAdmin } = require('./harness');
let bad = 0, total = 0;
const ok = (c, t, d) => { total++; if (!c) bad++; console.log(`[${c ? 'OK   ' : 'CHYBA'}] ${t}${!c && d !== undefined ? ' | ' + (typeof d === 'string' ? d : JSON.stringify(d)) : ''}`); };
const iso = min => new Date(Date.now() - min * 60000).toISOString();
const ceka = ms => new Promise(r => setTimeout(r, ms));

function prace() {
  return {
    aktualizovano: iso(2),
    ukoly: [
      { id: 'a', nazev: 'Spoj šroubem 40×40', stav: 'bezi', popis: 'Dělám animaci spoje šroubem pro profil 40×40.', zbyva: 'Dokončit render a texty', odkaz: 'https://autovestavby.logiman.cz/nahled-john/spoj-40/',
        dalsi_odkazy: ['https://autovestavby.logiman.cz/nahled-john/spoj-40-b/', { nazev: 'Podklad', url: '/nahled-john/podklad.pdf' }], zahajeno: iso(90), aktualizovano: iso(5), hotovo: null },
      { id: 'b', nazev: 'Připni cokoli 35×35', stav: 'ceka_na_schvaleni', popis: 'Hotové, čeká na schválení.', zbyva: 'Schválení Robertem', odkaz: 'https://autovestavby.logiman.cz/nahled-john/pc-35/', zahajeno: iso(300), aktualizovano: iso(30) },
      { id: 'c', nazev: 'Schéma průřezu 35×35', stav: 'rozpracovano', popis: 'Kreslím schéma.', zbyva: 'Kóty', zahajeno: iso(200), aktualizovano: iso(70) },
      { id: 'd', nazev: 'Kufříky Milwaukee', stav: 'zive', popis: 'Nasazeno.', zbyva: '', odkaz: 'https://autovestavby.logiman.cz/nahled-john/kufriky/', zahajeno: iso(2000), aktualizovano: iso(900), hotovo: iso(900) },
      { id: 'e', nazev: 'Starý úkol', stav: 'zastaveno', popis: 'Zastaveno Robertem.', aktualizovano: iso(5000) },
      { id: 'f', nazev: 'Divný stav', stav: 'neznamy_stav', popis: 'Neznámý stav.', aktualizovano: iso(10) },
    ],
    historie: [
      { cas: iso(60), text: 'Spuštěn úkol Spoj šroubem 40×40.' },
      { cas: iso(5), text: 'Hotový render 1/3.' },
      { cas: iso(20), text: 'Připni cokoli 35×35 čeká na schválení.' },
    ],
  };
}
const klik = (page, tab) => page.evaluate(t => document.querySelector('.tab-btn[data-tab="' + t + '"]').click(), tab);
const otevriPanel = async (h) => { await klik(h.page, 'john'); await h.page.waitForSelector('#tab-john.active', { timeout: 5000 }); await h.page.waitForSelector('#johnUkoly .jn-karta, #johnBanner .jn-banner', { timeout: 8000 }).catch(() => {}); };

(async () => {
  // ---------------------------------------------------------------- A) vzhled, skupiny, obsah
  let h = await otevriAdmin({ prace: prace() });
  const p = h.page;
  ok(await p.locator('.nav-group[data-group="prehledy"] .nav-subgroup[data-group="prehledy-john"] .tab-btn[data-tab="john"]').count() === 1, 'A1 v menu Přehledy je podskupina John s tlačítkem Johnova práce');
  await otevriPanel(h);
  ok((await p.evaluate(() => location.hash)) === '#john', 'A2 po kliknutí je v adrese #john (po F5 se panel obnoví)');
  const poradi = await p.$$eval('#johnUkoly details.jn-skupina', ds => ds.map(d => ({ stav: d.dataset.stav, otevrena: d.open, karet: d.querySelectorAll('.jn-karta').length })));
  ok(poradi.map(x => x.stav).join() === 'bezi,ceka_na_schvaleni,rozpracovano,zive,zastaveno,_jiny', 'A3 skupiny jsou řazené: Běží, Čeká na schválení, Rozpracováno, Živé, Zastaveno, Ostatní', poradi);
  ok(poradi[0].otevrena && poradi[1].otevrena && poradi[2].otevrena && !poradi[3].otevrena && !poradi[4].otevrena, 'A4 aktivní skupiny jsou rozbalené, Živé a Zastaveno sbalené', poradi);
  const stitky = await p.$$eval('#johnUkoly .jn-skupina-hlava .jn-stitek', s => s.map(x => x.textContent));
  ok(stitky.join('|') === 'Běží|Čeká na schválení|Rozpracováno|Živé|Zastaveno|Ostatní', 'A5 barevné štítky mají české názvy stavů', stitky);
  const karta = p.locator('#johnUkoly .jn-karta[data-id="a"]');
  ok((await karta.innerText()).includes('Dělám animaci spoje šroubem') && (await karta.innerText()).includes('Zbývá: Dokončit render a texty'), 'A6 karta ukazuje popis a „Zbývá“');
  const cas = await karta.locator('time.jn-cas').first().innerText();
  ok(/^před [4-6] min$/.test(cas), 'A7 čas poslední změny je „před 5 min“ (u karty)', cas);
  ok(/Aktualizováno \d\d:\d\d \(před [1-3] min\)/.test(await p.locator('#johnStav').innerText()), 'A8 hlavička ukazuje „Aktualizováno HH:MM (před 2 min)“', await p.locator('#johnStav').innerText());
  ok(/● živě · načteno \d\d:\d\d:\d\d/.test(await p.locator('#johnStav').innerText()), 'A9 hlavička ukazuje, že se načítá živě, a čas posledního načtení');
  const odk = await karta.locator('a.jn-odkaz').evaluateAll(as => as.map(a => ({ t: a.textContent, href: a.getAttribute('href'), target: a.target, rel: a.rel })));
  ok(odk.length === 3 && odk[0].t.startsWith('Otevřít náhled') && odk[0].target === '_blank' && /noopener/.test(odk[0].rel) && odk[2].href.indexOf('/nahled-john/podklad.pdf') >= 0 && odk[1].t.includes('Další odkaz'), 'A10 odkazy: hlavní „Otevřít náhled“, další (řetězec i objekt), nový panel + noopener', odk);
  const hist = await p.$$eval('#johnHistorie .jn-hist-radek .jn-hist-text', t => t.map(x => x.textContent));
  ok(hist[0] === 'Hotový render 1/3.' && hist[2] === 'Spuštěn úkol Spoj šroubem 40×40.', 'A11 historie je od nejnovějšího', hist);
  ok(h.chyby.length === 0, 'A12 bez chyb JS', h.chyby.slice(0, 3));
  await h.zavri();

  // ---------------------------------------------------------------- B) nedůvěryhodný obsah
  const zlo = prace();
  zlo.ukoly.push({ id: 'xss', nazev: '<img src=x onerror="window.__xss=1">Útok', stav: 'bezi', popis: '<script>window.__xss=2</script><b>tučně</b>', zbyva: '<i>x</i>', odkaz: 'javascript:window.__xss=3',
    dalsi_odkazy: ['https://evil.example.com/x', 'data:text/html,<b>x</b>', { nazev: 'Naše', url: 'https://autovestavby.logiman.cz/ok/' }, { nazev: 'Cizí subdoména', url: 'https://logiman.cz.evil.example.com/' }], aktualizovano: iso(1) });
  h = await otevriAdmin({ prace: zlo });
  await otevriPanel(h);
  await ceka(400);
  const xk = h.page.locator('#johnUkoly .jn-karta[data-id="xss"]');
  ok(await h.page.evaluate(() => window.__xss === undefined) && (await h.page.locator('#tab-john img, #tab-john script').count()) === 0 && (await xk.locator('.jn-popis *, .jn-nazev *').count()) === 0 && (await xk.locator('.jn-zbyva > *').count()) === 1, 'B1 HTML a skripty v textech se zobrazí jen jako text (žádný img/script, žádné značky v názvu a popisu, nic se nespustilo)');
  const x = await h.page.locator('#johnUkoly .jn-karta[data-id="xss"]');
  ok((await x.innerText()).includes('<img src=x onerror='), 'B2 text s <img…> je vidět doslova', (await x.innerText()).slice(0, 120));
  const xo = await x.locator('.jn-odkaz').evaluateAll(es => es.map(e => ({ tag: e.tagName, t: e.textContent.slice(0, 40), href: e.getAttribute('href') })));
  ok(xo.filter(o => o.tag === 'A').length === 1 && xo.find(o => o.tag === 'A').href === 'https://autovestavby.logiman.cz/ok/' && xo.filter(o => o.tag === 'SPAN').length === 4, 'B3 odkazy: jen naše domény jsou klikací; javascript:, data:, cizí a podvržená doména (logiman.cz.evil…) jsou jen text', xo);
  await h.zavri();

  // ---------------------------------------------------------------- C) automatická obnova bez reloadu
  h = await otevriAdmin({ prace: prace(), interval: 1500, live: { zkontrolovano: iso(0), bezi: [{ jednotka: 'john-spoj-40.service', od: iso(12) }], selhaly: [] } });
  await otevriPanel(h);
  await ceka(300);
  const n0 = h.pozadavky.prace;
  ok(/Právě běží:.*john-spoj-40\.service/.test(await h.page.locator('#johnLive').innerText()), 'C1 živá jednotka john-* se ukáže („Právě běží: john-spoj-40.service“)', await h.page.locator('#johnLive').innerText());
  const zm = prace(); zm.ukoly[1].stav = 'schvaleno'; zm.ukoly.push({ id: 'nova', nazev: 'Nový úkol od Johna', stav: 'bezi', popis: 'Právě začal.', aktualizovano: iso(0) }); zm.historie.push({ cas: iso(0), text: 'Nový úkol od Johna.' });
  h.stav.prace = zm;
  await h.page.waitForSelector('#johnUkoly .jn-karta[data-id="nova"]', { timeout: 6000 }).catch(() => {});
  ok(await h.page.locator('#johnUkoly .jn-karta[data-id="nova"]').count() === 1 && h.pozadavky.prace > n0, 'C2 po změně souboru se nový úkol objeví sám (bez reloadu), panel soubor načítá opakovaně', { n0, ted: h.pozadavky.prace });
  ok(await h.page.evaluate(() => window.__marker === 'ziva'), 'C3 stránka se nenačetla znovu (proměnná z původního načtení žije)');
  const sch = await h.page.$$eval('#johnUkoly details.jn-skupina', ds => ds.map(d => d.dataset.stav));
  ok(sch.includes('schvaleno') && !sch.includes('ceka_na_schvaleni'), 'C4 úkol změnil skupinu (Čeká na schválení → Schváleno)', sch);
  ok(await h.page.locator('#johnUkoly .jn-karta.jn-zmena').count() >= 1, 'C5 změněná karta je krátce zvýrazněná');
  ok((await h.page.locator('#johnHistorie .jn-hist-text').first().innerText()) === 'Nový úkol od Johna.', 'C6 historie ukáže nový záznam nahoře');
  // sbalená/rozbalená skupina se při obnově nepřepne zpět
  await h.page.evaluate(() => { const d = document.querySelector('#johnUkoly details[data-stav="zive"]'); d.open = true; d.dispatchEvent(new Event('toggle')); });
  await ceka(2200);
  ok(await h.page.evaluate(() => document.querySelector('#johnUkoly details[data-stav="zive"]').open === true), 'C7 ručně rozbalená skupina zůstane rozbalená i po automatické obnově');
  // opuštění záložky zastaví obnovu
  await klik(h.page, 'zalohy');
  await ceka(400); const n1 = h.pozadavky.prace; await ceka(3200);
  ok(h.pozadavky.prace === n1, 'C8 po přepnutí na jinou záložku se přestane obnovovat (žádné zbytečné dotazy)', { n1, ted: h.pozadavky.prace });
  await klik(h.page, 'john'); await ceka(600);
  ok(h.pozadavky.prace > n1, 'C9 po návratu na záložku se načte hned znovu');
  ok(h.chyby.length === 0, 'C10 bez chyb JS', h.chyby.slice(0, 3));
  await h.zavri();

  // ---------------------------------------------------------------- D) chyby a stará data
  h = await otevriAdmin({ prace: null, interval: 1500 });
  await otevriPanel(h);
  ok(/chybí \(404\)/.test(await h.page.locator('#johnBanner').innerText()), 'D1 chybějící prace.json = výrazné varování (404)', await h.page.locator('#johnBanner').innerText());
  h.stav.prace = prace();
  await h.page.waitForSelector('#johnUkoly .jn-karta', { timeout: 6000 }).catch(() => {});
  ok(await h.page.locator('#johnUkoly .jn-karta').count() >= 5 && !/chybí/.test(await h.page.locator('#johnBanner').innerText()), 'D2 jakmile soubor vznikne, panel ho sám načte a varování zmizí');
  h.stav.prace = { __status: 500 };
  await h.page.waitForSelector('#johnBanner .jn-banner-varovani', { timeout: 6000 }).catch(() => {});
  ok(/Poslední obnovení selhalo/.test(await h.page.locator('#johnBanner').innerText()) && await h.page.locator('#johnUkoly .jn-karta').count() >= 5, 'D3 při výpadku zůstanou zobrazená poslední data a je vidět varování', await h.page.locator('#johnBanner').innerText());
  ok(/nedostupné/.test(await h.page.locator('#johnStav').innerText()), 'D4 hlavička ukáže „nedostupné“');
  h.stav.prace = { __raw: '{rozbité' };
  await h.page.waitForFunction(() => /není platný JSON/.test(document.getElementById('johnBanner').textContent), null, { timeout: 6000 }).catch(() => {});
  ok(/není platný JSON/.test(await h.page.locator('#johnBanner').innerText()), 'D5 rozbitý JSON = varování, panel nespadne');
  h.stav.prace = []; h.stav.prace.__x = 1;
  await ceka(2200);
  ok(h.chyby.length === 0, 'D6 žádná výjimka ani při špatném tvaru souboru', h.chyby.slice(0, 3));
  await h.zavri();

  const stare = prace(); stare.aktualizovano = iso(5 * 60);
  h = await otevriAdmin({ prace: stare });
  await otevriPanel(h);
  ok(/neaktualizoval/.test(await h.page.locator('#johnBanner').innerText()), 'D7 přehled starší než 3 h = varování „neaktualizoval“', await h.page.locator('#johnBanner').innerText());
  await h.zavri();
  const bezStare = prace(); bezStare.aktualizovano = iso(60);
  h = await otevriAdmin({ prace: bezStare });
  await otevriPanel(h);
  ok(/Běží, ale přehled se neměnil \d+ min/.test(await h.page.locator('#johnBanner').innerText()), 'D8 úkol „Běží“ a soubor 60 min beze změny = varování, že se John mohl zaseknout', await h.page.locator('#johnBanner').innerText());
  await h.zavri();
  h = await otevriAdmin({ prace: prace() });
  await otevriPanel(h);
  ok((await h.page.locator('#johnBanner .jn-banner').count()) === 0, 'D9 čerstvý přehled = žádné varování');
  await h.zavri();

  // ---------------------------------------------------------------- E) živé jednotky vs. přehled
  h = await otevriAdmin({ prace: prace(), live: { zkontrolovano: iso(0), bezi: [], selhaly: [] } });
  await otevriPanel(h);
  ok(/žádná jednotka john-\* teď neběží/.test(await h.page.locator('#johnBanner').innerText()), 'E1 úkol „Běží“, ale žádná jednotka neběží = varování', await h.page.locator('#johnBanner').innerText());
  ok(/Právě neběží žádná jednotka/.test(await h.page.locator('#johnLive').innerText()), 'E2 řádek živého stavu říká, že nic neběží');
  await h.zavri();
  const bezUkolu = prace(); bezUkolu.ukoly = bezUkolu.ukoly.filter(u => u.stav !== 'bezi');
  h = await otevriAdmin({ prace: bezUkolu, live: { zkontrolovano: iso(0), bezi: [{ jednotka: 'john-x.service', od: iso(3) }], selhaly: [{ jednotka: 'john-y.service' }] } });
  await otevriPanel(h);
  const bt = await h.page.locator('#johnBanner').innerText();
  ok(/běží jednotka John/i.test(bt) && /Selhala jednotka: john-y\.service/.test(bt), 'E3 jednotka běží bez úkolu „Běží“ = informace; selhaná jednotka = chyba', bt);
  await h.zavri();
  h = await otevriAdmin({ prace: prace(), live: { __status: 404 } });
  await otevriPanel(h);
  ok((await h.page.locator('#johnLive').innerText()) === '' && await h.page.locator('#johnUkoly .jn-karta').count() >= 5, 'E4 bez živého endpointu (404 před nasazením API) panel funguje jen ze souboru, bez chyby');
  await h.zavri();

  // ---------------------------------------------------------------- F) oprávnění
  h = await otevriAdmin({ prace: prace(), user: { role: 'manager', permissions: {} } });
  ok(await h.page.locator('.tab-btn[data-tab="john"]').evaluate(b => b.style.display === 'none'), 'F1 role bez práva `prehledy_john` záložku nevidí (fail-closed)');
  await h.zavri();
  h = await otevriAdmin({ prace: prace(), user: { role: 'manager', permissions: { prehledy_john: true } } });
  ok(await h.page.locator('.tab-btn[data-tab="john"]').evaluate(b => b.style.display !== 'none'), 'F2 role s právem `prehledy_john` záložku vidí');
  await h.zavri();
  h = await otevriAdmin({ prace: prace(), user: { role: 'manager', permissions: { nastaveni: true } } });
  ok(await h.page.locator('.tab-btn[data-tab="john"]').evaluate(b => b.style.display === 'none'), 'F3 sekce `nastaveni` (Boti, Zálohy…) záložku John NEodemyká');
  await h.zavri();

  // ---------------------------------------------------------------- G) telefon
  h = await otevriAdmin({ prace: prace(), viewport: { width: 390, height: 800 } });
  await otevriPanel(h);
  await h.page.evaluate(() => document.querySelectorAll('#johnUkoly details').forEach(d => { d.open = true; }));
  await ceka(200);
  // POZOR: samotna stranka admin.html ma na telefonu uz dnes sirku 704 px (areaSwitch / odhlasit v hlavicce) u VSECH zalozek - mer se jen panel John
  const ov = await h.page.evaluate(() => { const pan = document.getElementById('tab-john'), pr = pan.getBoundingClientRect(); let max = 0; pan.querySelectorAll('*').forEach(e => { const r = e.getBoundingClientRect(); if (r.width > 0) max = Math.max(max, r.right); }); return { panelRight: Math.round(pr.right), maxPotomek: Math.round(max), sw: pan.scrollWidth, cw: pan.clientWidth, okno: window.innerWidth }; });
  ok(ov.maxPotomek <= ov.panelRight + 1 && ov.sw <= ov.cw + 1 && ov.panelRight <= ov.okno, 'G1 telefon 390 px: panel John se vejde (nic nepřetéká přes jeho pravý okraj, panel je v okně)', ov);
  const vel = await h.page.locator('#johnUkoly .jn-odkaz-hlavni').first().evaluate(a => { const r = a.getBoundingClientRect(); return { w: Math.round(r.width), h: Math.round(r.height) }; });
  ok(vel.h >= 38 && vel.w >= 150, 'G2 odkaz na náhled je dost velký na prst', vel);
  await h.zavri();

  console.log(`\n==> ${total - bad}/${total} kontrol OK`);
  process.exit(bad ? 1 : 0);
})().catch(e => { console.error('SPADLO', e); process.exit(1); });
