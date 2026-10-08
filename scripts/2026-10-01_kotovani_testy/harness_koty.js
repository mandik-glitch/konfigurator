// Harness kotovani 2D vykresu pro nabidku: SKUTECNA funkce drawDimensionOverlay (+ fillMaybeSplitLabel) se vytahne ze
// scene.html (nebo kandidata: SCENE_HTML=...) a spusti v Chromiu nad SYNTETICKOU sestavou (stul z profilu 35x35, orto kamera
// stejnym rezimem jako setViewMode). Ven jde PNG a mereni: kolik popisku vybiha z platna a kolik se jich prekryva.
// Bez sceny, bez DB, bez site. three.js 0.128 (stejna verze jako scena) z node_modules.
const { chromium } = require('/opt/konfigurator/node_modules/playwright-core');
const fs = require('fs');
const path = require('path');

const REPO = path.join(__dirname, '../..');
const SCENE_HTML = process.env.SCENE_HTML || path.join(REPO, 'webapp/scene.html');
const CATALOG_PANELS = process.env.CATALOG_PANELS_JS || path.join(REPO, 'webapp/js/scene/catalog-panels.js');
const THREE_JS = path.join(REPO, 'node_modules/three/build/three.min.js');

// vytahne zdroj funkce (od "function <jmeno>(" po jeji parovou "}") - pocitanim slozenych zavorek
function vytahniFunkci(src, jmeno) {
  const start = src.indexOf('function ' + jmeno + '(');
  if (start < 0) throw new Error('funkce nenalezena: ' + jmeno);
  let i = src.indexOf('{', src.indexOf(')', start)), depth = 0, inStr = null, inLine = false, inBlock = false;
  for (; i < src.length; i++) {
    const c = src[i], n = src[i + 1];
    if (inLine) { if (c === '\n') inLine = false; continue; }
    if (inBlock) { if (c === '*' && n === '/') { inBlock = false; i++; } continue; }
    if (inStr) { if (c === '\\') { i++; continue; } if (c === inStr) inStr = null; continue; }
    if (c === '/' && n === '/') { inLine = true; continue; }
    if (c === '/' && n === '*') { inBlock = true; continue; }
    if (c === '"' || c === "'" || c === '`') { inStr = c; continue; }
    if (c === '{') depth++;
    else if (c === '}') { depth--; if (depth === 0) return src.slice(start, i + 1); }
  }
  throw new Error('nenalezen konec funkce ' + jmeno);
}

function zdroje() {
  const scene = fs.readFileSync(SCENE_HTML, 'utf8');
  const panels = fs.readFileSync(CATALOG_PANELS, 'utf8');
  return {
    fill: vytahniFunkci(scene, 'fillMaybeSplitLabel'),
    draw: vytahniFunkci(scene, 'drawDimensionOverlay'),
    capture: vytahniFunkci(scene, 'captureOrthoWithDims'),
    setView: vytahniFunkci(panels, 'setViewMode'),
    defaultStyle: (/const DEFAULT_DIM_STYLE = (\{[^}]*\});/.exec(scene) || [])[1],
    offerKonst: (scene.match(/const OFFER_IMAGE_MIN_ASPECT[^;]*;/) || [''])[0],
    kotaKonst: (scene.match(/const OFFER_KOTA_ZOOM[^;]*;/) || [''])[0],
    layout: scene.includes('function offerKotaLayout(') ? vytahniFunkci(scene, 'offerKotaLayout') : null,
  };
}

