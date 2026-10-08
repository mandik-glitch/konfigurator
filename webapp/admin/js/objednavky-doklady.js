// ==================== OBJEDNAVKY ====================
const ORDER_STATUS_LABELS = {
  nova: "Nová", potvrzena: "Potvrzená", ceka_na_zbozi: "Čeká na zboží",
  pripravit: "Připravit", expedovana: "Expedovaná", fakturovana: "Fakturovaná", zrusena: "Zrušená",
};
// bot16, 2026-09-17 (Robert primo, presne vybrano) - sdileno mezi taby
// (renderOrderStatusTabs) i vlastnim sloupcem "Stav" ikony v tabulce
// (renderOrdersTable) - jedno misto pravdy pro obe pouziti. Barvy k
// nim viz .order-status-pill.* / .order-tab-btn.status-* v admin.html.
const ORDER_STATUS_ICONS = {
  nova: "○", potvrzena: "✓", ceka_na_zbozi: "⏳", pripravit: "⚙",
  expedovana: "🚚", fakturovana: "▤", zrusena: "✕",
};
const ORDER_URGENT_ICON = "⚠";
const ORDER_ALLOWED_TRANSITIONS = {
  nova: ["potvrzena", "ceka_na_zbozi", "zrusena"],
  ceka_na_zbozi: ["potvrzena", "zrusena"],
  potvrzena: ["pripravit", "zrusena"],
  pripravit: ["expedovana", "zrusena"],
  // Robert (pres bot3, revize kodu 2026-09-03): zruseni z expedovane uz
  // neni povolene (viz stejna zmena v api/orders.py ALLOWED_TRANSITIONS) -
  // tenhle seznam je NEZAVISLA kopie pro UI (nectena z backend odpovedi),
  // musi se udrzovat rucne synchronni.
  expedovana: ["fakturovana"],
  fakturovana: [],
  zrusena: [],
};
// bot5, 2026-09-17 (Robert primo: "udelejme to v tabulce objednavek tak,
// ze to preklapeni se bude nabizet jako dynamicke tlacitko v kazdem
// radku objednavky podle stavu, skladnik/admin si to rucne odklikneme" +
// "klikam, meni se barva a text tlacitka") - jen PRIMARNI dopredny krok
// (ne "zrusena" - zruseni zustava zamerne jen v modalu, at ho nejde
// omylem trefit rychlym klikem v seznamu). Prvni polozka z
// ORDER_ALLOWED_TRANSITIONS krome "zrusena".
const ORDER_NEXT_STATUS = {
  nova: "potvrzena", ceka_na_zbozi: "potvrzena", potvrzena: "pripravit",
  pripravit: "expedovana", expedovana: "fakturovana", fakturovana: null, zrusena: null,
};
let orderFilter = {
  status: "", urgent: false, q: "", date_from: "", date_to: "",
  shipping_method: "", payment_method: "", price_min: "", price_max: "", has_account: "", origin: "",
  // Stránkování (task #78/87) - stejny objekt jako ostatni filtry, page se
  // resetuje na 1 pri kazde zmene filtru/tabu (viz nize).
  page: 1, page_size: 50,
};
let ordersCache = [];
let currentOrderId = null;

async function loadOrders() {
  const params = new URLSearchParams({ page: orderFilter.page, page_size: orderFilter.page_size });
  if (orderFilter.status) params.set("status", orderFilter.status);
  if (orderFilter.urgent) params.set("urgent", "1");
  if (orderFilter.q) params.set("q", orderFilter.q);
  if (orderFilter.date_from) params.set("date_from", orderFilter.date_from);
  if (orderFilter.date_to) params.set("date_to", orderFilter.date_to);
  if (orderFilter.shipping_method) params.set("shipping_method", orderFilter.shipping_method);
  if (orderFilter.payment_method) params.set("payment_method", orderFilter.payment_method);
  if (orderFilter.price_min !== "") params.set("price_min", orderFilter.price_min);
  if (orderFilter.price_max !== "") params.set("price_max", orderFilter.price_max);
  if (orderFilter.has_account !== "") params.set("has_account", orderFilter.has_account);
  if (orderFilter.origin) params.set("origin", orderFilter.origin);
  if (orderFilter.shipping_review) params.set("shipping_review", "1");      // puvod: eshop | <host mini-shopu> (bot5: order_host/order_lang)
  try {
    const r = await fetch(`/api/admin/orders?${params.toString()}`);
    const data = await r.json();
    if (!r.ok) { document.getElementById("ordersErr").textContent = data.error || "Chyba."; return; }
    ordersCache = data.orders || [];
    fillOriginFilter(data.origins);
    renderOrderStatusTabs(data.counts || {});
    renderOrdersTable(ordersCache);
    renderPager("ordersPager", data, orderFilter, loadOrders);
  } catch (e) {
    document.getElementById("ordersErr").textContent = "Nepodařilo se načíst objednávky.";
  }
}

// Puvod objednavky (Robert 2026-10-03: mini-shopy vytvari objednavky v hlavnim adminu, sloupec "Puvod" = mini-shop + jazyk, hlavni e-shop = "e-shop";
// data order_host/order_lang z API bot5, dokud je nema, je to "e-shop")
function orderOriginLabel(o) {
  if (o.origin_label) return o.origin_label;
  if (o.order_host) return o.order_host.replace(/^www\./, "") + (o.order_lang ? " · " + o.order_lang : "");
  return "e-shop";
}
function fillOriginFilter(origins) {                   // moznosti filtru = puvody, ktere API zna ([{key, label}]); vybrana hodnota se zachova
  const sel = document.getElementById("orderFilterOrigin");
  if (!sel || !Array.isArray(origins)) return;
  const cur = sel.value;
  sel.innerHTML = '<option value="">Původ: vše</option><option value="eshop">e-shop</option>' + origins.filter(x => x && x.key && x.key !== "eshop").map(x => `<option value="${escapeHtmlAdmin(x.key)}">${escapeHtmlAdmin(x.label || x.key)}</option>`).join("");
  sel.value = cur;
}

function renderOrderStatusTabs(counts) {
  const defs = [
    { key: "", label: "Všechny", count: counts.all ?? 0, urgent: false },
    { key: "nova", label: "Nová", count: counts.nova ?? 0, urgent: false },
    { key: "potvrzena", label: "Potvrzená", count: counts.potvrzena ?? 0, urgent: false },
    { key: "ceka_na_zbozi", label: "Čeká na zboží", count: counts.ceka_na_zbozi ?? 0, urgent: false },
    { key: "pripravit", label: "Připravit", count: counts.pripravit ?? 0, urgent: false },
    { key: "expedovana", label: "Expedovaná", count: counts.expedovana ?? 0, urgent: false },
    { key: "fakturovana", label: "Fakturovaná", count: counts.fakturovana ?? 0, urgent: false },
    { key: "zrusena", label: "Zrušená", count: counts.zrusena ?? 0, urgent: false },
    { key: "__urgent__", label: "Urgentní", count: counts.urgent ?? 0, urgent: true },
    { key: "__shipreview__", label: "Doprava ke schválení", count: counts.shipping_review ?? 0, urgent: false, shipReview: true },
  ];
  const wrap = document.getElementById("orderStatusTabs");
  wrap.innerHTML = defs.map(d => {
    const active = d.shipReview ? !!orderFilter.shipping_review : (d.urgent ? orderFilter.urgent : (!orderFilter.urgent && !orderFilter.shipping_review && orderFilter.status === d.key));
    // bot16, 2026-09-17 (Robert primo) - barva/ikona podle stavu (viz
    // ORDER_STATUS_ICONS + .order-tab-btn.status-* v admin.html), "Vsechny"
    // beze zmeny (zadny jednotlivy stav, zadna barva).
    const statusCls = d.urgent ? " status-urgent" : (d.key ? ` status-${d.key}` : "");
    const icon = d.urgent ? ORDER_URGENT_ICON : ORDER_STATUS_ICONS[d.key];
    const iconHtml = icon ? `<em>${icon}</em> ` : "";
    return `<button type="button" class="order-tab-btn${active ? " active" : ""}${statusCls}" data-key="${d.key}" data-urgent="${d.urgent ? 1 : 0}" data-shipreview="${d.shipReview ? 1 : 0}">${iconHtml}${escapeHtmlAdmin(d.label)}<span class="otc">(${d.count})</span></button>`;
  }).join("");
  wrap.querySelectorAll(".order-tab-btn").forEach(btn => {
    btn.onclick = () => {
      if (btn.dataset.shipreview === "1") {
        orderFilter.shipping_review = !orderFilter.shipping_review;
      } else if (btn.dataset.urgent === "1") {
        orderFilter.urgent = !orderFilter.urgent;
      } else {
        orderFilter.status = btn.dataset.key;
        orderFilter.urgent = false;
        orderFilter.shipping_review = false;
      }
      orderFilter.page = 1;
      loadOrders();
    };
  });
}

