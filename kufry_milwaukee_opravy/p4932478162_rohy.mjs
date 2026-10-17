// Čtyři svislé hliníkové tyče (stojí ≈ 10 mm od stěny) a osm černých rohových patek (4 horní, 4 dolní) XL boxu.
import { Part, Group, rbox, bx, cylX, cylY, loftBox, extXZ, extYZ, roundPoly } from './p4932478162_zaklad.mjs';
import { HX, HY, ROH, TYC } from './p4932478162_data.mjs';

// rohová patka: půdorys [|Y| yIn..yOut] × [|X| xIn..xOut] se zaoblením vnějšího rohu, výška z0..z1; zkosení vnější hrany nahoře/dole
function patka(name, sx, sy, z0, z1, { yIn = ROH.yIn, xIn = ROH.xIn, hi = true, xOut = HX } = {}) {
  const x0 = sx > 0 ? xIn : -xOut, x1 = sx > 0 ? xOut : -xIn;
  const y0 = sy > 0 ? yIn : -HY, y1 = sy > 0 ? HY : -yIn;
  const ru = 9;
  const L = (z, d) => ({ z, x0: x0 + (sx > 0 ? 0 : d), x1: x1 - (sx > 0 ? d : 0), y0: y0 + (sy > 0 ? 0 : d), y1: y1 - (sy > 0 ? d : 0), r: ru });
  // zkosení směrem ven (hrana, kde se patka stýká s víkem/dnem, je plná)
  const layers = hi ? [L(z0, 0), L(z1 - 14, 0), L(z1 - 2, 5), L(z1, 7)] : [L(z0, 7), L(z0 + 2, 5), L(z0 + 14, 0), L(z1, 0)];
  const body = loftBox('cerna', name, layers, { seg: 3, crease: 38 });
  return body;
}

export function rohy() {
  const g = new Group('rohy');
  for (const sx of [1, -1]) for (const sy of [1, -1]) {
    const id = (sx > 0 ? 'p' : 'z') + (sy > 0 ? '1' : '2');
    g.add(patka('patka_horni_' + id, sx, sy, ROH.zTopLo, ROH.zTopHi, { hi: true, yIn: ROH.yIn, xOut: HX }));
    g.add(patka('patka_dolni_' + id, sx, sy, ROH.zBotLo, ROH.zBotHi, { yIn: 238, xIn: 140, hi: false }));
    // šroub (ocel) na čelní a boční ploše patek
    const xs = sx * (HX - 0.4), ys = sy * (HY - 0.4);
    const zT = (ROH.zTopLo + ROH.zTopHi) / 2 + 6, zB = (ROH.zBotLo + ROH.zBotHi) / 2 - 8;
    const xTop = HX;
    g.add(cylX('ocel', 'srouby_x_' + id, 4.2, sx > 0 ? xTop - 1.5 : -xTop, sx > 0 ? xTop : -xTop + 1.5, sy * (HY - 22), zT, 14));
    g.add(cylX('ocel', 'srouby_xd_' + id, 4.2, sx > 0 ? HX - 1.5 : -HX, sx > 0 ? HX : -HX + 1.5, sy * (HY - 22), zB, 14));
    g.add(cylY('ocel', 'srouby_y_' + id, 4.0, sy > 0 ? HY - 1.5 : -HY, sy > 0 ? HY : -HY + 1.5, (sx > 0 ? HX - 27 : -HX + 27), zT, 14));
    // svislá drážka na čele patky (tmavá)
    g.add(bx('cerna_mat', 'patka_drazka_' + id, sx > 0 ? xTop - 1 : -xTop, sx > 0 ? xTop : -xTop + 1, sy * (HY - 33) - 1.5, sy * (HY - 33) + 1.5, ROH.zTopLo + 14, ROH.zTopHi - 14));
  }
  // hliníkové tyče: kvádr se zaoblením a třemi drážkami (tmavé linky), stojí na patkách
  for (const sx of [1, -1]) for (const sy of [1, -1]) {
    const id = (sx > 0 ? 'p' : 'z') + (sy > 0 ? '1' : '2');
    const xc = sx * TYC.xc, yc = sy * TYC.yc;
    g.add(rbox('hlinik', 'tyc_' + id, xc - TYC.d / 2, xc + TYC.d / 2, yc - TYC.w / 2, yc + TYC.w / 2, TYC.z0 - 2, TYC.z1 + 2, 3.5, 1.2, 3));
    for (const dy of [-5, 0, 5]) g.add(bx('cerna_mat', 'tyc_drazka_' + id, xc + (sx > 0 ? TYC.d / 2 - 0.6 : -TYC.d / 2 - 0.2), xc + (sx > 0 ? TYC.d / 2 + 0.2 : -TYC.d / 2 + 0.6), yc + dy - 0.7, yc + dy + 0.7, TYC.z0 + 4, TYC.z1 - 4));
  }
  return g;
}
