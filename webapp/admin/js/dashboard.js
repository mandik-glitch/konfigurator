// ==================== KNIHA JIZD (Robert 2026-08-05) ====================
let fleetVehicles = [];

function escapeHtmlFleet(s) {
  return String(s == null ? "" : s).replace(/[&<>"']/g, c => ({ "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;" }[c]));
}

async function loadFleetFuelEmail() {
  try {
    const r = await fetch("/api/admin/fleet/settings");
    const data = await r.json().catch(() => ({}));
    if (!r.ok) return;
    document.getElementById("fleetFuelEmailInput").value = data.fuel_receipt_email || "";
    document.getElementById("fleetFuelFolderInput").value = data.fuel_receipt_folder_path || "";
  } catch (e) {}
}

document.getElementById("btnSaveFleetFuelEmail").onclick = async () => {
  const status = document.getElementById("fleetFuelEmailStatus");
  const email = document.getElementById("fleetFuelEmailInput").value.trim();
  status.textContent = "ukládám…";
  try {
    const r = await fetch("/api/admin/fleet/settings", {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ fuel_receipt_email: email }),
    });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(data.error || ("HTTP " + r.status));
    status.textContent = "uloženo ✓";
    setTimeout(() => { status.textContent = ""; }, 2000);
  } catch (e) {
    status.textContent = "chyba: " + e.message;
  }
};

document.getElementById("btnSaveFleetFuelFolder").onclick = async () => {
  const status = document.getElementById("fleetFuelFolderStatus");
  const folderInput = document.getElementById("fleetFuelFolderInput");
  const folderPath = folderInput.value.trim();
  status.textContent = "ukládám…";
  try {
    const r = await fetch("/api/admin/fleet/settings", {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ fuel_receipt_folder_path: folderPath }),
    });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(data.error || ("HTTP " + r.status));
    status.textContent = "uloženo ✓";
    await loadFleetFuelEmail();
    setTimeout(() => { status.textContent = ""; }, 2000);
  } catch (e) {
    status.textContent = "chyba: " + e.message;
  }
};

async function loadFleetVehicles() {
  try {
    const r = await fetch("/api/admin/fleet/vehicles");
    const data = await r.json().catch(() => ({}));
    if (!r.ok) { document.getElementById("fleetVehiclesErr").textContent = data.error || "Nepodařilo se načíst vozidla."; return; }
    fleetVehicles = data.vehicles || [];
    renderFleetVehicles();
    renderFleetTripsVehicleFilter();
  } catch (e) {
    document.getElementById("fleetVehiclesErr").textContent = "Nepodařilo se načíst vozidla.";
  }
}

function renderFleetVehicles() {
  const tbody = document.getElementById("fleetVehiclesTbody");
  tbody.innerHTML = "";
  fleetVehicles.forEach((v) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td><input type="text" class="fv-name" style="width:160px" value="${escapeHtmlFleet(v.name)}"></td>
      <td><input type="text" class="fv-spz" style="width:100px" value="${escapeHtmlFleet(v.spz)}"></td>
      <td><input type="text" class="fv-vin" style="width:160px" value="${escapeHtmlFleet(v.vin || "")}"></td>
      <td><input type="checkbox" class="fv-active" ${v.active ? "checked" : ""}></td>
      <td><button class="fv-save">Uložit</button> <button class="fv-delete danger">Smazat</button></td>
    `;
    tr.querySelector(".fv-save").onclick = async () => {
      const r = await fetch(`/api/admin/fleet/vehicles/${v.id}`, {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: tr.querySelector(".fv-name").value.trim(),
          spz: tr.querySelector(".fv-spz").value.trim(),
          vin: tr.querySelector(".fv-vin").value.trim(),
          active: tr.querySelector(".fv-active").checked,
        }),
      });
      const data = await r.json().catch(() => ({}));
      document.getElementById("fleetVehiclesErr").textContent = r.ok ? "" : (data.error || "Uložení se nezdařilo.");
      loadFleetVehicles();
    };
    tr.querySelector(".fv-delete").onclick = async () => {
      if (!confirm(`Smazat vozidlo "${v.name}"?`)) return;
      const r = await fetch(`/api/admin/fleet/vehicles/${v.id}`, { method: "DELETE" });
      const data = await r.json().catch(() => ({}));
      if (!r.ok) { document.getElementById("fleetVehiclesErr").textContent = data.error || "Smazání se nezdařilo."; return; }
      if (data.deactivated) document.getElementById("fleetVehiclesErr").textContent = "Vozidlo má jízdy v historii - jen deaktivováno.";
      else document.getElementById("fleetVehiclesErr").textContent = "";
      loadFleetVehicles();
    };
    tbody.appendChild(tr);
  });
}

document.getElementById("fleetVehAdd").onclick = async () => {
  const name = document.getElementById("fleetVehName").value.trim();
  const spz = document.getElementById("fleetVehSpz").value.trim();
  const vin = document.getElementById("fleetVehVin").value.trim();
  if (!name || !spz) { document.getElementById("fleetVehiclesErr").textContent = "Vyplňte název a SPZ."; return; }
  const r = await fetch("/api/admin/fleet/vehicles", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, spz, vin }),
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) { document.getElementById("fleetVehiclesErr").textContent = data.error || "Přidání se nezdařilo."; return; }
  document.getElementById("fleetVehiclesErr").textContent = "";
  document.getElementById("fleetVehName").value = "";
  document.getElementById("fleetVehSpz").value = "";
  document.getElementById("fleetVehVin").value = "";
  loadFleetVehicles();
};

function renderFleetTripsVehicleFilter() {
  const sel = document.getElementById("fleetTripsVehicleFilter");
  const current = sel.value;
  sel.innerHTML = `<option value="">Všechna vozidla</option>` +
    fleetVehicles.map(v => `<option value="${v.id}">${escapeHtmlFleet(v.name)} (${escapeHtmlFleet(v.spz)})</option>`).join("");
  sel.value = current;
}

function fleetFormatDateTime(iso) {
  // Robert 2026-08-05: "nebudeme vubec pouzivat vteriny v knize jizd" -
  // bez { second: "2-digit" } (vychozi cs-CZ ho jinak pripoji).
  if (!iso) return "–";
  return new Date(iso).toLocaleString("cs-CZ", {
    day: "numeric", month: "numeric", year: "numeric", hour: "2-digit", minute: "2-digit",
  });
}

function fleetFormatDuration(startIso, endIso) {
  if (!startIso) return "–";
  const start = new Date(startIso);
  const end = endIso ? new Date(endIso) : new Date();
  const mins = Math.max(0, Math.round((end - start) / 60000));
  const h = Math.floor(mins / 60), m = mins % 60;
  return h ? `${h} h ${m} min` : `${m} min`;
}

async function loadFleetTrips() {
  try {
    // Robert 2026-08-05 ("bude potreba to tedy filtrovat vsechno podle
    // auta"): filtr posilame na server (?vehicle_id=), ne jen skryvani
    // radku v prohlizeci - viz api/fleet.py fleet_trips_list().
    const vehicleId = document.getElementById("fleetTripsVehicleFilter").value;
    const url = "/api/admin/fleet/trips" + (vehicleId ? `?vehicle_id=${vehicleId}` : "");
    const r = await fetch(url);
    const data = await r.json().catch(() => ({}));
    if (!r.ok) { document.getElementById("fleetTripsErr").textContent = data.error || "Nepodařilo se načíst jízdy."; return; }
    renderFleetTrips(data.trips || []);
  } catch (e) {
    document.getElementById("fleetTripsErr").textContent = "Nepodařilo se načíst jízdy.";
  }
}

function fleetStopIcon(stopType) { return stopType === "fuel" ? "⛽" : "🏁"; }

function fleetRenderStopLine(s) {
  if (s.stop_type === "fuel") {
    return s.drive_file_id
      ? `⛽ <a href="/api/admin/drive/files/${s.drive_file_id}/download">${escapeHtmlFleet(s.drive_filename || "doklad")}</a>`
      : `⛽ doklad (soubor chybí)`;
  }
  return `🏁 ${escapeHtmlFleet(s.company_name || "bez firmy")} – ${escapeHtmlFleet(s.city || "?")}`;
}

// Sdilene odstraneni jakehokoli otevreneho detailniho radku (zastavky NEBO
// GPS pozice) - drzi se pravidlo "jen jeden rozbaleny najednou v cele
// tabulce", stejne jako predtim jen pro zastavky.
function fleetRemoveDetailRows() {
  document.querySelectorAll(".fleet-stops-row, .fleet-points-row").forEach(el => el.remove());
}

async function fleetToggleTripStops(tripId, row) {
  const existing = row.nextElementSibling;
  if (existing && existing.classList.contains("fleet-stops-row")) { existing.remove(); return; }
  fleetRemoveDetailRows();
  const detailTr = document.createElement("tr");
  detailTr.className = "fleet-stops-row";
  const td = document.createElement("td");
  td.colSpan = 10;
  td.style.background = "rgba(127,127,127,.06)";
  td.textContent = "Načítám zastávky…";
  detailTr.appendChild(td);
  row.after(detailTr);
  const r = await fetch(`/api/admin/fleet/trips/${tripId}/stops`);
  const data = await r.json().catch(() => ({}));
  const stops = data.stops || [];
  td.innerHTML = stops.length
    ? stops.map(s => `<div style="padding:3px 0;">${fleetFormatDateTime(s.recorded_at)} – ${fleetRenderStopLine(s)}</div>`).join("")
    : "Bez zastávek.";
}

// Robert 2026-08-07 ("zajímá mě jestli někde v systému jsou vidět
// jednotlivé GPS pozice během cesty... udělej pro každou jízdu přídavný
// záznam a sice tabulku GPS pozic") - endpoint
// GET /api/admin/fleet/trips/<id>/points uz existoval (fleet_trip_points,
// zaznam po ujeti ~2km), ale nikde se nevolal. Ted tabulka spoji start
// (t.start_lat/lng, z jiz nactenych dat jizdy), vsechny mezilehle body
// z API, a konec (t.end_lat/lng) do jedne chronologicke tabulky.
async function fleetToggleTripPoints(trip, row) {
  const existing = row.nextElementSibling;
  if (existing && existing.classList.contains("fleet-points-row")) { existing.remove(); return; }
  fleetRemoveDetailRows();
  const detailTr = document.createElement("tr");
  detailTr.className = "fleet-points-row";
  const td = document.createElement("td");
  td.colSpan = 10;
  td.style.background = "rgba(127,127,127,.06)";
  td.textContent = "Načítám GPS pozice…";
  detailTr.appendChild(td);
  row.after(detailTr);
  const r = await fetch(`/api/admin/fleet/trips/${trip.id}/points`);
  const data = await r.json().catch(() => ({}));
  const rows = [];
  if (trip.start_lat != null && trip.start_lng != null) {
    rows.push({ recorded_at: trip.started_at, lat: trip.start_lat, lng: trip.start_lng, distance_km: 0, label: "Start" });
  }
  (data.points || []).forEach(p => rows.push({ recorded_at: p.recorded_at, lat: p.lat, lng: p.lng, distance_km: p.distance_km, label: "" }));
  if (trip.end_lat != null && trip.end_lng != null) {
    rows.push({ recorded_at: trip.ended_at, lat: trip.end_lat, lng: trip.end_lng, distance_km: trip.distance_km, label: "Konec" });
  }
  if (!rows.length) { td.textContent = "Žádné GPS pozice nezaznamenány."; return; }
  td.innerHTML = `
    <table style="width:100%; font-size:12px; border-collapse:collapse;">
      <thead><tr>
        <th style="text-align:left; padding:2px 8px;">Čas</th>
        <th style="text-align:left; padding:2px 8px;">Zeměpisná šířka</th>
        <th style="text-align:left; padding:2px 8px;">Zeměpisná délka</th>
        <th style="text-align:right; padding:2px 8px;">Km od startu</th>
        <th style="padding:2px 8px;"></th>
      </tr></thead>
      <tbody>
        ${rows.map(p => `
          <tr>
            <td style="padding:2px 8px;">${fleetFormatDateTime(p.recorded_at)}</td>
            <td style="padding:2px 8px;">${p.lat.toFixed(6)}</td>
            <td style="padding:2px 8px;">${p.lng.toFixed(6)}</td>
            <td style="padding:2px 8px; text-align:right;">${p.distance_km.toFixed(2)} km</td>
            <td style="padding:2px 8px;">${p.label ? `<b>${p.label}</b> ` : ""}<a href="https://www.openstreetmap.org/?mlat=${p.lat}&mlon=${p.lng}#map=17/${p.lat}/${p.lng}" target="_blank" rel="noopener">mapa ↗</a></td>
          </tr>
        `).join("")}
      </tbody>
    </table>
  `;
}

function renderFleetTrips(trips) {
  const tbody = document.getElementById("fleetTripsTbody");
  tbody.innerHTML = "";
  trips.forEach((t) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${t.trip_number}</td>
      <td>${escapeHtmlFleet(t.vehicle_name)} (${escapeHtmlFleet(t.vehicle_spz)})</td>
      <td>${escapeHtmlFleet(t.user_name)}</td>
      <td>${fleetFormatDateTime(t.started_at)}</td>
      <td>${fleetFormatDateTime(t.ended_at)}</td>
      <td>${fleetFormatDuration(t.started_at, t.ended_at)}</td>
      <td>${t.distance_km.toFixed(1)} km</td>
      <td>${t.odometer_km != null ? t.odometer_km + " km" : "–"}</td>
      <td>${t.status === "active" ? "🟢 probíhá" : "ukončena"}</td>
      <td><button class="fleet-stops-btn">Zastávky</button> <button class="fleet-points-btn">GPS pozice</button></td>
    `;
    tr.querySelector(".fleet-stops-btn").onclick = () => fleetToggleTripStops(t.id, tr);
    tr.querySelector(".fleet-points-btn").onclick = () => fleetToggleTripPoints(t, tr);
    tbody.appendChild(tr);
  });
}

