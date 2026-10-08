// Vandr model jako REFERENCNI objekt v hlavni Scene v karoserii z knihovny (bot8, 2026-10-07; webapp/js/scene/vandr-ref.js).
// SKUTECNA scena (scene.html) v Chromiu pres most k Flasku (scripts/2026-10-06_nabidka_vykresy_testy/_most_scena.py: DB jen cte, zapisy se nepredavaji, chraneny Vandr GLB vydava most primo ze souboru).
// Overuje: ?vandr=4967&karoserie=K-227 vlozi karoserii MAN L3H3 + cely levy Vandr regal; zarovnani (otoceni o 180 st. kolem Y, podlaha, prepazka) a NEZAVISLE fyzikalni kontrola
// paprsky ve scene (regal 0-6 mm nad podlahou, od prepazky ~271 mm, od leve steny malo); regal je "kontrolni pomucka" (mimo ulozeni, kusovnik); pomocne uzly Vandr exportu pryc;
// barvy z GLB; posun a otoceni tlacitky; odebrani; vlozeni dalsi karty z panelu (bez ?vandr=); chyby (neexistujici karta, neznama karoserie); scena po F5 obnovuje jen to, co adresa vklada.
// Spusteni:  WEB_DIR=<kandidat statiky> systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --setenv=HOME=/root --setenv=WEB_DIR=... --working-directory=/opt/konfigurator \
//            api/venv/bin/python3 scripts/2026-10-06_nabidka_vykresy_testy/_most_scena.py scripts/2026-10-07_vandr_ref_testy/test_vandr_ref.js
const { chromium } = require('/opt/konfigurator/node_modules/playwright-core');
const BASE = process.env.BASE;
const KARTA = 4967, KAROSERIE = 'K-227';
const vysl = [];
const over = (nazev, podminka, detail) => { vysl.push(!!podminka); console.log((podminka ? 'OK   ' : 'FAIL ') + nazev + (podminka ? '' : '  -> ' + JSON.stringify(detail).slice(0, 500))); };
const blizko = (a, b, tol) => Math.abs(a - b) <= tol;

