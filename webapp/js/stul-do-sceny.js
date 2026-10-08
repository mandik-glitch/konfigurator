// stul-do-sceny.js - tlacitko "Vlozit do Sceny" na strance Generator stolu (bot8, 2026-10-04; protokol v2 bot10, 2026-10-08).
// Robert 2026-10-03: ovladani stolu se neduplikuje (jeden modul pro vse) -> Scena uz nema vlastni panel voleb, jen PRIJIMA konfiguraci z teto stranky
// (webapp/js/scene/stul-konfigurator.js). `query` = parametry generatoru (stejne jako ve vyrobnich odkazech resp.staff), bere se z resp.staff.vyrobni_list_url (stav drzi stul-host.js).
//
// v3 (bot10, 2026-10-08, Robert: "nemusim mit otevrenou scenu, proste se otevre scena s tim modelem"): tlacitko "Vlozit do Sceny" TED VZDY OTEVRE NOVOU Scenu se stolem
// (window.open("/scene.html?stul=<query>") PRIMO v kliknuti - blokator oken by pozdejsi otevreni po cekani zahodil; Firefox novou kartu postavi do popredi, kdezto existujici kartu
// programove do popredi nedostane). Zadna otevrena Scena neni potreba a na jinych kartach Sceny nezalezi. Zablokuje-li prohlizec nove okno, ukaze se odkaz. Vlozeni do JIZ OTEVRENE
// Sceny (Scena s dalsim obsahem, ktery se nema ztratit; protokol v2 nize) zustava jako maly odkaz "nebo vlozit do uz otevrene Sceny" pod hlasenim.
//
// PROTOKOL v2 (vlozeni do uz otevrene Sceny; bot10, 2026-10-08; Robert: "klikl jsem na vlozit do sceny, nic se nevlozilo, a napsala se divna veta"). Puvodne se stul posilal DO VSECH otevrenych karet Sceny
// (BroadcastChannel "stul-konfigurace" {type:"vloz", query}) a prvni odpoved do 1,5 s se vyhlasila za uspech ("Stul je vlozeny do otevrene Sceny") - bez informace, KAM se vlozil.
// Robert mel karet Sceny nekolik (dalsi mu otevirala navigace "Scena" v zahlavi, kazda PRAZDNA), stul se vlozil do jine, skryte, a on ho nenasel; studena Scena (nacita modely)
// navic stihla odpovedet az po 1,5 s, tak se hlasilo "Scena neni otevrena" a vznikaly dalsi karty. Ted:
//   1) generator posle na verejny kanal {type:"ping", req}; kazda otevrena Scena odpovi {type:"pong", req, id, viditelna, aktivni} (jen se ohlasi, nic nevklada);
//   2) generator vybere JEDNU Scenu (viditelnou, jinak tu, kterou uzivatel pouzil naposledy) a posle jí na jeji SOUKROMY kanal "stul-konfigurace-<id>" {type:"vloz", query, req};
//      ostatni karty Sceny se nemeni;
//   3) Scena odpovi na soukromem kanalu {type:"ack", req, ok, viditelna, vymena, zprava} az po vlozeni (smi trvat desitky sekund) a stranka rekne, kde stul je
//      (viditelna Scena / jina karta prohlizece - ta ma pred nazvem "●").
// Zadna odpoved na ping (Sceny ze starsi verze stranky, ktere ping neznaji; ping ceka max 2,5 s - vytizena Scena odpovi se zpozdenim) -> puvodni protokol: {type:"vloz", query} na verejnem
// kanalu, ack do 1,5 s, jinak odkaz "Otevrit Scenu s timto stolem" (/scene.html?stul=<query>; odkaz, ne window.open po cekani - blokator oken by ho zahodil). Zalozni zprava nese i req
// a v:2 (Scena v2, ktera na ping nestihla odpovedet, protoze byla vytizena - prave se nacita - na ni odpovi ackem s req a viditelnosti). Kanal zustane dalsich 60 s otevreny: odpovi-li
// stara / vytizena Scena az pozdeji, hlaseni "Zadna Scena neni otevrena" se opravi. Novy klik zrusi predchozi nedokonceny pozadavek (jeho pozdni odpovedi uz hlaseni neprepisou).
(function () {
  "use strict";
  var CHANNEL = "stul-konfigurace", PONG_MS = 2500, PONG_DALSI_MS = 250, ACK_MS = 1500, POZDNI_MS = 60000, VLOZ_MS = 90000;

  function $(id) { return document.getElementById(id); }

  function dotaz() {
    var H = window.StulHost, st = H && H.state && H.state.staff;
    var u = st && st.vyrobni_list_url;
    var i = u ? u.indexOf("?") : -1;
    return i >= 0 ? u.slice(i + 1) : null;
  }

  function stav(text, chyba, odkaz) {
    var el = $("sceneStatus");
    if (!el) return;
    el.textContent = text || "";
    el.style.color = chyba ? "var(--err)" : "var(--muted)";
    if (odkaz) {
      var a = document.createElement("a");
      a.href = odkaz.href; a.target = "_blank"; a.rel = "noopener"; a.textContent = odkaz.text; a.style.marginLeft = "6px"; a.style.color = "var(--accent)";
      el.appendChild(a);
    }
  }

  function nahodneId() { return Math.random().toString(36).slice(2, 10) + Date.now().toString(36); }

  // viditelna Scena, jinak ta, kterou uzivatel pouzil naposledy
  function vyberScenu(pongy) {
    return pongy.slice().sort(function (a, b) {
      if (!!a.viditelna !== !!b.viditelna) return a.viditelna ? -1 : 1;
      return (b.aktivni || 0) - (a.aktivni || 0);
    })[0];
  }

  function zpravaUspechu(m, pocet) {
    var co = m.vymena ? "✔ Stůl ve Scéně je vyměněný za tuto konfiguraci (ostatní obsah Scény zůstal)." : "✔ Stůl je vložený do Scény.";
    var kde = m.viditelna ? "" : " Je v JINÉ KARTĚ prohlížeče – přepni se na ni (karta má před názvem ●).";
    var vic = pocet > 1 ? " Otevřených Scén je " + pocet + ", vložilo se do " + (m.viditelna ? "viditelné" : "naposledy použité") + "." : "";
    return co + kde + vic;
  }

  // PRIMARNI akce tlacitka (v3): nova karta Sceny se stolem
  function otevritScenu() {
    var q = dotaz();
    if (!q) { stav("Konfigurace se ještě nepočítá, zkus za chvíli.", true); return "nic"; }
    var odkaz = { href: "/scene.html?stul=" + encodeURIComponent(q), text: "Otevřít Scénu s tímto stolem" };
    var w = null;
    try { w = window.open(odkaz.href, "_blank"); } catch (e) { w = null; }              // PRIMO v kliknuti (jinak by blokator oken okno zahodil)
    if (!w) { stav("Prohlížeč zablokoval nové okno – otevři Scénu odkazem:", false, odkaz); return "odkaz"; }
    stav("✔ Scéna se stolem se otevřela v nové kartě prohlížeče.", false);
    return "otevreno";
  }

  var zrusPredchozi = null;

  // VEDLEJSI akce (maly odkaz): vlozeni do uz otevrene Sceny, protokol v2 (puvodni nazev poslat() zustava)
  function poslat() {
    var q = dotaz();
    if (!q) { stav("Konfigurace se ještě nepočítá, zkus za chvíli.", true); return Promise.resolve("nic"); }
    var odkaz = { href: "/scene.html?stul=" + encodeURIComponent(q), text: "Otevřít Scénu s tímto stolem" };
    var odkazNovy = { href: odkaz.href, text: "Otevřít novou Scénu s tímto stolem" };
    if (typeof BroadcastChannel === "undefined") { stav("Tento prohlížeč neumí poslat stůl do otevřené Scény.", false, odkaz); return Promise.resolve("odkaz"); }
    return new Promise(function (resolve) {
      var req = nahodneId(), bc = new BroadcastChannel(CHANNEL), soukromy = null, pongy = [], hotovo = false, pozdni = false, rozhodnuto = false, casovace = [], dalsiCasovac = null;
      function zavriKanaly() {
        casovace.forEach(function (t) { clearTimeout(t); });
        try { bc.close(); } catch (e) { /* ignoruj */ }
        try { if (soukromy) soukromy.close(); } catch (e) { /* ignoruj */ }
      }
      if (zrusPredchozi) zrusPredchozi();                                // novy klik prebije predchozi nedokonceny pozadavek (a jeho pozdni odpovedi)
      zrusPredchozi = function () { if (!hotovo) { hotovo = true; resolve("prebito"); } pozdni = false; zavriKanaly(); };
      function konec(kam, text, chyba, o, pozdniOkno) {
        if (hotovo) return;
        hotovo = true;
        casovace.forEach(function (t) { clearTimeout(t); });
        stav(text, chyba, o);
        if (pozdniOkno) { pozdni = true; casovace.push(setTimeout(zavriKanaly, POZDNI_MS)); }    // kanal zustane otevreny: Scena, ktera odpovi az pozdeji, hlaseni opravi
        else zavriKanaly();
        resolve(kam);
      }
      function ackV2(m, pocet) {                                         // odpoved Sceny v2 (soukromy kanal, nebo verejny pri zalozni ceste): vysledek vlozeni s viditelnosti
        var text = m.ok ? zpravaUspechu(m, pocet) : "Scéna stůl nepřijala: " + (m.zprava || "chyba ve Scéně (hlášení je v jejím panelu Generátor stolu)");
        var o = m.ok && m.viditelna ? null : odkazNovy;
        if (!hotovo) konec(m.ok ? "scena" : "chyba", text, !m.ok, o);
        else if (pozdni) { pozdni = false; stav(text, !m.ok, o); zavriKanaly(); }            // pozdni odpoved opravi hlaseni "Zadna Scena neni otevrena"
      }
      function rozhodni() {
        if (hotovo || rozhodnuto) return;
        rozhodnuto = true;
        if (!pongy.length) {                                            // nikdo na ping neodpovedel: puvodni protokol (Sceny ze starsi verze stranky); ani ty = zadna Scena neni otevrena
          stav("Posílám do Scény…", false);
          bc.postMessage({ type: "vloz", query: q, req: req, v: 2 });
          casovace.push(setTimeout(function () { konec("odkaz", "Žádná Scéna není otevřená – otevři ji s tímto stolem:", false, odkaz, true); }, ACK_MS));
          return;
        }
        var cil = vyberScenu(pongy), pocet = pongy.length;
        soukromy = new BroadcastChannel(CHANNEL + "-" + cil.id);
        soukromy.onmessage = function (ev) {
          var m = ev && ev.data;
          if (!m || hotovo || m.type !== "ack" || m.req !== req) return;
          ackV2(m, pocet);
        };
        stav(cil.viditelna ? "Vkládám do Scény…" : "Vkládám do Scény v jiné kartě prohlížeče…", false);
        soukromy.postMessage({ type: "vloz", query: q, req: req });
        casovace.push(setTimeout(function () { konec("chyba", "Scéna neodpověděla včas – stůl se možná ještě vkládá, podívej se do Scény.", true, odkazNovy); }, VLOZ_MS));
      }
      bc.onmessage = function (ev) {
        var m = ev && ev.data;
        if (!m || (hotovo && !pozdni)) return;
        if (m.type === "pong" && m.req === req && typeof m.id === "string" && !hotovo && !rozhodnuto) {      // pozdni pong po rozhodnuti se ignoruje (jinak by zalozni cesta pozdni ack zahodila)
          pongy.push(m);
          if (!dalsiCasovac && !rozhodnuto) { dalsiCasovac = setTimeout(rozhodni, PONG_DALSI_MS); casovace.push(dalsiCasovac); }   // dalsi karty Sceny odpovidaji temer soucasne
          return;
        }
        if (m.type === "ack" && m.req === req && rozhodnuto && !pongy.length) { ackV2(m, 1); return; }   // zalozni cesta: vytizena Scena v2 odpovida na verejnem kanalu s req
        if (m.type === "ack" && m.req == null && rozhodnuto && !pongy.length) {                // puvodni protokol: Scena ze starsi verze stranky (nebo vytizena, ktera na ping nestihla odpovedet)
          var ok = !!m.ok, text = ok ? "✔ Stůl je vložený do otevřené Scény (v jiné kartě prohlížeče – přepni se na ni)." : "Scéna stůl nepřijala (hlášení je v jejím panelu Generátor stolu).";
          if (!hotovo) konec(ok ? "scena" : "chyba", text, !ok, ok ? odkazNovy : null);
          else { pozdni = false; stav(text, !ok, ok ? odkazNovy : null); zavriKanaly(); }       // pozdni odpoved opravi hlaseni "Zadna Scena neni otevrena"
        }
      };
      stav("Hledám otevřenou Scénu…", false);
      bc.postMessage({ type: "ping", req: req });
      casovace.push(setTimeout(rozhodni, PONG_MS));
    });
  }

  function init() {
    var b = $("sceneBtn");
    if (!b) return;
    b.addEventListener("click", otevritScenu);
    var st = $("sceneStatus");
    if (!b.disabled && st && st.parentNode && !$("sceneVlozitDoOtevrene")) {            // stul SSE (tlacitko zakazane) se do Sceny nevklada vubec
      var d = document.createElement("div"), a = document.createElement("a");
      d.style.cssText = "margin-top:4px;font-size:.78rem";
      a.href = "#"; a.id = "sceneVlozitDoOtevrene"; a.textContent = "nebo vložit do už otevřené Scény (vymění jen díly stolu)"; a.style.color = "var(--muted)"; a.style.textDecoration = "underline";
      a.addEventListener("click", function (ev) { ev.preventDefault(); poslat(); });
      d.appendChild(a);
      st.parentNode.insertBefore(d, st.nextSibling);
    }
  }
  window.StulDoSceny = { otevrit: otevritScenu, poslat: poslat, vlozitDoOtevrene: poslat, dotaz: dotaz };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();
})();
