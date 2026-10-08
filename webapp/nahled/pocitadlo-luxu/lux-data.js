/* Hodnoty ověřeny ve veřejných podkladech 2026-10-05. Zdroje viz tabulka_cinnosti.md.
 * Nikdy nejde o povolení vykonávat práci ani o potvrzení shody celé soustavy. */
(function (root) {
  'use strict';
  const electronic = 'https://www.licht.de/de/lichtanwendungen/bereich/7-industrie-und-gewerbe/150-elektro-und-elektronik';
  const wood = 'https://www.licht.de/de/lichtanwendungen/bereich/7-industrie-und-gewerbe/35-holzverarbeitung';
  const packing = 'https://www.bgbau-medien.de/handlungshilfen_gb/daten/dguv/115_401/3.htm';
  function task(id, cs, sk, en, lux, uniformity, ra, ugr, source, standard) {
    return {id, label: {cs, sk, en}, lux, uniformity, ra, ugr, source, standard};
  }
  const data = {
    catalogue: [{productId: 4929, sku: 'LED1200', type: 'linear', luminousFluxLm: 3960, powerW: 33,
      nominalLengthMm: 1200, housingLengthMm: 1247, emittingLengthMm: null, beamAngleDeg: null,
      distribution: null, cctK: null, criRa: null, photometryFile: null, maintenanceFactor: null,
      source: 'ukoly/podklady/led_produkt_4929.json: název; api/stul_konfigurator.py:55'}],
    activities: [
      task('packing', 'Balení a expedice ve skladu', 'Balenie a expedícia v sklade', 'Warehouse packing and dispatch', 300, null, null, null, packing, 'DGUV 115-401 / ASR A3.4 (DE; doplňkový podklad)'),
      task('wood_assembly', 'Lepení a sestavování dřeva', 'Lepenie a zostavovanie dreva', 'Wood gluing and assembly', 300, 0.6, 80, 25, wood, 'EN 12464-1:2021'),
      task('electrical_coarse', 'Hrubá elektrotechnická montáž', 'Hrubá elektrotechnická montáž', 'Coarse electrical assembly', 300, 0.6, 80, 25, electronic, 'EN 12464-1:2021'),
      task('electrical_medium', 'Středně jemná elektrotechnická montáž', 'Stredne jemná elektrotechnická montáž', 'Medium electrical assembly', 500, 0.6, 80, 22, electronic, 'EN 12464-1:2021'),
      task('electrical_fine', 'Velmi jemná elektrotechnická montáž', 'Veľmi jemná elektrotechnická montáž', 'Very fine electrical assembly', 750, 0.7, 80, 19, electronic, 'EN 12464-1:2021'),
      task('electrical_precision', 'Přesná montáž měřidel a desek plošných spojů', 'Presná montáž meradiel a dosiek plošných spojov', 'Precision instrument and circuit board assembly', 1000, 0.7, 80, 16, electronic, 'EN 12464-1:2021'),
      task('wood_inspection', 'Kontrola kvality dřeva', 'Kontrola kvality dreva', 'Wood quality inspection', 1000, 0.7, 90, 19, wood, 'EN 12464-1:2021')
    ],
    texts: {
      cs: {title: 'Světlo na pracovní ploše', mean: 'Průměr', minimum: 'Minimum v síti', edge: 'Minimum v doplňkových bodech', uniformity: 'Rovnoměrnost',
        estimate: 'Orientační odhad', initial: 'Počáteční stav; údržba neurčena', maintained: 'Scénář s údržbou',
        hoverTitle: 'Porovnání s požadavky pro činnosti', scope: 'Celá zvolená pracovní plocha · všechna světla',
        reached: 'Luxový práh dosažen', low: 'Luxový práh nedosažen', uneven: 'Nízká rovnoměrnost', unknownUniformity: 'Rovnoměrnost: údaj chybí',
        caveat: 'Odhad světla z LED. Shoda s normou není posouzena; zbývá ověřit optiku, údržbu, oslnění, podání barev a okolní osvětlení.',
        empty: 'Světla jsou vypnutá.', missing: 'Pro výpočet chybí údaje.',
        assumption: 'Pro ukázku předpokládáme rovnoměrnou světelnou čáru a Lambertovo vyzařování; skutečná optika LED není známá.',
        width: 'Šířka desky', depth: 'Hloubka desky', height: 'Výška desky', arm: 'Vodorovné vysunutí LED', gap: 'Výška LED nad deskou',
        count: 'Počet světel', type: 'Typ světla', known: 'LED1200 · 3960 lm · 33 W', custom: 'Vlastní údaje světelné čáry',
        customPoint: 'Vlastní bodový model (scénář)', flux: 'Světelný tok jednoho světla (lm)', length: 'Délka světelné čáry (mm)', dimming: 'Stmívání (%)',
        guide: 'Otáčejte tažením. Najetím na LED se ukáže průsvitný panel. Na dotykové obrazovce klepněte na LED.',
        subtitle: 'Pracovní ukázka k posouzení. Rozměry v mm; cifry se mění živě.', manual: 'Vlastní hodnoty jsou váš scénář, nejsou údajem produktové karty.'},
      sk: {title: 'Svetlo na pracovnej ploche', mean: 'Priemer', minimum: 'Minimum v sieti', edge: 'Minimum v doplnkových bodoch', uniformity: 'Rovnomernosť',
        estimate: 'Orientačný odhad', initial: 'Počiatočný stav; údržba neurčená', maintained: 'Scenár s údržbou',
        hoverTitle: 'Porovnanie s požiadavkami pre činnosti', scope: 'Celá zvolená pracovná plocha · všetky svetlá',
        reached: 'Luxový prah dosiahnutý', low: 'Luxový prah nedosiahnutý', uneven: 'Nízka rovnomernosť', unknownUniformity: 'Rovnomernosť: údaj chýba',
        caveat: 'Odhad svetla z LED. Zhoda s normou nie je posúdená; zostáva overiť optiku, údržbu, oslnenie, podanie farieb a okolité osvetlenie.',
        empty: 'Svetlá sú vypnuté.', missing: 'Na výpočet chýbajú údaje.',
        assumption: 'V ukážke predpokladáme rovnomernú svetelnú čiaru a Lambertovo vyžarovanie; skutočná optika LED nie je známa.',
        width: 'Šírka dosky', depth: 'Hĺbka dosky', height: 'Výška dosky', arm: 'Vodorovné vysunutie LED', gap: 'Výška LED nad doskou',
        count: 'Počet svetiel', type: 'Typ svetla', known: 'LED1200 · 3960 lm · 33 W', custom: 'Vlastné údaje svetelnej čiary',
        customPoint: 'Vlastný bodový model (scenár)', flux: 'Svetelný tok jedného svetla (lm)', length: 'Dĺžka svetelnej čiary (mm)', dimming: 'Stmievanie (%)',
        guide: 'Otáčajte ťahaním. Pri ukázaní na LED sa zobrazí priesvitný panel. Na dotykovej obrazovke klepnite na LED.',
        subtitle: 'Pracovná ukážka na posúdenie. Rozmery v mm; čísla sa menia priebežne.', manual: 'Vlastné hodnoty sú váš scenár, nie údaj produktovej karty.'},
      en: {title: 'Light on the work surface', mean: 'Average', minimum: 'Grid minimum', edge: 'Additional probe minimum', uniformity: 'Uniformity',
        estimate: 'Indicative estimate', initial: 'Initial state; maintenance unspecified', maintained: 'Maintenance scenario',
        hoverTitle: 'Comparison with task requirements', scope: 'Entire selected work area · all lights',
        reached: 'Lux threshold reached', low: 'Lux threshold not reached', uneven: 'Low uniformity', unknownUniformity: 'Uniformity: data missing',
        caveat: 'Estimated LED illumination. Standard compliance is not assessed; optics, maintenance, glare, colour rendering and surrounding lighting still need checking.',
        empty: 'Lights are off.', missing: 'Required calculation data is missing.',
        assumption: 'The demo assumes a uniform luminous line with Lambertian emission; the actual LED optics are unknown.',
        width: 'Worktop width', depth: 'Worktop depth', height: 'Worktop height', arm: 'Horizontal LED reach', gap: 'LED height above worktop',
        count: 'Number of lights', type: 'Light type', known: 'LED1200 · 3960 lm · 33 W', custom: 'Custom luminous line data',
        customPoint: 'Custom point model (scenario)', flux: 'Flux per light (lm)', length: 'Luminous line length (mm)', dimming: 'Dimming (%)',
        guide: 'Drag to rotate. Hover over a light for the translucent panel. Tap a light on a touch screen.',
        subtitle: 'Working preview for review. Dimensions in mm; values update live.', manual: 'Custom values describe your scenario, not a product specification.'}
    }
  };
  if (typeof module === 'object' && module.exports) module.exports = data;
  else root.LuxData = data;
})(typeof globalThis !== 'undefined' ? globalThis : this);
