// ==================== ZAKAZNICI: SKUPINY (ramcova sleva) ====================
let customerGroupsCache = [];
let editingGroupId = null;
let groupsShowArchived = false;

async function loadCustomerGroups() {
  try {
    const r = await fetch(`/api/admin/customer-groups${groupsShowArchived ? "?archived=1" : ""}`);
    const data = await r.json();
    customerGroupsCache = data.groups || [];
    renderCustomerGroups();
    populateGroupSelect();
  } catch (e) {
    document.getElementById("groupsErr").textContent = "Nepodařilo se načíst skupiny.";
  }
}
document.getElementById("groupsShowArchivedBtn").onclick = () => {
  groupsShowArchived = !groupsShowArchived;
  const btn = document.getElementById("groupsShowArchivedBtn");
  btn.textContent = groupsShowArchived ? "Skrýt archivované" : "Zobrazit archivované";
  btn.style.background = groupsShowArchived ? "#3a5a7a" : "none";
  btn.style.color = groupsShowArchived ? "#fff" : "#c7ccd4";
  groupsSelectedIds.clear();
  loadCustomerGroups();
};

let groupsSelectedIds = new Set();

function renderCustomerGroups() {
  const tbody = document.getElementById("groupsTbody");
  if (!customerGroupsCache.length) {
    tbody.innerHTML = '<tr><td colspan="7" style="color:#666;">Zatím žádné skupiny.</td></tr>';
    updateGroupsBulkToolbar();
    return;
  }
  tbody.innerHTML = customerGroupsCache.map(g => `
    <tr data-id="${g.id}" style="cursor:pointer;">
      <td><input type="checkbox" class="grp-chk" data-id="${g.id}" ${groupsSelectedIds.has(g.id) ? "checked" : ""} onclick="event.stopPropagation()"></td>
      <td>${escapeHtmlAdmin(g.name)}</td>
      <td>${g.discount_percent} %</td>
      <td>${escapeHtmlAdmin(g.note || "")}</td>
      <td>${g.active ? "ano" : "ne"}</td>
      <td>${g.sort_order}</td>
      <td>
        <button type="button" class="grp-edit" data-id="${g.id}">Upravit</button>
        <button type="button" class="grp-delete danger" data-id="${g.id}">Smazat</button>
      </td>
    </tr>
  `).join("");
  tbody.querySelectorAll(".grp-edit").forEach(btn => {
    btn.onclick = (e) => { e.stopPropagation(); openGroupModal(parseInt(btn.dataset.id, 10)); };
  });
  tbody.querySelectorAll(".grp-delete").forEach(btn => {
    btn.onclick = (e) => { e.stopPropagation(); deleteGroup(parseInt(btn.dataset.id, 10)); };
  });
  tbody.querySelectorAll(".grp-chk").forEach(chk => {
    chk.onchange = () => {
      const id = parseInt(chk.dataset.id, 10);
      if (chk.checked) groupsSelectedIds.add(id); else groupsSelectedIds.delete(id);
      updateGroupsBulkToolbar();
    };
  });
  updateGroupsBulkToolbar();
  // Robert 2026-07-26: klik kdekoli na radek -> stejny detail jako "Upravit".
  tbody.querySelectorAll("tr[data-id]").forEach(tr => {
    tr.onclick = () => openGroupModal(parseInt(tr.dataset.id, 10));
  });
}

function populateGroupSelect() {
  const sel = document.getElementById("customerGroupSelect");
  if (sel) {
    sel.innerHTML = '<option value="">— bez skupiny —</option>' +
      customerGroupsCache.map(g => `<option value="${g.id}">${escapeHtmlAdmin(g.name)} (${g.discount_percent} %)</option>`).join("");
  }
  const bulkSel = document.getElementById("custBulkGroup");
  if (bulkSel) {
    bulkSel.innerHTML = '<option value="">— nastavit skupinu —</option><option value="__none__">(bez skupiny)</option>' +
      customerGroupsCache.map(g => `<option value="${g.id}">${escapeHtmlAdmin(g.name)} (${g.discount_percent} %)</option>`).join("");
  }
}

