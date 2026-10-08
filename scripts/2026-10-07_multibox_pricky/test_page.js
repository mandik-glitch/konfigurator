// Test sekce "Pricky do multiboxu" na strance online nabidky webapp/nabidka-online.html (bot8, 2026-10-07; Robert: "multiboxy maji moznost delicich pricek ... v online nabidce pro multiboxy
// nejaky system pro priobjednani pricek jako prislusenstvi, v nejakych par variantach i vizualne primo v multiboxech, at jsou videt ceny"; "nabidnout vzdy nejake varianty SETU, vzdy pro celou
// polici / suplik s multiboxy"; "chci hotove varianty mix, v jedne polici napr. 4 moznosti ruznych kombinaci - je zdlouhave klikat kazdy box zvlast"). Zakaznik vybira HOTOVY SET (bez / mix 1-4 /
// plny) pro celou polici nebo suplik; stranka ho prevede na pocty pricek v boxech (g.sety[set].po_boxech) a vyber drzi i posila PO BOXECH {id boxu: n}.
// SPUSTENI (z teto slozky; nejdriv jednou postavit zakaznicka GLB s `mbx`, Blender na CPU, ~15 s na kartu):
//   python3 /opt/konfigurator/scripts/2026-10-02_v3d_testy/build_karty.py 4921 4453          (GLB do <V3D_TEST_OUT>/out2; vychozi <tmp>/v3d_testy)
//   node test_page.js                                                                         (~4 min; exit 0 jen kdyz vse prosel, na konci "N/N kontrol prošlo"; SNIMKY=<slozka> uklada snimky)
//   python3 mutace_page.py                                                                    (mutacni kontrola: zamerne chyby ve KOPII stranky, kazda musi test shodit)
// Prostredi (vse nepovinne): PRICKY_REPO (koren repa, vychozi ../..), NABIDKA_HTML (kandidat stranky pred nasazenim, vychozi <repo>/webapp/nabidka-online.html), PLUGIN_JS (plugin pro kontrolu pinu,
//   vychozi <repo>/webapp/js/v3d/pricky-multibox.js), PRICKY_API (slozka s nabidka_pricky.py a v3d_glb.py, vychozi <repo>/api), V3D_TEST_OUT / PRICKY_FIX (zakaznicka GLB), NABIDKA_BASE_HTML (VOLITELNE:
//   puvodni verze stranky; je-li zadana, porovna se s ni cely #deck u nabidky bez priccek bajt po bajtu; bez ni se jen tato kontrola preskoci).
// Co to je: SKUTECNA stranka v Chromiu proti FALESNEMU serveru (harness_pricky.js: zadna DB, zadna sit), 3D prohlizec V3D je atrapa rizena z testu, plugin je atrapa stub-pricky.js (skutecny viewer +
//   skutecny plugin overuje test_page_real.js). Payload (offer.pricky) si test vyrobi z `spec` zakaznickeho GLB karty 4921 (police 8 + 2 suplíky po 7 boxech) pres api/nabidka_pricky.payload.
// Hlida: bez offer.pricky se NIC nemeni (zadne prvky priccek, plugin se nenacita, mount bez plugins, QR bez pr, accept bez pricky, order-prefs bez priccek, soucty beze zmeny); pin pluginu ve strance =
//   sha256 souboru; sekce a cipy JEN pro sety, ktere skupina nabizi (g.sety, v poradi payload.sety), miniatura = rada malych boxu s carami podle po_boxech (rozdil mezi mixy je videt), cena za celou skupinu
//   a "N pricek", aktivni cip jen pri PRESNE shode poctu (jinak "Vlastni kombinace"), klik = setGroup/setAll + souhrn + patička + banner + rozpis + radky tabulky + QR ?pr a accept pricky ve tvaru
//   "b01:6,b02:1" (jen n > 0, serazeno podle CISLA boxu); qty, montaz % (z castky vcetne priccek), zaloha; localStorage {v:2, boxy} (platne, poskozene, v1, castecne neplatne, preziti reloadu);
//   chyby pluginu / modelu / skupiny a boxy bez 3D; neplatne sety v payloadu; XSS; nahled_admin; stav po prijeti (jen ke cteni); mobil 360 px, rozlozeni vedle modelu, tisk, navigace v panelu; hide_bom_prices.
// v4.1 (Robert 2026-10-07 po zkousce zive nabidky: "Vsechny police a suplíky, multibox pricky tam nechci"; "jen postupne po policich at je videt do kterych suplíku/polic to je myslene a zaroven se musi
//   vsechny multiboxy vysunout aby to bylo rovnou videt ve 3D"): radek "Vsechny ..." NEEXISTUJE (set se vybira po skupinach; B4, B13); zvyrazneni skupiny ve 3D - mys, dotyk, klavesnice, ~3 s po kliknuti
//   na set (sekce Z); po vyberu setu jineho nez "Bez pricek" se vsechny boxy skupiny vysunou: viewer.play(id, 1) pro id z api.motionIds(gid), po jednom s odstupem ~150 ms, jen na klik zakaznika
//   (ne pri obnove z localStorage, ne pri "Bez pricek", zavirani se nedela; selhani pluginu / viewer.play nesmi shodit stranku; sekce O).
// v5 (Robert 2026-10-07: "potom i pricky v suplíku, sloty po 100 mm, smer jen zepredu dozadu"; jen ocelove suplíky): druh skupiny "suplik" - nadpis sekce a aria-label podle druhu zobrazenych skupin (jen multiboxy /
//   jen suplíky / obojí), slova suplík / suplíky / suplíku, miniatura z rozmeru typu (typy[k].L, W, lem: pomer stran, tmavy lem jen u multiboxu, cary podle desky[].s[0] / L), stitek "zakaznik zatim nevidi"
//   u skupiny se skryto:true (jen admin), sety se deduplikuji (1 podnos = bez + plny), ceny / rozpis "pricky bez DPH" / QR / prijeti stejne jako u multiboxu (sekce U). Payload vyrabi api/nabidka_pricky.payload
//   z RUCNICH scenaru SPECY v harness_pricky.js (mm, bez GLB).
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const H = require('./harness_pricky.js');

const vysl = [];
const over = (nazev, podminka, detail) => { vysl.push(!!podminka); console.log((podminka ? 'OK   ' : 'FAIL ') + nazev + (podminka ? '' : '  -> ' + JSON.stringify(detail).slice(0, 500))); if (!podminka && process.env.FAILFAST) process.exit(1); };       // FAILFAST=1: konec pri prvni selhane kontrole (mutace_page.py)
const BASE_HTML = process.env.NABIDKA_BASE_HTML || '';
const SNIMKY = process.env.SNIMKY || '';                                  // slozka pro snimky obrazovky (nepovinne)
const P0 = H.payload('4921');
const NET_ZBOZI = H.nabidka({ pricky: null }).total_price;                // total_price vzorove nabidky (bez DPH)
const fmtK = n => Math.round(n).toLocaleString('cs-CZ').replace(/[\u00a0\u202f]/g, ' ');   // jako fmtCzk na strance (bez "Kč"), mezery tisicu jako obycejne mezery (stranka se cte normalizovana)
const plPricek = n => (n === 1 ? 'příčka' : (n >= 2 && n <= 4 ? 'příčky' : 'příček'));
const plBoxu = n => (n === 1 ? 'box' : (n >= 2 && n <= 4 ? 'boxy' : 'boxů'));
const plSkupin = n => (n === 1 ? 'skupina' : (n >= 2 && n <= 4 ? 'skupiny' : 'skupin'));

// ---- nezavisla implementace modelu a vzorce serveru (vyber = {id boxu: n}); items_net = total_price*qty + pricky_net*qty, montaz % z items_net, DPH 21 %
const boxP = (P, id) => P.boxy.find(b => b.id === id);
const skP = (P, gid) => P.skupiny.find(g => g.id === gid);
const jednP = (P, id) => P.dily.find(d => d.klic === P.typy[boxP(P, id).k].dil).cena;
const maxP = (P, id) => P.typy[boxP(P, id).k].max;
// vyber boxu pro {id skupiny: id setu}: pocty z g.sety[set].po_boxech (poradi boxu = g.boxy)
const vyberSetu = (P, sety) => { const v = {}; Object.keys(sety).forEach(gid => { const g = skP(P, gid); g.boxy.forEach((id, i) => { const n = g.sety[sety[gid]].po_boxech[i]; if (n > 0) v[id] = n; }); }); return v; };
const sumSk = (P, gid, vyber) => { let priccek = 0, cena = 0; skP(P, gid).boxy.forEach(id => { const n = vyber[id] || 0; priccek += n; cena += n * jednP(P, id); }); return { priccek, cena: Math.round(cena * 100) / 100 }; };
function vypocet(P, vyber, { qty = 1, montaz = false, pct = 10 } = {}) {
  const pocty = {};
  Object.keys(vyber).forEach(id => { if (vyber[id] > 0) { const dil = P.typy[boxP(P, id).k].dil; pocty[dil] = (pocty[dil] || 0) + vyber[id]; } });
  const radky = P.dily.filter(d => pocty[d.klic]).map(d => ({ klic: d.klic, nazev: d.nazev, qty: pocty[d.klic], unit: d.cena, total: Math.round(d.cena * pocty[d.klic] * 100) / 100 }));
  const pricky = Math.round(radky.reduce((s, r) => s + r.total, 0) * 100) / 100;
  const items = (NET_ZBOZI + pricky) * qty;
  const montazNet = montaz ? Math.round(items * pct / 100 * 100) / 100 : 0;
  const total = items + montazNet;
  return { radky, pricky, items, montazNet, total, gross: total * 1.21, kusu: radky.reduce((s, r) => s + r.qty, 0) };
}
const retezec = vyber => Object.keys(vyber).filter(id => vyber[id] > 0).sort((a, b) => parseInt(a.slice(1), 10) - parseInt(b.slice(1), 10)).map(id => id + ':' + vyber[id]).join(',');
const idsSk = gid => skP(P0, gid).boxy;                                   // id boxu skupiny v poradi skupiny[].boxy
const setyG = (P, gid) => P.sety.filter(s => skP(P, gid).sety[s.id]).map(s => s.id);          // sety, ktere skupina nabizi (v poradi payload.sety)

// ---- cteni stavu stranky
const stavCeny = page => page.evaluate(() => {
  const q = s => document.querySelector(s), t = s => { const e = q(s); return e ? e.textContent.replace(/[\u00a0\u202f]/g, ' ').replace(/\s+/g, ' ').trim() : null; };
  const tb = [...document.querySelectorAll('table.items tbody')];
  return {
    banner: t('#totalBannerValue'), detail: t('#totalBannerDetail'), vat: t('#totalBannerVat'), montazInfo: t('#montazInfo'), qrAmount: t('#payQrAmount'), deposit: t('#depositVal'),
    montazBtn: t('#montazOnBtn'), qr: q('#payQrImg') ? q('#payQrImg').getAttribute('src') : null,
    radky: [...document.querySelectorAll('#prickyTbody tr')].map(tr => [...tr.children].map(td => td.textContent.replace(/[\u00a0\u202f]/g, ' ').trim())),
    pocetTbody: tb.length, zakladRadku: tb.length ? tb[0].querySelectorAll('tr').length : 0,
  };
});
const stavPanelu = page => page.evaluate(() => {
  const p = document.getElementById('prickyPanel');
  if (!p) return null;
  const tt = e => e ? e.textContent.replace(/[\u00a0\u202f]/g, ' ').replace(/\s+/g, ' ').trim() : null;
  const chip = b => ({ set: b.dataset.set, pressed: b.getAttribute('aria-pressed'), disabled: b.disabled, text: tt(b), boxu: b.querySelectorAll('svg .pr-mb').length, car: b.querySelectorAll('svg .pr-cara').length, svg: b.querySelector('svg').innerHTML,
    rects: [...b.querySelectorAll('svg .pr-mb')].map(r => ({ x: +r.getAttribute('x'), y: +r.getAttribute('y'), w: +r.getAttribute('width'), h: +r.getAttribute('height') })),
    lemy: [...b.querySelectorAll('svg .pr-lem')].map(l => ({ x: +l.getAttribute('x'), y: +l.getAttribute('y'), w: +l.getAttribute('width') })),
    cary: [...b.querySelectorAll('svg .pr-cara')].map(l => ({ x: +l.getAttribute('x1'), y1: +l.getAttribute('y1'), y2: +l.getAttribute('y2') })),
    pop: tt(b.querySelector('.pr-pop')), pozn: tt(b.querySelector('.pr-pri')), cena: tt(b.querySelector('.pr-cena')), pocet: tt(b.querySelector('.pr-pocet')) });
  const karty = [...p.querySelectorAll('.pr-card[data-skupina]')].map(c => ({
    id: c.dataset.skupina, nadpis: tt(c.querySelector('h4')), skryto: c.querySelectorAll('.pr-skryto').length, skrytoText: tt(c.querySelector('.pr-skryto')), skrytoTitle: (c.querySelector('.pr-skryto') || {}).title || null, souhrn: tt(c.querySelector('.pr-sum')), vlastni: c.querySelector('.pr-sum').classList.contains('pr-vlastni'), chipy: [...c.querySelectorAll('.pr-chip')].map(chip),
    stepper: c.querySelectorAll('.pr-step, .pr-row, details.pr-det, [data-akce]').length,
  }));
  return { hidden: p.hidden, display: getComputedStyle(p).display, titul: tt(p.querySelector('.pr-title')), aria: p.getAttribute('aria-label'), karty, vseRadek: !!p.querySelector('.pr-all, [data-cil="vse"]'),
    paticka: tt(p.querySelector('.pr-foot')), odznak: tt(p.querySelector('.pr-badge')), text: tt(p), imgs: p.querySelectorAll('img').length };
});
const volani = page => page.evaluate(() => (window.__pr ? window.__pr.calls.map(c => c.join(':')) : null));
const pluginVyber = page => page.evaluate(() => (window.__pr && window.__pr.api ? window.__pr.api.get() : null));
const mounty = page => page.evaluate(() => (window.__v3d ? window.__v3d.calls.map(c => ({ plugins: Array.isArray(c.o.plugins) ? c.o.plugins.length : null, klice: Object.keys(c.o).sort() })) : null));
const aktSlide = page => page.evaluate(() => { const s = document.querySelector('.slide.active'); return s && s.dataset.key; });
const qrPr = page => page.evaluate(() => new URL(document.getElementById('payQrImg').src).searchParams.get('pr'));
const lsHodnota = page => page.evaluate(() => localStorage.getItem('pricky:TESTTOKEN'));
const klik = async (page, cil, set) => { await page.click(`#prickyPanel .pr-chip[data-cil="${cil}"][data-set="${set}"]`); await page.waitForTimeout(120); };
const hlVolani = page => page.evaluate(() => (window.__pr ? window.__pr.calls.filter(c => c[0] === 'highlightGroup').map(c => c[1]) : null));            // poradi volani highlightGroup (id skupiny / null)
const playLog = page => page.evaluate(() => (window.__v3dPlay ? window.__v3dPlay.map(x => Object.assign({}, x)) : null));                                   // volani viewer.play / playAll: {fn, id, dir, t}
const playVymaz = page => page.evaluate(() => { window.__v3dPlay.length = 0; if (window.__pr) window.__pr.calls.length = 0; });
const idsPohybu = (P, gid) => skP(P, gid).boxy.map(id => 'm_' + id);          // atrapa pluginu: pohyb boxu = "m_<id boxu>" (skutecny plugin dava id pohybu vieweru)
const posl = a => a[a.length - 1];
const ceny = async page => { await H.naCeny(page); await page.waitForTimeout(150); return stavCeny(page); };
// prvky stranky patrici sekci priccek (trida / id pricky*, pr-*)
const prvkyPricek = page => page.evaluate(() => document.querySelectorAll('[class*="pricky"], [id*="pricky"], [class^="pr-"], [class*=" pr-"], .has-pricky').length);

