// Korpus (spodní díl) Hilti Kufr 2-tools (M) SF/SI+TE (2329206): červená vana (vnější plášť) + černá vložka (hladká dutina), okno madla skrz celou tloušťku,
// kapsy západek v čele, boční vybouleniny, hladké dno. Vnitřek je zjednodušený (prázdná dutina bez přihrádek).
// Míry z fotografie c01 (pohled shora na zavřený kufr; převod px → mm viz p2329206_zaklad.mjs: pX, pY). Co z fotografií vyčíst nejde (výšky, dno, bok), je
// v poznámkách označeno „odhad“ / „neověřeno“.
import { Group, Part, vanaH, trubka, prstenec, extYZ, bx, rb, cylinder, zc, pX, pY } from './p2329206_zaklad.mjs';

// z' = výška od spodní plochy kufru (0..175). SP = dělicí spára víko/korpus – NENÍ změřena (žádný boční pohled), odhad.
export const SP = +(process.env.KUF_SP || 90);
export const Z_CAP = 163;          // horní plocha skořepiny víka (dno drážky s logem), odhad
export const Z_PL = 172;           // plató víka, odhad
export const Z_PAD = 175;          // vršek stohovacích ploten = celková výška 175 (katalog)

// obrys půdorysu (z c01): čelní hrana X 223,6 (py 14), zadní X −229, šířka 589 + boční vybouleniny (Y ±297,5 jen v pásu X −58,8..78,5, c01 py 310..590),
// zkosený roh čelo→bok s mezibody podle okraje c01 (px 170/100/54/30/14, py 18/25/36/42/48), zadní roh zúžený o ~12 mm (c01 px 23, py 880..939).
export const D = { XF: 223.6, XR: -229, Y: 297.5, YF: 220, CFX: 23, RR: 10, DR: 11.7, CM: [[0.235, 0.356], [0.47, 0.649], [0.597, 0.80], [0.72, 0.906], [0.98, 0.951]] };
export const S = (z, d = 0) => ({ z, xf: D.XF - d, xr: D.XR + d, y0: -(D.Y - d), y1: D.Y - d, yF: D.YF - d * 0.3, cfx: D.CFX, rr: D.RR, dr: D.DR, cm: D.CM });
export const enFR = (z0, z1) => [
  { fr: [{ z: z0, x0: 78.5, x1: D.XF - D.CFX, d: 3 }, { z: z1, x0: 78.5, x1: D.XF - D.CFX, d: 3 }] },
  { fr: [{ z: z0, x0: -201, x1: -58.8, d: 3 }, { z: z1, x0: -201, x1: -58.8, d: 3 }] },
];

// okno madla (průchozí, bílé na c01): lichoběžník px 448..750 × py 66..125 (zúžení od py 80), souměrně kolem Y = 0; polygony CCW (X doprava, Y nahoru)
export const WIN = [[169.2, -51.3], [191.3, -74.5], [198.1, -74.5], [198.1, 74.5], [191.3, 74.5], [169.2, 51.3]];
// vnější obrys rámu madla (šedý): px 383..814 (Y ±107), py 0..75 (čelo X 230,5 .. 193,7), zúžení k py 143 (X 160,1; Y ±66)
export const FRAME = [[160.1, -66], [193.7, -107], [230.5, -107], [230.5, 107], [193.7, 107], [160.1, 66]];
export const orientace = P => { let a = 0; for (let i = 0; i < P.length; i++) { const p = P[i], q = P[(i + 1) % P.length]; a += p[0] * q[1] - q[0] * p[1]; } return a / 2; };

// kapsy západek v čele (c01: pouzdro px 131..299, py 15..100; rovná část čelní hrany končí v Y 220, proto kapsa jen 149..220)
export const LAT = { nx: pX(100) };
export const LAT_Y = [149, 220];
export const LAT_BLK = { x0: pX(77), x1: pX(15), ya: pY(292), yb: pY(157) };   // černý blok západky (c01 px 157..292, py 15..77) → Y 152,5..219,5 (levá strana fotografie = +Y)

function cylY(mat, name, r, y0, y1, x, z, n = 20) {
  return cylinder(mat, name, r, y0, y1, n, [0, 0]).mapV((u, v, w) => [u + x, w, v + zc(z)]).flip();
}
export const HINGE = { x: -223.7, r: 6.8 };
export function hingeRadius(h) { return Math.abs((h.a + h.b) / 2) < 124 ? 5.6 : HINGE.r; }   // c01: střed (|Y| < 124) končí o 2,5 mm dřív než kraje
export function hingeSegments() {
  // 7 článků pantu po délce (c02: ~9 malých článků; počet a rozteč neověřeny), střídavě korpus / víko
  const n = 7, y0 = -283, y1 = 283, seg = (y1 - y0) / n, out = [];
  for (let i = 0; i < n; i++) out.push({ i, a: y0 + i * seg + 0.8, b: y0 + (i + 1) * seg - 0.8 });
  return out;
}

export function korpus() {
  const g = new Group('korpus');
  const fr = [S(0, 4.5), S(2, 1.8), S(5, 0.4), S(9, 0), S(SP - 1.4, 0), S(SP, 0.7)];
  const notches = [
    { fr: [{ z: SP - 30, y0: -LAT_Y[1], y1: -LAT_Y[0], nx: LAT.nx }, { z: SP, y0: -LAT_Y[1], y1: -LAT_Y[0], nx: LAT.nx }] },
    { fr: [{ z: SP - 30, y0: LAT_Y[0], y1: LAT_Y[1], nx: LAT.nx }, { z: SP, y0: LAT_Y[0], y1: LAT_Y[1], nx: LAT.nx }] },
  ];
  const [plast, vlozka] = vanaH('cervena', 'cerna', 'korpus_vana', { frames: fr, notches, enotches: enFR(0, SP), wall: 3.5, floorZ: 9, holePolys: [WIN] });
  g.add(plast, vlozka);
  g.add(trubka('seda', 'okno_trubka_korpus', WIN, 0, SP));
  // rám madla korpusu (červený držák kolem okna) a černá rukojeť (gumová příčka) – vidět jen u otevřeného kufru (c02); poloha/výška neověřena
  g.add(prstenec('cervena', 'drzak_madla', FRAME.map(([x, y]) => [Math.min(x, 224.5), y]), WIN, SP - 18, SP - 0.5));
  g.add(rb('cerna_mat', 'rukojet_korpus', { x0: pX(70), x1: 226, y0: -99, y1: 99, z0: SP - 16, z1: SP - 2, rc: 5, re: 3, seg: 3, fs: 2 }));
  // západky (černé bloky v kapsách; pozice zavřené západky – u otevřeného víka se objeví i na víku, viz p2329206_vicko.mjs)
  for (const s of [-1, 1]) {
    g.add(rb('cerna', 'zapadka_korpus', { x0: LAT_BLK.x0 + 6, x1: LAT_BLK.x1 + 1, y0: s < 0 ? -LAT_BLK.yb : LAT_BLK.ya, y1: s < 0 ? -LAT_BLK.ya : LAT_BLK.yb, z0: SP - 28, z1: SP - 1, rc: 3, re: 2.2, seg: 2, fs: 2 }));
  }
  // pant: články korpusu (liché)
  for (const h of hingeSegments()) if (h.i % 2 === 1) g.add(cylY('cervena', 'pant_clanek', hingeRadius(h), h.a, h.b, HINGE.x, SP));
  return g;
}