document.getElementById("fleetTripsRefresh").onclick = loadFleetTrips;
document.getElementById("fleetTripsVehicleFilter").onchange = loadFleetTrips;

// ==================== DASHBOARD ====================
// bot10, 2026-09-11 (Robert pres bot3: "stávající tabulky... chci mít
// možnost sbalit" - misto pro novy panel Tvorba sestav nebylo v rade
// pěti hustych sloupcu). Stejny vzor jako setNavGroupCollapsed
// (crm-nabidky.js) - jen tady sbaluje CELE TELO panelu (.dash-panel-body),
// hlavicka (nazev+pocet, uz existujici *Total spany) zustava vidy videt.
// "Nesahej na obsah panelu" - zadna z loadXxx() funkci nize se nemeni,
// jen se pridava toggle tlacitko do hlavicky a schovava/ukazuje telo.
function dashPanelStorageKey(panelId) { return "dashPanelCollapsed_" + panelId; }
function setDashPanelCollapsed(panelId, collapsed) {
  const panel = document.getElementById(panelId);
  if (!panel) return;
  panel.classList.toggle("dash-panel-collapsed", collapsed);
  const btn = panel.querySelector(".dash-panel-toggle");
  if (btn) btn.textContent = collapsed ? "▸" : "▾";
  try { localStorage.setItem(dashPanelStorageKey(panelId), collapsed ? "1" : "0"); } catch (e) {}
}
function initDashPanelCollapse() {
  document.querySelectorAll(".dash-panel-toggle[data-panel]").forEach(btn => {
    const panelId = btn.dataset.panel;
    if (btn.dataset.wired) return;
    btn.dataset.wired = "1";
    btn.onclick = () => {
      const panel = document.getElementById(panelId);
      setDashPanelCollapsed(panelId, !panel.classList.contains("dash-panel-collapsed"));
    };
    let collapsed = false;
    try { collapsed = localStorage.getItem(dashPanelStorageKey(panelId)) === "1"; } catch (e) {}
    setDashPanelCollapsed(panelId, collapsed);
  });
}

async function loadDashboard() {
  initDashPanelCollapse();
  loadApprovals();
  loadQaAuditGroup("opravit");
  loadQaAuditGroup("doplnit");
  loadQaTasks();
  loadQaSystemReport();
  loadClientErrors();
  loadDeployStatus();
  if (typeof loadVyrobaSestavPrehled === "function") loadVyrobaSestavPrehled();
  if (typeof loadVandrVyrobaPrehled === "function") loadVandrVyrobaPrehled();
  if (typeof loadGpuMonitorPanel === "function") loadGpuMonitorPanel();
  try {
    const r = await fetch("/api/shop/dashboard");
    const data = await r.json();
    if (!r.ok) { document.getElementById("dashErr").textContent = data.error || "Chyba."; return; }
    renderDashCards(data);
    renderDashLowStock(data.low_stock_items || []);
    renderDashRecent(data.recent_movements || []);
  } catch (e) {
    document.getElementById("dashErr").textContent = "Nepodařilo se načíst dashboard.";
  }
}

// Robert 2026-08-09 ("na dashboardu admina mi udelej panel, kde uvidim
// vsechny tyto chyby/odchylky") - zive kontroly z api/qa_checks.py (viz
// scripts/qa_product_audit.py, ktery pouziva stejny modul pro CLI).
// Robert: "jakmile ty odchylky vyresime, z panelu zmizi" - zadny
// "vyreseno" stav se neuklada, kazde volani proste znovu spocita
// aktualni stav DB, takze opravena polozka na dalsim refreshi uz
// nevyjde.
// Robert 2026-08-10 ("napříč naším celým kódem... vymyslí nějaký
// chytrý skript který by nám toto na pozadí neustále kontroloval") -
// kontroly rozsireny za hranice produktovych dat (viz api/qa_checks.py),
// takze "id" radku uz nemusi byt vzdy shop_products.id - napr.
// category_missing_meta_description vraci id KATEGORIE,
// homepage_block_missing_image id DLAZDICE, admin_modal_missing_close
// neni cislo vubec.
//
// Robert 2026-08-10 ("u vypsaných chyb mi dávej k odkliknutí: opravit
// a doplnit" / "malé tlačítko opravit bude u každé hlášky o chybě") -
// kazdy nalez ma tlacitko. Kontroly, kde existuje jednoznacny zaznam v
// administraci (produkt/kategorie/dlazdice) otevrou primo jeho editor
// - "open" dostane id radku. "Doplnit" pro kontroly typu "chybi
// hodnota", "Opravit" pro kontroly typu "spatna/rozbita hodnota".
// Kontroly BEZ zaznamu v administraci (kodove bugy jako chybejici
// zaviraci krizek, duplicitni HTML id, mrtvy JS odkaz, rozbity fetch,
// nebo vicenasobne/cizi id jako duplicate_sku/missing_glb_file/
// orphaned_gallery_items) nemaji "open" - tlacitko "Opravit" u nich
// ulozi nalez do qa_reported_tasks (viz qaReportAuditFinding), aby
// sel videt/spravovat primo v administraci (panel "Nahlášené úkoly"
// nize). Robert 2026-08-10 ("stisknu opravit a nic... rovnou poslat
// botovi (vytvorit ukol)") - puvodne jen kopirovalo do schranky, coz
// pusobilo jako "nic se nestalo". TASKS.md (git-trackovany rucni
// backlog) zamerne NENI cilem - www-data (Flask) do nej nemuze psat.
const QA_AUDIT_ACTIONS = {
  missing_price: { label: "Doplnit", open: (id) => openStockCardModalById(parseInt(id, 10)) },
  missing_image: { label: "Doplnit", open: (id) => openStockCardModalById(parseInt(id, 10)) },
  missing_description: { label: "Doplnit", open: (id) => openStockCardModalById(parseInt(id, 10)) },
  board_missing_material_key: { label: "Doplnit", open: (id) => openStockCardModalById(parseInt(id, 10)) },
  board_price_not_per_m2: { label: "Opravit", open: (id) => openStockCardModalById(parseInt(id, 10)) },
  product_slug_not_from_name: { label: "Opravit", open: (id) => openStockCardModalById(parseInt(id, 10)) },
  profile_wrong_length_claim: { label: "Opravit", open: (id) => openStockCardModalById(parseInt(id, 10)) },
  orphaned_cfg_dily_ref: { label: "Opravit", open: (id) => openStockCardModalById(parseInt(id, 10)) },
  zero_weight_profile: { label: "Doplnit", open: (id) => openStockCardModalById(parseInt(id, 10)) },
  category_missing_meta_description: { label: "Doplnit", open: (id) => qaOpenCategoryEdit(parseInt(id, 10)) },
  homepage_block_missing_image: { label: "Doplnit", open: (id) => qaOpenHomepageBlockEdit(parseInt(id, 10)) },
};
async function qaReportAuditFinding(payload, btn) {
  const restore = () => { btn.textContent = "Opravit"; };
  try {
    const r = await fetch("/api/admin/qa-audit/tasks", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
    });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) { btn.textContent = "⚠ Chyba"; setTimeout(restore, 1500); return; }
    btn.textContent = data.already_reported ? "Už nahlášeno" : "✓ Nahlášeno";
    setTimeout(restore, 1500);
    loadQaTasks();
  } catch (e) {
    btn.textContent = "⚠ Chyba spojení";
    setTimeout(restore, 1500);
  }
}
// Kazda kontrola muze mit hodne nalezu (napr. chybejici meta popis u
// kategorii - desitky) - bez oriznuti by jeden takovy nalez pohltil
// cely panel a schoval ostatni, mensi (ale casto naléhavější) kontroly.
const QA_AUDIT_ITEM_LIMIT = 8;
// Robert 2026-08-10 ("budou 2 scripty ktere bude admin spoustet a
// zastavovat nezavisle") - jedna parametrizovana funkce pro oba
// panely (category "opravit"/"doplnit"), misto dvou skoro-identickych
// kopii. ID prvku v DOM se odvozuji z prefixu (qaBug.../qaData...).
const QA_AUDIT_GROUP_IDS = {
  opravit: { panel: "qaBugPanel", content: "qaBugContent", btn: "qaBugRefreshBtn", total: "qaBugTotal" },
  doplnit: { panel: "qaDataPanel", content: "qaDataContent", btn: "qaDataRefreshBtn", total: "qaDataTotal" },
};
async function loadQaAuditGroup(category) {
  const ids = QA_AUDIT_GROUP_IDS[category];
  const panel = document.getElementById(ids.panel);
  const content = document.getElementById(ids.content);
  const runBtn = document.getElementById(ids.btn);
  const runBtnOrigLabel = runBtn.textContent;
  runBtn.disabled = true;
  runBtn.textContent = "⏸ Kontroluji…";
  try {
    const r = await fetch(`/api/admin/qa-audit?category=${category}`);
    // Robert ("vidim jen 1 tlacitko... nevidim druhé tlačitko") - panel
    // (vc. tlacitka Spustit) se drive schoval CELY, kdyz kontrola nenasla
    // nic (count=0) - jakmile jedna skupina byla cista (napr. po oprave
    // obou bugu z "Chyby v kódu"), zmizelo i jeji tlacitko, takze uz
    // nesla znovu rucne spustit. Ted zustava panel VZDY viditelny (krome
    // 403/role bez prav, kde by tlacitko stejne nefungovalo) - schova se
    // jen obsah nalezu, misto neho kratke potvrzeni "cisto".
    if (!r.ok) { panel.style.display = "none"; return; }
    panel.style.display = "";
    const data = await r.json();
    const checks = (data.checks || []).filter(c => c.count > 0);
    document.getElementById(ids.total).textContent = data.total ? `(${data.total})` : "";
    if (!checks.length) {
      content.innerHTML = `<div style="font-size:12.5px;color:var(--success,#2e7d46);">✓ Žádné nálezy.</div>`;
      return;
    }
    // actionTargets se plni ve STEJNEM poradi, v jakem se tlacitka
    // renderuji nize - druhy pruchod (querySelectorAll) je pak jen
    // zipne dohromady podle indexu, zadne escapovani popisu do
    // data-* atributu neni potreba.
    const actionTargets = [];
    content.innerHTML = checks.map(c => {
      const action = QA_AUDIT_ACTIONS[c.key];
      const shown = c.items.slice(0, QA_AUDIT_ITEM_LIMIT);
      const hidden = c.items.length - shown.length;
      return `
      <div style="margin-bottom:10px;">
        <div style="font-weight:600;font-size:13px;margin-bottom:4px;">${escapeHtmlAdmin(c.label)} (${c.count})
          ${c.added ? `<span style="font-weight:400;font-size:11px;color:var(--text-muted);margin-left:6px;" title="Kontrola přidána do QA auditu">přidáno ${new Date(c.added).toLocaleDateString("cs-CZ")}</span>` : ""}
        </div>
        ${shown.map(it => {
          const pid = parseInt(it.id, 10);
          const openable = action && Number.isFinite(pid) && String(pid) === String(it.id);
          const btnLabel = action ? action.label : "Opravit";
          actionTargets.push(openable
            ? { open: () => action.open(it.id) }
            : { report: { check_key: c.key, finding_key: `${c.key}:${it.id}`, label: c.label, detail: it.detail } });
          return `
          <div class="qa-audit-item" style="display:flex; align-items:baseline; gap:8px; font-size:12.5px; padding:2px 0 2px 12px;">
            <div style="flex:1; min-width:0;"><strong>#${it.id}</strong> ${escapeHtmlAdmin(it.name)} — <span style="color:#9aa4b2;">${escapeHtmlAdmin(it.detail)}</span></div>
            <button type="button" class="qa-audit-action-btn" style="flex:0 0 auto; font-size:11px; padding:2px 8px;">${btnLabel}</button>
          </div>`;
        }).join("")}
        ${hidden > 0 ? `<div style="font-size:12px;color:#9aa4b2;padding:2px 0 2px 12px;">… a dalších ${hidden} (plný výpis: scripts/qa_product_audit.py --only ${c.key})</div>` : ""}
      </div>`;
    }).join("");
    panel.style.display = "";
    content.querySelectorAll(".qa-audit-action-btn").forEach((btn, i) => {
      const target = actionTargets[i];
      if (!target) return;
      btn.onclick = () => { target.open ? target.open() : qaReportAuditFinding(target.report, btn); };
    });
  } catch (e) { /* ticho - panel jen zustane, jak byl (stejny vzor jako loadApprovals) */ }
  finally {
    runBtn.disabled = false;
    runBtn.textContent = runBtnOrigLabel;
  }
}
document.getElementById("qaBugRefreshBtn").onclick = () => loadQaAuditGroup("opravit");
document.getElementById("qaDataRefreshBtn").onclick = () => loadQaAuditGroup("doplnit");

