// ==================== HDRI environmentalni mapy ====================
// Robert 2026-08-06: "dej mi do konfiguratoru moznost nahravat, menit HDRI
// environmentalni mapu". Soubory .hdr/.exr na serveru (api/hdri.py,
// /katalog/hdri/<soubor>), vyber pro vsechny prihlasene (localStorage),
// upload/mazani jen admin. PMREMGenerator dela z equirect mapy prefiltrovany
// environment pro odlesky MeshStandardMaterialu; nefiltrovana equirect
// textura jde zaroven do scene.background (r128 equirect pozadi podporuje).
let activeHdriTexture = null;
let activeHdriEnvMap = null;
const hdriPmremGen = new THREE.PMREMGenerator(renderer);

function deactivateHdri() {
  activeHdriFile = "";
  if (activeHdriEnvMap) { activeHdriEnvMap.dispose(); activeHdriEnvMap = null; }
  if (activeHdriTexture) { activeHdriTexture.dispose(); activeHdriTexture = null; }
  scene.environment = null;
  applyEnvironmentHue(envHue); // vrati barevny gradient pozadi
  const sel = document.getElementById("hdriSelect");
  if (sel) sel.value = "";
  try { localStorage.setItem("konfHdriFile", ""); } catch (e) { /* ignoruj */ }
  try { if (typeof hdriRingSetVisible === "function") hdriRingSetVisible(false); } catch (e) { /* ignoruj */ }
}

function applyHdri(fname) {
  if (!fname) { deactivateHdri(); return; }
  const statusEl = document.getElementById("hdriStatus");
  const ext = fname.toLowerCase().split(".").pop();
  const LoaderCls = ext === "exr" ? THREE.EXRLoader : THREE.RGBELoader;
  if (statusEl) statusEl.textContent = "Načítám " + fname + "…";
  new LoaderCls().load(
    "katalog/hdri/" + encodeURIComponent(fname),
    (tex) => {
      // uklid predchozi mapy az PO uspesnem nacteni nove (kdyby load
      // selhal, zustane funkcni stara)
      if (activeHdriEnvMap) activeHdriEnvMap.dispose();
      if (activeHdriTexture) activeHdriTexture.dispose();
      tex.mapping = THREE.EquirectangularReflectionMapping;
      // otaceni mapy (prstenec) - posun equirect textury podel X
      tex.wrapS = THREE.RepeatWrapping;
      activeHdriTexture = tex;
      activeHdriEnvMap = hdriPmremGen.fromEquirectangular(tex).texture;
      activeHdriFile = fname;
      // Robert 2026-08-06 (podruhe, po revertu): mapa JEN pro odlesky
      // (scene.environment), NE jako viditelne pozadi sceny - pozadi
      // zustava barevny gradient (applyEnvironmentHue).
      scene.environment = activeHdriEnvMap;
      if (statusEl) statusEl.textContent = "";
      try { localStorage.setItem("konfHdriFile", fname); } catch (e) { /* ignoruj */ }
      try {
        if (typeof hdriRingSetVisible === "function") {
          hdriRingSetVisible(true);
          if (typeof applyHdriRotation === "function") applyHdriRotation(hdriRotation, true);
        }
      } catch (e) { /* prstenec neni kriticky */ }
    },
    undefined,
    () => {
      if (statusEl) statusEl.textContent = "Nepodařilo se načíst " + fname + ".";
    }
  );
}

// ---- Otoceni HDRI mapy malym ovladacem v panelu (Robert 2026-08-06:
// "prstenec jsem myslel maly nekde v rohu" - puvodni velky 3D prstenec ve
// scene nahrazen malym kruhovym ovladacem #hdriRotDial v HDRI bloku) ----
// DULEZITA OPRAVA ("nevidim ze se odlesky menili kdyz tim otacim"):
// PMREMGenerator.fromEquirectangular v r128 IGNORUJE texture.offset (sampluje
// primo smerovym vektorem ve vlastnim shaderu), takze puvodni posun textury
// nedelal NIC. Spravna cesta v r128: pomocna mini-scena s velkououli
// otexturovanou equirect mapou (klasicky skysphere trik, scale(-1,1,1) pro
// spravnou orientaci) + PMREMGenerator.fromScene() - rotace koule = skutecne
// otoceni celeho environmentu. Regenerace se behem tazeni throttluje.
// CELY blok failure-safe (try/catch, degradace bez ovladace).
let hdriRotation = 0;
try {
  const savedRot = parseFloat(localStorage.getItem("konfHdriRot"));
  if (isFinite(savedRot)) hdriRotation = savedRot;
} catch (e) { /* ignoruj */ }

let hdriRegenTimer = null, hdriRegenPending = false;
let hdriEnvScene = null, hdriEnvSphere = null;

function hdriEnvSceneEnsure() {
  if (hdriEnvScene) return hdriEnvScene;
  hdriEnvScene = new THREE.Scene();
  const geom = new THREE.SphereGeometry(100, 64, 32);
  geom.scale(-1, 1, 1); // koule "naruby" - textura na vnitrni strane, spravna orientace
  hdriEnvSphere = new THREE.Mesh(geom, new THREE.MeshBasicMaterial());
  hdriEnvScene.add(hdriEnvSphere);
  return hdriEnvScene;
}

function hdriRegenEnvironment() {
  if (!activeHdriTexture || !activeHdriFile) return;
  hdriEnvSceneEnsure();
  hdriEnvSphere.material.map = activeHdriTexture;
  hdriEnvSphere.material.needsUpdate = true;
  hdriEnvSphere.rotation.y = hdriRotation;
  const old = activeHdriEnvMap;
  activeHdriEnvMap = hdriPmremGen.fromScene(hdriEnvScene, 0, 1, 1000).texture;
  scene.environment = activeHdriEnvMap;
  if (old) old.dispose();
}

function hdriRingSetVisible(v) {
  // nazev zachovan (vola ho applyHdri/deactivateHdri) - ted ukazuje/schovava
  // uz JEN kruhovy ovladac otoceni HDRI. Posuvniky povrchu vedle nej
  // (#hdriSurfaceWrap) zustavaji viditelne vzdy - Robert 2026-08-11
  // ("zmizely posuvniky pbr"): mizely spolu s ovladacem, i kdyz
  // kovovost/hrubost/barva plati i bez HDRI mapy.
  const wrap = document.getElementById("hdriRotWrap");
  if (wrap) wrap.style.display = v ? "flex" : "none";
}

function hdriDialSyncUi() {
  const dot = document.getElementById("hdriRotDot");
  const deg = document.getElementById("hdriRotDeg");
  if (dot) {
    const r = 15; // polomer drahy tecky uvnitr 44px kruhu
    dot.style.transform = `translate(${Math.cos(hdriRotation) * r}px, ${Math.sin(hdriRotation) * r}px)`;
  }
  if (deg) deg.textContent = Math.round(((hdriRotation * 180 / Math.PI) % 360 + 360) % 360) + "°";
}

function applyHdriRotation(angle, immediate) {
  hdriRotation = angle;
  hdriDialSyncUi();
  try { localStorage.setItem("konfHdriRot", String(hdriRotation)); } catch (e) { /* ignoruj */ }
  if (!activeHdriTexture) return;
  if (immediate) {
    hdriRegenEnvironment();
    return;
  }
  // throttle - PMREM regenerace je drahsi operace, behem tazeni max ~6x/s
  if (hdriRegenTimer) { hdriRegenPending = true; return; }
  hdriRegenEnvironment();
  hdriRegenTimer = setTimeout(() => {
    hdriRegenTimer = null;
    if (hdriRegenPending) { hdriRegenPending = false; applyHdriRotation(hdriRotation); }
  }, 150);
}

// Male posuvniky vlastnosti povrchu (Robert 2026-08-06). Zive MUTUJI
// existujici materialy (metalness/roughness/color jsou uniformy, zadna
// rekompilace/prestavba materialu - zamerne NE refreshAllMaterials, ktere
// prestavuje i hranovou geometrii; touhle cestou je zmena okamzita a bez
// rizika). Nove polozene dily dostanou hodnoty pres materialForLayer nize.
// envMapIntensity zustava napevno 1 (puvodni posuvnik "Sila" Robert zrusil -
// "neni zajimavy, je to moc svetle").
const hdriReflIntensity = 1;
let hdriReflRoughness = null, hdriReflMetalness = null, hdriReflBaseColor = null;
// MIKRO-TRPYT HLINIKU ZRUSEN (Robert 2026-09-11: "trpyt (sparkle) uplne
// zrusit"). Byla to procedura primo v shaderu vrstvy "alu", ktera jemne
// rozkmitavala hrubost povrchu podle lokalni pozice - do produktoveho
// renderu se stejne nepropisovala, protoze Blender ten shader nezna.
// Pozor: `paint-sparkle` / spawnPaintSparkles ve scene.html je NECO JINEHO
// (dekorativni trpytky u tlacitka barvy) a zustava.
try {
  const ro = parseFloat(localStorage.getItem("konfHdriRough"));
  if (isFinite(ro)) hdriReflRoughness = Math.max(0, Math.min(1, ro));
  const me = parseFloat(localStorage.getItem("konfHdriMetal"));
  if (isFinite(me)) hdriReflMetalness = Math.max(0, Math.min(1, me));
  const bc = localStorage.getItem("konfHdriBaseColor");
  if (bc && /^#[0-9a-fA-F]{6}$/.test(bc)) hdriReflBaseColor = bc;
} catch (e) { /* ignoruj */ }

// VYCHOZI HLINIK ULOZENY PRO VSECHNY (api/scene_materials.py, klic "alu").
// Nacita se POD localStorage: kdo si zrovna nasel svoje nastaveni, nechce,
// aby mu ho prepsalo vychozi. Kdo si nic neladil, dostane to, co je
// ulozene - a shoduje se tak se scenou u ostatnich i s produktovym
// renderem. Bez tohohle by ulozeni platilo az po smazani localStorage.
fetch("/api/scene/material-defaults", { credentials: "same-origin" })
  .then(r => (r.ok ? r.json() : null))
  .then(d => {
    const alu = d && d.ok && d.materials && d.materials.alu;
    if (!alu) return;
    let zmena = false;
    const nemaVlastni = k => { try { return localStorage.getItem(k) == null; } catch (e) { return true; } };
    if (typeof alu.color === "string" && nemaVlastni("konfHdriBaseColor")) {
      hdriReflBaseColor = alu.color; zmena = true;
    }
    if (isFinite(alu.metal) && nemaVlastni("konfHdriMetal")) { hdriReflMetalness = alu.metal; zmena = true; }
    if (isFinite(alu.rough) && nemaVlastni("konfHdriRough")) { hdriReflRoughness = alu.rough; zmena = true; }
    if (!zmena) return;
    if (typeof partMaterialColor !== "undefined" && hdriReflBaseColor) partMaterialColor.alu = hdriReflBaseColor;
    if (typeof partMaterialMetalness !== "undefined" && hdriReflMetalness != null) partMaterialMetalness.alu = hdriReflMetalness;
    if (typeof partMaterialRoughness !== "undefined" && hdriReflRoughness != null) partMaterialRoughness.alu = hdriReflRoughness;
    if (typeof hdriApplySurfaceLive === "function") hdriApplySurfaceLive();
  })
  .catch(() => { /* bez prihlaseni/offline - plati localStorage a vychozi z kodu */ });

function hdriApplySurfaceLive() {
  try {
    placed.forEach(en => {
      // PRAVIDLO Robert 2026-09-10: "tak kovovost co je ve scene, se nemuze
      // aplikovat na vsechno, jen na profily." Posuvniky HDRI ovladace ladi
      // vzhled HLINIKU v odrazech mapy - na euroboxech, uhelnicich,
      // zaslepkach a MDF deskach nemaji co delat. Stejna podminka jako v
      // materialForLayer (layer "alu" = katalogovy profil; produktove dily
      // maji layer vzdy "produkt").
      const jeProfil = !!(en.part && en.part.layer === "alu");
      en.object3d.traverse(n => {
        if (n.isMesh && n.material && n.material.isMeshStandardMaterial) {
          if (!jeProfil) return;
          n.material.envMapIntensity = hdriReflIntensity;
          if (hdriReflRoughness != null) n.material.roughness = hdriReflRoughness;
          if (hdriReflMetalness != null) n.material.metalness = hdriReflMetalness;
          // Robert 2026-08-06 ("klik barví ale ne renderovanou verzi s hdri
          // mapu") - rucne obarveny dil (en.customColor, z "Obarvit
          // díl"/"Obarvit stejné") se ziva zmena globalni HDRI barvy uz
          // NESMI dotknout, jinak tazeni posuvniku "Barva" tise prepise
          // uzivatelovo malovani zpet na spolecnou barvu. Stejne tak i
          // castecne obarvena konkretni cast vicedilneho dilu (2026-08-09,
          // viz meshColors/paintEntry).
          const meshColors = en.object3d.userData && en.object3d.userData.meshColors;
          if (hdriReflBaseColor != null && !en.customColor && !(meshColors && meshColors[n.name])) n.material.color.set(hdriReflBaseColor);
        }
      });
    });
  } catch (e) { /* neni kriticke */ }
}

(function initHdriFxSliders() {
  try {
    const metalS = document.getElementById("hdriMetalSlider");
    const roughS = document.getElementById("hdriRoughSlider");
    const colorP = document.getElementById("hdriBaseColorPicker");
    const colorReset = document.getElementById("hdriBaseColorReset");
    if (!metalS || !roughS) return;
    const sync = () => {
      metalS.value = hdriReflMetalness != null ? hdriReflMetalness : 0.5;
      roughS.value = hdriReflRoughness != null ? hdriReflRoughness : 0.4;
      if (colorP) colorP.value = hdriReflBaseColor || "#c9cdd1";
      const mv = document.getElementById("hdriMetalVal");
      const rv = document.getElementById("hdriRoughVal");
      if (mv) mv.textContent = Number(metalS.value).toFixed(2);
      if (rv) rv.textContent = Number(roughS.value).toFixed(2);
    };
    metalS.addEventListener("input", () => {
      hdriReflMetalness = parseFloat(metalS.value);
      try { localStorage.setItem("konfHdriMetal", String(hdriReflMetalness)); } catch (e) { /* ignoruj */ }
      sync(); hdriApplySurfaceLive();
    });
    roughS.addEventListener("input", () => {
      hdriReflRoughness = parseFloat(roughS.value);
      try { localStorage.setItem("konfHdriRough", String(hdriReflRoughness)); } catch (e) { /* ignoruj */ }
      sync(); hdriApplySurfaceLive();
    });
    if (colorP) colorP.addEventListener("input", () => {
      hdriReflBaseColor = colorP.value;
      try { localStorage.setItem("konfHdriBaseColor", hdriReflBaseColor); } catch (e) { /* ignoruj */ }
      hdriApplySurfaceLive();
    });
    if (colorReset) colorReset.addEventListener("click", () => {
      hdriReflBaseColor = null;
      try { localStorage.removeItem("konfHdriBaseColor"); } catch (e) { /* ignoruj */ }
      sync(); refreshAllMaterials();
    });

    // ULOZENI HLINIKU JAKO VYCHOZIHO (Robert 2026-09-10: "cim se uklada
    // nastaveni pro profily? postav to poradne").
    //
    // Posuvniky vyse ladi VYHRADNE hlinik/profily a drzely se jen v
    // localStorage - do jine sestavy ani do produktoveho renderu se nikdy
    // nedostaly. Uloziste je proto spolecne s ostatnimi materialy
    // (api/scene_materials.py, klic "alu"), jen ovladani zustava tady, aby
    // se neduplikovalo s panelem Materialy.
    //
    // Do palety partMaterial* se zapisuje taky: renderovaci vetev cte
    // hodnoty odtud a bez toho by hlinik ve scene a v renderu zustal
    // rozejity (zmereno 2026-09-10: scena kov 0,50/drsnost 0,40, render
    // 0,60/0,35).
    const aluSave = document.getElementById("hdriAluSaveDefault");
    if (aluSave) aluSave.addEventListener("click", () => {
      const puvodni = aluSave.textContent;
      aluSave.disabled = true;
      aluSave.textContent = "Ukládám…";
      const barva = (hdriReflBaseColor || (colorP && colorP.value) || "#c9cdd1").toLowerCase();
      const telo = {
        materials: {
          alu: {
            color: barva,
            metal: hdriReflMetalness != null ? hdriReflMetalness : parseFloat(metalS.value),
            rough: hdriReflRoughness != null ? hdriReflRoughness : parseFloat(roughS.value),
            // Odstin, pod kterym se profily k hliniku dosud hlasily -
            // podle nej server najde radky v katalogu k prebarveni.
            prev: (typeof partMaterialColor !== "undefined" && partMaterialColor.alu)
              ? String(partMaterialColor.alu).toLowerCase() : null,
          },
        },
      };
      fetch("/api/scene/material-defaults", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(telo),
      })
        .then(r => r.json().then(d => ({ ok: r.ok, d })))
        .then(({ ok, d }) => {
          if (!ok || !d.ok) throw new Error((d && d.error) || "nezdarilo se");
          // Paleta ve scene musi jit s tim - jinak by se hlinik v panelu
          // Materialy a v renderu rozesel s tim, co je tady na posuvnicich.
          if (typeof partMaterialColor !== "undefined") partMaterialColor.alu = barva;
          if (typeof partMaterialMetalness !== "undefined") partMaterialMetalness.alu = telo.materials.alu.metal;
          if (typeof partMaterialRoughness !== "undefined") partMaterialRoughness.alu = telo.materials.alu.rough;
          const p = d.prebarveno || {};
          const kusu = (p.shop_products || 0) + (p.cfg_dily || 0);
          aluSave.textContent = kusu ? "✓ Uloženo, přebarveno " + kusu + " dílů" : "✓ Uloženo jako výchozí";
          setTimeout(() => { aluSave.textContent = puvodni; aluSave.disabled = false; }, 2600);
        })
        .catch(e => {
          console.error("hdriAluSaveDefault", e);
          aluSave.textContent = "✗ Nepodařilo se uložit";
          setTimeout(() => { aluSave.textContent = puvodni; aluSave.disabled = false; }, 2600);
        });
    });
    sync();
  } catch (e) { /* posuvniky nejsou kriticke */ }
})();

(function initHdriDialDrag() {
  try {
    const dial = document.getElementById("hdriRotDial");
    if (!dial) return;
    let dragging = false;
    const angleFromEvent = (ev) => {
      const r = dial.getBoundingClientRect();
      return Math.atan2(ev.clientY - (r.top + r.height / 2), ev.clientX - (r.left + r.width / 2));
    };
    dial.addEventListener("pointerdown", (ev) => {
      try {
        ev.preventDefault();
        dragging = true;
        dial.setPointerCapture(ev.pointerId);
        applyHdriRotation(angleFromEvent(ev));
      } catch (e) { /* ovladac neni kriticky */ }
    });
    dial.addEventListener("pointermove", (ev) => {
      if (!dragging) return;
      try { applyHdriRotation(angleFromEvent(ev)); } catch (e) { /* ignoruj */ }
    });
    const end = (ev) => {
      if (!dragging) return;
      dragging = false;
      try { applyHdriRotation(hdriRotation, true); } catch (e) { /* ignoruj */ }
    };
    dial.addEventListener("pointerup", end);
    dial.addEventListener("pointercancel", end);
    hdriDialSyncUi();
  } catch (e) { /* ovladac neni kriticky - scena jede dal */ }
})();

function loadHdriList() {
  const sel = document.getElementById("hdriSelect");
  if (!sel) return Promise.resolve();
  return fetch("/api/hdri")
    .then(r => r.ok ? r.json() : { files: [] })
    .then(data => {
      const files = data.files || [];
      const current = sel.value;
      sel.innerHTML = '<option value="">— barva (bez HDRI) —</option>' +
        files.map(f => `<option value="${f.file.replace(/"/g, "&quot;")}">${f.name.replace(/</g, "&lt;")}</option>`).join("");
      // zachovat vyber, pokud soubor porad existuje
      if (current && files.some(f => f.file === current)) sel.value = current;
    })
    .catch(() => { /* seznam neni kriticky */ });
}

(function initHdriUi() {
  const sel = document.getElementById("hdriSelect");
  if (!sel) return;
  sel.addEventListener("change", () => applyHdri(sel.value));
  const upBtn = document.getElementById("hdriUploadBtn");
  const upFile = document.getElementById("hdriUploadFile");
  const delBtn = document.getElementById("hdriDeleteBtn");
  const statusEl = document.getElementById("hdriStatus");
  if (upBtn && upFile) {
    upBtn.addEventListener("click", async () => {
      const f = (upFile.files || [])[0];
      if (!f) { if (statusEl) statusEl.textContent = "Vyber nejdřív .hdr/.exr soubor."; return; }
      upBtn.disabled = true;
      if (statusEl) statusEl.textContent = "Nahrávám " + f.name + "…";
      try {
        const fd = new FormData();
        fd.append("file", f);
        const r = await fetch("/api/admin/hdri", { method: "POST", body: fd });
        const data = await r.json();
        if (!r.ok) throw new Error(data.error || ("HTTP " + r.status));
        await loadHdriList();
        sel.value = data.file;
        applyHdri(data.file);
        upFile.value = "";
      } catch (e) {
        if (statusEl) statusEl.textContent = "Chyba: " + e.message;
      } finally {
        upBtn.disabled = false;
      }
    });
  }
  if (delBtn) {
    delBtn.addEventListener("click", async () => {
      const fname = sel.value;
      if (!fname) { if (statusEl) statusEl.textContent = "Vyber nejdřív mapu ke smazání."; return; }
      if (!confirm("Smazat HDRI mapu \"" + fname + "\" ze serveru?")) return;
      try {
        const r = await fetch("/api/admin/hdri/" + encodeURIComponent(fname), { method: "DELETE" });
        const data = await r.json();
        if (!r.ok) throw new Error(data.error || ("HTTP " + r.status));
        deactivateHdri();
        await loadHdriList();
      } catch (e) {
        if (statusEl) statusEl.textContent = "Chyba: " + e.message;
      }
    });
  }
  // obnoveni ulozene volby po nacteni seznamu
  loadHdriList().then(() => {
    let saved = "";
    try { saved = localStorage.getItem("konfHdriFile") || ""; } catch (e) { /* ignoruj */ }
    if (saved && [...sel.options].some(o => o.value === saved)) {
      sel.value = saved;
      applyHdri(saved);
    }
  });
})();

function updateViewportSize() {
  const aspect = viewport.clientWidth/viewport.clientHeight;
  if (camera.isOrthographicCamera) {
    camera.left = -ORTHO_VIEW_HALF_HEIGHT * aspect;
    camera.right = ORTHO_VIEW_HALF_HEIGHT * aspect;
    camera.top = ORTHO_VIEW_HALF_HEIGHT;
    camera.bottom = -ORTHO_VIEW_HALF_HEIGHT;
  } else {
    camera.aspect = aspect;
  }
  camera.updateProjectionMatrix();
  renderer.setSize(viewport.clientWidth, viewport.clientHeight);
}
window.addEventListener("resize", updateViewportSize);

// --- Manual panel width resizing (drag handles) ---
(function setupResizers() {
  const sidebarEl = document.getElementById("sidebar");
  const summaryEl = document.getElementById("summary");
  const resizerLeft = document.getElementById("resizerLeft");
  const resizerRight = document.getElementById("resizerRight");
  const MIN_W = 120, MAX_W = 600;

  function applyWidth(el, key, w) {
    w = Math.max(MIN_W, Math.min(MAX_W, w));
    el.style.width = w + "px";
    try { localStorage.setItem(key, String(w)); } catch (e) {}
  }

  try {
    const savedSidebar = parseInt(localStorage.getItem("panelWidth_sidebar"), 10);
    if (savedSidebar) sidebarEl.style.width = Math.max(MIN_W, Math.min(MAX_W, savedSidebar)) + "px";
    const savedSummary = parseInt(localStorage.getItem("panelWidth_summary"), 10);
    if (savedSummary) summaryEl.style.width = Math.max(MIN_W, Math.min(MAX_W, savedSummary)) + "px";
  } catch (e) {}

  function startDrag(resizerEl, panelEl, key, sign) {
    resizerEl.addEventListener("mousedown", (ev) => {
      ev.preventDefault();
      resizerEl.classList.add("active");
      const startX = ev.clientX;
      const startW = panelEl.getBoundingClientRect().width;
      document.body.style.userSelect = "none";
      function onMove(mv) {
        const dx = (mv.clientX - startX) * sign;
        applyWidth(panelEl, key, startW + dx);
        updateViewportSize();
        // Robert 2026-08-06: "namagnetované panely tlačítka a okna se
        // musí posunout s tím zároveň" - ZIVE (kazdy pohyb mysi behem
        // tazeni resizeru), ne az po pusteni - viz reclampAllFloating
        // nize v souboru (magnet/backstop pro plovouci panely i taby).
        if (typeof reclampAllFloating === "function") reclampAllFloating();
      }
      function onUp() {
        resizerEl.classList.remove("active");
        document.body.style.userSelect = "";
        document.removeEventListener("mousemove", onMove);
        document.removeEventListener("mouseup", onUp);
        updateViewportSize();
        if (typeof reclampAllFloating === "function") reclampAllFloating();
      }
      document.addEventListener("mousemove", onMove);
      document.addEventListener("mouseup", onUp);
    });
  }

  startDrag(resizerLeft, sidebarEl, "panelWidth_sidebar", 1);
  startDrag(resizerRight, summaryEl, "panelWidth_summary", -1);

  setTimeout(updateViewportSize, 0);
})();

// --- Zasouvaci/vysouvaci chovani hlavniho leveho (#sidebar) a praveho
// (#summary) panelu - Robert 2026-07-25: "udelej zajizdeji pravy i levy
// panel". Stejny princip jako uz existujici plovouci panely (Tvary,
// Mikroposuv, Posun/Rotace), jen aplikovany na hlavni sloupce layoutu -
// zasunuti zde znamena zuzeni na sirku 0 (#sidebar/#summary jsou soucast
// flex radku #app, ne plovouci overlay, viz .collapsed v CSS). Prislusny
// resizer (#resizerLeft/#resizerRight) se pri zasunuti take schova, protoze
// by jinak zustal viset na okraji obrazovky bez viditelneho efektu.
// Robert 2026-07-25: "tlacitka zasunutych panelu udelej plovouci ať si
// kazdy posune kam chce vyskove, kazdemu uzivateli by se to melo ulozit do
// prohlizece" - tab (Katalog/Prehled) jde tahnout mysi nahoru/dolu po
// pravem/levem okraji obrazovky, pozice (top v px) se uklada do
// localStorage (tedy per prohlizec/uzivatel, ne sdilene na serveru).
// Robert 2026-07-25 (doplneno): "vsechny postranni tlacitka zasuvnych
// panelu nechť jsou plovouci, vyskove" - puvodne jen sidebar/summary tab,
// ted VSECH 5 (Katalog, Prehled, Tvary, Mikroposuv, Posun/Rotace mysi).
// #sidebarTab/#summaryTab jsou position:fixed (souradnice "top" uz jsou
// relativni k oknu), ale #wizardTab/#axisMoveTab/#moveTab jsou
// position:absolute UVNITR #viewport (souradnice "top" relativni k jeho
// rohu, ktery zacina az pod horni listou) - proto se pozice prepocitava
// pres offsetParent, aby fungovalo tazeni stejne spolehlive pro oba typy.
// Nektere z puvodnich tabu pouzivaly CSS "bottom" misto "top" - jakmile se
// jednou pretahnou (nebo obnovi ulozena pozice), prepnou se natrvalo na
// "top" pozicovani (bottom:auto).
// Robert 2026-08-06 ("ty ikony jsou stale zafixovane, to nechceme" +
// "chceceme je plně plovoucí a jen magnet k bočním panelům, to už asi
// je"): puvodne slo tahnout jen svisle (podel pevneho leveho/praveho
// okraje) - ted plne 2D jako rozbalene panely (viz makePanelDraggable),
// a pri pusteni mysi se aplikuje UPLNE STEJNY magnet k #sidebar/#summary
// (dosah 200px) + tvrdy backstop proti oriznuti #viewport
// (applyPanelSideMagnet/clampRectToViewport, definovane nize v souboru -
// funkcni deklarace jsou hoistovane, funguje i kdyz se tahnuti spusti az
// po plnem nacteni skriptu). Nazev funkce zustal (pouziva ji 9 mist v
// kodu), i kdyz uz neni jen "vertically" - X souradnice se uklada pod
// stejnym klicem s "Top"->"Left" na konci, zadne volajici misto se
// nemusi menit.
function makeTabVerticallyDraggable(tabEl, storageKeyTop, opts) {
  if (!tabEl) return;
  // Robert 2026-08-06 ("vyřaď [minTop=50 strop] pro tlačítko Vlastní tvary"):
  // volitelny per-tab override - ctou ho clampRectToViewport/applyPanelSideMagnet/
  // resolvePanelOverlaps pres tabEl._minTop. Bez opts.minTop se chovani NEMENI
  // (zustava sdilenych 50px pro vsechny ostatni taby).
  if (opts && opts.minTop != null) tabEl._minTop = opts.minTop;
  // Robert 2026-08-06 (nasledne upresneni: "to nebylo to co vraci tlacitko
  // k hornimu okraji" - realny viník byl magnet+kolizni vyhybani po pusteni
  // mysi, ne staticky minTop strop) - opts.skipDropRepositioning zcela
  // vypne applyPanelSideMagnet/resolvePanelOverlaps v onUp nize (jen bounds
  // clamp zustava, tab zustane presne tam, kam ho uzivatel pustil). Zase jen
  // pro tenhle jeden tab (fwShapesTab) - vsechny ostatni taby maji magnet+
  // kolizi po pusteni beze zmeny.
  if (opts && opts.skipDropRepositioning) tabEl._skipDropRepositioning = true;
  const storageKeyLeft = storageKeyTop.replace(/Top$/, "Left");
  try {
    const savedTop = parseFloat(localStorage.getItem(storageKeyTop));
    const savedLeft = parseFloat(localStorage.getItem(storageKeyLeft));
    if (!isNaN(savedTop) && !isNaN(savedLeft)) {
      tabEl.style.top = savedTop + "px";
      tabEl.style.left = savedLeft + "px";
      tabEl.style.right = "auto";
      tabEl.style.bottom = "auto";
    }
  } catch (e) { /* ignoruj */ }
  if (typeof DRAGGABLE_TABS !== "undefined") DRAGGABLE_TABS.push(tabEl);
  // Robert 2026-08-06 ("opakuji, nesmí docházet k překrytí prvků
  // ovládání") - i vychozi/ulozena pozice (bez jakehokoli tazeni) musi
  // byt hned opravena, ne az po prvnim pretazeni. V tuhle chvili jeste
  // neni jiste, jestli je tab viditelny (.visible se nastavuje az
  // nasledujicim setCollapsed() volanim ve volajicim kodu) -
  // setTimeout(...,0) pockej na konec aktualniho synchronniho behu
  // skriptu, kdy uz je stav definitivne znamy.
  setTimeout(() => { if (typeof finalizeTabPosition === "function") finalizeTabPosition(tabEl); }, 0);

  tabEl.addEventListener("mousedown", (ev) => {
    if (ev.button !== 0) return;
    if (typeof floatingIconsLocked !== "undefined" && floatingIconsLocked) return;   // zamek pozic (viz setFloatingLocked)
    ev.preventDefault();
    const startX = ev.clientX, startY = ev.clientY;
    const rect = tabEl.getBoundingClientRect(); // vzdy relativne k oknu
    const parentEl = tabEl.offsetParent || document.body;
    const parentRect = parentEl.getBoundingClientRect();
    let moved = false;
    tabEl.classList.add("dragging");
    document.body.style.userSelect = "none";
    function onMove(mv) {
      const dx = mv.clientX - startX, dy = mv.clientY - startY;
      if (Math.abs(dx) > 3 || Math.abs(dy) > 3) moved = true;
      // Behem tazeni zadna fixace na sidebar/summary - jen holá hranice
      // okna (stejny princip jako u plnych panelu, viz makePanelDraggable).
      // Normalizovane [lo,hi] - viz clampRectToViewport.
      const minTopWindow = tabEl._minTop != null ? tabEl._minTop : 50, maxTopWindow = window.innerHeight - tabEl.offsetHeight - 6;
      const minLeftWindow = 0, maxLeftWindow = window.innerWidth - tabEl.offsetWidth - 6;
      const topLo = Math.min(minTopWindow, maxTopWindow), topHi = Math.max(minTopWindow, maxTopWindow);
      const leftLo = Math.min(minLeftWindow, maxLeftWindow), leftHi = Math.max(minLeftWindow, maxLeftWindow);
      const newTopWindow = Math.max(topLo, Math.min(topHi, rect.top + dy));
      const newLeftWindow = Math.max(leftLo, Math.min(leftHi, rect.left + dx));
      tabEl.style.top = (newTopWindow - parentRect.top) + "px";
      tabEl.style.left = (newLeftWindow - parentRect.left) + "px";
      tabEl.style.right = "auto";
      tabEl.style.bottom = "auto";
    }
    function onUp() {
      tabEl.classList.remove("dragging");
      document.body.style.userSelect = "";
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
      if (moved) {
        tabEl._justDragged = true; // potlaci nasledujici "click" (viz tab.onclick nize)
        // Az ted (pusteni mysi): magnet k bocnim panelum + tvrdy backstop +
        // vyhnuti se #toolbar/jinym panelum/tabum - stejne funkce jako
        // pouziva makePanelDraggable pro plne panely.
        const dropRect = tabEl.getBoundingClientRect();
        const width = tabEl.offsetWidth, height = tabEl.offsetHeight;
        let pos = { top: dropRect.top, left: dropRect.left };
        if (!tabEl._skipDropRepositioning) {
          pos = applyPanelSideMagnet(pos.top, pos.left, width, height, tabEl._minTop != null ? tabEl._minTop : null);
          tabEl._attachedWall = pos.wall; // viz followAttachedWall - null = uz se ke stene nedrzi
          pos = resolvePanelOverlaps(tabEl, pos.top, pos.left, width, height);
        }
        pos = clampRectToViewport(pos.top, pos.left, width, height, tabEl._minTop != null ? tabEl._minTop : null);
        const pr = (tabEl.offsetParent || document.body).getBoundingClientRect();
        tabEl.style.top = (pos.top - pr.top) + "px";
        tabEl.style.left = (pos.left - pr.left) + "px";
        try {
          localStorage.setItem(storageKeyTop, String(Math.round(parseFloat(tabEl.style.top))));
          localStorage.setItem(storageKeyLeft, String(Math.round(parseFloat(tabEl.style.left))));
        } catch (e) { /* ignoruj */ }
      }
    }
    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
  });
}

// Robert 2026-07-25: "zatahovaci panely, kdyz se rozbali maji pevne dane
// pozice, chceme aby i rozbalene panely byly plovouci" - tazeni CELEHO
// rozbaleneho panelu za jeho hlavicku (stejny princip jako
// makeTabVerticallyDraggable vyse, ale ve 2 osach - X i Y - protoze panely
// na rozdil od tabu nejsou pripoutane k okraji obrazovky). Klik primo na
// tlacitko uvnitr hlavicky (X - zasunout) tazeni nezahaji.
// Robert 2026-08-06 (2. kolo - "nefunguje to" + nove presnejsi zadani):
// "podmínka: nikdy nesmí zůstat jeden panel přes druhý jakmile se pustí
// myš, to zafixování které tam máme pro plovoucí panely k levému nebo
// pravému koncovému panelu, zrušme a udelejme to jako magnet k těm
// bočním panelům (magnet s dosahem 200px)". Puvodni "tvrde" ohraniceni
// BEHEM tazeni (nemozne prekrocit hranici #sidebar/#summary) je pryc -
// behem tazeni se panel hlida jen proti oknu (jako drive vzdy), zadna
// "fixace" na bocni panely. AZ PRI PUSTENI MYSI (onUp): 1) magnet - je-li
// okraj panelu do 200px od hrany #sidebar/#summary, "prisaje" se presne
// na ni; 2) tvrdy backstop proti #viewport (ten ma overflow:hidden -
// cokoli za jeho hranici by se oriznulo/zmizelo, proto tenhle limit
// zustava, i kdyz uz neni citit BEHEM tazeni); 3) kolize s OSTATNIMI
// viditelnymi plovoucimi panely - odsune se pod ne (pripadne doprava,
// kdyz uz dole neni misto), az zadny prekryv nezbyde.
function getRightPanelDragBoundary() {
  const summary = document.getElementById("summary");
  if (summary && !summary.classList.contains("collapsed")) {
    const r = summary.getBoundingClientRect();
    if (r.width > 0) return r.left;
  }
  return window.innerWidth;
}
function getLeftPanelDragBoundary() {
  const sidebar = document.getElementById("sidebar");
  if (sidebar && !sidebar.classList.contains("collapsed")) {
    const r = sidebar.getBoundingClientRect();
    if (r.width > 0) return r.right;
  }
  return 0;
}

const DRAGGABLE_PANELS = [];
const PANEL_MAGNET_RANGE = 200;

// Robert 2026-08-08: "Magnet panelů k okraji" - ovladaci checkboxy
// (Horni/Dolni/Levy/Pravy) odstraneny (Robert: "stejne to nefunguje"),
// applyPanelSideMagnet nize zustava beze zmeny, jen s pevnymi vychozimi
// hodnotami misto uzivatelsky prepinatelnych.
let magnetWalls = { top: false, bottom: true, left: true, right: true };

function rectsOverlap(a, b) {
  return a.left < b.right && a.right > b.left && a.top < b.bottom && a.bottom > b.top;
}

// Tvrdy backstop - jen aby panel nezmizel mimo viditelnou plochu (viz
// komentar vyse), pouziva se JEN po pusteni mysi (a pri init/resize),
// nikdy prubezne behem tazeni.
function clampRectToViewport(top, left, width, height, minTopOverride) {
  // Robert 2026-08-06 ("vyřaď [minTop strop] pro tlačítko Vlastní tvary"):
  // volitelny per-element override pevneho minTop=50 - viz makeTabVerticallyDraggable
  // (ctenim elToPlace._minTop), pouzito JEN u fwShapesTab, vsechny ostatni
  // volajici mista override nepredavaji a chovaji se beze zmeny.
  const minTop = minTopOverride != null ? minTopOverride : 50, maxTop = window.innerHeight - height - 6;
  const minLeft = getLeftPanelDragBoundary();
  const maxLeft = Math.max(minLeft, getRightPanelDragBoundary() - width - 6);
  // Je-li panel vyssi/sirsi nez dostupny prostor (maxTop < minTop, napr.
  // "Menu nástrojů" pred pridanim max-height na panel - viz Robertovo
  // "i když posunu tlačitko... vrátí se nahoru"), puvodni
  // Math.max(minTop, Math.min(maxTop, top)) VZDY vratilo minTop bez
  // ohledu na to, kam byl panel presunuty (Math.min uz srazelo pod
  // minTop, pak ho Math.max natvrdo vratil zpet) - normalizovane
  // [lo,hi] tomu predejde, i kdyby k tomu znovu nekde doslo.
  const topLo = Math.min(minTop, maxTop), topHi = Math.max(minTop, maxTop);
  const leftLo = Math.min(minLeft, maxLeft), leftHi = Math.max(minLeft, maxLeft);
  return {
    top: Math.max(topLo, Math.min(topHi, top)),
    left: Math.max(leftLo, Math.min(leftHi, left)),
  };
}

// Robert 2026-08-06 ("magnetuje to, ale nahoru. tak udělejme pravidlo,
// magnetovat bude k té stěně ke které má nejblíže") - puvodne magnet
// znal jen 2 smery (leva/prava stena - #sidebar/#summary), zadny
// nahoru/dolu. Ted 4 "steny" (leva/prava/horni/dolni okraj viditelne
// plochy) - spocita vzdalenost ke kazde, a je-li nejblizsi v dosahu
// PANEL_MAGNET_RANGE, "prisaje" se JEN NA NI (jednu, ne kombinaci vic
// najednou).
function applyPanelSideMagnet(top, left, width, height, minTopOverride) {
  let rightWallX = window.innerWidth;
  const summary = document.getElementById("summary");
  if (summary && !summary.classList.contains("collapsed")) {
    const r = summary.getBoundingClientRect();
    if (r.width > 0) rightWallX = r.left;
  }
  let leftWallX = 0;
  const sidebar = document.getElementById("sidebar");
  if (sidebar && !sidebar.classList.contains("collapsed")) {
    const r = sidebar.getBoundingClientRect();
    if (r.width > 0) leftWallX = r.right;
  }
  const topWallY = minTopOverride != null ? minTopOverride : 50; // stejna hranice jako "minTop" v clampRectToViewport
  const bottomWallY = window.innerHeight - 6;

  const candidates = [
    { wall: "left", dist: Math.abs(left - leftWallX), apply: () => { left = leftWallX + 6; } },
    { wall: "right", dist: Math.abs(rightWallX - (left + width)), apply: () => { left = rightWallX - width - 6; } },
    { wall: "top", dist: Math.abs(top - topWallY), apply: () => { top = topWallY; } },
    { wall: "bottom", dist: Math.abs(bottomWallY - (top + height)), apply: () => { top = bottomWallY - height; } },
  ].filter(c => magnetWalls[c.wall]);
  // Robert 2026-08-06 ("Menu nástroje, nech kopíruje pohyb Pravého panelu",
  // upresneno: pohybuje se SPOLU s nim) - vraci i KTEROU stenu si panel/tab
  // vybral (nebo null, kdyz zadnou), aby volajici mohl zapamatovat "attached"
  // stav - viz followAttachedWall() nize, ktera pak pri zmene polohy dane
  // steny (zmenseni/zabaleni #summary/#sidebar) panel/tab prisune k jejimu
  // NOVEMU umisteni misto aby jen (jednosmerne) uhybal, kdyz do nej stena
  // narostla.
  let wall = null;
  if (candidates.length) {
    const nearest = candidates.reduce((a, b) => (a.dist < b.dist ? a : b));
    if (nearest.dist <= PANEL_MAGNET_RANGE) { nearest.apply(); wall = nearest.wall; }
  }
  return { top, left, wall };
}

// Robert 2026-08-06 ("opakuji, nesmí docházet k překrytí prvků ovládání,
// ošetři to") - i po predchozim z-index fixu (tab uz nebyl SCHOVANY pod
// #toolbar, ale porad se s nim vizualne PREKRYVAL/dotykal) je jasne, ze
// staci vyssi z-index nestaci - #toolbar musi byt PREKAZKA stejne jako
// ostatni plovouci panely/taby, at se jim aktivne vyhnou. Sbira aktualni
// obdelniky vsech "pevnych" prekazek (jine viditelne panely, taby,
// #toolbar) KROME elementu, ktery se prave umist'uje.
function getFixedObstacleRects(excludeEl) {
  const rects = [];
  const toolbar = document.getElementById("toolbar");
  if (toolbar && toolbar !== excludeEl) {
    const r = toolbar.getBoundingClientRect();
    if (r.width > 0 && r.height > 0) rects.push(r);
  }
  DRAGGABLE_PANELS.forEach(p => {
    if (p !== excludeEl && p.offsetParent !== null && !p.classList.contains("collapsed")) {
      rects.push(p.getBoundingClientRect());
    }
  });
  DRAGGABLE_TABS.forEach(t => {
    if (t !== excludeEl && t.classList.contains("visible")) rects.push(t.getBoundingClientRect());
  });
  return rects;
}

// Odsune panel/tab, aby se neprekryval se ZADNOU pevnou prekazkou
// (#toolbar, jine viditelne panely, jine taby) - zkusi primo pod
// prekryvajici se prekazku, kdyz uz dole neni misto v okne, o kus
// doprava. Nekolik kol (kaskadovite prekryvy), s pojistkou proti
// nekonecne smycce.
function resolvePanelOverlaps(elToPlace, top, left, width, height) {
  const minTopOverride = elToPlace && elToPlace._minTop != null ? elToPlace._minTop : null;
  const aboveTopLimit = minTopOverride != null ? minTopOverride : 50;
  const obstacles = getFixedObstacleRects(elToPlace);
  for (let i = 0; i < 12; i++) {
    const rect = { top, left, right: left + width, bottom: top + height };
    const hit = obstacles.find(o => rectsOverlap(rect, o));
    if (!hit) break;
    // Robert 2026-08-06 ("nefunguje to porad se tlačítka lepí nahoru") -
    // tenhle fallback drive VZDY resetoval top na pevnych 50px, kdyz se
    // panel nevesel pod prekazku - NEZAVISLE na magnetu/jeho checkboxech
    // (jina funkce), proto vypnuti "Horní okraj" v magnetu nemelo zadny
    // vliv. Ted zkousime postupne: pod prekazku, jinak NAD prekazku,
    // jinak doprava OD prekazky (a top zustane, jak byl - zadny pevny
    // "magic number" navrat nahoru).
    const belowTop = hit.bottom + 8;
    const aboveTop = hit.top - height - 8;
    if (belowTop + height <= window.innerHeight - 6) {
      top = belowTop;
    } else if (aboveTop >= aboveTopLimit) {
      top = aboveTop;
    } else {
      left = hit.right + 8; // top necham, jak byl
    }
    const c = clampRectToViewport(top, left, width, height, minTopOverride);
    top = c.top; left = c.left;
  }
  return { top, left };
}

function writePanelWindowPos(panelEl, topWindow, leftWindow) {
  const parentEl = panelEl.offsetParent || document.body;
  const parentRect = parentEl.getBoundingClientRect();
  panelEl.style.top = (topWindow - parentRect.top) + "px";
  panelEl.style.left = (leftWindow - parentRect.left) + "px";
  panelEl.style.right = "auto";
  panelEl.style.bottom = "auto";
}

// Robert 2026-08-06 ("vidis co je porad nahore? už o delas 3 hodiny a
// nic") - PO SERII regresi zpusobenych timhle, zásadní zjednodušení:
// magnet+kolizni vyhybani (applyPanelSideMagnet/resolvePanelOverlaps)
// uz NEBEZI automaticky (pri nacteni stranky, resize, rozbaleni bocnich
// panelu) - jen v okamziku, kdy uzivatel SKUTECNE rucne pusti tazeny
// panel/tab (viz makePanelDraggable/makeTabVerticallyDraggable onUp,
// kde je magnet+kolize inline). Automaticke "reklampovani" ted dela JEN
// jednu vec - nedovoli panelu/tabu zmizet mimo viditelnou plochu
// (clampRectToViewport), zadne posouvani vuci ostatnim panelum/#toolbar.
// Duvod: kdyz se magnet+kolize spustily automaticky pro VSECHNY panely
// najednou (pri nacteni stranky, kazdy proti uz vyresenym predchozim),
// kaskadovite se to slozilo do jedne rady u horniho okraje - presne to,
// co bylo na Robertove screenshotu. Rucni tazeni jednoho panelu takove
// riziko kaskady nema (resi se jen ON, ne vsech N najednou).
// Panel/tab s `_attachedWall` (nastavuje makePanelDraggable/
// makeTabVerticallyDraggable po uspesnem magnet-snapu v applyPanelSideMagnet)
// se ZIVE prisune k AKTUALNI pozici te steny - na rozdil od
// clampRectToViewport (ktery jen brani PREKROCENI hranice) tohle funguje
// OBEMA smery: kdyz #summary/#sidebar naroste DO panelu, klasicky ho odsune
// (uz delal clamp), ale kdyz se #summary/#sidebar naopak ZMENSI/zabali,
// tenhle kod panel/tab k nove (blizsi) pozici steny PRITAHNE zpet, misto
// aby zustal trcet tam, kde stena drive byla.
function followAttachedWall(el) {
  if (!el || !el._attachedWall) return;
  const width = el.offsetWidth, height = el.offsetHeight;
  const rect = el.getBoundingClientRect();
  let top = rect.top, left = rect.left;
  if (el._attachedWall === "left") {
    const sidebar = document.getElementById("sidebar");
    const r = sidebar && !sidebar.classList.contains("collapsed") ? sidebar.getBoundingClientRect() : null;
    left = (r && r.width > 0 ? r.right : 0) + 6;
  } else if (el._attachedWall === "right") {
    const summary = document.getElementById("summary");
    const r = summary && !summary.classList.contains("collapsed") ? summary.getBoundingClientRect() : null;
    const rightWallX = r && r.width > 0 ? r.left : window.innerWidth;
    left = rightWallX - width - 6;
  } else if (el._attachedWall === "top") {
    top = el._minTop != null ? el._minTop : 50;
  } else if (el._attachedWall === "bottom") {
    top = window.innerHeight - 6 - height;
  }
  writePanelWindowPos(el, top, left);
}

function finalizePanelPosition(panelEl) {
  if (!panelEl || panelEl.classList.contains("collapsed")) return;
  // Robert 2026-08-12 (nove tazitelne panely Kontrola ploch/Pozice
  // uhelniku/🎓 Naucit napojeni, ktere se schovavaji primo pres
  // style.display, ne jen tridou .collapsed): skryty panel (display:none
  // nebo skryty predek) ma offsetParent null a getBoundingClientRect()
  // by vratil same nuly - bez tehle pojistky by resize okna, kdyz je
  // panel zavreny, prepsal jeho ulozenou pozici na (0,0).
  if (panelEl.offsetParent === null) return;
  followAttachedWall(panelEl);
  const rect = panelEl.getBoundingClientRect();
  const width = panelEl.offsetWidth, height = panelEl.offsetHeight;
  const pos = clampRectToViewport(rect.top, rect.left, width, height);
  writePanelWindowPos(panelEl, pos.top, pos.left);
}

const DRAGGABLE_TABS = [];
function finalizeTabPosition(tabEl) {
  if (!tabEl || !tabEl.classList.contains("visible")) return; // skryty tab ma nulovy rect
  // Robert 2026-08-12 ("plovouci ikony se mi pokazde nejak rozhodi"):
  // pri zamceni se zalozky uz nesrovnavaji ani automaticky (magnet ke
  // stene panelu, kolizni vyhybani, doklapnuti pri zmene velikosti okna)
  // - prave tohle je posouvalo "samo od sebe". Zustava jen tvrde
  // orezani na okno nize, aby ikona nikdy neskoncila mimo obrazovku.
  if (typeof floatingIconsLocked === "undefined" || !floatingIconsLocked) followAttachedWall(tabEl);
  const rect = tabEl.getBoundingClientRect();
  const width = tabEl.offsetWidth, height = tabEl.offsetHeight;
  const pos = clampRectToViewport(rect.top, rect.left, width, height, tabEl._minTop != null ? tabEl._minTop : null);
  writePanelWindowPos(tabEl, pos.top, pos.left);
}

function reclampAllFloating() {
  DRAGGABLE_PANELS.forEach(finalizePanelPosition);
  DRAGGABLE_TABS.forEach(finalizeTabPosition);
}
window.addEventListener("resize", reclampAllFloating);

function makePanelDraggable(panelEl, handleEl, storageKeyPrefix) {
  if (!panelEl || !handleEl) return;
  try {
    const savedTop = parseFloat(localStorage.getItem(storageKeyPrefix + "Top"));
    const savedLeft = parseFloat(localStorage.getItem(storageKeyPrefix + "Left"));
    if (!isNaN(savedTop) && !isNaN(savedLeft)) {
      panelEl.style.top = savedTop + "px";
      panelEl.style.left = savedLeft + "px";
      panelEl.style.right = "auto";
      panelEl.style.bottom = "auto";
    }
  } catch (e) { /* ignoruj */ }
  DRAGGABLE_PANELS.push(panelEl);
  finalizePanelPosition(panelEl);

  handleEl.addEventListener("mousedown", (ev) => {
    if (ev.button !== 0) return;
    if (ev.target.closest("button")) return; // klik na X (zasunout) neni tazeni
    ev.preventDefault();
    const startX = ev.clientX, startY = ev.clientY;
    const rect = panelEl.getBoundingClientRect();
    let moved = false;
    handleEl.classList.add("panel-dragging");
    document.body.style.userSelect = "none";
    function onMove(mv) {
      const dx = mv.clientX - startX, dy = mv.clientY - startY;
      if (Math.abs(dx) > 3 || Math.abs(dy) > 3) moved = true;
      // Behem tazeni ZADNA fixace na sidebar/summary (Robert: "zrušme to
      // zafixování") - jen holá hranice okna, at panel nezmizi uplne.
      // Normalizovane [lo,hi] (viz clampRectToViewport) - kdyby byl panel
      // vyssi/sirsi nez okno, Math.max(min, Math.min(max, x)) by ho VZDY
      // vratilo na min bez ohledu na tazeni (Robertuv bug "vrátí se nahoru").
      const minTopWindow = 50, maxTopWindow = window.innerHeight - panelEl.offsetHeight - 6;
      const minLeftWindow = 0, maxLeftWindow = window.innerWidth - panelEl.offsetWidth - 6;
      const topLo = Math.min(minTopWindow, maxTopWindow), topHi = Math.max(minTopWindow, maxTopWindow);
      const leftLo = Math.min(minLeftWindow, maxLeftWindow), leftHi = Math.max(minLeftWindow, maxLeftWindow);
      const newTopWindow = Math.max(topLo, Math.min(topHi, rect.top + dy));
      const newLeftWindow = Math.max(leftLo, Math.min(leftHi, rect.left + dx));
      writePanelWindowPos(panelEl, newTopWindow, newLeftWindow);
    }
    function onUp() {
      handleEl.classList.remove("panel-dragging");
      document.body.style.userSelect = "";
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
      if (moved) {
        // Az TED (pusteni mysi): magnet k bocnim panelum + tvrdy
        // backstop + kolize s ostatnimi plovoucimi panely.
        const dropRect = panelEl.getBoundingClientRect();
        const width = panelEl.offsetWidth, height = panelEl.offsetHeight;
        let pos = applyPanelSideMagnet(dropRect.top, dropRect.left, width, height);
        panelEl._attachedWall = pos.wall; // viz followAttachedWall - null = uz se ke stene nedrzi
        pos = clampRectToViewport(pos.top, pos.left, width, height);
        pos = resolvePanelOverlaps(panelEl, pos.top, pos.left, width, height);
        writePanelWindowPos(panelEl, pos.top, pos.left);
        try {
          localStorage.setItem(storageKeyPrefix + "Top", String(Math.round(parseFloat(panelEl.style.top))));
          localStorage.setItem(storageKeyPrefix + "Left", String(Math.round(parseFloat(panelEl.style.left))));
        } catch (e) { /* ignoruj */ }
      }
    }
    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
  });
}

// Robert 2026-08-12 ("dej ty okna plovouci, porad mi to nejak zavazi"):
// Kontrola ploch / Pozice uhelniku / 🎓 Naucit napojeni jdou nove
// odtahnout kamkoli za hlavicku, stejnym mechanismem jako ostatni
// plovouci panely (makePanelDraggable). Panel MUSI byt v okamziku
// volani viditelny (display != none) - jinak by getBoundingClientRect()
// vratil nuly a prvni pozice by byla spatne spocitana - proto se
// nevola pri startu stranky, ale az PRI KAZDEM OTEVRENI panelu (a jen
// jednou, viz dataset.dragInit flag).
function ensurePanelDraggable(panelEl, headerEl, storageKeyPrefix) {
  if (!panelEl || !headerEl || panelEl.dataset.dragInit) return;
  panelEl.dataset.dragInit = "1";
  makePanelDraggable(panelEl, headerEl, storageKeyPrefix);
}

function setupSidePanelCollapse(panelId, headerBtnId, tabId, resizerId, storageKey) {
  const panel = document.getElementById(panelId);
  const btn = document.getElementById(headerBtnId);
  const tab = document.getElementById(tabId);
  const resizerEl = document.getElementById(resizerId);
  if (!panel || !btn || !tab) return;

  // Zasunuti/rozbaleni sidebar/summary posouva magnet/backstop pro
  // plovouci panely (viz DRAGGABLE_PANELS) - po dobehnuti prechodu je
  // potreba je "dotlacit" do platne pozice, kdyby uz nekteremu prekazely.
  function reclampFloatingPanels() {
    if (typeof reclampAllFloating === "function") reclampAllFloating();
  }
  function setCollapsed(collapsed) {
    panel.classList.toggle("collapsed", collapsed);
    if (resizerEl) resizerEl.classList.toggle("collapsed", collapsed);
    tab.classList.toggle("visible", collapsed);
    try { localStorage.setItem(storageKey, collapsed ? "1" : "0"); } catch (e) {}
    updateViewportSize();
    reclampFloatingPanels();
  }
  // Sirka se meni prechodem (transition) .22s - az dobehne, doladi se
  // presna velikost 3D vykreslovaciho plátna (renderer + aspect kamery)
  // a znovu se overi pozice plovoucich panelu (viz reclampFloatingPanels).
  panel.addEventListener("transitionend", (ev) => {
    if (ev.propertyName === "width") { updateViewportSize(); reclampFloatingPanels(); }
  });

  btn.onclick = () => setCollapsed(true);
  tab.onclick = () => {
    if (tab._justDragged) { tab._justDragged = false; return; }
    setCollapsed(false);
  };
  makeTabVerticallyDraggable(tab, storageKey + "TabTop");

  // Robert 2026-08-07 ("Při otevření scény nechej všechny panely
  // zabalené") - vychozi (kdyz jeste neni nic v localStorage) zmeneno
  // ze zabaleno=false na true, pro VSECHNY panely (tady sidebar/summary,
  // stejna zmena i u wizard/ai/axisMove/move/camera/toolsMenu nize v
  // souboru). Uz ulozena volba uzivatele (localStorage) ma porad
  // prednost - tyka se jen prvniho nacteni bez zadne ulozene historie.
  let startCollapsed = true;
  try { const saved = localStorage.getItem(storageKey); if (saved !== null) startCollapsed = saved === "1"; } catch (e) {}
  setCollapsed(startCollapsed);
}
setupSidePanelCollapse("sidebar", "sidebarCollapseBtn", "sidebarTab", "resizerLeft", "sidebarCollapsed");
setupSidePanelCollapse("summary", "summaryCollapseBtn", "summaryTab", "resizerRight", "summaryCollapsed");

// --- Vysouvací/zasouvací panel "Přednastavené tvary" (ať nezavazí ve výhledu do scény) ---
(function setupWizardPanelToggle() {
  const panel = document.getElementById("wizardPanel");
  const tab = document.getElementById("wizardTab");
  const collapseBtn = document.getElementById("wizardCollapseBtn");
  if (!panel || !tab || !collapseBtn) return;
  const STORAGE_KEY = "wizardPanelCollapsed";
  // Robert 2026-08-06 ("udělej totéž s ostatními tlačítky" - viz fwShapesTab
  // vyse): skipDropRepositioning vypne magnet+kolizni repozici po pusteni
  // mysi (skutecny viník navratu tabu k hornimu okraji), tab zustane presne
  // tam, kam ho uzivatel pustil.

  function setCollapsed(collapsed) {
    panel.classList.toggle("collapsed", collapsed);
    tab.classList.toggle("visible", collapsed);
    try { localStorage.setItem(STORAGE_KEY, collapsed ? "1" : "0"); } catch (e) {}
  }

  collapseBtn.onclick = () => setCollapsed(true);
  tab.onclick = () => {
    if (tab._justDragged) { tab._justDragged = false; return; }
    setCollapsed(false);
  };
  makeTabVerticallyDraggable(tab, STORAGE_KEY + "TabTop", { skipDropRepositioning: true });
  makePanelDraggable(panel, document.getElementById(panel.id + "Header"), STORAGE_KEY + "Pos");

  let startCollapsed = true;
  try { const saved = localStorage.getItem(STORAGE_KEY); if (saved !== null) startCollapsed = saved === "1"; } catch (e) {}
  setCollapsed(startCollapsed);
})();

(function setupAiPanelToggle() {
  const panel = document.getElementById("aiPanel");
  const tab = document.getElementById("aiTab");
  const collapseBtn = document.getElementById("aiCollapseBtn");
  if (!panel || !tab || !collapseBtn) return;
  const STORAGE_KEY = "aiPanelCollapsed";
  // Robert 2026-08-06 ("udělej totéž s ostatními tlačítky" - viz fwShapesTab
  // vyse): skipDropRepositioning vypne magnet+kolizni repozici po pusteni
  // mysi, tab zustane presne tam, kam ho uzivatel pustil.

  function setCollapsed(collapsed) {
    panel.classList.toggle("collapsed", collapsed);
    tab.classList.toggle("visible", collapsed);
    try { localStorage.setItem(STORAGE_KEY, collapsed ? "1" : "0"); } catch (e) {}
  }

  collapseBtn.onclick = () => setCollapsed(true);
  tab.onclick = () => {
    if (tab._justDragged) { tab._justDragged = false; return; }
    setCollapsed(false);
  };
  makeTabVerticallyDraggable(tab, STORAGE_KEY + "TabTop", { skipDropRepositioning: true });
  makePanelDraggable(panel, document.getElementById(panel.id + "Header"), STORAGE_KEY + "Pos");

  let startCollapsed = true;
  try { const saved = localStorage.getItem(STORAGE_KEY); if (saved !== null) startCollapsed = saved === "1"; } catch (e) {}
  setCollapsed(startCollapsed);
})();

(function setupAxisMovePanelToggle() {
  const panel = document.getElementById("axisMovePanel");
  const tab = document.getElementById("axisMoveTab");
  const collapseBtn = document.getElementById("axisMoveCollapseBtn");
  if (!panel || !tab || !collapseBtn) return;
  const STORAGE_KEY = "axisMovePanelCollapsed";
  // Robert 2026-08-06 ("udělej totéž s ostatními tlačítky" - viz fwShapesTab
  // vyse): skipDropRepositioning vypne magnet+kolizni repozici po pusteni
  // mysi, tab zustane presne tam, kam ho uzivatel pustil.

  function setCollapsed(collapsed) {
    panel.classList.toggle("collapsed", collapsed);
    tab.classList.toggle("visible", collapsed);
    try { localStorage.setItem(STORAGE_KEY, collapsed ? "1" : "0"); } catch (e) {}
  }

  collapseBtn.onclick = () => setCollapsed(true);
  tab.onclick = () => {
    if (tab._justDragged) { tab._justDragged = false; return; }
    setCollapsed(false);
  };
  makeTabVerticallyDraggable(tab, STORAGE_KEY + "TabTop", { skipDropRepositioning: true });
  makePanelDraggable(panel, document.getElementById(panel.id + "Header"), STORAGE_KEY + "Pos");

  let startCollapsed = true;
  try { const saved = localStorage.getItem(STORAGE_KEY); if (saved !== null) startCollapsed = saved === "1"; } catch (e) {}
  setCollapsed(startCollapsed);
})();

(function setupMovePanelToggle() {
  const panel = document.getElementById("movePanel");
  const tab = document.getElementById("moveTab");
  const collapseBtn = document.getElementById("moveCollapseBtn");
  if (!panel || !tab || !collapseBtn) return;
  const STORAGE_KEY = "movePanelCollapsed";
  // Robert 2026-08-06 ("udělej totéž s ostatními tlačítky" - viz fwShapesTab
  // vyse): skipDropRepositioning vypne magnet+kolizni repozici po pusteni
  // mysi, tab zustane presne tam, kam ho uzivatel pustil.

  function setCollapsed(collapsed) {
    panel.classList.toggle("collapsed", collapsed);
    tab.classList.toggle("visible", collapsed);
    try { localStorage.setItem(STORAGE_KEY, collapsed ? "1" : "0"); } catch (e) {}
  }

  collapseBtn.onclick = () => setCollapsed(true);
  tab.onclick = () => {
    if (tab._justDragged) { tab._justDragged = false; return; }
    setCollapsed(false);
  };
  makeTabVerticallyDraggable(tab, STORAGE_KEY + "TabTop", { skipDropRepositioning: true });
  makePanelDraggable(panel, document.getElementById(panel.id + "Header"), STORAGE_KEY + "Pos");

  let startCollapsed = true;
  try { const saved = localStorage.getItem(STORAGE_KEY); if (saved !== null) startCollapsed = saved === "1"; } catch (e) {}
  setCollapsed(startCollapsed);
})();

(function setupToolsMenuPanelToggle() {
  const panel = document.getElementById("toolsMenuPanel");
  const tab = document.getElementById("toolsMenuTab");
  const collapseBtn = document.getElementById("toolsMenuCollapseBtn");
  if (!panel || !tab || !collapseBtn) return;
  const STORAGE_KEY = "toolsMenuPanelCollapsed";

  function setCollapsed(collapsed) {
    panel.classList.toggle("collapsed", collapsed);
    tab.classList.toggle("visible", collapsed);
    try { localStorage.setItem(STORAGE_KEY, collapsed ? "1" : "0"); } catch (e) {}
  }

  collapseBtn.onclick = () => setCollapsed(true);
  tab.onclick = () => {
    if (tab._justDragged) { tab._justDragged = false; return; }
    setCollapsed(false);
  };
  // Robert 2026-08-06 ("Menu nástroje nech se magnetuje na bočný pravý
  // panel, když se zabalí boční panel Menu se posune na jeho místo a
  // obráceně") - trvale namagnetovano k prave stene (#summary, viz
  // followAttachedWall) hned od zacatku, ne az po prvnim rucnim
  // pretazeni tam uzivatelem. Nastaveno PRED makePanelDraggable/
  // makeTabVerticallyDraggable, aby to zachytil uz jejich prvni interni
  // finalizePanelPosition/finalizeTabPosition volani. Rucni pretazeni
  // jinam (mimo dosah magnetu) toto chovani jako obvykle vypne (viz onUp).
  panel._attachedWall = "right";
  tab._attachedWall = "right";
  makeTabVerticallyDraggable(tab, STORAGE_KEY + "TabTop");
  makePanelDraggable(panel, document.getElementById(panel.id + "Header"), STORAGE_KEY + "Pos");

  let startCollapsed = true;
  try { const saved = localStorage.getItem(STORAGE_KEY); if (saved !== null) startCollapsed = saved === "1"; } catch (e) {}
  setCollapsed(startCollapsed);
})();

// Robert 2026-08-02 ("udelej ve scene pro tlacitka takovou strukturu, ve
// forme menu, do ktereho presuneme vsechny tlacitka, kazdy uzivatel si
// nasledne muze pretahovat tlacitka z menu do sceny a zpet, takze
// plovouci"): kazde tlacitko v #toolsMenuList jde uchopit a vytahnout
// mysi ven do sceny (#viewport) - stane se tam samostatnym plovoucim
// tlacitkem (.toolFloatingBtn, position:absolute na miste puštění), beze
// zmeny funkce (puvodni "click" listener zustava navazany na TENTYZ
// DOM uzel - jen se presouva, nikdy neklonuje). Pretazenim zpet na panel
// #toolsMenuPanel (kdyz je rozbaleny) se tlacitko vrati do seznamu.
// Rozlozeni (co je kde) se pamatuje per prohlizec (localStorage) - kazdy
// uzivatel/pocitac ma vlastni, nezavisle na serveru.
const TOOLS_MENU_BUTTON_IDS = [
  "btnClear", "btnUndo", "btnStepBack", "btnDeselectAll", "btnCopySelection", "btnFindJoints", "btnHighlightJointFaces",
  "btnAttachAccessory", "btnAttachProfiles2", "btnMagnetReachToggle", "btnAttachKloub", "btnGroundSelection", "btnExportFbx",
  "btnConnectorReview", "btnJointPositionReview", "btnUhelnikPoseReview", "btnRoztahuj", "btnPaintMode", "btnPaintSameMode", "btnSetSelectColor",
  // Robert 2026-08-02 ("proc neni ten pruh barvy na gradient plovouci??? pravidlo
  // je jasne, vsechny nove prvky patri do menu" + "jako odnimatelne prvky zpet
  // na scenu"): NOVE STANDARDNI PRAVIDLO jde dopredu - kazdy nove pridany UI
  // prvek patri od zacatku do Menu nastroju a musi jit vytahnout/vratit stejne
  // jako tlacitka. Prouzek na vyber barvy prostredi (#envColorStripWrap, drive
  // samostatny plovouci panel mimo menu) je prvni prvek retroaktivne prevedeny
  // na tento system - viz TOOLS_MENU_EXCLUDE_SELECTORS nize (jeho vlastni
  // tazeni po prouzku - vyber odstinu - musi mit prednost pred relokacnim
  // tazenim, jinak by tazeni barvy omylem vytahovalo cely prvek ze sceny).
  "envColorStripWrap",
];
// Nekterym polozkam menu (ne jen tlacitkum) je potreba vyloucit jejich vlastni
// ovladaci gesto z relokacniho tazeni - mousedown, ktery zacne uvnitr tohoto
// selektoru, relokaci vubec nespusti a necha ho plne v rezii vlastniho
// listeneru prvku (napr. #envColorStrip ma svuj vlastni mousedown pro vyber
// barvy - viz setupEnvColorStrip).
const TOOLS_MENU_EXCLUDE_SELECTORS = { envColorStripWrap: "#envColorStrip, #envBrightnessSlider, #envSaturationSlider, #lightIntensitySlider, #sceneContrastSlider, #shadowsToggle, #lowResToggle, #envReturnToMenuBtn, #envColorCollapseBtn" };
// Robert 2026-08-06 ("v tom panelu musíme udělat 2. úroveň zanoření",
// upresneno na AskUserQuestion: "sbalitelné skupiny/složky tlačítek",
// rozdeleni navrhnout sam) - vychozi rozdeleni TOOLS_MENU_BUTTON_IDS do
// pojmenovanych skupin podle funkce. Pouziva se jen kdyz jeste neni
// ulozene layout.groups (viz buildToolsMenuGroups) - jakmile uzivatel
// jednou tlacitko pretahne, dal uz rozhoduje ulozena struktura, ne tenhle
// seznam (ten uz jen doplnuje BUDOUCI nova ID, ktera v ulozene strukture
// jeste nejsou).
const TOOLS_MENU_DEFAULT_GROUPS = [
  { id: "edit", label: "Výběr a úpravy", buttonIds: ["btnClear", "btnUndo", "btnStepBack", "btnDeselectAll", "btnCopySelection", "btnGroundSelection", "btnExportFbx"] },
  { id: "joints", label: "Spoje a příslušenství", buttonIds: ["btnFindJoints", "btnHighlightJointFaces", "btnAttachAccessory", "btnAttachProfiles2", "btnMagnetReachToggle", "btnAttachKloub", "btnConnectorReview", "btnJointPositionReview", "btnUhelnikPoseReview", "btnRoztahuj"] },
  { id: "colors", label: "Barvy a prostředí", buttonIds: ["btnPaintMode", "btnPaintSameMode", "btnSetSelectColor", "envColorStripWrap"] },
  // Robert 2026-09-18 ("novy panel nastroju, nazev: auta, pro scenu kde se
  // budou davat funkce tykajici se sestav pro auta") - zatim prazdna skupina,
  // funkce se budou pridavat postupne. Nove tlacitko sem zaradis pridanim
  // jeho id do TOOLS_MENU_BUTTON_IDS vyse (jinak se v menu vubec nezobrazi)
  // a do buttonIds tady (vychozi razeni, dokud si uzivatel layout sam neupravi).
  { id: "auta", label: "Auta", buttonIds: [] },
];
const TOOLS_MENU_LAYOUT_KEY = "konfToolsMenuLayout";
const TOOL_DRAG_THRESHOLD_PX = 5;

function loadToolsMenuLayout() {
  try {
    const raw = localStorage.getItem(TOOLS_MENU_LAYOUT_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch (e) { return {}; }
}
function saveToolsMenuLayout(layout) {
  try { localStorage.setItem(TOOLS_MENU_LAYOUT_KEY, JSON.stringify(layout)); } catch (e) { /* ignoruj */ }
}

// Rozhodne, jestli se ma tlacitko pri pusteni vratit do menu - podle toho,
// jestli je bod pusteni (cursorX/Y, souradnice OKNA) uvnitr aktualne
// ROZBALENEHO panelu #toolsMenuPanel (kdyz je zabaleny - jen tab - vraceni
// timhle zpusobem nejde, uzivatel musi panel nejdriv rozbalit).
function isPointOverToolsMenuPanel(cursorX, cursorY) {
  const panel = document.getElementById("toolsMenuPanel");
  if (!panel || panel.classList.contains("collapsed")) return false;
  const r = panel.getBoundingClientRect();
  return cursorX >= r.left && cursorX <= r.right && cursorY >= r.top && cursorY <= r.bottom;
}

// Robert 2026-09-13 ("prazdny panel, kam muzu vkladat tlacitka co se
// valeji po plose"): #toolboxPanel (material-panel.js) uz existoval jako
// KODEM naplnovany kontejner (scenePridejTlacitko) - tohle je DRUHY,
// nezavisly zpusob, jak se do nej dostat tlacitko: rucni pretazeni
// libovolneho plovouciho tlacitka Menu nastroju, stejny princip jako
// isPointOverToolsMenuPanel vyse. `display:none` (uplne prazdny panel)
// pocita jako "neni cil" - stejne jako sbaleny #toolsMenuPanel vyse.
function isPointOverToolboxPanel(cursorX, cursorY) {
  const panel = document.getElementById("toolboxPanel");
  if (!panel || getComputedStyle(panel).display === "none") return false;
  const r = panel.getBoundingClientRect();
  return cursorX >= r.left && cursorX <= r.right && cursorY >= r.top && cursorY <= r.bottom;
}

// Zarazuje tlacitko do RUCNE rady #toolboxPanelUser (na rozdil od
// #toolboxPanelBody, kterou cely prekresluje prekresliToolbox() v
// material-panel.js - do te se proto nikdy nesaha primo, aby dalsi
// scenePridejTlacitko/sceneOdeberTlacitko rucne dokovane tlacitko tise
// nesmazal). Vzdy na konec rady - presne poradi pretazeni tu nehraje roli,
// jde o "odlozitko", ne o serazeny seznam jako Menu nastroju.
function dockToolButtonInToolbox(btn) {
  btn.classList.remove("toolFloatingBtn", "tool-btn-dragging");
  btn.style.left = ""; btn.style.top = "";
  btn.classList.remove("collapsed");
  const btnTab = document.getElementById(btn.id + "Tab");
  if (btnTab) btnTab.classList.remove("visible");
  const userWrap = document.getElementById("toolboxPanelUser");
  if (userWrap) userWrap.appendChild(btn);
  const panel = document.getElementById("toolboxPanel");
  if (panel) panel.style.display = ""; // prave prijalo tlacitko - urcite nema byt schovany
  const layout = loadToolsMenuLayout();
  delete layout.order; // stary plochy format (pred zavedenim skupin)
  layout[btn.id] = { dockedIn: "toolbox" };
  saveToolsMenuLayout(layout);
}

// Robert 2026-08-06 ("určit si pořadí podle toho mezi které stávající to
// vložím" + nasledne "2. úroveň zanoření" - sbalitelne skupiny) - podle
// Y souradnice kurzoru najde JAK cilovou SKUPINU (nejbliz kurzoru, nebo
// tu, ve ktere se kurzor primo nachazi), TAK pozici v jejim seznamu
// (PRED ktere stavajici tlacitko se ma vlozit - porovnava s vodorovnym
// stredem kazde polozky). `before: null` = vlozit na konec te skupiny.
function findToolsMenuDropTarget(cursorY) {
  const menuList = document.getElementById("toolsMenuList");
  if (!menuList) return null;
  const groupEls = Array.from(menuList.querySelectorAll(".tools-menu-group"));
  if (!groupEls.length) return null;
  let target = groupEls.find(g => {
    const r = g.getBoundingClientRect();
    return cursorY >= r.top && cursorY <= r.bottom;
  });
  if (!target) {
    target = groupEls.reduce((best, g) => {
      const r = g.getBoundingClientRect();
      const dist = Math.min(Math.abs(cursorY - r.top), Math.abs(cursorY - r.bottom));
      return (!best || dist < best.dist) ? { g, dist } : best;
    }, null).g;
  }
  const list = target.querySelector(".tools-menu-group-list");
  const children = Array.from(list.children).filter(el => el.id !== "toolsMenuDropIndicator");
  let before = null;
  for (const child of children) {
    const r = child.getBoundingClientRect();
    if (cursorY < r.top + r.height / 2) { before = child; break; }
  }
  return { list, before };
}
function updateToolsMenuDropIndicator(cursorX, cursorY) {
  removeToolsMenuDropIndicator();
  if (!isPointOverToolsMenuPanel(cursorX, cursorY)) return;
  const target = findToolsMenuDropTarget(cursorY);
  if (!target) return;
  const indicator = document.createElement("div");
  indicator.id = "toolsMenuDropIndicator";
  if (target.before) target.list.insertBefore(indicator, target.before);
  else target.list.appendChild(indicator);
}
function removeToolsMenuDropIndicator() {
  const indicator = document.getElementById("toolsMenuDropIndicator");
  if (indicator) indicator.remove();
}

function clampFloatingButtonToViewport(btn) {
  const viewport = document.getElementById("viewport");
  if (!viewport) return;
  const vw = viewport.clientWidth, vh = viewport.clientHeight;
  const bw = btn.offsetWidth || 40, bh = btn.offsetHeight || 24;
  let left = parseFloat(btn.style.left) || 0;
  let top = parseFloat(btn.style.top) || 0;
  // Robert 2026-08-06 ("porad je to nahoře nalepene všechno") - TOHLE byl
  // skutecny viník, jiny system nez #toolsMenuPanel/tabu (viz predchozi
  // zapisy) - "Prostředí scény" je jednotlive vytazitelne tlacitko
  // (makeToolButtonRelocatable), ne panel z makePanelDraggable. Diky
  // dnesnim pridanym posuvnikum (Jas/Sytost/Svetlo/Kontrast/Stiny/Magnet)
  // uz box neni maly ctverecek, ale vysoky sloupec - kdyz jeho vyska (bh)
  // presahla vysku viewportu, "46" (min) bylo VETSI nez "vh-bh" (max), a
  // Math.max(46, Math.min(...)) VZDY vratil 46 bez ohledu na tazeni -
  // stejny bug jako v clampRectToViewport, jen v uplne jine funkci, ktere
  // jsem si predtim nevsiml. Normalizovane [lo,hi] jako tam.
  const topLo = Math.min(46, vh - bh), topHi = Math.max(46, vh - bh);
  const leftLo = Math.min(0, vw - bw), leftHi = Math.max(0, vw - bw);
  left = Math.max(leftLo, Math.min(leftHi, left));
  top = Math.max(topLo, Math.min(topHi, top));
  btn.style.left = left + "px";
  btn.style.top = top + "px";
}

// Precte AKTUALNI DOM strukturu skupin (#toolsMenuList > .tools-menu-group
// > .tools-menu-group-list > tlacitka) a ulozi ji do layout.groups - volano
// po kazde zmene (navrat tlacitka, presun mezi skupinami), aby poradi i
// prirazeni do skupin prezily reload stranky.
function persistToolsMenuGroups() {
  const menuList = document.getElementById("toolsMenuList");
  if (!menuList) return;
  const layout = loadToolsMenuLayout();
  layout.groups = Array.from(menuList.querySelectorAll(".tools-menu-group")).map(g => {
    const header = g.querySelector(".tools-menu-group-header");
    return {
      id: g.dataset.groupId,
      label: (header && header.dataset.label) || g.dataset.groupId,
      order: Array.from(g.querySelector(".tools-menu-group-list").children)
        .filter(el => el.id !== "toolsMenuDropIndicator")
        .map(el => el.id).filter(Boolean),
    };
  });
  saveToolsMenuLayout(layout);
}

// Vraci vytazene tlacitko/box zpet do Menu nastroju - sdileno mezi
// "pusteni presne na panelu" (onUp nize) a primym tlacitkem "↩ Menu"
// (Robert 2026-08-06: "je potřeba aby se dalo vraqcet zpět do panelu" -
// primy klik nezavisi na presnosti pretazeni zpet na panel).
// `targetListEl`/`insertBeforeEl` (Robert 2026-08-06, "určit si pořadí..."
// + "2. úroveň zanoření"): volitelny odkaz na cilovy `.tools-menu-group-list`
// a stavajici tlacitko v nem, PRED ktere se ma vratit - bez nich (napr.
// klik na "↩ Menu") se pouzije prvni skupina a konec jejiho seznamu.
function returnToolButtonToMenu(btn, targetListEl, insertBeforeEl) {
  btn.classList.remove("toolFloatingBtn", "tool-btn-dragging");
  btn.style.left = ""; btn.style.top = "";
  // bot7 2026-08-08: pokud se dokovany dil vraci sbaleny (viz
  // setupEnvColorPanelToggle - zatim jedine tlacitko s vlastnim sbalenim),
  // vycistit stav i schovat jeho tab, at pri pristim vytazeni nezustane
  // "duchem" sbaleny/tab viditelny bez ucelu.
  btn.classList.remove("collapsed");
  const btnTab = document.getElementById(btn.id + "Tab");
  if (btnTab) btnTab.classList.remove("visible");
  const menuList = document.getElementById("toolsMenuList");
  const list = (targetListEl && targetListEl.classList && targetListEl.classList.contains("tools-menu-group-list"))
    ? targetListEl
    : (menuList.querySelector(".tools-menu-group-list") || menuList);
  if (insertBeforeEl && insertBeforeEl.parentElement === list && insertBeforeEl !== btn) {
    list.insertBefore(btn, insertBeforeEl);
  } else {
    list.appendChild(btn);
  }
  const layout = loadToolsMenuLayout();
  delete layout[btn.id];
  delete layout.order; // stary plochy format (pred zavedenim skupin) - nahrazen layout.groups
  saveToolsMenuLayout(layout);
  persistToolsMenuGroups();
}

// ---------------------------------------------------------------------
// ZAMEK POZIC PLOVOUCICH IKON (Robert 2026-08-12: "plovouci ikony ve
// scene se mi pokazde nejak rozhodi, potrebuju ikony ve smyslu uzamceni
// pozice na obrazovce s moznosti odemceni").
//
// Zamek se tyka POUZE tazeni - kliky (vlozit dil, spustit nastroj,
// otevrit panel) funguji dal. Plati na vsechny tri druhy plovoucich
// prvku: vytazena tlacitka Menu nastroju (.toolFloatingBtn), ikony
// obrazkoveho katalogu a svisle zalozky panelu (.fw-shapes-tab).
// Stav prezije obnoveni stranky.
//
// OPRAVA (Robert 2026-08-12, "cela scena cerna"): `let floatingIconsLocked`
// byl puvodne az TADY, ale finalizeTabPosition/reclampAllFloating (o
// tisice radku VYS v souboru) na nej odkazuji uz behem POCATECNIHO
// nacteni stranky - v tu chvili tenhle radek jeste NEDOBEHL, coz je
// v JS ReferenceError ("temporal dead zone"), i pres `typeof x ===
// "undefined"` ochranu (ta funguje jen na OPRAVDU nedeklarovanou
// promennou, ne na let/const pred jejich radkem). Nezachycena vyjimka
// zastavila CELY zbytek hlavniho skriptu (Three.js scena, GLB, tlacitka
// renderu...) - proto byl videt jen staticke HTML, ale 3D vyrez cerny.
// Samotna deklarace je proto ted uplne na zacatku skriptu (viz
// FLOATING_ICONS_LOCKED_DECLARED_EARLY), tady zustavaji jen funkce.
// ---------------------------------------------------------------------
const FLOATING_LOCK_KEY = "konfFloatingIconsLocked";
function setFloatingLocked(on) {
  floatingIconsLocked = !!on;
  document.body.classList.toggle("floating-locked", floatingIconsLocked);
  const btn = document.getElementById("floatingLockBtn");
  if (btn) {
    btn.textContent = floatingIconsLocked ? "🔒" : "🔓";
    btn.classList.toggle("is-locked", floatingIconsLocked);
    btn.title = floatingIconsLocked
      ? "Pozice plovoucích ikon jsou ZAMČENÉ - kliknutím odemkneš a půjdou zase přesouvat"
      : "Zamknout pozice plovoucích ikon a záložek ve scéně (zabrání nechtěnému přetažení)";
  }
  try { localStorage.setItem(FLOATING_LOCK_KEY, floatingIconsLocked ? "1" : "0"); } catch (e) { /* ignoruj */ }
}
(function initFloatingLock() {
  let saved = false;
  try { saved = localStorage.getItem(FLOATING_LOCK_KEY) === "1"; } catch (e) { /* ignoruj */ }
  setFloatingLocked(saved);
  const btn = document.getElementById("floatingLockBtn");
  if (btn) btn.addEventListener("click", (ev) => {
    ev.preventDefault(); ev.stopPropagation();   // hlavicka panelu je tazitelna
    setFloatingLocked(!floatingIconsLocked);
    showJoinToast(floatingIconsLocked
      ? "🔒 Pozice plovoucích ikon zamčené - přetažení je vypnuté, kliky fungují dál."
      : "🔓 Pozice plovoucích ikon odemčené - ikony jde zase přesouvat.");
  });
  const hdr = document.getElementById("toolsMenuPanelHeader");
  if (hdr) hdr.addEventListener("mousedown", (ev) => {
    if (ev.target && ev.target.id === "floatingLockBtn") ev.stopPropagation();
  }, true);
})();

function makeToolButtonRelocatable(btn, opts) {
  if (!btn) return;
  const excludeSelector = opts && opts.excludeSelector;
  btn.addEventListener("mousedown", (ev) => {
    if (ev.button !== 0) return;
    if (floatingIconsLocked) return;   // zamceno - viz setFloatingLocked
    if (excludeSelector && ev.target.closest(excludeSelector)) return; // vlastni gesto prvku (napr. vyber barvy) ma prednost pred relokaci
    const startX = ev.clientX, startY = ev.clientY;
    let dragging = false;
    let offsetX = 0, offsetY = 0;
    const viewport = document.getElementById("viewport");

    function onMove(mv) {
      const dx = mv.clientX - startX, dy = mv.clientY - startY;
      if (!dragging) {
        if (Math.hypot(dx, dy) < TOOL_DRAG_THRESHOLD_PX) return;
        dragging = true;
        // Prevzit tlacitko do #viewport (pokud tam jeste neni) a spocitat
        // odsazeni kurzoru od jeho leveho horniho rohu, aby "neskoclo" pod
        // stred kurzoru, ale zustalo tam, kde ho uzivatel chytil.
        const r = btn.getBoundingClientRect();
        const vpRect = viewport.getBoundingClientRect();
        offsetX = startX - r.left;
        offsetY = startY - r.top;
        if (btn.parentElement !== viewport) viewport.appendChild(btn);
        btn.classList.add("toolFloatingBtn", "tool-btn-dragging");
        btn.style.left = (r.left - vpRect.left) + "px";
        btn.style.top = (r.top - vpRect.top) + "px";
      }
      const vpRect = viewport.getBoundingClientRect();
      btn.style.left = (mv.clientX - vpRect.left - offsetX) + "px";
      btn.style.top = (mv.clientY - vpRect.top - offsetY) + "px";
      const panel = document.getElementById("toolsMenuPanel");
      const overPanel = isPointOverToolsMenuPanel(mv.clientX, mv.clientY);
      if (panel) panel.classList.toggle("drop-target", overPanel);
      if (overPanel) updateToolsMenuDropIndicator(mv.clientX, mv.clientY);
      else removeToolsMenuDropIndicator();
      // Druhy mozny cil (viz isPointOverToolboxPanel) - jen kdyz uz to neni
      // Menu nastroju (dva soucasne zvyraznene panely by matly).
      const toolboxPanel = document.getElementById("toolboxPanel");
      if (toolboxPanel) toolboxPanel.classList.toggle("drop-target", !overPanel && isPointOverToolboxPanel(mv.clientX, mv.clientY));
    }

    function onUp(mv) {
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
      const panel = document.getElementById("toolsMenuPanel");
      if (panel) panel.classList.remove("drop-target");
      const toolboxPanel = document.getElementById("toolboxPanel");
      if (toolboxPanel) toolboxPanel.classList.remove("drop-target");
      // Indikator ukazuje presne misto vlozeni (i cilovou skupinu - jeho
      // rodic) - jeho nasledujici sourozenec je tlacitko, PRED ktere se ma
      // tazene tlacitko zaradit (null = konec te skupiny).
      const indicator = document.getElementById("toolsMenuDropIndicator");
      const targetListEl = indicator ? indicator.parentElement : null;
      const insertBeforeEl = indicator ? indicator.nextElementSibling : null;
      removeToolsMenuDropIndicator();
      if (!dragging) return; // obycejny klik - nic nemenit, "click" event probehne normalne
      if (isPointOverToolsMenuPanel(mv.clientX, mv.clientY)) {
        returnToolButtonToMenu(btn, targetListEl, insertBeforeEl);
      } else if (isPointOverToolboxPanel(mv.clientX, mv.clientY)) {
        dockToolButtonInToolbox(btn);
      } else {
        btn.classList.remove("tool-btn-dragging");
        clampFloatingButtonToViewport(btn);
        const layout = loadToolsMenuLayout();
        layout[btn.id] = { floating: true, x: parseFloat(btn.style.left) || 0, y: parseFloat(btn.style.top) || 0 };
        saveToolsMenuLayout(layout);
      }
    }

    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
  });
}

// Robert 2026-08-16 ("toto tlacitko chci vyjimatelne z panelu na plochu a
// zpet"): stejny princip a vizualni jazyk jako makeToolButtonRelocatable
// (tazeni ven do #viewport = plovouci tlacitko .toolFloatingBtn, stejne
// localStorage ulozeni pozice pres konfToolsMenuLayout), jen zjednodusene
// pro tlacitko MIMO skupinovy system #toolsMenuList (napr. #btnAutoTeach
// uvnitr #attachTeachPanel) - nema zadne poradi/skupiny k volbe, vraci se
// PRESNE tam, odkud vzniklo (zapamatovany puvodni rodic + pozice mezi
// sourozenci), kdyz se pusti nad zadanym "domovskym" panelem.
function makeSimpleToolButtonFloatable(btn, homePanelEl) {
  if (!btn || !homePanelEl) return;
  const homeParent = btn.parentElement;
  const homeNextSibling = btn.nextSibling;
  function isPointOverHome(x, y) {
    const r = homePanelEl.getBoundingClientRect();
    return x >= r.left && x <= r.right && y >= r.top && y <= r.bottom;
  }
  btn.addEventListener("mousedown", (ev) => {
    if (ev.button !== 0) return;
    if (floatingIconsLocked) return; // zamceno - viz setFloatingLocked
    const startX = ev.clientX, startY = ev.clientY;
    let dragging = false;
    let offsetX = 0, offsetY = 0;
    const viewport = document.getElementById("viewport");

    function onMove(mv) {
      const dx = mv.clientX - startX, dy = mv.clientY - startY;
      if (!dragging) {
        if (Math.hypot(dx, dy) < TOOL_DRAG_THRESHOLD_PX) return;
        dragging = true;
        const r = btn.getBoundingClientRect();
        const vpRect = viewport.getBoundingClientRect();
        offsetX = startX - r.left;
        offsetY = startY - r.top;
        if (btn.parentElement !== viewport) viewport.appendChild(btn);
        btn.classList.add("toolFloatingBtn", "tool-btn-dragging");
        btn.style.left = (r.left - vpRect.left) + "px";
        btn.style.top = (r.top - vpRect.top) + "px";
      }
      const vpRect = viewport.getBoundingClientRect();
      btn.style.left = (mv.clientX - vpRect.left - offsetX) + "px";
      btn.style.top = (mv.clientY - vpRect.top - offsetY) + "px";
      homePanelEl.classList.toggle("drop-target", isPointOverHome(mv.clientX, mv.clientY));
    }

    function onUp(mv) {
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
      homePanelEl.classList.remove("drop-target");
      if (!dragging) return; // obycejny klik - nic nemenit
      const layout = loadToolsMenuLayout();
      if (isPointOverHome(mv.clientX, mv.clientY)) {
        btn.classList.remove("toolFloatingBtn", "tool-btn-dragging");
        btn.style.left = ""; btn.style.top = "";
        homeParent.insertBefore(btn, homeNextSibling);
        delete layout[btn.id];
      } else {
        btn.classList.remove("tool-btn-dragging");
        clampFloatingButtonToViewport(btn);
        layout[btn.id] = { floating: true, x: parseFloat(btn.style.left) || 0, y: parseFloat(btn.style.top) || 0 };
      }
      saveToolsMenuLayout(layout);
    }

    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
  });
  // Obnoveni plovouciho stavu po reloadu - stejne ulozeni jako Menu
  // nastroju (viz initToolsMenuButtons), jen samostatne pro tohle tlacitko.
  const savedLayout = loadToolsMenuLayout();
  const saved = savedLayout[btn.id];
  if (saved && saved.floating) {
    const viewport = document.getElementById("viewport");
    if (viewport) {
      viewport.appendChild(btn);
      btn.classList.add("toolFloatingBtn");
      btn.style.left = (saved.x || 0) + "px";
      btn.style.top = (saved.y || 0) + "px";
      clampFloatingButtonToViewport(btn);
    }
  }
}
(function initAutoTeachButtonFloatable() {
  const btn = document.getElementById("btnAutoTeach");
  const homePanel = document.getElementById("attachTeachPanel");
  makeSimpleToolButtonFloatable(btn, homePanel);
})();

// Slozi definitivni seznam skupin + jejich poradi tlacitek - z ulozene
// layout.groups (kdyz uz uzivatel neco pretahal), jinak z vychozich
// TOOLS_MENU_DEFAULT_GROUPS. V obou pripadech doplni chybejici skupiny/ID
// (napr. nove tlacitko pridane budoucim botem do TOOLS_MENU_BUTTON_IDS,
// ktere jeste neni v zadne ulozene skupine) na konec jejich vychozi
// skupiny, aby nikdy nezmizely ze seznamu.
function buildToolsMenuGroups(layout) {
  const savedGroups = Array.isArray(layout.groups) ? layout.groups : null;
  const groups = savedGroups
    ? savedGroups.filter(g => g && g.id).map(g => ({ id: g.id, label: g.label || g.id, order: Array.isArray(g.order) ? g.order.slice() : [] }))
    : TOOLS_MENU_DEFAULT_GROUPS.map(g => ({ id: g.id, label: g.label, order: g.buttonIds.slice() }));
  TOOLS_MENU_DEFAULT_GROUPS.forEach(dg => {
    if (!groups.some(g => g.id === dg.id)) groups.push({ id: dg.id, label: dg.label, order: [] });
  });
  const placed = new Set();
  groups.forEach(g => g.order.forEach(id => placed.add(id)));
  TOOLS_MENU_BUTTON_IDS.forEach(id => {
    if (placed.has(id)) return;
    const defaultGroup = TOOLS_MENU_DEFAULT_GROUPS.find(dg => dg.buttonIds.includes(id));
    const targetId = defaultGroup ? defaultGroup.id : groups[0].id;
    (groups.find(g => g.id === targetId) || groups[0]).order.push(id);
    placed.add(id);
  });
  return groups;
}

// #automatGroup a #hdriWrap jsou staticke bloky primo v #toolsMenuList,
// ktere NEJSOU v TOOLS_MENU_BUTTON_IDS (nejdou jednotlive vytahnout jako
// plovouci tlacitko - Automat ma vlastni rozbalovani poduzeb, HDRI je cely
// vnoreny formular) - bez zarazeni by po zavedeni skupin "vypadly" mimo
// jakoukoli skupinu na zacatek panelu. `beforeId` = puvodni sousedni
// tlacitko v raw HTML, pred ktere se maji vlozit (zachova puvodni poradi
// v ramci sve cilove skupiny) - viz fallback (konec skupiny), kdyby
// uzivatel to sousedni tlacitko sam pretahl jinam.
const TOOLS_MENU_STATIC_BLOCKS = [
  { id: "automatGroup", groupId: "joints", beforeId: "btnUhelnikPoseReview" },
  { id: "hdriWrap", groupId: "colors", beforeId: "envColorStripWrap" },
];

function renderToolsMenuGroup(id, label, collapsed) {
  const wrap = document.createElement("div");
  wrap.className = "tools-menu-group" + (collapsed ? " collapsed" : "");
  wrap.dataset.groupId = id;
  const header = document.createElement("button");
  header.type = "button";
  header.className = "tools-menu-group-header";
  header.dataset.label = label;
  header.textContent = (collapsed ? "▸ " : "▾ ") + label;
  header.addEventListener("click", () => {
    const nowCollapsed = !wrap.classList.contains("collapsed");
    wrap.classList.toggle("collapsed", nowCollapsed);
    header.textContent = (nowCollapsed ? "▸ " : "▾ ") + label;
    const layout = loadToolsMenuLayout();
    if (!layout.collapsedGroups || typeof layout.collapsedGroups !== "object") layout.collapsedGroups = {};
    layout.collapsedGroups[id] = nowCollapsed;
    saveToolsMenuLayout(layout);
  });
  const list = document.createElement("div");
  list.className = "tools-menu-group-list";
  wrap.appendChild(header);
  wrap.appendChild(list);
  return wrap;
}

(function initToolsMenuButtons() {
  const layout = loadToolsMenuLayout();
  const viewport = document.getElementById("viewport");
  const menuList = document.getElementById("toolsMenuList");
  TOOLS_MENU_BUTTON_IDS.forEach(id => {
    const btn = document.getElementById(id);
    if (!btn) return;
    makeToolButtonRelocatable(btn, { excludeSelector: TOOLS_MENU_EXCLUDE_SELECTORS[id] });
  });
  const groups = buildToolsMenuGroups(layout);
  const collapsedGroups = layout.collapsedGroups && typeof layout.collapsedGroups === "object" ? layout.collapsedGroups : {};
  const staticBlocksPlaced = new Set();
  groups.forEach(g => {
    const groupEl = renderToolsMenuGroup(g.id, g.label, !!collapsedGroups[g.id]);
    menuList.appendChild(groupEl);
    const listEl = groupEl.querySelector(".tools-menu-group-list");
    g.order.forEach(id => {
      TOOLS_MENU_STATIC_BLOCKS.forEach(block => {
        if (block.groupId === g.id && block.beforeId === id && !staticBlocksPlaced.has(block.id)) {
          const blockEl = document.getElementById(block.id);
          if (blockEl) { listEl.appendChild(blockEl); staticBlocksPlaced.add(block.id); }
        }
      });
      const btn = document.getElementById(id);
      if (!btn) return;
      const saved = layout[id];
      if (saved && saved.floating && viewport) {
        viewport.appendChild(btn);
        btn.classList.add("toolFloatingBtn");
        btn.style.left = (saved.x || 0) + "px";
        btn.style.top = (saved.y || 0) + "px";
        clampFloatingButtonToViewport(btn);
      } else if (saved && saved.dockedIn === "toolbox") {
        // Rucne pretazene do #toolboxPanel drivejsi session - viz
        // dockToolButtonInToolbox. Panel se musi ukazat, i kdyby
        // #toolboxPanelBody (kodem rizena rada) byla zrovna prazdna.
        const userWrap = document.getElementById("toolboxPanelUser");
        const toolboxPanel = document.getElementById("toolboxPanel");
        if (userWrap) userWrap.appendChild(btn);
        if (toolboxPanel) toolboxPanel.style.display = "";
      } else {
        listEl.appendChild(btn);
      }
    });
    // Fallback: staticky blok, jehoz "beforeId" tlacitko uz v teto skupine
    // neni (uzivatel ho odsud pretahl jinam) - pripoj na konec teto
    // skupiny, aby nezustal osirely mimo jakoukoli skupinu.
    TOOLS_MENU_STATIC_BLOCKS.forEach(block => {
      if (block.groupId === g.id && !staticBlocksPlaced.has(block.id)) {
        const blockEl = document.getElementById(block.id);
        if (blockEl) { listEl.appendChild(blockEl); staticBlocksPlaced.add(block.id); }
      }
    });
  });
  window.addEventListener("resize", () => {
    TOOLS_MENU_BUTTON_IDS.forEach(id => {
      const btn = document.getElementById(id);
      if (btn && btn.classList.contains("toolFloatingBtn")) clampFloatingButtonToViewport(btn);
    });
  });
})();

(function setupEnvReturnToMenuBtn() {
  try {
    const returnBtn = document.getElementById("envReturnToMenuBtn");
    if (!returnBtn) return;
    returnBtn.addEventListener("click", (e) => {
      e.preventDefault(); e.stopPropagation();
      const wrap = document.getElementById("envColorStripWrap");
      if (!wrap || !wrap.classList.contains("toolFloatingBtn")) return;
      // Vrat do jeho vlastni vychozi skupiny ("Barvy a prostředí"), ne
      // vzdy do prvni skupiny - primy klik nema (na rozdil od tazeni)
      // zadnou pozici kurzoru, ze ktere by se cilova skupina dala odvodit.
      const defaultGroup = TOOLS_MENU_DEFAULT_GROUPS.find(g => g.buttonIds.includes("envColorStripWrap"));
      const listEl = defaultGroup && document.querySelector(`.tools-menu-group[data-group-id="${defaultGroup.id}"] .tools-menu-group-list`);
      returnToolButtonToMenu(wrap, listEl || null);
    });
  } catch (e) { /* tlacitko neni kriticke */ }
})();

// Robert 2026-08-08 ("udelej sbalitené jako jsou ostatni prvky ve scene"):
// stejny fly-to-tab vzor jako setupAxisMovePanelToggle/setupMovePanelToggle
// atd. vyse - jen kdyz je box PLOVOUCI (viz CSS .toolFloatingBtn#envColorStripWrap.collapsed).
// Na rozdil od tech panelu NEVOLAME makePanelDraggable na samotny panel -
// envColorStripWrap uz ma svuj VLASTNI presun (makeToolButtonRelocatable,
// tazeni za cely box mimo ovladaci prvky), dalsi drag-listener na stejnem
// elementu by se s nim bil. Tab (envColorStripWrapTab) zadny vlastni drag
// jeste nema, tomu se makeTabVerticallyDraggable prida stejne jako u
// ostatnich. Sbaleni se ZAMERNE nepersistuje (na rozdil od ostatnich
// panelu) - plovouci/dokovany stav uz sam o sobe persistuje pres
// loadToolsMenuLayout, pridavat druhou nezavislou vrstvu ulozeneho stavu
// jen pro tenhle jeden panel by nestalo za slozitost, po nacteni stranky
// tak panel vzdy zacina rozbaleny.
(function setupEnvColorPanelToggle() {
  const panel = document.getElementById("envColorStripWrap");
  const tab = document.getElementById("envColorStripWrapTab");
  const collapseBtn = document.getElementById("envColorCollapseBtn");
  if (!panel || !tab || !collapseBtn) return;

  function setCollapsed(collapsed) {
    panel.classList.toggle("collapsed", collapsed);
    tab.classList.toggle("visible", collapsed);
  }

  collapseBtn.onclick = () => setCollapsed(true);
  tab.onclick = () => {
    if (tab._justDragged) { tab._justDragged = false; return; }
    setCollapsed(false);
  };
  makeTabVerticallyDraggable(tab, "envColorStripWrapTabTop", { skipDropRepositioning: true });
})();

(function setupCameraPanelToggle() {
  const panel = document.getElementById("cameraPanel");
  const tab = document.getElementById("cameraTab");
  const collapseBtn = document.getElementById("cameraCollapseBtn");
  if (!panel || !tab || !collapseBtn) return;
  const STORAGE_KEY = "cameraPanelCollapsed";
  // Robert 2026-08-06 ("udělej totéž s ostatními tlačítky" - viz fwShapesTab
  // vyse): skipDropRepositioning vypne magnet+kolizni repozici po pusteni
  // mysi, tab zustane presne tam, kam ho uzivatel pustil.

  function setCollapsed(collapsed) {
    panel.classList.toggle("collapsed", collapsed);
    tab.classList.toggle("visible", collapsed);
    try { localStorage.setItem(STORAGE_KEY, collapsed ? "1" : "0"); } catch (e) {}
  }

  collapseBtn.onclick = () => setCollapsed(true);
  tab.onclick = () => {
    if (tab._justDragged) { tab._justDragged = false; return; }
    setCollapsed(false);
  };
  makeTabVerticallyDraggable(tab, STORAGE_KEY + "TabTop", { skipDropRepositioning: true });
  makePanelDraggable(panel, document.getElementById(panel.id + "Header"), STORAGE_KEY + "Pos");

  let startCollapsed = true;
  try { const saved = localStorage.getItem(STORAGE_KEY); if (saved !== null) startCollapsed = saved === "1"; } catch (e) {}
  setCollapsed(startCollapsed);
})();

// DULEZITE: musi byt deklarovano PRED prvnim volanim animate() nize - "let"
// promenna pouzita v updateDimLabelPositions() driv, nez by se k tomuto
// radku dostalo normalni poradi skriptu, by shodila cely zbytek <script>
// bloku (ReferenceError: Cannot access before initialization) - presne tenhle
// bug zpusobil, ze se nedaly vkladat zadne dily (vsechno pripojovani tlacitek
// za timto bodem v souboru se uz nikdy nestihlo spustit).
let dimLabelEntries = []; // [{entry, el}]
// bot1 2026-07-28 HOTFIX: tyhle promenne MUSI byt deklarovane driv nez
// animate() nize (viz komentar u puvodni definice dale v souboru) -
// updateConnectionMarkerPositions() se z animate() vola uz pri prvnim
// synchronnim behu.
const CONNECTION_MARKER_REVEAL_PX = 240; // vzdalenost na obrazovce (px), ve ktere se znacka odkryje
let cachedMarkerGroups = [];
let connectionMarkerEntries = []; // { el }
let connectionMarkerSubEl = null; // aktualne otevrene "vice moznosti" okenko
let lastMouseClientX = null, lastMouseClientY = null;
let partNumberEntries = []; // [{entry, el}] - stejny mechanismus jako dimLabelEntries, viz komentar vyse
// Robert 2026-08-16: STEJNY bug jako komentar vyse popisuje (uz se stal
// jednou, zpusobilo to "nedaji se vkladat zadne dily") - dimPairLabelEntries/
// freeConnDiagDimLabelEntries se ctou z updateDimPairLabelPositions()/
// updateFreeConnDiagDimLabelPositions(), obe volane z animate() uz pri
// prvnim synchronnim behu (animate() se vola primo, ne jen pres
// requestAnimationFrame) - MUSI byt deklarovane driv nez animate() nize.
let dimMode = 1;
let dimPairLabelEntries = [];
let freeConnDiagDimLabelEntries = [];
// Robert 2026-08-16 ("updateLiveTechnicalDimensions selhalo... can't
// access lexical declaration 'liveDimCanvas'"): STEJNY bug, tentokrat
// uz PREDCHOZI (ne dnes pridany) - ensureLiveDimCanvas()/
// updateLiveTechnicalDimensions() se taky volaji z animate() uz pri
// prvnim synchronnim behu. Puvodni deklarace byla az ~17828 (daleko za
// animate()) - presunuto sem.
let liveDimCanvas = null, liveDimCtx = null;
// Robert 2026-08-16 ("nech verze 3 kotuje i prurez profilu ve 2D
// pohledech") - dalsi popisky navic k delkovym (dimLabelEntries), jen
// pro profily, jen rezim 3 + 2D pohled - viz refreshDimLabels/
// updateCrossSectionLabelPositions.
let crossSectionLabelEntries = []; // { entry, el }
// Robert 2026-08-16 ("Vrtaci koty... budou se zobrazovat samostatne") -
// nezavisly prepinac, viz computeDrillingDimensionSegments/
// refreshDrillingDimLabels.
let drillingDimsEnabled = false;
let drillingDimLabelEntries = []; // { el, worldPoint }
// Robert 2026-08-22 ("zatrzitko aktivni/neaktivni... pro tyto koty zadnich
// a bocnich dveri") - nezavisly prepinac stejneho vzoru jako drillingDimsEnabled,
// vychozi ZAPNUTO (na rozdil od vrtacich kot) - dvere karoserie jsou hlavni
// duvod, proc tenhle cely mechanismus vznikl.
let carBodyDoorDimsEnabled = true;
// Robert 2026-08-16 ("u kazde koty mi dej zatrzitko, aktivni zatrzitko =
// nepatri tam") - stejny TDZ duvod jako komentare vyse: syncDimIssueCheckboxes()
// se vola z updateLiveTechnicalDimensions(), ktera bezi z animate() uz pri
// prvnim synchronnim behu.
let dimIssueReviewOn = false;
let dimIssueContainerEl = null;
let dimIssuePanelEl = null;
let dimIssueCheckboxEls = new Map(); // id -> <input type=checkbox>
let dimIssueChecked = new Map();     // id -> boolean (prezije pretvoreni checkboxu mezi snimky)
// Robert 2026-08-22 ("koty zadnich dveří... udelejme to ze je mohu ve
// vodorovne posunout") - stejny TDZ duvod jako komentar vyse (musi
// existovat pred prvnim synchronnim behem animate()).
let carBodyDoorFlipContainerEl = null;
let carBodyDoorFlipBtnEls = new Map(); // groupKey -> button el
// Robert 2026-08-22 ("posuvník průhlednosti karoserie... při plné
// průhlednosti schovat, aby nezatěžovala CPU") - stejny TDZ duvod jako
// komentare vyse (applyCarBodyOpacity/carBodyOpacityWatchdog se voláji
// z updateLiveTechnicalDimensions(), ktera bezi z animate() uz pri prvnim
// synchronnim behu). carBodyOpacityPct: 0 = plne viditelna/nepruhledna
// (vychozi), 100 = plne pruhledna + object3d.visible=false.
let carBodyOpacityPct = 0;
let carBodyOpacityAppliedForCount = -1;
// Robert 2026-09-02 ("udělej mi grid živý model do scény, linky po cca
// 350 mm"): zjednoduseny vzhled karoserie - misto plnych sten jen mrizka
// linek (shader, viz makeCarBodyGridMaterial). Vychozi VYPNUTO (Robert
// 2026-09-02: "kdo ti řekl, že máš předělávat všechny karoserie na grid?"
// - je to VZOREK na vyzadani, ne novy vychozi vzhled), perzistuje se
// (stejny vzor jako toggleCarBodyDoorDims).
let carBodyGridEnabled = false;
// bot8 2026-08-22: PUVODNE "const placed = [];" o par tisic radku nize
// (u "loader = new THREE.GLTFLoader()") - presunuto sem, protoze
// carBodyOn vyse (`carBodyDoorDimsEnabled && placed.length > 0`) je
// PRVNI misto v teto funkci, kde se `placed.length` skutecne vyhodnoti
// i pri prvnim synchronnim behu animate() (na rozdil od puvodniho `on`
// o par radku vyse, ktery se od `placed` chrani jen nahodou - `allow` je
// pri prvnim behu vzdy false, takze && ho zkrati driv, nez se na
// `placed` vubec dojde). Bez presunu tenhle radek spolehlive (ne jen
// obcas) hazel TDZ ReferenceError na uplne prvnim snimku - overeno
// primym A/B testem (git stash) na cistem HEAD vs s touto zmenou.
const placed = [];
// bot10, 2026-09-11 (nalez bot4/bot3: fronta ke schvalovani "ukazuje cizi
// cisla" - detaily viz komentar u clearAll()/insertCustomShape() nize).
// Pocitadlo generaci sceny - kazdy clearAll() ho zvysi, insertCustomShape()
// si na zacatku poznamena, ktera generace bezela PRI JEHO VOLANI, a po
// kazdem async kroku overi, ze porad bezi TATAZ generace - jinak prestane
// vkladat dalsi dily (opustene volani z PREDCHOZI sestavy uz nema co delat
// v AKTUALNI scene). Normalni jednorazove volani (bez mezitimniho
// clearAll()) se timhle chovanim vubec nezmeni - generace se za jeho behu
// nezmeni.
let sceneGeneration = 0;
// Robert 2026-09-13 ("ve scene neni nikde videt ID sestavy nebo karoserie"):
// meta aktualne vlozene sestavy/tvaru pro zobrazeni v pravem panelu (viz
// refreshSummary ve scene.html) - nastavuje insertCustomShape(), maze clearAll().
let currentAssemblyMeta = null; // {id, name} | null
// bot8, 2026-08-17: plovouci 3D popisky (srovnavaci galerie ruznych
// napojovacich funkci, viz insertCustomShape), NEZAVISLE na `placed`
// (nejsou to katalogove dily) - vlastni pole + vlastni cleanup,
// ulozene/nactene pres custom_shapes "text_labels" (viz api/app.py
// _validate_custom_shape_text_labels). PUVODNE deklarovano az u
// createSceneTextLabel() nize - presunuto sem 2026-08-22 ze STEJNEHO
// duvodu jako `placed` vyse (sweepOrphanedCarBodySpecLabels v
// updateLiveTechnicalDimensions je prvni misto, kde by na tuhle
// promennou dosel prvni synchronni beh animate()).
const sceneTextLabels = [];
// Robert 2026-08-22 ("režim... kdy jakýkoli předmět prolne karoserii,
// tato zčervená") - vychozi VYPNUTO (na rozdil od kot/pruhlednosti -
// tenhle vypocet je narocnejsi, netreba ho platit, kdyz o nej Robert
// zrovna nestoji). carBodyCollisionFrameCounter - viz throttle v
// checkCarBodyCollisions (nebezi kazdy snimek, jen kazdy N-ty).
let carBodyCollisionEnabled = false;
let carBodyCollisionFrameCounter = 0;
// Robert 2026-08-22 ("pokracuj tou kolizi karoserie s profilem"):
// zvyrazni cerveni i SAMOTNY kolidujici dil (ne jen steny karoserie) -
// pri vice dilech v sestave jinak neni na prvni pohled jasne, KTERY
// dil je puvodce kolize. Sleduje entries aktualne obarvene kvuli
// kolizi (viz checkCarBodyCollisions), aby sla barva spolehlive vratit
// i kdyz dil mezitim prestal kolidovat.
let carBodyCollisionFlaggedParts = new Set();

// Robert 2026-08-08 ("zobrazujme male osy, kříž uprostřed nahoře ať víme
// jak se natáčí prostor"): samostatna mini THREE.js scena/kamera/renderer
// (vlastni maly canvas, viz #orientationGizmoCanvas) - obsahuje jen
// THREE.AxesHelper v pocatku. gizmoCamera KAZDY snimek prevezme jen
// SMER pohledu hlavni kamery (ne pozici/zoom/target), takze gizmo vzdy
// ukazuje aktualni natoceni sceny, at uzivatel scenu jakkoli otoci/oddali.
const orientationGizmoScene = new THREE.Scene();
const orientationGizmoCamera = new THREE.PerspectiveCamera(45, 1, 0.1, 10);
const orientationGizmoCanvasEl = document.getElementById("orientationGizmoCanvas");
const orientationGizmoRenderer = new THREE.WebGLRenderer({ canvas: orientationGizmoCanvasEl, alpha: true, antialias: true });
orientationGizmoRenderer.setSize(64, 64, false);
orientationGizmoScene.add(new THREE.AxesHelper(1));
const ogzLabelEls = { x: document.getElementById("ogzLabelX"), y: document.getElementById("ogzLabelY"), z: document.getElementById("ogzLabelZ") };
const ogzTmpDir = new THREE.Vector3();
const ogzTmpPt = new THREE.Vector3();

function renderOrientationGizmo() {
  camera.getWorldDirection(ogzTmpDir);
  // Robert 2026-08-08 ("Y neni videt") - puvodni vzdalenost/delka popisku
  // (2.4 / 1.35) byla moc tesna: pri natoceni, kdy nektera osa smeruje
  // skoro presne "nahoru/dolu" na obrazovce (typicky prave Y), jeji
  // popisek vyjde MIMO zorne pole gizmo-kamery (NDC > 1) a je neviditelny.
  // 3.8 / 1.2 dava dostatecnou rezervu i v tomhle nejhorsim pripade
  // (viz vypocet v AGENTS_LOG) + jeste navic tvrdy clamp pod smyckou.
  orientationGizmoCamera.position.copy(ogzTmpDir).multiplyScalar(-3.8);
  orientationGizmoCamera.up.copy(camera.up);
  orientationGizmoCamera.lookAt(0, 0, 0);
  orientationGizmoRenderer.render(orientationGizmoScene, orientationGizmoCamera);
  ["x", "y", "z"].forEach((axis, i) => {
    ogzTmpPt.set(i === 0 ? 1.2 : 0, i === 1 ? 1.2 : 0, i === 2 ? 1.2 : 0).project(orientationGizmoCamera);
    const px = (ogzTmpPt.x * 0.5 + 0.5) * 64;
    const py = (-ogzTmpPt.y * 0.5 + 0.5) * 64;
    // Tvrdy clamp jako pojistka (i kdyby vypocet vyse nekdy nestacil) -
    // popisek at zustane vzdy nekde uvnitr/na okraji viditelneho boxu,
    // misto aby uplne zmizel mimo nej.
    ogzLabelEls[axis].style.left = Math.max(4, Math.min(60, px)) + "px";
    ogzLabelEls[axis].style.top = Math.max(4, Math.min(60, py)) + "px";
  });
}

// Robert 2026-08-08 ("zobrazujme nějak náznakově i osy vcetne písmena u
// označených produktů"): PER-DIL orientacni krizek pro aktualne oznacene
// dily (viz setSelectHighlight nize) - skutecny 3D THREE.AxesHelper primo
// ve scene (ne dite object3d, aby ho nedeformovalo pripadne nerovnomerne
// protazeni entry.object3d.scale - pozice/rotace se kopiruje rucne kazdy
// snimek), pismena X/Y/Z jako 2D DOM-overlay (stejny princip jako cisla
// dilu, viz updatePartNumberPositions).
const partAxisHelpers = new Map(); // entry -> { helper, axisLen, labelEls:{x,y,z} }

function addPartAxisIndicator(entry) {
  if (partAxisHelpers.has(entry)) return;
  entry.object3d.updateMatrixWorld(true);
  const box = new THREE.Box3().setFromObject(entry.object3d);
  const size = box.getSize(new THREE.Vector3());
  const axisLen = Math.max(Math.min(size.x, size.y, size.z) * 0.7, 40);
  const helper = new THREE.AxesHelper(axisLen);
  helper.renderOrder = 999;
  scene.add(helper);
  const container = document.getElementById("partAxisLabels");
  const labelEls = {};
  ["x", "y", "z"].forEach(axis => {
    const el = document.createElement("div");
    el.className = "part-axis-label part-axis-label-" + axis;
    el.textContent = axis.toUpperCase();
    container.appendChild(el);
    labelEls[axis] = el;
  });
  partAxisHelpers.set(entry, { helper, axisLen, labelEls });
}

function removePartAxisIndicator(entry) {
  const rec = partAxisHelpers.get(entry);
  if (!rec) return;
  scene.remove(rec.helper);
  if (rec.helper.geometry) rec.helper.geometry.dispose();
  if (rec.helper.material) rec.helper.material.dispose();
  Object.values(rec.labelEls).forEach(el => el.remove());
  partAxisHelpers.delete(entry);
}

const partAxisTmpDir = new THREE.Vector3();
const partAxisTmpCenter = new THREE.Vector3();
function updatePartAxisIndicators() {
  if (!partAxisHelpers.size) return;
  const rect = renderer.domElement.getBoundingClientRect();
  partAxisHelpers.forEach((rec, entry) => {
    // Dil mezitim mohl byt smazan (Delete/Odebrat/Vycistit) bez explicitniho
    // odoznaceni - lazy uklid tady je spolehlivejsi nez spolehat na to, ze
    // kazde jedno misto v kodu, ktere maze z `placed`, taky volalo
    // setSelectHighlight(entry, false).
    if (!placed.includes(entry)) { removePartAxisIndicator(entry); return; }
    entry.object3d.updateMatrixWorld(true);
    const box = new THREE.Box3().setFromObject(entry.object3d);
    partAxisTmpCenter.copy(box.getCenter(partAxisTmpCenter));
    rec.helper.position.copy(partAxisTmpCenter);
    rec.helper.quaternion.copy(entry.object3d.quaternion);
    ["x", "y", "z"].forEach((axis, i) => {
      partAxisTmpDir.set(i === 0 ? 1 : 0, i === 1 ? 1 : 0, i === 2 ? 1 : 0)
        .applyQuaternion(entry.object3d.quaternion)
        .multiplyScalar(rec.axisLen * 1.2)
        .add(partAxisTmpCenter);
      const ndc = partAxisTmpDir.clone().project(camera);
      const el = rec.labelEls[axis];
      if (ndc.z < -1 || ndc.z > 1) { el.style.display = "none"; return; }
      el.style.display = "block";
      el.style.left = ((ndc.x * 0.5 + 0.5) * rect.width) + "px";
      el.style.top = ((-ndc.y * 0.5 + 0.5) * rect.height) + "px";
    });
  });
}

// Robert 2026-08-08 ("musí být dobře vidět střed všech os ve scéně"):
// TRVALY indikator pocatku souradnic (0,0,0), na rozdil od per-dil
// verze vyse (addPartAxisIndicator) neni vazany na oznaceni - je videt
// porad, stejny princip (skutecny 3D THREE.AxesHelper + 2D DOM-overlay
// pismena X/Y/Z), jen staticky (zadna rotace/pozice se neposouva,
// pocitaji se jen 2D souradnice popisku kazdy snimek).
const ORIGIN_AXIS_LEN = 150;
const originAxisHelper = new THREE.AxesHelper(ORIGIN_AXIS_LEN);
originAxisHelper.renderOrder = 998;
scene.add(originAxisHelper);
const originAxisLabelEls = {};
(function initOriginAxisLabels() {
  const container = document.getElementById("partAxisLabels");
  ["x", "y", "z"].forEach(axis => {
    const el = document.createElement("div");
    el.className = "part-axis-label part-axis-label-" + axis;
    el.textContent = axis.toUpperCase();
    container.appendChild(el);
    originAxisLabelEls[axis] = el;
  });
})();
const originAxisTmpPt = new THREE.Vector3();
// Robert 2026-08-11 ("pri funkci Kontrola ploch odstran stredovy kriz os,
// po ukonceni funkce jej zobraz zpet"): kriz v pocatku prekryva zkoumany
// dil a plete se s barevnymi sipkami ploch. Skryva se i s popisky X/Y/Z.
function setOriginAxisVisible(v) {
  originAxisHelper.visible = v;
  ["x", "y", "z"].forEach(axis => {
    const el = originAxisLabelEls[axis];
    if (el) el.style.display = v ? "block" : "none";
  });
}
function updateOriginAxisIndicator() {
  if (!originAxisHelper.visible) return;   // skryty kriz nema co polohovat
  const rect = renderer.domElement.getBoundingClientRect();
  ["x", "y", "z"].forEach((axis, i) => {
    originAxisTmpPt.set(i === 0 ? 1 : 0, i === 1 ? 1 : 0, i === 2 ? 1 : 0).multiplyScalar(ORIGIN_AXIS_LEN * 1.2);
    const ndc = originAxisTmpPt.clone().project(camera);
    const el = originAxisLabelEls[axis];
    if (ndc.z < -1 || ndc.z > 1) { el.style.display = "none"; return; }
    el.style.display = "block";
    el.style.left = ((ndc.x * 0.5 + 0.5) * rect.width) + "px";
    el.style.top = ((-ndc.y * 0.5 + 0.5) * rect.height) + "px";
  });
}

// Robert 2026-08-08 ("vlevo dole zobrazujme reálné průřezy profilů
// které jsou zrovna označené. pixely cca 200x200, ale čistě jen ty
// čela bez těla profilu"): profilové GLB modely jsou otevřené "trubky"
// (jen boční stěny vytažené po délce, BEZ čelních uzavíracích plošek -
// koncové čelo se v běžném provozu nikdy nevidí, díly se spojují konec
// na konec). Pohled kamerou přesně podél délkové osy proto na takové
// geometrii nic nevykreslí (boční stěny jsou z tohoto úhlu vidět přesně
// z hrany = nulová plocha). Skutečný tvar čela se místo toho REKONSTRUUJE
// přímo z site: najdou se hraniční hrany (hrana použitá jen jedním
// trojúhelníkem) ležící v rovině jednoho konce profilu, poskládají se do
// uzavřené smyčky a ta se vykreslí jako 2D výplň na obyčejném <canvas>
// (fill-rule "evenodd" automaticky zvládne i vnitřní dutiny profilu jako
// díru). GLB export duplikuje vrcholy na hranách (ostré normály pro flat
// shading), takže hranice se nejdřív musí "sešít" podle zaokrouhlené
// světové pozice (0.05mm), jinak by hraniční hrany zůstaly v indexovém
// prostoru nespojité (degree 1 místo 2) a smyčku by nešlo projít.
function extractProfileEndLoops(entry) {
  const axis = profileLengthAxisWorld(entry);
  if (!axis) return null;
  let mesh = null;
  entry.object3d.traverse(n => { if (n.isMesh && !mesh) mesh = n; });
  if (!mesh || !mesh.geometry.index) return null;
  mesh.updateMatrixWorld(true);

  const posAttr = mesh.geometry.attributes.position;
  const idx = mesh.geometry.index;
  const vCount = posAttr.count;
  const worldPts = [];
  const tmp = new THREE.Vector3();
  for (let i = 0; i < vCount; i++) {
    tmp.fromBufferAttribute(posAttr, i);
    mesh.localToWorld(tmp);
    worldPts.push(tmp.clone());
  }

  const keyOf = p => Math.round(p.x * 20) + "_" + Math.round(p.y * 20) + "_" + Math.round(p.z * 20);
  const canonicalId = new Map();
  const remap = new Int32Array(vCount);
  for (let i = 0; i < vCount; i++) {
    const key = keyOf(worldPts[i]);
    if (!canonicalId.has(key)) canonicalId.set(key, i);
    remap[i] = canonicalId.get(key);
  }

  const ts = worldPts.map(p => p.dot(axis));
  const tMin = Math.min(...ts);

  const edgeCount = new Map();
  const triCount = idx.count / 3;
  for (let t = 0; t < triCount; t++) {
    const a = remap[idx.getX(t * 3)], b = remap[idx.getX(t * 3 + 1)], c = remap[idx.getX(t * 3 + 2)];
    [[a, b], [b, c], [c, a]].forEach(([p1, p2]) => {
      if (p1 === p2) return;
      const key = p1 < p2 ? p1 + "_" + p2 : p2 + "_" + p1;
      const rec = edgeCount.get(key);
      if (rec) rec.count++; else edgeCount.set(key, { count: 1, a: p1, b: p2 });
    });
  }
  const EPS = 1.0;
  const adjacency = new Map();
  edgeCount.forEach(rec => {
    if (rec.count !== 1) return;
    if (Math.abs(ts[rec.a] - tMin) >= EPS || Math.abs(ts[rec.b] - tMin) >= EPS) return;
    if (!adjacency.has(rec.a)) adjacency.set(rec.a, []);
    if (!adjacency.has(rec.b)) adjacency.set(rec.b, []);
    adjacency.get(rec.a).push(rec.b);
    adjacency.get(rec.b).push(rec.a);
  });
  if (!adjacency.size) return null;

  const refUp = Math.abs(axis.y) > 0.9 ? new THREE.Vector3(1, 0, 0) : new THREE.Vector3(0, 1, 0);
  const uAxis = new THREE.Vector3().crossVectors(refUp, axis).normalize();
  const vAxis = new THREE.Vector3().crossVectors(axis, uAxis).normalize();

  function traceLoop(startIdx, visited) {
    const loop = [startIdx];
    visited.add(startIdx);
    let prev = null, cur = startIdx;
    while (true) {
      const neighbors = adjacency.get(cur) || [];
      const next = neighbors.find(nb => nb !== prev);
      if (next == null || next === startIdx) break;
      if (visited.has(next)) break;
      visited.add(next);
      loop.push(next);
      prev = cur; cur = next;
    }
    return loop;
  }

  const visited = new Set();
  const loops = [];
  adjacency.forEach((_, startIdx) => {
    if (visited.has(startIdx)) return;
    const loop = traceLoop(startIdx, visited);
    if (loop.length >= 3) loops.push(loop);
  });
  if (!loops.length) return null;

  return loops.map(loop => loop.map(i => {
    const p = worldPts[i];
    return { x: p.dot(uAxis), y: p.dot(vAxis) };
  }));
}

// bot7 2026-08-08 (Robert po 120px: "tak to zase vraťme to je už moc
// male" - zpet na 175px, JPEG kvalita 0.92 beze zmeny).
const CROSS_SECTION_THUMB_PX = 175;

function renderCrossSectionThumb(entry) {
  const loops2d = extractProfileEndLoops(entry);
  if (!loops2d) return null;

  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  loops2d.forEach(loop => loop.forEach(p => {
    minX = Math.min(minX, p.x); maxX = Math.max(maxX, p.x);
    minY = Math.min(minY, p.y); maxY = Math.max(maxY, p.y);
  }));
  const cx = (minX + maxX) / 2, cy = (minY + maxY) / 2;
  const S = CROSS_SECTION_THUMB_PX;
  const scale = (S * 0.85) / Math.max(maxX - minX, maxY - minY, 1);

  const canvas = document.createElement("canvas");
  canvas.width = S; canvas.height = S;
  const ctx = canvas.getContext("2d");
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, S, S);

  let mesh = null;
  entry.object3d.traverse(n => { if (n.isMesh && !mesh) mesh = n; });
  const colorHex = (mesh && mesh.material && mesh.material.color) ? "#" + mesh.material.color.getHexString() : "#8a95a8";

  ctx.beginPath();
  loops2d.forEach(loop => {
    loop.forEach((p, i) => {
      const px = (p.x - cx) * scale + S / 2;
      const py = S / 2 - (p.y - cy) * scale;
      if (i === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py);
    });
    ctx.closePath();
  });
  ctx.fillStyle = colorHex;
  ctx.fill("evenodd");
  ctx.strokeStyle = "#333944";
  ctx.lineWidth = 1.5;
  ctx.stroke();

  return canvas.toDataURL("image/jpeg", 0.92);
}

// bot7 2026-08-08 (Robert: "ty náhledy čel profilů orezat nech je mezera
// vnejsi minimalni" + "přeformatuj... nemusí mít tak velké rozlišení, a
// zmenši pixelu na 150x150"): drivejsi CSS-only orez (proste ukazal levou
// polovinu "combined" Dogus obrazku) nechaval velky bily okraj kolem
// samotneho nakresu, protoze ta polovina ma vlastni vycpavku. Misto toho
// se obrazek analyzuje na canvasu (server posila Access-Control-Allow-
// -Origin: *, takze getImageData nehodi "tainted canvas" chybu) - najde se
// bounding box NEBILYCH pixelu uvnitr leve poloviny (= samotny nakres bez
// fotky vpravo), s malou rezervou domalo, a presne tenhle vyrez se
// prekresli zvetseny na vystupni 150x150 JPEG (mensi soubor nez PNG pro
// tenhle typ obsahu = "jiny format, mensi rozliseni"). Vysledek se
// cachuje podle URL, protoze se stejny profil casto vybira/odvybira znovu.
const dogusCrossSectionCropCache = new Map(); // url -> Promise<string|null>

function computeDogusCrossSectionCrop(url) {
  if (dogusCrossSectionCropCache.has(url)) return dogusCrossSectionCropCache.get(url);
  const promise = new Promise(resolve => {
    const img = new Image();
    img.crossOrigin = "anonymous";
    img.onload = () => {
      try {
        const iw = img.naturalWidth, ih = img.naturalHeight;
        const srcCanvas = document.createElement("canvas");
        srcCanvas.width = iw; srcCanvas.height = ih;
        const sctx = srcCanvas.getContext("2d");
        sctx.drawImage(img, 0, 0);
        const halfW = Math.floor(iw * 0.5);
        const data = sctx.getImageData(0, 0, halfW, ih).data;
        const THRESH = 245;
        let minX = halfW, minY = ih, maxX = 0, maxY = 0, found = false;
        for (let y = 0; y < ih; y++) {
          for (let x = 0; x < halfW; x++) {
            const i = (y * halfW + x) * 4;
            if (data[i] < THRESH || data[i + 1] < THRESH || data[i + 2] < THRESH) {
              found = true;
              if (x < minX) minX = x;
              if (x > maxX) maxX = x;
              if (y < minY) minY = y;
              if (y > maxY) maxY = y;
            }
          }
        }
        if (!found) { resolve(null); return; }
        const padX = Math.max(3, (maxX - minX) * 0.05);
        const padY = Math.max(3, (maxY - minY) * 0.05);
        minX = Math.max(0, minX - padX); maxX = Math.min(halfW, maxX + padX);
        minY = Math.max(0, minY - padY); maxY = Math.min(ih, maxY + padY);
        const cropW = maxX - minX, cropH = maxY - minY;

        const S = CROSS_SECTION_THUMB_PX;
        const outCanvas = document.createElement("canvas");
        outCanvas.width = S; outCanvas.height = S;
        const octx = outCanvas.getContext("2d");
        octx.fillStyle = "#ffffff";
        octx.fillRect(0, 0, S, S);
        const scale = Math.min(S / cropW, S / cropH);
        const dw = cropW * scale, dh = cropH * scale;
        octx.drawImage(srcCanvas, minX, minY, cropW, cropH, (S - dw) / 2, (S - dh) / 2, dw, dh);
        resolve(outCanvas.toDataURL("image/jpeg", 0.92));
      } catch (e) {
        resolve(null); // CORS/taint nebo jina chyba -> volajici spadne na neorizly obrazek
      }
    };
    img.onerror = () => resolve(null);
    img.src = url;
  });
  dogusCrossSectionCropCache.set(url, promise);
  return promise;
}

let crossSectionPanelSeq = 0;

async function refreshCrossSectionPanel() {
  const panel = document.getElementById("crossSectionPanel");
  if (!panel) return;
  const entries = Array.from(currentJoinSelectionUnion()).filter(e => isProfilePart(e.part));
  const seen = new Set();
  const distinct = [];
  entries.forEach(e => {
    if (seen.has(e.part.id)) return;
    seen.add(e.part.id);
    distinct.push(e);
  });
  if (!distinct.length) {
    panel.innerHTML = "";
    panel.classList.remove("open");
    return;
  }

  // bot7 2026-08-08: orez dogus obrazku je asynchronni (nacteni Image()) -
  // seq guard zajisti, ze rychle po sobe jdouci zmeny vyberu neprepisi
  // panel POZDEJI dorazivsim vysledkem ze STARSIHO volani.
  const mySeq = ++crossSectionPanelSeq;
  const results = await Promise.all(distinct.map(async entry => {
    // bot7 2026-08-08: prednostne skutecny technicky nakres z Dogusu -
    // jde o REALNY prurez dane vyroby, ne o priblizny model. Vypocitana
    // GLB silueta (renderCrossSectionThumb) je jen fallback pro profily,
    // ktere jeste nemaji dogus parovani (viz sql/2026-08-08_dogus_pairing.sql).
    let src = null;
    if (entry.part.dogus_image_schema_url) {
      src = await computeDogusCrossSectionCrop(entry.part.dogus_image_schema_url);
      if (!src) src = entry.part.dogus_image_schema_url; // orez selhal -> aspon neorizly original
    } else {
      src = renderCrossSectionThumb(entry);
    }
    return { entry, src };
  }));
  if (crossSectionPanelSeq !== mySeq) return;

  panel.innerHTML = "";
  results.forEach(({ entry, src }) => {
    if (!src) return;
    const card = document.createElement("div");
    card.className = "cross-section-card";
    const img = document.createElement("img");
    img.src = src;
    img.alt = entry.part.name;
    const cross = (entry.part.cross_section_mm && entry.part.cross_section_mm[0] != null) ? entry.part.cross_section_mm : null;
    const label = document.createElement("span");
    label.textContent = entry.part.name + (cross ? ` (${Math.round(cross[0])}×${Math.round(cross[1])} mm)` : "");
    card.appendChild(img);
    card.appendChild(label);
    panel.appendChild(card);
  });
  panel.classList.add("open");
}

// Robert ("flashuje ale cela scena, ne jen tlacitka") - po 3 predchozich
// pokusech (schovavani <canvas> pres visibility, schovavani jednotlivych
// DOM prekryvovych vrstev) porad neco probleskavalo. Duvod: schovani
// canvasu/vrstev NEBRANI animate() smycce (bezi porad na pozadi kazdy
// snimek pres requestAnimationFrame) v tom, aby dal pocitala a
// VYKRESLOVALA aktualni (docasne zmeneny) stav scene/camera - u
// prohlizecu/GPU driveru, kde neni vizibilita canvasu 100% synchronni se
// skutecnym momentem kompozitu snimku, muze i jen jeden takovy mezikrok
// probleknout. Misto spolehani na "schovej a doufej" ted CELA animate()
// smycka behem generovani nahledu (viz suppressMainRender nize) NEBEZI
// VUBEC - viewport tak zustane cely tu dobu zamrzly na poslednim
// spravnem snimku, naprosto beze zmeny, misto aby se cokoliv prekreslovalo.
let suppressMainRender = false;
// Stav ovladace dosahu magnetu (viz sekce "Dosah magnetu" o ~7,5k radku
// nize, kde je zbytek logiky). Deklarace MUSI byt tady, pred animate():
// animate() se vola synchronne hned pod svou definici a jeho prvni snimek
// vola refreshMagnetReachSpheres(), ktera cte magnetReachVisible - s
// puvodni deklaraci az dole to byl TDZ ReferenceError na kazdem nacteni
// stranky (console.error "refreshMagnetReachSpheres selhalo", bot5 e2e /
// bot3 revize 2026-09-02).
let magnetReachVisible = false;
try { magnetReachVisible = localStorage.getItem("konfMagnetReachVisible") === "1"; } catch (e) { /* ignoruj */ }
const magnetReachSpheres = []; // {mesh, accEntry}
let magnetReachDragState = null; // {plane, startRadius}
function animate(){
  requestAnimationFrame(animate);
  if (suppressMainRender) return;
  controls.update();
  renderer.render(scene, camera);
  // Robert 2026-07-25 (panel Kamera - ted plovouci/roztahovatelne okenko
  // misto deleni platna): pokud bezi kamerovy přelet, dokresli navic jeste
  // stream do samostatneho okenka (vlastni 2. renderer) - viz
  // renderCameraStream nize. typeof guard, protoze je definovana az v
  // pozdejsim bloku skriptu (na uplne prvni synchronni volani animate()
  // jeste nemusi existovat).
  if (typeof cameraOrbitActive !== "undefined" && cameraOrbitActive &&
      typeof renderCameraStream === "function") {
    renderCameraStream();
  }
  updateDimLabelPositions();
  if (typeof updateCrossSectionLabelPositions === "function") updateCrossSectionLabelPositions();
  if (typeof updateDimPairLabelPositions === "function") updateDimPairLabelPositions();
  if (typeof updateDrillingDimLabelPositions === "function") updateDrillingDimLabelPositions();
  if (typeof updateFreeConnDiagDimLabelPositions === "function") updateFreeConnDiagDimLabelPositions();
  updatePartNumberPositions();
  renderOrientationGizmo();
  updateOriginAxisIndicator();
  updatePartAxisIndicators();
  try {
    if (typeof updateConnectionMarkerPositions === "function") updateConnectionMarkerPositions();
  } catch (e) {
    console.error("updateConnectionMarkerPositions selhalo (nezastavuje zbytek appky):", e);
  }
  try {
    if (typeof refreshRotateHandle === "function") refreshRotateHandle();
  } catch (e) {
    console.error("refreshRotateHandle selhalo (nezastavuje zbytek appky):", e);
  }
  try {
    if (typeof refreshRotateAxisCornerPreview === "function") refreshRotateAxisCornerPreview();
  } catch (e) {
    console.error("refreshRotateAxisCornerPreview selhalo (nezastavuje zbytek appky):", e);
  }
  try {
    if (typeof refreshMagnetReachSpheres === "function") refreshMagnetReachSpheres();
  } catch (e) {
    console.error("refreshMagnetReachSpheres selhalo (nezastavuje zbytek appky):", e);
  }
  try {
    if (typeof updateLiveTechnicalDimensions === "function") updateLiveTechnicalDimensions();
  } catch (e) {
    console.error("updateLiveTechnicalDimensions selhalo (nezastavuje zbytek appky):", e);
  }
  try {
    // Robert 2026-08-22 ("kdy jakýkoli předmět prolne karoserii, tato
    // zčervená") - jen kdyz je zatrzitko zapnute (vychozi VYPNUTO, viz
    // carBodyCollisionEnabled) A jen kazdy COLLISION_CHECK_EVERY_N_FRAMES-ty
    // snimek (drahy raycasting, netreba pocitat kazdy snimek).
    if (carBodyCollisionEnabled && typeof checkCarBodyCollisions === "function") {
      carBodyCollisionFrameCounter++;
      if (carBodyCollisionFrameCounter % COLLISION_CHECK_EVERY_N_FRAMES === 0) checkCarBodyCollisions();
    }
  } catch (e) {
    console.error("checkCarBodyCollisions selhalo (nezastavuje zbytek appky):", e);
  }
}
animate();

// --- katalog dilu -> 3D scena ---
// Kazdy dil ma spocitane 2 "konektory" (body + smerovy vektor) na koncich
// sve nejdelsi osy (u profilu = konce tyce). Konektory se pouzivaji pro
// AI stavitel (viz runAIPlan nize), ktery dily napojuje presne konec-na-konec.
// Rucni tazeni mysi bylo zruseno - novy dil se pri kliknuti v katalogu
// vzdy objevi rovnou na stredu os (0,0,0).
const loader = new THREE.GLTFLoader();
// bot8, 2026-08-17 (Robert: srovnavaci galerie ruznych napojovacich funkci
function createSceneTextLabel(text, worldPos) {
  const canvas = document.createElement("canvas");
  const ctx = canvas.getContext("2d");
  const fontPx = 54;
  ctx.font = `bold ${fontPx}px sans-serif`;
  const lines = String(text).split("\n");
  const textW = Math.max(...lines.map(l => ctx.measureText(l).width));
  const padX = 24, padY = 16, lineH = fontPx * 1.25;
  canvas.width = Math.ceil(textW + padX * 2);
  canvas.height = Math.ceil(lineH * lines.length + padY * 2);
  ctx.font = `bold ${fontPx}px sans-serif`;
  ctx.fillStyle = "rgba(20,22,26,0.85)";
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.strokeStyle = "#ffe033";
  ctx.lineWidth = 4;
  ctx.strokeRect(2, 2, canvas.width - 4, canvas.height - 4);
  ctx.fillStyle = "#ffffff";
  ctx.textBaseline = "top";
  lines.forEach((l, i) => ctx.fillText(l, padX, padY + i * lineH));
  const tex = new THREE.CanvasTexture(canvas);
  tex.minFilter = THREE.LinearFilter;
  const mat = new THREE.SpriteMaterial({ map: tex, depthTest: false, transparent: true });
  const sprite = new THREE.Sprite(mat);
  sprite.renderOrder = 1000;
  // bot8 2026-09-18: puvodni text nikde jinde neprezije (canvas je uz jen
  // vykreslene pixely) - potreba pro "Ulozit opravu tvaru" (scene.html
  // resaveOpenedCustomShape), ktere popisky musi umet serializovat zpet
  // do data.text_labels.
  sprite.userData.text = text;
  // Merítko: sirka sestavy je typicky radove 1000mm, popisek chceme
  // citelny ve stejnem meritku (ne fixni pixelovou velikost obrazovky) -
  // prevadi canvas pixely na mm sceny tak, aby text vysel cca 30mm vysoky
  // na radek (umerne 30-40mm prurezu profilu - puvodnich 220mm/radek bylo
  // OMYLEM 7x moc, popisky vysly pres 2m siroke a zakryly celou sestavu,
  // Robert: "nevidim pres ty cerne tabule").
  const MM_PER_LINE = 30;
  const scale = MM_PER_LINE / lineH;
  sprite.scale.set(canvas.width * scale, canvas.height * scale, 1);
  sprite.position.copy(worldPos);
  scene.add(sprite);
  sceneTextLabels.push(sprite);
  return sprite;
}
function clearSceneTextLabels() {
  sceneTextLabels.forEach(s => { scene.remove(s); s.material.map.dispose(); s.material.dispose(); });
  sceneTextLabels.length = 0;
}
// Robert 2026-08-16 ("na startu naskoci 2D shora ale ve scene je 3D, asi
// pri reloadech kdyz necham 2D") - viz komentar u viewModeSelectEl listeneru
// vyse. `placed` je tu uz bezpecne inicializovane, takze tenhle jednorazovy
// sync muze bezpecne zavolat setViewMode() i pro "top"/"front"/"side"
// (ty pocitaji ram pohledu z bboxOfEntries(placed)). Primo setViewMode()
// (ne applyViewMode()) - ten je soukromy uvnitr predchoziho if-bloku a
// jeho `lastAppliedViewMode` guard by prvni skutecnou zmenu z dropdownu
// zbytecne nekomplikoval; kdyz uzivatel pak sam prepne, applyViewMode()
// prekresli znovu (mode !== null), neskodne.
if (viewModeSelectEl && viewModeSelectEl.value !== "3d") {
  setViewMode(viewModeSelectEl.value);
  renderer.render(scene, camera);
}
let occupiedConnectors = []; // {point:Vector3(world), normal:Vector3(world), owner:entry}
// Vizualni znacky (sipky) na volnych KONCOVYCH konektorech - oranzova = volny
// konec (da se za nej tahat pro protazeni, nebo na nem kliknout pro pridani dalsiho
// dilu), tmava/skryta = konec uz je s necim spojeny. Pole { mesh, entry, connIdx }.
// Sipka (kuzel) misto koule - hrot smeruje ven ve smeru, kam dil "roste"
// (connector normal), 50% pruhlednost, aby nezakryvala geometrii pod sebou.
const endpointMarkers = [];
// Robert 2026-07-24: "šipky oddálit od profilů cca 10 cm, o 20% zvětšit,
// o 30% zprůhlednit a při najetí myší pořádně rozsvítit".
// Robert 2026-07-24: "muzem sipky znovu posunout o 10cm od koncu profilu
// a jeste o 15% zvetsit" - navazuje na puvodni +20% zvetseni.
const ENDPOINT_ARROW_LEN = 28 * 1.2 * 1.15; // +20%, pak jeste +15%
const ENDPOINT_ARROW_RADIUS = 10 * 1.2 * 1.15; // +20%, pak jeste +15%
const endpointMarkerGeom = new THREE.ConeGeometry(ENDPOINT_ARROW_RADIUS, ENDPOINT_ARROW_LEN, 14);
// Robert 2026-07-24: skutecna pricina skoku/vystrelovani nalezena a
// opravena (stale dragState.originalLocalLength pri opakovanem tazeni -
// viz AGENTS_LOG.md), takze odsazeni sipky muze byt zase 100mm jako
// puvodne pozadovano ("sipky oddalit od profilu cca 10 cm").
const ENDPOINT_ARROW_GAP = 100; // mm - mezera mezi koncem profilu a zakladnou sipky
const ENDPOINT_ARROW_COLOR = 0xff9900;
const ENDPOINT_ARROW_OPACITY = 0.5 * 0.7; // -30% (0.5 -> 0.35)
const ENDPOINT_ARROW_HOVER_COLOR = 0xffdd55; // vyrazne svetlejsi/zarivejsi oranzova
const ENDPOINT_ARROW_HOVER_OPACITY = 1;
const ENDPOINT_ARROW_HOVER_SCALE = 1.3;

// Robert 2026-07-24: "vsechny zavrene tvary je vhodne mit moznost
// natahnout" - sipky pro natazeni CELEHO uzavreneho tvaru (Ctverec/rám):
// odlisna (modra) barva od bezmych oranzovych "protahovacich" sipek
// jednotlivych volnych koncu, aby uzivatel na prvni pohled poznal rozdil
// (tahle sipka meni rozmer cele sestavy, ne jen jednoho dilu).
const FRAME_HANDLE_COLOR = 0x4db8ff;
const FRAME_HANDLE_HOVER_COLOR = 0x8fd6ff;
const FRAME_HANDLE_OPACITY = 0.6;
const FRAME_HANDLE_HOVER_OPACITY = 1;
const FRAME_HANDLE_HOVER_SCALE = 1.3;
const FRAME_HANDLE_GAP = 130; // o neco dal nez bezna sipka, aby se nepletly
let hoveredEndpointMarker = null; // { mesh, entry, connIdx } - aktualne podsviceny konec pod kurzorem
let hoveredFrameHandle = null; // { mesh, frameMeta, axis } - aktualne podsviceny handle pro natazeni ramu

// Robert 2026-08-07 ("postavit 2D protahovani pro desky", pak "proč
// šipky zelené? protahujeme oranžový, profily mají oranžový") - hrana
// desky pouziva STEJNOU oranzovou jako konec profilu (ENDPOINT_ARROW_*
// nize) - je to koncepcne stejna akce (protazeni jednoho rozmeru
// JEDNOHO dilu), jen u jineho typu dilu, na rozdil od modre (protazeni
// CELEHO ramu - jina skupina pusobnosti). Puvodni samostatna zelena
// barva odstranena, aby nevznikal zbytecny treti vizualni jazyk.
let hoveredBoardEdgeMarker = null; // { mesh, entry, connIdx }
function setEndpointMarkerHover(markerEntry, isHover) {
  if (!markerEntry) return;
  markerEntry.mesh.material.color.setHex(isHover ? ENDPOINT_ARROW_HOVER_COLOR : ENDPOINT_ARROW_COLOR);
  markerEntry.mesh.material.opacity = isHover ? ENDPOINT_ARROW_HOVER_OPACITY : ENDPOINT_ARROW_OPACITY;
  markerEntry.mesh.scale.setScalar(isHover ? ENDPOINT_ARROW_HOVER_SCALE : 1);
}

// Textury cel profilu ODSTRANENY (Robert 2026-07-24: "dejme pryc ty obrazky cela profilu").

// Robert 2026-08-12 ("oznaci plochy podle geometrie a ja to klikem
// potvrdim"): spolecny helper pro vsechna mista, ktera pocitaji
// connectorsLocal pro KONKRETNI katalogovy dil - vždy stejná dvojice
// (wallSnap pro prislusenstvi + naucene geometricke plochy, pokud dil
// nejake ma). Jedno misto, at se pri pridavani dalsich per-dil
// vlastnosti nemusi menit desitky volani jednotlive.
function partConnectorOpts(p) {
  return { wallSnap: !isProfilePart(p), geoFaces: (p && Array.isArray(p.geo_faces)) ? p.geo_faces : undefined };
}

// Robert 2026-08-07 ("postavit 2D protahovani pro desky"): obdoba
// computeConnectorsLocal vyse, ale pro DESKOVY material (shop_products
// s is_board_material=1, viz sql/2026-08-07_product_board_material.sql) -
// misto 1 delkove osy (profil) identifikuje 2 PROMENNE osy (sirka+vyska,
// dve nejvetsi rozmery bboxu) a 1 PEVNOU tloustku (nejmensi rozmer).
// Vraci VZDY presne 4 hranove konektory (kind "edge") - indexy [0,1] =
// protilehle hrany sirky (axis:"width"), [2,3] = protilehle hrany vysky
// (axis:"height"). Zamerne ZADNY "end"/"mid"/"face" kind - vsechen
// stavajici kod pro spoje/protazeni profilu filtruje presne na "end",
// takze deska je pro nej automaticky neviditelna (nechova se jako
// profil - nejde spojovat na profily ani natahovat oranzovou sipkou,
// coz je v teto prvni verzi zamerne mimo rozsah).
function computeBoardEdgeConnectors(obj) {
  const box = new THREE.Box3().setFromObject(obj);
  const size = new THREE.Vector3(); box.getSize(size);
  const center = new THREE.Vector3(); box.getCenter(center);
  const dims = [size.x, size.y, size.z];
  let thicknessIdx = 0;
  if (dims[1] < dims[thicknessIdx]) thicknessIdx = 1;
  if (dims[2] < dims[thicknessIdx]) thicknessIdx = 2;
  const [widthIdx, heightIdx] = [0, 1, 2].filter(i => i !== thicknessIdx);
  const widthVec = new THREE.Vector3(widthIdx === 0 ? 1 : 0, widthIdx === 1 ? 1 : 0, widthIdx === 2 ? 1 : 0);
  const heightVec = new THREE.Vector3(heightIdx === 0 ? 1 : 0, heightIdx === 1 ? 1 : 0, heightIdx === 2 ? 1 : 0);
  const halfWidth = dims[widthIdx] / 2, halfHeight = dims[heightIdx] / 2;
  return [
    { point: center.clone().addScaledVector(widthVec, halfWidth), normal: widthVec.clone(), kind: "edge", axis: "width" },
    { point: center.clone().addScaledVector(widthVec, -halfWidth), normal: widthVec.clone().negate(), kind: "edge", axis: "width" },
    { point: center.clone().addScaledVector(heightVec, halfHeight), normal: heightVec.clone(), kind: "edge", axis: "height" },
    { point: center.clone().addScaledVector(heightVec, -halfHeight), normal: heightVec.clone().negate(), kind: "edge", axis: "height" },
  ];
}

// Zjisti, o kolik "vycuhuje" prurez dilu (entry) ve smeru worldDir od jeho
// stredove/delkove osy - tedy polovinu sirky dilu v tom smeru. Pouziva se na
// OBOU stranach spoje: 1) kolik se ma pripojovany dil odsadit OD rodice, aby
// nesahal skrz jeho stred, 2) kolik se ma "zasunout" podel delky rodice, aby
// nepresahoval za jeho spicku. Pracuje jen s 90-stupnovymi natocenimi, takze
// smer bud presne sedi s nekterou prurezovou osou (projekce ~1), nebo je na
// ni kolmy (~0) - proto staci prah 0.5.
function rebuildOccupiedConnectors() {
  occupiedConnectors = [];
  placed.forEach(e => occupiedConnectors.push(...worldConnectorsOf(e)));
  if (typeof refreshFreeConnectorsDebugIfActive === "function") refreshFreeConnectorsDebugIfActive();
}

// Prekresli oranzove znacky na volnych koncich dilu. Volaji vsechny funkce, ktere
// meni obsah sceny (pridani/odebrani dilu, spojeni, protazeni) - viz volani nize.
function refreshEndpointMarkers() {
  endpointMarkers.forEach(m => scene.remove(m.mesh));
  endpointMarkers.length = 0;
  hoveredEndpointMarker = null; // stare mesh instance uz jsou pryc ze sceny
  placed.forEach(entry => {
    if (!entry.usedConn) entry.usedConn = new Set();
    const worldConns = worldConnectorsOf(entry);
    entry.connectorsLocal.forEach((c, connIdx) => {
      if (c.kind !== "end") return; // znacky jen na koncich, ne na "mid" T-konektoru
      // Robert 2026-07-28: "pravidlo: natahovat oranzovyma sipkama nejde
      // prislusenstvi, jen profily" - oranzova sipka (protazeni delky) davá
      // smysl jen u hlinikoveho profilu (entry.part.layer === "alu"), ktery
      // ma skutecnou promennou delku. Prislusenstvi/spojky (layer black/
      // zinc) i produkty (layer "produkt", viz fetch_katalog_parts()
      // v app.py) maji pevny tvar - "protazeni" by je jen natahlo/zdeformovalo
      // bez fyzickeho smyslu. Predtim se tohle rucne resilo jen v JEDNOM
      // specifickem importu (SSE baked-world, entry.usedConn=[0,1]), takze
      // vsechny OSTATNI cesty vlozeni dilu (klik na katalog, AI generate,
      // kopie, wizard, vlastni tvary...) sipky prislusenstvi/produktum
      // omylem ukazovaly. Reseno centralne tady - plati pro VSECHNY cesty
      // vlozeni najednou, bez ohledu na to, kudy dil do `placed` pribyl.
      if (entry.part && entry.part.layer && entry.part.layer !== "alu") return;
      // Robert 2026-07-24: "chci tam i ty puvodni sipky oranzove, protoze
      // tim muzu zmenit tvar" - u dilu, ktere jsou soucasti uzavreneho ramu
      // (entry.frameGroup), ukazujeme oranzovou sipku VZDY, i na jiz
      // spojenem konci - Robert chce moznost kdykoli rucne protahnout/
      // zkratit jednotlivy dil ramu (i za cenu rozbiti pravidelneho
      // ctvercoveho/obdelnikoveho tvaru), NEZAVISLE na novem modrem
      // tlacitku, ktere naopak rozmer cele sestavy zachovava. U vsech
      // ostatnich (nerámových) spojenych dilu zustava puvodni chovani -
      // spojeny konec sipku nema (u tech bezne nema smysl ho protahovat
      // izolovane, viz komentar u dragState/applyLengthScale).
      if (entry.usedConn.has(connIdx) && !entry.frameGroup) return; // konec uz je pripojeny - neni co tahat/rozsirovat
      const mat = new THREE.MeshBasicMaterial({ color: ENDPOINT_ARROW_COLOR, transparent: true, opacity: ENDPOINT_ARROW_OPACITY });
      const mesh = new THREE.Mesh(endpointMarkerGeom, mat);
      const normal = worldConns[connIdx].normal;
      // Zaklad sipky je odsazeny o ENDPOINT_ARROW_GAP od konektoru (misto aby
      // se ho dotykal), pak teprve nasleduje sipka samotna smerem ven.
      mesh.position.copy(worldConns[connIdx].point).addScaledVector(normal, ENDPOINT_ARROW_GAP + ENDPOINT_ARROW_LEN / 2);
      mesh.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), normal);
      mesh.userData.isEndpointMarker = true;
      scene.add(mesh);
      endpointMarkers.push({ mesh, entry, connIdx });
    });
  });
  refreshFrameResizeHandles();
  refreshBoardEdgeMarkers();
}

// Sipky pro natazeni CELEHO uzavreneho tvaru (viz refitRectFrameEntries
// vyse) - jedna na Y-osu (delka dilu A/B), jedna na X-osu (rozestup A-B).
// Zavola se vzdy spolu s refreshEndpointMarkers() (viz jeji konec nize),
// aby se nemuselo dohledavat/upravovat vsechna mista, ktera uz
// refreshEndpointMarkers() volaji.
let frameResizeHandles = [];
function refreshFrameResizeHandles() {
  frameResizeHandles.forEach(h => scene.remove(h.mesh));
  frameResizeHandles.length = 0;
  hoveredFrameHandle = null;
  const seen = new Set();
  placed.forEach(entry => {
    const fg = entry.frameGroup;
    if (!fg || seen.has(fg)) return;
    seen.add(fg);
    const { entryA, entryB } = fg;
    const wcA = worldConnectorsOf(entryA);
    const yDir = wcA[1].point.clone().sub(wcA[0].point).normalize();
    const wcB0 = worldConnectorsOf(entryB)[0].point;
    const xDir = wcB0.clone().sub(wcA[0].point).normalize();

    // Y-osa: za vzdalenym koncem A (konektor 1), smerem dal ve smeru yDir.
    const yMat = new THREE.MeshBasicMaterial({ color: FRAME_HANDLE_COLOR, transparent: true, opacity: FRAME_HANDLE_OPACITY });
    const yMesh = new THREE.Mesh(endpointMarkerGeom, yMat);
    yMesh.position.copy(wcA[1].point).addScaledVector(yDir, FRAME_HANDLE_GAP + ENDPOINT_ARROW_LEN / 2);
    yMesh.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), yDir);
    yMesh.userData.isFrameHandle = true;
    scene.add(yMesh);
    frameResizeHandles.push({ mesh: yMesh, frameMeta: fg, axis: "Y" });

    // X-osa: u dilu B, na jeho vnejsi strane (smerem od A), v polovine jeho delky.
    const wcB = worldConnectorsOf(entryB);
    const midB = wcB[0].point.clone().add(wcB[1].point).multiplyScalar(0.5);
    const halfB = crossAxisHalfWidthTowardDirection(entryB.connectorsLocal, entryB.object3d.quaternion, xDir);
    const xMat = new THREE.MeshBasicMaterial({ color: FRAME_HANDLE_COLOR, transparent: true, opacity: FRAME_HANDLE_OPACITY });
    const xMesh = new THREE.Mesh(endpointMarkerGeom, xMat);
    xMesh.position.copy(midB).addScaledVector(xDir, halfB + FRAME_HANDLE_GAP + ENDPOINT_ARROW_LEN / 2);
    xMesh.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), xDir);
    xMesh.userData.isFrameHandle = true;
    scene.add(xMesh);
    frameResizeHandles.push({ mesh: xMesh, frameMeta: fg, axis: "X" });
  });
}

// Robert 2026-08-07 ("postavit 2D protahovani pro desky") - zelene sipky
// na vsech 4 hranach kazde polozene DESKY (entry.part.is_board_material) -
// obdoba refreshEndpointMarkers, ale pro "edge" kind konektory
// (computeBoardEdgeConnectors). Zavola se vzdy spolu s
// refreshEndpointMarkers() (viz jeji konec vyse), stejny princip jako
// refreshFrameResizeHandles.
let boardEdgeMarkers = [];
function refreshBoardEdgeMarkers() {
  boardEdgeMarkers.forEach(m => scene.remove(m.mesh));
  boardEdgeMarkers.length = 0;
  hoveredBoardEdgeMarker = null;
  placed.forEach(entry => {
    if (!entry.part || !entry.part.is_board_material) return;
    const worldConns = worldConnectorsOf(entry);
    entry.connectorsLocal.forEach((c, connIdx) => {
      if (c.kind !== "edge") return;
      const mat = new THREE.MeshBasicMaterial({ color: ENDPOINT_ARROW_COLOR, transparent: true, opacity: ENDPOINT_ARROW_OPACITY });
      const mesh = new THREE.Mesh(endpointMarkerGeom, mat);
      const normal = worldConns[connIdx].normal;
      mesh.position.copy(worldConns[connIdx].point).addScaledVector(normal, ENDPOINT_ARROW_GAP + ENDPOINT_ARROW_LEN / 2);
      mesh.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), normal);
      mesh.userData.isBoardEdgeMarker = true;
      scene.add(mesh);
      boardEdgeMarkers.push({ mesh, entry, connIdx });
    });
  });
}
function setBoardEdgeMarkerHover(markerEntry, isHover) {
  if (!markerEntry) return;
  markerEntry.mesh.material.color.setHex(isHover ? ENDPOINT_ARROW_HOVER_COLOR : ENDPOINT_ARROW_COLOR);
  markerEntry.mesh.material.opacity = isHover ? ENDPOINT_ARROW_HOVER_OPACITY : ENDPOINT_ARROW_OPACITY;
  markerEntry.mesh.scale.setScalar(isHover ? ENDPOINT_ARROW_HOVER_SCALE : 1);
}
function repositionDraggedBoardEdgeMarker(entry, connIdx) {
  const markerEntry = boardEdgeMarkers.find(m => m.entry === entry && m.connIdx === connIdx);
  if (!markerEntry) return;
  const worldConns = worldConnectorsOf(entry);
  const normal = worldConns[connIdx].normal;
  markerEntry.mesh.position.copy(worldConns[connIdx].point).addScaledVector(normal, ENDPOINT_ARROW_GAP + ENDPOINT_ARROW_LEN / 2);
  markerEntry.mesh.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), normal);
}

// Robert 2026-07-24: "porad to skace kdyz zacnu natahovat tazenim skoci
// to" - skutecna pricina (nesouvisejici s vypoctem delky) byla tady:
// refreshEndpointMarkers() nici a znovu vytvari VSECHNY sipky pri KAZDEM
// pointermove behem tazeni (viz volani nize v pointermove), a pritom
// bezpodminecne nuluje hoveredEndpointMarker a vytvari nove mesh instance
// s VYCHOZIM (ne-hover) stylem. Protoze uzivatel typicky sipku pred
// kliknutim chvili najizdi mysi (hover -> zvetsena/zvyraznena), prvni
// pointermove behem tazeni okamzite znicil tenhle "hover" mesh a nahradil
// ho cerstvym normalnim - vizualne pusobilo jako "skok" presne na zacatku
// tazeni, i kdyz samotna DELKA dilu se pocitala spravne. Reseni: behem
// aktivniho tazeni NEPROVADIME plny rebuild vsech znacek (zbytecne a
// draze), jen prepocitame pozici/natoceni JIZ EXISTUJICI sipky taheneho
// konce - zadne mesh instance se nenici ani nevytvari, takze zadny
// vizualni skok. Plny refreshEndpointMarkers() se zavola az po skonceni
// tazeni (pointerup), jak uz byvalo zvykem.
function repositionDraggedEndpointMarker(entry, connIdx) {
  const markerEntry = endpointMarkers.find(m => m.entry === entry && m.connIdx === connIdx);
  if (!markerEntry) return;
  const worldConns = worldConnectorsOf(entry);
  const normal = worldConns[connIdx].normal;
  markerEntry.mesh.position.copy(worldConns[connIdx].point).addScaledVector(normal, ENDPOINT_ARROW_GAP + ENDPOINT_ARROW_LEN / 2);
  markerEntry.mesh.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), normal);
}

// --- Zive koty (mm) - HTML popisky s aktualni delkou kazdeho dilu, primo nad
// dilem ve scene. "Zive" = pocitaji se z aktualni vzdalenosti koncovych
// konektoru (tedy respektuji i protazeni tazenim za oranzovy konec), ne z
// puvodni katalogove delky. Vykreslene jako obycejne HTML divy nad canvasem
// (promitnute z 3D do 2D pres camera.project), ne jako 3D geometrie - jednodussi
// a ostre citelne v jakemkoli zoomu. (dimLabelEntries je deklarovane vyse,
// pred prvnim volanim animate() - viz komentar tam.)
// Robert 2026-08-16 ("udelejme vic rezimu kotovani: 1) cele profily
// (aktualni) 2) ad 1 plus koty mezi vsemi profily 3) ad 2 plus koty
// dilu"): dimMode 1 = jen dnesni chovani (delka kazdeho profilu/rozmer
// desky - viz updateDimLabelPositions), 2 = navic kota "vzdalenost spoje
// od nejblizsiho konce" pro kazdou dvojici DOTYKAJICICH SE profilu
// (Robert zvolil "jen sousedici/dotykajici se", ne kazdy s kazdym - u N
// profilu by to bylo N² a nepouzitelne prepnene), 3 = navic rozmer
// obalky (W×H×D) u prislusenstvi/spojek (viz vetev v
// updateDimLabelPositions vyse). (dimMode/dimPairLabelEntries jsou
// deklarovane vyse, pred prvnim volanim animate() - viz komentar tam.)
// Robert 2026-08-16 ("upresnim technicke kotovani verzi 2 a 3 nejede"):
// vytazeno z puvodniho telesa refreshDimPairLabels(), aby stejny vypocet
// (kandidatni T-spoje + vzdalenosti k oběma koncum pruchoziho profilu)
// mohly pouzit OBA rendery - jednoduchy DOM-popiskovy (refreshDimPairLabels
// nize) i sipkove Technicke kotovani (drawDimensionOverlay/
// updateLiveTechnicalDimensions) - misto duplikovat tu same geometrii
// na dvou mistech.
// Robert 2026-08-16 ("od sten... vrtaci koty... budou se zobrazovat
// samostatne"): detekce T-spoju (kdo je "pruchozi" profil, kdo "protinajici",
// + fp = footprint protinajiciho profilu na ose pruchoziho) je SPOLECNA
// pro dva ruzne zpusoby kotovani (ke stene - computeJointDimensionSegments,
// ke stredu/ose - computeDrillingDimensionSegments, tzv. "vrtaci kóty") -
// vytazeno sem, aby se nepocitalo/neduplikovalo dvakrat.
function findProfileJointCandidates() {
  const out = []; // { throughProf, otherProf, axis, fp }
  const profs = placed.filter(e => e.part && isProfilePart(e.part));
  for (let i = 0; i < profs.length; i++) {
    for (let j = i + 1; j < profs.length; j++) {
      const a = profs[i], b = profs[j];
      if (!a.licPeers || !a.licPeers.has(b)) continue;
      const inferred = (typeof inferProfileJointConnectors === "function") ? inferProfileJointConnectors(a, b) : null;
      if (!inferred) continue;
      const aKind = a.connectorsLocal[inferred.myConnIdx] && a.connectorsLocal[inferred.myConnIdx].kind;
      const bKind = b.connectorsLocal[inferred.otherConnIdx] && b.connectorsLocal[inferred.otherConnIdx].kind;
      // Smysluplna kota je jen u T-spoje (jeden konec, druhy stred/bok) -
      // "vzdalenost spoje od konce pruchoziho profilu". Rovne prodlouzeni
      // (oba "end") i bok-k-boku (oba "face") kotovat nema smysl (0 nebo
      // nejednoznacne).
      let throughProf = null, otherProf = null;
      if (aKind === "end" && bKind !== "end") { throughProf = b; otherProf = a; }
      else if (bKind === "end" && aKind !== "end") { throughProf = a; otherProf = b; }
      else continue;
      const axis = profileAxisInfo(throughProf);
      if (!axis) continue;
      const fp = axisFootprint(otherProf, axis.axisA, axis.axisDir);
      if (!fp) continue;
      out.push({ throughProf, otherProf, axis, fp });
    }
  }
  return out;
}
// Robert 2026-08-16 ("oprav nejdrive hlasene tech koty" - zaskrtnuty
// jako spatne 4 spoje rezimu 2 checkboxovym reportem): puvodni verze
// obou funkci nize pocitala kazdou dvojici (throughProf, otherProf) z
// findProfileJointCandidates() NEZAVISLE - "od zacatku profilu ke
// SPOJI" + "od SPOJE do konce profilu", bez ohledu na to, ze STEJNY
// throughProf muze mit VIC nez jeden spoj podel sve delky (napr.
// slozitejsi krizeni vic profilu na jednom pruchozim kuse). U profilu
// se 2+ spoji tak kazda dvojice kreslila SVOJI vlastni "od kraje"
// kotu, ktera se prekryvala/nesedela s kotou od sousedniho spoje -
// presne ten typ zdanlive "nahodnych"/spatnych kot, co Robert
// oznacil. Oprava: seskup kandidaty PODLE throughProf, setrid jejich
// intervaly podel osy a okotuj je jako RETEZEC (kraj->spoj1,
// spoj1->spoj2, ..., spojN->kraj) - stejny princip jako uz existujici
// "chain" kotovani delky dilu vyse (dimensionGroups/chainOuterPoint).
function groupJointCandidatesByThroughProfile() {
  const byThrough = new Map(); // throughProf -> { axis, intervals:[{t0,t1}] }
  findProfileJointCandidates().forEach(({ throughProf, otherProf, axis, fp }) => {
    let g = byThrough.get(throughProf);
    if (!g) { g = { axis, intervals: [] }; byThrough.set(throughProf, g); }
    const t0 = Math.max(0, Math.min(axis.L, fp.t0));
    const t1 = Math.max(0, Math.min(axis.L, fp.t1));
    // otherProf se nese s intervalem dal (bot8 2026-09-10) - vrtaci koty na
    // noze se podle nej deli na CELNI a BOCNI radu, viz
    // computeDrillingDimensionSegments.
    if (t1 > t0) g.intervals.push({ t0, t1, otherProf });
  });
  byThrough.forEach(g => {
    g.intervals.sort((a, b) => a.t0 - b.t0);
    // Sousedni/prekryvajici se intervaly (napr. dva spoje tesne vedle
    // sebe) slouc do jednoho, at retezec nevytvori nulovou/zapornou kotu.
    const merged = [];
    g.intervals.forEach(iv => {
      const last = merged[merged.length - 1];
      if (last && iv.t0 <= last.t1 + 1) last.t1 = Math.max(last.t1, iv.t1);
      else merged.push({ t0: iv.t0, t1: iv.t1, otherProf: iv.otherProf });
    });
    g.intervals = merged;
  });
  return byThrough;
}
// Rezim 2 - ke STENE (blizsimu kraji) protinajiciho profilu, ne k jeho ose.
function computeJointDimensionSegments() {
  const out = []; // { p0, p1, distMm }
  if (dimMode < 2) return out;
  groupJointCandidatesByThroughProfile().forEach(({ axis, intervals }) => {
    let cursor = 0;
    intervals.forEach(iv => {
      const distMm = Math.round(iv.t0 - cursor);
      if (distMm >= 1) {
        out.push({
          p0: axis.axisA.clone().addScaledVector(axis.axisDir, cursor),
          p1: axis.axisA.clone().addScaledVector(axis.axisDir, iv.t0),
          distMm,
        });
      }
      cursor = iv.t1;
    });
    const tailMm = Math.round(axis.L - cursor);
    if (tailMm >= 1) {
      out.push({
        p0: axis.axisA.clone().addScaledVector(axis.axisDir, cursor),
        p1: axis.axisA.clone().addScaledVector(axis.axisDir, axis.L),
        distMm: tailMm,
      });
    }
  });
  return out;
}
// Robert 2026-08-22 ("U kazde karoserie chceme zobrazovat 3D kotu vysky
// otvoru zadnich dveri", pak upresneno "Proto pisu kota 3d protoze ji chci
// videt odkud kam vede primo ve 3d pohledu" - tedy skutecna kotovaci cara
// se sipkami mezi 2 body, ne jen plovouci cislo, POTOM jeste "kde je
// celo/prepazka ale kotu chceme tam kde je velky otvor - to znamena na
// druhe strane karoserie"): stejny "extraLines" mechanismus jako joint/
// cross-section/drilling kóty vyse, kresli se stejnym drawDimensionOverlay
// (viz updateLiveTechnicalDimensions), takze je videt i primo ve 3D
// perspektive (zatrzitko "i ve 3D"), presne jak uz funguje u profilu.
//
// Dil "B" NENI zadni otvor - je to celni prepazka/bulkhead (stejna
// front/back nejednoznacnost orientace, kterou uz Robert drive akceptoval
// jako inherentni limit detekce os, viz AGENTS_LOG 2026-08-19/21). Velky
// otvor je na DRUHEM konci karoserie - tam, kde bocnice L/R_D konci BEZ
// prepazky. Vyska tam NENI vzdy stejna jako u B (u 2 testovanych modelu
// vysla shodou stejne, ale u zbylych ~300 modelu to neni overene - proto
// se MERI realne, ne prevzato z B, viz ensureCarBodyDoorEdgeLocalCache).
function ensureCarBodyDoorEdgeLocalCache(sideEntry) {
  if (sideEntry._doorEdgeLocalCache !== undefined) return sideEntry._doorEdgeLocalCache;
  sideEntry.object3d.updateMatrixWorld(true);
  const worldPts = [];
  let zMin = Infinity, zMax = -Infinity;
  sideEntry.object3d.traverse(node => {
    if (!node.isMesh || !node.geometry || !node.geometry.attributes || !node.geometry.attributes.position) return;
    node.updateMatrixWorld(true);
    const pos = node.geometry.attributes.position;
    for (let i = 0; i < pos.count; i++) {
      const p = new THREE.Vector3().fromBufferAttribute(pos, i).applyMatrix4(node.matrixWorld);
      worldPts.push(p);
      if (p.z < zMin) zMin = p.z;
      if (p.z > zMax) zMax = p.z;
    }
  });
  if (!worldPts.length || !isFinite(zMin)) { sideEntry._doorEdgeLocalCache = null; return null; }
  // Skutecny okrajovy ram byva tenka plocha temer presne na hranicni Z -
  // postupne rozsiruj toleranci, dokud neni dost bodu pro spolehlivy odhad
  // (misto pevneho "sirokeho pasma", ktere by mohlo zasahnout uz do
  // zuzujici se prechodove geometrie uprostred delky - viz diagnostika).
  function edgeYRange(extremeZ) {
    for (const eps of [5, 15, 40, 100, 250]) {
      const ys = worldPts.filter(p => Math.abs(p.z - extremeZ) <= eps).map(p => p.y);
      if (ys.length >= 8) return { min: Math.min(...ys), max: Math.max(...ys) };
    }
    return null;
  }
  const midXWorld = (function () { const b = new THREE.Box3().setFromPoints(worldPts); return (b.min.x + b.max.x) / 2; })();
  function toLocalCache(edge, zWorld) {
    if (!edge) return null;
    const p0 = sideEntry.object3d.worldToLocal(new THREE.Vector3(midXWorld, edge.min, zWorld));
    const p1 = sideEntry.object3d.worldToLocal(new THREE.Vector3(midXWorld, edge.max, zWorld));
    return { p0, p1 };
  }
  sideEntry._doorEdgeLocalCache = {
    minZWorldAtCache: zMin, maxZWorldAtCache: zMax,
    minEdge: toLocalCache(edgeYRange(zMin), zMin),
    maxEdge: toLocalCache(edgeYRange(zMax), zMax),
  };
  return sideEntry._doorEdgeLocalCache;
}
// Seskup L/R_D/B podle spolecneho zakladu souboru (napr.
// ".../BYD_ETP3_L.glb?v=..." a "..._B.glb?v=..." -> zaklad
// ".../BYD_ETP3") - vic karoserii ve scene soucasne se tim nemichaji
// dohromady, na rozdil od pouheho hledani "nejblizsi B/L v poli". Sdileno
// mezi zmerenou a oficialni (vyrobcovou) kotou nize - stejne dvojice.
function groupCarBodyEntriesByBase() {
  const groups = new Map();
  placed.forEach(entry => {
    if (!entry.part || entry.part.source !== "car_body" || !entry.part.file) return;
    const clean = entry.part.file.split("?")[0];
    const m = clean.match(/^(.*)_(L|R_D|B)\.glb$/);
    if (!m) return;
    const g = groups.get(m[1]) || {};
    g[m[2]] = entry;
    groups.set(m[1], g);
  });
  return groups;
}
// Najde pro jednu skupinu L/R_D+B "vzdalenejsi hranu" (viz komentar u
// ensureCarBodyDoorEdgeLocalCache vyse) - {p0Local, p1Local, sideEntry}
// v LOKALNIM prostoru bocnice, nebo null kdyz to nejde spocitat. Spolecne
// pro zmerenou i oficialni kotu - lisi se jen ve zpusobu vypoctu p1.
function findCarBodyFarEdgeLocal(g) {
  const bEntry = g.B;
  const sideEntry = g.L || g.R_D;
  if (!bEntry || !sideEntry) return null;
  bEntry.object3d.updateMatrixWorld(true);
  const bBox = new THREE.Box3().setFromObject(bEntry.object3d);
  if (bBox.isEmpty()) return null;
  const cache = ensureCarBodyDoorEdgeLocalCache(sideEntry);
  if (!cache) return null;
  const bZmid = (bBox.min.z + bBox.max.z) / 2;
  let useMin = Math.abs(bZmid - cache.minZWorldAtCache) > Math.abs(bZmid - cache.maxZWorldAtCache);
  // Robert 2026-08-22 ("koty zadnich dveří jsou u nekterych modelů porad v
  // predni casti, takze udelejme to ze je mohu ve vodorovne posunout") -
  // automaticka detekce vzdalenejsiho konce neni 100% spolehliva pro vsech
  // ~300 modelu (viz i puvodni B/prepazka omyl) - klik na kotu (viz
  // syncCarBodyDoorFlipTargets) prehodi na druhy konec, ulozeno primo na
  // sideEntry (preziva dokud je dil ve scene, neuklada se do DB/tvaru).
  if (sideEntry._doorKotaFlipped) useMin = !useMin;
  const edge = useMin ? cache.minEdge : cache.maxEdge;
  if (!edge) return null;
  return { sideEntry, p0Local: edge.p0, p1Local: edge.p1 };
}
function computeCarBodyDoorDimensionSegments() {
  const out = [];
  groupCarBodyEntriesByBase().forEach(g => {
    const found = findCarBodyFarEdgeLocal(g);
    if (!found) return;
    found.sideEntry.object3d.updateMatrixWorld(true);
    const p0 = found.p0Local.clone().applyMatrix4(found.sideEntry.object3d.matrixWorld);
    const p1 = found.p1Local.clone().applyMatrix4(found.sideEntry.object3d.matrixWorld);
    out.push({ p0, p1, distMm: Math.round(p0.distanceTo(p1)) });
  });
  return out;
}
// Robert 2026-08-22 ("oficialni vysky dveri od vyrobcu uvadejme jako
// druhou 3D kotu zacinajici od podlahy karoserie"): DRUHA kota vedle
// zmerene (computeCarBodyDoorDimensionSegments vyse) - stejny pocatecni
// bod (podlaha bocnice na vzdalenejsim konci), ale KONCOVY bod NENI
// zmereny z geometrie - je to podlaha + rucne dohledana/zkrizovana
// hodnota od vyrobce (bot10, backups/2026-08-22_door_height_
// reconciliation_*, ulozeno v karoserie_model_reference.official_door_
// opening_height_mm). bot8 2026-09-06: pripojeni na specifikaci pres
// part.car_model_id (stabilni, viz api/app.py fetch_katalog_parts) -
// stejny mechanismus jako hover karta v panelu Vlastni tvary.
function computeCarBodyOfficialDoorDimensionSegments() {
  const out = [];
  groupCarBodyEntriesByBase().forEach(g => {
    const found = findCarBodyFarEdgeLocal(g);
    if (!found) return;
    const spec = found.sideEntry.part && found.sideEntry.part.car_model_id != null ? KAROSERIE_SPECS[String(found.sideEntry.part.car_model_id)] : null;
    if (!spec || spec.official_door_height_mm == null) return;
    found.sideEntry.object3d.updateMatrixWorld(true);
    const p0 = found.p0Local.clone().applyMatrix4(found.sideEntry.object3d.matrixWorld);
    const p1Local = found.p0Local.clone();
    p1Local.y += spec.official_door_height_mm;
    const p1 = p1Local.applyMatrix4(found.sideEntry.object3d.matrixWorld);
    out.push({ p0, p1, distMm: spec.official_door_height_mm, source: spec.official_door_height_source });
  });
  return out;
}
// Robert 2026-08-22 ("stejnym zpusobem chceme znat, ulozit a zobrazovat
// oficialni rozmery otvoru bocnich dveri vsech modelu vsech znacek"): jen
// vyrobcova hodnota (official_side_door_height_mm) - zadna vlastni zmerena
// geometricka kota. Bocni dvere jsou na dilu "R_D" (jediny z L/R_D/B s
// oznacenim dveri v nazvu), ale NA ROZDIL od zadnich dveri (hrana na konci
// bocnice) nemaji spolehlivy geometricky signal (viz AGENTS_LOG - overeno
// 4 ruznymi pristupy: kontrola diry v siti, kontrola oddelenych ostrovu,
// hruby hloubkovy scan, jemny rastr paprsku - vsechny selhaly najit cistou
// hranici). Pozice je proto jen ROZUMNY VYCHOZI ODHAD (stred delky R_D
// steny) - X/Y/Z offset lze v budoucnu udelat rucne posunutelny stejne
// jako se to dela u zadnich dveri (viz syncCarBodyDoorFlipTargets), zatim
// staticky.
// Robert 2026-08-22 ("kotu výška bočních dveří ale musíme zespoda zkrátit,
// o ten nástupní schod pokud existuje"): presne ta prohlubeň u podlahy,
// kterou drivejsi hledani otvoru bocnich dveri naslo a vyhodnotilo jako
// "asi jen prah/nastupni schod, ne dvere samotne" - overeno 2x na realne
// geometrii (Ducato FI07: baseline hloubka -905mm, schod konci na
// Y=353mm; Renault Master RE23: baseline -876mm, schod Y=239mm) - u
// mensich/nizkych dodavek (BYD ETP3) zadny jasny schod neni, coz
// odpovida realite (male dodavky casto nemaji vystouply schod).
// Cachovano na rdEntry (drahy vertex scan jen jednou, ne kazdy snimek).
function ensureSideDoorStepLocalCache(rdEntry, midZWorld) {
  const cache = rdEntry._sideDoorStepCache;
  if (cache && cache.forMidZ === midZWorld) return cache.stepTopYLocal;
  rdEntry.object3d.updateMatrixWorld(true);
  const worldPts = [];
  rdEntry.object3d.traverse(node => {
    if (!node.isMesh || !node.geometry || !node.geometry.attributes || !node.geometry.attributes.position) return;
    node.updateMatrixWorld(true);
    const pos = node.geometry.attributes.position;
    for (let i = 0; i < pos.count; i++) worldPts.push(new THREE.Vector3().fromBufferAttribute(pos, i).applyMatrix4(node.matrixWorld));
  });
  const ZBAND = 300, YBASE_MIN = 500, YSTEP_MAX = 600, XTHRESH = 50;
  const band = worldPts.filter(p => Math.abs(p.z - midZWorld) <= ZBAND);
  let stepTopYWorld = null;
  const highXs = band.filter(p => p.y > YBASE_MIN).map(p => p.x).sort((a, b) => a - b);
  if (highXs.length) {
    const baseline = highXs[Math.floor(highXs.length / 2)]; // median
    band.forEach(p => {
      if (p.y < YSTEP_MAX && p.x > baseline + XTHRESH) {
        if (stepTopYWorld === null || p.y > stepTopYWorld) stepTopYWorld = p.y;
      }
    });
  }
  const stepTopYLocal = stepTopYWorld == null ? null : rdEntry.object3d.worldToLocal(new THREE.Vector3(0, stepTopYWorld, 0)).y;
  rdEntry._sideDoorStepCache = { forMidZ: midZWorld, stepTopYLocal };
  return stepTopYLocal;
}
// Robert 2026-08-22 ("sleduju že koty bočních dveří jsou u aut nejak
// posunuté ke středu nákladového prostoru"): puvodni "stred Z cele
// bocnice" davalo spolehlive spatnou pozici, protoze bocnice NENI
// symetricka - u vsech testovanych modelu (Ford/VW/Fiat/Renault) je
// zadni ~roh/podběh modelovany s mnohem VETSI hloubkovou variaci
// (vertex X sahajici temer pres celou sirku steny, ~870-1000mm) nez
// zbytek bocnice vcetne oblasti dveri (~100-300mm) - viz diagnostika
// scripts/tmp_2026-08-22_side_door_z_scan.js. (min+max)/2 pocitane z
// CELE bounding boxu tak vzdy "taha" stred smerem k tomuto hlubokemu
// zadnimu shluku, pryc od skutecne oblasti dveri, ktera lezi vic vpredu
// (blize kabine) - presne to Robert pozoruje.
//
// Oprava: vazeny stred (podle poctu vertexu) jen pres "mělká" Z-pasma
// (hloubkova variace < SHALLOW_MAX_MM) - vyloucenim hlubokeho zadniho
// shluku zustane vazeny prumer soustredeny v oblasti dveri/predni
// casti bocnice. NENI to presna detekce hranic dveri (na rozdil od
// vysky/sirky, ktere mame primo od vyrobce) - jen podstatne lepsi
// odhad polohy nez puvodni "stred cele bocnice". Robertuv `_sideDoorZOffsetMm`
// (rucni korekce per-karoserie) zustava k dispozici pro pripady, kdy
// ani tohle nesedi presne.
function ensureSideDoorZCenterLocal(rdEntry) {
  if (rdEntry._sideDoorZCenterLocal !== undefined) return rdEntry._sideDoorZCenterLocal;
  rdEntry.object3d.updateMatrixWorld(true);
  const worldPts = [];
  rdEntry.object3d.traverse(node => {
    if (!node.isMesh || !node.geometry || !node.geometry.attributes || !node.geometry.attributes.position) return;
    node.updateMatrixWorld(true);
    const pos = node.geometry.attributes.position;
    for (let i = 0; i < pos.count; i++) worldPts.push(new THREE.Vector3().fromBufferAttribute(pos, i).applyMatrix4(node.matrixWorld));
  });
  if (!worldPts.length) { rdEntry._sideDoorZCenterLocal = null; return null; }
  const box = new THREE.Box3().setFromPoints(worldPts);
  const NBINS = 30, SHALLOW_MAX_MM = 400;
  const binW = (box.max.z - box.min.z) / NBINS;
  let centerWorldZ = (box.min.z + box.max.z) / 2; // fallback, pouzije se kdyz binovani selze
  if (binW > 0) {
    const bins = Array.from({ length: NBINS }, () => ({ count: 0, xMin: Infinity, xMax: -Infinity }));
    const yLo = box.min.y + (box.max.y - box.min.y) * 0.15, yHi = box.min.y + (box.max.y - box.min.y) * 0.85;
    worldPts.forEach(p => {
      if (p.y < yLo || p.y > yHi) return;
      let bi = Math.floor((p.z - box.min.z) / binW);
      if (bi >= NBINS) bi = NBINS - 1;
      if (bi < 0) bi = 0;
      const b = bins[bi];
      b.count++;
      if (p.x < b.xMin) b.xMin = p.x;
      if (p.x > b.xMax) b.xMax = p.x;
    });
    let sumW = 0, sumWZ = 0;
    bins.forEach((b, i) => {
      if (!b.count || (b.xMax - b.xMin) > SHALLOW_MAX_MM) return;
      const zc = box.min.z + (i + 0.5) * binW;
      sumW += b.count;
      sumWZ += b.count * zc;
    });
    if (sumW > 0) centerWorldZ = sumWZ / sumW;
  }
  const midXWorld = (box.min.x + box.max.x) / 2, midYWorld = (box.min.y + box.max.y) / 2;
  rdEntry._sideDoorZCenterLocal = rdEntry.object3d.worldToLocal(new THREE.Vector3(midXWorld, midYWorld, centerWorldZ));
  return rdEntry._sideDoorZCenterLocal;
}
function carBodySideDoorAnchor(rdEntry) {
  rdEntry.object3d.updateMatrixWorld(true);
  const box = new THREE.Box3().setFromObject(rdEntry.object3d);
  if (box.isEmpty()) return null;
  const zOffsetMm = rdEntry._sideDoorZOffsetMm || 0;
  const detectedLocal = ensureSideDoorZCenterLocal(rdEntry);
  const detectedWorldZ = detectedLocal ? rdEntry.object3d.localToWorld(detectedLocal.clone()).z : (box.min.z + box.max.z) / 2;
  let midZ = detectedWorldZ + zOffsetMm;
  midZ = Math.min(box.max.z, Math.max(box.min.z, midZ));
  const stepTopYLocal = ensureSideDoorStepLocalCache(rdEntry, midZ);
  let stepTopYWorld = null;
  if (stepTopYLocal != null) {
    stepTopYWorld = rdEntry.object3d.localToWorld(new THREE.Vector3(0, stepTopYLocal, 0)).y;
  }
  return {
    midX: (box.min.x + box.max.x) / 2,
    floorY: box.min.y,
    // "zespoda zkratit o nastupni schod, pokud existuje" - vyskova kota
    // zacina na vrsku schodu, ne na absolutni podlaze; kdyz schod
    // nenalezen, spadne zpet na puvodni podlahu (beze zmeny chovani).
    heightStartY: stepTopYWorld != null && stepTopYWorld > box.min.y ? stepTopYWorld : box.min.y,
    midZ,
  };
}
function computeCarBodySideDoorDimensionSegments() {
  const out = [];
  groupCarBodyEntriesByBase().forEach(g => {
    const rdEntry = g.R_D;
    if (!rdEntry) return;
    const spec = rdEntry.part && rdEntry.part.car_model_id != null ? KAROSERIE_SPECS[String(rdEntry.part.car_model_id)] : null;
    if (!spec || spec.official_side_door_height_mm == null) return;
    const a = carBodySideDoorAnchor(rdEntry);
    if (!a) return;
    // a.heightStartY = vrsek nastupniho schodu (pokud detekovan), jinak
    // spadne zpet na absolutni podlahu - delka kotovaci cary (distMm)
    // zustava presne official_side_door_height_mm, jen posunuta vys, at
    // "nezasahuje" dolu do schodu (Robert: "zespoda zkratit o schod").
    const p0 = new THREE.Vector3(a.midX, a.heightStartY, a.midZ);
    const p1 = new THREE.Vector3(a.midX, a.heightStartY + spec.official_side_door_height_mm, a.midZ);
    out.push({ p0, p1, distMm: spec.official_side_door_height_mm, source: spec.official_side_door_source });
  });
  return out;
}
// Robert 2026-08-22 ("u bočních dveří potřebujeme 2 koty, výšku a šířku
// otvoru dveří") - druhy rozmer, VODOROVNA cara podel delky (Z), na
// stejnem pocatecnim bode (podlaha, stejny stred midZ) jako vyskova kota
// vyse - sdileji tak spolecny roh, zvykla technicka konvence.
function computeCarBodySideDoorWidthDimensionSegments() {
  const out = [];
  groupCarBodyEntriesByBase().forEach(g => {
    const rdEntry = g.R_D;
    if (!rdEntry) return;
    const spec = rdEntry.part && rdEntry.part.car_model_id != null ? KAROSERIE_SPECS[String(rdEntry.part.car_model_id)] : null;
    if (!spec || spec.official_side_door_width_mm == null) return;
    const a = carBodySideDoorAnchor(rdEntry);
    if (!a) return;
    const half = spec.official_side_door_width_mm / 2;
    const p0 = new THREE.Vector3(a.midX, a.floorY, a.midZ - half);
    const p1 = new THREE.Vector3(a.midX, a.floorY, a.midZ + half);
    out.push({ p0, p1, distMm: spec.official_side_door_width_mm, source: spec.official_side_door_width_source });
  });
  return out;
}
// Robert 2026-08-22 ("kotu pro karoserie ve scene budeme tahat pouze z
// oficialnich zdroju. pridej kotu: rozmer mezi podbehy"): sirka lozne
// plochy mezi podbehy kol (klicovy udaj pro europalety) - VYHRADNE
// vyrobcova hodnota, zadna vlastni geometricka (overeno: L/R_D/B dily
// nemaji modelovanou podlahu s podbehy vubec - profil zustava plochy po
// cele delce, viz AGENTS_LOG). Pozice: vodorovna cara pres X (sirku) na
// podlaze, u rozumneho vychoziho Z (stred sestavy, stejne jako karoserie
// spec tabulka) - presnejsi umisteni nema geometricky anchor k dispozici,
// stejny limit jako u bocnich dveri.
function computeCarBodyWheelArchWidthDimensionSegments() {
  const out = [];
  groupCarBodyEntriesByBase().forEach(g => {
    const bEntry = g.B, sideEntry = g.L || g.R_D;
    if (!bEntry || !sideEntry) return;
    const spec = sideEntry.part && sideEntry.part.car_model_id != null ? KAROSERIE_SPECS[String(sideEntry.part.car_model_id)] : null;
    if (!spec || spec.official_wheel_arch_width_mm == null) return;
    const box = new THREE.Box3();
    [g.L, g.R_D, g.B].forEach(e => { if (e) { e.object3d.updateMatrixWorld(true); box.union(new THREE.Box3().setFromObject(e.object3d)); } });
    if (box.isEmpty()) return;
    const zOffsetMm = sideEntry._wheelArchZOffsetMm || 0;
    let midZ = (box.min.z + box.max.z) / 2 + zOffsetMm;
    midZ = Math.min(box.max.z, Math.max(box.min.z, midZ));
    const midXAll = (box.min.x + box.max.x) / 2;
    const half = spec.official_wheel_arch_width_mm / 2;
    const p0 = new THREE.Vector3(midXAll - half, box.min.y, midZ);
    const p1 = new THREE.Vector3(midXAll + half, box.min.y, midZ);
    out.push({ p0, p1, distMm: spec.official_wheel_arch_width_mm, source: spec.official_wheel_arch_width_source });
  });
  return out;
}
// Robert 2026-08-22 ("koty zadnich dveří jsou u nekterych modelů porad v
// predni casti, takze udelejme to ze je mohu ve vodorovne posunout") - male
// klikaci "⇄" tlacitko u kazde vlozene karoserie s vykreslenou kotou zadnich
// dveri, primo nad body vytazenou kotovaci carou (worldMid). Klik prehodi
// findCarBodyFarEdgeLocal() na druhy konec (viz sideEntry._doorKotaFlipped).
// Stejny "neviditelny kontejner + klikatelne prvky uvnitr" vzor jako
// #dimIssueCheckboxes/syncDimIssueCheckboxes vyse, jen vlastni ucel.
// (carBodyDoorFlipContainerEl/carBodyDoorFlipBtnEls jsou deklarovane vyse
// u carBodyDoorDimsEnabled - stejny TDZ duvod jako dimIssueContainerEl.)
function ensureCarBodyDoorFlipUi() {
  if (carBodyDoorFlipContainerEl) return carBodyDoorFlipContainerEl;
  carBodyDoorFlipContainerEl = document.createElement("div");
  carBodyDoorFlipContainerEl.id = "carBodyDoorFlipTargets";
  document.getElementById("viewport").appendChild(carBodyDoorFlipContainerEl);
  return carBodyDoorFlipContainerEl;
}
function syncCarBodyDoorFlipTargets() {
  if (!carBodyDoorDimsEnabled) {
    if (carBodyDoorFlipContainerEl && carBodyDoorFlipContainerEl.childElementCount) {
      carBodyDoorFlipContainerEl.innerHTML = "";
      carBodyDoorFlipBtnEls.clear();
    }
    return;
  }
  const groups = groupCarBodyEntriesByBase();
  const seen = new Set();
  const rect = renderer.domElement.getBoundingClientRect();
  groups.forEach((g, groupKey) => {
    const found = findCarBodyFarEdgeLocal(g);
    if (!found) return;
    found.sideEntry.object3d.updateMatrixWorld(true);
    const p0 = found.p0Local.clone().applyMatrix4(found.sideEntry.object3d.matrixWorld);
    const p1 = found.p1Local.clone().applyMatrix4(found.sideEntry.object3d.matrixWorld);
    const mid = p0.clone().add(p1).multiplyScalar(0.5);
    const ndc = mid.clone().project(camera);
    if (ndc.z < -1 || ndc.z > 1 || ndc.x < -1.3 || ndc.x > 1.3 || ndc.y < -1.3 || ndc.y > 1.3) return;
    seen.add(groupKey);
    let btn = carBodyDoorFlipBtnEls.get(groupKey);
    if (!btn) {
      btn = document.createElement("div");
      btn.className = "car-body-door-flip-btn";
      btn.textContent = "⇄";
      btn.title = "Kóta otvoru zadních dveří je na špatné straně? Klikni pro přehození na druhý konec karoserie.";
      btn.addEventListener("click", (ev) => {
        ev.stopPropagation();
        found.sideEntry._doorKotaFlipped = !found.sideEntry._doorKotaFlipped;
      });
      ensureCarBodyDoorFlipUi().appendChild(btn);
      carBodyDoorFlipBtnEls.set(groupKey, btn);
    }
    btn.style.left = ((ndc.x * 0.5 + 0.5) * rect.width) + "px";
    btn.style.top = ((-ndc.y * 0.5 + 0.5) * rect.height) + "px";
  });
  carBodyDoorFlipBtnEls.forEach((btn, key) => {
    if (!seen.has(key)) { btn.remove(); carBodyDoorFlipBtnEls.delete(key); }
  });
}
// Robert 2026-08-22 ("posuvník průhlednosti karoserie... při plné
// průhlednosti chceme karoserii zároveň schovat, aby nezatěžovala CPU"):
// pct = 0..100 "procento pruhlednosti" (0 = plne viditelna/nepruhledna,
// 100 = plne pruhledna). Pri pct>=100 se cely object3d rovnou schova
// (visible=false) - WebGLRenderer takove objekty preskoci uplne, coz
// usetri vykon narozdil od pouheho opacity:0 (material by se porad
// vykresloval, jen neviditelne). Stejny trik jiz pouziva
// generateCatalogThumbnails() pro docasne schovani cele sceny.
// Robert 2026-09-02 ("chci nějaké pomyslné stěny... jen jako linky, lehce
// možná rozmazané, kde rohy jdou do ztracena" -> "udělej mi grid živý
// model do scény, linky po cca 350 mm"): zjednoduseny VZHLED karoserie.
// Puvodni GLB soubory ani geometrie ve scene se NEMENI - jen se na
// meshe karoserie navlekne vlastni ShaderMaterial, ktery misto plne
// steny kresli mrizku linek (svisle + vodorovne po CAR_BODY_GRID_CELL_MM,
// promitane triplanarne podle prevazujici normaly, takze na bocnici i
// na podlaze/strope jsou rozestupy skutecnych 350 mm). Linky maji mekky
// (rozmazany) okraj a smerem k rohum/hranam kazde steny slabnou do
// ztracena (podle vzdalenosti k obalce dilu na ne-tenkych osach). Kresli
// se jen povrch privraceny k nakladovemu prostoru (test normaly proti
// stredu cele karoserie v LOKALNIM prostoru meshe - vnejsi plocha steny
// ~9 mm za nim by delala dvojite linky). Kolize (checkCarBodyCollisions -
// realna geometrie, BVH), koty dveri (findCarBodyFarEdgeLocal) i
// raycasting zustavaji beze zmeny - material na ne nema vliv.
//
// Material ma vlastnost `color` namapovanou na uniform uColor, aby s nim
// beze zmeny fungovalo setMeshesCollisionColor (cervena pri kolizi) i
// setSelectHighlight (oboji pracuji pres mat.color.getHex/setHex).
// Pruhlednost karoserie (#carBodyOpacitySlider) jde pres uniform
// uOpacity - u ShaderMaterialu renderer material.opacity sam neaplikuje.
const CAR_BODY_GRID_CELL_MM = 350;
const CAR_BODY_GRID_VERT = `
varying vec3 vPos; varying vec3 vNrm;
void main(){ vPos = position; vNrm = normal; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`;
const CAR_BODY_GRID_FRAG = `
precision highp float;
varying vec3 vPos; varying vec3 vNrm;
uniform vec3 uCenter; uniform vec3 uMin; uniform vec3 uMax;
uniform float uCell, uLw, uSoft, uFade, uAlpha, uEdgeMix, uOpacity; uniform vec3 uColor;
float lineDist(vec2 uv, vec2 d){ float f = fract(dot(uv, d)); return abs(f - 0.5); }
void main(){
  vec3 n = normalize(vNrm);
  if (dot(n, vPos - uCenter) > 0.0) discard; // jen vnitrni povrch steny
  vec3 an = abs(n); vec2 uv;
  if (an.x >= an.y && an.x >= an.z) uv = vPos.zy; else if (an.y >= an.z) uv = vPos.xz; else uv = vPos.xy;
  vec2 p = uv / uCell;
  float dEdge = min(lineDist(p, vec2(1.0, 0.0)), lineDist(p, vec2(0.0, 1.0))) * uCell; // mm k nejblizsi lince
  float aa = fwidth(dEdge) * 0.75;
  float core = 1.0 - smoothstep(uLw - aa, uLw + aa + uSoft, dEdge);      // jadro linky, mekky okraj
  float halo = (1.0 - smoothstep(uLw, uLw + uSoft * 3.0, dEdge)) * 0.25; // lehke rozmazani kolem
  float line = max(core, halo);
  // rohy do ztracena: utlum podle vzdalenosti k obalce dilu, po osach zvlast
  // (tenka osa = tloustka steny se nepocita); u rohu jsou male dva -> silny
  // utlum, u hrany jen jeden -> mirny utlum
  vec3 ext = uMax - uMin; vec3 dmin = vPos - uMin; vec3 dmax = uMax - vPos;
  float sMin = 1.0, sMax = 0.0; int cnt = 0;
  for (int k = 0; k < 3; k++) {
    float e = ext[k]; if (e < 120.0) continue;
    float fd = min(uFade, e * 0.45);
    float sk = smoothstep(0.0, fd, min(dmin[k], dmax[k]));
    sMin = min(sMin, sk); sMax = max(sMax, sk); cnt++;
  }
  float f = cnt == 0 ? 1.0 : max(sMax, 0.0) * mix(1.0, sMin, uEdgeMix);
  float a = line * f * uAlpha * uOpacity;
  if (a < 0.003) discard;
  gl_FragColor = vec4(uColor, a);
}`;
function makeCarBodyGridMaterial(mesh, centerLocal) {
  if (!mesh.geometry.boundingBox) mesh.geometry.computeBoundingBox();
  const bb = mesh.geometry.boundingBox;
  const mat = new THREE.ShaderMaterial({
    vertexShader: CAR_BODY_GRID_VERT,
    fragmentShader: CAR_BODY_GRID_FRAG,
    transparent: true,
    depthWrite: true,
    side: THREE.DoubleSide,
    extensions: { derivatives: true },
    uniforms: {
      uCenter: { value: centerLocal.clone() },
      uMin: { value: bb.min.clone() }, uMax: { value: bb.max.clone() },
      uCell: { value: CAR_BODY_GRID_CELL_MM },
      uLw: { value: 2.5 }, uSoft: { value: 4 }, uFade: { value: 450 }, uEdgeMix: { value: 0.35 },
      uAlpha: { value: 0.8 }, uOpacity: { value: 1 },
      // svetle sedomodra - 3D pozadi sceny je tmave (0x14161b / tmavy gradient),
      // tmava linka by na nem nebyla videt
      uColor: { value: new THREE.Color(0xb4bfcc) },
    },
  });
  mat.userData.isCarBodyGrid = true;
  Object.defineProperty(mat, "color", { get() { return this.uniforms.uColor.value; } });
  return mat;
}
// Stred cele karoserie (L+R_D+B dohromady, ve svetovych souradnicich) -
// pro test "vnitrni povrch" v shaderu; per skupina (viz
// groupCarBodyEntriesByBase), aby se vic karoserii ve scene nemichalo.
function carBodyGroupCentersWorld() {
  const centers = new Map(); // entry -> Vector3 (world)
  groupCarBodyEntriesByBase().forEach(g => {
    const entries = [g.L, g.R_D, g.B].filter(Boolean);
    const box = new THREE.Box3();
    entries.forEach(e => { e.object3d.updateMatrixWorld(true); box.union(new THREE.Box3().setFromObject(e.object3d)); });
    if (box.isEmpty()) return;
    const c = box.getCenter(new THREE.Vector3());
    entries.forEach(e => centers.set(e, c));
  });
  return centers;
}
// Navlekne/sundá mrizkovy material podle carBodyGridEnabled. Puvodni
// (standardni) material se pamatuje v mesh.userData.carBodyStdMaterial a
// pri vypnuti se vraci. V dratenych rezimech vykresleni (wireframe*) se
// mrizka nepouzije - tam uz applyPartMaterial kresli hrany sam.
function applyCarBodyGridMaterials() {
  // `let renderMode` je deklarovany az o par tisic radku nize a tahle
  // funkce bezi (pres applyCarBodyOpacity z animate()) uz pri prvnim
  // synchronnim behu - i `typeof` na TDZ promenne hodi ReferenceError,
  // proto try/catch (v tu chvili jeste stejne nejsou zadne karoserie).
  let rm = "rendered";
  try { rm = renderMode; } catch (e) { /* TDZ pri prvnim snimku */ }
  const wire = (rm === "wireframe" || rm === "wireframe_hidden");
  const useGrid = carBodyGridEnabled && !wire;
  const centers = useGrid ? carBodyGroupCentersWorld() : null;
  placed.forEach(entry => {
    if (!entry.part || entry.part.source !== "car_body") return;
    const cWorld = centers ? centers.get(entry) : null;
    entry.object3d.traverse(n => {
      if (!n.isMesh || !n.material) return;
      const isGrid = !!(n.material.userData && n.material.userData.isCarBodyGrid);
      if (useGrid && cWorld) {
        n.updateMatrixWorld(true);
        const cLocal = n.worldToLocal(cWorld.clone());
        if (isGrid) { n.material.uniforms.uCenter.value.copy(cLocal); return; }
        n.userData.carBodyStdMaterial = n.material;
        n.material = makeCarBodyGridMaterial(n, cLocal);
      } else if (isGrid) {
        const std = n.userData.carBodyStdMaterial;
        n.material.dispose();
        n.material = std || new THREE.MeshStandardMaterial({ color: 0x9aa0a6, side: THREE.DoubleSide, flatShading: true });
        n.userData.carBodyStdMaterial = null;
      }
    });
  });
}
function applyCarBodyOpacity(pct) {
  carBodyOpacityPct = pct;
  const opacityValue = 1 - pct / 100;
  const hide = pct >= 100;
  let count = 0;
  try { applyCarBodyGridMaterials(); } catch (e) { console.error("applyCarBodyGridMaterials selhalo (karoserie zustane s puvodnim materialem):", e); }
  placed.forEach(entry => {
    if (!entry.part || entry.part.source !== "car_body") return;
    count++;
    entry.object3d.visible = !hide;
    if (hide) return; // schovano - zbytecne mutovat material meshu, ktere se stejne nevykresli
    entry.object3d.traverse(n => {
      if (!n.isMesh || !n.material) return;
      const mats = Array.isArray(n.material) ? n.material : [n.material];
      mats.forEach(m => {
        if (m.userData && m.userData.isCarBodyGrid) {
          // mrizka je vzdy transparent+depthWrite (viz makeCarBodyGridMaterial),
          // pruhlednost jde jen do uniformu
          m.uniforms.uOpacity.value = opacityValue;
          return;
        }
        m.transparent = opacityValue < 1;
        m.opacity = opacityValue;
        m.depthWrite = opacityValue >= 1;
      });
    });
  });
  carBodyOpacityAppliedForCount = count;
}
// Robert 2026-08-22 ("chceme ve scene režim... kdy jakýkoli předmět
// prolne karoserii, tato zčervená"): pro kazdou skupinu karoserie
// (L/R_D/B) zkontroluje VSECHNY ostatni vlozene dily, jestli nektera
// jejich SKUTECNA hrana (trojuhelniky realne geometrie, ne jen
// ohranicujici box - box by u pootoceneho profilu falesne "naboural"
// stenu, i kdyz se dil ve skutecnosti vejde, presne stejna past jako
// jinde v tomto souboru s pivotem/connektory) protne nekterou stenu
// karoserie. Pri nalezenem prusidku obarvi VSECHNY steny dane skupiny
// cervene (docasne, puvodni barva se pamatuje v mesh.userData.origColorHex
// a vraci, jakmile prusecik zmizi).
//
// Vykon (Robert 2026-08-22, "trhá se pohyb" pak "je to nepresné" - viz
// ensureWallBoundsTree/BVH akcelerace vyse, ktera vyresila obe naraz):
// (a) levny AABB pre-filter pred raycastingem, (b) pocet testovanych
// hran na dil - COLLISION_MAX_EDGES_PER_PART, uz NENI potreba drasticky
// omezovat (dominantni naklady byly na strane steny, ne kandidata, viz
// BVH vyse) - vraceno na plnych 300 pro lepsi presnost i u kandidata,
// (c) throttle na kazdy COLLISION_CHECK_EVERY_N_FRAMES snimek - dilky
// BVH uz muze byt castejsi (10 misto puvodnich 15/30) a porad citelne
// rychlejsi nez puvodni bez-BVH verze, (d) computePlacedTransformFingerprint
// pred checkCarBodyCollisions preskoci CELY vypocet, kdyz se od
// posledni kontroly nic ve scene nehnulo (typicky rotace/pan kamerou).
const COLLISION_CHECK_EVERY_N_FRAMES = 10;
const COLLISION_MAX_EDGES_PER_PART = 300;
const COLLISION_AABB_MARGIN_MM = 50;
// meshWorldEdgeSample/ensureWallBoundsTree/setMeshesCollisionColor/
// objectCollidesWithWalls PRESUNUTY 2026-08-30 do js/scene-geometry-
// shared.js (Robert: "co umí 3D scéna skrze admina, musí umět Node.js
// skrze bota úplně stejně") - nacitaji se jako globaly stejne jako
// ostatni sdilene funkce (baseQuaternion, computeConnectorsLocal...),
// zadna zmena volajiciho kodu nize krome nahrazeni rucni smycky v
// checkCarBodyCollisions volanim objectCollidesWithWalls. Duvod k
// presunu: Node.js skripty pro umisteni sestav do karoserie (nohy T6/
// Jumpy) drive obsahovaly RUCNI kopii tehle logiky - presne riziko
// ticheho rozjeti, kteremu ma scene-geometry-shared.js jako celek
// predejit (viz jeho hlavicka). BVH vykonovy kontext (~2.3s bez BVH,
// ~35ms s BVH) i poznamka o korupci Box3().setFromObject() po
// computeBoundsTree() jsou zdokumentovane primo tam.
// Robert 2026-08-22 ("funguje ale je to náročné na zobrazování, trhá se
// pohyb... obnovovací frekvence?"): puvodni AABB pre-filter v praxi moc
// nefiltroval, protoze cely smysl teto funkce je stavet DOVNITR
// karoserie - vetsina dilu realne sestavy tak stejne skonci jako
// "kandidat" k drahemu raycastingu (az COLLISION_MAX_EDGES_PER_PART
// hran x pocet trojuhelniku steny BEZ prostorove akcelerace/BVH - zadna
// takova knihovna v projektu neni). Levny "otisk" (soucet pozic+rotaci
// vsech `placed`) pred drahym vypoctem - kdyz se od posledni USPESNE
// kontroly NIC nepohnulo (typicky: uzivatel jen otaci/pojizdi kamerou,
// nic netahne), cely drahy raycasting se preskoci. Behem SKUTECNEHO
// tazeni dilu se otisk meni kazdy snimek, takze tam tohle samo o sobe
// nepomuze - na to viz snizeny COLLISION_MAX_EDGES_PER_PART a vyssi
// COLLISION_CHECK_EVERY_N_FRAMES (viz komentare u obou konstant).
let carBodyCollisionLastFingerprint = null;
function computePlacedTransformFingerprint() {
  let sum = 0;
  for (const e of placed) {
    const p = e.object3d.position, q = e.object3d.quaternion;
    sum += p.x + p.y * 1.0001 + p.z * 1.0002 + q.x * 7 + q.y * 11 + q.z * 13 + q.w * 17;
  }
  return placed.length + "|" + sum.toFixed(3);
}
// Robert 2026-08-22 ("pokracuj tou kolizi karoserie s profilem"): sbira
// entries kolidujici v TOMHLE pruchodu napric VSEMI skupinami karoserie
// (jeden dil muze teoreticky kolidovat s vic karoseriemi soucasne, pro
// obarveni dilu na tom ale nezalezi - staci vedet "koliduje s necim").
function checkCarBodyCollisions() {
  const groups = groupCarBodyEntriesByBase();
  if (!groups.size) return;
  if (carBodyCollisionEnabled) {
    const fp = computePlacedTransformFingerprint();
    if (fp === carBodyCollisionLastFingerprint) return; // nic se od posledni kontroly nepohnulo
    carBodyCollisionLastFingerprint = fp;
  }
  if (!carBodyCollisionEnabled) {
    // Vypnuto - vratit barvu VSEM prave oznacenym dilum (ne jen stenam,
    // viz smycka nize), ne cekat, az prestanou kolidovat.
    carBodyCollisionFlaggedParts.forEach(entry => {
      const meshes = [];
      entry.object3d.traverse(n => { if (n.isMesh) meshes.push(n); });
      setMeshesCollisionColor(meshes, false);
    });
    carBodyCollisionFlaggedParts.clear();
  }
  const raycaster = new THREE.Raycaster();
  const collidingEntriesThisPass = new Set();
  groups.forEach(g => {
    const wallEntries = [g.L, g.R_D, g.B].filter(Boolean);
    if (!wallEntries.length) return;
    wallEntries.forEach(e => e.object3d.updateMatrixWorld(true));
    const wallMeshes = [];
    wallEntries.forEach(e => e.object3d.traverse(n => { if (n.isMesh) wallMeshes.push(n); }));
    if (!wallMeshes.length) return;
    if (!carBodyCollisionEnabled) { setMeshesCollisionColor(wallMeshes, false); return; }
    // BVH strom pro kazdou stenu (viz ensureWallBoundsTree) - jednou
    // vypocitany a cachovany, dal uz jen levne vyuzity globalnim patchem
    // THREE.Mesh.prototype.raycast (viz nahore v souboru).
    wallMeshes.forEach(ensureWallBoundsTree);
    const carBox = new THREE.Box3();
    wallEntries.forEach(e => carBox.union(new THREE.Box3().setFromObject(e.object3d)));
    carBox.expandByScalar(COLLISION_AABB_MARGIN_MM);

    let colliding = false;
    for (const entry of placed) {
      // Ochranne razitko se do kolizni kontroly nepocita. Logo lici se stenou
      // profilu a jeste kousek vycniva (relief), vypln drazky je naopak
      // ZAMERNE zanorena do drazky - obojim by razitko delalo prave to, co
      // kontrola hleda, aniz by slo o skutecnou vadu. Razitkuji se i bocni
      // steny (front+90/+270), tedy ty, ktere mohou mirit ke stene vozu, takze
      // by to cervenalo karoserii kvuli 3mm reliefu loga. (bot8 2026-09-11,
      // razitka jsou od tehoz dne primo v datech sestavy.)
      if (wallEntries.includes(entry) || (entry.part && entry.part.source === "car_body")
          || isStampPart(entry) || isKontrolniPart(entry)) continue;
      entry.object3d.updateMatrixWorld(true);
      const partBox = new THREE.Box3().setFromObject(entry.object3d);
      if (partBox.isEmpty() || !partBox.intersectsBox(carBox)) continue;
      const hitFound = objectCollidesWithWalls(entry.object3d, wallMeshes, COLLISION_MAX_EDGES_PER_PART, raycaster);
      if (hitFound) { colliding = true; collidingEntriesThisPass.add(entry); }
    }
    setMeshesCollisionColor(wallMeshes, colliding);
  });
  if (!carBodyCollisionEnabled) return;
  // Nove kolidujici dily oznacit cerveni, uz neoznacene (prestaly
  // kolidovat) vratit na puvodni barvu - jen ROZDIL oproti minulemu
  // pruchodu, ne kazdy dil znovu.
  collidingEntriesThisPass.forEach(entry => {
    if (carBodyCollisionFlaggedParts.has(entry)) return;
    const meshes = [];
    entry.object3d.traverse(n => { if (n.isMesh) meshes.push(n); });
    setMeshesCollisionColor(meshes, true);
    carBodyCollisionFlaggedParts.add(entry);
  });
  carBodyCollisionFlaggedParts.forEach(entry => {
    if (collidingEntriesThisPass.has(entry)) return;
    const meshes = [];
    entry.object3d.traverse(n => { if (n.isMesh) meshes.push(n); });
    setMeshesCollisionColor(meshes, false);
    carBodyCollisionFlaggedParts.delete(entry);
  });
}
// "Vrtaci koty" (Robert 2026-08-16: "kóty od konců profilů na středy os
// napojených profilů jsou Vrtací kóty, ty chceme taky") - vzdalenost od
// konce pruchoziho profilu ke STREDU/OSE protinajiciho profilu (ne k jeho
// stene) - relevantni pro vrtani, kde stred vrtaneho otvoru sedi na ose
// pripojovaneho dilu, ne na jeho kraji. Samostatny prepinac
// (drillingDimsEnabled), nezavisly na rezimu 1/2/3. Stejna oprava retezenim
// jako u computeJointDimensionSegments vyse - vic vrtacich bodu na jednom
// pruchozim profilu se ted kotuje jako navazujici retezec (kraj->otvor1,
// otvor1->otvor2, ...), ne jako prekryvajici se nezavisle kotovane dvojice.
function computeDrillingDimensionSegments() {
  const out = [];
  if (typeof drillingDimsEnabled === "undefined" || !drillingDimsEnabled) return out;

  // OSA DELKY REGALU - potreba pro rozliseni CELNI/BOCNI kóty na noze.
  // Robert 2026-09-10: "celni kota souvisi s prickou, bocni kota navazuje na
  // nosnik". Nosniky bezi PODEL regalu, pricky/spojnice NAPRIC jeho hloubkou.
  // Smer delky se odvodi z rozmisteni SVISLYCH profilu (noh): vodorovna osa,
  // ve ktere jsou nohy rozprostrene nejvic, je delka regalu. Nezavisle na tom,
  // jak je regal ve svete natoceny.
  function osaDelkyRegalu() {
    let minX = Infinity, maxX = -Infinity, minZ = Infinity, maxZ = -Infinity, n = 0;
    placed.forEach(e => {
      if (!e.part || !isProfilePart(e.part)) return;
      const a = (typeof profileAxisInfo === "function") ? profileAxisInfo(e) : null;
      if (!a || Math.abs(a.axisDir.y) < 0.9) return;      // jen svisle = nohy
      const p = a.axisA;
      minX = Math.min(minX, p.x); maxX = Math.max(maxX, p.x);
      minZ = Math.min(minZ, p.z); maxZ = Math.max(maxZ, p.z);
      n++;
    });
    if (n < 2) return "z";                                 // nedost dat - rozumny default
    return (maxX - minX) > (maxZ - minZ) ? "x" : "z";
  }
  const delkaOsa = osaDelkyRegalu();

  // Surove dvojice (bez slucovani) - na noze potrebujeme KAZDY napojeny dil
  // zvlast. Slucovani intervalu by nosnik a spojnici ve STEJNE VYSCE spojilo
  // do jednoho, prestoze jsou to dva RUZNE otvory ve dvou ruznych stenach
  // (jeden celni, jeden bocni) - presne to, co ma byt ve dvou radach.
  const syroveDleProfilu = new Map();
  findProfileJointCandidates().forEach(k => {
    let l = syroveDleProfilu.get(k.throughProf);
    if (!l) { l = []; syroveDleProfilu.set(k.throughProf, l); }
    l.push(k);
  });

  groupJointCandidatesByThroughProfile().forEach(({ axis, intervals }, throughProf) => {
    const jeNoha = Math.abs(axis.axisDir.y) > 0.9;

    if (jeNoha) {
      // PRAVIDLA PRO NOHU (Robert 2026-09-10):
      //  * "vrtaji se nohy / vrtaci bod na noze je ten, kde ma napojeny profil
      //    svuj stred" -> kotuje se na OSU napojeneho dilu
      //  * "vzdy absolutni" -> kazda kota od jedne zakladny, ne po retezu
      //  * "vrtaci koty nohy kotujeme od spodni hrany" -> zakladna je SPODNI
      //    konec nohy (osa profilu muze byt ulozena i obracene)
      //  * "vrtaci koty se bud celni nebo bocni, tzn 2 rady, znac u toho c
      //    nebo b" + "celni kota souvisi s prickou, bocni kota navazuje na
      //    nosnik" -> dve rady, oznacene "c" a "b"
      //  * konec profilu NENI vrtaci bod -> zadna kota na horni konec
      const axisANahore = axis.axisDir.y < 0;
      const spodniPt = axisANahore
        ? axis.axisA.clone().addScaledVector(axis.axisDir, axis.L)
        : axis.axisA.clone();
      const videno = new Set();
      (syroveDleProfilu.get(throughProf) || []).forEach(k => {
        const t = (k.fp.t0 + k.fp.t1) / 2;
        if (t < 0 || t > axis.L) return;
        const odSpodu = axisANahore ? (axis.L - t) : t;
        const distMm = Math.round(odSpodu);
        if (distMm < 1) return;
        // Rada podle vlastni osy napojeneho dilu: bezi-li PODEL regalu, je to
        // nosnik/podelnik -> BOCNI; jinak pricka/spojnice -> CELNI.
        const ao = (typeof profileAxisInfo === "function") ? profileAxisInfo(k.otherProf) : null;
        let znak = "č";
        if (ao) {
          const podelDelky = delkaOsa === "x" ? Math.abs(ao.axisDir.x) : Math.abs(ao.axisDir.z);
          if (podelDelky > 0.7) znak = "b";
        }
        const klic = znak + "|" + distMm;
        if (videno.has(klic)) return;      // dva dily tehoz smeru = jeden otvor
        videno.add(klic);

        // Robert 2026-09-10 ("koty v miste pomyslnych vrtacich otvoru"):
        // bod kóty MUSI lezet na STENE, do ktere se vrta, ne na ose profilu.
        // Otvor je tam, kde se napojeny dil dotyka nohy - tedy na te jeji
        // stene, ktera k nemu miri. Posune se proto CELA kota (spodni bod
        // i bod otvoru) o polovinu prurezu nohy tim smerem; kotovaci cara
        // pak bezi PODEL te steny.
        //
        // Vedlejsi zisk, kvuli kteremu to stoji za to: celni a bocni rada
        // tim lezi na DVOU RUZNYCH stranach nohy a jsou odlisene i
        // prostorove, nejen pismenem a barvou.
        const bodOsy = axis.axisA.clone().addScaledVector(axis.axisDir, t);
        let posun = new THREE.Vector3();
        try {
          const boxDilu = new THREE.Box3().setFromObject(k.otherProf.object3d);
          const stredDilu = boxDilu.getCenter(new THREE.Vector3());
          const smer = stredDilu.sub(bodOsy);
          smer.addScaledVector(axis.axisDir, -smer.dot(axis.axisDir));  // slozka kolmo na osu nohy
          if (smer.lengthSq() > 1e-9) {
            smer.normalize();
            const boxNohy = new THREE.Box3().setFromObject(throughProf.object3d);
            const vel = boxNohy.getSize(new THREE.Vector3());
            // polovina prurezu nohy ve smeru "smer" (oporna funkce AABB)
            const polovina = 0.5 * (Math.abs(smer.x) * vel.x + Math.abs(smer.y) * vel.y + Math.abs(smer.z) * vel.z);
            posun = smer.multiplyScalar(polovina);
          }
        } catch (e) { /* bez posunu - kota zustane na ose, radeji nez zadna */ }

        out.push({
          p0: spodniPt.clone().add(posun),
          p1: bodOsy.clone().add(posun),
          distMm,
          znak,
        });
      });
      return;
    }

    // LUZKO A OSTATNI VODOROVNE PROFILY - PUVODNI CHOVANI, NESAHAT.
    // Retezeni si vyzadal Robert 2026-08-16 a 2026-09-10 vyslovne rekl
    // "pravidlo pro luzko nech byt nyni" / "nech luzko na pokoji".
    let cursor = 0;
    const cursorPt = () => axis.axisA.clone().addScaledVector(axis.axisDir, cursor);
    intervals.forEach(iv => {
      const t = (iv.t0 + iv.t1) / 2;
      const distMm = Math.round(t - cursor);
      if (distMm >= 1) out.push({ p0: cursorPt(), p1: axis.axisA.clone().addScaledVector(axis.axisDir, t), distMm });
      cursor = t;
    });
    const tailMm = Math.round(axis.L - cursor);
    if (tailMm >= 1) out.push({ p0: cursorPt(), p1: axis.axisA.clone().addScaledVector(axis.axisDir, axis.L), distMm: tailMm });
  });
  return out;
}
// Robert 2026-08-16 ("nech verze 3 kotuje i prurez profilu... technicke
// kotovani verzi 2 a 3 nejede"): kota prurezu jako sipkova cara mezi
// dvema PROTILEHLYMI "face" konektory profilu (normaly miri presne
// proti sobe) - dava dve kolme kotovane vzdalenosti (sirka+vyska
// prurezu), presne jako u kotovani sirky/vysky desky vyse.
function computeCrossSectionDimensionSegments() {
  const out = [];
  if (dimMode < 3) return out;
  placed.forEach(entry => {
    if (!entry.part || !isProfilePart(entry.part)) return;
    const world = worldConnectorsOf(entry);
    const faces = [];
    // Robert 2026-08-16 (screenshot - "X" prekrizene 40mm koty u konce
    // profilu): "face" konektory NEJSOU jen 4 bocni steny uprostred delky
    // (viz computeConnectorsLocal) - u dilu s naucenymi geo_faces
    // (isGeoFace:true, "🎓 Naucit napojeni") pribyvaji dalsi "face"
    // konektory KDEKOLI na geometrii, casto poblíž konců profilu (mistni
    // dosedaci plochy pro prislusenstvi). Parovani nize podle normaly bez
    // kontroly polohy podel delky pak klidne sparovalo box-stenu uprostred
    // s naucenou plochou u konce (nebo dve naucene plochy u ruznych konců)
    // - vysledna cara vedla napric delkou profilu misto kolmo na prurez.
    // Prurezova kota ma zobrazovat skutecny prurez dilu (40x40mm apod.) -
    // k tomu staci vzdy presne 4 puvodni box-face konektory, ucene plochy
    // sem nepatri.
    world.forEach((c, idx) => { if (c.kind === "face" && !c.isGeoFace) faces.push(c); });
    // Robert 2026-08-16 ("zelene koty maji byt na konci profilu"): box-face
    // konektory lezi presne v polovine delky profilu (viz
    // computeConnectorsLocal - faceNormal je vzdy KOLMY na delkovou osu,
    // takze se podel ni vubec neposune) - kota tak visela uprostred dilu,
    // kde v sikmych pohledech vizualne krizila ostatni koty a pusobila
    // jako "X".
    const axis = (typeof profileAxisInfo === "function") ? profileAxisInfo(entry) : null;
    // Robert 2026-08-16 (dalsi screenshoty: "musis se to rozdelit, ktere
    // koty se zobrazi na kterem konci, nebo rovnou na tom volnem, kde
    // nejsou zadne profily, pravidlo je davat koty tak aby se
    // neprebijeli" -> pak "neprobehlo to na vsech profilech sceny", X
    // porad videt u husteho vicebodoveho spoje): proste presunuti VZDY
    // na stejny konec (axisA) nahradilo "vsechny uprostred" za "vsechny
    // na jednom konci", pak jsem to zmenil na volny konec - ale u
    // KRATKYCH kusu poblíž husteho spoje (typicky prave u slozitych
    // krizovatek vic profilu) maji OBA konce spoj (sevreny mezi dvema
    // spoji) A ZAROVEN je i ten "volny" konec porad fyzicky blizko
    // stejneho preplneneho mista - zadny fallback bod na tomhle kratkem
    // useku neni skutecne "volny prostor". Misto vynuceneho fallbacku
    // (stred, ktery se v takove situaci porad kryl s ostatnimi kotami)
    // se prurezova kota u profilu s OBEMA obsazenymi konci radeji VUBEC
    // NEKRESLI - hodnota 40mm uz je vic nez dostatecne videt na
    // desitkach jinych profilu se skutecne volnym koncem ve scene,
    // netreba ji za každou cenu vecpat i do nejhustsiho mista.
    let anchorT = null;
    if (axis) {
      const endIdxs = [];
      entry.connectorsLocal.forEach((c, i) => { if (c.kind === "end") endIdxs.push(i); });
      if (endIdxs.length === 2 && typeof profileEndIsFree === "function") {
        const startFree = profileEndIsFree(entry, endIdxs[0]);
        const farFree = profileEndIsFree(entry, endIdxs[1]);
        if (startFree) anchorT = 0;
        else if (farFree) anchorT = axis.L;
        // jinak (oba konce obsazene) anchorT zustava null -> viz skip nize
      } else {
        anchorT = axis.L / 2; // nestandardni pocet "end" konektoru - stara pojistka
      }
    }
    if (axis && anchorT === null) return; // oba konce obsazene - radeji vynechat nez kupit na stred
    const anchorAt = (pt) => {
      if (!axis) return pt;
      const rel = pt.clone().sub(axis.axisA);
      const along = rel.dot(axis.axisDir);
      const perp = rel.clone().sub(axis.axisDir.clone().multiplyScalar(along));
      return axis.axisA.clone().addScaledVector(axis.axisDir, anchorT).add(perp);
    };
    const used = new Set();
    for (let i = 0; i < faces.length; i++) {
      if (used.has(i)) continue;
      for (let j = i + 1; j < faces.length; j++) {
        if (used.has(j) || faces[i].normal.dot(faces[j].normal) >= -0.9) continue;
        used.add(i); used.add(j);
        const distMm = Math.round(faces[i].point.distanceTo(faces[j].point));
        if (distMm > 0) out.push({ p0: anchorAt(faces[i].point), p1: anchorAt(faces[j].point), distMm });
        break;
      }
    }
  });
  return out;
}
function refreshDimPairLabels() {
  dimPairLabelEntries.forEach(d => d.el.remove());
  dimPairLabelEntries = [];
  // Robert 2026-09-10: "kdyz zatrhnu vrtaci koty, musi se zobrazovat jen
  // vrtaci koty" - zapnuta fajfka Vrtaci koty schova ostatni kotovaci vrstvy.
  if (typeof drillingDimsEnabled !== "undefined" && drillingDimsEnabled) return;
  if (dimMode < 2) return;
  const container = document.getElementById("dimLabelsExtra");
  computeJointDimensionSegments().forEach(({ p0, p1, distMm }) => {
    const el = document.createElement("div");
    el.className = "dim-label";
    el.style.color = "#7ad1ff"; el.style.borderColor = "#7ad1ff66";
    el.textContent = distMm + " mm";
    container.appendChild(el);
    dimPairLabelEntries.push({ el, worldPoint: p0.clone().add(p1).multiplyScalar(0.5) });
  });
}
function updateDimPairLabelPositions() {
  if (!dimPairLabelEntries.length) return;
  const rect = renderer.domElement.getBoundingClientRect();
  dimPairLabelEntries.forEach(({ el, worldPoint }) => {
    const ndc = worldPoint.clone().project(camera);
    if (ndc.z < -1 || ndc.z > 1 || ndc.x < -1.3 || ndc.x > 1.3 || ndc.y < -1.3 || ndc.y > 1.3) { el.style.display = "none"; return; }
    el.style.display = "block";
    el.style.left = ((ndc.x * 0.5 + 0.5) * rect.width) + "px";
    el.style.top = ((-ndc.y * 0.5 + 0.5) * rect.height) + "px";
  });
}

function refreshDimLabels() {
  dimLabelEntries.forEach(d => d.el.remove());
  dimLabelEntries = [];
  crossSectionLabelEntries.forEach(d => d.el.remove());
  crossSectionLabelEntries = [];
  // viz refreshDimPairLabels - Vrtaci koty jsou vyhradni vrstva.
  if (typeof drillingDimsEnabled !== "undefined" && drillingDimsEnabled) return;
  const container = document.getElementById("dimLabels");
  const extraContainer = document.getElementById("dimLabelsExtra");
  placed.forEach(entry => {
    const el = document.createElement("div");
    el.className = "dim-label";
    container.appendChild(el);
    dimLabelEntries.push({ entry, el });
    if (entry.part && isProfilePart(entry.part)) {
      const csEl = document.createElement("div");
      csEl.className = "dim-label";
      csEl.style.color = "#8fe08f"; csEl.style.borderColor = "#8fe08f66";
      extraContainer.appendChild(csEl);
      crossSectionLabelEntries.push({ entry, el: csEl });
    }
  });
  updateDimLabelPositions();
  updateCrossSectionLabelPositions();
  refreshDimPairLabels();
  updateDimPairLabelPositions();
  refreshDrillingDimLabels();
  updateDrillingDimLabelPositions();
  // Cislovani dilu (viz refreshPartNumberLabels nize) se prekresluje ve
  // stejnych chvilich jako koty (pridani/odebrani dilu, vycisteni sceny) -
  // proto se to zavola primo odsud, misto abychom hledali a upravovali
  // vsechna mista, kde se refreshDimLabels() vola (je jich pres 10).
  refreshPartNumberLabels();
}

// Robert 2026-08-16 ("Vrtaci koty... budou se zobrazovat samostatne") -
// stejny DOM-popiskovy princip jako refreshDimPairLabels, jen vlastni
// kontejner/prepinac (drillingDimsEnabled), nezavisly na dimMode.
function refreshDrillingDimLabels() {
  drillingDimLabelEntries.forEach(d => d.el.remove());
  drillingDimLabelEntries = [];
  if (!drillingDimsEnabled) return;
  const container = document.getElementById("dimLabelsDrilling");
  computeDrillingDimensionSegments().forEach(({ p0, p1, distMm, znak }) => {
    const el = document.createElement("div");
    el.className = "dim-label";
    el.style.color = "#e0a04a"; el.style.borderColor = "#e0a04a66";
    // Robert 2026-09-10: "rozlisil bych vrtaci koty celni/bocni podle barvy"
    // -> "pismenem i barvou". Cela rada (pricky/spojnice) a bocni (nosniky/
    // podelniky) maji tedy jinou znacku i jinou barvu popisku. Vodorovne
    // profily (luzko) znacku nemaji a drzi si puvodni oranzovou.
    if (znak === "č") { el.style.color = "#4ad1a0"; el.style.borderColor = "#4ad1a066"; }
    else if (znak === "b") { el.style.color = "#d17ad1"; el.style.borderColor = "#d17ad166"; }
    el.textContent = (znak ? znak + " " : "") + distMm + " mm";
    container.appendChild(el);
    // Robert 2026-09-10: popisek patri K OTVORU. U nohy (znak c/b) se kota
    // meri absolutne od spodni hrany, takze stred kotovaci cary lezi nekde
    // v polovine vysky a s otvorem nema nic spolecneho - popisek proto sedi
    // na koncovem bodu (p1 = otvor). U luzka jsou koty retezene MEZI dvema
    // otvory, tam stred cary spravny je a zustava.
    drillingDimLabelEntries.push({
      el,
      worldPoint: znak ? p1.clone() : p0.clone().add(p1).multiplyScalar(0.5),
    });
  });
}
function updateDrillingDimLabelPositions() {
  if (!drillingDimLabelEntries.length) return;
  const rect = renderer.domElement.getBoundingClientRect();
  drillingDimLabelEntries.forEach(({ el, worldPoint }) => {
    const ndc = worldPoint.clone().project(camera);
    if (ndc.z < -1 || ndc.z > 1 || ndc.x < -1.3 || ndc.x > 1.3 || ndc.y < -1.3 || ndc.y > 1.3) { el.style.display = "none"; return; }
    el.style.display = "block";
    el.style.left = ((ndc.x * 0.5 + 0.5) * rect.width) + "px";
    el.style.top = ((-ndc.y * 0.5 + 0.5) * rect.height) + "px";
  });
}
document.getElementById("toggleDrillingDims").addEventListener("change", (e) => {
  drillingDimsEnabled = e.target.checked;
  const drillEl = document.getElementById("dimLabelsDrilling");
  if (drillEl) drillEl.style.display = drillingDimsEnabled ? "block" : "none";
  try { localStorage.setItem("konfShowDrillingDims", drillingDimsEnabled ? "1" : "0"); } catch (err) { /* ignoruj (napr. soukromy rezim) */ }
  // Vrtaci koty jsou VYHRADNI vrstva (Robert 2026-09-10: "kdyz zatrhnu
  // vrtaci koty, musi se zobrazovat jen vrtaci koty") - prepnuti fajfky
  // proto musi prekreslit i OSTATNI vrstvy, jinak by pri zapnuti zustaly
  // viset na obrazovce a pri vypnuti by se nevratily.
  if (typeof refreshDimLabels === "function") refreshDimLabels();
  if (typeof refreshDimPairLabels === "function") refreshDimPairLabels();
  refreshDrillingDimLabels();
  updateDrillingDimLabelPositions();
  if (typeof updateDimLabelPositions === "function") updateDimLabelPositions();
});
(function () {
  try {
    const saved = localStorage.getItem("konfShowDrillingDims");
    if (saved === null) return;
    const on = saved === "1";
    const cb = document.getElementById("toggleDrillingDims");
    if (cb) cb.checked = on;
    drillingDimsEnabled = on;
  } catch (e) { /* ignoruj */ }
})();
// Robert 2026-08-22 ("zatržíko pro koty karoserie nech platí i pro
// popis karoserie"): text/tabulka popisek (specSprite - "Rozměry/
// Rozvor/Ložný prostor/Objem", viz insertCustomShape) se dosud
// zobrazoval VZDY, nezávisle na zatržítku "🚐 Kóty karoserie" - teď
// sdílí stejnou viditelnost. Popisky jsou označené
// userData.isCarBodySpecLabel (nastaveno při vytvoření v
// insertCustomShape), aby se rozlišily od ostatních sceneTextLabels
// (srovnávací galerie apod.), které tímhle zatržítkem nejsou dotčené.
function applyCarBodySpecLabelVisibility() {
  sceneTextLabels.forEach(s => {
    if (s.userData && s.userData.isCarBodySpecLabel) s.visible = carBodyDoorDimsEnabled;
  });
}
// Robert 2026-08-22 ("popis karoserie zustava viset když se karoserie
// smaže, musí taky zmizet"): dily se muzou smazat vice ruznymi cestami
// (removeLast/deleteSelectedEntries/krok zpet...) - misto opravovani
// kazde z nich zvlast tohle bezi jako sdilena kontrola kazdy snimek
// (viz volani v updateLiveTechnicalDimensions): kdyz uz ZADNY z dilu,
// ktere popisek popisoval (ownerEntries, viz insertCustomShape), neni
// v `placed`, popisek se uklidi (scene.remove + dispose, at nezustane
// v pameti). Levne - poctem karoserii/dilu v realne scene zanedbatelne,
// nema smysl slozitejsi "count changed" branu jako u applyCarBodyOpacity.
function sweepOrphanedCarBodySpecLabels() {
  for (let i = sceneTextLabels.length - 1; i >= 0; i--) {
    const s = sceneTextLabels[i];
    if (!s.userData || !s.userData.isCarBodySpecLabel) continue;
    const owners = s.userData.ownerEntries || [];
    if (owners.some(e => placed.includes(e))) continue; // aspon jeden dil porad existuje
    scene.remove(s);
    s.material.map.dispose();
    s.material.dispose();
    sceneTextLabels.splice(i, 1);
  }
}
document.getElementById("toggleCarBodyDoorDims").addEventListener("change", (e) => {
  carBodyDoorDimsEnabled = e.target.checked;
  try { localStorage.setItem("konfShowCarBodyDoorDims", carBodyDoorDimsEnabled ? "1" : "0"); } catch (err) { /* ignoruj (napr. soukromy rezim) */ }
  // zadny vlastni HTML kontejner k prepnuti (na rozdil od vrtacich kot) -
  // koty dveri karoserie jedou vyhradne pres extraLines/drawDimensionOverlay
  // canvas (viz updateLiveTechnicalDimensions), ten uz bezi kazdy snimek.
  applyCarBodySpecLabelVisibility();
});
(function () {
  try {
    const saved = localStorage.getItem("konfShowCarBodyDoorDims");
    if (saved === null) return;
    const on = saved === "1";
    const cb = document.getElementById("toggleCarBodyDoorDims");
    if (cb) cb.checked = on;
    carBodyDoorDimsEnabled = on;
  } catch (e) { /* ignoruj */ }
})();
// Robert 2026-08-22 ("posuvník průhlednosti karoserie... při plné
// průhlednosti schovat, aby nezatěžovala CPU") - viz applyCarBodyOpacity.
// Neperzistuje se do localStorage (stejny vzor jako #explodeSlider vedle
// nej - docasne nastaveni pro aktualni sezeni, ne trvala preference).
document.getElementById("carBodyOpacitySlider").addEventListener("input", (e) => {
  applyCarBodyOpacity(parseFloat(e.target.value));
});
// Robert 2026-09-02 ("grid živý model do scény, linky po cca 350 mm") -
// viz applyCarBodyGridMaterials. Vychozi VYPNUTO (vzorek na vyzadani),
// perzistuje se.
document.getElementById("toggleCarBodyGrid").addEventListener("change", (e) => {
  carBodyGridEnabled = e.target.checked;
  try { localStorage.setItem("konfCarBodyGrid", carBodyGridEnabled ? "1" : "0"); } catch (err) { /* ignoruj */ }
  applyCarBodyOpacity(carBodyOpacityPct);
});
(function () {
  try {
    const saved = localStorage.getItem("konfCarBodyGrid");
    if (saved === null) return;
    const on = saved === "1";
    const cb = document.getElementById("toggleCarBodyGrid");
    if (cb) cb.checked = on;
    carBodyGridEnabled = on;
  } catch (e) { /* ignoruj */ }
})();
// Robert 2026-08-22 ("chceme ve scene režim... kdy jakýkoli předmět
// prolne karoserii, tato zčervená") - viz checkCarBodyCollisions.
// Vychozi VYPNUTO, ale perzistuje se (stejny vzor jako toggleCarBodyDoorDims) -
// kdyz uz si ho Robert jednou zapne, at zustane zapnuty i priste.
document.getElementById("toggleCarBodyCollision").addEventListener("change", (e) => {
  carBodyCollisionEnabled = e.target.checked;
  try { localStorage.setItem("konfShowCarBodyCollision", carBodyCollisionEnabled ? "1" : "0"); } catch (err) { /* ignoruj */ }
  if (!carBodyCollisionEnabled) {
    checkCarBodyCollisions(); // hned vratit puvodni barvy, necekat na dalsi throttle tick
  } else {
    // Zapnuti po predchozim vypnuti: barvy byly vratky vyse bez ohledu
    // na skutecny stav kolize, takze stary "otisk" uz neodpovida tomu,
    // co je zrovna VIDET (cerveny stav se vypnutim ztratil) - vynutit
    // realny prepocet i kdyby se mezitim nic nehnulo.
    carBodyCollisionLastFingerprint = null;
  }
});
(function () {
  try {
    const saved = localStorage.getItem("konfShowCarBodyCollision");
    if (saved === null) return;
    const on = saved === "1";
    const cb = document.getElementById("toggleCarBodyCollision");
    if (cb) cb.checked = on;
    carBodyCollisionEnabled = on;
  } catch (e) { /* ignoruj */ }
})();

function updateDimLabelPositions() {
  if (!dimLabelEntries.length) return;
  const rect = renderer.domElement.getBoundingClientRect();
  dimLabelEntries.forEach(({ entry, el }) => {
    const worldConns = worldConnectorsOf(entry);
    // Robert 2026-08-07 ("postavit 2D protahovani pro desky") - deska
    // nema "end" konektory (ma "edge", 2 nezavisle osy sirka+vyska),
    // takze potrebuje vlastni vetev - "šířka × výška mm" misto jedine
    // delky, stred = prumer vsech 4 hranovych bodu.
    let mid, labelText;
    if (entry.part && entry.part.is_board_material) {
      const widthIdx = [], heightIdx = [];
      entry.connectorsLocal.forEach((c, i) => { if (c.kind === "edge") (c.axis === "width" ? widthIdx : heightIdx).push(i); });
      if (widthIdx.length < 2 || heightIdx.length < 2) { el.style.display = "none"; return; }
      const widthMm = Math.round(worldConns[widthIdx[0]].point.distanceTo(worldConns[widthIdx[1]].point));
      const heightMm = Math.round(worldConns[heightIdx[0]].point.distanceTo(worldConns[heightIdx[1]].point));
      mid = worldConns[widthIdx[0]].point.clone().add(worldConns[widthIdx[1]].point)
        .add(worldConns[heightIdx[0]].point).add(worldConns[heightIdx[1]].point).multiplyScalar(0.25);
      labelText = widthMm + " × " + heightMm + " mm";
    } else {
      const endIdx = [];
      entry.connectorsLocal.forEach((c, i) => { if (c.kind === "end") endIdx.push(i); });
      if (endIdx.length < 2) {
        // Robert 2026-08-16 ("rezimy kotovani... 3) ad 2 plus koty dilu",
        // pak "nech verze 3 se zobrazuje jen ve 2D pohledech"):
        // prislusenstvi/spojky (nemaji 2 "end" konektory jako profil) se
        // driv vzdy schovaly - v rezimu 3 misto toho ukaz rozmer obalky
        // (W×H×D), stejny princip jako u desky vyse. Jen ve 2D pohledech -
        // stejny is2D test jako existujici Technicke kotovani
        // (updateLiveTechnicalDimensions) - v 3D perspektive by se to jen
        // "mihalo" pri otaceni kamerou, stejny duvod jako u tamtoho.
        const is2DNow = typeof viewModeSelectEl !== "undefined" && viewModeSelectEl && viewModeSelectEl.value !== "3d";
        if (dimMode >= 3 && is2DNow && entry.part && !isProfilePart(entry.part) && !entry.part.is_board_material) {
          entry.object3d.updateMatrixWorld(true);
          const bb = new THREE.Box3().setFromObject(entry.object3d);
          if (bb.isEmpty()) { el.style.display = "none"; return; }
          const size = bb.getSize(new THREE.Vector3());
          mid = bb.getCenter(new THREE.Vector3());
          labelText = `${Math.round(size.x)}×${Math.round(size.y)}×${Math.round(size.z)} mm`;
        } else {
          el.style.display = "none"; return;
        }
      } else {
        const p0 = worldConns[endIdx[0]].point, p1 = worldConns[endIdx[1]].point;
        mid = p0.clone().add(p1).multiplyScalar(0.5);
        labelText = Math.round(p0.distanceTo(p1)) + " mm";
      }
    }
    const ndc = mid.clone().project(camera);
    if (ndc.z < -1 || ndc.z > 1 || ndc.x < -1.3 || ndc.x > 1.3 || ndc.y < -1.3 || ndc.y > 1.3) {
      el.style.display = "none";
      return;
    }
    el.style.display = "block";
    el.style.left = ((ndc.x * 0.5 + 0.5) * rect.width) + "px";
    el.style.top = ((-ndc.y * 0.5 + 0.5) * rect.height) + "px";
    el.textContent = labelText;
  });
}

// Robert 2026-08-16 ("nech verze 3 kotuje i prurez profilu ve 2D
// pohledech"): navic k delkove kote (updateDimLabelPositions vyse) - u
// KAZDEHO profilu popisek prurezu (Š×V mm) primo z jiz znameho
// part.cross_section_mm (zadna nova geometrie), u jednoho konce, jen v
// rezimu 3 a jen ve 2D pohledech (stejny is2D test jako u ostatnich
// 2D-only kot v tomhle souboru).
function updateCrossSectionLabelPositions() {
  if (!crossSectionLabelEntries.length) return;
  const is2DNow = typeof viewModeSelectEl !== "undefined" && viewModeSelectEl && viewModeSelectEl.value !== "3d";
  if (dimMode < 3 || !is2DNow) {
    crossSectionLabelEntries.forEach(({ el }) => { el.style.display = "none"; });
    return;
  }
  const rect = renderer.domElement.getBoundingClientRect();
  crossSectionLabelEntries.forEach(({ entry, el }) => {
    const cs = entry.part && entry.part.cross_section_mm;
    if (!cs || cs[0] == null || cs[1] == null) { el.style.display = "none"; return; }
    const endIdx = [];
    entry.connectorsLocal.forEach((c, i) => { if (c.kind === "end") endIdx.push(i); });
    if (!endIdx.length) { el.style.display = "none"; return; }
    const endPt = worldConnectorsOf(entry)[endIdx[0]].point;
    const ndc = endPt.clone().project(camera);
    if (ndc.z < -1 || ndc.z > 1 || ndc.x < -1.3 || ndc.x > 1.3 || ndc.y < -1.3 || ndc.y > 1.3) { el.style.display = "none"; return; }
    el.style.display = "block";
    el.style.left = ((ndc.x * 0.5 + 0.5) * rect.width) + "px";
    // mala odchylka nad koncovy bod, at nesplyva s delkovou kotou/koncem dilu
    el.style.top = ((-ndc.y * 0.5 + 0.5) * rect.height - 16) + "px";
    el.textContent = `${Math.round(cs[0])}×${Math.round(cs[1])} mm`;
  });
}

document.getElementById("toggleDims").addEventListener("change", (e) => {
  // Robert 2026-08-16 ("ted se zase zobrazuji koty i kdyz neni zatrzitko
  // aktivni! delejte to dusledne!"): #dimLabelsExtra (rezim 2/3 kóty)
  // pridany dnes vubec NEsledoval tuhle fajfku - opraveno, ridi se
  // DUSLEDNE stejne jako puvodni #dimLabels, na obou mistech nize.
  document.getElementById("dimLabels").style.display = e.target.checked ? "block" : "none";
  const extraEl = document.getElementById("dimLabelsExtra");
  if (extraEl) extraEl.style.display = e.target.checked ? "block" : "none";
  try { localStorage.setItem("konfShowDims", e.target.checked ? "1" : "0"); } catch (err) { /* ignoruj (napr. soukromy rezim) */ }
});

// Obnoveni ulozeneho stavu zatrzitka "Koty (mm)" pri nacteni stranky -
// drive se HTML atribut "checked" (vzdy zapnuto) nikdy nesynchronizoval
// se skutecnou viditelnosti #dimLabels, takze koty po kazdem znovunacteni
// naskocily zpet, i kdyz je Robert predtim vypnul.
(function () {
  try {
    const saved = localStorage.getItem("konfShowDims");
    if (saved === null) return; // zatim nic ulozeno - necháme vychozi (zapnuto)
    const on = saved === "1";
    const cb = document.getElementById("toggleDims");
    const dims = document.getElementById("dimLabels");
    const dimsExtra = document.getElementById("dimLabelsExtra");
    if (cb) cb.checked = on;
    if (dims) dims.style.display = on ? "block" : "none";
    if (dimsExtra) dimsExtra.style.display = on ? "block" : "none";
  } catch (e) { /* ignoruj */ }
})();

// Prepinac urovne kotovani (1/2/3) - viz komentar u dimMode/refreshDimLabels.
document.querySelectorAll(".dim-mode-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    dimMode = parseInt(btn.dataset.mode, 10) || 1;
    document.querySelectorAll(".dim-mode-btn").forEach(b => b.classList.toggle("is-active", b === btn));
    try { localStorage.setItem("konfDimMode", String(dimMode)); } catch (e) { /* ignoruj */ }
    refreshDimLabels();
  });
});
(function () {
  try {
    const saved = parseInt(localStorage.getItem("konfDimMode"), 10);
    if (!saved || saved < 1 || saved > 3) return;
    dimMode = saved;
    document.querySelectorAll(".dim-mode-btn").forEach(b => b.classList.toggle("is-active", parseInt(b.dataset.mode, 10) === saved));
  } catch (e) { /* ignoruj */ }
})();

// --- Cislovani dilu ve scene (1,2,3...) - stejne poradi/cisla jako v
// Kusovniku vpravo (index+1 v poli placed). Umoznuje jednoznacne odkazovat
// na konkretni dil ("spoj mezi 2 a 3") pri reseni spoju - viz Robertovo
// "implementuje cislovani profilu ve scene, pomuze nam to vyresit spravne
// spoje" (2026-07-23). Vykreslene stejnym zpusobem jako zive koty (mm) -
// HTML kolecko s cislem, promitnute z 3D stredu dilu do 2D.
function refreshPartNumberLabels() {
  partNumberEntries.forEach(d => d.el.remove());
  partNumberEntries = [];
  const container = document.getElementById("partNumberLabels");
  placed.forEach((entry, i) => {
    const el = document.createElement("div");
    el.className = "part-number-label";
    el.textContent = String(i + 1);
    container.appendChild(el);
    partNumberEntries.push({ entry, el });
  });
  updatePartNumberPositions();
}

function updatePartNumberPositions() {
  if (!partNumberEntries.length) return;
  const rect = renderer.domElement.getBoundingClientRect();
  partNumberEntries.forEach(({ entry, el }) => {
    const endIdx = [];
    entry.connectorsLocal.forEach((c, i) => { if (c.kind === "end") endIdx.push(i); });
    let mid;
    if (endIdx.length >= 2) {
      const worldConns = worldConnectorsOf(entry);
      mid = worldConns[endIdx[0]].point.clone().add(worldConns[endIdx[1]].point).multiplyScalar(0.5);
    } else {
      // Robert 2026-08-07 ("postavit 2D protahovani pro desky") - deska
      // (a obecne jakykoli dil bez "end" konektoru) nema dva krajni body
      // k prumerovani - pouzij misto toho stred jeho world bounding boxu,
      // aby cislo dilu v kusovniku melo vzdy viditelnou pozici ve scene.
      entry.object3d.updateMatrixWorld(true);
      mid = new THREE.Box3().setFromObject(entry.object3d).getCenter(new THREE.Vector3());
    }
    const ndc = mid.clone().project(camera);
    if (ndc.z < -1 || ndc.z > 1 || ndc.x < -1.3 || ndc.x > 1.3 || ndc.y < -1.3 || ndc.y > 1.3) {
      el.style.display = "none";
      return;
    }
    el.style.display = "flex";
    el.style.left = ((ndc.x * 0.5 + 0.5) * rect.width) + "px";
    // Posunuto o kousek vyse nad stred dilu, aby se kolecko s cislem
    // nepřekrývalo s kotou delky (dim-label), ktera je presne na stredu.
    // Robert 2026-08-06 ("dej ty značky dál od sebe", screenshot ukazoval
    // kolecko a kotu tesne u sebe/prekryvajici se) - puvodnich 16px bylo
    // mene nez soucet poloviny vysky kolecka (20px) a poloviny vysky
    // dim-labelu (~19px) + jakakoli mezera, takze se spodek kolecka a
    // vrch koty porad dotykaly/prekryvaly. 26px dava viditelnou mezeru.
    el.style.top = ((-ndc.y * 0.5 + 0.5) * rect.height - 26) + "px";
  });
}

document.getElementById("toggleNums").addEventListener("change", (e) => {
  document.getElementById("partNumberLabels").style.display = e.target.checked ? "block" : "none";
  try { localStorage.setItem("konfShowNums", e.target.checked ? "1" : "0"); } catch (err) { /* ignoruj (napr. soukromy rezim) */ }
});

// Obnoveni ulozeneho stavu zatrzitka "Cisla dilu" pri nacteni stranky -
// stejna oprava jako u "Koty (mm)" (viz vyse) - drive se HTML atribut
// "checked" nikdy nesynchronizoval se skutecnou viditelnosti, takze cisla
// po kazdem znovunacteni naskocila zpet, i kdyz je Robert predtim vypnul.
(function () {
  try {
    const saved = localStorage.getItem("konfShowNums");
    if (saved === null) return; // zatim nic ulozeno - necháme vychozi (zapnuto)
    const on = saved === "1";
    const cb = document.getElementById("toggleNums");
    const nums = document.getElementById("partNumberLabels");
    if (cb) cb.checked = on;
    if (nums) nums.style.display = on ? "block" : "none";
  } catch (e) { /* ignoruj */ }
})();

// --- Zpusob vykresleni dilu: dratovy / rendered (PBR s osvetlenim) -
// prepinac v toolbaru, viz #renderModeSelect nize. ---
let renderMode = "rendered";

function materialForLayer(layer, overrideColor) {
  // posuvnik "Barva" u HDRI ovladace nastavuje vychozi barvu VSECH dilu
  // (viz hdriApplySurfaceLive), ale Robert 2026-08-06 ("klik barví ale ne
  // renderovanou verzi s hdri mapu") - rucne obarveny dil (overrideColor,
  // z "Obarvit díl"/"Obarvit stejné") musi mit VZDY prednost, jinak
  // globalni HDRI barva potichu prebije individualni malovani a klik
  // vypada, jako by nic neudelal. typeof guard pro jistotu.
  // PRAVIDLO Robert 2026-09-10, doslovne: "tak kovovost co je ve scene, se
  // nemuze aplikovat na vsechno, jen na profily."
  //
  // Posuvniky u HDRI ovladace (barva / kovovost / drsnost) do teto chvile
  // prebijely material KAZDEHO dilu - tedy i euroboxu, uhelniku, zaslepek a
  // MDF desek. To je spatne: ty posuvniky ladi vzhled HLINIKU v odrazech
  // HDRI mapy, ne plastu a desek. Plati proto uz jen pro PROFILY.
  //
  // Profil se pozna podle vrstvy "alu" - katalogove profily (cfg_dily) ji maji,
  // produktove dily maji layer VZDY natvrdo "produkt" (fetch_katalog_parts).
  // Rucni obarveni dilu (overrideColor) ma prednost dal, jako doposud.
  const jeProfil = (layer === "alu");
  const baseColorOverride = (jeProfil && typeof hdriReflBaseColor !== "undefined") ? hdriReflBaseColor : null;
  const color = overrideColor || baseColorOverride || partMaterialColor[layer] || "#9aa0a6";
  // "rendered" (vychozi) - PBR material, vyuziva svetla ve scene
  // (Hemisphere/Directional/Ambient), vypada realistictejsi (odlesky kovu).
  // DULEZITE: flatShading:true - GLB profily maji sdilene (prumerovane)
  // vertex normaly pres cele oblo-vypadajici hrany prurezu (kazdy vrchol
  // extruze je sdileny mezi sousednimi plochami). Bez flatShading by Three.js
  // pouzil hladke stinovani (Gouraud/Phong) a i ostre 90-stupnove hrany
  // profilu by vizualne vypadaly zaobleny/s radiusem - to NENI chyba
  // zdrojoveho souboru, jen artefakt hladkeho stinovani. flatShading pocita
  // normalu pro kazdy trojuhelnik zvlast, takze hrany zustanou ostre.
  const mat = new THREE.MeshStandardMaterial({
    color,
    // posuvniky u HDRI ovladace (viz hdriApplySurfaceLive) - nove dily
    // dostanou stejne hodnoty jako uz polozene; typeof guard pro jistotu
    // Produktove dily (shop_products) maji layer VZDY natvrdo "produkt"
    // (api/app.py) - jedine, co o nich vime, je jejich color_hex. Kdyz ta
    // barva presne sedi na nekterou z partMaterialColor palety (zinek/
    // plast/guma - viz HEX_TO_METALNESS), pouzije se kovovost TE palety
    // i bez realneho pole "layer"; jinak (profily s realnym layer="alu"
    // apod.) rozhoduje layer jako drive.
    metalness: (jeProfil && typeof hdriReflMetalness !== "undefined" && hdriReflMetalness != null) ? hdriReflMetalness
      : ((typeof HEX_TO_METALNESS !== "undefined" && HEX_TO_METALNESS[String(color).toLowerCase()] != null) ? HEX_TO_METALNESS[String(color).toLowerCase()]
      : ((typeof partMaterialMetalness !== "undefined" && partMaterialMetalness[layer] != null) ? partMaterialMetalness[layer] : 0.35)),
    // Stejny princip jako kovovost o par radku vyse - vstrikovany plast
    // ma mit ostre odlesky (nizka drsnost), guma naopak hodne matnou
    // (vysoka) - drive tu bylo VSECHNO stejnych 0.4 bez ohledu na material.
    roughness: (jeProfil && typeof hdriReflRoughness !== "undefined" && hdriReflRoughness != null) ? hdriReflRoughness
      : ((typeof HEX_TO_ROUGHNESS !== "undefined" && HEX_TO_ROUGHNESS[String(color).toLowerCase()] != null) ? HEX_TO_ROUGHNESS[String(color).toLowerCase()]
      : ((typeof partMaterialRoughness !== "undefined" && partMaterialRoughness[layer] != null) ? partMaterialRoughness[layer] : 0.4)),
    // Sila odrazu HDRI je taky vlastnost lesklych profilu - na plastu a
    // desce nema co delat (viz jeProfil vyse).
    envMapIntensity: (jeProfil && typeof hdriReflIntensity !== "undefined") ? hdriReflIntensity : 1,
    side: THREE.DoubleSide,
    flatShading: true,
  });
  return mat;
}

// Sdilena funkce pro nastaveni materialu dilu - pouziva ji jak rucni pridavani
// (placeAtOrigin), tak AI stavitel (runAIPlan), aby se chovaly stejne.
//
// Robert 2026-08-09 ("šlo by tu patku přebarvit jen částečně?") - dily s
// vice samostatnymi telesy v jednom GLB (napr. STEP dily po opravě
// step_convert_worker.py, pojmenovane meshe "Solid_0"/"Solid_1"/...) muzou
// mit KAZDE teleso svou vlastni barvu - viz obj.userData.meshColors (mapa
// jmeno meshe -> barva), kterou nastavuje paintEntry() pri kliknuti na
// konkretni cast. Kdyz mesh v mape neni (bezny pripad, jednodilne dily),
// pouzije se spolecny overrideColor jako drive - beze zmeny chovani.
function applyPartMaterial(obj, layer, overrideColor) {
  const meshColors = (obj.userData && obj.userData.meshColors) || null;
  obj.traverse(n => {
    if (n.isMesh) {
      const color = (meshColors && meshColors[n.name]) || overrideColor || partMaterialColor[layer] || "#9aa0a6";
      const partColor = (meshColors && meshColors[n.name]) || overrideColor;
      // Vrhani/prijimani stinu (Robert 2026-08-06: "pridejme lehce moznost
      // stinu") - jen priznaky, zadny vykon navic dokud neni zapnuty toggle
      // "Stiny" (viz applyShadowsEnabled - ten teprve zapne castShadow na
      // svetle a viditelnost podlahy, ktera stiny prijima).
      n.castShadow = true;
      n.receiveShadow = true;
      // Smazat drivejsi "hrany" pomocnou geometrii, pokud uz nejaka na tomto
      // mesh visi (napr. pri prepnuti rezimu vykresleni tam a zpet).
      const oldEdges = n.children.filter(c => c.userData && c.userData.isEdgesHelper);
      oldEdges.forEach(c => { n.remove(c); c.geometry.dispose(); c.material.dispose(); });

      if (renderMode === "wireframe" || renderMode === "wireframe_hidden") {
        // Misto plneho drateneho zobrazeni (wireframe:true na materialu),
        // ktere kresli KAZDOU hranu trojuhelniku vcetne "uhloprick" na
        // plochych stenach (FBX/GLB triangulace rozdeli kazdy ctverec na
        // 2 trojuhelniky), pouzijeme THREE.EdgesGeometry - ta zobrazi jen
        // hrany, kde uhel mezi sousednimi trojuhelniky presahuje prah
        // (1 stupen). Uhloprickami rozdelene ploche steny maji uhel ~180°
        // (jsou rovinne), takze se nezobrazi - zustanou jen skutecne hrany
        // profilu.
        const edgesGeom = new THREE.EdgesGeometry(n.geometry, 1);
        const edges = new THREE.LineSegments(edgesGeom, new THREE.LineBasicMaterial({ color }));
        edges.userData.isEdgesHelper = true;

        if (renderMode === "wireframe_hidden") {
          // Robertuv pozadavek (2026-07-23): druha varianta drateneho
          // zobrazeni, kde se kresli JEN hrany viditelne z aktualniho uhlu
          // pohledu (skryte hrany za nepruhlednou stenou dilu se neukazuji),
          // na rozdil od puvodni "X-ray" varianty, kde jsou videt uplne
          // vsechny hrany dilu naskrz. Trik: mesh zustane graficky neviditelny
          // (colorWrite:false - nic nevykresli do barevneho bufferu, takze
          // klikani/tazeni pres raycasting funguje dal stejne jako drive),
          // ale POCITA se do hloubkoveho bufferu (depthWrite:true) - tim
          // spravne "zakryje" hrany, ktere jsou aktualne za jeho pevnou
          // stenou. renderOrder zajisti, ze se tento neviditelny "occluder"
          // vykresli DRIV nez hrany, aby hloubkovy test fungoval spolehlive
          // (jinak by poradi vykreslovani mezi mesh a jeho potomkem-hranami
          // nebylo zarucene, protoze jsou prakticky ve stejne vzdalenosti
          // od kamery).
          n.material = new THREE.MeshBasicMaterial({ colorWrite: false, depthWrite: true });
          n.renderOrder = 0;
          edges.renderOrder = 1;
        } else {
          // Puvodni "X-ray" varianta - mesh uplne preskocen i pro hloubku
          // (material.visible:false neovlivnuje raycasting, takze
          // klikani/tazeni dilu funguje dal), takze jsou videt VSECHNY
          // hrany dilu, i ty na odvracene/skryte strane.
          n.material = new THREE.MeshBasicMaterial({ visible: false });
        }
        n.add(edges);
      } else if (renderMode === "ghost") {
        // Robert 2026-08-08 ("Pohled ghost musíme přidat zároveň do 3D
        // scény k ostatním"): poloprůhledný celý model - stejný material
        // jako "rendered" (barva/kov/HDRI), jen s transparent+opacity, aby
        // bylo videt dovnitr sestavy. depthWrite:false, aby se pruhledne
        // steny mezi sebou nerezaly/neblikaly pri prekryvu (typicky trik
        // pro poloprůhledné shluky vice objektu).
        const mat = materialForLayer(layer, partColor);
        mat.transparent = true;
        mat.opacity = 0.35;
        mat.depthWrite = false;
        n.material = mat;
      } else {
        n.material = materialForLayer(layer, partColor);
      }
    }
  });
}

// Prekresli material vsech uz polozenych dilu podle aktualne zvoleneho
// renderMode - volá se pri prepnuti v #renderModeSelect. Predava i pripadnou
// rucne nastavenou barvu (entry.customColor, viz nastroj "Obarvit dil"), aby
// prepnuti rezimu vykresleni obarveny dil neresetovalo zpet na barvu vrstvy.
function refreshAllMaterials() {
  // Robert 2026-08-07 ("potřebuji dát produktu barvu ve scéně, aby se
  // objevil rovnou zbarvený"): kdyz dil nema rucne nastavenou barvu
  // (customColor, z "Obarvit díl"), pouzij vychozi barvu produktu z
  // katalogu (part.color_hex, nastavitelna v adminu u skladove karty).
  // Robert 2026-08-11 ("obarvil jsem ale nebylo to trvale, novy se objevil
  // neobarveny"): color_hex uz maji i PROFILY (cfg_dily.color_hex, viz
  // sql/2026-08-11_cfg_dily_color_hex.sql) - dokud je NULL, plati barva
  // podle vrstvy jako drive.
  //
  // OPRAVA (tyz den, Robert: "obarvil jsem produkt PR10 ale ve scéně je
  // porad stejný"): puvodni `e.customColor || (e.part && e.part.color_hex)`
  // davalo customColor VZDY prednost - jenze placeAtOrigin() ho nastavuje
  // VZDY (i automaticky z part.color_hex pri vlozeni, ne jen rucnim
  // "Obarvit díl"), takze jakmile mel produkt pri vlozeni nejakou
  // (nenulovou) vychozi barvu, customColor "zamrzl" na tehdejsi hodnote
  // natrvalo - pozdejsi zmena color_hex v adminu uz se na jiz umistene
  // kusy nikdy nepropsala, ani po prekresleni. `manualColor` (nastavuje
  // VYHRADNE paintEntry/paintEntrySameParts, viz nize) ted rozlisuje
  // "uzivatel tohle rucne obarvil" (ma vzdy prednost) od "barva je jen
  // odvozena z aktualni vychozi barvy produktu" (ma sledovat AKTUALNI
  // part.color_hex, ne zamrznout na hodnote z okamziku vlozeni).
  // OPRAVA (Robert 2026-08-17, "vkládání profilů nebarví profily do
  // žádné barvy"): vychozi part.color_hex se u PROFILU (na rozdil od
  // prislusenstvi/desek) nema pouzivat vubec - jinak by kazde
  // prekresleni (zmena rezimu vykresleni/HDRI) profil znovu prebarvilo
  // zpatky, i kdyz placeAtOrigin() uz vedome zadnou barvu nenastavil.
  placed.forEach(e => applyPartMaterial(e.object3d, e.part.layer, e.manualColor ? e.customColor : (e.part && !isProfilePart(e.part) && e.part.color_hex)));
  // applyPartMaterial prave nahradil i material karoserii standardnim -
  // mrizkovy vzhled (applyCarBodyGridMaterials) a pruhlednost znovu
  // navleknout (count-brana v updateLiveTechnicalDimensions by to sama
  // nechytla, pocet karoserii se nezmenil). Pozor: stary mrizkovy material
  // uz na meshi neni, takze carBodyStdMaterial se tu jen prepise novym.
  placed.forEach(e => { if (e.part && e.part.source === "car_body") e.object3d.traverse(n => { if (n.isMesh) n.userData.carBodyStdMaterial = null; }); });
  applyCarBodyOpacity(carBodyOpacityPct);
  // applyPartMaterial vytvori nove materialy/hrany, takze pripadne zvyrazneni
  // vybranych dilu v rezimu "Mikroposuv" by se ztratilo - obnov ho.
  if (typeof selectedMoveEntries !== "undefined") selectedMoveEntries.forEach(e => setSelectHighlight(e, true));
}

function loadGlbAsync(file) {
  return new Promise((resolve, reject) => {
    loader.load(file, (gltf) => resolve(gltf.scene), undefined, reject);
  });
}

function placeAtOrigin(p) {
  loader.load(p.file, (gltf) => {
    const obj = gltf.scene;
    // Robert 2026-08-07 ("aby se objevil rovnou zbarvený") - vychozi
    // barva produktu z katalogu (p.color_hex, nastavena v adminu) se
    // pouzije UZ PRI VLOZENI, ne az pri prvnim refreshAllMaterials() -
    // ulozena i jako customColor (stejny mechanismus jako rucni "Obarvit
    // díl"), aby prezila zmenu rezimu vykresleni/HDRI beze ztraty.
    // OPRAVA (Robert 2026-08-17, "vkládání profilů přes Katalog obrázků
    // nebarví profily do žádné barvy"): u PROFILU se tohle nema delat -
    // vychozi color_hex byl mysleny pro prislusenstvi/desky, u profilu
    // zbytecne barvi (napr. na zlutou) i kdyz uzivatel zadnou barvu
    // nezvolil.
    const placeColorHex = isProfilePart(p) ? undefined : p.color_hex;
    applyPartMaterial(obj, p.layer, placeColorHex);
    // Robert 2026-08-07 ("postavit 2D protahovani pro desky") - deska
    // (p.is_board_material) dostane 4 hranove konektory (sirka+vyska
    // nezavisle protazitelne) misto bezne 1 delkove osy profilu.
    // wallSnap jen pro PRISLUSENSTVI (neprofily) - u profilu je dosedaci
    // rovinou opravdu kraj obalky, u rozku/uhelniku az stena za zobackem.
    const connectorsLocal = p.is_board_material
      ? computeBoardEdgeConnectors(obj)
      : computeConnectorsLocal(obj, partConnectorOpts(p));
    obj.position.set(0, 0, 0);
    // Robert 2026-08-09 ("natocit kulatinou nahoru"): vetsina dilu lezi
    // na zemi, ale p.place_vertical (nastavitelne v adminu u karty
    // produktu) da prednost puvodni svisle orientaci z 3D modelu - viz
    // baseQuaternion.
    obj.quaternion.copy(baseQuaternion(0, p.place_vertical ? "vertical" : "horizontal"));
    obj.updateMatrixWorld(true);
    // Robert 2026-08-11 ("kazdy objekt ktery se vklada do sceny nech se
    // objevi na stredu os bez ohledu na to jake mel souradnice v dobe
    // vytvoreni"): GLB modely maji geometrii casto daleko od pocatku
    // (napr. 20x40x100.glb ma stred v X = -240 mm), takze
    // position.set(0,0,0) polozilo dil nekam stranou. Dil se proto po
    // natoceni JESTE srovna: vodorovne presne na osu (stred obalky v
    // X/Z = 0) a spodni hranou na rovinu mrizky (Y = 0), aby nebyl
    // zpola zapichnuty pod podlahou. connectorsLocal se pocitaji vyse v
    // LOKALNIM ramci dilu, takze je tenhle posun neovlivnuje.
    const placeBox = new THREE.Box3().setFromObject(obj);
    if (!placeBox.isEmpty()) {
      const placeCenter = placeBox.getCenter(new THREE.Vector3());
      obj.position.set(-placeCenter.x, -placeBox.min.y, -placeCenter.z);
      obj.updateMatrixWorld(true);
    }
    obj.userData.basePos = obj.position.clone();
    scene.add(obj);
    placed.push({ part: p, object3d: obj, connectorsLocal, customColor: placeColorHex || undefined });
    rebuildOccupiedConnectors();
    refreshEndpointMarkers(); refreshDimLabels();
    refreshSummary();
  }, undefined, (err) => { console.error("GLB load failed for", p.name, err); alert("Nepodařilo se načíst díl " + p.name + "."); });
}

// Robert 2026-08-08 ("obrazky jako tlacitka" - novy obrazkovy plovouci
// panel katalogu vedle stavajiciho stromu, "co nejmensi plocha" pro
// desitky novych produktu): davkovy generator 3D nahledu pro KAZDY dil
// katalogu bez existujiciho thumbnail_file. Stejny zaklad jako
// paOpenPreviewGenerator/paCapture360Set (docasne vlozit dil izolovane,
// vyfotit, uklidit), jen pro JEDNOTLIVE katalogove dily misto sestav a
// spoustene jako jednorazova admin davka (ne interaktivni panel) -
// admin klikne 1x, projede se cely katalog sekvencne.
// Robert 2026-09-17 ("zaroven z toho generovani vylouci karoserie"): 912
// z 1066 katalogovych polozek jsou car_body_* (viz komentar u
// #catalogSearchWrap - "912 položek v jediné skupině auto") - ty nikdy
// nemely katalogovy nahled (zobrazuji se zive ve 3D, ne jako ikonka) a
// pred touhle opravou tvorily 941 z 942 cilu davky. isCarBodyPart sdilena
// se zbytkem sceny (scene-geometry-shared.js).
let CATALOG_THUMB_CANCEL = false;
async function generateCatalogThumbnails() {
  if (!CURRENT_USER || CURRENT_USER.role !== "admin") {
    alert("Generování náhledů katalogu je jen pro administrátora.");
    return;
  }
  const targets = CATALOG.filter(p => !p.thumbnail_file && !isCarBodyPart(p));
  const statusEl = document.getElementById("catalogThumbStatus");
  if (!targets.length) {
    if (statusEl) statusEl.textContent = "Všechny díly už mají náhled.";
    return;
  }
  const btn = document.getElementById("btnGenerateCatalogThumbnails");
  if (btn) btn.disabled = true;
  CATALOG_THUMB_CANCEL = false;
  const stopBtn = document.getElementById("btnStopCatalogThumbnails");
  if (stopBtn) stopBtn.style.display = "";

  // Docasne vyjmout aktualni scenu z vykreslovani (ne smazat) - stejny
  // princip jako paOpenPreviewGenerator, jen pro VSECHNY placed[] najednou.
  const savedPlaced = placed.slice();
  const savedAxisIndicatorEntries = placed.filter(e => partAxisHelpers.has(e));
  placed.length = 0;
  savedPlaced.forEach(e => { e.object3d.visible = false; });
  if (typeof setHelperMarkersVisible === "function") setHelperMarkersVisible(false);
  const prevRenderMode = renderMode;
  renderMode = "rendered";
  const prevCamPos = camera.position.clone();
  const prevTarget = controls.target.clone();
  const prevAspect = camera.aspect;
  const prevGridVisible = grid.visible;
  const prevShadowGroundVisible = shadowGround.visible;
  grid.visible = false;
  shadowGround.visible = false;
  // Stejny fix jako generateWizardShapeThumbnails (viz komentar tam,
  // Robert: "flashuje cela scena") - hlavni render smycka se na dobu
  // generovani uplne vypne (suppressMainRender), zachyceni bezi na
  // samostatnem thumbOffscreenRenderer, ne na hlavnim <canvas>u.
  suppressMainRender = true;

  // Ctvercove platno jen pro miniaturu tlacitka (ne cely nepravidelny
  // pomer stran viewportu) - 480x480 staci na ostrou ikonku.
  const THUMB_PX = 480;
  thumbOffscreenRenderer.setSize(THUMB_PX, THUMB_PX, false);
  camera.aspect = 1;

  let ok = 0, fail = 0;
  // try/finally kolem cele davky - suppressMainRender=true nesmi zustat
  // trvale zapnute (natrvalo by zamrzl hlavni viewport), i kdyby neco
  // vyhodilo vyjimku MIMO uz existujici per-dil try/catch nize.
  try {
    for (let i = 0; i < targets.length; i++) {
      if (CATALOG_THUMB_CANCEL) { if (statusEl) statusEl.textContent = `Zastaveno po ${i}/${targets.length} (${ok} hotovo, ${fail} selhalo).`; break; }
      const p = targets[i];
      if (statusEl) statusEl.textContent = `Generuji náhledy… (${i + 1}/${targets.length}) ${p.name}`;
      try {
        const obj = await new Promise((resolve, reject) => {
          loader.load(p.file, (gltf) => resolve(gltf.scene), undefined, reject);
        });
        applyPartMaterial(obj, p.layer, p.color_hex || undefined);
        obj.position.set(0, 0, 0);
        obj.quaternion.copy(baseQuaternion(0, "horizontal"));
        obj.updateMatrixWorld(true);
        scene.add(obj);

        // Tesny zoom podle bounding sphere (radi nez box - stejne dobre
        // funguje pro dlouhe tenke profily i kompaktni hardware) - vzdalenost
        // dopoctena z vertikalniho FOV kamery (45°), aby dil vyplnil
        // vetsinu ctvercoveho snimku bez ohledu na jeho tvar/pomer stran.
        const box = new THREE.Box3().setFromObject(obj);
        const sphere = box.getBoundingSphere(new THREE.Sphere());
        const center = sphere.center;
        const radius = Math.max(sphere.radius, 10);
        camera.updateProjectionMatrix();
        const fovRad = (camera.fov * Math.PI) / 180;
        const dist = (radius * 1.25) / Math.sin(fovRad / 2);
        const dir = new THREE.Vector3(1, 0.85, 1).normalize();
        camera.position.copy(center).addScaledVector(dir, dist);
        camera.lookAt(center);
        controls.target.copy(center);
        thumbOffscreenRenderer.render(scene, camera);
        const dataUrl = thumbOffscreenRenderer.domElement.toDataURL("image/jpeg", 0.88);

        const blob = await (await fetch(dataUrl)).blob();
        const fd = new FormData();
        fd.append("part_id", p.id);
        fd.append("file", blob, "thumb.jpg");
        const resp = await fetch("/api/catalog-thumbnail", { method: "POST", body: fd });
        if (resp.ok) {
          const data = await resp.json();
          p.thumbnail_file = "katalog/" + data.thumbnail_file + "?v=" + Date.now();
          ok++;
        } else {
          fail++;
        }
        scene.remove(obj);
      } catch (err) {
        console.error("Náhled selhal pro", p.id, err);
        fail++;
      }
    }
  } finally {
    savedPlaced.forEach(e => { e.object3d.visible = true; });
    placed.push(...savedPlaced);
    savedAxisIndicatorEntries.forEach(e => {
      if (!partAxisHelpers.has(e) && typeof addPartAxisIndicator === "function") addPartAxisIndicator(e);
    });
    renderMode = prevRenderMode;
    if (typeof setHelperMarkersVisible === "function") setHelperMarkersVisible(true);
    grid.visible = prevGridVisible;
    shadowGround.visible = prevShadowGroundVisible;
    camera.aspect = prevAspect;
    camera.position.copy(prevCamPos);
    controls.target.copy(prevTarget);
    camera.lookAt(controls.target);
    camera.updateProjectionMatrix();
    controls.update();
    // Vse obnoveno - az TED zase pustit hlavni render smycku a hned
    // vykreslit jeden spravny snimek.
    suppressMainRender = false;
    renderer.render(scene, camera);
  }

  if (btn) btn.disabled = false;
  if (stopBtn) stopBtn.style.display = "none";
  if (statusEl && !CATALOG_THUMB_CANCEL) statusEl.textContent = `Hotovo: ${ok} náhledů vygenerováno${fail ? `, ${fail} selhalo` : ""}.`;
}

function removeLast(){
  const last = placed.pop();
  if (last) {
    if (typeof releaseAllJointsFor === "function") releaseAllJointsFor(last);
    scene.remove(last.object3d);
    if (typeof selectedMoveEntries !== "undefined" && selectedMoveEntries.has(last)) {
      selectedMoveEntries.delete(last);
      refreshMoveSelectionLabel();
    }
    // Posun mysi (axisMoveSelectedEntries) ma vlastni, nezavislou sadu vyberu
    // - bez tohohle by po smazani dilu zustala "zamrzla" sipka aktivni osy
    // ve scene, protoze by na ni nic neupozornilo na zmenu.
    if (typeof axisMoveSelectedEntries !== "undefined" && axisMoveSelectedEntries.has(last)) {
      axisMoveSelectedEntries.delete(last);
      if (typeof refreshAxisMoveLabel === "function") refreshAxisMoveLabel();
    }
    if (typeof syncCatalogSelectionHighlight === "function") syncCatalogSelectionHighlight();
    rebuildOccupiedConnectors(); refreshEndpointMarkers(); refreshDimLabels(); refreshSummary();
  }
}

// Robert 2026-07-24: "oznaceny objekt lze smazat tlacitkem delete" - smaze
// VSECHNY aktualne oznacene dily, at uz jsou vybrane v Mikroposuvu
// (selectedMoveEntries) nebo v Posunu mysi (axisMoveSelectedEntries) - obe
// sady sdileji stejne vizualni zvyrazneni (setSelectHighlight), takze
// "oznaceny" znamena "vybrany v kterekoli z techto dvou funkci". Stejny
// vzorec cisteni navaznych stavu jako uz existujici removeLast()/clearAll().
function deleteSelectedEntries() {
  const toDelete = new Set();
  if (typeof selectedMoveEntries !== "undefined") selectedMoveEntries.forEach(e => toDelete.add(e));
  if (typeof axisMoveSelectedEntries !== "undefined") axisMoveSelectedEntries.forEach(e => toDelete.add(e));
  if (!toDelete.size) return;
  toDelete.forEach(entry => {
    if (typeof releaseAllJointsFor === "function") releaseAllJointsFor(entry);
    scene.remove(entry.object3d);
    const idx = placed.indexOf(entry);
    if (idx !== -1) placed.splice(idx, 1);
  });
  if (typeof selectedMoveEntries !== "undefined" && selectedMoveEntries.size) {
    selectedMoveEntries.clear();
    refreshMoveSelectionLabel();
  }
  if (typeof axisMoveSelectedEntries !== "undefined" && axisMoveSelectedEntries.size) {
    axisMoveSelectedEntries.clear();
    if (typeof refreshAxisMoveLabel === "function") refreshAxisMoveLabel();
  }
  paintHoverEntry = null; paintHoverMesh = null; // pro jistotu, kdyby smazany dil byl prave "namoceny" hoverem
  // Robert 2026-08-11 ("kdyz smazu oznaceny produkt, musi se v levem
  // katalogu odznacit a neviset tam"): vyberove sady se vyprazdnily bez
  // volani setSelectHighlight, takze podsviceni v katalogu i jmenovka
  // pod osovym krizem by zustaly viset na uz neexistujicim dilu.
  if (typeof syncCatalogSelectionHighlight === "function") syncCatalogSelectionHighlight();
  // Robert 2026-07-24 (funkce Join): smazany dil uz nemuze byt v zadne
  // skupine - odstranit ho ze vsech jointGroups, a skupiny ktere tim
  // klesnou na <=1 clen rozpustit (jednoclenna "skupina" nema smysl).
  if (typeof jointGroups !== "undefined" && jointGroups.length) {
    jointGroups = jointGroups
      .map(g => { toDelete.forEach(e => g.delete(e)); return g; })
      .filter(g => g.size > 1);
  }
  rebuildOccupiedConnectors();
  refreshEndpointMarkers(); refreshDimLabels();
  refreshSummary();
}

// bot8 2026-08-20 (Robert: "ne vždy ve scene funguje delete oznaceneho
// objektu... hloubkove prozkoumej" - REPRODUKOVANO): puvodni straz
// blokovala Delete pri fokusu na JAKEMKOLI INPUT/SELECT - tedy i na
// zaskrtavatku, selectu nebo slideru, kde se zadny text nepise. Po
// kliknuti na libovolny ovladaci prvek panelu tam fokus ZUSTAVA, takze
// Delete (tise!) nedelal nic, dokud uzivatel neklikl do sceny. Skutecny
// "pisici" kontext je jen textove pole - vsude jinde ma klavesa mazat dil.
function isTypingTarget(el) {
  if (!el || !el.tagName) return false;
  if (el.isContentEditable) return true;
  const tag = el.tagName;
  if (tag === "TEXTAREA") return true;
  if (tag !== "INPUT") return false;
  const t = (el.type || "text").toLowerCase();
  return ["text", "number", "search", "password", "email", "url", "tel", "date", "time"].includes(t);
}
window.addEventListener("keydown", (ev) => {
  if (ev.key !== "Delete") return;
  // Robert 2026-07-25: "oznaceny dil nelze smazat tl. Delete" - hlaseno bez
  // chyby v konzoli, tzn. jde o nektery z tichych "early return" vyse, ne o
  // JS vyjimku. Bez zivého repro nejde jistotou najit KTERY konkretni duvod
  // nastal (fokus na jinem prvku? rozjete tazeni? prazdny vyber?) - misto
  // dalsiho hadani aspon KAZDY z duvodu ted vypise viditelny toast, aby
  // bylo hned videt proc Delete nic neudelal, misto tiche neaktivity.
  if (isTypingTarget(ev.target)) {
    // Zamerne BEZ toastu - tady je Delete spravne urcen pro mazani znaku
    // v poli (napr. "Krok (mm)"), ne pro mazani dilu.
    return;
  }
  // Ne-pisici ovladaci prvek (select/checkbox/tlacitko) drzici fokus se
  // odfokusuje, at dalsi klavesy jdou cele scene.
  if (ev.target && ev.target.blur && ev.target !== document.body) ev.target.blur();
  // Nemazat behem rozjeteho tazeni (protahovani konce, Posun mysi, rotace) -
  // smazani dilu, na ktery prave nejaky drag-stav ukazuje, by ho nechalo
  // odkazovat na uz neexistujici objekt.
  if (dragState) { showJoinToast("Delete: právě probíhá tažení za konec dílu - dokonči ho (pusť tlačítko myši) a zkus to znovu."); return; }
  if (typeof axisMoveDragState !== "undefined" && axisMoveDragState) { showJoinToast("Delete: právě probíhá Posun myší - dokonči ho (pusť tlačítko myši) a zkus to znovu."); return; }
  if (typeof rotateActive !== "undefined" && rotateActive) { showJoinToast("Delete: právě probíhá rotace - dokonči ji a zkus to znovu."); return; }
  // Synchronni rozsireni na cele Join skupiny PRED cteni vyberu - jinak by
  // rychle "klikni + hned Delete" smazalo jen jeden dil ze skupiny a
  // osirelo zbytek (viz expandSelectionToGroups nize, jinak bezi jen na
  // 200ms intervalu).
  if (typeof expandSelectionToGroups === "function") expandSelectionToGroups();
  const hasSelection = (typeof selectedMoveEntries !== "undefined" && selectedMoveEntries.size)
    || (typeof axisMoveSelectedEntries !== "undefined" && axisMoveSelectedEntries.size);
  if (!hasSelection) {
    showJoinToast("Delete: nic není označeno. Klikni na díl ve scéně (Mikroposuv nebo Posun myší), pak zkus Delete znovu.");
    return;
  }
  ev.preventDefault();
  deleteSelectedEntries();
});

// Robert 2026-07-24: "přidej funkci Join, tlačítko J, které označené
// objekty zamče spolu, a budou se tvářit jako 1 objekt. Pro odemčení
// stačí opět označit a J." Rešeno jako trvala skupina (jointGroups - pole
// Setu dilu), NEZAVISLA na docasnem vyberu Mikroposuvu/Posunu mysi (ktery
// se po kazde akci maze). Jakmile je dil clenem skupiny, kazdy dalsi vyber
// KTERYKOLI z jejich clenu (v libovolne ze dvou vyberovych sad) se
// automaticky rozsiri na CELOU skupinu (viz expandSelectionToGroups) -
// diky tomu Mikroposuv, Posun mysi (vc. rotace, ktera pouziva stejnou
// sadu) i Delete uz automaticky pracuji se skupinou jako s jednim celkem,
// BEZ jakekoli zmeny v kodu tech funkci (jen se jim "podstrci" vetsi
// vyber, nez sami vybrali).
let jointGroups = [];

function jointGroupOf(entry) {
  return jointGroups.find(g => g.has(entry)) || null;
}

// Robert 2026-07-24 (znovu): "furt dokola, spojene dily nejde odznacit,
// porad jsou oznacene" - predchozi 2 pokusy (polling + snapshot-diff
// heuristika) byly zavisle na CASOVANI kliku vuci 60ms tikum a proto se
// chovaly nespolehlive/nepredvidatelne. Reseni: zrusit zavislost na
// casovani uplne - klik na dil, ktery je clenem Join skupiny, se ted
// vyhodnocuje SYNCHRONNE a ATOMICKY v okamziku samotneho kliku (zadne
// cekani na interval): pokud je CELA skupina prave TED (pred timto
// klikem) uz plne vybrana, klik ji CELOU odebere z vyberu; jinak klik
// CELOU skupinu do vyberu prida. Zadna ambiguita, zadny race - funguje
// stejne spolehlive jako toggle jednotliveho neskupinoveho dilu.
function groupAwareToggle(set, entry) {
  if (!entry || !set) return;
  const g = jointGroupOf(entry);
  if (!g) {
    // neskupinovy dil - puvodni prosty toggle
    if (set.has(entry)) { set.delete(entry); if (typeof setSelectHighlight === "function") setSelectHighlight(entry, false); }
    else { set.add(entry); if (typeof setSelectHighlight === "function") setSelectHighlight(entry, true); }
    return;
  }
  const allSelected = Array.from(g).every(m => set.has(m));
  if (allSelected) {
    g.forEach(m => { if (set.delete(m) && typeof setSelectHighlight === "function") setSelectHighlight(m, false); });
  } else {
    g.forEach(m => { if (!set.has(m)) { set.add(m); if (typeof setSelectHighlight === "function") setSelectHighlight(m, true); } });
  }
}

// Robert 2026-07-24: "zustava oznaceny, nelze odznacit" - puvodni verze
// jen DOPLNOVALA chybejici cleny skupiny do vyberu (bez odebirani), takze
// klik na JEDNOHO clena uz plne vybrane skupiny (aby se odznacil) byl do
// 60ms "vracen zpet" timto doplnenim.
//
// Robert 2026-07-24 (nasledny report): "takze 2 dily J spoji, ale 3 uz ne,
// oznaceny spojeny objekt nejde rozpojit zpet" - DALSI pokus o opravu (
// heuristika "clen jiz plne pritomne skupiny byl odebran = uzivatel chce
// odznacit celou skupinu") se ukazal byt SAM O SOBE chybny: kdyz uzivatel
// bezne postupne klika na VICE dilu jedne uz existujici skupiny (napr. aby
// si ji "znovu vybral" pred rozpojenim, nebo pri rozsirovani o dalsi dil),
// prvni klik ji auto-rozsiri (tick do 60ms), a DRUHY klik na jiz (auto-
// pridaneho) clena skupiny je Mikroposuvem/Posunem mysi vyhodnocen jako
// prosty TOGGLE-OFF (uz byl vybrany) - coby "prave odebran clen plne
// pritomne skupiny", coz predchozi heuristika vyhodnotila jako "chce
// odznacit vse" a smazala CELY vyber vc. dilu pridanych uzivatelem umyslne.
// Vysledek: nahodne "nefunkcni" spojovani/rozpojovani podle presneho
// časování kliku - presne to, co Robert hlasil.
//
// Reseni: vratit se k PROSTEMU, jednoznacnemu chovani - rozsireni pouze
// DOPLNUJE chybejici cleny skupiny (nikdy nic needstranuje). Pro UPLNE
// odznaceni (vc. cele skupiny) slouzi existujici spolehlive "Zrušit výběr"
// tlacitko a klavesa Escape (obe delaji hromadne vycisteni vyberu najednou,
// bez zavislosti na poradi/casovani jednotlivych kliku). Spojeni/rozpojeni
// samotne (J nebo tlacitko "Spojit/Rozpojit") pracuje s tim, co je PRAVE
// vybrano, at uz vybrano rucne nebo auto-rozsirenim.
function expandOneSelectionSet(set) {
  if (!set) return false;
  const sizeBefore = set.size;
  let changed = true;
  const addedThisCall = [];
  while (changed) {
    changed = false;
    const toAdd = [];
    set.forEach(e => {
      const g = jointGroupOf(e);
      if (g) g.forEach(m => { if (!set.has(m)) toAdd.push(m); });
    });
    if (toAdd.length) { toAdd.forEach(m => { set.add(m); addedThisCall.push(m); }); changed = true; }
  }
  if (typeof setSelectHighlight === "function") {
    addedThisCall.forEach(m => setSelectHighlight(m, true));
  }
  return set.size !== sizeBefore;
}

// Prubezne (i synchronne pred Delete/J) synchronizuje OBE vyberove sady se
// stavem Join skupin. Mutuje existujici Set objekty NA MISTE (nenahrazuje
// je novymi) - Mikroposuv i Posun mysi si drzi vlastni referenci na tentyz
// Set, takze zmena je pro ne okamzite viditelna bez zasahu do jejich kodu.
function expandSelectionToGroups() {
  if (!jointGroups.length) return;
  let moveChanged = false, axisChanged = false;
  if (typeof selectedMoveEntries !== "undefined") moveChanged = expandOneSelectionSet(selectedMoveEntries);
  if (typeof axisMoveSelectedEntries !== "undefined") axisChanged = expandOneSelectionSet(axisMoveSelectedEntries);
  if (moveChanged && typeof refreshMoveSelectionLabel === "function") refreshMoveSelectionLabel();
  if (axisChanged && typeof refreshAxisMoveLabel === "function") refreshAxisMoveLabel();
}
// Casteji nez drive (200ms -> 60ms), aby se rozsireni cele skupiny (vc.
// zvyrazneni) projevilo prakticky okamzite po kliknuti.
setInterval(expandSelectionToGroups, 60);

let joinToastEl = null;
function showJoinToast(msg) {
  if (!joinToastEl) {
    joinToastEl = document.createElement("div");
    joinToastEl.id = "joinToastBanner";
    // Robert 2026-08-08 ("hlasky ve 3D scene dej pismo malinko vetsi a
    // premisti hlasky na spodní hranu sceny"): puvodne top:10px, font-size:12px.
    // Robert 2026-09-13 (screenshot: text schovany za tlacitkem "Materiály"):
    // OPRAVA PRVNIHO POKUSU (z-index 50->70) byla nedostatecna - skutecny
    // prekryvajici prvek neni .toolFloatingBtn (z-index:60), ale
    // #toolboxPanel (z-index:520, viz material-panel.js), ktery ma navic
    // TOTOZNOU pozici "bottom:10px; left:50%" jako tenhle banner - odtud
    // "Materiály" (jeho jedine, vzdy pritomne tlacitko, viz start() v
    // material-panel.js) doslova sedelo na stejnem miste. 530 - bezpecne
    // nad 520, at banner vyhraje nad kterymkoli obsahem toolboxPanelu.
    joinToastEl.style.cssText = "position:absolute;bottom:14px;left:50%;transform:translateX(-50%);z-index:530;background:#2a4a3a;color:#c8f7d8;padding:8px 14px;border-radius:8px;font-size:13px;max-width:80%;";
    document.getElementById("viewport").appendChild(joinToastEl);
  }
  joinToastEl.textContent = msg;
  joinToastEl.style.display = "block";
  clearTimeout(joinToastEl._hideTimer);
  // Robert 2026-08-16 ("ty hlasky zelene musi trvat 10 sekund, nejde to
  // ani precist jak hned zmizi"): 2200 -> 10000.
  joinToastEl._hideTimer = setTimeout(() => { joinToastEl.style.display = "none"; }, 10000);
}

// Prepinac (J): pokud oznaceny vyber PRESNE odpovida uz existujici jedne
// skupine, rozpusti ji (odemceni). Jinak slouci vsechny skupiny dotcene
// vyberem + samotny vyber do JEDNE nove skupiny (zamceni) - takze jde i
// dodatecne pripojit dalsi dil k uz existujici skupine.
function toggleJoinForSelection(entries) {
  const entrySet = new Set(entries);
  const touchedGroups = new Set();
  entries.forEach(e => { const g = jointGroupOf(e); if (g) touchedGroups.add(g); });

  const touchedArr = Array.from(touchedGroups);
  const isSingleExactGroup = touchedArr.length === 1 && touchedArr[0].size === entrySet.size
    && Array.from(entrySet).every(e => touchedArr[0].has(e));

  if (isSingleExactGroup) {
    jointGroups = jointGroups.filter(g => g !== touchedArr[0]);
    showJoinToast(`Skupina rozpojena (${touchedArr[0].size} dílů).`);
  } else {
    const merged = new Set(entries);
    touchedArr.forEach(g => g.forEach(m => merged.add(m)));
    jointGroups = jointGroups.filter(g => !touchedGroups.has(g));
    jointGroups.push(merged);
    showJoinToast(`Spojeno do 1 skupiny (${merged.size} dílů).`);
  }
}

// Sjednoceny vyber z obou vyberovych sad (Mikroposuv + Posun mysi) -
// pouziva jak klavesa J, tak tlacitko "Spojit/Rozpojit".
function currentJoinSelectionUnion() {
  const entries = new Set();
  if (typeof selectedMoveEntries !== "undefined") selectedMoveEntries.forEach(e => entries.add(e));
  if (typeof axisMoveSelectedEntries !== "undefined") axisMoveSelectedEntries.forEach(e => entries.add(e));
  return entries;
}

function runJoinToggleOnCurrentSelection() {
  expandSelectionToGroups();
  const entries = currentJoinSelectionUnion();
  if (entries.size < 2) {
    showJoinToast("Označ aspoň 2 díly (Mikroposuv nebo Posun myší), pak stiskni J nebo klikni na Spojit.");
    return;
  }
  toggleJoinForSelection(Array.from(entries));
  if (typeof refreshJoinActionButton === "function") refreshJoinActionButton();
}

window.addEventListener("keydown", (ev) => {
  if (ev.key.toLowerCase() !== "j") return;
  const tag = (ev.target && ev.target.tagName) || "";
  if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
  if (dragState) return;
  if (typeof axisMoveDragState !== "undefined" && axisMoveDragState) return;
  if (typeof rotateActive !== "undefined" && rotateActive) return;
  ev.preventDefault();
  runJoinToggleOnCurrentSelection();
});

// Robert 2026-08-01 ("vymysli rozumne odpojeni"): klavesa U (Uvolnit) -
// oznaceny (prave 1), uz pripojeny neprofil se odpoji od profilu, ke
// kteremu je pripnuty. Nemeni pozici/natoceni (zustava presne tam, kde
// je) - jen zrusi stav "pripojeno" (attachedTo), snizi jointCount o 1 (uz
// se neuctuje jako spoj) a uvolni licPeers parovani, aby ho slo pripadne
// znovu pripojit (tazenim blizko k libovolne plose) bez zabranovani
// starym stavem.
window.addEventListener("keydown", (ev) => {
  if (ev.key.toLowerCase() !== "u") return;
  const tag = (ev.target && ev.target.tagName) || "";
  if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
  if (dragState) return;
  if (typeof axisMoveDragState !== "undefined" && axisMoveDragState) return;
  if (typeof rotateActive !== "undefined" && rotateActive) return;
  // Robert 2026-08-04 ("nefunguje odpocet pri rozpojeni") - OPRAVA: U
  // drive koukala JEN na vyber z Posunu mysi (axisMoveSelectedEntries) -
  // dil oznaceny pres Mikroposuv (selectedMoveEntries) U uplne
  // ignorovala. Ted se bere SJEDNOCENI obou vyberu (stejna mnozina jako
  // u J/Spojit/Pripoj - currentJoinSelectionUnion), presne 1 dil.
  const selectedForU = (typeof currentJoinSelectionUnion === "function")
    ? Array.from(currentJoinSelectionUnion())
    : (typeof axisMoveSelectedEntries !== "undefined" ? Array.from(axisMoveSelectedEntries) : []);
  if (!selectedForU.length) return;
  // Robert 2026-08-20 ("v rezimu uceni nefunguje U"): rezim uceni
  // (Stena/Volne celo + 🤖 Automaticky vyzkouset) vyzaduje oznacit DVA
  // dily (dil + profil) - puvodni podminka "presne 1 oznaceny" pak U
  // TISE zahodila, bez jakekoli hlasky. Nove: z vyberu se vezmou jen
  // dily, ktere skutecne evidujou spoj; kdyz je mezi nimi prave jeden
  // NEprofil (typicky pripad dil+profil), odpoji se ten - profil ve
  // vyberu nevadi. A kdyz neni co odpojit, rekne se to nahlas.
  const jointedForU = selectedForU.filter(e =>
    e.attachedTo || (isProfilePart(e.part) && e.lastJoint) || (e.licPeers && e.licPeers.size));
  if (!jointedForU.length) {
    ev.preventDefault();
    if (typeof showJoinToast === "function") showJoinToast("U: žádný z označených dílů není evidovaný jako připojený (náhled učení před ✓ Správně se neregistruje).");
    return;
  }
  const nonProfJointed = jointedForU.filter(e => !isProfilePart(e.part));
  const only = nonProfJointed.length === 1 ? nonProfJointed[0]
    : (jointedForU.length === 1 ? jointedForU[0] : null);
  if (!only) {
    ev.preventDefault();
    if (typeof showJoinToast === "function") showJoinToast("U: označ jen jeden díl k odpojení (teď je připojených ve výběru víc).");
    return;
  }
  // Robert 2026-08-04 ("nepocita to rozpojeni... ci klavesou U"): U dosud
  // odpojovala jen prislusenstvi (attachedTo) - pro PROFIL spojeny s jinym
  // profilem (lastJoint, viz Pripoj/R-otaceni) nedelala nic a spoj zustaval
  // zapocitany navzdy. Ted U odpoji i profil-profil spoj - stejny princip
  // (nemeni pozici/natoceni, jen zrusi ucetnictvi: jointCount/licPeers/
  // usedConn/lastJoint pres detachProfileJoint).
  //
  // Robert 2026-08-12 ("u trojcestneho L nefunguje U rozpojit"): attachedTo
  // i lastJoint pamatuji vzdy jen JEDEN konkretni spoj, ale dil muze mit
  // soucasne VIC peeru (viz komentar u releaseAllJointsFor - "sloupek
  // spojeny s vice prycnami v ruznych vyskach") - u trojcestneho dilu tak
  // prvni U odpojilo jen lastJoint (a hned ho vynulovalo), zbyle 1-2 spoje
  // v licPeers uz U nikdy nedosahlo (podminky vyse na ne nesedely). Ted se
  // VSECHNY zbyvajici licPeers teto entry odpoji rovnou pri stejnem stisku.
  const hadJoint = !!(only.attachedTo || (isProfilePart(only.part) && only.lastJoint) || (only.licPeers && only.licPeers.size));
  if (!hadJoint) return;
  ev.preventDefault();
  if (only.attachedTo) detachAccessory(only);
  if (isProfilePart(only.part) && only.lastJoint && typeof detachProfileJoint === "function") detachProfileJoint(only);
  if (only.licPeers && only.licPeers.size && typeof releaseAllJointsFor === "function") releaseAllJointsFor(only);
  rebuildOccupiedConnectors();
  refreshEndpointMarkers(); refreshDimLabels();
  refreshSummary();
  if (typeof showJoinToast === "function") showJoinToast("Odpojeno od profilu (všechny spoje tohoto dílu).");
  if (typeof refreshAxisMoveLabel === "function") refreshAxisMoveLabel();
});

// Robert 2026-07-25: "udelej funkci kopirovani oznacenych objektu (jedno
// i vicedilovy, spojeny i nespojeny) na CTRL+C, vytvor i plovouci
// tlacitko v ploe" + upresneni "pred vykreslenim kopie se system
// tabulkou zepta, kam se vlozi, tzn kolik mm v kazde ose."
//
// Kopiruje aktualni SJEDNOCENY vyber (currentJoinSelectionUnion - stejna
// funkce, kterou uz pouziva J/Spojit) - funguje tedy uplne stejne pro 1
// samostatny dil, vice jednotlive oznacenych dilu, i pro celou Join
// skupinu (diky expandSelectionToGroups, ktera do 60ms doplni vyber na
// CELOU skupinu, kdyz klikne uzivatel na jejiho clena).
//
// Fyzicke spoje (entry.jointCount/usedConn, viz PRAVIDLA_SPOJU.md 2d
// a 2m) se v kopii zachovaji jen tehdy, kdyz jsou cele "uvnitr"
// kopirovane sady (oba konce spoje jsou soucasti vyberu) - viz
// computeInternalConnectivity nize. Spoj smerujici VEN z kopirovane sady
// (k dilu, ktery se nekopiruje) by v kopii byl fyzicky neplatny (kopie
// se nic takoveho nedotyka), proto se pro TAKOVY dil cele pripojeni
// resetuje (bezpecny vychozi stav - radsi podhodnotit cenu spoju u
// vzacneho smiseneho pripadu, nez ji nadhodnotit).
function computeInternalConnectivity(entries) {
  const TOUCH_EPS = 0.75; // mm
  const worldConnCache = new Map();
  entries.forEach(e => worldConnCache.set(e, worldConnectorsOf(e)));
  const result = new Map();
  entries.forEach(e => {
    const used = e.usedConn ? Array.from(e.usedConn) : [];
    if (!used.length) { result.set(e, true); return; } // nic pouzite - neni co resit
    const myConns = worldConnCache.get(e);
    const allInternal = used.every(connIdx => {
      const myConn = myConns[connIdx];
      if (!myConn) return true;
      return entries.some(other => {
        if (other === e) return false;
        return worldConnCache.get(other).some(oc => oc.point.distanceTo(myConn.point) < TOUCH_EPS);
      });
    });
    result.set(e, allInternal);
  });
  return result;
}

// Vytvori nezavisle kopie dane sady dilu, posunute o `offset` (THREE.Vector3,
// mm), zachova Join skupinu a frameGroup (Ctverec/rám), pokud kopirovana
// sada presne odpovida cele existujici skupine/ramu. Vraci pole novych
// entries (v poradi odpovidajicim vstupu).
function duplicateEntries(entries, offset) {
  if (!entries || !entries.length) return [];
  const internalMap = computeInternalConnectivity(entries);
  const entryMap = new Map();

  entries.forEach(old => {
    // Object3D.clone(true) sdili geometrii i material se stavajicimi
    // instancemi (Three.js vychozi chovani) - to je zamerne v poradku:
    // material se pri kazdem obarveni (paintEntry -> applyPartMaterial)
    // vytvari VZDY jako novy objekt a jen se PREPISUJE reference na
    // konkretnim meshi, nikdy se nemutuje sdileny material "na miste" -
    // takze pozdejsi prebarveni originalu ani kopie nema vliv na tu
    // druhou stranu.
    const newObj = old.object3d.clone(true);
    // Robert 2026-08-02 ("kopirovane objekty pres CTRL C nech se
    // neoznacuji"): clone(true) SDILI materialy s originalem a original
    // je pri kopirovani prave oznaceny (zvyraznena barva je mutovana
    // primo v material.color - viz setSelectHighlight). Kopie proto
    // dostane VLASTNI klony materialu, vracene na puvodni (neoznacenou)
    // barvu - jinak by vypadala oznacene a kazde dalsi oznaceni
    // originalu by ji pres sdileny material obarvovalo taky.
    newObj.traverse(n => {
      if (n.isMesh && n.material) {
        n.material = n.material.clone();
        if (n.userData && n.userData.origMeshColor != null) {
          if (n.material.color) n.material.color.setHex(n.userData.origMeshColor);
          n.userData.origMeshColor = null;
          if (n.material.emissive) {
            n.material.emissive.setHex(0x000000);
            if (n.material.emissiveIntensity !== undefined) n.material.emissiveIntensity = 1;
          }
        }
      }
      if (n.userData && n.userData.isEdgesHelper && n.material) {
        n.material = n.material.clone();
        if (n.userData.origLineColor != null && n.material.color) {
          n.material.color.setHex(n.userData.origLineColor);
          n.userData.origLineColor = null;
        }
      }
    });
    newObj.position.add(offset);
    newObj.updateMatrixWorld(true);
    newObj.userData.basePos = newObj.position.clone();
    scene.add(newObj);

    const newEntry = {
      part: old.part,
      object3d: newObj,
      connectorsLocal: old.connectorsLocal, // nemenne geometricke konstanty - bezpecne sdilet referenci
    };
    // bot8 2026-09-16 (Robert, 3 incidenty "Uloz oprava" prepsala sestavu
    // cizim obsahem): SKUTECNA prvotni pricina - kopirovani (Ctrl+C /
    // btnCopySelection) role vubec neprenaselo na kopii. Kopie dilu ze
    // ulozene sestavy (napr. "eurobox-sloupec0-patro0") tak ztratila svou
    // semantickou identitu - vypadala stejne, ale serializeEntryForSave
    // (`if (entry.role) out.role = entry.role`) uz ji neulozil s rolí.
    // Kdyz uzivatel pak smazal originaly a ulozil, zbyla scena vypadala
    // "cizi" (0 roli) - presne signatura vsech tri dnesnich incidentu.
    if (old.role) newEntry.role = old.role;
    if (old.customColor) newEntry.customColor = old.customColor;

    if (internalMap.get(old)) {
      if (old.usedConn) newEntry.usedConn = new Set(old.usedConn);
      if (old.hiddenEndConn) newEntry.hiddenEndConn = new Set(old.hiddenEndConn);
      newEntry.jointCount = old.jointCount || 0;
      if (old.wasThrough) newEntry.wasThrough = true;
      if (old.wasAttached) newEntry.wasAttached = true;
      if (old.vertical) newEntry.vertical = true;
    } else {
      // Smiseny/vnejsi pripad (viz komentar u funkce vyse) - bezpecny reset.
      newEntry.usedConn = new Set();
      newEntry.jointCount = 0;
    }

    placed.push(newEntry);
    entryMap.set(old, newEntry);
  });

  // Robert 2026-08-04 ("napocita 4 spoje u dvou prilehlych profilu na
  // rodice" po kopirovani): kopie PROFILU dedila jointCount z originalu,
  // ale licPeers se nekopiruji - auto-registrace dotykem (nova, dnesni)
  // pak tentyz fyzicky spoj pricetla PODRUHE (dedup v registerLicJoint
  // je prave pres licPeers). U kopie samotneho profilu navic zustaval
  // "fantomovy" pocet za spoj, ktery kopie vubec nema (jeji partner se
  // nekopiroval). Oprava: pocty spoju profilu v kopii se REBUILDNOU
  // ciste z paru UVNITR kopirovane sady - viz
  // rebuildCopiedProfileJointAccounting nize.
  rebuildCopiedProfileJointAccounting(entries, entryMap);

  // Robert 2026-08-02 ("kopirovany objekt pomoci CTRL+C a ktery je
  // zaroven pripojenym prislusenstvim k nejakemu profilu ci objektu,
  // nech se jeho kopie stane taktez pripojenym ke stejnemu profilu" +
  // upresneni "bez posuvu"): kopie pripojeneho prislusenstvi prebira
  // stav "pripojeno" - BEZ jakehokoli dalsiho posouvani ci prichytavani
  // (kopie zustava presne tam, kam ji polozil offset z kopirovaciho
  // dialogu; ZADNY snap na stred plochy profilu). Diky tomu na kopii
  // hned funguje R / rotacni prstenec, U (odpojit), zastavovani na
  // rovine cela pri posunu i cenove uctovani spoje. Kdyz se spolu s
  // prislusenstvim kopiruje i jeho profil, pripoji se kopie ke KOPII
  // profilu (entryMap); jinak ke stejnemu originalnimu profilu.
  // Ucetnictvi (usedConn/jointCount) se dopocitava jen kdyz ho
  // nepokrylo kopirovani "vnitrnich" spoju vyse (internalMap false =
  // usedConn/jointCount byly resetovane); licPeers se nekopiruji nikdy,
  // takze vazba se registruje vzdy.
  entries.forEach(old => {
    if (!old.attachedTo || !old.attachedTo.profEntry) return;
    if (isProfilePart(old.part)) return; // tyka se jen prislusenstvi
    const newEntry = entryMap.get(old);
    if (!newEntry || newEntry.attachedTo) return;
    const at = old.attachedTo;
    const targetProf = entryMap.get(at.profEntry) || at.profEntry;
    if (!placed.includes(targetProf)) return; // profil uz neni ve scene
    newEntry.attachedTo = {
      profEntry: targetProf,
      forcedParentConnIdx: at.forcedParentConnIdx,
      childFaceConnIdx: at.childFaceConnIdx,
      spinIndex: at.spinIndex || 0,
    };
    newEntry.usedConn = newEntry.usedConn || new Set();
    if (!internalMap.get(old)) {
      newEntry.usedConn.add(at.childFaceConnIdx);
      // Robert 2026-08-04: spoj prislusenstvi-profil se NEpocita (viz
      // applyFaceToFaceCandidate) - drivejsi "+1" pro kopii pripojeneho
      // prislusenstvi odstranen, pripojeni (attachedTo/licPeers) zustava.
    }
    if (typeof linkJointPeers === "function") linkJointPeers(newEntry, targetProf);
  });

  // Zachovat Join skupinu, pokud kopirovana sada PRESNE odpovida cele
  // existujici skupine.
  if (typeof jointGroups !== "undefined") {
    const matched = jointGroups.find(g => g.size === entries.length && entries.every(e => g.has(e)));
    if (matched) {
      jointGroups.push(new Set(entries.map(e => entryMap.get(e))));
    }
  }

  // Zachovat frameGroup (Ctverec/rám), pokud kopirovana sada PRESNE
  // odpovida vsem 4 dilum existujiciho ramu - kopie tak zustane stejne
  // "natahovatelna" modrymi sipkami jako original.
  const first = entries[0];
  if (first && first.frameGroup) {
    const fg = first.frameGroup;
    const fEntries = [fg.entryA, fg.entryB, fg.entryC, fg.entryD];
    if (fEntries.length === entries.length && fEntries.every(e => entries.includes(e))) {
      const newFrameMeta = {
        kind: "rectFrame",
        entryA: entryMap.get(fg.entryA),
        entryB: entryMap.get(fg.entryB),
        entryC: entryMap.get(fg.entryC),
        entryD: entryMap.get(fg.entryD),
      };
      [newFrameMeta.entryA, newFrameMeta.entryB, newFrameMeta.entryC, newFrameMeta.entryD].forEach(e => { e.frameGroup = newFrameMeta; });
    }
  }

  return entries.map(e => entryMap.get(e));
}

// Robert 2026-08-02 ("to ctrl+C u pripojeneho prislusenstvi... nemelo by
// se tam vubec objevit kopirovaci okno a objevit by se mel na stejne
// stene profilu o silu profilu dal"): Ctrl+C na JEDINEM pripojenem
// prislusenstvi preskakuje kopirovaci dialog uplne - kopie se rovnou
// polozi na STEJNOU stenu profilu, posunuta podel jeho delky o "silu
// profilu" (vetsi rozmer prurezu, napr. 30mm u profilu 30x30 - kopie
// tak sedi hned vedle originalu). Smer: k druhemu konci profilu; kdyz
// tam neni misto (original u konce), otoci se; kdyz neni misto ani na
// jedne strane, kopie se nevytvori (toast). Dil sedici na CELE se
// posouva smerem VEN od profilu (dovnitr by se zaryl do tela profilu).
// Pripojeni kopie (attachedTo/usedConn/jointCount/licPeers) resi
// duplicateEntries - viz jeho druhy pruchod.
// Robert 2026-08-04 ("napocita 4 spoje..."): rebuild uctu spoju PROFILU
// v kopii - jointCount kopii profilu se vynuluje a znovu postavi JEN z
// paru, kde jsou OBE strany soucasti kopirovane sady (pak se kopie
// propoji pres linkJointPeers - dedup registr pro auto-registraci - a
// pocet se pricte jednou na jedne strane paru). lastJoint se namapuje na
// kopie, aby na nich hned fungovalo R. Spoje smerujici VEN ze sady se u
// kopie NEprenaseji (kopie lezi jinde; kdyz ji uzivatel privede na dotyk,
// pricte ji spoj auto-registrace) - stejna filozofie "radsi podhodnotit"
// jako u computeInternalConnectivity. Prislusenstvi se tady nedotyka
// (jeho ucetnictvi resi attachedTo pruchod nize).
function rebuildCopiedProfileJointAccounting(entries, entryMap) {
  entries.forEach(old => {
    if (!old.part || !isProfilePart(old.part)) return;
    const ne = entryMap.get(old);
    if (ne) ne.jointCount = 0;
  });
  entries.forEach(old => {
    if (!old.part || !isProfilePart(old.part)) return;
    const copyA = entryMap.get(old);
    if (!copyA) return;
    if (old.licPeers) {
      old.licPeers.forEach(peer => {
        if (!peer || !peer.part || !isProfilePart(peer.part)) return;
        const copyB = entryMap.get(peer);
        if (!copyB) return;
        if (copyA.licPeers && copyA.licPeers.has(copyB)) return; // par uz zpracovan z druhe strany
        linkJointPeers(copyA, copyB);
        copyA.jointCount = (copyA.jointCount || 0) + 1;
      });
    }
    if (old.lastJoint && old.lastJoint.otherEntry && entryMap.get(old.lastJoint.otherEntry)) {
      copyA.lastJoint = {
        otherEntry: entryMap.get(old.lastJoint.otherEntry),
        myConnIdx: old.lastJoint.myConnIdx,
        otherConnIdx: old.lastJoint.otherConnIdx,
        iHoldCount: old.lastJoint.iHoldCount,
        candidateSig: old.lastJoint.candidateSig,
      };
    }
  });
}

// Robert 2026-08-04 ("pri kopirovani pripojenych profilu to chce
// zkopirovani bez volby pozice, automaticky proste hned vedle sebe"):
// stejny princip jako copyAttachedAccessoryAlongProfile nize, ale pro
// JEDEN oznaceny PROFIL spojeny s jinym profilem - zadny dialog, kopie
// se polozi hned vedle originalu podel delky PARTNERA (posun = rozmer
// kopirovaneho dilu podel tehle osy + 5mm mezirka, aby se kopie
// nedotykala originalu a nepocital se falesny spoj kopie-original).
// Kopie zustava na stene partnera -> spoj se ji hned zaregistruje
// (autoRegisterTouchedProfileJoints vc. lastJoint pro R). U spoje na
// CELE partnera (rovne prodlouzeni) se kopie posouva smerem VEN od
// partnera. Vraci false = pokracovat beznym dialogem.
function copyAttachedProfileAlongPartner(profEntry) {
  if (!profEntry.part || !isProfilePart(profEntry.part)) return false;
  let partner = null;
  if (profEntry.lastJoint && profEntry.lastJoint.otherEntry && placed.includes(profEntry.lastJoint.otherEntry) &&
      profEntry.lastJoint.otherEntry.part && isProfilePart(profEntry.lastJoint.otherEntry.part)) {
    partner = profEntry.lastJoint.otherEntry;
  } else if (profEntry.licPeers) {
    profEntry.licPeers.forEach(p => {
      if (!partner && p && placed.includes(p) && p.part && isProfilePart(p.part)) partner = p;
    });
  }
  if (!partner) return false;
  const endIdxs = [];
  partner.connectorsLocal.forEach((c, i) => { if (c.kind === "end") endIdxs.push(i); });
  if (endIdxs.length !== 2) return false;
  const pw = worldConnectorsOf(partner);
  const A = pw[endIdxs[0]].point, B = pw[endIdxs[1]].point;
  const axis = B.clone().sub(A);
  const L = axis.length();
  if (L < 1e-6) return false;
  axis.normalize();
  profEntry.object3d.updateMatrixWorld(true);
  const bbox = new THREE.Box3().setFromObject(profEntry.object3d);
  if (bbox.isEmpty()) return false;
  let mn = Infinity, mx = -Infinity;
  for (let xi = 0; xi < 2; xi++) for (let yi = 0; yi < 2; yi++) for (let zi = 0; zi < 2; zi++) {
    const corner = new THREE.Vector3(
      xi ? bbox.max.x : bbox.min.x,
      yi ? bbox.max.y : bbox.min.y,
      zi ? bbox.max.z : bbox.min.z);
    const t = corner.sub(A).dot(axis);
    if (t < mn) mn = t;
    if (t > mx) mx = t;
  }
  const step = (mx - mn) + 5; // vlastni rozmer podel osy partnera + mezirka
  const jointKind = (profEntry.lastJoint && partner.connectorsLocal[profEntry.lastJoint.otherConnIdx])
    ? partner.connectorsLocal[profEntry.lastJoint.otherConnIdx].kind : null;
  let dir = 0;
  if (jointKind === "end") {
    dir = ((mn + mx) / 2 >= L / 2) ? 1 : -1; // na cele: ven od partnera
  } else {
    if (mx + step <= L + 1e-6) dir = 1;
    else if (mn - step >= -1e-6) dir = -1;
    if (!dir) {
      showJoinToast("Kopie se vedle originálu na partnera nevejde.");
      return true; // vyrizeno (bez kopie i bez dialogu)
    }
  }
  const offset = axis.clone().multiplyScalar(dir * step);
  const newEntries = duplicateEntries([profEntry], offset);
  if (newEntries && newEntries[0] && typeof autoRegisterTouchedProfileJoints === "function") {
    autoRegisterTouchedProfileJoints(newEntries[0]);
  }
  rebuildOccupiedConnectors();
  refreshEndpointMarkers(); refreshDimLabels();
  refreshSummary();
  showJoinToast("Kopie profilu přidána hned vedle originálu (o " + Math.round(step) + " mm dál, rovnou se spojem).");
  return true;
}

function copyAttachedAccessoryAlongProfile(accEntry) {
  const at = accEntry.attachedTo;
  if (!at || !at.profEntry || !placed.includes(at.profEntry)) return false;
  const profEntry = at.profEntry;
  const endIdxs = [];
  profEntry.connectorsLocal.forEach((c, i) => { if (c.kind === "end") endIdxs.push(i); });
  if (endIdxs.length !== 2) return false;
  const profWorld = worldConnectorsOf(profEntry);
  const A = profWorld[endIdxs[0]].point, B = profWorld[endIdxs[1]].point;
  const axis = B.clone().sub(A);
  const L = axis.length();
  if (L < 1e-6) return false;
  axis.normalize();
  const cs = profEntry.part.cross_section_mm || [];
  const thickness = Math.max(cs[0] || 0, cs[1] || 0) || 30;
  accEntry.object3d.updateMatrixWorld(true);
  const bbox = new THREE.Box3().setFromObject(accEntry.object3d);
  if (bbox.isEmpty()) return false;
  let mn = Infinity, mx = -Infinity;
  for (let xi = 0; xi < 2; xi++) for (let yi = 0; yi < 2; yi++) for (let zi = 0; zi < 2; zi++) {
    const corner = new THREE.Vector3(
      xi ? bbox.max.x : bbox.min.x,
      yi ? bbox.max.y : bbox.min.y,
      zi ? bbox.max.z : bbox.min.z);
    const t = corner.sub(A).dot(axis);
    if (t < mn) mn = t;
    if (t > mx) mx = t;
  }
  const parentKind = profEntry.connectorsLocal[at.forcedParentConnIdx].kind;
  let dir = 0;
  if (parentKind === "face") {
    if (mx + thickness <= L + 1e-6) dir = 1;
    else if (mn - thickness >= -1e-6) dir = -1;
    if (!dir) {
      showJoinToast("Kopie se vedle originálu na profil nevejde.");
      return true; // vyrizeno (bez kopie i bez dialogu)
    }
  } else {
    // dil na cele: ven od profilu
    dir = ((mn + mx) / 2 >= L / 2) ? 1 : -1;
  }
  const offset = axis.clone().multiplyScalar(dir * thickness);
  duplicateEntries([accEntry], offset);
  rebuildOccupiedConnectors();
  refreshEndpointMarkers(); refreshDimLabels();
  refreshSummary();
  showJoinToast("Kopie přidána na stejné stěně profilu o " + Math.round(thickness) + " mm dál (rovnou připojená).");
  return true;
}

let pendingCopyEntries = null;

function openCopyDialog() {
  expandSelectionToGroups();
  const entries = Array.from(currentJoinSelectionUnion());
  if (!entries.length) {
    showJoinToast("Nejdřív označ díl(y) ke kopírování (Mikroposuv nebo Posun myší).");
    return;
  }
  // Robert 2026-08-02: Ctrl+C na jedinem PRIPOJENEM prislusenstvi =
  // zadny dialog, kopie rovnou vedle originalu na stejne stene (viz
  // copyAttachedAccessoryAlongProfile vyse). Kdyz helper vrati false
  // (degenerovany pripad - profil bez 2 cel apod.), pokracuje se
  // normalnim dialogem.
  if (entries.length === 1 && !isProfilePart(entries[0].part) && entries[0].attachedTo &&
      typeof copyAttachedAccessoryAlongProfile === "function" &&
      copyAttachedAccessoryAlongProfile(entries[0])) {
    return;
  }
  // Robert 2026-08-04 ("pri kopirovani pripojenych profilu to chce
  // zkopirovani bez volby pozice, automaticky proste hned vedle sebe"):
  // stejny princip i pro JEDEN oznaceny PROFIL spojeny s jinym profilem.
  if (entries.length === 1 && isProfilePart(entries[0].part) &&
      typeof copyAttachedProfileAlongPartner === "function" &&
      copyAttachedProfileAlongPartner(entries[0])) {
    return;
  }
  pendingCopyEntries = entries;
  const box = new THREE.Box3();
  entries.forEach(e => { e.object3d.updateMatrixWorld(true); box.union(new THREE.Box3().setFromObject(e.object3d)); });
  const size = new THREE.Vector3();
  box.getSize(size);
  const hintEl = document.getElementById("copyOffsetHint");
  if (hintEl) hintEl.textContent = `Kopíruje se ${entries.length} ${entries.length === 1 ? "díl" : "dílů"}. Zadej posun kopie od originálu v mm.`;
  document.getElementById("copyOffsetX").value = Math.round(size.x || 100);
  document.getElementById("copyOffsetY").value = 0;
  document.getElementById("copyOffsetZ").value = 0;
  document.getElementById("copyOffsetPanel").style.display = "block";
  const xInput = document.getElementById("copyOffsetX");
  xInput.focus();
  xInput.select();
}

function closeCopyDialog() {
  pendingCopyEntries = null;
  document.getElementById("copyOffsetPanel").style.display = "none";
}

function confirmCopyDialog() {
  if (!pendingCopyEntries || !pendingCopyEntries.length) { closeCopyDialog(); return; }
  const entries = pendingCopyEntries;
  const dx = parseFloat((document.getElementById("copyOffsetX").value || "0").replace(",", ".")) || 0;
  const dy = parseFloat((document.getElementById("copyOffsetY").value || "0").replace(",", ".")) || 0;
  const dz = parseFloat((document.getElementById("copyOffsetZ").value || "0").replace(",", ".")) || 0;
  // Robert 2026-07-25 ("kopiroval jsem dily v ose z ale nakladali se
  // spatne"): stejna past jako uz jednou zapsana u axisMoveWorldDir a
  // Uzemnit - v UI "Z" vzdy znamena VYSKU (realna THREE osa Y), "Y" v UI
  // znamena hloubku (realna THREE osa Z). Puvodni verze tohodle dialogu
  // stavela offset primo z dx/dy/dz beze svapu, takze zadani hodnoty do
  // pole "Z" (Robert cekal posun vzhuru) ve skutecnosti posunulo kopii po
  // realne ose Z - u dilu, jehoz vlastni delkova osa smeruje prave tímto
  // smerem, se kopie tak jen "nastavila" za puvodni dil (viz Robertuv
  // screenshot: 3x 1000mm v jedne primce misto vertikalniho stohu).
  const offset = new THREE.Vector3(dx, dz, dy);

  const newEntries = duplicateEntries(entries, offset);

  // Robert 2026-08-02 ("kopirovane objekty pres CTRL C nech se
  // neoznacuji"): drivejsi chovani (vyber se presunul z originalu na
  // kopie, viz git historie tohoto mista) zruseno - kopie se ted
  // NEOZNACUJI vubec a vyber zustava beze zmeny na ORIGINALECH (v tom
  // rezimu, ve kterem byly vybrane). Kopie je proste jen polozena vedle
  // s poZadanym posunem.

  rebuildOccupiedConnectors();
  refreshEndpointMarkers(); refreshDimLabels();
  refreshSummary();
  showJoinToast(`Vytvořena kopie (${newEntries.length} ${newEntries.length === 1 ? "díl" : "dílů"}) - kopie není označena, výběr zůstává na originálu.`);
  closeCopyDialog();
}

document.getElementById("btnCopySelection").addEventListener("click", openCopyDialog);
document.getElementById("btnCopyConfirm").addEventListener("click", confirmCopyDialog);
document.getElementById("btnCopyCancel").addEventListener("click", closeCopyDialog);
["copyOffsetX", "copyOffsetY", "copyOffsetZ"].forEach(id => {
  const el = document.getElementById(id);
  if (!el) return;
  el.addEventListener("keydown", (ev) => {
    if (ev.key === "Enter") { ev.preventDefault(); confirmCopyDialog(); }
    else if (ev.key === "Escape") { ev.preventDefault(); closeCopyDialog(); }
  });
});

window.addEventListener("keydown", (ev) => {
  if (!(ev.ctrlKey || ev.metaKey)) return;
  if (ev.key.toLowerCase() !== "c") return;
  const tag = (ev.target && ev.target.tagName) || "";
  if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return; // necháme normalni CTRL+C v textovych polich
  if (dragState) return;
  if (typeof axisMoveDragState !== "undefined" && axisMoveDragState) return;
  if (typeof rotateActive !== "undefined" && rotateActive) return;
  ev.preventDefault();
  openCopyDialog();
});

// Robert 2026-08-02 ("pridej do sceny tlacitko na vyexportovani
// oznacenych objektu do fbx pro ulozeni na PC"): oznacene dily (union
// Mikroposuv + Posun mysi, vc. celych Join skupin) se prevedou na
// Wavefront OBJ text - trojuhelniky ve SVETOVYCH souradnicich (mm),
// tj. presne tak, jak dily prave stoji ve scene - a poslou na server
// (/api/export-fbx), kde je CLI nastroj assimp prevede na binarni
// Autodesk FBX a vrati jako stazeni. three.js zadny FBX exporter nema
// (jen FBXLoader), proto prevod bezi na serveru. Exportuje se cista
// geometrie (bez barev/materialu); hrany (isEdgesHelper) a jine
// pomocne ne-mesh objekty se preskakuji.
function buildObjFromEntries(entries) {
  const lines = ["# Konfigurator 3D export", "# jednotky: mm, svetove souradnice sceny"];
  let vOffset = 1;
  let objIndex = 0;
  const pos = new THREE.Vector3();
  entries.forEach(entry => {
    objIndex += 1;
    const rawName = (entry.part && (entry.part.name || entry.part.nazev)) || "dil";
    const name = String(rawName).normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/[^A-Za-z0-9_-]+/g, "_").slice(0, 40) || "dil";
    lines.push("o " + name + "_" + objIndex);
    entry.object3d.updateMatrixWorld(true);
    entry.object3d.traverse(n => {
      if (!n.isMesh || !n.geometry || !n.geometry.getAttribute) return;
      if (n.userData && n.userData.isEdgesHelper) return;
      const attr = n.geometry.getAttribute("position");
      if (!attr) return;
      for (let i = 0; i < attr.count; i++) {
        pos.fromBufferAttribute(attr, i).applyMatrix4(n.matrixWorld);
        lines.push("v " + pos.x.toFixed(4) + " " + pos.y.toFixed(4) + " " + pos.z.toFixed(4));
      }
      const index = n.geometry.getIndex();
      if (index) {
        for (let i = 0; i + 2 < index.count; i += 3) {
          lines.push("f " + (vOffset + index.getX(i)) + " " + (vOffset + index.getX(i + 1)) + " " + (vOffset + index.getX(i + 2)));
        }
      } else {
        for (let i = 0; i + 2 < attr.count; i += 3) {
          lines.push("f " + (vOffset + i) + " " + (vOffset + i + 1) + " " + (vOffset + i + 2));
        }
      }
      vOffset += attr.count;
    });
  });
  return lines.join("\n") + "\n";
}

function exportSelectionToFbx() {
  expandSelectionToGroups();
  const entries = Array.from(currentJoinSelectionUnion());
  if (!entries.length) {
    showJoinToast("Nejdřív označ díl(y) k exportu (Mikroposuv nebo Posun myší).");
    return;
  }
  const btn = document.getElementById("btnExportFbx");
  const objText = buildObjFromEntries(entries);
  if (btn) { btn.disabled = true; btn.textContent = "⏳ Exportuji…"; }
  fetch("/api/export-fbx", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ obj: objText }),
  }).then(r => {
    if (!r.ok) return r.json().then(j => { throw new Error(j.error || ("HTTP " + r.status)); });
    return r.blob();
  }).then(blob => {
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "konfigurator_export_" + new Date().toISOString().slice(0, 10) + ".fbx";
    document.body.appendChild(a);
    a.click();
    setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 2000);
    showJoinToast("FBX vyexportováno (" + entries.length + " " + (entries.length === 1 ? "díl" : "dílů") + ") - ukládá se do Stažených.");
  }).catch(err => {
    showJoinToast("Export FBX selhal: " + err.message);
  }).finally(() => {
    if (btn) { btn.disabled = false; btn.textContent = "📦 Export FBX"; }
  });
}
document.getElementById("btnExportFbx").addEventListener("click", exportSelectionToFbx);

// Puvodne (Robert 2026-07-25) "Najdi spoje" - plosne DOHLEDAVANI spoju:
// oznacena sada se skenovala proti VSEM polozenym dilum ve scene pres
// bounding-box "dotyk plochy" heuristiku (EPS_FACE/EPS_OVERLAP toleranci)
// a kazdy nalezeny dotyk se rovnou PRICETL jako novy spoj (registerLicJoint).
// Dulod vzniku: rucne poposunute dily bez pouziti Pripoj/Pripoj2/tazeni
// mely spoj fyzicky viditelny, ale nikde nezapocitany.
//
// PREJMENOVANO A PREPRACOVANO na "Spocitej spoje" (Robert 2026-08-10):
// "v podstate ve scene uz nespojujeme profily jinak nez tak, ze se
// propoji tlacitkem [Pripoj/Pripoj2] u slozitejsich sestav se zda, ze
// se pocet spoju vygeneruje chybne." Plosne skenovani proti VSEM dilum
// ve scene je dnes zbytecne (kazdy skutecny spoj uz vznika a pocita se
// primo pri spojeni - attachEntryToParent/registerJoint/registerLicJoint,
// a autoRegisterTouchedProfileJoints navic automaticky dopocita i spoj
// vznikly pouhym pritazenim k sobe) a u husteho/sloziteho rozlozeni dilu
// (napr. mrizka bliz sebe polozenych profilu) plodi FALESNE POZITIVNI
// nalezy - 2 dily blizko sebe na vsech 3 osach, aniz by šlo o skutecny
// zamysleny spoj, se stejnou heuristikou tez vyhodnoti jako "dotyk".
//
// Nova funkce uz NIC neregistruje ani nehleda geometricky - jen SECTE
// jiz drive zapocitane jointCount napric oznacenou sestavou (rozsirenou
// o cele Join skupiny) a vysledek ohlasi. Slouzi jako kontrolni/
// informativni nastroj ("kolik spoju ma tahle sestava"), ne jako zdroj
// novych spoju - cena uz je vzdy zivotne (refreshSummary) v souladu s
// entry.jointCount, tenhle vypocet na ni tedy nic nemeni.
//
// Robert 2026-08-10 (navazujici pozadavek): "necht tato funkce zaroven
// napocitane spoje oznaci primo ve scene" - k toastu s cislem pribyla i
// vizualni znacka v miste kazdeho zapocitaneho spoje, aby slo hned videt
// KDE presne se pocitane spoje nachazi, ne jen kolik jich je.
// OPRAVA (Robert, tyz den): puvodni zlata barva byla moc blizko barve
// oznaceni dilu (selectHighlightColor, vychozi 0xff9900) a znacky mizely
// uz po 4s - zmeneno na cervenou (jasne odlisitelnou od oznaceni) a misto
// casovace se drzi VIDITELNE, dokud uzivatel neudela dalsi akci mysi ve
// viewportu - mizi az na PRVNI dalsi pointerdown na renderer.domElement
// (jakykoli klik, zacatek tazeni dilu i zacatek orbitovani kamerou).
const JOINT_COUNT_MARKER_COLOR = 0xff2020;
const JOINT_COUNT_MARKER_RADIUS = 22; // mm
const jointCountMarkerGeom = new THREE.SphereGeometry(JOINT_COUNT_MARKER_RADIUS, 16, 12);
let jointCountMarkers = [];
function clearJointCountMarkers() {
  jointCountMarkers.forEach(m => scene.remove(m));
  jointCountMarkers = [];
  renderer.domElement.removeEventListener("pointerdown", clearJointCountMarkers);
}

// Znacka je jen VIZUALNI pomucka, ne zdroj pravdy o spoji.
// OPRAVA (Robert - screenshot: 3 tecky slepene na jednom miste u sloupku
// se 2 rozdilnymi T-spoji): puvodni verze hledala "nejblizsi dvojici ze
// VSECH connectorsLocal" - u obycejneho profilu je to ale jen 2 "end" +
// 1 "mid" (VZDY presne ve stredu delky, viz computeConnectorsLocal), takze
// realny T-spoj v LIBOVOLNE jine vysce podel delky rodice nema odpovidajici
// bod v zadnem z techto 3 pevnych mist - vice ruznych T-spoju na stejnem
// dilu se tak vizualne "slepilo" na to same (nejblizsi z techto 3) misto,
// misto aby kazdy dostal znacku na svem skutecnem miste.
// Reseni: prednostne pouzit PRESNY zaznamenany bod spoje (entry.lastJoint -
// child strana ho vzdy ma presne tam, kde se fyzicky dotyka rodice, viz
// attachEntryToParent/registerJoint/autoRegisterTouchedProfileJoints).
// Slepe hledani nejblizsi dvojice zustava jen jako zalozni varianta pro
// pripady bez lastJoint (cisty Licovani-only par).
function nearestJointPointBetween(entryA, entryB) {
  const ljA = entryA.lastJoint;
  if (ljA && ljA.otherEntry === entryB) {
    const wc = worldConnectorsOf(entryA)[ljA.myConnIdx];
    if (wc) return wc.point.clone();
  }
  const ljB = entryB.lastJoint;
  if (ljB && ljB.otherEntry === entryA) {
    const wc = worldConnectorsOf(entryB)[ljB.myConnIdx];
    if (wc) return wc.point.clone();
  }
  const connsA = worldConnectorsOf(entryA);
  const connsB = worldConnectorsOf(entryB);
  let best = null, bestDist = Infinity;
  connsA.forEach(ca => connsB.forEach(cb => {
    const d = ca.point.distanceTo(cb.point);
    if (d < bestDist) { bestDist = d; best = ca.point.clone().add(cb.point).multiplyScalar(0.5); }
  }));
  return best;
}

// Robert 2026-08-10 (dalsi navazujici hlaseni: "tech cervenych tecek je
// tam vic nez skutecnych spoju" na slozite sestave): znacky verne kopiruji
// entry.licPeers - pokud jich je vic nez realnych spoju, je nafouklé uz
// samotne ucetnictvi (licPeers/jointCount), ne vykreslovani znacek.
// Zdroj: "mekke" obecne dotyky bounding-boxu (Licovani, automaticke
// spojeni pri tazeni - autoRegisterTouchedProfileJoints) NIKDY
// nenastavuji usedConn, na rozdil od "tvrdych" spoju vznikajicich pres
// skutecne pouzivane tlacitko spojeni (Pripoj/Pripoj2/AI/presety -
// attachEntryToParent/registerJoint). V hustych/slozitych sestavach tyhle
// mekke dotyky snadno vzniknou i tam, kde jde jen o dily blizko sebe, ne o
// zamysleny spoj. Robert zvolil: pri kazdem spusteni "Spocitej spoje" se
// mekke spoje na oznacene sestave zahodi (odectou z jointCount/ceny).
//
// OPRAVA (Robert: "ted napocita 0 spoju"): 2 predchozi pokusy nefungovaly:
// (1) poznavani "tvrdeho" spoje z GEOMETRIE (jsou pouzite konektory obou
// dilu blizko sebe?) - spatny predpoklad, u T-spoju/rohu se pripojovany
// dil ZAMERNE odsazuje od konektoru rodice (plocha na plochu, ne stred na
// stred), takze konektory u naprosto BEZNEHO T-spoje/rohu nejsou blizko
// sebe vubec. (2) priznak pro TVRDY spoj (hardJointPeers) - nebezpecny
// pro uz rozestavenou scenu z PRED timhle nasazenim, protoze i stare
// tvrde spoje by priznak nemely a vsechny by se omylem zahodily.
// Financialni reseni: priznak JEN pro MEKKY spoj (softJointPeers, viz
// registerLicJoint - jedine misto vzniku mekkeho spoje) - vse ostatni,
// vcetne starych jeste neoznackovanych spoju z pred timhle nasazenim, se
// bere jako duveryhodne a NEODEBIRA se. Bezpecny vychozi stav "kdyz si
// nejsem jisty, nech to byt", ne "kdyz si nejsem jisty, smaz to".
function isSoftTaggedJoint(entryA, entryB) {
  return !!(entryA.softJointPeers && entryA.softJointPeers.has(entryB))
    || !!(entryB.softJointPeers && entryB.softJointPeers.has(entryA));
}

// Odpoji "entry" a "peer" od sebe navzajem (licPeers/softJointPeers/
// jointCount/usedConn/lastJoint) - stejny zpusob odregistrace jako
// releaseBrokenProfileJoints (preferuje detachProfileJoint, kdyz lastJoint
// odpovida - spravne resi iHoldCount; jinak rucni odecet licPeers/
// jointCount/softJointPeers jako zalozni vetev). Obecny nazev (ne "discard
// soft") - pouziva se jak pro zahazovani mekkych spoju pri "Spocitej
// spoje", tak pro uklid PRI MAZANI dilu (viz releaseAllJointsFor nize).
function severJointPair(entry, peer) {
  if (entry.lastJoint && entry.lastJoint.otherEntry === peer) {
    detachProfileJoint(entry);
  } else if (peer.lastJoint && peer.lastJoint.otherEntry === entry) {
    detachProfileJoint(peer);
  } else {
    if (entry.licPeers) entry.licPeers.delete(peer);
    if (peer.licPeers) peer.licPeers.delete(entry);
    if (entry.softJointPeers) entry.softJointPeers.delete(peer);
    if (peer.softJointPeers) peer.softJointPeers.delete(entry);
    if ((entry.jointCount || 0) > 0) entry.jointCount -= 1;
    else if ((peer.jointCount || 0) > 0) peer.jointCount -= 1;
  }
}

// Robert 2026-08-10 ("Pripoj2, s pripojeny profil posunu pripadne odmazu,
// ale zustane tam nejaky konektor ci neco co nema") - potvrzeno: mazani
// dilu (removeLast/deleteSelectedEntries) mazany dil jen odstranilo ze
// `placed`, ale NIKDY neuklidilo jeho stranu vztahu u PREZIJICIHO peera -
// ten si dal "pamatoval" spoj (licPeers/jointCount/lastJoint/usedConn) k
// dilu, ktery uz ve scene vubec neni. Takovy "osireny" spoj se pak
// pocital do souctu (Spocitej spoje i cena), ale ZADNOU znacku nedostal
// (viz markCountedJoints - dvojice s chybejicim peerem se preskakuji) -
// cislo v toastu tak mohlo byt vyssi, nez kolik tecek se skutecne ukazalo.
// Vola se PRED odstranenim entry z `placed` u KAZDEHO jeho peera (entry
// muze mit VICE peeru - napr. sloupek spojeny s vice prycnami v ruznych
// vyskach - entry.lastJoint je jen POSLEDNI z nich, proto se prochazi
// cele entry.licPeers, ne jen lastJoint).
function releaseAllJointsFor(entry) {
  if (!entry || !entry.licPeers || !entry.licPeers.size) return;
  Array.from(entry.licPeers).forEach(peer => {
    if (peer && placed.includes(peer)) severJointPair(entry, peer);
  });
}

// Projde vsechny licPeers dvojice dotcene oznacenou sestavou a zahodi ty
// oznacene priznakem softJointPeers (viz isSoftTaggedJoint vyse). Vraci
// pocet zahozenych spoju.
function discardSoftJointsForEntries(entries) {
  const seenPairs = new Set();
  let discarded = 0;
  entries.forEach(entry => {
    if (!entry.licPeers) return;
    Array.from(entry.licPeers).forEach(peer => {
      const ia = placed.indexOf(entry), ib = placed.indexOf(peer);
      if (ia < 0 || ib < 0) return; // spoj smerujici na uz odstraneny dil
      const key = ia < ib ? ia + "_" + ib : ib + "_" + ia;
      if (seenPairs.has(key)) return;
      seenPairs.add(key);
      if (isSoftTaggedJoint(entry, peer)) {
        severJointPair(entry, peer);
        discarded++;
      }
    });
  });
  return discarded;
}

function markCountedJoints(entries) {
  clearJointCountMarkers();
  const seenPairs = new Set();
  entries.forEach(entry => {
    if (!entry.licPeers) return;
    entry.licPeers.forEach(peer => {
      const ia = placed.indexOf(entry), ib = placed.indexOf(peer);
      if (ia < 0 || ib < 0) return; // spoj smerujici na uz odstraneny dil
      const key = ia < ib ? ia + "_" + ib : ib + "_" + ia;
      if (seenPairs.has(key)) return;
      seenPairs.add(key);
      const point = nearestJointPointBetween(entry, peer);
      if (!point) return;
      const mat = new THREE.MeshBasicMaterial({ color: JOINT_COUNT_MARKER_COLOR, transparent: true, opacity: 0.85, depthTest: false });
      const mesh = new THREE.Mesh(jointCountMarkerGeom, mat);
      mesh.position.copy(point);
      mesh.renderOrder = 999;
      scene.add(mesh);
      jointCountMarkers.push(mesh);
    });
  });
  if (jointCountMarkers.length) {
    renderer.domElement.addEventListener("pointerdown", clearJointCountMarkers, { once: true });
  }
}

// Robert 2026-08-10 ("uprav tu funkci jeste tak ze pocita spoje ve scene
// bez oznaceni"): bez oznaceni se dřív jen zobrazila vyzva. Ted bez
// oznaceni pracuje na CELE scene (vsechny polozene dily), s oznacenim
// beze zmeny na oznacene sestave jako dosud.
function findAndRegisterJoints() {
  expandSelectionToGroups();
  const selected = Array.from(currentJoinSelectionUnion());
  const wholeScene = !selected.length;
  const entries = wholeScene ? placed.slice() : selected;
  if (!entries.length) {
    showJoinToast("Scéna je prázdná, není co spočítat.");
    return;
  }
  const discarded = discardSoftJointsForEntries(entries);
  if (discarded > 0) {
    rebuildOccupiedConnectors();
    refreshEndpointMarkers(); refreshDimLabels();
    refreshSummary();
  }
  const totalSelected = entries.reduce((s, e) => s + (e.jointCount || 0), 0);
  const word = totalSelected === 1 ? "spoj" : (totalSelected >= 2 && totalSelected <= 4 ? "spoje" : "spojů");
  const subject = wholeScene
    ? `Celá scéna (${entries.length} ${entries.length === 1 ? "díl" : "dílů"})`
    : `Označená sestava (${entries.length} ${entries.length === 1 ? "díl" : "dílů"})`;
  let msg = `${subject} má celkem ${totalSelected} ${word}.`;
  if (discarded > 0) {
    msg += ` Zahozeno ${discarded} nepřesných (jen dotykových) ${discarded === 1 ? "spoje" : "spojů"} bez konektoru.`;
  }
  showJoinToast(msg);
  markCountedJoints(entries);
}

document.getElementById("btnFindJoints").addEventListener("click", findAndRegisterJoints);

// Robert 2026-09-13 ("oznac v teto sestave ve sceně kazdé čelo profilu,
// ktere se pocita jako spoj"): NENI totez jako markCountedJoints vyse -
// ta kresli 1 tecku na KAZDY fyzicky dotyk z entry.licPeers, VCETNE
// profil-prislusenstvi pripoju, ktere se do jointCount/ceny NEPOCITAJI
// (viz komentar u applyFaceToFaceCandidate: "system pocita spoj pro
// prislusenstvi na profil, ale NEMA se pocitat"). Tahle funkce naopak
// oznaci PRESNE ty konce profilu, ktere realne PRISPELY do
// entry.jointCount (tedy do radku "Cena spojů" v levem panelu i do
// price_summary.joint_count pri ulozeni - viz computeAssemblyBomAndPrice).
//
// OPRAVA (Robert: "oznacilo malo skutecnych spoju, jen nektere") - puvodni
// verze cetla jen entry.hiddenEndConn/usedConn (per-entry ucetnictvi). To
// se spolehlive plni jen v attachEntryToParent - ostatni tri registracni
// cesty (applyFaceToFaceCandidate, registerJoint, Licovani/registerLicJoint)
// hiddenEndConn PRED touto opravou vubec nenastavovaly (dodatecne doplneno
// primo v nich, at je uplne i pro NOVE spoje) - ale UZ ULOZENE sestavy v DB
// maji tenhle udaj z doby pred opravou porad chybejici/necely. Proto tahle
// funkce misto ucetnictvi POCITA GEOMETRICKY, z entry.licPeers (ten JE
// vzdy uplny a persistovany pres reload pro VSECHNY 4 cesty, viz
// insertCustomShape - "lic_peers... se resi az kdyz jsou nactene VSECHNY
// entries") - spolehlive i pro stara data bez jakekoli zavislosti na tom,
// jak presne konkretni spoj kdysi vznikl.
//
// Pro kazdy profil-profil pár v licPeers (dedup, jako markCountedJoints)
// se na KAZDE strane zvlast hleda jeji vlastni nejblizsi "end" konektor
// smerem k druhemu dilu - a oznaci se JEN kdyz je opravdu blizko
// (JOINT_FACE_NEAR_MM). To prirozene resi T-spoj: pruchozi (rodicovska)
// strana nema zadny svuj konec poblíž bodu dotyku (jeji konce jsou jinde
// podel delky), takze prahem propadne a spravne se NEOZNACI - oznaci se
// jen strana, ktera se tam fyzicky koncem skutecne opira.
const JOINT_FACE_MARKER_COLOR = 0x2288ff;
const JOINT_FACE_MARKER_SIZE = 26; // mm - strana ctverecku na celo profilu
// OPRAVA (Robert 2026-09-13, overeno rucne na sestave 346 - viz
// scripts/tmp_2026-09-13_bot8_joint_verify_346.js): puvodni verze merila
// vzdalenost KONCE od DISKRETNICH KONEKTORU souseda (jeho end/end/mid/face -
// jen ~4-7 pevnych bodu) - u "mid" konektoru pruchozi nohy to je bod v JEJIM
// STREDU, ne tam, kde po jeji delce prislusenstvi realne dosedaji. U dlouhe
// nohy s prickou daleko od stredu tak vychazela vzdalenost stovky mm i pro
// SKUTECNE dotykajici se celo (73 z 74 spoju sestavy 346 se ztratilo).
// Opraveno na vzdalenost od SKUTECNE PLOCHY (Box3) souseda - presne to, co
// uz pouziva inferProfileJointConnectors (scene.html) pro KLASIFIKACI T/roh.
// Prah proto muze byt uzky (realny dotyk = ~0mm od te plochy).
const JOINT_FACE_NEAR_MM = 2;
const jointFaceMarkerGeom = new THREE.PlaneGeometry(JOINT_FACE_MARKER_SIZE, JOINT_FACE_MARKER_SIZE);
let jointFaceMarkers = [];
function clearJointFaceMarkers() {
  jointFaceMarkers.forEach(m => scene.remove(m));
  jointFaceMarkers = [];
}
// Nejblizsi vlastni "end" konektor `entry` OD SKUTECNE PLOCHY `towardEntry`
// (Box3, ne diskretni konektory) - vraci {idx, dist} nebo null (profil bez
// zadneho "end" konektoru, teoreticky nemozne, ale at nespadne).
function nearestOwnEndConn(entry, towardEntry) {
  if (!entry.connectorsLocal) return null;
  const myConns = worldConnectorsOf(entry);
  towardEntry.object3d.updateMatrixWorld(true);
  const towardBox = new THREE.Box3().setFromObject(towardEntry.object3d);
  let bestIdx = null, bestDist = Infinity;
  entry.connectorsLocal.forEach((c, idx) => {
    if (c.kind !== "end") return;
    const d = towardBox.distanceToPoint(myConns[idx].point);
    if (d < bestDist) { bestDist = d; bestIdx = idx; }
  });
  return bestIdx == null ? null : { idx: bestIdx, dist: bestDist, point: myConns[bestIdx].point, normal: myConns[bestIdx].normal };
}
function highlightJointCountedFaces(entries) {
  clearJointFaceMarkers();
  const entriesSet = new Set(entries);
  const seenPairs = new Set();
  let marked = 0;
  const oznacCelo = (c) => {
    const mat = new THREE.MeshBasicMaterial({ color: JOINT_FACE_MARKER_COLOR, transparent: true, opacity: 0.85, depthTest: false, side: THREE.DoubleSide });
    const mesh = new THREE.Mesh(jointFaceMarkerGeom, mat);
    mesh.position.copy(c.point).addScaledVector(c.normal, 1); // 1mm ven - at nekmita (z-fighting) s povrchem profilu
    mesh.quaternion.setFromUnitVectors(new THREE.Vector3(0, 0, 1), c.normal);
    mesh.renderOrder = 999;
    scene.add(mesh);
    jointFaceMarkers.push(mesh);
    marked++;
  };
  entries.forEach(entry => {
    if (!entry.licPeers) return;
    entry.licPeers.forEach(peer => {
      // Robert 2026-09-13 (91 vs 73 na sestave 346): razitka (logo_logiman_cz/
      // vypln_drazky_30) maji v katalogu vyplnene length_mm/cross_section_mm,
      // takze isProfilePart() je propusti - musi se vylucit zvlast, stejne
      // jako v autoRegisterTouchedProfileJoints/registerLicJoint (scene.html).
      if (!entry.part || !peer.part || !isProfilePart(entry.part) || !isProfilePart(peer.part)
          || isStampPart(entry) || isStampPart(peer) || isKontrolniPart(entry) || isKontrolniPart(peer)) return;
      const ia = placed.indexOf(entry), ib = placed.indexOf(peer);
      if (ia < 0 || ib < 0) return; // spoj smerujici na uz odstraneny dil
      const key = ia < ib ? ia + "_" + ib : ib + "_" + ia;
      if (seenPairs.has(key)) return;
      seenPairs.add(key);
      [[entry, peer], [peer, entry]].forEach(([e, other]) => {
        if (!entriesSet.has(e)) return; // respektuj vyber - jen oznacene dily (nebo cela scena)
        const near = nearestOwnEndConn(e, other);
        if (near && near.dist <= JOINT_FACE_NEAR_MM) oznacCelo(near);
      });
    });
  });
  return marked;
}
// Robert 2026-09-13 ("aby se tam ty čela drzeli dokud to tlacitko znovu
// nestisknu, takze to ma byt vlastne přepínač a nesmi zmizet kdyz saham
// do sceny"): puvodne se znacky mazaly na PRVNI dalsi klik do viewportu
// (stejny vzor jako "Spočítej spoje"/markCountedJoints) - zmeneno na
// cisty ON/OFF prepinac ovladany jen timhle tlacitkem, zadny jiny zasah
// do sceny (vyber, orbit kamery, tazeni jineho dilu) znacky nesmaze.
// ZAMERNE staticke, ne live: znacky se pri zapnuti spocitaji jednou
// pro danou mnozinu dilu a dal se neprepocitavaji, dokud uzivatel
// tlacitko nevypne a znovu nezapne (stejny princip jako u "Spočítej
// spoje" - kdyby geometrie mezitim zmenila, obnovi se novym stiskem).
function highlightJointFacesAction() {
  const btn = document.getElementById("btnHighlightJointFaces");
  if (btn && btn.classList.contains("active")) {
    clearJointFaceMarkers();
    btn.classList.remove("active");
    showJoinToast("📐 Čela = spoj vypnuto.");
    return;
  }
  expandSelectionToGroups();
  const selected = Array.from(currentJoinSelectionUnion());
  const wholeScene = !selected.length;
  const entries = wholeScene ? placed.slice() : selected;
  if (!entries.length) {
    showJoinToast("Scéna je prázdná, není co označit.");
    return;
  }
  const marked = highlightJointCountedFaces(entries);
  if (btn) btn.classList.add("active");
  const word = marked === 1 ? "čelo" : (marked >= 2 && marked <= 4 ? "čela" : "čel");
  const subject = wholeScene ? "V celé scéně" : "V označených dílech";
  showJoinToast(marked
    ? `${subject} označeno ${marked} ${word}, které se počítají do "Cena spojů". Vypneš opětovným kliknutím na tlačítko.`
    : `${subject} žádné čelo nepočítá do "Cena spojů".`);
}
document.getElementById("btnHighlightJointFaces").addEventListener("click", highlightJointFacesAction);

// Robert 2026-07-25: "ve scene je zakladni grid v plose x/y, berem to jako
// 0mm pro osu Z... pridejme tlacitko Uzemnit, tzn ze spodni cast objektu
// dolehne v ose z na 0mm."
//
// POZOR na oznaceni os (stejna past jako uz jednou zapsana vyse u
// axisMoveWorldDir): Robertovo "Z" tady NENI realna THREE osa Z - je to
// UI oznaceni VYSKY, ktere uz drive vedome prohodil (viz komentar
// "labely Y/Z jsou prohozene... Robert chce, aby Z ovladalo vysku").
// Scena ma "nahoru" realne THREE osu Y (camera.up = (0,1,0), GridHelper
// lezi v realne rovine X-Z pri Y=0) - podlaha je tedy realne Y=0.
// "Uzemnit" proto posouva po realne ose Y, ne po realne ose Z.
//
// Pracuje na sjednocenem vyberu (currentJoinSelectionUnion, stejny vzor
// jako Kopirovani/Najdi spoje/BoxEdit skupina) - CELY vyber se posune o
// JEDNU spolecnou hodnotu (ne kazdy dil zvlast), aby se u spojene
// sestavy (Join skupina, ram, cely vlastni tvar) zachovaly vzajemne
// pozice dilu - jinak by se rozpojena/roztrzena sestava "polozila" po
// castech na ruzne vysky.
// Robert 2026-08-08 ("k tlacitku uzemnit přidej funkci které pocatecni
// roh umisti zaroveň na strd os X,Z"): puvodne jen svisly posun (Y na
// 0), ted NAVIC vodorovny posun, aby "pocatecni" roh vyberu (nejnizsi
// X a nejnizsi Z jeho spolecneho bounding boxu) skoncil presne v
// pocatku os X,Z (0,0) - cely vyber se tak "zarovna do rohu" scenu
// stejne, jako uz drive delal jen se svislou osou. Jeden spolecny
// Box3.union() pres cely vyber (misto 3 oddelenych pruchodu) - stejny
// princip jako puvodni smycka pro minY, jen rozsireny na vsechny 3 osy.
function groundSelection() {
  expandSelectionToGroups();
  const entries = Array.from(currentJoinSelectionUnion());
  if (!entries.length) {
    showJoinToast("Nejdřív označ díl(y), které chceš uzemnit.");
    return;
  }
  const box = new THREE.Box3();
  let any = false;
  entries.forEach(entry => {
    entry.object3d.updateMatrixWorld(true);
    const b = new THREE.Box3().setFromObject(entry.object3d);
    if (!b.isEmpty()) { box.union(b); any = true; }
  });
  if (!any) return;
  const deltaX = -box.min.x;
  const deltaY = -box.min.y;
  const deltaZ = -box.min.z;
  if (Math.abs(deltaX) < 0.05 && Math.abs(deltaY) < 0.05 && Math.abs(deltaZ) < 0.05) {
    showJoinToast("Výběr už je uzemněný a jeho počáteční roh je v počátku os X,Z.");
    return;
  }
  entries.forEach(entry => {
    entry.object3d.position.x += deltaX;
    entry.object3d.position.y += deltaY;
    entry.object3d.position.z += deltaZ;
    entry.object3d.updateMatrixWorld(true);
    entry.object3d.userData.basePos = entry.object3d.position.clone();
  });
  rebuildOccupiedConnectors();
  refreshEndpointMarkers(); refreshDimLabels();
  refreshSummary();
  showJoinToast(`Uzemněno a zarovnáno na počátek os (posun X:${Math.round(deltaX)} / Y:${Math.round(deltaY)} / Z:${Math.round(deltaZ)} mm).`);
}

document.getElementById("btnGroundSelection").addEventListener("click", groundSelection);

// RECT_FRAME_TOUCH_EPS/entryEndWorldPoints pouziva i "Automaticke
// vsazeni desky" nize (detectBoardTargetBounds) - sdilena tolerance/
// pomocna funkce, i kdyz puvodne vznikly pro tlacitko "Roztahuj"
// (smazano, Robert 2026-08-22 [remove-fn]).
const RECT_FRAME_TOUCH_EPS = 0.75; // mm - stejna tolerance jako Licovani/Najdi spoje

function entryEndWorldPoints(entry) {
  const wc = worldConnectorsOf(entry);
  return [wc[0].point, wc[1].point];
}

