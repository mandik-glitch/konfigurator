/*
 * oploceni-host.js - STRANKA GENERATORU 06 "OCHRANNY KRYT A OPLOCENI" pro zamestnance nad SPOLECNYM modulem voleb (js/product-configurator.js) a mrizkou oken (js/pdc-layout.js) - bot8, 2026-10-08.
 *
 * Robert 2026-10-08: "udelej generator ochranneho oploceni a krytovani stroju z profilu 40x40", "nahrat vsechno hned". Stejny princip jako Generator stolu (js/stul-host.js): ovladani se NEDUPLIKUJE,
 * stranka nema vlastni jezdce, meze ani texty - vse dela modul podle schematu ze serveru (verejne trasy /api/shop/*, recept `oploceni_kryt`, api/oploceni_shop.py). Proc nova tenka stranka a ne
 * obecny hostitel: stul-host.js je z 90 % veci stolu (systemy 30-45, pravidla stolu, vychozi konfigurace, Vlozit do Sceny, Do online nabidky, luxy); obecny hostitel by znamenal zasah do
 * souboru, ktery spravuji jini boti a ktery ma 5 stranek a sadu testu. Tahle stranka je minimalni (3D, volby, cena, kusovnik s cenami, odkaz na kartu) a pozdeji z ni jde obecny hostitel
 * odvodit (jediny produktovy kus je RECEPT a skupiny voleb v buildLayout).
 *
 * Co stranka umi: prihlaseni zamestnance (jinak nic), id karty produktu z GET /api/shop/configurator/recepty/oploceni_kryt (stranka nema pevne ID), mrizku oken (3D, cena, vyroba a odkazy, volby po
 * skupinach, kusovnik s cenami z resp.staff - server ho da jen zamestnanci na `staff: true`), hash v URL (#w=1500&front=door&...: verejne nazvy slotu; odkaz na konfiguraci).
 * ?public=1&id=<id karty> = VEREJNA varianta: bez prihlaseni, bez `staff` v resolve a bez zamestnaneckych oken (nahled toho, co uvidi zakaznik); ?lang=cs|en|sk = jazyk textu voleb ze serveru.
 * Bez tlacitek "Do online nabidky", "Vlozit do Sceny" a okna "Vzhled" (v1).
 */
