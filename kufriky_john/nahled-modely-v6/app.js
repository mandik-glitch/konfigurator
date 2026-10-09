"use strict";
(() => {
 const comparisons=window.KUFRIKY_COMPARISONS||{};function renderPhotoPairs(r){const area=document.getElementById('photo-model-pairs');if(!area)return;area.replaceChildren();document.getElementById('comparison-page').href='srovnani.html#'+r.sku[0];for(const pair of comparisons[r.sku[0]]||[]){const div=document.createElement('div');div.className='photo-model-pair';const f=document.createElement('figure'),title=document.createElement('figcaption');title.textContent=pair.label;f.append(title);if(pair.photo_url){const a=document.createElement('a');a.className='photo-external';a.href=pair.photo_url;a.target='_blank';a.rel='noopener noreferrer';a.textContent='Otevřít původní fotografii ↗';f.append(a);}else{const text=document.createElement('p');text.textContent='Fotografie tohoto pohledu pro toto SKU chybí – neověřeno.';f.append(text);}const note=document.createElement('p');note.textContent=pair.alignment;f.append(note);const g=document.createElement('figure'),im=document.createElement('img');im.src=pair.render_file;im.alt=r.name+' · '+pair.label+' · model v6';im.loading='lazy';const a=document.createElement('a');a.href=pair.render_file;a.target='_blank';a.append(im);g.append(a);const caption=document.createElement('figcaption');caption.textContent='Náš model v6 · '+pair.label;g.append(caption);div.append(f,g);area.append(div);}}const data=window.KUFRIKY_MODELY,records=data.records,$=id=>document.getElementById(id);
 const plain=s=>String(s).normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();
 const node=(tag,txt,cls)=>{const e=document.createElement(tag);if(txt!=null)e.textContent=txt;if(cls)e.className=cls;return e;};
 const link=(url,txt)=>{const a=node('a',txt);a.href=url;a.target='_blank';a.rel='noopener noreferrer';return a;};
 let tipOpenSlots=null;let meta=null,captureMode=false;let originalMaterials=new Map(),bottomLight;
 let current=records[0],loaded=null,model=null,lines=null,outline=null,labels=[],renderer,scene,camera,controls,view='iso',error=null,groups=[],closedBox=null,generation=0;
 const payloadPromises=new Map();
 function payload(sku){
  if(window.KUFRIKY_MODEL_PAYLOADS[sku])return Promise.resolve(window.KUFRIKY_MODEL_PAYLOADS[sku]);
  if(payloadPromises.has(sku))return payloadPromises.get(sku);
  const promise=new Promise((resolve,reject)=>{const s=document.createElement('script');s.src='modely/'+sku+'.js';s.onload=()=>resolve(window.KUFRIKY_MODEL_PAYLOADS[sku]);s.onerror=()=>reject(Error('Model se nepodařilo načíst.'));document.head.append(s);});
  payloadPromises.set(sku,promise);return promise;
 }
 function list(){
  const found=records.filter(r=>plain(r.name+' '+r.sku.join(' ')).includes(plain($('search').value)));$('types').replaceChildren();$('empty').hidden=found.length>0;
  for(const r of found){const b=node('button',null,'type'+(r.id===current.id?' active':''));b.type='button';b.dataset.sku=r.sku[0];b.setAttribute('aria-pressed',r.id===current.id);const img=node('img');img.src=r.review.render_file;img.alt='';const t=node('span');t.append(node('strong',r.name),node('small',r.sku.join(' / ')),node('small','Reálný tvar · vlastní','detail-state'));b.append(img,t);b.onclick=()=>select(r);$('types').append(b);}
 }
 for(const r of records){const o=node('option',r.name+' · '+r.sku[0]);o.value=r.sku[0];$('type-select').append(o);}
 $('type-select').onchange=()=>select(records.find(r=>r.sku.includes($('type-select').value)));$('search').oninput=list;
 function select(r){
  current=r;loaded=null;renderPhotoPairs(r);error=null;generation++;$('viewer-error').hidden=true;
  $('type-select').value=r.sku[0];$('name').textContent=r.name;$('sku').textContent=r.sku.join(' / ');$('detail-badge').textContent='Vlastní · '+r.detail_label;
  tipOpenSlots=null;$('open').checked=false;$('carry-raised').checked=false;$('carry-raised').disabled=r.sku[0]!=='4932498323';$('hide-lid').checked=false;$('bottom').checked=false;$('photo-view').checked=false;$('parts-colors').checked=false;$('parts-legend').replaceChildren();
  const d=r.outer.mm;$('dimensions-summary').replaceChildren();for(const [label,k] of [['Délka','length'],['Šířka','width'],['Výška','height']]){const e=node('div');e.append(node('small',label),node('strong',d[k]),node('span','mm'));$('dimensions-summary').append(e);}
  $('photo').src=r.review.render_file;$('photo').alt=r.name+' — vlastní render';$('photo-source').href=r.review.source_photo_url;
  $('support-summary').textContent=r.review.support_summary||'Probíhá kontrola všech spodních dílů.';
  $('control-views').replaceChildren(...(r.organizer_review?['front','back','side','sideOther','top','bottom','isoFrontRight','isoFrontLeft','isoBackRight','isoBackLeft']:['front','side','sideOther','top','bottom']).map((v,i)=>{const f=node('figure'),im=node('img');im.src='kontrola/'+r.sku[0]+'-'+v+'.png';im.alt=(r.organizer_review?['Čelo','Zezadu','Pravý bok','Levý bok','Shora','Zespodu','Šikmo přední pravý','Šikmo přední levý','Šikmo zadní pravý','Šikmo zadní levý']:['Čelo','Pravý bok','Levý bok','Shora','Zespodu'])[i];im.loading='lazy';f.append(im,node('figcaption',im.alt+' · v6'));return f;}));
  $('color-views').replaceChildren(...(r.organizer_review?['side','sideOther'].map((v,i)=>{const f=node('figure'),im=node('img');im.src='kontrola/'+r.sku[0]+'-'+v+'-casti.png';im.alt=(i?'Levý':'Pravý')+' bok s rozlišenými součástmi';im.loading='lazy';f.append(im,node('figcaption',im.alt));return f;}):[]));
  $('match').textContent=r.review.match;$('seen').textContent='Vidím na fotografiích: '+r.review.seen;$('changed').textContent=(r.organizer_review?'Dříve: '+r.organizer_review.findings_v4+' ':'')+'Opraveno: '+r.review.changed+(r.organizer_review?' Použito '+r.organizer_review.photo_count+' snímků / zdrojů: '+r.organizer_review.angle_summary+'.':'');$('comparison-note').textContent=r.review.comparison_note;
  $('render-before').src=r.review.render_before_file;$('render-after').src=r.review.render_file;
  $('review-unverified').replaceChildren(...r.review.unverified.map(x=>node('li',x)));$('photo-links').replaceChildren(...r.photo_sources.map((p,i)=>{const li=node('li');li.append(link(p.url,(i+1)+'. '+p.kind+' · fotografie ↗'),node('span',' · '),link(p.page_url,'Produktová stránka ↗'));return li;}));$('source').href=r.outer.source_url;
  $('raw-dimensions').textContent=r.outer.raw+' mm ('+r.outer.raw_order+'). '+r.outer.formula;
  $('verification').textContent='Kontrola všech vrcholů modelu při načtení. Kóty odpovídají zavřenému modelu v přepravní poloze.';
  $('hardware').textContent=r.hardware.text;$('sales').replaceChildren();for(const s of r.sales){const p=node('div',null,'sale');p.append(link(s.url,s.country+' · '+s.seller+' ↗'),node('span',' · '+s.price_net+' '+s.currency+' bez DPH · '+s.sku));$('sales').append(p);}
  $('conflicts').replaceChildren();for(const s of r.notes)$('conflicts').append(node('p',s));for(const s of r.observations){const p=node('p',s.text);p.append(link(s.source_url,'Zdroj ↗'));$('conflicts').append(p);}
  $('missing').replaceChildren(...r.missing_geometry.map(i=>node('li',i.text)));$('features').textContent=r.model_variants[0].features.join(' · ');
  const v=r.model_variants[0];$('model-stats').textContent=v.part_count+' částí · '+(v.bytes/1e6).toFixed(2).replace('.',',')+' MB'+(v.bin_count?' · '+v.bin_count+' přihrádek':'');
  $('model-download').href=r.model_file;$('model-download').download=r.sku[0]+'.glb';list();if(renderer)load(r,generation);history.replaceState(null,'','#'+r.sku[0]);
 }
 for(const r of records){const tr=node('tr'),cell=node('td');cell.append(link('#'+r.sku[0],r.name+' · '+r.sku.join(' / ')));cell.firstChild.target='';cell.firstChild.onclick=e=>{e.preventDefault();select(r);$('viewer').scrollIntoView({behavior:'smooth',block:'center'});};tr.append(cell,node('td','Reálný tvar · vlastní'),node('td',(r.model_variants[0].bytes/1e6).toFixed(2)+' MB'),node('td',(r.organizer_review?r.organizer_review.findings_v4+' Použito '+r.organizer_review.photo_count+' snímků / zdrojů: '+r.organizer_review.angle_summary+'. ':'')+r.review.changed+' '+(r.review.support_summary||'')+' '+r.review.match+' '+r.review.unverified.join(' ')));$('status-rows').append(tr);}
 for(const c of data.cad_sources){const e=node('div',null,'candidate');e.append(link(c.url,c.name+' ↗'),node('p',c.license),node('p',c.access),node('p',c.decision));$('cad-sources').append(e);}
 $('photo').onclick=()=>{$('large-photo').src=current.review.render_file;$('large-photo').alt=current.name;$('photo-dialog').showModal();};$('close-photo').onclick=()=>$('photo-dialog').close();
 function dispose(object){if(!object)return;object.traverse(o=>{if(o.geometry)o.geometry.dispose();if(o.material)for(const m of Array.isArray(o.material)?o.material:[o.material])m.dispose();});scene.remove(object);}
 async function load(r,version){
  try{
   const b64=await payload(r.sku[0]);if(version!==generation)return;const binary=Uint8Array.from(atob(b64),c=>c.charCodeAt(0));
   new THREE.GLTFLoader().parse(binary.buffer,'',gltf=>{
    if(version!==generation){gltf.scene.traverse(o=>{if(o.geometry)o.geometry.dispose();});return;}
    dispose(model);dispose(lines);dispose(outline);model=gltf.scene;meta=gltf.parser.json.asset.extras;model.updateMatrixWorld(true);
    const box=new THREE.Box3().setFromObject(model),size=box.getSize(new THREE.Vector3()).toArray(),expected=[r.outer.mm.width,r.outer.mm.length,r.outer.mm.height];
    const delta=Math.max(...expected.map((v,i)=>Math.abs(v-size[i])));if(delta>.01)throw Error('Rozměry modelu nesouhlasí s podkladem.');
    originalMaterials=new Map();const all=[];model.traverse(o=>{if(o.isMesh){o.castShadow=true;o.receiveShadow=true;all.push(o);originalMaterials.set(o,o.material);}});groups=[];
    const kinds=[...new Set(all.map(o=>o.userData.component))];
    const hb=new THREE.Box3();for(const m of all.filter(o=>/pant-vika-/.test(o.name)&&!o.name.includes('kotveni'))){m.geometry.computeBoundingBox();hb.union(m.geometry.boundingBox);}
    const lidPivot=hb.isEmpty()?new THREE.Vector3(box.min.x,0,box.max.z):hb.getCenter(new THREE.Vector3());
    const db=new THREE.Box3();for(const m of all.filter(o=>o.name.includes('dvere-horni-pant'))){m.geometry.computeBoundingBox();db.union(m.geometry.boundingBox);}
    const doorPivot=db.isEmpty()?new THREE.Vector3(box.max.x,0,box.max.z):db.getCenter(new THREE.Vector3());
    for(const kind of kinds){
     const meshes=all.filter(o=>o.userData.component===kind);if(!['lid','handle','door','lock','carry'].includes(kind)&&!kind.startsWith('drawer-')&&!kind.startsWith('tip-'))continue;
     const gb=new THREE.Box3();for(const m of meshes){m.geometry.computeBoundingBox();gb.union(m.geometry.boundingBox);}
     const cp=new THREE.Box3();for(const m of all.filter(o=>o.name.startsWith('drzadlo-cep-'))){m.geometry.computeBoundingBox();cp.union(m.geometry.boundingBox);}const pivot=kind==='carry'?cp.getCenter(new THREE.Vector3()):kind==='door'?doorPivot.clone():kind.startsWith('tip-')?new THREE.Vector3(gb.min.x+2,gb.getCenter(new THREE.Vector3()).y,gb.min.z+4):lidPivot.clone();
     const group=new THREE.Group();group.position.copy(pivot);model.add(group);for(const m of meshes){model.remove(m);group.add(m);m.position.sub(pivot);}
     groups.push({kind,group,pivot});
    }
    loaded={sku:r.sku[0],localSize:size,localMin:box.min.toArray(),localMax:box.max.toArray(),isProductGeometry:true,detailLevel:'realny_tvar',parts:all.length,delta,frontAxis:meta.front_axis,axisScale:meta.envelope_fit.axis_scale};
    $('verification').textContent='Všechny vrcholy změřeny; obálka '+r.outer.mm.length+' × '+r.outer.mm.width+' × '+r.outer.mm.height+' mm. Odchylka '+delta.toFixed(3).replace('.',',')+' mm od podkladu. Přesnost jednotlivých detailů není ověřená.';
    model.rotation.x=-Math.PI/2;model.position.y=r.outer.mm.height/2;model.updateMatrixWorld(true);scene.add(model);closedBox=new THREE.Box3().setFromObject(model);
    outline=new THREE.Box3Helper(closedBox,0x768b82);outline.visible=$('outline').checked;scene.add(outline);lines=new THREE.Group();scene.add(lines);buildDimensions(closedBox,r.outer.mm);
    $('open').disabled=!groups.some(g=>g.kind==='lid'||g.kind==='door'||g.kind.startsWith('drawer-')||g.kind.startsWith('tip-'));
    $('hide-lid').disabled=!groups.some(g=>g.kind==='lid'||g.kind==='door'||g.kind.startsWith('drawer-'));setView('iso');
   },e=>showError(e));
  }catch(e){showError(e);}
 }
 function colorParts(enabled){
  let i=0;$('parts-legend').replaceChildren();for(const [mesh,material] of originalMaterials){
   if(mesh.material!==material)mesh.material.dispose();
   if(enabled){const li=node('li',mesh.name);li.style.borderLeft='8px solid #'+new THREE.Color().setHSL((i*.61803398875)%1,.72,.48).getHexString();li.style.paddingLeft='8px';$('parts-legend').append(li);}
   mesh.material=enabled?new THREE.MeshBasicMaterial({color:new THREE.Color().setHSL((i*.61803398875)%1,.72,.48),side:THREE.DoubleSide}):material;i++;
  }
  if(captureMode)renderer.render(scene,camera);
 }
 function captureView(next){
  setView(next);const b=new THREE.Box3().setFromObject(model),c=b.getCenter(new THREE.Vector3());
  const ortho=new THREE.OrthographicCamera(-1,1,1,-1,.1,camera.far);ortho.position.copy(camera.position);ortho.up.copy(camera.up);ortho.lookAt(c);ortho.updateMatrixWorld(true);
  const projected=new THREE.Box3();for(const x of [b.min.x,b.max.x])for(const y of [b.min.y,b.max.y])for(const z of [b.min.z,b.max.z])projected.expandByPoint(new THREE.Vector3(x,y,z).applyMatrix4(ortho.matrixWorldInverse));
  const size=projected.getSize(new THREE.Vector3()),aspect=$('viewer').clientWidth/$('viewer').clientHeight,half=Math.max(size.y/2,size.x/(2*aspect))*1.10;
  ortho.left=-half*aspect;ortho.right=half*aspect;ortho.top=half;ortho.bottom=-half;ortho.updateProjectionMatrix();renderer.render(scene,ortho);
 }
 function showError(e){error=e.message||String(e);$('viewer-error').hidden=false;$('viewer-error').textContent=error;}
 function openModel(){
  if(!model)return;const open=$('open').checked,hide=$('hide-lid').checked,d=current.outer.mm;
  for(const {kind,group,pivot} of groups){
   group.position.copy(pivot);group.rotation.set(0,0,0);group.visible=true;
   if(kind==='lid'||kind==='handle'){if(open){if(meta.hinge_axis==='x')group.rotation.x=1.30;else group.rotation.y=-1.30;}if(kind==='lid'||kind==='handle')group.visible=!hide;}
   if(kind==='door'){if(open)group.rotation.y=-1.35;group.visible=!hide;}
   if(kind.startsWith('drawer-')){if(open)group.position.x+=d.width*.56;group.visible=!hide;}
   if(kind.startsWith('tip-')&&open&&(!tipOpenSlots||tipOpenSlots.includes(Number(kind.slice(4)))))group.rotation.y=-.55;
   if(kind==='lock')group.visible=!open&&!hide;
  }
  for(const g of groups.filter(a=>a.kind==='carry'))g.group.rotation.y=$('carry-raised').checked?-Math.PI/2:0;model.updateMatrixWorld(true);setView(view);
 }
 function segment(a,b,color){lines.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints([a,b]),new THREE.LineBasicMaterial({color})));}
 function buildDimensions(b,d){
  $('labels').replaceChildren();labels=[];const o=Math.max(d.length,d.width,d.height)*.12,v=(x,y,z)=>new THREE.Vector3(x,y,z);
  const specs=[[v(b.min.x-o,b.min.y,b.min.z),v(b.min.x-o,b.min.y,b.max.z),'L · '+d.length+' mm',0x576a9f],[v(b.min.x,b.min.y,b.max.z+o),v(b.max.x,b.min.y,b.max.z+o),'Š · '+d.width+' mm',0x708482],[v(b.max.x+o,b.min.y,b.min.z),v(b.max.x+o,b.max.y,b.min.z),'V · '+d.height+' mm',0x956356]];
  for(const [a,c,t,color] of specs){segment(a,c,color);const e=node('div',t,'dim-label');$('labels').append(e);labels.push({element:e,position:a.clone().add(c).multiplyScalar(.5)});}lines.visible=$('dimensions').checked;
 }
 function setView(next){
  if(bottomLight)bottomLight.visible=next==='bottom';
  view=next;const d=current.outer.mm,box=model?new THREE.Box3().setFromObject(model):null,center=box?box.getCenter(new THREE.Vector3()):new THREE.Vector3(0,d.height/2,0),radius=box?box.getSize(new THREE.Vector3()).length()/2:Math.hypot(d.length,d.width,d.height)/2;
  const aspect=$('viewer').clientWidth/$('viewer').clientHeight,angle=Math.min(camera.fov*Math.PI/180,2*Math.atan(Math.tan(camera.fov*Math.PI/360)*aspect)),dist=radius/Math.sin(angle/2)*1.20;
  const compact=meta?.front_axis==='positive_y';
  const compareDir=current.sku[0]==='4932478161'?new THREE.Vector3(1,.6,-1.0):current.sku[0]==='4932498323'?new THREE.Vector3(1,.7,-1.2):compact?new THREE.Vector3(-1,.8,-1.3):new THREE.Vector3(1.4,.7,-.8);
  const dir={iso:new THREE.Vector3(1,.85,1.15),photo:compareDir,front:compact?new THREE.Vector3(0,0,-1):new THREE.Vector3(1,0,0),back:compact?new THREE.Vector3(0,0,1):new THREE.Vector3(-1,0,0),side:compact?new THREE.Vector3(1,0,0):new THREE.Vector3(0,0,1),sideOther:compact?new THREE.Vector3(-1,0,0):new THREE.Vector3(0,0,-1),top:new THREE.Vector3(0,1,.001),bottom:new THREE.Vector3(0,-1,.001),isoFrontRight:compact?new THREE.Vector3(1,.6,-1):new THREE.Vector3(1,.6,1),isoFrontLeft:compact?new THREE.Vector3(-1,.6,-1):new THREE.Vector3(1,.6,-1),isoBackRight:compact?new THREE.Vector3(1,.6,1):new THREE.Vector3(-1,.6,1),isoBackLeft:compact?new THREE.Vector3(-1,.6,1):new THREE.Vector3(-1,.6,-1)}[next];
  camera.position.copy(center).add(dir.normalize().multiplyScalar(dist));camera.up.set(0,1,0);camera.near=.1;camera.far=dist*12;camera.updateProjectionMatrix();controls.target.copy(center);controls.minDistance=radius*.35;controls.maxDistance=dist*5;controls.update();if(captureMode)renderer.render(scene,camera);document.querySelectorAll('[data-view]').forEach(b=>b.classList.toggle('active',b.dataset.view===next));
 }
 try{
  scene=new THREE.Scene();scene.background=new THREE.Color(0xedf1f4);camera=new THREE.PerspectiveCamera(38,1,.1,100000);renderer=new THREE.WebGLRenderer({antialias:true});renderer.setPixelRatio(Math.min(devicePixelRatio,2));renderer.outputEncoding=THREE.sRGBEncoding;
  $('viewer').prepend(renderer.domElement);controls=new THREE.OrbitControls(camera,renderer.domElement);controls.enableDamping=true;scene.add(new THREE.HemisphereLight(0xffffff,0x7a818c,1.15));const light=new THREE.DirectionalLight(0xffffff,1.2);light.position.set(500,900,700);scene.add(light);const fill=new THREE.DirectionalLight(0xdce6ff,.7);fill.position.set(-500,300,-600);scene.add(fill);
  bottomLight=new THREE.DirectionalLight(0xffffff,1.6);bottomLight.position.set(800,-500,400);bottomLight.visible=false;scene.add(bottomLight);
  renderer.shadowMap.enabled=true;renderer.shadowMap.type=THREE.PCFSoftShadowMap;light.castShadow=true;light.shadow.mapSize.set(1024,1024);Object.assign(light.shadow.camera,{left:-1000,right:1000,top:1000,bottom:-1000,near:1,far:3000});light.shadow.bias=-.00015;
  const floor=new THREE.Mesh(new THREE.PlaneGeometry(4000,4000),new THREE.ShadowMaterial({opacity:.12}));floor.rotation.x=-Math.PI/2;floor.position.y=-.4;floor.receiveShadow=true;scene.add(floor);
  function resize(){const w=$('viewer').clientWidth,h=$('viewer').clientHeight;renderer.setSize(w,h);camera.aspect=w/h;camera.updateProjectionMatrix();if(model)setView(view);}
  new ResizeObserver(resize).observe($('viewer'));resize();
  function frame(){requestAnimationFrame(frame);if(captureMode)return;controls.update();renderer.render(scene,camera);for(const l of labels){const p=l.position.clone().project(camera);l.element.hidden=!$('dimensions').checked||p.z>1||p.z< -1;l.element.style.left=(p.x+1)*$('viewer').clientWidth/2+'px';l.element.style.top=(1-p.y)*$('viewer').clientHeight/2+'px';}}frame();
  document.querySelectorAll('[data-view]').forEach(b=>b.onclick=()=>{$('bottom').checked=false;setView(b.dataset.view);});$('reset').onclick=()=>{$('bottom').checked=false;setView('iso');};$('dimensions').onchange=()=>{if(lines)lines.visible=$('dimensions').checked;for(const l of labels)l.element.hidden=!$('dimensions').checked;};$('outline').onchange=()=>{if(outline)outline.visible=$('outline').checked;};$('parts-colors').onchange=()=>colorParts($('parts-colors').checked);$('open').onchange=openModel;$('carry-raised').onchange=openModel;$('hide-lid').onchange=openModel;$('bottom').onchange=()=>setView($('bottom').checked?'bottom':'iso');$('photo-view').onchange=()=>setView($('photo-view').checked?'photo':'iso');
 }catch(e){showError(e);}
 window.KUFRIKY_MODELY_UI={setTipSlots:slots=>{tipOpenSlots=slots;openModel();},setCarry:value=>{$('carry-raised').checked=value;openModel();},setOpen:value=>{$('open').checked=value;openModel();},poseCamera:(dir,up=[0,1,0],ortho=true)=>{captureMode=true;model.updateMatrixWorld(true);const box=new THREE.Box3().setFromObject(model),c=box.getCenter(new THREE.Vector3()),v=new THREE.Vector3(...dir).normalize();camera.position.copy(c).add(v.multiplyScalar(box.getSize(new THREE.Vector3()).length()*2));camera.up.set(...up);camera.lookAt(c);camera.updateMatrixWorld(true);if(bottomLight)bottomLight.visible=dir[1]<0;const cam=ortho?new THREE.OrthographicCamera(-1,1,1,-1,.1,100000):camera;cam.position.copy(camera.position);cam.up.copy(camera.up);cam.lookAt(c);cam.updateMatrixWorld(true);if(ortho){const projected=new THREE.Box3();model.traverse(m=>{if(!m.isMesh||!m.visible||!m.parent.visible)return;const a=m.geometry.getAttribute('position');for(let i=0;i<a.count;i++)projected.expandByPoint(new THREE.Vector3().fromBufferAttribute(a,i).applyMatrix4(m.matrixWorld).applyMatrix4(cam.matrixWorldInverse));});const size=projected.getSize(new THREE.Vector3()),aspect=$('viewer').clientWidth/$('viewer').clientHeight,half=Math.max(size.y/2,size.x/(2*aspect))*1.07,center=projected.getCenter(new THREE.Vector3());cam.left=center.x-half*aspect;cam.right=center.x+half*aspect;cam.top=center.y+half;cam.bottom=center.y-half;cam.updateProjectionMatrix();}renderer.render(scene,cam);},captureView,colorParts,meshNames:()=>[...originalMaterials.keys()].map(m=>m.name),select:sku=>select(records.find(r=>r.sku.includes(sku))),renderClean:()=>{captureMode=true;renderer.shadowMap.enabled=false;lines.visible=false;outline.visible=false;document.querySelector('#labels').hidden=true;document.querySelector('.watermark').hidden=true;setView('photo');},state:()=>({loaded,current:current.sku[0],error,view,camera:camera?camera.position.toArray():null,opened:$('open').checked,groups:groups.map(g=>({kind:g.kind,visible:g.group.visible,position:g.group.position.toArray(),rotation:g.group.rotation.toArray(),bounds:new THREE.Box3().setFromObject(g.group).getSize(new THREE.Vector3()).toArray(),max:new THREE.Box3().setFromObject(g.group).max.toArray()}))}),setView};
 select(records.find(r=>r.sku.includes(location.hash.slice(1)))||records[0]);
})();
