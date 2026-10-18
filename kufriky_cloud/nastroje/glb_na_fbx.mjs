// Převod našeho GLB (hierarchie uzlů s posunem + sítě s materiály) na binární FBX 7.4 (mm, Z nahoru). Bez závislostí.
// node nastroje/glb_na_fbx.mjs vstup.glb vystup.fbx
// Zachovává hierarchii uzlů (pivoty = posun uzlu), názvy a barvy materiálů; animace/osy pohybu se neexportují.
import fs from 'node:fs';

// ---------- čtení GLB ----------
function readGLB(file) {
  const b = fs.readFileSync(file);
  if (b.readUInt32LE(0) !== 0x46546C67) throw new Error('není GLB');
  const jl = b.readUInt32LE(12); const gltf = JSON.parse(b.slice(20, 20 + jl).toString('utf8'));
  const bo = 20 + jl + 8; const bin = b.slice(bo);
  const acc = (i) => {
    const a = gltf.accessors[i], bv = gltf.bufferViews[a.bufferView]; const o = (bv.byteOffset || 0) + (a.byteOffset || 0);
    const n = { SCALAR: 1, VEC3: 3 }[a.type]; const ab = bin.buffer.slice(bin.byteOffset + o, bin.byteOffset + o + a.count * n * (a.componentType === 5123 ? 2 : 4));
    return a.componentType === 5126 ? new Float32Array(ab) : a.componentType === 5123 ? new Uint16Array(ab) : new Uint32Array(ab);
  };
  return { gltf, acc };
}

// ---------- zápis binárního FBX ----------
const VERSION = 7400;
class N { constructor(name, props = [], children = []) { this.name = name; this.props = props; this.children = children; } }
const I = (v) => ({ t: 'I', v }); const L = (v) => ({ t: 'L', v: BigInt(v) }); const D = (v) => ({ t: 'D', v }); const S = (v) => ({ t: 'S', v });
const AD = (v) => ({ t: 'd', v }); const AI = (v) => ({ t: 'i', v });
function encProp(p) {
  switch (p.t) {
    case 'I': { const b = Buffer.alloc(5); b.write('I', 0); b.writeInt32LE(p.v, 1); return b; }
    case 'L': { const b = Buffer.alloc(9); b.write('L', 0); b.writeBigInt64LE(p.v, 1); return b; }
    case 'D': { const b = Buffer.alloc(9); b.write('D', 0); b.writeDoubleLE(p.v, 1); return b; }
    case 'S': { const s = Buffer.from(p.v, 'utf8'); const b = Buffer.alloc(5 + s.length); b.write('S', 0); b.writeUInt32LE(s.length, 1); s.copy(b, 5); return b; }
    case 'd': { const n = p.v.length; const b = Buffer.alloc(13 + n * 8); b.write('d', 0); b.writeUInt32LE(n, 1); b.writeUInt32LE(0, 5); b.writeUInt32LE(n * 8, 9); for (let i = 0; i < n; i++) b.writeDoubleLE(p.v[i], 13 + i * 8); return b; }
    case 'i': { const n = p.v.length; const b = Buffer.alloc(13 + n * 4); b.write('i', 0); b.writeUInt32LE(n, 1); b.writeUInt32LE(0, 5); b.writeUInt32LE(n * 4, 9); for (let i = 0; i < n; i++) b.writeInt32LE(p.v[i], 13 + i * 4); return b; }
    default: throw new Error('typ ' + p.t);
  }
}
function encNode(node, base) {
  const props = Buffer.concat(node.props.map(encProp));
  const nm = Buffer.from(node.name, 'utf8');
  const headLen = 13 + nm.length;
  let kids = Buffer.alloc(0);
  if (node.children.length) {
    const parts = []; let off = base + headLen + props.length;
    for (const c of node.children) { const eb = encNode(c, off); parts.push(eb); off += eb.length; }
    parts.push(Buffer.alloc(13)); kids = Buffer.concat(parts);
  }
  const end = base + headLen + props.length + kids.length;
  const head = Buffer.alloc(headLen); head.writeUInt32LE(end, 0); head.writeUInt32LE(node.props.length, 4); head.writeUInt32LE(props.length, 8); head.writeUInt8(nm.length, 12); nm.copy(head, 13);
  return Buffer.concat([head, props, kids]);
}
function writeFBX(topNodes, file) {
  const head = Buffer.alloc(27); head.write('Kaydara FBX Binary  \x00', 0, 'latin1'); head.writeUInt8(0x1A, 21); head.writeUInt8(0x00, 22); head.writeUInt32LE(VERSION, 23);
  const parts = [head]; let off = 27;
  for (const n of topNodes) { const b = encNode(n, off); parts.push(b); off += b.length; }
  parts.push(Buffer.alloc(13)); off += 13;
  // patička (hodnoty nejsou při načítání kontrolovány běžnými importéry)
  const id = Buffer.from([0xfa, 0xbe, 0xb0, 0xb1, 0xa4, 0xa4, 0xcd, 0xdc, 0x79, 0xb7, 0x2b, 0xf9, 0xe4, 0xc5, 0x41, 0xa9]);
  const pad = (16 - ((off + id.length + 4) % 16)) % 16;
  const foot = Buffer.concat([id, Buffer.alloc(4 + pad), (() => { const v = Buffer.alloc(4); v.writeUInt32LE(VERSION, 0); return v; })(), Buffer.alloc(120),
    Buffer.from([0xf8, 0x5a, 0x8c, 0x6a, 0xde, 0xf5, 0xd9, 0x7e, 0xec, 0xe9, 0x0c, 0xe3, 0x75, 0x8f, 0x29, 0x0b])]);
  fs.writeFileSync(file, Buffer.concat([...parts, foot]));
}
const P = (name, type, label, flags, ...vals) => new N('P', [S(name), S(type), S(label), S(flags), ...vals]);
const lin2srgb = (c) => c <= 0.0031308 ? 12.92 * c : 1.055 * Math.pow(c, 1 / 2.4) - 0.055;

