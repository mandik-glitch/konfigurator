// Milwaukee PACKOUT Organiser 4932464082 (standard, 10 nádob). Vlastní parametrický generátor podle fotografií výrobce.
// Souřadnice: X = šířka (čelo +X), Y = délka, Z = výška; počátek = střed obálky 386 × 500 × 117 mm.
import { Part, Group, roundedBox, hollowBox, box, prism, lathe, cylinder, tube } from './jadro/mesh.js';

export const SKU = '4932464082';
export const OBALKA = { x: 386, y: 500, z: 117 };
export const CELO = 'X';

const ZC = 117 / 2;                               // výška od nejnižšího bodu (patky) → střed obálky
const RB = (mat, name, o) => roundedBox(mat, name, { x0: o.u0, x1: o.u1, y0: o.v0, y1: o.v1, z0: o.z0 - ZC, z1: o.z1 - ZC, rc: o.rc ?? 0, re: o.re ?? 0, reB: o.reB, reT: o.reT, seg: o.seg ?? 4, fs: o.fs ?? 2 });
const HB = (mat, name, o) => hollowBox(mat, name, { x0: o.u0, x1: o.u1, y0: o.v0, y1: o.v1, z0: o.z0 - ZC, z1: o.z1 - ZC, rc: o.rc ?? 3, re: o.re ?? 1, wall: o.wall ?? 1.5, floor: o.floor ?? 1.5, seg: o.seg ?? 3, fs: o.fs ?? 2 });
const BX = (mat, name, u0, u1, v0, v1, z0, z1) => box(mat, name, u0, u1, v0, v1, z0 - ZC, z1 - ZC);
const zc = z => z - ZC;

export const P = {
  zBody0: 12.5, zSeam: 93.5, zTop: 117, zFloor: 16,
  tub: { u0: -181, u1: 181, v0: -243, v1: 243, rc: 16 },
  capLen: 54, capW: 34,
  latchV: 145,
  lid: { u0: -178, u1: 180, v0: -243, v1: 243, rc: 14 },
  bins: { rowH: 99, rowGap: 3.5, uCenter: -12, clusterV0: 27, clusterV1: 229, colGap: 4 },
};

// patky na spodku (mirror v ±); [v0,v1,uOdČela0,uOdČela1] (z měření spodní fotografie)
const PADS = [
  [38.6, 112.5, 101, 135], [144.3, 218.2, 101, 135],
  [50, 105, 208, 242], [153, 219, 208, 242],
  [37, 116.7, 307, 351], [140, 221.5, 307, 351],
];

function korpus() {
  const g = new Group('korpus');
  const t = P.tub;
  g.add(HB('cerna', 'vana', { u0: t.u0, u1: t.u1, v0: t.v0, v1: t.v1, z0: P.zBody0, z1: P.zSeam, rc: t.rc, re: 4, wall: 4, floor: P.zFloor - P.zBody0, seg: 4 }));
  for (const sv of [-1, 1]) for (const su of [-1, 1])
    g.add(RB('cerna', 'naraznik', { u0: su > 0 ? 193 - P.capLen : -193, u1: su > 0 ? 193 : -193 + P.capLen, v0: sv > 0 ? 250 - P.capW : -250, v1: sv > 0 ? 250 : -250 + P.capW, z0: P.zBody0 + 3, z1: 113.5, rc: 18, re: 3.5, seg: 5 }));
  for (const sv of [-1, 1]) for (const [a, b, f0, f1] of PADS) {
    const v0 = sv > 0 ? a : -b, v1 = sv > 0 ? b : -a;
    g.add(RB('cerna', 'patka', { u0: 193 - f1, u1: 193 - f0, v0, v1, z0: 0, z1: P.zBody0 + 1, rc: 4, re: 1.2, seg: 3 }));
  }
  return g;
}

function nadoby() {
  const g = new Group('nadoby');
  const b = P.bins, uc = b.uCenter;
  const rows = [uc + b.rowH + b.rowGap, uc, uc - b.rowH - b.rowGap];     // střed řad: přední (+X), prostřední, zadní
  for (const sv of [-1, 1]) {
    const c0 = b.clusterV0, c1 = b.clusterV1, w = (c1 - c0 - b.colGap) / 2;
    const vs = sv > 0 ? [c0, c0 + w, c0 + w + b.colGap, c1] : [-c1, -(c0 + w + b.colGap), -(c0 + w), -c0];
    rows.forEach((u, r) => {
      const big = r === 1;
      const cols = big ? [[vs[0], vs[3]]] : [[vs[0], vs[1]], [vs[2], vs[3]]];
      for (const [va, vb] of cols) g.add(HB('cervena', 'nadoba', { u0: u - b.rowH / 2, u1: u + b.rowH / 2, v0: va, v1: vb, z0: P.zFloor + 0.2, z1: 100, rc: 6, re: 1.5, wall: 1.8, floor: 2, seg: 3 }));
    });
  }
  g.add(BX('cerna', 'stredni_pruh', uc - 150, uc + 150, -22, 22, P.zFloor, 100));
  return g;
}

