// Výstupní rendery (jen náš model, bílé pozadí) do kufriky_cloud/srovnani_opravy/<SKU>/: z kamer dofitovaných k fotografiím (<pohled>_model.png)
// a ze tří standardních pohledů (zepředu zprava, zezadu zleva, zhora) v zavřené poloze + víko otevřené.
// node final_render.mjs <SKU> [--len 900]
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { Renderer, kamera } from './render.mjs';
const HERE = path.dirname(fileURLToPath(import.meta.url));
const sku = process.argv[2], len = +(process.argv[process.argv.indexOf('--len') + 1] || 900);
const dir = path.join(HERE, '../../kufriky_cloud/srovnani_opravy', sku);
const dof = JSON.parse(fs.readFileSync(path.join(dir, `kamery_dofit_${sku}.json`), 'utf8'));
const cfg = JSON.parse(fs.readFileSync(path.join(HERE, `cfg_${sku}.json`), 'utf8'));
const R = await new Renderer().open(len, len);
const kmr = c => kamera({ azim: c.azim, elev: c.elev, dist: c.dist, fov: c.fov, roll: c.roll || 0, shiftX: (c.cx - 600) / 1200, shiftY: (c.cy - 600) / 1200 });
for (const [p, d] of Object.entries(dof)) {
  const glb = cfg[p]?.glb ? path.resolve(HERE, cfg[p].glb) : path.join(HERE, '../modely', sku + '.glb');
  await R.load(glb, false); await R.pose(d.pose || {}); await R.png(kmr(d.kamera), path.join(dir, `${p}_model.png`));
}
const glb = path.join(HERE, '../modely', sku + '.glb'); await R.load(glb, false);
const T = [0, 0, 0], dist = 1900;
const views = { zavreno_predni: [32, 22, {}], zavreno_zadni: [210, 24, {}], zavreno_shora: [0, 85, {}], otevreno: [28, 32, { vicko: 100, trmen_L: 140, trmen_P: 140 }] };
for (const [n, [az, el, pose]] of Object.entries(views)) { await R.pose(pose); await R.png(kamera({ azim: az, elev: el, dist, fov: 28, target: T }), path.join(dir, `${n}.png`)); }
await R.close(); console.log('hotovo', sku);
