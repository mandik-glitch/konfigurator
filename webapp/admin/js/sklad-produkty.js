// ==================== KATEGORIE ====================
// Robert 2026-07-25 (mockup): "udelejme kategorie rozbalovaci svisle, a v
// backendu zjednodusit at se neopakuji pridavani tlacitka vsude, jen
// nahoře". Strom je ted defaultne sbaleny (+/- toggle na kazde vetvi) a
// existuje jen JEDNO tlacitko "Pridat kategorii" nahore, ktere otevre
// modal s vyberem nadrazene kategorie (misto opakovaneho add-form
// formulare pod kazdou polozkou).
let catTree = [];
// Rozbalene vetve (cat.id) - drzeno mimo DOM (Robert 2026-09-16: "po
// presunu/manipulaci se strom porad sbaluje, ma zustat rozbaleny").
// renderCatTree() pri kazdem loadCategories() (po presunu/prejmenovani/
// smazani/pridani - viz volani nize) stavi CELY strom znovu od nuly,
// takze "expanded" CSS trida na starych DOM uzlech vzdy zmizi spolu s
// nimi. Reseni: stav rozbaleni drzet samostatne v tehle mnozine podle
// cat.id (preziva pres re-render), buildCatBlock/buildCatChildRow ji
// při stavbe ctou i zapisuji.
let catExpandedIds = new Set();

async function loadCategories() {
  try {
    const r = await fetch("/api/categories");
    const data = await r.json();
    catTree = data.tree || [];
    renderCatTree();
    document.getElementById("catCount").textContent = `Počet kategorií: ${countCatTree(catTree)}`;
  } catch (e) {
    document.getElementById("catErr").textContent = "Nepodařilo se načíst kategorie.";
  }
}

function countCatTree(nodes) {
  let n = 0;
  nodes.forEach(node => { n += 1 + countCatTree(node.children || []); });
  return n;
}

function renderCatTree() {
  const el = document.getElementById("catTree");
  el.innerHTML = "";
  if (!catTree.length) {
    el.innerHTML = '<p style="color:#666;font-size:13px;">Zatím žádné kategorie.</p>';
    return;
  }
  catTree.forEach(cat => {
    el.appendChild(buildCatBlock(cat));
  });
}

// Korenova (1.) uroven - stejna karta jako drive, ted s +/- sbalovacim
// tlacitkem misto vlastniho add-form formulare.
function buildCatBlock(cat) {
  const hasChildren = !!(cat.children && cat.children.length);
  const block = document.createElement("div");
  block.className = "cat-block";
  block.innerHTML = `
    <div class="cat-title-row" data-cat-id="${cat.id}">
      <span>
        <span class="cat-drag-handle" title="Přetažením přesunout">☰</span>
        <span class="cat-toggle${hasChildren ? "" : " spacer"}">+</span>
        <b class="cat-name-label" style="cursor:pointer;">${escapeHtmlAdmin(cat.name)}</b>
      </span>
      <span class="cat-actions">
        <button class="btn-edit-content">Upravit</button>
        <button class="btn-delete danger">Smazat</button>
      </span>
    </div>
    <div class="cat-children"></div>
  `;
  block.querySelector(".btn-delete").onclick = () => deleteCategory(cat);
  const openEdit = () => openCatEditModal(cat);
  block.querySelector(".btn-edit-content").onclick = openEdit;
  block.querySelector(".cat-name-label").onclick = openEdit;
  wireCatDrag(block.querySelector(".cat-title-row"), cat.id);

  const childrenEl = block.querySelector(".cat-children");
  (cat.children || []).forEach(child => {
    childrenEl.appendChild(buildCatChildRow(child, 1));
  });
  if (hasChildren) {
    const toggle = block.querySelector(".cat-toggle");
    if (catExpandedIds.has(cat.id)) {
      childrenEl.classList.add("expanded");
      toggle.textContent = "−";
    }
    toggle.onclick = () => {
      const expanded = childrenEl.classList.toggle("expanded");
      toggle.textContent = expanded ? "−" : "+";
      if (expanded) catExpandedIds.add(cat.id); else catExpandedIds.delete(cat.id);
    };
  }

  return block;
}

// 2. a dalsi uroven - rekurzivni radek, bez omezeni hloubky (produktove
// kategorie prevzate ze skladapp jdou az 4 urovne hluboko). Bez vlastniho
// add-form - pridavani je jen pres jedno tlacitko nahore stromu.
function buildCatChildRow(cat, depth) {
  const hasChildren = !!(cat.children && cat.children.length);
  const wrap = document.createElement("div");
  wrap.className = "cat-child-wrap";

  const row = document.createElement("div");
  row.className = "cat-child-row";
  row.dataset.catId = cat.id;
  row.innerHTML = `
    <span class="cat-drag-handle" title="Přetažením přesunout">☰</span>
    <span class="cat-toggle${hasChildren ? "" : " spacer"}">+</span>
    <span style="flex:1;cursor:pointer;" class="child-name">${escapeHtmlAdmin(cat.name)}</span>
    <button class="btn-edit-content">Upravit</button>
    <button class="btn-delete danger">Smazat</button>
  `;
  const openEdit = () => openCatEditModal(cat);
  row.querySelector(".btn-edit-content").onclick = openEdit;
  row.querySelector(".child-name").onclick = openEdit;
  row.querySelector(".btn-delete").onclick = () => deleteCategory(cat);
  wireCatDrag(row, cat.id);

  wrap.appendChild(row);

  const nestedChildren = document.createElement("div");
  nestedChildren.className = "cat-children-nested";
  (cat.children || []).forEach(grandchild => {
    nestedChildren.appendChild(buildCatChildRow(grandchild, depth + 1));
  });
  wrap.appendChild(nestedChildren);
  if (hasChildren) {
    const toggle = row.querySelector(".cat-toggle");
    if (catExpandedIds.has(cat.id)) {
      nestedChildren.classList.add("expanded");
      toggle.textContent = "−";
    }
    toggle.onclick = () => {
      const expanded = nestedChildren.classList.toggle("expanded");
      toggle.textContent = expanded ? "−" : "+";
      if (expanded) catExpandedIds.add(cat.id); else catExpandedIds.delete(cat.id);
    };
  }

  return wrap;
}

// --- Drag & drop presuny kategorii (Robert 2026-07-26: "strom kategorii
// v administraci udelej ... at s nima lze manipulovat"). Tazeni je
// omezene na uchyt (.cat-drag-handle), aby nekolidovalo s klikanim na
// tlacitka/nazev radku. Poloha kurzoru v ramci radku pri prejezdu urcuje
// efekt: horni ctvrtina radku = "before" (pred cil, stejny rodic jako
// cil), spodni ctvrtina = "after", stredni polovina = "inside" (vnoreni
// jako potomek cile). Po pusteni se cely (klientem jiz mutovany) strom
// preposle najednou na PUT /api/categories/reorder a znovu nacte ze
// serveru (stejny vzor jako u rename/delete - server je zdroj pravdy).
let catDragHandleArmed = false;
let catDraggedId = null;
let catDropRowEl = null;

document.addEventListener("mousedown", (e) => {
  catDragHandleArmed = !!e.target.closest(".cat-drag-handle");
});
document.addEventListener("mouseup", () => { catDragHandleArmed = false; });

function wireCatDrag(rowEl, catId) {
  rowEl.draggable = true;
  rowEl.addEventListener("dragstart", (e) => {
    if (!catDragHandleArmed) { e.preventDefault(); return; }
    catDraggedId = catId;
    rowEl.classList.add("cat-dragging");
    e.dataTransfer.effectAllowed = "move";
    e.dataTransfer.setData("text/plain", String(catId));
  });
  rowEl.addEventListener("dragend", () => {
    rowEl.classList.remove("cat-dragging");
    clearCatDropMarker();
    catDraggedId = null;
  });
  rowEl.addEventListener("dragover", (e) => {
    if (catDraggedId == null || catDraggedId === catId) return;
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
    const rect = rowEl.getBoundingClientRect();
    const ratio = (e.clientY - rect.top) / rect.height;
    const position = ratio < 0.25 ? "before" : ratio > 0.75 ? "after" : "inside";
    setCatDropMarker(rowEl, position);
  });
  rowEl.addEventListener("dragleave", () => {
    if (catDropRowEl === rowEl) clearCatDropMarker();
  });
  rowEl.addEventListener("drop", (e) => {
    e.preventDefault();
    const position = rowEl.dataset.dropPos;
    clearCatDropMarker();
    if (catDraggedId == null || catDraggedId === catId || !position) return;
    moveCategoryNode(catDraggedId, catId, position);
  });
}

function setCatDropMarker(rowEl, position) {
  if (catDropRowEl && catDropRowEl !== rowEl) clearCatDropMarker();
  catDropRowEl = rowEl;
  rowEl.dataset.dropPos = position;
  rowEl.classList.remove("cat-drop-before", "cat-drop-after", "cat-drop-inside");
  rowEl.classList.add(`cat-drop-${position}`);
}

function clearCatDropMarker() {
  if (!catDropRowEl) return;
  catDropRowEl.classList.remove("cat-drop-before", "cat-drop-after", "cat-drop-inside");
  delete catDropRowEl.dataset.dropPos;
  catDropRowEl = null;
}

function findCatNode(nodes, id) {
  for (let i = 0; i < nodes.length; i++) {
    if (nodes[i].id === id) return { node: nodes[i], siblings: nodes };
    const found = findCatNode(nodes[i].children || [], id);
    if (found) return found;
  }
  return null;
}

function collectCatIds(node) {
  let ids = [node.id];
  (node.children || []).forEach(c => { ids = ids.concat(collectCatIds(c)); });
  return ids;
}

function flattenForSave(nodes, parentId) {
  let out = [];
  nodes.forEach((n, idx) => {
    out.push({ id: n.id, parent_id: parentId, sort_order: idx });
    out = out.concat(flattenForSave(n.children || [], n.id));
  });
  return out;
}

async function moveCategoryNode(draggedId, targetId, position) {
  const draggedInfo = findCatNode(catTree, draggedId);
  const targetInfo = findCatNode(catTree, targetId);
  if (!draggedInfo || !targetInfo) return;

  // Cyklus: nelze presunout kategorii do sebe sama ani pod vlastniho
  // (i neprimeho) potomka.
  if (collectCatIds(draggedInfo.node).includes(targetId)) return;

  const oldIndex = draggedInfo.siblings.indexOf(draggedInfo.node);
  draggedInfo.siblings.splice(oldIndex, 1);

  if (position === "inside") {
    targetInfo.node.children = targetInfo.node.children || [];
    targetInfo.node.children.push(draggedInfo.node);
  } else {
    const targetIndex = targetInfo.siblings.indexOf(targetInfo.node);
    const insertAt = position === "before" ? targetIndex : targetIndex + 1;
    targetInfo.siblings.splice(insertAt, 0, draggedInfo.node);
  }

  const items = flattenForSave(catTree, null);
  renderCatTree();
  try {
    const r = await fetch("/api/categories/reorder", {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ items }),
    });
    if (!r.ok) document.getElementById("catErr").textContent = "Nepodařilo se uložit nové pořadí.";
  } catch (e) {
    document.getElementById("catErr").textContent = "Nepodařilo se uložit nové pořadí.";
  }
  loadCategories();
}

function flattenCatTree(nodes, depth) {
  depth = depth || 0;
  let out = [];
  nodes.forEach(n => {
    out.push({ id: n.id, label: "—".repeat(depth) + " " + n.name });
    out = out.concat(flattenCatTree(n.children || [], depth + 1));
  });
  return out;
}

function openCatAddModal() {
  document.getElementById("catAddName").value = "";
  document.getElementById("catAddErr").textContent = "";
  const sel = document.getElementById("catAddParent");
  sel.innerHTML = '<option value="">— (kořenová kategorie)</option>' +
    flattenCatTree(catTree).map(o => `<option value="${o.id}">${escapeHtmlAdmin(o.label)}</option>`).join("");
  document.getElementById("catAddModal").classList.add("open");
  document.getElementById("catAddName").focus();
}

function closeCatAddModal() {
  document.getElementById("catAddModal").classList.remove("open");
}

document.getElementById("btnAddCatTop").onclick = openCatAddModal;
document.getElementById("catAddCancel").onclick = closeCatAddModal;
document.getElementById("catAddModal").addEventListener("click", (e) => {
  if (e.target.id === "catAddModal") closeCatAddModal();
});
document.getElementById("catAddConfirm").onclick = async () => {
  const name = document.getElementById("catAddName").value.trim();
  const parentVal = document.getElementById("catAddParent").value;
  if (!name) { document.getElementById("catAddErr").textContent = "Vyplň název."; return; }
  const r = await fetch("/api/categories", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, parent_id: parentVal ? parseInt(parentVal, 10) : null }),
  });
  const data = await r.json();
  if (!r.ok) { document.getElementById("catAddErr").textContent = data.error || "Chyba."; return; }
  closeCatAddModal();
  loadCategories();
};

async function deleteCategory(cat) {
  if (!confirm(`Smazat kategorii "${cat.name}"${cat.children && cat.children.length ? " i s podkategoriemi" : ""}?`)) return;
  await fetch(`/api/categories/${cat.id}`, { method: "DELETE" });
  loadCategories();
}

// --- Modal "Upravit kategorii" (Robert, "kompletni infrastruktura
// kategorii" dle Shoptet screenshotu, 2026-07-26) - nahrazuje puvodni
// inline "Obsah" panel + samostatny prompt() "Prejmenovat". Vse (nazev,
// URL, horni/spodni popis, obrazek, SEO pole, viditelnost) je na jednom
// miste, zalozky odpovidaji referencnimu Shoptet editoru (bez "Doplnkova
// nastaveni" - Robert vyslovne "bez doplnku").
let cemCatId = null;
let cemQuillIntro = null;
let cemQuillBody = null;
let cemQuillBottom = null;

// Vlozeni fotogalerie primo do textu popisu (Robert: "editor kde
// chceme tlacitko, ktere do tela stranky vlozi tu fotogalerii" - pak
// upresneno: "kdyz tu fotogalerii pouziju, nenabizi mi vyber fotek
// vcetne formatu rozliseni kazde fotky" - kliknuti proto NEVLOZI
// rovnou celou galerii kategorie, ale otevre vyberovy modal
// (cemOpenGalleryPicker): admin zaskrtne, ktere uz nahrane fotky (nebo
// rovnou nahraje nove) chce prave TADY vlozit, a u kazde vybere
// velikost/rozliseni (mala/stredni/velka/puvodni). Vlastni Quill
// BlockEmbed blot "categoryGallery" ulozi VYBRANOU sadu (ne odkaz na
// celou fotobanku kategorie) primo do body_html/bottom_body_html jako
// <div class="cg-embed-gallery" data-images='[{"url":...,"size":...}]'>
// - verejna strana (category.html) je pak vykresli beze potreby
// dalsiho dotazu (viz renderEmbeddedGalleries tam). Funguje obecne pro
// KAZDOU kategorii (parametrizovano aktualnim cemCatId), ne jen pro
// jednu konkretni. Fixni misto galerie mezi popisem a produkty
// (#catGallery, cela fotobanka kategorie) zustava zaroven zachovano
// (Robert: "zachovat obojí").
const CemGalleryBlot = (function () {
  const BlockEmbed = Quill.import("blots/block/embed");
  class GalleryBlot extends BlockEmbed {
    static create(value) {
      const node = super.create();
      const images = value.images || [];
      node.setAttribute("class", "cg-embed-gallery");
      node.setAttribute("data-images", JSON.stringify(images));
      node.setAttribute("contenteditable", "false");
      node.textContent = `🖼️ Fotogalerie (${images.length} ${images.length === 1 ? "fotka" : "fotek"})`;
      return node;
    }
    static value(node) {
      let images = [];
      try { images = JSON.parse(node.getAttribute("data-images") || "[]"); } catch (e) {}
      return { images };
    }
  }
  GalleryBlot.blotName = "categoryGallery";
  GalleryBlot.tagName = "div";
  Quill.register(GalleryBlot);
  return GalleryBlot;
})();
Quill.import("ui/icons")["categoryGallery"] = "🖼️";

// Karusel jako znovupouzitelny blok do textu (Robert 2026-08-06: "smaž
// ten carusel z homepage, prvek jako takový zachovej... přidej prvek
// carusel pro další použití" - stejny princip jako CemGalleryBlot
// vyse, jen misto mrizky nahledu se na verejne strance (category.html
// renderEmbeddedCarousels) vykresli zivy prochazivy karusel. Sdili
// STEJNY vyberovy modal (cemOpenGalleryPicker) pres parametr "mode" -
// karusel na rozdil od galerie nema per-foto velikost (vsechny snimky
// sdili jeden ramecek 16:9), viz cemRefreshGalleryPickerGrid.
const CemCarouselBlot = (function () {
  const BlockEmbed = Quill.import("blots/block/embed");
  class CarouselBlot extends BlockEmbed {
    static create(value) {
      const node = super.create();
      const images = value.images || [];
      node.setAttribute("class", "cg-embed-carousel");
      node.setAttribute("data-images", JSON.stringify(images));
      node.setAttribute("contenteditable", "false");
      node.textContent = `🎠 Karusel (${images.length} ${images.length === 1 ? "fotka" : "fotek"})`;
      return node;
    }
    static value(node) {
      let images = [];
      try { images = JSON.parse(node.getAttribute("data-images") || "[]"); } catch (e) {}
      return { images };
    }
  }
  CarouselBlot.blotName = "categoryCarousel";
  CarouselBlot.tagName = "div";
  Quill.register(CarouselBlot);
  return CarouselBlot;
})();
Quill.import("ui/icons")["categoryCarousel"] = "🎠";
// Robert 2026-08-09 ("chybi mu zobrazeni v html") - ikona pro prepinac
// HTML zdroje, viz cemQuillHtmlHandler.
Quill.import("ui/icons")["html"] = "&lt;/&gt;";

const CEM_GALLERY_SIZES = [
  ["small", "Malá"],
  ["medium", "Střední"],
  ["large", "Velká"],
  ["original", "Původní"],
];

let cemGalleryPickerQuill = null;
let cemGalleryPickerSelected = new Map();
// "gallery" (vychozi) nebo "carousel" - stejny vyberovy modal pro oba,
// jen karusel nema per-foto velikost (viz cemRefreshGalleryPickerGrid)
// a na konci vlozi jiny Quill blot (viz cemGalleryPickerInsertBtn).
let cemGalleryPickerMode = "gallery";

function cemQuillGalleryHandler() {
  if (!cemCatId) return;
  cemOpenGalleryPicker(this.quill, "gallery");
}
function cemQuillCarouselHandler() {
  if (!cemCatId) return;
  cemOpenGalleryPicker(this.quill, "carousel");
}

async function cemOpenGalleryPicker(quillInstance, mode) {
  cemGalleryPickerQuill = quillInstance;
  cemGalleryPickerMode = mode || "gallery";
  cemGalleryPickerSelected = new Map();
  document.getElementById("cemGalleryPickerErr").textContent = "";
  const isCarousel = cemGalleryPickerMode === "carousel";
  document.getElementById("cemGalleryPickerTitle").textContent = isCarousel ? "Vybrat fotky pro karusel" : "Vybrat fotky pro galerii";
  document.getElementById("cemGalleryPickerHint").textContent = isCarousel
    ? "Klikni na fotky, které chceš vložit - pořadí kliknutí určuje pořadí snímků v karuselu."
    : "Klikni na fotky, které chceš vložit, u vybraných zvol velikost/rozlišení.";
  document.getElementById("cemGalleryPicker").classList.add("open");
  await cemRefreshGalleryPickerGrid();
  cemUpdateGalleryPickerCount();
}

function cemCloseGalleryPicker() {
  document.getElementById("cemGalleryPicker").classList.remove("open");
  cemGalleryPickerQuill = null;
  cemGalleryPickerMode = "gallery";
  cemGalleryPickerSelected = new Map();
  document.getElementById("cemGalleryPickerFile").value = "";
}

function cemGalleryPickerSizeOptionsHtml(current) {
  return CEM_GALLERY_SIZES.map(([val, label]) => `<option value="${val}" ${val === current ? "selected" : ""}>${label}</option>`).join("");
}

async function cemRefreshGalleryPickerGrid() {
  const grid = document.getElementById("cemGalleryPickerGrid");
  grid.innerHTML = '<span class="gal-empty">Načítám…</span>';
  const r = await fetch(`/api/gallery-items?owner_type=category&owner_id=${cemCatId}`);
  const data = await r.json();
  const items = data.items || [];
  if (!items.length) {
    grid.innerHTML = '<span class="gal-empty">Zatím žádné fotky u téhle kategorie - nahraj nové níže.</span>';
    return;
  }
  // Karusel nema per-foto velikost (vsechny snimky sdili jeden ramecek
  // 16:9) - dropdown velikosti se tam zobrazuje jen pro galerii.
  const isCarousel = cemGalleryPickerMode === "carousel";
  grid.innerHTML = items.map(it => {
    const picked = cemGalleryPickerSelected.get(String(it.id));
    return `<div class="gal-pick-tile${picked ? " picked" : ""}" data-id="${it.id}" data-url="${it.url}" data-caption="${escapeHtmlAdmin(it.caption || "")}">
      <img src="${it.url}">
      ${picked ? `<span class="gal-pick-check">✓</span>${isCarousel ? "" : `<select class="gal-pick-size">${cemGalleryPickerSizeOptionsHtml(picked.size)}</select>`}` : ""}
    </div>`;
  }).join("");
  grid.querySelectorAll(".gal-pick-tile").forEach(tile => {
    const id = tile.dataset.id;
    tile.onclick = () => {
      if (cemGalleryPickerSelected.has(id)) {
        cemGalleryPickerSelected.delete(id);
      } else {
        cemGalleryPickerSelected.set(id, { url: tile.dataset.url, caption: tile.dataset.caption, size: "medium" });
      }
      cemRefreshGalleryPickerGrid();
      cemUpdateGalleryPickerCount();
    };
    const sizeSel = tile.querySelector(".gal-pick-size");
    if (sizeSel) {
      sizeSel.onclick = (e) => e.stopPropagation();
      sizeSel.onchange = () => {
        const entry = cemGalleryPickerSelected.get(id);
        if (entry) entry.size = sizeSel.value;
      };
    }
  });
}

function cemUpdateGalleryPickerCount() {
  document.getElementById("cemGalleryPickerCount").textContent = cemGalleryPickerSelected.size;
}

document.getElementById("cemGalleryPickerUploadBtn").onclick = async () => {
  const fileInput = document.getElementById("cemGalleryPickerFile");
  if (!fileInput.files.length || !cemCatId) return;
  const fd = new FormData();
  Array.from(fileInput.files).forEach(f => fd.append("files", f));
  fd.append("owner_type", "category");
  fd.append("owner_id", cemCatId);
  const errEl = document.getElementById("cemGalleryPickerErr");
  errEl.textContent = "";
  const r = await fetch("/api/gallery-items", { method: "POST", body: fd });
  const d = await r.json();
  if (!r.ok) { errEl.textContent = d.error || "Nahrání se nezdařilo."; return; }
  fileInput.value = "";
  d.items.forEach(it => cemGalleryPickerSelected.set(String(it.id), { url: it.url, caption: it.caption, size: "medium" }));
  await cemRefreshGalleryPickerGrid();
  cemUpdateGalleryPickerCount();
  if (document.getElementById("cemGallery")) renderGalleryModule(document.getElementById("cemGallery"), "category", cemCatId);
};

document.getElementById("cemGalleryPickerInsertBtn").onclick = () => {
  if (!cemGalleryPickerQuill || !cemGalleryPickerSelected.size) return;
  const images = Array.from(cemGalleryPickerSelected.values());
  const quill = cemGalleryPickerQuill;
  const range = quill.getSelection(true) || { index: quill.getLength() };
  const blotName = cemGalleryPickerMode === "carousel" ? "categoryCarousel" : "categoryGallery";
  quill.insertEmbed(range.index, blotName, { images }, "user");
  quill.setSelection(range.index + 1);
  cemCloseGalleryPicker();
};
document.getElementById("cemGalleryPickerCancel").onclick = cemCloseGalleryPicker;
document.getElementById("cemGalleryPicker").addEventListener("click", (e) => {
  if (e.target.id === "cemGalleryPicker") cemCloseGalleryPicker();
});

// Vlozeni JEDNOTLIVEHO obrazku (Robert: "rozšiř, ať je plnohodnotný a
// nejen syrový" - editor ma mit i bezne "vlozit obrazek", ne jen
// hromadnou galerii). Nahrava se pres stejny /api/gallery-items jako
// fotogalerie (jedna spolecna fotobanka kategorie), vlozi se jako
// normalni <img> na pozici kurzoru a gallery grid nize (#cemGallery)
// se obnovi, aby foto bylo videt i tam.
function cemQuillImageHandler() {
  const quill = this.quill;
  if (!cemCatId) return;
  const input = document.createElement("input");
  input.type = "file";
  input.accept = "image/*";
  input.onchange = async () => {
    if (!input.files.length) return;
    const fd = new FormData();
    fd.append("files", input.files[0]);
    fd.append("owner_type", "category");
    fd.append("owner_id", cemCatId);
    const r = await fetch("/api/gallery-items", { method: "POST", body: fd });
    const d = await r.json();
    if (!r.ok) { alert(d.error || "Nahrání obrázku se nezdařilo."); return; }
    const range = quill.getSelection(true) || { index: quill.getLength() };
    quill.insertEmbed(range.index, "image", d.items[0].url, "user");
    quill.setSelection(range.index + 1);
    if (document.getElementById("cemGallery")) renderGalleryModule(document.getElementById("cemGallery"), "category", cemCatId);
  };
  input.click();
}

// Vlozeni videa (Robert: "rozšířit o vkládání ... videí") - primo v
// textu, na pozici kurzoru, ne jen do samostatneho pole Video URL nize
// (to zustava zachovano soucasne - stejny princip jako u fotogalerie:
// "obojí"). Vlastni prompt + prevod na embed URL (stejna logika jako
// toEmbedUrl() v category.html/product.html), aby fungoval i bezny
// youtube.com/watch?v= odkaz, ne jen uz-embed tvar - Quill vestaveny
// "video" format handler by to bez prevodu nezvladl.
function cemToEmbedUrl(url) {
  const yt = url.match(/(?:youtu\.be\/|youtube\.com\/watch\?v=)([\w-]+)/);
  if (yt) return `https://www.youtube.com/embed/${yt[1]}`;
  return null;
}

function cemQuillVideoHandler() {
  const quill = this.quill;
  const url = (prompt("Vlož odkaz na video (YouTube apod.):") || "").trim();
  if (!url) return;
  const embed = cemToEmbedUrl(url);
  if (!embed) { alert("Nepodařilo se rozpoznat video URL (podporováno YouTube)."); return; }
  const range = quill.getSelection(true) || { index: quill.getLength() };
  quill.insertEmbed(range.index, "video", embed, "user");
  quill.setSelection(range.index + 1);
}

// Robert ("chci smerovat na jiné weby linkem, v hlášce, ale před
// adresu se mi vkládá automaticky vandrawee.cz nechci") - Quillovo
// vychozi tlacitko "Odkaz" bere URL presne tak, jak ji admin napise,
// bez validace schematu. Kdyz nekdo napise jen "www.example.cz" (bez
// "https://"), prohlizec to bere jako RELATIVNI odkaz vuci aktualni
// strance (vysledny href je "https://vandrawee.cz/www.example.cz") -
// presne to nahlasil Robert. Sdileny handler pro VSECHNY editory s
// tlacitkem "link" (Hlášky, Homepage mozaika, Postranní panel, popis
// kategorie) - kdyz zadana adresa nema zadne schema (http/https/
// mailto/tel/...) a nezacina "/" ani "#" (interni/relativni odkaz je
// v poradku beze zmeny), doplni se "https://" automaticky.
function quillLinkHandler(value) {
  const quill = this.quill;
  if (!value) { quill.format("link", false); return; }
  const range = quill.getSelection();
  if (!range || range.length === 0) { alert("Nejprve označ text, který má být odkazem."); return; }
  let url = (prompt("Zadejte URL adresu (např. https://www.example.cz nebo /nazev-kategorie):", "https://") || "").trim();
  if (!url) return;
  if (!/^[a-z][a-z0-9+.-]*:/i.test(url) && !url.startsWith("/") && !url.startsWith("#")) {
    url = "https://" + url;
  }
  quill.format("link", url);
}

// Robert 2026-08-09 ("chybi mu zobrazeni v html") - prepinac na syrovy
// HTML zdroj primo v editoru. Klik poprve schova .ql-editor a misto nej
// vlozi <textarea> s aktualnim quill.root.innerHTML; druhy klik precte
// textarea a aplikuje ho zpet pres dangerouslyPasteHTML (spravne to
// prevede na Quillovu internal Delta reprezentaci, takze pak jde dal
// normalne WYSIWYG editovat).
function cemQuillHtmlHandler() {
  const quill = this.quill;
  const container = quill.container;
  const editorEl = quill.root;
  const existing = container.querySelector("textarea.cem-html-view");
  if (existing) {
    quill.clipboard.dangerouslyPasteHTML(existing.value);
    existing.remove();
    editorEl.style.display = "";
  } else {
    const ta = document.createElement("textarea");
    ta.className = "cem-html-view";
    ta.value = editorEl.innerHTML;
    editorEl.style.display = "none";
    editorEl.insertAdjacentElement("afterend", ta);
    ta.focus();
  }
}

// Plnohodnotny toolbar (Robert: "at je plnohodnotny a nejen syrovy") -
// nadpisy, velikost a font pisma, barva textu/pozadi, zarovnani,
// odsazeni, citace, kod, seznamy, odkaz/obrazek/video, nase galerie,
// clean. Vsechny formaty krome image/video/categoryGallery jsou
// vestavene Quill formaty (zadna dalsi registrace potreba,
// quill.snow.css uz umi jejich dropdowny/color-pickery vykreslit).
const CEM_QUILL_TOOLBAR = {
  container: [
    [{ font: [] }],
    [{ header: [1, 2, 3, false] }],
    [{ size: ["small", false, "large", "huge"] }],
    ["bold", "italic", "underline", "strike"],
    [{ color: [] }, { background: [] }],
    [{ align: [] }],
    ["blockquote", "code-block"],
    [{ list: "ordered" }, { list: "bullet" }],
    [{ indent: "-1" }, { indent: "+1" }],
    ["link", "image", "video"],
    ["categoryGallery", "categoryCarousel"],
    ["html"],
    ["clean"],
  ],
  handlers: {
    link: quillLinkHandler,
    image: cemQuillImageHandler, video: cemQuillVideoHandler,
    categoryGallery: cemQuillGalleryHandler, categoryCarousel: cemQuillCarouselHandler,
    html: cemQuillHtmlHandler,
  },
};

function cemInitQuill() {
  if (cemQuillBody) return;
  cemQuillIntro = new Quill("#cemIntroEditor", { theme: "snow", modules: { toolbar: CEM_QUILL_TOOLBAR } });
  cemQuillBody = new Quill("#cemBodyEditor", { theme: "snow", modules: { toolbar: CEM_QUILL_TOOLBAR } });
  cemQuillBottom = new Quill("#cemBottomEditor", { theme: "snow", modules: { toolbar: CEM_QUILL_TOOLBAR } });
  document.querySelectorAll(".ql-categoryGallery").forEach(btn => { btn.title = "Vložit fotogalerii kategorie"; });
  document.querySelectorAll(".ql-categoryCarousel").forEach(btn => { btn.title = "Vložit karusel kategorie"; });
  document.querySelectorAll(".ql-html").forEach(btn => { btn.title = "Zobrazit/upravit HTML zdroj"; });
}

// Robert 2026-08-09 ("na dlaždici mozaiky homepage... vložit obrazek,
// video, apd... jednoduchy editor") - stejny Quill pattern jako
// CEM_QUILL_TOOLBAR vyse, jen bez categoryGallery/categoryCarousel
// (tyhle custom bloty jsou svazane s kategorii/cemCatId, dlazdice
// homepage mozaiky vlastni fotobanku nema).
function hpbQuillImageHandler() {
  const quill = this.quill;
  if (!hpEditingId) { alert("Nejprve dlaždici uložte, pak lze vkládat obrázky do textu."); return; }
  const input = document.createElement("input");
  input.type = "file";
  input.accept = "image/*";
  input.onchange = async () => {
    if (!input.files.length) return;
    const fd = new FormData();
    fd.append("files", input.files[0]);
    fd.append("owner_type", "homepage_block");
    fd.append("owner_id", hpEditingId);
    const r = await fetch("/api/gallery-items", { method: "POST", body: fd });
    const d = await r.json();
    if (!r.ok) { alert(d.error || "Nahrání obrázku se nezdařilo."); return; }
    const range = quill.getSelection(true) || { index: quill.getLength() };
    quill.insertEmbed(range.index, "image", d.items[0].url, "user");
    quill.setSelection(range.index + 1);
  };
  input.click();
}

const HPB_QUILL_TOOLBAR = {
  container: [
    [{ font: [] }],
    [{ header: [1, 2, 3, false] }],
    [{ size: ["small", false, "large", "huge"] }],
    ["bold", "italic", "underline", "strike"],
    [{ color: [] }, { background: [] }],
    [{ align: [] }],
    ["blockquote", "code-block"],
    [{ list: "ordered" }, { list: "bullet" }],
    [{ indent: "-1" }, { indent: "+1" }],
    ["link", "image", "video"],
    ["html"],
    ["clean"],
  ],
  handlers: {
    link: quillLinkHandler,
    image: hpbQuillImageHandler, video: cemQuillVideoHandler,
    html: cemQuillHtmlHandler,
  },
};

function hpbInitQuill() {
  if (hpbQuill) return;
  hpbQuill = new Quill("#hpbBodyEditor", { theme: "snow", modules: { toolbar: HPB_QUILL_TOOLBAR } });
  document.querySelectorAll(".ql-html").forEach(btn => { btn.title = "Zobrazit/upravit HTML zdroj"; });
}

