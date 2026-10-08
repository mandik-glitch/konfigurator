/* Adaptace změřené šablony pro SAMOSTATNOU ukázku. Produkce musí předávat
 * skutečné pracovní plochy a LED po svém posunu z api/stul_glb.py. */
(function (root) {
  'use strict';
  function build(fixture, params, selectedType) {
    const data = JSON.parse(JSON.stringify(fixture));
    const base = fixture.sourceParameters;
    const dw = params.width - base.sirka, dd = params.depth - base.hloubka, dh = params.height - base.vyska;
    for (const k of ['width', 'depth', 'height', 'arm', 'gap', 'count', 'flux', 'length', 'dimming'])
      if (!Number.isFinite(params[k])) throw new Error('Neplatný parametr: ' + k);
    if (params.width < 500 || params.width > 3000 || params.depth < 400 || params.depth > 1500 ||
        params.height < 140 || params.height > 1200 || params.arm < 200 || params.arm > 1500 || params.gap < 100 || params.gap > 2000 ||
        !Number.isInteger(params.count) || params.count < 0 || params.count > 4 || params.length < 10 || params.length > 3000)
      throw new Error('Parametry ukázky jsou mimo povolený rozsah');
    const original = fixture.lights[0];
    data.workplane.widthMm += dw;
    data.workplane.depthMm += dd;
    data.workplane.originMm[1] += dh;
    const center = original.startMm.map((x, i) => (x + original.endMm[i]) / 2);
    // Zdroj R[LED]: x += dD; top_zkr = 560 - led_rameno; z += dW/2.
    center[0] += dd + base.led_rameno - params.arm;
    center[1] = data.workplane.originMm[1] + params.gap;
    center[2] += dw / 2;
    const known = selectedType === 'LED1200';
    const emittingLength = known ? original.nominalLengthMm : params.length;
    const spacing = known ? original.housingLengthMm : params.length;
    data.lights = Array.from({length: params.count}, (_, index) => {
      const light = JSON.parse(JSON.stringify(original));
      const c = [...center]; c[2] += (index - (params.count - 1) / 2) * spacing;
      light.id = (known ? original.sku : 'CUSTOM-LINE') + '-' + (index + 1);
      if (!known) {
        light.sku = 'CUSTOM-LINE'; light.productId = null; light.powerW = null;
        light.luminousFluxLm = params.flux; light.housingLengthMm = params.length;
        light.nominalLengthMm = params.length;
      }
      light.dimmingFactor = params.dimming / 100;
      light.startMm = [c[0], c[1], c[2] - emittingLength / 2];
      light.endMm = [c[0], c[1], c[2] + emittingLength / 2];
      if (selectedType === 'CUSTOM-POINT') { light.type = 'point'; light.positionMm = c; }
      const housing = original.housingBoundsMm;
      const housingDepth = housing[1][0] - housing[0][0], housingHeight = housing[1][1] - housing[0][1];
      // Vlastní scénář přebírá změřenou obálku původního tělesa pouze pro zobrazení.
      light.housingBoundsMm = [[c[0] - housingDepth / 2, c[1], c[2] - spacing / 2],
        [c[0] + housingDepth / 2, c[1] + housingHeight, c[2] + spacing / 2]];
      return light;
    });
    return data;
  }
  if (typeof module === 'object' && module.exports) module.exports = {build};
  else root.LuxDemoAdapter = {build};
})(typeof globalThis !== 'undefined' ? globalThis : this);
