// Sestavení společného základu XL boxu PACKOUT (použijí kufr_4932478162.mjs i kufr_4932501784.mjs).
import { Group, Part, extYZ } from './p4932478162_zaklad.mjs';
import { vana, bocniPanely, celniPanel, nohy, zamekSachta, vnitrek } from './p4932478162_telo.mjs';
import { vicko, vickoDetaily } from './p4932478162_vicko.mjs';
import { rohy } from './p4932478162_rohy.mjs';
import { spony, rukojetBok } from './p4932478162_zamky.mjs';
import { logoXL } from './p4932478162_logo.mjs';

export function zakladXL(root, { stitek = false } = {}) {
  const telo = vana(); telo.name = 'telo';
  const poc = bocniPanely(telo);
  celniPanel(telo); nohy(telo); zamekSachta(telo); vnitrek(telo);
  root.addGroup(telo);
  root.addGroup(rohy());
  const v = vicko(); vickoDetaily(v, { stitek });
  root.addGroup(v);
  root.addGroup(spony());
  root.addGroup(rukojetBok(1, poc)); root.addGroup(rukojetBok(-1, poc));
  const lg = new Group('logo'); logoXL(lg); root.addGroup(lg);
  return root;
}
