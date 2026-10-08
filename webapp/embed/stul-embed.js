/* stul-embed.js - verejny vlozitelny generator stolu (iframe na logiman.cz a na strance kategorie 206). Hostitel modulu voleb (js/product-configurator.js) v mrizce oken
   (js/pdc-layout.js): 3D, cena + tlacitko Objednat, volby po skupinach, vyrezy a loziska. Bez zamestnaneckych oken (kusovnik, pravidla, HDRI); pro zobrazeni staci verejne API
   /api/shop/*, objednani (POST /api/cart/items, kontrakt bot5) vyzaduje prihlaseneho zakaznika.
   Povoleny rodic: logiman.cz, www.logiman.cz a vlastni origin (kontrola puvodu rodice; pravou ochranu hlavickou frame-ancestors lze doplnit v nginx, viz docs/EMBED_STUL.md).
   Montaz (volitelna, % z ceny stolu nastavuje zamestnanec v Generatoru stolu; zakaznik vidi JEN radek "Montaz" s castkou, BEZ procenta - Robert 2026-10-04): castku dodava server (POST /api/shop/stul/quote s montaz true/false), v prohlizeci se nepocita.
   Nepřihlášený zakaznik objedna jako HOST (stul-embed-objednavka.js: souhrn -> udaje -> doprava -> odeslat), ucet zustava volitelny ("Mate ucet? Prihlasit se").
   Rodici posila: {type:"stul-embed-height", height}, {type:"stul-embed-scroll"} (rodic ma iframe posunout na zacatek) a po pridani do kosiku uctu {type:"stul-embed-cart-added"}. Od povoleneho rodice prijima {type:"stul-embed-theme", theme, accent}
   a {type:"stul-embed-viewport", height} (vyska okna rodice -> vyska 3D okna). Parametry adresy: ?p=<id produktu> ?theme=light|dark ?accent=%23rrggbb ?vh=<vyska okna rodice v px>. */
