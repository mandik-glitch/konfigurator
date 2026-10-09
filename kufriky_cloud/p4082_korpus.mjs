// Korpus (černá vana), rohové nárazníky, hřbet s pantem, patky a kanál spodku – model 4932464082.
import { Group, Part, rrPoly, roundPoly, ccw, loftSolid, ext, slab, rrShell, tray, ringSolid, bx, zc, polyMirrorY, polyArea, cylinder, ZC } from './p4082_zaklad.mjs';

export const K = {
  zBot: 12, zChan: 20, yCh: 32,            // spodní plocha vany (nad patkami)
  zRim: 108.5, yT: 239.5,           // horní okraj vany (stěny) – víko sedí na něm
  xF: 181, xR: -166.5,   // čelní a zadní vnější rovina vany
  yB: 233,             // polovina šířky vany (spodní deska / stěny u rohů)
  yBelt: 243.5,        // vnější plocha pásu na koncové stěně (nahoře)
};

// ---------- nárazníky ----------
// Profil siluety z koncového pohledu (c11/c16, rektifikace y=247): čelo: x=171 (z'=15,5) → 191,4 (z'=27); 191,4 do z'=40; 189 (střed);
// čepice 190,4 (z'=90..105) a zaoblení temene do z'≈112,5; zadní strana: -164 (z'=19) → -190,1 (z'=27..99), šikmé temeno -190 (z'=99) → -172 (z'=112).
// Plán (spodní pohled c08): obrys patky s konkávním zářezem; čelní špička zářezu x=139, zadní x=-128.
const frontPoly = (xF, yE) => roundPoly([[Math.min(181, xF - 12), 184], [Math.min(185.4, xF - 7.5), 184], [Math.min(185.4, xF - 7.5), 207], [xF, 220], [xF, 236], [Math.max(xF - 16.5, 163), yE], [160, yE], [150, yE - 6], [138, 236.2], [138, 227], [150, 196]], [0, 1.5, 2, 6, 3, 3, 3, 8, 1, 1, 0], 4);
// zadní patka (rektifikace spodního pohledu c08): max |y| = 250,4 v x = -147; zadní hrana x = xR; zkosení dole
const rearPoly = (xR, yE) => roundPoly([[-122.5, 232.3], [-127.5, yE - 13], [-131.9, yE - 6.3], [-137.5, yE - 2.5], [-146.9, yE], [-161, yE - 0.4], [-170, yE - 1.4], [-181, yE - 4], [xR, yE - 4.4], [xR, 221], [xR + 8, 214], [xR + 13, 206], [xR + 19, 198.5], [-169.4, 186.6], [-140, 190]], [0, 3, 3, 3, 4, 2, 2, 3, 2, 2, 3, 3, 3, 0, 0], 3);

