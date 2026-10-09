// Milwaukee PACKOUT Compact Slim Organiser 4932471065 (kompaktní, 4 malé + 1 velká nádoba). Vlastní parametrický generátor podle fotografií výrobce.
// Souřadnice: X = šířka (249), Y = délka (411, čelo +Y), Z = výška (64); počátek = střed obálky. Stavba je rozdělena do modulů p1065_*.mjs
// (korpus, nádoby, čelo se sponami, víko s prolisy); konstrukční řešení převzato z modelu 4932464082 (p4082_*). Poznámky: zdroje/4932471065_poznamky.md
import { Group } from './jadro/mesh.js';
import { korpus } from './p1065_korpus.mjs';
import { nadoby } from './p1065_nadoby.mjs';
import { celo } from './p1065_celo.mjs';
import { vicko } from './p1065_vicko.mjs';

export const SKU = '4932471065';
export const OBALKA = { x: 249, y: 411, z: 64 };
export const CELO = 'Y';

export function build() {
  const root = new Group(SKU);
  root.addGroup(korpus()); root.addGroup(nadoby()); root.addGroup(celo()); root.addGroup(vicko());
  return root;
}
