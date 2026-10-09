// Srovnání fotografie a modelu ze STEJNÉHO úhlu.
//  1) z fotografie (bílé pozadí) udělá masku (fotografie se jen čte; nic se neukládá do repa),
//  2) najde kameru, při které se silueta modelu (z GLB) nejlépe kryje s fotografií (IoU),
//  3) vyrenderuje náš model s touto kamerou (PNG do repa: srovnani/<SKU>/<pohled>.png + .json s kamerou a odkazem na fotku),
//  4) do scratchpadu uloží dvojici fotografie | render | překryv obrysu (cizí fotografie se do repa nedostane).
// Použití:
//  node render/srovnej.mjs --glb modely/4932464082.glb --foto ../kufriky_john/fotky/4932464082/c01.jpg --sku 4932464082 --pohled sikmo-celo-1
//        [--fov 20] [--pose vicko=0] [--start 30,25] [--reuse] [--scratch /cesta] [--len 1100]
import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { Renderer, kamera } from './render.mjs';
import { fitKamera } from './fit.mjs';
const HERE = path.dirname(fileURLToPath(import.meta.url)), ROOT = path.join(HERE, '..');
const opt = (k, d) => { const i = process.argv.indexOf('--' + k); return i > 0 ? process.argv[i + 1] : d; };
const flag = k => process.argv.includes('--' + k);
const glb = opt('glb'), foto = opt('foto'), sku = opt('sku'), pohled = opt('pohled');
if (!glb || !foto || !sku || !pohled) { console.error('chybí --glb --foto --sku --pohled'); process.exit(1); }
const scratch = opt('scratch', process.env.KUF_SCRATCH || '/tmp/kuf_scratch'); fs.mkdirSync(scratch, { recursive: true });
const outDir = path.join(ROOT, 'srovnani', sku); fs.mkdirSync(outDir, { recursive: true });
const fov = +opt('fov', 20), len = +opt('len', 1100);
const poseStr = opt('pose', ''); const pose = {}; for (const kv of poseStr.split(',').filter(Boolean)) { const [k, v] = kv.split('='); pose[k] = +v; }
const hide = opt('hide', '').split(',').filter(Boolean);
const maskFile = path.join(scratch, `${sku}_${pohled}.bin`);
execFileSync('python3', [path.join(ROOT, 'nastroje/foto_maska.py'), foto, maskFile, '320'], { stdio: 'inherit' });
const mb = fs.readFileSync(maskFile); const w = mb.readUInt32LE(0), h = mb.readUInt32LE(4), mask = mb.slice(8);
const jsonFile = path.join(outDir, pohled + '.json');
// 1. kamera
let cam;
if (flag('reuse') && fs.existsSync(jsonFile)) cam = JSON.parse(fs.readFileSync(jsonFile, 'utf8')).kamera;
else {
  const R = await new Renderer().open(w, h); await R.load(glb, true); if (Object.keys(pose).length) await R.pose(pose); if (hide.length) await R.hide(hide);
  const st = opt('start', null);
  cam = await fitKamera(R, mask, w, h, { fov, fitFov: opt('fov', null) === null, startAz: st ? +st.split(',')[0] : null, startEl: st ? +st.split(',')[1] : null, dist0: +opt('dist', 1500) });
  await R.close();
}
// 2. render ve velikosti fotografie (delší strana = len)
const sc = len / Math.max(w, h), W = Math.round(w * sc), H = Math.round(h * sc);
const R2 = await new Renderer().open(W, H); await R2.load(glb, false); if (Object.keys(pose).length) await R2.pose(pose); if (hide.length) await R2.hide(hide);
const camObj = kamera({ azim: cam.azim, elev: cam.elev, dist: cam.dist, fov: cam.fov ?? fov, roll: cam.roll, shiftX: cam.shiftX, shiftY: cam.shiftY });
const png = path.join(outDir, pohled + '.png'); await R2.png(camObj, png); await R2.close();
// 3. meta (odkaz na fotografii z index.tsv, pokud je v kufriky_john/fotky)
let url = null; try { const idx = fs.readFileSync(path.join(ROOT, '../kufriky_john/fotky/index.tsv'), 'utf8').split('\n'); const rel = path.relative(path.join(ROOT, '../kufriky_john'), path.resolve(foto)).replace(/\\/g, '/'); const row = idx.find(l => l.startsWith(rel + '\t')); if (row) url = row.split('\t')[1]; } catch { /* nic */ }
fs.writeFileSync(jsonFile, JSON.stringify({ sku, pohled, foto_repo_cesta: path.relative(path.join(ROOT, '..'), path.resolve(foto)), foto_url: url, pose, kamera: cam, iou: cam.iou, poznamka: 'Kamera odhadnuta z obrysu fotografie (IoU); ohnisko je pevně zvolené, ne změřené.' }, null, 1));
// 4. dvojice do scratchpadu
const pair = path.join(scratch, `${sku}_${pohled}_dvojice.png`);
execFileSync('python3', [path.join(ROOT, 'nastroje/porovnej.py'), foto, png, pair, '700'], { stdio: 'inherit' });
console.log(JSON.stringify({ iou: cam.iou, azim: cam.azim, elev: cam.elev, dist: cam.dist, render: png, dvojice: pair }));
