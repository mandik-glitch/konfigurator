// ==================== HOMEPAGE CAROUSEL ====================
// Robert pres bot3, 2026-09-27 ("na nas homepage chceme stejny carousel
// jako je na homepage logimanu") - samostatna, jednodussi obdoba Homepage
// mozaiky nize (zadny slug/meta_description/body_html/Quill - slide je jen
// obrazek + volitelny odkaz + volitelny popisek + poradi + aktivni).
let hpcSlides = [];
let hpcEditingId = null;
let hpcImgFileToUpload = null;

function loadHomepageCarousel() {
  fetch("/api/admin/homepage-carousel").then(r => r.ok ? r.json() : { slides: [] }).then(data => {
    hpcSlides = data.slides || [];
    renderHpCarousel();
  });
}

function renderHpCarousel() {
  document.getElementById("hpcCount").textContent = `Počet snímků: ${hpcSlides.length}`;
  const list = document.getElementById("hpcList");
  if (!hpcSlides.length) {
    list.innerHTML = '<p class="hint">Zatím žádné snímky. Přidej první tlačítkem výše.</p>';
    return;
  }
  list.innerHTML = hpcSlides.map(s => `
    <div class="hpb-row${s.is_visible ? "" : " is-hidden"}" data-id="${s.id}">
      ${s.image_url ? `<img class="hpb-thumb" src="${s.image_url}" alt="">` : '<div class="hpb-thumb"></div>'}
      <div>
        <div class="hpb-row-title">${hpEscapeHtml(s.caption_text || "(bez popisku)")}${s.is_visible ? "" : " (skryto)"}</div>
        <div class="hpb-row-slug">pořadí ${s.sort_order}${s.link_url ? " · odkaz: " + hpEscapeHtml(s.link_url) : ""}</div>
      </div>
      <div class="hpb-row-actions">
        <button type="button" class="hpc-up" data-id="${s.id}" style="background:none;border:1px solid #3a3f4a;color:#c7ccd4;">↑</button>
        <button type="button" class="hpc-down" data-id="${s.id}" style="background:none;border:1px solid #3a3f4a;color:#c7ccd4;">↓</button>
        <button type="button" class="hpc-toggle" data-id="${s.id}" data-visible="${s.is_visible ? 1 : 0}">${s.is_visible ? "👁 Skrýt" : "🚫 Zobrazit"}</button>
        <button type="button" class="hpc-edit" data-id="${s.id}">Upravit</button>
        <button type="button" class="hpc-delete" data-id="${s.id}" style="background:none; border:1px solid #5a3a3a; color:#e07070;">Smazat</button>
      </div>
    </div>
  `).join("");
  list.querySelectorAll(".hpc-up").forEach(btn => {
    btn.onclick = () => moveHpCarouselSlide(parseInt(btn.dataset.id, 10), -1);
  });
  list.querySelectorAll(".hpc-down").forEach(btn => {
    btn.onclick = () => moveHpCarouselSlide(parseInt(btn.dataset.id, 10), 1);
  });
  list.querySelectorAll(".hpc-toggle").forEach(btn => {
    btn.onclick = () => {
      const id = parseInt(btn.dataset.id, 10);
      const newVisible = btn.dataset.visible !== "1";
      fetch(`/api/admin/homepage-carousel/${id}`, {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ is_visible: newVisible }),
      }).then(() => loadHomepageCarousel());
    };
  });
  list.querySelectorAll(".hpc-edit").forEach(btn => {
    btn.onclick = () => openHpCarouselModal(hpcSlides.find(s => s.id === parseInt(btn.dataset.id, 10)));
  });
  list.querySelectorAll(".hpc-delete").forEach(btn => {
    btn.onclick = () => {
      if (!confirm("Opravdu smazat tenhle snímek?")) return;
      fetch(`/api/admin/homepage-carousel/${btn.dataset.id}`, { method: "DELETE" }).then(() => loadHomepageCarousel());
    };
  });
}

// Robert pres bot3, 2026-09-27 ("neda se urcit poradi snimku carouselu") -
// 1:1 port moveHpBlock() vyse (radek 208) - prohozeni sort_order se
// sousedem, 2 paralelni PUT (backend uz sort_order v payloadu podporuje,
// viz api/cms_blocks.py::admin_homepage_carousel_update), pak reload.
async function moveHpCarouselSlide(id, direction) {
  const idx = hpcSlides.findIndex(s => s.id === id);
  if (idx === -1) return;
  const neighborIdx = idx + direction;
  if (neighborIdx < 0 || neighborIdx >= hpcSlides.length) return;
  const slide = hpcSlides[idx];
  const neighbor = hpcSlides[neighborIdx];
  try {
    await Promise.all([
      fetch(`/api/admin/homepage-carousel/${slide.id}`, {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sort_order: neighbor.sort_order }),
      }),
      fetch(`/api/admin/homepage-carousel/${neighbor.id}`, {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sort_order: slide.sort_order }),
      }),
    ]);
    loadHomepageCarousel();
  } catch (e) {
    alert("Přeřazení se nezdařilo (chyba spojení).");
  }
}

