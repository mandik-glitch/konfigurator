/*
 * Stránka "Připni cokoli" (webapp/pripni-cokoli.html): samopohyblivá 3D ukázka stavebnice z hliníkových profilů (bot10, 2026-10-03).
 * Používá sdílený prohlížeč js/v3d/viewer3d.js + plugin js/v3d/demo-stavebnice.js; model pripni-cokoli/stavebnice-demo.glb.
 * Ovládání: tlačítka kroků skočí na začátek kroku a animace jede dál; klepnutí/tažení za model animaci nezastaví ani neposune.
 * Náhled návrhu externího bota (pravidlo 60): nahled=<id> (např. v3) = model z pripni-cokoli/nahled/<id>/ místo živého, s upozorněním; živá stránka se nemění.
 *   Volitelný soubor pripni-cokoli/nahled/<id>/texty.json (stejný tvar jako texty.json, jen jazyky cs/en/sk/de/pl) přidá/přepíše texty (např. popisky nových kroků návrhu); jen v náhledu, živý registr se nemění.
 * Parametry URL: profil=30 (varianta 30×30, drážka 8 mm; výchozí 40×40), lang=cs|en|sk|de|pl (výchozí podle prohlížeče), embed=1 (jen ukázka, bez nadpisu a patičky), bg=rrggbb (barva pozadí),
 *   autoplay=0, t=<s> (začátek), speed=<0.25-4>, ao=vyp|jemne|stredni|silne, model=<cesta pod /pripni-cokoli/> (jen pro zkoušení).
 * Texty: pripni-cokoli/texty.json (cs je zdroj, ostatní k revizi bot7). Nic se neukládá, žádné cookies, žádné externí požadavky mimo skripty three.
 */