(function () {
  "use strict";
  var Q = new URLSearchParams(location.search), PID = /^\d{1,7}$/.test(Q.get("p") || "") ? Q.get("p") : "4934";
  var ALLOW = ["https://logiman.cz", "https://www.logiman.cz", location.origin];       // + vlastni web (kategorie 206 na autovestavby.logiman.cz vklada generator ve stejnem originu)
  var CART_URL = "/product.html?openCart=1", INQUIRY_URL = "/poptavka-stul.html", QUOTE_URL = "/api/shop/stul/quote";
  var TILE_JS = "/js/pripni-cokoli-tile.js?v=6ed7fc6c7c", V3D_CSS = "/css/v3d.css?v=c76cbe7292";          // ukazka Pripni cokoli (PdcLayout.attachWindow); ?v= verzuje scripts/miniweb_verze.py
  var app = document.getElementById("app");
  var framed = window.top !== window.self, sameParent = false;
  if (framed) { try { void window.top.location.pathname; sameParent = true; } catch (e) { sameParent = false; } }
  if (!framed) document.documentElement.classList.add("emb-standalone");              // samostatne otevrena stranka (nahled): nepruhledne pozadi motivu; v iframe je pruhledne (pozadi dava rodic)
  var LINK_TARGET = !framed ? "_self" : sameParent ? "_top" : "_blank";                // odkazy z iframe: stejny web = cele okno, cizi rodic = novy panel (stranka rodice zustane)

  // motiv a akcentova barva hostitele: ?theme=light|dark, ?accent=%23rrggbb; za behu zprava {type:"stul-embed-theme", theme, accent} od povoleneho rodice
  function applyLook(theme, accent) {
    if (theme === "light" || theme === "dark") document.documentElement.setAttribute("data-theme", theme);
    if (typeof accent === "string" && /^#[0-9a-f]{6}$/i.test(accent)) { document.documentElement.style.setProperty("--accent", accent); document.documentElement.style.setProperty("--accent-glow", accent); }
  }
  // vyska 3D okna na sirokem: ~65 % vysky okna rodice, 560-900 px (ne z vlastni vysky iframe - ta se ridi obsahem, vznikla by zpetna vazba)
  function applyStageHeight(vh) {
    vh = Number(vh); if (!isFinite(vh) || vh < 300 || vh > 6000) return;
    document.documentElement.style.setProperty("--emb-stage-h", Math.max(560, Math.min(900, Math.round(vh * 0.65))) + "px");
  }
  applyLook(Q.get("theme"), Q.get("accent"));
  applyStageHeight(Q.get("vh"));
  if (sameParent && framed) { try { applyStageHeight(window.parent.innerHeight); } catch (e) { /* nic */ } }
  window.addEventListener("message", function (e) {
    if (ALLOW.indexOf(e.origin) < 0 || !e.data) return;
    if (e.data.type === "stul-embed-theme") applyLook(e.data.theme, e.data.accent);
    else if (e.data.type === "stul-embed-viewport") applyStageHeight(e.data.height);
  });

  function parentOrigin() {
    try { if (location.ancestorOrigins && location.ancestorOrigins.length) return location.ancestorOrigins[0]; } catch (e) { /* nic */ }
    try { return document.referrer ? new URL(document.referrer).origin : null; } catch (e) { return null; }
  }
  if (framed) {                                             // v iframe: rodic, ktereho umime poznat a neni na seznamu, generator nenacte (neznamy rodic se nepusti dal nez dosud)
    var po = parentOrigin();
    if (po && ALLOW.indexOf(po) < 0) { app.innerHTML = '<div class="emb-blocked">Tento generátor lze vložit jen na stránky logiman.cz.</div>'; return; }
  }

  function el(tag, attrs, kids) {
    var e = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) { var v = attrs[k]; if (v == null || v === false) return; if (k === "class") e.className = v; else if (k === "text") e.textContent = v; else e.setAttribute(k, v === true ? "" : v); });
    (kids == null ? [] : (Array.isArray(kids) ? kids : [kids])).forEach(function (c) { if (c != null) e.appendChild(typeof c === "string" ? document.createTextNode(c) : c); });
    return e;
  }
  function notifyParent(msg) { if (window.parent === window) return; try { window.parent.postMessage(msg, "*"); } catch (e) { /* nic */ } }
  function sendHeight() {
    var h = Math.ceil(Math.max(document.documentElement.scrollHeight, document.body.scrollHeight));
    notifyParent({ type: "stul-embed-height", height: h });
  }
  var hTimer = null; function sendHeightSoon() { clearTimeout(hTimer); hTimer = setTimeout(sendHeight, 60); }

  // rozdelana konfigurace pres prihlaseni: pri 401 se vyber ulozi (30 min), po navratu z prihlaseni se obnovi a (je-li zakaznik prihlaseny) sama prida do kosiku
  var PKEY = "stulEmbedPending";
  try { localStorage.removeItem(PKEY); } catch (e) { /* nic */ }                    // drive localStorage (preziv zavreni prohlizece): konfigurace se po zavreni prohlizece NEUCHOVAVA (Robert 2026-10-05), jen po dobu relace
  function readPending() {
    try { var o = JSON.parse(sessionStorage.getItem(PKEY) || "null"); if (o && o.pid === PID && o.selection && typeof o.selection === "object" && Date.now() - o.ts < 30 * 60 * 1000) return o; } catch (e) { /* nic */ }
    return null;
  }
  function writePending(sel, montaz) { try { sessionStorage.setItem(PKEY, JSON.stringify({ pid: PID, selection: sel, montaz: !!montaz, ts: Date.now() })); } catch (e) { /* nic */ } }
  function clearPending() { try { sessionStorage.removeItem(PKEY); } catch (e) { /* nic */ } }
  function loginHref() {
    var next;
    if (!framed) next = location.pathname + location.search;
    else if (sameParent) { try { next = window.top.location.pathname + window.top.location.search + "#catGenerator"; } catch (e) { next = "/"; } }
    else next = "/embed/stul.html?p=" + PID;                // cizi rodic: prihlaseni v novem panelu, navrat na samostatny generator (konfigurace se obnovi)
    return "/login.html?next=" + encodeURIComponent(next);
  }

  function postJSON(url, body) {
    return fetch(url, { method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) })
      .then(function (r) { return r.json().catch(function () { return {}; }).then(function (d) { return { st: r.status, d: d || {} }; }); });
  }
  var pend0 = readPending();

  fetch("/miniweb/i18n/cs.json").then(function (r) { return r.json(); }).catch(function () { return {}; }).then(function (D) {
    function pick(prefix) { var o = {}; Object.keys(D).forEach(function (k) { if (k.indexOf(prefix) === 0) o[k.slice(prefix.length)] = D[k]; }); return o; }
    var T = function (k, f) { return D[k] != null ? D[k] : f; };
    var narrow = !!(window.matchMedia && window.matchMedia("(max-width: 719px)").matches);
    var L = window.PdcLayout.create({ E: el, narrow: narrow }), grid = L.grid, win = L.win;
    app.textContent = ""; app.appendChild(grid);

    var wStage = win("stage", T("win.view", "3D pohled")), wPrice = win("price", "Cena konfigurace");
    var wDim = win("dim", "", { fold: true, mobileOpen: true, hidden: true }), wFrame = win("frame", "", { fold: true, hidden: true }), wExtras = win("extras", "", { fold: true, hidden: true });
    var wAdv = win("adv", T("win.advanced", "Výřezy a ložiska"), { fold: true, closed: true, hidden: true });
    var wSum = win("sum", T("win.summary", "Shrnutí"), { fold: true, hidden: true });
    // okno Hlavni profil a ukazka Pripni cokoli: stejne prvky jako v mini-shopu a na strankach Generator stolu (Robert 2026-10-05, "prvky napric generatory na vsech mistech"; sdileny kod js/pdc-layout.js)
    var wProfile = win("profile", T("win.profile", "Hlavní profil"), { hidden: true }), wAttach = win("attach", T("win.attach", "Připni cokoli"), { fold: true, hidden: true });
    var gate = window.PdcLayout.modelGate();
    var media = el("div", { class: "mw-pd-media" }), panel = el("div");
    wStage.body.appendChild(media);

    var big = el("div", { class: "big", text: "…" }), vat = el("div", { class: "small" }), kod = el("div", { class: "small" });
    wPrice.body.appendChild(el("div", { class: "emb-price" }, [big, vat, kod]));
    var money = function (n) { try { return new Intl.NumberFormat("cs-CZ", { style: "currency", currency: "CZK", maximumFractionDigits: 0 }).format(Number(n)); } catch (e) { return n + " Kč"; } };
    var moneyP = function (n) { n = Number(n); try { return new Intl.NumberFormat("cs-CZ", { style: "currency", currency: "CZK", minimumFractionDigits: n % 1 ? 2 : 0, maximumFractionDigits: 2 }).format(n); } catch (e) { return n + " Kč"; } };

    // ---- montaz: vzdy volitelna; castka od serveru (quote s montaz true a false: rozdil DPH = montaz s DPH), v prohlizeci se nepocita
    var montazOn = !!(pend0 && pend0.montaz), mInfo = null, mReady = false, mSeq = 0, mTimer = null, mKey = "", guestApi = null;     // guestApi: null = nezname, true/false = server ma / nema /api/shop/stul/quote
    var mCb = el("input", { type: "checkbox", id: "embMontaz" }), mAmt = el("span", { class: "emb-montaz-amt" });
    var mRowMontaz = el("span"), mRowTotal = el("span");
    var mLabel = T("pdc.montazLabel", "Montáž"), mState = el("p", { class: "emb-montaz-state" });            // doprovodny text: s montazi smontovano, bez demontovano (zneni v i18n/cs.json pdc.montazOn/Off - bot7)
    var mRows = el("div", { class: "emb-montaz-rows", hidden: true }, [el("div", { class: "emb-co-row" }, [el("span", { text: mLabel }), mRowMontaz]), el("div", { class: "emb-co-row is-total" }, [el("span", { text: "Celkem s montáží" }), mRowTotal])]);
    var mBox = el("div", { class: "emb-montaz", hidden: true }, [el("label", { class: "mw-opt", for: "embMontaz" }, [mCb, el("span", { class: "emb-montaz-t", text: mLabel }), mAmt]), mState, mRows]);
    var shipNote = el("p", { class: "emb-shipnote", text: window.StulObjednavka.TXT.shipNote });
    wPrice.body.appendChild(mBox); wPrice.body.appendChild(shipNote);
    // ---- ulozeni konfigurace (Robert 2026-10-05): po zadani ICO, e-mailu a telefonu (overi se pred ulozenim); zakaznik dostane odkaz pro navrat; tlacitko se ukaze jen kdyz backend funkci ma (probe)
    var ulozenaTok = window.StulUlozeni ? window.StulUlozeni.tokenFromUrl(location.search) : null;
    function ulozenaLink(token) {
      var u = null;
      if (framed && sameParent) { try { u = new URL(window.top.location.href); } catch (e) { u = null; } }                           // nase stranka kategorie / karty: odkaz vede na ni
      if (!u) { u = new URL(location.origin + "/embed/stul.html"); u.searchParams.set("p", PID); }
      u.searchParams.set("ulozena", token); u.hash = "";
      return u.toString();
    }
    var saveUi = window.StulUlozeni ? window.StulUlozeni.create({
      t: function (k, v) { var s = T(k, ""); return v && s ? s.replace(/\{(\w+)\}/g, function (m, n) { return v[n] != null ? v[n] : m; }) : s; },
      getPayload: function () { var pl = ctl && ctl.cartPayload(); return pl ? { product_id: Number(PID), configuration: { selection: pl.configuration.selection, rules_version: pl.configuration.rules_version } } : null; },
      privacyHref: fetch("/ochrana-osobnich-udaju", { method: "HEAD", credentials: "omit" }).then(function (r) { return r.ok ? "/ochrana-osobnich-udaju" : null; }).catch(function () { return null; }),
      privacyLabel: T("legal.privacy", ""), linkFor: ulozenaLink, onChange: sendHeightSoon, onRulesChanged: function () { if (ctl) ctl.refresh(); }
    }) : null;
    if (saveUi) wPrice.body.appendChild(saveUi.el);
    function renderMontaz() {
      mBox.hidden = !mInfo;
      if (!mInfo) { mRows.hidden = true; sendHeightSoon(); return; }
      mCb.checked = montazOn; mAmt.textContent = "+" + moneyP(mInfo.net) + " bez DPH";
      mState.textContent = montazOn ? T("pdc.montazOn", "Stůl dodáme smontovaný.") : T("pdc.montazOff", "Stůl dodáme demontovaný (rozložený).");
      mRows.hidden = !montazOn;
      mRowMontaz.textContent = moneyP(mInfo.net) + " bez DPH\n" + moneyP(mInfo.gross) + " s DPH";
      mRowTotal.textContent = moneyP(mInfo.totalNet) + " bez DPH\n" + moneyP(mInfo.totalGross) + " s DPH";
      sendHeightSoon();
    }
    mCb.addEventListener("change", function () { montazOn = mCb.checked; renderMontaz(); resetResult(); });
    function fetchMontaz() {                                           // po kazdem platnem vypoctu konfigurace (krátké zpoždění kvůli tažení posuvníků)
      clearTimeout(mTimer);
      mTimer = setTimeout(function () {
        if (guestApi === false) { mInfo = null; mReady = true; renderMontaz(); tryResume(); return; }     // server API pro montaz/hosta jeste nema (pred nasazenim): zadne dalsi dotazy
        var pl = ctl && ctl.cartPayload(); if (!pl) return;
        var key = JSON.stringify(pl.configuration.selection) + "|" + pl.configuration.rules_version;
        if (key === mKey && mReady) return;
        var my = ++mSeq; mKey = key; mReady = false;
        function item(m) { return { product_id: Number(PID), qty: 1, montaz: m, configuration: { selection: pl.configuration.selection, rules_version: pl.configuration.rules_version } }; }
        Promise.all([postJSON(QUOTE_URL, { items: [item(true)] }), postJSON(QUOTE_URL, { items: [item(false)] })]).then(function (r) {
          if (my !== mSeq) return;
          var a = r[0], b = r[1], ln = a.st === 200 && a.d.lines && a.d.lines[0];
          if (a.st === 404 || b.st === 404) guestApi = false; else if (a.st === 200 || a.st === 409) guestApi = true;
          if (a.st === 200 && b.st === 200 && ln && ln.montaz_czk != null && a.d.vat && b.d.vat) {      // dostupnost montaze = server vratil castku (409 montaz_unavailable pri sazbe 0); sazba se zakaznikovi neposila
            mInfo = { net: ln.montaz_czk, gross: Math.round((a.d.vat.total_with_vat - b.d.vat.total_with_vat) * 100) / 100, totalNet: a.d.subtotal_czk, totalGross: a.d.vat.total_with_vat };
          } else mInfo = null;                                            // montaz se u teto konfigurace nenabizi (neni nastavena sazba / neplatna konfigurace)
          mReady = true; renderMontaz(); tryResume();
        }).catch(function () { if (my === mSeq) { mInfo = null; mReady = true; renderMontaz(); tryResume(); } });
      }, 250);
    }
    function whenMontazReady() {                                        // pred zalozenim kosiku hosta pockame (max 3 s), az server rekne, zda se montaz nabizi
      return new Promise(function (res) { var t0 = Date.now(); (function w() { if (mReady || guestApi === false || Date.now() - t0 > 3000) res(); else setTimeout(w, 100); })(); });
    }
    function guestAvailable(pl) {                                       // objednavka hosta jen kdyz server API hosta ma (jinak puvodni vyzva k prihlaseni)
      if (guestApi !== null) return Promise.resolve(guestApi);
      return postJSON(QUOTE_URL, { items: [{ product_id: Number(PID), qty: 1, montaz: false, configuration: { selection: pl.configuration.selection, rules_version: pl.configuration.rules_version } }] })
        .then(function (x) { guestApi = x.st !== 404 && x.st !== 0; return guestApi; }).catch(function () { return false; });
    }

    // ---- objednavka: Objednat -> POST /api/cart/items {product_id, qty:1, configuration:{selection, rules_version}} (cena se neposila, server ji spocita znovu); pak odkaz do kosiku
    var orderBtn = el("button", { type: "button", class: "mw-btn emb-order-btn", text: "Objednat", disabled: true });
    var orderMsg = el("p", { class: "emb-order-msg", role: "status", "aria-live": "polite" });
    var goLink = el("a", { class: "mw-btn emb-order-go", href: CART_URL, target: LINK_TARGET, rel: "noopener", hidden: true, text: "Pokračovat k objednávce →" });
    var loginLink = el("a", { class: "mw-btn emb-order-login", href: loginHref(), target: LINK_TARGET, rel: "noopener", hidden: true, text: "Přihlásit se a pokračovat" });       // jen když server ještě nemá objednávku hosta
    var finishBtn = el("button", { type: "button", class: "mw-btn mw-btn-ghost emb-order-finish", hidden: true });
    wPrice.body.appendChild(el("div", { class: "emb-order" }, [orderBtn, orderMsg, goLink, loginLink, finishBtn]));
    wPrice.body.appendChild(el("p", { class: "emb-note", text: "Orientační cena podle zvolené konfigurace." }));

    var ctl = null, buyOk = false, buyReason = "", busy = false, added = false, needLogin = false, addedKey = null, msgText = "", msgKind = "", msgLink = null, guest = null;
    function sync() {
      orderBtn.disabled = busy || !buyOk || !ctl;
      if (saveUi) saveUi.update();
      orderBtn.textContent = busy ? "Ukládám…" : "Objednat";
      var text = msgText, kind = msgKind, link = msgLink;
      if (!text && !buyOk && buyReason) { text = buyReason; kind = ""; link = null; }
      orderMsg.textContent = text || "";
      orderMsg.className = "emb-order-msg" + (kind ? " " + kind : "");
      if (text && link) { orderMsg.appendChild(document.createTextNode(" ")); orderMsg.appendChild(el("a", { href: link.href, target: LINK_TARGET, rel: "noopener", text: link.text })); }
      goLink.hidden = !added; loginLink.hidden = !needLogin;
      var gn = guest ? guest.count() : 0; finishBtn.hidden = gn === 0; finishBtn.textContent = "Dokončit objednávku (" + gn + ")";
      sendHeightSoon();
    }
    function setMsg(text, kind, link) { msgText = text || ""; msgKind = kind || ""; msgLink = link || null; sync(); }
    function resetResult() { added = false; needLogin = false; addedKey = null; setMsg(""); }

    function fail(st, d) {
      var code = d && d.code ? d.code : "";
      if (code === "rules_changed") { if (ctl) ctl.refresh(); setMsg("Pravidla generátoru se mezitím změnila. Zkontrolujte prosím zvolené parametry a objednejte znovu.", "err"); }
      else if (code === "product_unavailable") setMsg("Tento stůl zatím nelze objednat online.", "err", { href: INQUIRY_URL, text: "Poptat stůl na míru" });
      else if (code === "invalid_selection" || code === "invalid_configuration" || code === "configuration_required") setMsg("Konfigurace není platná. Upravte ji prosím a zkuste to znovu.", "err");
      else if (code === "not_configurable") setMsg("Tento produkt nelze konfigurovat.", "err");
      else if (st === 429 || code === "rate_limited") setMsg("Příliš mnoho pokusů, zkuste to prosím za chvíli.", "err");
      else if (st === 403) setMsg("Košík je dočasně vypnutý.", "err");
      else setMsg("Nepodařilo se uložit do košíku. Zkuste to prosím znovu.", "err");
    }
    function order(resumed) {
      var pl = ctl && ctl.cartPayload();
      if (!pl) { setMsg("Konfigurace se ještě přepočítává nebo není platná.", "err"); return; }
      busy = true; added = false; setMsg("");
      var withMontaz = !!(montazOn && mInfo);
      var body = { product_id: Number(PID), qty: 1, lang: "cs", configuration: { selection: pl.configuration.selection, rules_version: pl.configuration.rules_version } };
      if (withMontaz) body.montaz_zvolena = true;
      fetch("/api/cart/items", { method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) })
        .then(function (r) { return r.json().catch(function () { return {}; }).then(function (d) { return { st: r.status, d: d || {} }; }); })
        .then(function (x) {
          busy = false;
          if (x.st === 200 || x.st === 201) {
            clearPending(); added = true; addedKey = JSON.stringify(pl.configuration.selection);
            setMsg(resumed ? "Po přihlášení jsme vaši konfiguraci uložili do košíku." : "Stůl je v košíku.", "ok");
            notifyParent({ type: "stul-embed-cart-added" });
          } else if (x.st === 401) {                                    // nepřihlášený: objednávka HOSTA bez registrace (košík v prohlížeči, údaje, odeslání); bez API hosta na serveru výzva k přihlášení
            busy = true; sync();
            guestAvailable(pl).then(function (okApi) { return okApi ? whenMontazReady().then(function () { return okApi; }) : okApi; }).then(function (okApi) {
              busy = false;
              if (okApi) {
                var ok = guest.add({ pid: Number(PID), qty: 1, montaz: withMontaz, can: !!mInfo, selection: pl.configuration.selection, rules_version: pl.configuration.rules_version, hash: pl.configuration.hash, kod: pl.kod || "" });
                if (ok) { setMsg(""); guest.open(); } else setMsg("Košík je plný nebo konfigurace není platná.", "err");
              } else {
                writePending(pl.configuration.selection, withMontaz); needLogin = true;
                setMsg("Pro objednání se prosím přihlaste – vaši konfiguraci si pamatujeme.", "");
              }
            });
          } else { if (resumed) clearPending(); fail(x.st, x.d); }       // automaticky pokus po prihlaseni se po chybe neopakuje pri kazdem nacteni stranky
        })
        .catch(function () { busy = false; setMsg("Spojení se nezdařilo. Zkuste to prosím znovu.", "err"); });
      sync();
    }
    orderBtn.addEventListener("click", function () { if (!busy) order(false); });
    finishBtn.addEventListener("click", function () { if (guest) guest.open(); });

    // navrat z prihlaseni: obnovit rozdelanou konfiguraci; je-li zakaznik uz prihlaseny, prida se do kosiku sama (jednou)
    var pend = pend0, auth = pend ? null : false, resumed = false;              // auth: null = zjistuje se, true/false
    function tryResume() {
      if (resumed || !pend || auth !== true || !ctl || !buyOk || busy) return;
      if (!ctl.cartPayload()) return;                                          // modul jeste dopocitava (napr. automaticke zapnuti voleb) - zkusime pri dalsim setBuyState
      if (pend.montaz && !mReady) { fetchMontaz(); return; }                   // volba montaze se do kosiku preda az po nacteni castky od serveru
      resumed = true; order(true);
    }
    if (pend) {
      fetch("/api/auth/me", { credentials: "same-origin" }).then(function (r) { return r.ok; }).catch(function () { return false; }).then(function (ok) {
        auth = ok; if (!ok) clearPending(); tryResume();                          // nepřihlášený po návratu: vybrané volby zůstanou, ale dál se nic nepamatuje
      });
    }

    var side = el("div", { class: "mw-col mw-col-side" }), col3 = el("div", { class: "mw-col mw-col-3" }), cfgBar = el("div", { class: "mw-cfgbar" }, [panel]);
    side.appendChild(wPrice.box); side.appendChild(wSum.box); col3.appendChild(wAdv.box);
    var extra = el("div", { class: "mw-col mw-col-extra" }, [wProfile.box, wAttach.box]);          // Hlavni profil + Pripni cokoli: pod volbami vpravo, ne vedle 3D (pravy sloupec 1. radku by prodlouzil 3D okno)
    var sumHost = L.summaryHost(wSum, { all: function (n) { return T("cart.cfg_all", "Celá konfigurace ({n})").replace("{n}", n); }, less: T("win.sum_less", "Zobrazit méně") });
    [wStage.box, side, cfgBar, wDim.box, wFrame.box, wExtras.box, col3, extra].forEach(function (n) { grid.appendChild(n); });
    var groupHost = L.groupHosts({ map: { g_size: wDim, g_frame: wFrame, g_extras: wExtras, g_cuts: wAdv, g_bearings: wAdv }, adv: wAdv });

    guest = window.StulObjednavka.create({
      el: el, host: app, generator: grid, target: LINK_TARGET, loginHref: loginHref, notifyParent: notifyParent, sendHeightSoon: sendHeightSoon,
      onAccount: function () { var pl = ctl && ctl.cartPayload(); if (pl) writePending(pl.configuration.selection, montazOn); }                // "Mate ucet? Prihlasit se": rozdelanou konfiguraci si pamatujeme
    });
    guest.onChange(function () { sync(); });
    var pendingText = T("pdc.pending", "");
    var hashSel = window.PdConfigurator.unpackSelection ? window.PdConfigurator.unpackSelection(location.hash) : null;       // vyber z prepnuti systemu (#v=...)
    if (hashSel) { try { history.replaceState(null, "", location.pathname + location.search); } catch (e) { /* nic */ } }
    var sysSwitch = {                                                // prepinac systemu stolu 30 <-> 40 (schema.systems): stejny vyber na karte druheho systemu
      mount: function (box) { app.insertBefore(box, grid); },
      go: function (t, sel) {
        var packed = window.PdConfigurator.packSelection(sel);
        var self = function () { var u = new URL(location.href); u.searchParams.set("p", String(t.card_id)); u.hash = packed; location.href = u.toString(); };
        if (framed && sameParent) {                                  // nase stranka kategorie: prepne CELOU stranku na kategorii druheho systemu (nadpis, texty); kdyz nereaguje, prepne se jen generator
          try { window.parent.postMessage({ type: "stul-embed-switch-system", card_id: Number(t.card_id), system: t.system, v: packed }, location.origin); } catch (e) { self(); return; }
          setTimeout(self, 1500);
        } else self();
      }
    };
    var restoreP = ulozenaTok ? Promise.race([window.StulUlozeni.load(ulozenaTok), new Promise(function (res) { setTimeout(function () { res(null); }, 5000); })]) : Promise.resolve(null);
    restoreP.then(function (saved) {
    if (saved && String(saved.product_id) !== String(PID)) { sysSwitch.go({ system: saved.system, card_id: saved.product_id }, saved.selection); return; }          // ulozena konfigurace jineho systemu: prejit na jeho kartu / kategorii
    var lux = window.StulLuxy ? window.StulLuxy.create({ lang: "cs" }) : null;                    // pocitadlo luxu ve 3D nahledu (js/stul-luxy.js; Robert 2026-10-05)
    window.PdConfigurator.init({
      product: { id: Number(PID), configurator: { available: true, default_view: "configurator" } }, noTurntable: true, lang: "cs",
      labels: pick("pdc."), viewerLabels: pick("v3d."), ovladaniTexty: pick("v3do."), initialSelection: pend ? pend.selection : (saved ? saved.selection : (hashSel || undefined)), systemSwitch: sysSwitch,
      viewerOpts: window.matchMedia && window.matchMedia("(max-width: 800px)").matches ? { hudDock: "top" } : {},
      dom: { tabsBefore: null, visual: [], stageHost: media, panelHost: panel, groupHost: groupHost, summaryHost: sumHost, reveal: L.reveal, dependsOn: window.PdcLayout.DEPENDS },
      page: {
        setPrice: function (p, st) {
          if (p && p.net != null) { big.textContent = money(p.net) + " bez DPH"; vat.textContent = p.gross != null ? money(p.gross) + " s DPH" : ""; }
          else if (!st || st.pending !== true) { big.textContent = "…"; vat.textContent = ""; }
          kod.textContent = st && st.kod ? "Kód konfigurace: " + st.kod : "";
          sendHeightSoon();
        },
        setBuyState: function (ok, reason) { buyOk = !!ok; buyReason = ok || reason === pendingText ? "" : (reason || ""); sync(); if (ok) fetchMontaz(); tryResume(); },
        onSelection: function (sel) { if (added && JSON.stringify(sel) !== addedKey) resetResult(); },     // po zmene voleb uz potvrzeni "v kosiku" neplati
        toast: function () {}, onActivate: function () {}, track: function () {},
        viewerPlugins: lux ? lux.viewerPlugins : undefined, onResolved: lux ? lux.onResolved : undefined, onModel: function (url, hash) { gate.unlock(); if (lux && lux.onModel) lux.onModel(url, hash); }, onDrag: lux ? lux.onDrag : undefined
      },
      assets: { cssNow: ["/css/product-configurator.css?v=55f3678f8f"], css: ["/css/v3d.css?v=c76cbe7292"], viewer: "/js/v3d/viewer3d.js?v=e6b94b904a", ovladani: "/js/v3d-ovladani.js?v=1bc0d2b6ba" }
    }).then(function (c) {
      ctl = c;
      if (c && c.system && c.system() != null) document.title = "Generátor stolu – systém " + c.system();       // titulek podle systemu karty (?p=4954 = systém 40), ne napevno 30
      var prof = c && c.profile ? c.profile() : null;                                                          // profil ze schematu ("30x30"): okno Hlavni profil + ukazka Pripni cokoli (bez animace pro profil se neukazuji)
      if (prof) {
        window.PdcLayout.profileWindow(wProfile, { profile: prof, version: TILE_JS.split("?v=")[1], text: function (mm, g) { return T("win.profile_text", "Profil {mm}×{mm} mm, drážka {g} mm.").replace(/\{mm\}/g, mm).replace(/\{g\}/g, g); } });
        window.PdcLayout.attachWindow(wAttach, { profile: prof, lang: "cs", accent: (getComputedStyle(document.documentElement).getPropertyValue("--accent") || "").trim() || undefined,
          getEnv: function () { return c.envConfig ? c.envConfig() : null; }, gate: gate, tileUrl: TILE_JS, cssUrl: V3D_CSS, onReady: sendHeightSoon });
      }
      if (!c) { app.innerHTML = '<div class="emb-blocked">Generátor se nepodařilo načíst.</div>'; }
      sync(); if (c) fetchMontaz(); tryResume(); sendHeightSoon();
      if (ulozenaTok && saveUi) saveUi.notice(saved ? T("ulozeni.obnovena", "") : T("ulozeni.nenalezena", ""));
    });
    });

    if (window.ResizeObserver) new ResizeObserver(sendHeightSoon).observe(document.body);
    window.addEventListener("resize", sendHeightSoon); window.addEventListener("load", sendHeightSoon);
    sendHeightSoon();
  });
})();