function openHpCarouselModal(slide) {
  hpcEditingId = slide ? slide.id : null;
  hpcImgFileToUpload = null;
  document.getElementById("hpcModalTitle").textContent = slide ? "Upravit snímek" : "Přidat snímek";
  document.getElementById("hpcCaption").value = slide ? (slide.caption_text || "") : "";
  document.getElementById("hpcLink").value = slide ? (slide.link_url || "") : "";
  document.getElementById("hpcVisible").checked = slide ? !!slide.is_visible : true;
  const preview = document.getElementById("hpcImgPreview");
  if (slide && slide.image_url) { preview.src = slide.image_url; preview.style.display = ""; }
  else { preview.style.display = "none"; }
  document.getElementById("hpcImgFile").value = "";
  document.getElementById("hpcModalErr").textContent = "";
  document.getElementById("hpcModal").classList.add("open");
}
function closeHpCarouselModal() {
  document.getElementById("hpcModal").classList.remove("open");
}
document.getElementById("btnAddHpCarousel").onclick = () => openHpCarouselModal(null);
document.getElementById("hpcModalClose").onclick = closeHpCarouselModal;
document.getElementById("hpcCancel").onclick = closeHpCarouselModal;
document.getElementById("hpcImgFile").onchange = (e) => {
  hpcImgFileToUpload = e.target.files[0] || null;
  if (hpcImgFileToUpload) {
    const preview = document.getElementById("hpcImgPreview");
    preview.src = URL.createObjectURL(hpcImgFileToUpload);
    preview.style.display = "";
  }
};
document.getElementById("hpcSave").onclick = async () => {
  const errEl = document.getElementById("hpcModalErr");
  errEl.textContent = "";
  const isNew = !hpcEditingId;
  if (isNew && !hpcImgFileToUpload) { errEl.textContent = "Nový snímek musí mít obrázek."; return; }
  const payload = {
    caption_text: document.getElementById("hpcCaption").value.trim(),
    link_url: document.getElementById("hpcLink").value.trim(),
    is_visible: document.getElementById("hpcVisible").checked,
  };
  try {
    let slideId = hpcEditingId;
    if (slideId) {
      const r = await fetch(`/api/admin/homepage-carousel/${slideId}`, {
        method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
      });
      if (!r.ok) { const d = await r.json().catch(() => ({})); errEl.textContent = d.error || "Uložení selhalo."; return; }
    } else {
      const r = await fetch("/api/admin/homepage-carousel", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
      });
      const d = await r.json().catch(() => ({}));
      if (!r.ok) { errEl.textContent = d.error || "Vytvoření selhalo."; return; }
      slideId = d.id;
    }
    if (hpcImgFileToUpload) {
      const fd = new FormData();
      fd.append("file", hpcImgFileToUpload);
      const rImg = await fetch(`/api/admin/homepage-carousel/${slideId}/image`, { method: "POST", body: fd });
      if (!rImg.ok) { errEl.textContent = "Snímek uložen, ale obrázek se nepodařilo nahrát."; return; }
    }
    closeHpCarouselModal();
    loadHomepageCarousel();
  } catch (e) {
    errEl.textContent = "Chyba spojení.";
  }
};

// ==================== HOMEPAGE MOZAIKA ====================
// Robert 2026-08-09 ("na homepage vytvoř system... oken... mozaika...
// pozitivni vliv na SEO/GEO... funkce jakoby mala web stranka
// zmensena, kde lze menit nazev, meta popis, obrazek, telo textu").
let hpBlocks = [];
const HPB_GALLERY_CATEGORY_LABELS = { vestavby_dodavek: "Vestavby do dodávek", realizace_stolu: "Realizace stolů a pracovišť" };
let hpEditingId = null;
let hpImgFileToUpload = null;
// bot16, 2026-09-13 (Robert primo: "...v dlazdicich mozaiky se nabidne
// adminovi moznost vlozit fotky z centralni fotogalerie") - alternativa
// k hpImgFileToUpload, navzajem se vylucuji (viz oba onchange/onclick
// handlery nize). ID fotky v content_photo_library, ne soubor.
let hpLibraryPhotoId = null;
let hpbQuill = null;

// Robert primo, 2026-09-27 ("pridej editovatelny text na homepage vcetne
// meta popisu") - jednoduchy jednorazovy text (app_settings, ne seznam
// polozek jako dlazdice), stejny Quill toolbar vzor jako ANN_QUILL_TOOLBAR
// nize (headers/bold/list/link/html, bez image/video - cistě SEO text).
let hpIntroQuill = null;
const HPI_QUILL_TOOLBAR = {
  container: [
    [{ header: [1, 2, 3, false] }],
    ["bold", "italic", "underline"],
    [{ list: "ordered" }, { list: "bullet" }],
    ["link"],
    ["html"],
    ["clean"],
  ],
  handlers: { link: quillLinkHandler, html: cemQuillHtmlHandler },
};
function hpIntroInitQuill() {
  if (hpIntroQuill) return;
  hpIntroQuill = new Quill("#hpIntroEditor", { theme: "snow", modules: { toolbar: HPI_QUILL_TOOLBAR } });
  document.querySelectorAll(".ql-html").forEach(btn => { btn.title = "Zobrazit/upravit HTML zdroj"; });
}
function loadHomepageIntro() {
  hpIntroInitQuill();
  fetch("/api/admin/homepage-intro-text").then(r => r.ok ? r.json() : { body_html: "" }).then(data => {
    hpIntroQuill.root.innerHTML = data.body_html || "";
  });
}
document.getElementById("btnSaveHpIntro").onclick = async () => {
  const errEl = document.getElementById("hpIntroErr");
  const statusEl = document.getElementById("hpIntroStatus");
  errEl.textContent = "";
  statusEl.textContent = "";
  try {
    const r = await fetch("/api/admin/homepage-intro-text", {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ body_html: hpIntroQuill.root.innerHTML }),
    });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) { errEl.textContent = d.error || "Uložení selhalo."; return; }
    statusEl.textContent = "Uloženo ✓";
    setTimeout(() => { statusEl.textContent = ""; }, 2500);
  } catch (e) {
    errEl.textContent = "Chyba spojení.";
  }
};

function loadHomepageBlocks() {
  fetch("/api/admin/homepage-blocks").then(r => r.ok ? r.json() : { blocks: [] }).then(data => {
    hpBlocks = data.blocks || [];
    renderHpBlocks();
  });
}

