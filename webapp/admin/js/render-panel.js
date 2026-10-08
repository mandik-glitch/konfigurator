// render-panel.js - panel "Sdílený disk → Rendering → HDRi": přiřazení materiálů, HDRi a světel pro
// testovací rendery + nastavení, které čte automat renderů, fronta testů a volba stroje "renderovat na".
//
// Dřív žil uvnitř crm-nabidky.js (renderDriveFolderContents). Robert 2026-09-29/30: "nechápu proč pořád
// zavadíme o soubor crm-nabidky, když v crm vůbec neděláme" -> bot4 2026-09-30 přesunul 1:1 sem, BEZ změny
// chování (text panelu je kopie po řádcích, ne přepis).
//
// Vazba na crm-nabidky.js (obrazovka Sdíleného disku): renderDriveFolderContents() ve složce s HDRI soubory
// vloží do hlavičky renderPanelHtml(driveHdriFiles) a po vykreslení zavolá renderPanelInit(wrap). Sdílené
// proměnné (driveActiveHdriId, driveHdriFiles, driveJeHdri) zůstávají tam, kde se plní (loadDriveTree).
// Skript se načítá v admin.html hned ZA crm-nabidky.js (používá escapeHtmlAdmin ze sklad-produkty.js).
//
// Mechanismus (panel -> app_settings -> knihovna -> CLI) a kontrakty: PRODUKTOVE_RENDERY.md, sekce
// "Panel Rendering → HDRi". TESTY: scripts/2026-09-30_render_panel_testy/run_all.sh - po KAŽDÉ změně
// tohoto souboru (harness z něj vytahuje blok panelu podle kotev `const matPoleId = {` a
// `btnUlozit.addEventListener("click"`, neprejmenovavej je bez úpravy harness.js).

// 3D nahled v prirazovacim panelu (bot4 2026-09-28) - panel se pri kazdem
// prekresleni slozky vytvori znovu, posluchac zprav z iframe jen JEDNOU a
// vzdy pracuje s aktualnim stavem (matPrirazeni3dStav).
let matPrirazeni3dStav = null;
let matPrirazeni3dPosluchac = false;

// HTML panelu (vkládá ho renderDriveFolderContents do hlavičky složky s HDRI soubory).
// hdriFiles = seznam HDRI souborů disku [{id, filename}] pro roletu HDRi.
function renderPanelHtml(hdriFiles) {
  const hdriMoznosti = hdriFiles.map(f =>
    `<option value="${f.id}">${escapeHtmlAdmin(f.filename)}</option>`).join("");
  return `
    <div id="matPrirazeniPanel" style="margin:0 0 10px;padding:8px 9px;background:var(--panel-bg-alt, rgba(127,127,127,.12));
                border:1px solid var(--border-soft2);border-radius:6px;">
      <div style="font-size:10.5px;color:var(--text-muted);text-transform:uppercase;letter-spacing:.04em;margin-bottom:6px;">
        Přiřazení materiálu pro test render (Regálová vestavba – Renault Master L2H2)</div>
      <div style="display:flex;gap:14px;flex-wrap:wrap;align-items:flex-start;">
      <div id="matPrirazeni3dKol" style="flex:1 1 440px;min-width:300px;top:8px;">
        <div style="display:flex;gap:6px;align-items:center;flex-wrap:wrap;font-size:12px;margin-bottom:4px;">
          <span style="color:var(--text2);">3D sestava</span>
          <select id="matPrirazeni3dKarta" style="font-size:12px;flex:1 1 200px;min-width:0;"></select>
          <button type="button" id="matPrirazeni3dDalsi" style="font-size:12px;padding:2px 8px;" disabled
                  title="Stejný materiál v další sestavě - ne všude znamená totéž">další sestava s tímto materiálem ›</button>
        </div>
        <iframe id="matPrirazeni3d" title="3D náhled materiálů"
                style="display:block;width:100%;height:460px;border:1px solid var(--border-soft2);border-radius:6px;background:#eef1f4;"></iframe>
        <div id="matPrirazeni3dInfo" style="margin-top:4px;font-size:11px;color:var(--text-muted);">načítám…</div>
      </div>
      <div style="flex:1 1 560px;min-width:320px;">
      <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:6px 10px;font-size:12px;">
        <div></div>
        <div style="color:var(--text-muted);">materiál (název)</div>
        <div style="color:var(--text-muted);">knihovna (soubor na disku)</div>
        <div class="mp-lab" data-rodina3d="ALU" style="color:var(--text2);"><button type="button" class="mp-oko" data-rodina3d="ALU" title="Ukázat ve 3D">👁</button> hliník</div>
        <select id="matPrirazeniAluMaterial" style="font-size:12px;min-width:0;"></select>
        <input type="text" id="matPrirazeniAluKnihovna" placeholder="např. Alumi2.blend" style="font-size:12px;">
        <div class="mp-lab" data-rodina3d="__celo__" style="color:var(--text2);"><button type="button" class="mp-oko" data-rodina3d="__celo__" title="Ukázat ve 3D">👁</button> čelo šuplíku</div>
        <select id="matPrirazeniKltMaterial" style="font-size:12px;min-width:0;"></select>
        <input type="text" id="matPrirazeniKltKnihovna" placeholder="např. Blue_GloPLA.blend" style="font-size:12px;">
      </div>
      <div style="margin-top:10px;font-size:10.5px;color:var(--text-muted);text-transform:uppercase;letter-spacing:.04em;">
        Díly Vandr sestav podle role (skupina v exportu, stejná ve všech sestavách) — prázdné = materiál, který si díl nese z modelu · 👁 = ukázat ve 3D</div>
      <div id="matPrirazeniRodiny" style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:6px 10px;font-size:12px;margin-top:4px;">
        <div style="color:var(--text-muted);grid-column:1/-1;">načítám seznam materiálů…</div>
      </div>
      </div>
      </div>
      <div style="margin-top:8px;font-size:12px;display:flex;gap:14px;align-items:center;flex-wrap:wrap;">
        <span style="display:flex;gap:6px;align-items:center;">
          <span style="color:var(--text2);">šedý plast (přitmavit)</span>
          <input type="number" id="matPrirazeniCubSeda" min="0" max="1" step="0.05" placeholder="0-1" style="width:70px;font-size:12px;">
        </span>
        <span style="display:flex;gap:6px;align-items:center;">
          <span style="color:var(--text2);">AO síla</span>
          <input type="number" id="matPrirazeniAoSila" min="0" max="1" step="0.05" placeholder="0-1" style="width:70px;font-size:12px;">
        </span>
        <label style="display:flex;gap:6px;align-items:center;cursor:pointer;" title="Kryci listy v drazkach profilu se v renderu vubec nezobrazi (--kryci-listy-pruhledne)">
          <input type="checkbox" id="matPrirazeniKrycList">
          <span style="color:var(--text2);">schované krycí lišty</span>
        </label>
      </div>
      <div style="margin-top:8px;font-size:12px;display:flex;gap:14px;align-items:center;flex-wrap:wrap;">
        <span style="display:flex;gap:6px;align-items:center;"
              title="Světla z tohoto .blend souboru (např. X1_SCENA.blend ze Sdíleného disku) nahradí vestavěné osvětlení renderů. Sestava zůstane uprostřed a světla se otáčejí spolu s kamerou. Prostředí (HDRi) zůstává z nastavení níže. Nezatržené = vestavěné osvětlení (soubor a síla zůstanou uložené).">
          <label style="display:flex;gap:6px;align-items:center;cursor:pointer;">
            <input type="checkbox" id="matPrirazeniSvetlaAktivni">
            <span style="color:var(--text2);">světla ze souboru</span>
          </label>
          <input type="text" id="matPrirazeniSvetlaSoubor" placeholder="např. X1_SCENA.blend" style="font-size:12px;width:210px;">
        </span>
        <span style="display:flex;gap:6px;align-items:center;" title="Násobek výkonu všech světel ze souboru, 1 = přesně jak jsou v souboru">
          <span style="color:var(--text2);">síla světel</span>
          <input type="number" id="matPrirazeniSvetlaSila" min="0" max="50" step="0.1" placeholder="1.0" style="width:70px;font-size:12px;">
        </span>
        <span id="matPrirazeniSvetlaInfo" style="font-size:11px;color:var(--text-muted);"></span>
      </div>
      <div id="matPrirazeniSvetlaSeznam" style="display:none;margin-top:6px;font-size:12px;gap:4px 16px;flex-wrap:wrap;align-items:center;"></div>
      <div style="margin-top:8px;padding-top:8px;border-top:1px dashed var(--border-soft2);
                  font-size:12px;display:flex;gap:14px;align-items:center;flex-wrap:wrap;">
        <span style="display:flex;gap:6px;align-items:center;">
          <span style="color:var(--text2);">HDRi</span>
          <select id="matPrirazeniHdriId" style="font-size:12px;max-width:220px;">
            <option value="">— vyber soubor —</option>
            ${hdriMoznosti}
          </select>
        </span>
        <span style="display:flex;gap:6px;align-items:center;">
          <span style="color:var(--text2);">síla</span>
          <input type="number" id="matPrirazeniHdriSila" min="0" step="0.05" placeholder="např. 1.0" style="width:70px;font-size:12px;">
        </span>
        <span style="display:flex;gap:6px;align-items:center;">
          <span style="color:var(--text2);">natočení °</span>
          <input type="number" id="matPrirazeniHdriRotace" min="0" max="359" step="1" placeholder="0-359" style="width:70px;font-size:12px;">
        </span>
        <span style="display:flex;gap:6px;align-items:center;"
              title="Přesně z tohohle úhlu testovací snímek ukáže sestavu (stejná čísla jako snímky otočky, 270 = obvykle zepředu). Prázdné = zepředu">
          <span style="color:var(--text2);">azimut sestavy °</span>
          <input type="number" id="matPrirazeniAzimut" min="0" max="359" step="1" placeholder="zepředu" style="width:70px;font-size:12px;">
        </span>
        <button id="matPrirazeniUlozit" style="font-size:12px;padding:3px 12px;">💾 Uložit</button>
        <button id="matPrirazeniSpustit" style="font-size:12px;padding:3px 12px;">▶ Spustit testovací render</button>
        <span id="matPrirazeniKdeWrap" style="display:none;gap:6px;align-items:center;">
          <span style="color:var(--text2);">renderovat na</span>
          <select id="matPrirazeniKde" style="font-size:12px;max-width:210px;"></select>
          <span id="matPrirazeniKdeNapoveda" style="font-size:11px;color:var(--text-muted);"></span>
        </span>
        <span id="matPrirazeniStav" style="font-size:12px;color:var(--text-muted);"></span>
      </div>
      <div id="matPrirazeniFronta" style="margin-top:6px;font-size:12px;display:flex;flex-direction:column;gap:2px;"></div>
      <div style="margin-top:8px;padding-top:8px;border-top:1px dashed var(--border-soft2);font-size:12px;">
        <label style="display:flex;gap:6px;align-items:center;cursor:pointer;">
          <input type="checkbox" id="matPrirazeniAutomat">
          <span>Platné i pro automatickou linku renderů (Vandr) — dokud je zatržené, každý
            další automaticky zařazený render použije tohle nastavení místo výchozího</span>
        </label>
        <span id="matPrirazeniUlozStav" style="font-size:11px;color:var(--text-muted);"></span>
        <div id="matPrirazeniAutomatStav" style="margin-top:6px;font-size:12px;color:var(--text2);line-height:1.45;"></div>
      </div>
    </div>`;
}