async function otevri(search) {
  const browser = await chromium.launch({ args: ['--no-sandbox', '--use-gl=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  const page = await browser.newPage({ viewport: { width: 1500, height: 900 } });
  const chyby = [], http = [];
  await page.addInitScript(() => { try { localStorage.setItem('konfHelpSeen', '1'); } catch (e) { /* ignoruj */ } });   // uvodni napoveda by prekryla tlacitka
  page.on('pageerror', e => chyby.push(e.message.slice(0, 200)));
  page.on('response', r => { if (r.status() >= 400) http.push(r.status() + ' ' + r.url().replace(BASE, '').slice(0, 90)); });
  await page.goto(BASE + '/scene.html' + search);
  return { browser, page, chyby, http };
}
const stav = page => page.evaluate(() => { const e = document.getElementById('vandrRefStatus'); return e ? e.textContent : null; });
const pockejStav = (page, re, ms = 150000) => page.waitForFunction(r => { const e = document.getElementById('vandrRefStatus'); return e && new RegExp(r).test(e.textContent); }, re.source, { timeout: ms });

// merene ve scene: kde stoji regal vuci karoserii (paprsky), kolik je pomocnych uzlu, barev, zda je pomucka
const MERENI = () => {
  const e = placed.find(x => x.part && x.part.id === 'vandr_4967');
  const body = [];
  placed.forEach(x => { if (isCarBodyPart(x)) x.object3d.traverse(n => { if (n.isMesh) body.push(n); }); });
  scene.updateMatrixWorld(true);
  const out = { jeRegal: !!e, telo: placed.filter(x => isCarBodyPart(x)).length };
  if (!e) return out;
  const o = e.object3d;
  out.poz = o.position.toArray().map(v => Math.round(v * 10) / 10);
  out.quat = o.quaternion.toArray().map(v => Math.round(v * 1000) / 1000);
  out.role = e.role; out.pomucka = isKontrolniPart(e);
  const box = new THREE.Box3().setFromObject(o);
  out.box = { min: box.min.toArray().map(Math.round), max: box.max.toArray().map(Math.round) };
  let meshu = 0, pomocnych = 0; const barvy = new Set();
  o.traverse(n => { if (!n.isMesh) return; meshu++; const seg = []; for (let p = n; p; p = p.parent) if (p.name) seg.push(p.name); if (seg.some(s => /^(podlaha|karoserie|dimension|fixarea|legshoverbox|logo|text)/i.test(s))) pomocnych++; barvy.add(n.material && n.material.color ? n.material.color.getHexString() : '?'); });
  out.meshu = meshu; out.pomocnych = pomocnych; out.barev = barvy.size;
  // fyzikalni kontrola paprsky: vzdalenost od regalu k podlaze, k prepazce a k leve strane
  const rc = new THREE.Raycaster();
  const dist = (orig, dir) => { rc.set(new THREE.Vector3(...orig), new THREE.Vector3(...dir)); rc.far = 4000; const h = rc.intersectObjects(body, false)[0]; return h ? Math.round(h.distance * 10) / 10 : null; };
  const cx = (box.min.x + box.max.x) / 2, cy = box.min.y + 700, cz = (box.min.z + box.max.z) / 2;
  out.dPodlaha = dist([cx, box.min.y + 30, cz], [0, -1, 0]);        // paprsek dolu z 30 mm nad nejnizsim bodem regalu -> vzdalenost k podlaze
  out.dPrepazka = dist([cx, cy, box.min.z], [0, 0, -1]);          // od celniho okraje regalu k prepazce
  out.dLevaSt = dist([box.min.x, cy, cz], [-1, 0, 0]);              // od krajniho bodu k leve strane (x zaporne)
  out.dPravaSt = dist([box.max.x, cy, cz], [1, 0, 0]);
  return out;
};

(async () => {
  let { browser, page, chyby, http } = await otevri(`?vandr=${KARTA}&karoserie=${KAROSERIE}`);
  await pockejStav(page, /Hotovo|nepodařilo/);
  const st = await stav(page);
  over('V1 vlozeni hotovo: stav "Hotovo: karta #4967 v karoserii K-227 ..."', /^Hotovo: karta #4967 v karoserii K-227/.test(st || ''), st);
  const m = await page.evaluate(MERENI);
  over('V2 ve scene je karoserie (3 dily L+R_D+B) a prave jeden Vandr regal', m.telo === 3 && m.jeRegal, m);
  over('V3 regal je "kontrolni pomucka" (role kontrolni-pomucka-vandr-4967, isKontrolniPart)', m.pomucka === true && /^kontrolni-pomucka-vandr-4967$/.test(m.role || ''), { role: m.role, pomucka: m.pomucka });
  over('V4 zarovnani: otoceni o 180 st. kolem Y (quat 0,1,0,0) a posun (0, -313, -1456) +-30 mm (podlaha y=0, prepazka z=-3160 v K-227)', m.quat && blizko(Math.abs(m.quat[1]), 1, 0.01) && blizko(m.poz[0], 0, 1) && blizko(m.poz[1], -313, 30) && blizko(m.poz[2], -1456, 45), { poz: m.poz, quat: m.quat });
  over('V5 NEZAVISLE paprsky ve scene: regal stoji na podlaze (nejnizsi bod 0-8 mm nad ni), od prepazky 230-320 mm, od leve steny 0-60 mm, vpravo volno', m.dPodlaha != null && m.dPodlaha - 30 >= -1 && m.dPodlaha - 30 <= 8 && m.dPrepazka >= 230 && m.dPrepazka <= 320 && m.dLevaSt != null && m.dLevaSt >= 0 && m.dLevaSt <= 60 && (m.dPravaSt == null || m.dPravaSt > 600), { dPodlaha: m.dPodlaha, dPrepazka: m.dPrepazka, dLevaSt: m.dLevaSt, dPravaSt: m.dPravaSt, box: m.box });
  over('V6 pomocne uzly Vandr exportu (podlaha, dimension, fixarea, legshoverbox, logo, text) jsou pryc; zbyva stovky meshu a vic barev (ne jedna barva vrstvy)', m.pomocnych === 0 && m.meshu >= 380 && m.barev >= 3, { meshu: m.meshu, pomocnych: m.pomocnych, barev: m.barev });
  const excl = await page.evaluate(() => {
    const e = placed.find(x => x.part && x.part.id === 'vandr_4967');
    selectedMoveEntries.add(e);
    const ulozeni = collectSelectedEntriesForSave().includes(e);
    selectedMoveEntries.delete(e);
    return { ulozeni, urlParams: location.search };
  });
  over('V7 regal se NEDOSTANE do ulozeni (collectSelectedEntriesForSave ho vyrazuje)', excl.ulozeni === false, excl);
  over('V8 adresa nese ?vandr=4967&karoserie=K-227 (F5 vlozi totez)', /vandr=4967/.test(excl.urlParams) && /karoserie=K-227/.test(excl.urlParams), excl.urlParams);
  over('V9 bez chyb ve strance a bez neuspesnych pozadavku', chyby.length === 0 && http.length === 0, { chyby: chyby.slice(0, 3), http: http.slice(0, 5) });

  // tlacitka posunu / otoceni / vychozi zarovnani / odebrani
  over('V9c v panelu je predvolena karoserie K-227 a cislo karty', await page.evaluate(() => document.getElementById('vandrRefKaroserie').value === 'K-227' && document.getElementById('vandrRefKarta').value === '4967'), await page.evaluate(() => [document.getElementById('vandrRefKaroserie').value, document.getElementById('vandrRefKarta').value]));
  over('V9b z odkazu se panel Vandr model otevre sam (posun je hned po ruce)', await page.evaluate(() => { const w = document.getElementById('fwVandrRefWindow'); return !!w && getComputedStyle(w).display !== 'none'; }), null);
  const pred = await page.evaluate(() => { const e = placed.find(x => x.part.id === 'vandr_4967'); return e.object3d.position.toArray(); });
  await page.click('.vandr-ref-nudge[data-osa="x"][data-v="10"]');
  await page.click('.vandr-ref-nudge[data-osa="z"][data-v="-50"]');
  await page.click('.vandr-ref-nudge[data-osa="y"][data-v="1"]');
  const po = await page.evaluate(() => { const e = placed.find(x => x.part.id === 'vandr_4967'); return e.object3d.position.toArray(); });
  over('V10 tlacitka posunu: X +10, Z -50, Y +1 mm', blizko(po[0] - pred[0], 10, 0.01) && blizko(po[2] - pred[2], -50, 0.01) && blizko(po[1] - pred[1], 1, 0.01), { pred, po });
  await page.click('.vandr-ref-rot[data-v="180"]');
  const rot = await page.evaluate(() => { const e = placed.find(x => x.part.id === 'vandr_4967'); const q = e.object3d.quaternion; return [q.x, q.y, q.z, q.w].map(v => Math.round(v * 1000) / 1000); });
  over('V11 otoceni o 180 st.: model je ted v puvodni (Vandr) orientaci (quat ~ 0,0,0,+-1)', blizko(Math.abs(rot[3]), 1, 0.01) && blizko(rot[1], 0, 0.01), rot);
  await page.click('#vandrRefZpet');
  const zpet = await page.evaluate(() => { const e = placed.find(x => x.part.id === 'vandr_4967'); return { p: e.object3d.position.toArray().map(Math.round), q: e.object3d.quaternion.toArray().map(v => Math.round(v * 1000) / 1000) }; });
  over('V12 "Vychozi zarovnani" vrati puvodni polohu a otoceni', blizko(zpet.p[1], -313, 30) && blizko(Math.abs(zpet.q[1]), 1, 0.01), zpet);
  await page.click('#vandrRefOdeber');
  const odebrano = await page.evaluate(() => ({ regal: placed.some(x => x.part && x.part.id === 'vandr_4967'), telo: placed.filter(x => isCarBodyPart(x)).length }));
  over('V13 "Odebrat model" odebere regal, karoserie zustane', odebrano.regal === false && odebrano.telo === 3, odebrano);

  // druha karta (pravy regal #4968) z panelu - karoserie uz ve scene je
  await page.fill('#vandrRefKarta', '4968');
  await page.click('#vandrRefVloz');
  await pockejStav(page, /Hotovo: karta #4968|nepodařilo/);
  const m2 = await page.evaluate(() => { const e = placed.find(x => x.part && x.part.id === 'vandr_4968'); if (!e) return null; const b = new THREE.Box3().setFromObject(e.object3d); return { poz: e.object3d.position.toArray().map(v => Math.round(v)), min: b.min.toArray().map(Math.round), max: b.max.toArray().map(Math.round), telo: placed.filter(x => isCarBodyPart(x)).length }; });
  over('V14 pravy regal #4968 z panelu (karoserie uz ve scene, nevklada se znovu): ve scene je, vpravo (x>0), 3 dily karoserie', m2 && m2.telo === 3 && m2.max[0] > 300 && m2.min[0] > -120, m2);

  // ponk na prepazku (#4969, GLB bez plechu podlaha): nejnizsi bod na podlaze, zada u prepazky, vystredeno
  await page.fill('#vandrRefKarta', '4969');
  await page.click('#vandrRefVloz');
  await pockejStav(page, /Hotovo: karta #4969|nepodařilo/);
  const m3 = await page.evaluate(() => {
    const e = placed.find(x => x.part && x.part.id === 'vandr_4969'); if (!e) return null;
    const body = []; placed.forEach(x => { if (isCarBodyPart(x)) x.object3d.traverse(n => { if (n.isMesh) body.push(n); }); });
    scene.updateMatrixWorld(true);
    const b = new THREE.Box3().setFromObject(e.object3d), rc = new THREE.Raycaster();
    rc.set(new THREE.Vector3((b.min.x + b.max.x) / 2, b.min.y + 700, b.min.z), new THREE.Vector3(0, 0, -1)); rc.far = 4000;
    const h = rc.intersectObjects(body, false)[0];
    return { min: b.min.toArray().map(Math.round), max: b.max.toArray().map(Math.round), stredX: Math.round((b.min.x + b.max.x) / 2), dPrepazka: h ? Math.round(h.distance) : null, pomucka: isKontrolniPart(e) };
  });
  over('V14b ponk #4969 (bez plechu podlaha): nejnizsi bod 0-3 mm nad podlahou, zada 0-12 mm od prepazky, vystredeny v ose vozu (+-20 mm), jako pomucka', m3 && m3.min[1] >= -1 && m3.min[1] <= 3 && m3.dPrepazka != null && m3.dPrepazka >= 0 && m3.dPrepazka <= 12 && Math.abs(m3.stredX) <= 20 && m3.pomucka === true, m3);

  // chyby
  const chyba1 = await page.evaluate(async () => { const ok = await VandrRef.vloz(99999999, 'K-227'); return { ok, st: document.getElementById('vandrRefStatus').textContent }; });
  over('V15 neexistujici karta: srozumitelna chyba, nic se nevlozi', chyba1.ok === false && /nepodařilo vložit/.test(chyba1.st) && /99999999|neexistuje/.test(chyba1.st), chyba1);
  await browser.close();

  // F5 / cista scena: bez karoserie a bez ?karoserie => chyba, ne tichy neuspech; znama karta bez karoserie v knihovne
  ({ browser, page, chyby, http } = await otevri(`?vandr=${KARTA}&karoserie=K-9999`));
  await pockejStav(page, /Hotovo|nepodařilo/);
  const s3 = await stav(page);
  over('V16 neznama karoserie K-9999: chyba "není v knihovně", ve scene nic nepribylo', /není v knihovně/.test(s3 || '') && (await page.evaluate(() => placed.length)) === 0, s3);
  await browser.close();

  const ok = vysl.filter(Boolean).length;
  console.log(`\nVYSLEDEK vandr referencni model ve scene: ${ok}/${vysl.length} OK`);
  process.exit(ok === vysl.length ? 0 : 1);
})().catch(e => { console.error('TEST SPADL:', e.message); process.exit(2); });
