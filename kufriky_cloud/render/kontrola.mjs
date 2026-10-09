// Závěrečná kontrola všech pohledů: pro každý srovnani/<SKU>/<pohled>.json znovu vyrenderuje obrys modelu s uloženou kamerou
// a porovná ho s obrysem fotografie (IoU). Fotografie se jen čtou z kufriky_john/fotky/.
// Použití: node render/kontrola.mjs [SKU ...]  → tabulka + soubor srovnani/kontrola.json (jen čísla, žádné obrázky)
import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { Renderer, kamera } from './render.mjs';
const HERE = path.dirname(fileURLToPath(import.meta.url)), ROOT = path.join(HERE, '..');
const scratch = process.env.KUF_SCRATCH || '/tmp/kuf_scratch_kontrola'; fs.mkdirSync(scratch, { recursive: true });
const want = process.argv.slice(2);
const skus = fs.readdirSync(path.join(ROOT, 'srovnani')).filter(d => /^\d+$/.test(d)).filter(d => !want.length || want.includes(d));
const out = {}; let slabe = 0;
for (const sku of skus) {
  const glb = path.join(ROOT, 'modely', sku + '.glb'); if (!fs.existsSync(glb)) continue;
  const jsons = fs.readdirSync(path.join(ROOT, 'srovnani', sku)).filter(f => f.endsWith('.json'));
  out[sku] = {};
  for (const jf of jsons) {
    const j = JSON.parse(fs.readFileSync(path.join(ROOT, 'srovnani', sku, jf), 'utf8')); if (!j.kamera || !j.foto_repo_cesta) continue;
    const foto = path.join(ROOT, '..', j.foto_repo_cesta); if (!fs.existsSync(foto)) { console.log(sku, j.pohled, 'fotografie chybí'); continue; }
    const mf = path.join(scratch, `${sku}_${j.pohled}.bin`);
    execFileSync('python3', [path.join(ROOT, 'nastroje/foto_maska.py'), foto, mf, '320'], { stdio: ['ignore', 'ignore', 'inherit'] });
    const mb = fs.readFileSync(mf), w = mb.readUInt32LE(0), h = mb.readUInt32LE(4), mask = mb.slice(8);
    const R = await new Renderer().open(w, h); await R.load(glb, true); if (j.pose && Object.keys(j.pose).length) await R.pose(j.pose);
    const c = j.kamera; const m = await R.mask(kamera({ azim: c.azim, elev: c.elev, dist: c.dist, fov: c.fov, roll: c.roll, shiftX: c.shiftX, shiftY: c.shiftY }));
    await R.close();
    let I = 0, U = 0; for (let i = 0; i < m.length; i++) { if (m[i] & mask[i]) I++; if (m[i] | mask[i]) U++; }
    const iou = I / U; out[sku][j.pohled] = { iou: +iou.toFixed(4), foto: j.foto_repo_cesta, pose: j.pose || {} };
    if (iou < 0.95) slabe++;
    console.log(`${sku}  ${j.pohled.padEnd(24)} IoU ${iou.toFixed(4)}  ${iou < 0.95 ? '<<< SLABÉ' : ''}  ${path.basename(j.foto_repo_cesta)}`);
  }
}
fs.writeFileSync(path.join(ROOT, 'srovnani', 'kontrola.json'), JSON.stringify(out, null, 1));
console.log(slabe ? `${slabe} pohledů pod 0.95` : 'všechny pohledy ≥ 0.95');
