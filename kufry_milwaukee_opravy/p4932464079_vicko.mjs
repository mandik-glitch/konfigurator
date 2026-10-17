// Víko: hluboká skořepina (spodní lem s rohovými výřezy pro krytky, vnější plášť se zkosenými rameny na koncích, plató s 10 kapsami, červený štítek;
// zevnitř strop se žebry, kruhový výstupek a šikmé výztuhy u pantu). Samostatná skupina `vicko` s pivotem na ose pantu (zadní horní hrana vany),
// extras.osa = [0,-1,0] (otevření = kladný úhel, max. 110°). Nájezdy zámků (pouzdra) a žebrovaný výstupek v čele patří k víku.
import { Group, Part, rrPoly, polyInset, ccw, loftRings, roundPoly, plateHoles, capPoly, bx, slab, extYZ, extXZ, cylX, cylY, cylZ, zc, ZC, loftSolid } from './p4932464079_zaklad.mjs';

// půdorys víka: dxF/dxR = odsazení čelní/zadní hrany, dy = odsazení koncových hran, r = poloměr rohů
const planL = (V, dxF, dxR, dy, r = V.rLid ?? 30) => rrPoly(-(V.X - dxR), V.X - dxF, -(V.Y - dy), V.Y - dy, Math.max(r - Math.max(dxF, dy) * 0.6, 3), 5);
// půdorys spodního lemu s rohovými výřezy (do nich zapadají krytky)
export function lemPoly(V) {
  if (V.rohy === false) return ccw(rrPoly(-V.X, V.X - (V.lemOdsazeni ?? 6), -V.Y, V.Y, V.rLid ?? 38, 5));
  const X = V.X, Y = V.Y, xn = V.xN - 0.8, yn = V.yN - 0.8, XF = V.X - (V.lemOdsazeni ?? 6);
  const pts = [[XF, -yn], [XF, yn], [xn, yn], [xn, Y], [-xn, Y], [-xn, yn], [-X, yn], [-X, -yn], [-xn, -yn], [-xn, -Y], [xn, -Y], [xn, -yn]];
  return ccw(roundPoly(pts, [6, 6, 3, 6, 6, 3, 6, 6, 3, 6, 6, 3], 3));
}
// profil horní části: [dxF, dxR, dy, z'] zdola nahoru
export function profilVika(V) {
  const zk = V.H - V.lidH + V.capUp, H = V.H;
  return [[0, 0, 0, zk], [0, 0, 0, H - 30], [0.5, 1, 6, H - 22], [3, 2.5, 20, H - 14], [8, 5, 33, H - 5], [11, 9, 38, H - 1.2], [12.5, 11, 40, H]];
}
// obdélníkové kapsy plató: [x0,x1,y0,y1], skupiny levá (Y<0) a pravá (Y>0), středové žebro mezi nimi
export function kapsyVika(V = {}) {
  if (V.lidTyp === 'elektrikar') {
    // zavřené víko boxu z fotografie sady (shora): 2 skupiny po 5 kapsách + úzká drážka mezi skupinami; v jedné skupině kapsa s červeným štítkem, ve druhé vysoká kapsa
    const rz = [-160, -96], rs = [-84, 22], rp = [34, 100], R = [];
    const add = (r, y0, y1, d = 14) => R.push({ x0: r[0], x1: r[1], y0, y1, d });
    add(rz, -232, -132); add(rz, -120, -12); add(rs, -176, -58); add(rp, -232, -132); add(rp, -120, -12);
    add(rz, 12, 120); add(rz, 132, 232); add(rs, 30, 232); add(rp, 12, 120); add(rp, 132, 232);
    R.push({ x0: -150, x1: 110, y0: -9, y1: 9, d: 7 });
    return R;
  }
  const R = [], radky = { zad: [-160, -96], stred: [-84, 22], predni: [34, 100] };
  for (const s of [-1, 1]) {
    const m = (a, b) => s < 0 ? [-b, -a] : [a, b];
    const sp = (r, a, b) => { const [y0, y1] = m(a, b); R.push({ x0: r[0], x1: r[1], y0, y1 }); };
    sp(radky.zad, 12, 120); sp(radky.zad, 132, 232); sp(radky.stred, 30, 222); sp(radky.predni, 12, 120); sp(radky.predni, 132, 232);
  }
  return R.map(k => ({ ...k, d: 14 }));
}

