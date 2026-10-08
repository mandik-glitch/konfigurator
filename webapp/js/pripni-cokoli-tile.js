/*
 * Prvek "Připni cokoli" pro mřížku na kartě (např. karta stolu v mini-shopu): samopohyblivá živá 3D ukázka připevnění dílu do T-drážky profilu (bot10, 2026-10-03).
 * Vkládá se jedním voláním, nic dalšího není potřeba; bez značky (žádné jméno firmy ani dodavatele, žádné odkazy ven kromě skriptů three z CDN).
 * Revize dat: model 40×40 v2, model 30×30 v5 (Robert schválil 2026-10-04; zive:true v texty.json), texty EN „slot“ místo „groove“ (Robert 2026-10-05). Po výměně modelu nebo textů změnit tuhle řádku, aby mini-shop dostal novou verzi (?v= = hash tohoto souboru).
 *
 *   PripniCokoliTile.mount(document.getElementById('policko'), { lang: 'en' }).then(function (ctl) { ... });   // ctl.destroy(), ctl.play(), ctl.pause()
 *
 * Možnosti:
 *   profile     profil generatoru, ke kteremu se ma animace sama sparovat: '30x30', '30', 'Object_7', SKU '1.1.08.030030.03', cislo produktu profilu nebo text se "systém 30"
 *               (registr v texty.json, _profily). Bez profile = vychozi 40x40. Profil bez animace nebo s `zive:false` (neschvaleno): mount() vrati null a nic nevykresli.
 *   variant     primo klic varianty (napr. '30x30-d8'), preskoci rozpoznani
 *   lang        'cs' | 'en' | 'sk' (výchozí 'en'; jazyk mimo seznam aktivních v texty.json -> 'cs')
 *   assetBase   adresář s modelem a texty (výchozí '/pripni-cokoli/': soubory stavebnice-demo.glb a texty.json)
 *   version     řetězec přidaný jako ?v= k modelu a textům (obejde mezipaměť po výměně souborů; mini-shop má Cloudflare + expires 1 h)
 *   viewerUrl, pluginUrl   skripty prohlížeče a pluginu (výchozí '/js/v3d/viewer3d.js' a '/js/v3d/demo-stavebnice.js'; nepoužijí se, pokud už je V3D načtený)
 *   texts       { cues:{...}, viewer:{...}, play:'..', pause:'..', restart:'..', failed:'..' } - přepíše texty z texty.json (např. z i18n obchodu)
 *   accent      barva akcentu popisků a spojnic (např. '#14b8a6'); bez ní zelená
 *   bg          barva pozadí 3D plochy (výchozí #0f1722)
 *   autoplay    true (animace sama běží; mimo obrazovku a na kartě na pozadí se zastaví; "omezit animace" startuje pozastaveně)
 *   caption     false (titulek pod ukázkou se nezobrazuje, text nese popisek v 3D); true = i titulek pod ukázkou (jako na samostatné stránce)
 *   steps       false; true = pod ukázkou tlačítka kroků (skok na začátek kroku, animace jede dál)
 *   speed       násobek rychlosti (výchozí 1)
 *   viewerOpts  { ... } přidá se k volbám V3D.mount prvku (např. envConfig hlavního prohlížeče stránky: HDR se pak nestahuje podruhé, cache HDR je v prohlížeči sdílená)
 * Prvek se přizpůsobí šířce políčka (poměr 4:3, na úzkém políčku popisky nahoře, na širokém vlevo). Klepnutí na model animaci nezastaví.
 */
