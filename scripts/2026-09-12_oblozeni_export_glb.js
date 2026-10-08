// Export 4 panelu obkladu K-075 (backups/2026-09-12_oblozeni_K075_
// obtazene.json) jako skutecne .glb soubory pro katalog - Robert
// 2026-09-12, pres bot3: "vloz to normalne jako ostatni tvary... vyber
// ze seznamu, vloz do sceny, posouvat, otacet, koukat".
//
// Kazdy panel: triangulace 2D projekce (THREE.ShapeUtils.triangulateShape,
// stejna technika jako docasny scene.html overlay), skutecne vrcholy
// jsou puvodni 3D souradnice z obtazeneho souboru (zadna rotace roviny).
// Normala je konstantni pro cely (rovinny) panel - spocita se z prvnich
// 3 bodu obrysu.
//
// Minimalni rucni GLB writer (12B header + JSON chunk + BIN chunk),
// stejny format, jaky cely projekt cely den JEN CETL (2026-08-19_glb_
// real_geometry.js) - tady poprve i ZAPISUJE, formát je uz dukladne
// znamy z opakovaneho parsovani.
const fs = require("fs");
const THREE = require("three");

// bot3 2026-09-12, 2. kolo: boky uz NEJSOU rovinne (X se meni bod od
// bodu - napasovano na skutecne zakrivenou stenu, 10mm pod povrchem).
// Konstantni normala uz proto nestaci - normala se pocita PER
// TROJUHELNIK a zprumeruje se do kazdeho vertexu (standardni smooth
// shading), stejny princip jako computeVertexNormals() v three.js.
//
// 3. kolo (bot3): puvodni data byla poradi pixelu v obrazku, ne obvod -
// "SERAZENE" soubor uz je skutecny uzavreny polygon (`uzavreny: true`,
// prvni bod == posledni). Ten duplicitni uzaviraci bod se PRED
// triangulaci odstranuje (degenerovana nulova hrana by jinak mohla
// zmást ear-clipping) - polygon je uzavreny uz implicitne (posledni bod
// -> prvni), duplicita nic nepridava.
const IN_FILE = "/opt/konfigurator/backups/2026-09-12_oblozeni_K075_SERAZENE.json";
const OUT_DIR = "/opt/konfigurator/webapp/katalog/kontrolni_pomucky/";

function triangulate(dilRaw) {
  const dil = { ...dilRaw };
  if (dil.body.length > 1) {
    const [x1, y1, z1] = dil.body[0];
    const [x2, y2, z2] = dil.body[dil.body.length - 1];
    if (x1 === x2 && y1 === y2 && z1 === z2) dil.body = dil.body.slice(0, -1);
  }
  const pts2d = dil.rovina === "XZ"
    ? dil.body.map(p => new THREE.Vector2(p[0], p[2]))
    : dil.body.map(p => new THREE.Vector2(p[1], p[2]));
  const triangles = THREE.ShapeUtils.triangulateShape(pts2d, []);
  const positions = new Float32Array(dil.body.length * 3);
  dil.body.forEach((p, i) => { positions[i * 3] = p[0]; positions[i * 3 + 1] = p[1]; positions[i * 3 + 2] = p[2]; });
  const indices = new Uint32Array(triangles.length * 3);
  triangles.forEach((t, i) => { indices[i * 3] = t[0]; indices[i * 3 + 1] = t[1]; indices[i * 3 + 2] = t[2]; });

  const normalsAcc = new Array(dil.body.length).fill(null).map(() => new THREE.Vector3());
  const vA = new THREE.Vector3(), vB = new THREE.Vector3(), vC = new THREE.Vector3();
  for (const [ia, ib, ic] of triangles) {
    vA.set(positions[ia*3], positions[ia*3+1], positions[ia*3+2]);
    vB.set(positions[ib*3], positions[ib*3+1], positions[ib*3+2]);
    vC.set(positions[ic*3], positions[ic*3+1], positions[ic*3+2]);
    const faceN = new THREE.Vector3().subVectors(vB, vA).cross(new THREE.Vector3().subVectors(vC, vA));
    normalsAcc[ia].add(faceN); normalsAcc[ib].add(faceN); normalsAcc[ic].add(faceN);
  }
  const normals = new Float32Array(dil.body.length * 3);
  normalsAcc.forEach((n, i) => {
    if (n.lengthSq() < 1e-12) n.set(0, 1, 0); // izolovany vertex (netriangulovany) - nahradni normala
    else n.normalize();
    normals[i*3]=n.x; normals[i*3+1]=n.y; normals[i*3+2]=n.z;
  });
  return { positions, normals, indices };
}