// Syntetická sestava: stůl 1200 x 600 x 720 z profilů 35x35 + police (740 / 650 mm) - jako v ukázkovém nárysu nabídky
const SESTAVA = `
function profil(id, osa, delka, x, y, z) {
  const S = 35, g = new THREE.BoxGeometry(osa === 'x' ? delka : S, osa === 'y' ? delka : S, osa === 'z' ? delka : S);
  const m = new THREE.Mesh(g, new THREE.MeshBasicMaterial());
  const o = new THREE.Group(); o.add(m); o.position.set(x, y, z); o.updateMatrixWorld(true);
  const e = osa === 'x' ? new THREE.Vector3(1, 0, 0) : osa === 'y' ? new THREE.Vector3(0, 1, 0) : new THREE.Vector3(0, 0, 1);
  return { part: { id, length_mm: delka, cross_section_mm: [S, S], is_board_material: false }, object3d: o, osa, delka,
           connectorsLocal: [{ kind: 'end', point: e.clone().multiplyScalar(-delka / 2), normal: e.clone().multiplyScalar(-1) },
                             { kind: 'end', point: e.clone().multiplyScalar(delka / 2), normal: e.clone() }] };
}
window.sestavaRegal = function () {
  const P = [];
  const W = 1100, D = 600, H = 1790, S = 35;
  [[-W / 2, -D / 2], [W / 2, -D / 2], [-W / 2, D / 2], [W / 2, D / 2]].forEach(([x, z]) => P.push(profil(201, 'y', H, x, H / 2, z)));
  [100, 520, 900, 1280, 1700].forEach(y => { [-D / 2, D / 2].forEach(z => P.push(profil(202, 'x', W - S, 0, y, z))); });
  [100, 520, 1700].forEach(y => { [-W / 2, W / 2].forEach(x => P.push(profil(203, 'z', D - S, x, y, 0))); });
  P.push(profil(204, 'x', 740, -150, 720, -D / 2));   // kratke kusy v ruznych vyskach -> vic pruhu kot
  P.push(profil(205, 'x', 650, -120, 640, -D / 2));
  P.push(profil(206, 'y', 360, 330, 1500, -D / 2));
  return P;
};
window.sestavaStul = function () {
  const P = [];
  const W = 1200, D = 600, H = 720, S = 35;
  [[-W / 2, -D / 2], [W / 2, -D / 2], [-W / 2, D / 2], [W / 2, D / 2]].forEach(([x, z], i) => P.push(profil(101, 'y', H, x, H / 2, z)));
  [[H - S / 2, -D / 2], [H - S / 2, D / 2], [200, -D / 2], [200, D / 2]].forEach(([y, z]) => P.push(profil(102, 'x', W - S, 0, y, z)));
  [[H - S / 2, -W / 2], [H - S / 2, W / 2], [200, -W / 2], [200, W / 2]].forEach(([y, x]) => P.push(profil(103, 'z', D - S, x, y, 0)));
  // police a vystup (kratsi kusy v ruznych vyskach -> vic pruhu kot)
  P.push(profil(104, 'x', 740, -230, 420, -D / 2));
  P.push(profil(105, 'x', 650, -270, 340, -D / 2));
  P.push(profil(106, 'y', 300, 420, 560, -D / 2));
  P.push(profil(107, 'x', 560, 320, 700, D / 2));
  return P;
};
`;

async function otevri() {
  const browser = await chromium.launch({ args: ['--no-sandbox'] });
  const page = await browser.newPage({ viewport: { width: 1400, height: 1300 } });
  const chyby = [];
  page.on('pageerror', e => chyby.push(e.message));
  await page.setContent('<html><body style="margin:0;background:#fff"></body></html>');
  await page.addScriptTag({ path: THREE_JS });
  const z = zdroje();
  await page.addScriptTag({ content: SESTAVA });
  // rozhrani, ktere funkce ze sceny ocekavaji (isProfilePart, worldConnectorsOf, DEFAULT_DIM_STYLE) - zjednodusene, ale funkcne
  await page.addScriptTag({ content: `
    window.isProfilePart = part => !!(part && part.length_mm && !part.is_board_material);
    window.worldConnectorsOf = entry => entry.connectorsLocal.map(c => ({
      point: c.point.clone().applyMatrix4(entry.object3d.matrixWorld),
      normal: c.normal.clone().transformDirection(entry.object3d.matrixWorld) }));
    window.DEFAULT_DIM_STYLE = ${z.defaultStyle || '{ chainMerge: true, occlusion: "loose", totals: "segmentsOnly" }'};
    ${z.fill}
    ${z.draw}
    window.fillMaybeSplitLabel = fillMaybeSplitLabel; window.drawDimensionOverlay = drawDimensionOverlay;
    ${z.layout ? z.kotaKonst + '\n' + z.layout + '\nwindow.offerKotaLayout = offerKotaLayout;' : ''}
  ` });
  return { browser, page, chyby, z };
}

