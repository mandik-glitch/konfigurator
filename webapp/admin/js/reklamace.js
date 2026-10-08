// ==================== REKLAMACE A VRATKY ====================
// bot18, 2026-09-05 (Robert pres bot3) - navazuje na OFBiz srovnani "Za
// hranice objednavky" + navrh "Reklamace a vratky". Samostatna zalozka
// (tab-returns) + integrace do detailu objednavky (orderReturnSection,
// volano z renderOrderModal v objednavky-doklady.js). Viz api/returns.py
// modulovy docstring pro celkovy kontext/rozhodnuti.

const RETURN_TYPE_LABELS = { reklamace: "Reklamace", odstoupeni: "Odstoupení od smlouvy" };
const RETURN_STATUS_LABELS = {
  pozadovano: "Požadováno", posuzovano: "Posuzováno", schvaleno: "Schváleno",
  prijato: "Přijato zpět", vyrizeno: "Vyřízeno", zamitnuto: "Zamítnuto", zruseno: "Zrušeno",
};
const RETURN_RESOLUTION_LABELS = { refund: "Vrácení peněz", repair: "Oprava", rejected: "Zamítnuto" };
const ITEM_CONDITION_LABELS = { nepouzite: "Nepoužité", poskozene: "Poškozené", vadne: "Vadné" };
// Stejny stavovy graf jako api/returns.py::RETURN_ALLOWED_TRANSITIONS -
// jen pro vykresleni tlacitek s DOVOLENYMI prechody, skutecne vynuceni je
// na backendu (tenhle seznam je jen UX, ne bezpecnostni hranice).
const RETURN_ALLOWED_TRANSITIONS = {
  pozadovano: ["posuzovano", "zruseno"],
  posuzovano: ["schvaleno", "zamitnuto", "zruseno"],
  schvaleno: ["prijato", "zruseno"],
  prijato: ["vyrizeno"],
  vyrizeno: [], zamitnuto: [], zruseno: [],
};

let returnsFilter = { status: "", return_type: "" };
let returnsCache = [];
let currentReturnId = null;

async function loadReturns() {
  const params = new URLSearchParams();
  if (returnsFilter.status) params.set("status", returnsFilter.status);
  if (returnsFilter.return_type) params.set("return_type", returnsFilter.return_type);
  try {
    const r = await fetch(`/api/admin/returns?${params.toString()}`);
    const data = await r.json();
    if (!r.ok) { document.getElementById("returnsErr").textContent = data.error || "Chyba."; return; }
    returnsCache = data.returns || [];
    renderReturnsStatusTabs();
    renderReturnsTable();
  } catch (e) {
    document.getElementById("returnsErr").textContent = "Nepodařilo se načíst reklamace/vratky.";
  }
}

function renderReturnsStatusTabs() {
  const counts = { "": returnsCache.length };
  returnsCache.forEach(r => { counts[r.status] = (counts[r.status] || 0) + 1; });
  const defs = [{ key: "", label: "Vše" }].concat(
    Object.keys(RETURN_STATUS_LABELS).map(k => ({ key: k, label: RETURN_STATUS_LABELS[k] }))
  );
  const wrap = document.getElementById("returnsStatusTabs");
  wrap.innerHTML = defs.map(d => {
    const active = returnsFilter.status === d.key;
    return `<button type="button" class="order-tab-btn${active ? " active" : ""}" data-key="${d.key}">${escapeHtmlAdmin(d.label)}<span class="otc">(${counts[d.key] || 0})</span></button>`;
  }).join("");
  wrap.querySelectorAll(".order-tab-btn").forEach(btn => {
    btn.onclick = () => { returnsFilter.status = btn.dataset.key; loadReturns(); };
  });
}

