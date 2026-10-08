// ==================== CRM / POPTAVKY (bot5, 2026-07-31) ====================
// Struktura 1:1 klon Podpory vyse - viz api/crm.py.
let crmLeadPollTimer = null;
let crmModalLeadId = null;
let crmModalLeadArchived = false;
let crmModalPollTimer = null;
let crmFilter = { status: "", q: "", assigned_to: "", craftsman_id: "", unread_only: false, archived: false, sort: "newest", page: 1, page_size: 50 };
const CRM_STATUS_LABELS = { nova: "Nová", v_jednani: "V jednání", nabidnuto: "Nabídnuto", vyhrano: "Vyhráno", prohrano: "Prohráno" };
let crmAssignableUsers = [];

// Robert 2026-08-22 (pres bot3, "ať to nezdržuje/nenačítá se zbytečně" -
// rychlost načtení Poptávek): loadCrmLeads() se voláním z crmLeadPollTimer
// opakuje KAŽDÝCH 6s, dokud je admin.html vůbec otevřené (i mimo záložku
// CRM) - dřív pri kazdém tomhle behu natvrdo dofetchoval i dashboard karty
// (GET /api/admin/crm/dashboard, 3 SQL dotazy). Vypínatelné - čistě UI
// preference admina (ne sdílený stav), localStorage staci, DB/API zbytecne.
let crmDashEnabled = localStorage.getItem("crm_dash_enabled") !== "0"; // vychozi zapnuto (zachovava puvodni chovani)
function crmApplyDashToggleUI() {
  document.getElementById("crmDashToggle").checked = crmDashEnabled;
  document.getElementById("crmDashCards").style.display = crmDashEnabled ? "" : "none";
}

function crmFmtTime(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleString("cs-CZ", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
}

async function loadCrmAssignableUsers() {
  try {
    const r = await fetch("/api/admin/crm/assignable-users");
    if (!r.ok) return;
    const data = await r.json();
    crmAssignableUsers = data.users || [];
    const opts = crmAssignableUsers.map(u => `<option value="${u.id}">${escapeHtmlAdmin(u.name || u.email)}</option>`).join("");
    document.getElementById("crmFilterAssignedTo").innerHTML = '<option value="">Přiřazeno: kdokoli</option>' + opts;
    document.getElementById("crmModalAssignedTo").innerHTML = '<option value="">Nepřiřazeno</option>' + opts;
  } catch (e) { /* ticho - filtr/vyber jen zustane prazdny */ }
}

// Modul 3 (bot11 2026-08-19) - filtr poptavek podle remeslnika, viz
// REMESLO_KONCEPT.md. Stejny nacitaci vzor jako loadCrmAssignableUsers
// vyse, jen jiny zdroj dat (remeslo_craftsmen misto app_users).
async function loadCrmCraftsmenFilter() {
  try {
    const r = await fetch("/api/remeslo/craftsmen");
    if (!r.ok) return;
    const data = await r.json();
    const opts = (data.craftsmen || []).map(c => `<option value="${c.id}">${escapeHtmlAdmin(c.name)}</option>`).join("");
    document.getElementById("crmFilterCraftsman").innerHTML = '<option value="">Řemeslník: kdokoli</option>' + opts;
    document.getElementById("crmModalCraftsman").innerHTML = '<option value="">Bez řemeslníka</option>' + opts;
  } catch (e) { /* ticho - filtr jen zustane prazdny */ }
}

async function loadCrmDashboard() {
  try {
    const r = await fetch("/api/admin/crm/dashboard");
    if (!r.ok) return;
    const data = await r.json();
    const cards = [
      { label: "Hodnota pipeline", value: crmFmtMoney(data.pipeline_value) },
      { label: "Win rate (tento měsíc)", value: data.win_rate == null ? "—" : `${data.win_rate} %` },
      { label: "Vyhráno / prohráno (měsíc)", value: `${data.month_won} / ${data.month_lost}` },
      { label: "Zpožděné úkoly", value: data.overdue_tasks, warn: data.overdue_tasks > 0 },
    ];
    document.getElementById("crmDashCards").innerHTML = cards.map(c => `
      <div class="dash-card${c.warn ? " warn" : ""}">
        <div class="dc-label">${c.label}</div>
        <div class="dc-value">${c.value}</div>
      </div>
    `).join("");
  } catch (e) { /* ticho - dashboard karty jen zustanou prazdne */ }
}

function renderCrmStatusTabs(statusCounts, archivedCount) {
  const total = Object.values(statusCounts).reduce((a, b) => a + b, 0);
  // Zalozka Archiv (Robert 2026-08-06: "testovaci poptavky automaticky
  // archivujme") - archivovane poptavky ziji jen tady, bezne zalozky
  // je neukazuji (backend filtruje archived=0).
  const defs = [{ key: "", label: "Vše", count: total }].concat(
    Object.keys(CRM_STATUS_LABELS).map(k => ({ key: k, label: CRM_STATUS_LABELS[k], count: statusCounts[k] || 0 })),
    [{ key: "__archiv", label: "🗄 Archiv", count: archivedCount || 0 }]
  );
  const wrap = document.getElementById("crmStatusTabs");
  wrap.innerHTML = defs.map(d => {
    const active = d.key === "__archiv" ? crmFilter.archived : (!crmFilter.archived && crmFilter.status === d.key);
    return `<button type="button" class="order-tab-btn${active ? " active" : ""}" data-key="${d.key}">${d.label}<span class="otc">(${d.count})</span></button>`;
  }).join("");
  wrap.querySelectorAll(".order-tab-btn").forEach(btn => {
    btn.onclick = () => {
      if (btn.dataset.key === "__archiv") {
        crmFilter.archived = true;
        crmFilter.status = "";
      } else {
        crmFilter.archived = false;
        crmFilter.status = btn.dataset.key;
      }
      crmFilter.page = 1;
      loadCrmLeads();
    };
  });
}

let crmLeadCache = [];
let crmSelectedIds = new Set();
async function loadCrmLeads() {
  try {
    const params = new URLSearchParams({ page: crmFilter.page, page_size: crmFilter.page_size });
    if (crmFilter.status) params.set("status", crmFilter.status);
    if (crmFilter.q) params.set("q", crmFilter.q);
    if (crmFilter.assigned_to) params.set("assigned_to", crmFilter.assigned_to);
    if (crmFilter.craftsman_id) params.set("craftsman_id", crmFilter.craftsman_id);
    if (crmFilter.unread_only) params.set("unread_only", "1");
    if (crmFilter.archived) params.set("archived", "1");
    const r = await fetch(`/api/admin/crm/leads?${params.toString()}`);
    if (!r.ok) throw new Error("HTTP " + r.status);
    const data = await r.json();
    renderCrmStatusTabs(data.status_counts || {}, data.archived_count || 0);
    crmLeadCache = data.leads || [];
    crmSelectedIds.clear();
    renderCrmLeadTable();
    updateCrmBulkToolbar();
    const badge = document.getElementById("crmNavBadge");
    const n = data.unread_count || 0;
    badge.textContent = n;
    badge.classList.toggle("show", n > 0);
    renderPager("crmLeadPager", data, crmFilter, loadCrmLeads);
    if (crmDashEnabled) loadCrmDashboard();
  } catch (e) {
    document.getElementById("crmLeadErr").textContent = "Chyba načtení: " + e.message;
  }
}

function crmAssigneeName(id) {
  const u = crmAssignableUsers.find(u => u.id === id);
  return u ? (u.name || u.email) : "—";
}

function crmFmtMoney(v) {
  return v == null ? "—" : `${Number(v).toLocaleString("cs-CZ")} Kč`;
}

function renderCrmLeadTable() {
  const tbody = document.getElementById("crmLeadTbody");
  tbody.innerHTML = crmLeadCache.map(l => `
    <tr class="${l.unread_by_admin ? 'unread' : ''}" data-id="${l.id}" style="cursor:pointer;">
      <td><input type="checkbox" class="crm-chk" data-id="${l.id}" ${crmSelectedIds.has(l.id) ? "checked" : ""}></td>
      <td>${escapeHtmlAdmin(l.contact_name || l.contact_email)}</td>
      <td>${escapeHtmlAdmin(l.contact_email || "")}</td>
      <td>${escapeHtmlAdmin(l.subject || "") || '<span style="color:#8b93a1;">–</span>'}
        ${l.last_message_preview ? `<div style="font-size:11px;color:#8b93a1;margin-top:2px;" title="Poslední zpráva ve vlákně">💬 ${escapeHtmlAdmin(l.last_message_preview)}</div>` : ""}</td>
      <td>${escapeHtmlAdmin(l.company_name || "")}</td>
      <td>${crmFmtMoney(l.estimated_value)}</td>
      <td>${CRM_STATUS_LABELS[l.status] || l.status}</td>
      <td>${l.assigned_to ? escapeHtmlAdmin(crmAssigneeName(l.assigned_to)) : "—"}</td>
      <td>${crmFmtTime(l.last_message_at)}</td>
      <td>${l.next_task_title
        ? `${escapeHtmlAdmin(l.next_task_title)}${l.next_task_due_at
            ? `<div style="font-size:11px;${new Date(l.next_task_due_at) < new Date() ? "color:var(--error,#e05d5d);" : "color:#8b93a1;"}">${crmFmtDue(l.next_task_due_at)}</div>`
            : ""}`
        : '<span style="color:#8b93a1;">–</span>'}</td>
    </tr>
  `).join("") || '<tr><td colspan="10" style="color:#8b93a1;">Žádné poptávky neodpovídají filtru.</td></tr>';
  tbody.querySelectorAll("tr[data-id]").forEach(tr => {
    tr.onclick = (e) => { if (e.target.closest("input")) return; openCrmModal(parseInt(tr.dataset.id, 10)); };
  });
  tbody.querySelectorAll(".crm-chk").forEach(chk => {
    chk.onchange = () => {
      const id = parseInt(chk.dataset.id, 10);
      if (chk.checked) crmSelectedIds.add(id); else crmSelectedIds.delete(id);
      updateCrmBulkToolbar();
    };
  });
}

function updateCrmBulkToolbar() {
  const bar = document.getElementById("crmBulkToolbar");
  const count = crmSelectedIds.size;
  bar.classList.toggle("active", count > 0);
  document.getElementById("crmBulkCount").textContent = `${count} vybráno`;
}
document.getElementById("crmSelectAll").onchange = (e) => {
  if (e.target.checked) crmLeadCache.forEach(l => crmSelectedIds.add(l.id));
  else crmSelectedIds.clear();
  renderCrmLeadTable();
  updateCrmBulkToolbar();
};
document.getElementById("crmBulkApplyStatus").onclick = async () => {
  if (!crmSelectedIds.size) return;
  await fetch("/api/admin/crm/leads/bulk-status", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ids: [...crmSelectedIds], status: document.getElementById("crmBulkStatusSelect").value }),
  });
  loadCrmLeads();
};
document.getElementById("crmBulkDelete").onclick = async () => {
  if (!crmSelectedIds.size) return;
  if (!confirm(`Opravdu smazat ${crmSelectedIds.size} poptávek? Tuto akci nelze vrátit zpět.`)) return;
  await fetch("/api/admin/crm/leads/bulk", {
    method: "DELETE", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ids: [...crmSelectedIds] }),
  });
  loadCrmLeads();
};

document.getElementById("crmSearchApply").onclick = () => {
  crmFilter.q = document.getElementById("crmSearchQ").value.trim();
  crmFilter.assigned_to = document.getElementById("crmFilterAssignedTo").value;
  crmFilter.craftsman_id = document.getElementById("crmFilterCraftsman").value;
  crmFilter.unread_only = document.getElementById("crmFilterUnreadOnly").checked;
  crmFilter.page = 1;
  loadCrmLeads();
};
document.getElementById("crmSearchReset").onclick = () => {
  document.getElementById("crmSearchQ").value = "";
  document.getElementById("crmFilterAssignedTo").value = "";
  document.getElementById("crmFilterCraftsman").value = "";
  document.getElementById("crmFilterUnreadOnly").checked = false;
  crmFilter = { status: crmFilter.status, q: "", assigned_to: "", craftsman_id: "", unread_only: false, archived: crmFilter.archived, sort: "newest",
    page: 1, page_size: crmFilter.page_size };
  loadCrmLeads();
};
document.getElementById("crmSearchQ").addEventListener("keydown", (e) => {
  if (e.key === "Enter") { e.preventDefault(); document.getElementById("crmSearchApply").click(); }
});

function openCrmNewLeadModal() {
  ["crmNewContactName", "crmNewContactEmail", "crmNewContactPhone", "crmNewCompanyName", "crmNewSubject", "crmNewValue"]
    .forEach(id => { document.getElementById(id).value = ""; });
  document.getElementById("crmNewLeadErr").textContent = "";
  document.getElementById("crmNewLeadModal").classList.add("open");
}
function closeCrmNewLeadModal() {
  document.getElementById("crmNewLeadModal").classList.remove("open");
}
document.getElementById("btnCrmNewLead").onclick = openCrmNewLeadModal;
document.getElementById("crmNewLeadCancel").onclick = closeCrmNewLeadModal;
document.getElementById("crmNewLeadModal").addEventListener("click", (e) => {
  if (e.target.id === "crmNewLeadModal") closeCrmNewLeadModal();
});

// ---- Nastaveni klasifikace e-mailu (Robert: "panel pro nastavovani
// filtru a klicovych spojeni ktere slouzi k vyhodnocovani") ----
let ccwAllWords = [];

async function loadClassifierWords() {
  const resp = await fetch("/api/admin/crm/classifier/words");
  const data = await resp.json().catch(() => ({}));
  ccwAllWords = data.words || [];
  renderClassifierWords();
}
function renderClassifierWords() {
  const filter = (document.getElementById("ccwFilter").value || "").trim().toLowerCase();
  const rows = ccwAllWords.filter(w => !filter || w.word.includes(filter));
  document.getElementById("ccwTbody").innerHTML = rows.length ? rows.map(w => `
    <tr>
      <td>${escapeHtmlAdmin(w.word)}</td>
      <td class="num">${w.poptavka_count}</td>
      <td class="num">${w.jine_count}</td>
      <td><button class="ccw-del-btn" data-word="${escapeHtmlAdmin(w.word)}">✕</button></td>
    </tr>
  `).join("") : `<tr><td colspan="4" style="color:var(--text-muted);">Žádná slova.</td></tr>`;
  document.getElementById("ccwTbody").querySelectorAll(".ccw-del-btn").forEach(b => {
    b.onclick = async () => {
      await fetch(`/api/admin/crm/classifier/words/${encodeURIComponent(b.dataset.word)}`, { method: "DELETE" });
      loadClassifierWords();
    };
  });
}
document.getElementById("ccwFilter").addEventListener("input", renderClassifierWords);
document.getElementById("btnCcwAdd").onclick = async () => {
  const word = document.getElementById("ccwWord").value.trim();
  if (!word) return;
  const poptavka_count = parseInt(document.getElementById("ccwPoptavka").value, 10) || 0;
  const jine_count = parseInt(document.getElementById("ccwJine").value, 10) || 0;
  await fetch("/api/admin/crm/classifier/words", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ word, poptavka_count, jine_count }),
  });
  document.getElementById("ccwWord").value = "";
  document.getElementById("ccwPoptavka").value = "";
  document.getElementById("ccwJine").value = "";
  loadClassifierWords();
};

async function loadClassifierSenderRules() {
  const resp = await fetch("/api/admin/crm/classifier/sender-rules");
  const data = await resp.json().catch(() => ({}));
  const rules = data.rules || [];
  const typeLabels = { ignore: "Ignorovat", force_poptavka: "Vždy poptávka", force_shop_related: "Vždy Emaily příchozí", force_objednavka: "Vždy objednávka (propojit)" };
  document.getElementById("ccrTbody").innerHTML = rules.length ? rules.map(r => `
    <tr>
      <td>${escapeHtmlAdmin(r.pattern)}</td>
      <td>${typeLabels[r.rule_type] || r.rule_type}</td>
      <td>${escapeHtmlAdmin(r.note || "")}</td>
      <td><button class="ccr-del-btn" data-id="${r.id}">✕</button></td>
    </tr>
  `).join("") : `<tr><td colspan="4" style="color:var(--text-muted);">Žádné výjimky.</td></tr>`;
  document.getElementById("ccrTbody").querySelectorAll(".ccr-del-btn").forEach(b => {
    b.onclick = async () => {
      await fetch(`/api/admin/crm/classifier/sender-rules/${b.dataset.id}`, { method: "DELETE" });
      loadClassifierSenderRules();
    };
  });
}
document.getElementById("btnCcrAdd").onclick = async () => {
  const pattern = document.getElementById("ccrPattern").value.trim();
  if (!pattern) return;
  const rule_type = document.getElementById("ccrType").value;
  const note = document.getElementById("ccrNote").value.trim();
  const resp = await fetch("/api/admin/crm/classifier/sender-rules", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ pattern, rule_type, note }),
  });
  if (!resp.ok) { const d = await resp.json().catch(() => ({})); alert(d.error || "Nepodařilo se přidat pravidlo."); return; }
  document.getElementById("ccrPattern").value = "";
  document.getElementById("ccrNote").value = "";
  loadClassifierSenderRules();
};

async function loadClassifierSettings() {
  const resp = await fetch("/api/admin/crm/classifier/settings");
  const s = await resp.json().catch(() => ({}));
  document.getElementById("ccsAppUsers").checked = !!s.check_app_users;
  document.getElementById("ccsShopCustomers").checked = !!s.check_shop_customers;
  document.getElementById("ccsShopOrders").checked = !!s.check_shop_orders;
  document.getElementById("ccsSupportConversations").checked = !!s.check_support_conversations;
}
function saveClassifierSettings() {
  fetch("/api/admin/crm/classifier/settings", {
    method: "PUT", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      check_app_users: document.getElementById("ccsAppUsers").checked,
      check_shop_customers: document.getElementById("ccsShopCustomers").checked,
      check_shop_orders: document.getElementById("ccsShopOrders").checked,
      check_support_conversations: document.getElementById("ccsSupportConversations").checked,
    }),
  });
}
["ccsAppUsers", "ccsShopCustomers", "ccsShopOrders", "ccsSupportConversations"].forEach(id => {
  document.getElementById(id).addEventListener("change", saveClassifierSettings);
});

function openCrmClassifierModal() {
  loadClassifierWords();
  loadClassifierSenderRules();
  loadClassifierSettings();
  document.getElementById("crmClassifierModal").classList.add("open");
}
document.getElementById("btnCrmClassifierSettings").onclick = openCrmClassifierModal;
document.getElementById("btnCrmClassifierClose").onclick = () => {
  document.getElementById("crmClassifierModal").classList.remove("open");
};
document.getElementById("crmClassifierModal").addEventListener("click", (e) => {
  if (e.target.id === "crmClassifierModal") document.getElementById("crmClassifierModal").classList.remove("open");
});
document.getElementById("crmNewLeadSave").onclick = async () => {
  const contact_email = document.getElementById("crmNewContactEmail").value.trim();
  const errEl = document.getElementById("crmNewLeadErr");
  if (!contact_email) { errEl.textContent = "E-mail je povinný."; return; }
  const payload = {
    contact_email,
    contact_name: document.getElementById("crmNewContactName").value.trim(),
    contact_phone: document.getElementById("crmNewContactPhone").value.trim(),
    company_name: document.getElementById("crmNewCompanyName").value.trim(),
    subject: document.getElementById("crmNewSubject").value.trim(),
    estimated_value: document.getElementById("crmNewValue").value || null,
  };
  try {
    const r = await fetch("/api/admin/crm/leads", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
    });
    const data = await r.json();
    if (!r.ok) { errEl.textContent = data.error || "Chyba."; return; }
    closeCrmNewLeadModal();
    loadCrmLeads();
    openCrmModal(data.id);
  } catch (e) {
    errEl.textContent = "Chyba: " + e.message;
  }
};

function crmRenderModalLog(messages) {
  const log = document.getElementById("crmModalLog");
  // sig + stickToBottom + HTML bubliny - stejny duvod/vzor jako v
  // supportRenderModalLog vyse ("roluje se to samo porad dole" + "dejme
  // tomu nejaky format tabulky").
  // email_status v sig taky - meni se casem (pending -> sent/failed po
  // schvaleni v Emaily odchozí), i kdyz se seznam ID zprav nezmeni
  // (Robert 2026-08-24: "fajfka pokud je odpoved odeslana").
  const sig = (messages || []).map(m => `${m.id}:${m.email_status || ""}`).join(",");
  if (log.dataset.everLoaded === "1" && log.dataset.sig === sig) return;
  const stick = log.dataset.everLoaded !== "1" || (log.scrollHeight - log.scrollTop - log.clientHeight) < 40;
  const EMAIL_STATUS_ICONS = {
    sent: '<span title="E-mail odeslán" style="color:var(--success);">✓</span>',
    pending: '<span title="E-mail čeká na schválení v Emaily odchozí" style="color:var(--warn);">⏳</span>',
    failed: '<span title="E-mail se nepodařilo odeslat" style="color:var(--error);">✗</span>',
  };
  log.innerHTML = (messages || []).map(m => {
    const cls = m.sender_type === "operator" ? "operator" : "contact";
    const who = m.sender_type === "operator" ? (m.sender_name || "Operátor") : (m.sender_name || "Kontakt");
    const emailIcon = m.email_status ? ` ${EMAIL_STATUS_ICONS[m.email_status] || ""}` : "";
    const meta = `<span class="support-msg-meta">${escapeHtmlAdmin(who)} · ${crmFmtTime(m.created_at)}${emailIcon}</span>`;
    if (m.body_html) {
      return `<div class="support-msg ${cls} html-msg" data-html-msg-id="${m.id}"><div class="support-msg-htmlbox"></div>${meta}</div>`;
    }
    // normalizeEmailBody - stejny duvod jako v supportRenderModalLog
    // (rozstrikany plain-text tabulkovych e-mailu bez body_html)
    const esc = normalizeEmailBody(m.body).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    return `<div class="support-msg ${cls}">${esc}${meta}</div>`;
  }).join("");
  hydrateHtmlMessageBubbles(log, messages);
  log.dataset.everLoaded = "1";
  log.dataset.sig = sig;
  if (stick) log.scrollTop = log.scrollHeight;
}

async function loadCrmModalThread() {
  if (!crmModalLeadId) return;
  // bot23 2026-08-18: stejna race condition jako loadSupportModalThread
  // (viz komentar tam) - reqId zachyti, pro ktery lead tenhle fetch byl.
  const reqId = crmModalLeadId;
  try {
    const r = await fetch(`/api/admin/crm/leads/${reqId}/messages`);
    if (reqId !== crmModalLeadId) return;
    if (!r.ok) throw new Error("HTTP " + r.status);
    const data = await r.json();
    if (reqId !== crmModalLeadId) return;
    document.getElementById("crmModalMeta").textContent =
      `${data.lead.contact_name || data.lead.contact_email} · ${data.lead.contact_email || ""}${data.lead.company_name ? " · " + data.lead.company_name : ""}`;
    document.getElementById("crmModalStatus").value = data.lead.status;
    document.getElementById("crmModalAssignedTo").value = data.lead.assigned_to || "";
    document.getElementById("crmModalCraftsman").value = data.lead.craftsman_id || "";
    if (document.activeElement !== document.getElementById("crmModalValue")) {
      document.getElementById("crmModalValue").value = data.lead.estimated_value == null ? "" : data.lead.estimated_value;
    }
    // tlacitko archivace odrazi aktualni stav (auto-archivace testovacich
    // poptavek, Robert 2026-08-06)
    crmModalLeadArchived = !!data.lead.archived;
    document.getElementById("btnCrmModalArchive").textContent = crmModalLeadArchived ? "↩ Obnovit z archivu" : "🗄 Archivovat";
    renderCrmModalQuote(data.quote);
    crmRenderModalLog(data.messages);
    loadCrmLeads();
  } catch (e) {
    document.getElementById("crmModalMeta").textContent = "Chyba načtení: " + e.message;
  }
}

function renderCrmModalQuote(quote) {
  const wrap = document.getElementById("crmModalQuote");
  if (quote) {
    wrap.innerHTML = `<button id="btnCrmOpenQuote" style="background:none;border:1px solid var(--accent);color:var(--accent);">📁 Otevřít nabídku ${escapeHtmlAdmin(quote.quote_number)}</button>`;
    document.getElementById("btnCrmOpenQuote").onclick = () => {
      closeCrmModal();
      document.querySelector('.tab-btn[data-tab="quotes"]').click();
      openQuoteDetail(quote.id);
    };
  } else {
    wrap.innerHTML = `<button id="btnCrmCreateQuote" style="background:none;border:1px solid var(--accent);color:var(--accent);">+ Vytvořit nabídku</button>`;
    document.getElementById("btnCrmCreateQuote").onclick = async () => {
      if (!crmModalLeadId) return;
      const btn = document.getElementById("btnCrmCreateQuote");
      btn.disabled = true;
      try {
        const r = await fetch(`/api/admin/crm/leads/${crmModalLeadId}/create-quote`, { method: "POST" });
        const data = await r.json();
        if (!r.ok) throw new Error(data.error || "HTTP " + r.status);
        loadCrmModalThread();
      } catch (e) {
        alert("Vytvoření nabídky se nezdařilo: " + e.message);
      } finally {
        btn.disabled = false;
      }
    };
  }
}

function crmFmtDue(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleString("cs-CZ", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

async function loadCrmModalTasks() {
  if (!crmModalLeadId) return;
  try {
    const r = await fetch(`/api/admin/crm/leads/${crmModalLeadId}/tasks`);
    if (!r.ok) return;
    const data = await r.json();
    const now = new Date();
    const wrap = document.getElementById("crmModalTasks");
    wrap.innerHTML = (data.tasks || []).map(t => {
      const overdue = !t.done && t.due_at && new Date(t.due_at) < now;
      return `<div class="crm-task-row${t.done ? " done" : ""}" data-id="${t.id}">
        <input type="checkbox" class="crm-task-chk" data-id="${t.id}" ${t.done ? "checked" : ""}>
        <span class="crm-task-title">${escapeHtmlAdmin(t.title)}</span>
        <span class="crm-task-due${overdue ? " overdue" : ""}">${crmFmtDue(t.due_at)}</span>
        <button class="crm-del-btn" data-id="${t.id}" title="Smazat úkol">✕</button>
      </div>`;
    }).join("") || '<div style="color:#8b93a1;font-size:12px;">Žádné úkoly.</div>';
    wrap.querySelectorAll(".crm-task-chk").forEach(chk => {
      chk.onchange = async () => {
        await fetch(`/api/admin/crm/leads/${crmModalLeadId}/tasks/${chk.dataset.id}`, {
          method: "PUT", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ done: chk.checked }),
        });
        loadCrmModalTasks();
      };
    });
    wrap.querySelectorAll(".crm-del-btn").forEach(btn => {
      btn.onclick = async () => {
        await fetch(`/api/admin/crm/leads/${crmModalLeadId}/tasks/${btn.dataset.id}`, { method: "DELETE" });
        loadCrmModalTasks();
      };
    });
  } catch (e) { /* ticho - sekce jen zustane jak byla */ }
}

async function loadCrmModalNotes() {
  if (!crmModalLeadId) return;
  try {
    const r = await fetch(`/api/admin/crm/leads/${crmModalLeadId}/notes`);
    if (!r.ok) return;
    const data = await r.json();
    const wrap = document.getElementById("crmModalNotes");
    wrap.innerHTML = (data.notes || []).map(n => `
      <div class="crm-note-row" data-id="${n.id}">
        <span class="crm-note-body">${escapeHtmlAdmin(n.body)}</span>
        <span class="crm-note-meta">${escapeHtmlAdmin(n.author_name || "")} · ${crmFmtTime(n.created_at)}</span>
        <button class="crm-del-btn" data-id="${n.id}" title="Smazat poznámku">✕</button>
      </div>
    `).join("") || '<div style="color:#8b93a1;font-size:12px;">Žádné poznámky.</div>';
    wrap.querySelectorAll(".crm-del-btn").forEach(btn => {
      btn.onclick = async () => {
        await fetch(`/api/admin/crm/leads/${crmModalLeadId}/notes/${btn.dataset.id}`, { method: "DELETE" });
        loadCrmModalNotes();
      };
    });
  } catch (e) { /* ticho - sekce jen zustane jak byla */ }
}

document.getElementById("btnCrmAddTask").onclick = async () => {
  if (!crmModalLeadId) return;
  const titleEl = document.getElementById("crmNewTaskTitle");
  const dueEl = document.getElementById("crmNewTaskDue");
  const title = titleEl.value.trim();
  if (!title) return;
  await fetch(`/api/admin/crm/leads/${crmModalLeadId}/tasks`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title, due_at: dueEl.value ? dueEl.value.replace("T", " ") + ":00" : null }),
  });
  titleEl.value = ""; dueEl.value = "";
  loadCrmModalTasks();
};
document.getElementById("btnCrmAddNote").onclick = async () => {
  if (!crmModalLeadId) return;
  const bodyEl = document.getElementById("crmNewNoteBody");
  const body = bodyEl.value.trim();
  if (!body) return;
  await fetch(`/api/admin/crm/leads/${crmModalLeadId}/notes`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ body }),
  });
  bodyEl.value = "";
  loadCrmModalNotes();
};
document.getElementById("crmModalValue").addEventListener("change", async (e) => {
  if (!crmModalLeadId) return;
  await fetch(`/api/admin/crm/leads/${crmModalLeadId}`, {
    method: "PUT", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ estimated_value: e.target.value === "" ? null : e.target.value }),
  });
  loadCrmLeads();
});

function openCrmModal(leadId) {
  crmModalLeadId = leadId;
  document.getElementById("crmModalReply").value = "";
  document.getElementById("crmModalConvertResult").innerHTML = "";
  delete document.getElementById("crmModalLog").dataset.everLoaded;
  document.getElementById("crmModal").classList.add("open");
  loadCrmModalThread();
  loadCrmModalTasks();
  loadCrmModalNotes();
  renderGalleryModule(document.getElementById("crmModalGallery"), "lead", leadId);
  clearInterval(crmModalPollTimer);
  crmModalPollTimer = setInterval(() => { loadCrmModalThread(); loadCrmModalTasks(); }, 3000);
}

