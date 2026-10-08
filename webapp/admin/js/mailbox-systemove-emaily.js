// ==================== E-MAILY (v objednavce) ====================
// bot3 v9 (api/emails.py): rucni odeslani (potvrzeni objednavky / vlastni
// text) + historie e-mailu teto objednavky. Odeslani ke konkretnimu
// dokladu je "Poslat e-mail" odkaz primo u radku v Dokladech (viz
// sendDocumentEmail nize) - vzdy s PDF prilohou dokladu.
const EMAIL_KIND_LABELS_ADMIN = {
  order_confirmation: "Potvrzení objednávky", status_change: "Změna stavu objednávky",
  proforma_invoice: "Zálohová faktura", payment_tax_document: "Daňový doklad k přijaté platbě",
  invoice: "Faktura", delivery_note: "Dodací list", custom: "Vlastní e-mail",
  ucetni_doklad: "Doklad pro účetní",
};

// bot16, 2026-10-06 (bot5: hak "schvaleny doklad -> e-mail ucetni do fronty ke schvaleni", api/ucetni_hak.py): vydane doklady maji template_key "ucetni_doklad", prijate
// "prijaty_doklad:<id>" (id v klici) - backend EMAIL_KIND_LABELS je nezna, pro cloveka by zustal surovy klic. Stitek se skladat tady; ostatni typy beze zmeny.
function emailTypLabel(e) {
  const k = String((e && e.template_key) || "");
  if (k === "prijaty_doklad" || k.indexOf("prijaty_doklad:") === 0) return "Přijatý doklad pro účetní";
  if (k === "ucetni_doklad") return EMAIL_KIND_LABELS_ADMIN.ucetni_doklad;
  const l = e && e.template_label;
  return (l && l !== k ? l : "") || EMAIL_KIND_LABELS_ADMIN[k] || l || k;
}

// bot16, 2026-10-08 (Robert přes bot9, řádek id 201 „Daňový doklad k přijaté platbě“: „tohle se nabídlo k odeslání a přitom schválení v dashboardu jsem udělal až teď“):
// created_at = kdy se e-mail ZAŘADIL (u automatických do fronty ke schválení), skutečné odeslání je sent_at (backend ho nastaví při odeslání / schválení, u starších záznamů je
// doplněné z audit_logu, jinak null). Seznam dřív u stavu „Odesláno“ ukazoval jen čas zařazení, takže to vypadalo, že e-mail odešel dřív, než ho někdo schválil.
// Sloupec „Odesláno“ se zobrazí, jen když API pole sent_at vrací (do nasazení backendu zůstává jen „Zařazeno“, ne řada pomlček).
function emailMaSentAt(emails) { return (emails || []).some(e => e && Object.prototype.hasOwnProperty.call(e, "sent_at")); }
function emailCas(v) { const d = v ? new Date(v) : null; return d && !isNaN(d) ? d.toLocaleString("cs-CZ") : ""; }
function emailOdeslanoHtml(e) {
  const cas = e.status === "sent" ? emailCas(e.sent_at) : "";
  if (cas) return escapeHtmlAdmin(cas);
  const proc = e.status === "sent" ? "Čas odeslání se nezaznamenal."
    : e.status === "pending" ? "Zatím neodesláno – čeká na schválení."
    : e.status === "rejected" ? "Zamítnuto – e-mail neodešel."
    : "Neodesláno.";
  return `<span style="color:#8b93a1;" title="${escapeHtmlAdmin(proc)}">—</span>`;
}
// sloupec „Odesláno“ (th[data-sloupec="odeslano"]) v dané tabulce zobrazit / skrýt
function emailNastavSloupecOdeslano(tabulka, zobrazit) {
  if (!tabulka) return;
  tabulka.querySelectorAll('th[data-sloupec="odeslano"]').forEach(th => { th.hidden = !zobrazit; });
}
// bot16, 2026-10-08 (Robert PŘÍMO: „nemůže se nabídnout odeslat e-mail o zaslání dokladu, který není schválený!“): e-mail s dokladem jde zařadit i odeslat až po schválení dokladu
// (shop_documents.approval_status = 'schvaleno', schvaluje se na Dashboardu; server to hlídá taky, tohle jen neukazuje odkaz, který by skončil chybou).
// Dokud API pole approval_status nevrací (starý backend), odkaz zůstává jako dřív.
const DOC_EMAIL_CEKA_TEXT = "Doklad ještě není schválený – e-mail s ním jde odeslat až po jeho schválení (Dashboard).";
function docNeschvalen(d) { return !!d && typeof d.approval_status === "string" && d.approval_status !== "schvaleno"; }
function docEmailOdkaz(d, trida, atributy, styl) {
  if (docNeschvalen(d)) return `<span class="doc-email-ceka" style="color:#8b93a1;" title="${escapeHtmlAdmin(DOC_EMAIL_CEKA_TEXT)}">e-mail až po schválení</span>`;
  return `<a href="#" class="${trida}" ${atributy}${styl ? ` style="${styl}"` : ""}>Poslat e-mail</a>`;
}
// štítek stavu: v seznamu E-maily i v historii objednávky stejný (v historii objednávky se dřív čekající a zamítnuté ukazovaly jako „Selhalo“)
function emailStatusPill(e) {
  const STATUS_PILLS = {
    sent: '<span class="order-status-pill expedovana">Odesláno</span>',
    pending: '<span class="order-status-pill pripravit">Čeká na schválení</span>',
    rejected: '<span class="order-status-pill nova">Zamítnuto</span>',
  };
  return STATUS_PILLS[e.status]
    || `<span class="order-status-pill zrusena" title="${escapeHtmlAdmin(e.error_message || '')}">Selhalo</span>`;
}

