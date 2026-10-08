// Vykresy s kotami do online nabidky z konfigurace stolu (bot8, 2026-10-06): SKUTECNA scena (scene.html) v Chromiu pres most k Flasku (_most_scena.py; DB jen cte),
// rezim scene.html?stul=<query>&nabidka_vykresy=<offer_id> (webapp/js/scene/stul-nabidka-vykresy.js). Koncovy bod bot5 (POST /api/admin/konfigurace/nabidka/<id>/vykresy) je v testu
// FALESNY (page.route) - nic se nezapisuje.
// Overuje: A) hlavni tok - scena obsahuje JEN stul (posledni sestava z F5 se neobnovi), po vlozeni se vyrobi 3 vykresy (PNG s kotami) + 2 snimky 3D (JPEG), odeslou se na spravny endpoint
// v tvaru {views}; NARYS = celni strana stolu (kamera "side" = osa X, sirka stolu lezi na ose Z), BOKORYS = "front", PUDORYS = "top"; pocatecni krizek os se pri snimani skryje a pak vrati;
// pixelRatio, velikost platna a stav sceny se vrati; zadny popisek kot nevybiha z platna; B) chyby serveru / spojeni / neplatny stul - srozumitelna hlaska, "Zkusit znovu" posle znovu;
// C) bez parametru, neplatny parametr, chybi stul v adrese - nic se neodesle; D) male okno + HiDPI (1100x640, dpr 2) da TOTEZ (stejne rozmery obrazku) - vykres nezavisi na okne.
// Spusteni: systemd-run ... api/venv/bin/python3 scripts/2026-10-06_nabidka_vykresy_testy/_most_scena.py scripts/2026-10-06_nabidka_vykresy_testy/test_vykresy.js
//   (SHOT=/cesta ulozi vykresy jako PNG/JPEG; SCENARE=A|AD|AB|AC... = jen vybrane scenare, vychozi ADBC - pro mutacni beh; CEKEJ_MS = strop cekani na banner)
const { chromium } = require('/opt/konfigurator/node_modules/playwright-core');
const fs = require('fs');
const path = require('path');
const BASE = process.env.BASE, SHOT = process.env.SHOT || '', SCENARE = process.env.SCENARE || 'ADBC', CEKEJ_MS = Number(process.env.CEKEJ_MS) || 120000;
const vysl = [];
const over = (nazev, podminka, detail) => { vysl.push(!!podminka); console.log((podminka ? 'OK   ' : 'FAIL ') + nazev + (podminka ? '' : '  -> ' + JSON.stringify(detail).slice(0, 400))); };
const DEF = 'sirka=1280&hloubka=800&vyska=840&police=1&kolecka=1&panely=1&led=1&suplik=1&elektrozlab=1&drzak_pet=1&suplik_posun=0';
const KONEC = /Výkresy uloženy|nepodařilo|Nemáte|starší|selhalo|odmítl|chybí|nelze/;

// zachyceni volani captureOrthoWithDims (rezim, vysledek, smer kamery, stav os) - instaluje se hned po definici funkce, pred vlozenim stolu
const SONDA = () => {
  const t = setInterval(() => {
    if (typeof window.captureOrthoWithDims !== 'function' || window.captureOrthoWithDims.__sonda) return;
    clearInterval(t);
    const orig = window.captureOrthoWithDims;
    window.__vyk = [];
    window.captureOrthoWithDims = function (mode, opts) {
      const r = orig.apply(this, arguments);
      const d = camera.position.clone().sub(controls.target);
      const osa = Math.abs(d.x) >= Math.abs(d.y) && Math.abs(d.x) >= Math.abs(d.z) ? 'x' : Math.abs(d.y) >= Math.abs(d.z) ? 'y' : 'z';
      window.__vyk.push({ mode, uri: r, layer: opts && opts.kotaLayer, osaKamery: osa, osy: originAxisHelper.visible, ratio: renderer.getPixelRatio(), vyska: viewport.clientHeight });
      return r;
    };
    window.captureOrthoWithDims.__sonda = true;
  }, 2);
};