function renderOrdersTable(orders) {
  const tbody = document.getElementById("ordersTbody");

  // Dynamicky tolik sloupcu "Faktura N", kolik ma NEJVIC faktur jedna
  // objednavka na AKTUALNI strance (Robert 2026-08-22: "pokud je k
  // objednávce více faktur, přibudou další sloupce") - ne pevny strop.
  // Hlavicka se prekresluje pri KAZDEM renderu (meni se s filtrem/
  // strankou) - initColumnResizers() (bot11) uz ma vlastni ochranu
  // proti neplatnym ulozenym sirkam pri zmene poctu sloupcu (zahodi
  // cely ulozeny zaznam, kdyz index sedi mimo aktualni pocet bunek),
  // takze prehazeni poctu Faktura-sloupcu mezi strankami nezpusobi
  // rozbite/posunute sirky - nejhorsi dopad je, ze se u teto tabulky
  // obcas zapomene rucne nastavena sirka, ne ze by se prihodila
  // spatnemu sloupci.
  const maxInvoices = orders.reduce((m, o) => Math.max(m, (o.invoices || []).length), 0);
  const invoiceHeaders = Array.from({ length: maxInvoices }, (_, i) => `<th>Faktura ${i + 1}</th>`).join("");
  document.getElementById("ordersTblHeadRow").innerHTML =
    `<th><input type="checkbox" id="orderSelectAll"></th>
     <th>Číslo</th><th>Původ</th><th>Zákazník</th><th>Částka</th><th>Uhrazeno</th><th title="Ikona stavu"></th><th>Stav</th><th></th><th>Urgentní</th>${invoiceHeaders}<th>Datum</th>`;
  document.getElementById("orderSelectAll").onchange = (e) => {
    if (e.target.checked) ordersCache.forEach(o => orderSelectedIds.add(o.id));
    else orderSelectedIds.clear();
    renderOrdersTable(ordersCache);
    updateOrderBulkToolbar();
  };

  const totalCols = 11 + maxInvoices;
  if (!orders.length) {
    tbody.innerHTML = `<tr><td colspan="${totalCols}" style="color:#666;">Žádné objednávky.</td></tr>`;
    return;
  }
  tbody.innerHTML = orders.map(o => {
    const date = new Date(o.created_at).toLocaleString("cs-CZ");
    // bot10, 2026-08-22 (Robert: "uhrazená/neuhrazená a uhrazená kdy",
    // párovací znak VS - viz api/bank_statements.py::match_bank_payments_to_orders)
    // bot5, 2026-09-28 (Robert primo: "platbu jsem oznacil za přijatou,
    // vytvořil se doklad k platbě, ale v přehledu je objednávka jako
    // neuhrazená") - sloupec cetl JEN bank_paid (automaticke parovani
    // vypisu). Rucni potvrzeni platby (tlacitko "Označit platbu jako
    // přijatou", muze byt i BEZ shody VS - viz api/documents.py
    // can_mark_payment) se ukladalo jen do payment_received_at/_total,
    // sloupec o tom nevedel. Ted bere OBOJI - plne uhrazeno = bud
    // bank_paid, nebo rucne potvrzena castka >= total_czk.
    const manualFullyPaid = o.payment_received_total_czk != null
      && o.payment_received_total_czk >= o.total_czk - 0.01;
    const bankPaidCell = (o.bank_paid || manualFullyPaid)
      ? `<span class="order-status-pill fakturovana" title="${o.bank_paid ? 'Uhrazeno (bankovní převod, párováno podle VS)' : 'Uhrazeno (potvrzeno ručně)'}">✓ ${escapeHtmlAdmin(new Date(o.bank_paid ? o.bank_paid_at : o.payment_received_at).toLocaleDateString("cs-CZ"))}</span>`
      : (o.payment_received_total_czk > 0
          ? `<span style="color:#d9a441;" title="Přijata jen část platby">Částečně uhrazeno</span>`
          : '<span style="color:#666;">Neuhrazeno</span>');
    const invoiceCells = Array.from({ length: maxInvoices }, (_, i) => {
      const inv = (o.invoices || [])[i];
      return `<td>${inv ? `<a href="#" class="order-invoice-link" data-doc-id="${inv.id}">${escapeHtmlAdmin(inv.document_number)}</a>` : ""}</td>`;
    }).join("");
    // bot16, 2026-09-17 (Robert primo: "ty ikony budou i v radcich tzn
    // budou mit svuj sloupec") - vlastni uzky sloupec s ikonou stavu,
    // oddeleny od textoveho "Stav" pillu (ne duplicitne uvnitr pillu).
    // Barevny prouzek na celem radku (status-${o.status} trida, viz
    // .order-row.status-* v admin.html) - "zive prenest [barvu] na
    // radky objednavek".
    const statusIcon = ORDER_STATUS_ICONS[o.status] || "";
    const nextStatus = ORDER_NEXT_STATUS[o.status];
    // bot5, 2026-09-17 (Robert primo) - tlacitko barvou/textem ukazuje
    // CILOVY stav (kam preklopeni smeruje), stejna trida jako pill (viz
    // .order-status-pill.* v admin.html) - "meni se barva a text
    // tlacitka" presne timhle prekreslenim po kazde zmene stavu.
    const advanceCell = nextStatus
      ? `<button type="button" class="order-status-pill order-advance-btn ${nextStatus}" data-id="${o.id}" data-next="${nextStatus}" style="border:none;cursor:pointer;">→ ${escapeHtmlAdmin(ORDER_STATUS_LABELS[nextStatus])}</button>`
      : "";
    return `<tr class="order-row status-${o.status}" data-id="${o.id}">
      <td><input type="checkbox" class="order-chk" data-id="${o.id}" ${orderSelectedIds.has(o.id) ? "checked" : ""}></td>
      <td>${escapeHtmlAdmin(o.order_number)}</td>
      <td>${escapeHtmlAdmin(orderOriginLabel(o))}</td>
      <td>${escapeHtmlAdmin(o.customer_name)}</td>
      <td>${o.total_czk != null ? o.total_czk.toLocaleString("cs-CZ") + " Kč" : ""}</td>
      <td>${bankPaidCell}</td>
      <td class="order-status-icon-cell" title="${escapeHtmlAdmin(o.status_label)}"><em>${statusIcon}</em></td>
      <td><span class="order-status-pill ${o.status}">${escapeHtmlAdmin(o.status_label)}</span></td>
      <td>${advanceCell}</td>
      <td>${o.is_urgent ? `<span class="order-urgent-flag">${ORDER_URGENT_ICON} urgentní</span>` : ""}</td>
      ${invoiceCells}
      <td>${date}</td>
    </tr>`;
  }).join("");
  tbody.querySelectorAll("tr.order-row").forEach(tr => {
    tr.onclick = (e) => {
      if (e.target.closest("input") || e.target.closest(".order-invoice-link") || e.target.closest(".order-advance-btn")) return;
      openOrderDetail(parseInt(tr.dataset.id, 10));
    };
  });
  tbody.querySelectorAll(".order-advance-btn").forEach(btn => {
    btn.onclick = async (e) => {
      e.stopPropagation();
      const id = parseInt(btn.dataset.id, 10);
      const nextStatus = btn.dataset.next;
      btn.disabled = true;
      try {
        const r = await fetch(`/api/admin/orders/${id}`, {
          method: "PUT", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ status: nextStatus }),
        });
        const data = await r.json();
        if (!r.ok) { alert(data.error || "Chyba při změně stavu."); btn.disabled = false; return; }
        loadOrders();
      } catch (err) {
        alert("Nepodařilo se změnit stav.");
        btn.disabled = false;
      }
    };
  });
  tbody.querySelectorAll(".order-chk").forEach(chk => {
    chk.onchange = () => {
      const id = parseInt(chk.dataset.id, 10);
      if (chk.checked) orderSelectedIds.add(id); else orderSelectedIds.delete(id);
      updateOrderBulkToolbar();
    };
  });
  tbody.querySelectorAll(".order-invoice-link").forEach(a => {
    a.onclick = (e) => {
      e.stopPropagation();
      e.preventDefault();
      openPdfViewer(`/api/admin/documents/${a.dataset.docId}/pdf`);
    };
  });
}

let orderSelectedIds = new Set();
function updateOrderBulkToolbar() {
  const bar = document.getElementById("orderBulkToolbar");
  const count = orderSelectedIds.size;
  bar.classList.toggle("active", count > 0);
  document.getElementById("orderBulkCount").textContent = `${count} vybráno`;
}
// Puvodni staticka vazba na #orderSelectAll odstranena (bot9,
// 2026-08-22) - od zavedeni dynamickych sloupcu Faktura N se cela
// hlavicka tabulky (vc. teto checkboxy) prekresluje pri KAZDEM
// renderOrdersTable(), takze by tenhle jednorazovy top-level listener
// po prvnim prekresleni visel na uz odpojenem (starem) DOM elementu.
// Znovu-navazani je ted soucasti renderOrdersTable() vyse.
document.getElementById("orderBulkApplyStatus").onclick = async () => {
  if (!orderSelectedIds.size) return;
  const status = document.getElementById("orderBulkStatus").value;
  if (!status) return;
  const r = await fetch("/api/admin/orders/bulk-status", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ids: [...orderSelectedIds], status }),
  });
  const data = await r.json().catch(() => ({}));
  orderSelectedIds.clear();
  if (data.failed && data.failed.length) {
    alert(`Nastaveno: ${data.updated}. Nešlo změnit: ${data.failed.length} (neplatný přechod stavu).`);
  }
  loadOrders();
};
async function orderBulkSetUrgent(isUrgent) {
  if (!orderSelectedIds.size) return;
  const r = await fetch("/api/admin/orders/bulk-urgent", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ids: [...orderSelectedIds], is_urgent: isUrgent }),
  });
  const data = await r.json().catch(() => ({}));
  orderSelectedIds.clear();
  if (data.failed && data.failed.length) {
    alert(`Nastaveno: ${data.updated}. Nešlo změnit: ${data.failed.length}.`);
  }
  loadOrders();
}
document.getElementById("orderBulkUrgentOn").onclick = () => orderBulkSetUrgent(true);
document.getElementById("orderBulkUrgentOff").onclick = () => orderBulkSetUrgent(false);

// ==================== OBJEDNAVKY: SMAZAT VYBRANE / SMAZAT VSE ====================
// Robert 2026-07-27: "proc nemaji objednavky bulk smazat?" - u zakazniku uz
// "Smazat vse" existovalo (viz deleteAllCustomersModal vyse), u objednavek
// chybelo uplne (zadny backend endpoint). Stejny vzor: "Smazat vybrane" nad
// hromadne vybranou podmnozinou (orderSelectedIds, uz existuje pro
// bulk-status/bulk-urgent) a "Smazat vse" s confirm-count pojistkou pres
// modal (mirror deleteAllCustomersModal).
document.getElementById("orderBulkDelete").onclick = async () => {
  if (!orderSelectedIds.size) return;
  if (!confirm(`Opravdu smazat ${orderSelectedIds.size} vybraných objednávek? Tato akce je nevratná.`)) return;
  const r = await fetch("/api/admin/orders/bulk", {
    method: "DELETE", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ids: [...orderSelectedIds] }),
  });
  const data = await r.json().catch(() => ({}));
  orderSelectedIds.clear();
  if (data.failed && data.failed.length) {
    // bot5, 2026-09-26: "failed" ted obsahuje i normalni (netestovaci)
    // objednavky, ktere uz nejde tvrde smazat (viz orders.py::_is_test_order) -
    // duvod je u kazde v data.failed[].error, obecny text sedi na obojí.
    alert(`Smazáno: ${data.deleted}. Nešlo smazat: ${data.failed.length} (viz konzole pro důvody).`);
    console.log("Nesmazané objednávky:", data.failed);
  }
  loadOrders();
};

// bot16, 2026-09-17 (Robert primo) - "Smazat vsechny objednavky" schovano
// za tenhle rozbalovaci krok (viz komentar u .danger-zone v admin.html),
// at prvni omylny klik nespusti rovnou potvrzovaci modal.
document.getElementById("ordersDangerZoneToggle").onclick = () => {
  const zone = document.getElementById("ordersDangerZone");
  const btn = document.getElementById("ordersDangerZoneToggle");
  const zobrazeno = zone.hidden;
  zone.hidden = !zobrazeno;
  btn.textContent = zobrazeno ? "▴ Skrýt nebezpečné akce" : "▾ Nebezpečné akce";
};

document.getElementById("btnDeleteAllOrders").onclick = () => {
  const errEl = document.getElementById("deleteAllOrdersModalErr");
  errEl.textContent = "";
  const count = ordersCache.length;
  document.getElementById("delAllOrdCount").textContent = count;
  document.getElementById("delAllOrdCount2").textContent = count;
  document.getElementById("delAllOrdConfirmInput").value = "";
  document.getElementById("deleteAllOrdersModalConfirm").disabled = true;
  document.getElementById("deleteAllOrdersModal").classList.add("open");
};

document.getElementById("delAllOrdConfirmInput").addEventListener("input", () => {
  const val = document.getElementById("delAllOrdConfirmInput").value.trim();
  document.getElementById("deleteAllOrdersModalConfirm").disabled = (val !== String(ordersCache.length));
});

document.getElementById("deleteAllOrdersModalCancel").onclick = () => {
  document.getElementById("deleteAllOrdersModal").classList.remove("open");
};

document.getElementById("deleteAllOrdersModalConfirm").onclick = async () => {
  const errEl = document.getElementById("deleteAllOrdersModalErr");
  errEl.textContent = "";
  const count = ordersCache.length;
  const btn = document.getElementById("deleteAllOrdersModalConfirm");
  btn.disabled = true;
  btn.textContent = "Mažu…";
  try {
    const r = await fetch("/api/admin/orders", {
      method: "DELETE", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ confirm_count: count }),
    });
    const data = await r.json();
    if (!r.ok) {
      errEl.textContent = data.error || "Chyba při mazání.";
      if (typeof data.current_count === "number") {
        document.getElementById("delAllOrdCount").textContent = data.current_count;
        document.getElementById("delAllOrdCount2").textContent = data.current_count;
      }
      return;
    }
    document.getElementById("deleteAllOrdersModal").classList.remove("open");
    // bot5, 2026-09-26: od ted se tvrde maze jen testovaci objednavky
    // (viz orders.py::_is_test_order) - normalni zustavaji (musi se
    // zrusit stavem), aby nevznikaly diry v cislovani. "blocked" > 0 by
    // jinak vypadalo jako by se nic nestalo (modal se jen zavre).
    if (data.blocked) {
      alert(`Smazáno ${data.deleted} testovacích objednávek. ${data.blocked} normálních objednávek zůstalo (mají vydané číslo) - zrušte je jednotlivě stavem "Zrušená".`);
    }
    loadOrders();
  } catch (e) {
    errEl.textContent = "Nepodařilo se smazat objednávky (chyba spojení).";
  } finally {
    const val = document.getElementById("delAllOrdConfirmInput").value.trim();
    btn.disabled = (val !== String(ordersCache.length));
    btn.textContent = "Smazat vše";
  }
};

