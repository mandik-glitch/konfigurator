// Rychlé IoU obrysu modelu proti fotografii při ULOŽENÉ kameře (srovnani/<sku>/<pohled>.json z fit_lm_2329206.mjs).
// Použití: node iou_kamera_2329206.mjs --glb ../modely/2437394.glb --foto foto.jpg --sku 2437394 --pohled c02-lm [--cervena 1] [--uhel 98]
import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { Renderer, kamera } from '../../kufriky_cloud/render/render.mjs';
const HERE = path.dirname(fileURLToPath(import.meta.url)), KC = path.join(HERE, '../../kufriky_cloud');
// vyplnění děr v masce (okno madla je na fotografiích uzavřené rukojetí; maska fotografie má díry vyplněné zaplavením od okraje – stejné pro render)
function vypln(m, w, h) {
  const out = Uint8Array.from(m), q = new Int32Array(w * h); let a = 0, b = 0; const vis = new Uint8Array(w * h);
  const push = i => { if (!vis[i] && !m[i]) { vis[i] = 1; q[b++] = i; } };
  for (let x = 0; x < w; x++) { push(x); push((h - 1) * w + x); } for (let y = 0; y < h; y++) { push(y * w); push(y * w + w - 1); }
  while (a < b) { const i = q[a++], x = i % w, y = (i / w) | 0; if (x > 0) push(i - 1); if (x < w - 1) push(i + 1); if (y > 0) push(i - w); if (y < h - 1) push(i + w); }
  for (let i = 0; i < w * h; i++) if (!m[i] && !vis[i]) out[i] = 1; return out;
}
const opt = (k, d) => { const i = process.argv.indexOf('--' + k); return i > 0 ? process.argv[i + 1] : d; };
const glb = opt('glb'), foto = opt('foto'), sku = opt('sku'), pohled = opt('pohled');
const scratch = process.env.KUF_SCRATCH || '/tmp/kuf_scratch'; fs.mkdirSync(scratch, { recursive: true });
const maskFile = path.join(scratch, `${sku}_${pohled}_iou.bin`);
if (opt('cervena', null) !== null) execFileSync('python3', [path.join(HERE, 'maska_cervena.py'), foto, maskFile, '320'], { stdio: 'ignore' });
else execFileSync('python3', [path.join(KC, 'nastroje/foto_maska.py'), foto, maskFile, '320'], { stdio: 'ignore' });
const mb = fs.readFileSync(maskFile); const w = mb.readUInt32LE(0), h = mb.readUInt32LE(4), mask = mb.slice(8);
const j = JSON.parse(fs.readFileSync(path.join(KC, 'srovnani', sku, pohled + '.json'))), c = j.kamera;
const R = await new Renderer().open(w, h); await R.load(glb, true);
const pose = opt('uhel', null) !== null ? { vicko: +opt('uhel') } : j.pose; if (pose && Object.keys(pose).length) await R.pose(pose);
const m = vypln(await R.mask(kamera({ azim: c.azim, elev: c.elev, dist: c.dist, fov: c.fov, roll: c.roll, shiftX: c.shiftX, shiftY: c.shiftY })), w, h);
let I = 0, U = 0; for (let i = 0; i < m.length; i++) { const a = m[i], b = mask[i]; if (a & b) I++; if (a | b) U++; }
await R.close(); console.log(pohled, 'IoU', (I / U).toFixed(4), JSON.stringify(pose));
