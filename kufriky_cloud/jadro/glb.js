// Zápis GLB (glTF 2.0 binární) z vlastních skupin/dílů. Jednotky mm, osy souboru X, Y, Z (Z = výška) – konvence katalogu.
import { finalizePart } from './mesh.js';
import fs from 'node:fs';

export const MATERIALY = {
  cerna:      { color: [0.020, 0.020, 0.023], metallic: 0.0, roughness: 0.55 },   // černý PP/PA korpus (lineární sRGB)
  cerna_mat:  { color: [0.010, 0.010, 0.012], metallic: 0.0, roughness: 0.82 },   // vroubkování, guma, madlo
  seda:       { color: [0.085, 0.085, 0.095], metallic: 0.0, roughness: 0.55 },   // šedá (TPE, hrany)
  cervena:    { color: [0.58, 0.012, 0.028], metallic: 0.0, roughness: 0.42 },    // červený PP
  cira:       { color: [0.90, 0.94, 0.96], metallic: 0.0, roughness: 0.10, alpha: 0.22 }, // čirý PC (víko, boxy)
  cira_kour:  { color: [0.40, 0.42, 0.45], metallic: 0.0, roughness: 0.12, alpha: 0.40 }, // kouřové PC
  vicko_cira: { color: [0.60, 0.63, 0.66], metallic: 0.0, roughness: 0.12, alpha: 0.30 },   // lehce zakouřené čiré víko
  pozink:     { color: [0.40, 0.42, 0.45], metallic: 0.85, roughness: 0.48 },       // pozinkovaný plech
  plast_bily: { color: [0.80, 0.80, 0.78], metallic: 0.0, roughness: 0.38 },        // bílý plast (POM/PA)
  ocel:       { color: [0.78, 0.79, 0.82], metallic: 1.0, roughness: 0.30 },      // nerez
  bila:       { color: [0.80, 0.80, 0.80], metallic: 0.0, roughness: 0.5 },
  cervena_pruhl: { color: [0.62, 0.02, 0.04], metallic: 0.0, roughness: 0.35, alpha: 0.80 },
};

function align4(n) { return (n + 3) & ~3; }