function narazniky(g) {
  const fl = [[15.5, 172, 240], [19.5, 176.5, 244], [22.5, 181.5, 247], [24, 189, 249], [25.5, 191.8, 250], [27, 192.9, 250], [40, 192.9, 250]];
  const flr = [[19, -166, 241], [21, -180, 243], [22.5, -184, 245], [24, -187, 247], [25.5, -190.2, 249.5], [27, -192.6, 250], [40, -192.6, 250]];
  const items = [];
  items.push(loftSolid('cerna_mat', 'naraznik_patka', fl.map(([z, xF, yE]) => ({ poly: ccw(frontPoly(xF, yE)), z })), { crease: 40 }));
  items.push(loftSolid('cerna_mat', 'naraznik_patka_z', flr.map(([z, xR, yE]) => ({ poly: ccw(rearPoly(xR, yE)), z })), { crease: 40 }));
  // střední sloupek (mírně zapuštěný)
  items.push(slab('cerna_mat', 'naraznik_sloupek', { x0: 157, x1: 190.5, y0: 213, y1: 248.2, z0: 38, z1: 91, rs: [12, 4, 4, 3], seg: 4, reT: 0.5, reB: 0.5, fs: 1 }));
  items.push(slab('cerna_mat', 'naraznik_sloupek_z', { x0: -192.6, x1: -146, y0: 207, y1: 248.2, z0: 38, z1: 99, rs: [4, 12, 4, 4], seg: 4, reT: 0.5, reB: 0.5, fs: 1 }));
  // čepice: čelní se zaobleným temenem, zadní se šikmým temenem
  items.push(slab('cerna_mat', 'naraznik_cepice', { x0: 155, x1: 192, y0: 211, y1: 250, z0: 88, z1: 113, rs: [14, 5, 5, 4], seg: 4, reT: 8, reB: 1, fs: 5, kT: 1.7 }));
  const zadni = loftSolid('cerna_mat', 'naraznik_cepice_z', [
    { poly: ccw(rrPoly(-192.6, -146, 207, 250, [5, 14, 5, 5], 4)), z: 88 },
    { poly: ccw(rrPoly(-192.6, -146, 207, 250, [5, 14, 5, 5], 4)), z: 99.5 },
    { poly: ccw(rrPoly(-184, -146, 207, 250, [5, 14, 5, 5], 4)), z: 105 },
    { poly: ccw(rrPoly(-174, -146, 207, 250, [5, 14, 5, 5], 4)), z: 112 }], { crease: 40 });
  items.push(zadni);
  for (const it of items) { g.add(it); const m = it.clone(it.name + '_m'); m.mirror('y', 0); g.add(m); }
}

// rámeček z pásků kolem obdélníku (osa normály X nebo Y): n = 'x' | 'y', p = poloha plochy, a0..a1 = rozsah podél plochy, z0..z1
function ramecek(L, name, { n, p, a0, a1, z0, z1, w = 1.5, h = 0.7 }) {
  const lo = h < 0 ? p + h : p - 0.3, hi = h < 0 ? p + 0.3 : p + h;
  const mk = (u0, u1, zz0, zz1) => n === 'x' ? bx('seda', name, lo, hi, u0, u1, zz0, zz1) : bx('seda', name, u0, u1, lo, hi, zz0, zz1);
  L.push(mk(a0, a1, z0, z0 + w), mk(a0, a1, z1 - w, z1), mk(a0, a0 + w, z0 + w, z1 - w), mk(a1 - w, a1, z0 + w, z1 - w));
}
function okna(g) {
  const L = [];
  // čelní nárazník (y>0): čelo x = 192,3 (patka) / 191,4 (čepice); horní okna z' 90,5..100,5, dolní 26,7..36,7
  for (const [a, b] of [[221, 234.5]]) ramecek(L, 'okno_cF_h', { n: 'x', p: 191.7, a0: a, a1: b, z0: 90.5, z1: 100.5 });
  for (const [a, b] of [[225, 235]]) ramecek(L, 'okno_cF_d', { n: 'x', p: 192.3, a0: a, a1: b, z0: 26.7, z1: 36.7 });
  ramecek(L, 'panel_cF', { n: 'x', p: 190.4, a0: 222.7, a1: 236, z0: 40, z1: 87.5, w: 1.0, h: 0.5 });
  // okna na zkosené ploše rohu (45°: z (192,237) do (176,250))
  for (const [z0, z1, nm] of [[90.5, 100.5, 'okno_cS_h'], [26.7, 36.7, 'okno_cS_d']]) {
    const th = 139.4, c = [184.65, 243], ww = 9, ws = [[-ww / 2, ww / 2]];
    const bars = [];
    const mk = (u0, u1, zz0, zz1) => { const q = bx('seda', nm, u0, u1, -0.7, 0.3, zz0, zz1); return q; };
    bars.push(mk(-ww / 2, ww / 2, z0, z0 + 1.2), mk(-ww / 2, ww / 2, z1 - 1.2, z1), mk(-ww / 2, -ww / 2 + 1.2, z0 + 1.2, z1 - 1.2), mk(ww / 2 - 1.2, ww / 2, z0 + 1.2, z1 - 1.2));
    for (const q of bars) { q.rot('z', th - 0, [0, 0, 0]); q.move(c[0], c[1], 0); L.push(q); }
  }
  // koncová plocha čelního nárazníku (y ≈ 250): okno na rovné části
  for (const [a, b] of [[160.5, 171]]) ramecek(L, 'okno_kF_h', { n: 'y', p: 249.0, a0: a, a1: b, z0: 91, z1: 101 });
  for (const [a, b] of [[162, 172.5]]) ramecek(L, 'okno_kF_d', { n: 'y', p: 249.1, a0: a, a1: b, z0: 26.7, z1: 36.7 });
  // řada drobných žeber pod římsou koncové stěny (rozteč 12 mm, c11)
  for (let i = 0; i < 11; i++) { const x = 52 - i * 12; L.push(bx('cerna_mat', 'zebro_pasu', x - 0.6, x + 0.6, 243.2, 244.1, 80.5, 89)); }
  for (const it of L) { g.add(it); const m = it.clone(it.name + '_m'); m.mirror('y', 0); g.add(m); }
}

