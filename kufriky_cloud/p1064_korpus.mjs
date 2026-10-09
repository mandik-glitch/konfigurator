// Korpus (černá vana) 4932471064: vana s lemem na švíku víka, otvor pro nádoby, střední příčka, čtyři rohové nárazníky, pantové kloubky.
// Spodek (patky, žebra) není na žádné fotografii → zjednodušeno (rovná spodní plocha se zkosením), označeno v poznámkách jako NEOVĚŘENO.
import { cylinder, Group, Part, roundPoly, rrPoly, ccw, loftSolid, ext, slab, ringSolid, bx, zc, polyInset, ZC } from './p1064_zaklad.mjs';
import { flatFace } from './pomocne_4932471064.mjs';
import { H, BASE, CAV, X } from './p1064_data.mjs';

// obrys v plánu (xp, Y) → model; rs po vrcholech
const poly = (pts, rs, n = 4) => ccw(roundPoly(pts.map(([a, b]) => [X(a), b]), rs, n));

// pás mezi smyčkami (A spodní, B horní)
function band(p, A, B, out = true) {
  const n = A.length, a = A.map(q => p.addV(q[0], q[1], q[2])), b = B.map(q => p.addV(q[0], q[1], q[2]));
  for (let i = 0; i < n; i++) { const j = (i + 1) % n; if (out) p.addQ(a[i], a[j], b[j], b[i]); else p.addQ(a[i], b[i], b[j], a[j]); }
}
const L3 = (P, z) => P.map(q => [q[0], q[1], zc(z)]);

function vana(g) {
  const B = BASE, C = CAV;
  // vnější obrys vany: zaoblený obdélník, vpředu výřez pro průchozí štěrbinu držadla (Y −82 … 72, xp 340)
  const outer = poly([[B.xp0, -B.y], [B.xp1, -B.y], [B.xp1, B.y], [B.xp0, B.y]], [B.rc, B.rc, B.rc, B.rc], 6);
  const cav = poly([[C.xp0, -C.y], [C.xp1, -C.y], [C.xp1, C.y], [C.xp0, C.y]], [C.rc, C.rc, C.rc, C.rc], 4);
  const p = new Part('vana', 'cerna_mat'); p.crease = 35;
  const zb = H.zBot, zs = H.zSeam, zf = H.zFloor;
  // vnější stěna se zaoblením u dna
  const bl = polyInset(outer, 1.8);
  band(p, L3(bl, zb), L3(outer, zb + 1.8), true);
  band(p, L3(outer, zb + 1.8), L3(outer, zs), true);
  flatFace(p, bl, [], zc(zb), false);
  // lem na švíku (horní plocha mezi vnějším obrysem a otvorem), vnitřní stěna otvoru, podlaha
  flatFace(p, outer, [cav], zc(zs), true);
  band(p, L3(cav, zf), L3(cav, zs), false);
  flatFace(p, cav, [], zc(zf), true);
  g.add(p);
}

// ---------- nárazníky ----------
// Nárazník = zakřivený "chránič" kolem zaobleného rohu víka (c04: černý pás šířky ~7–9 mm kolem rohu víka, vně o 7,5 mm před čelem víka),
// po celé výšce až těsně pod horní plochu víka (c07/c08: vyšší u vnějšího okraje, víko do rohu zapadá).
const arc = (cx, cy, R, a0, a1, n = 8) => { const o = []; for (let k = 0; k <= n; k++) { const a = (a0 + (a1 - a0) * k / n) * Math.PI / 180; o.push([cx + R * Math.cos(a), cy + R * Math.sin(a)]); } return o; };
function guardPts() {
  // čelní chránič (+Y): rozsah xp 326 … 380, Y 198 … 250; vnitřní hrana = obrys víka (xp 372, roh R 26 se středem (346,214)) + 1 mm
  const front = [[326, 250], [352, 250], ...arc(352, 222, 28, 90, 0, 8).slice(1), [380, 212], [374, 198], [373, 198], [373, 214], ...arc(346, 214, 27, 0, 90, 8).slice(1), [326, 241]];
  // zadní chránič (+Y): xp 0 … 62, rohy R 15; vnitřní hrana = obrys víka (xp 14, roh R 26 se středem (40,214)) + 1 mm
  const rear = [[62, 241], [62, 250], [15, 250], ...arc(15, 235, 15, 90, 180, 6).slice(1), [0, 214], [13, 214], ...arc(40, 214, 27, 180, 90, 8).slice(1)];
  return { front, rear };
}
function narazniky(g) {
  const { front, rear } = guardPts();
  const mk = (pts, name) => {
    const base = ccw(pts.map(([a, b]) => [X(a), b]));
    const R = 2.6, top = H.zBumper, L = [{ poly: polyInset(base, 1.5), z: 5 }, { poly: base, z: 6.5 }, { poly: base, z: top - R }];
    for (let k = 1; k <= 3; k++) { const a = Math.PI / 2 * k / 3; L.push({ poly: polyInset(base, R - R * Math.cos(a)), z: top - R + R * Math.sin(a) }); }
    return loftSolid('cerna_mat', name, L, { crease: 40 });
  };
  for (const it of [mk(front, 'naraznik_celo'), mk(rear, 'naraznik_zad')]) { g.add(it); const m = it.clone(it.name + '_m'); m.mirror('y', 0); g.add(m); }
}

// ---------- hřbet: černá oka pantu (mezi čirými články víka) + ocelový čep ----------
function hrbet(g) {
  const lug = (y0, y1) => g.add(slab('cerna_mat', 'pant_oko', { x0: X(1), x1: X(19), y0, y1, z0: 30, z1: 50, rs: 2.5, seg: 2, reT: 2, reB: 0.8, fs: 2 }));
  lug(-26, 26);
  for (const yc of [78.3, 127.8, 177]) for (const s of [-1, 1]) lug(s * yc - 11, s * yc + 11);
  g.add(cylinder('ocel', 'pant_cep', 1.5, 0, 470, 12, [0, 0]).rot('x', 90).move(X(10), 235, zc(42)));
}
// rámečky "oken" na čelní ploše nárazníků (c07: dvě obdélníková okna se žebrem)
function okna(g) {
  const L = [];
  for (const [z0, z1] of [[34, 43], [19, 28]]) {
    const w = 15, y0 = 217, e = 1.1;
    L.push(bx('seda', 'okno_h', X(379.5), X(380.4), y0, y0 + w, z0, z0 + e), bx('seda', 'okno_h', X(379.5), X(380.4), y0, y0 + w, z1 - e, z1),
      bx('seda', 'okno_v', X(379.5), X(380.4), y0, y0 + e, z0 + e, z1 - e), bx('seda', 'okno_v', X(379.5), X(380.4), y0 + w - e, y0 + w, z0 + e, z1 - e));
  }
  for (const it of L) { g.add(it); const m = it.clone(it.name + '_m'); m.mirror('y', 0); g.add(m); }
}

export function korpus() {
  const g = new Group('korpus');
  vana(g); narazniky(g); hrbet(g); okna(g);
  return g;
}
