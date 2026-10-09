// Buňky: přepážky, střední sloupek se západkou, tři ocelové tyče a deset výklopných boxů (8 malých + 2 velké s děličem) – model 4932498323.
// Každý box je samostatná skupina box_N s pivotem na ose tyče (rovnoběžná s Y) a extras.osa = [0,-1,0] (kladný úhel = sklopení dopředu, +Z).
import { loftRings } from './jadro/mesh.js';
import { Group, Part, slab, tray, roundPoly, ccw, polyInset, ext, bx, tube, cylinder, mirrorInto } from './p8323_zaklad.mjs';
import { K } from './p8323_korpus.mjs';

export const B = {
  pitch: 108.1, xTop0: K.XOT,               // rozteč řad; horní hrana boxů v 1. řadě (u madla)
  hF: 94.2, rodBelow: 80.2,                 // výška boxu u čela (od špiček pilířků po okraj); osa tyče pod okrajem
  zRod: 77, rRod: 2.7,                      // osa tyče (Z), poloměr tyče
  zHood: 74.2,                              // čelní rovina kápě boxu (Z)
  D: 102, rise: 4, hood: 16, t: 1.7,        // hloubka boxu (kápa → zadní stěna), stoupání okraje k zadní stěně, výška kápě, tloušťka stěn
  wS: 87.6, gap: 5.7, y0: 19.0,             // malý box: šířka, mezera, vnitřní hrana (|y|) – vedle sloupku
  colHalf: 15.6,
};
export const XTOP = [0, 1, 2].map(r => B.xTop0 - B.pitch * r);
export const XROD = XTOP.map(x => x - B.rodBelow);

// ---------- přepážky, sloupek, tyče ----------
export function bunky(g) {
  const { YIN, ZBP } = K;
  // přepážky pod každou řadou (u poslední je to spodní polička nad spodním pásem)
  for (let r = 0; r < 3; r++) {
    const xb = XTOP[r] - B.hF;
    g.add(slab('o8323_mat', 'prepazka_' + (r + 1), { x0: xb - 13.9, x1: xb, y0: -YIN, y1: YIN, z0: ZBP, z1: 72, rs: 0.8, seg: 2, reT: 1, fs: 2 }));
  }
  // střední sloupek (užší horní část)
  g.add(slab('o8323_mat', 'sloupek', { x0: K.XOB, x1: 95, y0: -B.colHalf, y1: B.colHalf, z0: ZBP, z1: 82, rs: 1, seg: 2, reT: 1.2, fs: 2 }));
  g.add(slab('o8323_mat', 'sloupek_horni', { x0: 95, x1: K.XOT, y0: -12.3, y1: 12.3, z0: ZBP, z1: 80, rs: 1, seg: 2, reT: 1.2, fs: 2 }));
  for (let r = 0; r < 3; r++) g.add(slab('o8323_mat', 'sloupek_objimka_' + (r + 1), { x0: XROD[r] - 6.5, x1: XROD[r] + 6.5, y0: -17.6, y1: 17.6, z0: 66, z1: 82.5, rs: 1.5, seg: 2, reT: 1.5, fs: 2 }));
  // červená západka na sloupku (T), c01: příčka y -10,5…9,5 / X 42,3…54,2; nožka y -5,5…5 / X 28…42,3
  g.add(slab('cervena', 'sloupek_zapadka', { x0: 42.3, x1: 54.2, y0: -10.5, y1: 9.5, z0: 82, z1: 85, rs: 1.5, seg: 2, reT: 0.8, fs: 2 }));
  g.add(slab('cervena', 'sloupek_zapadka_noha', { x0: 28, x1: 42.3, y0: -5.5, y1: 5, z0: 82, z1: 85, rs: 1.2, seg: 2, reT: 0.8, fs: 2 }));
  // tyče
  for (let r = 0; r < 3; r++) g.add(tube('ocel', 'tyc_' + (r + 1), [[XROD[r], -YIN - 8, B.zRod], [XROD[r], YIN + 8, B.zRod]], B.rRod, 14));
}