// bot5 2026-08-10 - Postranni panel, stejny Quill vzor jako hpbInitQuill.
function sbbQuillImageHandler() {
  const quill = this.quill;
  if (!sbEditingId) { alert("Nejprve položku uložte, pak lze vkládat obrázky do textu."); return; }
  const input = document.createElement("input");
  input.type = "file";
  input.accept = "image/*";
  input.onchange = async () => {
    if (!input.files.length) return;
    const fd = new FormData();
    fd.append("files", input.files[0]);
    fd.append("owner_type", "sidebar_block");
    fd.append("owner_id", sbEditingId);
    const r = await fetch("/api/gallery-items", { method: "POST", body: fd });
    const d = await r.json();
    if (!r.ok) { alert(d.error || "Nahrání obrázku se nezdařilo."); return; }
    const range = quill.getSelection(true) || { index: quill.getLength() };
    quill.insertEmbed(range.index, "image", d.items[0].url, "user");
    quill.setSelection(range.index + 1);
  };
  input.click();
}
const SBB_QUILL_TOOLBAR = {
  container: [
    [{ font: [] }],
    [{ header: [1, 2, 3, false] }],
    [{ size: ["small", false, "large", "huge"] }],
    ["bold", "italic", "underline", "strike"],
    [{ color: [] }, { background: [] }],
    [{ align: [] }],
    ["blockquote", "code-block"],
    [{ list: "ordered" }, { list: "bullet" }],
    [{ indent: "-1" }, { indent: "+1" }],
    ["link", "image", "video"],
    ["html"],
    ["clean"],
  ],
  handlers: {
    link: quillLinkHandler,
    image: sbbQuillImageHandler, video: cemQuillVideoHandler,
    html: cemQuillHtmlHandler,
  },
};
function sbbInitQuill() {
  if (sbbQuill) return;
  sbbQuill = new Quill("#sbbBodyEditor", { theme: "snow", modules: { toolbar: SBB_QUILL_TOOLBAR } });
  document.querySelectorAll(".ql-html").forEach(btn => { btn.title = "Zobrazit/upravit HTML zdroj"; });
}

function cemSwitchTab(tabName) {
  document.querySelectorAll(".cem-tab").forEach(b => b.classList.toggle("active", b.dataset.tab === tabName));
  document.querySelectorAll(".cem-panel").forEach(p => { p.hidden = p.dataset.panel !== tabName; });
}
document.querySelectorAll(".cem-tab").forEach(btn => {
  btn.onclick = () => cemSwitchTab(btn.dataset.tab);
});

function cemSetImagePreview(imgId, removeBtnId, filename) {
  const img = document.getElementById(imgId);
  const removeBtn = document.getElementById(removeBtnId);
  if (filename) {
    img.src = `/content-files/categories/${filename}`;
    img.style.display = "";
    removeBtn.style.display = "";
  } else {
    img.style.display = "none";
    removeBtn.style.display = "none";
  }
}

async function cemRefreshFiles() {
  const r = await fetch(`/api/categories/${cemCatId}/content`);
  const data = await r.json();
  renderFileList(document.getElementById("cemFiles"), data.files || [], cemCatId, cemRefreshFiles);
}

function cemUpdateSeoWidgets() {
  const title = document.getElementById("cemMetaTitle").value.trim() || document.getElementById("cemName").value.trim();
  const desc = document.getElementById("cemMetaDescription").value.trim();
  const slug = document.getElementById("cemSlug").value.trim();
  const keyword = document.getElementById("cemFocusKeyword").value.trim().toLowerCase();
  const bodyText = cemQuillBody ? cemQuillBody.getText().trim() : "";

  const titleLen = title.length, descLen = desc.length;
  const titleCounter = document.getElementById("cemTitleCounter");
  titleCounter.textContent = `${titleLen} / 60`;
  titleCounter.className = "cem-seo-counter" + (titleLen > 60 ? " bad" : titleLen > 50 ? " warn" : "");
  const descCounter = document.getElementById("cemDescCounter");
  descCounter.textContent = `${descLen} / 156`;
  descCounter.className = "cem-seo-counter" + (descLen > 156 ? " bad" : descLen < 50 ? " warn" : "");

  document.getElementById("cemSerpUrl").textContent = `konfigurator3d.cz › kategorie › ${slug || "…"}`;
  document.getElementById("cemSerpTitle").textContent = title || "Název kategorie – Hliníkový konstrukční stavebnicový systém s drážkami";
  document.getElementById("cemSerpDesc").textContent = desc || "Stručný popis pro vyhledávače…";

  const checklist = document.getElementById("cemSeoChecklist");
  if (!keyword) {
    checklist.innerHTML = '<li>Vyplň klíčové slovo pro kontrolu jeho použití v title/popisu/URL/textu.</li>';
    return;
  }
  const checks = [
    { label: "V title (tag title)", ok: title.toLowerCase().includes(keyword) },
    { label: "V meta popisu", ok: desc.toLowerCase().includes(keyword) },
    { label: "V URL adrese (slugu)", ok: slug.toLowerCase().includes(_seoSlugify(keyword)) },
    { label: "V textu kategorie", ok: bodyText.toLowerCase().includes(keyword) },
  ];
  checklist.innerHTML = checks.map(c => `<li class="${c.ok ? "ok" : "bad"}">${c.ok ? "✓" : "✗"} ${c.label}</li>`).join("");
}
function _seoSlugify(s) {
  return (s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
}
["cemName", "cemMetaTitle", "cemMetaDescription", "cemSlug", "cemFocusKeyword"].forEach(id => {
  document.getElementById(id).addEventListener("input", cemUpdateSeoWidgets);
});

async function openCatEditModal(cat) {
  cemCatId = cat.id;
  cemInitQuill();
  cemSwitchTab("general");
  document.getElementById("cemCatName").textContent = `— ${cat.name}`;
  document.getElementById("cemErr").textContent = "";
  document.getElementById("cemStatus").textContent = "";
  document.getElementById("cemImageInput").value = "";
  document.getElementById("cemOgImageInput").value = "";
  document.getElementById("catEditModal").classList.add("open");

  const r = await fetch(`/api/categories/${cat.id}/content`);
  const data = await r.json();
  if (!r.ok) {
    document.getElementById("cemErr").textContent = data.error || "Nepodařilo se načíst kategorii.";
    return;
  }
  const c = data.category, page = data.page || {};

  document.getElementById("cemName").value = c.name || "";
  document.getElementById("cemSlug").value = c.slug || "";
  cemQuillIntro.root.innerHTML = page.intro_html || "";
  cemQuillBody.root.innerHTML = page.body_html || "";
  cemQuillBottom.root.innerHTML = page.bottom_body_html || "";
  document.getElementById("cemVideo").value = page.video_url || "";
  cemSetImagePreview("cemImagePreview", "cemImageRemove", c.image_filename);
  renderGalleryModule(document.getElementById("cemGallery"), "category", cat.id);
  renderGalleryModule(document.getElementById("cemGallery"), "category", cat.id);

  document.getElementById("cemNavLabel").value = c.nav_label || "";
  document.getElementById("cemMetaTitle").value = c.meta_title || "";
  document.getElementById("cemMetaDescription").value = c.meta_description || "";
  document.getElementById("cemFocusKeyword").value = c.focus_keyword || "";
  cemUpdateSeoWidgets();
  cemSetImagePreview("cemOgImagePreview", "cemOgImageRemove", c.og_image_filename);

  document.getElementById("cemVisible").checked = c.is_visible !== false;
  document.getElementById("cemMenuExpanded").checked = !!c.menu_expanded;
  document.getElementById("cemDogusCoef").value = c.dogus_price_coefficient ?? "";

  renderFileList(document.getElementById("cemFiles"), data.files || [], cat.id, cemRefreshFiles);
}

function closeCatEditModal() {
  document.getElementById("catEditModal").classList.remove("open");
  cemCatId = null;
}
document.getElementById("cemClose").onclick = closeCatEditModal;
document.getElementById("cemCancel").onclick = closeCatEditModal;

// Robert 2026-08-10 ("u vypsaných chyb mi dávej k odkliknutí: opravit
// a doplnit") - #qaAuditPanel na Dashboardu potrebuje otevrit editaci
// kategorie jen podle id (openCatEditModal chce cely {id,name} objekt,
// ktery na Dashboardu neni po ruce - vse ostatni si funkce stejne
// dotahne az z /api/categories/<id>/content). Meta popis (SEO) je na
// zalozce "Pokročilé", proto tam po otevreni rovnou prepneme.
function qaOpenCategoryEdit(id) {
  openCatEditModal({ id, name: "" }).then(() => cemSwitchTab("advanced"));
}
document.getElementById("catEditModal").addEventListener("click", (e) => {
  if (e.target.id === "catEditModal") closeCatEditModal();
});

document.getElementById("cemSave").onclick = async () => {
  if (!cemCatId) return;
  const status = document.getElementById("cemStatus");
  const err = document.getElementById("cemErr");
  err.textContent = "";
  const name = document.getElementById("cemName").value.trim();
  if (!name) { err.textContent = "Vyplň název."; return; }
  status.textContent = "ukládám…";
  try {
    const r1 = await fetch(`/api/categories/${cemCatId}`, {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name,
        slug: document.getElementById("cemSlug").value.trim(),
        nav_label: document.getElementById("cemNavLabel").value.trim(),
        meta_title: document.getElementById("cemMetaTitle").value.trim(),
        meta_description: document.getElementById("cemMetaDescription").value.trim(),
        focus_keyword: document.getElementById("cemFocusKeyword").value.trim(),
        is_visible: document.getElementById("cemVisible").checked,
        menu_expanded: document.getElementById("cemMenuExpanded").checked,
        dogus_price_coefficient: document.getElementById("cemDogusCoef").value.trim() || null,
      }),
    });
    const d1 = await r1.json();
    if (!r1.ok) throw new Error(d1.error || "Nepodařilo se uložit kategorii.");

    const r2 = await fetch(`/api/categories/${cemCatId}/content`, {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title: name,
        intro_html: cemQuillIntro.root.innerHTML,
        body_html: cemQuillBody.root.innerHTML,
        bottom_body_html: cemQuillBottom.root.innerHTML,
        video_url: document.getElementById("cemVideo").value.trim(),
      }),
    });
    const d2 = await r2.json();
    if (!r2.ok) throw new Error(d2.error || "Nepodařilo se uložit obsah.");

    status.textContent = "uloženo ✓";
    setTimeout(() => { status.textContent = ""; }, 2000);
    loadCategories();
  } catch (e) {
    status.textContent = "";
    err.textContent = e.message;
  }
};

async function cemUploadImage(inputId, endpoint, previewId, removeBtnId) {
  const input = document.getElementById(inputId);
  if (!input.files.length || !cemCatId) return;
  const fd = new FormData();
  fd.append("file", input.files[0]);
  const r = await fetch(`/api/categories/${cemCatId}/${endpoint}`, { method: "POST", body: fd });
  const d = await r.json();
  if (!r.ok) { document.getElementById("cemErr").textContent = d.error || "Nepodařilo se nahrát obrázek."; return; }
  input.value = "";
  cemSetImagePreview(previewId, removeBtnId, d.image_filename || d.og_image_filename);
}
document.getElementById("cemImageInput").onchange = () => cemUploadImage("cemImageInput", "image", "cemImagePreview", "cemImageRemove");
document.getElementById("cemOgImageInput").onchange = () => cemUploadImage("cemOgImageInput", "og-image", "cemOgImagePreview", "cemOgImageRemove");

document.getElementById("cemImageRemove").onclick = async () => {
  if (!cemCatId) return;
  await fetch(`/api/categories/${cemCatId}/image`, { method: "DELETE" });
  cemSetImagePreview("cemImagePreview", "cemImageRemove", null);
};
document.getElementById("cemOgImageRemove").onclick = async () => {
  if (!cemCatId) return;
  await fetch(`/api/categories/${cemCatId}/og-image`, { method: "DELETE" });
  cemSetImagePreview("cemOgImagePreview", "cemOgImageRemove", null);
};

document.getElementById("cemFileUpload").onclick = async () => {
  const fileInput = document.getElementById("cemFileInput");
  if (!fileInput.files.length || !cemCatId) return;
  const fd = new FormData();
  fd.append("file", fileInput.files[0]);
  await fetch(`/api/categories/${cemCatId}/files`, { method: "POST", body: fd });
  fileInput.value = "";
  cemRefreshFiles();
};

function renderFileList(container, files, catId, onChange) {
  container.innerHTML = files.length ? "" : '<span style="color:#666;font-size:12px;">Žádné soubory.</span>';
  files.forEach(f => {
    const row = document.createElement("div");
    row.style.display = "flex";
    row.style.alignItems = "center";
    row.style.gap = "8px";
    row.innerHTML = `<a href="/content-files/${f.stored_name}" target="_blank">📄 ${f.filename}</a> <button class="danger" style="padding:2px 8px;font-size:11px;">Smazat</button>`;
    row.querySelector("button").onclick = async () => {
      await fetch(`/api/categories/files/${f.id}`, { method: "DELETE" });
      onChange();
    };
    container.appendChild(row);
  });
}

// ==================== FOTOGALERIE (obecny, pripojitelny modul) ====================
// Robert: "vytvor modul fotogalerie tak aby se to dalo pridavat kdykoliv
// pozdeji v administraci do kategorii do obsahu kategorie nebo k
// samotnym produktum katalogu" - jeden znovupouzitelny widget nad
// /api/gallery-items (viz api/gallery_items.py), volany
// renderGalleryModule(container, "category"|"product", ownerId) - ted
// zapojen v modalu "Upravit kategorii" (#cemGallery) i ve Skladove karte
// produktu (#stockCardGallery), pripojeni k dalsim mistum v budoucnu je
// jen otazka zavolani teto funkce na novem kontejneru.
let galDragHandleArmed = false;
let galDraggedId = null;
document.addEventListener("mousedown", (e) => {
  if (e.target.closest(".gal-drag-handle")) galDragHandleArmed = true;
});
document.addEventListener("mouseup", () => { galDragHandleArmed = false; });

// Lightbox pro zvetseni fotky/videa PRIMO v adminu (Robert: fotka
// otevrena pres <a target="_blank"> nesla zpatky zavrit - zadne UI na
// zavreni na mobilu/PWA bez adresniho radku). Sdileny jeden overlay
// pro renderGalleryModule i Foto kos.
function openImgLightbox(url, isVideo) {
  const img = document.getElementById("imgLightboxImg");
  const video = document.getElementById("imgLightboxVideo");
  if (isVideo) {
    video.src = url; video.classList.add("show"); img.classList.remove("show"); img.src = "";
  } else {
    img.src = url; img.classList.add("show"); video.classList.remove("show"); video.pause(); video.src = "";
  }
  document.getElementById("imgLightbox").classList.add("open");
}
function closeImgLightbox() {
  document.getElementById("imgLightbox").classList.remove("open");
  const video = document.getElementById("imgLightboxVideo");
  video.pause(); video.src = "";
}
document.getElementById("imgLightboxClose").onclick = closeImgLightbox;
document.getElementById("imgLightbox").addEventListener("click", (e) => {
  if (e.target.id === "imgLightbox") closeImgLightbox();
});

// Prohlizec PDF primo v adminu - viz komentar u #pdfViewer v <style>.
// Sdileny jeden overlay pro vsechna mista, ktera dosud otevirala PDF
// pres target="_blank"/window.open (doklady v objednavce, zalozka Doklady).
function openPdfViewer(url) {
  document.getElementById("pdfViewerFrame").src = url;
  document.getElementById("pdfViewer").classList.add("open");
}
function closePdfViewer() {
  document.getElementById("pdfViewer").classList.remove("open");
  document.getElementById("pdfViewerFrame").src = "";
}
document.getElementById("pdfViewerClose").onclick = closePdfViewer;
document.getElementById("pdfViewer").addEventListener("click", (e) => {
  if (e.target.id === "pdfViewer") closePdfViewer();
});

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    closeImgLightbox(); closePdfViewer();
    document.getElementById("incomingDocDetailModal")?.classList.remove("open");
  }
});

async function renderGalleryModule(container, ownerType, ownerId) {
  // bot10, 2026-09-12 (centralni fotogalerie): fotka kategorie muze byt
  // v libovolnem poctu kategorii zaroven (M:N) - "Smazat" v pohledu JEDNE
  // kategorie proto nesmi znicit soubor/knihovni zaznam, jen zrusit
  // prirazeni SEM (bot3/Robert: "tlačítko v pohledu jedné kategorie nemá
  // právo smazat něco, co vidí i jiná kategorie"). Skutecne trvale smazani
  // z knihovny zije jen v nove centralni obrazovce. Ostatni owner_type
  // (produkt/dokument/objednavka/...) zustavaji na dnesnim chovani -
  // zadne M:N, "Smazat" tam pořád znamena trvale smazat.
  const isSharedLibrary = ownerType === "category";
  container.innerHTML = `
    <div class="gal-grid"></div>
    <div class="gal-toolbar">
      <button class="gal-capture-btn">📷 Vyfotit</button>
      <input type="file" class="gal-file-input" multiple accept="image/*">
      <button class="gal-upload-btn">Nahrát fotky</button>
      <input type="url" class="gal-url-input" placeholder="URL obrázku…">
      <button class="gal-url-btn">Přidat z URL</button>
      ${isSharedLibrary ? '<button class="gal-pick-library-btn">📁 Vybrat z knihovny</button>' : ""}
      <label style="font-size:12px;margin-left:8px;"><input type="checkbox" class="gal-select-all"> Vybrat vše</label>
      <button class="gal-bulk-delete danger" style="display:none;">Smazat vybrané</button>
    </div>
    <div class="gal-err err"></div>
  `;
  const grid = container.querySelector(".gal-grid");
  const errEl = container.querySelector(".gal-err");
  const fileInput = container.querySelector(".gal-file-input");
  const urlInput = container.querySelector(".gal-url-input");
  // Robert 2026-08 ("proc nejde mazat bulk soubory v produktech?"):
  // galerie mela jen jednotlive mazani krizkem - hromadny vyber
  // (checkbox na dlazdici + Vybrat vse + Smazat vybrane) doplnen.
  // Vyber je lokalni pro instanci modulu (kazdy produkt/kategorie/... ma
  // svou galerii), backend bulk endpoint neni potreba - smaze se
  // paralelne po jednotlivych DELETE (fotek u vlastnika byva do desitek).
  const galSelectedIds = new Set();
  const bulkDeleteBtn = container.querySelector(".gal-bulk-delete");
  const selectAllCb = container.querySelector(".gal-select-all");
  function updateGalBulkUi(itemCount) {
    bulkDeleteBtn.style.display = galSelectedIds.size ? "" : "none";
    bulkDeleteBtn.textContent = isSharedLibrary
      ? `Odebrat vybrané odsud (${galSelectedIds.size})`
      : `Smazat vybrané (${galSelectedIds.size})`;
    selectAllCb.checked = itemCount > 0 && galSelectedIds.size === itemCount;
  }
  bulkDeleteBtn.onclick = async () => {
    if (!galSelectedIds.size) return;
    const confirmMsg = isSharedLibrary
      ? `Odebrat ${galSelectedIds.size} vybraných fotek z téhle kategorie? Fotky zůstanou v knihovně a v ostatních kategoriích, kde jsou přiřazené.`
      : `Trvale smazat ${galSelectedIds.size} vybraných souborů? Tohle nejde vrátit.`;
    if (!confirm(confirmMsg)) return;
    await Promise.all([...galSelectedIds].map(id =>
      fetch(`/api/gallery-items/${id}?owner_type=${encodeURIComponent(ownerType)}&owner_id=${ownerId}`, { method: "DELETE" })));
    galSelectedIds.clear();
    refresh();
  };

  async function refresh() {
    errEl.textContent = "";
    const r = await fetch(`/api/gallery-items?owner_type=${ownerType}&owner_id=${ownerId}`);
    const data = await r.json();
    if (!r.ok) { errEl.textContent = data.error || "Nepodařilo se načíst fotky."; return; }
    renderGrid(data.items || []);
  }

  function renderGrid(items) {
    grid.innerHTML = "";
    // vyber ocistit o polozky, ktere uz neexistuji (po refresh/mazani)
    const liveIds = new Set(items.map(i => i.id));
    [...galSelectedIds].forEach(id => { if (!liveIds.has(id)) galSelectedIds.delete(id); });
    selectAllCb.onchange = () => {
      if (selectAllCb.checked) items.forEach(i => galSelectedIds.add(i.id));
      else galSelectedIds.clear();
      renderGrid(items);
    };
    updateGalBulkUi(items.length);
    if (!items.length) {
      grid.innerHTML = '<span class="gal-empty">Zatím žádné fotky.</span>';
      return;
    }
    items.forEach(item => {
      const tile = document.createElement("div");
      tile.className = "gal-tile";
      tile.dataset.id = item.id;
      const mediaHtml = item.media_type === "video"
        ? `<video src="${item.url}" muted playsinline preload="metadata"></video><span class="gal-video-badge">▶ video</span>`
        : `<img src="${item.url}" loading="lazy" alt="">`;
      const audioHtml = item.audio_url ? `<audio controls src="${item.audio_url}"></audio>` : "";
      tile.innerHTML = `
        <span class="gal-drag-handle" title="Přetažením přeuspořádat">☰</span>
        <input type="checkbox" class="gal-select-cb" title="Vybrat" ${galSelectedIds.has(item.id) ? "checked" : ""}
               style="position:absolute;top:2px;left:26px;z-index:3;width:16px;height:16px;">
        <span class="gal-media-open" title="Zvětšit">${mediaHtml}</span>
        ${audioHtml}
        <button class="gal-delete danger" title="${isSharedLibrary ? "Odebrat odsud" : "Smazat"}">${isSharedLibrary ? "↩" : "✕"}</button>
      `;
      tile.querySelector(".gal-select-cb").onchange = (e) => {
        if (e.target.checked) galSelectedIds.add(item.id); else galSelectedIds.delete(item.id);
        updateGalBulkUi(items.length);
      };
      tile.querySelector(".gal-media-open").onclick = () => {
        openImgLightbox(item.url, item.media_type === "video");
      };
      tile.querySelector(".gal-delete").onclick = async () => {
        const confirmMsg = isSharedLibrary
          ? "Odebrat fotku z téhle kategorie? Zůstane v knihovně a v ostatních kategoriích, kde je přiřazená."
          : "Smazat fotku?";
        if (!confirm(confirmMsg)) return;
        await fetch(`/api/gallery-items/${item.id}?owner_type=${encodeURIComponent(ownerType)}&owner_id=${ownerId}`, { method: "DELETE" });
        refresh();
      };
      tile.draggable = true;
      tile.addEventListener("dragstart", (e) => {
        if (!galDragHandleArmed) { e.preventDefault(); return; }
        galDraggedId = String(item.id);
        tile.classList.add("gal-dragging");
        e.dataTransfer.effectAllowed = "move";
      });
      tile.addEventListener("dragend", () => { tile.classList.remove("gal-dragging"); galDraggedId = null; });
      tile.addEventListener("dragover", (e) => {
        if (!galDraggedId || galDraggedId === tile.dataset.id) return;
        e.preventDefault();
        tile.classList.add("gal-drop-target");
      });
      tile.addEventListener("dragleave", () => tile.classList.remove("gal-drop-target"));
      tile.addEventListener("drop", async (e) => {
        e.preventDefault();
        tile.classList.remove("gal-drop-target");
        const draggedId = galDraggedId;
        const targetId = tile.dataset.id;
        if (!draggedId || draggedId === targetId) return;
        const ids = Array.from(grid.children).map(el => el.dataset.id);
        const fromIdx = ids.indexOf(draggedId);
        const toIdx = ids.indexOf(targetId);
        if (fromIdx === -1 || toIdx === -1) return;
        ids.splice(fromIdx, 1);
        ids.splice(toIdx, 0, draggedId);
        await fetch("/api/gallery-items/reorder", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ owner_type: ownerType, owner_id: ownerId, ids: ids.map(Number) }),
        });
        refresh();
      });
      grid.appendChild(tile);
    });
  }

  container.querySelector(".gal-capture-btn").onclick = () => {
    openCameraCaptureModal(ownerType, ownerId, refresh);
  };
  container.querySelector(".gal-upload-btn").onclick = async () => {
    if (!fileInput.files.length) return;
    const fd = new FormData();
    Array.from(fileInput.files).forEach(f => fd.append("files", f));
    fd.append("owner_type", ownerType);
    fd.append("owner_id", ownerId);
    const r = await fetch("/api/gallery-items", { method: "POST", body: fd });
    const d = await r.json();
    if (!r.ok) { errEl.textContent = d.error || "Nahrání se nezdařilo."; return; }
    fileInput.value = "";
    refresh();
  };
  container.querySelector(".gal-url-btn").onclick = async () => {
    const url = urlInput.value.trim();
    if (!url) return;
    const r = await fetch("/api/gallery-items/import-url", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ owner_type: ownerType, owner_id: ownerId, url }),
    });
    const d = await r.json();
    if (!r.ok) { errEl.textContent = d.error || "Import se nezdařil."; return; }
    urlInput.value = "";
    refresh();
  };
  // bot16, 2026-09-13 (Robert primo: "v kazde kategorii eshopu... se
  // nabidne adminovi moznost vlozit fotky z centralni fotogalerie coz
  // se provaze zaroven s tim zarazovanim v adminu fotogalerie, ktere uz
  // tam je") - misto vytvareni druheho zarazovaciho mechanismu jen
  // dopise TUHLE kategorii do stavajiciho seznamu vybrane fotky
  // (photo.categories, uz nactene pickerem) a posle STEJNYM endpointem,
  // jaky pouziva Knihovna fotek (api/gallery.py gallery_library_update) -
  // fotka pak vidi svoje prirazeni na obou mistech, zadna duplicita dat.
  const pickLibraryBtn = container.querySelector(".gal-pick-library-btn");
  if (pickLibraryBtn) {
    pickLibraryBtn.onclick = () => {
      openGalleryLibraryPicker(async (photo) => {
        errEl.textContent = "";
        const categoryIds = (photo.categories || []).map(c => c.id);
        if (!categoryIds.includes(Number(ownerId))) categoryIds.push(Number(ownerId));
        try {
          const r = await fetch(`/api/admin/gallery/library/${photo.id}`, {
            method: "PUT", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ category_ids: categoryIds }),
          });
          const d = await r.json().catch(() => ({}));
          if (!r.ok) { errEl.textContent = d.error || "Přiřazení se nezdařilo."; return; }
          refresh();
        } catch (e) {
          errEl.textContent = "Přiřazení se nezdařilo (chyba spojení).";
        }
      });
    };
  }

  await refresh();
}

// ==================== FOTOAPARAT V ADMINU (foto/video + zvuk + GPS) ====================
// Robert 2026-07-31: prenest "foceni a ukladani" z projektu Photosss.
// Ziva nahled kamera (getUserMedia) + spoust -> canvas -> JPEG blob, NEBO
// prepnuti na nahravani videa (samostatny stream s audio:true jen kdyz
// se video opravdu naharava, kvuli jednoduchosti preview streamu).
// Volitelna zvukova poznamka (samostatny mic-only MediaRecorder,
// nezavisly na video streamu) a volitelna GPS poloha.
let camState = null; // { ownerType, ownerId, onDone, previewStream, recStream, mediaRecorder, recordedChunks, capturedBlob, mediaType, audioRecorder, audioChunks, audioBlob, lat, lon }

function camStopAllTracks() {
  if (!camState) return;
  [camState.previewStream, camState.recStream, camState.audioStream].forEach(s => {
    if (s) s.getTracks().forEach(t => t.stop());
  });
}

async function openCameraCaptureModal(ownerType, ownerId, onDone) {
  if (!navigator.mediaDevices || !window.isSecureContext) {
    alert("Fotoaparát vyžaduje zabezpečené připojení (HTTPS). Otevři admin na https://80-211-210-103.sslip.io:8091/admin.html");
    return;
  }
  const modal = document.getElementById("camCaptureModal");
  const preview = document.getElementById("camPreview");
  const canvas = document.getElementById("camCanvas");
  const errEl = document.getElementById("camErr");
  const statusEl = document.getElementById("camStatus");
  const geoStatusEl = document.getElementById("camGeoStatus");
  const shutterBtn = document.getElementById("camShutterBtn");
  const videoToggleBtn = document.getElementById("camVideoToggleBtn");
  const audioToggleBtn = document.getElementById("camAudioToggleBtn");
  const geoToggleBtn = document.getElementById("camGeoToggleBtn");
  const confirmBtn = document.getElementById("camConfirmBtn");
  const retakeBtn = document.getElementById("camRetakeBtn");

  camState = {
    ownerType, ownerId, onDone, previewStream: null, recStream: null, audioStream: null,
    mediaRecorder: null, recordedChunks: [], capturedBlob: null, mediaType: null,
    audioRecorder: null, audioChunks: [], audioBlob: null, lat: null, lon: null,
  };
  errEl.textContent = ""; statusEl.textContent = ""; geoStatusEl.textContent = "";
  confirmBtn.disabled = true;
  retakeBtn.style.display = "none";
  canvas.style.display = "none";
  preview.style.display = "";
  videoToggleBtn.textContent = "🎥 Nahrát video";
  videoToggleBtn.classList.remove("active");
  audioToggleBtn.textContent = "🎙️ Hlasová poznámka";
  audioToggleBtn.classList.remove("active");

  try {
    camState.previewStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } });
    preview.srcObject = camState.previewStream;
  } catch (e) {
    errEl.textContent = "Nepodařilo se otevřít kameru: " + e.message;
  }
  modal.classList.add("open");

  shutterBtn.onclick = () => {
    canvas.width = preview.videoWidth || 1280;
    canvas.height = preview.videoHeight || 720;
    canvas.getContext("2d").drawImage(preview, 0, 0, canvas.width, canvas.height);
    canvas.toBlob(blob => {
      camState.capturedBlob = blob;
      camState.mediaType = "image";
      confirmBtn.disabled = false;
      statusEl.textContent = "Foto pořízeno.";
    }, "image/jpeg", 0.85);
    canvas.style.display = "";
    preview.style.display = "none";
    retakeBtn.style.display = "";
  };

  videoToggleBtn.onclick = async () => {
    if (camState.mediaRecorder && camState.mediaRecorder.state === "recording") {
      camState.mediaRecorder.stop();
      return;
    }
    try {
      camState.recStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" }, audio: true });
    } catch (e) {
      errEl.textContent = "Nepodařilo se spustit záznam videa: " + e.message;
      return;
    }
    preview.srcObject = camState.recStream;
    camState.recordedChunks = [];
    camState.mediaRecorder = new MediaRecorder(camState.recStream, { mimeType: "video/webm" });
    camState.mediaRecorder.ondataavailable = e => { if (e.data.size) camState.recordedChunks.push(e.data); };
    camState.mediaRecorder.onstop = () => {
      camState.capturedBlob = new Blob(camState.recordedChunks, { type: "video/webm" });
      camState.mediaType = "video";
      confirmBtn.disabled = false;
      statusEl.textContent = "Video nahráno.";
      videoToggleBtn.textContent = "🎥 Nahrát video";
      videoToggleBtn.classList.remove("active");
      camState.recStream.getTracks().forEach(t => t.stop());
    };
    camState.mediaRecorder.start();
    videoToggleBtn.textContent = "⏹ Zastavit nahrávání";
    videoToggleBtn.classList.add("active");
    statusEl.textContent = "Nahrávám video…";
  };

  audioToggleBtn.onclick = async () => {
    if (camState.audioRecorder && camState.audioRecorder.state === "recording") {
      camState.audioRecorder.stop();
      return;
    }
    try {
      camState.audioStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (e) {
      errEl.textContent = "Nepodařilo se spustit mikrofon: " + e.message;
      return;
    }
    camState.audioChunks = [];
    camState.audioRecorder = new MediaRecorder(camState.audioStream, { mimeType: "audio/webm" });
    camState.audioRecorder.ondataavailable = e => { if (e.data.size) camState.audioChunks.push(e.data); };
    camState.audioRecorder.onstop = () => {
      camState.audioBlob = new Blob(camState.audioChunks, { type: "audio/webm" });
      audioToggleBtn.textContent = "🎙️ Hlasová poznámka (nahráno)";
      audioToggleBtn.classList.remove("active");
      camState.audioStream.getTracks().forEach(t => t.stop());
    };
    camState.audioRecorder.start();
    audioToggleBtn.textContent = "⏹ Zastavit poznámku";
    audioToggleBtn.classList.add("active");
  };

  geoToggleBtn.onclick = () => {
    if (!navigator.geolocation) { geoStatusEl.textContent = "Poloha není v tomto prohlížeči dostupná."; return; }
    geoStatusEl.textContent = "Zjišťuji polohu…";
    navigator.geolocation.getCurrentPosition(
      pos => {
        camState.lat = pos.coords.latitude;
        camState.lon = pos.coords.longitude;
        geoStatusEl.textContent = `Poloha: ${camState.lat.toFixed(5)}, ${camState.lon.toFixed(5)}`;
      },
      err => { geoStatusEl.textContent = "Polohu se nepodařilo zjistit: " + err.message; },
      { timeout: 10000 }
    );
  };

  retakeBtn.onclick = () => {
    camState.capturedBlob = null;
    camState.mediaType = null;
    confirmBtn.disabled = true;
    canvas.style.display = "none";
    preview.style.display = "";
    retakeBtn.style.display = "none";
    statusEl.textContent = "";
  };

  confirmBtn.onclick = async () => {
    if (!camState.capturedBlob) return;
    errEl.textContent = "";
    const fd = new FormData();
    fd.append("owner_type", camState.ownerType);
    fd.append("owner_id", camState.ownerId);
    fd.append("media_type", camState.mediaType);
    fd.append("media", camState.capturedBlob, camState.mediaType === "video" ? "capture.webm" : "capture.jpg");
    if (camState.audioBlob) fd.append("audio", camState.audioBlob, "note.webm");
    if (camState.lat != null) fd.append("latitude", camState.lat);
    if (camState.lon != null) fd.append("longitude", camState.lon);
    const r = await fetch("/api/gallery-items/capture", { method: "POST", body: fd });
    const d = await r.json();
    if (!r.ok) { errEl.textContent = d.error || "Uložení se nezdařilo."; return; }
    const done = camState.onDone;
    camCloseCaptureModal();
    if (done) done();
  };

  document.getElementById("camCancelBtn").onclick = camCloseCaptureModal;
}

function camCloseCaptureModal() {
  camStopAllTracks();
  document.getElementById("camCaptureModal").classList.remove("open");
  camState = null;
}

document.getElementById("camCaptureModal").addEventListener("click", (e) => {
  if (e.target.id === "camCaptureModal") camCloseCaptureModal();
});

// Sdileny mini-modal pro plochy bez vlastniho gallery kontejneru
// (doklady/skladove pohyby/polozky nakupni objednavky).
function openAttachmentModal(ownerType, ownerId, label) {
  document.getElementById("attachMiannModalTitle").textContent = label;
  const body = document.getElementById("attachMiannModalBody");
  body.innerHTML = "";
  document.getElementById("attachMiannModal").classList.add("open");
  renderGalleryModule(body, ownerType, ownerId);
}

document.getElementById("attachMiannModalClose").onclick = () => {
  document.getElementById("attachMiannModal").classList.remove("open");
};
document.getElementById("attachMiannModal").addEventListener("click", (e) => {
  if (e.target.id === "attachMiannModal") document.getElementById("attachMiannModal").classList.remove("open");
});

// ==================== FOTO KOS (osobni kose z mobilni fotoapky) ====================
// Robert 2026-07-31: fotky z /capture.html padaji do osobniho kose per
// uzivatel (owner_type='inbox'), tady je admin tridi a pripojuje k
// zaznamum. "Manazer bude fotit k objednavkam" -> cil 'order' v nabidce.
const PHOTO_INBOX_TARGETS = [
  ["order", "Objednávka (ID)"], ["product", "Produkt (ID)"], ["document", "Doklad (ID)"],
  ["stock_movement", "Skladový pohyb (ID)"], ["po_item", "Položka nák. obj. (ID)"],
  ["lead", "Poptávka - CRM (ID)"],
];
let photoInboxCurrentUser = null;

