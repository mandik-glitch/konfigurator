// Zalozka Prodej > E-maily ucetni (admin/js/ucetni-emaily.js; bot16 2026-10-06, Robert: "chceme schvalene doklady automaticky posilat na emaily ucetni, budou to ruzne emaily podle typu
// dokladu, postav nato tabulku v adminu"). SKUTECNY admin.html + admin/js proti falesnemu serveru (harness.js), nic se neposila ani neuklada do zive DB.
// Kandidat pred nasazenim:  ADMIN_HTML=<kandidat>/admin.html JS_DIR=<kandidat>/js node scripts/2026-10-06_ucetni_emaily_testy/test_ucetni_emaily_panel.js
const { otevriAdmin, TYPY } = require('./harness');
let bad = 0, total = 0;
const ok = (c, t, d) => { total++; if (!c) bad++; console.log(`[${c ? 'OK   ' : 'CHYBA'}] ${t}${!c && d !== undefined ? ' | ' + (typeof d === 'string' ? d : JSON.stringify(d)) : ''}`); };
const ceka = ms => new Promise(r => setTimeout(r, ms));
const klik = (page, tab) => page.evaluate(t => document.querySelector('.tab-btn[data-tab="' + t + '"]').click(), tab);
const otevriPanel = async h => {
  await klik(h.page, 'accountantemails');
  await h.page.waitForSelector('#tab-accountantemails.active', { timeout: 5000 });
  await h.page.waitForFunction(() => document.querySelectorAll('#ueTelo tr').length > 0 || /Tabulka bude|nemáš|Načtení se nepovedlo|Nejsi/.test((document.getElementById('ueStav') || {}).textContent || ''), null, { timeout: 5000 });
};
const R = (page, kod) => page.locator('#ueTelo tr[data-typ="' + kod + '"]');
const iso = min => new Date(Date.now() - min * 60000).toISOString();
const typyPredvyplnene = () => { const t = TYPY(); Object.assign(t[0], { adresy: ['faktury@ucetni.cz', 'kopie@ucetni.cz'], aktivni: true, poznamka: 'Vydané faktury', upraveno: iso(120), upravil: 'Robert' }); return t; };
const puty = h => h.stav.puts.map(p => p.kod);
const text = (loc) => loc.evaluate(e => e.textContent.replace(/\s+/g, ' ').trim());
const dirty = async (h, kod) => R(h.page, kod).evaluate(tr => tr.classList.contains('dirty'));
const ulozPovoleno = async (h, kod) => !(await R(h.page, kod).locator('.ue-uloz').isDisabled());
const KODY = ['invoice', 'proforma_invoice', 'payment_tax_document', 'credit_note', 'delivery_note', 'prijaty_doklad'];

