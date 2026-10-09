// Nádoby (10 ks, červené) a střední pruh vany – model 4932464082.
// Rozměry: řady (X) ~99 mm, sloupce (Y) ~100 mm, mezera 3,5 mm; středy řad podle horního pohledu c13 (viz poznámky).
import { Group, Part, tray, trayT, slab, rrFrame, bx, zc } from './p4082_zaklad.mjs';

export const N = {
  // horní okraj nádob (červená příruba viditelná shora, rektifikace c13): x −162,1 … 151; |y| 27 … 235; mezera řad 2,5 mm, sloupců 5 mm
  rowH: 102.7, rowC: [99.65, -5.55, -110.75],       // středy řad v X (přední, prostřední, zadní)
  gap: 5, c0: 27, c1: 235,                          // shluk nádob v Y: od vnitřního po vnější okraj (|y|), mezera sloupců
  zFloor: 22.7, zTop: 104, taper: 3.2,            // dno nádob, horní okraj (z'), zúžení ode dna k okraji (úkos stěn)
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
    g.add(trayT('cervena', 'nadoba', { x0: n.x0, x1: n.x1, y0: n.y0, y1: n.y1, z0: N.zFloor, z1: N.zTop, rs: 7, seg: 1, wall: 1.8, floor: 2, re: 2, fs: 2, taper: N.taper }));
    // horní lem (příruba) – červený pás široký 5 mm podél okraje
    g.add(rrFrame('cervena', 'nadoba_lem', { x0: n.x0, x1: n.x1, y0: n.y0, y1: n.y1, z0: N.zTop - 2.6, z1: N.zTop, w: 5.2, rs: 7, seg: 1 }));
  }
  // střední pruh (černý přepážkový blok mezi shluky)
  g.add(slab('cerna_mat', 'stredni_pruh', { x0: -160, x1: 150, y0: -N.c0, y1: N.c0, z0: 22.7, z1: 100, rs: 3, seg: 2, reT: 1, reB: 0.5, fs: 1 }));
  return g;
}
