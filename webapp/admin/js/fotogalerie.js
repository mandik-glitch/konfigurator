// ==================== FOTOGALERIE ====================
// Robert: "udelej sekce fotogalerie, systemove at se pohodlne nahravaji
// hromadne obrazky, at se jim z hlediska SEO davaji vhodne nazvy, cerpej
// z fotogalerii logiman.cz rovnou tam nacucni ty obrazky". Backend
// api/gallery.py - stejny vzor jako Doklady/E-maily (counts pro taby),
// navic inline editace popisku/kategorie primo v kartě a hromadny upload.
const GALLERY_CATEGORY_LABELS_ADMIN = {
  vestavby_dodavek: "Vestavby do dodávek",
  realizace_stolu: "Realizace stolů a pracovišť",
};
let galleryFilter = { category: "" };
let galleryCache = [];
let galleryShowArchived = false;

async function loadGallery() {
  const params = new URLSearchParams();
  if (galleryFilter.category) params.set("category", galleryFilter.category);
  if (galleryShowArchived) params.set("archived", "1");
  try {
    const r = await fetch(`/api/admin/gallery?${params.toString()}`);
    const data = await r.json();
    if (!r.ok) { document.getElementById("galleryErr").textContent = data.error || "Chyba."; return; }
    galleryCache = data.images || [];
    renderGalleryCategoryTabs(data.counts || {});
    renderGalleryGrid(galleryCache);
  } catch (e) {
    document.getElementById("galleryErr").textContent = "Nepodařilo se načíst fotogalerii.";
  }
}
document.getElementById("galleryShowArchivedBtn").onclick = () => {
  galleryShowArchived = !galleryShowArchived;
  const btn = document.getElementById("galleryShowArchivedBtn");
  btn.textContent = galleryShowArchived ? "Skrýt archivované" : "Zobrazit archivované";
  btn.style.background = galleryShowArchived ? "#3a5a7a" : "none";
  btn.style.color = galleryShowArchived ? "#fff" : "#c7ccd4";
  loadGallery();
};

function renderGalleryCategoryTabs(counts) {
  const all = (counts.vestavby_dodavek || 0) + (counts.realizace_stolu || 0);
  const defs = [
    { key: "", label: "Vše", count: all },
    { key: "vestavby_dodavek", label: GALLERY_CATEGORY_LABELS_ADMIN.vestavby_dodavek, count: counts.vestavby_dodavek || 0 },
    { key: "realizace_stolu", label: GALLERY_CATEGORY_LABELS_ADMIN.realizace_stolu, count: counts.realizace_stolu || 0 },
  ];
  const wrap = document.getElementById("galleryCategoryTabs");
  wrap.innerHTML = defs.map(d => {
    const active = galleryFilter.category === d.key;
    return `<button type="button" class="order-tab-btn${active ? " active" : ""}" data-key="${d.key}">${escapeHtmlAdmin(d.label)}<span class="otc">(${d.count})</span></button>`;
  }).join("");
  wrap.querySelectorAll(".order-tab-btn").forEach(btn => {
    btn.onclick = () => {
      galleryFilter.category = btn.dataset.key;
      loadGallery();
    };
  });
}