export function vicko(V) {
  const zs = V.H - V.lidH, zk = zs + V.capUp, H = V.H;
  const g = new Group('vicko', { pivot: [V.pantX, 0, zc(zs + V.pantZ_off)], extras: { osa: [0, -1, 0], max_uhel: 110, poznamka: 'otevření = kladný úhel kolem osy -Y (pant vzadu), jako v prohlížeči' } });
  // --- spodní lem (výška capUp + švík): dutý prstenec s rohovými výřezy
  { const P = lemPoly(V), Pi = polyInset(P, 3.2), p = new Part('vicko_lem', 'cerna'); p.crease = 38;
    const R = (poly, z) => poly.map(q => [q[0], q[1], zc(z)]);
    loftRings(p, [R(P, zs), R(P, zk), R(Pi, zk), R(Pi, zs)], { closed: true }); g.add(p); }
  // --- horní plášť
  const pr = profilVika(V);
  const ringsO = pr.map(([a, b, c, z]) => ccw(planL(V, a, b, c)).map(q => [q[0], q[1], zc(z)]));
  const innerPr = [[3.2, 3.2, 3.2, zk], [3.2, 3.2, 3.2, H - 30], [8, 6, 20, H - 22], [14, 10, 36, H - 22 + 3], [20, 16, 42, H - 19], [24, 20, 46, H - 17.5]];
  // vnitřní plášť: odsazení od vnějšího
  const ringsI = [[3.2, 3.2, 3.2, zk], [3.2, 3.2, 3.2, H - 32], [6, 5, 14, H - 26], [12, 10, 34, H - 20], [18, 15, 42, H - 17.5]].map(([a, b, c, z]) => ccw(planL(V, a, b, c)).map(q => [q[0], q[1], zc(z)])).reverse();
  const p = new Part('vicko_plast', 'cerna'); p.crease = 38;
  loftRings(p, [...ringsI, ...ringsO], {});
  { const R = ringsI[0]; capPoly(p, R.map(q => [q[0], q[1]]), R[0][2], false); }
  g.add(p);
  // --- plató s kapsami
  const top = ccw(planL(V, pr[pr.length - 1][0], pr[pr.length - 1][1], pr[pr.length - 1][2]));
  const KS = kapsyVika(V), kap = KS.map(k => ccw(rrPoly(k.x0, k.x1, k.y0, k.y1, 7, 3))), dKap = 14;
  g.add(plateHoles('cerna', 'vicko_plato', top, kap, H - dKap, H, { bottom: false, outerWall: false }));
  // hluboké kapsy: stěny do dna (plateHoles má stěny děr do z0 = H - dKap); mělčí drážka má dno výše
  kap.forEach((k, i) => { const f = new Part('kapsa_dno_' + i, 'cerna'); capPoly(f, k, zc(H - dKap), true); g.add(f); });
  // červený štítek
  if (V.lidTyp === 'elektrikar') g.add(slab('cervena', 'vicko_stitek', { x0: -76, x1: 12, y0: -170, y1: -64, z0: H - dKap, z1: H - dKap + 1.6, rs: 4, seg: 2, reT: 0.5, reB: 0.1, fs: 1 }));
  else g.add(slab('cervena', 'vicko_stitek', { x0: 4, x1: 16, y0: 112, y1: 226, z0: H - dKap, z1: H - dKap + 1.2, rs: 2, seg: 2, reT: 0.4, reB: 0.1, fs: 1 }));
  // --- ouška na koncích víka (pro čepy horního držadla / žebrovaný výstupek)
  if (V.rohy !== false) for (const s of [-1, 1]) {
    g.add(slab('cerna', 'vicko_uso_' + (s > 0 ? 'P' : 'L'), { x0: -44, x1: 56, y0: s > 0 ? V.Y - 9.5 : -V.Y + 0.1, y1: s > 0 ? V.Y - 0.1 : -V.Y + 9.5, z0: H - 52, z1: H - 20, rs: 5, seg: 2, reT: 3, reB: 1.5, fs: 2 }));
    for (let i = 0; i < 6; i++) g.add(bx('cerna_mat', 'vicko_uso_zebro', -34 + i * 17, -34 + i * 17 + 3.5, s > 0 ? V.Y - 11.5 : -V.Y + 9.4, s > 0 ? V.Y - 9.4 : -V.Y + 11.5, H - 50, H - 22));
  }
  // --- čelo víka: nájezdy zámků (pouzdra) a žebrovaný výstupek uprostřed
  for (const s of [-1, 1]) g.add(slab('cerna', 'vicko_pouzdro_' + (s > 0 ? 'P' : 'L'), { x0: V.xF - 0.5, x1: V.X - 0.6, y0: s * V.yLatch - 36, y1: s * V.yLatch + 36, z0: zk - 0.5, z1: zk + 22, rs: 5, seg: 2, reT: 2, reB: 1, fs: 2 }));
  g.add(slab('cerna', 'vicko_vystupek', { x0: V.X - 12, x1: V.X - 0.4, y0: -52, y1: 46, z0: zs + 2, z1: zs + 56, rs: 3, seg: 2, reT: 3, reB: 1, fs: 2 }));
  for (let k = 0; k < 5; k++) g.add(slab('cerna_mat', 'vicko_zebro', { x0: V.X - 12, x1: V.X + 0.1 - 0.5, y0: -42 + k * 17 - 1.5, y1: -42 + k * 17 + 1.5, z0: zs + 6, z1: zs + 50, rs: 0.5, seg: 1, reT: 1.5, reB: 0.3, fs: 1 }));
  if (V.vnitrekVika !== 'panel') {
  // --- vnitřní žebra víka (pohled zevnitř: dvě podélná žebra, kruhový výstupek, šikmé výztuhy u pantu, šrouby)
  const zc0 = H - 17.5;                           // strop uvnitř
  for (const s of [-1, 1]) g.add(slab('cerna', 'vicko_zebro_vnitrni_' + (s > 0 ? 'P' : 'L'), { x0: -170, x1: 150, y0: s * 96 - 2.2, y1: s * 96 + 2.2, z0: zc0 - 17, z1: zc0 + 0.5, rs: 1, seg: 1, reT: 0.4, reB: 0.8, fs: 1 }));
  g.add(cylZ('cerna', 'vicko_vystupek_kruh', 33, zc0 - 13, zc0 + 0.5, -10, 0, 28));
  g.add(cylZ('cerna_mat', 'vicko_vystupek_kruh_dno', 27, zc0 - 14.2, zc0 - 12.5, -10, 0, 28));
  for (let k = 0; k < 5; k++) { const y = -148 + k * 74; g.add(extYZ('seda', 'vicko_vyztuha_pantu', [[y - 18, zc0 + 0.5], [y + 18, zc0 + 0.5], [y + 11, zc0 - 16], [y - 11, zc0 - 16]], -V.X + 20, -V.X + 24.5)); }
  for (const [x, y] of [[-120, -150], [-120, 150], [90, -160], [90, 160], [-60, -60], [-60, 60], [40, 0]]) g.add(cylZ('cerna_mat', 'vicko_sroub_sloupek', 4.2, zc0 - 6, zc0 + 0.5, x, y, 12));
  }
  // --- kloubová oka pantu (víko) a čep
  for (const yc of [-190, -95, 0, 95, 190]) g.add(cylY('cerna', 'pant_oko_vicko', 7.2, yc - 17, yc + 17, V.pantX, zs + V.pantZ_off, 20));
  return g;
}