function closeCrmModal() {
  document.getElementById("crmModal").classList.remove("open");
  crmModalLeadId = null;
  clearInterval(crmModalPollTimer);
}

async function sendCrmReply() {
  const body = document.getElementById("crmModalReply").value.trim();
  if (!body || !crmModalLeadId) return;
  const btn = document.getElementById("btnCrmModalSend");
  btn.disabled = true;
  try {
    const r = await fetch(`/api/admin/crm/leads/${crmModalLeadId}/reply`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ body }),
    });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(data.error || ("HTTP " + r.status));
    document.getElementById("crmModalReply").value = "";
    loadCrmModalThread();
    // Robert 2026-08-24: odpoved z poptavky VZDY ceka ve schvalovaci
    // fronte (auto=True) - admin ji jeste musi schvalit v "Emaily
    // odchozí", at ji sam napsal kdokoliv. Jasne to oznamit, at nikdo
    // neceka, ze se odeslalo hned (presne ten puvodni bug, jen teď
    // zdůrazněno opačným směrem).
    if (data.email_status === "pending") {
      alert("Zpráva je uložená ve vlákně. E-mail zákazníkovi ČEKÁ na schválení v záložce \"Emaily odchozí\" - tam ho musíš potvrdit, než skutečně odejde.");
    } else if (data.email_status === "failed") {
      alert("Zpráva je uložená ve vlákně, ALE e-mail se nepodařilo odeslat: " + (data.email_error || "neznámá chyba") +
            "\nZkontroluj záložku \"Emaily odchozí\".");
    }
  } catch (e) {
    alert("Chyba odeslání: " + e.message);
  } finally {
    btn.disabled = false;
  }
}

document.getElementById("crmModalStatus").onchange = async (e) => {
  if (!crmModalLeadId) return;
  await fetch(`/api/admin/crm/leads/${crmModalLeadId}`, {
    method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ status: e.target.value }),
  });
  loadCrmLeads();
};
document.getElementById("crmModalAssignedTo").onchange = async (e) => {
  if (!crmModalLeadId) return;
  await fetch(`/api/admin/crm/leads/${crmModalLeadId}`, {
    method: "PUT", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ assigned_to: e.target.value ? parseInt(e.target.value, 10) : null }),
  });
  loadCrmLeads();
};
document.getElementById("crmModalCraftsman").onchange = async (e) => {
  if (!crmModalLeadId) return;
  await fetch(`/api/admin/crm/leads/${crmModalLeadId}`, {
    method: "PUT", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ craftsman_id: e.target.value ? parseInt(e.target.value, 10) : null }),
  });
  loadCrmLeads();
};

document.getElementById("btnCrmModalConvert").onclick = async () => {
  if (!crmModalLeadId) return;
  const resultEl = document.getElementById("crmModalConvertResult");
  resultEl.textContent = "Hledám shodu…";
  try {
    const r = await fetch(`/api/admin/crm/leads/${crmModalLeadId}/convert`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({}),
    });
    const data = await r.json();
    if (!r.ok) { resultEl.textContent = data.error || "Chyba."; return; }
    if (data.status === "ok") {
      resultEl.innerHTML = `Propojeno se zákazníkem #${data.customer_id}.`;
    } else if (data.status === "created") {
      resultEl.innerHTML = `Vytvořen nový zákazník #${data.customer_id} z údajů v e-mailu`
        + (data.prefill.company_name ? ` (${escapeHtmlAdmin(data.prefill.company_name)})` : "") + ".";
    } else if (data.status === "suggestions") {
      resultEl.innerHTML = "Možná shoda:<br>" + data.duplicate_suggestions.map(s =>
        `${escapeHtmlAdmin(s.full_name || s.account_email)} (${escapeHtmlAdmin(s.email || s.account_email)}) `
        + `<button class="crm-link-btn" data-cid="${s.customer_id}">Propojit</button>`
      ).join("<br>");
      resultEl.querySelectorAll(".crm-link-btn").forEach(btn => {
        btn.onclick = async () => {
          await fetch(`/api/admin/crm/leads/${crmModalLeadId}/convert`, {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ customer_id: parseInt(btn.dataset.cid, 10) }),
          });
          resultEl.textContent = "Propojeno.";
        };
      });
    } else {
      resultEl.textContent = "Žádná shoda - jde založit nový zákaznický profil ručně (záložka Zákazníci) s předvyplněnými údaji: "
        + `${data.prefill.full_name || ""} <${data.prefill.email || ""}>`;
    }
  } catch (e) {
    resultEl.textContent = "Chyba: " + e.message;
  }
};

async function rejectCrmLead() {
  if (!crmModalLeadId) return;
  if (!confirm("Přesunout tuto poptávku do Podpory? Zmizí ze záložky Poptávky a systém se z toho poučí pro příští klasifikaci.")) return;
  const btn = document.getElementById("btnCrmModalReject");
  btn.disabled = true;
  try {
    const r = await fetch(`/api/admin/crm/leads/${crmModalLeadId}/reject`, { method: "POST" });
    const data = await r.json();
    if (!r.ok) throw new Error(data.error || "HTTP " + r.status);
    closeCrmModal();
    loadCrmLeads();
  } catch (e) {
    alert("Přesun se nezdařil: " + e.message);
  } finally {
    btn.disabled = false;
  }
}

document.getElementById("btnCrmModalReject").onclick = rejectCrmLead;
document.getElementById("btnCrmModalArchive").onclick = async () => {
  if (!crmModalLeadId) return;
  const r = await fetch(`/api/admin/crm/leads/${crmModalLeadId}`, {
    method: "PUT", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ archived: !crmModalLeadArchived }),
  });
  if (!r.ok) { alert("Archivace se nezdařila."); return; }
  closeCrmModal();
  loadCrmLeads();
};
document.getElementById("btnCrmModalClose").onclick = closeCrmModal;
document.getElementById("btnCrmModalSend").onclick = sendCrmReply;
document.getElementById("crmModalReply").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendCrmReply(); }
});
document.getElementById("crmModal").addEventListener("click", (e) => {
  if (e.target.id === "crmModal") closeCrmModal();
});
document.getElementById("crmDashToggle").onchange = (e) => {
  crmDashEnabled = e.target.checked;
  localStorage.setItem("crm_dash_enabled", crmDashEnabled ? "1" : "0");
  crmApplyDashToggleUI();
  if (crmDashEnabled) loadCrmDashboard();
};
crmApplyDashToggleUI();

loadCrmAssignableUsers();
loadCrmCraftsmenFilter();
crmLeadPollTimer = setInterval(loadCrmLeads, 6000);

// ==================== SDILENY DISK (bot5, 2026-08-01) ====================
// Robert: "na google drive máme sdílené složky a chci je tam zrušit a
// vést sdílený disk (složky prostě uložiště) na našem serveru" - viz
// api/drive.py. JEDEN globalni strom (na rozdil od Nabidek zadne
// "korenove" id) - stejny strom/obsah UI vzor jako quoteFolderTree/
// quoteFolderContents nize, ale bez scopovani na quote_id.
let driveData = null;
let driveSelectedFolderId = null; // null = koren disku
let driveSelectedFileIds = new Set(); // bulk mazani souboru (fajky)
// Robert 2026-09-26 ("proč to nemá bulk zaškrtávátka? opravit" - u
// podslozek v aktualni slozce, ne zamena za driveSelectedFolderId
// vyse, ktere je "ktera slozka je zrovna OTEVRENA"): stejny vzor jako
// driveSelectedFileIds, ale ZVLAST - slozky a soubory se mazou jinym
// endpointem a nema smysl je slucovat do jednoho seznamu/tlacitka.
let driveSelectedSubfolderIds = new Set();
// Robert 2026-08-10 ("chci moznost... zobrazovat ikony cca 250x250px") -
// prepinac zobrazeni Sdileneho disku: "list" (puvodni radkovy seznam)
// nebo "icons" (ctvercova karta 250x250, obrazkove soubory ukazuji
// skutecny nahled). Zustava jen v pameti (ne perzistovano na serveru) -
// staci pro jednu session, staci prepinat kdyz je to potreba.
let driveViewMode = "list";
function driveIsImageFile(f) {
  return !!(f.content_type && f.content_type.startsWith("image/"));
}
// Robert 2026-09-23 ("nemuzu je prece rucne stahovat abych se podíval!"):
// fullscreen nahled obrazku primo v adminu s Prev/Next mezi VSEMI obrazky
// aktualni slozky - drive uz obrazek servíruje spravne pres /download (viz
// komentar u fileRowsIcons nize), tohle jen pridava vetsi zobrazeni + rychle
// prolistovani, aniz by se cokoli stahovalo na disk.
let driveLightboxFiles = [];
let driveLightboxIndex = 0;
function driveLightboxRender() {
  const f = driveLightboxFiles[driveLightboxIndex];
  if (!f) return;
  const el = document.getElementById("driveLightbox");
  el.querySelector("img").src = `/api/admin/drive/files/${f.id}/download`;
  el.querySelector(".dlb-caption").textContent = f.filename;
  el.querySelector(".dlb-counter").textContent = `${driveLightboxIndex + 1} / ${driveLightboxFiles.length}`;
}
function driveOpenLightbox(imageFiles, startIndex) {
  driveLightboxFiles = imageFiles;
  driveLightboxIndex = startIndex;
  let el = document.getElementById("driveLightbox");
  if (!el) {
    el = document.createElement("div");
    el.id = "driveLightbox";
    el.innerHTML = `
      <button class="dlb-close" title="Zavřít (Esc)">×</button>
      <button class="dlb-nav dlb-prev" title="Předchozí (←)">‹</button>
      <img alt="">
      <button class="dlb-nav dlb-next" title="Další (→)">›</button>
      <div class="dlb-caption"></div>
      <div class="dlb-counter"></div>`;
    document.body.appendChild(el);
    el.querySelector(".dlb-close").onclick = driveCloseLightbox;
    el.addEventListener("click", (e) => { if (e.target === el) driveCloseLightbox(); });
    el.querySelector(".dlb-prev").onclick = () => driveLightboxStep(-1);
    el.querySelector(".dlb-next").onclick = () => driveLightboxStep(1);
  }
  el.style.display = "flex";
  driveLightboxRender();
}
function driveLightboxStep(delta) {
  if (!driveLightboxFiles.length) return;
  driveLightboxIndex = (driveLightboxIndex + delta + driveLightboxFiles.length) % driveLightboxFiles.length;
  driveLightboxRender();
}
function driveCloseLightbox() {
  const el = document.getElementById("driveLightbox");
  if (el) el.style.display = "none";
}
document.addEventListener("keydown", (e) => {
  const el = document.getElementById("driveLightbox");
  if (!el || el.style.display !== "flex") return;
  if (e.key === "Escape") driveCloseLightbox();
  else if (e.key === "ArrowLeft") driveLightboxStep(-1);
  else if (e.key === "ArrowRight") driveLightboxStep(1);
});
function driveGenericIcon(f) {
  const ext = (f.filename || "").split(".").pop().toLowerCase();
  if (ext === "pdf") return "📕";
  if (["doc", "docx"].includes(ext)) return "📘";
  if (["xls", "xlsx"].includes(ext)) return "📗";
  if (["zip", "rar", "7z"].includes(ext)) return "🗜️";
  if (["mp4", "mov", "avi", "webm"].includes(ext)) return "🎬";
  return "📄";
}

// Robert 2026-09-09: "chci mit moznost podle vyslednych renderu
// preklikavat ktery hdri se pouzije priste". Ktera mapa je zrovna
// vybrana - nacita se spolu se stromem disku, at u kazdeho .hdr/.exr
// souboru jde ukazat stav i tlacitko.
let driveActiveHdriId = null;
let driveHdriFiles = [];
const DRIVE_HDRI_EXT = [".hdr", ".exr"];
const driveJeHdri = (n) => DRIVE_HDRI_EXT.some(e => (n || "").toLowerCase().endsWith(e));

async function loadDriveTree() {
  try {
    const r = await fetch("/api/admin/drive");
    if (!r.ok) throw new Error("HTTP " + r.status);
    driveData = await r.json();
    try {
      const rh = await fetch("/api/admin/render-hdri");
      if (rh.ok) {
        const rhData = await rh.json();
        driveActiveHdriId = rhData.active_id;
        driveHdriFiles = rhData.files || [];
      }
    } catch (e) { /* vyber HDRI je doplnek - vypadek nesmi shodit cely disk */ }
    renderDriveFolderTree();
    renderDriveFolderContents();
  } catch (e) {
    document.getElementById("driveErr").textContent = "Chyba načtení: " + e.message;
  }
}

function driveFindFolder(folders, id) {
  for (const f of folders) {
    if (f.id === id) return f;
    const found = driveFindFolder(f.children, id);
    if (found) return found;
  }
  return null;
}

// Robert 2026-08-13 ("strukturu disku potrebujeme sbalovaci") - mnozina
// ID rozbalenych slozek. Zive mimo renderDriveFolderTree(), aby
// prekresleni stromu (klik na slozku, pridani nove) stav nezahodilo.
// Vychozi = vse sbalene; cesta k prave vybrane slozce se rozbali sama
// (viz driveExpandPathTo nize), at se vyber nikdy neschova.
let driveExpandedFolderIds = new Set();

// Robert 2026-09-09 ("udelej nahore radek, ktery ukazuje celou cestu k
// souboru") - pri praci s rendery potreboval PRESNOU cestu k .blend
// souboru, aby vedel, ze se renderuje z toho spravneho; ze stromu vlevo
// se dala vycist jen pracne. Vraci retez slozek od korene k cilove.
function drivePathChain(folders, targetId, chain = []) {
  for (const f of folders) {
    if (f.id === targetId) return [...chain, f];
    const found = drivePathChain(f.children || [], targetId, [...chain, f]);
    if (found) return found;
  }
  return null;
}

function driveExpandPathTo(folders, targetId, chain = []) {
  for (const f of folders) {
    if (f.id === targetId) { chain.forEach(id => driveExpandedFolderIds.add(id)); return true; }
    if (driveExpandPathTo(f.children || [], targetId, [...chain, f.id])) return true;
  }
  return false;
}

function renderDriveFolderTree() {
  const wrap = document.getElementById("driveFolderTree");
  const isAdmin = ADMIN_USER && ADMIN_USER.role === "admin";
  const rootActive = driveSelectedFolderId === null;
  let html = `<div class="qf-tree-row${rootActive ? " active" : ""}" data-id="">📁 Kořen disku</div>`;
  // Omezeni podle role (bot4, 2026-08-05) plati jen na TOP-LEVEL slozkach
  // (depth 1) - hlubsi urovne jen zdedi vizualni "locked" stav sveho
  // top-level predka, backend uz vraci children/files prazdne.
  function renderNode(f, depth, inheritedLocked) {
    const active = driveSelectedFolderId === f.id;
    const locked = inheritedLocked || f.locked;
    const gearBtn = depth === 1 && isAdmin
      ? `<button type="button" class="qf-folder-roles-btn" data-id="${f.id}" data-name="${escapeHtmlAdmin(f.name)}" data-roles='${JSON.stringify(f.allowed_roles || [])}' title="Přístup podle role">⚙</button>`
      : "";
    const kids = f.children || [];
    const hasKids = kids.length > 0;
    const expanded = driveExpandedFolderIds.has(f.id);
    const caret = `<span class="qf-tree-caret${hasKids ? "" : " qf-leaf"}" data-caret="${f.id}">${hasKids ? (expanded ? "▼" : "▶") : "•"}</span>`;
    let out = `<div class="qf-tree-row${active ? " active" : ""}${locked ? " qf-locked" : ""}" data-id="${f.id}" style="padding-left:${depth * 14 + 8}px;display:flex;align-items:center;gap:4px;">${caret}<span style="flex:1;overflow:hidden;text-overflow:ellipsis;">${locked ? "🔒" : "📁"} ${escapeHtmlAdmin(f.name)}</span>${gearBtn}</div>`;
    if (expanded) kids.forEach(c => { out += renderNode(c, depth + 1, locked); });
    return out;
  }
  if (driveSelectedFolderId !== null) driveExpandPathTo(driveData.folders, driveSelectedFolderId);
  driveData.folders.forEach(f => { html += renderNode(f, 1, false); });
  wrap.innerHTML = html + `<div class="crm-add-row" style="margin-top:10px;">
      <input type="text" id="driveNewFolderName" placeholder="Nová složka…">
      <button id="btnDriveAddFolder">Přidat</button>
    </div>`;
  wrap.querySelectorAll(".qf-tree-row[data-id]").forEach(row => {
    row.onclick = (e) => {
      if (e.target.closest(".qf-folder-roles-btn")) return;
      // klik na sipku jen sbali/rozbali, vyber slozky nechava byt
      const caret = e.target.closest(".qf-tree-caret");
      if (caret && !caret.classList.contains("qf-leaf")) {
        const cid = parseInt(caret.dataset.caret, 10);
        if (driveExpandedFolderIds.has(cid)) driveExpandedFolderIds.delete(cid);
        else driveExpandedFolderIds.add(cid);
        renderDriveFolderTree();
        return;
      }
      driveSelectedFolderId = row.dataset.id === "" ? null : parseInt(row.dataset.id, 10);
      // vybrana slozka se rovnou rozbali, at jsou podslozky videt bez
      // druheho kliku na sipku
      if (driveSelectedFolderId !== null) driveExpandedFolderIds.add(driveSelectedFolderId);
      renderDriveFolderTree();
      renderDriveFolderContents();
    };
    wireDriveFolderDrag(row);
  });
  wrap.querySelectorAll(".qf-folder-roles-btn").forEach(btn => {
    btn.onclick = (e) => {
      e.stopPropagation();
      openDriveFolderRolesModal(parseInt(btn.dataset.id, 10), btn.dataset.name, JSON.parse(btn.dataset.roles));
    };
  });
  document.getElementById("btnDriveAddFolder").onclick = async () => {
    const nameEl = document.getElementById("driveNewFolderName");
    const name = nameEl.value.trim();
    if (!name) return;
    await fetch("/api/admin/drive/folders", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, parent_folder_id: driveSelectedFolderId }),
    });
    loadDriveTree();
  };
}

// Robert 2026-08-21 ("potřebuji přesouvat složky ve sdilenem disku") -
// tazeni slozky na jinou slozku ji tam presune (parent_folder_id),
// backend (PUT /api/admin/drive/folders/<id>) uz sam hlida cykly a
// ochranu top-level slozek s rolovym omezenim - staci jen zavolat.
// Zjednoduseno oproti obdobnemu vzoru pro kategorie Vlastnich tvaru
// (scene.html wireCsCategoryDrag) - tady jen "pusť NA složku = staň se
// jejím potomkem", zadne before/after razeni sourozencu (backend ho
// stejne nepodporuje, jen name/parent_folder_id).
// Robert ("nahravam soubor a porad se to vraci na zacatek"): pravdepodobne
// tahal soubor primo z plochy/exploreru na stranku (prirozene ocekavani
// po pridani "grag and drop" presunu). Zadne mistu na strance predtim
// nezastavovalo vychozi chovani prohlizece pro drop MIMO konkretni cilova
// mista (jen ta uz vola e.preventDefault() sama) - prohlizec proto
// upuštěný soubor sam OTEVREL/navigoval na nej celou zalozku, coz
// vypadalo jako "vraceni na zacatek" (cely admin se znovu nacetl od
// nuly). Globalni pojistka na urovni dokumentu to zastavi VŠUDE, aniž
// by rusila uz existujici specificke drop handlery (ty si preventDefault
// zavolaji sami driv, nez event probublá az sem).
document.addEventListener("dragover", (e) => e.preventDefault());
document.addEventListener("drop", (e) => e.preventDefault());

// Robert ("kdyz to clovek zahaji... to musi dobehnout i na pozadi"):
// samotny XHR beh (viz driveUploadXhr nize) preziva prepnuti zalozky
// v adminu bez problemu - neni vazany na existenci DOM elementu, jen
// na JS closure v teto funkci. Problem byl jinde: prepnuti NA zalozku
// "Sdílený disk" vola loadDriveTree() (viz "drive" tab-btn handler),
// ktery cely panel prekresli (renderDriveFolderContents) - tim vzniknou
// UPLNE NOVE #btnDriveFileUpload/#driveFileInput/... elementy, ktere
// nevi, ze nekde na pozadi porad bezi upload (nejsou disabled) - klik
// na "Nahrát" by tak spustil DRUHY, nezavisly upload stejneho souboru
// (stejna trida bugu, jakou uz kdysi resilo zamykani tlacitka behem
// jednoho behu - viz komentar u btnDriveFileUpload nize, jen ted pres
// prepnuti zalozky misto dvojkliku). driveUploadState prezije
// prekresleni (modulova promenna, ne DOM) - driveApplyUploadUiState()
// se zavola po KAZDEM renderDriveFolderContents() a obnovi spravny
// (zamknuty/rozjety) vzhled, i kdyz elementy mezitim vznikly znovu.
// Musi sedet s `client_max_body_size` v nginx vhostech, ktere servi
// admin (sites-available/konfigurator + logiman-autovestavby) - tam 1G.
// Trochu nizsi kvuli multipart rezii, at hlasku ukaze radeji klient
// (srozumitelne) nez nginx (zabitim spojeni uprostred nahravani).
const DRIVE_MAX_UPLOAD_BYTES = 1000 * 1024 * 1024;
let driveUploadState = null; // {pct, label} nebo null = nic nebezi
function driveApplyUploadUiState() {
  const btn1 = document.getElementById("btnDriveFileUpload");
  const input1 = document.getElementById("driveFileInput");
  const btn2 = document.getElementById("btnDriveFolderUpload");
  const input2 = document.getElementById("driveFolderInput");
  const statusEl = document.getElementById("driveUploadStatus");
  const progressEl = document.getElementById("driveUploadProgress");
  const running = !!driveUploadState;
  [btn1, input1, btn2, input2].forEach(el => { if (el) el.disabled = running; });
  if (statusEl) statusEl.textContent = running ? driveUploadState.label : "";
  if (progressEl) {
    progressEl.style.display = running ? "" : "none";
    progressEl.value = running ? driveUploadState.pct : 0;
  }
}

let driveDraggedFolderId = null;
// Robert ("chceme umet presouvat soubory mezi slozkami" / "grag and
// drop"): tazeni SOUBORU na slozku (v levem stromu, nebo na podslozkovou
// kartu v obsahu aktualni slozky - viz wireDriveFileDrag/[data-folder-id]
// nize) ho tam presune (PUT /api/admin/drive/files/<id> {folder_id}) -
// stejny princip jako uz existujici tazeni SLOZEK vyse, jen jiny
// endpoint/payload. Oba typy tazeni sdili tyhle rady, aby slo current
// stejnou slozku pustit obojim (soubor i podslozku).
let driveDraggedFileId = null;
async function driveHandleDropOnFolder(targetFolderId) {
  if (driveDraggedFileId != null) {
    const movedId = driveDraggedFileId;
    driveDraggedFileId = null;
    const r = await fetch(`/api/admin/drive/files/${movedId}`, {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ folder_id: targetFolderId }),
    });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) { alert(data.error || "Přesun souboru se nezdařil."); return; }
    loadDriveTree();
    return;
  }
  if (driveDraggedFolderId != null && driveDraggedFolderId !== targetFolderId) {
    const movedId = driveDraggedFolderId;
    driveDraggedFolderId = null;
    const r = await fetch(`/api/admin/drive/folders/${movedId}`, {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ parent_folder_id: targetFolderId }),
    });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) { alert(data.error || "Přesun složky se nezdařil."); return; }
    loadDriveTree();
  }
}
function wireDriveFileDrag(row, fileId) {
  row.draggable = true;
  row.addEventListener("dragstart", (e) => {
    driveDraggedFileId = fileId;
    row.classList.add("drive-drag-source");
    e.dataTransfer.effectAllowed = "move";
    e.dataTransfer.setData("text/plain", String(fileId));
  });
  row.addEventListener("dragend", () => {
    row.classList.remove("drive-drag-source");
    document.querySelectorAll(".drive-drop-target").forEach(el => el.classList.remove("drive-drop-target"));
    driveDraggedFileId = null;
  });
}
function wireDriveFolderDrag(row) {
  const id = row.dataset.id === "" ? null : parseInt(row.dataset.id, 10);
  row.draggable = true;
  row.addEventListener("dragstart", (e) => {
    driveDraggedFolderId = id;
    if (id === null) { e.preventDefault(); driveDraggedFolderId = null; return; } // Kořen se tahat neda
    row.classList.add("qf-drag-source");
    e.dataTransfer.effectAllowed = "move";
    e.dataTransfer.setData("text/plain", String(id));
  });
  row.addEventListener("dragend", () => {
    row.classList.remove("qf-drag-source");
    document.querySelectorAll("#driveFolderTree .qf-drop-target").forEach(el => el.classList.remove("qf-drop-target"));
    driveDraggedFolderId = null;
  });
  row.addEventListener("dragover", (e) => {
    if (driveDraggedFileId == null && (driveDraggedFolderId == null || driveDraggedFolderId === id)) return;
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
    row.classList.add("qf-drop-target");
  });
  row.addEventListener("dragleave", () => row.classList.remove("qf-drop-target"));
  row.addEventListener("drop", async (e) => {
    e.preventDefault();
    row.classList.remove("qf-drop-target");
    await driveHandleDropOnFolder(id);
  });
}

// ---- Pristup ke slozce podle role (bot4, 2026-08-05) - jen admin ----
const DRIVE_ROLE_CHECK_ROLES = ["manager", "skladnik", "ucetni", "sklad"]; // monter do administrace nema pristup
function openDriveFolderRolesModal(folderId, folderName, currentRoles) {
  document.getElementById("driveFolderRolesTitle").textContent = `Přístup ke složce „${folderName}“`;
  document.getElementById("driveFolderRolesErr").textContent = "";
  document.getElementById("driveFolderRolesChecks").innerHTML = DRIVE_ROLE_CHECK_ROLES.map(role => `
    <label style="display:flex;align-items:center;gap:8px;margin-bottom:6px;">
      <input type="checkbox" class="dfr-role-cb" value="${role}" ${currentRoles.includes(role) ? "checked" : ""}>
      ${RP_ROLE_LABELS[role] || role}
    </label>
  `).join("");
  document.getElementById("driveFolderRolesModal").classList.add("open");
  document.getElementById("driveFolderRolesSave").onclick = async () => {
    const roles = [...document.querySelectorAll(".dfr-role-cb:checked")].map(cb => cb.value);
    const r = await fetch(`/api/admin/drive/folders/${folderId}/roles`, {
      method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ roles }),
    });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) { document.getElementById("driveFolderRolesErr").textContent = data.error || "Uložení se nezdařilo."; return; }
    document.getElementById("driveFolderRolesModal").classList.remove("open");
    loadDriveTree();
  };
  document.getElementById("driveFolderRolesCancel").onclick = () => {
    document.getElementById("driveFolderRolesModal").classList.remove("open");
  };
}

// Sdilena bulk-delete logika pro Sdileny disk (soubory i slozky, bot5
// 2026-09-26) - Promise.allSettled, NE Promise.all: jedno selhani (napr.
// 403 na zamcenou podslozku bez prav) nesmi umlcet zbytek davky ani
// znemoznit nasledny loadDriveTree() refresh (puvodni Promise.all u
// souboru tohle delalo - jedno rejectnute fetch zastavilo celou funkci
// PRED clear()/reload, zbytek uspesne smazanych zustal ve stavu "porad
// vybrano" a UI se vubec neobnovilo). fetch() samo o sobe NEREJECTUJE na
// HTTP chybu (jen na sitovou), takze se musi kontrolovat r.ok explicitne
// - "verify db write rowcount" duch: nevěřit, že request "prosel", overit
// vysledek. Po dokonceni vzdy vola loadDriveTree() (caller), cimz se
// zobrazi skutecny stav z DB, ne jen predpoklad.
async function driveBulkDeleteWithReport(ids, urlForId, labelPlural) {
  const results = await Promise.allSettled(ids.map(id => fetch(urlForId(id), { method: "DELETE" })));
  const failed = results.filter(r => r.status === "rejected" || !r.value.ok).length;
  if (failed > 0) {
    alert(`Smazáno ${ids.length - failed} z ${ids.length} ${labelPlural}, ${failed} se nepodařilo smazat (zkontrolujte přístupová práva).`);
  }
}

