// Kóty ve výkresech stolu pro online nabídku: bez překryvů, bez duplicit, rozumně rozložené (bot16, 2026-10-07).
// Robert 2026-10-07 (nabídka č. 126 z generátoru): „kóty se nesmí takto překrývat ani být příliš blízko", „musí se umísťovat rozumně rovnoměrně, ať jsou jasné",
// „nad stolem nad deskou je spousta volného místa, proto nechceme cpát všechny kóty pod stůl". Výkresy ze stolu dělá SCÉNA (scene.html?stul=<dotaz>&nabidka_vykresy=<id>,
// drawDimensionOverlay s volbou kotaAvoid); test spustí SKUTEČNOU scénu v Chromiu přes most k Flasku (_most_scena.py; DB jen čte, koncový bod nabídky je falešný přes page.route),
// pro sadu stolů (dotazy.json: přesně stůl z nabídky 126, výchozí stoly 30/35/40 a plně vybavený stůl) vyrobí nárys / bokorys / půdorys a ze zaznamenané geometrie kót
// (window.__kotaDebug) spočítá: duplicity, překryvy popisků, popisek přes cizí čáru, rovnoběžné čáry blíž než MINSEP, popisek mimo plátno. Porovnává VYPNUTÉ (původní chování,
// window.__kotaAvoidOff) a ZAPNUTÉ rozmisťování; zapnuté musí mít všude nuly. Obrázky: SHOT=/cesta uloží PNG (nazev_off|on_pohled.png).
// Spuštění: systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --setenv=HOME=/root --setenv=SHOT=/cesta --working-directory=/opt/konfigurator \
//   api/venv/bin/python3 scripts/2026-10-06_nabidka_vykresy_testy/_most_scena.py scripts/2026-10-07_koty_stul_testy/test_koty_stul.js     (WEB_DIR = kandidát statiky, SCEN=nabidka126,… výběr, MOD=on|off|oba)
const { chromium } = require('/opt/konfigurator/node_modules/playwright-core');
const fs = require('fs');
const path = require('path');
const BASE = process.env.BASE, SHOT = process.env.SHOT || '', MOD = process.env.MOD || 'oba', SCEN = (process.env.SCEN || '').split(',').filter(Boolean);
const SADA = JSON.parse(fs.readFileSync(path.join(__dirname, 'dotazy.json'), 'utf8')).filter(s => !SCEN.length || SCEN.includes(s.nazev));
const vysl = [];
const over = (nazev, podminka, detail) => { vysl.push(!!podminka); console.log((podminka ? 'OK   ' : 'FAIL ') + nazev + (podminka ? '' : '  -> ' + JSON.stringify(detail).slice(0, 500))); };

const SONDA = () => {            // do __kotaDebug se pred kazdym snimkem zapise {type:'capture', mode}
  const t = setInterval(() => {
    if (typeof window.captureOrthoWithDims !== 'function' || window.captureOrthoWithDims.__sonda) return;
    clearInterval(t);
    const orig = window.captureOrthoWithDims;
    window.captureOrthoWithDims = function (mode) { window.__kotaDebug.push({ type: 'capture', mode }); return orig.apply(this, arguments); };
    window.captureOrthoWithDims.__sonda = true;
  }, 2);
};

async function jedenStul(browser, sc, vypnuto) {
  const page = await browser.newPage({ viewport: { width: 1500, height: 900 } });
  const posts = [], chyby = [];
  page.on('pageerror', e => chyby.push(e.message.slice(0, 200)));
  await page.route('**/api/admin/konfigurace/nabidka/*/vykresy', async route => {
    posts.push(JSON.parse(route.request().postData() || '{}'));
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true, offer_id: 777, vykresy: ['bokorys', 'narys', 'pudorys', 'view3d_a', 'view3d_b'] }) });
  });
  await page.addInitScript(off => { window.__kotaDebug = []; if (off) window.__kotaAvoidOff = true; }, vypnuto);
  await page.addInitScript(SONDA);
  await page.goto(BASE + '/scene.html?stul=' + encodeURIComponent(sc.dotaz) + '&nabidka_vykresy=777');
  await page.waitForFunction(() => { const b = document.getElementById('nabidkaVykresyText'); return b && /Výkresy uloženy|nepodařilo|selhalo|odmítl|chybí|nelze/.test(b.textContent); }, null, { timeout: 240000 });
  const dbg = await page.evaluate(() => window.__kotaDebug);
  await page.close();
  return { posts, dbg, chyby };
}