async function loadOrderEmails(orderId) {
  const tbody = document.getElementById("orderModalEmails");
  // bot5, 2026-09-29 (Robert primo: "ten Poslat email nevyvolá žádnou
  // akci!") - sendDocumentEmail nize se od 0c84caa1 vola i z prehledu
  // Doklady (objednavky-doklady.js), kde #orderModalEmails vubec
  // neexistuje (jen v detailu objednavky) - .innerHTML na null tise
  // (bez jakekoli hlasky v UI) shodilo celou funkci hned na prvnim
  // radku nize.
  if (!tbody) return;
  try {
    const r = await fetch(`/api/admin/orders/${orderId}/emails`);
    const data = await r.json();
    if (!r.ok) { tbody.innerHTML = ""; return; }
    const emails = data.emails || [];
    const maOdeslano = emailMaSentAt(emails);
    emailNastavSloupecOdeslano(tbody.closest("table"), maOdeslano);
    tbody.innerHTML = emails.length ? emails.map(e => `
      <tr>
        <td>${escapeHtmlAdmin(emailCas(e.created_at))}</td>${maOdeslano ? `
        <td class="email-odeslano">${emailOdeslanoHtml(e)}</td>` : ""}
        <td>${escapeHtmlAdmin(e.recipient_email || "")}</td>
        <td>${escapeHtmlAdmin(e.subject || "")}</td>
        <td>${escapeHtmlAdmin(emailTypLabel(e))}</td>
        <td>${emailStatusPill(e)}</td>
      </tr>
    `).join("") : `<tr><td colspan="${maOdeslano ? 6 : 5}" style="color:#666;">Zatím žádné e-maily.</td></tr>`;
  } catch (e) {
    tbody.innerHTML = "";
  }
}

// loadOrderSupportConversations (Robert 2026-08-22, "objednavka se
// nearchivuje !!! jde do objednavek") - konverzace z Emaily prichozi
// propojene na tuhle objednavku (viz api/support.py
// _link_conversation_to_order). Sekce zustava schovana (display:none),
// kdyz zadna konverzace neni propojena - vetsina objednavek zadnou mit
// nebude, prazdna tabulka by jen zabirala misto.
async function loadOrderSupportConversations(orderId) {
  const section = document.getElementById("orderModalSupportSection");
  const tbody = document.getElementById("orderModalSupportConversations");
  try {
    const r = await fetch(`/api/admin/orders/${orderId}/support-conversations`);
    const data = await r.json();
    const convs = (r.ok && data.conversations) || [];
    section.style.display = convs.length ? "" : "none";
    tbody.innerHTML = convs.map(c => `
      <tr class="order-row" style="cursor:pointer;" data-conv-id="${c.id}">
        <td>${new Date(c.last_message_at || c.created_at).toLocaleString("cs-CZ")}</td>
        <td>${escapeHtmlAdmin(c.customer_name || c.customer_email || "")}</td>
        <td>${escapeHtmlAdmin(c.email_subject || "(bez předmětu)")}${c.unread_by_admin ? " 🔵" : ""}</td>
        <td>${c.status === "closed" ? "Uzavřeno" : "Otevřeno"}</td>
      </tr>
    `).join("");
    tbody.querySelectorAll("tr[data-conv-id]").forEach(tr => {
      tr.onclick = () => {
        document.getElementById("orderModal").classList.remove("open");
        document.querySelector('.tab-btn[data-tab="support"]').click();
        openSupportModal(parseInt(tr.dataset.convId, 10));
      };
    });
  } catch (e) {
    section.style.display = "none";
  }
}

// bot5, 2026-09-29 (Robert primo: "ten Poslat email nevyvolá žádnou
// akci!") - #orderEmailErr existuje jen v detailu objednavky (modal),
// ne v prehledu Doklady (0c84caa1 volá tuhle funkci i odtud) - primy
// zapis na null tise (zadna hlaska, zadny error v UI) shazoval funkci
// driv, nez se vubec dostala k fetch(). Oba pristupy na DOM ted
// osetreny + vraci se {ok,error}, at si i volajici MIMO modal (viz
// objednavky-doklady.js) muze sam ukazat vysledek (napr. alert).
async function sendDocumentEmail(orderId, docId) {
  const errEl = document.getElementById("orderEmailErr");
  if (errEl) errEl.textContent = "";
  try {
    const r = await fetch(`/api/admin/documents/${docId}/email`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({}),
    });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) {
      const msg = data.error || "Odeslání se nezdařilo.";
      if (errEl) errEl.textContent = msg;
      return { ok: false, error: msg };
    }
    loadOrderEmails(orderId);
    return { ok: true };
  } catch (e) {
    const msg = "Odeslání se nezdařilo (chyba spojení).";
    if (errEl) errEl.textContent = msg;
    return { ok: false, error: msg };
  }
}

