// Vyrobí samostatný HTML soubor (bez sítě): three.js + OrbitControls + GLB vloženo jako base64.
// node nastroje/zabal_prohlizec.mjs modely/<SKU>.glb vystup.html
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const ROOT = path.join(path.dirname(fileURLToPath(import.meta.url)), '..');
const [glb, out] = process.argv.slice(2);
let t = fs.readFileSync(path.join(ROOT, 'prohlizec/prohlizec.html'), 'utf8');
const js = f => fs.readFileSync(path.join(ROOT, 'vendor', f), 'utf8').replace(/<\/script/gi, '<\\/script');
t = t.replace('<!--THREE_SCRIPTS-->', `<script>${js('three.min.js')}</script><script>${js('OrbitControls.js')}</script>`);
t = t.replace('__GLB_B64__', fs.readFileSync(glb).toString('base64'));
if (process.argv.includes('--artifact')) {
  t = t.replace(/<!doctype html>\s*/i, '').replace(/<html[^>]*>\s*/i, '').replace(/<head>\s*/i, '').replace(/<meta charset[^>]*>\s*/i, '').replace(/<meta name="viewport"[^>]*>\s*/i, '').replace(/<\/head>\s*/i, '').replace(/<body>\s*/i, '').replace(/<\/body>\s*<\/html>\s*$/i, '');
  t = t.replace(/<title>[^<]*<\/title>/, '<title>PACKOUT organizér 3D</title>');
}
fs.writeFileSync(out, t); console.log(out, (t.length / 1e6).toFixed(2) + ' MB');
