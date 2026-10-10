#!/usr/bin/env node
// Stůl balení LIDL (prototyp II) -> 3D model poskládaný z dílů katalogu.
//
// Vstup:  stul_balici_spec.json (kóty z výkresu jako parametry + členy rámu, desky, příslušenství)
// Výstup: vystup/sestava_parts.json      jednoduchý seznam dílů (part_id, pozice, kvaternion, měřítko, role)
//         vystup/custom_shape_data.json  formát sloupce custom_shapes.data {parts, join_groups, frame_groups}
//         vystup/custom_shape_data_se_zastupnymi.json  totéž + zástupné díly (box 1x1x1 z katalogu, doplní se id karty)
//         vystup/zastupne_dily.json      díly, které nejsou v katalogu (válečky, kování, rameno monitoru...)
//         vystup/kusovnik.json, vystup/kusovnik.md, vystup/koty.json, vystup/validace.txt
//         nahled/stul_balici.html        samostatný 3D náhled (bez sítě, GLB vložené)
//
// Spuštění:  node stul_balici/generuj_sestavu.mjs        (v kořeni repa; vyžaduje `npm install` = three@0.128.0)
// Exit kód:  0 = vše změřeno a čisté, 1 = nalezen problém nebo něco se nedalo změřit (nikdy tiché přeskočení)
//
// Pravidla projektu, která se tu vynucují měřením na REÁLNÉ GLB geometrii (ne syntetickém boxu):
//  - žádné zanoření, žádné částečně kryté čelo (touchReport / isValidFlushTouch + plné krytí čela),
//  - T-styl spoj: připojovaný profil se zkrátí o CELOU šířku průchozího (délka = světlé rozpětí),
//  - noha se zespoda neuzavírá profilem (patka), pivot dílu se MĚŘÍ (Box3), nikdy se neodvozuje z position +- size/2,
//  - "0 nálezů" musí znamenat "změřeno": validace vypisuje rozsah měření a při nule padá.
import { createRequire } from 'node:module';
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);
const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.join(HERE, '..');
const THREE = require('three');
const lib = require(path.join(ROOT, 'scripts/2026-08-18_scene_geometry_lib.js'));
const { parseGlbMesh } = require(path.join(ROOT, 'scripts/2026-08-19_glb_real_geometry.js'));
const MK = require(path.join(ROOT, 'scripts/2026-09-11_mesh_kolize_lib.js'));
const KATALOG = path.join(ROOT, 'webapp/katalog');
const OUT = path.join(HERE, 'vystup');
const NAHRAZKY = path.join(HERE, 'nahrazky');
const SPEC_PATH = path.join(HERE, 'stul_balici_spec.json');
const SQ = Math.SQRT1_2;
const EPS = 0.05;                 // tolerance dotyku (mm), stejná jako v lib.isValidFlushTouch
const r3 = v => Math.round(v * 1000) / 1000;
const r6 = v => Math.round(v * 1e6) / 1e6;
const AX = ['x', 'y', 'z'];
const chyby = [];                 // tvrdé chyby (exit 1)
const varovani = [];
const err = m => { chyby.push(m); };
const warn = m => { varovani.push(m); };

// ---------------------------------------------------------------------------------------------------------------
// 1) spec a parametry
// ---------------------------------------------------------------------------------------------------------------
const specText = fs.readFileSync(SPEC_PATH, 'utf8');
const spec = JSON.parse(specText);
const specHash = crypto.createHash('sha256').update(specText).digest('hex').slice(0, 12);

function vyhodnot(expr, scope) {
  if (typeof expr === 'number') return expr;
  if (typeof expr !== 'string') throw new Error('výraz není číslo ani řetězec: ' + JSON.stringify(expr));
  return new Function(...Object.keys(scope), `"use strict"; return (${expr});`)(...Object.values(scope));
}
const P = {};
for (const [k, v] of Object.entries(spec.param)) {
  P[k] = Array.isArray(v) ? v.map(e => vyhodnot(e, { ...P })) : vyhodnot(v, { ...P });
}
const K = spec.katalog;
const scope = () => ({ ...P, katalog: K });
const ev = e => vyhodnot(e, scope());

// ---------------------------------------------------------------------------------------------------------------
// 2) geometrie dílů katalogu (REÁLNÉ GLB; chybějící GLB = náhradní GLB z nahrazky/, nikdy tiché přeskočení)
// ---------------------------------------------------------------------------------------------------------------
function zapisBoxGlb(file, lo, hi) {
  // minimální platný .glb s jedním kvádrem (12 trojúhelníků, 24 vrcholů) - stejné pořadí os jako reálné GLB (Y nahoru)
  const [x0, y0, z0] = lo, [x1, y1, z1] = hi;
  const pos = [], idx = [], nrm = [];
  const faces = [
    [[1, 0, 0], [[x1, y0, z0], [x1, y1, z0], [x1, y1, z1], [x1, y0, z1]]],
    [[-1, 0, 0], [[x0, y0, z1], [x0, y1, z1], [x0, y1, z0], [x0, y0, z0]]],
    [[0, 1, 0], [[x0, y1, z0], [x0, y1, z1], [x1, y1, z1], [x1, y1, z0]]],
    [[0, -1, 0], [[x0, y0, z1], [x0, y0, z0], [x1, y0, z0], [x1, y0, z1]]],
    [[0, 0, 1], [[x1, y0, z1], [x1, y1, z1], [x0, y1, z1], [x0, y0, z1]]],
    [[0, 0, -1], [[x0, y0, z0], [x0, y1, z0], [x1, y1, z0], [x1, y0, z0]]],
  ];
  faces.forEach(([n, vs], f) => {
    vs.forEach(v => { pos.push(...v); nrm.push(...n); });
    const b = f * 4; idx.push(b, b + 1, b + 2, b, b + 2, b + 3);
  });
  const posBuf = Buffer.from(new Float32Array(pos).buffer), nrmBuf = Buffer.from(new Float32Array(nrm).buffer), idxBuf = Buffer.from(new Uint16Array(idx).buffer);
  const bin = Buffer.concat([posBuf, nrmBuf, idxBuf]);
  const json = {
    asset: { version: '2.0', generator: 'stul_balici/generuj_sestavu.mjs (náhradní GLB)' },
    scene: 0, scenes: [{ nodes: [0] }], nodes: [{ mesh: 0 }],
    meshes: [{ primitives: [{ attributes: { POSITION: 0, NORMAL: 1 }, indices: 2, mode: 4 }] }],
    accessors: [
      { bufferView: 0, componentType: 5126, count: 24, type: 'VEC3', min: [x0, y0, z0], max: [x1, y1, z1] },
      { bufferView: 1, componentType: 5126, count: 24, type: 'VEC3' },
      { bufferView: 2, componentType: 5123, count: 36, type: 'SCALAR' },
    ],
    bufferViews: [{ buffer: 0, byteOffset: 0, byteLength: posBuf.length, target: 34962 }, { buffer: 0, byteOffset: posBuf.length, byteLength: nrmBuf.length, target: 34962 }, { buffer: 0, byteOffset: posBuf.length + nrmBuf.length, byteLength: idxBuf.length, target: 34963 }],
    buffers: [{ byteLength: bin.length }],
  };
  let jb = Buffer.from(JSON.stringify(json)); while (jb.length % 4) jb = Buffer.concat([jb, Buffer.from(' ')]);
  let bb = bin; while (bb.length % 4) bb = Buffer.concat([bb, Buffer.from([0])]);
  const head = Buffer.alloc(12); head.writeUInt32LE(0x46546c67, 0); head.writeUInt32LE(2, 4); head.writeUInt32LE(12 + 8 + jb.length + 8 + bb.length, 8);
  const c1 = Buffer.alloc(8); c1.writeUInt32LE(jb.length, 0); c1.writeUInt32LE(0x4e4f534a, 4);
  const c2 = Buffer.alloc(8); c2.writeUInt32LE(bb.length, 0); c2.writeUInt32LE(0x004e4942, 4);
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, Buffer.concat([head, c1, jb, c2, bb]));
}

const katalogInfo = {};   // klíč katalogu -> {part_id, sku, nazev, glbPath, nahrada(bool), lokalniBox, lokalniStred}
function pripravKatalog() {
  for (const [klic, k] of Object.entries(K)) {
    let glbPath, nahrada = false;
    if (k.glb) {
      glbPath = path.join(KATALOG, k.glb);
      if (!fs.existsSync(glbPath)) throw new Error(`chybí GLB ${k.glb} katalogového dílu ${k.part_id} (${klic}) - nelze měřit`);
      const rizika = require(path.join(ROOT, 'scripts/2026-08-19_glb_real_geometry.js')).glbRizikaParseru(glbPath);
      if (rizika.length) throw new Error(`${k.glb}: parser GLB neumí: ${rizika.join('; ')}`);
    } else if (k.nahrada) {
      nahrada = true;
      glbPath = path.join(HERE, k.nahrada.soubor);
      if (klic === 'led1200') {
        const c = k.stred_obalky_lokalni, d = k.nahrada.rozmer;   // rozměry v lokálních osách GLB: X délka, Y 85, Z 81
        zapisBoxGlb(glbPath, [c[0] - d[0] / 2, c[1] - 85 / 2, c[2] - 81 / 2], [c[0] + d[0] / 2, c[1] + 85 / 2, c[2] + 81 / 2]);
      } else {
        const d = k.nahrada.rozmer;
        zapisBoxGlb(glbPath, [-d[0] / 2, -d[1] / 2, -d[2] / 2], [d[0] / 2, d[1] / 2, d[2] / 2]);
      }
    } else throw new Error(`katalog ${klic}: ani glb, ani nahrada`);
    const obj = parseGlbMesh(glbPath);
    obj.geometry.computeBoundingBox();
    const bb = obj.geometry.boundingBox.clone();
    katalogInfo[klic] = { ...k, klic, glbPath, nahrada, lokalniBox: bb, lokalniStred: bb.getCenter(new THREE.Vector3()) };
  }
  // zástupné díly: jednotkový kvádr z katalogu (webapp/katalog/kvadr_plny_1x1x1.glb) - id karty se musí doplnit z DB
  const kv = path.join(KATALOG, 'kvadr_plny_1x1x1.glb');
  if (!fs.existsSync(kv)) throw new Error('chybí webapp/katalog/kvadr_plny_1x1x1.glb (zástupný kvádr)');
  const o = parseGlbMesh(kv); o.geometry.computeBoundingBox();
  katalogInfo.__kvadr = { part_id: null, sku: null, nazev: 'zástupný kvádr 1x1x1 (karta se doplní z DB)', glbPath: kv, nahrada: false, lokalniBox: o.geometry.boundingBox.clone(), lokalniStred: o.geometry.boundingBox.getCenter(new THREE.Vector3()), klic: '__kvadr' };
}
pripravKatalog();

