// IoU Johnova modelu v6 STEJNÝM postupem a STEJNOU maskou (vyloučené oblasti) jako náš model: (a) kamera z kontroly bez dofitu, (b) kamera dofitovaná k jeho obrysu.
// Johnův GLB se jen čte (reference). Výstup: kufriky_cloud/srovnani_opravy/<SKU>/john_iou.json. node john_iou.mjs <SKU> [pohled ...]
import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
const HERE = path.dirname(fileURLToPath(import.meta.url));
const [sku, ...ph] = process.argv.slice(2);
const cfgF = path.join(HERE, `cfg_${sku}.json`), cfg = JSON.parse(fs.readFileSync(cfgF, 'utf8'));
const glb = path.resolve(HERE, '../../kufriky_john/nahled-modely-v6/modely', sku + '.glb');
const dir = path.join(HERE, '../../kufriky_cloud/srovnani_opravy', sku), res = {};
// Johnův GLB nemá uzly s osou pantu (víko je rozptýlené ve 'viko-*' dílech), proto se IoU přepočítává jen pro fotografie se zavřeným víkem; u ostatních platí IoU z kontroly (dofitovaný úhel víka)
for (const p of (ph.length ? ph : Object.keys(cfg).filter(k => !cfg[k].glb && !('vicko' in (cfg[k].pose || {}))))) {
  const base = ['srov.mjs', '--cfg', cfgF, '--pohled', p, '--glb', glb, '--bez-rendru', '--tag', 'john_' + p];
  const run = a => { for (let t = 0; ; t++) { try { return JSON.parse(execFileSync('node', [...base, ...a], { cwd: HERE, encoding: 'utf8', maxBuffer: 1e8, stdio: ['ignore', 'pipe', 'ignore'] }).trim().split('\n').pop()); } catch (e) { if (t >= 3) throw e; console.error('opakuji (pád prohlížeče)', p, t + 1); } } };
  const poseJohn = (cfg[p].pose && 'vicko' in cfg[p].pose) ? ['--pose', 'vicko=' + (-cfg[p].pose.vicko)] : [];   // Johnův model: osa pantu opačné znaménko (kontrola: záporný úhel)
  const k = run(poseJohn), f = run([...poseJohn, '--fit', '--free', 'azim,elev,dist,fov,cx,cy' + (poseJohn.length ? ',vicko' : ''), '--iter', '120']);
  res[p] = { iou_kamera_kontroly: k.iou, iou_dofit: f.iou, kamera_dofit: f.kamera, pose_dofit: f.pose, iou_podle_kontroly: cfg[p].john_iou };
  console.log(sku, p, JSON.stringify(res[p].iou_kamera_kontroly), JSON.stringify(f.iou), 'kontrola uvádí', cfg[p].john_iou);
}
fs.writeFileSync(path.join(dir, 'john_iou.json'), JSON.stringify(res, null, 1));
