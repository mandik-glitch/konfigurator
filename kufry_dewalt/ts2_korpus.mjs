// Korpus (spodní díl) DeWalt ToughSystem 2.0: vana s čelním vybráním (štítek s logem), kapsami západek v rozích čela, kapsami madel na obou koncích,
// žlutá těsnicí linka, západky (černá páka + drátový třmen), černé madlo na koncích, spodní články pantu. Vnitřek je hladká vana (zjednodušeno).
// Míry z fotografií c01/c02 (studiové, šikmé); poměry odvozeny z proporcí (měřítko = datasheet 554 × 371 × H), viz zdroje/*_poznamky.md.
import { Group, Part, vana, prstenec, plocha, extYZ, extXZ, bx, rb, cylX, cylinder, tube, zc } from './ts2_zaklad.mjs';
import { par, F, nl, D } from './ts2_par.mjs';

export const KOR = { xF: 184.5, y: 276.2, panelY: 125, panelD: 12, latchHalf: 48 };

export function korFrames(p) {
  const { zRim } = p, xf = KOR.xF, y = KOR.y;
  const c = 13, r = 12;
  return [
    F(0, xf - 9, -xf + 9, y - 9, y - 9 - c, c, r), F(6, xf - 2.5, -xf + 2.5, y - 2.5, y - 2.5 - c, c, r), F(16, xf - 0.5, -xf + 0.5, y - 0.5, y - 0.5 - c, c, r),
    F(34, xf, -xf, y, y - c, c, r), F(zRim, xf, -xf, y, y - c, c, r),
  ];
}
// výřezy v čelní hraně (zleva doprava podle Y): kapsa levé západky, vybrání štítku (logo), kapsa pravé západky
export function korNotches(p) {
  const { zRim, zIn, yLatch } = p, xf = KOR.xF, LH = KOR.latchHalf;
  const lat = s => nl([{ z: zRim - 128, y0: s * yLatch - LH, y1: s * yLatch + LH, nx: xf - 9 }, { z: zRim, y0: s * yLatch - LH, y1: s * yLatch + LH, nx: xf - 9 }]);
  return [lat(-1), nl([{ z: zIn, y0: -KOR.panelY, y1: KOR.panelY, nx: xf - KOR.panelD }, { z: zRim - 24, y0: -KOR.panelY, y1: KOR.panelY, nx: xf - KOR.panelD }]), lat(1)];
}
// výřezy v koncových stěnách (kapsa madla): X −160…+78, hloubka 7 mm, od spodní hrany panelu (zRim − 86) po spáru
export function korEnds(p) { return [{ fr: [{ z: p.zRim - 86, x0: -160, x1: 78, d: 7 }, { z: p.zRim, x0: -160, x1: 78, d: 7 }] }]; }

// žlutá těsnicí linka podél spáry (tenký pás, vyčnívá o ~0,5 mm nad korpus a je kryt přesahem víka)
function tesneni(g, p) {
  const f = (z) => F(z, 185.0, -185.0, 276.7, 263.7, 13, 12);
  g.add(prstenec('zluta', 'tesneni', { frames: [f(p.zRim - 5.5), f(p.zRim + 1)], wall: 2.5 }));
}

function logo(g, p) {
  // logo DEWALT + TOUGHSYSTEM 2.0 jako tenké žluté plošky (písmena z obdélníků) na vybrání štítku; rovina x = xF − panelD
  const x0 = KOR.xF - KOR.panelD - 0.05, x1 = x0 + 0.7, zt = p.zRim;
  const R = (a, b, c, d) => g.add(bx('zluta', 'logo_dewalt', x0, x1, Math.min(a, b), Math.max(a, b), zt + Math.min(c, d), zt + Math.max(c, d)));   // y0,y1,z0,z1 (z relativně ke spáře, záporné dolů)
  const bar = (a, b, c, d) => R(a, b, c, d);
  // horní a dolní linka
  bar(-92, 92, -50, -53.5); bar(-92, 92, -92, -95.5);
  // DEWALT: 6 písmen v pásu z −57 … −89 (výška 32), šířky 27, mezera 3
  const zA = -89, zB = -57, st = 6.5, w = 27, gap = 3, L0 = -90;
  const letters = ['D', 'E', 'W', 'A', 'L', 'T'];
  letters.forEach((ch, i) => {
    const a = L0 + i * (w + gap), b = a + w, m = (a + b) / 2;
    if (ch === 'D') { bar(a, a + st, zA, zB); bar(a, b - 7, zB - st, zB); bar(a, b - 7, zA, zA + st); bar(b - st, b, zA + 7, zB - 7); bar(b - 7, b - st + 0.01, zA + 2, zA + 7); bar(b - 7, b - st + 0.01, zB - 7, zB - 2); }
    if (ch === 'E') { bar(a, a + st, zA, zB); bar(a, b, zB - st, zB); bar(a, b - 3, (zA + zB) / 2 - st / 2, (zA + zB) / 2 + st / 2); bar(a, b, zA, zA + st); }
    if (ch === 'W') { bar(a, a + st, zA + 3, zB); bar(b - st, b, zA + 3, zB); bar(m - st / 2, m + st / 2, zA + 3, zB - 8); bar(a, b, zA, zA + st); }
    if (ch === 'A') { bar(a, a + st, zA, zB - 6); bar(b - st, b, zA, zB - 6); bar(a + 3, b - 3, zB - st, zB); bar(a, b, (zA + zB) / 2 - st / 2, (zA + zB) / 2 + st / 2); }
    if (ch === 'L') { bar(a, a + st, zA, zB); bar(a, b, zA, zA + st); }
    if (ch === 'T') { bar(a, b, zB - st, zB); bar(m - st / 2, m + st / 2, zA, zB); }
  });
  // TOUGHSYSTEM 2.0: schematicky tři ploché pásy (TOUGH tučně, SYSTEM tenčí, 2.0 tučně), výška 17 (z −99 … −116)
  bar(-92, -22, -116, -99); bar(-19, 52, -113, -102); bar(56, 92, -116, -99);
}

