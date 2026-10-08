// Test: STAVITELNA PATKA ve SCENE = dva kusy (sroub s maticí + plastovy kuzel v cerne; webapp/js/scene/patky-kuzel.js) a stul s patkou M8 se do Sceny vlozi CELY
// (webapp/js/scene/stul-konfigurator.js: doplneni dilu, ktere katalog Sceny nezna, + kontrola uplnosti; bot10, 2026-10-08).
// Robert 2026-10-08: "kdyz udelam nabidku z generatoru, 3D scena neni ta nova ale stara" - 3D pohledy a vykresy nabidky z generatoru dela SCENA ze svych katalogovych dilu
// (scene.html?stul=<dotaz>&nabidka_vykresy=<id>), ne GLB generatoru. Nalez pri oprave: patka M8 (product_3251, systemy 30 a 35) ma visible_in_scene=0, katalog Sceny ji nezna a
// vkladani stolu se na ni PRERUSILO (alert "neznamy dil product_3251 v katalogu", ve Scene 21 z 51 dilu - i ve vykresech nabidky).
// Spusti SKUTECNOU scenu (scene.html) v Chromiu pres most scripts/2026-10-06_nabidka_vykresy_testy/_most_scena.py (API cte Flask, DB se jen cte, zapisy se nepredavaji), vlozi stul z generatoru
// pres ?stul=<dotaz> a zmeri dily patek ve scene. Spusteni (REPO = koren s api / scripts, WEB_DIR = kandidat statiky; ROZDELENO=0 overi PUVODNI stav = patka je jeden mesh a M8 chybi):
//   systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --setenv=HOME=/root --setenv=REPO=<koren> --setenv=WEB_DIR=<koren>/webapp [--setenv=SHOT=/cesta/predpona] \
//     --working-directory=/opt/konfigurator api/venv/bin/python3 scripts/2026-10-06_nabidka_vykresy_testy/_most_scena.py /opt/konfigurator/scripts/2026-10-08_patky_kuzel/test_patky_scena.js
const { chromium } = require('/opt/konfigurator/node_modules/playwright-core');
const fs = require('fs');
const path = require('path');
const BASE = process.env.BASE, SHOT = process.env.SHOT || '', WEB = process.env.WEB_DIR || '/opt/konfigurator/webapp';
const ROZDELENO = process.env.ROZDELENO !== '0';
const vysl = [];
const over = (nazev, podminka, detail) => { vysl.push(!!podminka); console.log((podminka ? 'OK   ' : 'FAIL ') + nazev + (podminka ? '' : '  -> ' + JSON.stringify(detail).slice(0, 700))); };

const SADA = JSON.parse(fs.readFileSync(path.join(__dirname, '..', '2026-10-07_koty_stul_testy', 'dotazy.json'), 'utf8'));
const zakladni = n => SADA.find(s => s.nazev === n).dotaz;
function dotaz(zaklad, zmeny) { const q = new URLSearchParams(zakladni(zaklad)); Object.keys(zmeny).forEach(k => q.set(k, String(zmeny[k]))); return q.toString(); }
const KUZEL = '242424';                                                    // vychozi barva kuzele ve Scene (cerny plast jako zaslepky); sroub s maticí drzi barvu dilu (katalogova barva = Robert ji meni v adminu i pres "Obarvit dil")
const KONFIG = [
  { nazev: 'system 30, patky M8 (nabidka 126)', dotaz: zakladni('nabidka126'), part: 3251, trojuhelniku: 7904, kuzel: 7514, vyska: 25.0, polomer: 20.5 },
  { nazev: 'system 30, siroky stul 2000 mm, patky', dotaz: dotaz('stul30_vychozi', { kolecka: 0, patky: 1, sirka: 2000 }), part: 3251, trojuhelniku: 7904, kuzel: 7514, vyska: 25.0, polomer: 20.5 },
  { nazev: 'system 40, patky M10', dotaz: dotaz('stul40_vychozi', { kolecka: 0, patky: 1 }), part: 3283, trojuhelniku: 6832, kuzel: 6460, vyska: 31.0, polomer: 30.0 },
  { nazev: 'system 35 bez navleku, patky M8', dotaz: dotaz('stul35_vychozi', { kolecka: 0, patky: 1, navlek: 0 }), part: 3251, trojuhelniku: 7904, kuzel: 7514, vyska: 25.0, polomer: 20.5 },
  { nazev: 'system 45, hluboky stul 2000 mm, patky M10', dotaz: dotaz('stul40_vychozi', { system: 45, kolecka: 0, patky: 1, hloubka: 2000 }), part: 3283, trojuhelniku: 6832, kuzel: 6460, vyska: 31.0, polomer: 30.0 },
];

