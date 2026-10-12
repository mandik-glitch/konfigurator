// Víko Hilti Kufr 2-tools (M) SF/SI+TE (2329206): dutý červený plášť (hladká dutina), „koruna“ (čelní a zadní plató se sklonem ke krajům) s drážkou přes celou šířku
// (bílé logo HILTI), stohovací desky, kapsy západek s černými bloky, madlo (šedý rám + černá rukojeť) s průchozím oknem, články pantu.
// Víko je samostatná skupina `vicko` s pivotem na pantové hraně (zadní, X −223,7, z' = SP) a extras.osa = [0,−1,0].
// Všechny výšky z' jsou ODHAD (žádný boční pohled); půdorysné míry z c01 (viz p2329206_zaklad.mjs pX, pY).
import { Group, vickoPlast, plocha, prstenec, trubka, bx, rb, cylinder, prism, zc, pX, pY } from './p2329206_zaklad.mjs';
import { SP, Z_CAP, Z_PL, Z_PAD, D, S, enFR, WIN, FRAME, LAT, LAT_Y, LAT_BLK, HINGE, hingeSegments, hingeRadius } from './p2329206_korpus.mjs';

export const V = { pivot: [HINGE.x, 0, zc(SP)] };

// drážka s logem (c01): předního plató se týká stěna py 320..350, zadního py 570..600 (stěny drážky ~15 mm široké, ~45° sklon); dno drážky = horní plocha skořepiny
const XG = { f0: pX(320), f1: pX(350), r1: pX(570), r0: pX(600) };      // 73,6 / 58,9 / −49,0 / −63,7
const XPL = { frontTop: pX(130), rearTop: pX(800), rearFoot: pX(870) };  // čelní plató končí v py 130 (X 166,7), zadní svah py 800..870

function koruna() {
  // čelní část: základna na z = Z_CAP (obrys skořepiny bez bulge), plató Z_PL se sklony 54 mm vpředu a 47 mm po stranách
  const cm = D.CM;
  const FF = [
    { z: Z_CAP, xf: D.XF - 3.1, xr: XG.f1, y0: -293.5, y1: 293.5, yF: 217, cfx: 21, rr: 0.05, cm },
    { z: Z_PL, xf: XPL.frontTop, xr: XG.f0, y0: -247, y1: 247, yF: 170, cfx: 16, rr: 0.05, cm },
  ];
  const fr = [{ z: Z_CAP, z1: Z_PL }];
  const nl = (y0, y1) => ({ fr: [{ z: Z_CAP, y0, y1, nx: LAT.nx }, { z: Z_PL, y0, y1, nx: LAT.nx }] });
  const nh = { fr: [{ z: Z_CAP }, { z: Z_PL }], path: [[193.7, -107], [160.1, -66], [160.1, 66], [193.7, 107]] };
  const front = plocha('cervena', 'koruna_predni', { frames: FF, notches: [nl(-LAT_Y[1], -LAT_Y[0]), nh, nl(LAT_Y[0], LAT_Y[1])] });
  // zadní část: z drážky (X −49) do plató, zadní svah 34 mm (py 800..870), po stranách 24 mm
  const FR = [
    { z: Z_CAP, xf: XG.r1, xr: XPL.rearFoot, y0: -293.5, y1: 293.5, yF: 293.4, cfx: 0.3, rr: 22, cm: [] },
    { z: Z_PL, xf: XG.r0, xr: XPL.rearTop, y0: -270, y1: 270, yF: 269.9, cfx: 0.3, rr: 16, cm: [] },
  ];
  const rear = plocha('cervena', 'koruna_zadni', { frames: FR });
  return [front, rear];
}

function padPoly(py0, py1, pxa, pxb) {
  // lichoběžník stohovací desky: delší hrana (pxa) u py0, kratší (pxb) u py1; px → Y, py → X
  return [[pX(py0), pY(pxa[0])], [pX(py0), pY(pxa[1])], [pX(py1), pY(pxb[1])], [pX(py1), pY(pxb[0])]];
}
function plotny(g) {
  // c01: levé desky px 50..277, pravé 920..1147; řady py 210..265 (přední), 648..698 (zadní); sražené konce – dvoustupňově (spodní 1,6 mm + horní 1,4 mm)
  const spec = [[210, 265, [50, 277], [75, 265], [920, 1147], [940, 1125]], [648, 698, [50, 277], [62, 262], [920, 1147], [935, 1135]]];
  for (const [py0, py1, La, Lb, Ra, Rb] of spec) {
    for (const [A, B] of [[La, Lb], [Ra, Rb]]) {
      const P = padPoly(py0, py1, A, B);
      g.add(prisma('cervena', 'plotna', P, Z_PL - 0.4, Z_PAD - 1.5));
      // horní stupeň: o 1,8 mm menší dovnitř
      const cx = P.reduce((a, q) => a + q[0], 0) / 4, cy = P.reduce((a, q) => a + q[1], 0) / 4;
      const Q = P.map(([x, y]) => [cx + (x - cx) * 0.93 + 0, cy + (y - cy) * 0.97]);
      g.add(prisma('cervena', 'plotna_horni', Q, Z_PAD - 1.6, Z_PAD));
    }
  }
}
const prisma = (mat, name, P, z0, z1) => prism(mat, name, P, zc(z0), zc(z1));