// bot5, 2026-09-02 - JS chyby z prohlizecu (webapp/js/client-errors.js),
// seskupene serverem podle fingerprint (viz api/client_errors.py) -
// stejny "panel vzdy viditelny, jen obsah se meni" vzor jako
// loadQaAuditGroup vyse.
async function loadClientErrors() {
  const panel = document.getElementById("clientErrorsPanel");
  const content = document.getElementById("clientErrorsContent");
  const runBtn = document.getElementById("clientErrorsRefreshBtn");
  runBtn.disabled = true;
  try {
    const r = await fetch("/api/admin/client-errors");
    if (!r.ok) { panel.style.display = "none"; return; }
    panel.style.display = "";
    const data = await r.json();
    document.getElementById("clientErrorsTotal").textContent = data.total ? `(${data.total})` : "";
    if (data.table_missing) {
      content.innerHTML = `<div style="font-size:12.5px;color:#9aa4b2;">Čeká na migraci sql/2026-09-02_client_errors.sql.</div>`;
      return;
    }
    if (!data.errors || !data.errors.length) {
      content.innerHTML = `<div style="font-size:12.5px;color:var(--success,#2e7d46);">✓ Žádné chyby za posledních 14 dní.</div>`;
      return;
    }
    content.innerHTML = data.errors.slice(0, 30).map(e => `
      <div style="margin-bottom:8px;padding-bottom:8px;border-bottom:1px solid var(--border-soft);font-size:12.5px;">
        <div><strong>${escapeHtmlAdmin(e.message)}</strong> <span style="color:#9aa4b2;">×${e.count}</span></div>
        <div style="color:#9aa4b2;font-size:11.5px;">${escapeHtmlAdmin(e.source || "")}${e.line ? ":" + e.line : ""} — naposledy ${new Date(e.last_seen_at).toLocaleString("cs-CZ")} — <a href="${escapeHtmlAdmin(e.url)}" target="_blank" rel="noopener">${escapeHtmlAdmin(e.url)}</a></div>
      </div>`).join("");
  } catch (e) { /* ticho - panel jen zustane, jak byl */ }
  finally {
    runBtn.disabled = false;
  }
}
document.getElementById("clientErrorsRefreshBtn").onclick = () => loadClientErrors();

// bot16, 2026-10-01 (Robert pres bot3: "uz me nebavi delat restart") - panel "Nasazeni serveru": kdy pujde
// serverovy kod (api/*.py) ven, co ceka a jak dopadlo posledni nasazeni. Jen cteni (viz api/deploy_runs.py);
// nasazeni 2x denne bez vypadku dela scripts/nasazeni.py. Selhani a varovani se ukazuji TADY (zadny e-mail,
// WORKFLOW.md pravidlo 16). Panel je skryty, dokud endpoint neodpovi (neni pravo / backend jeste neni nasazeny).
const DEPLOY_STATUS_LABEL = {
  ok: ["✓ v pořádku", "dep-ok"], varovani: ["⚠ s varováním", "dep-warn"], selhalo: ["✗ SELHALO", "dep-bad"],
  preskoceno: ["⏭ přeskočeno", "dep-warn"], nic: ["✓ nebylo co nasazovat", "dep-muted"], bezi: ["⏳ běží", "dep-warn"],
  prerusen: ["✗ přerušeno", "dep-bad"],
};
function depFmt(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("cs-CZ", { day: "numeric", month: "numeric", hour: "2-digit", minute: "2-digit" });
}
function depZa(iso) {
  const min = Math.round((new Date(iso).getTime() - Date.now()) / 60000);
  if (min < 1) return "za chvíli";
  return min >= 60 ? `za ${Math.floor(min / 60)} h ${String(min % 60).padStart(2, "0")} min` : `za ${min} min`;
}
function renderDeployStatus(d) {
  const esc = escapeHtmlAdmin;
  const p = d.posledni;
  const lab = p ? (DEPLOY_STATUS_LABEL[p.status] || [p.status, "dep-muted"]) : null;
  const sonda = (p && p.detail && p.detail.sonda) || null;
  const banners = (d.upozorneni || []).map(u => `<div class="dep-banner dep-banner-${esc(u.uroven)}">${esc(u.text)}</div>`).join("");
  const stat = (label, value, sub) =>
    `<div class="dep-stat"><div class="dep-label">${label}</div>${value}${sub ? `<div class="dep-sub">${sub}</div>` : ""}</div>`;
  const stats = [
    stat("Poslední nasazení",
      p ? `<span class="dep-stat-value ${lab[1]}">${lab[0]}</span>` : `<span class="dep-stat-value dep-muted">zatím žádné</span>`,
      p ? `${esc(depFmt(p.zacatek))} · ${p.trigger === "plan" ? "plánované" : "ruční"}` : ""),
    stat("Další termín",
      `<span class="dep-stat-value">${esc(depFmt(d.dalsi_okno))}</span>`,
      `${esc(depZa(d.dalsi_okno))} · ${d.casovac === "zapnuty" ? "časovač zapnutý" : "časovač NENÍ zapnutý"}`),
    stat("Čeká na nasazení",
      `<span class="dep-stat-value ${d.ceka_celkem ? "dep-warn" : ""}">${d.ceka_celkem}</span>`, "commitů do api/*.py"),
  ];
  if (sonda) {
    stats.push(stat("Pauza obsluhy při nasazení",
      `<span class="dep-stat-value ${sonda.selhalo ? "dep-bad" : ""}">${esc(Number(sonda.nejdelsi_pauza_s).toLocaleString("cs-CZ"))} s</span>`,
      `selhalo ${sonda.selhalo} z ${sonda.pozadavku} požadavků`));
  }
  let html = banners + `<div class="dep-stats">${stats.join("")}</div>`;
  if (d.table_missing) html += `<div class="dep-sub">Historie nasazení se začne zapisovat při prvním běhu (tabulka deploy_runs).</div>`;
  if ((d.ceka || []).length) {
    html += `<div class="dep-block"><div class="dep-label">Čeká na nasazení – půjde ven v nejbližším termínu</div>` +
      d.ceka.map(c => `<div class="dep-line"><span class="dep-time">${esc(depFmt(c.cas))}</span> <code>${esc(c.hash)}</code> ${esc(c.predmet)}</div>`).join("") + `</div>`;
  }
  if ((d.necommitnute || []).length) {
    html += `<div class="dep-block"><div class="dep-label">Necommitnuté změny v kódu serveru – blokují plánované nasazení</div>` +
      d.necommitnute.map(n => `<div class="dep-line"><code>${esc(n.soubor)}</code> <span class="dep-sub">[${esc(n.stav)}]</span></div>`).join("") + `</div>`;
  }
  if (p) {
    const kom = (p.commity || []).map(c => `<div class="dep-line"><code>${esc(c.hash)}</code> ${esc(c.predmet)}</div>`).join("");
    html += `<div class="dep-block"><div class="dep-label">Poslední běh</div><div class="dep-reason">${esc(p.duvod || "")}</div>` +
      (kom ? `<details><summary>Nasazené commity (${p.commitu})</summary>${kom}</details>` : "") + `</div>`;
  }
  if ((d.behy || []).length > 1) {
    html += `<details class="dep-block"><summary>Historie (${d.behy.length} posledních běhů)</summary><table class="dep-table">` +
      d.behy.map(b => {
        const l = DEPLOY_STATUS_LABEL[b.status] || [b.status, ""];
        return `<tr><td>${esc(depFmt(b.zacatek))}</td><td class="${l[1]}">${l[0]}</td><td>${b.trigger === "plan" ? "plán" : "ruční"}</td>` +
          `<td>${b.commitu} commitů</td><td>${b.trvani_s != null ? esc(Number(b.trvani_s).toLocaleString("cs-CZ")) + " s" : "—"}</td></tr>`;
      }).join("") + `</table></details>`;
  }
  return html;
}
async function loadDeployStatus() {
  const panel = document.getElementById("deployPanel");
  const content = document.getElementById("deployContent");
  const btn = document.getElementById("deployRefreshBtn");
  if (!panel || !content) return;
  if (btn) btn.disabled = true;
  try {
    const r = await fetch("/api/admin/deploy-runs");
    if (!r.ok) { panel.style.display = "none"; return; }
    const d = await r.json();
    panel.style.display = "";
    const bad = (d.upozorneni || []).some(u => u.uroven === "chyba");
    document.getElementById("deployTotal").textContent = d.ceka_celkem ? `(${d.ceka_celkem} čeká)` : "";
    panel.style.borderColor = bad ? "var(--error, #c23b3b)" : "";
    content.innerHTML = renderDeployStatus(d);
  } catch (e) { /* ticho - panel jen zustane, jak byl */ }
  finally { if (btn) btn.disabled = false; }
}
{
  const deployRefreshBtn = document.getElementById("deployRefreshBtn");
  if (deployRefreshBtn) deployRefreshBtn.onclick = () => loadDeployStatus();
}

