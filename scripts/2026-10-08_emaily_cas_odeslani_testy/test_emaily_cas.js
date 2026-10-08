// Admin > E-maily: SKUTECNY cas odeslani (sent_at) vedle casu zarazeni (created_at) - bot16, 2026-10-08.
// Robert (pres bot9) u radku id 201 (Danovy doklad k prijate platbe 26VDD00001): seznam u "Odeslano" ukazoval "28. 9. 2026 0:42:08" = cas ZARAZENI do fronty, ale e-mail odesel az po schvaleni
// (audit_log 6392, 29. 9. 2026 9:32:42). Pozadavek: sloupce "Zarazeno" a "Odeslano"; "Odeslano" jen kdyz API vraci pole sent_at (do nasazeni backendu zustava jen "Zarazeno").
// SKUTECNY admin.html + admin/js proti falesnemu serveru (harness z 2026-10-06_ucetni_emaily_testy, zadna DB / sit).
// Kandidat pred nasazenim:  ADMIN_HTML=<kandidat>/admin.html JS_DIR=<kandidat>/js node scripts/2026-10-08_emaily_cas_odeslani_testy/test_emaily_cas.js
// Puvodni kod (mutace) MUSI selhat: stejny prikaz s ADMIN_HTML/JS_DIR z kommitu pred touto zmenou.
const { otevriAdmin } = require('../2026-10-06_ucetni_emaily_testy/harness');
let bad = 0, total = 0;
const ok = (c, t, d) => { total++; if (!c) bad++; console.log(`[${c ? 'OK   ' : 'CHYBA'}] ${t}${!c && d !== undefined ? ' | ' + (typeof d === 'string' ? d : JSON.stringify(d)) : ''}`); };
const ceka = ms => new Promise(r => setTimeout(r, ms));
const norm = s => String(s == null ? '' : s).replace(/\s+/g, ' ').trim();

const radek = (id, extra) => Object.assign({ id, order_id: 187, purchase_order_id: null, document_id: null, template_key: 'custom', template_label: 'Vlastní e-mail', recipient_email: 'x@example.cz', cc_email: null,
  subject: 'Predmet ' + id, body_text: 'telo', status: 'sent', error_message: null, trigger_type: 'manual', sent_by: 'Robert', created_at: '2026-09-29T10:06:57', order_number: 'OBJ-2026-00001', customer_name: 'Zakaznik',
  document_number: null, po_number: null, po_supplier_name: null }, extra || {});
// stejne hodnoty jako ve skutecne DB (shop_emails 197 / 201 / 203 po zpetnem doplneni sent_at z audit_log)
const R201 = radek(201, { document_id: 90, document_number: '26VDD00001', template_key: 'payment_tax_document', template_label: 'Daňový doklad k přijaté platbě', recipient_email: 'eraz@centrum.cz', trigger_type: 'auto',
  subject: 'Daňový doklad k přijaté platbě č. 26VDD00001 - objednávka OBJ-2026-00001', created_at: '2026-09-28T00:42:08', sent_at: '2026-09-29T09:32:42' });
const R203 = radek(203, { document_id: 90, document_number: '26VDD00001', template_key: 'payment_tax_document', template_label: 'Daňový doklad k přijaté platbě', recipient_email: 'eraz@centrum.cz', trigger_type: 'manual', created_at: '2026-09-29T10:06:57', sent_at: '2026-09-29T10:06:57' });
const R197 = radek(197, { order_id: null, purchase_order_id: 37, po_number: 'NO-2026-00037', order_number: null, template_key: 'purchase_order', template_label: 'Objednávka dodavateli', recipient_email: 'info@tbaplast.cz', trigger_type: 'auto', created_at: '2026-08-24T07:48:41', sent_at: '2026-08-24T10:04:06' });
const PENDING = radek(301, { status: 'pending', trigger_type: 'auto', created_at: '2026-10-08T15:00:00', sent_at: null, sent_by: 'Systém (automaticky)' });
const REJECTED = radek(302, { status: 'rejected', trigger_type: 'auto', created_at: '2026-10-07T12:00:00', sent_at: null });
const FAILED = radek(303, { status: 'failed', error_message: 'SMTP chyba XY', trigger_type: 'auto', created_at: '2026-10-06T12:00:00', sent_at: null });
const BEZ_CASU = radek(304, { status: 'sent', trigger_type: 'auto', created_at: '2026-10-05T12:00:00', sent_at: null });
const NOVE = [R201, R203, R197, PENDING, REJECTED, FAILED, BEZ_CASU];
const bezSentAt = r => { const k = Object.assign({}, r); delete k.sent_at; return k; };
const STARE = NOVE.map(bezSentAt);
const odp = (emails, extra) => Object.assign({ emails, counts: { all: emails.length }, status_counts: { sent: emails.filter(e => e.status === 'sent').length, pending: emails.filter(e => e.status === 'pending').length }, total: emails.length, page: 1, page_size: 50 }, extra || {});

