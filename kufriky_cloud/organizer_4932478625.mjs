// Milwaukee PACKOUT Deep Organiser 4932478625 (hluboký organizér, 8 oddílů, 6 červených děličů).
// VLASTNÍ parametrický generátor podle fotografií výrobce (viz zdroje/4932478625_poznamky.md).
// Souřadnice (mm): X = šířka (čelo +X), Y = délka, Z = výška (nahoru); počátek = střed obálky 386 × 507 × 178.
// Uvnitř souboru se pracuje ve "výškách od spodku" zA (0 = nejnižší bod = 0 .. 178 = vršek víka); do GLB se převádí zA - 89.
import { Part, Group, roundedBox, hollowBox, box, prism, lathe, cylinder, tube } from './jadro/mesh.js';
import { reliefX, deskaVyska, deskaObrys, plastObvodu, prismYZ, prismXZ, rrPolyYZ, rozdel, smooth, clamp, sdRR, patch } from './pomocne_8625.mjs';

export const SKU = '4932478625';
export const OBALKA = { x: 386, y: 507, z: 178 };
export const CELO = 'X';

const ZC = 89;
const zc = z => z - ZC;
const RB = (mat, name, o) => roundedBox(mat, name, { x0: o.x0, x1: o.x1, y0: o.y0, y1: o.y1, z0: o.z0 - ZC, z1: o.z1 - ZC, rc: o.rc ?? 0, re: o.re ?? 0, reB: o.reB, reT: o.reT, seg: o.seg ?? 4, fs: o.fs ?? 2 });
const BX = (mat, name, x0, x1, y0, y1, z0, z1) => box(mat, name, x0, x1, y0, y1, z0 - ZC, z1 - ZC);
const shiftZ = (p) => p.move(0, 0, -ZC);

// ---------------------------------------------------------------------------------------------
// PARAMETRY (hodnoty z fotografií, nejistoty viz poznámky)
// ---------------------------------------------------------------------------------------------
export const P = {
  zBody0: 25.5,      // spodek vany: čelní spodní hrana těla leží ve výšce ~25 mm (měřeno na c13 podle siluety)
  zSeam: 157,        // dosedací rovina víka (okraj vany); víko má 21 mm (c13: přechod čiré/černé v rektifikovaném čele)
  zTop: 178,         // vršek víka
  xFace: 184,        // rovina čelní stěny (zadní -xFace)
  yWall: 249.5,      // boční stěna vany (± Y)
  post: { dx: 34, dy: 30, xo: 193, yo: 253.5, z1: 176 },
  inner: { x0: -152.5, x1: 152.5, y0: -228.5, y1: 228.5, floor: 34 },
  latchY: 152,       // osa západek (± Y)
  lid: { x0: -188, x1: 187, y0: -250.5, y1: 250.5, rc: 16 },
};

// ---------------------------------------------------------------------------------------------
// KORPUS (černý)
// ---------------------------------------------------------------------------------------------
function korpus() {
  const g = new Group('korpus');
  const I = P.inner;
  // vana: tenkostěnná dutá nádoba (otevřená nahoře) + silné čelní a zadní stěny
  g.add(shiftZ(hollowBox('cerna', 'vana', { x0: -P.xFace, x1: P.inner.x1 + 6, y0: -P.yWall, y1: P.yWall, z0: P.zBody0 + 4, z1: P.zSeam, rc: 16, re: 4, wall: 5, floor: I.floor - P.zBody0 - 4, seg: 4, fs: 2 })));
  // silná čelní a zadní stěna (kolem vnitřního prostoru 305 mm)
  g.add(RB('cerna', 'stena_zadni', { x0: -P.xFace + 1, x1: I.x0, y0: -230, y1: 230, z0: P.zBody0 + 2, z1: P.zSeam, rc: 2, re: 0.5 }));
  // rohové sloupky (nárazníky)
  const q = P.post;
  for (const sx of [-1, 1]) for (const sy of [-1, 1]) {
    g.add(RB('cerna', 'sloupek', { x0: sx > 0 ? q.xo - q.dx : -q.xo, x1: sx > 0 ? q.xo : -q.xo + q.dx, y0: sy > 0 ? q.yo - q.dy : -q.yo, y1: sy > 0 ? q.yo : -q.yo + q.dy, z0: P.zBody0, z1: q.z1, rc: 9, re: 3 }));
  }
  return g;
}

