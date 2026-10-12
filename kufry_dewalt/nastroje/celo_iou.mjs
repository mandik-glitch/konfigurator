// Srovnání přímého (téměř ortografického) pohledu na model s fotografií (obrys, IoU) pro NEOŘÍZNUTÉ studiové fotografie na bílém pozadí.
// Postup: render modelu (fov 2°, dlouhá ohnisková vzdálenost) při elevaci el → maska renderu i fotografie se oříznou na obrys a render se roztáhne na rozměr obrysu fotografie → IoU.
// Elevace fotografie není známa: --scan "6:13:0.5" projde elevace a vybere nejlepší (IoU), azim zadán (--az, 0 = čelní pohled).
// Použití: node celo_iou.mjs --glb ../modely/DWST83346.glb --foto <foto.jpg> --sku DWST83346 --pohled celo-c02 [--az 0] [--el 9.5 | --scan 6:13:0.5] [--dist 6000] [--pose drzadlo=0] [--hide pref]
// Výstup: ../../kufriky_cloud/srovnani/<sku>/<pohled>.png|json (jen náš render a parametry), scratchpad: dvojice foto | model | překryv.
import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { Renderer, kamera } from '../../kufriky_cloud/render/render.mjs';
const HERE = path.dirname(fileURLToPath(import.meta.url)), KC = path.join(HERE, '../../kufriky_cloud');
const opt = (k, d) => { const i = process.argv.indexOf('--' + k); return i > 0 ? process.argv[i + 1] : d; };
const glb = opt('glb'), foto = opt('foto'), sku = opt('sku'), pohled = opt('pohled');
const az = +opt('az', 0), roll = +opt('roll', 0), dist = +opt('dist', 6000), fov = +opt('fov', 2 * Math.atan(270 / dist) * 180 / Math.PI)   // výchozí vzdálenost 6 m (teleobjektiv), zorné pole tak, aby se kufr vešel do čtvercového záběru;
const pose = {}; for (const kv of opt('pose', '').split(',').filter(Boolean)) { const [k, v] = kv.split('='); pose[k] = +v; }
const hide = opt('hide', '').split(',').filter(Boolean);
const scan = opt('scan', null), els = scan ? (() => { const [a, b, s] = scan.split(':').map(Number); const o = []; for (let e = a; e <= b + 1e-9; e += s) o.push(+e.toFixed(3)); return o; })() : [+opt('el', 0)];
const scratch = process.env.KUF_SCRATCH || '/tmp/kuf_scratch'; fs.mkdirSync(scratch, { recursive: true });
const outDir = path.join(KC, 'srovnani', sku); fs.mkdirSync(outDir, { recursive: true });
const R = await new Renderer().open(1600, 1600); await R.load(glb, false);
if (Object.keys(pose).length) await R.pose(pose); if (hide.length) await R.hide(hide);
const PY = `
import sys, numpy as np
from PIL import Image
from PIL import ImageDraw
def mask(fn, thr):
    a = np.asarray(Image.open(fn).convert('RGB')).astype(int); m = a.min(axis=2) < thr
    p = Image.new('L', (m.shape[1] + 4, m.shape[0] + 4), 0); p.paste(Image.fromarray((m * 255).astype('uint8')), (2, 2))   # vyplnění děr (odlesky kovu nad prahem)
    ImageDraw.floodfill(p, (0, 0), 128); return np.asarray(p)[2:-2, 2:-2] != 128
def crop(m):
    ys, xs = np.where(m); return m[ys.min():ys.max()+1, xs.min():xs.max()+1]
f = crop(mask(sys.argv[1], 235)); r = crop(mask(sys.argv[2], 238))
from PIL import Image as I
r2 = np.asarray(I.fromarray((r*255).astype('uint8')).resize((f.shape[1], f.shape[0]), I.NEAREST)) > 127
print('%.5f' % ((f & r2).sum() / (f | r2).sum()), f.shape[1], f.shape[0], r.shape[1], r.shape[0])
`;
let best = null;
for (const el of els) {
  const tmp = path.join(scratch, `${sku}_${pohled}_el${el}.png`);
  await R.png(kamera({ azim: az, elev: el, dist, fov, roll }), tmp);
  const o = execFileSync('python3', ['-I', '-c', PY, foto, tmp], { encoding: 'utf8' }).trim().split(' ');
  const iou = +o[0]; console.log('el', el, 'IoU', iou);
  if (!best || iou > best.iou) best = { iou, el, tmp, fw: +o[1], fh: +o[2], rw: +o[3], rh: +o[4] };
}
await R.close();
// konečný render (oříznutý na obrys) + dvojice
const png = path.join(outDir, pohled + '.png');
const CP = `
import sys, numpy as np
from PIL import Image
im = Image.open(sys.argv[1]).convert('RGB'); a = np.asarray(im).astype(int); m = a.min(axis=2) < 238
ys, xs = np.where(m); im.crop((xs.min(), ys.min(), xs.max()+1, ys.max()+1)).save(sys.argv[2])
f = np.asarray(Image.open(sys.argv[3]).convert('RGB')).astype(int).min(axis=2) < 235; ys, xs = np.where(f)
Image.open(sys.argv[3]).convert('RGB').crop((xs.min(), ys.min(), xs.max()+1, ys.max()+1)).save(sys.argv[4])
`;
const fcrop = path.join(scratch, `${sku}_${pohled}_fotocrop.png`);
execFileSync('python3', ['-I', '-c', CP, best.tmp, png, foto, fcrop]);
fs.writeFileSync(path.join(outDir, pohled + '.json'), JSON.stringify({ sku, pohled, foto_repo_cesta: path.basename(path.dirname(foto)) + '/' + path.basename(foto) + ' (mimo repo, scratchpad)', pose, kamera: { azim: az, elev: best.el, roll, dist, fov, poznamka: 'téměř ortografický pohled; render i fotografie oříznuty na obrys, render roztažen na rozměr obrysu fotografie; elevace vybrána maximem IoU' }, iou: best.iou, obrys_foto_px: [best.fw, best.fh], obrys_render_px: [best.rw, best.rh] }, null, 1));
const pair = path.join(scratch, `${sku}_${pohled}_dvojice.png`);
execFileSync('python3', [path.join(KC, 'nastroje/porovnej.py'), fcrop, png, pair, '700'], { stdio: 'inherit' });
console.log(JSON.stringify({ iou: best.iou, el: best.el, pair }));
