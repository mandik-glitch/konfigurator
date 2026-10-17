// Pomocný render GLB z libovolné kamery do scratchpadu: node render_kamera.mjs glb out.png azim elev dist fov [tx ty tz] [--pose a=90] [--hide pred,pred] [--size 1000]
import { Renderer, kamera } from '../../kufriky_cloud/render/render.mjs';
const a = process.argv.slice(2); const pos = []; for (let i = 0; i < a.length; i++) { if (a[i].startsWith('--')) { i++; continue; } pos.push(a[i]); }
const opt = (k, d) => { const i = a.indexOf('--' + k); return i >= 0 ? a[i + 1] : d; };
const [glb, out, az, el, dist, fov, tx = 0, ty = 0, tz = 0] = pos;
const pose = {}; for (const kv of opt('pose', '').split(',').filter(Boolean)) { const [k, v] = kv.split('='); pose[k] = +v; }
const hide = opt('hide', '').split(',').filter(Boolean); const size = +opt('size', 1000);
const R = await new Renderer().open(size, size); await R.load(glb, false); if (Object.keys(pose).length) await R.pose(pose); if (hide.length) await R.hide(hide);
await R.png(kamera({ azim: +az, elev: +el, dist: +dist, fov: +fov, target: [+tx, +ty, +tz] }), out); await R.close(); console.log(out);
