// Pojízdný box 4932498651 – zásuvka (samostatný posuvný uzel `zasuvka`, osa X, zdvih ≈ 330 mm – odhad z c02, skutečný zdvih nelze z fotky změřit).
import { Part, Group, rrPoly, loftBox, loftVessel, rbox, bx, extYZ, extXZ, cylX, cylY, extrude, roundPoly, tube } from './p4932478162_zaklad.mjs';
import { ZASUVKA as Z } from './p4932498651_data.mjs';
import { logoXL } from './p4932478162_logo.mjs';

export function zasuvka() {
  const g = new Group('zasuvka', { pivot: [0, 0, 0], extras: { osa: [1, 0, 0], max_posuv: Z.zdvih, popis: 'výsuvná zásuvka (posuv podél +X); zdvih je odhad' } });
  const w = 4.5;
  // vana zásuvky: vnější stěny zdola nahoru, okraj, vnitřní stěny dolů (dno)
  const L = (z, d, r = 12) => ({ z, x0: Z.x0 + d, x1: 223 - d, y0: -Z.y + d, y1: Z.y - d, r });
  g.add(loftVessel('cerna', 'zasuvka_vana', [L(Z.z0, 8, 16), L(Z.z0 + 8, 0), L(Z.z1, 0)], [L(Z.z1, w), L(Z.z0 + 14, w), L(Z.z0 + 8 + 2, w + 6)], { seg: 4, crease: 38 }));
  // horní okraj (lem) se zkosením
  g.add(loftVessel('cerna', 'zasuvka_lem', [{ z: Z.z1 - 8, x0: Z.x0 - 2, x1: 225, y0: -Z.y - 2, y1: Z.y + 2, r: 13 }, { z: Z.z1 + 1, x0: Z.x0 - 3, x1: 226, y0: -Z.y - 3, y1: Z.y + 3, r: 13 }],
    [{ z: Z.z1 + 1, x0: Z.x0 + 1, x1: 221, y0: -Z.y + 1, y1: Z.y - 1, r: 11 }, { z: Z.z1 - 8, x0: Z.x0 + 2, x1: 220, y0: -Z.y + 2, y1: Z.y - 2, r: 11 }], { seg: 4 }));
  // žebrování bočních stěn (3 svislé štěrbiny jako na c02 + žebra)
  for (const s of [1, -1]) for (const x of [-20, 40, 100]) g.add(bx('cerna_mat', 'zasuvka_zebro' + (s > 0 ? '' : '_m') + x, x - 3, x + 3, s > 0 ? Z.y - 1 : -Z.y - 2.5, s > 0 ? Z.y + 2.5 : -Z.y + 1, Z.z0 + 40, Z.z1 - 40));
  // čelní panel (stupňovitý): základní deska + zvýšená spodní plocha
  const front = roundPoly([[-Z.y, Z.z0 + 6], [Z.y, Z.z0 + 6], [Z.y, Z.z1 - 2], [-Z.y, Z.z1 - 2]], [8, 8, 4, 4], 3);
  g.add(extYZ('cerna', 'zasuvka_celo', front, 221.5, 231, 30));
  // spodní zesílená část čela (stupeň)
  g.add(extYZ('cerna', 'zasuvka_celo_stupen', [[-196, Z.z0 + 10], [196, Z.z0 + 10], [196, -40], [-196, -40]], 230.5, 234.5, 25));
  // zamykací červený blok nahoře uprostřed se čtvercovým vybráním (z rektifikace c01 na rovinu X = 238: z 160…218)
  g.add(extYZ('cervena', 'zasuvka_zamek', roundPoly([[-27, 160], [27, 160], [27, 214], [-27, 214]], [8, 8, 12, 12], 3), 229, 236, 25, [roundPoly([[-10, 176], [10, 176], [10, 200], [-10, 200]], [5, 5, 5, 5], 3)]));
  g.add(extYZ('cerna_mat', 'zasuvka_zamek_vybrani', [[-38, 150], [38, 150], [38, 222], [-38, 222]], 227, 231.5, 22));
  // červená rukojeť (vodorovná lišta) Y ±85, z 88…120 a zahloubený rámeček pod ní
  g.add(extYZ('cervena', 'zasuvka_rukojet', roundPoly([[-85, 90], [85, 90], [85, 120], [-85, 120]], [6, 6, 4, 4], 3), 231, 238, 25));
  g.add(bx('cerna_mat', 'zasuvka_rukojet_prohlubne', 229, 233, -80, 80, 78, 90));
  g.add(extYZ('cerna_mat', 'zasuvka_rukojet_ram', [[-96, 74], [96, 74], [96, 128], [-96, 128]], 229.5, 232, 22));
  // spodní „tác“: zvýšená deska se zkosenými horními rohy (Y −85…105, z −190…−45)
  g.add(extYZ('cerna', 'zasuvka_tac', [[-86, Z.z0 + 14], [106, Z.z0 + 14], [106, -58], [92, -45], [-72, -45], [-86, -58]], 230.5, 235, 25));
  // logo (Milwaukee/PACKOUT)
  const lg = new Group('logo'); logoXL(lg, { x0: 235 }); lg.parts.forEach(p => { p.move(0, 5, 0); g.add(p); });
  // dvě kolečka ve spodních rozích zásuvky (osa Y)
  for (const s of [1, -1]) {
    const yc = s * (Z.y - 40);
    g.add(rbox('cerna', 'kolecko_drzak' + (s > 0 ? '' : '_m'), 196, 226, yc - 14, yc + 14, Z.z0 - 6, Z.z0 + 12, 4, 1.5));
    g.add(cylY('guma', 'kolecko' + (s > 0 ? '' : '_m'), 14, yc - 9, yc + 9, 210, Z.z0 - 8, 18));
  }
  return g;
}