document.getElementById("btnSendOrderConfirmation").onclick = async () => {
  const errEl = document.getElementById("orderEmailErr");
  errEl.textContent = "";
  try {
    const r = await fetch(`/api/admin/orders/${currentOrderId}/emails`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ kind: "order_confirmation" }),
    });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) { errEl.textContent = data.error || "Odeslání se nezdařilo."; return; }
    loadOrderEmails(currentOrderId);
  } catch (e) {
    errEl.textContent = "Odeslání se nezdařilo (chyba spojení).";
  }
};

document.getElementById("btnToggleCustomEmail").onclick = () => {
  const form = document.getElementById("customEmailForm");
  form.style.display = form.style.display === "none" ? "" : "none";
};
document.getElementById("btnCancelCustomEmail").onclick = () => {
  document.getElementById("customEmailForm").style.display = "none";
};
document.getElementById("btnSendCustomEmail").onclick = async () => {
  const errEl = document.getElementById("orderEmailErr");
  errEl.textContent = "";
  const subject = document.getElementById("emailSubject").value.trim();
  const bodyText = document.getElementById("emailBody").value.trim();
  if (!subject || !bodyText) { errEl.textContent = "Vyplň předmět i text e-mailu."; return; }
  const payload = {
    kind: "custom", subject, body: bodyText,
    recipient: document.getElementById("emailRecipient").value.trim() || undefined,
    cc: document.getElementById("emailCc").value.trim() || undefined,
  };
  const attachId = document.getElementById("emailAttach").value;
  if (attachId) payload.attach_document_id = parseInt(attachId, 10);
  try {
    const r = await fetch(`/api/admin/orders/${currentOrderId}/emails`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
    });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) { errEl.textContent = data.error || "Odeslání se nezdařilo."; return; }
    document.getElementById("customEmailForm").style.display = "none";
    document.getElementById("emailRecipient").value = "";
    document.getElementById("emailCc").value = "";
    document.getElementById("emailSubject").value = "";
    document.getElementById("emailBody").value = "";
    loadOrderEmails(currentOrderId);
  } catch (e) {
    errEl.textContent = "Odeslání se nezdařilo (chyba spojení).";
  }
};

// ==================== E-MAILY: CELKOVY PREHLED ====================
// bot3 log (14): GET /api/admin/emails - stejny vzor jako Doklady, ale
// primarni taby jsou podle STAVU (Vse/Odeslano/Selhalo), protoze tady je
// nejdulezitejsi hned videt selhani odeslani. Typ sablony a zpusob
// odeslani (rucne/automaticky) jsou az filtry v panelu.
// page/page_size - task #78/87
let emailFilter = { status: "", template_key: "", trigger_type: "", q: "", date_from: "", date_to: "",
  page: 1, page_size: 50 };
let emailsCache = [];

// ==================== MAILBOX (bot3, 2026-08-24) ====================
let mailboxLogFilter = { page: 1, page_size: 50, outcome: "", q: "" };

async function loadMailboxLog() {
  const params = new URLSearchParams({ page: mailboxLogFilter.page, page_size: mailboxLogFilter.page_size });
  if (mailboxLogFilter.outcome) params.set("outcome", mailboxLogFilter.outcome);
  if (mailboxLogFilter.q) params.set("q", mailboxLogFilter.q);
  try {
    const r = await fetch(`/api/admin/support/mailbox-log?${params.toString()}`);
    const data = await r.json();
    if (!r.ok) { document.getElementById("mailboxLogErr").textContent = data.error || "Chyba."; return; }
    renderMailboxLogOutcomeTabs(data.outcome_counts || {}, data.outcome_labels || {});
    renderMailboxLogTable(data.entries || []);
    renderPager("mailboxLogPager", data, mailboxLogFilter, loadMailboxLog);
  } catch (e) {
    document.getElementById("mailboxLogErr").textContent = "Nepodařilo se načíst mailbox log.";
  }
}

function renderMailboxLogOutcomeTabs(counts, labels) {
  const total = Object.values(counts).reduce((a, b) => a + b, 0);
  const defs = [{ key: "", label: "Vše", count: total }]
    .concat(Object.keys(labels).map(k => ({ key: k, label: labels[k], count: counts[k] || 0 })));
  const wrap = document.getElementById("mailboxLogOutcomeTabs");
  wrap.innerHTML = defs.map(d => {
    const active = mailboxLogFilter.outcome === d.key;
    return `<button type="button" class="order-tab-btn${active ? " active" : ""}" data-key="${d.key}">${escapeHtmlAdmin(d.label)}<span class="otc">(${d.count})</span></button>`;
  }).join("");
  wrap.querySelectorAll(".order-tab-btn").forEach(btn => {
    btn.onclick = () => {
      mailboxLogFilter.outcome = btn.dataset.key;
      mailboxLogFilter.page = 1;
      loadMailboxLog();
    };
  });
}

