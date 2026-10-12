// Madlo MAKPAC: černý plochý třmen (U) s vroubkovanou gumovou vložkou. Výchozí poloha = sklopené dozadu do kapsy ve víku (leží vodorovně);
// skupina `madlo` má pivot na ose čepů (rovnoběžná s Y), extras.osa = [0,1,0]: pose madlo=90° = vztyčené (tak je madlo na všech fotografiích výrobce).
import { Group, Part, extXY, bx, cylZ, zc } from './makpac_zaklad.mjs';

export const MADLO = { xp: 48, L: 82, yo: 134, yi: 98, bw: 28, t: 16, zdolu: 22 };   // xp = x osy čepů; L = délka ramen; yo/yi = vnější/vnitřní polovina šířky; bw = šířka příčky; t = tloušťka

// zaoblení vybraných rohů polygonu (kvadratická Bézierova křivka mezi tečnými body); radii[i] = poloměr rohu i (0 = ostrý)
function zaoblit(poly, radii, n = 5) {
  const out = [], N = poly.length;
  poly.forEach((P, i) => {
    const r = radii[i] || 0; if (!r) { out.push(P); return; }
    const A = poly[(i + N - 1) % N], B = poly[(i + 1) % N];
    const ua = [A[0] - P[0], A[1] - P[1]], ub = [B[0] - P[0], B[1] - P[1]], la = Math.hypot(...ua), lb = Math.hypot(...ub);
    const t = Math.min(r, la * 0.45, lb * 0.45);
    const T1 = [P[0] + ua[0] / la * t, P[1] + ua[1] / la * t], T2 = [P[0] + ub[0] / lb * t, P[1] + ub[1] / lb * t];
    for (let k = 0; k <= n; k++) { const u = k / n, a = (1 - u) * (1 - u), b = 2 * u * (1 - u), c = u * u; out.push([a * T1[0] + b * P[0] + c * T2[0], a * T1[1] + b * P[1] + c * T2[1]]); }
  });
  return out;
}
export function madlo(V) {
  const { xp, L, yo, yi, bw, t, zdolu } = MADLO;
  const z0 = V - zdolu + 0.5, z1 = z0 + t, zp = (z0 + z1) / 2;
  const g = new Group('madlo', { pivot: [xp, 0, zc(zp)], extras: { osa: [0, 1, 0], max_uhel: 100 } });
  const U = zaoblit([[xp, -yo], [xp, -yi], [xp - bw, -yi], [xp - bw, yi], [xp, yi], [xp, yo], [xp - L, yo], [xp - L, -yo]], [0, 0, 6, 6, 0, 0, 12, 12]);
  g.add(extXY('cerna', 'madlo_trmen', U, z0, z1, { crease: 30 }));
  // gumová vložka na vrchní ploše příčky (po vztyčení je to přední strana s vroubkováním)
  const xa = xp - L + 4, xb = xp - L + bw - 4;
  g.add(bx('cerna_mat', 'madlo_vlozka', xa, xb, -70, 70, z1, z1 + 0.5));
  const d = new Part('madlo_vroubky', 'cerna');
  for (let r = 0; r < 4; r++) for (let k = 0; k < 11 - (r % 2); k++) {
    const x = xa + 3 + r * (xb - xa - 6) / 3, y = -65 + 13 * k + (r % 2) * 6.5;
    d.append(cylZ('cerna', 'v', 1.5, z1 + 0.3, z1 + 0.8, x, y, 8));
  }
  g.add(d);
  return g;
}
