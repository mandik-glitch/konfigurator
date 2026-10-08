// Physically flip all 19 Proace-family car bodies (L/R_D/B, 57 files) 180deg
// about Y, per orientation audit (all 19 verdict=NEEDS_FLIP, verified live
// against TO07 and TO25 matching the precomputed audit jsonl exactly).
// Backups already copied to backups/2026-08-31_car_body_proace_family_180_flip/
// before this script runs. Template: tmp_2026-08-30_flip_car_body_180.js.
const fs = require("fs");

function flipGlb180Y(path) {
  const buf = fs.readFileSync(path);
  const magic = buf.readUInt32LE(0);
  if (magic !== 0x46546c67) throw new Error(`${path}: not a valid glb`);
  const version = buf.readUInt32LE(4);
  let offset = 12, json = null, binChunk = null;
  while (offset < buf.length) {
    const chunkLen = buf.readUInt32LE(offset);
    const chunkType = buf.readUInt32LE(offset + 4);
    const chunkData = buf.slice(offset + 8, offset + 8 + chunkLen);
    if (chunkType === 0x4e4f534a) { json = JSON.parse(chunkData.toString("utf8")); }
    else if (chunkType === 0x004e4942) { binChunk = Buffer.from(chunkData); }
    offset += 8 + chunkLen;
  }
  if (!json || !binChunk) throw new Error(`${path}: missing JSON or BIN chunk`);

  for (const mesh of json.meshes || []) {
    for (const prim of mesh.primitives) {
      ["POSITION", "NORMAL"].forEach(attrName => {
        const accIdx = prim.attributes[attrName];
        if (accIdx == null) return;
        const acc = json.accessors[accIdx];
        const bv = json.bufferViews[acc.bufferView];
        const byteOffset = (bv.byteOffset || 0) + (acc.byteOffset || 0);
        const floatCount = acc.count * 3;
        const arr = new Float32Array(binChunk.buffer, binChunk.byteOffset + byteOffset, floatCount);
        for (let i = 0; i < arr.length; i += 3) {
          arr[i] = -arr[i];
          arr[i + 2] = -arr[i + 2];
        }
        if (acc.min && acc.max) {
          const newMinX = -acc.max[0], newMaxX = -acc.min[0];
          const newMinZ = -acc.max[2], newMaxZ = -acc.min[2];
          acc.min = [newMinX, acc.min[1], newMinZ];
          acc.max = [newMaxX, acc.max[1], newMaxZ];
        }
      });
    }
  }

  const newJsonStr = JSON.stringify(json);
  let newJsonBuf = Buffer.from(newJsonStr, "utf8");
  const pad = (4 - (newJsonBuf.length % 4)) % 4;
  if (pad) newJsonBuf = Buffer.concat([newJsonBuf, Buffer.alloc(pad, 0x20)]);

  const header = Buffer.alloc(12);
  header.writeUInt32LE(0x46546c67, 0);
  header.writeUInt32LE(version, 4);

  const jsonChunkHeader = Buffer.alloc(8);
  jsonChunkHeader.writeUInt32LE(newJsonBuf.length, 0);
  jsonChunkHeader.writeUInt32LE(0x4e4f534a, 4);

  const binChunkHeader = Buffer.alloc(8);
  binChunkHeader.writeUInt32LE(binChunk.length, 0);
  binChunkHeader.writeUInt32LE(0x004e4942, 4);

  const newTotalLen = 12 + 8 + newJsonBuf.length + 8 + binChunk.length;
  header.writeUInt32LE(newTotalLen, 8);

  const out = Buffer.concat([header, jsonChunkHeader, newJsonBuf, binChunkHeader, binChunk]);
  fs.writeFileSync(path, out);
  console.log(`${path}: OK, ${buf.length} -> ${out.length} bytes`);
}

const BASES = [
  "Toyota_Proace City_TO11_2020-",
  "Toyota_Proace City_TO19_2020-",
  "Toyota_Proace City_TO20_2020-",
  "Toyota_Proace Max_TO14_2024-",
  "Toyota_Proace Max_TO15_2024-",
  "Toyota_Proace Max_TO16_2024-",
  "Toyota_Proace Max_TO18_2024-",
  "Toyota_Proace Max_TO24_2024-",
  "Toyota_Proace Max_TO25_2024-",
  "Toyota_Proace Max_TO26_2024-",
  "Toyota_Proace_City_TO10_2020-",
  "Toyota_Proace_TO07_2020-",
  "Toyota_Proace_TO08_2020-",
  "Toyota_Proace_TO09_2020-",
  "Toyota_Proace_TO12_2020-",
  "Toyota_Proace_TO17_2020-",
  "Toyota_Proace_TO21_2020-",
  "Toyota_Proace_TO22_2020-",
  "Toyota_Proace_TO23_2020-",
];
const DIR = "/opt/konfigurator/webapp/katalog/car_bodies/";
for (const b of BASES) {
  for (const suf of ["_L.glb", "_R_D.glb", "_B.glb"]) {
    flipGlb180Y(DIR + b + suf);
  }
}
console.log("DONE, flipped", BASES.length * 3, "files");
