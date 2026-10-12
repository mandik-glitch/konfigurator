// Madlo MAKPAC: černý plochý třmen (U) s vroubkovanou gumovou vložkou. Výchozí poloha = sklopené dozadu do kapsy ve víku (leží vodorovně);
// skupina `madlo` má pivot na ose čepů (rovnoběžná s Y), extras.osa = [0,1,0]: pose madlo=90° = vztyčené (tak je madlo na všech fotografiích výrobce).
import { Group, Part, extXY, bx, cylZ, zc } from './makpac_zaklad.mjs';

export const MADLO = { xp: 8, L: 70, yo: 122, yi: 88, bw: 28, t: 16, zdolu: 20 };   // xp = x osy čepů; L = délka ramen; yo/yi = vnější/vnitřní polovina šířky; bw = šířka příčky; t = tloušťka

export function madlo(V) {
  const { xp, L, yo, yi, bw, t, zdolu } = MADLO;
  const z0 = V - zdolu + 0.5, z1 = z0 + t, zp = (z0 + z1) / 2;
  const g = new Group('madlo', { pivot: [xp, 0, zc(zp)], extras: { osa: [0, 1, 0], max_uhel: 100 } });
  const c = 7;                                                      // sražení vnějších rohů příčky
  const U = [[xp, -yo], [xp, -yi], [xp - bw - 14, -yi], [xp - bw, -yi + 6], [xp - bw, yi - 6], [xp - bw - 14, yi], [xp, yi], [xp, yo], [xp - L + c, yo], [xp - L, yo - c], [xp - L, -yo + c], [xp - L + c, -yo]];
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