function openGroupModal(id) {
  editingGroupId = id || null;
  document.getElementById("groupModalErr").textContent = "";
  if (id) {
    const g = customerGroupsCache.find(x => x.id === id);
    document.getElementById("groupModalTitle").textContent = "Upravit skupinu";
    document.getElementById("groupName").value = g.name;
    document.getElementById("groupDiscount").value = g.discount_percent;
    document.getElementById("groupNote").value = g.note || "";
    document.getElementById("groupSortOrder").value = g.sort_order;
    document.getElementById("groupActive").checked = g.active;
  } else {
    document.getElementById("groupModalTitle").textContent = "Nová skupina";
    document.getElementById("groupName").value = "";
    document.getElementById("groupDiscount").value = 0;
    document.getElementById("groupNote").value = "";
    document.getElementById("groupSortOrder").value = 0;
    document.getElementById("groupActive").checked = true;
  }
  document.getElementById("groupModal").classList.add("open");
}

document.getElementById("btnAddGroup").onclick = () => openGroupModal(null);
document.getElementById("groupModalCancel").onclick = () => {
  document.getElementById("groupModal").classList.remove("open");
};

document.getElementById("groupModalSave").onclick = async () => {
  const errEl = document.getElementById("groupModalErr");
  errEl.textContent = "";
  const name = document.getElementById("groupName").value.trim();
  if (!name) { errEl.textContent = "Chybí název."; return; }
  const body = {
    name,
    discount_percent: parseFloat(document.getElementById("groupDiscount").value) || 0,
    note: document.getElementById("groupNote").value.trim(),
    sort_order: parseInt(document.getElementById("groupSortOrder").value, 10) || 0,
    active: document.getElementById("groupActive").checked,
  };
  const url = editingGroupId ? `/api/admin/customer-groups/${editingGroupId}` : "/api/admin/customer-groups";
  const method = editingGroupId ? "PUT" : "POST";
  const r = await fetch(url, { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const data = await r.json();
  if (!r.ok) { errEl.textContent = data.error || "Chyba."; return; }
  document.getElementById("groupModal").classList.remove("open");
  loadCustomerGroups();
};

async function deleteGroup(id) {
  if (!confirm("Smazat skupinu? Zákazníci v ní ztratí přiřazení (žádná jejich data se nesmažou).")) return;
  const r = await fetch(`/api/admin/customer-groups/${id}`, { method: "DELETE" });
  if (r.ok) { loadCustomerGroups(); loadCustomers(); }
}

function updateGroupsBulkToolbar() {
  const bar = document.getElementById("groupsBulkToolbar");
  const count = groupsSelectedIds.size;
  bar.classList.toggle("active", count > 0);
  document.getElementById("groupsBulkCount").textContent = `${count} vybráno`;
}
document.getElementById("groupsSelectAll").onchange = (e) => {
  if (e.target.checked) customerGroupsCache.forEach(g => groupsSelectedIds.add(g.id));
  else groupsSelectedIds.clear();
  renderCustomerGroups();
};
async function groupsBulkSetActive(active) {
  if (!groupsSelectedIds.size) return;
  await fetch("/api/admin/customer-groups/bulk-active", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ids: [...groupsSelectedIds], active }),
  });
  loadCustomerGroups();
}
document.getElementById("groupsBulkActivate").onclick = () => groupsBulkSetActive(true);
document.getElementById("groupsBulkDeactivate").onclick = () => groupsBulkSetActive(false);
document.getElementById("groupsBulkDelete").onclick = async () => {
  if (!groupsSelectedIds.size) return;
  if (!confirm(`Smazat ${groupsSelectedIds.size} vybraných skupin? Zákazníci v nich ztratí přiřazení (žádná jejich data se nesmažou).`)) return;
  const r = await fetch("/api/admin/customer-groups/bulk-delete", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ids: [...groupsSelectedIds] }),
  });
  const data = await r.json().catch(() => ({}));
  groupsSelectedIds.clear();
  if (!r.ok) { alert(data.error || "Chyba při mazání."); }
  loadCustomerGroups();
  loadCustomers();
};

// ==================== ZAKAZNICI: PROFILY ====================
let customersCache = [];
let editingCustomerId = null;

// Stránkování (task #78/87)
const customersPagerState = { page: 1, page_size: 50 };

async function loadCustomers() {
  const q = document.getElementById("custSearchQ").value.trim();
  const params = new URLSearchParams({
    page: customersPagerState.page, page_size: customersPagerState.page_size,
  });
  if (q) params.set("q", q);
  try {
    const r = await fetch(`/api/admin/customers?${params.toString()}`);
    const data = await r.json();
    customersCache = data.customers || [];
    renderCustomers();
    renderPager("customersPager", data, customersPagerState, loadCustomers);
  } catch (e) {
    document.getElementById("customersErr").textContent = "Nepodařilo se načíst zákazníky.";
  }
}

