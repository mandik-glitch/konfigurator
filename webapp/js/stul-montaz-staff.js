/* stul-montaz-staff.js - pole "Montaz (% z ceny stolu)" v ZAMESTNANECKEM Generatoru stolu (stul-konfigurator.html a -40.html; Robert 2026-10-04 pres bot9: "tech 12 % za montaz v generatoru
   volim primo v nem"). Samostatny modul, ktery se jen pripoji do okna (napr. Cena a scena): window.StulMontazStaff.mount(hostElement).
   API (bot5, api/stul_montaz.py): GET /api/stul/montaz -> {pct, default, available, stored}; PUT /api/stul/montaz {pct} (0-100; 0 = montaz se nenabizi), RBAC nastaveni/upravit, audit.
   Pole se ukaze JEN kdyz server odpovi (statika jde zive driv nez nasazene API; nepřihlášený / bez prava / starý server = pole zustane skryte).
   Zakaznik procento NIKDE nevidi (ve verejnych odpovedich a v generatoru je jen castka); montaz je vzdy volitelna a plati pro vsechny stoly, hosty i prihlasene. */
(function (global) {
  "use strict";
  function el(tag, attrs, kids) {
    var e = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) { var v = attrs[k]; if (v == null || v === false) return; if (k === "class") e.className = v; else if (k === "text") e.textContent = v; else e.setAttribute(k, v === true ? "" : v); });
    (kids == null ? [] : (Array.isArray(kids) ? kids : [kids])).forEach(function (c) { if (c != null) e.appendChild(typeof c === "string" ? document.createTextNode(c) : c); });
    return e;
  }
  var MSG = { pct_invalid: "Zadej číslo od 0 do 100 (0 = montáž se nenabízí).", 403: "Na změnu sazby montáže nemáš oprávnění.", fail: "Uložení se nepovedlo.", net: "Spojení selhalo." };

  function mount(host, opt) {
    opt = opt || {};
    var input = el("input", { type: "text", inputmode: "decimal", id: "montazPct", autocomplete: "off", "aria-describedby": "montazStav", style: "width:6rem;" });
    var save = el("button", { type: "button", id: "montazUloz", text: "Uložit" });
    var reset = el("button", { type: "button", id: "montazVychozi", class: "sh-ghost", text: "Výchozí" });
    var stav = el("div", { id: "montazStav", role: "status", class: "small" });
    var note = el("div", { class: "small", text: "Zákazník vidí jen částku, ne procento; montáž je vždy volitelná a platí pro všechny stoly (hosty i přihlášené). 0 = montáž se nenabízí." });
    var box = el("div", { class: "sh-montaz", id: "staffMontaz", hidden: true, style: "margin-top:12px;padding-top:10px;border-top:1px solid var(--line, #3a3f4a);" },
                 [el("label", { for: "montazPct", text: "Montáž (% z ceny stolu)" }), el("div", { class: "sh-btns", style: "align-items:center;" }, [input, el("span", { text: "%" }), save, reset]), stav, note]);
    host.appendChild(box);
    var state = { def: 12 };
    function say(t, bad) { stav.textContent = t || ""; stav.style.color = bad ? "var(--error, #e07070)" : "var(--muted, #8b93a1)"; }
    function show(d) {
      state.def = d.default != null ? Number(d.default) : 12;
      input.value = String(d.pct); box.hidden = false;
      reset.textContent = "Výchozí (" + state.def + ")";
      say(d.stored ? "" : "Zatím nenastaveno – platí výchozí sazba " + state.def + " %.", false);
    }
    function put(pct) {
      say("Ukládám…", false); save.disabled = reset.disabled = true;
      fetch("/api/stul/montaz", { method: "PUT", credentials: "same-origin", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ pct: pct }) })
        .then(function (r) { return r.json().catch(function () { return {}; }).then(function (d) { return { ok: r.ok, st: r.status, d: d }; }); })
        .then(function (x) {
          save.disabled = reset.disabled = false;
          if (!x.ok) { say(x.d && x.d.error === "pct_invalid" ? MSG.pct_invalid : (MSG[x.st] || MSG.fail), true); return; }
          show(Object.assign({ stored: true }, x.d, { pct: x.d.pct != null ? x.d.pct : pct }));
          say("Uloženo: " + (x.d.pct != null ? x.d.pct : pct) + " %" + (Number(pct) === 0 ? " – montáž se zákazníkům nenabízí." : ". Platí hned pro nové kalkulace a objednávky."), false);
          if (opt.onSaved) opt.onSaved(x.d);
        }).catch(function () { save.disabled = reset.disabled = false; say(MSG.net, true); });
    }
    save.addEventListener("click", function () {
      var v = String(input.value || "").replace(/\s+/g, "").replace(",", ".");
      if (!/^\d{1,3}(\.\d{1,2})?$/.test(v) || Number(v) < 0 || Number(v) > 100) { say(MSG.pct_invalid, true); input.focus(); return; }
      put(Number(v));
    });
    reset.addEventListener("click", function () { put(state.def); });
    fetch("/api/stul/montaz", { credentials: "same-origin" }).then(function (r) { return r.ok ? r.json() : null; }).then(function (d) { if (d && d.pct != null) show(d); }).catch(function () { /* nepřihlášený / bez práva / starý server: pole zůstane skryté */ });
    return box;
  }
  global.StulMontazStaff = { mount: mount };
})(window);
