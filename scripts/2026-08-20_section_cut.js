// Presny 2D rez: rovina kolmo na osu profilu skrz stred dilu.
// Vystup: JSON segmenty {profil:[[x1,y1,x2,y2],...], dil:[...]} v mm
// souradnicich roviny rezu (u=napric stenou, v=svisle).
const path = require("path");
const THREE = require("/opt/konfigurator/node_modules/three");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const fs = require("fs");

const [,, partGlb, mode, depthStr, outFile] = process.argv;
const depth = parseFloat(depthStr);

// profil Object_11 v identite: delka podel ktere osy? zmerime.
const prof = parseGlbMesh("/opt/konfigurator/webapp/katalog/Object_11.glb");
prof.updateMatrixWorld(true);
const pb = new THREE.Box3().setFromObject(prof);
const ps = pb.getSize(new THREE.Vector3());
const axIdxP = ps.x>=ps.y&&ps.x>=ps.z?0:(ps.y>=ps.z?1:2);
const axesL = ["x","y","z"];
const axL = axesL[axIdxP];
const crossAxes = axesL.filter(a=>a!==axL);
// stena: max na prvni pricne ose (u), svisla = druha pricna (v)
const uAx = crossAxes[0], vAx = crossAxes[1];
const wallCoord = pb.max[uAx];

// dil: osa kolecka = nejkratsi rozmer
const acc = parseGlbMesh("/opt/konfigurator/webapp/katalog/" + partGlb);
acc.updateMatrixWorld(true);
const ab = new THREE.Box3().setFromObject(acc);
const as = ab.getSize(new THREE.Vector3());
const axIdxA = as.x<=as.y&&as.x<=as.z?0:(as.y<=as.z?1:2);
const localAxle = new THREE.Vector3(axIdxA===0?1:0, axIdxA===1?1:0, axIdxA===2?1:0);
// orientace C: osa kolecka podel vAx (napric stenou svisle? C = osa podel
// steny kolmo na profil = vAx pro tento rig)
const targetDir = new THREE.Vector3(vAx==="x"?1:0, vAx==="y"?1:0, vAx==="z"?1:0);
const q = new THREE.Quaternion().setFromUnitVectors(localAxle, targetDir);
acc.quaternion.copy(q);
acc.position.set(0,0,0);
acc.updateMatrixWorld(true);
// stred na stred steny (stred profilu podelne, stred steny pricne)
const ab2 = new THREE.Box3().setFromObject(acc);
const cen = ab2.getCenter(new THREE.Vector3());
const wallCenter = new THREE.Vector3();
wallCenter[axL] = (pb.min[axL]+pb.max[axL])/2;
wallCenter[uAx] = wallCoord;
wallCenter[vAx] = (pb.min[vAx]+pb.max[vAx])/2;
acc.position.add(wallCenter.clone().sub(cen));
acc.updateMatrixWorld(true);
// zasunuti: min proj dilu na uAx = wallCoord - depth
const ab3 = new THREE.Box3().setFromObject(acc);
acc.position[uAx] += (wallCoord - depth) - ab3.min[uAx];
acc.updateMatrixWorld(true);

// rovina rezu: axL = konstanta (stred dilu)
const ab4 = new THREE.Box3().setFromObject(acc);
const cutAt = ab4.getCenter(new THREE.Vector3())[axL];

function sectionSegments(obj) {
  const segs = [];
  const vA=new THREE.Vector3(), vB=new THREE.Vector3(), vC=new THREE.Vector3();
  obj.traverse(n => {
    if (!n.isMesh || !n.geometry || !n.geometry.attributes.position) return;
    const pos = n.geometry.attributes.position, index = n.geometry.index;
    const triCount = index ? index.count/3 : pos.count/3;
    for (let t=0;t<triCount;t++) {
      const ia=index?index.getX(t*3):t*3, ib=index?index.getX(t*3+1):t*3+1, ic=index?index.getX(t*3+2):t*3+2;
      vA.fromBufferAttribute(pos,ia).applyMatrix4(n.matrixWorld);
      vB.fromBufferAttribute(pos,ib).applyMatrix4(n.matrixWorld);
      vC.fromBufferAttribute(pos,ic).applyMatrix4(n.matrixWorld);
      const pts=[];
      const tri=[[vA,vB],[vB,vC],[vC,vA]];
      tri.forEach(([p1,p2])=>{
        const d1=p1[axL]-cutAt, d2=p2[axL]-cutAt;
        if ((d1>0)!==(d2>0)) {
          const s=d1/(d1-d2);
          pts.push([p1[uAx]+s*(p2[uAx]-p1[uAx]), p1[vAx]+s*(p2[vAx]-p1[vAx])]);
        }
      });
      if (pts.length===2) segs.push([pts[0][0],pts[0][1],pts[1][0],pts[1][1]]);
    }
  });
  return segs;
}
const out = {profil: sectionSegments(prof), dil: sectionSegments(acc),
             wall: wallCoord, depth, mode,
             profilRange: {u:[pb.min[uAx],pb.max[uAx]], v:[pb.min[vAx],pb.max[vAx]]}};
fs.writeFileSync(outFile, JSON.stringify(out));
console.log(partGlb, mode, depth, "profil segs:", out.profil.length, "dil segs:", out.dil.length);

// POZNAMKA (bot8): tenhle nastroj vznikl na Robertovu vyzvu "neni to videt
// dobre, takove uceni je k nicemu kdyz mi nedas presne podklady ke
// schvalovani" - 3D/wireframe nahledy nestacily. Vystupni JSON kresli
// scratchpadovy matplotlib skript (mm mrizka, kota zasunuti) - viz
// AGENTS_LOG 2026-08-20. Pro dalsi dily uprav orientaci/hloubku dle
// schvalovaneho pripadu.