function renderCustomers() {
  const tbody = document.getElementById("customersTbody");
  if (!customersCache.length) {
    tbody.innerHTML = '<tr><td colspan="7" style="color:#666;">Žádní zákazníci.</td></tr>';
    return;
  }
  tbody.innerHTML = customersCache.map(c => {
    const date = c.updated_at ? new Date(c.updated_at).toLocaleString("cs-CZ") : "";
    const label = c.customer_type === "firma" ? (c.company_name || c.full_name) : c.full_name;
    return `<tr class="cust-row" data-id="${c.id}">
      <td><input type="checkbox" class="cust-chk" data-id="${c.id}" ${custSelectedIds.has(c.id) ? "checked" : ""}></td>
      <td>${escapeHtmlAdmin(label)}</td>
      <td>${escapeHtmlAdmin(c.ico || "")}</td>
      <td>${escapeHtmlAdmin(c.email)}</td>
      <td>${escapeHtmlAdmin(c.phone || "")}</td>
      <td>${c.group_name ? escapeHtmlAdmin(c.group_name) + ` (${c.group_discount_percent} %)` : "—"}</td>
      <td>${date}</td>
    </tr>`;
  }).join("");
  tbody.querySelectorAll(".cust-row").forEach(tr => {
    tr.style.cursor = "pointer";
    tr.onclick = (e) => {
      if (e.target.closest("input")) return;
      openCustomerModal(parseInt(tr.dataset.id, 10));
    };
  });
  tbody.querySelectorAll(".cust-chk").forEach(chk => {
    chk.onchange = () => {
      const id = parseInt(chk.dataset.id, 10);
      if (chk.checked) custSelectedIds.add(id); else custSelectedIds.delete(id);
      updateCustBulkToolbar();
    };
  });
}

let custSelectedIds = new Set();
function updateCustBulkToolbar() {
  const bar = document.getElementById("custBulkToolbar");
  const count = custSelectedIds.size;
  bar.classList.toggle("active", count > 0);
  document.getElementById("custBulkCount").textContent = `${count} vybráno`;
}
document.getElementById("custSelectAll").onchange = (e) => {
  if (e.target.checked) customersCache.forEach(c => custSelectedIds.add(c.id));
  else custSelectedIds.clear();
  renderCustomers();
  updateCustBulkToolbar();
};
document.getElementById("custBulkApplyGroup").onclick = async () => {
  if (!custSelectedIds.size) return;
  const val = document.getElementById("custBulkGroup").value;
  if (val === "") return;
  const group_id = val === "__none__" ? null : parseInt(val, 10);
  await fetch("/api/admin/customers/bulk-group", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ids: [...custSelectedIds], group_id }),
  });
  loadCustomers();
};
document.getElementById("custBulkDelete").onclick = async () => {
  if (!custSelectedIds.size) return;
  if (!confirm(`Opravdu smazat ${custSelectedIds.size} vybraných zákazníků? Tuto akci nelze vrátit zpět.`)) return;
  const r = await fetch("/api/admin/customers/bulk", {
    method: "DELETE", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ids: [...custSelectedIds] }),
  });
  const data = await r.json().catch(() => ({}));
  custSelectedIds.clear();
  if (data.failed && data.failed.length) {
    alert(`Smazáno: ${data.deleted}. Nešlo smazat: ${data.failed.length}.`);
  }
  loadCustomers();
};

document.getElementById("custSearchApply").onclick = () => { customersPagerState.page = 1; loadCustomers(); };
document.getElementById("custSearchReset").onclick = () => {
  document.getElementById("custSearchQ").value = "";
  customersPagerState.page = 1;
  loadCustomers();
};

