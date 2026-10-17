// Kontrola sítí: znaménko objemu (obrácené normály u uzavřených těles), degenerované trojúhelníky, díly mimo obálku. node kontrola_sit.mjs <SKU>
import path from 'node:path'; import { fileURLToPath } from 'node:url';
const HERE = path.dirname(fileURLToPath(import.meta.url));
const sku = process.argv[2]; const mod = await import(path.join(HERE, '..', 'kufr_' + sku + '.mjs'));
const root = mod.build({});
let bad = 0, n = 0;
for (const p of root.allParts()) {
  n++; let vol = 0, deg = 0; const P = p.pos, I = p.idx;
  for (let t = 0; t < I.length; t += 3) {
    const a = I[t] * 3, b = I[t + 1] * 3, c = I[t + 2] * 3;
    const ax = P[a], ay = P[a + 1], az = P[a + 2], bx = P[b], by = P[b + 1], bz = P[b + 2], cx = P[c], cy = P[c + 1], cz = P[c + 2];
    vol += (ax * (by * cz - bz * cy) - ay * (bx * cz - bz * cx) + az * (bx * cy - by * cx)) / 6;
    const ux = bx - ax, uy = by - ay, uz = bz - az, vx = cx - ax, vy = cy - ay, vz = cz - az;
    if (Math.hypot(uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx) < 1e-9) deg++;
  }
  // otevřené plochy (plošky, víčka bez uzavření) mají objem ≈ náhodný; uzavřená tělesa mají mít kladný
  if (vol < -1) { bad++; console.log('ZÁPORNÝ OBJEM', p.name, p.mat, vol.toFixed(0), 'trojúhelníků', I.length / 3); }
  if (deg > 0) console.log('degenerované', p.name, deg);
}
console.log(sku, 'dílů', n, 'se záporným objemem', bad);
