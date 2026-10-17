// node diffmask.mjs glb foto cam.json out.png [--pose a=1] [--pos a=1] [--crop x0,y0,x1,y1] → červená = jen fotka, modrá = jen model, šedá = shoda (L=600 maska)
import fs from 'node:fs';
import { execFileSync } from 'node:child_process';
import { Renderer } from '../../kufriky_cloud/render/render.mjs';
import { maska, nastavPozu, parseKV, camObj } from './rend.mjs';
const [glb, foto, camf, out] = process.argv.slice(2, 6);
const opt = (k, d) => { const i = process.argv.indexOf('--' + k); return i > 0 ? process.argv[i + 1] : d; };
const { w, h, mask } = await maska(foto, 600, process.argv.includes('--nofill'));
const R = await new Renderer().open(w, h); await R.load(glb, true); await nastavPozu(R, parseKV(opt('pose', '')), parseKV(opt('pos', '')));
const m = await R.mask(camObj(JSON.parse(fs.readFileSync(camf)), w, h)); await R.close();
const buf = Buffer.alloc(w * h * 3);
for (let i = 0; i < w * h; i++) { const a = m[i], b = mask[i]; const c = a && b ? [190, 190, 190] : a ? [40, 80, 255] : b ? [255, 60, 60] : [255, 255, 255]; buf[3 * i] = c[0]; buf[3 * i + 1] = c[1]; buf[3 * i + 2] = c[2]; }
fs.writeFileSync(out + '.raw', buf);
execFileSync('python3', ['-c', `from PIL import Image;im=Image.frombytes('RGB',(${w},${h}),open('${out}.raw','rb').read());c='${opt('crop', '')}'
if c:
    x0,y0,x1,y1=[int(v)*${w}//1200 for v in c.split(',')];im=im.crop((x0,y0,x1,y1))
im=im.resize((im.width*2,im.height*2),Image.NEAREST);im.save('${out}')`]);
fs.unlinkSync(out + '.raw');
