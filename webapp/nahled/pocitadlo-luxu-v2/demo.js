/* Samostatný geometrický náhled desky a světel; všechny výpočty dělá plugin.
 * THREE je lokální kopie existující knihovny; stránka nic nestahuje. */
(function () {
  'use strict';
  const fixture = globalThis.LuxGeometryFixture;
  const root = document.getElementById('preview'), canvas = document.getElementById('scene');
  const controlsForm = document.getElementById('controls'), error = document.getElementById('error');
  const scene = new THREE.Scene(), model = new THREE.Group(); scene.add(model);
  const camera = new THREE.PerspectiveCamera(42, 1, 1, 50000);
  let renderer;
  try { renderer = new THREE.WebGLRenderer({canvas, antialias: true, alpha: true}); }
  catch (e) { error.textContent = 'WebGL není dostupné / WebGL unavailable'; return; }
  renderer.setPixelRatio(Math.min(devicePixelRatio || 1, 2));
  scene.add(new THREE.HemisphereLight(0xc7efff, 0x53605c, 1));
  const visualLight = new THREE.DirectionalLight(0xffffff, 0.8); visualLight.position.set(-800, 3000, 700); scene.add(visualLight);
  const controls = new THREE.EventDispatcher(), frames = new Set();
  let input, yaw = -0.9, elevation = 0.7, renderId = null, dragged = null;
  function requestRender() {
    if (renderId !== null) return;
    renderId = requestAnimationFrame(t => {renderId = null; for (const f of frames) f(t); renderer.render(scene, camera);});
  }
  const lux = V3D.luxPlugin({allowEstimate: true, lang: 'cs', onError: e => {error.textContent = e.message;}});
  const disposePlugin = lux.plugin({THREE, model, scene, camera, controls, root, renderer,
    requestRender, onFrame(fn) {frames.add(fn); return () => frames.delete(fn);}});
  function removeGeometry() {
    for (const child of [...model.children]) {
      model.remove(child);
      if (child.geometry) child.geometry.dispose();
      if (child.material) child.material.dispose();
    }
  }
  function box(low, high, color) {
    const object = new THREE.Mesh(new THREE.BoxGeometry(...high.map((x, i) => x - low[i])), new THREE.MeshStandardMaterial({color, roughness: 0.8}));
    object.position.set(...high.map((x, i) => (x + low[i]) / 2)); model.add(object); return object;
  }
  function resize() {
    const width = root.clientWidth, height = root.clientHeight;
    renderer.setSize(width, height, false); camera.aspect = width / height; camera.updateProjectionMatrix(); positionCamera();
  }
  function positionCamera() {
    if (!input) return;
    const bounds = new THREE.Box3().setFromObject(model), target = bounds.getCenter(new THREE.Vector3());
    const size = bounds.getSize(new THREE.Vector3());
    const halfVertical = camera.fov * Math.PI / 360;
    const halfHorizontal = Math.atan(Math.tan(halfVertical) * camera.aspect);
    // Celá obalová koule s rezervou 20 %, včetně desky dole i na mobilu.
    const radius = Math.max(size.length() / 2, 250) * 1.2 / Math.sin(Math.min(halfVertical, halfHorizontal));
    camera.position.set(target.x + radius * Math.cos(elevation) * Math.sin(yaw), target.y + radius * Math.sin(elevation),
      target.z + radius * Math.cos(elevation) * Math.cos(yaw));
    camera.lookAt(target); camera.updateMatrixWorld(true); controls.dispatchEvent({type:'change'}); requestRender();
  }
  function geometry() {
    removeGeometry();
    const plane = input.workplane;
    const board = fixture.measurements.find(m => m.partId === 'product_4933');
    const thickness = board.maxMm[1] - board.minMm[1];
    const low = [...plane.originMm]; low[1] -= thickness;
    const high = [low[0] + plane.depthMm, plane.originMm[1], low[2] + plane.widthMm];
    box(low, high, 0xc6d8da);
    for (const light of input.lights) box(...light.housingBoundsMm, 0xe4fff0);
    const result = lux.result();
    if (result) {
      const vertices = [], colors = [];
      const dx = result.grid.stepVMm, dz = result.grid.stepUMm;
      const ramp = x => {
        const stops = [[0, new THREE.Color('#21446b')], [300, new THREE.Color('#319bad')], [750, new THREE.Color('#6de0be')], [1000, new THREE.Color('#ffda8e')]];
        for (let i = 1; i < stops.length; i++) if (x < stops[i][0]) return stops[i-1][1].clone().lerp(stops[i][1], (x-stops[i-1][0])/(stops[i][0]-stops[i-1][0]));
        return stops[stops.length-1][1];
      };
      for (const p of result.points) {
        const [x, y, z] = p.positionMm, c = ramp(p.lux);
        // +1 mm je výhradně odstup barevné vrstvy pro vykreslení, výpočet zůstává na desce.
        for (const corner of [[-1,-1],[-1,1],[1,1],[-1,-1],[1,1],[1,-1]]) {
          vertices.push(x + corner[0]*dx/2, y+1, z+corner[1]*dz/2); colors.push(c.r,c.g,c.b);
        }
      }
      const geo = new THREE.BufferGeometry(); geo.setAttribute('position', new THREE.Float32BufferAttribute(vertices,3)); geo.setAttribute('color',new THREE.Float32BufferAttribute(colors,3));
      const heat = new THREE.Mesh(geo, new THREE.MeshBasicMaterial({vertexColors:true, side:THREE.DoubleSide, transparent:true, opacity:0.82}));
      heat.userData.__v3dHelper = true; model.add(heat);
    }
    resize();
  }
  function parameters() {
    const p = Object.fromEntries(['width','depth','height','arm','gap','flux','length','dimming'].map(id => [id, Number(document.getElementById(id).value)]));
    const count = document.getElementById('count').value;
    p.modeId = document.getElementById('power-mode').value;
    p.count = count === 'auto' ? Math.max(1, Math.floor((p.width + 47) / fixture.lights[0].housingLengthMm)) : Number(count);
    return p;
  }
  function update() {
    error.textContent = '';
    const p = parameters(), type = document.getElementById('type').value;
    document.getElementById('custom-inputs').hidden = type === 'LED1200';
    document.getElementById('power-inputs').hidden = type !== 'LED1200';
    document.getElementById('power-mode').disabled = type !== 'LED1200';
    document.getElementById('dimming-input').hidden = type === 'LED1200';
    document.getElementById('dimming').disabled = type === 'LED1200';
    document.getElementById('length').disabled = type === 'CUSTOM-POINT';
    for (const id of ['width','depth','height','arm','gap','dimming']) document.querySelector('output[for="'+id+'"]').textContent = p[id] + (id==='dimming'?' %':' mm');
    try {
      input = LuxDemoAdapter.build(fixture, p, type);
      lux.setInput(input);
      if (!lux.result()) { removeGeometry(); requestRender(); return; }
      geometry();
    } catch (e) { error.textContent = e.message; input = null; lux.setInput(null); removeGeometry(); requestRender(); }
  }
  document.getElementById('gap').value = fixture.lights[0].startMm[1] - fixture.workplane.originMm[1];
  function language() {
    const lang = document.getElementById('language').value, t = LuxData.texts[lang]; document.documentElement.lang = lang;
    document.querySelectorAll('[data-text]').forEach(e => {e.textContent = t[e.dataset.text] || e.dataset.text;}); lux.setLanguage(lang);
  }
  controlsForm.addEventListener('submit', e => e.preventDefault()); controlsForm.addEventListener('input', update);
  document.getElementById('language').addEventListener('change', language);
  canvas.addEventListener('pointerdown', e => {dragged={x:e.clientX,y:e.clientY,id:e.pointerId}; canvas.setPointerCapture(e.pointerId);});
  canvas.addEventListener('pointermove', e => {
    if (!dragged || dragged.id !== e.pointerId || !e.buttons) return;
    yaw += (e.clientX-dragged.x)/200; elevation = Math.min(1.45,Math.max(-0.2,elevation+(e.clientY-dragged.y)/300));
    dragged.x=e.clientX; dragged.y=e.clientY; positionCamera();
  });
  canvas.addEventListener('pointerup', () => {dragged=null;}); canvas.addEventListener('pointercancel', () => {dragged=null;});
  window.addEventListener('resize', resize); window.addEventListener('pagehide', () => {disposePlugin(); removeGeometry(); renderer.dispose(); if(renderId!==null) cancelAnimationFrame(renderId);}, {once:true});
  language(); update();
  // Jen lokální pomůcka pro ověření; nepřistupuje k síti ani k produkčnímu API.
  globalThis.LuxDemo = {update, input: () => input, result: () => lux.result(), disposePlugin};
})();