async function openCustomerModal(id) {
  editingCustomerId = id;
  const c = customersCache.find(x => x.id === id);
  if (!c) return;
  document.getElementById("customerModalErr").textContent = "";
  document.getElementById("customerModalTitle").textContent = `Zákazník: ${c.account_email}`;
  document.getElementById("custType").value = c.customer_type;
  document.getElementById("custFullName").value = c.full_name || "";
  document.getElementById("custCompanyName").value = c.company_name || "";
  document.getElementById("custIco").value = c.ico || "";
  document.getElementById("custDic").value = c.dic || "";
  document.getElementById("custEmail").value = c.email || "";
  document.getElementById("custPhone").value = c.phone || "";
  document.getElementById("custBillingAddress").value = c.billing_address || "";
  document.getElementById("custBillingZip").value = c.billing_zip || "";
  document.getElementById("custDeliveryAddress").value = c.delivery_address || "";
  document.getElementById("custDeliveryZip").value = c.delivery_zip || "";
  // Robert 2026-08-07: "veškeré tyto údaje z objednávky zákazníkovi
  // sepisují do karty zákazníka" - PSC/checkbox "stejna jako
  // fakturacni" ted uz zakaznicky checkout uklada (viz webapp/index.html
  // atd., commit 75efcac), tenhle modal je musel doplnit, jinak by je
  // pri kazde admin editaci tise vynuloval (viz _validate_and_clean).
  // Stary zakaznik bez vlastni dodaci adresy se bere jako "stejna".
  const hasOwnDeliveryData = !!(c.delivery_address || c.delivery_zip);
  document.getElementById("custDeliverySame").checked = !hasOwnDeliveryData || !!c.delivery_same_as_billing;
  toggleCustDeliveryFields();
  document.getElementById("customerGroupSelect").value = c.group_id || "";
  document.getElementById("customerModal").classList.add("open");
  // bot5, 2026-09-29 (Robert pres bot3: "vicero dodacich adres") -
  // adresar se nacita AZ TADY (samostatny fetch, ne z customersCache
  // ze seznamu) - viz api/customers.py::admin_customers_get.
  document.getElementById("custAddressesSection").style.display = "";
  await loadCustomerAddresses(id);
}

// ==================== ZAKAZNICI: ADRESAR (Robert pres bot3, 2026-09-29
// "u zakazniku potrebujeme mit moznost vicero dodacich adres, asi na
// zalozky") - jednoducha editovatelna tabulka misto zalozek (adresar
// je typicky kratky seznam, tabulka je pro to prirozenejsi/rychlejsi
// na zorientovani nez prepinani mezi zalozkami jedne polozky). ====
let customerAddressesCache = [];
let editingAddressId = null;

async function loadCustomerAddresses(customerId) {
  try {
    const r = await fetch(`/api/admin/customers/${customerId}`);
    const data = await r.json();
    customerAddressesCache = (data.addresses || []);
    renderCustomerAddresses();
  } catch (e) {
    customerAddressesCache = [];
    renderCustomerAddresses();
  }
}

function renderCustomerAddresses() {
  const tbody = document.getElementById("custAddressesTbody");
  if (!customerAddressesCache.length) {
    tbody.innerHTML = '<tr><td style="color:#666;font-size:12.5px;padding:4px 0;">Zatím žádná uložená adresa.</td></tr>';
    return;
  }
  tbody.innerHTML = customerAddressesCache.map(a => {
    const line = [a.street, [a.zip, a.city].filter(Boolean).join(" ")].filter(Boolean).join(", ");
    return `<tr data-id="${a.id}">
      <td style="padding:4px 6px 4px 0;">
        <b>${escapeHtmlAdmin(a.label)}</b>${a.is_default ? ' <span style="color:var(--accent);font-size:11px;">(výchozí)</span>' : ""}
        <div style="color:#9aa4b2;font-size:12px;">${escapeHtmlAdmin(line || "—")}</div>
      </td>
      <td style="text-align:right;white-space:nowrap;font-size:12px;">
        ${a.is_default ? "" : `<a href="#" class="ca-set-default" data-id="${a.id}">Nastavit výchozí</a> · `}
        <a href="#" class="ca-edit" data-id="${a.id}">Upravit</a> ·
        <a href="#" class="ca-delete" data-id="${a.id}">Smazat</a>
      </td>
    </tr>`;
  }).join("");
  tbody.querySelectorAll(".ca-set-default").forEach(a => {
    a.onclick = async (e) => {
      e.preventDefault();
      await saveCustomerAddress(parseInt(a.dataset.id, 10), { is_default: true });
    };
  });
  tbody.querySelectorAll(".ca-edit").forEach(a => {
    a.onclick = (e) => {
      e.preventDefault();
      openAddressForm(customerAddressesCache.find(x => x.id === parseInt(a.dataset.id, 10)));
    };
  });
  tbody.querySelectorAll(".ca-delete").forEach(a => {
    a.onclick = async (e) => {
      e.preventDefault();
      const addr = customerAddressesCache.find(x => x.id === parseInt(a.dataset.id, 10));
      if (!confirm(`Smazat adresu „${addr ? addr.label : ""}“?`)) return;
      const r = await fetch(`/api/admin/customers/addresses/${a.dataset.id}`, { method: "DELETE" });
      const data = await r.json().catch(() => ({}));
      if (!r.ok) { alert(data.error || "Smazání se nezdařilo."); return; }
      await loadCustomerAddresses(editingCustomerId);
    };
  });
}

