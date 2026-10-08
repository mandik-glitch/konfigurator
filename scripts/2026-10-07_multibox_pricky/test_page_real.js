// Integracni test stranky online nabidky se SKUTECNYM 3D prohlizecem V3D (webapp/js/v3d/viewer3d.js + three r128, swiftshader) a SKUTECNYM pluginem priccek (bot8, 2026-10-07).
// Stranka proti falesnemu serveru (harness_pricky.js), model = zakaznicke GLB karty 4921, payload = SKUTECNY offer.pricky z api/nabidka_pricky.payload (vsechny skupiny vc. supliku, pokud je GLB ma:
// GLB z v5 buildu = police 8 + 2 vysuvy po 7 + 3 skupiny po 1 podnosu supliku). Overuje se skutecnymi soucastmi:
//   klik na set skupiny -> pricky ve scene, vsechny boxy / podnosy TE skupiny se VYSUNOU (viewer.play(id, 1) pro id z api.motionIds, kazdy jednou, v poradi; jine skupiny ne), "Bez pricek" nezavre,
//   zvyrazneni skupiny ve scene (obrys) a jeho zruseni nejdrive ~3 s po kliknuti, obnova vyberu z localStorage pri nacteni nic nevysune; u supliku totez pro skupinu podnosu.
// Casovani odstupu ~150 ms mezi boxy se tu NEOVERUJE (swiftshader blokuje hlavni vlakno a casovace se pak spusti nahromadene) - to hlida test_page.js s atrapou prohlizece (sekce O).
// SPUSTENI (z teto slozky; potrebuje zakaznicke GLB: python3 /opt/konfigurator/scripts/2026-10-02_v3d_testy/build_karty.py 4921, a node_modules/three; ~3-8 min, swiftshader):
//   node test_page_real.js        (exit 0 jen kdyz vse prosel; SNIMKY=<slozka> uklada snimky vysunute police a podnosu)
// Prostredi jako u test_page.js (PRICKY_REPO, NABIDKA_HTML, PLUGIN_JS = skutecny plugin, PRICKY_API, V3D_TEST_OUT, THREE_DIR).
const fs = require('fs');
const path = require('path');
const H = require('./harness_pricky.js');
const vysl = [];
const over = (nazev, podminka, detail) => { vysl.push(!!podminka); console.log((podminka ? 'OK   ' : 'FAIL ') + nazev + (podminka ? '' : '  -> ' + JSON.stringify(detail).slice(0, 600))); };
const SNIMKY = process.env.SNIMKY || '';
const HOOK = `
  (function () {
    // viewer i plugin nejdriv priradi PRAZDNY objekt (global.V3D = {}, global.V3DPricky = {}) a funkce doplni pozdeji -> zachyceni pres pristupovou vlastnost na tom objektu
    function hookProp(obj, name, wrapper) {
      var val;
      Object.defineProperty(obj, name, { configurable: true, enumerable: true, get: function () { return val; }, set: function (f) { val = typeof f === 'function' ? wrapper(f) : f; } });
    }
    function hookGlobal(jmeno, vlastnost, wrapper) {
      var obj;
      Object.defineProperty(window, jmeno, { configurable: true, get: function () { return obj; }, set: function (v) { obj = v; if (v && typeof v === 'object') hookProp(v, vlastnost, wrapper); } });
    }
    function pocetObrysu() {                                  // znacky obrysu zvyrazneni ve scene (plugin: userData.__prickyHl)
      var c = window.__ctx, n = 0; if (!c) return -1;
      c.scene.traverse(function (o) { if (o.userData && o.userData.__prickyHl !== undefined) n++; });
      return n;
    }
    window.__playLog = []; window.__hlLog = []; window.__tClick = null;
    document.addEventListener('click', function () { window.__tClick = performance.now(); }, true);
    hookGlobal('V3DPricky', 'create', function (orig) { return function () {
      var r = orig.apply(this, arguments); window.__prApi = r.api;
      var hg = r.api.highlightGroup;                          // zaznam volani zvyrazneni s casem a poctem obrysu ve scene hned po volani (nezavisle na zpozdeni Playwrightu pri zatizeni)
      r.api.highlightGroup = function (gid) { var res = hg.apply(this, arguments); window.__hlLog.push({ gid: gid, t: performance.now(), obrysu: pocetObrysu() }); return res; };
      return r; }; });
    hookGlobal('V3D', 'mount', function (orig) { return function (el, o) {
      o = Object.assign({}, o);
      o.plugins = (o.plugins || []).concat([function (ctx) { window.__ctx = ctx; window.__ctxN = (window.__ctxN || 0) + 1; }]);
      var api = orig.call(this, el, o); window.__v3dApi = api;
      var p = api.play; api.play = function (id, dir) { window.__playLog.push([id, dir, performance.now()]); return p.apply(this, arguments); };
      return api; }; });
  })();
`;
const znacky = page => page.evaluate(() => {
  const c = window.__ctx; if (!c) return null;
  const out = { pricky: 0 };
  c.scene.traverse(n => { if (n.userData && n.userData.__pricky !== undefined && n.userData.__pricky !== true) out.pricky++; });
  return out;
});
const stavT = (page, ids) => page.evaluate(ids => { const t = window.__v3dApi.state().t; return ids.map(id => Math.round((t[id] || 0) * 1000) / 1000); }, ids);
const cekejOtevreno = (page, ids, ms = 40000) => page.waitForFunction(ids => { const t = window.__v3dApi.state().t; return ids.every(id => (t[id] || 0) >= 0.99); }, ids, { timeout: ms }).then(() => true, () => false);
const playLog = page => page.evaluate(() => window.__playLog.map(x => [x[0], x[1]]));

