// Verify zMidB < 0 (OK) for all flipped Expert/Vito car bodies, reading POSITION accessor
// min/max directly from GLB header (no full geometry decode needed).
const fs = require("fs");
const path = require("path");

function getPositionBBox(p) {
  const buf = fs.readFileSync(p);
  let offset = 12, json = null;
  while (offset < buf.length) {
    const chunkLen = buf.readUInt32LE(offset);
    const chunkType = buf.readUInt32LE(offset + 4);
    const chunkData = buf.slice(offset + 8, offset + 8 + chunkLen);
    if (chunkType === 0x4e4f534a) { json = JSON.parse(chunkData.toString("utf8")); break; }
    offset += 8 + chunkLen;
  }
  const mesh = json.meshes[0];
  const prim = mesh.primitives[0];
  const acc = json.accessors[prim.attributes.POSITION];
  return { min: acc.min, max: acc.max };
}

const DIR = "/opt/konfigurator/webapp/katalog/car_bodies";
const bases = [
  "Peugeot_Expert_PE12_2007-2015", "Peugeot_Expert_PE13_2007-2015", "Peugeot_Expert_PE14_2007-2015",
  "Peugeot_Expert_PE15_2016-", "Peugeot_Expert_PE16_2016-", "Peugeot_Expert_PE17_2016-",
  "Peugeot_Expert_PE20_2016-", "Peugeot_Expert_PE21_2016-",
  "Peugeot_Expert_PE25_2021-", "Peugeot_Expert_PE26_2021-", "Peugeot_Expert_PE27_2021-",
  "Mercedes_Vito_MB17_2014-", "Mercedes_Vito_MB18_2014-", "Mercedes_Vito_MB19_2014-",
  "Mercedes_Vito_MB24_2014-", "Mercedes_Vito_MB25_2014-", "Mercedes_Vito_MB46_2014-", "Mercedes_Vito_MB47_2014-",
];
let allOk = true;
for (const base of bases) {
  const b = getPositionBBox(path.join(DIR, base + "_B.glb"));
  const zMidB = (b.min[2] + b.max[2]) / 2;
  const verdict = zMidB < -50 ? "OK" : (zMidB > 50 ? "NEEDS_FLIP" : "UNCERTAIN");
  if (verdict !== "OK") allOk = false;
  console.log(base, "zMidB=", zMidB.toFixed(1), verdict);
}
console.log(allOk ? "\nALL OK" : "\nSOME STILL NEED FLIP");