function renderMailboxLogTable(entries) {
  const tbody = document.getElementById("mailboxLogTbody");
  if (!entries.length) {
    tbody.innerHTML = '<tr><td colspan="5" style="color:#666;">Žádné záznamy.</td></tr>';
    return;
  }
  tbody.innerHTML = entries.map(e => {
    const when = new Date(e.processed_at).toLocaleString("cs-CZ");
    const link = e.lead_id ? { tab: "crm", label: "→ poptávka" }
      : e.conversation_id ? { tab: "support", label: "→ konverzace" }
      : e.document_id ? { tab: "incomingdocuments", label: "→ doklad" }
      : null;
    return `<tr class="order-row" style="cursor:${link ? "pointer" : "default"};" data-tab="${link ? link.tab : ""}">
      <td>${when}</td>
      <td>${escapeHtmlAdmin(e.from_name ? `${e.from_name} <${e.from_email}>` : (e.from_email || ""))}</td>
      <td>${escapeHtmlAdmin(e.subject || "")}</td>
      <td>${escapeHtmlAdmin(e.outcome_label)}${link ? ` <span style="color:#8b93a1;">${link.label}</span>` : ""}</td>
      <td>${escapeHtmlAdmin(e.note || "")}</td>
    </tr>`;
  }).join("");
  tbody.querySelectorAll("tr.order-row").forEach(tr => {
    if (!tr.dataset.tab) return;
    tr.onclick = () => document.querySelector(`.tab-btn[data-tab="${tr.dataset.tab}"]`).click();
  });
}

document.getElementById("mailboxLogSearchApply").onclick = () => {
  mailboxLogFilter.q = document.getElementById("mailboxLogSearchQ").value.trim();
  mailboxLogFilter.page = 1;
  loadMailboxLog();
};
document.getElementById("mailboxLogSearchReset").onclick = () => {
  document.getElementById("mailboxLogSearchQ").value = "";
  mailboxLogFilter.q = "";
  mailboxLogFilter.page = 1;
  loadMailboxLog();
};

async function loadEmails() {
  const params = new URLSearchParams({ page: emailFilter.page, page_size: emailFilter.page_size });
  if (emailFilter.status) params.set("status", emailFilter.status);
  if (emailFilter.template_key) params.set("template_key", emailFilter.template_key);
  if (emailFilter.trigger_type) params.set("trigger_type", emailFilter.trigger_type);
  if (emailFilter.q) params.set("q", emailFilter.q);
  if (emailFilter.date_from) params.set("date_from", emailFilter.date_from);
  if (emailFilter.date_to) params.set("date_to", emailFilter.date_to);
  try {
    const r = await fetch(`/api/admin/emails?${params.toString()}`);
    const data = await r.json();
    if (!r.ok) { document.getElementById("emailsErr").textContent = data.error || "Chyba."; return; }
    emailsCache = data.emails || [];
    renderEmailStatusTabs(data.counts || {}, data.status_counts || {});
    renderEmailsTable(emailsCache);
    renderPager("emailsPager", data, emailFilter, loadEmails);
  } catch (e) {
    document.getElementById("emailsErr").textContent = "Nepodařilo se načíst e-maily.";
  }
}

function renderEmailStatusTabs(counts, statusCounts) {
  const defs = [
    { key: "", label: "Vše", count: counts.all ?? 0 },
    // "pending" (Robert 2026-08-22) - schvalovaci fronta, viz send_and_log
    // v api/emails.py. Prvni za "Vše" - potrebuje nejvic pozornosti.
    { key: "pending", label: "Čeká na schválení", count: statusCounts.pending ?? 0 },
    { key: "sent", label: "Odesláno", count: statusCounts.sent ?? 0 },
    { key: "failed", label: "Selhalo", count: statusCounts.failed ?? 0 },
    { key: "rejected", label: "Zamítnuto", count: statusCounts.rejected ?? 0 },
  ];
  const wrap = document.getElementById("emailStatusTabs");
  wrap.innerHTML = defs.map(d => {
    const active = emailFilter.status === d.key;
    return `<button type="button" class="order-tab-btn${active ? " active" : ""}" data-key="${d.key}">${escapeHtmlAdmin(d.label)}<span class="otc">(${d.count})</span></button>`;
  }).join("");
  wrap.querySelectorAll(".order-tab-btn").forEach(btn => {
    btn.onclick = () => {
      emailFilter.status = btn.dataset.key;
      emailFilter.page = 1;
      loadEmails();
    };
  });
}

