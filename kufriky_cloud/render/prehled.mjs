// Přehled jednoho GLB z 6 pohledů (čelo přímo, šikmo čelo, vzadu, shora, otevřené víko, spodek) do jednoho obrázku.
// node render/prehled.mjs modely/<SKU>.glb vystup.png [celoAzim=0] [vicko=osa-nazev]
import { Renderer, kamera } from './render.mjs';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
const [glb, out, a0s, victy] = process.argv.slice(2); const a0 = +(a0s ?? 0);
const g = JSON.parse(Buffer.from(fs.readFileSync(glb).subarray(20, 20 + fs.readFileSync(glb).readUInt32LE(12))).toString());
const lidNode = g.nodes.find(n => /vicko|lid/i.test(n.name || '') && n.extras && n.extras.osa);
const R = await new Renderer().open(700, 520); await R.load(glb);
const dist = 2300, fov = 14, T = [0, 0, 0];
const views = [
  ['celo', kamera({ azim: a0, elev: 4, dist, fov })], ['sikmo celo', kamera({ azim: a0 + 32, elev: 24, dist, fov })], ['vzadu', kamera({ azim: a0 + 150, elev: 24, dist, fov })],
  ['shora', kamera({ azim: a0, elev: 88, dist, fov })], ['otevrene', kamera({ azim: a0 + 25, elev: 38, dist: 2700, fov }), lidNode ? { [lidNode.name]: 105 } : {}], ['spodek', kamera({ azim: a0 + 20, elev: -55, dist, fov })],
];
const files = [];
for (const [n, c, pose] of views) { await R.pose(pose || {}); const f = `/tmp/prehled_${n.replace(' ', '_')}.png`; await R.png(c, f); files.push([n, f]); }
await R.close();
execFileSync('python3', ['-c', `
from PIL import Image, ImageDraw
fs=${JSON.stringify(files)}
W,H=700,520
im=Image.new('RGB',(W*3,H*2),'white'); d=ImageDraw.Draw(im)
for i,(n,f) in enumerate(fs):
    t=Image.open(f).convert('RGB'); im.paste(t,((i%3)*W,(i//3)*H)); d.text(((i%3)*W+8,(i//3)*H+6),n,fill='black')
im.save('${out}'); print('${out}',im.size)`], { stdio: 'inherit' });
