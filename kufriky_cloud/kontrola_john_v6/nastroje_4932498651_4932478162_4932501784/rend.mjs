// Vlastní skript kontroly (scratchpad): render GLB z uložené kamery + IoU proti masce fotografie. Použití:
// node rend.mjs --glb X.glb --foto f.jpg --cam cam.json --png out.png [--iou-json out.json] [--hide a,b] [--pair pair.png] [--L 600]
import fs from 'node:fs'; import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { Renderer, kamera } from './rendlib.mjs';
const opt=(k,d)=>{const i=process.argv.indexOf('--'+k);return i>0?process.argv[i+1]:d;};
const glb=opt('glb'),foto=opt('foto'),camF=opt('cam'),png=opt('png'),L=+opt('L',600),hide=opt('hide','').split(',').filter(Boolean);
const SC='/tmp/claude-0/-home-user-konfigurator/4afe04ea-52af-557e-a8a4-75a8d542e4f9/scratchpad/w';
const mf=path.join(SC,'mask_'+path.basename(path.dirname(foto))+'_'+path.basename(foto)+'.bin');
execFileSync('python3',['-I','/home/user/konfigurator/kufriky_cloud/nastroje/foto_maska.py',foto,mf,String(L)],{stdio:'ignore'});
const mb=fs.readFileSync(mf);const w=mb.readUInt32LE(0),h=mb.readUInt32LE(4),mask=mb.slice(8);
const c=JSON.parse(fs.readFileSync(camF));
const camObj=kamera({azim:c.azim,elev:c.elev,dist:c.dist,fov:c.fov,roll:c.roll||0,shiftX:c.shiftX!==undefined?c.shiftX:(c.cx-c.w/2)/c.w,shiftY:c.shiftY!==undefined?c.shiftY:(c.cy-c.h/2)/c.h});
const R=await new Renderer().open(w,h);await R.load(glb,true);if(hide.length)await R.hide(hide);if(opt('shift',null))await R.shift(['zasuvka-0-'],+opt('shift'));
const m=await R.mask(camObj);let I=0,U=0,A=0,B=0;for(let i=0;i<m.length;i++){const a=m[i],b=mask[i];if(a&b)I++;if(a|b)U++;A+=a;B+=b;}
await R.close();
const W=+opt('W',1200),H=Math.round(W*(c.h||1200)/(c.w||1200));
const R2=await new Renderer().open(W,H);await R2.load(glb,false);if(hide.length)await R2.hide(hide);if(opt('shift',null))await R2.shift(['zasuvka-0-'],+opt('shift'));await R2.png(camObj,png);await R2.close();
const yc=Math.round(+opt('ycut',0)*h/c.h);let I2=0,U2=0;for(let y=yc;y<h;y++)for(let x=0;x<w;x++){const i=y*w+x,a=m[i],b=mask[i];if(a&b)I2++;if(a|b)U2++;}
const res={iou:+(I/U).toFixed(4),iou_pod_radkem:+(I2/U2).toFixed(4),ycut_px:+opt('ycut',0),maskL:L,model_px:A,foto_px:B};
if(opt('iou-json',null))fs.writeFileSync(opt('iou-json'),JSON.stringify(res));
console.log(JSON.stringify(res));
