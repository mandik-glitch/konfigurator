// ==================== MINI-ESHOPY (car_storefronts) ====================
// bot14, 2026-08-29 (Robert pres toscanaccio-0b): "ruzne znacky/modely aut
// budou mit vlastni web s kosikem... nemelo by to mit vlastni administraci,
// ta by se ridila vice centralne". Zdroj dat: api/car_storefronts.py.
let sfItems = [];
let sfEditingId = null;
let sfCarMakesTree = null; // cache /api/car-makes-tree (nemeni se casto behem jedne navstevy)
let sfSelectedModelIds = new Set();

function loadStorefronts() {
  fetch("/api/admin/storefronts").then(r => r.ok ? r.json() : { storefronts: [] }).then(data => {
    sfItems = data.storefronts || [];
    renderStorefronts();
  });
}

function renderStorefronts() {
  document.getElementById("sfCount").textContent = `Počet webů: ${sfItems.length}`;
  const list = document.getElementById("sfList");
  if (!sfItems.length) {
    list.innerHTML = '<p class="hint">Zatím žádné mini-eshopy. Přidej první tlačítkem výše.</p>';
    return;
  }
  list.innerHTML = sfItems.map(s => `
    <div class="hpb-row" data-id="${s.id}">
      <div class="hpb-thumb" style="display:flex; align-items:center; justify-content:center;">${s.status === "live" ? "🟢" : "⚪"}</div>
      <div>
        <div class="hpb-row-title">${hpEscapeHtml(s.name)}${s.car_make_name ? " (" + hpEscapeHtml(s.car_make_name) + ")" : ""}</div>
        <div class="hpb-row-slug"><a href="https://${hpEscapeHtml(s.primary_domain)}" target="_blank" rel="noopener">${hpEscapeHtml(s.primary_domain)}</a> · ${s.model_count} variant · ${s.status === "live" ? "zveřejněno" : "rozpracováno"}</div>
      </div>
      <div class="hpb-row-actions">
        <button type="button" class="sf-edit" data-id="${s.id}">Upravit</button>
        <button type="button" class="sf-delete" data-id="${s.id}" style="background:none; border:1px solid #5a3a3a; color:#e07070;">Smazat</button>
      </div>
    </div>
  `).join("");
  list.querySelectorAll(".sf-edit").forEach(btn => {
    btn.onclick = () => openSfModal(sfItems.find(s => s.id === parseInt(btn.dataset.id, 10)));
  });
  list.querySelectorAll(".sf-delete").forEach(btn => {
    btn.onclick = () => {
      if (!confirm("Opravdu smazat tento mini-eshop? Doména přestane fungovat.")) return;
      fetch(`/api/admin/storefronts/${btn.dataset.id}`, { method: "DELETE" }).then(() => loadStorefronts());
    };
  });
}

function sfSlugify(s) {
  return (s || "").toLowerCase()
    .normalize("NFD").replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
}

function ensureCarMakesTree() {
  if (sfCarMakesTree) return Promise.resolve(sfCarMakesTree);
  return fetch("/api/car-makes-tree").then(r => r.json()).then(data => {
    sfCarMakesTree = data.tree || [];
    return sfCarMakesTree;
  });
}

function populateSfMakeSelect(selectedMakeId) {
  return ensureCarMakesTree().then(tree => {
    const sel = document.getElementById("sfMake");
    sel.innerHTML = '<option value="">- nevybráno -</option>' +
      tree.map(mk => `<option value="${mk.id}">${hpEscapeHtml(mk.name)}</option>`).join("");
    sel.value = selectedMakeId || "";
  });
}

function renderSfVariantPicker(makeId) {
  const box = document.getElementById("sfVariantPicker");
  if (!makeId) { box.innerHTML = '<p class="hint" style="margin:0;">Nejdřív vyber značku.</p>'; return; }
  ensureCarMakesTree().then(tree => {
    const make = tree.find(mk => mk.id === parseInt(makeId, 10));
    if (!make || !make.models.length) { box.innerHTML = '<p class="hint" style="margin:0;">Tato značka nemá žádné modely.</p>'; return; }
    box.innerHTML = make.models.map(md => `
      <label>
        <input type="checkbox" class="sf-vp-check" value="${md.id}" ${sfSelectedModelIds.has(md.id) ? "checked" : ""}>
        ${hpEscapeHtml(md.name)}
      </label>
    `).join("");
    box.querySelectorAll(".sf-vp-check").forEach(cb => {
      cb.onchange = () => {
        const id = parseInt(cb.value, 10);
        if (cb.checked) sfSelectedModelIds.add(id); else sfSelectedModelIds.delete(id);
      };
    });
  });
}

