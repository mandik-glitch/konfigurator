// Height-planner (shape_geometry_methods.id=3 vyklad_seznamu_povolenych_vysek
// + box_muze_presahovat_zadni_profil) - genericky, per column: floorY (rail0
// top = floorY+T), TOP_Y (920 pro H=1180/CAP_H=260, jinak H-CAP_H), physCeil
// (fresh kolizne odvozeny fyzicky strop pro TENHLE sloupec). Vraci pole
// {boxH, railYCenter, boxTop} bottom->top, nerostouci vysky, RAIL_CENTER_MAX
// (TOP_Y-T/2) vzdy dodrzeno pro VSECHNY patra (i posledni) - jen BOX smi
// presahnout az do physCeil na poslednim patre.
const HEIGHTS_DESC = [270, 220, 170, 120];
const GAP = 30;

function planColumn(floorY, TOP_Y, physCeil, T = 30, heightsDesc = HEIGHTS_DESC) {
  const RAIL_CENTER_MAX = TOP_Y - T / 2;
  const levels = [];
  let railTop = floorY + T;
  let prevH = Infinity;
  // Pass 1: konzervativni naplneni (limit=TOP_Y na kazdem patre, aby se
  // nezpotrebovala kapacita nespravne - "posledni" se pozna az kdyz nic
  // dalsiho nejde pridat).
  while (true) {
    const railYCenter = railTop - T / 2;
    if (railYCenter > RAIL_CENTER_MAX + 1e-6) break;
    let chosen = null;
    for (const h of heightsDesc) {
      if (h > prevH + 1e-6) continue; // nerostouci
      const boxTop = railTop + h;
      if (boxTop <= TOP_Y + 1e-6) { chosen = h; break; }
    }
    if (chosen === null) break;
    levels.push({ boxH: chosen, railYCenter, boxTop: railTop + chosen });
    prevH = chosen;
    railTop = railTop + chosen + GAP + T;
  }
  // Pass 2: posledni patro smi vyuzit physCeil (box presahuje profil, rail
  // sam zustava v RAIL_CENTER_MAX, jiz zarucen vyse).
  if (levels.length > 0) {
    const last = levels[levels.length - 1];
    const railTopLast = last.railYCenter + T / 2;
    const capBelow = levels.length >= 2 ? levels[levels.length - 2].boxH : Infinity;
    let bestH = last.boxH;
    for (const h of heightsDesc) {
      if (h > capBelow + 1e-6) continue;
      if (h < last.boxH - 1e-6) continue; // jen zvetsit/zachovat, ne zmensit
      const boxTop = railTopLast + h;
      if (boxTop <= physCeil + 1e-6) { bestH = h; break; }
    }
    last.boxH = bestH;
    last.boxTop = railTopLast + bestH;
  } else {
    // ani jedno konzervativni patro nevyslo - zkus JEDNO patro rovnou s physCeil limitem
    const railYCenter = floorY + T / 2;
    if (railYCenter <= RAIL_CENTER_MAX + 1e-6) {
      for (const h of heightsDesc) {
        const boxTop = floorY + T + h;
        if (boxTop <= physCeil + 1e-6) { levels.push({ boxH: h, railYCenter, boxTop }); break; }
      }
    }
  }
  return levels;
}

// Diversity pass: zkusi napric VSEMI sloupci sestavy zvysit pocet distinct
// vysek na >=3 (z dostupnych 4), beze zmeny poctu pater a bez poruseni
// nerostouci posloupnosti/limitu - prohodi jedno patro za jinou povolenou
// vysku, pokud to jeste porad projde stejnymi limity (railYCenter constant,
// jen boxTop se prepocita a musi zustat <= puvodni limit tohoto patra).
function diversify(columnsLevels, limits, heightsDesc = HEIGHTS_DESC) {
  // columnsLevels: pole poli levels (bottom->top). limits: pole {TOP_Y, physCeil} per column (paralelni index).
  const distinctUsed = () => new Set(columnsLevels.flatMap(lv => lv.map(l => l.boxH)));
  let guard = 0;
  while (distinctUsed().size < 3 && guard < 50) {
    guard++;
    let changed = false;
    const beforeCount = distinctUsed().size;
    outer:
    for (let ci = 0; ci < columnsLevels.length; ci++) {
      const levels = columnsLevels[ci];
      const { TOP_Y, physCeil } = limits[ci];
      for (let li = 0; li < levels.length; li++) {
        const cur = levels[li];
        const isTop = li === levels.length - 1;
        const limit = isTop ? physCeil : TOP_Y;
        const upperNeighbor = li + 1 < levels.length ? levels[li + 1].boxH : 0;
        const lowerNeighbor = li - 1 >= 0 ? levels[li - 1].boxH : Infinity;
        for (const h of heightsDesc) {
          if (h === cur.boxH) continue;
          if (h > lowerNeighbor + 1e-6) continue;
          if (h < upperNeighbor - 1e-6) continue;
          const railTop = cur.boxTop - cur.boxH;
          const newBoxTop = railTop + h;
          if (newBoxTop > limit + 1e-6) continue;
          const used = distinctUsed();
          if (used.has(h)) continue; // uz pouzita, nepomuze
          // over, ze zmena SKUTECNE zvysi POCET distinct hodnot v CELE
          // sestave (ne jen "je jina") - jinak by mohla zbytecne
          // zmensovat box bez pokroku v rozmanitosti (napr. jen 2 patra
          // celkem, kde 3. distinct hodnota fyzicky nikdy nepribude).
          const oldH = cur.boxH;
          cur.boxH = h; cur.boxTop = newBoxTop;
          const afterCount = distinctUsed().size;
          if (afterCount > beforeCount) { changed = true; break outer; }
          cur.boxH = oldH; cur.boxTop = railTop + oldH; // revert, nepomohlo
        }
      }
    }
    if (!changed) break;
  }
  return columnsLevels;
}

