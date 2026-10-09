// Čelní strana (+X) hlubokého organizéru 4932478625: reliéf čelní stěny (okno držadla, žebra, kapsy západek), držadlo, kroužek,
// dvě západky s třmenem (třmeny jako samostatné uzly), klínové nožičky. Rozměry z rektifikace c13 (viz zdroje/4932478625_poznamky.md).
import { Group, Part, roundPoly, ccw, extYZ, slab, bx, zc, tube, cylinder, ZC } from './p8625_zaklad.mjs';
import { reliefX, rozdel, smooth, prismYZ } from './pomocne_8625.mjs';
import { RAM, JAZYK, ZAMEK_L, ZAMEK_P } from './p8625_data.mjs';

export const F = {
  xf: 183.5,                    // rovina čelní stěny (horní okraj vany pod víkem, c04: X = 183)
  zB: 26.5,                     // spodní hrana čelní stěny (silueta c13)
  zSeam: 157.5,                 // švík s víkem
  win: { hy: 98.0, z0: 36, z1: 121, xBack: 154 },                 // okno držadla
  blade: { y0: 98.0, y1: 118.6, z1: 115, h: 1.5 },                // žebra mezi oknem a kapsou
  pocket: { y0: 118.6, y1: 186.6, z0: 51, z1: 157.5, zr: 88, depth: 13.5 },    // kapsy západek (dno x = 170)
  latchY: 150.7,
};
const cl = (v) => Math.max(0, Math.min(1, v));
const soft = (d, w) => smooth(d / w + 0.5);

// hloubková funkce čelní stěny: x = x(y, z')
export function frontX(y, z) {
  const ay = Math.abs(y), q = F.pocket, b = F.blade, w = F.win;
  let x = F.xf;
  const mb = soft(Math.min(ay - b.y0, b.y1 - ay, b.z1 - z), 1.2);
  x += b.h * mb * cl((z - 20) / 4);
  const ramp = cl((z - q.z0) / (q.zr - q.z0));
  const inset = 10 * (1 - ramp);
  const mp = soft(Math.min(ay - q.y0 - inset, q.y1 - ay - inset, q.z1 - z, z - q.z0), 1.2);
  x -= q.depth * ramp * mp;
  const mw = soft(Math.min(w.hy - ay, w.z1 - z, z - w.z0), 1.0);
  x -= (F.xf - w.xBack) * mw;
  const mt = soft(Math.min(48 - ay, 136 - z, z - 118), 1.0);
  x -= 14 * mt;
  return Math.max(x, 154);
}

function reliefCela(g) {
  const yb = [98, 118.6, 186.6, 48], zb = [36, 51, 88, 115, 118, 121, 136];
  const zly = [], zlz = [...zb, 20, 24, 26.5, F.zSeam];
  for (const v of yb) zly.push(v, -v, v - 1.5, v + 1.5, -v - 1.5, -v + 1.5, v - 10, -v + 10, v + 10, -v - 10);
  const rel = reliefX('cerna_mat', 'celo_relief', { y0: -226, y1: 226, z0: F.zB, z1: F.zSeam - 0.4, hy: 3, hz: 3, zlomyY: zly, zlomyZ: zlz, fn: frontX, xb: 151.3 });
  rel.move(0, 0, -ZC); g.add(rel);
}

// klínové nožičky po stranách okna: vnitřní hrana svislá, vnější zešikmená (c13)
function nozicky(g) {
  for (const s of [-1, 1]) {
    const a = 98.0, b = 120.5;
    const poly = s > 0 ? [[a, 31], [b, 31], [b - 7.5, 0.5], [a, 0.5]] : [[-a, 31], [-a, 0.5], [-b + 7.5, 0.5], [-b, 31]];
    const p = prismYZ('cerna_mat', 'klin', poly.map(([y, z]) => [y, z - ZC]), 160, F.xf - 1);
    g.add(p);
  }
}

function drzadlo(g) {
  // červený rám (U, hřebeny) – obrys z rektifikace; tloušťka v X 172,5 … 182,5
  g.add(extYZ('cervena', 'drzadlo_ram', roundPoly(RAM, new Array(RAM.length).fill(0.6), 2), 172.5, 182.5));
  // šedý gumový úchop s příčnými žebry
  g.add(slab('seda', 'drzadlo_uchop', { x0: 174, x1: 186.5, y0: -55.8, y1: 51.7, z0: 47.5, z1: 72.3, rs: 5, seg: 3, reT: 7, reB: 4, fs: 4 }));
  for (let k = 0; k < 19; k++) {
    const y0 = -52.5 + k * 5.4;
    g.add(slab('cerna_mat', 'drzadlo_vroubek', { x0: 174.5, x1: 187.4, y0, y1: y0 + 2.6, z0: 49.5, z1: 70.5, rs: 1, seg: 1, reT: 5, reB: 3, fs: 3 }));
  }
  // čep (ocel) na levém rameni
  g.add(cylinder('ocel', 'drzadlo_cep', 2.4, 0, 2.4, 14, [0, 0]).rot('y', 90).move(182.2, -53.3, zc(107.3)));
  // černé zámkové prsty v zářezech ramen (4 ks)
  for (const yc of [-85.5, -71.6, 67.8, 82.1]) g.add(bx('cerna_mat', 'drzadlo_prst', 171, 181.5, yc - 2.2, yc + 2.2, 90, 148));
  // spodní červený jazýček (pojistka) a žebrovaný pás nad ním
  g.add(extYZ('cervena', 'dolni_jazyk', roundPoly([[-6.7, 14.5], [41.8, 14.5], [41.8, 33], [-6.7, 33]], [1, 1, 0, 0], 2), 176, 183.2));
  g.add(slab('cerna_mat', 'pas_zebra', { x0: 182.2, x1: 183.9, y0: -12, y1: 38, z0: 28.5, z1: 44, rs: 0.5, seg: 1, reT: 0.4, reB: 0.4, fs: 1 }));
  for (let k = 0; k < 9; k++) g.add(bx('cerna_mat', 'pas_zebro', 182.0, 184.6, -11 + k * 5.5, -9 + k * 5.5, 29, 43));
}

