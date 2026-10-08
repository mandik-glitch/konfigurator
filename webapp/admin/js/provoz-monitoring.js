// ==================== PŘEHLED SYSTÉMU (pipeline VŠECH modulů) ====================
// bot9, 2026-08-26, Robert pres bot3: "chceme pipeline všeho" - primy
// vzor ze sesterskeho Toscanaccia (stejny nazev funkci/CSS trid).
// POZOR - nezamenovat s "Pipeline" vys (tab-pipeline,
// loadPipelineOverview/renderPipelineDiagram) - to je uzsi, jen
// e-mailova fronta/schvalovani (SVG diagram). Tenhle panel je SIRSI:
// zivy zdravotni stav VSECH ~30 backendovych modulu (tabulky/soubory/
// cache), ne jen e-mailovy tok - odlisny endpoint (GET /api/admin/
// system-pipeline, api/system_pipeline.py), odlisna komponenta
// (.pipe-card/.pipe-chain/.pipe-grid, ne SVG).
let pipeStatusFilter = "";
let pipeData = null;

async function loadSystemPipeline() {
  const errEl = document.getElementById("pipeErr");
  errEl.textContent = "";
  try {
    const r = await fetch("/api/admin/system-pipeline");
    if (!r.ok) throw new Error("HTTP " + r.status);
    pipeData = await r.json();
    renderPipeStatusTabs();
    renderPipeContent();
  } catch (e) {
    errEl.textContent = "Nepodařilo se načíst přehled systému: " + e.message;
  }
}

function renderPipeStatusTabs() {
  const c = pipeData.status_counts;
  const defs = [
    { key: "", label: "Vše", count: pipeData.total_modules },
    { key: "ok", label: "Funguje", count: c.ok || 0 },
    { key: "error", label: "Chyba", count: c.error || 0 },
    { key: "unknown", label: "Neověřeno", count: c.unknown || 0 },
    { key: "static", label: "Statický popis", count: c.static || 0 },
  ];
  const wrap = document.getElementById("pipeStatusTabs");
  wrap.innerHTML = defs.map(d => {
    const active = pipeStatusFilter === d.key;
    return `<button type="button" class="order-tab-btn${active ? " active" : ""}" data-key="${d.key}">${d.label}<span class="otc">(${d.count})</span></button>`;
  }).join("");
  wrap.querySelectorAll(".order-tab-btn").forEach(btn => {
    btn.onclick = () => { pipeStatusFilter = btn.dataset.key; renderPipeStatusTabs(); renderPipeContent(); };
  });
}

function pipeModuleCardHtml(m) {
  const fmt = (iso) => iso ? new Date(iso).toLocaleString("cs-CZ") : "—";
  return `
    <div class="pipe-card status-${m.status}" title="${escapeHtmlAdmin(m.key)}">
      <div class="pc-top">
        <span class="pc-label">${escapeHtmlAdmin(m.label)}</span>
        <span class="pc-dot ${m.status}" title="${m.status}"></span>
      </div>
      <div class="pc-desc">${escapeHtmlAdmin(m.description)}</div>
      ${m.metric ? `<div class="pc-metric">${escapeHtmlAdmin(m.metric)}</div>` : ""}
      ${m.last_activity ? `<div class="pc-last">poslední aktivita: ${fmt(m.last_activity)}</div>` : ""}
    </div>`;
}

function renderPipeContent() {
  const matches = (m) => !pipeStatusFilter || m.status === pipeStatusFilter;
  const chainsHtml = pipeData.pipelines.map(p => {
    if (!p.modules.some(matches)) return "";
    const cardsHtml = p.modules.map((m, i) => {
      const card = pipeModuleCardHtml(m);
      return i === 0 ? card : `<span class="pipe-arrow">→</span>${card}`;
    }).join("");
    return `<div class="pipe-group"><div class="pipe-group-label">${escapeHtmlAdmin(p.label)}</div><div class="pipe-chain">${cardsHtml}</div></div>`;
  }).join("");
  const standaloneFiltered = pipeData.standalone.filter(matches);
  const standaloneHtml = standaloneFiltered.length
    ? `<div class="pipe-group"><div class="pipe-group-label">Samostatné moduly</div><div class="pipe-grid">${standaloneFiltered.map(pipeModuleCardHtml).join("")}</div></div>`
    : "";
  document.getElementById("pipeContent").innerHTML = chainsHtml + standaloneHtml
    || `<p style="color:var(--text-faint);">Žádný modul neodpovídá filtru.</p>`;
}

