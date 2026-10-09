// Víko (čiré, lehce zakouřené): rám, desky s kapsami nad nádobami, čelní lem se sponami, články pantu – model 4932464082.
// Víko je samostatná skupina s pivotem na ose pantu (osa -Y: kladný úhel víko otevírá). Díly se staví v souřadnicích zavřeného modelu.
import { Group, Part, rrPoly, polyMirrorY, ccw, loftSolid, ext, slab, rrShell, rrFrame, ringSolid, bx, zc, tube, cylinder, ZC } from './p4082_zaklad.mjs';
import { seznamNadob, N } from './p4082_nadoby.mjs';
import { kapsa } from './p4082_kapsy.mjs';

export const V = {
  x0: -163, x1: 188.5, y: 244.5,           // obrys víka (deska)
  zSk: 109, zTop: 117, tPl: 2.5,           // spodek obvodové sukně, horní plocha, tloušťka desky
  rF: 30, rR: 14,
  inner: { x0: -158, x1: 146, y: 229 },     // obdélník, uvnitř kterého se deska skládá z buněk (kolem kapes)
  pivot: [-175.5, 0, 97],
  zPocket: 105.5, dPocket: 11,
  ins: 2.5,                                 // okraj kapsy vzhledem k nádobě
};

function kapsy() {
  return seznamNadob().map(n => ({ x0: n.x0 + V.ins, x1: n.x1 - V.ins, y0: n.y0 + V.ins, y1: n.y1 - V.ins, big: n.velka }));
}

