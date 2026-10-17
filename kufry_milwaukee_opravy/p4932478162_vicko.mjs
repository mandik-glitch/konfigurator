// Víko XL boxu: dutý plášť (vnitřní žebra), deska s 10 kapsami, větrání na čele, ouška pro spony; uzel `vicko` s pivotem na zadním pantu.
import { Part, Group, loftRings, rrPoly, bx, rbox, extYZ, extXZ, extrude, roundPoly, cylX, cylY, ccw, rectPoly } from './p4932478162_zaklad.mjs';
import { LID, Z_SEAM, HX, ROH } from './p4932478162_data.mjs';

// půdorys víka s rohovými výřezy pro rohové patky (nx × ny); rs = poloměry (pro všechny vrcholy stejný vzor)
export function lidPoly(x0, x1, y0, y1, nx, ny, r = 14, rn = 3) {
  const P = [
    [x1, y1 - ny], [x1 - nx, y1 - ny], [x1 - nx, y1],
    [x0 + nx, y1], [x0 + nx, y1 - ny], [x0, y1 - ny],
    [x0, y0 + ny], [x0 + nx, y0 + ny], [x0 + nx, y0],
    [x1 - nx, y0], [x1 - nx, y0 + ny], [x1, y0 + ny],
  ];
  // pořadí vrcholů: konvexní vnější rohy mezi výřezy → po zaoblení stále stejný počet bodů
  const R = [0.01, rn, 0.01, 0.01, rn, 0.01, 0.01, rn, 0.01, 0.01, rn, 0.01];
  return roundPoly(P, R, 2);
}
// půdorys bez výřezů zaoblený tak, aby měl stejný počet bodů jako lidPoly: výřez zmenšíme na minimum
export const LIDLAY = [
  { z: Z_SEAM, x0: -LID.xf, x1: LID.xf, y0: -LID.yw, y1: LID.yw, nx: 50, ny: 34 },
  { z: 164, x0: -LID.xf, x1: LID.xf, y0: -LID.yw, y1: LID.yw, nx: 50, ny: 34 },
  { z: 197, x0: -189, x1: 190, y0: -(LID.yw - 6), y1: LID.yw - 6, nx: 50, ny: 34 },
  { z: 198.2, x0: -187, x1: 188, y0: -(LID.yw - 8), y1: LID.yw - 8, nx: 1.5, ny: 1.5 },
  { z: 206, x0: -176, x1: 176, y0: -240, y1: 240, nx: 1.5, ny: 1.5 },
  { z: 209.5, x0: -163, x1: 163, y0: -229, y1: 229, nx: 1.5, ny: 1.5 },
];
const poly = L => lidPoly(L.x0, L.x1, L.y0, L.y1, L.nx, L.ny);

// 10 kapes: [x0,x1,y0,y1] – řady od zadní (-X) k přední (+X); malé × 4, dlouhé × 2, malé × 4 (odhad rozměrů z rektifikace)
const YI = [[37, 117], [137, 217]];
export const KAPSY_RADY = [
  { x0: -138, x1: -76, bloky: [[-217, -137], [-117, -37], [37, 117], [137, 217]] },
  { x0: -62, x1: 14, bloky: [[-217, -37], [37, 217]] },
  { x0: 28, x1: 94, bloky: [[-217, -137], [-117, -37], [37, 117], [137, 217]] },
];
export function kapsy() {
  const out = [];
  for (const r of KAPSY_RADY) for (const [y0, y1] of r.bloky) {
    const c = 9;   // sražené rohy
    out.push(roundPoly([[r.x1, y1], [r.x0, y1], [r.x0, y0], [r.x1, y0]], [c, c, c, c], 3));
  }
  return out;
}

