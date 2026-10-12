// Víko DeWalt TSTAK IP54: dutý plášť (lem při spáře, zešikmené konce a rameno čela), kapsa pro sklopné držadlo, ostrůvek s logem DEWALT a štítkem TSTAK,
// štítky IP54, žluté stohovací háky na koncích, sklopné držadlo (skupina `drzadlo`, pivot vpředu na kapse).
// Víko = skupina `vicko`; pant je na fotografiích neviditelný (zadní strana se nefotí) – pivot je ODHAD na zadní hraně spáry (viz poznámky).
import { Group, S, zs, zf, vickoPlast, vyrez, bx, rb, extYZ, mirY, cylZ, zc } from './tstak_zaklad.mjs';

export const V = {
  xRim0: -166.5, xRim1: 162,       // lem víka (obálka −166,5; čelo lemu 162, západky dosahují 166,5)
  y: 220,                          // polovina délky (obálka)
  zRimH: 22,                       // výška lemu nad spárou
  rec: { x0: -52, x1: 62, y: 89, dno: 16 },   // kapsa držadla na horní ploše: hloubka 16 mm pod temenem
  piv: { x: 55, zDol: 9 },         // pivot držadla (vpředu na kapse), z' = H − 9
};

export function vicko() {
  const H = S.H, Z = zs(), Zf = zf(), ZT = H - 0.6;
  const g = new Group('vicko', { pivot: [-160, 0, zc(Z)], extras: { osa: [0, -1, 0], poznamka: 'pant neviditelný na fotografiích; pivot odhadnut na zadní hraně spáry' } });
  // --- plášť víka ---
  const T = S.trim;
  const FR = [
    { z: Z, xr: V.xRim0 + T, xf: V.xRim1, y: V.y, rc: 10 },
    { z: Zf + 21, xr: V.xRim0 + T, xf: V.xRim1, y: V.y, rc: 10 },
    { z: Zf + V.zRimH, xr: -164 + T, xf: 160.5, y: 218.4, rc: 12 },
    { z: H - 12, xr: -160 + T, xf: 158, y: 209, rc: 24 },
    { z: ZT, xr: -148 + T, xf: 107, y: 199, rc: 25 },
  ];
  const r = V.rec;
  g.add(vickoPlast('cerna', 'vicko_plast', FR, { wall: 3.5, topT: 3.5, holes: [{ x0: r.x0, x1: r.x1, y0: -r.y, y1: r.y }] }));
  g.add(vyrez('cerna_mat', 'vicko_kapsa', r.x0, r.x1, -r.y, r.y, H - r.dno, ZT));
  // --- čelní sloupky víka (rohové bloky nad západkami, y 108…172): mírně předsazené před čelo, mezi sloupkem a ostrůvkem je drážka ---
  for (const s of [-1, 1]) g.add(rb('cerna', 'sloupek' + (s < 0 ? '_l' : '_p'), { x0: 100, x1: 160.8, y0: s < 0 ? -172 : 108, y1: s < 0 ? -108 : 172, z0: Zf + V.zRimH, z1: H - 11, rc: 4, re: 1.6, seg: 1, fs: 1 }));
  // --- ostrůvek s logem a štítkem TSTAK (čelo, uprostřed) ---
  g.add(rb('cerna', 'ostruvek', { x0: 98, x1: 159, y0: -92, y1: 92, z0: H - 50, z1: H - 4, rc: 3, re: 1.2, seg: 1, fs: 1 }));
  g.add(bx('zluta', 'logo_dewalt', 120, 146, -57, 57, H - 4.2, H - 3.6));
  g.add(bx('zluta', 'stitek_tstak', 159, 159.5, -47, 47, Zf + 36, Zf + 51));
  g.add(bx('cira', 'stitek_tstak_kryt', 159.3, 160.3, -51, 51, Zf + 34, Zf + 53.5));
  // --- žlutý proužek pod ostrůvkem na lemu (c02, vlevo od středu) ---
  g.add(bx('zluta', 'prouzek_zluty', 161.6, 162.8, -90, -36, Zf + 11, Zf + 17));
  // --- štítky IP54 na čelech levého a pravého sloupku (c02: y −162…−118) ---
  for (const s of [-1]) {   // štítek IP54 je na fotografiích jen vlevo (pohled zepředu)
    const a = s < 0 ? -162 : 118, b = s < 0 ? -118 : 162, nm = s < 0 ? '_l' : '_p';
    g.add(bx('zluta', 'stitek_ip54' + nm, 160.6, 162.0, a, b, Zf + 23, Zf + 54));
    g.add(bx('cerna_mat', 'stitek_ip54_pole' + nm, 160.9, 162.3, a + 1.6, b - 1.6, Zf + 25, Zf + 52));
  }
  // --- žluté stohovací háky na koncích víka (c01/c02: na horní ploše u konců, přes rameno konce) ---
  const tab = [[182, H - 0.1], [200.3, H - 0.1], [211.0, H - 12.0], [212.2, H - 13.2], [210.6, H - 14.8], [190, H - 4], [182, H - 4]];
  const hook = extYZ('zluta', 'hak_stoh_p', tab, -44, 90);
  g.add(hook); g.add(mirY(hook, 'hak_stoh_l'));
  // --- důlky pro stohovací čepy (6 ks) – jen tmavé terčíky na horní ploše ---
  for (const y of [-150, 150]) for (const x of [-95, 20]) g.add(cylZ('cerna_mat', 'cep_dulek', 4.2, ZT - 0.05, ZT + 0.25, x, y, 14));
  // --- držadlo (sklopené v kapse; skupina drzadlo, otočení kolem osy Y v pivotu) ---
  const px = V.piv.x, pz = H - V.piv.zDol;
  const h = new Group('drzadlo', { pivot: [px, 0, zc(pz)], extras: { osa: [0, 1, 0], poznamka: 'kladný úhel zvedne držadlo (c01/c02 mělký: ~80°)' } });
  h.add(rb('cerna', 'drzadlo_hmat', { x0: -30, x1: 0, y0: -87, y1: 87, z0: H - 18, z1: H - 4, rc: 4, re: 2.5, seg: 2, fs: 2 }));
  for (const s of [-1, 1]) h.add(rb('cerna', 'drzadlo_rameno' + (s < 0 ? '_l' : '_p'), { x0: -30, x1: px + 4, y0: s < 0 ? -87 : 64, y1: s < 0 ? -64 : 87, z0: H - 14.5, z1: H - 4, rc: 2, re: 1.5, seg: 1, fs: 1 }));
  h.add(bx('cerna_mat', 'drzadlo_logo', -20, -10, -30, 30, H - 4.2, H - 3.8));
  g.addGroup(h);
  return g;
}