function renderGalleryGrid(images) {
  const grid = document.getElementById("galleryGrid");
  if (!images.length) {
    grid.innerHTML = '<p class="hint">Zatím žádné obrázky v této kategorii.</p>';
    return;
  }
  grid.innerHTML = images.map(img => `
    <div class="gallery-card${img.active ? "" : " inactive"}" data-id="${img.id}">
      <label style="position:relative;display:block;">
        <input type="checkbox" class="gc-select" data-id="${img.id}" ${gallerySelectedIds.has(img.id) ? "checked" : ""} style="position:absolute;top:6px;left:6px;width:18px;height:18px;z-index:2;">
        <img class="gc-thumb" src="${img.url}" alt="${escapeHtmlAdmin(img.alt_text || "")}" loading="lazy">
      </label>
      <div class="gc-body">
        <div class="gc-filename">${escapeHtmlAdmin(img.filename)}</div>
        <input type="text" class="gc-title" placeholder="Titulek" value="${escapeHtmlAdmin(img.title || "").replace(/"/g, "&quot;")}">
        <input type="text" class="gc-alt" placeholder="Alt text (SEO)" value="${escapeHtmlAdmin(img.alt_text || "").replace(/"/g, "&quot;")}">
        <select class="gc-category">
          <option value="vestavby_dodavek"${img.category === "vestavby_dodavek" ? " selected" : ""}>Vestavby do dodávek</option>
          <option value="realizace_stolu"${img.category === "realizace_stolu" ? " selected" : ""}>Realizace stolů</option>
        </select>
        <div class="gc-active-row">
          <label><input type="checkbox" class="gc-active"${img.active ? " checked" : ""}> Aktivní (zobrazeno veřejně)</label>
        </div>
        <div class="gc-actions">
          <button class="gc-save">Uložit</button>
          <button class="gc-up" style="background:none;border:1px solid #3a3f4a;color:#c7ccd4;">↑</button>
          <button class="gc-down" style="background:none;border:1px solid #3a3f4a;color:#c7ccd4;">↓</button>
          <button class="gc-delete danger">Smazat</button>
        </div>
      </div>
    </div>
  `).join("");

  grid.querySelectorAll(".gallery-card").forEach(card => {
    const id = parseInt(card.dataset.id, 10);
    card.querySelector(".gc-save").onclick = () => saveGalleryImage(id, card);
    card.querySelector(".gc-delete").onclick = () => deleteGalleryImage(id);
    card.querySelector(".gc-up").onclick = () => moveGalleryImage(id, -1);
    card.querySelector(".gc-down").onclick = () => moveGalleryImage(id, 1);
    card.querySelector(".gc-select").onchange = (e) => {
      if (e.target.checked) gallerySelectedIds.add(id); else gallerySelectedIds.delete(id);
      updateGalleryBulkToolbar();
    };
  });
  const visibleIds = new Set(images.map(i => i.id));
  [...gallerySelectedIds].forEach(id => { if (!visibleIds.has(id)) gallerySelectedIds.delete(id); });
  updateGalleryBulkToolbar();
}

let gallerySelectedIds = new Set();
function updateGalleryBulkToolbar() {
  const bar = document.getElementById("galleryBulkToolbar");
  const count = gallerySelectedIds.size;
  bar.classList.toggle("active", count > 0);
  document.getElementById("galleryBulkCount").textContent = `${count} vybráno`;
}
async function galleryBulkSetActive(active) {
  if (!gallerySelectedIds.size) return;
  const r = await fetch("/api/admin/gallery/bulk-visibility", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ids: [...gallerySelectedIds], active }),
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) { alert(data.error || "Chyba při ukládání."); return; }
  gallerySelectedIds.clear();
  loadGallery();
}
document.getElementById("galleryBulkActivate").onclick = () => galleryBulkSetActive(true);
document.getElementById("galleryBulkDeactivate").onclick = () => galleryBulkSetActive(false);
document.getElementById("galleryBulkDelete").onclick = async () => {
  if (!gallerySelectedIds.size) return;
  if (!confirm(`Opravdu smazat ${gallerySelectedIds.size} obrázků? Akci nelze vrátit zpět.`)) return;
  const r = await fetch("/api/admin/gallery/bulk-delete", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ids: [...gallerySelectedIds] }),
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) { alert(data.error || "Smazání se nezdařilo."); return; }
  gallerySelectedIds.clear();
  loadGallery();
};

