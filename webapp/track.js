/*
 * Sdileny page-view tracking pro CELY verejny web (Robert pres bot3,
 * 2026-08-22: "totez nasadit na vandrawee.cz" - stejny princip jako
 * geo-tracking na /opt/toscanaccio). Kazda stranka nema vlastni
 * sdileny JS soubor, tenhle se proto pripoji zvlast
 * (<script src="/track.js" defer>) na kazdou verejnou stranku, misto
 * duplikovani stejneho kodu po strankach.
 *
 * ANONYMNI/agregovany tracking - zadna syrova IP se nikam neposila
 * odsud (poloha se pocita az na serveru z IP requestu, viz
 * api/geoip.py). Zadne cookies/localStorage identifikatory - dedup
 * unikatnich navstevniku resi server (ip_hash).
 */
(function () {
  "use strict";

  var PAGE_TYPE_BY_PATH = [
    [/^\/(index\.html)?$/, "domov"],
    [/^\/(category\.html|kategorie\/)/, "kategorie"],
    [/^\/(product\.html|produkt\/)/, "produkt"],
    [/^\/(blok\.html|blok\/|panel\/)/, "blok"],
    [/^\/nabidka-online\.html/, "nabidka_online"],
    [/^\/poptavka-stul\.html/, "poptavka_stul"],
    [/^\/realizace\.html/, "realizace"],
    [/^\/remeslo/, "remeslo"],
  ];

  function detectPageType(pathname) {
    for (var i = 0; i < PAGE_TYPE_BY_PATH.length; i++) {
      if (PAGE_TYPE_BY_PATH[i][0].test(pathname)) return PAGE_TYPE_BY_PATH[i][1];
    }
    return "jine";
  }

  var trackedPath = location.pathname + location.search;
  var trackedPageType = detectPageType(location.pathname);

  function trackPageView() {
    fetch("/api/track/page-view", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path: trackedPath, page_type: trackedPageType }),
      keepalive: true,
    }).catch(function () { /* tise ignorovat - tracking nesmi rusit stranku */ });
  }

  // Straveny cas na strance (Robert pres bot3, 2026-08-22: "stravany
  // cas (dwell time)... pridej dwell-tracking i do obecneho page_views
  // stejnym vzorem jako u receptu [na toscanacciu]") - pocita se od
  // nacteni stranky, pauzuje se pri prepnuti do jine zalozky
  // (visibilitychange), odesila navigator.sendBeacon() (funguje i pri
  // zavirani zalozky/odchodu ze stranky, na rozdil od beznehofetch,
  // ktery by prohlizec mohl prerusit driv, nez stihne odejit).
  var dwellStart = Date.now();
  var dwellAccum = 0;
  var dwellPaused = false;

  function flushDwell() {
    var ms = dwellAccum;
    if (!dwellPaused) ms += Date.now() - dwellStart;
    dwellAccum = 0;
    dwellStart = Date.now();
    if (ms <= 0) return;
    navigator.sendBeacon("/api/track/page-dwell", new Blob([JSON.stringify({
      path: trackedPath, page_type: trackedPageType, ms: Math.round(ms),
    })], { type: "application/json" }));
  }

  document.addEventListener("visibilitychange", function () {
    if (document.hidden) {
      flushDwell();
      dwellPaused = true;
    } else {
      dwellPaused = false;
      dwellStart = Date.now();
    }
  });
  window.addEventListener("pagehide", flushDwell);

  // Volano z product.html/category.html (uz maji productId/catId v JS) -
  // geo-breakdown NAVIC k jednotlivemu produktu/kategorii, viz
  // POST /api/track/product-view a /api/track/category-view.
  window.trackEntityView = function (entityType, entityId) {
    if (!entityId && entityId !== 0) return;
    var url = entityType === "product" ? "/api/track/product-view" : "/api/track/category-view";
    var payload = entityType === "product" ? { product_id: entityId } : { category_id: entityId };
    fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      keepalive: true,
    }).catch(function () {});
  };

  trackPageView();
})();