// Robert 2026-08-10 ("oznacit jako VYSOKA PRIORITA pro dalsi session")
// - seznam nalezu ulozenych pres tlacitko "Opravit" (api/qa_audit.py
// /api/admin/qa-audit/tasks). Na rozdil od qaBugPanel/qaDataPanel se
// NEPOCITA zive - jde o rucne oznacene "resit hned" polozky, ktere
// zustanou, dokud je nekdo neoznaci jako hotove.
async function loadQaTasks() {
  const panel = document.getElementById("qaTasksPanel");
  const content = document.getElementById("qaTasksContent");
  try {
    const r = await fetch("/api/admin/qa-audit/tasks");
    if (!r.ok) { panel.style.display = "none"; return; }
    const data = await r.json();
    const tasks = data.tasks || [];
    if (!tasks.length) { panel.style.display = "none"; content.innerHTML = ""; return; }
    document.getElementById("qaTasksTotal").textContent = `(${tasks.length})`;
    content.innerHTML = tasks.map(t => `
      <div style="display:flex; align-items:baseline; gap:8px; font-size:12.5px; padding:3px 0;">
        <div style="flex:1; min-width:0;">
          ${t.priority ? '<span style="color:var(--warn,#b58a3a);font-weight:600;">🔴 PRIORITA</span> ' : ""}
          <strong>${escapeHtmlAdmin(t.label)}</strong> — <span style="color:#9aa4b2;">${escapeHtmlAdmin(t.detail)}</span>
        </div>
        <button type="button" class="qa-task-done-btn" data-id="${t.id}" style="flex:0 0 auto; font-size:11px; padding:2px 8px;">Hotovo</button>
      </div>`).join("");
    panel.style.display = "";
    content.querySelectorAll(".qa-task-done-btn").forEach(btn => {
      btn.onclick = async () => {
        btn.disabled = true;
        try {
          await fetch(`/api/admin/qa-audit/tasks/${btn.dataset.id}/resolve`, { method: "POST" });
          loadQaTasks();
        } catch (e) { btn.disabled = false; }
      };
    });
  } catch (e) { /* ticho - panel jen zustane, jak byl */ }
}
document.getElementById("qaTasksRefreshBtn").onclick = loadQaTasks;

// ---- QA běhy (systém) - snapshot z scripts/qa/run_all.sh, viz
// api/qa_audit.py::admin_qa_report_latest. Jiny zdroj dat nez
// loadQaAuditGroup() vyse (ta bezi zive nad DB pri kazdem nacteni,
// tohle je hotovy report z casovace - systemd/HTTP/TLS/disk/logy/
// bezpecnost/SEO nejde "zive" spocitat pri kazdem otevreni Dashboardu). ----
const QA_SEVERITY_COLOR = { critical: "#c0392b", warning: "#b58a3a", info: "#9aa4b2", ok: "#2e7d46", warn: "#b58a3a", fail: "#c0392b" };
async function loadQaSystemReport() {
  const panel = document.getElementById("qaSystemPanel");
  const content = document.getElementById("qaSystemContent");
  const statusEl = document.getElementById("qaSystemStatus");
  try {
    const r = await fetch("/api/admin/qa-report/latest");
    if (r.status === 404) {
      panel.style.display = "";
      statusEl.textContent = "";
      content.innerHTML = '<div style="font-size:12.5px;color:#9aa4b2;">Zatím žádný běh (čeká na scripts/qa/run_all.sh nebo denní časovač 04:30).</div>';
      return;
    }
    if (!r.ok) { panel.style.display = "none"; return; }
    const data = await r.json();
    panel.style.display = "";
    statusEl.innerHTML = `<span style="color:${QA_SEVERITY_COLOR[data.overall_status] || '#9aa4b2'};">${(data.overall_status || "").toUpperCase()}</span> · ${data.generated_at ? new Date(data.generated_at).toLocaleString("cs-CZ") : ""}`;

    const suitesHtml = (data.suites || []).map(s => `
      <div style="display:flex; justify-content:space-between; font-size:12px; padding:2px 0;">
        <span>${escapeHtmlAdmin(s.suite)}</span>
        <span style="color:${QA_SEVERITY_COLOR[s.status] || '#9aa4b2'};">${escapeHtmlAdmin(s.status)} (${s.finding_count})</span>
      </div>`).join("") || '<div style="font-size:12px;color:#9aa4b2;">Žádné suity.</div>';

    const diff = data.diff || {};
    const diffHtml = (diff.new_count || diff.resolved_count)
      ? `<div style="font-size:12px;margin:6px 0;color:#9aa4b2;">Δ oproti minulému běhu: +${diff.new_count || 0} nových, −${diff.resolved_count || 0} vyřešených</div>`
      : "";

    const top = (data.findings || []).slice(0, 20);
    const topHtml = top.length ? top.map(f => `
      <div style="font-size:12.5px; padding:4px 0; border-top:1px solid var(--border-soft);">
        <strong style="color:${QA_SEVERITY_COLOR[f.severity] || '#9aa4b2'};">[${escapeHtmlAdmin(f.severity)}]</strong>
        ${escapeHtmlAdmin(f.code)} <span style="color:#9aa4b2;">(${escapeHtmlAdmin(f.suite || "")})</span> — ${escapeHtmlAdmin(f.title)}
        ${f.where ? `<div style="color:#9aa4b2;">${escapeHtmlAdmin(f.where)}</div>` : ""}
      </div>`).join("") : '<div style="font-size:12.5px;color:var(--success,#2e7d46);">✓ Žádné nálezy.</div>';

    content.innerHTML = `<div style="margin-bottom:8px;">${suitesHtml}</div>${diffHtml}${topHtml}`;
  } catch (e) { /* ticho - panel jen zustane, jak byl (stejny vzor jako ostatni QA panely) */ }
}
document.getElementById("qaSystemRefreshBtn").onclick = loadQaSystemReport;

// ---- Ke schvaleni (Robert 2026-08: nove doklady/nabidky/objednavky/PO
// se musi IHNED objevit na dashboardu role, ktera je schvaluje) ----
// Sekce prijdou uz predfiltrovane podle prav prihlasene role (backend
// approvals.py, has_permission). Panel se obnovuje kazdych 30s, dokud
// je uzivatel na zalozce Dashboard - "ihned" tedy znamena do pul minuty
// i bez reloadu stranky.
let approvalsTimer = null;

// Robert 2026-08-22 (screenshot Dashboardu): "ve schvalovacich oknech
// potrebujeme prolinkovat jednotlive polozky, ne jen nadpis sekce" -
// nazev konkretni polozky je odkaz, ktery otevre PRIMO ten doklad/
// objednavku/nabidku, ne jen prepne zalozku.
//
// Zrcadli zavedeny vzor z jinych mist adminu (mailbox-systemove-
// emaily.js:369, objednavky-doklady.js:654, crm-nabidky.js:447):
// kliknout na .tab-btn a HNED potom zavolat openXDetail(id). Zadny
// location.hash - hash v adminu umi jen zalozku, ne konkretni polozku
// (viz restoreTabFromHash v admin.html). Cekat na nacteni tabulky
// zalozky netreba, vsechny opener funkce si data dotahnou samy podle id.
//
// Vsechny moduly jsou klasicke <script> bez type="module" (admin.html
// ~4934-4967) a dashboard.js je nactene AZ ZA objednavky-doklady.js i
// crm-nabidky.js, takze jsou jejich top-level funkce tady dostupne.
const APPROVAL_ITEM_OPENERS = {
  orders:             { tab: "orders",            open: (it) => openOrderDetail(it.id) },
  purchase_orders:    { tab: "purchaseorders",    open: (it) => openPODetail(it.id) },
  quotes:             { tab: "quotes",            open: (it) => openQuoteDetail(it.id) },
  incoming_documents: { tab: "incomingdocuments", open: (it) => openIncomingDocDetail(it.id) },
  // Doklady jako jedine nemaji vlastni detail modal - otevirame rovnou
  // PDF nahled, stejne jako to dela tlacitko v zalozce Doklady.
  documents:          { tab: "documents",         open: (it) => openPdfViewer(`/api/admin/documents/${it.id}/pdf`) },
  // Sestava k objednani nema detail radku -> skladova karta produktu,
  // proto potrebuje krome id i product_id (dodava api/approvals.py).
  reorder:            { tab: "reorder",           open: (it) => openStockCardModalById(it.product_id), needs: "product_id" },
};

// Vrati konfiguraci otevirani, nebo null (= polozka zustane cistym
// textem). Radsi necuklikatelny text nez mrtvy odkaz: sekce, kterou
// backend prida bez zdejsiho mapovani, ani polozka bez potrebneho id
// nesmi vyrobit odkaz, ktery po kliknuti nic neudela.
function approvalItemOpener(sectionKey, it) {
  const cfg = APPROVAL_ITEM_OPENERS[sectionKey];
  if (!cfg) return null;
  if (cfg.needs && !it[cfg.needs]) return null;
  return cfg;
}

async function loadApprovals() {
  try {
    const r = await fetch("/api/admin/approvals");
    if (!r.ok) return; // napr. role bez admin prav - panel proste zustane skryty
    const data = await r.json();
    const panel = document.getElementById("approvalsPanel");
    const content = document.getElementById("approvalsContent");
    // Object.entries (ne .values) - klic sekce urcuje, cim se polozka
    // otevira (APPROVAL_ITEM_OPENERS vyse).
    const sections = Object.entries(data.sections || {});
    const nonEmpty = sections.filter(([, s]) => s.items.length);
    if (!nonEmpty.length) { panel.style.display = "none"; content.innerHTML = ""; return; }
    document.getElementById("approvalsTotal").textContent = `(${data.total})`;
    content.innerHTML = nonEmpty.map(([key, s]) => `
      <div style="margin-bottom:10px;">
        <div style="font-weight:600;font-size:13px;margin-bottom:4px;">
          <a href="#" class="appr-tab-link" data-tab-target="${s.tab}" data-subsection="${s.subsection || ""}">${escapeHtmlAdmin(s.label)} (${s.items.length})</a>
        </div>
        ${s.items.map(it => {
          const titleHtml = approvalItemOpener(key, it)
            ? `<a href="#" class="appr-item-link" data-section="${key}" data-item-id="${it.id}">${escapeHtmlAdmin(it.title)}</a>`
            : `<span>${escapeHtmlAdmin(it.title)}</span>`;
          return `
          <div style="font-size:12.5px;padding:2px 0 2px 12px;display:flex;gap:10px;align-items:center;">
            ${titleHtml}
            ${s.approve_url ? `<button class="appr-approve-btn" style="font-size:11px;padding:2px 8px;" data-url="${s.approve_url.replace("{id}", it.id)}">Schválit</button>` : ""}
          </div>`;
        }).join("")}
      </div>`).join("");
    panel.style.display = "";
    content.querySelectorAll(".appr-tab-link").forEach(a => {
      a.onclick = (e) => {
        e.preventDefault();
        const btn = document.querySelector(`.tab-btn[data-tab="${a.dataset.tabTarget}"]`);
        if (btn) btn.click();
      };
    });
    content.querySelectorAll(".appr-item-link").forEach(a => {
      a.onclick = (e) => {
        e.preventDefault();
        const key = a.dataset.section;
        const section = (data.sections || {})[key];
        const it = (section && section.items || []).find(x => String(x.id) === a.dataset.itemId);
        if (!it) return;
        const cfg = approvalItemOpener(key, it);
        if (!cfg) return;
        // Role bez teto zalozky tlacitko nema - detail se presto otevre
        // (modaly/PDF nahled jsou na zalozce nezavisle), proto zadny
        // return, jen preskoc prepnuti.
        const btn = document.querySelector(`.tab-btn[data-tab="${cfg.tab}"]`);
        if (btn) btn.click();
        try {
          cfg.open(it);
        } catch (err) {
          // napr. kdyby se prislusny modul nenacetl - radsi hlaska v
          // konzoli nez tiche nic, panel sam zustane funkcni
          console.error("Ke schválení: detail se nepodařilo otevřít", key, it.id, err);
        }
      };
    });
    content.querySelectorAll(".appr-approve-btn").forEach(b => {
      b.onclick = async () => {
        b.disabled = true;
        const r2 = await fetch(b.dataset.url, { method: "POST" });
        if (!r2.ok) { const d2 = await r2.json().catch(() => ({})); alert(d2.error || "Schválení se nezdařilo."); }
        loadApprovals();
      };
    });
  } catch (e) { /* ticho - panel jen zustane, jak je */ }
}
if (!approvalsTimer) {
  approvalsTimer = setInterval(() => {
    const dashVisible = document.getElementById("tab-dashboard").classList.contains("active");
    if (dashVisible && !document.hidden) loadApprovals();
  }, 30000);
}