async function saveGalleryImage(id, card) {
  const errEl = document.getElementById("galleryErr");
  errEl.textContent = "";
  const body = {
    title: card.querySelector(".gc-title").value.trim(),
    alt_text: card.querySelector(".gc-alt").value.trim(),
    category: card.querySelector(".gc-category").value,
    active: card.querySelector(".gc-active").checked,
  };
  try {
    const r = await fetch(`/api/admin/gallery/${id}`, {
      method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) { errEl.textContent = data.error || "Uložení se nezdařilo."; return; }
    loadGallery();
  } catch (e) {
    errEl.textContent = "Uložení se nezdařilo (chyba spojení).";
  }
}
async function deleteGalleryImage(id) {
  if (!confirm("Smazat tento obrázek? Akci nelze vrátit zpět.")) return;
  const errEl = document.getElementById("galleryErr");
  errEl.textContent = "";
  try {
    const r = await fetch(`/api/admin/gallery/${id}`, { method: "DELETE" });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) { errEl.textContent = data.error || "Smazání se nezdařilo."; return; }
    loadGallery();
  } catch (e) {
    errEl.textContent = "Smazání se nezdařilo (chyba spojení).";
  }
}
async function moveGalleryImage(id, direction) {
  // Prohodi sort_order se sousedem v ramci STEJNE kategorie (galleryCache
  // uz je serazena podle category, sort_order, id - viz backend).
  const img = galleryCache.find(g => g.id === id);
  if (!img) return;
  const sameCategory = galleryCache.filter(g => g.category === img.category);
  const idx = sameCategory.findIndex(g => g.id === id);
  const neighborIdx = idx + direction;
  if (neighborIdx < 0 || neighborIdx >= sameCategory.length) return;
  const neighbor = sameCategory[neighborIdx];
  try {
    await Promise.all([
      fetch(`/api/admin/gallery/${img.id}`, {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sort_order: neighbor.sort_order }),
      }),
      fetch(`/api/admin/gallery/${neighbor.id}`, {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sort_order: img.sort_order }),
      }),
    ]);
    loadGallery();
  } catch (e) {
    document.getElementById("galleryErr").textContent = "Přeřazení se nezdařilo (chyba spojení).";
  }
}

document.getElementById("galleryUploadBtn").onclick = async () => {
  const errEl = document.getElementById("galleryUploadErr");
  const statusEl = document.getElementById("galleryUploadStatus");
  errEl.textContent = "";
  statusEl.textContent = "";
  const filesInput = document.getElementById("galleryUploadFiles");
  const files = filesInput.files;
  if (!files || !files.length) { errEl.textContent = "Vyber alespoň jeden soubor."; return; }
  const fd = new FormData();
  fd.append("category", document.getElementById("galleryUploadCategory").value);
  for (const f of files) fd.append("files", f);
  statusEl.textContent = `Nahrávám ${files.length} souborů…`;
  try {
    const r = await fetch("/api/admin/gallery/upload", { method: "POST", body: fd });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) { errEl.textContent = data.error || "Nahrání se nezdařilo."; statusEl.textContent = ""; return; }
    statusEl.textContent = `Nahráno ${data.count} obrázků.`;
    filesInput.value = "";
    loadGallery();
  } catch (e) {
    errEl.textContent = "Nahrání se nezdařilo (chyba spojení).";
    statusEl.textContent = "";
  }
};
document.getElementById("galleryUrlBtn").onclick = async () => {
  const errEl = document.getElementById("galleryUrlErr");
  const statusEl = document.getElementById("galleryUrlStatus");
  errEl.textContent = "";
  statusEl.textContent = "";
  const urlInput = document.getElementById("galleryUrlInput");
  const url = urlInput.value.trim();
  if (!url) { errEl.textContent = "Zadej URL obrázku."; return; }
  const category = document.getElementById("galleryUrlCategory").value;
  const title = document.getElementById("galleryUrlTitle").value.trim();
  statusEl.textContent = "Stahuji obrázek…";
  try {
    const r = await fetch("/api/admin/gallery/import-url", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ category, url, title: title || undefined }),
    });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) { errEl.textContent = data.error || "Přidání se nezdařilo."; statusEl.textContent = ""; return; }
    statusEl.textContent = `Přidáno (${data.filename || data.id}).`;
    urlInput.value = "";
    document.getElementById("galleryUrlTitle").value = "";
    loadGallery();
  } catch (e) {
    errEl.textContent = "Přidání se nezdařilo (chyba spojení).";
    statusEl.textContent = "";
  }
};

// ==================== KNIHOVNA FOTEK (centrální obrazovka) ====================
// bot16, 2026-09-13 (Robert přímo: "rozdělení na 2 padá, aplikuj novou
// verzi fotogalerie") - viz komentář v api/gallery.py nad gallery_library_list
// pro celé pozadí. Na rozdíl od panelu výše (jen realizace_tag bucket pro
// /realizace.html) tohle je CELÁ content_photo_library: přiřazení do
// libovolného počtu e-shopových kategorií a jediné místo, odkud jde fotka
// trvale smazat (soubor i řádek), ne jen odebrat z jednoho místa.
let galleryLibCache = [];
let galleryLibCategoriesFlat = [];

