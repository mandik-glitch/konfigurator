// Sdilena knihovna pro rendery Vandr FBX modelu (viz VANDR_RENDER_HOWTO.md).
// Kazda funkce tady odpovida jednomu skutecne chycenemu a opravenemu
// bugu behem 2026-09-06/07 - nekopirovat inline do novych skriptu,
// importovat odtud.
import * as THREE from 'three';

export const PALETTE = [0x9fb6cc, 0xd98c8c, 0xc9c9c9, 0x8fbf8f, 0xd9c17a, 0xb08cd9];

// ZAVAZNA barevna konvence (VANDR_RENDER_HOWTO.md hlavni ⭐ pravidlo):
// barva podle poradi SUB-MESHU uvnitr jednoho modelu, NIKDY podle
// identity dilu. Volej bez druheho argumentu.
export function colorize(obj) {
  let i = 0;
  obj.traverse(n => { if (n.isMesh) { n.material = new THREE.MeshStandardMaterial({ color: PALETTE[i % PALETTE.length], metalness: 0.2, roughness: 0.6 }); i++; } });
}

// "Hlavni cast" (strukturalni hlinik) - meshe primo pod uzlem "alu".
// VYLUCUJE sroubovy uchyt ("sroub"), zaslepky ("black") a plastovy
// panel ("plast_gr"), ktere mohou vycnivat mimo skutecnou 459/414mm
// hloubku. Pouzij pro kontrolu hloubky nohy (VANDR_RENDER_HOWTO.md 3c).
export function structuralZRange(obj) {
  let min = Infinity, max = -Infinity;
  obj.traverse(n => {
    if (n.isMesh && n.parent && n.parent.name === 'alu') {
      const box = new THREE.Box3().setFromObject(n);
      min = Math.min(min, box.min.z); max = Math.max(max, box.max.z);
    }
  });
  return { min, max };
}

// Koncovy nosnik komponenty (ten, co dosedne na nohu) = "alu" cast s
// NEJMENSIM X. NIKDY nestredit/zarovnavat podle celeho bboxu dilu -
// dvirka/supliky mivaji mimostredovy pant/kliku/kolecko, ktere
// posunou CELKOVY bbox o nekolik mm i kdyz nosnik sam presne sedi
// (VANDR_RENDER_HOWTO.md 3f).
export function endBracketOf(obj) {
  let best = null;
  obj.traverse(n => {
    if (n.isMesh && n.parent && n.parent.name === 'alu') {
      const b = new THREE.Box3().setFromObject(n);
      if (!best || b.min.x < best.min.x) best = b;
    }
  });
  return best;
}

// Cervene plosky (parent.name === 'red') = SKUTECNE dorazy zapsane
// primo v modelu, ne jen vizualni napoveda (VANDR_DILY_ZNACENI.md).
// Nezavisi na colorize() - ta meni jen n.material, ne hierarchii
// rodicu, takze se da volat kdykoli. Pri stohovani komponenty NA
// JINOU KOMPONENTU (ne na nohu) zarovnej spodni doraz horniho dilu
// PRESNE na horni doraz dolniho (mezera=0, zadna rezerva).
export function redStopsYRange(obj) {
  let min = Infinity, max = -Infinity;
  obj.traverse(n => {
    if (n.isMesh && n.parent && n.parent.name === 'red') {
      const b = new THREE.Box3().setFromObject(n);
      min = Math.min(min, b.min.y); max = Math.max(max, b.max.y);
    }
  });
  return { min, max };
}

// Najde exponovanou "podlahu" nohy s vyrezem: vrchol/spodek zkraceneho
// zadniho sloupku tam, kde po vyrezu zase zacina (VANDR_SKLADANI_
// REGALU.md "dosednuti plati i svisle"). Vraci Y v aktualnim
// (transformovanem) souradnem systemu objektu.
export function exposedFloorYOf(legObj) {
  const alu = [];
  legObj.traverse(n => { if (n.isMesh && n.parent && n.parent.name === 'alu') alu.push({ name: n.name, box: new THREE.Box3().setFromObject(n) }); });
  const rearPost = alu.filter(p => p.name.includes('_noha') && !p.name.includes('Zx1') && p.box.min.z < 0)
    .reduce((a, b) => (a.box.max.y > b.box.max.y ? a : b));
  return rearPost.box.min.y;
}

// Horni hranice hlavni zony = vrchol zadniho sloupku NORMALNI nohy
// (bez vyrezu). Vyrez meni jen spodni hranici zony, ne tuhle.
export function mainZoneTopOf(legObj) {
  const alu = [];
  legObj.traverse(n => { if (n.isMesh && n.parent && n.parent.name === 'alu') alu.push({ name: n.name, box: new THREE.Box3().setFromObject(n) }); });
  const rearPost = alu.filter(p => p.name.includes('_noha') && !p.name.includes('Zx1') && p.box.min.z < 0)
    .reduce((a, b) => (a.box.max.y > b.box.max.y ? a : b));
  return rearPost.box.max.y;
}

