import fs from 'node:fs'; import { execFileSync } from 'node:child_process';
import { Renderer, kamera } from './rendlib.mjs'; import { fitKamera } from './fitlib.mjs';
const G='/home/user/konfigurator/kufriky_john/nahled-modely-v6/modely/4932498651.glb';
const foto='../kufry3/4932498651/c02.jpg'; const mf='mask_r2fit.bin';
execFileSync('python3',['-I','/home/user/konfigurator/kufriky_cloud/nastroje/foto_maska.py',foto,mf,'300'],{stdio:'ignore'});
const mb=fs.readFileSync(mf);const w=mb.readUInt32LE(0),h=mb.readUInt32LE(4),mask=mb.slice(8);
const out={};
for (const s of [200,300,400]) {
  const R=await new Renderer().open(w,h); await R.load(G,true); await R.shift(['zasuvka-0-'],s);
  const cam=await fitKamera(R,mask,w,h,{fov:21,fitFov:false,startAz:30,startEl:25,dist0:2800}); await R.close();
  out[s]=cam; console.log(s,JSON.stringify(cam));
}
fs.writeFileSync('fit_r2.json',JSON.stringify(out,null,1));