async function loadPhotoInboxes() {
  const usersEl = document.getElementById("photoInboxUsers");
  const errEl = document.getElementById("photoInboxErr");
  errEl.textContent = "";
  const r = await fetch("/api/gallery-items/inboxes");
  const d = await r.json().catch(() => ({}));
  if (!r.ok) { errEl.textContent = d.error || "Nepodařilo se načíst koše."; return; }
  const inboxes = d.inboxes || [];
  usersEl.innerHTML = inboxes.length
    ? inboxes.map(u => `<button class="pi-user-btn" data-uid="${u.id}">${escapeHtmlAdmin(u.name || u.email)} (${u.role}) – ${u.item_count}</button>`).join("")
    : '<span class="hint">Žádné fotky v koších.</span>';
  usersEl.querySelectorAll(".pi-user-btn").forEach(btn => {
    btn.onclick = () => { photoInboxCurrentUser = parseInt(btn.dataset.uid, 10); loadPhotoInboxGrid(); };
  });
  if (inboxes.length && !photoInboxCurrentUser) photoInboxCurrentUser = inboxes[0].id;
  if (photoInboxCurrentUser) loadPhotoInboxGrid();
  else document.getElementById("photoInboxGrid").innerHTML = "";
}

async function loadPhotoInboxGrid() {
  const grid = document.getElementById("photoInboxGrid");
  const errEl = document.getElementById("photoInboxErr");
  const r = await fetch(`/api/gallery-items?owner_type=inbox&owner_id=${photoInboxCurrentUser}`);
  const d = await r.json().catch(() => ({}));
  if (!r.ok) { errEl.textContent = d.error || "Chyba."; return; }
  grid.innerHTML = "";
  (d.items || []).forEach(item => {
    const wrap = document.createElement("div");
    wrap.style.cssText = "border:1px solid var(--border-soft);border-radius:8px;padding:8px;width:190px;";
    const media = item.media_type === "video"
      ? `<video src="${item.url}" muted playsinline preload="metadata" style="width:100%;border-radius:6px;background:#000;cursor:zoom-in;" class="pi-media-open"></video>`
      : `<img src="${item.url}" loading="lazy" style="width:100%;border-radius:6px;cursor:zoom-in;" class="pi-media-open" alt="">`;
    wrap.innerHTML = `${media}
      ${item.audio_url ? `<audio controls src="${item.audio_url}" style="width:100%;height:24px;margin-top:4px;"></audio>` : ""}
      ${item.latitude != null ? `<div class="hint">📍 ${item.latitude.toFixed(4)}, ${item.longitude.toFixed(4)}</div>` : ""}
      <div class="hint">${item.created_role || ""} · ${item.created_at ? new Date(item.created_at).toLocaleString("cs-CZ") : ""}</div>
      <div style="display:flex;gap:4px;margin-top:6px;flex-wrap:wrap;">
        <select class="pi-target-type" style="flex:1 1 100%;">${PHOTO_INBOX_TARGETS.map(t => `<option value="${t[0]}">${t[1]}</option>`).join("")}</select>
        <input type="number" class="pi-target-id" placeholder="ID" style="width:70px;">
        <button class="pi-move-btn">Připojit</button>
        <button class="pi-del-btn danger">✕</button>
      </div>`;
    wrap.querySelector(".pi-media-open").onclick = () => openImgLightbox(item.url, item.media_type === "video");
    wrap.querySelector(".pi-move-btn").onclick = async () => {
      const tid = parseInt(wrap.querySelector(".pi-target-id").value, 10);
      if (!tid) { errEl.textContent = "Zadej ID cíle."; return; }
      const rr = await fetch(`/api/gallery-items/${item.id}/move`, {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ owner_type: wrap.querySelector(".pi-target-type").value, owner_id: tid }),
      });
      const dd = await rr.json().catch(() => ({}));
      if (!rr.ok) { errEl.textContent = dd.error || "Připojení se nezdařilo."; return; }
      errEl.textContent = "";
      loadPhotoInboxes();
    };
    wrap.querySelector(".pi-del-btn").onclick = async () => {
      if (!confirm("Smazat fotku z koše?")) return;
      await fetch(`/api/gallery-items/${item.id}`, { method: "DELETE" });
      loadPhotoInboxes();
    };
    grid.appendChild(wrap);
  });
  if (!(d.items || []).length) grid.innerHTML = '<span class="gal-empty">Koš je prázdný.</span>';
}

// ==================== UZIVATELE ====================
// ==================== SKLAD (PRODUKTY A KATEGORIE) ====================
let shopCatFlatOptions = [];
let shopProductsCache = [];

// Kategorie jsou ted SJEDNOCENE se strom. Kategorie tabem (content_categories
// / /api/categories) - tady si jen natahneme strom pro vyber v selectech
// (filtr produktu + pridani noveho produktu). Sprava stromu (pridat/
// prejmenovat/smazat) se dela v zalozce Kategorie.
async function loadShopProductCategoryOptions() {
  try {
    const r = await fetch("/api/categories");
    const data = await r.json();
    buildShopCatFlatOptions(data.tree || []);
    populateShopCategorySelects();
  } catch (e) {
    document.getElementById("shopProdErr").textContent = "Nepodařilo se načíst kategorie.";
  }
}

function buildShopCatFlatOptions(tree) {
  shopCatFlatOptions = [];
  function walk(nodes, depth, parentPath) {
    nodes.forEach(n => {
      const path = parentPath ? `${parentPath} > ${n.name}` : n.name;
      shopCatFlatOptions.push({ id: n.id, label: "—".repeat(depth) + " " + n.name, path });
      walk(n.children || [], depth + 1, path);
    });
  }
  walk(tree, 0, "");
  populateShopCatPathDatalist();
}

// Robert 2026-07-28: "tady se musí přece rozbalit nabídka existujících
// kategorií stromu" (u pole "Kategorie (Shoptet)" ve skladové kartě -
// import z shoptetu, volny text, casto se nepresne shoduje s realnym
// stromem kategorii). Datalist misto pevneho selectu - pole zustava
// editovatelny text (Shoptet cesta nemusi 1:1 sedet se stromem), ale
// prohlizec nabidne/rozbali existujici cesty ze stromu jako napovedu.
function populateShopCatPathDatalist() {
  const dl = document.getElementById("shopCatPathList");
  if (!dl) return;
  dl.innerHTML = shopCatFlatOptions.map(o => `<option value="${escapeHtmlAdmin(o.path)}">`).join("");
}

function populateShopCategorySelects() {
  const filterSel = document.getElementById("shopProdCategoryFilter");
  const addSel = document.getElementById("newShopProdCategory");
  const bulkSel = document.getElementById("shopBulkCategory");
  const keepFilter = filterSel.value;
  const keepAdd = addSel.value;
  filterSel.innerHTML = '<option value="">Všechny kategorie</option>'
    + '<option value="none">— bez kategorie —</option>'
    + shopCatFlatOptions.map(o => `<option value="${o.id}">${escapeHtmlAdmin(o.label)}</option>`).join("");
  addSel.innerHTML = '<option value="">(bez kategorie)</option>' +
    shopCatFlatOptions.map(o => `<option value="${o.id}">${escapeHtmlAdmin(o.label)}</option>`).join("");
  bulkSel.innerHTML = '<option value="">— změnit kategorii —</option>' +
    shopCatFlatOptions.map(o => `<option value="${o.id}">${escapeHtmlAdmin(o.label)}</option>`).join("");
  if (keepFilter) filterSel.value = keepFilter;
  if (keepAdd) addSel.value = keepAdd;
}

function shopCatNameById(id) {
  const found = shopCatFlatOptions.find(o => o.id === id);
  return found ? found.label.replace(/^—+\s*/, "") : "";
}

let shopSelectedIds = new Set();
// Stránkování (task #78/87) - stav drzeny mimo funkci, pager ho pri
// zmene aktualizuje a znovu zavola loadShopProducts().
const shopProdPagerState = { page: 1, page_size: 50 };
// Robert 2026-08: "nelze dobre mazat bulk archivovane produkty" - "Vybrat
// vse" vybiralo jen produkty na AKTUALNI STRANCE (50 z celkovych 1266+
// archivovanych), takze hromadne smazani vsech archivovanych vyzadovalo
// desitky opakovani po strankach. shopProdLastTotal drzi skutecny pocet
// VSECH produktu odpovidajicich aktualnimu filtru (ne jen nactenou
// stranku) - viz shopSelectAllMatching() nize.
let shopProdLastTotal = 0;

// Hledani podle CISLA KARTY (shop_products.id) - Robert 2026-10-04 pres bot9 ("nejde hledat podle ID karty"): pole "ID karty" (4934 nebo #4934), nebo "#4934" napsane
// do pole pro nazev. Vraci cislo, null (ID se nehleda) nebo NaN (nejde o cislo). Hleda se PRESNA karta bez ohledu na ostatni filtry (i archivovana a neaktivni) pres
// GET /api/shop/products/<id> (detail; funguje hned, bez zmeny serveru) - radek tabulky bere z detailu jen pole, ktera tabulka pouziva (id, sku, name, unit, ceny, sklad...).
function shopProdIdFilter() {
  const idRaw = document.getElementById("shopProdIdSearch").value.trim();
  const nameRaw = document.getElementById("shopProdSearch").value.trim();
  const raw = idRaw || (nameRaw.charAt(0) === "#" ? nameRaw : "");
  if (!raw) return null;
  const m = /^#?\s*(\d{1,9})$/.exec(raw);
  return m ? Number(m[1]) : NaN;
}

let shopProdIdErrShown = false;           // hlaska hledani podle ID (neexistuje / neni cislo) - po zruseni ID filtru se smaze, cizi hlasky v #shopProdErr se nemazou

async function loadShopProductById(idq) {
  const errEl = document.getElementById("shopProdErr");
  errEl.textContent = "";
  let p = null;
  if (Number.isNaN(idq)) {
    errEl.textContent = "ID karty je číslo, např. 4934 nebo #4934.";
  } else {
    try {
      const r = await fetch(`/api/shop/products/${idq}`);
      const data = await r.json().catch(() => ({}));
      p = r.ok && data.product ? data.product : null;
      if (!p) errEl.textContent = r.status === 404 || r.ok ? `Karta s ID ${idq} neexistuje.` : "Nepodařilo se načíst produkt.";
    } catch (e) {
      errEl.textContent = "Nepodařilo se načíst produkt.";
    }
  }
  shopProdIdErrShown = !!errEl.textContent;
  shopProductsCache = p ? [p] : [];
  shopProdLastTotal = shopProductsCache.length;
  shopSelectedIds.clear();
  renderShopProducts();
  updateShopBulkToolbar();
  renderPager("shopProdPager", { total: shopProdLastTotal, page: 1, page_size: shopProdPagerState.page_size }, shopProdPagerState, loadShopProducts);
}

async function loadShopProducts() {
  const idq = shopProdIdFilter();
  if (idq !== null) { await loadShopProductById(idq); return; }
  if (shopProdIdErrShown) { document.getElementById("shopProdErr").textContent = ""; shopProdIdErrShown = false; }
  const categoryId = document.getElementById("shopProdCategoryFilter").value;
  const q = document.getElementById("shopProdSearch").value.trim();
  const sku = document.getElementById("shopProdSkuSearch").value.trim();
  const lowStockOnly = document.getElementById("shopProdLowStockOnly").checked;
  const showArchived = document.getElementById("shopProdShowArchived").checked;
  const activeFilter = document.getElementById("shopProdActiveFilter").value;
  const inSceneOnly = document.getElementById("shopProdInSceneOnly").checked;
  const params = new URLSearchParams({
    all: "1",
    page: shopProdPagerState.page,
    page_size: shopProdPagerState.page_size,
  });
  if (categoryId) params.set("category_id", categoryId);
  if (q) params.set("q", q);
  if (sku) params.set("sku", sku);
  if (lowStockOnly) params.set("low_stock", "1");
  if (inSceneOnly) params.set("in_scene", "1");
  if (showArchived) params.set("archived", "1");
  // Robert 2026-08-08 ("novou produktovou sestavu nevidím v produktech") -
  // nove sestavy ze sceny se zakladaji jako neaktivni navrh (active=0),
  // ale seznam produktu je defaultne razeny abecedne (name) - u stovek
  // produktu se novy navrh snadno "ztrati" nekde uprostred abecedy. Filtr
  // "Jen neaktivní" (viz #shopProdActiveFilter) rovnou razeni prehodi na
  // nejnovejsi-prvni (viz shop_products_list v api/app.py).
  if (activeFilter === "active") params.set("active_only", "1");
  else if (activeFilter === "inactive") params.set("inactive_only", "1");
  try {
    const r = await fetch(`/api/shop/products?${params.toString()}`);
    const data = await r.json();
    shopProductsCache = data.products || [];
    shopProdLastTotal = data.total ?? shopProductsCache.length;
    shopSelectedIds.clear();
    renderShopProducts();
    updateShopBulkToolbar();
    renderPager("shopProdPager", data, shopProdPagerState, loadShopProducts);
  } catch (e) {
    document.getElementById("shopProdErr").textContent = "Nepodařilo se načíst produkty.";
  }
}

// Zavre vsechna otevrena "⋮" menu v tabulce produktu (klik mimo, nebo
// otevreni jineho radku) - viz .row-more-menu.
function closeAllRowMoreMenus() {
  document.querySelectorAll(".row-more-menu.open").forEach(m => m.classList.remove("open"));
}
document.addEventListener("click", closeAllRowMoreMenus);

// Robert 2026-07-26: klik-na-radek na tabulkach, ktere maji jen
// product_id (ne cely product objekt) - dotahne aktualni produkt pres
// verejny GET /api/shop/products/<id> a otevre stejnou Skladovou kartu.
// ==================== SKLADOVA KARTA: ZIVY 3D NAHLED SESTAVY ====================
// Robert 2026-09-06 ("Zhmotni na frontendu to, co jsi mel v artefaktu -
// prepinani horni blok, ruzne verze"): presne totez, co uz overene fungovalo
// v samostatnem demu (interaktivni 3D + prepinani variant horniho bloku +
// zivy kusovnik/cena), ale ZABUDOVANE do skutecne skladove karty (zalozka
// "3D model"), NE dalsi scratch demo. Zdroj geometrie: staff-scoped
// GET /api/product-assemblies/lookup?product=<id> (plne parts[] vc.
// position/quaternion/scale, na rozdil od /api/admin/product-assemblies/
// by-product/<id> pouzivaneho zalozkou "Kusovnik" vyse, ktery vraci jen
// bom/price_summary snapshot bez geometrie). GLB soubory: /katalog/<file>
// (verejne servirovane staticky nginxem, viz api/app.py hlavicka u
// KATALOG_GLB_DIR - netyka se to karoserii, tam plati samostatne
// staff-only pravidlo /api/car-body-file). Zivy prepocet kusovniku/ceny
// tady je NEZAVISLY na ulozenem price_summary v zalozce "Kusovnik" (ten
// zustava statickym snapshotem z okamziku ulozeni sestavy ve scene).
let sc3dScriptsPromise = null;
function scLoadScriptOnce(src) {
  return new Promise((resolve, reject) => {
    const existing = document.querySelector(`script[src="${src}"]`);
    if (existing) { existing.dataset.scLoaded === "1" ? resolve() : existing.addEventListener("load", resolve); return; }
    const s = document.createElement("script");
    s.src = src;
    s.onload = () => { s.dataset.scLoaded = "1"; resolve(); };
    s.onerror = reject;
    document.head.appendChild(s);
  });
}
function scEnsureThreeJs() {
  if (!sc3dScriptsPromise) {
    // stejne verze/UMD buildy jako scene.html (webapp/scene.html hlavicka) -
    // zadny modulovy import, THREE/OrbitControls/GLTFLoader jako globaly.
    sc3dScriptsPromise = scLoadScriptOnce("https://cdn.jsdelivr.net/npm/three@0.128.0/build/three.min.js")
      .then(() => Promise.all([
        scLoadScriptOnce("https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"),
        scLoadScriptOnce("https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/loaders/GLTFLoader.js"),
      ]));
  }
  return sc3dScriptsPromise;
}

let scKatalogMapPromise = null;
function scFetchKatalogMap() {
  // Cache na cely zivot admin stranky (katalog se behem jedne session
  // nemeni natolik, aby stalo za to refetchovat pri kazdem otevreni karty) -
  // mapuje part_id ("Object_7", "product_3939", ...) na PRICE-like objekt +
  // GLB soubor, presne tvar jako PRICE v demu regal3d.html.
  if (!scKatalogMapPromise) {
    scKatalogMapPromise = fetch("/api/katalog").then(r => r.json()).then(d => {
      const map = new Map();
      (d.parts || []).forEach(p => {
        map.set(String(p.id), {
          name: p.name,
          file: p.file,
          length_mm: p.length_mm,
          cross_section_mm: p.cross_section_mm,
          weight_kg: p.weight_kg_approx != null ? p.weight_kg_approx : (p.weight_g != null ? p.weight_g / 1000 : null),
          price_czk: p.price_czk_approx_PLACEHOLDER,
          price_per_cut: p.price_per_cut_czk,
          is_board: !!p.is_board_material,
        });
      });
      return map;
    });
  }
  return scKatalogMapPromise;
}
let scPricingConfigPromise = null;
function scFetchPricingConfig() {
  if (!scPricingConfigPromise) {
    scPricingConfigPromise = fetch("/api/pricing-config").then(r => r.json())
      .catch(() => ({ joint_price_czk: 0, profile_flat_fee_czk: 0 }));
  }
  return scPricingConfigPromise;
}

// ---- volby horniho bloku (Robert 2026-09-05/06, shape_geometry_methods.id=9,
// "7_varianty_hornibloku") - stejne klice/popisky jako v regal3d.html demu.
const SC3D_SKUPINY = [
  { klic: "blok", nazev: "Horní blok pro dlouhé předměty", moznosti: [
    { k: "bez", n: "Bez horního bloku", s: "Regál končí nad boxy" },
    { k: "eko", n: "Eko — jen profily", s: "Rám bez výplní" },
    { k: "plne", n: "Plné výplně", s: "Záda, čelo, bok, dna — celá výška" },
    { k: "polo", n: "Výplně do poloviny", s: "Spodní půlka zaklopená" },
    { k: "dvirka", n: "Sklopné dvířko (koncept)", s: "Čelo se otevírá — panty nenavrženy" },
  ]},
  { klic: "ram", nazev: "Profily rámu", moznosti: [
    { k: "jen_podelniky", n: "Jen podélníky", s: "Bez příček" },
    { k: "s_prickami", n: "Podélníky + příčky", s: "Příčka v rovině každé nohy" },
  ]},
];
function sc3dJeVyplnRole(r) { return (r || "").startsWith("vypln"); }
// Pricky horniho bloku ve VSECH trech pasmech: horni, police (ram prostredni
// police) a spodni. Puvodni verze znala jen `pricka-horni*` a PRESNOU shodu
// `pricka-spodni-prepazka` - realne generovane role jsou ale `pricka-spodni-0/1/2`
// a `pricka-police-0/1/2`, takze zadny predikat je nechytil, spadly do vetve
// "vzdy zobrazit" a visely ve vzduchu i ve variante "Bez horniho bloku".
// POZOR: `pricka-uzavreni-vyrezu` sem NEPATRI - ta je soucast nohy POD blokem
// a zobrazuje se vzdy (proto se nesmi pouzit siroke startsWith("pricka")).
function sc3dJePrickaRole(r) {
  r = r || "";
  return r.startsWith("pricka-horni") || r.startsWith("pricka-police") || r.startsWith("pricka-spodni");
}
function sc3dJeRamRole(r) { return (r || "").startsWith("podelnik") || sc3dJePrickaRole(r); }
function sc3dMaHorniBlok(parts) { return parts.some(p => sc3dJeVyplnRole(p.role) || (p.role || "").startsWith("podelnik-zadni-horni")); }
function sc3dVyberDily(parts, v) {
  return parts.filter(p => {
    const r = p.role || "";
    if (sc3dJeVyplnRole(r)) return v.blok === "plne" || v.blok === "polo" || v.blok === "dvirka";
    if (sc3dJeRamRole(r)) {
      if (v.blok === "bez") return false;
      if (sc3dJePrickaRole(r) && v.ram !== "s_prickami") return false;
      return true;
    }
    return true; // zaklad regalu (nohy, spojnice, eurobox patra, uhelniky...) - vzdy
  });
}
// VODOROVNE lezici panel (dno bloku, prostredni police) vs. svisla stena.
// Test je GEOMETRICKY - rotace kolem osy X o ~90 st. (|quaternion.x| > 0.5) -
// zamerne NE podle jmena role: jmenny seznam ("vypln-dno") se uz jednou
// rozesel s daty, kdyz do generatoru pribyla `vypln-police`, a prave to
// zpusobilo, ze se police v "poloviznich vyplnich" chovala jako svisla stena.
function sc3dJeVodorovnyPanel(p) { return Math.abs(((p.quaternion || [])[0]) || 0) > 0.5; }
// Rezim "polo" - viz regal3d.html: puvodni rozsah GLB je 1000-jednotkovy box
// centrovany v +-500, panel se ukotvi ke SPODNI hrane a zmensi jen nahoru.
// POUZITELNE JEN NA SVISLE STENY (viz sc3dJeVodorovnyPanel).
function sc3dTransformujProPolo(p) {
  const Yc = p.position[1], Sy = p.scale[1];
  const spodek = Yc - Sy * 500;
  const novySy = Sy / 2;
  return { pos: [p.position[0], spodek + novySy * 500, p.position[2]], scaleY: novySy };
}
function sc3dOtevriDvirko(mesh, part, uhelStupne) {
  const delkaMm = part.scale[0] * 1000;
  const hingeZ = part.position[2] - delkaMm / 2;
  const pivot = new THREE.Group();
  pivot.position.set(part.position[0], part.position[1], hingeZ);
  mesh.position.set(0, 0, delkaMm / 2);
  mesh.quaternion.set(...part.quaternion);
  // MERITKO SE MUSI NASTAVIT I TADY. Ostatni vetve v postavScenu volaji
  // mesh.scale.set() samy, tahle na to zapomnela - panel se pak kreslil
  // v syrove velikosti GLB (1000mm krychle) misto 444/848mm desky, takze
  // ve variante "Sklopne dvirko" stala vedle regalu obri deska mimo nej.
  // Neprojevilo se to driv jen proto, ze cela vetev byla do 24d7160b mrtva
  // (predikat testoval `vypln-celo-0` proti realne roli `vypln-celo-0-a`).
  mesh.scale.set(...part.scale);
  pivot.quaternion.setFromAxisAngle(new THREE.Vector3(0, 1, 0), THREE.MathUtils.degToRad(uhelStupne));
  pivot.add(mesh);
  return pivot;
}
function sc3dIsProfil(cat) { return !!(cat && cat.length_mm && cat.cross_section_mm && cat.cross_section_mm[0] != null); }
function sc3dCzk(n) { return Math.round(n).toLocaleString("cs-CZ") + " Kč"; }
// Karoserie (car_body_*, 3 party/sestava - leva/prava stena + podlaha) je
// jen KONTEXT ve scene.html, ne prodavana polozka skladove karty (Robert,
// 2026-09-09 pres bot3: "produktova sestava se neprodava s karoserii").
// Sdileny filtr pro VSECHNY produktove pohledy na sestavu - kusovnik/cenu
// (nize) i samotny 3D viewer skladove karty (scBuildViewer3D -> postavScenu,
// viz prekresli()). Presne stejna vyjimka jako produkcni
// computeAssemblyBomAndPrice (viz volajici filtr pred sestavenim `entries`),
// jeji Node port scripts/2026-09-06_backfill_bom_price.js:134, a turntable
// render scripts/2026-09-09_turntable_job.py:resolve_parts(). Karoserie v
// datech NEMAZAT (scene.html na ni zustava zavisly) - filtruje se jen
// vykreslovani/cena na produktove vrstve.
function sc3dJeKaroserie(p) { return String(p.part_id).startsWith("car_body_"); }
function sc3dSpocitejKusovnik(dily, katalogMap, pricingConfig) {
  const skupiny = new Map();
  let totalMaterial = 0, totalAccessory = 0, totalCut = 0, totalProfiles = 0, chybiCena = 0;
  dily.forEach(p => {
    if (sc3dJeKaroserie(p)) return;
    const cat = katalogMap.get(String(p.part_id));
    if (!cat) return;
    const isMat = sc3dIsProfil(cat) || cat.is_board;
    const cena = cat.price_czk;
    if (cena == null) chybiCena++;
    if (isMat) totalMaterial += cena || 0; else totalAccessory += cena || 0;
    if (sc3dIsProfil(cat)) { totalCut += cat.price_per_cut || 0; totalProfiles++; }
    // delka_mm jen u profilu (viz sc3dIsProfil) - pro Cena/m sloupec v
    // renderKusovnikCena (Robert 2026-09-15 pres bot3: "vsechny kusovniky...
    // i cenu za 1m"). Reprezentativni hodnota prvniho vyskytu v teto
    // skupine, presne stejny princip jako uz `unit` par radku vyse - viz
    // komentar tam, proc je "podle nazvu" seskupeni uz beztak priblizne.
    const g = skupiny.get(cat.name) || { name: cat.name, unit: cena, qty: 0, delka_mm: sc3dIsProfil(cat) ? cat.length_mm : null };
    g.qty++; skupiny.set(cat.name, g);
  });
  const bom = [...skupiny.values()].map(g => ({ ...g, total: g.unit != null ? Math.round(g.unit * g.qty) : null }))
    .sort((a, b) => (b.total || 0) - (a.total || 0));
  const flatFee = totalProfiles * (pricingConfig.profile_flat_fee_czk || 0);
  return { bom, totalMaterial, totalAccessory, totalCut, flatFee, total: totalMaterial + totalAccessory + totalCut + flatFee, chybiCena, totalProfiles };
}

let scCurrent3dParts = null; // parts[] aktualne otevrene skladove karty (null = zadna sestava/jeste nenacteno)
// Vsechny sestavy navazane na prave otevrenou kartu = SCHVALENE varianty
// (Robert 2026-09-10: "posuvnik proste nezobrazuje sest schvalenych variant
// horniho bloku"). Plni se z by-product pri otevreni karty; kdyz jich je vic
// nez jedna, ekvalizer prepina PRIMO MEZI NIMI misto dopocitavanych os
// SC3D_SKUPINY - viz scBuildViewer3D.
let scCurrent3dVariants = [];
const scVariantPartsCache = new Map();   // assembly_id -> parts[]

// Nazvy sestav vznikaji ve scene a nesou sluzebni prefix i model vozidla
// ("NÁHLED horní blok 1/6 jedno pásmo - jen rám (Doblo K-075 C)"). Do
// uzkeho tahla ekvalizeru se to nevejde, tak se rozdeli na kratky titulek
// (poradi) a popis (co varianta je).
function sc3dVariantaPopisky(name) {
  let s = String(name || "").trim();
  s = s.replace(/\s*\([^()]*\)\s*$/, "");
  s = s.replace(/^\s*(NÁHLED|NAHLED)\s+/i, "");
  s = s.replace(/^horní blok\s+/i, "");
  // AKTUALNI TVAR (Robert 2026-09-11 pres bot8: "mel by se prestat pouzivat
  // hloupy nazev NÁHLED, kodovani jsme si napsali"): "<KOD> - <popis>",
  // napr. "K-075-E30-C1 - jedno pásmo, jen rám". Kod = cely prvni token a
  // oddelovac MUSI byt pomlcka obklopena mezerami - jinak by se ukousla uz
  // prvni pomlcka uvnitr kodu samotneho a titulek by vysel "K".
  // Kod se zamerne nerozebira na casti: varianta typologie ("C") dostane po
  // dokonceni ciselniku od bot9 svuj skutecny kod, takze se nesmi spolehat
  // na to, ze tam bude zrovna tohle pismeno.
  const kod = s.match(/^(\S+)\s+[-–—]\s+(.*)$/);
  if (kod) return { titulek: kod[1], popis: (kod[2] || "").trim() };
  // STARY TVAR "3/6 ..." - nez Robert kodovani zavedl. Nechavam kvuli
  // sestavam, ktere jeste nikdo neprejmenoval.
  const m = s.match(/^(\d+\/\d+)\s*(.*)$/);
  if (m) return { titulek: m[1], popis: (m[2] || "").replace(/^[-–—\s]+/, "").trim() };
  return { titulek: s.slice(0, 14), popis: s };
}
// Barvy dilu ve 3D. Vytazeno z uzaveru scBuildViewer3D na uroven modulu
// (bot16, 2026-09-11), aby stejne materialy pouzivaly i nahledy v zalozce
// "Varianty" - jinak by porovnani vypadalo, jako by slo o jine dily.
const SC3D_MATCACHE = {};
function sc3dMaterialProDil(part) {
  let key, color, rough, metal;
  if (part.part_id === "Object_7") { key = "profil"; color = 0xb9c0c2; rough = 0.45; metal = 0.55; }
  else if ((part.role || "").startsWith("vypln")) { key = "mdf"; color = 0x9aa3a0; rough = 0.85; metal = 0.02; }
  else if ((part.role || "").startsWith("eurobox")) { key = "box"; color = 0xcfd6d2; rough = 0.6; metal = 0.05; }
  else { key = "spojka"; color = 0x8a8f86; rough = 0.55; metal = 0.15; }
  if (!SC3D_MATCACHE[key]) SC3D_MATCACHE[key] = new THREE.MeshStandardMaterial({ color, roughness: rough, metalness: metal });
  return SC3D_MATCACHE[key];
}
let sc3dActive = null; // { dispose() } aktualne postaveneho vieweru - zavre se pri kazdem novem otevreni/prekresleni karty
function scDisposeViewer3D() {
  if (sc3dActive) { try { sc3dActive.dispose(); } catch (e) {} sc3dActive = null; }
}

// Ekvalizerove posuvniky pro varianty (Robert, 2026-09-09 pres bot3:
// "roletky nechci, udelejme z toho takovy ekvalizer posuvniky" +
// upresneni "vertikalne vedle obrazkoveho okna to bude"). Diskretni
// polohy (ne plynule), popisek aktualni volby, sipky na klavesnici,
// mys/dotyk (Pointer Events). Styl vlozen jednou globalne (idempotentni).
function sc3dEnsureEqStyles() {
  if (document.getElementById("sc3dEqStyle")) return;
  const s = document.createElement("style");
  s.id = "sc3dEqStyle";
  s.textContent = `
    /* grid (ne flex) + display:contents na pasu => vsechny tracky zacinaji
       i konci na stejne vysce i pri ruzne dlouhych popiskach - to je u
       ekvalizeru podstatne, jinak "tahla" nesedi v jedne rovine. */
    .sc3d-eq { display:grid; grid-auto-flow:column; grid-auto-columns:72px; grid-template-rows:auto minmax(150px,1fr) auto; gap:0 16px; height:100%; }
    .sc3d-eq-band { display:contents; }
    .sc3d-eq-current { font-size:11.5px; font-weight:600; text-align:center; display:flex; align-items:flex-end; justify-content:center; line-height:1.2; padding-bottom:6px; }
    .sc3d-eq-track { position:relative; width:32px; height:100%; justify-self:center; border-radius:8px; background:var(--panel-bg-alt); border:1px solid var(--border-soft); cursor:pointer; touch-action:none; }
    .sc3d-eq-track:hover { border-color:var(--accent-focus); }
    .sc3d-eq-track:focus-visible { outline:2px solid var(--accent-focus); outline-offset:2px; }
    .sc3d-eq-notch { position:absolute; left:4px; right:4px; height:2px; margin-top:-1px; background:color-mix(in srgb, var(--text-muted) 70%, transparent); border-radius:1px; }
    .sc3d-eq-fill { position:absolute; left:3px; right:3px; bottom:3px; border-radius:6px; background:color-mix(in srgb, var(--accent) 32%, transparent); transition:top .12s ease; pointer-events:none; }
    .sc3d-eq-thumb { position:absolute; left:50%; width:26px; height:13px; margin-left:-13px; background:var(--accent); border-radius:4px; box-shadow:0 1px 3px rgba(0,0,0,.4); transition:top .12s ease; pointer-events:none; }
    .sc3d-eq-track.sc3d-eq-dragging .sc3d-eq-thumb, .sc3d-eq-track.sc3d-eq-dragging .sc3d-eq-fill { transition:none; }
    .sc3d-eq-title { font-size:10.5px; color:var(--text-muted); text-align:center; padding-top:6px; line-height:1.25; }
  `;
  document.head.appendChild(s);
}
// g = polozka SC3D_SKUPINY, initIdx = pocatecni index v g.moznosti,
// onChange(k) se zavola pri KAZDE zmene (discretni krok, ne kazdy pixel tahu).
function sc3dEqBand(g, initIdx, onChange) {
  const PAD = 12, N = g.moznosti.length;
  let idx = Math.max(0, Math.min(N - 1, initIdx));
  const frac = i => (N > 1 ? i / (N - 1) : 0.5);
  const topCalc = i => `calc(${PAD}px + ${(1 - frac(i)).toFixed(4)} * (100% - ${2 * PAD}px))`;

  const wrap = document.createElement("div"); wrap.className = "sc3d-eq-band";
  const cur = document.createElement("div"); cur.className = "sc3d-eq-current";
  const track = document.createElement("div"); track.className = "sc3d-eq-track";
  track.tabIndex = 0;
  track.setAttribute("role", "slider");
  track.setAttribute("aria-orientation", "vertical");
  track.setAttribute("aria-valuemin", "0");
  track.setAttribute("aria-valuemax", String(N - 1));
  track.setAttribute("aria-label", g.nazev);
  const notches = document.createElement("div");
  g.moznosti.forEach((_, i) => {
    const n = document.createElement("div"); n.className = "sc3d-eq-notch"; n.style.top = topCalc(i);
    notches.appendChild(n);
  });
  const fill = document.createElement("div"); fill.className = "sc3d-eq-fill";
  const thumb = document.createElement("div"); thumb.className = "sc3d-eq-thumb";
  track.append(fill, notches, thumb); // rysky NAD vyplni, at jsou videt i ve vyplnene casti
  const title = document.createElement("div"); title.className = "sc3d-eq-title"; title.textContent = g.nazev;
  wrap.append(cur, track, title);

  function render() {
    const m = g.moznosti[idx];
    cur.textContent = m.n;
    cur.title = m.s || m.n;
    thumb.style.top = topCalc(idx);
    fill.style.top = topCalc(idx);
    track.setAttribute("aria-valuenow", String(idx));
    track.setAttribute("aria-valuetext", m.n);
  }
  function setIdx(i, fire) {
    i = Math.max(0, Math.min(N - 1, i));
    if (i === idx) return;
    idx = i;
    render();
    if (fire) onChange(g.moznosti[idx].k);
  }
  function idxFromClientY(clientY) {
    const rect = track.getBoundingClientRect();
    const travel = Math.max(1, rect.height - 2 * PAD);
    const y = Math.min(rect.height - PAD, Math.max(PAD, clientY - rect.top));
    return Math.round((1 - (y - PAD) / travel) * (N - 1));
  }
  let dragging = false;
  track.addEventListener("pointerdown", e => {
    dragging = true;
    track.classList.add("sc3d-eq-dragging");
    track.setPointerCapture(e.pointerId);
    track.focus();
    setIdx(idxFromClientY(e.clientY), true);
    e.preventDefault();
  });
  track.addEventListener("pointermove", e => { if (dragging) setIdx(idxFromClientY(e.clientY), true); });
  function endDrag(e) {
    if (!dragging) return;
    dragging = false;
    track.classList.remove("sc3d-eq-dragging");
    try { track.releasePointerCapture(e.pointerId); } catch (err) {}
  }
  track.addEventListener("pointerup", endDrag);
  track.addEventListener("pointercancel", endDrag);
  track.addEventListener("keydown", e => {
    if (e.key === "ArrowUp" || e.key === "ArrowRight") setIdx(idx + 1, true);
    else if (e.key === "ArrowDown" || e.key === "ArrowLeft") setIdx(idx - 1, true);
    else if (e.key === "Home") setIdx(0, true);
    else if (e.key === "End") setIdx(N - 1, true);
    else return;
    e.preventDefault();
  });

  render();
  return wrap;
}