function renderDriveFolderContents() {
  const wrap = document.getElementById("driveFolderContents");
  const folder = driveSelectedFolderId === null ? null : driveFindFolder(driveData.folders, driveSelectedFolderId);
  if (folder && folder.locked) {
    const roleNames = (folder.allowed_roles || []).map(r => RP_ROLE_LABELS[r] || r).join(", ") || "—";
    wrap.innerHTML = `<h4 style="margin:0 0 10px;">🔒 ${escapeHtmlAdmin(folder.name)}</h4>
      <p style="color:var(--text-muted);">Nemáte přístup k této složce. Otevřít ji smí jen role: ${escapeHtmlAdmin(roleNames)}.</p>`;
    return;
  }
  const files = driveSelectedFolderId === null ? driveData.root_files : (folder ? folder.files : []);
  const subfolders = driveSelectedFolderId === null ? driveData.folders : (folder ? folder.children : []);

  // Robert 2026-09-09: řádek s CELOU cestou úplně nahoře. Text jde
  // označit jedním kliknutím (user-select:all), aby se dal rovnou
  // zkopírovat - přesně to potřeboval u .blend souborů pro rendering.
  const cestaChain = driveSelectedFolderId === null
    ? [] : (drivePathChain(driveData.folders, driveSelectedFolderId) || []);
  const cestaText = "Kořen disku" + cestaChain.map(f => " / " + f.name).join("");
  const cestaRadek = `
    <div style="margin:0 0 10px;padding:6px 9px;background:var(--panel-bg-alt, rgba(127,127,127,.12));
                border:1px solid var(--border-soft2);border-radius:6px;">
      <div style="font-size:10.5px;color:var(--text-muted);text-transform:uppercase;letter-spacing:.04em;">Cesta</div>
      <div style="font-family:ui-monospace,Consolas,monospace;font-size:12.5px;color:var(--text2);
                  user-select:all;word-break:break-all;">${escapeHtmlAdmin(cestaText)}</div>
    </div>`;

  // Panel prirazeni materialu + HDRi (Robert 2026-09-28: "primo v tom
  // disku/adminu chci priradovat jaky material na jaky objekt a s jakym
  // HDri") - jen ve slozce s HDRI soubory. Roleta HDRi je JEDINA volba HDRi
  // pro vsechny rendery (ulozPrirazeni ji ulozi i jako hlavni). Hodnoty na
  // serveru (app_settings). Prazdny radek = material z modelu.
  // KÓD panelu (HTML + logika) je od 2026-09-30 v render-panel.js, ne tady.
  const maMaterialPanel = files.some(f => driveJeHdri(f.filename));
  const materialPanel = maMaterialPanel ? renderPanelHtml(driveHdriFiles) : "";
  // Materialy katalogu pro render (render-materialy-katalogu.js) - vizualni prirazovaci tabulka pod panelem HDRi
  const materialyKatalogu = maMaterialPanel && typeof materialyKataloguHtml === "function" ? materialyKataloguHtml() : "";

  const header = cestaRadek + materialPanel + materialyKatalogu + (driveSelectedFolderId === null
    ? `<h4 style="margin:0 0 10px;">Kořen disku</h4>`
    : `<div style="display:flex;gap:8px;align-items:center;margin-bottom:10px;flex-wrap:wrap;">
         <input type="text" id="driveFolderRenameInput" value="${escapeHtmlAdmin(folder ? folder.name : "")}" style="flex:1 1 160px;">
         <button id="btnDriveFolderRename">Přejmenovat</button>
         <button id="btnDriveFolderDelete" class="danger" title="Smaže CELOU tuto otevřenou složku, ne jen její obsah">🗑️ Smazat TUTO složku</button>
       </div>`);

  const subfolderRows = subfolders.map(f => `
    <div class="crm-task-row" data-folder-id="${f.id}" style="cursor:pointer;">
      <input type="checkbox" class="dr-subfolder-cb" data-id="${f.id}" ${driveSelectedSubfolderIds.has(f.id) ? "checked" : ""} style="margin-right:6px;" onclick="event.stopPropagation();">
      <span class="crm-task-title">📁 ${escapeHtmlAdmin(f.name)}</span>
    </div>
  `).join("");

  const subfolderBulkBar = subfolders.length ? `
    <div style="display:flex;gap:8px;align-items:center;margin:10px 0 6px;padding-top:8px;border-top:1px dashed var(--border-soft2);font-size:12px;">
      <label><input type="checkbox" id="driveSubfoldersSelectAll"> Vybrat podsložky níže</label>
      <button id="driveSubfoldersBulkDelete" class="danger" style="display:none;font-size:12px;padding:3px 10px;">Smazat jen zaškrtnuté podsložky</button>
    </div>` : "";

  // Robert 2026-08-02 ("pridej obema bulk mazani s fajkama"): checkbox u
  // kazdeho souboru + Vybrat vse + Smazat vybrane (v aktualni slozce)
  //
  // Robert 2026-08-11 ("kdyz ve sdilenem disku kliknu stahnout, cele to
  // zhasne na sekundu"): odkazy "Stáhnout" NESMI mit target="_blank".
  // Backend (/download routes v api/drive.py a api/quotes.py) posila
  // vzdy Content-Disposition: attachment, takze kliknuti soubor rovnou
  // stahne BEZ opusteni stranky. S target="_blank" prohlizec nejdriv
  // otevrel nove prazdne okno, pak zjistil ze jde o stahovani a okno
  // zase zavrel - ten sekundovy "zhasnuty" zablesk byl prave to prazdne
  // okno. Plati pro vsechny download odkazy v adminu (disk, nabidky,
  // kniha jizd). "Zobrazit" u PDF target="_blank" MA - tam je nova
  // zalozka zamer (inline preview, /preview route).
  const fileRowsList = files.map(f => {
    const isPdf = f.content_type === "application/pdf" || /\.pdf$/i.test(f.filename || "");
    const isImg = driveIsImageFile(f);
    return `
    <div class="crm-note-row" data-file-id="${f.id}" title="Přetažením přesunete do jiné složky">
      <input type="checkbox" class="dr-file-cb" data-id="${f.id}" ${driveSelectedFileIds.has(f.id) ? "checked" : ""} style="margin-right:6px;">
      <span class="crm-note-body">${escapeHtmlAdmin(f.filename)} <span style="color:var(--text-muted);">(${driveFmtSize(f.size_bytes)}${f.created_at ? " · " + driveFmtDate(f.created_at) : ""})</span></span>
      ${isPdf ? `<a href="/api/admin/drive/files/${f.id}/preview" target="_blank" draggable="false">Zobrazit</a>` : ""}
      ${isImg ? `<a href="#" class="dr-file-view-img" data-id="${f.id}" draggable="false">Zobrazit</a>` : ""}
      <a href="/api/admin/drive/files/${f.id}/download" draggable="false">Stáhnout</a>
      <button class="dr-file-rename" data-id="${f.id}" data-name="${escapeHtmlAdmin(f.filename)}" title="Přejmenovat soubor" style="background:none;border:none;color:var(--text-muted);cursor:pointer;padding:0 4px;">✎</button>
      <button class="crm-del-btn dr-file-del" data-id="${f.id}" title="Smazat soubor">✕</button>
    </div>
  `;
  }).join("");

  // Robert 2026-08-10 ("chci moznost ve sdilenem disku... zobrazovat
  // ikony cca 250x250px") - stejny obsah/akce jako radkovy seznam, jen
  // jako ctvercove karty. Obrazkove soubory (content_type image/*)
  // ukazuji skutecny nahled pres /download (Content-Disposition:
  // attachment tam sice zustava vzdy nastaveno kvuli XSS pojistce, ale
  // prohlizec ho u <img> podresourcu ignoruje - vykresli inline stejne
  // jako u normalniho <img src>).
  const fileRowsIcons = `<div class="drive-icon-grid">` + files.map(f => {
    const isPdf = f.content_type === "application/pdf" || /\.pdf$/i.test(f.filename || "");
    const isImg = driveIsImageFile(f);
    const thumb = isImg
      ? `<img src="/api/admin/drive/files/${f.id}/download" loading="lazy" alt="" draggable="false">`
      : `<span class="dic-generic-icon">${driveGenericIcon(f)}</span>`;
    return `
    <div class="drive-icon-card" data-file-id="${f.id}" title="Přetažením přesunete do jiné složky">
      <div class="dic-thumb-wrap">
        <input type="checkbox" class="dr-file-cb dic-cb" data-id="${f.id}" ${driveSelectedFileIds.has(f.id) ? "checked" : ""}>
        <button class="dic-del dr-file-del" data-id="${f.id}" title="Smazat soubor">✕</button>
        ${thumb}
      </div>
      <div class="dic-body">
        <div class="dic-filename" title="${escapeHtmlAdmin(f.filename)}">${escapeHtmlAdmin(f.filename)}</div>
        <div style="font-size:10px;color:var(--text-muted);margin-bottom:4px;">${driveFmtSize(f.size_bytes)}${f.created_at ? " · " + driveFmtDate(f.created_at) : ""}</div>
        <div class="dic-actions">
          ${isPdf ? `<a href="/api/admin/drive/files/${f.id}/preview" target="_blank" draggable="false">Zobrazit</a>` : ""}
          <a href="/api/admin/drive/files/${f.id}/download" draggable="false">Stáhnout</a>
          <button class="dr-file-rename" data-id="${f.id}" data-name="${escapeHtmlAdmin(f.filename)}" title="Přejmenovat soubor" style="background:none;border:none;color:var(--text-muted);cursor:pointer;padding:0;font-size:11px;">Přejmenovat</button>
        </div>
      </div>
    </div>
  `;
  }).join("") + `</div>`;

  const fileRows = driveViewMode === "icons" ? fileRowsIcons : fileRowsList;

  const bulkBar = files.length ? `
    <div style="display:flex;gap:8px;align-items:center;margin:6px 0;font-size:12px;">
      <label><input type="checkbox" id="driveFilesSelectAll"> Vybrat vše</label>
      <button id="driveFilesBulkDelete" class="danger" style="display:none;font-size:12px;padding:3px 10px;">Smazat vybrané</button>
    </div>` : "";

  const viewToggle = files.length ? `
    <div class="drive-view-toggle">
      <button id="driveViewList" class="${driveViewMode === "list" ? "active" : ""}">📋 Seznam</button>
      <button id="driveViewIcons" class="${driveViewMode === "icons" ? "active" : ""}">🖼️ Ikony</button>
    </div>` : "";

  wrap.innerHTML = header
    + (subfolderRows ? `<div style="margin-bottom:10px;">${subfolderRows}</div>` : "")
    + subfolderBulkBar
    + viewToggle
    + bulkBar
    + (files.length ? fileRows : '<div style="color:#8b93a1;font-size:12px;">Žádné soubory.</div>')
    + `<div class="crm-add-row" style="margin-top:10px;">
         <input type="file" id="driveFileInput" multiple style="flex:1 1 auto;">
         <button id="btnDriveFileUpload">Nahrát</button>
         <span id="driveUploadStatus" style="font-size:12px;color:#8b93a1;"></span>
       </div>
       <progress id="driveUploadProgress" value="0" max="100" style="display:none;width:100%;margin-top:4px;"></progress>
       <div class="crm-add-row" style="margin-top:6px;">
         <input type="file" id="driveFolderInput" webkitdirectory multiple style="flex:1 1 auto;">
         <button id="btnDriveFolderUpload">Nahrát celou složku (se stromem)</button>
       </div>`;
  const btnViewList = document.getElementById("driveViewList");
  const btnViewIcons = document.getElementById("driveViewIcons");
  if (btnViewList) btnViewList.onclick = () => { driveViewMode = "list"; renderDriveFolderContents(); };
  if (btnViewIcons) btnViewIcons.onclick = () => { driveViewMode = "icons"; renderDriveFolderContents(); };

  const liveFileIds = new Set(files.map(f => f.id));
  [...driveSelectedFileIds].forEach(id => { if (!liveFileIds.has(id)) driveSelectedFileIds.delete(id); });
  function updateDriveBulkUi() {
    const btn = document.getElementById("driveFilesBulkDelete");
    if (!btn) return;
    btn.style.display = driveSelectedFileIds.size ? "" : "none";
    btn.textContent = `Smazat vybrané (${driveSelectedFileIds.size})`;
    const all = document.getElementById("driveFilesSelectAll");
    if (all) all.checked = files.length > 0 && files.every(f => driveSelectedFileIds.has(f.id));
  }
  wrap.querySelectorAll(".dr-file-cb").forEach(cb => {
    cb.onchange = () => {
      const id = parseInt(cb.dataset.id, 10);
      if (cb.checked) driveSelectedFileIds.add(id); else driveSelectedFileIds.delete(id);
      updateDriveBulkUi();
    };
  });
  const selAllEl = document.getElementById("driveFilesSelectAll");
  if (selAllEl) {
    selAllEl.onchange = () => {
      if (selAllEl.checked) files.forEach(f => driveSelectedFileIds.add(f.id));
      else driveSelectedFileIds.clear();
      renderDriveFolderContents();
    };
  }
  const bulkDelEl = document.getElementById("driveFilesBulkDelete");
  if (bulkDelEl) {
    bulkDelEl.onclick = async () => {
      if (!driveSelectedFileIds.size) return;
      if (!confirm(`Trvale smazat ${driveSelectedFileIds.size} vybraných souborů? Tohle nejde vrátit.`)) return;
      await driveBulkDeleteWithReport([...driveSelectedFileIds], id => `/api/admin/drive/files/${id}`, "souborů");
      driveSelectedFileIds.clear();
      loadDriveTree();
    };
  }
  updateDriveBulkUi();

  // Robert 2026-09-26 ("proč to nemá bulk zaškrtávátka? opravit" - u
  // podslozek, videl slozku plnou testovacich render davek pod
  // "Rendering") - PARALELNI mechanismus vedle toho souborovyho vyse,
  // NEslouceny do jednoho seznamu/tlacitka (jiny mazaci endpoint,
  // kaskadove mazani obsahu - viz confirm text nize, stejne zneni jako
  // u jednotlive slozky o par radku vyse "btnDriveFolderDelete").
  const liveSubfolderIds = new Set(subfolders.map(f => f.id));
  [...driveSelectedSubfolderIds].forEach(id => { if (!liveSubfolderIds.has(id)) driveSelectedSubfolderIds.delete(id); });
  function updateDriveSubfolderBulkUi() {
    const btn = document.getElementById("driveSubfoldersBulkDelete");
    if (!btn) return;
    btn.style.display = driveSelectedSubfolderIds.size ? "" : "none";
    btn.textContent = `Smazat jen zaškrtnuté podsložky (${driveSelectedSubfolderIds.size})`;
    const all = document.getElementById("driveSubfoldersSelectAll");
    if (all) all.checked = subfolders.length > 0 && subfolders.every(f => driveSelectedSubfolderIds.has(f.id));
  }
  wrap.querySelectorAll(".dr-subfolder-cb").forEach(cb => {
    cb.onchange = () => {
      const id = parseInt(cb.dataset.id, 10);
      if (cb.checked) driveSelectedSubfolderIds.add(id); else driveSelectedSubfolderIds.delete(id);
      updateDriveSubfolderBulkUi();
    };
  });
  const subfolderSelAllEl = document.getElementById("driveSubfoldersSelectAll");
  if (subfolderSelAllEl) {
    subfolderSelAllEl.onchange = () => {
      if (subfolderSelAllEl.checked) subfolders.forEach(f => driveSelectedSubfolderIds.add(f.id));
      else driveSelectedSubfolderIds.clear();
      renderDriveFolderContents();
    };
  }
  const subfolderBulkDelEl = document.getElementById("driveSubfoldersBulkDelete");
  if (subfolderBulkDelEl) {
    subfolderBulkDelEl.onclick = async () => {
      if (!driveSelectedSubfolderIds.size) return;
      const n = driveSelectedSubfolderIds.size;
      if (!confirm(`Smazat těchto ${n} zaškrtnutých podsložek VČETNĚ VŠECH JEJICH PODSLOŽEK A SOUBORŮ? Tuto akci nelze vzít zpět.`)) return;
      await driveBulkDeleteWithReport([...driveSelectedSubfolderIds], id => `/api/admin/drive/folders/${id}`, "složek");
      driveSelectedSubfolderIds.clear();
      loadDriveTree();
    };
  }
  updateDriveSubfolderBulkUi();

  wrap.querySelectorAll("[data-file-id]").forEach(row => {
    wireDriveFileDrag(row, parseInt(row.dataset.fileId, 10));
  });
  const driveImageFiles = files.filter(driveIsImageFile);
  wrap.querySelectorAll(".dic-thumb-wrap img").forEach(img => {
    img.onclick = (e) => {
      e.stopPropagation();
      const fid = parseInt(img.closest("[data-file-id]").dataset.fileId, 10);
      const idx = driveImageFiles.findIndex(f => f.id === fid);
      if (idx >= 0) driveOpenLightbox(driveImageFiles, idx);
    };
  });
  // Seznam pohled (list, ne ikony) nema zadnou miniaturu ke kliknuti -
  // odkaz "Zobrazit" u obrazku (viz fileRowsList vyse) je tam JEDINA cesta
  // k lightboxu (Robert se divil "tady je chci prohlizet" prave v tomhle
  // pohledu, ne v Ikonach).
  wrap.querySelectorAll(".dr-file-view-img").forEach(a => {
    a.onclick = (e) => {
      e.preventDefault();
      const fid = parseInt(a.dataset.id, 10);
      const idx = driveImageFiles.findIndex(f => f.id === fid);
      if (idx >= 0) driveOpenLightbox(driveImageFiles, idx);
    };
  });
  // Panel Rendering → HDRi: ovládací prvky, fronta testů, volba stroje (kód v render-panel.js).
  if (maMaterialPanel) renderPanelInit(wrap);
  if (maMaterialPanel && typeof materialyKataloguInit === "function") materialyKataloguInit(wrap);
  // Robert 2026-09-09: "chci mit moznost soubory ve sdilenem disku
  // prejmenovat". Backend to umel uz driv (PUT .../files/<id> bere
  // filename), chybelo jen ovladani. Pripona se hlida: kdyz ji uzivatel
  // v novem nazvu vynecha, doplni se z puvodniho - jinak by soubor
  // prestal byt rozpoznany jako .blend/.pdf a rozbily by se navazne
  // funkce (napr. render bere jen .blend).
  wrap.querySelectorAll(".dr-file-rename").forEach(btn => {
    btn.onclick = async (e) => {
      e.stopPropagation();
      const stary = btn.dataset.name || "";
      let novy = prompt("Nový název souboru:", stary);
      if (novy === null) return;
      novy = novy.trim();
      if (!novy || novy === stary) return;
      const tecka = stary.lastIndexOf(".");
      if (tecka > 0 && !novy.includes(".")) novy += stary.slice(tecka);
      const r = await fetch(`/api/admin/drive/files/${btn.dataset.id}`, {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ filename: novy }),
      });
      const data = await r.json().catch(() => ({}));
      if (!r.ok) { alert(data.error || "Přejmenování se nezdařilo."); return; }
      loadDriveTree();
    };
  });
  wrap.querySelectorAll(".dr-file-del").forEach(btn => {
    btn.onclick = async () => {
      if (!confirm("Smazat soubor?")) return;
      await fetch(`/api/admin/drive/files/${btn.dataset.id}`, { method: "DELETE" });
      loadDriveTree();
    };
  });
  wrap.querySelectorAll("[data-folder-id]").forEach(row => {
    const targetId = parseInt(row.dataset.folderId, 10);
    row.onclick = () => {
      driveSelectedFolderId = targetId;
      renderDriveFolderTree();
      renderDriveFolderContents();
    };
    // Podslozkova karta v obsahu aktualni slozky je taky cil pro
    // presunuti souboru tazenim (vedle stromu vlevo - viz
    // driveHandleDropOnFolder), at nemusi uzivatel skakat pohledem tam
    // a zpet mezi obsahem a stromem.
    row.addEventListener("dragover", (e) => {
      if (driveDraggedFileId == null) return;
      e.preventDefault();
      e.dataTransfer.dropEffect = "move";
      row.classList.add("drive-drop-target");
    });
    row.addEventListener("dragleave", () => row.classList.remove("drive-drop-target"));
    row.addEventListener("drop", async (e) => {
      e.preventDefault();
      row.classList.remove("drive-drop-target");
      await driveHandleDropOnFolder(targetId);
    });
  });
  if (driveSelectedFolderId !== null) {
    document.getElementById("btnDriveFolderRename").onclick = async () => {
      const name = document.getElementById("driveFolderRenameInput").value.trim();
      if (!name) return;
      await fetch(`/api/admin/drive/folders/${driveSelectedFolderId}`, {
        method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name }),
      });
      loadDriveTree();
    };
    document.getElementById("btnDriveFolderDelete").onclick = async () => {
      // Robert 2026-09-26 (incident "zmizela Rendering"): jmeno cile
      // rovnou v potvrzeni, at je jasne, ze mazes CELOU tuhle otevrenou
      // slozku, ne jen zaskrtnute podslozky pod ni (to dela tlacitko
      // "Smazat jen zaskrtnute podslozky" v panelu nize).
      const cilNazev = folder ? folder.name : "(kořen)";
      if (!confirm(`Smazat CELOU složku „${cilNazev}“ včetně VŠECH jejích podsložek a souborů? Tuto akci nelze vzít zpět.`)) return;
      await fetch(`/api/admin/drive/folders/${driveSelectedFolderId}`, { method: "DELETE" });
      driveSelectedFolderId = null;
      loadDriveTree();
    };
  }
  // Robert 2026-08-10 ("nejde mi ty soubory uploadovat" / "jsou tam ale
  // šlo to divně pomalu sekaně" / "blbne to, nahrava se to tam opakovane
  // duplikuje se to"): puvodni handler behem cekani na fetch() nijak
  // nezmenil vzhled tlacitka a nemel zadny try/catch - pri vetsich
  // souborech (PBR textury v radu MB) tak nekolik vterin/desitek vterin
  // vypadalo, jako by se NIC nedelo. Uzivatel klikl vicekrat = kazdy klik
  // spustil dalsi NEZAVISLY upload (na serveru fungujici spravne - overeno
  // primym testem API), takze vysledkem byly duplicitni soubory, ne
  // "zaseknuti". Ted: tlacitko se behem nahravani deaktivuje + ukaze
  // "Nahrávám… X/Y" (nejde re-kliknout znovu) a chyba site/serveru se
  // zobrazi rovnou u tlacitka, ne tise nikam.
  document.getElementById("btnDriveFileUpload").onclick = async () => {
    const fileInput = document.getElementById("driveFileInput");
    if (!fileInput.files.length) return;
    const fileCount = fileInput.files.length;
    const totalBytes = Array.from(fileInput.files).reduce((s, f) => s + f.size, 0);
    // Robert 2026-09-09 (70MB soubor, nginx ho odmitl a zabil spojeni
    // uprostred nahravani -> prohlizec hlasil jen obecnou "chybu
    // spojeni" a progress se vracel na nulu): rict to DOPREDU a
    // konkretne, at uzivatel nekouka na rostouci procenta, ktera stejne
    // nemuzou dojit do konce. Limit drzi nginx (client_max_body_size).
    if (totalBytes > DRIVE_MAX_UPLOAD_BYTES) {
      alert(`Moc velké: ${driveFmtSize(totalBytes)} v jednom nahrání, server přijme nejvýš ${driveFmtSize(DRIVE_MAX_UPLOAD_BYTES)}. Nahraj soubory po menších dávkách.`);
      return;
    }
    const fd = new FormData();
    Array.from(fileInput.files).forEach(f => fd.append("files", f));
    if (driveSelectedFolderId !== null) fd.append("folder_id", driveSelectedFolderId);
    driveUploadState = { pct: 0, label: `Nahrávám ${fileCount} soubor(ů)… 0 %` };
    driveApplyUploadUiState();
    try {
      // Robert ("chci videt prubeh"): fetch() nema pouzitelny upload
      // progress napric prohlizeci, proto XHR - jedina cesta k reálnym
      // procentum nahranych bajtu (ne jen "probíhá/neprobíhá").
      const res = await driveUploadXhr("/api/admin/drive/files", fd, (loaded, total) => {
        const pct = Math.round((loaded / total) * 100);
        // pres driveUploadState + driveApplyUploadUiState (ne pres drzene
        // reference na elementy) - po prepnuti zalozky tam a zpet jsou
        // elementy uz JINE instance, viz komentar u driveUploadState.
        driveUploadState = { pct, label: `Nahrávám ${fileCount} soubor(ů)… ${pct} %` };
        driveApplyUploadUiState();
      });
      if (!res.ok) {
        const msg = res.status === 413
          ? `Server soubor odmítl jako příliš velký (${driveFmtSize(totalBytes)}). Zkus menší dávku.`
          : ((res.json && res.json.error) || `Nahrání se nezdařilo (HTTP ${res.status}).`);
        alert(msg);
        return;
      }
      loadDriveTree();
    } catch (err) {
      // vypadek site/serveru - drive predtim tise "zamrzlo", ted aspon videt chybu
      alert(`Nahrání se nezdařilo (${err.message}). U velkých souborů to obvykle znamená, že server spojení ukončil — zkus menší dávku.`);
    } finally {
      driveUploadState = null;
      driveApplyUploadUiState();
    }
  };

  // Robert 2026-08-21 ("udelej sdileny disk... aby mohl uploadovat cely
  // strom se soubory uvnitr"): webkitdirectory naplni input.files VSEMI
  // soubory v cele vybrane slozce (vc. podslozek), kazdy nese
  // webkitRelativePath (napr. "Karoserie/Ford/Connect_FO13...glb").
  // Posila se v DAVKACH (ne vsech 300 najednou v 1 requestu - riziko
  // limitu velikosti/timeoutu na serveru i tichy "vypada zamrzle" pocit
  // jako u puvodniho jednosouboroveho uploadu, viz komentar vyse) s
  // viditelnym postupem X/Y, tlacitko zamknute behem behu.
  const btnFolderUpload = document.getElementById("btnDriveFolderUpload");
  if (btnFolderUpload) {
    btnFolderUpload.onclick = async () => {
      const folderInput = document.getElementById("driveFolderInput");
      const allFiles = Array.from(folderInput.files || []);
      if (!allFiles.length) return;
      const BATCH_SIZE = 15;
      driveUploadState = { pct: 0, label: `Nahrávám strom… 0/${allFiles.length}` };
      driveApplyUploadUiState();
      let processed = 0, newCount = 0, skipCount = 0;
      let hadError = false;
      try {
        for (let i = 0; i < allFiles.length; i += BATCH_SIZE) {
          const batch = allFiles.slice(i, i + BATCH_SIZE);
          // Robert ("normálně to funguje jinak, prostě se hlídá nějak aby
          // to nespadlo"): tezistem neni rucni obnova PO padu, ale
          // AUTOMATICKE preziti prechodnych vypadku (site, timeout) -
          // kazda davka se zkusi az 4x s narustajici prodlevou, nez se
          // to vubec ohlasi jako chyba uzivateli. Skip-duplicit (server)
          // zustava jako pojistka navic, ne hlavni mechanismus.
          let batchOk = false, lastErrMsg = "", respJson = {};
          for (let attempt = 1; attempt <= 4 && !batchOk; attempt++) {
            if (attempt > 1) {
              driveUploadState = { pct: Math.round((processed / allFiles.length) * 100), label: `Dávka selhala, zkouším znovu (${attempt}/4)… ${processed}/${allFiles.length}` };
              driveApplyUploadUiState();
              await new Promise(res => setTimeout(res, 1000 * attempt));
            }
            const fd = new FormData();
            batch.forEach(f => fd.append("files", f));
            fd.append("paths", JSON.stringify(batch.map(f => f.webkitRelativePath || f.name)));
            if (driveSelectedFolderId !== null) fd.append("folder_id", driveSelectedFolderId);
            driveUploadState = { pct: Math.round((processed / allFiles.length) * 100), label: `Nahrávám strom… ${processed}/${allFiles.length} (nově ${newCount}, přeskočeno ${skipCount})` };
            driveApplyUploadUiState();
            try {
              const r = await fetch("/api/admin/drive/files", { method: "POST", body: fd });
              if (r.ok) {
                respJson = await r.json().catch(() => ({}));
                batchOk = true;
              } else {
                try { const j = await r.json(); lastErrMsg = j && j.error ? j.error : `HTTP ${r.status}`; } catch (e) { lastErrMsg = `HTTP ${r.status}`; }
              }
            } catch (netErr) {
              lastErrMsg = netErr.message;
            }
          }
          if (!batchOk) {
            hadError = true;
            alert(`Dávka se nezdařila i po 4 pokusech (${lastErrMsg}). Zastaveno na souboru ${processed + 1}/${allFiles.length} — co už se nahrálo zůstává. Zkus znovu kliknout na "Nahrát celou složku" se stejnou složkou, hotové se přeskočí.`);
            break;
          }
          const batchSkipped = (respJson.skipped || []).length;
          skipCount += batchSkipped;
          newCount += batch.length - batchSkipped;
          processed += batch.length;
          driveUploadState = { pct: Math.round((processed / allFiles.length) * 100), label: `Nahrávám strom… ${processed}/${allFiles.length} (nově ${newCount}, přeskočeno ${skipCount})` };
          driveApplyUploadUiState();
        }
        const doneMsg = hadError ? "" : `Hotovo: ${processed}/${allFiles.length} zpracováno (nově nahráno ${newCount}, přeskočeno ${skipCount} už existujících).`;
        loadDriveTree();
        if (doneMsg) { const s = document.getElementById("driveUploadStatus"); if (s) s.textContent = doneMsg; }
      } catch (err) {
        alert(`Nahrání se přerušilo (chyba spojení): ${err.message} — zpracováno ${processed}/${allFiles.length} (nově ${newCount}, přeskočeno ${skipCount}). Klidně spusť znovu se stejnou složkou, hotové se přeskočí.`);
      } finally {
        driveUploadState = null;
        driveApplyUploadUiState();
      }
    };
  }

  // Az uplne nakonec: kdyz se panel prekreslil BEHEM beziciho uploadu
  // (typicky prepnuti zalozky tam a zpet - "drive" tab-btn vola
  // loadDriveTree()), jsou vsechny elementy vyse cerstve nove a nevi o
  // nem. Tohle jim vrati spravny stav - zamknuta tlacitka (zadny
  // duplicitni upload) + viditelny aktualni postup. Samotny prenos bezi
  // dal bez preruseni, na DOM nezavisi.
  driveApplyUploadUiState();
}

// Robert ("chci videt prubeh" pri nahravani na sdileny disk): fetch()
// nema napric prohlizeci pouzitelny upload progress event (jen Response
// se resolvne az PO celem odeslani), proto XMLHttpRequest - jedina
// spolehliva cesta k xhr.upload.onprogress s realnymi nahranymi/celkovymi
// bajty. Vraci tvar podobny fetch() Response (ok/status/json), aby
// volajici kod nemusel resit dva ruzne API.
function driveUploadXhr(url, formData, onProgress) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", url);
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable && onProgress) onProgress(e.loaded, e.total);
    };
    xhr.onload = () => {
      let json = {};
      try { json = JSON.parse(xhr.responseText); } catch (e) { /* telo neni JSON */ }
      resolve({ ok: xhr.status >= 200 && xhr.status < 300, status: xhr.status, json });
    };
    xhr.onerror = () => reject(new Error("chyba spojení"));
    xhr.send(formData);
  });
}
function driveFmtSize(bytes) {
  if (bytes == null) return "";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} kB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

