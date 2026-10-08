# Sablonove odvozeni: zmerit frame-relativni normalizovany offset stredu
# DOBRE usazeneho rozku 30x30 (3158, pose z DB) -> pro 40/45 vybrat
# kandidata s nejblizsim offsetem -> overit na celem kvadru stejnou
# sablonou.
from playwright.sync_api import sync_playwright
import json
BASE = "http://127.0.0.1:8090"
SC = "/tmp/claude-0/-opt-konfigurator/b336267e-a1f5-4ea8-b332-89232804d6ac/scratchpad/"
PWD = open(SC+"testpwd.txt").read().strip()

JS = """async (args) => {
  const [refPart, refProf, refSize, targets] = args;
  const ov = document.getElementById("helpModalOverlay");
  if (ov) ov.classList.remove("open");
  const box=(o)=>new THREE.Box3().setFromObject(o);
  const mkProf=(id,deg)=>new Promise(res=>{const prof=CATALOG.find(p=>p.id===id);loader.load(prof.file,g=>{const obj=g.scene.clone(true);applyPartMaterial(obj,prof.layer,null);const en={part:prof,object3d:obj,connectorsLocal:computeConnectorsLocal(obj)};obj.quaternion.copy(baseQuaternion(deg));obj.position.set(0,0,0);obj.updateMatrixWorld(true);scene.add(obj);placed.push(en);res(en);});});
  const mkAcc=(id)=>new Promise(res=>{const part=CATALOG.find(p=>p.id===id);loader.load(part.file,g=>{const obj=g.scene.clone(true);applyPartMaterial(obj,part.layer,null);const en={part,object3d:obj,connectorsLocal:computeConnectorsLocal(obj,{wallSnap:!isProfilePart(part),geoFaces:Array.isArray(part.geo_faces)?part.geo_faces:undefined})};obj.updateMatrixWorld(true);scene.add(obj);res(en);});});

  // geometrie rohu (P/C, osa, dWall, mx) - sdilene
  function cornerGeom(A, C0) {
    A.object3d.updateMatrixWorld(true); C0.object3d.updateMatrixWorld(true);
    const bA=box(A.object3d), bB=box(C0.object3d);
    let dA=Infinity,dB=Infinity;
    worldConnectorsOf(A).forEach(c=>{if(c.kind==="end")dA=Math.min(dA,bB.distanceToPoint(c.point));});
    worldConnectorsOf(C0).forEach(c=>{if(c.kind==="end")dB=Math.min(dB,bA.distanceToPoint(c.point));});
    const P = dA<=dB ? C0 : A; const C = P===A ? C0 : A;
    const eIdx=[];P.connectorsLocal.forEach((cn,i)=>{if(cn.kind==="end")eIdx.push(i);});
    const wP=worldConnectorsOf(P);
    const axisA=wP[eIdx[0]].point.clone();
    const vFull=wP[eIdx[1]].point.clone().sub(axisA);
    const L=vFull.length(); const axisDir=vFull.clone().normalize();
    const cB=box(C.object3d); let mn=Infinity,mx=-Infinity;
    for(let xi=0;xi<2;xi++)for(let yi=0;yi<2;yi++)for(let zi=0;zi<2;zi++){const c2=new THREE.Vector3(xi?cB.max.x:cB.min.x,yi?cB.max.y:cB.min.y,zi?cB.max.z:cB.min.z);const t=c2.sub(axisA).dot(axisDir);if(t<mn)mn=t;if(t>mx)mx=t;}
    const cc=cB.getCenter(new THREE.Vector3());
    const tC=cc.clone().sub(axisA).dot(axisDir);
    const foot=axisA.clone().addScaledVector(axisDir,tC);
    const dWall=cc.clone().sub(foot).normalize();
    return {P, C, axisA, axisDir, L, mn, mx, dWall};
  }
  function normOffset(obj, g, side, size) {
    const F = uhelnikCornerFrameQuat(g.axisDir, side, g.dWall);
    const cornerPt = g.axisA.clone().addScaledVector(g.axisDir, side === 1 ? g.mx : g.mn);
    obj.updateMatrixWorld(true);
    const cen = box(obj).getCenter(new THREE.Vector3());
    const rel = cen.sub(cornerPt).applyQuaternion(F.clone().invert());
    return [rel.x/size, rel.y/size, rel.z/size];
  }

  // 1) SABLONA z dobreho 30x30
  clearAll();
  let A=await mkProf(refProf,0), C0=await mkProf(refProf,90);
  attachEntryToParent(C0,A,baseQuaternion(90),null,0);
  let g = cornerGeom(A, C0);
  const refCat = CATALOG.find(p=>p.id===refPart);
  const refAcc = await mkAcc(refPart);
  // polozit pres uhelnikAutPlaceOne s pozou z DB (presna produkcni cesta)
  const okRef = uhelnikAutPlaceOne(refAcc, g.P, g.dWall, g.axisA, g.axisDir, g.L, g.mx, 1, {a:g.P,b:g.C});
  if (!okRef) return {err:"referencni 30x30 nelze polozit"};
  placed.push(refAcc);
  const template = normOffset(refAcc.object3d, g, 1, refSize);
  const results = {template: template.map(v=>+v.toFixed(4)), targets: []};

  // 2) pro kazdy cil: brute-force kandidatu, vyber dle sablony
  for (const [dst, profId, size, override] of targets) {
    clearAll();
    A=await mkProf(profId,0); C0=await mkProf(profId,90);
    attachEntryToParent(C0,A,baseQuaternion(90),null,0);
    g = cornerGeom(A, C0);
    const acc = await mkAcc(dst);
    const cands = uhelnikAutPoseCandidates(acc, g.P, g.dWall);
    let best=null, bestD=Infinity, bestOff=null;
    for (const cnd of cands) {
      applyConnectionCandidate(cnd, acc, g.P, {skipBookkeeping:true});
      if (!uhelnikAutAlignAxial(acc, g.axisA, g.axisDir, g.L, g.mx, 1)) continue;
      applyAttachTeachOffset(acc, cnd.childFaceConnIdx);
      const off = normOffset(acc.object3d, g, 1, size);
      const d = Math.hypot(off[0]-template[0], off[1]-template[1], off[2]-template[2]);
      if (d < bestD) { bestD = d; best = cnd; bestOff = off; }
    }
    scene.remove(acc.object3d);
    if (!best || bestD > 0.15) { results.targets.push({dst, err:"zadny kandidat nesedi sablone", bestD:+bestD.toFixed(3), bestOff}); continue; }
    const F = uhelnikCornerFrameQuat(g.axisDir, 1, g.dWall);
    const qRel = F.clone().invert().multiply(best.option.quat);
    const pose = {face: best.childFaceConnIdx, q:[qRel.x,qRel.y,qRel.z,qRel.w]};
    // 3) overeni na celem kvadru sablonou
    CATALOG.find(p=>p.id===dst).uhelnik_pose = pose;
    clearAll();
    buildKvadrShape(profId);
    await new Promise(r=>setTimeout(r,3200));
    if (override) runUhelnikAut(override); else runUhelnikAut(null);
    await new Promise(r=>setTimeout(r,3200));
    const es = placed.filter(e=>e.part&&e.part.id===dst);
    let good=0; const dists=[];
    es.forEach(e=>{
      const tag=e.autoUhelnikFor; if(!tag) return;
      const gg = cornerGeom(tag.a===e.attachedTo.profEntry?tag.a:tag.b, tag.a===e.attachedTo.profEntry?tag.b:tag.a);
      const side = e.autoUhelnikSide || 1;
      const off = normOffset(e.object3d, gg, side, size);
      const d = Math.hypot(off[0]-template[0], off[1]-template[1], off[2]-template[2]);
      dists.push(+d.toFixed(3));
      if (d < 0.15) good++;
    });
    results.targets.push({dst, pose, bestD:+bestD.toFixed(4), kvadrPlaced: es.length, kvadrGood: good, dists: dists.slice(0,6)});
  }
  clearAll();
  return results;
}"""

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    ctx = b.new_context(viewport={"width":1200,"height":900})
    pg = ctx.new_page()
    errors=[]
    pg.on("pageerror", lambda e: errors.append(str(e)))
    ctx.request.post(BASE+"/api/auth/login", data=json.dumps({"email":"bot8-test-scene@test.local","password":PWD}), headers={"Content-Type":"application/json"})
    pg.goto(BASE+"/scene.html", wait_until="domcontentloaded", timeout=30000)
    pg.wait_for_function("typeof placed !== 'undefined' && Array.isArray(CATALOG) && CATALOG.length > 0", timeout=30000)
    out = pg.evaluate(JS, ["product_3158", "Object_7", 30, [
        ["product_3176", "Object_11", 40, "__ROZEK__"],
        ["product_3205", "Object_2", 45, "__ROZEK__"],
    ]])
    print(json.dumps(out, ensure_ascii=False, indent=1))
    with open(SC+"rozek_template_results.json","w") as f: json.dump(out,f)
    print("JS errors:", errors[:3] if errors else "none")
    b.close()
