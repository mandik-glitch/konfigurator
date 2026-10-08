// Technicky rez konkretniho rohu ze ZIVEHO stavu ulozene sestavy
// (product_assemblies.id=58) - bot10, na zadani bot8/Robert 2026-09-11.
// Robertovo zavazne pravidlo: umisteni dilu se schvaluje nad 2D
// technickymi rezy s kotami ze ZIVEHO stavu, ne nad vlastnim rigem
// (viz kolecko 3404 - schvaleny rez z vlastniho rigu neodpovidal
// scene). Tenhle skript NEVYMYSLI zadnou orientaci - bere PRESNE
// position/quaternion/scale ulozene v product_assemblies.data.parts
// (totozne s tim, co vykresluje zivy web/scena) a stejnou triangle-
// plane-intersection logiku jako 2026-08-20_live_section_cut.js
// (sectionSegments), jen zobecnenou na N dilu a 2 rovnou zadane roviny
// rezu (misto odvozovani "steny" - tady zadna stena neni, je to roh
// dvou profilu).
//
// Roh: zaslepka (product_3071) na pozici cca (-735.5, 925, -1658.5) v
// sestave id=58 (Proace Compact 16- A), sousedi geometricky se DVEMA
// profily (Object_7) - vodorovny (konec na ose X) a svisla noha
// (horni konec na ose Y) - + uhelnikova spojka (product_3045), ktera
// je spojuje. Otazka pro Roberta: ktery z tech dvou koncu zaslepka
// fakticky zakryva.
//
// Pouziti: node 2026-09-11_corner_zaslepka_section.js
// (assembly id, part indexy a roviny rezu jsou natvrdo dole - jednorazovy
// nastroj pro tenhle konkretni pripad, ne obecna knihovna)
const fs = require("fs");
const path = require("path");
const THREE = require("three");
const { parseGlbMesh } = require("./2026-08-19_glb_real_geometry.js");

const KATALOG_DIR = "/opt/konfigurator/webapp/katalog";

function load(glbFile, posArr, quatArr, scaleArr) {
  const obj = parseGlbMesh(path.join(KATALOG_DIR, glbFile));
  obj.position.fromArray(posArr);
  obj.quaternion.fromArray(quatArr);
  obj.scale.fromArray(scaleArr || [1, 1, 1]);
  obj.updateMatrixWorld(true);
  return obj;
}

// --- PRESNE data z product_assemblies.id=58, parts index 2/3/40 (bracket) + endcap idx1 z is_endcap filtru ---
// (vytazeno primo z DB - viz scratchpad dump joint_sample20_dump.json, shape.id===58)
const PARTS = JSON.parse(fs.readFileSync("/tmp/claude-0/-opt-konfigurator/a0c7cc49-b540-492a-9d17-c27a0dbab25e/scratchpad/corner58_parts.json", "utf8"));

const objects = PARTS.map(p => ({
  label: p.label, part_id: p.part_id,
  obj: load(p.glb_file, p.position, p.quaternion, p.scale),
}));

function sectionSegments(obj, planeNormal, planeOrigin, projFn) {
  const segs = [];
  const vA = new THREE.Vector3(), vB = new THREE.Vector3(), vC = new THREE.Vector3();
  obj.traverse(n => {
    if (!n.isMesh || !n.geometry || !n.geometry.attributes.position) return;
    const pos = n.geometry.attributes.position, index = n.geometry.index;
    const triCount = index ? index.count / 3 : pos.count / 3;
    for (let t = 0; t < triCount; t++) {
      const ia = index ? index.getX(t * 3) : t * 3, ib = index ? index.getX(t * 3 + 1) : t * 3 + 1, ic = index ? index.getX(t * 3 + 2) : t * 3 + 2;
      vA.fromBufferAttribute(pos, ia).applyMatrix4(n.matrixWorld);
      vB.fromBufferAttribute(pos, ib).applyMatrix4(n.matrixWorld);
      vC.fromBufferAttribute(pos, ic).applyMatrix4(n.matrixWorld);
      const pts = [];
      [[vA, vB], [vB, vC], [vC, vA]].forEach(([p1, p2]) => {
        const d1 = p1.clone().sub(planeOrigin).dot(planeNormal), d2 = p2.clone().sub(planeOrigin).dot(planeNormal);
        if ((d1 > 0) !== (d2 > 0)) {
          const s = d1 / (d1 - d2);
          pts.push(projFn(p1.clone().lerp(p2, s)));
        }
      });
      if (pts.length === 2) segs.push([pts[0][0], pts[0][1], pts[1][0], pts[1][1]]);
    }
  });
  return segs;
}

