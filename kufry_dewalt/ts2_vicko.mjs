// Víko DeWalt ToughSystem 2.0: dutý plášť (stěna 3 mm) s přesahem u spáry, zkosenou horní hranou, kapsami horních částí západek v rozích čela,
// vybráním štítku v čele, kapsou sklopného madla v horní ploše (madlo = samostatná skupina `drzadlo`), žlutými čepy na koncích a pantovými články.
// Vnitřek víka je hladký (zjednodušeno; ve skutečnosti žebrování).
import { Group, vickoPlast, vana, prstenec, extYZ, extXZ, bx, rb, cylX, cylinder, tube, zc } from './ts2_zaklad.mjs';
import { par, F, nl, D } from './ts2_par.mjs';
import { KOR } from './ts2_korpus.mjs';

export function vickoFrames(p) {
  const { zRim, H } = p, t = D.LID, yp = 150;       // yp: konce horní plochy – střední pás (|Y| < 150, mezi rohovými sloupky západek) je o ~10 mm výš než rohové a koncové bloky
  return [
    F(zRim, 185.5, -185.5, 277, 264, 13, 12), F(zRim + 9, 185.5, -185.5, 277, 264, 13, 12), F(zRim + 11, 183.5, -183.5, 275.5, 262.5, 13, 12),
    F(H - 0.34 * t, 183.5, -183.5, 275.5, 262, 14, 13), F(H - 0.17 * t, 177, -177, 268.5, 250, 22, 18), F(H - 0.17 * t + 0.1, 177, -177, yp + 6, yp - 20, 22, 18),
    F(H - 0.07 * t, 171, -171, yp + 2, yp - 24, 26, 22), F(H, 164, -164, yp - 6, yp - 32, 28, 24),
  ];
}
export function vickoNotches(p) {
  const { zRim, H, yLatch } = p, xf = 183.5, LH = KOR.latchHalf;
  const lat = s => nl([{ z: zRim, y0: s * yLatch - LH, y1: s * yLatch + LH, nx: xf - 7.5 }, { z: zRim + 0.8 * D.LID, y0: s * yLatch - LH, y1: s * yLatch + LH, nx: xf - 7.5 }]);
  // střed čela: stupeň pod štítkem (hloubka 10 do z' zRim+40), nad ním ustoupí o 28 mm
  const mid = nl([{ z: zRim, y0: -128, y1: 128, nx: xf - 10 }, { z: zRim + 0.5 * D.LID, y0: -128, y1: 128, nx: xf - 10 }, { z: zRim + 0.5 * D.LID + 2, y0: -128, y1: 128, nx: xf - 26 }, { z: H - 0.3 * D.LID, y0: -128, y1: 128, nx: xf - 26 }, { z: H - 0.15 * D.LID, y0: -128, y1: 128, nx: 400 }]);
  return [lat(-1), mid, lat(1)];
}

// kapsa sklopného madla v horní ploše (obrys = otvor v plášti); stojí na dně z' = zPocket
const OT = (wl = 0) => ({ z: 0, xf: 56 + wl, xr: -56 - wl, y0: -140 - wl, y1: 140 + wl, yF: 132 + wl, cfx: 8, rr: 10, ns: 2, wx: 3, wy: 3 });
export const MADLO = { LH: 78, xPiv: -48, T: 18, W: 24, Ys: 118 };      // délka smyčky od osy, tloušťka, šířka stojky, Y osy stojek