// Robert 2026-09-11 ("v tomto prehledu chci videt casove razitko") -
// `f.created_at` z api/drive.py uz je `.isoformat()` (bez "Z"/offsetu -
// naivni MISTNI cas, stejny vzor jako u ostatnich mist opravenych po
// bot4ove nalezu "GMT nalepka na mistnim case, o 2 hodiny mimo"). `new
// Date()` retezec BEZ offsetu ze specifikace parsuje jako MISTNI cas
// prohlizece - u nas i produkce je to CET/CEST, takze zadny prevod
// netreba a cislo sedi presne.
//
// Dnesni datum ukazuje jen cas (Robert: "zvaz, jestli u dnesniho data
// nestaci jen cas") - kratsi, a datum by stejne rikalo jen "dnes".
function driveFmtDate(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "";
  const cas = d.toLocaleTimeString("cs-CZ", { hour: "2-digit", minute: "2-digit" });
  if (d.toDateString() === new Date().toDateString()) return cas;
  return `${d.getDate()}. ${d.getMonth() + 1}. ${cas}`;
}

// ---- Online nabidky (bot5, 2026-08-04) - seznam + statistiky shlednuti ----
function fmtDurationMs(ms) {
  ms = Number(ms) || 0;
  const totalSec = Math.round(ms / 1000);
  const min = Math.floor(totalSec / 60), sec = totalSec % 60;
  return min > 0 ? `${min} min ${sec} s` : `${sec} s`;
}
function fmtDateCz(iso) {
  if (!iso) return "";
  return new Date(iso).toLocaleString("cs-CZ", { day: "numeric", month: "numeric", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

let onlineOffersFilter = { q: "", page: 1, page_size: 50, archived: false };

// Bulk mazani online nabidek (Robert 2026-08-05) - vyber checkboxy na
// aktualni strance, smazani vc. vsech souboru na disku resi backend.
const onlineOffersSelected = new Set();
function updateOnlineOffersBulkUi() {
  const btn = document.getElementById("onlineOffersBulkDelete");
  const countEl = document.getElementById("onlineOffersBulkCount");
  if (!btn) return;
  btn.style.display = onlineOffersSelected.size ? "" : "none";
  if (countEl) countEl.textContent = onlineOffersSelected.size;
}
document.getElementById("onlineOffersCheckAll").onchange = (e) => {
  document.querySelectorAll("#onlineOffersTbody .oo-select").forEach(cb => {
    cb.checked = e.target.checked;
    const id = parseInt(cb.dataset.id, 10);
    if (cb.checked) onlineOffersSelected.add(id); else onlineOffersSelected.delete(id);
  });
  updateOnlineOffersBulkUi();
};
document.getElementById("onlineOffersBulkDelete").onclick = async () => {
  const n = onlineOffersSelected.size;
  if (!n) return;
  if (!confirm(`Opravdu smazat ${n} vybraných nabídek?\n\nSmaže se i jejich PDF ze Sdíleného disku, obrázky, 3D model a všechny statistiky shlédnutí. Odkazy poslané klientům přestanou fungovat. Akce je nevratná.`)) return;
  const btn = document.getElementById("onlineOffersBulkDelete");
  btn.disabled = true;
  try {
    const r = await fetch("/api/admin/scene-offers/bulk-delete", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ids: [...onlineOffersSelected] }),
    });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) { alert(data.error || "Mazání se nepodařilo."); return; }
    loadOnlineOffersList();
  } catch (e) {
    alert("Chyba spojení.");
  } finally {
    btn.disabled = false;
  }
};

async function loadOnlineOffersList() {
  const tbody = document.getElementById("onlineOffersTbody");
  const errEl = document.getElementById("onlineOffersErr");
  errEl.textContent = "";
  const params = new URLSearchParams({ page: onlineOffersFilter.page, page_size: onlineOffersFilter.page_size });
  if (onlineOffersFilter.q) params.set("q", onlineOffersFilter.q);
  if (onlineOffersFilter.archived) params.set("archived", "1");
  const resp = await fetch(`/api/admin/scene-offers?${params.toString()}`);
  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) {
    errEl.textContent = data.error || "Nabídky se nepodařilo načíst.";
    return;
  }
  renderPager("onlineOffersPager", data, onlineOffersFilter, loadOnlineOffersList);
  const counts = data.counts || {};
  document.getElementById("onlineOffersActiveCount").textContent = counts.active ?? 0;
  document.getElementById("onlineOffersArchivedCount").textContent = counts.archived ?? 0;
  const offers = data.offers || [];
  onlineOffersSelected.clear();
  updateOnlineOffersBulkUi();
  const checkAllEl = document.getElementById("onlineOffersCheckAll");
  if (checkAllEl) checkAllEl.checked = false;
  // V archivu (Robert 2026-08-06: "platnost 30 dní, poté vždy končí v
  // archivu, z archivu je vyvolá pouze admin ručně") je stav vzdy "V
  // archivu" bez ohledu na is_active - odkaz stejne nefunguje, dokud
  // admin nevyvola "Obnovit z archivu" (= regenerate-link, posune
  // platnost o dalsich 30 dni a nabidka se objevi zpet v Aktivnich).
  tbody.innerHTML = offers.length ? offers.map(o => `
    <tr data-id="${o.id}">
      <td><input type="checkbox" class="oo-select" data-id="${o.id}"></td>
      <td>${escapeHtmlAdmin(o.offer_number)}</td>
      <td>${escapeHtmlAdmin(o.customer_name || "—")}</td>
      <td>${Math.round(o.total_price).toLocaleString("cs-CZ")} Kč</td>
      <td>${o.view_count}</td>
      <td>${fmtDurationMs(o.total_dwell_ms)}</td>
      <td>${fmtDateCz(o.created_at)}</td>
      <td>${fmtDateCz(o.expires_at)}</td>
      <td>${o.is_archived
        ? '<span style="color:#c9a227;">📦 v archivu</span>'
        : (o.is_active ? '<span style="color:#4caf7d;">aktivní</span>' : '<span style="color:var(--text-muted);">deaktivováno</span>')}</td>
      <td>${o.accepted_name ? `<span style="color:#4caf7d;">✓ ${escapeHtmlAdmin(o.accepted_name)}</span>` : '<span style="color:var(--text-muted);">-</span>'}</td>
      <td style="white-space:nowrap;">
        <button class="oo-view-btn" data-id="${o.id}" title="Otevře online nabídku v nové záložce (klientský odkaz zůstává beze změny)">👁 Zobrazit</button>
        <button class="oo-edit-btn" data-id="${o.id}" title="Upravit nabídku přímo, bez nutnosti projít přes Statistiky">✏️ Upravit</button>
        <button class="oo-stats-btn" data-id="${o.id}">📊 Statistiky</button>
        <button class="oo-renders-btn" data-id="${o.id}" data-number="${escapeHtmlAdmin(o.offer_number)}" title="Schválené rendery na stránce Vizualizace online nabídky - smazání, popisky, pořadí">🖼 Rendery</button>
        <button class="oo-link-btn" data-id="${o.id}">${o.is_archived ? "↩ Obnovit z archivu" : "🔗 Nový odkaz"}</button>
        ${o.is_archived ? "" : `<button class="oo-toggle-btn" data-id="${o.id}" data-active="${o.is_active ? 1 : 0}">${o.is_active ? "Deaktivovat" : "Aktivovat"}</button>`}
      </td>
    </tr>
  `).join("") : `<tr><td colspan="11" style="color:var(--text-muted);">${onlineOffersFilter.archived ? "Žádné nabídky v archivu." : "Zatím žádné online nabídky."}</td></tr>`;

  tbody.querySelectorAll(".oo-select").forEach(cb => {
    cb.onchange = () => {
      const id = parseInt(cb.dataset.id, 10);
      if (cb.checked) onlineOffersSelected.add(id); else onlineOffersSelected.delete(id);
      updateOnlineOffersBulkUi();
    };
  });

  tbody.querySelectorAll(".oo-stats-btn").forEach(b => {
    b.onclick = () => openOnlineOfferStats(parseInt(b.dataset.id, 10));
  });
  // Robert primo, 2026-09-14 (pres bot3): "Upravit" v radku otevre
  // editacni modal PRIMO, bez nutnosti projit pres Statistiky -
  // openOfferEditModal cte offer ID z currentOnlineOfferId (stejny
  // globalni stav, ktery jinak nastavuje openOnlineOfferStats).
  tbody.querySelectorAll(".oo-edit-btn").forEach(b => {
    b.onclick = () => {
      currentOnlineOfferId = parseInt(b.dataset.id, 10);
      openOfferEditModal();
    };
  });
  tbody.querySelectorAll(".oo-renders-btn").forEach(b => {
    b.onclick = () => openOfferRenders(parseInt(b.dataset.id, 10), b.dataset.number);
  });
  // "Zobrazit online" (Robert 2026-08-05) - klientsky token je v DB jen
  // jako hash, endpoint proto vygeneruje ODDELENY admin token (klientsky
  // odkaz/platnost se nemeni) a vrati URL k otevreni. Okno se otevira
  // PRED fetchem (prazdne) - window.open az v async callbacku by vetsina
  // prohlizecu zablokovala jako popup bez uzivatelskeho gesta.
  tbody.querySelectorAll(".oo-view-btn").forEach(b => {
    b.onclick = async () => {
      const win = window.open("about:blank", "_blank");
      try {
        const r = await fetch(`/api/admin/scene-offers/${b.dataset.id}/view-online`, { method: "POST" });
        const data = await r.json().catch(() => ({}));
        if (!r.ok || !data.online_url) {
          if (win) win.close();
          alert(data.error || "Nabídku se nepodařilo otevřít.");
          return;
        }
        if (win) win.location = data.online_url;
      } catch (e) {
        if (win) win.close();
        alert("Chyba spojení.");
      }
    };
  });
  tbody.querySelectorAll(".oo-toggle-btn").forEach(b => {
    b.onclick = async () => {
      await fetch(`/api/admin/scene-offers/${b.dataset.id}/toggle-active`, { method: "POST" });
      loadOnlineOffersList();
    };
  });
  // Token se uklada jen jako hash (viz backend) - puvodni odkaz uz
  // nejde zpetne zobrazit, proto misto "zobrazit odkaz" rovnou
  // vygenerujeme NOVY (stary prestane platit) a zkopirujeme ho.
  tbody.querySelectorAll(".oo-link-btn").forEach(b => {
    b.onclick = async () => {
      // Bez tehle pojistky dvojklik/rychle dva klepnuti na dotyku
      // vygeneruje NOVY token dvakrat za sebou - prvni odkaz, co admin
      // stihne zkopirovat/odeslat, tim okamzite prestane platit (viz
      // AGENTS_LOG 2026-09-15, nabidka Logiman0109).
      if (b.disabled) return;
      b.disabled = true;
      try {
        const resp = await fetch(`/api/admin/scene-offers/${b.dataset.id}/regenerate-link`, { method: "POST" });
        const data = await resp.json().catch(() => ({}));
        if (!resp.ok) { alert(data.error || "Odkaz se nepodařilo vygenerovat."); return; }
        const onlineUrl = new URL(data.online_url, window.location.origin).href;
        const orig = b.textContent;
        try {
          await navigator.clipboard.writeText(onlineUrl);
          b.textContent = "✓ Zkopírováno";
        } catch (e) {
          window.prompt("Odkaz pro klienta (starý přestal platit):", onlineUrl);
        }
        setTimeout(() => { b.textContent = orig; loadOnlineOffersList(); }, 2000);
      } finally {
        b.disabled = false;
      }
    };
  });
}
document.getElementById("onlineOffersSearchApply").onclick = () => {
  onlineOffersFilter.q = document.getElementById("onlineOffersSearchQ").value.trim();
  onlineOffersFilter.page = 1;
  loadOnlineOffersList();
};
document.getElementById("onlineOffersSearchReset").onclick = () => {
  document.getElementById("onlineOffersSearchQ").value = "";
  onlineOffersFilter = { q: "", page: 1, page_size: onlineOffersFilter.page_size, archived: onlineOffersFilter.archived };
  loadOnlineOffersList();
};
document.getElementById("onlineOffersSearchQ").addEventListener("keydown", (e) => {
  if (e.key === "Enter") { e.preventDefault(); document.getElementById("onlineOffersSearchApply").click(); }
});
document.querySelectorAll('input[name="onlineOffersView"]').forEach(r => {
  r.onchange = () => {
    onlineOffersFilter.archived = document.querySelector('input[name="onlineOffersView"]:checked').value === "archived";
    onlineOffersFilter.page = 1;
    loadOnlineOffersList();
  };
});

// Stala testovaci nabidka (Robert 2026-08-05: "dej mi do adminu
// testovaci nabidku stalou tlacitko") - cislo TEST, nikdy nevyprsi,
// prvni klik ji zalozi (placeholder vykresy + katalogovy GLB model),
// kazdy dalsi klik vygeneruje cerstvy klientsky odkaz a otevre ho v
// nove zalozce. Admin pohled (modrozelene znacky) pres bezne
// "Zobrazit online" v radku TEST v seznamu nize.
document.getElementById("btnTestOffer").onclick = async () => {
  const btn = document.getElementById("btnTestOffer");
  btn.disabled = true;
  try {
    const r = await fetch("/api/admin/scene-offers/test-offer", { method: "POST" });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) { alert(data.error || "Testovací nabídku se nepodařilo otevřít."); return; }
    window.open(data.online_url, "_blank");
    loadOnlineOffersList();
  } catch (e) {
    alert("Chyba spojení.");
  } finally {
    btn.disabled = false;
  }
};

let currentOnlineOfferId = null;

// Sprava renderu nabidky (Robert 2026-08-11: "ad 1") - nacte seznam,
// vykresli karty s miniaturou, popiskem (ulozeni na Enter/opusteni pole),
// sipkami poradi a mazanim. Po kazde akci se seznam znovu nacte, aby
// poradi vzdy odpovidalo serveru.
async function openOfferRenders(offerId, offerNumber) {
  document.getElementById("offerRendersTitle").textContent = `Rendery nabídky ${offerNumber}`;
  document.getElementById("offerRendersModal").classList.add("open");
  await reloadOfferRenders(offerId);
}

async function reloadOfferRenders(offerId) {
  const grid = document.getElementById("offerRendersGrid");
  grid.innerHTML = '<div style="color:var(--text-muted);font-size:13px;">Načítám…</div>';
  const r = await fetch(`/api/admin/scene-offers/${offerId}/renders`);
  const d = await r.json().catch(() => ({}));
  if (!r.ok) { grid.innerHTML = `<div style="color:#e05a5a;">${escapeHtmlAdmin(d.error || "Nepodařilo se načíst.")}</div>`; return; }
  const renders = d.renders || [];
  if (!renders.length) {
    grid.innerHTML = '<div style="color:var(--text-muted);font-size:13px;">Tato nabídka zatím žádné rendery nemá. Přidáš je ve scéně: render → „✚ Přidat do nabídky" v okně výsledku.</div>';
    return;
  }
  grid.innerHTML = renders.map((rn, i) => `
    <div class="offer-render-card" data-rid="${rn.id}">
      <img src="${rn.url}" alt="Render ${i + 1}" title="Otevřít v plné velikosti" onclick="window.open('${rn.url}', '_blank')">
      <input type="text" class="or-caption" placeholder="popisek pod obrázkem (nepovinné)" value="${escapeHtmlAdmin(rn.caption || "")}">
      <div class="offer-render-actions">
        <button class="or-up" title="Posunout dopředu" ${i === 0 ? "disabled" : ""}>↑</button>
        <button class="or-down" title="Posunout dozadu" ${i === renders.length - 1 ? "disabled" : ""}>↓</button>
        <span style="flex:1;"></span>
        <button class="or-del" title="Smazat render z nabídky (soubor se odstraní, ve scéně ho můžeš vyrenderovat znovu)">🗑 Smazat</button>
      </div>
    </div>`).join("");

  grid.querySelectorAll(".offer-render-card").forEach(card => {
    const rid = card.dataset.rid;
    const captionEl = card.querySelector(".or-caption");
    let savedCaption = captionEl.value;
    const saveCaption = async () => {
      if (captionEl.value === savedCaption) return;
      const resp = await fetch(`/api/admin/scene-offers/${offerId}/renders/${rid}`, {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ caption: captionEl.value }),
      });
      if (resp.ok) { savedCaption = captionEl.value; captionEl.style.borderColor = "#4caf7d"; setTimeout(() => captionEl.style.borderColor = "", 900); }
      else alert("Popisek se nepodařilo uložit.");
    };
    captionEl.addEventListener("blur", saveCaption);
    captionEl.addEventListener("keydown", (ev) => { if (ev.key === "Enter") { ev.preventDefault(); captionEl.blur(); } });
    card.querySelector(".or-up").onclick = async () => {
      await fetch(`/api/admin/scene-offers/${offerId}/renders/${rid}`, {
        method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ move: "up" }) });
      reloadOfferRenders(offerId);
    };
    card.querySelector(".or-down").onclick = async () => {
      await fetch(`/api/admin/scene-offers/${offerId}/renders/${rid}`, {
        method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ move: "down" }) });
      reloadOfferRenders(offerId);
    };
    card.querySelector(".or-del").onclick = async () => {
      if (!confirm("Opravdu smazat tento render z nabídky?")) return;
      const resp = await fetch(`/api/admin/scene-offers/${offerId}/renders/${rid}`, { method: "DELETE" });
      if (!resp.ok) { const dd = await resp.json().catch(() => ({})); alert(dd.error || "Smazání se nepodařilo."); return; }
      reloadOfferRenders(offerId);
    };
  });
}

async function openOnlineOfferStats(offerId) {
  currentOnlineOfferId = offerId;
  const resp = await fetch(`/api/admin/scene-offers/${offerId}/stats`);
  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) { alert(data.error || "Statistiky se nepodařilo načíst."); return; }

  document.getElementById("onlineOfferStatsTitle").textContent = `Statistiky nabídky ${data.offer_number}`;

  const acceptEl = document.getElementById("onlineOfferStatsAcceptance");
  acceptEl.innerHTML = data.acceptance
    ? `<span style="color:#4caf7d;">✓ Objednáno - ${escapeHtmlAdmin(data.acceptance.name)}, ${fmtDateCz(data.acceptance.accepted_at)}</span>`
    : `<span style="color:var(--text-muted);">Zatím neobjednáno.</span>`;

  // Odmitnuti/pripominka (Robert 2026-08-10) - vic radku = klient klikl
  // vickrat, nejnovejsi napred (stejne poradi jako backend vraci).
  const declinesEl = document.getElementById("onlineOfferStatsDeclines");
  declinesEl.innerHTML = (data.declines || []).length
    ? `<div style="color:#e0a03a;">⚠ Nemá zájem / připomínka:</div>` + data.declines.map(d =>
        `<div style="margin-left:12px;">${d.reason ? escapeHtmlAdmin(d.reason) : "<i>bez uvedení důvodu</i>"} <span style="color:var(--text-muted);font-size:11.5px;">(${fmtDateCz(d.declined_at)})</span></div>`
      ).join("")
    : "";

  // Volby klienta (doprava/platba/zaloha/stav dodani) - Robert:
  // "ulozit a zobrazit v adminu". Vic radku = nabidku otevrelo vic
  // ruznych navstevniku (guest_id), nejnovejsi napred.
  const prefLabels = {
    shipping_method: { vlastni: "Vlastní odvoz", toptrans: "Toptrans" },
    payment_method: { dobirka: "Dobírka", zaloha: "Zálohová platba" },
    delivery_state: { smontovano: "Smontováno", demontovano: "Demontováno" },
  };
  const prefsEl = document.getElementById("onlineOfferStatsOrderPrefs");
  prefsEl.innerHTML = (data.order_prefs || []).length ? data.order_prefs.map(p => {
    const parts = [];
    if (p.shipping_method) parts.push(`🚚 ${prefLabels.shipping_method[p.shipping_method] || p.shipping_method}`);
    if (p.payment_method) parts.push(`💳 ${prefLabels.payment_method[p.payment_method] || p.payment_method}${p.payment_method === "zaloha" && p.deposit_pct ? ` ${p.deposit_pct} %` : ""}`);
    if (p.delivery_state) parts.push(`📦 ${prefLabels.delivery_state[p.delivery_state] || p.delivery_state}`);
    // Robert 2026-10-07 ("zase tam chybi montaz KDE Praha/Slavicin"): pocet kusu a zvolena montaz s mistem (Praha / Slavicin) - pole posila API od 2026-10-07 (starsi API je nema = nic se nepridava)
    if (p.qty > 1) parts.push(`🔢 ${escapeHtmlAdmin(String(p.qty))} ks`);
    if (p.montaz_zvolena) parts.push(`🔧 Montáž${p.montaz_misto_label || p.montaz_misto ? " – " + escapeHtmlAdmin(String(p.montaz_misto_label || p.montaz_misto)) : ""}`);
    return `<div>${parts.join(" · ") || "<i>bez voleb</i>"} <span style="color:var(--text-muted);font-size:11.5px;">(${fmtDateCz(p.updated_at)})</span></div>`;
  }).join("") : `<span style="color:var(--text-muted);">Klient zatím nic nevybral.</span>`;

  const notesBody = document.getElementById("onlineOfferStatsNotes");
  notesBody.innerHTML = (data.notes || []).length ? data.notes.map(n => `
    <tr>
      <td>${escapeHtmlAdmin(n.item_name || n.page_key || "obecný dotaz")}</td>
      <td>${escapeHtmlAdmin(n.body)}</td>
      <td>${fmtDateCz(n.created_at)}</td>
    </tr>
  `).join("") : `<tr><td colspan="3" style="color:var(--text-muted);">Zatím žádné dotazy.</td></tr>`;

  const byIpBody = document.getElementById("onlineOfferStatsByIp");
  byIpBody.innerHTML = (data.by_ip || []).length ? data.by_ip.map(r => `
    <tr><td>${escapeHtmlAdmin(r.ip_address)}</td><td>${r.visits}</td><td>${fmtDateCz(r.first_seen)}</td><td>${fmtDateCz(r.last_seen)}</td></tr>
  `).join("") : `<tr><td colspan="4" style="color:var(--text-muted);">Zatím žádná shlédnutí.</td></tr>`;

  const pageLabels = {
    cover: "Titulní strana", intro: "O nabízeném řešení", drawings_1: "Technické výkresy (1)",
    drawings_2: "Technické výkresy (2)", drawings_vandr: "Technické výkresy (Vandr)", view_3d: "3D pohledy", renders: "Vizualizace", pricing: "Cenová nabídka", closing: "Závěr",
  };
  const byPageBody = document.getElementById("onlineOfferStatsByPage");
  byPageBody.innerHTML = (data.by_page || []).map(r => `
    <tr>
      <td>${escapeHtmlAdmin(pageLabels[r.page_key] || r.page_key)}</td>
      <td>${r.views}</td><td>${r.unique_views}</td>
      <td>${fmtDurationMs(r.total_dwell_ms)}</td><td>${fmtDurationMs(r.avg_dwell_ms)}</td>
      <td>${r.views ? `${r.avg_scroll_pct}% / ${r.max_scroll_pct}%` : "—"}</td>
    </tr>
  `).join("");

  const clickLabels = {
    image_narys: "Obrázek: Nárys", image_bokorys: "Obrázek: Bokorys", image_pudorys: "Obrázek: Půdorys",
    image_view3d_a: "Obrázek: 3D pohled 1", image_view3d_b: "Obrázek: 3D pohled 2",
    total_price: "Celková cena", contact_email: "Kontakt: e-mail", contact_phone: "Kontakt: telefon", contact_web: "Kontakt: web",
    interact_3d_model: "3D model (otočení)", item_product_link: "Odkaz na e-shop (kusovník)",
    download_pdf: "Stažení PDF", bom_highlight: "Zvýraznění dílu v 3D", payment_qr: "QR Platba",
  };
  const byClickBody = document.getElementById("onlineOfferStatsByClick");
  byClickBody.innerHTML = (data.by_click || []).length ? data.by_click.map(r => `
    <tr><td>${escapeHtmlAdmin(clickLabels[r.target] || r.target)}</td><td>${r.clicks}</td><td>${r.unique_clicks}</td></tr>
  `).join("") : `<tr><td colspan="3" style="color:var(--text-muted);">Zatím žádné kliky.</td></tr>`;

  await loadOnlineOfferRevisions(offerId);
  document.getElementById("onlineOfferStatsModal").classList.add("open");
}

// Historie verzi (Robert 2026-08-10: "plne editovani nabidky v
// adminu") - samostatny fetch od /stats vyse (jiny endpoint, viz
// api/scene_offers.py::admin_scene_offer_revisions), radek kliknutelny
// -> read-only nahled stare verze (openOfferRevisionDetail).
async function loadOnlineOfferRevisions(offerId) {
  const resp = await fetch(`/api/admin/scene-offers/${offerId}/revisions`);
  const data = await resp.json().catch(() => ({}));
  const body = document.getElementById("onlineOfferStatsRevisions");
  if (!resp.ok || !(data.revisions || []).length) {
    body.innerHTML = `<tr><td colspan="5" style="color:var(--text-muted);">Nabídka zatím nebyla upravena.</td></tr>`;
    return;
  }
  body.innerHTML = data.revisions.map(r => `
    <tr class="offer-rev-row" data-rev-id="${r.id}">
      <td>${r.revision_number}</td>
      <td>${r.total_price.toLocaleString("cs-CZ")} Kč</td>
      <td>${escapeHtmlAdmin(r.edited_by_name || "-")}</td>
      <td>${fmtDateCz(r.edited_at)}</td>
      <td>${escapeHtmlAdmin(r.change_note || "")}</td>
    </tr>
  `).join("");
  body.querySelectorAll(".offer-rev-row").forEach(tr => {
    tr.onclick = () => openOfferRevisionDetail(parseInt(tr.dataset.revId, 10));
  });
}

async function openOfferRevisionDetail(revisionId) {
  const resp = await fetch(`/api/admin/scene-offers/revisions/${revisionId}`);
  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) { alert(data.error || "Verzi se nepodařilo načíst."); return; }
  document.getElementById("offerRevisionDetailTitle").textContent = `Verze ${data.revision_number}`;
  document.getElementById("offerRevisionDetailItems").innerHTML = (data.items || []).map(it => `
    <tr>
      <td>${escapeHtmlAdmin(it.name)}</td><td>${escapeHtmlAdmin(it.dim || "-")}</td>
      <td>${escapeHtmlAdmin(String(it.qty ?? ""))}</td>
      <td>${it.unit_price != null ? it.unit_price + " Kč" : "-"}</td>
      <td>${it.total} Kč</td>
    </tr>
  `).join("");
  document.getElementById("offerRevisionDetailTotal").textContent = `Celkem: ${data.total_price} Kč`;
  document.getElementById("offerRevisionDetailPopis").textContent = data.editable_text?.popis || "";
  document.getElementById("offerRevisionDetailModal").classList.add("open");
}
document.getElementById("btnOnlineOfferStatsClose").onclick = () => {
  document.getElementById("onlineOfferStatsModal").classList.remove("open");
};

// Editace nabidky (Robert 2026-08-10: "plne editovani nabidky v
// adminu") - ZAMERNE jen mnozstvi/cena EXISTUJICICH radku kusovniku +
// celkove texty, viz docstring backend endpointu (PUT .../scene-offers/
// <id> v api/scene_offers.py) proc ne pridavani/mazani radku.
let offerEditItems = [];
function offerEditRecalcRow(idx) {
  const it = offerEditItems[idx];
  const row = document.querySelector(`#offerEditItemsBody tr[data-idx="${idx}"]`);
  if (it.unit_price != null) {
    const qtyInput = row.querySelector(".oe-qty");
    const priceInput = row.querySelector(".oe-price");
    const n = parseFloat(qtyInput.value) || 0;
    // radky ze sceny maji mnozstvi "N ks" (retezec) - zapis zustane stejny, jinak by stranka po uprave ukazovala holou cisli bez "ks" (bot8, 2026-10-06)
    it.qty = (typeof it.qty === "string" && /ks\s*$/i.test(it.qty)) ? `${n} ks` : n;
    it.unit_price = parseFloat(priceInput.value) || 0;
    it.total = Math.round(n * it.unit_price);
  } else {
    // Paušální řádky bez jednotkové ceny (Cena řezů/spojů/manipulační
    // tarif...) - editovatelná je jen celková částka přímo.
    const totalInput = row.querySelector(".oe-total-flat");
    it.total = parseFloat(totalInput.value) || 0;
  }
  row.querySelector(".oe-row-total").textContent = it.total.toLocaleString("cs-CZ") + " Kč";
  offerEditUpdateGrandTotal();
}
function offerEditUpdateGrandTotal() {
  const total = offerEditItems.reduce((s, it) => s + (it.total || 0), 0);
  document.getElementById("offerEditTotal").textContent = `Celková cena: ${total.toLocaleString("cs-CZ")} Kč`;
}
function renderOfferEditItems() {
  document.getElementById("offerEditItemsBody").innerHTML = offerEditItems.map((it, idx) => it.manual ? "" : `
    <tr data-idx="${idx}">
      <td>${escapeHtmlAdmin(it.name)}</td>
      <td>${escapeHtmlAdmin(it.dim || "-")}</td>
      <td>${it.unit_price != null
        ? `<input type="number" class="oe-qty" min="0" step="1" value="${Number.isFinite(parseFloat(it.qty)) ? parseFloat(it.qty) : ""}">`
        : escapeHtmlAdmin(String(it.qty ?? ""))}</td>
      <td>${it.unit_price != null
        ? `<input type="number" class="oe-price" min="0" step="1" value="${it.unit_price}">`
        : "-"}</td>
      <td class="oe-row-total">${it.unit_price != null
        ? it.total.toLocaleString("cs-CZ") + " Kč"
        : `<input type="number" class="oe-total-flat" min="0" step="1" value="${it.total}">`}</td>
    </tr>
  `).join("");
  document.getElementById("offerEditItemsBody").querySelectorAll("tr").forEach(row => {
    const idx = parseInt(row.dataset.idx, 10);
    row.querySelectorAll(".oe-qty, .oe-price, .oe-total-flat").forEach(input => {
      input.addEventListener("input", () => offerEditRecalcRow(idx));
    });
  });
  renderOfferEditManual();
  offerEditUpdateGrandTotal();
}