// container = #stockCard3dViewer, parts = assembly.parts (z lookup endpointu)
async function scBuildViewer3D(container, partsVstup) {
  let parts = partsVstup;   // pri prepnuti varianty se nahradi, viz nize
  scDisposeViewer3D();
  container.innerHTML = `<div class="sc-3d-loading" style="padding:14px;color:var(--text-muted);font-size:13px;">Načítám 3D náhled…</div>`;

  let katalogMap, pricingConfig;
  try {
    await scEnsureThreeJs();
    [katalogMap, pricingConfig] = await Promise.all([scFetchKatalogMap(), scFetchPricingConfig()]);
  } catch (e) {
    container.innerHTML = `<div class="sc-3d-loading" style="padding:14px;color:var(--warn,#c77);font-size:13px;">3D náhled se nepodařilo načíst (${e.message || e}).</div>`;
    return;
  }

  const maHorniBlok = sc3dMaHorniBlok(parts);
  // Karta s vic navazanymi sestavami ma ekvalizer VZDYCKY - prepina mezi
  // schvalenymi variantami (viz nize). Bez tehle podminky by se kontejner
  // #sc3dSkupiny nevykreslil u zakladni sestavy, ktera sama horni blok
  // nema, a tahlo by nebylo kam povesit.
  const maSchvaleneVarianty = (Array.isArray(scCurrent3dVariants) ? scCurrent3dVariants.length : 0) > 1;
  const zobrazEkvalizer = maHorniBlok || maSchvaleneVarianty;
  const volba = { blok: "plne", ram: "s_prickami" };

  sc3dEnsureEqStyles();
  container.innerHTML = `
    <div style="display:grid;grid-template-columns:minmax(0,2.4fr) auto minmax(280px,1fr);gap:16px;align-items:start;">
      <div>
        <!-- Vyska nahledu se ridi VYSKOU OKNA, ne pomerem stran (Robert
             2026-09-09 "okno produktu je male"): po rozsireni karty na 1720px
             by aspect-ratio:16/11 udelalo z nahledu ~1000px vysoky blok,
             ktery uz se do karty (max-height:92vh) nevejde a musel by se
             scrollovat. clamp() drzi nahled velky, ale porad cely na obrazovce
             - a na uzkem/nizkem okne nespadne pod 340px. -->
        <div id="sc3dViewport" style="width:100%;height:clamp(340px,64vh,820px);border-radius:6px;background:#20272b;position:relative;overflow:hidden;cursor:grab;"></div>
        <div style="display:flex;gap:6px;margin-top:8px;flex-wrap:wrap;">
          <button type="button" class="sc3d-viewbtn" data-az="0" data-el="4">Zepředu</button>
          <button type="button" class="sc3d-viewbtn" data-az="90" data-el="4">Ze strany</button>
          <button type="button" class="sc3d-viewbtn" data-az="35" data-el="85">Shora</button>
          <button type="button" class="sc3d-viewbtn" data-az="35" data-el="22">Izometricky</button>
        </div>
      </div>
      ${zobrazEkvalizer ? `<div id="sc3dSkupiny" class="sc3d-eq" style="align-self:stretch;"></div>` : ""}
      <div>
        ${zobrazEkvalizer ? "" : `<div style="font-size:12px;color:var(--text-muted);margin-bottom:14px;">Tato sestava nemá volitelný horní blok — zobrazen jen statický 3D náhled.</div>`}
        <div id="sc3dKusovnik"></div>
      </div>
    </div>
  `;
  for (const b of container.querySelectorAll(".sc3d-viewbtn")) {
    b.style.cssText = "font:inherit;font-size:12px;background:var(--panel-bg-alt);border:1px solid var(--border-soft);color:var(--text-muted);border-radius:5px;padding:5px 10px;cursor:pointer;";
  }

  const el = container.querySelector("#sc3dViewport");
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x20272b);
  const camera = new THREE.PerspectiveCamera(38, el.clientWidth / Math.max(1, el.clientHeight), 10, 20000);
  const renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setPixelRatio(Math.min(2, window.devicePixelRatio || 1));
  renderer.setSize(el.clientWidth, el.clientHeight);
  el.appendChild(renderer.domElement);
  scene.add(new THREE.HemisphereLight(0xf3ede2, 0x2a2f26, 1.05));
  const dir = new THREE.DirectionalLight(0xffffff, 0.85); dir.position.set(600, 1400, 900); scene.add(dir);
  const dir2 = new THREE.DirectionalLight(0xbcd0ff, 0.35); dir2.position.set(-800, 600, -700); scene.add(dir2);
  const grid = new THREE.GridHelper(4000, 40, 0x37414a, 0x37414a); grid.position.y = -2; scene.add(grid);
  const group = new THREE.Group(); scene.add(group);
  const controls = new THREE.OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true; controls.dampingFactor = 0.08;

  let disposed = false, raf = null;
  function animate() { if (disposed) return; raf = requestAnimationFrame(animate); controls.update(); renderer.render(scene, camera); }
  const onResize = () => {
    if (disposed) return;
    camera.aspect = el.clientWidth / Math.max(1, el.clientHeight);
    camera.updateProjectionMatrix();
    renderer.setSize(el.clientWidth, el.clientHeight);
  };
  window.addEventListener("resize", onResize);

  function priblizNaBox(box, azimutDeg, elevDeg) {
    if (!box || box.isEmpty()) return;
    const size = box.getSize(new THREE.Vector3()), center = box.getCenter(new THREE.Vector3());
    const maxDim = Math.max(size.x, size.y, size.z), dist = maxDim * 1.7 + 400;
    const az = THREE.MathUtils.degToRad(azimutDeg), elr = THREE.MathUtils.degToRad(elevDeg);
    controls.target.copy(center);
    camera.position.set(center.x + dist * Math.cos(elr) * Math.sin(az), center.y + dist * Math.sin(elr), center.z + dist * Math.cos(elr) * Math.cos(az));
    camera.near = Math.max(1, maxDim / 200); camera.far = dist * 8;
    camera.updateProjectionMatrix(); controls.update();
  }
  let posledniBox = null;

  // Materialy resi sdilena sc3dMaterialProDil() (viz nahore) - stejne barvy
  // musi mit i nahledy v zalozce "Varianty", jinak by porovnani vypadalo,
  // jako by slo o jine dily. (Puvodni lokalni MATCACHE tim odpadl.)
  const materialProDil = sc3dMaterialProDil;

  const gltfCache = {};
  const loader = new THREE.GLTFLoader();
  async function nactiGlb(partId) {
    if (gltfCache[partId] !== undefined) return gltfCache[partId];
    const cat = katalogMap.get(String(partId));
    if (!cat || !cat.file) { gltfCache[partId] = null; return null; }
    try {
      const gltf = await new Promise((resolve, reject) => loader.load(`/katalog/${cat.file}`, resolve, undefined, reject));
      gltfCache[partId] = gltf.scene;
    } catch (e) { gltfCache[partId] = null; }
    return gltfCache[partId];
  }

  function postavScenu(dily) {
    while (group.children.length) group.remove(group.children[0]);
    dily.forEach(p => {
      const tpl = gltfCache[p.part_id];
      if (!tpl) return;
      const mesh = tpl.clone(true);
      mesh.traverse(n => { if (n.isMesh) n.material = materialProDil(p); });
      // startsWith, ne presna shoda: realne role jsou `vypln-celo-0-a`/`-b`
      // (steny jsou kvuli prostredni polici delene na patra), takze presna
      // shodovy test nikdy neplatil a varianta "Sklopne dvirko" nedelala nic.
      const jeCelo = (p.role || "").startsWith("vypln-celo-0") || (p.role || "").startsWith("vypln-celo-1");
      if (volba.blok === "dvirka" && jeCelo) {
        group.add(sc3dOtevriDvirko(mesh, p, 42));
      } else if (volba.blok === "polo" && sc3dJeVyplnRole(p.role) && !sc3dJeVodorovnyPanel(p)) {
        const t = sc3dTransformujProPolo(p);
        mesh.position.set(...t.pos); mesh.quaternion.set(...p.quaternion); mesh.scale.set(p.scale[0], t.scaleY, p.scale[2]);
        group.add(mesh);
      } else {
        mesh.position.set(...p.position); mesh.quaternion.set(...p.quaternion); mesh.scale.set(...p.scale);
        group.add(mesh);
      }
    });
    group.updateMatrixWorld(true);
    const box = new THREE.Box3(); let maBox = false;
    group.traverse(n => { if (n.isMesh) { if (!maBox) { box.setFromObject(n); maBox = true; } else box.expandByObject(n); } });
    return maBox ? box : null;
  }

  function renderKusovnikCena(dily) {
    const r = sc3dSpocitejKusovnik(dily, katalogMap, pricingConfig);
    const kEl = container.querySelector("#sc3dKusovnik");
    if (!kEl) return;
    kEl.innerHTML = `
      <table class="sc-mv-table"><thead><tr><th>Položka</th><th>Ks</th><th>Cena/m</th><th>Cena/ks</th><th>Celkem</th></tr></thead>
      <tbody>${r.bom.map(g => { const zaM = (g.delka_mm && g.unit != null) ? g.unit / (g.delka_mm / 1000) : null; return `<tr><td>${escapeHtmlAdmin(g.name)}</td><td>${g.qty}</td><td>${zaM == null ? "—" : Math.round(zaM)}</td><td>${g.unit == null ? "—" : Math.round(g.unit)}</td><td>${g.total == null ? "—" : g.total.toLocaleString("cs-CZ")}</td></tr>`; }).join("")}</tbody></table>
      <div style="font-size:12.5px;margin-top:8px;display:flex;flex-direction:column;gap:2px;">
        <div>Materiál + příslušenství: <b>${sc3dCzk(r.totalMaterial + r.totalAccessory)}</b></div>
        <div>Řezání (${r.totalProfiles} × 50 Kč) + paušál: <b>${sc3dCzk(r.totalCut + r.flatFee)}</b></div>
        <div style="font-size:13.5px;margin-top:4px;">Celkem (bez ceny za spoje): <b>${sc3dCzk(r.total)}</b></div>
      </div>
      ${r.chybiCena ? `<div style="font-size:11.5px;color:var(--warn,#c77);margin-top:6px;">${r.chybiCena} položek nemá v katalogu cenu — nezapočítáno.</div>` : ""}
    `;
  }

  async function prekresli() {
    // sc3dJeKaroserie: karoserie do 3D nahledu skladove karty nepatri (jen
    // do scene.html) - viz komentar u sc3dJeKaroserie/sc3dSpocitejKusovnik.
    const dily = sc3dVyberDily(parts, volba).filter(p => !sc3dJeKaroserie(p));
    await Promise.all([...new Set(dily.map(p => p.part_id))].map(nactiGlb));
    if (disposed) return;
    posledniBox = postavScenu(dily);
    renderKusovnikCena(dily);
  }

  // Robert 2026-09-10: *"posuvnik proste nezobrazuje sest schvalenych variant
  // horniho bloku"*. Kdyz ma karta navazanych VIC sestav, jsou to varianty,
  // ktere Robert schvaloval ve scene - a ekvalizer musi prepinat PRIMO MEZI
  // NIMI. Dopocitavane osy SC3D_SKUPINY (blok x ram, skryvani dilu podle
  // roli) byly zastupce z doby, kdy skutecne varianty jeste neexistovaly;
  // vedle sebe by si odporovaly (osa by skryvala dily uz hotove varianty),
  // takze se v tom pripade nezobrazuji.
  const gc = container.querySelector("#sc3dSkupiny");
  const varianty = Array.isArray(scCurrent3dVariants) ? scCurrent3dVariants : [];
  if (!gc) {
    // nic k zaveseni - viz zobrazEkvalizer vyse
  } else if (varianty.length > 1) {
    const skupina = {
      klic: "varianta",
      nazev: "Schválené varianty",
      moznosti: varianty.map((v, i) => {
        const p = sc3dVariantaPopisky(v.name);
        // Prvni (nejstarsi) je zakladni sestava produktu - jeji nazev je
        // nazev vozidla/sestavy, ne "N/6", takze by se do tahla nevesel.
        const jeZakladni = i === 0 && !/^\d+\/\d+$/.test(p.titulek);
        let popisek = jeZakladni ? "Základní"
          : (p.titulek + (p.popis ? " " + p.popis : "")).trim();
        if (popisek.length > 44) popisek = popisek.slice(0, 43).trimEnd() + "…";
        return { k: String(v.id), n: popisek, s: v.name };
      }),
    };
    // Karta se otevira na ZAKLADNI sestave (nejstarsi id - viz lookup),
    // takze tahlo zacina na prvni polozce.
    const initIdx = 0;
    gc.appendChild(sc3dEqBand(skupina, initIdx, async (k) => {
      const id = parseInt(k, 10);
      if (!id) return;
      let nove = scVariantPartsCache.get(id);
      if (!nove) {
        try {
          const r = await fetch(`/api/product-assemblies/lookup?assembly=${id}`);
          const d = await r.json().catch(() => null);
          nove = (d && d.assembly && d.assembly.parts) || null;
          if (nove) scVariantPartsCache.set(id, nove);
        } catch (e) { nove = null; }
      }
      if (disposed) return;
      if (!nove) {
        console.warn("skladova karta: variantu #" + id + " se nepodarilo nacist");
        return;
      }
      parts = nove;
      prekresli();
      // Sekce "Kusovnik (ze sceny)" musi nasledovat posuvnik (Robert pres
      // bot8, 2026-09-11) - drive zustala viset na zakladni sestave, takze
      // pri prepnuti varianty ukazovala kusovnik JINE sestavy, nez byla
      // videt ve 3D. Bere se snimek te varianty z by-product, ne dopocet.
      scRenderBomSection(varianty.find(v => v.id === id) || null);
    }));
  } else if (maHorniBlok) {
    SC3D_SKUPINY.forEach(g => {
      const initIdx = g.moznosti.findIndex(m => m.k === volba[g.klic]);
      gc.appendChild(sc3dEqBand(g, initIdx < 0 ? 0 : initIdx, k => { volba[g.klic] = k; prekresli(); }));
    });
  }
  for (const b of container.querySelectorAll(".sc3d-viewbtn")) {
    b.addEventListener("click", () => priblizNaBox(posledniBox, parseFloat(b.dataset.az), parseFloat(b.dataset.el)));
  }

  animate();
  await prekresli();
  priblizNaBox(posledniBox, 35, 22);

  sc3dActive = {
    dispose() {
      disposed = true;
      if (raf) cancelAnimationFrame(raf);
      window.removeEventListener("resize", onResize);
      renderer.dispose();
      if (renderer.domElement.parentNode) renderer.domElement.parentNode.removeChild(renderer.domElement);
    },
  };
}

async function openStockCardModalById(productId) {
  try {
    const r = await fetch(`/api/shop/products/${productId}`);
    const data = await r.json().catch(() => ({}));
    if (!r.ok || !data.product) { alert((data && data.error) || "Produkt se nepodařilo načíst."); return; }
    openStockCardModal(data.product);
  } catch (e) {
    alert("Produkt se nepodařilo načíst.");
  }
}

// Primy odkaz na skladovou kartu: admin.html?karta=<id>#shop (Robert: prime odkazy misto "koukni do adminu").
// Ceka na prihlaseni (ADMIN_USER) a na nacteni kategorii (select v karte), pak kartu otevre.
(function () {
  const id = parseInt(new URLSearchParams(location.search).get("karta"), 10);
  if (!id) return;
  const start = Date.now();
  const pockej = setInterval(() => {
    const prihlasen = typeof ADMIN_USER !== "undefined" && ADMIN_USER;
    const kategorie = typeof shopCatFlatOptions !== "undefined" && shopCatFlatOptions.length > 0;
    if (prihlasen && (kategorie || Date.now() - start > 4000)) { clearInterval(pockej); openStockCardModalById(id); }
    else if (Date.now() - start > 20000) clearInterval(pockej);
  }, 300);
})();

// Duplikace produktu (Robert pres bot3, 2026-09-30: "potrebujeme mit moznost duplikovat/kopirovat skladovou polozku,
// produkt"). Vznikne NEAKTIVNI kopie (co se kopiruje a co ne: api/product_duplicate.py) a rovnou se otevre jeji karta,
// aby slo zkontrolovat nazev/SKU/kategorii a pak ji aktivovat. Pravo hlida server (sklad_karty/vytvorit).
async function duplicateShopProduct(productId, productName) {
  const nazev = productName || `#${productId}`;
  if (!confirm(`Duplikovat produkt „${nazev}“?\n\n`
    + "Vznikne nová NEAKTIVNÍ karta (název „… (kopie)“, SKU „…-kopie“). Zkopírují se údaje karty, kategorie, obrázky, dokumenty a fotogalerie.\n"
    + "Nekopíruje se skladový stav a pohyby, objednávky, statistiky, 3D model, otočka ani sestavy.")) return;
  let r, data = {};
  try {
    r = await fetch(`/api/shop/products/${productId}/duplicate`, { method: "POST" });
    data = await r.json().catch(() => ({}));
  } catch (e) {
    alert("Duplikace se nezdařila: server neodpovídá.");
    return;
  }
  if (!r.ok) {
    alert((data && data.error)
      || (r.status === 404 ? "Duplikace zatím není na serveru nasazená (čeká se na restart služby konfigurátoru)." : `Duplikace se nezdařila (${r.status}).`));
    return;
  }
  if (typeof loadShopProducts === "function") await loadShopProducts();
  let nova = null;
  try {
    const rp = await fetch(`/api/shop/products/${data.id}`);
    const dp = await rp.json().catch(() => ({}));
    nova = rp.ok ? dp.product : null;
  } catch (e) { /* kopie existuje, jen se jeji karta neotevre */ }
  if (!nova) { alert(`Kopie vznikla (SKU ${data.sku}), kartu se ale nepodařilo otevřít - najdeš ji v seznamu.`); return; }
  await openStockCardModal(nova);
  const c = data.copied || {};
  document.getElementById("stockCardCurrent").textContent =
    `Kopie vznikla jako NEAKTIVNÍ (SKU ${data.sku}). Zkontroluj název, SKU a kategorii a pak ji aktivuj. `
    + `Zkopírováno: ${c.categories || 0} kategorií, ${c.images || 0} obrázků, ${c.usage_images || 0} obrázků použití, `
    + `${c.documents || 0} dokumentů, ${c.gallery || 0} fotek galerie.`
    + (data.missing_files ? ` ⚠ ${data.missing_files} souborů se nepodařilo zkopírovat (chybí na disku).` : "");
}

// Adresy (slugy) produktu se tvori STROJOVE (api/product_slug.py), ne rucne (Robert 2026-10-01: "aby se prostě strojově
// vytvářely pěkné URL adresy pro SEO, ale ne ručně botem"). Sjednoti adresy VEREJNYCH produktu, ktere neodpovidaji nazvu
// (po prejmenovani, z puvodniho importu, s internim nazvem v adrese): server nejdriv udela NAHLED (provede a vrati zpet),
// ukaze se potvrzeni s poctem a priklady, teprve pak se provede. Kazda stara adresa se sama presmeruje (301), staré odkazy
// tedy funguji dal. `ids` = jen tyto produkty (odkaz v karte), jinak vsechny. Vraci odpoved serveru po provedeni, jinak null.
async function normalizeProductSlugs(ids) {
  const volej = async (dryRun) => {
    const r = await fetch("/api/shop/products/normalize-slugs", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(ids ? { dry_run: dryRun, ids } : { dry_run: dryRun }),
    });
    return { r, d: await r.json().catch(() => ({})) };
  };
  let nahled;
  try { nahled = await volej(true); } catch (e) { alert("Server neodpovídá."); return null; }
  if (!nahled.r.ok) {
    alert(nahled.d.error || (nahled.r.status === 404
      ? "Sjednocení adres zatím není na serveru nasazené (čeká se na restart služby konfigurátoru)."
      : `Sjednocení adres se nezdařilo (${nahled.r.status}).`));
    return null;
  }
  const zmeny = nahled.d.changes || [];
  if (!nahled.d.count) {
    alert(ids ? "Není co měnit: adresa odpovídá názvu, nebo produkt není veřejný (aktivní a nearchivovaný)."
      : "Všechny veřejné produkty mají adresu, která odpovídá názvu. Není co sjednocovat.");
    return null;
  }
  const duvody = { interni: "obsahuje interní název", nesedi: "neodpovídá názvu", chybi: "chybí" };
  const pocty = {};
  zmeny.forEach(c => { pocty[c.reason] = (pocty[c.reason] || 0) + 1; });
  const souhrn = Object.keys(pocty).map(k => `${pocty[k]}× ${duvody[k] || k}`).join(", ");
  const priklady = zmeny.slice(0, 6).map(c => `${c.old || "(žádná)"}  →  ${c.new}`).join("\n");
  if (!confirm(`Sjednotit adresy produktů (SEO)?\n\nProduktů se změnou adresy: ${nahled.d.count} (${souhrn}).\n`
    + "Adresa se vždy vytvoří z aktuálního názvu a stará se sama přesměruje (301), takže staré odkazy dál fungují.\n\n"
    + `Příklady:\n${priklady}${nahled.d.count > 6 ? "\n…" : ""}`)) return null;
  let hotovo;
  try { hotovo = await volej(false); } catch (e) { alert("Server neodpovídá."); return null; }
  if (!hotovo.r.ok) { alert(hotovo.d.error || `Sjednocení adres se nezdařilo (${hotovo.r.status}).`); return null; }
  alert(`Hotovo: adresa sjednocena u ${hotovo.d.count} produktů, staré adresy jsou přesměrované (301).`);
  if (typeof loadShopProducts === "function") loadShopProducts();
  return hotovo.d;
}
(function () {
  const b = document.getElementById("btnNormalizeSlugs");
  if (b) b.onclick = () => normalizeProductSlugs();
})();

// Robert 2026-07-26: "u všech přehledových tabulek, chybí nabídka
// stránkování a po kolika" - sdileny pager pro vsechny strankovane
// prehledy (produkty, zakaznici, objednavky, dodavatele, nakupni
// objednavky, doklady, e-maily, podpora, audit log, sestava k objednani,
// skladove pohyby). `state` je obycejny objekt { page, page_size } drzeny
// volajicim (per-tabulka), `onChange(newState)` se zavola po kliku na
// prev/next/velikost stranky - volajici si sam ulozi novy stav a znovu
// zavola load funkci.
const PAGER_SIZE_CHOICES = [25, 50, 100, 250];

function renderPager(containerId, meta, state, onChange) {
  const el = document.getElementById(containerId);
  if (!el) return;
  const total = meta.total ?? 0;
  const pageSize = meta.page_size ?? state.page_size;
  const page = meta.page ?? state.page;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  el.innerHTML = "";
  el.className = "pager";

  const sizeWrap = document.createElement("div");
  sizeWrap.className = "pager-size";
  const sizeLabel = document.createElement("span");
  sizeLabel.textContent = "Zobrazit po:";
  const sizeSelect = document.createElement("select");
  PAGER_SIZE_CHOICES.forEach(n => {
    const opt = document.createElement("option");
    opt.value = n;
    opt.textContent = n;
    if (n === pageSize) opt.selected = true;
    sizeSelect.appendChild(opt);
  });
  sizeSelect.onchange = () => {
    state.page_size = parseInt(sizeSelect.value, 10);
    state.page = 1;
    onChange();
  };
  sizeWrap.append(sizeLabel, sizeSelect);

  const navWrap = document.createElement("div");
  navWrap.className = "pager-nav";
  const prevBtn = document.createElement("button");
  prevBtn.type = "button";
  prevBtn.textContent = "‹ Předchozí";
  prevBtn.disabled = page <= 1;
  prevBtn.onclick = () => { state.page = page - 1; onChange(); };
  const startN = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const endN = Math.min(page * pageSize, total);
  const info = document.createElement("span");
  info.textContent = `${startN}–${endN} z ${total}`;
  const nextBtn = document.createElement("button");
  nextBtn.type = "button";
  nextBtn.textContent = "Další ›";
  nextBtn.disabled = page >= totalPages;
  nextBtn.onclick = () => { state.page = page + 1; onChange(); };
  navWrap.append(prevBtn, info, nextBtn);

  el.append(sizeWrap, navWrap);
}

// Cislo karty (shop_products.id): viditelne v seznamu produktu i v hlavicce skladove karty, klik ho zkopiruje (Robert 2026-10-04: "pridat do produktu/karet cisla karet,
// jinak nevim o jakou se jedna").
function copyCardId(btn, id) {
  const hotovo = () => { const t = btn.textContent; btn.textContent = "zkopírováno"; btn.classList.add("copied"); setTimeout(() => { btn.textContent = t; btn.classList.remove("copied"); }, 900); };
  const fallback = () => { const ta = document.createElement("textarea"); ta.value = String(id); ta.style.cssText = "position:fixed;opacity:0;"; document.body.appendChild(ta); ta.select(); try { document.execCommand("copy"); } catch (e) { /* nic */ } ta.remove(); hotovo(); };
  if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(String(id)).then(hotovo, fallback); else fallback();
}
function makeCardIdChip(id) {
  const b = document.createElement("button");
  b.type = "button"; b.className = "card-id-chip"; b.textContent = `#${id}`;
  b.title = "Číslo karty (ID produktu). Kliknutím se zkopíruje.";
  b.onclick = (ev) => { ev.stopPropagation(); copyCardId(b, id); };
  return b;
}

function renderShopProducts() {
  const tbody = document.getElementById("shopProdTbody");
  tbody.innerHTML = "";
  const LIMIT = 500;
  shopProductsCache.slice(0, LIMIT).forEach(p => {
    const tr = document.createElement("tr");
    if (p.is_archived) tr.className = "row-archived";

    const selTd = document.createElement("td");
    const selCb = document.createElement("input");
    selCb.type = "checkbox";
    selCb.checked = shopSelectedIds.has(p.id);
    selCb.onchange = () => {
      if (selCb.checked) shopSelectedIds.add(p.id); else shopSelectedIds.delete(p.id);
      updateShopBulkToolbar();
    };
    selTd.appendChild(selCb);

    const nameTd = document.createElement("td");
    nameTd.textContent = p.name;
    if (p.is_archived) {
      const abadge = document.createElement("span");
      abadge.className = "badge-archived";
      abadge.textContent = "archivováno";
      nameTd.appendChild(abadge);
    }
    const skuTd = document.createElement("td"); skuTd.textContent = p.sku;
    const catTd = document.createElement("td"); catTd.textContent = shopCatNameById(p.category_id);
    const unitTd = document.createElement("td"); unitTd.textContent = p.unit;
    // U desky musi byt z ceny poznat, co znamena (Kč za m² x Kč za celou tabuli) - bez jednotky je to jen cislo
    // a presne tak se u laminodesky 3671 (2026-09-30) zamenila cena za tabuli s cenou za m².
    const priceTd = document.createElement("td");
    priceTd.textContent = (p.is_board_material && p.price_czk_placeholder != null && p.price_czk_placeholder !== "")
      ? `${Number(p.price_czk_placeholder).toLocaleString("cs-CZ")} Kč / ${p.unit === "m2" ? "m²" : "tabuli"}`
      : (p.price_czk_placeholder ?? "");
    const stockTd = document.createElement("td");
    const stockQty = p.stock_qty ?? 0;
    const underMin = p.min_stock != null && stockQty < p.min_stock;
    const stockBadge = document.createElement("span");
    stockBadge.className = "stock-badge" + (underMin ? " under-min" : stockQty === 0 ? " zero" : stockQty < 5 ? " low" : "");
    stockBadge.textContent = `${stockQty} ${p.unit}`;
    stockTd.appendChild(stockBadge);
    // Robert 2026-07-26: "kde se to zadává?" - min/max sklad byl doteď
    // vyplnitelny jen pri zakladani noveho produktu (formular "Pridat
    // produkt"), pro existujici produkty (drtiva vetsina - Shoptet
    // import) k tomu chybelo UI, i kdyz PUT /api/shop/products/<id> pole
    // uz umel. Misto staticke bunky ted primo editovatelna dvojice poli.
    const minMaxTd = document.createElement("td");
    minMaxTd.style.cssText = "white-space:nowrap;";
    const minInput = document.createElement("input");
    minInput.type = "number"; minInput.min = "0"; minInput.placeholder = "min";
    minInput.value = p.min_stock ?? "";
    minInput.title = "Minimální skladová zásoba";
    minInput.style.cssText = "width:52px;font-size:11.5px;padding:3px 4px;";
    const maxInput = document.createElement("input");
    maxInput.type = "number"; maxInput.min = "0"; maxInput.placeholder = "max";
    maxInput.value = p.max_stock ?? "";
    maxInput.title = "Maximální skladová zásoba";
    maxInput.style.cssText = "width:52px;font-size:11.5px;padding:3px 4px;margin-left:4px;";
    const saveMinMax = async () => {
      const min_stock = minInput.value === "" ? null : parseInt(minInput.value, 10);
      const max_stock = maxInput.value === "" ? null : parseInt(maxInput.value, 10);
      await fetch(`/api/shop/products/${p.id}`, {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ min_stock, max_stock }),
      });
      p.min_stock = min_stock;
      p.max_stock = max_stock;
      const stockQtyNow = p.stock_qty ?? 0;
      const underMinNow = p.min_stock != null && stockQtyNow < p.min_stock;
      stockBadge.className = "stock-badge" + (underMinNow ? " under-min" : stockQtyNow === 0 ? " zero" : stockQtyNow < 5 ? " low" : "");
      [minInput, maxInput].forEach(inp => {
        inp.style.borderColor = "#7ed49a";
        setTimeout(() => { inp.style.borderColor = ""; }, 900);
      });
    };
    minInput.onchange = saveMinMax;
    maxInput.onchange = saveMinMax;
    minMaxTd.append(minInput, document.createTextNode(" / "), maxInput);
    const activeTd = document.createElement("td"); activeTd.textContent = p.active ? "ano" : "ne";
    // Robert 2026-07-26 (screenshot + "s tím ovšem souvisí co je tam
    // nasazeno.... uplně zbytečně např pohyby... musíme to nějak vyřešit
    // at jsou řádky uzké"): 5 tlačítek natvrdo v řádku dělalo sloupec
    // Akce zbytečně široký a při zalomení extrémně vysoký. Řádek teď nese
    // jen "Karta" (hlavní, nejčastější akce) + kompaktní "⋮" menu se
    // zbytkem (Příjem, Výdej, Archivovat, Smazat) - viz .row-more-menu CSS.
    const actionsTd = document.createElement("td");
    actionsTd.style.cssText = "position:relative;white-space:nowrap;";
    const cardBtn = document.createElement("button");
    cardBtn.style.cssText = "padding:4px 9px;font-size:11.5px;background:none;border:1px solid #3a3f4a;color:#c7ccd4;margin-right:4px;";
    cardBtn.textContent = "Karta";
    cardBtn.onclick = () => openStockCardModal(p);

    const moreBtn = document.createElement("button");
    moreBtn.type = "button";
    moreBtn.className = "row-more-btn";
    moreBtn.textContent = "⋮";
    moreBtn.title = "Další akce";

    const menu = document.createElement("div");
    menu.className = "row-more-menu";

    const receiptItem = document.createElement("button");
    receiptItem.textContent = "Příjem";
    receiptItem.onclick = () => { closeAllRowMoreMenus(); openStockModal(p, "receipt"); };

    const issueItem = document.createElement("button");
    issueItem.textContent = "Výdej";
    issueItem.onclick = () => { closeAllRowMoreMenus(); openStockModal(p, "issue"); };

    const dupItem = document.createElement("button");
    dupItem.textContent = "Duplikovat";
    dupItem.title = "Vytvořit NEAKTIVNÍ kopii této karty";
    dupItem.onclick = () => { closeAllRowMoreMenus(); duplicateShopProduct(p.id, p.name); };

    const archiveItem = document.createElement("button");
    archiveItem.textContent = p.is_archived ? "Obnovit" : "Archivovat";
    archiveItem.onclick = async () => {
      closeAllRowMoreMenus();
      await fetch(`/api/shop/products/${p.id}`, {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ is_archived: !p.is_archived }),
      });
      loadShopProducts();
    };

    const delItem = document.createElement("button");
    delItem.className = "danger";
    delItem.textContent = "Smazat";
    delItem.onclick = async () => {
      closeAllRowMoreMenus();
      if (!confirm(`Smazat produkt "${p.name}"? (Zvaž raději Archivovat, jde vzít zpět.)`)) return;
      await fetch(`/api/shop/products/${p.id}`, { method: "DELETE" });
      loadShopProducts();
    };

    menu.append(receiptItem, issueItem, dupItem, archiveItem, delItem);
    moreBtn.onclick = (e) => {
      e.stopPropagation();
      const isOpen = menu.classList.contains("open");
      closeAllRowMoreMenus();
      if (!isOpen) menu.classList.add("open");
    };
    actionsTd.append(cardBtn, moreBtn, menu);
    const idTd = document.createElement("td"); idTd.appendChild(makeCardIdChip(p.id));
    tr.append(selTd, idTd, skuTd, nameTd, catTd, unitTd, priceTd, stockTd, minMaxTd, activeTd, actionsTd);
    // Robert 2026-07-26 ("nejde jen o hover... kliknutim na radek...
    // produkty, doklady, pohyby... se musi prejit na detail"): klik
    // kdekoli na radek otevira Skladovou kartu, krome kliku na
    // interaktivni prvky (checkbox, min/max inputy, Karta/⋮ tlacitka a
    // jejich menu), ty se chovaji standardne.
    tr.style.cursor = "pointer";
    tr.onclick = (e) => {
      if (e.target.closest("input, button, .row-more-menu")) return;
      openStockCardModal(p);
    };
    tbody.appendChild(tr);
  });
  if (shopProductsCache.length > LIMIT) {
    const info = document.createElement("tr");
    const td = document.createElement("td");
    td.colSpan = 10;
    td.style.cssText = "color:#666;font-size:12px;";
    td.textContent = `Zobrazeno prvních ${LIMIT} z ${shopProductsCache.length} - zúžit přes filtr/hledání.`;
    info.appendChild(td);
    tbody.appendChild(info);
  }
}

