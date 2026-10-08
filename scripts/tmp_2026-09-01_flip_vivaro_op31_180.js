// 180-Y flip for Opel Vivaro OP31 (2020- Electric L1) car body - same technique as
// scripts/2026-09-01_flip_expert_vito_180.js / 2026-08-31_flip_car_body_ci25_180.js.
// zMidB measured positive (+1943.2) via 2026-08-31_glb_position_bbox.js -> NEEDS_FLIP.
// Originals backed up to backups/2026-09-01_car_body_vivaro_op31_180_flip/ before this ran.
const fs = require("fs");
const path = require("path");

function flipGlb180Y(p) {
  const buf = fs.readFileSync(p);
  const magic = buf.readUInt32LE(0);
  if (magic !== 0x46546c67) throw new Error(`${p}: not a valid glb`);
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
  if (!json || !binChunk) throw new Error(`${p}: missing JSON or BIN chunk`);

  for (const mesh of json.meshes) {
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

  const newBinLen = binChunk.length;
  const header = Buffer.alloc(12);
  header.writeUInt32LE(0x46546c67, 0);
  header.writeUInt32LE(version, 4);

  const jsonChunkHeader = Buffer.alloc(8);
  jsonChunkHeader.writeUInt32LE(newJsonBuf.length, 0);
  jsonChunkHeader.writeUInt32LE(0x4e4f534a, 4);

  const binChunkHeader = Buffer.alloc(8);
  binChunkHeader.writeUInt32LE(newBinLen, 0);
  binChunkHeader.writeUInt32LE(0x004e4942, 4);

  const newTotalLen = 12 + 8 + newJsonBuf.length + 8 + newBinLen;
  header.writeUInt32LE(newTotalLen, 8);

  const out = Buffer.concat([header, jsonChunkHeader, newJsonBuf, binChunkHeader, binChunk]);
  fs.writeFileSync(p, out);
  console.log(`${path.basename(p)}: OK, ${buf.length} -> ${out.length} bytes`);
}

const DIR = "/opt/konfigurator/webapp/katalog/car_bodies";
const base = "Opel_Vivaro_OP31_2020-";
const suffixes = ["_L.glb", "_R_D.glb", "_B.glb"];
for (const suf of suffixes) {
  flipGlb180Y(path.join(DIR, base + suf));
}
console.log("Done, 3 files flipped.");
