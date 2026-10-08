// ==================== DOPRAVA A PLATBA ====================
// Robert: "dopravu v adminu nevidím ani faktury" - admin UI nad
// shipping-methods/payment-methods (existovalo bez UI) + Toptrans
// shipping-price-rules/shipping-zip-bands (bot3 v8), aby slo cenik a
// PSC pasma opravovat bez redeploy.
let shippingMethodsCache = [];
let paymentMethodsCache = [];
let shippingShowArchived = false;
let paymentShowArchived = false;

async function loadShippingMethods() {
  try {
    const r = await fetch(`/api/admin/shipping-methods${shippingShowArchived ? "?archived=1" : ""}`);
    const data = await r.json();
    shippingMethodsCache = data.methods || [];
    renderShippingMethods();
    populateKmBandFilter();
    const sel = document.getElementById("orderFilterShipping");
    if (sel) {
      const current = sel.value;
      sel.innerHTML = '<option value="">Doprava: vše</option>' +
        shippingMethodsCache.map(m => `<option value="${escapeHtmlAdmin(m.name)}">${escapeHtmlAdmin(m.name)}</option>`).join("");
      sel.value = current;
    }
  } catch (e) {
    document.getElementById("shippingMethodsErr").textContent = "Nepodařilo se načíst způsoby dopravy.";
  }
}
document.getElementById("shippingShowArchivedBtn").onclick = () => {
  shippingShowArchived = !shippingShowArchived;
  const btn = document.getElementById("shippingShowArchivedBtn");
  btn.textContent = shippingShowArchived ? "Skrýt archivované" : "Zobrazit archivované";
  btn.style.background = shippingShowArchived ? "#3a5a7a" : "none";
  btn.style.color = shippingShowArchived ? "#fff" : "#c7ccd4";
  shippingSelectedIds.clear();
  loadShippingMethods();
};

let shippingSelectedIds = new Set();

function renderShippingMethods() {
  const tbody = document.getElementById("shippingMethodsTbody");
  tbody.innerHTML = shippingMethodsCache.map(m => `
    <tr data-id="${m.id}">
      <td><input type="checkbox" class="ship-chk" data-id="${m.id}" ${shippingSelectedIds.has(m.id) ? "checked" : ""}></td>
      <td><input type="text" class="ship-name" value="${escapeHtmlAdmin(m.name)}" style="width:160px;"></td>
      <td><input type="number" class="ship-price" value="${m.price_czk}" step="0.01" style="width:90px;"></td>
      <td>${m.pricing_mode === "zip_weight" ? "PSČ + hmotnost (Toptrans)" : "pevná cena"}</td>
      <td>${m.is_default ? "ano" : "ne"}</td>
      <td><input type="checkbox" class="ship-active" ${m.active ? "checked" : ""}></td>
      <td>
        <button class="ship-save" data-id="${m.id}">Uložit</button>
        <button class="ship-del" data-id="${m.id}" style="background:none;border:1px solid #3a3f4a;color:#c7ccd4;">Smazat</button>
      </td>
    </tr>
  `).join("");
  tbody.querySelectorAll(".ship-save").forEach(btn => {
    btn.onclick = async () => {
      const tr = btn.closest("tr");
      const body = {
        name: tr.querySelector(".ship-name").value.trim(),
        price_czk: parseFloat(tr.querySelector(".ship-price").value) || 0,
        active: tr.querySelector(".ship-active").checked,
      };
      const r = await fetch(`/api/admin/shipping-methods/${btn.dataset.id}`, {
        method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
      });
      const data = await r.json().catch(() => ({}));
      if (!r.ok) { document.getElementById("shippingMethodsErr").textContent = data.error || "Chyba."; return; }
      loadShippingMethods();
    };
  });
  tbody.querySelectorAll(".ship-del").forEach(btn => {
    btn.onclick = async () => {
      if (!confirm("Opravdu smazat tento způsob dopravy?")) return;
      await fetch(`/api/admin/shipping-methods/${btn.dataset.id}`, { method: "DELETE" });
      loadShippingMethods();
    };
  });
  tbody.querySelectorAll(".ship-chk").forEach(chk => {
    chk.onchange = () => {
      const id = parseInt(chk.dataset.id, 10);
      if (chk.checked) shippingSelectedIds.add(id); else shippingSelectedIds.delete(id);
      updateShippingBulkToolbar();
    };
  });
  updateShippingBulkToolbar();
}