function hpEscapeHtml(s) {
  const d = document.createElement("div");
  d.textContent = s == null ? "" : s;
  return d.innerHTML;
}

function renderHpBlocks() {
  document.getElementById("hpbCount").textContent = `Počet dlaždic: ${hpBlocks.length}`;
  const list = document.getElementById("hpbList");
  if (!hpBlocks.length) {
    list.innerHTML = '<p class="hint">Zatím žádné dlaždice. Přidej první tlačítkem výše.</p>';
    return;
  }
  list.innerHTML = hpBlocks.map(b => `
    <div class="hpb-row${b.is_visible ? "" : " is-hidden"}" data-id="${b.id}">
      ${b.image_url ? `<img class="hpb-thumb" src="${b.image_url}" alt="">` : '<div class="hpb-thumb"></div>'}
      <div>
        <div class="hpb-row-title">${hpEscapeHtml(b.title)}${b.is_visible ? "" : " (skryto)"}${b.gallery_preview ? ` 🖼 karusel galerie${b.gallery_category ? " (" + hpEscapeHtml(HPB_GALLERY_CATEGORY_LABELS[b.gallery_category] || b.gallery_category) + ")" : ""}` : ""}</div>
        <div class="hpb-row-slug">${b.gallery_preview ? `/realizace.html${b.gallery_category ? "?category=" + encodeURIComponent(b.gallery_category) : ""}` : `/blok/${hpEscapeHtml(b.slug)}`}</div>
      </div>
      <div class="hpb-row-actions">
        <button type="button" class="hpb-up" data-id="${b.id}" style="background:none;border:1px solid #3a3f4a;color:#c7ccd4;">↑</button>
        <button type="button" class="hpb-down" data-id="${b.id}" style="background:none;border:1px solid #3a3f4a;color:#c7ccd4;">↓</button>
        <button type="button" class="hpb-toggle" data-id="${b.id}" data-visible="${b.is_visible ? 1 : 0}">${b.is_visible ? "👁 Skrýt" : "🚫 Zobrazit"}</button>
        <button type="button" class="hpb-edit" data-id="${b.id}">Upravit</button>
        <button type="button" class="hpb-delete" data-id="${b.id}" style="background:none; border:1px solid #5a3a3a; color:#e07070;">Smazat</button>
      </div>
    </div>
  `).join("");
  list.querySelectorAll(".hpb-up").forEach(btn => {
    btn.onclick = () => moveHpBlock(parseInt(btn.dataset.id, 10), -1);
  });
  list.querySelectorAll(".hpb-down").forEach(btn => {
    btn.onclick = () => moveHpBlock(parseInt(btn.dataset.id, 10), 1);
  });
  list.querySelectorAll(".hpb-toggle").forEach(btn => {
    btn.onclick = () => {
      const id = parseInt(btn.dataset.id, 10);
      const newVisible = btn.dataset.visible !== "1";
      fetch(`/api/admin/homepage-blocks/${id}`, {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ is_visible: newVisible }),
      }).then(() => loadHomepageBlocks());
    };
  });
  list.querySelectorAll(".hpb-edit").forEach(btn => {
    btn.onclick = () => openHpBlockModal(hpBlocks.find(b => b.id === parseInt(btn.dataset.id, 10)));
  });
  list.querySelectorAll(".hpb-delete").forEach(btn => {
    btn.onclick = () => {
      if (!confirm("Opravdu smazat tuhle dlaždici a její stránku?")) return;
      fetch(`/api/admin/homepage-blocks/${btn.dataset.id}`, { method: "DELETE" }).then(() => loadHomepageBlocks());
    };
  });
}

// Robert 2026-08-11 ("navrhni urcovani poradi jednotlivych dlazdic
// mozaiky homepage" -> sipky nahoru/dolu) - stejny vzor jako
// moveGalleryImage() u fotogalerie realizaci: prohodi sort_order se
// sousedem v hpBlocks (uz serazenem podle sort_order, viz backend
// ORDER BY), 2 PUT pozadavky, pak znovunacte cely seznam.
async function moveHpBlock(id, direction) {
  const idx = hpBlocks.findIndex(b => b.id === id);
  if (idx === -1) return;
  const neighborIdx = idx + direction;
  if (neighborIdx < 0 || neighborIdx >= hpBlocks.length) return;
  const block = hpBlocks[idx];
  const neighbor = hpBlocks[neighborIdx];
  try {
    await Promise.all([
      fetch(`/api/admin/homepage-blocks/${block.id}`, {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sort_order: neighbor.sort_order }),
      }),
      fetch(`/api/admin/homepage-blocks/${neighbor.id}`, {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sort_order: block.sort_order }),
      }),
    ]);
    loadHomepageBlocks();
  } catch (e) {
    alert("Přeřazení se nezdařilo (chyba spojení).");
  }
}

