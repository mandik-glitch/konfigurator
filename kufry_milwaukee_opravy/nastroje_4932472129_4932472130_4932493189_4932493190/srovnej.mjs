// Vyrenderuje opravený model z kamer kontrolního reportu (kufriky_cloud/kontrola_john_v6/<SKU>/cNN_kamera.json nebo vlastní doladěné
// kufriky_cloud/srovnani_opravy/<SKU>/cNN.json) a uloží do scratchpadu: <out>/<SKU>_cNN_model.png (stínovaný) a _maska.png (obrys).
// Zásuvky z `ext` kamery (John: drawer-k, k od 0 shora) se mapují na uzly zasuvka-(k+1); sklopený třmen podle tabulky SKLOPENY.
// Použití: node srovnej.mjs --sku 4932493189 --pohled c02 --out <scratch> [--kam doladena] [--glb cesta] [--ext zasuvka-3=372,zasuvka-2=240] [--trmen -90]
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { Renderer, kamera } from '../../kufriky_cloud/render/render.mjs';
const HERE = path.dirname(fileURLToPath(import.meta.url)), REPO = path.join(HERE, '../..');
const opt = (k, d) => { const i = process.argv.indexOf('--' + k); return i > 0 ? process.argv[i + 1] : d; };
const sku = opt('sku'), pohledy = opt('pohled').split(','), out = opt('out');
const glb = opt('glb', path.join(HERE, '../modely', sku + '.glb'));
// fotky se sklopeným třmenem: c02/c03 (report R5) a všechny fotky s vysunutými zásuvkami (na nich třmen není vidět – překážel by zásuvkám)
const SKLOPENY = { '4932472129:c02': -90, '4932472130:c02': -90, '4932493189:c03': -90, '4932493189:c04': -90, '4932493189:c05': -90, '4932493190:c03': -90, '4932493190:c04': -90, '4932493190:c05': -90, '4932493190:c06': -90 };
fs.mkdirSync(out, { recursive: true });
const R = await new Renderer().open(1200, 1200);
async function pose2(p) {
  await R.page.evaluate(p => {
    const byName = {};
    root.traverse(o => { byName[o.name] = o; if (o.userData && o.userData.osa) { if (!o.userData._p0) o.userData._p0 = o.position.clone(); o.position.copy(o.userData._p0); o.quaternion.identity(); } });
    root.traverse(o => {
      const u = o.userData; if (!u || !u.osa) return;
      const ax = new THREE.Vector3(...u.osa).normalize();
      if (u.typ === 'posuv') { let v = p[o.name]; if (v === undefined && u.vazba && p[u.vazba] !== undefined) v = p[u.vazba] * (u.podil ?? 1); if (v !== undefined) o.position.addScaledVector(ax, v); }
      else if (u.typ === 'rotace') { const a = p[o.name]; if (a !== undefined) o.quaternion.setFromAxisAngle(ax, a * Math.PI / 180); }
    });
  }, p);
}
for (const pohled of pohledy) {
  const doladena = path.join(REPO, 'kufriky_cloud/srovnani_opravy', sku, pohled + '.json');
  const kj = opt('kam') === 'doladena' && fs.existsSync(doladena) ? JSON.parse(fs.readFileSync(doladena)) : JSON.parse(fs.readFileSync(path.join(REPO, 'kufriky_cloud/kontrola_john_v6', sku, pohled + '_kamera.json')));
  const kont = JSON.parse(fs.readFileSync(path.join(REPO, 'kufriky_cloud/kontrola_john_v6', sku, pohled + '_kamera.json')));
  const pose = {};
  for (const [k, v] of Object.entries(kont.ext || {})) pose['zasuvka-' + (+k.split('-')[1] + 1)] = v;
  if (opt('ext')) for (const kv of opt('ext').split(',')) { const [k, v] = kv.split('='); pose[k] = +v; }
  const tr = opt('trmen') !== undefined ? +opt('trmen') : SKLOPENY[sku + ':' + pohled];
  if (tr !== undefined) pose['trmen'] = tr;
  const c = kj.kamera, cam = kamera({ azim: c.azim, elev: c.elev, dist: c.dist, fov: c.fov, roll: c.roll || 0, shiftX: c.shiftX || 0, shiftY: c.shiftY || 0 });
  const bezPrepazek = (sku + ':' + pohled) === '4932493190:c05';          // na fotce c05 (3190) je vysunutá zásuvka bez přepážek
  await R.load(glb, true); if (bezPrepazek) await R.hide(['prepazk']); await pose2(pose); await R.png(cam, path.join(out, `${sku}_${pohled}_maska.png`));
  await R.load(glb, false); if (bezPrepazek) await R.hide(['prepazk']); await pose2(pose); await R.png(cam, path.join(out, `${sku}_${pohled}_model.png`));
  console.log(sku, pohled, JSON.stringify(pose));
}
await R.close();