document.getElementById("orderSearchApply").onclick = () => {
  orderFilter.q = document.getElementById("orderSearchQ").value.trim();
  orderFilter.date_from = document.getElementById("orderFilterDateFrom").value;
  orderFilter.date_to = document.getElementById("orderFilterDateTo").value;
  orderFilter.shipping_method = document.getElementById("orderFilterShipping").value;
  orderFilter.payment_method = document.getElementById("orderFilterPayment").value;
  orderFilter.price_min = document.getElementById("orderFilterPriceMin").value;
  orderFilter.price_max = document.getElementById("orderFilterPriceMax").value;
  orderFilter.has_account = document.getElementById("orderFilterAccount").value;
  orderFilter.origin = document.getElementById("orderFilterOrigin").value;
  orderFilter.page = 1;
  loadOrders();
};
document.getElementById("orderSearchReset").onclick = () => {
  document.getElementById("orderSearchQ").value = "";
  document.getElementById("orderFilterDatePreset").value = "";
  document.getElementById("orderFilterDateFrom").value = "";
  document.getElementById("orderFilterDateTo").value = "";
  document.getElementById("orderFilterShipping").value = "";
  document.getElementById("orderFilterPayment").value = "";
  document.getElementById("orderFilterPriceMin").value = "";
  document.getElementById("orderFilterPriceMax").value = "";
  document.getElementById("orderFilterAccount").value = "";
  document.getElementById("orderFilterOrigin").value = "";
  orderFilter = { status: orderFilter.status, urgent: orderFilter.urgent, q: "", date_from: "", date_to: "",
    shipping_method: "", payment_method: "", price_min: "", price_max: "", has_account: "", origin: "",
    page: 1, page_size: orderFilter.page_size };
  loadOrders();
};

// Zalozky v detailu objednavky (Robert primo, 2026-09-16, navazujici na
// pozadavek o vizualni oddeleni sekci: "idealne postav zalozky protoze
// bude potreba pridavat funkce atd, napr potrebujeme resit dodaci listy,
// to bude prvni zalozka"). Kazda .om-section v #orderModal ma [data-om-tab]
// (vic sekci muze sdilet stejny klic, napr Kontakt+Polozky = "prehled"),
// prepinani jen CSS tridou .active - zadny dalsi fetch, data uz jsou
// vykreslena vsechna najednou v renderOrderModal/loadOrderDocuments/atd.
function omSwitchTab(key) {
  document.querySelectorAll("#orderModalTabs .om-tab-btn").forEach(btn => {
    btn.classList.toggle("active", btn.dataset.omTab === key);
  });
  document.querySelectorAll("#orderModalBox .om-section[data-om-tab]").forEach(sec => {
    sec.classList.toggle("active", sec.dataset.omTab === key);
  });
}
document.querySelectorAll("#orderModalTabs .om-tab-btn").forEach(btn => {
  btn.onclick = () => omSwitchTab(btn.dataset.omTab);
});

async function openOrderDetail(id) {
  currentOrderId = id;
  document.getElementById("orderModalErr").textContent = "";
  omSwitchTab("dodaci");
  try {
    const r = await fetch(`/api/admin/orders/${id}`);
    const data = await r.json();
    if (!r.ok) { alert(data.error || "Chyba při načítání objednávky."); return; }
    renderOrderModal(data.order);
    document.getElementById("orderModal").classList.add("open");
    loadOrderDocuments(id);
    loadOrderEmails(id);
    loadOrderSupportConversations(id);
    loadCuttingPlan(id);
    renderGalleryModule(document.getElementById("orderModalGallery"), "order", id);
    document.getElementById("customEmailForm").style.display = "none";
    document.getElementById("emailRecipient").value = "";
    document.getElementById("emailCc").value = "";
    document.getElementById("emailSubject").value = "";
    document.getElementById("emailBody").value = "";
    document.getElementById("orderAddItemErr").textContent = "";
    document.getElementById("orderAddItemQty").value = "1";
    document.getElementById("orderAddCustomQty").value = "1";
  } catch (e) {
    alert("Nepodařilo se načíst detail objednávky.");
  }
}

function renderOrderModal(order) {
  document.getElementById("orderModalTitle").textContent = `Objednávka ${order.order_number}`;
  const created = new Date(order.created_at).toLocaleString("cs-CZ");
  document.getElementById("orderModalMeta").textContent =
    `Vytvořeno: ${created} · Stav: ${order.status_label}${order.is_urgent ? " · URGENTNÍ" : ""}`;

  const contact = document.getElementById("orderModalContact");
  contact.innerHTML = [
    `<div><b>${escapeHtmlAdmin(order.customer_name)}</b></div>`,
    `<div>${escapeHtmlAdmin(order.customer_email)}</div>`,
    order.customer_phone ? `<div>${escapeHtmlAdmin(order.customer_phone)}</div>` : "",
    order.delivery_address ? `<div>${escapeHtmlAdmin(order.delivery_address)}</div>` : "",
    order.note ? `<div style="margin-top:6px;color:#9aa4b2;">Poznámka zákazníka: ${escapeHtmlAdmin(order.note)}</div>` : "",
  ].join("");

  const itemsEditable = !ORDER_ITEMS_LOCKED_STATUSES.includes(order.status);
  document.getElementById("orderModalItems").innerHTML = (order.items || []).map(it => `
    <tr>
      <td>${escapeHtmlAdmin(it.product_name)}${it.cut_pieces ? `<div style="font-size:11px;color:#9aa4b2;margin-top:2px;">Přířezy: ${it.cut_pieces.map(c => `${c.qty}× ${c.length_mm} mm`).join(", ")} (zbytky náleží zákazníkovi)</div>` : ""}${it.assembly_kod_snapshot ? `<div style="font-size:11px;color:#9aa4b2;margin-top:2px;">Varianta: ${escapeHtmlAdmin(it.assembly_kod_snapshot)}</div>` : ""}${it.montaz_zvolena ? `<div style="font-size:11px;color:#7fc97f;margin-top:2px;">+ Montáž${it.montaz_misto_label ? ` – ${escapeHtmlAdmin(it.montaz_misto_label)}` : ""}${it.montaz_czk_snapshot != null ? ` (${it.montaz_czk_snapshot.toLocaleString("cs-CZ")} Kč)` : ""}</div>` : ""}${it.bez_boxu ? `<div style="font-size:11px;color:#e0a840;margin-top:2px;">Bez boxů (klient má vlastní)${it.boxy_czk_snapshot != null ? ` − ${it.boxy_czk_snapshot.toLocaleString("cs-CZ")} Kč` : ""}</div>` : ""}</td>
      <td>${itemsEditable
        ? `<input type="number" class="om-item-qty" data-item-id="${it.id}" data-prev-qty="${it.qty}" value="${it.qty}" min="1" step="1" style="width:60px;background:var(--panel-bg-alt);border:1px solid var(--border-soft);color:var(--text2);padding:2px 4px;border-radius:4px;">`
        : it.qty}</td>
      <td>${it.unit_price_czk != null ? it.unit_price_czk.toLocaleString("cs-CZ") + " Kč" : ""}</td>
      <td>${it.line_total_czk != null ? it.line_total_czk.toLocaleString("cs-CZ") + " Kč" : ""}</td>
      <td>${itemsEditable ? `<button type="button" class="om-item-remove" data-item-id="${it.id}" style="background:none;border:1px solid #3a3f4a;color:#e07070;padding:2px 7px;">×</button>` : ""}</td>
    </tr>
  `).join("");
  document.querySelectorAll("#orderModalItems .om-item-remove").forEach(btn => {
    btn.onclick = () => removeOrderItem(parseInt(btn.dataset.itemId, 10));
  });
  document.querySelectorAll("#orderModalItems .om-item-qty").forEach(inp => {
    inp.onchange = () => updateOrderItemQty(parseInt(inp.dataset.itemId, 10), inp);
  });
  document.getElementById("orderAddItemWrap").style.display = itemsEditable ? "" : "none";
  document.getElementById("orderAddItemLockedNote").style.display = itemsEditable ? "none" : "";

  document.getElementById("orderModalHistory").innerHTML = (order.history || []).map(h => {
    const date = new Date(h.changed_at).toLocaleString("cs-CZ");
    // Robert 2026-08 ("u automatickych dokladu doplnit: automat"):
    // changed_by=NULL vzdy znamena, ze zmenu/zalozeni provedl system
    // (auto-preklopeni stavu, automaticke zalozeni PO na chybejici
    // zbozi), ne ze by se "nikdo neuvedl" - popisat to jednoznacne.
    const who = h.changed_by_name || "Automat";
    return `<tr>
      <td>${date}</td>
      <td>${escapeHtmlAdmin(h.status_label)}</td>
      <td>${escapeHtmlAdmin(who)}</td>
      <td>${escapeHtmlAdmin(h.note || "")}</td>
    </tr>`;
  }).join("");

  const statusSelect = document.getElementById("orderEditStatus");
  const allowed = ORDER_ALLOWED_TRANSITIONS[order.status] || [];
  const opts = [`<option value="">— beze změny (${escapeHtmlAdmin(order.status_label)}) —</option>`]
    .concat(allowed.map(s => `<option value="${s}">${escapeHtmlAdmin(ORDER_STATUS_LABELS[s] || s)}</option>`));
  statusSelect.innerHTML = opts.join("");
  statusSelect.disabled = allowed.length === 0;

  document.getElementById("orderEditUrgent").checked = !!order.is_urgent;
  document.getElementById("orderEditAdminNote").value = order.admin_note || "";
  document.getElementById("orderEditHistoryNote").value = "";

  // Reklamace/vratky (bot18, 2026-09-05) - vlastni sekce v admin/js/reklamace.js,
  // volana odsud at ma primo k dispozici uz nacteny `order` objekt (zadny
  // dalsi fetch potreba). Zavolano az na konci - potrebuje order.id/status/items.
  if (typeof renderOrderReturnSection === "function") renderOrderReturnSection(order);

  renderOrderDispatch(order);
  renderShippingReview(order);
}

