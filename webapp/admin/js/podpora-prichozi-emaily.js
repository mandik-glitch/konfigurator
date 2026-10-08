// ==================== PODPORA (zivy chat) ====================
// bot1, 2026-07-25 - Faze 1 z SUPPORT_SYSTEM_NAVRH.md. Zdroj dat: api/support.py.
// Rozsireno 2026-07-26 (Robert: "chybi tlacitko smazat a filtry") o
// filtrovani podle stavu/hledani a mazani konverzace.
let supportConvPollTimer = null;
let supportModalConvId = null;
let supportModalConvArchived = false;
let supportModalPollTimer = null;
// page/page_size - task #78/87
let supportFilter = { status: "", q: "", source: "", date_from: "", date_to: "", unread_only: false, sort: "newest",
  archived: false, page: 1, page_size: 50 };
const SUPPORT_SOURCE_LABELS = { widget_scene: "3D konfigurátor", widget_realizace: "Realizace.html", widget_offer: "Online nabídka", email: "E-mail" };

function supportFmtTime(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleString("cs-CZ", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
}

function renderSupportStatusTabs(statusCounts, archivedCount) {
  const open = statusCounts.open || 0;
  const closed = statusCounts.closed || 0;
  // Zalozka Archiv (bot23, 2026-08-17, stejny vzor jako renderCrmStatusTabs)
  // - archivovane konverzace zij jen tady, bezne zalozky je neukazuji
  // (backend filtruje archived=0).
  const defs = [
    { key: "", label: "Vše", count: open + closed },
    { key: "open", label: "Otevřené", count: open },
    { key: "closed", label: "Uzavřené", count: closed },
    { key: "__archiv", label: "🗄 Archiv", count: archivedCount || 0 },
  ];
  const wrap = document.getElementById("supportStatusTabs");
  wrap.innerHTML = defs.map(d => {
    const active = d.key === "__archiv" ? supportFilter.archived : (!supportFilter.archived && supportFilter.status === d.key);
    return `<button type="button" class="order-tab-btn${active ? " active" : ""}" data-key="${d.key}">${d.label}<span class="otc">(${d.count})</span></button>`;
  }).join("");
  wrap.querySelectorAll(".order-tab-btn").forEach(btn => {
    btn.onclick = () => {
      if (btn.dataset.key === "__archiv") {
        supportFilter.archived = true;
        supportFilter.status = "";
      } else {
        supportFilter.archived = false;
        supportFilter.status = btn.dataset.key;
      }
      supportFilter.page = 1;
      loadSupportConversations();
    };
  });
}

async function loadSupportNotifyEmail() {
  try {
    const r = await fetch("/api/admin/support/settings");
    const data = await r.json().catch(() => ({}));
    if (!r.ok) return;
    document.getElementById("supportNotifyEmailInput").value = data.notify_email || "";
  } catch (e) {}
}

document.getElementById("btnSaveSupportNotifyEmail").onclick = async () => {
  const status = document.getElementById("supportNotifyEmailStatus");
  const email = document.getElementById("supportNotifyEmailInput").value.trim();
  status.textContent = "ukládám…";
  try {
    const r = await fetch("/api/admin/support/settings", {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ notify_email: email }),
    });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(data.error || ("HTTP " + r.status));
    status.textContent = "uloženo ✓";
    setTimeout(() => { status.textContent = ""; }, 2000);
  } catch (e) {
    status.textContent = "chyba: " + e.message;
  }
};

let supportConvCache = [];
let supportSelectedIds = new Set();
async function loadSupportConversations(preserveSelection = false) {
  try {
    const params = new URLSearchParams({ page: supportFilter.page, page_size: supportFilter.page_size });
    if (supportFilter.status) params.set("status", supportFilter.status);
    if (supportFilter.q) params.set("q", supportFilter.q);
    if (supportFilter.source) params.set("source", supportFilter.source);
    if (supportFilter.date_from) params.set("date_from", supportFilter.date_from);
    if (supportFilter.date_to) params.set("date_to", supportFilter.date_to);
    if (supportFilter.unread_only) params.set("unread_only", "1");
    if (supportFilter.sort === "oldest") params.set("sort", "oldest");
    if (supportFilter.archived) params.set("archived", "1");
    const r = await fetch(`/api/admin/support/conversations?${params.toString()}`);
    if (!r.ok) throw new Error("HTTP " + r.status);
    const data = await r.json();
    renderSupportStatusTabs(data.status_counts || {}, data.archived_count || 0);
    supportConvCache = data.conversations || [];
    if (!preserveSelection) supportSelectedIds.clear();
    renderSupportConvTable();
    updateSupportBulkToolbar();
    const badge = document.getElementById("supportNavBadge");
    const n = data.unread_count || 0;
    badge.textContent = n;
    badge.classList.toggle("show", n > 0);
    renderPager("supportConvPager", data, supportFilter, loadSupportConversations);
  } catch (e) {
    document.getElementById("supportConvErr").textContent = "Chyba načtení: " + e.message;
  }
}

function renderSupportConvTable() {
  const tbody = document.getElementById("supportConvTbody");
  tbody.innerHTML = supportConvCache.map(c => `
    <tr class="${c.unread_by_admin ? 'unread' : ''}" data-id="${c.id}" style="cursor:pointer;">
      <td><input type="checkbox" class="support-chk" data-id="${c.id}" ${supportSelectedIds.has(c.id) ? "checked" : ""}></td>
      <td>${escapeHtmlAdmin(c.customer_name || c.customer_email || ('#' + c.customer_user_id))}</td>
      <td>${escapeHtmlAdmin(c.customer_email || "")}</td>
      <td>${c.linked_lead_id ? `<span class="support-lead-badge" data-lead-id="${c.linked_lead_id}" title="Klasifikováno jako poptávka - klikni pro otevření v Poptávkách">🏷️ Poptávka</span> ` : ""}${escapeHtmlAdmin(c.email_subject || "") || '<span style="color:#8b93a1;">–</span>'}</td>
      <td>${SUPPORT_SOURCE_LABELS[c.source] || c.source}</td>
      <td>${c.status === "closed" ? "Uzavřeno" : "Otevřeno"}</td>
      <td>${supportFmtTime(c.last_message_at)}</td>
    </tr>
  `).join("") || '<tr><td colspan="7" style="color:#8b93a1;">Žádné konverzace neodpovídají filtru.</td></tr>';
  tbody.querySelectorAll("tr[data-id]").forEach(tr => {
    tr.onclick = (e) => {
      if (e.target.closest("input") || e.target.closest(".support-lead-badge")) return;
      openSupportModal(parseInt(tr.dataset.id, 10));
    };
  });
  // bot10, 2026-08-23 (Robert pres bot3: "poptavka jako stitek opticky
  // uz v emailech") - klik na stitek otevre rovnou detail poptavky
  // (openCrmModal je samostatny modal, nevyzaduje prepnuti na zalozku
  // Poptavky driv), misto otevreni konverzace pod nim.
  tbody.querySelectorAll(".support-lead-badge").forEach(badge => {
    badge.onclick = (e) => {
      e.stopPropagation();
      openCrmModal(parseInt(badge.dataset.leadId, 10));
    };
  });
  tbody.querySelectorAll(".support-chk").forEach(chk => {
    chk.onchange = () => {
      const id = parseInt(chk.dataset.id, 10);
      if (chk.checked) supportSelectedIds.add(id); else supportSelectedIds.delete(id);
      updateSupportBulkToolbar();
    };
  });
}