const otevriSeznam = async (emails, opts) => {
  const h = await otevriAdmin(Object.assign({ emails: odp(emails) }, opts || {}));
  await h.page.evaluate(() => document.querySelector('.tab-btn[data-tab="emails"]').click());
  await h.page.waitForFunction(n => document.querySelectorAll('#emailsTbody tr.order-row[data-email-id]').length >= n, emails.length, { timeout: 8000 }).catch(() => {});
  return h;
};
const viditelneHlavicky = p => p.$$eval('#emailsTbl thead th', ths => ths.filter(t => getComputedStyle(t).display !== 'none').map(t => (t.textContent || '').trim()));
const bunky = async (p, id) => {      // chybejici bunky (puvodni kod ma o sloupec min) se doplni, aby mutace hlasila vsechna selhani misto pádu
  const r = await p.$$eval(`#emailsTbody tr.order-row[data-email-id="${id}"] > td`, tds => tds.map(t => ({ text: (t.textContent || '').replace(/\s+/g, ' ').trim(), title: (t.querySelector('[title]') || {}).title || '' })));
  const n = r.length;
  while (r.length < 12) r.push({ text: '(chybí)', title: '' });
  r.pocet = n;
  return r;
};

(async () => {
  // ---------- A: API s polem sent_at ----------
  let h = await otevriSeznam(NOVE);
  let p = h.page;
  const hl = await viditelneHlavicky(p);
  ok(hl.join('|') === '|Zařazeno|Odesláno|Příjemce|Předmět|Šablona|Objednávka|Přílohy|Způsob|Stav', 'A1 hlavička: Zařazeno + Odesláno (žádné „Datum“, sloupec způsobu se nejmenuje „Odeslání“)', hl);
  const b201 = await bunky(p, 201);
  ok(b201.pocet === 10, 'A2 řádek 201 má 10 buněk (stejně jako hlavička)', b201.pocet);
  ok(/^28\. 9\. 2026,? 0:42:08$/.test(b201[1].text), 'A3 řádek 201: „Zařazeno“ = 28. 9. 2026 0:42:08 (čas zařazení do fronty)', b201[1].text);
  ok(/^29\. 9\. 2026,? 9:32:42$/.test(b201[2].text), 'A4 řádek 201: „Odesláno“ = 29. 9. 2026 9:32:42 (čas schválení = skutečné odeslání)', b201[2].text);
  ok(b201[1].text !== b201[2].text, 'A5 u řádku 201 se oba časy liší (to je celý smysl opravy)');
  ok(b201[8].text === 'Automaticky' && b201[9].text === 'Odesláno', 'A6 řádek 201: způsob „Automaticky“ a stav „Odesláno“ beze změny', [b201[8].text, b201[9].text]);
  const b203 = await bunky(p, 203);
  ok(b203[1].text === b203[2].text && /10:06:57/.test(b203[2].text), 'A7 ručně odeslaný (203): oba časy stejné (odeslalo se hned)', [b203[1].text, b203[2].text]);
  const b197 = await bunky(p, 197);
  ok(/24\. 8\. 2026,? 7:48:41/.test(b197[1].text) && /24\. 8\. 2026,? 10:04:06/.test(b197[2].text), 'A8 e-mail dodavateli (197): zařazeno 7:48:41, odesláno 10:04:06', [b197[1].text, b197[2].text]);
  const bp = await bunky(p, 301), br = await bunky(p, 302), bf = await bunky(p, 303), bn = await bunky(p, 304);
  ok(bp[2].text === '—' && /čeká na schválení/.test(bp[2].title), 'A9 čekající: Odesláno „—“ s vysvětlením (čeká na schválení)', bp[2]);
  ok(br[2].text === '—' && /Zamítnuto/.test(br[2].title), 'A10 zamítnutý: Odesláno „—“ (neodešel)', br[2]);
  ok(bf[2].text === '—' && /Neodesláno/.test(bf[2].title), 'A11 selhaný: Odesláno „—“', bf[2]);
  ok(bn[2].text === '—' && /nezaznamenal/.test(bn[2].title), 'A12 odeslaný bez zaznamenaného času: „—“ s vysvětlením (nevymýšlí se čas zařazení)', bn[2]);
  const pocty = await p.$$eval('#emailsTbody tr.order-row[data-email-id]', trs => trs.map(t => t.children.length));
  ok(pocty.length === 7 && pocty.every(n => n === 10), 'A13 všechny řádky mají 10 buněk', pocty);
  const detail = await p.$$eval('#emailsTbody tr.email-preview-detail > td', tds => tds.map(t => t.colSpan));
  ok(detail.length === 1 && detail[0] === 10, 'A14 řádek s náhledem čekajícího e-mailu přes všech 10 sloupců', detail);
  ok(await p.$$eval('#emailsTbody tr.order-row[data-email-id="201"]', trs => trs.length) === 1 && (await p.locator('#emailsTbody tr.order-row[data-email-id="301"] .email-preview-btn').count()) === 1, 'A15 čekající řádek dál nabízí Náhled / Schválit / Zamítnout');
  // prazdny vysledek filtru po nacteni novych dat: sloupec zustane, colspan 10
  await p.route('**/api/admin/emails**', r => r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(odp([], { counts: { all: 0 }, total: 0 })) }));
  await p.fill('#emailSearchQ', 'nic'); await p.click('#emailSearchApply'); await ceka(500);
  const prazdny = await p.$$eval('#emailsTbody td', tds => tds.map(t => [t.colSpan, (t.textContent || '').trim()]));
  const hl2 = await viditelneHlavicky(p);
  ok(prazdny.length === 1 && prazdny[0][0] === 10 && /Žádné e-maily/.test(prazdny[0][1]), 'A16 prázdný výsledek: jeden řádek přes 10 sloupců', prazdny);
  ok(hl2.includes('Odesláno'), 'A17 hlavička „Odesláno“ po prázdném výsledku zůstává', hl2);
  ok(h.chyby.length === 0, 'A18 žádné chyby JS', h.chyby.slice(0, 3));
  if (process.env.SNIMEK) { await h.zavri(); }
  else await h.zavri();

  // ---------- B: API bez pole sent_at (backend jeste nenasazen) ----------
  h = await otevriSeznam(STARE);
  p = h.page;
  const hlB = await viditelneHlavicky(p);
  ok(hlB.join('|') === '|Zařazeno|Příjemce|Předmět|Šablona|Objednávka|Přílohy|Způsob|Stav', 'B1 bez sent_at: hlavička „Zařazeno“, žádný sloupec „Odesláno“ (ne řada pomlček)', hlB);
  const bB = await bunky(p, 201);
  ok(bB.pocet === 9 && /^28\. 9\. 2026,? 0:42:08$/.test(bB[1].text) && bB[8].text === 'Odesláno', 'B2 řádek 201: 9 buněk, „Zařazeno“ 28. 9. 0:42:08, stav „Odesláno“', bB.map(x => x.text));
  const poctyB = await p.$$eval('#emailsTbody tr.order-row[data-email-id]', trs => trs.map(t => t.children.length));
  ok(poctyB.every(n => n === 9), 'B3 všechny řádky mají 9 buněk', poctyB);
  ok((await p.$$eval('#emailsTbody tr.email-preview-detail > td', tds => tds.map(t => t.colSpan)))[0] === 9, 'B4 řádek s náhledem přes 9 sloupců');
  ok(await p.evaluate(() => !document.querySelector('#emailsTbody .email-odeslano')), 'B5 žádná buňka „Odesláno“');
  ok(h.chyby.length === 0, 'B6 žádné chyby JS', h.chyby.slice(0, 3));

  // ---------- C: historie e-mailů v detailu objednávky ----------
  const objednavka = emails => p.route('**/api/admin/orders/187/emails', r => r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ emails }) }));
  await objednavka([R201, R203, PENDING, REJECTED, FAILED, BEZ_CASU]);
  await p.evaluate(() => loadOrderEmails(187));
  await ceka(300);
  const thC = await p.$$eval('#orderModalEmails', t => { const tab = t[0].closest('table'); return [...tab.querySelectorAll('thead th')].filter(x => getComputedStyle(x).display !== 'none').map(x => x.textContent.trim()); });
  ok(thC.join('|') === 'Zařazeno|Odesláno|Komu|Předmět|Šablona|Stav', 'C1 historie objednávky: Zařazeno + Odesláno + Komu + Předmět + Šablona + Stav', thC);
  const rC = await p.$$eval('#orderModalEmails tr', trs => trs.map(t => [...t.children].map(c => (c.textContent || '').replace(/\s+/g, ' ').trim())));
  ok(rC.length === 6 && rC.every(r => r.length === 6), 'C2 6 řádků po 6 buňkách', rC.map(r => r.length));
  ok(/^28\. 9\. 2026,? 0:42:08$/.test(rC[0][0]) && /^29\. 9\. 2026,? 9:32:42$/.test(rC[0][1]), 'C3 řádek 201 v historii objednávky: zařazeno 28. 9. 0:42:08, odesláno 29. 9. 9:32:42', rC[0].slice(0, 2));
  ok(rC[0][5] === 'Odesláno' && rC[2][5] === 'Čeká na schválení' && rC[3][5] === 'Zamítnuto' && rC[4][5] === 'Selhalo' && rC[5][5] === 'Odesláno', 'C4 štítky stavu v historii: čekající není „Selhalo“, zamítnutý je „Zamítnuto“', rC.map(r => r[5]));
  ok(rC[2][1] === '—' && rC[3][1] === '—' && rC[4][1] === '—' && rC[5][1] === '—', 'C5 neodeslané a bez času: „—“', rC.map(r => r[1]));
  ok((await p.locator('#orderModalEmails .order-status-pill.zrusena').first().getAttribute('title')) === 'SMTP chyba XY', 'C6 u „Selhalo“ zůstává chyba v bublině');
  await objednavka(STARE.slice(0, 2).concat([bezSentAt(PENDING)]));
  await p.evaluate(() => loadOrderEmails(187)); await ceka(300);
  const thC2 = await p.$$eval('#orderModalEmails', t => [...t[0].closest('table').querySelectorAll('thead th')].filter(x => getComputedStyle(x).display !== 'none').map(x => x.textContent.trim()));
  const rC2 = await p.$$eval('#orderModalEmails tr', trs => trs.map(t => t.children.length));
  ok(thC2.join('|') === 'Zařazeno|Komu|Předmět|Šablona|Stav' && rC2.every(n => n === 5), 'C7 historie objednávky bez sent_at: původních 5 sloupců, hlavička „Zařazeno“', [thC2, rC2]);
  await objednavka([]);
  await p.evaluate(() => loadOrderEmails(187)); await ceka(300);
  ok((await p.$$eval('#orderModalEmails td', t => t.map(x => x.colSpan)))[0] === 5, 'C8 prázdná historie: jeden řádek přes 5 sloupců');
  ok(h.chyby.length === 0, 'C9 žádné chyby JS', h.chyby.slice(0, 3));
  await h.zavri();

  // ---------- D: nebezpecne hodnoty se nevykonaji ----------
  const ZLY = radek(401, { sent_at: '<img src=x onerror=window.__xss=1>', created_at: '<b>x</b>' });
  h = await otevriSeznam([ZLY, R201]);
  p = h.page;
  const bz = await bunky(p, 401);
  ok(!/[<>]/.test(bz[1].text + bz[2].text) && (await p.evaluate(() => window.__xss)) === undefined && (await p.locator('#emailsTbody img, #emailsTbody b').count()) === 0, 'D1 hodnoty s HTML v datu jsou jen text (žádný <img> / <b>, nic se nespustilo)', bz.slice(0, 3));
  ok(h.chyby.length === 0, 'D2 žádné chyby JS', h.chyby.slice(0, 3));
  await h.zavri();

  // ---------- F: Systemove e-maily (overeni e-mailu pri registraci) - stejny vzor, GET /api/admin/system-emails ----------
  const sys = (id, extra) => Object.assign({ id, user_id: 5, kind: 'email_verification', kind_label: 'Ověření e-mailu', recipient_email: 'novy@example.cz', subject: 'Potvrďte e-mail ' + id, body_text: 'odkaz', status: 'sent',
    error_message: null, sent_by: 'Robert', created_at: '2026-09-27T22:00:00', sent_at: '2026-09-28T00:59:39' }, extra || {});
  const SYS_NOVE = [sys(20), sys(21, { status: 'pending', sent_at: null, sent_by: null, created_at: '2026-10-08T14:00:00' }), sys(22, { status: 'rejected', sent_at: null })];
  const SYS_STARE = SYS_NOVE.map(bezSentAt);
  const otevriSystem = async data => {
    const hh = await otevriAdmin({ emails: odp([]) });
    await hh.page.route('**/api/admin/system-emails**', r => r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ emails: data, status_counts: { sent: 1, pending: 1, rejected: 1 }, total: data.length, page: 1, page_size: 50 }) }));
    await hh.page.evaluate(() => document.querySelector('.tab-btn[data-tab="emails"]').click());
    await hh.page.evaluate(() => loadSystemEmails());      // pri startu admin.html se nacte hned (jeste pred touto atrapou), proto znovu
    await hh.page.waitForFunction(n => document.querySelectorAll('#systemEmailsTbody tr').length >= n, data.length, { timeout: 8000 }).catch(() => {});
    await ceka(300);
    return hh;
  };
  const hlavickySys = pp => pp.$$eval('#systemEmailsTbl thead th', ths => ths.filter(x => getComputedStyle(x).display !== 'none').map(x => (x.textContent || '').trim()));
  const radkySys = pp => pp.$$eval('#systemEmailsTbody > tr:not(.system-email-preview-detail)', trs => trs.map(t => [...t.children].map(c => (c.textContent || '').replace(/\s+/g, ' ').trim())));
  h = await otevriSystem(SYS_NOVE);
  p = h.page;
  const hF = await hlavickySys(p), rF = await radkySys(p);
  ok(hF.join('|') === '|Zařazeno|Odesláno|Příjemce|Předmět|Typ|Stav', 'F1 systémové e-maily: hlavička Zařazeno + Odesláno', hF);
  ok(rF.length === 3 && rF.every(r => r.length === 7), 'F2 3 řádky po 7 buňkách', rF.map(r => r.length));
  ok(/^27\. 9\. 2026,? 22:00:00$/.test(rF[0][1]) && /^28\. 9\. 2026,? 0:59:39$/.test(rF[0][2]), 'F3 odeslaný systémový e-mail: zařazeno 27. 9. 22:00:00, odesláno 28. 9. 0:59:39', rF[0].slice(1, 3));
  ok(rF[1][2] === '—' && rF[2][2] === '—' && rF[1][6].indexOf('Čeká na schválení') === 0 && rF[2][6] === 'Zamítnuto', 'F4 čekající a zamítnutý: Odesláno „—“, štítky stavu beze změny', [rF[1][2], rF[2][2], rF[1][6], rF[2][6]]);
  ok((await p.$$eval('#systemEmailsTbody tr.system-email-preview-detail > td', t => t.map(x => x.colSpan)))[0] === 7, 'F5 řádek s náhledem čekajícího přes 7 sloupců');
  ok(h.chyby.length === 0, 'F6 žádné chyby JS', h.chyby.slice(0, 3));
  await h.zavri();
  h = await otevriSystem(SYS_STARE);
  p = h.page;
  const hF2 = await hlavickySys(p), rF2 = await radkySys(p);
  ok(hF2.join('|') === '|Zařazeno|Příjemce|Předmět|Typ|Stav' && rF2.length === 3 && rF2.every(r => r.length === 6), 'F7 systémové e-maily bez sent_at: původních 6 sloupců, hlavička „Zařazeno“', [hF2, rF2.map(r => r.length)]);
  ok((await p.$$eval('#systemEmailsTbody tr.system-email-preview-detail > td', t => t.map(x => x.colSpan)))[0] === 6, 'F8 řádek s náhledem přes 6 sloupců');
  ok(h.chyby.length === 0, 'F9 žádné chyby JS', h.chyby.slice(0, 3));
  await h.zavri();

  // ---------- E: snimek pro kontrolu ocima (jen kdyz SNIMEK=cesta.png) ----------
  if (process.env.SNIMEK) {
    h = await otevriSeznam([R201, R203, R197], { viewport: { width: 1500, height: 520 } });
    await h.page.addStyleTag({ content: '#emailsTbody tr[data-email-id="201"] td { outline: 2px solid #f5a623; outline-offset: -2px; }' });
    await h.page.locator('#tab-emails').screenshot({ path: process.env.SNIMEK });
    await h.zavri();
  }
  console.log(`\n==> ${total - bad}/${total} kontrol OK`);
  process.exit(bad ? 1 : 0);
})().catch(e => { console.error(e); process.exit(2); });