// ---------------------------------------------------------------------------------------------------------------------
// RUCNI POLOZKY (bot8, 2026-10-06; Robert: "admin pripise do online nabidky dalsi polozky rucne z katalogu vcetne vlozeni 3D modelu, parametru a ceny" a "... jen jako
// volny text s nactenim obrazku (1-2 ks) a ceny"). Radek `items[].manual` ({typ: "katalog" | "text", popis, model, obrazky}) - pridava se na konec kusovniku, upravuje se
// vlastnim editorem pod tabulkou (obycejne radky ze sceny zustavaji beze zmeny: nejde je pridat, smazat ani prejmenovat). Server vsechno znovu overuje (api/scene_offers.py,
// _over_rucni_polozky). Staticky kod je zivy driv nez API, proto se tlacitka ukazou JEN kdyz edit-data nese priznak `rucni_polozky` (offerEditManualCfg).
// ---------------------------------------------------------------------------------------------------------------------
let offerEditManualCfg = null;            // {max, obrazky_max} z edit-data; null = backend to neumi
let offerEditUploads = 0;                 // rozpracovana nahravani obrazku (ulozeni pocka)
const offerEditManualMoney = n => (Number(n) || 0).toLocaleString("cs-CZ") + " Kč";
function offerEditManualIdxs() { return offerEditItems.map((it, i) => (it.manual ? i : -1)).filter(i => i >= 0); }
function offerEditPlainText(html) {
  if (!html) return "";
  const doc = new DOMParser().parseFromString(String(html), "text/html");           // bez spousteni skriptu
  return (doc.body.textContent || "").replace(/\s+/g, " ").trim();
}
// do atributu (value, data-*) je nutne escapovat i uvozovky - escapeHtmlAdmin je nechava (nazev z katalogu muze obsahovat " a ')
const offerEditAttr = s => escapeHtmlAdmin(s).replace(/"/g, "&quot;").replace(/'/g, "&#39;");
function offerEditManualStatus(text, cls) {
  const el = document.getElementById("offerEditManualStatus");
  el.textContent = text || ""; el.className = cls || "";
}
function renderOfferEditManual() {
  const wrap = document.getElementById("offerEditManualWrap");
  if (!offerEditManualCfg) { wrap.style.display = "none"; return; }
  wrap.style.display = "";
  const idxs = offerEditManualIdxs();
  const imgMax = offerEditManualCfg.obrazky_max || 2;
  document.getElementById("offerEditManualList").innerHTML = idxs.map((idx, pos) => {
    const it = offerEditItems[idx], m = it.manual, kat = m.typ === "katalog";
    const obr = Array.isArray(m.obrazky) ? m.obrazky : [];
    return `<div class="oe-mi" data-idx="${idx}">
      <div class="oe-mi-head">
        <span class="oe-mi-typ">${kat ? "Z katalogu · #" + escapeHtmlAdmin(it.product_id) : "Volný text"}</span>
        <span class="oe-mi-btns">
          <button type="button" class="oe-mi-up" title="Posunout výš" ${pos === 0 ? "disabled" : ""}>↑</button>
          <button type="button" class="oe-mi-down" title="Posunout níž" ${pos === idxs.length - 1 ? "disabled" : ""}>↓</button>
          <button type="button" class="oe-mi-del" title="Odebrat položku">✕</button>
        </span>
      </div>
      <div class="oe-mi-grid">
        <div class="oe-mi-c-name"><label>Název</label><input type="text" class="oe-mi-name" maxlength="200" value="${offerEditAttr(it.name)}"></div>
        <div class="oe-mi-c-dim"><label>Rozměr / parametr</label><input type="text" class="oe-mi-dim" maxlength="120" value="${offerEditAttr(it.dim || "")}" placeholder="např. 800 × 600 mm"></div>
        <div><label>Množství</label><input type="number" class="oe-mi-qty" min="1" max="999" step="1" value="${parseInt(it.qty, 10) || 1}"></div>
        <div><label>Cena/ks bez DPH (Kč)</label><input type="number" class="oe-mi-price" min="0" step="0.01" value="${it.unit_price != null ? it.unit_price : 0}"></div>
        <div><label>Celkem</label><div class="oe-mi-total">${offerEditManualMoney(it.total)}</div></div>
      </div>
      <label>Popis / parametry (zákazník je uvidí pod tabulkou)</label>
      <textarea class="oe-mi-popis" maxlength="2000">${escapeHtmlAdmin(m.popis || "")}</textarea>
      ${kat
        ? `<label class="oe-mi-check"><input type="checkbox" class="oe-mi-model" ${m.model ? "checked" : ""}> Ukázat zákazníkovi 3D model produktu <span class="oe-mi-hint"></span></label>`
        : `<label>Obrázky (nejvýše ${imgMax})</label>
           <div class="oe-mi-imgs">
             ${obr.map(k => `<span class="oe-mi-img" data-key="${offerEditAttr(k)}"><img src="/api/admin/scene-offers/${currentOnlineOfferId}/item-images/${encodeURIComponent(k)}" alt=""><button type="button" class="oe-mi-img-del" title="Odebrat obrázek">✕</button></span>`).join("")}
             ${obr.length < imgMax ? `<label class="oe-mi-add">+ Přidat obrázek<input type="file" class="oe-mi-file" accept="image/png,image/jpeg"></label>` : ""}
           </div>`}
    </div>`;
  }).join("");
  const nTotal = idxs.length, max = offerEditManualCfg.max || 20;
  document.getElementById("offerEditManualSearch").disabled = nTotal >= max;
  document.getElementById("btnOfferEditManualText").disabled = nTotal >= max;
  // saved catalog polozky: zjistit, jestli produkt STALE ma 3D model (hint + vypnuti zatrhavatka, at ulozeni nespadne na "nema 3D model")
  document.querySelectorAll("#offerEditManualList .oe-mi").forEach(card => {
    const it = offerEditItems[+card.dataset.idx];
    if (!it || !it.manual || it.manual.typ !== "katalog" || !it.product_id) return;
    offerEditProductHasModel(it.product_id).then(has => {
      if (has !== false) return;
      const cb = card.querySelector(".oe-mi-model");
      if (!cb) return;
      cb.checked = false; cb.disabled = true; it.manual.model = false;
      card.querySelector(".oe-mi-hint").textContent = "(produkt nemá 3D model)";
    });
  });
}
const offerEditModelCache = new Map();    // product_id -> true / false / null (nezjisteno)
async function offerEditProductHasModel(pid) {
  if (offerEditModelCache.has(pid)) return offerEditModelCache.get(pid);
  let has = null;
  try {
    const r = await fetch(`/api/shop/products/${encodeURIComponent(pid)}`);
    if (r.ok) { const d = await r.json(); has = !!(d.product && d.product.glb_file); }
  } catch (e) { /* nezjisteno - zatrhavatko zustane a server pri ulozeni overi */ }
  offerEditModelCache.set(pid, has);
  return has;
}
function offerEditManualSwap(idx, smer) {
  const idxs = offerEditManualIdxs(), pos = idxs.indexOf(idx), jiny = idxs[pos + smer];
  if (pos < 0 || jiny === undefined) return;
  [offerEditItems[idx], offerEditItems[jiny]] = [offerEditItems[jiny], offerEditItems[idx]];
  renderOfferEditManual();
}
// obrazek z disku -> data URI; vetsi nez 1,5 MB (fotky z mobilu) se zmensi na max 1600 px jako JPEG (server bere png / jpeg do 6 MB)
function offerEditImageDataUri(file) {
  return new Promise((resolve, reject) => {
    if (!/^image\/(png|jpeg)$/.test(file.type)) return reject(new Error("Obrázek musí být PNG nebo JPEG."));
    const fr = new FileReader();
    fr.onerror = () => reject(new Error("Soubor se nepodařilo přečíst."));
    fr.onload = () => {
      if (file.size <= 1500 * 1024) return resolve(fr.result);
      const img = new Image();
      img.onerror = () => reject(new Error("Soubor není platný obrázek."));
      img.onload = () => {
        const k = Math.min(1, 1600 / Math.max(img.naturalWidth, img.naturalHeight));
        const c = document.createElement("canvas");
        c.width = Math.max(1, Math.round(img.naturalWidth * k)); c.height = Math.max(1, Math.round(img.naturalHeight * k));
        const g = c.getContext("2d"); g.fillStyle = "#fff"; g.fillRect(0, 0, c.width, c.height); g.drawImage(img, 0, 0, c.width, c.height);
        resolve(c.toDataURL("image/jpeg", 0.88));
      };
      img.src = fr.result;
    };
    fr.readAsDataURL(file);
  });
}
async function offerEditUploadImage(it, file) {
  offerEditUploads++;
  offerEditManualStatus("Nahrávám obrázek…", "");
  try {
    const uri = await offerEditImageDataUri(file);
    const r = await fetch(`/api/admin/scene-offers/${currentOnlineOfferId}/item-images`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ image: uri }),
    });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(d.error || "Obrázek se nepodařilo nahrát.");
    if (!Array.isArray(it.manual.obrazky)) it.manual.obrazky = [];
    it.manual.obrazky.push(d.key);
    offerEditManualStatus("", "");
    renderOfferEditManual();
  } catch (e) {
    offerEditManualStatus(e.message || "Obrázek se nepodařilo nahrát.", "err");
  } finally {
    offerEditUploads--;
  }
}
function offerEditAddCatalogItem(p) {
  if (!p || offerEditManualIdxs().length >= (offerEditManualCfg.max || 20)) return;
  const price = p.price_czk_placeholder != null && isFinite(Number(p.price_czk_placeholder)) ? Number(p.price_czk_placeholder) : 0;   // cena z katalogu = vychozi hodnota, admin ji prepise
  offerEditModelCache.set(p.id, !!p.glb_file);
  offerEditItems.push({
    name: String(p.name || "").slice(0, 200), dim: "", qty: 1, unit_price: price, total: Math.round(price), product_id: p.id,
    manual: { typ: "katalog", popis: offerEditPlainText(p.description).slice(0, 2000), model: !!p.glb_file },
  });
  renderOfferEditManual(); offerEditUpdateGrandTotal();
  offerEditManualStatus("", "");
}
function offerEditAddTextItem() {
  if (offerEditManualIdxs().length >= (offerEditManualCfg.max || 20)) return;
  offerEditItems.push({ name: "", dim: "", qty: 1, unit_price: 0, total: 0, manual: { typ: "text", popis: "", obrazky: [] } });
  renderOfferEditManual(); offerEditUpdateGrandTotal();
  const jmena = document.querySelectorAll("#offerEditManualList .oe-mi-name");
  if (jmena.length) jmena[jmena.length - 1].focus();
}
let offerEditSearchTimer = null, offerEditSearchSeq = 0;
function offerEditCatalogSearch() {
  const input = document.getElementById("offerEditManualSearch"), box = document.getElementById("offerEditManualSuggest");
  const q = input.value.trim();
  if (q.length < 2) { box.classList.remove("open"); box.innerHTML = ""; return; }
  const seq = ++offerEditSearchSeq;
  fetch(`/api/shop/products?all=1&q=${encodeURIComponent(q)}&page_size=12`).then(r => r.json()).then(data => {
    if (seq !== offerEditSearchSeq) return;                 // pozdni odpoved na starsi dotaz
    const list = data.products || [];
    box.innerHTML = list.length
      ? list.map(p => `<div class="ps-row" data-id="${p.id}">${escapeHtmlAdmin(p.name)} <span class="ps-sku">(${escapeHtmlAdmin(p.sku)})</span>${p.glb_file ? ' <span class="ps-note">3D</span>' : ""}
          <span class="ps-sku">· ${p.price_czk_placeholder != null ? offerEditManualMoney(p.price_czk_placeholder) : "bez ceny"}</span></div>`).join("")
      : '<div class="ps-empty">Žádný produkt neodpovídá hledání.</div>';
    box.querySelectorAll(".ps-row").forEach(row => {
      row.onclick = () => {
        offerEditAddCatalogItem(list.find(p => String(p.id) === row.dataset.id));
        input.value = ""; box.classList.remove("open"); box.innerHTML = "";
      };
    });
    box.classList.add("open");
  }).catch(() => {});
}
(function wireOfferEditManual() {
  const input = document.getElementById("offerEditManualSearch");
  input.addEventListener("input", () => { clearTimeout(offerEditSearchTimer); offerEditSearchTimer = setTimeout(offerEditCatalogSearch, 250); });
  input.addEventListener("blur", () => setTimeout(() => document.getElementById("offerEditManualSuggest").classList.remove("open"), 150));
  document.getElementById("btnOfferEditManualText").onclick = offerEditAddTextItem;
  const list = document.getElementById("offerEditManualList");
  const polozka = ev => { const card = ev.target.closest(".oe-mi"); const it = card && offerEditItems[+card.dataset.idx]; return it && it.manual ? { card, it } : null; };
  list.addEventListener("input", ev => {
    const x = polozka(ev); if (!x) return;
    const c = ev.target.classList;
    if (c.contains("oe-mi-name")) x.it.name = ev.target.value;
    else if (c.contains("oe-mi-dim")) x.it.dim = ev.target.value;
    else if (c.contains("oe-mi-popis")) x.it.manual.popis = ev.target.value;
    else if (c.contains("oe-mi-qty") || c.contains("oe-mi-price")) {
      x.it.qty = parseInt(x.card.querySelector(".oe-mi-qty").value, 10) || 0;
      x.it.unit_price = parseFloat(x.card.querySelector(".oe-mi-price").value) || 0;
      x.it.total = Math.round(x.it.qty * x.it.unit_price);
      x.card.querySelector(".oe-mi-total").textContent = offerEditManualMoney(x.it.total);
      offerEditUpdateGrandTotal();
    }
  });
  list.addEventListener("change", ev => {
    const x = polozka(ev); if (!x) return;
    if (ev.target.classList.contains("oe-mi-model")) x.it.manual.model = ev.target.checked;
    else if (ev.target.classList.contains("oe-mi-file") && ev.target.files && ev.target.files[0]) offerEditUploadImage(x.it, ev.target.files[0]);
  });
  list.addEventListener("click", ev => {
    const x = polozka(ev); if (!x) return;
    const idx = +x.card.dataset.idx, c = ev.target.classList;
    if (c.contains("oe-mi-del")) { offerEditItems.splice(idx, 1); renderOfferEditManual(); offerEditUpdateGrandTotal(); }
    else if (c.contains("oe-mi-up")) offerEditManualSwap(idx, -1);
    else if (c.contains("oe-mi-down")) offerEditManualSwap(idx, 1);
    else if (c.contains("oe-mi-img-del")) {
      const key = ev.target.closest(".oe-mi-img").dataset.key;
      x.it.manual.obrazky = (x.it.manual.obrazky || []).filter(k => k !== key);
      renderOfferEditManual();
    }
  });
})();
// bot16, 2026-09-14 (Robert primo: "volba nechci kusovnik s zadnymi
// cenami, vlozeni individualni ceny") - prepina #offerEditTotal (auto-
// soucet radku) <-> #offerEditCustomTotalWrap (rucne zadavane cislo).
// Pri zapnuti se input predvyplni AKTUALNIM souctem/hodnotou (at
// admin nezacina od nuly), ne pri kazdem prekresleni - proto zvlast
// "seed" jen z openOfferEditModal, tady jen viditelnost.
function offerEditSyncHideBomPricesUI() {
  const on = document.getElementById("offerEditHideBomPrices").checked;
  document.getElementById("offerEditTotal").style.display = on ? "none" : "";
  document.getElementById("offerEditCustomTotalWrap").style.display = on ? "" : "none";
}
document.getElementById("offerEditHideBomPrices").onchange = offerEditSyncHideBomPricesUI;
function offerEditSyncFixedDepositUI() {
  document.getElementById("offerEditFixedDepositWrap").style.display =
    document.getElementById("offerEditFixedDepositOn").checked ? "" : "none";
}
document.getElementById("offerEditFixedDepositOn").onchange = offerEditSyncFixedDepositUI;
// bot5, 2026-09-28: rucni prebiti ceny dopravy pro "Smontovano" davá
// smysl jen u sestav BEZ montaze (u sestavy do auta se "Dodani ve
// stavu" vubec nenabizi, viz nabidka-online.html) - schovat, at admin
// nezadava cislo, ktere se stejne nikde nepouzije.
function offerEditSyncVehicleAssemblyUI() {
  document.getElementById("offerEditManualShippingWrap").style.display =
    document.getElementById("offerEditIsVehicleAssembly").checked ? "none" : "";
}
document.getElementById("offerEditIsVehicleAssembly").onchange = offerEditSyncVehicleAssemblyUI;

let offerEditCustomerNameSupported = false;
let offerEditDiscountSupported = false;           // sleva v %: jen s backendem, ktery ji umi (edit-data nese priznak `sleva`), jinak by starsi API hodnotu potichu zahodilo
async function openOfferEditModal() {
  document.getElementById("onlineOfferStatsModal").classList.remove("open");
  const resp = await fetch(`/api/admin/scene-offers/${currentOnlineOfferId}/edit-data`);
  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) { alert(data.error || "Data k editaci se nepodařilo načíst."); return; }
  document.getElementById("offerEditTitle").textContent = `Upravit nabídku ${data.offer_number}`;
  offerEditItems = data.items;
  offerEditManualCfg = data.rucni_polozky && typeof data.rucni_polozky === "object" ? data.rucni_polozky : null;   // backend s rucnimi polozkami (jinak se editor neukaze)
  offerEditManualStatus("", "");
  renderOfferEditItems();
  // pole Klient jen kdyz backend jmeno klienta umi (edit-data nese customer_name) - staticky kod je zivy driv nez API; starsi backend by jmeno potichu zahodil
  offerEditCustomerNameSupported = "customer_name" in data;
  document.getElementById("offerEditCustomerNameLabel").style.display = document.getElementById("offerEditCustomerName").style.display = offerEditCustomerNameSupported ? "" : "none";
  document.getElementById("offerEditCustomerName").value = data.customer_name || "";
  offerEditDiscountSupported = !!(data.sleva && typeof data.sleva === "object");
  document.getElementById("offerEditDiscountRow").style.display = offerEditDiscountSupported ? "" : "none";
  document.getElementById("offerEditPopis").value = data.editable_text.popis || "";
  document.getElementById("offerEditPatka").value = data.editable_text.patka || "";
  const opts = data.offer_options || {};
  document.getElementById("offerEditShowQr").checked = opts.show_qr !== false;
  document.getElementById("offerEditDeliveryTerm").value = opts.delivery_term || "";
  document.getElementById("offerEditHiddenPayment").value = opts.hidden_payment_method || "";
  document.getElementById("offerEditHiddenDeliveryState").value = opts.hidden_delivery_state || "";
  document.getElementById("offerEditFixedDepositOn").checked = opts.fixed_deposit_pct != null;
  document.getElementById("offerEditFixedDepositPct").value = opts.fixed_deposit_pct || 70;
  offerEditSyncFixedDepositUI();
  document.getElementById("offerEditHideBomPrices").checked = !!opts.hide_bom_prices;
  document.getElementById("offerEditCustomTotal").value = data.total_price;
  offerEditSyncHideBomPricesUI();
  document.getElementById("offerEditIsVehicleAssembly").checked = !!opts.is_vehicle_assembly;
  document.getElementById("offerEditManualShipping").value = opts.manual_assembled_shipping_czk != null ? opts.manual_assembled_shipping_czk : "";
  document.getElementById("offerEditMontazPct").value = opts.montaz_pct != null ? opts.montaz_pct : "";
  document.getElementById("offerEditDiscountPct").value = opts.discount_pct != null ? opts.discount_pct : "";       // sleva (bot16, 2026-10-07): prazdne = bez slevy
  offerEditSyncVehicleAssemblyUI();
  document.getElementById("offerEditChangeNote").value = "";
  const statusEl = document.getElementById("offerEditStatus");
  statusEl.textContent = ""; statusEl.className = "";
  document.getElementById("offerEditModal").classList.add("open");
}
document.getElementById("btnOnlineOfferEditOpen").onclick = openOfferEditModal;
document.getElementById("btnOfferEditCancel").onclick = () => {
  document.getElementById("offerEditModal").classList.remove("open");
};
document.getElementById("btnOfferEditSave").onclick = async () => {
  const saveBtn = document.getElementById("btnOfferEditSave");
  const statusEl = document.getElementById("offerEditStatus");
  if (offerEditUploads > 0) {
    statusEl.textContent = "Počkejte, nahrává se obrázek."; statusEl.className = "err";
    return;
  }
  const hideBomPrices = document.getElementById("offerEditHideBomPrices").checked;
  // "vlozeni individualni ceny" - kdyz je zapnute, total_price jde z
  // rucne zadaneho cisla, ne ze souctu radku kusovniku (ktery se navic
  // vubec neukaze zakaznikovi, viz nabidka-online.html).
  const total = hideBomPrices
    ? (parseFloat(document.getElementById("offerEditCustomTotal").value) || 0)
    : offerEditItems.reduce((s, it) => s + (it.total || 0), 0);
  const fixedDepositOn = document.getElementById("offerEditFixedDepositOn").checked;
  // Sazba montaze (bot5, 2026-10-01): prazdne = vychozi sazba z nastaveni (null), jinak 0-100 %
  const montazRaw = document.getElementById("offerEditMontazPct").value.trim().replace(",", ".");
  const montazPct = montazRaw === "" ? null : parseFloat(montazRaw);
  if (montazPct !== null && !(montazPct >= 0 && montazPct <= 100)) {
    statusEl.textContent = "Montáž musí být číslo od 0 do 100 %."; statusEl.className = "err";
    return;
  }
  // Sleva (bot16, 2026-10-07; Robert: "nabidnout slevu v cenovem souhrnu online nabidky, i zpetne"): % z ceny zbozi, prazdne = bez slevy (null), jinak 0-100 %
  const slevaRaw = document.getElementById("offerEditDiscountPct").value.trim().replace(",", ".");
  const slevaPct = slevaRaw === "" ? null : parseFloat(slevaRaw);
  if (offerEditDiscountSupported && slevaPct !== null && !(slevaPct >= 0 && slevaPct <= 100)) {
    statusEl.textContent = "Sleva musí být číslo od 0 do 100 %."; statusEl.className = "err";
    return;
  }
  saveBtn.disabled = true;
  try {
    const resp = await fetch(`/api/admin/scene-offers/${currentOnlineOfferId}`, {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        items: offerEditItems, total_price: total,
        ...(offerEditCustomerNameSupported ? { customer_name: document.getElementById("offerEditCustomerName").value } : {}),
        editable_text: {
          popis: document.getElementById("offerEditPopis").value,
          patka: document.getElementById("offerEditPatka").value,
        },
        offer_options: {
          show_qr: document.getElementById("offerEditShowQr").checked,
          delivery_term: document.getElementById("offerEditDeliveryTerm").value,
          hidden_payment_method: document.getElementById("offerEditHiddenPayment").value || null,
          hidden_delivery_state: document.getElementById("offerEditHiddenDeliveryState").value || null,
          fixed_deposit_pct: fixedDepositOn
            ? (parseInt(document.getElementById("offerEditFixedDepositPct").value, 10) || 70)
            : null,
          hide_bom_prices: hideBomPrices,
          is_vehicle_assembly: document.getElementById("offerEditIsVehicleAssembly").checked,
          manual_assembled_shipping_czk: (() => {
            const v = document.getElementById("offerEditManualShipping").value;
            return v === "" ? null : parseFloat(v);
          })(),
          montaz_pct: montazPct,
          ...(offerEditDiscountSupported ? { discount_pct: slevaPct } : {}),      // bez podpory v API se klic neposila (backend chybejici klic zachova)
        },
        change_note: document.getElementById("offerEditChangeNote").value,
      }),
    });
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) { statusEl.textContent = data.error || "Uložení se nepodařilo."; statusEl.className = "err"; saveBtn.disabled = false; return; }
    statusEl.textContent = "✓ Uloženo."; statusEl.className = "ok";
    setTimeout(() => {
      document.getElementById("offerEditModal").classList.remove("open");
      saveBtn.disabled = false;
      openOnlineOfferStats(currentOnlineOfferId);
      loadOnlineOffersList();
    }, 700);
  } catch (e) {
    statusEl.textContent = "Chyba spojení."; statusEl.className = "err";
    saveBtn.disabled = false;
  }
};

// Filtr disku (stejny vzor jako u Nabidek: hledani + Filtrovat + Reset).
// Hleda napric CELYM stromem (soubory i slozky podle nazvu) a vysledky
// ukaze naplocho s cestou - stejne "prohledej vsechno" chovani, jake ma
// hledani v Nabidkach pres vsechny nabidky.
function driveCollectMatches(q) {
  const out = { files: [], folders: [] };
  const walk = (folders, path) => {
    folders.forEach(f => {
      const p = path ? `${path} / ${f.name}` : f.name;
      if (f.name.toLowerCase().includes(q)) out.folders.push({ folder: f, path: p });
      (f.files || []).forEach(file => {
        if (file.filename.toLowerCase().includes(q)) out.files.push({ file, path: p });
      });
      walk(f.children || [], p);
    });
  };
  (driveData.root_files || []).forEach(file => {
    if (file.filename.toLowerCase().includes(q)) out.files.push({ file, path: "Kořen disku" });
  });
  walk(driveData.folders || [], "");
  return out;
}
function renderDriveSearchResults() {
  const box = document.getElementById("driveSearchResults");
  const q = document.getElementById("driveSearchQ").value.trim().toLowerCase();
  if (!q || !driveData) { box.style.display = "none"; box.innerHTML = ""; return; }
  const m = driveCollectMatches(q);
  const folderRows = m.folders.map(x => `
    <div class="crm-task-row" data-goto-folder="${x.folder.id}" style="cursor:pointer;">
      <span class="crm-task-title">📁 ${escapeHtmlAdmin(x.path)}</span>
    </div>`).join("");
  const fileRows = m.files.map(x => {
    const isPdf = x.file.content_type === "application/pdf" || /\.pdf$/i.test(x.file.filename || "");
    return `
    <div class="crm-note-row">
      <span class="crm-note-body">${escapeHtmlAdmin(x.file.filename)}
        <span style="color:var(--text-muted);">(${escapeHtmlAdmin(x.path)}, ${driveFmtSize(x.file.size_bytes)})</span></span>
      ${isPdf ? `<a href="/api/admin/drive/files/${x.file.id}/preview" target="_blank">Zobrazit</a>` : ""}
      <a href="/api/admin/drive/files/${x.file.id}/download">Stáhnout</a>
    </div>`;
  }).join("");
  box.innerHTML = `<h4 style="margin:0 0 8px;">Výsledky hledání (${m.folders.length + m.files.length})</h4>`
    + (folderRows || "") + (fileRows || "")
    + (!folderRows && !fileRows ? '<div style="color:#8b93a1;font-size:12px;">Nic nenalezeno.</div>' : "");
  box.style.display = "";
  box.querySelectorAll("[data-goto-folder]").forEach(row => {
    row.onclick = () => {
      driveSelectedFolderId = parseInt(row.dataset.gotoFolder, 10);
      document.getElementById("driveSearchQ").value = "";
      renderDriveSearchResults();
      renderDriveFolderTree();
      renderDriveFolderContents();
    };
  });
}
document.getElementById("driveSearchApply").onclick = renderDriveSearchResults;
document.getElementById("driveSearchQ").addEventListener("keydown", (e) => { if (e.key === "Enter") renderDriveSearchResults(); });
document.getElementById("driveSearchReset").onclick = () => {
  document.getElementById("driveSearchQ").value = "";
  renderDriveSearchResults();
};

// ==================== NABIDKY (bot5, 2026-08-01) ====================
// Detail neni modal (strom slozek se do modalu nevejde citelne) -
// prepinani #quotesListView / #quoteDetailView v ramci jedne zalozky.
let quoteFilter = { q: "", page: 1, page_size: 50 };
let quoteListCache = [];
let quoteDetailId = null;
let quoteDetailData = null;
let quoteSelectedFolderId = null; // null = koren nabidky

