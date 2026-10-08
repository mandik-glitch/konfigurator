/* miniweb/stul-ulozeni.js - "Ulozit konfiguraci" v generatoru stolu na vsech webech (bot16, 2026-10-05; Robert: "Konfigurace ma zmizet, neulozit se po zavreni prohlizece. Nabidneme moznost ulozeni
   konfigurace po zadani ICO, email, telefon (overit platnost ICO a emailu pred ulozenim)"). Sdilena komponenta: vlozeny generator (embed/stul-embed.js, kategorie a karty ve ramu) a karta
   produktu mini-shopu (miniweb/miniweb-pages.js). Backend: api/stul_ulozeni.py (POST /api/shop/configurator/ulozit, GET .../ulozena/<token>; pod /api/shop/configurator/, ktere nginx mini-shopu
   propousti). Prohlizec NIC o konfiguraci nedrzi: tlacitko ulozi na server az po overeni ICO v registru a e-mailu; zakaznik dostane odkaz pro navrat (e-mailem se nic neposila).
   Funkce je VYPNUTA, dokud backend neexistuje (obecne 404 starsiho serveru) nebo nema tabulku (503) nebo hostitel nema texty ulozeni.* (bot7): probe vyzaduje 404 se znackou {"error":"not_found","ulozeni":1} a tlacitko se jinak vubec neukaze.
   Pouziti: var s = StulUlozeni.create({ t: function (key, vars) -> text ("" kdyz chybi), getPayload: function () -> null | {product_id, configuration:{selection, rules_version}},
                                         country: "CZ"|"SK"|undefined, privacyHref: string|Promise|null, privacyLabel: string, linkFor: function (token) -> url, onChange: function (), onSaved: function (r), onOpen: function (formBox) (po otevreni formulare, napr. odscrollovat),
                                         onRulesChanged: function () (host nacte nove schema generatoru, napr. ctl.refresh(); volano pri 409 rules_changed) });
              host.appendChild(s.el); s.update() po kazdem vypoctu; s.notice(text) = zprava (napr. "Ulozena konfigurace byla nactena"). */
