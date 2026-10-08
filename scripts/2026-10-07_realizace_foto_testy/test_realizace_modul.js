// Modul webapp/js/realizace-foto.js (bot16, 2026-10-07; Robert: "v kazde sestave do aut i stolu a v online nabidce musi byt ukazana realna fotografie 4ks a odkaz na fotogalerii; ty 4 fotky se musi tocit,
// kolovat, tzn v kazde nabidce budou jine i v kazde karte"). SKUTECNY modul v Chromiu, ZIVA galerie (read-only), skutecne soubory fotek z disku. Kandidat: RF_JS=/cesta/realizace-foto.js node test_realizace_modul.js
const { chromium } = require('/opt/konfigurator/node_modules/playwright-core');
const fs = require('fs'), path = require('path');
const { REPO, nactiGalerie, galerieRoute } = require('./harness_realizace');
const MODUL = process.env.RF_JS || path.join(REPO, 'webapp/js/realizace-foto.js');
const vysl = [];
const over = (nazev, podminka, detail) => { vysl.push(!!podminka); console.log((podminka ? 'OK   ' : 'FAIL ') + nazev + (podminka ? '' : '  -> ' + JSON.stringify(detail).slice(0, 400))); };

(async () => {
  const G = await nactiGalerie();
  over('0 zive API galerie: vestavby >= 100 fotek, stoly >= 10 fotek, vsechny verejne s url', G.vestavby.images.length >= 100 && G.stoly.images.length >= 10 && [...G.vestavby.images, ...G.stoly.images].every(i => i.url && i.active), [G.vestavby.images.length, G.stoly.images.length]);
  const browser = await chromium.launch({ args: ['--no-sandbox'] });
  const chyby = [];
  async function strana(opt = {}) {
    const ctx = opt.ctx || await browser.newContext({ viewport: { width: opt.sirka || 1280, height: 900 } });          // opt.ctx = dalsi nacteni stejneho prohlizece (sdileny localStorage)
    const page = await ctx.newPage();
    page.on('pageerror', e => chyby.push(e.message));
    await page.route('**/*', async route => {
      const u = new URL(route.request().url());
      if (u.hostname !== 'rf.test') return route.abort();
      if (u.pathname === '/t.html') return route.fulfill({ status: 200, contentType: 'text/html; charset=utf-8', body: '<!doctype html><html><body style="margin:0;background:#22262e;color:#e8eaed;font-family:sans-serif"><div id="a" style="max-width:1000px;margin:20px auto"></div><div id="b" style="max-width:1000px;margin:20px auto"></div><script src="/js/realizace-foto.js"></script></body></html>' });
      if (u.pathname === '/js/realizace-foto.js') return route.fulfill({ status: 200, contentType: 'text/javascript', body: fs.readFileSync(MODUL) });
      if (galerieRoute(route, u, G, opt)) return;
      return route.fulfill({ status: 404, body: '' });
    });
    await page.goto('http://rf.test/t.html');
    return { page, ctx };
  }

  // ---- A) algoritmus vyberu na ZIVYCH datech
  let { page, ctx } = await strana();
  const sady = await page.evaluate((imgs) => {
    const ids = i => i.map(x => x.id);
    const pro = (n, tyden) => Array.from({ length: n }, (_, k) => ids(window.RealizaceFoto.vyber(imgs, 'p' + (k + 1), 4, tyden)));
    return { t0: pro(120, 0), t0b: pro(120, 0), t1: pro(120, 1), male: ids(window.RealizaceFoto.vyber(imgs.slice(0, 3), 'x', 4, 0)), prazdne: window.RealizaceFoto.vyber([], 'x', 4, 0).length, N: imgs.length };
  }, G.vestavby.images.map(i => ({ id: i.id, url: i.url })));
  const klic = s => s.slice().sort((a, b) => a - b).join(',');
  over('A1 kazda sada ma 4 ruzne fotky z galerie vestaveb', sady.t0.every(s => s.length === 4 && new Set(s).size === 4), sady.t0.find(s => s.length !== 4 || new Set(s).size !== 4));
  over('A2 vyber je deterministicky (stejna karta / nabidka = stejne fotky pri obnoveni)', JSON.stringify(sady.t0) === JSON.stringify(sady.t0b), null);
  over('A3 120 ruznych karet / nabidek ma >= 110 RUZNYCH sad (kazda jina)', new Set(sady.t0.map(klic)).size >= 110, new Set(sady.t0.map(klic)).size);
  over('A4 fotky "koluji" po cele galerii: 120 karet pokryje >= 90 % z ' + sady.N + ' fotek', new Set(sady.t0.flat()).size >= 0.9 * sady.N, new Set(sady.t0.flat()).size);
  const prekryv = sady.t0.slice(1).map((s, i) => s.filter(x => sady.t0[i].includes(x)).length);
  over('A5 sousedni karty (p1 / p2 / p3 ...) maji skoro ruzne fotky (prumerny prekryv < 0,6)', prekryv.reduce((a, b) => a + b, 0) / prekryv.length < 0.6, prekryv.reduce((a, b) => a + b, 0) / prekryv.length);
  over('A6 po tydnu se sada u vetsiny karet zmeni (>= 90 % ze 120 se lisi)', sady.t0.filter((s, i) => klic(s) !== klic(sady.t1[i])).length >= 108, sady.t0.filter((s, i) => klic(s) !== klic(sady.t1[i])).length);
  over('A7 malá galerie (3 fotky): ukaze se 3 (ne 4), prazdna galerie: nic', sady.male.length === 3 && sady.prazdne === 0, [sady.male, sady.prazdne]);
  await ctx.close();

  // ---- B) vykresleni: vestavby i stoly
  for (const [typ, tag, hrefOcek, textOcek] of [['vestavby', 'vestavby_dodavek', '/realizace.html?category=vestavby_dodavek', 'Zobrazit fotogalerii vestaveb →'], ['stoly', 'realizace_stolu', '/realizace.html?category=realizace_stolu', 'Zobrazit fotogalerii stolů →']]) {
    ({ page, ctx } = await strana());
    const ok = await page.evaluate(t => window.RealizaceFoto.mount(document.getElementById('a'), { typ: t, seed: 'p4955', eager: true }), typ);
    await page.waitForFunction(() => [...document.querySelectorAll('#a img')].length === 4 && [...document.querySelectorAll('#a img')].every(i => i.complete), null, { timeout: 15000 }).catch(() => {});
    const d = await page.evaluate(() => ({ imgs: [...document.querySelectorAll('#a .rf-foto img')].map(i => ({ src: i.getAttribute('src'), w: i.naturalWidth, alt: i.alt })), link: (() => { const a = document.querySelector('#a a.rf-link'); return a && { href: a.getAttribute('href'), target: a.target, rel: a.rel, text: a.textContent.trim() }; })(), popis: (document.querySelector('#a .rf-popis') || {}).textContent, sloupcu: (() => { const g = document.querySelector('#a .rf-grid'); return g ? getComputedStyle(g).gridTemplateColumns.split(' ').length : 0; })(), preteka: document.documentElement.scrollWidth > innerWidth }));
    over(`B ${typ}: mount vrati true a zobrazi 4 REALNE fotky (vsechny se nacetly, ruzne src), ${typ === 'vestavby' ? 'z vestaveb' : 'ze stolu'}`, ok === true && d.imgs.length === 4 && d.imgs.every(i => i.w > 0) && new Set(d.imgs.map(i => i.src)).size === 4 && d.imgs.every(i => i.src.includes('/' + tag + '/')), d.imgs);
    over(`B ${typ}: odkaz na fotogalerii "${textOcek}" vede na ${hrefOcek}, otevira se v nove karte (noopener)`, d.link && d.link.href === hrefOcek && d.link.target === '_blank' && /noopener/.test(d.link.rel) && d.link.text === textOcek, d.link);
    over(`B ${typ}: 4 sloupce na pocitaci, bez vodorovneho prekroceni, popisek je`, d.sloupcu === 4 && !d.preteka && /Reálné fotografie/.test(d.popis || ''), [d.sloupcu, d.preteka, d.popis]);
    await ctx.close();
  }
  ({ page, ctx } = await strana({ sirka: 390 }));
  await page.evaluate(() => window.RealizaceFoto.mount(document.getElementById('a'), { typ: 'vestavby', seed: 'p1', eager: true }));
  await page.waitForTimeout(600);
  const mob = await page.evaluate(() => ({ sloupcu: getComputedStyle(document.querySelector('#a .rf-grid')).gridTemplateColumns.split(' ').length, preteka: document.documentElement.scrollWidth > innerWidth, odkazSirka: Math.round(document.querySelector('#a a.rf-link').getBoundingClientRect().width), okno: innerWidth }));
  over('B mobil 390 px: 2 sloupce (2 x 2 fotky), nic nepreteka, tlacitko odkazu pres sirku', mob.sloupcu === 2 && !mob.preteka && mob.odkazSirka > 300, mob);
  await ctx.close();

  // ---- C) lightbox: zvetseni, Esc, sipky se nepredavaji strance
  ({ page, ctx } = await strana());
  await page.evaluate(() => { window.__sipky = 0; document.addEventListener('keydown', e => { if (e.key === 'ArrowRight') window.__sipky++; }); return window.RealizaceFoto.mount(document.getElementById('a'), { typ: 'vestavby', seed: 'p7', eager: true }); });
  await page.waitForSelector('#a .rf-foto');
  const src0 = await page.locator('#a .rf-foto img').first().getAttribute('src');
  await page.locator('#a .rf-foto').first().click();
  let lb = await page.evaluate(() => { const l = document.querySelector('.rf-lb'); return { otevreno: !!l && l.classList.contains('rf-open'), src: l && l.querySelector('img').getAttribute('src'), cap: l && l.querySelector('figcaption').textContent }; });
  over('C1 klik na fotku otevre zvetseni (lightbox) se stejnym obrazkem a popiskem "(1 / 4)"', lb.otevreno && lb.src === src0 && /\(1 \/ 4\)/.test(lb.cap), lb);
  await page.keyboard.press('ArrowRight');
  lb = await page.evaluate(() => ({ src: document.querySelector('.rf-lb img').getAttribute('src'), cap: document.querySelector('.rf-lb figcaption').textContent, sipky: window.__sipky }));
  over('C2 sipka doprava = dalsi fotka (2 / 4) a udalost se NEPREDA strance (u online nabidky by jinak prepnula stranku)', lb.src !== src0 && /\(2 \/ 4\)/.test(lb.cap) && lb.sipky === 0, lb);
  await page.keyboard.press('Escape');
  const po = await page.evaluate(() => ({ otevreno: document.querySelector('.rf-lb').classList.contains('rf-open'), fokus: document.activeElement && document.activeElement.className }));
  over('C3 Esc zavre lightbox a fokus se vrati na miniaturu', !po.otevreno && /rf-foto/.test(po.fokus), po);
  await ctx.close();

  // ---- D) chyby a bezpecnost
  ({ page, ctx } = await strana({ galerieChyba: true }));
  let r = await page.evaluate(() => window.RealizaceFoto.mount(document.getElementById('a'), { typ: 'vestavby', seed: 1 }).then(ok => ({ ok, html: document.getElementById('a').innerHTML })));
  over('D1 API galerie vraci 500: mount vrati false a kontejner zustane prazdny (volajici blok skryje)', r.ok === false && r.html === '', r);
  await ctx.close();
  ({ page, ctx } = await strana({ upravGalerii: () => ({ images: [] }) }));
  r = await page.evaluate(() => window.RealizaceFoto.mount(document.getElementById('a'), { typ: 'stoly', seed: 1 }).then(ok => ({ ok, html: document.getElementById('a').innerHTML })));
  over('D2 prazdna galerie: mount vrati false, nic se nezobrazi', r.ok === false && r.html === '', r);
  r = await page.evaluate(() => window.RealizaceFoto.mount(document.getElementById('a'), { typ: 'neexistuje', seed: 1 }).then(ok => ok));
  over('D3 neznamy typ galerie: false (bez vyjimky)', r === false, r);
  await ctx.close();
  ({ page, ctx } = await strana({ upravGalerii: s => ({ images: s.images.slice(0, 8).map((i, k) => k === 0 ? Object.assign({}, i, { title: '<img src=x onerror="window.__xss=1">', alt_text: '"><img src=x onerror="window.__xss=1">' }) : i) }) }));
  await page.evaluate(() => window.RealizaceFoto.mount(document.getElementById('a'), { typ: 'vestavby', seed: 'p1', n: 8, eager: true }));
  await page.waitForTimeout(500);
  const xss = await page.evaluate(() => ({ x: window.__xss === 1, divImg: document.querySelectorAll('#a img').length, popisky: [...document.querySelectorAll('#a .rf-foto')].map(b => b.getAttribute('aria-label')).filter(t => /<img/.test(t)).length }));
  over('D4 popisek / alt z dat s HTML se neinterpretuje (zadny XSS, pocet img = pocet fotek)', !xss.x && xss.divImg === 8, xss);
  await ctx.close();
  // ---- D5) bezZnacky (storefronty bez znacky): fotky se znackou v nazvu souboru / titulku se nevybiraji; mountGalerie ukaze celou galerii (bez vyloucenych a bez znackovych)
  ({ page, ctx } = await strana({ upravGalerii: s => ({ images: s.images.map((i, k) => k % 2 ? i : Object.assign({}, i, { filename: 'stavebnice-do-aut-vandrawee-' + k + '.jpg' })) }) }));
  const bz = await page.evaluate(() => window.RealizaceFoto.mount(document.getElementById('a'), { typ: 'vestavby', seed: 'p1', n: 400, bezZnacky: true, eager: true }).then(() => [...document.querySelectorAll('#a .rf-foto img')].map(i => i.getAttribute('src'))));
  over('D5 bezZnacky: fotky s "vandrawee" v nazvu se nevybiraji (zbyde jen cast, zadna se znackou)', bz.length > 0 && bz.length < 139 && bz.every(s => !/vandr|logiman/i.test(s)), bz.length);
  await ctx.close();
  ({ page, ctx } = await strana());
  const gal = await page.evaluate(() => window.RealizaceFoto.mountGalerie(document.getElementById('a'), { typ: 'vestavby', bezZnacky: true }).then(ok => ({ ok, n: document.querySelectorAll('#a .rf-foto').length, ids: [...document.querySelectorAll('#a .rf-foto')].map(b => Number(b.dataset.rfId)), V: window.RealizaceFoto.VYLOUCENE.vestavby })));
  const bezZ = G.vestavby.images.filter(i => !/vandr|logiman|konfigur[aá]tor/i.test(i.filename + ' ' + (i.title || '') + ' ' + (i.alt_text || '')) && !gal.V.includes(i.id)).length;
  over('D6 mountGalerie: zobrazi VSECHNY fotky bez znacky v nazvu a bez vyloucenych (' + bezZ + '), zadnou vyloucenou', gal.ok === true && gal.n === bezZ && gal.ids.every(i => !gal.V.includes(i)), [gal.n, bezZ]);
  await page.locator('#a .rf-foto').nth(1).click();
  const lbg = await page.evaluate(() => { const l = document.querySelector('.rf-lb'); return { otevreno: l && l.classList.contains('rf-open'), cap: l && l.querySelector('figcaption').textContent }; });
  over('D6 galerie: klik na fotku otevre zvetseni "(2 / N)"', lbg.otevreno && /\(2 \/ \d+\)/.test(lbg.cap), lbg);
  await ctx.close();

  // ---- F) ROTACE PRI KAZDEM NACTENI (Robert 2026-10-08: "reloaduju F5 a nactou se stale tytez"): cital v localStorage posouva okno fotek
  {
    const ids = el => [...el.querySelectorAll('.rf-foto')].map(b => Number(b.dataset.rfId));
    const nacti = async (page, opts, seed) => page.evaluate(async ([o, sd]) => { const el = document.createElement('div'); document.body.appendChild(el); await window.RealizaceFoto.mount(el, Object.assign({ typ: 'vestavby', seed: sd }, o)); return [...el.querySelectorAll('.rf-foto')].map(b => Number(b.dataset.rfId)); }, [opts, seed]);
    const ctxF = await browser.newContext({ viewport: { width: 1280, height: 900 } });
    const sadyF = []; let citac = [];
    for (let k = 0; k < 12; k++) {
      const { page: pg } = await strana({ ctx: ctxF });
      sadyF.push(await nacti(pg, {}, 'p4499'));
      if (k === 0) { const dalsi = await nacti(pg, {}, 'p4499'); over('F1 v ramci JEDNE stranky se pri opakovanem vykresleni bloku sada NEMENI (zadne preskakovani fotek)', JSON.stringify(dalsi) === JSON.stringify(sadyF[0]), [dalsi, sadyF[0]]); }
      citac.push(await pg.evaluate(() => localStorage.getItem('rf:n:p4499')));
      await pg.close();
    }
    const dvojice = sadyF.slice(1).map((x, i) => x.filter(id => sadyF[i].includes(id)).length);
    over('F2 kazde dalsi nacteni (F5) ukaze 4 NOVE fotky: 12 po sobe jdoucich nacteni, zadne dve sousedni nemaji spolecnou fotku', sadyF.every(x => x.length === 4) && dvojice.every(n => n === 0), [sadyF, dvojice]);
    over('F3 behem 12 nacteni se zadna fotka neopakuje (okna jdou po jedne permutaci celou galerii)', new Set(sadyF.flat()).size === 48, new Set(sadyF.flat()).size);
    over('F4 citac nacteni v localStorage (rf:n:<seed>) roste o 1 pri kazdem nacteni', citac.every((v, i) => i === 0 || Number(v) === Number(citac[i - 1]) + 1), citac);
    await ctxF.close();
    ({ page, ctx } = await strana());
    const ruzne = await page.evaluate(async () => { const out = []; for (const sd of ['p4499', 'p4515', 'p4955']) { const el = document.createElement('div'); document.body.appendChild(el); await window.RealizaceFoto.mount(el, { typ: 'vestavby', seed: sd }); out.push([...el.querySelectorAll('.rf-foto')].map(b => b.dataset.rfId).join(',')); } return out; });
    over('F5 ruzne karty (ruzny seed) maji ve stejnem nacteni RUZNE sady', new Set(ruzne).size === 3, ruzne);
    const stab = await page.evaluate(async () => { const o = []; for (let i = 0; i < 2; i++) { const el = document.createElement('div'); document.body.appendChild(el); await window.RealizaceFoto.mount(el, { typ: 'vestavby', seed: 'px', stabilni: true, tyden: 3 }); o.push([...el.querySelectorAll('.rf-foto')].map(b => b.dataset.rfId).join(',')); } const el3 = document.createElement('div'); document.body.appendChild(el3); await window.RealizaceFoto.mount(el3, { typ: 'vestavby', seed: 'px', poradi: 2, tyden: 3 }); o.push([...el3.querySelectorAll('.rf-foto')].map(b => b.dataset.rfId).join(',')); return o; });
    over('F6 volba stabilni: true drzi stale stejnou sadu, poradi: 2 da pevne okno (jine nez stabilni)', stab[0] === stab[1] && stab[2] !== stab[0], stab);
    await ctx.close();
    // localStorage nedostupny (soukromy rezim / zakazano): blok se stejne vykresli (4 fotky) a nic nespadne
    const ctxN = await browser.newContext({ viewport: { width: 1280, height: 900 } });
    await ctxN.addInitScript(() => { Object.defineProperty(window, 'localStorage', { get() { throw new Error('zakazano'); } }); });
    const { page: pn } = await strana({ ctx: ctxN });
    const bez = await nacti(pn, {}, 'p4499');
    over('F7 bez localStorage (zakazano): blok se vykresli, 4 ruzne fotky, bez chyby', bez.length === 4 && new Set(bez).size === 4, bez);
    await ctxN.close();
  }

  // ---- E) vyloucene fotky (rendery, produktove snimky, fotky s textem druhe znacky, duplicity) se NIKDY nevyberou - blok slibuje "realne fotografie"
  ({ page, ctx } = await strana());
  const E = await page.evaluate(async () => {
    const V = window.RealizaceFoto.VYLOUCENE, vys = { vestavby: [], stoly: [] };
    for (const typ of ['vestavby', 'stoly']) for (let k = 1; k <= 150; k++) {
      const el = document.createElement('div'); document.body.appendChild(el);
      await window.RealizaceFoto.mount(el, { typ, seed: 'p' + k, tyden: k % 5 });
      vys[typ].push([...el.querySelectorAll('.rf-foto')].map(b => Number(b.dataset.rfId)));
    }
    return { V, vys };
  });
  const idsV = new Set(G.vestavby.images.map(i => i.id)), idsS = new Set(G.stoly.images.map(i => i.id));
  over('E1 seznam vyloucenych fotek (rendery, produktove snimky, text druhe znacky, duplicity) odpovida zive galerii: vestavby >= 15 id, vsechna existuji; stoly (render #148) existuje', E.V.vestavby.length >= 15 && E.V.vestavby.every(i => idsV.has(i)) && E.V.stoly.every(i => idsS.has(i)) && E.V.stoly.includes(148), [E.V.vestavby.filter(i => !idsV.has(i)), E.V.stoly]);
  over('E2 ve 150 blocich vestaveb (a ruznych tydnech) se NEVYSKYTNE zadna vyloucena fotka', E.vys.vestavby.every(s => s.length === 4 && s.every(i => !E.V.vestavby.includes(i))), E.vys.vestavby.find(s => s.some(i => E.V.vestavby.includes(i))));
  over('E3 ve 150 blocich stolu se NEVYSKYTNE render #148 a kazdy blok ma 4 fotky', E.vys.stoly.every(s => s.length === 4 && !s.includes(148)), E.vys.stoly.find(s => s.includes(148) || s.length !== 4));
  over('E4 vyber po vyloucenich porad pokryva galerii: 150 bloku vestaveb ukaze >= 85 % ze zbylych fotek', new Set(E.vys.vestavby.flat()).size >= 0.85 * (G.vestavby.images.length - E.V.vestavby.length), [new Set(E.vys.vestavby.flat()).size, G.vestavby.images.length - E.V.vestavby.length]);
  await ctx.close();
  over('Z bez neodchycenych JS chyb', chyby.length === 0, chyby.slice(0, 3));
  await browser.close();
  const ok = vysl.filter(Boolean).length;
  console.log(`\nVYSLEDEK realizace-foto modul: ${ok}/${vysl.length} OK`);
  process.exit(ok === vysl.length ? 0 : 1);
})().catch(e => { console.error('TEST SPADL:', e); process.exit(2); });
