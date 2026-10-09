// Milwaukee PACKOUT Tilt Bin Organiser 4932498323 (organizér s výklopnými boxy, 8 malých + 2 velké boxy s děličem).
// Vlastní parametrický generátor podle fotografií výrobce. Souřadnice: X = šířka (čelo s madlem +X), Y = délka, Z = výška
// (plocha s boxy +Z); počátek = střed obálky 386 × 500 × 170 mm. Stavba po modulech p8323_*.mjs; poznámky: zdroje/4932498323_poznamky.md
import { Group } from './jadro/mesh.js';
import { MATERIALY } from './jadro/glb.js';
import { korpus } from './p8323_korpus.mjs';
import { celo } from './p8323_celo.mjs';
import { bunky, boxy } from './p8323_bunky.mjs';

// vlastní materiály (jedinečné názvy, aby se nepřepsaly materiály jiných modelů)
MATERIALY.o8323_cerna = { color: [0.014, 0.014, 0.016], metallic: 0.0, roughness: 0.55 };       // černý PP korpus
MATERIALY.o8323_mat = { color: [0.008, 0.008, 0.009], metallic: 0.0, roughness: 0.8 };         // matný černý PP (nárazníky, přepážky, guma)
MATERIALY.o8323_cira = { color: [0.55, 0.6, 0.65], metallic: 0.0, roughness: 0.08, alpha: 0.14 };   // čirý PC (boxy)

export const SKU = '4932498323';
export const OBALKA = { x: 386, y: 500, z: 170 };
export const CELO = 'X';

export function build() {
  const root = new Group(SKU);
  root.addGroup(korpus()); root.addGroup(celo());
  const bk = new Group('bunky'); bunky(bk); root.addGroup(bk);
  for (const b of boxy()) root.addGroup(b);
  return root;
}
