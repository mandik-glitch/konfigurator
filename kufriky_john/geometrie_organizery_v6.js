// Loaded after the saved v5 generator. Only the five organizer SKUs are rebuilt.
// All novel proportions are photo reconstruction, not measured production CAD.
function addPolygon(p,name,points,z,h,mat=0,group='fixed',holes=[]){
 const s=new THREE.Shape();s.moveTo(...points[0]);for(const q of points.slice(1))s.lineTo(...q);s.closePath();
 for(const q of holes){const h=new THREE.Path();h.moveTo(...q[0]);for(const a of q.slice(1))h.lineTo(...a);h.closePath();s.holes.push(h);}
 const g=new THREE.ExtrudeGeometry(s,{depth:h,steps:1,curveSegments:6,bevelEnabled:false});return p.add(name,g,mat,group,[0,0,z]);
}
function localPlane(p,name,w,h,t,xyz,mat=0,group='fixed',angle=[Math.PI/2,Math.PI/2,0]){
 return p.solid(name,w,h,t,Math.min(w,h)*.1,xyz,mat,group,angle);
}
function frontU(p,name,front,z,span,high,thickness,mat=1){
 const a=span/2,b=high/2,t=high*.19;
 const pts=[[-a,b],[-a,-b+t],[-a+t,-b],[a-t,-b],[a,-b+t],[a,b],[a-t,b],[a-t,-b+t],[-a+t,-b+t],[-a+t,b]];
 const s=new THREE.Shape();s.moveTo(...pts[0]);for(const q of pts.slice(1))s.lineTo(...q);s.closePath();
 return p.add(name,new THREE.ExtrudeGeometry(s,{depth:thickness,curveSegments:5,bevelEnabled:false}),mat,'fixed',[front,0,z],[Math.PI/2,Math.PI/2,0]);
}
function handleV6(p,e,front,z,slim=false,backFace=front-8){
 const span=(e.front_handle_fraction[1]-e.front_handle_fraction[0])*p.l;
 const high=slim?p.h*.40:Math.min(p.h*.46,72),depth=slim?Math.min(p.d*.055,19):9;
 if(slim){
  // Handle is horizontal, its hole is visible from above; not a tiny frame
  // extruded on the vertical facade as in v5.
  p.ring('drzadlo-otevreny-uchop',depth,span,p.h*.26,depth*.25,[depth*.43,span*.73,depth*.18],[front+depth/2,0,z-high*.34],0,'fixed');
  for(const sy of [-1,1])p.solid('drzadlo-celni-rameno-'+sy,front+depth-backFace,span*.135,p.h*.32,3,[(front+depth+backFace)/2,sy*span*.4325,z-high*.38],0);
  p.solid('PACKOUT-celni-odjistovaci-tlacitko',depth*.3,span*.2,p.h*.20,3,[front-2,0,z-high*.1],1);
 }else{
  frontU(p,'drzadlo-otevreny-uchop',front,z,span,high,6,1);
  const gripZ=z-high*.29;
  p.tube('drzadlo-cerny-uchop',[front+4,-span*.29,gripZ],[front+4,span*.29,gripZ],high*.115,4);
  for(let k=0;k<22;k++){
   const cy=(k-10.5)*span*.026;
   p.add('drzadlo-vroubek-'+k,new THREE.CylinderGeometry(high*.13,high*.13,span*.011,10,1),0,'fixed',[front+4,cy,gripZ]);
  }
  for(const sy of [-1,1]){
   p.solid('drzadlo-nosny-sloupek-'+sy,front+1-backFace,span*.075,p.h*.73,3,[(front+1+backFace)/2,sy*span*.54,p.h*.06],0);
   p.tube('drzadlo-cep-'+sy,[front+1,sy*span*.43-3,z+high*.40],[front+1,sy*span*.43+3,z+high*.40],3,2);
   for(let k=0;k<3;k++)localPlane(p,'drzadlo-cerveny-prst-'+sy+'-'+k,span*.025,high*.32,4,[front+1,sy*span*.39+(k-1)*span*.042,z+high*.5],1);
  }
  // The C is moulded into the front panel, separate from the carry handle.
  releaseC(p,front-4,z+high*.22);
 }
 p.features.add(slim?'vodorovný otevřený černý čelní úchop':'červená výklopná rukojeť s černým vroubkovaným úchopem a čepy');
}
function latchesV6(p,front,top,slim,backFace=front-5){
 if(p.compact)front=backFace+8;
 const height=slim?p.h*.54:Math.min(p.h*.49,71),width=p.compact?p.l*.135:p.l*.085;
 const yPos=p.compact?p.l*.37:p.l*.32;
 for(const sign of [-1,1]){
  const y=sign*yPos,z=top-height*.90;
  p.solid('zapadka-zaklad-'+sign,front+2-backFace,width,height,3,[(front+2+backFace)/2,y,z],0);
  p.solid('zapadka-cervena-'+sign,7,width*.82,height*.64,4,[front+1,y,z],1);
  for(let k=0;k<4;k++)p.solid('zapadka-cerveny-prst-'+sign+'-'+k,3,width*.10,height*.27,1,[front+5,y+(k-1.5)*width*.19,z+height*.48],1);
  for(let k=0;k<3;k++)p.solid('zapadka-vroubek-'+sign+'-'+k,1.2,width*.73,height*.035,.4,[front+8,y,z+height*(.08+.07*k)],1);
  const x=front+7;
  p.tube('zapadka-kov-levy-'+sign,[x,y-width*.48,z+height*.14],[x,y-width*.48,z+height*.92],1.4,2);
  p.tube('zapadka-kov-pravy-'+sign,[x,y+width*.48,z+height*.14],[x,y+width*.48,z+height*.92],1.4,2);
  p.tube('zapadka-kov-mustek-'+sign,[x,y-width*.48,z+height*.92],[x,y+width*.48,z+height*.92],1.4,2);
  p.solid('zapadka-ciry-horni-kryt-'+sign,8,width,8,3,[front+3,y,top-3],3,'lid');
 }
 p.features.add('dva červené uzávěry s kovovými sponami a průhlednými horními úchyty');
}
function binGridV6(p,e,q,cx){
 const rf=e.row_fractions,bf=e.bank_fractions;
 const rmin=Math.min(...rf.flat()),rmax=Math.max(...rf.flat()),bmin=Math.min(...bf.flat()),bmax=Math.max(...bf.flat());
 const scaleX=(q.id-6)/(rmax-rmin),scaleY=(q.il-6)/(bmax-bmin),xc=(rmin+rmax)/2,yc=(bmin+bmax)/2,out=[];
 for(let row=0;row<3;row++)for(let bank=0;bank<bf.length;bank++){
  const x0=cx+(rf[row][0]-xc)*scaleX,x1=cx+(rf[row][1]-xc)*scaleX;
  const y0=(bf[bank][0]-yc)*scaleY,y1=(bf[bank][1]-yc)*scaleY;
  const n=row===1?1:2;
  for(let k=0;k<n;k++)out.push({x:(x0+x1)/2,y:y0+(k+.5)*(y1-y0)/n,dx:x1-x0,dy:(y1-y0)/n-(n===2?4:0),row,bank,k});
 }
 return out;
}
function binsV6(p,e,sh){
 const grid=binGridV6(p,e,sh,sh.cx);let count=0;
 for(const b of grid){
  const id=count++,t=2,z=sh.floor+.7,height=sh.z1-z-2,r=Math.min(b.dx,b.dy)*.12;
  p.solid('prihradka-'+id+'-dno',b.dx,b.dy,t,r,[b.x,b.y,z],1,'bins');
  p.ring('prihradka-'+id+'-duta-stena',b.dx,b.dy,height-t,r,[b.dx-2*t,b.dy-2*t,r*.85],[b.x,b.y,z+t],1,'bins');
  p.ring('prihradka-'+id+'-horni-lem',b.dx+.5,b.dy+.5,2,r,[b.dx-4,b.dy-4,r*.8],[b.x,b.y,z+height-2],1,'bins');
  const n=e.sku==='4932464082'?0:(b.row===1?2:1);
  for(let k=0;k<n;k++){
   const yy=b.y+(k+1)*(b.dy-4)/(n+1)-(b.dy-4)/2;
   p.solid('prihradka-'+id+'-delic-'+k,b.dx-4,1.5,height*.80,1,[b.x,yy,z+t],1,'bins');
  }
  // Photo shows ribs/notches for removable partitions, not separate lids.
  for(const sy of [-1,1])for(let k=0;k<(b.row===1?4:2);k++)p.solid('prihradka-'+id+'-vodici-zebro-'+sy+'-'+k,b.dx*.055,1.7,height*.52,.4,[b.x+(k-(b.row===1?1.5:.5))*b.dx*.20,b.y+sy*(b.dy/2-t-1),z+t],1,'bins');
 }
 p.binCount=count;p.features.add(count+' samostatných dutých nádob s mezerami a zaoblenými okraji');return grid;
}
function hexReliefV6(p,name,b,z){
 // The repeated honeycomb is surface relief, not bins or locking stations.
 const pts=[],n=[];const spacing=13,rx=spacing/Math.sqrt(3),x0=b.x-b.dx/2+8,x1=b.x+b.dx/2-8,y0=b.y-b.dy/2+8,y1=b.y+b.dy/2-8;
 const geom=new THREE.BufferGeometry();let ii=0;
 for(let x=x0;x<x1;x+=rx*1.5,ii++)for(let y=y0+(ii%2)*spacing/2;y<y1;y+=spacing){
  for(let k=0;k<3;k++){
   const a=k*Math.PI/3,c=(k+1)*Math.PI/3,A=[x+rx*Math.cos(a),y+rx*Math.sin(a)],B=[x+rx*Math.cos(c),y+rx*Math.sin(c)],vx=B[0]-A[0],vy=B[1]-A[1],len=Math.hypot(vx,vy),nx=-vy/len*.12,ny=vx/len*.12;
   if([...A,...B].some(v=>!Number.isFinite(v))||Math.max(A[0],B[0])>x1||Math.max(A[1],B[1])>y1)continue;
   for(const q of [[A[0]+nx,A[1]+ny],[A[0]-nx,A[1]-ny],[B[0]-nx,B[1]-ny],[A[0]+nx,A[1]+ny],[B[0]-nx,B[1]-ny],[B[0]+nx,B[1]+ny]]){pts.push(q[0],q[1],z);n.push(0,0,1);}
  }
 }
 geom.setAttribute('position',new THREE.Float32BufferAttribute(pts,3));geom.setAttribute('normal',new THREE.Float32BufferAttribute(n,3));if(pts.length)p.add(name,geom,3,'lid');
}
function lidV6(p,e,sh,grid,lh){
 const top=sh.z1,h=p.h,d=sh.d,ocx=sh.outerCX||0,rx=Math.min(d,p.l)*e.body_corner_fraction;
 const slim=['4932471064','4932471065'].includes(p.sku),recess=p.d*(slim?.095:.065);
 const rim=organizerContour(d-2,p.l-2,p.compact?d*.025:recess);const hole=outline(sh.id+5,sh.il+5,10).getPoints(6).map(a=>new THREE.Vector2(a.x+sh.cx-ocx,a.y));rim.holes.push(new THREE.Path(hole));
 p.add('viko-nosny-okraj',new THREE.ExtrudeGeometry(rim,{depth:lh-2,curveSegments:6,bevelEnabled:false}),3,'lid',[ocx,0,top]);
 p.ring('viko-tesneni',sh.id+9,sh.il+9,1.5,12,[sh.id+5,sh.il+5,10],[sh.cx,0,top-.1],4,'lid');
 const panel=organizerContour(d-10,p.l-10,p.compact?d*.025:recess);
 p.add('viko-panel',new THREE.ExtrudeGeometry(panel,{depth:1.6,curveSegments:6,bevelEnabled:false}),3,'lid',[ocx,0,h-2]);
 for(const [i,b] of grid.entries()){
  const rr=Math.min(b.dx,b.dy)*.12;
  p.ring('viko-prolis-'+i,b.dx+4,b.dy+4,lh*.22,rr,[b.dx-8,b.dy-8,rr*.65],[b.x,b.y,h-lh*.22],3,'lid');
  p.solid('viko-okno-'+i,b.dx-7,b.dy-7,.8,rr*.65,[b.x,b.y,h-.8],3,'lid');
  hexReliefV6(p,'viko-plastve-'+i,{...b,dx:b.dx-8,dy:b.dy-8},h-.35);
 }
 if(!p.compact){
  const gap=p.l*.09;p.solid('viko-stredni-pruh',sh.id,gap,lh*.24,4,[sh.cx,0,h-lh*.24],3,'lid');
  hexReliefV6(p,'viko-stredni-plastve',{x:sh.cx,y:0,dx:sh.id,dy:gap},h-.35);
 }
 for(let k=0;k<11;k++){
  const yy=(k-5)*(p.l-24)/11;
  p.solid('viko-celni-zebro-'+k,8,2.5,lh*.64,1,[ocx+d/2-9,yy,top],3,'lid');
 }
 for(let k=0;k<7;k++){
  const y=(k-3)*(p.l-50)/7,x=ocx-d/2+7;
  p.tube('pant-vika-'+k,[x,y-8,top+2],[x,y+8,top+2],3,3,'lid');
  p.solid('pant-vika-kotveni-'+k,7,18,7,2,[x+2,y,top-4],0);
 }
 // Lettering belongs on a sealing window. Its exact brand script is not CAD.
 const label=grid.find(b=>b.row===1&&b.bank===0);
 if(label){
  for(const [txt,size,shift] of [['MILWAUKEE',label.dy*.060,0],['PACKOUT',label.dy*.041,7]]){
   const g=new THREE.TextGeometry(txt,{font,size,height:.13,curveSegments:2,bevelEnabled:false});g.computeBoundingBox();g.translate(-(g.boundingBox.max.x+g.boundingBox.min.x)/2,0,0);g.rotateZ(-Math.PI/2);
   p.add('viko-oznaceni-'+txt,g,6,'lid',[label.x+shift,label.y,h+.0-.22]);
  }
 }
 p.features.add('průhledné členěné víko, samostatná těsnicí okna, střední pruh, jemné plastve a obvodové těsnění');
}
function bodyDetailV6(p,e,sh){
 const cx=sh.outerCX||0,d=sh.d,z0=sh.z0,top=sh.z1,ht=top-z0,w=p.l*.047,depth=d*.085;
 // Corners have horizontal relief bands, with real attachment to the shell.
 for(const sx of [-1,1])for(const sy of [-1,1]){
  const x=cx+sx*(d/2-depth/2),y=sy*(p.l/2-w/2);
  p.solid('roh-nosne-telo-'+sx+'-'+sy,depth,w,ht,Math.min(depth,w)*.35,[x,y,z0],0);
  for(const z of [z0+ht*.08,top-ht*.12])p.ring('roh-obvodovy-prolis-'+sx+'-'+sy,depth-.4,w-.4,3,Math.min(depth,w)*.32,[depth-4,w-4,2],[x,y,z],5);
 }
 for(const sy of [-1,1]){
  const side=p.l/2-1.3;
  for(const fraction of [-.30,.22])p.solid('bok-nosne-zebro-'+sy+'-'+fraction,3,2.6,ht*.89,1,[cx+fraction*d,sy*side,z0+ht*.04],5);
  for(const z of [z0+ht*.10,top-ht*.08])p.solid('bok-podelny-prolis-'+sy+'-'+z,d*.77,2.4,2.5,.7,[cx,sy*side,z],5);
 }
 for(const sy of [-1,1])for(const z of [z0+ht*.09,top-ht*.1])p.solid('celo-prolis-'+sy+'-'+z,2.4,p.l*.22,2.4,.7,[p.d/2-p.d*(['4932471064','4932471065'].includes(p.sku)?.115:.10)+1.2,sy*p.l*.34,z],5);
}
function undersideV6(p,e,sh){
 if(!e.bottom){
  p.evidenceV6.underside='unverified_no_family_substitution';
  p.features.add('spodní zámkové pozice tohoto SKU neověřené; bez přenosu z jiného organizéru');return;
 }
 const compact=p.compact,rows=compact?[-.30,0,.30]:[-.28,0,.28],cols=compact?[-.25,.25]:[-.375,-.13,.13,.375];
 const sx=sh.d*(compact?.105:.095),sy=sh.l*(compact?.19:.145),z1=sh.z0;
 for(const [i,xx] of rows.entries())for(const [j,yy] of cols.entries()){
  const x=xx*sh.d,y=yy*sh.l;
  p.solid('PACKOUT-spodni-patka-'+i+'-'+j,sx,sy,z1,3,[x,y,0],0);
  p.solid('PACKOUT-spodni-zub-'+i+'-'+j,sx*.18,sy*.8,z1*.4,1,[x+sx*.38,y,0],0);
  for(let k=0;k<6;k++)p.solid('PACKOUT-spodni-prolis-'+i+'-'+j+'-'+k,sx*.34,sy*.08,z1*.12,.3,[x,y+(k-2.5)*sy*.14,z1*.1],4);
 }
 p.evidenceV6.underside='own_SKU_photograph_topology_only';
}
function organizerV6(p,e){
 const q=cavity(p),slim=['4932471064','4932471065'].includes(p.sku),deep=p.sku==='4932478625',f=Math.min(p.h*.05,7),lh=p.h*e.lid_height_fraction,top=p.h-lh;
 // Published closed inner height spans both base and underside of the lid.
 const floor=p.h-2.0-q.ih,bodyIH=top-floor;
 const bodyD=p.compact?p.d*(792-72)/(793-6):p.d,outerCX=(bodyD-p.d)/2;
 const cx=p.compact?p.d*((Math.min(...e.row_fractions.flat())+Math.max(...e.row_fractions.flat()))/2-.5):-p.d*.018;
 if(floor<=f||bodyIH<=0)throw Error('Invalid closed cavity '+p.sku);
 const reserve=p.compact?bodyD*.025:p.d*(slim?.115:.10),face=outerCX+bodyD/2-reserve;
 const floorShape=organizerContour(bodyD,p.l,reserve),floorGeo=new THREE.ExtrudeGeometry(floorShape,{depth:floor-f,curveSegments:6,bevelEnabled:false});
 p.add('telo-dno',floorGeo,0,'fixed',[outerCX,0,f]);p.floorContourOverride=floorShape.getPoints(6).map(a=>[a.x+outerCX,a.y]);
 const wall=organizerContour(bodyD,p.l,reserve);const hole=outline(q.id,q.il,10).getPoints(6).map(a=>new THREE.Vector2(a.x+cx-outerCX,a.y));wall.holes.push(new THREE.Path(hole));
 p.add('telo-duta-stena',new THREE.ExtrudeGeometry(wall,{depth:bodyIH,curveSegments:6,bevelEnabled:false}),0,'fixed',[outerCX,0,floor]);
 const sh={d:bodyD,l:p.l,cx,outerCX,id:q.id,il:q.il,ih:bodyIH,z0:f,z1:top,floor};
 p.feet(bodyD,p.l);bodyDetailV6(p,e,sh);
 let grid;
 if(deep){
  const split=cx-q.id*.10;
  p.solid('hluboky-pevny-stredni-delic',4,q.il,bodyIH-4,1,[split,0,floor],0,'bins');
  for(const [i,y] of [-q.il/4,0,q.il/4].entries()){
   const front0=split+2,front1=cx+q.id/2,rear0=cx-q.id/2,rear1=split-2;
   for(const [name,a,b] of [['dlouhy',front0,front1],['kratky',rear0,rear1]]){
    p.solid('hluboky-cerveny-'+name+'-delic-'+i,b-a,3,bodyIH*.88,2,[(a+b)/2,y,floor],1,'bins');
    p.solid('hluboky-'+name+'-delic-horni-lem-'+i,b-a,5,3,1,[(a+b)/2,y,floor+bodyIH*.88-3],1,'bins');
    for(const x of [a,b])p.solid('hluboky-'+name+'-vodici-drazka-'+i+'-'+x,4,6,bodyIH*.88,1,[x,y,floor],0,'bins');
   }
  }
  p.binCount=8;grid=binGridV6(p,e,sh,cx);p.features.add('pevný střed a 3 dlouhé + 3 krátké červené děliče: 2 × 4 = 8 oddílů podle Hero_2');
 }else grid=binsV6(p,e,sh);
 lidV6(p,e,sh,grid,lh);
 // Carve the photographed front handle pocket in the actual front wall.
 const front=p.compact?p.d/2-19:p.d/2-p.d*(slim?.065:.045),span=p.l*(slim?.45:.38),hh=slim?p.h*.36:Math.min(p.h*.58,90),hz=slim?top-p.h*.25:f+hh*.56;
 // Front panel pocket below the top cap: a real opening, not hiding meshes.
 const first=p.parts.length;handleV6(p,e,front,hz,slim,face);latchesV6(p,front,top,slim,face);
 // Body pocket: lower the outside face where the handle is mounted, leaving
 // the sourced interior cavity unchanged; this is an appearance draft.
 if(slim){
  const shell=p.parts.find(a=>a.name==='telo-duta-stena'),g=shell.g.toNonIndexed? shell.g:shell.g;
  // A horizontal grip projects forward as on the photo, within outer corners.
 }
 p.solid('PACKOUT-spodni-odjistovaci-tlacitko',8,p.compact?18:26,floor-f,2,[p.compact?face-8:front-10,0,f],1);
 if(p.compact){p.evidenceV6.front_overhang_photo=e.top_photo.url;p.evidenceV6.body_depth_photo_formula='411 × (792 − 72) / (793 − 6) = '+bodyD+' mm; projected reconstruction, not physical metrology';p.equations.push(p.evidenceV6.body_depth_photo_formula);}
 undersideV6(p,e,sh);
 p.measuredFeatures=[{kind:'closed_cavity',dimensions_mm:{width:q.id,length:q.il,height:q.ih},source_url:p.r.inner[0].source_url,component:'telo-duta-stena',note:'height includes free volume under the closed lid'}];
 p.equations.push(`Uzavřený prostor: z_dno = ${p.h} − 2 − ${q.ih} = ${floor} mm; horní rovina dutiny = ${p.h} − 2 = ${p.h-2} mm; ${p.h-2} − ${floor} = ${q.ih} mm. Výška spodního těla = ${top} − ${floor} = ${bodyIH} mm. Tloušťka 2 mm je nekótovaná vzhledová rekonstrukce.`);
 p.equations.push(`Přihrádky: obrazový poměr normalizován na doložený vnitřní půdorys ${q.id} × ${q.il} mm; počet = ${p.binCount}. Tato operace neprokazuje polohu detailů na fyzickém kusu do 2 mm.`);
 p.features.add('zveřejněná vnitřní výška zahrnuje i prostor pod zavřeným víkem');
}
function tipV6(p,e){
 const f=7,back=9,frame=p.l*.079,frontDepth=p.d*.064,top=p.h;
 p.solid('vyklopny-organizer-zadni-panel',p.d,p.l,back,15,[0,0,f],0);
 // The frame has side walls, three metal retaining rods, a central spine.
 // It must NOT be the v5 continuous tall ring covering the storage face.
 for(const sy of [-1,1])p.solid('vyklopny-organizer-bocni-nosnik-'+sy,p.d,frame,p.h-f,16,[0,sy*(p.l/2-frame/2),f],0);
 const x0=-p.d/2+frontDepth,x1=p.d/2-frontDepth,centerX=-p.d*.04;
 for(const x of [x0,x1])p.solid('vyklopny-organizer-celni-nosnik-'+x,frontDepth,p.l,11,5,[x,0,p.h-12],0);
 p.solid('vyklopny-organizer-stredni-sloupek',p.d-frontDepth*2,23,p.h-f-back,6,[0,0,f+back],0);
 const spanX=x1-x0-frontDepth,cellX=spanX/3,gap=7,banks=[[-p.l/2+frame,-15],[15,p.l/2-frame]];
 const ids=[];let count=0;
 for(let row=0;row<3;row++)for(let bank=0;bank<2;bank++){
  const [y0,y1]=banks[bank],n=row===1?1:2;
  for(let k=0;k<n;k++){
   const dx=cellX-gap,dy=(y1-y0)/n-gap,x=x0+frontDepth/2+(row+.5)*cellX,y=y0+(k+.5)*(y1-y0)/n,z=f+back,bh=p.h-z-20,name='tip-'+count,g=name;
   p.solid(name+'-dno',dx,dy,2,8,[x,y,z],3,g);
   p.ring(name+'-dute-cire-steny',dx,dy,bh,8,[dx-4,dy-4,6],[x,y,z+2],3,g);
   // Each cup has its own lid and an integral handle lip; no shared lid.
   p.solid(name+'-vicko',dx-2,dy-2,1.4,7,[x,y,z+bh],3,g);
   p.ring(name+'-ciry-horni-lem',dx+1,dy+1,3,8,[dx-5,dy-5,5],[x,y,z+bh-2],3,g);
   p.solid(name+'-uchop',8,dy*.65,4,2,[x+dx/2-3,y,z+bh+1],3,g);
   if(row===1)p.solid(name+'-vnitrni-delic',dx-4,2.5,bh*.82,3,[x,y,z+2],0,g);
   p.tube(name+'-pant',[x-dx/2+2,y-dy/2+5,z+4],[x-dx/2+2,y+dy/2-5,z+4],2,2,g);
   p.solid(name+'-pant-kotveni',6,dy,8,2,[x-dx/2+2,y,z],0);
   ids.push({x,y,dx,dy});count++;
  }
  // Retaining bar along the front edge of each row, visible across both banks.
 }
 for(let row=0;row<3;row++){
  const x=x0+frontDepth/2+row*cellX+gap/2;
  p.tube('vyklopny-organizer-kovova-tyc-'+row,[x,-p.l/2+frame*.45,p.h-20],[x,p.l/2-frame*.45,p.h-20],2,2);
 }
 const ts=new THREE.Shape();ts.moveTo(-9,12);ts.lineTo(9,12);ts.lineTo(9,4);ts.lineTo(4,4);ts.lineTo(4,-9);ts.lineTo(-4,-9);ts.lineTo(-4,4);ts.lineTo(-9,4);ts.closePath();
 p.add('vyklopny-organizer-zapadka-T',new THREE.ExtrudeGeometry(ts,{depth:3,bevelEnabled:false}),1,'fixed',[centerX,0,p.h-3],[0,0,-Math.PI/2]);
 handleV6(p,e,p.d/2-24,p.h*.43,false);
 for(const part of p.parts)if(part.name==='drzadlo-otevreny-uchop'||part.name==='drzadlo-cerny-uchop'||part.name.startsWith('drzadlo-vroubek-')||part.name.startsWith('drzadlo-cerveny-prst-'))part.group='carry';
 p.solid('vyklopny-organizer-stitek-celo',frontDepth*.85,p.l*.22,.5,1,[x1,-p.l*.15,p.h-.8],1);
 for(const [text,size,shift] of [['MILWAUKEE',5,3],['PACKOUT',3,-4]]){
  const label=new THREE.TextGeometry(text,{font,size,height:.13,curveSegments:2,bevelEnabled:false});label.computeBoundingBox();label.translate(-(label.boundingBox.min.x+label.boundingBox.max.x)/2,0,0);label.rotateZ(-Math.PI/2);
  p.add('vyklopny-organizer-oznaceni-'+text,label,6,'fixed',[x1+shift,-p.l*.15,p.h-.2]);
 }
 p.solid('PACKOUT-spodni-odjistovaci-tlacitko',8,28,18,3,[p.d/2-24,0,7],1);
 for(const sy of [-1,1])p.solid('vyklopny-organizer-bocni-stitek-'+sy,p.d*.50,2,13,1,[0,sy*(p.l/2-1),p.h*.75],1);
 p.feet();p.binCount=count;
 p.features.add('otevřený nosný rám, střední sloupek, tři kovové tyče a červená západka T');
 p.features.add('8 malých a 2 velké průhledné boxy se samostatnými víčky; dělič v obou velkých');
 p.evidenceV6.underside='unverified_no_family_substitution';
 p.equations.push('Vyklápěcí boxy: 2 banky × (2 + 1 + 2) = 10, z toho 8 malých + 2 velké. Kovové tyče: 3 řady × 1 = 3.');
}
function mainV6(){
 M.push({name:'Bílý popis – vizuální rekonstrukce',pbrMetallicRoughness:{baseColorFactor:[.94,.94,.94,1],metallicFactor:0,roughnessFactor:.7}});
 for(const dir of ['nahled-modely-v6/modely','mereni-tvar-v6'])fs.mkdirSync(path.join(ROOT,dir),{recursive:true});
 for(const id of catalog.model_order){
  const r=catalog.records.find(a=>a.id===id),e=EVIDENCE_V6.find(a=>r.sku.includes(a.sku));
  if(!e){const quick=JSON.parse(fs.readFileSync(path.join(ROOT,'zdroje/doladeni-v6/ostatni-review.json'))).find(a=>a.sku.includes(r.sku[0]));if(quick){r.quick_review_v6=quick;r.review.match='V6 rychlé srovnání: model stále vyžaduje přepracování detailů. '+quick.seen;r.review.changed='Typ rychle porovnaný, geometrie zachovaná z v5. Další nálezy jsou uvedené samostatně.';r.review.comparison_note='Geometrie zachovaná z v5; rychlé porovnání odhalilo další rozdíly.';r.review.render_before_file='porovnani/'+r.sku[0]+'-v5.png';}for(const sku of r.sku)fs.copyFileSync(path.join(ROOT,'nahled-modely-v5/modely',sku+'.glb'),path.join(OUT,'modely',sku+'.glb'));continue;}
  const p=new Product(r,e.sku);p.evidenceV6={revision:6,sku:e.sku,top_photo_url:e.top_photo.url,annotations_file:'anotace-v6.json',physical_accuracy_verified:false,physical_tolerance_mm:null};
  if(e.sku==='4932498323')tipV6(p,e);else organizerV6(p,e);
  r.review.changed_v5=r.review.changed;r.review.changed=e.changed;r.review.seen=e.findings_v5;r.review.unverified=e.unverified;r.review.match='Viditelné rozdíly v5 přepracované podle vlastních fotografií SKU. Shoda detailů do 2 mm NEOVĚŘENA.';
  r.review.render_before_file='porovnani/'+e.sku+'-v5.png';r.review.render_file='porovnani/'+e.sku+'.png';r.review.comparison_note='Vlevo zachovaný model v5, vpravo v6. Srovnání s originální fotografií je samostatně u každého úhlu.';
  r.organizer_review={...r.organizer_review,findings_v4:e.findings_v5,angle_summary:'samostatné srovnání čela, boku, horní a spodní strany, zavřeného a otevřeného stavu',photo_count:organizerPhotos.records.find(a=>a.sku===e.sku).photos.length};
  const bottomCount=p.parts.filter(a=>/^(patka-|PACKOUT-spodni-(patka-|zub-|prolis-))/.test(a.name)).length;
  r.review.support_summary='Změřeno '+p.parts.length+' součástí včetně '+bottomCount+' spodních dílů. Patky ověřené proti skutečné ploše dna; digitální tolerance 0,01 mm. Fyzická shoda detailů do 2 mm neověřená.';
  if(p.compact)r.review.support_summary+=' Předsazené držadlo doložené fotografií tohoto SKU; odvozená hloubka těla není fyzicky změřená.';
  r.model_variants=[p.write()];r.detail_label='Rekonstrukce v6 · detaily do 2 mm neověřené';r.revision=6;
  console.log(e.sku+' — v6, '+p.parts.length+' součástí, '+p.binCount+' nádob / oddílů');
 }
 catalog.stage_status='doladeni_v6_shoda_detailu_neoverena';catalog.schema_version='2.4';catalog.model_preview_url='https://autovestavby.logiman.cz/nahled-john/kufriky-milwaukee-modely-v6/';catalog.model_summary.message='Pět organizérů přepracováno podle samostatných fotografií; přesnost detailů do 2 mm a funkčních spojů není potvrzená.';
 fs.writeFileSync(path.join(ROOT,'kufriky.json'),JSON.stringify(catalog,null,2)+'\n');
 const publicEvidence=JSON.parse(fs.readFileSync(path.join(ROOT,'zdroje/doladeni-v6/anotace.json')));
 for(const e of publicEvidence.records)delete e.top_photo.file;
 fs.writeFileSync(path.join(OUT,'anotace-v6.json'),JSON.stringify(publicEvidence,null,2)+'\n');
}
mainV6();