// Oživí panel vykreslený v `wrap` (#driveFolderContents): ukládání, materiály, světla, 3D náhled,
// fronta testovacích renderů, volba stroje, tlačítko testu. Volá se po každém překreslení složky.
function renderPanelInit(wrap) {
  const maMaterialPanel = !!wrap.querySelector("#matPrirazeniPanel");
  // Tlacitka "použít pro render" / "otestovat render" u kazdeho HDRI souboru
  // zrusena (Robert 2026-09-28: "toto se bije s tím novým systémem roletky") -
  // HDRi se vybira JEN roletou v panelu prirazeni nize, viz ulozPrirazeni.
  // Testovaci render (tlacitko v panelu) = 1 snimek s HDRi z rolety
  // (api/render_hdri.py + scripts/2026-09-24_render_hdri_test_dispatch.py).
  // Polluje stav, dokud render nedobehne.
  // Prirazeni materialu: hodnoty se drzi TRVALE na serveru (app_settings,
  // api/render_hdri.py::render_prirazeni_get/set), ne v localStorage
  // jednoho prohlizece - Robert 2026-09-28: "musí zustat uloženo pro
  // další pouzití" (mysli i jiny pocitac/jineho admina). Nacte se pri
  // otevreni slozky, ulozi se pri kazde zmene (vc. zatrzitka "plati i
  // pro automat" - to samo o sobe nic nerenderuje, jen ho precte
  // pri pristim kroku scripts/2026-09-23_vandr_render_auto_dispatch.py).
  const matPoleId = {
    text: ["matPrirazeniAluMaterial", "matPrirazeniAluKnihovna",
           "matPrirazeniKltMaterial", "matPrirazeniKltKnihovna",
           "matPrirazeniSvetlaSoubor"],
    cislo: ["matPrirazeniCubSeda", "matPrirazeniAoSila", "matPrirazeniHdriId",
            "matPrirazeniHdriSila", "matPrirazeniHdriRotace", "matPrirazeniAzimut",
            "matPrirazeniSvetlaSila"],
  };
  const matKlicPodleId = {
    matPrirazeniAluMaterial: "alu_material", matPrirazeniAluKnihovna: "alu_knihovna_soubor",
    matPrirazeniKltMaterial: "klt_material", matPrirazeniKltKnihovna: "klt_knihovna_soubor",
    matPrirazeniCubSeda: "cub_seda_tmava_sila",
    matPrirazeniAoSila: "alu_ao_sila", matPrirazeniHdriId: "hdri_file_id",
    matPrirazeniHdriSila: "hdri_sila", matPrirazeniHdriRotace: "hdri_rotace_deg",
    matPrirazeniAzimut: "azimut_deg",
    matPrirazeniSvetlaSoubor: "svetla_soubor", matPrirazeniSvetlaSila: "svetla_sila",
  };
  // Robert 2026-09-28: "každý materiál udělej jeden řádek" - radky se
  // generuji ze SKUTECNYCH rodin materialu ve Vandr GLB
  // (/api/admin/render-prirazeni/rodiny), ne z natvrdo psaneho seznamu.
  // Popisky jen pro orientaci; klic je vzdy puvodni jmeno rodiny z modelu.
  const MAT_RODINA_POPIS = {
    "blue klt": "KLT boxy / loga (liší se podle sestavy)", "multibox": "Multibox (přihrádky)", "preklizka hn": "překližka hnědá",
    "preklizka black": "překližka černá", "black": "černé plasty (záslepky, úchyty)",
    "black_2": "černá 2", "cub seda": "šedý plast (police, výplně)", "cub bila": "bílý plast",
    "podlaha_2": "podlaha", "chrome": "chrom (šrouby, trubky)", "red": "červená",
    "box tmava": "tmavý box", "box sv seda": "světle šedý box", "plexi": "plexisklo",
    "orange": "oranžová", "zinc": "zinek", "zinc_2": "zinek 2",
  };
  let matRodinyRadky = [];   // [{rodina, matEl, knEl}]
  let ulozPrirazeni = async () => {};
  // stroje z /api/admin/render-worker/cile (plni nactiCileRenderu nize) - stavovy radek automatu
  // rika, na kterych strojich automat renderuje (Logiman2 + notebook, kdyz pomaha)
  let cileRenderu = [];
  let obnovStavAutomatuHook = () => {};   // nactiCileRenderu po nacteni prekresli stavovy radek
  if (maMaterialPanel) {
    const vsechnaPolePrirazeni = [...matPoleId.text, ...matPoleId.cislo];
    const checkboxAutomat = wrap.querySelector("#matPrirazeniAutomat");
    const svetlaAktivniEl = wrap.querySelector("#matPrirazeniSvetlaAktivni");
    const ulozStavEl = wrap.querySelector("#matPrirazeniUlozStav");
    let poslednePrijate = {};
    // Robert 2026-09-30 ("nech jen 2 světla"): které světla souboru se použijí.
    // svetlaVyber = jména zaškrtnutých světel, patří k souboru svetlaVyberSoubor;
    // svetlaSeznam = světla naposledy načtená ze souboru svetlaSeznamSoubor.
    let svetlaVyber = null, svetlaVyberSoubor = "", svetlaSeznam = [], svetlaSeznamSoubor = "";
    // uložený výběr světel přestal platit, panel ukazuje výchozí, ale server drží starý (neplatný)
    // výběr, dokud se panel neuloží - automat mezitím zařazování odmítá
    let svetlaVyberNeulozen = false, svetlaPreskoceno = 0;
    // hlavni (dřív „použít pro render“) HDRi a natočení - roleta je jediná volba
    const hlavniHdri = { id: null, rot: null, nacteno: false };
    // Robert 2026-09-29: "výběr ze seznamu materiálů, které vybraný soubor
    // opravdu obsahuje" - název materiálu se nepíše rukou, vybírá se z rolety
    // naplněné /api/admin/render-prirazeni/materialy podle souboru v sousedním
    // poli knihovny. Nesedící uložená hodnota se ukáže jako ⚠, ne tiše zahodí.
    const matSeznamCache = {};
    let matSeznamFronta = Promise.resolve();   // po jednom - každý soubor čte Blender
    const nactiSeznamMaterialu = (knihovna) => {
      const k = knihovna || "";
      if (!matSeznamCache[k]) {
        matSeznamCache[k] = matSeznamFronta = matSeznamFronta.then(() =>
          fetch("/api/admin/render-prirazeni/materialy?knihovna=" + encodeURIComponent(k))
            .then(async r => {
              const d = await r.json().catch(() => ({}));
              if (r.ok && Array.isArray(d.materialy)) return { materialy: d.materialy };
              return { chyba: d.error || ("seznam se nenačetl (HTTP " + r.status + ")") };
            })
            .catch(() => ({ chyba: "seznam se nenačetl (server neodpověděl)" }))
        ).then(v => { if (v.chyba) delete matSeznamCache[k]; return v; });
      }
      return matSeznamCache[k];
    };
    const normMat = (s) => String(s || "").toLowerCase().replace(/[^a-z0-9]/g, "");
    // sel = <select> materialu, knEl = pole knihovny vedle nej;
    // bezKnihovny: "vychozi" (radky dilu - prazdna knihovna = vychozi VD knihovna)
    //              | "zakazano" (hlinik/celo - bez knihovny se radek nepouzije)
    const pripojVyberMaterialu = (sel, knEl, bezKnihovny) => {
      let poradi = 0;
      sel._hodnota = "";
      const pridej = (val, text, disabled) => {
        const o = document.createElement("option");
        o.value = val; o.textContent = text; if (disabled) o.disabled = true;
        sel.appendChild(o);
        return o;
      };
      sel.addEventListener("change", () => { sel._hodnota = sel.value; });
      sel._obnov = async (zmenaKnihovny) => {
        const kn = knEl.value.trim();
        const moje = ++poradi;
        sel.style.outline = ""; sel.title = "";
        const prazdny = kn ? "— z knihovny (automaticky) —" : "— nevyplněno (materiál z modelu) —";
        sel.innerHTML = "";
        if (!kn && bezKnihovny === "zakazano") {
          pridej("", "— nejdřív zadej knihovnu —");
          if (sel._hodnota) { pridej(sel._hodnota, sel._hodnota + " (bez knihovny se nepoužije)"); sel.value = sel._hodnota; }
          sel.disabled = true;
          return;
        }
        // hodnota je hned k dispozici i dřív, než se seznam načte
        pridej("", prazdny);
        if (sel._hodnota) { pridej(sel._hodnota, sel._hodnota); sel.value = sel._hodnota; }
        sel.disabled = true;
        const v = await nactiSeznamMaterialu(kn);
        if (moje !== poradi) return;
        sel.innerHTML = "";
        sel.disabled = false;
        if (v.chyba) {
          pridej("", prazdny);
          if (sel._hodnota) pridej(sel._hodnota, "⚠ " + sel._hodnota);
          pridej("", "⚠ " + v.chyba, true);
          sel.value = sel._hodnota;
          sel.style.outline = "2px solid #d9534f";
          sel.title = v.chyba;
          return;
        }
        pridej("", prazdny);
        let zvoleno = "";
        if (sel._hodnota) {
          if (v.materialy.includes(sel._hodnota)) zvoleno = sel._hodnota;
          else {
            const shoda = v.materialy.filter(m => normMat(m) === normMat(sel._hodnota));
            if (shoda.length === 1) zvoleno = shoda[0];
          }
          if (!zvoleno && !zmenaKnihovny) {
            pridej(sel._hodnota, "⚠ " + sel._hodnota + " — v souboru není");
            zvoleno = sel._hodnota;
            sel.style.outline = "2px solid #d9534f";
            sel.title = "Tenhle materiál soubor '" + (kn || "vd_materialy.blend") + "' neobsahuje - vyber z nabídky.";
          }
        }
        v.materialy.forEach(m => pridej(m, m));
        sel.value = zvoleno;
        sel._hodnota = zvoleno;
      };
      sel._nastavHodnotu = (h) => { sel._hodnota = h || ""; return sel._obnov(false); };
      return sel;
    };
    // Robert 2026-09-30: "neříká jasně, jaké se používají nastavení renderu,
    // pokud není zatrženo to spodní" - pod zatržítkem automatu je vždy psáno,
    // podle čeho teď automat opravdu renderuje (platí uložený stav panelu).
    const obnovStavAutomatu = () => {
      const el = wrap.querySelector("#matPrirazeniAutomatStav");
      if (!el) return;
      const pole = pid => ((wrap.querySelector("#" + pid) || {}).value || "").trim();
      const hdriSel = wrap.querySelector("#matPrirazeniHdriId");
      const hdriOpt = hdriSel && hdriSel.value ? hdriSel.selectedOptions[0] : null;
      const hdriNazev = hdriOpt ? hdriOpt.textContent.trim() : "";
      const rot = pole("matPrirazeniHdriRotace");
      const cz = v => String(v).replace(".", ",");
      const hlavni = (hdriNazev ? "HDRi „" + hdriNazev + "“" : "HDRi z nastavení disku")
        + (rot !== "" ? ", natočení " + cz(rot) + "°" : "");
      el.textContent = "";
      const tucne = document.createElement("b");
      const text = document.createElement("span");
      if (!checkboxAutomat || !checkboxAutomat.checked) {
        tucne.textContent = "Automat teď NEPOUŽÍVÁ tenhle panel. ";
        text.textContent = "Renderuje s výchozím nastavením (výchozí materiály, vestavěné osvětlení, "
          + "krycí lišty viditelné). Z panelu bere jen " + hlavni + " — ty platí pro všechny rendery i bez zatržení. "
          + "Všechno ostatní tady platí jen pro testovací rendery.";
      } else {
        const radkuDilu = matRodinyRadky.filter(r => r.matEl.value.trim() || r.knEl.value.trim()).length;
        const cast = [];
        const mat = [];
        if (pole("matPrirazeniAluKnihovna") || pole("matPrirazeniAluMaterial")) mat.push("hliník");
        if (pole("matPrirazeniKltKnihovna") || pole("matPrirazeniKltMaterial")) mat.push("čelo šuplíku");
        if (radkuDilu) mat.push(radkuDilu + " ř. dílů");
        cast.push("materiály: " + (mat.length ? mat.join(" + ") : "výchozí"));
        const svSoubor = pole("matPrirazeniSvetlaSoubor");
        const svVybrano = svetlaSeznamSoubor === svSoubor && svetlaVyberSoubor === svSoubor && svetlaVyber
          ? svetlaVyber.join(" + ") + ", " : "";
        cast.push("světla: " + (svetlaAktivniEl && svetlaAktivniEl.checked && svSoubor
          ? "ze souboru " + svSoubor + " (" + svVybrano + "síla " + cz(pole("matPrirazeniSvetlaSila") || "1,0") + ")"
          : "vestavěná"));
        cast.push(hlavni + (pole("matPrirazeniHdriSila") !== "" ? " (síla " + cz(pole("matPrirazeniHdriSila")) + ")" : ""));
        const krycEl = wrap.querySelector("#matPrirazeniKrycList");
        cast.push("krycí lišty: " + (krycEl && krycEl.checked ? "schované" : "viditelné"));
        tucne.textContent = "Automat teď renderuje podle TOHOTO panelu: ";
        text.textContent = cast.join("; ") + ".";
      }
      el.append(tucne, text);
      // Stroje (bot4 2026-09-30, Robert: automat smi i na notebook): na kterych strojich automat renderuje.
      // Plati vzdy (bez ohledu na zatrzitko nahore) - vyber stroje s panelem nesouvisi.
      if (cileRenderu.length) {
        const vych = cileRenderu.find(c => c.vychozi) || cileRenderu[0];
        const dalsi = cileRenderu.filter(c => c !== vych);
        const stroje = document.createElement("span");
        stroje.style.cssText = "display:block;margin-top:2px;";
        const stav = c => (c.online ? "online" : "offline");
        stroje.textContent = "Stroje automatu: " + vych.jmeno + " (výchozí, " + stav(vych) + ")"
          + (dalsi.length
            ? dalsi.map(c => c.nabidky
              // stroj pro nabidky a testy ze sceny (bot4 2026-10-01): automat ho nepouziva, jinak by nabidka cekala za otockou
              ? " · " + c.jmeno + " (vyhrazený pro nabídky a testy ze scény, automat ho nepoužívá; teď " + stav(c) + ")"
              : " · " + c.jmeno + " (pomáhá, když je " + vych.jmeno + " vytížený nebo vypnutý a stroj je online a volný; teď " + stav(c) + ")").join("")
            : " · notebook se objeví po prvním přihlášení jeho renderovacího agenta") + ".";
        el.appendChild(stroje);
      }
      if (checkboxAutomat && checkboxAutomat.checked && svetlaVyberNeulozen && svetlaAktivniEl && svetlaAktivniEl.checked) {
        const varovani = document.createElement("b");
        varovani.style.color = "var(--danger, #c0392b)";
        varovani.textContent = " ⚠ Uložený výběr světel už v souboru neplatí — automat teď renderování NEZAŘAZUJE, "
          + "dokud panel neuložíš (tlačítko Uložit).";
        el.appendChild(varovani);
      }
    };
    obnovStavAutomatuHook = obnovStavAutomatu;
    // ukládání jde vždy po jednom a každé čte stav panelu až ve chvíli, kdy na něj přijde řada -
    // rychlé zaškrtání dvou světel pak nemůže skončit starším výběrem na serveru
    let ulozRetez = Promise.resolve();
    ulozPrirazeni = () => {
      const dalsi = ulozRetez.then(ulozPrirazeniTelo, ulozPrirazeniTelo);
      ulozRetez = dalsi;
      return dalsi;
    };
    const ulozPrirazeniTelo = async () => {
      const telo = {};
      vsechnaPolePrirazeni.forEach(id => {
        const el = wrap.querySelector(`#${id}`);
        if (el && el.value !== "") telo[matKlicPodleId[id]] = el.value;
      });
      telo.nahrady = matRodinyRadky
        .map(r => ({ role: r.role || "", rodina: r.rodina || "", typ: r.typ || "", material: r.matEl.value.trim(), knihovna_soubor: r.knEl.value.trim() }))
        .filter(r => r.material || r.knihovna_soubor);   // knihovna stačí, materiál se vezme z ní
      telo.aktivni_pro_automat = !!(checkboxAutomat && checkboxAutomat.checked);
      telo.svetla_aktivni = !!(svetlaAktivniEl && svetlaAktivniEl.checked);
      // výběr světel se posílá jen k souboru, ke kterému patří; jinak server
      // použije výchozí 2 nejsilnější (stejné, jako panel ukáže po načtení)
      const svSouborUloz = ((svetlaSouborEl || {}).value || "").trim();
      if (svetlaVyber && svetlaVyber.length && svetlaVyberSoubor === svSouborUloz) telo.svetla_vybrana = svetlaVyber;
      const bylNeulozen = svetlaVyberNeulozen;
      // Robert 2026-09-28: "schované krycí lišty < aplikuj do renderovací
      // tabulky jako zatržítko"
      const krycEl = wrap.querySelector("#matPrirazeniKrycList");
      telo.kryci_listy_skryt = !!(krycEl && krycEl.checked);
      if (ulozStavEl) ulozStavEl.textContent = "ukládám…";
      try {
        const r = await fetch("/api/admin/render-prirazeni", {
          method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(telo),
        });
        const data = await r.json().catch(() => ({}));
        if (!r.ok) throw new Error(data.error || `HTTP ${r.status}`);
        // Robert 2026-09-28: "aktuální určuju právě v té roletě" - HDRi z rolety
        // a natočení platí pro VŠECHNY rendery (i automat a nativní sestavy):
        // ukládá se i jako hlavní volba. Jen když se liší a panel je načtený,
        // prázdná roleta nic nemaže.
        if (hlavniHdri.nacteno) {
          const hdriId = parseInt((wrap.querySelector("#matPrirazeniHdriId") || {}).value, 10);
          if (hdriId && hdriId !== hlavniHdri.id) {
            const rh = await fetch("/api/admin/render-hdri", {
              method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ file_id: hdriId }),
            });
            const dh = await rh.json().catch(() => ({}));
            if (!rh.ok) throw new Error(dh.error || `HDRi: HTTP ${rh.status}`);
            hlavniHdri.id = hdriId;
            driveActiveHdriId = hdriId;
          }
          const rotEl = wrap.querySelector("#matPrirazeniHdriRotace");
          const rot = rotEl && rotEl.value !== "" ? parseFloat(rotEl.value) : null;
          if (rot !== null && !Number.isNaN(rot) && rot !== hlavniHdri.rot) {
            const rr = await fetch("/api/admin/render-hdri-rotace", {
              method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ rotace_deg: rot }),
            });
            const dr = await rr.json().catch(() => ({}));
            if (!rr.ok) throw new Error(dr.error || `natočení: HTTP ${rr.status}`);
            hlavniHdri.rot = rot;
          }
        }
        if (ulozStavEl) ulozStavEl.textContent = "uloženo ✓";
        if (telo.svetla_vybrana) svetlaVyberNeulozen = false;
        if (bylNeulozen && !svetlaVyberNeulozen && telo.svetla_aktivni && svetlaSeznam.length && svetlaSeznamSoubor === svSouborUloz) {
          vykresliSeznamSvetel(svetlaPreskoceno, "");
        }
        obnovStavAutomatu();
        return true;
      } catch (err) {
        if (ulozStavEl) ulozStavEl.textContent = "chyba uložení: " + err.message;
        return false;
      }
    };
    // Robert 2026-09-29: "nastavení světel podle nějakého souboru" - pod polem
    // se ukáže, jaká světla soubor opravdu obsahuje (nebo proč nejde použít).
    const svetlaInfoEl = wrap.querySelector("#matPrirazeniSvetlaInfo");
    const svetlaSeznamEl = wrap.querySelector("#matPrirazeniSvetlaSeznam");
    const svetlaSouborEl = wrap.querySelector("#matPrirazeniSvetlaSoubor");
    const svetlaSilaEl = wrap.querySelector("#matPrirazeniSvetlaSila");
    let svetlaInfoPozadavek = 0;
    const svetlaCz = v => String(v).replace(".", ",");
    const svetlaVykonText = w => svetlaCz(w >= 10 ? Math.round(w) : Math.round(w * 100) / 100) + " W";
    const svetlaPocetText = () => svetlaVyber.length + " ze " + svetlaSeznam.length + " světel";
    // zaškrtávací seznam světel souboru (nejméně jedno musí zůstat)
    const vykresliSeznamSvetel = (preskoceno, poznamka) => {
      if (!svetlaSeznamEl) return;
      svetlaSeznamEl.textContent = "";
      const nadpis = document.createElement("span");
      nadpis.style.color = "var(--text2)";
      nadpis.textContent = "použít světla:";
      svetlaSeznamEl.appendChild(nadpis);
      const nejsilnejsi = Math.max(...svetlaSeznam.map(x => x.vykon || 0));
      svetlaSeznam.forEach(x => {
        const lab = document.createElement("label");
        lab.style.cssText = "display:flex;gap:5px;align-items:center;cursor:pointer;";
        lab.title = "Světlo „" + x.jmeno + "“ ze souboru" + (x.vychozi ? " — patří mezi 2 nejsilnější (výchozí výběr)" : "");
        const cb = document.createElement("input");
        cb.type = "checkbox";
        cb.dataset.svetlo = x.jmeno;
        cb.checked = svetlaVyber.includes(x.jmeno);
        cb.addEventListener("change", () => {
          const zaskrtnuta = [...svetlaSeznamEl.querySelectorAll("input[data-svetlo]")].filter(c => c.checked).map(c => c.dataset.svetlo);
          if (!zaskrtnuta.length) {
            cb.checked = true;    // poslední světlo nejde odškrtnout - render bez světel nedává smysl
            svetlaInfoEl.textContent = "Aspoň jedno světlo musí zůstat zaškrtnuté.";
            setTimeout(() => {
              if (svetlaInfoEl.textContent.startsWith("Aspoň jedno") && svetlaAktivniEl && svetlaAktivniEl.checked) {
                svetlaInfoEl.textContent = "ZAPNUTO — " + svetlaPocetText();
              }
            }, 3000);
            return;
          }
          svetlaVyber = svetlaSeznam.map(y => y.jmeno).filter(j => zaskrtnuta.includes(j));
          svetlaVyberSoubor = svetlaSeznamSoubor;
          svetlaInfoEl.textContent = "ZAPNUTO — " + svetlaPocetText();
          ulozPrirazeni();
        });
        const txt = document.createElement("span");
        txt.style.color = "var(--text2)";
        txt.textContent = x.jmeno + " (" + x.typ + ", " + svetlaVykonText(x.vykon) + ")";
        lab.append(cb, txt);
        if (nejsilnejsi > 0 && (x.vykon || 0) < nejsilnejsi / 100) {
          const slabe = document.createElement("span");
          slabe.style.cssText = "font-size:11px;color:var(--text-muted);";
          slabe.textContent = "téměř nesvítí";
          lab.appendChild(slabe);
        }
        svetlaSeznamEl.appendChild(lab);
      });
      if (preskoceno) {
        const p = document.createElement("span");
        p.style.cssText = "font-size:11px;color:var(--text-muted);";
        p.textContent = "(+" + preskoceno + " vypnuté v souboru, nepoužije se)";
        svetlaSeznamEl.appendChild(p);
      }
      if (poznamka) {
        const p = document.createElement("span");
        p.style.cssText = "font-size:11px;color:var(--danger, #c0392b);";
        p.textContent = poznamka;
        svetlaSeznamEl.appendChild(p);
      }
      svetlaSeznamEl.style.display = "flex";
    };
    // Robert 2026-09-30: "neříká jasně jestli jsou světla aktivní nebo ne" -
    // zatržítko + text ZAPNUTO/VYPNUTO, při vypnutí jsou pole ztlumená.
    const obnovInfoSvetel = async () => {
      if (!svetlaInfoEl) return;
      const zapnuto = !!(svetlaAktivniEl && svetlaAktivniEl.checked);
      [svetlaSouborEl, svetlaSilaEl].forEach(e => { if (e) e.style.opacity = zapnuto ? "" : "0.45"; });
      const soubor = ((svetlaSouborEl || {}).value || "").trim();
      const moje = ++svetlaInfoPozadavek;
      svetlaInfoEl.style.color = "";
      const skryjSeznam = () => { if (svetlaSeznamEl) { svetlaSeznamEl.style.display = "none"; svetlaSeznamEl.textContent = ""; } };
      if (!zapnuto) {
        skryjSeznam();
        svetlaInfoEl.textContent = "VYPNUTO — render použije vestavěné osvětlení" + (soubor ? " (soubor zůstává uložený)" : "");
        return;
      }
      if (!soubor) { skryjSeznam(); svetlaInfoEl.textContent = "zapnuto, ale chybí soubor — render použije vestavěné osvětlení"; return; }
      svetlaInfoEl.textContent = "čtu soubor…";
      // starý seznam (jiný soubor) by během čtení zůstal klikatelný a jeho klik by se ztratil
      if (soubor !== svetlaSeznamSoubor) skryjSeznam();
      let text, chyba = false, d = {};
      try {
        const r = await fetch("/api/admin/render-prirazeni/svetla?soubor=" + encodeURIComponent(soubor));
        d = await r.json().catch(() => ({}));
        if (!(r.ok && Array.isArray(d.svetla))) { text = "⚠ " + (d.error || "HTTP " + r.status); chyba = true; }
      } catch (err) { text = "⚠ " + err.message; chyba = true; }
      if (moje !== svetlaInfoPozadavek) return;   // mezitím se soubor změnil
      svetlaInfoEl.style.color = chyba ? "var(--danger, #c0392b)" : "";
      if (chyba) { skryjSeznam(); svetlaInfoEl.textContent = text; return; }
      // server bez výběru světel (stará verze API) by vrátil světla bez `vychozi` a render
      // by pak použil všechna - raději hlasitá chyba než tichý rozdíl mezi panelem a renderem
      if (d.svetla.length && !d.svetla.some(x => x.vychozi === true)) {
        skryjSeznam();
        svetlaInfoEl.style.color = "var(--danger, #c0392b)";
        svetlaInfoEl.textContent = "⚠ API neumí výběr světel (je potřeba restartovat službu konfigurator)";
        return;
      }
      // výběr platí jen, když patří k tomuhle souboru a všechna jeho světla v něm jsou;
      // jinak výchozí = 2 nejsilnější (server je určuje stejně)
      const jmena = d.svetla.map(x => x.jmeno);
      const platny = svetlaVyberSoubor === soubor && Array.isArray(svetlaVyber) && svetlaVyber.length
        && svetlaVyber.every(j => jmena.includes(j));
      const bylVyber = svetlaVyberSoubor === soubor && Array.isArray(svetlaVyber) && svetlaVyber.length;
      svetlaSeznam = d.svetla;
      svetlaSeznamSoubor = soubor;
      if (!platny) svetlaVyber = d.svetla.filter(x => x.vychozi).map(x => x.jmeno);
      svetlaVyberSoubor = soubor;
      svetlaPreskoceno = d.preskoceno;
      svetlaVyberNeulozen = !!(bylVyber && !platny);
      svetlaInfoEl.textContent = "ZAPNUTO — " + svetlaPocetText();
      vykresliSeznamSvetel(d.preskoceno, bylVyber && !platny
        ? "uložený výběr světel už v souboru neplatí, nastavena výchozí 2 nejsilnější (uloží se při další změně panelu)" : "");
      obnovStavAutomatu();
    };
    if (svetlaSouborEl) svetlaSouborEl.addEventListener("change", () => {
      // nový soubor = chci ho použít; ukládá až obecný posluchač níže
      if (svetlaAktivniEl && svetlaSouborEl.value.trim() && !svetlaAktivniEl.checked) svetlaAktivniEl.checked = true;
      obnovInfoSvetel();
    });
    // ukládá se až po načtení světel souboru - jinak by šel na server starý, už neplatný výběr
    if (svetlaAktivniEl) svetlaAktivniEl.addEventListener("change", async () => { await obnovInfoSvetel(); ulozPrirazeni(); });
    const rodinyEl = wrap.querySelector("#matPrirazeniRodiny");
    Promise.all([
      fetch("/api/admin/render-prirazeni").then(r => r.json()).catch(() => ({})),
      fetch("/api/admin/render-prirazeni/rodiny").then(r => r.json()).catch(() => ({ rodiny: [] })),
      fetch("/api/admin/render-hdri-rotace").then(r => r.json()).catch(() => ({})),
    ]).then(([n, rd, hlRot]) => {
      hlavniHdri.id = driveActiveHdriId;
      hlavniHdri.rot = (hlRot && hlRot.rotace_deg !== null && hlRot.rotace_deg !== undefined) ? Number(hlRot.rotace_deg) : null;
      hlavniHdri.nacteno = true;
      poslednePrijate = n || {};
      vsechnaPolePrirazeni.forEach(id => {
        const el = wrap.querySelector(`#${id}`);
        const hodnota = poslednePrijate[matKlicPodleId[id]];
        if (!el || hodnota === undefined || hodnota === null) return;
        // materialove role plni pripojVyberMaterialu nize; roleta HDRi je taky <select>, ale hodnotu bere odsud
        if (el.tagName === "SELECT" && id !== "matPrirazeniHdriId") return;
        el.value = hodnota;
        if (id === "matPrirazeniHdriId" && hodnota && String(el.value) !== String(hodnota)) {
          const o = document.createElement("option");
          o.value = String(hodnota);
          o.textContent = "⚠ uložený HDRi soubor (#" + hodnota + ") už v této složce není";
          el.appendChild(o);
          el.value = String(hodnota);
        }
      });
      [["matPrirazeniAluMaterial", "matPrirazeniAluKnihovna"], ["matPrirazeniKltMaterial", "matPrirazeniKltKnihovna"]]
        .forEach(([mid, kid]) => {
          const sel = wrap.querySelector("#" + mid), kn = wrap.querySelector("#" + kid);
          if (!sel || !kn) return;
          pripojVyberMaterialu(sel, kn, "zakazano");
          sel._nastavHodnotu(poslednePrijate[matKlicPodleId[mid]]);
        });
      if (checkboxAutomat) checkboxAutomat.checked = !!poslednePrijate.aktivni_pro_automat;
      // starý uložený stav bez klíče: světla jsou zapnutá, je-li vyplněný soubor
      if (svetlaAktivniEl) svetlaAktivniEl.checked = poslednePrijate.svetla_aktivni === undefined
        ? !!poslednePrijate.svetla_soubor : !!poslednePrijate.svetla_aktivni;
      if (Array.isArray(poslednePrijate.svetla_vybrana) && poslednePrijate.svetla_vybrana.length) {
        svetlaVyber = poslednePrijate.svetla_vybrana.slice();
        svetlaVyberSoubor = String(poslednePrijate.svetla_soubor || "").trim();
      }
      const krycElN = wrap.querySelector("#matPrirazeniKrycList");
      if (krycElN) krycElN.checked = !!poslednePrijate.kryci_listy_skryt;
      obnovInfoSvetel();
      obnovStavAutomatu();
      if (!rodinyEl) return;
      // Robert 2026-09-28: "v různých sestavách mají multiboxy různý
      // materiál" -> radky podle ROLE DILU (skupina nad dilem v exportu,
      // napr. Multibox_Arc = prihradky Multibox, at maji material "blue KLT"
      // nebo "multibox"), ne podle jmena materialu ze zdroje. Kazda role jde
      // dal rozdelit podle typu komponenty (KLT box, Police s Multiboxy...).
      // Klic radku ve 3D: "role:<role>" / "role:<role>@<typ>".
      const ulozene = {};
      (poslednePrijate.nahrady || []).forEach(r => {
        if (r.role) ulozene[String(r.role).toLowerCase() + "|" + (r.typ || "")] = r;
      });
      const role = (rd && rd.role) || [];
      rodinyEl.innerHTML = "";
      matRodinyRadky = [];
      if (!role.length) {
        // bez seznamu roli tabulka chybi, ale 3D nahled (hlinik, celo) ma
        // nabehnout dal - drive tu byl `return` a preskocil i matPrirazeni3dInit
        rodinyEl.innerHTML = `<div style="color:var(--text-muted);grid-column:1/-1;">seznam dílů se nepodařilo načíst</div>`;
      }
      const dvojiceMaterialKnihovna = (placeholderKnihovny, hodnotaMat, hodnotaKn) => {
        const matEl = document.createElement("select");
        matEl.style.cssText = "font-size:12px;min-width:0;";
        const knEl = document.createElement("input");
        knEl.type = "text"; knEl.placeholder = placeholderKnihovny; knEl.style.fontSize = "12px";
        pripojVyberMaterialu(matEl, knEl, "vychozi");
        matEl.addEventListener("change", ulozPrirazeni);
        knEl.addEventListener("change", async () => { await matEl._obnov(true); ulozPrirazeni(); });
        knEl.value = hodnotaKn || "";
        matEl._nastavHodnotu(hodnotaMat);
        return [matEl, knEl];
      };
      role.forEach(r => {
        const klic3d = "role:" + r.role;
        const lab = document.createElement("div");
        lab.style.color = "var(--text2)";
        lab.className = "mp-lab";
        lab.dataset.rodina3d = klic3d;
        const zdroj = (r.rodiny || []).length ? ` <span style="color:var(--text-muted);font-size:10.5px;">— materiál ve zdroji: ${escapeHtmlAdmin(r.rodiny.join(", "))}</span>` : "";
        lab.innerHTML = `<button type="button" class="mp-oko" data-rodina3d="${escapeHtmlAdmin(klic3d)}" title="Ukázat ve 3D">👁</button> `
          + `${escapeHtmlAdmin(r.nazev)}${zdroj}`
          + `<br><span style="color:var(--text-muted);font-size:10.5px;">ve ${r.sestav} sestavách · ${r.dilu} dílů</span>`;
        const u = ulozene[r.role + "|"] || {};
        const [matEl, knEl] = dvojiceMaterialKnihovna("knihovna .blend (prázdné = výchozí VD)", u.material, u.knihovna_soubor);
        rodinyEl.append(lab, matEl, knEl);
        matRodinyRadky.push({ role: r.role, typ: "", matEl, knEl });
        // "ostatní díly" (typ "") = totéž co hlavní řádek (sdílí klíč role|"") -
        // jako podřádek jen zdvojoval hodnotu a sám rozbaloval skupinu
        const typy = (r.typy || []).filter(t => t.typ && t.typ !== "logo" && t.typ !== "podlaha");
        if (typy.length > 1) {
          const bunkyPod = [];
          const podRadky = [];
          typy.forEach(t => {
            const k3 = klic3d + "@" + t.typ;
            const pl = document.createElement("div");
            pl.className = "mp-lab"; pl.dataset.rodina3d = k3;
            pl.style.cssText = "color:var(--text2);padding-left:22px;font-size:11.5px;";
            pl.innerHTML = `<button type="button" class="mp-oko" data-rodina3d="${escapeHtmlAdmin(k3)}" title="Ukázat ve 3D">👁</button> `
              + `↳ ${escapeHtmlAdmin(t.nazev)} <span style="color:var(--text-muted);font-size:10.5px;">— ve ${t.sestav} sestavách</span>`;
            const up = ulozene[r.role + "|" + t.typ] || {};
            const [pm, pk] = dvojiceMaterialKnihovna("knihovna .blend (jen pro " + t.nazev + ")", up.material, up.knihovna_soubor);
            [pl, pm, pk].forEach(el => { el.hidden = true; bunkyPod.push(el); });
            rodinyEl.append(pl, pm, pk);
            podRadky.push([pm, pk]);
            matRodinyRadky.push({ role: r.role, typ: t.typ, matEl: pm, knEl: pk });
          });
          const tl = document.createElement("button");
          tl.type = "button"; tl.className = "mp-rozdelit";
          tl.style.cssText = "font-size:10.5px;padding:0 6px;margin-left:4px;";
          const nastav = (otevrit) => {
            bunkyPod.forEach(el => { el.hidden = !otevrit; });
            const vyplneno = podRadky.filter(([a, b]) => a.value.trim() || b.value.trim()).length;
            tl.textContent = (otevrit ? "▾ sbalit" : "▸ rozdělit podle dílu") + ` (${typy.length})`
              + (vyplneno ? ` · vyplněno ${vyplneno}` : "");
            tl.dataset.otevreno = otevrit ? "1" : "";
          };
          tl.addEventListener("click", (e) => { e.preventDefault(); e.stopPropagation(); nastav(!tl.dataset.otevreno); });
          lab.appendChild(tl);
          lab._rozbalit = () => nastav(true);
          // Robert 2026-09-28: "tu tabulku chci normálně zabalenou/sbalenou" -
          // vždy sbalené, vyplněné podřádky ukazuje počet na tlačítku
          nastav(false);
        }
      });
      obnovStavAutomatu();   // řádky dílů už jsou načtené
      matPrirazeni3dInit(rd);
    });

    // Robert 2026-09-28: "u HDRi přiřazovací tabulce musíš vykreslit celou
    // sestavu... a zvýraznit materiál ve 3D modelu, který to je" + "může
    // v tom být chaos". 3D = kontrolni scena (rezim=materialy) v iframe,
    // 👁 u radku = zvyraznit (kdyz tahle sestava material nema, prepne na
    // prvni, ktera ho ma), klik na dil v modelu = oznaci radek tabulky.
    function matPrirazeni3dInit(rd) {
      const panelEl = wrap.querySelector("#matPrirazeniPanel");
      const st = {
        iframe: wrap.querySelector("#matPrirazeni3d"),
        select: wrap.querySelector("#matPrirazeni3dKarta"),
        dalsi: wrap.querySelector("#matPrirazeni3dDalsi"),
        info: wrap.querySelector("#matPrirazeni3dInfo"),
        karta: null, nacteno: false, pritomne: new Set(), celoPritomne: false, aktivni: null,
        kartaRodiny: {}, kartyRodiny: (rd && rd.karty_rodiny) || {}, nazvy: (rd && rd.nazvy_karet) || {},
        kartyRodinyTyp: (rd && rd.karty_rodiny_typ) || {}, kombinace: new Set(),
        kartyRole: (rd && rd.karty_role) || {}, kartyRoleTyp: (rd && rd.karty_role_typ) || {},
        rolePritomne: new Set(), kombinaceRole: new Set(),
        roleVTabulce: new Set(((rd && rd.role) || []).map(x => x.role)),
        celkem: (rd && rd.celkem_rodin) || 0,
      };
      if (!panelEl || !st.iframe || !st.select) return;
      matPrirazeni3dStav = st;
      // Prilepeni 3D okna pri posunu stranky JEN kdyz je vedle tabulky - v
      // uzkem okne (3D nad tabulkou) by prilepene prekryvalo radky tabulky
      // (nalezeno Playwright snimkem 2026-09-28).
      const kol3d = wrap.querySelector("#matPrirazeni3dKol");
      const kolTab = kol3d && kol3d.nextElementSibling;
      const upravSticky = () => {
        if (!kol3d || !kolTab) return;
        kol3d.style.position = Math.abs(kol3d.offsetTop - kolTab.offsetTop) < 5 ? "sticky" : "static";
      };
      const ro = new ResizeObserver(() => { if (!panelEl.isConnected) { ro.disconnect(); return; } upravSticky(); });
      ro.observe(panelEl);
      upravSticky();
      ((rd && rd.rodiny) || []).forEach(r => { if (r.karta) st.kartaRodiny[r.rodina.toLowerCase()] = r.karta; });
      Object.entries((rd && rd.specialni_karta) || {}).forEach(([k, v]) => { if (v) st.kartaRodiny[k] = v; });
      // vychozi a nabizene sestavy = pokryti podle ROLI (tabulka je podle roli)
      const sestavy = ((rd && rd.sestavy_role) || []).length ? rd.sestavy_role : ((rd && rd.sestavy) || []);
      const nazevKarty = k => st.nazvy[k] || ("karta " + k);
      const pridejMoznost = (karta, popis) => {
        if ([...st.select.options].some(o => o.value === String(karta))) return;
        const o = document.createElement("option");
        o.value = String(karta); o.textContent = popis || nazevKarty(karta);
        st.select.appendChild(o);
      };
      sestavy.forEach(x => pridejMoznost(x.karta, x.pocet_roli != null
        ? `${x.nazev} — ${x.pocet_roli} z ${st.roleVTabulce.size} dílů`
        : `${x.nazev} — ${x.pocet_rodin} z ${st.celkem} materiálů`));
      const klicLc = klic => (klic === "__celo__" ? "tyrkys" : String(klic || "").toLowerCase().split("@")[0]);
      // klic radku: "ALU" (cela rodina), "blue KLT@multibox" (rodina jen v
      // danem typu dilu), "__celo__" (celo supliku = tyrkys v Suplik)
      // klic: "ALU" (rodina), "role:multiboxarc[@typ]" (role dilu), "__celo__"
      const rozloz = klic => {
        if (klic === "__celo__") return { druh: "role", jmeno: "drawer", typ: null, celo: true };
        let t = String(klic || "").toLowerCase();
        const druh = t.startsWith("role:") ? "role" : "rodina";
        if (druh === "role") t = t.slice(5);
        const [j, ty] = t.split("@");
        return { druh, jmeno: j, typ: ty === undefined ? null : ty, celo: false };
      };
      const jeVSestave = klic => {
        const k = rozloz(klic);
        if (k.celo) return st.celoPritomne;
        if (k.druh === "role") return k.typ === null ? st.rolePritomne.has(k.jmeno) : st.kombinaceRole.has(k.jmeno + "|" + k.typ);
        return k.typ === null ? st.pritomne.has(k.jmeno) : st.kombinace.has(k.jmeno + "|" + k.typ);
      };
      const kartyPro = klic => {
        const k = rozloz(klic);
        if (k.druh === "role") return k.typ === null ? (st.kartyRole[k.jmeno] || []) : (st.kartyRoleTyp[k.jmeno + "|" + k.typ] || []);
        return k.typ === null ? (st.kartyRodiny[k.jmeno] || []) : (st.kartyRodinyTyp[k.jmeno + "|" + k.typ] || []);
      };

      st.posliNastaveni = () => {
        const k = wrap.querySelector("#matPrirazeniKrycList");
        if (st.iframe.contentWindow) st.iframe.contentWindow.postMessage(
          { typ: "kontrola-nastaveni", kryciListySkryt: !!(k && k.checked) }, location.origin);
      };
      st.postni = (klic) => {
        if (st.iframe.contentWindow) st.iframe.contentWindow.postMessage({ typ: "kontrola-zvyraznit", rodina: klic || null }, location.origin);
      };
      st.nacti = (karta, zvyraznit) => {
        st.karta = karta; st.nacteno = false; st.pritomne = new Set(); st.celoPritomne = false; st.kombinace = new Set();
        st.rolePritomne = new Set(); st.kombinaceRole = new Set();
        pridejMoznost(karta);
        st.select.value = String(karta);
        st.info.textContent = "načítám " + nazevKarty(karta) + "…";
        st.iframe.src = `/api/kontrola-scena?items=vd:${karta}&rezim=materialy`
          + (zvyraznit ? `&zvyraznit=${encodeURIComponent(zvyraznit)}` : "");
        st.aktualizujDalsi();
      };
      st.zvyrazniRadek = (klic) => {
        panelEl.querySelectorAll(".mp-lab").forEach(el => { el.style.background = ""; el.style.outline = ""; });
        if (!klic) return;
        const labs = [...panelEl.querySelectorAll(".mp-lab")];
        const najdi = k => labs.find(x => (x.dataset.rodina3d || "").toLowerCase() === String(k).toLowerCase());
        // klik v modelu posila "rodina@typ" - podradek (rozbalit, kdyz je
        // sbaleny), jinak radek cele rodiny
        let el = najdi(klic);
        if (el && el.hidden) {
          const rodinny = najdi(String(klic).split("@")[0]);
          if (rodinny && rodinny._rozbalit) rodinny._rozbalit();
        }
        if (!el) el = najdi(String(klic).split("@")[0]);
        if (el) {
          el.style.background = "rgba(255,31,75,.16)";
          el.style.outline = "1px solid rgba(255,31,75,.55)";
          el.scrollIntoView({ block: "nearest" });
        }
      };
      st.aktualizujDalsi = () => {
        const seznam = st.aktivni ? kartyPro(st.aktivni) : [];
        st.dalsi.disabled = seznam.length < 2;
        const i = seznam.indexOf(st.karta);
        st.dalsi.textContent = "další sestava s tímto materiálem ›" + (seznam.length > 1 ? ` (${i + 1 || "–"}/${seznam.length})` : "");
      };
      st.oznacRadky = () => {
        panelEl.querySelectorAll(".mp-oko").forEach(b => {
          const je = jeVSestave(b.dataset.rodina3d);
          b.style.opacity = je ? "1" : "0.45";
          b.title = je ? "Ukázat ve 3D" : ("V této sestavě není — přepne na: " + nazevKarty(kartyPro(b.dataset.rodina3d)[0]));
        });
        // jen rodiny z tabulky (bez materialu razitek/log z katalogu)
        const vTabulce = [...st.rolePritomne].filter(r => st.roleVTabulce.has(r)).length;
        st.info.textContent = `${nazevKarty(st.karta)}: ${vTabulce} z ${st.roleVTabulce.size} dílů tabulky · 👁 u řádku nebo klik na díl v modelu`;
      };
      st.ukaz = (klic) => {
        st.aktivni = klic;
        st.zvyrazniRadek(klic);
        const je = st.nacteno && jeVSestave(klic);
        const jinaKarta = kartyPro(klic)[0] || st.kartaRodiny[klicLc(klic)];
        if (!je && jinaKarta && jinaKarta !== st.karta) st.nacti(jinaKarta, klic);
        else st.postni(klic); // pri nacitani si ho iframe zapamatuje (a po nacteni posleme znovu)
        st.aktualizujDalsi();
      };

      panelEl.addEventListener("click", (e) => {
        const b = e.target.closest(".mp-oko");
        if (!b || !panelEl.contains(b)) return;
        e.preventDefault(); e.stopPropagation();
        st.ukaz(st.aktivni === b.dataset.rodina3d ? null : b.dataset.rodina3d); // druhy klik = zrusit
      });
      st.select.addEventListener("change", () => st.nacti(Number(st.select.value), st.aktivni));
      st.dalsi.addEventListener("click", (e) => {
        e.stopPropagation();
        const seznam = kartyPro(st.aktivni);
        if (seznam.length < 2) return;
        const i = seznam.indexOf(st.karta);
        st.nacti(seznam[(i + 1) % seznam.length], st.aktivni);
      });

      if (!matPrirazeni3dPosluchac) {
        matPrirazeni3dPosluchac = true;
        window.addEventListener("message", (e) => {
          const s3 = matPrirazeni3dStav;
          if (!s3 || e.origin !== location.origin || !e.data || !s3.iframe.isConnected
              || e.source !== s3.iframe.contentWindow) return;
          if (e.data.typ === "kontrola-rodiny") {
            s3.nacteno = true;
            s3.pritomne = new Set((e.data.rodiny || []).map(r => String(r).toLowerCase()));
            s3.celoPritomne = !!e.data.celo;
            s3.kombinace = new Set((e.data.kombinace || []).map(k => String(k).toLowerCase()));
            s3.rolePritomne = new Set((e.data.role || []).map(k => String(k).toLowerCase()));
            s3.kombinaceRole = new Set((e.data.kombinaceRole || []).map(k => String(k).toLowerCase()));
            s3.posliNastaveni();
            s3.oznacRadky();
            if (s3.aktivni) s3.postni(s3.aktivni);
            s3.aktualizujDalsi();
          } else if (e.data.typ === "kontrola-klik") {
            s3.aktivni = e.data.rodina || null;
            s3.zvyrazniRadek(s3.aktivni);
            s3.aktualizujDalsi();
          }
        });
      }
      if (sestavy.length) st.nacti(sestavy[0].karta, null);
      else st.info.textContent = "3D náhled: žádná Vandr sestava k dispozici";
    }
    const materialKKnihovne = { matPrirazeniAluKnihovna: "matPrirazeniAluMaterial", matPrirazeniKltKnihovna: "matPrirazeniKltMaterial" };
    vsechnaPolePrirazeni.forEach(id => {
      const el = wrap.querySelector(`#${id}`);
      if (!el) return;
      if (materialKKnihovne[id]) {
        el.addEventListener("change", async () => {
          const sel = wrap.querySelector("#" + materialKKnihovne[id]);
          if (sel && sel._obnov) await sel._obnov(true);
          ulozPrirazeni();
        });
      } else {
        el.addEventListener("change", ulozPrirazeni);
      }
    });
    if (checkboxAutomat) checkboxAutomat.addEventListener("change", ulozPrirazeni);
    // stavový řádek automatu se přepíše hned při každé změně, ne až po uložení
    wrap.addEventListener("change", () => obnovStavAutomatu());
    wrap.addEventListener("input", () => obnovStavAutomatu());
    const krycElZ = wrap.querySelector("#matPrirazeniKrycList");
    if (krycElZ) krycElZ.addEventListener("change", () => {
      ulozPrirazeni();
      if (matPrirazeni3dStav && matPrirazeni3dStav.posliNastaveni) matPrirazeni3dStav.posliNastaveni();
    });
    // Robert 2026-09-28: "a kde je volba uložit" - automaticke ukladani pri
    // zmene pole neni videt, explicitni tlacitko (stejna funkce).
    const btnUlozit = wrap.querySelector("#matPrirazeniUlozit");
    if (btnUlozit) btnUlozit.addEventListener("click", (e) => { e.stopPropagation(); ulozPrirazeni(); });
  }

  // Fronta testovacich renderu (Robert 2026-09-29: "kdyz budu opakovane
  // klikat spustit render a pritom menit napr HDri nebo jine parametry, nech
  // se to ukládá do fronty"). Kazde kliknuti = vlastni pozadavek s vlastnim
  // otiskem nastaveni panelu (server ho zapise pri zarazeni), automat je
  // zpracuje po jednom za sebou. Tlacitko proto zustava aktivni.
  const frontaEl = wrap.querySelector("#matPrirazeniFronta");
  const OBNOVENI_FRONTY_MS = 12000;
  const vykresliFrontu = (testy) => {
    if (!frontaEl) return;
    if (!testy.length) { frontaEl.innerHTML = ""; return; }
    const cekajici = testy.filter(t => t.status === "pending").map(t => t.id).sort((x, y) => x - y);
    const bezi = testy.some(t => t.status === "dispatched");
    frontaEl.innerHTML = testy.map(t => {
      const azimut = t.azimut_deg !== null && t.azimut_deg !== undefined && t.azimut_deg !== ""
        ? `azimut ${Math.round(Number(t.azimut_deg))}°` : "zepředu";
      const popis = [azimut, t.hdri_filename,
        t.hdri_rotace_deg !== null ? `natočení ${t.hdri_rotace_deg}°` : null,
        t.hdri_sila !== null ? `síla ${t.hdri_sila}` : null,
        t.render_na ? `na: ${t.render_na}` : null].filter(Boolean).join(" · ");
      let stav;
      if (t.status === "done" && t.frame_url) {
        const odkaz = t.drive_download_url || t.frame_url;
        const mAz = /\/a(\d{3})\.jpg/.exec(t.frame_url);
        const zadano = t.azimut_deg !== null && t.azimut_deg !== undefined && t.azimut_deg !== "" ? Math.round(Number(t.azimut_deg)) % 360 : null;
        const varovani = mAz && zadano !== null && parseInt(mAz[1], 10) !== zadano
          ? ` — POZOR, vyrenderováno ${parseInt(mAz[1], 10)}°` : "";
        stav = `<a href="${escapeHtmlAdmin(odkaz)}" target="_blank" draggable="false">✓ zobrazit render${t.drive_download_url ? " (na disku)" : ""}</a>${escapeHtmlAdmin(varovani)}`;
      } else if (t.status === "done") {
        stav = "hotovo, ale snímek chybí";
      } else if (t.status === "error") {
        stav = `<span style="color:#d9534f;">chyba: ${escapeHtmlAdmin(t.error || "neznámá")}</span>`;
      } else if (t.status === "dispatched") {
        stav = "renderuje… (1 snímek, pár minut)";
      } else {
        const pozice = cekajici.indexOf(t.id) + 1 + (bezi ? 1 : 0);
        stav = `čeká ve frontě (${pozice}.)`;
      }
      return `<div style="display:flex;gap:8px;flex-wrap:wrap;align-items:baseline;">`
        + `<span style="color:var(--text-muted);">#${t.id} · ${escapeHtmlAdmin(t.requested_at || "")}</span>`
        + `<span>${escapeHtmlAdmin(popis)}</span><span>${stav}</span></div>`;
    }).join("");
  };
  let casovacFronty = null;
  const obnovFrontu = async () => {
    if (casovacFronty) { clearTimeout(casovacFronty); casovacFronty = null; }
    if (!frontaEl || !frontaEl.isConnected) return;
    let testy;
    try {
      const r = await fetch("/api/admin/render-hdri/test-render");
      const data = await r.json();
      if (!r.ok) throw new Error(data.error || `HTTP ${r.status}`);
      testy = data.testy || [];
    } catch (err) {
      frontaEl.textContent = "fronta testů: nejde načíst (" + err.message + ")";
      casovacFronty = setTimeout(obnovFrontu, OBNOVENI_FRONTY_MS);
      return;
    }
    vykresliFrontu(testy);
    if (testy.some(t => t.status === "pending" || t.status === "dispatched")) {
      casovacFronty = setTimeout(obnovFrontu, OBNOVENI_FRONTY_MS);
    }
  };
  obnovFrontu();

  // Kde renderovat test (Robert 2026-09-29: "nastav mi tam moznost renderovat
  // u mě"): GPU stanice (vychozi) nebo dalsi stroj, na kterem bezi
  // renderovaci agent (notebook). Vybere se jen pro TENHLE test; produkce a
  // automat jdou na GPU stanici, notebook jim od 2026-09-30 jen POMAHA, kdyz je
  // online a volny (scripts/_render_stroje.py). Offline stroj zustane vybratelny a
  // server ho hlasite odmitne s duvodem - zadne tiche prepnuti jinam.
  const kdeEl = wrap.querySelector("#matPrirazeniKde");
  const kdeWrapEl = wrap.querySelector("#matPrirazeniKdeWrap");
  const kdeNapovedaEl = wrap.querySelector("#matPrirazeniKdeNapoveda");
  const KDE_KLIC = "renderKdeTest";
  const nactiCileRenderu = async () => {
    if (!kdeEl || !kdeEl.isConnected) return;
    let cile;
    try {
      const r = await fetch("/api/admin/render-worker/cile");
      const d = await r.json();
      if (!r.ok || !Array.isArray(d.cile) || !d.cile.length) return;   // starsi server bez volby - panel se chova jako driv
      cile = d.cile;
    } catch (err) { return; }
    cileRenderu = cile;
    obnovStavAutomatuHook();   // stavovy radek automatu ukazuje i stroje
    let zvolene = kdeEl.value;
    if (!zvolene) { try { zvolene = localStorage.getItem(KDE_KLIC) || ""; } catch (err) { zvolene = ""; } }
    kdeEl.innerHTML = "";
    cile.forEach(c => {
      const o = document.createElement("option");
      o.value = c.vychozi ? "" : c.jmeno;
      const gpu = c.gpu ? " – " + String(c.gpu).replace(/^(OPTIX|CUDA|HIP|METAL|ONEAPI):\s*/i, "").replace(/^NVIDIA\s+/i, "") : "";
      o.textContent = c.jmeno + (c.vychozi ? " (výchozí)" : "") + gpu + (c.online ? "" : " — offline");
      if (!c.online && c.duvod) o.title = c.duvod;
      kdeEl.appendChild(o);
    });
    kdeEl.value = zvolene;
    if (kdeEl.value !== zvolene) kdeEl.value = "";
    kdeWrapEl.style.display = "flex";
    if (kdeNapovedaEl) kdeNapovedaEl.textContent = cile.length < 2
      ? "(notebook se tu objeví po prvním přihlášení jeho renderovacího agenta)" : "";
  };
  if (kdeEl) {
    kdeEl.addEventListener("change", () => { try { localStorage.setItem(KDE_KLIC, kdeEl.value); } catch (err) { /* jen pohodli */ } });
    kdeEl.addEventListener("focus", nactiCileRenderu);
    nactiCileRenderu();
  }

  const spustitPrirazeniRender = async (fileId, stavEl, btn) => {
    const ctiPole = pid => (wrap.querySelector(`#${pid}`) || {}).value || null;
    const telo = {
      alu_material: ctiPole("matPrirazeniAluMaterial"),
      alu_knihovna_soubor: ctiPole("matPrirazeniAluKnihovna"),
      klt_material: ctiPole("matPrirazeniKltMaterial"),
      klt_knihovna_soubor: ctiPole("matPrirazeniKltKnihovna"),
      cub_seda_tmava_sila: ctiPole("matPrirazeniCubSeda"),
      alu_ao_sila: ctiPole("matPrirazeniAoSila"),
      hdri_sila: ctiPole("matPrirazeniHdriSila"),
      hdri_rotace_deg: ctiPole("matPrirazeniHdriRotace"),
      svetla_soubor: ctiPole("matPrirazeniSvetlaSoubor"),
      svetla_sila: ctiPole("matPrirazeniSvetlaSila"),
      render_na: kdeEl && kdeEl.value ? kdeEl.value : null,
    };
    // Tlacitko je zamcene jen po dobu ulozeni + zarazeni (zlomek vteriny),
    // aby otisk panelu patril presne tomuhle kliknuti; pak jde kliknout dal.
    btn.disabled = true;
    try {
      if (stavEl) stavEl.textContent = "ukládám…";
      // Kdyz se panel neulozi (napr. neznamy material), nezarazovat - jinak
      // by test bezel se starym ulozenym stavem a nikdo by to nevidel.
      if ((await ulozPrirazeni()) === false) {
        if (stavEl) stavEl.textContent = "test nezařazen - panel se neuložil (viz chyba u Uložit)";
        return;
      }
      if (stavEl) stavEl.textContent = "zařazuji…";
      const r = await fetch(`/api/admin/render-hdri/${fileId}/test-render`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(telo),
      });
      const data = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(data.error || `HTTP ${r.status}`);
      if (stavEl) stavEl.textContent = `zařazeno do fronty ✓ (#${data.request_id}${data.render_na ? ", na " + data.render_na : ""})`;
    } catch (err) {
      if (stavEl) stavEl.textContent = "chyba: " + err.message;
      return;
    } finally {
      btn.disabled = false;
    }
    obnovFrontu();
  };

  const btnPrirazeniSpustit = wrap.querySelector("#matPrirazeniSpustit");
  if (btnPrirazeniSpustit) {
    btnPrirazeniSpustit.onclick = (e) => {
      e.stopPropagation();
      const fileId = (wrap.querySelector("#matPrirazeniHdriId") || {}).value;
      const stavEl = wrap.querySelector("#matPrirazeniStav");
      if (!fileId) {
        if (stavEl) stavEl.textContent = "vyber nejdřív HDRi soubor";
        return;
      }
      spustitPrirazeniRender(fileId, stavEl, btnPrirazeniSpustit);
    };
  }
}
