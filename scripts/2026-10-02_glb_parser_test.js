// Test cteni GLB pro kolizni sweep (parseGlbMesh + pojistka v mesh_kolize_lib) - bot8, 2026-10-02.
// Nalez bot3/bot5: konfigurator-kolize-uhelniky.service padal 146x za sebou na
// product_3219.glb ("3 mesh / 3 primitivu - parseGlbMesh cte jen prvni"). parseGlbMesh uz od 2026-09-18
// cte vsechny meshe (kazdy 1. primitivum), jenze pojistka zkontrolujJedinyPrimitiv() v knihovne odmitala
// kazdy soubor s vice nez 1 meshem -> cely sweep (21 ruznych dilu ve 530 sestavach) se nepocital.
// Oprava: parser cte i VSECHNA primitiva meshe, indexy po bytech, proloženy bufferView, smes indexovanych a
// neindexovanych primitiv; pojistka odmita jen to, co parser neumi (transformace uzlu).
//
// Test: (1) syntetické GLB (kazdy vzor zvlast), (2) skutecny product_3219 vc. presne cesty sweepu
// (dilVeSvete), (3) pokryti geometrie na vsech top-level GLB katalogu (bbox z pozic == sjednoceni
// accessor.min/max).
// Spusteni: node scripts/2026-10-02_glb_parser_test.js   (kandidat: GLB_LIB_DIR=/cesta/ke/slozce s oběma .js)
const fs = require("fs"), os = require("os"), path = require("path"), assert = require("assert");
const LIB = process.env.GLB_LIB_DIR || __dirname;
const G = require(path.join(LIB, "2026-08-19_glb_real_geometry.js"));
const M = require(path.join(LIB, "2026-09-11_mesh_kolize_lib.js"));
const KAT = "/opt/konfigurator/webapp/katalog/";
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "glbtest-"));
process.on("exit", () => { try { fs.rmSync(tmp, { recursive: true, force: true }); } catch (e) { /* uklid */ } });

// --- stavitel GLB -------------------------------------------------------------------------------
function buildGlb(spec) {
  const chunks = [], views = [], accessors = [];
  let len = 0;
  const addBuf = (b, stride) => {
    const pad = (4 - (len % 4)) % 4; if (pad) { chunks.push(Buffer.alloc(pad)); len += pad; }
    views.push(Object.assign({ buffer: 0, byteOffset: len, byteLength: b.length }, stride ? { byteStride: stride } : {}));
    chunks.push(b); len += b.length; return views.length - 1;
  };
  const meshes = spec.meshes.map(m => ({
    primitives: m.primitives.map(pr => {
      const n = pr.positions.length / 3;
      let buf, stride = 0;
      if (pr.stride) {   // proloženo: kazdy vrchol = pr.stride bajtu, pozice na zacatku, zbytek vypln
        stride = pr.stride; buf = Buffer.alloc(n * stride, 0x7f);
        for (let i = 0; i < n; i++) for (let k = 0; k < 3; k++) buf.writeFloatLE(pr.positions[i * 3 + k], i * stride + k * 4);
      } else { buf = Buffer.alloc(n * 12); pr.positions.forEach((v, i) => buf.writeFloatLE(v, i * 4)); }
      const bv = addBuf(buf, stride);
      const mn = [Infinity, Infinity, Infinity], mx = [-Infinity, -Infinity, -Infinity];
      for (let i = 0; i < n; i++) for (let k = 0; k < 3; k++) { mn[k] = Math.min(mn[k], pr.positions[i * 3 + k]); mx[k] = Math.max(mx[k], pr.positions[i * 3 + k]); }
      accessors.push(Object.assign({ bufferView: bv, componentType: 5126, count: n, type: "VEC3", min: mn, max: mx }, pr.sparse ? { sparse: {} } : {}));
      const prim = { attributes: { POSITION: accessors.length - 1 } };
      if (pr.mode != null) prim.mode = pr.mode;
      if (pr.noPosition) delete prim.attributes.POSITION;
      if (pr.indices) {
        const size = pr.indexType === "u8" ? 1 : pr.indexType === "u32" ? 4 : 2;
        const ib = Buffer.alloc(pr.indices.length * size);
        pr.indices.forEach((v, i) => size === 1 ? ib.writeUInt8(v, i) : size === 2 ? ib.writeUInt16LE(v, i * 2) : ib.writeUInt32LE(v, i * 4));
        accessors.push({ bufferView: addBuf(ib), componentType: size === 1 ? 5121 : size === 2 ? 5123 : 5125, count: pr.indices.length, type: "SCALAR" });
        prim.indices = accessors.length - 1;
      }
      return prim;
    }),
  }));
  const json = { asset: { version: "2.0" }, meshes, accessors, bufferViews: views, buffers: [{ byteLength: len }],
                 nodes: spec.nodes || meshes.map((_, i) => ({ mesh: i })), scenes: [{ nodes: (spec.nodes || meshes).map((_, i) => i) }], scene: 0 };
  let js = Buffer.from(JSON.stringify(json)); js = Buffer.concat([js, Buffer.alloc((4 - (js.length % 4)) % 4, 0x20)]);
  let bin = Buffer.concat(chunks); bin = Buffer.concat([bin, Buffer.alloc((4 - (bin.length % 4)) % 4)]);
  const head = Buffer.alloc(12); head.writeUInt32LE(0x46546c67, 0); head.writeUInt32LE(2, 4); head.writeUInt32LE(12 + 8 + js.length + 8 + bin.length, 8);
  const ch = (type, b) => { const h = Buffer.alloc(8); h.writeUInt32LE(b.length, 0); h.writeUInt32LE(type, 4); return Buffer.concat([h, b]); };
  return Buffer.concat([head, ch(0x4e4f534a, js), ch(0x004e4942, bin)]);
}
let counter = 0;
const write = (spec) => { const f = path.join(tmp, `t${++counter}.glb`); fs.writeFileSync(f, buildGlb(spec)); return f; };
const tri = (o) => [o, 0, 0, o + 1, 0, 0, o, 1, 0];          // jeden trojuhelnik posunuty v X
const arr = (x) => Array.from(x);

