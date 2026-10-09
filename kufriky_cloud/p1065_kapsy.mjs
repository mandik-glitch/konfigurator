// Kapsy víka (osmiúhelníkové prolisy s šikmou stěnou, tenkostěnné, + dno + šestiúhelníková mřížka) – model 4932471065.
// Šestiúhelníky: ploché (horní a spodní hrana rovnoběžná s X), strana a = 6,93 mm (c03: rozteč sloupců 10,4 = 1,5 a), společná mřížka celého víka.
import { Part, ccw, zc } from './p1065_zaklad.mjs';
import { loftRings } from './jadro/mesh.js';
import { extrude, offsetPoly, insetRounded, pointInPoly } from './pomocne.mjs';

export const HEX = { a: 6.93, x0: -72.1, y0: 98.2 };

// tenké čáry mřížky jako oboustranné pásky v rovině z' = z; hrany, jejichž oba koncové body leží uvnitř polygonu `poly` a nejsou v `skip`
export function hexMrizka(mat, name, { poly, z, w = 0.7, skip = null }) {
  const p = new Part(name, mat); p.crease = 60;
  const a = HEX.a, h = Math.sqrt(3) * a, inner = offsetPoly(poly, 0.9), seen = new Set();
  const key = q => Math.round(q[0] * 20) + ',' + Math.round(q[1] * 20), Z = zc(z);
  for (let i = -20; i <= 20; i++) for (let j = -20; j <= 20; j++) {
    const cx = HEX.x0 + 1.5 * a * i, cy = HEX.y0 + h * j + (Math.abs(i) % 2 ? h / 2 : 0);
    if (cx < -110 || cx > 110 || cy < -185 || cy > 135) continue;
    const V = Array.from({ length: 6 }, (_, k) => [cx + a * Math.cos(k * Math.PI / 3), cy + a * Math.sin(k * Math.PI / 3)]);
    for (let k = 0; k < 6; k++) {
      const A = V[k], B = V[(k + 1) % 6], ek = [key(A), key(B)].sort().join('|');
      if (seen.has(ek)) continue; seen.add(ek);
      if (!pointInPoly(A, inner) || !pointInPoly(B, inner)) continue;
      if (skip && (skip(A) || skip(B))) continue;
      const dx = B[0] - A[0], dy = B[1] - A[1], l = Math.hypot(dx, dy), nx = -dy / l * w / 2, ny = dx / l * w / 2;
      const v = [p.addV(A[0] + nx, A[1] + ny, Z), p.addV(B[0] + nx, B[1] + ny, Z), p.addV(B[0] - nx, B[1] - ny, Z), p.addV(A[0] - nx, A[1] - ny, Z)];
      p.addQ(v[0], v[1], v[2], v[3]); p.addQ(v[0], v[3], v[2], v[1]);
    }
  }
  return p;
}

// kapsa: ostrý obrys `pts` se zaoblením `rs` (v rovině horní plochy zTop), hloubka d, vodorovný průmět šikmé stěny s; stěna tl. 1,2 (uzavřený profil), dno tl. 1,2
export function kapsa(g, { pts, rs, zTop, d, s, name, mat = 'vicko_cira', hex = true, skip = null, matHex = 'bila' }) {
  const zF = zTop - d, t = 1.2, ring = k => ccw(insetRounded(pts, rs, k, 3));
  const prof = [[zTop, 0], [zF, s], [zF - t, s + 0.7], [zTop - t, 1.5]];
  const wall = new Part(name + '_stena', mat); wall.crease = 50;
  loftRings(wall, prof.map(([z, k]) => ring(k).map(q => [q[0], q[1], zc(z)])), { closed: true });
  g.add(wall);
  g.add(extrude(mat, name + '_dno', ring(s + 0.3), [], zc(zF - t), zc(zF), { crease: 30 }));
  if (hex) g.add(hexMrizka(matHex, name + '_hex', { poly: ring(s), z: zF + 0.12, skip }));
}