// Doprava ke schvaleni u objednavek z mini-shopu (Robert 2026-10-03; API bot5: POST /api/admin/orders/<id>/shipping {shipping_price_czk, approve, vat_ok?, note?}):
// zamestnanec upravi cenu dopravy (Kc bez DPH) a schvali -> server prepocte celek, vystavi zalohovou fakturu a zaradi e-mail do schvalovaci fronty (pravidlo 16).
function renderShippingReview(order) {
  const box = document.getElementById("orderShippingReview");
  if (!box) return;
  if (!order.shipping_review) { box.hidden = true; box.innerHTML = ""; return; }
  let snap = null;
  const m = /\[EUR-SNAPSHOT (\{.*?\})\]/.exec(order.admin_note || "");
  if (m) { try { snap = JSON.parse(m[1]); } catch (e) { snap = null; } }
  // objednavka HLAVNIHO e-shopu (stul z generatoru, host i prihlaseny; bot5 2026-10-04): bez EUR snimku a bez kontroly VAT cisla; zamestnanec urcuje dopravu podle montaze (radek "Montaz - kod")
  const isMain = !snap && (!order.order_host || /(^|\.)logiman\.cz$/.test(order.order_host));
  const vatCheck = order.vat_check || "none", vatMode = order.vat_mode || "standard";
  const vatNeedsOk = !isMain && vatCheck === "vies_unavailable";
  const eur = n => (n == null ? "—" : Number(n).toLocaleString("cs-CZ") + " €");
  box.hidden = false;
  box.innerHTML = `
    <strong>Doprava ke schválení</strong> <span style="color:#8b93a1;">(objednávka ${isMain ? "hlavního e-shopu" : "z mini-shopu"}: ${escapeHtmlAdmin(orderOriginLabel(order))})</span>
    <div style="margin:6px 0;font-size:13px;color:#c7ccd4;">
      ${isMain ? `Zboží a případná montáž jsou v položkách objednávky (řádek „Montáž – kód“); cenu dopravy určete podle toho, zda zákazník montáž zvolil. Zákazník cenu uvidí ke schválení před zálohovou fakturou.` : `${snap ? `Zboží ${eur(snap.goods_eur)} · kurz ${escapeHtmlAdmin(String(snap.rate))} · marže ${escapeHtmlAdmin(String(snap.margin_pct))} %${snap.shipping_eur != null ? " · doprava (odhad) " + eur(snap.shipping_eur) : ""}` : "Snímek EUR nenalezen v poznámce."}
      <br>DPH: ${vatMode === "reverse_charge" ? "0 % (přenesená povinnost / platné VAT číslo)" : "standardní"} · kontrola VAT: ${escapeHtmlAdmin({ none: "bez VAT čísla", vies_valid: "platné (VIES)", vies_unavailable: "VIES nedostupné - ověřte ručně", vies_invalid: "neplatné (VIES)" }[vatCheck] || vatCheck)}`}
    </div>
    <label for="orderShipPrice">Cena dopravy (Kč bez DPH)</label>
    <input type="number" id="orderShipPrice" min="0" step="1" style="width:140px;" value="${order.shipping_price_czk != null ? escapeHtmlAdmin(String(order.shipping_price_czk)) : ""}">
    ${vatNeedsOk ? `<label style="display:block;margin-top:6px;"><input type="checkbox" id="orderShipVatOk"> IČ DPH jsem ověřil(a) ručně</label>` : ""}
    <div style="margin-top:8px;display:flex;gap:8px;flex-wrap:wrap;">
      <button type="button" id="orderShipSave">Uložit cenu dopravy</button>
      <button type="button" id="orderShipApprove">Schválit a vystavit zálohovou fakturu</button>
    </div>
    <div id="orderShipMsg" style="margin-top:6px;font-size:13px;"></div>`;
  const msg = document.getElementById("orderShipMsg");
  async function send(approve) {
    const price = parseFloat(document.getElementById("orderShipPrice").value);
    if (!isFinite(price) || price < 0) { msg.style.color = "#e07070"; msg.textContent = "Zadejte cenu dopravy (0 nebo více)."; return; }
    if (approve && !confirm("Schválit dopravu a vystavit zálohovou fakturu? E-mail zákazníkovi půjde do schvalovací fronty.")) return;
    const body = { shipping_price_czk: price, approve };
    const ok = document.getElementById("orderShipVatOk");
    if (ok && ok.checked) body.vat_ok = true;
    document.getElementById("orderShipSave").disabled = true; document.getElementById("orderShipApprove").disabled = true;
    try {
      const r = await fetch(`/api/admin/orders/${order.id}/shipping`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      const d = await r.json().catch(() => ({}));
      if (!r.ok) { msg.style.color = "#e07070"; msg.textContent = d.message || d.error || "Chyba."; document.getElementById("orderShipSave").disabled = false; document.getElementById("orderShipApprove").disabled = false; return; }
      msg.style.color = "#7ed49a";
      msg.textContent = d.approved ? `Schváleno. Celkem ${Number(d.total_czk).toLocaleString("cs-CZ")} Kč${d.proforma ? ", zálohová faktura " + d.proforma.document_number : ""}.` : `Uloženo. Celkem ${Number(d.total_czk).toLocaleString("cs-CZ")} Kč (objednávka zůstává ke schválení).`;
      loadOrders(); openOrderDetail(order.id);
    } catch (e) { msg.style.color = "#e07070"; msg.textContent = "Spojení selhalo."; document.getElementById("orderShipSave").disabled = false; document.getElementById("orderShipApprove").disabled = false; }
  }
  document.getElementById("orderShipSave").onclick = () => send(false);
  document.getElementById("orderShipApprove").onclick = () => send(true);
}

// Dodaci listy (Robert primo, 2026-09-16: "polozky ktere se vydali a ktere
// jeste ne, navazano na vydejky ze skladu") - cisty UI/procesni pokrok
// per-polozka (shop_order_items.qty_dispatched), NEZAVISLE na skladove
// zasobe - tu odecita az existujici prechod objednavky do stavu
// potvrzena/pripravit/expedovana/fakturovana (STOCK_DEDUCTED_STATUSES,
// api/orders.py), a to naraz cele mnozstvi vsech polozek. Tady jde jen
// o to, kolik z KAZDE polozky uz fyzicky odeslo, pro vicedavkovou expedici.
function renderOrderDispatch(order) {
  const tbody = document.getElementById("orderModalDispatch");
  if (!tbody) return;
  document.getElementById("orderDispatchErr").textContent = "";
  tbody.innerHTML = (order.items || []).map(it => {
    const dispatched = it.qty_dispatched || 0;
    const remaining = Math.max(0, it.qty - dispatched);
    return `<tr>
      <td>${escapeHtmlAdmin(it.product_name)}</td>
      <td>${it.qty}</td>
      <td><input type="number" class="om-dispatch-qty" data-item-id="${it.id}" data-qty="${it.qty}"
            value="${dispatched}" min="0" max="${it.qty}" step="1"
            style="width:60px;background:var(--panel-bg-alt);border:1px solid var(--border-soft);color:var(--text2);padding:2px 4px;border-radius:4px;"></td>
      <td>${remaining}</td>
      <td>${remaining > 0
        ? `<button type="button" class="om-dispatch-all" data-item-id="${it.id}" data-qty="${it.qty}" style="background:none;border:1px solid #3a3f4a;color:#c7ccd4;padding:2px 7px;">Vydat vše</button>`
        : `<span style="color:#7fc97f;">hotovo</span>`}</td>
    </tr>`;
  }).join("");
  document.querySelectorAll("#orderModalDispatch .om-dispatch-qty").forEach(inp => {
    inp.onchange = () => updateOrderItemDispatch(parseInt(inp.dataset.itemId, 10), parseInt(inp.value, 10));
  });
  document.querySelectorAll("#orderModalDispatch .om-dispatch-all").forEach(btn => {
    btn.onclick = () => updateOrderItemDispatch(parseInt(btn.dataset.itemId, 10), parseInt(btn.dataset.qty, 10));
  });
  const btnAll = document.getElementById("btnDispatchAll");
  if (btnAll) {
    const zbyvaNejaka = (order.items || []).some(it => (it.qty_dispatched || 0) < it.qty);
    btnAll.disabled = !zbyvaNejaka;
    btnAll.onclick = () => dispatchAllItems(order.items || []);
  }
}

async function updateOrderItemDispatch(itemId, qtyDispatched) {
  if (!currentOrderId) return;
  const errEl = document.getElementById("orderDispatchErr");
  errEl.textContent = "";
  try {
    const r = await fetch(`/api/admin/orders/${currentOrderId}/items/${itemId}/dispatch`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ qty_dispatched: qtyDispatched }),
    });
    const data = await r.json();
    if (!r.ok) { errEl.textContent = data.error || "Chyba při ukládání."; return; }
    openOrderDetail(currentOrderId);
  } catch (e) {
    errEl.textContent = "Nepodařilo se uložit vydané množství.";
  }
}

// Hromadne "Vydat vse" (Robert primo, 2026-09-17: "pridej tlacitko vydat
// vsechno") - na rozdil od jednotlive updateOrderItemDispatch() posle
// VSECHNY PUT najednou (Promise.all), teprve pak JEDNOU znovu nacte
// modal - jednotlivy fetch-po-fetchu se sekvencnim reloadem by pro N
// polozek delal N zbytecnych reloadu.
async function dispatchAllItems(items) {
  if (!currentOrderId) return;
  const errEl = document.getElementById("orderDispatchErr");
  errEl.textContent = "";
  const zbyvajici = items.filter(it => (it.qty_dispatched || 0) < it.qty);
  if (!zbyvajici.length) return;
  try {
    const results = await Promise.all(zbyvajici.map(it =>
      fetch(`/api/admin/orders/${currentOrderId}/items/${it.id}/dispatch`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ qty_dispatched: it.qty }),
      }).then(r => r.json().then(data => ({ ok: r.ok, data })))
    ));
    const chyba = results.find(r => !r.ok);
    if (chyba) errEl.textContent = chyba.data.error || "Některé položky se nepodařilo vydat.";
    openOrderDetail(currentOrderId);
  } catch (e) {
    errEl.textContent = "Nepodařilo se vydat všechny položky.";
  }
}

// Pridani/odebrani polozky do JIZ EXISTUJICI objednavky (Robert 2026-08-06:
// "v objednávce je potřeba přidat možnost přidat zboží, produkt službu") -
// stejny vzor jako "Nova objednavka" (populateManualOrderProductSelect,
// wireProductSuggest), ale misto stavby lokalniho pole rovnou vola
// POST/DELETE /api/admin/orders/<id>/items a znovu vykresli modal.
// ORDER_ITEMS_LOCKED_STATUSES musi odpovidat backendu (NON_EDITABLE_ITEM_STATUSES
// v api/orders.py) - "zrusena"/"fakturovana"/"expedovana" (Robert pres
// bot3, 2026-08-22: "vyřízená objednávka nelze upravovat") uz polozky
// menit nedovoluji.
const ORDER_ITEMS_LOCKED_STATUSES = ["zrusena", "fakturovana", "expedovana"];

async function addOrderItemToCurrent(body) {
  if (!currentOrderId) return;
  const errEl = document.getElementById("orderAddItemErr");
  errEl.textContent = "";
  try {
    const r = await fetch(`/api/admin/orders/${currentOrderId}/items`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await r.json();
    if (!r.ok) { errEl.textContent = data.error || "Chyba při přidávání položky."; return; }
    document.getElementById("orderAddItemProductSearch").value = "";
    document.getElementById("orderAddCustomName").value = "";
    document.getElementById("orderAddCustomPrice").value = "";
    await refreshOrderModal();
    loadOrders();
  } catch (e) {
    errEl.textContent = "Chyba při přidávání položky: " + e.message;
  }
}

async function removeOrderItem(itemId) {
  if (!currentOrderId) return;
  if (!confirm("Opravdu odebrat tuto položku z objednávky?")) return;
  const errEl = document.getElementById("orderAddItemErr");
  errEl.textContent = "";
  try {
    const r = await fetch(`/api/admin/orders/${currentOrderId}/items/${itemId}`, { method: "DELETE" });
    const data = await r.json();
    if (!r.ok) { errEl.textContent = data.error || "Chyba při odebírání položky."; return; }
    await refreshOrderModal();
    loadOrders();
  } catch (e) {
    errEl.textContent = "Chyba při odebírání položky: " + e.message;
  }
}

async function updateOrderItemQty(itemId, inputEl) {
  if (!currentOrderId) return;
  const errEl = document.getElementById("orderAddItemErr");
  errEl.textContent = "";
  const prevQty = parseInt(inputEl.dataset.prevQty, 10);
  const newQty = parseInt(inputEl.value, 10);
  if (!Number.isInteger(newQty) || newQty <= 0) {
    errEl.textContent = "Množství musí být kladné celé číslo.";
    inputEl.value = prevQty;
    return;
  }
  if (newQty === prevQty) return;
  inputEl.disabled = true;
  try {
    const r = await fetch(`/api/admin/orders/${currentOrderId}/items/${itemId}`, {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ qty: newQty }),
    });
    const data = await r.json();
    if (!r.ok) {
      errEl.textContent = data.error || "Chyba při úpravě množství.";
      inputEl.value = prevQty;
      inputEl.disabled = false;
      return;
    }
    await refreshOrderModal();
    loadOrders();
  } catch (e) {
    errEl.textContent = "Chyba při úpravě množství: " + e.message;
    inputEl.value = prevQty;
    inputEl.disabled = false;
  }
}