function vicko() {
  const L = P.lid, b = P.bins, uc = b.uCenter;
  const g = new Group('vicko', { pivot: [-186, 0, zc(P.zSeam + 3)], extras: { osa: [0, -1, 0], max_uhel: 110 } });
  // čiré víko = dutá skořepina otevřená dolů (hollowBox zrcadlený podle svislé osy)
  const h = HB('vicko_cira', 'vicko_plast', { u0: L.u0, u1: L.u1, v0: L.v0, v1: L.v1, z0: P.zSeam, z1: P.zTop, rc: L.rc, re: 2.5, wall: 2.5, floor: 2.2, seg: 4 });
  h.mirror('z', zc((P.zSeam + P.zTop) / 2));
  g.add(h);
  // kapsy víka nad každou nádobou (čiré misky 12 mm hluboké, okraj v rovině vršku)
  const rows = [uc + b.rowH + b.rowGap, uc, uc - b.rowH - b.rowGap];
  for (const sv of [-1, 1]) {
    const c0 = b.clusterV0, c1 = b.clusterV1, w = (c1 - c0 - b.colGap) / 2;
    const vs = sv > 0 ? [c0, c0 + w, c0 + w + b.colGap, c1] : [-c1, -(c0 + w + b.colGap), -(c0 + w), -c0];
    rows.forEach((u, r) => {
      const cols = r === 1 ? [[vs[0], vs[3]]] : [[vs[0], vs[1]], [vs[2], vs[3]]];
      for (const [va, vb] of cols) g.add(HB('vicko_cira', 'vicko_kapsa', { u0: u - b.rowH / 2 + 1, u1: u + b.rowH / 2 - 1, v0: va + 1, v1: vb - 1, z0: P.zTop - 13, z1: P.zTop - 1.2, rc: 5, re: 1.2, wall: 1.2, floor: 1.2, seg: 3 }));
    });
  }
  // čelní lem víka (žebrovaný) a čiré držáky třmenů nad západkami
  g.add(RB('vicko_cira', 'vicko_lem', { u0: 176, u1: 184.5, v0: -241, v1: 241, z0: P.zSeam, z1: P.zSeam + 12, rc: 3, re: 1.5, seg: 3 }));
  for (let k = -19; k <= 19; k++) g.add(BX('vicko_cira', 'vicko_lem_zebro', 184.5, 185.6, k * 12 - 0.7, k * 12 + 0.7, P.zSeam + 1, P.zSeam + 11));
  for (const s2 of [-1, 1]) g.add(RB('vicko_cira', 'vicko_drzak', { u0: 168, u1: 190, v0: s2 * P.latchV - 29, v1: s2 * P.latchV + 29, z0: P.zSeam, z1: P.zSeam + 12.5, rc: 3, re: 1.5, seg: 3 }));
  return g;
}

// eliptický prstenec/trubka podél osy X (vnější a vnitřní elipsa v rovině YZ), u0..u1
function prstenecX(mat, name, { u0, u1, vc, zc: z0, rvO, rzO, rvI, rzI, n = 28 }) {
  const p = new Part(name, mat);
  const ring = (rv, rz, u) => { const R = []; for (let i = 0; i < n; i++) { const a = 2 * Math.PI * i / n; R.push([u, vc + rv * Math.cos(a), z0 - ZC + rz * Math.sin(a)]); } return R; };
  // profil: vnější plocha od u0 do u1, přední čelo dovnitř, vnitřní stěna zpět; prstence jsou CCW při pohledu z +X
  const rings = [ring(rvO, rzO, u0), ring(rvO, rzO, u1), ring(rvI, rzI, u1), ring(rvI, rzI, u0)];
  loftPlain(p, rings, n);
  return p;
}
function loftPlain(p, rings, n) {
  const base = rings.map(r => r.map(q => p.addV(q[0], q[1], q[2])));
  for (let k = 0; k < rings.length - 1; k++) for (let i = 0; i < n; i++) { const j = (i + 1) % n; p.addQ(base[k][i], base[k][j], base[k + 1][j], base[k + 1][i]); }
  p.crease = 50;
}

