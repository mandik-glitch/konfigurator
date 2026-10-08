// Online nabidka: 2D vykresy z Vandr systemu (stranka "Technicke vykresy", drawings_vandr) jsou VELKE (bot16, 2026-10-07).
// Robert: "v te nabidce online, 2D pohledy prevedene z vandr systemu jsou moc male, chce to zvetsit".
// PUVODNE: Vandr dava kotovany vykres jako 1280x720 PNG (kóty ~14 px); spolecna nabidka (2-3 vykresy) je ukazovala vedle sebe v kartach max 620 px siroke a 80 vh vysoke
// (obrazek 618x348 = pulka velikosti, kolem nej velka prazdna seda plocha), jeden vykres max 1100 px. TED: karty pod sebou na plnou sirku (max 1600 px), vyska podle obrazku,
// obrazek nejvyse tak vysoky, aby se vesel na obrazovku (u vice vykresu o neco nizsi, aby pod prvnim byl videt okraj dalsiho). Jen na obrazovce - tisk beze zmeny.
// SKUTECNA stranka webapp/nabidka-online.html v Chromiu proti falesnemu serveru (harness bot8, page.route, zadna DB/sit); vykresy = syntetické 1280x720 PNG (stejny rozmer jako z Vandru).
// Spusteni: node test_vandr_vykresy.js        Kandidat: NABIDKA_HTML=/cesta/nabidka-online.html node test_vandr_vykresy.js
// Mutacni kontrola: NABIDKA_HTML=<puvodni verze> MUSI selhat (obrazek 618 px siroky, karty vedle sebe).
const zlib = require('zlib');
const { otevriNabidku, vzorovaNabidka } = require('../2026-10-06_nabidka_montaz_polozky_testy/harness');

const vysl = [];
const over = (nazev, podminka, detail) => { vysl.push(!!podminka); console.log((podminka ? 'OK   ' : 'FAIL ') + nazev + (podminka ? '' : '  -> ' + JSON.stringify(detail))); };

// --- syntetický PNG 1280x720 (bila plocha, cervený ramecek, sede pruhy) - jen aby mel obrazek skutecny rozmer a pomer jako u Vandru
const CRC = (() => { const t = []; for (let n = 0; n < 256; n++) { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1; t[n] = c >>> 0; } return t; })();
const crc32 = buf => { let c = 0xffffffff; for (const b of buf) c = CRC[(c ^ b) & 0xff] ^ (c >>> 8); return (c ^ 0xffffffff) >>> 0; };
function chunk(typ, data) { const t = Buffer.from(typ), len = Buffer.alloc(4), crc = Buffer.alloc(4); len.writeUInt32BE(data.length); crc.writeUInt32BE(crc32(Buffer.concat([t, data]))); return Buffer.concat([len, t, data, crc]); }
function png(w, h, pruh) {
  const raw = Buffer.alloc((w * 3 + 1) * h, 255);
  for (let y = 0; y < h; y++) {
    raw[y * (w * 3 + 1)] = 0;
    for (let x = 0; x < w; x++) {
      const o = y * (w * 3 + 1) + 1 + x * 3;
      const ramecek = x < 6 || x >= w - 6 || y < 6 || y >= h - 6;
      const sedy = Math.abs((x - y * 1.5) % 160) < 12;
      const c = ramecek ? [220, 30, 30] : sedy ? [200, 200, 205] : [255, 255, 255];
      raw[o] = c[0]; raw[o + 1] = c[1]; raw[o + 2] = pruh ? Math.min(c[2], 240) : c[2];
    }
  }
  const ihdr = Buffer.alloc(13); ihdr.writeUInt32BE(w, 0); ihdr.writeUInt32BE(h, 4); ihdr[8] = 8; ihdr[9] = 2;
  return Buffer.concat([Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]), chunk('IHDR', ihdr), chunk('IDAT', zlib.deflateSync(raw)), chunk('IEND', Buffer.alloc(0))]);
}
const OBR = png(1280, 720, false);
const trasy = async (route, { p }) => {
  if (!/^\/api\/public\/offers\/TESTTOKEN\/image\/(narys|bokorys|pudorys)$/.test(p)) return false;
  route.fulfill({ status: 200, contentType: 'image/png', body: OBR }); return true;
};

