const THREE = require("three");
const shared = require("/opt/konfigurator/webapp/js/scene-geometry-shared.js");
const { baseQuaternion, computeConnectorsLocal, crossAxisHalfWidthTowardDirection,
        worldConnectorsOf, applyLengthScale } = shared;
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");

function boxOf(e) { return new THREE.Box3().setFromObject(e.object3d); }
let anyBad = false;

function testProfile(glbPath, w, label) {
  console.log(`\n=== ${label} (w=${w}) ===`);
  function mkEntry() {
    const obj = parseGlbMesh(glbPath);
    return { object3d: obj, connectorsLocal: computeConnectorsLocal(obj) };
  }

  // --- buildLLengthShape PO OPRAVE (s pullbackem = zub-fix) ---
  {
    const entry1 = mkEntry();
    entry1.object3d.quaternion.copy(baseQuaternion(0));
    entry1.object3d.position.set(0, 0, 0);
    entry1.object3d.updateMatrixWorld(true);
    const L1 = entry1.connectorsLocal[0].point.distanceTo(entry1.connectorsLocal[1].point);
    applyLengthScale(entry1, (L1 + w) / L1, 0);

    const entry2 = mkEntry();
    const quat2 = baseQuaternion(90);
    entry2.object3d.quaternion.copy(quat2);
    entry2.object3d.position.set(0, 0, 0);
    entry2.object3d.updateMatrixWorld(true);
    const childDir = entry2.connectorsLocal[1].point.clone().sub(entry2.connectorsLocal[0].point).applyQuaternion(quat2).normalize();
    const pcw = worldConnectorsOf(entry1)[0];
    const ph = crossAxisHalfWidthTowardDirection(entry1.connectorsLocal, entry1.object3d.quaternion, childDir);
    const target = pcw.point.clone().addScaledVector(childDir, ph);
    // >>> OPRAVA (zub-fix, stejny princip jako placeAttached u ctverce) <<<
    const childHalf2 = crossAxisHalfWidthTowardDirection(entry2.connectorsLocal, quat2, pcw.normal);
    target.addScaledVector(pcw.normal, -childHalf2);
    // >>> konec opravy <<<
    const rl = entry2.connectorsLocal[0].point.clone().applyQuaternion(quat2);
    entry2.object3d.position.copy(target.clone().sub(rl));
    entry2.object3d.updateMatrixWorld(true);
    const L2 = entry2.connectorsLocal[0].point.distanceTo(entry2.connectorsLocal[1].point);
    applyLengthScale(entry2, (L2 - w) / L2, 0);

    const b1 = boxOf(entry1), b2 = boxOf(entry2);
    const overhang = b1.min.z - b2.min.z;
    const covered = Math.min(b1.max.z, b2.max.z) - Math.max(b1.min.z, b2.min.z);
    const gapX = Math.max(b1.min.x - b2.max.x, b2.min.x - b1.max.x);
    const len1 = b1.max.z - b1.min.z, len2 = b2.max.x - b2.min.x;
    const ok = Math.abs(overhang) < 0.01 && Math.abs(covered - w) < 0.01 && Math.abs(gapX) < 0.01;
    if (!ok) anyBad = true;
    console.log(`  L_length: presah=${overhang.toFixed(4)} kryti=${covered.toFixed(4)}/${w} gapX=${gapX.toFixed(4)} delky=${len1.toFixed(1)}/${len2.toFixed(1)} ${ok ? "OK" : "FAIL"}`);
  }

  // --- buildLLengthReversedShape PO OPRAVE ---
  {
    function virtualEntry(cl) { return { connectorsLocal: cl, object3d: new THREE.Object3D() }; }
    function localCorners8(cl) {
      const center = cl[0].point.clone().add(cl[1].point).multiplyScalar(0.5);
      const lv = cl[0].point.clone().sub(center);
      const cr = cl.crossAxesLocal;
      const out = [];
      [1,-1].forEach(sL => [1,-1].forEach(sA => [1,-1].forEach(sB => {
        out.push(center.clone().addScaledVector(lv, sL).addScaledVector(cr[0].dir, sA*cr[0].halfWidth).addScaledVector(cr[1].dir, sB*cr[1].halfWidth));
      })));
      return out;
    }
    function assemblyOuterCornerMin(parts) {
      const min = new THREE.Vector3(Infinity, Infinity, Infinity);
      parts.forEach(p => localCorners8(p.connectorsLocal).forEach(c => {
        min.min(c.clone().multiply(p.scale || new THREE.Vector3(1,1,1)).applyQuaternion(p.quat).add(p.pos));
      }));
      return min;
    }
    function outerCornerOfLengthJoin(cl, tq, cq, w2) {
      const th = virtualEntry(cl);
      th.object3d.quaternion.copy(tq); th.object3d.position.set(0,0,0); th.object3d.updateMatrixWorld(true);
      const LL = cl[0].point.distanceTo(cl[1].point);
      if (w2 && LL) applyLengthScale(th, (LL+w2)/LL, 0);
      const ch = virtualEntry(cl);
      ch.object3d.quaternion.copy(cq); ch.object3d.position.set(0,0,0); ch.object3d.updateMatrixWorld(true);
      const cd = cl[1].point.clone().sub(cl[0].point).applyQuaternion(cq).normalize();
      const pw2 = worldConnectorsOf(th)[0];
      const ph2 = crossAxisHalfWidthTowardDirection(cl, th.object3d.quaternion, cd);
      const tg = pw2.point.clone().addScaledVector(cd, ph2);
      const rl2 = cl[0].point.clone().applyQuaternion(cq);
      ch.object3d.position.copy(tg.clone().sub(rl2)); ch.object3d.updateMatrixWorld(true);
      const LL2 = cl[0].point.distanceTo(cl[1].point);
      if (w2 && LL2) applyLengthScale(ch, (LL2-w2)/LL2, 0);
      return assemblyOuterCornerMin([
        { connectorsLocal: cl, quat: tq, pos: th.object3d.position, scale: th.object3d.scale },
        { connectorsLocal: cl, quat: cq, pos: ch.object3d.position, scale: ch.object3d.scale },
      ]);
    }
    const entry2 = mkEntry();
    const quat2 = baseQuaternion(90), quat1c = baseQuaternion(0);
    entry2.object3d.quaternion.copy(quat2);
    const tc = outerCornerOfLengthJoin(entry2.connectorsLocal, quat1c, quat2, w);
    const nc = outerCornerOfLengthJoin(entry2.connectorsLocal, quat2, quat1c, w);
    entry2.object3d.position.copy(tc.clone().sub(nc));
    entry2.object3d.updateMatrixWorld(true);
    const L2 = entry2.connectorsLocal[0].point.distanceTo(entry2.connectorsLocal[1].point);
    applyLengthScale(entry2, (L2 + w) / L2, 0);

    const entry1 = mkEntry();
    const quat1 = baseQuaternion(0);
    entry1.object3d.quaternion.copy(quat1);
    entry1.object3d.position.set(0,0,0);
    entry1.object3d.updateMatrixWorld(true);
    const cd1 = entry1.connectorsLocal[1].point.clone().sub(entry1.connectorsLocal[0].point).applyQuaternion(quat1).normalize();
    const pw = worldConnectorsOf(entry2)[0];
    const ph1 = crossAxisHalfWidthTowardDirection(entry2.connectorsLocal, entry2.object3d.quaternion, cd1);
    const tg1 = pw.point.clone().addScaledVector(cd1, ph1);
    // >>> OPRAVA (zub-fix) <<<
    const childHalf1 = crossAxisHalfWidthTowardDirection(entry1.connectorsLocal, quat1, pw.normal);
    tg1.addScaledVector(pw.normal, -childHalf1);
    // >>> konec opravy <<<
    const rl1 = entry1.connectorsLocal[0].point.clone().applyQuaternion(quat1);
    entry1.object3d.position.copy(tg1.clone().sub(rl1));
    entry1.object3d.updateMatrixWorld(true);
    const L1b = entry1.connectorsLocal[0].point.distanceTo(entry1.connectorsLocal[1].point);
    applyLengthScale(entry1, (L1b - w) / L1b, 0);

    const b1 = boxOf(entry1), b2 = boxOf(entry2);
    // dil2 podel X (pruchozi), dil1 podel Z (pripojeny) - presah dilu 1 za konec dilu 2 v ose X
    const overhang = b2.min.x - b1.min.x;
    const covered = Math.min(b1.max.x, b2.max.x) - Math.max(b1.min.x, b2.min.x);
    const gapZ = Math.max(b1.min.z - b2.max.z, b2.min.z - b1.max.z);
    const ok = Math.abs(overhang) < 0.01 && Math.abs(covered - w) < 0.01 && Math.abs(gapZ) < 0.01;
    if (!ok) anyBad = true;
    console.log(`  L_length_rev: presah=${overhang.toFixed(4)} kryti=${covered.toFixed(4)}/${w} gapZ=${gapZ.toFixed(4)} ${ok ? "OK" : "FAIL"}`);
  }
}

testProfile("/opt/konfigurator/webapp/katalog/profil_30x30_uzavreny.glb", 30, "profil_30x30_uzavreny (pivot-offset)");
testProfile("/opt/konfigurator/webapp/katalog/profil_35x35.glb", 35, "profil_35x35");
testProfile("/opt/konfigurator/webapp/katalog/profil_20x20.glb", 20, "profil_20x20");
console.log(`\n${anyBad ? "FAIL" : "VSE OK"}`);