// Interni tymovy chat (Robert 2026-08-08: "na dashboard pridej chatovaci
// okno pro vsechny prihlasene v systemu") - jedna sdilena mistnost,
// stejny "sig" skip-render + "stick to bottom jen kdyz uz tam byl" vzor
// jako supportRenderModalLog (Podpora chat), viz komentar tam.
let internalChatSig = null;
let internalChatTimer = null;

function escapeInternalChat(s) {
  return String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function renderInternalChatLog(messages) {
  const log = document.getElementById("internalChatLog");
  if (!log) return;
  const sig = messages.map(m => m.id).join(",");
  if (sig === internalChatSig) return;
  const stickToBottom = internalChatSig === null || (log.scrollHeight - log.scrollTop - log.clientHeight) < 40;
  internalChatSig = sig;
  // Robert 2026-08-08: "kazda role nech ma svoji barvu textu v chatu at
  // se to hned pozna kdo pise" - role-X trida (viz CSS vyse) obarvi jen
  // jmeno odesilatele, ne cely text zpravy (lepsi citelnost delsich zprav).
  log.innerHTML = messages.length
    ? messages.map(m => {
        const roleClass = m.sender_role ? `role-${m.sender_role}` : "";
        return `<div class="ic-msg ${roleClass}"><span class="ic-msg-sender">${escapeInternalChat(m.sender_name)}</span><span class="ic-msg-meta">${supportFmtTime(m.created_at)}</span><br>${escapeInternalChat(m.body)}</div>`;
      }).join("")
    : `<div class="ic-empty">Zatím žádné zprávy - napište první.</div>`;
  if (stickToBottom) log.scrollTop = log.scrollHeight;
}

async function loadInternalChat() {
  try {
    const r = await fetch("/api/admin/internal-chat/messages");
    if (!r.ok) return;
    const data = await r.json();
    renderInternalChatLog(data.messages || []);
  } catch (e) { /* ticho - dalsi poll to zkusi znovu */ }
}

async function sendInternalChatMessage() {
  const input = document.getElementById("internalChatInput");
  const errEl = document.getElementById("internalChatErr");
  const body = input.value.trim();
  if (!body) return;
  errEl.textContent = "";
  const btn = document.getElementById("internalChatSendBtn");
  btn.disabled = true;
  try {
    const r = await fetch("/api/admin/internal-chat/messages", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ body }),
    });
    const data = await r.json();
    if (!r.ok) { errEl.textContent = data.error || "Odeslání se nezdařilo."; return; }
    input.value = "";
    input.style.height = "";
    await loadInternalChat();
  } catch (e) {
    errEl.textContent = "Chyba spojení.";
  } finally {
    btn.disabled = false;
  }
}

document.getElementById("internalChatSendBtn").onclick = sendInternalChatMessage;
document.getElementById("internalChatInput").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendInternalChatMessage();
  }
});

if (!internalChatTimer) {
  internalChatTimer = setInterval(() => {
    const dashVisible = document.getElementById("tab-dashboard").classList.contains("active");
    if (dashVisible && !document.hidden) loadInternalChat();
  }, 4000);
}

function renderDashCards(data) {
  const cards = [
    { label: "Aktivní produkty", value: data.active_products },
    { label: "Archivované produkty", value: data.archived_products },
    { label: "Hodnota skladu", value: `${data.stock_value_czk.toLocaleString("cs-CZ")} Kč` },
    { label: "Pod minimem", value: data.low_stock_count, warn: data.low_stock_count > 0 },
    { label: "Kategorií", value: data.category_count },
  ];
  document.getElementById("dashCards").innerHTML = cards.map(c => `
    <div class="dash-card${c.warn ? " warn" : ""}">
      <div class="dc-label">${c.label}</div>
      <div class="dc-value">${c.value}</div>
    </div>
  `).join("");
}

function renderDashLowStock(items) {
  const tbody = document.getElementById("dashLowStockTbody");
  if (!items.length) {
    tbody.innerHTML = '<tr><td colspan="4" style="color:#666;">Žádné položky pod minimem.</td></tr>';
    return;
  }
  tbody.innerHTML = items.map(p => `
    <tr data-product-id="${p.id}" style="cursor:pointer;">
      <td>${escapeHtmlAdmin(p.sku)}</td>
      <td>${escapeHtmlAdmin(p.name)}</td>
      <td class="stock-badge under-min">${p.stock_qty} ${escapeHtmlAdmin(p.unit)}</td>
      <td>${p.min_stock}</td>
    </tr>
  `).join("");
  tbody.querySelectorAll("tr[data-product-id]").forEach(tr => {
    tr.onclick = () => openStockCardModalById(parseInt(tr.dataset.productId, 10));
  });
}

function renderDashRecent(movements) {
  const tbody = document.getElementById("dashRecentTbody");
  if (!movements.length) {
    tbody.innerHTML = '<tr><td colspan="5" style="color:#666;">Zatím žádné pohyby.</td></tr>';
    return;
  }
  tbody.innerHTML = movements.map(m => {
    const date = new Date(m.created_at).toLocaleString("cs-CZ");
    const typeLabel = m.movement_type === "receipt"
      ? '<span class="sc-mv-receipt">+ Příjem</span>'
      : '<span class="sc-mv-issue">− Výdej</span>';
    const who = m.user_name || m.user_email || "";
    return `<tr data-product-id="${m.product_id ?? ""}" style="cursor:pointer;">
      <td>${date}</td>
      <td>${escapeHtmlAdmin(m.product_name)} (${escapeHtmlAdmin(m.product_sku)})</td>
      <td>${typeLabel}</td>
      <td>${m.qty}</td>
      <td>${escapeHtmlAdmin(who)}</td>
    </tr>`;
  }).join("");
  tbody.querySelectorAll("tr[data-product-id]").forEach(tr => {
    const pid = tr.dataset.productId;
    if (!pid) return;
    tr.onclick = () => openStockCardModalById(parseInt(pid, 10));
  });
}

// ==================== DODAVATELE ====================
let suppliersCache = [];
let editingSupplierId = null;

// Stránkování (task #78/87)
const suppliersPagerState = { page: 1, page_size: 50 };
let supplierShowArchived = false;

async function loadSuppliers() {
  const q = document.getElementById("supplierSearchQ").value.trim();
  const params = new URLSearchParams({
    page: suppliersPagerState.page, page_size: suppliersPagerState.page_size,
  });
  if (q) params.set("q", q);
  if (supplierShowArchived) params.set("archived", "1");
  try {
    const r = await fetch(`/api/admin/suppliers?${params.toString()}`);
    const data = await r.json();
    suppliersCache = data.suppliers || [];
    renderSuppliers();
    populateNewPOSupplierSelect();
    renderPager("suppliersPager", data, suppliersPagerState, loadSuppliers);
  } catch (e) {
    document.getElementById("suppliersErr").textContent = "Nepodařilo se načíst dodavatele.";
  }
}

function renderSuppliers() {
  const tbody = document.getElementById("suppliersTbody");
  if (!suppliersCache.length) {
    tbody.innerHTML = '<tr><td colspan="8" style="color:#666;">Žádní dodavatelé.</td></tr>';
    return;
  }
  tbody.innerHTML = suppliersCache.map(s => `
    <tr class="supplier-row" data-id="${s.id}" style="cursor:pointer;${s.active ? "" : "opacity:.55;"}">
      <td><input type="checkbox" class="supplier-chk" data-id="${s.id}" ${supplierSelectedIds.has(s.id) ? "checked" : ""}></td>
      <td>${escapeHtmlAdmin(s.name)}</td>
      <td>${escapeHtmlAdmin(s.ico || "")}</td>
      <td>${escapeHtmlAdmin(s.contact_name || "")}</td>
      <td>${escapeHtmlAdmin(s.email || "")}</td>
      <td>${escapeHtmlAdmin(s.phone || "")}</td>
      <td>${s.active ? "ano" : "ne"}</td>
      <td></td>
    </tr>
  `).join("");
  tbody.querySelectorAll(".supplier-row").forEach(tr => {
    tr.onclick = (e) => {
      if (e.target.closest("input")) return;
      openSupplierModal(parseInt(tr.dataset.id, 10));
    };
  });
  tbody.querySelectorAll(".supplier-chk").forEach(chk => {
    chk.onchange = () => {
      const id = parseInt(chk.dataset.id, 10);
      if (chk.checked) supplierSelectedIds.add(id); else supplierSelectedIds.delete(id);
      updateSupplierBulkToolbar();
    };
  });
}

let supplierSelectedIds = new Set();
function updateSupplierBulkToolbar() {
  const bar = document.getElementById("supplierBulkToolbar");
  const count = supplierSelectedIds.size;
  bar.classList.toggle("active", count > 0);
  document.getElementById("supplierBulkCount").textContent = `${count} vybráno`;
}
document.getElementById("supplierSelectAll").onchange = (e) => {
  if (e.target.checked) suppliersCache.forEach(s => supplierSelectedIds.add(s.id));
  else supplierSelectedIds.clear();
  renderSuppliers();
  updateSupplierBulkToolbar();
};
async function supplierBulkSetActive(active) {
  if (!supplierSelectedIds.size) return;
  await fetch("/api/admin/suppliers/bulk-activate", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ids: [...supplierSelectedIds], active }),
  });
  loadSuppliers();
}
document.getElementById("supplierBulkActivate").onclick = () => supplierBulkSetActive(true);
document.getElementById("supplierBulkDeactivate").onclick = () => supplierBulkSetActive(false);
document.getElementById("supplierBulkDelete").onclick = async () => {
  if (!supplierSelectedIds.size) return;
  if (!confirm(`Opravdu trvale smazat ${supplierSelectedIds.size} dodavatelů? Smažou se i VŠECHNY jejich nákupní ` +
               `objednávky (vč. vrácení skladu za přijaté zboží) a e-maily. Produkty navázané na smazané ` +
               `dodavatele jen ztratí odkaz na kartu, zůstanou zachované. Akci nelze vrátit zpět.`)) return;
  const r = await fetch("/api/admin/suppliers/bulk-delete", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ids: [...supplierSelectedIds] }),
  });
  const data = await r.json().catch(() => ({}));
  supplierSelectedIds.clear();
  if (!r.ok) { document.getElementById("suppliersErr").textContent = data.error || "Mazání se nezdařilo."; return; }
  if (data.stock_failed && data.stock_failed.length) {
    alert(`Pozor: ${data.stock_failed.length} skladových pohybů se nepodařilo vrátit ` +
          `(šlo by do záporu skladu) - zkontrolujte skladovou kartu.`);
  }
  loadSuppliers();
};

document.getElementById("supplierSearchApply").onclick = () => { suppliersPagerState.page = 1; loadSuppliers(); };
document.getElementById("supplierSearchReset").onclick = () => {
  document.getElementById("supplierSearchQ").value = "";
  suppliersPagerState.page = 1;
  loadSuppliers();
};
document.getElementById("supplierShowArchivedBtn").onclick = () => {
  supplierShowArchived = !supplierShowArchived;
  const btn = document.getElementById("supplierShowArchivedBtn");
  btn.textContent = supplierShowArchived ? "Skrýt archivované" : "Zobrazit archivované";
  btn.style.background = supplierShowArchived ? "#3a5a7a" : "none";
  btn.style.color = supplierShowArchived ? "#fff" : "#c7ccd4";
  suppliersPagerState.page = 1;
  loadSuppliers();
};

