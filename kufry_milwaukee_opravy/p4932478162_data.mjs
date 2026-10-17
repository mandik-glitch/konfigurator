// Společné rozměry XL boxu PACKOUT (4932478162 / 4932501784), mm, souřadnice modelu (čelo +X, Z nahoru, počátek střed obálky 394 × 554 × 422).
// Hodnoty vycházejí z rektifikace fotografií (viz zdroje/4932478162_poznamky.md); co je odhad, je tam označeno.
export const HX = 197, HY = 277, HZ = 211;       // polovina obálky: hloubka, šířka, výška
export const Z_SEAM = 128;                        // švík tělo / víko
export const Z_BOT = -193;                        // spodní hrana těla (pod ní jen nohy)
export const BODY = { yw: 241, xf: 188, xr: -186 };   // šířka těla (|Y|), čelní a zadní rovina těla v pásu pod víkem
export const LID = { yw: 262, xf: 194, xr: -194, zTop: 211, zPlate: 201 };  // víko: |Y| 262 (přesah), čelo 194, temeno 211
export const ROH = { yIn: 232, y: 277, xIn: 148, zTopLo: 130, zTopHi: 196, zBotLo: -202, zBotHi: -144 }; // rohové patky (vnitřní okraj, vnější okraj, výška)
export const TYC = { yc: 262, w: 20, xc: 176, d: 28, z0: -143, z1: 131 };    // hliníkové tyče: střed Y, šířka (Y), střed X, hloubka (X), rozsah Z
export const ZAMEK_Y = 162;                       // střed spon (|Y|)
