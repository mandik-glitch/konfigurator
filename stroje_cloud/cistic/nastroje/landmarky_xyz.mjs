// 3D souřadnice (z' nad zemí) landmarků podle MODELU (K z c_zaklad.mjs) – protějšky ručně změřených pixelů v zdroje/landmarky/l*.json.
// node nastroje/landmarky_xyz.mjs > zdroje/landmarky/xyz_model.json
import { K } from '../c_zaklad.mjs';
import { OTVOR } from '../c_kryt.mjs';
const S = { E: 1, W: -1 }, o = {};
for (const [n, s] of Object.entries(S)) {
  o['FT_' + n] = [s * K.hw, K.Yf, K.Ht]; o['SH_' + n] = [s * K.hw, K.ys, K.Ht]; o['SB_' + n] = [s * K.hw, K.yb, K.Hb];
  o['FB_' + n] = [s * K.hw, K.Yf, K.zb]; o['FRtf_' + n] = [s * K.hw, K.yft, K.zft];
  o['HUB_' + n] = [s * K.xw, K.yw, K.R]; o['TT_' + n] = [s * K.xw, K.yw, 2 * K.R]; o['TB_' + n] = [s * K.xw, K.yw, 0];
  o['PBOT_' + n] = [s * K.xp, K.yp, 118]; o['CST_' + n] = [s * K.xc, K.yc, 0];
}
o.HOLE = [OTVOR.cx, OTVOR.cy, K.Ht]; o.HNDM = [0, K.Yh, K.zh];
console.log(JSON.stringify(o, null, 1));