// Vnitrni (dotykova) stena predniho/zadniho sloupku nohy - NE cely
// structuralZRange() (ten zahrnuje i VNEJSI plochu obou sloupku, tedy
// celou 459mm obalku, ne 369mm "dotykovy" rozestup mezi nimi). Reálně
// chyceno 2026-09-07 (Ducato H2.1700.459 + Police.1D.1057.459): pri
// kontrole gapFront/gapRear proti structuralZRange() vyslo 45mm na obou
// stranach, presne o sirku jednoho profilu (45mm) - protoze noha je RAM
// (2 svisle sloupky *_noha + horizontalni vzpery *_Zx1/*_Zx2 MEZI nimi,
// viz VANDR_SKLADANI_REGALU.md "Zona pro hlavni komponenty"), takze
// spravna dotykova plocha pro koncovy nosnik komponenty je VNITRNI stena
// sloupku (kam sedi vzpera "Zx2"), ne jejich vnejsi obrys. Pouzij tuto
// funkci VZDY, kdyz kontrolujes flush-fit komponenty vuci noze v ose Z -
// structuralZRange() nech jen pro celkovou hloubku SAMOTNE nohy (napr.
// porovnani "459 vs 459" u dvou ruznych noh).
export function innerWallZRangeOf(legObj) {
  const posts = [];
  legObj.traverse(n => {
    if (n.isMesh && n.parent && n.parent.name === 'alu' && n.name.includes('_noha')) {
      posts.push(new THREE.Box3().setFromObject(n));
    }
  });
  const front = posts.filter(b => b.min.z >= 0).reduce((a, b) => (a.min.z < b.min.z ? a : b));
  const rear = posts.filter(b => b.max.z <= 0).reduce((a, b) => (a.max.z > b.max.z ? a : b));
  return { min: rear.max.z, max: front.min.z };
}

export function makeTextSprite(text, opts = {}) {
  const { fontsize = 44, color = '#1a1a1a', bg = 'rgba(255,255,255,0.85)' } = opts;
  const canvas = document.createElement('canvas');
  const ctx = canvas.getContext('2d');
  ctx.font = `bold ${fontsize}px Arial`;
  const w = ctx.measureText(text).width + 24;
  canvas.width = w; canvas.height = fontsize * 1.5;
  ctx.font = `bold ${fontsize}px Arial`;
  ctx.fillStyle = bg; ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.fillStyle = color; ctx.textBaseline = 'middle';
  ctx.fillText(text, 12, canvas.height / 2);
  const tex = new THREE.CanvasTexture(canvas);
  const mat = new THREE.SpriteMaterial({ map: tex, depthTest: false });
  const sprite = new THREE.Sprite(mat);
  sprite.scale.set(canvas.width * 0.6, canvas.height * 0.6, 1);
  sprite.renderOrder = 999;
  return sprite;
}

export function dimensionLine(p1, p2, label, offsetDir, offsetLen) {
  const group = new THREE.Group();
  const off = offsetDir.clone().normalize().multiplyScalar(offsetLen);
  const a = p1.clone().add(off), b = p2.clone().add(off);
  const mat = new THREE.LineBasicMaterial({ color: 0xb03030 });
  group.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints([p1, a]), mat));
  group.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints([p2, b]), mat));
  group.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints([a, b]), mat));
  const dir = b.clone().sub(a).normalize();
  const perp = new THREE.Vector3().crossVectors(dir, new THREE.Vector3(0, 1, 0)).normalize();
  if (perp.lengthSq() < 0.01) perp.set(0, 0, 1);
  const arrowLen = 30;
  [[a, dir], [b, dir.clone().negate()]].forEach(([pt, d]) => {
    const t1 = pt.clone().add(d.clone().multiplyScalar(arrowLen)).add(perp.clone().multiplyScalar(arrowLen * 0.4));
    const t2 = pt.clone().add(d.clone().multiplyScalar(arrowLen)).add(perp.clone().multiplyScalar(-arrowLen * 0.4));
    group.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints([pt, t1]), mat));
    group.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints([pt, t2]), mat));
  });
  const label3d = makeTextSprite(label, { color: '#b03030' });
  label3d.position.copy(a.clone().add(b).multiplyScalar(0.5));
  group.add(label3d);
  return group;
}

// Orto kamera s SPRAVNYM pomerem stran (VANDR_RENDER_HOWTO.md 3g) -
// pouzij MISTO rucniho "new THREE.OrthographicCamera(-halfW,halfW,...)",
// jinak hrozi zdeformovany ctvercovy profil na neètvercovem platne.
export function makeAspectCorrectOrtho(W, H, halfH) {
  const aspect = W / H;
  const halfW = halfH * aspect;
  return new THREE.OrthographicCamera(-halfW, halfW, halfH, -halfH, 1, 5000);
}
