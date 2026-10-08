// Extract column/leg structure from existing variant-A product_assemblies.data
// for Vito MB47(83), Custom FO31(111), Transporter VW25(118), Vivaro OP31(136) -
// used to plan variant B/C height compositions without hardcoding per-vehicle
// leg constants (T=30 universal; H/CAP_H derived straight from data).
const fs = require("fs");

const IDS = { MB47: 83, FO31: 111, VW25: 118, OP31: 136 };
const T = 30;

function extract(id) {
  const data = JSON.parse(fs.readFileSync(`/tmp/claude-0/-opt-domeny/40752a20-c083-499a-8fe3-7c39a4eef60b/scratchpad/data/pa_${id}.json`, "utf8"));
  const parts = data.parts;
  const carBodyParts = parts.filter(p => p.part_id && p.part_id.startsWith("car_body_"));
  const legParts = parts.filter(p => p.role && !/sloupec\d+-patro\d+/.test(p.role) && !p.part_id.startsWith("car_body_"));
  // RAIL_TOP_MAX: top of any back-post segment (zadni-svislice-dolni OR zadni-svislice-nad-zarezem)
  const backPosts = parts.filter(p => p.role === "zadni-svislice-dolni" || p.role === "zadni-svislice-nad-zarezem");
  const tops = backPosts.map(p => p.position[1] + p.scale[1] * 500);
  const RAIL_TOP_MAX = Math.max(...tops);
  const RAIL_TOP_MAX_MIN = Math.min(...tops); // sanity: should equal max if globally constant

  // columns
  const colSet = new Set();
  parts.forEach(p => {
    const m = p.role && p.role.match(/^(?:nosnik|spojnice|eurobox)-sloupec(\d+)-patro(\d+)/);
    if (m) colSet.add(Number(m[1]));
  });
  const columns = [...colSet].sort((a, b) => a - b).map(colIdx => {
    const nosnik0 = parts.filter(p => p.role === `nosnik-sloupec${colIdx}-patro0`);
    const spojnice0 = parts.filter(p => p.role === `spojnice-sloupec${colIdx}-patro0`);
    const railXs = [...new Set(nosnik0.map(p => p.position[0]))];
    const railZCenter = nosnik0[0].position[2];
    const railLen = nosnik0[0].scale[1] * 1000;
    const connZs = spojnice0.map(p => p.position[2]).sort((a, b) => a - b);
    const N = connZs.length - 1;
    const floorY = nosnik0[0].position[1] - T / 2;
    // how many levels currently exist + their heights
    let levelIdx = 0, heights = [];
    while (true) {
      const boxes = parts.filter(p => p.role === `eurobox-sloupec${colIdx}-patro${levelIdx}` || (p.role && p.role.startsWith(`eurobox-sloupec${colIdx}-patro${levelIdx}-`)));
      if (boxes.length === 0) break;
      // derive height from part_id
      const pid = boxes[0].part_id;
      const H_BY_PID = { product_3788: 120, product_3793: 170, product_3794: 220, product_3795: 270 };
      heights.push(H_BY_PID[pid]);
      levelIdx++;
    }
    return { colIdx, N, railXs, railZCenter, railLen, connZs, floorY, currentHeights: heights };
  });
  return { id, RAIL_TOP_MAX, RAIL_TOP_MAX_MIN, columns, legPartsCount: legParts.length, carBodyParts };
}

for (const [key, id] of Object.entries(IDS)) {
  const info = extract(id);
  console.log(`\n=== ${key} (id=${id}) ===`);
  console.log(`RAIL_TOP_MAX=${info.RAIL_TOP_MAX} (min=${info.RAIL_TOP_MAX_MIN}) legParts=${info.legPartsCount}`);
  info.columns.forEach(c => {
    console.log(`  col${c.colIdx}: N=${c.N} floorY=${c.floorY} railXs=${JSON.stringify(c.railXs)} railZCenter=${c.railZCenter} railLen=${c.railLen} connZs=${JSON.stringify(c.connZs)} currentHeights=${JSON.stringify(c.currentHeights)}`);
    const budget = info.RAIL_TOP_MAX - (c.floorY + T);
    console.log(`    budget(RAIL_TOP_MAX - (floorY+T)) = ${budget}`);
  });
}
