const fs = require("fs");
const THREE = require("three");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const KAT = "/opt/konfigurator/webapp/katalog/";
const OBJ7 = KAT + "Object_7.glb";

const T = 30, H = 1180, CAP_H = 260, CUTOUT_H = 395;
// OPRAVA 2026-08-30 (stejna chyba jako v prevod-profilu skriptu): cap
// musi byt kotven k FIXNI vzdalenosti od steny (D), ne k vnitrni hrane
// pricniku (D-T) - jinak by u ruznych T vychazel jiny bod kolize.
const CAP_OFFSET_FROM_WALL = 70;
const WALL_CLEARANCE_ARCH = 349 - 225; // 124mm - fyzicka vule pred podbehem, NEZAVISLA na D

function part(xCenter, yCenter, lengthY, vertical, zCenter, role) {
  return {
    position: [xCenter, yCenter, zCenter],
    quaternion: vertical ? [0, 0, 0, 1] : [0, 0, -0.707107, 0.707107],
    scale: [1, lengthY / 1000, 1],
    role,
  };
}

function buildPlainAtDepth(D) {
  const zCenter = T / 2;
  const rungLo = T, rungHi = D - T;
  const capRight = D - CAP_OFFSET_FROM_WALL, capLeft = capRight - T;
  const skipCap = D <= CAP_OFFSET_FROM_WALL + 2 * T; // <=130
  const parts = [];
  parts.push(part(T / 2, H / 2, H, true, zCenter, "predni-svislice"));
  if (!skipCap) {
    const rungLen = rungHi - rungLo;
    parts.push(part((rungLo + rungHi) / 2, T / 2, rungLen, false, zCenter, "spojnice-dolni"));
    parts.push(part((rungLo + rungHi) / 2, H - CAP_H - T / 2, rungLen, false, zCenter, "spojnice-horni"));
    parts.push(part(D - T / 2, (H - CAP_H) / 2, H - CAP_H, true, zCenter, "zadni-svislice-dolni"));
    parts.push(part((capLeft + capRight) / 2, H - CAP_H / 2, CAP_H, true, zCenter, "cap"));
  } else {
    const rungLen2 = (D - T) - T;
    if (rungLen2 > 0.01) parts.push(part((T + (D - T)) / 2, T / 2, rungLen2, false, zCenter, "spojnice-dolni"));
    parts.push(part(D - T / 2, (H - CAP_H) / 2, H - CAP_H, true, zCenter, "zadni-svislice-dolni"));
  }
  return parts;
}

function buildVyrezAtDepth(D) {
  const zCenter = T / 2;
  const skipColumn = D <= WALL_CLEARANCE_ARCH + 2 * T; // <=184
  const skipCap = D <= CAP_OFFSET_FROM_WALL + 2 * T; // <=130
  const parts = [];
  parts.push(part(T / 2, H / 2, H, true, zCenter, "predni-svislice"));

  if (!skipColumn) {
    // normalni: zuzeny sloupek existuje, kotven k WALL_CLEARANCE_ARCH od steny
    const colRight = D - WALL_CLEARANCE_ARCH, colLeft = colRight - T;
    parts.push(part((colLeft + colRight) / 2, CUTOUT_H / 2, CUTOUT_H, true, zCenter, "sloupek-pred-podbehem"));
    const rungLen0 = colLeft - T;
    if (rungLen0 > 0.01) parts.push(part((T + colLeft) / 2, T / 2, rungLen0, false, zCenter, "spojnice-dolni"));
    // DOPLNENO (Robert 2026-08-31, "na spodní krátký svislý profil posaď
    // shora stejný profil vodorovný jako je nahoře"): sloupek pred
    // podbehem a zadni svislice nad zarezem na sebe navazuji stejnou
    // vyskou (CUTOUT_H), ale RUZNOU plochou (jsou v jinem X) - "cela
    // plocha cela" (Robertovo pravidlo spoju) tak mezi nimi napřímo
    // nejde. Reseni: vodorovny profil POLOZENY SHORA na sloupek (T-styl
    // dosed na horni celo, presne jako "cap" na spojnici jinde v teto
    // noze), ktery se natahne az k zadni svislici a dotkne se JEJI
    // strany. Uzavira tim "otevrenou" strukturu vyrezove nohy.
    if (!skipCap) {
      // OPRAVA (Robert 2026-08-31, "protahni na dotek k prednimu svislemu
      // profilu, ma byt stejne dlouha jako ta horni"): puvodni verze
      // koncila na colLeft (sloupek), nedosahovala az k predni svislici.
      // Ted ma STEJNY rozsah jako "spojnice-horni" (rungLo=T az rungHi=D-T)
      // - cestou pres sloupek pred podbehem na nem porad dosedne shora
      // (cap-styl), jen uz nekonci na jeho hrane.
      const closeLeft = T, closeRight = D - T, closeLen = closeRight - closeLeft;
      if (closeLen > 0.01) {
        parts.push(part((closeLeft + closeRight) / 2, CUTOUT_H + T / 2, closeLen, false, zCenter, "pricka-uzavreni-vyrezu"));
      }
    }
  }
  // horni cast (nad zarezem) a cap - stejna logika jako plna noha, pokud jeste nejsou "skipnuty"
  if (!skipCap) {
    const rungLo = T, rungHi = D - T;
    const rungLen = rungHi - rungLo;
    const capRight = D - CAP_OFFSET_FROM_WALL, capLeft = capRight - T;
    const upperH = (H - CAP_H) - CUTOUT_H;
    parts.push(part(D - T / 2, CUTOUT_H + upperH / 2, upperH, true, zCenter, "zadni-svislice-nad-zarezem"));
    parts.push(part((rungLo + rungHi) / 2, H - CAP_H - T / 2, rungLen, false, zCenter, "spojnice-horni"));
    parts.push(part((capLeft + capRight) / 2, H - CAP_H / 2, CAP_H, true, zCenter, "cap"));
  } else {
    // cap i horni zadni svislice "skipnuty" - predni svislice (jiz plna vyska) je jedina az do H
    // nic dalsiho pridavat netreba (predni-svislice uz pokryva 0..H)
  }
  return parts;
}

