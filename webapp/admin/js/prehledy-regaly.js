// ==================== PREHLEDY > TYPOLOGIE/UMISTENI REGALU ====================
// bot16, 2026-09-13 - Robert primo v chatu (relayovano pres bot9): zivy
// katalogovy prehled dvou os, podle kterych se dnes stavi regalove
// sestavy - system/obsah (regal_typologie) a umisteni (regal_umisteni).
// STEJNY princip jako Prehledy > Pravidla/Postupy - zadna kopie obsahu,
// vsechno (cislo i popis) se cte zive z /api/admin/regal-typologie-prehled
// (api/regal_osy_prehled.py) pri kazdem nacteni.

function renderRegalyOsyTable(osy) {
  const tbody = document.getElementById("regalyOsyTbody");
  if (!osy || !osy.length) {
    tbody.innerHTML = '<tr><td colspan="4" class="hint">Žádná data.</td></tr>';
    return;
  }
  // Řádky přichází z backendu už seřazené a seskupené podle osy (nejdřív
  // celá regal_typologie, pak celá regal_umisteni) - první výskyt osy v
  // poli dostane sloupec "Osa" s rowspan přes celou skupinu, další řádky
  // té samé skupiny sloupec "Osa" vůbec nevykreslí (pokryto rowspanem).
  const rowspanByOsa = {};
  osy.forEach(o => { rowspanByOsa[o.osa] = (rowspanByOsa[o.osa] || 0) + 1; });
  const seenOsa = new Set();
  tbody.innerHTML = osy.map(o => {
    const isGroupStart = !seenOsa.has(o.osa);
    seenOsa.add(o.osa);
    const osaCell = isGroupStart
      ? `<td rowspan="${rowspanByOsa[o.osa]}" style="font-weight:600;vertical-align:top;">${escapeHtmlAdmin(o.osa_label)}</td>`
      : "";
    return `
      <tr${isGroupStart ? ' style="border-top:2px solid var(--border-soft2);"' : ""}>
        ${osaCell}
        <td><code>${escapeHtmlAdmin(o.kod)}</code></td>
        <td>
          <div style="font-weight:600;">${escapeHtmlAdmin(o.nazev)}${o.aktivni ? "" : ' <span style="color:var(--text-muted);font-size:11px;">(neaktivní)</span>'}</div>
          <div style="color:var(--text-muted);font-size:12px;margin-top:2px;max-width:520px;">${escapeHtmlAdmin(o.popis || "")}</div>
        </td>
        <td style="text-align:right;font-variant-numeric:tabular-nums;">${o.pocet_sestav}</td>
      </tr>`;
  }).join("");
}

function renderRegalyVerzeTable(verzeRozpad, celkem) {
  const tbody = document.getElementById("regalyVerzeTbody");
  if (!verzeRozpad || !verzeRozpad.length) {
    tbody.innerHTML = '<tr><td colspan="2" class="hint">Žádná data.</td></tr>';
    return;
  }
  tbody.innerHTML = verzeRozpad.map(v => `
    <tr>
      <td><code>${escapeHtmlAdmin(v.verze)}</code></td>
      <td style="text-align:right;font-variant-numeric:tabular-nums;">${v.pocet}</td>
    </tr>
  `).join("") + `
    <tr style="border-top:2px solid var(--border-soft2);font-weight:600;">
      <td>Celkem sestav</td>
      <td style="text-align:right;font-variant-numeric:tabular-nums;">${celkem}</td>
    </tr>`;
}

async function loadRegalyOsy() {
  const errEl = document.getElementById("regalyOsyErr");
  errEl.textContent = "";
  try {
    const r = await fetch("/api/admin/regal-typologie-prehled");
    const data = await r.json();
    if (!r.ok) { errEl.textContent = data.error || "Načtení selhalo."; return; }
    renderRegalyOsyTable(data.osy || []);
    renderRegalyVerzeTable(data.verze_rozpad || [], data.celkem_sestav || 0);
  } catch (e) {
    errEl.textContent = "Načtení selhalo: " + e.message;
  }
}
document.getElementById("regalyOsyRefreshBtn").onclick = loadRegalyOsy;
