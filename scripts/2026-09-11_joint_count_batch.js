// Davkovy dopocet joint_count/joint_czk pro product_assemblies (bot10,
// zadani bot8 2026-09-11, po potvrzenem dry-runu na 20 sestavach +
// technickych rezech rohu zaslepky). Pravidla (rozhodnuti bot8):
//  - profil<->profil, profil<->uhelnikova spojka: GEOMETRICKY pocet
//    flush dvojic na realne .glb geometrii (touchReport, jako
//    2026-08-19_bookkeeping_validator.js).
//  - profil<->zaslepka: PRESNE 1 spoj/kus, BEZ geometrickeho overovani
//    (potvrzeno rezy - zaslepka vzdy patri jednomu profilu, zadna
//    dvojznacnost).
//  - deska (is_board_material) a eurobox/ostatni: 0, nepocita se.
//
// Vstup: JSON {ids:[...], glb_map, is_profile, is_bracket, is_endcap,
// is_board} - viz scratchpad batch_classification.json + batch_target_ids.json.
// Vystup: JSON {id: {jointCount, boardCount, glbMissing:[...]}} na stdout.
const fs = require("fs");
const path = require("path");
const THREE = require("three");
const { parseGlbMesh } = require("./2026-08-19_glb_real_geometry.js");
const { isStampPart } = require("/opt/konfigurator/webapp/js/scene-geometry-shared.js");

const KATALOG_DIR = "/opt/konfigurator/webapp/katalog";
const [, , dumpPath] = process.argv;
const dump = JSON.parse(fs.readFileSync(dumpPath, "utf8"));

function boxOf(obj) { return new THREE.Box3().setFromObject(obj); }
function touchReport(A, B) {
  const out = {};
  ["x", "y", "z"].forEach(ax => {
    out[ax] = {
      gap: Math.max(A.min[ax] - B.max[ax], B.min[ax] - A.max[ax]),
      overlap: Math.min(A.max[ax], B.max[ax]) - Math.max(A.min[ax], B.min[ax]),
    };
  });
  return out;
}
function isFlush(r, eps) {
  eps = eps == null ? 0.05 : eps;
  const axes = ["x", "y", "z"];
  const f = axes.filter(ax => Math.abs(r[ax].overlap) <= eps);
  const o = axes.filter(ax => r[ax].overlap > eps);
  return f.length === 1 && o.length === 2;
}

// cache: parsovat kazdy .glb soubor jen jednou (geometrie se nemeni,
// jen transform per instance)
const geoCache = new Map();
function getGeometry(glbFile) {
  if (!geoCache.has(glbFile)) {
    const file = path.join(KATALOG_DIR, glbFile);
    if (!fs.existsSync(file)) { geoCache.set(glbFile, null); return null; }
    geoCache.set(glbFile, parseGlbMesh(file).geometry);
  }
  return geoCache.get(glbFile);
}
function meshFor(part) {
  const glbFile = dump.glb_map[part.part_id];
  if (!glbFile) return null;
  const geo = getGeometry(glbFile);
  if (!geo) return null;
  const obj = new THREE.Mesh(geo);
  obj.position.fromArray(part.position);
  obj.quaternion.fromArray(part.quaternion);
  obj.scale.fromArray(part.scale || [1, 1, 1]);
  obj.updateMatrixWorld(true);
  return obj;
}

const results = {};
dump.shapes.forEach(shape => {
  // bot9 2026-09-11: ochranne razitko (logo + vypln drazky) MUSI ven driv,
  // nez se cokoli klasifikuje - logo ma v katalogu length_mm/cross_section_mm
  // (source "profil"), takze by ho isProfilePart oznacilo za profil a
  // isFlush by napocital falesny spoj s profilem, na ktery je logo nalepene
  // (je tam VZDY flush z definice umisteni). Puvodni verze tenhle filtr
  // nemela - nevadilo to na 241 uz zpracovanych sestavach (zadna z nich
  // mela razitka v datech, overeno), ale u techto 28 8-14 razitkovych dilu
  // na sestavu vcetne 334, ktera jde dnes na web. Stejny filtr jako
  // scene.html/2026-09-06_backfill_bom_price.js.
  const rawParts = shape.parts.filter(p => !String(p.part_id).startsWith("car_body_") && !isStampPart(p));
  const glbMissing = new Set();

  const profileLikeParts = rawParts.filter(p => dump.is_profile[p.part_id] || dump.is_bracket[p.part_id]);
  const boxes = [];
  profileLikeParts.forEach(p => {
    const obj = meshFor(p);
    if (!obj) { glbMissing.add(p.part_id); return; }
    boxes.push({ part: p, box: boxOf(obj), isProfile: !!dump.is_profile[p.part_id] });
  });

  let geomJoints = 0;
  for (let i = 0; i < boxes.length; i++) {
    for (let j = i + 1; j < boxes.length; j++) {
      if (!(boxes[i].isProfile || boxes[j].isProfile)) continue;
      const r = touchReport(boxes[i].box, boxes[j].box);
      if (isFlush(r)) geomJoints++;
    }
  }

  const endcapCount = rawParts.filter(p => dump.is_endcap[p.part_id]).length;
  const boardCount = rawParts.filter(p => dump.is_board[p.part_id]).length;
  const jointCount = geomJoints + endcapCount;

  results[shape.id] = {
    jointCount, geomJoints, endcapCount, boardCount,
    partsTotal: shape.parts.length,
    glbMissing: [...glbMissing],
  };
});

console.log(JSON.stringify(results));
