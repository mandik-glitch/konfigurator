/* Hodnoty ověřeny ve veřejných podkladech 2026-10-05. Zdroje viz tabulka_cinnosti.md.
 * Nikdy nejde o povolení vykonávat práci ani o potvrzení shody celé soustavy. */
(function (root) {
  'use strict';
  const electronic = 'https://www.licht.de/de/lichtanwendungen/bereich/7-industrie-und-gewerbe/150-elektro-und-elektronik';
  const wood = 'https://www.licht.de/de/lichtanwendungen/bereich/7-industrie-und-gewerbe/35-holzverarbeitung';
  const packing = 'https://www.licht.de/de/lichtanwendungen/bereich/7-industrie-und-gewerbe/41-lager-und-logistik';
  const metal = 'https://www.licht.de/de/lichtanwendungen/bereich/7-industrie-und-gewerbe/149-metall-maschinen-und-anlagenbau';
  const asr = 'https://www.baua.de/DE/Angebote/Regelwerk/ASR/pdf/ASR-A3-4.pdf?__blob=publicationFile';
  const dguv = 'https://publikationen.dguv.de/widgets/pdf/download/article/642';
  const isco = 'https://csu.gov.cz/klasifikace_zamestnani_-cz_isco-';
  function task(id, cs, sk, en, lux, uniformity, ra, ugr, source, standard) {
    return {id, label: {cs, sk, en}, lux, uniformity, ra, ugr, source, standard};
  }
  const data = {
    catalogue: [{productId: 4929, sku: 'LED1200', type: 'linear', luminousFluxLm: 3960, powerW: 33,
      manufacturer: 'LEDVANCE', modelName: 'DAMPPROOF COMPACT TH 1200 IP66 PS',
      typeDesignation: 'DP COMP TH 1200 V 33W 840 IP66 PS', labelCode: 'AC40258', ean: '4058075740914',
      colour: 'WHITE', nominalLengthMm: 1200, housingLengthMm: 1247,
      labelledDimensionsMm: [1285, 60, 53], emittingLengthMm: null, beamAngleDeg: 120,
      distribution: {kind: 'cosine_power', exponent: 1, beamAngleDeg: 120, status: 'hypothesis',
        source: 'https://cie.co.at/eilvterm/17-24-062; https://cie.co.at/eilv/840; 120° ze štítku; předpoklad polovičního maxima'},
      cctK: 4000, criRa: {min: 80, operator: '>'}, ip: 'IP66', ik: 'IK08', indoorOnly: true,
      dimmable: false, protectionClass: 'II', operatingTemperatureC: [-20, 45],
      lifetime: {hours: 50000, lumenMaintenance: 'L80'}, voltageV: [220, 240], frequencyHz: [50, 60],
      markings: ['TÜV SÜD', 'CE', 'UKCA', 'EAC'],
      defaultModeId: '33W', modeId: '33W',
      powerModes: [{id: '33W', powerW: 33, luminousFluxLm: 3960, efficacyLmPerW: 120},
        {id: '21W', powerW: 21, luminousFluxLm: 2600, efficacyLmPerW: 123}],
      photometryFile: null, maintenanceFactor: null,
      sources: {label: 'led_stitek_ledvance_AC40258.jpg',
        box: 'led_stitek_ledvance_krabice_nazev.jpg', card: 'led_produkt_4929.json',
        manufacturer: 'https://www.ledvance.com/en/gtin/4058075740914', geometry: 'generátor stolu (délka modelu)'},
      source: 'Dvě fotografie štítku a obalu svítidla; karta 4929; délka modelu v generátoru stolu'},
    // LED 600 (karta 5359, 2026-10-07): zná se JEN výkon, tok a délka z karty; ostatní údaje neznámé (null), optika = PŘEDPOKLAD jako u LED1200 (hypothesis) – ověřit podle štítku / datového listu
    {productId: 5359, sku: 'LED600', type: 'linear', luminousFluxLm: 1920, powerW: 16,
      manufacturer: null, modelName: null, typeDesignation: null, labelCode: null, ean: null,
      colour: null, nominalLengthMm: 600, housingLengthMm: 647,
      labelledDimensionsMm: null, emittingLengthMm: null, beamAngleDeg: null,
      distribution: {kind: 'cosine_power', exponent: 1, beamAngleDeg: 120, status: 'hypothesis',
        source: 'předpoklad: stejná optika jako LED1200 (kosinová charakteristika, 120°); skutečná fotometrie LED 600 není známa'},
      cctK: null, criRa: null, ip: null, ik: null, indoorOnly: null,
      dimmable: false, protectionClass: null, operatingTemperatureC: null,
      lifetime: null, voltageV: null, frequencyHz: null,
      markings: [],
      defaultModeId: '16W', modeId: '16W',
      powerModes: [{id: '16W', powerW: 16, luminousFluxLm: 1920, efficacyLmPerW: 120}],
      photometryFile: null, maintenanceFactor: null,
      sources: {card: 'karta_5359'},
      source: 'Karta 5359 (Osvětlení LED 600mm 16W 1920lm): výkon, tok a délka; délka modelu v generátoru stolu (647 mm); optika předpokládána jako u LED1200'}],
    activities: [
      task('metal_coarse', 'Hrubá montáž kovů', 'Hrubá montáž kovov', 'Coarse metal assembly', 200, 0.6, 60, 25, metal, 'EN 12464-1:2021'),
      task('packing', 'Balení a expedice ve skladu', 'Balenie a expedícia v sklade', 'Warehouse packing and dispatch', 300, 0.6, 80, 25, packing, 'EN 12464-1:2021'),
      task('packing_group', 'Balení a seskupování ve skladu', 'Balenie a zoskupovanie v sklade', 'Warehouse packing and grouping', 300, 0.5, 80, 25, packing, 'EN 12464-1:2021'),
      task('wood_assembly', 'Lepení a sestavování dřeva', 'Lepenie a zostavovanie dreva', 'Wood gluing and assembly', 300, 0.6, 80, 25, wood, 'EN 12464-1:2021'),
      task('electrical_coarse', 'Hrubá elektrotechnická montáž', 'Hrubá elektrotechnická montáž', 'Coarse electrical assembly', 300, 0.6, 80, 25, electronic, 'EN 12464-1:2021'),
      task('electrical_medium', 'Středně jemná elektrotechnická montáž', 'Stredne jemná elektrotechnická montáž', 'Medium electrical assembly', 500, 0.6, 80, 22, electronic, 'EN 12464-1:2021'),
      task('office', 'Psaní a čtení v kanceláři', 'Písanie a čítanie v kancelárii', 'Office writing and reading', 500, 0.6, 80, 19, asr, 'ASR A3.4 / DGUV 215-442 (DE)'),
      task('computer', 'Práce na počítači', 'Práca na počítači', 'Computer data processing', 500, 0.6, 80, 19, asr, 'ASR A3.4 / DGUV 215-442 (DE)'),
      task('electrical_fine', 'Velmi jemná elektrotechnická montáž', 'Veľmi jemná elektrotechnická montáž', 'Very fine electrical assembly', 750, 0.7, 80, 19, electronic, 'EN 12464-1:2021'),
      task('drawing', 'Ruční technické kreslení', 'Ručné technické kreslenie', 'Technical drawing by hand', 750, 0.6, 80, null, asr, 'ASR A3.4 (DE)'),
      task('electrical_precision', 'Přesná montáž měřidel a desek plošných spojů', 'Presná montáž meradiel a dosiek plošných spojov', 'Precision instrument and circuit board assembly', 1000, 0.7, 80, 16, electronic, 'EN 12464-1:2021'),
      task('colour_sorting', 'Barevné třídění a kontrola', 'Farebné triedenie a kontrola', 'Colour sorting and inspection', 1000, 0.6, 90, null, asr, 'ASR A3.4 (DE)'),
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
  const additions = {
    cs: {known: 'LED1200 · dva výkonové stupně', powerMode: 'Výkonový stupeň LED', mode33: '33 W · 3960 lm (výchozí)', mode21: '21 W · 2600 lm',
      nonDimmable: 'Nestmívatelné · volí se jeden ze dvou výkonových stupňů', technical: 'Údaje svítidla',
      beam: 'Úhel vyzařování', cct: 'Teplota chromatičnosti', cri: 'Podání barev', protection: 'Krytí / nárazová odolnost',
      environment: 'Použití', indoor: 'Uvnitř', lifetime: 'Životnost', temperature: 'Provozní teplota',
      dimensions: 'Rozměry na krabici', protectionClass: 'Třída ochrany', electrical: 'Napájení', modes: 'Dostupné stupně',
      activeMode: 'Zvolený stupeň', manufacturerSource: 'Údaje výrobce',
      dimensionConflict: 'Krabice: 1285 mm; model: 1247 mm. Rozpor čeká na ověření; geometrie se nemění.',
      colourRelevance: '4000 K: neutrální bílá. EN 12464-1 posuzuje barvu světla i Ra podle úlohy; samotných 4000 K činnost nepotvrzuje.',
      criScope: 'Ra se zde vztahuje k označenému svítidlu. Společné osvětlení pracoviště není posouzeno.',
      raSupported: 'Ra požadavek doložen pro všechna zvolená světla', raUnproven: 'Požadované Ra není doloženo', raUnknown: 'Ra: požadavek neuveden',
      assumption: 'Úhel 120° je doložen štítkem. Rozložení odhadujeme kosinovým modelem; svítící délka a naměřená fotometrie zatím chybí.',
      caveat: 'Odhad přímého světla LED. Shoda s normou není posouzena; zbývá ověřit fotometrii, údržbu, oslnění a okolní osvětlení.'},
    sk: {known: 'LED1200 · dva výkonové stupne', powerMode: 'Výkonový stupeň LED', mode33: '33 W · 3960 lm (predvolený)', mode21: '21 W · 2600 lm',
      nonDimmable: 'Nestmievateľné · volí sa jeden z dvoch výkonových stupňov', technical: 'Údaje svietidla',
      beam: 'Uhol vyžarovania', cct: 'Teplota chromatickosti', cri: 'Podanie farieb', protection: 'Krytie / nárazová odolnosť',
      environment: 'Použitie', indoor: 'Vnútri', lifetime: 'Životnosť', temperature: 'Prevádzková teplota',
      dimensions: 'Rozmery na krabici', protectionClass: 'Trieda ochrany', electrical: 'Napájanie', modes: 'Dostupné stupne',
      activeMode: 'Zvolený stupeň', manufacturerSource: 'Údaje výrobcu',
      dimensionConflict: 'Krabica: 1285 mm; model: 1247 mm. Rozpor čaká na overenie; geometria sa nemení.',
      colourRelevance: '4000 K: neutrálna biela. EN 12464-1 posudzuje farbu svetla aj Ra podľa úlohy; samotných 4000 K činnosť nepotvrdzuje.',
      criScope: 'Ra sa tu vzťahuje na označené svietidlo. Spoločné osvetlenie pracoviska nie je posúdené.',
      raSupported: 'Ra požiadavka doložená pre všetky zvolené svetlá', raUnproven: 'Požadované Ra nie je doložené', raUnknown: 'Ra: požiadavka neuvedená',
      assumption: 'Uhol 120° je doložený štítkom. Rozloženie odhadujeme kosínusovým modelom; svietiaca dĺžka a nameraná fotometria zatiaľ chýbajú.',
      caveat: 'Odhad priameho svetla LED. Zhoda s normou nie je posúdená; zostáva overiť fotometriu, údržbu, oslnenie a okolité osvetlenie.'},
    en: {known: 'LED1200 · two power settings', powerMode: 'LED power setting', mode33: '33 W · 3960 lm (default)', mode21: '21 W · 2600 lm',
      nonDimmable: 'Not dimmable · select one of two power settings', technical: 'Luminaire specifications',
      beam: 'Beam angle', cct: 'Colour temperature', cri: 'Colour rendering', protection: 'Ingress / impact protection',
      environment: 'Use', indoor: 'Indoors', lifetime: 'Lifetime', temperature: 'Operating temperature',
      dimensions: 'Dimensions on box', protectionClass: 'Protection class', electrical: 'Power supply', modes: 'Available settings',
      activeMode: 'Selected setting', manufacturerSource: 'Manufacturer data',
      dimensionConflict: 'Box: 1285 mm; model: 1247 mm. Difference awaits verification; geometry is unchanged.',
      colourRelevance: '4000 K: neutral white. EN 12464-1 considers light colour and Ra for each task; 4000 K alone does not establish suitability.',
      criScope: 'Ra here refers to the selected luminaire. Combined workplace lighting has not been assessed.',
      raSupported: 'Ra requirement documented for all selected lights', raUnproven: 'Required Ra is not documented', raUnknown: 'Ra: requirement unspecified',
      assumption: 'The label confirms 120°. Distribution is estimated with a cosine model; emitting length and measured photometry are still missing.',
      caveat: 'Estimated direct LED illumination. Standard compliance is not assessed; photometry, maintenance, glare and surrounding lighting still need checking.'}
  };
  for (const lang of ['cs', 'sk', 'en']) Object.assign(data.texts[lang], additions[lang]);
  // ČSÚ: systematická část účinná 1. 2. 2026. Překlady jsou vlastní;
  // přiřazení zaměstnání k úloze není součástí ČSÚ ani světelné normy.
  const occupations = {
    '8211': {cs:'Montážní dělníci mechanických zařízení', sk:'Montážni pracovníci mechanických zariadení', en:'Mechanical machinery assemblers'},
    '8212': {cs:'Montážní dělníci elektrických, energetických a elektronických zařízení', sk:'Montážni pracovníci elektrických, energetických a elektronických zariadení', en:'Electrical, energy and electronic equipment assemblers'},
    '8219': {cs:'Montážní dělníci ostatních výrobků', sk:'Montážni pracovníci ostatných výrobkov', en:'Other product assemblers'},
    '9321': {cs:'Ruční baliči, plniči a etiketovači', sk:'Ručné balenie, plnenie a etiketovanie', en:'Hand packers, fillers and labellers'},
    '4110': {cs:'Všeobecní administrativní pracovníci', sk:'Všeobecní administratívni pracovníci', en:'General office clerks'},
    '4132': {cs:'Pracovníci pro zadávání dat', sk:'Pracovníci na zadávanie údajov', en:'Data entry clerks'},
    '31152': {cs:'Strojírenští technici projektanti, konstruktéři', sk:'Strojárski technici projektanti, konštruktéri', en:'Mechanical engineering design technicians'},
    '7311': {cs:'Výrobci, mechanici a opraváři přesných přístrojů a zařízení', sk:'Výrobcovia, mechanici a opravári presných prístrojov a zariadení', en:'Precision instrument makers and repairers'},
    '7543': {cs:'Kvalitáři a testovači výrobků, laboranti (kromě potravin a nápojů)', sk:'Kontrolóri a testeri výrobkov, laboranti (okrem potravín a nápojov)', en:'Product graders, testers and laboratory assistants (except food and beverages)'}
  };
  const codes = {metal_coarse:['8211'], packing:['9321'], packing_group:['9321'], wood_assembly:['8219'],
    electrical_coarse:['8212'], electrical_medium:['8212'], office:['4110'], computer:['4132'],
    electrical_fine:['8212'], drawing:['31152'], electrical_precision:['8212','7311'],
    colour_sorting:['7543'], wood_inspection:['7543']};
  const summaryIds = ['metal_coarse','packing','office','computer','electrical_fine','drawing','electrical_precision'];
  for (const row of data.activities) {
    row.summary = summaryIds.includes(row.id);
    row.classification = 'CZ-ISCO'; row.classificationEdition = '2026-02-01';
    row.occupationMapping = 'indicative'; row.occupationSource = isco;
    row.occupations = codes[row.id].map(code => ({code, label: occupations[code]}));
    row.evidence = row.source === asr ? 'primary_DE_rule' : 'published_EN_excerpt';
    row.sourceLocator = row.source === asr ? 'ASR A3.4:2023, příloha 3; rovnoměrnost 6.2(3)' : 'Zveřejněná tabulka EN 12464-1:2021 na stránce';
    if (['office','computer'].includes(row.id)) row.glareSource = dguv;
  }
  data.normSources = {
    standard: {id:'ČSN EN 12464-1:2022 / EN 12464-1:2021', url:'https://csnonline.agentura-cas.cz/Detailnormy.aspx?k=514798',
      title:{cs:'Světlo a osvětlení – Osvětlení pracovišť – Část 1: Vnitřní pracoviště',
        sk:'Svetlo a osvetlenie – Osvetlenie pracovísk – Časť 1: Vnútorné pracoviská (česká norma)',
        en:'Light and lighting – Lighting of work places – Part 1: Indoor work places'}},
    law: {id:'Nařízení vlády č. 361/2007 Sb., § 45–46', url:'https://e-sbirka.gov.cz/sb/2007/361?odkazId=209331627',
      title:{cs:'Kterým se stanoví podmínky ochrany zdraví při práci',
        sk:'Nariadenie vlády ČR o podmienkach ochrany zdravia pri práci',
        en:'Czech Government Regulation laying down conditions for occupational health protection'}},
    physics: {id:'CIE S 017:2020', url:'https://cie.co.at/eilvterm/17-25-104'},
    excerpt: {id:'licht.de / ZVEI – EN 12464-1:2021', url:'https://www.licht.de/fileadmin/Publikationen_Downloads/Weitere/2403_LF60_Leitfaden_DIN_EN_12464-1.pdf'},
    asr: {id:'ASR A3.4:2023 (DE)', url:asr}, isco: {id:'CZ-ISCO · ČSÚ · 1. 2. 2026', url:isco}
  };
  const panelTexts = {
    cs: {norms:'Podle jakých norem', normsShort:'Porovnání: ČSN EN 12464-1 · NV 361/2007 Sb.',
      normBasis:'Luxy: fyzikální model CIE. Tabulka: zveřejněné výtahy EN; kancelář a kreslení mají doplňkový německý podklad ASR/DGUV.',
      lawBasis:'§ 45(3): prostor s vyhovujícím denním světlem ≥ 200 lx, U₀ ≥ 0,4, pokud norma nepožaduje více. § 45(7), případy odst. 5: ≥ 300 lx, U₀ ≥ 0,4 a navýšení normových hodnot nejméně o stupeň. Výpočet bez denního světla neurčuje právní režim prostoru.',
      maintainedBasis:'Požadavky jsou udržované hodnoty. Bez určené údržby ukazujeme počáteční stav. České předpisy se překladem nestávají slovenskými.',
      tasksShort:'Činnosti · orientační porovnání', moreTasks:'Další obory a povolání', taskDetails:'Požadavky, zdroje a CZ-ISCO',
      checkLegend:'✓ průměr + rovnoměrnost v síti. ✗ některý práh nedosažen. Není to povolení práce.',
      highest:'Nejvyšší dosažený práh', noneReached:'Žádný dosažený práh s doloženým Ra.', threshold:'Práh průměru',
      mappingNote:'Přiřazení CZ-ISCO je orientační. Číselník luxy neurčuje.', source:'Zdroj požadavku', glare:'Oslnění neposouzeno',
      shortCaveat:'Orientační výpočet, ne měření. Bez denního světla, stínů a odrazů; odrazivost není určena.',
      workplane:'Rovina desky nad podlahou', close:'Zavřít panel', resultTitle:'Tato konfigurace',
      colourRelevance:'4000 K činnost samo nepotvrzuje. Ra > 80 dokládá požadavek Ra ≥ 80; Ra ≥ 90 pro barevnou kontrolu není doloženo.',
      deReference:'Doplňkový podklad DE', technicalMore:'Další údaje LED'},
    sk: {norms:'Podľa akých noriem', normsShort:'Porovnanie: ČSN EN 12464-1 · NV ČR 361/2007 Sb.',
      normBasis:'Luxy: fyzikálny model CIE. Tabuľka: zverejnené výňatky EN; kancelária a kreslenie majú doplnkový nemecký podklad ASR/DGUV.',
      lawBasis:'§ 45(3): priestor s vyhovujúcim denným svetlom ≥ 200 lx, U₀ ≥ 0,4, ak norma nepožaduje viac. § 45(7), prípady ods. 5: ≥ 300 lx, U₀ ≥ 0,4 a zvýšenie normových hodnôt najmenej o stupeň. Výpočet bez denného svetla neurčuje právny režim priestoru.',
      maintainedBasis:'Požiadavky sú udržiavané hodnoty. Bez určenej údržby ukazujeme počiatočný stav. Preklad českých predpisov nenahrádza slovenské predpisy.',
      tasksShort:'Činnosti · orientačné porovnanie', moreTasks:'Ďalšie odbory a povolania', taskDetails:'Požiadavky, zdroje a CZ-ISCO',
      checkLegend:'✓ priemer + rovnomernosť v sieti. ✗ niektorý prah nedosiahnutý. Nie je to povolenie práce.',
      highest:'Najvyšší dosiahnutý prah', noneReached:'Žiadny dosiahnutý prah s doloženým Ra.', threshold:'Prah priemeru',
      mappingNote:'Priradenie CZ-ISCO je orientačné. Číselník luxy neurčuje.', source:'Zdroj požiadavky', glare:'Oslnenie neposúdené',
      shortCaveat:'Orientačný výpočet, nie meranie. Bez denného svetla, tieňov a odrazov; odrazivosť nie je určená.',
      workplane:'Rovina dosky nad podlahou', close:'Zavrieť panel', resultTitle:'Táto konfigurácia',
      colourRelevance:'4000 K činnosť samo nepotvrdzuje. Ra > 80 dokladá požiadavku Ra ≥ 80; Ra ≥ 90 pre farebnú kontrolu nie je doložené.',
      deReference:'Doplnkový podklad DE', technicalMore:'Ďalšie údaje LED'},
    en: {norms:'Standards used', normsShort:'Comparison: ČSN EN 12464-1 · Czech Regulation 361/2007',
      normBasis:'Lux: a CIE physical model. Tables: published EN extracts; office and drawing tasks use supplementary German ASR/DGUV sources.',
      lawBasis:'Section 45(3): space with adequate daylight ≥ 200 lx, U₀ ≥ 0.4, unless the standard requires more. Section 45(7), cases under paragraph 5: ≥ 300 lx, U₀ ≥ 0.4 and at least one step higher standard values. Excluding daylight from this calculation does not determine the legal regime of the space.',
      maintainedBasis:'Requirements are maintained values. Without a defined maintenance factor we show the initial state. Translations retain the Czech jurisdiction.',
      tasksShort:'Tasks · indicative comparison', moreTasks:'More trades and occupations', taskDetails:'Requirements, sources and CZ-ISCO',
      checkLegend:'✓ average + grid uniformity. ✗ a threshold is missed. This does not authorise work.',
      highest:'Highest reached threshold', noneReached:'No reached threshold with documented Ra.', threshold:'Average threshold',
      mappingNote:'CZ-ISCO mapping is indicative. The classification specifies no lux values.', source:'Requirement source', glare:'Glare not assessed',
      shortCaveat:'Indicative calculation, not a measurement. No daylight, shadows or reflections; reflectance is unspecified.',
      workplane:'Worktop plane above floor', close:'Close panel', resultTitle:'This configuration',
      colourRelevance:'4000 K alone does not establish suitability. Ra > 80 documents Ra ≥ 80; Ra ≥ 90 for colour inspection is not documented.',
      deReference:'Supplementary DE reference', technicalMore:'More LED specifications'}
  };
  for (const lang of ['cs','sk','en']) Object.assign(data.texts[lang], panelTexts[lang]);
  // Panel v3: pouze nové vysvětlení; číselník a zdroje zůstávají z v2.
  const clearPanelTexts = {
    cs: {
      verdictLead: 'Při tomto osvětlení:', canDo: '✓ Lze dělat', cannotDo: '✗ Nelze dělat',
      canCount: (yes, total) => '✓ Lze dělat ' + yes + ' z ' + total + ' činností.',
      cannotCount: no => '✗ Nelze dělat: ' + no + '.',
      comparisonScope: 'Orientační porovnání světla a doloženého podání barev (Ra), ne povolení práce.',
      uniformityHelp: 'Rovnoměrnost = minimum / průměr: 1 znamená stejně světla všude, nižší číslo tmavší místa.',
      required: 'Požadováno', achieved: 'Máte', averageWord: 'průměr', uniformityWord: 'rovnoměrnost',
      noPassing: 'Zatím žádná činnost. Důvody jsou ve skupině níže.', allPassing: 'Všechny uvedené činnosti vyhovují tomuto porovnání.',
      okayReason: 'Průměr, rozložení světla i doložené podání barev vyhovují tomuto porovnání.',
      averageOkay: 'Průměr světla stačí.',
      lowReason: (have, need) => 'Průměr je ' + have + ' lx, potřeba alespoň ' + need + ' lx — světla je málo.',
      unevenReason: (have, need) => 'Rovnoměrnost je ' + have + ', potřeba alespoň ' + need + ' — některá místa na ploše mají příliš málo světla.',
      unknownUniformityReason: 'Požadavek na rozložení světla chybí, proto vhodnost nelze potvrdit.',
      missingUniformityReason: 'Rovnoměrnost nelze určit, protože plocha nemá vypočtené světlo.',
      colourReason: (have, need) => 'Podání barev ' + have + ' nedokládá požadovaných alespoň Ra ' + need + ' — správné rozlišení barev nelze potvrdit.',
      missingRa: 'Ra není doloženo pro všechna aktivní světla', unknownRa: 'požadavek Ra neuveden',
      cannotConfirm: '✗ Nelze potvrdit', helpTitle: 'Co by pomohlo',
      layoutHelp: (need, have) => 'Je potřeba osvětlit tmavší místa: při stejném průměru by minimum muselo být alespoň ' + need + ' lx (teď ' + have + ' lx). Samotné stejné zesílení všech světel rovnoměrnost nezmění.',
      powerHelp: (power, mean, uniformity) => 'Přepnutí aktivních světel na ' + power + ' v tomto modelu dává průměr ' + mean + ' lx a rovnoměrnost ' + uniformity + '. Počítáno ve stejných polohách.',
      morePrecision: 'Rozhoduje nezaokrouhlená hodnota.', tasksShort: 'Činnosti při tomto osvětlení'
    },
    sk: {
      verdictLead: 'Pri tomto osvetlení:', canDo: '✓ Možno robiť', cannotDo: '✗ Nemožno robiť',
      canCount: (yes, total) => '✓ Možno robiť ' + yes + ' z ' + total + ' činností.',
      cannotCount: no => '✗ Nemožno robiť: ' + no + '.',
      comparisonScope: 'Orientačné porovnanie svetla a doloženého podania farieb (Ra), nie povolenie práce.',
      uniformityHelp: 'Rovnomernosť = minimum / priemer: 1 znamená rovnako svetla všade, nižšie číslo tmavšie miesta.',
      required: 'Požadované', achieved: 'Máte', averageWord: 'priemer', uniformityWord: 'rovnomernosť',
      noPassing: 'Zatiaľ žiadna činnosť. Dôvody sú v skupine nižšie.', allPassing: 'Všetky uvedené činnosti vyhovujú tomuto porovnaniu.',
      okayReason: 'Priemer, rozloženie svetla aj doložené podanie farieb vyhovujú tomuto porovnaniu.',
      averageOkay: 'Priemer svetla stačí.',
      lowReason: (have, need) => 'Priemer je ' + have + ' lx, treba aspoň ' + need + ' lx — svetla je málo.',
      unevenReason: (have, need) => 'Rovnomernosť je ' + have + ', treba aspoň ' + need + ' — niektoré miesta na ploche majú príliš málo svetla.',
      unknownUniformityReason: 'Požiadavka na rozloženie svetla chýba, preto vhodnosť nemožno potvrdiť.',
      missingUniformityReason: 'Rovnomernosť nemožno určiť, pretože plocha nemá vypočítané svetlo.',
      colourReason: (have, need) => 'Podanie farieb ' + have + ' nedokladá požadovaných aspoň Ra ' + need + ' — správne rozlíšenie farieb nemožno potvrdiť.',
      missingRa: 'Ra nie je doložené pre všetky aktívne svetlá', unknownRa: 'požiadavka Ra neuvedená',
      cannotConfirm: '✗ Nemožno potvrdiť', helpTitle: 'Čo by pomohlo',
      layoutHelp: (need, have) => 'Treba osvetliť tmavšie miesta: pri rovnakom priemere by minimum muselo byť aspoň ' + need + ' lx (teraz ' + have + ' lx). Samotné rovnaké zosilnenie všetkých svetiel rovnomernosť nezmení.',
      powerHelp: (power, mean, uniformity) => 'Prepnutie aktívnych svetiel na ' + power + ' v tomto modeli dáva priemer ' + mean + ' lx a rovnomernosť ' + uniformity + '. Počítané v rovnakých polohách.',
      morePrecision: 'Rozhoduje nezaokrúhlená hodnota.', tasksShort: 'Činnosti pri tomto osvetlení'
    },
    en: {
      verdictLead: 'With this lighting:', canDo: '✓ Can do', cannotDo: '✗ Cannot do',
      canCount: (yes, total) => '✓ Can do ' + yes + ' of ' + total + ' tasks.',
      cannotCount: no => '✗ Cannot do: ' + no + '.',
      comparisonScope: 'Indicative comparison of light and documented colour rendering (Ra), not authorisation to work.',
      uniformityHelp: 'Uniformity = minimum / average: 1 means equal light everywhere; a lower number means darker areas.',
      required: 'Required', achieved: 'You have', averageWord: 'average', uniformityWord: 'uniformity',
      noPassing: 'No tasks yet. The reasons are in the group below.', allPassing: 'All listed tasks pass this comparison.',
      okayReason: 'Average light, its distribution and documented colour rendering pass this comparison.',
      averageOkay: 'The average light is sufficient.',
      lowReason: (have, need) => 'Average light is ' + have + ' lx; at least ' + need + ' lx is required — there is too little light.',
      unevenReason: (have, need) => 'Uniformity is ' + have + '; at least ' + need + ' is required — some areas have too little light.',
      unknownUniformityReason: 'The light distribution requirement is missing, so suitability cannot be confirmed.',
      missingUniformityReason: 'Uniformity cannot be determined because the surface has no calculated light.',
      colourReason: (have, need) => 'Colour rendering ' + have + ' does not document the required Ra of at least ' + need + ' — accurate colour distinction cannot be confirmed.',
      missingRa: 'Ra is not documented for all active lights', unknownRa: 'Ra requirement unspecified',
      cannotConfirm: '✗ Cannot confirm', helpTitle: 'What would help',
      layoutHelp: (need, have) => 'Darker areas need more light: at the same average, the minimum would need to be at least ' + need + ' lx (currently ' + have + ' lx). Increasing all lights equally does not change uniformity.',
      powerHelp: (power, mean, uniformity) => 'Switching the active lights to ' + power + ' gives an average of ' + mean + ' lx and uniformity of ' + uniformity + ' in this model. Calculated at the same positions.',
      morePrecision: 'The unrounded value determines the result.', tasksShort: 'Tasks with this lighting'
    }
  };
  for (const language of ['cs', 'sk', 'en']) Object.assign(data.texts[language], clearPanelTexts[language]);
  data.selectLight = function (sku, modeId) {
    const entry = data.catalogue.find(l => l.sku === sku);
    if (!entry) throw new Error('Neznámý typ světla: ' + sku);
    const copy = JSON.parse(JSON.stringify(entry));
    const mode = copy.powerModes.find(m => m.id === (modeId === undefined ? copy.defaultModeId : modeId));
    if (!mode) throw new Error('Neznámý výkonový stupeň');
    Object.assign(copy, mode, {modeId: mode.id}); delete copy.id;
    return copy;
  };
  if (typeof module === 'object' && module.exports) module.exports = data;
  else root.LuxData = data;
})(typeof globalThis !== 'undefined' ? globalThis : this);
