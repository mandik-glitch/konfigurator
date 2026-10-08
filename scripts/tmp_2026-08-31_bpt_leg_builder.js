// Genericky 30x30 (Object_7) noha builder pro Berlingo/Partner/Trafic
// (bot16, 2026-08-31), prevod z 40x40 puvodnich sablon custom_shapes
// 492 (Berlingo)/505 (Partner)/510+511 (Trafic) metodou id=1 "prevod-
// profilu-zachovanim-rozmeru".
//
// DULEZITY ROZDIL OD JUMPY/VIVARO SABLONY: puvodni DB tvary 492/505/510
// NEMAJI zadny "cap" dil ani horni vodorovny pricnik - jsou to proste DVE
// plnovyskove svislice (predni+zadni) spojene JEN spodnim pricnikem u
// podlahy ("U" tvar, otevreny nahoru). buildPlainAtDepth() nize tenhle
// puvodni tvar respektuje 1:1 (zadny cap pridavat netreba, zadna svislice
// se nezkracuje).
//
// Pro Trafic vyrez (511) puvodni DB tvar mel zuzeny sloupek VNITRNE (ne u
// steny) BEZ premostovaci pricky k zadni svislici nad zarezem - to je
// stejna nekompletni topologie, jakou mela puvodni (pred opravou 2026-08-
// 31) Jumpy vyrez sablona. buildVyrezAtDepth() nize pouziva UZ OPRAVENOU
// topologii (stejnou jako tmp_2026-08-30_build_depth_variants_both.js
// pro Jumpy/Vivaro po fixu "pricka-uzavreni-vyrezu"), jen s parametry
// (H, CUTOUT_H, WALL_CLEARANCE_ARCH) urcenymi CERSTVYM kolriznim
// krokovanim pro Trafic, ne prevzatymi z Jumpy.
const T = 30;

function part(xCenter, yCenter, lengthY, vertical, zCenter, role) {
  return {
    position: [xCenter, yCenter, zCenter],
    quaternion: vertical ? [0, 0, 0, 1] : [0, 0, -0.707107, 0.707107],
    scale: [1, lengthY / 1000, 1],
    role,
  };
}

// Plna noha bez podbehu: predni svislice (X=T/2, plna vyska H) + zadni
// svislice (X=D-T/2, TAKE plna vyska H, zadny cap) + spodni pricnik u
// podlahy (T..D-T).
function buildPlainAtDepth(D, H, T_ = T) {
  const zCenter = T_ / 2;
  const rungLo = T_, rungHi = D - T_;
  const parts = [];
  parts.push(part(T_ / 2, H / 2, H, true, zCenter, "predni-svislice"));
  parts.push(part(D - T_ / 2, H / 2, H, true, zCenter, "zadni-svislice"));
  const rungLen = rungHi - rungLo;
  if (rungLen > 0.01) parts.push(part((rungLo + rungHi) / 2, T_ / 2, rungLen, false, zCenter, "spojnice-dolni"));
  return parts;
}

// Vyrez noha (podbeh): predni svislice plna vyska H; zuzeny "sloupek-pred-
// podbehem" kotveny WALL_CLEARANCE_ARCH mm od steny (vnejsi hrana D,
// T-nezavisla kotva - stejny princip jako Jumpy gotcha2_2026_08_30),
// vysky CUTOUT_H; spodni pricnik od predni svislice ke sloupku; "pricka-
// uzavreni-vyrezu" polozena SHORA na sloupek (cap-styl) a dotykajici se
// boku zadni svislice nad zarezem, stejneho rozsahu jako by mel horni
// pricnik (T..D-T); "zadni-svislice-nad-zarezem" u steny (D-T..D) od
// CUTOUT_H do H.
function buildVyrezAtDepth(D, H, CUTOUT_H, WALL_CLEARANCE_ARCH, T_ = T) {
  const zCenter = T_ / 2;
  const parts = [];
  parts.push(part(T_ / 2, H / 2, H, true, zCenter, "predni-svislice"));

  const colRight = D - WALL_CLEARANCE_ARCH, colLeft = colRight - T_;
  parts.push(part((colLeft + colRight) / 2, CUTOUT_H / 2, CUTOUT_H, true, zCenter, "sloupek-pred-podbehem"));
  const rungLen0 = colLeft - T_;
  if (rungLen0 > 0.01) parts.push(part((T_ + colLeft) / 2, T_ / 2, rungLen0, false, zCenter, "spojnice-dolni"));

  const closeLeft = T_, closeRight = D - T_, closeLen = closeRight - closeLeft;
  if (closeLen > 0.01) parts.push(part((closeLeft + closeRight) / 2, CUTOUT_H + T_ / 2, closeLen, false, zCenter, "pricka-uzavreni-vyrezu"));

  const upperH = H - CUTOUT_H;
  parts.push(part(D - T_ / 2, CUTOUT_H + upperH / 2, upperH, true, zCenter, "zadni-svislice-nad-zarezem"));
  return parts;
}

// Rozsireni vyrez sloupku na novou vysku Y_new (shape_geometry_methods.id=6,
// po fresh kolriznim krokovani proti realne karoserii) - stejny vzor jako
// Jumpy/Vivaro buildVyrezAtDepthExtended.
function buildVyrezAtDepthExtended(D, H, Y_new, WALL_CLEARANCE_ARCH, T_ = T) {
  const base = buildVyrezAtDepth(D, H, 395 /* placeholder, prepsano nize */, WALL_CLEARANCE_ARCH, T_);
  const zCenter = T_ / 2;
  const orig = base.find(p => p.role === "sloupek-pred-podbehem");
  const colX = orig.position[0];
  const parts = base.filter(p => !["sloupek-pred-podbehem", "pricka-uzavreni-vyrezu", "zadni-svislice-nad-zarezem"].includes(p.role));
  parts.push(part(colX, Y_new / 2, Y_new, true, zCenter, "sloupek-pred-podbehem"));
  const origPricka = base.find(p => p.role === "pricka-uzavreni-vyrezu");
  if (origPricka) {
    const closeLen = origPricka.scale[1] * 1000;
    parts.push(part(origPricka.position[0], Y_new + T_ / 2, closeLen, false, zCenter, "pricka-uzavreni-vyrezu"));
  }
  const upperLen = H - Y_new;
  parts.push(part(D - T_ / 2, (Y_new + H) / 2, upperLen, true, zCenter, "zadni-svislice-nad-zarezem"));
  return parts;
}

module.exports = { buildPlainAtDepth, buildVyrezAtDepth, buildVyrezAtDepthExtended, T };
