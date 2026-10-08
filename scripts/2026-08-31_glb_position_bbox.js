const fs = require("fs");

function glbBbox(path) {
  const buf = fs.readFileSync(path);
  const magic = buf.readUInt32LE(0);
  if (magic !== 0x46546c67) throw new Error(`${path}: not a valid glb`);
  let offset = 12, json = null, binChunk = null;
  while (offset < buf.length) {
    const chunkLen = buf.readUInt32LE(offset);
    const chunkType = buf.readUInt32LE(offset + 4);
    const chunkData = buf.slice(offset + 8, offset + 8 + chunkLen);
    if (chunkType === 0x4e4f534a) { json = JSON.parse(chunkData.toString("utf8")); }
    else if (chunkType === 0x004e4942) { binChunk = Buffer.from(chunkData); }
    offset += 8 + chunkLen;
  }
  if (!json) throw new Error(`${path}: missing JSON chunk`);

  // Aggregate min/max across ALL meshes/primitives (some files may have >1 primitive)
  let minX = Infinity, minY = Infinity, minZ = Infinity;
  let maxX = -Infinity, maxY = -Infinity, maxZ = -Infinity;
  let usedAccessorMinMax = true;
  for (const mesh of (json.meshes || [])) {
    for (const prim of mesh.primitives) {
      const accIdx = prim.attributes.POSITION;
      if (accIdx == null) continue;
      const acc = json.accessors[accIdx];
      if (acc.min && acc.max) {
        minX = Math.min(minX, acc.min[0]); maxX = Math.max(maxX, acc.max[0]);
        minY = Math.min(minY, acc.min[1]); maxY = Math.max(maxY, acc.max[1]);
        minZ = Math.min(minZ, acc.min[2]); maxZ = Math.max(maxZ, acc.max[2]);
      } else {
        usedAccessorMinMax = false;
      }
    }
  }
  return { minX, maxX, minY, maxY, minZ, maxZ, usedAccessorMinMax };
}

const files = process.argv.slice(2);
for (const f of files) {
  try {
    const b = glbBbox(f);
    console.log(JSON.stringify({ file: f, ...b }));
  } catch (e) {
    console.log(JSON.stringify({ file: f, error: String(e) }));
  }
}
