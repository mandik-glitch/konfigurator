// Online nabidka: ZAKRESLENE ZMENY (bot16, 2026-10-07) - stranka (frontend). Backend (api/offer_markup_requests.py) ma vlastni testy v scripts/2026-10-07_nabidka_zakresleni_testy/.
// Robert: "zakreslovani zmen komplet je na webu hotove, jen to prenest do online nabidky a to i pro stoly z generatoru" (+ Vandr). Pouziva se STEJNY modul jako na
// product.html (webapp/js/image-markup.js): tuzka, krouzek, skrtnout, sipka, text, 3 barvy; "Zakreslit zmenu" u obrazku -> kresleni -> Hotovo -> formular (poznamka + kontakt)
// -> POST /api/public/offers/<token>/markup-requests (multipart: email, phone, note, views JSON, composite_i JPEG).
// SKUTECNA stranka webapp/nabidka-online.html + SKUTECNY image-markup.js v Chromiu proti falesnemu serveru (harness bot8, page.route; zadna DB, zadna sit mimo CDN pro 3D).
// Spusteni: node test_zakresleni_stranka.js     Kandidat: NABIDKA_HTML=/cesta/nabidka-online.html node test_zakresleni_stranka.js
// Mutacni kontrola: NABIDKA_HTML=<puvodni verze> MUSI selhat (zadna tlacitka, stary stetec).
const fs = require('fs');
const path = require('path');
const zlib = require('zlib');
const pw = require('/opt/konfigurator/node_modules/playwright-core');
const _launch = pw.chromium.launch.bind(pw.chromium);                          // WebGL (SwiftShader) pro zivy 3D prohlizec V3D
pw.chromium.launch = (o = {}) => _launch(Object.assign({}, o, { args: [...(o.args || []), '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] }));
const { otevriNabidku, vzorovaNabidka } = require('../2026-10-06_nabidka_montaz_polozky_testy/harness');

const KONFIG = JSON.parse(fs.readFileSync(path.join(__dirname, '../2026-10-06_nabidka_cover_testy/fixture_nabidka_z_konfigurace.json'), 'utf8'));
const GLB = fs.readFileSync(path.join(__dirname, '../../webapp/katalog/20x40x100.glb'));
const vysl = [];
const over = (nazev, podminka, detail) => { vysl.push(!!podminka); console.log((podminka ? 'OK   ' : 'FAIL ') + nazev + (podminka ? '' : '  -> ' + JSON.stringify(detail))); };
const ceka = ms => new Promise(r => setTimeout(r, ms));

// --- syntetický PNG 1280x720 (rozmer jako vykres z Vandru)
const CRC = (() => { const t = []; for (let n = 0; n < 256; n++) { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1; t[n] = c >>> 0; } return t; })();
const crc32 = buf => { let c = 0xffffffff; for (const b of buf) c = CRC[(c ^ b) & 0xff] ^ (c >>> 8); return (c ^ 0xffffffff) >>> 0; };
const chunk = (typ, data) => { const t = Buffer.from(typ), len = Buffer.alloc(4), crc = Buffer.alloc(4); len.writeUInt32BE(data.length); crc.writeUInt32BE(crc32(Buffer.concat([t, data]))); return Buffer.concat([len, t, data, crc]); };
function png(w, h) {
  const raw = Buffer.alloc((w * 3 + 1) * h, 255);
  for (let y = 0; y < h; y++) { raw[y * (w * 3 + 1)] = 0; for (let x = 0; x < w; x++) { const o = y * (w * 3 + 1) + 1 + x * 3; const r = x < 6 || x >= w - 6 || y < 6 || y >= h - 6; if (r) { raw[o] = 220; raw[o + 1] = 30; raw[o + 2] = 30; } } }
  const ihdr = Buffer.alloc(13); ihdr.writeUInt32BE(w, 0); ihdr.writeUInt32BE(h, 4); ihdr[8] = 8; ihdr[9] = 2;
  return Buffer.concat([Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]), chunk('IHDR', ihdr), chunk('IDAT', zlib.deflateSync(raw)), chunk('IEND', Buffer.alloc(0))]);
}
const OBR = png(1280, 720);

// --- multipart parser (jen to, co potrebujeme)
function multipart(buf, contentType) {
  const m = /boundary=(?:"([^"]+)"|([^;]+))/.exec(contentType || '');
  if (!m) return [];
  const b = Buffer.from('--' + (m[1] || m[2]));
  const casti = []; let pos = buf.indexOf(b);
  while (pos !== -1) {
    const next = buf.indexOf(b, pos + b.length);
    if (next === -1) break;
    const raw = buf.slice(pos + b.length + 2, next - 2);
    const he = raw.indexOf('\r\n\r\n');
    const hdr = raw.slice(0, he).toString('utf8');
    casti.push({ name: (/name="([^"]*)"/.exec(hdr) || [])[1], filename: (/filename="([^"]*)"/.exec(hdr) || [])[1], body: raw.slice(he + 4) });
    pos = next;
  }
  return casti;
}

// --- falesny server: obrazky 1280x720, model GLB, odeslani zakresleni (zachytava a odpovida podle `stav.odpoved`)
function server() {
  const stav = { posty: [], odpoved: () => ({ status: 201, json: { status: 'ok', views: 1 } }) };
  stav.trasy = async (route, { p, m, json, req }) => {
    if (/^\/api\/public\/offers\/TESTTOKEN\/image\/(narys|bokorys|pudorys|view3d_a|view3d_b|narys_ghost|bokorys_ghost|pudorys_ghost)$/.test(p)) { route.fulfill({ status: 200, contentType: 'image/png', body: OBR }); return true; }
    if (p === '/api/public/offers/TESTTOKEN/model') { route.fulfill({ status: 200, contentType: 'model/gltf-binary', body: GLB }); return true; }
    if (p === '/api/public/offers/TESTTOKEN/markup-requests' && m === 'POST') {
      const buf = req.postDataBuffer(); const ct = req.headers()['content-type'];
      stav.posty.push({ casti: multipart(buf, ct), velikost: buf ? buf.length : 0 });
      const o = stav.odpoved(stav.posty.length);
      if (o.html) route.fulfill({ status: o.status, contentType: 'text/html', body: '<html>chyba</html>' });
      else route.fulfill({ status: o.status, contentType: 'application/json', body: JSON.stringify(o.json) });
      return true;
    }
    return false;
  };
  return stav;
}

const KLIC = page => page.evaluate(() => (document.querySelector('.slide.active') || { dataset: {} }).dataset.key);
async function naStranku(page, klic) {
  for (let i = 0; i < 10 && (await KLIC(page)) !== klic; i++) { await page.keyboard.press('ArrowRight'); await page.waitForTimeout(450); }
  await page.waitForFunction(() => [...document.querySelectorAll('.slide.active img')].every(i => !i.src || i.complete), null, { timeout: 8000 }).catch(() => {});
  await page.waitForTimeout(400);
}
const vandr = (opts, flag = true) => vzorovaNabidka(d => { d.markup_requests = flag; d.offer_options = Object.assign({}, d.offer_options, { vandr_single_drawing: true }, opts); return d; });
const DVE = { vandr_drawings: [{ slot: 'narys', label: 'Levá strana' }, { slot: 'bokorys', label: 'Pravá strana' }] };
const viditelne = (page, sel) => page.evaluate(s => [...document.querySelectorAll(s)].filter(e => { const r = e.getBoundingClientRect(), c = getComputedStyle(e); return c.display !== 'none' && c.visibility !== 'hidden' && r.width > 0 && r.height > 0; }).length, sel);

async function nakresli(page) {
  await page.waitForSelector('.im-overlay .im-canvas', { timeout: 10000 });
  await page.waitForFunction(() => { const c = document.querySelector('.im-overlay .im-canvas'); return c && c.getBoundingClientRect().width > 50; }, null, { timeout: 10000 });
  const b = await (await page.$('.im-overlay .im-canvas')).boundingBox();
  await page.mouse.move(b.x + b.width * 0.30, b.y + b.height * 0.30);
  await page.mouse.down();
  for (let i = 1; i <= 14; i++) await page.mouse.move(b.x + b.width * (0.30 + i * 0.025), b.y + b.height * (0.30 + i * 0.015), { steps: 3 });
  await page.mouse.up();
}
const hotovo = async page => { await page.click('.im-overlay .im-done-btn'); await page.waitForSelector('#imgMarkupSubmit', { timeout: 10000 }); };
async function vyplnAOdesli(page, o = {}) {
  await page.fill('#imNote', o.note || 'Prosím posunout police o 5 cm výš.');
  await page.fill('#imEmail', o.email || 'zakaznik@firma-test.cz');
  await page.fill('#imPhone', o.phone || '+420 603 111 222');
  await page.click('#imgMarkupSubmit .im-submit-btn');
}
const jpeg = b => b && b.length > 1000 && b[0] === 0xff && b[1] === 0xd8;

(async () => {
  console.log('== A) viditelnost: kdy se tlacitka ukazou');
  {
    // A1 nabidka ze sceny (1. vetev) BEZ priznaku: stary stetec zustava, zadna nova tlacitka
    const { browser, page, chyby } = await otevriNabidku({ width: 1920, height: 1080, nabidka: vzorovaNabidka(), trasy: server().trasy });
    await naStranku(page, 'drawings_1');
    over('A1 nabidka ze sceny bez priznaku: zadna tlacitka "Zakreslit zmenu", stary stetec (Kreslit/Oznacit) zustava, "Odeslat zmeny" neni', (await viditelne(page, '.om-draw-btn')) === 0 && (await viditelne(page, '.slide.active .markup-toolbar')) === 1 && (await viditelne(page, '#nav .markup-number-btn')) === 1 && (await viditelne(page, '#btnMarkupSend')) === 0 && (await viditelne(page, '.om-hint')) === 0, chyby);
    await browser.close();
  }
  {
    // A2 Vandr s priznakem, 2 vykresy
    const { browser, page, chyby } = await otevriNabidku({ width: 1920, height: 1080, nabidka: vandr(DVE), trasy: server().trasy });
    await naStranku(page, 'drawings_vandr');
    const t = await page.evaluate(() => [...document.querySelectorAll('.slide.active .view-card')].map(c => ({ label: c.querySelector('.caption').childNodes[0].textContent.trim(), tl: !!c.querySelector('.caption .om-draw-btn'), viditelne: (b => !!b && getComputedStyle(b).display !== 'none')(c.querySelector('.om-draw-btn')) })));
    over('A2 Vandr s priznakem: obe karty maji viditelne tlacitko "Zakreslit zmenu"', t.length === 2 && t.every(x => x.tl && x.viditelne) && t[0].label === 'Levá strana', t);
    over('A2b stary stetec (Kreslit/Oznacit/Ulozit oznaceni) je skryty, "Odeslat zmeny" neni videt, dokud nic nezakreslim', (await viditelne(page, '#nav .markup-number-btn')) === 0 && (await viditelne(page, '#nav .markup-save-btn')) === 0 && (await viditelne(page, '#btnMarkupSend')) === 0, null);
    over('A2c pod nadpisem stranky je napoveda "Chcete neco upravit? Kliknete na Zakreslit zmenu..."', (await viditelne(page, '.slide.active .om-hint')) === 1 && /Zakreslit změnu/.test(await page.evaluate(() => document.querySelector('.slide.active .om-hint').textContent)), null);
    over('A2d bez chyb JS', chyby.length === 0, chyby.slice(0, 2));
    await browser.close();
  }
  {
    // A3 admin ("Zobrazit online"): tlacitka nevidi
    const n = vandr(DVE); n.viewer_role = 'admin';
    const { browser, page } = await otevriNabidku({ width: 1920, height: 1080, nabidka: n, trasy: server().trasy });
    await naStranku(page, 'drawings_vandr');
    over('A3 admin (viewer_role admin): zadne tlacitko "Zakreslit zmenu" ani napoveda neni videt', (await viditelne(page, '.om-draw-btn')) === 0 && (await viditelne(page, '.om-hint')) === 0, null);
    over('A3b admin MA stary stetec (Robert 2026-10-07, nabidka Logiman0133: "nevidim moznosti zakreslit zmeny, zmizelo to"): v dolni liste Oznacit i Ulozit oznaceni, na strance vykresu lista Kreslit/Oznacit',
      (await viditelne(page, '#nav .markup-number-btn')) === 1 && (await viditelne(page, '#nav .markup-save-btn')) === 1 && (await viditelne(page, '.slide.active .markup-toolbar')) === 1, { number: await viditelne(page, '#nav .markup-number-btn'), save: await viditelne(page, '#nav .markup-save-btn'), toolbar: await viditelne(page, '.slide.active .markup-toolbar') });
    await browser.close();
  }
  {
    // A4 priznak false u Vandr (starsi API / nepodporovana nabidka): nic se nezmeni oproti dnesku
    const { browser, page } = await otevriNabidku({ width: 1920, height: 1080, nabidka: vandr(DVE, false), trasy: server().trasy });
    await naStranku(page, 'drawings_vandr');
    over('A4 Vandr BEZ priznaku (API jeste nenasazeno): zadna nova tlacitka (nic se nerozbije)', (await viditelne(page, '.om-draw-btn')) === 0 && (await viditelne(page, '#btnMarkupSend')) === 0, null);
    await browser.close();
  }
  {
    // A5 nabidka z konfigurace stolu S vykresy ze sceny (drawings_1/2): nova tlacitka, stary stetec skryty
    const n = JSON.parse(JSON.stringify(KONFIG)); n.markup_requests = true; n.configuration.vykresy = true;
    const { browser, page } = await otevriNabidku({ width: 1920, height: 1080, nabidka: n, trasy: server().trasy });
    await naStranku(page, 'drawings_1');
    over('A5 stul z generatoru (s vykresy): u narysu a bokorysu tlacitko "Zakreslit zmenu", stary stetec (lista Kreslit/Oznacit) skryty', (await viditelne(page, '.slide.active .om-draw-btn')) === 2 && (await viditelne(page, '.slide.active .markup-toolbar')) === 0, null);
    await browser.close();
  }

  console.log('== B) tok: kresleni -> Hotovo -> formular -> odeslani (Vandr, 2 vykresy)');
  {
    const srv = server();
    const { browser, page, chyby } = await otevriNabidku({ width: 1920, height: 1080, nabidka: vandr(DVE), trasy: srv.trasy });
    await naStranku(page, 'drawings_vandr');
    await page.click('.slide.active .view-card:nth-child(1) .om-draw-btn');
    await page.waitForSelector('.im-overlay .im-canvas', { timeout: 10000 });
    const nastroje = await page.evaluate(() => [...document.querySelectorAll('.im-overlay .im-toolbar .im-btn')].map(b => b.textContent.replace(/\s+/g, ' ').trim()));
    over('B1 otevre se kreslici okno s nastroji z webu (Tuzka, Krouzek, Skrtnout, Sipka, Text, Zpet, Vymazat, Hotovo, Zavrit)', ['Tužka', 'Kroužek', 'Škrtnout', 'Šipka', 'Text', 'Zpět', 'Vymazat', 'Hotovo', 'Zavřít'].every(x => nastroje.some(n => n.includes(x))), nastroje);
    const stav1 = await page.evaluate(() => ({ nazev: (document.querySelector('.im-overlay .im-title') || {}).textContent, pohled: (document.querySelector('.im-overlay .im-viewlabel') || {}).textContent, src: (document.querySelector('.im-overlay .im-img') || {}).src }));
    over('B1b okno nese cislo nabidky, popisek pohledu "Levá strana" a obrazek vykresu z nabidky', /Logiman/.test(stav1.nazev) && stav1.pohled === 'Levá strana' && /\/image\/narys$/.test(stav1.src), stav1);
    await nakresli(page);
    // klavesy: sipka doprava v kreslicim okne NEmeni stranku nabidky
    await page.keyboard.press('ArrowRight'); await page.waitForTimeout(500);
    over('B2 behem kresleni sipka doprava neprepne stranku nabidky', (await KLIC(page)) === 'drawings_vandr', await KLIC(page));
    await hotovo(page);
    over('B3 po "Hotovo" se hned otevre formular (1 nahled), v dolni liste je "Odeslat zmeny (1)"', (await viditelne(page, '#imgMarkupSubmit .im-view-thumb')) === 1 && /\(1\)/.test(await page.evaluate(() => document.getElementById('btnMarkupSend').textContent)), null);
    await vyplnAOdesli(page);
    await page.waitForFunction(() => !document.getElementById('imgMarkupSubmit'), null, { timeout: 8000 });
    const post = srv.posty[0];
    const pole = n => (post.casti.find(c => c.name === n) || {}).body;
    const views = JSON.parse((pole('views') || Buffer.from('[]')).toString('utf8'));
    over('B4 odeslano jednim POSTem: e-mail, telefon, poznamka a views[0] = Levá strana / drawing / narys / aspon 1 znacka (tuzka)', srv.posty.length === 1 && String(pole('email')) === 'zakaznik@firma-test.cz' && /603 111 222/.test(String(pole('phone'))) && /police/.test(String(pole('note'))) && views.length === 1 && views[0].label === 'Levá strana' && views[0].page === 'drawings_vandr' && views[0].view.kind === 'drawing' && views[0].view.key === 'narys' && views[0].marks.length >= 1 && views[0].marks[0].kind === 'pen' && views[0].image_w > 0, { views, pole: post.casti.map(c => c.name) });
    over('B5 priloha composite_0 je platny JPEG (zakresleny obrazek), zadne composite_1', jpeg(pole('composite_0')) && !pole('composite_1'), (pole('composite_0') || []).length);
    over('B6 po uspechu: pocitadlo zmizi (0 pohledu), v dolni liste neni "Odeslat zmeny", potvrzeni zakaznikovi (toast)', (await viditelne(page, '#btnMarkupSend')) === 0 && /odeslali|Změny/.test(await page.evaluate(() => (document.getElementById('toastStack') || { textContent: '' }).textContent)), null);
    over('B7 bez chyb JS', chyby.length === 0, chyby.slice(0, 3));
    await browser.close();
  }

  console.log('== C) vice pohledu najednou, zavreni formulare, odebrani, limit');
  {
    const srv = server(); srv.odpoved = () => ({ status: 201, json: { status: 'ok', views: 2 } });
    const { browser, page } = await otevriNabidku({ width: 1920, height: 1080, nabidka: vandr(DVE), trasy: srv.trasy });
    await naStranku(page, 'drawings_vandr');
    await page.click('.slide.active .view-card:nth-child(1) .om-draw-btn'); await nakresli(page); await hotovo(page);
    await page.click('#imgMarkupSubmit .im-close-btn');                                                  // formular zavreny bez odeslani
    over('C1 po zavreni formulare pohled zustava: dolni lista "Odeslat zmeny (1)"', (await viditelne(page, '#btnMarkupSend')) === 1, null);
    await page.click('.slide.active .view-card:nth-child(2) .om-draw-btn'); await nakresli(page); await hotovo(page);
    over('C2 druhy pohled: formular ukazuje 2 nahledy, dolni lista (2)', (await viditelne(page, '#imgMarkupSubmit .im-view-thumb')) === 2 && /\(2\)/.test(await page.evaluate(() => document.getElementById('btnMarkupSend').textContent)), null);
    await page.click('#imgMarkupSubmit .im-view-thumb:nth-child(2) .im-view-remove');
    over('C3 odebrani nahledu (x) ve formulari: zbyde 1 a dolni lista (1)', (await viditelne(page, '#imgMarkupSubmit .im-view-thumb')) === 1 && /\(1\)/.test(await page.evaluate(() => document.getElementById('btnMarkupSend').textContent)), null);
    await page.click('#imgMarkupSubmit .im-close-btn');
    await page.click('.slide.active .view-card:nth-child(2) .om-draw-btn'); await nakresli(page); await hotovo(page);
    await vyplnAOdesli(page);
    await page.waitForFunction(() => !document.getElementById('imgMarkupSubmit'), null, { timeout: 8000 });
    const post = srv.posty[0]; const views = JSON.parse(String(post.casti.find(c => c.name === 'views').body));
    over('C4 odeslany 2 pohledy: views = [Levá strana, Pravá strana], composite_0 i composite_1 jsou JPEG', views.length === 2 && views[0].label === 'Levá strana' && views[1].label === 'Pravá strana' && jpeg((post.casti.find(c => c.name === 'composite_0') || {}).body) && jpeg((post.casti.find(c => c.name === 'composite_1') || {}).body), views.map(v => v.label));
    await browser.close();
  }
  {
    // limit 6 pohledu
    const { browser, page } = await otevriNabidku({ width: 1920, height: 1080, nabidka: vandr(DVE), trasy: server().trasy });
    await naStranku(page, 'drawings_vandr');
    for (let i = 0; i < 6; i++) { await page.click('.slide.active .view-card:nth-child(1) .om-draw-btn'); await nakresli(page); await hotovo(page); await page.click('#imgMarkupSubmit .im-close-btn'); }
    await page.click('.slide.active .view-card:nth-child(1) .om-draw-btn'); await page.waitForTimeout(500);
    over('C5 7. pohled: kreslici okno se neotevre, toast hlasi limit 6', (await viditelne(page, '.im-overlay')) === 0 && /nejvýše 6/.test(await page.evaluate(() => (document.getElementById('toastStack') || { textContent: '' }).textContent)), null);
    await browser.close();
  }

  console.log('== D) chyby serveru: formular zustane otevreny, zakaznik nepride o praci');
  for (const [nazev, odp, re] of [
    ['400 s hlaskou', () => ({ status: 400, json: { error: 'Zadejte platný e-mail (doména neexistuje).', field: 'email' } }), /doména neexistuje/],
    ['429 prilis casto', () => ({ status: 429, json: { error: 'x' } }), /příliš často/],
    ['502 HTML (nginx)', () => ({ status: 502, html: true }), /dočasně nedostupný/],
    ['413 HTML (nginx)', () => ({ status: 413, html: true }), /příliš velké/],
  ]) {
    const srv = server(); srv.odpoved = odp;
    const { browser, page } = await otevriNabidku({ width: 1920, height: 1080, nabidka: vandr(DVE), trasy: srv.trasy });
    await naStranku(page, 'drawings_vandr');
    await page.click('.slide.active .view-card:nth-child(1) .om-draw-btn'); await nakresli(page); await hotovo(page);
    await vyplnAOdesli(page); await page.waitForTimeout(900);
    const st = await page.evaluate(() => ({ text: (document.querySelector('#imgMarkupSubmit .im-status') || {}).textContent, otevreno: !!document.getElementById('imgMarkupSubmit') }));
    over(`D ${nazev}: hlaska zakaznikovi, formular zustava, pohled se neztrati (v liste porad (1))`, re.test(st.text || '') && st.otevreno && /\(1\)/.test(await page.evaluate(() => document.getElementById('btnMarkupSend').textContent)), st);
    await browser.close();
  }

  console.log('== E) 3D: staticke nahledy i ZIVY prohlizec (snimek aktualniho pohledu)');
  {
    const srv = server();
    const n = JSON.parse(JSON.stringify(KONFIG)); n.markup_requests = true;
    const { browser, page, chyby } = await otevriNabidku({ width: 1920, height: 1080, nabidka: n, trasy: srv.trasy, cdn: true });
    await naStranku(page, 'view_3d');
    let ziv = false;
    try { await page.waitForSelector('.om-3d-bar.live', { timeout: 90000 }); ziv = true; } catch (e) { ziv = false; }
    over('E1 zivy 3D prohlizec se nacetl a pod nim je tlacitko "Zakreslit zmenu v tomto 3D pohledu"', ziv, chyby.slice(0, 3));
    if (ziv) {
      await page.click('.om-3d-bar .om-draw-btn');
      await page.waitForSelector('.im-overlay .im-img', { timeout: 20000 });
      const src = await page.evaluate(() => document.querySelector('.im-overlay .im-img').src);
      over('E2 kreslici okno dostalo SNIMEK 3D platna (data:image/jpeg) a popisek "3D pohled"', /^data:image\/jpeg/.test(src) && src.length > 2000 && /3D pohled/.test(await page.evaluate(() => document.querySelector('.im-overlay .im-viewlabel').textContent)), src.slice(0, 40));
      await nakresli(page); await hotovo(page); await vyplnAOdesli(page);
      await page.waitForFunction(() => !document.getElementById('imgMarkupSubmit'), null, { timeout: 8000 });
      const post = srv.posty[0]; const v = JSON.parse(String(post.casti.find(c => c.name === 'views').body))[0];
      over('E3 odeslano: view = 3d/live (s kamerou), page view_3d, composite JPEG', v.view.kind === '3d' && v.view.key === 'live' && v.page === 'view_3d' && jpeg((post.casti.find(c => c.name === 'composite_0') || {}).body), v);
    }
    await browser.close();
  }
  {
    // staticke 3D nahledy (fallback), kdyz se zivy model nenacte (CDN zakazan)
    const srv = server();
    const n = JSON.parse(JSON.stringify(KONFIG)); n.markup_requests = true;
    const { browser, page } = await otevriNabidku({ width: 1920, height: 1080, nabidka: n, trasy: srv.trasy });
    await naStranku(page, 'view_3d'); await page.waitForTimeout(1500);
    const t = await page.evaluate(() => [...document.querySelectorAll('#viewer3dFallback .view-card')].map(c => ({ label: c.querySelector('.caption').childNodes[0].textContent.trim(), tl: !!c.querySelector('.om-draw-btn'), viditelne: c.getBoundingClientRect().width > 0 })));
    over('E4 bez zivého modelu jsou staticke 3D pohledy (uhel 1 a 2) s tlacitkem "Zakreslit zmenu"', t.length === 2 && t.every(x => x.tl), t);
    await browser.close();
  }

  console.log('== F) telefon 390 px a tisk');
  {
    const { browser, page } = await otevriNabidku({ width: 390, height: 800, mobil: true, nabidka: vandr(DVE), trasy: server().trasy });
    await naStranku(page, 'drawings_vandr');
    const r = await page.evaluate(() => { const b = document.querySelector('.slide.active .view-card .om-draw-btn').getBoundingClientRect(); return { sirka: b.width, vlevo: b.left, vpravo: b.right, vw: innerWidth, preteka: document.documentElement.scrollWidth > innerWidth + 1 }; });
    over('F1 telefon: tlacitko je cele v obrazovce, nic nepreteka', r.vlevo >= 0 && r.vpravo <= r.vw && !r.preteka, r);
    await page.tap ? await page.tap('.slide.active .view-card .om-draw-btn') : await page.click('.slide.active .view-card .om-draw-btn');
    await page.waitForSelector('.im-overlay .im-canvas', { timeout: 10000 });
    const lista = await page.evaluate(() => { const t = document.querySelector('.im-overlay .im-toolbar').getBoundingClientRect(); return { vlevo: t.left, vpravo: t.right, vw: innerWidth }; });
    over('F2 telefon: nastrojova lista kresleni se vejde na sirku displeje', lista.vlevo >= -1 && lista.vpravo <= lista.vw + 1, lista);
    await browser.close();
  }
  {
    const { browser, page } = await otevriNabidku({ width: 794, height: 1123, nabidka: vandr(DVE), trasy: server().trasy });
    await naStranku(page, 'drawings_vandr');
    await page.emulateMedia({ media: 'print' }); await page.waitForTimeout(300);
    over('F3 tisk: tlacitka "Zakreslit zmenu", napoveda a "Odeslat zmeny" se netisknou', (await viditelne(page, '.om-draw-btn')) === 0 && (await viditelne(page, '.om-hint')) === 0 && (await viditelne(page, '#btnMarkupSend')) === 0, null);
    await browser.close();
  }

  const ok = vysl.filter(Boolean).length;
  console.log(`\nVYSLEDEK zakreslene zmeny v online nabidce (stranka): ${ok}/${vysl.length} OK`);
  process.exit(ok === vysl.length ? 0 : 1);
})().catch(e => { console.error('TEST SPADL:', e); process.exit(2); });
