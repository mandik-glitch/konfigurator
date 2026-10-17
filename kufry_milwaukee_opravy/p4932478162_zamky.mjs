// Spony (červená páka + ocelový třmen, samostatné uzly) a boční rukojeti (zapuštěné v pouzdrech, samostatné uzly) XL boxu.
import { Part, Group, bx, rbox, extYZ, extXZ, cylX, cylY, tube, roundPoly, extrude } from './p4932478162_zaklad.mjs';
import { ZAMEK_Y, HX } from './p4932478162_data.mjs';

// jedna sponka: páka (červená) pivotuje na spodním čepu v kapse čela, třmen na čepu pod ouškem víka
function sponka(s) {
  const yc = s * ZAMEK_Y, id = s > 0 ? 'P' : 'L';
  const gr = new Group('sponka_' + id);
  const piv = [184, yc, 60];
  const lever = new Group('paka_' + id, { pivot: piv, extras: { osa: [0, 1, 0], max_uhel: 75, popis: 'červená páka spony (čepem dole)' } });
  // tělo páky (profil v YZ)
  const body = roundPoly([[yc - 28, 58], [yc + 28, 58], [yc + 28, 116], [yc - 28, 116]], [4, 4, 6, 6], 3);
  lever.add(extYZ('cervena', 'paka_telo_' + id, body, 183, 195.5, 30));
  // prsty (4 žebra nahoře) – úchop
  for (let k = 0; k < 4; k++) { const y = yc - 23.5 + k * 12.6; lever.add(extYZ('cervena', 'paka_prst_' + id + k, roundPoly([[y, 114], [y + 8.8, 114], [y + 8.8, 132], [y, 132]], [1.5, 1.5, 3, 3], 2), 183, 195.5, 25)); }
  // příčná žebra ve spodní části páky + zvýšený štítek
  for (let k = 0; k < 4; k++) lever.add(bx('cervena', 'paka_zebro_' + id + k, 194.5, 196.5, yc - 22, yc + 22, 60 + k * 3.6, 62 + k * 3.6));
  lever.add(rbox('cervena_mat', 'paka_stitek_' + id, 194.5, 196.8, yc - 20, yc + 20, 78, 104, 3, 0.5));
  gr.addGroup(lever);
  // třmen: ocelový drát Ø4,2, otočný kolem spodních konců
  const tr = new Group('trmen_' + id, { pivot: [194.2, yc, 100], extras: { osa: [0, 1, 0], max_uhel: 80, popis: 'ocelový třmen spony' } });
  const w = 35.5, zt = 176, r = 2.1, xw = 194.2;
  const P = [[xw, yc - w, 102], [xw, yc - w, zt - 7], [xw, yc - w + 1.2, zt - 2.3], [xw, yc - w + 7, zt], [xw, yc + w - 7, zt], [xw, yc + w - 1.2, zt - 2.3], [xw, yc + w, zt - 7], [xw, yc + w, 102]];
  tr.add(tube('ocel', 'trmen_drat_' + id, P, r, 8));
  gr.addGroup(tr);
  return gr;
}

export function spony() { const g = new Group('spony'); g.addGroup(sponka(1)); g.addGroup(sponka(-1)); return g; }

// boční rukojeť v pouzdře (zapuštěná; uzel s čepem nahoře, osa X): dvě červené vidlice s hřebeny nahoře, spodní červená příčka a černý gumový úchop
export function rukojetBok(s, POC) {
  const id = s > 0 ? 'P' : 'L', y0 = 223.5, y1 = 232;
  const piv = [3, s * 222, 118];
  const g = new Group('rukojet_bok_' + id, { pivot: piv, extras: { osa: [s > 0 ? 1 : -1, 0, 0], max_uhel: 60, popis: 'boční rukojeť (zapuštěná v pouzdře), čep nahoře' } });
  const yA = s > 0 ? y0 : -y1, yB = s > 0 ? y1 : -y0;
  const ucho = (xa, xb, nm) => {
    const poly = roundPoly([[xa, 46], [xb, 46], [xb, 126], [xb - 7, 126], [xb - 7, 112], [xa + 7, 112], [xa + 7, 126], [xa, 126]], [4, 4, 1, 1, 1, 1, 1, 1], 2);
    g.add(extXZ('cervena', nm + id, poly, yA, yB, 30));
  };
  ucho(-112, -86, 'rukojet_bok_ucho_'); ucho(88, 114, 'rukojet_bok_ucho2_');
  g.add(rbox('cervena', 'rukojet_bok_pricka_' + id, -112, 114, s > 0 ? y0 : -(y1 + 2), s > 0 ? y1 + 2 : -y0, 46, 60, 4, 2));
  g.add(rbox('guma', 'rukojet_bok_uchop_' + id, -84, 88, s > 0 ? y0 + 1 : -(y1 + 6), s > 0 ? y1 + 6 : -(y0 + 1), 58, 76, 4, 3));
  g.add(cylY('ocel', 'rukojet_bok_cep_' + id, 4, s > 0 ? y1 : -(y1 + 3), s > 0 ? y1 + 3 : -y1, -99, 116, 12));
  g.add(cylY('ocel', 'rukojet_bok_cep2_' + id, 4, s > 0 ? y1 : -(y1 + 3), s > 0 ? y1 + 3 : -y1, 101, 116, 12));
  return g;
}