function zapadky(g, p) {
  const { zRim, yLatch } = p, xp = KOR.xF - 9;                 // dno kapsy
  for (const s of [-1, 1]) {
    const yc = s * yLatch;
    // spodní (dlouhý) díl páky v kapse korpusu: z' zRim−120 … zRim−4, šířka 62
    g.add(rb('cerna_mat', 'zapadka_paka', { x0: xp + 1, x1: KOR.xF - 0.9, y0: yc - 31, y1: yc + 31, z0: zRim - 120, z1: zRim - 4, rc: 2, re: 1.5, seg: 2, fs: 2 }));
    for (const k of [-18, -6, 6, 18]) g.add(bx('cerna', 'zapadka_zebro', KOR.xF - 1.2, KOR.xF - 0.45, yc + k - 1, yc + k + 1, zRim - 100, zRim - 60));
    // drátový třmen (pozink), spodní polovina: dvě svislé větve + spodní příčka; horní polovina je na víku (ts2_vicko.mjs)
    const xw = xp + 5.5;
    const path = [[xw, yc - 40, zRim - 1], [xw, yc - 40, zRim - 100], [xw, yc - 39, zRim - 106], [xw, yc - 33, zRim - 108.5], [xw, yc + 33, zRim - 108.5], [xw, yc + 39, zRim - 106], [xw, yc + 40, zRim - 100], [xw, yc + 40, zRim - 1]];
    g.add(tube('seda_svetla', 'zapadka_drat_spodni', path.map(q => [q[0], q[1], zc(q[2])]), 2.3, 8));
  }
}

function madlaKonce(g, p) {
  // sklopné madlo v kapse na každém konci (složené): horní příčka, dvě stojky, držadlo; tvar přibližný (c01/c02: kapsa 7 mm, madlo vyplňuje kapsu)
  const { zRim } = p;
  for (const s of [-1, 1]) {
    const yIn = KOR.y - 7, yOut = yIn + 6;                  // dno kapsy → líc madla
    const Y = (a, b) => s > 0 ? [yIn + a, yIn + b] : [-(yIn + b), -(yIn + a)];
    let [a, b] = Y(0, 6);
    g.add(bx('cerna_mat', 'madlo_pricka', -146, 66, a, b, zRim - 20, zRim - 6));           // horní příčka s čepy
    g.add(bx('cerna_mat', 'madlo_stojka', -148, -128, a, b, zRim - 82, zRim - 6));           // zadní stojka
    g.add(bx('cerna_mat', 'madlo_stojka', 40, 68, a, b, zRim - 82, zRim - 6));               // přední stojka
    [a, b] = Y(0, 5);
    g.add(bx('cerna', 'madlo_drzadlo', -128, 40, a, b, zRim - 66, zRim - 44));              // úchopová příčka
  }
}

function pant(g, p) {
  // spodní články pantu na zadní straně (liché úseky); osa Y, střed x = −181; tvar přibližný, zadní strana na fotografiích není vidět
  const zz = p.zRim - 1;
  for (const yc of [-215, -75, 75, 215]) g.add(cylinder('cerna_mat', 'pant_clanek', 6.2, yc - 34, yc + 34, 14, [0, 0]).mapV((u, v, w) => [u - 179.2, w, v + zc(zz + 3.5)]).flip());
}

export function korpus(p) {
  const g = new Group('korpus');
  g.add(vana('cerna', 'korpus_vana', { frames: korFrames(p), notches: korNotches(p), enotches: korEnds(p), wall: 3.5, floorZ: 12 }));
  tesneni(g, p); logo(g, p); zapadky(g, p); madlaKonce(g, p); pant(g, p);
  return g;
}
