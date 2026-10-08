// Načte SKUTEČNOU geometrii z .glb souboru (POSITION accessor + indexy) do
// THREE.BufferGeometry/Mesh - BEZ GLTFLoaderu, čistě parsováním binárního
// formátu (12bajtová hlavička + JSON chunk + BIN chunk). Vznik: bot8
// 2026-08-19, po Robertově "proč nekontrolujeme matematiku?" - veškeré
// dosavadní Node.js ověřování geometrie spojů v tomhle projektu
// (scripts/2026-08-18_scene_geometry_lib.js::mkProfileEntry) používalo
// SYNTETICKÝ THREE.BoxGeometry(dimX,dimY,dimZ), který je vždy dokonale
// symetrický kolem lokálního počátku - skutečné .glb soubory v
// webapp/katalog/ symetrické být nemusí (viz VLASTNOSTI_PROFILU.md
// "Pravidlo profilů - pivot dílu NENÍ vždy jeho geometrický střed").
// Použitím TÉHLE funkce místo mkProfileEntry() se dá stejná otázka
// ("sedí spoj přesně?") ověřit na reálných datech, ne na aproximaci.
//
// Použití: `npm install` v ROOTU repa (ne ve scripts/, viz package.json),
// pak:
//   const { parseGlbMesh, mkRealProfileEntry } = require("./2026-08-19_glb_real_geometry.js");
//   const { computeConnectorsLocal } = require("./2026-08-18_scene_geometry_lib.js");
//   const entry = mkRealProfileEntry("/opt/konfigurator/webapp/katalog/profil_30x30_uzavreny.glb");
//   // entry.object3d, entry.connectorsLocal - dál použitelné stejně jako
//   // mkProfileEntry() výstup, ale se SKUTEČNOU (ne odhadnutou) geometrií.

const fs = require("fs");
const THREE = require("three");

