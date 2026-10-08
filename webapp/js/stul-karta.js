/* stul-karta.js - tlacitko "Vytvorit kartu" + dialog v ZAMESTNANECKEM Generatoru stolu (stul-konfigurator*.html = generatory 01-05, systemy 30 / 35 / 40 / 41 / 45; bot10, 2026-10-07).
   Robert 2026-10-07: "pridat do generatoru: tlacitko ktere z aktualni sestavy vytvori aktivni kartu". Kontrakt: docs/KONTRAKT_KARTA_Z_KONFIGURACE.md.
   GET /api/admin/konfigurace/karta = SONDA (200 {ok:true, verze:1, muze_aktivovat, kategorie:[{id,name}], vychozi_kategorie:{system:id}} jen se pravem sklad_karty/vytvorit; 401/403/404 = tlacitko se
   NEUKAZE - statika jde zive driv nez nasazene API). POST stejne URL: s `nahled:true` nic nezapise a vrati, co by vzniklo (SKU, nazev, cena, kategorie, uz existujici karta); bez nej zalozi kartu.
   Klient posila JEN vyber (selection + rules_version, hash) + volitelne upraveny nazev, kategorii a priznak aktivni; cenu, kod, model a popis pocita server. Dvojity klik je bezpecny (karta se stejnym
   SKU uz existuje -> server vrati ji, nic nemeni). Z odpovedi serveru se nevklada zadne HTML (jen textContent), odkazy jen http(s) na nase domeny.
   Samostatny modul bez zavislosti na hostiteli: window.StulKarta.mount(hostElement, { getPayload, onRulesChanged }) -> { sync(), destroy(), jeZobrazeno() };
   getPayload() vraci { product_id, selection, rules_version, hash, kod, system } nebo null (konfigurace se prepocitava / neni platna). Nova verze modulu = scripts/stul_verze.py (pin ?v= v HTML generatoru). */
