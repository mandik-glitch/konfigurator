// Jako kufriky_cloud/nastroje/zabal_prohlizec.mjs, ale s vlastní šablonou prohlizec_posuv.html (posuvníky i pro posuvné uzly). node zabal_posuv.mjs modely/<SKU>.glb nahled/<SKU>.html
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const HERE = path.dirname(fileURLToPath(import.meta.url)), KC = path.join(HERE, '../../kufriky_cloud');
const [glb, out] = process.argv.slice(2);
let t = fs.readFileSync(path.join(HERE, 'prohlizec_posuv.html'), 'utf8');
const js = f => fs.readFileSync(path.join(KC, 'vendor', f), 'utf8').replace(/<\/script/gi, '<\\/script');
t = t.replace('<!--THREE_SCRIPTS-->', `<script>${js('three.min.js')}</script><script>${js('OrbitControls.js')}</script>`);
t = t.replace('__GLB_B64__', fs.readFileSync(glb).toString('base64'));
fs.writeFileSync(out, t); console.log(out, (t.length / 1e6).toFixed(2) + ' MB');