// ---------------------------------------------------------------------------------------------------------------
// 3) položky sestavy (item) = díl s reálnou geometrií v poloze; Box3 se vždy MĚŘÍ z geometrie
// ---------------------------------------------------------------------------------------------------------------
const items = [];                  // všechny díly sestavy (včetně zástupných) v pořadí vzniku
const byId = new Map();
const v3 = (x, y, z) => new THREE.Vector3(x, y, z);

function novyItem({ id, kat, klic, quat, scale, center, origin, role, extra = {} }) {
  const ki = katalogInfo[klic];
  const q = new THREE.Quaternion(...quat);
  const s = new THREE.Vector3(...scale);
  // `center` = kam přijde STŘED OBÁLKY dílu: pozice = center - R*(s*lokalniStred) (pivot dílu NENÍ jeho střed, SKILL 3d-scena-spoje, pravidlo 4);
  // `origin` = kam přijde lokální počátek GLB (patka: horní střed závitu)
  const lc = ki.lokalniStred.clone().multiply(s).applyQuaternion(q);
  const pos = origin ? origin.clone() : center.clone().sub(lc);
  const obj = parseGlbMesh(ki.glbPath);
  obj.position.copy(pos); obj.quaternion.copy(q); obj.scale.copy(s); obj.updateMatrixWorld(true);
  const it = { id, kat, klic, part_id: ki.part_id, role, object3d: obj, glbPath: ki.glbPath, ...extra };
  it.box = new THREE.Box3().setFromObject(obj);
  if (byId.has(id)) throw new Error('duplicitní id ' + id);
  items.push(it); byId.set(id, it);
  return it;
}
const partSpec = it => ({ position: it.object3d.position.toArray(), quaternion: it.object3d.quaternion.toArray(), scale: it.object3d.scale.toArray() });
function prepocitejBox(it) { it.object3d.updateMatrixWorld(true); it.box = new THREE.Box3().setFromObject(it.object3d); }

