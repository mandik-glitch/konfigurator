// Pojízdný box 4932498651 – zásuvka (samostatný posuvný uzel `zasuvka`, osa X, zdvih ≈ 330 mm – odhad z c02, skutečný zdvih nelze z fotky změřit).
import { Part, Group, rrPoly, loftBox, loftVessel, loftHood, rbox, bx, extYZ, extXZ, cylX, cylY, extrude, roundPoly, tube } from './p4932478162_zaklad.mjs';
import { ZASUVKA as Z } from './p4932498651_data.mjs';
import { logoXL } from './p4932478162_logo.mjs';

export function zasuvka() {
  const g = new Group('zasuvka', { pivot: [0, 0, 0], extras: { posuv_osa: [1, 0, 0], max_posuv: Z.zdvih, popis: 'výsuvná zásuvka (posuv podél +X); zdvih je odhad' } });
  const w = 4.5;
  // vana zásuvky: vnější stěny zdola nahoru, okraj, vnitřní stěny dolů (dno)
  const L = (z, d, r = 12) => ({ z, x0: Z.x0 + d, x1: 223 - d, y0: -Z.y + d, y1: Z.y - d, r });
  g.add(loftVessel('cerna', 'zasuvka_vana', [L(Z.z0, 8, 16), L(Z.z0 + 8, 0), L(Z.z1, 0)], [L(Z.z1, w), L(Z.z0 + 14, w), L(Z.z0 + 8 + 2, w + 6)], { seg: 4, crease: 38 }));
  // horní okraj (lem) se zkosením
  g.add(loftHood('cerna', 'zasuvka_lem', [{ z: Z.z1 - 8, x0: Z.x0 - 2, x1: 225, y0: -Z.y - 2, y1: Z.y + 2, r: 13 }, { z: Z.z1 + 1, x0: Z.x0 - 3, x1: 226, y0: -Z.y - 3, y1: Z.y + 3, r: 13 }],
    [{ z: Z.z1 + 1, x0: Z.x0 + 1, x1: 221, y0: -Z.y + 1, y1: Z.y - 1, r: 11 }, { z: Z.z1 - 8, x0: Z.x0 + 2, x1: 220, y0: -Z.y + 2, y1: Z.y - 2, r: 11 }], { seg: 4 }));
  // žebrování bočních stěn (3 svislé štěrbiny jako na c02 + žebra)
  for (const s of [1, -1]) for (const x of [-20, 40, 100]) g.add(bx('cerna_mat', 'zasuvka_zebro' + (s > 0 ? '' : '_m') + x, x - 3, x + 3, s > 0 ? Z.y - 1 : -Z.y - 2.5, s > 0 ? Z.y + 2.5 : -Z.y + 1, Z.z0 + 40, Z.z1 - 40));
  // žebra uvnitř vany (boční a zadní stěna) – tlumené, jen náznak podle c02
  for (const sg of [1, -1]) for (const x of [-120, -40, 40, 120]) g.add(bx('cerna_mat', 'zasuvka_vnitrni_zebro' + (sg > 0 ? '' : '_m') + x, x - 2.5, x + 2.5, sg > 0 ? Z.y - w - 5 : -(Z.y - w), sg > 0 ? Z.y - w : -(Z.y - w - 5), Z.z0 + 30, Z.z1 - 24));
  for (const y of [-150, -75, 0, 75, 150]) g.add(bx('cerna_mat', 'zasuvka_zadni_zebro' + y, Z.x0 + w, Z.x0 + w + 5, y - 2.5, y + 2.5, Z.z0 + 30, Z.z1 - 24));
  // čelní panel (stupňovitý): základní deska + zvýšená spodní plocha
  const front = roundPoly([[-Z.y, Z.z0 + 6], [Z.y, Z.z0 + 6], [Z.y, Z.z1 - 2], [-Z.y, Z.z1 - 2]], [8, 8, 4, 4], 3);
  g.add(extYZ('cerna', 'zasuvka_celo', front, 221.5, 231, 30));
  // spodní zesílená část čela (stupeň)
  g.add(extYZ('cerna', 'zasuvka_celo_stupen', [[-196, Z.z0 + 10], [196, Z.z0 + 10], [196, -40], [-196, -40]], 230.5, 234.5, 25));
  // prvky čela jsou na fotce o ≈ +12 mm v Y vůči středu panelu (rektifikace c02 na rovinu čela); z podle téže rektifikace
  const dY = 12;
  const Y = a => a + dY;
  // zamykací červený blok nahoře se čtvercovým vybráním (z 146…200)
  g.add(extYZ('cervena', 'zasuvka_zamek', roundPoly([[Y(-27), 146], [Y(27), 146], [Y(27), 200], [Y(-27), 200]], [8, 8, 12, 12], 3), 229, 236, 25, [roundPoly([[Y(-10), 162], [Y(10), 162], [Y(10), 186], [Y(-10), 186]], [5, 5, 5, 5], 3)]));
  g.add(extYZ('cerna_mat', 'zasuvka_zamek_vybrani', [[Y(-38), 136], [Y(38), 136], [Y(38), 208], [Y(-38), 208]], 227, 231.5, 22));
  // červená rukojeť (vodorovná lišta) Y −80…104, z 76…106 a zahloubený rámeček pod ní
  g.add(extYZ('cervena', 'zasuvka_rukojet', roundPoly([[Y(-90), 76], [Y(90), 76], [Y(90), 106], [Y(-90), 106]], [6, 6, 4, 4], 3), 231, 238, 25));
  g.add(bx('cerna_mat', 'zasuvka_rukojet_prohlubne', 229, 233, Y(-84), Y(84), 64, 76));
  g.add(extYZ('cerna_mat', 'zasuvka_rukojet_ram', [[Y(-100), 60], [Y(100), 60], [Y(100), 114], [Y(-100), 114]], 229.5, 232, 22));
  // spodní „tác“: zvýšená deska se zkosenými horními rohy (Y −75…108, z −190…−45)
  g.add(extYZ('cerna', 'zasuvka_tac', [[-75, Z.z0 + 14], [108, Z.z0 + 14], [108, -58], [94, -45], [-61, -45], [-75, -58]], 230.5, 235, 25));
  // logo (Milwaukee/PACKOUT)
  const lg = new Group('logo'); logoXL(lg, { x0: 235 }); lg.parts.forEach(p => { p.move(0, dY + 6, -4); g.add(p); });
  // dvě kolečka ve spodních rozích zásuvky (osa Y)
  for (const s of [1, -1]) {
    const yc = s * (Z.y - 40);
    g.add(rbox('cerna', 'kolecko_drzak' + (s > 0 ? '' : '_m'), 196, 226, yc - 14, yc + 14, Z.z0 - 6, Z.z0 + 12, 4, 1.5));
    g.add(cylY('guma', 'kolecko' + (s > 0 ? '' : '_m'), 14, yc - 9, yc + 9, 210, Z.z0 - 8, 18));
  }
  return g;
}
