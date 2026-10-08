const fs = require("fs");
const { transformAssembly } = require("./tmp_2026-09-12_bot8_wide_TRANSFORM_LIB.js");
const data = JSON.parse(fs.readFileSync("/tmp/claude-0/-opt-konfigurator/c0c788fb-0783-4d56-adb5-543ba6b0dda8/scratchpad/data/assembly134.json", "utf8"));
const { parts, report } = transformAssembly(data.parts, { deltaZ: 8, deltaY: 10 });
console.log(JSON.stringify(report, null, 1));

// porovnej s ACTUAL 340 hodnotami pro klicove role (leg-vazane, nezavisle na box compozici)
const d340 = JSON.parse(fs.readFileSync("/tmp/claude-0/-opt-konfigurator/c0c788fb-0783-4d56-adb5-543ba6b0dda8/scratchpad/data/assembly340.json", "utf8"));
function find(arr, role, zNear) { return arr.find(p => p.role === role && Math.abs(p.position[2] - zNear) < 3); }
const checks = [
  ["zadni-svislice-nad-zarezem @leg1(-898.5)", "zadni-svislice-nad-zarezem", -898.5],
  ["sloupek-pred-podbehem @leg1(-898.5)", "sloupek-pred-podbehem", -898.5],
  ["pricka-uzavreni-vyrezu @leg1(-898.5)", "pricka-uzavreni-vyrezu", -898.5],
  ["zadni-svislice-nad-zarezem @leg2(-34.5)", "zadni-svislice-nad-zarezem", -34.5],
  ["sloupek-pred-podbehem @leg2(-34.5)", "sloupek-pred-podbehem", -34.5],
  ["pricka-uzavreni-vyrezu @leg2(-34.5)", "pricka-uzavreni-vyrezu", -34.5],
];
for (const [label, role, z] of checks) {
  const mine = find(parts, role, z);
  const gt = find(d340.parts, role, z + 8); // pozor: po deltaZ se predni noha hne, ale leg1/leg2 (cutout) se v Z nehybou vubec
  const gtSame = find(d340.parts, role, z);
  console.log(label, "\n  MINE:", JSON.stringify(mine && {pos:mine.position, scale:mine.scale}), "\n  GT(340):", JSON.stringify(gtSame && {pos:gtSame.position, scale:gtSame.scale}));
}
console.log("\n--- front leg (leg0=-1358.5) predni-svislice ---");
console.log("MINE:", JSON.stringify(find(parts, "predni-svislice", -1358.5+8)));
console.log("GT340:", JSON.stringify(find(d340.parts, "predni-svislice", -1350.5)));

console.log("\n--- col0-p0 nosnik (rebalance check) ---");
const nosnikMine = parts.filter(p => p.role === "nosnik-col0-p0");
const nosnikGT = d340.parts.filter(p => p.role === "nosnik-col0-p0");
console.log("MINE:", JSON.stringify(nosnikMine.map(p=>({x:p.position[0],y:p.position[1],z:p.position[2],sy:p.scale[1]}))));
console.log("GT (340, note diff box comp so only y/scale-z pattern comparable, not full identity):", JSON.stringify(nosnikGT.map(p=>({x:p.position[0],y:p.position[1],z:p.position[2],sy:p.scale[1]}))));
