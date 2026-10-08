/* John, 2026-10-05. Čistý výpočet; mm na vstupu, lx na výstupu.
 * Vzorce a meze modelu: ZDROJE_A_VYPOCET.md. Bez DOM, DB a sítě. */
(function (root, factory) {
  'use strict';
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.LuxCore = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';
  const dot = (a, b) => a.reduce((s, x, i) => s + x * b[i], 0);
  const sub = (a, b) => a.map((x, i) => x - b[i]);
  const add = (a, b) => a.map((x, i) => x + b[i]);
  const mul = (a, k) => a.map(x => x * k);
  function number(x, name, lo, hi) {
    if (typeof x !== 'number' || !Number.isFinite(x) || x < lo || x > hi)
      throw new Error('Neplatný vstup: ' + name);
    return x;
  }
  function vec(x, name) {
    if (!Array.isArray(x) || x.length !== 3) throw new Error('Neplatný vektor: ' + name);
    x.forEach(v => number(v, name, -1e6, 1e6));
    return x;
  }
  function unit(x, name) {
    vec(x, name);
    if (Math.abs(dot(x, x) - 1) > 1e-6) throw new Error('Vektor musí mít délku 1: ' + name);
    return x;
  }
  function integer(x, name, lo, hi) {
    number(x, name, lo, hi);
    if (!Number.isInteger(x)) throw new Error('Vyžaduje celé číslo: ' + name);
    return x;
  }
  function prepareLight(light, options) {
    if (!light || typeof light.id !== 'string' || !light.id) throw new Error('Chybí ID světla');
    number(light.luminousFluxLm, 'luminousFluxLm', 0, 1e6);
    unit(light.direction, 'direction');
    const distribution = light.distribution;
    if (!distribution || distribution.kind !== 'cosine_power') throw new Error('Chybí podporovaná vyzařovací charakteristika');
    number(distribution.exponent, 'exponent', 0, 100);
    if (!['hypothesis', 'verified'].includes(distribution.status)) throw new Error('Chybí stav charakteristiky');
    if (typeof distribution.source !== 'string' || !distribution.source) throw new Error('Chybí zdroj charakteristiky');
    if (!['hypothesis', 'measured'].includes(light.geometryStatus)) throw new Error('Chybí stav geometrie zářiče');
    const estimated = distribution.status === 'hypothesis' || light.geometryStatus === 'hypothesis';
    if (estimated && options.allowEstimate !== true) throw new Error('Odhad vyžaduje allowEstimate:true');
    const mf = light.maintenanceFactor;
    if (mf !== null && mf !== undefined) number(mf, 'maintenanceFactor', 0, 1);
    const dim = light.dimmingFactor === undefined ? 1 : number(light.dimmingFactor, 'dimmingFactor', 0, 1);
    let samples;
    if (light.type === 'point') samples = [vec(light.positionMm, 'positionMm')];
    else if (light.type === 'linear') {
      vec(light.startMm, 'startMm'); vec(light.endMm, 'endMm');
      const delta = sub(light.endMm, light.startMm);
      if (dot(delta, delta) < 1e-12) throw new Error('Nulová délka zářiče');
      const count = integer(options.lineSamples === undefined ? 128 : options.lineSamples, 'lineSamples', 1, 2048);
      samples = Array.from({length: count}, (_, i) => add(light.startMm, mul(delta, (i + 0.5) / count)));
    } else throw new Error('Nepodporovaný typ světla');
    // Normalizace integrálem přes polokouli: Φ = 2π I0/(n+1).
    return {samples, direction: light.direction, exponent: distribution.exponent,
      intensity0: light.luminousFluxLm * dim * (mf == null ? 1 : mf) * (distribution.exponent + 1) / (2 * Math.PI * samples.length),
      estimated, maintained: mf != null};
  }
  function sampleLux(point, normal, sources) {
    let total = 0;
    for (const light of sources) for (const source of light.samples) {
      const r = sub(point, source);
      const d2mm = dot(r, r);
      if (d2mm < 1) throw new Error('Bod je blíže než 1 mm od zářiče');
      const dir = mul(r, 1 / Math.sqrt(d2mm));
      const emissionCos = dot(light.direction, dir);
      const incidenceCos = -dot(normal, dir);
      if (emissionCos > 0 && incidenceCos > 0)
        total += light.intensity0 * Math.pow(emissionCos, light.exponent) * incidenceCos / (d2mm / 1e6);
    }
    if (!Number.isFinite(total)) throw new Error('Výpočet není konečný');
    return total;
  }
  function pointLux(point, normal, lights, options = {}) {
    vec(point, 'point'); unit(normal, 'normal');
    if (!Array.isArray(lights) || lights.length > 32) throw new Error('Neplatný seznam světel');
    return sampleLux(point, normal, lights.map(l => prepareLight(l, options)));
  }
  function calculate(input, options = {}) {
    if (!input || input.version !== 1 || input.units !== 'mm') throw new Error('Vyžaduje version:1 a units:mm');
    const p = input.workplane;
    if (!p) throw new Error('Chybí pracovní rovina');
    vec(p.originMm, 'originMm'); unit(p.axisU, 'axisU'); unit(p.axisV, 'axisV'); unit(p.normal, 'normal');
    if ([dot(p.axisU, p.axisV), dot(p.axisU, p.normal), dot(p.axisV, p.normal)].some(x => Math.abs(x) > 1e-6))
      throw new Error('Osy pracovní roviny nejsou kolmé');
    number(p.widthMm, 'widthMm', 1, 10000); number(p.depthMm, 'depthMm', 1, 10000);
    if (!Array.isArray(input.lights) || input.lights.length > 32) throw new Error('Neplatný seznam světel');
    const ids = input.lights.map(l => l.id);
    if (new Set(ids).size !== ids.length) throw new Error('Duplicitní ID světla');
    const lights = input.lights.map(l => prepareLight(l, options));
    const step = number(options.gridStepMm === undefined ? 100 : options.gridStepMm, 'gridStepMm', 1, 1000);
    const nu = Math.ceil(p.widthMm / step), nv = Math.ceil(p.depthMm / step);
    if (nu * nv > 4096 || nu * nv * lights.reduce((n, l) => n + l.samples.length, 0) > 5e6)
      throw new Error('Příliš náročné výpočetní pole');
    const holes = p.excludeRects || [];
    if (!Array.isArray(holes) || holes.length > 64) throw new Error('Neplatné výřezy');
    holes.forEach(h => {
      if (!Array.isArray(h) || h.length !== 4) throw new Error('Neplatný výřez');
      h.forEach((x, i) => number(x, 'výřez', 0, i % 2 ? p.depthMm : p.widthMm));
      if (h[2] <= h[0] || h[3] <= h[1]) throw new Error('Výřez nemá kladnou plochu');
    });
    const at = (u, v) => add(add(p.originMm, mul(p.axisU, u)), mul(p.axisV, v));
    const points = [];
    for (let j = 0; j < nv; j++) for (let i = 0; i < nu; i++) {
      const u = p.widthMm * (i + 0.5) / nu, v = p.depthMm * (j + 0.5) / nv;
      if (holes.some(h => u >= h[0] && u <= h[2] && v >= h[1] && v <= h[3])) continue;
      const positionMm = at(u, v);
      points.push({uMm: u, vMm: v, positionMm, lux: sampleLux(positionMm, p.normal, lights)});
    }
    if (!points.length) throw new Error('Pracovní pole neobsahuje žádný bod');
    const meanLux = points.reduce((s, q) => s + q.lux, 0) / points.length;
    const minLux = Math.min(...points.map(q => q.lux)), maxLux = Math.max(...points.map(q => q.lux));
    const probes = [];
    for (const v of [0, p.depthMm / 2, p.depthMm]) for (const u of [0, p.widthMm / 4, p.widthMm / 2, 3 * p.widthMm / 4, p.widthMm]) {
      if (holes.some(h => u >= h[0] && u <= h[2] && v >= h[1] && v <= h[3])) continue;
      const positionMm = at(u, v);
      probes.push({uMm: u, vMm: v, positionMm, lux: sampleLux(positionMm, p.normal, lights)});
    }
    return {points, probes, meanLux, minLux, maxLux, uniformity: meanLux > 0 ? minLux / meanLux : null,
      edgeMinLux: probes.length ? Math.min(...probes.map(q => q.lux)) : null,
      sampleCount: points.length, grid: {nu, nv, stepUMm: p.widthMm / nu, stepVMm: p.depthMm / nv},
      estimated: lights.some(l => l.estimated), basis: lights.length && lights.every(l => l.maintained) ? 'maintained' : 'initial',
      warnings: ['direct_light_only', 'no_shadows_or_reflections', 'technical_grid_not_normative'],
      illuminatedAreaM2: points.length * p.widthMm / nu * p.depthMm / nv / 1e6};
  }
  function assessActivities(result, activities) {
    return activities.map(a => ({...a, luxReached: result.meanLux >= a.lux,
      uniformityReached: a.uniformity == null ? null : result.uniformity != null && result.uniformity >= a.uniformity,
      provisional: result.estimated || result.basis !== 'maintained', compliance: 'not_assessed'}));
  }
  return {pointLux, calculate, assessActivities};
});
