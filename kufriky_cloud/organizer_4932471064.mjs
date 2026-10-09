// Milwaukee PACKOUT Slim Organiser 4932471064 (nízký organizér, 10 nádob). Vlastní parametrický generátor podle fotografií výrobce.
// Souřadnice: X = šířka (čelo +X), Y = délka, Z = výška; počátek = střed obálky 414 × 500 × 64 mm.
// Stavba je rozdělena do modulů p1064_*.mjs (data, korpus, čelo, víko, nádoby, kapsy); poznámky k měření: zdroje/4932471064_poznamky.md
import { Group } from './jadro/mesh.js';
import { korpus } from './p1064_korpus.mjs';
import { celo } from './p1064_celo.mjs';
import { vicko } from './p1064_vicko.mjs';
import { nadoby } from './p1064_nadoby.mjs';
import { cistiDil } from './pomocne_4932471064.mjs';

export const SKU = '4932471064';
export const OBALKA = { x: 414, y: 500, z: 64 };
export const CELO = 'X';

export function build() {
  const root = new Group(SKU);
  root.addGroup(korpus()); root.addGroup(nadoby()); root.addGroup(celo()); root.addGroup(vicko());
  for (const p of root.allParts()) cistiDil(p);          // žádné nulové plošky
  return root;
}
