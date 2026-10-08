// Navrh vertikalnich pater pro oba sloupce Vivara - respektuje:
// (a) rail joint-containment: railYCenter <= TOP_Y - T/2 = 905 pro KAZDOU uroven (nezmeneno)
// (b) NOVE pravidlo prekryvu (box_muze_presahovat_zadni_profil_2026_08_31):
//     box na NEJVYSSI urovni smi presahnout 920mm az do skutecneho fyzickeho
//     stropu (zjisteneho kolizi karoserie, step7), rail zustava pod 905/920.
// (c) nerostouci vysky odspoda nahoru v ramci sloupce
// (d) alespon 3 ruzne vysky z {120,170,220,270} NEKDE v cele sestave
const fs = require("fs");
const T = 30, TOP_Y = 920, RAIL_CENTER_MAX = 905;
const step5 = JSON.parse(fs.readFileSync("/opt/konfigurator/scripts/tmp_2026-08-31_vivaro_step5_result.json", "utf8"));
const step7 = JSON.parse(fs.readFileSync("/opt/konfigurator/scripts/tmp_2026-08-31_vivaro_step7_result.json", "utf8"));
const HEIGHTS = [270, 220, 170, 120]; // sestupne

function planColumn(floor, physCeil, seq) {
  // seq = pole vysek (nerostouci), zkusi je postupne umistit; posledni (top)
  // smi presahnout TOP_Y az do physCeil.
  let railTop = floor + T; // = floor + T (railYCenter = floor+T/2, railTop=railYCenter+T/2=floor+T)
  const levels = [];
  for (let i = 0; i < seq.length; i++) {
    const railYCenter = railTop - T / 2;
    if (railYCenter > RAIL_CENTER_MAX + 1e-6) return null; // rail sam nevaidni
    const isTop = i === seq.length - 1;
    const boxTop = railTop + seq[i];
    const limit = isTop ? physCeil : TOP_Y; // NEtop urovne: box nesmi presahnout 920 (pod ni jeste dalsi rail); TOP: smi az k fyzickemu stropu
    if (boxTop > limit + 1e-6) return null;
    levels.push({ railYCenter, railTop, boxH: seq[i], boxTop });
    railTop = railTop + seq[i] + 30 + T;
  }
  return levels;
}

for (const [colIdx, floorInfo] of Object.entries(step5)) {
  const floor = floorInfo.finalFloorY;
  const ceil = step7[colIdx].maxSafeBoxTop;
  console.log(`\n=== sloupec ${colIdx}: floor=${floor}, fyzicky strop=${ceil} ===`);
  // zkus par kandidatnich sekvenci (nerostouci, ruznorode)
  const candidates = [
    [270, 220, 170, 120],
    [270, 220, 170],
    [270, 220, 120],
    [220, 170, 120],
    [270, 170, 120],
    [270, 220],
    [220, 170],
    [270, 120],
    [120, 120, 120, 120],
    [220],
    [270],
  ];
  let best = null;
  for (const seq of candidates) {
    const levels = planColumn(floor, ceil, seq);
    if (levels) {
      const totalBoxH = levels.reduce((s, l) => s + l.boxH, 0);
      if (!best || levels.length > best.levels.length || (levels.length === best.levels.length && new Set(seq).size > new Set(best.seq).size)) {
        best = { seq, levels };
      }
      console.log(` seq=[${seq}] -> OK, ${levels.length} urovni, topBox top=${levels[levels.length-1].boxTop.toFixed(1)}`);
    } else {
      console.log(` seq=[${seq}] -> NEVEJDE SE`);
    }
  }
  console.log(" VYBRANO:", JSON.stringify(best));
}

console.log("\n\n=== EXHAUSTIVNI HLEDANI DEMO PRIPADU (topBox v (905,930]) ===");
function* nonIncreasingSeqs(maxLen, heights) {
  function* rec(prefix, remaining) {
    if (prefix.length > 0) yield prefix.slice();
    if (prefix.length >= maxLen) return;
    const lastH = prefix.length ? prefix[prefix.length - 1] : Infinity;
    for (const h of heights) {
      if (h <= lastH) yield* rec([...prefix, h], remaining);
    }
  }
  yield* rec([], maxLen);
}
for (const [colIdx, floorInfo] of Object.entries(step5)) {
  const floor = floorInfo.finalFloorY;
  const ceil = step7[colIdx].maxSafeBoxTop;
  for (const seq of nonIncreasingSeqs(5, HEIGHTS)) {
    const levels = planColumn(floor, ceil, seq);
    if (levels) {
      const top = levels[levels.length - 1].boxTop;
      if (top > 905 && top <= ceil) {
        console.log(`sloupec ${colIdx} seq=[${seq}] topBoxTop=${top.toFixed(1)} (presahuje 905, pod fyz.stropem ${ceil})`);
      }
    }
  }
}
