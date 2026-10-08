// Export "obklad desky" (offsetnuta REALNA plocha karoserie, viz
// 2026-09-12_karoserie_obklad_desky.js) jako .glb - nahrazuje drivejsi
// pokroucene "obtazene z fotky" panely presne tou technikou, jakou chtel
// Robert: "mela kopirovat tvar karoserie nejakym jednoduchym efektnim
// zpusobem" (2026-09-12). Zadne fitovani/binovani - vertexy jsou PRIMO
// z realne site karoserie, jen posunute podel normaly dovnitr, takze
// topologie (a tedy hladkost) je zdedena 1:1 od realne karoserie.
const fs = require("fs");
const THREE = require("three");

const IN_FILE = process.argv[2];
const OUT_DIR = "/opt/konfigurator/webapp/katalog/kontrolni_pomucky/";

function computeVertexNormals(verts, faces) {
  const n = verts.length;
  const acc = new Array(n).fill(null).map(() => new THREE.Vector3());
  const vA = new THREE.Vector3(), vB = new THREE.Vector3(), vC = new THREE.Vector3();
  for (const [ia, ib, ic] of faces) {
    vA.set(...verts[ia]); vB.set(...verts[ib]); vC.set(...verts[ic]);
    const faceN = new THREE.Vector3().subVectors(vB, vA).cross(new THREE.Vector3().subVectors(vC, vA));
    acc[ia].add(faceN); acc[ib].add(faceN); acc[ic].add(faceN);
  }
  const normals = new Float32Array(n * 3);
  acc.forEach((v, i) => {
    if (v.lengthSq() < 1e-12) v.set(0, 1, 0);
    else v.normalize();
    normals[i * 3] = v.x; normals[i * 3 + 1] = v.y; normals[i * 3 + 2] = v.z;
  });
  return normals;
}

function pad4(buf, fillByte) {
  const rem = buf.length % 4;
  if (rem === 0) return buf;
  return Buffer.concat([buf, Buffer.alloc(4 - rem, fillByte != null ? fillByte : 0)]);
}

function writeGlb(outPath, verts, faces) {
  const n = verts.length;
  const positions = new Float32Array(n * 3);
  verts.forEach((v, i) => { positions[i * 3] = v[0]; positions[i * 3 + 1] = v[1]; positions[i * 3 + 2] = v[2]; });
  const normals = computeVertexNormals(verts, faces);
  const indices = new Uint32Array(faces.length * 3);
  faces.forEach((f, i) => { indices[i * 3] = f[0]; indices[i * 3 + 1] = f[1]; indices[i * 3 + 2] = f[2]; });

  const posBuf = pad4(Buffer.from(positions.buffer, positions.byteOffset, positions.byteLength));
  const nrmBuf = pad4(Buffer.from(normals.buffer, normals.byteOffset, normals.byteLength));
  const idxBuf = pad4(Buffer.from(indices.buffer, indices.byteOffset, indices.byteLength));
  const bin = Buffer.concat([posBuf, nrmBuf, idxBuf]);

  let minX=Infinity,minY=Infinity,minZ=Infinity,maxX=-Infinity,maxY=-Infinity,maxZ=-Infinity;
  for (let i=0;i<positions.length;i+=3){
    const x=positions[i],y=positions[i+1],z=positions[i+2];
    if(x<minX)minX=x; if(x>maxX)maxX=x;
    if(y<minY)minY=y; if(y>maxY)maxY=y;
    if(z<minZ)minZ=z; if(z>maxZ)maxZ=z;
  }
  const json = {
    asset: { version: "2.0", generator: "tmp_2026-09-12_bot8_obklad_desky_export_glb.js" },
    scene: 0, scenes: [{ nodes: [0] }],
    nodes: [{ mesh: 0, name: "kontrolni_pomucka" }],
    meshes: [{ primitives: [{ attributes: { POSITION: 0, NORMAL: 1 }, indices: 2 }] }],
    buffers: [{ byteLength: bin.length }],
    bufferViews: [
      { buffer: 0, byteOffset: 0, byteLength: posBuf.length, target: 34962 },
      { buffer: 0, byteOffset: posBuf.length, byteLength: nrmBuf.length, target: 34962 },
      { buffer: 0, byteOffset: posBuf.length + nrmBuf.length, byteLength: idxBuf.length, target: 34963 },
    ],
    accessors: [
      { bufferView: 0, componentType: 5126, count: positions.length / 3, type: "VEC3", min: [minX,minY,minZ], max: [maxX,maxY,maxZ] },
      { bufferView: 1, componentType: 5126, count: normals.length / 3, type: "VEC3" },
      { bufferView: 2, componentType: 5125, count: indices.length, type: "SCALAR" },
    ],
  };
  const jsonBuf = pad4(Buffer.from(JSON.stringify(json), "utf8"), 0x20);
  const header = Buffer.alloc(12);
  header.writeUInt32LE(0x46546c67, 0);
  header.writeUInt32LE(2, 4);
  header.writeUInt32LE(12 + 8 + jsonBuf.length + 8 + bin.length, 8);
  const jsonChunkHeader = Buffer.alloc(8);
  jsonChunkHeader.writeUInt32LE(jsonBuf.length, 0);
  jsonChunkHeader.writeUInt32LE(0x4e4f534a, 4);
  const binChunkHeader = Buffer.alloc(8);
  binChunkHeader.writeUInt32LE(bin.length, 0);
  binChunkHeader.writeUInt32LE(0x004e4942, 4);
  const out = Buffer.concat([header, jsonChunkHeader, jsonBuf, binChunkHeader, bin]);
  fs.writeFileSync(outPath, out);
  return { bytes: out.length, verts: n, tris: faces.length };
}

