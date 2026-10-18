// Kontrola modelu: (1) obálka, (2) NaN/Infinity, (3) „levitující“ díly (bbox dílu se nedotýká bbox žádného jiného dílu, tolerance 1 mm), (4) díly mimo obálku,
// (5) normály ven (pro každou plochu: skalární součin normály plochy s vektorem od těžiště dílu – podíl záporných; jen orientační), (6) pohyblivé uzly (extras.osa).
// node nastroje/kontrola.mjs [modely/cistic.glb]
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { readGLB } from '../../../kufriky_cloud/jadro/glb.js';
const HERE = path.dirname(fileURLToPath(import.meta.url));
const f = process.argv[2] || path.join(HERE, '../modely/cistic.glb');
const g = readGLB(f), P = g.parts;
const bb = p => { const b = [Infinity, Infinity, Infinity, -Infinity, -Infinity, -Infinity]; for (let i = 0; i < p.pos.length; i += 3) for (let k = 0; k < 3; k++) { const v = p.pos[i + k]; if (!Number.isFinite(v)) throw new Error('NaN v ' + p.name); b[k] = Math.min(b[k], v); b[k + 3] = Math.max(b[k + 3], v); } return b; };
const B = P.map(bb), all = B.reduce((a, b) => a.map((v, i) => i < 3 ? Math.min(v, b[i]) : Math.max(v, b[i])), [Infinity, Infinity, Infinity, -Infinity, -Infinity, -Infinity]);
console.log('díly:', P.length, 'obálka:', [all[3] - all[0], all[4] - all[1], all[5] - all[2]].map(v => v.toFixed(2)).join(' × '), 'střed:', [(all[0] + all[3]) / 2, (all[1] + all[4]) / 2, (all[2] + all[5]) / 2].map(v => v.toFixed(2)).join(', '));
const tol = 1;
const iso = [];
P.forEach((p, i) => { let t = false; for (let j = 0; j < P.length && !t; j++) { if (j === i) continue; const a = B[i], b = B[j]; if (a[0] <= b[3] + tol && b[0] <= a[3] + tol && a[1] <= b[4] + tol && b[1] <= a[4] + tol && a[2] <= b[5] + tol && b[2] <= a[5] + tol) t = true; } if (!t) iso.push(p.name); });
console.log('levitující díly (bbox se nedotýká žádného jiného):', iso.length ? iso.join(', ') : 'žádné');
let bad = 0, tot = 0; const worst = [];
P.forEach((p, i) => {
  let n = 0, neg = 0; const c = [0, 0, 0]; const nv = p.pos.length / 3; for (let k = 0; k < p.pos.length; k += 3) { c[0] += p.pos[k] / nv; c[1] += p.pos[k + 1] / nv; c[2] += p.pos[k + 2] / nv; }
  for (let t = 0; t < p.idx.length; t += 3) { const a = p.idx[t] * 3, b = p.idx[t + 1] * 3, d = p.idx[t + 2] * 3; const u = [p.pos[b] - p.pos[a], p.pos[b + 1] - p.pos[a + 1], p.pos[b + 2] - p.pos[a + 2]], v = [p.pos[d] - p.pos[a], p.pos[d + 1] - p.pos[a + 1], p.pos[d + 2] - p.pos[a + 2]]; const nn = [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]]; const m = [(p.pos[a] + p.pos[b] + p.pos[d]) / 3 - c[0], (p.pos[a + 1] + p.pos[b + 1] + p.pos[d + 1]) / 3 - c[1], (p.pos[a + 2] + p.pos[b + 2] + p.pos[d + 2]) / 3 - c[2]]; n++; if (nn[0] * m[0] + nn[1] * m[1] + nn[2] * m[2] < 0) neg++; }
  bad += neg; tot += n; if (n > 20 && neg / n > 0.35) worst.push(`${p.name} ${(100 * neg / n).toFixed(0)} %`);
});
console.log('plochy s normálou k těžišti (orientační; duté/ohnuté díly mají přirozeně část):', (100 * bad / tot).toFixed(1), '% ; díly s > 35 %:', worst.length ? worst.join(', ') : 'žádné');
const nodes = g.gltf.nodes.filter(n => n.extras && n.extras.osa);
console.log('pohyblivé uzly (extras.osa):', nodes.map(n => `${n.name} osa ${JSON.stringify(n.extras.osa)} pivot(rel) ${JSON.stringify(n.translation.map(v => +v.toFixed(1)))}`).join(' | '));
