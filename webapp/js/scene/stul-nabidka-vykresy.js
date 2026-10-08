// stul-nabidka-vykresy.js - VÝKRESY S KÓTAMI do online nabídky z konfigurace stolu (bot8, 2026-10-06).
//
// Robert (přes bot5): „v online nabídce z generátoru chybí 2D kótovací systém, který už máme vyřešený – používá ho nabídka ze scény“. Nabídky z konfigurace (POST /api/admin/konfigurace/nabidka)
// mají 3D + souhrn + cenu, ale ne výkresy (nárys / bokorys / půdorys s kótami). Výkresy se dělají tady, ve Scéně, STEJNOU cestou jako u nabídky ze scény (generateSceneOffer v path-traced-preview.js):
// captureOrthoWithDims(front | side | top, styl z /api/admin/dimension-style) – vzhled i rozložení kót jsou tedy shodné. Kusovník ani nová nabídka se nevytváří.
//
// Režim: scene.html?stul=<query>&nabidka_vykresy=<offer_id> (adresu otevře bot16 po vytvoření nabídky z konfigurace stolu v nové záložce, query = vyrobni_list_url jako u „Vložit do Scény“):
//   1. Scéna se načte BEZ obnovy poslední sestavy (jinak by ve výkresech byl cizí obsah) - scene.html hlídá `window.__nabidkaVykresy`,
//   2. stul-konfigurator.js vloží stůl z ?stul= a pošle událost "stul-z-adresy-vlozen" {ok},
//   3. tady se po vložení vyrobí nárys, bokorys, půdorys (PNG s kótami) + dva 3D snímky (JPEG) a pošlou na
//      POST /api/admin/konfigurace/nabidka/<offer_id>/vykresy  {views: {narys, bokorys, pudorys, view3d_a, view3d_b}}  (staff cookie, právo nabidky/vytvorit, jen nabídka z konfigurace, 24 h od vytvoření),
//   4. nahoře se ukáže „Výkresy uloženy“ a nabídka zavřít kartu; při chybě důvod a „Zkusit znovu“. Opakované nahrání výkresy VYMĚNÍ.
// Nic dalšího se neukládá (žádný zápis sestavy, žádný klíč F5); scéna zůstává v prohlížeči jen jako výchozí podklad.
//
// Rozdíly proti generateSceneOffer (záměrné):
//  - NÁRYS = čelní strana stolu (pohled "side": šířka stolu leží ve Scéně na ose Z, hloubka na X), BOKORYS = pohled na hloubku ("front"); nabídka ze scény bere pevně kameru "front", ale tam si člověk
//    sestavu otočí sám, u generátoru je orientace daná (hlídá test A7: osa šířky = Z),
//  - plátno výkresů má PEVNOU výšku (VYKRES_VYSKA_PX) a pixelRatio 1 bez ohledu na okno prohlížeče (kóty a popisky se škálují od výšky plátna; v malém okně by se popisky ořezávaly),
//  - pomocný křížek os v počátku (originAxisHelper) se na čas snímání skryje (u nabídky ze scény je ve výkresu vidět).
//
// Načítá se AŽ PO stul-konfigurator.js; používá globály scény: placed, scene, camera, controls, renderer, THREE, fetchApprovedDimensionStyle, setHelperMarkersVisible, setTechnicalDrawingMode,
// captureOrthoWithDims, setViewMode, captureRaw3d, fitCameraToScene.
(function () {
  "use strict";

  const ENDPOINT = id => "/api/admin/konfigurace/nabidka/" + encodeURIComponent(id) + "/vykresy";
  const CEKANI_NA_DILY_MS = 20000;
  const VYKRES_SIRKA_PX = 1500, VYKRES_VYSKA_PX = 1180;                  // plátno výkresů (šířku si captureOrthoWithDims odvodí z tvaru stolu)
  const SNIMEK_3D_SIRKA_PX = 1600, SNIMEK_3D_VYSKA_PX = 1000;            // plátno 3D snímků
  const KOTA_OKRAJE = [undefined, 90, 115, 140];                         // okraj pro kóty (offerKotaLayout): výchozí 70, při ořezu popisku se výkres zopakuje s větším
  const HLASKY = {
    invalid_views: "Server odmítl výkresy (chybí nebo je poškozený obrázek).",
    vykresy_expired: "Nabídka je starší než 24 hodin – výkresy už nejdou doplnit. Vytvořte novou nabídku ze stolu.",
    not_configurator_offer: "Tohle není nabídka z konfigurace stolu.",
    not_found: "Nabídka neexistuje.",
    save_failed: "Server výkresy nedokázal uložit.",
  };

  function idZAdresy() {
    try {
      const v = new URLSearchParams(location.search).get("nabidka_vykresy");
      return /^\d{1,9}$/.test(v || "") ? v : null;
    } catch (e) { return null; }
  }

  const OFFER_ID = idZAdresy();
  window.__nabidkaVykresy = OFFER_ID;                                   // scene.html: bez obnovy poslední sestavy (obsah scény = jen stůl)
  // stul-konfigurator.js maže parametr stul z adresy hned při startu (F5 ho nevloží znovu) a předtím si nechá značku
  const MA_STUL = (() => { try { return window.__stulZAdresy === true || new URLSearchParams(location.search).has("stul"); } catch (e) { return false; } })();

  const state = { banner: null, text: null, tlacitka: null, bezi: false };

  function ui() {
    if (state.banner) return state;
    const b = document.createElement("div");
    b.id = "nabidkaVykresyBanner";
    b.style.cssText = "position:fixed;top:12px;left:50%;transform:translateX(-50%);z-index:100000;max-width:min(92vw,640px);padding:12px 16px;border-radius:10px;"
      + "background:#16324f;color:#fff;font:14px/1.4 system-ui,sans-serif;box-shadow:0 6px 24px rgba(0,0,0,.35);text-align:center;";
    const t = document.createElement("div");
    t.id = "nabidkaVykresyText";
    const bt = document.createElement("div");
    bt.style.cssText = "margin-top:8px;display:flex;gap:8px;justify-content:center;";
    b.appendChild(t); b.appendChild(bt);
    (document.body || document.documentElement).appendChild(b);
    state.banner = b; state.text = t; state.tlacitka = bt;
    return state;
  }

  function stav(text, druh, tlacitka) {
    const s = ui();
    s.text.textContent = text;
    s.banner.style.background = druh === "chyba" ? "#8a1f1f" : druh === "ok" ? "#14633a" : "#16324f";
    s.tlacitka.textContent = "";
    (tlacitka || []).forEach(([popis, fn]) => {
      const el = document.createElement("button");
      el.type = "button"; el.textContent = popis;
      el.style.cssText = "padding:6px 14px;border-radius:6px;border:0;background:#fff;color:#16324f;font-weight:600;cursor:pointer;";
      el.addEventListener("click", fn);
      s.tlacitka.appendChild(el);
    });
  }

  const dalsiSnimek = () => new Promise(r => (window.requestAnimationFrame ? requestAnimationFrame(() => setTimeout(r, 0)) : setTimeout(r, 16)));

  // Počká, až jsou všechny vložené díly stolu skutečně v scéně (mesh načtený), nejdéle CEKANI_NA_DILY_MS.
  async function pockejNaDily() {
    const t0 = Date.now();
    while (Date.now() - t0 < CEKANI_NA_DILY_MS) {
      if (typeof placed !== "undefined" && placed.length && placed.every(e => e.object3d && e.object3d.children && e.object3d.children.length)) break;
      await new Promise(r => setTimeout(r, 100));
    }
    await dalsiSnimek(); await dalsiSnimek();
  }

  // captureOrthoWithDims a setViewMode berou velikost plátna z viewport.clientWidth/clientHeight (velikost okna) - po dobu snímání ji nahradíme pevnou hodnotou
  const pevnyViewport = (w, h) => {
    Object.defineProperty(viewport, "clientWidth", { configurable: true, get: () => w });
    Object.defineProperty(viewport, "clientHeight", { configurable: true, get: () => h });
  };
  const uvolniViewport = () => { delete viewport.clientWidth; delete viewport.clientHeight; };

  // Je u kraje obrázku "inkoust" (tmavé pixely v pruhu 2 px)? Model má kolem sebe vždy rezervu, takže tam může být jen oříznutý popisek / čára kóty.
  function maOrez(uri) {
    return new Promise(resolve => {
      const img = new Image();
      img.onload = () => {
        const c = document.createElement("canvas"); c.width = img.naturalWidth; c.height = img.naturalHeight;
        const x = c.getContext("2d"); x.drawImage(img, 0, 0);
        const w = c.width, h = c.height;
        const tmave = d => { for (let k = 0; k < d.length; k += 4) if (d[k + 3] > 40 && (d[k] + d[k + 1] + d[k + 2]) / 3 < 200) return true; return false; };
        resolve(tmave(x.getImageData(0, 0, w, 2).data) || tmave(x.getImageData(0, h - 2, w, 2).data) || tmave(x.getImageData(0, 0, 2, h).data) || tmave(x.getImageData(w - 2, 0, 2, h).data));
      };
      img.onerror = () => resolve(false);
      img.src = uri;
    });
  }

  // Jeden výkres; offerKotaLayout počítá okraj pro jednu dráhu kót + popisek, druhá dráha na jedné straně popisek na kraji oříznula (půdorys výchozího stolu) -> při ořezu znovu s větším okrajem.
  async function vykres(mode, dimStyle) {
    let uri = null;
    for (const layer of KOTA_OKRAJE) {
      uri = captureOrthoWithDims(mode, Object.assign({}, dimStyle, { kotaLayer: layer, kotaAvoid: true }));          // kotaAvoid: bez prekryvu a duplicit kot, volne misto nad deskou (scene.html drawDimensionOverlay)
      if (!(await maOrez(uri))) return uri;
    }
    console.warn("Výkres " + mode + ": popisek kóty zůstal u kraje oříznutý ani s největším okrajem.");
    return uri;
  }

  // Výkresy a 3D snímky - stejná volání jako v generateSceneOffer (viz tam), bez kusovníku a bez GLB.
  async function vyrob() {
    const dimStyle = await fetchApprovedDimensionStyle();
    const pixelRatio = renderer.getPixelRatio();
    const osyViditelne = typeof originAxisHelper !== "undefined" && originAxisHelper.visible;
    setHelperMarkersVisible(false);
    if (osyViditelne) setOriginAxisVisible(false);
    renderer.setPixelRatio(1);
    try {
      pevnyViewport(VYKRES_SIRKA_PX, VYKRES_VYSKA_PX);
      setTechnicalDrawingMode(true);
      const narys = await vykres("side", dimStyle);                           // čelní strana stolu (šířka na ose Z)
      const bokorys = await vykres("front", dimStyle);                        // hloubka
      const pudorys = await vykres("top", dimStyle);
      setTechnicalDrawingMode(false);
      pevnyViewport(SNIMEK_3D_SIRKA_PX, SNIMEK_3D_VYSKA_PX);
      setViewMode("3d");
      // kamera ve výchozím směru, ale na vzdálenost podle obálky stolu (jinak by stůl mohl být malý nebo oříznutý)
      const f = fitCameraToScene({ x: camera.position.x, y: camera.position.y, z: camera.position.z }, { x: controls.target.x, y: controls.target.y, z: controls.target.z }, camera.fov, 1.5);
      camera.position.set(f.pos.x, f.pos.y, f.pos.z);
      controls.target.set(f.target.x, f.target.y, f.target.z);
      camera.lookAt(controls.target);
      controls.update();
      renderer.render(scene, camera);
      const view3d_a = captureRaw3d();
      const off = camera.position.clone().sub(controls.target);                // 2. úhel: otočení kolem stejného středu jako u nabídky ze scény (0,55 pi)
      const a = Math.PI * 0.55, c = Math.cos(a), s = Math.sin(a);
      camera.position.copy(controls.target).add(new THREE.Vector3(off.x * c - off.z * s, off.y, off.x * s + off.z * c));
      camera.lookAt(controls.target);
      const view3d_b = captureRaw3d();
      return { narys, bokorys, pudorys, view3d_a, view3d_b };
    } finally {
      setTechnicalDrawingMode(false);
      uvolniViewport();
      renderer.setPixelRatio(pixelRatio);
      setViewMode("3d");                                                        // plátno i kamera zpět na přirozenou velikost okna
      if (osyViditelne) setOriginAxisVisible(true);
      setHelperMarkersVisible(true);
    }
  }

  async function odesli(views) {
    const r = await fetch(ENDPOINT(OFFER_ID), { method: "POST", headers: { "Content-Type": "application/json" }, credentials: "same-origin", body: JSON.stringify({ views }) });
    const data = await r.json().catch(() => ({}));
    return { ok: r.ok, status: r.status, data };
  }

  // opakovat = false: chyba, kterou nové snímání nespraví (stůl se nevložil / ve scéně nic není) - tlačítko by jen spustilo výkresy nad prázdnou scénou
  function chyba(text, opakovat = true) {
    stav(text, "chyba", opakovat ? [["Zkusit znovu", () => spust(true)]] : []);
  }

  async function spust(vlozenoOk) {
    if (!OFFER_ID || state.bezi) return;
    state.bezi = true;
    try {
      if (!vlozenoOk) { chyba("Stůl se do scény nepodařilo vložit, výkresy nelze vyrobit. Zavřete kartu a vytvořte nabídku znovu.", false); return; }
      stav("Připravuji výkresy nabídky…", "info");
      await pockejNaDily();
      if (typeof placed === "undefined" || !placed.length) { chyba("Ve scéně není stůl, výkresy nelze vyrobit.", false); return; }
      let views;
      try { views = await vyrob(); } catch (e) { chyba("Výkresy se nepodařilo vyrobit: " + (e && e.message || e)); return; }
      stav("Ukládám výkresy do nabídky…", "info");
      let res;
      try { res = await odesli(views); } catch (e) { chyba("Spojení se serverem selhalo, výkresy se neuložily."); return; }
      if (!res.ok) {
        const kod = res.data && res.data.error;
        chyba(HLASKY[kod] || (res.status === 401 || res.status === 403 ? "Nemáte právo vytvářet nabídky (přihlaste se jako zaměstnanec)." : ((res.data && res.data.message) || "Výkresy se neuložily (chyba " + res.status + ").")));
        return;
      }
      stav("✓ Výkresy uloženy do nabídky. Tuto kartu můžete zavřít.", "ok", [["Zavřít kartu", () => { try { window.close(); } catch (e) { /* ignoruj */ } }]]);
    } finally {
      state.bezi = false;
    }
  }

  if (OFFER_ID) {
    window.addEventListener("stul-z-adresy-vlozen", ev => { spust(!!(ev && ev.detail && ev.detail.ok)); });
    const start = () => (MA_STUL ? stav("Čekám na načtení stolu…", "info") : stav("V adrese chybí konfigurace stolu (stul=…), výkresy nelze vyrobit. Otevřete odkaz z nabídky znovu.", "chyba"));
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
    else start();
  }

  window.StulNabidkaVykresy = { offerId: OFFER_ID, spust, vyrob, odesli, pockejNaDily };
})();