// emailReviewAction (Robert 2026-08-22) - schvaleni/zamitnuti jednoho
// "pending" e-mailu, stejny vzor jako support.py triage-proposals review
// (PUT .../<id> {approved}). Po akci prekresli tabulku (stav/pocty se
// zmenily) - loadEmails() misto rucniho patchovani cache, jednodussi a
// vzdy presne odpovida serveru.
async function emailReviewAction(id, approved, btnEl) {
  // Schvaleni skutecne odesila e-mail (SMTP), zivě overeno az ~15-20s
  // (stejny timeout jako u rucniho odeslani, viz send_email v app.py) -
  // deaktivace tlacitka po dobu volani zabrani zmatenemu dvojitemu kliku.
  if (btnEl) { btnEl.disabled = true; btnEl.textContent = "…"; }
  try {
    // Robert 2026-08-24: nahledove okno je editovatelne - pokud je u
    // radku otevrene (textarea existuje v DOM), posle se aktualni
    // (pripadne upraveny) text spolu s rozhodnutim schvalit/zamitnout,
    // ne jen puvodni predvyplneny text.
    const payload = { approved };
    const ta = document.querySelector(`.email-preview-body[data-email-id="${id}"]`);
    const su = document.querySelector(`.email-preview-subject[data-email-id="${id}"]`);
    if (ta) payload.body_text = ta.value;
    if (su) payload.subject = su.value;
    const r = await fetch(`/api/admin/emails/${id}`, {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) { alert(data.error || "Akce se nezdařila."); return; }
    loadEmails();
  } finally {
    if (btnEl) btnEl.disabled = false;
  }
}

async function emailSaveDraft(id, btnEl) {
  if (btnEl) { btnEl.disabled = true; btnEl.textContent = "…"; }
  try {
    const ta = document.querySelector(`.email-preview-body[data-email-id="${id}"]`);
    const su = document.querySelector(`.email-preview-subject[data-email-id="${id}"]`);
    const r = await fetch(`/api/admin/emails/${id}`, {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ body_text: ta ? ta.value : undefined, subject: su ? su.value : undefined }),
    });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) { alert(data.error || "Uložení se nezdařilo."); return; }
    if (btnEl) btnEl.textContent = "💾 Uloženo";
    setTimeout(() => { if (btnEl) btnEl.textContent = "💾 Uložit úpravy"; }, 1500);
  } finally {
    if (btnEl) btnEl.disabled = false;
  }
}