document.getElementById("btnAddSupplier").onclick = async () => {
  const errEl = document.getElementById("suppliersErr");
  errEl.textContent = "";
  const name = document.getElementById("newSupplierName").value.trim();
  if (!name) { errEl.textContent = "Chybí název dodavatele."; return; }
  const body = {
    name,
    ico: document.getElementById("newSupplierIco").value.trim(),
    dic: document.getElementById("newSupplierDic").value.trim(),
    contact_name: document.getElementById("newSupplierContact").value.trim(),
    email: document.getElementById("newSupplierEmail").value.trim(),
    phone: document.getElementById("newSupplierPhone").value.trim(),
  };
  const r = await fetch("/api/admin/suppliers", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) { errEl.textContent = data.error || "Chyba."; return; }
  ["newSupplierName", "newSupplierIco", "newSupplierDic", "newSupplierContact", "newSupplierEmail", "newSupplierPhone"]
    .forEach(id => { document.getElementById(id).value = ""; });
  loadSuppliers();
};

function openSupplierModal(id) {
  editingSupplierId = id;
  const s = suppliersCache.find(x => x.id === id);
  if (!s) return;
  document.getElementById("supplierModalErr").textContent = "";
  document.getElementById("editSupplierName").value = s.name || "";
  document.getElementById("editSupplierIco").value = s.ico || "";
  document.getElementById("editSupplierDic").value = s.dic || "";
  document.getElementById("editSupplierAddress").value = s.address || "";
  document.getElementById("editSupplierContact").value = s.contact_name || "";
  document.getElementById("editSupplierEmail").value = s.email || "";
  document.getElementById("editSupplierPhone").value = s.phone || "";
  document.getElementById("editSupplierActive").checked = !!s.active;
  document.getElementById("supplierModal").classList.add("open");
}

document.getElementById("supplierModalCancel").onclick = () => {
  document.getElementById("supplierModal").classList.remove("open");
};

document.getElementById("supplierModalSave").onclick = async () => {
  if (!editingSupplierId) return;
  const errEl = document.getElementById("supplierModalErr");
  errEl.textContent = "";
  const body = {
    name: document.getElementById("editSupplierName").value.trim(),
    ico: document.getElementById("editSupplierIco").value.trim(),
    dic: document.getElementById("editSupplierDic").value.trim(),
    address: document.getElementById("editSupplierAddress").value.trim(),
    contact_name: document.getElementById("editSupplierContact").value.trim(),
    email: document.getElementById("editSupplierEmail").value.trim(),
    phone: document.getElementById("editSupplierPhone").value.trim(),
    active: document.getElementById("editSupplierActive").checked,
  };
  const r = await fetch(`/api/admin/suppliers/${editingSupplierId}`, {
    method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) { errEl.textContent = data.error || "Chyba."; return; }
  document.getElementById("supplierModal").classList.remove("open");
  loadSuppliers();
};

document.getElementById("supplierModalDelete").onclick = async () => {
  if (!editingSupplierId) return;
  const s = suppliersCache.find(x => x.id === editingSupplierId);
  if (!confirm(`Opravdu smazat dodavatele „${s ? s.name : ""}“? Smažou se i VŠECHNY jeho nákupní objednávky ` +
               `(vč. vrácení skladu za přijaté zboží) a e-maily. Produkty navázané na dodavatele jen ztratí ` +
               `odkaz na kartu, zůstanou zachované.`)) return;
  const r = await fetch(`/api/admin/suppliers/${editingSupplierId}`, { method: "DELETE" });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) { document.getElementById("supplierModalErr").textContent = data.error || "Chyba."; return; }
  if (data.stock_failed && data.stock_failed.length) {
    alert(`Pozor: ${data.stock_failed.length} skladových pohybů se nepodařilo vrátit ` +
          `(šlo by do záporu skladu) - zkontrolujte skladovou kartu.`);
  }
  document.getElementById("supplierModal").classList.remove("open");
  loadSuppliers();
};

// ==================== NAKUPNI OBJEDNAVKY ====================
const PO_STATUS_LABELS = {
  navrh: "Návrh", odeslano: "Odesláno dodavateli", castecne_prijato: "Částečně přijato",
  prijato: "Přijato", zruseno: "Zrušeno",
};
const PO_ALLOWED_TRANSITIONS = {
  navrh: ["odeslano", "zruseno"],
  odeslano: ["zruseno"],
  castecne_prijato: ["zruseno"],
  prijato: [],
  zruseno: [],
};
// page/page_size v poFilter - stejny objekt jako ostatni filtry (task #78/87)
let poFilter = { status: "", q: "", page: 1, page_size: 50 };
let posCache = [];
let currentPOId = null;

async function loadPOs() {
  const params = new URLSearchParams({ page: poFilter.page, page_size: poFilter.page_size });
  if (poFilter.status) params.set("status", poFilter.status);
  if (poFilter.q) params.set("q", poFilter.q);
  try {
    const r = await fetch(`/api/admin/purchase-orders?${params.toString()}`);
    const data = await r.json();
    if (!r.ok) { document.getElementById("poErr").textContent = data.error || "Chyba."; return; }
    posCache = data.purchase_orders || [];
    renderPOStatusTabs(data.counts || {});
    renderPOsTable(posCache);
    renderPager("poPager", data, poFilter, loadPOs);
  } catch (e) {
    document.getElementById("poErr").textContent = "Nepodařilo se načíst nákupní objednávky.";
  }
}

function renderPOStatusTabs(counts) {
  const defs = [{ key: "", label: "Všechny", count: counts.all ?? 0 }]
    .concat(Object.keys(PO_STATUS_LABELS).map(k => ({ key: k, label: PO_STATUS_LABELS[k], count: counts[k] ?? 0 })));
  const wrap = document.getElementById("poStatusTabs");
  wrap.innerHTML = defs.map(d => {
    const active = poFilter.status === d.key;
    return `<button type="button" class="order-tab-btn${active ? " active" : ""}" data-key="${d.key}">${escapeHtmlAdmin(d.label)}<span class="otc">(${d.count})</span></button>`;
  }).join("");
  wrap.querySelectorAll(".order-tab-btn").forEach(btn => {
    btn.onclick = () => { poFilter.status = btn.dataset.key; poFilter.page = 1; loadPOs(); };
  });
}

function renderPOsTable(pos) {
  const tbody = document.getElementById("poTbody");
  if (!pos.length) {
    tbody.innerHTML = '<tr><td colspan="6" style="color:#666;">Žádné nákupní objednávky.</td></tr>';
    return;
  }
  tbody.innerHTML = pos.map(po => {
    const date = new Date(po.created_at).toLocaleString("cs-CZ");
    return `<tr class="po-row" data-id="${po.id}" style="cursor:pointer;">
      <td><input type="checkbox" class="po-chk" data-id="${po.id}" ${poSelectedIds.has(po.id) ? "checked" : ""}></td>
      <td>${escapeHtmlAdmin(po.po_number)}</td>
      <td>${escapeHtmlAdmin(po.supplier_name)}</td>
      <td><span class="po-status-pill ${po.status}">${escapeHtmlAdmin(po.status_label)}</span></td>
      <td>${po.total_czk != null ? po.total_czk.toLocaleString("cs-CZ") + " Kč" : ""}</td>
      <td>${date}</td>
    </tr>`;
  }).join("");
  tbody.querySelectorAll(".po-row").forEach(tr => {
    tr.onclick = (e) => {
      if (e.target.closest("input")) return;
      openPODetail(parseInt(tr.dataset.id, 10));
    };
  });
  tbody.querySelectorAll(".po-chk").forEach(chk => {
    chk.onchange = () => {
      const id = parseInt(chk.dataset.id, 10);
      if (chk.checked) poSelectedIds.add(id); else poSelectedIds.delete(id);
      updatePoBulkToolbar();
    };
  });
}

let poSelectedIds = new Set();
function updatePoBulkToolbar() {
  const bar = document.getElementById("poBulkToolbar");
  const count = poSelectedIds.size;
  bar.classList.toggle("active", count > 0);
  document.getElementById("poBulkCount").textContent = `${count} vybráno`;
}
document.getElementById("poSelectAll").onchange = (e) => {
  if (e.target.checked) posCache.forEach(po => poSelectedIds.add(po.id));
  else poSelectedIds.clear();
  renderPOsTable(posCache);
  updatePoBulkToolbar();
};
document.getElementById("poBulkApplyStatus").onclick = async () => {
  if (!poSelectedIds.size) return;
  const status = document.getElementById("poBulkStatus").value;
  if (!status) return;
  const r = await fetch("/api/admin/purchase-orders/bulk-status", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ids: [...poSelectedIds], status }),
  });
  const data = await r.json().catch(() => ({}));
  poSelectedIds.clear();
  if (data.failed && data.failed.length) {
    alert(`Nastaveno: ${data.updated}. Nešlo změnit: ${data.failed.length} (neplatný přechod stavu).`);
  }
  loadPOs();
};

document.getElementById("poBulkDelete").onclick = async () => {
  if (!poSelectedIds.size) return;
  if (!confirm(`Opravdu smazat ${poSelectedIds.size} nákupních objednávek? U objednávek s již přijatým zbožím ` +
               `se vrátí stav skladu a smažou navázané skladové pohyby. Akci nelze vrátit zpět.`)) return;
  const r = await fetch("/api/admin/purchase-orders/bulk-delete", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ids: [...poSelectedIds] }),
  });
  const data = await r.json().catch(() => ({}));
  poSelectedIds.clear();
  if ((data.failed && data.failed.length) || (data.stock_failed && data.stock_failed.length)) {
    let msg = `Smazáno: ${data.deleted}.`;
    if (data.failed && data.failed.length) {
      msg += ` Nešlo smazat: ${data.failed.length}\n` + data.failed.map(f => f.error).join("\n");
    }
    if (data.stock_failed && data.stock_failed.length) {
      msg += `\nPozor: ${data.stock_failed.length} skladových pohybů se nepodařilo vrátit ` +
             `(šlo by do záporu skladu) - zkontrolujte skladovou kartu.`;
    }
    alert(msg);
  }
  loadPOs();
};

document.getElementById("poSearchApply").onclick = () => {
  poFilter.q = document.getElementById("poSearchQ").value.trim();
  poFilter.page = 1;
  loadPOs();
};
document.getElementById("poSearchReset").onclick = () => {
  document.getElementById("poSearchQ").value = "";
  poFilter.q = "";
  poFilter.page = 1;
  loadPOs();
};

async function openPODetail(id) {
  currentPOId = id;
  document.getElementById("poModalErr").textContent = "";
  try {
    const r = await fetch(`/api/admin/purchase-orders/${id}`);
    const data = await r.json();
    if (!r.ok) { alert(data.error || "Chyba při načítání."); return; }
    renderPOModal(data.purchase_order);
    document.getElementById("poModal").classList.add("open");
  } catch (e) {
    alert("Nepodařilo se načíst detail nákupní objednávky.");
  }
}

