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
      function hide() { hovered = null; panel.hidden = true; }
      function panelContent(light) {
        const t = texts(); panel.replaceChildren();
        panel.appendChild(element('strong', light.sku || light.id));
        panel.appendChild(element('div', t.hoverTitle, 'lux-panel-title'));
        panel.appendChild(element('small', t.scope));
        panel.appendChild(element('p', t.caveat, 'lux-note'));
        for (const row of core.assessActivities(result, data.activities)) {
          const block = element('div', '', 'lux-task');
          const label = element('a', (row.label[lang] || row.label.cs) + ' · ' + row.lux + ' lx');
          if (/^https:\/\//.test(row.source)) { label.href = row.source; label.target = '_blank'; label.rel = 'noopener noreferrer'; }
          block.appendChild(label);
          let status = row.luxReached ? t.reached : t.low;
          if (row.uniformityReached === false) status += ' · ' + t.uneven;
          if (row.uniformityReached === null) status += ' · ' + t.unknownUniformity;
          block.appendChild(element('small', status));
          block.appendChild(element('small', row.standard));
          panel.appendChild(block);
        }
        panel.hidden = false;
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
        hud.appendChild(element('small', t.minimum + ': ' + number(result.minLux) + ' lx · ' + t.uniformity + ': ' +
          (result.uniformity == null ? '—' : result.uniformity.toFixed(2))));
        hud.appendChild(element('small', t.edge + ': ' + number(result.edgeMinLux) + ' lx'));
        hud.appendChild(element('small', t.estimate + ' · ' + (result.basis === 'initial' ? t.initial : t.maintained)));
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
        labels.forEach(l => {
          const projected = l.p.clone().applyMatrix4(ctx.model.matrixWorld).project(ctx.camera);
          const visible = projected.z >= -1 && projected.z <= 1 && Math.abs(projected.x) <= 1 && Math.abs(projected.y) <= 1;
          l.node.hidden = !visible;
          l.node.style.left = ((projected.x + 1) * view.width / 2 + view.left - host.left) + 'px';
          l.node.style.top = ((1 - projected.y) * view.height / 2 + view.top - host.top) + 'px';
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