// ---------------------------------------------------------------------------------------------
// ČELO (reliéf čelní stěny, západky, držadlo)
// ---------------------------------------------------------------------------------------------
// Rozměry v rovině čela změřeny na rektifikované fotografii c13 (rovina X=186, kamera z obrysu) – viz poznámky.
export const F = {
  xf: 184,                       // rovina čelní stěny
  win: { hy: 98.5, z0: 27, z1: 121, xBack: 160 },          // okno pro držadlo (|y| < hy)
  blade: { y0: 98.5, y1: 118.6, z1: 115, h: 1.5 },        // žebra (lopatky) po stranách okna
  pocket: { y0: 118.6, y1: 186.6, z0: 51, z1: 157, zr: 88, depth: 8 },   // kapsy západek
  latchY: 152.9,
};
const cl = (v) => Math.max(0, Math.min(1, v));
const soft = (d, w) => smooth(d / w + 0.5);              // 1 uvnitř, 0 vně, měkký přechod šířky w; d = podepsaná vzdálenost dovnitř
export function frontX(y, z) {
  const ay = Math.abs(y), q = F.pocket, b = F.blade, w = F.win;
  let x = F.xf;
  // lopatky
  const mb = soft(Math.min(ay - b.y0, b.y1 - ay, b.z1 - z), 1.2);
  x += b.h * mb * cl((z - 20) / 4);
  // kapsy západek (spodní šikmá "brada")
  const ramp = cl((z - q.z0) / (q.zr - q.z0));                          // 0 dole → 1 od zr nahoru
  const inset = 10 * (1 - ramp);                                        // zešikmení boků v brádě
  const mp = soft(Math.min(ay - q.y0 - inset, q.y1 - ay - inset, q.z1 - z, z - q.z0), 1.2);
  x -= q.depth * ramp * mp;
  // okno držadla
  const mw = soft(Math.min(w.hy - ay, w.z1 - z, z - w.z0), 1.0);
  x -= (F.xf - w.xBack) * mw;
  // horní výklenek nad prostředkem okna (deska s drážkami za kroužkem)
  const mt = soft(Math.min(48 - ay, 136 - z, z - 118), 1.0);
  x -= 18 * mt;
  return x;
}
function celo() {
  const g = new Group('celo');
  const yb = [98.5, 118.6, 186.6, 48], zb = [27, 51, 88, 115, 118, 121, 136];
  const zly = [], zlz = [...zb, 20, 24, 26.5, 157];
  for (const v of yb) { zly.push(v, -v, v - 1.5, v + 1.5, -v - 1.5, -v + 1.5, v - 10, -v + 10, v + 10, -v - 10); }
  const rel = reliefX('cerna', 'celo_relief', { y0: -226, y1: 226, z0: 26.5, z1: P.zSeam, hy: 3, hz: 3, zlomyY: zly, zlomyZ: zlz, fn: (y, z) => frontX(y, z), xb: 152.5 });
  shiftZ(rel); g.add(rel);
  // spodní lemy po stranách (nad lopatkami a mimo ně) – čelní stěna sahá dolů do z=26.5
  // klíny (nožičky po stranách držadla): svislá vnitřní hrana, vnější zešikmená (c13)
  for (const s of [-1, 1]) {
    const a = 98.5, bq = 120.5;
    const poly = s > 0 ? [[a, 30], [bq, 30], [bq - 7.5, 0.5], [a, 0.5]] : [[-a, 30], [-a, 0.5], [-bq + 7.5, 0.5], [-bq, 30]];
    g.add(shiftZ(prismYZ('cerna', 'klin', poly, 160, F.xf - 1)));
  }
  // spodní červený jazýček (pojistka) – podle c13 střed y≈+18, šířka ≈ 50
  g.add(RB('cervena', 'dolni_jazyk', { x0: 168, x1: 181, y0: -8, y1: 44, z0: 18, z1: 36, rc: 1, re: 0.8 }));
  g.add(RB('cervena', 'dolni_jazyk_vystup', { x0: 168, x1: 181, y0: -8, y1: 44, z0: 14, z1: 27, rc: 1, re: 0.8 }));
  // držadlo (zjednodušeně, bude doladěno)
  g.add(RB('cervena', 'drzadlo_pricka', { x0: 172, x1: 183, y0: -98, y1: 98, z0: 40, z1: 52, rc: 2, re: 1 }));
  for (const s of [-1, 1]) g.add(RB('cervena', 'drzadlo_sloupek', { x0: 172, x1: 183, y0: s > 0 ? 70 : -98, y1: s > 0 ? 98 : -70, z0: 40, z1: 118, rc: 2, re: 1 }));
  g.add(RB('seda', 'drzadlo_uchop', { x0: 174, x1: 185, y0: -55, y1: 63, z0: 40, z1: 62, rc: 3, re: 2 }));
  // západky
  for (const s of [-1, 1]) {
    const y = s * F.latchY;
    g.add(RB('cervena', 'zamek_jazyk', { x0: 175, x1: 181, y0: y - 26, y1: y + 26, z0: 91, z1: 147, rc: 3, re: 1 }));
    for (const t of [-1, 1]) g.add(tube('ocel', 'zamek_trmen', [[183, y + t * 33.5, zc(100)], [184, y + t * 33.5, zc(166)]], 1.3, 8));
    g.add(RB('vicko_cira', 'zamek_drzak', { x0: 176, x1: 190, y0: y - 30, y1: y + 30, z0: 156, z1: 170, rc: 2, re: 1 }));
  }
  return g;
}