function renderPOModal(po) {
  document.getElementById("poModalTitle").textContent = `Nákupní objednávka ${po.po_number}`;
  const created = new Date(po.created_at).toLocaleString("cs-CZ");
  document.getElementById("poModalMeta").textContent = `Vytvořeno: ${created} · Stav: ${po.status_label}`;
  document.getElementById("poModalExportCsv").href = `/api/admin/purchase-orders/${po.id}/export-csv`;

  document.getElementById("poModalSupplier").innerHTML = [
    `<div><b>${escapeHtmlAdmin(po.supplier_name)}</b></div>`,
    po.supplier_ico ? `<div>IČO: ${escapeHtmlAdmin(po.supplier_ico)}</div>` : "",
    po.supplier_contact_name ? `<div>${escapeHtmlAdmin(po.supplier_contact_name)}</div>` : "",
    po.supplier_email ? `<div>${escapeHtmlAdmin(po.supplier_email)}</div>` : "",
    po.supplier_phone ? `<div>${escapeHtmlAdmin(po.supplier_phone)}</div>` : "",
  ].join("");

  // Nahled presne odpovida textu, ktery se skutecne posle dodavateli
  // (viz _po_email_body() v api/purchase_orders.py - stejna sablona,
  // jen renderovana klientsky z uz nactenych dat, bez extra API volani).
  const previewLines = [
    "Dobrý den,", "",
    `zasíláme objednávku ${po.po_number}.`, "",
    "Objednáváme:",
  ];
  (po.items || []).forEach(it => {
    const price = it.unit_price_czk != null ? ` à ${it.unit_price_czk.toLocaleString("cs-CZ")} Kč` : "";
    previewLines.push(`  - ${it.product_name}: ${it.qty_ordered} ks${price}`);
  });
  previewLines.push("", `Celkem: ${(po.total_czk || 0).toLocaleString("cs-CZ")} Kč`, "");
  if (po.note) previewLines.push(po.note, "");
  previewLines.push("Děkujeme za potvrzení a sdělení termínu dodání.", "", "S pozdravem", "LOGiMAN");
  document.getElementById("poModalPreview").textContent = previewLines.join("\n");

  const canReceive = po.status === "odeslano" || po.status === "castecne_prijato";
  document.getElementById("poModalItems").innerHTML = (po.items || []).map(it => {
    const remaining = it.qty_ordered - it.qty_received;
    return `<tr>
      <td>${escapeHtmlAdmin(it.product_name)} (${escapeHtmlAdmin(it.sku || "")})</td>
      <td>${it.qty_ordered}</td>
      <td>${it.qty_received}</td>
      <td>${it.unit_price_czk != null ? it.unit_price_czk.toLocaleString("cs-CZ") + " Kč" : ""}</td>
      <td>${it.line_total_czk != null ? it.line_total_czk.toLocaleString("cs-CZ") + " Kč" : ""}</td>
      <td>${canReceive && remaining > 0
          ? `<input type="number" class="po-receive-qty" data-item-id="${it.id}" data-max="${remaining}" min="0" max="${remaining}" placeholder="0-${remaining}" style="width:70px;">`
          : (remaining <= 0 ? "hotovo" : "—")}</td>
      <td><button class="po-item-cam-btn" data-item-id="${it.id}" data-item-name="${escapeHtmlAdmin(it.product_name)}" title="Fotky k položce">📷</button></td>
    </tr>`;
  }).join("");
  document.querySelectorAll(".po-item-cam-btn").forEach(btn => {
    btn.onclick = () => {
      openAttachmentModal("po_item", parseInt(btn.dataset.itemId, 10), "Fotky – položka " + btn.dataset.itemName);
    };
  });
  document.getElementById("poReceiveSubmit").style.display = canReceive ? "" : "none";

  document.getElementById("poModalHistory").innerHTML = (po.history || []).map(h => {
    const date = new Date(h.changed_at).toLocaleString("cs-CZ");
    return `<tr>
      <td>${date}</td>
      <td>${escapeHtmlAdmin(h.status_label)}</td>
      <td>${escapeHtmlAdmin(h.changed_by_name || "Automat")}</td>
      <td>${escapeHtmlAdmin(h.note || "")}</td>
    </tr>`;
  }).join("");

  const statusSelect = document.getElementById("poEditStatus");
  const allowed = PO_ALLOWED_TRANSITIONS[po.status] || [];
  statusSelect.innerHTML = [`<option value="">— beze změny (${escapeHtmlAdmin(po.status_label)}) —</option>`]
    .concat(allowed.map(s => `<option value="${s}">${escapeHtmlAdmin(PO_STATUS_LABELS[s])}</option>`)).join("");
  statusSelect.disabled = allowed.length === 0;
  document.getElementById("poEditAdminNote").value = po.admin_note || "";
  document.getElementById("poEditHistoryNote").value = "";
}

document.getElementById("poModalCancel").onclick = () => {
  document.getElementById("poModal").classList.remove("open");
};

document.getElementById("poReceiveSubmit").onclick = async () => {
  if (!currentPOId) return;
  const errEl = document.getElementById("poModalErr");
  errEl.textContent = "";
  const items = [];
  document.querySelectorAll(".po-receive-qty").forEach(inp => {
    const qty = parseInt(inp.value, 10);
    if (qty > 0) items.push({ item_id: parseInt(inp.dataset.itemId, 10), qty });
  });
  if (!items.length) { errEl.textContent = "Zadej množství alespoň u jedné položky."; return; }
  const r = await fetch(`/api/admin/purchase-orders/${currentPOId}/receive`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ items }),
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) { errEl.textContent = data.error || "Chyba při příjmu zboží."; return; }
  openPODetail(currentPOId);
  loadPOs();
};

