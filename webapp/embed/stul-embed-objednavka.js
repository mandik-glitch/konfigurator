/* stul-embed-objednavka.js - OBJEDNAVKA HOSTA (bez registrace) ve vlozenem generatoru stolu (/embed/stul.html; kategorie 206, logiman.cz). Nacita se pred stul-embed.js.
   Kosik drzi prohlizec JEN PO DOBU RELACE (sessionStorage "stulHostKosik": jen volby konfigurace, ZADNA cena; po zavreni prohlizece zmizi, Robert 2026-10-05); server cenu VZDY pocita znovu (kontrakt bot5, api/stul_objednavka_host.py):
     POST /api/shop/stul/quote   {items:[{product_id, qty, montaz?, configuration:{selection, rules_version}}], delivery_zip?} -> radky, soucty, DPH, moznosti dopravy
     POST /api/shop/stul/order   {items, name, email, phone, company?, company_id?, vat_id?, delivery:{street,city,zip}, billing:{same:true}|{...}, shipping, payment:"transfer", consent:true,
                                  note?, expected_total_net, website (honeypot)} -> 201 {reference, status:"received", total, shipping:{id, net, review}, next:"proforma_after_shipping_confirmation"}
   Zadna automaticka proforma ani e-mail (pravidlo 16): cenu dopravy urci zamestnanec po objednavce, zakaznik ji uvidi ke schvaleni pred zalohovou fakturou.
   Rozhrani: var P = StulObjednavka.create({el, host, generator, target, loginHref, onAccount, notifyParent, sendHeightSoon}); P.add(radek); P.open(); P.close(); P.count(); P.onChange(fn). */
