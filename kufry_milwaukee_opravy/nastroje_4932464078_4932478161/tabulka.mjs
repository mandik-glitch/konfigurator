// Vypíše markdown tabulku IoU (stará verze × nová) z kufriky_cloud/srovnani_opravy/<SKU>/*.json: node tabulka.mjs <SKU>
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const HERE = path.dirname(fileURLToPath(import.meta.url)), ROOT = path.join(HERE, '../..');
const sku = process.argv[2], dir = path.join(ROOT, 'kufriky_cloud/srovnani_opravy', sku);
const f = v => v === undefined || v === null ? '–' : (+v).toFixed(3).replace('.', ',');
const rows = fs.readdirSync(dir).filter(n => /^c\d+\.json$/.test(n)).sort().map(n => JSON.parse(fs.readFileSync(path.join(dir, n))));
console.log('| foto | stav | dané kamery z kontroly: John / nový (bez vyplnění; s vyplněním jako v reportu) | dofit kamery: John / nový (bez vyplnění) | poznámka |\n|---|---|---|---|---|');
for (const r of rows) {
  const dana = r.iou_john_dana_kamera !== undefined ? `${f(r.iou_john_dana_kamera)} / ${f(r.iou_nova_dana_kamera)} (s vyplněním ${f(r.iou_john_dana_kamera_s_vyplnenim)} / ${f(r.iou_nova_dana_kamera_s_vyplnenim)})` : 'není';
  let dofit = `${r.iou_john_dofit_kamera !== undefined ? f(r.iou_john_dofit_kamera) : '–'} / ${f(r.iou_nova_dofit_kamera)}`;
  let nota = r.popis;
  if (r.iou_nova_dana_kamera_radky_od) { const q = r.iou_nova_dana_kamera_radky_od; nota += `; řádky y ≥ ${q.y} (s vyplněním): dané kamery John ${f(q.john_dana_s_vyplnenim)} / nový ${f(q.s_vyplnenim)}, dofit John ${f(q.john_dofit_s_vyplnenim)} / nový ${f(q.dofit_s_vyplnenim)}`; }
  if (r.iou_od_sloupce_x) { const q = r.iou_od_sloupce_x; nota += `; od x ≥ ${q.x}: dofit John ${f(q.john_dofit)} / nový ${f(q.nova_dofit)} (s vyplněním ${f(q.john_dofit_s_vyplnenim)} / ${f(q.nova_dofit_s_vyplnenim)})`; }
  if (r.mereno_od_radku_y) nota += ` (IoU jen od y ≥ ${r.mereno_od_radku_y})`;
  console.log(`| ${r.pohled} | ${Object.keys(r.pose || {}).length ? JSON.stringify(r.pose).replace(/"/g, '') : 'výchozí'} | ${dana} | ${dofit} | ${nota} |`);
}