document.getElementById("galleryModeRealizaceBtn").onclick = () => {
  document.getElementById("galleryModeRealizaceBtn").classList.add("active");
  document.getElementById("galleryModeLibraryBtn").classList.remove("active");
  document.getElementById("galleryRealizaceSection").style.display = "";
  document.getElementById("galleryLibrarySection").style.display = "none";
};
document.getElementById("galleryModeLibraryBtn").onclick = () => {
  document.getElementById("galleryModeLibraryBtn").classList.add("active");
  document.getElementById("galleryModeRealizaceBtn").classList.remove("active");
  document.getElementById("galleryRealizaceSection").style.display = "none";
  document.getElementById("galleryLibrarySection").style.display = "";
  if (!galleryLibCategoriesFlat.length) loadGalleryLibCategories();
  loadGalleryLibrary();
};

async function loadGalleryLibCategories() {
  try {
    const r = await fetch("/api/admin/categories/flat");
    const data = await r.json();
    if (!r.ok) return;
    galleryLibCategoriesFlat = (data.categories || []).slice().sort((a, b) => a.name.localeCompare(b.name, "cs"));
    const filterSel = document.getElementById("galleryLibCategoryFilter");
    filterSel.innerHTML = '<option value="">Všechny kategorie</option>' +
      galleryLibCategoriesFlat.map(c => `<option value="${c.id}">${escapeHtmlAdmin(c.name)}</option>`).join("");
  } catch (e) { /* filtr zůstane prázdný, nic kritického */ }
}

async function loadGalleryLibrary() {
  const errEl = document.getElementById("galleryLibErr");
  errEl.textContent = "";
  const params = new URLSearchParams();
  const q = document.getElementById("galleryLibSearch").value.trim();
  const catId = document.getElementById("galleryLibCategoryFilter").value;
  const unassigned = document.getElementById("galleryLibUnassignedOnly").checked;
  if (q) params.set("q", q);
  if (catId) params.set("category_id", catId);
  if (unassigned) params.set("unassigned", "1");
  try {
    const r = await fetch(`/api/admin/gallery/library?${params.toString()}`);
    const data = await r.json();
    if (!r.ok) { errEl.textContent = data.error || "Chyba."; return; }
    galleryLibCache = data.photos || [];
    renderGalleryLibGrid(galleryLibCache);
  } catch (e) {
    errEl.textContent = "Nepodařilo se načíst knihovnu.";
  }
}
document.getElementById("galleryLibSearchBtn").onclick = loadGalleryLibrary;
document.getElementById("galleryLibResetBtn").onclick = () => {
  document.getElementById("galleryLibSearch").value = "";
  document.getElementById("galleryLibCategoryFilter").value = "";
  document.getElementById("galleryLibUnassignedOnly").checked = false;
  loadGalleryLibrary();
};
document.getElementById("galleryLibSearch").addEventListener("keydown", (e) => {
  if (e.key === "Enter") loadGalleryLibrary();
});
document.getElementById("galleryLibCategoryFilter").onchange = loadGalleryLibrary;
document.getElementById("galleryLibUnassignedOnly").onchange = loadGalleryLibrary;