function openHpBlockModal(block) {
  hpEditingId = block ? block.id : null;
  hpImgFileToUpload = null;
  hpLibraryPhotoId = null;
  hpbInitQuill();
  document.getElementById("hpbModalTitle").textContent = block ? "Upravit dlaždici" : "Přidat dlaždici";
  document.getElementById("hpbTitle").value = block ? block.title : "";
  document.getElementById("hpbMeta").value = block ? (block.meta_description || "") : "";
  hpbQuill.setContents([]);
  document.getElementById("hpbVisible").checked = block ? !!block.is_visible : true;
  document.getElementById("hpbGalleryPreview").checked = block ? !!block.gallery_preview : false;
  document.getElementById("hpbGalleryCategory").value = block ? (block.gallery_category || "") : "";
  const preview = document.getElementById("hpbImgPreview");
  if (block && block.image_url) { preview.src = block.image_url; preview.style.display = ""; }
  else { preview.style.display = "none"; }
  document.getElementById("hpbImgFile").value = "";
  document.getElementById("hpbModalErr").textContent = "";
  document.getElementById("hpbModal").classList.add("open");
  // Telo textu (body_html) neni v seznamu z /api/admin/homepage-blocks
  // (jen zakladni pole), pri editaci ho dotahneme zvlast.
  if (block) {
    fetch(`/api/admin/homepage-blocks/${block.id}`).then(r => r.ok ? r.json() : null).then(data => {
      if (data) hpbQuill.root.innerHTML = data.body_html || "";
    });
  }
}
function closeHpBlockModal() {
  document.getElementById("hpbModal").classList.remove("open");
}
// Robert 2026-08-10 ("u vypsaných chyb mi dávej k odkliknutí: opravit
// a doplnit") - #qaAuditPanel na Dashboardu ma jen id dlazdice,
// openHpBlockModal(block) ale potrebuje cely objekt - dotahne se pres
// stejny GET, jaky uz pouziva editace v zalozce Homepage mozaika.
async function qaOpenHomepageBlockEdit(id) {
  const r = await fetch(`/api/admin/homepage-blocks/${id}`);
  const data = await r.json().catch(() => null);
  if (!r.ok || !data) { alert("Dlaždici se nepodařilo načíst."); return; }
  openHpBlockModal(data);
}
document.getElementById("btnAddHpBlock").onclick = () => openHpBlockModal(null);
document.getElementById("hpbModalClose").onclick = closeHpBlockModal;
document.getElementById("hpbCancel").onclick = closeHpBlockModal;
document.getElementById("hpbImgFile").onchange = (e) => {
  hpImgFileToUpload = e.target.files[0] || null;
  if (hpImgFileToUpload) {
    hpLibraryPhotoId = null; // vzajemne se vylucuje s vyberem z knihovny
    const preview = document.getElementById("hpbImgPreview");
    preview.src = URL.createObjectURL(hpImgFileToUpload);
    preview.style.display = "";
  }
};
document.getElementById("hpbPickLibraryBtn").onclick = () => {
  openGalleryLibraryPicker((photo) => {
    hpLibraryPhotoId = photo.id;
    hpImgFileToUpload = null; // vzajemne se vylucuje s cerstvym uploadem
    document.getElementById("hpbImgFile").value = "";
    const preview = document.getElementById("hpbImgPreview");
    preview.src = photo.url;
    preview.style.display = "";
  });
};
document.getElementById("hpbSave").onclick = async () => {
  const errEl = document.getElementById("hpbModalErr");
  errEl.textContent = "";
  const title = document.getElementById("hpbTitle").value.trim();
  if (!title) { errEl.textContent = "Chybí název."; return; }
  const payload = {
    title,
    meta_description: document.getElementById("hpbMeta").value.trim(),
    body_html: hpbQuill.root.innerHTML,
    is_visible: document.getElementById("hpbVisible").checked,
    gallery_preview: document.getElementById("hpbGalleryPreview").checked,
    gallery_category: document.getElementById("hpbGalleryCategory").value,
  };
  try {
    let blockId = hpEditingId;
    if (blockId) {
      const r = await fetch(`/api/admin/homepage-blocks/${blockId}`, {
        method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
      });
      if (!r.ok) { const d = await r.json().catch(() => ({})); errEl.textContent = d.error || "Uložení selhalo."; return; }
    } else {
      const r = await fetch("/api/admin/homepage-blocks", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
      });
      const d = await r.json().catch(() => ({}));
      if (!r.ok) { errEl.textContent = d.error || "Vytvoření selhalo."; return; }
      blockId = d.id;
    }
    if (hpImgFileToUpload) {
      const fd = new FormData();
      fd.append("file", hpImgFileToUpload);
      await fetch(`/api/admin/homepage-blocks/${blockId}/image`, { method: "POST", body: fd });
    } else if (hpLibraryPhotoId) {
      await fetch(`/api/admin/homepage-blocks/${blockId}/image-from-library`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ photo_id: hpLibraryPhotoId }),
      });
    }
    closeHpBlockModal();
    loadHomepageBlocks();
  } catch (e) {
    errEl.textContent = "Chyba spojení.";
  }
};

// ==================== POSTRANNI PANEL ====================
// bot5 2026-08-10 (Robert: "udelej novou sekci v adminu, a dlazdici
// tam prenes, prekopiruj") - samostatna obdoba Homepage mozaiky vyse,
// 1:1 stejny vzor, navic upload videa (Robert: "to video tam vloží
// admin").
let sbBlocks = [];
let sbEditingId = null;
let sbImgFileToUpload = null;
let sbVidFileToUpload = null;
let sbbQuill = null;

function loadSidebarBlocks() {
  fetch("/api/admin/sidebar-blocks").then(r => r.ok ? r.json() : { blocks: [] }).then(data => {
    sbBlocks = data.blocks || [];
    renderSbBlocks();
  });
}

