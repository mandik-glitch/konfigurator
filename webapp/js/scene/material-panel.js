// material-panel.js - PANEL VLASTNOSTÍ MATERIÁLŮ + univerzální panel tlačítek.
//
// Robert 2026-09-10: "tak kovovost co je ve scene, se nemuze aplikovat na
// vsechno, jen na profily" -> "resp ve scene musi mit každý materiál vlastní
// nastavovani vlastností (kovovost atd)" -> "měl by nato být dalsí panel"
// -> "udelej jeste responzivni panel, do ktereho se mohou vkladat libovolné
// tlačitka" -> "myšleno ve scene".
//
// PROC SAMOSTATNY SOUBOR: catalog-panels.js i hdri-panels-ui.js jsou zrovna
// rozpracovane jinymi boty. Tenhle panel na nich stoji (cte a MENI jejich
// tabulky partMaterialColor/Metalness/Roughness), ale zadny jejich radek
// neprepisuje - nacita se az za nimi, takze jejich globalni `const` objekty
// uz existuji a staci menit jejich OBSAH.
//
// KDE SE HODNOTY UKLADAJI: localStorage, stejne jako dnesni posuvniky HDRI
// ovladace (konfHdriMetal/konfHdriRough/...). Kazdy si tedy ladi svoje a
// nikomu jinemu to nic neprepise. POZOR: renderovaci vetev
// (scripts/2026-09-09_turntable_job.py, PART_MATERIAL_*) ma vlastni kopii
// tychz cisel a o localStorage nevi - kdyz se material naladi tady a ma se
// projevit i v produktovem renderu, musi se stejna hodnota prepsat i tam.

