// Kolo pojízdných PACKOUT boxů: pneumatika s běhounem, disk s paprsky, matice na ose. Osa kola = Y.
// Díly se tvoří v souřadnicích modelu; kolo = samostatný uzel s pivotem ve středu a extras.osa = [0,1,0] (volné otáčení).
import { Part, Group, box, tube, lathe, cylinder, roundedBox, prism, rrPoly, roundPoly } from './p4932464078_zaklad.mjs';

// cx, cz = střed kola (cz už v souřadnicích modelu); R = vnější poloměr; yIn..yOut = rozsah šířky (yOut = vnější strana)
export function kolo(name, { cx, cz, R: Rv = 112.5, yIn, yOut, nBloku = 26, nSpic = 5 }) {
  const R = Rv - 3.2;                                       // poloměr pláště bez bloků běhounu (vnější poloměr s bloky = Rv)
  const y0 = Math.min(yIn, yOut), y1 = Math.max(yIn, yOut), w = y1 - y0, yc = (y0 + y1) / 2, ph = w / 2;
  const sgn = yOut > yIn ? 1 : -1;                         // směr ven
  const g = new Group(name, { pivot: [cx, yc, cz], extras: { osa: [0, 1, 0], popis: 'kolo, volné otáčení kolem osy Y' } });
  const at = p => { p.rot('x', 90); p.move(cx, yc, cz); return p; };   // osa lathe Z -> Y
  // pneumatika (lathe kolem Z, výška = šířka)
  const sh = [[R * 0.66, -ph * 0.90], [R * 0.82, -ph * 0.99], [R * 0.935, -ph * 0.95], [R * 0.985, -ph * 0.70], [R, -ph * 0.40], [R, ph * 0.40], [R * 0.985, ph * 0.70], [R * 0.935, ph * 0.95], [R * 0.82, ph * 0.99], [R * 0.66, ph * 0.90]];
  g.add(at(lathe('cerna_mat', name + '_pneu', sh.map(([r, z]) => [r, z]), 56, [0, 0, 0])));
  // bloky běhounu (obvod + ramena na bocích)
  for (let i = 0; i < nBloku; i++) {
    const a = 360 * i / nBloku + (i % 2 ? 180 / nBloku : 0), hb = (2 * Math.PI * R / nBloku) * 0.30;
    const b = box('cerna_mat', name + '_blok' + i, -hb, hb, -ph * 0.52, ph * 0.52, R - 1.2, R + 3.2);
    b.rot('y', a); b.move(cx, yc, cz); g.add(b);
    const b2 = box('cerna_mat', name + '_rameno' + i, -hb * 0.8, hb * 0.8, ph * 0.46, ph * 0.99, R * 0.86, R * 0.97);
    b2.rot('y', a + 180 / nBloku); b2.move(cx, yc, cz); g.add(b2);
    const b3 = b2.clone(name + '_rameno_m' + i); b3.mirror('y', yc); g.add(b3);
  }
  // disk (vnější strana): věnec + náboj + paprsky
  const yd = yc + sgn * (ph - 11);
  const ring = lathe('cerna_mat', name + '_vence', [[R * 0.62, -4], [R * 0.74, -4], [R * 0.74, 5], [R * 0.62, 5]].map(([r, z]) => [r, z]), 40, [0, 0, 0]);
  ring.rot('x', 90); ring.move(cx, yd, cz); g.add(ring);
  const nab = lathe('cerna', name + '_nabor', [[0.1, -5], [22, -5], [24, 4], [20, 9], [0.1, 9]], 24, [0, 0, 0]);
  nab.rot('x', -90 * sgn); nab.move(cx, yd + sgn * 4, cz); g.add(nab);
  for (let i = 0; i < nSpic; i++) {
    const a = 360 * i / nSpic;
    const sp = box('cerna', name + '_spice' + i, -7, 7, -5, 5, 18, R * 0.72);
    sp.rot('y', a); sp.move(cx, yd, cz); g.add(sp);
  }
  // matice / čep osy
  g.add(tube('ocel', name + '_osa', [[cx, yd + sgn * 6, cz], [cx, yd + sgn * 16, cz]], 6.5, 10));
  return g;
}