// OPRAVA bot8 2026-09-18 (nalezeno pri technicke analyze custom_shapes#558,
// dilu product_3219 "Plastovy pant 3030"): puvodni verze cetla JEN
// `json.meshes[0]` - tichy predpoklad "1 GLB = 1 mesh", ktery neplati:
// zmereno napric CELYM katalogem (`webapp/katalog/*.glb`, 2026-09-18) -
// 85 z 495 souboru (17 %) ma VICE nez 1 mesh (az 9), vsechny uzly maji
// identity transform (zadne translation/rotation/scale/matrix), takze
// slouceni pozic+indexu ze VSECH meshu je bezpecne a spravne pro cely
// katalog. Kazde dosavadni pouziti parseGlbMesh/mkRealProfileEntry na
// nekterem z tech 85 souboru tiše merilo jen CAST skutecne geometrie -
// presne trida chyby popsana ve skillu 3d-scena-spoje, "0 nalezu musi
// znamenat zmereno, ne nezmereno". Jednomeshove soubory (413 z 495) se
// timhle chovaji uplne stejne jako pred opravou.
function parseGlbMesh(path) {
  const buf = fs.readFileSync(path);
  const magic = buf.readUInt32LE(0);
  if (magic !== 0x46546c67) throw new Error(`${path}: neni platny .glb (spatna magic hlavicka)`);
  let offset = 12, json = null, binChunk = null;
  while (offset < buf.length) {
    const chunkLen = buf.readUInt32LE(offset);
    const chunkType = buf.readUInt32LE(offset + 4);
    const chunkData = buf.slice(offset + 8, offset + 8 + chunkLen);
    if (chunkType === 0x4e4f534a) json = JSON.parse(chunkData.toString("utf8")); // 'JSON'
    else if (chunkType === 0x004e4942) binChunk = chunkData; // 'BIN\0'
    offset += 8 + chunkLen;
  }
  if (!json) throw new Error(`${path}: chybi JSON chunk`);
  if (!json.meshes || !json.meshes.length) throw new Error(`${path}: soubor neobsahuje zadny mesh`);
  if (!binChunk) throw new Error(`${path}: chybi BIN chunk`);

  // OPRAVA bot8 2026-10-02 (kolizni sweep padal na product_3219 - 3 meshe po 1 primitivu): krome
  // VSECH meshu (2026-09-18) se ted ctou i VSECHNA PRIMITIVA kazdeho meshe (driv jen `primitives[0]`;
  // 50 souboru v katalogu ma mesh s vice primitivy, hlavne car_bodies/ a vandr/ - ty by se merily
  // jen z casti). Dale: indexy UNSIGNED_BYTE (5121), proloženy bufferView (byteStride), primitivum
  // bez indexu ve smesi s indexovanymi (sekvencni indexy). Co se cist neumi (mod != TRIANGLES, sparse
  // accessor, POSITION jinak nez FLOAT) VYHODI chybu - radsi spadnout nez tise zmerit cast.
  // Transformace UZLU se NEAPLIKUJI (identita overena pro cely katalog 2026-09-18; kdo potrebuje
  // vedet, jestli to u daneho souboru plati, pouzije glbRizikaParseru()).
  // Soubory s 1 primitivem na mesh se chovaji bit po bitu stejne jako dřív.
  const posChunks = [];
  const idxChunks = [];
  const prims = [];
  for (const mesh of json.meshes) for (const prim of (mesh.primitives || [])) prims.push(prim);
  if (!prims.length) throw new Error(`${path}: mesh bez primitiv`);
  const anyIndexed = prims.some(pr => pr.indices != null);
  const readFloats = (acc, bv) => {
    const base = (bv.byteOffset || 0) + (acc.byteOffset || 0);
    const stride = bv.byteStride && bv.byteStride !== 12 ? bv.byteStride : 12;
    const abs = binChunk.byteOffset + base;
    if (stride === 12 && abs % 4 === 0) return new Float32Array(binChunk.buffer, abs, acc.count * 3);
    const out = new Float32Array(acc.count * 3);
    const dv = new DataView(binChunk.buffer, binChunk.byteOffset + base);
    for (let i = 0; i < acc.count; i++) for (let k = 0; k < 3; k++) out[i * 3 + k] = dv.getFloat32(i * stride + k * 4, true);
    return out;
  };
  const readIndices = (acc, bv) => {
    const base = (bv.byteOffset || 0) + (acc.byteOffset || 0);
    const size = acc.componentType === 5121 ? 1 : acc.componentType === 5123 ? 2 : acc.componentType === 5125 ? 4 : 0;
    if (!size) throw new Error(`${path}: nepodporovany typ indexu ${acc.componentType}`);
    const dv = new DataView(binChunk.buffer, binChunk.byteOffset + base);
    const stride = bv.byteStride && bv.byteStride > size ? bv.byteStride : size;
    const out = new Uint32Array(acc.count);
    for (let i = 0; i < acc.count; i++) {
      const o = i * stride;
      out[i] = size === 1 ? dv.getUint8(o) : size === 2 ? dv.getUint16(o, true) : dv.getUint32(o, true);
    }
    return out;
  };
  let vertexOffset = 0;
  for (const prim of prims) {
    if (prim.mode != null && prim.mode !== 4) throw new Error(`${path}: primitivum v modu ${prim.mode} (cist umim jen TRIANGLES = 4)`);
    const pa = prim.attributes && prim.attributes.POSITION;
    if (pa == null) throw new Error(`${path}: primitivum bez POSITION`);
    const posAccessor = json.accessors[pa];
    if (posAccessor.sparse || posAccessor.componentType !== 5126 || posAccessor.bufferView == null) {
      throw new Error(`${path}: POSITION accessor, ktery neumim cist (sparse / jine nez FLOAT / bez bufferView)`);
    }
    posChunks.push(readFloats(posAccessor, json.bufferViews[posAccessor.bufferView]));

    if (prim.indices != null) {
      const idxAccessor = json.accessors[prim.indices];
      if (idxAccessor.sparse || idxAccessor.bufferView == null) throw new Error(`${path}: index accessor, ktery neumim cist`);
      const raw = readIndices(idxAccessor, json.bufferViews[idxAccessor.bufferView]);
      for (let i = 0; i < raw.length; i++) raw[i] += vertexOffset;
      idxChunks.push(raw);
    } else if (anyIndexed) {
      const seq = new Uint32Array(posAccessor.count);   // primitivum bez indexu ve smesi s indexovanymi
      for (let i = 0; i < seq.length; i++) seq[i] = vertexOffset + i;
      idxChunks.push(seq);
    }
    vertexOffset += posAccessor.count;
  }

  let positions;
  if (posChunks.length === 1) {
    positions = posChunks[0];
  } else {
    const totalLen = posChunks.reduce((s, c) => s + c.length, 0);
    positions = new Float32Array(totalLen);
    let p = 0;
    for (const c of posChunks) { positions.set(c, p); p += c.length; }
  }

  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  if (anyIndexed && idxChunks.length) {
    const totalIdx = idxChunks.reduce((s, c) => s + c.length, 0);
    const merged = new Uint32Array(totalIdx);
    let p = 0;
    for (const c of idxChunks) { merged.set(c, p); p += c.length; }
    geo.setIndex(new THREE.BufferAttribute(merged, 1));
  }
  return new THREE.Mesh(geo);
}