// Orez podle SKUTECNEHO OBRYSU trasovaneho z fotky (Robert: "ty panely
// obkladu uz meli svuj obrysovy tvar z toho obrazku" - obdelnikovy
// bounding-box vyrez ho zahodil, napr. vyrezy kolem podbehu/rohy). Pouzit
// POINT-IN-POLYGON test proti skutecnemu obvodu (SERAZENE data), ne min/max.
const SERAZENE = JSON.parse(fs.readFileSync("/opt/konfigurator/backups/2026-09-12_oblozeni_K075_SERAZENE.json", "utf8"));
const OUTLINES = {};
for (const dil of SERAZENE.dily) {
  if (!(dil.nazev in { "bok-levy": 1, "bok-pravy": 1 })) continue;
  let body = dil.body;
  const [x1, y1, z1] = body[0], [x2, y2, z2] = body[body.length - 1];
  if (x1 === x2 && y1 === y2 && z1 === z2) body = body.slice(0, -1);
  OUTLINES[dil.nazev] = body.map(p => [p[1], p[2]]); // (Y,Z) - "rovina": YZ
}

function pointInPolygon(y, z, poly) {
  let inside = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [yi, zi] = poly[i], [yj, zj] = poly[j];
    const intersect = ((zi > z) !== (zj > z)) && (y < (yj - yi) * (z - zi) / (zj - zi) + yi);
    if (intersect) inside = !inside;
  }
  return inside;
}

function cropMesh(verts, faces, name) {
  const poly = OUTLINES[name];
  const inBounds = (v) => pointInPolygon(v[1], v[2], poly);
  const keepFaces = faces.filter(([ia, ib, ic]) => inBounds(verts[ia]) && inBounds(verts[ib]) && inBounds(verts[ic]));
  const usedIdx = new Map();
  const newVerts = [];
  const remap = (i) => {
    if (!usedIdx.has(i)) { usedIdx.set(i, newVerts.length); newVerts.push(verts[i]); }
    return usedIdx.get(i);
  };
  const newFaces = keepFaces.map(([ia, ib, ic]) => [remap(ia), remap(ib), remap(ic)]);
  return { verts: newVerts, faces: newFaces };
}

const data = JSON.parse(fs.readFileSync(IN_FILE, "utf8"));
if (!data.ok) { console.error("vstup neni ok:", data.error); process.exit(1); }
fs.mkdirSync(OUT_DIR, { recursive: true });

const NAME_MAP = { L: "bok-levy", R_D: "bok-pravy" };
for (const [key, panel] of Object.entries(data.panels)) {
  if (!NAME_MAP[key]) continue; // jen boky - podlaha uz je rovinna, jina technika, netykalo se stiznosti
  const name = NAME_MAP[key];
  const cropped = cropMesh(panel.verts, panel.faces, name);
  const outPath = OUT_DIR + "K075_oblozeni_" + name + ".glb";
  const info = writeGlb(outPath, cropped.verts, cropped.faces);
  console.log(`${outPath}: ${info.verts}v/${info.tris}t (orezano z ${panel.vertCount}v/${panel.triCount}t), ${(info.bytes/1024).toFixed(1)}kB`);
}