// ---------- vana ----------
function vana(g) {
  g.add(tray('cerna_mat', 'vana', { x0: K.xR, x1: K.xF, y0: -K.yT, y1: K.yT, z0: K.zChan, z1: K.zRim, rs: [10, 14, 14, 10], seg: 4, wall: 4, floor: 3, re: 3, fs: 3 }));
  // spodní desky po obou stranách kanálu (z' 12..26); čelní hrana desky: x=179,4 u rohů, x=169,4 v zářezu pod západkou (|y| 118..185), x=181 u držadla
  const zonyY = [[K.yCh, 118, 181], [118, 185, 169.4], [185, K.yB, 179.4]];
  for (const s of [-1, 1]) for (const [a, b, xf] of zonyY) {
    const y0 = s > 0 ? a : -b, y1 = s > 0 ? b : -a;
    const rs = b === K.yB ? (s > 0 ? [8, 14, 0.6, 0.6] : [0.6, 0.6, 14, 8]) : a === K.yCh ? (s > 0 ? [0.6, 0.6, 0.6, 0.6] : [0.6, 0.6, 0.6, 0.6]) : [0.6, 0.6, 0.6, 0.6];
    g.add(slab('cerna_mat', 'spodni_deska', { x0: K.xR, x1: xf, y0, y1, z0: K.zBot, z1: K.zChan + 3, rs, seg: 4, reB: 2.5, reT: 0.5, fs: 3 }));
  }
  // červený zachytávací háček v kanálu pod držadlem (3 drážky), x 148..167, y -25..22
  g.add(slab('cervena', 'kanal_hacek', { x0: 148, x1: 167.5, y0: -25, y1: 22, z0: 13.2, z1: 25, rs: 4, seg: 3, reB: 1.5, reT: 1, fs: 2 }));
  for (const yc of [-15, -1.5, 12]) g.add(slab('cerna_mat', 'kanal_hacek_drazka', { x0: 156, x1: 167.7, y0: yc - 3.2, y1: yc + 3.2, z0: 13.0, z1: 14.4, rs: 1, seg: 1, reB: 0.2, reT: 0.2, fs: 1 }));
  g.add(slab('cerna_mat', 'kanal_celo', { x0: 165, x1: 181, y0: -K.yCh - 0.5, y1: K.yCh + 0.5, z0: K.zBot, z1: K.zChan + 3, rs: 0.6, seg: 2, reB: 2, reT: 0.5, fs: 2 }));
  // horní deska vany (černý rám kolem otvoru pro nádoby): vnější obrys vany, otvor 305 × 457
  g.add(ringSolid('cerna_mat', 'vana_rám', rrPoly(K.xR, K.xF, -K.yT, K.yT, [10, 14, 14, 10], 4), rrPoly(-162.2, 151.3, -235.2, 235.2, [6.5, 6.5, 6.5, 6.5], 4), 104.5, K.zRim));
  // pásy na koncových stěnách (vystupují z vany k víku)
  for (const s of [-1, 1]) {
    const mk = (y0, y1, dz) => ccw(rrPoly(-80, 64, s > 0 ? y0 : -y1, s > 0 ? y1 : -y0, 3, 2));
    const belt = loftSolid('cerna_mat', 'pas_' + (s > 0 ? 'p' : 'm'), [
      { poly: mk(228, 238.5), z: 14 }, { poly: mk(228, 240), z: 30 }, { poly: mk(228, K.yBelt), z: 105 }, { poly: mk(228, K.yBelt - 1.5), z: 109 }], { crease: 40 });
    g.add(belt);
  }
}