(function (global) {
  "use strict";
  var URL_KARTA = "/api/admin/konfigurace/karta";
  var NASE_DOMENY = ["logiman.cz", "baliace-stoly.top", "packing-tables.top"];
  var CSS = ".kar-wrap{margin-top:10px}.kar-wrap[hidden]{display:none}.kar-status{margin-top:6px;font-size:.85rem;color:var(--muted,#8b93a1);line-height:1.4}.kar-status a{color:var(--accent,#2dd4bf)}"
    + ".kar-btn,.kar-primary{padding:.55rem 1rem;background:var(--accent,#2dd4bf);color:#1a1208;border:0;font:700 .85rem var(--mono,ui-monospace,monospace);letter-spacing:.06em;text-transform:uppercase;cursor:pointer}"
    + ".kar-btn:hover,.kar-primary:hover{background:var(--accent-glow,var(--accent,#5eead4))}.kar-btn[disabled],.kar-primary[disabled]{opacity:.5;cursor:not-allowed}"
    + ".kar-ghost{background:transparent;color:var(--text-soft,#c7ccd4);border:1px solid var(--line,#3a3f4a);padding:.5rem .8rem;font:inherit;cursor:pointer}.kar-ghost:hover{color:var(--accent,#2dd4bf);border-color:var(--accent,#2dd4bf)}"
    + ".kar-overlay{position:fixed;inset:0;z-index:9999;display:flex;align-items:center;justify-content:center;padding:16px;background:rgba(0,0,0,.6)}"
    + ".kar-dlg{width:100%;max-width:520px;max-height:calc(100vh - 32px);overflow:auto;background:var(--panel,#22262e);color:var(--text,#e8eaed);border:1px solid var(--line,#3a3f4a);padding:18px;font-size:16px;line-height:1.4;box-sizing:border-box}"
    + ".kar-dlg h2{margin:0 0 6px;font-size:1.25rem}.kar-dlg p{margin:0 0 12px}.kar-sub{color:var(--muted,#8b93a1)}"
    + ".kar-row{display:flex;flex-direction:column;gap:4px;margin:0 0 12px}.kar-row label{color:var(--muted,#8b93a1)}"
    + ".kar-row input[type=text],.kar-row select{font:inherit;padding:8px 10px;min-height:44px;background:var(--panel2,#1a1d23);color:inherit;border:1px solid var(--line,#3a3f4a);border-radius:0;width:100%;box-sizing:border-box}"
    + ".kar-chk{display:flex;gap:10px;align-items:flex-start;margin:0 0 12px}.kar-chk input{width:22px;height:22px;margin:2px 0 0;flex:none}.kar-chk label{color:inherit}"
    + ".kar-info{padding:8px 10px;margin:0 0 12px;border:1px solid var(--line,#3a3f4a)}"
    + ".kar-err{margin:0 0 12px;padding:8px 10px;color:var(--error,#e07070);border:1px solid var(--error,#e07070)}.kar-err ul{margin:6px 0 0 18px;padding:0}"
    + ".kar-warn{margin:0 0 12px;padding:8px 10px;border:1px solid var(--warn,#d9a441)}"
    + ".kar-btns{display:flex;flex-wrap:wrap;gap:8px;margin-top:6px}.kar-btns button,.kar-btns a{min-height:44px;cursor:pointer;text-decoration:none;display:inline-flex;align-items:center;box-sizing:border-box}"
    + ".kar-btns a{padding:8px 16px;border:1px solid var(--line,#3a3f4a);color:var(--accent,#2dd4bf);font:inherit}.kar-ok b{font-weight:600}";
  var MSG = {
    rules_changed: "Pravidla generátoru se mezitím změnila. Konfigurace se načte znovu – zkontroluj ji a vytvoř kartu znovu.",
    configuration_changed: "Konfigurace se mezitím změnila (server ji vyhodnotil jinak než stránka). Načítám ji znovu – zkontroluj ji a zkus to znovu.",
    price_on_request: "Cena téhle konfigurace není k dispozici, kartu nejde vytvořit.",
    invalid_configuration: "Tuhle konfiguraci nejde vyrobit:",
    invalid_selection: "Neplatná data konfigurace.",
    invalid_name: "Neplatný název karty (3 až 200 znaků, bez hranatých a špičatých závorek).",
    invalid_category: "Tuhle kategorii nelze použít.",
    not_configurable: "Tahle karta není konfigurovatelný stůl.",
    exists: "Karta s touhle konfigurací právě vznikla. Zavři okno a otevři ho znovu.",
    glb_failed: "Model konfigurace se nepodařilo postavit, karta nevznikla.",
    glb_invalid: "Model konfigurace nemá určené čelo, karta nevznikla.",
    selection_not_storable: "Konfiguraci nelze uložit, karta nevznikla.",
    save_failed: "Kartu se nepodařilo uložit, nic nevzniklo.",
    forbidden: "Na vytváření karet nemáš oprávnění.",
    rate_limited: "Limit 20 nových karet za hodinu je vyčerpaný, zkus to později.",
    unauthorized: "Nejsi přihlášený – přihlas se znovu.",
    net: "Spojení selhalo, karta nebyla vytvořena. Zkus to znovu.",
    fail: "Kartu se nepodařilo vytvořit."
  };

  function el(tag, attrs, kids) {
    var e = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) { var v = attrs[k]; if (v == null || v === false) return; if (k === "class") e.className = v; else if (k === "text") e.textContent = v; else e.setAttribute(k, v === true ? "" : v); });
    (kids == null ? [] : (Array.isArray(kids) ? kids : [kids])).forEach(function (c) { if (c != null) e.appendChild(typeof c === "string" ? document.createTextNode(c) : c); });
    return e;
  }
  function bezpecnyOdkaz(u) {                                    // jen http(s) na nase domeny (nebo relativni adresa), jinak null
    if (!u || typeof u !== "string" || u.length > 2000) return null;
    var url; try { url = new URL(u, location.origin); } catch (e) { return null; }
    if (url.protocol !== "https:" && url.protocol !== "http:") return null;
    var h = url.hostname.toLowerCase();
    return h === location.hostname.toLowerCase() || NASE_DOMENY.some(function (d) { return h === d || h.slice(-d.length - 1) === "." + d; }) ? url.href : null;
  }
  function kc(n) { return Number(n).toLocaleString("cs-CZ", { maximumFractionDigits: 0 }) + " Kč"; }
  function css() {
    if (document.getElementById("kar-css")) return;
    var s = document.createElement("style"); s.id = "kar-css"; s.textContent = CSS; document.head.appendChild(s);
  }

  function mount(host, opt) {
    opt = opt || {};
    css();
    var btn = el("button", { type: "button", class: "kar-btn", id: "kartaBtn", hidden: true, text: "Vytvořit kartu" });
    var stav = el("div", { class: "kar-status", id: "kartaStav", role: "status", "aria-live": "polite" });
    var wrap = el("div", { class: "kar-wrap", hidden: true }, [btn, stav]);                 // jeden prvek v okne (jedna mezera), do odpovedi sondy cely skryty
    host.appendChild(wrap);
    var dlg = null, busy = false, info = { muze_aktivovat: false, kategorie: [], vychozi_kategorie: {} };
    var ctl = { sync: sync, destroy: destroy, jeZobrazeno: function () { return !btn.hidden && !wrap.hidden; } };

    function platne() { try { return typeof opt.getPayload === "function" ? opt.getPayload() : null; } catch (e) { return null; } }
    function sync() {
      var ok = !!platne();
      btn.disabled = !ok;
      btn.title = ok ? "Z téhle konfigurace vytvoří novou kartu produktu v e-shopu (stůl se zadanými rozměry a volbami)" : "Konfigurace se právě přepočítává nebo není platná";
    }
    // sonda: tlacitko se ukaze jen kdyz endpoint existuje a uzivatel ma pravo (statika nesmi jit pred API)
    fetch(URL_KARTA, { credentials: "same-origin", headers: { Accept: "application/json" } })
      .then(function (r) { return r.ok ? r.json().catch(function () { return null; }) : null; })
      .then(function (j) {
        if (j && j.ok === true) {
          info = { muze_aktivovat: j.muze_aktivovat === true, kategorie: Array.isArray(j.kategorie) ? j.kategorie : [], vychozi_kategorie: j.vychozi_kategorie || {} };
          wrap.hidden = false; btn.hidden = false; sync();
        }
      })
      .catch(function () { /* bez tlacitka */ });
    btn.addEventListener("click", function () { if (!btn.disabled) otevri(); });

    function zavri() {
      if (!dlg) return;
      document.removeEventListener("keydown", klavesa, true);
      if (dlg.parentNode) dlg.parentNode.removeChild(dlg);
      dlg = null; try { btn.focus(); } catch (e) { /* nic */ }
    }
    function klavesa(e) {
      if (e.key === "Escape" && !busy) { e.stopPropagation(); zavri(); }
      else if (e.key === "Tab" && dlg) {                         // zachytit Tab v dialogu
        var f = dlg.querySelectorAll("button:not([disabled]),input:not([disabled]),select:not([disabled]),a[href]");
        if (!f.length) return;
        var prvni = f[0], posledni = f[f.length - 1];
        if (e.shiftKey && document.activeElement === prvni) { e.preventDefault(); posledni.focus(); }
        else if (!e.shiftKey && document.activeElement === posledni) { e.preventDefault(); prvni.focus(); }
      }
    }
    function volej(tela) {                                       // -> Promise<{ok, status, j}> ; sitova chyba = {ok:false, status:0, j:{error:"net"}}
      return fetch(URL_KARTA, { method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json", Accept: "application/json" }, body: JSON.stringify(tela) })
        .then(function (r) { return r.json().catch(function () { return {}; }).then(function (j) { return { ok: r.ok, status: r.status, j: j || {} }; }); })
        .catch(function () { return { ok: false, status: 0, j: { error: "net" } }; });
    }
    function zaklad(pl, extra) {
      var t = { product_id: pl.product_id, configuration: { selection: pl.selection, rules_version: pl.rules_version }, hash: pl.hash };
      Object.keys(extra || {}).forEach(function (k) { t[k] = extra[k]; });
      return t;
    }
    function chybaText(j) {
      var kod = j && j.error;
      var t = MSG[kod] || (j && typeof j.message === "string" && j.message) || MSG.fail;
      return { text: t, seznam: kod === "invalid_configuration" && Array.isArray(j.errors) ? j.errors.map(function (x) { return x && x.message; }).filter(Boolean) : [] };
    }
    function ukazChybu(box, j) {
      var c = chybaText(j);
      box.textContent = "";
      box.appendChild(document.createTextNode(c.text));
      if (c.seznam.length) { var ul = el("ul"); c.seznam.slice(0, 8).forEach(function (m) { ul.appendChild(el("li", { text: String(m).slice(0, 300) })); }); box.appendChild(ul); }
      box.hidden = false;
      if ((j && (j.error === "rules_changed" || j.error === "configuration_changed")) && typeof opt.onRulesChanged === "function") { try { opt.onRulesChanged(); } catch (e) { /* nic */ } }
    }
    function odkazKarty(url, popisek) {
      var h = bezpecnyOdkaz(url);
      return h ? el("a", { href: h, target: "_blank", rel: "noopener", text: popisek }) : null;
    }

    function otevri() {
      var pl = platne();
      if (!pl || dlg) return;
      var overlay = el("div", { class: "kar-overlay" });
      var box = el("div", { class: "kar-dlg", role: "dialog", "aria-modal": "true", "aria-labelledby": "karTitle" });
      overlay.appendChild(box); dlg = overlay;
      var obsah = el("div", { id: "karObsah" });
      var chyba = el("div", { class: "kar-err", id: "karChyba", role: "alert", hidden: true });
      var zrusit = el("button", { type: "button", id: "karZrusit", class: "kar-ghost", text: "Zrušit" });
      var odeslat = el("button", { type: "button", id: "karOdeslat", class: "kar-primary", text: "Vytvořit kartu", disabled: true });
      var tlacitka = el("div", { class: "kar-btns" }, [odeslat, zrusit]);
      box.appendChild(el("h2", { id: "karTitle", text: "Vytvořit kartu z konfigurace" }));
      box.appendChild(el("p", { class: "kar-sub", text: "Z téhle konfigurace vznikne nová karta produktu v e-shopu. Cenu, model a popis spočítá server; obrázky doplní render." }));
      box.appendChild(el("div", { class: "kar-info", id: "karInfo", text: "Konfigurace " + (pl.kod || "") + (pl.system ? " · " + (Number(pl.system) === 41 ? "SSE" : "systém " + pl.system) : "") }));
      box.appendChild(obsah); box.appendChild(chyba); box.appendChild(tlacitka);
      document.body.appendChild(overlay);
      document.addEventListener("keydown", klavesa, true);
      zrusit.addEventListener("click", function () { if (!busy) zavri(); });
      overlay.addEventListener("mousedown", function (e) { if (e.target === overlay && !busy) zavri(); });
      obsah.appendChild(el("p", { class: "kar-sub", id: "karPocitam", text: "Počítám, co vznikne…" }));
      try { zrusit.focus(); } catch (e) { /* nic */ }

      busy = true;
      volej(zaklad(pl, { nahled: true })).then(function (r) {
        busy = false;
        if (!dlg) return;
        obsah.textContent = "";
        if (!r.ok) { ukazChybu(chyba, r.j); return; }
        var n = r.j;
        if (n.existing) {                                          // takova karta uz je: nic nezakladat, jen ukazat
          var ex = n.existing, a = odkazKarty(ex.url, "Otevřít kartu");
          obsah.appendChild(el("div", { class: "kar-warn", id: "karExistuje" }, ["Karta s touhle konfigurací už existuje: #" + ex.id + " " + String(ex.name || "").slice(0, 200) + (ex.archived ? " (archivovaná)" : ex.active ? " (aktivní)" : " (neaktivní)") + ". Nová se nezakládá."]));
          odeslat.hidden = true; zrusit.textContent = "Zavřít";
          if (a) tlacitka.insertBefore(a, zrusit);
          return;
        }
        var nazev = el("input", { type: "text", id: "karNazev", maxlength: "200", value: String(n.name || ""), autocomplete: "off" });
        var kat = el("select", { id: "karKategorie" }, [el("option", { value: "", text: "— bez kategorie —" })].concat((n.kategorie || []).map(function (k) { return el("option", { value: String(k.id), text: String(k.name).slice(0, 120) }); })));
        kat.value = n.category_id != null ? String(n.category_id) : "";
        obsah.appendChild(el("div", { class: "kar-row" }, [el("label", { for: "karNazev", text: "Název karty" }), nazev]));
        obsah.appendChild(el("div", { class: "kar-row" }, [el("label", { for: "karKategorie", text: "Kategorie" }), kat]));
        var aktivni = null;
        if (n.muze_aktivovat) {
          aktivni = el("input", { type: "checkbox", id: "karAktivni", checked: true });
          obsah.appendChild(el("div", { class: "kar-chk" }, [aktivni, el("label", { for: "karAktivni", text: "Aktivní hned – zákazníci kartu uvidí v e-shopu" })]));
        } else {
          obsah.appendChild(el("p", { class: "kar-sub", id: "karNeaktivni", text: "Karta vznikne neaktivní (aktivaci zapíná uživatel s právem upravovat skladové karty)." }));
        }
        var cena = n.price || {};
        obsah.appendChild(el("p", { class: "kar-sub", id: "karCena", text: "Cena karty (snímek v okamžiku vytvoření): " + kc(cena.net_czk) + " bez DPH, " + kc(cena.gross_czk) + " s DPH. Stránka karty ukazuje vždy aktuální cenu generátoru." }));
        obsah.appendChild(el("p", { class: "kar-sub", id: "karSku", text: "Kód karty: " + String(n.sku || "") }));
        function popisTlacitka() { odeslat.textContent = aktivni ? (aktivni.checked ? "Vytvořit aktivní kartu" : "Vytvořit neaktivní kartu") : "Vytvořit kartu"; }
        if (aktivni) aktivni.addEventListener("change", popisTlacitka);
        popisTlacitka();
        odeslat.disabled = false;
        try { odeslat.focus(); } catch (e) { /* nic */ }
        odeslat.addEventListener("click", function () {
          if (busy) return;
          var nyni = platne();
          if (!nyni) { ukazChybu(chyba, { error: "configuration_changed" }); return; }
          busy = true; odeslat.disabled = true; zrusit.disabled = true; chyba.hidden = true;
          odeslat.textContent = "Vytvářím…"; stav.textContent = "Vytvářím kartu…";
          var tel = zaklad(nyni, { name: nazev.value, category_id: kat.value === "" ? null : Number(kat.value), active: aktivni ? aktivni.checked : false });
          volej(tel).then(function (v) {
            busy = false; zrusit.disabled = false;
            if (!dlg) return;
            if (!v.ok) { odeslat.disabled = false; popisTlacitka(); stav.textContent = ""; ukazChybu(chyba, v.j); return; }
            hotovo(v.j, obsah, tlacitka, odeslat, zrusit);
          });
        });
      });
    }
    function hotovo(j, obsah, tlacitka, odeslat, zrusit) {
      var a = odkazKarty(j.url, "Otevřít kartu");
      var text = (j.existing ? "Karta už existovala: #" : "Karta vytvořena: #") + j.id + " " + String(j.name || "").slice(0, 200) + (j.active ? " (aktivní)" : " (neaktivní)") + ".";
      obsah.textContent = "";
      obsah.appendChild(el("div", { class: "kar-info kar-ok", id: "karHotovo" }, [el("b", { text: text })]));
      obsah.appendChild(el("p", { class: "kar-sub", text: "Kód " + String(j.sku || "") + ". Obrázky doplní render; karta naběhne ve všech částech webu do minuty." + (j.poznamka ? " " + String(j.poznamka) : "") }));
      odeslat.hidden = true; zrusit.textContent = "Zavřít";
      if (a) tlacitka.insertBefore(a, zrusit);
      stav.textContent = "";
      var odkaz = odkazKarty(j.url, "karta #" + j.id);
      stav.appendChild(document.createTextNode((j.existing ? "Karta už existuje: " : "Karta vytvořena: ")));
      if (odkaz) stav.appendChild(odkaz); else stav.appendChild(document.createTextNode("#" + j.id));
      stav.appendChild(document.createTextNode(j.active ? " (aktivní)." : " (neaktivní)."));
    }

    function destroy() { zavri(); if (wrap.parentNode) wrap.parentNode.removeChild(wrap); }
    return ctl;
  }

  global.StulKarta = { mount: mount };
})(window);
