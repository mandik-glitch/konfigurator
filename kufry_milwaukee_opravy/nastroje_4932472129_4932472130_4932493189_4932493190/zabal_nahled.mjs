// Samostatný HTML náhled boxu se zásuvkami (three.js + GLB v base64). Používá sdílený prohlížeč kufriky_cloud/prohlizec/prohlizec.html BEZ jeho úpravy:
// výstup zabal_prohlizec.mjs se jen v hotovém HTML upraví tak, aby posuvníky rozlišovaly typy pohyblivých uzlů z extras:
//   typ 'posuv'  → výsuv zásuvky v mm po ose extras.osa (0 … rozsah_mm; navázané kolejnice se pohybují poloviční rychlostí),
//   typ 'rotace' → sklopení třmenu ve stupních (rozsah_deg),
//   typ 'prislusenstvi' → zobrazit/skrýt přepážky.
// node zabal_nahled.mjs <SKU>  → ../nahled/<SKU>.html
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { execFileSync } from 'node:child_process';
const HERE = path.dirname(fileURLToPath(import.meta.url)), ROOT = path.join(HERE, '..'), KC = path.join(ROOT, '../kufriky_cloud');
for (const sku of process.argv.slice(2)) {
  fs.mkdirSync(path.join(ROOT, 'nahled'), { recursive: true });
  const out = path.join(ROOT, 'nahled', sku + '.html');
  execFileSync('node', [path.join(KC, 'nastroje/zabal_prohlizec.mjs'), path.join(ROOT, 'modely', sku + '.glb'), out], { stdio: 'inherit' });
  let t = fs.readFileSync(out, 'utf8');
  const a = t.indexOf('  // posuvníky pro pohyblivé skupiny'), b = t.indexOf('  // řez: jedna ořezová rovina');
  if (a < 0 || b < 0) throw new Error('struktura prohlížeče se změnila – úprava posuvníků nelze provést');
  const nove = `  // posuvníky pro pohyblivé uzly (úprava pro boxy se zásuvkami): extras.typ = posuv | rotace | prislusenstvi
  const ovl=document.getElementById('ovl'); const uz=[];root.traverse(o=>{if(o.userData&&o.userData.typ)uz.push(o);});
  const p0=new Map();for(const o of uz)p0.set(o,o.position.clone());
  const radek=(txt,min,max,jed,fn)=>{const row=document.createElement('div');row.className='row';row.innerHTML='<label>'+txt+'</label><input type=range min='+min+' max='+max+' value=0 step=1><span>0 '+jed+'</span>';const inp=row.querySelector('input'),sp=row.querySelector('span');inp.oninput=()=>{sp.textContent=inp.value+' '+jed;fn(+inp.value);};ovl.appendChild(row);return inp;};
  const posun=(o,mm)=>{const ax=new THREE.Vector3(...o.userData.osa).normalize();o.position.copy(p0.get(o)).addScaledVector(ax,mm);for(const q of uz)if(q.userData.vazba===o.name){const ax2=new THREE.Vector3(...q.userData.osa).normalize();q.position.copy(p0.get(q)).addScaledVector(ax2,mm*(q.userData.podil||1));}};
  const zas=uz.filter(o=>o.userData.typ==='posuv'&&!o.userData.vazba);
  if(zas.length>1){const mx=zas[0].userData.rozsah_mm[1];const vse=radek('všechny zásuvky – výsuv',0,mx,'mm',v=>{for(const o of zas)posun(o,v);for(const r of rows)r.value=v;});}
  const rows=[];for(const o of zas){const inp=radek(o.name.replace('zasuvka-','zásuvka ')+' – výsuv',0,o.userData.rozsah_mm[1],'mm',v=>posun(o,v));rows.push(inp);}
  for(const o of uz.filter(o=>o.userData.typ==='rotace')){const [lo,hi]=o.userData.rozsah_deg;radek('třmen – sklopení',lo,hi,'°',v=>{const ax=new THREE.Vector3(...o.userData.osa).normalize();o.quaternion.setFromAxisAngle(ax,v*Math.PI/180);});}
  const prisl=uz.filter(o=>o.userData.typ==='prislusenstvi');
  if(prisl.length){const r2=document.createElement('div');r2.className='row';r2.innerHTML='<label>přepážky – zobrazit</label><input type=checkbox checked>';r2.querySelector('input').onchange=e=>{for(const o of prisl)o.visible=e.target.checked;};ovl.appendChild(r2);}
`;
  t = t.slice(0, a) + nove + t.slice(b);
  // v hlavičce: čelo zásuvek míří do +X, popis souřadnic
  fs.writeFileSync(out, t); console.log(out, 'upraven (posuvníky zásuvek a třmenu)');
}