function updateShippingBulkToolbar() {
  const bar = document.getElementById("shippingBulkToolbar");
  const count = shippingSelectedIds.size;
  bar.classList.toggle("active", count > 0);
  document.getElementById("shippingBulkCount").textContent = `${count} vybráno`;
}
document.getElementById("shippingSelectAll").onchange = (e) => {
  if (e.target.checked) shippingMethodsCache.forEach(m => shippingSelectedIds.add(m.id));
  else shippingSelectedIds.clear();
  renderShippingMethods();
};
async function shippingBulkSetActive(active) {
  if (!shippingSelectedIds.size) return;
  const r = await fetch("/api/admin/shipping-methods/bulk-active", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ids: [...shippingSelectedIds], active }),
  });
  const data = await r.json().catch(() => ({}));
  if (data.failed && data.failed.length) {
    alert(`Nastaveno: ${data.updated}. Přeskočeno: ${data.failed.length} (např. výchozí způsob dopravy).`);
  }
  loadShippingMethods();
}
document.getElementById("shippingBulkActivate").onclick = () => shippingBulkSetActive(true);
document.getElementById("shippingBulkDeactivate").onclick = () => shippingBulkSetActive(false);
document.getElementById("shippingBulkDelete").onclick = async () => {
  if (!shippingSelectedIds.size) return;
  if (!confirm(`Opravdu smazat ${shippingSelectedIds.size} vybraných způsobů dopravy?`)) return;
  const r = await fetch("/api/admin/shipping-methods/bulk-delete", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ids: [...shippingSelectedIds] }),
  });
  const data = await r.json().catch(() => ({}));
  shippingSelectedIds.clear();
  if (data.failed && data.failed.length) {
    alert(`Smazáno: ${data.deleted}. Nešlo smazat: ${data.failed.length} (např. výchozí způsob dopravy, nebo metoda s vlastním ceníkem).`);
  }
  loadShippingMethods();
};

document.getElementById("btnAddShippingMethod").onclick = async () => {
  const errEl = document.getElementById("shippingMethodsErr");
  errEl.textContent = "";
  const name = document.getElementById("newShippingName").value.trim();
  if (!name) { errEl.textContent = "Chybí název."; return; }
  const price = parseFloat(document.getElementById("newShippingPrice").value) || 0;
  const r = await fetch("/api/admin/shipping-methods", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name, price_czk: price }),
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) { errEl.textContent = data.error || "Chyba."; return; }
  document.getElementById("newShippingName").value = "";
  document.getElementById("newShippingPrice").value = "";
  loadShippingMethods();
};

async function loadPaymentMethods() {
  try {
    const r = await fetch(`/api/admin/payment-methods${paymentShowArchived ? "?archived=1" : ""}`);
    const data = await r.json();
    paymentMethodsCache = data.methods || [];
    renderPaymentMethods();
    const sel = document.getElementById("orderFilterPayment");
    if (sel) {
      const current = sel.value;
      sel.innerHTML = '<option value="">Platba: vše</option>' +
        paymentMethodsCache.map(m => `<option value="${escapeHtmlAdmin(m.name)}">${escapeHtmlAdmin(m.name)}</option>`).join("");
      sel.value = current;
    }
  } catch (e) {
    document.getElementById("paymentMethodsErr").textContent = "Nepodařilo se načíst způsoby platby.";
  }
}
document.getElementById("paymentShowArchivedBtn").onclick = () => {
  paymentShowArchived = !paymentShowArchived;
  const btn = document.getElementById("paymentShowArchivedBtn");
  btn.textContent = paymentShowArchived ? "Skrýt archivované" : "Zobrazit archivované";
  btn.style.background = paymentShowArchived ? "#3a5a7a" : "none";
  btn.style.color = paymentShowArchived ? "#fff" : "#c7ccd4";
  paymentSelectedIds.clear();
  loadPaymentMethods();
};

let paymentSelectedIds = new Set();

