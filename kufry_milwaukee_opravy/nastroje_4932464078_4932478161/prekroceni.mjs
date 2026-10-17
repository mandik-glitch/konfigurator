// Vypíše díly GLB, které vyčnívají z obálky (X Y Z intervaly): node prekroceni.mjs model.glb x y z   (obálka v mm)
import { readGLB } from '../../kufriky_cloud/jadro/glb.js';
const [f, X, Y, Z] = process.argv.slice(2); const lim = [X, Y, Z].map(v => +v / 2);
const g = readGLB(f);
for (const p of g.parts) {
  const b = [Infinity, Infinity, Infinity, -Infinity, -Infinity, -Infinity];
  for (let i = 0; i < p.pos.length; i += 3) for (let k = 0; k < 3; k++) { b[k] = Math.min(b[k], p.pos[i + k]); b[k + 3] = Math.max(b[k + 3], p.pos[i + k]); }
  const ex = []; for (let k = 0; k < 3; k++) { if (b[k] < -lim[k] - 0.5) ex.push('min' + 'XYZ'[k] + '=' + b[k].toFixed(1)); if (b[k + 3] > lim[k] + 0.5) ex.push('max' + 'XYZ'[k] + '=' + b[k + 3].toFixed(1)); }
  if (ex.length) console.log(p.name, ex.join(' '));
}
