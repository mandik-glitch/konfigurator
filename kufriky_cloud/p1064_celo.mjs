// Čelo (+X) nízkého organizéru 4932471064: nízké držadlo (příčka s průchozí štěrbinou, bez kroužku), červené tlačítko, dvě západky
// (černé pouzdro, červený jazyk s žebry, ocelový třmen jako samostatný uzel). Čiré háčky nad západkami jsou v uzlu víka.
import { Group, Part, roundPoly, ccw, ext, extYZ, slab, bx, zc, tube, ZC } from './p1064_zaklad.mjs';
import { X } from './p1064_data.mjs';

export const C = {
  yL: 148,                  // střed západky (±)
    bar: { xp0: 346, y0: -88, y1: 100, zs0: 22, zs1: 30, zh: 38 },
};

function drzadlo(g) {
  const b = C.bar, F = 414;
  // spodní blok držadla (příčka s hlubokým profilem) a horní rameno nad průchozí štěrbinou (z' 24 … 31), koncové sloupky; čelo xp 414
  g.add(slab('cerna_mat', 'drzadlo_pricka', { x0: X(b.xp0), x1: X(F), y0: b.y0, y1: b.y1, z0: 0, z1: b.zs0, rs: 3, seg: 3, reT: 1.5, reB: 2, fs: 2 }));
  g.add(slab('cerna_mat', 'drzadlo_horni', { x0: X(b.xp0), x1: X(F - 6), y0: b.y0, y1: b.y1, z0: b.zs1, z1: b.zh, rs: 3, seg: 3, reT: 1.5, reB: 1, fs: 2 }));
  g.add(slab('cerna_mat', 'drzadlo_sloupek_L', { x0: X(b.xp0), x1: X(F - 6), y0: b.y0, y1: b.y0 + 14, z0: 0, z1: b.zh, rs: 3, seg: 3, reT: 1.5, reB: 1.5, fs: 2 }));
  g.add(slab('cerna_mat', 'drzadlo_sloupek_P', { x0: X(b.xp0), x1: X(F - 6), y0: b.y1 - 14, y1: b.y1, z0: 0, z1: b.zh, rs: 3, seg: 3, reT: 1.5, reB: 1.5, fs: 2 }));
  g.add(slab('cervena', 'drzadlo_tlacitko', { x0: X(F - 12), x1: X(F - 4), y0: 17, y1: 53, z0: 30, z1: 38, rs: 3, seg: 3, reT: 1.5, reB: 1, fs: 2 }));
}

function zamek(g, s) {
  const yc = s * C.yL;
  g.add(slab('cerna_mat', 'zamek_pouzdro', { x0: X(343), x1: X(368), y0: yc - 27, y1: yc + 27, z0: 31, z1: 41, rs: 2, seg: 2, reT: 1.5, reB: 1, fs: 2 }));
  g.add(slab('cervena', 'zamek_jazyk', { x0: X(358), x1: X(373), y0: yc - 23, y1: yc + 23, z0: 10, z1: 32, rs: 3, seg: 3, reT: 2, reB: 2.5, fs: 2 }));
  for (let r = 0; r < 4; r++) g.add(slab('cerna_mat', 'zamek_zebro', { x0: X(372.4), x1: X(373.8), y0: yc - 19, y1: yc + 19, z0: 12.5 + r * 4.6, z1: 13.7 + r * 4.6, rs: 0.5, seg: 1, reT: 0.3, reB: 0.3, fs: 1 }));
  // třmen: samostatný uzel (pivot na dolních čepech, osa −Y; kladný úhel odklápí třmen dopředu a dolů)
  const tg = new Group(s > 0 ? 'trmen_P' : 'trmen_L', { pivot: [X(373), yc, zc(14)], extras: { osa: [0, -1, 0], max_uhel: 165 } });
  const yL = yc - 28.5, yR = yc + 28.5;
  tg.add(tube('ocel', 'zamek_trmen', [
    [X(369), yL + 4, zc(14)], [X(377.5), yL, zc(14.5)], [X(378.5), yL, zc(22)], [X(378.5), yL, zc(52)], [X(378), yL + 1.5, zc(55)], [X(376.5), yL + 5, zc(57.2)],
    [X(376.5), yR - 5, zc(57.2)], [X(378), yR - 1.5, zc(55)], [X(378.5), yR, zc(52)], [X(378.5), yR, zc(22)], [X(377.5), yR, zc(14.5)], [X(369), yR - 4, zc(14)]], 1.5, 8));
  return tg;
}

export function celo() {
  const g = new Group('celo');
  drzadlo(g);
  g.addGroup(zamek(g, 1)); g.addGroup(zamek(g, -1));
  return g;
}
