// Nádoby (10 ks, červené) a střední pruh vany – model 4932464082.
// Rozměry: řady (X) ~99 mm, sloupce (Y) ~100 mm, mezera 3,5 mm; středy řad podle horního pohledu c13 (viz poznámky).
import { Group, Part, tray, slab, rrFrame, bx, zc } from './p4082_zaklad.mjs';

export const N = {
  rowH: 99, gap: 3.5, rowC: [97, -5.5, -108],      // středy řad v X (přední, prostřední, zadní)
  c0: 25.5, c1: 226,                              // shluk nádob v Y: od vnitřního po vnější okraj (|y|)
  zFloor: 23.5, zTop: 106.5,                            // dno nádob a horní okraj (z')
};

// seznam nádob: [{x0,x1,y0,y1,velka}] pro obě poloviny
export function seznamNadob() {
  const out = [], w = (N.c1 - N.c0 - N.gap) / 2;
  for (const sv of [1, -1]) {
    const cols = [[N.c0, N.c0 + w], [N.c0 + w + N.gap, N.c1]];
    N.rowC.forEach((u, r) => {
      const x0 = u - N.rowH / 2, x1 = u + N.rowH / 2;
      if (r === 1) { const y0 = sv > 0 ? N.c0 : -N.c1, y1 = sv > 0 ? N.c1 : -N.c0; out.push({ x0, x1, y0, y1, velka: true, r }); }
      else for (const [a, b] of cols) { const y0 = sv > 0 ? a : -b, y1 = sv > 0 ? b : -a; out.push({ x0, x1, y0, y1, velka: false, r }); }
    });
  }
  return out;
}

export function nadoby() {
  const g = new Group('nadoby');
  for (const n of seznamNadob()) {
    g.add(tray('cervena', 'nadoba', { x0: n.x0, x1: n.x1, y0: n.y0, y1: n.y1, z0: N.zFloor, z1: N.zTop, rs: 6, seg: 3, wall: 1.8, floor: 2, re: 2, fs: 2 }));
    // horní lem (příruba)
    g.add(rrFrame('cervena', 'nadoba_lem', { x0: n.x0 - 0.8, x1: n.x1 + 0.8, y0: n.y0 - 0.8, y1: n.y1 + 0.8, z0: N.zTop - 2.4, z1: N.zTop, w: 4.5, rs: 6.8, seg: 3 }));
  }
  // střední pruh (černý přepážkový blok mezi shluky)
  g.add(slab('cerna_mat', 'stredni_pruh', { x0: -158, x1: 148, y0: -N.c0, y1: N.c0, z0: 23, z1: 105.5, rs: 3, seg: 2, reT: 1, reB: 0.5, fs: 1 }));
  return g;
}