function quoteFmtTime(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleString("cs-CZ", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" });
}
function quoteFmtSize(bytes) {
  if (bytes == null) return "";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} kB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

async function loadQuotesList() {
  try {
    const params = new URLSearchParams({ page: quoteFilter.page, page_size: quoteFilter.page_size });
    if (quoteFilter.q) params.set("q", quoteFilter.q);
    const r = await fetch(`/api/admin/crm/quotes?${params.toString()}`);
    if (!r.ok) throw new Error("HTTP " + r.status);
    const data = await r.json();
    quoteListCache = data.quotes || [];
    renderQuotesTable();
    renderPager("quotesPager", data, quoteFilter, loadQuotesList);
  } catch (e) {
    document.getElementById("quotesErr").textContent = "Chyba načtení: " + e.message;
  }
}

// Robert 2026-08-02: "pridej obema bulk mazani s fajkama" - checkbox na
// radku nabidky + Vybrat vse v hlavicce + Smazat vybrane u filtru.
const quoteSelectedIds = new Set();
function updateQuotesBulkUi() {
  const btn = document.getElementById("quotesBulkDelete");
  btn.style.display = quoteSelectedIds.size ? "" : "none";
  btn.textContent = `Smazat vybrané (${quoteSelectedIds.size})`;
  const all = document.getElementById("quotesSelectAll");
  if (all) all.checked = quoteListCache.length > 0 && quoteListCache.every(q => quoteSelectedIds.has(q.id));
}
function renderQuotesTable() {
  const tbody = document.getElementById("quotesTbody");
  const live = new Set(quoteListCache.map(q => q.id));
  [...quoteSelectedIds].forEach(id => { if (!live.has(id)) quoteSelectedIds.delete(id); });
  tbody.innerHTML = quoteListCache.map(q => `
    <tr data-id="${q.id}" style="cursor:pointer;">
      <td><input type="checkbox" class="quote-select-cb" data-id="${q.id}" ${quoteSelectedIds.has(q.id) ? "checked" : ""} onclick="event.stopPropagation()"></td>
      <td>${escapeHtmlAdmin(q.quote_number)}</td>
      <td>${escapeHtmlAdmin(q.client_label)}</td>
      <td>${escapeHtmlAdmin(q.title || "")}</td>
      <td>${quoteFmtTime(q.created_at)}</td>
    </tr>
  `).join("") || '<tr><td colspan="5" style="color:#8b93a1;">Žádné nabídky neodpovídají filtru.</td></tr>';
  tbody.querySelectorAll("tr[data-id]").forEach(tr => {
    tr.onclick = () => openQuoteDetail(parseInt(tr.dataset.id, 10));
  });
  tbody.querySelectorAll(".quote-select-cb").forEach(cb => {
    cb.onchange = () => {
      const id = parseInt(cb.dataset.id, 10);
      if (cb.checked) quoteSelectedIds.add(id); else quoteSelectedIds.delete(id);
      updateQuotesBulkUi();
    };
  });
  updateQuotesBulkUi();
}
document.getElementById("quotesSelectAll").onchange = (e) => {
  if (e.target.checked) quoteListCache.forEach(q => quoteSelectedIds.add(q.id));
  else quoteSelectedIds.clear();
  renderQuotesTable();
};
document.getElementById("quotesBulkDelete").onclick = async () => {
  if (!quoteSelectedIds.size) return;
  if (!confirm(`Trvale smazat ${quoteSelectedIds.size} vybraných nabídek včetně všech jejich složek a souborů? Tohle nejde vrátit.`)) return;
  await Promise.all([...quoteSelectedIds].map(id => fetch(`/api/admin/crm/quotes/${id}`, { method: "DELETE" })));
  quoteSelectedIds.clear();
  loadQuotesList();
};

document.getElementById("quotesSearchApply").onclick = () => {
  quoteFilter.q = document.getElementById("quotesSearchQ").value.trim();
  quoteFilter.page = 1;
  loadQuotesList();
};
document.getElementById("quotesSearchReset").onclick = () => {
  document.getElementById("quotesSearchQ").value = "";
  quoteFilter = { q: "", page: 1, page_size: quoteFilter.page_size };
  loadQuotesList();
};
document.getElementById("quotesSearchQ").addEventListener("keydown", (e) => {
  if (e.key === "Enter") { e.preventDefault(); document.getElementById("quotesSearchApply").click(); }
});

function openQuoteNewModal() {
  document.getElementById("quoteNewClientLabel").value = "";
  document.getElementById("quoteNewTitle").value = "";
  document.getElementById("quoteNewErr").textContent = "";
  document.getElementById("quoteNewModal").classList.add("open");
}
function closeQuoteNewModal() {
  document.getElementById("quoteNewModal").classList.remove("open");
}
document.getElementById("btnQuoteNew").onclick = openQuoteNewModal;
document.getElementById("quoteNewCancel").onclick = closeQuoteNewModal;
document.getElementById("quoteNewModal").addEventListener("click", (e) => {
  if (e.target.id === "quoteNewModal") closeQuoteNewModal();
});
document.getElementById("quoteNewSave").onclick = async () => {
  const client_label = document.getElementById("quoteNewClientLabel").value.trim();
  const errEl = document.getElementById("quoteNewErr");
  if (!client_label) { errEl.textContent = "Název klienta je povinný."; return; }
  try {
    const r = await fetch("/api/admin/crm/quotes", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ client_label, title: document.getElementById("quoteNewTitle").value.trim() }),
    });
    const data = await r.json();
    if (!r.ok) { errEl.textContent = data.error || "Chyba."; return; }
    closeQuoteNewModal();
    loadQuotesList();
    openQuoteDetail(data.id);
  } catch (e) {
    errEl.textContent = "Chyba: " + e.message;
  }
};

async function openQuoteDetail(quoteId) {
  quoteDetailId = quoteId;
  quoteSelectedFolderId = null;
  document.getElementById("quotesListView").style.display = "none";
  document.getElementById("quoteDetailView").style.display = "block";
  await loadQuoteDetail();
}

function closeQuoteDetail() {
  quoteDetailId = null;
  document.getElementById("quoteDetailView").style.display = "none";
  document.getElementById("quotesListView").style.display = "block";
  loadQuotesList();
}
document.getElementById("btnQuoteBackToList").onclick = closeQuoteDetail;

async function loadQuoteDetail() {
  if (!quoteDetailId) return;
  try {
    const r = await fetch(`/api/admin/crm/quotes/${quoteDetailId}`);
    if (!r.ok) throw new Error("HTTP " + r.status);
    quoteDetailData = await r.json();
    document.getElementById("quoteDetailTitle").textContent =
      `${quoteDetailData.quote.quote_number} — ${quoteDetailData.quote.client_label}`;
    document.getElementById("quoteDetailClientLabel").value = quoteDetailData.quote.client_label || "";
    document.getElementById("quoteDetailTitleInput").value = quoteDetailData.quote.title || "";
    renderQuoteOrderLink();
    renderQuoteFolderTree();
    renderQuoteFolderContents();
  } catch (e) {
    document.getElementById("quoteDetailErr").textContent = "Chyba načtení: " + e.message;
  }
}

// Robert (pres bot3, 2026-09-04, schvalene doporuceni z Dolibarr/ERPNext
// rozboru): "crm_quotes -> formalni order_id vazba + akce Vytvorit
// objednavku z nabidky". Nabidka nema polozkovy rozpis (jen PDF prilohy),
// takze "vytvorit objednavku" = otevrit STAVAJICI rucni formular
// (#manualOrderModal, admin.html) s predvyplnenym kontaktem - polozky
// zada admin rucne, presne jako u kazde jine rucni objednavky. Po
// uspesnem vytvoreni se nabidka automaticky propoji (viz manualOrderSubmit
// v admin.html).
function renderQuoteOrderLink() {
  const wrap = document.getElementById("quoteOrderLinkWrap");
  const info = quoteDetailData.order_info;
  if (info) {
    wrap.innerHTML = `
      <div style="font-size:13px;color:#c7ccd4;">
        <b>Objednávka:</b>
        <a href="#" id="quoteOrderLinkGoto" style="color:var(--accent);">${escapeHtmlAdmin(info.order_number)} – ${escapeHtmlAdmin(info.customer_name || "")} (${Number(info.total_czk).toLocaleString("cs-CZ")} Kč)</a>
        <button id="quoteOrderLinkDetach" style="margin-left:8px;font-size:11px;padding:2px 8px;">Odpojit</button>
      </div>`;
    document.getElementById("quoteOrderLinkGoto").onclick = (e) => {
      e.preventDefault();
      const btn = document.querySelector('.tab-btn[data-tab="orders"]');
      if (btn) btn.click();
      if (typeof openOrderDetail === "function") openOrderDetail(info.id);
    };
    document.getElementById("quoteOrderLinkDetach").onclick = async () => {
      if (!confirm("Odpojit nabídku od objednávky? Objednávka samotná zůstane beze změny.")) return;
      const errEl = document.getElementById("quoteDetailErr");
      try {
        const r = await fetch(`/api/admin/crm/quotes/${quoteDetailId}`, {
          method: "PUT", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ order_id: null }),
        });
        const data = await r.json();
        if (!r.ok) { errEl.textContent = data.error || "Chyba."; return; }
        errEl.textContent = "";
        loadQuoteDetail();
      } catch (e) {
        errEl.textContent = "Chyba: " + e.message;
      }
    };
  } else {
    wrap.innerHTML = `
      <div style="font-size:13px;color:#8a909c;">
        <b>Objednávka:</b> zatím nepřiřazena
        <button id="quoteOrderLinkCreate" style="margin-left:8px;font-size:12px;">Vytvořit objednávku z nabídky</button>
      </div>`;
    document.getElementById("quoteOrderLinkCreate").onclick = () => {
      openManualOrderModal({
        name: quoteDetailData.quote.client_label || "",
        email: quoteDetailData.quote.contact_email || "",
        linkQuoteId: quoteDetailId,
      });
    };
  }
}

document.getElementById("btnQuoteDetailSave").onclick = async () => {
  if (!quoteDetailId) return;
  const errEl = document.getElementById("quoteDetailErr");
  try {
    const r = await fetch(`/api/admin/crm/quotes/${quoteDetailId}`, {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        client_label: document.getElementById("quoteDetailClientLabel").value.trim(),
        title: document.getElementById("quoteDetailTitleInput").value.trim(),
      }),
    });
    const data = await r.json();
    if (!r.ok) { errEl.textContent = data.error || "Chyba."; return; }
    errEl.textContent = "";
    loadQuoteDetail();
  } catch (e) {
    errEl.textContent = "Chyba: " + e.message;
  }
};

function quoteFindFolder(folders, id) {
  for (const f of folders) {
    if (f.id === id) return f;
    const found = quoteFindFolder(f.children, id);
    if (found) return found;
  }
  return null;
}

function renderQuoteFolderTree() {
  const wrap = document.getElementById("quoteFolderTree");
  const rootActive = quoteSelectedFolderId === null;
  let html = `<div class="qf-tree-row${rootActive ? " active" : ""}" data-id="">📁 Kořen nabídky</div>`;
  function renderNode(f, depth) {
    const active = quoteSelectedFolderId === f.id;
    let out = `<div class="qf-tree-row${active ? " active" : ""}" data-id="${f.id}" style="padding-left:${depth * 14 + 8}px;">📁 ${escapeHtmlAdmin(f.name)}</div>`;
    f.children.forEach(c => { out += renderNode(c, depth + 1); });
    return out;
  }
  quoteDetailData.folders.forEach(f => { html += renderNode(f, 1); });
  wrap.innerHTML = html + `<div class="crm-add-row" style="margin-top:10px;">
      <input type="text" id="quoteNewFolderName" placeholder="Nová složka…">
      <button id="btnQuoteAddFolder">Přidat</button>
    </div>`;
  wrap.querySelectorAll(".qf-tree-row[data-id]").forEach(row => {
    row.onclick = () => {
      quoteSelectedFolderId = row.dataset.id === "" ? null : parseInt(row.dataset.id, 10);
      renderQuoteFolderTree();
      renderQuoteFolderContents();
    };
  });
  document.getElementById("btnQuoteAddFolder").onclick = async () => {
    const nameEl = document.getElementById("quoteNewFolderName");
    const name = nameEl.value.trim();
    if (!name) return;
    await fetch(`/api/admin/crm/quotes/${quoteDetailId}/folders`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, parent_folder_id: quoteSelectedFolderId }),
    });
    loadQuoteDetail();
  };
}

function renderQuoteFolderContents() {
  const wrap = document.getElementById("quoteFolderContents");
  const folder = quoteSelectedFolderId === null ? null : quoteFindFolder(quoteDetailData.folders, quoteSelectedFolderId);
  const files = quoteSelectedFolderId === null ? quoteDetailData.root_files : (folder ? folder.files : []);
  const subfolders = quoteSelectedFolderId === null ? quoteDetailData.folders : (folder ? folder.children : []);

  const header = quoteSelectedFolderId === null
    ? `<h4 style="margin:0 0 10px;">Kořen nabídky</h4>`
    : `<div style="display:flex;gap:8px;align-items:center;margin-bottom:10px;flex-wrap:wrap;">
         <input type="text" id="quoteFolderRenameInput" value="${escapeHtmlAdmin(folder ? folder.name : "")}" style="flex:1 1 160px;">
         <button id="btnQuoteFolderRename">Přejmenovat</button>
         <button id="btnQuoteFolderDelete" class="danger">Smazat složku</button>
       </div>`;

  const subfolderRows = subfolders.map(f => `
    <div class="crm-task-row" data-folder-id="${f.id}" style="cursor:pointer;">
      <span class="crm-task-title">📁 ${escapeHtmlAdmin(f.name)}</span>
    </div>
  `).join("");

  const fileRows = files.map(f => {
    const isPdf = f.content_type === "application/pdf" || /\.pdf$/i.test(f.filename || "");
    return `
    <div class="crm-note-row" data-file-id="${f.id}">
      <span class="crm-note-body">${escapeHtmlAdmin(f.filename)} <span style="color:var(--text-muted);">(${quoteFmtSize(f.size_bytes)}${f.source === "email_attachment" ? ", z e-mailu" : ""})</span></span>
      ${isPdf ? `<a href="/api/admin/crm/quotes/${quoteDetailId}/files/${f.id}/preview" target="_blank">Zobrazit</a>` : ""}
      <a href="/api/admin/crm/quotes/${quoteDetailId}/files/${f.id}/download">Stáhnout</a>
      <button class="crm-del-btn qf-file-del" data-id="${f.id}" title="Smazat soubor">✕</button>
    </div>
  `;
  }).join("");

  wrap.innerHTML = header
    + (subfolderRows ? `<div style="margin-bottom:10px;">${subfolderRows}</div>` : "")
    + (fileRows || '<div style="color:#8b93a1;font-size:12px;">Žádné soubory.</div>')
    + `<div class="crm-add-row" style="margin-top:10px;">
         <input type="file" id="quoteFileInput" multiple style="flex:1 1 auto;">
         <button id="btnQuoteFileUpload">Nahrát</button>
       </div>`;

  wrap.querySelectorAll(".qf-file-del").forEach(btn => {
    btn.onclick = async () => {
      if (!confirm("Smazat soubor?")) return;
      await fetch(`/api/admin/crm/quotes/${quoteDetailId}/files/${btn.dataset.id}`, { method: "DELETE" });
      loadQuoteDetail();
    };
  });
  wrap.querySelectorAll("[data-folder-id]").forEach(row => {
    row.onclick = () => {
      quoteSelectedFolderId = parseInt(row.dataset.folderId, 10);
      renderQuoteFolderTree();
      renderQuoteFolderContents();
    };
  });
  if (quoteSelectedFolderId !== null) {
    document.getElementById("btnQuoteFolderRename").onclick = async () => {
      const name = document.getElementById("quoteFolderRenameInput").value.trim();
      if (!name) return;
      await fetch(`/api/admin/crm/quotes/${quoteDetailId}/folders/${quoteSelectedFolderId}`, {
        method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name }),
      });
      loadQuoteDetail();
    };
    document.getElementById("btnQuoteFolderDelete").onclick = async () => {
      if (!confirm("Smazat složku včetně všech podsložek a souborů v ní? Tuto akci nelze vzít zpět.")) return;
      await fetch(`/api/admin/crm/quotes/${quoteDetailId}/folders/${quoteSelectedFolderId}`, { method: "DELETE" });
      quoteSelectedFolderId = null;
      loadQuoteDetail();
    };
  }
  document.getElementById("btnQuoteFileUpload").onclick = async () => {
    const fileInput = document.getElementById("quoteFileInput");
    if (!fileInput.files.length) return;
    const fd = new FormData();
    Array.from(fileInput.files).forEach(f => fd.append("files", f));
    if (quoteSelectedFolderId !== null) fd.append("folder_id", quoteSelectedFolderId);
    const r = await fetch(`/api/admin/crm/quotes/${quoteDetailId}/files`, { method: "POST", body: fd });
    if (!r.ok) { alert("Nahrání se nezdařilo."); return; }
    loadQuoteDetail();
  };
}

// Nadpis obsahoveho okna (#tabContentTitle) je vzdy odvozeny primo z
// textu aktivniho tlacitka v menu (jeden zdroj pravdy - pri budouci
// zmene nazvu sekce staci upravit tab-btn, nadpis se uz nemuze rozjet).
// Bere jen prvni text-node ditě tlacitka, aby se do nadpisu nedostalo
// cislo z pripadneho vnoreneho badge <span> (napr. supportNavBadge).
function setTabContentTitle(btn) {
  const firstNode = btn.childNodes[0];
  const label = firstNode && firstNode.nodeType === Node.TEXT_NODE ? firstNode.textContent.trim() : btn.textContent.trim();
  document.getElementById("tabContentTitle").textContent = label;
}

// Robert 2026-08-18 (screenshot dlouheho rozbaleneho menu): klik na
// nadpis skupiny uz SBALOVAT umel, ale kazda skupina se pri kazdem
// nacteni stranky vzdy znovu otevrela cela - fakticky "nesbalitelne"
// v praxi, protoze se stav nikam neukladal. Puvodni oprava (2026-08-18)
// si stav pamatovala v localStorage napric reloady - v praxi se ale
// kazde bezne prokliknuti admina (kazda skupina, do ktere se sahne,
// se drive nebo pozdeji stane "aktivni" a tim natrvalo ulozi jako
// rozbalena) postupne vratilo zpatky na "vsechno rozbalene", presne
// puvodni problem, jen o par kliknuti pozdeji (Robert 2026-09-16:
// "kdyz otevru admin panely nech jsou vsechny sbalene implicitne").
// Zjednoduseno: zadna trvala pamet mezi reloady. Skupina je pri
// KAZDEM nacteni stranky ve vychozim stavu SBALENA, KROME skupiny
// s prave aktivni zalozkou (a krome uzivatelem vytvorenych vlastnich
// skupin - viz vychoziSbaleno nize, ty zustavaji rozbalene, aby do
// prazdne skupiny slo hned neco pretahnout). Rucni rozbaleni/sbaleni
// kliknutim beham JEDNE session funguje beze zmeny - jen uz neprezije
// dalsi nacteni stranky.
function setNavGroupCollapsed(navGroup, collapsed) {
  navGroup.classList.toggle("collapsed", collapsed);
}
// bot16, 2026-09-12 - VSECHNY predky .nav-group daneho prvku, od nejblizsiho
// po nejvzdalenejsi. Do pridani 3. urovne (vnorene .nav-subgroup uvnitr
// "Prehledy") stacil jeden `.closest(".nav-group")` - aktivni zalozka mela
// nejvys JEDNOHO predka-skupinu. S vnorenim uz jich muze byt VIC (vnorena
// podskupina + jeji vnejsi skupina) a rozbaleni jen toho nejblizsiho by
// nechalo aktivni zalozku technicky "rozbalenou", ale schovanou za porad
// sbalenym vnejsim patrem - presne past, kterou tenhle helper resi.
function ancestorNavGroups(el) {
  const out = [];
  let g = el?.closest(".nav-group");
  while (g) {
    out.push(g);
    g = g.parentElement?.closest(".nav-group");
  }
  return out;
}
function applyNavGroupDefaults() {
  const activeGroups = ancestorNavGroups(document.querySelector(".tab-btn.active"));
  document.querySelectorAll(".nav-group").forEach(navGroup => {
    if (activeGroups.includes(navGroup)) { setNavGroupCollapsed(navGroup, false); return; }
    // bot16, 2026-09-12 (Robert nahlasil: "kdyz nejakou [kategorii]
    // vytvorim, nejde do ni nic presunout") - staticke skupiny defaultne
    // SBALENE, ale VLASTNI (uzivatelem vytvorena) skupina takhle
    // defaultne sbalena = jeji .nav-group-items dostane display:none
    // hned pri dalsim nacteni stranky -> neviditelna, nejde do ni nic
    // pretahnout. Vlastni prazdna skupina proto zustava rozbalena.
    const vychoziSbaleno = !navGroup.classList.contains("nav-group-custom");
    setNavGroupCollapsed(navGroup, vychoziSbaleno);
  });
}

// Robert 2026-08-18: "kategorie v levem menu udelejme presunovaci v
// ramci vsech levych panelu" - polozky menu (tab-btn) jde tahnout
// mysi, PREKLADAT PORADI v ramci vlastni skupiny i PRESOUVAT do
// JINE skupiny (napr. "Kategorie" z Katalogu do Skladu). Vysledne
// rozlozeni (ktera polozka je ve ktere skupine a v jakem poradi) se
// pamatuje v localStorage, prezije reload. Polozka, kterou tenhle
// ulozeny stav vubec nezmiuje (napr. nove pridana zalozka po
// Robertove poslednim prerovnani), zustava tam, kde ji polozil kod -
// nic se neztrati/neschova jen proto, ze uzivatel menu driv upravil.
function navMenuOrderStorageKey() { return "navMenuOrder"; }
function saveNavMenuOrder() {
  const order = {};
  document.querySelectorAll(".nav-group").forEach(g => {
    const groupName = g.dataset.group;
    if (!groupName) return;
    const items = g.querySelector(":scope > .nav-group-items");
    if (!items) return;
    order[groupName] = [...items.querySelectorAll(":scope > .tab-btn")].map(b => b.dataset.tab);
  });
  try { localStorage.setItem(navMenuOrderStorageKey(), JSON.stringify(order)); } catch (e) {}
}
function applyNavMenuOrder() {
  let order;
  try { order = JSON.parse(localStorage.getItem(navMenuOrderStorageKey()) || "null"); } catch (e) { order = null; }
  if (!order) return;
  Object.keys(order).forEach(groupName => {
    const group = document.querySelector('.nav-group[data-group="' + CSS.escape(groupName) + '"]');
    const items = group?.querySelector(":scope > .nav-group-items");
    if (!items) return;
    // appendChild na jiz existujicim uzlu ho PRESUNE (odebere ze
    // stareho rodice) - postupnym pruchodem ulozeneho poradi tak
    // vznikne spravne poradi i spravna prislusnost ke skupine
    // najednou, bez rucniho remove/insert.
    order[groupName].forEach(tabName => {
      const btn = document.querySelector('.tab-btn[data-tab="' + CSS.escape(tabName) + '"]');
      if (btn) items.appendChild(btn);
    });
  });
}
function navMenuDragAfterElement(container, y) {
  const els = [...container.querySelectorAll(":scope > .tab-btn:not(.dragging)")];
  return els.reduce((closest, child) => {
    const box = child.getBoundingClientRect();
    const offset = y - box.top - box.height / 2;
    if (offset < 0 && offset > closest.offset) return { offset, element: child };
    return closest;
  }, { offset: -Infinity }).element;
}
function makeNavMenuDraggable() {
  document.querySelectorAll(".tab-btn").forEach(btn => {
    btn.draggable = true;
    btn.ondragstart = () => { btn.classList.add("dragging"); };
    btn.ondragend = () => { btn.classList.remove("dragging"); saveNavMenuOrder(); };
  });
  // .nav-group-items.ondragover ma JEDINEHO vlastnika (tuhle funkci) -
  // resi jak tazeni POLOZKY (tab-btn, libovolna skupina je platny cil,
  // uz od zacatku), tak tazeni CELE PODSKUPINY mezi rodicovskymi
  // skupinami (bot16, 2026-09-12, viz makeNavSubgroupsDraggable nize -
  // Robert: "tento strom mi nenabizi plnou kontrolu tvorby
  // podkategorii... chci tam moznost zakladat kategorie/podkategorie").
  // Dve samostatne prirazeni container.ondragover = ... by se tise
  // prepsala (vyhral by to poslední) - proto oboji resi JEDEN handler.
  document.querySelectorAll(".nav-group-items").forEach(container => {
    container.ondragover = (e) => {
      const draggingTab = document.querySelector(".tab-btn.dragging");
      if (draggingTab) {
        e.preventDefault();
        // bot16, 2026-09-13 (Robert primo: "podkategorie lze vyndat...
        // ale napr pipeline emaily nelze vlozit do jine kategorie aby se
        // stala podkategorii") - KRITICKE: bez stopPropagation() tenhle
        // event probublava na KAZDY predek .nav-group-items (podskupina
        // je vnorena UVNITR nadrazene skupiny svym vlastnim .nav-group-
        // items). Pri tazeni polozky NAD vnorenou podskupinou tak
        // handler nejdriv spravne zaradil polozku dovnitr podskupiny,
        // ale hned nato probublal i na nadrazenou skupinu, jejiz handler
        // (bezici POZDEJI ve stejnem tiku, bublani jde od nejvnitrnejsiho
        // ven) polozku hned vytahl zpatky ven - navenek to vypadalo, ze
        // "do podskupiny nejde nic vlozit", ackoliv presne opacny smer
        // (vytazeni z podskupiny) fungoval, protoze tam zadny vnorenejsi
        // container nesoutezil. Overeno mimo prohlizec (bublaci
        // simulator), viz AGENTS_LOG.md.
        e.stopPropagation();
        const after = navMenuDragAfterElement(container, e.clientY);
        if (after == null) container.appendChild(draggingTab);
        else container.insertBefore(draggingTab, after);
        return;
      }
      // Podskupina smi jen do polozek TOP-LEVEL skupiny - zadne
      // vnorovani podskupiny do podskupiny (stejny 2-3urovnovy strop
      // jako jinde v tomhle menu).
      const draggingSub = document.querySelector(".nav-subgroup.subgroup-dragging");
      if (draggingSub && !container.closest(".nav-subgroup")) {
        e.preventDefault();
        e.stopPropagation();
        const after = navSubgroupDragAfterElement(container, e.clientY);
        if (after == null) container.appendChild(draggingSub);
        else container.insertBefore(draggingSub, after);
      }
    };
  });
  // Presunout polozku do SBALENE skupiny by jinak neslo (cilovy
  // seznam je display:none, nema kam "spadnout") - podrzeni tazene
  // polozky nad nadpisem sbalene skupiny ji rovnou rozbali, presne
  // jak na to jsou uzivatele zvykli z beznych souborovych spravcu.
  document.querySelectorAll(".nav-group-title").forEach(title => {
    title.ondragover = (e) => {
      // bot3, 2026-08-20: tenhle handler je jen pro tazeni JEDNE
      // POLOZKY nebo PODSKUPINY nad sbalenou skupinu (auto-rozbaleni,
      // at je kam pustit) - beze strazniho if by se spoustel i pri
      // tazeni CELE skupiny (viz makeNavGroupsDraggable nize), kde
      // nedava smysl.
      if (!document.querySelector(".tab-btn.dragging") && !document.querySelector(".nav-subgroup.subgroup-dragging")) return;
      e.preventDefault();
      // stopPropagation ze stejneho duvodu jako u .nav-group-items vyse -
      // titulek vnorene podskupiny je taky potomkem nadrazene skupiny
      // .nav-group-items, bez tohohle by probublani hned po rozbaleni
      // (nebo i u uz rozbalene podskupiny) souperilo s jejim handlerem.
      e.stopPropagation();
      const navGroup = title.closest(".nav-group");
      if (navGroup.classList.contains("collapsed")) setNavGroupCollapsed(navGroup, false);
    };
  });
}

// bot3, 2026-08-20 (Robert: "ano ale ja chci presouvat i ty panely") -
// stejny presouvaci mechanismus jako makeNavMenuDraggable() vyse, jen
// o uroven vys: cele .nav-group bloky (Prehled/Katalog/.../Nastaveni)
// jdou chytit za nadpis (.nav-group-title) a prerovnat mezi sebou.
// Poradi skupin se pamatuje samostatne od poradi polozek uvnitr
// (navGroupOrder vs. navMenuOrder), obe preziji reload nezavisle na
// sobe. Nova/neznama skupina (chybi v ulozenem poradi) zustava tam,
// kam ji polozil kod - stejna zasada jako u polozek.
function navGroupOrderStorageKey() { return "navGroupOrder"; }
function saveNavGroupOrder() {
  const order = [...document.querySelectorAll("#tabs > .nav-group")].map(g => g.dataset.group);
  try { localStorage.setItem(navGroupOrderStorageKey(), JSON.stringify(order)); } catch (e) {}
}
function applyNavGroupOrder() {
  let order;
  try { order = JSON.parse(localStorage.getItem(navGroupOrderStorageKey()) || "null"); } catch (e) { order = null; }
  if (!order) return;
  const tabsEl = document.getElementById("tabs");
  order.forEach(groupName => {
    const g = document.querySelector('.nav-group[data-group="' + CSS.escape(groupName) + '"]');
    if (g) tabsEl.appendChild(g);
  });
}
function navGroupDragAfterElement(container, y) {
  const els = [...container.querySelectorAll(":scope > .nav-group:not(.group-dragging)")];
  return els.reduce((closest, child) => {
    const box = child.getBoundingClientRect();
    const offset = y - box.top - box.height / 2;
    if (offset < 0 && offset > closest.offset) return { offset, element: child };
    return closest;
  }, { offset: -Infinity }).element;
}
function makeNavGroupsDraggable() {
  // bot16, 2026-09-12 - scope jen na TOP-LEVEL skupiny (#tabs > .nav-group
  // > .nav-group-title), od pridani 3. urovne (vnorene .nav-subgroup
  // uvnitr "Prehledy", viz HTML). Bez tehohle by unscoped dotaz nize
  // nasel i vnorene tituly - dragstart by jim (i CSS cursor:grab) tise
  // fungoval, ale ondragover NIZE je zadratovany jen na #tabs, takze by
  // preskupeni MEZI vnorenymi podskupinami nemelo kam spadnout - napul
  // rozbita funkce vypadajici jako hotova. Az bude Robert chtit tahat i
  // podskupiny mezi sebou, potrebuje to vlastni ondragover na urovni
  // rodicovske .nav-group-items (stejny vzor jako tahle funkce, jen o
  // patro niz), ne proste odstraneni tohohle scope.
  document.querySelectorAll("#tabs > .nav-group > .nav-group-title").forEach(title => {
    title.draggable = true;
    title.ondragstart = (e) => {
      e.stopPropagation();
      title.closest(".nav-group").classList.add("group-dragging");
    };
    title.ondragend = (e) => {
      e.stopPropagation();
      title.closest(".nav-group").classList.remove("group-dragging");
      saveNavGroupOrder();
    };
  });
  const tabsEl = document.getElementById("tabs");
  tabsEl.ondragover = (e) => {
    const dragging = document.querySelector(".nav-group.group-dragging");
    if (!dragging) return; // tazeni JEDNE polozky resi sve vlastni handlery vyse
    e.preventDefault();
    const after = navGroupDragAfterElement(tabsEl, e.clientY);
    if (after == null) tabsEl.appendChild(dragging);
    else tabsEl.insertBefore(dragging, after);
  };
}