function openAddressForm(addr) {
  editingAddressId = addr ? addr.id : null;
  document.getElementById("custAddrFormErr").textContent = "";
  document.getElementById("custAddrLabel").value = addr ? addr.label : "";
  document.getElementById("custAddrStreet").value = addr ? (addr.street || "") : "";
  document.getElementById("custAddrCity").value = addr ? (addr.city || "") : "";
  document.getElementById("custAddrZip").value = addr ? (addr.zip || "") : "";
  document.getElementById("custAddrIsDefault").checked = addr ? !!addr.is_default : false;
  document.getElementById("custAddressAddForm").style.display = "";
}
document.getElementById("custAddressAddBtn").onclick = () => openAddressForm(null);
document.getElementById("custAddrFormCancel").onclick = () => {
  document.getElementById("custAddressAddForm").style.display = "none";
};

async function saveCustomerAddress(addressId, body) {
  const r = await fetch(`/api/admin/customers/addresses/${addressId}`, {
    method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) { alert(data.error || "Uložení se nezdařilo."); return; }
  await loadCustomerAddresses(editingCustomerId);
}

document.getElementById("custAddrFormSave").onclick = async () => {
  const errEl = document.getElementById("custAddrFormErr");
  errEl.textContent = "";
  const body = {
    label: document.getElementById("custAddrLabel").value.trim(),
    street: document.getElementById("custAddrStreet").value.trim(),
    city: document.getElementById("custAddrCity").value.trim(),
    zip: document.getElementById("custAddrZip").value.trim(),
    is_default: document.getElementById("custAddrIsDefault").checked,
  };
  if (!body.label) { errEl.textContent = "Zadej název adresy."; return; }
  const url = editingAddressId
    ? `/api/admin/customers/addresses/${editingAddressId}`
    : `/api/admin/customers/${editingCustomerId}/addresses`;
  const r = await fetch(url, {
    method: editingAddressId ? "PUT" : "POST",
    headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) { errEl.textContent = data.error || "Uložení se nezdařilo."; return; }
  document.getElementById("custAddressAddForm").style.display = "none";
  await loadCustomerAddresses(editingCustomerId);
};

function toggleCustDeliveryFields() {
  document.getElementById("custDeliveryFields").style.display =
    document.getElementById("custDeliverySame").checked ? "none" : "";
}
document.getElementById("custDeliverySame").onchange = toggleCustDeliveryFields;

document.getElementById("customerModalCancel").onclick = () => {
  document.getElementById("customerModal").classList.remove("open");
};

document.getElementById("customerModalDelete").onclick = async () => {
  if (!editingCustomerId) return;
  const c = customersCache.find(x => x.id === editingCustomerId);
  const label = c ? (c.company_name || c.full_name || c.email) : "tohoto zákazníka";
  if (!confirm(`Opravdu smazat zákazníka „${label}“? Tuto akci nelze vrátit zpět.`)) return;
  const errEl = document.getElementById("customerModalErr");
  errEl.textContent = "";
  const r = await fetch(`/api/admin/customers/${editingCustomerId}`, { method: "DELETE" });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) { errEl.textContent = data.error || "Chyba při mazání."; return; }
  document.getElementById("customerModal").classList.remove("open");
  loadCustomers();
};

document.getElementById("customerModalSave").onclick = async () => {
  if (!editingCustomerId) return;
  const errEl = document.getElementById("customerModalErr");
  errEl.textContent = "";
  const groupVal = document.getElementById("customerGroupSelect").value;
  const body = {
    customer_type: document.getElementById("custType").value,
    full_name: document.getElementById("custFullName").value.trim(),
    company_name: document.getElementById("custCompanyName").value.trim(),
    ico: document.getElementById("custIco").value.trim(),
    dic: document.getElementById("custDic").value.trim(),
    email: document.getElementById("custEmail").value.trim(),
    phone: document.getElementById("custPhone").value.trim(),
    billing_address: document.getElementById("custBillingAddress").value.trim(),
    billing_zip: document.getElementById("custBillingZip").value.trim(),
    delivery_same_as_billing: document.getElementById("custDeliverySame").checked,
    delivery_address: document.getElementById("custDeliverySame").checked ? "" : document.getElementById("custDeliveryAddress").value.trim(),
    delivery_zip: document.getElementById("custDeliverySame").checked ? "" : document.getElementById("custDeliveryZip").value.trim(),
    group_id: groupVal ? parseInt(groupVal, 10) : null,
  };
  const r = await fetch(`/api/admin/customers/${editingCustomerId}`, {
    method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
  const data = await r.json();
  if (!r.ok) { errEl.textContent = data.error || "Chyba."; return; }
  document.getElementById("customerModal").classList.remove("open");
  loadCustomers();
};

// ==================== ZAKAZNICI: KOSIKY (Robert: "chci jako admin videt vsechno tzn i kosik") ====================
let cartsCache = [];

async function loadAdminCarts() {
  try {
    const r = await fetch("/api/admin/carts");
    const data = await r.json();
    cartsCache = data.carts || [];
    renderAdminCarts();
  } catch (e) {
    document.getElementById("cartsErr").textContent = "Nepodařilo se načíst košíky.";
  }
}

let cartsSelectedIds = new Set();

function renderAdminCarts() {
  const tbody = document.getElementById("cartsTbody");
  if (!cartsCache.length) {
    tbody.innerHTML = '<tr><td colspan="7" style="color:#666;">Žádné aktivní košíky.</td></tr>';
    updateCartsBulkToolbar();
    return;
  }
  tbody.innerHTML = cartsCache.map(c => {
    const date = c.updated_at ? new Date(c.updated_at).toLocaleString("cs-CZ") : "";
    return `<tr data-uid="${c.user_id}" style="cursor:pointer;">
      <td><input type="checkbox" class="cart-chk" data-uid="${c.user_id}" ${cartsSelectedIds.has(c.user_id) ? "checked" : ""} onclick="event.stopPropagation()"></td>
      <td>${escapeHtmlAdmin(c.user_name || "")}</td>
      <td>${escapeHtmlAdmin(c.user_email)}</td>
      <td>${c.items.length}</td>
      <td>${c.total_qty}</td>
      <td>${c.subtotal_czk.toLocaleString("cs-CZ")} Kč</td>
      <td>${date} <button type="button" class="cart-detail-btn" data-uid="${c.user_id}">Detail</button></td>
    </tr>`;
  }).join("");
  tbody.querySelectorAll(".cart-detail-btn").forEach(btn => {
    btn.onclick = (e) => { e.stopPropagation(); openCartDetail(parseInt(btn.dataset.uid, 10)); };
  });
  tbody.querySelectorAll(".cart-chk").forEach(chk => {
    chk.onchange = () => {
      const uid = parseInt(chk.dataset.uid, 10);
      if (chk.checked) cartsSelectedIds.add(uid); else cartsSelectedIds.delete(uid);
      updateCartsBulkToolbar();
    };
  });
  updateCartsBulkToolbar();
  // Robert 2026-07-26: klik kdekoli na radek -> stejny detail jako "Detail".
  tbody.querySelectorAll("tr[data-uid]").forEach(tr => {
    tr.onclick = (e) => {
      if (e.target.closest("input")) return;
      openCartDetail(parseInt(tr.dataset.uid, 10));
    };
  });
}

function updateCartsBulkToolbar() {
  const bar = document.getElementById("cartsBulkToolbar");
  const count = cartsSelectedIds.size;
  bar.classList.toggle("active", count > 0);
  document.getElementById("cartsBulkCount").textContent = `${count} vybráno`;
}
document.getElementById("cartsSelectAll").onchange = (e) => {
  if (e.target.checked) cartsCache.forEach(c => cartsSelectedIds.add(c.user_id));
  else cartsSelectedIds.clear();
  renderAdminCarts();
};
document.getElementById("cartsBulkClear").onclick = async () => {
  if (!cartsSelectedIds.size) return;
  if (!confirm(`Opravdu vyprázdnit košík ${cartsSelectedIds.size} vybraných zákazníků? Zákazník může v košíku právě nakupovat - tuto akci nelze vrátit zpět.`)) return;
  const r = await fetch("/api/admin/carts/bulk-clear", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ids: [...cartsSelectedIds] }),
  });
  const data = await r.json().catch(() => ({}));
  cartsSelectedIds.clear();
  if (!r.ok) { alert(data.error || "Chyba při mazání."); }
  loadAdminCarts();
};

