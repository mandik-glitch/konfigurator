/*
 * Ovládací panel prostředí (HDRI) pro admina generátoru (bot10, 2026-10-04; Robert: "v generátoru stolů chci mít možnost měnit jako admin HDRi přímo v generátoru").
 * Přidává se k prohlížeči viewer3d.js (od 1.9.0: V3D.envLibrary, v.setEnvConfig/getEnvConfig/resetEnvConfig, opts.envConfig). Hostitel panel ukáže JEN adminovi.
 *
 *   var panel = V3D.envPicker(viewer, document.getElementById('hdriPanel'), {
 *     saved: cfgUlozenaNaServeru || null,                  // co je dnes uložené pro všechny (null = výchozí)
 *     onSave: function (cfg) { return fetch('/api/…', { method: 'PUT', body: JSON.stringify(cfg) }); }   // Promise (rozhodne o hlášce); cfg = null = vrátit výchozí
 *   });
 *   panel.getConfig(); panel.setConfig(cfg); panel.markSaved(cfg); panel.destroy();
 *
 * Ovládání: výběr HDRI (V3D.envLibrary + Místnost), síla světla 0,1-3, natočení -180..180°, světlo shora 0-1,2; změna je živá (jen náhled), uloží ji až tlačítko
 * "Uložit pro všechny". "Obnovit uložené" vrátí náhled na uloženou konfiguraci, "Výchozí" nastaví tovární (crossfit, síla 0,6) a k uložení je potřeba tlačítko.
 * Možnosti: labels (přepis textů: title, hdri, strength, rotation, hemi, save, revert, factory, saving, saved, failed, unsaved), onChange(cfg) po každé živé změně.
 * Bez závislostí, vlastní CSS (třída v3d-envp, barvy z proměnných stránky --text/--panel2/--border/--accent s náhradními hodnotami).
 */