document.getElementById("poModalSave").onclick = async () => {
  if (!currentPOId) return;
  const errEl = document.getElementById("poModalErr");
  errEl.textContent = "";
  const newStatus = document.getElementById("poEditStatus").value;
  const body = { admin_note: document.getElementById("poEditAdminNote").value };
  if (newStatus) {
    body.status = newStatus;
    body.history_note = document.getElementById("poEditHistoryNote").value.trim();
  }
  const r = await fetch(`/api/admin/purchase-orders/${currentPOId}`, {
    method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) { errEl.textContent = data.error || "Chyba."; return; }
  document.getElementById("poModal").classList.remove("open");
  loadPOs();
  // Robert 2026-08 ("nakupni objednavka, jak/kdy se skutecne odesle
  // dodavateli? kde se to uvidi?"): prechod navrh->odeslano vola e-mail
  // na pozadi (viz send_po_to_supplier v purchase_orders.py), ale
  // vysledek (odeslano/selhalo/preskoceno-bez-emailu) se drive nikde
  // nezobrazoval - admin se to jinak dozvedel jen v zalozce E-maily.
  // Ted rovnou alert s vysledkem.
  if (newStatus === "odeslano") {
    if (data.email_status === "sent") alert("Objednávka odeslána dodavateli e-mailem.");
    else if (data.email_status === "skipped") alert("Stav změněn na „Odesláno“, ale e-mail se NEODESLAL: " + (data.email_error || "dodavatel nemá vyplněný e-mail.") + " Odešli objednávku dodavateli ručně.");
    else if (data.email_status === "failed") alert("Stav změněn na „Odesláno“, ale odeslání e-mailu SELHALO: " + (data.email_error || "neznámá chyba") + ". Zkontroluj to v záložce E-maily.");
  }
};

// ==================== NOVA NAKUPNI OBJEDNAVKA (+ propojeni se Sestavou k objednani) ====================
let newPOItems = [];
let newPOSourceReorderIds = [];

function populateNewPOSupplierSelect() {
  const sel = document.getElementById("newPOSupplier");
  sel.innerHTML = '<option value="">— zadám ručně níže —</option>' +
    suppliersCache.filter(s => s.active).map(s => `<option value="${s.id}">${escapeHtmlAdmin(s.name)}</option>`).join("");
}

// bot6, 2026-08-01: filtr nabidnutych produktu podle vybraneho dodavatele
// - filtruje jen LOKALNI vykres, nemeni sdileny stockMoveProductsCache
// (ten pouziva i zalozka Skladove pohyby). Bez vybraneho dodavatele
// (rucni zadani nazvu) se nabidnou vsechny produkty jako drive.
// bot5, 2026-08-01 (Robert: "vyhledávání těch položek musí mít nápovědu
// v tom textovém poli") - doplneno fulltextove hledani podle nazvu/SKU
// nad vyberem (bez dodavatele byl seznam vsech produktu neprohledatelny,
// jen posouvatelny 6radkovy vyber).
// bot5, 2026-09-28 (Robert primo: "chci mit moznost nakupni objednavku
// zadat pres eshop", potvrzeno AskUserQuestion) - PREPSANO z <select>
// na obrazkovou mrizku (kartova, jako katalog eshopu) - stejna data
// (stockMoveProductsCache = /api/shop/products?all=1, uz obsahuje
// image_url). Bez dodavatele/hledani NErendrujeme cely katalog naraz
// (stovky obrazku) - vyzada nejdriv dodavatele nebo hledany vyraz,
// stejne jako by realny eshop nezobrazil cely sklad na jednu stranku.
// Vysledek se navic tvrde oreze na PO_GRID_LIMIT s hlaskou o zbytku
// (zadne tiche oriznuti).
const PO_GRID_LIMIT = 60;
function renderNewPOProductOptions() {
  const grid = document.getElementById("newPOProductGrid");
  const supplierIdVal = document.getElementById("newPOSupplier").value;
  const supplierId = supplierIdVal ? parseInt(supplierIdVal, 10) : null;
  const q = document.getElementById("newPOProductSearch").value.trim().toLowerCase();
  // bot5, 2026-09-28 (Robert primo, screenshot: "tady nic není" - modal
  // bez filtru byl schvalne prazdny s napovedou, aby se nerenderoval
  // cely katalog naraz. Napoveda ale pusobila jako "nefunguje to" -
  // radeji rovnou ukazat prvnich PO_GRID_LIMIT produktu (stejne
  // orezani jako driv), at je hned videt, ze mrizka zije.
  let list = supplierId
    ? (stockMoveProductsCache || []).filter(p => p.supplier_id === supplierId)
    : (stockMoveProductsCache || []);
  if (q) {
    list = list.filter(p =>
      (p.name || "").toLowerCase().includes(q) || (p.sku || "").toLowerCase().includes(q));
  }
  if (!list.length) {
    grid.innerHTML = '<div class="po-product-grid-empty">Žádný produkt neodpovídá hledání.</div>';
    return;
  }
  const truncated = list.length > PO_GRID_LIMIT;
  const shown = list.slice(0, PO_GRID_LIMIT);
  // title se nastavuje jako DOM vlastnost nize (ne inline atribut v
  // retezci) - escapeHtmlAdmin escapuje jen &<> (bezpecne pro textovy
  // uzel), ne uvozovky, takze nazev/SKU s " by uvnitr title="..."
  // vylomil z atributu ven (bezpecnostni nalez pri psani, bot5).
  grid.innerHTML = shown.map(p => `
    <div class="po-product-card" data-id="${p.id}">
      <div class="po-product-card-img">${p.image_url ? `<img src="${escapeHtmlAdmin(p.image_url)}" loading="lazy" alt="">` : `<span class="po-product-card-img-ph">📦</span>`}</div>
      <div class="po-product-card-name">${escapeHtmlAdmin(p.name)}</div>
      <div class="po-product-card-sku">${escapeHtmlAdmin(p.sku || "")}${p.is_profile_material ? ' <span class="po-product-card-note">3000mm/ks</span>' : ""}</div>
      <div class="po-product-card-price">${p.price_czk_placeholder != null ? fmtBankCzk(p.price_czk_placeholder) + " Kč" : "—"}</div>
    </div>`).join("") + (truncated ? `<div class="po-product-grid-truncated">Zobrazeno prvních ${PO_GRID_LIMIT} z ${list.length} - zpřesni hledáním.</div>` : "");
  grid.querySelectorAll(".po-product-card").forEach(card => {
    const p = shown.find(x => x.id === parseInt(card.dataset.id, 10));
    card.title = p ? `${p.name}${p.sku ? " (" + p.sku + ")" : ""} – klikem přidáš do objednávky` : "";
    card.onclick = () => addSingleProductToNewPO(parseInt(card.dataset.id, 10));
  });
}

// wireProductSuggest() vycleneno do admin/js/objednavky-doklady.js (bot5, 2026-09-03, PLAN_ROZDELENI_FRONTENDU.md, schvaleno bot3 - sdileny helper, tenhle soubor se nacte pred timhle hlavnim <script>)

const renderNewPOProductSuggestions = wireProductSuggest(
  "newPOProductSearch", "newPOProductSuggestions",
  (p) => {
    const supplierIdVal = document.getElementById("newPOSupplier").value;
    const supplierId = supplierIdVal ? parseInt(supplierIdVal, 10) : null;
    return supplierId ? p.supplier_id === supplierId : true;
  },
  (productId) => { addSingleProductToNewPO(productId); renderNewPOProductOptions(); },
);
document.getElementById("newPOProductSearch").addEventListener("input", renderNewPOProductOptions);

// Naseptavac dodavatelu (Robert 2026-08-01: "při hledání dodavatele
// nefunguje nápověda") - stejny vzor jako wireProductSuggest vyse, jen
// nad suppliersCache (name+ico) misto stockMoveProductsCache. Pouziva ho
// jak vyber dodavatele v Nove nakupni objednavce (nahle prohledavatelne
// misto rolovani <select> se vsemi dodavateli), tak "Hledat" box u
// samotneho seznamu Dodavatelu.
function wireSupplierSuggest(searchInputId, boxId, onPick) {
  const input = document.getElementById(searchInputId);
  const box = document.getElementById(boxId);
  function render() {
    const q = input.value.trim().toLowerCase();
    if (!q) { box.classList.remove("open"); box.innerHTML = ""; return; }
    const list = (suppliersCache || [])
      .filter(s => (s.name || "").toLowerCase().includes(q) || (s.ico || "").toLowerCase().includes(q))
      .slice(0, 15);
    box.innerHTML = list.length
      ? list.map(s => `
          <div class="ps-row" data-id="${s.id}">
            ${escapeHtmlAdmin(s.name)}${s.ico ? ` <span class="ps-sku">(IČO ${escapeHtmlAdmin(s.ico)})</span>` : ""}
          </div>`).join("")
      : '<div class="ps-empty">Žádný dodavatel neodpovídá hledání.</div>';
    box.querySelectorAll(".ps-row").forEach(row => {
      row.onclick = () => {
        onPick(parseInt(row.dataset.id, 10));
        box.classList.remove("open");
        box.innerHTML = "";
      };
    });
    box.classList.add("open");
  }
  input.addEventListener("input", render);
  input.addEventListener("focus", () => { if (input.value.trim()) render(); });
  input.addEventListener("blur", () => setTimeout(() => box.classList.remove("open"), 150));
  return render;
}

wireSupplierSuggest("newPOSupplierSearch", "newPOSupplierSuggestions", (supplierId) => {
  const s = suppliersCache.find(x => x.id === supplierId);
  document.getElementById("newPOSupplier").value = String(supplierId);
  document.getElementById("newPOSupplierSearch").value = s ? s.name : "";
  document.getElementById("newPOSupplier").dispatchEvent(new Event("change"));
});

wireSupplierSuggest("supplierSearchQ", "supplierSearchSuggestions", (supplierId) => {
  const s = suppliersCache.find(x => x.id === supplierId);
  document.getElementById("supplierSearchQ").value = s ? s.name : "";
  suppliersPagerState.page = 1;
  loadSuppliers();
});

function addSingleProductToNewPO(productId) {
  const product = (stockMoveProductsCache || []).find(p => p.id === productId);
  if (!product) return;
  const qty = parseInt(document.getElementById("newPOQty").value, 10) || 1;
  const manualPrice = parseFloat(document.getElementById("newPOUnitPrice").value);
  const defaultPrice = product.price_czk_placeholder != null ? product.price_czk_placeholder : 0;
  const unitPrice = !isNaN(manualPrice) ? manualPrice : defaultPrice;
  // bot5, 2026-09-28: opakovany klik na STEJNOU kartu v mrizce (rychle
  // "naklikavani" mnozstvi, jako v eshopu) uz nezaklada dalsi radek se
  // stejnym product_id - pricte se Ks k jiz existujicimu radku (jen
  // kdyz ma i stejnou cenu/ks - jinak by se ceny promichaly do jednoho
  // souctu bez rozliseni, radeji zustane samostatny radek).
  const existing = newPOItems.find(it => it.product_id === productId && it.unit_price_czk === unitPrice);
  if (existing) {
    existing.qty += qty > 0 ? qty : 1;
  } else {
    newPOItems.push({
      product_id: productId,
      name: product.name,
      sku: product.sku,
      qty: qty > 0 ? qty : 1,
      unit_price_czk: unitPrice,
    });
  }
  // Rucne zadana cena je jen pro TENHLE jeden klik/produkt - po pridani
  // se maze, aby nezustala omylem "viset" a nepoužila se na dalsi
  // kliknuty produkt s jinou skutecnou cenou (bez zadani se pri
  // opakovanem kliku na stejnou kartu porad pouzije stejna
  // defaultPrice, takze se radky spravne slucuji).
  document.getElementById("newPOUnitPrice").value = "";
  renderNewPOItems();
}

async function openNewPOModal() {
  document.getElementById("newPOErr").textContent = "";
  document.getElementById("newPOSupplier").value = "";
  document.getElementById("newPOSupplierName").value = "";
  document.getElementById("newPOSupplierSearch").value = "";
  document.getElementById("newPOSupplierSuggestions").classList.remove("open");
  document.getElementById("newPOSupplierSuggestions").innerHTML = "";
  document.getElementById("newPOProductSearch").value = "";
  document.getElementById("newPOProductSuggestions").classList.remove("open");
  document.getElementById("newPOProductSuggestions").innerHTML = "";
  document.getElementById("newPOQty").value = "1";
  document.getElementById("newPOUnitPrice").value = "";
  document.getElementById("newPONote").value = "";
  populateNewPOSupplierSelect();
  document.getElementById("newPOProductGrid").innerHTML = '<div class="po-product-grid-hint">Načítám katalog…</div>';
  document.getElementById("newPOModal").classList.add("open");
  // bot5, 2026-09-28: stockMoveProductsCache muze byt jeste prazdna,
  // kdyz admin otevre "Novou nakupni objednavku" driv, nez kdy vubec
  // navstivil zalozku "Skladove pohyby" (ta ho drive jako jediná
  // nacitala) - mrizka by pak byla trvale prazdna bez zjevneho duvodu.
  // Nacte se tu vzdy znovu (idempotentni, at jsou i ceny/obrazky cerstve).
  await loadStockMoveProductOptions();
  renderNewPOProductOptions();
}

document.getElementById("newPOSupplier").onchange = () => {
  renderNewPOProductOptions();
  renderNewPOProductSuggestions();
};

document.getElementById("btnNewPO").onclick = () => {
  newPOItems = [];
  newPOSourceReorderIds = [];
  openNewPOModal();
  renderNewPOItems();
};

document.getElementById("newPOCancel").onclick = () => {
  document.getElementById("newPOModal").classList.remove("open");
};

// newPOAddItem/newPOProductSelect (bot6, 2026-08-01) odstraneny bot5,
// 2026-09-28 - nahrazeny katalogovou mrizkou (#newPOProductGrid, viz
// renderNewPOProductOptions vyse), kde klik primo na kartu pridava,
// stejnym vzorem jako uz existujici klik-na-napovedu v naseptavaci.

function renderNewPOItems() {
  const tbody = document.getElementById("newPOItemsTbody");
  tbody.innerHTML = newPOItems.map((it, i) => `
    <tr>
      <td>${escapeHtmlAdmin(it.name)} ${it.sku ? "(" + escapeHtmlAdmin(it.sku) + ")" : ""}</td>
      <td><input type="number" class="po-new-item-qty" data-idx="${i}" value="${it.qty}" min="1" style="width:70px;"></td>
      <td><input type="number" class="po-new-item-price" data-idx="${i}" value="${it.unit_price_czk}" min="0" step="0.01" style="width:90px;"></td>
      <td><button type="button" class="po-new-item-remove" data-idx="${i}" style="background:none;border:1px solid #3a3f4a;color:#c7ccd4;">×</button></td>
    </tr>
  `).join("");
  tbody.querySelectorAll(".po-new-item-qty").forEach(inp => {
    inp.onchange = () => { newPOItems[parseInt(inp.dataset.idx, 10)].qty = parseInt(inp.value, 10) || 1; };
  });
  tbody.querySelectorAll(".po-new-item-price").forEach(inp => {
    inp.onchange = () => { newPOItems[parseInt(inp.dataset.idx, 10)].unit_price_czk = parseFloat(inp.value) || 0; };
  });
  tbody.querySelectorAll(".po-new-item-remove").forEach(btn => {
    btn.onclick = () => { newPOItems.splice(parseInt(btn.dataset.idx, 10), 1); renderNewPOItems(); };
  });
}

document.getElementById("newPOSubmit").onclick = async () => {
  const errEl = document.getElementById("newPOErr");
  errEl.textContent = "";
  if (!newPOItems.length) { errEl.textContent = "Přidej alespoň jednu položku."; return; }
  const supplierIdVal = document.getElementById("newPOSupplier").value;
  const supplierName = document.getElementById("newPOSupplierName").value.trim();
  if (!supplierIdVal && !supplierName) { errEl.textContent = "Vyber dodavatele nebo zadej název ručně."; return; }
  for (const it of newPOItems) {
    if (!it.qty || it.qty <= 0) { errEl.textContent = "Množství musí být kladné u všech položek."; return; }
    if (it.unit_price_czk == null || it.unit_price_czk < 0 || isNaN(it.unit_price_czk)) {
      errEl.textContent = "Zadej cenu za kus (může být 0) u všech položek."; return;
    }
  }
  const body = {
    supplier_id: supplierIdVal ? parseInt(supplierIdVal, 10) : undefined,
    supplier_name: supplierName || undefined,
    note: document.getElementById("newPONote").value.trim(),
    items: newPOItems.map(it => ({ product_id: it.product_id, qty: it.qty, unit_price_czk: it.unit_price_czk })),
  };
  const btn = document.getElementById("newPOSubmit");
  btn.disabled = true;
  btn.textContent = "Vytvářím…";
  try {
    const r = await fetch("/api/admin/purchase-orders", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) { errEl.textContent = data.error || "Chyba."; return; }

    // pokud PO vznikla z vybranych polozek Sestavy k objednani, ty polozky
    // ted zmizi ze seznamu (staly se soucasti PO) - Robert: "teprve poté se
    // z toho stává nákupní objednávka"
    if (newPOSourceReorderIds.length) {
      await Promise.all(newPOSourceReorderIds.map(id =>
        fetch(`/api/shop/reorder-items/${id}`, { method: "DELETE" }).catch(() => {})
      ));
      newPOSourceReorderIds = [];
      loadReorderItems();
    }

    document.getElementById("newPOModal").classList.remove("open");
    loadPOs();
    alert(`Nákupní objednávka ${data.po_number} vytvořena (stav: Návrh).`);
  } catch (e) {
    errEl.textContent = "Nepodařilo se vytvořit nákupní objednávku (chyba spojení).";
  } finally {
    btn.disabled = false;
    btn.textContent = "Vytvořit objednávku";
  }
};

// most: Sestava k objednani ("vybrano") -> Nova nakupni objednavka
document.getElementById("reorderBulkToPO").onclick = () => {
  const checked = Array.from(document.querySelectorAll(".reorderChk:checked"));
  if (!checked.length) return;
  const ids = checked.map(chk => parseInt(chk.dataset.id, 10));
  const rows = reorderItemsCache.filter(it => ids.includes(it.id));
  newPOItems = rows.map(it => ({
    product_id: it.product_id, name: it.name, sku: it.sku, qty: it.qty_needed, unit_price_czk: 0,
  }));
  newPOSourceReorderIds = ids;
  openNewPOModal();
  renderNewPOItems();
  // prepnout na zalozku Nakupni objednavky, aby bylo videt kam se to prehodilo
  document.querySelector('.tab-btn[data-tab="purchaseorders"]').click();
};

