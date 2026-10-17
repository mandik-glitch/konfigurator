// Volné pohledy na model (kontrola sestavy zezadu, zespodu, shora, s vysunutými zásuvkami, se sklopeným třmenem).
// node pohledy.mjs --sku 4932493189 --out <složka> [--sada zakladni|otevrene]
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { Renderer, kamera } from '../../kufriky_cloud/render/render.mjs';
const HERE = path.dirname(fileURLToPath(import.meta.url));
const opt = (k, d) => { const i = process.argv.indexOf('--' + k); return i > 0 ? process.argv[i + 1] : d; };
const sku = opt('sku'), out = opt('out'), sada = opt('sada', 'zakladni');
const glb = opt('glb', path.join(HERE, '../modely', sku + '.glb'));
fs.mkdirSync(out, { recursive: true });
const R = await new Renderer().open(900, 900); await R.load(glb);
async function pose2(p) {
  await R.page.evaluate(p => {
    root.traverse(o => { if (o.userData && o.userData.osa) { if (!o.userData._p0) o.userData._p0 = o.position.clone(); o.position.copy(o.userData._p0); o.quaternion.identity(); } });
    root.traverse(o => { const u = o.userData; if (!u || !u.osa) return; const ax = new THREE.Vector3(...u.osa).normalize();
      if (u.typ === 'posuv') { let v = p[o.name]; if (v === undefined && u.vazba && p[u.vazba] !== undefined) v = p[u.vazba] * (u.podil ?? 1); if (v !== undefined) o.position.addScaledVector(ax, v); }
      else if (u.typ === 'rotace') { const a = p[o.name]; if (a !== undefined) o.quaternion.setFromAxisAngle(ax, a * Math.PI / 180); } });
  }, p);
}
const SADY = {
  zakladni: [['iso_zavreny', { azim: 35, elev: 25, dist: 2300, fov: 26 }, {}], ['zezadu', { azim: 215, elev: 22, dist: 2300, fov: 26 }, {}], ['zespodu', { azim: 40, elev: -35, dist: 2300, fov: 26 }, {}], ['shora', { azim: 90, elev: 80, dist: 2300, fov: 26 }, {}], ['bok', { azim: 90, elev: 3, dist: 2300, fov: 26 }, {}]],
  otevrene: [['iso_plne', { azim: 35, elev: 25, dist: 2500, fov: 26 }, 'plne'], ['iso_cast', { azim: 35, elev: 25, dist: 2500, fov: 26 }, 'cast'], ['bok_plne', { azim: 90, elev: 3, dist: 2600, fov: 26 }, 'plne'], ['shora_plne', { azim: 60, elev: 70, dist: 2600, fov: 26 }, 'plne'], ['trmen_sklopen', { azim: 30, elev: 15, dist: 2300, fov: 26 }, 'trmen']],
};
const n = JSON.parse(await R.page.evaluate(() => { const r = []; root.traverse(o => { if (o.name && o.name.startsWith('zasuvka-') && !o.name.includes('_')) r.push(o.name); }); return JSON.stringify(r); }));
for (const [nm, k, p] of SADY[sada]) {
  const pose = {};
  if (p === 'plne') for (const z of n) pose[z] = 372;
  if (p === 'cast') for (const z of n) pose[z] = 240;
  if (p === 'trmen') pose['trmen'] = -90;
  await pose2(pose); await R.png(kamera({ ...k }), path.join(out, `${sku}_${nm}.png`));
}
await R.close();