let passed = 0;
function test(name, fn) { try { fn(); passed++; console.log("  ok  -", name); } catch (e) { console.log("FAIL  -", name, "\n       ", e.message); process.exitCode = 1; } }

// --- 1) syntetické GLB ---------------------------------------------------------------------------------
test("S1 1 mesh / 1 primitivum indexovane (u16): beze zmeny proti drivejsku", () => {
  const g = G.parseGlbMesh(write({ meshes: [{ primitives: [{ positions: tri(0), indices: [0, 1, 2] }] }] })).geometry;
  assert.deepStrictEqual(arr(g.attributes.position.array), tri(0));
  assert.deepStrictEqual(arr(g.index.array), [0, 1, 2]);
});
test("S2 3 meshe po 1 primitivu (vzor product_3219): vsechny pozice, indexy posunute", () => {
  const f = write({ meshes: [0, 1, 2].map(o => ({ primitives: [{ positions: tri(o * 10), indices: [0, 1, 2] }] })) });
  const g = G.parseGlbMesh(f).geometry;
  assert.strictEqual(g.attributes.position.count, 9);
  assert.deepStrictEqual(arr(g.index.array), [0, 1, 2, 3, 4, 5, 6, 7, 8]);
  assert.strictEqual(g.attributes.position.array[18], 20, "3. mesh musi byt v pozicich");
});
test("S3 1 mesh se 3 primitivy: ctou se VSECHNA (driv jen prvni)", () => {
  const f = write({ meshes: [{ primitives: [0, 1, 2].map(o => ({ positions: tri(o * 10), indices: [0, 1, 2] })) }] });
  const g = G.parseGlbMesh(f).geometry;
  assert.strictEqual(g.attributes.position.count, 9, "chybi primitiva");
  assert.deepStrictEqual(arr(g.index.array), [0, 1, 2, 3, 4, 5, 6, 7, 8]);
});
test("S4 smes indexovaneho a neindexovaneho primitiva: neindexovane dostane sekvencni indexy s posunem", () => {
  const f = write({ meshes: [{ primitives: [{ positions: tri(0), indices: [0, 2, 1] }, { positions: tri(10) }] }] });
  const g = G.parseGlbMesh(f).geometry;
  assert.deepStrictEqual(arr(g.index.array), [0, 2, 1, 3, 4, 5]);
});
test("S5 jen neindexovane primitivum: bez index atributu (jako driv)", () => {
  const g = G.parseGlbMesh(write({ meshes: [{ primitives: [{ positions: tri(0) }] }] })).geometry;
  assert.strictEqual(g.index, null);
  assert.strictEqual(g.attributes.position.count, 3);
});
test("S6 indexy UNSIGNED_BYTE a UNSIGNED_INT", () => {
  const a = G.parseGlbMesh(write({ meshes: [{ primitives: [{ positions: tri(0), indices: [0, 1, 2], indexType: "u8" }] }] })).geometry;
  const b = G.parseGlbMesh(write({ meshes: [{ primitives: [{ positions: tri(0), indices: [2, 1, 0], indexType: "u32" }] }] })).geometry;
  assert.deepStrictEqual(arr(a.index.array), [0, 1, 2]);
  assert.deepStrictEqual(arr(b.index.array), [2, 1, 0]);
});
test("S7 proloženy bufferView (byteStride 24): pozice se ctou spravne", () => {
  const g = G.parseGlbMesh(write({ meshes: [{ primitives: [{ positions: tri(5), indices: [0, 1, 2], stride: 24 }] }] })).geometry;
  assert.deepStrictEqual(arr(g.attributes.position.array), tri(5));
});
test("S8 co parser neumi, vyhodi chybu: mod != TRIANGLES, sparse, chybi POSITION", () => {
  assert.throws(() => G.parseGlbMesh(write({ meshes: [{ primitives: [{ positions: tri(0), mode: 1 }] }] })), /modu 1/);
  assert.throws(() => G.parseGlbMesh(write({ meshes: [{ primitives: [{ positions: tri(0), sparse: true }] }] })), /neumim cist/);
  assert.throws(() => G.parseGlbMesh(write({ meshes: [{ primitives: [{ positions: tri(0), noPosition: true }] }] })), /bez POSITION/);
});
test("S9 glbRizikaParseru: identita [] / transformace uzlu = riziko", () => {
  const ok = write({ meshes: [{ primitives: [{ positions: tri(0) }] }], nodes: [{ mesh: 0, translation: [0, 0, 0], rotation: [0, 0, 0, 1], scale: [1, 1, 1] }] });
  assert.deepStrictEqual(G.glbRizikaParseru(ok), []);
  const t = write({ meshes: [{ primitives: [{ positions: tri(0) }] }], nodes: [{ mesh: 0, translation: [0, 300, 0] }] });
  assert.ok(G.glbRizikaParseru(t).length === 1 && /transformaci/.test(G.glbRizikaParseru(t)[0]));
  const m = write({ meshes: [{ primitives: [{ positions: tri(0) }] }], nodes: [{ mesh: 0, matrix: [1000, 0, 0, 0, 0, 1000, 0, 0, 0, 0, 1000, 0, 0, 0, 0, 1] }] });
  assert.strictEqual(G.glbRizikaParseru(m).length, 1);
});
test("S10 pojistka sweepu: vicemeshovy soubor PRIJME, soubor s transformaci uzlu ODMITNE (nemeri se napul)", () => {
  const multi = write({ meshes: [0, 1, 2].map(o => ({ primitives: [{ positions: tri(o * 10), indices: [0, 1, 2] }] })) });
  M.zkontrolujPokrytiParseru(multi);
  const t = write({ meshes: [{ primitives: [{ positions: tri(0) }] }], nodes: [{ mesh: 0, translation: [0, 300, 0] }] });
  assert.throws(() => M.zkontrolujPokrytiParseru(t), /nezmeril celou geometrii/);
  assert.strictEqual(typeof M.zkontrolujJedinyPrimitiv, "function", "stary nazev musi zustat");
});