function renderReturnsTable() {
  document.getElementById("returnsTbody").innerHTML = returnsCache.map(ret => {
    const created = new Date(ret.created_at).toLocaleString("cs-CZ");
    return `<tr class="clickable-row" data-id="${ret.id}">
      <td>${escapeHtmlAdmin(ret.return_number)}</td>
      <td>${escapeHtmlAdmin(ret.order_number || "")}</td>
      <td>${escapeHtmlAdmin(ret.customer_name || "")}</td>
      <td>${escapeHtmlAdmin(RETURN_TYPE_LABELS[ret.return_type] || ret.return_type)}</td>
      <td>${escapeHtmlAdmin(ret.status_label)}</td>
      <td>${created}</td>
    </tr>`;
  }).join("");
  document.querySelectorAll("#returnsTbody tr").forEach(tr => {
    tr.onclick = () => openReturnDetail(parseInt(tr.dataset.id, 10));
  });
}

document.addEventListener("DOMContentLoaded", () => {
  const applyBtn = document.getElementById("returnsFilterApply");
  if (applyBtn) applyBtn.onclick = () => {
    returnsFilter.return_type = document.getElementById("returnsFilterType").value;
    loadReturns();
  };
});

async function openReturnDetail(id) {
  currentReturnId = id;
  document.getElementById("returnModalErr").textContent = "";
  try {
    const r = await fetch(`/api/admin/returns/${id}`);
    const data = await r.json();
    if (!r.ok) { alert(data.error || "Chyba při načítání."); return; }
    renderReturnModal(data);
    document.getElementById("returnModal").classList.add("open");
  } catch (e) {
    alert("Nepodařilo se načíst detail reklamace/vratky.");
  }
}

function renderReturnModal(ret) {
  document.getElementById("returnModalTitle").textContent = `${ret.return_number} — ${RETURN_TYPE_LABELS[ret.return_type] || ret.return_type}`;
  document.getElementById("returnModalMeta").textContent =
    `Objednávka ${ret.order_number} · ${ret.customer_name || ""} · Založeno ${new Date(ret.created_at).toLocaleString("cs-CZ")}`;

  document.getElementById("returnModalItems").innerHTML = ret.items.map(it => `
    <tr>
      <td>${escapeHtmlAdmin(it.product_name_snapshot || "")}</td>
      <td>${it.qty}</td>
      <td>${it.unit_price_czk.toLocaleString("cs-CZ")} Kč</td>
      <td>${escapeHtmlAdmin(ITEM_CONDITION_LABELS[it.item_condition] || it.item_condition)}</td>
    </tr>
  `).join("");

  document.getElementById("returnModalReason").textContent = ret.reason || "(bez uvedeného důvodu)";

  const allowed = RETURN_ALLOWED_TRANSITIONS[ret.status] || [];
  const actionsHtml = allowed.length
    ? allowed.map(s => `<button type="button" class="return-status-btn" data-status="${s}">→ ${escapeHtmlAdmin(RETURN_STATUS_LABELS[s])}</button>`).join(" ")
    : `<span style="color:var(--text-muted);">Konečný stav (${escapeHtmlAdmin(ret.status_label)}), žádný další přechod.</span>`;
  document.getElementById("returnModalActions").innerHTML =
    `<div style="margin-bottom:6px;">Aktuální stav: <b>${escapeHtmlAdmin(ret.status_label)}</b>` +
    (ret.resolution ? ` · Řešení: <b>${escapeHtmlAdmin(RETURN_RESOLUTION_LABELS[ret.resolution] || ret.resolution)}</b>` : "") +
    `</div>${actionsHtml}`;
  document.querySelectorAll(".return-status-btn").forEach(btn => {
    btn.onclick = () => updateReturnStatus(ret.id, btn.dataset.status);
  });

  const creditWrap = document.getElementById("returnModalCreditNote");
  if (ret.credit_note_document_id) {
    creditWrap.innerHTML = `<span style="color:var(--text2);">Dobropis vystaven (doklad #${ret.credit_note_document_id}) - viz záložka Doklady.</span>`;
  } else if (["prijato", "schvaleno"].includes(ret.status)) {
    creditWrap.innerHTML = `<button type="button" id="returnIssueCreditNoteBtn">Vystavit dobropis (vrácení peněz)</button>`;
    document.getElementById("returnIssueCreditNoteBtn").onclick = () => issueCreditNote(ret.id);
  } else {
    creditWrap.innerHTML = `<span style="color:var(--text-muted);">Dobropis lze vystavit až po schválení/přijetí vratky zpět.</span>`;
  }

  const replWrap = document.getElementById("returnModalReplacement");
  replWrap.innerHTML = ret.replacement_order_id
    ? `Náhradní objednávka: <b>#${ret.replacement_order_id}</b> ` +
      `<button type="button" id="returnUnlinkReplacementBtn" style="background:none;border:1px solid #3a3f4a;color:#e07070;">Odpojit</button>`
    : `<input type="number" id="returnReplacementOrderInput" placeholder="ID objednávky…" style="width:120px;"> ` +
      `<button type="button" id="returnLinkReplacementBtn">Připojit náhradní objednávku</button>` +
      `<div style="font-size:11.5px;color:var(--text-muted);margin-top:4px;">Nová objednávka (stejný produkt zdarma, jiný produkt s doplatkem, cokoli) se zakládá ručně běžným způsobem v Objednávkách - tady se jen propojí.</div>`;
  if (ret.replacement_order_id) {
    document.getElementById("returnUnlinkReplacementBtn").onclick = () => setReplacementOrder(ret.id, null);
  } else {
    document.getElementById("returnLinkReplacementBtn").onclick = () => {
      const v = parseInt(document.getElementById("returnReplacementOrderInput").value, 10);
      if (!v) { alert("Zadej ID objednávky."); return; }
      setReplacementOrder(ret.id, v);
    };
  }

  document.getElementById("returnModalHistory").innerHTML = ret.history.map(h => {
    const date = new Date(h.changed_at).toLocaleString("cs-CZ");
    return `<div style="margin-bottom:4px;">${date} — ${escapeHtmlAdmin(h.status_label)}${h.note ? `: ${escapeHtmlAdmin(h.note)}` : ""}</div>`;
  }).join("");
}