export function vicko(uhelOtevreni = 0) {
  const g = new Group('vicko', { pivot: [-188, 0, 126], extras: { osa: [0, -1, 0], max_uhel: 105, popis: 'víko; pant vzadu (osa rovnoběžná s Y)' } });
  // plášť: vnější vrstvy nahoru, vnitřní (o stěnu 3,5) dolů; okraj dole uzavírá plášť
  const outer = LIDLAY.slice(0, 5);
  const t = 3.5;
  const inner = [
    { ...LIDLAY[4], z: 201, x0: LIDLAY[4].x0 + 8, x1: LIDLAY[4].x1 - 8, y0: LIDLAY[4].y0 + 8, y1: LIDLAY[4].y1 - 8 },
    { ...LIDLAY[3], z: 197, x0: LIDLAY[3].x0 + t, x1: LIDLAY[3].x1 - t, y0: LIDLAY[3].y0 + t, y1: LIDLAY[3].y1 - t },
    { ...LIDLAY[2], z: 190, x0: LIDLAY[2].x0 + t, x1: LIDLAY[2].x1 - t, y0: LIDLAY[2].y0 + t, y1: LIDLAY[2].y1 - t },
    { ...LIDLAY[1], x0: LIDLAY[1].x0 + t, x1: LIDLAY[1].x1 - t, y0: LIDLAY[1].y0 + t, y1: LIDLAY[1].y1 - t },
    { ...LIDLAY[0], x0: LIDLAY[0].x0 + t, x1: LIDLAY[0].x1 - t, y0: LIDLAY[0].y0 + t, y1: LIDLAY[0].y1 - t },
  ].map(L => ({ ...L, nx: L.nx, ny: L.ny }));
  const hood = new Part('vicko_plast', 'cerna_lesk'); hood.crease = 38;
  loftRings(hood, [...outer, ...inner].map(L => poly(L).map(q => [q[0], q[1], L.z])), { closed: true });
  g.add(hood);
  // horní deska s pocket-výřezy (plošina 205 → 211)
  const plate = extrude('cerna_lesk', 'vicko_deska', poly(LIDLAY[5]), kapsy(), 204.5, LID.zTop, { crease: 30 });
  g.add(plate);
  // dna kapes (pod deskou, vyčnívají dovnitř víka)
  for (const h of kapsy()) g.add(extrude('cerna', 'kapsa_dno', h, [], 198, 205.4, { top: true, bottom: true, crease: 30 }));
  // žebra uvnitř víka (mřížka 5 × 3 jako na Feat_1; odhad)
  for (const y of [-146, -88, -30, 30, 88, 146]) g.add(bx('cerna', 'zebro_y', -150, 150, y - 1.5, y + 1.5, 174, 199));
  for (const x of [-100, -20, 62]) g.add(bx('cerna', 'zebro_x', x - 1.5, x + 1.5, -216, 216, 174, 199));
  return g;
}

// větrání na čele víka (4 štěrbiny), ouška pro spony – součást víka (otáčejí se s ním)
export function vickoDetaily(g) {
  // blok větrání: zadní stěna + 5 svislých žeber
  g.add(rbox('cerna', 'vetrani_blok', 182, 195, -78, 72, 158, 198, 3, 1.5));
  for (let k = 0; k < 5; k++) { const y = -62 + k * 28; g.add(bx('cerna_mat', 'vetrani_zebro', 190, 196.5, y - 4.5, y + 4.5, 160, 196)); }
  // ouška spon na čele víka (černá), na nich oka pro třmen
  for (const s of [1, -1]) {
    const yc = s * 162;
    g.add(rbox('cerna', 'ouško_sponky' + (s > 0 ? '' : '_m'), 186, 196.5, yc - 38, yc + 38, 138, 192, 6, 2.5));
    g.add(bx('cerna_mat', 'ouško_zlab' + (s > 0 ? '' : '_m'), 195, 197, yc - 28, yc + 28, 147, 151));
  }
  // lišta pod švíkem
  g.add(rbox('cerna', 'vicko_lista', 190, 196.5, -245, 245, Z_SEAM - 1, Z_SEAM + 8, 4, 1.5));
}