// posledni snimek kazdeho pohledu: {mode -> {W,H,scale,laneStep,avoid,dims:[...], skipped}}
function pohledy(dbg) {
  const out = {};
  let mode = null, cur = null;
  for (const e of dbg) {
    if (e.type === 'capture') { mode = e.mode; cur = null; }
    else if (e.type === 'begin') { cur = { W: e.W, H: e.H, scale: e.scale, laneStep: e.laneStep, avoid: e.avoid, dims: [], skipped: 0 }; if (mode) out[mode] = cur; }
    else if (cur && e.type === 'dim') cur.dims.push(e);
    else if (cur && e.type === 'skip') cur.skipped++;
  }
  return out;
}
const hit = (a, b, pad = 0) => a[0] < b[2] + pad && a[2] > b[0] - pad && a[1] < b[3] + pad && a[3] > b[1] - pad;
const segBox = (e, pad) => [Math.min(e[0], e[2]) - pad, Math.min(e[1], e[3]) - pad, Math.max(e[0], e[2]) + pad, Math.max(e[1], e[3]) + pad];
function metriky(v) {
  const m = { dim: v.dims.length, skip: v.skipped, dup: 0, labelLabel: 0, labelCara: 0, rovnobezne: 0, mimo: 0, krizeni: 0, strany: { up: 0, down: 0, left: 0, right: 0 } };
  const MINSEP = 20 * v.scale;
  v.dims.forEach(d => { m.strany[d.side] = (m.strany[d.side] || 0) + 1; });
  v.dims.forEach(d => { if (d.labelBox[0] < 0 || d.labelBox[1] < 0 || d.labelBox[2] > v.W || d.labelBox[3] > v.H) m.mimo++; });
  for (let i = 0; i < v.dims.length; i++) {
    for (let j = 0; j < v.dims.length; j++) {
      if (i === j) continue;
      const a = v.dims[i], b = v.dims[j];
      if (j > i) {
        if (hit(a.labelBox, b.labelBox)) m.labelLabel++;
        const aq = segBox(a.q, 0.5 * v.scale), bq = segBox(b.q, 0.5 * v.scale);
        if (a.vertical === b.vertical) {
          const k = a.vertical ? 1 : 0;
          const ov = Math.min(aq[k + 2], bq[k + 2]) - Math.max(aq[k], bq[k]);
          const d = Math.abs(a.vertical ? a.q[0] - b.q[0] : a.q[1] - b.q[1]);
          if (ov > 4 * v.scale && d < MINSEP) m.rovnobezne++;
          if (a.label === b.label && ov >= 0.85 * Math.min(aq[k + 2] - aq[k], bq[k + 2] - bq[k]) && d < 1.25 * v.laneStep) m.dup++;
        } else if (hit(aq, bq)) m.krizeni++;
      }
      if (hit(a.labelBox, segBox(b.q, 1)) || b.ext.some(e => hit(a.labelBox, segBox(e, 1)))) m.labelCara++;
    }
  }
  return m;
}
const ulozPng = (nazev, mod, pohled, uri) => { if (!SHOT || !uri) return; fs.mkdirSync(SHOT, { recursive: true }); fs.writeFileSync(path.join(SHOT, `${nazev}_${mod}_${pohled}.png`), Buffer.from(String(uri).replace(/^data:image\/\w+;base64,/, ''), 'base64')); };
const PORADI = ['side', 'front', 'top'];                   // narys = "side", bokorys = "front", pudorys = "top" (viz stul-nabidka-vykresy.js)
const JMENO = { side: 'narys', front: 'bokorys', top: 'pudorys' };

