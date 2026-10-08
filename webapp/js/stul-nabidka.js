/* stul-nabidka.js - tlacitko "Do online nabidky" + dialog v ZAMESTNANECKEM Generatoru stolu (stul-konfigurator*.html = generatory 01-04, systemy 30 / 35 / 40 / 41; bot16, 2026-10-06).
   Robert 2026-10-06: "tlacitko pro promitnuti konfigurace stolu do online nabidky, pro kazdy generator" (zatim JEN zamestnanec, zakaznik az na jeho pokyn - rozhodnuti v okne bot5).
   Kontrakt (bot5): docs/KONTRAKT_NABIDKA_Z_KONFIGURACE.md. GET /api/admin/konfigurace/nabidka = SONDA (200 {ok:true, verze:1} jen se pravem nabidky.vytvorit; 401/403/404 = tlacitko se
   NEUKAZE - statika jde zive driv nez nasazene API). POST stejne URL = nova nabidka z konfigurace: klient posila JEN vyber (selection + rules_version, volitelne hash, qty, montaz_pct, zemi dodani,
   zakaznika), cenu, kod, kusovnik a model pocita server. Jedna nabidka = jedna konfigurace s mnozstvim (V1; qty 1-99 = VYCHOZI pocet kusu na strance nabidky, zakaznik ho tam smi zmenit);
   po uspechu se online_url (relativni /nabidka-online.html?t=<token>, stranka pro zakaznika) otevre v novem panelu; odpoved nema admin_url, nabidky jsou v adminu pod "Online nabidky" (#onlineoffers).
   Endpoint NENI idempotentni (dva kliky = dve nabidky): tlacitko drzi stav "Vytvarim..." do odpovedi; limit 30 nabidek za hodinu na uzivatele (429 rate_limited).
   VYKRESY (Robert 2026-10-06 pres bot5/bot8: nabidka ze stolu ma mit kotovane 2D vykresy jako nabidka ze sceny): po uspesnem 201 se do predotevrene zalozky nacte
   /scene.html?stul=<query>&nabidka_vykresy=<offer_id> (query = stejny retezec jako u "Vlozit do Sceny", StulDoSceny.dotaz()); Scena bez kliku vyrobi vykresy a posle je na
   POST /api/admin/konfigurace/nabidka/<offer_id>/vykresy (docs/NABIDKA_VYKRESY_ZE_STOLU.md, bot8). Stranka nabidky pro zakaznika zustava v dialogu jako odkaz. Stul SSE (system 41)
   se do Sceny nevklada -> predotevrena zalozka ukaze rovnou stranku nabidky, bez vykresu.
   Samostatny modul bez zavislosti na hostiteli: window.StulNabidka.mount(hostElement, { getPayload, onRulesChanged }) -> { sync(), destroy() };
   getPayload() vraci { product_id, selection, rules_version, hash, kod, system, sceneQuery } nebo null (konfigurace se prepocitava / neni platna). Z odpovedi serveru se nevklada zadne HTML (jen textContent),
   odkazy jen http(s) na nase domeny. Nova verze modulu = scripts/stul_verze.py (pin ?v= v HTML generatoru). */