function updateShopBulkToolbar() {
  const bar = document.getElementById("shopBulkToolbar");
  const count = shopSelectedIds.size;
  bar.classList.toggle("active", count > 0);
  document.getElementById("shopBulkCount").textContent = `${count} vybráno`;
  // odkaz "vybrat vsechny odpovidajici filtru" jen kdyz existuje vic
  // produktu, nez kolik jich je na aktualne nactene strance
  const link = document.getElementById("shopSelectAllMatching");
  if (shopProdLastTotal > shopProductsCache.length) {
    link.style.display = "";
    link.textContent = shopSelectedIds.size === shopProdLastTotal
      ? `Vybráno všech ${shopProdLastTotal} odpovídajících filtru`
      : `Vybrat všechny odpovídající filtru (${shopProdLastTotal})`;
  } else {
    link.style.display = "none";
  }
}

// Nacte VSECHNA id produktu odpovidajici aktualne nastavenym filtrum
// (ne jen prave zobrazenou stranku) a oznaci je jako vybrane - teprve
// tim jde hromadna akce (napr. Smazat) skutecne aplikovat na VSECHNY
// archivovane produkty najednou, ne jen po strankach.
document.getElementById("shopSelectAllMatching").onclick = async (e) => {
  e.preventDefault();
  if (shopProdLastTotal <= 0) return;
  if (shopProdIdFilter() !== null) {                    // hledani podle ID karty: odpovida jedine nactena karta
    shopProductsCache.forEach(p => shopSelectedIds.add(p.id));
    renderShopProducts();
    updateShopBulkToolbar();
    return;
  }
  const categoryId = document.getElementById("shopProdCategoryFilter").value;
  const q = document.getElementById("shopProdSearch").value.trim();
  const sku = document.getElementById("shopProdSkuSearch").value.trim();
  const lowStockOnly = document.getElementById("shopProdLowStockOnly").checked;
  const showArchived = document.getElementById("shopProdShowArchived").checked;
  const activeFilter = document.getElementById("shopProdActiveFilter").value;
  const inSceneOnly = document.getElementById("shopProdInSceneOnly").checked;
  // Robert 2026-08 ("maximalne se oznaci jen 250"): server ma strop
  // page_size=250 (get_pagination_args v app.py) - jeden dotaz s
  // page_size=total tise dostal jen prvnich 250. Stahuje se po
  // strankach 250, dokud nejsou vsechny.
  const PAGE = 250;
  try {
    const link = document.getElementById("shopSelectAllMatching");
    let page = 1, fetched = 0, total = shopProdLastTotal;
    while (fetched < total) {
      const params = new URLSearchParams({ all: "1", page: String(page), page_size: String(PAGE) });
      if (categoryId) params.set("category_id", categoryId);
      if (q) params.set("q", q);
      if (sku) params.set("sku", sku);
      if (lowStockOnly) params.set("low_stock", "1");
      if (inSceneOnly) params.set("in_scene", "1");
      if (showArchived) params.set("archived", "1");
      if (activeFilter === "active") params.set("active_only", "1");
      else if (activeFilter === "inactive") params.set("inactive_only", "1");
      const r = await fetch(`/api/shop/products?${params.toString()}`);
      const data = await r.json();
      const rows = data.products || [];
      if (!rows.length) break; // pojistka proti nekonecne smycce
      rows.forEach(p => shopSelectedIds.add(p.id));
      fetched += rows.length;
      total = data.total ?? total;
      link.textContent = `Vybírám… ${Math.min(fetched, total)}/${total}`;
      page++;
    }
    renderShopProducts();
    updateShopBulkToolbar();
  } catch (e2) {
    document.getElementById("shopProdErr").textContent = "Nepodařilo se načíst všechny odpovídající produkty.";
  }
};

document.getElementById("shopSelectAll").onchange = (e) => {
  const LIMIT = 500;
  if (e.target.checked) {
    shopProductsCache.slice(0, LIMIT).forEach(p => shopSelectedIds.add(p.id));
  } else {
    shopSelectedIds.clear();
  }
  renderShopProducts();
  updateShopBulkToolbar();
};

// Filtry vždy resetují stránkování zpět na 1 (jinak by šlo uvíznout na
// prázdné stránce 5, když nový filtr vrátí jen 2 výsledky).
const shopProdReload = () => { shopProdPagerState.page = 1; loadShopProducts(); };
document.getElementById("shopProdLowStockOnly").addEventListener("change", shopProdReload);
document.getElementById("shopProdInSceneOnly").addEventListener("change", shopProdReload);
document.getElementById("shopProdShowArchived").addEventListener("change", shopProdReload);
document.getElementById("shopProdActiveFilter").addEventListener("change", shopProdReload);

document.getElementById("shopBulkApplyCategory").onclick = async () => {
  const categoryId = document.getElementById("shopBulkCategory").value;
  if (!categoryId || !shopSelectedIds.size) return;
  await fetch("/api/shop/products/bulk", {
    method: "PUT", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ids: [...shopSelectedIds], category_id: parseInt(categoryId, 10) }),
  });
  loadShopProducts();
};
document.getElementById("shopBulkArchive").onclick = async () => {
  if (!shopSelectedIds.size) return;
  await fetch("/api/shop/products/bulk", {
    method: "PUT", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ids: [...shopSelectedIds], is_archived: true }),
  });
  loadShopProducts();
};
document.getElementById("shopBulkUnarchive").onclick = async () => {
  if (!shopSelectedIds.size) return;
  await fetch("/api/shop/products/bulk", {
    method: "PUT", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ids: [...shopSelectedIds], is_archived: false }),
  });
  loadShopProducts();
};

document.getElementById("shopBulkDelete").onclick = async () => {
  if (!shopSelectedIds.size) return;
  if (!confirm(`Opravdu smazat ${shopSelectedIds.size} vybraných produktů? Tuto akci nelze vrátit zpět (zvaž raději Archivovat).`)) return;
  const r = await fetch("/api/shop/products/bulk-delete", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ids: [...shopSelectedIds] }),
  });
  const data = await r.json().catch(() => ({}));
  shopSelectedIds.clear();
  if (data.failed && data.failed.length) {
    alert(`Smazáno: ${data.deleted}. Nešlo smazat: ${data.failed.length} (např. produkt použitý v nákupní objednávce).`);
  }
  loadShopProducts();
};

document.getElementById("btnImportProductsCsv").onclick = async () => {
  const fileInput = document.getElementById("importProductsCsvFile");
  const resultEl = document.getElementById("csvImportResult");
  if (!fileInput.files.length) { resultEl.textContent = "Vyber nejdřív CSV soubor."; return; }
  const formData = new FormData();
  formData.append("file", fileInput.files[0]);
  resultEl.textContent = "Importuji…";
  const r = await fetch("/api/shop/products/import", { method: "POST", body: formData });
  const data = await r.json();
  if (!r.ok) { resultEl.textContent = data.error || "Chyba importu."; return; }
  resultEl.textContent = `Hotovo: ${data.created} nových, ${data.updated} aktualizováno` +
    (data.errors && data.errors.length ? `, ${data.errors.length} chyb (${data.errors.slice(0, 3).join("; ")})` : "");
  fileInput.value = "";
  loadShopProductCategoryOptions();
  loadShopProducts();
};

document.getElementById("shopProdCategoryFilter").addEventListener("change", shopProdReload);
let shopSearchDebounce;
document.getElementById("shopProdSearch").addEventListener("input", () => {
  clearTimeout(shopSearchDebounce);
  shopSearchDebounce = setTimeout(shopProdReload, 300);
});
let shopSkuSearchDebounce;
document.getElementById("shopProdSkuSearch").addEventListener("input", () => {
  clearTimeout(shopSkuSearchDebounce);
  shopSkuSearchDebounce = setTimeout(shopProdReload, 300);
});
let shopIdSearchDebounce;
document.getElementById("shopProdIdSearch").addEventListener("input", () => {
  clearTimeout(shopIdSearchDebounce);
  shopIdSearchDebounce = setTimeout(shopProdReload, 300);
});

document.getElementById("btnAddShopProduct").onclick = async () => {
  const sku = document.getElementById("newShopProdSku").value.trim();
  const name = document.getElementById("newShopProdName").value.trim();
  const category_id = document.getElementById("newShopProdCategory").value || null;
  const unit = document.getElementById("newShopProdUnit").value.trim() || "ks";
  const priceStr = document.getElementById("newShopProdPrice").value;
  const price_czk_placeholder = priceStr === "" ? null : parseFloat(priceStr);
  const minStr = document.getElementById("newShopProdMinStock").value;
  const maxStr = document.getElementById("newShopProdMaxStock").value;
  const min_stock = minStr === "" ? null : parseInt(minStr, 10);
  const max_stock = maxStr === "" ? null : parseInt(maxStr, 10);
  if (!sku || !name) { document.getElementById("shopProdErr").textContent = "Vyplň SKU i název."; return; }
  const r = await fetch("/api/shop/products", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sku, name, category_id, unit, price_czk_placeholder, min_stock, max_stock }),
  });
  const data = await r.json();
  if (!r.ok) { document.getElementById("shopProdErr").textContent = data.error || "Chyba."; return; }
  document.getElementById("newShopProdSku").value = "";
  document.getElementById("newShopProdName").value = "";
  document.getElementById("newShopProdPrice").value = "";
  document.getElementById("newShopProdMinStock").value = "";
  document.getElementById("newShopProdMaxStock").value = "";
  document.getElementById("shopProdErr").textContent = "";
  loadShopProducts();
};

// --- Skladove pohyby (prijemky/vydejky) + skladova karta (Robert
// 2026-07-25: "začni rozšiřovat možnosti skladového systému, přijemky,
// vydejky, skladové karty pokud ještě nemáš vše co bylo vidět v
// skladapp" - inspirace ST_Transaction ze skladapp, zjednoduseno bez
// fyzickych skladu/polic/HMI na produkt + typ + mnozstvi + volitelna
// cena/poznamka/doklad). ---
let stockModalProduct = null;
let stockModalType = null;

function openStockModal(product, type) {
  stockModalProduct = product;
  stockModalType = type;
  document.getElementById("stockModalTitle").textContent = type === "receipt" ? "Příjem na sklad" : "Výdej ze skladu";
  document.getElementById("stockModalProductName").textContent = `${product.name} (${product.sku}) — aktuální stav: ${product.stock_qty ?? 0} ${product.unit}`;
  document.getElementById("stockQty").value = "";
  document.getElementById("stockUnitPrice").value = "";
  document.getElementById("stockDocNumber").value = "";
  document.getElementById("stockNote").value = "";
  document.getElementById("stockModalErr").textContent = "";
  document.getElementById("stockModal").classList.add("open");
}

document.getElementById("stockModalCancel").onclick = () => {
  document.getElementById("stockModal").classList.remove("open");
};

document.getElementById("stockModalConfirm").onclick = async () => {
  const qty = parseInt(document.getElementById("stockQty").value, 10);
  const unitPriceStr = document.getElementById("stockUnitPrice").value;
  const unit_price_czk = unitPriceStr === "" ? null : parseFloat(unitPriceStr);
  const document_number = document.getElementById("stockDocNumber").value.trim();
  const note = document.getElementById("stockNote").value.trim();
  const errEl = document.getElementById("stockModalErr");
  if (!qty || qty <= 0) { errEl.textContent = "Vyplň kladné množství."; return; }
  const r = await fetch("/api/shop/stock/movements", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      product_id: stockModalProduct.id, movement_type: stockModalType, qty,
      unit_price_czk, document_number, note,
    }),
  });
  const data = await r.json();
  if (!r.ok) { errEl.textContent = data.error || "Chyba."; return; }
  document.getElementById("stockModal").classList.remove("open");
  loadShopProducts();
  if (typeof loadStockMovements === "function") loadStockMovements();
};

function escapeHtmlAdmin(s) {
  const d = document.createElement("div");
  d.textContent = s == null ? "" : s;
  return d.innerHTML;
}

let stockMoveProductsCache = [];

async function loadStockMoveProductOptions() {
  try {
    const r = await fetch("/api/shop/products?all=1");
    const data = await r.json();
    stockMoveProductsCache = data.products || [];
    const opts = stockMoveProductsCache
      .map(p => `<option value="${p.id}">${escapeHtmlAdmin(p.name)} (${escapeHtmlAdmin(p.sku)})</option>`)
      .join("");
    document.getElementById("smFilterProduct").innerHTML = '<option value="">Všechny produkty</option>' + opts;
    // bot16, 2026-09-29 (Robert primo: "novy pohyb se urcite nebude
    // zadavat roletkou ale musi tam byt normalni textove pole s
    // napovedou") - #smNewProduct je ted <input list="smNewProductList">,
    // ne <select> - datalist nabizi napovedu pri psani, ale na rozdil
    // od <select> nema oddelene value/label (co se zobrazi = co se
    // vlozi do pole po vyberu), proto se pro rozliseni pouziva presny
    // text "Nazev (SKU)" - viz resolveStockMoveProduct nize.
    document.getElementById("smNewProductList").innerHTML = stockMoveProductsCache
      .map(p => `<option value="${escapeHtmlAdmin(p.name)} (${escapeHtmlAdmin(p.sku)})">`)
      .join("");
  } catch (e) {
    // ticho - filtr produktu zustane prazdny, zbytek zalozky funguje dal
  }
}

// Najde produkt podle presne napsaneho textu "Nazev (SKU)" (vybraneho z
// napovedy), nebo aspon podle presne shody samotneho SKU/nazvu (kdyby
// admin nevybral z napovedy a napsal jen cast rucne) - jinak null,
// volajici pak ukaze chybovou hlasku misto ticheho selhani.
function resolveStockMoveProduct(text) {
  const t = (text || "").trim();
  if (!t) return null;
  const bySuffix = stockMoveProductsCache.find(p => `${p.name} (${p.sku})` === t);
  if (bySuffix) return bySuffix;
  return stockMoveProductsCache.find(p => p.sku === t || p.name === t) || null;
}

let stockMovesCache = [];
// Stránkování (task #78/87) - nahrazuje puvodni pevny LIMIT 500 v mode=list
const stockMovesPagerState = { page: 1, page_size: 50 };

async function loadStockMovements() {
  const params = new URLSearchParams({
    mode: "list", page: stockMovesPagerState.page, page_size: stockMovesPagerState.page_size,
  });
  const type = document.getElementById("smFilterType").value;
  const productId = document.getElementById("smFilterProduct").value;
  const q = document.getElementById("smFilterQ").value.trim();
  const dateFrom = document.getElementById("smFilterDateFrom").value;
  const dateTo = document.getElementById("smFilterDateTo").value;
  if (type) params.set("type", type);
  if (productId) params.set("product_id", productId);
  if (q) params.set("q", q);
  if (dateFrom) params.set("date_from", dateFrom);
  if (dateTo) params.set("date_to", dateTo);
  try {
    const r = await fetch(`/api/shop/stock/movements?${params.toString()}`);
    const data = await r.json();
    stockMovesCache = data.movements || [];
    renderStockMoves();
    renderPager("stockMovesPager", data, stockMovesPagerState, loadStockMovements);
  } catch (e) {
    document.getElementById("stockMovesErr").textContent = "Nepodařilo se načíst pohyby.";
  }
}

function renderStockMoves() {
  const tbody = document.getElementById("stockMovesTbody");
  if (!stockMovesCache.length) {
    tbody.innerHTML = '<tr><td colspan="11" style="color:#666;">Žádné pohyby neodpovídají filtru.</td></tr>';
    updateSmMovesBulkToolbar();
    return;
  }
  tbody.innerHTML = stockMovesCache.map(m => {
    const date = new Date(m.created_at).toLocaleString("cs-CZ");
    const typeLabel = m.movement_type === "receipt"
      ? '<span class="sc-mv-receipt">+ Příjem</span>'
      : '<span class="sc-mv-issue">− Výdej</span>';
    const who = m.user_name || m.user_email || "";
    return `<tr data-product-id="${m.product_id ?? ""}" style="cursor:pointer;">
      <td><input type="checkbox" class="smMovesChk" data-id="${m.id}"></td>
      <td>${date}</td>
      <td>${escapeHtmlAdmin(m.product_name)}</td>
      <td>${escapeHtmlAdmin(m.product_sku)}</td>
      <td>${typeLabel}</td>
      <td>${m.qty} ${escapeHtmlAdmin(m.product_unit)}</td>
      <td>${m.unit_price_czk != null ? m.unit_price_czk.toLocaleString("cs-CZ") + " Kč" : ""}</td>
      <td>${escapeHtmlAdmin(m.document_number || "")}</td>
      <td>${escapeHtmlAdmin(m.note || "")}</td>
      <td>${escapeHtmlAdmin(who)}</td>
      <td><button class="smMovesFotoBtn" data-id="${m.id}" title="Fotky k pohybu">📷</button></td>
    </tr>`;
  }).join("");
  // Robert 2026-07-26: klik na radek pohybu -> Skladova karta produktu,
  // krome kliku na checkbox (bulk mazani pohybu s vracenim stavu skladu)
  // a krome 📷 tlacitka (fotky k pohybu, Robert 2026-07-31).
  tbody.querySelectorAll("tr[data-product-id]").forEach(tr => {
    const pid = tr.dataset.productId;
    if (!pid) return;
    tr.onclick = (e) => {
      if (e.target.closest("input") || e.target.closest(".smMovesFotoBtn")) return;
      openStockCardModalById(parseInt(pid, 10));
    };
  });
  tbody.querySelectorAll(".smMovesFotoBtn").forEach(btn => {
    btn.onclick = (e) => {
      e.stopPropagation();
      openAttachmentModal("stock_movement", parseInt(btn.dataset.id, 10), "Fotky – skladový pohyb #" + btn.dataset.id);
    };
  });
  tbody.querySelectorAll(".smMovesChk").forEach(chk => chk.addEventListener("change", updateSmMovesBulkToolbar));
  updateSmMovesBulkToolbar();
}

function updateSmMovesBulkToolbar() {
  const checked = Array.from(document.querySelectorAll(".smMovesChk:checked"));
  const toolbar = document.getElementById("smMovesBulkToolbar");
  const count = document.getElementById("smMovesBulkCount");
  if (checked.length > 0) {
    toolbar.classList.add("active");
    count.textContent = checked.length + " vybráno";
  } else {
    toolbar.classList.remove("active");
  }
}

document.getElementById("smMovesSelectAll").onchange = (e) => {
  document.querySelectorAll(".smMovesChk").forEach(chk => { chk.checked = e.target.checked; });
  updateSmMovesBulkToolbar();
};

document.getElementById("smMovesBulkDelete").onclick = async () => {
  const ids = Array.from(document.querySelectorAll(".smMovesChk:checked")).map(chk => parseInt(chk.dataset.id, 10));
  if (!ids.length) return;
  if (!confirm(`Smazat ${ids.length} vybraných skladových pohybů? Stav skladu dotčených produktů se odpovídajícím způsobem vrátí zpět (příjem se odečte, výdej se přičte).`)) return;
  const r = await fetch("/api/shop/stock/movements/bulk-delete", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ids }),
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) { alert(data.error || "Chyba při mazání."); return; }
  if (data.failed && data.failed.length) {
    alert(`${data.deleted} pohybů smazáno, ${data.failed.length} se nepodařilo smazat:\n`
      + data.failed.map(f => `#${f.id}: ${f.error}`).join("\n"));
  }
  loadStockMovements();
};

// ==================== RYCHLE PREDVOLBY DATUMOVEHO FILTRU ====================
// Robert 2026-07-26: "na vsech prehledech namisto vyberu datumu dej: dnes/
// vcera/posledni tyden/minuly tyden/posledni mesic/minuly mesic" - nahrazuje
// puvodni dva <input type="date"> (Od/Do) jednim vyberem predvolby napric
// vsemi filtry v adminu (objednavky, doklady, e-maily, podpora, skladove
// pohyby). Puvodni Od/Do inputy zustavaji v DOM jako skryte (existujici
// cteci kod filteru je necha beze zmeny), predvolba jen dopocita a vyplni
// jejich .value a spusti stavajici tlacitko "Filtrovat".
//
// "posledni X" = plovouci poslednich N dni vcetne dneska (jako "last 7
// days" v analytics nastrojich), "minuly X" = predchozi UZAVRENY
// kalendarni tyden/mesic (pondeli-nedele / 1. az posledni den mesice).
function computeDatePresetRange(key) {
  const pad = n => String(n).padStart(2, "0");
  const iso = d => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  const addDays = (d, n) => { const r = new Date(d); r.setDate(r.getDate() + n); return r; };
  const today = new Date();
  today.setHours(0, 0, 0, 0);

  switch (key) {
    case "today":
      return { from: iso(today), to: iso(today) };
    case "yesterday": {
      const y = addDays(today, -1);
      return { from: iso(y), to: iso(y) };
    }
    case "last7":
      return { from: iso(addDays(today, -6)), to: iso(today) };
    case "prevweek": {
      const dow = (today.getDay() + 6) % 7; // 0=pondeli ... 6=nedele
      const thisMonday = addDays(today, -dow);
      const prevMonday = addDays(thisMonday, -7);
      const prevSunday = addDays(thisMonday, -1);
      return { from: iso(prevMonday), to: iso(prevSunday) };
    }
    case "last30":
      return { from: iso(addDays(today, -29)), to: iso(today) };
    case "prevmonth": {
      const firstThisMonth = new Date(today.getFullYear(), today.getMonth(), 1);
      const lastPrevMonth = addDays(firstThisMonth, -1);
      const firstPrevMonth = new Date(lastPrevMonth.getFullYear(), lastPrevMonth.getMonth(), 1);
      return { from: iso(firstPrevMonth), to: iso(lastPrevMonth) };
    }
    default:
      return { from: "", to: "" };
  }
}

function wireDatePresetSelect(selectId, fromId, toId, applyBtnId) {
  const sel = document.getElementById(selectId);
  if (!sel) return;
  sel.onchange = () => {
    const range = sel.value ? computeDatePresetRange(sel.value) : { from: "", to: "" };
    document.getElementById(fromId).value = range.from;
    document.getElementById(toId).value = range.to;
    const btn = document.getElementById(applyBtnId);
    if (btn) btn.click();
  };
}

wireDatePresetSelect("smFilterDatePreset", "smFilterDateFrom", "smFilterDateTo", "smFilterApply");
wireDatePresetSelect("orderFilterDatePreset", "orderFilterDateFrom", "orderFilterDateTo", "orderSearchApply");
wireDatePresetSelect("docFilterDatePreset", "docFilterDateFrom", "docFilterDateTo", "docSearchApply");
wireDatePresetSelect("emailFilterDatePreset", "emailFilterDateFrom", "emailFilterDateTo", "emailSearchApply");
wireDatePresetSelect("supportFilterDatePreset", "supportFilterDateFrom", "supportFilterDateTo", "supportSearchApply");

document.getElementById("smFilterApply").onclick = () => { stockMovesPagerState.page = 1; loadStockMovements(); };
document.getElementById("smFilterReset").onclick = () => {
  document.getElementById("smFilterType").value = "";
  document.getElementById("smFilterProduct").value = "";
  document.getElementById("smFilterQ").value = "";
  document.getElementById("smFilterDatePreset").value = "";
  document.getElementById("smFilterDateFrom").value = "";
  document.getElementById("smFilterDateTo").value = "";
  stockMovesPagerState.page = 1;
  loadStockMovements();
};

document.getElementById("smNewReceipt").onclick = () => {
  const input = document.getElementById("smNewProduct");
  const errEl = document.getElementById("smNewProductErr");
  const p = resolveStockMoveProduct(input.value);
  if (!p) { errEl.textContent = "Vyber produkt z nápovědy (název nebo SKU musí přesně sedět)."; return; }
  errEl.textContent = "";
  openStockModal(p, "receipt");
};
document.getElementById("smNewIssue").onclick = () => {
  const input = document.getElementById("smNewProduct");
  const errEl = document.getElementById("smNewProductErr");
  const p = resolveStockMoveProduct(input.value);
  if (!p) { errEl.textContent = "Vyber produkt z nápovědy (název nebo SKU musí přesně sedět)."; return; }
  errEl.textContent = "";
  openStockModal(p, "issue");
};

document.getElementById("btnGenTestReceipts").onclick = async () => {
  const count = parseInt(document.getElementById("genTestReceiptsCount").value, 10) || 50;
  const item_pct = parseInt(document.getElementById("genTestReceiptsItemPct").value, 10) || 100;
  const resultEl = document.getElementById("genTestReceiptsResult");
  if (!confirm(`Vygenerovat ${count} náhodných testovacích příjemek? Zapíše se to do skladové historie.`)) return;
  resultEl.textContent = "Generuji…";
  const r = await fetch("/api/shop/stock/test-receipts", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ count, item_pct }),
  });
  const data = await r.json();
  if (!r.ok) { resultEl.textContent = data.error || "Chyba."; return; }
  resultEl.textContent = `Hotovo: vygenerováno ${data.created} příjemek.`;
  loadStockMovements();
  loadShopProducts();
  if (typeof loadDashboard === "function") loadDashboard();
};

document.getElementById("btnGenTestIssues").onclick = async () => {
  const count = parseInt(document.getElementById("genTestIssuesCount").value, 10) || 50;
  const item_pct = parseInt(document.getElementById("genTestIssuesItemPct").value, 10) || 100;
  const resultEl = document.getElementById("genTestIssuesResult");
  if (!confirm(`Vygenerovat ${count} náhodných testovacích výdejek? Zapíše se to do skladové historie a odečte se to ze skladu.`)) return;
  resultEl.textContent = "Generuji…";
  const r = await fetch("/api/shop/stock/test-issues", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ count, item_pct }),
  });
  const data = await r.json();
  if (!r.ok) { resultEl.textContent = data.error || "Chyba."; return; }
  resultEl.textContent = data.note ? `Hotovo: vygenerováno ${data.created} výdejek. ${data.note}` : `Hotovo: vygenerováno ${data.created} výdejek.`;
  loadStockMovements();
  loadShopProducts();
  if (typeof loadDashboard === "function") loadDashboard();
};

// Popisky poli skladove karty (Robert 2026-07-28: "tyto nadpisy udelejme
// jako databazove polozky, tzn budou se moci menit") - nacteny jednou
// (lazy, pri prvnim otevreni karty) z GET /api/admin/field-labels,
// drzeny v cache, kazdy popisek ma male tuzka ikonka pro rychlou
// zmenu primo v kontextu (misto samostatne nastavovaci obrazovky).
let productFieldLabels = null;
let productFieldOptions = {};
async function ensureProductFieldLabels() {
  if (productFieldLabels) return productFieldLabels;
  try {
    const r = await fetch("/api/admin/field-labels");
    const data = await r.json();
    productFieldLabels = data.labels || {};
    productFieldOptions = data.options || {};
  } catch (e) {
    productFieldLabels = {};
    productFieldOptions = {};
  }
  return productFieldLabels;
}
function scFieldLabel(key) {
  const text = (productFieldLabels && productFieldLabels[key]) || key;
  return `<div class="sc-stat-label">${escapeHtmlAdmin(text)}<span class="sc-label-edit" data-key="${key}" title="Přejmenovat popisek">✎</span></div>`;
}
// Robert 2026-07-28 (po AskUserQuestion "Fixní seznam možností pro
// vyplňování"): pokud má pole v Nastavení definovaný aspoň 1 možnost,
// vykreslí se select misto volneho textu (aktualni hodnota se prida do
// nabidky, i kdyz v seznamu neni - at se needitovanim nahodou neztrati
// stavajici udaj z importu).
function scFieldInput(key, id, currentValue) {
  const opts = productFieldOptions[key] || [];
  const val = currentValue || "";
  if (opts.length) {
    const allOpts = (val && !opts.includes(val)) ? [val, ...opts] : opts;
    const optionsHtml = `<option value="">—</option>` + allOpts.map(o =>
      `<option value="${escapeHtmlAdmin(o)}" ${o === val ? "selected" : ""}>${escapeHtmlAdmin(o)}</option>`
    ).join("");
    return `<select id="${id}" style="width:100%;">${optionsHtml}</select>`;
  }
  return `<input id="${id}" type="text" value="${escapeHtmlAdmin(val)}" style="width:100%;">`;
}

// Zalozka Nastaveni - stejnych 8 klicu jako PRODUCT_FIELD_LABEL_DEFAULTS
// v api/app.py (drzet synchronne, kdyby pribyl novy klic). U poli s
// "hasOptions: true" jde nastavit fixni seznam moznosti (viz
// scFieldInput() vyse); Kategorie (Shoptet) ma vlastni napovedu ze
// stromu kategorii (datalist) a kodova pole jsou CSV seznamy - u obou
// by jednoduchy select nedaval smysl, proto se u nich nabidka moznosti
// nezobrazuje (jen prejmenovani popisku).
const FIELD_SETTINGS_KEYS = [
  { key: "manufacturer", hasOptions: true },
  { key: "supplier_name", hasOptions: false, note: "Dodavatel je skutečná firma napojená na Nákupní objednávky - spravuje se v záložce Nákupní objednávky › Dodavatelé, zde jen přejmenování popisku." },
  { key: "ean", hasOptions: true },
  { key: "warranty", hasOptions: true },
  { key: "category_path", hasOptions: false, note: "Napověda se řídí stromem kategorií (viz záložka Kategorie), fixní seznam se zde nenastavuje." },
  { key: "availability_text", hasOptions: true },
  { key: "alternative_codes", hasOptions: false, note: "Více kódů oddělených čárkou u produktu, fixní seznam se zde nenastavuje." },
  { key: "related_codes", hasOptions: false, note: "Více kódů oddělených čárkou u produktu, fixní seznam se zde nenastavuje." },
];

async function loadFieldSettings() {
  const errEl = document.getElementById("fieldSettingsErr");
  errEl.textContent = "";
  try {
    const r = await fetch("/api/admin/field-labels");
    const data = await r.json();
    if (!r.ok) { errEl.textContent = data.error || "Chyba načtení."; return; }
    productFieldLabels = data.labels || {};
    productFieldOptions = data.options || {};
    renderFieldSettings();
  } catch (e) {
    errEl.textContent = "Nepodařilo se načíst nastavení (chyba spojení).";
  }
}

// Robert 2026-08-08 ("problémy s tím přihlašováním pořád dokola" ->
// misto vypnuti hesla pro cely system radeji trvaly odkaz jen pro
// jeho ucet) - stejny backend endpoint jako uz mel capture.html
// (api/app.py::auth_magic_generate), jen jina cilova stranka
// (/login.html?magic=<token>&next=/admin.html misto capture.html).
document.getElementById("btnGenMagicLink").addEventListener("click", async () => {
  const btn = document.getElementById("btnGenMagicLink");
  btn.disabled = true;
  try {
    const r = await fetch("/api/auth/magic-generate", { method: "POST" });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) { alert(data.error || "Nepodařilo se vytvořit odkaz."); return; }
    const link = `${location.origin}/login.html?magic=${data.token}&next=${encodeURIComponent("/admin.html")}`;
    try { await navigator.clipboard.writeText(link); } catch (e) { /* schranka nedostupna, odkaz je i tak v dialogu nize */ }
    prompt("Trvalý odkaz bez hesla (zkopírován do schránky) - ulož si ho jako záložku. Vygenerováním nového se tenhle zneplatní:", link);
  } finally {
    btn.disabled = false;
  }
});

function renderFieldSettings() {
  const wrap = document.getElementById("fieldSettingsRows");
  wrap.innerHTML = FIELD_SETTINGS_KEYS.map(f => {
    const label = productFieldLabels[f.key] || f.key;
    const optionsText = (productFieldOptions[f.key] || []).join("\n");
    const optionsBlock = f.hasOptions
      ? `<div style="margin-top:8px;">
          <label style="font-size:11px;color:#9aa4b2;display:block;margin-bottom:4px;">Fixní možnosti (jedna na řádek, prázdné = volný text)</label>
          <textarea class="fs-options" data-key="${f.key}" rows="3" style="width:100%;font-family:inherit;" placeholder="např. Skladem${"\n"}U dodavatele${"\n"}Vyprodáno">${escapeHtmlAdmin(optionsText)}</textarea>
          <button type="button" class="fs-save-options" data-key="${f.key}" style="margin-top:6px;">Uložit možnosti</button>
          <span class="fs-options-msg" data-key="${f.key}" style="font-size:11.5px;color:#7ec488;margin-left:8px;"></span>
        </div>`
      : `<div class="hint" style="margin-top:8px;font-size:11.5px;">${escapeHtmlAdmin(f.note || "")}</div>`;
    return `<div class="sc-stat sc-span-full" style="margin-bottom:14px;padding-bottom:14px;border-bottom:1px solid var(--border-faint);">
      <label style="font-size:11px;color:#9aa4b2;display:block;margin-bottom:4px;">Popisek pole „${escapeHtmlAdmin(f.key)}“</label>
      <div style="display:flex;gap:8px;align-items:center;">
        <input class="fs-label" data-key="${f.key}" type="text" value="${escapeHtmlAdmin(label)}" style="flex:1;">
        <button type="button" class="fs-save-label" data-key="${f.key}">Uložit název</button>
        <span class="fs-label-msg" data-key="${f.key}" style="font-size:11.5px;color:#7ec488;"></span>
      </div>
      ${optionsBlock}
    </div>`;
  }).join("");

  wrap.querySelectorAll(".fs-save-label").forEach(btn => {
    btn.onclick = async () => {
      const key = btn.dataset.key;
      const input = wrap.querySelector(`.fs-label[data-key="${key}"]`);
      const text = input.value.trim();
      if (!text) return;
      const r = await fetch("/api/admin/field-labels", {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ key, text }),
      });
      const data = await r.json().catch(() => ({}));
      const msgEl = wrap.querySelector(`.fs-label-msg[data-key="${key}"]`);
      if (!r.ok) { msgEl.style.color = "#e07a7a"; msgEl.textContent = data.error || "Chyba."; return; }
      productFieldLabels = data.labels;
      msgEl.style.color = "#7ec488";
      msgEl.textContent = "✓ Uloženo";
      setTimeout(() => { msgEl.textContent = ""; }, 2500);
    };
  });
  wrap.querySelectorAll(".fs-save-options").forEach(btn => {
    btn.onclick = async () => {
      const key = btn.dataset.key;
      const textarea = wrap.querySelector(`.fs-options[data-key="${key}"]`);
      const options = textarea.value.split("\n").map(s => s.trim()).filter(Boolean);
      const r = await fetch("/api/admin/field-options", {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ key, options }),
      });
      const data = await r.json().catch(() => ({}));
      const msgEl = wrap.querySelector(`.fs-options-msg[data-key="${key}"]`);
      if (!r.ok) { msgEl.style.color = "#e07a7a"; msgEl.textContent = data.error || "Chyba."; return; }
      productFieldOptions[key] = data.options;
      msgEl.style.color = "#7ec488";
      msgEl.textContent = options.length ? `✓ Uloženo (${data.options.length})` : "✓ Zrušeno (volný text)";
      setTimeout(() => { msgEl.textContent = ""; }, 2500);
    };
  });
}
async function renameProductFieldLabel(key) {
  const current = (productFieldLabels && productFieldLabels[key]) || key;
  const next = prompt("Nový název popisku:", current);
  if (next == null) return;
  const text = next.trim();
  if (!text || text === current) return;
  try {
    const r = await fetch("/api/admin/field-labels", {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ key, text }),
    });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) { alert(data.error || "Uložení se nezdařilo."); return; }
    productFieldLabels = data.labels;
    document.querySelectorAll(`.sc-label-edit[data-key="${key}"]`).forEach(el => {
      if (el.previousSibling) el.previousSibling.textContent = text;
    });
  } catch (e) {
    alert("Uložení se nezdařilo (chyba spojení).");
  }
}
document.addEventListener("click", (e) => {
  const el = e.target.closest(".sc-label-edit");
  if (el) renameProductFieldLabel(el.dataset.key);
});