// Co parseGlbMesh u daneho souboru NEUMI a tise by to zmerilo spatne: transformace uzlu (matrix /
// translation / rotation / scale != identita). [] = parser pokryva celou geometrii. Pouziva ji
// pojistka kolizniho sweepu (2026-09-11_mesh_kolize_lib.js) - "0 nalezu" musi znamenat ZMERENO.
function glbRizikaParseru(path) {
  const buf = fs.readFileSync(path);
  let off = 12, json = null;
  while (off < buf.length) {
    const l = buf.readUInt32LE(off), t = buf.readUInt32LE(off + 4);
    if (t === 0x4e4f534a) json = JSON.parse(buf.slice(off + 8, off + 8 + l).toString("utf8"));
    off += 8 + l;
  }
  const rizika = [];
  if (!json) return ["chybi JSON chunk"];
  const E = 1e-6, ID = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1];
  (json.nodes || []).forEach((n, i) => {
    const m = n.matrix && n.matrix.some((v, k) => Math.abs(v - ID[k]) > E);
    const t = n.translation && n.translation.some(v => Math.abs(v) > E);
    const r = n.rotation && n.rotation.some((v, k) => Math.abs(v - [0, 0, 0, 1][k]) > E);
    const s = n.scale && n.scale.some(v => Math.abs(v - 1) > E);
    if (m || t || r || s) rizika.push(`uzel ${i}${n.name ? " (" + n.name + ")" : ""} ma transformaci (parser ji neaplikuje)`);
  });
  return rizika;
}

// Rychlý bbox přímo z accessor.min/max (bez čtení binárního chunku) - pro
// případy, kdy stačí jen rozměry/střed, ne celá mesh geometrie.
function glbBoundingBox(path) {
  const buf = fs.readFileSync(path);
  let offset = 12, json = null;
  while (offset < buf.length) {
    const chunkLen = buf.readUInt32LE(offset);
    const chunkType = buf.readUInt32LE(offset + 4);
    const chunkData = buf.slice(offset + 8, offset + 8 + chunkLen);
    if (chunkType === 0x4e4f534a) json = JSON.parse(chunkData.toString("utf8"));
    offset += 8 + chunkLen;
  }
  const a = json.accessors.find(a => a.type === "VEC3" && a.min && a.max && (a.max[1] - a.min[1]) > 1);
  if (!a) throw new Error(`${path}: nenasel jsem POSITION accessor s min/max`);
  return {
    min: new THREE.Vector3(...a.min),
    max: new THREE.Vector3(...a.max),
    center: new THREE.Vector3((a.min[0] + a.max[0]) / 2, (a.min[1] + a.max[1]) / 2, (a.min[2] + a.max[2]) / 2),
    size: new THREE.Vector3(a.max[0] - a.min[0], a.max[1] - a.min[1], a.max[2] - a.min[2]),
  };
}

function mkRealProfileEntry(glbPath, computeConnectorsLocalFn) {
  const obj = parseGlbMesh(glbPath);
  const connectorsLocal = computeConnectorsLocalFn ? computeConnectorsLocalFn(obj) : undefined;
  return { object3d: obj, connectorsLocal };
}

module.exports = { parseGlbMesh, glbBoundingBox, mkRealProfileEntry, glbRizikaParseru };
