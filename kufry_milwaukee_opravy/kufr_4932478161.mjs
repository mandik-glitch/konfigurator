// Milwaukee PACKOUT Pojízdná bedna na nářadí, 4932478161 – OPRAVENÁ verze (vlastní generátor podle fotografií výrobce).
// Souřadnice: X = šířka 609 (čelo se západkami +X), Y = délka 965 (madlo na -Y, kola na +Y), Z = výška 401; počátek = střed obálky.
// Moduly: p4932478161_korpus (vana, čelo, koncový blok, patky), _vicko (víko + západky), _madlo (výsuvné madlo); společné: p4932464078_zaklad, p4932464078_kola.
import { Group } from './p4932464078_zaklad.mjs';
import { korpus, vlozka, zc } from './p4932478161_korpus.mjs';
import { vicko, zapadky } from './p4932478161_vicko.mjs';
import { madlo } from './p4932478161_madlo.mjs';
import { kolo } from './p4932464078_kola.mjs';

export const SKU = '4932478161';
export const OBALKA = { x: 609, y: 965, z: 401 };
export const CELO = 'X';
export const NAZEV = 'Milwaukee PACKOUT pojízdná bedna na nářadí (4932478161), oprava v6';

export function build() {
  const root = new Group(SKU);
  root.addGroup(korpus());
  root.addGroup(vlozka());
  root.addGroup(vicko());
  for (const z of zapadky()) root.addGroup(z);
  root.addGroup(madlo());
  // kola na konci +Y: osa X, střed Y = 367, vnější strany X = ±304.5
  root.addGroup(kolo('kolo_P', { cx: 0, cz: zc(112.5), yIn: 216, yOut: 304.5, osaX: 367 }));
  root.addGroup(kolo('kolo_L', { cx: 0, cz: zc(112.5), yIn: -216, yOut: -304.5, osaX: 367 }));
  return root;
}