(function (global) {
  "use strict";
  var URL_NABIDKA = "/api/admin/konfigurace/nabidka";
  var NASE_DOMENY = ["logiman.cz", "baliace-stoly.top", "packing-tables.top"];
  var ZEME = [["CZ", "Česko"], ["SK", "Slovensko"], ["PL", "Polsko"], ["DE", "Německo"], ["AT", "Rakousko"]];
  var CSS = ".nab-wrap{margin-top:10px}.nab-wrap[hidden]{display:none}.nab-status{margin-top:6px;font-size:.85rem;color:var(--muted,#8b93a1);line-height:1.4}"
    + ".nab-btn,.nab-primary{padding:.55rem 1rem;background:var(--accent,#2dd4bf);color:#1a1208;border:0;font:700 .85rem var(--mono,ui-monospace,monospace);letter-spacing:.06em;text-transform:uppercase;cursor:pointer;clip-path:polygon(0 0,calc(100% - 10px) 0,100% 10px,100% 100%,0 100%)}"
    + ".nab-btn:hover,.nab-primary:hover{background:var(--accent-glow,var(--accent,#5eead4))}.nab-btn[disabled],.nab-primary[disabled]{opacity:.5;cursor:not-allowed}"
    + ".nab-ghost{background:transparent;color:var(--text-soft,#c7ccd4);border:1px solid var(--line,#3a3f4a);padding:.5rem .8rem;font:inherit;cursor:pointer}.nab-ghost:hover{color:var(--accent,#2dd4bf);border-color:var(--accent,#2dd4bf)}"
    + ".nab-status a{color:var(--accent,#2dd4bf)}.nab-overlay{position:fixed;inset:0;z-index:9999;display:flex;align-items:center;justify-content:center;padding:16px;background:rgba(0,0,0,.6)}"
    + ".nab-dlg{width:100%;max-width:520px;max-height:calc(100vh - 32px);overflow:auto;background:var(--panel,#22262e);color:var(--text,#e8eaed);border:1px solid var(--line,#3a3f4a);padding:18px;font-size:16px;line-height:1.4;box-sizing:border-box}"
    + ".nab-dlg h2{margin:0 0 6px;font-size:1.25rem}.nab-dlg p{margin:0 0 12px}.nab-sub{color:var(--muted,#8b93a1)}"
    + ".nab-row{display:flex;flex-direction:column;gap:4px;margin:0 0 12px}.nab-row label{color:var(--muted,#8b93a1)}"
    + ".nab-row input,.nab-row select{font:inherit;padding:8px 10px;min-height:44px;background:var(--panel2,#1a1d23);color:inherit;border:1px solid var(--line,#3a3f4a);border-radius:0;width:100%;box-sizing:border-box}"
    + ".nab-cols{display:grid;grid-template-columns:1fr 1fr;gap:12px}@media(max-width:480px){.nab-cols{grid-template-columns:1fr}}"
    + ".nab-info{padding:8px 10px;margin:0 0 12px;border:1px solid var(--line,#3a3f4a)}"
    + ".nab-err{margin:0 0 12px;padding:8px 10px;color:var(--error,#e07070);border:1px solid var(--error,#e07070)}.nab-err ul{margin:6px 0 0 18px;padding:0}"
    + ".nab-btns{display:flex;flex-wrap:wrap;gap:8px;margin-top:6px}.nab-btns button,.nab-btns a{min-height:44px;cursor:pointer;text-decoration:none;display:inline-flex;align-items:center;box-sizing:border-box}.nab-btns a{padding:8px 16px;font:inherit}"
    + ".nab-btns a{border:1px solid var(--line,#3a3f4a);color:var(--accent,#2dd4bf)}.nab-ok b{font-weight:600}"
    + ".nab-tab{width:100%;border-collapse:collapse;margin:0 0 12px}.nab-tab td{padding:6px 0;border-bottom:1px solid var(--line,#3a3f4a)}.nab-tab td:last-child{text-align:right;white-space:nowrap;padding-left:12px}";
  var MSG = {
    rules_changed: "Pravidla generátoru se mezitím změnila. Konfigurace se načte znovu – zkontroluj ji a vytvoř nabídku znovu.",
    configuration_changed: "Konfigurace se mezitím změnila (server ji vyhodnotil jinak než stránka). Načítám ji znovu – zkontroluj ji a zkus to znovu.",
    price_on_request: "Cena téhle konfigurace není k dispozici, nabídku nejde vytvořit.",
    invalid_configuration: "Tuhle konfiguraci nejde vyrobit:",
    invalid_selection: "Neplatná data (zkontroluj množství, montáž a zemi dodání).",
    items_invalid: "Neplatná data (zkontroluj množství, montáž a zemi dodání).",
    not_configurable: "Tahle karta není konfigurovatelný stůl.",
    forbidden: "Na vytváření nabídek nemáš oprávnění.",
    rate_limited: "Limit 30 nabídek za hodinu je vyčerpaný, zkus to později.",
    unauthorized: "Nejsi přihlášený – přihlas se znovu.",
    net: "Spojení selhalo, nabídka nebyla vytvořena. Zkus to znovu.",
    fail: "Nabídku se nepodařilo vytvořit."
  };

  function el(tag, attrs, kids) {
    var e = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) { var v = attrs[k]; if (v == null || v === false) return; if (k === "class") e.className = v; else if (k === "text") e.textContent = v; else e.setAttribute(k, v === true ? "" : v); });
    (kids == null ? [] : (Array.isArray(kids) ? kids : [kids])).forEach(function (c) { if (c != null) e.appendChild(typeof c === "string" ? document.createTextNode(c) : c); });
    return e;
  }
  function bezpecnyOdkaz(u) {                                    // jen http(s) na nase domeny (nebo relativni adresa), jinak null
    if (!u || typeof u !== "string" || u.length > 6000) return null;                  // odkaz na Scenu nese celou konfiguraci stolu v query (~1,5 tis. znaku po zakodovani)
    var url; try { url = new URL(u, location.origin); } catch (e) { return null; }
    if (url.protocol !== "https:" && url.protocol !== "http:") return null;
    var h = url.hostname.toLowerCase();
    return h === location.hostname.toLowerCase() || NASE_DOMENY.some(function (d) { return h === d || h.slice(-d.length - 1) === "." + d; }) ? url.href : null;
  }
  function kc(n) { return Number(n).toLocaleString("cs-CZ", { maximumFractionDigits: 0 }) + " Kč"; }
  function css() {
    if (document.getElementById("nab-css")) return;
    var s = document.createElement("style"); s.id = "nab-css"; s.textContent = CSS; document.head.appendChild(s);
  }

  function mount(host, opt) {
    opt = opt || {};
    css();
    var btn = el("button", { type: "button", class: "nab-btn", id: "nabidkaBtn", hidden: true, text: "Do online nabídky" });
    var stav = el("div", { class: "nab-status", id: "nabidkaStav", role: "status", "aria-live": "polite" });
    var wrap = el("div", { class: "nab-wrap", hidden: true }, [btn, stav]);                // jeden prvek v okne (jedna mezera), do odpovedi sondy cely skryty
    host.appendChild(wrap);
    var dlg = null, busy = false, ctl = { sync: sync, destroy: destroy, jeZobrazeno: function () { return !btn.hidden && !wrap.hidden; } };

    function platne() { try { return typeof opt.getPayload === "function" ? opt.getPayload() : null; } catch (e) { return null; } }
    function sync() {
      var ok = !!platne();
      btn.disabled = !ok;
      btn.title = ok ? "Vytvoří z téhle konfigurace novou online nabídku pro zákazníka" : "Konfigurace se právě přepočítává nebo není platná";
    }
    // sonda: tlacitko se ukaze jen kdyz endpoint existuje a uzivatel ma pravo (statika nesmi jit pred API)
    fetch(URL_NABIDKA, { credentials: "same-origin", headers: { Accept: "application/json" } })
      .then(function (r) { return r.ok ? r.json().catch(function () { return null; }) : null; })
      .then(function (j) { if (j && j.ok === true) { wrap.hidden = false; btn.hidden = false; sync(); } })
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
    function radek(popisek, vstup, id) { return el("div", { class: "nab-row" }, [el("label", { for: id, text: popisek }), vstup]); }

    function otevri() {
      var pl = platne();
      if (!pl || dlg) return;
      var overlay = el("div", { class: "nab-overlay" });
      var box = el("div", { class: "nab-dlg", role: "dialog", "aria-modal": "true", "aria-labelledby": "nabTitle" });
      overlay.appendChild(box); dlg = overlay;
      var qty = el("input", { type: "number", id: "nabQty", min: "1", max: "99", step: "1", value: "1", inputmode: "numeric" });
      var montaz = el("select", { id: "nabMontaz" }, [el("option", { value: "default", text: "Výchozí sazba stolů" }), el("option", { value: "none", text: "Bez montáže (nenabízí se)" }), el("option", { value: "custom", text: "Vlastní sazba…" })]);
      var montazPct = el("input", { type: "text", id: "nabMontazPct", inputmode: "decimal", placeholder: "0–100", disabled: true, "aria-label": "Vlastní sazba montáže v procentech" });
      var zeme = el("select", { id: "nabZeme" }, ZEME.map(function (z) { return el("option", { value: z[0], text: z[1] + " (" + z[0] + ")" }); }));
      var jmeno = el("input", { type: "text", id: "nabJmeno", maxlength: "120", autocomplete: "off" });
      var email = el("input", { type: "email", id: "nabEmail", maxlength: "160", autocomplete: "off" });
      var chyba = el("div", { class: "nab-err", id: "nabChyba", role: "alert", hidden: true });
      var odeslat = el("button", { type: "button", id: "nabOdeslat", class: "nab-primary", text: "Vytvořit nabídku" });
      var zrusit = el("button", { type: "button", id: "nabZrusit", class: "nab-ghost", text: "Zrušit" });
      var montazNote = el("p", { class: "nab-sub", id: "nabMontazNote", hidden: true, text: "Do zahraničí se montáž nenabízí." });
      function zemeMontaz() { var zahr = zeme.value !== "CZ"; montaz.disabled = zahr; montazPct.disabled = zahr || montaz.value !== "custom"; montazNote.hidden = !zahr; }
      montaz.addEventListener("change", function () { montazPct.disabled = montaz.value !== "custom"; if (!montazPct.disabled) montazPct.focus(); });
      zeme.addEventListener("change", zemeMontaz);
      box.appendChild(el("h2", { id: "nabTitle", text: "Do online nabídky" }));
      box.appendChild(el("p", { class: "nab-sub", text: "Z téhle konfigurace vznikne nová online nabídka. Cenu spočítá server (prodejní cena generátoru bez DPH); montáž je zvlášť, jako volitelná služba." }));
      box.appendChild(el("div", { class: "nab-info", text: "Konfigurace " + (pl.kod || "") + (pl.system ? " · " + (Number(pl.system) === 41 ? "SSE" : "systém " + pl.system) : "") }));
      box.appendChild(chyba);
      box.appendChild(el("div", { class: "nab-cols" }, [radek("Množství (ks, výchozí v nabídce)", qty, "nabQty"), radek("Země dodání", zeme, "nabZeme")]));
      box.appendChild(el("div", { class: "nab-cols" }, [radek("Montáž", montaz, "nabMontaz"), radek("Sazba montáže (%)", montazPct, "nabMontazPct")]));
      box.appendChild(montazNote);
      box.appendChild(radek("Zákazník – jméno (nepovinné)", jmeno, "nabJmeno"));
      box.appendChild(radek("Zákazník – e-mail (nepovinné)", email, "nabEmail"));
      box.appendChild(el("p", { class: "nab-sub", text: "E-mail zákazníkovi se nikam neodesílá. Platba u těchto nabídek je jen předem (výroba na zakázku)." }));
      box.appendChild(el("div", { class: "nab-btns" }, [odeslat, zrusit]));
      box.addEventListener("keydown", function (e) { if (e.key === "Enter" && e.target && e.target.tagName === "INPUT" && !busy) { e.preventDefault(); odeslat.click(); } });      // Enter v poli = Vytvorit nabidku
      zrusit.addEventListener("click", function () { if (!busy) zavri(); });
      overlay.addEventListener("mousedown", function (e) { if (e.target === overlay && !busy) zavri(); });
      document.body.appendChild(overlay);
      document.addEventListener("keydown", klavesa, true);
      qty.focus(); qty.select();

      function ukazChybu(text, seznam) {
        chyba.textContent = ""; chyba.hidden = !text; if (!text) return;
        chyba.appendChild(document.createTextNode(text));
        if (seznam && seznam.length) { var ul = el("ul"); seznam.slice(0, 8).forEach(function (x) { ul.appendChild(el("li", { text: (x.slot ? x.slot + ": " : "") + String(x.message || "").slice(0, 200) })); }); chyba.appendChild(ul); }
      }
      var scenaCtx = null;                                        // co bylo v okamziku kliknuti: query pro Scenu a system (pro odkaz na vykresy po 201)
      function nacti() {                                          // validace formulare -> telo pozadavku nebo null
        var q = Number(qty.value);
        if (!/^\d{1,2}$/.test(String(qty.value).trim()) || q < 1 || q > 99) { ukazChybu("Množství musí být celé číslo od 1 do 99."); qty.focus(); return null; }
        var pct = null;                                           // null = vychozi sazba stolu; do zahranici montaz nejde (server vynuti 0), pole je zakazane
        if (zeme.value !== "CZ") pct = null;
        else if (montaz.value === "none") pct = 0;
        else if (montaz.value === "custom") {
          var t = String(montazPct.value).trim().replace(",", ".");
          if (!/^\d{1,3}(\.\d{1,2})?$/.test(t) || Number(t) < 0 || Number(t) > 100) { ukazChybu("Sazba montáže musí být číslo od 0 do 100."); montazPct.focus(); return null; }
          pct = Number(t);
        }
        var em = String(email.value).trim(), jm = String(jmeno.value).trim();
        if (em && !/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(em)) { ukazChybu("E-mail zákazníka nemá platný tvar."); email.focus(); return null; }
        var cur = platne();
        if (!cur) { ukazChybu("Konfigurace se právě přepočítává nebo není platná, počkej chvíli."); return null; }
        scenaCtx = { scenaQuery: cur.sceneQuery || null, system: cur.system };
        var b = { product_id: Number(cur.product_id), configuration: { selection: cur.selection, rules_version: cur.rules_version }, qty: q, montaz_pct: pct, delivery_country: zeme.value };
        if (cur.hash) b.hash = cur.hash;
        if (jm || em) { b.customer = {}; if (jm) b.customer.name = jm; if (em) b.customer.email = em; }
        return b;
      }
      odeslat.addEventListener("click", function () {
        if (busy) return;
        ukazChybu("");
        var telo = nacti(); if (!telo) return;
        busy = true; odeslat.disabled = zrusit.disabled = true; odeslat.textContent = "Vytvářím…";
        var okno = null;                                          // novy panel se otevre HNED (v rámci kliknuti, jinak by ho prohlizec zablokoval), po uspechu se do nej nacte nabidka
        try {
          okno = global.open("", "_blank");
          if (okno) { okno.opener = null; try { okno.document.title = "Vytvářím nabídku…"; okno.document.body.textContent = "Vytvářím nabídku…"; } catch (e2) { /* nic */ } }
        } catch (e) { okno = null; }
        fetch(URL_NABIDKA, { method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json", Accept: "application/json" }, body: JSON.stringify(telo) })
          .then(function (r) { return r.json().catch(function () { return {}; }).then(function (d) { return { st: r.status, d: d || {} }; }); })
          .then(function (x) {
            busy = false; odeslat.disabled = zrusit.disabled = false; odeslat.textContent = "Vytvořit nabídku";
            if (x.st === 201 || x.st === 200) { hotovo(box, x.d, okno, telo, scenaCtx); return; }
            if (okno) { try { okno.close(); } catch (e) { /* nic */ } }
            var kod = x.d && ((MSG[x.d.error] && x.d.error) || x.d.code || x.d.error), sm = x.d && typeof x.d.message === "string" ? x.d.message.slice(0, 300) : "";
            var text = MSG[kod] || (x.st === 401 ? MSG.unauthorized : x.st === 403 ? MSG.forbidden : x.st === 429 ? MSG.rate_limited : MSG.fail);
            if (sm && (kod === "invalid_selection" || kod === "items_invalid" || !MSG[kod])) text += " (" + sm + ")";      // zprava serveru je jen text (textContent); u vagnich kodu pomuze najit, co je spatne
            ukazChybu(text, kod === "invalid_configuration" && Array.isArray(x.d.errors) ? x.d.errors : null);
            if (kod === "rules_changed" || kod === "configuration_changed") { try { if (typeof opt.onRulesChanged === "function") opt.onRulesChanged(); } catch (e) { /* nic */ } }
          })
          .catch(function () {
            busy = false; odeslat.disabled = zrusit.disabled = false; odeslat.textContent = "Vytvořit nabídku";
            if (okno) { try { okno.close(); } catch (e) { /* nic */ } }
            ukazChybu(MSG.net);
          });
      });
    }

    function hotovo(box, d, okno, telo, ctx) {                  // vysledek: cislo, ceny, odkazy; do predotevrene zalozky se nacte Scena s vykresy (jinak stranka nabidky)
      var online = bezpecnyOdkaz(d.online_url), admin = bezpecnyOdkaz("/admin.html#onlineoffers");   // server admin_url nevraci (kontrakt bot5); nabidka je v adminu v seznamu Online nabidky
      var ks = Number((d.line && d.line.qty) || telo.qty) || 1;
      var ssse = !!ctx && Number(ctx.system) === 41;              // stul SSE se do Sceny nevklada
      var idNab = d.offer_id == null ? "" : String(d.offer_id);
      var scena = (ctx && ctx.scenaQuery && !ssse && /^\d{1,12}$/.test(idNab)) ? bezpecnyOdkaz("/scene.html?stul=" + encodeURIComponent(ctx.scenaQuery) + "&nabidka_vykresy=" + encodeURIComponent(idNab)) : null;
      var cil = scena || online;
      if (okno) { if (cil) { try { okno.location.href = cil; } catch (e) { /* nic */ } } else { try { okno.close(); } catch (e) { /* nic */ } } }
      box.textContent = "";
      box.appendChild(el("h2", { id: "nabTitle", text: "Nabídka vytvořena" }));
      box.appendChild(el("p", { class: "nab-ok" }, [el("b", { text: String(d.offer_number || ("č. " + (d.offer_id || ""))) }), " · konfigurace " + String((d.line && d.line.kod) || "") + " · " + ks + " ks"]));
      var tab = el("table", { class: "nab-tab" });
      function r(t, v) { tab.appendChild(el("tr", null, [el("td", { text: t }), el("td", { text: v })])); }
      if (d.price) {
        if (ks > 1 && d.line && d.line.unit_net_czk != null) r("Cena za 1 ks bez DPH", kc(d.line.unit_net_czk));
        if (d.price.net_czk != null) r("Cena bez DPH" + (ks > 1 ? " (" + ks + " ks)" : ""), kc(d.price.net_czk));
        if (d.price.vat_czk != null) r("DPH" + (d.price.vat_rate != null ? " " + d.price.vat_rate + " %" : ""), kc(d.price.vat_czk));
        if (d.price.gross_czk != null) r("Cena s DPH", kc(d.price.gross_czk));
      }
      if (d.montaz && d.montaz.czk != null) r("Montáž (volitelná, mimo cenu)" + (d.montaz.pct != null ? " " + d.montaz.pct + " %" : ""), kc(d.montaz.czk) + " bez DPH");
      if (tab.childNodes.length) box.appendChild(tab);
      box.appendChild(el("p", { class: "nab-sub", id: "nabVykresyInfo", text: scena
        ? (okno ? "Výkresy s kótami se dokončují ve Scéně (nová záložka) – až tam uvidíš „✓ Výkresy uloženy“, je nabídka kompletní."
                : "Prohlížeč zablokoval nové okno – otevři Scénu odkazem níže, jinak zůstane nabídka bez výkresů.")
        : (ssse ? "Pro stůl SSE zatím výkresy ze Scény nejsou (nohy SSE ve Scéně nejsou)." : "Výkresy se nepodařilo připravit (chybí odkaz na výrobní list nebo číslo nabídky) – nabídka zůstane bez výkresů.") }));
      if (d.v3d === false) box.appendChild(el("p", { class: "nab-sub", id: "nabBez3d", text: "Nabídka vznikla bez interaktivního 3D, zákazník uvidí souhrn bez modelu." + (typeof d.v3d_duvod === "string" && d.v3d_duvod ? " Důvod: " + d.v3d_duvod.slice(0, 300) : "") }));
      var tl = el("div", { class: "nab-btns" });
      if (scena) tl.appendChild(el("a", { href: scena, target: "_blank", rel: "noopener noreferrer", id: "nabScena", text: "Výkresy ve Scéně ↗" }));
      if (online) tl.appendChild(el("a", { href: online, target: "_blank", rel: "noopener noreferrer", id: "nabOnline", text: "Otevřít nabídku pro zákazníka ↗" }));
      if (admin) tl.appendChild(el("a", { href: admin, target: "_blank", rel: "noopener noreferrer", id: "nabAdmin", text: "Online nabídky v adminu ↗" }));
      var zavrit = el("button", { type: "button", id: "nabZavrit", class: "nab-primary", text: "Zavřít" }); zavrit.addEventListener("click", zavri); tl.appendChild(zavrit);
      box.appendChild(tl);
      stav.textContent = "";
      stav.appendChild(document.createTextNode("Poslední nabídka: " + String(d.offer_number || d.offer_id || "") + " "));
      if (online) stav.appendChild(el("a", { href: online, target: "_blank", rel: "noopener noreferrer", text: "zákaznická stránka" }));
      if (scena) { stav.appendChild(document.createTextNode(" · ")); stav.appendChild(el("a", { href: scena, target: "_blank", rel: "noopener noreferrer", text: "výkresy ve Scéně" })); }
      if (admin) { stav.appendChild(document.createTextNode(" · ")); stav.appendChild(el("a", { href: admin, target: "_blank", rel: "noopener noreferrer", text: "nabídky v adminu" })); }
      zavrit.focus();
    }
    function destroy() { zavri(); if (wrap.parentNode) wrap.parentNode.removeChild(wrap); }
    return ctl;
  }
  global.StulNabidka = { mount: mount };
})(window);