function touchOk(parts) {
  const meshes = parts.map(p => {
    const m = parseGlbMesh(OBJ7);
    m.position.set(...p.position); m.quaternion.set(...p.quaternion); m.scale.set(...p.scale);
    m.updateMatrixWorld(true);
    return m;
  });
  // over jen ze zadne dve casti se NEPRESAHUJI (kolize) - u nekterych paru (napr predni vs zadni pri normalnim provozu) se NEDOTYKAJI vubec, to je OK
  let overlapFound = false;
  for (let i = 0; i < meshes.length; i++) {
    for (let j = i + 1; j < meshes.length; j++) {
      const A = new THREE.Box3().setFromObject(meshes[i]), B = new THREE.Box3().setFromObject(meshes[j]);
      const overlapX = Math.min(A.max.x, B.max.x) - Math.max(A.min.x, B.min.x);
      const overlapY = Math.min(A.max.y, B.max.y) - Math.max(A.min.y, B.min.y);
      const overlapZ = Math.min(A.max.z, B.max.z) - Math.max(A.min.z, B.min.z);
      // kolize (zanoreni) = presah na VSECH 3 osach soucasne o vic nez 0.5mm
      if (overlapX > 0.5 && overlapY > 0.5 && overlapZ > 0.5) {
        console.log(`   !!! PRESAH (${parts[i].role} <-> ${parts[j].role}): x=${overlapX.toFixed(1)} y=${overlapY.toFixed(1)} z=${overlapZ.toFixed(1)}`);
        overlapFound = true;
      }
    }
  }
  return !overlapFound;
}

module.exports = { buildPlainAtDepth, buildVyrezAtDepth, touchOk };

const DEPTHS = [326, 300, 250, 184];
const result = {};
for (const D of DEPTHS) {
  console.log(`\n=== D=${D}mm ===`);
  const plain = buildPlainAtDepth(D);
  const vyrez = buildVyrezAtDepth(D);
  console.log(" plna noha:", plain.map(p => p.role).join(", "));
  const plainOk = touchOk(plain);
  console.log(" plna noha bez kolize:", plainOk);
  console.log(" vyrez noha:", vyrez.map(p => p.role).join(", "));
  const vyrezOk = touchOk(vyrez);
  console.log(" vyrez noha bez kolize:", vyrezOk);
  result[D] = { plain, vyrez, plainOk, vyrezOk };
}

fs.writeFileSync("/opt/konfigurator/scripts/tmp_2026-08-30_depth_variants_full.json", JSON.stringify(result, null, 1));
console.log("\nulozeno tmp_2026-08-30_depth_variants_full.json");