function openCartDetail(userId) {
  const c = cartsCache.find(x => x.user_id === userId);
  if (!c) return;
  document.getElementById("cartDetailTitle").textContent = `Košík: ${c.user_name || c.user_email}`;
  document.getElementById("cartDetailItems").innerHTML = c.items.map(i => {
    const warn = (!i.active || i.is_archived) ? ' <span style="color:#e07070;">(nedostupné)</span>'
      : (i.stock_qty < i.qty ? ` <span style="color:#e0a070;">(skladem jen ${i.stock_qty})</span>` : "");
    return `<tr>
      <td>${escapeHtmlAdmin(i.name)}${warn}</td>
      <td>${escapeHtmlAdmin(i.sku)}</td>
      <td>${i.qty}</td>
      <td>${i.unit_price_czk.toLocaleString("cs-CZ")} Kč</td>
      <td>${i.line_total_czk.toLocaleString("cs-CZ")} Kč</td>
    </tr>`;
  }).join("");
  document.getElementById("cartDetailModal").classList.add("open");
}

document.getElementById("cartDetailClose").onclick = () => {
  document.getElementById("cartDetailModal").classList.remove("open");
};

// ==================== ZAKAZNICI: RUCNI PRIDANI (Robert: "zakaznik lze pridat i rucne") ====================
function populateNewCustomerGroupSelect() {
  const sel = document.getElementById("newCustGroupSelect");
  sel.innerHTML = '<option value="">— bez skupiny —</option>' +
    customerGroupsCache.map(g => `<option value="${g.id}">${escapeHtmlAdmin(g.name)} (${g.discount_percent} %)</option>`).join("");
}

