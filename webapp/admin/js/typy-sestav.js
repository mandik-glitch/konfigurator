// bot16, 2026-09-26 (Robert pres bot3, PLAN_TVORBY_SESTAV.md "Nová osa:
// typ sestavy") - centralni sprava osy sestava_typ (AUTO/STUL_SKLAD/...)
// a jejich volitelnych sluzeb (sestava_typ_sluzba), jedno misto v adminu.
// Backend viz api/sestava_typ.py. DULEZITE: tenhle panel zatim NIC
// nemeni na chovani webu - je to jen sprava ciselniku pred budoucim
// zapojenim (migrace existujicich sestav na typ + presun Vandr textu
// jsou SAMOSTATNE kroky s dry-run, viz koordinace s bot3).

const PRICING_MODE_LABELS = {
  informativni: "Informativní (jen text)",
  procento_z_ceny: "Procento z ceny",
  pevna_castka: "Pevná částka",
};

let sestavaTypRows = [];
let sestavaTypSluzbyRows = [];

async function loadSestavaTyp() {
  try {
    const [rTyp, rSluzby] = await Promise.all([
      fetch("/api/admin/sestava-typ"),
      fetch("/api/admin/sestava-typ-sluzby"),
    ]);
    sestavaTypRows = (await rTyp.json()).rows || [];
    sestavaTypSluzbyRows = (await rSluzby.json()).rows || [];
    renderSestavaTyp();
  } catch (e) {
    const err = document.getElementById("sestavaTypErr");
    if (err) err.textContent = "Nepodařilo se načíst typy sestav.";
  }
}

function sluzbyProTyp(typId) {
  return sestavaTypSluzbyRows.filter(s => s.sestava_typ_id === typId);
}

function renderSluzbyTable(typId) {
  const rows = sluzbyProTyp(typId);
  const rowsHtml = rows.map(s => `
    <tr data-id="${s.id}">
      <td><input type="text" class="sts-nazev" style="width:160px" value="${(s.nazev || "").replace(/"/g, "&quot;")}"></td>
      <td style="color:var(--text-muted,#8b93a1);font-family:monospace;">${s.klic}</td>
      <td>
        <select class="sts-pricing-mode">
          ${Object.entries(PRICING_MODE_LABELS).map(([k, label]) =>
            `<option value="${k}" ${s.pricing_mode === k ? "selected" : ""}>${label}</option>`).join("")}
        </select>
      </td>
      <td><input type="number" step="0.01" class="sts-hodnota" style="width:90px" value="${s.hodnota ?? ""}" ${s.pricing_mode === "informativni" ? "disabled" : ""}></td>
      <td style="text-align:center;"><input type="checkbox" class="sts-vyzaduje" ${s.vyzaduje_dalsi_pole ? "checked" : ""}></td>
      <td style="text-align:center;"><input type="checkbox" class="sts-aktivni" ${s.aktivni ? "checked" : ""}></td>
      <td><button class="sts-save">Uložit</button></td>
    </tr>
  `).join("");
  return `
    <table style="width:100%;font-size:12.5px;margin:8px 0;">
      <thead><tr>
        <th style="text-align:left;">Název</th><th style="text-align:left;">Klíč</th>
        <th style="text-align:left;">Cena</th><th style="text-align:left;">Hodnota</th>
        <th>Vyžaduje pole</th><th>Aktivní</th><th></th>
      </tr></thead>
      <tbody class="sts-tbody" data-typ-id="${typId === null ? "" : typId}">${rowsHtml}</tbody>
    </table>
    <div class="add-form" style="margin-bottom:4px;">
      <input type="text" class="sts-new-nazev" placeholder="Nová služba (např. Montáž na místě)" style="width:220px;">
      <button class="sts-add">Přidat</button>
    </div>
  `;
}