// --- profily ---
const QOSA = { y: [0, 0, 0, 1], x: [0, 0, -SQ, SQ], z: [SQ, 0, 0, SQ] };   // lokální osa Y profilu -> světová osa
function postavProfil(def) {
  const prof = P.profil;
  const ki = katalogInfo.profil40;
  const L0 = ki.lokalniBox.max.y - ki.lokalniBox.min.y;   // 1000 (měřeno z GLB)
  let osa = def.osa, rozsah = {};     // rozsah[osa] = [min,max]
  const dalsi = {};
  if (def.mezi) {
    const [a, b] = def.mezi.map(id => { const it = byId.get(id); if (!it) throw new Error(`${def.id}: neznámý profil ${id} v 'mezi'`); return it; });
    const ca = a.box.getCenter(v3(0, 0, 0)), cb = b.box.getCenter(v3(0, 0, 0));
    // osa příčky = jediná osa, ve které jsou oba nosné profily od sebe (mezera > 0); v ostatních se rozsahy překrývají
    const mezery = AX.map(k => Math.max(a.box.min[k] - b.box.max[k], b.box.min[k] - a.box.max[k]));
    const oddelene = AX.filter((k, i) => mezery[i] > EPS);
    if (oddelene.length !== 1) throw new Error(`${def.id}: nosné profily ${a.id}, ${b.id} nejsou odděleny právě v jedné ose (${oddelene.join(',') || 'žádné'})`);
    osa = oddelene[0];
    const [lo, hi] = ca[osa] < cb[osa] ? [a, b] : [b, a];
    rozsah[osa] = [lo.box.max[osa], hi.box.min[osa]];          // T-styl: světlé rozpětí (zkrácení o CELOU šířku průchozího)
    for (const k of AX) if (k !== osa) dalsi[k] = def[k] != null ? ev(def[k]) : a.box.min[k];
    def._rodice = [a.id, b.id];
  } else {
    rozsah[osa] = [ev(def.od), ev(def.do)];
    for (const k of AX) if (k !== osa) dalsi[k] = ev(def[k]);
  }
  const lo = {}, hi = {};
  for (const k of AX) { if (k === osa) { lo[k] = rozsah[k][0]; hi[k] = rozsah[k][1]; } else { lo[k] = dalsi[k]; hi[k] = dalsi[k] + prof; } }
  const L = hi[osa] - lo[osa];
  if (!(L > 0)) throw new Error(`${def.id}: nekladná délka ${L}`);
  const center = v3((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, (lo.z + hi.z) / 2);
  const it = novyItem({ id: def.id, kat: 'profil', klic: 'profil40', quat: QOSA[osa], scale: [1, L / L0, 1], center, role: spec.prefix_roli + def.id, extra: { osa, delka: L, def } });
  // kontrola: změřený Box3 sedí na požadovaný rozsah (pivot/ škálování)
  for (const k of AX) {
    if (Math.abs(it.box.min[k] - lo[k]) > 0.01 || Math.abs(it.box.max[k] - hi[k]) > 0.01) err(`${def.id}: změřený Box3 ${k} [${r3(it.box.min[k])}, ${r3(it.box.max[k])}] != požadovaný [${lo[k]}, ${hi[k]}]`);
  }
  return it;
}
function rozbalProfily() {
  const out = [];
  for (const d of spec.profily) {
    if (d.typ === 'ram') {
      for (const strana of ['zadni', 'predni', 'leva', 'prava']) {
        if (!d[strana]) continue;
        out.push({ id: `${d.id}-${strana}`, mezi: d[strana], y: d.y });
      }
    } else out.push(d);
  }
  return out;
}
const profilDefs = rozbalProfily();
for (const d of profilDefs) postavProfil(d);
const profily = items.filter(i => i.kat === 'profil');

// --- desky (laminovaná deska 1000 x 1000 x 18, vystředěná, tloušťka v lokálním Z; stejně jako pracovní deska generátoru stolu) ---
const Q_DESKA = [-SQ, 0, 0, SQ];
for (const d of spec.desky) {
  const ki = katalogInfo[d.part_id];
  const [x0, x1] = d.x.map(ev), [z0, z1] = d.z.map(ev), yh = ev(d.horni);
  const tl = ki.lokalniBox.max.z - ki.lokalniBox.min.z;   // tloušťka z GLB / náhrady
  if (Math.abs(tl - P.deska) > 1e-6) err(`${d.id}: tloušťka GLB ${tl} != param.deska ${P.deska}`);
  novyItem({ id: d.id, kat: 'deska', klic: d.part_id, quat: Q_DESKA, scale: [(x1 - x0) / 1000, (z1 - z0) / 1000, 1], center: v3((x0 + x1) / 2, yh - tl / 2, (z0 + z1) / 2), role: spec.prefix_roli + d.id, extra: { def: d } });
}
const desky = items.filter(i => i.kat === 'deska');

// --- patky: pod každou svislou nohu s volným spodním čelem ---
{
  const pk = spec.prislusenstvi.patky;
  const zasun = ev(pk.zasun);
  const delkaGlb = -katalogInfo[pk.dil].lokalniBox.min.y;      // 79 (měřeno z GLB), počátek = horní střed závitu
  if (Math.abs(delkaGlb - K[pk.dil].delka) > 1e-6) err(`patka: délka z GLB ${delkaGlb} != katalog.delka ${K[pk.dil].delka}`);
  for (const noha of profily.filter(p => p.osa === 'y' && Math.abs(p.box.min.y - P.zem) < 1e-6)) {
    const c = noha.box.getCenter(v3(0, 0, 0));
    novyItem({ id: 'patka-' + noha.id, kat: 'patka', klic: pk.dil, quat: [0, 0, 0, 1], scale: [1, 1, 1], origin: v3(c.x, noha.box.min.y + zasun, c.z), role: spec.prefix_roli + 'patka-' + noha.id, extra: { noha: noha.id, zasun } });
  }
}
const patky = items.filter(i => i.kat === 'patka');

// --- úhelníky (držáky desek): pod deskou u každé svislé nohy, jejíž líc leží na hraně desky ---
// Geometrie podle api/stul_hpolice.py::_uhelnik: lokálně x = rameno od nohy pod deskou, y = šířka, z = -nahoru; vnější roh v bodě dotyku.
// Zde je rameno POD deskou (deska leží na horním líci ramene) a druhé rameno visí dolů po líci nohy => "nahoru" = -Y.
function matice(en, ez) { // sloupce = obrazy lokálních os x, y, z (ey = ez x en, pravotočivá soustava)
  const ey = new THREE.Vector3().crossVectors(ez, en);
  return new THREE.Matrix4().makeBasis(en, ey, ez);
}
{
  const dk = spec.prislusenstvi.drzaky_desek;
  const ki = katalogInfo[dk.dil];
  const lb = ki.lokalniBox;
  for (const deska of desky.filter(d => d.def.drzaky)) {
    const spodek = deska.box.min.y;
    const kandidati = [];
    for (const noha of profily.filter(p => p.osa === 'y')) {
      const zasahuje = noha.box.min.y < spodek - 37 && noha.box.max.y > spodek - 1e-6;
      const zRozsah = noha.box.min.z >= deska.box.min.z - EPS && noha.box.max.z <= deska.box.max.z + EPS;
      if (!zasahuje || !zRozsah) continue;
      if (Math.abs(noha.box.max.x - deska.box.min.x) < EPS) kandidati.push({ noha, en: v3(1, 0, 0), roviny: noha.box.max.x });
      else if (Math.abs(noha.box.min.x - deska.box.max.x) < EPS) kandidati.push({ noha, en: v3(-1, 0, 0), roviny: noha.box.min.x });
    }
    for (const k of kandidati) {
      const ez = v3(0, 1, 0);                                  // lokální +z = nahoru (rameno visí dolů po lokálním -z... viz níže)
      const R = matice(k.en, ez);
      const q = new THREE.Quaternion().setFromRotationMatrix(R);
      const lokRoh = v3(lb.min.x, (lb.min.y + lb.max.y) / 2, lb.max.z);   // vnější roh uprostřed šířky
      const bod = v3(k.roviny, spodek, (k.noha.box.min.z + k.noha.box.max.z) / 2);
      const origin = bod.clone().sub(lokRoh.clone().applyMatrix4(new THREE.Matrix4().extractRotation(R)));
      novyItem({ id: `drzak-${deska.id}-${k.noha.id}`, kat: 'drzak', klic: dk.dil, quat: q.toArray(), scale: [1, 1, 1], origin, role: spec.prefix_roli + `drzak-${deska.id}-${k.noha.id}`, extra: { deska: deska.id, noha: k.noha.id } });
    }
    if (kandidati.length === 0) err(`deska ${deska.id}: příznak drzaky, ale žádná noha s lícem na hraně desky`);
  }
}
const drzaky = items.filter(i => i.kat === 'drzak');

// --- svítidlo LED (karta product_4929; GLB v checkoutu chybí -> poloha z dokumentované obálky + orientace šablony generátoru) ---
{
  const led = spec.prislusenstvi.led;
  const ki = katalogInfo[led.dil];
  const Rt = new THREE.Matrix4().makeRotationFromQuaternion(new THREE.Quaternion(...K[led.dil].kvaternion_sablony));
  const dirX = v3(1, 0, 0).applyMatrix4(Rt);                       // kam míří lokální délka (X) v šabloně
  // otočení kolem Y, aby délka šla podél světového X
  const Ry = new THREE.Matrix4().makeRotationY(Math.abs(dirX.z) > 0.5 ? (dirX.z > 0 ? -Math.PI / 2 : Math.PI / 2) : 0);
  const Rm = Ry.clone().multiply(Rt);
  const q = new THREE.Quaternion().setFromRotationMatrix(Rm);
  // svislý rozměr po otočení z lokálních rozměrů (Y 85 / Z 81): změř, ne předpokládej
  const sizeLok = ki.lokalniBox.getSize(v3(0, 0, 0));
  const tmp = parseGlbMesh(ki.glbPath); tmp.quaternion.copy(q); tmp.updateMatrixWorld(true);
  const bq = new THREE.Box3().setFromObject(tmp); const sz = bq.getSize(v3(0, 0, 0));
  const nad = byId.get(led.viset_pod);
  const cx = ev(led.x), cz = ev(led.z);
  const cy = nad.box.min.y - sz.y / 2;                              // horní plocha svítidla dosedá na spodek příčky
  novyItem({ id: 'led-1', kat: 'led', klic: led.dil, quat: q.toArray(), scale: [1, 1, 1], center: v3(cx, cy, cz), role: spec.prefix_roli + 'led-1', extra: { rozmerSvet: sz.toArray(), rozmerLok: sizeLok.toArray() } });
}

// --- zástupné díly (nejsou v katalogu): jednotkový kvádr se škálou = rozměry; id karty doplní bot s DB ---
function postavZastupne() {
  for (const z of spec.zastupne) {
    const pocet = z.pocet ? ev(z.pocet) : 1;
    const [x0, x1] = (z.x).map(ev);
    for (let i = 0; i < pocet; i++) {
      let xa = x0, xb = x1;
      if (z.pocet) {
        const mezera = ev(z.mezera_x);
        const sirka = ((x1 - x0) - (pocet - 1) * mezera) / pocet;
        xa = x0 + i * (sirka + mezera); xb = xa + sirka;
      }
      let ya, yb;
      if (z.y_dole != null) { ya = ev(z.y_dole); yb = ya + ev(z.vyska); } else { [ya, yb] = z.y.map(ev); }
      const [za, zb] = z.z.map(ev);
      const id = z.pocet ? `${z.id}-${i + 1}` : z.id;
      novyItem({ id, kat: z.kategorie, klic: '__kvadr', quat: [0, 0, 0, 1], scale: [xb - xa, yb - ya, zb - za], center: v3((xa + xb) / 2, (ya + yb) / 2, (za + zb) / 2), role: spec.prefix_roli + id, extra: { zastupne: true, nazev: z.nazev, poznamka: z.poznamka } });
    }
  }
}
postavZastupne();

// ---------------------------------------------------------------------------------------------------------------
// 4) spoje profilů (z geometrie): T / čelní spoj = čelo jednoho profilu celou plochou na stěně druhého
// ---------------------------------------------------------------------------------------------------------------
function dotyk(a, b) {
  const r = lib.touchReport(a.box, b.box);
  return r;
}
const spoje = [];          // T / čelní spoje (účtují se jako spoj)
const bocniDosedy = [];    // profil přiložený boční stěnou k jiné stěně (posuvný profil na T-matice)
const nepovoleneDotyky = [];
for (let i = 0; i < profily.length; i++) {
  for (let j = i + 1; j < profily.length; j++) {
    const A = profily[i], B = profily[j];
    const r = dotyk(A, B);
    const ploch = AX.filter(k => Math.abs(r[k].overlap) <= EPS);
    const pln = AX.filter(k => r[k].overlap > EPS);
    if (!(ploch.length === 1 && pln.length === 2)) continue;     // žádný plošný dotyk (vzdálené, hranové, nebo zanořené - zanoření řeší kolizní kontrola)
    const a = ploch[0];
    const aEnd = A.osa === a, bEnd = B.osa === a;
    const t = Math.abs(A.box.max[a] - B.box.min[a]) <= EPS ? A.box.max[a] : B.box.max[a];
    if (aEnd !== bEnd) {                                         // T / čelní spoj: dítě = ten, jehož čelo je v rovině dotyku
      const dite = aEnd ? A : B, rodic = aEnd ? B : A;
      const dalsi = AX.filter(k => k !== a);
      const kryje = dalsi.every(k => dite.box.min[k] >= rodic.box.min[k] - EPS && dite.box.max[k] <= rodic.box.max[k] + EPS);
      const stredDite = dite.box.getCenter(v3(0, 0, 0))[a];
      const n = Math.sign(stredDite - t);                        // od stěny rodiče do těla dítěte
      spoje.push({ dite, rodic, osa: a, t, n, kryje, report: r });
    } else if (!aEnd && !bEnd) {
      const dite = A.def.bocni_dosed ? A : (B.def.bocni_dosed ? B : null);
      if (dite) bocniDosedy.push({ dite, rodic: dite === A ? B : A, osa: a, t, n: Math.sign(dite.box.getCenter(v3(0, 0, 0))[a] - t), report: r });
      else nepovoleneDotyky.push([A.id, B.id, a]);
    } else {
      nepovoleneDotyky.push([A.id, B.id, a + ' (čelo na čelo)']);
    }
  }
}
nepovoleneDotyky.forEach(([a, b, k]) => err(`neočekávaný plošný dotyk profilů ${a} x ${b} na ose ${k} (není ani T-spoj, ani označený boční dosed)`));

// ---------------------------------------------------------------------------------------------------------------
// 5) rohové spojky na každý T-spoj (pozice ze šablony generátoru: 20/20 spojek system 40 sedí na tuhle konstrukci)
// ---------------------------------------------------------------------------------------------------------------
// Lokální soustava spojky 3176 (měřeno): x = rameno podél dítěte od stěny rodiče (-3,43 .. 37; 3,43 mm zámek v drážce rodiče), y = -40,43 .. 0
// (3,43 mm zámek v drážce dítěte; stěna dítěte v lokálním y = -37), z = 0 .. 37 (šířka 37 ze 40). Pak R = [n, u, w=n x u]:
// n = od stěny rodiče do těla dítěte, u = strana dítěte, na které spojka sedí, počátek = střed čela dítěte + u*(půlka dítěte + 37) - w*18,5.
const SMERY = { '-y': v3(0, -1, 0), '+z': v3(0, 0, 1), '-z': v3(0, 0, -1), '+x': v3(1, 0, 0), '-x': v3(-1, 0, 0), '+y': v3(0, 1, 0) };
const POR_SMERU = ['-y', '+z', '-z', '+x', '-x', '+y'];
const RAMENO = 37.0;
function osaSmeru(vec) { return AX.find(k => Math.abs(vec[k]) > 0.5); }
const dilCache = new Map();
function dilSvet(it) {
  if (!dilCache.has(it)) dilCache.set(it, MK.dilVeSvete(it.glbPath, partSpec(it), parseGlbMesh));
  return dilCache.get(it);
}
function prekryvBoxuItemu(a, b) { return ['x', 'y', 'z'].map(k => Math.min(a.box.max[k], b.box.max[k]) - Math.max(a.box.min[k], b.box.min[k])); }

function umistiSpojky() {
  const sp = spec.prislusenstvi.spojky;
  const ki = katalogInfo[sp.dil];
  const poradi = spoje.slice().sort((a, b) => (a.dite.id + a.rodic.id).localeCompare(b.dite.id + b.rodic.id));
  let n = 0;
  for (const j of poradi) {
    const a = j.osa;
    const nVec = v3(0, 0, 0); nVec[a] = j.n;
    const stred = j.dite.box.getCenter(v3(0, 0, 0)); stred[a] = j.t;        // střed čela dítěte
    let umisteno = null; const zamitnuto = [];
    for (const klicSmeru of POR_SMERU) {
      const u = SMERY[klicSmeru];
      const ua = osaSmeru(u);
      if (ua === a) continue;                                                // u musí být kolmé na n
      const s = Math.sign(u[ua]);
      // rodič musí mít za povrchem dítěte (ve směru u) aspoň 37 mm materiálu pro zámek spojky; šířka 37 musí ležet v čele rodiče
      const povrchDite = s > 0 ? j.dite.box.max[ua] : j.dite.box.min[ua];
      const dalPovrchRodice = s > 0 ? j.rodic.box.max[ua] : j.rodic.box.min[ua];
      const volno = s * (dalPovrchRodice - povrchDite);
      if (volno < RAMENO - EPS) { zamitnuto.push(`${klicSmeru}: rodič má za dítětem jen ${r3(volno)} mm`); continue; }
      const w = new THREE.Vector3().crossVectors(nVec, u);
      const wa = osaSmeru(w);
      if (stred[wa] - 18.5 < j.rodic.box.min[wa] - EPS || stred[wa] + 18.5 > j.rodic.box.max[wa] + EPS) { zamitnuto.push(`${klicSmeru}: šířka spojky mimo čelo rodiče`); continue; }
      const R = new THREE.Matrix4().makeBasis(nVec, u, w);
      const q = new THREE.Quaternion().setFromRotationMatrix(R);
      const origin = stred.clone().addScaledVector(u, 20 + RAMENO).addScaledVector(w, -18.5);
      // zkušební díl
      const tmp = parseGlbMesh(ki.glbPath); tmp.position.copy(origin); tmp.quaternion.copy(q); tmp.updateMatrixWorld(true);
      const box = new THREE.Box3().setFromObject(tmp);
      const kand = { id: `spojka-${String(n + 1).padStart(2, '0')}-${j.dite.id}-${j.rodic.id}`, box, glbPath: ki.glbPath, object3d: tmp, partSpec: { position: origin.toArray(), quaternion: q.toArray(), scale: [1, 1, 1] } };
      // kolize s ostatními díly (mimo dva partnery spoje): box předfiltr + mesh test
      const D = MK.dilVeSvete(ki.glbPath, kand.partSpec, parseGlbMesh);
      let koliduje = null;
      for (const o of items) {
        if (o === j.dite || o === j.rodic) continue;
        const ov = prekryvBoxuItemu(kand, o);
        if (ov.every(v => v > 0.05)) {
          const res = MK.kolize(D, dilSvet(o));
          if (res.koliduje) { koliduje = `${o.id} (odsun ${res.odsun} mm)`; break; }
        }
      }
      if (koliduje) { zamitnuto.push(`${klicSmeru}: kolize s ${koliduje}`); continue; }
      umisteno = { klicSmeru, origin, q, nVec, u, w, id: kand.id };
      break;
    }
    if (!umisteno) {
      const duvod = (sp.vynechat || {})[j.dite.id];
      if (duvod) { j.bezSpojky = duvod; warn(`spoj ${j.dite.id} -> ${j.rodic.id}: BEZ rohové spojky (${duvod}); zamítnuté strany: ${zamitnuto.join('; ')}`); continue; }
      err(`spoj ${j.dite.id} -> ${j.rodic.id}: žádná strana pro rohovou spojku (${zamitnuto.join('; ')})`); continue;
    }
    n++;
    const it = novyItem({ id: umisteno.id, kat: 'spojka', klic: sp.dil, quat: umisteno.q.toArray(), scale: [1, 1, 1], origin: umisteno.origin, role: spec.prefix_roli + umisteno.id, extra: { dite: j.dite.id, rodic: j.rodic.id, strana: umisteno.klicSmeru, zamitnuto } });
    j.spojka = it;
  }
}
umistiSpojky();
const spojky = items.filter(i => i.kat === 'spojka');


// ---------------------------------------------------------------------------------------------------------------
// 6) účetnictví spojů (stejný model dat jako attachEntryToParent/registerJoint: dítě drží joint_count, used_conn, hidden_end_conn; lic_peers symetricky)
// ---------------------------------------------------------------------------------------------------------------
const entryOf = new Map();   // item -> entry pro lib (object3d, connectorsLocal, part_id, ...)
function entry(it) {
  if (!entryOf.has(it)) {
    const e = { part_id: it.part_id, object3d: it.object3d, item: it };
    if (it.kat === 'profil') {
      // konektory se počítají v identitě (jako v appce: computeConnectorsLocal před aplikací transformace)
      const tmp = parseGlbMesh(it.glbPath);
      e.connectorsLocal = lib.computeConnectorsLocal(tmp);
      e.vertical = it.osa === 'y';
    }
    entryOf.set(it, e);
  }
  return entryOf.get(it);
}
function koncovyKonektor(it, a, t) {      // který konec (0 = +lokální osa, 1 = -lokální osa) profilu leží v rovině t na ose a
  const e = entry(it);
  const wc = lib.worldConnectorsOf(e);
  let best = null;
  [0, 1].forEach(idx => { const d = Math.abs(wc[idx].point[a] - t); if (!best || d < best.d) best = { idx, d }; });
  if (best.d > 0.01) err(`${it.id}: žádný koncový konektor v rovině ${a}=${t} (nejblíž ${r3(best.d)} mm)`);
  return best.idx;
}
function licneKonektor(it, smer) {          // "face" konektor profilu s normálou ve světovém směru `smer`
  const e = entry(it);
  const wc = lib.worldConnectorsOf(e);
  let best = null;
  wc.forEach((c, idx) => { if (c.kind !== 'face') return; const d = c.normal.dot(smer); if (!best || d > best.d) best = { idx, d }; });
  if (!best || best.d < 0.9) err(`${it.id}: nenalezen face konektor ve směru ${smer.toArray()}`);
  return best.idx;
}
for (const j of spoje) {
  const idxDite = koncovyKonektor(j.dite, j.osa, j.t);
  lib.registerJoint(entry(j.rodic), 2, entry(j.dite), idxDite);     // rodič: mid konektor (T), dítě: koncový konektor; joint_count na dítěti
  entry(j.rodic).wasThrough = true;
  entry(j.dite).wasAttached = true;
  j.idxDite = idxDite;
}
for (const b of bocniDosedy) {
  const sm = v3(0, 0, 0); sm[b.osa] = b.n;
  const idxD = licneKonektor(b.dite, sm.clone().negate()), idxR = licneKonektor(b.rodic, sm);
  lib.registerJoint(entry(b.rodic), idxR, entry(b.dite), idxD);
  entry(b.dite).wasAttached = true;
}
for (const p of profily) entry(p);

// ---------------------------------------------------------------------------------------------------------------
// 7) validace (rozsah měření se vypisuje; nulový počet porovnání = chyba)
// ---------------------------------------------------------------------------------------------------------------
const V = [];
const L = (s = '') => V.push(s);
const fmtR = r => AX.map(k => `${k}:g=${r[k].gap.toFixed(3)}/o=${r[k].overlap.toFixed(3)}`).join(' ');
const katPocty = {};
items.forEach(i => { katPocty[i.kat] = (katPocty[i.kat] || 0) + 1; });
const realne = items.filter(i => !i.zastupne);

L('VALIDACE sestavy "' + spec.nazev + '"');
L(`spec sha256[:12] = ${specHash}, three r${THREE.REVISION}, měřeno na REÁLNÉ geometrii GLB (parseGlbMesh), tolerance dotyku ${EPS} mm`);
L('');
L('== 0. ROZSAH MĚŘENÍ ==');
L(`dílů celkem: ${items.length} (katalogových ${realne.length}, zástupných ${items.length - realne.length}); podle kategorií: ${Object.entries(katPocty).map(([k, v]) => `${k} ${v}`).join(', ')}`);
const nPar = items.length * (items.length - 1) / 2;
L(`dvojic dílů porovnáno obálkami (všechny s všemi): ${nPar}`);
L(`profilů ${profily.length} -> dvojic profil x profil: ${profily.length * (profily.length - 1) / 2}`);
if (!(items.length > 0 && profily.length > 0 && nPar > 0)) err('prázdná sestava - nulový počet porovnání');

// --- 7.1 profil x profil: dotyky, T-styl, krytí čela ---
L('');
L('== 1. SPOJE PROFILŮ (čelo celou plochou na stěně jiného profilu; touchReport / isValidFlushTouch) ==');
L(`nalezeno T / čelních spojů: ${spoje.length}; bočních dosedů (posuvný profil na T-matice): ${bocniDosedy.length}; neočekávaných plošných dotyků: ${nepovoleneDotyky.length}`);
let spojuOK = 0;
for (const j of spoje) {
  const rep = lib.touchReport(j.dite, j.rodic);
  const ok1 = lib.isValidFlushTouch(rep, EPS);
  const r2 = AX.filter(k => k !== j.osa);
  // plné krytí čela dítěte: čelo (průřez dítěte) celé uvnitř stěny rodiče
  const pokryti = r2.map(k => Math.min(j.dite.box.max[k], j.rodic.box.max[k]) - Math.max(j.dite.box.min[k], j.rodic.box.min[k]));
  const plne = pokryti.every(v => Math.abs(v - P.profil) < 0.01) && j.kryje;
  j.ok = ok1 && plne;
  if (j.ok) spojuOK++; else err(`spoj ${j.dite.id} -> ${j.rodic.id}: ${fmtR(rep)} krytí ${pokryti.map(r3).join('x')} (čelo ${P.profil}x${P.profil} musí být kryté celé)`);
  L(`  ${j.ok ? 'OK ' : 'CHYBA'} ${j.dite.id.padEnd(14)} -> ${j.rodic.id.padEnd(14)} osa ${j.osa} v ${r3(j.t)}  ${fmtR(rep)}  krytí čela ${pokryti.map(r3).join('x')}  ${j.spojka ? 'spojka ' + j.spojka.strana : 'BEZ spojky'}`);
}
L(`spojů platných: ${spojuOK} / ${spoje.length}`);
for (const b of bocniDosedy) {
  const rep = lib.touchReport(b.dite, b.rodic);
  L(`  boční dosed ${b.dite.id} -> ${b.rodic.id} osa ${b.osa} v ${r3(b.t)}  ${fmtR(rep)}  (T-matice, účtuje se jako spoj)`);
}
// T-styl: délka připojovaného profilu = světlé rozpětí mezi průchozími (měřeno z Box3)
let tstyl = 0;
for (const p of profily.filter(q => q.def._rodice)) {
  const [a, b] = p.def._rodice.map(id => byId.get(id));
  const gap = Math.max(a.box.min[p.osa] - b.box.max[p.osa], b.box.min[p.osa] - a.box.max[p.osa]);
  const lm = p.box.max[p.osa] - p.box.min[p.osa];
  tstyl++;
  if (Math.abs(gap - lm) > 0.01) err(`T-styl: ${p.id} délka ${r3(lm)} != světlé rozpětí ${r3(gap)} mezi ${a.id} a ${b.id}`);
}
L(`T-styl (připojovaný profil = světlé rozpětí, tj. zkrácení o CELOU šířku průchozího): ověřeno u ${tstyl} příček`);
// počet spojů na příčku
for (const p of profily.filter(q => q.def._rodice)) {
  const n = spoje.filter(j => j.dite === p).length;
  if (n !== 2) err(`${p.id}: očekávány 2 spoje (oba konce), nalezeno ${n}`);
}

// --- 7.2 nohy: volné čelo dole (patka), nahoře ---
L('');
L('== 2. NOHY (volné čelo; patka) ==');
let nohyDole = 0;
for (const n of profily.filter(q => q.osa === 'y' && q.id.startsWith('noha-'))) {
  const dole = n.box.min.y;
  const dotykDole = items.filter(o => o !== n && o.kat !== 'patka' && o.box.min.x < n.box.max.x - EPS && o.box.max.x > n.box.min.x + EPS && o.box.min.z < n.box.max.z - EPS && o.box.max.z > n.box.min.z + EPS && o.box.min.y <= dole + EPS && o.box.max.y >= dole - EPS);
  const patka = byId.get('patka-' + n.id);
  const nahore = spoje.filter(j => j.osa === 'y' && j.dite === n).map(j => j.rodic.id);
  const volnyNahore = nahore.length === 0;
  L(`  ${n.id}: spodek y=${r3(dole)} ${dotykDole.length ? 'CHYBA dotyk dole: ' + dotykDole.map(o => o.id).join(',') : 'volný (' + (patka ? 'patka ' + patka.part_id : 'BEZ PATKY') + ')'}; vršek y=${r3(n.box.max.y)} ${volnyNahore ? 'volný' : 'uzavřen horním rámem ' + nahore.join(',')}`);
  if (dotykDole.length) err(`${n.id}: spodní čelo není volné (dotyk: ${dotykDole.map(o => o.id).join(',')})`);
  if (!patka) err(`${n.id}: chybí patka`);
  nohyDole++;
}
if (!nohyDole) err('žádná noha změřena');

// --- 7.3 patky: poloha a zásun závitu (měřeno z vrcholů reálné sítě) ---
L('');
L('== 3. PATKY (product_3283) ==');
for (const pk of patky) {
  const noha = byId.get(pk.noha);
  const c = noha.box.getCenter(v3(0, 0, 0));
  const g = pk.object3d.geometry.attributes.position; pk.object3d.updateMatrixWorld(true);
  let rMax = 0, zasunMin = Infinity, vzorku = 0; const vv = v3(0, 0, 0);
  for (let i = 0; i < g.count; i++) {
    vv.fromBufferAttribute(g, i).applyMatrix4(pk.object3d.matrixWorld);
    if (vv.y > noha.box.min.y + EPS) { vzorku++; rMax = Math.max(rMax, Math.abs(vv.x - c.x), Math.abs(vv.z - c.z)); }
  }
  const spodek = pk.box.min.y;
  const okPoloha = Math.abs(spodek) < 0.01 && Math.abs((pk.box.min.x + pk.box.max.x) / 2 - c.x) < 0.01 && Math.abs((pk.box.min.z + pk.box.max.z) / 2 - c.z) < 0.01;
  const okZasun = rMax <= P.profil / 2 + 0.01 && vzorku > 0;
  L(`  ${pk.id}: základna y=${r3(spodek)} (podlaha 0), zásun ${r3(pk.zasun)} mm (část nad spodkem nohy má poloměr max ${r3(rMax)} mm <= ${P.profil / 2}; vrcholů ${vzorku}) ${okPoloha && okZasun ? 'OK' : 'CHYBA'}`);
  if (!(okPoloha && okZasun)) err(`${pk.id}: patka mimo osu nohy / mimo podlahu / zásun se nevejde do průřezu`);
}

// --- 7.4 kolize: všechny dvojice, obálky + mesh ---
L('');
L('== 4. KOLIZE (všechny dvojice dílů: obálky na 3 osách, pak přesný mesh test) ==');
const ocekavane = new Set();    // dvojice, kde je překryv obálek záměr (zámek spojky v drážce, závit patky v noze)
const klic = (a, b) => (a.id < b.id ? a.id + '|' + b.id : b.id + '|' + a.id);
for (const j of spoje) if (j.spojka) { ocekavane.add(klic(j.spojka, j.dite)); ocekavane.add(klic(j.spojka, j.rodic)); }
for (const pk of patky) ocekavane.add(klic(pk, byId.get(pk.noha)));
const idxItem = new Map(items.map((it, i) => [it, i]));
const definedPairs = new Set([...ocekavane].map(k => { const [a, b] = k.split('|'); return `${idxItem.get(byId.get(a))}-${idxItem.get(byId.get(b))}`; }));
const placed = items.map(i => ({ object3d: i.object3d }));
const boxKolize = lib.fullCollisionCheck(placed, new Set());       // lib: překryv obálek na všech 3 osách (bez výjimek)
const boxMimoOcekavane = boxKolize.filter(c => !definedPairs.has(`${c.i}-${c.j}`) && !definedPairs.has(`${c.j}-${c.i}`));
L(`překryv obálek na všech 3 osách současně (lib.fullCollisionCheck): ${boxKolize.length} dvojic, z toho očekávaných (zámek spojky, závit patky): ${boxKolize.length - boxMimoOcekavane.length}, ostatních: ${boxMimoOcekavane.length}`);
{
  const poKat = {};
  boxMimoOcekavane.forEach(c => { const kk = [items[c.i].kat, items[c.j].kat].sort().join(' x '); poKat[kk] = (poKat[kk] || 0) + 1; });
  L(`  ostatní překryvy obálek podle druhu (rozhoduje mesh test níže): ${Object.entries(poKat).map(([k, v]) => `${k} ${v}`).join(', ') || '-'}`);
}
let meshTestu = 0, meshKolizi = 0, meshNekoliduje = 0;
const kolizeNeoc = [];
for (const c of (process.env.SKIP_MESH ? [] : boxKolize)) {
  const A = items[c.i], B = items[c.j];
  const oc = ocekavane.has(klic(A, B));
  const res = MK.kolize(dilSvet(A), dilSvet(B), undefined, oc);     // u očekávaných dvojic stačí verdikt (hloubka zámku/závitu se měří zvlášť v oddílech 3 a 5)
  meshTestu++;
  if (res.koliduje) { meshKolizi++; if (!oc) { kolizeNeoc.push(`${A.id} x ${B.id}: odsun ${res.odsun} mm, oblast ${res.oblast.join('x')}`); err(`KOLIZE (mesh) ${A.id} x ${B.id}: odsun ${res.odsun} mm, oblast ${res.oblast.join('x')} mm`); } }
  else meshNekoliduje++;
}
L(`přesný mesh test (SAT + objemové vzorkování, scripts/2026-09-11_mesh_kolize_lib.js) na ${meshTestu} dvojicích: kolize ${meshKolizi} (očekávané zámky/závity ${meshKolizi - kolizeNeoc.length}, NEočekávané ${kolizeNeoc.length}), obálky ano / mesh ne ${meshNekoliduje}`);
kolizeNeoc.forEach(k => L('  NEOČEKÁVANÁ KOLIZE ' + k));
if (process.env.SKIP_MESH) err('DEV REŽIM (SKIP_MESH): přesný mesh test kolizí PŘESKOČEN - výsledek neplatí');
// zámek spojky: naměřený přesah obálky spojky se stěnami obou partnerů
L('');
L('== 5. ROHOVÉ SPOJKY (product_3176): zámek v drážce obou profilů ==');
let spojekOK = 0;
for (const j of spoje.filter(q => q.spojka)) {
  const sp = j.spojka;
  const ovR = AX.map(k => Math.min(sp.box.max[k], j.rodic.box.max[k]) - Math.max(sp.box.min[k], j.rodic.box.min[k]));
  const ovD = AX.map(k => Math.min(sp.box.max[k], j.dite.box.max[k]) - Math.max(sp.box.min[k], j.dite.box.min[k]));
  const aIdx = AX.indexOf(j.osa);
  const hookRodic = ovR[aIdx];                    // zámek v rodiči = přesah ve směru n
  const ua = AX.findIndex(k => { const u = SMERY[j.spojka.strana]; return Math.abs(u[k]) > 0.5; });
  const hookDite = ovD[ua];                       // zámek v dítěti = přesah ve směru u
  const ok = Math.abs(hookRodic - 3.43) < 0.1 && Math.abs(hookDite - 3.43) < 0.1;
  if (ok) spojekOK++; else err(`spojka ${sp.id}: zámek rodič ${r3(hookRodic)} / dítě ${r3(hookDite)} mm (očekáváno 3,43 jako ve všech spojkách šablony)`);
  L(`  ${ok ? 'OK ' : 'CHYBA'} ${sp.id.padEnd(34)} strana ${j.spojka.strana}  zámek v ${j.rodic.id}: ${r3(hookRodic)} mm, v ${j.dite.id}: ${r3(hookDite)} mm`);
}
L(`spojek se správným zámkem: ${spojekOK} / ${spojky.length}; spojů BEZ rohové spojky: ${spoje.filter(q => !q.spojka).length} (${spoje.filter(q => !q.spojka).map(q => q.dite.id + '->' + q.rodic.id).join(', ') || '-'})`);

// --- 7.5 účetnictví spojů (invarianty I1-I4 validátoru scripts/2026-08-19_bookkeeping_validator.js na podmnožině profilů) ---
L('');
L('== 6. ÚČETNICTVÍ SPOJŮ (invarianty I1-I4 validátoru, podmnožina = profily; příslušenství viz poznámka) ==');
const profIdx = new Map(profily.map((p, i) => [p, i]));
let I1 = 0, I2 = 0, I4 = 0, flushProf = 0, sumJoint = 0;
for (const p of profily) {
  const e = entry(p);
  sumJoint += e.jointCount || 0;
  (e.licPeers || new Set()).forEach(q => { if (!(q.licPeers && q.licPeers.has(e))) I1++; });
  [...(e.usedConn || [])].forEach(ci => { if (ci < 0 || ci >= e.connectorsLocal.length) I4++; });
}
const flushPairs = [];
for (let i = 0; i < profily.length; i++) for (let j = i + 1; j < profily.length; j++) {
  const r = lib.touchReport(profily[i], profily[j]);
  const f = AX.filter(k => Math.abs(r[k].overlap) <= EPS), o = AX.filter(k => r[k].overlap > EPS);
  if (f.length === 1 && o.length === 2) flushPairs.push([profily[i], profily[j]]);
}
for (const [a, b] of flushPairs) { flushProf++; const ea = entry(a), eb = entry(b); if (!(ea.licPeers && ea.licPeers.has(eb)) && !(eb.licPeers && eb.licPeers.has(ea))) I2++; }
const licPary = new Set(); profily.forEach(p => (entry(p).licPeers || new Set()).forEach(q => licPary.add(klic(p, q.item))));
const I2b = [...licPary].filter(k => !flushPairs.some(([a, b]) => klic(a, b) === k)).length;
const I3 = sumJoint === flushPairs.length;
L(`profilů ${profily.length}, plošných dotyků profil x profil (měřeno geometricky) ${flushProf}, součet joint_count ${sumJoint}, dvojic v lic_peers ${licPary.size}`);
L(`  I1 symetrie lic_peers: ${I1 === 0 ? 'OK' : 'CHYBA ' + I1}; I2 každý dotyk registrován: ${I2 === 0 ? 'OK' : 'CHYBA ' + I2}; I2b lic_peers bez dotyku: ${I2b === 0 ? 'OK' : 'CHYBA ' + I2b}; I3 součet joint_count == dotyky: ${I3 ? 'OK' : 'CHYBA'}; I4 used_conn indexy: ${I4 === 0 ? 'OK' : 'CHYBA ' + I4}`);
if (I1 || I2 || I2b || !I3 || I4) err(`účetnictví spojů: I1=${I1} I2=${I2} I2b=${I2b} I3=${I3} I4=${I4}`);
if (flushProf !== spoje.length + bocniDosedy.length) err(`počet plošných dotyků profilů ${flushProf} != spoje ${spoje.length} + boční dosedy ${bocniDosedy.length}`);
// ostatní plošné dotyky (deska/držák/zástupné na profilu...) - nejsou spoj, jen nosný dosed
const dosedy = {};
for (let i = 0; i < items.length; i++) for (let j = i + 1; j < items.length; j++) {
  const A = items[i], B = items[j];
  if (A.kat === 'profil' && B.kat === 'profil') continue;
  const r = lib.touchReport(A, B);
  const f = AX.filter(k => Math.abs(r[k].overlap) <= EPS), o = AX.filter(k => r[k].overlap > EPS);
  if (f.length === 1 && o.length === 2) { const kk = [A.kat, B.kat].sort().join(' x '); dosedy[kk] = (dosedy[kk] || 0) + 1; }
}
L(`ostatní plošné dosedy (nosné/montážní, do spojů se NEPOČÍTAJÍ): ${Object.entries(dosedy).map(([k, v]) => `${k} ${v}`).join(', ') || '-'}`);

// --- 7.6 kóty z výkresu x naměřeno ---
L('');
L('== 7. KÓTY Z VÝKRESU x NAMĚŘENO V SESTAVĚ ==');
function filtrItemu(f) { return items.filter(i => f.includes(i.kat) || f.includes(i.id)); }
const H = {
  rozpeti: (f, o) => { const a = filtrItemu(f); if (!a.length) throw new Error('rozpeti: nic nenalezeno pro ' + f); return Math.max(...a.map(i => i.box.max[o])) - Math.min(...a.map(i => i.box.min[o])); },
  minimum: (id, o) => byId.get(id).box.min[o],
  maximum: (id, o) => byId.get(id).box.max[o],
  delka: id => byId.get(id).delka,
  mezera: (a, b, o) => Math.max(byId.get(a).box.min[o] - byId.get(b).box.max[o], byId.get(b).box.min[o] - byId.get(a).box.max[o]),
};
const koty = [];
for (const k of spec.koty) {
  let m;
  try { m = new Function(...Object.keys(H), `"use strict"; return (${k.mereni});`)(...Object.values(H)); } catch (e) { err(`kóta "${k.kota}": ${e.message}`); m = NaN; }
  const rozdil = m - k.hodnota;
  const ok = Math.abs(rozdil) <= 0.01;
  if (!ok) err(`kóta "${k.kota}": výkres ${k.hodnota}, naměřeno ${r3(m)}`);
  koty.push({ kota: k.kota, vykres: k.hodnota, namereno: r3(m), rozdil: r3(rozdil), ok, mereni: k.mereni });
  L(`  ${ok ? 'OK ' : 'CHYBA'} ${String(k.hodnota).padStart(6)} ${String(r3(m)).padStart(9)} ${r3(rozdil).toFixed(3).padStart(7)}  ${k.kota}`);
}
L(`kót porovnáno: ${koty.length}, shoduje se na 0,01 mm: ${koty.filter(k => k.ok).length}`);
if (!koty.length) err('žádná kóta nebyla porovnána');

// ---------------------------------------------------------------------------------------------------------------
// 8) výstupy: seznam dílů, custom_shapes.data, kusovník
// ---------------------------------------------------------------------------------------------------------------
const BARVY = {
  profil: '#c3c8ce', deska: '#8f9399', spojka: '#2d3139', patka: '#16181b', drzak: '#9aa3b0', led: '#f2d45c',
  'zastupne-draha': '#e8833a', 'zastupne-kovani': '#d6504f', 'zastupne-rameno': '#3f8fd2', 'zastupne-plech': '#b8bec5', 'zastupne-vypinac': '#8f63cf',
};
const NAZVY_KAT = {
  profil: 'Profil 40x40 SuperLight S10 (Object_11)', deska: 'Laminodeska šedá 18 mm (product_4933)', spojka: 'Rohová spojka 40x40 (product_3176)', patka: 'Stavitelná patka M10 (product_3283)',
  drzak: 'Úhelník 40x40 - držák desky (product_3207)', led: 'Osvětlení LED 1,2 m (product_4929)', 'zastupne-draha': 'ZÁSTUPNĚ válečkové dráhy 60x24', 'zastupne-kovani': 'ZÁSTUPNĚ polohovací kování',
  'zastupne-rameno': 'ZÁSTUPNĚ rameno monitoru', 'zastupne-plech': 'ZÁSTUPNĚ čelní plech dráhy', 'zastupne-vypinac': 'ZÁSTUPNĚ vypínač',
};
const realneSerazene = items.filter(i => !i.zastupne);
const zastupneItems = items.filter(i => i.zastupne);
for (const it of items) if (it.role.length > 120) err('role delší než 120 znaků: ' + it.role);
{ const roleSet = new Set(); for (const it of items) { if (roleSet.has(it.role)) err('duplicitní role ' + it.role); roleSet.add(it.role); } }

const serial = lib.serializeToCustomShapeParts(realneSerazene.map(entry));
serial.forEach((p, i) => { p.role = realneSerazene[i].role; });
const zastupneSerial = zastupneItems.map(it => ({ part_id: '__KVADR_1x1x1__', ...partSpec(it), role: it.role, color: BARVY[it.kat] }));
const zastupneParts = zastupneItems.map(it => ({ id: it.id, role: it.role, kategorie: it.kat, nazev: it.nazev, poznamka: it.poznamka, katalogova_nahrada: 'kvadr_plny_1x1x1.glb (jednotkový kvádr; part_id karty z DB)', ...(() => { const s = partSpec(it); return { position: s.position.map(r6), quaternion: s.quaternion.map(r6), scale: s.scale.map(r6) }; })(), rozmer_mm: it.box.getSize(v3(0, 0, 0)).toArray().map(r3), box_min: it.box.min.toArray().map(r3), box_max: it.box.max.toArray().map(r3) }));

const seznamDilu = items.map((it, i) => {
  const ps = partSpec(it), sz = it.box.getSize(v3(0, 0, 0));
  const ki = katalogInfo[it.klic];
  return {
    index: i, role: it.role, id: it.id, kategorie: it.kat, part_id: it.part_id, sku: ki.sku || null, nazev: ki.nazev, zastupne: !!it.zastupne,
    glb: path.relative(ROOT, ki.glbPath), glb_je_nahrada: !!ki.nahrada,
    position: ps.position.map(r6), quaternion: ps.quaternion.map(r6), scale: ps.scale.map(r6),
    rozmer_mm: sz.toArray().map(r3), box_min: it.box.min.toArray().map(r3), box_max: it.box.max.toArray().map(r3),
    ...(it.kat === 'profil' ? { osa: it.osa, delka_mm: r3(it.delka) } : {}),
    ...(it.kat === 'spojka' ? { dite: it.dite, rodic: it.rodic, strana: it.strana } : {}),
  };
});

// kusovník
function kusovnik() {
  const bom = { profily: [], desky: [], spojky: {}, patky: {}, drzaky: {}, led: {}, zastupne: [] };
  const poDelce = new Map();
  for (const p of profily) { const d = r3(p.delka); if (!poDelce.has(d)) poDelce.set(d, []); poDelce.get(d).push(p.id); }
  bom.profily = [...poDelce.entries()].sort((a, b) => b[0] - a[0]).map(([delka, ids]) => ({ delka_mm: delka, ks: ids.length, id: ids }));
  const tot = bom.profily.reduce((s, r) => s + r.delka_mm * r.ks, 0);
  bom.profily_celkem = { ks: profily.length, delka_mm: r3(tot) };
  bom.desky = desky.map(d => { const sz = d.box.getSize(v3(0, 0, 0)); return { id: d.id, rozmer_mm: [r3(sz.x), r3(sz.z)], tloustka_mm: r3(sz.y), plocha_m2: r3(sz.x * sz.z / 1e6) }; });
  bom.desky_celkem_m2 = r3(bom.desky.reduce((s, d) => s + d.plocha_m2, 0));
  const k1 = (kat, klic) => ({ part_id: katalogInfo[klic].part_id, sku: katalogInfo[klic].sku, nazev: katalogInfo[klic].nazev, ks: items.filter(i => i.kat === kat).length });
  bom.spojky = k1('spojka', 'spojka40'); bom.patky = k1('patka', 'patka40'); bom.drzaky = k1('drzak', 'uhelnik40'); bom.led = k1('led', 'led1200');
  bom.profil_katalog = { part_id: K.profil40.part_id, sku: K.profil40.sku, nazev: K.profil40.nazev };
  bom.deska_katalog = { part_id: K.deska18.part_id, sku: K.deska18.sku, nazev: K.deska18.nazev };
  bom.zastupne = zastupneItems.map(i => ({ id: i.id, kategorie: i.kat, nazev: i.nazev, rozmer_mm: i.box.getSize(v3(0, 0, 0)).toArray().map(r3) }));
  bom.spoje_bez_rohove_spojky = spoje.filter(j => !j.spojka).map(j => `${j.dite.id} -> ${j.rodic.id}`);
  bom.pocet_spoju_profilu = { T_a_celni: spoje.length, bocni_dosedy: bocniDosedy.length };
  return bom;
}
const bom = kusovnik();
function bomMd(b) {
  const o = [];
  o.push('# Kusovník - Stůl balení LIDL (prototyp II)', '');
  o.push(`Generováno ze specifikace (sha ${specHash}). Díly se identifikují part_id / SKU, ne názvem.`, '');
  o.push(`## Profily (${b.profil_katalog.part_id}, SKU ${b.profil_katalog.sku}, ${b.profil_katalog.nazev})`, '', '| délka (mm) | ks | profily (id) |', '|---:|---:|---|');
  b.profily.forEach(r => o.push(`| ${r.delka_mm} | ${r.ks} | ${r.id.join(', ')} |`));
  o.push(`| **celkem** | **${b.profily_celkem.ks}** | ${b.profily_celkem.delka_mm} mm (${(b.profily_celkem.delka_mm / 1000).toFixed(2)} m) |`, '');
  o.push(`## Desky (${b.deska_katalog.part_id}, SKU ${b.deska_katalog.sku}, ${b.deska_katalog.nazev})`, '', '| deska | rozměr X x Z (mm) | tl. (mm) | plocha (m2) |', '|---|---:|---:|---:|');
  b.desky.forEach(d => o.push(`| ${d.id} | ${d.rozmer_mm[0]} x ${d.rozmer_mm[1]} | ${d.tloustka_mm} | ${d.plocha_m2} |`));
  o.push(`| **celkem** | | | **${b.desky_celkem_m2}** |`, '');
  o.push('## Příslušenství z katalogu', '', '| part_id | SKU | název | ks |', '|---|---|---|---:|');
  for (const k of [b.spojky, b.patky, b.drzaky, b.led]) o.push(`| ${k.part_id} | ${k.sku} | ${k.nazev} | ${k.ks} |`);
  o.push('', `Spojů profilů: ${b.pocet_spoju_profilu.T_a_celni} T/čelních + ${b.pocet_spoju_profilu.bocni_dosedy} bočních dosedů (posuvné profily / sloupek ramene). Rohových spojek 3176: ${b.spojky.ks}; spoje BEZ rohové spojky (šroub přes čelo): ${b.spoje_bez_rohove_spojky.length ? b.spoje_bez_rohove_spojky.join(', ') : '-'}.`, '');
  o.push('## Zástupné díly (NEJSOU v katalogu - potřebují ID z DB)', '', '| id | druh | název | rozměr (mm) |', '|---|---|---|---|');
  b.zastupne.forEach(z => o.push(`| ${z.id} | ${z.kategorie} | ${z.nazev} | ${z.rozmer_mm.join(' x ')} |`));
  return o.join('\n') + '\n';
}

// ---------------------------------------------------------------------------------------------------------------
// 9) zápis výstupů
// ---------------------------------------------------------------------------------------------------------------
fs.mkdirSync(OUT, { recursive: true });
const wj = (f, o) => fs.writeFileSync(path.join(OUT, f), JSON.stringify(o, null, 1) + '\n');
wj('sestava_parts.json', { _popis: 'Seznam dílů sestavy Stůl balení LIDL (prototyp II). Souřadnice mm, Y nahoru, X doprava, Z k pozorovateli; position/quaternion/scale jsou transformace GLB dílu jako v custom_shapes.', spec_sha: specHash, jednotky: 'mm', dily: seznamDilu });
wj('custom_shape_data.json', { parts: serial, join_groups: [], frame_groups: [] });
wj('custom_shape_data_se_zastupnymi.json', { _popis: 'Totéž + zástupné díly s part_id "__KVADR_1x1x1__" (nahradí ho zapis_do_db.py --zastupny-kvadr <part_id karty s kvadr_plny_1x1x1.glb>). lic_peers indexy beze změny (zástupné díly jsou na konci).', parts: [...serial, ...zastupneSerial], join_groups: [], frame_groups: [] });
wj('zastupne_dily.json', { _popis: 'Díly, které nejsou v katalogu. Orientační tvar = kvádr dané velikosti; skutečné díly potřebují karty v DB.', dily: zastupneParts });
wj('kusovnik.json', bom);
fs.writeFileSync(path.join(OUT, 'kusovnik.md'), bomMd(bom));
wj('koty.json', koty);

const NAHLED_SABLONA = String.raw`<!doctype html>
<html lang="cs"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Stůl balení LIDL - 3D model</title>
<style>
:root{--bg:#eef1f4;--fg:#18222c;--panel:rgba(255,255,255,.93);--line:#c4ccd4;--accent:#c8102e;--muted:#55636f;--ok:#1b7f3a;--bad:#b3261e}
@media (prefers-color-scheme:dark){:root{--bg:#12161b;--fg:#e8edf2;--panel:rgba(28,34,42,.93);--line:#36414d;--accent:#ff5266;--muted:#9aa8b6;--ok:#58c27d;--bad:#ff7b72}}
html,body{height:100%;margin:0}
body{background:var(--bg);color:var(--fg);font:13px/1.35 -apple-system,"Segoe UI",Roboto,Arial,sans-serif;overflow:hidden}
canvas{display:block;width:100%;height:100%;outline:none}
.pan{position:absolute;background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:8px 10px;box-sizing:border-box}
#leg{left:12px;top:12px;width:330px;max-height:calc(100% - 24px);overflow:auto}
#leg h1{font-size:14px;margin:0 0 2px}
#leg small{color:var(--muted);display:block;margin-bottom:6px}
.kat{display:flex;align-items:center;gap:6px;margin:3px 0;cursor:pointer}
.kat i{display:inline-block;width:14px;height:14px;border-radius:3px;border:1px solid rgba(0,0,0,.35);flex:0 0 14px}
.kat span{flex:1}.kat b{font-weight:600;color:var(--muted)}
.zast{margin-top:6px;padding-top:6px;border-top:1px dashed var(--line);color:var(--muted);font-size:12px}
.row{display:flex;gap:6px;flex-wrap:wrap;margin:6px 0}
button{font:inherit;color:var(--fg);background:transparent;border:1px solid var(--line);border-radius:7px;padding:3px 9px;cursor:pointer}
button:hover{border-color:var(--accent)}
input[type=range]{width:120px;accent-color:var(--accent)}
#koty{right:12px;top:12px;width:380px;max-height:calc(100% - 24px);overflow:auto;font-size:12px}
#koty table{border-collapse:collapse;width:100%}
#koty td,#koty th{padding:2px 4px;border-bottom:1px solid var(--line);text-align:right}
#koty td:first-child,#koty th:first-child{text-align:left}
#koty .ok{color:var(--ok)}#koty .bad{color:var(--bad);font-weight:700}
summary{cursor:pointer;font-weight:600}
#tip{position:absolute;pointer-events:none;background:var(--panel);border:1px solid var(--accent);border-radius:8px;padding:6px 8px;font-size:12px;max-width:340px;display:none;z-index:5}
#hint{position:absolute;left:12px;bottom:8px;color:var(--muted);font-size:12px;pointer-events:none}
@media (max-width:820px){#koty{display:none}#leg{width:250px}}
</style></head><body>
<div class="pan" id="leg"><h1 id="nazev"></h1><small id="info"></small><div id="kat"></div>
<div class="row"><button data-v="sikmo">šikmo</button><button data-v="celo">zepředu</button><button data-v="zad">zezadu</button><button data-v="leva">zleva</button><button data-v="prava">zprava</button><button data-v="shora">shora</button></div>
<div class="row"><label>průhlednost desek <input id="pruh" type="range" min="15" max="100" value="100"></label></div>
<div class="row"><label><input id="ram" type="checkbox"> obrysový rámeček 1750 x 800 x 2100</label></div></div>
<div class="pan" id="koty"><details open><summary>Kóty z výkresu x naměřeno v sestavě (mm)</summary><table id="kt"></table></details></div>
<div id="tip"></div><div id="hint">Táhni myší: otáčení. Kolečko: přiblížení. Pravé tlačítko: posun. Najetím na díl se ukáže part_id, SKU a rozměr. Souřadnice v mm (X doprava, Y nahoru, Z k pozorovateli).</div>
<script type="application/json" id="data">__DATA__</script>
<script>/*__THREE__*/</script>
<script>/*__ORBIT__*/</script>
<script>
(function(){
var D=JSON.parse(document.getElementById('data').textContent);
document.getElementById('nazev').textContent=D.nazev;
document.getElementById('info').textContent='dílů '+D.souhrn.dilu+' (profily, desky, spojky, patky, držáky + zástupné) | spojů profilů '+D.souhrn.spoju+' | validace: '+(D.souhrn.chyb?('CHYB '+D.souhrn.chyb):'bez chyb')+' | spec '+D.souhrn.spec_sha;
function parseGLB(b64){
  var bin=atob(b64),u=new Uint8Array(bin.length),i;for(i=0;i<bin.length;i++)u[i]=bin.charCodeAt(i);
  var dv=new DataView(u.buffer),jl=dv.getUint32(12,true),json=JSON.parse(new TextDecoder().decode(u.subarray(20,20+jl)));
  var binStart=20+jl+8,pos=[],idx=[],base=0;
  json.meshes.forEach(function(m){m.primitives.forEach(function(pr){
    var pa=json.accessors[pr.attributes.POSITION],bv=json.bufferViews[pa.bufferView],o=binStart+(bv.byteOffset||0)+(pa.byteOffset||0),st=bv.byteStride||12,k;
    for(k=0;k<pa.count;k++){pos.push(dv.getFloat32(o+k*st,true),dv.getFloat32(o+k*st+4,true),dv.getFloat32(o+k*st+8,true));}
    if(pr.indices!=null){var ia=json.accessors[pr.indices],ib=json.bufferViews[ia.bufferView],io=binStart+(ib.byteOffset||0)+(ia.byteOffset||0),sz=ia.componentType===5121?1:(ia.componentType===5123?2:4);
      for(k=0;k<ia.count;k++){idx.push(base+(sz===1?dv.getUint8(io+k):(sz===2?dv.getUint16(io+k*2,true):dv.getUint32(io+k*4,true))));}}
    else{for(k=0;k<pa.count;k++)idx.push(base+k);}
    base+=pa.count;});});
  var g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.Float32BufferAttribute(pos,3));g.setIndex(idx);
  var ng=g.toNonIndexed();ng.computeVertexNormals();return ng;
}
var renderer=new THREE.WebGLRenderer({antialias:true});renderer.setPixelRatio(Math.min(devicePixelRatio,2));renderer.setSize(innerWidth,innerHeight);document.body.insertBefore(renderer.domElement,document.body.firstChild);
var scene=new THREE.Scene();scene.background=new THREE.Color(getComputedStyle(document.body).backgroundColor);
scene.add(new THREE.HemisphereLight(0xffffff,0x778899,0.85));
var l1=new THREE.DirectionalLight(0xffffff,0.8);l1.position.set(-1500,3000,3500);scene.add(l1);
var l2=new THREE.DirectionalLight(0xffffff,0.35);l2.position.set(3000,1500,-2000);scene.add(l2);
var camera=new THREE.PerspectiveCamera(30,innerWidth/innerHeight,50,40000);
var T=new THREE.Vector3(875,1000,400);
var controls=new THREE.OrbitControls(camera,renderer.domElement);controls.enableDamping=true;controls.dampingFactor=0.12;controls.target.copy(T);
function pohled(dx,dy,dz,d){camera.position.set(T.x+dx*d,T.y+dy*d,T.z+dz*d);controls.target.copy(T);controls.update();}
var VIEWS={sikmo:[-0.62,0.32,0.72,5600],celo:[0,0.04,1,5300],zad:[0,0.04,-1,5300],leva:[-1,0.04,0,5300],prava:[1,0.04,0,5300],shora:[0,1,0.02,5000]};
pohled.apply(null,VIEWS.sikmo);
var grid=new THREE.GridHelper(4000,40,0x889099,0xb8c0c8);grid.position.set(875,0,400);scene.add(grid);
var katInfo={};D.kategorie.forEach(function(k){katInfo[k.kat]=k;});
var geoCache={},edgeCache={},matCache={},meshes=[],byKat={};
D.dily.forEach(function(d){
  var g=geoCache[d.glb]||(geoCache[d.glb]=parseGLB(D.glb[d.glb]));
  var k=katInfo[d.kat];
  var mat=new THREE.MeshStandardMaterial({color:new THREE.Color(k.barva),roughness:d.kat==='profil'?0.45:0.7,metalness:d.kat==='profil'?0.55:(d.kat==='spojka'||d.kat==='patka'?0.3:0.05),flatShading:true});
  if(d.kat==='deska'){mat.transparent=true;}
  var m=new THREE.Mesh(g,mat);m.position.fromArray(d.p);m.quaternion.fromArray(d.q);m.scale.fromArray(d.s);m.userData=d;
  var eg=edgeCache[d.glb]||(edgeCache[d.glb]=new THREE.EdgesGeometry(g,28));
  var ln=new THREE.LineSegments(eg,new THREE.LineBasicMaterial({color:0x20262d,transparent:true,opacity:d.kat==='profil'?0.55:0.4}));m.add(ln);
  scene.add(m);meshes.push(m);(byKat[d.kat]=byKat[d.kat]||[]).push(m);
});
var box=new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(1750,2100,800)),new THREE.LineBasicMaterial({color:0xc8102e}));box.position.set(875,1050,400);box.visible=false;scene.add(box);
document.getElementById('ram').onchange=function(e){box.visible=e.target.checked;};
var katEl=document.getElementById('kat'),zast=null;
D.kategorie.forEach(function(k){
  if(k.zastupne&&!zast){zast=document.createElement('div');zast.className='zast';zast.textContent='Zástupné díly (NEJSOU v katalogu, tvar orientační):';katEl.appendChild(zast);}
  var lab=document.createElement('label');lab.className='kat';
  lab.innerHTML='<input type="checkbox" checked><i style="background:'+k.barva+'"></i><span>'+k.nazev+'</span><b>'+k.pocet+'</b>';
  lab.querySelector('input').onchange=function(e){(byKat[k.kat]||[]).forEach(function(m){m.visible=e.target.checked;});};
  (k.zastupne?zast:katEl).appendChild(lab);
});
document.getElementById('pruh').oninput=function(e){var o=e.target.value/100;(byKat.deska||[]).forEach(function(m){m.material.opacity=o;m.material.depthWrite=o>0.95;});};
document.querySelectorAll('button[data-v]').forEach(function(b){b.onclick=function(){pohled.apply(null,VIEWS[b.dataset.v]);};});
var kt=document.getElementById('kt'),h='<tr><th>kóta</th><th>výkres</th><th>naměřeno</th><th>rozdíl</th></tr>';
D.koty.forEach(function(k){h+='<tr><td>'+k.kota+'</td><td>'+k.vykres+'</td><td class="'+(k.ok?'ok':'bad')+'">'+k.namereno+'</td><td class="'+(k.ok?'ok':'bad')+'">'+(k.rozdil>0?'+':'')+k.rozdil+'</td></tr>';});
kt.innerHTML=h;
var ray=new THREE.Raycaster(),mouse=new THREE.Vector2(),tip=document.getElementById('tip'),hover=null;
function ukaz(e){
  var r=renderer.domElement.getBoundingClientRect();mouse.set(((e.clientX-r.left)/r.width)*2-1,-((e.clientY-r.top)/r.height)*2+1);
  ray.setFromCamera(mouse,camera);var hit=ray.intersectObjects(meshes.filter(function(m){return m.visible;}),false)[0];
  if(hover&&(!hit||hit.object!==hover)){hover.material.emissive.setHex(0);hover=null;}
  if(!hit){tip.style.display='none';return;}
  hover=hit.object;hover.material.emissive.setHex(0x553300);
  var d=hover.userData;
  tip.innerHTML='<b>'+d.role+'</b><br>'+(d.part_id?('part_id <b>'+d.part_id+'</b>'+(d.sku?' | SKU '+d.sku:'')):'<b>ZÁSTUPNÝ díl - ID karty chybí</b>')+'<br>'+d.nazev+'<br>rozměr '+d.sz.join(' x ')+' mm<br>od ['+d.dolni.join(', ')+'] do ['+d.horni.join(', ')+']'+(d.nahrada?'<br><i>geometrie = náhradní kvádr (GLB karty v repu chybí)</i>':'')+(d.poznamka?('<br><i>'+d.poznamka+'</i>'):'');
  tip.style.display='block';tip.style.left=Math.min(e.clientX+14,innerWidth-360)+'px';tip.style.top=Math.min(e.clientY+14,innerHeight-130)+'px';
}
renderer.domElement.addEventListener('mousemove',ukaz);
addEventListener('resize',function(){renderer.setSize(innerWidth,innerHeight);camera.aspect=innerWidth/innerHeight;camera.updateProjectionMatrix();});
window.__nahled={camera:camera,controls:controls,pohled:pohled,VIEWS:VIEWS,scene:scene,renderer:renderer,meshes:meshes};
(function loop(){requestAnimationFrame(loop);controls.update();renderer.render(scene,camera);})();
})();
</script></body></html>
`;

// ---------------------------------------------------------------------------------------------------------------
// 10) samostatný 3D náhled (bez sítě): three.js + OrbitControls z kufriky_cloud/vendor, GLB vložené jako base64
// ---------------------------------------------------------------------------------------------------------------
function postavNahled() {
  const vendor = f => fs.readFileSync(path.join(ROOT, 'kufriky_cloud/vendor', f), 'utf8').replace(/<\/script/gi, '<\\/script');
  const glbMap = {};
  const dilyData = items.map((it, i) => {
    const ki = katalogInfo[it.klic];
    const key = path.basename(ki.glbPath);
    if (!glbMap[key]) glbMap[key] = fs.readFileSync(ki.glbPath).toString('base64');
    const ps = partSpec(it);
    return { i, id: it.id, kat: it.kat, role: it.role, part_id: it.part_id || null, sku: ki.sku || null, nazev: it.nazev || ki.nazev, zastupne: !!it.zastupne, nahrada: !!ki.nahrada, glb: key,
      p: ps.position.map(r6), q: ps.quaternion.map(r6), s: ps.scale.map(r6), sz: it.box.getSize(v3(0, 0, 0)).toArray().map(r3), dolni: it.box.min.toArray().map(r3), horni: it.box.max.toArray().map(r3), poznamka: it.poznamka || null };
  });
  const kategorie = Object.keys(katPocty).map(k => ({ kat: k, nazev: NAZVY_KAT[k] || k, barva: BARVY[k] || '#999999', pocet: katPocty[k], zastupne: k.startsWith('zastupne') }));
  const data = { nazev: spec.nazev, dily: dilyData, glb: glbMap, kategorie, koty, souhrn: { chyb: chyby.length, varovani: varovani.length, spoju: spoje.length, spojek: spojky.length, dilu: items.length, spec_sha: specHash } };
  const html = NAHLED_SABLONA
    .replace('/*__THREE__*/', () => vendor('three.min.js'))
    .replace('/*__ORBIT__*/', () => vendor('OrbitControls.js'))
    .replace('__DATA__', () => JSON.stringify(data).replace(/<\//g, '<\\/'));
  fs.mkdirSync(path.join(HERE, 'nahled'), { recursive: true });
  fs.writeFileSync(path.join(HERE, 'nahled/stul_balici.html'), html);
  return html.length;
}

const nahledB = postavNahled();
L('');
L('== 8. SOUHRN ==');
L(`dílů v custom_shape_data.json: ${serial.length} (profily ${profily.length}, desky ${desky.length}, patky ${patky.length}, držáky ${drzaky.length}, rohové spojky ${spojky.length}, LED ${items.filter(i => i.kat === 'led').length}); zástupných dílů mimo katalog: ${zastupneItems.length}`);
const maxPartsLimit = 1000;
if (serial.length > maxPartsLimit) err(`víc než ${maxPartsLimit} dílů (CUSTOM_SHAPE_MAX_PARTS)`);
L(`varování: ${varovani.length}`); varovani.forEach(w => L('  VAROVÁNÍ ' + w));
L(`chyb: ${chyby.length}`); chyby.forEach(c => L('  CHYBA ' + c));
L(chyby.length ? 'VÝSLEDEK: NEPROŠLO' : 'VÝSLEDEK: OK (vše změřeno a čisté; rozsah viz oddíl 0)');
fs.writeFileSync(path.join(OUT, 'validace.txt'), V.join('\n') + '\n');
console.log(V.join('\n'));
process.exitCode = chyby.length ? 1 : 0;