function updateSupportBulkToolbar() {
  const bar = document.getElementById("supportBulkToolbar");
  const count = supportSelectedIds.size;
  bar.classList.toggle("active", count > 0);
  document.getElementById("supportBulkCount").textContent = `${count} vybráno`;
  // Lista je trvale viditelna (Robert 2026-08-18) - tlacitka misto
  // toho disable/enable podle toho, jestli je co delat.
  ["supportBulkClose", "supportBulkOpen", "supportBulkArchive", "supportBulkDelete"].forEach(id => {
    document.getElementById(id).disabled = count === 0;
  });
  // V zalozce Archiv dava smysl jen "vratit z archivu", jinde jen
  // "archivovat" (bot23, 2026-08-17)
  document.getElementById("supportBulkArchive").textContent =
    supportFilter.archived ? "↩ Obnovit z archivu" : "🗄 Archivovat";
}
document.getElementById("supportSelectAll").onchange = (e) => {
  if (e.target.checked) supportConvCache.forEach(c => supportSelectedIds.add(c.id));
  else supportSelectedIds.clear();
  renderSupportConvTable();
  updateSupportBulkToolbar();
};
async function supportBulkSetStatus(status) {
  if (!supportSelectedIds.size) return;
  await fetch("/api/admin/support/conversations/bulk-close", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ids: [...supportSelectedIds], status }),
  });
  loadSupportConversations();
}
document.getElementById("supportBulkClose").onclick = () => supportBulkSetStatus("closed");
document.getElementById("supportBulkOpen").onclick = () => supportBulkSetStatus("open");
document.getElementById("supportBulkArchive").onclick = async () => {
  if (!supportSelectedIds.size) return;
  await fetch("/api/admin/support/conversations/bulk-archive", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ids: [...supportSelectedIds], archived: !supportFilter.archived }),
  });
  loadSupportConversations();
};
document.getElementById("supportBulkDelete").onclick = async () => {
  if (!supportSelectedIds.size) return;
  if (!confirm(`Opravdu smazat ${supportSelectedIds.size} konverzací? Tuto akci nelze vrátit zpět.`)) return;
  await fetch("/api/admin/support/conversations/bulk", {
    method: "DELETE", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ids: [...supportSelectedIds] }),
  });
  loadSupportConversations();
};

// ==================== TRIDENI PRICHOZICH E-MAILU (bot3, 2026-08-18) ====================
// Robert: tlacitko "Tridit" zada botovi ukol vytridit otevrene
// konverzace a navrhnout, kam kazda dal patri + co s prilohami -
// navrh se objevi tady k rucnimu schvaleni/zamitnuti kazdeho radku.
// Zadne zive AI volani (viz api/support.py modulovy komentar) -
// backend jen zaklada/cte "beh", skutecny navrh dopisuje bot rucne
// (scripts/2026-08-18_support_triage_submit.py), proto se to sem
// dotahuje pollingem.
const TRIAGE_DEST_LABELS = {
  crm: "Poptávka (CRM)", doklad: "Přijatý doklad", objednavka: "Objednávka (propojí/založí)",
  // Robert 2026-08-22 (přes bot3, po zavedení "Schválit -> Uzavřít"
  // vyse) - "Ponechat v Emaily příchozí" uz je matouci/nepravdive, ted
  // schvaleni konverzaci UZAVIRA, ne ze by "zustala lezet".
  podpora: "Podpora (vyřídit a uzavřít)", spam: "Spam/nesouvisející", jine: "Nejasné",
};

// Robert 2026-08-22 ("z tlačítek Schválit/Zamítnout musí být hned jasné,
// co se stane dál, bez znalosti kódu") - texty tlačítek podle kategorie
// misto genrickeho "Schválit"/"Zamítnout" napříč vším. "Zamítnout" je
// UNIVERZÁLNĚ "beze změny" (support.py support_triage_proposal_review -
// jen zaznamená rozhodnutí, žádná destinace nemá u zamítnutí vlastní
// větev) - stejný label pro všechny kategorie stačí, jen s tooltipem.
// "Schválit" se ale lisí kategorii od kategorie, viz jednotlive title
// atributy pro detail (napr. "doklad" ceka DALSI schvaleni jinde,
// "spam" je nevratne).
const TRIAGE_APPROVE_LABEL = {
  crm: "✓ Schválit → Poptávky",
  doklad: "✓ Schválit → Doklady",
  objednavka: "✓ Schválit → Objednávka",
  spam: "🗑️ Schválit → SMAZAT",
  podpora: "✓ Schválit → Uzavřít",
  jine: "✓ Schválit (bez akce)",
};
const TRIAGE_APPROVE_TITLE = {
  crm: "Přesune konverzaci do Poptávek (CRM) - zprávy i přílohy se napojí na poptávku (novou nebo vybranou).",
  doklad: "Pošle do fronty Dokladů - tam čeká na DRUHÉ, samostatné schválení, než se soubor uloží na Sdílený disk.",
  objednavka: "Propojí konverzaci s existující objednávkou podle čísla nalezeného v e-mailu. Nenajde-li se, ROVNOU ZALOŽÍ novou objednávku (bez položek - doplníte ručně) a propojí na ni.",
  spam: "Konverzaci i s přílohami TRVALE SMAŽE. Nelze vrátit zpět!",
  // Robert 2026-08-22 ("Ponechat v Emaily příchozí... co je to za
  // výmysl?" -> "nemůže existovat skupina, která bude hromadit
  // e-maily") - schválení už NENÍ bez akce, konverzace se rovnou
  // uzavře (status='closed'). Případnou odpověď zákazníkovi proto
  // musí admin napsat PŘED schválením, ne po - schválení = vyřízeno.
  podpora: "Uzavře konverzaci (zmizí z otevřených, zůstane dohledatelná v historii). Odpověď zákazníkovi napiš PŘED schválením, ne po.",
  jine: "Jen zaznamená rozhodnutí - konverzace zůstává beze změny v Emaily příchozí (stejný výsledek jako Zamítnout).",
};
const TRIAGE_REJECT_LABEL = "✕ Zamítnout (ponechat)";
const TRIAGE_REJECT_TITLE = "Konverzace zůstává beze změny v Emaily příchozí - žádná akce se neprovede.";
let supportTriagePollTimer = null;
let supportTriageRunId = null;

