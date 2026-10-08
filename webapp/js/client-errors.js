/**
 * JS error beacon (bot5, 2026-09-02, "kontrolni mechanismy" od Roberta
 * pres bot3, dil J) - posila nezachycene chyby na POST /api/client-errors
 * (bez auth, viz api/client_errors.py), admin je cte agregovane v
 * /api/admin/client-errors.
 *
 * Ochrana proti smycce/zahlceni: max MAX_REPORTS hlaseni za CELOU
 * zivotnost stranky (napr. chyba uvnitr requestAnimationFrame smycky by
 * jinak poslala stovky hlaseni za sekundu - zivy priklad nalezen behem
 * QA (E): scene.html refreshMagnetReachSpheres() haze chybu KAZDY snimek).
 * Chyby z tohoto souboru sameho se nikdy nehlasi (bylo by to kruhove).
 */
(function () {
  "use strict";
  var MAX_REPORTS = 10;
  var ENDPOINT = "/api/client-errors";
  var sent = 0;
  var SELF_MARK = "client-errors.js";

  function isFromSelf(source) {
    return typeof source === "string" && source.indexOf(SELF_MARK) !== -1;
  }

  function report(payload) {
    if (sent >= MAX_REPORTS) return;
    if (isFromSelf(payload.source) || isFromSelf(payload.stack)) return;
    sent++;
    try {
      payload.url = location.href;
      payload.ua = navigator.userAgent;
      payload.ts = Date.now();
      var body = JSON.stringify(payload);
      if (navigator.sendBeacon) {
        navigator.sendBeacon(ENDPOINT, new Blob([body], { type: "application/json" }));
      } else if (window.fetch) {
        fetch(ENDPOINT, { method: "POST", body: body, headers: { "Content-Type": "application/json" }, keepalive: true }).catch(function () {});
      }
    } catch (e) {
      // Beacon sam nikdy nesmi hodit dal - byla by to presne ta smycka,
      // ktere se snazime predejit.
    }
  }

  window.addEventListener("error", function (e) {
    var t = e.target;
    if (t && t !== window && t.tagName && (t.tagName === "SCRIPT" || t.tagName === "IMG" || t.tagName === "LINK")) {
      // Selhani nacteni zdroje (capture-only udalost, nebublá) - jiny
      // tvar nez chyba skriptu, ale stejny endpoint/tabulka.
      var url = t.src || t.href || "";
      report({ message: "Selhalo načtení zdroje (" + t.tagName.toLowerCase() + ")", source: url, line: null, col: null, stack: null });
      return;
    }
    report({
      message: e.message || "(bez zprávy)",
      source: e.filename || "",
      line: typeof e.lineno === "number" ? e.lineno : null,
      col: typeof e.colno === "number" ? e.colno : null,
      stack: e.error && e.error.stack ? String(e.error.stack) : null,
    });
  }, true);

  window.addEventListener("unhandledrejection", function (e) {
    var reason = e.reason;
    var msg = reason && reason.message ? reason.message : String(reason);
    report({
      message: "Unhandled promise rejection: " + msg,
      source: "",
      line: null,
      col: null,
      stack: reason && reason.stack ? String(reason.stack) : null,
    });
  });
})();
