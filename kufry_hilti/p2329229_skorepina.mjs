// Společná skořepina kufru Hilti 495 × 395 × 149 (víko + spodní díl) – parametrizovaná daty z fotografie c01 (pohled shora na zavřený kufr).
// Používají ji kufr_2329229.mjs (data p2329229_data.mjs) a kufr_2294834.mjs (data p2294834_data.mjs). Obálka je u obou stejná (katalog hilti.cz),
// vnější reliéf víka (madlo, západky, žebra, logo) se podle fotografií liší, proto jsou data dvě – viz zdroje/*_poznamky.md.
// Zavřená verze a vnější pohled; vnitřek je zjednodušen (hladká dutina, stěna 3 mm). Svislé míry (dělicí spára, výška desky, hloubka drážky) jsou ODHAD – boční pohled chybí.
import { Group, conv, mirrorFull, ccw, inset, dirD, lidShell, baseTray, lofted, padLoft, extrude, rb, cylY, zc } from './p2329229_zaklad.mjs';
import { MATERIALY } from '../kufriky_cloud/jadro/glb.js';

// bílé logo: materiál se doplňuje za běhu (glb.js se nemění); odstín podle fotografie (bílá ≈ 0,96 lineárně)
MATERIALY.logo_bila = { color: [0.93, 0.93, 0.93], metallic: 0.0, roughness: 0.45 };

export const Z = { zs: 88, zT: 140, zP: 146, zB: 149 };   // dělicí spára; deska víka; plató; vrch stohovacích nopů (z' v mm, odhad)
export const HX = -190;                                   // osa pantu (X)

export function skorepina(D) {
  const c = conv(D.W, D.H), PT = p => c.pt(p);
  const { zs, zT, zP, zB } = Z;
  const toPoly = pxList => pxList.map(PT);
  const mirX = pts => pts.map(([x, y]) => [D.W - 1 - x, y]);
  // ---------- půdorysy (px → mm), pravá polovina → celý polygon ----------
  const Pbase = ccw(toPoly(mirrorFull([...D.bay, ...D.front, ...D.side], D.W)));
  const Plid = ccw(toPoly(mirrorFull([...D.bay, ...D.frontLid, ...D.side], D.W)));

  // ---------- spodní díl ----------
  const korpus = new Group('korpus');
  korpus.add(baseTray('cervena', 'korpus_vana', Pbase, { z1: zs, rB: 2.5, wall: 3, floor: 3, groove: 0.6 }));
  // vložka (zjednodušená): hladká černá deska bez kapes – na fotografiích je dutina vyplněná černou tvarovanou vložkou; kapsy nemodelovány
  korpus.add(extrude('cerna_mat', 'vlozka_zjednodusena', inset(Pbase, 3.4, ), 3, zs - 6));
  // límec kolem okna madla (deska ve tvaru U): vrstvy D.collar = [{mat, outer, inner}] v px (cesta zleva doprava), pod víkem
  for (const L of D.collar) korpus.add(extrude(L.mat, 'madlo_lem', toPoly([...L.outer, ...L.inner.slice().reverse()]), zs - 5, zs - 1));
  // madlo: černá příčka přes okno u čela – spodní polovina (grip, zůstává ve spodním dílu); výška odhad
  const [bx0, bx1, by0, by1] = D.bar, bA = PT([bx0, by0]), bB = PT([bx1, by1]);
  const barBox = (z0, z1, name) => rb('cerna', name, { x0: Math.min(bA[0], bB[0]), x1: Math.max(bA[0], bB[0]), y0: Math.min(bA[1], bB[1]), y1: Math.max(bA[1], bB[1]), z0, z1, rc: 2, re: 3, seg: 2, fs: 2 });
  korpus.add(barBox(zs - 8, zs + 20, 'madlo_pricka_spodni'));
  // pant: spodní články (liché úseky) a černý kolík; osa Y u zadní hrany, neověřeno (zadní strana na fotografiích není)
  const seg = 480 / 7;
  for (let i = 1; i < 7; i += 2) korpus.add(cylY('cervena', 'pant_clanek', 5.2, -240 + i * seg + 0.6, -240 + (i + 1) * seg - 0.6, HX, zs, 16));
  korpus.add(cylY('cerna', 'pant_kolik', 1.8, -241, 241, HX, zs, 10));

  // ---------- víko ----------
  const vicko = new Group('vicko', { pivot: [HX, 0, zc(zs)], extras: { osa: [0, -1, 0], max_uhel: 135 } });
  vicko.add(lidShell('cervena', 'vicko_plast', Plid, { z0: zs, z1: zT, drop: 7, runs: [8, 11, 8], wall: 3 }));
  // horní polovina madla: černá příčka a límec okna (U) u horní hrany víka – to je vidět na pohledu shora; otevřené víko je nese s sebou
  vicko.add(barBox(zs + 20, D.barTop, 'madlo_pricka_horni'));
  for (const L of D.collar) vicko.add(extrude(L.mat, 'madlo_lem_vicko', toPoly([...L.outer, ...L.inner.slice().reverse()]), zT - 12, zT - 8));
  // plató (přední a zadní) nad deskou; mezi nimi drážka s logem (zP − zT hluboká)
  for (const pd of D.pads) vicko.add(padLoft('cervena', pd.name, toPoly(pd.B), pd.runs, zT, zP, zT - 7));
  // stohovací nopy na plató (čtyři; obdélník v px, levý a zrcadlový pravý)
  for (const r of D.bosses) for (const rr of [r, [D.W - 1 - r[1], D.W - 1 - r[0], r[2], r[3]]]) {
    const [x0, x1, y0, y1] = rr;
    vicko.add(padLoft('cervena', 'nop', toPoly([[x0, y0], [x1, y0], [x1, y1], [x0, y1]]), [3.5, 3.5, 3.5], zP, zB, zP));
  }
  // logo HILTI: bílé plošky v drážce (písmena z fotografie c01 – obdélníkové obrysy)
  for (const L of D.logo) vicko.add(extrude('logo_bila', 'logo_hilti', toPoly(L), zT - 0.2, zT + 0.45));
  // západky: černé bloky v kapsách u čela (levý a zrcadlový pravý); kapsa = výřez půdorysu víka, dno kapsy = červená deska na okraji spodního dílu
  for (const L of [D.latch, mirX(D.latch).reverse()]) {
    const B = ccw(toPoly(L));
    vicko.add(lofted('cerna', 'zapadka_blok', B, inset(B, 3), zs, zT - 2));
  }
  for (const L of [D.pocket, mirX(D.pocket).reverse()]) vicko.add(extrude('cervena', 'zapadka_kapsa_dno', toPoly(L), zs, zs + 3));
  // pant: horní články (sudé úseky)
  for (let i = 0; i < 7; i += 2) vicko.add(cylY('cervena', 'pant_clanek_vicko', 5.2, -240 + i * seg + 0.6, -240 + (i + 1) * seg - 0.6, HX, zs, 16));
  return { korpus, vicko };
}