// ---------- hřbet: černá oka pantu (z rektifikace c08 – středy |y| = 78,6; 128,1; 177,2; šířka 22,4 + střední 80 mm) ----------
function hrbet(g) {
  const lug = (y0, y1) => {
    // dutý černý "kalíšek" otevřený dolů: x -182..-164, z' 88..109
    g.add(slab('cerna_mat', 'pant_oko', { x0: -182, x1: -163, y0, y1, z0: 88, z1: 109, rs: 2.5, seg: 2, reT: 2, reB: 0.8, fs: 2 }));
  };
  lug(-40, 40);
  for (const yc of [78.6, 128.1, 177.2]) for (const s of [-1, 1]) lug(s * yc - 11.2, s * yc + 11.2);
  // ocelový čep pantu (osa Y) skrz oka – x = -175,5, z' = 97
  g.add(cylinder('ocel', 'pant_cep', 1.6, 0, 484, 12, [0, 0]).rot('x', 90).move(-175.5, 242, zc(97)));
}

// ---------- patky spodku + kanál ----------
// [y0,y1] pro řady (x): řada 1 u čela, 2 uprostřed, 3 u pantu; hodnoty z rektifikace c08 (±1,5 mm); základna patky u desky, spodní plocha užší (šikmé boky)
const PADS = [
  { x0: 63, x1: 98, ys: [[41.7, 116.7], [140, 223]] },
  { x0: -49, x1: -8, ys: [[52, 105], [151, 222]] },
  { x0: -150, x1: -112, ys: [[33, 120], [142, 225]] },
];
function patky(g) {
  for (const row of PADS) for (const [a, b] of row.ys) for (const s of [-1, 1]) {
    const y0 = s > 0 ? a : -b, y1 = s > 0 ? b : -a;
    const lay = (dx, dy, z) => ({ poly: ccw(rrPoly(row.x0 + dx, row.x1 - dx, y0 + dy, y1 - dy, 4, 3)), z });
    g.add(loftSolid('cerna_mat', 'patka', [lay(4.6, 1.9, 4), lay(3.6, 1.4, 5.5), lay(0.6, 0.3, K.zBot - 1.5), lay(0, 0, K.zBot + 1)], { crease: 40 }));
    // spodní plocha: obvodový rámeček + žebra mezi štěrbinami (štěrbiny = 4,6 × ~19 mm, rozteč 8,9 mm)
    const bx0 = row.x0 + 4.6, bx1 = row.x1 - 4.6, by0 = y0 + 1.9, by1 = y1 - 1.9;
    const sx0 = bx0 + 3.5, sx1 = bx1 - 3.5, ylen = by1 - by0;
    const n = Math.max(2, Math.floor((ylen - 7 + 4.3) / 8.9)), tot = n * 4.6 + (n - 1) * 4.3, ys0 = (by0 + by1) / 2 - tot / 2;
    const T = (x0, x1, yy0, yy1) => g.add(bx('cerna_mat', 'patka_zebro', x0, x1, yy0, yy1, 0, 4.5));
    T(bx0, sx0, by0, by1); T(sx1, bx1, by0, by1); T(sx0, sx1, by0, ys0); T(sx0, sx1, ys0 + tot, by1);
    for (let k = 0; k < n - 1; k++) T(sx0, sx1, ys0 + k * 8.9 + 4.6, ys0 + (k + 1) * 8.9);
  }
}

export function korpus() {
  const g = new Group('korpus');
  vana(g); narazniky(g); okna(g); hrbet(g); patky(g);
  return g;
}