const PRIPADY = {
  jedna: { vandr_single_drawing: true },
  jedna_ze_spolecne: { vandr_single_drawing: true, vandr_drawings: [{ slot: 'narys', label: 'Pravá strana' }] },
  dve: { vandr_single_drawing: true, vandr_drawings: [{ slot: 'narys', label: 'Levá strana' }, { slot: 'bokorys', label: 'Pravá strana' }] },
  tri: { vandr_single_drawing: true, vandr_drawings: [{ slot: 'narys', label: 'Levá strana' }, { slot: 'bokorys', label: 'Pravá strana' }, { slot: 'pudorys', label: 'Přepážka' }] },
};
const nabidka = opts => vzorovaNabidka(d => { d.offer_options = Object.assign({}, d.offer_options, opts); return d; });
const KEY = page => page.evaluate(() => (document.querySelector('.slide.active') || { dataset: {} }).dataset.key);
async function naStranku(page, klic) {
  for (let i = 0; i < 10 && (await KEY(page)) !== klic; i++) { await page.keyboard.press('ArrowRight'); await page.waitForTimeout(450); }
  await page.waitForFunction(() => [...document.querySelectorAll('.slide.active .view-card img')].every(i => i.complete && i.naturalWidth > 0), null, { timeout: 8000 });
  await page.waitForTimeout(500);
}
// mereni stranky Vykresy (bezi ve strance)
const MERENI = () => {
  const s = document.querySelector('.slide.active');
  const sr = s.getBoundingClientRect();
  const karty = [...s.querySelectorAll('.view-card')].map(c => {
    const cr = c.getBoundingClientRect(), img = c.querySelector('img'), ir = img.getBoundingClientRect();
    const pomer = img.naturalWidth / img.naturalHeight;
    return { top: cr.top - sr.top + s.scrollTop, bottom: cr.bottom - sr.top + s.scrollTop, w: cr.width, h: cr.height, imgW: ir.width, imgH: ir.height, videtelnaW: Math.min(ir.width, ir.height * pomer), videtelnaH: Math.min(ir.height, ir.width / pomer), pomer };
  });
  return { karty, scroll: s.scrollHeight, klient: s.clientHeight, sirkaOkna: innerWidth, vyskaOkna: innerHeight, preteka: document.documentElement.scrollWidth > innerWidth + 1 || s.scrollWidth > s.clientWidth + 1 };
};
const STARE_W = 618;   // dosavadni sirka obrazku ve spolecne nabidce

