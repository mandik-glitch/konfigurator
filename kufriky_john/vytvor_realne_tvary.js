"use strict";
// Offline generator. Millimetres: X=depth/short side, Y=long side, Z=height.
// Published dimensions are constraints. Appearance parameters are photo-derived
// reconstruction choices, NOT measured technical dimensions or mating CAD.
const fs=require('fs'),path=require('path');
const THREE=require('./nahled-modely/vendor/three.min.js');
const ROOT=__dirname, OUT=path.join(ROOT,'nahled-modely-v2');
const catalog=JSON.parse(fs.readFileSync(path.join(ROOT,'kufriky.json')));
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
 const s=outline(d,l,r);
 if(inner){const hole=outline(inner[0],inner[1],inner[2]);s.holes.push(new THREE.Path(hole.getPoints(5)));}
 const b=Math.min(bevel,h*.22,d*.025,l*.025);
 const g=new THREE.ExtrudeGeometry(s,{depth:h-2*b,steps:1,curveSegments:5,bevelEnabled:b>0,bevelSegments:2,bevelSize:b,bevelThickness:b});
 g.translate(0,0,b);g.computeVertexNormals();return g;
}
class Product{
 constructor(record,sku){this.r=record;this.sku=sku;this.d=record.outer.mm.width;this.l=record.outer.mm.length;this.h=record.outer.mm.height;this.parts=[];this.features=new Set();this.notes=[];this.equations=[];}
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
  const attr=wall.getAttribute('position'),taper=Math.min((d-id)/d,(l-il)/l)*.25;
  for(let i=0;i<attr.count;i++)if(Math.abs(attr.getX(i))>id/2+.01||Math.abs(attr.getY(i))>il/2+.01){const f=1-taper*(1-attr.getZ(i)/ih);attr.setX(i,attr.getX(i)*f);attr.setY(i,attr.getY(i)*f);}
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
  const dh=Math.min(this.h*.045,8),sx=d*.19,sy=l*.18;
  for(const x of [-1,1])for(const y of [-1,1]){
   const px=x*d*.24,py=y*l*.27;
   if(bottom){
    this.solid(`PACKOUT-spodni-patka-${x}-${y}`,sx*.8,sy,dh,3,[px,py,z],0,group);
    this.solid(`PACKOUT-spodni-zub-${x}-${y}`,sx,sy*.24,dh*.35,1.5,[px,py-sy*.35,z],0,group);
   }else{
    this.ring(`PACKOUT-horni-drazka-${x}-${y}`,sx,sy,dh,3,[sx*.68,sy*.72,2],[px,py,z],0,group);
    // Interrupted lip and overhang: real recess rather than a painted rectangle.
    this.solid(`PACKOUT-horni-zamek-${x}-${y}`,sx*.20,sy*.64,dh*.32,1,[px+sx*.35,py,z+dh*.68],0,group);
   }
  }
  if(!bottom){
   // Raised rails with open channels and moulded transverse stiffeners are
   // visible on the manufacturer's lid; no fit compatibility is claimed.
   for(const y of [-l*.40,l*.40]){
    this.solid('PACKOUT-vnejsi-lista-'+y,d*.82,l*.025,dh*.72,2,[0,y,z],0,group);
    for(let k=0;k<5;k++)this.solid('PACKOUT-lista-zebro-'+y+'-'+k,d*.045,l*.047,dh*.55,1,[(k-2)*d*.17,y,z+dh*.35],0,group);
   }
   this.ring('viko-prolis-obvod',d*.93,l*.91,dh*.40,6,[d*.89,l*.87,5],[0,0,z],0,group);
   for(const x of [-d*.35,0,d*.35])this.solid('viko-podelna-vyztuha-'+x,d*.025,l*.78,dh*.40,1,[x,0,z],0,group);
  }
  this.features.add('horní drážky a spodní zuby PACKOUT (vizuální)');
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
  this.solid('zapadka-cervena-'+y,t*.7,w*.78,h*.64,w*.06,[front,y,z],1,'fixed');
  for(let i=0;i<4;i++)this.solid('zapadka-zebro-'+y+'-'+i,t*.24,w*.10,h*.28,.5,[front+t*.7,y+(i-1.5)*w*.17,z+h*.34],1,'fixed');
  const x=front+t*.3;
  this.tube('zapadka-kov-levy-'+y,[x,y-w*.5,z+h*.28],[x,y-w*.5,z+h*.95],1.35,2);
  this.tube('zapadka-kov-pravy-'+y,[x,y+w*.5,z+h*.28],[x,y+w*.5,z+h*.95],1.35,2);
  this.tube('zapadka-kov-mustek-'+y,[x,y-w*.5,z+h*.95],[x,y+w*.5,z+h*.95],1.35,2);
  this.features.add('západky a kovové spony');
 }
 frontHandle(front,z,span,high,red=true){
  const thick=high*.18;
  this.ring('drzadlo-otevreny-uchop',span,high,Math.min(this.d*.018,7),high*.22,[span-thick*2,high-thick*2,high*.16],[front,0,z],red?1:0,'fixed',[Math.PI/2,Math.PI/2,0]);
  this.features.add('otevřené držadlo');
 }
 raisedHandle(z,span,high,cx=0,red=false){
  const t=high*.16;
  this.ring('vyklopne-drzadlo',span,high,Math.min(this.d*.035,12),high*.16,[span-2*t,high-2*t,high*.12],[cx,0,z+high/2],red?1:0,'handle',[Math.PI/2,Math.PI/2,0]);
  this.features.add('výklopné držadlo');
 }
 ribs(d,l,z0,z1,cx=0,metal=false){
  const ht=z1-z0,r=Math.min(d,l)*.03;
  for(const sy of [-1,1])for(const sx of [-1,1]){
   this.solid(`roh-ochrana-${sx}-${sy}`,r*1.2,r*1.2,ht,r*.32,[cx+sx*(d/2-r*.47),sy*(l/2-r*.47),z0],0);
   if(metal)this.solid(`roh-kov-${sx}-${sy}`,r*.6,r*.6,ht*.86,r*.13,[cx+sx*(d/2-r*.10),sy*(l/2-r*.10),z0+ht*.07],2);
  }
  for(const sy of [-1,1])for(const f of [-.22,0,.22])this.solid(`bok-zebro-${sy}-${f}`,d*.035,l*.012,ht*.74,1,[cx+f*d,sy*l/2,z0+ht*.08],0);
  for(const sy of [-1,1])this.ring('bok-prolis-'+sy,d*.64,ht*.65,2,5,[d*.60,ht*.59,4],[cx,sy*(l/2+1),z0+ht*.47],0,'fixed',[Math.PI/2,0,0]);
  this.ring('celo-prolis',l*.60,ht*.66,2,5,[l*.55,ht*.61,4],[cx+d/2+1,0,z0+ht*.45],0,'fixed',[Math.PI/2,Math.PI/2,0]);
  this.features.add('zaoblené rohy, ochrany a žebra');
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
    const bottom=shell.floor+1,ht=shell.z1-bottom-1.2;
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
 wheel(x,y,diam,width){
  const r=diam/2,z=r;
  this.add('kolo-pneumatika-'+y,new THREE.CylinderGeometry(r,r,width,40,1),4,'fixed',[x,y,z]);
  this.add('kolo-naboj-'+y,new THREE.CylinderGeometry(r*.70,r*.70,width+1,24,1),0,'fixed',[x,y,z]);
  this.add('kolo-osa-'+y,new THREE.CylinderGeometry(r*.10,r*.10,width+2,12,1),2,'fixed',[x,y,z]);
  for(let i=0;i<12;i++){
   const a=i*Math.PI/6;
   this.tube('kolo-paprsek-'+y+'-'+i,[x+Math.cos(a)*r*.20,y+Math.sign(y)*(width*.51),z+Math.sin(a)*r*.20],[x+Math.cos(a)*r*.68,y+Math.sign(y)*(width*.51),z+Math.sin(a)*r*.68],r*.026,0);
  }
  for(let i=0;i<28;i++){
   const a=i*Math.PI*2/28,g=new THREE.BoxGeometry(r*.035,width*.92,r*.10);
   g.rotateY(a);this.add('kolo-vzorek-'+y+'-'+i,g,4,'fixed',[x+Math.sin(a)*r*.965,y,z+Math.cos(a)*r*.965]);
  }
  this.features.add('kolečka s náboji, paprsky a vzorkem');
 }
 write(){
  // Constraints are checked on the product geometry, before centering. No box,
  // invisible support vertex or bounding shell is inserted to fake a result.
  const box=new THREE.Box3();for(const p of this.parts){p.g.computeBoundingBox();box.union(p.g.boundingBox);}
  const size=box.getSize(new THREE.Vector3());
  // Photo reconstruction is fitted to source envelope. Record axis scale and
  // unscaled bounds explicitly; this fit is not a physical accuracy certificate.
  const fit=[this.d/size.x,this.l/size.y,this.h/size.z],center=box.getCenter(new THREE.Vector3());
  const matrix=new THREE.Matrix4().makeScale(...fit);matrix.multiply(new THREE.Matrix4().makeTranslation(-center.x,-center.y,-center.z));
  for(const p of this.parts)p.g.applyMatrix4(matrix);
  const metadata={sku:this.sku,units:'mm',catalog_axes:{X:'width',Y:'length',Z:'height'},kind:'photo_reconstructed_product',is_product_geometry:true,
   detail_level:'realny_tvar',detail_label:'Reálný tvar · rekonstrukce z fotografií',physical_accuracy_verified:false,physical_tolerance_mm:null,
   source_url:this.r.outer.source_url,photo_url:this.r.image.source_url,photo_page_url:this.r.image.page_url,
   dimension_constraints_mm:this.r.outer.mm,features:[...this.features],bin_count:this.binCount||0,
   envelope_fit:{before_min_mm:box.min.toArray(),before_max_mm:box.max.toArray(),axis_scale:fit},
   limitation:'Kóty obálky jsou ze zdroje. Nekótované detaily a skryté spoje jsou vizuální rekonstrukce, ne přesný výrobní CAD. Kompatibilita PACKOUT a tolerance fyzického kusu neověřeny.',
   label_font_license:fontSource.original_font_information.license_description};
  const glb=encode(this.parts,metadata);if(glb.length>=3e6)throw Error('File over 3MB '+this.sku);
  const filename=this.sku+'.glb';fs.writeFileSync(path.join(ROOT,'modely',filename),glb);fs.writeFileSync(path.join(OUT,'modely',filename),glb);
  const report={...metadata,bytes:glb.length,parts:this.parts.map(p=>({name:p.name,group:p.group,material:p.mat,...p.extras})),equations:this.equations};
  fs.writeFileSync(path.join(ROOT,'mereni-tvar-v2',this.sku+'.json'),JSON.stringify(report,null,2)+'\n');
  return {sku:this.sku,file:'modely/'+filename,bytes:glb.length,part_count:this.parts.length,bin_count:this.binCount||0,features:metadata.features,detail_level:'realny_tvar',physical_accuracy_verified:false};
 }
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
function standard(p,kind='case'){
 const org=['slim','organiser','compact','deep'].includes(kind),compact=kind==='compact'||p.sku==='4932471723';
 const feet=p.feet(),handleBudget=!org&&p.sku==='4932471723'?p.h*.24:!org&&p.sku==='4932464079'?p.h*.20:0;
 const sourceIH=p.r.inner[0]?.mm.height;
 const lidH=Math.min(org?p.h*.18:Math.min(p.h*.13,35),sourceIH?p.h-feet-sourceIH-1:Infinity),top=p.h-handleBudget-lidH;
 const frontReserve=org?p.d*.085:p.d*.04,d=p.d-frontReserve,cx=-frontReserve/2;
 const inner=p.r.inner[0]?.mm;
 let id=inner?.width||d*.82,il=inner?.length||p.l*.86,ih=inner?.height||top-feet-p.h*.08;
 // Published inner height can exceed visible shell when a photo has a raised
 // handle: model with folded handle, avoiding reduction of the known cavity.
 let shellTop=Math.max(top,feet+ih+p.h*.018);if(shellTop+lidH>p.h){shellTop=p.h-lidH;ih=Math.min(ih,shellTop-feet-1);p.notes.push('Vnitřní hloubka omezená modelem víka; změřit skutečné uložení.');}
 const sh=p.shell('telo',d,p.l,feet,shellTop,id,il,ih,cx);
 p.ribs(d,p.l,feet,shellTop,cx,!org&&!compact);
 if(org){p.bins(sh,kind);p.clearLid(sh,shellTop,kind);}
 else{
  p.solid('viko-spodni-panel',d,p.l,lidH*.58,Math.min(d,p.l)*.028,[cx,0,shellTop],0,'lid');
  p.ring('viko-zesileny-okraj',d,p.l,lidH*.28,9,[d*.90,p.l*.91,5],[cx,0,shellTop+lidH*.55],0,'lid');
  p.docking(p.h-Math.min(p.h*.045,8),d,p.l,'lid');
  if(p.sku==='4932464079'||p.sku==='4932471723'){
   p.foldedHandle(p.h-6,p.l*(compact?.60:.64),cx);
  }
  // Visible removable shallow tray; actual cavity remains beneath it.
  if(p.sku!=='4932471723'&&p.sku!=='4932499703'&&p.sku!=='4932499704'){
   const th=Math.min(ih*.25,45),td=id*.30;
   p.solid('vyjimatelna-vlozka-dno',td,il*.88,2,3,[cx-id*.32,0,shellTop-th],5,'tray');
   p.ring('vyjimatelna-vlozka-steny',td,il*.88,th-2,3,[td-6,il*.88-6,2],[cx-id*.32,0,shellTop-th+2],5,'tray');p.features.add('vyjímatelná vnitřní vložka');
  }
 }
 const latchH=org?Math.min(p.h*.72,80):Math.min(p.h*.25,84),front=d/2+cx;
 if(compact){p.latch(front,0,shellTop-latchH*.92,latchH);}
 else for(const y of [-p.l*.32,p.l*.32])p.latch(front,y,shellTop-latchH*.92,latchH);
 p.frontHandle(p.d/2-4,Math.max(feet+5,shellTop-latchH*.66),p.l*(compact?.34:.35),org?Math.min(p.h*.45,42):35,!org||kind!=='slim');
 p.docking(0,d,p.l,'fixed',true);
 p.ring('zamek-packout-cerveny',24,29,3,8,[12,16,5],[front+2,0,Math.min(shellTop*.25,40)],1,'fixed',[0,Math.PI/2,0]);
 for(const y of [-p.l*.27,p.l*.27])p.tube('pant-vika-'+y,[-p.d/2+3,y-12,shellTop],[-p.d/2+3,y+12,shellTop],3,0,'lid');
 p.features.add('víko a spodní díl');
 if(!org)p.label(front+3,sh.floor+ih*.48,p.l*.63);
 if(['4932499703','4932499704'].includes(p.sku)){
  // Same published family photograph is used by the two source pages. Separate
  // files do not assert identical unseen specialist inserts.
  p.ring('vnitrni-vyjimatelny-panel',id*.76,il*.92,3,5,[id*.76-8,il*.92-8,3],[cx+id*.08,0,sh.floor+4],1,'tray');
  for(let i=0;i<5;i++)p.solid('vnitrni-kapsa-'+i,id*.30,il*.13,ih*.35,3,[cx-id*.21,-il*.34+i*il*.17,sh.floor+8],5,'tray');p.features.add('vnitřní panel s kapsami podle fotografie');
 }
}
function crate(p){
 const feet=p.feet(),q=p.r.inner[0].mm,floor=p.h-q.height;
 p.solid('prepravka-dno',p.d,p.l,Math.max(1,floor-feet),8,[0,0,feet],0);
 function wall(name,span,height,t,xyz,rot){
  const s=outline(span,height,6),h=outline(span*.43,height*.13,5);
  s.holes.push(new THREE.Path(h.getPoints(5).map(v=>v.add(new THREE.Vector2(0,height*.35)))));
  const g=new THREE.ExtrudeGeometry(s,{depth:t,bevelEnabled:false,curveSegments:5,steps:1});p.add(name,g,0,'fixed',xyz,rot);
 }
 const ht=p.h-floor,tx=(p.d-q.width)/2,ty=(p.l-q.length)/2;
 wall('prepravka-celo-s-otvorem',p.l,ht,tx,[p.d/2-tx,0,floor+ht/2],[Math.PI/2,Math.PI/2,0]);
 wall('prepravka-zada-s-otvorem',p.l,ht,tx,[-p.d/2,0,floor+ht/2],[Math.PI/2,Math.PI/2,0]);
 wall('prepravka-bok-s-otvorem-1',p.d,ht,ty,[0,p.l/2,floor+ht/2],[Math.PI/2,0,0]);
 wall('prepravka-bok-s-otvorem-2',p.d,ht,ty,[0,-p.l/2+ty,floor+ht/2],[Math.PI/2,0,0]);
 p.features.add('dutý vnitřní prostor');p.features.add('průchozí otvory držadel');
 p.ribs(p.d,p.l,feet,p.h,0,false);
 // Horizontal wall ribs are actual geometry, and the upper handholds are holes.
 for(const sy of [-1,1])for(const z of [.16,.38,.70,.93])p.solid('prepravka-podelne-zebro-'+sy+'-'+z,p.d,p.l*.016,3,1,[0,sy*p.l*.5,p.h*z],0);
 for(const sx of [-1,1])for(const z of [.16,.38,.70,.93])p.solid('prepravka-celni-zebro-'+sx+'-'+z,p.d*.016,p.l,3,1,[sx*p.d*.5,0,p.h*z],0);
 p.frontHandle(p.d/2-5,p.h*.82,p.l*.50,p.h*.15,false);p.frontHandle(-p.d/2+5,p.h*.82,p.l*.50,p.h*.15,false);
 p.label(p.d/2+2,p.h*.64,p.l*.55);
 p.docking(0,p.d,p.l,'fixed',true);p.features.add('otevřená přepravka');
}
function drawer(p,rolling=false){
 const feet=p.feet(),q=p.r.inner[0].mm;
 const wheelD=rolling?228:0,bodyD=rolling?p.d*.89:p.d,bodyL=rolling?p.l-wheelD*.38:p.l;
 const z0=rolling?36:feet,z1=p.h-15,front=bodyD/2;
 p.solid('skrin-zadni-stena',bodyD*.045,bodyL,z1-z0,7,[-bodyD/2+bodyD*.0225,0,z0],0);
 for(const y of [-1,1])p.solid('skrin-bocnice-'+y,bodyD,bodyL*.075,z1-z0,7,[0,y*bodyL*.4625,z0],0);
 p.solid('skrin-dno',bodyD,bodyL,10,6,[0,0,z0],0);p.solid('skrin-strop',bodyD,bodyL,12,6,[0,0,z1-12],0);
 p.ribs(bodyD,bodyL,z0,z1,0,true);p.docking(p.h-8,bodyD,bodyL,'fixed');p.docking(0,bodyD,bodyL,'fixed',true);
 const count=rolling?1:p.sku==='4932472129'?2:p.sku==='4932493189'?4:3;
 const hs=p.sku==='4932493190'?[61,61,130]:Array(count).fill(q.height);
 const available=z1-z0-20,total=hs.reduce((a,b)=>a+b,0),space=Math.max(3,(available-total)/(count+1));
 let z=z0+10;
 for(let i=count-1;i>=0;i--){
  const hh=hs[i],inner=p.r.inner[Math.min(i===2?1:0,p.r.inner.length-1)].mm;
  const dh=Math.min(hh,available/count-2),id=inner.width,il=inner.length;
  const g='drawer-'+i;
  p.solid('zasuvka-'+i+'-dno',id+8,il+8,3,4,[bodyD/2-(id+8)/2-15,0,z+space],5,g);
  p.ring('zasuvka-'+i+'-dute-steny',id+8,il+8,dh-3,4,[id,il,3],[bodyD/2-(id+8)/2-15,0,z+space+3],5,g);
  p.solid('zasuvka-'+i+'-celo',bodyD*.025,bodyL*.84,dh+2,4,[front-bodyD*.026,0,z+space-1],0,g);
  p.solid('zasuvka-'+i+'-cerveny-uchop',bodyD*.015,bodyL*.44,Math.min(12,dh*.20),2,[front-bodyD*.002,0,z+space+dh*.68],1,g);
  p.solid('zasuvka-'+i+'-prolis',bodyD*.009,bodyL*.55,dh*.35,2,[front+1,0,z+space+dh*.23],5,g);
  // Divider grid, visible when drawers are opened in the preview.
  for(const yy of [-il/6,il/6])p.solid('zasuvka-'+i+'-prepazka-'+yy,id-3,2,dh*.65,.4,[bodyD/2-(id+8)/2-15,yy,z+space+3],5,g);
  for(const yy of [-bodyL*.38,bodyL*.38])p.tube('zasuvka-'+i+'-vysuv-'+yy,[-bodyD*.36,yy,z+space+dh/2],[front-15,yy,z+space+dh/2],2.5,2,g);
  z+=dh+space;p.features.add('duté zásuvky, přepážky a výsuvy');
 }
 for(const y of [-bodyL*.13,bodyL*.13])p.tube('zajistovaci-lista-'+y,[front+3,y,z0+7],[front+3,y,z1-9],2.5,2,'lock');
 p.tube('zajistovaci-lista-mustek',[front+3,-bodyL*.13,z1-9],[front+3,bodyL*.13,z1-9],2.5,2,'lock');
 p.features.add('čelní zajišťovací lišta');
 p.label(front+4,p.h*.84,bodyL*.36);
 if(rolling){
  const ww=p.l*.075;for(const y of [-1,1])p.wheel(-p.d*.24,y*(p.l/2-ww/2),wheelD,ww);
  // Transport position is modelled; manufacturer's hero shows an extended
  // handle. Its unknown travel is not assigned a technical dimension.
  for(const y of [-bodyL*.28,bodyL*.28])p.solid('teleskopicka-tyc-'+y,10,10,p.h*.20,2,[-bodyD/2+8,y,p.h*.77],0,'handle');
  p.solid('teleskopicke-madlo',14,bodyL*.61,16,3,[-bodyD/2+8,0,p.h-16],1,'handle');p.features.add('teleskopické madlo v přepravní poloze');
 }
}
function cabinet(p){
 const f=p.feet(),q=p.r.inner[0].mm;
 p.solid('skrin-zada',p.d*.05,p.l,p.h-f-16,7,[-p.d*.475,0,f],0);
 for(const y of [-1,1])p.solid('skrin-bok-'+y,p.d,p.l*.055,p.h-f-16,7,[0,y*p.l*.4725,f],0);
 p.solid('skrin-dno',p.d,p.l,10,5,[0,0,f],0);p.solid('skrin-strop',p.d,p.l,13,6,[0,0,p.h-21],0);
 p.solid('dvere-panel',10,p.l*.90,p.h*.81,5,[p.d/2-10,0,f+9],0,'door');
 for(const y of [-p.l*.36,p.l*.36])p.solid('dvere-zebro-'+y,4,10,p.h*.72,2,[p.d/2,y,f+20],0,'door');
 p.solid('dvere-cerveny-uzaver',5,p.l*.18,19,4,[p.d/2+2,0,p.h*.13],1,'door');
 for(const z of [.25,.65])p.tube('dvere-pant-'+z,[p.d/2-1,-p.l*.455,p.h*z-8],[p.d/2-1,-p.l*.455,p.h*z+8],3,2);
 p.ribs(p.d,p.l,f,p.h-18,0);p.docking(p.h-8,p.d,p.l,'fixed');p.docking(0,p.d,p.l,'fixed',true);
 p.features.add('přední dvířka, panty a dutá skříň');p.equations.push('Publikovaný volný úložný prostor: '+JSON.stringify(q)+'; polohy hran nejsou kótované.');
 p.label(p.d/2+1,p.h*.57,p.l*.60,1,'door');
}
function tip(p){
 const f=p.feet(),d=p.d*.91,l=p.l*.93,ht=p.h*.86;
 p.solid('vyklopny-organizer-zadni-panel',d,l,8,7,[-p.d*.02,0,f],0);
 p.ring('vyklopny-organizer-obvodovy-ram',p.d,p.l,ht,12,[d,l,7],[0,0,f],0);
 const sh={cx:0,id:d*.95,il:l*.94,floor:f+8,z1:ht+f};
 p.binCount=0;
 const rows=[.27,.46,.27],gap=7;let x=-sh.id/2;
 for(let row=0;row<3;row++){
  const dx=sh.id*rows[row],n=row===1?2:4;
  for(let k=0;k<n;k++){
   const ly=sh.il/n-gap,bx=dx-gap,cy=-sh.il/2+(k+.5)*sh.il/n,cxx=x+dx/2,g='tip-'+p.binCount;
   p.solid(g+'-dno',bx,ly,2,4,[cxx,cy,sh.floor],3,g);
   p.ring(g+'-dute-cire-steny',bx,ly,ht-15,4,[bx-4,ly-4,3],[cxx,cy,sh.floor+2],3,g);
   p.solid(g+'-uchop',3,ly*.62,4,1,[cxx+bx/2-3,cy,ht+f-5],5,g);
   p.tube(g+'-pant',[cxx+bx/2,cy-ly/2+3,sh.floor+6],[cxx+bx/2,cy+ly/2-3,sh.floor+6],1.6,2,g);
   p.binCount++;
  }x+=dx;
 }
 p.frontHandle(p.d/2-4,ht*.5,p.l*.37,p.h*.22,true);p.docking(0,p.d,p.l,'fixed',true);
 p.features.add('8 malých a 2 velké průhledné výklopné boxy');p.features.add('samostatné panty a úchyty boxů');
}
function rolling(p,chest=false){
 const q=p.r.inner[0].mm,diam=chest?230:228,ww=chest?60:48;
 // Source specifies wheel diameter. Position and width are photo reconstruction.
 const bd=chest?p.d*.92:p.d*.81,bl=chest?p.l*.87:p.l-ww*2;
 const z0=chest?35:30,lidH=30,zt=p.h-lidH-(!chest?32:0),ih=Math.min(q.height,zt-z0-5);
 const sh=p.shell('pojezdove-telo',bd,bl,z0,zt,q.width,q.length,ih,0);
 p.ribs(bd,bl,z0,zt,0,true);p.solid('pojezdove-viko',bd,bl,lidH*.72,9,[0,0,zt],0,'lid');p.docking(zt+lidH*.70,bd,bl,'lid');p.docking(0,bd,bl,'fixed',true);
 for(const y of [-bl*.32,bl*.32])p.latch(bd/2,y,zt-60,75);
 const wheelX=chest?-bd*.12:-bd*.40;for(const y of [-1,1])p.wheel(wheelX,y*(p.l/2-ww/2),diam,ww);
 p.frontHandle(bd/2-3,zt-55,bl*.35,35,true);
 p.label(bd/2+3,z0+(zt-z0)*.60,bl*.60);
 if(chest){
  // Chest pull handle slides on the short side, not a tall trolley handle.
  p.ring('bedna-vysuvne-madlo',p.d*.62,70,10,10,[p.d*.62-20,48,6],[0,-bl/2-20,zt-10],0,'handle');
  p.features.add('boční výsuvné madlo');
 }else{
  for(const y of [-bl*.27,bl*.27])p.solid('vozík-výsuvná-tyč-'+y,12,14,65,3,[-bd*.42,y,p.h-82],0,'handle');
  p.solid('vozík-červené-madlo',20,bl*.65,18,4,[-bd*.42,0,p.h-18],1,'handle');p.features.add('výsuvné madlo v přepravní poloze');
 }
 p.features.add('víko a spodní díl');
 p.equations.push(`Průměr kol ze zdroje: ${diam} mm; poloměr = ${diam}/2 = ${diam/2} mm. Šířka a poloha nejsou kótované.`);
}
function build(r,sku){
 const p=new Product(r,sku);
 if(sku==='4932471064')standard(p,'slim');
 else if(sku==='4932464082')standard(p,'organiser');
 else if(sku==='4932471065')standard(p,'compact');
 else if(sku==='4932478625')standard(p,'deep');
 else if(sku==='4932471724')crate(p);
 else if(['4932472129','4932472130','4932493189','4932493190'].includes(sku))drawer(p);
 else if(sku==='4932498651')drawer(p,true);
 else if(sku==='4932480623')cabinet(p);
 else if(sku==='4932498323')tip(p);
 else if(sku==='4932464078')rolling(p);
 else if(sku==='4932478161')rolling(p,true);
 else standard(p);
 return p.write();
}
function main(){
 for(const dir of [OUT,path.join(OUT,'modely'),path.join(ROOT,'mereni-tvar-v2'),path.join(ROOT,'obalky-v1')])fs.mkdirSync(dir,{recursive:true});
 // Preserve old dimension envelopes and v1 preview. Subsequent reruns must not
 // turn reconstructed product geometry into the old envelope backup.
 for(const r of catalog.records.filter(r=>r.group==='kufriky'))for(const sku of r.sku){
  const src=path.join(ROOT,'modely',sku+'.glb'),dst=path.join(ROOT,'obalky-v1',sku+'.glb');if(!fs.existsSync(dst))fs.copyFileSync(src,dst);
 }
 const rows=[],order=catalog.model_order.map(id=>catalog.records.find(r=>r.id===id));
 for(const r of order){
  const variants=r.sku.map(sku=>build(r,sku));rows.push(...variants);
  r.model_file=variants[0].file;r.model_status='vlastni_rekonstrukce_tvaru';r.detail_level='realny_tvar';r.detail_label='Reálný tvar · rekonstrukce z fotografií';
  r.physical_accuracy_verified=false;r.model_variants=variants;
  r.geometry_evidence={dimensions:'Vnější rozměry ze zdroje, obálka ověřena na všech vrcholech.',appearance:'Viditelné prvky rekonstruované podle fotografie konkrétního typu.',unverified:'Přesné poloměry, úkosy, tloušťky, skryté prvky, spojovací vůle a polohy detailů nejsou kótované.',photo_url:r.image.page_url};
  r.envelope.file='obalky-v1/'+r.sku[0]+'.glb';for(const v of r.envelope.variants)v.file='obalky-v1/'+v.sku+'.glb';
 }
 catalog.schema_version='2.1';catalog.stage_status='realne_tvary_fotograficka_rekonstrukce_presnost_detailu_neoverena';catalog.model_preview_url='https://autovestavby.logiman.cz/nahled-john/kufriky-milwaukee-modely-v2/';
 catalog.model_summary={types_in_scope:20,sku_in_scope:21,real_shape_models_ready:20,exact_models_ready:0,envelopes_ready:20,message:'20 typů / 21 SKU má vlastní reálný tvar podle fotografií. Obálka odpovídá zdroji; přesnost nekótovaných detailů a funkčních spojů není ověřená.'};
 fs.writeFileSync(path.join(ROOT,'kufriky.json'),JSON.stringify(catalog,null,2)+'\n');fs.writeFileSync(path.join(OUT,'kufriky.json'),JSON.stringify(catalog,null,2)+'\n');
 fs.writeFileSync(path.join(ROOT,'mereni-tvar-v2/prehled.json'),JSON.stringify(rows,null,2)+'\n');
 console.log('Reálné tvary: '+order.length+' typů / '+rows.length+' SKU. Max GLB: '+Math.max(...rows.map(r=>r.bytes))+' B.');
}
main();
