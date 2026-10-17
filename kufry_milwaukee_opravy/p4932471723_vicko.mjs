// 4932471723 – víko: plášť ≈ 44 mm (z' 270–314) se zešikmeným ramenem, vyvýšená deska se 4 hlubokými kapsami (reliéf dovnitř), příčný pruh se štítkem, podélný žlábek pro sklopené držadlo, "uši" na předních rozích.
import { planPoly, rrPoly, Group } from './p4932471723_zaklad.mjs';
import { k, HX, HY, Z_VICKO } from './p4932471723_telo.mjs';

export const Z_DNO = 306;      // dno kapes / horní plocha pláště uvnitř
export const Z_LEM = 310;      // horní hrana pláště (lem) – kontrola kamerou: rohy lemu ≈ 322 v kalibraci, přepočteno na katalogovou výšku
export const Z_DESKA = 330;    // horní plocha vyvýšené desky = katalogová výška
export const DESKA = { x: 100, y0: -190, y1: 176 };
export function vicko() {
  const g = new Group('vicko');
  const nBr = [{ side: '+Y', a0: -52, a1: 52, d: 7 }];   // výřez v čele pláště pro třmen spony
  const mk = (dx, dy, r, nn) => planPoly(-HX + dx, HX - dx, -HY + dy, HY - dy, r, nn, 3);
  // plášť (skirt): z' 270–306, k vrchu zešikmené rameno (zúžení o 4 mm)
  g.add(k.sloupec('cerna', 'vicko-plast', [
    { z: Z_VICKO, pts: mk(0, 0, 17, nBr) }, { z: 296, pts: mk(0, 0, 17, nBr) }, { z: 302, pts: mk(1.2, 1.2, 16, nBr) }, { z: Z_DNO, pts: mk(4.5, 4.5, 13, nBr) }]));
  const plat = rrPoly(-DESKA.x, DESKA.x, DESKA.y0, DESKA.y1, 10, 3);
  // lem (římsa) kolem desky: z' 306–314
  g.add(k.slab('cerna', 'vicko-lem', mk(4.5, 4.5, 13, []), [plat], Z_DNO, Z_LEM));
  // vyvýšená deska s otvory (kapsy, žlábek + příčný pruh): z' 306–330
  const RR = 7, pocket = (x0, x1, y0, y1) => rrPoly(x0, x1, y0, y1, RR, 2);
  const rows = [[12, 128], [-172, -66]];
  const holes = [];
  for (const [y0, y1] of rows) { holes.push(pocket(16, 92, y0, y1)); holes.push(pocket(-92, -16, y0, y1)); }
  const w = 14, sx = 92, ya = -56, yb = -6, ye0 = -182, ye1 = 168;
  holes.push([[w, ye0], [w, ya], [sx, ya], [sx, yb], [w, yb], [w, ye1], [-w, ye1], [-w, yb], [-sx, yb], [-sx, ya], [-w, ya], [-w, ye0]].reverse());
  g.add(k.slab('cerna', 'vicko-deska', plat, holes, Z_DNO, Z_DESKA));
  // štítek v příčném pruhu (červený)
  g.add(k.bx('cervena', 'vicko-stitek', -84, 84, ya + 5, yb - 5, Z_DNO, Z_DNO + 1.2));
  // drobné nálitky v kapsách (zubaté okraje)
  for (const [y0, y1] of rows) for (const sgn of [-1, 1]) {
    g.add(k.bx('cerna', 'kapsa-zub', sgn > 0 ? 16 : -16 - 12, sgn > 0 ? 16 + 12 : -16, (y0 + y1) / 2 - 5, (y0 + y1) / 2 + 5, Z_DNO, Z_DNO + 6));
  }
  // "uši" na předních rozích (hroty nad lemem)
  for (const s of [-1, 1]) {
    const x = s * (HX - 12);
    g.add(k.extXZ('cerna', 'vicko-usi', s > 0 ? [[x - 7, 308], [x + 7, 308], [x + 4, 329], [x - 3, 329]] : [[x - 7, 308], [x + 7, 308], [x + 3, 329], [x - 4, 329]], HY - 20, HY - 9));
  }
  return g;
}