function wireSluzbyTable(container, typId) {
  const tbody = container.querySelector(".sts-tbody");
  tbody.querySelectorAll("tr").forEach(tr => {
    const id = tr.dataset.id;
    const modeSelect = tr.querySelector(".sts-pricing-mode");
    const hodnotaInput = tr.querySelector(".sts-hodnota");
    modeSelect.addEventListener("change", () => {
      hodnotaInput.disabled = modeSelect.value === "informativni";
    });
    tr.querySelector(".sts-save").onclick = async () => {
      const r = await fetch(`/api/admin/sestava-typ-sluzby/${id}`, {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          nazev: tr.querySelector(".sts-nazev").value.trim(),
          pricing_mode: modeSelect.value,
          hodnota: hodnotaInput.disabled ? null : hodnotaInput.value,
          vyzaduje_dalsi_pole: tr.querySelector(".sts-vyzaduje").checked,
          aktivni: tr.querySelector(".sts-aktivni").checked,
        }),
      });
      const d = await r.json().catch(() => ({}));
      const err = document.getElementById("sestavaTypErr");
      if (!r.ok) { err.textContent = d.error || "Chyba."; return; }
      err.textContent = "";
      loadSestavaTyp();
    };
  });
  const addInput = container.querySelector(".sts-new-nazev");
  container.querySelector(".sts-add").onclick = async () => {
    const nazev = addInput.value.trim();
    const err = document.getElementById("sestavaTypErr");
    if (!nazev) { err.textContent = "Zadejte název služby."; return; }
    const r = await fetch("/api/admin/sestava-typ-sluzby", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ nazev, sestava_typ_id: typId }),
    });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) { err.textContent = d.error || "Chyba."; return; }
    err.textContent = "";
    addInput.value = "";
    loadSestavaTyp();
  };
}

function renderSestavaTyp() {
  const root = document.getElementById("sestavaTypList");
  if (!root) return;
  root.innerHTML = "";

  // Globalni sluzby (sestava_typ_id = NULL) - plati pro vsechny typy.
  const globalCard = document.createElement("div");
  globalCard.style.cssText = "border:1px solid var(--border-soft);border-radius:6px;background:var(--panel-bg);padding:12px 14px;margin-bottom:18px;";
  globalCard.innerHTML = `
    <b>Globální služby</b>
    <span class="hint" style="margin:2px 0 0;">Platí pro všechny typy sestav zároveň (bot5: společný klíč, přes který se filtruje, co dává smysl u kterého typu).</span>
    ${renderSluzbyTable(null)}
  `;
  root.appendChild(globalCard);
  wireSluzbyTable(globalCard, null);

  sestavaTypRows.forEach(typ => {
    const card = document.createElement("div");
    card.style.cssText = "border:1px solid var(--border-soft);border-radius:6px;background:var(--panel-bg);padding:12px 14px;margin-bottom:18px;";
    card.innerHTML = `
      <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;">
        <span style="font-family:monospace;color:var(--text-muted,#8b93a1);">${typ.kod}</span>
        <input type="text" class="st-nazev" style="width:220px;" value="${(typ.nazev || "").replace(/"/g, "&quot;")}">
        <label style="display:flex;align-items:center;gap:4px;font-size:12px;">
          <input type="checkbox" class="st-aktivni" ${typ.aktivni ? "checked" : ""}> aktivní
        </label>
        <button class="st-save">Uložit</button>
      </div>
      <textarea class="st-popis" rows="2" placeholder="Výchozí text popisu pro tento typ (bez terminologie jiných typů - žádné vozidlové fráze u STUL_SKLAD apod.)" style="width:100%;margin-top:8px;">${typ.popis_sablona || ""}</textarea>
      <b style="margin-top:10px;display:block;">Volitelné služby pro tento typ</b>
      ${renderSluzbyTable(typ.id)}
    `;
    root.appendChild(card);
    card.querySelector(".st-save").onclick = async () => {
      const r = await fetch(`/api/admin/sestava-typ/${typ.id}`, {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          nazev: card.querySelector(".st-nazev").value.trim(),
          popis_sablona: card.querySelector(".st-popis").value,
          aktivni: card.querySelector(".st-aktivni").checked,
        }),
      });
      const d = await r.json().catch(() => ({}));
      const err = document.getElementById("sestavaTypErr");
      if (!r.ok) { err.textContent = d.error || "Chyba."; return; }
      err.textContent = "";
      loadSestavaTyp();
    };
    wireSluzbyTable(card, typ.id);
  });
}

const btnAddSestavaTyp = document.getElementById("btnAddSestavaTyp");
if (btnAddSestavaTyp) btnAddSestavaTyp.onclick = async () => {
  const input = document.getElementById("sestavaTypNewName");
  const nazev = input.value.trim();
  const err = document.getElementById("sestavaTypErr");
  if (!nazev) { err.textContent = "Zadejte název typu."; return; }
  const r = await fetch("/api/admin/sestava-typ", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ nazev }),
  });
  const d = await r.json().catch(() => ({}));
  if (!r.ok) { err.textContent = d.error || "Chyba."; return; }
  err.textContent = "";
  input.value = "";
  loadSestavaTyp();
};

loadSestavaTyp();
