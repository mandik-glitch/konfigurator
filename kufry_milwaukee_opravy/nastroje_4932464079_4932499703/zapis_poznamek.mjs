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
  const CF = rd(path.join(HERE, `cfg_${s}.json`)) || {};
  for (const p of fotky) {
    const n = L.fotky[p]; if (!n) continue;
    if (CF[p]?.nazev) { t += `| ${p} (${CF[p].nazev}) | – (Johnův model v kontrole s touto fotografií neporovnán) | – | – | – (kamera z kontroly neexistuje) | ${f4(n.iou_kamera_dofitovana)} | – |\n`; continue; }
    const kj = KJ?.fotky?.find(x => x.id === p)?.iou_siluety;
    const j = J[p];
    const cs = (j?.cervena_kontrola && n.cervena_kontrola) ? `${f4(j.cervena_kontrola.iou_cervena)} → ${f4(n.cervena_kontrola.iou_cervena)}` : '–';
    t += `| ${p} | ${f4(kj)} | ${j ? f4(j.iou_kamera_kontroly) : 'nelze přepočítat (viz níže)'} | ${j ? f4(j.iou_dofit) : '–'} | **${f4(n.iou_kamera_kontroly)}** | ${f4(n.iou_kamera_dofitovana)} | ${cs} |\n`;
  }
  return t;
}
const NIC = 'beze změny geometrie modelu (opakované měření / jiná poloha kamery po dofitu)';
const POPIS = {
  '4932464079': { 1: 'výchozí kompletní stav: výřezy rohů (okna), tyče + krytky, víko 75 mm s 10 kapsami a žebry, červená rukojeť a západky jako uzly, logo, horní držadlo (uzel) + varianta zvednutého', 2: 'tyče zeštíhleny na 29×8 mm, širší třmeny, lem vany, potisk loga písmem, otevřená poloha třmenů na c02/c03', 3: 'dolní krytky 11 mm nad nejnižší hranou těla (patky těla níž – z c01), landmarky spodních rohů přepočteny, silnější ramena horního držadla', 4: 'poloha předního hardwaru vyladěna podle IoU červených prvků při fixní kameře (západky o ≈ 14 mm výš, ±172; rukojeť z\' 54–135; kroužek)', 5: 'osmihranné krytky (větší zkosení)', 6: 'horní držadlo: širší ramena a lokty (z c01_nahore)', 7: 'západky zvětšeny na 58 × 72 mm (Johnovy 31 × 38), širší třmeny a pouzdra', 8: NIC },
  '4932464080': { 1: 'výchozí kompletní stav (stejný generátor, V = 165)', 2: 'tyče 29×8 mm, širší třmeny, lem vany, otevřená poloha třmenů na c02', 3: 'dolní krytky 11 mm nad nejnižší hranou těla, landmarky přepočteny', 4: 'poloha předního hardwaru vyladěna podle IoU červených prvků (rukojeť z\' 2–78, západky ±172, kroužek)', 5: 'osmihranné krytky', 6: 'úhel visících třmenů na c02 upraven (pozice, ne geometrie)', 7: 'západky zvětšeny na 58 × 72 mm, širší třmeny a pouzdra', 8: NIC },
  '4932499703': { 1: 'výchozí stav: dva panely, 4 vysoké kapsy, panel ve víku s pásem úchytů, tub bez tyčí', 2: 'červené žebrované držadlo (bez loga), větší držadlo, lem těla, víko podle fotografie sady', 3: NIC, 4: NIC, 5: 'rozložení 10 kapes + drážky na víku změřeno z fotografie zavřeného boxu (c05); štítek v kapse', 6: 'poloha západek (±164), rukojeti a kroužku vyladěna podle červených prvků na fotografii sady (c02)', 7: 'západky zvětšeny na 58 × 66 mm, širší třmeny a pouzdra', 8: 'panely v těle a ve víku doladěny podle červených lemů na c01 (±6 mm)' },
};
POPIS['4932499704'] = POPIS['4932499703'];
function historie(s, fotky) {
  const K = kola(s); if (!K.length) return '';
  let t = '| kolo | co se měnilo | ' + fotky.map(p => `${p} (kontrola / dofit)`).join(' | ') + ' |\n|---|---|' + fotky.map(() => '---').join('|') + '|\n';
  for (const k of K) t += `| ${k.kolo} | ${(POPIS[s] && POPIS[s][k.kolo]) || k.popis} | ` + fotky.map(p => k.fotky[p] ? `${f4(k.fotky[p].iou_kamera_kontroly)} / ${f4(k.fotky[p].iou_kamera_dofitovana)}` : '–').join(' | ') + ' |\n';
  return t;
}
export { tabulkaStaraNova, historie, f4, kola, rd, SR, ROOT };