// ==================== GEO PREHLED ====================
// Robert pres bot3, 2026-08-22: admin prehled geografickeho trackingu
// (viz #tab-geotracking) - ctyri tabulky napojene na jeden endpoint
// GET /api/admin/geo-tracking/overview. Country kod (ISO 3166-1
// alpha-2, napr. "CZ") se pro citelnost prevadi na cesky nazev pres
// nativni Intl.DisplayNames (zadna vlastni prekladova tabulka
// potreba) - fallback na holy kod, kdyz prohlizec API nema. Stejny
// vzor jako "Geo přehled" na /opt/toscanaccio, jen recepty ->
// produkty/kategorie.
const _geoCountryNamer = (() => {
  try { return new Intl.DisplayNames(["cs"], { type: "region" }); }
  catch (e) { return null; }
})();
function geoCountryLabel(code) {
  if (!code) return "—";
  if (_geoCountryNamer) {
    try { return `${_geoCountryNamer.of(code)} (${code})`; } catch (e) { /* neplatny/neznamy kod */ }
  }
  return code;
}

// Robert pres bot3, 2026-08-22 (dodatecne: "pouzite zarizeni" +
// "prohlizec") - device_type je "mobile"|"tablet"|"desktop"|""
// (klasifikovano serverove z User-Agent hlavicky, viz api/tracking.py
// _classify_device_type()/_classify_browser()). browser prichazi uz
// jako hotovy citelny nazev (napr. "Chrome"), zadny dalsi preklad
// netreba, jen escapovat.
const _GEO_DEVICE_LABELS = { mobile: "📱 Mobil", tablet: "📱 Tablet", desktop: "🖥️ Desktop" };
function geoDeviceLabel(deviceType) {
  return _GEO_DEVICE_LABELS[deviceType] || "—";
}
function geoBrowserLabel(browser) {
  return browser ? escapeHtmlAdmin(browser) : "—";
}

// Robert pres bot3, 2026-08-22 ("straveny cas (dwell time)") -
// dwell_seconds_total prichazi z backendu jako SUM(dwell_ms)/1000 pres
// VSECHNY navstevniky v danem radku (ne prumer na navstevnika - u
// souctu za "vic lidi" by prumer bez poctu unikatnich navstevniku
// stejne nebyl presny, soucet je aspon jednoznacny).
function geoDwellLabel(totalSeconds) {
  const s = Number(totalSeconds) || 0;
  if (s <= 0) return "—";
  const m = Math.floor(s / 60);
  const rem = Math.round(s % 60);
  return m > 0 ? `${m} min ${rem} s` : `${rem} s`;
}

// Robert pres bot3, dodatecne ("chci z toho pochopit kdo kdy a naco se
// divail") - den prichazi z backendu jako NULL v "all" pohledu
// (kumulativni tabulka nema denni granularitu, jen prvni/posledni
// navstevu za celou dobu) - "—" tam znamena "nelze urcit", ne "dnes".
function geoDenLabel(den) {
  return den ? new Date(den).toLocaleDateString("cs-CZ") : "—";
}

let geoProductCountriesAllRows = [];
let geoProductCountriesFilterQ = "";
let geoCategoryCountriesAllRows = [];
let geoCategoryCountriesFilterQ = "";
let geoTrackingRange = "all";
// Robert pres bot3, dodatecne ("casovy filtr chci i na dny") - kdyz je
// vyplnene aspon "od", ma prednost pred geoTrackingRange presetem
// (viz backend admin_geo_tracking_overview - stejna logika, date_from/
// date_to prebiji range).
let geoDateFrom = "";
let geoDateTo = "";

async function loadGeoTracking() {
  const errEl = document.getElementById("geoTrackingErr");
  errEl.textContent = "";
  let data;
  try {
    const params = new URLSearchParams({ range: geoTrackingRange });
    if (geoDateFrom) params.set("date_from", geoDateFrom);
    if (geoDateTo) params.set("date_to", geoDateTo);
    const r = await fetch(`/api/admin/geo-tracking/overview?${params.toString()}`);
    data = await r.json();
    if (!r.ok) { errEl.textContent = data.error || "Geo přehled se nepodařilo načíst."; return; }
  } catch (e) {
    errEl.textContent = "Geo přehled se nepodařilo načíst.";
    return;
  }

  const topCountries = data.top_countries || [];
  document.getElementById("geoTopCountriesEmpty").style.display = topCountries.length ? "none" : "block";
  document.getElementById("geoTopCountriesTbody").innerHTML = topCountries.map(row => `
    <tr>
      <td>${geoDenLabel(row.den)}</td>
      <td>${escapeHtmlAdmin(row.path || "—")}</td>
      <td>${geoCountryLabel(row.country)}</td>
      <td>${escapeHtmlAdmin(row.city || "—")}</td>
      <td>${geoDeviceLabel(row.device_type)}</td>
      <td>${geoBrowserLabel(row.browser)}</td>
      <td>${row.views}</td>
      <td>${geoDwellLabel(row.dwell_seconds_total)}</td>
    </tr>`).join("");

  const pageTypeTotals = data.page_type_totals || [];
  document.getElementById("geoPageTypeEmpty").style.display = pageTypeTotals.length ? "none" : "block";
  document.getElementById("geoPageTypeTbody").innerHTML = pageTypeTotals.map(row => `
    <tr><td>${escapeHtmlAdmin(row.page_type)}</td><td>${row.views}</td></tr>`).join("");

  geoProductCountriesAllRows = data.product_countries || [];
  renderGeoProductCountriesTable();
  geoCategoryCountriesAllRows = data.category_countries || [];
  renderGeoCategoryCountriesTable();
}

