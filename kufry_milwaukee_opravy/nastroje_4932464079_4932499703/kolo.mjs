// Jedno kolo srovnání: pro každou fotografii SKU spočítá IoU (a) při kameře z kontroly (bez dofitu, úhel víka z kontroly) a (b) při kameře dofitované k našemu modelu (+ úhel víka),
// výsledek připíše do kufriky_cloud/srovnani_opravy/<SKU>/kola.jsonl a uloží dofitovanou kameru do kamery_dofit_<SKU>.json.
// Použití: node kolo.mjs <SKU> <číslo kola> "popis změny" [pohled ...]
import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
const HERE = path.dirname(fileURLToPath(import.meta.url));
const [sku, kolo, popis, ...ph] = process.argv.slice(2);
const cfgF = path.join(HERE, `cfg_${sku}.json`), cfg = JSON.parse(fs.readFileSync(cfgF, 'utf8'));
const dir = path.join(HERE, '../../kufriky_cloud/srovnani_opravy', sku); fs.mkdirSync(dir, { recursive: true });
const dofF = path.join(dir, `kamery_dofit_${sku}.json`), dof = fs.existsSync(dofF) ? JSON.parse(fs.readFileSync(dofF, 'utf8')) : {};
const poh = ph.length ? ph : Object.keys(cfg);
const glbDef = path.join(HERE, '../modely', sku + '.glb');
const out = { sku, kolo: +kolo, popis, cas: new Date().toISOString(), fotky: {} };
for (const p of poh) {
  const glb = cfg[p].glb ? path.resolve(HERE, cfg[p].glb) : glbDef, pose0 = cfg[p].pose || {};
  const base = ['srov.mjs', '--cfg', cfgF, '--pohled', p, '--glb', glb, '--bez-rendru', '--tag', p];
  const run = a => { for (let t = 0; ; t++) { try { return JSON.parse(execFileSync('node', [...base, ...a], { cwd: HERE, encoding: 'utf8', maxBuffer: 1e8, stdio: ['ignore', 'pipe', 'ignore'] }).trim().split('\n').pop()); } catch (e) { if (t >= 3) throw e; console.error('opakuji (pád prohlížeče)', p, t + 1); } } };
  const hasLid = 'vicko' in pose0;
  const k = hasLid ? run(['--fit', '--free', 'vicko', '--iter', '40']) : run([]);     // kamera z kontroly beze změny; u otevřeného víka se jako v kontrole dofituje jen úhel víka
  const cerv = (a, tag) => { if (p !== 'c01') return null; try { const r = JSON.parse(execFileSync('node', ['srov.mjs', '--cfg', cfgF, '--pohled', p, '--glb', glb, '--len', '800', '--tag', tag, ...a], { cwd: HERE, encoding: 'utf8', maxBuffer: 1e8, stdio: ['ignore', 'pipe', 'ignore'] }).trim().split('\n').pop()); return JSON.parse(execFileSync('python3', [path.join(HERE, 'cervena_iou.py'), cfg[p].foto, r.render], { encoding: 'utf8' })); } catch (e) { return null; } };
  const kc = cerv([], 'cerv_k');
  const free = 'azim,elev,dist,fov,cx,cy' + ('vicko' in pose0 ? ',vicko' : '');
  const prev = dof[p], a = ['--fit', '--free', free, '--iter', prev ? '60' : '150'];
  if (prev) { const c = prev.kamera; a.push('--st', [c.azim, c.elev, c.dist, c.fov, c.cx, c.cy].join(','), '--pose', Object.entries(prev.pose || {}).map(([x, y]) => x + '=' + y).join(',')); }
  const f = run(a);
  const fc = cerv(['--st', [f.kamera.azim, f.kamera.elev, f.kamera.dist, f.kamera.fov, f.kamera.cx, f.kamera.cy].join(','), '--pose', Object.entries(f.pose || {}).map(([x, y]) => x + '=' + y).join(',') || 'x=0'], 'cerv_f');
  dof[p] = { kamera: f.kamera, pose: f.pose }; fs.writeFileSync(dofF, JSON.stringify(dof, null, 1));
  out.fotky[p] = { iou_kamera_kontroly: k.iou, pose_kamera_kontroly: k.pose, iou_kamera_dofitovana: f.iou, iou_bez_plneni_der_dofit: f.iou_bez_plneni_der, kamera_dofit: f.kamera, pose_dofit: f.pose, chyby_lm_px: f.chyby_lm_px, cervena_kontrola: kc, cervena_dofit: fc };
  console.log(sku, 'kolo', kolo, p, 'IoU kamera kontroly', k.iou, '| dofit', f.iou, JSON.stringify(f.pose));
}
fs.appendFileSync(path.join(dir, 'kola.jsonl'), JSON.stringify(out) + '\n');