(function () {
  'use strict';
  var LANGS = ['cs', 'en', 'sk', 'de', 'pl'];
  var CDN = 'https://cdn.jsdelivr.net/npm/three@0.128.0/';
  var DEPS = ['build/three.min.js', 'examples/js/controls/OrbitControls.js', 'examples/js/loaders/GLTFLoader.js', 'examples/js/environments/RoomEnvironment.js',
    'examples/js/renderers/CSS2DRenderer.js', 'examples/js/shaders/HorizontalBlurShader.js', 'examples/js/shaders/VerticalBlurShader.js'];
  var ASSET = '/pripni-cokoli/';
  var q = new URLSearchParams(location.search);
  function $(id) { return document.getElementById(id); }

  var LANG_NAMES = { cs: 'Čeština', en: 'English', sk: 'Slovenčina', de: 'Deutsch', pl: 'Polski' };
  // jazyky povolene v texty.json (_aktivni): neoverene preklady (DE, PL) se nezverejnuji, dokud je bot7 neschvali
  function pickLang(active) {
    var p = (q.get('lang') || '').toLowerCase();
    if (active.indexOf(p) >= 0) return p;
    var nav = ((navigator.languages && navigator.languages[0]) || navigator.language || 'cs').slice(0, 2).toLowerCase();
    return active.indexOf(nav) >= 0 ? nav : 'cs';
  }
  // rozpoznani profilu generatoru (stejne pravidlo je v prvku pripni-cokoli-tile.js): "30x30", "30", "30 x 30", "Object_7", SKU, produkt, "Stul system 30 SP002"
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
  function loadScript(url) {
    return new Promise(function (res, rej) {
      var s = document.createElement('script'); s.src = url; s.onload = res; s.onerror = function () { rej(new Error('nenacteno ' + url)); };
      document.head.appendChild(s);
    });
  }
  function setMeta(sel, attr, val) { var e = document.querySelector(sel); if (e) e.setAttribute(attr, val); }
  // texty z nahled/<id>/texty.json (jen v nahledu): retezce se prepisuji po klicich, cues a viewer o uroven hloub; cokoli jineho (neretezce, _profily, _varianty) se ignoruje
  function mergeNahledTexty(all, ex) {
    if (!ex || typeof ex !== 'object') return all;
    LANGS.forEach(function (l) {
      var e = ex[l]; if (!e || typeof e !== 'object' || !all[l]) return;
      Object.keys(e).forEach(function (k) {
        if ((k === 'cues' || k === 'viewer') && e[k] && typeof e[k] === 'object') {
          if (!all[l][k]) all[l][k] = {};
          Object.keys(e[k]).forEach(function (kk) { if (typeof e[k][kk] === 'string') all[l][k][kk] = e[k][kk]; });
        } else if (typeof e[k] === 'string') all[l][k] = e[k];
      });
    });
    return all;
  }
  var ICON = {
    play: '<svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true"><path d="M8 5v14l11-7z" fill="currentColor"/></svg>',
    pause: '<svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true"><path d="M7 5h4v14H7zM13 5h4v14h-4z" fill="currentColor"/></svg>',
    restart: '<svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true"><path d="M12 5V2L7 6.5 12 11V8a6 6 0 1 1-6 6H4a8 8 0 1 0 8-9z" fill="currentColor"/></svg>'
  };

  function start() {
    var embed = q.get('embed') === '1';
    if (embed) document.body.classList.add('embed');
    var bg = q.get('bg');
    if (bg && /^[0-9a-fA-F]{6}$/.test(bg)) document.documentElement.style.setProperty('--pc-bg', '#' + bg);

    var nahledId = (q.get('nahled') || '').toLowerCase(); if (!/^[a-z0-9][a-z0-9_-]{0,23}$/.test(nahledId)) nahledId = '';
    var nahledTexty = nahledId ? fetch(ASSET + 'nahled/' + nahledId + '/texty.json?t=' + Date.now()).then(function (r) { return r.ok ? r.json() : null; }).catch(function () { return null; }) : Promise.resolve(null);
    fetch(ASSET + 'texty.json?v=' + (window.PC_V || '1')).then(function (r) { if (!r.ok) throw new Error('texty ' + r.status); return r.json(); })
      .then(function (all) { return nahledTexty.then(function (ex) { return mergeNahledTexty(all, ex); }); })
      .then(function (all) {
      var active = (Array.isArray(all._aktivni) ? all._aktivni : LANGS).filter(function (l) { return all[l] && LANGS.indexOf(l) >= 0; });
      if (active.indexOf('cs') < 0) active.unshift('cs');
      var lang = pickLang(active);
      document.documentElement.lang = lang;
      var T = all[lang] || all.cs;
      var Tcs = all.cs;
      function tx(k) { return (T[k] != null ? T[k] : Tcs[k]); }
      document.title = tx('title');
      setMeta('meta[name="description"]', 'content', tx('description'));
      setMeta('meta[property="og:title"]', 'content', tx('title'));
      setMeta('meta[property="og:description"]', 'content', tx('description'));
      $('pcH1').textContent = tx('h1'); $('pcLead').textContent = tx('lead');
      $('pcPlay').setAttribute('aria-label', tx('pause')); $('pcPlay').title = tx('pause'); $('pcPlay').innerHTML = ICON.pause;
      $('pcRestart').setAttribute('aria-label', tx('restart')); $('pcRestart').title = tx('restart'); $('pcRestart').innerHTML = ICON.restart;
      $('pcScrub').setAttribute('aria-label', tx('scrub'));
      $('pcViewer').setAttribute('aria-label', tx('stage'));
      var cta = $('pcCta'); if (cta) cta.textContent = tx('cta');
      [['pcOtherH', 'other_title'], ['pcOtherLead', 'other_lead'], ['pcF40t', 'other_40_title'], ['pcF40n', 'other_40_note'], ['pcF30t', 'other_30_title'], ['pcF30n', 'other_30_note']].forEach(function (a) { var e = $(a[0]); if (e && tx(a[1])) e.textContent = tx(a[1]); });
      [['pcImg40', 'other_alt_40'], ['pcImg30', 'other_alt_30']].forEach(function (a) { var e = $(a[0]); if (e && tx(a[1])) e.setAttribute('alt', tx(a[1])); });
      var sel = $('pcLang');
      if (sel) { sel.textContent = ''; active.forEach(function (l) { var o = document.createElement('option'); o.value = l; o.textContent = LANG_NAMES[l] || l; sel.appendChild(o); }); sel.hidden = active.length < 2; sel.value = lang; sel.setAttribute('aria-label', 'Language'); sel.addEventListener('change', function () { var u = new URL(location.href); u.searchParams.set('lang', sel.value); location.href = u.toString(); }); }

      var cuesTx = {};
      Object.keys(Tcs.cues || {}).forEach(function (k) { cuesTx[k] = (T.cues && T.cues[k] != null) ? T.cues[k] : Tcs.cues[k]; });
      // varianta profilu podle registru texty.json (_profily): ?profil=30 | 30x30 | Object_7 | SKU ...; bez parametru nebo neznamy = vychozi (40x40)
      var profs = all._profily || {}, variant = resolveProfile(profs, q.get('profil')) || all._vychozi_profil || '40x40-d10';
      var vov = (all._varianty && all._varianty[variant]) ? (all._varianty[variant][lang] || all._varianty[variant].cs || {}) : {};
      Object.keys(vov).forEach(function (k) { cuesTx[k] = vov[k]; });
      var modelParam = q.get('model');
      // NAHLED (pravidlo 60 ve WORKFLOW.md: praci externiho bota Johna musi nejdriv videt Robert): ?nahled=v3 nacte model z nahled/<id>/ misto zive verze, nemeni zivou stranku
      var nahled = (q.get('nahled') || '').toLowerCase(); if (!/^[a-z0-9][a-z0-9_-]{0,23}$/.test(nahled)) nahled = '';
      var modelFile = (profs[variant] && profs[variant].model) || 'stavebnice-demo.glb';
      var model = ASSET + (nahled ? 'nahled/' + nahled + '/' : '') + modelFile + (nahled ? '?t=' + Date.now() : '?v=' + (window.PC_V || '1'));
      if (nahled) {
        var bn = document.createElement('div'); bn.className = 'pc-preview'; bn.setAttribute('role', 'note');
        bn.textContent = 'NÁHLED ' + nahled + ' – návrh externího bota Johna, čeká na schválení Robertem. Není to živá verze.';
        var pcRoot = document.querySelector('.pc'); if (pcRoot) pcRoot.insertBefore(bn, pcRoot.firstChild);
        document.title = 'NÁHLED ' + nahled + ' | ' + document.title;
      }
      if (modelParam && /^[A-Za-z0-9_.-]{1,60}\.glb$/.test(modelParam)) model = ASSET + modelParam + '?t=' + Date.now();   // jen soubor v /pripni-cokoli/
      var reduced = false; try { reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches; } catch (e) { /* */ }
      var fine = false; try { fine = window.matchMedia('(pointer:fine)').matches; } catch (e) { /* */ }
      var ao = q.get('ao'); if (['vyp', 'jemne', 'stredni', 'silne'].indexOf(ao) < 0) ao = (fine && window.innerWidth >= 900) ? 'jemne' : 'vyp';
      var speed = parseFloat(q.get('speed')); if (!(speed >= 0.25 && speed <= 4)) speed = 1;

      var D = 0, steps = [], chips = {}, scrubbing = false, demo = null;
      var capEl = $('pcCap'), scrub = $('pcScrub'), playBtn = $('pcPlay');
      // varianta, ktera jeste neni schvalena (_profily[..].zive === false): na zive strance se pro profil nic neukaze, jen v nahledu (?nahled=<id>)
      if (variant && profs[variant] && profs[variant].zive === false && !nahled) {
        document.body.classList.add('failed'); capEl.classList.remove('empty'); capEl.textContent = tx('soon') || 'Animace pro tento profil se připravuje.';
        return;
      }
      function setPlayIcon(playing) { playBtn.innerHTML = playing ? ICON.pause : ICON.play; var l = playing ? tx('pause') : tx('play'); playBtn.setAttribute('aria-label', l); playBtn.title = l; playBtn.setAttribute('aria-pressed', playing ? 'false' : 'true'); }
      function activeStepAt(t) { var a = null; steps.forEach(function (s) { if (t >= s.t0 && t < s.t1) a = s; }); return a; }
      function markChips(t) {
        var a = activeStepAt(t); var id = a && a.id;
        Object.keys(chips).forEach(function (k) { var on = k === id; chips[k].classList.toggle('on', on); chips[k].setAttribute('aria-current', on ? 'step' : 'false'); });
      }
      demo = window.V3D.demoPlugin({
        texts: cuesTx, autoplay: q.get('autoplay') !== '0', speed: speed, startTime: parseFloat(q.get('t')) || 0, reducedMotion: reduced,
        onCue: function (cue, text) { capEl.textContent = text || ''; capEl.classList.toggle('empty', !text); },
        onTime: function (t, d) { D = d; if (!scrubbing && d > 0) scrub.value = String(Math.round(t / d * 1000)); markChips(t); },
        onState: function (st) { setPlayIcon(st === 'play'); }
      });
      var v = window.V3D.mount($('pcViewer'), {
        modelUrl: model, mode: 'real', allowReal: true, hudKoty: false, dims: 0, aoVariant: ao, labels: T.viewer || Tcs.viewer,
        plugins: [demo.plugin]
        // klepnuti na dil zamerne NIC nedela (robert 2026-10-03: pri otaceni modelu se animace zastavovala/skakala); kroky jen tlacitky a posuvnikem
      });
      v.ready.then(function () {
        D = demo.duration(); steps = demo.steps();
        var box = $('pcSteps'); box.textContent = '';
        var shown = 0;
        steps.forEach(function (s, i) {
          var lab = tx('step_' + s.id);
          if (lab === '') return;                        // krok s prazdnym popiskem (napr. zaverecne rozpusteni) tlacitko nema
          var b = document.createElement('button'); b.type = 'button'; b.className = 'chip';
          b.textContent = (++shown) + '  ' + (lab || ((tx('step') || '') + ' ' + (i + 1)));
          b.addEventListener('click', function () { scrubbing = false; demo.playStep(s.id, { stop: false }); });
          box.appendChild(b); chips[s.id] = b;
        });
        setPlayIcon(demo.isPlaying());
        scrub.disabled = !(D > 0); markChips(demo.time());
        document.body.classList.add('ready');
      }, function (err) { fail(err); });
      playBtn.addEventListener('click', function () { scrubbing = false; demo.toggle(); setPlayIcon(demo.isPlaying()); });
      $('pcRestart').addEventListener('click', function () { scrubbing = false; demo.restart(); setPlayIcon(true); });
      var scrubTimer = 0;
      function scrubDone() { scrubbing = false; clearTimeout(scrubTimer); }
      scrub.addEventListener('pointerdown', function () { scrubbing = true; });
      scrub.addEventListener('input', function () {
        scrubbing = true; clearTimeout(scrubTimer); scrubTimer = setTimeout(scrubDone, 700);   // pojistka: posuvnik se po ukonceni tahu vrati k prehravani
        demo.pause(); setPlayIcon(false); demo.seek(parseInt(scrub.value, 10) / 1000 * (D || demo.duration()));
      });
      ['pointerup', 'pointercancel', 'change', 'blur'].forEach(function (ev) { scrub.addEventListener(ev, function () { clearTimeout(scrubTimer); scrubTimer = setTimeout(scrubDone, 150); }); });
      function fail(err) {
        document.body.classList.add('failed');
        capEl.classList.remove('empty'); capEl.textContent = (window.WebGLRenderingContext ? tx('viewer').load_failed || '' : tx('nowebgl')) || String(err && err.message || err);
        if (window.console) console.warn('pripni-cokoli:', err);
      }
    }).catch(function (err) {
      document.body.classList.add('failed'); var c = $('pcCap'); if (c) { c.classList.remove('empty'); c.textContent = '3D: ' + (err && err.message || err); }
    });
  }

  var chain = Promise.resolve();
  DEPS.forEach(function (u) { chain = chain.then(function () { return loadScript(CDN + u); }); });
  chain = chain.then(function () { return loadScript('/js/v3d/viewer3d.js?v=' + (window.PC_VIEWER_V || '1')); })
    .then(function () { return loadScript('/js/v3d/demo-stavebnice.js?v=' + (window.PC_PLUGIN_V || '1')); })
    .then(start, function (err) { document.body.classList.add('failed'); var c = $('pcCap'); if (c) { c.classList.remove('empty'); c.textContent = String(err && err.message || err); } });
})();
