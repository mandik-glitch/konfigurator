// "Tvorba sestav – Vandr" panel na Dashboardu (bot5, 2026-09-23, zadání
// Robert přes bot3: "udelejme v adminu uplne stejnou prehledovou tabulku
// tvorby sestav Vandr, jako ma 1. vetev").
//
// SAMOSTATNÝ od admin/js/vyroba-sestav.js - stejný vizuální koncept
// (fáze jako sloupce, dopočítávané server-side, needitovatelné tady),
// ale jednodušší data: 1 řádek = 1 Vandr karta (VD-<uuid>), žádné
// rozbalování na sestavy (Vandr karta = vždy jen 1 "sestava"/stub, na
// rozdíl od nativní větve). Zdroj: api/vandr_production_overview.py.

let vandrVyrobaData = null;

function escapeHtmlVandrVyroba(s) {
  return String(s == null ? "" : s).replace(/[&<>"']/g, c => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
  ));
}

function vandrVyrobaBoolCell(v) {
  return v ? '<span class="vs-ratio-full">✓</span>' : '<span class="vs-ratio-zero">–</span>';
}

// Razítka - stejné 3 stavy/vzhled jako nativní panel (scripts/razitkovac.py::stav_razitek).
function vandrVyrobaRazitkoCell(stav) {
  if (stav === "aktualni") return '<span class="vs-ratio-full">✓</span>';
  if (stav === "zastarala") return '<span class="vs-razitka-stale" title="Razítka neodpovídají aktuální sestavě, potřebují přerazítkovat.">⚠ zastaralé</span>';
  return '<span class="vs-ratio-zero">–</span>';
}

function vandrVyrobaElevaceCell(elevace) {
  if (!elevace || !elevace.length) return '<span class="vs-ratio-zero">–</span>';
  const chce = [0, 40];
  const ma = chce.every(e => elevace.includes(e));
  const cls = ma ? "vs-ratio-full" : "vs-ratio-partial";
  return `<span class="${cls}">${elevace.map(e => e + "°").join(", ")}</span>`;
}

// WORKFLOW.md pravidlo 51 (bot10 2026-09-24, Robert pres bot3: "kazda
// sestava do auta musi nest stitek na jakou stranu auta je navrzena" +
// "stitky umisteni sestavy musi byt videt jak v prehledu sestav tak
// detailu"). Stejna konvence jako webapp/scene.html (bot8, commit
// eb0d7650): kod jako kratky odznak (prehled), plny nazev v tooltipu
// (detail); NULL je CERVENE "?", nikdy prazdno/pomlcka - karta bez
// stitku neni hotova, nesmi to vypadat jako "v poradku, jen 0".
function vandrVyrobaUmisteniCell(kod, nazev) {
  if (!kod) {
    return '<span class="vs-umisteni-neurceno" title="NEURČENO - karta nemá štítek strany vozu (WORKFLOW.md pravidlo 51)">?</span>';
  }
  return `<span title="Umístění: ${escapeHtmlVandrVyroba(kod)} - ${escapeHtmlVandrVyroba(nazev || "")}">${escapeHtmlVandrVyroba(kod)}</span>`;
}

async function loadVandrVyrobaPrehled() {
  const errEl = document.getElementById("vandrVyrobaErr");
  const contentEl = document.getElementById("vandrVyrobaContent");
  if (!contentEl) return;
  errEl.textContent = "";
  try {
    const r = await fetch("/api/admin/vandr-vyroba/prehled");
    const data = await r.json();
    if (!r.ok) {
      if (r.status === 403 || r.status === 401) {
        document.getElementById("vandrVyrobaPanel").style.display = "none";
        return;
      }
      errEl.textContent = data.error || "Nepodařilo se načíst přehled.";
      return;
    }
    document.getElementById("vandrVyrobaPanel").style.display = "";
    vandrVyrobaData = data;
    const totalEl = document.getElementById("vandrVyrobaTotal");
    if (totalEl) totalEl.textContent = `(${data.pocet} karet)`;
    renderVandrVyrobaSummary();
    renderVandrVyrobaTable();
  } catch (e) {
    errEl.textContent = "Nepodařilo se načíst přehled (spojení).";
  }
}

