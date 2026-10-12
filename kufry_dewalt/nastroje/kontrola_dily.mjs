// Kontrola modelu: (1) nic neplave – každý díl se dotýká/prolíná bboxem aspoň s jedním jiným dílem (tolerance 0,6 mm), (2) žádný díl nevyčnívá z obálky ±1 mm,
// (3) počty dílů/trojúhelníků. Použití: node kontrola_dily.mjs ../modely/DWST83346.glb 333 440 302
import { readGLB } from '../../kufriky_cloud/jadro/glb.js';
const [f, ox, oy, oz] = process.argv.slice(2); const g = readGLB(f), ob = [+ox, +oy, +oz];
const bb = g.parts.map(p => { const b = [1e9, 1e9, 1e9, -1e9, -1e9, -1e9]; for (let i = 0; i < p.pos.length; i += 3) for (let k = 0; k < 3; k++) { b[k] = Math.min(b[k], p.pos[i + k]); b[k + 3] = Math.max(b[k + 3], p.pos[i + k]); } return b; });
let bad = 0, tri = 0; const T = 0.6;
g.parts.forEach((p, i) => {
  tri += p.idx.length / 3;
  const b = bb[i]; let hit = false;
  for (let j = 0; j < bb.length && !hit; j++) { if (j === i) continue; const c = bb[j]; hit = [0, 1, 2].every(k => b[k] <= c[k + 3] + T && c[k] <= b[k + 3] + T); }
  if (!hit) { bad++; console.log('PLOVOUCÍ díl:', p.name); }
  for (let k = 0; k < 3; k++) if (b[k] < -ob[k] / 2 - 1 || b[k + 3] > ob[k] / 2 + 1) { bad++; console.log('MIMO OBÁLKU:', p.name, b.map(v => v.toFixed(1)).join(',')); break; }
});
console.log(`${g.parts.length} dílů, ${tri} trojúhelníků, problémů: ${bad}`);
process.exit(bad ? 1 : 0);
