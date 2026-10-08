// Priprava finalniho payloadu pro plny navrat (Robert: "Vratit i vymeny
// boxu" - kompletni rollback dnesniho 25mm prepoctu na 8 sestavach).
// Diff overil (viz predchozi bash): headroom_v2.json[id].data.parts se od
// current_8.json[id].data.parts lisi VYHRADNE v (a) Y+17mm na hornim
// bloku a (b) ocekavanem product_3788->3793 swapu v cilovem sloupci -
// tedy je to presne a cistě "pred-recalc" stav, bezpecne pouzitelny k
// obnove. Mimo "parts" se nic jineho v data nemeni (bom/price_summary
// nebyly recalc skriptem nikdy touched, zustavaji jak byly).
const fs = require("fs");
const SCRATCH = "/tmp/claude-0/-opt-konfigurator/68994686-5a6b-46d4-b3c7-14bc1f68c6ac/scratchpad";
const H = JSON.parse(fs.readFileSync(`${SCRATCH}/headroom_v2.json`, "utf8"));
const C = JSON.parse(fs.readFileSync(`${SCRATCH}/current_8.json`, "utf8"));
const ids = [369, 370, 379, 380, 382, 383, 384, 385];

const NOTE = "bot8 2026-09-14: navrat na stav PRED 25mm-bezpecnostni-mezera prepoctem - Robert zmenil zadani (\"C uz neni vzor, vzorem jsou A/B pred upravou boxu\") a pri overeni vyslo, ze posun horniho bloku +17mm nebyl vedlejsi ucinek, ale nutna podminka pro to, aby vymena boxu 120->170mm splnovala 25mm pravidlo (bez posunu mezera klesla na 12-23mm). Robert zvolil kompletni rollback: vraceny i box (170->120mm), horni blok zpet bez posunu. parts obnoveny 1:1 ze snapshotu pred dnesnim prepoctem (headroom_v2.json), bom/price_summary nedotčeny (jiz predtim nebyly recalc skriptem menene).";

const out = {};
for (const id of ids) {
  const expectCount = C[id].data.parts.length;
  const revertParts = H[id].data.parts;
  if (revertParts.length !== expectCount) throw new Error(`id=${id}: pocet dilu v headroom_v2 (${revertParts.length}) != current (${expectCount})`);
  out[id] = { expectCount, revertParts, note: NOTE };
}
fs.writeFileSync(`${SCRATCH}/full_revert_payload.json`, JSON.stringify(out));
console.log("payload pripraven pro", Object.keys(out).length, "sestav");
for (const id of ids) console.log(" ", id, "->", out[id].revertParts.length, "dilu");
