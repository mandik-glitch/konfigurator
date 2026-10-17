// Jeden render modelu z kamery zadané na příkazové řádce: node render1.mjs --glb m.glb --az 30 --el 40 --dist 3000 --fov 20 [--cx 600 --cy 600 --roll 0] [--pose a=1,b=2] --out x.png [--size 1000]
import { Renderer, kamera } from './render.mjs';
const opt = (k, d) => { const i = process.argv.indexOf('--' + k); return i > 0 ? process.argv[i + 1] : d; };
const size = +opt('size', 1000), W0 = 1200;
const pose = {}; for (const s of (opt('pose', '') || '').split(',').filter(Boolean)) { const [k, v] = s.split('='); pose[k] = +v; }
const R = await new Renderer().open(size, size); await R.load(opt('glb'), false); if (Object.keys(pose).length) await R.pose(pose);
const cam = kamera({ azim: +opt('az', 30), elev: +opt('el', 30), dist: +opt('dist', 3000), fov: +opt('fov', 20), roll: +opt('roll', 0), shiftX: (+opt('cx', 600) - W0 / 2) / W0, shiftY: (+opt('cy', 600) - W0 / 2) / W0 });
await R.png(cam, opt('out', '/tmp/r1.png')); await R.close(); console.log(opt('out', '/tmp/r1.png'));