// Vykresli sestavu s kotami; cfg: { mode:'front', H (vyska platna), padding, kotaZoom }; vraci { png, mereni }
async function vykresli(page, cfg) {
  return page.evaluate(async cfg => {
    const placed = cfg.sestava === 'regal' ? window.sestavaRegal() : window.sestavaStul();
    window.placed = placed;
    const box = new THREE.Box3(); placed.forEach(e => box.expandByObject(e.object3d));
    const size = box.getSize(new THREE.Vector3()), center = box.getCenter(new THREE.Vector3());
    const modelW = cfg.mode === 'side' ? size.z : size.x, modelH = cfg.mode === 'top' ? size.z : size.y;
    const aspect = Math.min(2.5, Math.max(0.4, modelW / modelH));
    const H = cfg.H, W = Math.round(H * aspect);
    let padding = cfg.padding, kotaScaleRel = null, lay = null;
    if (cfg.layout && window.offerKotaLayout) { lay = window.offerKotaLayout(W / H); padding = lay.padding; kotaScaleRel = lay.rel; }
    const halfW = modelW / 2 * padding, halfH = modelH / 2 * padding;
    const h = Math.max(halfH, halfW / aspect);
    const cam = new THREE.OrthographicCamera(-h * aspect, h * aspect, h, -h, 1, 100000);
    if (cfg.mode === 'front') { cam.position.set(center.x, center.y, 2000); cam.up.set(0, 1, 0); cam.lookAt(center.x, center.y, 0); }
    else { cam.position.set(2000, center.y, center.z); cam.up.set(0, 1, 0); cam.lookAt(0, center.y, center.z); }
    cam.updateProjectionMatrix(); cam.updateMatrixWorld(true);
    window.camera = cam;
    const cv = document.createElement('canvas'); cv.width = W; cv.height = H; document.body.appendChild(cv);
    const ctx = cv.getContext('2d');
    ctx.fillStyle = '#fff'; ctx.fillRect(0, 0, W, H);
    // obrysy dilu (jako technicky vykres)
    ctx.strokeStyle = '#16324f'; ctx.lineWidth = 1.5;
    placed.forEach(e => {
      const b = new THREE.Box3().setFromObject(e.object3d), xs = [], ys = [];
      for (let i = 0; i < 8; i++) {
        const v = new THREE.Vector3(i & 1 ? b.max.x : b.min.x, i & 2 ? b.max.y : b.min.y, i & 4 ? b.max.z : b.min.z).project(cam);
        xs.push((v.x * 0.5 + 0.5) * W); ys.push((-v.y * 0.5 + 0.5) * H);
      }
      ctx.strokeRect(Math.min(...xs), Math.min(...ys), Math.max(...xs) - Math.min(...xs), Math.max(...ys) - Math.min(...ys));
    });
    // zachyt vsech fillText (text, pismo, transformace) - mereni velikosti a kolizi popisku
    const texty = [], orig = ctx.fillText.bind(ctx);
    ctx.fillText = (t, x, y) => {
      const m = ctx.getTransform(), w = ctx.measureText(t).width, px = parseFloat(/(\d+(\.\d+)?)px/.exec(ctx.font)[1]);
      const x0 = ctx.textAlign === 'center' ? x - w / 2 : x;
      const pts = [[x0, y - 0.8 * px], [x0 + w, y - 0.8 * px], [x0 + w, y + 0.2 * px], [x0, y + 0.2 * px]].map(([a, b]) => [m.a * a + m.c * b + m.e, m.b * a + m.d * b + m.f]);
      texty.push({ text: t, px, minX: Math.min(...pts.map(p => p[0])), maxX: Math.max(...pts.map(p => p[0])), minY: Math.min(...pts.map(p => p[1])), maxY: Math.max(...pts.map(p => p[1])) });
      orig(t, x, y);
    };
    const opts = Object.assign({ chainMerge: true, occlusion: 'loose', totals: 'segmentsOnly' }, kotaScaleRel ? { kotaScaleRel } : {});
    window.drawDimensionOverlay(ctx, W, H, opts);
    const mimo = texty.filter(t => t.minX < -0.5 || t.minY < -0.5 || t.maxX > W + 0.5 || t.maxY > H + 0.5).map(t => t.text);
    let prekryvy = 0;
    for (let i = 0; i < texty.length; i++) for (let j = i + 1; j < texty.length; j++) {
      const a = texty[i], b = texty[j];
      if (a.minX < b.maxX - 1 && a.maxX > b.minX + 1 && a.minY < b.maxY - 1 && a.maxY > b.minY + 1) prekryvy++;
    }
    return { png: cv.toDataURL('image/png'), W, H, layout: lay, padding, popisku: texty.length, pismo: texty.length ? Math.max(...texty.map(t => t.px)) : null, mimo, prekryvy,
             modelPx: Math.round(Math.max(modelW, 1) / (2 * h * aspect) * W) };
  }, cfg);
}

module.exports = { otevri, vykresli, vytahniFunkci, zdroje };