// Cena za 1m profilu (Robert 2026-09-15 pres bot3: "vsechny kusovniky na
// vsech kartach... i cenu za 1m a pridat sloupec pred nim [Cena/ks]") -
// zpetne dopocitano z Cena/ks a delky rezu v `dim` ("1180 mm"), stejny
// princip jako u cen za m2 u desek jinde v souboru. Plati JEN pro radky,
// kde `dim` je proste "<cislo> mm" (jeden rozmer = delka rezu profilu) -
// nemetrazovane dily (zaslepky/spojky/produkty, dim="-") a plosne dily
// (MDF "169 × 1238 mm", dva rozmery) vraci null, sloupec necha pomlcku.
function scCenaZaMetrZDim(dim, unitPrice) {
  if (unitPrice == null) return null;
  const m = String(dim || "").trim().match(/^(\d+(?:[.,]\d+)?)\s*mm$/);
  if (!m) return null;
  const delkaM = parseFloat(m[1].replace(",", ".")) / 1000;
  return delkaM > 0 ? unitPrice / delkaM : null;
}

// Sekce "Kusovnik (ze sceny)" (#stockCardBomSection). Vytazeno ze
// openStockCardModal do samostatne funkce (bot16, 2026-09-11), aby ji mohl
// zavolat i ekvalizer pri prepnuti varianty - drive se vykreslila JEDNOU pri
// otevreni karty se zakladni sestavou a uz se nehnula, takze pri prepnuti na
// jine provedeni ukazovala kusovnik JINE sestavy, nez co bylo videt ve 3D
// (Robert pres bot8: "kusovnik potrebujeme", ale ma nasledovat posuvnik).
//
// `assembly` = polozka z /api/admin/product-assemblies/by-product/<id>
// (`assembly` nebo kterykoli prvek `assemblies[]`) - nese bom/price_summary/
// parts_count. Jsou to SNIMKY z okamziku ulozeni sestavy ve scene, ne zivy
// vypocet; zivy prepocet dela sc3dSpocitejKusovnik primo ve 3D nahledu.
function scRenderBomSection(assembly) {
  const bomBox = document.getElementById("stockCardBomSection");
  if (!bomBox) return;
  if (!assembly) { bomBox.style.display = "none"; bomBox.innerHTML = ""; return; }
  const ps = assembly.price_summary || {};
  const bomRows = assembly.bom || [];
  const priceRowHtml = (label, val, qty) => (val == null) ? "" : `<tr><td>${label}</td><td></td><td>${qty ?? ""}</td><td></td><td></td><td style="text-align:right;">${Math.round(val).toLocaleString("cs-CZ")} Kč</td></tr>`;

  // (1) CENA JE DOLNI ODHAD - nesmi se zamlcet (bot8, 2026-09-11).
  // U sestav, kde se nedochoval pocet spoju, je `joint_czk`=0 a chybejici
  // prace za spoje je odhadnuta v `joint_price_odhad_chybi_czk` (u sedmi
  // provedeni Dobla C 5 720 az 6 820 Kc na sestavu). Rekonstrukci poctu
  // spoju dela bot10; do te doby neni total_czk konecna cena.
  const chybiSpoje = !ps.joint_czk && (ps.joint_price_odhad_chybi_czk != null);
  const odhadChybi = ps.joint_price_odhad_chybi_czk;

  // (2) MDF NEMA weight_g, takze desky prispivaji 0 kg - proto muze mit
  // provedeni s dvema deskami navic STEJNOU hmotnost (bot8, 2026-09-11).
  const maDesky = bomRows.some(r => /MDF|deska/i.test(r.name || ""));

  bomBox.innerHTML = `
    <h4 class="sc-section-title">Kusovník (ze scény) — sestava „${escapeHtmlAdmin(assembly.name)}“, ${assembly.parts_count} dílů</h4>
    <table class="sc-mv-table">
      <thead><tr><th>Položka</th><th>Rozměr</th><th>Ks</th><th>Cena/m</th><th>Cena/ks</th><th>Celkem</th></tr></thead>
      <tbody>
        ${bomRows.map(row => { const zaM = scCenaZaMetrZDim(row.dim, row.unit_price); return `<tr><td>${escapeHtmlAdmin(row.name)}</td><td>${escapeHtmlAdmin(row.dim || "-")}</td><td>${row.qty}</td><td>${zaM != null ? Math.round(zaM).toLocaleString("cs-CZ") + " Kč" : "-"}</td><td>${row.unit_price != null ? Math.round(row.unit_price).toLocaleString("cs-CZ") + " Kč" : "-"}</td><td style="text-align:right;">${row.total != null ? Math.round(row.total).toLocaleString("cs-CZ") + " Kč" : "-"}</td></tr>`; }).join("")}
        ${priceRowHtml("Cena řezů", ps.cut_czk, null)}
        ${priceRowHtml("Manipulační tarif", ps.profile_flat_fee_czk, null)}
        ${priceRowHtml("Cena spojů", ps.joint_czk, ps.joint_count)}
        ${priceRowHtml("Příslušenství (spojovací materiál)", ps.accessory_czk, null)}
      </tbody>
    </table>
    <div style="display:flex;gap:18px;flex-wrap:wrap;margin-top:8px;font-size:12.5px;color:#c7ccd4;">
      <div>Hmotnost: <b>${ps.weight_kg != null ? ps.weight_kg.toLocaleString("cs-CZ") : "?"} kg</b>${maDesky ? ` <span style="color:var(--warn,#e0a070);" title="MDF desky nemají v katalogu vyplněnou hmotnost (weight_g), takže do součtu přispívají 0 kg. Dvě provedení lišící se jen počtem desek proto mohou mít stejnou hmotnost.">(bez desek)</span>` : ""}</div>
      <div>Náklad na materiál celkem: <b>${ps.material_czk != null ? Math.round(ps.material_czk).toLocaleString("cs-CZ") : "?"} Kč</b></div>
      <div style="font-size:13.5px;">Celkový náklad sestavy: <b>${ps.total_czk != null ? Math.round(ps.total_czk).toLocaleString("cs-CZ") : "?"} Kč</b>${chybiSpoje ? ` <span style="color:var(--warn,#e0a070);font-size:12.5px;">a víc</span>` : ""}</div>
    </div>
    ${chybiSpoje ? `<div style="font-size:12px;color:var(--warn,#e0a070);margin-top:6px;">
      ⚠ Cena je <b>dolní odhad</b> — u této sestavy se nedochoval počet spojů, takže práce za spoje není započítaná
      (odhadem chybí ${Math.round(odhadChybi).toLocaleString("cs-CZ")} Kč). Skutečný náklad bude vyšší.
    </div>` : ""}
    <div style="font-size:11px;color:#8b93a1;margin-top:6px;">Interní kalkulace nákladu ze scény (snímek z okamžiku uložení sestavy) - neovlivňuje prodejní cenu výše, ani se nikde nezobrazuje zákazníkům na e-shopu.</div>
  `;
  bomBox.style.display = "";
}

// Popisek pole s cenou. U desky ZALEZI na jednotce: PR10 a laminovaná mají
// cenu za celou tabuli, MDF za m² - a admin dřív u všech tří tvrdil
// "Cena za 1 m² (Kč)", i když to nebyla pravda. E-shop přitom nakupuje celé
// tabule, takže na tom rozdílu stojí výsledná cena (viz cena_desky()
// v api/products.py).
function scfPopisekCeny(sp) {
  if (sp && sp.is_board_material) {
    return sp.unit === "m2" ? "Cena za 1 m² (Kč)" : "Cena za celou tabuli (Kč)";
  }
  return (sp && sp.unit === "m") ? "Cena / m (Kč)" : "Cena / ks (Kč)";
}

// Adresa produktu na webu pod polem Nazev. Tvori se STROJOVE z aktualniho nazvu (api/product_slug.py); po prejmenovani se
// adresa zmeni a stara se sama presmeruje (301) - Robert 2026-10-01 ("aby se strojove vytvarely pekne URL adresy pro SEO,
// ale ne rucne botem"). Odkaz "Prepsat adresu z nazvu" ji prepocita u tohoto produktu, kdyz je rozjeta/chybi.
function scfSlugHintHtml(slug) {
  return slug
    ? `Adresa na webu: <code>${escapeHtmlAdmin(slug)}</code> — tvoří se sama z názvu: po přejmenování se změní a stará se přesměruje (301). `
      + `<a href="#" id="scfSlugRegen">Přepsat adresu z názvu</a>`
    : `Adresa na webu vznikne sama při uložení názvu nebo aktivaci produktu. <a href="#" id="scfSlugRegen">Vytvořit adresu z názvu</a>`;
}

// Co uvidi web a kosik u desky z ceny a jednotky - stejny vypocet jako cena_desky() v api/products.py (u unit
// "m2" je zadana cena za 1 m², jinak za celou tabuli). Vraci { plocha (m² tabule), za_tabuli, za_m2 }; co nejde
// spocitat (chybi rozmer tabule nebo cena), je null. Jen pro zobrazeni - ulozena zustava cena v zadane jednotce.
function scfPrepocetDesky(unit, cena, sirkaMm, vyskaMm) {
  const w = Number(sirkaMm), h = Number(vyskaMm);
  const plocha = (w > 0 && h > 0) ? (w / 1000) * (h / 1000) : null;
  const r2 = (x) => Math.round(x * 100) / 100;
  if (!Number.isFinite(cena)) return { plocha, za_tabuli: null, za_m2: null };
  if (unit === "m2") return { plocha, za_m2: cena, za_tabuli: plocha ? r2(cena * plocha) : null };
  return { plocha, za_tabuli: cena, za_m2: plocha ? r2(cena / plocha) : null };
}
const scfKc = (n) => new Intl.NumberFormat("cs-CZ", { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(n) + " Kč";
function scfPrepocetHtml(unit, cena, sirkaMm, vyskaMm) {
  if (!Number.isFinite(cena)) return "";
  const p = scfPrepocetDesky(unit, cena, sirkaMm, vyskaMm);
  if (!p.plocha) {
    return `⚠ Chybí rozměr tabule (Doplňkové údaje → Formát tabule), cenu nejde přepočítat${unit === "m2" ? " - košík by pak použil cenu za m² jako cenu celé tabule" : " na m²"}.`;
  }
  const tab = `${sirkaMm}×${vyskaMm} mm`;
  const m2 = `${p.plocha.toLocaleString("cs-CZ", { maximumFractionDigits: 3 })} m²`;
  return unit === "m2"
    ? `Web a košík: <b>${scfKc(p.za_m2)} / m²</b> · celá tabule ${tab} (${m2}) = <b>${scfKc(p.za_tabuli)}</b>`
    : `Web a košík: celá tabule ${tab} (${m2}) = <b>${scfKc(p.za_tabuli)}</b> · <b>${scfKc(p.za_m2)} / m²</b>`;
}

// ---------------------------------------------------------------------------
// Zalozka "Varianty" - vsechna provedeni sestavy POD SEBOU (Robert 2026-09-11
// pres bot8, na otazku "nova zalozka, nebo dodelat 3D?" odpovedel "obojí").
// Rozdil proti posuvniku ve 3D modelu: tam se provedeni PREPINAJI (vidis vzdy
// jedno), tady jsou VEDLE SEBE a daji se porovnat bez preklikavani.
// ---------------------------------------------------------------------------
let scVariantyBuiltFor = null;   // pole variant, pro ktere uz je panel postaveny

// Nahledy: JEDEN sdileny WebGL renderer, ktery kresli varianty SEKVENCNE a
// vysledek vzdy odlozi do <img> pres toDataURL. Zamerne ne sedm zivych
// canvasu - prohlizec ma tvrdy strop na pocet soucasnych WebGL kontextu
// (bezne 8-16) a pri vic kartach/zalozkach by nejstarsi kontexty tise
// umiraly. Tady zije kontext jen po dobu generovani a pak se uvolni.
// (Overeno 2026-09-11, ze se nahledy nedaji vzit z hotovych renderu:
// product_turntable_frames je uplne prazdna a produkt nema zadny obrazek.)
async function scVygenerujNahledyVariant(varianty, sirka, vyska) {
  await scEnsureThreeJs();
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, preserveDrawingBuffer: true });
  renderer.setPixelRatio(1);
  renderer.setSize(sirka, vyska);
  const loader = new THREE.GLTFLoader();
  const gltfCache = {};
  const katalogMap = await scFetchKatalogMap();

  async function nactiGlb(partId) {
    if (gltfCache[partId] !== undefined) return gltfCache[partId];
    const cat = katalogMap.get(String(partId));
    if (!cat || !cat.file) { gltfCache[partId] = null; return null; }
    try {
      const gltf = await new Promise((res, rej) => loader.load(`/katalog/${cat.file}`, res, undefined, rej));
      gltfCache[partId] = gltf.scene;
    } catch (e) { gltfCache[partId] = null; }
    return gltfCache[partId];
  }

  const vysledky = new Map();
  try {
    for (const v of varianty) {
      let parts = scVariantPartsCache.get(v.id);
      if (!parts) {
        try {
          const r = await fetch(`/api/product-assemblies/lookup?assembly=${v.id}`);
          const d = await r.json().catch(() => null);
          parts = (d && d.assembly && d.assembly.parts) || null;
          if (parts) scVariantPartsCache.set(v.id, parts);
        } catch (e) { parts = null; }
      }
      if (!parts) { vysledky.set(v.id, null); continue; }

      // Karoserie do produktoveho nahledu nepatri - stejne pravidlo jako
      // ve 3D nahledu (WORKFLOW.md bod 25, sestava se neprodava s karoserii).
      const dily = parts.filter(p => !sc3dJeKaroserie(p));
      await Promise.all([...new Set(dily.map(p => p.part_id))].map(nactiGlb));

      const scene = new THREE.Scene();
      scene.background = new THREE.Color(0x20272b);
      scene.add(new THREE.HemisphereLight(0xf3ede2, 0x2a2f26, 1.05));
      const d1 = new THREE.DirectionalLight(0xffffff, 0.85); d1.position.set(600, 1400, 900); scene.add(d1);
      const d2 = new THREE.DirectionalLight(0xbcd0ff, 0.35); d2.position.set(-800, 600, -700); scene.add(d2);
      const group = new THREE.Group(); scene.add(group);
      dily.forEach(p => {
        const tpl = gltfCache[p.part_id];
        if (!tpl) return;
        const mesh = tpl.clone(true);
        mesh.traverse(n => { if (n.isMesh) n.material = sc3dMaterialProDil(p); });
        mesh.position.set(...p.position);
        mesh.quaternion.set(...p.quaternion);
        mesh.scale.set(...p.scale);
        group.add(mesh);
      });
      group.updateMatrixWorld(true);

      const box = new THREE.Box3(); let maBox = false;
      group.traverse(n => { if (n.isMesh) { if (!maBox) { box.setFromObject(n); maBox = true; } else box.expandByObject(n); } });
      const camera = new THREE.PerspectiveCamera(38, sirka / vyska, 10, 20000);
      if (maBox) {
        const size = box.getSize(new THREE.Vector3()), center = box.getCenter(new THREE.Vector3());
        const maxDim = Math.max(size.x, size.y, size.z), dist = maxDim * 1.7 + 400;
        // Stejny izometricky pohled jako vychozi ve 3D nahledu (az 35/22),
        // aby sla provedeni porovnavat mezi sebou i proti 3D zalozce.
        const az = THREE.MathUtils.degToRad(35), el = THREE.MathUtils.degToRad(22);
        camera.position.set(
          center.x + dist * Math.cos(el) * Math.sin(az),
          center.y + dist * Math.sin(el),
          center.z + dist * Math.cos(el) * Math.cos(az));
        camera.lookAt(center);
        camera.near = Math.max(1, maxDim / 200); camera.far = dist * 8;
        camera.updateProjectionMatrix();
      }
      renderer.render(scene, camera);
      try { vysledky.set(v.id, renderer.domElement.toDataURL("image/png")); }
      catch (e) { vysledky.set(v.id, null); }
    }
  } finally {
    // Kontext uvolnit VZDY, i kdyz nektera varianta selze - jinak by po
    // par otevrenich karty dosly WebGL kontexty.
    renderer.dispose();
    if (renderer.forceContextLoss) { try { renderer.forceContextLoss(); } catch (e) {} }
  }
  return vysledky;
}

async function scRenderVariantyPanel() {
  const box = document.getElementById("stockCardVariantyPanel");
  if (!box) return;
  const varianty = Array.isArray(scCurrent3dVariants) ? scCurrent3dVariants : [];
  if (scVariantyBuiltFor === varianty) return;   // uz postaveno pro tahle data
  scVariantyBuiltFor = varianty;

  if (!varianty.length) {
    box.innerHTML = `<div style="font-size:12.5px;color:var(--text-muted);">K tomuto produktu není uložená žádná produktová sestava.</div>`;
    return;
  }

  const czk = v => (v == null ? "?" : Math.round(v).toLocaleString("cs-CZ"));
  box.innerHTML = `
    <h4 class="sc-section-title">Varianty sestavy (${varianty.length}) — provedení vedle sebe</h4>
    <div style="font-size:12px;color:var(--text-muted);margin-bottom:12px;">
      Náhledy se vykreslují postupně, chvíli to trvá. Přepínat mezi provedeními a otáčet modelem jde v záložce „3D model“.
    </div>
    <div id="scVariantyList" style="display:flex;flex-direction:column;gap:14px;"></div>`;
  const list = box.querySelector("#scVariantyList");

  // Nejlevnejsi varianta - kvuli zvyrazneni rozdilu proti ni.
  const ceny = varianty.map(v => (v.price_summary || {}).total_czk).filter(x => x != null);
  const nejlevnejsi = ceny.length ? Math.min(...ceny) : null;

  varianty.forEach((v, i) => {
    const ps = v.price_summary || {};
    const p = sc3dVariantaPopisky(v.name);
    const jeZakladni = i === 0;
    const chybiSpoje = !ps.joint_czk && (ps.joint_price_odhad_chybi_czk != null);
    const rozdil = (nejlevnejsi != null && ps.total_czk != null) ? Math.round(ps.total_czk - nejlevnejsi) : null;
    const el = document.createElement("div");
    el.style.cssText = "display:grid;grid-template-columns:220px minmax(0,1fr);gap:14px;border:1px solid var(--border-soft);border-radius:8px;padding:12px;background:var(--panel-bg-alt);";
    el.innerHTML = `
      <div>
        <div class="scVariantaNahled" data-id="${v.id}" style="width:220px;height:150px;border-radius:6px;background:#20272b;display:flex;align-items:center;justify-content:center;color:var(--text-muted);font-size:11.5px;">náhled se generuje…</div>
      </div>
      <div style="min-width:0;">
        <div style="display:flex;gap:8px;align-items:baseline;flex-wrap:wrap;">
          <b style="font-size:14px;">${escapeHtmlAdmin(p.titulek)}</b>
          ${jeZakladni ? `<span style="font-size:11px;color:var(--accent);border:1px solid var(--accent);border-radius:10px;padding:1px 7px;">základní</span>` : ""}
          <span style="font-size:12.5px;color:var(--text-muted);">${escapeHtmlAdmin(p.popis || "")}</span>
        </div>
        <div style="font-size:12px;color:var(--text-muted);margin-top:3px;">${escapeHtmlAdmin(v.name)}</div>
        <div style="display:flex;gap:18px;flex-wrap:wrap;margin-top:8px;font-size:12.5px;">
          <div>Dílů: <b>${v.parts_count}</b></div>
          <div>Položek kusovníku: <b>${(v.bom || []).length}</b></div>
          <div>Hmotnost: <b>${ps.weight_kg != null ? ps.weight_kg.toLocaleString("cs-CZ") : "?"} kg</b></div>
          <div>Materiál: <b>${czk(ps.material_czk)} Kč</b></div>
          <div style="font-size:13.5px;">Celkem: <b>${czk(ps.total_czk)} Kč</b>${chybiSpoje ? `<span style="color:var(--warn,#e0a070);font-size:12px;"> a víc</span>` : ""}</div>
          ${rozdil != null && rozdil > 0 ? `<div style="color:var(--text-muted);">(+${czk(rozdil)} Kč proti nejlevnější)</div>` : ""}
        </div>
        ${chybiSpoje ? `<div style="font-size:11.5px;color:var(--warn,#e0a070);margin-top:6px;">⚠ Dolní odhad — práce za spoje není započítaná (chybí přibližně ${czk(ps.joint_price_odhad_chybi_czk)} Kč).</div>` : ""}
        <details style="margin-top:8px;">
          <summary style="cursor:pointer;font-size:12.5px;color:var(--accent);">Kusovník (${(v.bom || []).length} položek)</summary>
          <table class="sc-mv-table" style="margin-top:6px;">
            <thead><tr><th>Položka</th><th>Rozměr</th><th>Ks</th><th>Cena/m</th><th>Cena/ks</th><th>Celkem</th></tr></thead>
            <tbody>${(v.bom || []).map(row => { const zaM = scCenaZaMetrZDim(row.dim, row.unit_price); return `<tr><td>${escapeHtmlAdmin(row.name)}</td><td>${escapeHtmlAdmin(row.dim || "-")}</td><td>${row.qty}</td><td>${zaM != null ? czk(zaM) + " Kč" : "-"}</td><td>${row.unit_price != null ? czk(row.unit_price) + " Kč" : "-"}</td><td style="text-align:right;">${row.total != null ? czk(row.total) + " Kč" : "-"}</td></tr>`; }).join("")}</tbody>
          </table>
        </details>
      </div>`;
    list.appendChild(el);
  });

  // Nahledy az po vykresleni textu - tabulky maji byt videt hned, obrazky
  // doteci postupne.
  let nahledy;
  try {
    nahledy = await scVygenerujNahledyVariant(varianty, 220, 150);
  } catch (e) {
    console.warn("skladova karta: nahledy variant se nepodarilo vygenerovat", e);
    return;
  }
  box.querySelectorAll(".scVariantaNahled").forEach(elm => {
    const url = nahledy.get(parseInt(elm.dataset.id, 10));
    if (url) elm.innerHTML = `<img src="${url}" alt="" style="width:100%;height:100%;object-fit:contain;border-radius:6px;">`;
    else elm.textContent = "náhled se nepodařilo vykreslit";
  });
}

