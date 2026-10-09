// Nádoby (4 malé + 1 velká se děliči, červené) – model 4932471065. Stojí na podlaze vany (vlastní uzavřené dno), horní okraj s lemem
// vyčnívá nad horní hranu černé vany (fotografie otevřeného organizéru c02/c05/c11/c12).
// Rozměry: horní pohled c06 (±1 mm; paralaxa víka ~1 %), řady Y: 77,25 / -24,5 / -126,25; malé 100,8 × 100,8, velká 202,4 × 100,8.
import { Group, Part, trayT, rrFrame, bx, zc } from './p1065_zaklad.mjs';

export const N = {
  rowY: [77.25, -24.5, -126.25], s: 100.8, big: 202.4, cx: 50.9,
  zFloor: 7.8, zTop: 51.4,                 // dno nádob (0,2 mm pod podlahou vany – pevné spojení), horní okraj (pod dnem kapsy víka 51,8)
  taper: 2.6, wall: 1.8, floor: 2, chamf: 7.5,
};

export function seznamNadob() {
  const out = [], s = N.s, h = s / 2;
  for (const sx of [-1, 1]) out.push({ x0: sx * N.cx - h, x1: sx * N.cx + h, y0: N.rowY[0] - h, y1: N.rowY[0] + h, velka: false, jm: 'F' + (sx < 0 ? 'L' : 'P') });
  out.push({ x0: -N.big / 2, x1: N.big / 2, y0: N.rowY[1] - h, y1: N.rowY[1] + h, velka: true, jm: 'velka' });
  for (const sx of [-1, 1]) out.push({ x0: sx * N.cx - h, x1: sx * N.cx + h, y0: N.rowY[2] - h, y1: N.rowY[2] + h, velka: false, jm: 'B' + (sx < 0 ? 'L' : 'P') });
  return out;
}

export function nadoby() {
  const g = new Group('nadoby');
  for (const n of seznamNadob()) {
    const nm = 'nadoba_' + n.jm;
    g.add(trayT('cervena', nm, { x0: n.x0, x1: n.x1, y0: n.y0, y1: n.y1, z0: N.zFloor, z1: N.zTop, rs: N.chamf, seg: 1, wall: N.wall, floor: N.floor, re: 2, fs: 2, taper: N.taper }));
    g.add(rrFrame('cervena', nm + '_lem', { x0: n.x0, x1: n.x1, y0: n.y0, y1: n.y1, z0: N.zTop - 2.6, z1: N.zTop, w: 3.4, rs: N.chamf, seg: 1 }));
    const ix0 = n.x0 + 4.2, ix1 = n.x1 - 4.2, iy0 = n.y0 + 4.2, iy1 = n.y1 - 4.2;      // vnitřní okraj stěn u dna (úkos stěn zahrnut)
    if (!n.velka) {
      // dělicí stěna rovnoběžná s osou X (c12: ~56 % hloubky od zadní strany), s okrajovou lištou a ouškem na koncích
      const yd = (n.y0 + n.y1) / 2 - 2.5, hz = N.zFloor + N.floor + (N.zTop - N.zFloor - N.floor) * 0.56;
      g.add(bx('cervena', nm + '_delic', ix0 - 0.6, ix1 + 0.6, yd - 0.85, yd + 0.85, N.zFloor + 1.6, hz));
      g.add(bx('cervena', nm + '_delic_lista', ix0 - 0.6, ix1 + 0.6, yd - 1.7, yd + 1.7, hz - 0.6, hz));
      for (const e of [[ix0 - 0.6, ix0 + 3.2], [ix1 - 3.2, ix1 + 0.6]]) g.add(bx('cervena', nm + '_delic_ucho', e[0], e[1], yd - 2.3, yd + 2.3, N.zFloor + 1.6, hz + 2));
      // zámkový žebro na zadní (−Y) stěně (c12)
      g.add(bx('cervena', nm + '_zebro', (n.x0 + n.x1) / 2 - 3.2, (n.x0 + n.x1) / 2 + 3.2, iy0 - 0.8, iy0 + 1.4, N.zTop - 15, N.zTop - 1.2));
    } else {
      const hz = N.zFloor + N.floor + (N.zTop - N.zFloor - N.floor) * 0.88;
      for (const xd of [-33.7, 33.7]) {
        g.add(bx('cervena', nm + '_delic', xd - 1.3, xd + 1.3, iy0 - 0.6, iy1 + 0.6, N.zFloor + 1.6, hz));
        for (const e of [[iy0 - 0.6, iy0 + 3.4], [iy1 - 3.4, iy1 + 0.6]]) g.add(bx('cervena', nm + '_delic_ucho', xd - 2.4, xd + 2.4, e[0], e[1], N.zFloor + 1.6, hz + 1.5));
      }
    }
  }
  return g;
}