(function (global) {
  'use strict';
  var V3D = global.V3D = global.V3D || {};
  var CSS_ID = 'v3d-envp-css';
  var CSS = [
    '.v3d-envp{display:flex;flex-direction:column;gap:8px;font:14px/1.35 -apple-system,"Segoe UI",Roboto,Arial,sans-serif;color:var(--text,inherit);padding:10px 12px;',
    'background:var(--panel2,rgba(128,128,128,.12));border:1px solid var(--border,rgba(128,128,128,.4));border-radius:8px}',
    '.v3d-envp h4{margin:0;font-size:14px;font-weight:700}',
    '.v3d-envp .row{display:grid;grid-template-columns:1fr auto;gap:2px 8px;align-items:center}',
    '.v3d-envp .row label{grid-column:1/2;font-size:13px;opacity:.9}.v3d-envp .row output{grid-column:2/3;font-variant-numeric:tabular-nums;font-size:13px;min-width:3.4em;text-align:right}',
    '.v3d-envp .row input[type=range]{grid-column:1/-1;width:100%;height:30px;margin:0;accent-color:var(--accent,#2fe07a)}',
    '.v3d-envp select{width:100%;min-height:38px;padding:4px 8px;font:inherit;color:inherit;background:var(--panel,rgba(255,255,255,.06));border:1px solid var(--border,rgba(128,128,128,.4));border-radius:6px}',
    '.v3d-envp .btns{display:flex;flex-wrap:wrap;gap:8px}',
    '.v3d-envp button{min-height:40px;padding:0 14px;font:600 13px -apple-system,"Segoe UI",Roboto,Arial,sans-serif;cursor:pointer;color:inherit;background:var(--panel,rgba(255,255,255,.06));border:1px solid var(--border,rgba(128,128,128,.4));border-radius:6px}',
    '.v3d-envp button.primary{background:var(--accent,#2fe07a);border-color:var(--accent,#2fe07a);color:#05140b}',
    '.v3d-envp button:disabled{opacity:.55;cursor:default}',
    '.v3d-envp .st{min-height:1.3em;font-size:13px;opacity:.95}.v3d-envp .st.err{color:#ff6b57}.v3d-envp .st.ok{color:var(--accent,#2fe07a)}'
  ].join('');
  var L0 = { title: 'Prostředí (HDRI) generátoru', hdri: 'HDRI', strength: 'Síla světla', rotation: 'Natočení', hemi: 'Světlo shora', save: 'Uložit pro všechny', revert: 'Obnovit uložené',
    factory: 'Výchozí', saving: 'Ukládám…', saved: 'Uloženo, uvidí to všichni návštěvníci generátoru.', failed: 'Uložení se nepovedlo', unsaved: 'Náhled, zatím neuloženo.' };
  var FACTORY = { hdri: 'crossfit', strength: 0.6, rot_deg: 0, hemi: 0 };

  function ensureCss() {
    try { if (document.getElementById(CSS_ID)) return; var s = document.createElement('style'); s.id = CSS_ID; s.textContent = CSS; document.head.appendChild(s); } catch (e) { /* bez stylu */ }
  }
  function same(a, b) { return !!a && !!b && a.hdri === b.hdri && Math.abs(a.strength - b.strength) < 1e-6 && Math.abs(a.rot_deg - b.rot_deg) < 1e-6 && Math.abs(a.hemi - b.hemi) < 1e-6; }

  V3D.envPicker = function (viewer, container, options) {
    var o = options || {}, L = {};
    Object.keys(L0).forEach(function (k) { L[k] = (o.labels && o.labels[k]) || L0[k]; });
    ensureCss();
    var norm = V3D.normalizeEnvConfig || function (c) { return c; };
    var saved = norm(o.saved) || null;                    // uloženo pro všechny (null = výchozí)
    var cur = norm(viewer.getEnvConfig ? viewer.getEnvConfig() : FACTORY) || FACTORY;
    var uid = 'envp' + Math.floor(Math.random() * 1e9);
    var root = document.createElement('div'); root.className = 'v3d-envp'; root.setAttribute('role', 'group'); root.setAttribute('aria-label', L.title);
    var lib = (V3D.envLibrary || [{ key: 'crossfit', label: 'Crossfit gym' }]);
    var optHtml = lib.map(function (h) { return '<option value="' + h.key + '">' + String(h.label).replace(/</g, '&lt;') + '</option>'; }).join('');
    root.innerHTML = '<h4>' + L.title + '</h4>' +
      '<div class="row"><label for="' + uid + 'h">' + L.hdri + '</label><select id="' + uid + 'h">' + optHtml + '</select></div>' +
      '<div class="row"><label for="' + uid + 's">' + L.strength + '</label><output id="' + uid + 'so"></output><input type="range" id="' + uid + 's" min="0.1" max="3" step="0.05"></div>' +
      '<div class="row"><label for="' + uid + 'r">' + L.rotation + '</label><output id="' + uid + 'ro"></output><input type="range" id="' + uid + 'r" min="-180" max="180" step="1"></div>' +
      '<div class="row"><label for="' + uid + 'e">' + L.hemi + '</label><output id="' + uid + 'eo"></output><input type="range" id="' + uid + 'e" min="0" max="1.2" step="0.05"></div>' +
      '<div class="btns"><button type="button" class="primary" data-a="save">' + L.save + '</button><button type="button" data-a="revert">' + L.revert + '</button><button type="button" data-a="factory">' + L.factory + '</button></div>' +
      '<div class="st" role="status"></div>';
    container.appendChild(root);
    var q = function (id) { return root.querySelector('#' + uid + id); };
    var elH = q('h'), elS = q('s'), elR = q('r'), elE = q('e'), oS = q('so'), oR = q('ro'), oE = q('eo'), st = root.querySelector('.st');
    var btnSave = root.querySelector('[data-a=save]'), btnRev = root.querySelector('[data-a=revert]'), btnFac = root.querySelector('[data-a=factory]');
    var timer = 0, busy = false, dead = false;

    function show(c) {
      elH.value = c.hdri; elS.value = String(c.strength); elR.value = String(c.rot_deg); elE.value = String(c.hemi);
      oS.textContent = c.strength.toFixed(2); oR.textContent = Math.round(c.rot_deg) + '°'; oE.textContent = c.hemi.toFixed(2);
    }
    function status(text, cls) { st.textContent = text || ''; st.className = 'st' + (cls ? ' ' + cls : ''); }
    function dirty() { return !same(cur, saved || FACTORY); }
    function readUi() { return { hdri: elH.value, strength: parseFloat(elS.value), rot_deg: parseFloat(elR.value), hemi: parseFloat(elE.value) }; }
    function applyLive(c) {
      var n = norm(c); if (!n) return;
      cur = n; show(n); if (viewer.setEnvConfig) viewer.setEnvConfig(n);
      if (typeof o.onChange === 'function') { try { o.onChange(n); } catch (e) { /* hostitel */ } }
      status(dirty() ? L.unsaved : '', '');
    }
    function onInput() {
      var c = norm(readUi()); if (!c) return;
      cur = c; show(c); status(dirty() ? L.unsaved : '', '');
      clearTimeout(timer); timer = setTimeout(function () { if (!dead) applyLive(cur); }, 120);     // živě, ale ne při každém pixelu (přepočet prostředí je dražší)
    }
    [elH, elS, elR, elE].forEach(function (e) { e.addEventListener('input', onInput); e.addEventListener('change', function () { clearTimeout(timer); cur = norm(readUi()) || cur; applyLive(cur); }); });
    btnFac.addEventListener('click', function () { applyLive(FACTORY); });
    btnRev.addEventListener('click', function () { applyLive(saved || FACTORY); });
    btnSave.addEventListener('click', function () {
      if (busy || typeof o.onSave !== 'function') return;
      busy = true; btnSave.disabled = true; status(L.saving, '');
      var toSave = same(cur, FACTORY) ? null : cur;           // výchozí se neukládá jako konfigurace, ale jako "nic" (hostitel smaže uloženou)
      var p; try { p = Promise.resolve(o.onSave(toSave)); } catch (e) { p = Promise.reject(e); }
      p.then(function (r) {
        if (r && typeof r === 'object' && typeof r.ok === 'boolean' && !r.ok) throw new Error('HTTP ' + r.status);
        saved = toSave; status(L.saved, 'ok');
      }, function (e) { status(L.failed + ': ' + ((e && e.message) || e), 'err'); })
        .then(function () { busy = false; btnSave.disabled = false; });
    });
    show(cur); status('', '');
    return {
      el: root,
      getConfig: function () { return { hdri: cur.hdri, strength: cur.strength, rot_deg: cur.rot_deg, hemi: cur.hemi }; },
      setConfig: function (c) { applyLive(c); },
      markSaved: function (c) { saved = norm(c) || null; status(dirty() ? L.unsaved : '', ''); },
      destroy: function () { dead = true; clearTimeout(timer); if (root.parentNode) root.parentNode.removeChild(root); }
    };
  };
})(typeof window !== 'undefined' ? window : this);
