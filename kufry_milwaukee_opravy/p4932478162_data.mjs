// Společné rozměry XL boxu PACKOUT (4932478162 / 4932501784), mm, souřadnice modelu (čelo +X, Z nahoru, počátek střed obálky 394 × 554 × 422).
// Hodnoty vycházejí z rektifikace fotografií (viz zdroje/4932478162_poznamky.md); co je odhad, je tam označeno.
export const HX = 197, HY = 277, HZ = 211;       // polovina obálky: hloubka, šířka, výška
export const Z_SEAM = 126;                        // švík tělo / víko
export const Z_BOT = -193;                        // spodní hrana těla (pod ní jen nohy)
export const BODY = { yw: 240, xf: 188, xr: -168 };   // šířka těla (|Y|), čelní a zadní rovina těla v pásu pod víkem
export const LID = { yw: 272, xf: 194, xr: -170, zTop: 211, zPlate: 201 };  // víko: |Y| 262 (přesah), čelo 194, temeno 211
export const ROH = { yIn: 232, y: 277, xIn: 148, zTopLo: 123, zTopHi: 186, zBotLo: -197, zBotHi: -143 }; // rohové patky (vnitřní okraj, vnější okraj, výška)
export const TYC = { yc: 262, w: 20, xc: 176, xcZ: -158, d: 28, z0: -145, z1: 124 };    // hliníkové tyče: střed Y, šířka (Y), střed X, hloubka (X), rozsah Z
export const ZAMEK_Y = 162;                       // střed spon (|Y|)