// `planColumn()` NEROZHODUJE za nas, kterou konkretni skladbu vysek
// pouzit - je to greedy "na kazde patro nejvyssi vyska z nabidky, co se
// tam vejde" (bot8 2026-09-11, overeno SPUSTENIM: planColumn(...,[270,170])
// vratilo [270,270], 170 se vubec nepouzilo, protoze uz 270 se vesla na
// obe patra - funkce nema duvod sahnout niz). `diversify()` umi jen
// prohodit JEDNO patro kvuli pravidlu "aspon 2-3 ruzne vysky", ne trefit
// presny predepsany soucet/poradi. Kdyz uz existujici B/C/D/E varianta
// (konkretni zakaznicky viditelna skladba, napr. "270x3-220x2-170x3-120x2")
// potrebuje rekonstrukci (napr. po oprave karoserie, viz devitka sestav
// se zanorenim 2026-09-11), tenhle par funkci na to nestaci - pouzij
// planColumnExact() nize.
//
// planColumnExact: OVERUJE, ze predepsana posloupnost vysek (bottom->top,
// PRESNE tahle, zadny vyber) fyzicky sedi do stejnych limitu jako
// planColumn (RAIL_CENTER_MAX pro rail kazdeho patra, TOP_Y pro box vsech
// pater krome posledniho, physCeil jen pro posledni patro) - stejna
// matematika, jen bez rozhodovani. Kdyz nesedi, VYHAZUJE chybu s presnym
// duvodem (ktere patro, o kolik) - volajici NESMI kombinaci prizpusobovat,
// jen nahlasit, ze puvodni skladba uz fyzicky nejde (viz zadani bot3
// 2026-09-11: "Kdyz se ukaze, ze se nektera kombinace fyzicky nevejde,
// nepřizpůsobuj ji. Rekni mi to.").
function planColumnExact(floorY, TOP_Y, physCeil, T, heightsInOrder) {
  const RAIL_CENTER_MAX = TOP_Y - T / 2;
  const levels = [];
  let railTop = floorY + T;
  let prevH = Infinity;
  for (let i = 0; i < heightsInOrder.length; i++) {
    const h = heightsInOrder[i];
    if (h > prevH + 1e-6) {
      throw new Error(`patro ${i}: vyska ${h} je vetsi nez predchozi patro ${prevH} - `
        + `posloupnost musi byt neresouci bottom->top`);
    }
    const railYCenter = railTop - T / 2;
    if (railYCenter > RAIL_CENTER_MAX + 1e-6) {
      throw new Error(`patro ${i} (boxH=${h}): stred kolejnicky ${railYCenter.toFixed(2)}mm `
        + `presahuje RAIL_CENTER_MAX ${RAIL_CENTER_MAX.toFixed(2)}mm - nevejde se`);
    }
    const isLast = i === heightsInOrder.length - 1;
    const limit = isLast ? physCeil : TOP_Y;
    const boxTop = railTop + h;
    if (boxTop > limit + 1e-6) {
      throw new Error(`patro ${i} (boxH=${h}): vrch boxu ${boxTop.toFixed(2)}mm presahuje `
        + `${isLast ? "physCeil" : "TOP_Y"} ${limit.toFixed(2)}mm o ${(boxTop - limit).toFixed(2)}mm - nevejde se`);
    }
    levels.push({ boxH: h, railYCenter, boxTop });
    prevH = h;
    railTop = railTop + h + GAP + T;
  }
  return levels;
}

module.exports = { planColumn, diversify, planColumnExact, HEIGHTS_DESC, GAP };