function renderSbBlocks() {
  document.getElementById("sbbCount").textContent = `Počet položek: ${sbBlocks.length}`;
  const list = document.getElementById("sbbList");
  if (!sbBlocks.length) {
    list.innerHTML = '<p class="hint">Zatím žádné položky. Přidej první tlačítkem výše.</p>';
    return;
  }
  list.innerHTML = sbBlocks.map(b => `
    <div class="hpb-row${b.is_visible ? "" : " is-hidden"}" data-id="${b.id}">
      ${b.image_url ? `<img class="hpb-thumb" src="${b.image_url}" alt="">` : '<div class="hpb-thumb"></div>'}
      <div>
        <div class="hpb-row-title">${hpEscapeHtml(b.title)}${b.is_visible ? "" : " (skryto)"}${b.video_url ? " 🎥" : ""}</div>
        <div class="hpb-row-slug">/panel/${hpEscapeHtml(b.slug)}</div>
      </div>
      <div class="hpb-row-actions">
        <button type="button" class="sbb-toggle" data-id="${b.id}" data-visible="${b.is_visible ? 1 : 0}">${b.is_visible ? "👁 Skrýt" : "🚫 Zobrazit"}</button>
        <button type="button" class="sbb-edit" data-id="${b.id}">Upravit</button>
        <button type="button" class="sbb-delete" data-id="${b.id}" style="background:none; border:1px solid #5a3a3a; color:#e07070;">Smazat</button>
      </div>
    </div>
  `).join("");
  list.querySelectorAll(".sbb-toggle").forEach(btn => {
    btn.onclick = () => {
      const id = parseInt(btn.dataset.id, 10);
      const newVisible = btn.dataset.visible !== "1";
      fetch(`/api/admin/sidebar-blocks/${id}`, {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ is_visible: newVisible }),
      }).then(() => loadSidebarBlocks());
    };
  });
  list.querySelectorAll(".sbb-edit").forEach(btn => {
    btn.onclick = () => openSbBlockModal(sbBlocks.find(b => b.id === parseInt(btn.dataset.id, 10)));
  });
  list.querySelectorAll(".sbb-delete").forEach(btn => {
    btn.onclick = () => {
      if (!confirm("Opravdu smazat tuhle položku a její stránku?")) return;
      fetch(`/api/admin/sidebar-blocks/${btn.dataset.id}`, { method: "DELETE" }).then(() => loadSidebarBlocks());
    };
  });
}

function openSbBlockModal(block) {
  sbEditingId = block ? block.id : null;
  sbImgFileToUpload = null;
  sbVidFileToUpload = null;
  sbbInitQuill();
  document.getElementById("sbbModalTitle").textContent = block ? "Upravit položku" : "Přidat položku";
  document.getElementById("sbbTitle").value = block ? block.title : "";
  document.getElementById("sbbMeta").value = block ? (block.meta_description || "") : "";
  sbbQuill.setContents([]);
  document.getElementById("sbbVisible").checked = block ? !!block.is_visible : true;
  const preview = document.getElementById("sbbImgPreview");
  if (block && block.image_url) { preview.src = block.image_url; preview.style.display = ""; }
  else { preview.style.display = "none"; }
  const vidPreview = document.getElementById("sbbVidPreview");
  if (block && block.video_url) { vidPreview.src = block.video_url; vidPreview.style.display = ""; }
  else { vidPreview.style.display = "none"; vidPreview.removeAttribute("src"); }
  document.getElementById("sbbImgFile").value = "";
  document.getElementById("sbbVidFile").value = "";
  document.getElementById("sbbModalErr").textContent = "";
  document.getElementById("sbbModal").classList.add("open");
  if (block) {
    fetch(`/api/admin/sidebar-blocks/${block.id}`).then(r => r.ok ? r.json() : null).then(data => {
      if (data) sbbQuill.root.innerHTML = data.body_html || "";
    });
  }
}
function closeSbBlockModal() {
  document.getElementById("sbbModal").classList.remove("open");
}
document.getElementById("btnAddSbBlock").onclick = () => openSbBlockModal(null);
document.getElementById("sbbModalClose").onclick = closeSbBlockModal;
document.getElementById("sbbCancel").onclick = closeSbBlockModal;
document.getElementById("sbbImgFile").onchange = (e) => {
  sbImgFileToUpload = e.target.files[0] || null;
  if (sbImgFileToUpload) {
    const preview = document.getElementById("sbbImgPreview");
    preview.src = URL.createObjectURL(sbImgFileToUpload);
    preview.style.display = "";
  }
};
document.getElementById("sbbVidFile").onchange = (e) => {
  sbVidFileToUpload = e.target.files[0] || null;
  if (sbVidFileToUpload) {
    const preview = document.getElementById("sbbVidPreview");
    preview.src = URL.createObjectURL(sbVidFileToUpload);
    preview.style.display = "";
  }
};
document.getElementById("sbbSave").onclick = async () => {
  const errEl = document.getElementById("sbbModalErr");
  errEl.textContent = "";
  const title = document.getElementById("sbbTitle").value.trim();
  if (!title) { errEl.textContent = "Chybí název."; return; }
  const payload = {
    title,
    meta_description: document.getElementById("sbbMeta").value.trim(),
    body_html: sbbQuill.root.innerHTML,
    is_visible: document.getElementById("sbbVisible").checked,
  };
  try {
    let blockId = sbEditingId;
    if (blockId) {
      const r = await fetch(`/api/admin/sidebar-blocks/${blockId}`, {
        method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
      });
      if (!r.ok) { const d = await r.json().catch(() => ({})); errEl.textContent = d.error || "Uložení selhalo."; return; }
    } else {
      const r = await fetch("/api/admin/sidebar-blocks", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
      });
      const d = await r.json().catch(() => ({}));
      if (!r.ok) { errEl.textContent = d.error || "Vytvoření selhalo."; return; }
      blockId = d.id;
    }
    if (sbImgFileToUpload) {
      const fd = new FormData();
      fd.append("file", sbImgFileToUpload);
      await fetch(`/api/admin/sidebar-blocks/${blockId}/image`, { method: "POST", body: fd });
    }
    if (sbVidFileToUpload) {
      const fd = new FormData();
      fd.append("file", sbVidFileToUpload);
      await fetch(`/api/admin/sidebar-blocks/${blockId}/video`, { method: "POST", body: fd });
    }
    closeSbBlockModal();
    loadSidebarBlocks();
  } catch (e) {
    errEl.textContent = "Chyba spojení.";
  }
};

