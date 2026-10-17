// Jedno kolo srovnání: pro každou fotografii SKU spočítá IoU (a) při kameře z kontroly (bez dofitu) a (b) při kameře dofitované k našemu modelu (+ úhel víka),
// výsledek připíše do kufriky_cloud/srovnani_opravy/<SKU>/kola.jsonl. Použití: node kolo.mjs <SKU> <číslo kola> "popis změny" [pohled ...]
import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
const HERE = path.dirname(fileURLToPath(import.meta.url));
const [sku, kolo, popis, ...ph] = process.argv.slice(2);
const cfgF = path.join(HERE, `cfg_${sku}.json`), cfg = JSON.parse(fs.readFileSync(cfgF, 'utf8'));
const poh = ph.length ? ph : Object.keys(cfg).filter(k => !k.includes('nahore'));
const glbDef = path.join(HERE, '../modely', sku + '.glb');
const out = { sku, kolo: +kolo, popis, cas: new Date().toISOString(), fotky: {} };
for (const p of poh) {
  const glb = cfg[p].glb || glbDef, pose0 = cfg[p].pose || {};
  const base = ['srov.mjs', '--cfg', cfgF, '--pohled', p, '--glb', glb, '--bez-rendru', '--tag', p];
  const run = a => JSON.parse(execFileSync('node', [...base, ...a], { cwd: HERE, encoding: 'utf8', maxBuffer: 1e8 }).trim().split('\n').pop());
  const k = run([]);                                                     // kamera z kontroly, úhel víka z kontroly
  const f = run(['--fit', '--free', 'azim,elev,dist,fov,cx,cy' + ('vicko' in pose0 ? ',vicko' : '')]);
  out.fotky[p] = { iou_kamera_kontroly: k.iou, iou_kamera_dofitovana: f.iou, kamera_dofit: f.kamera, pose_dofit: f.pose, chyby_lm_px: f.chyby_lm_px };
  console.log(sku, 'kolo', kolo, p, 'IoU kontrola', k.iou, 'dofit', f.iou, JSON.stringify(f.pose));
}
const dir = path.join(HERE, '../../kufriky_cloud/srovnani_opravy', sku); fs.mkdirSync(dir, { recursive: true });
fs.appendFileSync(path.join(dir, 'kola.jsonl'), JSON.stringify(out) + '\n');