function renderVandrVyrobaSummary() {
  const el = document.getElementById("vandrVyrobaSummary");
  if (!el) return;
  const s = (vandrVyrobaData && vandrVyrobaData.souhrn) || null;
  if (!s) { el.innerHTML = ""; return; }
  el.innerHTML = `
    <span class="vs-serie-badge">🌐 live na webu: <b>${s.web}</b>/${s.celkem}</span>
    ${s.ceka_glb ? ` <span class="vs-serie-badge">🧊 čeká na GLB konverzi (bot10): <b>${s.ceka_glb}</b></span>` : ""}
    ${s.ceka_razitko ? ` <span class="vs-serie-badge">⏳ čeká na razítko (bot4): <b>${s.ceka_razitko}</b></span>` : ""}
    ${s.razitko_zastarala ? ` <span class="vs-razitka-stale">⚠ zastaralé razítko: <b>${s.razitko_zastarala}</b></span>` : ""}
    ${s.cheka_render ? ` <span class="vs-serie-badge">🎬 čeká na render: <b>${s.cheka_render}</b></span>` : ""}
    ${s.bez_karty ? ` <span class="vs-serie-badge">📦 FBX bez karty: <b>${s.bez_karty}</b></span>` : ""}
  `;
}

function renderVandrVyrobaTable() {
  const contentEl = document.getElementById("vandrVyrobaContent");
  if (!vandrVyrobaData || !vandrVyrobaData.kartas.length) {
    contentEl.innerHTML = '<p class="hint">Žádné Vandr karty.</p>';
    return;
  }
  const rows = vandrVyrobaData.kartas.map(k => {
    const nazev = k.name
      ? `${escapeHtmlVandrVyroba(k.name)} <span class="hint">${escapeHtmlVandrVyroba(k.sku)}</span>`
      : `<span class="hint">(zatím bez karty)</span> ${escapeHtmlVandrVyroba(k.sku)}`;
    const odkaz = k.slug
      ? `<a href="/produkt/${encodeURIComponent(k.slug)}" target="_blank" rel="noopener">${nazev}</a>`
      : nazev;
    return `
      <tr>
        <td>${odkaz}</td>
        <td class="vs-center">${vandrVyrobaUmisteniCell(k.umisteni_kod, k.umisteni_nazev)}</td>
        <td class="vs-center">${vandrVyrobaBoolCell(k.fbx_export)}</td>
        <td class="vs-center">${vandrVyrobaBoolCell(k.karta)}</td>
        <td class="vs-center">${vandrVyrobaBoolCell(k.cena && k.kategorie)}</td>
        <td class="vs-center">${vandrVyrobaBoolCell(k.glb)}</td>
        <td class="vs-center">${vandrVyrobaRazitkoCell(k.razitko)}</td>
        <td class="vs-center">${vandrVyrobaElevaceCell(k.elevace)}</td>
        <td class="vs-center">${vandrVyrobaBoolCell(k.web)}</td>
        <td>${escapeHtmlVandrVyroba(k.dalsi_krok)}</td>
      </tr>`;
  }).join("");

  contentEl.innerHTML = `
    <div style="overflow-x:auto;">
    <table class="vs-table">
      <thead><tr>
        <th>Karta</th><th title="WORKFLOW.md pravidlo 51">Umístění</th><th>1 FBX export</th><th>2 Karta</th><th>3 Cena+kategorie</th>
        <th>GLB (bot10)</th><th>Razítko (bot4)</th><th>4 Rendery (0°/40°)</th><th>5 Web</th><th>Další krok</th>
      </tr></thead>
      <tbody>${rows}</tbody>
    </table>
    </div>`;
}

const vandrVyrobaRefreshBtnEl = document.getElementById("vandrVyrobaRefreshBtn");
if (vandrVyrobaRefreshBtnEl) vandrVyrobaRefreshBtnEl.onclick = loadVandrVyrobaPrehled;
