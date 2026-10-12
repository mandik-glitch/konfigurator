// Srovnání přímého (téměř ortografického) pohledu na model s fotografií, která je těsně oříznutá na obrys výrobku.
// Volný odhad kamery (render/srovnej.mjs) tady selhává (obrys = skoro obdélník, kamera se "nafoukne"), proto je kamera pevná:
// azimut/elevace zadané, dlouhé ohnisko (fov 2°), výsledný render se ořízne na obrys a roztáhne na rozměr fotografie.
// Použití: node porovnej_celo.mjs --kod 8215526 --foto <foto.jpg> --pohled celo [--az 0] [--el 0] [--roll 0] [--pose vicko=0] [--fov 2 | --dist 6000 (fov = 2·atan(430/dist))] [--hide pref,pref]
import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { Renderer, kamera } from '../../kufriky_cloud/render/render.mjs';
const HERE = path.dirname(fileURLToPath(import.meta.url)), KC = path.join(HERE, '../../kufriky_cloud');
const opt = (k, d) => { const i = process.argv.indexOf('--' + k); return i > 0 ? process.argv[i + 1] : d; };
const kod = opt('kod'), foto = opt('foto'), pohled = opt('pohled'), sku = kod, glb = path.join(HERE, '../modely', kod + '.glb');
const az = +opt('az', 0), el = +opt('el', 0), roll = +opt('roll', 0);
const distOpt = opt('dist', null);
const fov = distOpt ? 2 * Math.atan(430 / +distOpt) * 180 / Math.PI : +opt('fov', 2);
const pose = {}; for (const kv of opt('pose', '').split(',').filter(Boolean)) { const [k, v] = kv.split('='); pose[k] = +v; }
const hide = opt('hide', '').split(',').filter(Boolean);
const scratch = process.env.KUF_SCRATCH || '/tmp/kuf_scratch'; fs.mkdirSync(scratch, { recursive: true });
const outDir = path.join(KC, 'srovnani', sku); fs.mkdirSync(outDir, { recursive: true });
const dist = distOpt ? +distOpt : 1700 * (2 / fov) * 6;     // bez --dist: dist úměrné 1/tan(fov/2), zobrazená výška ≈ 2·dist·tan(fov/2)
const R = await new Renderer().open(2000, 1200); await R.load(glb, false);
if (Object.keys(pose).length) await R.pose(pose); if (hide.length) await R.hide(hide);
const tmp = path.join(scratch, `${sku}_${pohled}_surovy.png`);
const hh = 2 * dist * Math.tan(fov * Math.PI / 360);   // výška záběru v mm
await R.png(kamera({ azim: az, elev: el, dist, fov, roll }), tmp); await R.close();
const png = path.join(outDir, pohled + '.png');
const fcrop = path.join(scratch, `${sku}_${pohled}_foto_orez.png`);
const py = `
import sys, numpy as np
from PIL import Image
# fotografie i render se oříznou na vlastní obrys; render se roztáhne na rozměr oříznuté fotografie
ph=Image.open(sys.argv[2]).convert('RGB'); pa=np.asarray(ph).astype(int).min(axis=2)<235
ys,xs=np.where(pa); fx0,fx1,fy0,fy1=xs.min(),xs.max()+1,ys.min(),ys.max()+1
fc=ph.crop((fx0,fy0,fx1,fy1)); fc.save(sys.argv[5])
im=Image.open(sys.argv[1]).convert('RGB'); a=np.asarray(im).astype(int)
m=a.min(axis=2)<238
ys,xs=np.where(m); x0,x1,y0,y1=xs.min(),xs.max()+1,ys.min(),ys.max()+1
c=im.crop((x0,y0,x1,y1)).resize(fc.size,Image.LANCZOS); c.save(sys.argv[3])
print('obrys fotografie px',fc.size,'obrys modelu px',x1-x0,y1-y0,'; poměr stran foto %.4f model %.4f'%(fc.size[0]/fc.size[1],(x1-x0)/(y1-y0)))
`;
execFileSync('python3', ['-I', '-c', py, tmp, foto, png, String(hh), fcrop], { stdio: 'inherit' });
const maskPy = `
import sys, numpy as np
from PIL import Image
f=np.asarray(Image.open(sys.argv[1]).convert('RGB')).astype(int).min(axis=2)<235
r=np.asarray(Image.open(sys.argv[2]).convert('RGB')).astype(int).min(axis=2)<238
print('IoU obrysu (po oříznutí na obrys): %.4f'%((f&r).sum()/(f|r).sum()))
`;
execFileSync('python3', ['-I', '-c', maskPy, fcrop, png], { stdio: 'inherit' });
fs.writeFileSync(path.join(outDir, pohled + '.json'), JSON.stringify({ sku, pohled, foto_repo_cesta: path.basename(path.dirname(foto)) + '/' + path.basename(foto) + ' (scratchpad, mimo repo)', pose, kamera: { azim: az, elev: el, roll, dist, fov, poznamka: 'téměř ortografický pohled, render oříznut na obrys a roztažen na rozměr fotografie' } }, null, 1));
const pair = path.join(scratch, `${sku}_${pohled}_dvojice.png`);
execFileSync('python3', [path.join(KC, 'nastroje/porovnej.py'), fcrop, png, pair, '700'], { stdio: 'inherit' });
console.log(pair);
