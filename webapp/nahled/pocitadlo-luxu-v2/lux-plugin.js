/* Plugin se stejným životním cyklem jako V3D.demoPlugin. Žádná síť ani zápis.
 * Závislosti dodá hostitel: LuxCore, LuxData, THREE v ctx; styly lux.css. */
(function (root) {
  'use strict';
  const V3D = root.V3D = root.V3D || {};
  V3D.luxPlugin = function (options = {}) {
    const core = options.core || root.LuxCore;
    const data = options.data || root.LuxData;
    if (!core || !data) throw new Error('Chybí LuxCore nebo LuxData');
    let state = options.input || null, lang = options.lang || 'cs', active = null;
    const texts = () => data.texts[lang] || data.texts.cs;
    const listeners = new Set();
    function recalculate() {
      if (active) active.update();
    }
    function plugin(ctx) {
      const doc = ctx.root.ownerDocument || root.document;
      const THREE = ctx.THREE;
      const canvas = ctx.renderer.domElement;
      let result = null, disposed = false, hovered = null, labels = [], pointer = null;
      const overlay = doc.createElement('div'); overlay.className = 'lux-overlay';
      const hud = doc.createElement('div'); hud.className = 'lux-hud'; hud.setAttribute('aria-live', 'polite');
      const panel = doc.createElement('div'); panel.className = 'lux-hover'; panel.hidden = true; panel.setAttribute('role', 'dialog');
      overlay.appendChild(hud); overlay.appendChild(panel); ctx.root.appendChild(overlay);
      const raycaster = new THREE.Raycaster(), cursor = new THREE.Vector2();
      function element(tag, content, className) {
        const e = doc.createElement(tag); e.textContent = content;
        if (className) e.className = className;
        return e;
      }
      function hide() { hovered = null; panel.hidden = true; hud.hidden = false; project(); }
      function link(label, url) {
        const a = element('a', label);
        if (/^https:\/\//.test(url || '')) { a.href = url; a.target = '_blank'; a.rel = 'noopener noreferrer'; }
        return a;
      }
      function details(parent, title, className) {
        const block = element('details', '', className || 'lux-details');
        block.appendChild(element('summary', title)); parent.appendChild(block); return block;
      }
      function norms(parent) {
        const t = texts(), sources = data.normSources;
        const block = details(parent, t.norms, 'lux-norms');
        block.appendChild(element('p', t.normBasis));
        for (const key of ['standard','law']) {
          const s = sources[key]; block.appendChild(link(s.id + ' – ' + s.title[lang], s.url));
        }
        for (const key of ['physics','excerpt','asr']) block.appendChild(link(sources[key].id, sources[key].url));
        block.appendChild(element('p', t.lawBasis));
        block.appendChild(element('p', t.maintainedBasis));
        return block;
      }
      function metrics(parent) {
        const t = texts(), values = element('div', '', 'lux-metrics');
        for (const [title, value] of [[t.minimum, number(result.minLux) + ' lx'],
          [t.mean, number(result.meanLux) + ' lx'],
          [t.uniformity, result.uniformity == null ? '—' : result.uniformity.toFixed(2)]]) {
          const cell = element('div', ''); cell.appendChild(element('small', title)); cell.appendChild(element('strong', value)); values.appendChild(cell);
        }
        parent.appendChild(values);
      }
      function panelContent(light) {
        const t = texts(); panel.replaceChildren();
        const close = element('button', '×', 'lux-close'); close.type = 'button'; close.setAttribute('aria-label', t.close);
        close.addEventListener('click', hide); panel.appendChild(close);
        panel.appendChild(element('strong', light.modelName ? light.manufacturer + ' ' + light.modelName : light.sku || light.id));
        panel.appendChild(element('div', light.powerW == null ? light.luminousFluxLm + ' lm' : light.powerW + ' W · ' + light.luminousFluxLm + ' lm', 'lux-light-setting'));
        const compactSpecs = [];
        if (light.cctK != null) compactSpecs.push(light.cctK + ' K');
        if (light.criRa != null) compactSpecs.push(typeof light.criRa === 'number' ? 'Ra ' + light.criRa : 'Ra ' + light.criRa.operator + ' ' + light.criRa.min);
        if (light.beamAngleDeg != null) compactSpecs.push(light.beamAngleDeg + '°');
        if (compactSpecs.length) panel.appendChild(element('small', compactSpecs.join(' · ')));
        panel.appendChild(element('div', t.resultTitle, 'lux-panel-title'));
        metrics(panel); panel.appendChild(element('small', t.scope));
        panel.appendChild(element('small', t.estimate + ' · ' + (result.basis === 'initial' ? t.initial : t.maintained)));
        panel.appendChild(element('small', t.normsShort, 'lux-norms-caption')); norms(panel);
        panel.appendChild(element('div', t.tasksShort, 'lux-panel-title'));
        panel.appendChild(element('small', t.checkLegend));
        const rows = core.assessActivities(result, data.activities, state.lights);
        // ✓ je jen číselné porovnání průměru a U₀. Shoda pracoviště se neuděluje.
        const numerical = row => row.luxReached && row.uniformityReached === true;
        const eligible = rows.filter(row => numerical(row) && row.raReached === true);
        const highest = eligible.length ? Math.max(...eligible.map(row => row.lux)) : null;
        if (highest == null) panel.appendChild(element('small', t.noneReached));
        const more = details(panel, t.moreTasks);
        function activity(row, parent) {
          const best = highest != null && row.lux === highest && numerical(row) && row.raReached === true;
          const block = element('div', '', 'lux-task' + (best ? ' lux-best-task' : ''));
          block.setAttribute('data-activity', row.id);
          block.appendChild(element('div', (numerical(row) ? '✓ ' : '✗ ') + (row.label[lang] || row.label.cs) + ' · ' + row.lux + ' lx'));
          block.appendChild(element('small', 'CZ-ISCO ' + row.occupations.map(o => o.code).join(', ') +
            (row.evidence === 'primary_DE_rule' ? ' · ' + t.deReference : '')));
          if (best) block.appendChild(element('small', t.highest));
          if (row.uniformityReached === false && row.luxReached) block.appendChild(element('small', t.uneven));
          if (row.uniformityReached === null) block.appendChild(element('small', t.unknownUniformity));
          if (row.raReached !== true && row.ra != null) block.appendChild(element('small', t.raUnproven + ' (Ra ≥ ' + row.ra + ')'));
          parent.appendChild(block);
        }
        // Krátký výběr zůstává nahoře; původní obory zachovány v rozbalení.
        rows.filter(r => r.summary).forEach(row => activity(row, panel));
        rows.filter(r => !r.summary).forEach(row => activity(row, more));
        // Rozbalovací řádek pro další obory patří až za hlavní seznam.
        more.remove(); panel.appendChild(more);
        const requirements = details(panel, t.taskDetails);
        requirements.appendChild(element('small', t.mappingNote));
        requirements.appendChild(link(data.normSources.isco.id, data.normSources.isco.url));
        for (const row of rows) {
          const block = element('div', '', 'lux-task');
          block.appendChild(link((row.label[lang] || row.label.cs) + ' · ' + row.lux + ' lx', row.source));
          block.appendChild(element('small', row.standard + ' · U₀ ≥ ' + (row.uniformity == null ? '—' : row.uniformity) +
            ' · Ra ≥ ' + (row.ra == null ? '—' : row.ra)));
          if (row.ugr != null) block.appendChild(link('UGR ≤ ' + row.ugr + ' · ' + t.glare, row.glareSource || row.source));
          for (const o of row.occupations) block.appendChild(element('small', 'CZ-ISCO ' + o.code + ' · ' + o.label[lang]));
          block.appendChild(element('small', row.ra == null ? t.raUnknown : row.raReached ? t.raSupported : t.raUnproven));
          requirements.appendChild(block);
        }
        panel.appendChild(element('p', t.shortCaveat, 'lux-note'));
        panel.appendChild(element('small', t.workplane + ': ' + number(state.workplane.originMm[1]) + ' mm · ' + t.edge + ': ' + number(result.edgeMinLux) + ' lx'));
        const technical = details(panel, t.technicalMore);
        const specifications = element('dl', '', 'lux-specifications');
        function specification(label, value) {
          if (value == null) return;
          specifications.appendChild(element('dt', label)); specifications.appendChild(element('dd', value));
        }
        specification(t.activeMode, light.powerW == null ? light.luminousFluxLm + ' lm' : light.powerW + ' W · ' + light.luminousFluxLm + ' lm');
        if (light.powerModes) specification(t.modes, light.powerModes.map(m => m.powerW + ' W / ' + m.luminousFluxLm + ' lm').join(' · '));
        specification(t.beam, light.beamAngleDeg == null ? null : light.beamAngleDeg + '°');
        specification(t.cct, light.cctK == null ? null : light.cctK + ' K');
        specification(t.cri, light.criRa == null ? null : typeof light.criRa === 'number' ? 'Ra ' + light.criRa : 'Ra ' + light.criRa.operator + ' ' + light.criRa.min);
        specification(t.protection, light.ip ? light.ip + ' / ' + light.ik : null);
        specification(t.environment, light.indoorOnly === true ? t.indoor : null);
        specification(t.protectionClass, light.protectionClass);
        specification(t.lifetime, light.lifetime ? number(light.lifetime.hours) + ' h @ ' + light.lifetime.lumenMaintenance : null);
        specification(t.temperature, light.operatingTemperatureC ? light.operatingTemperatureC.join(' … +') + ' °C' : null);
        specification(t.dimensions, light.labelledDimensionsMm ? light.labelledDimensionsMm.join(' × ') + ' mm' : null);
        specification(t.electrical, light.voltageV ? light.voltageV.join('–') + ' V~ · ' + light.frequencyHz.join('/') + ' Hz' : null);
        if (light.labelCode) specification('EAN · ' + light.labelCode, light.ean);
        specification('SKU', light.sku);
        technical.appendChild(specifications);
        if (light.dimmable === false) technical.appendChild(element('small', t.nonDimmable));
        if (light.labelledDimensionsMm && light.labelledDimensionsMm[0] !== light.housingLengthMm) technical.appendChild(element('p', t.dimensionConflict, 'lux-note'));
        if (light.cctK === 4000) technical.appendChild(element('p', t.colourRelevance, 'lux-note'));
        if (light.criRa) technical.appendChild(element('small', t.criScope));
        if (light.sources && /^https:\/\//.test(light.sources.manufacturer)) {
          const source = element('a', t.manufacturerSource); source.href = light.sources.manufacturer;
          source.target = '_blank'; source.rel = 'noopener noreferrer'; technical.appendChild(source);
        }
        panel.hidden = false;
        hud.hidden = true; project();
      }
      function number(value) { return Number.isFinite(value) ? Math.round(value).toLocaleString(lang) : '—'; }
      function update() {
        if (disposed) return;
        hide();
        labels.forEach(l => l.node.remove()); labels = []; hud.replaceChildren(); result = null;
        const t = texts();
        hud.appendChild(element('strong', t.title));
        if (!state) { hud.appendChild(element('p', t.missing)); return; }
        try { result = core.calculate(state, {...options.calculation, allowEstimate: options.allowEstimate === true}); }
        catch (e) {
          hud.appendChild(element('p', t.missing));
          if (typeof options.onError === 'function') options.onError(e);
          return;
        }
        hud.appendChild(element('span', t.mean + ': ≈ ' + number(result.meanLux) + ' lx', 'lux-main-number'));
        hud.appendChild(element('small', t.minimum + ': ' + number(result.minLux) + ' lx'));
        hud.appendChild(element('small', t.uniformity + ': ' + (result.uniformity == null ? '—' : result.uniformity.toFixed(2))));
        hud.appendChild(element('small', t.edge + ': ' + number(result.edgeMinLux) + ' lx'));
        hud.appendChild(element('small', t.estimate + ' · ' + (result.basis === 'initial' ? t.initial : t.maintained)));
        hud.appendChild(element('small', t.normsShort, 'lux-norms-caption')); norms(hud);
        if (!state.lights.length) hud.appendChild(element('small', t.empty));
        // Výběr pěti míst; při dlouhém stole skutečně různé hodnoty nad deskou.
        const row = result.probes.filter(p => p.vMm === state.workplane.depthMm / 2);
        row.forEach(p => {
          const node = element('div', '≈ ' + number(p.lux) + ' lx', 'lux-point'); overlay.appendChild(node);
          labels.push({node, p: new THREE.Vector3(...p.positionMm)});
        });
        for (const fn of listeners) fn(result);
        project(); ctx.requestRender();
      }
      function project() {
        if (disposed) return;
        const view = canvas.getBoundingClientRect(), host = ctx.root.getBoundingClientRect();
        ctx.model.updateMatrixWorld(true); ctx.camera.updateMatrixWorld(true);
        const occupied = [];
        if (hud.offsetWidth && hud.offsetHeight && !hud.hidden) {
          const r = hud.getBoundingClientRect(); occupied.push({left:r.left-host.left, top:r.top-host.top, right:r.right-host.left, bottom:r.bottom-host.top});
        }
        // Přednost má střed, pak konce. V těsném záběru méně cifer zůstane čitelných.
        const priority = [2,0,4,1,3].map(i => labels[i]).filter(Boolean);
        priority.forEach(l => {
          const projected = l.p.clone().applyMatrix4(ctx.model.matrixWorld).project(ctx.camera);
          const visible = projected.z >= -1 && projected.z <= 1 && Math.abs(projected.x) <= 1 && Math.abs(projected.y) <= 1;
          const x = (projected.x + 1) * view.width / 2 + view.left - host.left;
          const y = (1 - projected.y) * view.height / 2 + view.top - host.top;
          l.node.style.left = x + 'px'; l.node.style.top = y + 'px';
          // Skrytý uzel nejdřív zpřístupníme kvůli měření skutečné šířky textu.
          l.node.hidden = false;
          const w = l.node.offsetWidth || 76, h = l.node.offsetHeight || 28;
          const r = {left:x-w/2-3, right:x+w/2+3, top:y-h/2-3, bottom:y+h/2+3};
          const fits = r.left >= 0 && r.right <= host.width && r.top >= 0 && r.bottom <= host.height;
          const collides = occupied.some(o => r.left < o.right && r.right > o.left && r.top < o.bottom && r.bottom > o.top);
          l.node.hidden = !visible || !fits || collides || !panel.hidden;
          if (!l.node.hidden) occupied.push(r);
        });
      }
      function hitLight(event) {
        if (!result || !state || !state.lights.length) return null;
        const rect = canvas.getBoundingClientRect();
        if (!rect.width || !rect.height) return null;
        cursor.set((event.clientX - rect.left) / rect.width * 2 - 1, 1 - (event.clientY - rect.top) / rect.height * 2);
        ctx.model.updateMatrixWorld(true); ctx.camera.updateMatrixWorld(true);
        raycaster.setFromCamera(cursor, ctx.camera);
        const meshes = []; ctx.model.traverse(o => {
          if (!o.isMesh || o.userData.__v3dHelper) return;
          for (let parent = o; parent; parent = parent.parent) if (!parent.visible) return;
          meshes.push(o);
        });
        const hit = raycaster.intersectObjects(meshes, false)[0];
        if (!hit) return null;
        const point = ctx.model.worldToLocal(hit.point.clone());
        return state.lights.find(l => l.housingBoundsMm && new THREE.Box3(
          new THREE.Vector3(...l.housingBoundsMm[0]), new THREE.Vector3(...l.housingBoundsMm[1])).expandByScalar(0.5).containsPoint(point)) || null;
      }
      function showFor(event) {
        const light = hitLight(event);
        if (!light) { hide(); return; }
        if (hovered !== light.id) { hovered = light.id; panelContent(light); }
      }
      function move(e) { if ((!e.pointerType || e.pointerType === 'mouse') && !e.buttons) showFor(e); }
      function leave(e) { if (!e.relatedTarget || !panel.contains(e.relatedTarget)) hide(); }
      function down(e) { pointer = {x: e.clientX, y: e.clientY, id: e.pointerId}; hide(); }
      function up(e) {
        if (pointer && pointer.id === e.pointerId && e.pointerType !== 'mouse' && Math.hypot(e.clientX - pointer.x, e.clientY - pointer.y) < 8) showFor(e);
        pointer = null;
      }
      function escape(e) { if (e.key === 'Escape') hide(); }
      canvas.addEventListener('pointermove', move); canvas.addEventListener('pointerleave', leave);
      canvas.addEventListener('pointerdown', down); canvas.addEventListener('pointerup', up);
      panel.addEventListener('pointerleave', hide); doc.addEventListener('keydown', escape);
      ctx.controls.addEventListener('change', project);
      const observer = typeof root.ResizeObserver === 'function' ? new root.ResizeObserver(project) : null;
      if (observer) observer.observe(ctx.root);
      // onFrame neběží v klidném vieweru; změny kamery a rozměrů hlídáme zvlášť.
      const offFrame = ctx.onFrame(project);
      const live = {update, result: () => result}; active = live; update();
      return function dispose() {
        if (disposed) return;
        disposed = true; offFrame(); if (observer) observer.disconnect();
        canvas.removeEventListener('pointermove', move); canvas.removeEventListener('pointerleave', leave);
        canvas.removeEventListener('pointerdown', down); canvas.removeEventListener('pointerup', up);
        panel.removeEventListener('pointerleave', hide); doc.removeEventListener('keydown', escape);
        ctx.controls.removeEventListener('change', project); overlay.remove();
        if (active === live) active = null;
      };
    }
    return {plugin, setInput(input) {state = input; recalculate();}, setLanguage(value) {lang = data.texts[value] ? value : 'cs'; recalculate();},
      result() {return active ? active.result() : null;}, onResult(fn) {listeners.add(fn); return () => listeners.delete(fn);}};
  };
})(typeof globalThis !== 'undefined' ? globalThis : this);