// bot3, 2026-08-20 - viditelny "uchyt" (ikonka), at je hned na prvni
// pohled jasne, ze polozka/panel jde tahnout (drive jedina napoveda
// byl cursor:grab na hoveru, Robert si funkce nevsimnul). Pridava se
// jako POSLEDNI potomek (ne prvni!) - setTabContentTitle() vyse cte
// jen childNodes[0] jako popisek zalozky, pridani na konec ho tedy
// nijak neovlivni.
function addDragHandles() {
  document.querySelectorAll(".tab-btn, .nav-group-title").forEach(el => {
    if (el.querySelector(":scope > .drag-handle")) return;
    const handle = document.createElement("span");
    handle.className = "drag-handle";
    handle.textContent = "\u22ee\u22ee";
    handle.setAttribute("aria-hidden", "true");
    el.appendChild(handle);
  });
}

// ==================== VLASTNI SKUPINY/PODSKUPINY MENU ====================
// Robert (chat, 2026-09-12): "chci tam moznost vytvorit novou kategorii
// ve vsech panelech... nebo podkategorii" -> po screenshotu leveho menu
// a upresneni "tento strom mi nenabizi plnou kontrolu tvorby
// podkategorii... jen pres bota, takze tam chci mit moznost zakladat
// kategorie/podkategorie abych mohl sekce lépe organizovat" se ukazalo,
// ze reč byla o TOMHLE menu (Přehledy/Katalog/Sklad/...), ne o
// produktovych kategoriich (ty uz maji vlastni strom + drag&drop, viz
// #tab-categories) - viz AGENTS_LOG.md 2026-09-12.
//
// Presouvani JEDNOTLIVYCH polozek mezi skupinami uz fungovalo
// (makeNavMenuDraggable vyse pocitala s libovolnou .nav-group-items
// jako platnym cilem uz od zacatku). Chybelo: (a) vytvorit NOVOU
// (prazdnou) skupinu/podskupinu bez zasahu bota, (b) tahat cele
// PODSKUPINY mezi rodicovskymi skupinami (drive jen TODO komentar u
// makeNavGroupsDraggable). Stejna localStorage-per-prohlizec
// perzistence jako uz existujici poradi (navMenuOrder/navGroupOrder) -
// zamerne NE DB/server: Robert rekl "abych MOHL presouvat" (prvni
// osoba, jeho vlastni uprava), konzistentni se stavajicim mechanismem.

function customNavGroupsKey() { return "customNavGroups"; }
function loadCustomNavGroups() {
  try { return JSON.parse(localStorage.getItem(customNavGroupsKey()) || "[]"); } catch (e) { return []; }
}
function saveCustomNavGroups(list) {
  try { localStorage.setItem(customNavGroupsKey(), JSON.stringify(list)); } catch (e) {}
}
function slugifyNavGroup(nazev) {
  let s = nazev.toLowerCase()
    .normalize("NFD").replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
  if (!s) s = "skupina";
  let klic = "vlastni-" + s, i = 2;
  while (document.querySelector('.nav-group[data-group="' + CSS.escape(klic) + '"]')) {
    klic = "vlastni-" + s + "-" + i; i++;
  }
  return klic;
}

// Vytvori DOM uzly pro ulozene vlastni skupiny, ktere jeste v DOM
// nejsou (staticke skupiny z HTML samozrejme zustavaji, jak jsou).
// Musi bezet PRED applyNavGroupOrder/applyNavSubgroupLayout/
// applyNavMenuOrder - ty uz pocitaji s tim, ze cil existuje.
function renderCustomNavGroups() {
  const tabsEl = document.getElementById("tabs");
  loadCustomNavGroups().forEach(g => {
    if (document.querySelector('.nav-group[data-group="' + CSS.escape(g.key) + '"]')) return;
    const div = document.createElement("div");
    div.className = "nav-group nav-group-custom" + (g.parent ? " nav-subgroup" : "");
    div.dataset.group = g.key;
    div.innerHTML = '<div class="nav-group-title"><span class="ng-arrow">▾</span>'
      + escapeHtmlAdmin(g.label) + '</div><div class="nav-group-items"></div>';
    const parentItems = g.parent
      ? document.querySelector('.nav-group[data-group="' + CSS.escape(g.parent) + '"] > .nav-group-items')
      : null;
    (parentItems || tabsEl).insertBefore(div, parentItems ? null : document.getElementById("btnAddNavGroup"));
  });
}

// bot16, 2026-09-13 (Robert primo: "chci moznost smazat kategorii menu
// adminu nebo podkategorii") - rozsireni puvodniho "smazat jen prazdnou
// VLASTNI skupinu" na VSECHNY skupiny/podskupiny vc. STATICKYCH
// (vestavenych z admin.html). Staticke se ale nesmi zmizet NAVZDY jen
// tim, ze se odstrani z DOM - jejich HTML se vraci cerstve pri KAZDEM
// nacteni stranky (na rozdil od vlastnich, ktere se vubec nevykresli,
// pokud nejsou v customNavGroups), takze jde o samostatny "skryt seznam"
// (hiddenStaticNavGroups), ktery se musi znovu aplikovat pri kazdem
// initTabs() - viz applyHiddenStaticNavGroups() nize, volana z initTabs()
// PRED renderCustomNavGroups(). Obsah skryvane skupiny se (stejne jako u
// vlastnich) presune o uroven vys, ne zmizi spolu s ni - viz sdileny
// _presunoutObsahNavGroupNahoru().
function hiddenStaticNavGroupsKey() { return "hiddenStaticNavGroups"; }
function loadHiddenStaticNavGroups() {
  try { return JSON.parse(localStorage.getItem(hiddenStaticNavGroupsKey()) || "[]"); } catch (e) { return []; }
}
function saveHiddenStaticNavGroups(list) {
  try { localStorage.setItem(hiddenStaticNavGroupsKey(), JSON.stringify(list)); } catch (e) {}
}
// Musi bezet PRED renderCustomNavGroups/applyNavGroupOrder/
// applyNavSubgroupLayout/applyNavMenuOrder (stejne poradi-pozadavky jako
// u renderCustomNavGroups) - odstranuje STATICKE skupiny, ktere Robert
// skryl, pri KAZDEM nacteni stranky (staticky HTML se vraci nedotceny).
function applyHiddenStaticNavGroups() {
  loadHiddenStaticNavGroups().forEach(klic => {
    const navGroup = document.querySelector('.nav-group[data-group="' + CSS.escape(klic) + '"]:not(.nav-group-custom)');
    if (navGroup) _presunoutObsahNavGroupNahoru(navGroup);
  });
}
function _presunoutObsahNavGroupNahoru(navGroup) {
  const items = navGroup.querySelector(":scope > .nav-group-items");
  const destination = navGroup.parentElement; // rodicovska .nav-group-items, nebo #tabs u top-level skupiny
  if (items && destination) {
    [...items.children].forEach(child => destination.insertBefore(child, navGroup));
  }
  navGroup.remove();
}
function updateRestoreHiddenNavGroupsBtn() {
  const n = loadHiddenStaticNavGroups().length;
  const btn = document.getElementById("btnRestoreHiddenNavGroups");
  btn.hidden = n === 0;
  document.getElementById("hiddenNavGroupsCount").textContent = n;
}
document.getElementById("btnRestoreHiddenNavGroups").onclick = () => {
  const n = loadHiddenStaticNavGroups().length;
  if (!confirm(`Obnovit ${n} skrytých sekcí menu? Vrátí se na svoje původní místo (ne nutně tam, kam byl mezitím přesunut jejich obsah).`)) return;
  saveHiddenStaticNavGroups([]);
  location.reload();
};

// bot16, 2026-09-13 (Robert primo: "a take prejmenovat libovolnou
// polozku menu adminu") - ukladá se JEN zmenena hodnota (label), ne
// duplicitni kopie celeho stromu. Klic je "group:<data-group>" nebo
// "tab:<data-tab>" - VLASTNI skupiny maji svuj label uz v
// customNavGroups (jediny zdroj pravdy tam), tenhle mechanismus je pro
// STATICKE skupiny/podskupiny a pro JEDNOTLIVE polozky (tab-btn).
function navLabelOverridesKey() { return "navLabelOverrides"; }
function loadNavLabelOverrides() {
  try { return JSON.parse(localStorage.getItem(navLabelOverridesKey()) || "{}"); } catch (e) { return {}; }
}
function saveNavLabelOverrides(map) {
  try { localStorage.setItem(navLabelOverridesKey(), JSON.stringify(map)); } catch (e) {}
}
// Popisek skupiny je text node HNED v .nav-group-title, vedle .ng-arrow
// spanu a pred pripadnymi +/✕/✏️ ovladacimi ikonkami (ty jsou taky
// spany, ne text node) - hledej PRVNI neprazdny text node, ne
// childNodes[0] (to by u skupiny mohl byt arrow, ne label).
function navGroupTitleTextNode(title) {
  for (const node of title.childNodes) {
    if (node.nodeType === Node.TEXT_NODE && node.textContent.trim()) return node;
  }
  return null;
}
function applyNavLabelOverrides() {
  const overrides = loadNavLabelOverrides();
  Object.keys(overrides).forEach(fullKey => {
    const sep = fullKey.indexOf(":");
    if (sep < 0) return;
    const kind = fullKey.slice(0, sep), klic = fullKey.slice(sep + 1);
    const label = overrides[fullKey];
    if (kind === "group") {
      const navGroup = document.querySelector('.nav-group[data-group="' + CSS.escape(klic) + '"]');
      const title = navGroup && navGroup.querySelector(":scope > .nav-group-title");
      const textNode = title && navGroupTitleTextNode(title);
      if (textNode) textNode.textContent = label;
    } else if (kind === "tab") {
      const btn = document.querySelector('.tab-btn[data-tab="' + CSS.escape(klic) + '"]');
      const textNode = btn && btn.childNodes[0];
      if (textNode && textNode.nodeType === Node.TEXT_NODE) textNode.textContent = label;
    }
  });
}
function promptRenameNavLabel(kind, klic, currentLabel, onApply) {
  const novy = prompt("Nový název (prázdné = vrátit původní):", currentLabel);
  if (novy === null) return; // Zrušit - nic nemenit
  const trimmed = novy.trim();
  const overrides = loadNavLabelOverrides();
  const fullKey = kind + ":" + klic;
  if (trimmed) { overrides[fullKey] = trimmed; } else { delete overrides[fullKey]; }
  saveNavLabelOverrides(overrides);
  onApply(trimmed || null);
}

// bot16, 2026-09-13 (Robert primo: "na mazani tam udelej nejakou
// pojistku znovu zeptani se a okopirovanim nejake vety") - DRUHY,
// prisnejsi krok potvrzeni nad ramec obycejneho confirm() (ten zustava
// jako prvni rychla pojistka). Veta se sklada z AKTUALNIHO viditelneho
// nazvu (ne interniho klice) - pri skutecnem omylu si administrator
// vetu proste OPISE/ZKOPIRUJE z hlasky primo do pole, takze funguje i
// bez presne shody velkych/malych pismen (trim + lowercase porovnani -
// pojistka ma zabranit NEPOZORNOSTI, ne trestat preklep). `null`
// (Zrusit) i nespravny text = smazani se NEPROVEDE.
function potvrdSmazaniOpisemVety(label) {
  const veta = `smazat ${label}`;
  const zadano = prompt(
    `Poslední pojistka proti omylu - pro potvrzení OPIŠ (nebo zkopíruj) přesně tuhle větu do pole níže:\n\n${veta}`,
    ""
  );
  if (zadano === null) return false;
  return zadano.trim().toLowerCase() === veta.toLowerCase();
}

// Male "+"/"✕"/"✏️" ovladaci ikonky v nadpisu skupiny - "+" (pridat
// podskupinu) jen u TOP-LEVEL skupin (stejny scope jako presouvani
// celych skupin), "✕" (smazat) a "✏️" (prejmenovat) uz na VSECH
// skupinach/podskupinach vc. statickych (viz komentare u
// hiddenStaticNavGroups/navLabelOverrides vyse).
function addNavGroupControls() {
  document.querySelectorAll("#tabs > .nav-group > .nav-group-title").forEach(title => {
    if (title.querySelector(":scope > .nav-add-sub")) return;
    const btn = document.createElement("span");
    btn.className = "nav-add-sub";
    btn.title = "Přidat podskupinu sem";
    btn.textContent = "+";
    btn.onclick = (e) => {
      e.stopPropagation();
      const nazev = prompt("Název nové podskupiny:");
      if (!nazev || !nazev.trim()) return;
      const parentKlic = title.closest(".nav-group").dataset.group;
      const list = loadCustomNavGroups();
      list.push({ key: slugifyNavGroup(nazev.trim()), label: nazev.trim(), parent: parentKlic });
      saveCustomNavGroups(list);
      renderCustomNavGroups();
      makeNavMenuDraggable(); makeNavGroupsDraggable(); makeNavSubgroupsDraggable(); addNavGroupControls();
    };
    title.appendChild(btn);
  });
  document.querySelectorAll(".nav-group-title").forEach(title => {
    if (title.querySelector(":scope > .nav-rename-item")) return;
    const navGroup = title.closest(".nav-group");
    const isCustom = navGroup.classList.contains("nav-group-custom");
    const klic = navGroup.dataset.group;
    const renameBtn = document.createElement("span");
    renameBtn.className = "nav-rename-item";
    renameBtn.title = "Přejmenovat";
    renameBtn.textContent = "✏️";
    renameBtn.onclick = (e) => {
      e.stopPropagation();
      const textNode = navGroupTitleTextNode(title);
      const currentLabel = textNode ? textNode.textContent.trim() : "";
      if (isCustom) {
        // Vlastni skupina ma label v customNavGroups - JEDINY zdroj
        // pravdy (zadny zdvojeny zapis do navLabelOverrides).
        const novy = prompt("Nový název:", currentLabel);
        if (novy === null || !novy.trim()) return;
        const list = loadCustomNavGroups();
        const entry = list.find(x => x.key === klic);
        if (entry) { entry.label = novy.trim(); saveCustomNavGroups(list); if (textNode) textNode.textContent = novy.trim(); }
      } else {
        promptRenameNavLabel("group", klic, currentLabel, (novyLabel) => {
          if (textNode) textNode.textContent = novyLabel || currentLabel;
          if (!novyLabel) location.reload(); // navrat k puvodnimu - jednodussi nez pamatovat originalni text
        });
      }
    };
    title.appendChild(renameBtn);
    if (title.querySelector(":scope > .nav-del-group")) return;
    const delBtn = document.createElement("span");
    delBtn.className = "nav-del-group";
    delBtn.title = "Smazat tuhle skupinu";
    delBtn.textContent = "✕";
    delBtn.onclick = (e) => {
      e.stopPropagation();
      // bot16, 2026-09-13 (Robert primo: "chci mit moznost smazat
      // kategorii nebo podkategorii v adminu levy panel" + "chci moznost
      // smazat kategorii menu adminu nebo podkategorii") - drive slo
      // smazat jen PRAZDNOU vlastni skupinu (bez toho by mazani mohlo
      // vypadat, ze zmizely i skutecne zalozky/panely uvnitr). Misto
      // blokovani se obsah pri mazani presune o uroven vys (presne to,
      // co uz umi rucni tazeni jednotlivych polozek/podskupin ven -
      // tady se to jen udela naraz za vsechny najednou). TED uz to jde
      // i pro staticke skupiny - ty se jen SKRYJI (hiddenStaticNavGroups),
      // ne trvale smazou (jsou to skutecne funkcni sekce adminu, ne jen
      // organizacni slozky) - viz #btnRestoreHiddenNavGroups.
      const items = navGroup.querySelector(":scope > .nav-group-items");
      const childCount = items ? items.children.length : 0;
      const textNode = navGroupTitleTextNode(title);
      const currentLabel = textNode ? textNode.textContent.trim() : klic;
      const confirmMsg = (childCount
        ? `Smazat skupinu "${currentLabel}"? Obsahuje ${childCount} položek/podskupin - přesunou se o úroveň výš.`
        : `Smazat prázdnou skupinu "${currentLabel}"?`)
        + (isCustom ? "" : " (Skryje se jen v tomhle prohlížeči, jde vrátit tlačítkem dole v menu.)");
      if (!confirm(confirmMsg)) return;
      // bot16, 2026-09-13 (Robert primo: "na mazani tam udelej nejakou
      // pojistku znovu zeptani se a okopirovanim nejake vety") - druhy,
      // prisnejsi krok NAD RAMEC confirm() vyse - viz
      // potvrdSmazaniOpisemVety().
      if (!potvrdSmazaniOpisemVety(currentLabel)) { alert("Smazání zrušeno - věta nesouhlasila."); return; }
      _presunoutObsahNavGroupNahoru(navGroup);
      if (isCustom) {
        saveCustomNavGroups(loadCustomNavGroups().filter(x => x.key !== klic));
      } else {
        const hidden = loadHiddenStaticNavGroups();
        if (!hidden.includes(klic)) hidden.push(klic);
        saveHiddenStaticNavGroups(hidden);
        updateRestoreHiddenNavGroupsBtn();
      }
      saveNavMenuOrder();
      saveNavGroupOrder();
      saveNavSubgroupLayout();
    };
    title.appendChild(delBtn);
  });
}

// bot16, 2026-09-13 (Robert primo: "a take prejmenovat libovolnou
// polozku menu adminu") - "✏️" na KAZDEM tab-btn (jednotliva polozka
// menu, ne skupina) - stejny navLabelOverrides mechanismus jako u
// statickych skupin vyse ("tab:" prefix misto "group:").
function addNavItemRenameControls() {
  document.querySelectorAll(".tab-btn").forEach(btn => {
    if (btn.querySelector(":scope > .nav-rename-item")) return;
    const renameBtn = document.createElement("span");
    renameBtn.className = "nav-rename-item";
    renameBtn.title = "Přejmenovat";
    renameBtn.textContent = "✏️";
    renameBtn.onclick = (e) => {
      e.stopPropagation();
      const klic = btn.dataset.tab;
      const textNode = btn.childNodes[0];
      const currentLabel = textNode && textNode.nodeType === Node.TEXT_NODE ? textNode.textContent.trim() : btn.textContent.trim();
      promptRenameNavLabel("tab", klic, currentLabel, (novyLabel) => {
        if (novyLabel && textNode && textNode.nodeType === Node.TEXT_NODE) { textNode.textContent = novyLabel; }
        else location.reload(); // navrat k puvodnimu, nebo textNode chybel - jednodussi nez dohledavat
        if (btn.classList.contains("active")) setTabContentTitle(btn);
      });
    };
    btn.appendChild(renameBtn);
  });
}

document.getElementById("btnAddNavGroup").onclick = () => {
  const nazev = prompt("Název nové skupiny menu:");
  if (!nazev || !nazev.trim()) return;
  const list = loadCustomNavGroups();
  list.push({ key: slugifyNavGroup(nazev.trim()), label: nazev.trim(), parent: null });
  saveCustomNavGroups(list);
  renderCustomNavGroups();
  makeNavMenuDraggable(); makeNavGroupsDraggable(); makeNavSubgroupsDraggable(); addNavGroupControls();
};

// Tazeni CELYCH PODSKUPIN mezi ruznymi rodicovskymi skupinami - stejny
// princip jako makeNavGroupsDraggable (top-level skupiny mezi sebou),
// jen o uroven niz. Cilovy .ondragover uz zajistuje samotna
// makeNavMenuDraggable vyse (jediny vlastnik .nav-group-items.ondragover).
function navSubgroupLayoutKey() { return "navSubgroupLayout"; }
function saveNavSubgroupLayout() {
  const layout = {};
  document.querySelectorAll("#tabs > .nav-group").forEach(g => {
    const subs = [...g.querySelectorAll(":scope > .nav-group-items > .nav-subgroup")].map(s => s.dataset.group);
    if (subs.length) layout[g.dataset.group] = subs;
  });
  try { localStorage.setItem(navSubgroupLayoutKey(), JSON.stringify(layout)); } catch (e) {}
}
function applyNavSubgroupLayout() {
  let layout;
  try { layout = JSON.parse(localStorage.getItem(navSubgroupLayoutKey()) || "null"); } catch (e) { layout = null; }
  if (!layout) return;
  Object.keys(layout).forEach(parentKlic => {
    const parentItems = document.querySelector('.nav-group[data-group="' + CSS.escape(parentKlic) + '"] > .nav-group-items');
    if (!parentItems) return;
    layout[parentKlic].forEach(subKlic => {
      const sub = document.querySelector('.nav-subgroup[data-group="' + CSS.escape(subKlic) + '"]');
      if (sub) parentItems.appendChild(sub);
    });
  });
}
function navSubgroupDragAfterElement(container, y) {
  const els = [...container.querySelectorAll(":scope > .nav-subgroup:not(.subgroup-dragging)")];
  return els.reduce((closest, child) => {
    const box = child.getBoundingClientRect();
    const offset = y - box.top - box.height / 2;
    if (offset < 0 && offset > closest.offset) return { offset, element: child };
    return closest;
  }, { offset: -Infinity }).element;
}
function makeNavSubgroupsDraggable() {
  document.querySelectorAll(".nav-subgroup > .nav-group-title").forEach(title => {
    title.draggable = true;
    title.ondragstart = (e) => {
      e.stopPropagation();
      title.closest(".nav-subgroup").classList.add("subgroup-dragging");
    };
    title.ondragend = (e) => {
      e.stopPropagation();
      title.closest(".nav-subgroup").classList.remove("subgroup-dragging");
      saveNavSubgroupLayout();
    };
  });
}

function initTabs() {
  // Robert 2026-07-25: "seskup to v nejaky strom... levym menu 2-3 urovne" -
  // #tabs je ted strom skupin (.nav-group -> .nav-group-title + .tab-btn
  // polozky), misto puvodniho plocheho radku tlacitek. Skupiny lze sbalit/
  // rozbalit klikem na nadpis, aktivni polozka vzdy vynuti rozbaleni sve
  // skupiny (aby nezustala schovana po prepnuti).
  applyHiddenStaticNavGroups();
  renderCustomNavGroups();
  applyNavSubgroupLayout();
  applyNavGroupOrder();
  applyNavMenuOrder();
  applyNavGroupDefaults();
  makeNavMenuDraggable();
  makeNavGroupsDraggable();
  makeNavSubgroupsDraggable();
  addDragHandles();
  addNavGroupControls();
  addNavItemRenameControls();
  applyNavLabelOverrides();
  updateRestoreHiddenNavGroupsBtn();
  document.querySelectorAll(".nav-group-title").forEach(title => {
    title.onclick = () => {
      const navGroup = title.closest(".nav-group");
      setNavGroupCollapsed(navGroup, !navGroup.classList.contains("collapsed"));
    };
  });
  document.querySelectorAll(".tab-btn").forEach(btn => {
    btn.onclick = () => {
      document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
      document.querySelectorAll(".tab-panel").forEach(p => p.classList.remove("active"));
      btn.classList.add("active");
      document.getElementById("tab-" + btn.dataset.tab).classList.add("active");
      // ancestorNavGroups (ne jen nejblizsi .closest) - viz komentar tamtez,
      // stejna past s vnorenou 3. urovni.
      ancestorNavGroups(btn).forEach(g => g.classList.remove("collapsed"));
      setTabContentTitle(btn);
      // Robert 2026-07-26: "když obnovuju stránku F5, musím se načíst
      // tatáž stránka" - aktivní záložka se ukládá do URL hash, takže po
      // F5 (prohlížeč hash zachová) se stejná záložka obnoví níže v
      // restoreTabFromHash(). history.replaceState (ne pushState) - ať
      // přepínání záložek nezaplavuje tlačítko Zpět v prohlížeči.
      history.replaceState(null, "", "#" + btn.dataset.tab);
      if (btn.dataset.tab === "photoinbox") loadPhotoInboxes();
      if (btn.dataset.tab === "incomingdocuments") loadIncomingDocuments();
      if (btn.dataset.tab === "accountantemails") loadUcetniEmaily();   // bot16, 2026-10-06 Prodej > E-maily ucetni (rozeditovane radky se nepreplachuji)
      if (btn.dataset.tab === "banktransactions") loadBankTransactions();
      if (btn.dataset.tab === "drive") loadDriveTree();
      if (btn.dataset.tab === "quotes") loadQuotesList();
      if (btn.dataset.tab === "onlineoffers") loadOnlineOffersList();
      if (btn.dataset.tab === "fleet") { loadFleetVehicles(); loadFleetTrips(); loadFleetFuelEmail(); }
      if (btn.dataset.tab === "centralnitexty") loadContentObor();
      if (btn.dataset.tab === "homepagecarousel") loadHomepageCarousel();
      if (btn.dataset.tab === "homepageblocks") { loadHomepageBlocks(); loadHomepageIntro(); }
      if (btn.dataset.tab === "sidebarblocks") loadSidebarBlocks();
      if (btn.dataset.tab === "announcementitems") loadAnnouncementItems();
      if (btn.dataset.tab === "boti") { loadBoti(); botiConnectEvents(); } else { botiDisconnectEvents(); }
      if (btn.dataset.tab === "pravidla") loadPravidla();
      if (btn.dataset.tab === "zalohy") loadZalohy();
      if (btn.dataset.tab === "john") johnStart(); else if (typeof johnStop === "function") johnStop();   // bot16, 2026-10-06 Prehledy > John: obnova kazdych 30 s jen dokud je zalozka otevrena
      if (btn.dataset.tab === "regalyosy") loadRegalyOsy();
      if (btn.dataset.tab === "geopravidla") loadGeoPravidla();  // bot8 2026-09-21, Prehledy > Geometrie
      if (btn.dataset.tab === "returns") loadReturns();
      // bot5, 2026-09-17 (Robert primo pres bot3: "pri kazdem otevreni
      // sekce Objednavky se ma spustit kontrola uhrad proti vypisum") -
      // cist DB-local parovani (zadny FIO dotaz, viz endpoint docstring
      // v api/bank_statements.py), bezpecne volat pri kazdem prepnuti na
      // tenhle tab. Vysledek se tise promitne do dalsiho loadOrders()
      // (bank_paid pole), zadny vlastni UI element pro tenhle krok.
      if (btn.dataset.tab === "orders") {
        fetch("/api/admin/bank-transactions/rematch", { method: "POST" })
          .then(() => { if (typeof loadOrders === "function") loadOrders(); })
          .catch(() => {});
      }
      if (btn.dataset.tab === "storefronts") loadStorefronts();
      if (btn.dataset.tab === "miniweb") loadMiniwebShops();
      if (btn.dataset.tab === "productmarkups") loadProductMarkups();
      if (btn.dataset.tab === "rendering") loadRenderingSettings();
      if (btn.dataset.tab === "pipeline") loadPipelineOverview();
      if (btn.dataset.tab === "pipelinecrm") loadCrmPipeline();
      if (btn.dataset.tab === "pipelineorders") loadOrdersPipeline();
      if (btn.dataset.tab === "pipelinesklad") loadSkladPipeline();
      if (btn.dataset.tab === "pipelinerender") loadRenderPipeline();
      if (btn.dataset.tab === "systempipeline") loadSystemPipeline();
      if (btn.dataset.tab === "geotracking") loadGeoTracking();
      // bot11, 2026-08-22 (zjištěno živě, stejný gotcha jako Toscanaccio):
      // initColumnResizers() se jinak spouští jen přes MutationObserver na
      // změnu OBSAHU #tabContent - prosté PŘEPNUTÍ záložky (jen classList
      // toggle, žádná mutace) by ho nikdy nevyvolalo, takže tabulka, která
      // byla při prvním (skrytém) vykreslení 0×0px, by tažítka nikdy
      // nedostala, i když po zviditelnění evidentně přeteká.
      initColumnResizers();
      closeAdminSidebarMobile();
    };
  });
  setTabContentTitle(document.querySelector(".tab-btn.active"));
  initTabSearch();
}

// ==================== HLEDANI ZALOZEK V LEVEM MENU ====================
// bot16, 2026-09-23 (Robert pres bot3 koordinace - "hledat/filtrovat
// sekce podle nazvu, misto proklikavani skupinami" - nice-to-have, ne
// blokujici). 49 .tab-btn napric stackovanymi skupinami (Pipeline/
// E-maily/CRM/Objednavky/Sklad/Render, Geo prehled/Sdileny disk/
// Nabidky, Ceny profilu/Spoje/Kategorie/Mini-eshopy/Galerie/Homepage,
// Import/Rendering, Skladove pohyby/Nakupni objednavky/Rezne plany,
// Doklady/Reklamace/Prijate doklady/Bankovni vypisy/Zakaznici/CRM/
// Kniha jizd, Doprava/Vzhled/Uzivatele/Role...) - jedno pole nad
// stromem #tabs filtruje/zvyrazni podle ceskeho popisku VSECHNY
// skupiny najednou, prosty substring (bez diakritiky-insenzitivity,
// bez fuzzy - Robert/bot3 zadani rovnou rikalo, ze to staci).
let tabSearchActive = false;
let tabSearchCollapsedBackup = null; // Map<navGroupEl, byl-sbaleny-pred-hledanim>

function tabSearchLabel(btn) {
  // Stejny zpusob jako setTabContentTitle() vyse - vezme jen PRVNI text
  // uzel (napr. u "Emaily příchozí <span id=supportNavBadge>" tim padem
  // nezapocita cislo v badge do hledaneho textu ani ho neodstrani z DOM).
  const firstNode = btn.childNodes[0];
  return (firstNode && firstNode.nodeType === Node.TEXT_NODE ? firstNode.textContent : btn.textContent).trim();
}

