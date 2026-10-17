// Dávka: pro každý pohled vyrenderuje NAŠI verzi (PNG do kufriky_cloud/srovnani_opravy/<SKU>/), spočítá IoU (bez vyplnění děr i s vyplněním jako v kontrole), IoU Johnova modelu
// při stejné (dané) kameře a zapíše <pohled>.json. Fotografie se jen čtou ze scratchpadu (do repa se nekopírují; zapisuje se jen URL z milwaukeetool.eu).
// node srovnani.mjs [SKU]
import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
const HERE = path.dirname(fileURLToPath(import.meta.url)), ROOT = path.join(HERE, '../..');
const S = '/tmp/claude-0/-home-user-konfigurator/4afe04ea-52af-557e-a8a4-75a8d542e4f9/scratchpad';
const URL = (sku, n) => `https://static.milwaukeetool.eu/remote.axd/milwaukee-media-images.s3.amazonaws.com/hi/${sku}--Hero_${n}.jpg?width=1200`;
const CFG = {
  '4932464078': { john: 'kufriky_john/nahled-modely-v6/modely/4932464078.glb', views: [
    { p: 'c01', kam: 'dofit_final', dana: 'z_bodu', johnKam: 'john_dofit', pose: '', popis: 'šikmo zepředu, madlo složené' },
    { p: 'c02', kam: 'dofit_final', dana: 'z_bodu', johnKam: 'john_dofit', pose: 'madlo_1=130', popis: 'šikmo zepředu, první stupeň madla vysunut' },
    { p: 'c05', kam: 'dofit_final', dana: 'z_bodu', johnKam: 'john_dofit', pose: 'madlo_1=130,madlo_2=479', popis: 'zezadu, madlo vysunuto naplno', rows: 790 },
    { p: 'c09', kam: 'dofit_final', pose: '', popis: 'sestava (dole pojízdný box), madlo vysunuto; měřeno jen od y>=790', ymin: 790 },
    { p: 'c08', kam: 'dofit_final', pose: '', popis: 'sestava (dole pojízdný box); měřeno jen od y>=880', ymin: 880 },
    { p: 'c07', kam: 'dofit_final', pose: 'madlo_1=130,madlo_2=479', popis: 'zezadu zprava, madlo vysunuto, na boxu další box; měřeno jen od y>=700', ymin: 700 },
  ] },
  '4932478161': { john: 'kufriky_john/nahled-modely-v6/modely/4932478161.glb', views: [
    { p: 'c06', kam: 'dofit_final', dana: 'z_bodu', johnKam: 'john_dofit', pose: '', popis: 'téměř boční pohled, madlo složené' },
    { p: 'c01', kam: 'dofit_final', dana: 'z_obrysu', johnKam: 'john_dofit', pose: 'madlo=285', popis: 'šikmo, madlo vysunuto', xmin: 235 },
    { p: 'c02', kam: 'dofit_final', pose: 'vicko=95,madlo=285', popis: 'víko otevřené (≈95°), madlo vysunuto, vložka vevnitř' },
    { p: 'c03', kam: 'dofit_final', pose: 'vicko=95,madlo=285', hide: 'vlozka', popis: 'totéž bez vložky' },
    { p: 'c04', kam: 'dofit_final', pose: 'vicko=95,madlo=285', hide: 'vlozka', popis: 'totéž s nářadím (porovnána jen vnější silueta bez vložky)' },
    { p: 'c05', kam: 'dofit_final', pose: '', popis: 'bedna nakloněná na kolech (póza nahrazena pohybem kamery)' },
  ] },
};
const want = process.argv.slice(2).filter(a => /^\d+$/.test(a));
for (const [sku, cfg] of Object.entries(CFG)) {
  if (want.length && !want.includes(sku)) continue;
  const K = path.join(ROOT, 'kufriky_cloud/srovnani_opravy', sku, `kamery_${sku}.json`), out = path.join(ROOT, 'kufriky_cloud/srovnani_opravy', sku);
  const kams = JSON.parse(fs.readFileSync(K, 'utf8'));
  const glb = path.join(ROOT, 'kufry_milwaukee_opravy/modely', sku + '.glb');
  const run = (g, foto, v, kv, extra) => JSON.parse(execFileSync('node', [path.join(HERE, 'iou.mjs'), '--glb', g, '--foto', foto, '--kam', K, '--pohled', v.p, '--kamvar', kv, ...(v.pose ? ['--pose', v.pose] : []), ...(v.hide ? ['--hide', v.hide] : []), ...(v.ymin ? ['--ymin', String(v.ymin)] : []), ...extra], { env: { ...process.env, KUF_SCRATCH: S + '/ms' }, encoding: 'utf8' }).trim().split('\n').pop());
  for (const v of cfg.views) {
    const foto = `${S}/kufry3/${sku}/${v.p}.jpg`, png = path.join(out, v.p + '_nas_model.png');
    const res = { sku, pohled: v.p, popis: v.popis, foto_url: URL(sku, +v.p.slice(1)), foto_repo_cesta: null, poznamka_foto: 'Fotografie se do repa nekopíruje; zde je jen URL (v6 kontrola: stejné soubory).', pose: {}, hide: v.hide || null, mereno_od_radku_y: v.ymin || null };
    const a = run(glb, foto, v, v.kam, ['--rend', png, '--pair', `${S}/ms/dv_${sku}_${v.p}.png`]);
    res.render = path.relative(ROOT, png); res.pose = a.pose; res.kamera_dofit = kams[v.p][v.kam]; res.iou_nova_dofit_kamera = a.iou;
    res.iou_nova_dofit_kamera_s_vyplnenim = run(glb, foto, v, v.kam, ['--vyplnit', '--bez-rendru']).iou;
    if (v.dana) { res.kamera_dana_kontrolou = kams[v.p][v.dana]; res.iou_nova_dana_kamera = run(glb, foto, { ...v }, v.dana, ['--bez-rendru']).iou; res.iou_nova_dana_kamera_s_vyplnenim = run(glb, foto, v, v.dana, ['--vyplnit', '--bez-rendru']).iou; }
    const jg = path.join(ROOT, cfg.john);
    if (v.dana) { const vj = { ...v, pose: '', hide: '' }; res.iou_john_dana_kamera = run(jg, foto, vj, v.dana, ['--bez-rendru']).iou; res.iou_john_dana_kamera_s_vyplnenim = run(jg, foto, vj, v.dana, ['--vyplnit', '--bez-rendru']).iou; }
    if (v.johnKam && kams[v.p][v.johnKam]) { const vj = { ...v, pose: '', hide: '' }; res.iou_john_dofit_kamera = kams[v.p][v.johnKam].iou; }
    if (v.rows) { const vr = { ...v, ymin: v.rows }; res.iou_nova_dana_kamera_radky_od = { y: v.rows, s_vyplnenim: run(glb, foto, vr, v.dana, ['--vyplnit', '--bez-rendru']).iou, dofit_s_vyplnenim: run(glb, foto, vr, v.kam, ['--vyplnit', '--bez-rendru']).iou, john_dana_s_vyplnenim: run(jg, foto, { ...vr, pose: '' }, v.dana, ['--vyplnit', '--bez-rendru']).iou }; }
    if (v.xmin) { const vx = { ...v, xmin: v.xmin }; const ex = ['--xmin', String(v.xmin), '--bez-rendru'];
      res.iou_od_sloupce_x = { x: v.xmin, nova_dofit: run(glb, foto, v, v.kam, ex).iou, john_dofit: run(jg, foto, { ...v, pose: '' }, v.johnKam, ex).iou, john_dofit_s_vyplnenim: run(jg, foto, { ...v, pose: '' }, v.johnKam, [...ex, '--vyplnit']).iou, nova_dofit_s_vyplnenim: run(glb, foto, v, v.kam, [...ex, '--vyplnit']).iou }; }
    if (v.rows && v.johnKam) res.iou_nova_dana_kamera_radky_od.john_dofit_s_vyplnenim = run(jg, foto, { ...v, pose: '', ymin: v.rows }, 'john_dofit_rows', ['--vyplnit', '--bez-rendru']).iou;
    res.poznamka = 'Kamera z obrysu (dofit) je ODHAD přizpůsobený fotografii; IoU z dofitované kamery je horní mez, ne důkaz správnosti tvaru. IoU "bez vyplnění" počítá okna/mezery jako pozadí (přísnější než sdílená maska kontroly, která díry vyplňuje; sloupce s_vyplnenim jsou srovnatelné s hodnotami v kontrolním reportu).';
    fs.writeFileSync(path.join(out, v.p + '.json'), JSON.stringify(res, null, 1));
    console.log(sku, v.p, 'nova_dofit', res.iou_nova_dofit_kamera, 'nova_dana', res.iou_nova_dana_kamera ?? '-', 'john_dana', res.iou_john_dana_kamera ?? '-');
  }
  fs.writeFileSync(path.join(out, 'kamery_' + sku + '.json'), JSON.stringify(kams, null, 1));
}
