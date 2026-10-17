// Milwaukee PACKOUT Pojízdný box s výsuvným držadlem, 4932464078 – OPRAVENÁ verze (vlastní generátor podle fotografií výrobce).
// Souřadnice: X = hloubka 472 (čelo +X), Y = šířka 561, Z = výška 530 (složené madlo nahoře); počátek = střed obálky.
// Moduly: p4932464078_korpus (vana, čelo, lišty, boční madla, zadní stěna), _vicko (víko + západky), _madlo (dvoustupňové madlo), _kola (kola); společné: p4932464078_zaklad.
import { Group } from './p4932464078_zaklad.mjs';
import { korpus, zc } from './p4932464078_korpus.mjs';
import { vicko, zapadky } from './p4932464078_vicko.mjs';
import { madlo } from './p4932464078_madlo.mjs';
import { kolo } from './p4932464078_kola.mjs';

export const SKU = '4932464078';
export const OBALKA = { x: 472, y: 561, z: 530 };
export const CELO = 'X';
export const NAZEV = 'Milwaukee PACKOUT pojízdný box (4932464078), oprava v6';

export function build() {
  const root = new Group(SKU);
  root.addGroup(korpus());
  root.addGroup(vicko());
  for (const z of zapadky()) root.addGroup(z);
  root.addGroup(madlo());
  root.addGroup(kolo('kolo_P', { cx: -112, cz: zc(112.5), yIn: 194.5, yOut: 280.5 }));
  root.addGroup(kolo('kolo_L', { cx: -112, cz: zc(112.5), yIn: -194.5, yOut: -280.5 }));
  return root;
}
