const fs = require("fs");
function glbPositionBbox(absPath) {
  const buf = fs.readFileSync(absPath);
  const magic = buf.readUInt32LE(0);
  if (magic !== 0x46546c67) throw new Error(`not a valid glb`);
  let offset = 12, json = null;
  while (offset < buf.length) {
    const chunkLen = buf.readUInt32LE(offset);
    const chunkType = buf.readUInt32LE(offset + 4);
    const chunkData = buf.slice(offset + 8, offset + 8 + chunkLen);
    if (chunkType === 0x4e4f534a) { json = JSON.parse(chunkData.toString("utf8")); }
    offset += 8 + chunkLen;
  }
  let minX = Infinity, maxX = -Infinity;
  for (const mesh of (json.meshes || [])) {
    for (const prim of mesh.primitives) {
      const accIdx = prim.attributes.POSITION;
      if (accIdx == null) continue;
      const acc = json.accessors[accIdx];
      if (acc.min && acc.max) {
        minX = Math.min(minX, acc.min[0]); maxX = Math.max(maxX, acc.max[0]);
      }
    }
  }
  return { minX, maxX };
}
const DIR = "/opt/konfigurator/webapp/katalog/";
const rows = fs.readFileSync("/tmp/L_ids.txt", "utf8").trim().split("\n").map(l => {
  const [id, glb] = l.trim().split(/\s+/);
  return { id, glb };
});
for (const r of rows) {
  const bbox = glbPositionBbox(DIR + r.glb);
  const mid = (bbox.minX + bbox.maxX) / 2;
  console.log(r.id, r.glb, "minX=" + bbox.minX.toFixed(1), "maxX=" + bbox.maxX.toFixed(1), "mid=" + mid.toFixed(1), mid < 0 ? "NEGATIVE(mirror)" : "POSITIVE(normal)");
}