function renderGalleryLibGrid(photos) {
  const grid = document.getElementById("galleryLibGrid");
  if (!photos.length) {
    grid.innerHTML = '<p class="hint">Žádné fotky neodpovídají filtru.</p>';
    return;
  }
  const catOptions = galleryLibCategoriesFlat.map(c => `<option value="${c.id}">${escapeHtmlAdmin(c.name)}</option>`).join("");
  grid.innerHTML = photos.map(p => {
    const chips = (p.categories || []).map(c =>
      `<span class="gc-chip" data-cid="${c.id}" style="display:inline-flex;align-items:center;gap:3px;background:#2a3040;border:1px solid #3a3f4a;border-radius:10px;padding:2px 6px;font-size:11.5px;margin:2px 4px 2px 0;">${escapeHtmlAdmin(c.name)}<button type="button" class="gc-chip-x" title="Odebrat z kategorie" style="background:none;border:none;color:#c7ccd4;cursor:pointer;padding:0;line-height:1;">×</button></span>`
    ).join("") || '<span class="hint" style="font-size:11.5px;">bez kategorie</span>';
    return `
    <div class="gallery-card${p.is_public ? "" : " inactive"}" data-id="${p.id}">
      <img class="gc-thumb" src="${p.url}" alt="${escapeHtmlAdmin(p.alt_text || "")}" loading="lazy">
      <div class="gc-body">
        <div class="gc-filename">${escapeHtmlAdmin(p.filename)}</div>
        <input type="text" class="gc-title" placeholder="Titulek" value="${escapeHtmlAdmin(p.title || "").replace(/"/g, "&quot;")}">
        <input type="text" class="gc-alt" placeholder="Alt text (SEO)" value="${escapeHtmlAdmin(p.alt_text || "").replace(/"/g, "&quot;")}">
        <div class="gc-cats-row" style="margin:4px 0;">${chips}</div>
        <select class="gc-cat-add"><option value="">+ přidat do kategorie…</option>${catOptions}</select>
        <select class="gc-realizace-tag" style="margin-top:4px;">
          <option value=""${!p.realizace_tag ? " selected" : ""}>— realizace: žádná —</option>
          <option value="vestavby_dodavek"${p.realizace_tag === "vestavby_dodavek" ? " selected" : ""}>Vestavby do dodávek</option>
          <option value="realizace_stolu"${p.realizace_tag === "realizace_stolu" ? " selected" : ""}>Realizace stolů</option>
        </select>
        <div class="gc-active-row">
          <label><input type="checkbox" class="gc-active"${p.is_public ? " checked" : ""}> Veřejná</label>
        </div>
        <div class="gc-actions">
          <button class="gc-save">Uložit</button>
          <button class="gc-delete danger">Smazat trvale</button>
        </div>
      </div>
    </div>`;
  }).join("");

  grid.querySelectorAll(".gallery-card").forEach(card => {
    const id = parseInt(card.dataset.id, 10);
    card.querySelector(".gc-save").onclick = () => saveGalleryLibPhoto(id, card);
    card.querySelector(".gc-delete").onclick = () => deleteGalleryLibPhoto(id, card);
    card.querySelector(".gc-cat-add").onchange = (e) => {
      const catId = parseInt(e.target.value, 10);
      e.target.value = "";
      if (!catId) return;
      addGalleryLibCategory(id, catId);
    };
    card.querySelectorAll(".gc-chip-x").forEach(btn => {
      btn.onclick = () => {
        const catId = parseInt(btn.closest(".gc-chip").dataset.cid, 10);
        removeGalleryLibCategory(id, catId);
      };
    });
  });
}

function galleryLibCurrentCatIds(photoId) {
  const photo = galleryLibCache.find(p => p.id === photoId);
  return (photo?.categories || []).map(c => c.id);
}

async function addGalleryLibCategory(photoId, catId) {
  const ids = galleryLibCurrentCatIds(photoId);
  if (ids.includes(catId)) return;
  await putGalleryLibPhoto(photoId, { category_ids: [...ids, catId] });
}
async function removeGalleryLibCategory(photoId, catId) {
  const ids = galleryLibCurrentCatIds(photoId).filter(id => id !== catId);
  await putGalleryLibPhoto(photoId, { category_ids: ids });
}
async function putGalleryLibPhoto(photoId, body) {
  const errEl = document.getElementById("galleryLibErr");
  errEl.textContent = "";
  try {
    const r = await fetch(`/api/admin/gallery/library/${photoId}`, {
      method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) { errEl.textContent = data.error || "Uložení se nezdařilo."; return; }
    loadGalleryLibrary();
  } catch (e) {
    errEl.textContent = "Uložení se nezdařilo (chyba spojení).";
  }
}

function saveGalleryLibPhoto(id, card) {
  return putGalleryLibPhoto(id, {
    title: card.querySelector(".gc-title").value.trim(),
    alt_text: card.querySelector(".gc-alt").value.trim(),
    realizace_tag: card.querySelector(".gc-realizace-tag").value || null,
    is_public: card.querySelector(".gc-active").checked,
  });
}

async function deleteGalleryLibPhoto(id, card) {
  const filename = card.querySelector(".gc-filename").textContent;
  if (!confirm(`Trvale smazat „${filename}" z knihovny? Zmizí i ze všech přiřazených kategorií a případně z /realizace.html. Akci nelze vrátit zpět.`)) return;
  const errEl = document.getElementById("galleryLibErr");
  errEl.textContent = "";
  try {
    const r = await fetch(`/api/admin/gallery/library/${id}`, { method: "DELETE" });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) { errEl.textContent = data.error || "Smazání se nezdařilo."; return; }
    loadGalleryLibrary();
  } catch (e) {
    errEl.textContent = "Smazání se nezdařilo (chyba spojení).";
  }
}