// ---------- převod ----------
export function glbNaFbx(vstup, vystup) {
  const g = readGLB(vstup); const gl = g.gltf;
  let nextId = 1000; const id = () => nextId++;
  const geoms = [], models = [], mats = [], conns = [];
  const matId = gl.materials.map((m, i) => {
    const mid = id(); const c = m.pbrMetallicRoughness.baseColorFactor; const rough = m.pbrMetallicRoughness.roughnessFactor ?? 0.5; const met = m.pbrMetallicRoughness.metallicFactor ?? 0;
    const col = [lin2srgb(c[0]), lin2srgb(c[1]), lin2srgb(c[2])];
    mats.push(new N('Material', [L(mid), S(`${m.name || 'mat' + i}\x00\x01Material`), S('')], [
      new N('Version', [I(102)]), new N('ShadingModel', [S('phong')]), new N('MultiLayer', [I(0)]),
      new N('Properties70', [], [
        P('DiffuseColor', 'Color', '', 'A', D(col[0]), D(col[1]), D(col[2])),
        P('SpecularColor', 'Color', '', 'A', D(0.25 + 0.5 * met), D(0.25 + 0.5 * met), D(0.25 + 0.5 * met)),
        P('ShininessExponent', 'Number', '', 'A', D(Math.max(2, (1 - rough) * 120))),
        P('Opacity', 'double', 'Number', '', D(c[3] ?? 1)), P('TransparencyFactor', 'Number', '', 'A', D(1 - (c[3] ?? 1))),
      ])]));
    return mid;
  });
  const kor = (ni, parentId) => {
    const n = gl.nodes[ni]; const mid = id(); const t = n.translation || [0, 0, 0];
    const hasMesh = n.mesh !== undefined;
    const props = [P('Lcl Translation', 'Lcl Translation', '', 'A', D(t[0]), D(t[1]), D(t[2]))];
    const nm = (n.name || 'uzel' + ni).replace(/\0/g, '');
    models.push(new N('Model', [L(mid), S(`${nm}\x00\x01Model`), S(hasMesh ? 'Mesh' : 'Null')], [
      new N('Version', [I(232)]), new N('Properties70', [], props), new N('Shading', [I(1)]), new N('Culling', [S('CullingOff')])]));
    conns.push(['OO', mid, parentId]);
    if (hasMesh) {
      const prim = gl.meshes[n.mesh].primitives[0]; const pos = g.acc(prim.attributes.POSITION), nor = g.acc(prim.attributes.NORMAL), idx = g.acc(prim.indices);
      const gid = id(); const poly = new Array(idx.length);
      for (let i = 0; i < idx.length; i += 3) { poly[i] = idx[i]; poly[i + 1] = idx[i + 1]; poly[i + 2] = -idx[i + 2] - 1; }
      geoms.push(new N('Geometry', [L(gid), S(`${nm}\x00\x01Geometry`), S('Mesh')], [
        new N('Properties70', []),
        new N('GeometryVersion', [I(124)]),
        new N('Vertices', [AD(Array.from(pos))]),
        new N('PolygonVertexIndex', [AI(poly)]),
        new N('LayerElementNormal', [I(0)], [new N('Version', [I(101)]), new N('Name', [S('')]), new N('MappingInformationType', [S('ByVertice')]), new N('ReferenceInformationType', [S('Direct')]), new N('Normals', [AD(Array.from(nor))])]),
        new N('LayerElementMaterial', [I(0)], [new N('Version', [I(101)]), new N('Name', [S('')]), new N('MappingInformationType', [S('AllSame')]), new N('ReferenceInformationType', [S('IndexToDirect')]), new N('Materials', [AI([0])])]),
        new N('Layer', [I(0)], [new N('Version', [I(100)]), new N('LayerElement', [], [new N('Type', [S('LayerElementNormal')]), new N('TypedIndex', [I(0)])]), new N('LayerElement', [], [new N('Type', [S('LayerElementMaterial')]), new N('TypedIndex', [I(0)])])]),
      ]));
      conns.push(['OO', gid, mid]); conns.push(['OO', matId[prim.material], mid]);
    }
    for (const c of n.children || []) kor(c, mid);
  };
  for (const s of gl.scenes[gl.scene].nodes) kor(s, 0);
  const meta = gl.asset.extras || {};
  const now = new Date();
  const top = [
    new N('FBXHeaderExtension', [], [new N('FBXHeaderVersion', [I(1003)]), new N('FBXVersion', [I(VERSION)]),
      new N('CreationTimeStamp', [], [new N('Version', [I(1000)]), new N('Year', [I(now.getFullYear())]), new N('Month', [I(now.getMonth() + 1)]), new N('Day', [I(now.getDate())]), new N('Hour', [I(now.getHours())]), new N('Minute', [I(now.getMinutes())]), new N('Second', [I(now.getSeconds())]), new N('Millisecond', [I(0)])]),
      new N('Creator', [S('GLB na FBX (vlastní nástroj)')])]),
    new N('GlobalSettings', [], [new N('Version', [I(1000)]), new N('Properties70', [], [
      P('UpAxis', 'int', 'Integer', '', I(2)), P('UpAxisSign', 'int', 'Integer', '', I(1)), P('FrontAxis', 'int', 'Integer', '', I(1)), P('FrontAxisSign', 'int', 'Integer', '', I(-1)),
      P('CoordAxis', 'int', 'Integer', '', I(0)), P('CoordAxisSign', 'int', 'Integer', '', I(1)),
      P('UnitScaleFactor', 'double', 'Number', '', D(0.1)), P('OriginalUnitScaleFactor', 'double', 'Number', '', D(0.1))])]),
    new N('Documents', [], [new N('Count', [I(1)]), new N('Document', [L(900000), S('Scene'), S('Scene')], [new N('Properties70', []), new N('RootNode', [L(0)])])]),
    new N('References', []),
    new N('Definitions', [], [new N('Version', [I(100)]), new N('Count', [I(1 + models.length + geoms.length + mats.length)]),
      new N('ObjectType', [S('Model')], [new N('Count', [I(models.length)])]), new N('ObjectType', [S('Geometry')], [new N('Count', [I(geoms.length)])]), new N('ObjectType', [S('Material')], [new N('Count', [I(mats.length)])])]),
    new N('Objects', [], [...geoms, ...models, ...mats]),
    new N('Connections', [], conns.map(([t, a, b]) => new N('C', [S(t), L(a), L(b)]))),
    new N('Takes', [], [new N('Current', [S('')])]),
  ];
  writeFBX(top, vystup);
  return { modelu: models.length, siti: geoms.length, materialu: mats.length, bajtu: fs.statSync(vystup).size, nazev: meta.nazev || '' };
}
if (process.argv[1] && process.argv[1].endsWith('glb_na_fbx.mjs')) {
  const [a, b] = process.argv.slice(2); console.log(JSON.stringify(glbNaFbx(a, b)));
}