function chytej(page) {
  const o = { chyby: [], dialogy: [] };
  page.on('pageerror', e => o.chyby.push(e.message.slice(0, 200)));
  page.on('console', m => { if (m.type() === 'error' && !/Failed to load resource/.test(m.text())) o.chyby.push('console: ' + m.text().slice(0, 200)); });
  page.on('dialog', async d => { o.dialogy.push(d.message().slice(0, 200)); await d.dismiss(); });
  return o;
}

async function otevri(browser, q) {
  const page = await browser.newPage({ viewport: { width: 1500, height: 900 } });
  const sber = chytej(page);
  await page.goto(BASE + '/scene.html?stul=' + encodeURIComponent(q));
  await page.waitForFunction(() => window.StulKonf && window.StulKonf.state && window.StulKonf.state.inserted, null, { timeout: 180000 });
  await page.waitForTimeout(800);
  return { page, sber };
}

const MERENI = () => {
  const jeNoha = e => e.part && /(^|_)(3251|3283)$/.test(String(e.part.id));
  const noh = placed.filter(jeNoha);
  const meshe = e => { const o = []; e.object3d.traverse(n => { if (n.isMesh) { n.geometry.computeBoundingBox(); const b = n.geometry.boundingBox, p = n.geometry.attributes.position; let r = 0; for (let i = 0; i < p.count; i++) r = Math.max(r, Math.hypot(p.getX(i), p.getZ(i)));
    o.push({ name: n.name, tris: n.geometry.index ? n.geometry.index.count / 3 : p.count / 3, col: n.material && n.material.color ? n.material.color.getHexString() : null, ymin: b.min.y, ymax: b.max.y, r: r }); } }); return o; };
  const out = noh.map(e => ({ id: String(e.part.id), meshe: meshe(e), mc: e.object3d.userData.meshColors || null, save: (typeof serializeEntryForSave === 'function' ? (serializeEntryForSave(e) || {}).mesh_colors || null : 'chybi') }));
  const ostatni = placed.filter(e => !jeNoha(e)).map(e => { let n = 0; e.object3d.traverse(x => { if (x.isMesh) n++; }); return n; });
  const BEZ_SCENY = { jekl_40x40x2: true, jekl_zaslepka_40: true, sse_jekl_40: true, sse_profil_35: true, sse_plech_150: true, sse_patka_35: true };
  const d = window.StulKonf.state.data;
  const cat = (noh[0] && noh[0].part) || null;
  const ocekSroub = cat ? materialForLayer(cat.layer, cat.color_hex || undefined).color.getHexString() : null;   // barva, jakou by cely dil mel bez rozdeleni (katalogova barva nebo barva vrstvy)
  const cizi = placed.filter(e => !jeNoha(e)).every(e => !('mesh_colors' in (serializeEntryForSave(e) || {})));      // ostatni dily se ukladaji jako dosud (bez mesh_colors)
  return { noh: out, ocekSroub: ocekSroub, ciziBezMeshColors: cizi, ostatniMeshe: ostatni, pocet: placed.length, ocekavano: d.dily.filter(x => !BEZ_SCENY[x.part_id]).length, vlastni: window.StulKonf.state.own.length, api: !!window.PATKY_KUZEL };
};

