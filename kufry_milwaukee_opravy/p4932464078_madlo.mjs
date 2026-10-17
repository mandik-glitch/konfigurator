// 4932464078 – výsuvné madlo (dvoustupňové): uzel `madlo_1` (vnější sloupky s černými objímkami + červená příčka) a vnořený `madlo_2` (červený rám s gumovým úchopem + vnitřní trubky).
// Výchozí poloha = složené (obálka 530 mm). Posun po ose Z (extras.posun_osa), extras.zdvih_max = největší zdvih [mm] podle c05 (celkem ≈ 609 mm: madlo_1 130 + madlo_2 479).
// Čísla (změřeno na c05, zezadu, měřítko z kol): osa sloupků Y = ±165, vnitřní trubky ≈ 40 × 46 mm, objímky ≈ 60 mm široké, vnější šířka rámu ≈ 380 mm, vršek rozevřeného madla z' ≈ 1120.
import { Part, Group, box, tube, rrPoly, roundPoly, ccw, ext, extYZ, extXZ, slab } from './p4932464078_zaklad.mjs';
import { zc, H_LID } from './p4932464078_korpus.mjs';
const bx = (mat, name, x0, x1, y0, y1, z0, z1) => box(mat, name, x0, x1, y0, y1, zc(z0), zc(z1));
export const M = { xc: -207, yp: 165, zL: H_LID, zTop: 530, d1: 130, d2: 479, hObj: 78 };

export function madlo() {
  const g1 = new Group('madlo_1', { pivot: [M.xc, 0, zc(M.zL)], extras: { posun_osa: [0, 0, 1], zdvih_max: M.d1, popis: 'vnější stupeň madla (sloupky, objímky, červená příčka); posun nahoru po Z' } });
  const g2 = new Group('madlo_2', { pivot: [M.xc, 0, zc(M.zL + 60)], extras: { posun_osa: [0, 0, 1], zdvih_max: M.d2, popis: 'horní stupeň madla (rám s úchopem + vnitřní trubky); posun nahoru po Z (relativně k madlo_1)' } });
  const xa = M.xc - 20, xb = M.xc + 20;                    // hloubka sloupku 44
  for (const s of [-1, 1]) {
    const nm = s > 0 ? 'P' : 'L', y0 = s * M.yp - 24, y1 = s * M.yp + 24;
    const ya = Math.min(y0, y1), yb = Math.max(y0, y1);
    // vnější sloupek: od kanálu v zadní stěně nahoru k objímce
    g1.add(bx('cerna', 'madlo_sloupek_' + nm, xa, xb, ya, yb, 240, M.zL + M.hObj - 2));
    // černá objímka (kolár) na horním konci vnějšího sloupku
    g1.add(slab('cerna', 'madlo_objimka_' + nm, { x0: xa - 3, x1: xb + 3, y0: ya - 4, y1: yb + 4, z0: zc(M.zL + 2), z1: zc(M.zL + M.hObj), rs: 5, reT: 3, fs: 2 }));
    g1.add(tube('ocel', 'madlo_sroub_' + nm, [[xb + 3, s * M.yp, zc(M.zL + 78)], [xb + 4.5, s * M.yp, zc(M.zL + 78)]], 3.4, 8));
    // vnitřní trubka horního stupně (uvnitř sloupku; při vysunutí vyjede) – délka 490, ve složené poloze skrytá v sloupku/kanálu
    g2.add(bx('cerna', 'madlo_trubka_' + nm, M.xc - 17, M.xc + 17, s * M.yp - 21, s * M.yp + 21, 2, M.zTop - 30));
    // červený koncový kryt horního stupně (obepíná objímku ve složené poloze)
    g2.add(slab('cervena', 'madlo_koncovka_' + nm, { x0: xa - 7, x1: xb + 7, y0: ya - 5, y1: yb + 5, z0: zc(M.zL + 30), z1: zc(M.zTop), rs: 8, reT: 4, fs: 2 }));
  }
  // červená příčka (základna složeného madla): mezi objímkami, nízká, s tmavým výřezem uprostřed
  g1.add(bx('cervena', 'madlo_pricka', xa - 2, xb + 2, -M.yp + 24, M.yp - 24, M.zL + 2, M.zL + 48));
  g1.add(bx('cerna', 'madlo_pricka_vyrez', xa + 12, xb + 3, -42, 42, M.zL + 38, M.zL + 48.5));
  g1.add(bx('cerna', 'madlo_pricka_zakl', xa - 2, xb + 2, -M.yp + 24, M.yp - 24, M.zL, M.zL + 8));
  // horní příčka (červená) s gumovým úchopem
  g2.add(bx('cervena', 'madlo_horni_pricka', xa - 7, xb + 7, -M.yp - 29, M.yp + 29, M.zTop - 30, M.zTop));
  for (const sx of [-1, 1]) g2.add(slab('cerna_mat', 'madlo_uchop' + (sx > 0 ? '_P' : '_Z'), { x0: sx > 0 ? xb + 6 : xa - 9, x1: sx > 0 ? xb + 9 : xa - 6, y0: -102, y1: 102, z0: zc(M.zTop - 26), z1: zc(M.zTop - 6), rs: 8, reT: 1, fs: 2 }));
  g1.addGroup(g2);
  return g1;
}