function escapeHtmlTriage(s) {
  return String(s == null ? "" : s).replace(/[&<>"']/g, c => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

// Robert 2026-08-19: "nechci urcovat radek po radku... chci schvalit
// nebo zamitnout celou tabulku" - misto jednoho dlouheho seznamu
// (kde uz vyrizene polozky poradaly viset a plest se s novymi) se
// navrhy seskupuji podle navrhovaneho cile (spam/CRM/doklad/...) a
// dá se schvalit/zamitnout CELA kategorie najednou (level po levelu).
// Poradi kategorii: spam nejdriv (nejjednoznacnejsi/nejrychlejsi),
// pak crm a doklad (vyzaduji akci), jine, podpora az nakonec (ta uz
// zustava na miste beze zmeny, nejmene urgentni). Uz vyrizene navrhy
// se v seznamu VUBEC nezobrazuji - jen souhrnny pocet nahore, aby
// znovuotevreni okna neukazovalo porad totez, co uz je hotove.
const TRIAGE_CATEGORY_ORDER = ["spam", "crm", "doklad", "objednavka", "jine", "podpora"];

function renderSupportTriageBody(run) {
  const body = document.getElementById("supportTriageBody");
  if (run.status === "pending") {
    body.innerHTML = '<p class="hint">Zpracovává se… (bot právě čte otevřené konverzace a připravuje návrh). Okno se samo doplní, klidně ho zatím zavři a vrať se později přes tlačítko "Třídit".</p>';
    return;
  }
  if (!run.proposals.length) {
    body.innerHTML = '<p class="hint">Bot nenašel žádné otevřené konverzace k vytřídění.</p>';
    return;
  }
  const pending = run.proposals.filter(p => p.review_status === "pending");
  const reviewedCount = run.proposals.length - pending.length;
  const summary = reviewedCount
    ? `<p class="hint">${reviewedCount} už vytříděno, zbývá ${pending.length}.</p>` : "";
  if (!pending.length) {
    body.innerHTML = summary + '<p class="hint">Vše vytříděno. 🎉</p>';
    return;
  }
  const byDest = {};
  pending.forEach(p => {
    (byDest[p.proposed_destination] ||= []).push(p);
  });
  const order = [...TRIAGE_CATEGORY_ORDER, ...Object.keys(byDest).filter(d => !TRIAGE_CATEGORY_ORDER.includes(d))];
  body.innerHTML = summary + order.filter(d => byDest[d]).map(dest => {
    const items = byDest[dest];
    const label = TRIAGE_DEST_LABELS[dest] || dest;
    const approveLabel = (TRIAGE_APPROVE_LABEL[dest] || "✓ Schválit").replace("Schválit", "Schválit vše");
    const approveTitle = TRIAGE_APPROVE_TITLE[dest] || "";
    // "doklad": Robert (2026-08-19) - appka/bot spolehlive nepozna,
    // jestli je priloha skutecne faktura, jen ON to pozna vizualne -
    // hromadne "Schvalit vse" tu proto NEJDE, kazda polozka se resi
    // jednotlive s nahledem prilohy (viz supportTriageLoadAttachments
    // nize). "Zamitnout vse" zustava beze zmeny (nic se tam neuklada).
    const bulkApprove = dest === "doklad" ? "" :
      `<button onclick="supportTriageBulkCategory('${dest}', true)" title="${escapeHtmlTriage(approveTitle)}" style="background:var(--success);color:#06140c;">${approveLabel}</button>`;
    // Robert 2026-08-22 ("z tlacitek musi byt hned jasne, co se stane
    // dal") - "jine" nema zadnou automatizovanou akci ani pri
    // schvaleni, takze Schvalit i Zamitnout delaji ve skutecnosti totez
    // (jen jine zaznamenane rozhodnuti) - kratka poznamka rovnou v
    // hlavicce kategorie, at to neni matouci ("proc obe tlacitka
    // vypadaji stejne dulezite, kdyz nic nedelaji"). "podpora" MELA
    // stejnou poznamku, ale Robert ten koncept odmitl ("Ponechat v
    // Emaily prichozi... co je to za vymysl?" -> "nemuze existovat
    // skupina, ktera bude hromadit e-maily") - schvaleni tam ted
    // konverzaci uzavira (viz TRIAGE_APPROVE_TITLE.podpora), takze uz
    // NENI stejne jako Zamitnout a poznamka by byla zavadejici.
    const sameEffectNote = dest === "jine"
      ? '<div class="hint" style="margin-top:2px;">Schválit i Zamítnout tady jen zaznamenají rozhodnutí - konverzace zůstává beze změny v obou případech.</div>'
      : "";
    return `
      <div class="triage-category">
        <div class="triage-category-head">
          <strong>${escapeHtmlTriage(label)} (${items.length})</strong>
          <div class="triage-actions">
            ${bulkApprove}
            <button onclick="supportTriageBulkCategory('${dest}', false)" title="${escapeHtmlTriage(TRIAGE_REJECT_TITLE)}" style="background:none;border:1px solid var(--error);color:var(--error);">${TRIAGE_REJECT_LABEL.replace("Zamítnout", "Zamítnout vše")}</button>
            <button onclick="supportTriageBulkDefer('${dest}')" style="background:none;border:1px solid var(--text-faint);color:var(--text-muted);">Přesunout do další dávky</button>
            ${dest === "jine" ? `<button onclick="supportTriageBulkDelete('${dest}')" title="Trvale smaže všechny konverzace v této kategorii. Nelze vrátit zpět!" style="background:var(--error);color:#fff;">🗑 Smazat vše</button>` : ""}
          </div>
        </div>
        ${sameEffectNote}
        ${items.map(p => `
          <div class="triage-row" data-id="${p.id}">
            <div class="triage-row-head">
              <div>
                <strong>${escapeHtmlTriage(p.customer_name)}</strong>
                ${p.email_subject ? " — " + escapeHtmlTriage(p.email_subject) : ""}
              </div>
              <div class="triage-actions">
                <button onclick="supportTriageReview(${p.id}, true)" title="${escapeHtmlTriage(TRIAGE_APPROVE_TITLE[dest] || "")}" style="background:var(--success);color:#06140c;">${TRIAGE_APPROVE_LABEL[dest] || "✓ Schválit"}</button>
                <button onclick="supportTriageReview(${p.id}, false)" title="${escapeHtmlTriage(TRIAGE_REJECT_TITLE)}" style="background:none;border:1px solid var(--error);color:var(--error);">${TRIAGE_REJECT_LABEL}</button>
                <button onclick="supportTriageDefer(${p.id})" style="background:none;border:1px solid var(--text-faint);color:var(--text-muted);">Přesunout do další dávky</button>
                ${dest === "jine" ? `<button onclick="supportTriageDelete(${p.id})" title="Trvale smaže tuto konverzaci. Nelze vrátit zpět!" style="background:var(--error);color:#fff;">🗑 Smazat</button>` : ""}
                ${p.customer_email && p.customer_email.includes("@") ? `<button class="triage-blacklist-domain-btn" data-conv-id="${p.conversation_id}" title="Zařadí celou doménu odesílatele do černé listiny (další e-maily z ní se od teď vůbec neuloží) a smaže tuto i všechny další zatím nevytříděné konverzace ze stejné domény." style="background:none;border:1px solid var(--error);color:var(--error);">🚫 Blacklistovat doménu</button>` : ""}
              </div>
            </div>
            ${p.reasoning ? `<div class="triage-reasoning">${escapeHtmlTriage(p.reasoning)}</div>` : ""}
            ${p.attachment_note ? `<div class="triage-attach">📎 ${escapeHtmlTriage(p.attachment_note)}</div>` : ""}
            ${dest === "doklad" ? `<div class="triage-invoice-picker" id="triageInvoicePicker${p.id}" data-suggested="${escapeHtmlTriage(p.invoice_attachment_filename || "")}"><span class="hint">Načítám přílohy…</span></div>`
              // Robert 2026-08-22 ("u kazdeho radku videt, jestli ma
              // konverzace prilohy a s jakymi nazvy") - u "doklad" uz
              // skutecny seznam ukazuje interaktivni picker vyse (radio
              // tlacitka se jmeny), tady jen zbyva zbytek destinaci.
              // Placeholder se po nacteni SAM ODSTRANI, kdyz priloha
              // zadna neni (viz supportTriageLoadAttachmentChips) - zadny
              // prazdny box.
              : `<div class="triage-attach-chips" id="triageAttachChips${p.id}"></div>`}
            ${dest === "crm" ? `
              <div class="triage-lead-picker" style="margin-top:6px;position:relative;">
                <input type="text" id="triageLeadSearch${p.id}" autocomplete="off"
                  placeholder="Přiřadit k existující poptávce (místo automatického rozpoznání)…"
                  style="width:100%;box-sizing:border-box;font-size:12.5px;">
                <div id="triageLeadSuggest${p.id}" class="product-suggestions"></div>
                <div id="triageLeadPicked${p.id}" class="hint" style="margin-top:4px;"></div>
              </div>
            ` : ""}
          </div>
        `).join("")}
      </div>
    `;
  }).join("");
  body.querySelectorAll(".triage-invoice-picker").forEach(el => {
    const proposalId = el.id.replace("triageInvoicePicker", "");
    supportTriageLoadAttachments(proposalId);
  });
  body.querySelectorAll(".triage-attach-chips").forEach(el => {
    const proposalId = el.id.replace("triageAttachChips", "");
    supportTriageLoadAttachmentChips(proposalId);
  });
  body.querySelectorAll(".triage-lead-picker").forEach(el => {
    const proposalId = el.querySelector("input").id.replace("triageLeadSearch", "");
    wireTriageLeadPicker(proposalId);
    // Prekresleni (napr. po jine akci v jinem radku) by jinak ztratilo
    // uz vybranou poptavku z pohledu UI - obnov zobrazeny stav z mapy.
    const picked = supportTriageLeadPick[proposalId];
    if (picked) {
      document.getElementById("triageLeadPicked" + proposalId).innerHTML =
        supportTriageLeadPickedHtml(picked);
    }
  });
  body.querySelectorAll(".triage-blacklist-domain-btn").forEach(btn => {
    btn.onclick = () => supportTriageBlacklistDomain(parseInt(btn.dataset.convId, 10));
  });
}

// Robert 2026-08-22 (pres bot3): "tlacitko ktere domenu odesilatele
// zaradi do cerne listiny tak abychom dalsi e-maily od nich uz
// nevideli" + "aby se automaticky mazali" - viz
// api/support.py support_admin_blacklist_sender_domain (backend
// mechanismus crm_classifier_sender_rules uz existoval, tohle je jen
// UI zkratka primo z trideni). Nevratna akce (blacklist + trvale
// smazani), proto potvrzovaci dialog jako u "spam".
async function supportTriageBlacklistDomain(conversationId) {
  if (!confirm('Opravdu blacklistovat doménu odesílatele? Další e-maily z ní se od teď VŮBEC NEULOŽÍ. Zároveň se TRVALE SMAŽE tato konverzace i všechny další zatím nevytříděné e-maily ze stejné domény (pokud nějaké existují). Nelze vrátit zpět!')) return;
  const r = await fetch(`/api/admin/support/conversations/${conversationId}/blacklist-sender-domain`, { method: "POST" });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) { alert(data.error || "Nepodařilo se blacklistovat doménu."); return; }
  // Robert 2026-08-22 (pres bot3): puvodni verze tu mela jeste uspesny
  // alert() - DRUHY nativni dialog hned po confirm() vyse. Prohlizec na
  // 2+ nativni dialogy v jedne zalozce reaguje vlastnim (appkou NIJAK
  // needitovatelnym) zaskrtavatkem "Zablokovat dalsi dotazy z <hostname
  // teto zalozky>" - to zamenil Robert za soucast appky/vlastni checkbox
  // funkce. Zadny takovy checkbox appka nikdy nevytvarela (viz i
  // ostatni triage akce vyse - supportTriageReview() take jen alert()
  // na CHYBU, na uspech je ticho + refresh, stejny vzor tady).
  loadSupportTriageRun();
  loadSupportConversations();
}

async function supportTriageBulkCategory(dest, approved) {
  const run = await fetch("/api/admin/support/triage-runs/" + supportTriageRunId).then(r => r.json());
  const ids = run.proposals.filter(p => p.review_status === "pending" && p.proposed_destination === dest).map(p => p.id);
  if (!ids.length) return;
  const verb = approved ? "schválit" : "zamítnout";
  if (!confirm(`Opravdu ${verb} všech ${ids.length} položek (${TRIAGE_DEST_LABELS[dest] || dest})?`)) return;
  // Respektuj jednotlive rucni prirazeni k poptavce (wireTriageLeadPicker),
  // pokud je admin pro nektere polozky pred kliknutim na "Schvalit vse"
  // vybral - jinak by je "Schvalit vse" tise prebilo automatickym
  // rozpoznanim.
  await Promise.all(ids.map(id => {
    const payload = { approved };
    const pickedLead = supportTriageLeadPick[id];
    if (pickedLead) payload.lead_id = pickedLead.id;
    delete supportTriageLeadPick[id];
    return fetch("/api/admin/support/triage-proposals/" + id, {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  }));
  loadSupportTriageRun();
  loadSupportConversations();
}

// Robert 2026-08-20 ("chci tlacitko presunout do dalsi davky") -
// misto vynuceni schvalit/zamitnout u polozky, kde jeste neni dost
// informaci na rozhodnuti, jde presunout do noveho stavu "deferred"
// (api/support.py) - konverzace zustava beze zmeny/otevrena, takze ji
// priste zalozeny beh treideni sam znovu najde. Odlisne od Zamitnout,
// at je v historii videt rozdil "bot navrhl spatne" vs. "nemel jsem
// cas/info ted".
async function supportTriageDefer(proposalId) {
  await fetch(`/api/admin/support/triage-proposals/${proposalId}/defer`, { method: "POST" });
  loadSupportTriageRun();
}
async function supportTriageBulkDefer(dest) {
  const run = await fetch("/api/admin/support/triage-runs/" + supportTriageRunId).then(r => r.json());
  const ids = run.proposals.filter(p => p.review_status === "pending" && p.proposed_destination === dest).map(p => p.id);
  if (!ids.length) return;
  if (!confirm(`Opravdu přesunout všech ${ids.length} položek (${TRIAGE_DEST_LABELS[dest] || dest}) do další dávky?`)) return;
  await Promise.all(ids.map(id => fetch(`/api/admin/support/triage-proposals/${id}/defer`, { method: "POST" })));
  loadSupportTriageRun();
}

// Robert 2026-08-22 ("u nejasných emailů přidej tlačítko smazat") -
// VYHRADNE u kategorie "jine" (Nejasne), kdyz admin vidi ze konverzace
// je jasne nepotrebna, ale zadna jina kategorie nesedi. Schvalit/
// Zamitnout u "jine" beze zmeny (poradnaji nic nedelaji, viz
// sameEffectNote vyse) - tohle je samostatna, nevratna akce (stejny
// potvrzovaci vzor jako supportTriageBlacklistDomain).
async function supportTriageDelete(proposalId) {
  if (!confirm("Opravdu trvale smazat tuto konverzaci? Nelze vrátit zpět!")) return;
  const r = await fetch(`/api/admin/support/triage-proposals/${proposalId}/delete`, { method: "POST" });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) { alert(data.error || "Nepodařilo se smazat konverzaci."); return; }
  loadSupportTriageRun();
  loadSupportConversations();
}
async function supportTriageBulkDelete(dest) {
  const run = await fetch("/api/admin/support/triage-runs/" + supportTriageRunId).then(r => r.json());
  const ids = run.proposals.filter(p => p.review_status === "pending" && p.proposed_destination === dest).map(p => p.id);
  if (!ids.length) return;
  if (!confirm(`Opravdu TRVALE SMAZAT všech ${ids.length} položek (${TRIAGE_DEST_LABELS[dest] || dest})? Nelze vrátit zpět!`)) return;
  await Promise.all(ids.map(id => fetch(`/api/admin/support/triage-proposals/${id}/delete`, { method: "POST" })));
  loadSupportTriageRun();
  loadSupportConversations();
}

// Vyber+nahled prilohy PRED schvalenim "doklad" navrhu (Robert,
// 2026-08-19: "Robert vizualne sam pozna, jestli je priloha skutecne
// faktura - appka/bot to spolehlive nepozna") - botuv invoice_
// attachment_filename je jen predvyplneny navrh, admin muze zvolit
// jinou prilohu nebo zadnou pred kliknutim na "Schválit".
// Robert 2026-08-22 ("u kazdeho radku videt, jestli ma konverzace
// prilohy a s jakymi nazvy") - lehka varianta pro VSECHNY destinace
// KROME "doklad" (ten uz ma plny interaktivni picker vyse se jmeny v
// radio tlacitkach - viz supportTriageLoadAttachments, beze zmeny).
// Skutecna data z shop_support_message_attachments (stejny endpoint
// jako doklad-picker), NE bota volny text attachment_note (ten muze
// byt nekonzistentni/chybejici - viz TASKS.md zadani). Kdyz konverzace
// nema zadnou prilohu, cely box se ODSTRANI (ne jen schova) - zadny
// prazdny ramecek.
async function supportTriageLoadAttachmentChips(proposalId) {
  const el = document.getElementById("triageAttachChips" + proposalId);
  if (!el) return;
  let attachments = [];
  try {
    const r = await fetch(`/api/admin/support/triage-proposals/${proposalId}/attachments`);
    const data = await r.json();
    attachments = data.attachments || [];
  } catch (e) { /* necháme prázdné - stejné jako "žádná příloha" */ }
  if (!attachments.length) { el.remove(); return; }
  el.innerHTML = attachments.map(a =>
    `<span class="triage-badge attach" title="${escapeHtmlTriage(a.content_type || "")}">📎 ${escapeHtmlTriage(a.filename)}</span>`
  ).join("");
}

async function supportTriageLoadAttachments(proposalId) {
  const el = document.getElementById("triageInvoicePicker" + proposalId);
  if (!el) return;
  const suggested = el.dataset.suggested || "";
  let attachments = [];
  try {
    const r = await fetch(`/api/admin/support/triage-proposals/${proposalId}/attachments`);
    const data = await r.json();
    attachments = data.attachments || [];
  } catch (e) { /* necháme prázdné, admin schválí bez souboru */ }
  if (!attachments.length) {
    el.innerHTML = '<span class="hint">Konverzace nemá žádné přílohy.</span>';
    return;
  }
  el.innerHTML = '<div class="hint" style="margin-bottom:4px;">Která příloha je faktura?</div>' +
    attachments.map(a => {
      const checked = a.filename === suggested ? "checked" : "";
      return `
        <label style="display:flex;align-items:center;gap:6px;margin-bottom:4px;">
          <input type="radio" name="triageInvoicePick${proposalId}" value="${escapeHtmlTriage(a.filename)}" ${checked}
            onchange="supportTriageShowAttachmentPreview(${proposalId}, '${a.filename.replace(/'/g, "\\'")}', '${(a.content_type || "").replace(/'/g, "\\'")}')">
          <span>${escapeHtmlTriage(a.filename)}</span>
        </label>`;
    }).join("") +
    `<label style="display:flex;align-items:center;gap:6px;margin-bottom:6px;">
      <input type="radio" name="triageInvoicePick${proposalId}" value="" ${suggested ? "" : "checked"}
        onchange="supportTriageShowAttachmentPreview(${proposalId}, '', '')">
      <span class="hint">Žádná (jen text e-mailu)</span>
    </label>
    <div id="triageInvoicePreview${proposalId}"></div>`;
  if (suggested) {
    const match = attachments.find(a => a.filename === suggested);
    if (match) supportTriageShowAttachmentPreview(proposalId, suggested, match.content_type || "");
  }
}

function supportTriageShowAttachmentPreview(proposalId, filename, contentType) {
  const previewEl = document.getElementById("triageInvoicePreview" + proposalId);
  if (!previewEl) return;
  if (!filename) { previewEl.innerHTML = ""; return; }
  const url = `/api/admin/support/triage-proposals/${proposalId}/attachment-preview/${encodeURIComponent(filename)}`;
  if ((contentType || "").startsWith("image/")) {
    previewEl.innerHTML = `<img src="${url}" style="max-width:280px;max-height:280px;border:1px solid var(--border-soft);border-radius:6px;margin-top:4px;">`;
  } else if (contentType === "application/pdf") {
    previewEl.innerHTML = `<embed src="${url}" type="application/pdf" style="width:280px;height:360px;border:1px solid var(--border-soft);border-radius:6px;margin-top:4px;">`;
  } else {
    previewEl.innerHTML = `<a href="${url}" target="_blank" rel="noopener" class="hint">Náhled souboru (${escapeHtmlTriage(contentType || "neznámý typ")})</a>`;
  }
}

function supportTriageSelectedInvoiceFilename(proposalId) {
  const checked = document.querySelector(`input[name="triageInvoicePick${proposalId}"]:checked`);
  return checked ? (checked.value || null) : undefined;
}

// Rucni prirazeni ke konkretni existujici poptavce (Robert 2026-08-22,
// WORKFLOW.md bod 17 - "bot to nemusi zvladnout rozeznat", admin musi
// mit vzdy moznost rucniho prepsani automatickeho rozpoznani pres
// Message-ID/predmet/e-mail). Zivy vyhledavaci naseptavac nad GET
// /api/admin/crm/leads (server-side hledani, ne in-memory cache jako
// wireProductSuggest - poptavek muze byt hodne a nejsou nikde
// kompletne preloadovane), stejne vizualni tridy (.product-suggestions/
// .ps-row/.ps-empty) jako existujici produktovy naseptavac pro
// konzistenci beze zavedeni nove CSS.
const supportTriageLeadPick = {}; // proposalId (string) -> {id, contact_name, company_name, subject}

function supportTriageLeadPickedHtml(lead) {
  const label = escapeHtmlTriage(lead.contact_name || lead.contact_email || ("#" + lead.id))
    + (lead.company_name ? ` (${escapeHtmlTriage(lead.company_name)})` : "")
    + (lead.subject ? " — " + escapeHtmlTriage(lead.subject) : "");
  return `✅ Přiřadí se k poptávce: <strong>${label}</strong> `
    + `<a href="#" onclick="supportTriageLeadClear(event, '${lead._proposalId}')" style="color:var(--error);">(zrušit výběr)</a>`;
}

function supportTriageLeadClear(e, proposalId) {
  e.preventDefault();
  delete supportTriageLeadPick[proposalId];
  const el = document.getElementById("triageLeadPicked" + proposalId);
  if (el) el.innerHTML = "";
}

function wireTriageLeadPicker(proposalId) {
  const input = document.getElementById("triageLeadSearch" + proposalId);
  const box = document.getElementById("triageLeadSuggest" + proposalId);
  const pickedEl = document.getElementById("triageLeadPicked" + proposalId);
  if (!input || !box) return;
  let debounceTimer = null;
  input.addEventListener("input", () => {
    clearTimeout(debounceTimer);
    const q = input.value.trim();
    if (!q) { box.classList.remove("open"); box.innerHTML = ""; return; }
    debounceTimer = setTimeout(async () => {
      let leads = [];
      try {
        const r = await fetch(`/api/admin/crm/leads?q=${encodeURIComponent(q)}&archived=0&page_size=15`);
        const data = await r.json().catch(() => ({}));
        leads = data.leads || [];
      } catch (e) { /* necháme prázdné, admin zkusí znovu */ }
      box.innerHTML = leads.length
        ? leads.map(l => `
            <div class="ps-row" data-id="${l.id}">
              ${escapeHtmlTriage(l.contact_name || l.contact_email || ("#" + l.id))}
              ${l.company_name ? ` <span class="ps-sku">(${escapeHtmlTriage(l.company_name)})</span>` : ""}
              ${l.subject ? " — " + escapeHtmlTriage(l.subject) : ""}
            </div>`).join("")
        : '<div class="ps-empty">Žádná aktivní poptávka neodpovídá hledání.</div>';
      box.querySelectorAll(".ps-row").forEach(row => {
        row.onclick = () => {
          const lead = leads.find(l => l.id === parseInt(row.dataset.id, 10));
          lead._proposalId = proposalId;
          supportTriageLeadPick[proposalId] = lead;
          pickedEl.innerHTML = supportTriageLeadPickedHtml(lead);
          input.value = "";
          box.classList.remove("open");
          box.innerHTML = "";
        };
      });
      box.classList.add("open");
    }, 250);
  });
  input.addEventListener("blur", () => setTimeout(() => box.classList.remove("open"), 150));
}

async function loadSupportTriageRun() {
  if (!supportTriageRunId) return;
  const r = await fetch("/api/admin/support/triage-runs/" + supportTriageRunId);
  if (!r.ok) return;
  const run = await r.json();
  renderSupportTriageBody(run);
  if (run.status !== "pending" && supportTriagePollTimer) {
    clearInterval(supportTriagePollTimer);
    supportTriagePollTimer = null;
  }
}

function openSupportTriageModal(runId) {
  supportTriageRunId = runId;
  document.getElementById("supportTriageModal").classList.add("open");
  loadSupportTriageRun();
  clearInterval(supportTriagePollTimer);
  supportTriagePollTimer = setInterval(loadSupportTriageRun, 4000);
}

document.getElementById("supportTriageBtn").onclick = async () => {
  // Nejdriv zkontrolovat, jestli uz nejaky beh nebezi/neceka na review
  // (misto zalozeni duplicitniho pri opakovanem kliku).
  const existing = await fetch("/api/admin/support/triage-runs").then(r => r.json()).catch(() => ({}));
  if (existing.run) { openSupportTriageModal(existing.run.id); return; }
  const r = await fetch("/api/admin/support/triage-runs", { method: "POST" });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) { alert(data.error || "Zadání se nezdařilo."); return; }
  openSupportTriageModal(data.id);
};
document.getElementById("supportTriageClose").onclick = () => {
  document.getElementById("supportTriageModal").classList.remove("open");
  clearInterval(supportTriagePollTimer);
  supportTriagePollTimer = null;
};
async function supportTriageReview(proposalId, approved) {
  const payload = { approved };
  // U "doklad" radku posli VYBRANOU prilohu (admin ji mohl zmenit
  // oproti botovu navrhu, nebo zvolit "zadna") - viz
  // supportTriageLoadAttachments/supportTriageSelectedInvoiceFilename.
  const selected = supportTriageSelectedInvoiceFilename(proposalId);
  if (selected !== undefined) payload.invoice_attachment_filename = selected;
  // U "crm" radku posli RUCNE vybranou poptavku, pokud admin nejakou
  // vybral (misto spolehnuti na automaticke rozpoznani) - viz
  // wireTriageLeadPicker/WORKFLOW.md bod 17.
  const pickedLead = supportTriageLeadPick[proposalId];
  if (pickedLead) payload.lead_id = pickedLead.id;
  const r = await fetch("/api/admin/support/triage-proposals/" + proposalId, {
    method: "PUT", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!r.ok) {
    const data = await r.json().catch(() => ({}));
    alert(data.error || "Akce se nezdařila.");
    return;
  }
  delete supportTriageLeadPick[proposalId];
  loadSupportTriageRun();
  // Schvaleni "spam"/"crm" navrhu rovnou smaze/presune konverzaci (viz
  // api/support.py support_triage_proposal_review) - obnov i hlavni
  // tabulku, jinak by tam smazany/presunuty radek zustal do rucniho
  // refreshe.
  loadSupportConversations();
}

document.getElementById("supportSearchApply").onclick = () => {
  supportFilter.q = document.getElementById("supportSearchQ").value.trim();
  supportFilter.source = document.getElementById("supportFilterSource").value;
  supportFilter.date_from = document.getElementById("supportFilterDateFrom").value;
  supportFilter.date_to = document.getElementById("supportFilterDateTo").value;
  supportFilter.unread_only = document.getElementById("supportFilterUnreadOnly").checked;
  supportFilter.sort = document.getElementById("supportFilterSort").value;
  supportFilter.page = 1;
  loadSupportConversations();
};
document.getElementById("supportSearchReset").onclick = () => {
  document.getElementById("supportSearchQ").value = "";
  document.getElementById("supportFilterSource").value = "";
  document.getElementById("supportFilterDatePreset").value = "";
  document.getElementById("supportFilterDateFrom").value = "";
  document.getElementById("supportFilterDateTo").value = "";
  document.getElementById("supportFilterUnreadOnly").checked = false;
  document.getElementById("supportFilterSort").value = "newest";
  supportFilter = { status: supportFilter.status, q: "", source: "", date_from: "", date_to: "", unread_only: false, sort: "newest",
    archived: supportFilter.archived, page: 1, page_size: supportFilter.page_size };
  loadSupportConversations();
};
document.getElementById("supportSearchQ").addEventListener("keydown", (e) => {
  if (e.key === "Enter") { e.preventDefault(); document.getElementById("supportSearchApply").click(); }
});

async function deleteSupportConversation() {
  if (!supportModalConvId) return;
  if (!confirm("Opravdu smazat celou konverzaci včetně všech zpráv? Tuto akci nelze vzít zpět.")) return;
  try {
    const r = await fetch(`/api/admin/support/conversations/${supportModalConvId}`, { method: "DELETE" });
    if (!r.ok) throw new Error("HTTP " + r.status);
    closeSupportModal();
    loadSupportConversations();
  } catch (e) {
    alert("Smazání se nezdařilo: " + e.message);
  }
}

async function resolveSupportConversation() {
  if (!supportModalConvId) return;
  const btn = document.getElementById("btnSupportModalResolve");
  btn.disabled = true;
  try {
    const r = await fetch(`/api/admin/support/conversations/${supportModalConvId}/close`, { method: "POST" });
    if (!r.ok) throw new Error("HTTP " + r.status);
    closeSupportModal();
    loadSupportConversations();
  } catch (e) {
    alert("Uzavření se nezdařilo: " + e.message);
  } finally {
    btn.disabled = false;
  }
}

// Normalizace bilych znaku v tele zpravy (Robert 2026-08-06, screenshot
// "prijata posta je rozbita"): plain-text verze tabulkovych e-mailu
// (objednavky apod.) obsahuje stovky mezer/prazdnych radku pro
// "zarovnani sloupcu" - bublina se white-space:pre-wrap je zobrazi
// doslova a text se rozstrika po cele plose. Sjednoti se: radky jen
// z mezer -> prazdne, 3+ mezer/tabu za sebou -> 2 mezery (oddeleni
// "bunek" zustane citelne), 3+ prazdnych radku -> 1. Bezne rucne psane
// zpravy tohle nikdy nezasahne (nemaji takove runy).
function normalizeEmailBody(s) {
  let t = String(s == null ? "" : s)
    .replace(/\r/g, "")
    // NBSP a dalsi unicode mezery (tabulkove e-maily je pouzivaji pro
    // "zarovnani bunek" - prave ty prezily prvni verzi normalizace)
    .replace(/[\u00A0\u2000-\u200B\u202F\u205F\u3000]/g, " ");
  // Outlook/Exchange plain-text export artefakty (Robert, TASKS.md
  // "CRM/Podpora - [Image]/[cid:...] artefakty", zpr\u00E1vy BEZ body_html -
  // ty s HTML \u010D\u00E1st\u00ED \u0159e\u0161\u00ED cleanEmailHtmlImages() jinde): e-mail bez
  // text/html \u010D\u00E1sti nem\u00E1 jak vlo\u017Een\u00FD obr\u00E1zek podpisu vyj\u00E1d\u0159it jinak ne\u017E
  // hol\u00FDm "[Image]" nebo "[cid:<content-id>]" - ani jeden nejde nikdy
  // dohledat na skute\u010Dn\u00FD obr\u00E1zek (\u017E\u00E1dn\u00E1 inline-p\u0159\u00EDloha infrastruktura),
  // tak\u017Ee se sma\u017Eou. Podobn\u011B "text<url>" - Outlook p\u0159ipoj\u00ED syrovou URL
  // v <> hned za viditeln\u00FD text odkazu/e-mailu (\u010Dasto je\u0161t\u011B jednou
  // zdvojen\u00E9 " <url>" za sebou) - viditeln\u00FD text s\u00E1m nese informaci,
  // <...> anotace jde smazat beze ztr\u00E1ty \u010Ditelnosti.
  t = t.replace(/\[(?:cid:[^\]]*|Image)\]/gi, "");
  t = t.replace(/<(?:https?:\/\/|mailto:)[^>\s]*>/gi, "");
  // kazdy radek: pryc odsazeni zleva/zprava, vnitrni runy mezer -> 1
  t = t.split("\n").map(l => l.trim().replace(/[ \t]{2,}/g, " ")).join("\n");
  // max 1 prazdny radek za sebou
  t = t.replace(/\n{3,}/g, "\n\n");
  // "Popisek:" na samostatnem radku + hodnota pod nim -> jeden radek
  // ("Jméno:\nJiří Michálek" -> "Jméno: Jiří Michálek") - smrskne
  // typicke objednavkove e-maily na polovinu (Robert: "vnitrni
  // strukturu nejak smrsknout")
  t = t.replace(/^(.{1,60}:)\n+(?=[^\s])/gm, "$1 ");
  // Uplne bez prazdnych radku (Robert 2026-08-06, 3. kolo: polozky se
  // vejdou na obrazovku naraz) - kazdy udaj = jeden radek pod sebou.
  return t.replace(/\n{2,}/g, "\n").trim();
}

// stickToBottom (Robert 2026-08-06, "roluje se to samo porad dole"):
// puvodne se log.scrollTop nastavoval na scrollHeight PRI KAZDEM pollu
// (kazde 3s), takze kdyz si admin odscrolloval nahoru precist starou
// zpravu, poll ho za 3s neprosbne strhl zpatky dolu. Ted se to deje jen
// pokud uz byl (skoro) na dne PRED prekreslenim - stejny vzor jako
// bezne chatovaci UI (drz se dna, dokud si uzivatel sam neodscrolluje).
// Prvni nacteni vlakna (log.dataset.everLoaded jeste neni "1", nastavuje
// se v open*Modal pri otevreni NOVE konverzace) vzdy sjede na konec.
// hydrateHtmlMessageBubbles (Robert 2026-08-06, "dejme tomu nejaky format
// tabulky"): u zprav s HTML verzi (m.body_html - jen prichozi e-maily s
// text/html castou, viz api/support_email_sync.py) se misto rozstrikaneho
// plain textu zobrazi skutecna HTML tabulka z originalu. Iframe se
// vytvari pres DOM API a `.srcdoc =` (JS vlastnost, ne HTML atribut) -
// obsah e-mailu tak NIKDY neprochazi HTML-atributovym escapovanim/
// parsovanim v RODICOVSKE strance, takze nehrozi zadny XSS unik ven z
// iframu bez ohledu na to, co e-mail obsahuje.
// `sandbox="allow-same-origin"` BEZ "allow-scripts" je zamerne: contentDocument
// zustava citelny z rodice (potreba pro automaticke dopocitani vysky
// nize), ale JAKYKOLI <script>/onerror/... z e-mailu se NIKDY nespusti -
// sandbox bez allow-scripts skriptovani v ramci iframu kompletne blokuje
// na urovni prohlizece, bez ohledu na obsah. Zamerne se NEfiltruji
// externi obrazky (napr. sledovaci pixely) - jde o transakcni e-maily
// vlastniho obchodu/zakaznickou komunikaci, ne hromadny marketing, a
// produktove obrazky v objednavce maji hodnotu pro citelnost.
//
// cleanEmailHtmlImages (Robert, 2026-08-22, pres bot3 - poptavkovy
// e-mail v CRM modalu vypadal "rozbity"): vlaknove odpovedi (Outlook/
// Gmail) pri KAZDE urovni citace znovu vlozi CELOU historii vc.
// podpisu - stejny obrazek (logo/podpis) se tak v jednom body_html
// opakuje 6-7x. `cid:...` odkazy (vlozene/inline prilohy, Content-ID)
// se navic v tomhle sandboxovanem iframu NIKDY nevyresi (zadny
// Content-ID resolver, appka inline prilohy e-mailu vubec neuklada -
// _extract_attachments v api/support_email_sync.py zachytava jen
// Content-Disposition: attachment, ne inline) - bez uprav by se
// zobrazilo 6-7 rozbitych placeholderu za sebou. Reseno pri RENDERU
// (ne pri ukladani/synchronizaci) - opravuje se tim rovnou CELA
// existujici historie, ne jen nove prichozi e-maily, bez nutnosti
// zpetne migrace ulozenych dat.
function cleanEmailHtmlImages(html) {
  const seenSrc = new Set();
  return html.replace(/<img\b[^>]*>/gi, (tag) => {
    const srcMatch = tag.match(/\bsrc\s*=\s*(["'])(.*?)\1/i);
    const key = srcMatch ? srcMatch[2].trim().toLowerCase() : "";
    if (key && seenSrc.has(key)) return ""; // opakovany stejny obrazek z vnorene citace
    if (key) seenSrc.add(key);
    if (key.startsWith("cid:")) {
      // vlozena priloha bez ulozeneho zdroje - nikdy nejde vyresit,
      // misto rozbiteho placeholderu jen nenapadna znacka
      return '<span style="display:inline-block;opacity:.5;font-size:11px;font-style:italic;">[obrázek z e-mailu]</span>';
    }
    return tag;
  });
}

function hydrateHtmlMessageBubbles(log, messages) {
  log.querySelectorAll("[data-html-msg-id]").forEach(el => {
    const id = Number(el.dataset.htmlMsgId);
    const m = (messages || []).find(x => x.id === id);
    if (!m || !m.body_html) return;
    const box = el.querySelector(".support-msg-htmlbox");
    if (!box) return;
    const iframe = document.createElement("iframe");
    iframe.sandbox = "allow-same-origin";
    iframe.scrolling = "no";
    iframe.className = "support-msg-iframe";
    iframe.style.height = "60px";
    iframe.addEventListener("load", () => {
      try {
        const h = iframe.contentDocument.documentElement.scrollHeight;
        iframe.style.height = Math.min(Math.max(h + 6, 40), 2400) + "px";
      } catch (e) { /* sandbox/cross-origin - necha vychozi vysku */ }
    });
    box.appendChild(iframe);
    iframe.srcdoc = cleanEmailHtmlImages(m.body_html);
  });
}

// stickToBottom (Robert 2026-08-06, "roluje se to samo porad dole"):
// puvodne se log.scrollTop nastavoval na scrollHeight PRI KAZDEM pollu
// (kazde 3s), takze kdyz si admin odscrolloval nahoru precist starou
// zpravu, poll ho za 3s neprosbne strhl zpatky dolu. Ted se to deje jen
// pokud uz byl (skoro) na dne PRED prekreslenim - stejny vzor jako
// bezne chatovaci UI (drz se dna, dokud si uzivatel sam neodscrolluje).
// Prvni nacteni vlakna (log.dataset.everLoaded jeste neni "1", nastavuje
// se v open*Modal pri otevreni NOVE konverzace) vzdy sjede na konec.
//
// sig (Robert 2026-08-06, soucasne s HTML tabulkami vyse): pokud se sada
// zprav od posledniho pollu vubec nezmenila (stejna id ve stejnem
// poradi - zpravy se v tehle appce nikdy needituji), cele prekresleni se
// PRESKOCI. Bez tohohle by kazdy 3s poll znovunacetl VSECHNY <iframe>
// (i beze zmeny obsahu), coz by kazde 3s vizualne "blyklo".
function supportRenderModalLog(messages) {
  const log = document.getElementById("supportModalLog");
  const sig = (messages || []).map(m => m.id).join(",");
  if (log.dataset.everLoaded === "1" && log.dataset.sig === sig) return;
  const stick = log.dataset.everLoaded !== "1" || (log.scrollHeight - log.scrollTop - log.clientHeight) < 40;
  log.innerHTML = (messages || []).map(m => {
    const cls = m.sender_type === "customer" ? "customer" : (m.sender_type === "ai" ? "ai" : "operator");
    const who = m.sender_type === "ai" ? "🤖 3Dbot (AI)" : (m.sender_type === "operator" ? (m.sender_name || "Operátor") : (m.sender_name || "Zákazník"));
    const meta = `<span class="support-msg-meta">${escapeHtmlAdmin(who)} · ${supportFmtTime(m.created_at)}</span>`;
    if (m.body_html) {
      return `<div class="support-msg ${cls} html-msg" data-html-msg-id="${m.id}"><div class="support-msg-htmlbox"></div>${meta}</div>`;
    }
    const esc = normalizeEmailBody(m.body).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    return `<div class="support-msg ${cls}">${esc}${meta}</div>`;
  }).join("");
  hydrateHtmlMessageBubbles(log, messages);
  log.dataset.everLoaded = "1";
  log.dataset.sig = sig;
  if (stick) log.scrollTop = log.scrollHeight;
}

async function loadSupportModalThread() {
  if (!supportModalConvId) return;
  // bot23 2026-08-18: race condition mezi 3s pollingem a rychlym
  // prepnutim konverzace - starsi (pomalejsi) fetch muze dorazit
  // POZDEJI nez fetch pro NOVE otevrenou konverzaci a prepsat modal
  // cizimi daty. reqId zachyti, pro kterou konverzaci tenhle fetch
  // vlastne byl - po navratu se overi, ze se mezitim nezmenila.
  const reqId = supportModalConvId;
  try {
    const r = await fetch(`/api/admin/support/conversations/${reqId}/messages`);
    if (reqId !== supportModalConvId) return;
    if (!r.ok) throw new Error("HTTP " + r.status);
    const data = await r.json();
    if (reqId !== supportModalConvId) return;
    document.getElementById("supportModalMeta").textContent =
      `${data.conversation.customer_name || data.conversation.customer_email} · ${data.conversation.customer_email || ""}`;
    // tlacitko archivace odrazi aktualni stav (bot23, 2026-08-17, stejny
    // vzor jako btnCrmModalArchive)
    supportModalConvArchived = !!data.conversation.archived;
    document.getElementById("btnSupportModalArchive").textContent =
      supportModalConvArchived ? "↩ Obnovit z archivu" : "🗄 Archivovat";
    supportRenderModalLog(data.messages);
    loadSupportConversations(true);
  } catch (e) {
    document.getElementById("supportModalMeta").textContent = "Chyba načtení: " + e.message;
  }
}

function openSupportModal(convId) {
  supportModalConvId = convId;
  document.getElementById("supportModalReply").value = "";
  delete document.getElementById("supportModalLog").dataset.everLoaded;
  document.getElementById("supportModal").classList.add("open");
  loadSupportModalThread();
  clearInterval(supportModalPollTimer);
  supportModalPollTimer = setInterval(loadSupportModalThread, 3000);
}

function closeSupportModal() {
  document.getElementById("supportModal").classList.remove("open");
  supportModalConvId = null;
  clearInterval(supportModalPollTimer);
}

async function sendSupportReply() {
  const body = document.getElementById("supportModalReply").value.trim();
  if (!body || !supportModalConvId) return;
  const btn = document.getElementById("btnSupportModalSend");
  btn.disabled = true;
  try {
    const r = await fetch(`/api/admin/support/conversations/${supportModalConvId}/reply`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ body }),
    });
    if (!r.ok) throw new Error("HTTP " + r.status);
    document.getElementById("supportModalReply").value = "";
    loadSupportModalThread();
  } catch (e) {
    alert("Chyba odeslání: " + e.message);
  } finally {
    btn.disabled = false;
  }
}

document.getElementById("btnSupportModalClose").onclick = closeSupportModal;
document.getElementById("btnSupportModalSend").onclick = sendSupportReply;
async function markSupportConversationAsLead() {
  if (!supportModalConvId) return;
  if (!confirm("Přesunout tuto konverzaci do Poptávek (CRM)? Zmizí ze záložky Emaily příchozí.")) return;
  const btn = document.getElementById("btnSupportModalMarkLead");
  btn.disabled = true;
  try {
    const r = await fetch(`/api/admin/support/conversations/${supportModalConvId}/mark-lead`, { method: "POST" });
    const data = await r.json();
    if (!r.ok) throw new Error(data.error || "HTTP " + r.status);
    closeSupportModal();
    loadSupportConversations();
  } catch (e) {
    alert("Přesun se nezdařil: " + e.message);
  } finally {
    btn.disabled = false;
  }
}

document.getElementById("btnSupportModalDelete").onclick = deleteSupportConversation;
document.getElementById("btnSupportModalMarkLead").onclick = markSupportConversationAsLead;
document.getElementById("btnSupportModalResolve").onclick = resolveSupportConversation;
document.getElementById("btnSupportModalArchive").onclick = async () => {
  if (!supportModalConvId) return;
  const r = await fetch(`/api/admin/support/conversations/${supportModalConvId}/archive`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ archived: !supportModalConvArchived }),
  });
  if (!r.ok) { alert("Archivace se nezdařila."); return; }
  closeSupportModal();
  loadSupportConversations();
};
document.getElementById("supportModalReply").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendSupportReply(); }
});
supportConvPollTimer = setInterval(() => loadSupportConversations(true), 6000);


