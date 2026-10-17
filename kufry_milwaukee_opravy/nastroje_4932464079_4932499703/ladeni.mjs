// Ladění parametrů generátoru podle raw masky fotografie v zadané oblasti (okna kolem rohových tyčí): node ladeni.mjs <SKU> <pohled> "x0,y0,x1,y1;..." '{"param":[hodnoty],...}' [pevne JSON]
import { execFileSync } from 'node:child_process';
import path from 'node:path'; import { fileURLToPath } from 'node:url';
const HERE = path.dirname(fileURLToPath(import.meta.url));
const [sku, pohled, oblast, grid, pevne = '{}'] = process.argv.slice(2);
const G = JSON.parse(grid), keys = Object.keys(G), base = JSON.parse(pevne);
const combos = keys.reduce((acc, k) => acc.flatMap(a => G[k].map(v => ({ ...a, [k]: v }))), [{}]);
const res = [];
for (const c of combos) {
  const ovr = JSON.stringify({ ...base, ...c });
  const env = { ...process.env, KUF_OVR: ovr, KUF_OUT: '/tmp/kuf_ladeni.glb' };
  execFileSync('node', ['../vytvor_4932464079_4932499703.mjs', sku], { cwd: HERE, env, stdio: 'ignore' });
  const o = JSON.parse(execFileSync('node', ['srov.mjs', '--cfg', `cfg_${sku}.json`, '--pohled', pohled, '--glb', '/tmp/kuf_ladeni.glb', '--raw', '--bez-rendru', '--oblast', oblast, '--tag', 'lad'], { cwd: HERE, env, encoding: 'utf8' }).trim().split('\n').pop());
  res.push({ ...c, iou: o.iou }); console.log(JSON.stringify({ ...c, iou: o.iou }));
}
res.sort((a, b) => b.iou - a.iou); console.log('NEJLEPŠÍ', JSON.stringify(res.slice(0, 3)));