(async () => {
  const browser = await chromium.launch({ args: ['--no-sandbox', '--use-gl=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  const vsechny = {};
  for (const sc of SADA) {
    for (const [mod, vypnuto] of [['off', true], ['on', false]]) {
      if (MOD !== 'oba' && MOD !== mod) continue;
      const { posts, dbg, chyby } = await jedenStul(browser, sc, vypnuto);
      const pv = pohledy(dbg);
      const views = (posts[0] && posts[0].views) || {};
      if (process.env.ONLY_PNG) {                                    // jen obrazky (porovnani s puvodni scenou bez zaznamu kot): zadne metriky ani kontroly
        for (const m of PORADI) ulozPng(sc.nazev, mod, JMENO[m], views[JMENO[m]]);
        continue;
      }
      over(`${sc.nazev} [${mod}]: vykresy odeslany a scena bez chyb`, posts.length >= 1 && chyby.length === 0 && PORADI.every(m => pv[m]), { posts: posts.length, chyby, pohledy: Object.keys(pv) });
      for (const m of PORADI) {
        if (!pv[m]) continue;
        const k = metriky(pv[m]);
        if (process.env.DUMP && process.env.DUMP.split(',').includes(JMENO[m])) pv[m].dims.forEach((d, i) => console.log(`      #${i} ${d.label.padEnd(9)} ${d.vertical ? 'svisle  ' : 'vodorovne'} strana ${d.side.padEnd(5)} k=${d.k} t=${d.t} cara [${d.q.map(x => Math.round(x)).join(',')}] popisek [${d.labelBox.map(x => Math.round(x)).join(',')}]`));
        vsechny[`${sc.nazev}|${mod}|${m}`] = k;
        console.log(`   ${sc.nazev.padEnd(16)} ${mod.padEnd(3)} ${JMENO[m].padEnd(8)} koty ${String(k.dim).padStart(2)} (vynechano duplicit ${k.skip}) | duplicity ${k.dup}, popisek x popisek ${k.labelLabel}, popisek x cara ${k.labelCara}, rovnobezne blizko ${k.rovnobezne}, mimo platno ${k.mimo}, krizeni car ${k.krizeni} | strany ${JSON.stringify(k.strany)}`);
        const nv = views[JMENO[m]];
        ulozPng(sc.nazev, mod, JMENO[m], nv);
      }
    }
  }
  await browser.close();
  if (MOD !== 'off') {
    for (const sc of SADA) {
      for (const m of PORADI) {
        const k = vsechny[`${sc.nazev}|on|${m}`];
        if (!k) continue;
        over(`${sc.nazev} ${JMENO[m]}: zapnute rozmistovani - zadna duplicita, zadny prekryv popisku, zadny popisek pres caru, zadne blizke rovnobezne cary, nic mimo platno`,
          k.dup === 0 && k.labelLabel === 0 && k.labelCara === 0 && k.rovnobezne === 0 && k.mimo === 0, k);
        const strany = Object.values(k.strany).filter(x => x > 0).length;
        if (k.dim >= 5) over(`${sc.nazev} ${JMENO[m]}: koty (${k.dim}) nejsou nacpane na jednu stranu - jsou na ${strany} ze 4 stran (volne misto se vyuziva)`, strany >= 3, k.strany);
        const o = vsechny[`${sc.nazev}|off|${m}`];
        if (o) over(`${sc.nazev} ${JMENO[m]}: zapnute rozmistovani neni horsi nez puvodni (mene nebo stejne problemu: ${o.dup + o.labelLabel + o.labelCara + o.rovnobezne + o.mimo} -> ${k.dup + k.labelLabel + k.labelCara + k.rovnobezne + k.mimo})`,
          k.dup + k.labelLabel + k.labelCara + k.rovnobezne + k.mimo <= o.dup + o.labelLabel + o.labelCara + o.rovnobezne + o.mimo, { off: o, on: k });
      }
    }
  }
  if (MOD === 'oba' && SADA.some(s => s.nazev === 'nabidka126')) {
    const pr = PORADI.map(m => vsechny[`nabidka126|off|${m}`]).filter(Boolean);
    over('nabidka126 (puvodni chovani): metriky zachyti problem, ktery videl Robert (duplicita, popisek pres caru, blizke rovnobezne cary)', pr.length === 3 && pr.every(k => k.dup >= 1 && k.rovnobezne >= 1) && pr.some(k => k.labelCara >= 1), pr);
  }
  const ok = vysl.filter(Boolean).length;
  console.log(`\nVYSLEDEK koty ve vykresech stolu: ${ok}/${vysl.length} OK`);
  process.exit(ok === vysl.length ? 0 : 1);
})().catch(e => { console.error('CHYBA TESTU', e); process.exit(2); });
