// Diagnostika: proc plna I vyrez noha koliduji IDENTICKY v celem pasmu
// Z=[-1193..137]? To znamena, ze zuzeny sloupek vyrez nohy (kotveny
// WALL_CLEARANCE_ARCH=124mm od steny, prevzato z Jumpy) NENI dost daleko
// od steny na to, aby se vyhnul skutecnemu podbehu Vivara - potreba zjistit
// SKUTECNOU hloubku vyklenuti podbehu u Vivara kolizni krokovanim.
const THREE = require("three");
const fs = require("fs");
const { collidesWithWalls } = require("/opt/konfigurator/scripts/tmp_2026-08-31_place_vivaro.js");

const step1 = JSON.parse(fs.readFileSync("/opt/konfigurator/scripts/tmp_2026-08-31_vivaro_step1_result.json", "utf8"));
const { offsetX, offsetY, D, T } = step1;

// Testovaci "sonda": tenky svisly hranol vysky CUTOUT_H=395 (jako by to byl
// jen zuzeny sloupek pred podbehem, T=30 x T=30 prurez), na ruznem X (ruzna
// vzdalenost od steny) a ruznem Z, aby se zjistilo skutecne vyklenuti
// podbehu (misto prevzateho 124mm z Jumpy).
function probeAt(xCenter, zCenter, hLow, hHigh) {
  const lenY = hHigh - hLow;
  const geo = new THREE.BoxGeometry(T, lenY, T);
  const mesh = new THREE.Mesh(geo);
  mesh.position.set(xCenter, (hLow + hHigh) / 2 + offsetY, zCenter + T / 2);
  mesh.updateMatrixWorld(true);
  return mesh;
}

const CUTOUT_H = 395;
// Vyber nekolik Z v ramci kolizni zony, najdi min offset-from-wall (v mm)
// pro NIZKOU sondu (0..CUTOUT_H) a pro VYSOKOU sondu (CUTOUT_H..1180-260=920),
// abychom zjistili, jestli je problem vysky nebo hloubky.
const testZs = [-1193, -1000, -800, -600, -400, -200, 0, 137];
const wallNearX = offsetX + D; // -362, puvodni "u steny" X (nasi nohy)
console.log("wallNearX (D od offsetX) =", wallNearX);

for (const z of testZs) {
  // najdi min "clearance od steny" (posun smerem OD steny, tj. + smerem k
  // centru, protoze stena je na zaporne X) pro nizkou sondu, krokovanim 5mm
  let clearanceLow = null;
  for (let c = 0; c <= 700; c += 5) {
    const xCenter = wallNearX + c; // posun od steny smerem ke stredu (kladny smer)
    if (!collidesWithWalls(probeAt(xCenter, z, 0, CUTOUT_H))) { clearanceLow = c; break; }
  }
  let clearanceHigh = null;
  for (let c = 0; c <= 700; c += 5) {
    const xCenter = wallNearX + c;
    if (!collidesWithWalls(probeAt(xCenter, z, CUTOUT_H, 920))) { clearanceHigh = c; break; }
  }
  console.log(`Z=${z}: clearance-od-steny NIZKA sonda(0-${CUTOUT_H})=${clearanceLow}mm, VYSOKA sonda(${CUTOUT_H}-920)=${clearanceHigh}mm`);
}
