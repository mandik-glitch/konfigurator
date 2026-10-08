// bot16, 2026-09-26 (Robert: "udelej v adminu poradne rozlozene menu s
// oznacenim kazde casti s barvitkem at je to jasne i malemu decku,
// nastaveni z webu dej pryc") - nahrazuje puvodni #catAdminTreeColors
// panel, ktery byl vlozeny primo do sidebaru vsech 4 e-shop stranek
// (webapp/index.html, category.html, product.html, blok.html - tam ted
// zbyva jen VEREJNA cast: nacteni ulozenych barev + jejich aplikace na
// --cat-tree-* promenne, viz catTreeColorsLoad()/Apply() tam). Editace
// (tenhle soubor) zije jen tady, v panelu "Menu kategorií" - backend
// API (api/cat_tree_colors.py) je beze zmeny, jen misto, odkud se vola.
//
// bot16, 2026-09-26 (Robert dale: "dej vlevo plnohodnotny strom a vpravo
// souvisejici barveni") - #cmpPreview vykresluje SKUTECNY strom kategorii
// (/api/categories, stejny endpoint jako webapp/category.html), ne 5
// rucne vypsanych ukazkovych radku. Barvy se aplikuji jako --cat-tree-*
// CSS promenne primo na #cmpPreview (ne na <html> jako na webu) - viz
// #cmpPreview .cat-tree-* pravidla v <style> admin.html - takze zmena
// tady nemuze uniknout mimo tenhle jeden panel.

const CAT_TREE_COLOR_FIELDS = [
  { field: "bg_rows_hex", cssVar: "--cat-tree-bg-rows", pickerId: "catTreeBgRowsPicker" },
  { field: "bg_open_hex", cssVar: "--cat-tree-bg-open", pickerId: "catTreeBgOpenPicker" },
  { field: "bg_outer_hex", cssVar: "--cat-tree-bg-outer", pickerId: "catTreeBgOuterPicker" },
  { field: "bg_nested_hex", cssVar: "--cat-tree-bg-nested", pickerId: "catTreeBgNestedPicker" },
  { field: "bg_active_hex", cssVar: "--cat-tree-bg-active", pickerId: "catTreeBgActivePicker" },
  { field: "bg_hover_hex", cssVar: "--cat-tree-bg-hover", pickerId: "catTreeBgHoverPicker" },
  { field: "text_rows_hex", cssVar: "--cat-tree-text-rows", pickerId: "catTreeTextRowsPicker" },
  { field: "text_open_hex", cssVar: "--cat-tree-text-open", pickerId: "catTreeTextOpenPicker" },
  { field: "text_outer_hex", cssVar: "--cat-tree-text-outer", pickerId: "catTreeTextOuterPicker" },
  { field: "text_nested_hex", cssVar: "--cat-tree-text-nested", pickerId: "catTreeTextNestedPicker" },
  { field: "text_active_hex", cssVar: "--cat-tree-text-active", pickerId: "catTreeTextActivePicker" },
  { field: "text_hover_hex", cssVar: "--cat-tree-text-hover", pickerId: "catTreeTextHoverPicker" },
];

// Zrcadli appendCatTreeSiblings/buildCatTreeNode z webapp/category.html -
// musi zustat vizualne 1:1 stejne (stejne CSS tridy), jinak by nahled
// lhal o tom, jak strom skutecne vypada. Rozdily oproti webove verzi:
// zadna navigace po kliku na nazev (je to jen nahled, ne skutecna
// stranka) a "aktivni"/"rozbalena" polozka se urcuje tady (cmpDemoState),
// ne podle URL parametru.
function cmpAppendCatTreeSiblings(container, cats, expandedIds, activeId, depth) {
  let prevGroup = null;
  cats.forEach(cat => {
    const group = cat.menu_group_label || null;
    if (group !== prevGroup) {
      const marker = document.createElement("div");
      marker.className = group ? "cat-tree-group-label" : "cat-tree-group-break";
      if (group) marker.textContent = group;
      container.appendChild(marker);
      prevGroup = group;
    }
    container.appendChild(cmpBuildCatTreeNode(cat, expandedIds, activeId, depth));
  });
}

