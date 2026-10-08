/* i18n.js - preklad textu stranek podle slovniku (EN / IT). Na ceskem hostu (<html lang="cs"> nebo bez slovniku) NEDELA NIC. bot16, 2026-10-08; viz docs/web_jazyky/README.md.
 *
 * Slovnik (dodava server ve strance pred timto skriptem):
 *   window.__I18N = { lang: "en", exact: { "<normalizovana cestina>": "<preklad>", ... }, patterns: [ ["<normalizovana cestina s {0}>", "<preklad>"], ... ] }
 * Klic = norm(veta): mezery slozene na jednu, ciselne skupiny -> {n}, inline znacky uvnitr vety -> cislovane <1>..</1> (poradi vyskytu), <br> / prazdny prvek -> <2/>.
 * MUSI byt shodne s scripts/web_jazyk_ui_zdroj.py (norm + jednotka_inline); hlida test scripts/2026-10-08_web_jazyky_testy/test_i18n_js.js.
 *
 * Co se preklada: textove uzly a cele vety s inline znackami (<a>, <b>, <span> ... - puvodni prvky se jen presunou, takze zustanou jejich obsluhy udalosti),
 * atributy placeholder / title / alt / aria-label, value tlacitek, document.title, alert / confirm / prompt. Dynamicky pridany obsah se prelozi MutationObserverem
 * jeste pred vykreslenim. Veta bez prekladu zustane cesky (brana "vse nebo nic" pred indexaci hlida server + E2E test).
 * Verejne API: window.I18N = { lang, active, t(vetaCesky), norm(text), money(castka, mena), translateNode(uzel), apply() }
 */