async function refreshOrderModal() {
  if (!currentOrderId) return;
  const r = await fetch(`/api/admin/orders/${currentOrderId}`);
  const data = await r.json();
  if (r.ok) renderOrderModal(data.order);
}

wireProductSuggest(
  "orderAddItemProductSearch", "orderAddItemProductSuggestions",
  () => true,
  (productId) => addOrderItemToCurrent({
    product_id: productId, qty: parseInt(document.getElementById("orderAddItemQty").value, 10) || 1,
  }),
);

document.getElementById("orderAddCustomBtn").onclick = () => {
  const name = document.getElementById("orderAddCustomName").value.trim();
  const qty = parseInt(document.getElementById("orderAddCustomQty").value, 10) || 1;
  const price = parseFloat(document.getElementById("orderAddCustomPrice").value);
  if (!name) { document.getElementById("orderAddItemErr").textContent = "Zadej název vlastní položky."; return; }
  if (isNaN(price) || price < 0) { document.getElementById("orderAddItemErr").textContent = "Zadej platnou cenu za kus."; return; }
  addOrderItemToCurrent({ name, qty, unit_price_czk: price });
};

document.getElementById("orderModalCancel").onclick = () => {
  document.getElementById("orderModal").classList.remove("open");
};

document.getElementById("orderModalSave").onclick = async () => {
  if (!currentOrderId) return;
  const errEl = document.getElementById("orderModalErr");
  errEl.textContent = "";
  const body = {};
  const newStatus = document.getElementById("orderEditStatus").value;
  if (newStatus) body.status = newStatus;
  body.is_urgent = document.getElementById("orderEditUrgent").checked;
  body.admin_note = document.getElementById("orderEditAdminNote").value;
  const historyNote = document.getElementById("orderEditHistoryNote").value.trim();
  if (historyNote) body.history_note = historyNote;

  const r = await fetch(`/api/admin/orders/${currentOrderId}`, {
    method: "PUT", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await r.json();
  if (!r.ok) { errEl.textContent = data.error || "Chyba."; return; }
  document.getElementById("orderModal").classList.remove("open");
  loadOrders();
};

// ==================== DOKLADY: NASTAVENI CISELNE RADY ====================
// bot10, 2026-08-22 - viz api/documents.py GET/PUT /api/admin/document-
// sequences[/<document_type>]. Admin editovatelny prefix per typ dokladu
// (drive hardcoded v Pythonu, viz TASKS.md/AGENTS_LOG.md pro cely kontext).
// bot5, 2026-09-28 (Robert primo, TRETI a FINALNI verze zadani - po
// "rok automaticky" a "jen 3 nove typy" jeste dorazilo "kde vidis v
// prefixu 2609????" u dodaciho listu, kdyz tam cekal jen to, co sam
// napsal) - VSECHNY typy dokladu stejne, zadna vyjimka: prefix se
// pouzije DOSLOVA CELY tak, jak ho admin napise, + poradi na 5 cislic,
// nic vic. Spocitame PRESNE totez, co spocita _next_document_number()
// na backendu, a ukazeme to zive vedle poli, jeste pred ulozenim.
function docSeqPreview(prefixValue, currentValue) {
  const nextSeq = (parseInt(currentValue, 10) || 0) + 1;
  return `${prefixValue}${String(nextSeq).padStart(5, "0")}`;
}

async function loadDocSequences() {
  const r = await fetch("/api/admin/document-sequences");
  const data = await r.json().catch(() => ({}));
  const tbody = document.getElementById("docSeqTbody");
  if (!r.ok) { tbody.innerHTML = `<tr><td colspan="5" style="color:var(--error);">${escapeHtmlAdmin(data.error || "Chyba.")}</td></tr>`; return; }
  const currentYear = new Date().getFullYear();
  const sequences = data.sequences || [];
  tbody.innerHTML = sequences.map(s => {
    const yearRow = (s.years || []).find(y => y.seq_year === currentYear);
    // bot5, 2026-09-27 (Robert primo, ze screenshotu): "aktuální číslo"
    // uz neni jen zobrazeni, jde editovat - posledni VYDANE cislo letos
    // (next_number-1), prazdne kdyz jeste zadne nebylo (0 by vypadalo
    // jako "uz jeden vydany").
    const lastIssued = yearRow ? yearRow.next_number - 1 : "";
    const prefixHint = `prefix se použije doslova celý (i s rokem, pokud ho tam chcete) - žádný rok se sám nepřidává`;
    return `<tr data-type="${s.document_type}">
      <td>${escapeHtmlAdmin(s.label)}</td>
      <td><input type="text" class="docseq-prefix" data-type="${s.document_type}" value="${escapeHtmlAdmin(s.prefix)}" title="${escapeHtmlAdmin(prefixHint)}" style="width:90px;text-transform:uppercase;"></td>
      <td><input type="number" min="0" class="docseq-current" data-type="${s.document_type}" value="${lastIssued}" placeholder="0" style="width:90px;"></td>
      <td class="docseq-preview" data-type="${s.document_type}" style="font-family:ui-monospace,Consolas,monospace;color:var(--accent);"></td>
      <td><button type="button" class="docseq-save" data-type="${s.document_type}">Uložit</button></td>
    </tr>`;
  }).join("");

  function updatePreview(type) {
    const s = sequences.find(x => x.document_type === type);
    const prefixInput = tbody.querySelector(`.docseq-prefix[data-type="${type}"]`);
    const currentInput = tbody.querySelector(`.docseq-current[data-type="${type}"]`);
    const previewEl = tbody.querySelector(`.docseq-preview[data-type="${type}"]`);
    previewEl.textContent = "další bude: " + docSeqPreview(prefixInput.value.trim().toUpperCase(), currentInput.value);
  }
  sequences.forEach(s => updatePreview(s.document_type));
  tbody.querySelectorAll(".docseq-prefix, .docseq-current").forEach(inp => {
    inp.addEventListener("input", () => updatePreview(inp.dataset.type));
  });

  tbody.querySelectorAll(".docseq-save").forEach(btn => {
    btn.onclick = async () => {
      const type = btn.dataset.type;
      const prefixInput = tbody.querySelector(`.docseq-prefix[data-type="${type}"]`);
      const currentInput = tbody.querySelector(`.docseq-current[data-type="${type}"]`);
      const errEl = document.getElementById("docSeqErr");
      errEl.textContent = "";
      const body = { prefix: prefixInput.value };
      if (currentInput.value.trim() !== "") body.current_number = currentInput.value.trim();
      const resp = await fetch(`/api/admin/document-sequences/${type}`, {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const d = await resp.json().catch(() => ({}));
      if (!resp.ok) { errEl.textContent = d.error || "Uložení se nezdařilo."; return; }
      // bot5, 2026-09-27/28 (Robert: "nepřepisuje mi to zpátky tím co je
      // v DB") - CELY loadDocSequences() by tady prepsal/smazal rozepsane
      // (jeste neulozene) hodnoty ve VSECH OSTATNICH radcich panelu, ne
      // jen v tomhle jednom - admin typicky nastavuje víc řad najednou.
      // Ulozene se skutecne ulozilo (viz resp.ok vyse) - staci potvrdit,
      // ne cely seznam znovu stahovat/prekreslovat.
      btn.textContent = "✓ Uloženo";
      setTimeout(() => { btn.textContent = "Uložit"; }, 1500);
    };
  });
}
document.getElementById("btnDocSequenceSettings").onclick = () => {
  loadDocSequences();
  document.getElementById("docSequenceModal").classList.add("open");
};
document.getElementById("btnDocSequenceClose").onclick = () => {
  document.getElementById("docSequenceModal").classList.remove("open");
};
document.getElementById("docSequenceModal").addEventListener("click", (e) => {
  if (e.target.id === "docSequenceModal") document.getElementById("docSequenceModal").classList.remove("open");
});

// ==================== DOKLADY: CELKOVY PREHLED ====================
// bot3 log (13): GET /api/admin/documents - stejny vzor jako Objednavky
// (counts pro taby, filtrovani, tabulka). Klik na radek otevre prislusnou
// objednavku (prepne na zalozku Objednavky + otevre orderModal).
const DOCUMENT_TYPE_LABELS_ADMIN = {
  proforma_invoice: "Zálohová faktura",
  payment_tax_document: "Daňový doklad k přijaté platbě",
  invoice: "Faktura - Daňový doklad",
};
// page/page_size - task #78/87
let docFilter = { document_type: "", q: "", date_from: "", date_to: "", page: 1, page_size: 50 };
let documentsCache = [];

async function loadDocuments() {
  const params = new URLSearchParams({ page: docFilter.page, page_size: docFilter.page_size });
  if (docFilter.document_type) params.set("document_type", docFilter.document_type);
  if (docFilter.q) params.set("q", docFilter.q);
  if (docFilter.date_from) params.set("date_from", docFilter.date_from);
  if (docFilter.date_to) params.set("date_to", docFilter.date_to);
  try {
    const r = await fetch(`/api/admin/documents?${params.toString()}`);
    const data = await r.json();
    if (!r.ok) { document.getElementById("documentsErr").textContent = data.error || "Chyba."; return; }
    documentsCache = data.documents || [];
    renderDocumentStatusTabs(data.counts || {});
    renderDocumentsTable(documentsCache);
    renderPager("documentsPager", data, docFilter, loadDocuments);
    const totalEl = document.getElementById("docTotalOutstanding");
    const total = data.total_outstanding_czk ?? 0;
    totalEl.textContent = `Celkem nesplaceno (zálohové faktury a faktury): ${total.toLocaleString("cs-CZ")} Kč`;
  } catch (e) {
    document.getElementById("documentsErr").textContent = "Nepodařilo se načíst doklady.";
  }
}

function renderDocumentStatusTabs(counts) {
  const defs = [
    { key: "", label: "Vše", count: counts.all ?? 0 },
    { key: "proforma_invoice", label: DOCUMENT_TYPE_LABELS_ADMIN.proforma_invoice, count: counts.proforma_invoice ?? 0 },
    { key: "payment_tax_document", label: DOCUMENT_TYPE_LABELS_ADMIN.payment_tax_document, count: counts.payment_tax_document ?? 0 },
    { key: "invoice", label: DOCUMENT_TYPE_LABELS_ADMIN.invoice, count: counts.invoice ?? 0 },
  ];
  const wrap = document.getElementById("docStatusTabs");
  wrap.innerHTML = defs.map(d => {
    const active = docFilter.document_type === d.key;
    return `<button type="button" class="order-tab-btn${active ? " active" : ""}" data-key="${d.key}">${escapeHtmlAdmin(d.label)}<span class="otc">(${d.count})</span></button>`;
  }).join("");
  wrap.querySelectorAll(".order-tab-btn").forEach(btn => {
    btn.onclick = () => {
      docFilter.document_type = btn.dataset.key;
      docFilter.page = 1;
      loadDocuments();
    };
  });
}

function renderDocumentsTable(docs) {
  const tbody = document.getElementById("documentsTbody");
  if (!docs.length) {
    tbody.innerHTML = '<tr><td colspan="8" style="color:#666;">Žádné doklady.</td></tr>';
    return;
  }
  tbody.innerHTML = docs.map(d => {
    const issued = d.issue_date ? new Date(d.issue_date).toLocaleDateString("cs-CZ") : "";
    const due = d.amount_due_czk != null ? d.amount_due_czk.toLocaleString("cs-CZ") + " Kč" : "0 Kč";
    return `<tr class="order-row" data-order-id="${d.order_id}">
      <td><input type="checkbox" class="doc-chk" data-id="${d.id}" ${docSelectedIds.has(d.id) ? "checked" : ""} onclick="event.stopPropagation()"></td>
      <td>${escapeHtmlAdmin(d.document_number)}</td>
      <td>${escapeHtmlAdmin(d.document_type_label)}</td>
      <td>${escapeHtmlAdmin(d.order_number)}</td>
      <td>${escapeHtmlAdmin(d.customer_name)}</td>
      <td>${issued}</td>
      <td>${due}</td>
      <td><a href="#" onclick="event.stopPropagation(); openPdfViewer('/api/admin/documents/${d.id}/pdf'); return false;">Stáhnout PDF</a>
        · ${docEmailOdkaz(d, "doc-tab-send-email", `data-order-id="${d.order_id}" data-doc-id="${d.id}"`)}
        · <a href="#" class="doc-tab-cam-btn" data-doc-id="${d.id}" data-doc-number="${escapeHtmlAdmin(d.document_number)}">📷 Foto</a>${d.document_type === "payment_tax_document"
          ? ` · <a href="#" class="doc-tab-edit-payment-date" data-doc-id="${d.id}" data-current="${d.issue_date ? d.issue_date.slice(0, 10) : ""}" title="Ruční oprava data přijetí platby">✏️ Datum</a>`
          : ""}</td>
    </tr>`;
  }).join("");
  // Robert 2026-09-29: akce z detailu objednavky (Poslat e-mail, Datum platby u VDD)
  // musi byt i v celkovem prehledu dokladu - stejny backend i stejne funkce jako tam.
  tbody.querySelectorAll(".doc-tab-send-email").forEach(a => {
    a.onclick = async (e) => {
      e.preventDefault();
      e.stopPropagation();
      // bot5, 2026-09-29 (Robert primo: "ten Poslat email nevyvolá
      // žádnou akci!") - sendDocumentEmail driv umela hlasit vysledek
      // jen do #orderEmailErr (existuje pouze v detailu objednavky),
      // tady v prehledu Doklady zadny takovy prvek neni - bez vlastni
      // hlasky vypadal klik, jako by se vubec nic nestalo.
      const result = await sendDocumentEmail(parseInt(a.dataset.orderId, 10), parseInt(a.dataset.docId, 10));
      alert(result && result.ok ? "E-mail odeslán." : (result && result.error) || "Odeslání se nezdařilo.");
    };
  });
  tbody.querySelectorAll(".doc-tab-edit-payment-date").forEach(a => {
    a.onclick = async (e) => {
      e.preventDefault();
      e.stopPropagation();
      const newDate = prompt("Skutečné datum přijetí platby (YYYY-MM-DD):", a.dataset.current || "");
      if (!newDate) return;
      const r = await fetch(`/api/admin/documents/${a.dataset.docId}/payment-date`, {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ payment_date: newDate }),
      });
      const resp = await r.json().catch(() => ({}));
      if (!r.ok) { alert(resp.error || "Úprava data se nezdařila."); return; }
      loadDocuments();
    };
  });
  tbody.querySelectorAll("tr.order-row").forEach(tr => {
    tr.onclick = () => {
      document.querySelector('.tab-btn[data-tab="orders"]').click();
      openOrderDetail(parseInt(tr.dataset.orderId, 10));
    };
  });
  tbody.querySelectorAll(".doc-tab-cam-btn").forEach(a => {
    a.onclick = (e) => {
      e.preventDefault();
      e.stopPropagation();
      openAttachmentModal("document", parseInt(a.dataset.docId, 10), "Fotky – doklad " + a.dataset.docNumber);
    };
  });
  tbody.querySelectorAll(".doc-chk").forEach(chk => {
    chk.onchange = () => {
      const id = parseInt(chk.dataset.id, 10);
      if (chk.checked) docSelectedIds.add(id); else docSelectedIds.delete(id);
      updateDocBulkToolbar();
    };
  });
  updateDocBulkToolbar();
}

let docSelectedIds = new Set();
function updateDocBulkToolbar() {
  const bar = document.getElementById("docBulkToolbar");
  const count = docSelectedIds.size;
  bar.classList.toggle("active", count > 0);
  document.getElementById("docBulkCount").textContent = `${count} vybráno`;
}
document.getElementById("docSelectAll").onchange = (e) => {
  if (e.target.checked) documentsCache.forEach(d => docSelectedIds.add(d.id));
  else docSelectedIds.clear();
  renderDocumentsTable(documentsCache);
};
document.getElementById("docBulkDelete").onclick = async () => {
  if (!docSelectedIds.size) return;
  if (!confirm(`Opravdu trvale smazat ${docSelectedIds.size} vybraných dokladů? Jde o účetní doklady ` +
               `(zálohové faktury, daňové doklady k platbě, faktury) - tuto akci nelze vrátit zpět.`)) return;
  const r = await fetch("/api/admin/documents/bulk-delete", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ids: [...docSelectedIds] }),
  });
  const data = await r.json().catch(() => ({}));
  docSelectedIds.clear();
  if ((data.failed && data.failed.length) || (data.stock_failed && data.stock_failed.length)) {
    let msg = `Smazáno: ${data.deleted}.`;
    if (data.failed && data.failed.length) msg += ` Nešlo smazat: ${data.failed.length}.`;
    if (data.stock_failed && data.stock_failed.length) {
      msg += ` Pozor: ${data.stock_failed.length} skladových pohybů objednávky se nepodařilo vrátit ` +
             `(šlo by do záporu skladu) - zkontrolujte skladovou kartu.`;
    }
    alert(msg);
  }
  loadDocuments();
};