(async () => {
  const browser = await chromium.launch({ args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  let prvni = true;
  for (const k of KONFIG) {
    const { page, sber } = await otevri(browser, k.dotaz);
    const m = await page.evaluate(MERENI);
    const n = m.noh.length;
    over(`${k.nazev}: stul je ve scene CELY (${m.pocet} z ${m.ocekavano} dilu, vsechny jsou "vlastni") a bez alertu`, m.pocet === m.ocekavano && m.vlastni === m.pocet && sber.dialogy.length === 0, { pocet: m.pocet, ocekavano: m.ocekavano, vlastni: m.vlastni, dialogy: sber.dialogy });
    over(`${k.nazev}: ve scene jsou dily patek (${n} ks) a modul patky-kuzel.js ${ROZDELENO ? 'je nacteny' : 'NENI nacteny (puvodni stav)'}`, n >= 4 && m.api === ROZDELENO, { n, api: m.api });
    if (ROZDELENO) {
      over(`${k.nazev}: KAZDA patka ma prave 2 mesh: sroub_matice + plast_cerny`, m.noh.every(p => p.meshe.length === 2 && p.meshe.map(x => x.name).sort().join() === 'plast_cerny,sroub_matice'), m.noh.map(p => p.meshe.map(x => x.name)));
      over(`${k.nazev}: trojuhelniky: kuzel ${k.kuzel} + sroub s maticí ${k.trojuhelniku - k.kuzel} = puvodnich ${k.trojuhelniku} (nic neztraceno)`, m.noh.every(p => { const c = p.meshe.find(x => x.name === 'plast_cerny'), s = p.meshe.find(x => x.name === 'sroub_matice'); return c && s && c.tris === k.kuzel && s.tris === k.trojuhelniku - k.kuzel; }), m.noh[0].meshe);
      over(`${k.nazev}: kuzel je cerny plast #${KUZEL}, sroub s maticí drzi barvu dilu (#${m.ocekSroub})`, m.noh.every(p => { const c = p.meshe.find(x => x.name === 'plast_cerny'), s = p.meshe.find(x => x.name === 'sroub_matice'); return c.col === KUZEL && s.col === m.ocekSroub; }), [m.ocekSroub, m.noh[0].meshe.map(x => [x.name, x.col])]);
      over(`${k.nazev}: rozmery kuzele: vyska ${k.vyska} mm, polomer ${k.polomer} mm; sroub s maticí navazuje nad nim a konci v nule`, m.noh.every(p => { const c = p.meshe.find(x => x.name === 'plast_cerny'), s = p.meshe.find(x => x.name === 'sroub_matice');
        return Math.abs((c.ymax - c.ymin) - k.vyska) < 0.06 && Math.abs(c.r - k.polomer) < 0.06 && Math.abs(s.ymax) < 0.06 && s.ymin >= c.ymax - 0.06; }), m.noh[0].meshe);
      over(`${k.nazev}: vychozi cerna kuzele je v meshColors (panely materialu / HDRI ji nepreplacnou), sroub s maticí v meshColors NENI (sleduje barvu dilu) a vychozi cerna se do ULOZENE sestavy NEZAPISUJE`, m.noh.every(p => p.mc && p.mc.plast_cerny === '#' + KUZEL && !('sroub_matice' in p.mc) && p.save === null), m.noh[0]);
      over(`${k.nazev}: ostatni dily ve scene jsou nedotcene (kazdy ma 1 mesh jako dosud; zadny dalsi dil se nedelil, ukladaji se bez mesh_colors)`, m.ostatniMeshe.every(x => x >= 1) && m.noh.every(p => p.meshe.length === 2) && m.ciziBezMeshColors, [m.ostatniMeshe.slice(0, 8), m.ciziBezMeshColors]);
      // prekresleni materialu (zmena rezimu / HDRI) barvy casti nepreplacne
      const po = await page.evaluate(() => { refreshAllMaterials(); const o = []; placed.filter(e => e.part && /(^|_)(3251|3283)$/.test(String(e.part.id))).forEach(e => e.object3d.traverse(n => { if (n.isMesh) o.push([n.name, n.material.color.getHexString()]); })); return o; });
      over(`${k.nazev}: po refreshAllMaterials() je kuzel porad cerny a sroub s maticí drzi barvu dilu`, po.filter(x => x[0] === 'plast_cerny').length === n && po.every(x => x[1] === (x[0] === 'plast_cerny' ? KUZEL : m.ocekSroub)), po.slice(0, 4));
      if (prvni && SHOT) {                                                                          // snimek patky zblizka (jen pro lidskou kontrolu)
        prvni = false;
        await page.evaluate(() => { const o = document.getElementById('helpModalOverlay'); if (o) o.classList.remove('open');
          const e = placed.find(x => x.part && /(^|_)(3251|3283)$/.test(String(x.part.id))); const b = new THREE.Box3().setFromObject(e.object3d), c = b.getCenter(new THREE.Vector3());
          controls.target.copy(c); camera.position.set(c.x + 140, c.y + 60, c.z + 140); controls.update(); });
        await page.waitForTimeout(900);
        await page.screenshot({ path: SHOT + '_patka.png' });
      }
    } else {
      over(`${k.nazev}: PUVODNI stav: patka je jeden mesh (referencni beh bez kandidata)`, m.noh.every(p => p.meshe.length === 1), m.noh.map(p => p.meshe.map(x => x.name)));
    }
    over(`${k.nazev}: bez chyb ve strance ani v konzoli`, sber.chyby.length === 0, sber.chyby.slice(0, 3));
    await page.close();
  }

  if (ROZDELENO) {
    // --- barvy casti: rucni obarveni a obnova ulozene sestavy (barvy zkousene v testu se liseji od katalogove barvy dilu)
    const { page, sber } = await otevri(browser, KONFIG[2].dotaz);
    const r = await page.evaluate(async () => {
      const barvy = e => { const o = {}; e.object3d.traverse(n => { if (n.isMesh) o[n.name] = n.material.color.getHexString(); }); return o; };
      const cat = CATALOG.find(p => p.id === 'product_3283');
      const karta = cat.color_hex || '#4d4d4d';                                                          // katalogova barva dilu (Robert ji meni v adminu / pres "Obarvit dil")
      const hex = c => materialForLayer(cat.layer, c || undefined).color.getHexString();
      const nactiUlozeny = async spec => { const e = await loadCustomShapePartEntry(Object.assign({ part_id: 'product_3283', position: [0, 0, 0], quaternion: [0, 0, 0, 1], scale: [1, 1, 1] }, spec)); return { barvy: barvy(e), mc: JSON.parse(JSON.stringify(e.object3d.userData.meshColors || null)) }; };
      const out = { karta: hex(karta), cataloguBez: hex(cat.color_hex) };
      out.ulozenyKatalogova = await nactiUlozeny({ color: karta });                                       // dil ulozeny s automaticky zapsanou katalogovou barvou
      out.ulozenyBezBarvy = await nactiUlozeny({});
      out.ulozenyRucne = await nactiUlozeny({ color: '#3366cc' });                                        // "Obarvit dil" modre
      out.ulozenyCastecne = await nactiUlozeny({ mesh_colors: { plast_cerny: '#00cc00' } });              // kuzel obarven samostatne
      const e0 = placed.find(x => x.part && String(x.part.id) === 'product_3283');
      out.kolo = await nactiUlozeny(JSON.parse(JSON.stringify(serializeEntryForSave(e0))));               // vlozeny dil -> ulozeny -> znovu nacteny: stejny vzhled
      out.kolo0 = barvy(e0);
      out.ulozenoVychozi = (serializeEntryForSave(e0) || {}).mesh_colors || null;
      const e = placed.find(x => x.part && String(x.part.id) === 'product_3283');
      const kuzel = []; e.object3d.traverse(n => { if (n.isMesh && n.name === 'plast_cerny') kuzel.push(n); });
      paintEntry(e, '#3366cc');                                                                           // "Obarvit dil": cely dil
      out.celyDil = { barvy: barvy(e), mc: JSON.parse(JSON.stringify(e.object3d.userData.meshColors || null)) };
      paintEntry(e, '#00cc00', kuzel[0]);                                                                 // klik na kuzel: jen kuzel
      out.klikNaKuzel = { barvy: barvy(e), mc: JSON.parse(JSON.stringify(e.object3d.userData.meshColors || null)) };
      refreshAllMaterials();
      out.poPrekresleni = barvy(e);
      out.ulozeno = JSON.parse(JSON.stringify((serializeEntryForSave(e) || {}).mesh_colors || null));
      return out;
    });
    over('obnova ulozene sestavy: dil s katalogovou barvou nebo bez barvy = sroub s maticí v barve dilu + cerny kuzel', r.ulozenyKatalogova.barvy.sroub_matice === r.karta && r.ulozenyKatalogova.barvy.plast_cerny === KUZEL && r.ulozenyBezBarvy.barvy.sroub_matice === r.cataloguBez && r.ulozenyBezBarvy.barvy.plast_cerny === KUZEL, r);
    over('obnova ulozene sestavy: rucne obarveny dil (#3366cc) = sroub s maticí modry, kuzel zustava cerny plast', r.ulozenyRucne.barvy.sroub_matice === '3366cc' && r.ulozenyRucne.barvy.plast_cerny === KUZEL, r.ulozenyRucne);
    over('obnova ulozene sestavy: samostatne obarveny kuzel (mesh_colors) se obnovi', r.ulozenyCastecne.barvy.plast_cerny === '00cc00', r.ulozenyCastecne);
    over('ulozena sestava s patkou vypada po nacteni stejne jako po vlozeni (sroub s maticí si drzi katalogovou barvu dilu, kuzel cerny; mesh_colors se pro nezmenenou patku neuklada)', JSON.stringify(r.kolo.barvy) === JSON.stringify(r.kolo0) && r.kolo.barvy.plast_cerny === KUZEL && r.ulozenoVychozi === null, [r.kolo, r.kolo0, r.ulozenoVychozi]);
    over('"Obarvit dil" (cely dil modre) obarvi sroub s maticí, kuzel zustane cerny plast', r.celyDil.barvy.sroub_matice === '3366cc' && r.celyDil.barvy.plast_cerny === KUZEL && r.celyDil.mc && r.celyDil.mc.plast_cerny === '#' + KUZEL, r.celyDil);
    over('klik na kuzel obarvi JEN kuzel (zelene), sroub s maticí zustane; barva prezije refreshAllMaterials() a jde do ulozene sestavy', r.klikNaKuzel.barvy.plast_cerny === '00cc00' && r.klikNaKuzel.barvy.sroub_matice === '3366cc' && r.poPrekresleni.plast_cerny === '00cc00' && r.poPrekresleni.sroub_matice === '3366cc' && r.ulozeno && r.ulozeno.plast_cerny === '#00cc00', [r.klikNaKuzel, r.poPrekresleni, r.ulozeno]);
    over('obarvovani: bez chyb ve strance', sber.chyby.length === 0, sber.chyby.slice(0, 3));
    await page.close();

    // --- stul se nikdy nevlozi napul: dil, ktery nelze doplnit z karty (404), nebo model, ktery se nenacte, vlozeni zastavi a ve scene nic nezustane
    const page2 = await browser.newPage({ viewport: { width: 1500, height: 900 } });
    const sber2 = chytej(page2);
    await page2.route('**/api/shop/products/3251', route => route.fulfill({ status: 404, contentType: 'application/json', body: '{"error":"Produkt neexistuje."}' }));
    await page2.goto(BASE + '/scene.html?stul=' + encodeURIComponent(KONFIG[0].dotaz));
    await page2.waitForFunction(() => { const e = document.getElementById('stulKonfStatus'); return e && /nevkl/.test(e.textContent); }, null, { timeout: 120000 });
    const s2 = await page2.evaluate(() => ({ placed: placed.length, inserted: window.StulKonf.state.inserted, own: window.StulKonf.state.own.length, status: document.getElementById('stulKonfStatus').textContent }));
    over('dil bez karty (404): stul se NEVLOZI napul - scena je prazdna, stav hlasi chybejici product_3251, zadny alert', s2.placed === 0 && !s2.inserted && s2.own === 0 && /product_3251/.test(s2.status) && sber2.dialogy.length === 0, { s2, dialogy: sber2.dialogy });
    over('dil bez karty (404): bez chyb ve strance', sber2.chyby.length === 0, sber2.chyby.slice(0, 3));
    await page2.close();

    const page3 = await browser.newPage({ viewport: { width: 1500, height: 900 } });
    const sber3 = chytej(page3);
    await page3.route('**/katalog/product_3251.glb*', route => route.fulfill({ status: 404, body: 'x' }));
    await page3.goto(BASE + '/scene.html?stul=' + encodeURIComponent(KONFIG[0].dotaz));
    await page3.waitForFunction(() => { const e = document.getElementById('stulKonfStatus'); return e && /selhalo/.test(e.textContent); }, null, { timeout: 120000 });
    const s3 = await page3.evaluate(() => ({ placed: placed.length, inserted: window.StulKonf.state.inserted, own: window.StulKonf.state.own.length, status: document.getElementById('stulKonfStatus').textContent }));
    over('model dilu se nenacte (404): vlozeni se zastavi, napul vlozeny stul se ze sceny ODEBERE, stav hlasi "vlozilo se jen N z M dilu"', s3.placed === 0 && !s3.inserted && s3.own === 0 && /vložilo se jen \d+ z \d+ dílů/.test(s3.status), s3);
    over('model dilu se nenacte (404): Scena o chybe informovala (alert), ne tichy neuplny stul', sber3.dialogy.length >= 1, sber3.dialogy);
    await page3.close();

    const html = fs.readFileSync(WEB + '/scene.html', 'utf8'), js = fs.readFileSync(WEB + '/js/scene/patky-kuzel.js', 'utf8');
    over('scene.html: modul patky-kuzel.js je vlozen JEDNOU (bez pinu jako ostatni skripty sceny) AZ PO #app-script a PRED stul-konfigurator.js', (html.match(/<script src="js\/scene\/patky-kuzel\.js"><\/script>/g) || []).length === 1 && (html.match(/patky-kuzel\.js/g) || []).length === 1
      && html.indexOf('<script id="app-script">') < html.indexOf('<script src="js/scene/patky-kuzel.js"></script>') && html.indexOf('<script src="js/scene/patky-kuzel.js"></script>') < html.indexOf('<script src="js/scene/stul-konfigurator.js"></script>'), null);
    // rovina kuzele v JS = rovina v api/stul_glb.py (jedna pravda)
    const g = fs.readFileSync(path.join(__dirname, '..', '..', 'api', 'stul_glb.py'), 'utf8');
    const py = /KUZEL_PATKY = \{"product_3251": (-?[\d.]+), "product_3283": (-?[\d.]+)\}/.exec(g), jsr = /ROVINA = \{ product_3251: (-?[\d.]+), product_3283: (-?[\d.]+) \}/.exec(js);
    over('rovina kuzele patek: patky-kuzel.js = api/stul_glb.py KUZEL_PATKY (stejne konstanty, 3251 / 3283)', py && jsr && Number(py[1]) === Number(jsr[1]) && Number(py[2]) === Number(jsr[2]), { py: py && py.slice(1), js: jsr && jsr.slice(1) });
  }
  await browser.close();
  console.log(`\n==> ${vysl.filter(Boolean).length}/${vysl.length} kontrol OK`);
  process.exit(vysl.every(Boolean) ? 0 : 1);
})().catch(e => { console.error('TEST SPADL:', e); process.exit(2); });
