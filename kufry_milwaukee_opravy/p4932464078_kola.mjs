// Kolo pojízdných PACKOUT boxů: pneumatika s běhounem a rameny na bocích, zapuštěný disk s pěti paprsky, náboj s maticí. Osa kola = Y (volitelně X, viz osaX).
// Díly se tvoří v souřadnicích modelu; kolo = samostatný uzel s pivotem ve středu a extras.osa (volné otáčení).
import { Part, Group, box, tube, lathe, latheClosed, cylinder, prism, rrPoly, roundPoly } from './p4932464078_zaklad.mjs';

// cx, cz = střed kola (cz už v souřadnicích modelu); R = vnější poloměr (s bloky běhounu); yIn..yOut = rozsah šířky (yOut = vnější strana)
export function kolo(name, { cx, cz, R: Rv = 112.5, yIn, yOut, nBloku = 26, nSpic = 5, osaX = null }) {
  const R = Rv - 3.2;                                       // poloměr pláště bez bloků běhounu (vnější poloměr s bloky = Rv)
  const y0 = Math.min(yIn, yOut), y1 = Math.max(yIn, yOut), w = y1 - y0, yc = (y0 + y1) / 2, ph = w / 2;
  const sgn = yOut > yIn ? 1 : -1;                         // směr ven
  const g = new Group(name, { pivot: [cx, yc, cz], extras: { osa: [0, 1, 0], popis: 'kolo, volné otáčení kolem osy Y' } });
  const at = p => { p.rot('x', 90); p.move(cx, yc, cz); return p; };   // osa lathe Z -> Y
  // pneumatika (lathe kolem Z, výška = šířka): boky sahají dovnitř jen do 0,80 R, aby byl vidět disk
  const sh = [[R * 0.80, -ph * 0.93], [R * 0.86, -ph * 0.99], [R * 0.935, -ph * 0.96], [R * 0.985, -ph * 0.70], [R, -ph * 0.40], [R, ph * 0.40], [R * 0.985, ph * 0.70], [R * 0.935, ph * 0.96], [R * 0.86, ph * 0.99], [R * 0.80, ph * 0.93]];
  g.add(at(latheClosed('cerna_mat', name + '_pneu', sh.map(([r, z]) => [r, z]), 60, [0, 0, 0])));
  // bloky běhounu (obvod) + ramena na bocích
  for (let i = 0; i < nBloku; i++) {
    const a = 360 * i / nBloku + (i % 2 ? 180 / nBloku : 0), hb = (2 * Math.PI * R / nBloku) * 0.30;
    const b = box('cerna_mat', name + '_blok' + i, -hb, hb, -ph * 0.52, ph * 0.52, R - 1.2, R + 3.2);
    b.rot('y', a); b.move(cx, yc, cz); g.add(b);
    for (const sd of [1, -1]) {
      const b2 = box('cerna_mat', name + '_rameno' + (sd > 0 ? '' : '_m') + i, -hb * 0.75, hb * 0.75, sd > 0 ? ph * 0.80 : -ph * 1.0, sd > 0 ? ph * 1.0 : -ph * 0.80, R * 0.84, R * 0.98);
      b2.rot('y', a + 180 / nBloku); b2.move(cx, yc, cz); g.add(b2);
    }
  }
  // disk: zadní deska + věnec + paprsky + náboj (vše zapuštěné ≈ 16 mm od vnější plochy pneumatiky)
  const yd = yc + sgn * (ph - 18), yb = yc + sgn * (ph - 30);
  const ring = latheClosed('seda', name + '_vence', [[R * 0.70, -5], [R * 0.80, -5], [R * 0.80, 5], [R * 0.70, 5]], 48, [0, 0, 0]); ring.rot('x', 90); ring.move(cx, yd, cz); g.add(ring);
  const deska = lathe('cerna_mat', name + '_deska', [[0.1, -3], [R * 0.80, -3], [R * 0.80, 3], [0.1, 3]], 48, [0, 0, 0]); deska.rot('x', 90); deska.move(cx, yb, cz); g.add(deska);
  const nab = lathe('seda', name + '_nabor', [[0.1, -5], [20, -5], [24, 3], [18, 10], [0.1, 10]], 24, [0, 0, 0]);
  nab.rot('x', -90 * sgn); nab.move(cx, yd + sgn * 4, cz); g.add(nab);
  for (let i = 0; i < nSpic; i++) {
    const a = 360 * i / nSpic + 18;
    const sp = prism('seda', name + '_spice' + i, [[-9, 16], [9, 16], [15, R * 0.74], [-15, R * 0.74]], -5, 5);   // lichoběžník v rovině (x,z') -> osa Y
    sp.mapV((u, v, ww) => [u, ww, v]); sp.flip();
    sp.rot('y', a); sp.move(cx, yd, cz); g.add(sp);
  }
  // matice / čep osy
  g.add(tube('ocel', name + '_osa', [[cx, yd + sgn * 6, cz], [cx, yd + sgn * (ph - (yd - yc) * sgn), cz]], 6.5, 10));
  if (osaX !== null) {                                       // kolo s osou X: sestaví se s osou Y u počátku a pootočí; osaX = Y-ová poloha středu kola v modelu (cx se bere jako 0)
    for (const p of g.allParts()) { p.rot('z', -90); p.move(0, osaX, 0); }
    g.pivot = [yc, osaX, cz]; g.extras = { osa: [1, 0, 0], popis: 'kolo, volné otáčení kolem osy X' };
  }
  return g;
}