// poslední známý stav sloupce „Odesláno“ (prázdný výsledek filtru ho nemá z čeho poznat)
let emailsMaOdeslano = false;
function renderEmailsTable(emails) {
  const tbody = document.getElementById("emailsTbody");
  if (emails.length) emailsMaOdeslano = emailMaSentAt(emails);
  emailNastavSloupecOdeslano(document.getElementById("emailsTbl"), emailsMaOdeslano);
  const sloupcu = emailsMaOdeslano ? 10 : 9;
  if (!emails.length) {
    tbody.innerHTML = `<tr><td colspan="${sloupcu}" style="color:#666;">Žádné e-maily.</td></tr>`;
    return;
  }
  tbody.innerHTML = emails.map(e => {
    const statusHtml = emailStatusPill(e);
    // bot5, 2026-08-02: e-maily nakupnich objednavek (dodavateli, template_key
    // "purchase_order") maji order_id/document_id NULL - patri jim misto toho
    // purchase_order_id. Sloupec "Objednávka"/proklik se podle toho prepne.
    const isPo = !e.order_id && e.purchase_order_id;
    const relatedLabel = isPo ? (e.po_number || "") : (e.order_number || "");
    // Pending radek: nezavisly klik na objednavku (aby se nedalo omylem
    // "odklinout pryc" bez rozhodnuti) - misto toho nahled + Schvalit/
    // Zamitnout primo v radku, stejny "bulk i po radcich" vzor jako triage.
    const pendingRow = e.status === "pending";
    return `<tr class="order-row${pendingRow ? " email-pending-row" : ""}" data-order-id="${e.order_id || ""}" data-po-id="${e.purchase_order_id || ""}" data-email-id="${e.id}" style="cursor:${pendingRow ? "default" : "pointer"};">
      <td><input type="checkbox" class="email-chk" data-id="${e.id}" ${emailSelectedIds.has(e.id) ? "checked" : ""} onclick="event.stopPropagation()"></td>
      <td>${escapeHtmlAdmin(emailCas(e.created_at))}</td>${emailsMaOdeslano ? `
      <td class="email-odeslano">${emailOdeslanoHtml(e)}</td>` : ""}
      <td>${escapeHtmlAdmin(e.recipient_email || "")}</td>
      <td>${escapeHtmlAdmin(e.subject || "")}</td>
      <td>${escapeHtmlAdmin(emailTypLabel(e))}</td>
      <td>${escapeHtmlAdmin(relatedLabel)}</td>
      <td>${e.document_id
        // bot5, 2026-09-29 (Robert primo: "nechte se na tom řádku ten
        // přikládaný soubor nechá aktivně načíst jako důkaz pro kontrolu
        // co obsahuje co skutečně odejde") - primy odkaz na STEJNY
        // endpoint (/api/admin/documents/<id>/pdf), ktery pouziva i
        // samotne schvaleni/odeslani (documents.render_document_pdf) -
        // cerstve vygenerovane PDF podle aktualnich dat, ne cachovany
        // soubor, takze presne ukazuje, co skutecne odejde.
        ? `<a href="/api/admin/documents/${e.document_id}/pdf" target="_blank" rel="noopener" onclick="event.stopPropagation()" title="Otevřít skutečné PDF přílohy v novém okně">📎 ${escapeHtmlAdmin(e.document_number || "PDF")}</a>`
        : "—"}</td>
      <td>${e.trigger_type === "auto" ? "Automaticky" : "Ručně"}</td>
      <td>${statusHtml}${pendingRow ? `
        <div style="margin-top:6px;display:flex;gap:6px;flex-wrap:wrap;">
          <button type="button" class="email-preview-btn" data-id="${e.id}" style="font-size:11.5px;padding:2px 8px;background:none;border:1px solid #3a3f4a;color:#c7ccd4;" onclick="event.stopPropagation()">✏️ Náhled a úprava</button>
          <button type="button" style="font-size:11.5px;padding:2px 8px;background:var(--success);color:#06140c;" onclick="event.stopPropagation();emailReviewAction(${e.id}, true, this)">✓ Schválit</button>
          <button type="button" style="font-size:11.5px;padding:2px 8px;background:none;border:1px solid var(--error);color:var(--error);" onclick="event.stopPropagation();emailReviewAction(${e.id}, false, this)">✕ Zamítnout</button>
        </div>` : ""}
      </td>
    </tr>${pendingRow ? `<tr class="email-preview-detail" data-email-id="${e.id}" style="display:none;"><td colspan="${sloupcu}" style="background:var(--panel-bg-alt);">
        ${e.cc_email ? `<div style="margin-bottom:6px;color:#9aa4b2;font-size:12.5px;">Kopie (Cc): ${escapeHtmlAdmin(e.cc_email)}</div>` : ""}
        <label style="display:block;font-size:11.5px;color:#9aa4b2;margin-bottom:3px;">Předmět</label>
        <input type="text" class="email-preview-subject" data-email-id="${e.id}" value="${escapeHtmlAdmin(e.subject || "")}" style="width:100%;box-sizing:border-box;margin-bottom:8px;">
        <label style="display:block;font-size:11.5px;color:#9aa4b2;margin-bottom:3px;">Text objednávky (upravitelný před schválením)</label>
        <textarea class="email-preview-body" data-email-id="${e.id}" rows="12" style="width:100%;box-sizing:border-box;font-family:inherit;font-size:13px;">${escapeHtmlAdmin(e.body_text || "")}</textarea>
        <div style="margin-top:6px;">
          <button type="button" style="font-size:11.5px;padding:2px 8px;background:none;border:1px solid #3a3f4a;color:#c7ccd4;" onclick="emailSaveDraft(${e.id}, this)">💾 Uložit úpravy</button>
        </div>
      </td></tr>` : ""}`;
  }).join("");
  tbody.querySelectorAll("tr.order-row").forEach(tr => {
    if (tr.classList.contains("email-pending-row")) return;
    tr.onclick = () => {
      if (tr.dataset.orderId) {
        document.querySelector('.tab-btn[data-tab="orders"]').click();
        openOrderDetail(parseInt(tr.dataset.orderId, 10));
      } else if (tr.dataset.poId) {
        document.querySelector('.tab-btn[data-tab="purchaseorders"]').click();
        openPODetail(parseInt(tr.dataset.poId, 10));
      }
    };
  });
  tbody.querySelectorAll(".email-preview-btn").forEach(btn => {
    btn.onclick = () => {
      const row = tbody.querySelector(`tr.email-preview-detail[data-email-id="${btn.dataset.id}"]`);
      if (row) row.style.display = row.style.display === "none" ? "" : "none";
    };
  });
  tbody.querySelectorAll(".email-chk").forEach(chk => {
    chk.onchange = () => {
      const id = parseInt(chk.dataset.id, 10);
      if (chk.checked) emailSelectedIds.add(id); else emailSelectedIds.delete(id);
      updateEmailBulkToolbar();
    };
  });
  updateEmailBulkToolbar();
}

let emailSelectedIds = new Set();
function updateEmailBulkToolbar() {
  const bar = document.getElementById("emailBulkToolbar");
  const count = emailSelectedIds.size;
  bar.classList.toggle("active", count > 0);
  document.getElementById("emailBulkCount").textContent = `${count} vybráno`;
}
document.getElementById("emailSelectAll").onchange = (e) => {
  if (e.target.checked) emailsCache.forEach(x => emailSelectedIds.add(x.id));
  else emailSelectedIds.clear();
  renderEmailsTable(emailsCache);
};
// Bulk Schvalit/Zamitnout (Robert 2026-08-22) - stejny vzor jako
// supportTriageBulkCategory: smycka fetch() (zadny dedikovany bulk-
// endpoint na backendu, konzistentni s triage), jeden loadEmails() az
// PO Promise.all (ne po kazde polozce zvlast - viz emailReviewAction
// pro jednotlive radky, ktery reload dela sam pro sebe). Radky, ktere
// uz nejsou "pending" (napr. zmenene mezitim jinym adminem), backend
// odmitne s 400 - Promise.all to nezastavi u zbytku davky.
document.getElementById("emailBulkApprove").onclick = async () => {
  if (!emailSelectedIds.size) return;
  const ids = [...emailSelectedIds];
  emailSelectedIds.clear();
  await Promise.all(ids.map(id => fetch(`/api/admin/emails/${id}`, {
    method: "PUT", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ approved: true }),
  })));
  loadEmails();
};
document.getElementById("emailBulkReject").onclick = async () => {
  if (!emailSelectedIds.size) return;
  if (!confirm(`Opravdu natrvalo zamítnout ${emailSelectedIds.size} vybraných e-mailů? Nikdy neodejdou.`)) return;
  const ids = [...emailSelectedIds];
  emailSelectedIds.clear();
  await Promise.all(ids.map(id => fetch(`/api/admin/emails/${id}`, {
    method: "PUT", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ approved: false }),
  })));
  loadEmails();
};
document.getElementById("emailBulkDelete").onclick = async () => {
  if (!emailSelectedIds.size) return;
  if (!confirm(`Opravdu trvale smazat ${emailSelectedIds.size} vybraných záznamů historie e-mailů? ` +
               `Jde o auditní záznamy odeslaných zpráv - tuto akci nelze vrátit zpět.`)) return;
  const r = await fetch("/api/admin/emails/bulk-delete", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ids: [...emailSelectedIds] }),
  });
  const data = await r.json().catch(() => ({}));
  emailSelectedIds.clear();
  if (data.failed && data.failed.length) {
    alert(`Smazáno: ${data.deleted}. Nešlo smazat: ${data.failed.length}.`);
  }
  loadEmails();
};

