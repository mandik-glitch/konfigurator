// 4932464078 – výsuvné madlo (dvoustupňové): uzel `madlo_1` (vnější sloupky + červená příčka + černé objímky) a vnořený `madlo_2` (červený rám s gumovým úchopem + vnitřní trubky).
// Výchozí poloha = složené (obálka 530 mm). Posun po ose Z (extras.posun_osa), extras.zdvih_max = největší zdvih [mm] podle fotek c02 / c05.
import { Part, Group, box, tube, rrPoly, roundPoly, ccw, ext, extYZ, extXZ, slab } from './p4932464078_zaklad.mjs';
import { zc } from './p4932464078_korpus.mjs';
const bx = (mat, name, x0, x1, y0, y1, z0, z1) => box(mat, name, x0, x1, y0, y1, zc(z0), zc(z1));
export const M = { xc: -196, yp: 163, zL: 395, zTop: 530, d1: 120, d2: 470 };   // osa sloupků x, rozteč sloupků ±y, vršek víka, vršek složeného madla, zdvihy

export function madlo() {
  const g1 = new Group('madlo_1', { pivot: [M.xc, 0, zc(M.zL)], extras: { posun_osa: [0, 0, 1], zdvih_max: M.d1, popis: 'vnější stupeň madla (sloupky + příčka); posun nahoru po Z' } });
  const g2 = new Group('madlo_2', { pivot: [M.xc, 0, zc(M.zL + 60)], extras: { posun_osa: [0, 0, 1], zdvih_max: M.d2, popis: 'horní stupeň madla (rám s úchopem + vnitřní trubky); posun nahoru po Z (relativně k madlo_1)' } });
  const xa = M.xc - 20, xb = M.xc + 20;                    // sloupek 40 mm v X
  for (const s of [-1, 1]) {
    const nm = s > 0 ? 'P' : 'L', y0 = s * M.yp - 22, y1 = s * M.yp + 22;
    // vnější sloupek: od hloubky ve víku nahoru k objímce
    g1.add(bx('cerna', 'madlo_sloupek_' + nm, xa, xb, Math.min(y0, y1), Math.max(y0, y1), 250, M.zL + 96));
    // černá objímka (kolár) na horním konci vnějšího sloupku
    g1.add(slab('cerna', 'madlo_objimka_' + nm, { x0: xa - 4, x1: xb + 4, y0: Math.min(y0, y1) - 4, y1: Math.max(y0, y1) + 4, z0: zc(M.zL + 2), z1: zc(M.zL + 98), rs: 5, reT: 3, fs: 2 }));
    g1.add(tube('ocel', 'madlo_sroub_' + nm, [[xb + 4, s * M.yp, zc(M.zL + 80)], [xb + 6.5, s * M.yp, zc(M.zL + 80)]], 3.2, 8));
    // vnitřní trubka horního stupně (uvnitř sloupku; při vysunutí vyjede)
    g2.add(bx('cerna', 'madlo_trubka_' + nm, M.xc - 14, M.xc + 14, s * M.yp - 15, s * M.yp + 15, M.zL + 20, M.zTop - 30));
    // červený koncový kryt horního stupně (obepíná objímku ve složené poloze)
    g2.add(slab('cervena', 'madlo_koncovka_' + nm, { x0: xa - 8, x1: xb + 8, y0: Math.min(y0, y1) - 8, y1: Math.max(y0, y1) + 8, z0: zc(M.zL + 26), z1: zc(M.zTop), rs: 8, reT: 5, fs: 2 }));
  }
  // červená příčka (základna složeného madla) s tmavým výřezem uprostřed – pevná na objímkách
  g1.add(bx('cervena', 'madlo_pricka', xa - 2, xb + 2, -M.yp + 20, M.yp - 20, M.zL + 2, M.zL + 54));
  g1.add(bx('cerna', 'madlo_pricka_vyrez', xa + 10, xb + 3, -42, 42, M.zL + 43, M.zL + 54.5));
  g1.add(bx('cerna', 'madlo_pricka_zakl', xa - 2, xb + 2, -M.yp + 20, M.yp - 20, M.zL, M.zL + 4));
  // horní příčka (červená) s gumovým úchopem
  g2.add(bx('cervena', 'madlo_horni_pricka', xa - 8, xb + 8, -M.yp - 24, M.yp + 24, M.zTop - 30, M.zTop));
  g2.add(slab('cerna_mat', 'madlo_uchop', { x0: xa + 2, x1: xb - 2, y0: -112, y1: 112, z0: zc(M.zTop - 62), z1: zc(M.zTop - 28), rs: 10, reB: 6, fs: 2 }));
  g1.addGroup(g2);
  return g1;
}