function cmpBuildCatTreeNode(cat, expandedIds, activeId, depth) {
  const hasChildren = !!(cat.children && cat.children.length);
  const startExpanded = hasChildren && expandedIds.has(cat.id);
  const node = document.createElement("div");
  node.className = "cat-tree-node" + (startExpanded ? " is-open" : "");
  node.dataset.depth = depth;

  const row = document.createElement("div");
  row.className = "cat-tree-row";

  const toggle = document.createElement("span");
  toggle.className = "cat-tree-toggle" + (hasChildren ? "" : " spacer");
  toggle.textContent = startExpanded ? "−" : "+";
  row.appendChild(toggle);

  const nameEl = document.createElement("span");
  nameEl.className = "cat-tree-name" + (cat.id === activeId ? " active" : "");
  nameEl.textContent = cat.name;
  row.appendChild(nameEl);

  node.appendChild(row);

  const childrenEl = document.createElement("div");
  childrenEl.className = "cat-tree-children" + (startExpanded ? " expanded" : "");
  cmpAppendCatTreeSiblings(childrenEl, cat.children || [], expandedIds, activeId, depth + 1);
  node.appendChild(childrenEl);

  if (hasChildren) {
    toggle.onclick = () => {
      const expanded = childrenEl.classList.toggle("expanded");
      toggle.textContent = expanded ? "−" : "+";
      node.classList.toggle("is-open", expanded);
    };
  }

  return node;
}

// Najde prvni vetev na 1. urovni, ktera ma vlastni deti - ukazkove
// "rozbaleni" + jeden jeji list jako "aktivni" polozka, at je v nahledu
// videt kazdy vizualni stav najednou (zavrene/otevrene/zanorene/aktivni),
// stejne jako u puvodnich 5 rucne vybranych ukazkovych radku.
function cmpPickDemoState(tree) {
  const branch = tree.find(c => c.children && c.children.length);
  if (!branch) return { expandedIds: new Set(), activeId: null };
  const leaf = branch.children.find(c => !c.children || !c.children.length) || branch.children[0];
  return { expandedIds: new Set([branch.id]), activeId: leaf ? leaf.id : null };
}

function cmpRenderTree(tree) {
  const root = document.getElementById("cmpTreeRoot");
  if (!root) return;
  root.innerHTML = "";
  if (!tree.length) {
    const empty = document.createElement("p");
    empty.className = "cat-empty";
    empty.textContent = "Žádné kategorie.";
    root.appendChild(empty);
    return;
  }
  const { expandedIds, activeId } = cmpPickDemoState(tree);
  cmpAppendCatTreeSiblings(root, tree, expandedIds, activeId, 0);
}

function catmenuApply(state) {
  const root = document.getElementById("cmpPreview");
  if (!root) return;
  CAT_TREE_COLOR_FIELDS.forEach(({ field, cssVar, pickerId }) => {
    const hex = state[field];
    if (hex) root.style.setProperty(cssVar, hex); else root.style.removeProperty(cssVar);
    const picker = document.getElementById(pickerId);
    if (hex && picker && document.activeElement !== picker) picker.value = hex;
  });

  root.style.textTransform = state.caps ? "uppercase" : "";
  const capsToggle = document.getElementById("catTreeCapsToggle");
  if (capsToggle && document.activeElement !== capsToggle) capsToggle.checked = !!state.caps;

  const bw = state.border_width;
  if (bw) root.style.setProperty("--cat-tree-border-width", bw + "px"); else root.style.removeProperty("--cat-tree-border-width");
  const bwPicker = document.getElementById("catTreeBorderWidthPicker");
  const bwVal = document.getElementById("catTreeBorderWidthVal");
  if (bwPicker && document.activeElement !== bwPicker) bwPicker.value = bw || 2;
  if (bwVal) bwVal.textContent = (bw || 2) + "px";

  // bot16, 2026-09-26 (Robert: "ta linka efektova je moc silna, ale
  // porad k ni neni zeslabovac, ten posuvnik se tyka jeste jine linky")
  // - Sila linek vyse meni jen levy prouzek aktivni polozky, tenhle
  // ovladac je pro intenzitu sweep hover efektu (jina "linka").
  const sweepOpacity = state.sweep_opacity;
  if (sweepOpacity) root.style.setProperty("--cat-tree-sweep-opacity", sweepOpacity); else root.style.removeProperty("--cat-tree-sweep-opacity");
  const sweepPicker = document.getElementById("catTreeSweepOpacityPicker");
  const sweepVal = document.getElementById("catTreeSweepOpacityVal");
  if (sweepPicker && document.activeElement !== sweepPicker) sweepPicker.value = sweepOpacity || 1;
  if (sweepVal) sweepVal.textContent = Math.round((sweepOpacity || 1) * 100) + "%";
}