function logo(g) {
  // logo HILTI: bílé obdélníky vektorizované z masky c01 (px x0..x1, py y0..y1 včetně), na dně drážky; tloušťka 0,5 mm (neověřeno, jen ploška)
  const R = [[161, 226, 396, 427], [161, 227, 486, 517], [161, 413, 428, 485], [346, 413, 486, 517], [347, 413, 396, 427], [431, 497, 396, 518], [514, 580, 396, 461], [514, 723, 462, 518], [670, 953, 395, 451], [779, 845, 452, 517], [972, 1037, 396, 517]];
  for (const [a, b, c, d] of R) g.add(bx('bila', 'logo_hilti', pX(d + 1), pX(c), pY(b + 1), pY(a), Z_CAP - 0.1, Z_CAP + 0.4));
}

function madlo(g) {
  // rám madla (šedý, z' Z_CAP..167) s oknem a černá rukojeť (válcová příčka u čela, c01 px 400..800, py 0..70)
  g.add(prstenec('seda', 'madlo_ram', FRAME, WIN, Z_CAP, 167));
  g.add(rb('cerna_mat', 'madlo_rukojet', { x0: pX(70), x1: 230.5, y0: -99.5, y1: 99.5, z0: 166, z1: 171.5, rc: 6, re: 2.6, seg: 3, fs: 2 }));
}

function zapadky(g) {
  // černé bloky západek v kapsách čelní koruny (c01 px 157..292 / 905..1045, py 15..77); sražený horní okraj
  for (const s of [-1, 1]) {
    const ya = s < 0 ? -LAT_BLK.yb : LAT_BLK.ya, yb = s < 0 ? -LAT_BLK.ya : LAT_BLK.yb;
    g.add(rb('cerna_mat', 'zapadka_vicko', { x0: LAT_BLK.x0, x1: LAT_BLK.x1, y0: ya, y1: yb, z0: Z_CAP - 0.3, z1: Z_CAP + 4, rc: 3, re: 1.8, seg: 2, fs: 2 }));
  }
}

function ramena(g) {
  // červená ramena čelní hrany vedle madla: hrana stoupá z X 223,6 (px 300, py 16) k madlu (px 385, py 1) – c01 sloupce x 300..385; oboustranně, souměrně
  for (const s of [-1, 1]) {
    const P = [[223.4, s * pY(300)], [pX(1), s * pY(385)], [223.4, s * pY(385)]];
    P.forEach(q => { q[1] = s > 0 ? Math.abs(q[1]) : -Math.abs(q[1]); });
    g.add(prisma('cervena', 'rameno_madla', P, Z_CAP - 8, Z_CAP + 1.0));
  }
}
function pant(g) {
  const cylY = (name, r, y0, y1, x, z) => cylinder('cervena', name, r, y0, y1, 20, [0, 0]).mapV((u, v, w) => [u + x, w, v + zc(z)]).flip();
  for (const h of hingeSegments()) if (h.i % 2 === 0) g.add(cylY('pant_clanek_vicko', hingeRadius(h), h.a, h.b, HINGE.x, SP));
}

export function vicko() {
  const g = new Group('vicko', { pivot: V.pivot, extras: { osa: [0, -1, 0], max_uhel: 140 } });
  const fr = [S(SP, 0.7), S(SP + 1.4, 0), S(Z_CAP - 1.4, 0), S(Z_CAP - 0.5, 0.8), S(Z_CAP, 2.2)];
  g.add(vickoPlast('cervena', 'vicko_plast', { frames: fr, enotches: enFR(SP, Z_CAP), wall: 3, topT: 3, holePolys: [WIN] }));
  g.add(trubka('seda', 'okno_trubka_vicko', WIN, SP, Z_CAP));
  for (const k of koruna()) g.add(k);
  plotny(g); ramena(g); logo(g); madlo(g); zapadky(g); pant(g);
  return g;
}
