// Čelní strana (+X): držadlo (červený rám + černý úchop), kroužek s oválným otvorem, dvě západky s třmenem – model 4932464082.
// Obrysy držadla a západek jsou z rektifikace c06 (rovina X=181, fotografie jen měřena); hodnoty y jsou opraveny o paralaxu
// (hloubka prvku vůči rovině měření), výšky z' = od nejnižšího bodu. Viz zdroje/4932464082_poznamky.md.
import { Group, Part, rrPoly, roundPoly, ccw, loftSolid, ext, extYZ, slab, rrShell, bx, zc, tube, cylinder, lathe, ZC } from './p4082_zaklad.mjs';

export const C = {
  yL: 150.2,                     // střed západky (±)
  xW: 181,                       // čelní rovina vany
};

// obrys (y_app, z) → (y, z'): paralaxa y -= sy, z' = z + zz
const mapH = (pts, sy = 3.0, zz = 56.9) => pts.map(([y, z]) => [y - sy, z + zz]);

function drzadlo(g) {
  const X0 = 179, X1 = 183.6;
  // pravý sloupek (y>0) – 3 hřebeny, spodní část s přechodem k úchopu
  const pr = mapH([[96.9, -44.5], [96.9, 29], [88.6, 29], [88.6, 4.2], [81.3, 4.2], [81.3, 29], [75.2, 29], [75.2, 4.2], [68.6, 4.2], [68.6, 29], [62.2, 29], [62.2, 3], [66, -5], [69, -12], [64, -17], [58, -19.5], [54, -24], [52, -37], [52, -44.5]]);
  const rr = [0, 1.4, 1.4, 0, 0, 1.4, 1.4, 0, 0, 1.4, 1.4, 3, 6, 6, 4, 3, 2, 0, 0];
  g.add(extYZ('cervena', 'drzadlo_sloupek_P', roundPoly(pr, rr, 3), X0, X1));
  // levý sloupek (y<0) – 2 hřebeny a rameno s čepem
  const pl = mapH([[-90.9, -44.5], [-90.9, 29], [-85.3, 29], [-85.3, 4.2], [-76.7, 4.2], [-76.7, 29], [-71.1, 29], [-71.1, 4.2], [-63.7, 4.2], [-63.7, 24], [-62, 29.3], [-46, 29.3], [-44.3, 24], [-44.3, 10], [-47, 3], [-50.3, 0], [-52.5, -5], [-52, -12], [-51.4, -20], [-51.4, -44.5]]);
  const rl = [0, 1.4, 1.4, 0, 0, 1.4, 1.4, 0, 0, 4, 4, 4, 4, 3, 5, 5, 4, 3, 0, 0];
  g.add(extYZ('cervena', 'drzadlo_sloupek_L', roundPoly(pl, rl, 3), X0, X1));
  g.add(cylinder('ocel', 'drzadlo_cep', 2.4, 0, 2.2, 14, [0, 0]).rot('y', 90).move(X1 - 0.2, -47.6 - 3.0 + 0.0, zc(19.7 + 56.9)));
  // spodní příčka (vyboulená dole směrem k čelu) a výstupek pod ní
  g.add(slab('cervena', 'drzadlo_pricka', { x0: 167, x1: 192.2, y0: -93.9, y1: 93.9, z0: 13.7, z1: 21.2, rs: 3, seg: 3, reT: 1.8, reB: 3.5, fs: 3 }));
  g.add(slab('cervena', 'drzadlo_vystupek', { x0: 183, x1: 190.5, y0: -3, y1: 35, z0: 11, z1: 14.5, rs: 1.5, seg: 2, reT: 0.4, reB: 1.2, fs: 2 }));
  // černý úchop – válcový profil s příčnými žebry
  g.add(slab('cerna_mat', 'drzadlo_uchop', { x0: 180.5, x1: 190.5, y0: -54.5, y1: 56, z0: 25.8, z1: 44.4, rs: 6, seg: 4, reT: 8, reB: 6, fs: 4 }));
  for (let k = 0; k < 18; k++) {
    const y0 = -51.5 + k * 5.9;
    g.add(slab('cerna_mat', 'drzadlo_vroubek', { x0: 180.5, x1: 191.4, y0, y1: y0 + 3.3, z0: 27.5, z1: 43, rs: 1.5, seg: 2, reT: 5, reB: 4, fs: 3 }));
  }
}