document.getElementById("emailSearchApply").onclick = () => {
  emailFilter.q = document.getElementById("emailSearchQ").value.trim();
  emailFilter.template_key = document.getElementById("emailFilterTemplate").value;
  emailFilter.trigger_type = document.getElementById("emailFilterTrigger").value;
  emailFilter.date_from = document.getElementById("emailFilterDateFrom").value;
  emailFilter.date_to = document.getElementById("emailFilterDateTo").value;
  emailFilter.page = 1;
  loadEmails();
};
document.getElementById("emailSearchReset").onclick = () => {
  document.getElementById("emailSearchQ").value = "";
  document.getElementById("emailFilterTemplate").value = "";
  document.getElementById("emailFilterTrigger").value = "";
  document.getElementById("emailFilterDatePreset").value = "";
  document.getElementById("emailFilterDateFrom").value = "";
  document.getElementById("emailFilterDateTo").value = "";
  emailFilter = { status: emailFilter.status, template_key: "", trigger_type: "", q: "", date_from: "", date_to: "",
    page: 1, page_size: emailFilter.page_size };
  loadEmails();
};

// ==================== SYSTEMOVE E-MAILY (bot13, 2026-08-23) ====================
// Fronta e-mailu nenavazanych na objednavku (dnes jen overeni e-mailu pri
// registraci, viz api/system_emails.py) - stejny schvalovaci vzor jako
// tabulka Odchozi e-maily vyse, jen mensi/bez filtru (nizky objem).
let systemEmailFilter = { status: "pending", page: 1, page_size: 50 };
let systemEmailsCache = [];
let systemEmailSelectedIds = new Set();

async function loadSystemEmails() {
  const params = new URLSearchParams({ page: systemEmailFilter.page, page_size: systemEmailFilter.page_size });
  if (systemEmailFilter.status) params.set("status", systemEmailFilter.status);
  try {
    const r = await fetch(`/api/admin/system-emails?${params.toString()}`);
    const data = await r.json();
    if (!r.ok) { document.getElementById("systemEmailsErr").textContent = data.error || "Chyba."; return; }
    systemEmailsCache = data.emails || [];
    renderSystemEmailStatusTabs(data.status_counts || {});
    renderSystemEmailsTable(systemEmailsCache);
    renderPager("systemEmailsPager", data, systemEmailFilter, loadSystemEmails);
  } catch (e) {
    document.getElementById("systemEmailsErr").textContent = "Nepodařilo se načíst systémové e-maily.";
  }
}

function renderSystemEmailStatusTabs(statusCounts) {
  const defs = [
    { key: "pending", label: "Čeká na schválení", count: statusCounts.pending ?? 0 },
    { key: "sent", label: "Odesláno", count: statusCounts.sent ?? 0 },
    { key: "failed", label: "Selhalo", count: statusCounts.failed ?? 0 },
    { key: "rejected", label: "Zamítnuto", count: statusCounts.rejected ?? 0 },
    { key: "", label: "Vše", count: Object.values(statusCounts).reduce((a, b) => a + b, 0) },
  ];
  const wrap = document.getElementById("systemEmailStatusTabs");
  wrap.innerHTML = defs.map(d => {
    const active = systemEmailFilter.status === d.key;
    return `<button type="button" class="order-tab-btn${active ? " active" : ""}" data-key="${d.key}">${escapeHtmlAdmin(d.label)}<span class="otc">(${d.count})</span></button>`;
  }).join("");
  wrap.querySelectorAll(".order-tab-btn").forEach(btn => {
    btn.onclick = () => {
      systemEmailFilter.status = btn.dataset.key;
      systemEmailFilter.page = 1;
      loadSystemEmails();
    };
  });
}

async function systemEmailReviewAction(id, approved, btnEl) {
  if (btnEl) { btnEl.disabled = true; btnEl.textContent = "…"; }
  try {
    const r = await fetch(`/api/admin/system-emails/${id}`, {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ approved }),
    });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) { alert(data.error || "Akce se nezdařila."); return; }
    loadSystemEmails();
  } finally {
    if (btnEl) btnEl.disabled = false;
  }
}