async function openStockCardModal(product) {
  await ensureProductFieldLabels();
  scSwitchTab("obrazky");
  document.getElementById("stockCardTitle").textContent = `Skladová karta — ${product.name}`;
  const idHost = document.getElementById("stockCardIdHost"); idHost.textContent = ""; idHost.appendChild(makeCardIdChip(product.id));
  document.getElementById("stockCardViewShopLink").href = `/product.html?id=${product.id}`;
  document.getElementById("stockCardDuplicateBtn").onclick = () => duplicateShopProduct(product.id, product.name);
  document.getElementById("stockCardCurrent").textContent = "Načítám…";
  document.getElementById("stockCardHeaderGrid").innerHTML = "";
  document.getElementById("stockCardTbody").innerHTML = "";
  document.getElementById("stockCardFooter").innerHTML = "";
  document.getElementById("stockCardShoptet").style.display = "none";
  document.getElementById("stockCardShoptet").innerHTML = "";
  document.getElementById("stockCardPricing").style.display = "none";
  document.getElementById("stockCardPricing").innerHTML = "";
  document.getElementById("stockCardHoverWindow").style.display = "none";
  document.getElementById("stockCardHoverWindow").innerHTML = "";
  document.getElementById("stockCardSeo").style.display = "none";
  document.getElementById("stockCardSeo").innerHTML = "";
  document.getElementById("stockCardRelated").style.display = "none";
  document.getElementById("stockCardRelated").innerHTML = "";
  document.getElementById("stockCardImagesSection").style.display = "none";
  document.getElementById("stockCardImages").innerHTML = "";
  document.getElementById("stockCardModal").classList.add("open");
  const r = await fetch(`/api/shop/stock/movements?product_id=${product.id}`);
  const data = await r.json();
  if (!r.ok) {
    document.getElementById("stockCardCurrent").textContent = data.error || "Nepodařilo se načíst.";
    return;
  }
  document.getElementById("stockCardCurrent").textContent = "";

  // Rozšířená hlavička karty (Robert 2026-07-26: "rozšiř skladové karty
  // položek") - vsechny hodnoty uz mame v `product` (predano z tabulky
  // produktu, viz renderShopProducts) nebo dopocitatelne, zadna zmena
  // backendu nebyla potreba.
  const stockQty = data.product.stock_qty ?? 0;
  const minStock = product.min_stock;
  const maxStock = product.max_stock;
  const underMin = minStock != null && stockQty < minStock;
  const unitPrice = product.price_czk_placeholder;
  const stockValue = unitPrice != null ? Math.round(unitPrice * stockQty * 100) / 100 : null;
  const catName = (typeof shopCatNameById === "function") ? shopCatNameById(product.category_id) : "";

  // Robert 2026-07-26: "já se ptám na všechny ty instance ze screenu kde
  // se editují... a mělo by to být uvnitř karet" - vsechna pole zobrazena
  // ve skladove karte jsou ted editovatelna PRIMO ZDE (input/select misto
  // statickeho textu), ne jen min/max v tabulce produktu. Kazde pole se
  // uklada samostatne (onchange -> PUT), stejny vzor jako inline editace
  // v tabulce produktu.
  // POZOR (Robert 2026-09-30, laminodeska 3671: v DB m2, admin ukazoval "za celou tabuli"): `data.product` z
  // /api/shop/stock/movements NEOBSAHUJE `unit` (ani cenu, kategorii, aktivni, archivovano) - ty drzi radek
  // seznamu (`product`). Bez doplneni z nej karta u KAZDE desky tvrdila "za celou tabuli" (radio uz bylo
  // vybrane, takze klik na nej nespustil change a "nejde prepnout") a u zbozi na metry "Cena / ks". Hodnoty z
  // `data.product` (cerstve z DB) maji prednost, co v nem chybi, se bere z radku seznamu.
  const sp = Object.assign({}, product, data.product);
  const catOptionsHtml = (typeof shopCatFlatOptions !== "undefined" ? shopCatFlatOptions : [])
    .map(o => `<option value="${o.id}" ${o.id === product.category_id ? "selected" : ""}>${escapeHtmlAdmin(o.label)}</option>`).join("");

  document.getElementById("stockCardHeaderGrid").innerHTML = `
    <div class="sc-stat sc-span-full">
      <div class="sc-stat-label">Název produktu</div>
      <input id="scfName" type="text" maxlength="200" value="${escapeHtmlAdmin(sp.name || "")}" style="width:100%;">
      <div id="scfSlugHint" style="font-size:11px;color:var(--text-muted);margin-top:4px;">${scfSlugHintHtml(sp.slug)}</div>
    </div>
    <div class="sc-stat${underMin ? " warn" : ""}">
      <div class="sc-stat-label">Aktuální stav</div>
      <div class="sc-stat-value" id="scfStockNow">${stockQty} ${escapeHtmlAdmin(sp.unit)}</div>
    </div>
    <div class="sc-stat">
      <div class="sc-stat-label">SKU</div>
      <input id="scfSku" type="text" value="${escapeHtmlAdmin(sp.sku || "")}" style="width:100%;">
    </div>
    <div class="sc-stat">
      <div class="sc-stat-label">Kategorie</div>
      <select id="scfCategory" style="width:100%;"><option value="">(bez kategorie)</option>${catOptionsHtml}</select>
    </div>
    <div class="sc-stat${underMin ? " warn" : ""}">
      <div class="sc-stat-label">Min / Max sklad</div>
      <div style="display:flex;gap:4px;align-items:center;">
        <input id="scfMin" type="number" min="0" placeholder="min" value="${minStock ?? ""}" style="width:50%;">
        <input id="scfMax" type="number" min="0" placeholder="max" value="${maxStock ?? ""}" style="width:50%;">
      </div>
    </div>
    <div class="sc-stat" id="scfPriceLabelWrap">
      <div class="sc-stat-label" id="scfPriceLabel">${scfPopisekCeny(sp)}</div>
      <input id="scfPrice" type="number" step="0.01" min="0" value="${unitPrice ?? ""}" style="width:100%;">
    </div>
    <div class="sc-stat">
      <div class="sc-stat-label">Hodnota skladu</div>
      <div class="sc-stat-value">${stockValue != null ? stockValue.toLocaleString("cs-CZ") + " Kč" : "–"}</div>
    </div>
    <div class="sc-stat sc-span-full" id="scfPriceConvWrap" style="display:none;border-left:3px solid var(--accent);">
      <div id="scfPriceConv" style="font-size:12.5px;color:var(--text);line-height:1.5;"></div>
    </div>
    ${!sp.is_profile_material ? `
    <div class="sc-stat sc-span-full" id="scfSoldByMeterWrap"${sp.is_board_material ? ' style="display:none;"' : ""}>
      <label style="display:flex;align-items:center;gap:6px;cursor:pointer;">
        <input id="scfSoldByMeter" type="checkbox" ${sp.unit === "m" ? "checked" : ""}>
        <span>Prodává se na metry — cena/sklad se pak zobrazují za 1 m, ne za 1 ks (jiné položky než profily, které se ale běžně prodávají na běžné metry)</span>
      </label>
    </div>` : ""}
    <div class="sc-stat sc-span-full">
      <label style="display:flex;align-items:center;gap:6px;cursor:pointer;">
        <input id="scfBoardMaterial" type="checkbox" ${sp.is_board_material ? "checked" : ""}>
        <span>Deskový materiál — prodává se po celých tabulích, cena se zadává za 1 m², přířezy se řežou z tabule${sp.glb_file ? "; ve 3D scéně jde deska protahovat na libovolný rozměr, tloušťka zůstává pevná" : ""}</span>
      </label>
    </div>
    <div class="sc-stat sc-span-full" id="scfBoardUnitWrap"${sp.is_board_material ? "" : ' style="display:none;"'}>
      <div class="sc-stat-label">Cena desky</div>
      <div id="scfBoardM2Info" style="font-size:12.5px;line-height:1.5;">
        Cena desky se zadává <b>vždy za 1 m²</b> (jednotně u všech desek). Cena celé tabule se dopočítá z formátu tabule
        a ukazuje ji řádek „Web a košík" nad tímto blokem.
      </div>
      <div id="scfBoardLegacy" style="display:none;font-size:12.5px;line-height:1.5;">
        <b style="color:var(--error);">Cena této desky je uložená za celou tabuli, ne za 1 m².</b>
        Ceny desek se sjednocují na 1 m² - převeď ji jedním kliknutím (cena i jednotka se změní najednou).
        <div style="margin-top:6px;"><button id="scfBoardToM2Btn" type="button">Převést na cenu za 1 m²</button></div>
      </div>
    </div>
    <div class="sc-stat sc-span-full" id="scfBoardSheetWrap"${sp.is_board_material ? "" : ' style="display:none;"'}>
      <div class="sc-stat-label">Formát tabule, ze které se řeže (mm) — deskové materiály se dodávají v různých formátech; z rozměru se počítá cena za m² i za celou tabuli</div>
      <div style="display:flex;gap:8px;align-items:center;">
        <input id="scfBoardSheetWidth" type="number" min="0" step="1" placeholder="šířka" value="${sp.board_sheet_width_mm ?? ""}" style="width:50%;">
        <span>×</span>
        <input id="scfBoardSheetHeight" type="number" min="0" step="1" placeholder="výška" value="${sp.board_sheet_height_mm ?? ""}" style="width:50%;">
      </div>
    </div>
    <div class="sc-stat${product.is_archived || !product.active ? " warn" : ""}">
      <div class="sc-stat-label">Stav</div>
      <div class="sc-stat-value" style="display:flex;align-items:center;gap:6px;">
        <label style="display:flex;align-items:center;gap:4px;font-weight:400;font-size:12.5px;">
          <input id="scfActive" type="checkbox" ${product.active ? "checked" : ""} style="width:auto;"> aktivní
        </label>
        ${product.is_archived ? '<span class="badge-archived">archivováno</span>' : ""}
      </div>
    </div>
  `;

  const scSaveFlash = (...ids) => ids.forEach(id => {
    const el = document.getElementById(id);
    if (!el) return;
    el.style.borderColor = "#7ed49a";
    setTimeout(() => { el.style.borderColor = ""; }, 900);
  });
  // Vraci true/false podle toho, jestli server zmenu prijal. Driv se odpoved zahazovala, takze pri chybe (403
  // bez opravneni, 500, vyprsela session) karta vypadala jako ulozena a zmena tise zmizela.
  let scLastPut = {};   // posledni odpoved serveru (napr. nova adresa `slug` po prejmenovani nebo aktivaci)
  const scPutProduct = async (body) => {
    const r = await fetch(`/api/shop/products/${product.id}`, {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const d = await r.json().catch(() => ({}));
    scLastPut = d || {};
    if (!r.ok) alert((d && d.error) || `Uložení se nezdařilo (${r.status}).`);
    return r.ok;
  };
  // Adresa produktu (slug) se tvori STROJOVE na serveru (api/product_slug.py): po prejmenovani nebo aktivaci produktu
  // bez adresy ji server vrati v odpovedi a starou presmeruje (301). Karta ji jen ukazuje.
  const scfSlugAktualizuj = () => {
    if (scLastPut && scLastPut.slug) { sp.slug = scLastPut.slug; product.slug = scLastPut.slug; }
    const el = document.getElementById("scfSlugHint");
    if (!el) return;
    el.innerHTML = scfSlugHintHtml(sp.slug);
    const a = document.getElementById("scfSlugRegen");
    if (a) a.onclick = async (ev) => {
      ev.preventDefault();
      const vysl = await normalizeProductSlugs([product.id]);
      if (vysl && vysl.changes && vysl.changes[0]) { sp.slug = vysl.changes[0].new; product.slug = vysl.changes[0].new; scfSlugAktualizuj(); }
    };
  };

  // --- Deska: prepocet ceny a cast karty, ktera zavisi na tom, jestli je produkt deska -------------------------
  // Prepocet ceny pod polem ceny: co uvidi web a kosik. Cte ZIVE hodnoty z poli (cena, rozmer tabule), takze se
  // prepocitava uz pri psani. U ne-desky je radek prazdny.
  const scfPrepocet = () => {
    const el = document.getElementById("scfPriceConv");
    if (!el) return;
    let html = "";
    if (sp.is_board_material) {
      const v = document.getElementById("scfPrice").value;
      const w = document.getElementById("scfBoardSheetWidth"), h = document.getElementById("scfBoardSheetHeight");
      html = scfPrepocetHtml(sp.unit === "m2" ? "m2" : "ks", v === "" ? NaN : parseFloat(v),
        w ? parseInt(w.value, 10) : sp.board_sheet_width_mm, h ? parseInt(h.value, 10) : sp.board_sheet_height_mm);
    }
    el.innerHTML = html;
    document.getElementById("scfPriceConvWrap").style.display = html ? "" : "none";
  };
  // Po zmene "je deska" / jednotky: popisek ceny, viditelnost bloku desky (jednotka, rozmer tabule, material pro
  // rezny plan), zatrzitko "na metry" (deska je jen m²/tabule) a prepocet.
  const scfObnovDesku = () => {
    const board = !!sp.is_board_material;
    const ukaz = (id, zap) => { const e = document.getElementById(id); if (e) e.style.display = zap ? "" : "none"; };
    ukaz("scfBoardUnitWrap", board); ukaz("scfBoardSheetWrap", board); ukaz("scfCuttingKeyWrap", board);
    ukaz("scfBoardM2Info", board && sp.unit === "m2");        // sjednocena cena za 1 m²
    ukaz("scfBoardLegacy", board && sp.unit !== "m2");        // starsi deska s cenou za celou tabuli -> nabidka prevodu
    ukaz("scfSoldByMeterWrap", !board);
    const popisek = document.getElementById("scfPriceLabel");
    if (popisek) popisek.textContent = scfPopisekCeny(sp);
    const sklad = document.getElementById("scfStockNow");     // jednotka u skladu musi drzet krok s jednotkou v DB
    if (sklad) sklad.textContent = `${stockQty} ${sp.unit}`;
    scfPrepocet();
  };
  document.getElementById("scfPrice").addEventListener("input", scfPrepocet);

  // Nazev produktu (Robert pres bot3, 2026-09-30: "produktum nejde upravit nazev"): backend `name` v PUT prijimal
  // od zacatku, v karte ale chybelo pole. Adresa (slug) SLEDUJE nazev: server ji pri prejmenovani vytvori znovu a starou
  // presmeruje (301) - api/product_slug.py (Robert 2026-10-01); nova adresa prijde v odpovedi.
  document.getElementById("scfName").onchange = async (e) => {
    const v = e.target.value.trim();
    if (!v) { alert("Název produktu nesmí být prázdný."); e.target.value = sp.name || ""; return; }
    if (v === sp.name) { e.target.value = v; return; }
    if (!(await scPutProduct({ name: v }))) { e.target.value = sp.name || ""; return; }
    e.target.value = v;
    sp.name = v; product.name = v;
    scfSlugAktualizuj();
    document.getElementById("stockCardTitle").textContent = `Skladová karta — ${v}`;
    scSaveFlash("scfName");
    if (typeof loadShopProducts === "function") loadShopProducts();
  };
  document.getElementById("scfSku").onchange = async (e) => {
    await scPutProduct({ sku: e.target.value.trim() });
    scSaveFlash("scfSku");
  };
  document.getElementById("scfCategory").onchange = async (e) => {
    await scPutProduct({ category_id: e.target.value ? parseInt(e.target.value, 10) : null });
    if (typeof loadShopProducts === "function") loadShopProducts();
  };
  const scSaveMinMax = async () => {
    const minV = document.getElementById("scfMin").value;
    const maxV = document.getElementById("scfMax").value;
    await scPutProduct({
      min_stock: minV === "" ? null : parseInt(minV, 10),
      max_stock: maxV === "" ? null : parseInt(maxV, 10),
    });
    scSaveFlash("scfMin", "scfMax");
    if (typeof loadShopProducts === "function") loadShopProducts();
  };
  document.getElementById("scfMin").onchange = scSaveMinMax;
  document.getElementById("scfMax").onchange = scSaveMinMax;
  document.getElementById("scfPrice").onchange = async (e) => {
    const v = e.target.value;
    await scPutProduct({ price_czk_placeholder: v === "" ? null : parseFloat(v) });
    scSaveFlash("scfPrice");
    if (typeof loadShopProducts === "function") loadShopProducts();
  };
  document.getElementById("scfActive").onchange = async (e) => {
    await scPutProduct({ active: e.target.checked });
    scfSlugAktualizuj();                       // aktivace produktu bez adresy ji na serveru vytvori
    if (typeof loadShopProducts === "function") loadShopProducts();
  };
  // Robert 2026-08-10 ("některé položky mimo profily prodáváme na
  // metry... cena je za 1m nikoli 1 ks") - zatrzitko jen preklada
  // shop_products.unit mezi "ks"/"m" (uz existujici obecne pole,
  // vsechny stranky - product.html/category.html/index.html - uz
  // vypisuji cenu jako "Kč / ${p.unit}" primo, takze zadna dalsi
  // zmena frontendu jinde neni potreba).
  const soldByMeterCb = document.getElementById("scfSoldByMeter");
  if (soldByMeterCb) {
    soldByMeterCb.onchange = async (e) => {
      const unit = e.target.checked ? "m" : "ks";
      if (!(await scPutProduct({ unit }))) { e.target.checked = !e.target.checked; return; }
      sp.unit = unit; product.unit = unit;
      document.getElementById("scfPriceLabel").textContent = unit === "m" ? "Cena / m (Kč)" : "Cena / ks (Kč)";
      scSaveFlash("scfPriceLabelWrap");
      if (typeof loadShopProducts === "function") loadShopProducts();
    };
  }

  // CENA DESKY JE VZDY ZA 1 m² (Robert 2026-08-07: "u deskovych materialu se cena zadava za 1m2"; znovu 2026-10-01:
  // "musi se sjednotit pouzivani za 1m2"). Dosud mohla mit deska jednotku "ks" (cena za celou tabuli) nebo "m2" a
  // karta nabizela prepinac; prepnuti ale zadane cislo neprepocitalo, jen menilo jeho vyznam, a presne tak vznikla
  // chyba u laminodesky 3671 (5 000 Kc za tabuli se cetlo jako 5 000 Kc za m² a tabule vysla na 28 980 Kc). Prepinac
  // je pryc. Starsi desku s cenou za tabuli (unit "ks") karta nabidne PREVEST: cena i jednotka se zmeni v JEDNOM
  // zapisu, takze neexistuje mezistav s chybnou cenou.
  const toM2Btn = document.getElementById("scfBoardToM2Btn");
  if (toM2Btn) toM2Btn.onclick = async () => {
    const cenaTxt = document.getElementById("scfPrice").value;
    const cena = cenaTxt === "" ? NaN : parseFloat(cenaTxt);
    const w = parseInt(document.getElementById("scfBoardSheetWidth").value, 10);
    const h = parseInt(document.getElementById("scfBoardSheetHeight").value, 10);
    if (!Number.isFinite(cena) || cena <= 0) { alert("Nejdřív vyplň cenu celé tabule."); return; }
    const p = scfPrepocetDesky("ks", cena, w, h);
    if (p.za_m2 == null) { alert("Nejdřív vyplň formát tabule (šířka × výška) - bez něj se cena za 1 m² nedá spočítat."); return; }
    const zpet = scfPrepocetDesky("m2", p.za_m2, w, h);          // co vyjde po zaokrouhleni na haliere
    if (!confirm(`Převést cenu desky na 1 m²?\n\nDosavadní cena celé tabule (${w}×${h} mm): ${scfKc(cena)}\n`
      + `Nová cena za 1 m²: ${scfKc(p.za_m2)}\nCelá tabule pak vyjde na ${scfKc(zpet.za_tabuli)} (zaokrouhleno na haléře).\n\n`
      + "Cenu za 1 m² můžeš po převodu upravit.")) return;
    if (!(await scPutProduct({ unit: "m2", price_czk_placeholder: p.za_m2 }))) return;
    sp.unit = "m2"; product.unit = "m2"; sp.price_czk_placeholder = p.za_m2; product.price_czk_placeholder = p.za_m2;
    document.getElementById("scfPrice").value = p.za_m2;
    scfObnovDesku();
    scSaveFlash("scfPriceLabelWrap");
    if (typeof loadShopProducts === "function") loadShopProducts();
  };

  // Doplnkove udaje (puvodne jen Shoptet import, task #68 - ted
  // editovatelne, takze je smysluplne zobrazit VZDY, ne jen kdyz uz neco
  // maji vyplnene, aby slo prazdne pole rovnou doplnit).
  const codesToText = (arr) => Array.isArray(arr) ? arr.join(", ") : "";
  const shoptetBox = document.getElementById("stockCardShoptet");
  shoptetBox.style.display = "";
  shoptetBox.innerHTML = `<h4 class="sc-section-title">Doplňkové údaje</h4>
    <div class="sc-header-grid">
      <div class="sc-stat">${scFieldLabel("manufacturer")}${scFieldInput("manufacturer", "scfManufacturer", sp.manufacturer)}</div>
      <div class="sc-stat">${scFieldLabel("supplier_name")}<input id="scfSupplier" type="text" list="supplierNameList" value="${escapeHtmlAdmin(sp.supplier_name || "")}" style="width:100%;"><datalist id="supplierNameList">${(typeof suppliersCache !== "undefined" ? suppliersCache : []).map(s => `<option value="${escapeHtmlAdmin(s.name)}">`).join("")}</datalist></div>
      <div class="sc-stat">${scFieldLabel("ean")}${scFieldInput("ean", "scfEan", sp.ean)}</div>
      <div class="sc-stat">${scFieldLabel("warranty")}${scFieldInput("warranty", "scfWarranty", sp.warranty)}</div>
      <div class="sc-stat sc-span-full">${scFieldLabel("category_path")}<input id="scfCategoryPath" type="text" list="shopCatPathList" value="${escapeHtmlAdmin(sp.category_path || "")}" style="width:100%;"><datalist id="shopCatPathList"></datalist></div>
      <div class="sc-stat">${scFieldLabel("availability_text")}${scFieldInput("availability_text", "scfAvailability", sp.availability_text)}</div>
      ${sp.has_variants ? `<div class="sc-stat"><div class="sc-stat-label">Varianty</div><div class="sc-stat-value">ano (${sp.variant_count})</div></div>` : ""}
      ${sp.glb_file ? `
      <div class="sc-stat sc-span-full">
        <div class="sc-stat-label">Barva ve 3D scéně — díl se do scény vloží rovnou v této barvě (místo výchozí podle vrstvy)</div>
        <div style="display:flex;gap:8px;align-items:center;">
          <input id="scfSceneColor" type="color" value="${sp.color_hex || "#9aa0a6"}" style="width:44px;height:30px;padding:2px;cursor:pointer;">
          <button id="scfSceneColorClear" type="button" style="flex:0 0 auto;">Zrušit (výchozí barva)</button>
        </div>
      </div>` : ""}
      <div class="sc-stat sc-span-full" id="scfCuttingKeyWrap"${sp.is_board_material ? "" : ' style="display:none;"'}>
        <div class="sc-stat-label">Materiál pro řezný plán — Robert 2026-08-08: "napoj reálně funkčně na řezné plány". Musí přesně odpovídat material_key v Nastavení → Řezné plány → Sklad materiálu (např. "preklizka_10"), jinak se objednávky s přířezy této desky do řezného plánu nedostanou.</div>
        <input id="scfCuttingMaterialKey" type="text" placeholder="např. preklizka_10" value="${escapeHtmlAdmin(sp.cutting_material_key || "")}" style="width:100%;">
      </div>
      <div class="sc-stat sc-span-full" style="border-top:1px solid #3a3f4a;padding-top:12px;margin-top:4px;">
        <div class="sc-stat-label">Hmotnost (kg) — Robert 2026-08-31: "u všech produktů přidat hmotnost". Hmotnost
          CELÉHO prodávaného kusu (u profilů tedy za 3m tyč, ne za běžný metr - to má samostatné pole "Hmotnost
          (kg/1m)" v záložce Ceny profilů). Používá se pro dopravu (Toptrans) i součet hmotnosti objednávky/košíku.</div>
        <input id="scfWeightKg" type="number" min="0" step="0.001" placeholder="hmotnost (kg)"
          value="${sp.weight_g != null ? (sp.weight_g / 1000) : ""}" style="width:33%;">
      </div>
      ${!sp.cfg_dily_id ? `
      <div class="sc-stat sc-span-full" style="border-top:1px solid #3a3f4a;padding-top:12px;margin-top:4px;">
        <div class="sc-stat-label">Rozměry pro dopravu (mm) — Robert 2026-08-08: "tak založ v kartách produktů také rozměry".
          Používá se k výpočtu objemu zásilky pro Toptrans dopravu (bere se vyšší cena z hmotnosti/objemu). U profilů
          (napojených na 3D scénu) se počítá automaticky z průřezu, tady se doplňuje jen u ostatního zboží.</div>
        <div style="display:flex;gap:8px;align-items:center;">
          <input id="scfLengthMm" type="number" min="0" step="1" placeholder="délka" value="${sp.length_mm ?? ""}" style="width:33%;">
          <span>×</span>
          <input id="scfWidthMm" type="number" min="0" step="1" placeholder="šířka" value="${sp.width_mm ?? ""}" style="width:33%;">
          <span>×</span>
          <input id="scfHeightMm" type="number" min="0" step="1" placeholder="výška" value="${sp.height_mm ?? ""}" style="width:33%;">
        </div>
      </div>` : ""}
    </div>`;

  // Cenotvorba (Robert 2026-08-08: "vlastni zalozky nech ma take ceno
  // tvorba") - presunuty automaticky refresh ceny z logiman.cz (drive
  // soucast Doplnkovych udaju), ktera do jejich obecne "Doplnkove"
  // sekce fakticky nepatrila.
  const scDtLocal = (iso) => iso ? iso.slice(0, 16) : "";
  const pricingBox = document.getElementById("stockCardPricing");
  pricingBox.style.display = "";
  pricingBox.innerHTML = `<h4 class="sc-section-title">Cenotvorba</h4>
    <div class="sc-header-grid">
      <div class="sc-stat sc-span-full">
        <div class="sc-stat-label">Zdrojová URL (logiman.cz) — cena se z ní 1× týdně automaticky obnoví</div>
        <div style="display:flex;gap:6px;align-items:center;">
          <input id="scfPriceSourceUrl" type="text" placeholder="https://www.logiman.cz/..." value="${escapeHtmlAdmin(sp.price_source_url || "")}" style="flex:1;">
          <button id="scfRefreshPriceBtn" type="button" style="flex:0 0 auto;">Obnovit cenu</button>
        </div>
        <div id="scfPriceRefreshStatus" style="font-size:11px;color:#666;margin-top:4px;">${sp.price_last_refreshed_at ? "Naposledy obnoveno: " + new Date(sp.price_last_refreshed_at).toLocaleString("cs-CZ") : "Zatím neobnoveno."}</div>
      </div>
      <div class="sc-stat sc-span-full" style="border-top:1px solid #3a3f4a;padding-top:12px;margin-top:4px;">
        <div class="sc-stat-label">Zdroj ceny (Doguskalip) — náš dodavatel, párováno automaticky přes SKU. Cena se každou noc (kolem 3:20) automaticky obnoví ze skutečného ceníku Dogus: cena v USD × koeficient kategorie × aktuální kurz Fio banka (devizy, "Prodej"), u tyčí navíc × 3 (cena tyče 3 m), nahoru na celé koruny — viz scripts/2026-08-09_dogus_price_recompute.py.</div>
        ${sp.dogus_url ? `
        <div style="font-size:12.5px;">
          <a href="${escapeHtmlAdmin(sp.dogus_url)}" target="_blank" rel="noopener">${escapeHtmlAdmin(sp.dogus_url)}</a>
        </div>
        <div style="font-size:11px;color:#666;margin-top:4px;">
          Kód: ${escapeHtmlAdmin(sp.dogus_stock_code || "")} · spárováno ${sp.dogus_matched_at ? new Date(sp.dogus_matched_at).toLocaleString("cs-CZ") : "-"}
        </div>
        ${(sp.dogus_list_price_usd != null || sp.dogus_price_rate_used != null) ? `
        <div style="font-size:11px;color:#666;margin-top:4px;">
          ${sp.dogus_list_price_usd != null ? `Cena Dogus: <strong>${sp.dogus_list_price_usd.toLocaleString("cs-CZ")} USD/m</strong>` : ""}
          ${sp.dogus_price_rate_used != null ? ` · kurz použitý při posledním přepočtu: <strong>${sp.dogus_price_rate_used.toLocaleString("cs-CZ")} Kč/USD</strong> (Fio banka, prodej)` : ""}
        </div>` : ""}
        ${(sp.dogus_image_render_url || sp.dogus_image_schema_url) ? `
        <div style="display:flex;gap:8px;margin-top:8px;">
          ${sp.dogus_image_render_url ? `<a href="${escapeHtmlAdmin(sp.dogus_image_render_url)}" target="_blank" title="Render"><img src="${escapeHtmlAdmin(sp.dogus_image_render_url)}" loading="lazy" style="width:72px;height:72px;object-fit:cover;border-radius:6px;border:1px solid var(--sc-stat-border);"></a>` : ""}
          ${(sp.dogus_image_schema_url && sp.dogus_image_schema_url !== sp.dogus_image_render_url) ? `<a href="${escapeHtmlAdmin(sp.dogus_image_schema_url)}" target="_blank" title="Schéma"><img src="${escapeHtmlAdmin(sp.dogus_image_schema_url)}" loading="lazy" style="width:72px;height:72px;object-fit:cover;border-radius:6px;border:1px solid var(--sc-stat-border);"></a>` : ""}
        </div>` : ""}
        ${sp.product_specs_json ? `
        <table style="width:100%;font-size:11.5px;margin-top:8px;border-collapse:collapse;">
          <tbody>
            ${Object.entries(sp.product_specs_json).map(([k, v]) => `<tr><td style="padding:2px 6px;color:var(--text-muted);white-space:nowrap;">${escapeHtmlAdmin(k)}</td><td style="padding:2px 6px;">${escapeHtmlAdmin(String(v))}</td></tr>`).join("")}
          </tbody>
        </table>` : ""}
        ` : `<div style="font-size:11px;color:#666;">Nespárováno (SKU nesedí s doguskalip.com.tr, nebo produkt zatím nebyl importován).</div>`}
      </div>
      <div class="sc-stat sc-span-full" style="border-top:1px solid #3a3f4a;padding-top:12px;margin-top:4px;">
        <div class="sc-stat-label">Akční cena s časovou platností — Robert: "akcni cena s casovou platnosti"</div>
        <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;">
          <input id="scfSalePrice" type="number" step="0.01" min="0" placeholder="akční cena (Kč)" value="${sp.sale_price_czk ?? ""}" style="width:140px;">
          <label style="font-size:12px;color:var(--text-muted);display:flex;align-items:center;gap:4px;" title="Zadává se v pražském čase.">od
            <input id="scfSaleFrom" type="datetime-local" value="${scDtLocal(sp.sale_price_from)}" title="pražský čas">
          </label>
          <label style="font-size:12px;color:var(--text-muted);display:flex;align-items:center;gap:4px;" title="Zadává se v pražském čase.">do
            <input id="scfSaleUntil" type="datetime-local" value="${scDtLocal(sp.sale_price_until)}" title="pražský čas">
          </label>
        </div>
        <div style="font-size:11px;color:#666;margin-top:4px;">Prázdné od/do = bez omezení daným směrem. Čas je pražský. Akční cena se použije jen v tomto časovém okně a jen pokud je nižší než ostatní ceny.</div>
      </div>
      ${ADMIN_USER && ADMIN_USER.role === "admin" ? `
      <div class="sc-stat sc-span-full" style="border-top:1px solid #3a3f4a;padding-top:12px;margin-top:4px;">
        <div class="sc-stat-label">Dealerská sleva (%) — jen pro administrátora. Robert: "prihlaseny ktery ma schvalenou dealerskou slevu, vidi ceny rovnou ponizene"</div>
        <input id="scfDealerDiscount" type="number" step="0.1" min="0" max="100" placeholder="např. 15" value="${sp.dealer_discount_percent ?? ""}" style="width:140px;">
        <div style="font-size:11px;color:#666;margin-top:4px;">Platí jen pro zákazníky se schválenou dealerskou slevou (Zákazníci → editace zákazníka).</div>
      </div>` : ""}
      <div class="sc-stat sc-span-full" style="border-top:1px solid #3a3f4a;padding-top:12px;margin-top:4px;">
        <div class="sc-stat-label">Slevové kupóny — Robert: "kuponovy system (forma jednorazove slevy)", jeden sdílený kód pro tento produkt</div>
        <div class="add-form" style="margin-bottom:8px;">
          <input id="scfCouponCode" type="text" placeholder="KÓD" style="width:110px;text-transform:uppercase;">
          <select id="scfCouponType"><option value="percent">%</option><option value="fixed">Kč</option></select>
          <input id="scfCouponValue" type="number" step="0.01" min="0" placeholder="hodnota" style="width:90px;">
          <input id="scfCouponFrom" type="datetime-local" title="platí od (nepovinné, pražský čas)">
          <input id="scfCouponUntil" type="datetime-local" title="platí do (nepovinné, pražský čas)">
          <button id="scfCouponAddBtn" type="button">Přidat kupón</button>
        </div>
        <div id="scfCouponErr" class="err"></div>
        <table style="width:100%;font-size:12.5px;">
          <thead><tr><th style="text-align:left;">Kód</th><th style="text-align:left;">Sleva</th><th style="text-align:left;">Platnost</th><th style="text-align:left;">Aktivní</th><th></th></tr></thead>
          <tbody id="scfCouponsTbody"></tbody>
        </table>
      </div>
    </div>`;

  // Hover okno (Robert 2026-08-08: "Hover okno na vlastni zalozku") -
  // presunuto z Doplnkovych udaju, viz sql/2026-08-08_product_hover_price.sql.
  const hoverBox = document.getElementById("stockCardHoverWindow");
  hoverBox.style.display = "";
  hoverBox.innerHTML = `<h4 class="sc-section-title">Hover okno produktu</h4>
    <div class="sc-header-grid">
      <div class="sc-stat sc-span-full">
        <label style="display:flex;align-items:center;gap:6px;cursor:pointer;margin-bottom:8px;">
          <input id="scfPriceVisible" type="checkbox" ${sp.price_visible_default === 0 ? "" : "checked"}>
          <span><b>Cena je vidět</b> — standardní zobrazení na kartě produktu v přehledu kategorie. Když se odškrtne, cena
            (a případně dostupnost) zmizí z karty a zobrazí se až po najetí myší ("hover okno") — zaškrtni níže, co se v něm má objevit.</span>
        </label>
        <div id="scfHoverOptsWrap" style="display:${sp.price_visible_default === 0 ? "flex" : "none"};flex-direction:column;padding-left:22px;gap:6px;">
          <label style="display:flex;align-items:center;gap:6px;cursor:pointer;">
            <input id="scfHoverShowPrice" type="checkbox" ${sp.hover_show_price === 0 ? "" : "checked"}>
            <span>V hover okně zobrazit cenu</span>
          </label>
          <label style="display:flex;align-items:center;gap:6px;cursor:pointer;">
            <input id="scfHoverShowAvailability" type="checkbox" ${sp.hover_show_availability ? "checked" : ""}>
            <span>V hover okně zobrazit dostupnost</span>
          </label>
        </div>
      </div>
    </div>`;

  // GEO/SEO (Robert 2026-08-08: "GEO/SEO(udelat)") - stejny vzor jako
  // content_categories.meta_title/meta_description, viz
  // sql/2026-08-08_product_seo_meta.sql.
  const seoBox = document.getElementById("stockCardSeo");
  seoBox.style.display = "";
  seoBox.innerHTML = `<h4 class="sc-section-title">GEO/SEO</h4>
    <div class="sc-header-grid">
      <div class="sc-stat sc-span-full">${scFieldLabel("meta_title")}<input id="scfMetaTitle" type="text" maxlength="255" value="${escapeHtmlAdmin(sp.meta_title || "")}" style="width:100%;"></div>
      <div class="sc-stat sc-span-full">${scFieldLabel("meta_description")}<textarea id="scfMetaDescription" maxlength="500" rows="3" style="width:100%;font-family:inherit;">${escapeHtmlAdmin(sp.meta_description || "")}</textarea></div>
    </div>`;

  // Souvisejici (Robert 2026-08-08: "zalozka nova Souvisejici, tam
  // budou presunuty jiz existuji souvis.produkty, dale souvisejici
  // dokumenty napr pdf a videa") - kody presunuty z Doplnkovych udaju
  // (scCodesField wiring dole beze zmeny), + novy sprava dokumentu.
  const relatedBox = document.getElementById("stockCardRelated");
  relatedBox.style.display = "";
  relatedBox.innerHTML = `<h4 class="sc-section-title">Související</h4>
    <div class="sc-header-grid">
      <div class="sc-stat sc-span-full">${scFieldLabel("alternative_codes")}<input id="scfAltCodes" type="text" placeholder="oddělené čárkou" value="${escapeHtmlAdmin(codesToText(sp.alternative_product_codes))}" style="width:100%;"></div>
      <div class="sc-stat sc-span-full">${scFieldLabel("related_codes")}<input id="scfRelCodes" type="text" placeholder="oddělené čárkou" value="${escapeHtmlAdmin(codesToText(sp.related_product_codes))}" style="width:100%;"></div>
      <div class="sc-stat sc-span-full" style="border-top:1px solid #3a3f4a;padding-top:12px;margin-top:4px;">
        <div class="sc-stat-label">Související dokumenty (PDF, video, YouTube)</div>
        <div class="add-form" style="margin-bottom:8px;">
          <select id="scfDocType"><option value="pdf">PDF</option><option value="video">Video (soubor)</option><option value="youtube">YouTube (odkaz)</option></select>
          <input id="scfDocFile" type="file" accept=".pdf,.mp4,.webm,.mov">
          <input id="scfDocYoutubeUrl" type="text" placeholder="https://www.youtube.com/watch?v=..." style="width:220px;display:none;">
          <input id="scfDocCaption" type="text" placeholder="popisek (nepovinné)" style="width:160px;">
          <button id="scfDocUploadBtn" type="button">Přidat</button>
        </div>
        <div id="scfDocErr" class="err"></div>
        <div id="scfDocList" style="display:flex;flex-direction:column;gap:4px;"></div>
      </div>
    </div>`;

  const scTextField = (id, key) => {
    document.getElementById(id).onchange = async (e) => {
      await scPutProduct({ [key]: e.target.value.trim() || null });
      scSaveFlash(id);
    };
  };
  scTextField("scfManufacturer", "manufacturer");
  scTextField("scfSupplier", "supplier_name");
  scTextField("scfEan", "ean");
  scTextField("scfWarranty", "warranty");
  scTextField("scfCategoryPath", "category_path");
  scTextField("scfAvailability", "availability_text");
  scTextField("scfPriceSourceUrl", "price_source_url");
  scTextField("scfMetaTitle", "meta_title");
  scTextField("scfMetaDescription", "meta_description");
  // bot7, 2026-08-07 (Robert: "potřebuji dát produktu barvu ve scéně, aby
  // se objevil rovnou zbarvený") - jen kdyz ma produkt glb_file (viz
  // podminka pri vykresleni vyse), jinak input v DOM neexistuje.
  const sceneColorInput = document.getElementById("scfSceneColor");
  if (sceneColorInput) {
    sceneColorInput.onchange = async (e) => {
      await scPutProduct({ color_hex: e.target.value });
      scSaveFlash("scfSceneColor");
    };
    document.getElementById("scfSceneColorClear").onclick = async () => {
      await scPutProduct({ color_hex: null });
      sceneColorInput.value = "#9aa0a6";
      scSaveFlash("scfSceneColor");
    };
  }
  // bot7, 2026-08-07 (Robert: "postavit 2D protahovani pro desky"). Od 2026-09-30 je zatrzitko dostupne u KAZDEHO
  // produktu (drive jen s glb_file): is_board_material urcuje i cenu desky na webu a v kosiku (cena_desky), rezani
  // pridezu a rozmer tabule - u desky bez 3D modelu (napr. laminodeska 4933) proto nesla oznacit ani zadat format.
  const boardMaterialCb = document.getElementById("scfBoardMaterial");
  if (boardMaterialCb) {
    boardMaterialCb.onchange = async (e) => {
      const zapnout = e.target.checked;
      // Deska ma cenu VZDY za 1 m² (jednotka "m2"), ostatni zbozi za kus ("ks") nebo metr: zmena druhu produktu proto
      // meni VYZNAM uz zadaneho cisla - pred ulozenim se ukaze dopad a nechá se potvrdit (stejna past jako 3671).
      const cenaTxt = document.getElementById("scfPrice").value;
      const cena = cenaTxt === "" ? NaN : parseFloat(cenaTxt);
      if (Number.isFinite(cena) && cena > 0 && ((zapnout && sp.unit !== "m2") || (!zapnout && sp.unit === "m2"))) {
        if (zapnout) {
          const w = parseInt(document.getElementById("scfBoardSheetWidth").value, 10);
          const h = parseInt(document.getElementById("scfBoardSheetHeight").value, 10);
          const p = scfPrepocetDesky("m2", cena, w, h);
          const dopad = p.za_tabuli != null
            ? `celá tabule ${w}×${h} mm pak vyjde na ${scfKc(p.za_tabuli)}`
            : "formát tabule zatím chybí, cena tabule se nedá spočítat";
          if (!confirm(`Zapnout deskový materiál?\n\nCena desky se zadává vždy za 1 m². Zadané číslo ${scfKc(cena)} se od teď čte jako cena ZA 1 m² (${dopad}).\n\n`
            + `Bylo-li ${scfKc(cena)} cena za kus nebo za celou tabuli, po zapnutí ji přepiš na cenu za 1 m².`)) { e.target.checked = false; return; }
        } else if (!confirm(`Vypnout deskový materiál?\n\nCena ${scfKc(cena)} se od teď čte jako cena ZA KUS (dosud za 1 m²). Přepiš ji podle potřeby.`)) {
          e.target.checked = true; return;
        }
      }
      const telo = { is_board_material: zapnout, unit: zapnout ? "m2" : "ks" };
      if (!(await scPutProduct(telo))) { e.target.checked = !zapnout; return; }
      sp.is_board_material = zapnout; product.is_board_material = zapnout ? 1 : 0;
      sp.unit = telo.unit; product.unit = telo.unit;
      scfObnovDesku();
      if (typeof loadShopProducts === "function") loadShopProducts();
    };
  }
  // Robert 2026-08-08 ("dej do skladových karet deskový materiálů ten
  // formát tabule k vyplňování") - referencni rozmer cele tabule (ne
  // vyrezaneho kusu, ten se pocita zive ve scene.html).
  const boardSheetW = document.getElementById("scfBoardSheetWidth");
  const boardSheetH = document.getElementById("scfBoardSheetHeight");
  if (boardSheetW && boardSheetH) {
    boardSheetW.onchange = async (e) => {
      const v = e.target.value.trim();
      const mm = v === "" ? null : parseInt(v, 10);
      if (!(await scPutProduct({ board_sheet_width_mm: mm }))) { e.target.value = sp.board_sheet_width_mm ?? ""; scfPrepocet(); return; }
      sp.board_sheet_width_mm = mm; product.board_sheet_width_mm = mm;
      scSaveFlash("scfBoardSheetWidth");
      scfPrepocet();
    };
    boardSheetH.onchange = async (e) => {
      const v = e.target.value.trim();
      const mm = v === "" ? null : parseInt(v, 10);
      if (!(await scPutProduct({ board_sheet_height_mm: mm }))) { e.target.value = sp.board_sheet_height_mm ?? ""; scfPrepocet(); return; }
      sp.board_sheet_height_mm = mm; product.board_sheet_height_mm = mm;
      scSaveFlash("scfBoardSheetHeight");
      scfPrepocet();
    };
    // prepocet ceny uz pri psani rozmeru (ulozi se az po opusteni pole)
    boardSheetW.addEventListener("input", scfPrepocet);
    boardSheetH.addEventListener("input", scfPrepocet);
  }
  scfObnovDesku();                      // pocatecni stav: viditelnost bloku desky (cena za 1 m² / nabidka prevodu) + prepocet
  scfSlugAktualizuj();                  // odkaz "Prepsat adresu z nazvu" pod nazvem
  // Robert 2026-08-08 ("napoj reálně funkčně na řezné plány") -
  // mapovani na shop_cutting_stock.material_key, viz sql/
  // 2026-08-08_board_cutting_material_key.sql.
  const cuttingMaterialKey = document.getElementById("scfCuttingMaterialKey");
  if (cuttingMaterialKey) {
    cuttingMaterialKey.onchange = async (e) => {
      const v = e.target.value.trim();
      await scPutProduct({ cutting_material_key: v || null });
      scSaveFlash("scfCuttingMaterialKey");
    };
  }
  // Robert 2026-08-31 ("u všech produktů přidat hmotnost") - ulozeno
  // primo v gramech (weight_g), input je v kg kvuli citelnosti (stejna
  // kg<->g konverze jako u zobrazeni weight_kg_approx/weight_kg jinde
  // v projektu). Math.round, at se needitovanim des. cisla nehromadi
  // zaokrouhlovaci chyba pri opakovanem kg->g->kg prevodu.
  const weightKgEl = document.getElementById("scfWeightKg");
  if (weightKgEl) {
    weightKgEl.onchange = async (e) => {
      const v = e.target.value.trim();
      await scPutProduct({ weight_g: v === "" ? null : Math.round(parseFloat(v) * 1000) });
      scSaveFlash("scfWeightKg");
    };
  }
  // Robert 2026-08-08 ("tak založ v kartách produktů také rozměry") -
  // rozmery pro vypocet objemu Toptrans dopravy, jen u produktu BEZ
  // cfg_dily_id (u profilu se pocita automaticky z prurezu, viz podminka
  // pri vykresleni vyse).
  [["scfLengthMm", "length_mm"], ["scfWidthMm", "width_mm"], ["scfHeightMm", "height_mm"]].forEach(([id, key]) => {
    const el = document.getElementById(id);
    if (!el) return;
    el.onchange = async (e) => {
      const v = e.target.value.trim();
      await scPutProduct({ [key]: v === "" ? null : parseInt(v, 10) });
      scSaveFlash(id);
    };
  });
  // Robert 2026-08-08 ("Hover okno produktu" - zatrzitka Cena je
  // vidět/není vidět ve skladové kartě, viz sql/2026-08-08_product_hover_price.sql).
  const priceVisibleCb = document.getElementById("scfPriceVisible");
  const hoverOptsWrap = document.getElementById("scfHoverOptsWrap");
  const hoverShowPriceCb = document.getElementById("scfHoverShowPrice");
  const hoverShowAvailabilityCb = document.getElementById("scfHoverShowAvailability");
  if (priceVisibleCb) {
    priceVisibleCb.onchange = async (e) => {
      if (hoverOptsWrap) hoverOptsWrap.style.display = e.target.checked ? "none" : "flex";
      await scPutProduct({ price_visible_default: e.target.checked });
      if (typeof loadShopProducts === "function") loadShopProducts();
    };
  }
  if (hoverShowPriceCb) {
    hoverShowPriceCb.onchange = async (e) => {
      await scPutProduct({ hover_show_price: e.target.checked });
      if (typeof loadShopProducts === "function") loadShopProducts();
    };
  }
  if (hoverShowAvailabilityCb) {
    hoverShowAvailabilityCb.onchange = async (e) => {
      await scPutProduct({ hover_show_availability: e.target.checked });
      if (typeof loadShopProducts === "function") loadShopProducts();
    };
  }
  document.getElementById("scfRefreshPriceBtn").onclick = async () => {
    const statusEl = document.getElementById("scfPriceRefreshStatus");
    const urlVal = document.getElementById("scfPriceSourceUrl").value.trim();
    if (!urlVal) {
      statusEl.textContent = "Nejdřív vyplň a ulož zdrojovou URL.";
      return;
    }
    statusEl.textContent = "Načítám cenu…";
    try {
      const r = await fetch(`/api/shop/products/${product.id}/refresh-price`, { method: "POST" });
      const data = await r.json();
      if (!r.ok) {
        statusEl.textContent = "Chyba: " + (data.error || "obnovení selhalo");
        return;
      }
      statusEl.textContent = "✓ Obnoveno: " + data.price_czk.toLocaleString("cs-CZ") + " Kč (" + new Date().toLocaleString("cs-CZ") + ")";
      document.getElementById("scfPrice").value = data.price_czk;
      if (typeof loadShopProducts === "function") loadShopProducts();
    } catch (err) {
      statusEl.textContent = "Chyba: " + err.message;
    }
  };
  const scCodesField = (id, key) => {
    document.getElementById(id).onchange = async (e) => {
      const list = e.target.value.split(",").map(s => s.trim()).filter(Boolean);
      await scPutProduct({ [key]: list });
      scSaveFlash(id);
    };
  };
  scCodesField("scfAltCodes", "alternative_product_codes");
  scCodesField("scfRelCodes", "related_product_codes");

  // Akcni cena (Robert 2026-08-08) - datetime-local input vraci
  // "YYYY-MM-DDTHH:MM" (bez sekund/casove zony) - MySQL DATETIME to
  // prijme primo, zadna dalsi konverze netreba.
  document.getElementById("scfSalePrice").onchange = async (e) => {
    const v = e.target.value.trim();
    await scPutProduct({ sale_price_czk: v === "" ? null : parseFloat(v) });
    scSaveFlash("scfSalePrice");
  };
  document.getElementById("scfSaleFrom").onchange = async (e) => {
    await scPutProduct({ sale_price_from: e.target.value || null });
    scSaveFlash("scfSaleFrom");
  };
  document.getElementById("scfSaleUntil").onchange = async (e) => {
    await scPutProduct({ sale_price_until: e.target.value || null });
    scSaveFlash("scfSaleUntil");
  };
  const dealerDiscountInput = document.getElementById("scfDealerDiscount");
  if (dealerDiscountInput) {
    dealerDiscountInput.onchange = async (e) => {
      const v = e.target.value.trim();
      await scPutProduct({ dealer_discount_percent: v === "" ? null : parseFloat(v) });
      scSaveFlash("scfDealerDiscount");
    };
  }

  // Kupony (Robert 2026-08-08: "kuponovy system") - vlastni CRUD, ne
  // scPutProduct (separatni tabulka shop_product_coupons).
  async function scLoadCoupons() {
    const r = await fetch(`/api/shop/products/${product.id}/coupons`);
    const data = await r.json().catch(() => ({ coupons: [] }));
    const tbody = document.getElementById("scfCouponsTbody");
    if (!tbody) return;
    const coupons = data.coupons || [];
    if (!coupons.length) {
      tbody.innerHTML = '<tr><td colspan="5" style="color:#666;">Žádné kupóny.</td></tr>';
      return;
    }
    tbody.innerHTML = coupons.map(c => {
      const period = (c.valid_from ? new Date(c.valid_from).toLocaleDateString("cs-CZ") : "…") + " – " +
        (c.valid_until ? new Date(c.valid_until).toLocaleDateString("cs-CZ") : "…");
      const discount = c.discount_type === "percent" ? `${c.discount_value} %` : `${c.discount_value} Kč`;
      return `<tr data-id="${c.id}">
        <td>${escapeHtmlAdmin(c.code)}</td>
        <td>${discount}</td>
        <td>${period}</td>
        <td><input type="checkbox" class="scf-coupon-active" ${c.active ? "checked" : ""}></td>
        <td><button type="button" class="scf-coupon-del" style="background:none;border:1px solid #3a3f4a;color:#c7ccd4;">Smazat</button></td>
      </tr>`;
    }).join("");
    tbody.querySelectorAll(".scf-coupon-active").forEach(cb => {
      cb.onchange = async (e) => {
        const id = e.target.closest("tr").dataset.id;
        await fetch(`/api/shop/products/coupons/${id}`, {
          method: "PUT", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ active: e.target.checked }),
        });
      };
    });
    tbody.querySelectorAll(".scf-coupon-del").forEach(btn => {
      btn.onclick = async () => {
        const id = btn.closest("tr").dataset.id;
        if (!confirm("Smazat tento kupón?")) return;
        await fetch(`/api/shop/products/coupons/${id}`, { method: "DELETE" });
        scLoadCoupons();
      };
    });
  }
  scLoadCoupons();
  document.getElementById("scfCouponAddBtn").onclick = async () => {
    const errEl = document.getElementById("scfCouponErr");
    errEl.textContent = "";
    const code = document.getElementById("scfCouponCode").value.trim();
    const discount_type = document.getElementById("scfCouponType").value;
    const discount_value = document.getElementById("scfCouponValue").value;
    const valid_from = document.getElementById("scfCouponFrom").value || null;
    const valid_until = document.getElementById("scfCouponUntil").value || null;
    if (!code || discount_value === "") { errEl.textContent = "Vyplň kód i hodnotu slevy."; return; }
    const r = await fetch(`/api/shop/products/${product.id}/coupons`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code, discount_type, discount_value: parseFloat(discount_value), valid_from, valid_until }),
    });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) { errEl.textContent = data.error || "Chyba."; return; }
    document.getElementById("scfCouponCode").value = "";
    document.getElementById("scfCouponValue").value = "";
    document.getElementById("scfCouponFrom").value = "";
    document.getElementById("scfCouponUntil").value = "";
    scLoadCoupons();
  };

  // Souvisejici dokumenty (Robert 2026-08-08) - PDF/video upload.
  async function scLoadDocuments() {
    const r = await fetch(`/api/shop/products/${product.id}`);
    const data = await r.json().catch(() => ({ documents: [] }));
    const listEl = document.getElementById("scfDocList");
    if (!listEl) return;
    const docs = data.documents || [];
    if (!docs.length) {
      listEl.innerHTML = '<div style="color:#666;font-size:12.5px;">Žádné dokumenty.</div>';
      return;
    }
    listEl.innerHTML = docs.map(d => `
      <div data-id="${d.id}" style="display:flex;align-items:center;gap:8px;font-size:12.5px;">
        <span style="text-transform:uppercase;color:var(--text-muted);">${d.doc_type}</span>
        <a href="${d.url}" target="_blank" rel="noopener">${escapeHtmlAdmin(d.caption || d.original_name || d.url)}</a>
        <button type="button" class="scf-doc-del" style="background:none;border:1px solid #3a3f4a;color:#c7ccd4;">×</button>
      </div>
    `).join("");
    listEl.querySelectorAll(".scf-doc-del").forEach(btn => {
      btn.onclick = async () => {
        const id = btn.closest("[data-id]").dataset.id;
        if (!confirm("Smazat tento dokument?")) return;
        await fetch(`/api/shop/products/documents/${id}`, { method: "DELETE" });
        scLoadDocuments();
      };
    });
  }
  scLoadDocuments();
  // Robert 2026-08-09: "moznost vlozit do detailu produktu video jako
  // embed z youtube" - typ "youtube" nema soubor k nahrani, jen odkaz
  // (JSON POST na samostatny endpoint), proto se pri jeho vyberu
  // schova souborovy input a ukaze textovy pro URL.
  const docTypeSel = document.getElementById("scfDocType");
  const docFileInput = document.getElementById("scfDocFile");
  const docYoutubeInput = document.getElementById("scfDocYoutubeUrl");
  docTypeSel.onchange = () => {
    const isYoutube = docTypeSel.value === "youtube";
    docFileInput.style.display = isYoutube ? "none" : "";
    docYoutubeInput.style.display = isYoutube ? "" : "none";
  };
  document.getElementById("scfDocUploadBtn").onclick = async () => {
    const errEl = document.getElementById("scfDocErr");
    errEl.textContent = "";
    const docType = docTypeSel.value;
    const caption = document.getElementById("scfDocCaption").value.trim();
    let r, data;
    if (docType === "youtube") {
      const url = docYoutubeInput.value.trim();
      if (!url) { errEl.textContent = "Vlož odkaz na YouTube video."; return; }
      r = await fetch(`/api/shop/products/${product.id}/documents/youtube`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url, caption }),
      });
      data = await r.json().catch(() => ({}));
      if (!r.ok) { errEl.textContent = data.error || "Chyba."; return; }
      docYoutubeInput.value = "";
    } else {
      const file = docFileInput.files[0];
      if (!file) { errEl.textContent = "Vyber soubor."; return; }
      const fd = new FormData();
      fd.append("file", file);
      fd.append("doc_type", docType);
      fd.append("caption", caption);
      r = await fetch(`/api/shop/products/${product.id}/documents`, { method: "POST", body: fd });
      data = await r.json().catch(() => ({}));
      if (!r.ok) { errEl.textContent = data.error || "Chyba."; return; }
      docFileInput.value = "";
    }
    document.getElementById("scfDocCaption").value = "";
    scLoadDocuments();
  };

  // Robert 2026-08-08 ("do produktové sestavy přineseme i cenu, i kusovník,
  // bude vidět v administraci všemi rolemi, nebude vidět na eshopu") -
  // kusovnik+cenovy rozpis jsou snapshot z okamziku ulozeni sestavy ve scene
  // (viz computeAssemblyBomAndPrice ve scene.html), cteny VYHRADNE pres
  // staff-scoped GET /api/admin/product-assemblies/by-product/<id>
  // (require_permission sklad_karty/zobrazit - tedy videt kazda role, ktera
  // se do teto karty vubec dostane), NIKDY pres verejny GET /api/shop/
  // products/<id> - proto samostatny fetch tady, ne soucast `data` vyse.
  // Sekce se zobrazi jen kdyz produkt ma navazanou sestavu (typicky vznikla
  // z Ctrl+Shift+S ve scene.html "Produktové sestavy").
  const bomBox = document.getElementById("stockCardBomSection");
  bomBox.style.display = "none";
  bomBox.innerHTML = "";
  scCurrent3dVariants = [];
  scVariantPartsCache.clear();
  // Panel variant patri predchozimu produktu - zahodit, jinak by se pri
  // otevreni jine karty ukazala stara provedeni (scVariantyBuiltFor
  // porovnava referenci pole, ktere se tady prave meni).
  scVariantyBuiltFor = null;
  const variantyBox = document.getElementById("stockCardVariantyPanel");
  if (variantyBox) variantyBox.innerHTML = "";
  fetch(`/api/admin/product-assemblies/by-product/${product.id}`)
    .then(r => r.ok ? r.json() : { assembly: null, assemblies: [] })
    .then(({ assembly, assemblies }) => {
      // Vsechny navazane sestavy = schvalene varianty pro ekvalizer
      // (Robert 2026-09-10). Poradi = poradi vzniku, prvni je zakladni.
      scCurrent3dVariants = Array.isArray(assemblies) ? assemblies : [];
      scRenderBomSection(assembly);
    })
    .catch(() => {}); // kusovnik neni kriticka funkce - tise ignoruj chybu nacteni

  // Zivy 3D nahled (zalozka "3D model", viz scBuildViewer3D vyse) - potrebuje
  // PLNOU geometrii (position/quaternion/scale kazdeho dilu), kterou
  // by-product/<id> vyse NEVRACI (jen bom/price_summary snapshot). Lazy:
  // samotny Three.js viewer se postavi az pri prvnim prepnuti na zalozku
  // (scSwitchTab nize), tady jen pripravime data a schovame sekci, kdyz
  // produkt zadnou sestavu nema.
  const viewer3dBox = document.getElementById("stockCard3dViewer");
  viewer3dBox.style.display = "none";
  viewer3dBox.innerHTML = "";
  scCurrent3dParts = null;
  scDisposeViewer3D();
  fetch(`/api/product-assemblies/lookup?product=${product.id}`)
    .then(r => r.ok ? r.json() : null)
    .then(data => {
      scCurrent3dParts = (data && data.assembly && data.assembly.parts) || null;
      // fetch je async - kdyz uzivatel uz mezitim kliknul na zalozku "3D
      // model" (viewer3dBox jeste schovany, protoze data tehdy nebyla),
      // dostav to teprve ted.
      const active = document.querySelector("#stockCardModalBox .sc-tab.active");
      if (active && active.dataset.tab === "model3d") scSwitchTab("model3d");
    })
    .catch(() => { scCurrent3dParts = null; });

  // Explicitni "Uložit změny" (Robert 2026-07-26: "vůbec tam není uložit" -
  // auto-save per pole na onchange uz existovalo, ale bylo malo viditelne
  // (jen kratky zeleny orámek). Tohle tlacitko posle VSECHNA aktualni pole
  // najednou v jednom PUT a da jasnou vizualni zpetnou vazbu, i kdyby
  // uzivatel u nejakeho pole zapomnel odkliknout mimo (blur).
  document.getElementById("stockCardSave").onclick = async () => {
    const altList = document.getElementById("scfAltCodes").value.split(",").map(s => s.trim()).filter(Boolean);
    const relList = document.getElementById("scfRelCodes").value.split(",").map(s => s.trim()).filter(Boolean);
    const minV = document.getElementById("scfMin").value;
    const maxV = document.getElementById("scfMax").value;
    const priceV = document.getElementById("scfPrice").value;
    const catV = document.getElementById("scfCategory").value;
    const ulozeno = await scPutProduct({
      name: document.getElementById("scfName").value.trim() || sp.name,
      sku: document.getElementById("scfSku").value.trim(),
      category_id: catV ? parseInt(catV, 10) : null,
      min_stock: minV === "" ? null : parseInt(minV, 10),
      max_stock: maxV === "" ? null : parseInt(maxV, 10),
      price_czk_placeholder: priceV === "" ? null : parseFloat(priceV),
      active: document.getElementById("scfActive").checked,
      manufacturer: document.getElementById("scfManufacturer").value.trim() || null,
      supplier_name: document.getElementById("scfSupplier").value.trim() || null,
      ean: document.getElementById("scfEan").value.trim() || null,
      warranty: document.getElementById("scfWarranty").value.trim() || null,
      category_path: document.getElementById("scfCategoryPath").value.trim() || null,
      availability_text: document.getElementById("scfAvailability").value.trim() || null,
      alternative_product_codes: altList,
      related_product_codes: relList,
    });
    // nazev ulozeny tlacitkem "Ulozit zmeny" se musi promitnout i do titulku karty
    const nazevNovy = document.getElementById("scfName").value.trim();
    if (ulozeno && nazevNovy && nazevNovy !== sp.name) {
      sp.name = nazevNovy; product.name = nazevNovy;
      scfSlugAktualizuj();
      document.getElementById("stockCardTitle").textContent = `Skladová karta — ${nazevNovy}`;
    }
    const indicator = document.getElementById("stockCardSaveIndicator");
    indicator.classList.add("show");
    setTimeout(() => indicator.classList.remove("show"), 1600);
    if (typeof loadShopProducts === "function") loadShopProducts();
  };

  // bot2, 2026-07-28: FBX upload pro produkty (Robert: "nekterym
  // produktum budeme pridavat fbx model k uploadu (obdobne jako pro
  // profily), polozka(produkt) ktery bude mit fbx model, se nasledne
  // pusti do 3D sceny do katalogu") - mirror UI z "Ceny profilu"
  // (uploadFbxFile/fbxStatusText), jen cili na /api/shop/products/<id>/fbx-upload.
  let fbxBox = document.getElementById("stockCardFbx");
  if (!fbxBox) {
    fbxBox = document.createElement("div");
    fbxBox.id = "stockCardFbx";
    fbxBox.className = "sc-section";
    document.getElementById("stockCardFbxWrap").appendChild(fbxBox);
  }
  // Robert 2026-08-08 ("do 3Dsceny nebudou vsechny produkty z eshopu,
  // ani vsechny ktere maji stp, ale pouze produkty s priznakem:
  // ProScenu") - mit nahrany 3D model uz NEznamena automaticky
  // zobrazeni ve scene (drive ano, viz git historie
  // shop_products_fbx_upload) - "Pro scénu" je ted samostatny prepinac
  // nize, status textu uz netvrdi automatickou viditelnost.
  const renderFbxStatus = (p) => {
    if (!p.fbx_original_name) return "Zatím nenahráno.";
    const dateTxt = p.fbx_uploaded_at ? " (" + new Date(p.fbx_uploaded_at).toLocaleString("cs-CZ") + ")" : "";
    return "✓ nahráno" + dateTxt + ": " + escapeHtmlAdmin(p.fbx_original_name);
  };
  // Robert 2026-08-09 ("v kartach jsou ulozene stp soubory, ty nesmi
  // zmizet, musí zustat pro dalsi pouziti" + "dalsim 3D souborem budou
  // glb ktere pretransformujeme z tech stp... tuto funkci pridej do
  // karet na zalozky 3D model, jako tlacitko Prevod na glb, prevedeny
  // glb nech zustane jakoby viditelny jako druhy soubor") - rucni
  // (opakovany) prevod uz ulozeneho STP/FBX na GLB pres
  // /convert-to-glb (na rozdil od /fbx-upload nize NENAHRAVA novy
  // soubor, jen znovu spusti prevod nad tim, co uz na disku je).
  // Zdrojovy soubor (fbx_original_name) timhle NIKDY nezmizi - GLB je
  // vzdy jen druhy, samostatny soubor vedle nej.
  const renderGlbStatus = (p) => p.glb_file ? "✓ GLB: " + escapeHtmlAdmin(p.glb_file) : "Zatím žádné GLB.";
  const fbxExt = (sp.fbx_original_name || "").toLowerCase().slice((sp.fbx_original_name || "").lastIndexOf("."));
  const fbxIsStep = fbxExt === ".stp" || fbxExt === ".step";
  // bot2, 2026-08-04: volba kvality 3D modelu (Robert: "potrebujeme
  // pridat do skladovych karet, zatrzitkovac hned vedle nacteni 3D
  // modelu, ma to byt vyber kvality 3D modelu, nejnizsi ta puvodni kdyz
  // je v modelu logo, stredni (tu jsme dnes pridali jako o 80% jemnejsi)
  // a dejme 3 stupen plne zaobleni, zaroven tam uvadejme velikost kB").
  // Jen pro STEP soubory (.stp/.step) - u FBX zadna volba kvality
  // neexistuje (jina, lehci prevodni cesta bez teto moznosti), proto se
  // panel kvality zobrazi az po vyberu .stp/.step souboru. Flow: vyber
  // souboru -> nahled velikosti (kB) pro vsechny 3 stupne najednou
  // (/api/admin/step-quality-preview, nic se natrvalo neuklada) ->
  // uzivatel zvoli stupen -> potvrdi -> az TEHDY se posle skutecny
  // upload (/api/shop/products/<id>/fbx-upload) se zvolenou kvalitou.
  fbxBox.innerHTML = `<h4 class="sc-section-title">3D model (FBX/STEP)</h4>
    <input type="file" id="scfFbxInput" accept=".fbx,.stp,.step" style="display:none;">
    <button id="scfFbxBtn">${sp.fbx_original_name ? "Nahradit model" : "Nahrát model"}</button>
    <div id="scfFbxQuality" style="display:none;margin-top:8px;padding:8px;border:1px solid var(--sc-stat-border);border-radius:6px;">
      <div style="font-size:11px;color:#666;margin-bottom:6px;">Kvalita 3D modelu (jen STEP):</div>
      <label style="display:block;font-size:12px;margin-bottom:4px;cursor:pointer;">
        <input type="radio" name="scfQuality" value="low"> Nízká - původní, s logem/rytinou
        <span class="scfQSize" data-q="low" style="color:#666;"></span>
      </label>
      <label style="display:block;font-size:12px;margin-bottom:4px;cursor:pointer;">
        <input type="radio" name="scfQuality" value="medium" checked> Střední - o 80&nbsp;% jemnější
        <span class="scfQSize" data-q="medium" style="color:#666;"></span>
      </label>
      <label style="display:block;font-size:12px;margin-bottom:8px;cursor:pointer;">
        <input type="radio" name="scfQuality" value="high"> Vysoká - plné zaoblení
        <span class="scfQSize" data-q="high" style="color:#666;"></span>
      </label>
      <button id="scfFbxConfirm">Nahrát s vybranou kvalitou</button>
      <button id="scfFbxCancel" style="margin-left:6px;">Zrušit</button>
    </div>
    <div id="scfFbxStatus" style="font-size:11px;color:#666;margin-top:4px;">${renderFbxStatus(sp)}</div>
    ${sp.fbx_original_name ? `
    <div id="scfConvertBox" style="margin-top:10px;padding:8px;border:1px solid var(--sc-stat-border);border-radius:6px;">
      <div style="font-size:11px;color:#666;margin-bottom:6px;">Ruční (opakovaný) převod uloženého souboru na GLB — zdrojový STP/FBX zůstane beze změny, GLB je vždy druhý, samostatný soubor.</div>
      ${fbxIsStep ? `<select id="scfConvertQuality" style="margin-right:6px;">
        <option value="low">Nízká - původní, s logem/rytinou</option>
        <option value="medium" selected>Střední - o 80&nbsp;% jemnější</option>
        <option value="high">Vysoká - plné zaoblení</option>
      </select>` : ""}
      <button id="scfConvertBtn" type="button">Převod na GLB</button>
      <div id="scfConvertStatus" style="font-size:11px;color:#666;margin-top:6px;">${renderGlbStatus(sp)}</div>
    </div>` : ""}
    <label style="display:flex;align-items:center;gap:6px;cursor:pointer;margin-top:8px;">
      <input id="scfVisibleInScene" type="checkbox" ${sp.visible_in_scene ? "checked" : ""}>
      <span><b>Pro scénu</b> — teprve tady se rozhodne, jestli se produkt objeví v katalogu dílů ve 3D scéně (nahraný 3D model sám o sobě ne).</span>
    </label>
    <label style="display:flex;align-items:center;gap:6px;cursor:pointer;margin-top:6px;">
      <input id="scfPlaceVertical" type="checkbox" ${sp.place_vertical ? "checked" : ""}>
      <span><b>Umístit svisle</b> — při vložení ze scény se díl postaví ve své původní (svislé) orientaci z 3D modelu, místo výchozího "leží na zemi". Hodí se pro drobné díly jako patičky/nožičky.</span>
    </label>`;
  document.getElementById("scfFbxBtn").onclick = () => document.getElementById("scfFbxInput").click();
  document.getElementById("scfVisibleInScene").onchange = async (e) => {
    await scPutProduct({ visible_in_scene: e.target.checked });
    scSaveFlash("scfVisibleInScene");
  };
  document.getElementById("scfPlaceVertical").onchange = async (e) => {
    await scPutProduct({ place_vertical: e.target.checked });
    scSaveFlash("scfPlaceVertical");
  };
  const scfConvertBtn = document.getElementById("scfConvertBtn");
  if (scfConvertBtn) {
    scfConvertBtn.onclick = async () => {
      const statusEl = document.getElementById("scfConvertStatus");
      const qualitySel = document.getElementById("scfConvertQuality");
      scfConvertBtn.disabled = true;
      statusEl.textContent = "Převádím…";
      try {
        const r = await fetch(`/api/shop/products/${product.id}/convert-to-glb`, {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ quality: qualitySel ? qualitySel.value : null }),
        });
        const data = await r.json();
        if (!r.ok || data.status !== "ok") {
          statusEl.textContent = "⚠ Převod selhal: " + ((data.conversion && data.conversion.error) || data.error || "neznámá chyba");
          return;
        }
        sp.glb_file = data.glb_file;
        statusEl.textContent = renderGlbStatus(sp);
      } catch (err) {
        statusEl.textContent = "Chyba: " + err.message;
      } finally {
        scfConvertBtn.disabled = false;
      }
    };
  }

  let scfPendingFile = null;

  const scfDoUpload = async (file, quality) => {
    const statusEl = document.getElementById("scfFbxStatus");
    statusEl.textContent = "Nahrávám a převádím…";
    const fd = new FormData();
    fd.append("file", file);
    if (quality) fd.append("quality", quality);
    try {
      const r = await fetch(`/api/shop/products/${product.id}/fbx-upload`, { method: "POST", body: fd });
      const respData = await r.json();
      if (!r.ok) {
        statusEl.textContent = "Chyba: " + (respData.error || "nahrání selhalo");
        return;
      }
      sp.fbx_original_name = respData.fbx_original_name;
      sp.fbx_uploaded_at = new Date().toISOString();
      const conv = respData.conversion || {};
      // Robert 2026-08-08: uspesny prevod uz NEnastavuje visible_in_scene
      // automaticky (viz renderFbxStatus komentar vyse) - jen informuje
      // o stavu prevodu, "Pro scénu" checkbox nize se ridi sam sebou.
      if (conv.success) {
        statusEl.textContent = "✓ nahráno a převedeno: " + escapeHtmlAdmin(sp.fbx_original_name);
      } else if (conv.attempted) {
        statusEl.textContent = "⚠ nahráno (" + escapeHtmlAdmin(sp.fbx_original_name) + "), převod do 3D selhal: " + escapeHtmlAdmin(conv.error || "neznámá chyba");
      } else {
        statusEl.textContent = "✓ nahráno (" + escapeHtmlAdmin(sp.fbx_original_name) + "), automatický převod nedostupný";
      }
      document.getElementById("scfFbxBtn").textContent = "Nahradit model";
      document.getElementById("scfFbxQuality").style.display = "none";
      scfPendingFile = null;
    } catch (err) {
      statusEl.textContent = "Chyba: " + err.message;
    }
  };

  document.getElementById("scfFbxInput").addEventListener("change", async () => {
    const input = document.getElementById("scfFbxInput");
    const file = input.files && input.files[0];
    if (!file) return;
    const statusEl = document.getElementById("scfFbxStatus");
    const ext = file.name.toLowerCase().slice(file.name.lastIndexOf("."));
    if (ext === ".stp" || ext === ".step") {
      scfPendingFile = file;
      const qBox = document.getElementById("scfFbxQuality");
      qBox.style.display = "";
      document.querySelectorAll(".scfQSize").forEach(el => { el.textContent = " (počítám…)"; });
      statusEl.textContent = "Počítám náhled velikostí pro 3 stupně kvality…";
      const fd = new FormData();
      fd.append("file", file);
      try {
        const r = await fetch("/api/admin/step-quality-preview", { method: "POST", body: fd });
        const data = await r.json();
        if (!r.ok) {
          statusEl.textContent = "Chyba náhledu: " + (data.error || "selhalo");
          document.querySelectorAll(".scfQSize").forEach(el => { el.textContent = ""; });
        } else {
          const q = data.qualities || {};
          document.querySelectorAll(".scfQSize").forEach(el => {
            const info = q[el.dataset.q];
            el.textContent = info && info.ok ? ` (${info.size_kb} kB)` : (info ? " (chyba náhledu)" : "");
          });
          statusEl.textContent = "Vyberte kvalitu a potvrďte nahrání.";
        }
      } catch (err) {
        statusEl.textContent = "Chyba náhledu: " + err.message;
        document.querySelectorAll(".scfQSize").forEach(el => { el.textContent = ""; });
      }
    } else {
      // FBX nema volbu kvality - rovnou nahrat jako drive.
      document.getElementById("scfFbxQuality").style.display = "none";
      await scfDoUpload(file, null);
    }
  });

  document.getElementById("scfFbxConfirm").onclick = async () => {
    if (!scfPendingFile) return;
    const checked = document.querySelector('input[name="scfQuality"]:checked');
    await scfDoUpload(scfPendingFile, checked ? checked.value : "medium");
  };
  document.getElementById("scfFbxCancel").onclick = () => {
    scfPendingFile = null;
    document.getElementById("scfFbxQuality").style.display = "none";
    document.getElementById("scfFbxInput").value = "";
    document.getElementById("scfFbxStatus").textContent = renderFbxStatus(sp);
  };

  const imgBox = document.getElementById("stockCardImages");
  const imgSection = document.getElementById("stockCardImagesSection");
  if (Array.isArray(sp.images) && sp.images.length) {
    imgSection.style.display = "";
    imgBox.innerHTML = sp.images.map(url => `<a href="${url}" target="_blank"><img src="${url}" loading="lazy" style="width:72px;height:72px;object-fit:cover;border-radius:6px;border:1px solid var(--sc-stat-border);"></a>`).join("");
  } else {
    imgSection.style.display = "none";
    imgBox.innerHTML = "";
  }
  renderGalleryModule(document.getElementById("stockCardGallery"), "product", product.id);

  const tbody = document.getElementById("stockCardTbody");
  if (!data.movements.length) {
    tbody.innerHTML = '<tr><td colspan="8" style="color:#666;">Zatím žádné pohyby.</td></tr>';
    document.getElementById("stockCardFooter").innerHTML = "";
    return;
  }

  // Pruzny zustatek (running balance) - movements chodi serazene DESC
  // (nejnovejsi prvni), takze zacneme od AKTUALNIHO stavu skladu a jdeme
  // pozpatku: "stav po pohybu" nejnovejsiho radku = aktualni stav; pro
  // kazdy dalsi (starsi) radek odecteme/pricteme efekt toho NOVEJSIHO,
  // ktery uz jsme prosli.
  let runningAfter = stockQty;
  const rows = data.movements.map(m => {
    const afterThis = runningAfter;
    const beforeThis = m.movement_type === "receipt" ? afterThis - m.qty : afterThis + m.qty;
    runningAfter = beforeThis;
    return { m, afterThis };
  });

  let totalReceipt = 0, totalIssue = 0;
  tbody.innerHTML = rows.map(({ m, afterThis }) => {
    const date = new Date(m.created_at).toLocaleString("cs-CZ");
    const typeLabel = m.movement_type === "receipt"
      ? `<span class="sc-mv-receipt">+ Příjem</span>`
      : `<span class="sc-mv-issue">− Výdej</span>`;
    if (m.movement_type === "receipt") totalReceipt += m.qty; else totalIssue += m.qty;
    const who = m.user_name || m.user_email || "";
    return `<tr>
      <td>${date}</td>
      <td>${typeLabel}</td>
      <td>${m.qty}</td>
      <td>${afterThis} ${product.unit}</td>
      <td>${m.unit_price_czk != null ? m.unit_price_czk.toLocaleString("cs-CZ") + " Kč" : ""}</td>
      <td>${escapeHtmlAdmin(m.document_number || "")}</td>
      <td>${escapeHtmlAdmin(m.note || "")}</td>
      <td>${escapeHtmlAdmin(who)}</td>
    </tr>`;
  }).join("");

  document.getElementById("stockCardFooter").innerHTML =
    `<span>Pohybů: <b>${data.movements.length}</b></span>` +
    `<span>Celkem přijato: <b>${totalReceipt} ${product.unit}</b></span>` +
    `<span>Celkem vydáno: <b>${totalIssue} ${product.unit}</b></span>` +
    `<span>Bilance: <b>${totalReceipt - totalIssue >= 0 ? "+" : ""}${totalReceipt - totalIssue} ${product.unit}</b></span>`;
}