// ==================== CENTRÁLNÍ TEXTY (obor -> typologie) ====================
// Robert pres bot3, 2026-09-27: centralni panel popisu kategorii, dvouurovnovy
// strom obor (content_obor) -> typologie (content_typologie). Bot7 napise
// navrh, admin (Robert) precte/opravi/schvali - schvaleno/schvaleno_at na obou
// urovnich je jen bota7 vlastni disciplina (dal uz na schvaleny radek nesahne),
// tady v UI se jen zobrazuje badge a checkbox, zadne technicke omezeni editace.
let cotObory = [];
let cotOborEditingId = null;
let cotTypEditingId = null;
let cotTypEditingOborId = null;
let cotOborQuill = null;
let cotTypQuill = null;
const COT_QUILL_TOOLBAR = {
  container: [
    [{ header: [1, 2, 3, false] }],
    ["bold", "italic", "underline"],
    [{ list: "ordered" }, { list: "bullet" }],
    ["link"],
    ["html"],
    ["clean"],
  ],
  handlers: { link: quillLinkHandler, html: cemQuillHtmlHandler },
};
function cotOborInitQuill() {
  if (cotOborQuill) return;
  cotOborQuill = new Quill("#cotOborEditor", { theme: "snow", modules: { toolbar: COT_QUILL_TOOLBAR } });
  document.querySelectorAll(".ql-html").forEach(btn => { btn.title = "Zobrazit/upravit HTML zdroj"; });
}
function cotTypInitQuill() {
  if (cotTypQuill) return;
  cotTypQuill = new Quill("#cotTypEditor", { theme: "snow", modules: { toolbar: COT_QUILL_TOOLBAR } });
  document.querySelectorAll(".ql-html").forEach(btn => { btn.title = "Zobrazit/upravit HTML zdroj"; });
}

function loadContentObor() {
  fetch("/api/admin/content-obor").then(r => r.ok ? r.json() : { obory: [] }).then(data => {
    cotObory = data.obory || [];
    renderCotList();
  });
}

function cotBadge(schvaleno, schvalenoAt) {
  if (schvaleno) {
    const d = schvalenoAt ? new Date(schvalenoAt) : null;
    const ds = d ? ` ${String(d.getDate()).padStart(2, "0")}.${String(d.getMonth() + 1).padStart(2, "0")}.` : "";
    return `<span class="cot-badge is-ok">✓ Schváleno${ds}</span>`;
  }
  return `<span class="cot-badge is-pending">Ke schválení</span>`;
}

function renderCotList() {
  document.getElementById("cotCount").textContent = `Počet oborů: ${cotObory.length}`;
  const list = document.getElementById("cotList");
  if (!cotObory.length) {
    list.innerHTML = '<p class="hint">Zatím žádné obory. Přidej první tlačítkem výše.</p>';
    return;
  }
  list.innerHTML = cotObory.map(o => `
    <div class="cot-obor-card" data-id="${o.id}">
      <div class="cot-obor-head">
        <span class="cot-obor-kod">#${hpEscapeHtml(o.kod)}</span>
        <span class="cot-obor-title">${hpEscapeHtml(o.nazev)}</span>
        ${cotBadge(o.schvaleno, o.schvaleno_at)}
        <div class="cot-obor-actions">
          <button type="button" class="cot-obor-addtyp" data-id="${o.id}">+ Typologie</button>
          <button type="button" class="cot-obor-edit" data-id="${o.id}">Upravit obor</button>
          <button type="button" class="cot-obor-delete" data-id="${o.id}" style="background:none; border:1px solid #5a3a3a; color:#e07070;">Smazat obor</button>
        </div>
      </div>
      <div class="cot-typ-list">
        ${(o.typologie || []).map(t => `
          <div class="cot-typ-row" data-id="${t.id}">
            <span class="cot-typ-title">${hpEscapeHtml(t.nazev)}</span>
            <span class="cot-typ-klic">${hpEscapeHtml(t.klic)}</span>
            <span class="cot-typ-katids">${t.kategorie_ids ? "kat: " + hpEscapeHtml(t.kategorie_ids) : ""}</span>
            ${cotBadge(t.schvaleno, t.schvaleno_at)}
            <div class="cot-typ-actions">
              <button type="button" class="cot-typ-edit" data-id="${t.id}" data-obor-id="${o.id}">Upravit</button>
              <button type="button" class="cot-typ-delete" data-id="${t.id}" style="background:none; border:1px solid #5a3a3a; color:#e07070;">Smazat</button>
            </div>
          </div>
        `).join("") || '<p class="hint">Zatím žádná typologie v tomhle oboru.</p>'}
      </div>
    </div>
  `).join("");
  list.querySelectorAll(".cot-obor-edit").forEach(btn => {
    btn.onclick = () => openCotOborModal(cotObory.find(o => o.id === parseInt(btn.dataset.id, 10)));
  });
  list.querySelectorAll(".cot-obor-delete").forEach(btn => {
    btn.onclick = () => {
      if (!confirm("Opravdu smazat celý obor včetně všech jeho typologií?")) return;
      fetch(`/api/admin/content-obor/${btn.dataset.id}`, { method: "DELETE" }).then(() => loadContentObor());
    };
  });
  list.querySelectorAll(".cot-obor-addtyp").forEach(btn => {
    btn.onclick = () => openCotTypModal(parseInt(btn.dataset.id, 10), null);
  });
  list.querySelectorAll(".cot-typ-edit").forEach(btn => {
    const oborId = parseInt(btn.dataset.oborId, 10);
    const obor = cotObory.find(o => o.id === oborId);
    btn.onclick = () => openCotTypModal(oborId, (obor.typologie || []).find(t => t.id === parseInt(btn.dataset.id, 10)));
  });
  list.querySelectorAll(".cot-typ-delete").forEach(btn => {
    btn.onclick = () => {
      if (!confirm("Opravdu smazat tuhle typologii?")) return;
      fetch(`/api/admin/content-typologie/${btn.dataset.id}`, { method: "DELETE" }).then(() => loadContentObor());
    };
  });
}