async function updateReturnStatus(id, status) {
  const note = document.getElementById("returnModalNote").value.trim();
  try {
    const r = await fetch(`/api/admin/returns/${id}/status`, {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status, note: note || null }),
    });
    const data = await r.json();
    if (!r.ok) { document.getElementById("returnModalErr").textContent = data.error || "Chyba."; return; }
    document.getElementById("returnModalNote").value = "";
    openReturnDetail(id);
    loadReturns();
  } catch (e) {
    document.getElementById("returnModalErr").textContent = "Nepodařilo se uložit stav.";
  }
}

async function issueCreditNote(id) {
  if (!confirm("Vystavit dobropis a označit vratku jako vyřízenou (vrácení peněz)?")) return;
  try {
    const r = await fetch(`/api/admin/returns/${id}/credit-note`, { method: "POST" });
    const data = await r.json();
    if (!r.ok) { document.getElementById("returnModalErr").textContent = data.error || "Chyba."; return; }
    openReturnDetail(id);
    loadReturns();
  } catch (e) {
    document.getElementById("returnModalErr").textContent = "Nepodařilo se vystavit dobropis.";
  }
}

async function setReplacementOrder(id, orderId) {
  try {
    const r = await fetch(`/api/admin/returns/${id}/replacement-order`, {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ order_id: orderId }),
    });
    const data = await r.json();
    if (!r.ok) { document.getElementById("returnModalErr").textContent = data.error || "Chyba."; return; }
    openReturnDetail(id);
  } catch (e) {
    document.getElementById("returnModalErr").textContent = "Nepodařilo se propojit objednávku.";
  }
}

// ---- integrace do detailu objednavky (volano z renderOrderModal) ----

const RETURNABLE_ORDER_STATUSES = ["expedovana", "fakturovana"];