document.getElementById("stockCardClose").onclick = () => {
  document.getElementById("stockCardModal").classList.remove("open");
  scDisposeViewer3D();
};
document.getElementById("stockCardCloseX").onclick = () => {
  document.getElementById("stockCardModal").classList.remove("open");
  scDisposeViewer3D();
};

// Robert 2026-08-08: "skladové karty se skládají z různých částí,
// velikost karty na obrazovce roste - rozdělme to na záložky" - stejny
// vzor jako #catEditModal (viz cemSwitchTab), jen sc- prefix. Obsah
// vsech zalozek zustava porad v DOM (jen [hidden]), takze
// document.getElementById uvnitr openStockCardModal funguje beze zmeny
// i pro pole ve prave neaktivni zalozce (napr. "Uložit změny").
let sc3dBuiltForParts = null; // reference na parts[], pro ktere uz viewer stoji (nestavet znovu pri pouhem prepnuti tam-zpet)
function scSwitchTab(tabName) {
  document.querySelectorAll("#stockCardModalBox .sc-tab").forEach(b => b.classList.toggle("active", b.dataset.tab === tabName));
  document.querySelectorAll("#stockCardModalBox .sc-panel").forEach(p => { p.hidden = p.dataset.panel !== tabName; });
  if (tabName === "model3d") {
    const viewer3dBox = document.getElementById("stockCard3dViewer");
    if (scCurrent3dParts && scCurrent3dParts.length) {
      viewer3dBox.style.display = "";
      if (sc3dBuiltForParts !== scCurrent3dParts) {
        sc3dBuiltForParts = scCurrent3dParts;
        scBuildViewer3D(viewer3dBox, scCurrent3dParts);
      }
    } else {
      viewer3dBox.style.display = "none";
    }
  }
  if (tabName === "varianty") {
    // Lazy jako 3D viewer: nahledy jsou drahe (WebGL + stahovani GLB), takze
    // se stavi az kdyz na zalozku nekdo prepne, ne pri otevreni karty.
    scRenderVariantyPanel();
  }
}
document.querySelectorAll("#stockCardModalBox .sc-tab").forEach(btn => {
  btn.onclick = () => scSwitchTab(btn.dataset.tab);
});

