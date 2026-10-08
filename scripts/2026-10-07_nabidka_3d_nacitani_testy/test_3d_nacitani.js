// HUD indikator "Nacita se 3D model" v okne 3D sceny online nabidky (bot8, 2026-10-07; Robert: "v online nabidce Vandr sestavy, v okne pro 3D scenu se zobrazi 2d pohledy z vandru puvodni
// nez se nacte 3D model, ale je potreba tam pridat jeste neco jako Nacita se.. s nejakym zivym efektem hud stylu"). SKUTECNA stranka webapp/nabidka-online.html v Chromiu proti falesnemu
// serveru (harness testu rucnich polozek), 3D prohlizec V3D je v testu NAHRAZEN rizenou atrapou (mount vrati promise `ready`, kterou test dokonci / odmitne), model se stahuje po castech
// s Content-Length (postupne procenta). Hlida: indikator se objevi AZ s nactenim 3D slidu a prekryva okno nad 2D pohledy; faze STAHUJI MODEL s rostoucimi procenty -> SESTAVUJI SCENU;
// animace skutecne bezi (poloha skenovaci cary, otaceni kruhu se meni); zmizi po ready i po chybe (2D pohledy zustanou); stahovani modelu selze -> zmizi; scrollHeight slidu se behem
// animace nemeni (past s transformem, viz .cover::after); mobil bez horizontalniho posunu; tisk a prefers-reduced-motion; vetev "nabidka z konfigurace"; (CDN=1) skutecny V3D.
// Spusteni: node test_3d_nacitani.js     Kandidat stranky: NABIDKA_HTML=/cesta/nabidka-online.html node ...     Skutecny V3D + three.js z CDN: CDN=1 node ...
const fs = require('fs');
const path = require('path');
const { otevriNabidku, vzorovaNabidka } = require('../2026-10-06_nabidka_montaz_polozky_testy/harness');
const vysl = [];
const over = (nazev, podminka, detail) => { vysl.push(!!podminka); console.log((podminka ? 'OK   ' : 'FAIL ') + nazev + (podminka ? '' : '  -> ' + JSON.stringify(detail).slice(0, 400))); };
const MODEL = '/api/public/offers/TESTTOKEN/model';