document.getElementById("docSearchApply").onclick = () => {
  docFilter.q = document.getElementById("docSearchQ").value.trim();
  docFilter.date_from = document.getElementById("docFilterDateFrom").value;
  docFilter.date_to = document.getElementById("docFilterDateTo").value;
  docFilter.page = 1;
  loadDocuments();
};
document.getElementById("docSearchReset").onclick = () => {
  document.getElementById("docSearchQ").value = "";
  document.getElementById("docFilterDatePreset").value = "";
  document.getElementById("docFilterDateFrom").value = "";
  document.getElementById("docFilterDateTo").value = "";
  docFilter = { document_type: docFilter.document_type, q: "", date_from: "", date_to: "",
    page: 1, page_size: docFilter.page_size };
  loadDocuments();
};

// ==================== PRIJATE DOKLADY (schvalovaci fronta) ====================
// bot8, 2026-08-17. Stejny vzor jako Doklady vyse (status taby + tabulka),
// jen misto strankovani (max 200 radku dost - schvalovaci fronta se
// prubezne cisti, ne hromadi jako vystavene doklady).
const INCOMING_DOC_STATUS_LABELS = {
  ceka_schvaleni: "Ke schválení",
  schvaleno: "Schváleno",
  zamitnuto: "Zamítnuto",
};
let incDocFilter = { status: "ceka_schvaleni", q: "", date_from: "", date_to: "", sort: "newest" };
let incomingDocumentsCache = [];
let incDocSelectedIds = new Set();

async function loadIncomingDocuments() {
  const params = new URLSearchParams();
  if (incDocFilter.status) params.set("status", incDocFilter.status);
  if (incDocFilter.q) params.set("q", incDocFilter.q);
  if (incDocFilter.date_from) params.set("date_from", incDocFilter.date_from);
  if (incDocFilter.date_to) params.set("date_to", incDocFilter.date_to);
  if (incDocFilter.sort === "oldest") params.set("sort", "oldest");
  try {
    const r = await fetch(`/api/admin/incoming-documents?${params.toString()}`);
    const data = await r.json();
    if (!r.ok) { document.getElementById("incomingDocumentsErr").textContent = data.error || "Chyba."; return; }
    incomingDocumentsCache = data.documents || [];
    incDocSelectedIds = new Set([...incDocSelectedIds].filter(id => incomingDocumentsCache.some(d => d.id === id)));
    renderIncomingDocStatusTabs(data.status_counts || {});
    renderIncomingDocumentsTable(incomingDocumentsCache);
    updateIncDocBulkToolbar();
  } catch (e) {
    document.getElementById("incomingDocumentsErr").textContent = "Nepodařilo se načíst doklady.";
  }
}

function renderIncomingDocStatusTabs(counts) {
  const all = (counts.ceka_schvaleni || 0) + (counts.schvaleno || 0) + (counts.zamitnuto || 0);
  // Poradi/stylizace sladeno s Emaily prichozi (Vse prvni, pak jednotlive
  // stavy) - bot3, 2026-08-20.
  const defs = [
    { key: "", label: "Vše", count: all },
    { key: "ceka_schvaleni", label: INCOMING_DOC_STATUS_LABELS.ceka_schvaleni, count: counts.ceka_schvaleni || 0 },
    { key: "schvaleno", label: INCOMING_DOC_STATUS_LABELS.schvaleno, count: counts.schvaleno || 0 },
    { key: "zamitnuto", label: INCOMING_DOC_STATUS_LABELS.zamitnuto, count: counts.zamitnuto || 0 },
  ];
  const wrap = document.getElementById("incDocStatusTabs");
  wrap.innerHTML = defs.map(d => {
    const active = incDocFilter.status === d.key;
    return `<button type="button" class="order-tab-btn${active ? " active" : ""}" data-key="${d.key}">${escapeHtmlAdmin(d.label)}<span class="otc">(${d.count})</span></button>`;
  }).join("");
  wrap.querySelectorAll(".order-tab-btn").forEach(btn => {
    btn.onclick = () => { incDocFilter.status = btn.dataset.key; loadIncomingDocuments(); };
  });
}

