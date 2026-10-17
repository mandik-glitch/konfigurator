// Pojízdný box 4932498651 – teleskopické madlo: pevné vedení v zadní stěně, střední stupeň (červená vodicí spona) a horní stupeň (červená příčka s gumovým úchopem).
// Výchozí = zasunuté (v obálce). Posuv podél +Z: `madlo_stredni` max 232 mm, `madlo_horni` max 600 mm (nad víkem ≈ 600 mm podle c01).
import { Part, Group, rbox, bx, extYZ, extXZ, roundPoly, cylY } from './p4932478162_zaklad.mjs';
import { MADLO as M, Z_TOP } from './p4932498651_data.mjs';

export function madlo() {
  const g = new Group('madlo');
  const a = M.a / 2, x0 = M.x - a, x1 = M.x + a;
  // pevné vedení (dva černé profily v zadní stěně, vyčnívají nad víko jen krátce – zadní okraj)
  for (const s of [1, -1]) g.add(rbox('cerna', 'madlo_vedeni' + (s > 0 ? '' : '_m'), x0 - 3, x1 + 3, s * M.y - a - 3, s * M.y + a + 3, -240, 238, 3, 1.2));
  // střední stupeň
  const st = new Group('madlo_stredni', { pivot: [M.x, 0, 0], extras: { osa: [0, 0, 1], max_posuv: M.zdvihStredni, popis: 'střední stupeň teleskopu (posuv podél +Z)' } });
  const zS = 234;   // horní hrana červené vodicí spony ve výchozí poloze (pod víkem; spona je ukryta ve skříni)
  for (const s of [1, -1]) st.add(rbox('cerna', 'madlo_trubka2' + (s > 0 ? '' : '_m'), x0 + 0.3, x1 - 0.3, s * M.y - a + 0.5, s * M.y + a - 0.5, -190, zS, 2, 1));
  // červená vodicí spona: konce (kolem trubek) vyšší, střed nižší a se zahloubením; pod ní černá polička
  const yE = M.y + a + 9, yI = M.y - a - 8;
  const spona = roundPoly([[-yE, zS - 46], [yE, zS - 46], [yE, zS], [yI + 18, zS], [yI - 14, zS - 18], [-(yI - 14), zS - 18], [-(yI + 18), zS], [-yE, zS]], [3, 3, 3, 6, 6, 6, 6, 3], 2);
  st.add(extYZ('cervena', 'madlo_spona', spona, M.x - 17, M.x + 17, 30));
  st.add(rbox('guma', 'madlo_spona_police', M.x - 12, M.x + 12, -(yI - 4), yI - 4, zS - 52, zS - 46, 2, 0.8));
  st.add(rbox('cerna', 'madlo_spona_tlacitko', M.x - 8, M.x + 8, -22, 22, zS - 18, zS - 12, 2, 1));
  g.addGroup(st);
  // horní stupeň
  const hr = new Group('madlo_horni', { pivot: [M.x, 0, 0], extras: { osa: [0, 0, 1], max_posuv: M.zdvihHorni, popis: 'horní stupeň teleskopu (posuv podél +Z), červená příčka s úchopem' } });
  for (const s of [1, -1]) hr.add(rbox('cerna', 'madlo_trubka1' + (s > 0 ? '' : '_m'), x0 + 2, x1 - 2, s * M.y - a + 2, s * M.y + a - 2, -160, Z_TOP - 40, 1.5, 0.8));
  // červená příčka: tělo (zkosené konce), černý gumový úchop, čepy
  const bar = roundPoly([[-M.y - a - 10, Z_TOP - 40], [M.y + a + 10, Z_TOP - 40], [M.y + a + 10, Z_TOP], [-M.y - a - 10, Z_TOP]], [5, 5, 5, 5], 3);
  hr.add(extYZ('cervena', 'madlo_pricka', bar, M.x - 14, M.x + 14, 30));
  hr.add(rbox('guma', 'madlo_uchop', M.x - 16, M.x + 16, -84, 84, Z_TOP - 32, Z_TOP - 9, 5, 3));
  for (const s of [1, -1]) hr.add(cylY('ocel', 'madlo_cep' + (s > 0 ? '' : '_m'), 4, s * (M.y + a + 2) - 2, s * (M.y + a + 2) + 2, M.x + 14, Z_TOP - 20, 10));
  g.addGroup(hr);
  return g;
}