function renderPaymentMethods() {
  const tbody = document.getElementById("paymentMethodsTbody");
  tbody.innerHTML = paymentMethodsCache.map(m => `
    <tr data-id="${m.id}">
      <td><input type="checkbox" class="pay-chk" data-id="${m.id}" ${paymentSelectedIds.has(m.id) ? "checked" : ""}></td>
      <td><input type="text" class="pay-name" value="${escapeHtmlAdmin(m.name)}" style="width:200px;"></td>
      <td><input type="number" class="pay-price" value="${m.price_czk}" step="0.01" style="width:90px;"></td>
      <td><input type="checkbox" class="pay-active" ${m.active ? "checked" : ""}></td>
      <td>
        <button class="pay-save" data-id="${m.id}">Uložit</button>
        <button class="pay-del" data-id="${m.id}" style="background:none;border:1px solid #3a3f4a;color:#c7ccd4;">Smazat</button>
      </td>
    </tr>
  `).join("");
  tbody.querySelectorAll(".pay-save").forEach(btn => {
    btn.onclick = async () => {
      const tr = btn.closest("tr");
      const body = {
        name: tr.querySelector(".pay-name").value.trim(),
        price_czk: parseFloat(tr.querySelector(".pay-price").value) || 0,
        active: tr.querySelector(".pay-active").checked,
      };
      const r = await fetch(`/api/admin/payment-methods/${btn.dataset.id}`, {
        method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
      });
      const data = await r.json().catch(() => ({}));
      if (!r.ok) { document.getElementById("paymentMethodsErr").textContent = data.error || "Chyba."; return; }
      loadPaymentMethods();
    };
  });
  tbody.querySelectorAll(".pay-del").forEach(btn => {
    btn.onclick = async () => {
      if (!confirm("Opravdu smazat tento způsob platby?")) return;
      await fetch(`/api/admin/payment-methods/${btn.dataset.id}`, { method: "DELETE" });
      loadPaymentMethods();
    };
  });
  tbody.querySelectorAll(".pay-chk").forEach(chk => {
    chk.onchange = () => {
      const id = parseInt(chk.dataset.id, 10);
      if (chk.checked) paymentSelectedIds.add(id); else paymentSelectedIds.delete(id);
      updatePaymentBulkToolbar();
    };
  });
  updatePaymentBulkToolbar();
}

function updatePaymentBulkToolbar() {
  const bar = document.getElementById("paymentBulkToolbar");
  const count = paymentSelectedIds.size;
  bar.classList.toggle("active", count > 0);
  document.getElementById("paymentBulkCount").textContent = `${count} vybráno`;
}
document.getElementById("paymentSelectAll").onchange = (e) => {
  if (e.target.checked) paymentMethodsCache.forEach(m => paymentSelectedIds.add(m.id));
  else paymentSelectedIds.clear();
  renderPaymentMethods();
};
async function paymentBulkSetActive(active) {
  if (!paymentSelectedIds.size) return;
  await fetch("/api/admin/payment-methods/bulk-active", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ids: [...paymentSelectedIds], active }),
  });
  loadPaymentMethods();
}
document.getElementById("paymentBulkActivate").onclick = () => paymentBulkSetActive(true);
document.getElementById("paymentBulkDeactivate").onclick = () => paymentBulkSetActive(false);
document.getElementById("paymentBulkDelete").onclick = async () => {
  if (!paymentSelectedIds.size) return;
  if (!confirm(`Opravdu smazat ${paymentSelectedIds.size} vybraných způsobů platby?`)) return;
  await fetch("/api/admin/payment-methods/bulk-delete", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ids: [...paymentSelectedIds] }),
  });
  paymentSelectedIds.clear();
  loadPaymentMethods();
};

document.getElementById("btnAddPaymentMethod").onclick = async () => {
  const errEl = document.getElementById("paymentMethodsErr");
  errEl.textContent = "";
  const name = document.getElementById("newPaymentName").value.trim();
  if (!name) { errEl.textContent = "Chybí název."; return; }
  const price = parseFloat(document.getElementById("newPaymentPrice").value) || 0;
  const r = await fetch("/api/admin/payment-methods", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name, price_czk: price }),
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) { errEl.textContent = data.error || "Chyba."; return; }
  document.getElementById("newPaymentName").value = "";
  document.getElementById("newPaymentPrice").value = "";
  loadPaymentMethods();
};

// --- Cenik Toptrans (shop_shipping_price_rules) ---
let priceRulesCache = [];
let priceRulesKmFilter = "";

