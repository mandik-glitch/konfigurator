// Flip 180 stupnu kolem Y pro Berlingo/Partner/Trafic (bot16, 2026-08-31).
// Zkopirovano z tmp_2026-08-31_flip_vw11_180.js (stejny algoritmus).
const fs = require("fs");
function flipGlb180Y(path) {
  const buf = fs.readFileSync(path);
  if (buf.readUInt32LE(0) !== 0x46546c67) throw new Error(`${path}: not glb`);
  const version = buf.readUInt32LE(4);
  let offset = 12, json = null, binChunk = null;
  while (offset < buf.length) {
    const chunkLen = buf.readUInt32LE(offset);
    const chunkType = buf.readUInt32LE(offset + 4);
    const chunkData = buf.slice(offset + 8, offset + 8 + chunkLen);
    if (chunkType === 0x4e4f534a) json = JSON.parse(chunkData.toString("utf8"));
    else if (chunkType === 0x004e4942) binChunk = Buffer.from(chunkData);
    offset += 8 + chunkLen;
  }
  const prim = json.meshes[0].primitives[0];
  ["POSITION", "NORMAL"].forEach(attrName => {
    const accIdx = prim.attributes[attrName];
    if (accIdx == null) return;
    const acc = json.accessors[accIdx];
    const bv = json.bufferViews[acc.bufferView];
    const byteOffset = (bv.byteOffset || 0) + (acc.byteOffset || 0);
    const arr = new Float32Array(binChunk.buffer, binChunk.byteOffset + byteOffset, acc.count * 3);
    for (let i = 0; i < arr.length; i += 3) { arr[i] = -arr[i]; arr[i + 2] = -arr[i + 2]; }
    if (acc.min && acc.max) {
      const newMinX = -acc.max[0], newMaxX = -acc.min[0];
      const newMinZ = -acc.max[2], newMaxZ = -acc.min[2];
      acc.min = [newMinX, acc.min[1], newMinZ];
      acc.max = [newMaxX, acc.max[1], newMaxZ];
    }
  });
  let newJsonBuf = Buffer.from(JSON.stringify(json), "utf8");
  const pad = (4 - (newJsonBuf.length % 4)) % 4;
  if (pad) newJsonBuf = Buffer.concat([newJsonBuf, Buffer.alloc(pad, 0x20)]);
  const header = Buffer.alloc(12);
  header.writeUInt32LE(0x46546c67, 0); header.writeUInt32LE(version, 4);
  const jsonChunkHeader = Buffer.alloc(8);
  jsonChunkHeader.writeUInt32LE(newJsonBuf.length, 0); jsonChunkHeader.writeUInt32LE(0x4e4f534a, 4);
  const binChunkHeader = Buffer.alloc(8);
  binChunkHeader.writeUInt32LE(binChunk.length, 0); binChunkHeader.writeUInt32LE(0x004e4942, 4);
  header.writeUInt32LE(12 + 8 + newJsonBuf.length + 8 + binChunk.length, 8);
  const out = Buffer.concat([header, jsonChunkHeader, newJsonBuf, binChunkHeader, binChunk]);
  fs.writeFileSync(path, out);
  console.log(`${path}: OK`);
}
const KAT = "/opt/konfigurator/webapp/katalog/car_bodies/";
const bases = [
  "Citro_n_Berlingo_CI03_2008-2018",
  "Citro_n_Berlingo_CI04_2008-2018",
  "Citroën_Berlingo_CI16_2019-",
  "Citroën_Berlingo_CI17_2019-",
  "Citroën_Berlingo_CI22_2021-",
  "Citroën_Berlingo_CI23_2021-",
  "Peugeot_Partner_PE02_2008-2018",
  "Peugeot_Partner_PE03_2008-2018",
  "Peugeot_Partner_PE18_2019-",
  "Peugeot_Partner_PE19_2019-",
  "Peugeot_Partner_PE23_2021-",
  "Peugeot_Partner_PE24_2021-",
  "Renault_Trafic_RE28_2026-",
  "Renault_Trafic_RE29_2026-",
];
const suffixes = ["_L.glb", "_R_D.glb", "_B.glb"];
let count = 0;
for (const base of bases) {
  for (const suf of suffixes) {
    flipGlb180Y(KAT + base + suf);
    count++;
  }
}
console.log("Celkem otoceno souboru:", count);