(async () => {
  // ---------------------------------------------------------------- A) navigace a vzhled
  let h = await otevriAdmin({ typy: typyPredvyplnene() });
  let p = h.page;
  ok(await p.locator('.nav-group[data-group="prodej"] .tab-btn[data-tab="accountantemails"]').count() === 1, 'A1 v menu Prodej je tlačítko „E-maily účetní“');
  ok(await p.locator('.tab-btn[data-tab="accountantemails"]').evaluate(b => b.firstChild.textContent.trim() === 'E-maily účetní'), 'A2 popisek tlačítka je „E-maily účetní“');
  ok(await p.evaluate(() => { const a = document.querySelector('.tab-btn[data-tab="emails"]'), b = document.querySelector('.tab-btn[data-tab="accountantemails"]'); return a.nextElementSibling === b; }), 'A3 tlačítko je hned za „Emaily odchozí“');
  await otevriPanel(h);
  ok((await p.evaluate(() => location.hash)) === '#accountantemails', 'A4 po kliknutí je v adrese #accountantemails (po F5 se záložka obnoví)');
  ok(h.pozadavky.get === 1, 'A5 při otevření se načte tabulka právě jednou', h.pozadavky.get);
  ok((await p.$$eval('#ueTelo tr', t => t.map(x => x.dataset.typ))).join() === KODY.join(), 'A6 řádky: faktura, záloha, daň. doklad k platbě, dobropis, dodací list, přijaté doklady (stabilní klíče)');
  ok((await text(R(p, 'invoice').locator('.ue-typ'))).startsWith('Faktura - Daňový doklad') && /Vydaný doklad/.test(await text(R(p, 'invoice').locator('.ue-typ'))) && /Přijatý doklad/.test(await text(R(p, 'prijaty_doklad').locator('.ue-typ'))), 'A7 řádky mají název typu a štítek Vydaný / Přijatý doklad');
  ok(await p.locator('#ueBanner').isVisible() && /Odesílání zatím není zapojené/.test(await text(p.locator('#ueBanner'))), 'A8 upozornění „Odesílání zatím není zapojené – tabulka jen ukládá adresy“ je vidět (backend odesilani_zapojeno=false)');
  const inv = R(p, 'invoice');
  ok((await inv.locator('.ue-adresy-pole').inputValue()) === 'faktury@ucetni.cz, kopie@ucetni.cz' && await inv.locator('input[type=checkbox]').isChecked() && (await inv.locator('.ue-pozn-pole').inputValue()) === 'Vydané faktury', 'A9 uložené hodnoty jsou předvyplněné (adresy oddělené čárkou, aktivní, poznámka)');
  ok(/Naposledy upraveno: .+\(Robert\)/.test(await text(inv.locator('.ue-meta'))) && (await text(R(p, 'credit_note').locator('.ue-meta'))) === 'Zatím nenastaveno.', 'A10 pod adresami je kdy a kdo naposledy upravil, nenastavené řádky ukazují „Zatím nenastaveno.“');
  ok(!(await dirty(h, 'invoice')) && !(await ulozPovoleno(h, 'invoice')), 'A11 bez změny: řádek není zvýrazněný a tlačítko Uložit je zakázané');
  const fs = await p.evaluate(() => ({ inp: getComputedStyle(document.querySelector('#ueTelo .ue-adresy-pole')).fontSize, typ: getComputedStyle(document.querySelector('#ueTelo .ue-typ')).fontSize, ban: getComputedStyle(document.getElementById('ueBanner')).fontSize }));
  ok(fs.inp === '16px' && fs.typ === '16px' && fs.ban === '16px', 'A12 písmo obsahu a polí 16 px (WORKFLOW pravidlo 6)', fs);
  ok(!(await p.locator('#tab-accountantemails').evaluate(e => /E-mail|Odeslat|Zkušební|test/i.test([...e.querySelectorAll('button')].map(b => b.textContent).join(' ')) && /odeslat|zkušební/i.test([...e.querySelectorAll('button')].map(b => b.textContent).join(' ')))), 'A13 v záložce NENÍ tlačítko pro odeslání ani zkušební odeslání (pravidlo 16)');
  await h.zavri();

  // ---------------------------------------------------------------- B) editace a ukládání
  h = await otevriAdmin({ typy: typyPredvyplnene() });
  p = h.page;
  await otevriPanel(h);
  let r = R(p, 'credit_note');
  await r.locator('.ue-adresy-pole').fill('Dobropisy@Ucetni.CZ');
  ok(await dirty(h, 'credit_note') && (await text(r.locator('.ue-radek-stav'))) === 'Neuloženo' && await ulozPovoleno(h, 'credit_note'), 'B1 po úpravě je řádek zvýrazněný („Neuloženo“) a Uložit je povolené');
  await r.locator('.ue-uloz').click();
  await p.waitForFunction(() => /Uloženo ✓/.test(document.querySelector('#ueTelo tr[data-typ="credit_note"] .ue-radek-stav').textContent));
  const b = h.stav.puts[0];
  ok(h.stav.puts.length === 1 && b.kod === 'credit_note' && /application\/json/.test(b.ctype) && JSON.stringify(b.body) === JSON.stringify({ adresy: ['dobropisy@ucetni.cz'], aktivni: false, poznamka: '' }), 'B2 uloží se jedním PUT na správný typ, adresy malými písmeny, aktivni=false (výchozí vypnuto), JSON', h.stav.puts);
  ok(!(await dirty(h, 'credit_note')) && (await r.locator('.ue-adresy-pole').inputValue()) === 'dobropisy@ucetni.cz' && /Naposledy upraveno: .+\(Test Admin\)/.test(await text(r.locator('.ue-meta'))) && /Uloženo: Dobropis/.test(await text(p.locator('#ueStav'))), 'B3 po uložení řádek není zvýrazněný, ukazuje hodnotu ze serveru, kdo/kdy upravil a stavový řádek „Uloženo: Dobropis“');
  r = R(p, 'payment_tax_document');
  await r.locator('.ue-adresy-pole').fill('  A@B.cz ; a@b.cz, C@D.cz ');
  await r.locator('.ue-uloz').click();
  await p.waitForFunction(() => /Uloženo ✓/.test(document.querySelector('#ueTelo tr[data-typ="payment_tax_document"] .ue-radek-stav').textContent));
  ok(JSON.stringify(h.stav.puts[1].body.adresy) === JSON.stringify(['a@b.cz', 'c@d.cz']) && (await r.locator('.ue-adresy-pole').inputValue()) === 'a@b.cz, c@d.cz', 'B4 normalizace: mezery, čárka/středník, velká písmena a duplicity se vyčistí před odesláním i v poli', h.stav.puts[1]);
  r = R(p, 'delivery_note');
  await r.locator('.ue-adresy-pole').fill('abc');
  ok(/Neplatná adresa: abc\./.test(await text(r.locator('.ue-radek-chyba'))) && !(await ulozPovoleno(h, 'delivery_note')) && await r.locator('.ue-radek-chyba').isVisible(), 'B5 neplatná adresa: chyba přímo pod polem a Uložit zakázané');
  const nPut = h.stav.puts.length;
  await r.locator('.ue-uloz').click({ force: true }).catch(() => {});
  ok(h.stav.puts.length === nPut, 'B6 klik na zakázané Uložit nic neodešle');
  await r.locator('.ue-adresy-pole').fill('ok@ucetni.cz');
  ok(!(await r.locator('.ue-radek-chyba').isVisible()) && await ulozPovoleno(h, 'delivery_note'), 'B7 po opravě chyba zmizí a Uložit je povolené');
  await r.locator('.ue-adresy-pole').fill('');
  r = R(p, 'proforma_invoice');
  await r.locator('input[type=checkbox]').check();
  ok(/Aktivní řádek musí mít aspoň jednu adresu\./.test(await text(r.locator('.ue-radek-chyba'))) && !(await ulozPovoleno(h, 'proforma_invoice')), 'B8 „aktivní“ bez adresy: chyba a Uložit zakázané');
  await r.locator('.ue-adresy-pole').fill('zalohy@ucetni.cz');
  await r.locator('.ue-uloz').click();
  await p.waitForFunction(() => /Uloženo ✓/.test(document.querySelector('#ueTelo tr[data-typ="proforma_invoice"] .ue-radek-stav').textContent));
  ok(h.stav.puts[h.stav.puts.length - 1].kod === 'proforma_invoice' && h.stav.puts[h.stav.puts.length - 1].body.aktivni === true && await r.locator('input[type=checkbox]').isChecked(), 'B9 aktivní řádek s adresou se uloží s aktivni=true');
  r = R(p, 'prijaty_doklad');
  await r.locator('.ue-adresy-pole').fill('a1@x.cz, a2@x.cz, a3@x.cz, a4@x.cz, a5@x.cz, a6@x.cz');
  ok(/Nejvýš 5 adres/.test(await text(r.locator('.ue-radek-chyba'))) && !(await ulozPovoleno(h, 'prijaty_doklad')), 'B10 šest adres: chyba „Nejvýš 5 adres“');
  await r.locator('.ue-adresy-pole').fill('a1@x.cz, a2@x.cz, a3@x.cz, a4@x.cz, a5@x.cz');
  ok(await ulozPovoleno(h, 'prijaty_doklad'), 'B11 pět adres je v pořádku');
  await r.locator('.ue-adresy-pole').fill('');
  r = R(p, 'invoice');
  const n1 = h.stav.puts.length;
  await r.locator('.ue-pozn-pole').fill('Nová poznámka');
  await r.locator('.ue-pozn-pole').press('Enter');
  await p.waitForFunction(() => /Uloženo ✓/.test(document.querySelector('#ueTelo tr[data-typ="invoice"] .ue-radek-stav').textContent));
  ok(h.stav.puts.length === n1 + 1 && h.stav.puts[n1].body.poznamka === 'Nová poznámka' && h.stav.puts[n1].body.aktivni === true && h.stav.puts[n1].body.adresy.length === 2, 'B12 Enter v poli uloží řádek; poznámka i ostatní hodnoty (aktivní, 2 adresy) jsou v těle', h.stav.puts[n1]);
  await r.locator('input[type=checkbox]').uncheck();
  ok(await dirty(h, 'invoice') && await ulozPovoleno(h, 'invoice'), 'B13 vypnutí „aktivní“ je změna (Uložit povolené)');
  await r.locator('.ue-uloz').click();
  await p.waitForFunction(() => /Uloženo ✓/.test(document.querySelector('#ueTelo tr[data-typ="invoice"] .ue-radek-stav').textContent));
  ok(h.stav.puts[h.stav.puts.length - 1].body.aktivni === false && h.stav.puts[h.stav.puts.length - 1].body.adresy.length === 2, 'B14 vypnutý řádek zachová adresy (jen neposílá), aktivni=false');
  ok(h.chyby.length === 0, 'B15 žádné chyby JS', h.chyby.slice(0, 3));
  await h.zavri();

  // ---------------------------------------------------------------- C) pomalé ukládání: dvojklik = jeden požadavek
  h = await otevriAdmin({ putDelay: 900 });
  p = h.page;
  await otevriPanel(h);
  r = R(p, 'credit_note');
  await r.locator('.ue-adresy-pole').fill('dobropisy@ucetni.cz');
  await r.locator('.ue-uloz').click();
  await r.locator('.ue-uloz').click({ force: true }).catch(() => {});
  await r.locator('.ue-adresy-pole').press('Enter', { timeout: 500 }).catch(() => {});
  await ceka(250);
  const busy = await r.evaluate(tr => ({ stav: tr.querySelector('.ue-radek-stav').textContent, inp: tr.querySelector('.ue-adresy-pole').disabled, chk: tr.querySelector('input[type=checkbox]').disabled, pz: tr.querySelector('.ue-pozn-pole').disabled, uloz: tr.querySelector('.ue-uloz').disabled }));
  ok(busy.stav === 'Ukládám…' && busy.inp && busy.chk && busy.pz && busy.uloz, 'C1 během ukládání se pole zamknou, tlačítko je zakázané a ukáže „Ukládám…“', busy);
  await p.waitForFunction(() => /Uloženo ✓/.test(document.querySelector('#ueTelo tr[data-typ="credit_note"] .ue-radek-stav').textContent), null, { timeout: 5000 });
  ok(h.stav.puts.length === 1, 'C2 dvojklik a Enter poslaly jen JEDEN požadavek', h.stav.puts.length);
  ok(!(await r.locator('.ue-adresy-pole').isDisabled()), 'C3 po uložení jsou pole zase odemčená');
  await h.zavri();

  // ---------------------------------------------------------------- D) chyby serveru při ukládání (401 řeší globálně admin.html = přesměrování na přihlášení, tady se netestuje)
  const CHYBY = [
    ['400 neplatná adresa (zpráva serveru)', () => ({ status: 400, body: { error: 'adresy_neplatne', message: 'Neplatná adresa: x.' } }), /Neplatná adresa: x\./],
    ['403 bez práva', () => ({ status: 403, body: { error: 'forbidden', code: 'forbidden' } }), /nemáš oprávnění/],
    ['404 neznámý typ', () => ({ status: 404, body: { error: 'typ_neznamy', message: 'x' } }), /Neznámý typ dokladu/],
    ['404 API není nasazené', () => ({ status: 404, body: { error: 'x' } }), /ještě není nasazené/],
    ['500 HTML', () => ({ status: 500, raw: '<html>boom</html>' }), /Server selhal/],
    ['výpadek spojení', () => ({ abort: true }), /Spojení selhalo/],
    ['200 bez radek v odpovědi', () => ({ status: 200, body: { ok: true } }), /Server selhal/],
  ];
  h = await otevriAdmin({});
  p = h.page;
  await otevriPanel(h);
  r = R(p, 'credit_note');
  for (const [nazev, odp, re] of CHYBY) {
    h.stav.putHandler = odp;
    await r.locator('.ue-adresy-pole').fill('dobropisy@ucetni.cz');
    const n = h.stav.puts.length;
    await r.locator('.ue-uloz').click();
    await p.waitForFunction(() => { const c = document.querySelector('#ueTelo tr[data-typ="credit_note"] .ue-radek-chyba'); return c && !c.hidden && c.textContent; }, null, { timeout: 5000 });
    const q = await r.evaluate(tr => ({ chyba: tr.querySelector('.ue-radek-chyba').textContent, dirty: tr.classList.contains('dirty'), uloz: tr.querySelector('.ue-uloz').disabled, inp: tr.querySelector('.ue-adresy-pole').disabled, value: tr.querySelector('.ue-adresy-pole').value }));
    ok(h.stav.puts.length === n + 1 && re.test(q.chyba) && q.dirty && !q.uloz && !q.inp && q.value === 'dobropisy@ucetni.cz', `D ${nazev}: hláška v řádku, změna zůstává (zvýrazněná), pole odemčená a Uložit jde zkusit znovu`, q);
  }
  h.stav.putHandler = null;
  await r.locator('.ue-uloz').click();
  await p.waitForFunction(() => /Uloženo ✓/.test(document.querySelector('#ueTelo tr[data-typ="credit_note"] .ue-radek-stav').textContent));
  ok(!(await r.locator('.ue-radek-chyba').isVisible()), 'D9 po úspěšném opakování chyba zmizí');
  ok(h.chyby.length === 0, 'D10 žádné chyby JS', h.chyby.slice(0, 3));
  await h.zavri();

  // ---------------------------------------------------------------- E) víc řádků najednou, přepínání záložek, Načíst znovu
  h = await otevriAdmin({ typy: typyPredvyplnene() });
  p = h.page;
  await otevriPanel(h);
  await R(p, 'invoice').locator('.ue-adresy-pole').fill('rozpracovano@ucetni.cz');
  await R(p, 'delivery_note').locator('.ue-adresy-pole').fill('dodaci@ucetni.cz');
  await R(p, 'delivery_note').locator('.ue-uloz').click();
  await p.waitForFunction(() => /Uloženo ✓/.test(document.querySelector('#ueTelo tr[data-typ="delivery_note"] .ue-radek-stav').textContent));
  ok(puty(h).join() === 'delivery_note' && await dirty(h, 'invoice') && (await R(p, 'invoice').locator('.ue-adresy-pole').inputValue()) === 'rozpracovano@ucetni.cz', 'E1 uložení jednoho řádku se nedotkne rozeditovaného jiného řádku (zůstane zvýrazněný a nezměněný)');
  const g0 = h.pozadavky.get;
  await klik(p, 'emails'); await ceka(150); await klik(p, 'accountantemails'); await ceka(300);
  ok(h.pozadavky.get === g0 && (await R(p, 'invoice').locator('.ue-adresy-pole').inputValue()) === 'rozpracovano@ucetni.cz', 'E2 přepnutí záložky pryč a zpět při rozeditovaném řádku tabulku NEnačte znovu (rozpracované zůstane)');
  h.stav.dialogOdpoved = false;
  await p.locator('#ueNacistZnovu').click(); await ceka(300);
  ok(h.stav.dialogy.length === 1 && /neuložené změny/i.test(h.stav.dialogy[0].text) && h.pozadavky.get === g0 && await dirty(h, 'invoice'), 'E3 „Načíst znovu“ s neuloženou změnou se zeptá; po „Zrušit“ se nic nenačte a změna zůstane', h.stav.dialogy);
  h.stav.dialogOdpoved = true;
  await p.locator('#ueNacistZnovu').click();
  await p.waitForFunction(g => true, g0); await ceka(400);
  ok(h.pozadavky.get === g0 + 1 && !(await dirty(h, 'invoice')) && (await R(p, 'invoice').locator('.ue-adresy-pole').inputValue()) === 'faktury@ucetni.cz, kopie@ucetni.cz', 'E4 po potvrzení se tabulka načte znovu a neuložená změna se zahodí', { get: h.pozadavky.get });
  const g1 = h.pozadavky.get;
  await klik(p, 'emails'); await ceka(150); await klik(p, 'accountantemails'); await ceka(400);
  ok(h.pozadavky.get === g1 + 1, 'E5 bez rozeditovaných řádků se při návratu na záložku načtou čerstvá data', { g1, ted: h.pozadavky.get });
  await p.locator('#ueNacistZnovu').click(); await ceka(300);
  ok(h.pozadavky.get === g1 + 2 && h.stav.dialogy.length === 2, 'E6 „Načíst znovu“ bez změn se nepta (počet dialogů zůstal 2 z kroků E3/E4) a načte', { get: h.pozadavky.get, dialogy: h.stav.dialogy.length });
  await h.zavri();

  // ---------------------------------------------------------------- F) chyby při načtení + zotavení
  const NACTENI = [
    ['404 (API ještě není nasazené)', { __status: 404 }, /Tabulka bude fungovat až po nasazení API/],
    ['403 (bez práva)', { __status: 403 }, /nemáš oprávnění/],
    ['500', { __status: 500 }, /Načtení se nepovedlo \(500\)/],
    ['výpadek spojení', { __abort: true }, /Načtení se nepovedlo/],
    ['rozbitý JSON', { __raw: '<html>not json' }, /Načtení se nepovedlo/],
    ['odpověď bez seznamu typů', { __body: { neco: 1 } }, /Načtení se nepovedlo/],
  ];
  for (const [nazev, get, re] of NACTENI) {
    h = await otevriAdmin({ get });
    await otevriPanel(h);
    const q = await h.page.evaluate(() => ({ stav: document.getElementById('ueStav').textContent, trida: document.getElementById('ueStav').className, radku: document.querySelectorAll('#ueTelo tr').length }));
    ok(re.test(q.stav) && /ue-chyba/.test(q.trida) && q.radku === 0, `F načtení ${nazev}: srozumitelná hláška, žádné řádky, žádná výjimka`, q);
    if (nazev.startsWith('404')) {
      h.stav.get = null;
      await h.page.locator('#ueNacistZnovu').click();
      await h.page.waitForFunction(() => document.querySelectorAll('#ueTelo tr').length === 6, null, { timeout: 5000 });
      ok(!/ue-chyba/.test(await h.page.locator('#ueStav').getAttribute('class')) && /Načteno/.test(await h.page.locator('#ueStav').textContent()), 'F zotavení: po nasazení API stačí „Načíst znovu“ a tabulka naskočí');
    }
    ok(h.chyby.length === 0, `F načtení ${nazev}: žádné chyby JS`, h.chyby.slice(0, 2));
    await h.zavri();
  }

  // ---------------------------------------------------------------- G) nedůvěryhodný obsah (XSS)
  const zly = TYPY();
  Object.assign(zly[0], { nazev: '<img src=x onerror="window.__xss=1">Faktura', adresy: ['<script>window.__xss=2</script>@x.cz'], poznamka: '<b onmouseover="window.__xss=3">pozn</b>', upravil: '<i>Hacker</i>', upraveno: iso(5), aktivni: true });
  h = await otevriAdmin({ typy: zly });
  await otevriPanel(h);
  const xs = await h.page.evaluate(() => ({ xss: window.__xss, img: document.querySelectorAll('#ueTelo img, #ueTelo script, #ueTelo b, #ueTelo i').length, typ: document.querySelector('#ueTelo tr[data-typ="invoice"] .ue-typ').textContent, adresy: document.querySelector('#ueTelo tr[data-typ="invoice"] .ue-adresy-pole').value, meta: document.querySelector('#ueTelo tr[data-typ="invoice"] .ue-meta').textContent }));
  ok(xs.xss === undefined && xs.img === 0 && /<img src=x/.test(xs.typ) && /<script>/.test(xs.adresy) && /<i>Hacker<\/i>/.test(xs.meta), 'G nedůvěryhodný text ze serveru (název, adresy, poznámka, jméno) je jen text: žádný <img>/<script>/<b>, nic se nespustilo', xs);
  await h.zavri();

  // ---------------------------------------------------------------- H) oprávnění (TAB_SECTION)
  const NAV = 'accountantemails';
  h = await otevriAdmin({ user: { role: 'manager', permissions: {} } });
  ok(await h.page.locator('.tab-btn[data-tab="' + NAV + '"]').evaluate(b => b.style.display === 'none'), 'H1 role bez práva `ucetni_emaily` záložku nevidí (fail-closed)');
  await h.zavri();
  h = await otevriAdmin({ user: { role: 'manager', permissions: { ucetni_emaily: true } } });
  ok(await h.page.locator('.tab-btn[data-tab="' + NAV + '"]').evaluate(b => b.style.display !== 'none'), 'H2 role s právem `ucetni_emaily` záložku vidí');
  await h.zavri();
  h = await otevriAdmin({ user: { role: 'manager', permissions: { emaily_odchozi: true, doklady: true, prijate_doklady: true, nastaveni: true } } });
  ok(await h.page.locator('.tab-btn[data-tab="' + NAV + '"]').evaluate(b => b.style.display === 'none'), 'H3 práva k Emailům odchozím, Dokladům, Přijatým dokladům ani Nastavení záložku NEodemykají (vlastní sekce)');
  await h.zavri();
  h = await otevriAdmin({});
  ok(await h.page.locator('.tab-btn[data-tab="' + NAV + '"]').evaluate(b => b.style.display !== 'none'), 'H4 admin záložku vidí vždy');
  await h.zavri();

  // ---------------------------------------------------------------- I) telefon 390 px
  h = await otevriAdmin({ viewport: { width: 390, height: 800 }, typy: typyPredvyplnene() });
  await otevriPanel(h);
  const m = await h.page.evaluate(() => {
    const pan = document.getElementById('tab-accountantemails'), pr = pan.getBoundingClientRect(); let max = 0;
    pan.querySelectorAll('*').forEach(e => { const r = e.getBoundingClientRect(); if (r.width > 0) max = Math.max(max, r.right); });
    const tr = document.querySelector('#ueTelo tr'), td = tr.querySelectorAll('td');
    return { panelRight: Math.round(pr.right), maxPotomek: Math.round(max), okno: innerWidth, trDisplay: getComputedStyle(tr).display, tdDisplay: getComputedStyle(td[1]).display, label: getComputedStyle(td[1], '::before').content, theadDisplay: getComputedStyle(document.querySelector('#ueTabulka thead')).display,
      ulozH: Math.round(document.querySelector('#ueTelo .ue-uloz').getBoundingClientRect().height), inputH: Math.round(document.querySelector('#ueTelo .ue-adresy-pole').getBoundingClientRect().height), sw: pan.scrollWidth, cw: pan.clientWidth };
  });
  ok(m.trDisplay === 'block' && m.tdDisplay === 'block' && m.theadDisplay === 'none' && /E-mailové adresy účetní/.test(m.label), 'I1 telefon: každý řádek je karta (hlavička tabulky skrytá, popisek pole z data-label)', m);
  ok(m.maxPotomek <= m.panelRight + 1 && m.sw <= m.cw + 1, 'I2 telefon 390 px: nic nepřetéká přes pravý okraj panelu (bez vodorovného posuvu)', m);
  ok(m.ulozH >= 44 && m.inputH >= 40, 'I3 telefon: tlačítko Uložit ≥ 44 px, pole ≥ 40 px', m);
  await h.zavri();

  console.log(`\n==> ${total - bad}/${total} kontrol OK`);
  process.exit(bad ? 1 : 0);
})();
