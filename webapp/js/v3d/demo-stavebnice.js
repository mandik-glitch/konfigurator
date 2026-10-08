/*
 * Plugin pro viewer3d.js: samopohyblivá ukázka "stavebnice" (bot10, 2026-10-03).
 * Přehraje zacyklenou animaci z GLB (klip `demo`), ukáže popisky (kotvené na pohyblivé díly + text pro stránku) a sám vede kameru.
 *
 *   var demo = V3D.demoPlugin({ texts: { intro: '...', kamen: '...' }, onCue: function (cue, text) { ... } });
 *   V3D.mount(el, { modelUrl: 'stavebnice-demo.glb', mode: 'real', allowReal: true, plugins: [demo.plugin] });
 *   demo.pause(); demo.play(); demo.restart(); demo.seek(12.5); demo.toggle();
 *
 * GLB (viz scripts/stavebnice/README): scenes[0].extras.demo = { v:1, duration, loop, poster,
 *   cues: [{ id, t0, t1, anchor: 'a_uzel' | null, side: 'left'|'right'|'top'|'bottom' }],
 *   camera: [{ t, pos:[x,y,z], target:[x,y,z], ease:'inout'|'linear', fit: poloměr_mm }],
 *   fade: { t0, t1 } }.  Texty nejsou v GLB: `options.texts[cue.id]` (stránka je překládá).
 *
 * Barva akcentu popisků a spojnic: CSS proměnné `--v3d-demo-accent` (výchozí #2fe07a) a `--v3d-demo-accent-soft` na rodiči prohlížeče (např. mini-shop s jinou barvou).
 * Možnosti: texts, clip ('demo'), autoplay (true), loop (z GLB), speed (1), startTime (0), reducedMotion (výchozí z prohlížeče:
 *   spustí se pozastavené na snímku `poster`), pauseWhenHidden (true: karta na pozadí / mimo obrazovku), userIdleMs (6000: po
 *   ruční manipulaci s kamerou ji plugin pustí a po klidu se plynule vrátí), labels (true = popisky v 3D),
 *   smooth (true: materiály s extras.smooth v GLB se stínují hladce, ne fasetově),
 *   labelLayout ('margin' výchozí: popisek leží v rezervovaném pruhu u okraje (vlevo na širokém okně, nahoře na úzkém), tenká spojnice vede
 *   k dílu (věty bez kotvy, např. úvod a závěr, jsou v pruhu bez spojnice) a kamera rámuje díly do zbývající plochy, takže popisek nic nezakrývá; 'anchor' = starý popisek přímo u dílu),
 *   onCue(cue|null, text|null), onTime(t, duration), onState('play'|'pause').
 * Kroky (živé ovládání jako u šuplíků): extras.demo.steps = [{ id, t0, t1, g:[...] }] (bez nich se berou cues);
 *   demo.steps(), demo.playStep(id, {stop:false}) (skočí na začátek kroku; výchozí = přehraje jen ten krok a na jeho konci zastaví, se stop:false jede dál), demo.stepForGroup(g) (klik na díl s extras.g -> id kroku).
 * Pomocné: demo.layout() ({mode:'none'|'side'|'top', W, H, colW, bandH}), demo.screenRect([g,...]) (obdélník dílů na obrazovce v px plátna).
 * Události: demo.on('cue'|'time'|'state'|'loop', fn). Vše bez závislostí mimo THREE (a THREE.CSS2DObject pro popisky v 3D).
 * Po načtení nového modelu (setModel) se plugin znovu inicializuje (viewer ho ukončí a zavolá znovu).
 */
