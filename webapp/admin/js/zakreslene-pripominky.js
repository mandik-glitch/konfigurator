// ==================== ZAKRESLENÉ PŘIPOMÍNKY (product_markups) ====================
// bot14, 2026-09-02 (Robert pres bot3/toscanaccio-0b) - viz api/product_markups.py.
// v2 (2026-09-02): 1 pripominka = 1..N pohledu (submission_id), karta =
// cely submission, ne jednotlivy pohled - viz admin_product_markups_list().
const PM_STATUS_LABELS = { new: "Nové", in_progress: "Řeší se", done: "Vyřízeno" };

function loadProductMarkups() {
  const status = document.getElementById("pmStatusFilter").value;
  const url = "/api/admin/product-markups" + (status ? ("?status=" + encodeURIComponent(status)) : "");
  fetch(url).then(r => r.ok ? r.json() : { items: [] }).then(data => {
    renderProductMarkups(data.items || []);
  }).catch(() => {
    document.getElementById("pmErr").textContent = "Nepodařilo se načíst připomínky.";
  });
}
document.getElementById("pmStatusFilter").onchange = loadProductMarkups;

// Base64url (bez paddingu) - domluveno s bot16 pro odkaz do scény
// (webapp/scene.html?product=<id>&view=<base64url(JSON)>).
function pmBase64UrlEncode(obj) {
  const json = JSON.stringify(obj);
  const b64 = btoa(unescape(encodeURIComponent(json)));
  return b64.replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function renderProductMarkups(items) {
  document.getElementById("pmCount").textContent = "Počet: " + items.length;
  const list = document.getElementById("pmList");
  if (!items.length) {
    list.innerHTML = '<p class="hint">Zatím žádné zakreslené připomínky.</p>';
    return;
  }
  list.innerHTML = items.map(sub => {
    const productUrl = sub.product_slug ? `/produkt/${sub.product_slug}` : `/product.html?id=${sub.product_id}`;
    const leadLink = sub.lead_id
      ? `<a href="#" onclick="document.querySelector('.tab-btn[data-tab=crm]').click(); return false;">CRM #${sub.lead_id}</a>`
      : "–";
    const viewsHtml = sub.views.map(v => {
      const fileUrl = `/api/admin/product-markups/${v.id}/file`;
      const kind = v.view_json && v.view_json.kind;
      let sceneBtn = "";
      if (kind === "turntable" || kind === "3d") {
        // "product=" (ne "assembly=") - v2 admin data maji po ruce
        // shop_products.id, ne product_assemblies.id; scene.html podle
        // domluvy s bot16 umi dohledat sestavu i tak (product_assemblies.
        // shop_product_id, 1:1).
        const sceneUrl = `/scene.html?product=${sub.product_id}&view=${pmBase64UrlEncode(v.view_json)}`;
        sceneBtn = `<a href="${sceneUrl}" target="_blank" class="pm-scene-btn">Otevřít ve scéně v tomto pohledu</a>`;
      }
      return `<div class="pm-view">
        <img src="${fileUrl}" alt="" style="width:90px; height:66px; object-fit:cover; border-radius:4px; cursor:pointer;" onclick="openImgLightbox('${fileUrl}', false)">
        <div class="pm-view-label">${escapeHtmlAdmin(v.view_label)}</div>
        ${sceneBtn}
      </div>`;
    }).join("");
    return `<div class="pm-card" data-submission="${sub.submission_id}" style="border:1px solid #3a3f4a; border-radius:8px; padding:12px; margin-bottom:10px;">
      <div style="display:flex; justify-content:space-between; gap:12px; flex-wrap:wrap;">
        <div>
          <a href="${productUrl}" target="_blank"><strong>${escapeHtmlAdmin(sub.product_name)}</strong></a> · ${leadLink}
          <div class="hint">${escapeHtmlAdmin(sub.contact_email)}${sub.contact_phone ? " · " + escapeHtmlAdmin(sub.contact_phone) : ""} · ${new Date(sub.created_at).toLocaleString("cs-CZ")}</div>
        </div>
        <select class="pm-status-select" data-submission="${sub.submission_id}">
          ${Object.entries(PM_STATUS_LABELS).map(([k, v]) => `<option value="${k}" ${k === sub.status ? "selected" : ""}>${v}</option>`).join("")}
        </select>
      </div>
      <p style="white-space:pre-wrap;">${escapeHtmlAdmin(sub.note)}</p>
      <div style="display:flex; gap:12px; flex-wrap:wrap;">${viewsHtml}</div>
    </div>`;
  }).join("");
  list.querySelectorAll(".pm-status-select").forEach(sel => {
    sel.onchange = () => {
      const sid = sel.dataset.submission;
      fetch(`/api/admin/product-markups/submission/${sid}`, {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: sel.value }),
      }).then(r => r.ok ? r.json() : Promise.reject()).catch(() => {
        document.getElementById("pmErr").textContent = "Uložení stavu selhalo.";
      });
    };
  });
}
