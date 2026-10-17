// Srovnání modelu s fotografií při ZADANÉ kameře (kamery_<SKU>.json): IoU obrysu + render + dvojice foto | model | překryv.
// Použití: node iou.mjs --glb ../modely/4932464078.glb --foto <scratchpad>/cNN.jpg --kam ../../kufriky_cloud/srovnani_opravy/4932464078/kamery_4932464078.json --pohled c01 [--kamvar z_bodu]
//         [--pose madlo_1=0,madlo_2=0,vicko=0] [--ymin 790] [--xmin 235] [--rend png] [--pair png] [--len 1200] [--maska 320] [--bez-rendru]
// Fotografie se jen čte (scratchpad), do repa jde jen náš render PNG (--rend) a JSON s výsledky.
import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { Renderer, kamera } from './render.mjs';
const HERE = path.dirname(fileURLToPath(import.meta.url)), KC = path.join(HERE, '../../kufriky_cloud');
const opt = (k, d) => { const i = process.argv.indexOf('--' + k); return i > 0 ? process.argv[i + 1] : d; };
const flag = k => process.argv.includes('--' + k);
const glb = opt('glb'), foto = opt('foto'), pohled = opt('pohled'), kamFile = opt('kam');
const scratch = process.env.KUF_SCRATCH || '/tmp/kuf_scratch'; fs.mkdirSync(scratch, { recursive: true });
const kams = JSON.parse(fs.readFileSync(kamFile, 'utf8'));
let cam = kams[pohled]; if (!cam) throw new Error('kamera ' + pohled + ' není v ' + kamFile);
const kv = opt('kamvar', null); if (kv) cam = cam[kv];
const pose = {}; for (const s of (opt('pose', '') || '').split(',').filter(Boolean)) { const [k, v] = s.split('='); pose[k] = +v; }
const ML = +opt('maska', 320);
const maskFile = path.join(scratch, `mask_${pohled}_${ML}.bin`);
execFileSync('python3', [path.join(KC, 'nastroje/foto_maska.py'), foto, maskFile, String(ML)], { stdio: 'ignore' });
const mb = fs.readFileSync(maskFile); const w = mb.readUInt32LE(0), h = mb.readUInt32LE(4), mask = mb.slice(8);
const W0 = cam.w ?? 1200, H0 = cam.h ?? 1200;
const kmr = (cam) => kamera({ azim: cam.azim, elev: cam.elev, dist: cam.dist, fov: cam.fov, roll: cam.roll || 0, shiftX: (cam.cx - W0 / 2) / W0, shiftY: (cam.cy - H0 / 2) / H0 });
const R = await new Renderer().open(w, h); await R.load(glb, true); if (Object.keys(pose).length) await R.pose(pose);
const m = await R.mask(kmr(cam));
const ymin = +opt('ymin', 0) * h / H0, xmin = +opt('xmin', 0) * w / W0, ymax = +opt('ymax', 1e9) * h / H0, xmax = +opt('xmax', 1e9) * w / W0;
let I = 0, U = 0;
for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) { if (y < ymin || x < xmin || y > ymax || x > xmax) continue; const i = y * w + x; const a = m[i], b = mask[i]; if (a & b) I++; if (a | b) U++; }
const iou = U ? I / U : 0;
// diagnostika: kde se liší (podíl FN = foto bez modelu, FP = model bez fota)
let FN = 0, FP = 0; for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) { if (y < ymin || x < xmin || y > ymax || x > xmax) continue; const i = y * w + x; if (mask[i] && !m[i]) FN++; if (m[i] && !mask[i]) FP++; }
let out = { pohled, iou: +iou.toFixed(4), foto_bez_modelu: +(FN / U).toFixed(4), model_bez_fota: +(FP / U).toFixed(4), pose };
if (!flag('bez-rendru')) {
  const len = +opt('len', 1200), rend = opt('rend', path.join(scratch, `rend_${pohled}.png`));
  await R.resize(len, len); await R.load(glb, false); if (Object.keys(pose).length) await R.pose(pose);
  await R.png(kmr(cam), rend); out.render = rend;
  const pair = opt('pair', path.join(scratch, `dvojice_${pohled}.png`));
  execFileSync('python3', [path.join(HERE, 'dvojice.py'), foto, rend, pair, '640', maskFile], { stdio: 'ignore' }); out.dvojice = pair;
}
await R.close();
console.log(JSON.stringify(out));
