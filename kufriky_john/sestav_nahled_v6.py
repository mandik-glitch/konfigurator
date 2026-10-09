"""Offline packing of v6 preview; foreign images are NEVER copied."""
from pathlib import Path
import json,base64,csv,shutil
from over_realne_tvary import inspect
ROOT=Path(__file__).resolve().parent
SITE=ROOT/'nahled-modely-v6'
cat=json.loads((ROOT/'kufriky.json').read_text())
records=[next(r for r in cat['records'] if r['id']==i) for i in cat['model_order']]
for r in records:
 for v in r['model_variants']:
  b=(SITE/'modely'/(v['sku']+'.glb')).read_bytes()
  (SITE/'modely'/(v['sku']+'.js')).write_text('window.KUFRIKY_MODEL_PAYLOADS['+json.dumps(v['sku'])+']='+json.dumps(base64.b64encode(b).decode())+';\n')
cad=json.loads((ROOT/'zdroje/cad_tvar_v2.json').read_text())['candidates']
(SITE/'data.js').write_text('window.KUFRIKY_MODEL_PAYLOADS={};\nwindow.KUFRIKY_MODELY='+json.dumps(dict(summary=cat['model_summary'],records=records,cad_sources=cad,convention=cat['model_convention']),ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')+';\n')
(SITE/'kufriky.json').write_text(json.dumps(cat,ensure_ascii=False,indent=2)+'\n')
with (SITE/'kufriky.csv').open('w',newline='',encoding='utf-8-sig') as f:
 w=csv.writer(f,delimiter=';');w.writerow(['SKU','název','L_mm','Š_mm','V_mm','model','opraveno_v6','neověřeno'])
 for r in records:w.writerow([','.join(r['sku']),r['name'],*[r['outer']['mm'][k] for k in ['length','width','height']],r['model_file'],r['review']['changed'],' | '.join(r['review']['unverified'])])
shutil.copyfile(SITE/'kufriky.csv',ROOT/'kufriky.csv')
with (SITE/'soucasti.csv').open('w',newline='',encoding='utf-8-sig') as f:
 w=csv.writer(f,delimiter=';');w.writerow(['SKU','součást','min X','min Y','min Z','max X','max Y','max Z','druh','poznámka'])
 for r in records:
  for v in r['model_variants']:
   _,parts,_=inspect(SITE/'modely'/(v['sku']+'.glb'))
   for p in parts:
    w.writerow([v['sku'],p['name'],*p['vertices'].min(0).tolist(),*p['vertices'].max(0).tolist(),p['role'],'Digitální měření modelu; fyzická přesnost detailů neověřená.'])
pairs=json.loads((ROOT/'zdroje/doladeni-v6/srovnani.json').read_text())
public_pairs={sku:[{k:v for k,v in p.items() if k!='source_file'} for p in rows] for sku,rows in pairs.items()}
(SITE/'srovnani-data.js').write_text('window.KUFRIKY_COMPARISONS='+json.dumps(public_pairs,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')+';\n')
s=(ROOT/'nahled-modely-v5/index.html').read_text().replace('v5','v6').replace('Model v4','Model v5').replace('Původní model v4','Původní model v5').replace('7. 10. 2026','8. 10. 2026')
s=s.replace('V4 · opravené podstavné plošky podle skutečného dna','V6 · pět organizérů přepracovaných podle vlastních fotografií SKU')
s=s.replace('<section class="review">','<section class="review"><p><a class="compare-link" id="comparison-page" href="srovnani.html">Fotografie ↔ model: šest úhlů a otevřený stav ↗</a></p><div id="photo-model-pairs"></div>')
s=s.replace('<label><input id="open" type="checkbox"> Otevřít / vysunout</label>', '<label><input id="open" type="checkbox"> Otevřít / vysunout</label><label><input id="carry-raised" type="checkbox"> Zvednout držadlo výklopného typu</label>')
s=s.replace('REÁLNÝ TVAR','REKONSTRUKCE v6').replace('<strong>Znovu zkontrolováno všech 20 typů.</strong>','<strong>Přepracováno všech pět organizérů.</strong>')
s=s.replace('Doladěné tvary v6','Porovnání se skutečností · v6')
(SITE/'index.html').write_text(s)
s=(ROOT/'nahled-modely-v5/app.js').read_text().replace("' · v5'","' · v6'")
s=s.replace("current=r;loaded=null;", "current=r;loaded=null;renderPhotoPairs(r);")
s=s.replace("!['lid','handle','door','lock'].includes(kind)","!['lid','handle','door','lock','carry'].includes(kind)")
s=s.replace("const pivot=kind==='door'", "const cp=new THREE.Box3();for(const m of all.filter(o=>o.name.startsWith('drzadlo-cep-'))){m.geometry.computeBoundingBox();cp.union(m.geometry.boundingBox);}const pivot=kind==='carry'?cp.getCenter(new THREE.Vector3()):kind==='door'")
s=s.replace("model.updateMatrixWorld(true);setView(view);","for(const g of groups.filter(a=>a.kind==='carry'))g.group.rotation.y=$('carry-raised').checked?-Math.PI/2:0;model.updateMatrixWorld(true);setView(view);")
s=s.replace("$('open').onchange=openModel;","$('open').onchange=openModel;$('carry-raised').onchange=openModel;")
s=s.replace("$('open').checked=false;","$('open').checked=false;$('carry-raised').checked=false;$('carry-raised').disabled=r.sku[0]!=='4932498323';")
s=s.replace('let meta=null,captureMode=false;', 'let tipOpenSlots=null;let meta=null,captureMode=false;')
s=s.replace("if(kind.startsWith('tip-')&&open)group.rotation.y=.38;","if(kind.startsWith('tip-')&&open&&(!tipOpenSlots||tipOpenSlots.includes(Number(kind.slice(4)))))group.rotation.y=-.55;")
s=s.replace("$('open').checked=false;", "tipOpenSlots=null;$('open').checked=false;")
# On the tip organizer the open bin must swing around its OWN hinge; a rim
# bounding box is not the hinge axis. Default is stacked/transport position.
s=s.replace("new THREE.Vector3(gb.max.x,gb.getCenter(new THREE.Vector3()).y,gb.min.z)","new THREE.Vector3(gb.min.x+2,gb.getCenter(new THREE.Vector3()).y,gb.min.z+4)")
s=s.replace("if(kind.startsWith('tip-')&&open)group.rotation.y=.38;","if(kind.startsWith('tip-')&&open)group.rotation.y=-.55;")
s=s.replace("rotation:g.group.rotation.toArray()","rotation:g.group.rotation.toArray(),bounds:new THREE.Box3().setFromObject(g.group).getSize(new THREE.Vector3()).toArray(),max:new THREE.Box3().setFromObject(g.group).max.toArray()")
s=s.replace("window.KUFRIKY_MODELY_UI={", "window.KUFRIKY_MODELY_UI={setTipSlots:slots=>{tipOpenSlots=slots;openModel();},setCarry:value=>{$('carry-raised').checked=value;openModel();},setOpen:value=>{$('open').checked=value;openModel();},poseCamera:(dir,up=[0,1,0],ortho=true)=>{captureMode=true;model.updateMatrixWorld(true);const box=new THREE.Box3().setFromObject(model),c=box.getCenter(new THREE.Vector3()),v=new THREE.Vector3(...dir).normalize();camera.position.copy(c).add(v.multiplyScalar(box.getSize(new THREE.Vector3()).length()*2));camera.up.set(...up);camera.lookAt(c);camera.updateMatrixWorld(true);if(bottomLight)bottomLight.visible=dir[1]<0;const cam=ortho?new THREE.OrthographicCamera(-1,1,1,-1,.1,100000):camera;cam.position.copy(camera.position);cam.up.copy(camera.up);cam.lookAt(c);cam.updateMatrixWorld(true);if(ortho){const projected=new THREE.Box3();model.traverse(m=>{if(!m.isMesh||!m.visible||!m.parent.visible)return;const a=m.geometry.getAttribute('position');for(let i=0;i<a.count;i++)projected.expandByPoint(new THREE.Vector3().fromBufferAttribute(a,i).applyMatrix4(m.matrixWorld).applyMatrix4(cam.matrixWorldInverse));});const size=projected.getSize(new THREE.Vector3()),aspect=$('viewer').clientWidth/$('viewer').clientHeight,half=Math.max(size.y/2,size.x/(2*aspect))*1.07,center=projected.getCenter(new THREE.Vector3());cam.left=center.x-half*aspect;cam.right=center.x+half*aspect;cam.top=center.y+half;cam.bottom=center.y-half;cam.updateProjectionMatrix();}renderer.render(scene,cam);},")
s=s.replace("const data=window.KUFRIKY_MODELY,", "const comparisons=window.KUFRIKY_COMPARISONS||{};function renderPhotoPairs(r){const area=document.getElementById('photo-model-pairs');if(!area)return;area.replaceChildren();document.getElementById('comparison-page').href='srovnani.html#'+r.sku[0];for(const pair of comparisons[r.sku[0]]||[]){const div=document.createElement('div');div.className='photo-model-pair';const f=document.createElement('figure'),title=document.createElement('figcaption');title.textContent=pair.label;f.append(title);if(pair.photo_url){const a=document.createElement('a');a.className='photo-external';a.href=pair.photo_url;a.target='_blank';a.rel='noopener noreferrer';a.textContent='Otevřít původní fotografii ↗';f.append(a);}else{const text=document.createElement('p');text.textContent='Fotografie tohoto pohledu pro toto SKU chybí – neověřeno.';f.append(text);}const note=document.createElement('p');note.textContent=pair.alignment;f.append(note);const g=document.createElement('figure'),im=document.createElement('img');im.src=pair.render_file;im.alt=r.name+' · '+pair.label+' · model v6';im.loading='lazy';const a=document.createElement('a');a.href=pair.render_file;a.target='_blank';a.append(im);g.append(a);const caption=document.createElement('figcaption');caption.textContent='Náš model v6 · '+pair.label;g.append(caption);div.append(f,g);area.append(div);}}const data=window.KUFRIKY_MODELY,")
(SITE/'app.js').write_text(s)
index=(SITE/'index.html').read_text().replace('<script defer src="app.js">','<script defer src="srovnani-data.js"></script><script defer src="app.js">')
(SITE/'index.html').write_text(index)
style=(ROOT/'nahled-modely-v5/style.css').read_text()+'''
.photo-model-pair{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin:22px 0;border:1px solid #ced4db;border-radius:12px;padding:14px;background:white}.photo-model-pair figure{margin:0;min-width:0}.photo-model-pair img{width:100%;background:white;border-radius:8px}.photo-external{display:flex;align-items:center;justify-content:center;min-height:170px;text-align:center;border:2px solid #8f222e;border-radius:8px;background:#fff5f5;font-size:20px;font-weight:bold;text-decoration:none;padding:20px}.compare-link{display:block;padding:14px;background:#8f222e;color:white;border-radius:8px;text-decoration:none;font-weight:bold}.comparison-gallery{max-width:1180px;margin:auto;padding:22px}.comparison-gallery h2{margin-top:45px}.comparison-gallery img{width:100%}.comparison-gallery p{line-height:1.5}.comparison-nav{display:flex;gap:10px;flex-wrap:wrap}.comparison-nav a{padding:10px;border:1px solid #ced4db;border-radius:8px} @media(max-width:650px){.photo-model-pair{grid-template-columns:1fr}.photo-external{min-height:90px}}
'''
(SITE/'style.css').write_text(style)
print('V6 sestavena; rendery a údaje srovnání se doplní samostatně.')
