'use strict';
// Prostredi (HDRI) pro admina generatoru: viewer3d.js >= 1.9.0 (knihovna HDRI, setEnvConfig/getEnvConfig/resetEnvConfig, opts.envConfig) a panel env-picker.js;
// od 1.10.0 i brana HDRI (velke HDRI az po prvnim modelu, maly nahled *_256.hdr hned, opts.envEager, snapshot ceka na plne HDRI; sekce 9).
// Offline (SwiftShader). GLB=<libovolny platny model> (viz run_all.sh: syntetickeho kostka z scripts/2026-10-03_pripni_cokoli_testy/make_synth_glb.py).
const path = require('path'), fs = require('fs');
const { chromium } = require('/opt/konfigurator/node_modules/playwright');
const WEB = '/opt/konfigurator/webapp', NM = '/opt/konfigurator/node_modules/three/', ORIGIN = 'https://v3d.test';
const GLB = process.env.GLB;
if (!GLB) { console.error('nastav GLB=<model.glb>'); process.exit(2); }
const out = [];
const ok = (n, c, d) => { out.push(!!c); console.log((c ? 'OK   ' : 'FAIL ') + n + (d !== undefined ? '  ' + JSON.stringify(d).slice(0, 300) : '')); };
(async () => {
  const b = await chromium.launch({ args: ['--host-resolver-rules=MAP * ~NOTFOUND', '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  const ctx = await b.newContext({ viewport: { width: 900, height: 700 }, deviceScaleFactor: 1 });
  const ext = [], reqs = [], reqT = [], errs = [];
  const D = { glb: 0, hdr: 0, block256: false, block1024: false }, T = {};     // zpozdeni/blokace odpovedi pro sekci 9 (nastavuje test pres window.__setD)
  const sleepN = (ms) => new Promise((r) => setTimeout(r, ms));
  await ctx.route('**/*', async (route) => {
    const u = new URL(route.request().url());
    if (u.origin === 'https://cdn.jsdelivr.net') {
      const f = path.join(NM, u.pathname.replace('/npm/three@0.128.0/', ''));
      return fs.existsSync(f) ? route.fulfill({ contentType: 'application/javascript', body: fs.readFileSync(f) }) : route.fulfill({ status: 404, body: '' });
    }
    if (u.origin !== ORIGIN) { ext.push(u.href); return route.fulfill({ status: 404, body: '' }); }
    reqs.push(u.pathname); reqT.push([Date.now(), u.pathname]);
    if (u.pathname === '/') return route.fulfill({ contentType: 'text/html; charset=utf-8', body: '<!doctype html><meta charset=utf-8><link rel=stylesheet href=/css/v3d.css><style>html,body{margin:0;background:#111;color:#eee}#v{width:600px;height:420px}</style><div id=v></div><div id=p style="width:360px"></div><div id=v2 style="width:300px;height:200px"></div>' });
    if (u.pathname === '/m.glb') { if (D.glb) await sleepN(D.glb); T.glbDone = Date.now(); return route.fulfill({ contentType: 'model/gltf-binary', body: fs.readFileSync(GLB) }); }
    const m = /^\/(js\/v3d\/[A-Za-z0-9_.-]+\.js|js\/v3d\/env\/[A-Za-z0-9_.-]+\.hdr|css\/v3d\.css)$/.exec(u.pathname);
    if (m && /_256\.hdr$/.test(m[1]) && D.block256) return route.fulfill({ status: 404, body: '' });
    if (m && /_1024\.hdr$/.test(m[1])) { if (D.block1024) return route.fulfill({ status: 404, body: '' }); if (D.hdr) await sleepN(D.hdr); }
    if (m && fs.existsSync(path.join(WEB, m[1]))) return route.fulfill({ contentType: /\.js$/.test(m[1]) ? 'application/javascript' : (/\.css$/.test(m[1]) ? 'text/css' : 'application/octet-stream'), body: fs.readFileSync(path.join(WEB, m[1])) });
    return route.fulfill({ status: 404, body: '' });
  });
  const page = await ctx.newPage();
  await page.exposeFunction('__setD', (o) => { Object.assign(D, o); });
  page.on('pageerror', (e) => errs.push(String(e)));
  await page.goto(ORIGIN + '/');
  for (const u of ['build/three.min.js', 'examples/js/controls/OrbitControls.js', 'examples/js/loaders/GLTFLoader.js', 'examples/js/environments/RoomEnvironment.js', 'examples/js/renderers/CSS2DRenderer.js', 'examples/js/shaders/HorizontalBlurShader.js', 'examples/js/shaders/VerticalBlurShader.js'])
    await page.addScriptTag({ url: 'https://cdn.jsdelivr.net/npm/three@0.128.0/' + u });
  await page.addScriptTag({ url: ORIGIN + '/js/v3d/viewer3d.js' });
  await page.addScriptTag({ url: ORIGIN + '/js/v3d/env-picker.js' });
  const r = await page.evaluate(async () => {
    const sleep = (ms) => new Promise((res) => setTimeout(res, ms));
    const until = async (fn, ms = 30000) => { const t0 = performance.now(); while (performance.now() - t0 < ms) { if (fn()) return true; await sleep(100); } return false; };
    const res = {};
    res.version = window.V3D.version; res.lib = window.V3D.envLibrary.map((h) => h.key);
    const v = window.V3D.mount(document.getElementById('v'), { modelUrl: '/m.glb', mode: 'real', allowReal: true, hudKoty: false, dims: 0 });
    window.v = v; await v.ready;
    await until(() => v.debug.state().envHdriLoaded);
    res.def = v.getEnvConfig(); res.defEnv = v.debug.state().env; const i0 = v.debug.envInfo(); res.i0 = i0;
    // 2) vyber jineho HDRI + sila
    res.set1 = v.setEnvConfig({ hdri: 'berg_inner', strength: 1, rot_deg: 30, hemi: 0.2 });
    await until(() => v.debug.envInfo().texId !== i0.texId);
    const i1 = v.debug.envInfo(); res.i1 = i1; res.st1 = v.debug.state().env; res.cfg1 = v.getEnvConfig();
    v.setEnvConfig({ hdri: 'berg_inner', strength: 2, rot_deg: 30, hemi: 0.2 }); await sleep(300);
    const i2 = v.debug.envInfo(); res.ratio = i2.matIntensity / i1.matIntensity; res.sameTex = i2.texId === i1.texId;
    // 3) natoceni = nova textura, v pameti nejvyse 3-4
    for (const deg of [40, 80, 120, 160, -100, -50]) { v.setEnvConfig({ hdri: 'berg_inner', strength: 1, rot_deg: deg, hemi: 0.2 }); await sleep(450); }
    res.cached = v.debug.envInfo().cached;
    // 4) kontrola vstupu
    res.bad = v.setEnvConfig({ hdri: 'neexistuje' }); res.envAfterBad = v.debug.state().env;
    res.clamp = v.setEnvConfig({ hdri: 'tv_studio', strength: 99, rot_deg: 540, hemi: -4 });
    res.nan = v.setEnvConfig({ hdri: 'crossfit', strength: 'abc', rot_deg: null, hemi: undefined });
    // 5) mistnost (bez HDRI)
    v.setEnvConfig({ hdri: 'mistnost', strength: 1, hemi: 0.6 }); await sleep(300); res.room = v.debug.envInfo();
    // 6) reset
    res.reset = v.resetEnvConfig(); await sleep(300); res.afterReset = { env: v.debug.state().env, cfg: v.getEnvConfig() };
    // 7) opts.envConfig pri mountu
    const v2 = window.V3D.mount(document.getElementById('v2'), { modelUrl: '/m.glb', mode: 'real', allowReal: true, hudKoty: false, dims: 0, envConfig: { hdri: 'tv_studio', strength: 1.5, rot_deg: 10, hemi: 0 } });
    await v2.ready; await until(() => v2.debug.state().envHdriLoaded);
    res.init = { env: v2.debug.state().env, cfg: v2.getEnvConfig() }; v2.dispose();
    return res;
  });
  ok('verze vieweru 1.10.0 a knihovna HDRI (crossfit, tv_studio, berg_inner, teufelsberg, mistnost)', r.version === '1.10.0' && JSON.stringify(r.lib) === JSON.stringify(['crossfit', 'tv_studio', 'berg_inner', 'teufelsberg', 'mistnost']), [r.version, r.lib]);
  ok('vychozi prostredi beze zmeny: hdri_tlumene = {crossfit, sila 0,6, natoceni 0, svetlo shora 0}', r.defEnv === 'hdri_tlumene' && JSON.stringify(r.def) === JSON.stringify({ hdri: 'crossfit', strength: 0.6, rot_deg: 0, hemi: 0 }) && r.i0.hemi === 0, [r.defEnv, r.def]);
  ok('setEnvConfig: vrati normalizovanou konfiguraci, stav env = custom, nactene HDRI berg_inner (nova textura prostredi)', r.set1 && r.set1.hdri === 'berg_inner' && r.st1 === 'custom' && r.cfg1.rot_deg === 30 && r.i1.texId !== r.i0.texId && r.i1.hemi === 0.2, [r.set1, r.st1]);
  ok('sila svetla: dvojnasobna sila = dvojnasobny envMapIntensity materialu a stejna textura (bez noveho nacitani)', Math.abs(r.ratio - 2) < 0.01 && r.sameTex, [r.ratio, r.sameTex]);
  ok('pri otaceni se v pameti drzi nejvyse 4 prostredi (GPU pamet)', r.cached <= 4 && r.cached >= 1, r.cached);
  ok('neznamy hdri se odmitne (false) a prostredi se nezmeni', r.bad === false && r.envAfterBad === 'custom', [r.bad, r.envAfterBad]);
  ok('mezni hodnoty se ořežou: sila 99 -> 3, natoceni 540 -> -180, svetlo shora -4 -> 0; nesmysl -> vychozi hodnoty', r.clamp.strength === 3 && r.clamp.rot_deg === -180 && r.clamp.hemi === 0 && r.nan.strength === 0.6 && r.nan.rot_deg === 0 && r.nan.hemi === 0, [r.clamp, r.nan]);
  ok('mistnost (bez HDRI): prostredi je a svetlo shora 0,6', r.room.hasEnv && Math.abs(r.room.hemi - 0.6) < 1e-6, r.room);
  ok('resetEnvConfig vrati vychozi hdri_tlumene', r.reset === true && r.afterReset.env === 'hdri_tlumene' && r.afterReset.cfg.hdri === 'crossfit' && r.afterReset.cfg.strength === 0.6, r.afterReset);
  ok('opts.envConfig pri mountu: prostredi tv_studio, sila 1,5, natoceni 10 a nacte se tv_studio_1024.hdr', r.init.env === 'custom' && r.init.cfg.hdri === 'tv_studio' && r.init.cfg.strength === 1.5 && r.init.cfg.rot_deg === 10 && reqs.some((p) => /tv_studio_1024\.hdr$/.test(p)), [r.init, reqs.filter((p) => /\.hdr$/.test(p))]);

  // 7b) zmena prostredi se musi PREKRESLIT (kick() bez dirty by nechal stary snimek): dva ruzne HDRI = ruzne obrazky platna
  const sha = (b) => require('crypto').createHash('sha1').update(b).digest('hex');
  await page.evaluate(async () => { window.v.setEnvConfig({ hdri: 'crossfit', strength: 1, rot_deg: 0, hemi: 0 }); await new Promise((r) => setTimeout(r, 2500)); });
  const shotA = sha(await page.locator('#v').screenshot());
  await page.evaluate(async () => { window.v.setEnvConfig({ hdri: 'tv_studio', strength: 1, rot_deg: 0, hemi: 0 }); await new Promise((r) => setTimeout(r, 2500)); });
  const shotB = sha(await page.locator('#v').screenshot());
  await page.evaluate(async () => { window.v.setEnvConfig({ hdri: 'tv_studio', strength: 2.5, rot_deg: 0, hemi: 0 }); await new Promise((r) => setTimeout(r, 1500)); });
  const shotC = sha(await page.locator('#v').screenshot());
  ok('zmena HDRI i sily se projevi na platne (obrazek se prekresli, tri ruzne snimky)', shotA !== shotB && shotB !== shotC && shotA !== shotC, [shotA.slice(0, 8), shotB.slice(0, 8), shotC.slice(0, 8)]);
  // 8) panel env-picker
  const rp = await page.evaluate(async () => {
    const sleep = (ms) => new Promise((res) => setTimeout(res, ms));
    const v = window.v; v.resetEnvConfig();
    const calls = []; let mode = 'ok';
    const panel = window.V3D.envPicker(v, document.getElementById('p'), { saved: null, onSave: (cfg) => { calls.push(cfg); return mode === 'ok' ? Promise.resolve({ ok: true, status: 200 }) : Promise.reject(new Error('sit')); } });
    const root = document.querySelector('.v3d-envp'); const $ = (s) => root.querySelector(s);
    const o = {};
    o.options = [...root.querySelectorAll('select option')].map((x) => x.value);
    o.initSel = root.querySelector('select').value;
    // vyber HDRI + natoceni
    const sel = root.querySelector('select'); sel.value = 'tv_studio'; sel.dispatchEvent(new Event('change', { bubbles: true })); await sleep(250);
    o.afterSel = v.getEnvConfig();
    const rot = root.querySelector('input[id$=r]'); rot.value = '45'; rot.dispatchEvent(new Event('input', { bubbles: true })); await sleep(500);
    o.afterRot = v.getEnvConfig(); o.statusUnsaved = $('.st').textContent;
    // ulozit
    root.querySelector('[data-a=save]').click(); await sleep(300);
    o.saveCall = calls[0]; o.statusSaved = $('.st').textContent; o.saveDisabled = root.querySelector('[data-a=save]').disabled;
    // zmenit a obnovit ulozene
    sel.value = 'teufelsberg'; sel.dispatchEvent(new Event('change', { bubbles: true })); await sleep(250);
    root.querySelector('[data-a=revert]').click(); await sleep(300);
    o.afterRevert = v.getEnvConfig();
    // vychozi a ulozit = null (smazat ulozene)
    root.querySelector('[data-a=factory]').click(); await sleep(250);
    o.afterFactory = v.getEnvConfig();
    root.querySelector('[data-a=save]').click(); await sleep(300);
    o.saveFactoryCall = calls[1] === null;
    // chyba ulozeni
    mode = 'fail'; sel.value = 'berg_inner'; sel.dispatchEvent(new Event('change', { bubbles: true })); await sleep(250);
    root.querySelector('[data-a=save]').click(); await sleep(300);
    o.statusFail = $('.st').textContent; o.failBtn = root.querySelector('[data-a=save]').disabled;
    panel.destroy(); o.gone = !document.querySelector('.v3d-envp');
    return o;
  });
  ok('panel: 5 voleb HDRI (vc. Mistnost), po vytvoreni ukazuje dnesni vychozi (crossfit)', JSON.stringify(rp.options) === JSON.stringify(['crossfit', 'tv_studio', 'berg_inner', 'teufelsberg', 'mistnost']) && rp.initSel === 'crossfit', [rp.options, rp.initSel]);
  ok('panel: vyber HDRI a posuvnik natoceni meni prostredi ve vieweru zive, stav "neulozeno"', rp.afterSel.hdri === 'tv_studio' && rp.afterRot.hdri === 'tv_studio' && rp.afterRot.rot_deg === 45 && /neuloženo/.test(rp.statusUnsaved), [rp.afterSel, rp.afterRot, rp.statusUnsaved]);
  ok('panel: tlacitko Ulozit pro vsechny zavola onSave s konfiguraci (tv_studio, natoceni 45) a ohlasi ulozeno', rp.saveCall && rp.saveCall.hdri === 'tv_studio' && rp.saveCall.rot_deg === 45 && /Uloženo/.test(rp.statusSaved) && rp.saveDisabled === false, [rp.saveCall, rp.statusSaved]);
  ok('panel: Obnovit ulozene vrati nahled na ulozenou konfiguraci', rp.afterRevert.hdri === 'tv_studio' && rp.afterRevert.rot_deg === 45, rp.afterRevert);
  ok('panel: Vychozi nastavi tovarni (crossfit, 0,6) a jeho ulozeni posle onSave(null) = smazat ulozene', rp.afterFactory.hdri === 'crossfit' && rp.afterFactory.strength === 0.6 && rp.saveFactoryCall === true, [rp.afterFactory, rp.saveFactoryCall]);
  ok('panel: pri chybe ulozeni hlasi "Ulozeni se nepovedlo" a tlacitko se znovu odemkne; destroy() panel odstrani', /nepovedlo/.test(rp.statusFail) && rp.failBtn === false && rp.gone, [rp.statusFail, rp.failBtn, rp.gone]);

  // 9) viewer 1.10.0: velke HDRI az po prvnim modelu, maly nahled (*_256.hdr) hned; opts.envEager = stare chovani; explicitni zmena prostredi a snapshot() HDRI pousti hned
  const hdrFrom = (from) => reqs.slice(from).filter((q) => /\.hdr$/.test(q)).map((q) => q.replace(/^.*\//, ''));
  await page.evaluate(() => {
    window.__mk = (id, extra) => { const d = document.createElement('div'); d.id = id; d.style.cssText = 'width:300px;height:200px'; document.body.appendChild(d); window.__mkN = (window.__mkN || 0) + 1; const v = window.V3D.mount(d, Object.assign({ modelUrl: '/m.glb?n=' + window.__mkN, mode: 'real', allowReal: true, hudKoty: false, dims: 0 }, extra || {})); window[id] = v; return v; };     // ?n=: jedinecna adresa, aby prohlizec nevzal model z mezipameti (zpozdeni route by se neuplatnilo)
    window.__until = async (fn, ms) => { const t0 = performance.now(); while (performance.now() - t0 < (ms || 30000)) { if (fn()) return true; await new Promise((r) => setTimeout(r, 100)); } return false; };
  });
  // 9a) brana: pred modelem jen nahled, plne HDRI AZ po jeho dodani
  D.glb = 6000; let i9 = reqs.length;
  await page.evaluate(() => { window.__mk('g1'); });
  const seedBefore = await page.evaluate(async () => { const ok = await window.__until(() => window.g1.debug.envInfo().seed, 4500); const e = window.g1.debug.envInfo(); return { seedApplied: ok, gate: e.gate, ready: window.g1.debug.state().ready }; });
  const a1 = hdrFrom(i9);
  ok('brana HDRI: pred prvnim modelem se stahuje jen nahled (crossfit_256.hdr), plne HDRI ne; nahled osvetluje scenu', a1.includes('crossfit_256.hdr') && !a1.includes('crossfit_1024.hdr') && seedBefore.seedApplied && seedBefore.gate === false && seedBefore.ready === false, [a1, seedBefore]);
  const fin1 = await page.evaluate(async () => { await window.g1.ready; await window.__until(() => window.g1.debug.state().envHdriLoaded, 30000); await new Promise((r) => setTimeout(r, 300)); const e = window.g1.debug.envInfo(); return { gate: e.gate, seed: e.seed, full: window.g1.debug.state().envHdriLoaded, seedFlag: window.g1.debug.state().envSeed, cached: e.cached }; });
  const t1024 = (reqT.slice(i9).find((x) => /crossfit_1024\.hdr$/.test(x[1])) || [0])[0];
  ok('brana HDRI: plne HDRI se zacne stahovat AZ po dodani modelu a nahradi nahled (nahled se uvolni)', t1024 >= T.glbDone && fin1.gate && fin1.full && !fin1.seed && !fin1.seedFlag && fin1.cached === 1, [t1024 - T.glbDone, fin1]);
  await page.evaluate(() => { window.g1.dispose(); document.getElementById('g1').remove(); });
  // 9b) opts.envEager: plne HDRI hned (jako do 1.9.0), bez nahledu
  D.glb = 4000; i9 = reqs.length;
  await page.evaluate(() => { window.__mk('g2', { envEager: true }); });
  await sleepN(900);
  const a2 = hdrFrom(i9);
  ok('opts.envEager: plne HDRI se stahuje hned pri mountu (model jeste neprisel), nahled se nestahuje', a2.includes('crossfit_1024.hdr') && !a2.includes('crossfit_256.hdr') && !(await page.evaluate(() => window.g2.debug.state().ready)), a2);
  await page.evaluate(() => { window.g2.dispose(); document.getElementById('g2').remove(); });
  // 9c) explicitni zmena prostredi pred modelem pusti plne HDRI hned (bez nahledu)
  D.glb = 5000; i9 = reqs.length;
  await page.evaluate(() => { window.__mk('g3'); });
  await sleepN(400);
  await page.evaluate(() => { window.g3.setEnvConfig({ hdri: 'berg_inner', strength: 1, rot_deg: 0, hemi: 0 }); });
  await sleepN(1200);
  const a3 = hdrFrom(i9); const rd3 = await page.evaluate(() => window.g3.debug.state().ready);
  ok('explicitni setEnvConfig pred modelem: plne HDRI se stahuje hned (berg_inner_1024.hdr), model jeste neprisel', a3.includes('berg_inner_1024.hdr') && !a3.includes('crossfit_1024.hdr') && !rd3, { a3, rd3, t: reqT.slice(i9).filter((x) => /hdr|m\.glb/.test(x[1])).map((x) => [x[1].replace(/^.*\//, ''), x[0] - reqT[i9][0]]), glbDoneRel: T.glbDone - reqT[i9][0] });
  await page.evaluate(() => { window.g3.dispose(); document.getElementById('g3').remove(); });
  // 9d) snapshot() pocka na plne HDRI (omezene na 4 s) - snimek je v plne kvalite: v okamziku cteni platna (toDataURL) je plne HDRI uz pouzite a nahled uvolnen.
  // Zahrati (jine viewery uz bezely): shadery pod SwiftShaderem se poprve prekladaji sekundy a blokuji vlakno, mereni by pak nebylo stabilni.
  D.glb = 0; D.hdr = 0;
  await page.evaluate(async () => { const w = window.__mk('gw'); await w.ready; await window.__until(() => w.debug.state().envHdriLoaded, 40000); await w.snapshot({ width: 60 }); w.dispose(); document.getElementById('gw').remove(); });
  D.hdr = 600;
  const snap = await page.evaluate(async () => {
    const v = window.__mk('g4'); await v.ready; const t0 = performance.now();
    const seedBefore = v.debug.envInfo().seed || !v.debug.state().envHdriLoaded;
    const proto = HTMLCanvasElement.prototype, orig = proto.toDataURL; let atRead = null;
    proto.toDataURL = function () { if (this === v.debug.canvas || this.width === 300 || true) { if (!atRead) atRead = { seed: v.debug.envInfo().seed, full: v.debug.state().envHdriLoaded, t: Math.round(performance.now() - t0) }; } return orig.apply(this, arguments); };
    let png; try { png = await v.snapshot({ width: 120 }); } finally { proto.toDataURL = orig; }
    const r = { tSnap: Math.round(performance.now() - t0), atRead, png: typeof png === 'string' && png.indexOf('data:image/png') === 0, seedBefore };
    v.dispose(); document.getElementById('g4').remove(); return r;
  });
  D.hdr = 0;
  ok('snapshot(): pocka na plne HDRI (pri zavolani jeste nebylo) - pri cteni platna je plne HDRI pouzite a nahled uvolnen', snap.png && snap.seedBefore && snap.atRead && snap.atRead.full && !snap.atRead.seed && snap.tSnap > 500, snap);
  // 9e) chybi nahled (404): plne HDRI po modelu presto prijde, bez varovani
  D.block256 = true;
  const miss = await page.evaluate(async () => { const v = window.__mk('g5'); await v.ready; await window.__until(() => v.debug.state().envHdriLoaded, 30000); const st = v.debug.state(); const r = { full: st.envHdriLoaded, env: st.env, warn: (st.warnings || []).filter((w) => /HDRI/.test(w)).length }; v.dispose(); document.getElementById('g5').remove(); return r; });
  D.block256 = false;
  ok('chybejici nahled (404): plne HDRI po modelu prijde, prostredi zustane hdri_tlumene a bez varovani', miss.full && miss.env === 'hdri_tlumene' && miss.warn === 0, miss);
  // 9f) plne HDRI se nenacte (404): zaloha 'mistnost' a varovani jako dosud
  D.block1024 = true;
  const fail = await page.evaluate(async () => { const v = window.__mk('g6'); await v.ready; await window.__until(() => v.debug.state().env === 'mistnost', 20000); const st = v.debug.state(); const r = { env: st.env, warn: (st.warnings || []).filter((w) => /HDRI/.test(w)).length, hasEnv: v.debug.envInfo().hasEnv }; v.dispose(); document.getElementById('g6').remove(); return r; });
  D.block1024 = false;
  ok('plne HDRI se nenacte: zaloha mistnost + varovani v state().warnings (chovani jako dosud)', fail.env === 'mistnost' && fail.warn === 1 && fail.hasEnv, fail);
  // 9g) dispose pred prvnim modelem: zadne plne HDRI, zadna chyba (casovac brany se zrusi)
  D.glb = 3000; i9 = reqs.length; const errs0 = errs.length;
  await page.evaluate(() => { const v = window.__mk('g7'); setTimeout(() => { v.dispose(); document.getElementById('g7').remove(); }, 300); });
  await sleepN(3800);
  const a7 = hdrFrom(i9);
  ok('dispose pred prvnim modelem: plne HDRI se nestahuje a nevznikne chyba', !a7.includes('crossfit_1024.hdr') && errs.length === errs0, [a7, errs.slice(errs0)]);
  // 9h) pojistka: model nedorazil -> po 12 s (zde zkraceno na 0,5 s) se plne HDRI stejne pusti
  await page.evaluate(() => { const o = window.setTimeout; window.__stOrig = o; window.setTimeout = function (fn, ms) { return o.call(window, fn, ms === 12000 ? 500 : ms); }; });
  D.glb = 7000; i9 = reqs.length;
  await page.evaluate(() => { window.__mk('g8'); });
  await sleepN(2200);
  const a8 = hdrFrom(i9); const rd8 = await page.evaluate(() => window.g8.debug.state().ready);
  await page.evaluate(() => { window.setTimeout = window.__stOrig; window.g8.dispose(); document.getElementById('g8').remove(); });
  ok('pojistka: model nedorazil -> plne HDRI se po limitu stejne pusti (limit 12 s, v testu 0,5 s)', a8.includes('crossfit_1024.hdr') && rd8 === false, [a8, rd8]);
  D.glb = 0;

  const allowed = /^\/(js\/v3d\/(viewer3d|env-picker)\.js|js\/v3d\/env\/(crossfit|tv_studio|berg_inner|teufelsberg)_(1024|256)\.hdr|css\/v3d\.css|m\.glb|)$/;
  const bad = [...new Set(reqs.filter((p) => !allowed.test(p)))];
  ok('jen povolene cesty (viewer, panel, 4 HDRI soubory + jejich nahledy, css, model); zadne pozadavky ven a bez neodchycenych chyb', bad.length === 0 && ext.length === 0 && errs.length === 0, { bad, ext, errs: errs.slice(0, 3) });
  await b.close();
  process.exit(out.every(Boolean) ? 0 : 1);
})().catch((e) => { console.error('CHYBA', e); process.exit(2); });