// --- 2) skutecny product_3219 ------------------------------------------------------------------------------
function glbJson(file) {
  const b = fs.readFileSync(file); let off = 12, js = null;
  while (off < b.length) { const l = b.readUInt32LE(off), t = b.readUInt32LE(off + 4); if (t === 0x4e4f534a) js = JSON.parse(b.slice(off + 8, off + 8 + l).toString("utf8")); off += 8 + l; }
  return js;
}
test("R1 product_3219 (3 meshe): pokryti 100 % - trojuhelniky i bbox == soucet accessoru; sweep cesta dilVeSvete nehodi", () => {
  const f = KAT + "product_3219.glb";
  if (!fs.existsSync(f)) { console.log("       (product_3219.glb chybi - preskoceno)"); return; }
  const js = glbJson(f);
  const prims = js.meshes.flatMap(m => m.primitives);
  assert.ok(prims.length >= 2, "test ma smysl jen pro vicemeshovy soubor");
  const expTri = prims.reduce((s, p) => s + js.accessors[p.indices].count / 3, 0);
  const g = G.parseGlbMesh(f).geometry;
  assert.strictEqual(g.index.count / 3, expTri, "pocet trojuhelniku");
  const mn = [Infinity, Infinity, Infinity], mx = [-Infinity, -Infinity, -Infinity];
  prims.forEach(p => { const a = js.accessors[p.attributes.POSITION]; for (let k = 0; k < 3; k++) { mn[k] = Math.min(mn[k], a.min[k]); mx[k] = Math.max(mx[k], a.max[k]); } });
  g.computeBoundingBox();
  [...g.boundingBox.min.toArray(), ...g.boundingBox.max.toArray()].forEach((v, i) => assert.ok(Math.abs(v - [...mn, ...mx][i]) < 1e-3, "bbox " + i));
  // PRESNA cesta sweepu (mesh_kolize_lib.dilVeSvete -> lokalniTrojuhelniky -> pojistka -> parseGlbMesh)
  const d = M.dilVeSvete(f, { position: [10, 20, 30], quaternion: [0, 0, 0, 1], scale: [1, 1, 1] }, G.parseGlbMesh);
  assert.ok(d, "dilVeSvete musi vratit dil");
});

