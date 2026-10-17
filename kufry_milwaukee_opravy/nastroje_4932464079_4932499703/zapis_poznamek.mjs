// Generuje zdroje/<SKU>_poznamky.md (tabulky IoU se čtou z kufriky_cloud/srovnani_opravy/<SKU>/kola.jsonl a john_iou.json). node zapis_poznamek.mjs
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const HERE = path.dirname(fileURLToPath(import.meta.url)), ROOT = path.join(HERE, '../..');
const SR = s => path.join(ROOT, 'kufriky_cloud/srovnani_opravy', s);
const rd = f => fs.existsSync(f) ? JSON.parse(fs.readFileSync(f, 'utf8')) : null;
const kola = s => (fs.existsSync(path.join(SR(s), 'kola.jsonl')) ? fs.readFileSync(path.join(SR(s), 'kola.jsonl'), 'utf8').trim().split('\n').map(l => JSON.parse(l)) : []);
const f4 = v => (v == null ? '–' : (+v).toFixed(3).replace('.', ','));
const kontrola = s => rd(path.join(ROOT, 'kufriky_cloud/kontrola_john_v6', s, 'kontrola.json'));

function tabulkaStaraNova(s, fotky) {
  const K = kola(s), L = K[K.length - 1], J = rd(path.join(SR(s), 'john_iou.json')) || {}, KJ = kontrola(s);
  if (!L) return '(kolo zatím nespuštěno)\n';
  let t = '| foto | staré IoU (Johnův v6, hodnota z kontroly) | staré IoU přeměřené naším postupem, kamera z kontroly | staré IoU, kamera dofitovaná k jeho obrysu | **nové IoU, kamera z kontroly** (u otevřeného víka dofitován jen úhel víka) | nové IoU, kamera dofitovaná k našemu modelu (+ úhel víka) | IoU červených prvků: staré → nové (kamera kontroly) |\n|---|---|---|---|---|---|---|\n';
  for (const p of fotky) {
    const n = L.fotky[p]; if (!n) continue;
    const kj = KJ?.fotky?.find(x => x.id === p)?.iou_siluety;
    const j = J[p];
    const cs = (j?.cervena_kontrola && n.cervena_kontrola) ? `${f4(j.cervena_kontrola.iou_cervena)} → ${f4(n.cervena_kontrola.iou_cervena)}` : '–';
    t += `| ${p} | ${f4(kj)} | ${j ? f4(j.iou_kamera_kontroly) : 'nelze přepočítat (viz níže)'} | ${j ? f4(j.iou_dofit) : '–'} | **${f4(n.iou_kamera_kontroly)}** | ${f4(n.iou_kamera_dofitovana)} | ${cs} |\n`;
  }
  return t;
}
function historie(s, fotky) {
  const K = kola(s); if (!K.length) return '';
  let t = '| kolo | co se měnilo | ' + fotky.map(p => `${p} (kontrola / dofit)`).join(' | ') + ' |\n|---|---|' + fotky.map(() => '---').join('|') + '|\n';
  for (const k of K) t += `| ${k.kolo} | ${k.popis} | ` + fotky.map(p => k.fotky[p] ? `${f4(k.fotky[p].iou_kamera_kontroly)} / ${f4(k.fotky[p].iou_kamera_dofitovana)}` : '–').join(' | ') + ' |\n';
  return t;
}
export { tabulkaStaraNova, historie, f4, kola, rd, SR, ROOT };
