"use strict";
// Offline generator. Millimetres: X=depth/short side, Y=long side, Z=height.
// Published dimensions are constraints. Appearance parameters are photo-derived
// reconstruction choices, NOT measured technical dimensions or mating CAD.
const fs=require('fs'),path=require('path');
const THREE=require('./nahled-modely/vendor/three.min.js');
const ROOT=__dirname, OUT=path.join(ROOT,'nahled-modely-v5');
const catalog=JSON.parse(fs.readFileSync(path.join(ROOT,process.env.KUFRIKY_BUILD_SKU?'kufriky.json':'zdroje/doladeni-v5/pred-kufriky.json')));
const research=JSON.parse(fs.readFileSync(path.join(ROOT,'zdroje/doladeni-v3/fotografie.json')));
const organizerPhotos=JSON.parse(fs.readFileSync(path.join(ROOT,'zdroje/doladeni-v5/fotografie.json')));
const reviews=JSON.parse(fs.readFileSync(path.join(ROOT,'zdroje/doladeni-v3/review.json')));
const fontSource=JSON.parse(fs.readFileSync(path.join(ROOT,'zdroje/pismo-v2/helvetiker_regular.typeface.json'))),font=new THREE.Font(fontSource);
const M=[
 {name:'Černé tělo – vizuální barva',pbrMetallicRoughness:{baseColorFactor:[.035,.04,.045,1],metallicFactor:0,roughnessFactor:.72}},
 {name:'Červené detaily – vizuální barva',pbrMetallicRoughness:{baseColorFactor:[.68,.008,.025,1],metallicFactor:0,roughnessFactor:.5}},
 {name:'Kovové detaily – vizuální vzhled',pbrMetallicRoughness:{baseColorFactor:[.57,.60,.63,1],metallicFactor:.75,roughnessFactor:.3}},
 {name:'Průhledné víko – vizuální vzhled',alphaMode:'BLEND',doubleSided:true,pbrMetallicRoughness:{baseColorFactor:[.72,.8,.84,.24],metallicFactor:0,roughnessFactor:.19}},
 {name:'Těsnění a pneumatika – vizuální vzhled',pbrMetallicRoughness:{baseColorFactor:[.012,.015,.018,1],metallicFactor:0,roughnessFactor:.95}},
 {name:'Vnitřní panely – vizuální vzhled',pbrMetallicRoughness:{baseColorFactor:[.075,.08,.09,1],metallicFactor:0,roughnessFactor:.85}}
];
function outline(d,l,r){
 const s=new THREE.Shape(),a=d/2,b=l/2; r=Math.min(r,a*.95,b*.95);
 s.moveTo(-a+r,-b);s.lineTo(a-r,-b);s.quadraticCurveTo(a,-b,a,-b+r);
 s.lineTo(a,b-r);s.quadraticCurveTo(a,b,a-r,b);s.lineTo(-a+r,b);
 s.quadraticCurveTo(-a,b,-a,b-r);s.lineTo(-a,-b+r);s.quadraticCurveTo(-a,-b,-a+r,-b);return s;
}
function extrusion(d,l,h,r,inner=null,bevel=0){
 const b=Math.min(bevel,h*.22,d*.025,l*.025);
 const s=outline(d-2*b,l-2*b,Math.max(.1,r-b));
 if(inner){const hole=outline(inner[0],inner[1],inner[2]);s.holes.push(new THREE.Path(hole.getPoints(5)));}
 const g=new THREE.ExtrudeGeometry(s,{depth:h-2*b,steps:1,curveSegments:5,bevelEnabled:b>0,bevelSegments:2,bevelSize:b,bevelThickness:b});
 g.translate(0,0,b);g.computeVertexNormals();return g;
}
class Product{
 constructor(record,sku){this.r=record;this.sku=sku;this.compact=['4932471065','4932471723'].includes(sku);this.d=record.outer.mm[this.compact?'length':'width'];this.l=record.outer.mm[this.compact?'width':'length'];this.h=record.outer.mm.height;this.parts=[];this.features=new Set();this.notes=[];this.equations=[];}
 add(name,g,mat=0,group='fixed',xyz=[0,0,0],rot=[0,0,0],extras={}){
  const matrix=new THREE.Matrix4().compose(new THREE.Vector3(...xyz),new THREE.Quaternion().setFromEuler(new THREE.Euler(...rot)),new THREE.Vector3(1,1,1));
  g.applyMatrix4(matrix);this.parts.push({name,g,mat,group,extras});return this.parts.at(-1);
 }
 solid(name,d,l,h,r,xyz,mat=0,group='fixed',rot=[0,0,0]){return this.add(name,extrusion(d,l,h,r,null,Math.min(h*.12,1.2)),mat,group,xyz,rot);}
 ring(name,d,l,h,r,inner,xyz,mat=0,group='fixed',rot=[0,0,0]){return this.add(name,extrusion(d,l,h,r,inner),mat,group,xyz,rot);}
 tube(name,a,b,r,mat=0,group='fixed'){
  a=new THREE.Vector3(...a);b=new THREE.Vector3(...b);const v=b.clone().sub(a),g=new THREE.CylinderGeometry(r,r,v.length(),12,1);
  g.applyMatrix4(new THREE.Matrix4().makeRotationFromQuaternion(new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0,1,0),v.normalize())));g.translate(...a.add(b).multiplyScalar(.5).toArray());return this.add(name,g,mat,group);
 }
 shell(name,d,l,z0,z1,id,il,ih,cx=0,mat=0,group='fixed'){
  const floor=z1-ih;if(floor<=z0)throw Error('Interior cannot fit '+this.sku);
  this.solid(name+'-dno',d,l,floor-z0,Math.min(d,l)*.025,[cx,0,z0],mat,group);
  const wall=extrusion(d,l,ih,Math.min(d,l)*.025,[id,il,Math.min(id,il)*.025]);
  // Taper the external lower edge while retaining the cavity ring. The taper
  // is an appearance reconstruction, not a measured draft angle.
  // Draft angle is unknown; retain the sourced cavity rather than deform it.
  wall.computeVertexNormals();this.add(name+'-duta-stena',wall,mat,group,[cx,0,floor]);
  this.features.add('dutý vnitřní prostor');
  this.equations.push(`${name}: z_dno = ${z1.toFixed(3)} − ${ih.toFixed(3)} = ${floor.toFixed(3)} mm; dutina Š × L × V = ${id} × ${il} × ${ih} mm.`);
  return {d,l,cx,z0,z1,id,il,ih,floor};
 }
 feet(d=this.d,l=this.l){
  const h=Math.min(this.h*.055,12),sx=d*.13,sy=l*.13;
  for(const x of [-1,1])for(const y of [-1,1])this.solid(`patka-${x}-${y}`,sx,sy,h,Math.min(sx,sy)*.15,[x*(d/2-sx/2),y*(l/2-sy/2),0],0);
  this.features.add('nožky / podstava');return h;
 }
 docking(z,d=this.d,l=this.l,group='lid',bottom=false){
  const support=this.parts.find(a=>/^(telo-dno|skrin-dno|prepravka-dno|pojezdove-telo-dno|vyklopny-organizer-zadni-panel)$/.test(a.name));
  let dh=Math.min(this.h*.045,7);if(bottom&&support){support.g.computeBoundingBox();dh=Math.max(dh,support.g.boundingBox.min.z-z+1);}
  const sx=d*.16,sy=l*.26;
  for(const x of [-1,0,1])for(const y of [-1,1]){
   const px=x*d*.28,py=y*l*.235;
   if(bottom){
    this.solid(`PACKOUT-spodni-patka-${x}-${y}`,sx,sy,dh,3,[px,py,z],0,group);
    this.solid(`PACKOUT-spodni-zub-${x}-${y}`,sx*.30,sy*.7,dh*.4,1.5,[px+sx*.35,py,z],0,group);
   }else{
    this.ring(`PACKOUT-horni-drazka-${x}-${y}`,sx,sy,dh,3,[sx*.68,sy*.72,2],[px,py,z],0,group);
    this.solid(`PACKOUT-horni-zamek-${x}-${y}`,sx*.16,sy*.72,dh*.30,1,[px+sx*.40,py,z+dh*.65],0,group);
   }
  }
  if(!bottom){
   for(const y of [-l*.41,l*.41])this.solid('PACKOUT-lista-'+y,d*.87,l*.025,dh*.5,1,[0,y,z],0,group);
   this.ring('viko-prolis-obvod',d*.94,l*.94,dh*.35,6,[d*.90,l*.90,5],[0,0,z],0,group);
   this.solid('PACKOUT-cervene-uvolneni',d*.06,l*.065,dh*.35,1,[d*.18,0,z],1,group);
  }
  this.features.add('šest spojovacích pozic a uložené lišty; profil spojů není kótovaný');
 }
 label(front,z,span,mat=1,group='fixed'){
  for(const [text,size,dz] of [['MILWAUKEE',span*.055,0],['PACKOUT',span*.036,-span*.045]]){
   const g=new THREE.TextGeometry(text,{font,size,height:.35,curveSegments:2,bevelEnabled:false});g.computeBoundingBox();const width=g.boundingBox.max.x-g.boundingBox.min.x;g.translate(-width/2,0,0);
   this.add('oznaceni-'+text,g,mat,group,[front,0,z+dz],[Math.PI/2,Math.PI/2,0],{visual_label:'Textová připomínka značky; nereprodukuje přesný tvar loga.'});
  }
 }
 latch(front,y,z,h,group='lid'){
  const w=this.l*.07,t=Math.min(this.d*.015,6);
  this.solid('zapadka-zaklad-'+y,t,w,h,w*.08,[front-t*.5,y,z],0,'fixed');
  this.solid('zapadka-cervena-'+y,t*.7,w*.78,h*.64,w*.06,[front+t*.35,y,z],1,'fixed');
  for(let i=0;i<4;i++)this.solid('zapadka-zebro-'+y+'-'+i,t*.24,w*.10,h*.28,.5,[front+t*.81,y+(i-1.5)*w*.17,z+h*.34],1,'fixed');
  const x=front+t*.7;
  this.tube('zapadka-kov-levy-'+y,[x,y-w*.5,z+h*.28],[x,y-w*.5,z+h*.95],1.35,2);
  this.tube('zapadka-kov-pravy-'+y,[x,y+w*.5,z+h*.28],[x,y+w*.5,z+h*.95],1.35,2);
  this.tube('zapadka-kov-mustek-'+y,[x,y-w*.5,z+h*.95],[x,y+w*.5,z+h*.95],1.35,2);
  this.features.add('západky a kovové spony');
 }
 frontHandle(front,z,span,high,red=true){
  const thick=high*.20,t=Math.min(this.d*.015,6);
  this.ring('drzadlo-otevreny-uchop',span,high,t,high*.22,[span-thick*2,high-thick*2,high*.16],[front,0,z],red?1:0,'fixed',[Math.PI/2,Math.PI/2,0]);
  for(const y of [-1,1])this.solid('drzadlo-kotveni-'+y,t*2,thick,high*.8,2,[front-t/2,y*(span/2-thick/2),z-high*.4],0);
  this.features.add('otevřené držadlo s kotvením do těla');
 }
 raisedHandle(z,span,high,cx=0,red=false){
  const t=high*.16;
  this.ring('vyklopne-drzadlo',span,high,Math.min(this.d*.035,12),high*.16,[span-2*t,high-2*t,high*.12],[cx,0,z+high/2],red?1:0,'handle',[Math.PI/2,Math.PI/2,0]);
  this.features.add('výklopné držadlo');
 }
 ribs(d,l,z0,z1,cx=0,metal=false){
  const ht=z1-z0,r=Math.min(d,l)*.035;
  for(const sy of [-1,1])for(const sx of [-1,1]){
   this.solid(`roh-ochrana-${sx}-${sy}`,r,r,ht,r*.25,[cx+sx*(d/2-r/2),sy*(l/2-r/2),z0],0);
   if(metal){
    this.solid(`roh-kov-${sx}-${sy}`,r*.32,r*.32,ht*.82,r*.08,[cx+sx*(d/2-r*.16),sy*(l/2-r*.16),z0+ht*.09],2);
    for(const end of [0,1])this.solid(`roh-kov-kotveni-${sx}-${sy}-${end}`,r*.6,r*.6,ht*.06,2,[cx+sx*(d/2-r*.32),sy*(l/2-r*.32),z0+end*ht*.94],0);
   }
  }
  for(const sy of [-1,1])for(const f of [-.22,.22])this.solid(`bok-zebro-${sy}-${f}`,d*.022,l*.012,ht*.76,1,[cx+f*d,sy*(l/2-l*.006),z0+ht*.06],0);
  this.features.add('zaoblené ochrany rohů s uloženými kovovými tyčemi a žebra');
 }
 foldedHandle(z,span,cx=0){
  const depth=this.d*.13,t=depth*.22;
  this.ring('vyklopne-drzadlo-sklopene',depth,span,5,depth*.25,[depth-2*t,span-2*t,depth*.15],[cx,0,z],0,'handle');
  for(let i=0;i<18;i++)this.solid('drzadlo-vroubkovani-'+i,depth*.20,span*.015,1,.2,[cx+depth*.37,(i-8.5)*span*.04,z+5],4,'handle');
  this.features.add('výklopné držadlo ve sklopené poloze');
 }
 bins(shell,kind){
  const cols=kind==='compact'?1:2, half=shell.il/cols, gap=Math.min(shell.il,shell.id)*.018;
  const heights=[.28,.44,.28];let x=-shell.id/2+gap;
  let count=0;
  for(let row=0;row<heights.length;row++){
   const dx=(shell.id-2*gap)*heights[row], small=row!==1,n=small?2:1;
   for(let col=0;col<cols;col++)for(let k=0;k<n;k++){
    const ly=half/n-gap,bx=dx-gap,by=-shell.il/2+col*half+(k+.5)*half/n;
    const bottom=shell.floor,ht=shell.z1-bottom-1.2;
    const t=Math.min(bx,ly)*.035;
    this.solid('prihradka-'+count+'-dno',bx,ly,t,3,[shell.cx+x+dx/2,by,bottom],1,'bins');
    this.ring('prihradka-'+count+'-duta-stena',bx,ly,ht-t,3,[bx-2*t,ly-2*t,2],[shell.cx+x+dx/2,by,bottom+t],1,'bins');
    count++;
   }
   x+=dx;
  }
  this.binCount=count;this.features.add('vyjímatelné duté přihrádky');
 }
 clearLid(shell,z,kind){
  const h=this.h-z,r=Math.min(shell.d,shell.l)*.03;
  this.ring('viko-ciry-okraj',shell.d,shell.l,h*.6,r,[shell.d*.91,shell.l*.95,r*.7],[shell.cx,0,z],3,'lid');
  this.solid('viko-ciry-panel',shell.d*.92,shell.l*.96,h*.08,r*.6,[shell.cx,0,z+h*.60],3,'lid');
  // Each raised sealing window is aligned to the actual bin grid.
  const cols=kind==='compact'?1:2,half=shell.il/cols,gap=Math.min(shell.il,shell.id)*.018;
  const rows=[.28,.44,.28];let x=-shell.id/2+gap;
  for(let row=0;row<rows.length;row++){
   const dx=(shell.id-2*gap)*rows[row],n=row!==1?2:1;
   for(let col=0;col<cols;col++)for(let k=0;k<n;k++){
    const bx=dx-gap,ly=half/n-gap,by=-shell.il/2+col*half+(k+.5)*half/n;
    this.ring(`viko-tesnici-prolis-${row}-${col}-${k}`,bx,ly,h*.27,4,[bx*.89,ly*.90,3],[shell.cx+x+dx/2,by,z+h*.66],3,'lid');
   }x+=dx;
  }
  this.solid('viko-stredni-vyztuha',shell.id,this.l*.065,h*.08,2,[shell.cx,0,z+h*.92],3,'lid');
  this.features.add('průhledné víko s prolisy nad přihrádkami');
 }
 wheel(x,y,diam,width,axis='y'){
  const first=this.parts.length,r=diam/2,z=r;
  this.add('kolo-pneumatika-'+y,new THREE.CylinderGeometry(r,r,width,48,1),4,'fixed',[x,y,z]);
  this.add('kolo-naboj-'+y,new THREE.CylinderGeometry(r*.68,r*.68,width,32,1),0,'fixed',[x,y,z]);
  for(const sign of [-1,1]){
   this.add('kolo-osa-'+y+'-'+sign,new THREE.CylinderGeometry(r*.105,r*.105,2,16,1),2,'fixed',[x,y+sign*(width/2-1),z]);
   for(let i=0;i<10;i++){
    const a=i*Math.PI/5,th=r*.047;
    this.tube('kolo-paprsek-'+y+'-'+sign+'-'+i,[x+Math.cos(a)*r*.16,y+sign*(width/2-th),z+Math.sin(a)*r*.16],[x+Math.cos(a)*r*.65,y+sign*(width/2-th),z+Math.sin(a)*r*.65],th,0);
   }
  }
  if(axis==='x')for(const part of this.parts.slice(first))part.g.rotateZ(Math.PI/2);
  this.measuredFeatures??=[];this.measuredFeatures.push({kind:'wheel',diameter_mm:diam,axis,source_url:this.r.hardware.source_url});
  this.features.add('kruhová kola bez dodatečného natažení, náboje a paprsky');
 }
 anchorBottomSupports(){
  // Measure the actual bottom contact plane, including its rounded/bevelled
  // perimeter. Feet never use the larger catalogue envelope as their frame.
  const floor=this.parts.find(a=>/^(telo-dno|skrin-dno|prepravka-dno|pojezdove-telo-dno|vyklopny-organizer-zadni-panel)$/.test(a.name));
  if(!floor)throw Error('Missing bottom support '+this.sku);
  floor.g.computeBoundingBox();const fb=floor.g.boundingBox,center=fb.getCenter(new THREE.Vector3()),size=fb.getSize(new THREE.Vector3());
  const a=floor.g.getAttribute('position'),xy=[];
  for(let i=0;i<a.count;i++)if(Math.abs(a.getZ(i)-fb.min.z)<.001)xy.push([a.getX(i),a.getY(i)]);
  const hull=this.floorContourOverride||convexHull(xy);if(hull.length<3)throw Error('Missing floor contact contour '+this.sku);
  for(const part of this.parts){
   if(/^(patka-|pojezdova-patka-)/.test(part.name)){
    part.g.computeBoundingBox();const old=part.g.boundingBox,oc=old.getCenter(new THREE.Vector3());
    const signs=[Math.sign(oc.x),Math.sign(oc.y)];
    const sx=/^patka-/.test(part.name)?size.x*.13:old.max.x-old.min.x;
    const sy=/^patka-/.test(part.name)?size.y*.13:old.max.y-old.min.y;
    const ranges=[[signs[0]<0?fb.min.x:fb.max.x-sx,signs[0]<0?fb.min.x+sx:fb.max.x],[signs[1]<0?fb.min.y:fb.max.y-sy,signs[1]<0?fb.min.y+sy:fb.max.y]];
    let contour=hull;
    for(let axis=0;axis<2;axis++)for(let end=0;end<2;end++)contour=clipPolygon(contour,axis,ranges[axis][end],end===0);
    if(contour.length<3)throw Error('Empty foot footprint '+this.sku+' '+part.name);
    const sh=new THREE.Shape();sh.moveTo(...contour[0]);for(const p of contour.slice(1))sh.lineTo(...p);sh.closePath();
    const g=new THREE.ExtrudeGeometry(sh,{depth:fb.min.z,bevelEnabled:false,steps:1,curveSegments:5});
    g.computeVertexNormals();part.g=g;part.extras={...part.extras,support_component:floor.name,footprint_constraint:'actual_floor_contact_contour',allowed_overhang_mm:0};
   }else if(/^PACKOUT-spodni-(patka|zub)-/.test(part.name)){
    part.g.translate(center.x,center.y,0);part.extras={...part.extras,support_component:floor.name,footprint_constraint:'actual_floor_contact_contour',allowed_overhang_mm:0};
   }
  }
  this.equations.push(`Podstava: skutečné dno X = [${fb.min.x.toFixed(3)}, ${fb.max.x.toFixed(3)}], Y = [${fb.min.y.toFixed(3)}, ${fb.max.y.toFixed(3)}]; střed = (${center.x.toFixed(3)}, ${center.y.toFixed(3)}) mm. Všechny spodní prvky jsou kotvené k tomuto dnu; výška patek = z_min dna = ${fb.min.z.toFixed(3)} mm.`);
  this.features.add('podstavné plošky uvnitř skutečného zaobleného obrysu dna');
 }
 write(){
  this.anchorBottomSupports();
  // No axis fitting. Known cavities and wheel diameters retain their size.
  // Compact boxes face along the long catalogue axis, unlike the wide family.
  if(this.compact)for(const part of this.parts)part.g.rotateZ(Math.PI/2);
  const box=new THREE.Box3();for(const part of this.parts){part.g.computeBoundingBox();box.union(part.g.boundingBox);}
  const size=box.getSize(new THREE.Vector3()),target=[this.r.outer.mm.width,this.r.outer.mm.length,this.h];
  const actual=size.toArray();if(Math.max(...actual.map((v,i)=>Math.abs(v-target[i])))>.01){console.log(this.parts.filter(a=>a.g.boundingBox.min.z < -.001||a.g.boundingBox.max.z>this.h+.001).map(a=>[a.name,a.g.boundingBox.min.toArray(),a.g.boundingBox.max.toArray()]));throw Error('Unfitted bounds '+this.sku+': '+actual+' expected '+target);}
  const center=box.getCenter(new THREE.Vector3());
  for(const part of this.parts)part.g.translate(-center.x,-center.y,-center.z);
  const fit=[1,1,1];
  const review=reviews.records.find(r=>r.sku.includes(this.sku));
  const photos=organizerPhotos.records.find(r=>r.sku===this.sku)?.photos||research.records.find(r=>r.id===this.r.id).photos;
  const metadata={sku:this.sku,units:'mm',catalog_axes:{X:'width',Y:'length',Z:'height'},kind:'photo_reconstructed_product',is_product_geometry:true,
   detail_level:'realny_tvar',detail_label:'Reálný tvar · rekonstrukce z fotografií',physical_accuracy_verified:false,physical_tolerance_mm:null,
   source_url:this.r.outer.source_url,photo_url:this.r.image.source_url,photo_page_url:this.r.image.page_url,
   dimension_constraints_mm:this.r.outer.mm,features:[...this.features],bin_count:this.binCount||0,
   envelope_fit:{before_min_mm:box.min.toArray(),before_max_mm:box.max.toArray(),axis_scale:fit,applied:false},
   bottom_supports:{constraint:'actual_floor_contact_contour',allowed_overhang_mm:0,physical_accuracy_verified:false},front_axis:this.compact?'positive_y':'positive_x',hinge_axis:this.compact?'x':'y',review:this.r.review||review.public,photo_sources:photos.map(p=>({url:p.url,page_url:p.page_url,kind:p.kind})),
   measured_features:this.measuredFeatures||[],
   limitation:'Kóty obálky jsou ze zdroje. Nekótované detaily a skryté spoje jsou vizuální rekonstrukce, ne přesný výrobní CAD. Kompatibilita PACKOUT a tolerance fyzického kusu neověřeny.',
   label_font_license:fontSource.original_font_information.license_description};
  const glb=encode(this.parts,metadata);if(glb.length>=3e6)throw Error('File over 3MB '+this.sku);
  const filename=this.sku+'.glb';fs.writeFileSync(path.join(ROOT,'modely',filename),glb);fs.writeFileSync(path.join(OUT,'modely',filename),glb);
  const report={...metadata,bytes:glb.length,parts:this.parts.map(p=>({name:p.name,group:p.group,material:p.mat,...p.extras})),equations:this.equations};
  fs.writeFileSync(path.join(ROOT,'mereni-tvar-v5',this.sku+'.json'),JSON.stringify(report,null,2)+'\n');
  return {sku:this.sku,file:'modely/'+filename,bytes:glb.length,part_count:this.parts.length,bin_count:this.binCount||0,features:metadata.features,detail_level:'realny_tvar',physical_accuracy_verified:false};
 }
}
function convexHull(points){
 const sorted=[...new Map(points.map(p=>[p.join(','),p])).values()].sort((a,b)=>a[0]-b[0]||a[1]-b[1]);
 const cross=(a,b,c)=>(b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]);
 const lower=[],upper=[];
 for(const p of sorted){while(lower.length>1&&cross(lower.at(-2),lower.at(-1),p)<=1e-8)lower.pop();lower.push(p);}
 for(const p of sorted.slice().reverse()){while(upper.length>1&&cross(upper.at(-2),upper.at(-1),p)<=1e-8)upper.pop();upper.push(p);}
 lower.pop();upper.pop();return lower.concat(upper);
}
function clipPolygon(points,axis,value,keepGreater){
 const inside=p=>keepGreater?p[axis]>=value-1e-8:p[axis]<=value+1e-8,out=[];
 for(let i=0;i<points.length;i++){
  const a=points[i],b=points[(i+1)%points.length],ia=inside(a),ib=inside(b);
  if(ia)out.push(a);
  if(ia!==ib){const t=(value-a[axis])/(b[axis]-a[axis]);const p=[a[0]+t*(b[0]-a[0]),a[1]+t*(b[1]-a[1])];p[axis]=value;out.push(p);}
 }
 return out;
}
function encode(parts,metadata){
 const doc={asset:{version:'2.0',generator:'John – vlastní fotografická rekonstrukce, mm',extras:metadata},scene:0,scenes:[{nodes:parts.map((_,i)=>i)}],nodes:[],meshes:[],materials:M,buffers:[{}],bufferViews:[],accessors:[]},chunks=[];let offset=0;
 function accessor(array,type,componentType,target,min,max){
  const b=Buffer.from(array.buffer,array.byteOffset,array.byteLength),v=doc.bufferViews.length;
  doc.bufferViews.push({buffer:0,byteOffset:offset,byteLength:b.length,target});chunks.push(b);offset+=b.length;
  const pad=(-offset)&3;if(pad){chunks.push(Buffer.alloc(pad));offset+=pad;}
  const a={bufferView:v,componentType,count:array.length/(type==='VEC3'?3:1),type};if(min)a.min=min;if(max)a.max=max;
  return doc.accessors.push(a)-1;
 }
 for(const p of parts){
  let g=p.g;if(g.index)g=g.toNonIndexed();
  const a=g.getAttribute('position').array,n=g.getAttribute('normal').array,positions=[],normals=[],indices=[],unique=new Map();let removed=0;
  // Weld identical positions/normals, retain hard edges; drop zero-area faces.
  for(let i=0;i<a.length;i+=9){
   const ab=new THREE.Vector3(a[i+3]-a[i],a[i+4]-a[i+1],a[i+5]-a[i+2]),ac=new THREE.Vector3(a[i+6]-a[i],a[i+7]-a[i+1],a[i+8]-a[i+2]);
   if(ab.cross(ac).lengthSq()<1e-12){removed++;continue;}
   for(let j=i;j<i+9;j+=3){const key=[a[j],a[j+1],a[j+2],n[j],n[j+1],n[j+2]].join(',');let k=unique.get(key);if(k===undefined){k=positions.length/3;unique.set(key,k);positions.push(a[j],a[j+1],a[j+2]);normals.push(n[j],n[j+1],n[j+2]);}indices.push(k);}
  }
  if(!indices.length)throw Error('Empty component '+p.name);
  const pos=new Float32Array(positions),nor=new Float32Array(normals),idx=positions.length/3<65536?new Uint16Array(indices):new Uint32Array(indices);
  const box=new THREE.Box3();for(let i=0;i<pos.length;i+=3)box.expandByPoint(new THREE.Vector3(pos[i],pos[i+1],pos[i+2]));
  const pi=accessor(pos,'VEC3',5126,34962,box.min.toArray(),box.max.toArray()),ni=accessor(nor,'VEC3',5126,34962),ii=accessor(idx,'SCALAR',idx instanceof Uint16Array?5123:5125,34963);
  const mesh=doc.meshes.length;doc.meshes.push({name:p.name,primitives:[{attributes:{POSITION:pi,NORMAL:ni},indices:ii,material:p.mat}]});
  doc.nodes.push({name:p.name,mesh,extras:{component:p.group,evidence:'photo_reconstruction',removed_degenerate_faces:removed,...p.extras}});
 }
 doc.buffers[0].byteLength=offset;const bin=Buffer.concat(chunks),json=Buffer.from(JSON.stringify(doc));const jt=Buffer.concat([json,Buffer.alloc((-json.length)&3,32)]);
 const head=Buffer.alloc(20);head.writeUInt32LE(0x46546c67,0);head.writeUInt32LE(2,4);head.writeUInt32LE(28+jt.length+bin.length,8);head.writeUInt32LE(jt.length,12);head.writeUInt32LE(0x4e4f534a,16);
 const bh=Buffer.alloc(8);bh.writeUInt32LE(bin.length,0);bh.writeUInt32LE(0x004e4942,4);return Buffer.concat([head,jt,bh,bin]);
}