// ==================== KNIHOVNA FOTEK - SDÍLENÝ PICKER ====================
// bot16, 2026-09-13 (Robert primo: "v kazde kategorii eshopu i v
// dlazdicich mozaiky se nabidne adminovi moznost vlozit fotky z
// centralni fotogalerie coz se provaze zaroven s tim zarazovanim v
// adminu fotogalerie, ktere uz tam je") - jeden znovupouzitelny picker
// nad /api/admin/gallery/library (STEJNY endpoint jako Knihovna fotek
// vyse - zadny druhy zdroj dat). Volatelny odkudkoli v adminu:
//   openGalleryLibraryPicker(photo => { ...pouzij photo.id/url/... });
// Vraci CELY objekt fotky (vc. jejich stavajicich `categories`), aby
// volajici nemusel delat dalsi dotaz - napr. pridani kategorie pak jde
// primo přes PUT /api/admin/gallery/library/<id> s doplnenym seznamem.
let galLibPickerOnSelect = null;
let galLibPickerLastResults = [];

function openGalleryLibraryPicker(onSelect) {
  galLibPickerOnSelect = onSelect;
  document.getElementById("galLibPickerSearch").value = "";
  document.getElementById("galLibPickerErr").textContent = "";
  document.getElementById("galLibPickerModal").classList.add("open");
  loadGalleryLibraryPicker();
}
function closeGalleryLibraryPicker() {
  document.getElementById("galLibPickerModal").classList.remove("open");
  galLibPickerOnSelect = null;
}
async function loadGalleryLibraryPicker() {
  const errEl = document.getElementById("galLibPickerErr");
  errEl.textContent = "";
  const q = document.getElementById("galLibPickerSearch").value.trim();
  const params = new URLSearchParams();
  if (q) params.set("q", q);
  try {
    const r = await fetch(`/api/admin/gallery/library?${params.toString()}`);
    const data = await r.json();
    if (!r.ok) { errEl.textContent = data.error || "Chyba."; return; }
    galLibPickerLastResults = data.photos || [];
    renderGalleryLibraryPickerGrid(galLibPickerLastResults);
  } catch (e) {
    errEl.textContent = "Nepodařilo se načíst knihovnu.";
  }
}
function renderGalleryLibraryPickerGrid(photos) {
  const grid = document.getElementById("galLibPickerGrid");
  if (!photos.length) {
    grid.innerHTML = '<p class="hint">Žádné fotky neodpovídají hledání.</p>';
    return;
  }
  grid.innerHTML = photos.map(p => `
    <div class="gallery-card gal-lib-picker-tile" data-id="${p.id}" title="${escapeHtmlAdmin(p.title || p.filename)}">
      <img class="gc-thumb" src="${p.url}" alt="${escapeHtmlAdmin(p.alt_text || "")}" loading="lazy">
      <div class="gc-body">
        <div class="gc-filename">${escapeHtmlAdmin(p.filename)}</div>
      </div>
    </div>
  `).join("");
  grid.querySelectorAll(".gal-lib-picker-tile").forEach(tile => {
    tile.onclick = () => {
      const id = parseInt(tile.dataset.id, 10);
      const photo = galLibPickerLastResults.find(p => p.id === id);
      const cb = galLibPickerOnSelect;
      closeGalleryLibraryPicker();
      if (cb && photo) cb(photo);
    };
  });
}
document.getElementById("galLibPickerClose").onclick = closeGalleryLibraryPicker;
document.getElementById("galLibPickerSearchBtn").onclick = loadGalleryLibraryPicker;
document.getElementById("galLibPickerSearch").addEventListener("keydown", (e) => {
  if (e.key === "Enter") loadGalleryLibraryPicker();
});
document.getElementById("galLibPickerModal").addEventListener("click", (e) => {
  if (e.target.id === "galLibPickerModal") closeGalleryLibraryPicker();
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && document.getElementById("galLibPickerModal").classList.contains("open")) {
    closeGalleryLibraryPicker();
  }
});