function renderIncomingDocumentsTable(docs) {
  const tbody = document.getElementById("incomingDocumentsTbody");
  if (!docs.length) {
    tbody.innerHTML = '<tr><td colspan="11" style="color:#666;">Žádné doklady v tomto stavu.</td></tr>';
    return;
  }
  tbody.innerHTML = docs.map(d => {
    const received = d.received_at ? new Date(d.received_at).toLocaleString("cs-CZ") : "";
    const fileLink = d.filename
      ? (d.approval_status === "schvaleno" && d.drive_file_id
          ? `<a href="/api/admin/drive/files/${d.drive_file_id}/download" target="_blank">${escapeHtmlAdmin(d.filename)}</a>`
          : `<a href="/api/admin/incoming-documents/${d.id}/download" target="_blank">${escapeHtmlAdmin(d.filename)}</a>`)
      : '<span style="color:#666;">(bez přílohy)</span>';
    const statusColor = d.approval_status === "schvaleno" ? "#4caf7a" : d.approval_status === "zamitnuto" ? "#c9564f" : "#d9a441";
    const actions = d.approval_status === "ceka_schvaleni"
      ? `<button type="button" class="idoc-approve" data-id="${d.id}">Schválit</button>
         <button type="button" class="idoc-reject danger" data-id="${d.id}">Zamítnout</button>`
      : "";
    // bot10, 2026-08-22 (Robert pres bot3: "spárujme odchozí platby s
    // přijatými doklady, ať admin nezaplatí omylem duplicitně") -
    // "Uhrazeno" sloupec: potvrzena shoda (zeleny datum + zrusit),
    // NAVRH shody k potvrzeni (zluty hint + tlacitko), nebo prazdno
    // (zadna castka k parovani, nebo zadny navrh nenalezen).
    let paymentCell;
    if (d.paid_at) {
      const paidDate = new Date(d.paid_at).toLocaleDateString("cs-CZ");
      paymentCell = `<span style="color:#4caf7a;">✓ ${paidDate}</span>
        <button type="button" class="idoc-unconfirm-payment" data-id="${d.id}" title="Zrušit potvrzenou shodu"
          style="background:none;border:none;color:#888;cursor:pointer;">✕</button>`;
    } else if (d.payment_matches && d.payment_matches.length) {
      const m = d.payment_matches[0];
      const mDate = new Date(m.transaction_date).toLocaleDateString("cs-CZ");
      paymentCell = `<span style="color:#d9a441;" title="Možná shoda: ${escapeHtmlAdmin(m.counter_account_name || "")}, ${m.amount_czk} Kč, ${mDate}">⚠ možná shoda</span>
        <button type="button" class="idoc-confirm-payment" data-id="${d.id}" data-bank-tx-id="${m.id}">Potvrdit úhradu</button>`;
    } else {
      paymentCell = '<span style="color:#666;">—</span>';
    }
    return `<tr data-id="${d.id}">
      <td><input type="checkbox" class="idoc-chk" data-id="${d.id}" ${incDocSelectedIds.has(d.id) ? "checked" : ""}></td>
      <td>${received}</td>
      <td>${escapeHtmlAdmin(d.source_name || d.source_email || "")}</td>
      <td>${escapeHtmlAdmin(d.subject || "")}</td>
      <td>${fileLink}</td>
      <td><input type="text" class="idoc-supplier" data-id="${d.id}" value="${escapeHtmlAdmin(d.supplier_name || "")}" placeholder="—" style="width:110px;"></td>
      <td><input type="number" class="idoc-amount" data-id="${d.id}" value="${d.amount_czk ?? ""}" placeholder="—" style="width:80px;"></td>
      <td><input type="text" class="idoc-note" data-id="${d.id}" value="${escapeHtmlAdmin(d.note || "")}" placeholder="—" style="width:120px;"></td>
      <td>${paymentCell}</td>
      <td style="color:${statusColor};">${INCOMING_DOC_STATUS_LABELS[d.approval_status] || d.approval_status}</td>
      <td>${actions}</td>
    </tr>`;
  }).join("");

  const saveField = async (id, field, value) => {
    await fetch(`/api/admin/incoming-documents/${id}`, {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ [field]: value }),
    });
  };
  tbody.querySelectorAll(".idoc-chk").forEach(chk => {
    chk.onchange = () => {
      const id = parseInt(chk.dataset.id, 10);
      if (chk.checked) incDocSelectedIds.add(id); else incDocSelectedIds.delete(id);
      updateIncDocBulkToolbar();
    };
  });
  tbody.querySelectorAll(".idoc-supplier").forEach(el => {
    el.onchange = () => saveField(parseInt(el.dataset.id, 10), "supplier_name", el.value);
  });
  tbody.querySelectorAll(".idoc-amount").forEach(el => {
    el.onchange = () => saveField(parseInt(el.dataset.id, 10), "amount_czk", el.value);
  });
  tbody.querySelectorAll(".idoc-note").forEach(el => {
    el.onchange = () => saveField(parseInt(el.dataset.id, 10), "note", el.value);
  });
  tbody.querySelectorAll(".idoc-approve").forEach(btn => {
    btn.onclick = async () => {
      const r = await fetch(`/api/admin/incoming-documents/${btn.dataset.id}/approve`, { method: "POST" });
      const data = await r.json().catch(() => ({}));
      if (!r.ok) { alert(data.error || "Schválení se nezdařilo."); return; }
      loadIncomingDocuments();
    };
  });
  tbody.querySelectorAll(".idoc-reject").forEach(btn => {
    btn.onclick = async () => {
      if (!confirm("Opravdu zamítnout tento doklad? Zůstane uložený, dá se to případně opravit ručně.")) return;
      const r = await fetch(`/api/admin/incoming-documents/${btn.dataset.id}/reject`, { method: "POST" });
      const data = await r.json().catch(() => ({}));
      if (!r.ok) { alert(data.error || "Zamítnutí se nezdařilo."); return; }
      loadIncomingDocuments();
    };
  });
  tbody.querySelectorAll(".idoc-confirm-payment").forEach(btn => {
    btn.onclick = async () => {
      const r = await fetch(`/api/admin/incoming-documents/${btn.dataset.id}/confirm-payment`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ bank_transaction_id: parseInt(btn.dataset.bankTxId, 10) }),
      });
      const data = await r.json().catch(() => ({}));
      if (!r.ok) { alert(data.error || "Potvrzení se nezdařilo."); return; }
      loadIncomingDocuments();
    };
  });
  tbody.querySelectorAll(".idoc-unconfirm-payment").forEach(btn => {
    btn.onclick = async () => {
      if (!confirm("Zrušit potvrzenou shodu s bankovní platbou?")) return;
      const r = await fetch(`/api/admin/incoming-documents/${btn.dataset.id}/unconfirm-payment`, { method: "POST" });
      const data = await r.json().catch(() => ({}));
      if (!r.ok) { alert(data.error || "Zrušení se nezdařilo."); return; }
      loadIncomingDocuments();
    };
  });

  // Robert 2026-08-22, opakovaně: "přijaté doklady musí být klikatelné
  // dovnitř co obsahují jakoby byly stále emaily" - klik na řádek MIMO
  // interaktivní prvky (checkbox/input/button/odkaz na přílohu) otevře
  // čitelný náhled e-mailu (subject/body_text/odesílatel/datum).
  tbody.querySelectorAll("tr[data-id]").forEach(tr => {
    tr.style.cursor = "pointer";
    tr.onclick = (e) => {
      if (e.target.closest("input, button, a")) return;
      openIncomingDocDetail(parseInt(tr.dataset.id, 10));
    };
  });
}

async function openIncomingDocDetail(docId) {
  const modal = document.getElementById("incomingDocDetailModal");
  const metaEl = document.getElementById("incomingDocDetailMeta");
  const bodyEl = document.getElementById("incomingDocDetailBody");
  const errEl = document.getElementById("incomingDocDetailErr");
  errEl.textContent = "";
  metaEl.textContent = "Načítám…";
  bodyEl.textContent = "";
  modal.classList.add("open");
  try {
    const r = await fetch(`/api/admin/incoming-documents/${docId}`);
    const data = await r.json();
    if (!r.ok) { errEl.textContent = data.error || "Nepodařilo se načíst doklad."; metaEl.textContent = ""; return; }
    const received = data.received_at ? new Date(data.received_at).toLocaleString("cs-CZ") : "—";
    metaEl.innerHTML =
      `<div><b>${escapeHtmlAdmin(data.subject || "(bez předmětu)")}</b></div>` +
      `<div>${escapeHtmlAdmin(data.source_name || "")}${data.source_name && data.source_email ? " — " : ""}${escapeHtmlAdmin(data.source_email || "")}</div>` +
      `<div>${received}</div>`;
    bodyEl.textContent = data.body_text || "(e-mail nemá textový obsah)";
  } catch (e) {
    errEl.textContent = "Nepodařilo se načíst doklad: " + e.message;
  }
}
document.getElementById("incomingDocDetailModal").addEventListener("click", (e) => {
  if (e.target.id === "incomingDocDetailModal") e.target.classList.remove("open");
});

// bot3, 2026-08-20 ("stejnou filtraci a stylizaci aplikuj na prijate
// doklady", vzor prevzaty z Emaily prichozi) - hledani/obdobi/razeni +
// hromadny vyber se stejnym bulk-toolbar vzorem jako support
// konverzace. Zadne "Smazat vybrane" tady zamerne NENI - zamitnute
// doklady se podle stavajici zasady (viz incoming_documents_reject)
// nemazou, zustavaji pro pripadnou rucni opravu.
function updateIncDocBulkToolbar() {
  const bar = document.getElementById("incDocBulkToolbar");
  const count = incDocSelectedIds.size;
  bar.classList.toggle("active", count > 0);
  document.getElementById("incDocBulkCount").textContent = `${count} vybráno`;
  document.getElementById("incDocBulkApprove").disabled = count === 0;
  document.getElementById("incDocBulkReject").disabled = count === 0;
}
document.getElementById("incDocSelectAll").onchange = (e) => {
  if (e.target.checked) incomingDocumentsCache.forEach(d => incDocSelectedIds.add(d.id));
  else incDocSelectedIds.clear();
  renderIncomingDocumentsTable(incomingDocumentsCache);
  updateIncDocBulkToolbar();
};
document.getElementById("incDocBulkApprove").onclick = async () => {
  if (!incDocSelectedIds.size) return;
  const r = await fetch("/api/admin/incoming-documents/bulk-approve", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ids: [...incDocSelectedIds] }),
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) { alert(data.error || "Hromadné schválení se nezdařilo."); return; }
  loadIncomingDocuments();
};
document.getElementById("incDocBulkReject").onclick = async () => {
  if (!incDocSelectedIds.size) return;
  if (!confirm(`Opravdu zamítnout ${incDocSelectedIds.size} dokladů? Zůstanou uložené, dá se to případně opravit ručně.`)) return;
  const r = await fetch("/api/admin/incoming-documents/bulk-reject", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ids: [...incDocSelectedIds] }),
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) { alert(data.error || "Hromadné zamítnutí se nezdařilo."); return; }
  loadIncomingDocuments();
};
document.getElementById("incDocSearchApply").onclick = () => {
  incDocFilter.q = document.getElementById("incDocSearchQ").value.trim();
  incDocFilter.date_from = document.getElementById("incDocFilterDateFrom").value;
  incDocFilter.date_to = document.getElementById("incDocFilterDateTo").value;
  incDocFilter.sort = document.getElementById("incDocFilterSort").value;
  loadIncomingDocuments();
};
document.getElementById("incDocSearchReset").onclick = () => {
  document.getElementById("incDocSearchQ").value = "";
  document.getElementById("incDocFilterDatePreset").value = "";
  document.getElementById("incDocFilterDateFrom").value = "";
  document.getElementById("incDocFilterDateTo").value = "";
  document.getElementById("incDocFilterSort").value = "newest";
  incDocFilter = { status: incDocFilter.status, q: "", date_from: "", date_to: "", sort: "newest" };
  loadIncomingDocuments();
};
document.getElementById("incDocSearchQ").addEventListener("keydown", (e) => {
  if (e.key === "Enter") { e.preventDefault(); document.getElementById("incDocSearchApply").click(); }
});
wireDatePresetSelect("incDocFilterDatePreset", "incDocFilterDateFrom", "incDocFilterDateTo", "incDocSearchApply");

