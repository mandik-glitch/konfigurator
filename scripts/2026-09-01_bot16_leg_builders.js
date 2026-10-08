// Parametrizovane builder funkce pro noze Caddy/Doblo (s cap) a Ford (bez cap,
// prosty zebrik) - profil 30x30 (Object_7), D=349mm fixni pro vsechny 3 rodiny
// (custom_shapes 534/535 Caddy, 536/537 Doblo, 538 Ford). bot16 2026-09-01.
const T = 30, D = 349;

function part(xCenter, yCenter, lengthY, vertical, zCenter, role) {
  return {
    position: [xCenter, yCenter, zCenter],
    quaternion: vertical ? [0, 0, 0, 1] : [0, 0, -0.707107, 0.707107],
    scale: [1, lengthY / 1000, 1],
    role,
  };
}

// Caddy/Doblo plain (s cap) - H, CAP_H, capRight jsou rodinove konstanty.
function buildPlainWithCap({ H, CAP_H, capRight }) {
  const zL = D - T, pR = T, rl = zL - pR;
  return [
    part(pR / 2 === undefined ? T / 2 : T / 2, H / 2, H, true, T / 2, "predni-svislice"),
    part(D - T / 2, (H - CAP_H) / 2, H - CAP_H, true, T / 2, "zadni-svislice-dolni"),
    part((pR + zL) / 2, T / 2, rl, false, T / 2, "spojnice-dolni"),
    part((pR + zL) / 2, (H - CAP_H) - T / 2, rl, false, T / 2, "spojnice-horni"),
    part(capRight - T / 2, H - CAP_H / 2, CAP_H, true, T / 2, "cap"),
  ];
}

// Caddy/Doblo vyrez - CUTOUT_H/colRight muzou byt PRO KONKRETNI VOZIDLO
// prepocitane (fresh kolizni krokovani, shape_geometry_methods.id=6), NE
// nutne stejne jako katalogovy vzor v custom_shapes.
function buildVyrezWithCap({ H, CAP_H, capRight, CUTOUT_H, colRight }) {
  const zL = D - T, pR = T, colLeft = colRight - T;
  return [
    part(T / 2, H / 2, H, true, T / 2, "predni-svislice"),
    part((pR + zL) / 2, (H - CAP_H) - T / 2, zL - pR, false, T / 2, "spojnice-horni-uzavreni"),
    part(capRight - T / 2, H - CAP_H / 2, CAP_H, true, T / 2, "cap"),
    part(D - T / 2, CUTOUT_H + (H - CAP_H - CUTOUT_H) / 2, (H - CAP_H) - CUTOUT_H, true, T / 2, "zadni-svislice-nad-zarezem"),
    part(colLeft + T / 2, CUTOUT_H / 2, CUTOUT_H, true, T / 2, "sloupek-pred-podbehem"),
    part((pR + colLeft) / 2, T / 2, colLeft - pR, false, T / 2, "spojnice-dolni"),
  ];
}

// Ford Connect plain (bez cap) - prosty zebrik, 2x plna vyska + 1 rung.
function buildFordPlain({ H }) {
  const zL = D - T, pR = T, rl = zL - pR;
  return [
    part(D - T / 2, H / 2, H, true, T / 2, "zadni-svislice"),
    part(T / 2, H / 2, H, true, T / 2, "predni-svislice"),
    part((pR + zL) / 2, T / 2, rl, false, T / 2, "spojnice-dolni"),
  ];
}

module.exports = { T, D, buildPlainWithCap, buildVyrezWithCap, buildFordPlain };