export function vicko() {
  const [px, py, pz] = V.pivot;
  const g = new Group('vicko', { pivot: [px, py, zc(pz)], extras: { osa: [0, -1, 0], max_uhel: 110 } });
  const plot = rrPoly(V.x0, V.x1, -V.y, V.y, [V.rF, V.rR, V.rR, V.rF], 6);
  // --- obvodová sukně
  g.add(rrShell('vicko_cira', 'vicko_sukne', { x0: V.x0, x1: V.x1, y0: -V.y, y1: V.y, rs: [V.rF, V.rR, V.rR, V.rF], seg: 6, profile: [[V.zSk, 0], [V.zTop - 1.2, 0], [V.zTop, 1.2], [V.zTop, 2.6], [V.zSk, 2.6]], closed: true }));
  // --- deska kolem kapes: obvodový prstenec + buňky mezi kapsami
  const iN = V.inner, inRect = rrPoly(iN.x0, iN.x1, -iN.y, iN.y, 0.01, 6);
  const outIn = rrPoly(V.x0 + 1.2, V.x1 - 1.2, -V.y + 1.2, V.y - 1.2, [V.rF - 1.2, V.rR - 1.2, V.rR - 1.2, V.rF - 1.2], 6);
  g.add(ringSolid('vicko_cira', 'vicko_deska_rám', outIn, inRect, V.zTop - V.tPl, V.zTop, { innerWall: false }));
  const P = kapsy();
  const strip = { x0: -143.3, x1: 131.7, y0: -22, y1: 22 };
  const holes = [...P, strip];
  const xs = new Set([iN.x0, iN.x1]), ys = new Set([-iN.y, iN.y]);
  for (const h of holes) { xs.add(h.x0); xs.add(h.x1); ys.add(h.y0); ys.add(h.y1); }
  const XS = [...xs].sort((a, b) => a - b), YS = [...ys].sort((a, b) => a - b);
  const isHole = (i, j) => { if (i < 0 || j < 0 || i >= XS.length - 1 || j >= YS.length - 1) return false; const cx = (XS[i] + XS[i + 1]) / 2, cy = (YS[j] + YS[j + 1]) / 2; return holes.some(h => cx > h.x0 && cx < h.x1 && cy > h.y0 && cy < h.y1); };
  // deska = buňky mimo kapsy; vykreslí se jen horní a spodní plocha a boční stěny u otvorů (žádné vnitřní plochy → žádné švy)
  const plate = new Part('vicko_deska', 'vicko_cira'); plate.crease = 30;
  const zt = zc(V.zTop), zb = zc(V.zTop - V.tPl);
  for (let i = 0; i < XS.length - 1; i++) for (let j = 0; j < YS.length - 1; j++) {
    if (isHole(i, j)) continue;
    const x0 = XS[i], x1 = XS[i + 1], y0 = YS[j], y1 = YS[j + 1];
    const q = (a, b, c, d) => plate.addQ(plate.addV(...a), plate.addV(...b), plate.addV(...c), plate.addV(...d));
    q([x0, y0, zt], [x1, y0, zt], [x1, y1, zt], [x0, y1, zt]);             // horní
    q([x0, y0, zb], [x0, y1, zb], [x1, y1, zb], [x1, y0, zb]);             // spodní
    if (isHole(i - 1, j)) q([x0, y1, zb], [x0, y0, zb], [x0, y0, zt], [x0, y1, zt]);     // stěna k otvoru v -x
    if (isHole(i + 1, j)) q([x1, y0, zb], [x1, y1, zb], [x1, y1, zt], [x1, y0, zt]);     // +x
    if (isHole(i, j - 1)) q([x0, y0, zb], [x1, y0, zb], [x1, y0, zt], [x0, y0, zt]);     // -y
    if (isHole(i, j + 1)) q([x1, y1, zb], [x0, y1, zb], [x0, y1, zt], [x1, y1, zt]);     // +y
  }
  g.add(plate);
  // zkosené rohy kapes (přední rohy) – trojúhelníky desky
  const ch = 9;
  for (const h of P) for (const sy of [0, 1]) {
    const y = sy ? h.y1 : h.y0, dy = sy ? -1 : 1;
    g.add(ext('vicko_cira', 'vicko_roh', ccw([[h.x1, y], [h.x1 - ch, y], [h.x1, y + dy * ch]]), V.zTop - V.tPl, V.zTop));
  }
  // --- kapsy (tenkostěnné misky s šikmou stěnou, uši, šestiúhelníkové dno) nad každou nádobou + pruh uprostřed
  for (const h of P) kapsa(g, { x0: h.x0, x1: h.x1, y0: h.y0, y1: h.y1, zTop: V.zTop, d: V.dPocket, s: V.dPocket, name: 'vicko_kapsa' });
  kapsa(g, { ...strip, zTop: V.zTop, d: 3, s: 3, ucho: false, name: 'vicko_pruh' });
  // plaketa s logem na dně velké kapsy (+y shluk): tenký bílý obrys se zkosenými rohy (text a logo se nemodelují)
  const zPl = V.zTop - V.dPocket + 0.2;
  g.add(rrFrame('bila', 'vicko_plaketa', { x0: -40, x1: 28.3, y0: 73.3, y1: 188.3, z0: zPl, z1: zPl + 0.5, w: 0.8, rs: 8, seg: 1 }));
  // těsnění (černá guma) pod víkem po obvodu
  g.add(rrFrame('cerna_mat', 'vicko_tesneni', { x0: -156.5, x1: 177.5, y0: -236.5, y1: 236.5, z0: 108.4, z1: 111, w: 2.6, rs: [26, 14, 14, 26], seg: 5 }));
  // --- čelní lem (z' 98..117), držáky spon, žebírka na okraji, kopule
  g.add(slab('vicko_cira', 'vicko_lem', { x0: 183.8, x1: 188.6, y0: -214, y1: 214, z0: 98, z1: V.zTop, rs: 4, seg: 3, reT: 1.2, reB: 1.2, fs: 2 }));
  for (const s of [-1, 1]) {
    const yc = s * 150.2;
    g.add(slab('vicko_cira', 'vicko_drzak', { x0: 182, x1: 191, y0: yc - 33.5, y1: yc + 33.5, z0: 95.5, z1: 116, rs: 4, seg: 3, reT: 2.5, reB: 1.5, fs: 3 }));
    // zápustka s příčkou pod třmenem (tmavší pruh na čele držáku)
    g.add(slab('cira', 'vicko_drzak_pruh', { x0: 190.4, x1: 191.4, y0: yc - 22, y1: yc + 22, z0: 100, z1: 108, rs: 1.5, seg: 2, reT: 0.4, reB: 0.4, fs: 1 }));
  }
  for (let k = -11; k <= 11; k++) {                     // žebírka na horní hraně čela
    const y = 5 + k * 20.4; if (Math.abs(y) > 212) continue;
    g.add(bx('cira', 'vicko_zebirko', 188.6, 189.6, y - 0.7, y + 0.7, 107, 116));
  }
  for (let k = 0; k < 11; k++) {                         // žebírka na koncích víka (po 21,5 mm)
    const x = 135 - k * 21.5 - 0 ; if (x < -150) continue;
    for (const s of [-1, 1]) g.add(bx('cira', 'vicko_zebirko_k', x - 1.2, x + 1.2, s > 0 ? V.y - 0.3 : -V.y - 0.9, s > 0 ? V.y + 0.9 : -V.y + 0.3, 108.5, 115.5));
  }
  g.add(cylinder('vicko_cira', 'vicko_kopule', 5.5, 0, 2.2, 20, [0, 0]).rot('y', 90).move(188.4, -46, zc(106)));
  // --- pant: čiré články (středy |y| = 54,4; 103,6; 152,7; 201,5; šířka 22) kolem čepu (x = -175,5, z' = 97)
  for (const yc of [54.4, 103.6, 152.7, 201.5]) for (const s of [-1, 1]) {
    g.add(slab('vicko_cira', 'vicko_clanek', { x0: -182, x1: -162, y0: s * yc - 11, y1: s * yc + 11, z0: 89, z1: 115, rs: 4, seg: 3, reT: 3, reB: 6, fs: 3 }));
  }
  return g;
}
