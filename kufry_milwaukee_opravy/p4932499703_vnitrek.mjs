// Box s vložnými panely 4932499703 / 4932499704: dva panely v těle (levý hladký, pravý s 4 vysokými látkovými kapsami při zadní hraně),
// panel ve víku s červeným lemem, červeným štítkem a pásem červených pružných úchytů. Zdroj: fotografie c01 (shora, otevřený box) + doplňkové fotografie sady 4932499466/467 (viz zdroje/*_poznamky.md).
import { Group, Part, slab, rrFrame, bx, extYZ, zc } from './p4932464079_zaklad.mjs';

// obdélníkový panel s červeným lemem: x0..x1, y0..y1, z0..z1 (z'); černá plsť + červená obruba 4 mm
function panel(g, nm, { x0, x1, y0, y1, z0, z1 }) {
  g.add(slab('cerna_mat', nm + '_deska', { x0, x1, y0, y1, z0, z1, rs: 5, seg: 3, reT: 1.2, reB: 0.8, fs: 2 }));
  g.add(rrFrame('cervena', nm + '_lem', { x0: x0 - 0.3, x1: x1 + 0.3, y0: y0 - 0.3, y1: y1 + 0.3, z0: z1 - 2.6, z1: z1 + 0.4, w: 4.2, rs: 5, seg: 3 }));
}

export function vlozkyTelo(V) {
  const zs = V.H - V.lidH, root = new Group('vlozky');
  const zL = 58, zR = 66, tP = 8;
  // levý panel (hladký, pod pravým; Y -242 .. +70 – zakrytá část je odhad)
  const gl = new Group('panel_levy', { pivot: [0, -90, zc(zL + tP)], extras: { poznamka: 'vložný panel (levý, hladký); zakrytá část pod pravým panelem je odhad' } });
  panel(gl, 'panel_levy', { x0: -146, x1: 144, y0: -244, y1: 70, z0: zL, z1: zL + tP });
  // podložka až k dnu (aby panel nevisel) – jen pod okraji
  gl.add(bx('cerna_mat', 'panel_levy_podpora', -140, 138, -238, 64, 7, zL));
  root.addGroup(gl);
  // pravý panel (s kapsami)
  const gp = new Group('panel_pravy', { pivot: [0, 60, zc(zR + tP)], extras: { poznamka: 'vložný panel (pravý) se 4 vysokými látkovými kapsami při zadní hraně' } });
  panel(gp, 'panel_pravy', { x0: -145, x1: 143, y0: -108, y1: 236, z0: zR, z1: zR + tP });
  // 4 vysoké látkové kapsy ≈ 75 × 130 mm (Y × X) při zadní hraně
  const yc = [-52, 28, 107, 187];
  yc.forEach((c, i) => {
    gp.add(slab('cerna_mat', 'kapsa_latka_' + (i + 1), { x0: -143, x1: -143 + 128, y0: c - 37, y1: c + 37, z0: zR + tP - 0.5, z1: zR + tP + 17, rs: 5, seg: 2, reT: 7, reB: 0.5, fs: 3 }));
    gp.add(slab('cerna', 'kapsa_okraj_' + (i + 1), { x0: -143 + 126, x1: -143 + 129.5, y0: c - 36, y1: c + 36, z0: zR + tP - 0.3, z1: zR + tP + 12, rs: 1, seg: 1, reT: 3, reB: 0.3, fs: 2 }));
    gp.add(bx('seda', 'kapsa_nit_' + (i + 1), -141, -139, c - 3, c + 3, zR + tP + 14.8, zR + tP + 17.2));
  });
  // černé poutko u přední hrany (odhad podle fotografie)
  gp.add(slab('cerna_mat', 'panel_poutko', { x0: 108, x1: 126, y0: 20, y1: 62, z0: zR + tP - 0.3, z1: zR + tP + 3.5, rs: 3, seg: 2, reT: 1.2, reB: 0.2, fs: 1 }));
  root.addGroup(gp);
  return root;
}

// panel ve víku (součást víka – přidává se do skupiny víka): visí pod stropem
export function vlozkaVicko(V, vk) {
  const H = V.H, zc0 = H - 17.5;
  const z1 = zc0, z0 = zc0 - 9;
  panel(vk, 'vicko_panel', { x0: -150, x1: 150, y0: -246, y1: 246, z0, z1: z1 });
  // červený štítek Milwaukee v rohu u čela (vlevo)
  vk.add(slab('cervena', 'vicko_stitek_milwaukee', { x0: 118, x1: 140, y0: -222, y1: -168, z0: z0 - 0.8, z1: z0 + 0.2, rs: 1.5, seg: 1, reT: 0.2, reB: 0.2, fs: 1 }));
  // pás se pružnými úchyty (u pantové hrany): černá lišta + červené "prsty"
  vk.add(slab('cerna', 'vicko_pas_lista', { x0: -142, x1: -98, y0: -192, y1: 192, z0: z0 - 20, z1: z0 + 0.5, rs: 2, seg: 2, reT: 1, reB: 3, fs: 2 }));
  const n = 64;
  for (let k = 0; k < n; k++) {
    const y = -190 + (380 / (n - 1)) * k, a = (k % 2) * 3;
    vk.add(slab('cervena', 'vicko_uchyt', { x0: -108 - a, x1: -97 + 7 + a * 0.5, y0: y - 1.5, y1: y + 1.5, z0: z0 - 17, z1: z0 - 3, rs: 0.3, seg: 1, reT: 0.8, reB: 0.2, fs: 1 }));
  }
}