(async () => {
  const OKNA = [[1400, 900], [1920, 1080], [2560, 1300], [1280, 720]];
  for (const [pripad, opts] of Object.entries(PRIPADY)) {
    const vice = pripad === 'dve' || pripad === 'tri';
    for (const [w, h] of OKNA) {
      const { browser, page, chyby } = await otevriNabidku({ width: w, height: h, nabidka: nabidka(opts), trasy });
      await naStranku(page, 'drawings_vandr');
      const m = await page.evaluate(MERENI);
      const ctx = `${pripad} ${w}x${h}`;
      const nahore = Math.max(320, m.vyskaOkna - 290), samotny = Math.max(360, m.vyskaOkna - 240);
      const ocekH = vice ? nahore : samotny;                                           // nejvyssi obrazek (max-height)
      const ocekVidW = Math.min(1598, ocekH * (1280 / 720));
      over(`A1 ${ctx}: kazdy vykres je velky - viditelna sirka obrazku ${m.karty.map(k => Math.round(k.videtelnaW)).join('/')} px (ocekavano ~${Math.round(ocekVidW)}), puvodne ${STARE_W} px`, m.karty.length === (opts.vandr_drawings ? opts.vandr_drawings.length : 1) && m.karty.every(k => k.videtelnaW >= ocekVidW * 0.95 && k.videtelnaW > STARE_W * 1.2), m.karty);
      over(`A2 ${ctx}: karty jsou POD SEBOU (zadna vedle sebe, zadne preklady) a bez prazdne sede plochy (karta = obrazek + popisek)`, m.karty.every((k, i) => i === 0 || (k.top >= m.karty[i - 1].bottom + 8)) && m.karty.every(k => k.h <= k.imgH + 70), m.karty);
      if (vice) over(`A3 ${ctx}: pod prvnim vykresem je videt okraj dalsiho (znamka "rolovat dal"): jeho horni okraj je v okne a hloubka nahledu 15-400 px`, m.karty[1].top < m.klient - 15 && m.karty[1].top > m.klient - 400, { top2: m.karty[1].top, klient: m.klient });
      else over(`A3 ${ctx}: jediny vykres se cely vejde na obrazovku bez rolovani`, m.scroll <= m.klient + 4, { scroll: m.scroll, klient: m.klient });
      over(`A4 ${ctx}: nic nepreteka vodorovne`, !m.preteka, m);
      over(`A5 ${ctx}: bez chyb JS`, chyby.length === 0, chyby.slice(0, 2));
      await browser.close();
    }
  }

  console.log('== B) telefon 390 px: plna sirka displeje, bez prazdne sede plochy, bez vodorovneho preteceni');
  for (const [pripad, opts] of Object.entries(PRIPADY)) {
    const { browser, page } = await otevriNabidku({ width: 390, height: 800, mobil: true, nabidka: nabidka(opts), trasy });
    await naStranku(page, 'drawings_vandr');
    const m = await page.evaluate(MERENI);
    over(`B1 telefon ${pripad}: obrazek na plnou sirku displeje (${m.karty.map(k => Math.round(k.videtelnaW)).join('/')} px), karta = obrazek + popisek, nic nepreteka`, m.karty.every(k => k.videtelnaW >= 320 && k.h <= k.imgH + 70) && !m.preteka, m);
    await browser.close();
  }

  console.log('== C) rolovani: dalsi vykresy jsou dosazitelne (kolecko) a po poslednim se prejde na dalsi stranu');
  {
    const { browser, page } = await otevriNabidku({ width: 1920, height: 1080, nabidka: nabidka(PRIPADY.tri), trasy });
    await naStranku(page, 'drawings_vandr');
    await page.mouse.move(960, 540);
    const viditelne = () => page.evaluate(() => { const s = document.querySelector('.slide.active'); const r = s.getBoundingClientRect(); return [...s.querySelectorAll('.view-card')].map(c => { const b = c.getBoundingClientRect(); return b.top >= r.top - 1 && b.bottom <= r.bottom + 1; }); });
    const videt = [await viditelne()];
    for (let i = 0; i < 40 && (await KEY(page)) === 'drawings_vandr'; i++) {
      await page.mouse.wheel(0, 300); await page.waitForTimeout(200);
      videt.push(await viditelne());
    }
    await page.waitForTimeout(1200);
    const viditelneAspon = [0, 1, 2].map(i => videt.some(v => v[i]));
    over('C1 kolecko: postupne je CELE videt prvni, druha i treti karta (3 vykresy)', viditelneAspon.every(Boolean), viditelneAspon);
    over('C2 po dorolovani na konec kolecko prejde na dalsi stranu nabidky', (await KEY(page)) !== 'drawings_vandr', await KEY(page));
    await browser.close();
  }

  console.log('== D) NE-Vandr nabidky a tisk beze zmeny');
  {
    const { browser, page } = await otevriNabidku({ width: 1920, height: 1080, nabidka: vzorovaNabidka(), trasy });
    await naStranku(page, 'drawings_1');
    const m = await page.evaluate(() => [...document.querySelectorAll('.slide.active .view-card')].map(c => { const r = c.getBoundingClientRect(); return [Math.round(r.width), Math.round(r.height), Math.round(r.left)]; }));
    over('D1 nabidka ze sceny (drawings_1): dve karty vedle sebe max 900 px siroke, vyska 88 vh (beze zmeny)', m.length === 2 && m.every(k => k[0] <= 901 && k[0] >= 600 && Math.abs(k[1] - 0.88 * 1080) <= 2) && m[1][2] > m[0][2], m);
    await browser.close();
  }
  {
    const { browser, page } = await otevriNabidku({ width: 794, height: 1123, nabidka: nabidka(PRIPADY.dve), trasy });
    await naStranku(page, 'drawings_vandr');
    await page.emulateMedia({ media: 'print' }); await page.waitForTimeout(400);
    const t = await page.evaluate(() => [...document.querySelectorAll('.slide[data-key="drawings_vandr"] .view-card')].map(c => [getComputedStyle(c.querySelector('img')).maxHeight, Math.round(c.getBoundingClientRect().height)]));
    over('D2 tisk: vykresy z Vandru maji v tisku vlastni max-height 80 mm (ne obrazovkove pravidlo podle okna) a kazda karta ma nenulovou vysku (2026-10-07: sloupec karet se v PDF sbalil na vysku 0 a vykresy chybely)', t.length === 2 && t.every(v => Math.abs(parseFloat(v[0]) - 302.36) < 1 && v[1] > 60), t);
    await browser.close();
  }

  console.log('== E) kreslici plocha (oznaceni) porad lezi presne na obrazku');
  {
    const { browser, page } = await otevriNabidku({ width: 1920, height: 1080, nabidka: nabidka(PRIPADY.dve), trasy });
    await naStranku(page, 'drawings_vandr');
    const r = await page.evaluate(() => [...document.querySelectorAll('.slide.active .view-card .img-wrap')].map(w => { const i = w.querySelector('img').getBoundingClientRect(), c = w.querySelector('canvas'); if (!c) return null; const b = c.getBoundingClientRect(); return { dx: Math.abs(b.left - i.left), dy: Math.abs(b.top - i.top), dw: Math.abs(b.width - i.width), dh: Math.abs(b.height - i.height) }; }));
    over('E1 kreslici plocha (canvas) pokryva obrazek na pixel (nebo plocha neni) u obou vykresu', r.length === 2 && r.every(x => x === null || (x.dx <= 2 && x.dy <= 2 && x.dw <= 2 && x.dh <= 2)), r);
    await browser.close();
  }

  const ok = vysl.filter(Boolean).length;
  console.log(`\nVYSLEDEK Vandr 2D vykresy v online nabidce: ${ok}/${vysl.length} OK`);
  process.exit(ok === vysl.length ? 0 : 1);
})().catch(e => { console.error('TEST SPADL:', e); process.exit(2); });