async function vyplnAccept(page) {
  await page.fill('#accIco', '12345678');
  await page.waitForTimeout(250);
  await page.fill('#accCompany', 'Test s.r.o.'); await page.fill('#accDic', 'CZ12345678'); await page.fill('#accAddress', 'Ulice 1, Praha');
  await page.fill('#accEmail', 'a@b.cz'); await page.fill('#accPhone', '+420123456789'); await page.fill('#acceptName', 'Jan Test');
}
const upravP = fn => { const P = H.payload('4921'); fn(P); return P; };
const snimek = async (page, jmeno) => { if (SNIMKY) { fs.mkdirSync(SNIMKY, { recursive: true }); await page.screenshot({ path: path.join(SNIMKY, jmeno) }); } };
const radkyOk = (rad, ex, zakl) => rad.length === ex.radky.length && ex.radky.every((x, i) => rad[i][0] === String(zakl + i + 1).padStart(2, '0') && rad[i][1] === x.nazev && rad[i][2] === '–' && rad[i][3] === x.qty + ' ks' && rad[i][4] === fmtK(x.unit) + ' Kč' && rad[i][5] === fmtK(x.total) + ' Kč');
const SETY_ID = P0.sety.map(s => s.id);                                    // bez, mix1..mix4, pln
const plSup = n => (n === 1 ? 'šuplík' : (n >= 2 && n <= 4 ? 'šuplíky' : 'šuplíků'));
const slovoBoxu = (g, n) => (g.k === 'suplik' ? plSup(n) : plBoxu(n));
const nadpisSk = g => `${g.popis} · ${g.boxu} ${slovoBoxu(g, g.boxu)}`;
// kontrola miniatury cipu podle payloadu: obdelnik na box skupiny, jeho vyska podle L:W typu (pomer 0,3-0,8; vyska 6-34 jednotek), tmavy lem jen u typu s lem > 0 (sirka lem / L, nejvyse 0,4), cary = pocet pricek,
// pozice car = desky[].s[0] / L z payloadu (vraci seznam nalezenych chyb, prazdny = v poradku)
function miniaturaChyby(P, g, ch) {
  const chyby = [], po = g.sety[ch.set].po_boxech, lemOcek = [];
  if (ch.rects.length !== g.boxy.length) chyby.push('obdelniku ' + ch.rects.length);
  g.boxy.forEach((id, i) => {
    const t = P.typy[P.boxy.find(b => b.id === id).k], rc = ch.rects[i], n = po[i];
    if (!rc) return;
    if (t.lem > 0) lemOcek.push({ rc, pomer: Math.min(t.lem, t.L * 0.4) / t.L });
    const vys = Math.max(6, Math.min(34, rc.w * Math.max(0.3, Math.min(0.8, t.W / t.L))));
    if (Math.abs(rc.h - vys) > 0.06) chyby.push(`box ${id}: vyska ${rc.h} != ${vys.toFixed(2)}`);
    const cary = ch.cary.filter(c => c.x >= rc.x - 0.01 && c.x <= rc.x + rc.w + 0.01 && c.y1 >= rc.y - 0.01 && c.y2 <= rc.y + rc.h + 0.01).map(c => (c.x - rc.x) / rc.w).sort((a, b) => a - b);
    const oc = n > 0 ? t.pocty.find(q => q.n === n).desky.map(d => d.s[0] / t.L).sort((a, b) => a - b) : [];
    if (cary.length !== oc.length || cary.some((x, j) => Math.abs(x - oc[j]) > 0.003)) chyby.push(`box ${id}: cary ${cary.map(x => x.toFixed(3))} != ${oc.map(x => x.toFixed(3))}`);
  });
  if (ch.lemy.length !== lemOcek.length) chyby.push(`lemu ${ch.lemy.length} != ${lemOcek.length}`);
  else lemOcek.forEach((l, j) => { if (Math.abs(ch.lemy[j].w / l.rc.w - l.pomer) > 0.003 || Math.abs(ch.lemy[j].x - l.rc.x) > 0.01) chyby.push(`lem ${j}: sirka ${(ch.lemy[j].w / l.rc.w).toFixed(3)} != ${l.pomer.toFixed(3)}`); });
  return chyby;
}