(async () => {
  const V = H.payloadVse('4921');                                                          // payload tak, jak ho dal server (multiboxy i supliky)
  const data = H.nabidka({ pricky: V });
  const mbx = V.skupiny.filter(g => g.k !== 'suplik'), sup = V.skupiny.filter(g => g.k === 'suplik');
  const g1 = mbx[0].id, g2 = mbx[1].id;
  const r = await H.otevri({ v3d: 'real', plugin: 'real', gl: true, init: [HOOK], width: 1440, height: 900, data });
  const { page } = r;
  await H.naSlide(page, 'view_3d');
  await page.waitForSelector('#prickyPanel:not([hidden]) .pr-card', { timeout: 120000 });
  await page.waitForFunction(() => window.__prApi && window.__prApi.ready && window.__prApi.ready(), null, { timeout: 120000 });
  await page.waitForTimeout(1500);
  const ids = {};
  for (const g of V.skupiny) ids[g.id] = await page.evaluate(g => window.__prApi.motionIds(g), g.id);
  const sk = await page.evaluate(() => window.__prApi.skupiny().map(g => [g.id, g.ready, g.pocet_ready, g.boxu]));
  const hasMotionIds = (await page.evaluate(() => typeof window.__prApi.motionIds)) === 'function';
  over(`R1 skutecny viewer + plugin: model se postavil, plugin vidi vsech ${V.skupiny.length} skupin a vsechny boxy / podnosy ve 3D a ma api.motionIds (id pohybu: unikatni retezce, pro kazdou skupinu aspon jeden)`,
    sk.length === V.skupiny.length && sk.every(g => g[1] && g[2] === g[3]) && hasMotionIds && V.skupiny.every(g => Array.isArray(ids[g.id]) && ids[g.id].length > 0 && new Set(ids[g.id]).size === ids[g.id].length && ids[g.id].every(x => typeof x === 'string')), { sk, ids });
  const vsechna = [].concat(...V.skupiny.map(g => ids[g.id]));
  over('R2 pred vyberem jsou vsechny pohyby zavrene (t = 0) a prohlizec nedostal zadne play', (await stavT(page, vsechna)).every(t => t === 0) && (await playLog(page)).length === 0, { t: await stavT(page, vsechna), play: await playLog(page) });
  await page.click(`#prickyPanel .pr-chip[data-cil="${g1}"][data-set="mix1"]`);
  await page.mouse.move(5, 5);                                                             // mys pryc z karty hned po kliknuti: zvyrazneni se ma presto drzet ~3 s
  const otevreno = await cekejOtevreno(page, ids[g1]);
  over(`R3 klik na set skupiny ${g1} (Mix 1): viewer.play(id, 1) dostaly VSECHNY pohyby boxu skupiny (id z api.motionIds), kazdy jednou a v poradi skupiny, nic jineho; boxy jsou plne vysunute (t = 1)`,
    otevreno && JSON.stringify(await playLog(page)) === JSON.stringify(ids[g1].map(id => [id, 1])), { otevreno, play: await playLog(page), ids: ids[g1], t: await stavT(page, ids[g1]) });
  const ostatni = [].concat(...V.skupiny.filter(g => g.id !== g1).map(g => ids[g.id])).filter(id => !ids[g1].includes(id));
  over('R4 pohyby ostatnich skupin zustaly zavrene (t = 0; pohyby sdilene s vysunutou skupinou se nepocitaji)', (await stavT(page, ostatni)).every(t => t === 0), { ostatni, t: await stavT(page, ostatni) });
  const z = await znacky(page);
  const sm = await page.evaluate(() => window.__prApi.souhrn());
  over(`R5 ve scene jsou pricky skupiny ${g1} (set Mix 1) a souhrn pluginu sedi se strankou (odznak v zahlavi)`, z.pricky > 0 && sm.kusy > 0 && (await page.evaluate(() => document.querySelector('#prickyPanel .pr-badge').textContent.replace(/[  ]/g, ' '))).startsWith(sm.kusy + ' ks'), { z, kusy: sm.kusy });
  await page.waitForFunction(() => window.__hlLog.some(x => x.gid === null && x.t > window.__tClick), null, { timeout: 30000 }).catch(() => {});
  const hl = await page.evaluate(() => ({ tClick: window.__tClick, log: window.__hlLog.map(x => [x.gid, Math.round(x.t - window.__tClick), x.obrysu]) }));
  const pred = hl.log.filter(x => x[1] >= 0), prvniNull = pred.find(x => x[0] === null);
  over(`R6 po kliknuti na set je skupina ${g1} ve scene zvyraznena (highlightGroup, obrys boxu ve scene) a zvyrazneni se zrusi (highlightGroup(null), obrysy zmizi) nejdrive ~3 s po kliknuti, i kdyz mys hned odjela z karty`,
    pred.length >= 2 && pred.some(x => x[0] === g1 && x[2] > 0) && prvniNull && prvniNull[1] >= 2900 && prvniNull[2] === 0 && pred.filter(x => x[0] === null).every(x => x[1] >= 2900), hl);
  if (SNIMKY) { fs.mkdirSync(SNIMKY, { recursive: true }); await page.screenshot({ path: path.join(SNIMKY, 'real_v5_police_vysunute.png') }); }
  const playPred = (await playLog(page)).length;
  await page.click(`#prickyPanel .pr-chip[data-cil="${g1}"][data-set="bez"]`);
  await page.waitForTimeout(2500);
  over('R7 "Bez pricek" boxy NEzavre (zadne dalsi play, zustavaji vysunute, t = 1), jen pricky ze sceny zmizely', (await playLog(page)).length === playPred && (await stavT(page, ids[g1])).every(t => t >= 0.99) && (await znacky(page)).pricky === 0, { t: await stavT(page, ids[g1]), z: await znacky(page) });
  await page.click(`#prickyPanel .pr-chip[data-cil="${g2}"][data-set="pln"]`);
  const otevreno2 = await cekejOtevreno(page, ids[g2]);
  const jinaZavrena = [].concat(...V.skupiny.filter(g => g.id !== g1 && g.id !== g2).map(g => ids[g.id])).filter(id => !ids[g1].includes(id) && !ids[g2].includes(id));
  over(`R8 dalsi skupina (${g2}, Plny set): vysunou se jeji boxy (t = 1); pohyby ostatnich skupin zustaly zavrene`, otevreno2 && (await stavT(page, jinaZavrena)).every(t => t === 0), { s2: await stavT(page, ids[g2]), jina: await stavT(page, jinaZavrena) });
  if (sup.length) {                                                                         // v5: skupina PODNOSU ocelovych supliku
    const gs = sup[0].id, sety = Object.keys(sup[0].sety);
    const pred = (await znacky(page)).pricky, playPredS = (await playLog(page)).length;
    await page.click(`#prickyPanel .pr-chip[data-cil="${gs}"][data-set="pln"]`);
    const otevrenoS = await cekejOtevreno(page, ids[gs]);
    const novePlay = (await playLog(page)).slice(playPredS);
    const sm2 = await page.evaluate(() => window.__prApi.souhrn());
    over(`R9 supliky (v5): klik na Plny set skupiny podnosu ${gs} (${sup[0].popis}): viewer.play(id, 1) dostaly vsechny pohyby podnosu skupiny (kazdy jednou, v poradi), podnosy jsou vysunute (t = 1), ve scene pribyly pricky (zepredu dozadu)`,
      sety.includes('pln') && otevrenoS && JSON.stringify(novePlay) === JSON.stringify(ids[gs].map(id => [id, 1])) && (await znacky(page)).pricky > pred && sm2.skupiny.some(x => x.id === gs && x.priccek > 0), { sety, otevrenoS, novePlay, ids: ids[gs], pred, po: await znacky(page) });
    if (SNIMKY) await page.screenshot({ path: path.join(SNIMKY, 'real_v5_suplik_vysunuty.png') });
    const dalsiSup = [].concat(...sup.slice(1).map(g => ids[g.id])).filter(id => !ids[gs].includes(id));
    over('R10 supliky: podnosy ostatnich skupin supliku zustaly zavrene (t = 0)', (await stavT(page, dalsiSup)).every(t => t === 0), { dalsiSup, t: await stavT(page, dalsiSup) });
  } else console.log('SKIP R9-R10 supliky (GLB nema podnosy supliku: postav v5 buildem build_karty.py 4921)');
  over('R11 bez chyb JS ve strance', r.chyby.length === 0, r.chyby);
  console.log('konzole:', JSON.stringify(r.konzole.filter(k => !/Failed to load resource|GPU stall/.test(k)).slice(0, 5)));
  await r.browser.close();

  // obnova vyberu z localStorage pri nacteni stranky nic nevysouva (jen pricky ve scene)
  const bs2 = mbx[1].boxy;
  const r2 = await H.otevri({ v3d: 'real', plugin: 'real', gl: true, init: [HOOK], width: 1440, height: 900, data: H.nabidka({ pricky: V }), ls: { v: 2, boxy: { [bs2[0]]: 1, [bs2[1]]: 1 } } });
  await H.naSlide(r2.page, 'view_3d');
  await r2.page.waitForSelector('#prickyPanel:not([hidden]) .pr-card', { timeout: 120000 });
  await r2.page.waitForFunction(() => window.__prApi && window.__prApi.ready && window.__prApi.ready(), null, { timeout: 120000 });
  await r2.page.waitForTimeout(2500);
  const idsAll = await r2.page.evaluate(() => window.__prApi.motionIds());
  const zr = await znacky(r2.page);
  over('R12 obnova vyberu z localStorage pri nacteni stranky: pricky ve scene jsou, ale ZADNY box se nevysunul (vsechny pohyby t = 0, prohlizec nedostal zadne play)', zr.pricky > 0 && idsAll.length > 0 && (await stavT(r2.page, idsAll)).every(t => t === 0) && (await playLog(r2.page)).length === 0, { zr, t: await stavT(r2.page, idsAll), play: await playLog(r2.page) });
  over('R13 bez chyb JS ve strance (obnova)', r2.chyby.length === 0, r2.chyby);
  await r2.browser.close();

  // karta 4968 (v5 GLB): skupiny po 2 podnosech (dvojice 443 + 695, OTOCENE e = -1) - Mix se ruznymi pocty pricek v podnosech jedne skupiny
  if (H.maKartu('4968')) {
    const V8 = H.payloadVse('4968'), gS = V8.skupiny[0], volba = gS.sety.mix1 ? 'mix1' : 'pln';
    const r3 = await H.otevri({ v3d: 'real', plugin: 'real', gl: true, init: [HOOK], width: 1440, height: 900, karta: '4968', data: H.nabidka({ karta: '4968', pricky: V8 }) });
    await H.naSlide(r3.page, 'view_3d');
    await r3.page.waitForSelector('#prickyPanel:not([hidden]) .pr-card', { timeout: 120000 });
    await r3.page.waitForFunction(() => window.__prApi && window.__prApi.ready && window.__prApi.ready(), null, { timeout: 120000 });
    await r3.page.waitForTimeout(1500);
    const idsS = await r3.page.evaluate(g => window.__prApi.motionIds(g), gS.id);
    await r3.page.click(`#prickyPanel .pr-chip[data-cil="${gS.id}"][data-set="${volba}"]`);
    const otevrenoS = await cekejOtevreno(r3.page, idsS);
    const pocty = await r3.page.evaluate(() => window.__prApi.get());
    const ocek = {};
    gS.boxy.forEach((id, i) => { const n = gS.sety[volba].po_boxech[i]; if (n > 0) ocek[id] = n; });
    over(`R14 karta 4968 (supliky otocene e = -1, skupiny po ${gS.boxy.length} podnosech): set ${volba} skupiny ${gS.id} (${gS.popis}) - viewer.play pro vsechny podnosy skupiny (kazdy jednou), podnosy vysunute, plugin drzi pocty po podnosech podle po_boxech, ve scene pricky`,
      otevrenoS && idsS.length > 0 && JSON.stringify(await playLog(r3.page)) === JSON.stringify(idsS.map(id => [id, 1])) && JSON.stringify(Object.entries(pocty).sort()) === JSON.stringify(Object.entries(ocek).sort()) && (await znacky(r3.page)).pricky > 0, { idsS, play: await playLog(r3.page), pocty, ocek });
    if (SNIMKY) { fs.mkdirSync(SNIMKY, { recursive: true }); await r3.page.screenshot({ path: path.join(SNIMKY, 'real_v5_4968_suplik_mix.png') }); }
    over('R15 bez chyb JS ve strance (karta 4968)', r3.chyby.length === 0, r3.chyby);
    await r3.browser.close();
  } else console.log('SKIP R14-R15 karta 4968 (GLB nema: v5 build build_karty.py 4968)');

  const ok = vysl.filter(Boolean).length;
  console.log(`\n${ok}/${vysl.length} kontrol prošlo (skutečný viewer + skutečný plugin)`);
  process.exit(ok === vysl.length ? 0 : 1);
})().catch(e => { console.error('TEST SPADL:', e.stack || e.message); process.exit(2); });