function openCotOborModal(obor) {
  cotOborEditingId = obor ? obor.id : null;
  cotOborInitQuill();
  document.getElementById("cotOborModalTitle").textContent = obor ? "Upravit obor" : "Přidat obor";
  document.getElementById("cotOborKod").value = obor ? obor.kod : "";
  document.getElementById("cotOborNazev").value = obor ? obor.nazev : "";
  document.getElementById("cotOborSchvaleno").checked = obor ? !!obor.schvaleno : false;
  cotOborQuill.setContents([]);
  document.getElementById("cotOborModalErr").textContent = "";
  document.getElementById("cotOborModal").classList.add("open");
  if (obor) {
    fetch(`/api/admin/content-obor/${obor.id}`).then(r => r.ok ? r.json() : null).then(data => {
      if (data) cotOborQuill.root.innerHTML = data.popis_html || "";
    });
  }
}
function closeCotOborModal() {
  document.getElementById("cotOborModal").classList.remove("open");
}
document.getElementById("btnAddCotObor").onclick = () => openCotOborModal(null);
document.getElementById("cotOborModalClose").onclick = closeCotOborModal;
document.getElementById("cotOborCancel").onclick = closeCotOborModal;
document.getElementById("cotOborSave").onclick = async () => {
  const errEl = document.getElementById("cotOborModalErr");
  errEl.textContent = "";
  const kod = document.getElementById("cotOborKod").value.trim();
  const nazev = document.getElementById("cotOborNazev").value.trim();
  if (!kod || !nazev) { errEl.textContent = "Chybí kód nebo název."; return; }
  const payload = {
    kod, nazev,
    popis_html: cotOborQuill.root.innerHTML,
    schvaleno: document.getElementById("cotOborSchvaleno").checked,
  };
  try {
    const url = cotOborEditingId ? `/api/admin/content-obor/${cotOborEditingId}` : "/api/admin/content-obor";
    const r = await fetch(url, {
      method: cotOborEditingId ? "PUT" : "POST",
      headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
    });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) { errEl.textContent = d.error || "Uložení selhalo."; return; }
    closeCotOborModal();
    loadContentObor();
  } catch (e) {
    errEl.textContent = "Chyba spojení.";
  }
};

function openCotTypModal(oborId, typologie) {
  cotTypEditingId = typologie ? typologie.id : null;
  cotTypEditingOborId = oborId;
  cotTypInitQuill();
  document.getElementById("cotTypModalTitle").textContent = typologie ? "Upravit typologii" : "Přidat typologii";
  document.getElementById("cotTypKlic").value = typologie ? typologie.klic : "";
  document.getElementById("cotTypNazev").value = typologie ? typologie.nazev : "";
  document.getElementById("cotTypKategorieIds").value = typologie ? (typologie.kategorie_ids || "") : "";
  document.getElementById("cotTypSchvaleno").checked = typologie ? !!typologie.schvaleno : false;
  cotTypQuill.setContents([]);
  document.getElementById("cotTypModalErr").textContent = "";
  document.getElementById("cotTypModal").classList.add("open");
  if (typologie) {
    fetch(`/api/admin/content-typologie/${typologie.id}`).then(r => r.ok ? r.json() : null).then(data => {
      if (data) cotTypQuill.root.innerHTML = data.popis_html || "";
    });
  }
}
function closeCotTypModal() {
  document.getElementById("cotTypModal").classList.remove("open");
}
document.getElementById("cotTypModalClose").onclick = closeCotTypModal;
document.getElementById("cotTypCancel").onclick = closeCotTypModal;
document.getElementById("cotTypSave").onclick = async () => {
  const errEl = document.getElementById("cotTypModalErr");
  errEl.textContent = "";
  const klic = document.getElementById("cotTypKlic").value.trim();
  const nazev = document.getElementById("cotTypNazev").value.trim();
  if (!klic || !nazev) { errEl.textContent = "Chybí klíč nebo název."; return; }
  const payload = {
    klic, nazev,
    kategorie_ids: document.getElementById("cotTypKategorieIds").value.trim(),
    popis_html: cotTypQuill.root.innerHTML,
    schvaleno: document.getElementById("cotTypSchvaleno").checked,
  };
  try {
    const url = cotTypEditingId
      ? `/api/admin/content-typologie/${cotTypEditingId}`
      : `/api/admin/content-obor/${cotTypEditingOborId}/typologie`;
    const r = await fetch(url, {
      method: cotTypEditingId ? "PUT" : "POST",
      headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
    });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) { errEl.textContent = d.error || "Uložení selhalo."; return; }
    closeCotTypModal();
    loadContentObor();
  } catch (e) {
    errEl.textContent = "Chyba spojení.";
  }
};

// ==================== NOVINKY ====================
// bot5 2026-08-10 (Robert: "jednoduchý typ dlazdice povedle mozaiky,
// pro ohlašování nových zpráv novinek... jen text plnohodnotně pro
// seo... jen s možností menit barvy okrajů") - obdoba Homepage
// mozaiky/Postranniho panelu vyse, ale BEZ obrazku/videa (proto i
// zjednoduseny Quill toolbar bez tlacitek image/video) a navic barva
// okraje (color input). Razeni je vzdy chronologicke (podle
// created_at), zadne rucni sort_order pole v UI.
let annItems = [];
let annEditingId = null;
let annQuill = null;
const ANN_QUILL_TOOLBAR = {
  container: [
    [{ header: [1, 2, 3, false] }],
    ["bold", "italic", "underline"],
    [{ list: "ordered" }, { list: "bullet" }],
    ["link"],
    ["html"],
    ["clean"],
  ],
  handlers: { link: quillLinkHandler, html: cemQuillHtmlHandler },
};
function annInitQuill() {
  if (annQuill) return;
  annQuill = new Quill("#annBodyEditor", { theme: "snow", modules: { toolbar: ANN_QUILL_TOOLBAR } });
  document.querySelectorAll(".ql-html").forEach(btn => { btn.title = "Zobrazit/upravit HTML zdroj"; });
}

