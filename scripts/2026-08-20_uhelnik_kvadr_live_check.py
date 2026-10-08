# End-to-end z CERSTVE stranky (pozy uz jen z DB): kvadr 40 i 45,
# uhelniky i rozky, sablonove overeni vsech 24 rohu + screenshoty.
from playwright.sync_api import sync_playwright
import json
BASE = "http://127.0.0.1:8090"
SC = "/tmp/claude-0/-opt-konfigurator/b336267e-a1f5-4ea8-b332-89232804d6ac/scratchpad/"
PWD = open(SC+"testpwd.txt").read().strip()
CASES = [
  ("Object_11", None,        "product_3207", "final_uhelnik40.png"),
  ("Object_11", "__ROZEK__", "product_3176", "final_rozek40.png"),
  ("Object_2",  None,        "product_3216", "final_uhelnik45.png"),
  ("Object_2",  "__ROZEK__", "product_3205", "final_rozek45.png"),
]
JS = """async (args) => {
  const [profId, override, dst, size, template] = args;
  const ov = document.getElementById("helpModalOverlay");
  if (ov) ov.classList.remove("open");
  const box=(o)=>new THREE.Box3().setFromObject(o);
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
  function normOffset(obj, g, side, sz) {
    const F = uhelnikCornerFrameQuat(g.axisDir, side, g.dWall);
    const cornerPt = g.axisA.clone().addScaledVector(g.axisDir, side === 1 ? g.mx : g.mn);
    obj.updateMatrixWorld(true);
    const cen = box(obj).getCenter(new THREE.Vector3());
    const rel = cen.sub(cornerPt).applyQuaternion(F.clone().invert());
    return [rel.x/sz, rel.y/sz, rel.z/sz];
  }
  clearAll();
  buildKvadrShape(profId);
  await new Promise(r=>setTimeout(r,3200));
  if (override) runUhelnikAut(override); else runUhelnikAut(null);
  await new Promise(r=>setTimeout(r,3200));
  const es = placed.filter(e=>e.part&&e.part.id===dst);
  let good=0; let worst=0;
  es.forEach(e=>{
    const tag=e.autoUhelnikFor; if(!tag) return;
    const gg = cornerGeom(tag.a===e.attachedTo.profEntry?tag.a:tag.b, tag.a===e.attachedTo.profEntry?tag.b:tag.a);
    const side = e.autoUhelnikSide || 1;
    const off = normOffset(e.object3d, gg, side, size);
    const d = Math.hypot(off[0]-template[0], off[1]-template[1], off[2]-template[2]);
    if (d < 0.15) good++; else worst = Math.max(worst, d);
  });
  camera.position.set(1500,1400,1600);
  camera.lookAt(new THREE.Vector3(500,500,500));
  if (typeof controls!=="undefined"&&controls.target){controls.target.set(500,500,500);controls.update();}
  renderer.render(scene,camera);
  return {dst, placed: es.length, good, worst:+worst.toFixed(3)};
}"""
TEMPLATE = [0.4884, 0.9116, 0]
with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    ctx = b.new_context(viewport={"width":1200,"height":900})
    pg = ctx.new_page()
    ctx.request.post(BASE+"/api/auth/login", data=json.dumps({"email":"bot8-test-scene@test.local","password":PWD}), headers={"Content-Type":"application/json"})
    pg.goto(BASE+"/scene.html", wait_until="domcontentloaded", timeout=30000)
    pg.wait_for_function("typeof placed !== 'undefined' && Array.isArray(CATALOG) && CATALOG.length > 0", timeout=30000)
    # sablona pro uhelniky se lisi od rozku - spocitat z 30x30 uhelniku (3045):
    uh_template = pg.evaluate("""async () => {
      const box=(o)=>new THREE.Box3().setFromObject(o);
      const mkProf=(id,deg)=>new Promise(res=>{const prof=CATALOG.find(p=>p.id===id);loader.load(prof.file,g=>{const obj=g.scene.clone(true);applyPartMaterial(obj,prof.layer,null);const en={part:prof,object3d:obj,connectorsLocal:computeConnectorsLocal(obj)};obj.quaternion.copy(baseQuaternion(deg));obj.position.set(0,0,0);obj.updateMatrixWorld(true);scene.add(obj);placed.push(en);res(en);});});
      const mkAcc=(id)=>new Promise(res=>{const part=CATALOG.find(p=>p.id===id);loader.load(part.file,g=>{const obj=g.scene.clone(true);applyPartMaterial(obj,part.layer,null);const en={part,object3d:obj,connectorsLocal:computeConnectorsLocal(obj,{wallSnap:!isProfilePart(part),geoFaces:Array.isArray(part.geo_faces)?part.geo_faces:undefined})};obj.updateMatrixWorld(true);scene.add(obj);res(en);});});
      clearAll();
      const A=await mkProf("Object_7",0), C0=await mkProf("Object_7",90);
      attachEntryToParent(C0,A,baseQuaternion(90),null,0);
      A.object3d.updateMatrixWorld(true);C0.object3d.updateMatrixWorld(true);
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
      const acc=await mkAcc("product_3045");
      const ok=uhelnikAutPlaceOne(acc,P,dWall,axisA,axisDir,L,mx,1,{a:P,b:C});
      if(!ok)return null;
      const F=uhelnikCornerFrameQuat(axisDir,1,dWall);
      const cornerPt=axisA.clone().addScaledVector(axisDir,mx);
      acc.object3d.updateMatrixWorld(true);
      const cen=box(acc.object3d).getCenter(new THREE.Vector3());
      const rel=cen.sub(cornerPt).applyQuaternion(F.clone().invert());
      return [rel.x/30, rel.y/30, rel.z/30];
    }""")
    print("uhelnik template:", uh_template)
    for profId, override, dst, shot in CASES:
        size = 40 if profId == "Object_11" else 45
        tpl = TEMPLATE if override else uh_template
        out = pg.evaluate(JS, [profId, override, dst, size, tpl])
        pg.wait_for_timeout(400)
        pg.screenshot(path=SC+shot)
        print(json.dumps(out, ensure_ascii=False))
    b.close()
