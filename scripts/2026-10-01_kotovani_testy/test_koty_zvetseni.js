// Cislice 2D kot ve vykresech online nabidky (Robert 2026-10-01: "koty 2D v online nabidce jsou prilis male cislice, zvetsit na 14px nebo 12px").
// Cislice jsou SOUCASTI obrazku (kresli je scena pri vytvoreni nabidky - drawDimensionOverlay), na obrazovce se zmensuji. Puvodne 13 px
// na 1000 px sirky platna -> na obrazovce 6-8 px. Test bere SKUTECNE funkce ze scene.html / catalog-panels.js:
//   A) napojeni exportu (captureOrthoWithDims + offerKotaLayout): meritko a okraj se predavaji, styl se nemeni, zive kotovani beze zmeny,
//   B) velikost pisma po zmene (drawDimensionOverlay nad syntetickym stolem/regalem) a jak velke je na OBRAZOVCE v online nabidce,
//   C) rozlozeni: zadny popisek nevybiha z platna ani se neprekryva.
// Spusteni: node test_koty_zvetseni.js   (konci kodem 0 jen kdyz VSE prosla)
// Kandidat pred nasazenim: SCENE_HTML=... CATALOG_PANELS_JS=... node test_koty_zvetseni.js   (RYCHLE=1 = jen napojeni + syntetika)
// Mutacni kontrola: puvodni soubory musi selhat (cislice na obrazovce < 12 px).
const vm = require('vm');
const fs = require('fs');
const os = require('os');
const path = require('path');
const { otevri, vykresli, zdroje } = require('./harness_koty');
const { otevriNabidku } = require('../2026-10-01_nabidka_tabulka_cen_testy/harness_nabidka');

const vysl = [];
const over = (nazev, podminka, detail) => {
  vysl.push(!!podminka);
  console.log((podminka ? 'OK   ' : 'FAIL ') + nazev + (podminka ? '' : '  -> ' + JSON.stringify(detail)));
};
const REPO = path.join(__dirname, '../..');
const SCENE = fs.readFileSync(process.env.SCENE_HTML || path.join(REPO, 'webapp/scene.html'), 'utf8');
const PANELS = fs.readFileSync(process.env.CATALOG_PANELS_JS || path.join(REPO, 'webapp/js/scene/catalog-panels.js'), 'utf8');
const D = fs.mkdtempSync(path.join(os.tmpdir(), 'koty-'));
// karta s vykresem v online nabidce pri 1440 x 900 (zmereno): sirka ~580 px, vyska ~752 px
const KARTA = { sirka: 580, vyska: 752 };

