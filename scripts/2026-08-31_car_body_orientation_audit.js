const fs = require("fs");
const path = require("path");

const KATALOG_DIR = "/opt/konfigurator/webapp/katalog/";
// Refresh s aktualnim obsahem DB pred spustenim (uz muze byt zastarale):
// mysql ... -N -e "SELECT id, name, glb_file FROM car_bodies WHERE glb_file IS NOT NULL ORDER BY glb_file" > scripts/2026-08-31_car_bodies_dump.tsv
const TSV = __dirname + "/2026-08-31_car_bodies_dump.tsv";

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
  if (!json) throw new Error("missing JSON chunk");
  let minX = Infinity, minY = Infinity, minZ = Infinity;
  let maxX = -Infinity, maxY = -Infinity, maxZ = -Infinity;
  for (const mesh of (json.meshes || [])) {
    for (const prim of mesh.primitives) {
      const accIdx = prim.attributes.POSITION;
      if (accIdx == null) continue;
      const acc = json.accessors[accIdx];
      if (acc.min && acc.max) {
        minX = Math.min(minX, acc.min[0]); maxX = Math.max(maxX, acc.max[0]);
        minY = Math.min(minY, acc.min[1]); maxY = Math.max(maxY, acc.max[1]);
        minZ = Math.min(minZ, acc.min[2]); maxZ = Math.max(maxZ, acc.max[2]);
      }
    }
  }
  return { minX, maxX, minY, maxY, minZ, maxZ };
}

// Parse TSV rows
const rows = fs.readFileSync(TSV, "utf8").split("\n").filter(Boolean).map(line => {
  const [id, name, glb_file] = line.split("\t");
  return { id, name, glb_file };
});

// Group by base (strip suffix)
const groups = new Map(); // base -> {L, R_D, B, rows:[]}
for (const row of rows) {
  const gf = row.glb_file;
  let base, role;
  if (gf.endsWith("_L.glb")) { base = gf.slice(0, -"_L.glb".length); role = "L"; }
  else if (gf.endsWith("_R_D.glb")) { base = gf.slice(0, -"_R_D.glb".length); role = "R_D"; }
  else if (gf.endsWith("_B_wall.glb")) { base = gf.slice(0, -"_B_wall.glb".length); role = "B"; }
  else if (gf.endsWith("_B.glb")) { base = gf.slice(0, -"_B.glb".length); role = "B"; }
  else { base = gf; role = "?"; }
  if (!groups.has(base)) groups.set(base, { rows: [] });
  groups.get(base)[role] = row;
  groups.get(base).rows.push(row);
}

const results = [];
for (const [base, g] of groups) {
  const rec = { base, name: null, ids: g.rows.map(r => r.id).join("/") };
  if (g.B) {
    const absPath = path.join(KATALOG_DIR, g.B.glb_file);
    if (fs.existsSync(absPath)) {
      try {
        const bbox = glbPositionBbox(absPath);
        rec.B_minZ = bbox.minZ;
        rec.B_maxZ = bbox.maxZ;
        rec.B_midZ = (bbox.minZ + bbox.maxZ) / 2;
        rec.B_minX = bbox.minX; rec.B_maxX = bbox.maxX;
      } catch (e) {
        rec.error = "B bbox error: " + e.message;
      }
    } else {
      rec.error = "B file missing on disk: " + g.B.glb_file;
    }
    rec.B_name = g.B.name;
  } else {
    rec.error = "no B row found";
  }
  if (g.L) {
    const absPath = path.join(KATALOG_DIR, g.L.glb_file);
    if (fs.existsSync(absPath)) {
      try {
        const bbox = glbPositionBbox(absPath);
        rec.L_minZ = bbox.minZ; rec.L_maxZ = bbox.maxZ;
        rec.L_minX = bbox.minX; rec.L_maxX = bbox.maxX;
      } catch (e) {}
    }
  }
  if (g.R_D) {
    const absPath = path.join(KATALOG_DIR, g.R_D.glb_file);
    if (fs.existsSync(absPath)) {
      try {
        const bbox = glbPositionBbox(absPath);
        rec.RD_minZ = bbox.minZ; rec.RD_maxZ = bbox.maxZ;
      } catch (e) {}
    }
  }
  if (rec.B_midZ != null) {
    if (rec.B_midZ < -50) rec.verdict = "OK";
    else if (rec.B_midZ > 50) rec.verdict = "NEEDS_FLIP";
    else rec.verdict = "UNCERTAIN(near zero)";
  } else {
    rec.verdict = "UNCERTAIN(" + (rec.error||"?") + ")";
  }
  results.push(rec);
}

results.sort((a,b) => a.base.localeCompare(b.base));
for (const r of results) {
  console.log(JSON.stringify(r));
}

// summary
const counts = {};
for (const r of results) counts[r.verdict] = (counts[r.verdict]||0)+1;
console.error("SUMMARY:", JSON.stringify(counts, null, 2));
console.error("TOTAL MODELS:", results.length);