async function otevri(search, opts = {}) {
  const browser = await chromium.launch({ args: ['--no-sandbox', '--use-gl=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  const page = await browser.newPage({ viewport: opts.okno || { width: 1500, height: 900 }, deviceScaleFactor: opts.dsf || 1 });
  const st = { posty: [], chyby: [], odpovedi: opts.odpovedi || [{ status: 200, body: { ok: true, offer_id: 777, vykresy: ['bokorys', 'narys', 'pudorys', 'view3d_a', 'view3d_b'] } }] };
  page.on('pageerror', e => st.chyby.push(e.message.slice(0, 200)));
  await page.route('**/api/admin/konfigurace/nabidka/*/vykresy', async route => {
    const req = route.request();
    st.posty.push({ url: new URL(req.url()).pathname, metoda: req.method(), body: JSON.parse(req.postData() || '{}') });
    const o = st.odpovedi[Math.min(st.posty.length - 1, st.odpovedi.length - 1)];
    if (o.abort) return route.abort();
    return route.fulfill({ status: o.status, contentType: 'application/json', body: JSON.stringify(o.body) });
  });
  if (opts.localStorage) await page.addInitScript(kv => { for (const k in kv) localStorage.setItem(k, kv[k]); }, opts.localStorage);
  if (opts.sonda) await page.addInitScript(SONDA);
  await page.goto(BASE + '/scene.html' + search);
  return { browser, page, st };
}
const banner = page => page.evaluate(() => { const b = document.getElementById('nabidkaVykresyBanner'); return b ? { text: b.querySelector('#nabidkaVykresyText').textContent, tlacitka: [...b.querySelectorAll('button')].map(x => x.textContent) } : null; });
const pockej = (page, re, ms = CEKEJ_MS) => page.waitForFunction(r => { const b = document.getElementById('nabidkaVykresyText'); return b && new RegExp(r).test(b.textContent); }, re.source, { timeout: ms });
// rozmery obrazku + pocet tmavych pixelu v okrajovem pasu 2 px (oriznuty popisek / cara by tam nechal "inkoust")
const obrazek = (page, uri) => page.evaluate(src => new Promise(r => {
  const i = new Image();
  i.onload = () => {
    const c = document.createElement('canvas'); c.width = i.naturalWidth; c.height = i.naturalHeight;
    const x = c.getContext('2d'); x.drawImage(i, 0, 0);
    const w = c.width, h = c.height; let inkoust = 0;
    const tmave = d => { for (let k = 0; k < d.length; k += 4) if (d[k + 3] > 40 && (d[k] + d[k + 1] + d[k + 2]) / 3 < 200) inkoust++; };
    tmave(x.getImageData(0, 0, w, 2).data); tmave(x.getImageData(0, h - 2, w, 2).data); tmave(x.getImageData(0, 0, 2, h).data); tmave(x.getImageData(w - 2, 0, 2, h).data);
    const st = x.getImageData(0, 0, Math.min(w, 40), Math.min(h, 40)).data;     // levy horni roh: barva pozadi
    r({ w, h, inkoust, roh: [st[0], st[1], st[2]] });
  };
  i.onerror = () => r(null); i.src = src;
}), uri);
const uloz = (adresar, v) => { fs.mkdirSync(adresar, { recursive: true }); for (const k of Object.keys(v)) fs.writeFileSync(path.join(adresar, 'vykres_' + k + (k.startsWith('view3d') ? '.jpg' : '.png')), Buffer.from(v[k].split(',')[1], 'base64')); };

(async () => {
  // ---- A) hlavni tok (okno 1500 x 900, dpr 1)
  let { browser, page, st } = await otevri(`?stul=${encodeURIComponent(DEF)}&nabidka_vykresy=777`, { sonda: true, localStorage: { konfSceneLastLoadedAssembly: JSON.stringify({ type: 'custom_shape', id: 577 }) } });
  await pockej(page, KONEC);
  const b = await banner(page);
  over('A1 po vlozeni stolu se vykresy vyrobi a odeslou; banner "Vykresy ulozeny" s tlacitkem "Zavrit kartu"', b && /Výkresy uloženy/.test(b.text) && b.tlacitka.includes('Zavřít kartu'), b);
  over('A2 odeslano prave jednou na POST /api/admin/konfigurace/nabidka/777/vykresy', st.posty.length === 1 && st.posty[0].metoda === 'POST' && st.posty[0].url === '/api/admin/konfigurace/nabidka/777/vykresy', st.posty.map(p => p.url));
  const v = (st.posty[0] || { body: {} }).body.views || {};
  over('A3 views: narys, bokorys, pudorys jako PNG data-URI, view3d_a / view3d_b jako JPEG data-URI (a nic navic)', Object.keys(v).sort().join() === 'bokorys,narys,pudorys,view3d_a,view3d_b' && ['narys', 'bokorys', 'pudorys'].every(k => /^data:image\/png;base64,/.test(v[k])) && ['view3d_a', 'view3d_b'].every(k => /^data:image\/jpeg;base64,/.test(v[k])), Object.keys(v));
  if (SHOT) uloz(SHOT, v);
  const A = {};
  for (const k of Object.keys(v)) A[k] = await obrazek(page, v[k]);
  over('A4 vykresy maji PEVNOU vysku 1180 px, 3D snimky 1600 x 1000 (nezavisle na okne), kazdy < 2,5 MB', ['narys', 'bokorys', 'pudorys'].every(k => A[k] && A[k].h === 1180 && A[k].w > 300) && ['view3d_a', 'view3d_b'].every(k => A[k] && A[k].w === 1600 && A[k].h === 1000) && Object.values(v).every(u => u.length < 2.5e6 * 1.37), { A, bajty: Object.fromEntries(Object.entries(v).map(([k, u]) => [k, Math.round(u.length * 0.75)])) });
  over('A5 zadny popisek ani cara nevybiha z platna (okrajovy pas 2 px bez inkoustu) a pozadi vykresu je bile', ['narys', 'bokorys', 'pudorys'].every(k => A[k] && A[k].inkoust === 0 && A[k].roh.every(c => c >= 250)), Object.fromEntries(['narys', 'bokorys', 'pudorys'].map(k => [k, A[k] && { ink: A[k].inkoust, roh: A[k].roh }])));
  const sc = await page.evaluate(() => {
    const b = bboxOfEntries(placed), s = b.getSize(new THREE.Vector3()), d = window.StulKonf.state.data;
    return { placed: placed.length, dily: d.dily.length, vlastni: window.StulKonf.state.own.length, zScena: s.z, sirka: d.rozmery.sirka_mm, hloubka: d.rozmery.hloubka_mm, xGen: d.rozmery.x_max - d.rozmery.x_min, zGen: d.rozmery.z_max - d.rozmery.z_min };
  });
  over('A6 scena obsahuje JEN stul z adresy (posledni sestava z F5 se neobnovila): pocet dilu ve scene = dily stolu', sc.placed === sc.dily && sc.placed === sc.vlastni, sc);
  over('A7 sirka stolu lezi na ose Z a hloubka na X (generator rozmery = scena) - na tom stoji mapovani narys = "side"', Math.abs(sc.zScena - sc.sirka) < 3 && Math.abs(sc.zGen - sc.sirka) < 3 && Math.abs(sc.xGen - sc.hloubka) < 3, sc);
  const vyk = await page.evaluate(() => window.__vyk || []);
  const poModech = { side: [], front: [], top: [] };
  vyk.forEach(x => { (poModech[x.mode] = poModech[x.mode] || []).push(x); });
  const posledni = m => poModech[m][poModech[m].length - 1];
  over('A8 narys = snimek kamery "side" (smer pohledu osa X = celni strana), bokorys = "front" (osa Z), pudorys = "top" (osa Y); odeslany je vzdy POSLEDNI snimek daneho rezimu',
    ['side', 'front', 'top'].every(m => poModech[m].length >= 1) && Object.keys(poModech).length === 3 && v.narys === posledni('side').uri && v.bokorys === posledni('front').uri && v.pudorys === posledni('top').uri
      && posledni('side').osaKamery === 'x' && posledni('front').osaKamery === 'z' && posledni('top').osaKamery === 'y', vyk.map(x => [x.mode, x.layer, x.osaKamery]));
  // opakovani pri orezu: kazdy NEposlední pokus mel orez (inkoust u kraje), posledni nema, prvni bez vetsiho okraje a okraje rostou
  const ink = {};
  for (const x of vyk) ink[x.uri.length + ':' + x.mode + ':' + x.layer] = (await obrazek(page, x.uri)).inkoust;
  const klic = x => x.uri.length + ':' + x.mode + ':' + x.layer;
  const okrajeOk = ['side', 'front', 'top'].every(m => { const c = poModech[m]; return c[0].layer === undefined && c.every((x, i) => i === 0 || x.layer > (c[i - 1].layer || 0)) && c.every((x, i) => i === c.length - 1 ? ink[klic(x)] === 0 : ink[klic(x)] > 0); });
  over('A8b opakovani pri orezu: prvni pokus s vychozim okrajem, dalsi se vetsim; kazdy neposledni pokus mel inkoust u kraje, posledni (odeslany) ne', okrajeOk, vyk.map(x => [x.mode, x.layer, ink[klic(x)]]));
  over('A9 pri snimani vykresu je krizek os v pocatku SKRYTY, pixelRatio 1 a vyska platna 1180 (pevne, ne z okna)', vyk.length >= 3 && vyk.every(x => x.osy === false && x.ratio === 1 && x.vyska === 1180), vyk.map(x => [x.mode, x.osy, x.ratio, x.vyska]));
  const po = await page.evaluate(() => ({ osy: originAxisHelper.visible, ratio: renderer.getPixelRatio(), vlastniVyska: Object.prototype.hasOwnProperty.call(viewport, 'clientHeight'), vlastniSirka: Object.prototype.hasOwnProperty.call(viewport, 'clientWidth'), vyska: viewport.clientHeight, plocha: renderer.domElement.height, pozadiBile: !!(scene.background && scene.background.isColor && scene.background.getHex() === 0xffffff), rezim: renderMode }));
  over('A10 po snimani je vse vraceno: krizek os viditelny, pixelRatio puvodni, viewport bez podvrzenych rozmeru, plátno v prirozene velikosti, scena bez bileho pozadi technickeho rezimu', po.osy === true && po.ratio === 1 && !po.vlastniVyska && !po.vlastniSirka && po.vyska > 300 && po.vyska < 1100 && po.plocha === po.vyska && !po.pozadiBile, po);
  over('A11 bez chyb ve strance', st.chyby.length === 0, st.chyby.slice(0, 3));
  const sirce3d = await page.evaluate(src => new Promise(r => { const i = new Image(); i.onload = () => { const c = document.createElement('canvas'); c.width = 20; c.height = 20; const x = c.getContext('2d'); x.drawImage(i, 0, 0, 20, 20); const d = x.getImageData(0, 0, 20, 20).data; let svetle = 0; for (let k = 0; k < d.length; k += 4) if ((d[k] + d[k + 1] + d[k + 2]) / 3 > 235) svetle++; r(svetle / 400); }; i.src = src; }), v.view3d_a);
  over('A12 3D snimek neni v bilem technickem rezimu (vetsina pozadi neni bila)', sirce3d < 0.3, sirce3d);
  await browser.close();

  // ---- D) male okno + HiDPI: totez (stejne rozmery) - vykres nezavisi na okne
  if (SCENARE.includes('D')) {
  ({ browser, page, st } = await otevri(`?stul=${encodeURIComponent(DEF)}&nabidka_vykresy=777`, { okno: { width: 1100, height: 640 }, dsf: 2 }));
  await pockej(page, KONEC);
  const vD = (st.posty[0] || { body: {} }).body.views || {};
  const D = {};
  for (const k of Object.keys(vD)) D[k] = await obrazek(page, vD[k]);
  over('D1 male okno 1100 x 640 s dpr 2: uspech a TYTEZ rozmery vsech 5 obrazku jako v okne 1500 x 900 s dpr 1', st.posty.length === 1 && ['narys', 'bokorys', 'pudorys', 'view3d_a', 'view3d_b'].every(k => D[k] && A[k] && D[k].w === A[k].w && D[k].h === A[k].h), { A: Object.fromEntries(Object.entries(A).map(([k, x]) => [k, x && [x.w, x.h]])), D: Object.fromEntries(Object.entries(D).map(([k, x]) => [k, x && [x.w, x.h]])) });
  over('D2 ani v malem okne popisky nevybihaji z platna', ['narys', 'bokorys', 'pudorys'].every(k => D[k] && D[k].inkoust === 0), Object.fromEntries(['narys', 'bokorys', 'pudorys'].map(k => [k, D[k] && D[k].inkoust])));
  await browser.close();
  }

  if (SCENARE.includes('B')) {
    // ---- B) chyby serveru a "Zkusit znovu"
    ({ browser, page, st } = await otevri(`?stul=${encodeURIComponent(DEF)}&nabidka_vykresy=778`, { odpovedi: [{ status: 409, body: { error: 'vykresy_expired', message: 'x' } }, { status: 403, body: { error: 'forbidden' } }, { status: 200, body: { ok: true, offer_id: 778, vykresy: [] } }] }));
    await pockej(page, /starší/);
    let bb = await banner(page);
    over('B1 409 vykresy_expired: ceska hlaska o 24 h a tlacitko "Zkusit znovu"', bb && /starší než 24 hodin/.test(bb.text) && bb.tlacitka.includes('Zkusit znovu'), bb);
    await page.click('#nabidkaVykresyBanner button');
    await pockej(page, /Nemáte právo/);
    over('B2 "Zkusit znovu" posle znovu (druhy POST) a 403 ukaze hlasku o pravu', st.posty.length === 2, st.posty.length);
    await page.click('#nabidkaVykresyBanner button');
    await pockej(page, /Výkresy uloženy/);
    over('B3 treti pokus uspeje: banner "Vykresy ulozeny" (3 POSTy celkem)', st.posty.length === 3, st.posty.length);
    await browser.close();
    ({ browser, page, st } = await otevri(`?stul=${encodeURIComponent(DEF)}&nabidka_vykresy=779`, { odpovedi: [{ abort: true }] }));
    await pockej(page, /Spojení/);
    bb = await banner(page);
    over('B4 vypadne spojeni: hlaska "Spojeni se serverem selhalo" a "Zkusit znovu"', bb && /Spojení se serverem selhalo/.test(bb.text) && bb.tlacitka.includes('Zkusit znovu'), bb);
    await browser.close();
    ({ browser, page, st } = await otevri(`?stul=${encodeURIComponent('sirka=abc&hloubka=800')}&nabidka_vykresy=780`));
    await pockej(page, /nepodařilo vložit/);
    bb = await banner(page);
    await page.waitForTimeout(1500);
    over('B5 neplatny stul (server ho odmitne): hlaska "Stul se do sceny nepodarilo vlozit", bez tlacitka a nic se neodesle', bb && /Stůl se do scény nepodařilo vložit/.test(bb.text) && bb.tlacitka.length === 0 && st.posty.length === 0, { bb, posty: st.posty.length });
    await browser.close();
  }

  if (SCENARE.includes('C')) {
    // ---- C) bez parametru / neplatny parametr / chybi stul: nic se neodesle
    for (const [popis, search, cekej] of [['bez nabidka_vykresy', `?stul=${encodeURIComponent(DEF)}`, 6000], ['neplatny nabidka_vykresy=abc', `?stul=${encodeURIComponent(DEF)}&nabidka_vykresy=abc`, 6000], ['jen nabidka_vykresy bez stolu', '?nabidka_vykresy=5', 2500]]) {
      ({ browser, page, st } = await otevri(search));
      await page.waitForFunction(() => typeof CATALOG !== 'undefined' && CATALOG.length > 0, null, { timeout: 60000 });
      await page.waitForTimeout(cekej);
      const x = await page.evaluate(() => ({ banner: !!document.getElementById('nabidkaVykresyBanner') && document.getElementById('nabidkaVykresyText').textContent, id: window.__nabidkaVykresy, placed: placed.length }));
      const ok = popis.startsWith('jen') ? /V adrese chybí konfigurace stolu/.test(x.banner) : !x.banner;
      over(`C ${popis}: ${popis.startsWith('jen') ? 'banner "V adrese chybi konfigurace stolu", nic se neodesle' : 'zadny banner, nic se neodesle'}`, st.posty.length === 0 && ok, x);
      await browser.close();
    }
  }
  const ok = vysl.filter(Boolean).length;
  console.log(`\nVYSLEDEK vykresy nabidky ze stolu: ${ok}/${vysl.length} OK`);
  process.exit(ok === vysl.length ? 0 : 1);
})().catch(e => { console.error('TEST SPADL:', e.message); process.exit(2); });
