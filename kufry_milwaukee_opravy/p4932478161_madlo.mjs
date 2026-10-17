// 4932478161 – výsuvné madlo na konci -Y: uzel `madlo` (dvě trubky Ø 16 + příčný úchop s gumovým návlekem) se posouvá po ose -Y (extras.posun_osa), zdvih ≈ 285 mm (c01, c02–c04).
// Ve výchozí poloze (zasunuté) je vidět jen příčný úchop při koncové stěně (c06, c05). Trubky vedou v koncové stěně; poloha trubek v ose X ±190 je odhad z c01.
import { Part, Group, box, tube, rrPoly, roundPoly, slab } from './p4932464078_zaklad.mjs';
import { zc, D } from './p4932478161_korpus.mjs';
export const M = { xr: 235, zc: 296, yEnd: -482.5, zdvih: 285 };

export function madlo() {
  const g = new Group('madlo', { pivot: [0, M.yEnd + 14, zc(M.zc)], extras: { posun_osa: [0, -1, 0], zdvih_max: M.zdvih, popis: 'výsuvné madlo (U z trubek) – posun od konce bedny po ose Y' } });
  const zz = zc(M.zc), yg = M.yEnd + 14;                     // střed úchopu (Ø 28)
  for (const s of [-1, 1]) g.add(tube('cerna', 'madlo_trubka_' + (s > 0 ? 'P' : 'L'), [[s * M.xr, yg, zz], [s * M.xr, yg + 360, zz]], 8, 12));
  // příčný úchop: ocelová trubka + gumový návlek s žebry
  g.add(tube('cerna', 'madlo_pricka', [[-M.xr - 8, yg, zz], [M.xr + 8, yg, zz]], 9, 12));
  g.add(tube('cerna_mat', 'madlo_navlek', [[-110, yg, zz], [110, yg, zz]], 14, 14));
  for (let i = 0; i < 14; i++) g.add(tube('cerna_mat', 'madlo_zebro' + i, [[-104 + i * 16, yg, zz], [-104 + i * 16, yg, zz]], 15.4, 14));
  // zaoblené koncovky trubek
  for (const s of [-1, 1]) g.add(slab('cerna', 'madlo_koncovka_' + (s > 0 ? 'P' : 'L'), { x0: s * M.xr - 14, x1: s * M.xr + 14, y0: yg - 14, y1: yg + 14, z0: zz - 14, z1: zz + 14, rs: 12, reT: 3, reB: 3, fs: 2 }));
  return g;
}