// groups: kořenová Group; meta: objekt do asset.extras
export function writeGLB(root, file, meta = {}) {
  const gltf = { asset: { version: '2.0', generator: 'kufriky_cloud generator (vlastní)', extras: meta }, scene: 0, scenes: [{ nodes: [0] }], nodes: [], meshes: [], materials: [], accessors: [], bufferViews: [], buffers: [] };
  const matIndex = {};
  const getMat = (name) => {
    if (matIndex[name] !== undefined) return matIndex[name];
    const m = MATERIALY[name]; if (!m) throw new Error('neznámý materiál ' + name);
    const mat = { name, pbrMetallicRoughness: { baseColorFactor: [...m.color, m.alpha ?? 1], metallicFactor: m.metallic, roughnessFactor: m.roughness }, doubleSided: false };
    if (m.alpha !== undefined && m.alpha < 1) { mat.alphaMode = 'BLEND'; mat.doubleSided = true; }
    gltf.materials.push(mat); return (matIndex[name] = gltf.materials.length - 1);
  };
  const chunks = []; let off = 0;
  const addBuf = (typed, target) => {
    const bytes = Buffer.from(typed.buffer, typed.byteOffset, typed.byteLength);
    const start = align4(off); if (start > off) chunks.push(Buffer.alloc(start - off)); chunks.push(bytes); off = start + bytes.length;
    gltf.bufferViews.push({ buffer: 0, byteOffset: start, byteLength: bytes.length, target });
    return gltf.bufferViews.length - 1;
  };
  let triTotal = 0, partTotal = 0;
  const emit = (g, parentPivot) => {
    const rel = [g.pivot[0] - parentPivot[0], g.pivot[1] - parentPivot[1], g.pivot[2] - parentPivot[2]];
    const node = { name: g.name, translation: rel, extras: { ...g.extras } };
    const my = gltf.nodes.length; gltf.nodes.push(node);
    const kids = [];
    for (const part of g.parts) {
      const f = finalizePart(part.clone());
      if (!f.idx.length) continue;
      // poloha vůči pivotu skupiny
      for (let i = 0; i < f.pos.length; i += 3) { f.pos[i] -= g.pivot[0]; f.pos[i + 1] -= g.pivot[1]; f.pos[i + 2] -= g.pivot[2]; }
      let mn = [Infinity, Infinity, Infinity], mx = [-Infinity, -Infinity, -Infinity];
      for (let i = 0; i < f.pos.length; i += 3) for (let k = 0; k < 3; k++) { mn[k] = Math.min(mn[k], f.pos[i + k]); mx[k] = Math.max(mx[k], f.pos[i + k]); }
      const bvP = addBuf(f.pos, 34962), bvN = addBuf(f.nor, 34962), bvI = addBuf(f.idx, 34963);
      gltf.accessors.push({ bufferView: bvP, componentType: 5126, count: f.pos.length / 3, type: 'VEC3', min: mn, max: mx }); const aP = gltf.accessors.length - 1;
      gltf.accessors.push({ bufferView: bvN, componentType: 5126, count: f.nor.length / 3, type: 'VEC3' }); const aN = gltf.accessors.length - 1;
      gltf.accessors.push({ bufferView: bvI, componentType: 5125, count: f.idx.length, type: 'SCALAR' }); const aI = gltf.accessors.length - 1;
      gltf.meshes.push({ name: part.name, primitives: [{ attributes: { POSITION: aP, NORMAL: aN }, indices: aI, material: getMat(part.mat) }] });
      gltf.nodes.push({ name: part.name, mesh: gltf.meshes.length - 1 }); kids.push(gltf.nodes.length - 1);
      triTotal += f.idx.length / 3; partTotal++;
    }
    for (const c of g.children) kids.push(emit(c, g.pivot));
    if (kids.length) node.children = kids;
    return my;
  };
  emit(root, [0, 0, 0]);
  const bin = Buffer.concat(chunks); const binPad = Buffer.alloc(align4(bin.length) - bin.length);
  gltf.buffers.push({ byteLength: bin.length + binPad.length });
  let json = Buffer.from(JSON.stringify(gltf), 'utf8'); const jpad = Buffer.alloc(align4(json.length) - json.length, 0x20); json = Buffer.concat([json, jpad]);
  const total = 12 + 8 + json.length + 8 + bin.length + binPad.length;
  const head = Buffer.alloc(12); head.writeUInt32LE(0x46546C67, 0); head.writeUInt32LE(2, 4); head.writeUInt32LE(total, 8);
  const jh = Buffer.alloc(8); jh.writeUInt32LE(json.length, 0); jh.writeUInt32LE(0x4E4F534A, 4);
  const bh = Buffer.alloc(8); bh.writeUInt32LE(bin.length + binPad.length, 0); bh.writeUInt32LE(0x004E4942, 4);
  fs.writeFileSync(file, Buffer.concat([head, jh, json, bh, bin, binPad]));
  return { bytes: total, triangles: triTotal, parts: partTotal };
}

// Čtečka GLB pro kontroly (nezávislá na generátoru): vrací seznam {name, mat, pos(world), idx}
export function readGLB(file) {
  const b = fs.readFileSync(file);
  if (b.readUInt32LE(0) !== 0x46546C67) throw new Error('není GLB');
  const jl = b.readUInt32LE(12); const gltf = JSON.parse(b.slice(20, 20 + jl).toString('utf8'));
  const bo = 20 + jl + 8; const bin = b.slice(bo);
  const acc = (i) => { const a = gltf.accessors[i], bv = gltf.bufferViews[a.bufferView]; const o = (bv.byteOffset || 0) + (a.byteOffset || 0); const n = { SCALAR: 1, VEC3: 3 }[a.type]; const T = a.componentType === 5126 ? Float32Array : Uint32Array; const buf = bin.buffer.slice(bin.byteOffset + o, bin.byteOffset + o + a.count * n * 4); return new T(buf); };
  const out = [];
  const walk = (ni, parent) => {
    const n = gltf.nodes[ni]; const t = n.translation || [0, 0, 0]; const w = [parent[0] + t[0], parent[1] + t[1], parent[2] + t[2]];
    if (n.mesh !== undefined) { const prim = gltf.meshes[n.mesh].primitives[0]; const pos = acc(prim.attributes.POSITION); const p = new Float32Array(pos.length); for (let i = 0; i < pos.length; i += 3) { p[i] = pos[i] + w[0]; p[i + 1] = pos[i + 1] + w[1]; p[i + 2] = pos[i + 2] + w[2]; } out.push({ name: n.name, mat: gltf.materials[prim.material].name, pos: p, idx: acc(prim.indices), node: ni }); }
    for (const c of n.children || []) walk(c, w);
  };
  for (const s of gltf.scenes[gltf.scene].nodes) walk(s, [0, 0, 0]);
  return { gltf, parts: out };
}