function kapsa(g, p) {
  const O3 = OT(3), fr = [{ ...O3, z: p.zPocket - 3 }, { ...O3, z: p.H - 0.4 }];
  g.add(vana('cerna', 'kapsa_madla', { frames: fr, wall: 3, floorZ: p.zPocket }));
  return O3;
}
function zluteDily(g, p) {
  const { zRim, H, zPocket } = p;
  for (const s of [-1, 1]) {
    // žlutý stohovací čep na konci víka s ryskami „TOUGHSYSTEM“; vystupuje z koncové stěny (275,5) na obálku 277
    const a = s > 0 ? 272.5 : -276.7, b = s > 0 ? 276.7 : -272.5;
    g.add(rb('zluta', 'cep_konec', { x0: -82, x1: 22, y0: Math.min(a, b), y1: Math.max(a, b), z0: zRim + 13, z1: H - 5, rc: 0.5, re: 1.5, seg: 2, fs: 2 }));
    const aa = s > 0 ? 276.3 : -277, bb = s > 0 ? 277 : -276.3;
    for (const dz of [25, 33, 41]) g.add(bx('cerna_mat', 'cep_ryska', -76, 16, Math.min(aa, bb), Math.max(aa, bb), zRim + dz, zRim + dz + 3));
  }
  // štítek na jmenovku v čele (žlutý pásek pod čirým krytem) a očko pro zámek (ocelová podložka)
  g.add(bx('zluta', 'stitek', 170, 177.5, -78, 78, zRim + 20, zRim + 35));
  g.add(bx('cerna_mat', 'stitek_kryt', 170, 178.5, -80, 80, zRim + 35, zRim + 37.2));
  g.add(cylX('seda_svetla', 'ocko_zamek', 8.5, 170, 177.8, 0, zRim + 6, 18));
  // žlutý uvolňovač madla v kapse (mezi stojkami)
  g.add(bx('zluta', 'tlacitko_madla', 14, 38, -22, 22, zPocket, zPocket + 5));
}
function hornDilyZapadek(g, p) {
  const { zRim, yLatch } = p, xp = 183.5 - 7.5;
  for (const s of [-1, 1]) {
    const yc = s * yLatch;
    // horní žebrovaná část páky (na víku): z' zRim+4 … zRim+54, šířka 66; rozteč žeber 4 × 14
    g.add(rb('cerna_mat', 'zapadka_hlava', { x0: xp + 1, x1: 185.0, y0: yc - 33, y1: yc + 33, z0: zRim + 4, z1: zRim + 0.7 * D.LID, rc: 2, re: 1.5, seg: 2, fs: 2 }));
    const xw = xp + 5.5, path = [[xw, yc - 40, zRim - 1], [xw, yc - 40, zRim + 36], [xw, yc - 37, zRim + 40], [xw, yc + 37, zRim + 40], [xw, yc + 40, zRim + 36], [xw, yc + 40, zRim - 1]];
    g.add(tube('seda_svetla', 'zapadka_drat_horni', path.map(q => [q[0], q[1], zc(q[2])]), 2.3, 8));
    for (const k of [-21, -7, 7, 21]) g.add(bx('cerna', 'zapadka_zebro_hlava', 184.4, 185.2, yc + k - 1.2, yc + k + 1.2, zRim + 12, zRim + 50));
  }
}
function lemVnitrni(g, p) {
  // žlutý vnitřní lem víka (těsnění) u spodního okraje, uvnitř stěny; kopíruje kapsy západek posunuté o stěnu (3 mm), viditelný jen z vnitřní strany
  const { zRim } = p, w = 3;
  const nn = vickoNotches(p).map(n => { const a = n.fr[0], g = { y0: a.y0 - w - 0.4, y1: a.y1 + w + 0.4, nx: a.nx - w - 0.4 }; return { fr: [{ z: zRim + 0.4, ...g }, { z: zRim + 9, ...g }] }; });   // výřezy jen v rozsahu lemu (z' zRim … zRim+9)
  const f = z => F(z, 182.4, -182.4, 274, 261, 13, 15);
  g.add(prstenec('zluta', 'lem_vicka', { frames: [f(zRim + 0.4), f(zRim + 9)], notches: nn, wall: 3 }));
}
function pant(g, p) {
  // horní (víkové) články pantu na zadní straně (sudé úseky); tvar přibližný, zadní strana na fotografiích není vidět
  const zz = p.zRim + 1;
  for (const yc of [-145, 0, 145]) g.add(cylinder('cerna_mat', 'pant_clanek_vicko', 6.2, yc - 34, yc + 34, 14, [0, 0]).mapV((u, v, w) => [u - 179.2, w, v + zc(zz + 3.5)]).flip());
  g.add(cylinder('seda_svetla', 'pant_cep', 2.2, -250, 250, 10, [0, 0]).mapV((u, v, w) => [u - 179.2, w, v + zc(zz + 3.5)]).flip());
}

export function vicko(p) {
  const g = new Group('vicko', { pivot: [p.pivotVicko[0], p.pivotVicko[1], zc(p.pivotVicko[2])], extras: { osa: [0, -1, 0], max_uhel: 105 } });
  const O3 = kapsa(g, p);
  g.add(vickoPlast('cerna', 'vicko_plast', { frames: vickoFrames(p), notches: vickoNotches(p), wall: 3, topT: 3, holes: [{ ...OT(), z: p.H }] }));
  zluteDily(g, p); hornDilyZapadek(g, p); lemVnitrni(g, p); pant(g, p);
  return g;
}

// sklopné madlo v horní ploše: smyčka (dvě stojky + příčka-držadlo) uložená v kapse, osa otáčení v Y na zadní hraně kapsy; extras.osa = [0,−1,0] (kladný úhel zvedá madlo)
export function madlo(p) {
  const { xPiv, LH, T, W, Ys } = MADLO, zP = p.zPocket + 5;
  const g = new Group('drzadlo', { pivot: [xPiv, 0, zc(zP)], extras: { osa: [0, -1, 0], max_uhel: 95 } });
  for (const s of [-1, 1]) {
    const ya = s > 0 ? Ys - W / 2 : -Ys - W / 2;
    g.add(rb('cerna_mat', 'madlo_stojka', { x0: xPiv - 4, x1: xPiv + LH, y0: ya, y1: ya + W, z0: zP - T / 2, z1: zP + T / 2, rc: 2, re: 2, seg: 2, fs: 2 }));
  }
  g.add(rb('cerna', 'madlo_pricka', { x0: xPiv + LH - 30, x1: xPiv + LH, y0: -Ys - W / 2, y1: Ys + W / 2, z0: zP - T / 2, z1: zP + T / 2, rc: 2, re: 3, seg: 3, fs: 3 }));
  return g;
}