(async () => {
  let r, page, sp, sc, e, vyb;
  const b01 = idsSk('s1')[0], b02 = idsSk('s1')[1], b03x = idsSk('s1')[2], b04 = idsSk('s1')[3], b05 = idsSk('s1')[4], b06 = idsSk('s1')[5];          // id boxu skupiny s1 (sekce F a G)
  console.log(`vstupy: stranka ${H.NABIDKA_HTML}; payload z GLB ${H.FIX}/4921.offer.glb = ${P0.skupiny.length} ${plSkupin(P0.skupiny.length)}, ${P0.boxy.length} boxu, sety ${SETY_ID.join('/')}; plugin (jen pin) ${H.PLUGIN_JS}`);

  // ======================================================== P) pin pluginu ve strance = sha256 souboru pluginu
  {
    const html = fs.readFileSync(H.NABIDKA_HTML, 'utf8');
    const m = [...html.matchAll(/\/js\/v3d\/pricky-multibox\.js\?v=([0-9a-f]{10})/g)];
    const sha = fs.existsSync(H.PLUGIN_JS) ? crypto.createHash('sha256').update(fs.readFileSync(H.PLUGIN_JS)).digest('hex').slice(0, 10) : null;
    over('P1 stranka odkazuje na plugin /js/v3d/pricky-multibox.js?v=<prvnich 10 znaku sha256 souboru> (pin odpovida aktualnimu souboru pluginu)', m.length === 1 && sha !== null && m[0][1] === sha, { v_ve_strance: m.map(x => x[1]), sha256_souboru: sha, soubor: H.PLUGIN_JS });
  }

  // ======================================================== A) bez offer.pricky se nic nemeni
  r = await H.otevri({ data: H.nabidka({ pricky: null }) });
  page = r.page;
  await H.naSlide(page, 'view_3d');
  await page.waitForFunction(() => window.__v3d && window.__v3d.calls.length > 0, null, { timeout: 8000 }).catch(() => {});          // V3D.mount se vola az po stazeni modelu a viewer3d.js (za zatizeni dele nez 0,5 s)
  await page.waitForTimeout(300);
  const moA = await mounty(page);
  const prvkyA3d = await prvkyPricek(page);
  await H.naCeny(page); await page.waitForTimeout(300);
  const cA = await stavCeny(page);
  const prvkyAcen = await prvkyPricek(page);
  const layoutA = await page.evaluate(() => ({ trida: document.getElementById('view3dLayout').className, panel: !!document.getElementById('prickyPanel'), tbody: !!document.getElementById('prickyTbody'), plugin: typeof window.V3DPricky }));
  await page.click('#qtyPlus'); await page.click('.opt-btn[data-field="payment_method"][data-val="zaloha"]'); await page.waitForTimeout(900);   // spusti ukladani voleb (order-prefs)
  await vyplnAccept(page); await page.click('#btnAccept'); await page.waitForTimeout(400);
  const accA = r.accepts[0], postyA = r.posty.slice(), qrA = r.qr.slice(), urlsA = r.urls.slice(), chybyA = r.chyby.slice();
  let deckA = null;
  if (BASE_HTML) deckA = { kandidat: await page.evaluate(() => document.getElementById('deck').innerHTML) };
  await r.browser.close();
  over('A1 bez offer.pricky: v DOM neni zadny prvek sekce priccek (trida/id pricky*, pr-*, has-pricky, #prickyPanel, #prickyTbody) ani na 3D, ani na cenove strance, rozlozeni 3D slidu beze zmeny', prvkyA3d === 0 && prvkyAcen === 0
    && layoutA.trida === '' && !layoutA.panel && !layoutA.tbody, { prvkyA3d, prvkyAcen, layoutA });
  over('A2 bez offer.pricky: plugin se vubec nenacita (zadny pozadavek na /js/v3d/pricky-multibox.js, window.V3DPricky neexistuje) a V3D.mount nedostane plugins', !urlsA.some(u => /pricky-multibox\.js/.test(u)) && layoutA.plugin === 'undefined'
    && moA.length === 1 && moA[0].plugins === null && !moA[0].klice.includes('plugins'), { urls: urlsA.filter(u => /pricky/.test(u)), plugin: layoutA.plugin, moA });
  over('A3 bez offer.pricky: banner = cena zbozi bez priccek, rozpis bez radku priccek, tabulka bez dalsiho <tbody> (1 tbody), QR v zadnem pozadavku nema pr', cA.banner === fmtK(NET_ZBOZI) + ' Kč' && !/příčky/.test(cA.detail) && cA.radky.length === 0
    && cA.pocetTbody === 1 && qrA.length > 0 && qrA.every(u => !/[?&]pr=/.test(u)), { cA, qrA });
  over('A4 bez offer.pricky: telo accept bez pole pricky (jen jmeno a firemni udaje) a order-prefs bez cehokoli o pricky', accA && !('pricky' in accA) && Object.keys(accA).sort().join() === 'company_address,company_dic,company_ico,company_name,contact_email,contact_phone,name'
    && postyA.length > 0 && postyA.every(b => !Object.keys(b).some(k => /pricky|^pr$|skupin|^set|boxy/i.test(k)) && !/pricky/i.test(JSON.stringify(b))), { accA, postyA: postyA.slice(-1) });
  over('A5 bez offer.pricky: zadne chyby JS ve strance', chybyA.length === 0, chybyA);
  if (BASE_HTML) {
    process.env.NABIDKA_HTML = BASE_HTML;
    delete require.cache[require.resolve('./harness_pricky.js')];
    const HB = require('./harness_pricky.js');
    const rb = await HB.otevri({ data: HB.nabidka({ pricky: null }) });
    await HB.naSlide(rb.page, 'view_3d'); await rb.page.waitForTimeout(500);
    await HB.naCeny(rb.page); await rb.page.waitForTimeout(300);
    await rb.page.click('#qtyPlus'); await rb.page.click('.opt-btn[data-field="payment_method"][data-val="zaloha"]'); await rb.page.waitForTimeout(900);
    await vyplnAccept(rb.page); await rb.page.click('#btnAccept'); await rb.page.waitForTimeout(400);
    deckA.puvodni = await rb.page.evaluate(() => document.getElementById('deck').innerHTML);
    await rb.browser.close();
    process.env.NABIDKA_HTML = H.NABIDKA_HTML;
    over('A6 (NABIDKA_BASE_HTML) bez offer.pricky je cely #deck bajt po bajtu STEJNY jako u puvodni verze stranky', deckA.puvodni === deckA.kandidat, { delka: [deckA.puvodni.length, deckA.kandidat.length] });
  } else console.log('SKIP A6 porovnani s puvodni verzi stranky (nastav NABIDKA_BASE_HTML=/cesta/puvodni/nabidka-online.html)');

  // ======================================================== B) sekce, cipy setu (mixy), vyber, ceny
  r = await H.otevri({}); page = r.page;
  const mp0 = await stavCeny(page);
  await H.na3D(page);
  sp = await stavPanelu(page);
  const mo = await mounty(page);
  over('B1 po otevreni 3D slidu je sekce viditelna, V3D.mount dostal prave jeden plugin a plugin vznikl jednou s payloadem nabidky', sp && !sp.hidden && sp.display !== 'none' && mo.length === 1 && mo[0].plugins === 1
    && await page.evaluate(n => window.__pr.created === 1 && window.__pr.payload.skupiny.length === n && document.getElementById('view3dLayout').classList.contains('has-pricky'), P0.skupiny.length), { sp: sp && sp.hidden, mo });
  over('B1b nadpis sekce u multiboxu: "Příčky do multiboxů" (v zahlaví i aria-label panelu)', sp.titul === 'Příčky do multiboxů' && sp.aria === 'Příčky do multiboxů', { titul: sp.titul, aria: sp.aria });
  over('B2 karta za KAZDOU skupinu (police / suplik) s titulkem "popis · N boxu" a cipy JEN pro sety, ktere skupina nabizi (g.sety), v poradi payload.sety (bez, Mix 1-4, Plny set); zadne ovladani po boxech (stepper, "Upravit po boxech")', sp.karty.length === P0.skupiny.length
    && sp.karty.every((k, i) => k.id === P0.skupiny[i].id && k.nadpis === `${P0.skupiny[i].popis} · ${P0.skupiny[i].boxu} ${plBoxu(P0.skupiny[i].boxu)}` && k.chipy.map(c => c.set).join() === setyG(P0, k.id).join() && k.stepper === 0) && SETY_ID.join() === 'bez,mix1,mix2,mix3,mix4,pln', sp.karty.map(k => [k.id, k.nadpis, k.chipy.map(c => c.set).join('/')]));
  over('B3 cip nese nazev setu ("Mix 1"), poznamku, CENU ZA CELOU SKUPINU (= cena z payloadu, napr. +1 012 Kc; 0 Kc u "Bez pricek") a "N pricek"; vychozi stav = "Bez pricek" aktivni', sp.karty.every((k, i) => k.chipy.every(c => {
    const s = P0.skupiny[i].sety[c.set], set = P0.sety.find(x => x.id === c.set);
    return c.pop === set.popis && (set.pozn ? c.pozn === set.pozn : c.pozn === null) && c.cena === (s.cena > 0 ? '+' + fmtK(s.cena) + ' Kč' : '0 Kč') && c.pocet === (s.priccek > 0 ? `${s.priccek} ${plPricek(s.priccek)}` : null) && c.pressed === (c.set === 'bez' ? 'true' : 'false') && !c.disabled;
  })), sp.karty[0].chipy.map(c => [c.set, c.cena, c.pocet, c.pressed]));
  const sety8 = P0.skupiny[0];
  over('B4 radek "Vsechny police a suplíky" NEEXISTUJE (v4.1, Robert: "multibox pricky tam nechci"): v panelu neni .pr-all, zadny cip s data-cil="vse", ani text "Vsechny police"; set se vybira jen po skupinach (kazda skupina ma vlastni cipy)', !sp.vseRadek && !/Všechny police/.test(sp.text)
    && sp.karty.length === P0.skupiny.length && sp.karty.length > 1 && sp.karty.every(k => k.chipy.length > 0), { vse: sp.vseRadek, text: sp.text.slice(0, 160) });
  over('B4b uvodni text sekce uz neodkazuje na "vsechny" a rika, ze se vybrana skupina zvyrazni a boxy vysunou', await page.evaluate(() => { const t = (document.querySelector('#prickyPanel .pr-sub') || {}).textContent || ''; return /zvýrazn/.test(t) && /vysunou/.test(t) && !/všechn/i.test(t); }), await page.evaluate(() => (document.querySelector('#prickyPanel .pr-sub') || {}).textContent));
  over('B5 miniatura cipu = RADA MALYCH BOXU: tolik obdelniku, kolik ma skupina boxu, a tolik car pricek, kolik je soucet po_boxech setu (bez = 0); miniatury ruznych mixu se lisi (rozdil je videt na prvni pohled)', sp.karty[0].chipy.every(c => c.boxu === sety8.boxy.length && c.car === sety8.sety[c.set].po_boxech.reduce((a, b) => a + b, 0))
    && new Set(sp.karty[0].chipy.map(c => c.svg)).size === sp.karty[0].chipy.length, sp.karty[0].chipy.map(c => [c.set, c.boxu, c.car]));
  over('B6 pred vyberem: banner = cena zbozi, zadne radky priccek, QR bez pr; patička "Pricky nejsou vybrane"', mp0.banner === fmtK(NET_ZBOZI) + ' Kč' && mp0.radky.length === 0 && !/pr=/.test(mp0.qr || '') && /Příčky nejsou vybrané/.test(sp.paticka), { mp0, pat: sp.paticka });

  // --- klik na cip jedne skupiny: set (mix) = pocty pricek v boxech podle po_boxech
  await klik(page, 's1', 'mix1');
  sp = await stavPanelu(page);
  vyb = vyberSetu(P0, { s1: 'mix1' });
  e = vypocet(P0, vyb);
  const s1m1 = sumSk(P0, 's1', vyb);
  over('B7 klik na "Mix 1" skupiny s1: plugin dostal setGroup(s1, mix1), plugin drzi pocty po boxech podle po_boxech (6,1,6,1,...); cip je aktivni jen u s1 / mix1; ostatni skupiny zustanou na "Bez pricek"', (await volani(page)).includes('setGroup:s1:mix1')
    && JSON.stringify(await pluginVyber(page)) === JSON.stringify(vyb) && sp.karty[0].chipy.find(c => c.set === 'mix1').pressed === 'true' && sp.karty[0].chipy.filter(c => c.pressed === 'true').length === 1 && sp.karty.slice(1).every(k => k.chipy.find(c => c.set === 'bez').pressed === 'true'), { v: await volani(page), s1: sp.karty[0].chipy.map(c => c.pressed), vyb });
  over('B8 souhrn karty "N pricek · X Kc bez DPH" (bez stitku vlastni kombinace; cena = cena setu z payloadu), patička "Pricky celkem: N ks · X Kc bez DPH", odznak v zahlavi', sp.karty[0].souhrn === `${s1m1.priccek} ${plPricek(s1m1.priccek)} · ${fmtK(s1m1.cena)} Kč bez DPH` && !sp.karty[0].vlastni && sp.karty[1].souhrn === 'Bez příček'
    && sp.paticka.includes(`Příčky celkem: ${e.kusu} ks · ${fmtK(e.pricky)} Kč bez DPH`) && sp.odznak === `${e.kusu} ks · ${fmtK(e.pricky)} Kč` && s1m1.cena === P0.skupiny[0].sety.mix1.cena && s1m1.priccek === P0.skupiny[0].sety.mix1.priccek, { souhrn: sp.karty[0].souhrn, pat: sp.paticka, odz: sp.odznak });
  sc = await ceny(page);
  over('B9 cenova tabulka: radky po dilech (nazev, ks, cena/ks, celkem) v samostatnem <tbody> mezi zbozim a dopravou, cislovani navazuje na radky zbozi', radkyOk(sc.radky, e, sc.zakladRadku) && sc.pocetTbody === 3 && e.radky.length >= 1, { radky: sc.radky, ocek: e.radky, zakl: sc.zakladRadku });
  over('B10 banner = zbozi + pricky (bez DPH), rozpis nese "pricky bez DPH", k uhrade vc. DPH a castka QR = stejne cislo jako vzorec serveru', sc.banner === fmtK(e.total) + ' Kč' && sc.detail.includes('zboží bez DPH ' + fmtK(NET_ZBOZI) + ' Kč')
    && sc.detail.includes('příčky bez DPH ' + fmtK(e.pricky) + ' Kč') && !/multibox/i.test(sc.detail) && sc.vat.includes('k úhradě vč. DPH ' + fmtK(e.gross) + ' Kč') && sc.qrAmount === fmtK(e.gross) + ' Kč', { sc, ocek: e });
  await page.waitForTimeout(150);
  over('B11 QR url dostane ?pr= PO BOXECH ("b01:6,b02:1,..." jen n > 0, serazeno podle cisla boxu, procento-kodovany) a ?qty=1', (await qrPr(page)) === retezec(vyb) && /qty=1/.test(sc.qr) && (await qrPr(page)).split(',').length === idsSk('s1').length, sc.qr);

  // --- jiny mix PREPISE predchozi (zadne scitani)
  await H.na3D(page, false); await page.waitForTimeout(200);
  await klik(page, 's1', 'mix3');
  sp = await stavPanelu(page);
  vyb = vyberSetu(P0, { s1: 'mix3' });
  e = vypocet(P0, vyb);
  sc = await ceny(page);
  over('B12 jiny mix PREPISE predchozi (mix3 po mix1, zadne scitani): pocty v boxech podle po_boxech mixu 3, cip mix3 aktivni a mix1 ne, cena a ?pr= odpovidaji jen mixu 3', JSON.stringify(await pluginVyber(page)) === JSON.stringify(vyb) && sp.karty[0].chipy.find(c => c.set === 'mix3').pressed === 'true'
    && sp.karty[0].chipy.find(c => c.set === 'mix1').pressed === 'false' && sc.banner === fmtK(e.total) + ' Kč' && (await qrPr(page)) === retezec(vyb) && radkyOk(sc.radky, e, sc.zakladRadku), { vyb, banner: sc.banner });

  // --- set ve VSECH skupinach, ale po jedne (radek "Vsechny" uz neni)
  await H.na3D(page, false); await page.waitForTimeout(200);
  for (const g of P0.skupiny) await klik(page, g.id, 'mix2');
  sp = await stavPanelu(page);
  const vsechny = Object.fromEntries(P0.skupiny.map(g => [g.id, 'mix2']));
  vyb = vyberSetu(P0, vsechny);
  e = vypocet(P0, vyb);
  const volB13 = await volani(page);
  over('B13 Mix 2 vybrany postupne u kazde skupiny (zadny hromadny set): plugin dostal setGroup(sN, mix2) pro kazdou skupinu a nikdy setAll, plugin drzi pocty vsech skupin, aktivni cip mix2 u vsech skupin, patička sedi', P0.skupiny.every(g => volB13.includes(`setGroup:${g.id}:mix2`)) && !volB13.some(v => v.startsWith('setAll'))
    && JSON.stringify(await pluginVyber(page)) === JSON.stringify(vyb) && sp.karty.every(k => k.chipy.find(c => c.set === 'mix2').pressed === 'true') && sp.paticka.includes(`Příčky celkem: ${e.kusu} ks · ${fmtK(e.pricky)} Kč bez DPH`), { v: volB13, pat: sp.paticka });
  sc = await ceny(page);
  over('B14 radky tabulky se agregovaly pres boxy a skupiny (soucet poctu pricek podle dilu), banner a ?pr= = vsech 22 boxu s jejich pocty', radkyOk(sc.radky, e, sc.zakladRadku) && sc.banner === fmtK(e.total) + ' Kč' && (await qrPr(page)) === retezec(vyb), { radky: sc.radky, ocek: e.radky, banner: sc.banner });

  // --- hover nad kartou = highlightGroup
  await H.na3D(page, false); await page.waitForTimeout(200);
  await page.hover('#prickyPanel .pr-card[data-skupina="s2"] h4');
  await page.waitForTimeout(100);
  const hlA = (await volani(page)).filter(v => v.startsWith('highlightGroup'));
  await page.mouse.move(5, 5);
  await page.waitForTimeout(100);
  const hlB = (await volani(page)).filter(v => v.startsWith('highlightGroup'));
  over('B15 najeti na kartu skupiny zvyrazni skupinu ve 3D (highlightGroup(s2)), odjeti zvyrazneni zrusi (highlightGroup(null))', hlA.includes('highlightGroup:s2') && hlB[hlB.length - 1] === 'highlightGroup:', { hlA, hlB });

  // --- Bez pricek: jedna skupina, pak dalsi
  await klik(page, 's1', 'bez');
  sp = await stavPanelu(page);
  const vyb2 = vyberSetu(P0, { s2: 'mix2', s3: 'mix2' });
  over('B16 "Bez pricek" u jedne skupiny vynuluje jen jeji boxy (ostatni skupiny zustanou)', JSON.stringify(await pluginVyber(page)) === JSON.stringify(vyb2) && sp.karty[0].chipy.find(c => c.set === 'bez').pressed === 'true', { v: await pluginVyber(page) });
  await klik(page, 's2', 'bez'); await klik(page, 's3', 'bez');
  sc = await ceny(page);
  over('B17 "Bez pricek" u vsech skupin (po jedne): vyber prazdny, banner zpet na cenu zbozi, zadne radky priccek, QR bez pr', sc.banner === fmtK(NET_ZBOZI) + ' Kč' && sc.radky.length === 0 && !/pr=/.test(sc.qr) && Object.keys(await pluginVyber(page)).length === 0, sc);
  await snimek(page, 'test_desktop_mixy.png');
  await r.browser.close();

  // ======================================================== M) sety jen z g.sety, vlastni kombinace z ulozeni, rozpoznani setu
  {
    // skupina s 2 boxy bez Mix 3, skupina s 1 boxem jen bez + plny (syntetika: jen to, co stranka cte - po_boxech, sety, boxy skupiny)
    const P = upravP(P => {
      const g2 = P.skupiny[1], g3 = P.skupiny[2];
      g2.boxy = g2.boxy.slice(0, 2); g2.boxu = 2; Object.keys(g2.sety).forEach(sid => { g2.sety[sid].po_boxech = g2.sety[sid].po_boxech.slice(0, 2); }); delete g2.sety.mix3;
      g3.boxy = g3.boxy.slice(0, 1); g3.boxu = 1; Object.keys(g3.sety).forEach(sid => { g3.sety[sid].po_boxech = g3.sety[sid].po_boxech.slice(0, 1); if (sid !== 'bez' && sid !== 'pln') delete g3.sety[sid]; });
    });
    r = await H.otevri({ data: H.nabidka({ pricky: P }) }); page = r.page;
    await H.na3D(page);
    sp = await stavPanelu(page);
    over('M1 cipy jen pro sety, ktere skupina ma v g.sety (v poradi payload.sety): 8 boxu = vsech 6, 2 boxy = bez Mix 3, 1 box = jen "Bez pricek" a "Plny set"', sp.karty[0].chipy.map(c => c.set).join() === SETY_ID.join() && sp.karty[1].chipy.map(c => c.set).join() === 'bez,mix1,mix2,mix4,pln' && sp.karty[2].chipy.map(c => c.set).join() === 'bez,pln', sp.karty.map(k => k.chipy.map(c => c.set).join('/')));
    over('M2 miniatura boxu u skupin ruzne velikosti: 2 a 1 maly box (a 8 u prvni skupiny)', sp.karty[0].chipy.every(c => c.boxu === 8) && sp.karty[1].chipy.every(c => c.boxu === 2) && sp.karty[2].chipy.every(c => c.boxu === 1), { b: sp.karty.map(k => k.chipy[0].boxu) });
    for (const g of P.skupiny) await klik(page, g.id, 'pln');
    sp = await stavPanelu(page);
    const vP = vyberSetu(P, { s1: 'pln', s2: 'pln', s3: 'pln' });
    const volM3 = await volani(page);
    over('M3 Plny set u skupin ruzne velikosti (po jedne): kazdy box ma max pricek, plugin setGroup(sN, pln), pocty po boxech sedi (8 + 2 + 1 boxu)', ['s1', 's2', 's3'].every(g => volM3.includes(`setGroup:${g}:pln`)) && JSON.stringify(await pluginVyber(page)) === JSON.stringify(vP) && Object.keys(vP).length === 11 && sp.karty.every(k => k.chipy.find(c => c.set === 'pln').pressed === 'true'), { v: await pluginVyber(page) });
    await r.browser.close();
  }
  // ulozeny vyber, ktery presne odpovida setu -> cip aktivni; ktery zadnemu neodpovida -> zadny cip, "Vlastni kombinace", cena se pocita
  vyb = vyberSetu(P0, { s1: 'mix3' });
  r = await H.otevri({ ls: { v: 2, boxy: vyb } }); page = r.page;
  await H.na3D(page);
  sp = await stavPanelu(page);
  over('M4 ulozeny vyber presne odpovidajici setu ("Mix 3" u s1) = cip Mix 3 je aktivni, souhrn bez stitku "Vlastni kombinace"', sp.karty[0].chipy.find(c => c.set === 'mix3').pressed === 'true' && sp.karty[0].chipy.filter(c => c.pressed === 'true').length === 1 && !sp.karty[0].vlastni && !sp.karty[0].souhrn.startsWith('Vlastní'), { chipy: sp.karty[0].chipy.map(c => [c.set, c.pressed]), souhrn: sp.karty[0].souhrn });
  await r.browser.close();
  const vlastni = { [idsSk('s1')[0]]: 2, [idsSk('s1')[1]]: 5, [idsSk('s2')[2]]: 1 };
  r = await H.otevri({ ls: { v: 2, boxy: vlastni } }); page = r.page;
  await H.na3D(page);
  sp = await stavPanelu(page);
  e = vypocet(P0, vlastni);
  sc = await ceny(page);
  const sk1v = sumSk(P0, 's1', vlastni);
  over('M5 ulozeny vyber, ktery zadnemu setu neodpovida (po_boxech jinak): ZADNY cip skupiny neni aktivni, souhrn "Vlastni kombinace · N pricek · X Kc", cena a ?pr= se presto pocitaji', sp.karty[0].chipy.every(c => c.pressed === 'false') && sp.karty[0].vlastni && sp.karty[0].souhrn === `Vlastní kombinace · ${sk1v.priccek} ${plPricek(sk1v.priccek)} · ${fmtK(sk1v.cena)} Kč bez DPH`
    && sp.karty[1].vlastni && sc.banner === fmtK(e.total) + ' Kč' && (await qrPr(page)) === retezec(vlastni) && radkyOk(sc.radky, e, sc.zakladRadku), { souhrn: sp.karty[0].souhrn, banner: sc.banner, pr: await qrPr(page) });
  await H.na3D(page);
  await klik(page, 's1', 'mix1');
  sp = await stavPanelu(page);
  over('M6 klik na cip PREPISE vlastni kombinaci skupiny (s1 -> Mix 1, ostatni skupiny zustanou): cip aktivni, stitek "Vlastni kombinace" u s1 pryc, u s2 zustava', sp.karty[0].chipy.find(c => c.set === 'mix1').pressed === 'true' && !sp.karty[0].vlastni && sp.karty[1].vlastni
    && JSON.stringify(await pluginVyber(page)) === JSON.stringify(Object.fromEntries(Object.entries(Object.assign({}, vyberSetu(P0, { s1: 'mix1' }), { [idsSk('s2')[2]]: 1 })).sort((a, b) => parseInt(a[0].slice(1), 10) - parseInt(b[0].slice(1), 10)))), { v: await pluginVyber(page) });
  await r.browser.close();

  // ======================================================== C) kanonicky retezec (poradi podle CISLA boxu: b2 < b9 < b10, ne abecedne) - id boxu bez uvodni nuly
  {
    const P = upravP(P => { const mapa = {}; P.boxy.forEach(b => { const n = 'b' + parseInt(b.id.slice(1), 10); mapa[b.id] = n; b.id = n; }); P.skupiny.forEach(g => { g.boxy = g.boxy.map(id => mapa[id]); }); });
    r = await H.otevri({ data: H.nabidka({ pricky: P }), ls: { v: 2, boxy: { b10: 1, b2: 1, b9: 2, b21: 1, b3: 3 } } }); page = r.page;
    await H.skocNaSlide(page, 'pricing'); await page.waitForTimeout(200);
    const qrC = await qrPr(page);
    over('C1 kanonicky retezec je serazen podle CISLA boxu (b2, b3, b9, b10, b21 - ne abecedne b10 pred b2), jen n > 0', qrC === 'b2:1,b3:3,b9:2,b10:1,b21:1', qrC);
    await vyplnAccept(page); await page.click('#btnAccept'); await page.waitForTimeout(400);
    over('C2 accept dostane pole pricky se stejnym retezcem', r.accepts[0] && r.accepts[0].pricky === 'b2:1,b3:3,b9:2,b10:1,b21:1', r.accepts[0]);
    await r.browser.close();
  }

  // ======================================================== D) mnozstvi, montaz %, zaloha, hide_bom_prices
  r = await H.otevri({}); page = r.page;
  await H.na3D(page);
  await klik(page, 's1', 'mix4'); await klik(page, 's2', 'pln'); await klik(page, 's3', 'mix2');
  vyb = vyberSetu(P0, { s1: 'mix4', s2: 'pln', s3: 'mix2' });
  const sD0 = await stavCeny(page), eD0 = vypocet(P0, vyb);
  over('D0 zmena vyberu prepocte DOM cenove stranky hned (stitek tlacitka montaze z castky vcetne priccek, banner), i bez prepnuti slidu - tisk / PDF cte DOM jak je', !!sD0.montazBtn && sD0.montazBtn.includes(fmtK(eD0.items * 10 / 100) + ' Kč bez DPH') && sD0.banner === fmtK(eD0.total) + ' Kč', sD0);
  await H.naCeny(page);
  await page.click('#qtyPlus'); await page.click('#qtyPlus'); await page.waitForTimeout(250);
  e = vypocet(P0, vyb, { qty: 3 });
  sc = await stavCeny(page);
  over('D1 mnozstvi 3: banner = (zbozi + pricky) x 3, rozpis "3 ks x ... + pricky", QR ?qty=3&pr=...', sc.banner === fmtK(e.total) + ' Kč' && sc.detail.includes('3 ks × ' + fmtK(NET_ZBOZI) + ' Kč bez DPH ' + fmtK(NET_ZBOZI * 3) + ' Kč')
    && sc.detail.includes('příčky bez DPH ' + fmtK(e.pricky * 3) + ' Kč') && /qty=3/.test(sc.qr) && (await qrPr(page)) === retezec(vyb), { sc, ocek: e });
  over('D2 radky tabulky zustavaji za JEDEN kus sestavy (jako ostatni radky), nasobi je az mnozstvi v souctu', sc.radky.length === e.radky.length && sc.radky.map(x => x[3]).join() === (e.radky.map(x => x.qty + ' ks').join()), sc.radky);
  await H.naSlide(page, 'view_3d'); await page.waitForTimeout(250);
  sp = await stavPanelu(page);
  over('D2b patička sekce po zmene mnozstvi ukazuje i nasobek ("Pri 3 ks sestavy: N ks · X Kc bez DPH")', sp.paticka.includes(`Při 3 ks sestavy: ${e.kusu * 3} ks · ${fmtK(e.pricky * 3)} Kč bez DPH`), sp.paticka);
  await H.naCeny(page); await page.waitForTimeout(150);
  // montaz %
  const pred = await stavCeny(page);
  over('D3 informace o montazi (sazba z castky VCETNE priccek x 3 ks): "Montaz 10 % z ceny ... " ukazuje spravnou cenu', pred.montazInfo && pred.montazInfo.includes(fmtK(e.items * 10 / 100) + ' Kč bez DPH'), { info: pred.montazInfo, ocek: e.items * 0.1 });
  over('D3b stitek tlacitka montaze "Montaz (+ ...)" pocita z castky vcetne priccek', pred.montazBtn && pred.montazBtn.includes(fmtK(e.items * 10 / 100) + ' Kč bez DPH'), pred.montazBtn);
  await page.click('#montazOnBtn'); await page.waitForTimeout(250);
  const em = vypocet(P0, vyb, { qty: 3, montaz: true });
  sc = await stavCeny(page);
  over('D4 zapnuta montaz (sestava do auta): celkem = (zbozi + pricky) x 3 + montaz 10 % z teto castky, rozpis nese "montaz bez DPH", k uhrade vc. DPH sedi s vzorcem serveru',
    sc.banner === fmtK(em.total) + ' Kč' && sc.detail.includes('montáž bez DPH ' + fmtK(em.montazNet) + ' Kč') && sc.vat.includes('k úhradě vč. DPH ' + fmtK(em.gross) + ' Kč') && sc.qrAmount === fmtK(em.gross) + ' Kč', { sc, ocek: em });
  // zaloha
  await page.click('.opt-btn[data-field="payment_method"][data-val="zaloha"]'); await page.waitForTimeout(250);
  sc = await stavCeny(page);
  over('D5 zalohova platba pocita procento z castky vcetne priccek i montaze (zaloha 70 %: text i QR castka)', /70 % = /.test(sc.deposit) && sc.deposit.includes(fmtK(em.gross * 0.7) + ' Kč') && sc.qrAmount.includes(fmtK(em.gross * 0.7) + ' Kč') && /deposit_pct=70/.test(sc.qr), sc);
  await page.waitForTimeout(800);
  over('D5b vyber priccek se NEposila v order-prefs (volby objednavky nesou jen doprava / platba / qty / montaz, nic o pricky)', r.posty.length > 0 && r.posty.every(b => !Object.keys(b).some(k => /pricky|^pr$|skupin|^set|boxy/i.test(k)) && !/pricky/i.test(JSON.stringify(b)) && !/b\d\d:/.test(JSON.stringify(b))), r.posty.slice(-1));
  await r.browser.close();

  // hide_bom_prices: tabulka bez cenovych sloupcu -> radky priccek taky
  r = await H.otevri({ data: H.nabidka({ uprava: d => { d.offer_options.hide_bom_prices = true; } }) });
  await H.na3D(r.page); await klik(r.page, 's2', 'pln');
  sc = await ceny(r.page);
  over('D6 hide_bom_prices: radky priccek maji jen 4 bunky (bez Cena/ks a Celkem), celkem je v banneru', sc.radky.length >= 1 && sc.radky.every(x => x.length === 4) && sc.banner === fmtK(vypocet(P0, vyberSetu(P0, { s2: 'pln' })).total) + ' Kč', sc);
  await r.browser.close();

  // ======================================================== E) prijeti nabidky
  r = await H.otevri({}); page = r.page;
  await H.na3D(page); await klik(page, 's1', 'mix3'); await klik(page, 's2', 'pln'); await klik(page, 's3', 'mix4');
  vyb = vyberSetu(P0, { s1: 'mix3', s2: 'pln', s3: 'mix4' });
  await H.naCeny(page);
  await vyplnAccept(page); await page.click('#btnAccept'); await page.waitForTimeout(500);
  over('E1 telo accept nese pole pricky = kanonicky retezec vyberu PO BOXECH ("b01:6,b02:6,b03:1,...") vedle firemnich udaju', r.accepts.length === 1 && r.accepts[0].pricky === retezec(vyb) && r.accepts[0].name === 'Jan Test' && r.accepts[0].company_ico === '12345678', r.accepts[0]);
  await H.naSlide(page, 'view_3d');
  sp = await stavPanelu(page);
  over('E2 po uspesnem prijeti je vyber jen ke cteni: cipy zakazane, vyber zustane videt (aktivni cipy), poznamka "Nabidka je objednana"', sp.karty.every(k => k.chipy.every(c => c.disabled))
    && sp.karty[0].chipy.find(c => c.set === 'mix3').pressed === 'true' && sp.karty[1].chipy.find(c => c.set === 'pln').pressed === 'true' && sp.karty[2].chipy.find(c => c.set === 'mix4').pressed === 'true' && /Nabídka je objednaná/.test(sp.text), { karty: sp.karty.map(k => k.chipy.map(c => [c.pressed, c.disabled])), text: sp.text.slice(-120) });
  const zmenaVol = async () => (await volani(page)).filter(v => /^(setGroup|setAll|setBox|clear)/.test(v)).length;
  const volPred = await zmenaVol();
  const playPred = (await playLog(page)).length;
  await page.click('#prickyPanel .pr-chip[data-cil="s3"][data-set="pln"]', { force: true }).catch(() => {});
  await page.waitForTimeout(300);
  over('E3 klik na zakazany cip nic nezmeni (zadne volani setGroup/setAll/setBox/clear, zadne vysunuti boxu viewer.play, stejna cena)', (await zmenaVol()) === volPred && (await playLog(page)).length === playPred && (await ceny(page)).banner === fmtK(vypocet(P0, vyb).total) + ' Kč', { vol: await zmenaVol(), volPred, playPred });
  await r.browser.close();

  // nabidka uz objednana pri nacteni (offer.accepted) + ulozeny vyber
  r = await H.otevri({ ls: { v: 2, boxy: vyberSetu(P0, { s1: 'mix2' }) }, data: H.nabidka({ uprava: d => { d.accepted = { name: 'Jan Test', accepted_at: '2026-10-06T10:00:00' }; } }) });
  await H.na3D(r.page);
  sp = await stavPanelu(r.page);
  over('E4 nabidka objednana uz pri nacteni: sekce je jen ke cteni (cipy zakazane), ulozeny vyber je videt (Mix 2 aktivni), cena ho zahrnuje', sp.karty.every(k => k.chipy.every(c => c.disabled)) && sp.karty[0].chipy.find(c => c.set === 'mix2').pressed === 'true'
    && (await ceny(r.page)).banner === fmtK(vypocet(P0, vyberSetu(P0, { s1: 'mix2' })).total) + ' Kč', sp.karty[0].chipy.map(c => c.pressed));
  await r.browser.close();

  // ======================================================== F) localStorage {v:2, boxy}
  const lsF = { [idsSk('s1')[0]]: 3, [idsSk('s2')[1]]: 1, [idsSk('s3')[0]]: 6 };
  r = await H.otevri({ ls: { v: 2, boxy: lsF } }); page = r.page;
  await H.skocNaSlide(page, 'pricing');
  sc = await stavCeny(page);
  const mo0F = await mounty(page);
  e = vypocet(P0, lsF);
  over('F1 platny ulozeny vyber ({v:2, boxy}) se projevi hned pri prvnim vykresleni ceny (i bez otevreni 3D): banner, radky tabulky, QR pr', sc.banner === fmtK(e.total) + ' Kč' && radkyOk(sc.radky, e, sc.zakladRadku) && (await qrPr(page)) === retezec(lsF) && mo0F.length === 0, { sc, mo0F });
  await H.na3D(page);
  sp = await stavPanelu(page);
  const vF = await volani(page);
  over('F2 po otevreni 3D slidu jsou skupiny "Vlastni kombinace" (zadny cip), plugin dostal setMany (pred modelem i po nem) a clear, plugin drzi presne ulozene pocty po boxech', sp.karty.every(k => k.vlastni && k.chipy.every(c => c.pressed === 'false')) && vF.filter(v => v.startsWith('setMany:')).length >= 2 && vF.includes('clear')
    && JSON.stringify(await pluginVyber(page)) === JSON.stringify(Object.fromEntries(Object.entries(lsF).sort((a, b) => parseInt(a[0].slice(1), 10) - parseInt(b[0].slice(1), 10)))), { v: vF, vlastni: sp.karty.map(k => k.vlastni) });
  // preziti reloadu: zmena (klik na mix) -> reload
  await klik(page, 's2', 'mix1');
  const ulozeno = await lsHodnota(page);
  const ocekLs = Object.assign({}, { [idsSk('s1')[0]]: 3, [idsSk('s3')[0]]: 6 }, vyberSetu(P0, { s2: 'mix1' }));
  over('F3 zmena vyberu se ulozi do localStorage (pricky:<token>) jako {v:2, boxy:{id: n}} (jen n > 0; klik na mix prepsal boxy skupiny s2)', ulozeno && JSON.parse(ulozeno).v === 2 && JSON.stringify(Object.entries(JSON.parse(ulozeno).boxy).sort()) === JSON.stringify(Object.entries(ocekLs).sort()) && !('vyber' in JSON.parse(ulozeno)), ulozeno);
  await page.reload(); await page.waitForSelector('#deck.show'); await page.waitForTimeout(400);
  sc = await ceny(page);
  over('F4 po obnoveni stranky (reload) vyber zustane (cena i radky)', sc.banner === fmtK(vypocet(P0, ocekLs).total) + ' Kč', sc.banner);
  await H.na3D(page);
  for (const g of P0.skupiny) await klik(page, g.id, 'bez');
  over('F5 "Bez pricek" u vsech skupin (po jedne) smaze polozku z localStorage', (await lsHodnota(page)) === null, await lsHodnota(page));
  await r.browser.close();

  for (const [nazev, ls, ocek] of [
    ['F6 poskozene JSON v localStorage se ignoruje (zadna chyba, cena zbozi)', '{"v":2,"boxy":{"b01":', {}],
    ['F7 stary format v1 (sety po skupinach {v:1, vyber:{s1:"zak"}}) se ignoruje', { v: 1, vyber: { s1: 'zak' } }, {}],
    ['F8 castecne neplatny vyber: neznamy box, n nad max, zaporne, nula, desetinne, text, cizi klic se zahodi, platna polozka zustane', `{"v":2,"boxy":{"${b01}":3,"b99":2,"${b02}":${maxP(P0, b02) + 1},"${b03x}":-1,"${b04}":0,"${b05}":1.5,"${b06}":"2","__proto__":3,"constructor":2}}`, { [b01]: 3 }],
    ['F9 ulozeni v nespravnem tvaru (boxy jako pole / chybi boxy) se ignoruje', { v: 2, boxy: [3] }, {}],
  ]) {
    r = await H.otevri({ ls });
    sc = await ceny(r.page);
    await H.na3D(r.page);
    sp = await stavPanelu(r.page);
    const okCena = sc.banner === fmtK(vypocet(P0, ocek).total) + ' Kč';
    const okPlugin = JSON.stringify(await pluginVyber(r.page)) === JSON.stringify(ocek);
    over(nazev, okCena && okPlugin && r.chyby.length === 0, { banner: sc.banner, ocek: vypocet(P0, ocek).total, plugin: await pluginVyber(r.page), chyby: r.chyby });
    await r.browser.close();
  }

  // ======================================================== G) chyby: plugin, model, skupiny / boxy bez 3D, neplatny payload
  r = await H.otevri({ plugin: '404', ls: { v: 2, boxy: { [b01]: 2 } } });
  await H.skocNaSlide(r.page, 'pricing');
  sc = await stavCeny(r.page);
  const predG = sc.banner;
  await H.na3D(r.page, false); await r.page.waitForTimeout(500);
  sp = await stavPanelu(r.page);
  const moG = await mounty(r.page);
  sc = await ceny(r.page);
  over('G1 plugin se nenacte (404): sekce zustane skryta, 3D se presto namountuje (bez plugins), ulozeny vyber se zahodi a cena je zpet jen zbozi, zadna chyba ve strance', sp && sp.hidden === true && moG.length === 1 && moG[0].plugins === null
    && predG === fmtK(vypocet(P0, { [b01]: 2 }).total) + ' Kč' && sc.banner === fmtK(NET_ZBOZI) + ' Kč' && sc.radky.length === 0 && r.chyby.length === 0, { sp: sp && sp.hidden, moG, predG, po: sc.banner, chyby: r.chyby });
  await r.browser.close();

  r = await H.otevri({ init: ['window.__v3dChyba = true'], ls: { v: 2, boxy: { [idsSk('s2')[0]]: 4 } } });
  await H.naSlide(r.page, 'view_3d'); await r.page.waitForTimeout(700);
  sp = await stavPanelu(r.page);
  sc = await ceny(r.page);
  over('G2 model 3D selze (ready se odmitne): sekce skryta, vyber zahozen, cena zbozi, dvoudimenzionalni nahledy zustanou', sp.hidden === true && sc.banner === fmtK(NET_ZBOZI) + ' Kč' && r.chyby.length === 0, { sp: sp.hidden, banner: sc.banner, chyby: r.chyby });
  await r.browser.close();

  r = await H.otevri({ init: [`window.__prNeready = ${JSON.stringify(P0.skupiny.map(g => g.id))}`] });
  await H.naSlide(r.page, 'view_3d'); await r.page.waitForTimeout(600);
  sp = await stavPanelu(r.page);
  over('G3 plugin nenasel ve 3D zadnou skupinu: sekce se neukaze', sp.hidden === true && sp.karty.length === 0, sp);
  await r.browser.close();

  r = await H.otevri({ init: ['window.__prNeready = ["s2"]'], ls: { v: 2, boxy: { [b01]: 2, [idsSk('s2')[0]]: 4 } } });
  await H.na3D(r.page);
  sp = await stavPanelu(r.page);
  sc = await ceny(r.page);
  over('G4 skupina, kterou plugin ve 3D nenasel (s2), se nenabizi a jeji ulozeny vyber se zahodi; zbyle skupiny funguji', sp.karty.map(k => k.id).join() === P0.skupiny.map(g => g.id).filter(id => id !== 's2').join() && sc.banner === fmtK(vypocet(P0, { [b01]: 2 }).total) + ' Kč', { karty: sp.karty.map(k => k.id), banner: sc.banner });
  await r.browser.close();

  r = await H.otevri({ init: [`window.__prNeready = ${JSON.stringify([b03x])}`], ls: { v: 2, boxy: { [b03x]: 2, [b01]: 1 } } });
  await H.na3D(r.page);
  sp = await stavPanelu(r.page);
  sc = await ceny(r.page);
  const gm = skP(P0, 's1'), idxX = gm.boxy.indexOf(b03x);
  const cenaM1 = gm.sety.mix1.cena - gm.sety.mix1.po_boxech[idxX] * jednP(P0, b03x);               // cena Mixu 1 bez nenalezeneho boxu
  over('G5 jediny box, ktery plugin ve 3D nenasel, se nepocita: skupina ma o box min (titulek, miniatura), jeho ulozeny pocet se zahodi a cip "Mix 1" ukazuje cenu jen za boxy ve 3D', sp.karty[0].nadpis === `${P0.skupiny[0].popis} · ${idsSk('s1').length - 1} ${plBoxu(idsSk('s1').length - 1)}`
    && sp.karty[0].chipy.every(c => c.boxu === idsSk('s1').length - 1) && sc.banner === fmtK(vypocet(P0, { [b01]: 1 }).total) + ' Kč' && sp.karty[0].chipy.find(c => c.set === 'mix1').cena === '+' + fmtK(cenaM1) + ' Kč', { nadpis: sp.karty[0].nadpis, banner: sc.banner, cena: sp.karty[0].chipy.find(c => c.set === 'mix1').cena, cenaM1 });
  await H.na3D(r.page, false); await r.page.waitForTimeout(200);
  await klik(r.page, 's1', 'mix1');
  const vS = vyberSetu(P0, { s1: 'mix1' }); delete vS[b03x];
  sc = await ceny(r.page);
  over('G5b zkratka-set u skupiny s nenalezenym boxem nastavi jen boxy ve 3D (cena a ?pr= bez nenalezeneho boxu)', sc.banner === fmtK(vypocet(P0, vS).total) + ' Kč' && (await qrPr(r.page)) === retezec(vS), { banner: sc.banner, pr: await qrPr(r.page) });
  await r.browser.close();

  for (const [nazev, data] of [
    ['G6 payload s enabled:false se na strance neprojevi (zadny panel, trida, tbody, plugin)', H.nabidka({ pricky: upravP(P => { P.enabled = false; }) })],
    ['G7 payload bez skupin je neplatny: stranka se chova jako bez priccek', H.nabidka({ pricky: upravP(P => { P.skupiny = []; }) })],
    ['G8 nabidka bez 3D modelu (has_3d_model:false) sekci nenabizi a ulozeny vyber ignoruje', H.nabidka({ uprava: d => { d.has_3d_model = false; } })],
    ['G9 payload bez pouzitelneho typu boxu (typy.<k>.max = 0): boxy se nenabizeji, zadna chyba, stranka se chova jako bez priccek', H.nabidka({ pricky: upravP(P => { Object.keys(P.typy).forEach(k => { P.typy[k].max = 0; }); }) })],
  ]) {
    r = await H.otevri({ data, ls: { v: 2, boxy: { [b01]: 1 } } });
    sc = await ceny(r.page);
    const stav = await r.page.evaluate(() => ({ panel: !!document.getElementById('prickyPanel'), trida: !!document.querySelector('.has-pricky'), tbody: !!document.getElementById('prickyTbody'), plugin: !!(window.__pr && window.__pr.created) }));
    over(nazev, !stav.panel && !stav.trida && !stav.tbody && !stav.plugin && sc.banner === fmtK(NET_ZBOZI) + ' Kč' && r.chyby.length === 0, { stav, banner: sc.banner });
    await r.browser.close();
  }
  // neplatne sety v payloadu: po_boxech spatne delky nebo n nad max se nenabizi (ostatni sety dal funguji)
  {
    const P = upravP(P => { const g = P.skupiny[0]; g.sety.mix2.po_boxech = g.sety.mix2.po_boxech.slice(0, 3); g.sety.mix3.po_boxech[0] = 99; g.sety.mix4.po_boxech[1] = -1; g.sety.pln.po_boxech[2] = 1.5; });
    r = await H.otevri({ data: H.nabidka({ pricky: P }) });
    await H.na3D(r.page);
    sp = await stavPanelu(r.page);
    over('G10 set s neplatnym po_boxech (spatna delka, n nad max, zaporne, desetinne) se u skupiny nenabizi, zbyle sety (bez, Mix 1) funguji; ostatni skupiny beze zmeny', sp.karty[0].chipy.map(c => c.set).join() === 'bez,mix1' && sp.karty[1].chipy.map(c => c.set).join() === SETY_ID.join() && r.chyby.length === 0, sp.karty.map(k => k.chipy.map(c => c.set).join('/')));
    await r.browser.close();
  }

  // ======================================================== H) nahled admina, XSS
  r = await H.otevri({ data: H.nabidka({ pricky: upravP(P => { P.nahled_admin = true; }) }) });
  await H.na3D(r.page);
  sp = await stavPanelu(r.page);
  over('H1 nahled_admin: pruh "Nahled pro zamestnance - karty pricek jeste nejsou aktivni" nad kartami', /Náhled pro zaměstnance – karty příček ještě nejsou aktivní/.test(sp.text) && (await r.page.evaluate(() => !!document.querySelector('#prickyPanel .pr-admin'))), sp.text.slice(0, 160));
  await r.browser.close();
  r = await H.otevri({});
  await H.na3D(r.page);
  over('H2 bez nahled_admin (aktivni karty) zadny pruh pro zamestnance', !(await r.page.evaluate(() => !!document.querySelector('#prickyPanel .pr-admin'))), null);
  await r.browser.close();

  const XSS = '<img src=x onerror="window.__xss=1">';
  r = await H.otevri({ data: H.nabidka({ pricky: upravP(P => {
    P.skupiny[0].popis = XSS + 'Police'; P.skupiny[1].popis = '<script>window.__xss=2</script>Suplik';
    P.sety[1].popis = XSS + 'Mix'; P.sety[1].pozn = '<b onmouseover="window.__xss=3">pozn</b>'; P.dily[0].nazev = XSS + 'Pricka'; P.typy['395x186'].popis = XSS;
    P.skupiny[0].g = '"><img src=x onerror="window.__xss=4">'; P.boxy[0].g = XSS;
  }) }) });
  await H.na3D(r.page);
  await klik(r.page, 's1', 'mix1');
  sc = await ceny(r.page);
  await r.page.waitForTimeout(300);
  const xss = await r.page.evaluate(() => ({ x: window.__xss, imgs: document.querySelectorAll('#prickyPanel img, #prickyTbody img').length, scripts: document.querySelectorAll('#prickyPanel script, #prickyTbody script').length,
    text: document.getElementById('prickyPanel').textContent.includes('<img src=x'), tabText: document.getElementById('prickyTbody').textContent.includes('<img src=x') }));
  over('H3 XSS: znacky v popis / nazev / pozn / g z payloadu se nespusti (zadne <img>/<script> v panelu ani tabulce, zobrazi se jako text)', xss.x === undefined && xss.imgs === 0 && xss.scripts === 0 && xss.text && xss.tabText, xss);
  await r.browser.close();

  // ======================================================== I) rozlozeni, mobil, tisk, navigace
  r = await H.otevri({ width: 1440, height: 900 }); page = r.page;
  await H.na3D(page);
  const lay = await page.evaluate(() => {
    const c = document.getElementById('viewer3dContainer').getBoundingClientRect(), p = document.getElementById('prickyPanel').getBoundingClientRect();
    return { cL: c.left, cR: c.right, cT: c.top, cB: c.bottom, pL: p.left, pR: p.right, pT: p.top, pB: p.bottom, vw: innerWidth, vh: innerHeight, open: document.querySelector('#prickyPanel details.pr-wrap').open };
  });
  over('I1 desktop: sekce je VEDLE 3D okna (vpravo, bez prekryvu), cela v sirce okna, rozbalena, nahore na stejne obrazovce jako model', lay.pL >= lay.cR - 1 && lay.pR <= lay.vw + 1 && lay.pT < lay.vh - 150 && lay.cT < lay.vh && lay.open, lay);
  await snimek(page, 'test_desktop.png');
  over('I2 panel ma vlastni rolovani (overflow-y auto, overscroll-behavior contain), aby kolecko v panelu nelistovalo stranky (viz I5-I7)', await page.evaluate(() => { const b = document.querySelector('#prickyPanel .pr-body'); return getComputedStyle(b).overflowY === 'auto' && getComputedStyle(b).overscrollBehaviorY === 'contain'; }), null);
  // navigace
  const okraj = await page.evaluate(() => { const s = document.querySelector('.slide.active'); s.scrollTop = s.scrollHeight; return s.scrollHeight > s.clientHeight; });
  await page.evaluate(() => document.querySelector('#prickyPanel .pr-chip').dispatchEvent(new WheelEvent('wheel', { deltaY: 400, bubbles: true, cancelable: true })));
  await page.waitForTimeout(900);
  const slW = await aktSlide(page);
  await page.evaluate(() => document.querySelector('.slide.active .slide-title').dispatchEvent(new WheelEvent('wheel', { deltaY: 400, bubbles: true, cancelable: true })));
  await page.waitForTimeout(900);
  const slW2 = await aktSlide(page);
  over('I5 kolecko mysi nad panelem priccek neprepne stranku (kontrola: stejne kolecko mimo panel stranku prepne)', slW === 'view_3d' && slW2 === 'pricing', { slW, slW2, okraj });
  await H.naSlide(page, 'view_3d'); await page.waitForTimeout(300);
  await page.focus('#prickyPanel .pr-chip'); await page.keyboard.press('ArrowRight'); await page.waitForTimeout(400);
  const slK = await aktSlide(page);
  await page.evaluate(() => document.activeElement.blur()); await page.keyboard.press('ArrowRight'); await page.waitForTimeout(500);
  const slK2 = await aktSlide(page);
  over('I6 sipka doprava pri zaostrenem cipu v panelu neprepne stranku (kontrola: mimo panel ano)', slK === 'view_3d' && slK2 === 'pricing', { slK, slK2 });
  await r.browser.close();

  r = await H.otevri({ width: 1100, height: 800, mobil: true }); page = r.page;
  await H.na3D(page);
  const swipe = (sel, dx) => page.evaluate(({ sel, dx }) => {
    const el = document.querySelector(sel), rc = el.getBoundingClientRect(), x = rc.left + rc.width / 2, y = rc.top + rc.height / 2;
    const t = (cx) => new Touch({ identifier: 1, target: el, clientX: cx, clientY: y });
    el.dispatchEvent(new TouchEvent('touchstart', { touches: [t(x)], changedTouches: [t(x)], bubbles: true }));
    el.dispatchEvent(new TouchEvent('touchend', { touches: [], changedTouches: [t(x + dx)], bubbles: true }));
  }, { sel, dx });
  await swipe('#prickyPanel .pr-chip', -160); await page.waitForTimeout(500);
  const slT = await aktSlide(page);
  await swipe('.slide.active .slide-title', -160); await page.waitForTimeout(600);
  const slT2 = await aktSlide(page);
  over('I7 tah prstem zacatkem v panelu priccek neprepne stranku (kontrola: tah mimo panel prepne)', slT === 'view_3d' && slT2 === 'pricing', { slT, slT2 });
  await r.browser.close();

  r = await H.otevri({ width: 360, height: 800, mobil: true }); page = r.page;
  await H.naSlide(page, 'view_3d'); await page.waitForSelector('#prickyPanel:not([hidden]) summary', { timeout: 20000 });
  const mob = await page.evaluate(() => {
    const p = document.getElementById('prickyPanel'), c = document.getElementById('viewer3dContainer').getBoundingClientRect(), pr = p.getBoundingClientRect(), d = p.querySelector('details.pr-wrap'), s = document.querySelector('.slide.active');
    return { pod: pr.top >= c.bottom - 2, open: d.open, sirka: pr.width, vw: innerWidth, docX: document.documentElement.scrollWidth, slideX: s.scrollWidth, slideCW: s.clientWidth, summaryViditelny: d.querySelector('summary').getBoundingClientRect().height > 10 };
  });
  over('I8 mobil 360 px: sekce je POD modelem na plnou sirku, vychozi stav sbaleny (rozbalitelny), bez vodorovneho posuvniku', mob.pod && !mob.open && mob.sirka <= mob.vw + 1 && mob.docX <= mob.vw + 1 && mob.slideX <= mob.slideCW + 1 && mob.summaryViditelny, mob);
  await page.click('#prickyPanel details.pr-wrap > summary'); await page.waitForTimeout(250);
  const mob2 = await page.evaluate(() => { const d = document.querySelector('#prickyPanel details.pr-wrap'), s = document.querySelector('.slide.active'); const prv = [...d.querySelectorAll('.pr-chip, .pr-chip svg')].map(b => b.getBoundingClientRect()); return { open: d.open, mimo: prv.filter(c => c.width > 0 && (c.right > innerWidth + 1 || c.left < -1)).length, prvku: prv.length, slideX: s.scrollWidth, slideCW: s.clientWidth }; });
  over('I9 mobil 360 px po rozbaleni: cipy (6 setu na skupinu) a jejich miniatury se vejdou do sirky (zadny mimo okno), stranka se nerozjede do sirky', mob2.open && mob2.mimo === 0 && mob2.prvku > 0 && mob2.slideX <= mob2.slideCW + 1, mob2);
  await snimek(page, 'test_mobil_3d.png');
  for (const g of P0.skupiny) await klik(page, g.id, 'mix2');
  await H.naCeny(page); await page.waitForTimeout(250);
  const mobC = await page.evaluate(() => { const s = document.querySelector('.slide.active'); return { slideX: s.scrollWidth, slideCW: s.clientWidth, docX: document.documentElement.scrollWidth, vw: innerWidth }; });
  over('I10 mobil 360 px: cenova stranka s radky priccek bez vodorovneho posuvniku', mobC.slideX <= mobC.slideCW + 1 && mobC.docX <= mobC.vw + 1, mobC);
  await snimek(page, 'test_mobil_ceny.png');
  await r.browser.close();

  r = await H.otevri({}); page = r.page;
  await H.na3D(page); for (const g of P0.skupiny) await klik(page, g.id, 'mix1');
  await page.emulateMedia({ media: 'print' });
  await page.waitForTimeout(200);
  const tisk = await page.evaluate(() => ({ panel: getComputedStyle(document.getElementById('prickyPanel')).display, radky: [...document.querySelectorAll('#prickyTbody tr')].map(tr => getComputedStyle(tr).display), tbody: getComputedStyle(document.getElementById('prickyTbody')).display }));
  over('I11 tisk: panel priccek se netiskne, radky priccek v cenove tabulce zustanou', tisk.panel === 'none' && tisk.radky.length >= 1 && tisk.radky.every(d => d !== 'none') && tisk.tbody !== 'none', tisk);
  await r.browser.close();

  // ======================================================== J) vzorec == server pro vice kombinaci (nezavisly vypocet)
  r = await H.otevri({}); page = r.page;
  await H.na3D(page);
  const kombinace = [
    { s1: 'bez', s2: 'pln', s3: 'mix4' },
    { s1: 'mix2', s2: 'mix2', s3: 'mix2' },
    { s1: 'pln', s2: 'mix3', s3: 'bez' },
    { s1: 'mix4', s2: 'mix1', s3: 'pln' },
  ];
  let shoda = true, detail = [];
  for (const k of kombinace) {
    await H.naSlide(page, 'view_3d');
    for (const g of Object.keys(k)) await klik(page, g, k[g]);
    const vyb3 = vyberSetu(P0, Object.fromEntries(Object.entries(k).filter(([, v]) => v !== 'bez')));
    const sv = await ceny(page);
    const ex = vypocet(P0, vyb3);
    const prQ = await qrPr(page);
    const ok = sv.banner === fmtK(ex.total) + ' Kč' && sv.vat.includes('k úhradě vč. DPH ' + fmtK(ex.gross) + ' Kč') && (prQ || '') === retezec(vyb3) && radkyOk(sv.radky, ex, sv.zakladRadku);
    if (!ok) { shoda = false; detail.push({ k, banner: sv.banner, ocek: ex.total, prQ, ocekPr: retezec(vyb3) }); }
  }
  over('J1 pro ruzne kombinace setu (4 kombinace x 3 skupiny) se banner, castka k uhrade, radky tabulky a ?pr= presne shoduji s nezavislym vypoctem vzorce serveru (items_net = zbozi + pricky, DPH 21 %)', shoda, detail);
  await r.browser.close();

  // ======================================================== L) jedna skupina (karta 4453: jeden suplik) - bez radku "Vsechny"
  if (H.maKartu('4453')) {
    r = await H.otevri({ karta: '4453' }); page = r.page;
    await H.na3D(page);
    sp = await stavPanelu(page);
    const P1 = H.payload('4453');
    await klik(page, 's1', 'mix2');
    sc = await ceny(page);
    const v1 = vyberSetu(P1, { s1: 'mix2' }), e1 = vypocet(P1, v1);
    over('L1 jedna skupina: jen jedna karta a zadny radek "Vsechny police a suplíky"; vyber funguje (cena, radky tabulky, ?pr= po boxech)', sp.karty.length === 1 && !sp.vseRadek && sc.radky.length === e1.radky.length && sc.banner === fmtK(e1.total) + ' Kč' && (await qrPr(page)) === retezec(v1), { karty: sp.karty.length, vse: sp.vseRadek, sc: sc.banner });
    await r.browser.close();
  } else console.log('SKIP L1 jedna skupina (chybi <OUT>/out2/4453.offer.glb: build_karty.py 4453)');

  // ======================================================== U) v5: ocelove SUPLIKY (druh skupiny "suplik"): nadpis sekce, slova, miniatura z rozmeru typu, sety, ceny, skryto (rucni scenare SPECY z harness_pricky.js)
  {
    const PD = H.payload('sup_dva'), PM = H.payload('smisene'), PJ = H.payload('sup_jeden'), PX = H.payload('sup_mix'), PH = H.payload('smisene_skryto');
    r = await H.otevri({ data: H.nabidka({ pricky: PD }) }); page = r.page;
    await H.na3D(page);
    sp = await stavPanelu(page);
    over('U1 jen suplíky: nadpis sekce "Příčky do šuplíků" (zahlavi i aria-label panelu), nadpisy skupin "Šuplíky N · M šuplíků / šuplíky" (spravny tvar slova), zadne slovo multibox v panelu, karta za kazdou skupinu a cipy jen pro sety z g.sety v poradi payload.sety',
      sp.titul === 'Příčky do šuplíků' && sp.aria === 'Příčky do šuplíků' && !/multibox/i.test(sp.text) && sp.karty.length === PD.skupiny.length && PD.skupiny.every(g => g.k === 'suplik')
      && sp.karty.every((k, i) => k.id === PD.skupiny[i].id && k.nadpis === nadpisSk(PD.skupiny[i]) && k.chipy.map(c => c.set).join() === setyG(PD, k.id).join()) && /šuplíků$/.test(sp.karty[0].nadpis) && /šuplíky$/.test(sp.karty[1].nadpis), { titul: sp.titul, aria: sp.aria, nadpisy: sp.karty.map(k => k.nadpis) });
    over('U2 cipy supliku nesou nazev setu, poznamku, CENU ZA CELOU SKUPINU a "N pricek" podle payloadu (cena dilu podle hloubky a vysky podnosu), vychozi stav "Bez pricek" aktivni', sp.karty.every((k, i) => k.chipy.every(c => {
      const g = PD.skupiny[i].sety[c.set], set = PD.sety.find(x => x.id === c.set);
      return c.pop === set.popis && (set.pozn ? c.pozn === set.pozn : c.pozn === null) && c.cena === (g.cena > 0 ? '+' + fmtK(g.cena) + ' Kč' : '0 Kč') && c.pocet === (g.priccek > 0 ? `${g.priccek} ${plPricek(g.priccek)}` : null) && c.pressed === (c.set === 'bez' ? 'true' : 'false') && !c.disabled;
    })), sp.karty[0].chipy.map(c => [c.set, c.cena, c.pocet]));
    const chybyMin = [];
    sp.karty.forEach((k, i) => k.chipy.forEach(c => miniaturaChyby(PD, PD.skupiny[i], c).forEach(x => chybyMin.push(`${k.id}/${c.set}: ${x}`))));
    over('U3 miniatura supliku = rada malych podnosu: obdelnik na podnos, pomer stran L:W typu (v mezich 0,3-0,8), BEZ tmaveho lemu, cary pricek podle desky[].s[0] / L (u supliku x podel sirky podnosu), pocet car = pocet pricek setu', chybyMin.length === 0
      && sp.karty[0].chipy.every(c => c.lemy.length === 0) && sp.karty[0].chipy[0].rects[0].h > sp.karty[0].chipy[0].rects[5].h, chybyMin.slice(0, 6));
    over('U3b podnosy ruzne sirky maji ruzny pomer stran: 443 mm siroky (pomer nad mez 0,8 -> 0,8) a 695 mm siroky (0,55) - prvni tri obdelniky stejne vysoke, dalsi tri nizsi', (() => { const rc = sp.karty[0].chipy[0].rects; return rc[0].h === rc[1].h && rc[1].h === rc[2].h && rc[3].h === rc[4].h && rc[4].h === rc[5].h && rc[0].h > rc[3].h + 1; })(), sp.karty[0].chipy[0].rects.map(x => x.h));
    await playVymaz(page);
    await klik(page, 's1', 'mix2');
    const n1u = PD.skupiny[0].boxy.length;
    await page.waitForTimeout((n1u - 1) * 150 + 600);
    vyb = vyberSetu(PD, { s1: 'mix2' });
    e = vypocet(PD, vyb);
    sc = await ceny(page);
    const plU = await playLog(page);
    over('U4 klik na set supliku (s1, Mix 2): plugin setGroup(s1, mix2) a drzi pocty po podnosech (po_boxech), cena = zbozi + pricky, rozpis "příčky bez DPH" (bez slova multibox), radky tabulky po dilech podle hloubky a vysky podnosu, QR ?pr= po boxech',
      (await volani(page)).includes('setGroup:s1:mix2') && JSON.stringify(await pluginVyber(page)) === JSON.stringify(vyb) && radkyOk(sc.radky, e, sc.zakladRadku) && e.radky.length >= 1 && sc.banner === fmtK(e.total) + ' Kč'
      && sc.detail.includes('příčky bez DPH ' + fmtK(e.pricky) + ' Kč') && !/multibox/i.test(sc.detail) && (await qrPr(page)) === retezec(vyb) && /^ps/.test(PD.typy[PD.boxy.find(b => b.id === PD.skupiny[0].boxy[0]).k].dil), { vyb, banner: sc.banner, radky: sc.radky });
    over('U4b po vyberu setu supliku se VSECHNY podnosy skupiny vysunou (viewer.play(id, 1) pro id z api.motionIds(s1), v poradi, jen s1)', JSON.stringify(plU.map(x => [x.fn, x.id, x.dir])) === JSON.stringify(idsPohybu(PD, 's1').map(id => ['play', id, 1])), plU.map(x => x.id));
    await r.browser.close();

    // vybrat set u obou skupin supliku + prijeti: pole pricky po boxech
    r = await H.otevri({ data: H.nabidka({ pricky: PD }) }); page = r.page;
    await H.na3D(page);
    await klik(page, 's1', 'pln'); await klik(page, 's2', 'mix3');
    vyb = vyberSetu(PD, { s1: 'pln', s2: 'mix3' });
    e = vypocet(PD, vyb);
    await H.naCeny(page);
    await vyplnAccept(page); await page.click('#btnAccept'); await page.waitForTimeout(400);
    over('U5 prijeti nabidky se supliky: telo accept nese pole pricky = kanonicky retezec po podnosech (cisla boxu serazena), banner i radky tabulky sedi se soucty dilu (ps...)', r.accepts.length === 1 && r.accepts[0].pricky === retezec(vyb) && (await stavCeny(page)).banner === fmtK(e.total) + ' Kč' && radkyOk((await stavCeny(page)).radky, e, (await stavCeny(page)).zakladRadku), { acc: r.accepts[0] && r.accepts[0].pricky, ocek: retezec(vyb) });
    await r.browser.close();

    // multiboxy + supliky v jedne nabidce
    r = await H.otevri({ data: H.nabidka({ pricky: PM }) }); page = r.page;
    await H.na3D(page);
    sp = await stavPanelu(page);
    const chM = [];
    sp.karty.forEach((k, i) => k.chipy.forEach(c => miniaturaChyby(PM, PM.skupiny[i], c).forEach(x => chM.push(`${k.id}/${c.set}: ${x}`))));
    over('U6 multiboxy + suplíky v jedne nabidce: nadpis sekce "Příčky do multiboxů a šuplíků" (zahlavi i aria-label), nadpisy skupin "Police s multiboxy 1 · 4 boxy" a "Šuplíky 1 · 3 šuplíky", miniatury: u multiboxu tmavy lem na kazdem boxu, u supliku zadny',
      sp.titul === 'Příčky do multiboxů a šuplíků' && sp.aria === 'Příčky do multiboxů a šuplíků' && sp.karty.length === 2 && sp.karty[0].nadpis === nadpisSk(PM.skupiny[0]) && sp.karty[1].nadpis === nadpisSk(PM.skupiny[1])
      && /boxy$/.test(sp.karty[0].nadpis) && /šuplíky$/.test(sp.karty[1].nadpis) && sp.karty[0].chipy.every(c => c.lemy.length === PM.skupiny[0].boxy.length) && sp.karty[1].chipy.every(c => c.lemy.length === 0) && chM.length === 0, { titul: sp.titul, nadpisy: sp.karty.map(k => k.nadpis), chM: chM.slice(0, 4) });
    await klik(page, 's1', 'mix1'); await klik(page, 's2', 'mix4');
    vyb = vyberSetu(PM, { s1: 'mix1', s2: 'mix4' });
    e = vypocet(PM, vyb);
    sc = await ceny(page);
    over('U7 multiboxy + suplíky: sety vybrane po skupinach, radky tabulky agregovane po dilech (p186 / p91 i ps384v137), banner a ?pr= sedi, rozpis "příčky bez DPH"', radkyOk(sc.radky, e, sc.zakladRadku) && e.radky.some(x => /^p/.test(x.klic) && !/^ps/.test(x.klic)) && e.radky.some(x => /^ps/.test(x.klic)) && sc.banner === fmtK(e.total) + ' Kč' && (await qrPr(page)) === retezec(vyb)
      && sc.detail.includes('příčky bez DPH ' + fmtK(e.pricky) + ' Kč'), { radky: sc.radky, ocek: e.radky.map(x => [x.klic, x.qty]) });
    await r.browser.close();

    // jediny podnos: sety se deduplikuji
    r = await H.otevri({ data: H.nabidka({ pricky: PJ }) }); page = r.page;
    await H.na3D(page);
    sp = await stavPanelu(page);
    const tJ = PJ.typy[PJ.boxy[0].k], gJ = PJ.skupiny[0];
    over('U8 jediny podnos ve skupine: sety se deduplikuji (jen "Bez pricek" a "Plny set", Mix 1-4 by dal totez), nadpis "Šuplíky 1 · 1 šuplík", sekce "Příčky do šuplíků"; miniatura = jeden obdelnik pres celou sirku (vyska nejvyse 34), Plny set = max pricek (cary)',
      sp.titul === 'Příčky do šuplíků' && sp.karty.length === 1 && sp.karty[0].chipy.map(c => c.set).join() === 'bez,pln' && Object.keys(gJ.sety).join() === 'bez,pln' && sp.karty[0].nadpis === `${gJ.popis} · 1 šuplík`
      && sp.karty[0].chipy.every(c => c.rects.length === 1 && Math.abs(c.rects[0].w - 100) < 0.01 && Math.abs(c.rects[0].h - 34) < 0.01 && miniaturaChyby(PJ, gJ, c).length === 0) && sp.karty[0].chipy[1].car === tJ.max, { titul: sp.titul, sety: sp.karty[0].chipy.map(c => c.set), rects: sp.karty[0].chipy[0].rects });
    await klik(page, 's1', 'pln');
    vyb = vyberSetu(PJ, { s1: 'pln' });
    e = vypocet(PJ, vyb);
    sc = await ceny(page);
    over('U9 jediny podnos, Plny set: max pricek v podnosu, cena = max x cena dilu, QR ?pr= "b01:max"', JSON.stringify(await pluginVyber(page)) === JSON.stringify({ [PJ.boxy[0].id]: tJ.max }) && sc.banner === fmtK(e.total) + ' Kč' && (await qrPr(page)) === `${PJ.boxy[0].id}:${tJ.max}` && e.pricky === Math.round(tJ.max * PJ.dily[0].cena * 100) / 100, { vyb, banner: sc.banner });
    await r.browser.close();

    // skupina se vsemi sety a skupina jen s bez / plny: kazda karta ma vlastni cipy (zadny radek "Vsechny")
    r = await H.otevri({ data: H.nabidka({ pricky: PX }) }); page = r.page;
    await H.na3D(page);
    sp = await stavPanelu(page);
    over('U10 skupina se vsemi sety a skupina jen s "Bez pricek" a "Plny set": kazda karta ma vlastni cipy podle g.sety, zadny spolecny radek "Vsechny"', sp.karty.length === 2 && sp.karty[0].chipy.length === 6 && sp.karty[1].chipy.map(c => c.set).join() === 'bez,pln' && !sp.vseRadek, sp.karty.map(k => k.chipy.map(c => c.set).join('/')));
    await r.browser.close();

    // skryto: jen admin, stitek u nazvu skupiny
    r = await H.otevri({ data: H.nabidka({ pricky: PH }) }); page = r.page;
    await H.na3D(page);
    sp = await stavPanelu(page);
    over('U11 skupina se skryto:true (jen admin): stitek "zákazník zatím nevidí" je u nazvu JEN teto skupiny (suplíky), skupina bez stitku (police), banner "Nahled pro zamestnance" zustava; nazev skupiny zustava (zacina "Šuplíky 1 · 3 šuplíky")',
      PH.skupiny[0].skryto === false && PH.skupiny[1].skryto === true && sp.karty[0].skryto === 0 && sp.karty[1].skryto === 1 && sp.karty[1].skrytoText === 'zákazník zatím nevidí' && !!sp.karty[1].skrytoTitle && sp.karty[1].nadpis.startsWith(nadpisSk(PH.skupiny[1]))
      && /Náhled pro zaměstnance/.test(sp.text) && (await page.evaluate(() => !!document.querySelector('#prickyPanel .pr-admin'))) && sp.titul === 'Příčky do multiboxů a šuplíků', { karty: sp.karty.map(k => [k.id, k.skryto, k.skrytoText]), text: sp.text.slice(0, 120) });
    await klik(page, 's2', 'mix1');
    vyb = vyberSetu(PH, { s2: 'mix1' });
    over('U12 skryta skupina funguje i pro admina (nahled): klik na set = setGroup, vyber, cena', (await volani(page)).includes('setGroup:s2:mix1') && JSON.stringify(await pluginVyber(page)) === JSON.stringify(vyb) && (await ceny(page)).banner === fmtK(vypocet(PH, vyb).total) + ' Kč', { vyb });
    await r.browser.close();
    r = await H.otevri({ data: H.nabidka({ pricky: PM }) }); page = r.page;
    await H.na3D(page);
    sp = await stavPanelu(page);
    over('U13 zakaznik (payload bez skryto:true, bez nahled_admin): zadny stitek "zakaznik zatim nevidi" a zadny banner pro zamestnance', sp.karty.every(k => k.skryto === 0) && !/zatím nevidí/.test(sp.text) && !(await page.evaluate(() => !!document.querySelector('#prickyPanel .pr-admin'))), sp.text.slice(0, 100));
    await r.browser.close();

    // nadpis sekce podle ZOBRAZENYCH skupin: skupina, kterou plugin ve 3D nenasel, se nepocita
    for (const [nazev, neready, ocek] of [['U14a supliky ve 3D nenalezeny', 's2', 'Příčky do multiboxů'], ['U14b multiboxy ve 3D nenalezeny', 's1', 'Příčky do šuplíků']]) {
      r = await H.otevri({ data: H.nabidka({ pricky: PM }), init: [`window.__prNeready = ["${neready}"]`] }); page = r.page;
      await H.na3D(page);
      sp = await stavPanelu(page);
      over(nazev + ': nadpis sekce i aria-label se ridi jen zobrazenymi skupinami -> "' + ocek + '"', sp.titul === ocek && sp.aria === ocek && sp.karty.length === 1 && sp.karty[0].id !== neready, { titul: sp.titul, aria: sp.aria, karty: sp.karty.map(k => k.id) });
      await r.browser.close();
    }

    // zpetna kompatibilita: starsi payload bez druh / os / L / W / H / lem / skryto (multiboxy) se vykresli stejne (lem z geom.studna_od, rozmery z klice typu)
    const PNOVY = H.payload('4921');
    const PSTARY = upravP(Pz => { Object.values(Pz.typy).forEach(t => { delete t.druh; delete t.os; delete t.L; delete t.W; delete t.H; delete t.lem; }); Pz.skupiny.forEach(g => { delete g.skryto; }); });
    let mNovy, mStary, spStary;
    r = await H.otevri({ data: H.nabidka({ pricky: PNOVY }) }); await H.na3D(r.page); mNovy = await stavPanelu(r.page); await r.browser.close();
    r = await H.otevri({ data: H.nabidka({ pricky: PSTARY }) }); await H.na3D(r.page); mStary = await stavPanelu(r.page); await r.browser.close();
    const cn = mNovy.karty[0].chipy[1], cs = mStary.karty[0].chipy[1];
    over('U15 starsi payload (bez druh / L / W / lem / skryto): nadpis sekce "Příčky do multiboxů", lem u kazdeho boxu a rozmery i cary miniatury shodne s novym payloadem (rozdil jen zaokrouhleni 395 / 395,5)', mStary.titul === 'Příčky do multiboxů' && cs.lemy.length === cs.rects.length && cn.rects.length === cs.rects.length
      && cn.rects.every((rc, i) => Math.abs(rc.h - cs.rects[i].h) < 0.1) && cn.cary.length === cs.cary.length && cn.cary.every((c, i) => Math.abs(c.x - cs.cary[i].x) < 0.15), { titul: mStary.titul, lem: cs.lemy.length, rects: cs.rects.length });
    const PBEZL = upravP(Pz => { Object.values(Pz.typy).forEach(t => { t.lem = 0; }); }), PVELKYL = upravP(Pz => { Object.values(Pz.typy).forEach(t => { t.lem = 9999; }); });
    r = await H.otevri({ data: H.nabidka({ pricky: PBEZL }) }); await H.na3D(r.page); const mBezL = await stavPanelu(r.page); await r.browser.close();
    r = await H.otevri({ data: H.nabidka({ pricky: PVELKYL }) }); await H.na3D(r.page); const mVelkyL = await stavPanelu(r.page); await r.browser.close();
    over('U16 typy[k].lem = 0 = bez tmaveho lemu (i u multiboxu); nesmyslne velky lem se omezi na 40 % delky boxu', mBezL.karty[0].chipy.every(c => c.lemy.length === 0) && mVelkyL.karty[0].chipy.every(c => c.lemy.length === c.rects.length && c.lemy.every((l, i) => Math.abs(l.w / c.rects[i].w - 0.4) < 0.003)), { bez: mBezL.karty[0].chipy[0].lemy.length, velky: mVelkyL.karty[0].chipy[0].lemy.slice(0, 2) });

    // XSS v nazvu skupiny supliku a v typu
    const XSSU = '<img src=x onerror="window.__xss=7">';
    const PXSS = JSON.parse(JSON.stringify(PD)); PXSS.skupiny[0].popis = XSSU + 'Suplíky'; PXSS.dily[0].nazev = XSSU + 'Pricka';
    r = await H.otevri({ data: H.nabidka({ pricky: PXSS }) }); page = r.page;
    await H.na3D(page);
    await klik(page, 's1', 'pln'); sc = await ceny(page); await page.waitForTimeout(200);
    const xssU = await page.evaluate(() => ({ x: window.__xss, imgs: document.querySelectorAll('#prickyPanel img, #prickyTbody img').length, text: document.getElementById('prickyPanel').textContent.includes('<img src=x') }));
    over('U17 XSS: znacky v nazvu skupiny supliku a v nazvu dilu se nespusti (jen text)', xssU.x === undefined && xssU.imgs === 0 && xssU.text, xssU);
    await r.browser.close();
  }

  // ======================================================== Z) zvyrazneni skupiny ve 3D (api.highlightGroup): mys, dotyk, klavesnice a ~3 s po kliknuti na set (dotyk nema hover)
  {
    r = await H.otevri({}); page = r.page;
    await H.na3D(page);
    await playVymaz(page);
    await page.hover('#prickyPanel .pr-card[data-skupina="s2"] h4');
    await page.waitForTimeout(80);
    const z1 = await hlVolani(page);
    await page.click('#prickyPanel .pr-chip[data-cil="s2"][data-set="mix1"]');              // klik na set (mys zustava nad kartou)
    const tKlik = Date.now();
    await page.mouse.move(5, 5);                                                             // mys pryc z karty
    await page.waitForTimeout(300);
    const z2 = await hlVolani(page);
    await page.waitForTimeout(Math.max(0, 1500 - (Date.now() - tKlik)));
    const z3 = await hlVolani(page);
    await page.waitForTimeout(Math.max(0, 3500 - (Date.now() - tKlik)));
    const z4 = await hlVolani(page);
    over('Z1 najeti na kartu skupiny zvyrazni skupinu ve 3D; po kliknuti na set zustane zvyraznena i po odjeti mysi (1,5 s po kliknuti) a po ~3 s se zrusi (highlightGroup(null)); cip zaostreny kliknutim mysi zvyrazneni neudrzuje', posl(z1) === 's2' && posl(z2) === 's2' && posl(z3) === 's2' && posl(z4) === null
      && await page.evaluate(() => !!(document.activeElement && document.activeElement.classList.contains('pr-chip'))), { z1, z2, z3, z4 });
    await page.click('#prickyPanel .pr-chip[data-cil="s1"][data-set="mix2"]');
    await page.hover('#prickyPanel .pr-card[data-skupina="s3"] h4');                       // najeti na JINOU kartu prebije drzeni po kliknuti
    await page.waitForTimeout(100);
    const z5 = await hlVolani(page);
    await page.mouse.move(5, 5);
    await page.waitForTimeout(150);
    const z6 = await hlVolani(page);
    over('Z2 najeti na JINOU kartu prebije zvyrazneni po kliknuti (s3 misto s1) a po odjeti zvyrazneni zmizi hned (drzeni po kliknuti uz neplati)', posl(z5) === 's3' && posl(z6) === null, { z5: z5.slice(-3), z6: z6.slice(-3) });
    await page.waitForTimeout(3300);                                                         // dobehne drzeni z predchozich kroku
    await page.focus('#prickyPanel .pr-card[data-skupina="s1"] .pr-chips > .pr-chip:last-child');
    await page.keyboard.press('Tab'); await page.waitForTimeout(100);
    const z7 = await hlVolani(page);
    await page.keyboard.press('Shift+Tab'); await page.waitForTimeout(100);
    const z8 = await hlVolani(page);
    await page.evaluate(() => document.activeElement.blur()); await page.waitForTimeout(100);
    const z9 = await hlVolani(page);
    over('Z3 zaostreni klavesnici (Tab / Shift+Tab) na karte skupiny zvyrazni skupinu ve 3D, odchod ze skupiny / panelu zvyrazneni zrusi', posl(z7) === 's2' && posl(z8) === 's1' && posl(z9) === null, { z7: z7.slice(-3), z8: z8.slice(-3), z9: z9.slice(-3) });
    await r.browser.close();

    r = await H.otevri({ width: 390, height: 800, mobil: true }); page = r.page;                // telefon: dotyk, zadny hover
    await H.naSlide(page, 'view_3d'); await page.waitForSelector('#prickyPanel:not([hidden]) summary', { timeout: 20000 });
    await page.tap('#prickyPanel details.pr-wrap > summary'); await page.waitForTimeout(250);
    await playVymaz(page);
    await page.tap('#prickyPanel .pr-card[data-skupina="s2"] h4');
    const tTap = Date.now();
    await page.waitForTimeout(250);
    const z10 = await hlVolani(page);
    await page.waitForTimeout(Math.max(0, 1500 - (Date.now() - tTap)));
    const z11 = await hlVolani(page);
    await page.waitForTimeout(Math.max(0, 3600 - (Date.now() - tTap)));
    const z12 = await hlVolani(page);
    over('Z4 dotyk na kartu skupiny (telefon, bez hoveru) zvyrazni skupinu ve 3D, po pusteni prstu ji drzi ~3 s a potom zvyrazneni zrusi', posl(z10) === 's2' && posl(z11) === 's2' && posl(z12) === null, { z10, z11, z12 });
    await r.browser.close();

    r = await H.otevri({ init: ['window.__prHlChyba = true'] }); page = r.page;
    await H.na3D(page); await klik(page, 's1', 'mix1'); await page.hover('#prickyPanel .pr-card[data-skupina="s2"] h4'); await page.waitForTimeout(100);
    over('Z5 highlightGroup vyhodi vyjimku: stranka bezi dal (vyber, cena, zadna chyba JS)', r.chyby.length === 0 && JSON.stringify(await pluginVyber(page)) === JSON.stringify(vyberSetu(P0, { s1: 'mix1' })) && (await ceny(page)).banner === fmtK(vypocet(P0, vyberSetu(P0, { s1: 'mix1' })).total) + ' Kč', r.chyby);
    await r.browser.close();
  }

  // ======================================================== O) po vyberu setu se VSECHNY boxy skupiny ve 3D vysunou (viewer.play(id, 1) pro id z api.motionIds), jen na klik zakaznika
  {
    r = await H.otevri({}); page = r.page;
    await H.na3D(page);
    await playVymaz(page);
    const n1 = idsSk('s1').length;
    await page.click('#prickyPanel .pr-chip[data-cil="s1"][data-set="mix1"]');
    const pl0 = await playLog(page);
    await page.waitForTimeout((n1 - 1) * 150 + 700);
    const pl1 = await playLog(page);
    const md1 = (await volani(page)).filter(v => v.startsWith('motionIds'));
    over('O1 klik na set (Mix 1) skupiny s1: viewer.play(id, 1) pro VSECHNY pohyby boxu skupiny (id z api.motionIds(s1)), v poradi skupiny, po jednom; prvni box hned, dalsi s odstupem ~150 ms (kazdy nejdriv v case i*150 ms); plugin se ptal jen na s1; nic dalsiho (zadny playAll, zadne zavirani)',
      JSON.stringify(pl1.map(x => [x.fn, x.id, x.dir])) === JSON.stringify(idsPohybu(P0, 's1').map(id => ['play', id, 1])) && md1.join() === 'motionIds:s1' && pl0.length >= 1 && pl0[0].id === idsPohybu(P0, 's1')[0]
      && pl1.every((x, i) => x.t - pl1[0].t >= i * 150 - 40) && n1 >= 3, { pl0: pl0.length, pl1: pl1.map(x => [x.id, Math.round(x.t - pl1[0].t)]), md1 });
    await playVymaz(page);
    await page.click('#prickyPanel .pr-chip[data-cil="s2"][data-set="mix2"]');
    await page.waitForTimeout((idsSk('s2').length - 1) * 150 + 700);
    const pl2 = await playLog(page);
    over('O2 dalsi skupina (s2, Mix 2): vysunou se jen boxy teto skupiny, boxy s1 se uz nevysouvaji', JSON.stringify(pl2.map(x => [x.fn, x.id, x.dir])) === JSON.stringify(idsPohybu(P0, 's2').map(id => ['play', id, 1])), pl2.map(x => x.id));
    await playVymaz(page);
    await page.click('#prickyPanel .pr-chip[data-cil="s2"][data-set="bez"]');
    await page.waitForTimeout(700);
    over('O3 "Bez pricek" boxy ani neotevira, ani NEzavira: zadne viewer.play / playAll (zavirani se nedela), plugin se na pohyby ani neptal; vyber se presto zmenil', (await playLog(page)).length === 0 && !(await volani(page)).some(v => v.startsWith('motionIds'))
      && JSON.stringify(await pluginVyber(page)) === JSON.stringify(vyberSetu(P0, { s1: 'mix1' })), { pl: await playLog(page), v: await pluginVyber(page) });
    await playVymaz(page);
    await page.click('#prickyPanel .pr-chip[data-cil="s1"][data-set="mix1"]');            // znovu stejny (uz zvoleny) set: vysune se znovu
    await page.waitForTimeout((n1 - 1) * 150 + 700);
    over('O4 opakovany klik na uz zvoleny set vysune boxy znovu (viewer.play je idempotentni; zakaznik mohl boxy mezitim zavrit)', JSON.stringify((await playLog(page)).map(x => x.id)) === JSON.stringify(idsPohybu(P0, 's1')), (await playLog(page)).map(x => x.id));
    await playVymaz(page);
    await page.evaluate(() => { const q = s => document.querySelector('#prickyPanel .pr-chip[data-cil="s1"][data-set="' + s + '"]'); q('mix2').click(); q('mix3').click(); });          // dva kliky v jednom tahu
    await page.waitForTimeout((n1 - 1) * 150 + 700);
    const pl6 = await playLog(page), poc6 = {};
    pl6.forEach(x => { poc6[x.id] = (poc6[x.id] || 0) + 1; });
    const ids1 = idsPohybu(P0, 's1');
    over('O5 dva rychle kliky po sobe na tu samou skupinu (Mix 2, hned Mix 3): casovace prvniho kliknuti se zrusi - prvni box se vysune 2x (kazdy klik ho spusti hned), ostatni vzdy 1x, vsechny boxy skupiny jsou vysunute', poc6[ids1[0]] === 2 && ids1.slice(1).every(id => poc6[id] === 1) && Object.keys(poc6).length === ids1.length, poc6);
    await r.browser.close();

    // obnova vyberu z localStorage pri nacteni stranky nic nevysouva
    r = await H.otevri({ ls: { v: 2, boxy: vyberSetu(P0, { s1: 'mix3', s2: 'pln' }) } }); page = r.page;
    await H.na3D(page); await page.waitForTimeout(1300);
    const volO = await volani(page);
    over('O6 obnova vyberu z localStorage pri nacteni stranky NIC nevysouva (zadne viewer.play ani dotaz na motionIds; zadne zvyrazneni skupiny), vyber se ve 3D obnovi (setMany)', (await playLog(page)).length === 0 && !volO.some(v => v.startsWith('motionIds')) && volO.some(v => v.startsWith('setMany:')) && (await hlVolani(page)).every(g => g === null), { pl: await playLog(page), volO: volO.slice(0, 8) });
    await r.browser.close();

    // odolnost: stranka nesmi spadnout, kdyz plugin / viewer nema funkci nebo vyhodi chybu; vyber a cena funguji dal
    for (const [nazev, init, ocekPlay] of [
      ['O7a plugin BEZ api.motionIds (starsi verze pluginu)', 'window.__prBezMotionIds = true', 0],
      ['O7b api.motionIds vyhodi vyjimku', "window.__prMotionIds = 'throw'", 0],
      ['O7c api.motionIds vrati neco jineho nez pole', 'window.__prMotionIds = 42', 0],
      ['O7d api.motionIds vrati prazdne pole', 'window.__prMotionIds = []', 0],
      ['O7e viewer.play vyhodi vyjimku (volani se zaznamena, stranka bezi dal)', 'window.__v3dPlayChyba = true', n1],
      ['O7f viewer bez play (starsi viewer)', 'window.__v3dBezPlay = true', 0],
    ]) {
      r = await H.otevri({ init: [init] }); page = r.page;
      await H.na3D(page);
      await playVymaz(page);
      await klik(page, 's1', 'mix1');
      await page.waitForTimeout((n1 - 1) * 150 + 500);
      const vz = vyberSetu(P0, { s1: 'mix1' });
      over(nazev + ': klik na set funguje (plugin drzi vyber, cena, ?pr=), zadna chyba JS', (await playLog(page)).length === ocekPlay && JSON.stringify(await pluginVyber(page)) === JSON.stringify(vz) && (await ceny(page)).banner === fmtK(vypocet(P0, vz).total) + ' Kč' && (await qrPr(page)) === retezec(vz) && r.chyby.length === 0, { pl: (await playLog(page)).length, chyby: r.chyby });
      await r.browser.close();
    }
    r = await H.otevri({ init: ["window.__prMotionIds = ['m1', 5, null, '', 'm1', 'm2', {}]"] }); page = r.page;
    await H.na3D(page); await playVymaz(page);
    await klik(page, 's1', 'mix1'); await page.waitForTimeout(700);
    over('O8 neplatna id pohybu (cislo, null, prazdne, objekt) se preskoci a duplicity se vysunou jen jednou: viewer.play jen pro "m1" a "m2"', JSON.stringify((await playLog(page)).map(x => [x.id, x.dir])) === JSON.stringify([['m1', 1], ['m2', 1]]) && r.chyby.length === 0, { pl: await playLog(page), chyby: r.chyby });
    await r.browser.close();
  }

  // ======================================================== K) chyby ve strance
  r = await H.otevri({});
  await H.na3D(r.page); for (const g of P0.skupiny) await klik(r.page, g.id, 'pln'); await klik(r.page, 's2', 'bez'); await klik(r.page, 's3', 'mix3'); await ceny(r.page);
  over('K1 behem celeho scenare (vyber, ceny, tabulka, QR) zadna chyba JS ve strance', r.chyby.length === 0, r.chyby);
  await r.browser.close();

  const ok = vysl.filter(Boolean).length;
  console.log(`\n${ok}/${vysl.length} kontrol prošlo`);
  process.exit(ok === vysl.length ? 0 : 1);
})().catch(e => { console.error('TEST SPADL:', e.stack || e.message); process.exit(2); });
