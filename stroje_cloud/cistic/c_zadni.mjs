// Zadní část: černá zadní stěna (skříň) mezi svislými sloupky, trubková rukojeť (U) ze sloupků, přípojky, navinutý přívodní kabel se zástrčkou.
import { Part, Group, roundedBox, box, tube, cylX, cylY, cylinder, filletPath, K } from './c_zaklad.mjs';

const KABEL_R = 4.5;

export function zadni() {
  const g = new Group('zadni_cast');
  const { hwBox, yBox0, yBox, zBox0, zBoxT, xp, yp, rp, Yh, zh } = K;
  // zadní skříň (černý plech): od zadní stěny krytu po zadní rovinu
  g.add(roundedBox('cerna', 'zadni_skrin', { x0: -hwBox, x1: hwBox, y0: yBox0 - 2, y1: yBox, z0: zBox0, z1: zBoxT, rc: 8, re: 5, seg: 3, fs: 3 }));
  // víko skříně: tmavý blok (úchyt) na horní části zadní stěny
  g.add(roundedBox('cerna_mat', 'zadni_blok', { x0: -109, x1: -36, y0: yBox, y1: yBox + 18, z0: 500, z1: 553, rc: 3, re: 2, seg: 2, fs: 2 }));
  // pouzdro zásuvky/vypínače (tmavé) + kulatý poklop
  g.add(roundedBox('cerna_mat', 'zadni_pouzdro', { x0: -192, x1: -86, y0: yBox, y1: yBox + 7, z0: 228, z1: 370, rc: 6, re: 1.5, seg: 2, fs: 2 }));
  g.add(cylY('seda', 'zadni_poklop', 22, yBox + 5, yBox + 16, -148, 338, 24));
  g.add(box('plocha_zluta', 'zadni_ploska', -150, -78, yBox, yBox + 0.8, 404, 478));
  // přípojky (mosaz): dvě trubkové vsuvky se šestihranem
  for (const [x, z] of [[131, 391], [34, 386]]) {
    g.add(cylY('mosaz', 'prip_trubka', 8, yBox, yBox + 34, x, z, 14));
    g.add(cylY('mosaz', 'prip_matice', 11.5, yBox + 2, yBox + 10, x, z, 6));
  }
  // rukojeť + sloupky: jedna trubka (U): noha E dole → nahoru → šikmo dozadu → příčka → noha W dolů
  const cesta = filletPath([[xp, yp, 112], [xp, yp, 500], [xp, Yh, zh], [-xp, Yh, zh], [-xp, yp, 500], [-xp, yp, 112]], [0, 120, 48, 48, 120, 0], 8);
  g.add(tube('cerna', 'rukojet_u', cesta, rp, 16, true));
  // spodní příčka rámu pod sloupky + desky koleček
  g.add(box('cerna', 'zadni_pricka', -xp - 14, xp + 14, 232, 268, 108, 122));
  // kabel: 3 závity kolem zadní části (zaoblený obdélník), závity kolem příčky rukojeti, zástrčka
  const smyc = (z0, z1, nTurn, hx, y0, y1, rc) => {
    const per = []; const N = 14 * nTurn;
    const rr = rc, sx = hx, loop = [];
    // obvod zaobleného obdélníku [−sx,sx] × [y0,y1] jako polygon s rohy
    const corner = (cx, cy, a0) => { const a = []; for (let i = 0; i <= 5; i++) { const t = (a0 + 90 * i / 5) * Math.PI / 180; a.push([cx + rr * Math.cos(t), cy + rr * Math.sin(t)]); } return a; };
    loop.push(...corner(sx - rr, y1 - rr, 0), ...corner(-sx + rr, y1 - rr, 90), ...corner(-sx + rr, y0 + rr, 180), ...corner(sx - rr, y0 + rr, 270));
    const M = loop.length, tot = M * nTurn;
    for (let i = 0; i <= tot; i++) { const q = loop[i % M], u = i / tot; per.push([q[0], q[1], z0 + (z1 - z0) * u]); }
    void N; return per;
  };
  g.add(tube('cerna_mat', 'kabel_smycky', smyc(566, 536, 3, xp + 24, 216, yp + 24, 22), KABEL_R, 8, false));
  // kabel přehozený přes příčku rukojeti: 5 smyček (Ω) visících dozadu; nejzazší bod kabelu = hranice obálky (Y = +325)
  const yMax = 325 - KABEL_R + 1.15, sr = rp + KABEL_R + 0.3;
  [-135, -70, -5, 60, 125].forEach((x, i) => {
    const sag = (i % 2 ? 0 : 6);
    g.add(tube('cerna_mat', 'kabel_smycka', filletPath([[x, Yh - sr - 6, zh - 8], [x, Yh - 2, zh + sr], [x, Yh + sr + 1, zh + 4], [x, yMax - 8 + sag * 0.5, zh - 50], [x, yMax - sag * 0.3, zh - 110], [x + 6, yMax - 14, 560], [x + 10, 292, 520], [x + 6, 262, 505]], 26, 6), KABEL_R, 8, true));
  });
  // volný konec kabelu se zástrčkou (visí u sloupku W vpředu)
  g.add(tube('cerna_mat', 'kabel_vol', filletPath([[-150, Yh + sr, zh - sr], [-200, 272, 520], [-244, 236, 540], [-246, 236, 520]], 30, 6), KABEL_R, 8, true));
  g.add(roundedBox('cerna', 'zastrcka', { x0: -258, x1: -234, y0: 226, y1: 246, z0: 478, z1: 524, rc: 4, re: 2, seg: 2, fs: 2 }));
  for (const dx of [-8, 8]) g.add(cylinder('pozink', 'kolik', 2.2, 468, 478, 8, [-246 + dx, 236]));
  return g;
}