function pad4(buf, fillByte) {
  const rem = buf.length % 4;
  if (rem === 0) return buf;
  const pad = Buffer.alloc(4 - rem, fillByte != null ? fillByte : 0);
  return Buffer.concat([buf, pad]);
}

function writeGlb(outPath, { positions, normals, indices }) {
  const posBuf = Buffer.from(positions.buffer, positions.byteOffset, positions.byteLength);
  const nrmBuf = Buffer.from(normals.buffer, normals.byteOffset, normals.byteLength);
  const idxBuf = Buffer.from(indices.buffer, indices.byteOffset, indices.byteLength);
  const posBufPadded = pad4(posBuf), nrmBufPadded = pad4(nrmBuf), idxBufPadded = pad4(idxBuf);
  const bin = Buffer.concat([posBufPadded, nrmBufPadded, idxBufPadded]);

  let minX=Infinity,minY=Infinity,minZ=Infinity,maxX=-Infinity,maxY=-Infinity,maxZ=-Infinity;
  for (let i=0;i<positions.length;i+=3){
    const x=positions[i],y=positions[i+1],z=positions[i+2];
    if(x<minX)minX=x; if(x>maxX)maxX=x;
    if(y<minY)minY=y; if(y>maxY)maxY=y;
    if(z<minZ)minZ=z; if(z>maxZ)maxZ=z;
  }

  const json = {
    asset: { version: "2.0", generator: "2026-09-12_oblozeni_export_glb.js" },
    scene: 0,
    scenes: [{ nodes: [0] }],
    nodes: [{ mesh: 0, name: "kontrolni_pomucka" }],
    meshes: [{ primitives: [{ attributes: { POSITION: 0, NORMAL: 1 }, indices: 2 }] }],
    buffers: [{ byteLength: bin.length }],
    bufferViews: [
      { buffer: 0, byteOffset: 0, byteLength: posBuf.length, target: 34962 },
      { buffer: 0, byteOffset: posBufPadded.length, byteLength: nrmBuf.length, target: 34962 },
      { buffer: 0, byteOffset: posBufPadded.length + nrmBufPadded.length, byteLength: idxBuf.length, target: 34963 },
    ],
    accessors: [
      { bufferView: 0, componentType: 5126, count: positions.length / 3, type: "VEC3", min: [minX,minY,minZ], max: [maxX,maxY,maxZ] },
      { bufferView: 1, componentType: 5126, count: normals.length / 3, type: "VEC3" },
      { bufferView: 2, componentType: 5125, count: indices.length, type: "SCALAR" },
    ],
  };
  const jsonBuf = pad4(Buffer.from(JSON.stringify(json), "utf8"), 0x20); // JSON chunk pad = mezera (spec), ne null - jinak JSON.parse spadne na "unexpected char after JSON"

  const header = Buffer.alloc(12);
  header.writeUInt32LE(0x46546c67, 0); // magic 'glTF'
  header.writeUInt32LE(2, 4); // version
  const totalLen = 12 + 8 + jsonBuf.length + 8 + bin.length;
  header.writeUInt32LE(totalLen, 8);

  const jsonChunkHeader = Buffer.alloc(8);
  jsonChunkHeader.writeUInt32LE(jsonBuf.length, 0);
  jsonChunkHeader.writeUInt32LE(0x4e4f534a, 4); // 'JSON'

  const binChunkHeader = Buffer.alloc(8);
  binChunkHeader.writeUInt32LE(bin.length, 0);
  binChunkHeader.writeUInt32LE(0x004e4942, 4); // 'BIN\0'

  const out = Buffer.concat([header, jsonChunkHeader, jsonBuf, binChunkHeader, bin]);
  fs.writeFileSync(outPath, out);
  return { bytes: out.length, verts: positions.length / 3, tris: indices.length / 3 };
}

fs.mkdirSync(OUT_DIR, { recursive: true });
const data = JSON.parse(fs.readFileSync(IN_FILE, "utf8"));
const results = [];
for (const dil of data.dily) {
  const geo = triangulate(dil);
  const outPath = OUT_DIR + "K075_oblozeni_" + dil.nazev + ".glb";
  const info = writeGlb(outPath, geo);
  results.push({ nazev: dil.nazev, outPath, ...info });
  console.log(`${outPath}: ${info.verts}v/${info.tris}t, ${(info.bytes/1024).toFixed(1)}kB`);
}
fs.writeFileSync("/tmp/oblozeni_export_result.json", JSON.stringify(results));