(function (root) {
  "use strict";
  var doc = root.document;
  var LANG = ((doc.documentElement.getAttribute("lang") || "cs").toLowerCase().split("-")[0]);
  var DICT = root.__I18N || null;
  var API = root.I18N = { lang: LANG, active: false, t: function (s) { return s; }, norm: norm, money: money, translateNode: function () {}, apply: function () {} };

  var WS = /[\s   ]+/g;
  var NUM = /(^|[^\p{L}\p{N}_{])(\d+(?:[  ]\d{3})*(?:[.,]\d+)?)(?![\p{L}\p{N}_}])/gu;
  var NUM_ONE = /\d+(?:[  ]\d{3})*(?:[.,]\d+)?/;
  function norm(s) {
    return String(s).replace(WS, " ").trim().replace(NUM, function (m, pre) { return pre + "{n}"; });
  }
  function cisla(s) {            // ciselne skupiny puvodniho textu v poradi vyskytu (stejna pravidla jako norm)
    var out = [], t = String(s).replace(WS, " ").trim(), m;
    NUM.lastIndex = 0;
    while ((m = NUM.exec(t))) out.push(m[2]);
    return out;
  }
  function money(amount, currency, opts) {
    var d = DICT || {}, n = Number(amount);
    var frac = Number.isInteger(n) ? 0 : 2;          // cele castky bez haleru, jinak 2 desetinna mista
    try {
      return new Intl.NumberFormat(d.locale || (LANG === "cs" ? "cs-CZ" : LANG), Object.assign({ style: "currency", currency: currency || d.currency || "CZK", minimumFractionDigits: frac, maximumFractionDigits: 2 }, opts || {})).format(n);
    } catch (e) { return String(amount) + " " + (currency || ""); }
  }
  // Castky v ceskem zapisu ("12 345,50 Kč", po prekladu "12 345,50 EUR") -> mena a format jazykoveho hostu ("€12,345.50" / "12.345,50 €"). Server vraci na jazykovem hostu uz EUR
  // (pole se jmenuji dal *_czk), stranky je ale skladaji po cesku; tohle je jediny pruchod, ktery je predela (stranky se tim nemeni).
  var MONEY_RE = /(\d{1,3}(?:[ \u00a0]\d{3})+(?:,\d+)?|\d+(?:,\d+)?)\s*(?:Kč|CZK|EUR)(?![\p{L}])/gu;
  function fixMoney(s) {
    if (!DICT || typeof s !== "string" || !/Kč|CZK|EUR/.test(s)) return s;
    return s.replace(MONEY_RE, function (m, num) {
      var n = parseFloat(num.replace(/[ \u00a0]/g, "").replace(",", "."));
      return isFinite(n) ? money(n, DICT.currency) : m;
    });
  }

  if (!DICT || LANG === "cs" || DICT.lang !== LANG || !DICT.exact) return;
  API.active = true;

  // ---------- vzory s {0} {1} (promenna cast vety) ----------
  var VZORY = [];
  (DICT.patterns || []).forEach(function (p) {
    var cs = p[0], tr = p[1], re = "", poslPlace = 0, staticLen = 0, parts = cs.split(/(\{n\}|\{\d+\})/);
    parts.forEach(function (x) {
      if (x === "{n}") { re += "\\{n\\}"; staticLen += 3; }
      else if (/^\{\d+\}$/.test(x)) re += "([\\s\\S]*?)";
      else { re += x.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"); staticLen += x.length; }
    });
    VZORY.push({ re: new RegExp("^" + re + "$"), tr: tr, pref: (parts[0] || "").slice(0, 2), staticLen: staticLen, kinds: parts.filter(function (x) { return /^\{\d+\}$/.test(x); }) });
  });
  VZORY.sort(function (a, b) { return b.staticLen - a.staticLen; });

  function dosad(tr, cislaPuvodni, zachyceno) {       // 1) {k} -> zachycena cast vety (uz normalizovana), 2) vsechna {n} v poradi -> puvodni cisla
    var ni = 0;
    if (zachyceno) tr = tr.replace(/\{(\d+)\}/g, function (m, k) { return zachyceno[k] != null ? zachyceno[k] : m; });
    return tr.replace(/\{n\}/g, function (m) { return ni < cislaPuvodni.length ? cislaPuvodni[ni++] : m; });
  }
  // preklad jedne normalizovane vety (surovy text kvuli cislum); vraci preklad nebo null
  function prelozVetu(key, surovy) {
    var tr = Object.prototype.hasOwnProperty.call(DICT.exact, key) ? DICT.exact[key] : null;
    if (tr != null && tr !== "") return dosad(tr, cisla(surovy), null);
    for (var i = 0; i < VZORY.length; i++) {
      var v = VZORY[i];
      if (v.pref && key.indexOf(v.pref) !== 0) continue;
      var m = v.re.exec(key);
      if (!m) continue;
      var zach = {}, gi = 1;
      v.kinds.forEach(function (k) { zach[k.slice(1, -1)] = m[gi++]; });
      // zachycene casti jsou uz normalizovane ({n} uvnitr) - cisla se dosadi na konci podle puvodniho poradi
      return dosad(v.tr, cisla(surovy), zach);
    }
    return null;
  }
  API.t = function (s) {
    if (typeof s !== "string" || !/[A-Za-zÀ-ž]/.test(s)) return s;
    var lead = s.match(/^\s*/)[0], trail = s.match(/\s*$/)[0];
    var tr = prelozVetu(norm(s), s);
    return tr == null ? fixMoney(s) : lead + fixMoney(tr) + trail;
  };

  // ---------- jednotky: prvek = veta (text + inline znacky) ----------
  var INLINE = { A: 1, ABBR: 1, B: 1, STRONG: 1, I: 1, EM: 1, SMALL: 1, SPAN: 1, BR: 1, SUP: 1, SUB: 1, CODE: 1, MARK: 1, U: 1, KBD: 1, S: 1, DEL: 1, INS: 1, LABEL: 1, FONT: 1, IMG: 1, WBR: 1 };
  var VOID = { BR: 1, IMG: 1, WBR: 1, INPUT: 1, HR: 1, META: 1, LINK: 1, AREA: 1, BASE: 1, COL: 1, EMBED: 1, SOURCE: 1, TRACK: 1 };
  var PRESKOC = { SCRIPT: 1, STYLE: 1, NOSCRIPT: 1, SVG: 1, PATH: 1, DEFS: 1, TEXTAREA: 1, CODE_X: 1 };
  function tag(el) { return (el.tagName || "").toUpperCase(); }
  function vsechnoInline(el) {
    for (var c = el.firstChild; c; c = c.nextSibling) {
      if (c.nodeType === 1) { if (!INLINE[tag(c)] || !vsechnoInline(c)) return false; }
    }
    return true;
  }
  function maText(el) {
    for (var c = el.firstChild; c; c = c.nextSibling) if (c.nodeType === 3 && c.nodeValue.trim()) return true;
    return false;
  }
  // znacky uvnitr vety: soukrome znaky (U+E002 otevreni, U+E004 uzavreni, U+E005 samostatna, U+E003 konec, cislo znacky = znak U+E100+k), aby je norm() nezamenil za {n};
  // po norm() se prevedou na <k> .. </k> .. <k/> (shodne s scripts/web_jazyk_ui_zdroj.py)
  var Z_OD = String.fromCharCode(0xe002), Z_KON = String.fromCharCode(0xe004), Z_SAM = String.fromCharCode(0xe005), Z_X = String.fromCharCode(0xe003);
  var ZNACKA_G = new RegExp("[" + Z_OD + Z_KON + Z_SAM + "][" + String.fromCharCode(0xe100) + "-" + String.fromCharCode(0xe1ff) + "]" + Z_X, "g");
  var Z_TRI = "([" + String.fromCharCode(0xe100) + "-" + String.fromCharCode(0xe1ff) + "])" + Z_X;
  var RE_OD = new RegExp(Z_OD + Z_TRI, "g"), RE_KON = new RegExp(Z_KON + Z_TRI, "g"), RE_SAM = new RegExp(Z_SAM + Z_TRI, "g");
  function znak(k) { return String.fromCharCode(0xe100 + k); }
  function klicJednotky(surovy) {
    return norm(surovy)
      .replace(RE_OD, function (m, c) { return "<" + (c.charCodeAt(0) - 0xe100) + ">"; })
      .replace(RE_KON, function (m, c) { return "</" + (c.charCodeAt(0) - 0xe100) + ">"; })
      .replace(RE_SAM, function (m, c) { return "<" + (c.charCodeAt(0) - 0xe100) + "/>"; });
  }
  function jednotka(el) {          // {surovy, kids}: surovy text se znackami (viz vyse); kids = puvodni inline prvky v poradi cisel znacek
    var kids = [];
    function rek(uzly) {
      var s = "";
      for (var c = uzly.firstChild; c; c = c.nextSibling) {
        if (c.nodeType === 3) s += c.nodeValue;
        else if (c.nodeType === 1) {
          kids.push(c);
          var k = kids.length;
          if (VOID[tag(c)] || !c.firstChild) s += Z_SAM + znak(k) + Z_X;
          else s += Z_OD + znak(k) + Z_X + rek(c) + Z_KON + znak(k) + Z_X;
        }
      }
      return s;
    }
    return { surovy: rek(el), kids: kids };
  }
  function slozDom(el, kids, preklad) {
    var re = /<(\/?)(\d+)(\/?)>/g, pos = 0, m, stack = [], frag = doc.createDocumentFragment(), cur = frag;
    function text(t) { if (t) cur.appendChild(doc.createTextNode(t)); }
    // puvodni prvky se znovupouziji (zustanou jejich obsluhy udalosti); vnitrek se vyprazdni a naplni z prekladu
    kids.forEach(function (k) { if (!VOID[tag(k)]) while (k.firstChild) k.removeChild(k.firstChild); });
    while ((m = re.exec(preklad))) {
      text(preklad.slice(pos, m.index));
      pos = re.lastIndex;
      var n = parseInt(m[2], 10) - 1, node = kids[n];
      if (!node) continue;
      if (m[3] === "/") cur.appendChild(node);
      else if (m[1] === "/") { var t = stack.pop(); cur = t ? t : frag; }
      else { cur.appendChild(node); stack.push(cur); cur = node; }
    }
    text(preklad.slice(pos));
    while (el.firstChild) el.removeChild(el.firstChild);
    el.appendChild(frag);
  }

  function prelozJednotku(el) {
    var j = jednotka(el), key = klicJednotky(j.surovy);
    if (!/[A-Za-zÀ-ž]/.test(key.replace(/<\d+\/?>|<\/\d+>|\{n\}/g, ""))) return;
    var tr = prelozVetu(key, j.surovy.replace(ZNACKA_G, ""));
    if (tr == null) { prelozPotomky(el); return; }
    tr = fixMoney(tr);
    if (!j.kids.length) {
      var t = null, ostatni = [];
      for (var c = el.firstChild; c; c = c.nextSibling) { if (c.nodeType === 3) { if (!t) t = c; else ostatni.push(c); } }
      if (!t) return;
      var lead = t.nodeValue.match(/^\s*/)[0], trail = (ostatni.length ? ostatni[ostatni.length - 1] : t).nodeValue.match(/\s*$/)[0];
      t.nodeValue = lead + tr + trail;
      ostatni.forEach(function (o) { o.parentNode.removeChild(o); });
    } else slozDom(el, j.kids, tr);
  }
  function prelozTextovyUzel(t) {
    var s = t.nodeValue;
    if (!s || !/[A-Za-zÀ-ž]/.test(s)) { if (s && /Kč|CZK/.test(s)) { var m0 = fixMoney(s); if (m0 !== s) t.nodeValue = m0; } return; }
    var tr = prelozVetu(norm(s), s);
    if (tr == null) { var m1 = fixMoney(s); if (m1 !== s) t.nodeValue = m1; return; }
    t.nodeValue = s.match(/^\s*/)[0] + fixMoney(tr) + s.match(/\s*$/)[0];
  }
  // veta (prvek s inline znackami) bez slovnikoveho zaznamu - typicky drobeckova navigace s nazvem kategorie, ktery uz je preložený: prelozi se jednotlive casti (text, vnorene prvky)
  // a v kazdem textu se upravi castky; cela veta se pritom NErozklada, kdyz ji slovnik zna (viz vyse)
  function prelozPotomky(el) {
    var deti = Array.prototype.slice.call(el.childNodes);
    for (var i = 0; i < deti.length; i++) {
      var c = deti[i];
      if (c.nodeType === 3) prelozTextovyUzel(c);
      else if (c.nodeType === 1) { prelozAtributy(c); if (!PRESKOC[tag(c)]) { if (!VOID[tag(c)] && maText(c) && vsechnoInline(c)) prelozJednotku(c); else projdi(c); } }
    }
  }
  var ATRIBUTY = ["placeholder", "title", "alt", "aria-label"];
  function prelozAtributy(el) {
    ATRIBUTY.forEach(function (a) {
      var v = el.getAttribute && el.getAttribute(a);
      if (v && /[A-Za-zÀ-ž]/.test(v)) { var tr = API.t(v); if (tr !== v) el.setAttribute(a, tr); }
    });
    if (tag(el) === "INPUT") {
      var typ = (el.getAttribute("type") || "").toLowerCase();
      if ((typ === "button" || typ === "submit" || typ === "reset") && el.getAttribute("value")) { var v2 = el.getAttribute("value"), tr2 = API.t(v2); if (tr2 !== v2) el.setAttribute("value", tr2); }
    }
  }
  function projdi(el) {
    if (!el || el.nodeType !== 1) return;
    prelozAtributy(el);
    if (PRESKOC[tag(el)]) return;
    var t = tag(el);
    if (t !== "HTML" && t !== "BODY" && !VOID[t] && maText(el) && vsechnoInline(el)) {
      prelozJednotku(el);
      var pod = el.querySelectorAll("*");
      for (var i = 0; i < pod.length; i++) prelozAtributy(pod[i]);
      return;
    }
    var deti = Array.prototype.slice.call(el.childNodes);
    for (var k = 0; k < deti.length; k++) {
      var c = deti[k];
      if (c.nodeType === 3) { if (t !== "SCRIPT" && t !== "STYLE" && t !== "TEXTAREA") prelozTextovyUzel(c); }
      else if (c.nodeType === 1) projdi(c);
    }
  }
  API.unitKey = function (el) { return klicJednotky(jednotka(el).surovy); };            // diagnostika / testy
  API.translateNode = function (uzel) {
    if (!uzel) return;
    if (uzel.nodeType === 3) { uzel = uzel.parentNode; if (!uzel || uzel.nodeType !== 1) return; }
    if (uzel.nodeType === 1) {
      // prvek uvnitr inline vety se prekladuje spolecne s rodicem (nejvyssi prvek, ktery je veta)
      var r = uzel, p = uzel.parentNode;
      while (p && p.nodeType === 1 && tag(p) !== "BODY" && tag(p) !== "HTML" && INLINE[tag(r)] && maText(p) && vsechnoInline(p)) { r = p; p = p.parentNode; }
      projdi(r);
    }
  };

  var observer = null, fronta = [], planovano = false;
  function zpracujFrontu() {
    planovano = false;
    var q = fronta; fronta = [];
    if (observer) observer.disconnect();
    try { q.forEach(function (u) { if (u.isConnected !== false) API.translateNode(u); }); } finally { spustPozorovani(); }
  }
  function spustPozorovani() {
    if (!observer || !doc.documentElement) return;
    observer.observe(doc.documentElement, { childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: ATRIBUTY.concat(["value"]) });
  }
  function nastartujPozorovani() {
    if (typeof MutationObserver !== "function") return;
    observer = new MutationObserver(function (zmeny) {
      for (var i = 0; i < zmeny.length; i++) {
        var z = zmeny[i];
        if (z.type === "childList") { for (var k = 0; k < z.addedNodes.length; k++) fronta.push(z.addedNodes[k]); if (z.target && z.target.nodeType === 1) fronta.push(z.target); }
        else if (z.type === "characterData") fronta.push(z.target.parentNode || z.target);
        else fronta.push(z.target);
      }
      if (fronta.length) zpracujFrontu();                 // synchronne v mikrotasku - pred vykreslenim
    });
    spustPozorovani();
  }
  API.apply = function () {
    if (observer) observer.disconnect();
    try {
      var metas = doc.querySelectorAll('meta[name="description"], meta[property="og:title"], meta[property="og:description"], meta[name="twitter:title"], meta[name="twitter:description"]');
      for (var mi = 0; mi < metas.length; mi++) { var mc = metas[mi].getAttribute("content"); if (mc) { var mt = API.t(mc); if (mt !== mc) metas[mi].setAttribute("content", mt); } }
      projdi(doc.documentElement);
      if (doc.title) { var tt = API.t(doc.title); if (tt !== doc.title) doc.title = tt; }
    } finally { spustPozorovani(); }
    doc.documentElement.classList.remove("i18n-pending");
  };

  // alert / confirm / prompt
  ["alert", "confirm", "prompt"].forEach(function (n) {
    var puvodni = root[n];
    if (typeof puvodni !== "function") return;
    root[n] = function (m, d) { return puvodni.call(root, API.t(m), n === "prompt" && typeof d === "string" ? API.t(d) : d); };
  });

  nastartujPozorovani();
  if (doc.readyState === "loading") doc.addEventListener("DOMContentLoaded", API.apply);
  else API.apply();
  root.setTimeout(function () { doc.documentElement.classList.remove("i18n-pending"); }, 2500);    // pojistka: stranka se nikdy nezustane schovana
})(window);