async function renderOrderReturnSection(order) {
  const el = document.getElementById("orderReturnSection");
  if (!el) return;
  if (!RETURNABLE_ORDER_STATUSES.includes(order.status)) {
    el.innerHTML = `<h4>Reklamace a vratky</h4><span style="color:var(--text-muted);font-size:12.5px;">Dostupné až po expedici objednávky.</span>`;
    return;
  }
  let existing = [];
  try {
    const r = await fetch(`/api/admin/returns?order_id=${order.id}`);
    const data = await r.json();
    existing = data.returns || [];
  } catch (e) { /* ticho - sekce neni kriticka pro zobrazeni objednavky */ }

  const existingHtml = existing.length
    ? `<table class="om-items-table"><thead><tr><th>Číslo</th><th>Typ</th><th>Stav</th></tr></thead><tbody>` +
      existing.map(x => `<tr class="clickable-row" data-return-id="${x.id}"><td>${escapeHtmlAdmin(x.return_number)}</td>` +
        `<td>${escapeHtmlAdmin(RETURN_TYPE_LABELS[x.return_type] || x.return_type)}</td><td>${escapeHtmlAdmin(x.status_label)}</td></tr>`).join("") +
      `</tbody></table>`
    : "";

  const itemsRows = (order.items || []).map(it => `
    <div class="mo-item-row" style="margin-bottom:4px;">
      <label style="display:flex;align-items:center;gap:6px;flex:1;">
        <input type="checkbox" class="ret-item-check" data-item-id="${it.id}" data-max-qty="${it.qty}">
        ${escapeHtmlAdmin(it.product_name)} (max ${it.qty} ks)
      </label>
      <input type="number" class="ret-item-qty" data-item-id="${it.id}" value="1" min="1" max="${it.qty}" style="width:60px;" disabled>
      <select class="ret-item-condition" data-item-id="${it.id}" disabled>
        <option value="nepouzite">Nepoužité</option>
        <option value="poskozene">Poškozené</option>
        <option value="vadne">Vadné</option>
      </select>
    </div>
  `).join("");

  el.innerHTML = `
    <h4>Reklamace a vratky</h4>
    ${existingHtml}
    <div style="margin-top:8px;">
      <div>${itemsRows}</div>
      <select id="orderReturnType" style="margin-top:6px;">
        <option value="reklamace">Reklamace (vadné/poškozené zboží)</option>
        <option value="odstoupeni">Odstoupení od smlouvy (14 dní)</option>
      </select>
      <textarea id="orderReturnReason" placeholder="Důvod (nepovinné)" style="width:100%;box-sizing:border-box;margin-top:6px;min-height:40px;"></textarea>
      <button type="button" id="orderReturnSubmitBtn" style="margin-top:6px;">Založit reklamaci/vratku</button>
      <div id="orderReturnErr" class="err"></div>
    </div>
  `;
  el.querySelectorAll(".ret-item-check").forEach(chk => {
    chk.onchange = () => {
      const row = chk.closest(".mo-item-row");
      row.querySelectorAll(".ret-item-qty, .ret-item-condition").forEach(inp => { inp.disabled = !chk.checked; });
    };
  });
  el.querySelectorAll(".clickable-row[data-return-id]").forEach(tr => {
    tr.onclick = () => {
      document.getElementById("orderModal").classList.remove("open");
      openReturnDetail(parseInt(tr.dataset.returnId, 10));
    };
  });
  document.getElementById("orderReturnSubmitBtn").onclick = () => createReturnFromOrderModal(order.id);
}

async function createReturnFromOrderModal(orderId) {
  const items = [];
  document.querySelectorAll("#orderReturnSection .ret-item-check:checked").forEach(chk => {
    const itemId = parseInt(chk.dataset.itemId, 10);
    const qty = parseInt(document.querySelector(`.ret-item-qty[data-item-id="${itemId}"]`).value, 10);
    const condition = document.querySelector(`.ret-item-condition[data-item-id="${itemId}"]`).value;
    items.push({ order_item_id: itemId, qty, item_condition: condition });
  });
  if (!items.length) { document.getElementById("orderReturnErr").textContent = "Vyber aspoň 1 položku."; return; }
  const body = {
    return_type: document.getElementById("orderReturnType").value,
    reason: document.getElementById("orderReturnReason").value.trim() || null,
    items,
  };
  try {
    const r = await fetch(`/api/admin/orders/${orderId}/returns`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    });
    const data = await r.json();
    if (!r.ok) { document.getElementById("orderReturnErr").textContent = data.error || "Chyba."; return; }
    openOrderDetail(orderId);
    loadReturns();
  } catch (e) {
    document.getElementById("orderReturnErr").textContent = "Nepodařilo se založit reklamaci/vratku.";
  }
}