let catmenuState = {};
function catmenuLoad() {
  fetch("/api/categories").then(r => r.ok ? r.json() : { tree: [] })
    .then(d => cmpRenderTree(d.tree || []))
    .catch(() => {});
  fetch("/api/public/cat-tree-colors").then(r => r.ok ? r.json() : {})
    .then(d => { catmenuState = d || {}; catmenuApply(catmenuState); })
    .catch(() => {});
}
catmenuLoad();

let catmenuSaveTimer = null;
function catmenuSave(patch) {
  const msg = document.getElementById("catTreeColorsMsg");
  if (msg) msg.textContent = "ukládám…";
  clearTimeout(catmenuSaveTimer);
  catmenuSaveTimer = setTimeout(() => {
    fetch("/api/admin/cat-tree-colors", {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(patch),
    }).then(r => {
      if (!msg) return;
      if (r.ok) { msg.textContent = "uloženo ✓"; setTimeout(() => { msg.textContent = ""; }, 2000); }
      else msg.textContent = "chyba při ukládání";
    }).catch(() => { if (msg) msg.textContent = "chyba při ukládání"; });
  }, 400);
}

CAT_TREE_COLOR_FIELDS.forEach(({ field, pickerId }) => {
  const picker = document.getElementById(pickerId);
  if (!picker) return;
  picker.addEventListener("input", () => {
    catmenuState[field] = picker.value;
    catmenuApply(catmenuState);
    catmenuSave({ [field]: picker.value });
  });
});

const catTreeBorderWidthPicker = document.getElementById("catTreeBorderWidthPicker");
if (catTreeBorderWidthPicker) catTreeBorderWidthPicker.addEventListener("input", () => {
  const bw = parseInt(catTreeBorderWidthPicker.value, 10);
  catmenuState.border_width = bw;
  catmenuApply(catmenuState);
  catmenuSave({ border_width: bw });
});

const catTreeSweepOpacityPicker = document.getElementById("catTreeSweepOpacityPicker");
if (catTreeSweepOpacityPicker) catTreeSweepOpacityPicker.addEventListener("input", () => {
  const sv = parseFloat(catTreeSweepOpacityPicker.value);
  catmenuState.sweep_opacity = sv;
  catmenuApply(catmenuState);
  catmenuSave({ sweep_opacity: sv });
});

const catTreeCapsToggle = document.getElementById("catTreeCapsToggle");
if (catTreeCapsToggle) catTreeCapsToggle.addEventListener("change", () => {
  catmenuState.caps = catTreeCapsToggle.checked;
  catmenuApply(catmenuState);
  catmenuSave({ caps: catTreeCapsToggle.checked });
});

const catTreeColorsReset = document.getElementById("catTreeColorsReset");
if (catTreeColorsReset) catTreeColorsReset.addEventListener("click", () => {
  catmenuState = {};
  catmenuApply({});
  clearTimeout(catmenuSaveTimer);
  const clearPatch = { caps: false, border_width: null, sweep_opacity: null };
  CAT_TREE_COLOR_FIELDS.forEach(({ field }) => { clearPatch[field] = null; });
  const msg = document.getElementById("catTreeColorsMsg");
  if (msg) msg.textContent = "ukládám…";
  fetch("/api/admin/cat-tree-colors", {
    method: "PUT", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(clearPatch),
  }).then(r => {
    if (!msg) return;
    if (r.ok) { msg.textContent = "vráceno na výchozí ✓"; setTimeout(() => { msg.textContent = ""; }, 2000); }
    else msg.textContent = "chyba při ukládání";
  }).catch(() => { if (msg) msg.textContent = "chyba při ukládání"; });
});