function populateKmBandFilter() {
  const bands = [...new Set(priceRulesCache.map(r => r.km_band))].sort((a, b) => a - b);
  const sel = document.getElementById("priceRulesFilterKm");
  const current = sel.value;
  sel.innerHTML = '<option value="">Všechna vzdálenostní pásma</option>' +
    bands.map(b => `<option value="${b}">do ${b} km</option>`).join("");
  sel.value = current;
}

async function loadPriceRules() {
  try {
    const r = await fetch("/api/admin/shipping-price-rules");
    const data = await r.json();
    priceRulesCache = data.rules || [];
    populateKmBandFilter();
    renderPriceRules();
  } catch (e) {
    document.getElementById("priceRulesErr").textContent = "Nepodařilo se načíst ceník.";
  }
}

function renderPriceRules() {
  const tbody = document.getElementById("priceRulesTbody");
  const rows = priceRulesKmFilter
    ? priceRulesCache.filter(r => String(r.km_band) === priceRulesKmFilter)
    : priceRulesCache;
  document.getElementById("priceRulesSelectAll").checked = false;
  if (!rows.length) {
    tbody.innerHTML = '<tr><td colspan="6" style="color:#666;">Žádná pravidla.</td></tr>';
    updatePriceRulesBulkToolbar();
    return;
  }
  tbody.innerHTML = rows.map(rule => `
    <tr data-id="${rule.id}">
      <td><input type="checkbox" class="priceRuleChk" data-id="${rule.id}"></td>
      <td><input type="number" class="rule-weight" value="${rule.weight_to_kg}" step="0.1" style="width:80px;"></td>
      <td><input type="number" class="rule-volume" value="${rule.volume_to_m3 ?? ""}" step="0.001" style="width:80px;"></td>
      <td><input type="number" class="rule-km" value="${rule.km_band}" style="width:80px;"></td>
      <td><input type="number" class="rule-price" value="${rule.price_czk}" step="0.01" style="width:100px;"></td>
      <td>
        <button class="rule-save" data-id="${rule.id}">Uložit</button>
        <button class="rule-del" data-id="${rule.id}" style="background:none;border:1px solid #3a3f4a;color:#c7ccd4;">Smazat</button>
      </td>
    </tr>
  `).join("");
  tbody.querySelectorAll(".priceRuleChk").forEach(chk => chk.addEventListener("change", updatePriceRulesBulkToolbar));
  tbody.querySelectorAll(".rule-save").forEach(btn => {
    btn.onclick = async () => {
      const tr = btn.closest("tr");
      const volRaw = tr.querySelector(".rule-volume").value;
      const body = {
        weight_to_kg: parseFloat(tr.querySelector(".rule-weight").value),
        volume_to_m3: volRaw === "" ? null : parseFloat(volRaw),
        km_band: parseInt(tr.querySelector(".rule-km").value, 10),
        price_czk: parseFloat(tr.querySelector(".rule-price").value),
      };
      const r = await fetch(`/api/admin/shipping-price-rules/${btn.dataset.id}`, {
        method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
      });
      const data = await r.json().catch(() => ({}));
      if (!r.ok) { document.getElementById("priceRulesErr").textContent = data.error || "Chyba."; return; }
      loadPriceRules();
    };
  });
  tbody.querySelectorAll(".rule-del").forEach(btn => {
    btn.onclick = async () => {
      if (!confirm("Opravdu smazat toto cenové pravidlo?")) return;
      await fetch(`/api/admin/shipping-price-rules/${btn.dataset.id}`, { method: "DELETE" });
      loadPriceRules();
    };
  });
  updatePriceRulesBulkToolbar();
}

function updatePriceRulesBulkToolbar() {
  const checked = document.querySelectorAll(".priceRuleChk:checked").length;
  const bar = document.getElementById("priceRulesBulkToolbar");
  bar.classList.toggle("active", checked > 0);
  document.getElementById("priceRulesBulkCount").textContent = `${checked} vybráno`;
}

document.getElementById("priceRulesSelectAll").onchange = (e) => {
  document.querySelectorAll(".priceRuleChk").forEach(chk => { chk.checked = e.target.checked; });
  updatePriceRulesBulkToolbar();
};

