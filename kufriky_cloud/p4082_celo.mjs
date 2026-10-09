// Čelní strana (+X): držadlo (červený rám + černý úchop), kroužek s oválným otvorem, dvě západky s třmenem – model 4932464082.
// Obrysy držadla a západek jsou z rektifikace c06 (rovina X=181, fotografie jen měřena); hodnoty y jsou opraveny o paralaxu
// (hloubka prvku vůči rovině měření), výšky z' = od nejnižšího bodu. Viz zdroje/4932464082_poznamky.md.
import { Group, Part, rrPoly, roundPoly, ccw, loftSolid, ext, extYZ, slab, rrShell, bx, zc, tube, cylinder, lathe, ZC } from './p4082_zaklad.mjs';

export const C = {
  yL: 148.5,                     // střed západky (±)
  xW: 181,                       // čelní rovina vany
};

// obrys (y_app, z) → (y, z'): paralaxa y -= sy, z' = z + zz
const mapH = (pts, sy = 3.0, zz = 54.9) => pts.map(([y, z]) => [(y - sy) * 0.965 + 0.8, z + zz]);   // paralaxa + korekce podle překryvu s fotografií c06/c01
const YH = y => y * 0.965 + 0.8;

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
  g.add(cylinder('ocel', 'drzadlo_cep', 2.4, 0, 2.2, 14, [0, 0]).rot('y', 90).move(X1 - 0.2, (-47.6 - 3.0) * 0.965 + 0.8, zc(19.7 + 54.9)));
  // spodní příčka (vyboulená dole směrem k čelu) a výstupek pod ní
  g.add(slab('cervena', 'drzadlo_pricka', { x0: 167, x1: 192.2, y0: YH(-93.9), y1: YH(93.9), z0: 14.3, z1: 21.2, rs: 3, seg: 3, reT: 1.8, reB: 3.5, fs: 3 }));
  g.add(slab('cervena', 'drzadlo_vystupek', { x0: 183, x1: 190.5, y0: YH(-3), y1: YH(35), z0: 11.5, z1: 15, rs: 1.5, seg: 2, reT: 0.4, reB: 1.2, fs: 2 }));
  // černý úchop – válcový profil s příčnými žebry
  g.add(slab('cerna_mat', 'drzadlo_uchop', { x0: 180.5, x1: 190.5, y0: YH(-54.5), y1: YH(56), z0: 25.8, z1: 44.4, rs: 6, seg: 4, reT: 8, reB: 6, fs: 4 }));
  for (let k = 0; k < 18; k++) {
    const y0 = YH(-51.5 + k * 5.9);
    g.add(slab('cerna_mat', 'drzadlo_vroubek', { x0: 180.5, x1: 191.4, y0, y1: y0 + 3.2, z0: 27.5, z1: 43, rs: 1.5, seg: 2, reT: 5, reB: 4, fs: 3 }));
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
  const yc = s * C.yL, W = 52, yl = yc - W / 2;
  // rozměry z překryvu s fotografií (c06/c01): tělo z' 27,4..62,6, zuby do 79,3; šířka ~47 mm; pravý okraj se šikmo zužuje ke třmenu
  const zb = 26.6, zs = 64.2, zt = 80.2;
  const body = roundPoly([[0, zb], [W - 9.5, zb], [W - 2.8, zb + 14], [W, zb + 34], [W, zs], [0, zs]].map(([y, z]) => [yl + y, z]), [5.5, 5, 3, 3, 1, 1], 3);
  g.add(extYZ('cervena', 'zamek_telo', body, 176.5, 184.4));
  // zuby (4 ks, kónické, tenčí než tělo)
  for (const [a, b] of [[3.8, 8.8], [14.0, 19.0], [24.2, 29.2], [34.4, 39.4]]) {
    const t = [[a, zs - 1], [a + 0.25, zt - 1.6], [a + 1.0, zt], [b - 1.0, zt], [b - 0.25, zt - 1.6], [b, zs - 1]].map(([y, z]) => [yl + y, z]);
    g.add(extYZ('cervena', 'zamek_zub', roundPoly(t, [0, 0, 1.4, 1.4, 0, 0], 3), 180.2, 183.4));
  }
  // vyvýšený střední panel (zdvih 2 mm) a tři žebra v dolní části jazyka
  const pl = [[3.2, zb + 9], [W - 4.5, zb + 9], [W - 4.5, zs - 2.5], [3.2, zs - 2.5]].map(([y, z]) => [yl + y, z]);
  g.add(extYZ('cervena', 'zamek_panel', roundPoly(pl, [2, 2, 2, 2], 3), 184.4, 186.4));
  for (let r = 0; r < 3; r++) g.add(slab('cervena', 'zamek_zebro', { x0: 184.2, x1: 185.8, y0: yl + 3.5, y1: yl + W - 12, z0: zb + 1.4 + r * 2.8, z1: zb + 2.9 + r * 2.8, rs: 0.6, seg: 1, reT: 0.5, reB: 0.3, fs: 1 }));
  for (const sv of [-1, 1]) g.add(slab('cervena', 'zamek_lista', { x0: 184.2, x1: 186.6, y0: sv < 0 ? yl + 3.2 : yl + W - 7.2, y1: sv < 0 ? yl + 5.2 : yl + W - 5.2, z0: zb + 8, z1: zs - 2.5, rs: 0.8, seg: 1, reT: 0.6, reB: 0.3, fs: 1 }));
  // černý rámeček (kapsa): štít nad zuby, dvě boční lišty a spodní lišta
  g.add(slab('cerna_mat', 'zamek_ramecek_hore', { x0: 181, x1: 187.4, y0: yc - 33, y1: yc + 33, z0: 81, z1: 93.5, rs: 2.5, seg: 2, reT: 1.5, reB: 0.8, fs: 2 }));
  for (const sv of [-1, 1]) g.add(slab('cerna_mat', 'zamek_ramecek_bok', { x0: 181, x1: 186.6, y0: sv < 0 ? yc - 33 : yc + 29.3, y1: sv < 0 ? yc - 29.3 : yc + 33, z0: 24, z1: 93.5, rs: 1.2, seg: 2, reT: 1, reB: 0.8, fs: 2 }));
  g.add(slab('cerna_mat', 'zamek_ramecek_dole', { x0: 181, x1: 186.6, y0: yc - 33, y1: yc + 33, z0: 23, z1: 27, rs: 1.2, seg: 2, reT: 0.8, reB: 0.8, fs: 2 }));
  // ocelový třmen: jeden drát (noha – zaoblená horní příčka – noha), nohy zahnuté dovnitř dole do čepů jazyka.
  // Třmen je samostatná skupina (otočná kolem osy čepů; v otevřeném stavu visí dolů – pose trmen_P / trmen_L = 165°).
  const yL = yc - 28.3, yR = yc + 28.3;
  const tg = new Group(s > 0 ? 'trmen_P' : 'trmen_L', { pivot: [183.6, yc, zc(54)], extras: { osa: [0, 1, 0], max_uhel: 170 } });
  tg.add(tube('ocel', 'zamek_trmen', [
    [181.5, yL + 2.2, zc(51.5)], [183.6, yL + 0.6, zc(54)], [187, yL, zc(60)], [188.6, yL, zc(66)], [188.6, yL, zc(100)], [188.2, yL + 1.4, zc(104.6)], [187.6, yL + 4.2, zc(106.8)],
    [187.6, yR - 4.2, zc(106.8)], [188.2, yR - 1.4, zc(104.6)], [188.6, yR, zc(100)], [188.6, yR, zc(66)], [187, yR, zc(60)], [183.6, yR - 0.6, zc(54)], [181.5, yR - 2.2, zc(51.5)]], 1.65, 8));
  return tg;
}

export function celo() {
  const g = new Group('celo');
  drzadlo(g);
  g.add(prstenecX('cervena', 'oval_kruzek', { u0: 179.5, u1: 188.5, vc: 16, zcen: 65.5, rvO: 15.6, rzO: 18.6, rvI: 9.6, rzI: 10.6 }));
  // černý okruží (boss) kolem kroužku
  g.add(slab('cerna_mat', 'oval_okruzi', { x0: 180.4, x1: 183, y0: -5, y1: 39, z0: 41, z1: 87, rs: 13, seg: 4, reT: 1, reB: 1, fs: 2 }));
  g.addGroup(zamek(g, 1)); g.addGroup(zamek(g, -1));
  return g;
}