(async () => {
  const z = zdroje();
  const maLayout = !!z.layout;
  const layoutFn = maLayout ? new vm.Script(`${z.kotaKonst}\n${z.layout}\nofferKotaLayout;`).runInNewContext({ Math }) : null;
  const konst = maLayout ? new vm.Script(`${z.kotaKonst}\n({ OFFER_KOTA_LAYER, OFFER_PADDING_MIN, OFFER_PADDING_MAX })`).runInNewContext({}) : null;

  // ---------------------------------------------------------------- A) napojeni exportu
  over('A0 scene.html ma funkci offerKotaLayout (meritko kot + okraj pro export nabidky)', maLayout, null);
  if (maLayout) {
    for (const a of [0.4, 0.5, 0.68, 1, 1.3, 1.64, 2, 2.5]) {
      const l = layoutFn(a), H = 1180, Wp = H * a;
      const okrajOk = (1 - 1 / l.padding) / 2 + 1e-9 >= konst.OFFER_KOTA_LAYER * l.rel / 1000 / Math.min(1, a);
      const cislicePx = 13 * l.rel * H / 1000 * Math.min(KARTA.sirka / Wp, KARTA.vyska / H);
      over(`A1 pomer stran ${a}: okraj ${l.padding.toFixed(2)} (1,2-1,9) staci na koty, na obrazovce (1440x900) ~${cislicePx.toFixed(1)} px`,
           l.padding >= konst.OFFER_PADDING_MIN && l.padding <= konst.OFFER_PADDING_MAX + 1e-9 && l.rel > 0 && okrajOk && cislicePx >= (a <= 2.05 ? 12 : 10), { l, cislicePx });
    }
  }
  {
    const radky = (SCENE.match(/const OFFER_IMAGE_MIN_ASPECT[^;]*;/g) || []).concat(maLayout ? [z.kotaKonst] : []);
    const spusti = (placedPrazdne) => {
      const volaniView = [], volaniDim = [];
      const ctxObj = {
        placed: placedPrazdne ? [] : [{}],
        bboxOfEntries: () => ({ isEmpty: () => false, getSize: v => Object.assign(v, { x: 1000, y: 1450, z: 600 }) }),
        THREE: { Vector3: function () { this.x = this.y = this.z = 0; } },
        viewport: { clientHeight: 1180, clientWidth: 1500 }, renderer: { setSize() {} },
        setViewMode: (...a) => volaniView.push(a),
        captureCompositeView: () => ({ canvas: { width: 807, height: 1180, toDataURL: () => 'data:image/png;base64,' }, ctx: {} }),
        drawDimensionOverlay: (c, w, h, opts) => volaniDim.push({ w, h, opts }),
        STYL: { chainMerge: true, occlusion: 'loose', totals: 'segmentsOnly' },
        Object, Math,
      };
      vm.createContext(ctxObj);
      vm.runInContext(radky.join('\n') + '\n' + (maLayout ? z.layout : '') + '\n' + z.capture + '\nglobalThis.vysledek = captureOrthoWithDims("front", STYL);', ctxObj);
      return { volaniView, volaniDim, styl: ctxObj.STYL };
    };
    const t = spusti(false);
    const lay1 = maLayout ? layoutFn(1000 / 1450 > 0.4 ? Math.round(1180 * (1000 / 1450)) / 1180 : 0.4) : null;   // tesny rez: sirka modelu / vyska modelu (front: x / y)
    over('A2 export (tesny rez): setViewMode dostane dopocteny okraj (nad 1,2), ne vychozi',
         t.volaniView.length === 1 && t.volaniView[0][2] > 1.2 && (!lay1 || Math.abs(t.volaniView[0][2] - lay1.padding) < 0.01), t.volaniView);
    over('A3 export: drawDimensionOverlay dostane kotaScaleRel a puvodni styl (chainMerge/occlusion/totals) zustane',
         t.volaniDim.length === 1 && t.volaniDim[0].opts.kotaScaleRel > 1 && t.volaniDim[0].opts.chainMerge === true && t.volaniDim[0].opts.occlusion === 'loose' && t.volaniDim[0].opts.totals === 'segmentsOnly', t.volaniDim);
    over('A4 export nezmeni styl predany volajicim (zadne sdilene pole kotaScaleRel)', t.styl.kotaScaleRel === undefined, t.styl);
    const f = spusti(true);
    over('A5 export (zadne dily / zaloha): i tady okraj + meritko', f.volaniView.length === 1 && f.volaniView[0][2] > 1.2 && f.volaniDim.length === 1 && f.volaniDim[0].opts.kotaScaleRel > 1, { view: f.volaniView, dim: f.volaniDim });
    const zive = SCENE.match(/drawDimensionOverlay\(liveDimCtx[^;]*;/);
    over('A6 zive kotovani ve scene zustava beze zmeny: meritko se predava jen z exportu, vychozi je sirka / 1000',
         !!zive && !/kotaScaleRel/.test(zive[0]) && (SCENE.match(/kotaScaleRel: lay/g) || []).length === 2 && /: canvasW \/ 1000;/.test(SCENE), { zive: zive && zive[0].slice(0, 140) });
    over('A7 setViewMode: bez 3. parametru zustava okraj 1,2 (zive 2D pohledy beze zmeny)', /const PADDING = paddingOverride \|\| 1\.2;/.test(PANELS) && /function setViewMode\(mode, aspectOverride, paddingOverride\)/.test(PANELS), null);
  }

  // ---------------------------------------------------------------- B) velikost pisma na platne a na obrazovce, C) rozlozeni
  const { browser, page, chyby } = await otevri();
  const obrazky = {}, meta = {};
  const varianty = [['narys', 'front', 'stul'], ['bokorys', 'side', 'stul'], ['regal_narys', 'front', 'regal'], ['regal_bokorys', 'side', 'regal']];
  for (const [klic, mode, sestava] of varianty) {
    const r = await vykresli(page, { mode, sestava, H: 1180, padding: 1.2, layout: true });
    const f = path.join(D, klic + '.png');
    fs.writeFileSync(f, Buffer.from(r.png.split(',')[1], 'base64'));
    obrazky[klic] = f; meta[klic] = r;
    if (maLayout) {
      const ocek = Math.round(13 * r.layout.rel * r.H / 1000);
      over(`B1 ${klic} (${r.W}x${r.H}, okraj ${r.padding.toFixed(2)}): pismo kot na platne = 13 x meritko = ${ocek} px`, r.pismo === ocek && r.pismo >= 20, { pismo: r.pismo, ocek });
    }
    over(`C1 ${klic}: zadny popisek kot nevybiha z platna (nic neorezano)`, r.mimo.length === 0, r.mimo);
    over(`C2 ${klic}: popisky se (temer) neprekryvaji - nejvyse 2 dotyky v husté syntetice (${r.prekryvy})`, r.prekryvy <= 2, r.prekryvy);
  }
  over('C3 stranka s funkci kot nevyhodila zadnou chybu', chyby.length === 0, chyby.slice(0, 2));
  await browser.close();

  if (process.env.RYCHLE) {   // rychla kontrola pod zamkem pri nasazeni: napojeni + syntetika, bez mereni v online nabidce
    const okR = vysl.filter(Boolean).length;
    console.log(`\nVYSLEDEK cislice kot (RYCHLE): ${okR}/${vysl.length} OK`);
    process.exit(okR === vysl.length ? 0 : 1);
  }
  // skutecna velikost cislic NA OBRAZOVCE v online nabidce (zobrazeny obrazek / nativni velikost x pismo na platne)
  const nab = JSON.parse(fs.readFileSync(path.join(__dirname, '../2026-10-01_nabidka_tabulka_cen_testy/ukazka_nabidky.json'), 'utf8'));
  const mereni = {};
  for (const [w, h] of [[1366, 768], [1440, 900], [1920, 1080]]) {
    mereni[`${w}x${h}`] = [];
    for (const sada of [['narys', 'bokorys'], ['regal_narys', 'regal_bokorys']]) {
      const mapa = { narys: obrazky[sada[0]], bokorys: obrazky[sada[1]] };
      const o = await otevriNabidku({ width: w, height: h, nabidka: nab, obrazky: mapa });
      for (let i = 0; i < 4; i++) {
        if (await o.page.evaluate(() => !!document.querySelector('.slide.active .view-card img'))) break;
        await o.page.click('#btnNext'); await o.page.waitForTimeout(500);
      }
      await o.page.waitForTimeout(500);
      const imgs = await o.page.evaluate(() => [...document.querySelectorAll('.slide.active .view-card img')].map(i => ({ src: i.currentSrc.split('/').pop(), nw: i.naturalWidth, nh: i.naturalHeight, w: i.getBoundingClientRect().width, h: i.getBoundingClientRect().height })));
      imgs.forEach((i, idx) => {
        const klic = sada[idx], s = Math.min(i.w / i.nw, i.h / i.nh);
        mereni[`${w}x${h}`].push({ obraz: klic, zobrazeno: `${Math.round(i.w)}x${Math.round(i.h)}`, cislicePx: +(meta[klic].pismo * s).toFixed(1) });
      });
      await o.browser.close();
    }
  }
  console.log('   cislice kot na OBRAZOVCE online nabidky (px):', JSON.stringify(mereni));
  const m = k => mereni[k];
  over('B2 online nabidka 1366x768: cislice kot na obrazovce >= 12 px (puvodne 5-6 px), u extremne uzkeho bokorysu (pomer 0,4) >= 11 px',
       m('1366x768').length === 4 && m('1366x768').every(x => x.cislicePx >= (x.obraz === 'regal_bokorys' ? 11 : 12)), m('1366x768'));
  over('B3 online nabidka 1440x900: cislice kot na obrazovce 13-18 px (cil 14 px)', m('1440x900').length === 4 && m('1440x900').every(x => x.cislicePx >= 13 && x.cislicePx <= 18), m('1440x900'));
  over('B4 online nabidka 1920x1080: cislice kot na obrazovce 13-22 px (nejsou obrovske)', m('1920x1080').length === 4 && m('1920x1080').every(x => x.cislicePx >= 13 && x.cislicePx <= 22), m('1920x1080'));

  const ok = vysl.filter(Boolean).length;
  console.log(`\nVYSLEDEK cislice kot ve vykresech nabidky: ${ok}/${vysl.length} OK`);
  process.exit(ok === vysl.length ? 0 : 1);
})().catch(e => { console.error('TEST SPADL:', e.message); process.exit(2); });
