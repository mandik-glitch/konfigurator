// Vygeneruje 3D text loga do OBJ. Blender ho pak dodela (spojeni vrcholu,
// zesileni reliefu, SRAZENI HORNICH HRAN, export GLB) - viz dokonci_logo.py.
//
//   node gen_logo_text.js 'LOGiMAN.CZ' /tmp/logo.obj
//   /opt/blender-5.2/blender -b -P dokonci_logo.py -- /tmp/logo.obj logo.glb
//
// Parametry (font, vyska, hloubka) jsou portem z build_logo.html - musi
// zustat stejne, aby logo sedlo na stejna mista jako drivejsi verze.
//
// === PROC JE BEVEL VYPNUTY (bot9 2026-09-11) =============================
// Drive tu bylo bevelEnabled:true, bevelThickness 0,15, bevelSize 0,12,
// bevelSegments 2. Melo to hranam dodat lesk, ale ve skutecnosti to
// ZNEMOZNOVALO srazeni, ktere Robert chtel:
//
//   * Hrana prisla z three.js uz jako lomeny OBLOUK (81/65/48/37 stupnu),
//     0,3 mm hluboky - a Robert vyslovne rekl "nechci oblouk ale primku".
//   * Blenderu tim vznikly mikro-hrany a jeho clamp_overlap pak neporovnaval
//     zadany 1 mm se sirkou tahu pisma, ale s nimi. Z 1 mm zbylo 0,013 mm,
//     tedy nic. Tri kola oprav tvrdila, ze je srazeni hotove; zmerena plocha
//     horniho lice se pritom od spodniho nelisila ani o promile.
//
// Vypnutim bevelu vznikne cisty ostry text (12600 -> 4128 vrcholu) a
// srazeni uz muze udelat Blender poradne a MERITELNE.
//
// DUSLEDEK NA ROZMER: bevel nafukoval bounding box, takze korekce vysky
// pismo o 0,85 % zmensovala. Bez nej je logo pri stejne vysce 28 mm
// DELSI - 223,764 mm misto 222,204 mm. Pismo je tim verne fontu.
// POZOR: delka loga je zadratovana i jinde (scripts/razitkovac.py
// LOGO_DELKA_MM, PLAN_TVORBY_SESTAV.md) - pri zmene ji tam srovnat.
const fs = require('fs');
const THREE = require('/opt/konfigurator/node_modules/three');

const TEXT = process.argv[2] || 'LOGiMAN.CZ';
const CIL = process.argv[3] || '/tmp/logo.obj';
const HEIGHT_MM = 28;     // Robert 2026-09-08: "velikost vyska loga 28mm"
const DEPTH_MM = 1.2;     // hloubka extruze; Blender ji pak zesili na 3 mm

const fontJson = JSON.parse(fs.readFileSync(
  '/opt/konfigurator/scripts/2026-09-08_logo_3d/fonts/helvetiker_bold.typeface.json', 'utf8'));
const font = new THREE.FontLoader().parse(fontJson);

const geo = new THREE.TextGeometry(TEXT, {
  font,
  size: HEIGHT_MM,
  height: DEPTH_MM,
  curveSegments: 6,
  bevelEnabled: false,    // viz hlavicka - srazeni dela az Blender, primkou
});
geo.computeBoundingBox();
let bb = geo.boundingBox;
geo.translate(-(bb.max.x + bb.min.x) / 2, -(bb.max.y + bb.min.y) / 2, -(bb.max.z + bb.min.z) / 2);

// KOREKCE VYSKY: parametr `size` neodpovida presne vyslednemu bounding-boxu
// (font metriky pridavaji navic), proto se skaluje podle ZMERENE vysky.
//
// POZOR u malych pismen: vysku urcuji VELKA pismena (L, O, G, M, ...), male
// `i` je nizsi a na celkovou vysku nema vliv.
bb = geo.boundingBox;
const korekce = HEIGHT_MM / (bb.max.y - bb.min.y);
geo.scale(korekce, korekce, korekce);
geo.computeBoundingBox();
bb = geo.boundingBox;

const pos = geo.attributes.position;
const idx = geo.index;
console.log('TEXT      : %s', TEXT);
console.log('vrcholu   : %d, trojuhelniku: %d', pos.count, (idx ? idx.count : pos.count) / 3);
console.log('rozmer mm : %s x %s x %s',
  (bb.max.x - bb.min.x).toFixed(3), (bb.max.y - bb.min.y).toFixed(3), (bb.max.z - bb.min.z).toFixed(3));

const radky = ['# 3D logo ' + TEXT + ' - vygenerovano z helvetiker_bold, bez bevelu'];
for (let i = 0; i < pos.count; i++) {
  radky.push('v ' + pos.getX(i).toFixed(6) + ' ' + pos.getY(i).toFixed(6) + ' ' + pos.getZ(i).toFixed(6));
}
if (idx) {
  for (let i = 0; i < idx.count; i += 3) {
    radky.push('f ' + (idx.getX(i) + 1) + ' ' + (idx.getX(i + 1) + 1) + ' ' + (idx.getX(i + 2) + 1));
  }
} else {
  for (let i = 0; i < pos.count; i += 3) {
    radky.push('f ' + (i + 1) + ' ' + (i + 2) + ' ' + (i + 3));
  }
}
fs.writeFileSync(CIL, radky.join('\n') + '\n');
console.log('ULOZENO   : %s', CIL);