// poslední známý stav sloupce „Odesláno“ (viz emailsMaOdeslano u hlavního seznamu)
let systemEmailsMaOdeslano = false;
function renderSystemEmailsTable(emails) {
  const tbody = document.getElementById("systemEmailsTbody");
  if (emails.length) systemEmailsMaOdeslano = emailMaSentAt(emails);
  emailNastavSloupecOdeslano(document.getElementById("systemEmailsTbl"), systemEmailsMaOdeslano);
  const sloupcu = systemEmailsMaOdeslano ? 7 : 6;
  if (!emails.length) {
    tbody.innerHTML = `<tr><td colspan="${sloupcu}" style="color:#666;">Žádné systémové e-maily.</td></tr>`;
    return;
  }
  tbody.innerHTML = emails.map(e => {
    const statusHtml = emailStatusPill(e);
    const pendingRow = e.status === "pending";
    return `<tr>
      <td><input type="checkbox" class="system-email-chk" data-id="${e.id}" ${systemEmailSelectedIds.has(e.id) ? "checked" : ""}></td>
      <td>${escapeHtmlAdmin(emailCas(e.created_at))}</td>${systemEmailsMaOdeslano ? `
      <td class="email-odeslano">${emailOdeslanoHtml(e)}</td>` : ""}
      <td>${escapeHtmlAdmin(e.recipient_email || "")}</td>
      <td>${escapeHtmlAdmin(e.subject || "")}</td>
      <td>${escapeHtmlAdmin(e.kind_label || e.kind || "")}</td>
      <td>${statusHtml}${pendingRow ? `
        <div style="margin-top:6px;display:flex;gap:6px;flex-wrap:wrap;">
          <button type="button" class="system-email-preview-btn" data-id="${e.id}" style="font-size:11.5px;padding:2px 8px;background:none;border:1px solid #3a3f4a;color:#c7ccd4;">👁 Náhled</button>
          <button type="button" style="font-size:11.5px;padding:2px 8px;background:var(--success);color:#06140c;" onclick="systemEmailReviewAction(${e.id}, true, this)">✓ Schválit</button>
          <button type="button" style="font-size:11.5px;padding:2px 8px;background:none;border:1px solid var(--error);color:var(--error);" onclick="systemEmailReviewAction(${e.id}, false, this)">✕ Zamítnout</button>
        </div>` : ""}
      </td>
    </tr>${pendingRow ? `<tr class="system-email-preview-detail" data-email-id="${e.id}" style="display:none;"><td colspan="${sloupcu}" style="white-space:pre-wrap;font-size:13px;background:var(--panel-bg-alt);">${escapeHtmlAdmin(e.body_text || "")}</td></tr>` : ""}`;
  }).join("");
  tbody.querySelectorAll(".system-email-preview-btn").forEach(btn => {
    btn.onclick = () => {
      const row = tbody.querySelector(`tr.system-email-preview-detail[data-email-id="${btn.dataset.id}"]`);
      if (row) row.style.display = row.style.display === "none" ? "" : "none";
    };
  });
  tbody.querySelectorAll(".system-email-chk").forEach(chk => {
    chk.onchange = () => {
      const id = parseInt(chk.dataset.id, 10);
      if (chk.checked) systemEmailSelectedIds.add(id); else systemEmailSelectedIds.delete(id);
      updateSystemEmailBulkToolbar();
    };
  });
  updateSystemEmailBulkToolbar();
}

function updateSystemEmailBulkToolbar() {
  const bar = document.getElementById("systemEmailBulkToolbar");
  const count = systemEmailSelectedIds.size;
  bar.classList.toggle("active", count > 0);
  document.getElementById("systemEmailBulkCount").textContent = `${count} vybráno`;
}
document.getElementById("systemEmailSelectAll").onchange = (e) => {
  if (e.target.checked) systemEmailsCache.forEach(x => systemEmailSelectedIds.add(x.id));
  else systemEmailSelectedIds.clear();
  renderSystemEmailsTable(systemEmailsCache);
};
document.getElementById("systemEmailBulkApprove").onclick = async () => {
  if (!systemEmailSelectedIds.size) return;
  const ids = [...systemEmailSelectedIds];
  systemEmailSelectedIds.clear();
  await Promise.all(ids.map(id => fetch(`/api/admin/system-emails/${id}`, {
    method: "PUT", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ approved: true }),
  })));
  loadSystemEmails();
};
document.getElementById("systemEmailBulkReject").onclick = async () => {
  if (!systemEmailSelectedIds.size) return;
  if (!confirm(`Opravdu natrvalo zamítnout ${systemEmailSelectedIds.size} vybraných e-mailů? Nikdy neodejdou.`)) return;
  const ids = [...systemEmailSelectedIds];
  systemEmailSelectedIds.clear();
  await Promise.all(ids.map(id => fetch(`/api/admin/system-emails/${id}`, {
    method: "PUT", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ approved: false }),
  })));
  loadSystemEmails();
};

