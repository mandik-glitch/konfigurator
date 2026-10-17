// Srovnání modelu s fotografií ze STEJNÉ kamery (kamera_cNN.json z kontroly) – SKU 4932471723, 4932471724, 4932480623.
// node srovnej.mjs --sku 4932471723 --c 01 [--glb cesta.glb] [--pose drzadlo=90,...] [--hide predpona,...] [--tag nazev]
//     [--kam soubor.json (jiná kamera: {kamera:{azim,elev,dist,fov,roll,shiftX,shiftY}})] [--size 1200] [--ref-fov 1]
// Výstup: render do kufriky_cloud/srovnani_opravy/<SKU>/<tag>.png + .json (jen náš render a kamera; foto je ve scratchpadu),
//         dvojice foto | model | překryv do scratchpadu (KUF_SCRATCH).
import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { Renderer, kamera } from '../../kufriky_cloud/render/render.mjs';
const HERE = path.dirname(fileURLToPath(import.meta.url)), ROOT = path.join(HERE, '../..'), KC = path.join(ROOT, 'kufriky_cloud');
const opt = (k, d) => { const i = process.argv.indexOf('--' + k); return i > 0 ? process.argv[i + 1] : d; };
const sku = opt('sku'), c = opt('c', '01');
const SCR = process.env.KUF_SCRATCH || '/tmp/claude-0/-home-user-konfigurator/4afe04ea-52af-557e-a8a4-75a8d542e4f9/scratchpad';
const foto = path.join(SCR, 'kufry3', sku, `c${c}.jpg`);
const glb = opt('glb', path.join(HERE, '../modely', sku + '.glb'));
const tag = opt('tag', `c${c}`);
const size = +opt('size', 1200), MS = 600;
const pose = {}; for (const kv of opt('pose', '').split(',').filter(Boolean)) { const [k, v] = kv.split('='); pose[k] = +v; }
const hide = opt('hide', '').split(',').filter(Boolean);
const kamFile = opt('kam', path.join(KC, 'kontrola_john_v6', sku, `kamera_c${c}.json`));
const cam = JSON.parse(fs.readFileSync(kamFile)).kamera;
const cm = kamera({ azim: cam.azim, elev: cam.elev, dist: cam.dist, fov: cam.fov, roll: cam.roll || 0, shiftX: cam.shiftX, shiftY: cam.shiftY });
const outDir = path.join(KC, 'srovnani_opravy', sku); fs.mkdirSync(outDir, { recursive: true });
const scr = path.join(SCR, 'out'); fs.mkdirSync(scr, { recursive: true });
// maska fotografie
const maskFile = path.join(scr, `${sku}_c${c}_foto.bin`);
execFileSync('python3', [path.join(KC, 'nastroje/foto_maska.py'), foto, maskFile, String(MS)], { stdio: 'ignore' });
const mb = fs.readFileSync(maskFile); const mw = mb.readUInt32LE(0), mh = mb.readUInt32LE(4), mask = mb.slice(8);
// maska modelu
const R1 = await new Renderer().open(mw, mh); await R1.load(glb, true); if (Object.keys(pose).length) await R1.pose(pose); if (hide.length) await R1.hide(hide);
const m = await R1.mask(cm); await R1.close();
let I = 0, U = 0; for (let i = 0; i < m.length; i++) { const a = m[i], b = mask[i]; if (a & b) I++; if (a | b) U++; }
const iou = I / U;
// render
const R2 = await new Renderer().open(size, size); await R2.load(glb, false); if (Object.keys(pose).length) await R2.pose(pose); if (hide.length) await R2.hide(hide);
const png = path.join(outDir, tag + '.png'); await R2.png(cm, png); await R2.close();
fs.writeFileSync(path.join(outDir, tag + '.json'), JSON.stringify({ sku, pohled: tag, foto: `c${c}.jpg (jen ve scratchpadu, mimo repo)`, kamera: cam, kamera_zdroj: path.relative(ROOT, kamFile), pose, skryto: hide, iou: +iou.toFixed(4), iou_rozliseni_px: mw + 'x' + mh, poznamka: 'IoU = průnik/sjednocení obrysu modelu a produktu na fotografii při dané kameře; kamera je z ručních bodů (ne dofitovaná na tento model), proto IoU není důkaz tvaru.' }, null, 1));
const pair = path.join(scr, `${sku}_${tag}_dvojice.png`);
execFileSync('python3', [path.join(KC, 'nastroje/porovnej.py'), foto, png, pair, '640'], { stdio: 'ignore' });
console.log(JSON.stringify({ sku, tag, iou: +iou.toFixed(4), dvojice: pair, render: png }));