function loadAnnouncementItems() {
  fetch("/api/admin/announcement-items").then(r => r.ok ? r.json() : { items: [] }).then(data => {
    annItems = data.items || [];
    renderAnnItems();
  });
}

function fmtAnnDate(iso) {
  if (!iso) return "";
  try { return new Date(iso).toLocaleDateString("cs-CZ"); } catch (e) { return ""; }
}

function renderAnnItems() {
  document.getElementById("annCount").textContent = `Počet hlášek: ${annItems.length}`;
  const list = document.getElementById("annList");
  if (!annItems.length) {
    list.innerHTML = '<p class="hint">Zatím žádné hlášky. Přidej první tlačítkem výše.</p>';
    return;
  }
  list.innerHTML = annItems.map(n => `
    <div class="hpb-row${n.is_visible ? "" : " is-hidden"}" data-id="${n.id}">
      <div class="hpb-thumb" style="display:flex; align-items:center; justify-content:center; border-left:4px solid ${n.border_color ? hpEscapeHtml(n.border_color) : "#2fe07a"};">📰</div>
      <div>
        <div class="hpb-row-title">${hpEscapeHtml(n.title)}${n.is_visible ? "" : " (skryto)"}</div>
        <div class="hpb-row-slug">${fmtAnnDate(n.created_at)}</div>
      </div>
      <div class="hpb-row-actions">
        <button type="button" class="ann-toggle" data-id="${n.id}" data-visible="${n.is_visible ? 1 : 0}">${n.is_visible ? "👁 Skrýt" : "🚫 Zobrazit"}</button>
        <button type="button" class="ann-edit" data-id="${n.id}">Upravit</button>
        <button type="button" class="ann-delete" data-id="${n.id}" style="background:none; border:1px solid #5a3a3a; color:#e07070;">Smazat</button>
      </div>
    </div>
  `).join("");
  list.querySelectorAll(".ann-toggle").forEach(btn => {
    btn.onclick = () => {
      const id = parseInt(btn.dataset.id, 10);
      const newVisible = btn.dataset.visible !== "1";
      fetch(`/api/admin/announcement-items/${id}`, {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ is_visible: newVisible }),
      }).then(() => loadAnnouncementItems());
    };
  });
  list.querySelectorAll(".ann-edit").forEach(btn => {
    btn.onclick = () => openAnnModal(annItems.find(n => n.id === parseInt(btn.dataset.id, 10)));
  });
  list.querySelectorAll(".ann-delete").forEach(btn => {
    btn.onclick = () => {
      if (!confirm("Opravdu smazat tuhle hlášku?")) return;
      fetch(`/api/admin/announcement-items/${btn.dataset.id}`, { method: "DELETE" }).then(() => loadAnnouncementItems());
    };
  });
}

function openAnnModal(item) {
  annEditingId = item ? item.id : null;
  annInitQuill();
  document.getElementById("annModalTitle").textContent = item ? "Upravit hlášku" : "Přidat hlášku";
  document.getElementById("annTitle").value = item ? item.title : "";
  annQuill.setContents([]);
  document.getElementById("annVisible").checked = item ? !!item.is_visible : true;
  document.getElementById("annBorderColor").value = (item && item.border_color) || "#2fe07a";
  document.getElementById("annModalErr").textContent = "";
  document.getElementById("annModal").classList.add("open");
  if (item) {
    fetch(`/api/admin/announcement-items/${item.id}`).then(r => r.ok ? r.json() : null).then(data => {
      if (data) annQuill.root.innerHTML = data.body_html || "";
    });
  }
}
function closeAnnModal() {
  document.getElementById("annModal").classList.remove("open");
}
document.getElementById("btnAddAnnouncement").onclick = () => openAnnModal(null);
document.getElementById("annModalClose").onclick = closeAnnModal;
document.getElementById("annCancel").onclick = closeAnnModal;
document.getElementById("annBorderColorReset").onclick = () => {
  document.getElementById("annBorderColor").value = "#2fe07a";
};
document.getElementById("annSave").onclick = async () => {
  const errEl = document.getElementById("annModalErr");
  errEl.textContent = "";
  const title = document.getElementById("annTitle").value.trim();
  if (!title) { errEl.textContent = "Chybí název."; return; }
  const payload = {
    title,
    body_html: annQuill.root.innerHTML,
    is_visible: document.getElementById("annVisible").checked,
    border_color: document.getElementById("annBorderColor").value,
  };
  try {
    let itemId = annEditingId;
    if (itemId) {
      const r = await fetch(`/api/admin/announcement-items/${itemId}`, {
        method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
      });
      if (!r.ok) { const d = await r.json().catch(() => ({})); errEl.textContent = d.error || "Uložení selhalo."; return; }
    } else {
      const r = await fetch("/api/admin/announcement-items", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
      });
      const d = await r.json().catch(() => ({}));
      if (!r.ok) { errEl.textContent = d.error || "Vytvoření selhalo."; return; }
      itemId = d.id;
    }
    closeAnnModal();
    loadAnnouncementItems();
  } catch (e) {
    errEl.textContent = "Chyba spojení.";
  }
};