(function (global) {
  'use strict';
  var V3D = global.V3D = global.V3D || {};

  var CSS_ID = 'v3d-demo-css';
  var CSS = [
    '.v3d-demo-label{position:absolute;pointer-events:none;font:600 14px/1.25 -apple-system,"Segoe UI",Roboto,Arial,sans-serif;color:#fff;',
    'background:rgba(15,23,34,.88);border:1px solid var(--v3d-demo-accent,#2fe07a);padding:6px 10px;max-width:220px;white-space:normal;',
    'clip-path:polygon(0 0,calc(100% - 8px) 0,100% 8px,100% 100%,8px 100%,0 calc(100% - 8px));opacity:0;transition:opacity .35s;',
    'text-align:left;box-shadow:0 2px 10px rgba(0,0,0,.35)}',
    '.v3d-demo-label.is-on{opacity:1}',
    '.v3d-demo-label::before{content:"";position:absolute;width:9px;height:9px;border-radius:50%;background:var(--v3d-demo-accent,#2fe07a);box-shadow:0 0 0 3px var(--v3d-demo-accent-soft,rgba(47,224,122,.35))}',
    '.v3d-demo-label.left{transform:translate(calc(-100% - 22px),-50%)}.v3d-demo-label.left::before{right:-26px;top:calc(50% - 4px)}',
    '.v3d-demo-label.right{transform:translate(22px,-50%)}.v3d-demo-label.right::before{left:-26px;top:calc(50% - 4px)}',
    '.v3d-demo-label.top{transform:translate(-50%,calc(-100% - 20px))}.v3d-demo-label.top::before{left:calc(50% - 4px);bottom:-24px}',
    '.v3d-demo-label.bottom{transform:translate(-50%,20px)}.v3d-demo-label.bottom::before{left:calc(50% - 4px);top:-24px}',
    /* popisky v pruhu u okraje (labelLayout 'margin') */
    '.v3d-demo-ov{position:absolute;pointer-events:none;overflow:hidden;z-index:4}',
    '.v3d-demo-ov svg{position:absolute;left:0;top:0;width:100%;height:100%;overflow:visible}',
    '.v3d-demo-ov line{stroke:var(--v3d-demo-accent,#2fe07a);stroke-width:1.5;opacity:.95}.v3d-demo-ov circle{fill:var(--v3d-demo-accent,#2fe07a);stroke:var(--v3d-demo-accent-soft,rgba(47,224,122,.35));stroke-width:6}',
    '.v3d-demo-tag{position:absolute;left:0;top:0;box-sizing:border-box;font:600 14px/1.3 -apple-system,"Segoe UI",Roboto,Arial,sans-serif;color:#fff;',
    'background:rgba(15,23,34,.94);border:1px solid var(--v3d-demo-accent,#2fe07a);padding:7px 10px;white-space:normal;text-align:left;opacity:0;transition:opacity .3s;',
    'clip-path:polygon(0 0,calc(100% - 8px) 0,100% 8px,100% 100%,8px 100%,0 calc(100% - 8px));box-shadow:0 2px 10px rgba(0,0,0,.35);will-change:transform}',
    '.v3d-demo-tag.is-on{opacity:1}.v3d-demo-tag.measure{visibility:hidden;transition:none}.v3d-demo-ov.top .v3d-demo-tag{font-size:13px;padding:6px 9px}'
  ].join('');
  function ensureCss() {
    try {
      if (document.getElementById(CSS_ID)) return;
      var s = document.createElement('style'); s.id = CSS_ID; s.textContent = CSS; document.head.appendChild(s);
    } catch (e) { /* bez stylu */ }
  }

  function smooth(x) { x = x < 0 ? 0 : (x > 1 ? 1 : x); return x * x * (3 - 2 * x); }
  function isVec3(a) { return Array.isArray(a) && a.length === 3 && a.every(function (n) { return typeof n === 'number' && isFinite(n); }); }

  V3D.demoPlugin = function (options) {
    options = options || {};
    var texts = options.texts || {};
    var listeners = { cue: [], time: [], state: [], loop: [] };
    function emit(ev, a, b) { (listeners[ev] || []).slice().forEach(function (f) { try { f(a, b); } catch (e) { /* posluchac */ } }); }

    // stav, ktery preziva (znovu)inicializaci pluginu
    var want = {
      playing: options.autoplay !== false,
      speed: typeof options.speed === 'number' && options.speed > 0 ? options.speed : 1,
      t: typeof options.startTime === 'number' ? options.startTime : 0,
      userPaused: false
    };
    var reduced = options.reducedMotion;
    if (reduced == null) { try { reduced = !!(global.matchMedia && global.matchMedia('(prefers-reduced-motion: reduce)').matches); } catch (e) { reduced = false; } }
    var live = null;      // aktivni instance (po inicializaci)

    function plugin(ctx) {
      var THREE = ctx.THREE;
      ensureCss();
      var scene0 = ctx.gltf && ctx.gltf.scenes && ctx.gltf.scenes[0];
      var demo = (scene0 && scene0.userData && scene0.userData.demo) || null;
      var clips = (ctx.gltf && ctx.gltf.animations) || [];
      var clip = null;
      for (var i = 0; i < clips.length; i++) if (clips[i].name === (options.clip || 'demo')) clip = clips[i];
      if (!clip && clips.length) clip = clips[0];
      var D = (demo && typeof demo.duration === 'number' && demo.duration > 0) ? demo.duration : (clip ? clip.duration : 0);
      var loop = demo ? demo.loop !== false : true;
      if (options.loop === false) loop = false;

      // hladke stinovani pro materialy s extras.smooth (valce, otvory, zaobleni; viewer jinak vsem vnucuje flatShading)
      if (options.smooth !== false) {
        ctx.model.traverse(function (o) {
          if (!o.isMesh) return;
          (Array.isArray(o.material) ? o.material : [o.material]).forEach(function (m) {
            if (m && m.userData && m.userData.smooth && m.flatShading) { m.flatShading = false; m.needsUpdate = true; }
          });
        });
      }

      var mixer = null, action = null;
      if (clip) {
        mixer = new THREE.AnimationMixer(ctx.model);
        action = mixer.clipAction(clip);
        action.setLoop(THREE.LoopRepeat, Infinity);
        action.clampWhenFinished = true;
        action.play();
      }
      var cues = (demo && Array.isArray(demo.cues) ? demo.cues : []).filter(function (c) {
        return c && typeof c.id === 'string' && typeof c.t0 === 'number' && typeof c.t1 === 'number' && c.t1 > c.t0;
      }).slice().sort(function (a, b) { return a.t0 - b.t0; });
      var steps = (demo && Array.isArray(demo.steps) && demo.steps.length ? demo.steps : cues).filter(function (c) {
        return c && typeof c.id === 'string' && typeof c.t0 === 'number' && typeof c.t1 === 'number' && c.t1 > c.t0;
      }).map(function (c) { return { id: c.id, t0: c.t0, t1: c.t1, g: Array.isArray(c.g) ? c.g.slice() : [] }; });
      var keys = (demo && Array.isArray(demo.camera) ? demo.camera : []).filter(function (k) {
        return k && typeof k.t === 'number' && isVec3(k.pos) && isVec3(k.target);
      }).slice().sort(function (a, b) { return a.t - b.t; });

      var t = Math.max(0, Math.min(want.t, D || 0));
      var playing = false, autoPaused = false, lastMs = null, activeCue = null, label = null, labelEl = null, labelAnchor = null;
      var userUntil = 0, userPose = null, blend = 1, camSet = false, disposed = false, stopAt = null;
      var offFrame = null;
      var tmpP = new THREE.Vector3(), tmpT = new THREE.Vector3(), tmpA = new THREE.Vector3(), tmpB = new THREE.Box3();
      var marginOn = options.labels !== false && options.labelLayout !== 'anchor';
      var layout = { mode: 'none', W: 0, H: 0, colW: 0, bandH: 0, Wu: 0, Hu: 0, key: '' };
      var ov = null, ovSvg = null, ovLine = null, ovDot = null, tag = null, tagNode = null, tagX = null, tagY = null, tagW = 0, tagH = 0;

      // ---- kamera: pozice a cil v case t (Catmull-Rom mezi klicovymi snimky, 'inout' = hladky start/konec useku) ----
      function keyPose(k, out) {
        out.pos.fromArray(k.pos); out.target.fromArray(k.target);
        if (typeof k.fit === 'number' && k.fit > 0) {
          var cam = ctx.camera, vf = cam.fov * Math.PI / 180;
          var half = Math.atan(Math.tan(vf / 2) * freeRatio());       // pulzorny uhel volne plochy (bez pruhu pro popisky)
          var dist = (k.fit / Math.sin(half)) * 1.06;
          var dir = out.pos.clone().sub(out.target); if (dir.lengthSq() < 1e-9) dir.set(0, 0, 1);
          out.pos.copy(out.target).add(dir.normalize().multiplyScalar(dist));
        }
        return out;
      }
      function freeRatio() {                                       // mensi rozmer volne plochy / vyska plochy
        var W = layout.W || ctx.camera.aspect || 1, H = layout.H || 1;
        if (!layout.W) return Math.min(1, ctx.camera.aspect || 1);
        return Math.min(layout.Wu, layout.Hu) / H;
      }
      var poses = null;
      function buildPoses() { poses = keys.map(function (k) { return keyPose(k, { pos: new THREE.Vector3(), target: new THREE.Vector3() }); }); }
      function cr(p0, p1, p2, p3, u, out) {
        var u2 = u * u, u3 = u2 * u;
        out.x = 0.5 * ((2 * p1.x) + (-p0.x + p2.x) * u + (2 * p0.x - 5 * p1.x + 4 * p2.x - p3.x) * u2 + (-p0.x + 3 * p1.x - 3 * p2.x + p3.x) * u3);
        out.y = 0.5 * ((2 * p1.y) + (-p0.y + p2.y) * u + (2 * p0.y - 5 * p1.y + 4 * p2.y - p3.y) * u2 + (-p0.y + 3 * p1.y - 3 * p2.y + p3.y) * u3);
        out.z = 0.5 * ((2 * p1.z) + (-p0.z + p2.z) * u + (2 * p0.z - 5 * p1.z + 4 * p2.z - p3.z) * u2 + (-p0.z + 3 * p1.z - 3 * p2.z + p3.z) * u3);
        return out;
      }
      function scriptedPose(time, outP, outT) {
        if (!keys.length) return false;
        if (!poses) buildPoses();
        var n = keys.length;
        if (time <= keys[0].t) { outP.copy(poses[0].pos); outT.copy(poses[0].target); return true; }
        if (time >= keys[n - 1].t) { outP.copy(poses[n - 1].pos); outT.copy(poses[n - 1].target); return true; }
        var s = 0; while (s < n - 2 && time >= keys[s + 1].t) s++;
        var k0 = keys[s], k1 = keys[s + 1], u = (time - k0.t) / (k1.t - k0.t);
        if (k1.ease !== 'linear') u = smooth(u);
        var a = poses[Math.max(0, s - 1)], b = poses[s], c = poses[s + 1], d = poses[Math.min(n - 1, s + 2)];
        cr(a.pos, b.pos, c.pos, d.pos, u, outP);
        cr(a.target, b.target, c.target, d.target, u, outT);
        return true;
      }

      // ---- popisky: 'margin' = v pruhu u okraje + spojnice k dilu (nic nezakryva), 'anchor' = u dilu (CSS2D) ----
      function hideLabel() {
        if (label && labelAnchor) { labelAnchor.remove(label); }
        if (labelEl) labelEl.classList.remove('is-on');
        label = null; labelEl = null; labelAnchor = null;
        if (tag && tag.parentNode) tag.parentNode.removeChild(tag);
        tag = null; tagNode = null; tagX = tagY = null;
        if (ovLine) { ovLine.setAttribute('visibility', 'hidden'); ovDot.setAttribute('visibility', 'hidden'); }
      }
      function ensureOverlay() {
        if (ov) return ov;
        var cv = ctx.renderer.domElement, host = cv.parentNode || ctx.root || ctx.container;
        ov = document.createElement('div'); ov.className = 'v3d-demo-ov';
        var NS = 'http://www.w3.org/2000/svg';
        ovSvg = document.createElementNS(NS, 'svg');
        ovLine = document.createElementNS(NS, 'line'); ovDot = document.createElementNS(NS, 'circle'); ovDot.setAttribute('r', '4');
        ovLine.setAttribute('visibility', 'hidden'); ovDot.setAttribute('visibility', 'hidden');
        ovSvg.appendChild(ovLine); ovSvg.appendChild(ovDot); ov.appendChild(ovSvg);
        host.appendChild(ov);
        return ov;
      }
      function measureBand(W, tagWidth) {                          // vyska nejdelsiho popisku -> pruh nahore je pro vsechny stejne vysoky (kamera neskace)
        var maxH = 0, m = document.createElement('div');
        m.className = 'v3d-demo-tag measure'; m.style.width = tagWidth + 'px';
        ensureOverlay(); ov.classList.add('top'); ov.appendChild(m);
        cues.forEach(function (c) {
          if (texts[c.id] == null) return;
          m.textContent = String(texts[c.id]); maxH = Math.max(maxH, m.offsetHeight);
        });
        ov.removeChild(m);
        return maxH;
      }
      function applyLayout() {
        var cv = ctx.renderer.domElement, W = cv.clientWidth || 0, H = cv.clientHeight || 0;
        if (!marginOn || W < 40 || H < 40) {
          if (layout.mode !== 'none') { try { ctx.camera.clearViewOffset(); } catch (e) { /* */ } layout.mode = 'none'; layout.key = ''; layout.W = 0; poses = null; if (ov) ov.style.display = 'none'; }
          return false;
        }
        var key = W + 'x' + H;
        if (layout.key === key) return false;
        var side = W >= 640 && W / H >= 1.1;
        layout.mode = side ? 'side' : 'top'; layout.W = W; layout.H = H; layout.key = key;
        if (side) {
          layout.colW = Math.max(170, Math.min(270, Math.round(W * 0.27))); layout.bandH = 0;
          tagW = layout.colW - 20; layout.Wu = W - layout.colW; layout.Hu = H;
        } else {
          tagW = Math.min(W - 20, 440);
          layout.bandH = Math.max(56, measureBand(W, tagW) + 20); layout.colW = 0;
          layout.Wu = W; layout.Hu = H - layout.bandH;
        }
        ensureOverlay();
        ov.style.display = ''; ov.className = 'v3d-demo-ov ' + (side ? 'side' : 'top');
        ov.style.left = cv.offsetLeft + 'px'; ov.style.top = cv.offsetTop + 'px'; ov.style.width = W + 'px'; ov.style.height = H + 'px';
        ctx.camera.setViewOffset(W, H, -layout.colW / 2, -layout.bandH / 2, W, H);   // predmet se zobrazi ve volne plose vedle pruhu
        poses = null;
        if (tag) { tag.style.width = tagW + 'px'; tagH = tag.offsetHeight; }
        return true;
      }
      function showLabel(cue, text) {
        hideLabel();
        if (options.labels === false || !cue || !text) return;
        if (!marginOn && !cue.anchor) return;                       // staré umístění u dílu potřebuje kotvu; v pruhu se bezkotvové věty (úvod, závěr) ukážou bez spojnice
        var node = cue.anchor ? ctx.model.getObjectByName(cue.anchor) : null;
        if (cue.anchor && !node) return;
        if (marginOn) {
          applyLayout(); ensureOverlay();
          tag = document.createElement('div'); tag.className = 'v3d-demo-tag'; tag.textContent = text;
          tag.style.width = tagW + 'px'; ov.appendChild(tag); tagH = tag.offsetHeight; tagNode = node; tagX = tagY = null;
          updateTag(0);
          global.requestAnimationFrame(function () { if (tag) tag.classList.add('is-on'); });
          return;
        }
        if (!THREE.CSS2DObject) return;
        var el = document.createElement('div');
        el.className = 'v3d-demo-label ' + (['left', 'right', 'top', 'bottom'].indexOf(cue.side) >= 0 ? cue.side : 'right');
        el.textContent = text;
        label = new THREE.CSS2DObject(el);
        node.add(label);
        labelEl = el; labelAnchor = node;
        global.requestAnimationFrame(function () { if (el) el.classList.add('is-on'); });
      }
      function updateTag(dt) {                                      // poloha popisku v pruhu + spojnice k dilu (kazdy snimek)
        if (!tag || layout.mode === 'none') return;
        var cam = ctx.camera, W = layout.W, H = layout.H;
        if (!tagNode) {                                             // veta bez dilu: v pruhu na pevnem miste, bez spojnice
          tagX = layout.mode === 'side' ? 10 : Math.max(10, (W - tagW) / 2); tagY = layout.mode === 'side' ? Math.max(10, H * 0.12) : 10;
          tag.style.transform = 'translate(' + tagX.toFixed(1) + 'px,' + tagY.toFixed(1) + 'px)';
          ovLine.setAttribute('visibility', 'hidden'); ovDot.setAttribute('visibility', 'hidden');
          return;
        }
        cam.updateMatrixWorld(true);
        tagNode.getWorldPosition(tmpA); tmpA.project(cam);
        var ax = (tmpA.x * 0.5 + 0.5) * W, ay = (-tmpA.y * 0.5 + 0.5) * H, front = tmpA.z > -1 && tmpA.z < 1;
        var k = dt > 0 ? 1 - Math.exp(-dt * 7) : 1, tx, ty, x1, y1;
        if (layout.mode === 'side') {
          tx = 10; ty = Math.max(10, Math.min(H - tagH - 56, ay - tagH / 2));
          if (tagY == null) tagY = ty; tagY += (ty - tagY) * k; tagX = tx;
          x1 = tagX + tagW; y1 = tagY + tagH / 2;
        } else {
          tx = Math.max(10, Math.min(W - tagW - 10, ax - tagW / 2)); ty = 10;
          if (tagX == null) tagX = tx; tagX += (tx - tagX) * k; tagY = ty;
          x1 = Math.max(tagX + 14, Math.min(tagX + tagW - 14, ax)); y1 = tagY + tagH;
        }
        tag.style.transform = 'translate(' + tagX.toFixed(1) + 'px,' + tagY.toFixed(1) + 'px)';
        var vis = front && ax > -20 && ax < W + 20 && ay > -20 && ay < H + 20;
        ovLine.setAttribute('visibility', vis ? 'visible' : 'hidden'); ovDot.setAttribute('visibility', vis ? 'visible' : 'hidden');
        if (vis) {
          ovLine.setAttribute('x1', x1.toFixed(1)); ovLine.setAttribute('y1', y1.toFixed(1)); ovLine.setAttribute('x2', ax.toFixed(1)); ovLine.setAttribute('y2', ay.toFixed(1));
          ovDot.setAttribute('cx', ax.toFixed(1)); ovDot.setAttribute('cy', ay.toFixed(1));
        }
      }
      function screenRect(gs) {                                     // obdelnik dilu se skupinou g na obrazovce (px platna); null = nic
        var cam = ctx.camera, W = layout.W || ctx.renderer.domElement.clientWidth, H = layout.H || ctx.renderer.domElement.clientHeight, r = null;
        cam.updateMatrixWorld(true); ctx.model.updateMatrixWorld(true);
        ctx.model.traverse(function (o) {
          if (!o.isMesh || !gs || gs.indexOf(groupOf(o)) < 0) return;
          tmpB.setFromObject(o);
          for (var i = 0; i < 8; i++) {
            tmpA.set(i & 1 ? tmpB.max.x : tmpB.min.x, i & 2 ? tmpB.max.y : tmpB.min.y, i & 4 ? tmpB.max.z : tmpB.min.z).project(cam);
            var x = (tmpA.x * 0.5 + 0.5) * W, y = (-tmpA.y * 0.5 + 0.5) * H;
            if (!r) r = { x0: x, y0: y, x1: x, y1: y }; else { r.x0 = Math.min(r.x0, x); r.y0 = Math.min(r.y0, y); r.x1 = Math.max(r.x1, x); r.y1 = Math.max(r.y1, y); }
          }
        });
        return r;
      }
      function groupOf(o) { while (o) { if (o.userData && typeof o.userData.g === 'number') return o.userData.g; o = o.parent; } return -1; }
      function updateCue() {
        var found = null;
        for (var i = 0; i < cues.length; i++) if (t >= cues[i].t0 && t < cues[i].t1) found = cues[i];
        if ((found && found.id) === (activeCue && activeCue.id)) return;
        activeCue = found;
        var text = found ? (texts[found.id] != null ? String(texts[found.id]) : null) : null;
        showLabel(found, text);
        if (typeof options.onCue === 'function') { try { options.onCue(found, text); } catch (e) { /* stranka */ } }
        emit('cue', found, text);
      }

      // ---- vykresleni jednoho okamziku animace ----
      function applyTime(dtSec) {
        if (mixer && action) { action.time = Math.min(t, Math.max(0, clip.duration - 1e-4)); mixer.update(0); }
        applyLayout();
        updateCue();
        updateCamera(dtSec);
        updateTag(dtSec);
        if (typeof options.onTime === 'function') { try { options.onTime(t, D); } catch (e) { /* stranka */ } }
        emit('time', t, D);
      }
      function updateCamera(dtSec) {
        if (!scriptedPose(t, tmpP, tmpT)) return;
        var nowMs = global.performance ? global.performance.now() : Date.now();
        if (nowMs < userUntil) { return; }                       // uzivatel ma kameru
        if (userPose) {                                          // navrat k choreografii: plynuly prechod z ruci nastavene pozice
          blend = Math.min(1, blend + dtSec / 1.2);
          var w = smooth(blend);
          tmpP.lerpVectors(userPose.pos, tmpP, w); tmpT.lerpVectors(userPose.target, tmpT, w);
          if (blend >= 1) userPose = null;
        }
        ctx.camera.position.copy(tmpP);
        ctx.controls.target.copy(tmpT);
        ctx.camera.lookAt(tmpT);
        ctx.controls.update();
        camSet = true;
      }
      function onUserStart() {
        var idle = typeof options.userIdleMs === 'number' ? options.userIdleMs : 6000;
        userUntil = (global.performance ? global.performance.now() : Date.now()) + idle;
        userPose = null; blend = 0;
      }
      function onUserEnd() {
        var idle = typeof options.userIdleMs === 'number' ? options.userIdleMs : 6000;
        userUntil = (global.performance ? global.performance.now() : Date.now()) + idle;
        userPose = { pos: ctx.camera.position.clone(), target: ctx.controls.target.clone() };
        blend = 0;
      }
      ctx.controls.addEventListener('start', onUserStart);
      ctx.controls.addEventListener('end', onUserEnd);

      // ---- prehravani ----
      function setPlaying(p, auto) {
        p = !!p && D > 0;
        if (!auto) want.userPaused = !p;
        if (p === playing && (!auto || p === !autoPaused)) { return; }
        playing = p;
        lastMs = null;
        ctx.setAnimating(playing && !autoPaused);
        ctx.requestRender();
        want.playing = playing;
        if (!auto) { emit('state', playing ? 'play' : 'pause'); if (typeof options.onState === 'function') { try { options.onState(playing ? 'play' : 'pause'); } catch (e) { /* stranka */ } } }
      }
      offFrame = ctx.onFrame(function (ms) {
        if (disposed) return;
        var dt = lastMs == null ? 0 : Math.min(0.25, (ms - lastMs) / 1000);
        lastMs = ms;
        if (playing && !autoPaused && D > 0) {
          t += dt * want.speed;
          if (stopAt != null && t >= stopAt) {            // prehrani jednoho kroku: zastavit na jeho konci
            t = stopAt; stopAt = null; playing = false; ctx.setAnimating(false);
            emit('state', 'pause'); if (typeof options.onState === 'function') { try { options.onState('pause'); } catch (e) { /* */ } }
          } else if (t >= D) {
            if (loop) { t = t % D; emit('loop'); } else { t = D; playing = false; ctx.setAnimating(false); emit('state', 'pause'); if (typeof options.onState === 'function') { try { options.onState('pause'); } catch (e) { /* */ } } }
          }
        }
        applyTime(dt);
      });

      // ---- viditelnost: karta na pozadi / mimo obrazovku = pauza (setri baterii) ----
      var io = null;
      function visChange() {
        var hidden = !!document.hidden || offscreen;
        if (hidden === autoPaused) return;
        autoPaused = hidden;
        if (playing) { lastMs = null; ctx.setAnimating(!autoPaused); if (!autoPaused) ctx.requestRender(); }
      }
      var offscreen = false;
      if (options.pauseWhenHidden !== false) {
        document.addEventListener('visibilitychange', visChange);
        if (global.IntersectionObserver && ctx.container) {
          io = new global.IntersectionObserver(function (es) { offscreen = !es[es.length - 1].isIntersecting; visChange(); }, { threshold: 0.05 });
          io.observe(ctx.container);
        }
      }

      // ---- ovladani (zvenku) ----
      live = {
        play: function () { stopAt = null; setPlaying(true, false); },
        pause: function () { setPlaying(false, false); },
        toggle: function () { setPlaying(!playing, false); },
        restart: function () { stopAt = null; t = 0; lastMs = null; userUntil = 0; userPose = null; blend = 1; activeCue = null; applyTime(0); if (!playing) setPlaying(true, false); else ctx.requestRender(); },
        seek: function (sec) { stopAt = null; t = Math.max(0, Math.min(D, +sec || 0)); userUntil = 0; userPose = null; blend = 1; applyTime(0); ctx.requestRender(); },
        time: function () { return t; },
        duration: function () { return D; },
        isPlaying: function () { return playing; },
        setSpeed: function (x) { if (x > 0 && x <= 4) want.speed = x; },
        cues: function () { return cues.slice(); },
        steps: function () { return steps.slice(); },
        playStep: function (id, o) {
          var st = null; for (var i = 0; i < steps.length; i++) if (steps[i].id === id) st = steps[i];
          if (!st) return false;
          t = st.t0; stopAt = (o && o.stop === false) ? null : st.t1; lastMs = null; userUntil = 0; userPose = null; blend = 1; activeCue = null;
          applyTime(0); setPlaying(true, false); return true;
        },
        stepForGroup: function (gg) {
          for (var i = 0; i < steps.length; i++) if (steps[i].g.indexOf(gg) >= 0) return steps[i].id;
          return null;
        },
        layout: function () { return { mode: layout.mode, W: layout.W, H: layout.H, colW: layout.colW, bandH: layout.bandH }; },
        screenRect: screenRect
      };

      // pocatecni stav: kamera/animace v case t hned (bez skoku), pak start nebo (omezit animace) pauza na snimku poster
      if (reduced && want.t === 0 && demo && typeof demo.poster === 'number') t = Math.max(0, Math.min(D, demo.poster));
      applyTime(0);
      var startPlaying = want.userPaused ? false : (reduced ? false : want.playing);
      if (startPlaying) setPlaying(true, true); else { playing = false; ctx.requestRender(); }

      // ukonceni pri setModel/dispose
      return function dispose() {
        disposed = true;
        want.t = t; want.playing = playing || want.playing;
        try { if (offFrame) offFrame(); } catch (e) { /* */ }
        try { ctx.controls.removeEventListener('start', onUserStart); ctx.controls.removeEventListener('end', onUserEnd); } catch (e) { /* */ }
        document.removeEventListener('visibilitychange', visChange);
        if (io) { try { io.disconnect(); } catch (e) { /* */ } }
        hideLabel();
        if (layout.mode !== 'none') { try { ctx.camera.clearViewOffset(); } catch (e) { /* */ } }
        if (ov && ov.parentNode) ov.parentNode.removeChild(ov);
        ov = null;
        if (mixer) { try { mixer.stopAllAction(); mixer.uncacheRoot(ctx.model); } catch (e) { /* */ } }
        ctx.setAnimating(false);
        live = null;
      };
    }

    function call(name) { return function (a) { if (live) return live[name](a); if (name === 'play') { want.userPaused = false; want.playing = true; } if (name === 'pause') { want.userPaused = true; want.playing = false; } if (name === 'setSpeed' && a > 0) want.speed = a; if (name === 'seek') want.t = +a || 0; return undefined; }; }
    return {
      plugin: plugin,
      play: call('play'), pause: call('pause'), toggle: function () { if (live) live.toggle(); else { want.userPaused = want.playing; want.playing = !want.playing; } },
      restart: call('restart'), seek: call('seek'), setSpeed: call('setSpeed'),
      time: function () { return live ? live.time() : want.t; },
      duration: function () { return live ? live.duration() : 0; },
      isPlaying: function () { return live ? live.isPlaying() : !!want.playing; },
      cues: function () { return live ? live.cues() : []; },
      steps: function () { return live ? live.steps() : []; },
      playStep: function (id, o) { return live ? live.playStep(id, o) : false; },
      stepForGroup: function (g) { return live ? live.stepForGroup(g) : null; },
      layout: function () { return live ? live.layout() : { mode: 'none', W: 0, H: 0, colW: 0, bandH: 0 }; },
      screenRect: function (gs) { return live ? live.screenRect(gs) : null; },
      on: function (ev, fn) { if (listeners[ev] && typeof fn === 'function') listeners[ev].push(fn); return function () { var l = listeners[ev], i = l.indexOf(fn); if (i >= 0) l.splice(i, 1); }; }
    };
  };
})(typeof window !== 'undefined' ? window : this);
