// Kolo porovnání: pro každý pohled vyrenderuje model (kamera kontroly i dofitovaná), spočítá IoU, uloží PNG+JSON do kufriky_cloud/srovnani_opravy/<SKU>/ a dvojice do scratchpadu.
// node srov.mjs <kolo> [SKU] [popis]
import fs from 'node:fs'; import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { iouRender, renderPng, SCR } from './rend.mjs';
const HERE = path.dirname(fileURLToPath(import.meta.url)), ROOT = path.join(HERE, '../..'), KO = path.join(ROOT, 'kufriky_cloud/kontrola_john_v6'), OUT = path.join(ROOT, 'kufriky_cloud/srovnani_opravy');
const FOT = '/tmp/claude-0/-home-user-konfigurator/4afe04ea-52af-557e-a8a4-75a8d542e4f9/scratchpad/kufry3';
const [kolo, only, popis] = [process.argv[2] || '1', process.argv[3], process.argv[4] || ''];
const V = JSON.parse(fs.readFileSync(path.join(HERE, 'pohledy.json')));
for (const v of V) {
  if (only && only !== 'all' && v.sku !== only) continue;
  const glb = path.join(ROOT, 'kufry_milwaukee_opravy/modely', v.sku + '.glb'), foto = path.join(FOT, v.sku, v.id + '.jpg');
  const kont = JSON.parse(fs.readFileSync(path.join(KO, v.sku, v.id + '_kamera.json')));
  const fitf = path.join(OUT, v.sku, v.id + '_kamera_dofit.json');
  const fit = fs.existsSync(fitf) ? JSON.parse(fs.readFileSync(fitf)) : null;
  const rot = v.pose || {}, pos = v.pos || {}, posK = v.posKontrola || pos;
  const r1 = await iouRender({ glb, foto, cam: kont, rot, pos: posK, ycut: v.ycut || 0 });
  let r2 = null, r3 = null; if (fit) { r2 = await iouRender({ glb, foto, cam: fit, rot, pos, ycut: v.ycut || 0 }); r3 = await iouRender({ glb, foto, cam: fit, rot, pos, ycut: 0, nofill: true }); }
  const cam = fit || kont, p = path.join(OUT, v.sku, `${v.id}_kolo${kolo}.png`);
  await renderPng({ glb, cam, rot, pos, W: 1000, out: p });
  const pair = path.join(SCR, `${v.sku}_${v.id}_kolo${kolo}_pair.png`);
  execFileSync('python3', [path.join(ROOT, 'kufriky_cloud/nastroje/porovnej.py'), foto, p, pair, '700'], { stdio: 'ignore' });
  const j = { sku: v.sku, foto: v.id, kolo: +kolo, popis, poza: { rot, pos }, iou_kamera_kontroly: r1, iou_kamera_dofitovana: r2, iou_dofit_maska_bez_vyplneni_der: r3, kamera_dofitovana: fit ? (fit.kamera || fit) : null, poznamka: v.poznamka || '' };
  fs.writeFileSync(path.join(OUT, v.sku, `${v.id}_kolo${kolo}.json`), JSON.stringify(j, null, 1));
  console.log(v.sku, v.id, 'kontrola', JSON.stringify(r1), 'dofit', r2 ? JSON.stringify(r2) : '-', 'nefill', r3 ? r3.iou : '-');
}
