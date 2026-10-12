// Znovu sestaví model 2437399 a spočítá IoU obrysu proti fotografiím c01 (čelní pohled), c02 a c03 (víko otevřené ~88°); do kufriky_cloud/srovnani/2437399/ uloží
// JEN vlastní rendery (<pohled>.png) a json (kamera, úhel víka, IoU, URL fotografie). Fotografie se čtou ze scratchpadu (mimo repo), do repa se nedostanou.
// Kamery pro c02/c03: fit_2437399.mjs (odhad z obrysu, roll = 0), pro c01: téměř ortografický pohled oříznutý na obrys (porovnej_celo.mjs).
// Použití: FOTO=<složka s c01..c05.jpg> [KUF_SCRATCH=<scratch>] node srovnej_vse_2437399.mjs [--refit]   (--refit znovu odhadne kamery c02/c03 z aktuálního modelu)
import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { Renderer, kamera } from '../../kufriky_cloud/render/render.mjs';
const HERE = path.dirname(fileURLToPath(import.meta.url)), KH = path.join(HERE, '..'), KC = path.join(HERE, '../../kufriky_cloud');
const FOTO = process.env.FOTO; if (!FOTO) { console.error('FOTO=složka s fotografiemi 2437399 (c01..c03.jpg)'); process.exit(1); }
const scratch = process.env.KUF_SCRATCH || '/tmp/kuf_scratch'; fs.mkdirSync(scratch, { recursive: true });
const sku = '2437399', outDir = path.join(KC, 'srovnani', sku), glb = path.join(KH, 'modely', sku + '.glb'); fs.mkdirSync(outDir, { recursive: true });
const urls = {}; for (const l of fs.readFileSync(path.join(KH, 'fotky_url.tsv'), 'utf8').split('\n')) { const [s, f, u] = l.split('\t'); if (s === sku) urls[f] = u; }
const run = (f, a) => execFileSync('node', [path.join(HERE, f), ...a], { encoding: 'utf8', env: { ...process.env, KUF_SCRATCH: scratch } });
const patch = (pohled, o) => { const f = path.join(outDir, pohled + '.json'); const j = JSON.parse(fs.readFileSync(f, 'utf8')); Object.assign(j, o); fs.writeFileSync(f, JSON.stringify(j, null, 1)); };
console.log(execFileSync('node', [path.join(KH, 'vytvor.mjs'), sku], { encoding: 'utf8' }).trim());
const res = {};
// c01: čelní pohled
{
  const out = run('porovnej_celo.mjs', ['--glb', glb, '--foto', path.join(FOTO, 'c01.jpg'), '--sku', sku, '--pohled', 'celo']);
  const iou = +out.match(/IoU obrysu[^:]*:\s*([\d.]+)/)[1]; patch('celo', { iou, foto_url: urls['c01.jpg'] }); res.celo = iou;
}
// c02, c03: kamery z fit_2437399.mjs (--refit) nebo uložené
const START = { 'otevreny-c02': '41.0,48.0,2957,17.3,-0.178,0.0734,89', 'otevreny-c03': '42.1,48.6,2216,20.06,0.0419,0.1643,87' };
for (const [pohled, c] of [['otevreny-c02', 'c02'], ['otevreny-c03', 'c03']]) {
  const foto = path.join(FOTO, c + '.jpg'), jf = path.join(outDir, pohled + '.json');
  if (process.argv.includes('--refit') || !fs.existsSync(jf)) run('fit_2437399.mjs', ['--glb', glb, '--foto', foto, '--pohled', pohled, '--cervena', '1', '--start', START[pohled]]);
  const j = JSON.parse(fs.readFileSync(jf, 'utf8')), k = j.kamera;
  const maskFile = path.join(scratch, `${sku}_${pohled}_vyh.bin`);
  execFileSync('python3', [path.join(HERE, 'maska_cervena.py'), foto, maskFile, '320'], { stdio: 'ignore' });
  const mb = fs.readFileSync(maskFile), w = mb.readUInt32LE(0), h = mb.readUInt32LE(4), mask = mb.slice(8);
  const cam = kamera({ azim: k.azim, elev: k.elev, dist: k.dist, fov: k.fov, roll: k.roll || 0, shiftX: k.shiftX, shiftY: k.shiftY });
  const R = await new Renderer().open(w, h); await R.load(glb, true); await R.pose(j.pose); const m = await R.mask(cam); await R.close();
  let I = 0, U = 0; for (let i = 0; i < m.length; i++) { if (m[i] & mask[i]) I++; if (m[i] | mask[i]) U++; }
  const iou = +(I / U).toFixed(4);
  const dim = execFileSync('python3', ['-I', '-c', 'import sys;from PIL import Image;print(*Image.open(sys.argv[1]).size)', foto], { encoding: 'utf8' }).trim().split(' ').map(Number);
  const H = 800, W = Math.round(dim[0] * H / dim[1]);
  const R2 = await new Renderer().open(W, H); await R2.load(glb, false); await R2.pose(j.pose); await R2.png(cam, path.join(outDir, pohled + '.png')); await R2.close();
  patch(pohled, { iou, foto_url: urls[c + '.jpg'], maska: 'podle červené barvy (šipky/popisky a pomocná vanička mimo výrobek se nepočítají)' }); res[pohled] = iou;
  const pair = path.join(scratch, `${sku}_${pohled}_dvojice.png`);
  execFileSync('python3', [path.join(KC, 'nastroje/porovnej.py'), foto, path.join(outDir, pohled + '.png'), pair, '700'], { stdio: 'ignore' });
}
console.log('IoU obrysu:', JSON.stringify(res));