(function (global) {
  "use strict";
  var KEY = "stulHostKosik", MAX_LINES = 10, MAX_QTY = 99, MAX_AGE = 30 * 24 * 3600 * 1000;
  try { localStorage.removeItem(KEY); } catch (e) { /* nic */ }                      // drive localStorage (preziv zavreni prohlizece): kosik hosta s konfiguraci drzi jen relace (Robert 2026-10-05)
  var TXT = {
    shipNote: "Cenu dopravy stanovíme po objednávce podle toho, zda zvolíte montáž; uvidíte ji ke schválení před zálohovou fakturou.",
    title: "Objednávka", back: "← Zpět k úpravě stolu", account: "Máte účet? Přihlásit se", empty: "Váš košík je prázdný.", pending: "Počítám…",
    quoteError: "Součty se nepodařilo spočítat. Zkuste to prosím znovu.", retry: "Zkusit znovu",
    invalidLine: "Konfigurace už neodpovídá aktuálním pravidlům. Odeberte položku a nakonfigurujte stůl znovu.",
    secContact: "Kontaktní údaje", secDelivery: "Dodací adresa", secBilling: "Fakturační adresa", secShipping: "Doprava", secPayment: "Platba", secNote: "Poznámka",
    name: "Jméno a příjmení", company: "Firma (nepovinné)", companyId: "IČO (nepovinné)", vatId: "DIČ (nepovinné)", email: "E-mail", phone: "Telefon",
    street: "Ulice a číslo", city: "Město", zip: "PSČ", billingSame: "Fakturační adresa je stejná jako dodací", note: "Poznámka k objednávce (nepovinné)",
    payment: "Bankovní převod na základě zálohové faktury. Zálohovou fakturu vystavíme až po potvrzení ceny dopravy; stůl se začne vyrábět po jejím zaplacení.",
    consent: "Souhlasím se zpracováním osobních údajů pro vyřízení objednávky.",              // dočasné znění, dokud neexistují stránky podmínek (viz CONSENT_PAGES)
    consentPre: "Souhlasím s ", consentTerms: "obchodními podmínkami", consentMid: " a beru na vědomí ", consentPriv: "zásady ochrany osobních údajů", consentEnd: ".", submit: "Objednávka zavazující k platbě", sending: "Odesílám…", fillRequired: "Vyplňte prosím označená pole.",
    qty: "Množství", remove: "Odebrat", params: "Zvolené parametry", montaz: "Montáž", goods: "Stůl bez DPH", montazRow: "Montáž bez DPH", totalNet: "Celkem bez DPH", vat: "DPH", totalGross: "Celkem s DPH (bez dopravy)",
    exclVat: "bez DPH", inclVat: "s DPH", shipFree: "zdarma", shipEstimate: "odhad",
    sentTitle: "Děkujeme, objednávka byla přijata", sentRef: "Číslo objednávky", sentNext: "Cenu dopravy určíme po objednávce (podle toho, zda jste zvolili montáž) a před vystavením zálohové faktury vám ji potvrdíme. Zálohovou fakturu s platebními údaji pošleme e-mailem po potvrzení dopravy; stůl se začne vyrábět po jejím zaplacení.",
    sentTotal: "Celkem bez dopravy", another: "Nakonfigurovat další stůl", generic: "Objednávku se nepodařilo odeslat. Zkuste to prosím znovu nebo nás kontaktujte.", network: "Spojení se nezdařilo. Zkuste to prosím znovu."
  };
  var ERR = {
    name_required: "Zadejte prosím své jméno.", email_invalid: "Zadejte prosím platný e-mail.", phone_invalid: "Zadejte prosím platné telefonní číslo.", street_required: "Zadejte prosím ulici a číslo.",
    city_required: "Zadejte prosím město.", zip_invalid: "Zadejte prosím platné PSČ (5 číslic).", company_id_required: "Zadejte prosím IČO firmy.", company_id_invalid: "IČO nemá platný tvar.",
    vat_id_invalid: "DIČ nemá platný tvar.", shipping_invalid: "Zvolte prosím způsob dopravy.", payment_invalid: "Zvolte prosím platbu.", consent_required: "Pro odeslání je potřeba souhlas.",
    items_invalid: "Některá položka už není dostupná. Odeberte ji a zkuste to znovu.", configuration_required: "Konfigurace stolu chybí. Vraťte se k úpravě stolu.",
    invalid_selection: "Konfigurace stolu není platná. Vraťte se k úpravě stolu.", invalid_configuration: "Tuto konfiguraci nelze vyrobit. Vraťte se k úpravě stolu.",
    rules_changed: "Pravidla generátoru se mezitím změnila. Vraťte se k úpravě stolu a zkontrolujte zvolené parametry.", product_not_available: "Tento stůl zatím nelze objednat online.",
    montaz_unavailable: "Montáž u této konfigurace není k dispozici. Odškrtněte ji a zkuste to znovu.", price_on_request: "Cena této konfigurace není k dispozici.",
    order_in_progress: "Objednávka se právě zpracovává. Zkuste to prosím za chvíli.", too_many_orders: "Z této e-mailové adresy dnes přišlo příliš mnoho objednávek.",
    rate_limited: "Příliš mnoho pokusů. Zkuste to prosím za několik minut.", order_too_large: "Objednávka přesahuje limit pro online objednání. Kontaktujte nás prosím.",
    expected_total_invalid: "Cenu se nepodařilo ověřit. Načtěte souhrn znovu.", internal_error: "Na naší straně se něco pokazilo. Zkuste to prosím později.", order_rejected: "Objednávku se nepodařilo přijmout. Zkontrolujte údaje."
  };
  var FIELD = { name: "name", email: "email", phone: "phone", company: "company", company_id: "company_id", vat_id: "vat_id", "delivery.street": "d_street", "delivery.city": "d_city", "delivery.zip": "d_zip",
                "billing.street": "b_street", "billing.city": "b_city", "billing.zip": "b_zip", consent: "consent", shipping: "shipping" };
  // znění souhlasu (bot7, čeká na Robertovo schválení podmínek): „Souhlasím s <obchodními podmínkami> a beru na vědomí <zásady ochrany osobních údajů>.“ Odkazy se použijí JEN když stránky existují
  // (dnes 404, texty budou editovatelné v adminu); do té doby zůstává dočasné znění bez odkazů.
  var CONSENT_PAGES = { terms: "/obchodni-podminky", privacy: "/ochrana-osobnich-udaju" };
  var consentProbe = null;
  function pageExists(url) {
    return fetch(url, { method: "HEAD", credentials: "omit", cache: "no-store" }).then(function (r) { return r.ok; }).catch(function () { return false; });
  }
  function consentPagesExist() {
    if (!consentProbe) consentProbe = Promise.all([pageExists(CONSENT_PAGES.terms), pageExists(CONSENT_PAGES.privacy)]).then(function (a) { return a[0] && a[1]; });
    return consentProbe;
  }
  var EMAIL_RE = /^[A-Za-z0-9._%+'-]+@([A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,24}$/, PHONE_RE = /^\+?[0-9][0-9 ()/.-]{5,29}$/, ZIP_RE = /^\d{3} ?\d{2}$/;

  var mem = null;                                                   // zaloha, kdyz sessionStorage neni k dispozici (soukromy rezim)
  function validLine(i) { return i && typeof i === "object" && Number.isInteger(i.pid) && i.pid > 0 && Number.isInteger(i.qty) && i.qty >= 1 && i.qty <= MAX_QTY && typeof i.montaz === "boolean" && i.selection && typeof i.selection === "object" && typeof i.hash === "string" && i.hash; }
  function readCart() {
    try { var o = JSON.parse(sessionStorage.getItem(KEY) || "null"); if (o && o.v === 1 && Array.isArray(o.items) && Date.now() - o.ts < MAX_AGE) return o.items.filter(validLine).slice(0, MAX_LINES); } catch (e) { /* nic */ }
    return mem ? mem.filter(validLine).slice(0, MAX_LINES) : [];
  }
  function writeCart(items) {
    mem = items.slice();
    try { if (items.length) sessionStorage.setItem(KEY, JSON.stringify({ v: 1, ts: Date.now(), items: items })); else sessionStorage.removeItem(KEY); } catch (e) { /* nic */ }
  }
  function lineKey(i) { return i.pid + "|" + i.hash + "|" + (i.montaz ? 1 : 0); }
  function fmt(n) {
    n = Number(n);
    try { return new Intl.NumberFormat("cs-CZ", { style: "currency", currency: "CZK", minimumFractionDigits: n % 1 ? 2 : 0, maximumFractionDigits: 2 }).format(n); } catch (e) { return n + " Kč"; }
  }
  function postJSON(url, body) {
    return fetch(url, { method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) })
      .then(function (r) { return r.json().catch(function () { return {}; }).then(function (d) { return { st: r.status, d: d || {} }; }); });
  }

  function create(o) {
    var el = o.el, items = readCart(), quote = null, qState = "idle", qSeq = 0, qTimer = null, busy = false, sent = null, listeners = [];
    var root = el("section", { class: "emb-co", hidden: true, "aria-labelledby": "embCoTitle" });
    var backBtn = el("button", { type: "button", class: "mw-btn mw-btn-ghost mw-btn-sm", text: TXT.back });
    var accountLink = el("a", { class: "emb-co-account", href: o.loginHref(), target: o.target, rel: "noopener", text: TXT.account });
    accountLink.addEventListener("click", function () { if (o.onAccount) o.onAccount(); });          // rozdelanou konfiguraci si pamatuje generator (obnovi se po prihlaseni)
    var title = el("h2", { id: "embCoTitle", tabindex: "-1", text: TXT.title });
    var head = el("div", { class: "emb-co-head" }, [backBtn, title, accountLink]);
    var linesHost = el("div", { class: "emb-co-lines" }), totalsHost = el("div", { class: "emb-co-totals" });
    var shipNote = el("p", { class: "emb-co-shipnote", text: TXT.shipNote });
    var form = el("form", { class: "emb-co-form", novalidate: true, autocomplete: "on" });
    var okBox = el("div", { class: "emb-co-done", hidden: true, role: "status" });
    root.appendChild(head); root.appendChild(linesHost); root.appendChild(totalsHost); root.appendChild(shipNote); root.appendChild(form); root.appendChild(okBox);
    o.host.appendChild(root);

    // ---------------------------------------------------------------- formular
    var F = {};                                                     // name -> {box, input, err}
    function field(name, label, attrs, tag) {
      var input = el(tag || "input", Object.assign(tag === "textarea" ? { rows: "3", maxlength: "1000" } : { type: "text" }, { name: name, id: "embCo_" + name }, attrs || {}));
      var err = el("span", { class: "emb-co-err", role: "alert", hidden: true });
      var box = el("label", { class: "mw-field", for: "embCo_" + name }, [el("span", { class: "mw-label", text: label }), input, err]);
      F[name] = { box: box, input: input, err: err };
      return box;
    }
    function checkbox(name, text, checked) {
      var input = el("input", { type: "checkbox", name: name, id: "embCo_" + name, checked: checked ? true : null });
      var err = el("span", { class: "emb-co-err", role: "alert", hidden: true });
      var label = el("span", { text: text });
      var box = el("label", { class: "mw-opt mw-field", for: "embCo_" + name }, [input, label, err]);
      F[name] = { box: box, input: input, err: err, label: label };
      return box;
    }
    function pair(a, b, cls) { return el("div", { class: "emb-co-grid" + (cls ? " " + cls : "") }, [a, b]); }
    var billBox = el("div", { class: "emb-co-billing", hidden: true }, [el("h3", { class: "mw-win-sub", text: TXT.secBilling }), field("b_street", TXT.street, { autocomplete: "billing street-address" }),
      pair(field("b_city", TXT.city, { autocomplete: "billing address-level2" }), field("b_zip", TXT.zip, { autocomplete: "billing postal-code", inputmode: "numeric" }), "is-zip")]);
    var companyExtra = el("div", { class: "emb-co-company", hidden: true }, [pair(field("company_id", TXT.companyId, { inputmode: "numeric" }), field("vat_id", TXT.vatId))]);
    var shipHost = el("fieldset", { class: "mw-pay emb-co-ship" }, [el("legend", { class: "mw-label", text: TXT.secShipping })]);
    var honey = el("div", { class: "emb-co-hp", "aria-hidden": "true" }, [el("label", {}, ["Web", el("input", { type: "text", name: "website", tabindex: "-1", autocomplete: "off" })])]);
    var submit = el("button", { type: "submit", class: "mw-btn emb-co-submit", text: TXT.submit });
    var formMsg = el("p", { class: "emb-co-msg", role: "alert", "aria-live": "polite" });
    [el("h3", { class: "mw-win-sub", text: TXT.secContact }),
     pair(field("name", TXT.name, { autocomplete: "name" }), field("company", TXT.company, { autocomplete: "organization" })), companyExtra,
     pair(field("email", TXT.email, { type: "email", autocomplete: "email" }), field("phone", TXT.phone, { type: "tel", autocomplete: "tel" })),
     el("h3", { class: "mw-win-sub", text: TXT.secDelivery }), field("d_street", TXT.street, { autocomplete: "shipping street-address" }),
     pair(field("d_city", TXT.city, { autocomplete: "shipping address-level2" }), field("d_zip", TXT.zip, { autocomplete: "shipping postal-code", inputmode: "numeric" }), "is-zip"),
     checkbox("billing_same", TXT.billingSame, true), billBox, shipHost,
     field("note", TXT.note, {}, "textarea"), el("p", { class: "mw-fine emb-co-pay", text: TXT.payment }), checkbox("consent", TXT.consent, false), honey, submit, formMsg].forEach(function (n) { form.appendChild(n); });

    function setErr(name, text) { var f = F[name]; if (!f) return; f.err.textContent = text || ""; f.err.hidden = !text; if (f.input.setAttribute) { if (text) f.input.setAttribute("aria-invalid", "true"); else f.input.removeAttribute("aria-invalid"); } }
    function clearErrs() { Object.keys(F).forEach(function (k) { setErr(k, ""); }); formMsg.textContent = ""; formMsg.className = "emb-co-msg"; }
    function val(n) { return (F[n].input.value || "").trim(); }
    function zipDigits(n) { return val(n).replace(/\D/g, ""); }
    function syncBilling() { billBox.hidden = F.billing_same.input.checked; }
    function syncCompany() { companyExtra.hidden = !val("company"); }
    F.billing_same.input.addEventListener("change", function () { syncBilling(); o.sendHeightSoon(); });
    F.company.input.addEventListener("input", function () { syncCompany(); o.sendHeightSoon(); });
    var zipTimer = null;
    F.d_zip.input.addEventListener("input", function () { clearTimeout(zipTimer); zipTimer = setTimeout(function () { if (!root.hidden && !sent) requestQuote(); }, 700); });

    // ---------------------------------------------------------------- souhrn z quote
    function lineOf(idx) { return quote && quote.lines && quote.lines.length === items.length ? quote.lines[idx] : null; }
    function renderLines() {
      linesHost.textContent = "";
      if (!items.length) { linesHost.appendChild(el("p", { class: "mw-muted", text: TXT.empty })); return; }
      items.forEach(function (it, idx) {
        var ln = lineOf(idx), cfg = ln && ln.configuration, bad = ln && cfg && cfg.valid === false;
        var q = el("input", { type: "number", min: "1", max: String(MAX_QTY), value: String(it.qty), "aria-label": TXT.qty });
        q.addEventListener("change", function () { it.qty = Math.max(1, Math.min(MAX_QTY, parseInt(q.value, 10) || 1)); changed(); });
        var rm = el("button", { type: "button", class: "mw-link", text: TXT.remove });
        rm.addEventListener("click", function () { items.splice(idx, 1); changed(); });
        var mz = null;
        if (it.can || it.montaz) {                                                    // montaz je vzdy volitelna (nabizi se, kdyz ji server pro stul nabizel); castku dodava server (po zvoleni), procento zakaznik nevidi
          var cb = el("input", { type: "checkbox", checked: it.montaz ? true : null });
          cb.addEventListener("change", function () { it.montaz = cb.checked; mergeSame(); changed(); });
          mz = el("label", { class: "mw-opt emb-co-montaz" }, [cb, el("span", { text: TXT.montaz + (it.montaz && ln && ln.montaz_total_czk != null ? " · " + fmt(ln.montaz_total_czk) + " " + TXT.exclVat + (ln.montaz_total_with_vat_czk != null ? " · " + fmt(ln.montaz_total_with_vat_czk) + " " + TXT.inclVat : "") : "") })]);
        }
        var sum = cfg && Array.isArray(cfg.summary) && cfg.summary.length
          ? el("details", { class: "emb-co-sum" }, [el("summary", { text: TXT.params + " (" + cfg.summary.length + ")" }), el("dl", {}, cfg.summary.reduce(function (a, s) { a.push(el("dt", { text: s.label }), el("dd", { text: s.value })); return a; }, []))]) : null;
        linesHost.appendChild(el("article", { class: "emb-co-line" + (bad ? " is-bad" : "") }, [
          el("div", { class: "emb-co-line-l" }, [el("strong", { text: (ln && ln.name) || "Stůl" }), el("p", { class: "mw-fine", text: cfg && cfg.kod ? "Kód konfigurace: " + cfg.kod : (it.kod ? "Kód konfigurace: " + it.kod : "") }),
                                                  bad ? el("p", { class: "emb-co-warn", text: TXT.invalidLine }) : null, sum, mz]),
          el("div", { class: "emb-co-line-r" }, [el("label", { class: "mw-qty" }, [el("span", { class: "mw-label", text: TXT.qty }), q]),
                                                  ln && ln.line_total_czk != null ? el("p", { class: "emb-co-lineprice" }, [el("strong", { text: fmt(ln.line_total_czk) }), el("small", { text: " " + TXT.exclVat }),
                                                                                                    ln.line_total_with_vat_czk != null ? el("small", { class: "emb-co-gross", text: fmt(ln.line_total_with_vat_czk) + " " + TXT.inclVat }) : null]) : null, rm])
        ]));
      });
    }
    function row(label, value, cls) { return el("div", { class: "emb-co-row" + (cls ? " " + cls : "") }, [el("span", { text: label }), el("span", { text: value })]); }
    function renderTotals() {
      totalsHost.textContent = "";
      if (!items.length) return;
      if (qState === "pending" && !quote) { totalsHost.appendChild(el("p", { class: "mw-muted", text: TXT.pending })); return; }
      if (qState === "error" || !quote) {
        var retry = el("button", { type: "button", class: "mw-link", text: TXT.retry }); retry.addEventListener("click", requestQuote);
        totalsHost.appendChild(el("p", { class: "emb-co-warn" }, [TXT.quoteError + " ", retry])); return;
      }
      totalsHost.appendChild(row(TXT.goods, fmt(quote.subtotal_goods_czk)));
      if (quote.subtotal_montaz_czk > 0) totalsHost.appendChild(row(TXT.montazRow, fmt(quote.subtotal_montaz_czk)));
      totalsHost.appendChild(row(TXT.totalNet, fmt(quote.subtotal_czk), "is-strong"));
      if (quote.vat) { totalsHost.appendChild(row(TXT.vat + " " + quote.vat.rate + " %", fmt(quote.vat.amount))); totalsHost.appendChild(row(TXT.totalGross, fmt(quote.vat.total_with_vat), "is-total")); }
      if (qState === "pending") totalsHost.classList.add("is-stale"); else totalsHost.classList.remove("is-stale");
    }
    function renderShipping() {
      var cur = (shipHost.querySelector("input:checked") || {}).value;
      while (shipHost.childNodes.length > 1) shipHost.removeChild(shipHost.lastChild);
      var opts = ((quote && quote.shipping_options) || []).filter(function (s) { return s.id !== "toptrans" || s.net != null; });     // Toptrans jen s odhadem; jinak cenu urci zamestnanec ("po dohode")
      if (!opts.length) opts = [{ id: "quote", label: "Doprava po dohodě (cenu upřesníme)", net: null }, { id: "pickup", label: "Osobní odběr", net: 0 }];
      var keep = opts.some(function (s) { return s.id === cur; }) ? cur : opts[0].id;
      opts.forEach(function (s) {
        var price = s.net == null ? "" : (s.net === 0 ? " (" + TXT.shipFree + ")" : " (" + (s.estimated ? TXT.shipEstimate + " " : "") + fmt(s.net) + " " + TXT.exclVat + ")");
        shipHost.appendChild(el("label", { class: "mw-opt" }, [el("input", { type: "radio", name: "shipping", value: s.id, checked: s.id === keep ? true : null }), el("span", { text: s.label + price })]));
      });
    }
    function render() {
      var hasBad = !!(quote && quote.lines && quote.lines.some(function (l) { return l.configuration && l.configuration.valid === false; }));
      renderLines(); renderTotals(); renderShipping();
      submit.disabled = busy || !items.length || qState !== "ok" || hasBad;
      form.hidden = !items.length || !!sent;
      shipNote.hidden = !items.length || !!sent;
      o.sendHeightSoon();
    }

    // ---------------------------------------------------------------- kosik a quote
    function apiItems() { return items.map(function (i) { return { product_id: i.pid, qty: i.qty, montaz: !!i.montaz, configuration: { selection: i.selection, rules_version: i.rules_version } }; }); }
    function mergeSame() {
      var seen = {}, out = [];
      items.forEach(function (i) { var k = lineKey(i); if (seen[k]) { seen[k].qty = Math.min(MAX_QTY, seen[k].qty + i.qty); } else { seen[k] = i; out.push(i); } });
      items = out;
    }
    function changed() { writeCart(items); listeners.forEach(function (f) { try { f(items.length); } catch (e) { /* nic */ } }); if (items.length) requestQuote(); else { quote = null; qState = "idle"; render(); } }
    function requestQuote() {
      if (!items.length) { render(); return; }
      var my = ++qSeq; qState = "pending"; renderTotals(); submit.disabled = true;
      var body = { items: apiItems() }, zip = zipDigits("d_zip"); if (zip.length === 5) body.delivery_zip = zip;
      postJSON("/api/shop/stul/quote", body).then(function (x) {
        if (my !== qSeq) return;
        if (x.st === 200 && x.d && Array.isArray(x.d.lines)) {
          quote = x.d; qState = "ok";
          if (quote.lines.length !== items.length) {                                // server sloucil shodne radky: prevezmeme jeho pohled (platne radky)
            items = quote.lines.filter(function (l) { return l.configuration && l.configuration.valid !== false && l.configuration.hash; }).map(function (l) { return { pid: l.product_id, qty: l.qty, montaz: !!l.montaz_zvolena, can: true, selection: l.configuration.selection, rules_version: l.configuration.rules_version, hash: l.configuration.hash, kod: l.configuration.kod || "" }; });
            writeCart(items); quote = null; requestQuote(); return;
          }
        } else { quote = null; qState = "error"; }
        render();
      }).catch(function () { if (my !== qSeq) return; quote = null; qState = "error"; render(); });
    }

    // ---------------------------------------------------------------- odeslani
    function validate() {
      clearErrs(); var bad = null;
      function need(n, msgKey, ok) { if (!ok) { setErr(n, ERR[msgKey]); if (!bad) bad = n; } }
      need("name", "name_required", val("name").length > 0);
      need("email", "email_invalid", EMAIL_RE.test(val("email")) && val("email").indexOf("..") < 0 && val("email").length <= 254);
      need("phone", "phone_invalid", PHONE_RE.test(val("phone")));
      need("d_street", "street_required", val("d_street").length > 0); need("d_city", "city_required", val("d_city").length > 0); need("d_zip", "zip_invalid", ZIP_RE.test(val("d_zip")) && zipDigits("d_zip").length === 5);
      if (!F.billing_same.input.checked) { need("b_street", "street_required", val("b_street").length > 0); need("b_city", "city_required", val("b_city").length > 0); need("b_zip", "zip_invalid", ZIP_RE.test(val("b_zip")) && zipDigits("b_zip").length === 5); }
      need("consent", "consent_required", F.consent.input.checked);
      if (bad) { formMsg.textContent = TXT.fillRequired; formMsg.className = "emb-co-msg is-err"; F[bad].input.focus(); }
      return !bad;
    }
    function serverError(x) {
      var d = x.d || {}, code = d.error || "", text = ERR[code] || TXT.generic;
      if (code === "price_changed") { text = "Cena se mezitím změnila" + (d.current_total_net != null ? " na " + fmt(d.current_total_net) + " " + TXT.exclVat : "") + ". Zkontrolujte souhrn a odešlete objednávku znovu."; requestQuote(); }
      else if (code === "rules_changed" || code === "invalid_configuration" || code === "montaz_unavailable") requestQuote();
      var f = d.field && FIELD[d.field];
      if (f && F[f]) { setErr(f, text); F[f].input.focus(); formMsg.textContent = TXT.fillRequired; } else formMsg.textContent = text;
      formMsg.className = "emb-co-msg is-err";
    }
    form.addEventListener("submit", function (ev) {
      ev.preventDefault();
      if (busy || !validate()) return;
      if (!quote || qState !== "ok") { formMsg.textContent = qState === "error" ? TXT.quoteError : TXT.pending; formMsg.className = "emb-co-msg is-err"; return; }
      var same = F.billing_same.input.checked, body = {
        items: apiItems(), name: val("name"), email: val("email"), phone: val("phone"), company: val("company") || undefined, company_id: val("company") && val("company_id") ? val("company_id") : undefined, vat_id: val("company") && val("vat_id") ? val("vat_id") : undefined,
        delivery: { street: val("d_street"), city: val("d_city"), zip: val("d_zip") }, billing: same ? { same: true } : { street: val("b_street"), city: val("b_city"), zip: val("b_zip") },
        shipping: (shipHost.querySelector("input:checked") || {}).value || "quote", payment: "transfer", consent: true, note: val("note") || undefined,
        expected_total_net: quote.subtotal_czk, website: (form.querySelector("input[name=website]") || {}).value || ""
      };
      busy = true; submit.textContent = TXT.sending; submit.disabled = true; formMsg.textContent = ""; formMsg.className = "emb-co-msg";
      postJSON("/api/shop/stul/order", body).then(function (x) {
        busy = false; submit.textContent = TXT.submit;
        if (x.st === 200 || x.st === 201) { done(x.d); } else { serverError(x); render(); }
      }).catch(function () { busy = false; submit.textContent = TXT.submit; formMsg.textContent = TXT.network; formMsg.className = "emb-co-msg is-err"; render(); });
    });
    function done(d) {
      sent = d || {}; items = []; writeCart(items); listeners.forEach(function (f) { try { f(0); } catch (e) { /* nic */ } });
      var t = d && d.total ? d.total : null;
      okBox.textContent = "";
      okBox.appendChild(el("h3", { text: TXT.sentTitle }));
      if (d && d.reference) okBox.appendChild(el("p", {}, [TXT.sentRef + ": ", el("strong", { text: d.reference })]));
      okBox.appendChild(el("p", { text: TXT.sentNext }));
      if (t && t.net != null) okBox.appendChild(el("p", { class: "mw-fine", text: TXT.sentTotal + ": " + fmt(t.net) + " " + TXT.exclVat + (t.total_with_vat != null ? " · " + fmt(t.total_with_vat) + " " + TXT.inclVat : "") }));
      var again = el("button", { type: "button", class: "mw-btn", text: TXT.another });
      again.addEventListener("click", function () { sent = null; okBox.hidden = true; form.reset(); syncBilling(); syncCompany(); clearErrs(); close(); });
      okBox.appendChild(again); okBox.hidden = false; form.hidden = true; linesHost.hidden = true; totalsHost.hidden = true; shipNote.hidden = true; head.hidden = true;
      o.sendHeightSoon(); o.notifyParent({ type: "stul-embed-scroll" });
    }

    // ---------------------------------------------------------------- otevreni / zavreni
    backBtn.addEventListener("click", function () { close(); });
    var consentUpgraded = false;
    function upgradeConsent() {                                           // stranky podminek a ochrany udaju existuji -> souhlas s odkazy (otevrou se v novem panelu, objednavka zustane)
      if (consentUpgraded) return;
      consentPagesExist().then(function (ok) {
        if (!ok || consentUpgraded) return;
        consentUpgraded = true;
        var lab = F.consent.label; lab.textContent = "";
        function link(url, text) { return el("a", { href: url, target: "_blank", rel: "noopener", text: text }); }
        [TXT.consentPre, link(CONSENT_PAGES.terms, TXT.consentTerms), TXT.consentMid, link(CONSENT_PAGES.privacy, TXT.consentPriv), TXT.consentEnd].forEach(function (n) { lab.appendChild(typeof n === "string" ? document.createTextNode(n) : n); });
        o.sendHeightSoon();
      });
    }
    function open() {
      upgradeConsent(); mergeSame(); sent = null; okBox.hidden = true; linesHost.hidden = false; totalsHost.hidden = false; head.hidden = false;
      root.hidden = false; if (o.generator) o.generator.hidden = true;
      syncBilling(); syncCompany(); quote = null; render(); if (items.length) requestQuote();
      o.notifyParent({ type: "stul-embed-scroll" }); o.sendHeightSoon();
      try { title.focus({ preventScroll: true }); } catch (e) { /* nic */ }
    }
    function close() {
      root.hidden = true; if (o.generator) o.generator.hidden = false;
      o.notifyParent({ type: "stul-embed-scroll" }); o.sendHeightSoon();
    }
    function add(line) {                                                    // line: {pid, qty, montaz, selection, rules_version, hash, kod}
      var l = { pid: Number(line.pid), qty: Math.max(1, Math.min(MAX_QTY, parseInt(line.qty, 10) || 1)), montaz: !!line.montaz, can: !!line.can, selection: line.selection, rules_version: line.rules_version || null, hash: String(line.hash || ""), kod: String(line.kod || "") };
      if (!validLine(l)) return false;
      if (items.length >= MAX_LINES && !items.some(function (i) { return lineKey(i) === lineKey(l); })) return false;
      items.push(l); mergeSame(); writeCart(items); listeners.forEach(function (f) { try { f(items.length); } catch (e) { /* nic */ } });
      return true;
    }
    return { add: add, open: open, close: close, count: function () { return items.length; }, onChange: function (f) { listeners.push(f); }, isOpen: function () { return !root.hidden; } };
  }

  global.StulObjednavka = { create: create, TXT: TXT, readCart: readCart };
})(window);