// Appearance proportions below describe the inspected photo topology. They are
// not manufacturer dimensions. Sourced cavities and wheel diameters are retained
// without fitting. Unknown wall/radius values remain explicitly unverified.
function cavity(p){
 const q=p.r.inner[0]?.mm;
 if(!q)return null;
 return {id:p.compact?q.length:q.width,il:p.compact?q.width:q.length,ih:q.height};
}
function supportedLid(p,sh,lidH,clear=false,kind='case'){
 const z=sh.z1,d=sh.d,l=sh.l,cx=sh.cx;
 // The rim meets the body; panel, sealing fields and ribs all meet that rim.
 p.ring('viko-nosny-okraj',d,l,lidH*.65,7,[d-12,l-12,4],[cx,0,z],clear?3:0,'lid');
 p.solid('viko-panel',d-8,l-8,Math.max(lidH*.20,lidH*.50-7),6,[cx,0,z+lidH*.50],clear?3:0,'lid');
 if(clear){
  const cols=kind==='compact'?1:2,rows=[.28,.44,.28],gap=3;
  const id=sh.id,il=sh.il;let xx=-id/2;
  for(let row=0;row<3;row++){
   const dx=id*rows[row],n=row===1?1:2;
   for(let col=0;col<cols;col++)for(let k=0;k<n;k++){
    const ly=il/cols/n-gap,yy=-il/2+(col+(k+.5)/n)*il/cols;
    p.ring(`viko-prolis-${row}-${col}-${k}`,dx-gap,ly,lidH*.30,3,[dx-gap-6,ly-6,2],[cx+xx+dx/2,yy,z+lidH*.70],3,'lid');
   }xx+=dx;
  }
 }else{
  const first=p.parts.length;
  p.docking(z+lidH-7,d,l,'lid');
  for(const part of p.parts.slice(first))part.g.translate(cx,0,0);
  // An actual panel extends to the highest source plane, so no invisible
  // extremal vertices are needed and all top lock lips have a supporting face.
  for(const y of [-l*.40,l*.40])p.solid('viko-nosne-zebro-'+y,d*.86,5,lidH*.30,1,[cx,y,z+lidH*.70],0,'lid');
 }
 for(const y of [-l*.26,l*.26]){
  const x=cx-d/2+4;
  p.tube('pant-vika-'+y,[x,y-12,z],[x,y+12,z],3,0,'lid');
  p.solid('pant-vika-kotveni-'+y,9,27,9,2,[x+1,y,z-5],0,'fixed');
 }
 p.features.add('víko s propojeným okrajem, panelem a panty');
}
function fixedHandle(p,front,z,span,high,red=true){
 const t=5,th=high*.20;
 p.ring('drzadlo-otevreny-uchop',span,high,t,high*.23,[span-2*th,high-2*th,high*.16],[front,0,z],red?1:0,'fixed',[Math.PI/2,Math.PI/2,0]);
 for(const y of [-1,1])p.solid('drzadlo-kotveni-'+y,t*2,th+2,high,2,[front-t*.5,y*(span/2-th/2),z-high/2],0);
 p.features.add('čelní úchop s kotvením');
}
function sideHandles(p,bodyD,bodyL,z){
 const span=bodyD*.35,high=34,t=5;
 for(const y of [-1,1]){
  p.ring('bocni-drzadlo-'+y,span,high,t,6,[span-14,high-14,4],[0,y*(bodyL/2-t),z],1,'fixed',[-y*Math.PI/2,0,0]);
  for(const x of [-1,1])p.solid('bocni-drzadlo-kotveni-'+y+'-'+x,12,12,high,3,[x*(span/2-6),y*(bodyL/2-6),z-high/2],0);
 }
 p.features.add('boční rukojeti s uchycením');
}
function lowTray(p,sh,group='tray'){
 const h=Math.min(sh.ih*.25,42),d=sh.id*.30,l=sh.il*.90,z=sh.z1-h;
 p.solid('vlozka-dno',d,l,2,3,[sh.cx-sh.id*.31,0,z],5,group);
 p.ring('vlozka-dute-steny',d,l,h-2,3,[d-6,l-6,2],[sh.cx-sh.id*.31,0,z+2],5,group);
 // The tray rests on two actual ledges rather than hanging inside a cavity.
 for(const y of [-1,1])p.solid('vlozka-operna-lista-'+y,sh.id,(sh.il-l)/2+4,3,1,[sh.cx,y*(sh.il/2+l/2)/2,z-3],0);
 p.features.add('dutá vyjímatelná vložka s opěrnými lištami');
}
function standard(p,kind='case'){
 const org=['slim','organiser','compact','deep'].includes(kind),q=cavity(p);
 const f=p.feet(),reserve=org?Math.min(p.d*.04,16):Math.min(p.d*.025,12);
 const bd=p.d-reserve,cx=-reserve/2,lh=Math.min(org?Math.min(p.h*.17,15):Math.min(p.h*.12,30),q?p.h-f-q.ih-2:Infinity),top=p.h-lh;
 const id=q?.id||bd*.83,il=q?.il||p.l*.86,ih=q?.ih||top-f-8;
 if(id>=bd||il>=p.l||top-ih<=f)throw Error('Published cavity does not fit '+p.sku);
 const sh=p.shell('telo',bd,p.l,f,top,id,il,ih,cx);
 p.ribs(bd,p.l,f,top,cx,!org&&!p.compact);
 // The photographed cases have substantial front corner guards, with the
 // latch/handle face recessed between them. Reconstruct those visible guards
 // separately; source envelope must not be set by displaced feet.
 const corner=Math.min(bd,p.l)*.035;
 for(const y of [-1,1])p.solid('celo-roh-ochrana-'+y,corner+reserve,corner,top-f,corner*.25,[p.d/2-(corner+reserve)/2,y*(p.l/2-corner/2),f],0);
 p.features.add('čelní ochrany rohů; podstava neurčuje vnější délku těla');
 if(org&&kind!=='deep')p.bins(sh,kind);
 if(kind==='deep'){
  // Open hero 2/3 and application 2/3 show a long rear compartment plus
  // three front compartments: not ten removable red cups.
  const split=sh.cx-sh.id*.24;
  p.solid('hluboky-zadni-dlouhy-delic',3,sh.il,sh.ih*.87,1,[split,0,sh.floor],0,'bins');
  for(const y of [-sh.il/6,sh.il/6])p.solid('hluboky-cerveny-delic-'+y,sh.id*.73,3,sh.ih*.88,1,[sh.cx+sh.id*.125,y,sh.floor],1,'bins');
  p.binCount=4;p.features.add('zadní dlouhá přihrádka a tři přední oddíly podle otevřených snímků');
 }
 supportedLid(p,sh,lh,org,kind);
 const lhatch=org?Math.min(p.h*.57,74):Math.min(p.h*.21,72),front=cx+bd/2;
 if(p.sku==='4932471723'){
  // The compact case has a single wide latch on its short face.
  const first=p.parts.length;p.latch(front,0,Math.min(top-lhatch*.9,p.h-lhatch),lhatch);
  for(const part of p.parts.slice(first)){
   const a=part.g.getAttribute('position');for(let i=0;i<a.count;i++)a.setY(i,a.getY(i)*2.3);part.g.computeVertexNormals();
  }
 }else for(const y of [-p.l*.32,p.l*.32])p.latch(front,y,Math.min(top-lhatch*.9,p.h-lhatch),lhatch);
 if(!['4932471723','4932501784','4932478162'].includes(p.sku))fixedHandle(p,front+2,top-lhatch*.50,p.l*(org?.31:.33),org?Math.min(33,p.h*.32):33,kind!=='slim'&&kind!=='compact');
 if(['4932501784','4932478162'].includes(p.sku))sideHandles(p,bd,p.l,top-56);
 if(['4932471723','4932464079'].includes(p.sku)){
  const span=p.l*.63,depth=p.d*.125,t=depth*.20,z=p.h-5;
  p.ring('vyklopne-drzadlo-sklopene',depth,span,5,5,[depth-2*t,span-2*t,3],[cx,0,z],0,'handle');
  for(const y of [-1,1])p.solid('drzadlo-horni-cep-'+y,depth,12,8,2,[cx,y*(span/2-6),z-3],0,'lid');
  p.features.add('sklopené horní držadlo s čepy');
 }
 if(!org&&!['4932471723','4932499703','4932499704'].includes(p.sku))lowTray(p,sh);
 if(p.sku==='4932471723'){
  p.solid('kompakt-vnitrni-delic',sh.id,3,sh.ih*.65,1,[cx,0,sh.floor],5,'tray');p.features.add('vnitřní dělič podle otevřených fotografií');
 }
 p.docking(0,bd,p.l,'fixed',true);
 if(['slim','compact'].includes(kind)){
  // Hero front views show a small release tab in the handle, not the large
  // red loop inherited from the taller case family.
  const handleH=Math.min(33,p.h*.32),handleZ=top-lhatch*.50;
  p.solid('PACKOUT-celni-odjistovaci-tlacitko',3,12,handleH*.15,1,[front+1.5,0,handleZ-handleH*.45],1);
 }else{
  const releaseZ=kind==='organiser'?top-lhatch*.50:Math.min(top*.25,40);
  p.ring('zamek-packout-cerveny',24,29,3,8,[12,16,5],[front,0,releaseZ],1,'fixed',[0,Math.PI/2,0]);
 }
 if(!org)p.label(front+2,sh.floor+ih*.5,p.l*.50);
 if(['4932499703','4932499704'].includes(p.sku)){
  const panD=id*.83,panL=il*.90,z=sh.floor;
  p.solid('profesni-panel-dno',panD,panL,3,5,[cx+id*.05,0,z],5,'tray');
  p.ring('profesni-panel-cerveny-ram',panD,panL,3,5,[panD-7,panL-7,3],[cx+id*.05,0,z+3],1,'tray');
  for(let i=0;i<5;i++){
   const d=panD*.22,l=panL*.135,x=cx-panD*.20,y=-panL*.34+i*panL*.17,h=ih*.34;
   p.solid('profesni-kapsa-'+i+'-dno',d,l,2,2,[x,y,z+6],5,'tray');
   p.ring('profesni-kapsa-'+i+'-duta-stena',d,l,h,2,[d-4,l-4,1],[x,y,z+8],5,'tray');
  }
  p.ring('profesni-viko-cerveny-ram',bd*.85,p.l*.87,2,5,[bd*.85-6,p.l*.87-6,3],[cx,0,top+2],1,'lid');
  p.features.add('vnitřní rámy a skutečně duté kapsy; rozdíly profesních vložek nedoložené');
 }
 p.measuredFeatures??=[];if(q)p.measuredFeatures.push({kind:'cavity',dimensions_mm:{width:q.id,length:q.il,height:q.ih},source_url:p.r.inner[0].source_url,component:'telo-duta-stena',local_axes:p.compact?'compact_rotated':'normal'});
}
function crate(p){
 const q=cavity(p),f=p.h-q.ih,tx=(p.d-q.id)/2,ty=(p.l-q.il)/2;
 p.solid('prepravka-dno',p.d,p.l,f,7,[0,0,0],0);
 function wall(name,span,height,t,xyz,rot){
  const s=outline(span,height,6),hole=outline(span*.43,height*.13,5);
  s.holes.push(new THREE.Path(hole.getPoints(5).map(v=>v.add(new THREE.Vector2(0,height*.35)))));
  p.add(name,new THREE.ExtrudeGeometry(s,{depth:t,bevelEnabled:false,curveSegments:5,steps:1}),0,'fixed',xyz,rot);
 }
 const ht=p.h-f;
 wall('prepravka-celo-s-otvorem',p.l,ht,tx,[p.d/2-tx,0,f+ht/2],[Math.PI/2,Math.PI/2,0]);
 wall('prepravka-zada-s-otvorem',p.l,ht,tx,[-p.d/2,0,f+ht/2],[Math.PI/2,Math.PI/2,0]);
 for(const y of [-1,1])wall('prepravka-bok-s-otvorem-'+y,p.d,ht,ty,[0,y*p.l/2+(y<0?ty:0),f+ht/2],[Math.PI/2,0,0]);
 p.ribs(p.d,p.l,0,p.h);
 for(const z of [.14,.37,.70,.95]){
  for(const sy of [-1,1])p.solid('prepravka-podelne-zebro-'+sy+'-'+z,p.d,5,4,1,[0,sy*(p.l/2-2.5),p.h*z],0);
  for(const sx of [-1,1])p.solid('prepravka-celni-zebro-'+sx+'-'+z,5,p.l,4,1,[sx*(p.d/2-2.5),0,p.h*z],0);
 }
 p.label(p.d/2-1,p.h*.62,p.l*.5);
 p.ring('prepravka-cerveny-odjistovac',25,30,3,8,[14,17,5],[p.d/2-3,0,p.h*.21],1,'fixed',[0,Math.PI/2,0]);
 p.docking(0,p.d,p.l,'fixed',true);
 p.features.add('otevřená přepravka; držadla jsou průchozí otvory ve stěnách');
 p.measuredFeatures=[{kind:'cavity',dimensions_mm:{width:q.id,length:q.il,height:q.ih},source_url:p.r.inner[0].source_url}];
}
function drawer(p,rolling=false){
 const q=cavity(p),f=rolling?25:p.feet(),top=p.h-15;
 const wheelD=rolling?228:0,ww=rolling?Math.min((p.l-q.il)/2-12,48):0;
 const bd=p.d,bl=rolling?p.l-ww*2:p.l;
 const id=q.id,il=q.il,cx=0,backT=Math.max(8,(bd-id)/2-7),sideT=(bl-il)/2-5;
 if(sideT<3)throw Error('Drawer cannot fit '+p.sku);
 p.solid('skrin-zadni-stena',backT,bl,top-f,6,[-bd/2+backT/2,0,f],0);
 for(const y of [-1,1])p.solid('skrin-bocnice-'+y,bd,sideT,top-f,6,[0,y*(bl/2-sideT/2),f],0);
 p.solid('skrin-dno',bd,bl,8,5,[0,0,f],0);p.solid('skrin-strop',bd,bl,12,5,[0,0,top-12],0);
 p.ribs(bd,bl,f,top,0,true);
 p.solid('skrin-horni-panel',bd,bl,8,6,[0,0,p.h-15],0);p.docking(p.h-7,bd,bl,'fixed');p.docking(0,bd,bl,'fixed',true);
 const count=rolling?1:p.sku==='4932472129'?2:p.sku==='4932493189'?4:3;
 const hs=p.sku==='4932493190'?[61,61,130]:Array(count).fill(q.ih),available=top-f-20,total=hs.reduce((a,b)=>a+b+3,0),space=(available-total)/(count+1);
 if(space<1)throw Error('Drawer heights cannot fit '+p.sku);
 let z=f+9;
 for(let i=count-1;i>=0;i--){
  const ih=hs[i],h=ih+3,g='drawer-'+i,base=z+space,dx=bd/2-15-(id+8)/2;
  p.solid('zasuvka-'+i+'-dno',id+8,il+8,3,4,[dx,0,base],5,g);
  p.ring('zasuvka-'+i+'-dute-steny',id+8,il+8,ih,4,[id,il,3],[dx,0,base+3],5,g);
  const fx=dx+(id+8)/2+2;
  p.solid('zasuvka-'+i+'-celo',8,bl*.85,h+2,4,[fx,0,base-1],0,g);
  p.solid('zasuvka-'+i+'-cerveny-uchop',5,bl*.32,Math.min(12,ih*.16),2,[fx+5,0,base+h*.74],1,g);
  for(const yy of [-il/6,il/6])p.solid('zasuvka-'+i+'-cervena-prepazka-'+yy,id,2,ih*.72,.4,[dx,yy,base+3],1,g);
  for(const yy of [-bl*.37,bl*.37])p.tube('zasuvka-'+i+'-vysuv-'+yy,[-bd*.35,yy,base+h/2],[fx-5,yy,base+h/2],2.5,2,g);
  p.measuredFeatures??=[];p.measuredFeatures.push({kind:'drawer_cavity',drawer:i,dimensions_mm:{width:id,length:il,height:ih},source_url:p.r.inner[Math.min(i===2?1:0,p.r.inner.length-1)].source_url,component:'zasuvka-'+i+'-dute-steny'});
  z+=h+space;
 }
 const front=bd/2-5;
 if(!rolling){
  const ys=[-bl*.13,bl*.13],zlow=f+5,zhigh=top-6;
  for(const y of ys){
   p.tube('zajistovaci-lista-'+y,[front,y,zlow],[front,y,zhigh],2.5,2,'lock');
   p.solid('zajistovaci-lista-dolni-cep-'+y,9,12,10,2,[front-2,y,zlow-3],0);
   p.solid('zajistovaci-lista-horni-kotveni-'+y,10,13,10,2,[front-2,y,zhigh-5],1);
  }
  p.tube('zajistovaci-lista-mustek',[front,ys[0],zhigh],[front,ys[1],zhigh],2.5,2,'lock');
  p.label(front-6,p.h*.80,bl*.30,1,'drawer-0');
 }else{
  const first=p.parts.find(x=>x.name==='zasuvka-0-celo');
  p.ring('rolling-zasuvka-horni-uzaver',26,30,3,5,[14,18,3],[bd/2-4,0,p.h*.76],1,'drawer-0',[0,Math.PI/2,0]);
  for(const y of [-1,1])p.wheel(-bd/2+wheelD/2,y*(p.l/2-ww/2),wheelD,ww);
  p.tube('rolling-kola-skutecna-osa',[-bd/2+wheelD/2,-p.l/2+ww/2,wheelD/2],[-bd/2+wheelD/2,p.l/2-ww/2,wheelD/2],5,2);
  sideHandles(p,bd,bl,p.h*.77);trolleyHandle(p,bd,bl);
 }
 p.features.add('duté zásuvky se zdrojovou výškou, červené přepážky a uložené úchopy');
}
function trolleyHandle(p,bd,bl){
 const x=-bd/2+11,span=bl*.48,z=p.h-80;
 for(const y of [-1,1]){
  p.solid('teleskopicke-vedeni-'+y,18,20,p.h*.70,3,[x,y*span/2,p.h*.20],0);
  p.solid('teleskopicka-tyc-'+y,10,12,70,2,[x,y*span/2,z],0,'trolley-handle');
  p.solid('teleskopicke-kotveni-'+y,22,26,18,3,[x,y*span/2,z-8],0);
 }
 p.solid('teleskopicke-madlo',18,span+20,18,3,[x,0,p.h-18],1,'trolley-handle');
 p.solid('teleskopicky-mustek',16,span+16,13,3,[x,0,z+12],1,'trolley-handle');
 p.features.add('teleskopické madlo ve vedeních, přepravní poloha');
}
function cabinet(p){
 const q=cavity(p),f=p.feet(),top=p.h-15,tx=(p.d-q.id)/2,ty=(p.l-q.il)/2;
 p.solid('skrin-zada',tx,p.l,top-f,6,[-p.d/2+tx/2,0,f],0);
 for(const y of [-1,1])p.solid('skrin-bok-'+y,p.d,ty,top-f,6,[0,y*(p.l/2-ty/2),f],0);
 const floor=top-q.ih;
 p.solid('skrin-dno',p.d,p.l,floor-f,5,[0,0,f],0);p.solid('skrin-strop',p.d,p.l,8,5,[0,0,top-8],0);
 const front=p.d/2-10;
 p.solid('dvere-panel',10,p.l*.87,q.ih-10,5,[front,0,floor+2],0,'door');
 for(const y of [-p.l*.36,p.l*.36])p.solid('dvere-zebro-'+y,5,10,q.ih-14,2,[front+4,y,floor+5],0,'door');
 p.solid('dvere-cerveny-uzaver',5,p.l*.18,18,3,[front+7,0,floor+3],1,'door');
 for(const y of [-p.l*.30,p.l*.30]){
  p.tube('dvere-horni-pant-'+y,[front,y-13,top],[front,y+13,top],3,2);
  p.tube('dvere-pant-rameno-'+y,[front,y,top-8],[front,y,top],2,2,'door');
  p.solid('dvere-horni-kotveni-'+y,12,30,10,2,[front-2,y,top-6],0);
 }
 p.ribs(p.d,p.l,f,top);p.solid('skrin-horni-panel',p.d,p.l,8,6,[0,0,top],0);p.docking(p.h-7,p.d,p.l,'fixed');p.docking(0,p.d,p.l,'fixed',true);
 p.label(front+5,floor+q.ih*.55,p.l*.50,1,'door');
 p.features.add('horní vodorovný pant; dvířka se zvedají vzhůru');
}
function tip(p){
 const f=p.feet(),d=p.d*.92,l=p.l*.94,ht=p.h-f-10;
 p.solid('vyklopny-organizer-zadni-panel',p.d,p.l,8,8,[0,0,f],0);
 p.ring('vyklopny-organizer-obvodovy-ram',p.d,p.l,ht,10,[d,l,6],[0,0,f],0);
 const rows=[.28,.44,.28],gap=5;let x=-d/2; p.binCount=0;
 for(let row=0;row<3;row++){
  const dx=d*rows[row],n=row===1?2:4;
  for(let k=0;k<n;k++){
   const by=l/n-gap,bx=dx-gap,cy=-l/2+(k+.5)*l/n,cxx=x+dx/2,g='tip-'+p.binCount,z=f+8,bh=ht-11;
   p.solid(g+'-dno',bx,by,2,4,[cxx,cy,z],3,g);
   p.ring(g+'-dute-cire-steny',bx,by,bh,4,[bx-4,by-4,3],[cxx,cy,z+2],3,g);
   p.solid(g+'-vicko',bx-2,by-2,1.5,3,[cxx,cy,z+bh],3,g);
   p.solid(g+'-uchop',3,by*.5,4,1,[cxx+bx/2-3,cy,z+bh-3],5,g);
   p.tube(g+'-pant',[cxx+bx/2-2,cy-by/2+3,z+6],[cxx+bx/2-2,cy+by/2-3,z+6],1.6,2,g);
   p.solid(g+'-pant-kotveni',5,by,10,2,[cxx+bx/2-2,cy,z],0);
   p.binCount++;
  }x+=dx;
 }
 // Photo Hero_4 / Hero_5 shows a handle on the narrow front edge, not in
 // the middle of the storage face. Mounts touch the frame at the edge.
 fixedHandle(p,p.d/2-5,p.h*.52,p.l*.37,36,true);
 for(const y of [-1,1])p.solid('vyklopny-organizer-horni-nosny-lem-'+y,p.d,6,10,2,[0,y*(p.l/2-3),p.h-10],0);
 p.docking(0,p.d,p.l,'fixed',true);
 p.features.add('8 menších a 2 větší průhledné nádoby s víčky, čelní rukojeť a panty');
}
function recessFrontWall(p,sh,depth){
 // The front latches in Hero_1/6 sit in a recessed face between full-depth
 // corners. Change only that outer face; retain the published cavity, floor,
 // wheel positions and envelope. Depth is a reconstruction parameter.
 if(depth>=(sh.d-sh.id)/2-.5)throw Error('Front recess would cut sourced cavity '+p.sku);
 const a=sh.d/2,b=sh.l/2,r=Math.min(sh.d,sh.l)*.025,y=sh.l*.41,s=new THREE.Shape();
 s.moveTo(-a+r,-b);s.lineTo(a-r,-b);s.quadraticCurveTo(a,-b,a,-b+r);
 s.lineTo(a,-y);s.lineTo(a-depth,-y);s.lineTo(a-depth,y);s.lineTo(a,y);
 s.lineTo(a,b-r);s.quadraticCurveTo(a,b,a-r,b);s.lineTo(-a+r,b);
 s.quadraticCurveTo(-a,b,-a,b-r);s.lineTo(-a,-b+r);s.quadraticCurveTo(-a,-b,-a+r,-b);
 const hole=outline(sh.id,sh.il,Math.min(sh.id,sh.il)*.025);s.holes.push(new THREE.Path(hole.getPoints(5)));
 const g=new THREE.ExtrudeGeometry(s,{depth:sh.ih,steps:1,curveSegments:5,bevelEnabled:false});g.translate(sh.cx,0,sh.floor);g.computeVertexNormals();
 const part=p.parts.find(x=>x.name==='pojezdove-telo-duta-stena');if(!part)throw Error('Missing rolling wall');part.g=g;
 p.features.add('čelní západky v zapuštěné stěně mezi ochrannými rohy');
 p.equations.push(`Čelo: rekonstrukční hloubka kapsy = 2 × ${depth/2} = ${depth} mm; zdrojová dutina a vnější obálka zachované.`);
}
function rolling(p,chest=false){
 const q=cavity(p),diam=chest?230:228,ww=chest?42:Math.min(40,(p.l-q.il-8)/2);
 const bd=chest?p.d-ww*2:p.d,bl=chest?p.l-14:p.l-ww*2;
 const z0=chest?35:32,lh=chest?25:28,top=p.h-lh;
 const sh=p.shell('pojezdove-telo',bd,bl,z0,top,q.id,q.il,q.ih,0);
 const frontRecess=2*Math.min(p.d*.015,6);recessFrontWall(p,sh,frontRecess);
 // Four physical bottom supports account for the ground plane. These have
 // no bounding shell or hidden vertices, and meet the floor of the body.
 for(const x of [-1,1])for(const y of [-1,1])p.solid('pojezdova-patka-'+x+'-'+y,22,22,z0,4,[x*(bd/2-11),y*(bl/2-11),0],0);
 p.ribs(bd,bl,z0,top,0,true);supportedLid(p,sh,lh);
 for(const y of [-bl*.32,bl*.32])p.latch(bd/2-6,y,top-62,70);
 p.label(bd/2-frontRecess,z0+(top-z0)*.58,bl*.47);
 if(chest){
  // The two wheels are at +Y, on opposite X sides; rotating about Z changes
  // the wheel axle from Y to X. Bounds remain source dimensions without fit.
  const cy=p.l/2-diam/2,cx=p.d/2-ww/2;
  for(const x of [-1,1])p.wheel(cy,-x*cx,diam,ww,'x');
  p.tube('bedna-kola-skutecna-osa',[-cx,cy,diam/2],[cx,cy,diam/2],5,2);
  // Double Stack Top: duplicate the actual six-pocket layout on both halves.
  p.parts=p.parts.filter(a=>!a.name.startsWith('PACKOUT-horni')&&!a.name.startsWith('PACKOUT-lista')&&!a.name.startsWith('PACKOUT-cervene'));
  for(const sy of [-1,1]){
   const first=p.parts.length;p.docking(p.h-7,bd,bl*.46,'lid');
   for(const part of p.parts.slice(first)){part.name='dvojite-pole-'+sy+'-'+part.name;part.g.translate(0,sy*bl*.25,0);}
  }
  const span=bd*.60,z=top-14;
  p.ring('bedna-zasunute-bocni-madlo',span,45,8,8,[span-16,29,4],[0,-bl/2+1,z],0,'pull-handle',[Math.PI/2,0,0]);
  for(const x of [-1,1])p.solid('bedna-madlo-vedeni-'+x,22,30,45,3,[x*(span/2-10),-bl/2+12,z-22],0);
  p.features.add('obě kola na jednom konci, dvě horní stohovací pole, boční madlo v pouzdrech');
 }else{
  const x=-bd/2+diam/2;
  for(const y of [-1,1])p.wheel(x,y*(p.l/2-ww/2),diam,ww);
  p.tube('vozik-kola-skutecna-osa',[x,-p.l/2+ww/2,diam/2],[x,p.l/2-ww/2,diam/2],5,2);
  sideHandles(p,bd,bl,top-57);trolleyHandle(p,bd,bl);
 }
 p.docking(0,bd,bl,'fixed',true);
 p.measuredFeatures.push({kind:'cavity',dimensions_mm:{width:q.id,length:q.il,height:q.ih},source_url:p.r.inner[0].source_url,component:'pojezdove-telo-duta-stena'});
 p.features.add('zdrojová dutina bez deformace a kola se zdrojovým průměrem');
}
function build(r,sku){
 const p=new Product(r,sku);
 if(sku==='4932471064')organizerV5(p,'slim');
 else if(sku==='4932464082')organizerV5(p,'organiser');
 else if(sku==='4932471065')organizerV5(p,'compact');
 else if(sku==='4932478625')organizerV5(p,'deep');
 else if(sku==='4932471724')crate(p);
 else if(['4932472129','4932472130','4932493189','4932493190'].includes(sku))drawer(p);
 else if(sku==='4932498651')drawer(p,true);
 else if(sku==='4932480623')cabinet(p);
 else if(sku==='4932498323'){
  tip(p);
  // Hero_4/5: release tab directly below the front handle, within the body.
  p.solid('PACKOUT-spodni-odjistovaci-tlacitko',8,28,p.h*.08,2,[p.d/2-7,0,p.h*.34],1);
  p.features.add('červené čelní odjištění pod držadlem podle boční fotografie');
 }
 else if(sku==='4932464078')rolling(p);
 else if(sku==='4932478161')rolling(p,true);
 else standard(p);
 return p.write();
}