function renderGeoProductCountriesTable() {
  const q = geoProductCountriesFilterQ.toLowerCase();
  const rows = q
    ? geoProductCountriesAllRows.filter(r => (r.product_name || "").toLowerCase().includes(q))
    : geoProductCountriesAllRows;
  document.getElementById("geoProductCountriesEmpty").style.display = rows.length ? "none" : "block";
  document.getElementById("geoProductCountriesTbody").innerHTML = rows.map(row => `
    <tr>
      <td>${geoDenLabel(row.den)}</td>
      <td>${escapeHtmlAdmin(row.product_name)}</td>
      <td>${geoCountryLabel(row.country)}</td>
      <td>${escapeHtmlAdmin(row.city || "—")}</td>
      <td>${geoDeviceLabel(row.device_type)}</td>
      <td>${geoBrowserLabel(row.browser)}</td>
      <td>${row.views}</td>
    </tr>`).join("");
}
document.getElementById("geoProductCountriesSearchQ").addEventListener("input", (e) => {
  geoProductCountriesFilterQ = e.target.value.trim();
  renderGeoProductCountriesTable();
});

function renderGeoCategoryCountriesTable() {
  const q = geoCategoryCountriesFilterQ.toLowerCase();
  const rows = q
    ? geoCategoryCountriesAllRows.filter(r => (r.category_name || "").toLowerCase().includes(q))
    : geoCategoryCountriesAllRows;
  document.getElementById("geoCategoryCountriesEmpty").style.display = rows.length ? "none" : "block";
  document.getElementById("geoCategoryCountriesTbody").innerHTML = rows.map(row => `
    <tr>
      <td>${geoDenLabel(row.den)}</td>
      <td>${escapeHtmlAdmin(row.category_name)}</td>
      <td>${geoCountryLabel(row.country)}</td>
      <td>${escapeHtmlAdmin(row.city || "—")}</td>
      <td>${geoDeviceLabel(row.device_type)}</td>
      <td>${geoBrowserLabel(row.browser)}</td>
      <td>${row.views}</td>
    </tr>`).join("");
}
document.getElementById("geoCategoryCountriesSearchQ").addEventListener("input", (e) => {
  geoCategoryCountriesFilterQ = e.target.value.trim();
  renderGeoCategoryCountriesTable();
});
document.querySelectorAll(".geo-range-btn").forEach(btn => {
  btn.onclick = () => {
    document.querySelectorAll(".geo-range-btn").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    geoTrackingRange = btn.dataset.range;
    // Datum ma na backendu prednost pred presetem (viz
    // admin_geo_tracking_overview) - kdyby zustalo vyplnene, klik na
    // preset by tise nic nezmenil. Zrusit ho tady je citelnejsi nez
    // nechat uzivatele hadat, proc se data nezmenila.
    geoDateFrom = ""; geoDateTo = "";
    document.getElementById("geoDateFrom").value = "";
    document.getElementById("geoDateTo").value = "";
    loadGeoTracking();
  };
});
document.getElementById("geoDateApplyBtn").addEventListener("click", () => {
  const from = document.getElementById("geoDateFrom").value;
  const to = document.getElementById("geoDateTo").value;
  if (!from && !to) return;
  geoDateFrom = from;
  geoDateTo = to;
  document.querySelectorAll(".geo-range-btn").forEach(b => b.classList.remove("active"));
  loadGeoTracking();
});
document.getElementById("geoDateClearBtn").addEventListener("click", () => {
  geoDateFrom = ""; geoDateTo = "";
  document.getElementById("geoDateFrom").value = "";
  document.getElementById("geoDateTo").value = "";
  document.querySelectorAll(".geo-range-btn").forEach(b => b.classList.remove("active"));
  document.querySelector('.geo-range-btn[data-range="all"]').classList.add("active");
  geoTrackingRange = "all";
  loadGeoTracking();
});