// --- 3) pokryti na top-level katalogu --------------------------------------------------------------------------
test("K1 vsechny top-level GLB katalogu bez transformace uzlu: parser pokryva 100 % geometrie (bbox == soucet accessoru)", () => {
  let checked = 0, skippedTransf = 0, multi = 0;
  const bad = [];
  for (const fn of fs.readdirSync(KAT).filter(x => x.endsWith(".glb"))) {
    const f = KAT + fn;
    let js; try { js = glbJson(f); } catch (e) { continue; }
    if (!js || !js.meshes) continue;
    if (G.glbRizikaParseru(f).length) { skippedTransf++; continue; }
    const prims = js.meshes.flatMap(m => m.primitives || []);
    if (prims.some(p => (p.mode != null && p.mode !== 4) || !p.attributes || p.attributes.POSITION == null)) continue;
    let g; try { g = G.parseGlbMesh(f).geometry; } catch (e) { bad.push(fn + ": " + e.message.split(": ").pop()); continue; }
    const mn = [Infinity, Infinity, Infinity], mx = [-Infinity, -Infinity, -Infinity];
    prims.forEach(p => { const a = js.accessors[p.attributes.POSITION]; for (let k = 0; k < 3; k++) { mn[k] = Math.min(mn[k], a.min[k]); mx[k] = Math.max(mx[k], a.max[k]); } });
    g.computeBoundingBox();
    const got = [...g.boundingBox.min.toArray(), ...g.boundingBox.max.toArray()], want = [...mn, ...mx];
    if (got.some((v, i) => Math.abs(v - want[i]) > 1e-2)) bad.push(fn + ": bbox neodpovida accessorum");
    const expVerts = prims.reduce((s, p) => s + js.accessors[p.attributes.POSITION].count, 0);
    if (g.attributes.position.count !== expVerts) bad.push(fn + ": pocet vrcholu");
    if (js.meshes.length > 1 || prims.length > 1) multi++;
    checked++;
  }
  console.log(`       zkontrolovano ${checked} souboru (z nich ${multi} vicemeshovych / vicepinitivovych), preskoceno ${skippedTransf} s transformaci uzlu`);
  assert.deepStrictEqual(bad.slice(0, 5), [], `${bad.length} souboru s neuplnym pokrytim`);
  assert.ok(checked > 100, "kontrola fakticky nebezela");
});

console.log(passed + " testu proslo" + (process.exitCode ? " - NEKTERE SELHALY" : ""));
