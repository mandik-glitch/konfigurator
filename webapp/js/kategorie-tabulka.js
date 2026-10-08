// Tabulka variant a štítky-filtry v kategorii e-shopu (bot16, 2026-10-07; Robert přes bot9: „chce to štítky pro rychlé filtrování podle délky… není příjemné koukat na desítky stejných
// obrázků… v tom se nedá orientovat“; schváleno „Ano, nasadit“ po náhledu /nahled-tabulka/dopravniky-324.html). Znovupoužitelný modul: KategorieTabulka.mount(kontejner, { categoryId }).
// Zdroj dat: živé API e-shopu GET /api/shop/products?category_id=<id>&page_size=100&include=specs (typ válečku, šířka = délka válečku, délka dopravníku, cena bez DPH); nic se nezapisuje.
// Použití: webapp/category.html pro kategorie vyjmenované v KATEGORIE_TABULKA (zatím #324 Válečkové dopravníky; další jen na Robertovo slovo). Texty češtiny kontroluje bot7.
// Pravidla: hodnoty z dat se do DOM dávají jen přes textContent (žádné innerHTML z dat); stav filtrů, řazení a zobrazení je v adrese (sdílitelný odkaz, ostatní parametry a #hash se zachovají);
// ceny bez DPH i s DPH 21 % (zaokrouhleno na celé Kč); typ válečku se filtruje podle hodnoty ze specs, zobrazuje se česky (Ocelový / Hliníkový / Hliníkový vroubkovaný).
(function () {
  "use strict";
  var VAT = 21;
  // Zobrazované názvy typu válečku (bot7, 2026-10-07): hodnota ve specs ("Typ válečku") zůstává beze změny a podle ní se filtruje i sestavuje adresa; v zobrazení Ocelový / Hliníkový /
  // Hliníkový vroubkovaný („hladký“ není ve zdroji - nevymýšlíme vlastnost). Neznámá hodnota se zobrazí tak, jak je.
  var TYP_LABEL = { "Ocel": "Ocelový", "Hliník hladký": "Hliníkový", "Hliník vroubkovaný": "Hliníkový vroubkovaný" };
  function typLabel(v) { return TYP_LABEL[v] || v; }
  function fmtDelkaCislo(mm) { mm = Number(mm); return mm % 1000 === 0 ? String(mm / 1000) : String(mm / 1000).replace(".", ","); }
  function fmtDelka(mm) { return fmtDelkaCislo(mm) + " m"; }
  var GROUPS = [
    { key: "delka", label: "Délka dopravníku", fmt: fmtDelka, title: function (v) { return "Délka dopravníku " + v + " mm"; } },
    { key: "sirka", label: "Šířka dopravníku (délka válečku)", fmt: function (v) { return v + " mm"; }, title: function (v) { return "Délka válečku " + v + " mm"; } },
    { key: "typ", label: "Typ válečku", fmt: typLabel, title: typLabel }
  ];

  function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
  function num(v) { var m = String(v == null ? "" : v).replace(",", ".").match(/-?\d+(\.\d+)?/); return m ? parseFloat(m[0]) : null; }
  function fmtKc(n) { return Math.round(n).toLocaleString("cs-CZ") + " Kč"; }
  function plVar(n) { n = Math.abs(n); return n + " " + (n === 1 ? "varianta" : (n >= 2 && n <= 4 ? "varianty" : "variant")); }      // 1 varianta, 2-4 varianty, 0 a 5+ variant
  function withVat(net) { return net + Math.round((net * VAT / 100 + 1e-9) * 100) / 100; }
  function detailUrl(p) { return p.slug ? "/produkt/" + encodeURIComponent(p.slug) : "/product.html?id=" + p.id; }

  function norm(p, i) {
    var s = p.specs || {};
    var m = /Ø(\d+)\s*[×x]\s*(\d+)\s*mm.*?délka\s*(\d+)\s*mm/i.exec(p.name || "") || [];       // záloha, kdyby specs chyběly
    var typ = s["Typ válečku"] || "Neuvedeno";
    return { idx: i, id: p.id, slug: p.slug, name: p.name, sku: s["Stock Code"] || p.sku || "", typ: typ, typL: typLabel(typ),
      prumer: num(s["Roller"]) != null ? num(s["Roller"]) : num(m[1]), sirka: num(s["Roller length"]) != null ? num(s["Roller length"]) : num(m[2]),
      delka: num(s["Conveyor Length"]) != null ? num(s["Conveyor Length"]) : num(m[3]), net: p.price_czk_placeholder, img: p.image_url || "" };
  }

  function mount(root, opts) {
    opts = opts || {};
    var API = "/api/shop/products?category_id=" + encodeURIComponent(opts.categoryId) + "&page_size=100&include=specs";
    var state = { delka: {}, sirka: {}, typ: {}, sort: "vychozi", dir: "asc", view: "tabulka" };
    var all = [], ui = {};

    // ---------- kostra
    root.textContent = ""; root.classList.add("kt-root");
    ui.intro = el("p", "kt-intro", "Vyberte délku, šířku a typ válečku – tabulka ukazuje všechny varianty najednou, ceny bez DPH i s DPH.");
    var panel = el("section", "kt-panel"); panel.setAttribute("aria-label", "Filtry");
    ui.box = el("details", "kt-filters-box"); ui.box.setAttribute("open", "");
    var sum = el("summary"); var sumSpan = el("span", null, "Filtry "); ui.activeN = el("span", "kt-activen"); sumSpan.appendChild(ui.activeN); sum.appendChild(sumSpan); ui.box.appendChild(sum);
    ui.filters = el("div", "kt-filters-body"); ui.box.appendChild(ui.filters); panel.appendChild(ui.box);
    var bar = el("div", "kt-toolbar");
    ui.count = el("div", "kt-count", "Načítám varianty…"); ui.count.setAttribute("role", "status"); ui.count.setAttribute("aria-live", "polite"); bar.appendChild(ui.count);
    ui.reset = el("button", "kt-btn-reset", "Zrušit filtry"); ui.reset.type = "button"; ui.reset.hidden = true; bar.appendChild(ui.reset);
    var tools = el("div", "kt-tools"), lab = el("label", null, "Řazení "); ui.sort = el("select", "kt-sort"); ui.sort.setAttribute("aria-label", "Řazení");
    [["vychozi:asc", "Výchozí"], ["cena:asc", "Cena: od nejnižší"], ["cena:desc", "Cena: od nejvyšší"], ["delka:asc", "Délka: od nejkratší"], ["delka:desc", "Délka: od nejdelší"],
     ["sirka:asc", "Šířka: od nejužší"], ["sirka:desc", "Šířka: od nejširší"]].forEach(function (o) { var op = el("option", null, o[1]); op.value = o[0]; ui.sort.appendChild(op); });
    lab.appendChild(ui.sort); tools.appendChild(lab);
    var seg = el("span", "kt-seg"); seg.setAttribute("role", "group"); seg.setAttribute("aria-label", "Zobrazení");
    ui.viewTab = el("button", null, "Tabulka"); ui.viewTab.type = "button"; ui.viewCards = el("button", null, "Karty"); ui.viewCards.type = "button";
    seg.appendChild(ui.viewTab); seg.appendChild(ui.viewCards); tools.appendChild(seg); bar.appendChild(tools);
    ui.result = el("div", "kt-result");
    ui.note = el("p", "kt-note", "Ceny jsou uvedeny bez DPH; cena s DPH je vypočtena se sazbou 21 %. Šířka odpovídá délce válečku, délka je délka dopravníku.");
    [ui.intro, panel, bar, ui.result, ui.note].forEach(function (n) { root.appendChild(n); });

    // ---------- stav v adrese (sdílitelné odkazy na nastavení filtrů; ostatní parametry a #hash stránky se zachovají)
    function readUrl() {
      var q = new URLSearchParams(location.search);
      GROUPS.forEach(function (g) { (q.get(g.key) || "").split(",").forEach(function (v) { if (v !== "") state[g.key][g.key === "typ" ? v : Number(v)] = true; }); });
      var r = (q.get("razeni") || "").split(":");
      if (["vychozi", "cena", "delka", "sirka"].indexOf(r[0]) >= 0) { state.sort = r[0]; state.dir = r[1] === "desc" ? "desc" : "asc"; }
      if (q.get("zobrazeni") === "karty") state.view = "karty";
    }
    function writeUrl() {
      var q = new URLSearchParams(location.search);
      GROUPS.forEach(function (g) { q.delete(g.key); }); q.delete("razeni"); q.delete("zobrazeni");
      GROUPS.forEach(function (g) { var v = Object.keys(state[g.key]); if (v.length) q.set(g.key, v.join(",")); });
      if (state.sort !== "vychozi") q.set("razeni", state.sort + ":" + state.dir);
      if (state.view === "karty") q.set("zobrazeni", "karty");
      var s = q.toString();
      try { history.replaceState(null, "", location.pathname + (s ? "?" + s : "") + location.hash); } catch (e) { /* adresa se nezapíše, filtry fungují dál */ }
    }

    // ---------- filtrování a řazení
    function passes(p, skipKey) {
      return GROUPS.every(function (g) {
        if (g.key === skipKey) return true;
        var sel = state[g.key]; if (!Object.keys(sel).length) return true;
        return sel[p[g.key]] === true;
      });
    }
    function filtered() { return all.filter(function (p) { return passes(p, null); }); }
    function activeCount() { return GROUPS.reduce(function (n, g) { return n + Object.keys(state[g.key]).length; }, 0); }
    function sorted(list) {
      var arr = list.slice(), d = state.dir === "desc" ? -1 : 1, k = state.sort;
      arr.sort(function (a, b) {
        var x, y;
        if (k === "cena") { x = a.net; y = b.net; } else if (k === "delka") { x = a.delka; y = b.delka; } else if (k === "sirka") { x = a.sirka; y = b.sirka; } else { return a.idx - b.idx; }
        return (x - y) * d || a.idx - b.idx;
      });
      return arr;
    }
    function options(g) {
      var seen = {}, out = [];
      all.forEach(function (p) { var v = p[g.key]; if (v != null && !seen[v]) { seen[v] = true; out.push(v); } });
      if (g.key !== "typ") out.sort(function (a, b) { return a - b; });
      return out;
    }

    // ---------- vykreslení
    function renderFilters() {
      var box = ui.filters; box.textContent = "";
      GROUPS.forEach(function (g) {
        var fs = el("fieldset", "kt-fgroup"); fs.setAttribute("data-group", g.key);
        fs.appendChild(el("legend", null, g.label));
        var chips = el("div", "kt-chips");
        options(g).forEach(function (v) {
          var n = all.filter(function (p) { return p[g.key] === v && passes(p, g.key); }).length;      // počet při ostatních aktivních filtrech
          var on = state[g.key][v] === true;
          var b = el("button", "kt-chip"); b.type = "button"; b.setAttribute("data-val", String(v));
          b.setAttribute("aria-pressed", on ? "true" : "false"); b.title = g.title(v);
          if (n === 0 && !on) b.setAttribute("aria-disabled", "true");
          b.appendChild(document.createTextNode(g.fmt(v)));
          var c = el("span", "kt-n", String(n)); c.setAttribute("aria-label", plVar(n)); b.appendChild(c);
          b.addEventListener("click", function () { if (b.getAttribute("aria-disabled") === "true") return; if (on) delete state[g.key][v]; else state[g.key][v] = true; update(); });
          chips.appendChild(b);
        });
        fs.appendChild(chips); box.appendChild(fs);
      });
      var n = activeCount(); ui.activeN.textContent = n ? "(" + n + ")" : "";
    }
    function renderTable(list) {
      var t = el("table", "kt-table"); t.appendChild(el("caption", "kt-sr", "Varianty válečkových dopravníků"));
      var thead = el("thead"), tr = el("tr");
      [["typ", "Typ válečku", false, null], ["prumer", "Ø válečku", true, null], ["sirka", "Šířka (mm)", true, "sirka"], ["delka", "Délka (m)", true, "delka"], ["cena", "Cena bez DPH", true, "cena"],
       ["cena-vat", "Cena s DPH", true, null], ["detail", "", false, null]].forEach(function (c) {
        var th = el("th"); th.scope = "col"; if (c[2]) th.className = "kt-num";
        if (c[3]) {
          th.setAttribute("aria-sort", state.sort === c[3] ? (state.dir === "desc" ? "descending" : "ascending") : "none");
          var b = el("button"); b.type = "button"; b.appendChild(document.createTextNode(c[1])); b.appendChild(el("span", "kt-ar", state.sort === c[3] ? (state.dir === "desc" ? "▼" : "▲") : "↕"));
          b.addEventListener("click", function () { if (state.sort === c[3]) state.dir = state.dir === "asc" ? "desc" : "asc"; else { state.sort = c[3]; state.dir = "asc"; } update(); });
          th.appendChild(b);
        } else if (c[1]) { th.appendChild(el("span", "kt-h", c[1])); } else { th.appendChild(el("span", "kt-sr", "Detail")); }
        tr.appendChild(th);
      });
      thead.appendChild(tr); t.appendChild(thead);
      var tb = el("tbody");
      list.forEach(function (p) {
        var r = el("tr"); r.setAttribute("data-id", String(p.id));
        var c1 = el("td", "kt-c-typ"); c1.appendChild(el("span", "kt-typ", p.typL)); if (p.sku) c1.appendChild(el("span", "kt-kod", p.sku)); r.appendChild(c1);
        function cell(cls, label, text) { var td = el("td", cls, text); if (label) td.setAttribute("data-label", label); r.appendChild(td); return td; }
        cell("kt-num kt-c-prumer", null, p.prumer != null ? "Ø" + p.prumer : "–");
        var ts = cell("kt-num kt-c-sirka", "Šířka", p.sirka != null ? String(p.sirka) : "–"); if (p.sirka != null) ts.appendChild(el("span", "kt-u", " mm"));        // jednotka je v záhlaví sloupce; na mobilu (bez záhlaví) se ukáže u hodnoty
        var td2 = cell("kt-num kt-c-delka", "Délka", p.delka != null ? fmtDelkaCislo(p.delka) : "–"); if (p.delka != null) td2.appendChild(el("span", "kt-u", " m"));
        var net = p.net, hasP = typeof net === "number";
        cell("kt-num kt-cena", null, hasP ? fmtKc(net) : "na dotaz");
        cell("kt-num kt-cena-vat", "s DPH", hasP ? fmtKc(withVat(net)) : "–");
        var td = el("td", "kt-c-detail"), a = el("a", "kt-btn-detail", "Detail"); a.href = detailUrl(p);
        a.setAttribute("aria-label", "Detail produktu: " + p.typL + ", šířka " + p.sirka + " mm, délka " + fmtDelka(p.delka));
        td.appendChild(a); r.appendChild(td);
        tb.appendChild(r);
      });
      t.appendChild(tb); return t;
    }
    function renderCards(list) {
      var g = el("div", "kt-cards");
      list.forEach(function (p) {
        var c = el("article", "kt-dcard"); c.setAttribute("data-id", String(p.id));
        var im = el("div", "kt-im"); if (p.img) { var i = el("img"); i.src = p.img; i.loading = "lazy"; i.alt = ""; im.appendChild(i); } c.appendChild(im);
        var bd = el("div", "kt-bd");
        bd.appendChild(el("div", "kt-t", p.typL));
        bd.appendChild(el("div", "kt-p", "Ø" + p.prumer + " · šířka " + p.sirka + " mm · délka " + fmtDelka(p.delka)));
        var pr = el("div", "kt-cena", typeof p.net === "number" ? fmtKc(p.net) : "na dotaz");
        if (typeof p.net === "number") { pr.appendChild(document.createTextNode(" bez DPH")); pr.appendChild(el("small", null, fmtKc(withVat(p.net)) + " s DPH")); }
        bd.appendChild(pr);
        var a = el("a", "kt-btn-detail", "Detail"); a.href = detailUrl(p); a.setAttribute("aria-label", "Detail produktu: " + p.typL + ", šířka " + p.sirka + " mm, délka " + fmtDelka(p.delka)); bd.appendChild(a);
        c.appendChild(bd); g.appendChild(c);
      });
      return g;
    }
    function renderResult() {
      var list = sorted(filtered()), res = ui.result; res.textContent = "";
      ui.count.textContent = "Nalezeno " + list.length + " z " + all.length + " variant";
      ui.reset.hidden = activeCount() === 0;
      if (!list.length) {
        var s = el("div", "kt-state", "Žádná varianta neodpovídá vybraným filtrům."); s.appendChild(document.createElement("br"));
        var b = el("button", "kt-btn-reset", "Zrušit filtry"); b.type = "button"; b.addEventListener("click", resetAll); s.appendChild(b); res.appendChild(s); return;
      }
      res.appendChild(state.view === "karty" ? renderCards(list) : renderTable(list));
    }
    function syncControls() {
      ui.sort.value = state.sort + ":" + (state.sort === "vychozi" ? "asc" : state.dir);
      ui.viewTab.setAttribute("aria-pressed", state.view === "tabulka" ? "true" : "false");
      ui.viewCards.setAttribute("aria-pressed", state.view === "karty" ? "true" : "false");
    }
    function update() { renderFilters(); renderResult(); syncControls(); writeUrl(); }
    function resetAll() { GROUPS.forEach(function (g) { state[g.key] = {}; }); update(); }

    // ---------- data
    function loadAll() {
      var rows = [], page = 1;
      function next() {
        return fetch(API + "&page=" + page).then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); }).then(function (d) {
          var pr = d.products || []; rows = rows.concat(pr);
          if (pr.length && rows.length < (d.total || 0) && page < 20) { page++; return next(); }
          return rows;
        });
      }
      return next();
    }
    function showError() {
      ui.count.textContent = "Varianty se nepodařilo načíst.";
      var s = el("div", "kt-state", "Data e-shopu se nepodařilo načíst. "); var b = el("button", "kt-btn-reset", "Zkusit znovu"); b.type = "button"; b.addEventListener("click", init); s.appendChild(b);
      ui.result.textContent = ""; ui.result.appendChild(s);
    }
    function init() {
      ui.count.textContent = "Načítám varianty…";
      return loadAll().then(function (rows) {
        all = rows.map(norm).filter(function (p) { return p.delka != null && p.sirka != null; });
        ui.intro.textContent = "Vyberte délku, šířku a typ válečku – tabulka ukazuje všech " + all.length + " variant najednou, ceny bez DPH i s DPH.";
        update();
      }).catch(function () { showError(); });
    }

    // ---------- ovládání
    ui.reset.addEventListener("click", resetAll);
    ui.sort.addEventListener("change", function () { var p = this.value.split(":"); state.sort = p[0]; state.dir = p[1] === "desc" ? "desc" : "asc"; update(); });
    ui.viewTab.addEventListener("click", function () { state.view = "tabulka"; update(); });
    ui.viewCards.addEventListener("click", function () { state.view = "karty"; update(); });
    // na mobilu jsou filtry sbalené, na počítači rozbalené
    if (window.matchMedia && window.matchMedia("(max-width: 760px)").matches) ui.box.removeAttribute("open");

    readUrl();
    return init();
  }

  window.KategorieTabulka = { mount: mount };
})();