(function (global) {
  'use strict';
  var CDN = 'https://cdn.jsdelivr.net/npm/three@0.128.0/';
  var DEPS = ['build/three.min.js', 'examples/js/controls/OrbitControls.js', 'examples/js/loaders/GLTFLoader.js', 'examples/js/environments/RoomEnvironment.js',
    'examples/js/renderers/CSS2DRenderer.js', 'examples/js/shaders/HorizontalBlurShader.js', 'examples/js/shaders/VerticalBlurShader.js'];
  var CSS_ID = 'pct-css';
  var CSS = [
    '.pct{display:flex;flex-direction:column;gap:8px;width:100%;color:#e8eff6;font:15px/1.4 -apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}',
    '.pct-view{position:relative;width:100%;aspect-ratio:4/3;min-height:220px;background:radial-gradient(120% 90% at 50% 20%,#1f3144 0%,var(--pct-bg,#0f1722) 70%);overflow:hidden}',
    '.pct-view .v3d-tl,.pct-view .v3d-tr{display:none}.pct-view .v3d-root{background:transparent}',
    '.pct-cap{min-height:2.8em;font-weight:600;font-size:15px;line-height:1.35}.pct-cap.empty{visibility:hidden}',
    '.pct-ctl{display:flex;align-items:center;gap:8px;flex-wrap:wrap}',
    '.pct-btn{-webkit-appearance:none;appearance:none;width:42px;height:42px;display:inline-grid;place-items:center;border:1px solid rgba(255,255,255,.22);background:rgba(255,255,255,.06);color:inherit;cursor:pointer;border-radius:0}',
    '.pct-btn:hover,.pct-btn:focus-visible{border-color:var(--v3d-demo-accent,#2fe07a);outline:none}',
    '.pct-bar{flex:1 1 90px;height:4px;background:rgba(255,255,255,.18);position:relative;min-width:60px}.pct-bar>i{position:absolute;left:0;top:0;bottom:0;width:0;background:var(--v3d-demo-accent,#2fe07a)}',
    '.pct-steps{display:flex;flex-wrap:wrap;gap:6px;flex:1 1 100%}',
    '.pct-chip{-webkit-appearance:none;appearance:none;min-height:36px;padding:0 12px;border:1px solid rgba(255,255,255,.22);background:rgba(255,255,255,.06);color:inherit;font:600 13px -apple-system,"Segoe UI",Roboto,Arial,sans-serif;cursor:pointer;border-radius:0;white-space:pre}',
    '.pct-chip.on{background:var(--v3d-demo-accent,#2fe07a);border-color:var(--v3d-demo-accent,#2fe07a);color:#05140b}',
    '.pct.failed .pct-ctl{display:none}'
  ].join('');
  var ICON = {
    play: '<svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true"><path d="M8 5v14l11-7z" fill="currentColor"/></svg>',
    pause: '<svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true"><path d="M7 5h4v14H7zM13 5h4v14h-4z" fill="currentColor"/></svg>',
    restart: '<svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true"><path d="M12 5V2L7 6.5 12 11V8a6 6 0 1 1-6 6H4a8 8 0 1 0 8-9z" fill="currentColor"/></svg>'
  };
  var FALLBACK = { play: 'Play', pause: 'Pause', restart: 'Restart', failed: '3D preview unavailable' };
  var loading = {};

  function ensureCss() {
    try { if (document.getElementById(CSS_ID)) return; var s = document.createElement('style'); s.id = CSS_ID; s.textContent = CSS; document.head.appendChild(s); } catch (e) { /* bez stylu */ }
  }
  function loadScript(url) {
    if (loading[url]) return loading[url];
    loading[url] = new Promise(function (res, rej) {
      var s = document.createElement('script'); s.src = url; s.onload = res; s.onerror = function () { delete loading[url]; rej(new Error('nenacteno ' + url)); };
      document.head.appendChild(s);
    });
    return loading[url];
  }
  function ensureDeps(o) {
    var chain = Promise.resolve();
    if (!(global.THREE && global.THREE.GLTFLoader && global.THREE.OrbitControls)) DEPS.forEach(function (u) { chain = chain.then(function () { return loadScript(CDN + u); }); });
    chain = chain.then(function () { return (global.V3D && global.V3D.mount) ? null : loadScript(o.viewerUrl); });
    chain = chain.then(function () { return (global.V3D && global.V3D.demoPlugin) ? null : loadScript(o.pluginUrl); });
    return chain;
  }
  // rozpoznani profilu generatoru (stejne pravidlo je na strance pripni-cokoli-page.js): "30x30", "30", "30 x 30", "Object_7", SKU, produkt, "Stul system 30 SP002"
  function normProfile(s) { return String(s == null ? '' : s).toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/×/g, 'x').replace(/\s+/g, ''); }
  function resolveProfile(profs, id) {
    var n = normProfile(id), keys = Object.keys(profs || {});
    if (!n) return null;
    function byAlias(a) { for (var i = 0; i < keys.length; i++) { if ((profs[keys[i]].aliasy || []).indexOf(a) >= 0) return keys[i]; } return null; }
    var r = byAlias(n); if (r) return r;
    var m = /(\d{2,3})x(\d{2,3})/.exec(n); if (m && (r = byAlias(m[1] + 'x' + m[2]))) return r;
    m = /(?:system|sys)(\d{2,3})/.exec(n); if (m && (r = byAlias(m[1]))) return r;
    return null;
  }
  function el(tag, cls, html) { var e = document.createElement(tag); if (cls) e.className = cls; if (html != null) e.innerHTML = html; return e; }

  function mount(host, options) {
    var o = options || {};
    o.assetBase = (o.assetBase || '/pripni-cokoli/').replace(/\/?$/, '/');
    o.viewerUrl = o.viewerUrl || '/js/v3d/viewer3d.js';
    o.pluginUrl = o.pluginUrl || '/js/v3d/demo-stavebnice.js';
    var ver = o.version ? '?v=' + encodeURIComponent(o.version) : '';
    ensureCss();
    host.textContent = '';
    var root = el('div', 'pct'), view = el('div', 'pct-view'), cap = el('div', 'pct-cap empty'), ctl = el('div', 'pct-ctl');
    cap.setAttribute('aria-live', 'polite');
    var btnPlay = el('button', 'pct-btn'), btnRe = el('button', 'pct-btn'), bar = el('div', 'pct-bar', '<i></i>'), chipsBox = el('div', 'pct-steps');
    btnPlay.type = 'button'; btnRe.type = 'button'; btnRe.innerHTML = ICON.restart;
    ctl.appendChild(btnPlay); ctl.appendChild(btnRe); ctl.appendChild(bar);
    if (o.steps) ctl.appendChild(chipsBox);
    if (o.caption) root.appendChild(view), root.appendChild(cap); else root.appendChild(view);
    root.appendChild(ctl); host.appendChild(root);
    if (o.bg) root.style.setProperty('--pct-bg', o.bg);
    if (o.accent) { root.style.setProperty('--v3d-demo-accent', o.accent); root.style.setProperty('--v3d-demo-accent-soft', o.accent + '59'); }

    var noMatch = false, dead = false, viewer = null, demo = null, T = null, tx = function (k) { return (o.texts && o.texts[k]) || (T && T[k]) || FALLBACK[k] || ''; };
    var D = 0, steps = [], chips = {}, modelFile = 'stavebnice-demo.glb';

    function setPlayIcon(playing) {
      btnPlay.innerHTML = playing ? ICON.pause : ICON.play;
      var l = playing ? tx('pause') : tx('play'); btnPlay.setAttribute('aria-label', l); btnPlay.title = l;
    }
    function fail(msg) {
      root.classList.add('failed'); if (!cap.parentNode) root.insertBefore(cap, ctl); cap.classList.remove('empty'); cap.textContent = msg || tx('failed');
      if (global.console) global.console.warn('pripni-cokoli-tile:', msg);
    }
    setPlayIcon(true); btnRe.setAttribute('aria-label', FALLBACK.restart); btnRe.title = FALLBACK.restart;

    var ready = Promise.all([
      fetch(o.assetBase + 'texty.json' + ver).then(function (r) { if (!r.ok) throw new Error('texty ' + r.status); return r.json(); }),
      ensureDeps(o)
    ]).then(function (res) {
      if (dead) return null;
      var all = res[0], active = (Array.isArray(all._aktivni) ? all._aktivni : ['cs']).filter(function (l) { return all[l]; });
      var profs = all._profily || {}, variant = null;
      if (o.variant && profs[o.variant]) variant = o.variant;
      else if (o.profile != null && o.profile !== '') variant = resolveProfile(profs, o.profile);
      else variant = all._vychozi_profil || '40x40-d10';
      if (variant && profs[variant] && profs[variant].zive === false) variant = null;               // nesvalena varianta (zive:false, pravidlo 60): jako by animace pro profil nebyla
      if (!variant) { noMatch = true; dead = true; host.textContent = ''; return null; }       // profil bez animace: nic se nevykresli
      var lang = active.indexOf(o.lang) >= 0 ? o.lang : (active.indexOf('en') >= 0 && !o.lang ? 'en' : 'cs');
      T = all[lang] || all.cs; var Tcs = all.cs;
      var cuesTx = {}, vov = (all._varianty && all._varianty[variant]) ? (all._varianty[variant][lang] || all._varianty[variant].cs || {}) : {};
      Object.keys(Tcs.cues || {}).forEach(function (k) {
        cuesTx[k] = (o.texts && o.texts.cues && o.texts.cues[k] != null) ? o.texts.cues[k] : (vov[k] != null ? vov[k] : ((T.cues && T.cues[k] != null) ? T.cues[k] : Tcs.cues[k]));
      });
      modelFile = (profs[variant] && profs[variant].model) || 'stavebnice-demo.glb';
      btnRe.setAttribute('aria-label', tx('restart')); btnRe.title = tx('restart'); setPlayIcon(demo ? demo.isPlaying() : true);
      var reduced = false; try { reduced = global.matchMedia('(prefers-reduced-motion: reduce)').matches; } catch (e) { /* */ }
      var fill = bar.firstChild;
      demo = global.V3D.demoPlugin({
        texts: cuesTx, autoplay: o.autoplay !== false, speed: o.speed > 0 ? o.speed : 1, reducedMotion: reduced,
        onCue: function (cue, text) { cap.textContent = text || ''; cap.classList.toggle('empty', !text); },
        onTime: function (t, d) {
          D = d; if (d > 0) fill.style.width = (t / d * 100).toFixed(1) + '%';
          if (o.steps) steps.forEach(function (s) { if (chips[s.id]) chips[s.id].classList.toggle('on', t >= s.t0 && t < s.t1); });
        },
        onState: function (st) { setPlayIcon(st === 'play'); }
      });
      var vopts = {
        modelUrl: o.assetBase + modelFile + ver, mode: 'real', allowReal: true, hudKoty: false, dims: 0, aoVariant: 'vyp',
        labels: (o.texts && o.texts.viewer) || T.viewer || Tcs.viewer, plugins: [demo.plugin]
      };
      if (o.viewerOpts && typeof o.viewerOpts === 'object') Object.keys(o.viewerOpts).forEach(function (k) { if (k !== 'plugins' && k !== 'modelUrl') vopts[k] = o.viewerOpts[k]; });
      viewer = global.V3D.mount(view, vopts);
      return viewer.ready;
    }).then(function () {
      if (dead || noMatch || !demo) return;
      D = demo.duration(); steps = demo.steps();
      if (o.steps) {
        var n = 0;
        steps.forEach(function (s, i) {
          var lab = tx('step_' + s.id); if (lab === '') return;
          var b = el('button', 'pct-chip'); b.type = 'button'; b.textContent = (++n) + '  ' + (lab || ((tx('step') || '') + ' ' + (i + 1)));
          b.addEventListener('click', function () { demo.playStep(s.id, { stop: false }); });
          chipsBox.appendChild(b); chips[s.id] = b;
        });
      }
      setPlayIcon(demo.isPlaying());
    }).catch(function (err) { fail(err && err.message); });

    btnPlay.addEventListener('click', function () { if (!demo) return; demo.toggle(); setPlayIcon(demo.isPlaying()); });
    btnRe.addEventListener('click', function () { if (!demo) return; demo.restart(); setPlayIcon(true); });

    var api = {
      ready: ready,
      play: function () { if (demo) demo.play(); },
      pause: function () { if (demo) demo.pause(); },
      isPlaying: function () { return !!demo && demo.isPlaying(); },
      destroy: function () { dead = true; try { if (viewer && viewer.dispose) viewer.dispose(); } catch (e) { /* */ } host.textContent = ''; }
    };
    return ready.then(function () { return noMatch ? null : api; });
  }

  // supports(profile, {assetBase}) -> Promise<boolean>: ma tento profil animaci? (pro hostitele, ktery chce policko vubec ukazat)
  var regCache = {};
  function supports(profile, options) {
    var base = ((options && options.assetBase) || '/pripni-cokoli/').replace(/\/?$/, '/');
    regCache[base] = regCache[base] || fetch(base + 'texty.json').then(function (r) { return r.ok ? r.json() : {}; }).catch(function () { return {}; });
    return regCache[base].then(function (all) { var k = resolveProfile(all._profily, profile); return !!k && all._profily[k].zive !== false; });
  }

  global.PripniCokoliTile = { mount: mount, supports: supports };
})(typeof window !== 'undefined' ? window : this);
