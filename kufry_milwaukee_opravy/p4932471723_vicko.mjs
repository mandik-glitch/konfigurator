// 4932471723 – víko: plášť ≈ 45 mm (z' 288–322?) se zešikmeným ramenem, deska se 4 hlubokými kapsami (reliéf dovnitř), příčný pruh se štítkem, podélný žlábek pro sklopené držadlo, "uši" na předních rozích.
import { kit, planPoly, rrPoly, Group } from './p4932471723_zaklad.mjs';
import { k, HX, HY, Z_VICKO } from './p4932471723_telo.mjs';

export const Z_RIM = 322;      // horní hrana víka (kontrola: zt = 321,7 mm z fitu kamery)
export const Z_DNO_KAPS = 303; // dno kapes a žlábku
export function vicko() {
  const g = new Group('vicko');
  const nBr = [{ side: '+Y', a0: -52, a1: 52, d: 7 }];   // výřez v čele pláště pro třmen spony
  const mk = (dx, dy, r, nn) => planPoly(-HX + dx, HX - dx, -HY + dy, HY - dy, r, nn, 3);
  // plášť (skirt) z' 288–303 a zešikmené rameno 303–306 (zúžení o 4 mm)
  g.add(k.sloupec('cerna', 'vicko-plast', [
    { z: Z_VICKO, pts: mk(0, 0, 17, nBr) }, { z: 296, pts: mk(0, 0, 17, nBr) }, { z: 302, pts: mk(1.2, 1.2, 16, nBr) }, { z: Z_DNO_KAPS, pts: mk(4.5, 4.5, 13, nBr) }]));
  // horní deska s otvory (kapsy, žlábek + příčný pruh), z' 303–322
  const PX = [22, 106], RR = 7;
  const pocket = (x0, x1, y0, y1) => rrPoly(x0, x1, y0, y1, RR, 2);
  const rows = [[26, 146], [-150, -34]];
  const holes = [];
  for (const [y0, y1] of rows) { holes.push(pocket(PX[0], PX[1], y0, y1)); holes.push(pocket(-PX[1], -PX[0], y0, y1)); }
  // kříž: podélný žlábek (X ±17, Y −192…+190) + příčný pruh (X ±110, Y −26…+16)
  const w = 17, sx = 110, ya = -26, yb = 16, ye0 = -192, ye1 = 190;
  holes.push([[w, ye0], [w, ya], [sx, ya], [sx, yb], [w, yb], [w, ye1], [-w, ye1], [-w, yb], [-sx, yb], [-sx, ya], [-w, ya], [-w, ye0]].reverse());
  const outer = mk(4.5, 4.5, 13, []);
  g.add(k.slab('cerna', 'vicko-deska', outer, holes, Z_DNO_KAPS, Z_RIM));
  // štítek v příčném pruhu (červený)
  g.add(k.bx('cervena', 'vicko-stitek', -92, 92, ya + 4, yb - 4, Z_DNO_KAPS, Z_DNO_KAPS + 1.2));
  // drobné nálitky v kapsách (zubaté okraje)
  for (const [y0, y1] of rows) for (const sgn of [-1, 1]) {
    g.add(k.bx('cerna', 'kapsa-zub', sgn > 0 ? PX[0] : -PX[0] - 14, sgn > 0 ? PX[0] + 14 : -PX[0], (y0 + y1) / 2 - 5, (y0 + y1) / 2 + 5, Z_DNO_KAPS, Z_DNO_KAPS + 5));
  }
  // "uši" na předních rozích (hroty nad lemem) – viditelné na fotce nad levým a pravým předním rohem
  for (const s of [-1, 1]) {
    const x = s * (HX - 12);
    g.add(k.extXZ('cerna', 'vicko-usi', s > 0 ? [[x - 7, 316], [x + 7, 316], [x + 4, 329], [x - 3, 329]] : [[x - 7, 316], [x + 7, 316], [x + 3, 329], [x - 4, 329]], HY - 20, HY - 9));
  }
  return g;
}