// ---------- box ----------
// Stavba v lokálních souřadnicích (u = hloubka od čela kápy dozadu, v = šířka (Y), w = výška (X) od osy tyče), pak otočení do modelu:
// (u,v,w) → X = XROD + w, Y = yc + v, Z = zHood − u.
function hoodBand(mat, name, W, notches) {
  const { D, t, hood, rise } = B;
  const hw = W / 2, wLow = 80.2 - hood - 1.7, wFront = 80.2;
  // vrcholy (u,v) proti směru hodinových ručiček; na čelní hraně body výřezu pro prst
  const front = [];
  for (const c of [...notches].sort((a, b) => b - a)) front.push([0, c + 9], [0, c + 5], [0, c - 5], [0, c - 9]);
  const verts = [[D, -hw], [D, hw], [0, hw], ...front, [0, -hw]];
  const rr = verts.map((p, i) => i === 0 || i === 1 ? 5 : (i === 2 || i === verts.length - 1) ? 3.5 : 0);
  const outer = ccw(roundPoly(verts, rr, 3));
  const inner = polyInset(outer, t);
  const wTop = (p, depth) => wFront + rise * p[0] / D - depth;
  const notchDepth = p => {
    if (p[0] > 2.5) return 0;
    let d = 0;
    for (const c of notches) { const a = Math.abs(p[1] - c); d = Math.max(d, a <= 5.01 ? 5 : a < 9.01 ? 5 * (9 - a) / 4 : 0); }
    return d;
  };
  const P = new Part(name, mat); P.crease = 40;
  const ring = (poly, f) => poly.map(p => [p[0], p[1], f(p)]);
  loftRings(P, [ring(outer, () => wLow), ring(outer, p => wTop(p, notchDepth(p))), ring(inner, p => wTop(p, notchDepth(p))), ring(inner, () => wLow)], { closed: true });
  return P;
}

export function box(idx, row, yc, W, big) {
  const { D, t, hood, zHood, zRod } = B;
  const xr = XROD[row], hw = W / 2;
  const g = new Group('box_' + idx, { pivot: [xr, yc, zRod], extras: { osa: [0, -1, 0], rada: row + 1, velky: !!big, max_uhel: 100, popis: 'výklopný box; osa otáčení = tyč (rovnoběžná s Y); kladný úhel = sklopení dopředu (+Z)' } });
  const L = [];
  const wHb = 80.2 - hood - 1.7;                       // dolní hrana kápy (w)
  // spodní nádoba (vlastní dno i stěny), horní okraj ve výšce dolní hrany kápy
  L.push(tray('o8323_cira', 'telo', { x0: 1.7, x1: D, y0: -hw, y1: hw, z0: -5, z1: wHb, rs: [5, 3, 3, 5], seg: 3, wall: t, floor: t, re: 3.5, fs: 3 }));
  // kápa s okrajem šikmo stoupajícím k zadní stěně a výřezy pro prst
  L.push(hoodBand('o8323_cira', 'kapa', W, big ? [-W / 4, W / 4] : [0]));
  // čelní pilířky (boční hrany bez zapuštění) až na špičky pod dnem; zadní výstupky na dně (západky)
  for (const s of [-1, 1]) {
    const v0 = s > 0 ? hw - 5.5 : -hw, v1 = s > 0 ? hw : -hw + 5.5;
    L.push(slab('o8323_cira', 'pilirek', { x0: 0, x1: 2.6, y0: v0, y1: v1, z0: -14, z1: wHb + 1, rs: 0.8, seg: 2, reB: 1.6, fs: 2 }));
    L.push(slab('o8323_cira', 'vystupek_dna', { x0: D - 24, x1: D - 8, y0: s > 0 ? hw - 0.3 : -hw - 5.7, y1: s > 0 ? hw + 5.7 : -hw + 0.3, z0: -13, z1: -5, rs: 0.8, seg: 2, reB: 1, fs: 2 }));
    // oko okolo tyče (hák) a krček ke stěně
    const vv = s > 0 ? [hw - t - 0.3, hw + 0.6] : [-hw - 0.6, -hw + t + 0.3];
    L.push(tube('o8323_cira', 'hak', [[zHood - zRod, vv[0], 0], [zHood - zRod, vv[1], 0]], 5, 14));
  }
  // dvě nízká žebra na dně
  for (const s of [-1, 1]) L.push(slab('o8323_cira', 'zebro_dna', { x0: D - 52, x1: D - 30, y0: s * (hw - 14) - 3.2, y1: s * (hw - 14) + 3.2, z0: -5 + t, z1: -5 + t + 1.8, rs: 0.8, seg: 2, reT: 0.6, fs: 1 }));
  // dělič (jen velké boxy): černá deska s okrajem
  if (big) {
    const dv = [[4.6, -5 + t + 0.2], [D - t - 1.5, -5 + t + 0.2], [D - t - 1.5, 83.8], [4.6, 80.1]];
    const d = ext('o8323_cerna', 'delic', ccw(dv), -1.1, 1.1);     // polygon (u,w), vytažení po v
    d.mapV((a, b, c) => [a, c, b]); d.flip();
    L.push(d);
  }
  for (const p of L) { p.rot('y', 90, [0, 0, 0]); p.move(xr, yc, zHood); g.add(p); }
  return g;
}

export function boxy() {
  const out = [];
  const { wS, gap, y0 } = B;
  const wBig = 2 * wS + gap;
  const cB = y0 + wS / 2, cA = cB + wS + gap, cBig = y0 + wBig / 2;
  let n = 0;
  for (const c of [cA, cB, -cB, -cA]) out.push(box(++n, 0, c, wS, false));
  for (const c of [cBig, -cBig]) out.push(box(++n, 1, c, wBig, true));
  for (const c of [cA, cB, -cB, -cA]) out.push(box(++n, 2, c, wS, false));
  return out;
}