// kroužek s oválným otvorem: eliptický prstenec podél osy X, černé okruží
function prstenecX(mat, name, { u0, u1, vc, zcen, rvO, rzO, rvI, rzI, tilt = 0, n = 36 }) {
  const p = new Part(name, mat), rings = [];
  const ring = (rv, rz, u) => {
    const R = [], c = Math.cos(tilt * Math.PI / 180), s = Math.sin(tilt * Math.PI / 180);
    for (let i = 0; i < n; i++) { const a = 2 * Math.PI * i / n; const yy = rv * Math.cos(a), zz = rz * Math.sin(a); R.push([u, vc + yy * c - zz * s, zc(zcen) + yy * s + zz * c]); }
    return R;
  };
  const rs = [ring(rvO, rzO, u0), ring(rvO, rzO, u1 - 1.2), ring(rvO - 1.2, rzO - 1.2, u1), ring(rvI + 1, rzI + 1, u1), ring(rvI, rzI, u1 - 1.4), ring(rvI, rzI, u0)];
  const base = rs.map(r => r.map(q => p.addV(q[0], q[1], q[2])));
  for (let k = 0; k < rs.length - 1; k++) for (let i = 0; i < n; i++) { const j = (i + 1) % n; p.addQ(base[k][i], base[k][j], base[k + 1][j], base[k + 1][i]); }
  p.crease = 50;
  return p;
}
function kruzek(g) {
  g.add(prstenecX('cervena', 'oval_kruzek', { u0: 154, u1: 158.5, vc: 0, zcen: 82.8, rvO: 17.5, rzO: 19.8, rvI: 9.6, rzI: 11.2, tilt: 8 }));
  g.add(slab('cerna_mat', 'oval_okruzi', { x0: 152.6, x1: 155.6, y0: -21.5, y1: 21.5, z0: 62, z1: 104, rs: 13, seg: 4, reT: 1, reB: 1, fs: 2 }));
  // deska s drážkami nad kroužkem (výklenek v čelní stěně, svislá žebra)
  for (let k = 0; k < 6; k++) g.add(bx('cerna_mat', 'zebra_desky', 154, 156.5, -22 + k * 8.6, -20 + k * 8.6, 108, 133));
}

// západka: červený jazyk (obrys z rektifikace, rovina X = 176), černý rámeček (kapsa), třmen = samostatný uzel
function zamek(g, s) {
  const yc = s * F.latchY;
  const poly = s > 0 ? ZAMEK_P : ZAMEK_L;
  g.add(extYZ('cervena', s > 0 ? 'zamek_jazyk_P' : 'zamek_jazyk_L', roundPoly(poly, new Array(poly.length).fill(0.5), 2), 171.5, 176.2));
  // zvýšený střední panel (logo) a tři žebra dole
  g.add(slab('cervena', 'zamek_panel', { x0: 176, x1: 177.8, y0: yc - 20, y1: yc + 20, z0: 91, z1: 118, rs: 1.5, seg: 2, reT: 0.5, reB: 0.3, fs: 1 }));
  for (let r = 0; r < 3; r++) g.add(slab('cervena', 'zamek_zebro', { x0: 176, x1: 177.4, y0: yc - 19, y1: yc + 19, z0: 84.8 + r * 2.8, z1: 86.4 + r * 2.8, rs: 0.4, seg: 1, reT: 0.4, reB: 0.2, fs: 1 }));
  // černý štít nad zuby a boční lišty
  g.add(slab('cerna_mat', 'zamek_stit', { x0: 168, x1: 184, y0: yc - 31, y1: yc + 31, z0: 140.5, z1: 154, rs: 2, seg: 2, reT: 1, reB: 0.6, fs: 2 }));
  // čirý držák na víku s třmenem
  g.add(slab('cira_tm', 'zamek_drzak', { x0: 176, x1: 191, y0: yc - 27.5, y1: yc + 27.5, z0: 152, z1: 168, rs: 3.5, seg: 3, reT: 2.5, reB: 1.5, fs: 3 }));
  const c = yc, yL = c - 28.9, yR = c + 28.9;
  const tg = new Group(s > 0 ? 'trmen_P' : 'trmen_L', { pivot: [177.5, c, zc(114)], extras: { osa: [0, 1, 0], max_uhel: 170 } });
  tg.add(tube('ocel', 'zamek_trmen', [
    [176.6, yL + 3.5, zc(113.2)], [178.2, yL, zc(114.6)], [183.5, yL, zc(122)], [187.5, yL, zc(140)], [190.2, yL, zc(163)], [190.6, yL + 1.8, zc(166)], [190.6, yL + 5, zc(167.4)],
    [190.6, yR - 5, zc(167.4)], [190.6, yR - 1.8, zc(166)], [190.2, yR, zc(163)], [187.5, yR, zc(140)], [183.5, yR, zc(122)], [178.2, yR, zc(114.6)], [176.6, yR - 3.5, zc(113.2)]], 1.75, 8));
  return tg;
}

export function celo() {
  const g = new Group('celo');
  reliefCela(g); nozicky(g); drzadlo(g); kruzek(g);
  g.addGroup(zamek(g, 1)); g.addGroup(zamek(g, -1));
  return g;
}
