// Pojízdný box 4932498651 – kola (2 ks, uzly s osou otáčení rovnoběžnou s Y): pryžová pneumatika s dezénem, loukoťový disk s 10 širokými vybráními,
// matice osy. Levé kolo = zrcadlo pravého podle roviny Y = 0.
import { Part, Group, lathe, cylY, extrude, roundPoly, circlePoly, rotPoly, loftRings } from './p4932478162_zaklad.mjs';
import { KOLO } from './p4932498651_data.mjs';

function dilyKola() {
  const K = KOLO, W = K.y1 - K.y0, out = [];
  const toY = p => { p.mapV((u, v, w) => [u + K.xc, w + K.y0, v + K.zc]); return p.flip(); };   // osa Z → osa Y (transpozice → flip)
  // pneumatika: uzavřený prstenec (průřez „vana“ s mírně vypouklým běhounem), uprostřed otvor pro disk
  const prof = [[K.r - 9, 0], [K.r - 1.5, 4], [K.r, 9], [K.r, W - 9], [K.r - 1.5, W - 4], [K.r - 9, W], [76, W - 3], [76, 3]];
  const tire = new Part('pneumatika', 'guma'); tire.crease = 40;
  const N = 56;
  loftRings(tire, prof.map(([rr, w]) => Array.from({ length: N }, (_, i) => { const a = 2 * Math.PI * i / N; return [rr * Math.cos(a), rr * Math.sin(a), w]; })), { closed: true });
  out.push(toY(tire));
  // dezén: krátké příčné žlábky po obvodu (tmavší kostky na běhounu)
  for (let k = 0; k < 28; k++) {
    const a = 2 * Math.PI * k / 28, c = Math.cos(a), s = Math.sin(a), r0 = K.r - 0.6;
    const q = new Part('dezen', 'cerna_mat'); const pts = [];
    for (const [rr, w] of [[r0 - 2.2, 4], [r0 + 0.6, 4], [r0 + 0.6, W - 4], [r0 - 2.2, W - 4]]) pts.push([K.xc + rr * c, K.y0 + w, K.zc + rr * s]);
    const d = 3.2 / K.r, c2 = Math.cos(a + d), s2 = Math.sin(a + d);
    const P = [[r0 - 2.2, 4], [r0 + 0.6, 4], [r0 + 0.6, W - 4], [r0 - 2.2, W - 4]];
    const A = P.map(([rr, w]) => q.addV(K.xc + rr * c, K.y0 + w, K.zc + rr * s)), B = P.map(([rr, w]) => q.addV(K.xc + rr * c2, K.y0 + w, K.zc + rr * s2));
    for (let i = 0; i < 4; i++) { const j = (i + 1) % 4; q.addQ(A[i], A[j], B[j], B[i]); }
    q.addQ(A[0], B[0], B[3], A[3]); q.addQ(A[1], A[2], B[2], B[1]);
    out.push(q);
  }
  // disk (loukoť): plný kotouč s 10 velkými vybráními
  const outer = circlePoly(0, 0, 80, 48);
  const holes = [];
  const pol = (r, deg) => [r * Math.cos(deg * Math.PI / 180), r * Math.sin(deg * Math.PI / 180)];
  for (let k = 0; k < 10; k++) { const a = 36 * k + 18; holes.push(roundPoly([pol(46, a - 11), pol(70, a - 13.5), pol(70, a + 13.5), pol(46, a + 11)], [4, 4, 4, 4], 2)); }
  const disk = extrude('kolo_seda', 'disk', outer, holes, 0, 26, { crease: 30 }); toY(disk); disk.move(0, 12, 0);
  out.push(disk);
  out.push(cylY('cerna', 'naboj', 27, K.y0 + 8, K.y1 - 6, K.xc, K.zc, 24).move(0, 0, 0));
  out.push(cylY('ocel', 'matice', 16, K.y1 - 6, K.y1, K.xc, K.zc, 6));
  return out;
}
function kolo(s) {
  const K = KOLO, id = s > 0 ? 'P' : 'L';
  const g = new Group('kolo_' + id, { pivot: [K.xc, s * (K.y0 + K.y1) / 2, K.zc], extras: { osa: [0, 1, 0], max_uhel: 360, popis: 'kolo Ø 228 (otáčí se kolem osy Y)' } });
  for (const p of dilyKola()) { p.name += '_' + id; if (s < 0) p.mirror('y', 0); g.add(p); }
  return g;
}
export function kola() { const g = new Group('kola'); g.addGroup(kolo(1)); g.addGroup(kolo(-1)); return g; }