// ==================== BANKOVNI VYPISY (FIO) ====================
// bot10, 2026-08-21. Stejny vzor jako Prijate doklady vyse (hint +
// filtr + tabulka), jen misto schvalovaci fronty jde o cisty prehled +
// hledani (vc. hledani podle castky, presne/rozsah - Robertovo zadani).
// direction: 'prijem' (vychozi, zachovava puvodni chovani) / 'vydaj' -
// bot10, 2026-08-22 (Robert pres bot3: "z bankovnich vypisu je videt i
// odchozi platby").
let bankTxFilter = { q: "", amount: "", amount_from: "", amount_to: "", date_from: "", date_to: "", direction: "prijem" };
const fmtBankCzk = (n) => n.toLocaleString("cs-CZ", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

async function loadBankTransactions() {
  const params = new URLSearchParams();
  params.set("direction", bankTxFilter.direction);
  if (bankTxFilter.q) params.set("q", bankTxFilter.q);
  if (bankTxFilter.amount) params.set("amount", bankTxFilter.amount);
  if (bankTxFilter.amount_from) params.set("amount_from", bankTxFilter.amount_from);
  if (bankTxFilter.amount_to) params.set("amount_to", bankTxFilter.amount_to);
  if (bankTxFilter.date_from) params.set("date_from", bankTxFilter.date_from);
  if (bankTxFilter.date_to) params.set("date_to", bankTxFilter.date_to);
  try {
    const r = await fetch(`/api/admin/bank-transactions?${params.toString()}`);
    const data = await r.json();
    if (!r.ok) { document.getElementById("bankTransactionsErr").textContent = data.error || "Chyba."; return; }
    renderBankTransactionsTable(data.transactions || []);
    const sumEl = document.getElementById("bankTxTotalSum");
    sumEl.textContent = `Zobrazeno ${data.transactions.length} z ${data.total_count} plateb, součet zobrazených: ` +
      `${fmtBankCzk(data.transactions.reduce((s, t) => s + t.amount_czk, 0))} Kč ` +
      `(celkem v evidenci: ${fmtBankCzk(data.total_amount_czk)} Kč).`;
    document.getElementById("bankTransactionsErr").textContent = "";
  } catch (e) {
    document.getElementById("bankTransactionsErr").textContent = "Nepodařilo se načíst bankovní výpisy.";
  }
  loadBankSyncStatus();
  loadBankPartialPayments();
}

async function loadBankPartialPayments() {
  const wrap = document.getElementById("bankTxPartialPaymentsWrap");
  try {
    const r = await fetch("/api/admin/bank-transactions/partial-payments");
    const data = await r.json();
    if (!r.ok) { wrap.style.display = "none"; return; }
    const rows = data.partial_payments || [];
    if (!rows.length) { wrap.style.display = "none"; return; }
    wrap.style.display = "";
    const tbody = document.getElementById("bankTxPartialPaymentsTbody");
    tbody.innerHTML = rows.map(p => `<tr>
      <td>${escapeHtmlAdmin(p.order_number)}</td>
      <td>${fmtBankCzk(p.total_czk)} Kč</td>
      <td>${fmtBankCzk(p.bank_total_czk)} Kč</td>
      <td>${fmtBankCzk(p.missing_czk)} Kč</td>
      <td>${p.first_payment_date ? new Date(p.first_payment_date).toLocaleDateString("cs-CZ") : ""}</td>
    </tr>`).join("");
  } catch (e) { wrap.style.display = "none"; }
}

function renderBankTransactionsTable(rows) {
  const tbody = document.getElementById("bankTransactionsTbody");
  if (!rows.length) {
    tbody.innerHTML = '<tr><td colspan="9" style="color:#666;">Žádné platby neodpovídají filtru.</td></tr>';
    return;
  }
  tbody.innerHTML = rows.map(t => {
    const testBadge = t.is_test_data ? ' <span style="color:#d9a441;" title="Testovací záznam, ne skutečná platba">(test)</span>' : "";
    // bot10, 2026-08-22: proklik na spárovaný Přijatý doklad (jen u
    // odchozích plateb, kde admin potvrdil shodu - viz api/incoming_documents.py)
    const linkedDoc = t.linked_incoming_document_id
      ? `<a href="#" onclick="document.querySelector('.tab-btn[data-tab=&quot;incomingdocuments&quot;]').click(); return false;" title="${escapeHtmlAdmin(t.linked_incoming_document_supplier || '')}">✓ doklad #${t.linked_incoming_document_id}</a>`
      : "";
    return `<tr>
      <td>${t.transaction_date ? new Date(t.transaction_date).toLocaleDateString("cs-CZ") : ""}</td>
      <td>${fmtBankCzk(t.amount_czk)} Kč${testBadge}</td>
      <td>${escapeHtmlAdmin(t.variable_symbol || "")}</td>
      <td>${escapeHtmlAdmin(t.counter_account || "")}</td>
      <td>${escapeHtmlAdmin(t.counter_account_name || "")}</td>
      <td>${escapeHtmlAdmin(t.message_for_recipient || "")}</td>
      <td>${escapeHtmlAdmin(t.comment || "")}</td>
      <td>${escapeHtmlAdmin(t.transaction_type || "")}</td>
      <td>${linkedDoc}</td>
    </tr>`;
  }).join("");
}

async function loadBankSyncStatus() {
  try {
    const r = await fetch("/api/admin/bank-transactions/sync-status");
    const data = await r.json();
    const el = document.getElementById("bankTxSyncStatus");
    if (!data.configured) {
      el.textContent = "⚠️ Synchronizace s FIO bankou zatím není nastavena (chybí API token) - zobrazená data mohou být jen testovací.";
      return;
    }
    if (!data.last_sync_at) {
      el.textContent = "Synchronizace s FIO bankou zatím neproběhla.";
      return;
    }
    const when = new Date(data.last_sync_at).toLocaleString("cs-CZ");
    if (data.last_sync_status === "ok") {
      el.textContent = `Poslední synchronizace: ${when} (nově staženo ${data.last_sync_count} plateb).`;
    } else {
      el.textContent = `Poslední synchronizace ${when} skončila chybou: ${data.last_sync_error || ""}`;
    }
  } catch (e) { /* tichy fallback - neni kriticke pro zobrazeni tabulky */ }
}

document.getElementById("bankTxSearchApply").onclick = () => {
  bankTxFilter.q = document.getElementById("bankTxSearchQ").value.trim();
  bankTxFilter.amount = document.getElementById("bankTxAmountExact").value.trim();
  bankTxFilter.amount_from = document.getElementById("bankTxAmountFrom").value.trim();
  bankTxFilter.amount_to = document.getElementById("bankTxAmountTo").value.trim();
  bankTxFilter.date_from = document.getElementById("bankTxFilterDateFrom").value;
  bankTxFilter.date_to = document.getElementById("bankTxFilterDateTo").value;
  loadBankTransactions();
};
document.getElementById("bankTxSearchReset").onclick = () => {
  document.getElementById("bankTxSearchQ").value = "";
  document.getElementById("bankTxAmountExact").value = "";
  document.getElementById("bankTxAmountFrom").value = "";
  document.getElementById("bankTxAmountTo").value = "";
  document.getElementById("bankTxFilterDatePreset").value = "";
  document.getElementById("bankTxFilterDateFrom").value = "";
  document.getElementById("bankTxFilterDateTo").value = "";
  bankTxFilter = { q: "", amount: "", amount_from: "", amount_to: "", date_from: "", date_to: "", direction: bankTxFilter.direction };
  loadBankTransactions();
};
document.getElementById("bankTxSearchQ").addEventListener("keydown", (e) => {
  if (e.key === "Enter") { e.preventDefault(); document.getElementById("bankTxSearchApply").click(); }
});
document.querySelectorAll(".bankTxDirBtn").forEach(btn => {
  btn.onclick = () => {
    document.querySelectorAll(".bankTxDirBtn").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    bankTxFilter.direction = btn.dataset.direction;
    loadBankTransactions();
  };
});
document.getElementById("bankTxSyncNow").onclick = async () => {
  const btn = document.getElementById("bankTxSyncNow");
  btn.disabled = true;
  try {
    const r = await fetch("/api/admin/bank-transactions/sync", { method: "POST" });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) { alert(data.error || "Synchronizace se nezdařila."); return; }
    // bot16, 2026-09-02 (revize bot3, bod 9 - kolize VS): backend platbu NEspáruje, když stejný VS
    // sedí na víc objednávek (zálohovka vs. importované číslo objednávky) - vrátí je v
    // bank_paid_vs_conflicts a admin musí rozhodnout ručně.
    let msg = `Synchronizováno - nově staženo ${data.inserted} plateb.`;
    const conflicts = Array.isArray(data.bank_paid_vs_conflicts) ? data.bank_paid_vs_conflicts : [];
    if (conflicts.length) {
      msg += `\n\n⚠ Kolize VS - ${conflicts.length}× NEspárováno, nutné ruční rozhodnutí:\n` +
        conflicts.map(c => {
          const others = (c.conflicting_orders || []).map(o => o.order_number).join(", ");
          return `• VS ${c.variable_symbol}: objednávka ${c.order_number} ↔ ${others} (${fmtBankCzk(c.bank_total_czk || 0)} Kč)`;
        }).join("\n");
    }
    alert(msg);
    loadBankTransactions();
  } finally {
    btn.disabled = false;
  }
};
wireDatePresetSelect("bankTxFilterDatePreset", "bankTxFilterDateFrom", "bankTxFilterDateTo", "bankTxSearchApply");

// wireProductSuggest() presunuto sem z hlavniho <script> admin.html (bot5,
// 2026-09-03, PLAN_ROZDELENI_FRONTENDU.md, schvaleno bot3) - puvodne bylo
// definovano az v hlavnim <script>, tenhle blok ho ale vola uz na top-levelu
// (autocomplete pro pridani polozky do objednavky), coz by pri nacteni jako
// samostatny <script src> PRED hlavnim <script> spadlo na ReferenceError.
// Funkce je sdileny helper (pouziva ji i Nova nakupni objednavka a Rucni
// zadani objednavky admin, oboje ZUSTAVA v hlavnim <script> - jejich volani
// funguje beze zmeny, protoze tenhle soubor se nacte jeste driv nez ony).
// Skutecny naseptavac (dropdown primo pod polem, klik = rovnou pridat) -
// SDILENA komponenta (bot5, 2026-08-01, Robert: "dej stejne parametry
// pridavani polozek v nakupnich objednavkach jako v prijatych
// objednavkach") - pouziva ji Nova nakupni objednavka (newPOModal) i
// Nova objednavka (manualOrderModal), viz volani nize. filterFn(p)
// rozhoduje, ktere produkty jsou vubec kandidati (u NOO podle
// vybraneho dodavatele), onPick(productId) se zavola po kliknuti na
// navrh. Vraci render funkci pro pripad, ze ji volajici potrebuje
// zavolat i odjinud (napr. pri zmene dodavatele).
function wireProductSuggest(searchInputId, boxId, filterFn, onPick) {
  const input = document.getElementById(searchInputId);
  const box = document.getElementById(boxId);
  function render() {
    const q = input.value.trim().toLowerCase();
    if (!q) { box.classList.remove("open"); box.innerHTML = ""; return; }
    let list = (stockMoveProductsCache || []).filter(filterFn);
    list = list.filter(p =>
      (p.name || "").toLowerCase().includes(q) || (p.sku || "").toLowerCase().includes(q)).slice(0, 15);
    box.innerHTML = list.length
      ? list.map(p => `
          <div class="ps-row" data-id="${p.id}">
            ${escapeHtmlAdmin(p.name)} <span class="ps-sku">(${escapeHtmlAdmin(p.sku)})</span>${p.is_profile_material ? ' <span class="ps-note">3000mm/ks</span>' : ""}
          </div>`).join("")
      : '<div class="ps-empty">Žádný produkt neodpovídá hledání.</div>';
    box.querySelectorAll(".ps-row").forEach(row => {
      row.onclick = () => {
        onPick(parseInt(row.dataset.id, 10));
        input.value = "";
        box.classList.remove("open");
        box.innerHTML = "";
      };
    });
    box.classList.add("open");
  }
  input.addEventListener("input", render);
  input.addEventListener("focus", () => { if (input.value.trim()) render(); });
  // mala prodleva na blur, aby stihnul proklik na .ps-row (blur by jinak
  // dropdown schoval driv, nez se zpracuje click)
  input.addEventListener("blur", () => setTimeout(() => box.classList.remove("open"), 150));
  return render;
}
