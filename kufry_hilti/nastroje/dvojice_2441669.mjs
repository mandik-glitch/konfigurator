// Dvojice fotografie | model | překryv (50 %) při uložené kameře srovnani/2441669/<pohled>.json. Fotografie se jen čte (scratchpad), výstup jde do scratchpadu.
// Použití: node dvojice_2441669.mjs --glb ../modely/2441669.glb --foto c03.jpg --pohled otevreny-c03 [--out dvojice.png] [--vlastni-render srovnani.png]
import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { Renderer, kamera } from '../../kufriky_cloud/render/render.mjs';
const HERE = path.dirname(fileURLToPath(import.meta.url)), KC = path.join(HERE, '../../kufriky_cloud');
const opt = (k, d) => { const i = process.argv.indexOf('--' + k); return i > 0 ? process.argv[i + 1] : d; };
const glb = opt('glb'), foto = opt('foto'), pohled = opt('pohled'), sku = '2441669';
const scratch = process.env.KUF_SCRATCH || '/tmp/kuf_scratch'; fs.mkdirSync(scratch, { recursive: true });
const j = JSON.parse(fs.readFileSync(path.join(KC, 'srovnani', sku, pohled + '.json'))), c = j.kamera;
const dim = execFileSync('python3', ['-I', '-c', 'import sys;from PIL import Image;im=Image.open(sys.argv[1]);print(im.width,im.height)', foto]).toString().trim().split(' ').map(Number);
const R = await new Renderer().open(dim[0], dim[1]); await R.load(glb, false);
const png = path.join(scratch, `${sku}_${pohled}_model.png`);
await R.png(kamera({ azim: c.azim, elev: c.elev, dist: c.dist, fov: c.fov, roll: c.roll, shiftX: c.shiftX, shiftY: c.shiftY }), png); await R.close();
const out = opt('out', path.join(scratch, `${sku}_${pohled}_dvojice.png`));
execFileSync('python3', ['-I', '-c', `
import sys
from PIL import Image
f=Image.open(sys.argv[1]).convert('RGB'); m=Image.open(sys.argv[2]).convert('RGB').resize(f.size)
b=Image.blend(f,m,0.5)
o=Image.new('RGB',(f.width*3,f.height),'white'); o.paste(f,(0,0)); o.paste(m,(f.width,0)); o.paste(b,(2*f.width,0)); o.save(sys.argv[3])
`, foto, png, out]);
if (opt('vlastni-render', null)) { fs.copyFileSync(png, path.join(KC, 'srovnani', sku, opt('vlastni-render'))); }   // jen náš render (ne fotografie) do repa
console.log(out);
