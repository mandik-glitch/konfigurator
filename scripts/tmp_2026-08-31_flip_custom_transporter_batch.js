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
const bases = [
  "Ford_Custom_FO10_2012-2023",
  "Ford_Custom_FO21_2012-2023",
  "Ford_Custom_FO27_2012-2023",
  "Ford_Custom_FO28_2012-2023",
  "Ford_Custom_FO31_2023-",
  "Ford_Custom_FO38_2023-",
  "Ford_Custom_FO39_2023-",
  "Ford_Custom_FO47_2023-",
  "Ford_Custom_FO48_2023-",
  "Volkswagen_Transporter_VW12_2003-2023",
  "Volkswagen_Transporter_VW15_2003-2023",
  "Volkswagen_Transporter_VW25_2024-",
  "Volkswagen_Transporter_VW27_2024-",
  "Volkswagen_Transporter_VW29_2024-",
  "Volkswagen_Transporter_VW30_2024-",
];
const DIR = "/opt/konfigurator/webapp/katalog/car_bodies/";
for (const b of bases) {
  for (const suf of ["_B.glb", "_L.glb", "_R_D.glb"]) {
    flipGlb180Y(DIR + b + suf);
  }
}