function openSfModal(item) {
  sfEditingId = item ? item.id : null;
  document.getElementById("sfModalTitle").textContent = item ? "Upravit mini-eshop" : "Přidat mini-eshop";
  document.getElementById("sfName").value = item ? item.name : "";
  document.getElementById("sfSlug").value = item ? item.slug : "";
  document.getElementById("sfDomain").value = item ? item.primary_domain : "";
  document.getElementById("sfStatus").value = item ? item.status : "draft";
  document.getElementById("sfTemplate").value = (item && item.template_id) || "default";
  document.getElementById("sfHeroTitleInput").value = (item && item.hero_title) || "";
  document.getElementById("sfHeroText").value = (item && item.hero_text) || "";
  document.getElementById("sfMetaTitle").value = (item && item.meta_title) || "";
  document.getElementById("sfMetaDescription").value = (item && item.meta_description) || "";
  document.getElementById("sfModalErr").textContent = "";
  sfSelectedModelIds = new Set();

  populateSfMakeSelect(item ? item.car_make_id : "");

  if (item) {
    // Nacti aktualne navazane varianty (GET vraci i car_make_id/model_id
    // detaily, viz api/car_storefronts.py::admin_storefronts_get).
    fetch(`/api/admin/storefronts/${item.id}`).then(r => r.ok ? r.json() : null).then(data => {
      if (!data) return;
      (data.models || []).forEach(m => sfSelectedModelIds.add(m.id));
      renderSfVariantPicker(item.car_make_id);
    });
  } else {
    document.getElementById("sfVariantPicker").innerHTML = '<p class="hint" style="margin:0;">Nejdřív vyber značku.</p>';
  }

  document.getElementById("sfModal").classList.add("open");
}
function closeSfModal() {
  document.getElementById("sfModal").classList.remove("open");
}
document.getElementById("btnAddStorefront").onclick = () => openSfModal(null);
document.getElementById("sfModalClose").onclick = closeSfModal;
document.getElementById("sfCancel").onclick = closeSfModal;
document.getElementById("sfName").addEventListener("input", () => {
  if (!sfEditingId) document.getElementById("sfSlug").value = sfSlugify(document.getElementById("sfName").value);
});
document.getElementById("sfMake").onchange = () => {
  renderSfVariantPicker(document.getElementById("sfMake").value);
};
document.getElementById("sfSave").onclick = async () => {
  const errEl = document.getElementById("sfModalErr");
  errEl.textContent = "";
  const name = document.getElementById("sfName").value.trim();
  const domain = document.getElementById("sfDomain").value.trim();
  if (!name) { errEl.textContent = "Chybí název."; return; }
  if (!domain) { errEl.textContent = "Chybí doména."; return; }
  const payload = {
    name,
    slug: document.getElementById("sfSlug").value.trim() || sfSlugify(name),
    primary_domain: domain,
    car_make_id: document.getElementById("sfMake").value ? parseInt(document.getElementById("sfMake").value, 10) : null,
    template_id: document.getElementById("sfTemplate").value,
    status: document.getElementById("sfStatus").value,
    hero_title: document.getElementById("sfHeroTitleInput").value.trim() || null,
    hero_text: document.getElementById("sfHeroText").value.trim() || null,
    meta_title: document.getElementById("sfMetaTitle").value.trim() || null,
    meta_description: document.getElementById("sfMetaDescription").value.trim() || null,
  };
  try {
    let itemId = sfEditingId;
    let r, data;
    if (itemId) {
      r = await fetch(`/api/admin/storefronts/${itemId}`, {
        method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
      });
      data = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(data.error || ("HTTP " + r.status));
    } else {
      r = await fetch("/api/admin/storefronts", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
      });
      data = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(data.error || ("HTTP " + r.status));
      itemId = data.id;
      sfEditingId = itemId;
    }
    const modelsR = await fetch(`/api/admin/storefronts/${itemId}/models`, {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ car_model_ids: [...sfSelectedModelIds] }),
    });
    const modelsData = await modelsR.json().catch(() => ({}));
    if (!modelsR.ok) throw new Error(modelsData.error || ("HTTP " + modelsR.status));
    closeSfModal();
    loadStorefronts();
  } catch (e) {
    errEl.textContent = "Chyba: " + e.message;
  }
};
