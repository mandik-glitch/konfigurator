// Balne v nove vytvorene nabidce (Robert 2026-10-01: "nevidim v nabidce cenu za montaz a balne"): scena (generateSceneOffer v
// webapp/js/scene/path-traced-preview.js) skladala kusovnik nabidky BEZ balneho, ackoli souhrn sceny pocita Cenu celkem vcetne
// balneho (app_settings.packaging_pct). Test bere SKUTECNOU funkci offerPackagingItem ze zdroje a overuje i jeji zapojeni pred soucet.
// Spusteni: node test_balne_nabidka.js    Kandidat pred nasazenim: PATH_TRACED_JS=/cesta/k/path-traced-preview.js node test_balne_nabidka.js
const vm = require('vm');
const fs = require('fs');
const path = require('path');
const { vytahniFunkci } = require('../2026-10-01_kotovani_testy/harness_koty');

const vysl = [];
const over = (nazev, podminka, detail) => {
  vysl.push(!!podminka);
  console.log((podminka ? 'OK   ' : 'FAIL ') + nazev + (podminka ? '' : '  -> ' + JSON.stringify(detail)));
};
const SRC = fs.readFileSync(process.env.PATH_TRACED_JS || path.join(__dirname, '../../webapp/js/scene/path-traced-preview.js'), 'utf8');

const maFunkci = SRC.includes('function offerPackagingItem(');
over('1 path-traced-preview.js ma funkci offerPackagingItem (balne do kusovniku nabidky)', maFunkci, null);
if (maFunkci) {
  const spust = (pricing, items) => {
    const ctx = vm.createContext({ Number, Math, PRICING_CONFIG: pricing });
    vm.runInContext(vytahniFunkci(SRC, 'offerPackagingItem'), ctx);
    return ctx.offerPackagingItem(items);
  };
  const radek = t => ({ name: 'x', dim: '-', qty: '1 ks', unit_price: t, total: t });
  const b = spust({ packaging_pct: 3 }, [radek(7000), radek(3000)]);
  over('2 3 % z 10 000 = 300 Kc, radek "Balne (3 %)" bez ceny za kus a bez dilu (jako Cena rezu / spoju)', b && b.name === 'Balné (3 %)' && b.total === 300 && b.unit_price === null && b.qty === '-' && b.dim === '-', b);
  const c = spust({ packaging_pct: 5 }, [radek(25552)]);
  over('3 overeny priklad ze sceny (sestava 334): 25 552 Kc subtotal, 5 % -> 1 278 Kc', c && c.total === 1278 && c.name === 'Balné (5 %)', c);
  over('4 procento 0 / chybi / neplatne -> zadne balne (null), nic nespadne', spust({ packaging_pct: 0 }, [radek(100)]) === null && spust({}, [radek(100)]) === null
       && spust(undefined, [radek(100)]) === null && spust({ packaging_pct: 'abc' }, [radek(100)]) === null, null);
  over('5 prazdny kusovnik / zaokrouhleni na 0 -> zadne balne', spust({ packaging_pct: 3 }, []) === null && spust({ packaging_pct: 3 }, undefined) === null && spust({ packaging_pct: 3 }, [radek(10)]) === null, null);
  over('6 desetinne procento (2,5 %) se zaokrouhli jako v souhrnu sceny: 1 000 -> 25 Kc', (spust({ packaging_pct: 2.5 }, [radek(1000)]) || {}).total === 25, spust({ packaging_pct: 2.5 }, [radek(1000)]));
}
// zapojeni: balne se pridava AZ po vsech radcich (rezy, pausal, spoje, prislusenstvi) a PRED souctem total_price
const iPrisl = SRC.indexOf('name: "Příslušenství (spojovací materiál)"');
const iBalne = SRC.indexOf('const balneItem = offerPackagingItem(items)');
const iSoucet = SRC.indexOf('const computedTotalPrice = items.reduce');
over('7 generateSceneOffer pridava balne po vsech ostatnich radcich a pred soucet total_price', iPrisl > 0 && iBalne > iPrisl && iSoucet > iBalne, { iPrisl, iBalne, iSoucet });

const ok = vysl.filter(Boolean).length;
console.log(`\nVYSLEDEK balne v nabidce: ${ok}/${vysl.length} OK`);
process.exit(ok === vysl.length ? 0 : 1);