// minimalni platny GLB s popisem v3d (scenes[0].extras.v3d) - stranka podle toho vybere sdileny prohlizec V3D; JSON chunk doplneny mezerami na `velikost` bajtu (kvuli procentum)
function glb(velikost) {
  const j = JSON.stringify({ asset: { version: '2.0' }, scene: 0, scenes: [{ nodes: [], extras: { v3d: { x: 1 } } }], nodes: [] });
  let jb = Buffer.from(j);
  const cil = Math.max(jb.length, (velikost || 0) - 20);
  jb = Buffer.concat([jb, Buffer.alloc((((cil + 3) >> 2) << 2) - jb.length, 0x20)]);
  const h = Buffer.alloc(20); h.write('glTF', 0); h.writeUInt32LE(2, 4); h.writeUInt32LE(20 + jb.length, 8); h.writeUInt32LE(jb.length, 12); h.write('JSON', 16);
  return Buffer.concat([h, jb]);
}
const STUB = () => {
  window.__v3d = { calls: [] };
  window.V3D = { deps: [], mount(el, o) { const c = { o, el }; c.ready = new Promise((res, rej) => { c.res = res; c.rej = rej; }); window.__v3d.calls.push(c); return { ready: c.ready, dispose() {} }; } };
  const orig = window.fetch.bind(window);
  window.fetch = function (url, opts) {
    if (String(url).endsWith('/model') && window.__model) {          // pomale stahovani po castech s Content-Length (rizeno z testu)
      const buf = window.__model.buf, n = window.__model.kousky, prodleva = window.__model.prodleva;
      let i = 0;
      const stream = new ReadableStream({ async pull(ctrl) { if (i >= n) { ctrl.close(); return; } await new Promise(r => setTimeout(r, prodleva)); ctrl.enqueue(buf.slice(Math.floor(buf.length * i / n), Math.floor(buf.length * (i + 1) / n))); i++; } });
      return Promise.resolve(new Response(stream, { status: 200, headers: { 'Content-Type': 'model/gltf-binary', 'Content-Length': String(buf.length) } }));
    }
    return orig(url, opts);
  };
};
const trasy = (statusModelu) => async (route, { p }) => {
  if (p === '/api/public/offers/TESTTOKEN/model') { if (statusModelu === 200) await route.fulfill({ status: 200, contentType: 'model/gltf-binary', body: glb(2000) }); else await route.fulfill({ status: statusModelu, body: '' }); return true; }
  return false;
};
const nabidka = (upr) => vzorovaNabidka(d => { d.order_prefs = null; d.has_3d_model = true; d.model_url = MODEL; d.source = null; if (upr) upr(d); });
async function model(page, kousky = 8, prodleva = 160, velikost = 600000) {
  await page.evaluate(({ b64, kousky, prodleva }) => { window.__model = { buf: Uint8Array.from(atob(b64), c => c.charCodeAt(0)), kousky, prodleva }; }, { b64: glb(velikost).toString('base64'), kousky, prodleva });
}
async function na3D(page) {
  for (let i = 0; i < 14; i++) {
    if (await page.evaluate(() => !!document.querySelector('.slide.active #viewer3dFallback'))) return;
    await page.click('#btnNext');
    await page.waitForTimeout(150);
  }
  throw new Error('slide s 3D oknem nenalezen');
}
const stavNacitani = page => page.evaluate(() => {
  const el = document.getElementById('viewer3dLoading');
  if (!el) return null;
  const r = el.getBoundingClientRect(), w = el.parentElement.getBoundingClientRect();
  const cs = s => { const e = el.querySelector(s); return e ? getComputedStyle(e) : null; };
  return { show: el.classList.contains('show'), zobrazeno: getComputedStyle(el).display !== 'none' && getComputedStyle(el).opacity !== '0', hostTrida: el.parentElement.className, hostMaFallback: !!el.parentElement.querySelector('#viewer3dFallback'),
    shoda: Math.abs(r.left - w.left) < 2 && Math.abs(r.top - w.top) < 2 && Math.abs(r.width - w.width) < 2 && Math.abs(r.height - w.height) < 2,
    nadpis: el.querySelector('.v3dn-nadpis').textContent, uppercase: cs('.v3dn-nadpis').textTransform, faze: el.querySelector('.v3dn-faze').textContent, pct: el.querySelector('.v3dn-pct').textContent,
    urcita: el.querySelector('.v3dn-lista').classList.contains('urcita'), p: el.querySelector('.v3dn-lista').style.getPropertyValue('--p'), bodyTrida: document.body.classList.contains('v3d-nacita-aktivni'),
    role: el.getAttribute('role'), scanPoz: cs('.v3dn-scan').backgroundPositionY, kruh: cs('.v3dn-k1').transform, animKruh: cs('.v3dn-k1').animationName, animScan: cs('.v3dn-scan').animationName,
    boxRight: el.querySelector('.v3dn-box').getBoundingClientRect().right, boxLeft: el.querySelector('.v3dn-box').getBoundingClientRect().left, wRight: w.right, wLeft: w.left, display: getComputedStyle(el).display };
});
const fallbackViditelny = page => page.evaluate(() => { const f = document.getElementById('viewer3dFallback'); return !!f && getComputedStyle(f).display !== 'none'; });

