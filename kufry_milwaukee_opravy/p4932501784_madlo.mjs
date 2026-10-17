// Zdvižitelné U-madlo revize 4932501784: pohyblivý uzel `madlo_nosne` s čepem na zadním horním okraji (osa Y).
// Geometrie je postavena ve ZDVIŽENÉ poloze (podle fotek c01/c02: ≈ 155 mm nad víkem, ramena vně u zadních rohových patek, vnější šířka ≈ 548 mm)
// a pak otočena o 180° do výchozí (sklopené) polohy – kam se madlo skládá, z fotek NEVÍME; sklopení dozadu dolů je předpoklad uvnitř obálky.
import { Group, Part, extYZ, cylY, roundPoly } from './p4932478162_zaklad.mjs';

export const MADLO = { px: +(process.env.MADLO_PX ?? -183), pz: 200, t: 24, y0: 236, y1: 258, zc: 351, rAlu: 12, rGrip: 14, yAlu: 187, yGrip: 72 };

export function madlo() {
  const M = MADLO, h = M.t / 2;
  const g = new Group('madlo_nosne', { pivot: [M.px, 0, M.pz], extras: { osa: [0, 1, 0], max_uhel: 180, popis: 'zdvižitelné U-madlo; úhel 0 = sklopené dolů za zadní stěnou (výchozí, uvnitř obálky), 180 = zdvižené svisle' } });
  const raised = [];
  for (const s of [1, -1]) {
    const id = s > 0 ? 'P' : 'L', S = ([y, z]) => [s * y, z];
    // rameno + koncovka (jeden profil v rovině YZ, tlustý M.t): svislá noha, oblé zalomení, černá koncovka pro hliníkovou trubku
    const prof = [[M.y0, M.pz - 2], [M.y1, M.pz - 2], [M.y1, M.zc + 18], [M.y1 - 36, M.zc + 17], [M.yAlu, M.zc + 17], [M.yAlu, M.zc - 17], [M.y0 + 0.0, M.zc - 17]].map(S);
    const pr = roundPoly(s > 0 ? prof : prof.slice().reverse(), s > 0 ? [0.5, 0.5, 30, 0.5, 0.5, 0.5, 8] : [8, 0.5, 0.5, 0.5, 30, 0.5, 0.5], 4);
    raised.push(extYZ('cerna', 'madlo_rameno_' + id, pr, M.px - h, M.px + h, 30));
    raised.push(cylY('hlinik', 'madlo_tyc_' + id, M.rAlu, s > 0 ? M.yGrip - 2 : -(M.yAlu + 1), s > 0 ? M.yAlu + 1 : -(M.yGrip - 2), M.px, M.zc, 22));
    raised.push(cylY('ocel', 'madlo_cep_' + id, 5.5, s > 0 ? M.y1 - 1 : -(M.y1 + 3), s > 0 ? M.y1 + 3 : -(M.y1 - 1), M.px, M.pz + 6, 14));
  }
  raised.push(cylY('guma', 'madlo_uchop', M.rGrip - 1.2, -M.yGrip, M.yGrip, M.px, M.zc, 24));
  for (let k = 0; k < 17; k++) { const y = -M.yGrip + 2 + k * 8.4; raised.push(cylY('cerna_mat', 'madlo_zebro', M.rGrip, y, y + 3.6, M.px, M.zc, 24)); }
  for (const p of raised) { p.rot('y', 180, [M.px, 0, M.pz]); g.add(p); }
  return g;
}
