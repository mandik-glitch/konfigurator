'use strict';
// Offline test stranky pripni-cokoli.html nad syntetickym GLB (kostka): texty, popisky, kroky, posuvnik, jazyky, embed, chyby.
const path = require('path'), fs = require('fs');
const { chromium } = require('/opt/konfigurator/node_modules/playwright');
const WEB = '/opt/konfigurator/webapp', NM = '/opt/konfigurator/node_modules/three/', ORIGIN = 'https://pc.test';
const GLB = process.env.GLB;
if (!GLB) { console.error('nastav GLB=<synth_demo2.glb> (viz run_all.sh)'); process.exit(2); }
const out = [];
let TEXTY_OVERRIDE = null;
const REAL_TEXTY = JSON.parse(fs.readFileSync(path.join(WEB, 'pripni-cokoli/texty.json'), 'utf8'));
const APPROVED_TEXTY = JSON.stringify(Object.assign({}, REAL_TEXTY, { _profily: Object.assign({}, REAL_TEXTY._profily, { '30x30-d8': Object.assign({}, REAL_TEXTY._profily['30x30-d8'], { zive: true }) }) }));
const UNAPPROVED_TEXTY = JSON.stringify(Object.assign({}, REAL_TEXTY, { _profily: Object.assign({}, REAL_TEXTY._profily, { '30x30-d8': Object.assign({}, REAL_TEXTY._profily['30x30-d8'], { zive: false }) }) }));   // simulace NEschvalene varianty (pravidlo 60); zivy registr je od 2026-10-04 schvaleny (Robert, Johnova v5)
const ok = (n, c, d) => { out.push(!!c); console.log((c ? 'OK   ' : 'FAIL ') + n + (d !== undefined ? '  ' + JSON.stringify(d).slice(0, 280) : '')); };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
(async () => {
  const b = await chromium.launch({ args: ['--host-resolver-rules=MAP * ~NOTFOUND', '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  const errs = [], ext = [];
  const mkctx = async (opts) => {
    const ctx = await b.newContext(Object.assign({ viewport: { width: 1000, height: 900 }, deviceScaleFactor: 1 }, opts || {}));
    await ctx.route('**/*', (route) => {
      const u = new URL(route.request().url());
      if (u.origin === 'https://cdn.jsdelivr.net') {
        const f = path.join(NM, u.pathname.replace('/npm/three@0.128.0/', ''));
        return fs.existsSync(f) ? route.fulfill({ contentType: 'application/javascript', body: fs.readFileSync(f) }) : route.fulfill({ status: 404, body: '' });
      }
      if (u.origin !== ORIGIN) { ext.push(u.href); return route.fulfill({ status: 404, body: '' }); }
      let p = u.pathname; if (p === '/') p = '/pripni-cokoli.html';
      if (p === '/pripni-cokoli/stavebnice-demo.glb') return route.fulfill({ contentType: 'model/gltf-binary', body: fs.readFileSync(GLB) });
      if (p === '/pripni-cokoli/chybi.glb' ) return route.fulfill({ status: 404, body: '' });
      if (p === '/pripni-cokoli/texty.json' && TEXTY_OVERRIDE) return route.fulfill({ contentType: 'application/json', body: TEXTY_OVERRIDE });   // simulace schvaleneho registru
      const f = path.join(WEB, p);
      if (!f.startsWith(WEB) || !fs.existsSync(f) || fs.statSync(f).isDirectory()) return route.fulfill({ status: 404, body: '' });
      const ct = { '.js': 'application/javascript', '.css': 'text/css', '.html': 'text/html; charset=utf-8', '.json': 'application/json', '.glb': 'model/gltf-binary', '.svg': 'image/svg+xml' }[path.extname(f)] || 'application/octet-stream';
      return route.fulfill({ contentType: ct, body: fs.readFileSync(f) });
    });
    return ctx;
  };
  const open = async (ctx, query) => {
    const page = await ctx.newPage();
    page.on('pageerror', (e) => errs.push(String(e)));
    await page.goto(ORIGIN + '/pripni-cokoli.html' + (query || ''));
    await page.waitForSelector('body.ready, body.failed', { timeout: 30000 }).catch(() => {});
    await sleep(800);
    return page;
  };
  let ctx = await mkctx();
  let page = await open(ctx, '?lang=cs');
  let r = await page.evaluate(() => ({ ready: document.body.classList.contains('ready'), h1: document.getElementById('pcH1').textContent, title: document.title, lang: document.documentElement.lang,
    chips: [...document.querySelectorAll('#pcSteps .chip')].map((c) => c.textContent.trim()), cap: document.getElementById('pcCap').textContent, scrubDis: document.getElementById('pcScrub').disabled,
    play: document.getElementById('pcPlay').getAttribute('aria-label') }));
  ok('stranka se nacetla (body.ready), h1 "Připni cokoli", lang cs', r.ready && r.h1 === 'Připni cokoli' && r.lang === 'cs', r);
  ok('kroky: 3 tlacitka (Profil, Kámen, Hotovo) s cisly', r.chips.length === 3 && /1\s+Profil/.test(r.chips[0]) && /2\s+Kámen/.test(r.chips[1]) && /3\s+Hotovo/.test(r.chips[2]), r.chips);
  ok('titulek stranky z texty.json', /Připni cokoli/.test(r.title));
  // hraje samo, popisek se meni (cue intro 0-2 s -> text; kamen 2-4,5)
  const caps = new Set();
  for (let i = 0; i < 80; i++) {   // pod zatizenim stroje bezi prehravani pomalu: cekat na podminku, ne na pevny cas
    caps.add(await page.evaluate(() => document.getElementById('pcCap').textContent)); await sleep(500);
    if ([...caps].some((c) => /Hliníkový profil 40×40/.test(c)) && [...caps].some((c) => /Kámen se zasune/.test(c))) break;
  }
  ok('popisek se behem prehravani meni a pouziva ceske texty (intro + kamen)', [...caps].some((c) => /Hliníkový profil 40×40/.test(c)) && [...caps].some((c) => /Kámen se zasune/.test(c)), [...caps]);
  // pauza
  await page.click('#pcPlay'); await sleep(300);
  const t0 = await page.evaluate(() => document.getElementById('pcScrub').value); await sleep(900);
  const t1 = await page.evaluate(() => document.getElementById('pcScrub').value);
  ok('tlacitko pauza zastavi cas (posuvnik stoji), ikona/aria = Prehrat', t0 === t1 && (await page.getAttribute('#pcPlay', 'aria-label')) === 'Přehrát', [t0, t1]);
  // posuvnik: seek na 50 % = 3 s
  await page.evaluate(() => { const s = document.getElementById('pcScrub'); s.value = '500'; s.dispatchEvent(new Event('input', { bubbles: true })); });
  await sleep(400);
  const capSeek = await page.evaluate(() => document.getElementById('pcCap').textContent);
  ok('posuvnik na 50 % (3 s): popisek cue "kamen" a krok 2 zvyrazneny', /Kámen se zasune/.test(capSeek) && (await page.evaluate(() => document.querySelectorAll('#pcSteps .chip.on')[0].textContent)).includes('Kámen'), capSeek);
  // klik na krok 2 (Kamen): skoci na zacatek kroku (t0 = 2 s => ~333/1000) a animace JEDE DAL (nezastavuje se na konci kroku)
  await page.click('#pcSteps .chip:nth-child(2)'); await sleep(500);
  const sv0 = await page.evaluate(() => ({ v: +document.getElementById('pcScrub').value, label: document.getElementById('pcPlay').getAttribute('aria-label') }));
  ok('klik na krok "Kámen": skoci na zacatek kroku (~333/1000) a prehravani bezi', sv0.v >= 320 && sv0.v <= 520 && sv0.label === 'Pozastavit', sv0);
  let sv1 = sv0;
  for (let i = 0; i < 80; i++) { await sleep(300); sv1 = await page.evaluate(() => ({ v: +document.getElementById('pcScrub').value, label: document.getElementById('pcPlay').getAttribute('aria-label') })); if (sv1.v > 700 || sv1.v < sv0.v - 50) break; }
  ok('po konci kroku se NEZASTAVI: pokracuje dal (dalsi krok nebo smycka), tlacitko stale Pozastavit', sv1.label === 'Pozastavit' && (sv1.v > 700 || sv1.v < sv0.v), [sv0.v, sv1.v, sv1.label]);
  // klepnuti na dil ve 3D: zamerne nic nedela (neskace a nezastavuje); tazeni taky ne
  const hit = await page.evaluate(() => { const hook = window.__v3d; const p = hook.screenOf ? hook.screenOf('box') : null; return p; });
  ok('ladici hook vraci polohu dilu na obrazovce (priprava pro klepnuti)', !!hit, hit);
  if (hit) {
    const box = await page.locator('#pcViewer canvas').boundingBox();
    const before = await page.evaluate(() => +document.getElementById('pcScrub').value);
    await page.mouse.click(box.x + hit.x, box.y + hit.y); await sleep(400);
    const after = await page.evaluate(() => ({ v: +document.getElementById('pcScrub').value, label: document.getElementById('pcPlay').getAttribute('aria-label') }));
    const dv = ((after.v - before) + 1000) % 1000;     // pri nepretrzitem prehravani se cas jen posunul dopredu (max pul okruhu)
    ok('klepnuti na dil ve 3D NEPRESKOCI a NEZASTAVI animaci (cas dal roste, tlacitko Pozastavit)', after.label === 'Pozastavit' && dv < 500, { before, after });
    await page.mouse.move(box.x + hit.x, box.y + hit.y); await page.mouse.down(); await page.mouse.move(box.x + hit.x + 60, box.y + hit.y + 20, { steps: 6 }); await page.mouse.up(); await sleep(300);
    const afterDrag = await page.evaluate(() => document.getElementById('pcPlay').getAttribute('aria-label'));
    ok('tazeni (otoceni modelu) animaci nezastavi', afterDrag === 'Pozastavit', afterDrag);
  }
  // restart
  await page.click('#pcRestart'); await sleep(400);
  const rs = await page.evaluate(() => ({ v: +document.getElementById('pcScrub').value, label: document.getElementById('pcPlay').getAttribute('aria-label') }));
  ok('Od zacatku: cas se vraci na zacatek a prehravani bezi', rs.v < 150 && rs.label === 'Pozastavit', rs);
  // schemata dalsich profilu (40x40/10 mm a 30x30/8 mm): blok viditelny, obe SVG se nactou, texty cesky
  await page.evaluate(() => document.getElementById('pcOther').scrollIntoView());
  await page.waitForFunction(() => ['pcImg40', 'pcImg30'].every((i) => { const e = document.getElementById(i); return e && e.complete && e.naturalWidth > 0; }), null, { timeout: 15000 }).catch(() => {});
  const sch = await page.evaluate(() => ({ vis: getComputedStyle(document.getElementById('pcOther')).display !== 'none', h: document.getElementById('pcOtherH').textContent,
    t30: document.getElementById('pcF30t').textContent, t40: document.getElementById('pcF40t').textContent,
    ok40: document.getElementById('pcImg40').naturalWidth > 0, ok30: document.getElementById('pcImg30').naturalWidth > 0, alt30: document.getElementById('pcImg30').alt }));
  ok('schemata profilu: blok "Stejný princip platí pro další profily" viditelný, oba obrázky se načetly, popisky 40×40/10 mm a 30×30/8 mm', sch.vis && /Stejný princip/.test(sch.h) && /30×30, drážka 8 mm/.test(sch.t30) && /40×40, drážka 10 mm/.test(sch.t40) && sch.ok40 && sch.ok30 && /30×30/.test(sch.alt30), sch);
  const svgTxt = await page.evaluate(async () => ({ a: await (await fetch('/pripni-cokoli/schema-30x30-d8.svg')).text(), b: await (await fetch('/pripni-cokoli/schema-40x40-d10.svg')).text() }));
  ok('SVG schémata: platný XML, obsahují obrys profilu a kóty (30 a 8,2; 40 a 10,2), bez externích odkazů', /^<svg [^>]*viewBox/.test(svgTxt.a) && /<path class="p" d="M/.test(svgTxt.a) && />30</.test(svgTxt.a) && />8,2</.test(svgTxt.a) && />40</.test(svgTxt.b) && />10,2</.test(svgTxt.b) && !/href|http:\/\/(?!www\.w3\.org)/.test(svgTxt.a + svgTxt.b), [svgTxt.a.length, svgTxt.b.length]);
  await page.close();
  // jazyk en, embed, parametry
  page = await open(ctx, '?lang=en&embed=1&bg=101820&autoplay=0');
  r = await page.evaluate(() => ({ h1: document.getElementById('pcH1').textContent, headVisible: getComputedStyle(document.querySelector('.pc-head')).display !== 'none', otherVisible: getComputedStyle(document.getElementById('pcOther')).display !== 'none', otherH: document.getElementById('pcOtherH').textContent, footVisible: getComputedStyle(document.querySelector('.pc-foot')).display !== 'none',
    bg: getComputedStyle(document.documentElement).getPropertyValue('--pc-bg').trim(), play: document.getElementById('pcPlay').getAttribute('aria-label'), chips: [...document.querySelectorAll('#pcSteps .chip')].map((c) => c.textContent.trim()), lang: document.documentElement.lang }));
  ok('lang=en: anglicke texty (Attach anything, Play, Slot nut), embed skryje hlavicku a paticku, bg z parametru, autoplay=0 -> Prehrat', r.h1 === 'Attach anything' && !r.headVisible && !r.footVisible && r.bg === '#101820' && r.play === 'Play' && /Slot nut/.test(r.chips[1]) && r.lang === 'en' && !r.otherVisible && /The same principle/.test(r.otherH), r);
  await page.close();
  // varianta profilu 30x30: Johnova prace je do schvaleni Robertem na zive strance VYPNUTA (registr _profily['30x30-d8'].zive === false, pravidlo 60), ukaze se jen v nahledu (?nahled=<id>)
  {
    const mkp = async (query, override) => {
      const rq = []; TEXTY_OVERRIDE = override || null;
      const pg = await ctx.newPage(); pg.on('pageerror', (e) => errs.push(String(e))); pg.on('request', (r) => rq.push(new URL(r.url()).pathname));
      await pg.goto(ORIGIN + '/pripni-cokoli.html?autoplay=0&t=1&' + query);
      await pg.waitForSelector('body.ready, body.failed', { timeout: 30000 }).catch(() => {}); await sleep(700);
      const st = await pg.evaluate(() => ({ ready: document.body.classList.contains('ready'), failed: document.body.classList.contains('failed'), cap: document.getElementById('pcCap').textContent, chips: document.querySelectorAll('#pcSteps .chip').length,
        ctl: getComputedStyle(document.querySelector('.pc-ctl')).display, banner: (document.querySelector('.pc-preview') || {}).textContent || null, title: document.title }));
      TEXTY_OVERRIDE = null; await pg.close();
      return { rq, st, glbs: rq.filter((p) => /\.glb$/.test(p)) };
    };
    let r = await mkp('lang=en&profil=30', UNAPPROVED_TEXTY);
    ok('?profil=30 s NESCHVALENOU variantou (zive:false v simulovanem registru): nic se neukaze (model se nenacita), hlaska "animation ... being prepared", ovladani skryte, zadne kroky', r.st.failed && !r.st.ready && /being prepared/.test(r.st.cap) && r.glbs.length === 0 && r.st.chips === 0 && r.st.ctl === 'none', r);
    for (const q of ['Object_7', '1.1.08.030030.03']) {
      r = await mkp('lang=cs&profil=' + encodeURIComponent(q), UNAPPROVED_TEXTY);
      ok('?profil=' + q + ' s neschvalenou variantou: totez (30x30 je do schvaleni vypnuto), zadny model, hlaska cesky', r.st.failed && /připravuje/.test(r.st.cap) && r.glbs.length === 0, r);
    }
    r = await mkp('lang=cs&profil=45');
    ok('?profil=45 (neznamy): vychozi model 40x40', r.st.ready && r.glbs.some((p) => /\/stavebnice-demo\.glb$/.test(p)) && !r.glbs.some((p) => /30x30/.test(p)), r.glbs);
    r = await mkp('lang=cs&profil=30&nahled=v2');
    ok('?profil=30&nahled=v2: model z nahled/v2/, oranzove upozorneni "NAHLED v2 ... ceka na schvaleni Robertem", titulek s NAHLED, uvodni veta o 30x30, zivy model se nenacita', r.st.ready && r.glbs.some((p) => /\/pripni-cokoli\/nahled\/v2\/stavebnice-demo-30x30\.glb$/.test(p)) && !r.glbs.some((p) => /^\/pripni-cokoli\/stavebnice-demo-30x30\.glb$/.test(p))
      && /NÁHLED v2/.test(r.st.banner || '') && /schválení Robertem/.test(r.st.banner || '') && /^NÁHLED/.test(r.st.title) && /30×30/.test(r.st.cap) && r.st.chips >= 3, r);
    r = await mkp('lang=cs&profil=30&nahled=..%2Fx', UNAPPROVED_TEXTY);
    ok('?nahled=../x (neplatne id) se ignoruje: jako zive s neschvalenou variantou (nic se neukaze), zadne upozorneni', r.st.failed && r.glbs.length === 0 && !r.st.banner, r);
    r = await mkp('lang=en&profil=30');
    ok('ZIVY registr je schvaleny (Robert 2026-10-04, Johnova v5): ?profil=30 se ukaze: nacte se zivy model 30x30 a uvodni veta o profilu 30×30 (zapnuti je jeden krok v texty.json)', r.st.ready && r.glbs.some((p) => /^\/pripni-cokoli\/stavebnice-demo-30x30\.glb$/.test(p)) && /30×30/.test(r.st.cap) && r.st.chips >= 3, r);
  }
  // chyba nacteni (neexistujici model)
  page = await open(ctx, '?lang=cs&model=chybi.glb');
  r = await page.evaluate(() => ({ failed: document.body.classList.contains('failed'), cap: document.getElementById('pcCap').textContent, ctl: getComputedStyle(document.querySelector('.pc-ctl')).display }));
  ok('chybejici model: stranka hlasi chybu textem a skryje ovladani', r.failed && r.cap.length > 5 && r.ctl === 'none', r);
  await page.close();
  // neplatny parametr model (mimo /pripni-cokoli/) se ignoruje
  page = await open(ctx, '?model=../../etc/passwd');
  r = await page.evaluate(() => ({ ready: document.body.classList.contains('ready') }));
  ok('parametr model s cestou mimo adresar se ignoruje (nacte se vychozi model)', r.ready, r);
  await page.close();
  await ctx.close();
  // mobil 390 px + omezit animace
  ctx = await mkctx({ viewport: { width: 390, height: 800 }, reducedMotion: 'reduce', hasTouch: true, isMobile: true });
  page = await open(ctx, '?lang=sk');
  r = await page.evaluate(async () => { const a = document.getElementById('pcScrub').value; await new Promise((x) => setTimeout(x, 1200)); const bV = document.getElementById('pcScrub').value;
    return { sw: document.documentElement.scrollWidth, iw: innerWidth, h1: document.getElementById('pcH1').textContent, a, b: bV, label: document.getElementById('pcPlay').getAttribute('aria-label'), viewerH: document.getElementById('pcViewer').getBoundingClientRect().height }; });
  ok('mobil 390 px, omezit animace: bez horizontalniho scrollu, slovensky nadpis, start pozastaveny (cas stoji, tlacitko Prehrat)', r.sw <= r.iw && r.h1 === 'Pripni čokoľvek' && r.a === r.b && r.label === 'Prehrať', r);
  
  await ctx.close();
  ok('zadny pozadavek mimo mock (jen three z CDN)', ext.length === 0, ext);
  ok('bez neodchycenych chyb stranky', errs.length === 0, errs.slice(0, 3));
  await b.close();
  process.exit(out.every(Boolean) ? 0 : 1);
})().catch((e) => { console.error('CHYBA', e); process.exit(2); });