// The side / bottom photographs show a continuous moulded corner, not the
// two detached vertical boards used in v4. Dimensions below inherited from
// v4 are APPEARANCE parameters, never claimed as physical measurements.
function organizerContour(d,l,depth){
 const a=d/2,b=l/2,r=Math.min(d,l)*.025,y=l*.41,s=new THREE.Shape();
 s.moveTo(-a+r,-b);s.lineTo(a-r,-b);s.quadraticCurveTo(a,-b,a,-b+r);
 s.lineTo(a,-y);s.quadraticCurveTo(a,-y+depth,a-depth,-y+depth);
 s.lineTo(a-depth,y-depth);s.quadraticCurveTo(a,y-depth,a,y);
 s.lineTo(a,b-r);s.quadraticCurveTo(a,b,a-r,b);s.lineTo(-a+r,b);
 s.quadraticCurveTo(-a,b,-a,b-r);s.lineTo(-a,-b+r);s.quadraticCurveTo(-a,-b,-a+r,-b);s.closePath();return s;
}
function organizerDocking(p,sh){
 // TIM underside: 3 rows × 4 stations for 4932464082.
 // Slovak dealer underside: 3 rows × 2 stations for 4932471065.
 // The photographs confirm topology and orientation. Exact coordinates and
 // cross sections remain explicitly unverified appearance proportions;
 // they are not claimed as calibrated physical measurements.
 const wide=!p.compact,n=wide?4:2;
 const px=wide?[-.28,0,.28]:[-.30,0,.30],py=wide?[-.375,-.13,.13,.375]:[-.25,.25];
 const sx=sh.d*(wide?.095:.105),sy=sh.l*(wide?.145:.19),z1=sh.z0;
 for(let i=0;i<3;i++)for(let j=0;j<n;j++){
  const x=sh.cx+px[i]*sh.d,y=py[j]*sh.l,id=i+'-'+j;
  p.solid('PACKOUT-spodni-patka-'+id,sx,sy,z1,3,[x,y,0],0);
  p.solid('PACKOUT-spodni-zub-'+id,sx*.18,sy*.8,z1*.4,1,[x+sx*.38,y,0],0);
  // Visual ribs on the actual station, no detached plates at the front.
  for(let k=0;k<6;k++)p.solid('PACKOUT-spodni-prolis-'+id+'-'+k,sx*.34,sy*.09,z1*.12,.3,[x,y+(k-2.5)*sy*.14,z1*.10],4);
 }
 p.features.add(wide?'spodní pole 3 × 4 pozice podle fotografie evropského organizéru':'spodní pole 3 × 2 pozice podle fotografie kompaktního organizéru');
 p.equations.push(`Spodní pole: ${3} × ${n} = ${3*n} pozic; střed X = ${sh.cx} + poměr × ${sh.d}; Y = poměr × ${sh.l}. Poměry z fotografií nejsou kótované výrobní rozteče.`);
}
function releaseC(p,front,z){
 // This is the small C shaped red front feature visible in Hero / Feat_1.
 // It is not a large rectangular lock loop hanging below the case.
 const s=new THREE.Shape(),rad=9,inner=5,a=.24*Math.PI,b=1.76*Math.PI;
 s.moveTo(rad*Math.cos(a),rad*Math.sin(a));s.absarc(0,0,rad,a,b,false);
 s.lineTo(inner*Math.cos(b),inner*Math.sin(b));s.absarc(0,0,inner,b,a,true);s.closePath();
 const g=new THREE.ExtrudeGeometry(s,{depth:1.5,curveSegments:12,bevelEnabled:false});
 p.add('PACKOUT-celni-C-odjisteni',g,1,'fixed',[front,0,z],[Math.PI/2,Math.PI/2,0]);
}
function organizerHandle(p,front,z,span,high,red){
 fixedHandle(p,front,z,span,high,red);
 if(!red)return;
 // Hero_1 and Feat_1 show a U shaped red housing, open at its top,
 // rather than the closed red rectangle inherited from the generic case.
 // Reuse the v4 extent and wall thickness; change only the evidenced topology.
 const a=span/2,b=high/2,t=high*.20,s=new THREE.Shape();
 s.moveTo(-a,b);s.lineTo(-a,-b+t);s.quadraticCurveTo(-a,-b,-a+t,-b);
 s.lineTo(a-t,-b);s.quadraticCurveTo(a,-b,a,-b+t);s.lineTo(a,b);
 s.lineTo(a-t,b);s.lineTo(a-t,-b+t);s.lineTo(-a+t,-b+t);s.lineTo(-a+t,b);s.closePath();
 const g=new THREE.ExtrudeGeometry(s,{depth:5,curveSegments:5,bevelEnabled:false});
 const part=p.parts.find(a=>a.name==='drzadlo-otevreny-uchop');
 g.applyMatrix4(new THREE.Matrix4().compose(new THREE.Vector3(front,0,z),new THREE.Quaternion().setFromEuler(new THREE.Euler(Math.PI/2,Math.PI/2,0)),new THREE.Vector3(1,1,1)));
 g.computeVertexNormals();part.g=g;
 p.features.add('červené pouzdro úchopu tvaru U, otevřené nahoře podle čelních fotografií');
}
function organizerV5(p,kind){
 const q=cavity(p),f=p.feet(),reserve=Math.min(p.d*.04,16),lh=Math.min(Math.min(p.h*.17,15),p.h-f-q.ih-2),top=p.h-lh;
 const sh=p.shell('telo',p.d,p.l,f,top,q.id,q.il,q.ih,0),shape=organizerContour(p.d,p.l,reserve);
 const releaseX=p.d/2-reserve-10,releaseWidth=p.compact?18:26;
 const releaseHole=outline(8,releaseWidth,2).getPoints(5).map(a=>new THREE.Vector2(a.x+releaseX,a.y));
 shape.holes.push(new THREE.Path(releaseHole));
 const make=(shape,z,h)=>{const g=new THREE.ExtrudeGeometry(shape,{depth:h,steps:1,curveSegments:5,bevelEnabled:false});g.translate(0,0,z);g.computeVertexNormals();return g;};
 p.parts.find(a=>a.name==='telo-dno').g=make(shape,sh.z0,sh.floor-sh.z0);
 p.floorContourOverride=shape.getPoints(5).map(a=>[a.x,a.y]);
 const wall=organizerContour(p.d,p.l,reserve);wall.holes.push(new THREE.Path(outline(q.id,q.il,Math.min(q.id,q.il)*.025).getPoints(5)));
 p.parts.find(a=>a.name==='telo-duta-stena').g=make(wall,sh.floor,q.ih);
 // Side stiffening is attached directly to the body. No external guard board.
 for(const sy of [-1,1])for(const frac of [-.22,.22])p.solid('bok-zebro-'+sy+'-'+frac,p.d*.022,p.l*.012,(top-f)*.76,1,[frac*p.d,sy*(p.l/2-p.l*.006),f+(top-f)*.06],0);
 if(kind==='deep'){
  const split=-sh.id*.24;p.solid('hluboky-zadni-dlouhy-delic',3,sh.il,sh.ih*.87,1,[split,0,sh.floor],0,'bins');
  for(const y of [-sh.il/6,sh.il/6])p.solid('hluboky-cerveny-delic-'+y,sh.id*.73,3,sh.ih*.88,1,[sh.id*.125,y,sh.floor],1,'bins');
  p.binCount=4;
 }else p.bins(sh,kind);
 supportedLid(p,sh,lh,true,kind);
 // Same moulded contour on the lid rim. A flat full-width rim would produce
 // a new blade floating over the newly recessed face.
 const rim=organizerContour(p.d,p.l,reserve);rim.holes.push(new THREE.Path(outline(p.d-2*reserve-12,p.l-12,4).getPoints(5)));
 p.parts.find(a=>a.name==='viko-nosny-okraj').g=make(rim,top,lh*.65);
 const panel=p.parts.find(a=>a.name==='viko-panel');
 const narrow=p.d-reserve;panel.g=extrusion(narrow-8,p.l-8,Math.max(lh*.20,lh*.50-7),6);panel.g.translate(-reserve/2,0,top+lh*.50);
 // Sealing reliefs follow the sourced cavity, unaffected by the outer contour.
 const front=p.d/2-reserve,hl=Math.min(p.h*.57,74),hz=top-hl*.50;
 for(const y of [-p.l*.32,p.l*.32])p.latch(front,y,Math.min(top-hl*.9,p.h-hl),hl);
 organizerHandle(p,front+2,hz,p.l*.31,Math.min(33,p.h*.32),kind!=='slim'&&kind!=='compact');
 if(kind==='slim'||kind==='compact'){
  const h=Math.min(33,p.h*.32);
  p.solid('PACKOUT-celni-odjistovaci-tlacitko',3,12,h*.15,1,[front+1.5,0,hz-h*.45],1);
 }else releaseC(p,front,hz);
 // Separate underside release button, confirmed by Photo007 and the SK
 // underside. Its attachment reaches the actual bottom, instead of floating.
 p.solid('PACKOUT-spodni-odjistovaci-tlacitko',8,releaseWidth,sh.floor-f,2,[releaseX,0,f],1);
 const old=p.parts.length;organizerDocking(p,sh);
 // anchorBottomSupports() normally translates generic docking by floor
 // centre. Our measured field is already centred on the contour. Floor bbox
 // has centre 0, so this transformation is exactly identity.
 p.features.add('spojené zaoblené čelní rohy a dno bez samostatných vyčnívajících desek');
 p.measuredFeatures=[{kind:'cavity',dimensions_mm:{width:q.id,length:q.il,height:q.ih},source_url:p.r.inner[0].source_url,component:'telo-duta-stena'}];
 p.equations.push(`Čelo: kraj trupu = ${p.d}/2 = ${p.d/2} mm; čelní kapsa = ${p.d/2} − ${reserve} = ${front} mm. Rezerva převzata z v4 jako nekótovaný vzhledový parametr, nevydává se za fyzické měření.`);
}
function main(){
 for(const dir of ['nahled-modely-v5/modely','mereni-tvar-v5'])fs.mkdirSync(path.join(ROOT,dir),{recursive:true});
 const changed=new Set(organizerPhotos.records.map(r=>r.sku));let count=0;
 for(const id of catalog.model_order){
  const r=catalog.records.find(r=>r.id===id),org=changed.has(r.sku[0]);
  r.review={...r.review,render_before_file:'porovnani/'+r.sku[0]+'-v4.png',render_file:'porovnani/'+r.sku[0]+'.png',comparison_note:'Vlevo zachovaný model v4, vpravo v5. U organizérů je deset pohledů a barevné rozlišení dílů. Kóty obálky potvrzené; přesnost nekótovaných detailů není ověřená.'};
  if(org){
   r.photo_sources=organizerPhotos.records.find(x=>x.sku===r.sku[0]).photos.map(p=>({url:p.url,page_url:p.page_url,kind:p.view||p.kind}));
   r.review.changed_v4=r.review.changed;
   r.review.changed=r.sku[0]==='4932498323'?'Zkontrolované všechny součásti; nebyla nalezena vyčnívající podstava. Doplněné připojené červené odjištění pod čelním držadlem podle bočního snímku; vše v obrysu trupu.':'Samostatné vyčnívající čelní desky nahrazené spojitým zaobleným trupem, dnem a okrajem víka. Červená smyčka nahrazena odpovídajícím čelním prvkem a připojeným spodním odjištěním; upravené spodní spojovací pole.';
   r.review.match='Opravené vyčnívající desky a nesprávné odjištění; vzhledová rekonstrukce. Přesné nekótované rozměry dosud neověřené.';
   r.review.photo_count=r.photo_sources.length;
   r.organizer_review={photo_count:r.photo_sources.length,views:['front','back','side','sideOther','top','bottom','isoFrontRight','isoFrontLeft','isoBackRight','isoBackLeft'],mesh_colors:true};
   r.model_variants=r.sku.map(sku=>build(r,sku));count+=r.model_variants.length;
  }else{
   r.review.changed='Model beze změny oproti v4; zkontrolované obě boční strany, čelo, horní a spodní pohled a všechny podstavy.';
   for(const sku of r.sku)fs.copyFileSync(path.join(ROOT,'modely-v4',sku+'.glb'),path.join(OUT,'modely',sku+'.glb'));
  }
 }
 catalog.schema_version='2.3';catalog.stage_status='doladeni_v5_presnost_detailu_neoverena';catalog.model_preview_url='https://autovestavby.logiman.cz/nahled-john/kufriky-milwaukee-modely-v5/';
 catalog.model_summary.message='Opravené organizéry; všechny typy mají ověřenou obálku a podstavy. Přesnost nekótovaných detailů a spojů zůstává neověřená.';
 fs.writeFileSync(path.join(ROOT,'kufriky.json'),JSON.stringify(catalog,null,2)+'\n');
 fs.writeFileSync(path.join(ROOT,'mereni-tvar-v5/prehled.json'),JSON.stringify(catalog.model_order.flatMap(id=>catalog.records.find(r=>r.id===id).model_variants),null,2)+'\n');
 console.log('V5: '+count+' organizérů; ostatních 16 SKU zachováno bitově z v4.');
}
main();