// VIEW A - celni pohled (rovina rezu kolma na Z, konstantni Z), osy
// vykreslene X (vodorovny profil) x Y (svisla noha) - ukaze, jestli
// zaslepka sedi na vrcholu nohy, na konci vodorovneho profilu, nebo
// na obou.
const zCut = -1658.5; // stred zaslepky, prochazi vsemi 4 dily
const viewA = {};
objects.forEach(o => {
  viewA[o.label] = sectionSegments(
    o.obj, new THREE.Vector3(0, 0, 1), new THREE.Vector3(0, 0, zCut),
    p => [p.x, p.y]
  );
});

// VIEW B - pudorys (rovina rezu kolma na Y, konstantni Y = 918, tesne
// pod vrcholem nohy/uvnitr zaslepky) - X x Z, ukaze pudorysny vztah
// (je profil dutý/otevreny v teto vysce, nebo uz zakryty?).
const yCut = 918;
const viewB = {};
objects.forEach(o => {
  viewB[o.label] = sectionSegments(
    o.obj, new THREE.Vector3(0, 1, 0), new THREE.Vector3(0, yCut, 0),
    p => [p.x, p.z]
  );
});

// POZOR (oprava po prvnim pokusu): profil ma x_min=-720.5 (konec u rohu)
// a x_max=-431.5 (daleky konec) - "za koncem" tedy znamena x < -720.5,
// NE x > -720.5 (to je porad UVNITR profilu). Noha zabira presne
// x=[-750.5,-720.5], tedy sedi FLUSH hned za koncem profilu (0mm mezera)
// - neexistuje zadny "prazdny prostor" v ose X, protoze noha je hned
// tam. Otazka tedy neni "je tam neco v X", ale "je STENA nohy v miste
// dotyku plna, nebo se tam kryje s dutinou profilu" - to ukaze rozdil
// mezi prurezem TESNE PRED (uvnitr profilu) a TESNE ZA (uvnitr nohy)
// tou spolecnou hranici x=-720.5, na SKUTECNE mesh geometrii (ne boxu).

// VIEW C - prurez 0.3mm UVNITR NOHY (x=-720.8) - Y x Z, skutecna
// dutina/stena nohy tesne za spolecnou hranici s profilem.
const xCutLeg = -720.8;
const viewC = {};
objects.forEach(o => {
  viewC[o.label] = sectionSegments(
    o.obj, new THREE.Vector3(1, 0, 0), new THREE.Vector3(xCutLeg, 0, 0),
    p => [p.z, p.y]
  );
});

// VIEW D - prurez 0.3mm UVNITR PROFILU (x=-720.2), tesne pred jeho
// koncem - Y x Z, skutecny dutý prurez konce profilu pro srovnani s View C.
const xCutProfile = -720.2;
const viewD = {};
objects.forEach(o => {
  viewD[o.label] = sectionSegments(
    o.obj, new THREE.Vector3(1, 0, 0), new THREE.Vector3(xCutProfile, 0, 0),
    p => [p.z, p.y]
  );
});

fs.writeFileSync("/tmp/claude-0/-opt-konfigurator/a0c7cc49-b540-492a-9d17-c27a0dbab25e/scratchpad/corner58_sections.json", JSON.stringify({
  viewA: { cutAxis: "z", cutValue: zCut, xLabel: "X (podel vodorovneho profilu) [mm]", yLabel: "Y (vyska, podel nohy) [mm]", segs: viewA },
  viewB: { cutAxis: "y", cutValue: yCut, xLabel: "X [mm]", yLabel: "Z [mm]", segs: viewB },
  viewC: { cutAxis: "x", cutValue: xCutLeg, xLabel: "Z [mm]", yLabel: "Y (vyska) [mm]", segs: viewC },
  viewD: { cutAxis: "x", cutValue: xCutProfile, xLabel: "Z [mm]", yLabel: "Y (vyska) [mm]", segs: viewD },
}, null, 2));
console.log("hotovo, segmenty A:", Object.fromEntries(Object.entries(viewA).map(([k, v]) => [k, v.length])));
console.log("hotovo, segmenty C (x=%d, uvnitr nohy):", xCutLeg, Object.fromEntries(Object.entries(viewC).map(([k, v]) => [k, v.length])));
console.log("hotovo, segmenty D (x=%d, uvnitr profilu):", xCutProfile, Object.fromEntries(Object.entries(viewD).map(([k, v]) => [k, v.length])));