// Prepocita viditelnost .nav-group ze SKUTECNE vypoctene viditelnosti
// potomku (getComputedStyle), takze zohledni soucasne permission-hide
// (inline styl z applyTabPermissions) i search-hide (trida nize) -
// nezasahuje do puvodni logiky primo v applyTabPermissions, jen ji
// znovu spousti po zmene hledaneho vyrazu.
function refreshNavGroupVisibility() {
  document.querySelectorAll("#tabs .nav-group").forEach(group => {
    const btns = [...group.querySelectorAll(".tab-btn")];
    if (!btns.length) return;
    const anyVisible = btns.some(b => getComputedStyle(b).display !== "none");
    group.style.display = anyVisible ? "" : "none";
  });
}

function clearTabSearch() {
  document.querySelectorAll("#tabs .tab-btn").forEach(b => {
    b.classList.remove("tab-search-hide", "tab-search-match");
  });
  if (tabSearchCollapsedBackup) {
    // vratit sbaleni presne tam, kde admin menu nechal PRED hledanim -
    // ne vzdy plosne "vse rozbalit".
    tabSearchCollapsedBackup.forEach((collapsed, group) => setNavGroupCollapsed(group, collapsed));
    tabSearchCollapsedBackup = null;
  }
  tabSearchActive = false;
  refreshNavGroupVisibility();
  const countEl = document.getElementById("tabSearchCount");
  if (countEl) countEl.textContent = "";
}

function applyTabSearch(query) {
  const q = (query || "").trim().toLowerCase();
  if (!q) { clearTabSearch(); return; }
  if (!tabSearchActive) {
    tabSearchCollapsedBackup = new Map();
    document.querySelectorAll("#tabs .nav-group").forEach(g => tabSearchCollapsedBackup.set(g, g.classList.contains("collapsed")));
    tabSearchActive = true;
  }
  let matchCount = 0;
  document.querySelectorAll("#tabs .tab-btn").forEach(btn => {
    const permVisible = btn.style.display !== "none"; // opravneni (applyTabPermissions) ma vzdy prednost
    const match = permVisible && tabSearchLabel(btn).toLowerCase().includes(q);
    btn.classList.toggle("tab-search-match", match);
    btn.classList.toggle("tab-search-hide", !match);
    if (match) matchCount++;
  });
  // rozbalit VSECHNY skupiny/podskupiny, at je kazda shoda dohledatelna
  // bez ohledu na to, kde ve stromu (i vnorenem) lezi.
  document.querySelectorAll("#tabs .nav-group").forEach(g => setNavGroupCollapsed(g, false));
  refreshNavGroupVisibility();
  const countEl = document.getElementById("tabSearchCount");
  if (countEl) countEl.textContent = matchCount ? (matchCount + (matchCount === 1 ? " shoda" : matchCount < 5 ? " shody" : " shod")) : "Žádná shoda";
}

function initTabSearch() {
  const input = document.getElementById("tabSearchInput");
  const tabsEl = document.getElementById("tabs");
  if (!input || !tabsEl || input.dataset.tabSearchBound) return;
  input.dataset.tabSearchBound = "1";
  input.addEventListener("input", () => applyTabSearch(input.value));
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      const first = tabsEl.querySelector(".tab-btn.tab-search-match");
      if (first) first.click();
    } else if (e.key === "Escape") {
      input.value = "";
      clearTabSearch();
      input.blur();
    }
  });
  // Klik na vysledek (i synteticky, vyvolany Enterem vyse) uz prepnul
  // zalozku pres existujici btn.onclick (viz initTabs() - bublani ho
  // spusti jako prvni, driv nez tenhle delegovany listener na predkovi
  // #tabs) - tady uz jen zavreme hledani, at se menu vrati do normalu
  // se zvolenou zalozkou aktivni.
  tabsEl.addEventListener("click", (e) => {
    if (!tabSearchActive) return;
    if (e.target.closest(".tab-btn")) {
      input.value = "";
      clearTabSearch();
    }
  });
}

// ==================== PIPELINE (živý SVG diagram) ====================
// bot9, 2026-08-22 (Robert pres bot3, viz komentar u #tab-pipeline v
// HTML) - cisty READ-ONLY diagram, zadny vlastni stav krome
// prekreslovani. Data z GET /api/admin/pipeline/overview.

function pipelineFmtDt(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("cs-CZ", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
}

// Jeden box diagramu - x/y/w/h v SVG jednotkach, barevny tón podle
// "role" boxu (neutral/warn/success/error), volitelny klik = prechod
// na existujici obrazovku (Robert: "jen READ-ONLY přehled + prokliky").
function pipelineBox(x, y, w, h, title, sub, tone, onclick) {
  const toneVar = { neutral: "var(--border-soft)", warn: "var(--warn)", success: "var(--success)", error: "var(--error)", accent: "var(--accent)" }[tone] || "var(--border-soft)";
  const cursor = onclick ? "cursor:pointer;" : "";
  const clickAttr = onclick ? ` class="pl-clickbox" data-nav="${onclick}"` : "";
  return `
    <g${clickAttr} style="${cursor}">
      <rect x="${x}" y="${y}" width="${w}" height="${h}" rx="9" fill="var(--panel-bg-alt)" stroke="${toneVar}" stroke-width="1.6"></rect>
      <text x="${x + w / 2}" y="${y + (sub ? 22 : h / 2 + 5)}" text-anchor="middle" fill="var(--text2)" font-size="12.5" font-weight="600">${title}</text>
      ${sub ? `<text x="${x + w / 2}" y="${y + h - 10}" text-anchor="middle" fill="${toneVar}" font-size="12" font-weight="700">${sub}</text>` : ""}
    </g>`;
}

// Elbow šipka (pravoúhlá) mezi dvěma body přes zadaný "via" bod (osa X
// nebo Y podle toho, co je zadané) - standardní styl vývojových schémat.
function pipelineArrow(x1, y1, x2, y2, viaX, label) {
  const d = viaX != null
    ? `M${x1},${y1} H${viaX} V${y2} H${x2}`
    : `M${x1},${y1} V${y2} H${x2}`;
  // Popisek na stredu SVISLEHO useku (x=viaX) - u teto diagramove
  // geometrie je to vzdy prazdny prostor mezi sloupci boxu (overeno
  // rucne pro kazdou sipku), na rozdil od umisteni tesne pred cilovy
  // box, kde se kratky vodorovny usek prekryval s ramecekem cilove
  // schranky u sipek smerujicich zprava doleva (bot9, 2. vizualni test).
  const lx = viaX != null ? viaX : (x1 + x2) / 2;
  const ly = (y1 + y2) / 2;
  return `
    <path d="${d}" fill="none" stroke="var(--text-faint)" stroke-width="1.4" marker-end="url(#plArrowHead)"></path>
    ${label ? `<text x="${lx}" y="${ly - 5}" text-anchor="middle" fill="var(--text-faint)" font-size="10.5">${label}</text>` : ""}`;
}

// Kanonicky seznam uzlu Pipeline diagramu - 1:1 v poradi s boxy nize
// (bot16, 2026-09-12, viz komentar u #tab-pipeline v admin.html).
// Puvodne zilo jako sloupec v tabulce Boti, Robert po vyzkouseni
// presunul editaci sem: "stacilo by uplne kdyby to bylo v tom
// pipelinu, tady to byt nemusi". Data (kdo ma co na starosti) zustavaji
// v bots.pipeline_uzly (CSV), jen editace je centralizovana tady -
// viz PUT /api/admin/bots/pipeline-uzel (api/bots.py), ktery navic
// vynucuje nejvyse jednoho vlastnika na uzel.
const PIPELINE_UZLY = [
  ["sync_emailu", "📥 Sync e-mailů"],
  ["crm_poptavky", "💼 CRM Poptávky"],
  ["doklady_2_schvaleni", "🧾 Doklady: 2. schválení"],
  ["objednavky", "📦 Objednávky"],
  ["netrideno", "✉️ Netříděno"],
  ["trideni_review", "🔀 Třídění (review)"],
  ["sdileny_disk", "💾 Sdílený disk"],
  ["platby_banka", "💳 Platby (banka)"],
  ["smazano_spam", "🗑️ Smazáno (spam)"],
  ["podpora_vyrizeno", "✅ Podpora: vyřízeno"],
  ["systemove_udalosti", "⚙️ Systémové události"],
  ["emaily_odchozi", "✉️ Emaily odchozí"],
  ["odeslano_smtp", "✅ Odesláno (SMTP)"],
  ["zamitnuto", "✕ Zamítnuto"],
];

function renderPipelineDiagram(d, uzelBot) {
  const wrap = document.getElementById("pipelineDiagramWrap");
  const cat = d.triage.pending_by_category;
  const runLabel = d.triage.active_run
    ? `běh #${d.triage.active_run.id} (${d.triage.active_run.status === "ready_for_review" ? "čeká na review" : "otevřen"})`
    : "žádný aktivní běh";
  // Kompaktni doplnek do sub-textu boxu, at zabira co nejmin extra
  // mista (Robert: "hlavne aby to nezabralo velkou plochu") - zadny
  // novy SVG uzel, jen kus textu pripojeny k uz existujicimu radku.
  const vlastnik = (klic) => (uzelBot && uzelBot[klic]) ? ` · 👤 ${uzelBot[klic]}` : "";

  const boxes = [
    pipelineBox(20, 110, 170, 230, "📥 Sync e-mailů", `naposledy ${pipelineFmtDt(d.sync.last_sync_at)}${vlastnik("sync_emailu")}`, "neutral"),
    pipelineBox(430, 20, 200, 60, "💼 CRM Poptávky", `nepřečteno: ${d.incoming.leads_unread}${vlastnik("crm_poptavky")}`, "accent", "crm"),
    pipelineBox(430, 100, 200, 60, "🧾 Doklady: 2. schválení", `čeká: ${d.documents.pending_second_approval ?? "—"}${vlastnik("doklady_2_schvaleni")}`, "warn", "incomingdocuments"),
    pipelineBox(430, 180, 200, 60, "📦 Objednávky", `propojeno dnes: ${d.incoming.objednavky_linked_today}${vlastnik("objednavky")}`, "accent", "orders"),
    pipelineBox(430, 260, 200, 60, "✉️ Netříděno", `čeká: ${d.incoming.untriaged}${vlastnik("netrideno")}`, "warn", "support"),
    pipelineBox(760, 250, 210, 80, "🔀 Třídění (review)", `${runLabel} · ${d.triage.pending_total} čeká${vlastnik("trideni_review")}`, "warn", "support"),
    pipelineBox(760, 20, 210, 50, "💾 Sdílený disk", `po 2. schválení${vlastnik("sdileny_disk")}`, "success"),
    // bot18, 2026-09-04 (TASKS.md "Pipeline diagram: doplnit dlaždici
    // Platby") - prázdný prostor mezi "Sdílený disk" (končí y=70) a
    // "Třídění" (začíná y=250), stejný sloupec x=760. Tón/text stejný
    // vzor jako "Doklady: 2. schválení" výš - "warn" i bez oprávnění
    // (hodnota pak "—"), at je to konzistentni napric diagramem.
    pipelineBox(760, 140, 200, 60, "💳 Platby (banka)",
      `30d: ${d.payments.matched_recent ?? "—"} spárováno · ${d.payments.unmatched_pending ?? "—"} čeká${vlastnik("platby_banka")}`,
      "warn", "banktransactions"),
    pipelineBox(1030, 190, 190, 50, "🗑️ Smazáno (spam)", `${cat.spam} v běhu${vlastnik("smazano_spam")}`, "error"),
    pipelineBox(1030, 340, 190, 50, "✅ Podpora: vyřízeno", `${cat.podpora + cat.jine} v běhu${vlastnik("podpora_vyrizeno")}`, "success", "support"),
    pipelineBox(20, 440, 190, 55, "⚙️ Systémové události", `potvrzení objednávky, změna stavu…${vlastnik("systemove_udalosti")}`, "neutral"),
    pipelineBox(250, 440, 220, 55, "✉️ Emaily odchozí: čeká", `čeká: ${d.outgoing.pending_approval ?? "—"}${vlastnik("emaily_odchozi")}`, "warn", "emails"),
    pipelineBox(530, 415, 190, 40, "✅ Odesláno (SMTP)", vlastnik("odeslano_smtp").replace(/^ · /, ""), "success"),
    pipelineBox(530, 465, 190, 40, "✕ Zamítnuto", vlastnik("zamitnuto").replace(/^ · /, ""), "error"),
  ].join("");

  const arrows = [
    pipelineArrow(190, 150, 430, 50, 260, "poptávka"),
    pipelineArrow(190, 195, 430, 130, 280, "doklad"),
    pipelineArrow(190, 240, 430, 210, 300, "objednávka (auto)"),
    pipelineArrow(190, 285, 430, 290, 320, "ostatní"),
    pipelineArrow(630, 290, 760, 290, 695, "třídění ručně/auto"),
    pipelineArrow(760, 260, 630, 50, 700, "crm"),
    pipelineArrow(760, 290, 630, 130, 680, "doklad"),
    pipelineArrow(760, 320, 630, 210, 660, "objednávka"),
    pipelineArrow(630, 195, 760, 170, 695, "platba spárována"),
    pipelineArrow(970, 270, 1030, 215, 1000, "spam"),
    pipelineArrow(970, 310, 1030, 365, 1000, "podpora/jiné"),
    pipelineArrow(630, 130, 760, 45, 700, "schváleno"),
    pipelineArrow(210, 467, 250, 467, 230, ""),
    pipelineArrow(470, 455, 530, 435, 490, "schváleno"),
    pipelineArrow(470, 480, 530, 485, 490, "zamítnuto"),
  ].join("");

  wrap.innerHTML = `
    <svg viewBox="0 0 1240 540" width="1240" height="540" style="min-width:1100px;">
      <defs>
        <marker id="plArrowHead" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
          <path d="M0,0 L6,3 L0,6 Z" fill="var(--text-faint)"></path>
        </marker>
      </defs>
      ${arrows}
      ${boxes}
    </svg>`;

  wrap.querySelectorAll(".pl-clickbox").forEach(g => {
    g.addEventListener("click", () => {
      const btn = document.querySelector('.tab-btn[data-tab="' + g.dataset.nav + '"]');
      if (btn) btn.click();
    });
  });
}

// bot16, 2026-09-12: naplni oba selecty ovladaciho radku (uzel + bot),
// zachova aktualne zvolenou hodnotu (kdyz porad existuje) - stejny
// vzor jako "keepFilter"/"keepAdd" u populateShopCategorySelects.
function fillPipelineAssignSelects(bots) {
  const uzelSel = document.getElementById("plAssignUzel");
  if (!uzelSel.options.length) {
    uzelSel.innerHTML = PIPELINE_UZLY.map(([k, label]) => `<option value="${k}">${escapeHtmlAdmin(label)}</option>`).join("");
  }
  const botSel = document.getElementById("plAssignBot");
  const keepBot = botSel.value;
  botSel.innerHTML = '<option value="">— nikdo —</option>'
    + bots.map(b => `<option value="${escapeHtmlAdmin(b.bot_id)}">${escapeHtmlAdmin(b.bot_id)}</option>`).join("");
  if ([...botSel.options].some(o => o.value === keepBot)) botSel.value = keepBot;
}

async function loadPipelineOverview() {
  const errEl = document.getElementById("pipelineErr");
  errEl.textContent = "";
  try {
    const r = await fetch("/api/admin/pipeline/overview");
    if (!r.ok) { errEl.textContent = "Načtení pipeline selhalo."; return; }
    const data = await r.json();
    // Kdo ma co na starosti - viz komentar u PIPELINE_UZLY vyse. Vypadek
    // tohohle doplnkoveho fetch nesmi shodit cely diagram (stejny vzor
    // jako u HDRI vyberu v loadDriveTree).
    let uzelBot = {}, boti = [];
    try {
      const rb = await fetch("/api/admin/bots");
      if (rb.ok) {
        boti = (await rb.json()).items || [];
        boti.forEach(b => {
          (b.pipeline_uzly || "").split(",").map(s => s.trim()).filter(Boolean)
            .forEach(k => { uzelBot[k] = b.bot_id; });
        });
      }
    } catch (e) { /* viz komentar vyse */ }
    renderPipelineDiagram(data, uzelBot);
    fillPipelineAssignSelects(boti);
    document.getElementById("pipelineUpdatedAt").textContent = "aktualizováno " + new Date().toLocaleTimeString("cs-CZ");
  } catch (e) {
    errEl.textContent = "Načtení pipeline selhalo: " + e.message;
  }
}

document.getElementById("plAssignBtn").onclick = async () => {
  const uzel = document.getElementById("plAssignUzel").value;
  const bot_id = document.getElementById("plAssignBot").value;
  const msgEl = document.getElementById("plAssignMsg");
  msgEl.textContent = "";
  msgEl.style.color = "var(--text-faint)";
  const r = await fetch("/api/admin/bots/pipeline-uzel", {
    method: "PUT", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ uzel, bot_id }),
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) { msgEl.style.color = "var(--error)"; msgEl.textContent = data.error || "Chyba."; return; }
  msgEl.textContent = "Uloženo.";
  loadPipelineOverview();
};

// ==================== PIPELINE - NABIDKY/CRM (mimo e-mail) ====================
// bot16, 2026-09-12 (Robert: "tak chci pipeline na vsechno co se deje v
// projektu", pak "vic samostatnych diagramu", pak "musi to byt zivy
// pipeline odraz skutecneho stavu"). Zivá data: GET /api/admin/crm/leads
// uz vraci status_counts (api/crm.py) - zadny novy backend potreba,
// jen nove vykresleni ve stejnem box+sipka stylu jako e-mailova pipeline.
function renderCrmPipelineDiagram(counts) {
  const wrap = document.getElementById("plCrmDiagramWrap");
  const c = (k) => counts[k] ?? 0;
  const boxes = [
    pipelineBox(20, 60, 190, 60, "🆕 Nová", `${c("nova")}`, "accent", "crm"),
    pipelineBox(250, 60, 190, 60, "💬 V jednání", `${c("v_jednani")}`, "warn", "crm"),
    pipelineBox(480, 60, 190, 60, "📨 Nabídnuto", `${c("nabidnuto")}`, "warn", "crm"),
    pipelineBox(710, 10, 190, 55, "✅ Vyhráno", `${c("vyhrano")}`, "success", "crm"),
    pipelineBox(710, 105, 190, 55, "✕ Prohráno", `${c("prohrano")}`, "error", "crm"),
  ].join("");
  const arrows = [
    pipelineArrow(210, 90, 250, 90, 230, ""),
    pipelineArrow(440, 90, 480, 90, 460, ""),
    pipelineArrow(670, 90, 710, 37, 690, "vyhráno"),
    pipelineArrow(670, 90, 710, 132, 690, "prohráno"),
  ].join("");
  wrap.innerHTML = `
    <svg viewBox="0 0 920 180" width="920" height="180" style="min-width:820px;">
      <defs>
        <marker id="plArrowHead" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
          <path d="M0,0 L6,3 L0,6 Z" fill="var(--text-faint)"></path>
        </marker>
      </defs>
      ${arrows}
      ${boxes}
    </svg>`;
  wrap.querySelectorAll(".pl-clickbox").forEach(g => {
    g.addEventListener("click", () => {
      const btn = document.querySelector('.tab-btn[data-tab="' + g.dataset.nav + '"]');
      if (btn) btn.click();
    });
  });
}
async function loadCrmPipeline() {
  const errEl = document.getElementById("plCrmErr");
  errEl.textContent = "";
  try {
    const r = await fetch("/api/admin/crm/leads?page_size=1");
    if (!r.ok) { errEl.textContent = "Načtení selhalo."; return; }
    const data = await r.json();
    renderCrmPipelineDiagram(data.status_counts || {});
    document.getElementById("plCrmUpdatedAt").textContent = "aktualizováno " + new Date().toLocaleTimeString("cs-CZ");
  } catch (e) {
    errEl.textContent = "Načtení selhalo: " + e.message;
  }
}
document.getElementById("plCrmRefreshBtn").onclick = loadCrmPipeline;

// ==================== PIPELINE - OBJEDNAVKY ====================
// Zivá data: GET /api/admin/orders uz vraci "counts" pro kazdy
// ORDER_STATUSES + "all"/"urgent" (api/orders.py) - zadny novy backend.
// STATUS_LABELS_CZ (stejny soubor) je zdroj popisku, at se text nikde
// nerozejde s tim, co uz Objednavky tab pouziva.
function renderOrdersPipelineDiagram(counts, labels) {
  const wrap = document.getElementById("plOrdersDiagramWrap");
  const c = (k) => counts[k] ?? 0;
  const poradi = ["nova", "potvrzena", "ceka_na_zbozi", "pripravit", "expedovana", "fakturovana"];
  const ikony = { nova: "🆕", potvrzena: "✅", ceka_na_zbozi: "⏳", pripravit: "📦", expedovana: "🚚", fakturovana: "🧾" };
  const w = 175, gap = 20, x0 = 20, y0 = 70;
  const boxes = poradi.map((s, i) =>
    pipelineBox(x0 + i * (w + gap), y0, w, 60, `${ikony[s]} ${labels[s] || s}`, `${c(s)}`, i < 2 ? "accent" : "warn", "orders")
  );
  boxes.push(pipelineBox(x0 + poradi.length * (w + gap) + 10, y0, w, 60, "✕ Zrušená", `${c("zrusena")}`, "error", "orders"));
  const arrows = [];
  for (let i = 0; i < poradi.length - 1; i++) {
    const x1 = x0 + i * (w + gap) + w, x2 = x0 + (i + 1) * (w + gap);
    arrows.push(pipelineArrow(x1, y0 + 30, x2, y0 + 30, (x1 + x2) / 2, ""));
  }
  const totalW = x0 + (poradi.length + 1) * (w + gap) + 20;
  wrap.innerHTML = `
    <svg viewBox="0 0 ${totalW} 180" width="${totalW}" height="180" style="min-width:${Math.min(totalW, 1100)}px;">
      <defs>
        <marker id="plArrowHead" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
          <path d="M0,0 L6,3 L0,6 Z" fill="var(--text-faint)"></path>
        </marker>
      </defs>
      ${arrows.join("")}
      ${boxes.join("")}
    </svg>`;
  wrap.querySelectorAll(".pl-clickbox").forEach(g => {
    g.addEventListener("click", () => {
      const btn = document.querySelector('.tab-btn[data-tab="' + g.dataset.nav + '"]');
      if (btn) btn.click();
    });
  });
}
async function loadOrdersPipeline() {
  const errEl = document.getElementById("plOrdersErr");
  errEl.textContent = "";
  try {
    const r = await fetch("/api/admin/orders?page_size=1");
    if (!r.ok) { errEl.textContent = "Načtení selhalo."; return; }
    const data = await r.json();
    // ORDER_STATUS_LABELS - existujici globalni konstanta z
    // objednavky-doklady.js (mirror api/orders.py STATUS_LABELS_CZ),
    // zadny duplicitni zdroj popisku.
    renderOrdersPipelineDiagram(data.counts || {}, ORDER_STATUS_LABELS);
    document.getElementById("plOrdersUpdatedAt").textContent = "aktualizováno " + new Date().toLocaleTimeString("cs-CZ");
  } catch (e) {
    errEl.textContent = "Načtení selhalo: " + e.message;
  }
}
document.getElementById("plOrdersRefreshBtn").onclick = loadOrdersPipeline;

// ==================== PIPELINE - SKLAD A NAKUP ====================
// Zivá data: GET /api/shop/reorder-items (pocita se client-side podle
// status - jen "needed"/"selected" existuji, api/shop_api.py) +
// GET /api/admin/purchase-orders (uz vraci "counts" pro PO_STATUSES,
// api/purchase_orders.py) - zadny novy backend.
function renderSkladPipelineDiagram(reorderCounts, poCounts) {
  const wrap = document.getElementById("plSkladDiagramWrap");
  const boxes = [
    pipelineBox(20, 70, 210, 60, "📉 Návrh doobjednání", `čeká: ${reorderCounts.needed || 0}`, "warn", "reorder"),
    pipelineBox(280, 70, 210, 60, "☑️ Vybráno k objednání", `${reorderCounts.selected || 0}`, "accent", "reorder"),
    pipelineBox(540, 10, 220, 55, "📝 Objednávka u dodavatele", `návrh+odesláno: ${(poCounts.navrh || 0) + (poCounts.odeslano || 0)}`, "warn", "purchaseorders"),
    pipelineBox(540, 105, 220, 55, "📦 Částečně/plně přijato", `${(poCounts.castecne_prijato || 0) + (poCounts.prijato || 0)}`, "success", "purchaseorders"),
  ].join("");
  const arrows = [
    pipelineArrow(230, 100, 280, 100, 255, ""),
    pipelineArrow(490, 100, 540, 37, 515, ""),
    pipelineArrow(490, 100, 540, 132, 515, ""),
  ].join("");
  wrap.innerHTML = `
    <svg viewBox="0 0 800 180" width="800" height="180" style="min-width:760px;">
      <defs>
        <marker id="plArrowHead" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
          <path d="M0,0 L6,3 L0,6 Z" fill="var(--text-faint)"></path>
        </marker>
      </defs>
      ${arrows}
      ${boxes}
    </svg>`;
  wrap.querySelectorAll(".pl-clickbox").forEach(g => {
    g.addEventListener("click", () => {
      const btn = document.querySelector('.tab-btn[data-tab="' + g.dataset.nav + '"]');
      if (btn) btn.click();
    });
  });
}
async function loadSkladPipeline() {
  const errEl = document.getElementById("plSkladErr");
  errEl.textContent = "";
  try {
    const [rReorder, rPo] = await Promise.all([
      fetch("/api/shop/reorder-items?page_size=500"),
      fetch("/api/admin/purchase-orders?page_size=1"),
    ]);
    if (!rReorder.ok || !rPo.ok) { errEl.textContent = "Načtení selhalo."; return; }
    const dReorder = await rReorder.json();
    const dPo = await rPo.json();
    const reorderCounts = {};
    (dReorder.items || []).forEach(it => { reorderCounts[it.status] = (reorderCounts[it.status] || 0) + 1; });
    renderSkladPipelineDiagram(reorderCounts, dPo.counts || {});
    document.getElementById("plSkladUpdatedAt").textContent = "aktualizováno " + new Date().toLocaleTimeString("cs-CZ");
  } catch (e) {
    errEl.textContent = "Načtení selhalo: " + e.message;
  }
}
document.getElementById("plSkladRefreshBtn").onclick = loadSkladPipeline;

// ==================== PIPELINE - RENDER/GPU FRONTA ====================
// Jediná ze 4 novych domen, ktera potrebovala novy endpoint (stavy
// uloh zijou v *.status.json souborech, ne v DB tabulce s COUNT) -
// GET /api/admin/pipeline/render-overview (api/render_worker.py),
// znovupouziva uz existujici _stavy_uloh()/worker_tepe() (stejny zdroj
// jako system_pipeline.py), jen agregovane podle stavu.
function renderRenderPipelineDiagram(counts, worker) {
  const wrap = document.getElementById("plRenderDiagramWrap");
  const c = (k) => counts[k] || 0;
  const zpracovava = c("queued") + c("running");
  const chyba = c("error") + c("cancelled");
  const gpuPopis = worker.online
    ? `${worker.name || "?"} online${worker.gpu_temp_c != null ? " · " + worker.gpu_temp_c.toFixed(0) + "°C" : ""}`
    : "offline";
  const boxes = [
    pipelineBox(20, 70, 190, 60, "🕓 Fronta", `${c("waiting_worker")}`, "warn"),
    pipelineBox(280, 70, 190, 60, "⚙️ Zpracovává se", `${zpracovava}`, "accent"),
    pipelineBox(540, 20, 190, 55, "✅ Hotovo", `${c("done")}`, "success"),
    pipelineBox(540, 115, 190, 55, "✕ Chyba/zrušeno", `${chyba}`, "error"),
    pipelineBox(280, 0, 190, 50, worker.online ? "🖥️ GPU stanice" : "🖥️ GPU stanice (offline)", gpuPopis, worker.online ? "success" : "neutral", "dashboard"),
  ].join("");
  const arrows = [
    pipelineArrow(210, 100, 280, 100, 245, ""),
    pipelineArrow(470, 100, 540, 47, 505, ""),
    pipelineArrow(470, 100, 540, 142, 505, ""),
  ].join("");
  wrap.innerHTML = `
    <svg viewBox="0 0 760 190" width="760" height="190" style="min-width:700px;">
      <defs>
        <marker id="plArrowHead" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
          <path d="M0,0 L6,3 L0,6 Z" fill="var(--text-faint)"></path>
        </marker>
      </defs>
      ${arrows}
      ${boxes}
    </svg>`;
  wrap.querySelectorAll(".pl-clickbox").forEach(g => {
    g.addEventListener("click", () => {
      const btn = document.querySelector('.tab-btn[data-tab="' + g.dataset.nav + '"]');
      if (btn) btn.click();
    });
  });
}
async function loadRenderPipeline() {
  const errEl = document.getElementById("plRenderErr");
  errEl.textContent = "";
  try {
    const r = await fetch("/api/admin/pipeline/render-overview");
    if (!r.ok) { errEl.textContent = "Načtení selhalo."; return; }
    const data = await r.json();
    renderRenderPipelineDiagram(data.counts || {}, data.worker || {});
    // bot16, 2026-09-12 (bot4: Robert se divá sem, ne na Dashboard) -
    // stejne funkce jako Dashboard > GPU render worker panel, jen s
    // jinym cilovym elementem (viz gpuMonRenderCurrentJob/gpuMonRenderRecentJobs
    // v gpu-monitor.js) - zadna duplicitni logika.
    gpuMonRenderCurrentJob(data.current_job, "plRenderCurrentJob");
    gpuMonRenderRecentJobs(data.recent_jobs, "plRenderRecentJobs");
    document.getElementById("plRenderUpdatedAt").textContent = "aktualizováno " + new Date().toLocaleTimeString("cs-CZ");
  } catch (e) {
    errEl.textContent = "Načtení selhalo: " + e.message;
  }
}
document.getElementById("plRenderRefreshBtn").onclick = loadRenderPipeline;

document.getElementById("pipelineRefreshBtn")?.addEventListener("click", loadPipelineOverview);