document.getElementById("priceRulesBulkDelete").onclick = async () => {
  const ids = Array.from(document.querySelectorAll(".priceRuleChk:checked")).map(chk => parseInt(chk.dataset.id, 10));
  if (!ids.length) return;
  if (!confirm(`Opravdu smazat ${ids.length} vybraných cenových pravidel? Tuto akci nelze vrátit zpět.`)) return;
  const r = await fetch("/api/admin/shipping-price-rules/bulk-delete", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ids }),
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) { document.getElementById("priceRulesErr").textContent = data.error || "Chyba."; return; }
  if (data.failed && data.failed.length) {
    alert(`Smazáno: ${data.deleted}. Nenalezeno: ${data.failed.length}.`);
  }
  loadPriceRules();
};

document.getElementById("priceRulesFilterApply").onclick = () => {
  priceRulesKmFilter = document.getElementById("priceRulesFilterKm").value;
  renderPriceRules();
};
document.getElementById("priceRulesFilterReset").onclick = () => {
  document.getElementById("priceRulesFilterKm").value = "";
  priceRulesKmFilter = "";
  renderPriceRules();
};

document.getElementById("btnAddPriceRule").onclick = async () => {
  const errEl = document.getElementById("priceRulesErr");
  errEl.textContent = "";
  const toptrans = shippingMethodsCache.find(m => m.pricing_mode === "zip_weight");
  if (!toptrans) { errEl.textContent = "Nenalezen způsob dopravy s výpočtem podle PSČ/hmotnosti."; return; }
  const weight = parseFloat(document.getElementById("newRuleWeight").value);
  const volumeRaw = document.getElementById("newRuleVolume").value;
  const volume = volumeRaw === "" ? null : parseFloat(volumeRaw);
  const km = parseInt(document.getElementById("newRuleKm").value, 10);
  const price = parseFloat(document.getElementById("newRulePrice").value);
  if (isNaN(weight) || isNaN(km) || isNaN(price)) { errEl.textContent = "Vyplň všechna pole."; return; }
  const r = await fetch("/api/admin/shipping-price-rules", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ shipping_method_id: toptrans.id, weight_to_kg: weight, volume_to_m3: volume, km_band: km, price_czk: price }),
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) { errEl.textContent = data.error || "Chyba."; return; }
  document.getElementById("newRuleWeight").value = "";
  document.getElementById("newRuleVolume").value = "";
  document.getElementById("newRuleKm").value = "";
  document.getElementById("newRulePrice").value = "";
  loadPriceRules();
};

// --- PSC -> vzdalenostni pasmo (shop_zip_distance_bands) ---
let zipBandsCache = [];
let zipBandsFilterQ = "";

async function loadZipBands() {
  try {
    const r = await fetch("/api/admin/shipping-zip-bands");
    const data = await r.json();
    zipBandsCache = data.zip_bands || [];
    renderZipBands();
  } catch (e) {
    document.getElementById("zipBandsErr").textContent = "Nepodařilo se načíst PSČ pásma.";
  }
}

function renderZipBands() {
  const tbody = document.getElementById("zipBandsTbody");
  const q = zipBandsFilterQ.toLowerCase();
  const rows = q
    ? zipBandsCache.filter(b => b.zip_prefix.includes(q) || (b.note || "").toLowerCase().includes(q))
    : zipBandsCache;
  document.getElementById("zipBandsSelectAll").checked = false;
  if (!rows.length) {
    tbody.innerHTML = '<tr><td colspan="5" style="color:#666;">Žádná pravidla.</td></tr>';
    updateZipBandsBulkToolbar();
    return;
  }
  tbody.innerHTML = rows.map(b => `
    <tr data-id="${b.id}">
      <td><input type="checkbox" class="zipBandChk" data-id="${b.id}"></td>
      <td>${escapeHtmlAdmin(b.zip_prefix)}</td>
      <td><input type="number" class="zip-km" value="${b.km_band}" style="width:80px;"></td>
      <td><input type="text" class="zip-note" value="${escapeHtmlAdmin(b.note || "")}" style="width:220px;"></td>
      <td>
        <button class="zip-save" data-id="${b.id}">Uložit</button>
        <button class="zip-del" data-id="${b.id}" style="background:none;border:1px solid #3a3f4a;color:#c7ccd4;">Smazat</button>
      </td>
    </tr>
  `).join("");
  tbody.querySelectorAll(".zipBandChk").forEach(chk => chk.addEventListener("change", updateZipBandsBulkToolbar));
  tbody.querySelectorAll(".zip-save").forEach(btn => {
    btn.onclick = async () => {
      const tr = btn.closest("tr");
      const body = {
        km_band: parseInt(tr.querySelector(".zip-km").value, 10),
        note: tr.querySelector(".zip-note").value.trim(),
      };
      const r = await fetch(`/api/admin/shipping-zip-bands/${btn.dataset.id}`, {
        method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
      });
      const data = await r.json().catch(() => ({}));
      if (!r.ok) { document.getElementById("zipBandsErr").textContent = data.error || "Chyba."; return; }
      loadZipBands();
    };
  });
  tbody.querySelectorAll(".zip-del").forEach(btn => {
    btn.onclick = async () => {
      if (!confirm("Opravdu smazat toto PSČ pravidlo?")) return;
      await fetch(`/api/admin/shipping-zip-bands/${btn.dataset.id}`, { method: "DELETE" });
      loadZipBands();
    };
  });
  updateZipBandsBulkToolbar();
}