(function () {
  "use strict";

  // Pořadí a lidské názvy materiálů. Klíče musí sedět na partMaterialColor
  // v catalog-panels.js - tenhle panel žádný nový materiál nezavádí, jen
  // zpřístupňuje ty existující.
  // HLINIK TU ZAMERNE NENI (Robert 2026-09-10: "jestli mas v materialech
  // hlinik, a zaroven na hlavnim panelu tak se to bije snad ne se to
  // duplikuje"). Hlinik uz ma sve ovladani na HDRI ovladaci - a od
  // 2026-09-10 se ty posuvniky drzi VYHRADNE profilu, takze jsou fakticky
  // ovladanim hliniku. Dva ovladace tehoz materialu pres dva RUZNE
  // mechanismy (globalni override hdriRefl* vs. paleta partMaterial*) by se
  // navzajem prepisovaly - kdo tahne posledni, ten vyhrava.
  // Tenhle panel proto resi jen materialy, ktere sve ovladani NEMAJI.
  const MATERIALY = [
    // Robert 2026-09-10: "uhelnik je odlitek, ne plast !" - uhelnikove
    // spojky patri sem, ne pod plast. Az do teto opravy mely v DB
    // color_hex plastu, takze na zinek NEREAGOVALY (Robert to hlasil
    // dvakrat: "Uhelniky nemeni barvu ten zinek na to neni navazany",
    // "opakuji, zinek na uhelniky nereaguje"). Nesla za tim zadna chyba
    // panelu - dil se k materialu hlasi podle sve barvy z katalogu, a ta
    // byla proste zarazena spatne.
    { klic: "zinc", nazev: "Zinek (odlitky)", pozn: "úhelníkové spojky" },
    { klic: "plast_svetly", nazev: "Plast světlý", pozn: "euroboxy" },
    { klic: "mdf", nazev: "MDF deska", pozn: "výplně horního bloku" },
    { klic: "black", nazev: "Černá", pozn: "záslepky" },
    { klic: "guma", nazev: "Guma", pozn: "" },
  ];

  const LS = k => "konfMat_" + k;

  // PUVODNI barvy palety, zachycene JESTE PRED nactenim ulozenych hodnot.
  // Robert 2026-09-10 ("Uhelniky nemeni barvu"): dil se k materialu
  // prirazuje podle sve barvy (part.color_hex z katalogu). Kdyz panel
  // zmenil barvu materialu, uz polozene dily mely porad tu STAROU a
  // prestaly se k materialu hlasit - zadny se neprekreslil. Prirazeni se
  // proto MUSI delat proti puvodnimu (katalogovemu) odstinu, ne proti
  // aktualne nastavenemu. Barva v palete je vystup, ne identita.
  const PUVODNI_HEX = {};

  function tabulkyExistuji() {
    return typeof partMaterialColor !== "undefined"
      && typeof partMaterialMetalness !== "undefined"
      && typeof partMaterialRoughness !== "undefined";
  }

  // HEX_TO_* se odvozuji z palety - po zmene barvy se MUSI prepocitat,
  // jinak by material zustal navazany na stary odstin. Jsou to `const`
  // objekty, takze se meni jejich obsah, ne vazba.
  function prepocitejMapy() {
    if (typeof HEX_TO_METALNESS !== "undefined") {
      Object.keys(HEX_TO_METALNESS).forEach(k => { delete HEX_TO_METALNESS[k]; });
      for (const k in partMaterialColor) HEX_TO_METALNESS[partMaterialColor[k].toLowerCase()] = partMaterialMetalness[k];
    }
    if (typeof HEX_TO_ROUGHNESS !== "undefined") {
      Object.keys(HEX_TO_ROUGHNESS).forEach(k => { delete HEX_TO_ROUGHNESS[k]; });
      for (const k in partMaterialColor) HEX_TO_ROUGHNESS[partMaterialColor[k].toLowerCase()] = partMaterialRoughness[k];
    }
  }

  // Ke kteremu materialu dil patri. Produktove dily (shop_products) nemaji
  // realny `layer` - poznaji se VYHRADNE podle color_hex, presne jako v
  // materialForLayer(). Rucne obarveny dil nepatri nikam (jeho barva je
  // uzivatelovo rozhodnuti a panel ji nesmi prebit).
  function klicMaterialu(entry) {
    if (!entry || !entry.part) return null;
    if (entry.customColor) return null;
    const hex = String(entry.part.color_hex || "").toLowerCase();
    if (hex) {
      for (const k in PUVODNI_HEX) {
        if (PUVODNI_HEX[k] === hex) return k;   // proti PUVODNI barve, viz vyse
      }
      return null;                       // barva mimo paletu - panel na ni nesaha
    }
    return partMaterialColor[entry.part.layer] ? entry.part.layer : null;
  }

  // Prekresli uz polozene dily daneho materialu. Nesaha na rucne obarvene
  // dily ani na castecne obarvene casti (meshColors) - stejna pravidla jako
  // hdriApplySurfaceLive.
  function aplikujNaScenu(klic) {
    if (typeof placed === "undefined") return;
    const barva = partMaterialColor[klic];
    placed.forEach(en => {
      if (klicMaterialu(en) !== klic) return;
      en.object3d.traverse(n => {
        if (!n.isMesh || !n.material || !n.material.isMeshStandardMaterial) return;
        const meshColors = en.object3d.userData && en.object3d.userData.meshColors;
        if (meshColors && meshColors[n.name]) return;
        n.material.color.set(barva);
        n.material.metalness = partMaterialMetalness[klic];
        n.material.roughness = partMaterialRoughness[klic];
        n.material.needsUpdate = true;
      });
    });
  }

  function zachytPuvodniHex() {
    for (const k in partMaterialColor) PUVODNI_HEX[k] = partMaterialColor[k].toLowerCase();
  }

  function nactiUlozene() {
    MATERIALY.forEach(m => {
      try {
        const raw = localStorage.getItem(LS(m.klic));
        if (!raw) return;
        const v = JSON.parse(raw);
        if (typeof v.color === "string") partMaterialColor[m.klic] = v.color;
        if (isFinite(v.metal)) partMaterialMetalness[m.klic] = v.metal;
        if (isFinite(v.rough)) partMaterialRoughness[m.klic] = v.rough;
      } catch (e) { /* poskozena/zakazana localStorage - vychozi hodnoty */ }
    });
    prepocitejMapy();
  }

  function uloz(klic) {
    try {
      localStorage.setItem(LS(klic), JSON.stringify({
        color: partMaterialColor[klic],
        metal: partMaterialMetalness[klic],
        rough: partMaterialRoughness[klic],
      }));
    } catch (e) { /* soukromy rezim - hodnota plati aspon do zavreni */ }
  }

  function radekMaterialu(m) {
    const row = document.createElement("div");
    row.className = "mat-row";
    row.innerHTML = `
      <div class="mat-head">
        <input type="color" class="mat-color" value="${partMaterialColor[m.klic]}"
               title="Barva materiálu">
        <span class="mat-name">${m.nazev}</span>
        ${m.pozn ? `<span class="mat-note">${m.pozn}</span>` : ""}
      </div>
      <label class="mat-slider">kov
        <input type="range" class="mat-metal" min="0" max="1" step="0.01"
               value="${partMaterialMetalness[m.klic]}">
        <span class="mat-val">${partMaterialMetalness[m.klic].toFixed(2)}</span>
      </label>
      <label class="mat-slider">drsnost
        <input type="range" class="mat-rough" min="0" max="1" step="0.01"
               value="${partMaterialRoughness[m.klic]}">
        <span class="mat-val">${partMaterialRoughness[m.klic].toFixed(2)}</span>
      </label>`;
    const barva = row.querySelector(".mat-color");
    const kov = row.querySelector(".mat-metal");
    const drs = row.querySelector(".mat-rough");
    const [kovVal, drsVal] = row.querySelectorAll(".mat-val");
    barva.addEventListener("input", () => {
      partMaterialColor[m.klic] = barva.value;
      prepocitejMapy(); aplikujNaScenu(m.klic); uloz(m.klic);
    });
    kov.addEventListener("input", () => {
      partMaterialMetalness[m.klic] = parseFloat(kov.value);
      kovVal.textContent = partMaterialMetalness[m.klic].toFixed(2);
      prepocitejMapy(); aplikujNaScenu(m.klic); uloz(m.klic);
    });
    drs.addEventListener("input", () => {
      partMaterialRoughness[m.klic] = parseFloat(drs.value);
      drsVal.textContent = partMaterialRoughness[m.klic].toFixed(2);
      prepocitejMapy(); aplikujNaScenu(m.klic); uloz(m.klic);
    });
    return row;
  }

  // ------------------------------------------------------------------
  // VYCHOZI HODNOTY PRO VSECHNY (Robert 2026-09-10: "kdyz zmenim barvu
  // napriklad na uhelniku tak se to nedostane do dalsi sestavy, chybi tam
  // tlacitko ulozit jako vychozi").
  //
  // localStorage vyse je OSOBNI ladeni - drzi se v jednom prohlizeci a
  // renderovaci vetev o nem nevi. Tohle tlacitko naladene hodnoty povysi
  // na vychozi pro vsechny: ulozi je do DB (app_settings), odkud je cte
  // scena i scripts/2026-09-09_turntable_job.py.
  //
  // Sestavy barvu NENESOU (data.parts ma jen part_id/position/quaternion/
  // scale), takze se zmena projevi ve vsech sestavach sama. Prepocitat je
  // potreba jen uz vyrenderovane obrazky - ty se poslou do fronty znovu.
  const API_VYCHOZI = "/api/scene/material-defaults";

  function sesbirejHodnoty() {
    const out = {};
    MATERIALY.forEach(m => {
      if (partMaterialColor[m.klic] == null) return;
      out[m.klic] = {
        color: partMaterialColor[m.klic],
        metal: partMaterialMetalness[m.klic],
        rough: partMaterialRoughness[m.klic],
        // PUVODNI odstin, pod kterym se k materialu dily dosud hlasily.
        // Server podle nej najde radky v katalogu, ktere ma prebarvit -
        // z nove barvy uz to poznat nejde. Bez toho by se paleta zmenila,
        // ale dily by u ni zustaly na starem odstinu a prestaly by se k
        // materialu hlasit (presne to Robert hlasil u uhelniku).
        prev: PUVODNI_HEX[m.klic] || null,
      };
    });
    return out;
  }

  function nactiVychoziZDb() {
    // Vychozi z DB se nacitaji PRED localStorage, aby si rozdelane osobni
    // ladeni zustalo navrchu - kdo si neco ladi, nechce, aby mu to skok na
    // jinou sestavu prepsal.
    return fetch(API_VYCHOZI, { credentials: "same-origin" })
      .then(r => (r.ok ? r.json() : null))
      .then(d => {
        const mat = d && d.ok && d.materials;
        if (!mat) return;
        Object.keys(mat).forEach(klic => {
          if (partMaterialColor[klic] == null) return;
          const v = mat[klic];
          if (typeof v.color === "string") partMaterialColor[klic] = v.color;
          if (isFinite(v.metal)) partMaterialMetalness[klic] = v.metal;
          if (isFinite(v.rough)) partMaterialRoughness[klic] = v.rough;
        });
      })
      .catch(() => { /* bez prihlaseni/offline - plati hodnoty z kodu */ });
  }

  // Po prebarveni katalogu na serveru musi TOTEZ probehnout i v bezici
  // scene. CATALOG se nacita z /api/katalog JEDNOU pri startu, takze by v
  // nem zustal stary `color_hex` - a protoze se dil k materialu hlasi
  // prave podle nej (klicMaterialu), prestal by se hlasit uplne. Robert
  // 2026-09-10: "barva se po ulozeni do novych sestav nebo dalsich
  // vyvolanych sestav do sceny nepromita, porad je tam nejaka nenapojena
  // vazba" - tohle byla ta vazba. Bez toho pomohl az tvrdy reload stranky.
  function propisNovouBarvu(zmeny) {
    if (!zmeny.length) return;
    const mapa = new Map(zmeny);           // stary hex -> novy hex
    const prepis = obj => {
      if (!obj) return;
      const stary = String(obj.color_hex || "").toLowerCase();
      if (mapa.has(stary)) obj.color_hex = mapa.get(stary);
    };
    if (typeof CATALOG !== "undefined" && Array.isArray(CATALOG)) CATALOG.forEach(prepis);
    // Polozene dily drzi vlastni odkaz na `part` - u dilu vlozenych drive
    // to nemusi byt tentyz objekt jako v CATALOG.
    if (typeof placed !== "undefined" && placed.forEach) placed.forEach(en => prepis(en.part));
  }

  function ulozJakoVychozi(btn) {
    const puvodni = btn.textContent;
    // Dvojice stara -> nova barva se MUSI zachytit PRED odeslanim; po nem
    // uz PUVODNI_HEX prepiseme a puvodni odstin by nebyl kde vzit.
    const zmeny = [];
    MATERIALY.forEach(m => {
      const stary = String(PUVODNI_HEX[m.klic] || "").toLowerCase();
      const novy = String(partMaterialColor[m.klic] || "").toLowerCase();
      if (stary && novy && stary !== novy) zmeny.push([stary, novy]);
    });
    btn.disabled = true;
    btn.textContent = "Ukládám…";
    fetch(API_VYCHOZI, {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ materials: sesbirejHodnoty() }),
    })
      .then(r => r.json().then(d => ({ ok: r.ok, d })))
      .then(({ ok, d }) => {
        if (!ok || !d.ok) throw new Error((d && d.error) || "nezdarilo se");
        // Osobni prepis uz nema smysl drzet - prave se stal vychozim.
        MATERIALY.forEach(m => {
          try { localStorage.removeItem(LS(m.klic)); } catch (e) { /* nevadi */ }
        });
        // Katalog uz ma nove odstiny, takze totez musi platit i tady -
        // jinak by se dily prestaly k materialu hlasit (viz propisNovouBarvu).
        propisNovouBarvu(zmeny);
        // Az POTOM prepocitat PUVODNI_HEX: od ted je "puvodni" ta nova
        // barva. Bez toho by panel pri dalsi zmene poslal jako `prev` uz
        // neexistujici odstin a nenasel by v katalogu co prebarvit.
        zachytPuvodniHex();
        // Prekreslit uz polozene dily - maji ted spravne color_hex, takze
        // se k materialu zase hlasi.
        MATERIALY.forEach(m => { if (partMaterialColor[m.klic] != null) aplikujNaScenu(m.klic); });
        const p = d.prebarveno || {};
        const kusu = (p.shop_products || 0) + (p.cfg_dily || 0);
        btn.textContent = kusu
          ? "✓ Uloženo, přebarveno " + kusu + " dílů"
          : "✓ Uloženo jako výchozí";
        setTimeout(() => { btn.textContent = puvodni; btn.disabled = false; }, 2600);
      })
      .catch(e => {
        console.error("ulozJakoVychozi", e);
        btn.textContent = "✗ Nepodařilo se uložit";
        setTimeout(() => { btn.textContent = puvodni; btn.disabled = false; }, 2600);
      });
  }

  function postavPanelMaterialu() {
    const telo = document.getElementById("matPanelBody");
    if (!telo || !tabulkyExistuji()) return;
    telo.innerHTML = "";
    MATERIALY.filter(m => partMaterialColor[m.klic] != null)
      .forEach(m => telo.appendChild(radekMaterialu(m)));

    const patka = document.createElement("div");
    patka.className = "mat-footer";
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "mat-save-default";
    btn.textContent = "Uložit jako výchozí";
    btn.title = "Zapíše aktuální nastavení jako výchozí pro všechny sestavy "
              + "i pro produktové rendery. Už vyrenderované obrázky je potřeba "
              + "vyrenderovat znovu.";
    btn.addEventListener("click", () => ulozJakoVychozi(btn));
    patka.appendChild(btn);
    telo.appendChild(patka);
  }

  // ------------------------------------------------------------------
  // UNIVERZALNI PANEL TLACITEK (Robert: "responzivni panel, do ktereho se
  // mohou vkladat libovolné tlačitka"). Zadne konkretni tlacitko tu
  // natvrdo neni - panel je prazdny kontejner a naplnuje se za behu:
  //
  //    scenePridejTlacitko({ id, text, title, onClick });
  //    scenePridejTlacitko({ id, text, onClick, aktivni: true });   // prepinac
  //    sceneOdeberTlacitko(id);
  //
  // Panel se sam skryje, dokud v nem neni ani jedno tlacitko - at
  // nezavazi prazdny ve vyhledu.
  const tlacitka = new Map();

  function prekresliToolbox() {
    const panel = document.getElementById("toolboxPanel");
    const telo = document.getElementById("toolboxPanelBody");
    if (!panel || !telo) return;
    telo.innerHTML = "";
    tlacitka.forEach((def, id) => {
      const b = document.createElement("button");
      b.type = "button";
      b.dataset.toolboxId = id;
      b.textContent = def.text;
      if (def.title) b.title = def.title;
      if (def.aktivni) b.classList.add("is-active");
      b.addEventListener("click", () => {
        try { def.onClick && def.onClick(b, def); } catch (e) { console.error("toolbox " + id, e); }
      });
      telo.appendChild(b);
    });
    // Robert 2026-09-13 ("prazdny panel, kam muzu vkladat tlacitka co se
    // valeji po plose"): #toolboxPanelUser je DRUHA, rucne pretahovana rada
    // (viz dockToolButtonInToolbox v hdri-panels-ui.js) - tahle funkce ji
    // nikdy neplni ani nemaze, ale nesmi ji schovat, kdyz je prekresliToolbox
    // zavolana s prazdnou `tlacitka` mapou a v userWrap pritom neco je.
    const userWrap = document.getElementById("toolboxPanelUser");
    panel.style.display = (tlacitka.size || (userWrap && userWrap.children.length)) ? "" : "none";
  }

  window.scenePridejTlacitko = function (def) {
    if (!def || !def.id) { console.warn("scenePridejTlacitko: chybi id"); return; }
    tlacitka.set(def.id, def);
    prekresliToolbox();
  };
  window.sceneOdeberTlacitko = function (id) {
    tlacitka.delete(id);
    prekresliToolbox();
  };
  window.sceneToolboxSeznam = function () { return Array.from(tlacitka.keys()); };

  // ------------------------------------------------------------------
  function start() {
    if (!tabulkyExistuji()) return;      // scena se nenacetla cela
    zachytPuvodniHex();                  // MUSI byt pred nactiUlozene()
    // Vychozi z DB nejdriv, osobni localStorage az nad ne - viz komentar
    // u nactiVychoziZDb(). Panel se postavi hned s hodnotami z kodu a po
    // dojiti odpovedi se prekresli, at scena necaka na sit.
    nactiVychoziZDb().then(() => {
      nactiUlozene();
      postavPanelMaterialu();
      MATERIALY.forEach(m => { if (partMaterialColor[m.klic] != null) aplikujNaScenu(m.klic); });
    });
    nactiUlozene();
    postavPanelMaterialu();
    prekresliToolbox();
    // hlinik se zamerne neaplikuje - patri HDRI ovladaci (viz MATERIALY vyse)
    MATERIALY.forEach(m => { if (partMaterialColor[m.klic] != null) aplikujNaScenu(m.klic); });
    const zavrit = document.getElementById("matPanelClose");
    const panel = document.getElementById("matPanel");
    // Robert 2026-09-13 ("at se mi po F5 otevrou stejne okna") - ostatni
    // plovouci panely (Tvary/AI/Kamera/...) uz svuj stav pres reload
    // pamatuji samy (setupXPanelToggle v hdri-panels-ui.js, "<jmeno>Collapsed"
    // v localStorage) - tenhle jediny to nedelal, protoze nema vlastni "tab",
    // otevira se jen pres tlacitko v univerzalnim panelu (viz nize).
    const MAT_PANEL_COLLAPSED_KEY = "matPanelCollapsed";
    function setMatPanelCollapsed(collapsed) {
      if (!panel) return;
      panel.classList.toggle("collapsed", collapsed);
      const tlacitkoOtevrit = document.getElementById("btnToggleMaterialy");
      if (tlacitkoOtevrit) tlacitkoOtevrit.classList.toggle("is-active", !collapsed);
      try { localStorage.setItem(MAT_PANEL_COLLAPSED_KEY, collapsed ? "1" : "0"); } catch (e) { /* ignoruj */ }
    }
    if (zavrit && panel) zavrit.addEventListener("click", () => setMatPanelCollapsed(true));
    // bot8 2026-09-18 (Robert: "dej hned plovouci ten material a zaraditelny
    // do menu nastroju, tady dole zavazi") - drive tlacitko v dolni liste
    // stredu obrazovky (window.scenePridejTlacitko, #toolboxPanelBody), ted
    // primo v panelu Nastroje (#btnToggleMaterialy, viz scene.html
    // #toolsMenuList) - min zavazeni uprostred, konzistentni s ostatnimi
    // tlacitky Nastroju.
    if (panel) {
      const btnOtevrit = document.getElementById("btnToggleMaterialy");
      if (btnOtevrit) btnOtevrit.addEventListener("click", () => setMatPanelCollapsed(!panel.classList.contains("collapsed")));
      let startCollapsed = true;
      try {
        const saved = localStorage.getItem(MAT_PANEL_COLLAPSED_KEY);
        if (saved !== null) startCollapsed = saved === "1";
      } catch (e) { /* ignoruj */ }
      setMatPanelCollapsed(startCollapsed);
    }
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
  else start();
})();
