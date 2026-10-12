// IoU obrysu modelu proti studiové fotografii při ULOŽENÉ kameře a póze (kufriky_cloud/srovnani/<sku>/<pohled>.json z fit_ts2.mjs) + render modelu do repa.
// Použití: node iou_ts2.mjs --glb ../modely/DWST83294.glb --foto foto.jpg --sku DWST83294 --pohled sikmo-c02 [--L 640] [--png 1] [--len 1100]
// Fotografie se jen čte (scratchpad); do repa se zapisuje jen náš render (srovnani/<sku>/<pohled>.png) a json s IoU. Do scratchpadu: dvojice foto | model | rozdíl obrysů (červeně jen model, modře jen foto).
import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { Renderer, kamera } from '../../kufriky_cloud/render/render.mjs';
const HERE = path.dirname(fileURLToPath(import.meta.url)), KC = path.join(HERE, '../../kufriky_cloud');
const opt = (k, d) => { const i = process.argv.indexOf('--' + k); return i > 0 ? process.argv[i + 1] : d; };
const glb = opt('glb'), foto = opt('foto'), sku = opt('sku'), pohled = opt('pohled'), L = opt('L', '640');
const scratch = process.env.KUF_SCRATCH || '/tmp/kuf_scratch'; fs.mkdirSync(scratch, { recursive: true });
const jf = path.join(KC, 'srovnani', sku, pohled + '.json'), j = JSON.parse(fs.readFileSync(jf)), c = j.kamera;
const maskFile = path.join(scratch, `${sku}_${pohled}_iou.bin`);
execFileSync('python3', ['-I', path.join(KC, 'nastroje/foto_maska.py'), foto, maskFile, L], { stdio: 'ignore' });
const mb = fs.readFileSync(maskFile); const w = mb.readUInt32LE(0), h = mb.readUInt32LE(4), mask = mb.slice(8);
const cam = kamera({ azim: c.azim, elev: c.elev, dist: c.dist, fov: c.fov, roll: c.roll, shiftX: c.shiftX, shiftY: c.shiftY });
const R = await new Renderer().open(w, h); await R.load(glb, true); if (j.pose && Object.keys(j.pose).length) await R.pose(j.pose);
const m = await R.mask(cam); let I = 0, U = 0, Mo = 0, Fo = 0;
for (let i = 0; i < m.length; i++) { const a = m[i], b = mask[i]; if (a & b) I++; if (a | b) U++; }
await R.close();
const iou = I / U; console.log(pohled, 'IoU', iou.toFixed(4), JSON.stringify(j.pose));
j.iou = iou; j.kamera.iou = iou; j.iou_rozliseni_masky = `${w}x${h}`; fs.writeFileSync(jf, JSON.stringify(j, null, 1));
if (opt('png', '1') !== '0') {
  const len = +opt('len', 1100), sc = len / Math.max(w, h), W = Math.round(w * sc), H = Math.round(h * sc);
  const R2 = await new Renderer().open(W, H); await R2.load(glb, false); if (j.pose && Object.keys(j.pose).length) await R2.pose(j.pose);
  const png = path.join(KC, 'srovnani', sku, pohled + '.png'); await R2.png(cam, png); await R2.close();
  execFileSync('python3', ['-I', path.join(HERE, 'dvojice_ts2.py'), foto, png, path.join(scratch, `${sku}_${pohled}_dvojice.png`)], { stdio: 'inherit' });
}