// ---------------------------------------------------------------------------------------------
// VÍKO (čiré) – samostatná skupina s pivotem na pantové hraně
// ---------------------------------------------------------------------------------------------
// Půdorys a kapsy víka: změřeno na c04 (pohled shora, rektifikace roviny vršku), měřítko dorovnáno na obálku 507×386.
export const LID = {
  xR: -171, xF: 182, xFn: 173, notchY: [-42.5, 51.3],           // zadní hrana, přední hrana, přední hrana ve výřezu uprostřed
  yS: 241, rc: 18,                                              // poloviční šířka víka, zaoblení rohů
  plat: { x0: -169, x1: 156, y: 230.7, rc: 14 },                 // horní plošina (kapsy), okolo klesající okraj
  D: 14, t: 2.5,                                                // hloubka kapes, tloušťka plastu
  rows: [[46.4, 137.8], [-55.6, 32.8], [-157.8, -69.4]],        // [x0 (zadní), x1 (přední)] řad A, B, C
  cols: [[-224.4, -133.2], [-121.4, -30.9], [31.4, 121.4], [133.7, 225]],
  slot: { y0: -21.2, y1: 23.1, x0: -149.6, x1: 126.9 },
};
const pockets = () => {
  const [A, B, C] = LID.rows, [c1, c2, c3, c4] = LID.cols; const out = [];
  for (const [r, cs] of [[A, [c1, c2, c3, c4]], [C, [c1, c2, c3, c4]]]) for (const c of cs) out.push({ x0: r[0], x1: r[1], y0: c[0], y1: c[1] });
  out.push({ x0: B[0], x1: B[1], y0: c1[0], y1: c2[1] }, { x0: B[0], x1: B[1], y0: c3[0], y1: c4[1] });
  return out;
};
const cl01 = (v) => Math.max(0, Math.min(1, v));
function pocketDepth(x, y, k) {
  // hloubka kapsy v bodě (0 mimo); strmá zadní stěna, pozvolná přední, boční 4.5 mm, u zadních rohů široké schody (16 mm)
  const bevF = 10, bevR = 1.5, bevS = 4.5, bevN = 16, zone = 27, tr = 10;
  const tt = smooth((x - (k.x0 + zone)) / tr);
  const bs = bevN + (bevS - bevN) * tt;
  const f = Math.min(cl01((k.x1 - x) / bevF), cl01((x - k.x0) / bevR), cl01((y - k.y0) / bs), cl01((k.y1 - y) / bs));
  const ch = 8, cb = 6.4;
  const c1 = cl01(((k.x1 - x) + (k.y1 - y) - ch) / cb), c2 = cl01(((k.x1 - x) + (y - k.y0) - ch) / cb), c3 = cl01(((x - k.x0) + (k.y1 - y) - ch) / cb), c4 = cl01(((x - k.x0) + (y - k.y0) - ch) / cb);
  return LID.D * smooth(Math.min(f, c1, c2, c3, c4));
}
function slotDepth(x, y) {
  const s = LID.slot;
  const f = Math.min(cl01((s.x1 - x) / 3), cl01((x - s.x0) / 3), cl01((y - s.y0) / 4), cl01((s.y1 - y) / 4));
  const rib = 1 - smooth((Math.abs(y - (s.y0 + s.y1) / 2) - 3) / 2);    // středové žebro (zdvihnuté o 8 mm)
  return LID.D * smooth(f) - 8 * rib * smooth(f);
}
function lidTop(x, y, PK) {
  const L = LID, pl = L.plat;
  const dF = Math.max(0, x - pl.x1), dS = Math.max(0, Math.abs(y) - pl.y), dR = Math.max(0, pl.x0 - x);
  let z = P.zTop - 8 * smooth(dF / 24) - 6 * smooth(dS / 9) - 4 * smooth(dR / 2);
  let d = 0; for (const k of PK) { if (x < k.x0 - 1 || x > k.x1 + 1 || y < k.y0 - 1 || y > k.y1 + 1) continue; d = Math.max(d, pocketDepth(x, y, k)); }
  d = Math.max(d, slotDepth(x, y));
  return z - d;
}
function vicko() {
  const L = LID;
  const g = new Group('vicko', { pivot: [-183, 0, zc(P.zSeam + 1)], extras: { osa: [0, -1, 0], max_uhel: 110 } });
  const PK = pockets();
  // souřadnice mřížky (zlomy na hranách kapes, svazích a okrajích)
  const bx = [L.xR, L.xF, L.xFn, L.plat.x1, L.plat.x1 + 24, L.plat.x0, L.slot.x0, L.slot.x1, L.slot.x0 + 3, L.slot.x1 - 3];
  const by = [-L.yS, L.yS, -L.plat.y, L.plat.y, -L.plat.y + 9, L.plat.y - 9, L.slot.y0, L.slot.y1, L.slot.y0 + 4, L.slot.y1 - 4, -4, 4, -1, 1, ...L.notchY, L.notchY[0] - 10, L.notchY[1] + 10];
  for (const k of PK) { bx.push(k.x0, k.x0 + 1.5, k.x1 - 10, k.x1, k.x0 + 27, k.x0 + 37, k.x1 - 8, k.x0 + 8); by.push(k.y0, k.y0 + 4.5, k.y0 + 8, k.y0 + 16, k.y1 - 16, k.y1 - 8, k.y1 - 4.5, k.y1); }
  const xs = rozdel(L.xR, L.xF, 7, bx), ys = rozdel(-L.yS, L.yS, 7, by);
  const xmax = (y) => { const [a, b] = L.notchY; const dd = Math.max(a - y, y - b, 0); return L.xFn + (L.xF - L.xFn) * smooth(dd / 10); };
  const rcl = L.rc;
  const proj = (x, y) => {
    // zaoblení rohů obdélníku [xR..xF]×[-yS..yS] poloměrem rc (zlomy v rozích) + přední výřez
    const cx = (L.xR + L.xF) / 2, hx = (L.xF - L.xR) / 2, hy = L.yS;
    let X = Math.min(x, xmax(y)), Y = y;
    const qx = Math.abs(X - cx), qy = Math.abs(Y), ix = hx - rcl, iy = hy - rcl;
    if (qx > ix && qy > iy) { const dx = qx - ix, dy = qy - iy, d = Math.hypot(dx, dy); if (d > rcl) { const kk = rcl / d; X = cx + Math.sign(X - cx) * (ix + dx * kk); Y = Math.sign(Y) * (iy + dy * kk); } }
    return [X, Y];
  };
  const pl = deskaObrys('vicko_cira', 'vicko_deska', { xs, ys, top: (x, y) => lidTop(x, y, PK), t: () => L.t, proj });
  shiftZ(pl.part); g.add(pl.part);
  const loop = pl.loop.map(q => [q[0], q[1], q[2]]);
  const skirt = plastObvodu('vicko_cira', 'vicko_plast', loop, { zBottom: P.zSeam, tw: 2.2 });
  shiftZ(skirt); g.add(skirt);
  return g;
}

// ---------------------------------------------------------------------------------------------
// VNITŘEK: pevný střed a děliče
// ---------------------------------------------------------------------------------------------
function vnitrek() {
  const g = new Group('vnitrek');
  const I = P.inner;
  g.add(RB('cerna', 'pevny_stred', { x0: -62, x1: -59, y0: I.y0, y1: I.y1, z0: I.floor - 1, z1: 145, rc: 0, re: 0.5 }));
  return g;
}

export function build() {
  const root = new Group(SKU);
  root.addGroup(korpus());
  root.addGroup(celo());
  root.addGroup(vnitrek());
  root.addGroup(vicko());
  return root;
}