function celo() {
  const g = new Group('celo');
  // --- západky (2×): černé pouzdro, červený jazyk s hřebenem, ocelový třmen, čirá úchytka na víku
  for (const s of [-1, 1]) {
    const v = s * P.latchV;
    g.add(RB('cerna', 'zamek_pouzdro', { u0: 168, u1: 186, v0: v - 31, v1: v + 31, z0: 36, z1: 93.5, rc: 3, re: 1.5 }));
    g.add(RB('cervena', 'zamek_jazyk', { u0: 181, u1: 188.5, v0: v - 21.5, v1: v + 21.5, z0: 22, z1: 71, rc: 4, re: 1.5, seg: 4 }));
    for (let k = 0; k < 4; k++) g.add(RB('cervena', 'zamek_hreben', { u0: 181, u1: 188.5, v0: v - 19.5 + k * 11.2, v1: v - 19.5 + k * 11.2 + 6.4, z0: 70, z1: 80, rc: 1.2, re: 0.8, seg: 2 }));
    for (let r = 0; r < 4; r++) g.add(BX('cerna', 'zamek_zebra', 188.5, 189.2, v - 14, v + 14, 24.5 + r * 2.6, 25.5 + r * 2.6));
    for (const sv of [-1, 1]) {
      const vv = v + sv * 24.5;
      g.add(tube('ocel', 'zamek_trmen', [[186.5, vv, zc(104)], [189.5, vv, zc(100)], [189.5, vv, zc(54)], [188.2, vv, zc(48)]], 1.35, 8));
    }
    g.add(tube('ocel', 'zamek_trmen_horni', [[189.5, v - 24.5, zc(102)], [189.5, v + 24.5, zc(102)]], 1.35, 8));
  }
  // --- černé lícnice kolem prohlubně držadla a rámečky západek
  for (const sv of [-1, 1]) g.add(RB('cerna', 'celo_licnice', { u0: 181, u1: 187.5, v0: sv > 0 ? 101 : -113, v1: sv > 0 ? 113 : -101, z0: 13, z1: 93.5, rc: 2.5, re: 1.2, seg: 3 }));
  g.add(RB('cerna', 'celo_nadprazi', { u0: 181, u1: 186, v0: -113, v1: 113, z0: 90.5, z1: 93.5, rc: 2, re: 1, seg: 3 }));
  for (const s2 of [-1, 1]) {
    const v = s2 * P.latchV;
    for (const sv of [-1, 1]) g.add(RB('cerna', 'zamek_ramecek', { u0: 181, u1: 190, v0: v + sv * 29 - 3.5, v1: v + sv * 29 + 3.5, z0: 24, z1: 93.5, rc: 2, re: 1.2, seg: 3 }));
    g.add(RB('cerna', 'zamek_ramecek_dole', { u0: 181, u1: 190, v0: v - 32.5, v1: v + 32.5, z0: 18, z1: 24, rc: 2, re: 1.2, seg: 3 }));
  }
  // --- držadlo: červený rám (spodní příčka + dva sloupky s hřebeny) + černý vroubkovaný úchop
  g.add(RB('cervena', 'drzadlo_pricka', { u0: 179, u1: 193, v0: -95, v1: 95, z0: 13.5, z1: 26, rc: 2.5, re: 1.5, seg: 3 }));
  g.add(RB('cervena', 'drzadlo_sloupek_L', { u0: 180, u1: 191, v0: -95, v1: -66, z0: 13.5, z1: 86, rc: 2.5, re: 1.5, seg: 3 }));
  g.add(RB('cervena', 'drzadlo_rameno_L', { u0: 180, u1: 190, v0: -70, v1: -52, z0: 50, z1: 88, rc: 6, re: 2, seg: 4 }));
  g.add(cylinder('ocel', 'drzadlo_cep', 2.2, 0, 3, 14, [0, 0]).rot('y', 90).move(190, -58, zc(78)));
  g.add(RB('cervena', 'drzadlo_sloupek_P', { u0: 180, u1: 191, v0: 62, v1: 95, z0: 13.5, z1: 82, rc: 2.5, re: 1.5, seg: 3 }));
  for (const [a, b, h] of [[-92, -85, 90], [-82, -75, 90], [66, 73, 86], [76, 83, 86], [86, 93, 86]])    // hřebeny na koncích sloupků
    g.add(RB('cervena', 'drzadlo_hreben', { u0: 180, u1: 191, v0: a, v1: b, z0: 78, z1: h, rc: 1, re: 0.8, seg: 2 }));
  g.add(RB('cerna_mat', 'drzadlo_uchop_zaklad', { u0: 183, u1: 190, v0: -55, v1: 60, z0: 21, z1: 40, rc: 3, re: 2, seg: 3 }));
  for (let k = 0; k < 19; k++) g.add(RB('cerna_mat', 'drzadlo_vroubek', { u0: 183, u1: 191, v0: -53 + k * 6.0, v1: -53 + k * 6.0 + 3.6, z0: 22, z1: 39, rc: 1.4, re: 1.2, seg: 2 }));
  // --- kroužek s oválným otvorem nad úchopem
  g.add(prstenecX('cervena', 'oval_kruzek', { u0: 176, u1: 186.5, vc: 16, zc: 65, rvO: 18.5, rzO: 18, rvI: 10.5, rzI: 9 }));
  return g;
}

export function build() {
  const root = new Group(SKU);
  root.addGroup(korpus()); root.addGroup(nadoby()); root.addGroup(celo()); root.addGroup(vicko());
  return root;
}
