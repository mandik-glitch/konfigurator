// Render modelu ze stejné kamery jako fotografie: node render_kamery.mjs modely/cistic.glb kamery.json foto_id vystup.png [sirka] [--maska maska.bin]
// kamery.json: {"cams":{"13":[cx,cy,cz,yaw,pitch,roll,fov]}} (z' nad zemí; model má počátek ve středu obálky → z = z' − 390); fotografie: 11,12,14 = 1500×1125, 13 = 2000×1500 (4:3)
import fs from 'node:fs';
import { Renderer } from '../../../kufriky_cloud/render/render.mjs';
import { kameraZ } from './kamera_z.mjs';
const [glb, camf, id, out, wArg] = process.argv.slice(2);
const J = JSON.parse(fs.readFileSync(camf)); const c = (J.cams || J)[id];
const W = +(wArg || 750), H = Math.round(W * 3 / 4);
const R = await new Renderer().open(W, H);
const mask = process.argv.includes('--maska');
await R.load(glb, mask);
if (mask) { const m = await R.mask(kameraZ(c)); fs.writeFileSync(out, Buffer.concat([Buffer.from(new Uint32Array([W, H]).buffer), m])); }
else await R.png(kameraZ(c), out);
await R.close();