// eliptická trubka podél osy X (vnější a vnitřní elipsa v rovině YZ), u0..u1
function prstenecX(mat, name, { u0, u1, vc, zcen, rvO, rzO, rvI, rzI, n = 32 }) {
  const p = new Part(name, mat), rings = [];
  const ring = (rv, rz, u) => { const R = []; for (let i = 0; i < n; i++) { const a = 2 * Math.PI * i / n; R.push([u, vc + rv * Math.cos(a), zc(zcen) + rz * Math.sin(a)]); } return R; };
  const rs = [ring(rvO, rzO, u0), ring(rvO, rzO, u1 - 1), ring(rvO - 1.2, rzO - 1.2, u1), ring(rvI + 1, rzI + 1, u1), ring(rvI, rzI, u1 - 1.2), ring(rvI, rzI, u0)];
  const base = rs.map(r => r.map(q => p.addV(q[0], q[1], q[2])));
  for (let k = 0; k < rs.length - 1; k++) for (let i = 0; i < n; i++) { const j = (i + 1) % n; p.addQ(base[k][i], base[k][j], base[k + 1][j], base[k + 1][i]); }
  p.crease = 50;
  return p;
}

function zamek(g, s) {
  const yc = s * C.yL, yl = yc - 24.7;          // levý okraj těla západky
  const rel = ys => ys.map(y => y);              // (pomocná)
  // obrys těla s hřebenem (4 zuby) a zkosením vpravo dole; souřadnice relativně k levému okraji
  const zb = 25.8, zs = 67.5, zt = 80.8, zc0 = 49.8, W = 49.4;
  const tz = [[3.4, 8.3], [13.2, 18.3], [23.8, 28.7], [33.4, 38.3]];
  const pts = [[0, zb], [0, zs]];
  for (const [a, b] of tz) { pts.push([a, zs], [a, zt], [b, zt], [b, zs]); }
  pts.push([W, zs], [W, zc0], [W - 11.1, zb]);
  const rr = pts.map((p, i) => (p[1] === zt ? 1.3 : (i === 0 ? 3 : (i >= pts.length - 2 ? 3 : 0))));
  const poly = pts.map(([y, z]) => [yl + y, z]);
  g.add(extYZ('cervena', 'zamek_jazyk', roundPoly(poly, rr, 3), 174.4, 184.4));
  // žebra a značka na jazyku
  for (let r = 0; r < 3; r++) g.add(slab('cervena', 'zamek_zebro', { x0: 183.8, x1: 185.4, y0: yl + 7, y1: yl + 41, z0: 27.5 + r * 2.7, z1: 29.3 + r * 2.7, rs: 0.5, seg: 1, reT: 0.4, reB: 0.4, fs: 1 }));
  // ocelový třmen: dvě nohy + horní příčka
  for (const sv of [-1, 1]) {
    const vv = yc + sv * 27.9;
    g.add(tube('ocel', 'zamek_trmen', [[181, vv, zc(52)], [186.5, vv, zc(56)], [188.6, vv, zc(63)], [188.6, vv, zc(103)], [187.6, vv, zc(107)]], 1.45, 8));
  }
  g.add(tube('ocel', 'zamek_trmen_horni', [[187.6, yc - 27.9, zc(107)], [187.6, yc + 27.9, zc(107)]], 1.45, 8));
}

export function celo() {
  const g = new Group('celo');
  drzadlo(g);
  g.add(prstenecX('cervena', 'oval_kruzek', { u0: 179.5, u1: 188.5, vc: 17, zcen: 65.5, rvO: 17.2, rzO: 19, rvI: 10.6, rzI: 10.8 }));
  // černý okruží (boss) kolem kroužku
  g.add(slab('cerna_mat', 'oval_okruzi', { x0: 180.4, x1: 183, y0: -5, y1: 39, z0: 41, z1: 87, rs: 13, seg: 4, reT: 1, reB: 1, fs: 2 }));
  zamek(g, 1); zamek(g, -1);
  return g;
}