// Robert (V9, 2026-07-26): "zvlast PSC, zvlast Mesto i Ulici, zatrzitko
// na stejnou dodaci adresu s fakturacni, vsechna pole povinna krome
// poznamky, u firmy jmeno zaznacit interne ze se nema prenaset do
// faktury a na doklady" - viditelnost "Nazev firmy"/"nepřenášet jméno"
// podle typu zakaznika, viditelnost dodaci adresy podle zatrzitka.
function ncmUpdateTypeVisibility() {
  const isFirma = document.getElementById("newCustType").value === "firma";
  document.getElementById("newCustHideNameWrap").style.display = isFirma ? "" : "none";
}
function ncmUpdateDeliveryVisibility() {
  const same = document.getElementById("newCustDeliverySame").checked;
  document.getElementById("newCustDeliveryFields").style.display = same ? "none" : "";
}
document.getElementById("newCustType").onchange = ncmUpdateTypeVisibility;
document.getElementById("newCustDeliverySame").onchange = ncmUpdateDeliveryVisibility;

document.getElementById("btnAddCustomer").onclick = () => {
  document.getElementById("newCustomerModalErr").textContent = "";
  document.getElementById("newCustEmail").value = "";
  document.getElementById("newCustAccountName").value = "";
  document.getElementById("newCustType").value = "osoba";
  document.getElementById("newCustFullName").value = "";
  document.getElementById("newCustCompanyName").value = "";
  document.getElementById("newCustHideName").checked = true;
  document.getElementById("newCustIco").value = "";
  document.getElementById("newCustDic").value = "";
  document.getElementById("newCustPhone").value = "";
  document.getElementById("newCustBillingStreet").value = "";
  document.getElementById("newCustBillingCity").value = "";
  document.getElementById("newCustBillingZip").value = "";
  document.getElementById("newCustDeliverySame").checked = true;
  document.getElementById("newCustDeliveryStreet").value = "";
  document.getElementById("newCustDeliveryCity").value = "";
  document.getElementById("newCustDeliveryZip").value = "";
  document.getElementById("newCustNote").value = "";
  ncmUpdateTypeVisibility();
  ncmUpdateDeliveryVisibility();
  populateNewCustomerGroupSelect();
  document.getElementById("newCustGroupSelect").value = "";
  document.getElementById("newCustomerModal").classList.add("open");
};

document.getElementById("newCustomerModalCancel").onclick = () => {
  document.getElementById("newCustomerModal").classList.remove("open");
};