(async () => {
  // ---------------- A) Vandr vetev (GLB s v3d) - rizena atrapa V3D
  let { browser, page, chyby } = await otevriNabidku({ nabidka: nabidka(), trasy: trasy(200), initScript: STUB });
  over('N0 dokud zakaznik neotevre 3D slide, indikator se neukazuje (nic se nenacita)', !(await page.evaluate(() => { const e = document.getElementById('viewer3dLoading'); return !!e && e.classList.contains('show'); })), null);
  await model(page, 8, 220);
  await na3D(page);
  await page.waitForTimeout(250);
  const s1 = await stavNacitani(page);
  over('N1 po otevreni 3D slidu se ukaze HUD indikator "Nacita se 3D model" PREKRYVAJICI okno (stejny obdelnik jako okno), 2D pohledy pod nim zustavaji', s1 && s1.show && s1.zobrazeno && s1.hostMaFallback && /v3d-wrap/.test(s1.hostTrida) && s1.shoda && /Načítá se 3D model/.test(s1.nadpis) && s1.uppercase === 'uppercase' && s1.role === 'status' && (await fallbackViditelny(page)), s1);
  // procenta a faze behem stahovani
  const vzorky = [];
  for (let i = 0; i < 14; i++) { vzorky.push(await page.evaluate(() => { const e = document.getElementById('viewer3dLoading'); return e ? { faze: e.querySelector('.v3dn-faze').textContent, pct: e.querySelector('.v3dn-pct').textContent, urcita: e.querySelector('.v3dn-lista').classList.contains('urcita') } : null; })); await page.waitForTimeout(90); }
  const pcts = vzorky.filter(v => v && /^\d+ %$/.test(v.pct)).map(v => parseInt(v.pct, 10));
  over('N2 faze "Stahuji model" ukazuje ROSTOUCI procenta (aspon 3 ruzne hodnoty, neklesaji, pod 100) a linka je v urcitem rezimu', pcts.length >= 3 && new Set(pcts).size >= 3 && pcts.every((v, i) => i === 0 || v >= pcts[i - 1]) && Math.max(...pcts) < 100 && vzorky.some(v => v && v.urcita && /Stahuji model/i.test(v.faze)), { pcts, vzorky: vzorky.slice(0, 4) });
  // zivy efekt: poloha skenovaci cary a otoceni kruhu se meni v case
  const a1 = await stavNacitani(page); await page.waitForTimeout(500); const a2 = await stavNacitani(page); await page.waitForTimeout(350); const a3 = await stavNacitani(page);
  over('N3 efekt je ZIVY: animace bezi (scan + kruh) a poloha skenovaci cary i otoceni kruhu se v case meni', a1.animScan === 'v3dnScan' && a1.animKruh === 'v3dnRot' && new Set([a1.scanPoz, a2.scanPoz, a3.scanPoz]).size >= 2 && new Set([a1.kruh, a2.kruh, a3.kruh]).size >= 2, { scan: [a1.scanPoz, a2.scanPoz, a3.scanPoz], kruh: [a1.kruh, a2.kruh, a3.kruh] });
  // po stazeni: faze "Sestavuji scenu", V3D.mount s hotovym arrayBuffer
  await page.waitForFunction(() => window.__v3d && window.__v3d.calls.length === 1, null, { timeout: 15000 });
  const s4 = await stavNacitani(page);
  const mount = await page.evaluate(() => ({ n: window.__v3d.calls.length, buf: window.__v3d.calls[0].o.arrayBuffer instanceof ArrayBuffer, delka: window.__v3d.calls[0].o.arrayBuffer.byteLength, disp: getComputedStyle(document.getElementById('viewer3dContainer')).display, fallback: getComputedStyle(document.getElementById('viewer3dFallback')).display }));
  over('N4 po stazeni: faze "Sestavuji scenu" (bez procent, neurcita linka), indikator STALE bezi (zmizi az s hotovym modelem), V3D.mount dostal cely model, 3D kontejner je odkryty', s4.show && /Sestavuji scénu/i.test(s4.faze) && s4.pct === '' && !s4.urcita && mount.n === 1 && mount.buf && mount.delka === 600000 && mount.disp === 'block' && mount.fallback === 'none', { s4: { faze: s4.faze, pct: s4.pct, urcita: s4.urcita }, mount });
  // past scrollHeight: behem animace se vyska rolovatelne stranky nesmi menit
  const vyska = []; for (let i = 0; i < 16; i++) { vyska.push(await page.evaluate(() => document.querySelector('.slide.active').scrollHeight)); await page.waitForTimeout(180); }
  over('N5 scrollHeight slidu je behem animace STALY (zadne prodluzovani rolovani zivym efektem)', Math.max(...vyska) - Math.min(...vyska) <= 1, { min: Math.min(...vyska), max: Math.max(...vyska) });
  // tisk + reduced motion (na zive strance indikatoru)
  await page.emulateMedia({ media: 'print' });
  const tisk = await page.evaluate(() => getComputedStyle(document.getElementById('viewer3dLoading')).display);
  await page.emulateMedia({ media: 'screen', reducedMotion: 'reduce' });
  const redukce = await page.evaluate(() => ({ kruh: getComputedStyle(document.querySelector('#viewer3dLoading .v3dn-k1')).animationName, scan: getComputedStyle(document.querySelector('#viewer3dLoading .v3dn-scan')).animationName }));
  await page.emulateMedia({ reducedMotion: 'no-preference' });
  over('N6 v tisku se indikator neukazuje; pri prefers-reduced-motion se animace vypnou', tisk === 'none' && redukce.kruh === 'none' && redukce.scan === 'none', { tisk, redukce });
  // hotovo
  await page.evaluate(() => window.__v3d.calls[0].res());
  await page.waitForTimeout(600);
  const s6 = await stavNacitani(page);
  over('N7 po dokonceni modelu (V3D ready) indikator zmizi (skryty, bez tridy show, bez tridy na body); 3D okno zustane', s6 && !s6.show && s6.display === 'none' && !s6.bodyTrida && (await page.evaluate(() => getComputedStyle(document.getElementById('viewer3dContainer')).display)) === 'block', s6);
  over('N8 bez chyb ve strance (vetev Vandr)', chyby.length === 0, chyby.slice(0, 3));
  await browser.close();

  // ---------------- B) V3D ohlasi chybu (onError): indikator zmizi, 2D pohledy zustanou
  ({ browser, page, chyby } = await otevriNabidku({ nabidka: nabidka(), trasy: trasy(200), initScript: STUB }));
  await model(page, 3, 40, 3000); await na3D(page);
  await page.waitForFunction(() => window.__v3d.calls.length === 1, null, { timeout: 15000 });
  await page.evaluate(() => window.__v3d.calls[0].o.onError(new Error('WebGL')));
  await page.waitForTimeout(600);
  const sb = await stavNacitani(page);
  over('N9 chyba prohlizece (onError): indikator zmizi a zustanou puvodni 2D pohledy (fallback viditelny, 3D kontejner skryty)', sb && !sb.show && !sb.bodyTrida && (await fallbackViditelny(page)) && (await page.evaluate(() => getComputedStyle(document.getElementById('viewer3dContainer')).display)) === 'none', sb);
  await browser.close();

  // ---------------- C) promise ready se odmitne: totez
  ({ browser, page, chyby } = await otevriNabidku({ nabidka: nabidka(), trasy: trasy(200), initScript: STUB }));
  await model(page, 3, 40, 3000); await na3D(page);
  await page.waitForFunction(() => window.__v3d.calls.length === 1, null, { timeout: 15000 });
  await page.evaluate(() => window.__v3d.calls[0].rej(new Error('parse')));
  await page.waitForTimeout(600);
  const sc = await stavNacitani(page);
  over('N10 model se nepodari sestavit (ready odmitnuto): indikator zmizi, 2D pohledy zustanou, zadna chyba ve strance', sc && !sc.show && (await fallbackViditelny(page)) && chyby.length === 0, { sc, chyby: chyby.slice(0, 2) });
  await browser.close();

  // ---------------- D) stazeni modelu selze (404) -> klasicka vetev, three.js z CDN neni (test bez site) -> tichy navrat, indikator zmizi
  ({ browser, page, chyby } = await otevriNabidku({ nabidka: nabidka(), trasy: trasy(404), initScript: STUB }));
  await na3D(page);
  await page.waitForTimeout(1500);
  const sd = await stavNacitani(page);
  over('N11 model nejde stahnout / zadny prohlizec: indikator zmizi (ne nekonecne "nacita se"), 2D pohledy zustanou, bez chyb ve strance', sd && !sd.show && !sd.bodyTrida && (await fallbackViditelny(page)) && chyby.length === 0, { sd, chyby: chyby.slice(0, 2) });
  await browser.close();

  // ---------------- E) mobil 390 px: box se vejde, stranka se neposouva do strany
  ({ browser, page, chyby } = await otevriNabidku({ width: 390, height: 844, mobil: true, nabidka: nabidka(), trasy: trasy(200), initScript: STUB }));
  await model(page, 8, 300, 600000); await na3D(page);
  await page.waitForTimeout(500);
  const sm = await stavNacitani(page);
  const pret = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1);
  over('N12 uzka obrazovka (390 px): indikator je videt, box je uvnitr okna a stranka se neposouva do strany', sm && sm.show && sm.boxLeft >= sm.wLeft - 1 && sm.boxRight <= sm.wRight + 1 && !pret, { sm: { boxLeft: sm.boxLeft, boxRight: sm.boxRight, wLeft: sm.wLeft, wRight: sm.wRight }, pret });
  const polohaBoxu = () => page.evaluate(() => { const r = document.querySelector('#viewer3dLoading .v3dn-box').getBoundingClientRect(); return { stred: Math.round(r.top + r.height / 2), vh: innerHeight }; });
  const p0 = await polohaBoxu();
  await page.evaluate(() => { const s = document.querySelector('.slide.active'); s.scrollTop = 350; });
  await page.waitForTimeout(200);
  const p1 = await polohaBoxu();
  over('N12b uzka obrazovka: HUD box je hned videt uprostred obrazovky a pri rolovani vysokeho okna se lepi k obrazovce (neutece pod okraj)', p0.stred > 40 && p0.stred < p0.vh - 40 && p1.stred > 40 && p1.stred < p1.vh - 40, { p0, p1 });
  over('N12c nadpis "Otocite tazenim mysi" je behem nacitani skryty (nema smysl pro 2D pohled)', await page.evaluate(() => getComputedStyle(document.getElementById('viewer3dHint')).visibility) === 'hidden', null);
  await browser.close();

  // ---------------- F) nabidka z konfigurace sestavy: stejny indikator, konci s ready
  ({ browser, page, chyby } = await otevriNabidku({ nabidka: nabidka(d => { d.source = 'configurator'; d.configuration = { kod: 'TEST-1', souhrn: [], bom: [], pocet_spoju: 0, vykresy: false }; }), trasy: trasy(200), initScript: STUB }));
  try {
    await na3D(page);
    await page.waitForFunction(() => window.__v3d.calls.length === 1, null, { timeout: 15000 });
    const sf1 = await stavNacitani(page);
    await page.evaluate(() => window.__v3d.calls[0].res());
    await page.waitForTimeout(600);
    const sf2 = await stavNacitani(page);
    over('N13 nabidka z konfigurace: indikator bezi (faze "Sestavuji scenu") a po ready zmizi', sf1 && sf1.show && /Sestavuji scénu/i.test(sf1.faze) && sf2 && !sf2.show && chyby.length === 0, { sf1: sf1 && sf1.faze, sf2: sf2 && sf2.show, chyby: chyby.slice(0, 2) });
  } catch (e) { over('N13 nabidka z konfigurace: indikator bezi a po ready zmizi', false, e.message); }
  await browser.close();

  // ---------------- G) skutecny V3D + three.js z CDN (jen CDN=1)
  if (process.env.CDN) {
    const gl = fs.readFileSync(path.join(__dirname, '../../webapp/katalog/vandr/v3d_nahled/4910.glb'));
    const trasyReal = async (route, { p }) => { if (p === '/api/public/offers/TESTTOKEN/model') { await route.fulfill({ status: 200, contentType: 'model/gltf-binary', body: gl, headers: { 'Content-Length': String(gl.length) } }); return true; } return false; };
    ({ browser, page, chyby } = await otevriNabidku({ nabidka: nabidka(), trasy: trasyReal, cdn: true }));
    await na3D(page);
    await page.waitForTimeout(400);
    const r1 = await stavNacitani(page);
    await page.waitForFunction(() => { const e = document.getElementById('viewer3dLoading'); return e && !e.classList.contains('show'); }, null, { timeout: 90000 }).catch(() => {});
    const r2 = await stavNacitani(page);
    const cv = await page.evaluate(() => { const c = document.querySelector('#viewer3dContainer canvas'); return { canvas: !!c, w: c && c.clientWidth, h: c && c.clientHeight }; });
    over('N14 skutecny V3D: indikator se ukaze a po nacteni modelu zmizi, 3D platno ma nenulovou velikost', r1 && r1.show && r2 && !r2.show && cv.canvas && cv.w > 100 && cv.h > 100, { r1: r1 && r1.show, r2: r2 && r2.show, cv });
    if (process.env.SNIMKY) { fs.mkdirSync(process.env.SNIMKY, { recursive: true }); }
    await browser.close();
  }

  const ok = vysl.filter(Boolean).length;
  console.log(`\nVYSLEDEK indikator nacitani 3D v online nabidce: ${ok}/${vysl.length} OK`);
  process.exit(ok === vysl.length ? 0 : 1);
})().catch(e => { console.error('TEST SPADL:', e.message); process.exit(2); });