(function () {
  "use strict";
  var RECEPT = "oploceni_kryt";
  var Q = location.search;
  var PUBLIC = /[?&]public=1(?:&|$)/.test(Q);
  var ID_PARAM = (/[?&]id=(\d{1,9})(?:&|$)/.exec(Q) || [])[1] || null;
  var LANG = (/[?&]lang=(cs|en|sk)(?:&|$)/.exec(Q) || [])[1] || "cs";
  var LABELS = {
    title: "Vaše konfigurace", reset: "Výchozí hodnoty", price: "Cena", noVat: "bez DPH", withVat: "s DPH", pending: "Počítám…", code: "Kód konfigurace", summary: "Souhrn",
    unavailable: "Tohle teď nejde zapnout.", errLoad: "Konfigurátor se nepodařilo načíst. Zkus to prosím znovu.", errNet: "Spojení selhalo. Zkus to prosím znovu.", retry: "Zkusit znovu",
    rateLimit: "Moc změn najednou, chvilku počkej…", rulesChanged: "Pravidla se změnila, načítám nové volby.", modelPrep: "Připravuji model…", modelErr: "Model se nepodařilo načíst, cena platí.",
    noWebgl: "Tenhle prohlížeč nepodporuje 3D náhled, volby a cena fungují.", viewerErr: "3D náhled se nepodařilo načíst, volby a cena fungují.", invalid: "Vyber platnou konfiguraci.",
    yes: "ano", no: "ne", auto: "automaticky", lock: "Klepnutím ovládáš 3D pohled", allowed: "Povoleno od {min} do {max} {unit}"
  };
  var V3D_CSS = "/css/v3d.css?v=c76cbe7292";
  var S = { ctl: null, staff: null, bomRows: [], bomOpen: {}, sel: null, L: null, productId: null, card: null };
  if (/[?&]debug=1/.test(Q)) window.__pdcDebug = true;               // testy: modul vystavi window.__pdcState

  function $(id) { return document.getElementById(id); }
  function el(tag, attrs, text) {
    var e = document.createElement(tag);
    if (attrs) Object.keys(attrs).forEach(function (k) { e.setAttribute(k, attrs[k]); });
    if (text != null) e.textContent = text;
    return e;
  }
  function div(cls, id) { var d = el("div", cls ? { "class": cls } : null); if (id) d.id = id; return d; }
  function money(v) { return Number(v).toLocaleString("cs-CZ", { maximumFractionDigits: 0 }) + " Kč"; }
  function qtyText(x) { return x == null ? "" : String(Math.round(x * 100) / 100).replace(".", ","); }

  // ---------------------------------------------------------------- hash <-> vyber (verejne nazvy slotu)
  function parseHash(h) {
    var out = {}, raw = String(h || "").replace(/^#/, "");
    if (!raw) return out;
    raw.split("&").forEach(function (kv) {
      var i = kv.indexOf("="); if (i < 1) return;
      var k = decodeURIComponent(kv.slice(0, i)), v = decodeURIComponent(kv.slice(i + 1));
      if (!/^[a-z_]{1,20}$/.test(k)) return;
      if (k === "feet") { out.feet = v === "1" || v === "true"; return; }
      if (k === "door_h") { out.door_h = (v === "" || v === "auto") ? null : Number(v); return; }          // prazdne = automaticky
      out[k] = (v !== "" && isFinite(Number(v))) ? Number(v) : v;
    });
    return out;
  }
  function zapisHash(sel) {
    var q = [];
    Object.keys(sel || {}).sort().forEach(function (k) {
      var v = sel[k]; if (v == null || typeof v === "object") return;
      q.push(encodeURIComponent(k) + "=" + encodeURIComponent(typeof v === "boolean" ? (v ? 1 : 0) : v));
    });
    try { history.replaceState(null, "", location.pathname + location.search + "#" + q.join("&")); } catch (e) { /* ignoruj */ }
  }

  // ---------------------------------------------------------------- zamestnanecky blok (z resp.staff)
  function renderBom(k) {
    var body = $("bomBody");
    S.bomRows = [];
    body.textContent = "";
    if (!k) { body.appendChild(el("div", { "class": "note" }, "Kusovník se nepodařilo spočítat.")); return; }
    var tbl = el("table"), head = el("tr");
    ["Položka", "Rozměr", "Ks", "Cena/ks", "Celkem"].forEach(function (h) { head.appendChild(el("th", null, h)); });
    tbl.appendChild(el("thead")).appendChild(head);
    var tb = el("tbody");
    function sec(text) { var tr = el("tr", { "class": "sec" }); var td = el("td", null, text); td.colSpan = 5; tr.appendChild(td); tb.appendChild(tr); S.bomRows.push([text]); }
    function row(cells, cls) {
      var tr = el("tr", cls ? { "class": cls } : null);
      cells.forEach(function (c, i) { var td = el("td", null, c); if (i === 0 && cells.length < 5) td.colSpan = 4; tr.appendChild(td); });
      tb.appendChild(tr);
    }
    function line(x, cls, hid) {
      var cells = [x.nazev, x.rozmer || "", qtyText(x.mnozstvi), x.cena_ks == null ? "" : money(x.cena_ks), money(x.celkem)];
      row(cells, cls); S.bomRows.push(cells);
      if (hid) tb.lastChild.hidden = true;
    }
    // hlinikove profily: kazdy druh profilu je JEDEN radek (soucet kusu a ceny), rozbalenim se ukazou delky (jako Generator stolu)
    function jeProfil(x) { return /^Profil /.test(x.nazev || "") && /\bmm$/.test(x.rozmer || ""); }
    function skupinaProfilu(nazev, dily) {
      var ks = 0, celkem = 0;
      dily.forEach(function (d) { ks += d.mnozstvi || 0; celkem += d.celkem || 0; });
      var open = !!S.bomOpen[nazev], tr = el("tr", { "class": "grp" });
      var btn = el("button", { type: "button", "class": "bom-tog", "aria-expanded": open ? "true" : "false", title: "Rozbalit / sbalit délky" });
      btn.appendChild(el("span", { "class": "bom-chev", "aria-hidden": "true" }, open ? "▾" : "▸")); btn.appendChild(document.createTextNode(nazev));
      var td0 = el("td"); td0.appendChild(btn); tr.appendChild(td0);
      [dily.length + (dily.length === 1 ? " délka" : dily.length < 5 ? " délky" : " délek"), qtyText(ks), "", money(celkem)].forEach(function (c) { tr.appendChild(el("td", null, c)); });
      tb.appendChild(tr);
      var det = dily.slice().sort(function (a, b) { return (parseFloat(String(b.rozmer).replace(",", ".")) || 0) - (parseFloat(String(a.rozmer).replace(",", ".")) || 0); });
      var radky = det.map(function (d) { line(d, "det", !open); return tb.lastChild; });
      btn.addEventListener("click", function () {
        open = !open; S.bomOpen[nazev] = open; btn.setAttribute("aria-expanded", open ? "true" : "false"); btn.firstChild.textContent = open ? "▾" : "▸";
        radky.forEach(function (r) { r.hidden = !open; });
      });
    }
    sec("Materiál a díly");
    var skupiny = {}, poradi = [];
    (k.radky || []).forEach(function (x) {
      if (!jeProfil(x)) { poradi.push({ x: x }); return; }
      if (!skupiny[x.nazev]) { skupiny[x.nazev] = []; poradi.push({ grp: x.nazev }); }
      skupiny[x.nazev].push(x);
    });
    poradi.forEach(function (p) { if (p.grp) skupinaProfilu(p.grp, skupiny[p.grp]); else line(p.x); });
    sec("Práce, spoje a balné"); (k.prace || []).forEach(function (x) { line(x); });                   // POZOR: ne forEach(line) - forEach by predal index a pole jako `cls`/`hid`
    var c = k.celkem || {};
    [["Celkem bez DPH", c.bez_dph, "sum"], ["DPH " + c.sazba_dph + " %", c.dph, ""], ["Celkem s DPH", c.s_dph, "sum"]].forEach(function (x) {
      row([x[0], money(x[1])], x[2]); S.bomRows.push([x[0], "", "", "", money(x[1])]);
    });
    tbl.appendChild(tb); body.appendChild(tbl);
    var m = k.montaz || {};
    body.appendChild(el("div", { "class": "note" }, "Hmotnost " + String(k.hmotnost_kg).replace(".", ",") + " kg (výplně odhadem z plochy) · Montáž: " + (m.poznamka || "–") + " · ceny bez DPH v Kč"));
    (k.varovani || []).forEach(function (w) { body.appendChild(el("div", { "class": "note" }, "⚠ " + w)); });
  }

  function renderStaff(r) {
    var st = r && r.staff;
    S.staff = st || null;
    var W = S.L.wins;
    ["info", "bom"].forEach(function (k) { W[k].box.hidden = !st; });
    if (!st) return;
    renderBom(st.kusovnik);
    var pr = $("staffProblems");
    pr.textContent = "";
    (st.problemy || []).slice(0, 8).forEach(function (x) { pr.appendChild(el("div", null, "• " + (x.text || x.kod))); });
    var rz = st.rozmery || {};
    $("staffCode").textContent = "Kód konfigurace: " + (st.kod || "") + " · " + (st.pocet_spoju != null ? st.pocet_spoju + " spojů profilů" : "") + (st.dilu != null ? " · " + st.dilu + " dílů" : "")
      + (rz.sirka_mm ? " · obrys " + Math.round(rz.sirka_mm) + " × " + Math.round(rz.hloubka_mm) + " × " + Math.round(rz.vyska_mm) + " mm" : "");
  }

  function setPrice(price, st) {
    $("titleCode").textContent = (st && st.kod) || "…";
    if (!price) { $("priceNet").textContent = "–"; $("priceGross").textContent = ""; return; }
    $("priceNet").textContent = money(price.net);
    $("priceGross").textContent = price.gross != null ? money(price.gross) + " s DPH (" + price.vat_rate + " %)" : "";
  }

  // ---------------------------------------------------------------- rozlozeni: mrizka oken jako Generator stolu
  function skupinyDoOken(map, spodnadpisy) {
    var hosts = {};
    return function groupHost(g) {
      if (hosts[g.id]) return hosts[g.id];
      var w = map[g.id];
      if (!w) return null;
      w.box.hidden = false;
      if (spodnadpisy.indexOf(w) >= 0) {                                    // vic skupin v jednem okne: kazda ma podnadpis, sekce se schovava celá
        var sec = div("pdc-sekce"), sub = div();
        sec.appendChild(el("h3", { "class": "mw-win-sub" }, g.label || "")); sec.appendChild(sub); w.body.appendChild(sec);
        return (hosts[g.id] = { body: sub, box: sec });
      }
      if (!w.hlava) { var hd = w.box.firstChild.firstChild; if (hd && !hd.textContent) hd.textContent = g.label || ""; w.hlava = true; }
      return (hosts[g.id] = { body: w.body, box: w.box });
    };
  }

  function buildLayout() {
    var narrow = !!(window.matchMedia && window.matchMedia("(max-width: 899px)").matches);
    var L = window.PdcLayout.create({ narrow: narrow }), W = L.wins;
    S.L = L;
    var media = div("mw-pd-media", "stage"), panel = div(null, "host");
    var wStage = L.win("stage", "3D náhled"), wPrice = L.win("price", "Cena"), wInfo = L.win("info", "Výroba a odkazy", { hidden: true });
    var wDim = L.win("dim", "", { fold: true, mobileOpen: true, hidden: true }), wFrame = L.win("frame", "", { fold: true, mobileOpen: true, hidden: true }), wExtras = L.win("extras", "Výplň, dveře a příslušenství", { fold: true, hidden: true });
    var wFillAdv = L.win("adv", "Výplň po stranách", { fold: true, closed: true, hidden: true });
    var wBom = L.win("bom", "Kusovník s cenami (interní)", { fold: true, mobileOpen: true, hidden: true });
    var wSum = L.win("sum", "Shrnutí", { fold: true, hidden: true });
    var msg = div(null, "stageMsg"); msg.textContent = "Načítám 3D model…";
    wStage.body.appendChild(media); wStage.body.appendChild(msg);

    var priceBox = div("sh-price", "staffPrice");
    priceBox.appendChild(div("small")).textContent = "Cena bez DPH";
    var big = div("big", "priceNet"); big.textContent = "–"; priceBox.appendChild(big);
    priceBox.appendChild(div("small", "priceGross"));
    wPrice.body.appendChild(priceBox);
    wPrice.body.appendChild(div(null, "cardInfo"));

    wInfo.body.appendChild(div(null, "staffProblems"));
    wInfo.body.appendChild(div(null, "staffLinks"));
    var row = div("sh-btns"); row.appendChild(el("button", { type: "button", id: "copyBtn", "class": "sh-ghost" }, "Zkopírovat odkaz na tuto konfiguraci")); wInfo.body.appendChild(row);
    wInfo.body.appendChild(div(null, "staffCode"));

    wBom.body.appendChild(div(null, "bomBody"));
    var row3 = div("sh-btns"); row3.appendChild(el("button", { type: "button", id: "bomCopy", "class": "sh-ghost" }, "Zkopírovat tabulku")); wBom.body.appendChild(row3);

    var side = div("mw-col mw-col-side"), col3 = div("mw-col mw-col-3");
    side.appendChild(wPrice.box); side.appendChild(wInfo.box);
    col3.appendChild(wFillAdv.box); col3.appendChild(wSum.box);
    var cfgBar = div("mw-cfgbar"); cfgBar.appendChild(panel);
    [wStage.box, side, cfgBar, wDim.box, wFrame.box, wExtras.box, wBom.box, col3].forEach(function (n) { L.grid.appendChild(n); });
    $("shGrid").appendChild(L.grid);

    // skupiny voleb -> okna: Rozmery | Strany a strecha | Vyplne + Dvere + Prislusenstvi (jedno okno, kazda skupina ma podnadpis) | Vyplne po stranach (sklopne, ve 3. sloupci). Vlastni rozdelovac mista
    // L.groupHosts: podnadpis skupiny se schova spolu se skupinou (L.groupHosts ho nechava viset, kdyz ve skupine nic neni videt - napr. "Dvere" bez dveri)
    var groupHost = skupinyDoOken({ g_size: wDim, g_sides: wFrame, g_fill: wExtras, g_door: wExtras, g_extras: wExtras, g_fill_adv: wFillAdv }, [wExtras]);
    var sumHost = L.summaryHost(wSum, { all: function (n) { return "Celá konfigurace (" + n + ")"; }, less: "Méně" });
    return { media: media, panel: panel, groupHost: groupHost, sumHost: sumHost, reveal: L.reveal };
  }

  function start() {
    var lay = buildLayout();
    $("loginLink").setAttribute("href", "/login.html?next=" + encodeURIComponent(location.pathname + location.search + location.hash));
    $("copyBtn").addEventListener("click", function () {
      var url = location.href;
      if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(url).then(function () { $("staffCode").textContent = "Odkaz je zkopírovaný."; }, function () { $("staffCode").textContent = url; });
      else $("staffCode").textContent = url;
    });
    $("bomCopy").addEventListener("click", function () {
      var txt = S.bomRows.map(function (r) { return r.join("\t"); }).join("\n");
      if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(txt).then(function () { $("staffCode").textContent = "Kusovník je zkopírovaný (vlož do tabulky)."; });
    });
    if (PUBLIC) { $("navNote").textContent = "veřejná varianta (náhled)"; ["info", "bom"].forEach(function (k) { S.L.wins[k].box.hidden = true; }); }
    var najdiProdukt = PUBLIC
      ? Promise.resolve(ID_PARAM ? { status: 200, d: { product_id: Number(ID_PARAM), active: null } } : { status: 404, d: {} })
      : fetch("/api/auth/me", { credentials: "same-origin" }).then(function (r) { return r.ok ? r.json() : { user: null }; }).catch(function () { return { user: null }; }).then(function (me) {
          if (!me.user) return { status: 401, d: {} };
          return fetch("/api/shop/configurator/recepty/" + RECEPT, { credentials: "same-origin" }).then(function (r) { return r.json().catch(function () { return {}; }).then(function (d) { return { status: r.status, d: d }; }); })
            .catch(function () { return { status: 0, d: {} }; });
        });
    najdiProdukt.then(function (x) {
      if (x.status === 401) { $("login").style.display = "block"; $("stageMsg").textContent = "Pro zobrazení se přihlas."; $("shGrid").style.display = "none"; return; }
      if (x.status === 403) { $("stageMsg").textContent = "Na tuhle stránku nemáš oprávnění (jen zaměstnanci)."; return; }
      if (x.status !== 200 || !x.d.product_id) { $("stageMsg").textContent = "Generátor ochranného krytu a oplocení zatím není zapnutý (chybí karta produktu s receptem " + RECEPT + ")."; return; }
      S.productId = x.d.product_id; S.card = x.d;
      var ci = $("cardInfo");
      if (!PUBLIC) {
        ci.appendChild(document.createTextNode("Karta produktu #" + S.productId + (x.d.active ? " (aktivní) " : " (neaktivní) ")));
        ci.appendChild(el("a", { href: "/product.html?id=" + S.productId, target: "_blank", rel: "noopener" }, "otevřít kartu"));
      }
      var mobil = !!(window.matchMedia && window.matchMedia("(max-width: 700px)").matches);
      var ctx = {
        product: { id: S.productId, configurator: { available: true, default_view: "configurator" } },
        noTurntable: true, lang: LANG, labels: LANG === "cs" ? LABELS : undefined, initialSelection: parseHash(location.hash), resolveExtra: PUBLIC ? undefined : { staff: true },
        dom: { tabsBefore: null, visual: [], stageHost: lay.media, panelHost: lay.panel, groupHost: lay.groupHost, summaryHost: lay.sumHost, reveal: lay.reveal, dependsOn: {} },
        page: {
          setPrice: setPrice, setBuyState: function () {}, toast: function () {}, onActivate: function () {}, track: function () {},
          onResolved: function (r) { $("stageMsg").style.display = "none"; if (!PUBLIC) renderStaff(r); },
          onSelection: function (sel) { S.sel = sel; zapisHash(sel); },
          onModel: function () {}
        },
        assets: { cssNow: ["/css/product-configurator.css?v=55f3678f8f"], css: [V3D_CSS], viewer: "/js/v3d/viewer3d.js?v=c0ba0ef528" },
        viewerOpts: mobil ? { hudDock: "top", hudKoty: true, dims: 0 } : { hudDock: "top", hudKoty: true }
      };
      window.PdConfigurator.init(ctx).then(function (ctl) {
        S.ctl = ctl;
        if (!ctl) $("stageMsg").textContent = "Generátor se nepodařilo spustit.";
      });
    });
  }
  window.OploceniHost = { state: S, parseHash: parseHash, recept: RECEPT };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start); else start();
})();