// ==================== RENDERING (HDRI/PBR PRO NABIDKY) ====================
// Robert 2026-08-10 ("za chodu myslím toto: čerpat hdri i PBR pro 3D
// scenu v nabídce ve sdíleném disku slozka rendering, ja jen budu
// vybírat na nějaké obrazovce jaký se pouzije adresář" + "chci
// zatrzitkovat ty ktere se maji pouzivat") - zadny novy upload, jen
// vyber KTERA slozka na Sdilenem disku je prave aktivni pro HDRI a
// ktera pro PBR texturu hliniku (viz api/rendering_settings.py).
// Zaskrtavatka se chovaji jako "radio" (max 1 aktivni na sloupec).
function _renderingFlattenFolders(folders, prefix) {
  let out = [];
  (folders || []).forEach(f => {
    const label = prefix ? `${prefix} / ${f.name}` : f.name;
    out.push({ id: f.id, name: label });
    out = out.concat(_renderingFlattenFolders(f.children, label));
  });
  return out;
}

async function loadRenderingSettings() {
  const hdriListEl = document.getElementById("renderingHdriList");
  const pbrListEl = document.getElementById("renderingPbrList");
  const statusEl = document.getElementById("renderingSettingsStatus");
  hdriListEl.textContent = "Načítám…";
  pbrListEl.textContent = "Načítám…";
  try {
    const [driveRes, settingsRes] = await Promise.all([
      fetch("/api/admin/drive").then(r => r.json()),
      fetch("/api/admin/rendering-settings").then(r => r.json()),
    ]);
    const folders = _renderingFlattenFolders(driveRes.folders, "");
    const activeHdriId = settingsRes.hdri_folder ? settingsRes.hdri_folder.id : null;
    const activePbrId = settingsRes.pbr_folder ? settingsRes.pbr_folder.id : null;

    function renderColumn(el, kind, activeId, filesPreview) {
      if (!folders.length) {
        el.innerHTML = '<p class="hint">Na Sdíleném disku zatím nejsou žádné složky.</p>';
        return;
      }
      el.innerHTML = folders.map(f => `
        <label style="display:flex;align-items:center;gap:6px;padding:3px 0;">
          <input type="checkbox" class="rendering-folder-cb" data-kind="${kind}" data-id="${f.id}" ${f.id === activeId ? "checked" : ""}>
          <span>${f.name}</span>
        </label>
      `).join("")
      + (activeId && filesPreview && filesPreview.length
          ? `<div style="margin-top:6px;font-size:11.5px;color:var(--text-muted);">Nalezené soubory: ${
              filesPreview.map(x => x.role ? `${x.filename} → <b>${x.role}</b>` : `${x.filename} (role nerozpoznána, ignorováno)`).join(", ")
            }</div>`
          : "");
    }
    renderColumn(hdriListEl, "hdri", activeHdriId, (settingsRes.hdri_files || []).map(x => ({ filename: x.filename, role: null })));
    renderColumn(pbrListEl, "pbr", activePbrId, settingsRes.pbr_files || []);

    document.querySelectorAll(".rendering-folder-cb").forEach(cb => {
      cb.addEventListener("change", async () => {
        const kind = cb.dataset.kind;
        const folderId = cb.checked ? parseInt(cb.dataset.id, 10) : null;
        // "radio" chovani - odskrtnout vsechny ostatni ve stejnem sloupci
        document.querySelectorAll(`.rendering-folder-cb[data-kind="${kind}"]`).forEach(other => {
          if (other !== cb) other.checked = false;
        });
        statusEl.textContent = "Ukládám…";
        try {
          const body = {};
          body[kind + "_folder_id"] = folderId;
          const r = await fetch("/api/admin/rendering-settings", {
            method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
          });
          if (!r.ok) {
            const j = await r.json().catch(() => ({}));
            statusEl.textContent = "⚠ " + (j.error || "Uložení se nezdařilo.");
            return;
          }
          statusEl.textContent = "✓ Uloženo.";
          loadRenderingSettings(); // znovu nacist - ukaze detekovane soubory pro nove zvolenou slozku
        } catch (err) {
          statusEl.textContent = "⚠ Uložení se nezdařilo (chyba spojení): " + err.message;
        }
      });
    });
  } catch (err) {
    hdriListEl.textContent = pbrListEl.textContent = "";
    statusEl.textContent = "⚠ Načtení se nezdařilo: " + err.message;
  }
}
