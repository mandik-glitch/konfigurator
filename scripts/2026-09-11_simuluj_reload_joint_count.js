// PRESNA KOPIE algoritmu scene.html pro obnoveni jointCount po nacteni
// sestavy (insertCustomShape + autoRegisterTouchedProfileJoints +
// registerLicJoint) - port do Node, aby se dalo zmerit na realnych datech,
// co by scena SKUTECNE napocitala, kdyby sestavu nekdo otevrel a znovu ulozil.
//
// TRI OTAZKY, ktere tohle ma rozlisit:
//  A) muj/bot10uv joint_count_batch.js: geomJoints (isFlush, PROFIL i
//     UHELNIK na obou stranach) + endcapCount (1/kus) = "puvodni" cislo.
//  B) profil-profil dvojice, ale MERENE STEJNYM (loose) testem jako batch.js.
//  C) profil-profil dvojice, MERENE PRESNE testem ze sceny
//     (autoRegisterTouchedProfileJoints, plna kontejnace na 2 osach,
//     EPS_FACE=0.75, EPS_OVERLAP=0.5) - tohle je to, co scena SKUTECNE
//     obnovi po nacteni, protoze registerLicJoint pocita jointCount JEN
//     pro dve strany, kde OBE jsou isProfilePart (Robert 2026-08-04:
//     "prislusenstvi na profil se NEMA pocitat").
const fs = require("fs");
const path = require("path");
const THREE = require("three");
const { parseGlbMesh } = require("./2026-08-19_glb_real_geometry.js");

const dumpPath = process.argv[2];
const dump = JSON.parse(fs.readFileSync(dumpPath, "utf8"));
const KATALOG_DIR = "/opt/konfigurator/webapp/katalog";

function boxOf(obj) { return new THREE.Box3().setFromObject(obj); }
const geoCache = new Map();
function getGeometry(glbFile) {
  if (!geoCache.has(glbFile)) {
    const file = path.join(KATALOG_DIR, glbFile);
    geoCache.set(glbFile, fs.existsSync(file) ? parseGlbMesh(file).geometry : null);
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

// --- A/B: loose isFlush (presna kopie joint_count_batch.js) -------------
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
function isFlushLoose(r, eps) {
  eps = eps == null ? 0.05 : eps;
  const axes = ["x", "y", "z"];
  const f = axes.filter(ax => Math.abs(r[ax].overlap) <= eps);
  const o = axes.filter(ax => r[ax].overlap > eps);
  return f.length === 1 && o.length === 2;
}

// --- C: presna kopie autoRegisterTouchedProfileJoints (scene.html:7533) -
const AXIS_LETTERS_ARJ = ["x", "y", "z"];
const EPS_FACE_ARJ = 0.75, EPS_OVERLAP_ARJ = 0.5;
function touchingPresneJakoScena(boxA, boxB) {
  for (let axisIdx = 0; axisIdx < 3; axisIdx++) {
    const a = AXIS_LETTERS_ARJ[axisIdx];
    const faceClose =
      Math.abs(boxA.max[a] - boxB.min[a]) < EPS_FACE_ARJ ||
      Math.abs(boxA.min[a] - boxB.max[a]) < EPS_FACE_ARJ;
    if (!faceClose) continue;
    let overlaps = true;
    for (let j = 0; j < 3; j++) {
      if (j === axisIdx) continue;
      const oa = AXIS_LETTERS_ARJ[j];
      const lo = Math.max(boxA.min[oa], boxB.min[oa]);
      const hi = Math.min(boxA.max[oa], boxB.max[oa]);
      const sizeA = boxA.max[oa] - boxA.min[oa];
      const sizeB = boxB.max[oa] - boxB.min[oa];
      const minSize = Math.min(sizeA, sizeB);
      if ((hi - lo) < (minSize - EPS_OVERLAP_ARJ)) { overlaps = false; break; }
    }
    if (overlaps) return true;
  }
  return false;
}

const vysledky = [];
dump.shapes.forEach(shape => {
  const rawParts = shape.parts; // uz bez car_body/razitek (pripraveno drive)
  const entries = [];
  rawParts.forEach(p => {
    const obj = meshFor(p);
    if (!obj) return;
    entries.push({
      part: p, box: boxOf(obj),
      isProfile: !!dump.is_profile[p.part_id],
      isBracket: !!dump.is_bracket[p.part_id],
      isEndcap: !!dump.is_endcap[p.part_id],
    });
  });

  // A) puvodni cislo z batch.js: geomJoints (profil NEBO uhelnik na kterekoli
  // strane, loose isFlush) + endcapCount (1/kus)
  let geomJointsLoose = 0;
  const profileLike = entries.filter(e => e.isProfile || e.isBracket);
  for (let i = 0; i < profileLike.length; i++) {
    for (let j = i + 1; j < profileLike.length; j++) {
      if (!(profileLike[i].isProfile || profileLike[j].isProfile)) continue;
      if (isFlushLoose(touchReport(profileLike[i].box, profileLike[j].box))) geomJointsLoose++;
    }
  }
  const endcapCount = entries.filter(e => e.isEndcap).length;
  const puvodni = geomJointsLoose + endcapCount;

  // B) jen profil-profil, loose isFlush test (izoluje vliv vyrazeni uhelniku/zaslepek)
  const profiles = entries.filter(e => e.isProfile);
  let profilProfilLoose = 0;
  for (let i = 0; i < profiles.length; i++) {
    for (let j = i + 1; j < profiles.length; j++) {
      if (isFlushLoose(touchReport(profiles[i].box, profiles[j].box))) profilProfilLoose++;
    }
  }

  // C) presne to, co scena obnovi po nacteni: jen profil-profil, presny test
  // sceny (plna kontejnace, jine epsilony)
  let profilProfilScena = 0;
  for (let i = 0; i < profiles.length; i++) {
    for (let j = i + 1; j < profiles.length; j++) {
      if (touchingPresneJakoScena(profiles[i].box, profiles[j].box)) profilProfilScena++;
    }
  }

  vysledky.push({
    id: shape.id, name: shape.name,
    A_puvodni_batch: puvodni, geomJointsLoose, endcapCount,
    B_profil_profil_loose: profilProfilLoose,
    C_profil_profil_scena: profilProfilScena,
  });
});

vysledky.forEach(v => {
  console.log(`id=${v.id} "${v.name.slice(0,45)}"`);
  console.log(`   A) puvodni batch.js total: ${v.A_puvodni_batch}  (geomJoints=${v.geomJointsLoose} + endcapCount=${v.endcapCount})`);
  console.log(`   B) jen profil-profil, loose test:   ${v.B_profil_profil_loose}`);
  console.log(`   C) jen profil-profil, presne jako SCENA po nacteni: ${v.C_profil_profil_scena}`);
  console.log(`   -> po otevreni+ulozeni ve scene by total_czk pocitalo s jointCount=${v.C_profil_profil_scena} misto ${v.A_puvodni_batch}`);
});
fs.writeFileSync("/tmp/claude-0/-opt-konfigurator/37d34b49-011f-4fd0-9e15-1bb776dbacfa/scratchpad/reload_simulace.json",
  JSON.stringify(vysledky, null, 2));