(function (global) {
  "use strict";
  var SAVE_URL = "/api/shop/configurator/ulozit", GET_URL = "/api/shop/configurator/ulozena/";
  var PROBE_TOKEN = "AAAAAAAAAAAAAAAAAAAAAA";

  function el(tag, attrs, kids) {
    var e = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) { var v = attrs[k]; if (v == null || v === false) return; if (k === "class") e.className = v; else if (k === "text") e.textContent = v; else e.setAttribute(k, v === true ? "" : v); });
    (kids == null ? [] : (Array.isArray(kids) ? kids : [kids])).forEach(function (c) { if (c != null) e.appendChild(typeof c === "string" ? document.createTextNode(c) : c); });
    return e;
  }

  var probeP = null;                                           // zapnuto = backend ma tabulku (GET probe vraci 404 not_found); 503 / jina odpoved = vypnuto
  function probe() {
    if (!probeP) probeP = fetch(GET_URL + PROBE_TOKEN, { credentials: "same-origin" }).then(function (r) { return r.status === 404 ? r.json().then(function (d) { return !!d && d.error === "not_found" && d.ulozeni === 1; }) : false; }).catch(function () { return false; });
    return probeP;
  }
  // ulozena konfigurace podle tokenu z odkazu: Promise<{product_id, system, selection, rules_version, kod}|null>
  function load(token) {
    if (!/^[A-Za-z0-9_-]{16,32}$/.test(token || "")) return Promise.resolve(null);
    return fetch(GET_URL + encodeURIComponent(token), { credentials: "same-origin" }).then(function (r) { return r.ok ? r.json() : null; }).catch(function () { return null; });
  }
  function tokenFromUrl(search) {
    var m = /(?:^|[?&])ulozena=([A-Za-z0-9_-]{16,32})(?:&|$)/.exec(String(search || ""));
    return m ? m[1] : null;
  }

  function create(o) {
    var T = function (k, v) { var s = o.t(k, v); return typeof s === "string" ? s : ""; };
    var root = el("div", { class: "pdc-save", hidden: true });
    var state = "closed", btn = null, formBox = null, built = false;
    var fields = {};

    function changed() { if (typeof o.onChange === "function") { try { o.onChange(); } catch (e) { /* nic */ } } }
    function show(s) { state = s; render(); changed(); }

    function fieldBox(name, label, type, extra) {
      var input = el("input", Object.assign({ type: type, name: name, id: "pdcSave_" + name, required: true, "aria-describedby": "pdcSaveErr_" + name }, extra || {}));
      var err = el("div", { class: "pdc-save-err", id: "pdcSaveErr_" + name, role: "alert" });
      var box = el("div", { class: "pdc-save-field" }, [el("label", { for: "pdcSave_" + name, text: label }), input, err]);
      fields[name] = { box: box, input: input, err: err };
      input.addEventListener("input", function () { setErr(name, ""); });
      return box;
    }
    function setErr(name, text) {
      var f = fields[name]; if (!f) return;
      f.err.textContent = text || ""; f.box.classList.toggle("is-bad", !!text);
      if (text) f.input.setAttribute("aria-invalid", "true"); else f.input.removeAttribute("aria-invalid");
    }
    function say(text, bad) { if (status) { status.textContent = text || ""; status.classList.toggle("is-bad", !!bad); } changed(); }

    var status = null, submit = null, doneBox = null, notes = el("div", { class: "pdc-save-notice", role: "status", "aria-live": "polite", hidden: true });

    function build() {
      built = true;
      btn = el("button", { type: "button", class: "pdc-save-btn", text: T("ulozeni.btn") });
      btn.addEventListener("click", function () { show(state === "form" ? "closed" : "form"); if (state === "form") { if (fields.ico) fields.ico.input.focus(); if (typeof o.onOpen === "function") { try { o.onOpen(formBox); } catch (e) { /* nic */ } } } });
      status = el("div", { class: "pdc-save-status", role: "status", "aria-live": "polite" });
      var consent = el("input", { type: "checkbox", name: "consent", id: "pdcSave_consent", required: true });
      var consentLabel = el("label", { for: "pdcSave_consent" }, [el("span", { text: T("ulozeni.souhlas") })]);
      if (o.privacyHref) Promise.resolve(o.privacyHref).then(function (h) {                          // odkaz na ochranu udaju (string nebo Promise: stranka se overuje HEAD dotazem, ukaze se jen kdyz existuje)
        if (h && o.privacyLabel) { consentLabel.appendChild(document.createTextNode(" ")); consentLabel.appendChild(el("a", { href: h, target: "_blank", rel: "noopener", text: o.privacyLabel })); changed(); }
      });
      var consentErr = el("div", { class: "pdc-save-err", id: "pdcSaveErr_consent", role: "alert" });
      fields.consent = { box: el("div", { class: "pdc-save-consent" }, [consent, el("div", {}, [consentLabel, consentErr])]), input: consent, err: consentErr };
      consent.addEventListener("change", function () { setErr("consent", ""); });
      var hp = el("input", { type: "text", name: "website", tabindex: "-1", autocomplete: "off", "aria-hidden": "true" });
      submit = el("button", { type: "submit", class: "pdc-save-go", text: T("ulozeni.uloz") });
      var cancel = el("button", { type: "button", class: "pdc-save-cancel", text: T("ulozeni.zrusit") });
      cancel.addEventListener("click", function () { say(""); show("closed"); });
      formBox = el("form", { class: "pdc-save-form", novalidate: true, autocomplete: "on" }, [
        el("h4", { class: "pdc-save-h", text: T("ulozeni.nadpis") }), el("p", { class: "pdc-save-intro", text: T("ulozeni.uvod") }),
        fieldBox("ico", T("ulozeni.ico"), "text", { inputmode: "numeric", autocomplete: "off", maxlength: "12" }),
        fieldBox("email", T("ulozeni.email"), "email", { autocomplete: "email", maxlength: "254" }),
        fieldBox("phone", T("ulozeni.telefon"), "tel", { autocomplete: "tel", maxlength: "40" }),
        fields.consent.box, el("div", { class: "pdc-save-hp", "aria-hidden": "true" }, [hp]),
        el("div", { class: "pdc-save-actions" }, [submit, cancel]), status
      ]);
      formBox.addEventListener("submit", onSubmit);
      doneBox = el("div", { class: "pdc-save-done", role: "status", "aria-live": "polite" });
      root.appendChild(notes); root.appendChild(btn); root.appendChild(formBox); root.appendChild(doneBox);
      render();
    }

    function validate() {
      var ok = true, ico = fields.ico.input.value.replace(/\s+/g, ""), em = fields.email.input.value.trim(), ph = fields.phone.input.value.replace(/[\s().\-/]/g, "");
      if (!/^\d{6,8}$/.test(ico)) { setErr("ico", T("ulozeni.err.ico_invalid")); ok = false; }
      if (!/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(em) || em.length > 254 || /\.\./.test(em)) { setErr("email", T("ulozeni.err.email_invalid")); ok = false; }
      if (!/^\+?\d{9,15}$|^00\d{9,15}$/.test(ph)) { setErr("phone", T("ulozeni.err.phone_invalid")); ok = false; }
      if (!fields.consent.input.checked) { setErr("consent", T("ulozeni.err.consent_required")); ok = false; }
      return ok;
    }

    function onSubmit(ev) {
      ev.preventDefault();
      ["ico", "email", "phone", "consent"].forEach(function (n) { setErr(n, ""); });
      var payload = o.getPayload ? o.getPayload() : null;
      if (!payload) { say(T("ulozeni.err.config_invalid"), true); return; }
      if (!validate()) { changed(); return; }
      var body = { product_id: payload.product_id, configuration: payload.configuration, ico: fields.ico.input.value.replace(/\s+/g, ""), email: fields.email.input.value.trim(), phone: fields.phone.input.value.trim(),
                   consent: true, website: formBox.querySelector("input[name=website]").value };
      if (o.country) body.country = o.country;
      submit.disabled = true; say(T("ulozeni.overuji"), false);
      fetch(SAVE_URL, { method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) })
        .then(function (r) { return r.json().catch(function () { return {}; }).then(function (d) { return { st: r.status, d: d || {} }; }); })
        .then(function (x) {
          submit.disabled = false;
          if (x.st === 201 && x.d.token) { done(x.d); return; }
          var code = x.d && x.d.error, key = ({ rules_changed: "pdc.rulesChanged", product_not_available: "ulozeni.err.config_invalid", too_many: "ulozeni.err.rate_limited" })[code] || "ulozeni.err." + code;
          var msg = T(key) || T("ulozeni.err.unavailable");
          if (code === "rules_changed" && typeof o.onRulesChanged === "function") { try { o.onRulesChanged(); } catch (e) { /* nic */ } }          // stara stranka: modul nacte nove schema, formular zustane vyplneny, zakaznik klikne znovu
          if (x.d && x.d.field && fields[x.d.field] && x.d.field !== "configuration") { setErr(x.d.field, msg); say("", false); fields[x.d.field].input.focus(); } else say(msg, true);
        }).catch(function () { submit.disabled = false; say(T("ulozeni.err.unavailable"), true); });
    }

    function done(d) {
      var url = typeof o.linkFor === "function" ? o.linkFor(d.token) : "";
      var linkInput = el("input", { type: "text", class: "pdc-save-link", readonly: true, value: url, "aria-label": T("ulozeni.odkaz") });
      var copy = el("button", { type: "button", class: "pdc-save-copy", text: T("ulozeni.kopirovat") });
      copy.addEventListener("click", function () {
        function ok() { copy.textContent = T("ulozeni.zkopirovano"); setTimeout(function () { copy.textContent = T("ulozeni.kopirovat"); }, 2000); }
        if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(url).then(ok, function () { linkInput.select(); try { document.execCommand("copy"); ok(); } catch (e) { /* nic */ } });
        else { linkInput.select(); try { document.execCommand("copy"); ok(); } catch (e) { /* nic */ } }
      });
      linkInput.addEventListener("focus", function () { linkInput.select(); });
      doneBox.textContent = "";
      doneBox.appendChild(el("p", { class: "pdc-save-ok", text: T("ulozeni.hotovo") }));
      if (d.firma) doneBox.appendChild(el("p", { class: "pdc-save-firma", text: T("ulozeni.firma", { name: d.firma }) }));
      doneBox.appendChild(el("label", { class: "pdc-save-linklbl", text: T("ulozeni.odkaz") }));
      doneBox.appendChild(el("div", { class: "pdc-save-linkrow" }, [linkInput, copy]));
      doneBox.appendChild(el("p", { class: "pdc-save-note", text: T("ulozeni.poznamka") }));
      show("done");
      try { linkInput.focus({ preventScroll: true }); linkInput.select(); } catch (e) { /* nic */ }
      if (typeof o.onSaved === "function") { try { o.onSaved(d); } catch (e) { /* nic */ } }
    }

    function render() {
      if (!built) return;
      formBox.hidden = state !== "form"; doneBox.hidden = state !== "done"; btn.hidden = state === "done";
      btn.setAttribute("aria-expanded", state === "form" ? "true" : "false");
      btn.disabled = !(o.getPayload && o.getPayload());
    }

    probe().then(function (on) { if (!on || !T("ulozeni.btn")) return; root.hidden = false; build(); changed(); });
    return {
      el: root,
      update: function () { render(); },
      notice: function (text) { if (!built) { var tries = 0; var iv = setInterval(function () { if (built || ++tries > 20) { clearInterval(iv); if (built) show2(text); } }, 200); } else show2(text); function show2(t) { notes.textContent = t || ""; notes.hidden = !t; changed(); } },
      reset: function () { if (!built) return; state = "closed"; doneBox.textContent = ""; render(); }
    };
  }

  global.StulUlozeni = { create: create, probe: probe, load: load, tokenFromUrl: tokenFromUrl };
})(window);