document.getElementById("newCustomerModalSave").onclick = async () => {
  const errEl = document.getElementById("newCustomerModalErr");
  errEl.textContent = "";

  const val = (id) => document.getElementById(id).value.trim();
  const customerType = val("newCustType");
  const deliverySame = document.getElementById("newCustDeliverySame").checked;

  // Klientska validace "vsechna pole povinna krome poznamky" - server
  // (_require_all_fields v api/customers.py) overuje totez, tohle je
  // jen rychla zpetna vazba bez odeslani requestu.
  const missing = [];
  if (!val("newCustEmail")) missing.push("e-mail");
  if (!val("newCustFullName")) missing.push("jméno a příjmení");
  if (customerType === "firma" && !val("newCustCompanyName")) missing.push("název firmy");
  if (!val("newCustPhone")) missing.push("telefon");
  if (!val("newCustBillingStreet")) missing.push("ulice (fakturační)");
  if (!val("newCustBillingCity")) missing.push("město (fakturační)");
  if (!val("newCustBillingZip")) missing.push("PSČ (fakturační)");
  if (!deliverySame) {
    if (!val("newCustDeliveryStreet")) missing.push("ulice (dodací)");
    if (!val("newCustDeliveryCity")) missing.push("město (dodací)");
    if (!val("newCustDeliveryZip")) missing.push("PSČ (dodací)");
  }
  if (missing.length) { errEl.textContent = "Chybí povinné údaje: " + missing.join(", ") + "."; return; }

  const groupVal = document.getElementById("newCustGroupSelect").value;
  const body = {
    email: val("newCustEmail"),
    account_name: val("newCustAccountName"),
    customer_type: customerType,
    full_name: val("newCustFullName"),
    company_name: val("newCustCompanyName"),
    hide_name_on_documents: customerType === "firma" ? document.getElementById("newCustHideName").checked : false,
    ico: val("newCustIco"),
    dic: val("newCustDic"),
    phone: val("newCustPhone"),
    billing_street: val("newCustBillingStreet"),
    billing_city: val("newCustBillingCity"),
    billing_zip: val("newCustBillingZip"),
    delivery_same_as_billing: deliverySame,
    delivery_street: deliverySame ? "" : val("newCustDeliveryStreet"),
    delivery_city: deliverySame ? "" : val("newCustDeliveryCity"),
    delivery_zip: deliverySame ? "" : val("newCustDeliveryZip"),
    note: val("newCustNote"),
    group_id: groupVal ? parseInt(groupVal, 10) : undefined,
  };

  const btn = document.getElementById("newCustomerModalSave");
  btn.disabled = true;
  btn.textContent = "Vytvářím…";
  try {
    const r = await fetch("/api/admin/customers", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    });
    const data = await r.json();
    if (!r.ok) { errEl.textContent = data.error || "Chyba."; return; }
    document.getElementById("newCustomerModal").classList.remove("open");
    loadCustomers();
  } catch (e) {
    errEl.textContent = "Zákazníka se nepodařilo vytvořit (chyba spojení).";
  } finally {
    btn.disabled = false;
    btn.textContent = "Vytvořit";
  }
};

// ==================== ZAKAZNICI: SMAZAT VSE ====================
// Robert 2026-07-25: "potřebujeme tlačítka v zakaznikách: smazat vše" -
// potvrzeno, ze cilem jsou profily/ucty zakazniku. Nevratna akce, proto
// vyzaduje presne napsani aktualniho poctu zakazniku pred povolenim tlacitka.
document.getElementById("btnDeleteAllCustomers").onclick = () => {
  const errEl = document.getElementById("deleteAllCustomersModalErr");
  errEl.textContent = "";
  const count = customersCache.length;
  document.getElementById("delAllCustCount").textContent = count;
  document.getElementById("delAllCustCount2").textContent = count;
  document.getElementById("delAllCustConfirmInput").value = "";
  document.getElementById("deleteAllCustomersModalConfirm").disabled = true;
  document.getElementById("deleteAllCustomersModal").classList.add("open");
};

document.getElementById("delAllCustConfirmInput").addEventListener("input", () => {
  const val = document.getElementById("delAllCustConfirmInput").value.trim();
  document.getElementById("deleteAllCustomersModalConfirm").disabled = (val !== String(customersCache.length));
});

document.getElementById("deleteAllCustomersModalCancel").onclick = () => {
  document.getElementById("deleteAllCustomersModal").classList.remove("open");
};

document.getElementById("deleteAllCustomersModalConfirm").onclick = async () => {
  const errEl = document.getElementById("deleteAllCustomersModalErr");
  errEl.textContent = "";
  const count = customersCache.length;
  const btn = document.getElementById("deleteAllCustomersModalConfirm");
  btn.disabled = true;
  btn.textContent = "Mažu…";
  try {
    const r = await fetch("/api/admin/customers", {
      method: "DELETE", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ confirm_count: count }),
    });
    const data = await r.json();
    if (!r.ok) {
      errEl.textContent = data.error || "Chyba při mazání.";
      if (typeof data.current_count === "number") {
        document.getElementById("delAllCustCount").textContent = data.current_count;
        document.getElementById("delAllCustCount2").textContent = data.current_count;
      }
      return;
    }
    document.getElementById("deleteAllCustomersModal").classList.remove("open");
    loadCustomers();
  } catch (e) {
    errEl.textContent = "Nepodařilo se smazat zákazníky (chyba spojení).";
  } finally {
    const val = document.getElementById("delAllCustConfirmInput").value.trim();
    btn.disabled = (val !== String(customersCache.length));
    btn.textContent = "Smazat vše";
  }
};
