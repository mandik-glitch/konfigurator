// Převod 16bitových indexů v GLB na 32bitové (jen kopie do scratchpadu pro naše renderery; originál se nemění).
// node u16_na_u32.mjs vstup.glb vystup.glb
import fs from 'node:fs';
const [inp, out] = process.argv.slice(2);
const b = fs.readFileSync(inp); const jl = b.readUInt32LE(12);
const gltf = JSON.parse(b.slice(20, 20 + jl).toString('utf8')); const bin = b.slice(20 + jl + 8);
const chunks = []; let off = 0;
const bvNew = gltf.bufferViews.map(() => null);
const idxViews = new Set(gltf.accessors.filter(a => a.componentType === 5123).map(a => a.bufferView));
gltf.bufferViews.forEach((bv, i) => {
  const o = bv.byteOffset || 0; let data = bin.slice(o, o + bv.byteLength);
  if (idxViews.has(i)) { const u = new Uint32Array(data.length / 2); for (let k = 0; k < u.length; k++) u[k] = data.readUInt16LE(2 * k); data = Buffer.from(u.buffer); }
  const start = (off + 3) & ~3; if (start > off) chunks.push(Buffer.alloc(start - off)); chunks.push(data);
  bvNew[i] = { ...bv, byteOffset: start, byteLength: data.length }; off = start + data.length;
});
gltf.bufferViews = bvNew; for (const a of gltf.accessors) if (a.componentType === 5123) a.componentType = 5125;
const nb = Buffer.concat(chunks); const pad = Buffer.alloc(((nb.length + 3) & ~3) - nb.length); gltf.buffers = [{ byteLength: nb.length + pad.length }];
let js = Buffer.from(JSON.stringify(gltf)); js = Buffer.concat([js, Buffer.alloc(((js.length + 3) & ~3) - js.length, 0x20)]);
const tot = 12 + 8 + js.length + 8 + nb.length + pad.length;
const h = Buffer.alloc(12); h.writeUInt32LE(0x46546C67, 0); h.writeUInt32LE(2, 4); h.writeUInt32LE(tot, 8);
const jh = Buffer.alloc(8); jh.writeUInt32LE(js.length, 0); jh.writeUInt32LE(0x4E4F534A, 4);
const bh = Buffer.alloc(8); bh.writeUInt32LE(nb.length + pad.length, 0); bh.writeUInt32LE(0x004E4942, 4);
fs.writeFileSync(out, Buffer.concat([h, jh, js, bh, nb, pad]));