function updateZipBandsBulkToolbar() {
  const checked = document.querySelectorAll(".zipBandChk:checked").length;
  const bar = document.getElementById("zipBandsBulkToolbar");
  bar.classList.toggle("active", checked > 0);
  document.getElementById("zipBandsBulkCount").textContent = `${checked} vybráno`;
}

document.getElementById("zipBandsSelectAll").onchange = (e) => {
  document.querySelectorAll(".zipBandChk").forEach(chk => { chk.checked = e.target.checked; });
  updateZipBandsBulkToolbar();
};

document.getElementById("zipBandsBulkApplyKm").onclick = async () => {
  const ids = Array.from(document.querySelectorAll(".zipBandChk:checked")).map(chk => parseInt(chk.dataset.id, 10));
  if (!ids.length) return;
  const km = parseInt(document.getElementById("zipBandsBulkKm").value, 10);
  if (isNaN(km) || km <= 0) { document.getElementById("zipBandsErr").textContent = "Zadej platné nové pásmo (km)."; return; }
  const r = await fetch("/api/admin/shipping-zip-bands/bulk-set-km", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ids, km_band: km }),
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) { document.getElementById("zipBandsErr").textContent = data.error || "Chyba."; return; }
  if (data.failed && data.failed.length) {
    alert(`Nastaveno: ${data.updated}. Nenalezeno: ${data.failed.length}.`);
  }
  document.getElementById("zipBandsBulkKm").value = "";
  loadZipBands();
};

document.getElementById("zipBandsBulkDelete").onclick = async () => {
  const ids = Array.from(document.querySelectorAll(".zipBandChk:checked")).map(chk => parseInt(chk.dataset.id, 10));
  if (!ids.length) return;
  if (!confirm(`Opravdu smazat ${ids.length} vybraných PSČ pravidel? Tuto akci nelze vrátit zpět.`)) return;
  const r = await fetch("/api/admin/shipping-zip-bands/bulk-delete", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ids }),
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) { document.getElementById("zipBandsErr").textContent = data.error || "Chyba."; return; }
  if (data.failed && data.failed.length) {
    alert(`Smazáno: ${data.deleted}. Nenalezeno: ${data.failed.length}.`);
  }
  loadZipBands();
};

document.getElementById("zipBandSearchApply").onclick = () => {
  zipBandsFilterQ = document.getElementById("zipBandSearchQ").value.trim();
  renderZipBands();
};
document.getElementById("zipBandSearchReset").onclick = () => {
  document.getElementById("zipBandSearchQ").value = "";
  zipBandsFilterQ = "";
  renderZipBands();
};

document.getElementById("btnAddZipBand").onclick = async () => {
  const errEl = document.getElementById("zipBandsErr");
  errEl.textContent = "";
  const prefix = document.getElementById("newZipPrefix").value.trim();
  const km = parseInt(document.getElementById("newZipKm").value, 10);
  const note = document.getElementById("newZipNote").value.trim();
  if (!prefix || isNaN(km)) { errEl.textContent = "Vyplň PSČ prefix a pásmo (km)."; return; }
  const r = await fetch("/api/admin/shipping-zip-bands", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ zip_prefix: prefix, km_band: km, note }),
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) { errEl.textContent = data.error || "Chyba."; return; }
  document.getElementById("newZipPrefix").value = "";
  document.getElementById("newZipKm").value = "";
  document.getElementById("newZipNote").value = "";
  loadZipBands();
};

