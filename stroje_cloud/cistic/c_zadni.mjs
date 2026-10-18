// Zadní část: černá zadní stěna (skříň) mezi svislými sloupky, trubková rukojeť (U) ze sloupků, přípojky, navinutý přívodní kabel se zástrčkou.
import { Part, Group, roundedBox, box, tube, cylX, cylY, cylinder, filletPath, K, Y } from './c_zaklad.mjs';

const KABEL_R = 5;

export function zadni() {
  const g = new Group('zadni_cast');
  const { hwBox, yBox0, yBox, zBox0, zBoxT, xp, yp, rp, Yh, zh } = K;
  // zadní skříň (černý plech): od zadní stěny krytu po zadní rovinu
  g.add(roundedBox('cerna', 'zadni_skrin', { x0: -hwBox, x1: hwBox, y0: yBox0 - 2, y1: yBox, z0: zBox0, z1: zBoxT, rc: 8, re: 5, seg: 3, fs: 3 }));
  // světlejší víko skříně (zašpiněný plech), lem po obvodu
  g.add(roundedBox('nerez', 'zadni_viko', { x0: -hwBox + 4, x1: hwBox - 4, y0: yBox0 + 2, y1: yBox - 4, z0: zBoxT - 0.5, z1: zBoxT + 3.5, rc: 5, re: 1.5, seg: 2, fs: 2 }));
  // víko skříně: tmavý blok (úchyt) na horní části zadní stěny
  g.add(roundedBox('cerna_mat', 'zadni_blok', { x0: -165, x1: -45, y0: yBox - 52, y1: yBox - 8, z0: zBoxT, z1: zBoxT + 26, rc: 4, re: 3, seg: 2, fs: 2 }));
  // pouzdro zásuvky/vypínače (tmavé) + kulatý poklop
  g.add(roundedBox('cerna_mat', 'zadni_pouzdro', { x0: -192, x1: -86, y0: yBox, y1: yBox + 7, z0: 228, z1: 370, rc: 6, re: 1.5, seg: 2, fs: 2 }));
  g.add(cylY('seda', 'zadni_poklop', 22, yBox + 5, yBox + 16, -148, 338, 24));
  g.add(box('plocha_zluta', 'zadni_ploska', -150, -78, yBox, yBox + 0.8, 404, 478));
  // přípojky (mosaz): dvě trubkové vsuvky se šestihranem
  for (const [x, z] of [[131, 391], [34, 386]]) {
    g.add(cylY('mosaz', 'prip_trubka', 8, yBox, yBox + 26, x, z, 14));
    g.add(cylY('mosaz', 'prip_matice', 11.5, yBox + 2, yBox + 10, x, z, 6));
  }
  // rukojeť + sloupky: jedna trubka (U): noha E dole → nahoru → šikmo dozadu → příčka → noha W dolů
  const cesta = filletPath([[xp, yp, 112], [xp, yp, 560], [xp, Yh, zh], [-xp, Yh, zh], [-xp, yp, 560], [-xp, yp, 112]], [0, 80, 58, 58, 80, 0], 8);
  g.add(tube('cerna', 'rukojet_u', cesta, rp, 16, true));
  // spodní příčka rámu pod sloupky + desky koleček
  g.add(box('cerna', 'zadni_pricka', -xp - 14, xp + 14, yp - 18, yp + 18, 112, 124));
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
  g.add(tube('cerna_mat', 'kabel_smycky', smyc(566, 536, 3, xp + 24, yBox0 + 4, yp + 24, 22), KABEL_R, 8, false));
  // kabel: 4 prameny prověšené mezi sloupky těsně pod příčkou rukojeti (jako v c11/c14), volný konec se zástrčkou
  for (let k = 0; k < 5; k++) {
    const yy = Yh - 4 + (k - 2) * 9.5, zz = zh - 22 - k * 3, pts = [];
    for (let i = 0; i <= 24; i++) { const u = i / 24, x = (xp + 8) * (1 - 2 * u), sag = (30 + k * 7) * (1 - (2 * u - 1) ** 2); pts.push([x, yy + 5 * Math.sin(u * Math.PI), zz - sag]); }
    g.add(tube('cerna_mat', 'kabel_pramen', pts, KABEL_R, 8, true));
  }
  g.add(tube('cerna_mat', 'kabel_vol', filletPath([[-150, Yh + 6, 600], [-200, yp + 14, 560], [-244, yp - 14, 545], [-246, yp - 14, 522]], 30, 6), KABEL_R, 8, true));
  g.add(roundedBox('cerna', 'zastrcka', { x0: -258, x1: -234, y0: yp - 24, y1: yp - 4, z0: 478, z1: 524, rc: 4, re: 2, seg: 2, fs: 2 }));
  for (const dx of [-8, 8]) g.add(cylinder('pozink', 'kolik', 2.2, 468, 478, 8, [-246 + dx, yp - 14]));
  return g;
}
