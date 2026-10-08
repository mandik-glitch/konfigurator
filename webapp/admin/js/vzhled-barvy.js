// --- Barevne schema (svetly/tmavy motiv admin panelu) - task #66.
// localStorage drzi hodnotu jen pro okamzite prekresleni pred nactenim
// /api/auth/me; jakmile prijde odpoved serveru, theme_admin z app_users
// je autoritativni (a localStorage se s ni srovna) - takze si uzivatel
// odnese sve nastaveni i na jiny pocitac/prohlizec po prihlaseni.
// ==================== NASTAVITELNE BARVY (task #69) ====================
// Barvy nejsou uz napevno v CSS - GET /api/theme-colors vraci obe palety
// (dark/light), applyThemeColorVars() je prepise jako inline CSS
// promenne (--jmeno) na <html>, coz ma prednost pred statickymi :root /
// [data-theme] pravidly ve stylesheetu (ta zustavaji jen jako fallback,
// dokud fetch nedobehne / pri chybe site).
const THEME_COLOR_DEFAULTS = {
  dark: {
    bg: "#1b1e24", panel_bg: "#22262e", panel_bg_alt: "#1a1d23",
    border: "#3a3f4a", border_soft: "#333333", border_soft2: "#2c313a", border_faint: "#2a2e36",
    text: "#e8eaed", text2: "#c7ccd4", text_muted: "#8b93a1", text_faint: "#6f7684",
    accent: "#9fd0ff", accent_focus: "#6fa8ff",
    btn_bg: "#3a5a7a", btn_bg_hover: "#4a6a8a", btn_danger: "#7a3a3a", btn_danger_hover: "#8a4a4a",
    error: "#e07070", success: "#7ed49a", warn: "#e0a070",
    row_dirty_bg: "#26303c",
    support_bubble_bg: "#3a4049", support_ai_bubble_bg: "#3a3560", support_ai_text: "#e0d4ff",
    thumb_bg: "#111111",
    sc_stat_bg: "#1a1d23", sc_stat_border: "#2c313a",
    sc_section_header: "#8b93a1", sc_table_header_bg: "#1a1d23",
  },
  light: {
    bg: "#eef1f5", panel_bg: "#ffffff", panel_bg_alt: "#f3f5f8",
    border: "#d7dce3", border_soft: "#e3e7ec", border_soft2: "#dde2e8", border_faint: "#e6e9ee",
    text: "#1b1e24", text2: "#3a3f4a", text_muted: "#5c6570", text_faint: "#97a0ab",
    accent: "#1a6fd4", accent_focus: "#2d6cdf",
    btn_bg: "#2f6690", btn_bg_hover: "#3a76a0", btn_danger: "#b23b3b", btn_danger_hover: "#c24b4b",
    error: "#c23b3b", success: "#2f9e5c", warn: "#b8721f",
    row_dirty_bg: "#eaf2fb",
    support_bubble_bg: "#eceff2", support_ai_bubble_bg: "#ece7fb", support_ai_text: "#4a3f7a",
    thumb_bg: "#dfe3e8",
    sc_stat_bg: "#f3f5f8", sc_stat_border: "#dde2e8",
    sc_section_header: "#5c6570", sc_table_header_bg: "#f3f5f8",
  },
};

// --- Přednastavené motivy (Robert, 2026-07-26: "udělej navíc nějaké
// další 2 barevné motivy, rozumně příjemné") - rychlý start navrch k
// výchozímu tmavému/světlému motivu, který si Robert nadále může
// libovolně doladit v tabulce níže. Jen frontendová konstanta - aplikace
// zkopíruje dark+light do právě editovaného povrchu, uloží se až
// kliknutím na "Uložit barvy" (žádná nová serverová logika).
// Robert 2026-07-26: "udelej ty schemata barev editovatelne" - drive
// byl tenhle seznam natvrdo v JS a slo jen "pouzit" (zkopirovat).
// DEFAULT_PRESET_THEMES je ted uz jen SEED/fallback - autoritativni
// seznam zije v DB (app_settings.theme_presets) a nacita se pres
// loadThemePresets() do window.__themePresets, ktere renderThemePresets()
// skutecne vykresluje. Pokud fetch selze (offline/chyba), pouzije se
// tento fallback, aby editor barev nezustal prazdny.
const DEFAULT_PRESET_THEMES = [
  {
    // Robert poslal 5 barev jako svatch (#000000, #666666, #979797,
    // #EEEEEE, #0088CC) a napsal "a toto schema pridej" - cerno-sedo-modry
    // minimalisticky kontrastni motiv.
    id: "blackblue",
    name: "Černo-modrá",
    dark: {
      bg: "#000000", panel_bg: "#1c1c1c", panel_bg_alt: "#141414",
      border: "#666666", border_soft: "#4d4d4d", border_soft2: "#333333", border_faint: "#262626",
      text: "#eeeeee", text2: "#cfcfcf", text_muted: "#979797", text_faint: "#6e6e6e",
      accent: "#0088cc", accent_focus: "#1a9ddb",
      btn_bg: "#0088cc", btn_bg_hover: "#1a9ddb", btn_danger: "#7a3a3a", btn_danger_hover: "#8a4a4a",
      error: "#e0776a", success: "#7ed49a", warn: "#e0a070",
      row_dirty_bg: "#0d2733",
      support_bubble_bg: "#333333", support_ai_bubble_bg: "#0d2733", support_ai_text: "#bfe3f5",
      thumb_bg: "#000000",
      sc_stat_bg: "#141414", sc_stat_border: "#4d4d4d",
      sc_section_header: "#979797", sc_table_header_bg: "#141414",
    },
    light: {
      bg: "#eeeeee", panel_bg: "#ffffff", panel_bg_alt: "#f5f5f5",
      border: "#979797", border_soft: "#cccccc", border_soft2: "#d9d9d9", border_faint: "#e2e2e2",
      text: "#000000", text2: "#333333", text_muted: "#666666", text_faint: "#979797",
      accent: "#0088cc", accent_focus: "#006fa8",
      btn_bg: "#0088cc", btn_bg_hover: "#006fa8", btn_danger: "#b23b3b", btn_danger_hover: "#c24b4b",
      error: "#b8422f", success: "#4f8a3d", warn: "#a06b1c",
      row_dirty_bg: "#e0f0fa",
      support_bubble_bg: "#f5f5f5", support_ai_bubble_bg: "#e0f0fa", support_ai_text: "#004a70",
      thumb_bg: "#d9d9d9",
      sc_stat_bg: "#f5f5f5", sc_stat_border: "#cccccc",
      sc_section_header: "#666666", sc_table_header_bg: "#f5f5f5",
    },
  },
  {
    // Robert poslal screenshot ciziho webu (Masaze Royal - cerne pozadi,
    // zlaty/kremovy akcent, elegantni luxusni styl) a napsal "pridej mi
    // tam toto schema barev" - odvozeno z toho screenshotu.
    id: "royal",
    name: "Royal (černo-zlatá)",
    dark: {
      bg: "#1a1512", panel_bg: "#241d18", panel_bg_alt: "#1f1915",
      border: "#3a2f22", border_soft: "#332921", border_soft2: "#2c2419", border_faint: "#251f17",
      text: "#ede4d3", text2: "#cbbfa8", text_muted: "#a89882", text_faint: "#7d7062",
      accent: "#c9a227", accent_focus: "#d4af37",
      btn_bg: "#9c7a28", btn_bg_hover: "#b38f34", btn_danger: "#7a3a3a", btn_danger_hover: "#8a4a4a",
      error: "#e0776a", success: "#8fbf7a", warn: "#d4af37",
      row_dirty_bg: "#332619",
      support_bubble_bg: "#332921", support_ai_bubble_bg: "#3a2e1a", support_ai_text: "#e8d4a0",
      thumb_bg: "#120e0b",
      sc_stat_bg: "#1f1915", sc_stat_border: "#3a2f22",
      sc_section_header: "#a89882", sc_table_header_bg: "#1f1915",
    },
    light: {
      bg: "#f7f1e6", panel_bg: "#ffffff", panel_bg_alt: "#f3ead8",
      border: "#ddcba0", border_soft: "#e8ddc4", border_soft2: "#e2d4b4", border_faint: "#ece2cc",
      text: "#241d15", text2: "#4a3d2a", text_muted: "#6d5d45", text_faint: "#9c8d72",
      accent: "#a9822a", accent_focus: "#8a6a1f",
      btn_bg: "#a9822a", btn_bg_hover: "#8a6a1f", btn_danger: "#b23b3b", btn_danger_hover: "#c24b4b",
      error: "#b8422f", success: "#4f8a3d", warn: "#a06b1c",
      row_dirty_bg: "#f5e9cc",
      support_bubble_bg: "#efe4cc", support_ai_bubble_bg: "#f0e2b8", support_ai_text: "#6b4f23",
      thumb_bg: "#e6d8b8",
      sc_stat_bg: "#f3ead8", sc_stat_border: "#e2d4b4",
      sc_section_header: "#6d5d45", sc_table_header_bg: "#f3ead8",
    },
  },
  {
    id: "modern",
    name: "Moderní",
    dark: {
      bg: "#14161a", panel_bg: "#1c1f26", panel_bg_alt: "#171a20",
      border: "#2c313a", border_soft: "#262a32", border_soft2: "#22262d", border_faint: "#1e2127",
      text: "#f0f2f5", text2: "#c9ced6", text_muted: "#8b93a1", text_faint: "#5f6672",
      accent: "#6d8cff", accent_focus: "#8aa3ff",
      btn_bg: "#4f63d2", btn_bg_hover: "#5f74e0", btn_danger: "#d1495b", btn_danger_hover: "#e0596b",
      error: "#f26d7d", success: "#4ade9a", warn: "#f0b429",
      row_dirty_bg: "#232a3a",
      support_bubble_bg: "#262a32", support_ai_bubble_bg: "#262038", support_ai_text: "#d8ccff",
      thumb_bg: "#101216",
    },
    light: {
      bg: "#f7f8fa", panel_bg: "#ffffff", panel_bg_alt: "#f2f4f7",
      border: "#e2e5eb", border_soft: "#ebedf1", border_soft2: "#e6e9ee", border_faint: "#eef0f3",
      text: "#16181d", text2: "#3d4148", text_muted: "#6b7280", text_faint: "#9aa0ab",
      accent: "#4f63d2", accent_focus: "#3f52c2",
      btn_bg: "#4f63d2", btn_bg_hover: "#3f52c2", btn_danger: "#d1495b", btn_danger_hover: "#c13a4c",
      error: "#d1495b", success: "#16a374", warn: "#d18f1a",
      row_dirty_bg: "#eef0fc",
      support_bubble_bg: "#f2f4f7", support_ai_bubble_bg: "#ede9fe", support_ai_text: "#5b3fa8",
      thumb_bg: "#e9ebef",
    },
  },
  {
    id: "copper",
    name: "Měď a grafit",
    dark: {
      bg: "#201d1a", panel_bg: "#2b2622", panel_bg_alt: "#221e1b",
      border: "#4a3f36", border_soft: "#3a332c", border_soft2: "#332e28", border_faint: "#2e2924",
      text: "#ece6df", text2: "#cdc3b8", text_muted: "#a3968a", text_faint: "#7d7168",
      accent: "#d68a4c", accent_focus: "#e2a06a",
      btn_bg: "#8a5a35", btn_bg_hover: "#a06a40", btn_danger: "#7a3a3a", btn_danger_hover: "#8a4a4a",
      error: "#e0776a", success: "#8fbf7a", warn: "#e0a95c",
      row_dirty_bg: "#362b1f",
      support_bubble_bg: "#3a332c", support_ai_bubble_bg: "#3a2e22", support_ai_text: "#e8c9a0",
      thumb_bg: "#17140f",
    },
    light: {
      bg: "#f4efe8", panel_bg: "#ffffff", panel_bg_alt: "#f7f2ea",
      border: "#ddd1c0", border_soft: "#e8dfd1", border_soft2: "#e2d7c6", border_faint: "#ece4d8",
      text: "#241f1a", text2: "#4a3f34", text_muted: "#6d6052", text_faint: "#9c9182",
      accent: "#b5651f", accent_focus: "#c9762c",
      btn_bg: "#9c5f2e", btn_bg_hover: "#ac6f3c", btn_danger: "#b23b3b", btn_danger_hover: "#c24b4b",
      error: "#b8422f", success: "#4f8a3d", warn: "#a06b1c",
      row_dirty_bg: "#f5e6d3",
      support_bubble_bg: "#efe6d9", support_ai_bubble_bg: "#f0e2cc", support_ai_text: "#6b4423",
      thumb_bg: "#e6dbc9",
    },
  },
  {
    id: "forest",
    name: "Lesní zeleň",
    dark: {
      bg: "#1a1f1c", panel_bg: "#212823", panel_bg_alt: "#1b211d",
      border: "#3a453d", border_soft: "#313a34", border_soft2: "#2b332e", border_faint: "#262d29",
      text: "#e6ece7", text2: "#c4d0c6", text_muted: "#8fa091", text_faint: "#6f7d71",
      accent: "#7fbf8a", accent_focus: "#98d1a2",
      btn_bg: "#3f6b4d", btn_bg_hover: "#4d7d5c", btn_danger: "#7a3a3a", btn_danger_hover: "#8a4a4a",
      error: "#e0776a", success: "#7ed49a", warn: "#e0c070",
      row_dirty_bg: "#26312a",
      support_bubble_bg: "#313a34", support_ai_bubble_bg: "#2a3830", support_ai_text: "#cfe8d4",
      thumb_bg: "#12160f",
    },
    light: {
      bg: "#eef3ee", panel_bg: "#ffffff", panel_bg_alt: "#f3f7f3",
      border: "#d3ded5", border_soft: "#e0e9e1", border_soft2: "#d9e3da", border_faint: "#e5ede6",
      text: "#1c231e", text2: "#3c463e", text_muted: "#5e6b60", text_faint: "#93a196",
      accent: "#2f7d47", accent_focus: "#388c52",
      btn_bg: "#2f6b45", btn_bg_hover: "#3a7b52", btn_danger: "#b23b3b", btn_danger_hover: "#c24b4b",
      error: "#c23b3b", success: "#2f9e5c", warn: "#b8721f",
      row_dirty_bg: "#e5f0e6",
      support_bubble_bg: "#eaf1eb", support_ai_bubble_bg: "#e3f0e5", support_ai_text: "#234a30",
      thumb_bg: "#dbe6dc",
    },
  },
  // Robert 2026-08-07 (screenshot "Můj počítač" - tmave pozadi + fialovo-
  // purpurove neonove prstence + zeleny zvyraznujici text): "udělej nový
  // barevný motiv v tomto duchu pro eshop i administraci". Stejna paleta
  // jako DEFAULT_THEME_PRESETS v api/app.py (drz synchronizovane).
  {
    id: "neon",
    name: "Neon (fialovo-purpurová)",
    dark: {
      bg: "#0d0b14", panel_bg: "#1a1626", panel_bg_alt: "#150f1f",
      border: "#3d2f52", border_soft: "#2c2138", border_soft2: "#241b30", border_faint: "#1e1628",
      text: "#f2eef9", text2: "#d4c9e8", text_muted: "#9d8bb8", text_faint: "#6e5c88",
      accent: "#c04cff", accent_focus: "#e879f9",
      btn_bg: "#8b2fd9", btn_bg_hover: "#a855f7", btn_danger: "#c2255c", btn_danger_hover: "#d63384",
      error: "#ff5c8a", success: "#39e88f", warn: "#ffb84d",
      row_dirty_bg: "#2a1c3d",
      support_bubble_bg: "#2c2138", support_ai_bubble_bg: "#3d1f52", support_ai_text: "#f0d9ff",
      thumb_bg: "#0a0812",
      sc_stat_bg: "#1a1626", sc_stat_border: "#3d2f52",
      sc_section_header: "#9d8bb8", sc_table_header_bg: "#1a1626",
    },
    light: {
      bg: "#f5f0fb", panel_bg: "#ffffff", panel_bg_alt: "#f0e8fa",
      border: "#d9c2f0", border_soft: "#e6d7f5", border_soft2: "#ddc9f2", border_faint: "#ede0f9",
      text: "#1e1330", text2: "#4a3566", text_muted: "#7a638f", text_faint: "#a893bd",
      accent: "#a020c9", accent_focus: "#8b13ad",
      btn_bg: "#9333ea", btn_bg_hover: "#7e22ce", btn_danger: "#c2255c", btn_danger_hover: "#a8134a",
      error: "#c2255c", success: "#16a34a", warn: "#c2760a",
      row_dirty_bg: "#f0e0fa",
      support_bubble_bg: "#f0e8fa", support_ai_bubble_bg: "#ecdcfa", support_ai_text: "#5b2380",
      thumb_bg: "#e6d7f5",
      sc_stat_bg: "#f0e8fa", sc_stat_border: "#ddc9f2",
      sc_section_header: "#7a638f", sc_table_header_bg: "#f0e8fa",
    },
  },
];

// window.__themePresets = aktualne nacteny/editovany seznam presetu
// (pole objektu {id,name,dark,light}), autoritativni zdroj pro
// renderThemePresets/applyThemePreset/toggleEditPreset/atd.
// window.__editingPresetId != null znamena, ze se prave edituje jeden
// konkretni preset (ne zivy povrch) - Ulozit barvy pak posila CELY
// seznam presetu na server. window.__expandedCardId drzi, ktera karta
// (id presetu, nebo "__current__" pro zivou paletu povrchu) je prave
// rozbalena - Robert 2026-07-26: "ty kalamáře chci nahoře na
// schematech ne dole v tabulce" - editace barev uz NENI ve sdilene
// tabulce, ale primo rozbalena uvnitr prislusne karty nahore.
window.__themePresets = null;
window.__editingPresetId = null;
window.__expandedCardId = null;

async function loadThemePresets() {
  try {
    const r = await fetch("/api/admin/theme-presets");
    const data = await r.json();
    window.__themePresets = Array.isArray(data.presets) && data.presets.length
      ? data.presets
      : JSON.parse(JSON.stringify(DEFAULT_PRESET_THEMES));
  } catch (e) {
    window.__themePresets = JSON.parse(JSON.stringify(DEFAULT_PRESET_THEMES));
  }
}

async function saveThemePresetsList() {
  const err = document.getElementById("themeColorsErr");
  if (err) err.textContent = "";
  try {
    const r = await fetch("/api/admin/theme-presets", {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ presets: window.__themePresets }),
    });
    if (!r.ok) {
      const d = await r.json().catch(() => ({}));
      throw new Error(d.error || ("HTTP " + r.status));
    }
    return true;
  } catch (e) {
    if (err) err.textContent = "chyba uložení motivů: " + e.message;
    return false;
  }
}

function renderThemePresets() {
  const row = document.getElementById("themePresetsRow");
  if (!row) return;
  const presets = window.__themePresets || DEFAULT_PRESET_THEMES;
  const swatchKeys = ["bg", "panel_bg", "accent", "btn_bg", "text"];
  const isAdmin = window.__themeEditorSurface === "admin";
  const currentPalette = isAdmin ? window.__themeColors : window.__themeColorsEshop;
  const currentLabel = isAdmin ? "administrace" : "zákaznického e-shopu";

  const cards = [];

  // "Aktualni barvy" - vzdy prvni karta, needituje preset ale primo
  // zivou paletu prave vybraneho povrchu (Administrace/Zakaznicky
  // e-shop). Neni to preset - nema Pouzit/Prejmenovat/Smazat, jen
  // Upravit (rozbali kalamare primo v karte) a Vratit na vychozi.
  if (currentPalette) {
    const curExpanded = window.__expandedCardId === "__current__";
    const curSwatches = swatchKeys.map(k => '<span style="background:' + (currentPalette.dark[k] || "#000") + ';"></span>').join("");
    cards.push(
      '<div class="theme-preset-card theme-preset-card-current' + (curExpanded ? ' expanded editing' : '') + '" data-card-id="__current__">'
      + '<div class="theme-preset-swatches">' + curSwatches + '</div>'
      + '<div class="theme-preset-name">Aktuální barvy ' + currentLabel + (curExpanded ? ' (upravuje se)' : '') + '</div>'
      + '<div class="theme-preset-actions">'
      + '<button type="button" data-act="edit-current">' + (curExpanded ? "Zavřít" : "Upravit") + '</button>'
      + (curExpanded ? "" : '<button type="button" data-act="reset-current">Vrátit na výchozí</button>')
      + '</div>'
      + (curExpanded ? '<div class="cp-inline-mount"></div>' : '')
      + '</div>'
    );
  }

  presets.forEach(p => {
    const isEditing = window.__editingPresetId === p.id;
    const swatches = swatchKeys.map(k => '<span style="background:' + (p.dark[k] || "#000") + ';"></span>').join("");
    cards.push(
      '<div class="theme-preset-card' + (isEditing ? ' expanded editing' : '') + '" data-card-id="' + p.id + '" data-preset-card="' + p.id + '">'
      + '<div class="theme-preset-swatches">' + swatches + '</div>'
      + '<div class="theme-preset-name">' + p.name + (isEditing ? ' (upravuje se)' : '') + '</div>'
      + (isEditing ? "" : '<button type="button" class="theme-preset-apply" data-act="apply" data-preset="' + p.id + '">Použít</button>')
      + '<div class="theme-preset-actions">'
      + '<button type="button" data-act="edit" data-preset="' + p.id + '">' + (isEditing ? "Zavřít" : "Upravit") + '</button>'
      + '<button type="button" data-act="rename" data-preset="' + p.id + '">Přejmenovat</button>'
      + '<button type="button" class="theme-preset-delete" data-act="delete" data-preset="' + p.id + '">Smazat</button>'
      + '</div>'
      + (isEditing ? '<div class="cp-inline-mount"></div>' : '')
      + '</div>'
    );
  });

  row.innerHTML = cards.join("")
    + '<div class="theme-preset-card-new"><button type="button" id="btnAddThemePreset">+ Nový motiv</button></div>';

  row.querySelectorAll("[data-act]").forEach(btn => {
    const id = btn.dataset.preset;
    const act = btn.dataset.act;
    if (act === "apply") btn.onclick = () => applyThemePreset(id);
    else if (act === "edit") btn.onclick = () => toggleEditPreset(id);
    else if (act === "rename") btn.onclick = () => renamePreset(id);
    else if (act === "delete") btn.onclick = () => deletePreset(id);
    else if (act === "edit-current") btn.onclick = () => toggleEditCurrentSurface();
    else if (act === "reset-current") btn.onclick = () => resetCurrentSurfaceColors();
  });
  const addBtn = document.getElementById("btnAddThemePreset");
  if (addBtn) addBtn.onclick = addNewPreset;

  // Pokud je nejaka karta prave rozbalena, namontuj do ni inline
  // editor barev (kalamare + skala) - viz _mountInlineColorEditor.
  if (window.__expandedCardId) {
    const mount = row.querySelector('.theme-preset-card[data-card-id="' + window.__expandedCardId + '"] .cp-inline-mount');
    if (mount) _mountInlineColorEditor(mount);
  }
}

async function applyThemePreset(presetId) {
  const presets = window.__themePresets || DEFAULT_PRESET_THEMES;
  const preset = presets.find(p => p.id === presetId);
  if (!preset) return;
  const label = window.__themeEditorSurface === "admin" ? "administrace" : "zákaznického e-shopu";
  if (!confirm('Aplikovat motiv "' + preset.name + '" na barvy ' + label + '? Přepíše a rovnou uloží aktuální barvy.')) return;
  window.__editingPresetId = null;
  window.__expandedCardId = null;
  const target = window.__themeEditorSurface === "admin"
    ? window.__themeColors
    : (window.__themeColorsEshop || (window.__themeColorsEshop = { dark: {}, light: {} }));
  target.dark = JSON.parse(JSON.stringify(preset.dark));
  target.light = JSON.parse(JSON.stringify(preset.light));
  if (window.__themeEditorSurface === "admin") {
    applyThemeColorVars(document.documentElement.getAttribute("data-theme") || "dark");
  }
  renderThemePresets();
  const ok = await _saveCurrentSurfaceColors();
  const status = document.getElementById("themeColorsStatus");
  if (status) {
    status.textContent = ok ? "motiv aplikován a uložen ✓" : "";
    if (ok) setTimeout(() => { status.textContent = ""; }, 3000);
  }
}

// Rozbaleni/zabaleni editace jedne konkretni karty - preset, nebo
// "__current__" pro zivou paletu povrchu (viz toggleEditCurrentSurface).
// Jen jedna karta muze byt rozbalena naraz.
function toggleEditPreset(presetId) {
  if (window.__editingPresetId === presetId) {
    window.__editingPresetId = null;
    window.__expandedCardId = null;
    renderThemePresets();
    return;
  }
  const presets = window.__themePresets || DEFAULT_PRESET_THEMES;
  const preset = presets.find(p => p.id === presetId);
  if (!preset) return;
  window.__editingPresetId = presetId;
  window.__expandedCardId = presetId;
  window.__themeEditorColors = preset;
  renderThemePresets();
}

function toggleEditCurrentSurface() {
  if (window.__expandedCardId === "__current__") {
    window.__expandedCardId = null;
    renderThemePresets();
    return;
  }
  window.__editingPresetId = null;
  window.__expandedCardId = "__current__";
  window.__themeEditorColors = window.__themeEditorSurface === "admin" ? window.__themeColors : window.__themeColorsEshop;
  renderThemePresets();
}

function resetCurrentSurfaceColors() {
  const label = window.__themeEditorSurface === "admin" ? "administrace" : "zákaznického e-shopu";
  if (!confirm('Vrátit obě palety (' + label + ') na výchozí barvy? Uloží se ihned.')) return;
  const fresh = JSON.parse(JSON.stringify(THEME_COLOR_DEFAULTS));
  if (window.__themeEditorSurface === "admin") {
    window.__themeColors = fresh;
  } else {
    window.__themeColorsEshop = fresh;
  }
  if (window.__expandedCardId === "__current__") {
    window.__themeEditorColors = window.__themeEditorSurface === "admin" ? window.__themeColors : window.__themeColorsEshop;
  }
  if (window.__themeEditorSurface === "admin") {
    applyThemeColorVars(document.documentElement.getAttribute("data-theme") || "dark");
  }
  renderThemePresets();
  _saveCurrentSurfaceColors();
}

async function renamePreset(presetId) {
  const presets = window.__themePresets || DEFAULT_PRESET_THEMES;
  const preset = presets.find(p => p.id === presetId);
  if (!preset) return;
  const name = prompt("Nový název motivu:", preset.name);
  if (!name || !name.trim()) return;
  preset.name = name.trim();
  renderThemePresets();
  const ok = await saveThemePresetsList();
  const status = document.getElementById("themeColorsStatus");
  if (status) {
    status.textContent = ok ? "přejmenováno ✓" : "";
    if (ok) setTimeout(() => { status.textContent = ""; }, 2000);
  }
}

async function deletePreset(presetId) {
  const presets = window.__themePresets || DEFAULT_PRESET_THEMES;
  const preset = presets.find(p => p.id === presetId);
  if (!preset) return;
  if (!confirm('Opravdu smazat motiv "' + preset.name + '"? Tuto akci nelze vrátit zpět.')) return;
  window.__themePresets = presets.filter(p => p.id !== presetId);
  if (window.__editingPresetId === presetId) {
    window.__editingPresetId = null;
    window.__expandedCardId = null;
  }
  renderThemePresets();
  const ok = await saveThemePresetsList();
  const status = document.getElementById("themeColorsStatus");
  if (status) {
    status.textContent = ok ? "smazáno ✓" : "";
    if (ok) setTimeout(() => { status.textContent = ""; }, 2000);
  }
}

async function addNewPreset() {
  const name = prompt("Název nového motivu:", "Nový motiv");
  if (!name || !name.trim()) return;
  const base = window.__themeEditorSurface === "admin" ? window.__themeColors : window.__themeColorsEshop;
  const preset = {
    id: "custom_" + Date.now(),
    name: name.trim(),
    dark: JSON.parse(JSON.stringify(base.dark)),
    light: JSON.parse(JSON.stringify(base.light)),
  };
  if (!window.__themePresets) window.__themePresets = JSON.parse(JSON.stringify(DEFAULT_PRESET_THEMES));
  window.__themePresets.push(preset);
  const ok = await saveThemePresetsList();
  const status = document.getElementById("themeColorsStatus");
  if (status) {
    status.textContent = ok ? "motiv vytvořen ✓" : "";
    if (ok) setTimeout(() => { status.textContent = ""; }, 2000);
  }
  toggleEditPreset(preset.id);
}

const THEME_COLOR_FIELDS = [
  { group: "Pozadí a panely" },
  { key: "bg", label: "Pozadí okna" },
  { key: "panel_bg", label: "Pozadí panelu" },
  { key: "panel_bg_alt", label: "Pozadí panelu (alt)" },
  { group: "Ohraničení" },
  { key: "border", label: "Ohraničení" },
  { key: "border_soft", label: "Ohraničení (jemné)" },
  { key: "border_soft2", label: "Ohraničení (jemné 2)" },
  { key: "border_faint", label: "Ohraničení (velmi jemné)" },
  { group: "Text" },
  { key: "text", label: "Text" },
  { key: "text2", label: "Text (sekundární)" },
  { key: "text_muted", label: "Text (tlumený)" },
  { key: "text_faint", label: "Text (velmi tlumený)" },
  { group: "Akcent a tlačítka" },
  { key: "accent", label: "Akcent" },
  { key: "accent_focus", label: "Akcent (focus)" },
  { key: "btn_bg", label: "Tlačítko" },
  { key: "btn_bg_hover", label: "Tlačítko (hover)" },
  { key: "btn_danger", label: "Tlačítko (nebezpečné)" },
  { key: "btn_danger_hover", label: "Tlačítko nebezpečné (hover)" },
  { group: "Stavové barvy" },
  { key: "error", label: "Chyba" },
  { key: "success", label: "Úspěch" },
  { key: "warn", label: "Varování" },
  { key: "row_dirty_bg", label: "Neuložený řádek" },
  { group: "Podpora (chat)" },
  { key: "support_bubble_bg", label: "Bublina zprávy" },
  { key: "support_ai_bubble_bg", label: "Bublina 3Dbot" },
  { key: "support_ai_text", label: "Text 3Dbot" },
  { key: "thumb_bg", label: "Pozadí náhledu" },
  { group: "Skladová karta" },
  { key: "sc_stat_bg", label: "Pozadí dlaždic (SKU, min/max, cena…)" },
  { key: "sc_stat_border", label: "Ohraničení dlaždic" },
  { key: "sc_section_header", label: "Nadpisy sekcí" },
  { key: "sc_table_header_bg", label: "Záhlaví tabulky pohybů" },
];

function applyThemeColorVars(theme) {
  const palette = window.__themeColors && window.__themeColors[theme];
  if (!palette) return;
  Object.keys(palette).forEach(key => {
    document.documentElement.style.setProperty("--" + key.replace(/_/g, "-"), palette[key]);
  });
}

// Robert 2026-07-26: "ikony pro barvy všechny zruš" - dřívější systém
// malých kontextových 🎨 ikonek na každém modálním okně (mountInlineColorIcons/
// PANEL_MODAL_LABELS/INLINE_COLOR_ICONS) byl kompletně odstraněn. Editace
// barev jde nadále jen přes velkou tabulku v záložce Vzhled.

// --- Oddelene povrchy (task #66, Robert: "chci si vse obarvit sam", "admin
// i zakaznicky web, oddelene"). window.__themeColors = paleta ADMIN
// povrchu - pouziva se i pro zive prekresleni admin.html (applyThemeColorVars,
// inline ikonky), takze musi zustat autoritativni pro admin bez ohledu na to,
// jaky povrch je zrovna otevreny ve velke editacni tabulce. Velka tabulka
// (Vzhled) muze editovat i "eshop" povrch - pro ten se drzi samostatny
// window.__themeColorsEshop (nacte se lazy pri prvnim prepnuti). Ktery z
// obou je prave v tabulce, urcuje window.__themeEditorSurface +
// window.__themeEditorColors (reference na jeden z obou objektu vyse).
window.__themeEditorSurface = "admin";
window.__themeEditorColors = null;

// ==================== KALAMAR BAREV (task #100) ====================
// Robert 2026-07-26: "nevím, která barva co znamená ve schématu...
// ideálně kdyby ty ikony barev byly kalamářem, který změním na škále" -
// puvodni holy ctverecek <input type="color"> nerikal nic o tom, co
// prave edituju, a otviral neprehledny nativni OS picker. Misto toho:
// ikona kalamare (barva "inkoustu" = aktualni hodnota) + vodorovna
// barevna skala (duha) vedle ni pro rychlou zmenu odstinu. Klik na
// kalamar otevre popover s 2D plochou sytost/jas + presnym hex polem
// pro doladeni.
function hexToHsl(hex) {
  hex = (hex || "#000000").replace("#", "");
  if (hex.length === 3) hex = hex.split("").map(c => c + c).join("");
  const r = parseInt(hex.substr(0, 2), 16) / 255;
  const g = parseInt(hex.substr(2, 2), 16) / 255;
  const b = parseInt(hex.substr(4, 2), 16) / 255;
  const max = Math.max(r, g, b), min = Math.min(r, g, b);
  let h, s, l = (max + min) / 2;
  if (max === min) {
    h = s = 0;
  } else {
    const d = max - min;
    s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
    switch (max) {
      case r: h = (g - b) / d + (g < b ? 6 : 0); break;
      case g: h = (b - r) / d + 2; break;
      default: h = (r - g) / d + 4; break;
    }
    h /= 6;
  }
  return { h: Math.round(h * 360), s: Math.round(s * 100), l: Math.round(l * 100) };
}

function hslToHex(h, s, l) {
  h = ((h % 360) + 360) % 360;
  s = Math.max(0, Math.min(100, s)) / 100;
  l = Math.max(0, Math.min(100, l)) / 100;
  const c = (1 - Math.abs(2 * l - 1)) * s;
  const x = c * (1 - Math.abs((h / 60) % 2 - 1));
  const m = l - c / 2;
  let r, g, b;
  if (h < 60) { r = c; g = x; b = 0; }
  else if (h < 120) { r = x; g = c; b = 0; }
  else if (h < 180) { r = 0; g = c; b = x; }
  else if (h < 240) { r = 0; g = x; b = c; }
  else if (h < 300) { r = x; g = 0; b = c; }
  else { r = c; g = 0; b = x; }
  const toHex = v => Math.round((v + m) * 255).toString(16).padStart(2, "0");
  return "#" + toHex(r) + toHex(g) + toHex(b);
}

window.__cpState = {};
function _cpKey(mode, key) { return mode + "|" + key; }

function _cpCellHtml(mode, key, hex) {
  const hsl = hexToHsl(hex);
  window.__cpState[_cpKey(mode, key)] = hsl;
  return '<div class="cp-cell" data-mode="' + mode + '" data-key="' + key + '">'
    + '<button type="button" class="cp-inkwell" data-mode="' + mode + '" data-key="' + key + '" title="Doladit barvu (' + hex + ')">'
    + '<svg viewBox="0 0 24 24" class="cp-inkwell-svg">'
    + '<path class="cp-glass" d="M7 3h10l1.2 5.2-2.2 2V19a2 2 0 0 1-2 2H10a2 2 0 0 1-2-2v-8.8l-2.2-2z"/>'
    + '<path class="cp-ink" fill="' + hex + '" d="M7.6 11.2h8.8V19a1 1 0 0 1-1 1H8.6a1 1 0 0 1-1-1z"/>'
    + '<path class="cp-glass-cap" d="M7 3h10l1.2 5.2H5.8z"/>'
    + "</svg>"
    + "</button>"
    + '<input type="range" class="cp-hue" min="0" max="360" value="' + hsl.h + '" data-mode="' + mode + '" data-key="' + key + '">'
    + "</div>";
}

// Robert 2026-07-26: "jak poznám k čemu ta barva patří?" - popisky
// jako "Ohraničení (jemné 2)" samy o sobě neukazuji, co presne v
// rozhrani barvi, a editace presetu se navic zamerne NEpromita do
// zive administrace. CP_PREVIEW_TARGETS mapuje kazdy klic na CSS
// vlastnost (pozadi/text/ohraniceni) malé samostatne makety uvnitr
// rozbalene karty (viz _cpMockupHtml) - makety NEJSOU napojene na
// skutecny dokument, takze funguji stejne pri editaci zive palety
// i presetu.
const CP_PREVIEW_TARGETS = {
  bg: "background", panel_bg: "background", panel_bg_alt: "background",
  border: "border-color", border_soft: "border-color", border_soft2: "border-color", border_faint: "border-color",
  text: "color", text2: "color", text_muted: "color", text_faint: "color",
  accent: "color", accent_focus: "border-color",
  btn_bg: "background", btn_bg_hover: "background", btn_danger: "background", btn_danger_hover: "background",
  error: "color", success: "color", warn: "color",
  row_dirty_bg: "background",
  support_bubble_bg: "background", support_ai_bubble_bg: "background", support_ai_text: "color",
  thumb_bg: "background",
  sc_stat_bg: "background", sc_stat_border: "border-color", sc_section_header: "color", sc_table_header_bg: "background",
};

function _cpUpdatePreviewEl(mode, key, hex) {
  const prop = CP_PREVIEW_TARGETS[key];
  const container = window.__cpInlineContainer;
  if (!prop || !container) return;
  const el = container.querySelector('.cp-preview-mockup[data-preview-mode="' + mode + '"] [data-cpv="' + key + '"]');
  if (el) el.style.setProperty(prop, hex);
}

function _cpApply(mode, key, hex) {
  window.__themeEditorColors[mode][key] = hex;
  const container = window.__cpInlineContainer;
  const cell = container && container.querySelector('.cp-cell[data-mode="' + mode + '"][data-key="' + key + '"]');
  if (cell) {
    const ink = cell.querySelector(".cp-ink");
    if (ink) ink.setAttribute("fill", hex);
    const btn = cell.querySelector(".cp-inkwell");
    if (btn) btn.title = "Doladit barvu (" + hex + ")";
  }
  _cpUpdatePreviewEl(mode, key, hex);
  // Zive prekresleni admin.html ma smysl jen kdyz se prave edituje
  // povrch "admin" (eshop paleta se v adminu samotnem nikde nevykresluje)
  // A NEedituje se zrovna preset - preset je jen data, ktera se nikde
  // primo nevykresluji, dokud nejsou aplikovana tlacitkem "Pouzit".
  if (!window.__editingPresetId && window.__themeEditorSurface === "admin") {
    const current = document.documentElement.getAttribute("data-theme") || "dark";
    if (mode === current) applyThemeColorVars(current);
  }
  if (window.__cpPopoverTarget === _cpKey(mode, key)) _cpSyncPopoverUI();
}

function _cpOutsideClick(ev) {
  if (window.__cpPopoverEl && !window.__cpPopoverEl.contains(ev.target) && !ev.target.closest(".cp-inkwell")) {
    _cpClosePopover();
  }
}

function _cpClosePopover() {
  if (window.__cpPopoverEl) {
    window.__cpPopoverEl.remove();
    window.__cpPopoverEl = null;
    window.__cpPopoverTarget = null;
    document.removeEventListener("mousedown", _cpOutsideClick);
    document.removeEventListener("keydown", _cpEscClose);
    window.removeEventListener("scroll", _cpClosePopover, true);
  }
}

function _cpEscClose(ev) {
  if (ev.key === "Escape") _cpClosePopover();
}

function _cpSyncPopoverUI(skipHex) {
  if (!window.__cpPopoverEl || !window.__cpPopoverTarget) return;
  const st = window.__cpState[window.__cpPopoverTarget];
  const parts = window.__cpPopoverTarget.split("|");
  const mode = parts[0], key = parts[1];
  const hex = window.__themeEditorColors[mode][key];
  const pad = window.__cpPopoverEl.querySelector(".cp-sl-pad");
  pad.style.backgroundColor = "hsl(" + st.h + ",100%,50%)";
  const thumb = window.__cpPopoverEl.querySelector(".cp-sl-thumb");
  thumb.style.left = st.s + "%";
  thumb.style.top = (100 - st.l) + "%";
  if (!skipHex) {
    const hexInput = window.__cpPopoverEl.querySelector(".cp-hex-input");
    if (document.activeElement !== hexInput) hexInput.value = hex;
  }
  const container = window.__cpInlineContainer;
  const cell = container && container.querySelector('.cp-cell[data-mode="' + mode + '"][data-key="' + key + '"]');
  if (cell) {
    const slider = cell.querySelector(".cp-hue");
    if (slider) slider.value = st.h;
  }
}

function _cpOpenPopover(anchorBtn, mode, key) {
  _cpClosePopover();
  const st = window.__cpState[_cpKey(mode, key)];
  const pop = document.createElement("div");
  pop.className = "cp-popover";
  pop.innerHTML =
    '<div class="cp-sl-pad">'
    + '<div class="cp-sl-white"></div>'
    + '<div class="cp-sl-black"></div>'
    + '<div class="cp-sl-thumb"></div>'
    + "</div>"
    + '<div class="cp-popover-row">'
    + '<input type="text" class="cp-hex-input" maxlength="7" spellcheck="false">'
    + '<button type="button" class="cp-popover-close">Zavřít</button>'
    + "</div>";
  document.body.appendChild(pop);
  const rect = anchorBtn.getBoundingClientRect();
  pop.style.position = "fixed";
  pop.style.left = Math.max(8, Math.min(rect.left, window.innerWidth - 216)) + "px";
  pop.style.top = Math.min(rect.bottom + 6, window.innerHeight - 210) + "px";
  window.__cpPopoverEl = pop;
  window.__cpPopoverTarget = _cpKey(mode, key);
  _cpSyncPopoverUI();

  const pad = pop.querySelector(".cp-sl-pad");
  const thumb = pop.querySelector(".cp-sl-thumb");
  let dragging = false;
  function updateFromEvent(ev) {
    const r = pad.getBoundingClientRect();
    let x = (ev.clientX - r.left) / r.width;
    let y = (ev.clientY - r.top) / r.height;
    x = Math.max(0, Math.min(1, x));
    y = Math.max(0, Math.min(1, y));
    const s = Math.round(x * 100);
    const l = Math.round((1 - y) * 100);
    const state = window.__cpState[window.__cpPopoverTarget];
    state.s = s; state.l = l;
    const hex = hslToHex(state.h, state.s, state.l);
    _cpApply(mode, key, hex);
    thumb.style.left = (x * 100) + "%";
    thumb.style.top = (y * 100) + "%";
  }
  pad.addEventListener("pointerdown", ev => { dragging = true; pad.setPointerCapture(ev.pointerId); updateFromEvent(ev); });
  pad.addEventListener("pointermove", ev => { if (dragging) updateFromEvent(ev); });
  pad.addEventListener("pointerup", () => { dragging = false; });

  const hexInput = pop.querySelector(".cp-hex-input");
  hexInput.oninput = () => {
    let v = hexInput.value.trim();
    if (!/^#?[0-9a-fA-F]{6}$/.test(v)) return;
    if (v[0] !== "#") v = "#" + v;
    v = v.toLowerCase();
    window.__cpState[window.__cpPopoverTarget] = hexToHsl(v);
    _cpApply(mode, key, v);
    _cpSyncPopoverUI(true);
  };
  pop.querySelector(".cp-popover-close").onclick = _cpClosePopover;

  document.addEventListener("mousedown", _cpOutsideClick);
  document.addEventListener("keydown", _cpEscClose);
  window.addEventListener("scroll", _cpClosePopover, true);
}

// Namontuje kalamarove radky (Tmavy/Svetly sloupec) primo do dane karty
// (container = jeji .cp-inline-mount) - nahrazuje drivejsi sdilenou
// tabulku #themeColorsTbl (task #101, Robert: "kalamáře chci nahoře na
// schematech ne dole v tabulce"). window.__themeEditorColors uz drzi
// bud zivou paletu povrchu, nebo primo objekt jednoho presetu - stejny
// mechanismus jako predtim, jen se vykresluje jinam.
// Mala samostatna maketa rozhrani (okno/panel/tlacitka/text/stavy/chat/
// nahled/skladova karta) - NENAPOJENA na skutecny dokument (vsechny
// barvy jsou primo v inline style teto makety), takze funguje shodne
// pri editaci zive palety i presetu. Kazdy prvek nese data-cpv="klic"
// odpovidajici THEME_COLOR_FIELDS - viz hover-zvyrazneni v
// _mountInlineColorEditor, ktere prave timhle resi "jak poznam k cemu
// ta barva patri".
function _cpMockupHtml(mode, palette) {
  const p = palette[mode] || {};
  const c = key => p[key] || "#888888";
  const modeLabel = mode === "dark" ? "Tmavý motiv" : "Světlý motiv";
  return '<div class="cp-preview-mockup" data-preview-mode="' + mode + '">'
    + '<div class="cp-pv-label">' + modeLabel + ' – náhled</div>'
    + '<div class="cp-pv-window" data-cpv="bg" style="background:' + c("bg") + ';">'
    + '<div class="cp-pv-panel" data-cpv="panel_bg" style="background:' + c("panel_bg") + ';">'
    + '<div class="cp-pv-row" data-cpv="panel_bg_alt" style="background:' + c("panel_bg_alt") + ';">'
    + '<span data-cpv="text" style="color:' + c("text") + ';">Text</span> '
    + '<span data-cpv="text2" style="color:' + c("text2") + ';">sekundární</span>'
    + '</div>'
    + '<div class="cp-pv-row" data-cpv="row_dirty_bg" style="background:' + c("row_dirty_bg") + ';">'
    + '<span data-cpv="text_muted" style="color:' + c("text_muted") + ';">tlumený</span> '
    + '<span data-cpv="text_faint" style="color:' + c("text_faint") + ';">velmi tlumený</span>'
    + '</div>'
    + '<div class="cp-pv-borders">'
    + '<span data-cpv="border" style="border-color:' + c("border") + ';">okraj</span>'
    + '<span data-cpv="border_soft" style="border-color:' + c("border_soft") + ';">jemný</span>'
    + '<span data-cpv="border_soft2" style="border-color:' + c("border_soft2") + ';">jemný 2</span>'
    + '<span data-cpv="border_faint" style="border-color:' + c("border_faint") + ';">velmi jemný</span>'
    + '</div>'
    + '<div class="cp-pv-link" data-cpv="accent" style="color:' + c("accent") + ';">Akcent odkaz</div>'
    + '<input class="cp-pv-focus" data-cpv="accent_focus" style="border-color:' + c("accent_focus") + ';" readonly value="focus rámeček">'
    + '<div class="cp-pv-btns">'
    + '<button data-cpv="btn_bg" style="background:' + c("btn_bg") + ';">Tlačítko</button>'
    + '<button data-cpv="btn_bg_hover" style="background:' + c("btn_bg_hover") + ';">hover</button>'
    + '<button data-cpv="btn_danger" style="background:' + c("btn_danger") + ';">Smazat</button>'
    + '<button data-cpv="btn_danger_hover" style="background:' + c("btn_danger_hover") + ';">hover</button>'
    + '</div>'
    + '<div class="cp-pv-status">'
    + '<span data-cpv="error" style="color:' + c("error") + ';">Chyba</span>'
    + '<span data-cpv="success" style="color:' + c("success") + ';">Úspěch</span>'
    + '<span data-cpv="warn" style="color:' + c("warn") + ';">Varování</span>'
    + '</div>'
    + '<div class="cp-pv-chat">'
    + '<span class="cp-pv-bubble" data-cpv="support_bubble_bg" style="background:' + c("support_bubble_bg") + ';">Zpráva</span>'
    + '<span class="cp-pv-bubble" data-cpv="support_ai_bubble_bg" style="background:' + c("support_ai_bubble_bg") + ';"><span data-cpv="support_ai_text" style="color:' + c("support_ai_text") + ';">3Dbot</span></span>'
    + '</div>'
    + '<div class="cp-pv-thumb" data-cpv="thumb_bg" style="background:' + c("thumb_bg") + ';">náhled</div>'
    + '<div class="cp-pv-sc-header" data-cpv="sc_section_header" style="color:' + c("sc_section_header") + ';">Nadpis sekce</div>'
    + '<div class="cp-pv-sc-stat" data-cpv="sc_stat_bg" style="background:' + c("sc_stat_bg") + ';">'
    + '<span data-cpv="sc_stat_border" style="border-color:' + c("sc_stat_border") + ';">dlaždice</span>'
    + '</div>'
    + '<div class="cp-pv-sc-table-head" data-cpv="sc_table_header_bg" style="background:' + c("sc_table_header_bg") + ';">Záhlaví tabulky</div>'
    + '</div>'
    + '</div>'
    + '</div>';
}

function _mountInlineColorEditor(container) {
  const palette = window.__themeEditorColors;
  if (!container || !palette) return;
  _cpClosePopover();
  window.__cpState = {};
  const isCurrentSurface = window.__expandedCardId === "__current__";
  container.innerHTML =
    '<div class="cp-editor-layout">'
    + '<div class="cp-preview-wrap">' + _cpMockupHtml("dark", palette) + _cpMockupHtml("light", palette) + '</div>'
    + '<div class="cp-rows-col">'
    + '<p class="hint" style="margin:2px 0 10px;">Najetím na název barvy se v náhledu vlevo zvýrazní, co přesně barví.</p>'
    + '<div class="cp-inline-cols-head"><div></div><div>Tmavý motiv</div><div>Světlý motiv</div></div>'
    + THEME_COLOR_FIELDS.map(f => {
      if (f.group) return '<div class="cp-inline-group">' + f.group + '</div>';
      const dark = palette.dark[f.key] || "#000000";
      const light = palette.light[f.key] || "#ffffff";
      return '<div class="cp-inline-row" data-row-key="' + f.key + '">'
        + '<div class="cp-inline-label">' + f.label + '</div>'
        + _cpCellHtml("dark", f.key, dark)
        + _cpCellHtml("light", f.key, light)
        + '</div>';
    }).join("")
    + '</div>'
    + '</div>'
    + '<div class="cp-inline-actions">'
    + '<button type="button" class="cp-inline-save">Uložit barvy</button>'
    + (isCurrentSurface ? '<button type="button" class="cp-inline-reset-current">Vrátit na výchozí</button>' : "")
    + '<span class="cp-inline-status row-status"></span>'
    + '</div>';

  window.__cpInlineContainer = container;

  container.querySelectorAll(".cp-hue").forEach(slider => {
    slider.oninput = () => {
      const mode = slider.dataset.mode, key = slider.dataset.key;
      const st = window.__cpState[_cpKey(mode, key)];
      st.h = parseInt(slider.value, 10);
      const hex = hslToHex(st.h, st.s, st.l);
      _cpApply(mode, key, hex);
    };
  });
  container.querySelectorAll(".cp-inkwell").forEach(btn => {
    btn.onclick = () => _cpOpenPopover(btn, btn.dataset.mode, btn.dataset.key);
  });
  container.querySelectorAll(".cp-inline-row[data-row-key]").forEach(row => {
    const key = row.dataset.rowKey;
    const setHighlight = on => {
      container.querySelectorAll('[data-cpv="' + key + '"]').forEach(el => el.classList.toggle("cp-preview-highlight", on));
    };
    row.addEventListener("mouseenter", () => setHighlight(true));
    row.addEventListener("mouseleave", () => setHighlight(false));
    row.addEventListener("focusin", () => setHighlight(true));
    row.addEventListener("focusout", () => setHighlight(false));
  });
  container.querySelector(".cp-inline-save").onclick = _saveExpandedCard;
  const resetBtn = container.querySelector(".cp-inline-reset-current");
  if (resetBtn) resetBtn.onclick = resetCurrentSurfaceColors;
}

async function _saveExpandedCard() {
  const container = window.__cpInlineContainer;
  const statusEl = container && container.querySelector(".cp-inline-status");
  if (statusEl) statusEl.textContent = "ukládám…";
  const ok = window.__editingPresetId ? await saveThemePresetsList() : await _saveCurrentSurfaceColors();
  if (statusEl) {
    statusEl.textContent = ok ? "uloženo ✓" : "chyba uložení";
    if (ok) setTimeout(() => { if (statusEl) statusEl.textContent = ""; }, 2000);
  }
}

async function _saveCurrentSurfaceColors() {
  const err = document.getElementById("themeColorsErr");
  if (err) err.textContent = "";
  const palette = window.__themeEditorSurface === "admin" ? window.__themeColors : window.__themeColorsEshop;
  try {
    const r = await fetch("/api/admin/theme-colors", {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ surface: window.__themeEditorSurface, dark: palette.dark, light: palette.light }),
    });
    if (!r.ok) {
      const d = await r.json().catch(() => ({}));
      throw new Error(d.error || ("HTTP " + r.status));
    }
    return true;
  } catch (e) {
    if (err) err.textContent = "chyba: " + e.message;
    return false;
  }
}

function _updateThemeSurfaceButtons() {
  const isAdmin = window.__themeEditorSurface === "admin";
  const bAdmin = document.getElementById("btnThemeSurfaceAdmin");
  const bEshop = document.getElementById("btnThemeSurfaceEshop");
  if (bAdmin) bAdmin.classList.toggle("active", isAdmin);
  if (bEshop) bEshop.classList.toggle("active", !isAdmin);
}

async function switchThemeEditorSurface(surface) {
  window.__themeEditorSurface = surface;
  window.__editingPresetId = null;
  window.__expandedCardId = null;
  _updateThemeSurfaceButtons();
  const err = document.getElementById("themeColorsErr");
  if (err) err.textContent = "";
  if (surface === "admin") {
    renderThemePresets();
    return;
  }
  if (window.__themeColorsEshop) {
    renderThemePresets();
    return;
  }
  try {
    const r = await fetch("/api/theme-colors?surface=eshop");
    const data = await r.json();
    window.__themeColorsEshop = { dark: data.dark, light: data.light };
    renderThemePresets();
  } catch (e) {
    if (err) err.textContent = "Chyba načtení: " + e.message;
  }
}

document.getElementById("btnThemeSurfaceAdmin").onclick = () => switchThemeEditorSurface("admin");
document.getElementById("btnThemeSurfaceEshop").onclick = () => switchThemeEditorSurface("eshop");

async function loadThemeColors() {
  try {
    const r = await fetch("/api/theme-colors?surface=admin");
    const data = await r.json();
    window.__themeColors = { dark: data.dark, light: data.light };
    window.__themeEditorSurface = "admin";
    window.__editingPresetId = null;
    window.__expandedCardId = null;
    await loadThemePresets();
    _updateThemeSurfaceButtons();
    renderThemePresets();
    applyThemeColorVars(document.documentElement.getAttribute("data-theme") || "dark");
  } catch (e) {
    const err = document.getElementById("themeColorsErr");
    if (err) err.textContent = "Chyba načtení: " + e.message;
  }
}

// ==================== BARVY ONLINE NABIDKY (Robert 2026-08-06: "dej do
// nabídky barvítka, uprava barev hlavních prvků upravím si to jak
// potřebuju") - samostatna, jednodussi obdoba theme-colors vyse: jedna
// pevna paleta (surface="nabidka", ctou/ukladaji se jen klice "light" -
// nabidka nema tmavy/svetly prepinac, "dark" polovina API tvaru se
// jen drzi synchronizovana pro pripad budoucího vyuziti). Klice viz
// api/app.py THEME_COLOR_KEYS ("offer_*").
const OFFER_COLOR_FIELDS = [
  { key: "offer_navy_dark", label: "Tmavě námořnická (pozadí úvodu/závěru, horní lišta)" },
  { key: "offer_navy", label: "Námořnická (nadpisy, hlavičky tabulek)" },
  { key: "offer_navy_light", label: "Světlejší námořnická (přechod v pozadí)" },
  { key: "offer_orange", label: "Oranžová (hlavní akcent, tlačítka)" },
  { key: "offer_orange_light", label: "Světlejší oranžová (hover)" },
  { key: "offer_card_bg", label: "Pozadí karet" },
  { key: "offer_ink", label: "Základní text" },
  { key: "offer_ink_soft", label: "Sekundární text" },
  { key: "offer_muted", label: "Popisky / meta text" },
  { key: "offer_border", label: "Ohraničení karet a polí" },
];
let offerColorsCurrent = null;

async function loadOfferColors() {
  const errEl = document.getElementById("offerColorsErr");
  errEl.textContent = "";
  try {
    const r = await fetch("/api/theme-colors?surface=nabidka");
    if (!r.ok) throw new Error("HTTP " + r.status);
    const data = await r.json();
    offerColorsCurrent = data.light;
    renderOfferColors();
  } catch (e) {
    errEl.textContent = "Chyba načtení: " + e.message;
  }
}

function renderOfferColors() {
  const grid = document.getElementById("offerColorsGrid");
  if (!grid || !offerColorsCurrent) return;
  grid.innerHTML = OFFER_COLOR_FIELDS.map(f => {
    const val = offerColorsCurrent[f.key] || "#000000";
    return `<div class="offer-color-row">
      <input type="color" data-key="${f.key}" value="${val}">
      <div>
        <div class="offer-color-label">${escapeHtmlAdmin(f.label)}</div>
        <div class="offer-color-hex" id="offerColorHex_${f.key}">${val}</div>
      </div>
    </div>`;
  }).join("");
  grid.querySelectorAll('input[type="color"]').forEach(inp => {
    inp.oninput = () => {
      offerColorsCurrent[inp.dataset.key] = inp.value;
      const hexEl = document.getElementById("offerColorHex_" + inp.dataset.key);
      if (hexEl) hexEl.textContent = inp.value;
    };
  });
}

document.getElementById("btnSaveOfferColors").onclick = async () => {
  const btn = document.getElementById("btnSaveOfferColors");
  const status = document.getElementById("offerColorsStatus");
  const errEl = document.getElementById("offerColorsErr");
  errEl.textContent = "";
  btn.disabled = true;
  try {
    const r = await fetch("/api/admin/theme-colors", {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ surface: "nabidka", light: offerColorsCurrent, dark: offerColorsCurrent }),
    });
    const data = await r.json();
    if (!r.ok) throw new Error(data.error || ("HTTP " + r.status));
    status.textContent = "uloženo ✓";
    setTimeout(() => { status.textContent = ""; }, 3000);
  } catch (e) {
    errEl.textContent = "Chyba uložení: " + e.message;
  } finally {
    btn.disabled = false;
  }
};

// Stejne hodnoty jako api/app.py THEME_COLOR_DEFAULTS["light"] (offer_*
// klice) - jen pro tlacitko "Vratit na vychozi" (zadny zvlastni backend
// endpoint, proste se ulozi tahle sada pres bezny PUT jako u ostatnich
// povrchu vyse).
const OFFER_COLOR_DEFAULTS = {
  offer_navy_dark: "#0f2138", offer_navy: "#16324f", offer_navy_light: "#1c4a6b",
  offer_orange: "#ff7a3d", offer_orange_light: "#ffb35c",
  offer_card_bg: "#f4f8fb", offer_ink: "#1b2430", offer_ink_soft: "#2a3646",
  offer_muted: "#7a8798", offer_border: "#e2e7f1",
};
document.getElementById("btnResetOfferColors").onclick = async () => {
  if (!confirm("Vrátit barvy online nabídky na výchozí? Uloží se ihned.")) return;
  const errEl = document.getElementById("offerColorsErr");
  errEl.textContent = "";
  offerColorsCurrent = { ...OFFER_COLOR_DEFAULTS };
  renderOfferColors();
  try {
    const r = await fetch("/api/admin/theme-colors", {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ surface: "nabidka", light: offerColorsCurrent, dark: offerColorsCurrent }),
    });
    const data = await r.json();
    if (!r.ok) throw new Error(data.error || ("HTTP " + r.status));
    const status = document.getElementById("offerColorsStatus");
    status.textContent = "vráceno na výchozí ✓";
    setTimeout(() => { status.textContent = ""; }, 3000);
  } catch (e) {
    errEl.textContent = "Chyba uložení: " + e.message;
  }
};

// ==================== BARVY KOSIKU (Robert 2026-08-08: "v adminu do
// Vzhledu novy prvek, zmena barev pro kosik") - identicka obdoba BARVY
// ONLINE NABIDKY vyse, jen surface="cart" a klice "cart_*" (viz api/app.py
// THEME_COLOR_KEYS). #cartDrawer v product/category/index.html cte tuhle
// paletu a mapuje ji na sve --cn-* CSS promenne (viz applyCartColors tam).
const CART_COLOR_FIELDS = [
  { key: "cart_navy_dark", label: "Tmavě námořnická (horní lišta kroků)" },
  { key: "cart_navy", label: "Námořnická (hlavička, nadpisy)" },
  { key: "cart_navy_light", label: "Světlejší námořnická (přechod v total-banneru)" },
  { key: "cart_orange", label: "Oranžová (hlavní akcent, tlačítka)" },
  { key: "cart_orange_light", label: "Světlejší oranžová (hotové kroky)" },
  { key: "cart_card_bg", label: "Pozadí karet" },
  { key: "cart_ink", label: "Základní text" },
  { key: "cart_ink_soft", label: "Sekundární text" },
  { key: "cart_muted", label: "Popisky / meta text" },
  { key: "cart_border", label: "Ohraničení karet a polí" },
];
let cartColorsCurrent = null;

async function loadCartColors() {
  const errEl = document.getElementById("cartColorsErr");
  errEl.textContent = "";
  try {
    const r = await fetch("/api/theme-colors?surface=cart");
    if (!r.ok) throw new Error("HTTP " + r.status);
    const data = await r.json();
    cartColorsCurrent = data.light;
    renderCartColors();
  } catch (e) {
    errEl.textContent = "Chyba načtení: " + e.message;
  }
}

function renderCartColors() {
  const grid = document.getElementById("cartColorsGrid");
  if (!grid || !cartColorsCurrent) return;
  grid.innerHTML = CART_COLOR_FIELDS.map(f => {
    const val = cartColorsCurrent[f.key] || "#000000";
    return `<div class="offer-color-row">
      <input type="color" data-key="${f.key}" value="${val}">
      <div>
        <div class="offer-color-label">${escapeHtmlAdmin(f.label)}</div>
        <div class="offer-color-hex" id="cartColorHex_${f.key}">${val}</div>
      </div>
    </div>`;
  }).join("");
  grid.querySelectorAll('input[type="color"]').forEach(inp => {
    inp.oninput = () => {
      cartColorsCurrent[inp.dataset.key] = inp.value;
      const hexEl = document.getElementById("cartColorHex_" + inp.dataset.key);
      if (hexEl) hexEl.textContent = inp.value;
    };
  });
}

document.getElementById("btnSaveCartColors").onclick = async () => {
  const btn = document.getElementById("btnSaveCartColors");
  const status = document.getElementById("cartColorsStatus");
  const errEl = document.getElementById("cartColorsErr");
  errEl.textContent = "";
  btn.disabled = true;
  try {
    const r = await fetch("/api/admin/theme-colors", {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ surface: "cart", light: cartColorsCurrent, dark: cartColorsCurrent }),
    });
    const data = await r.json();
    if (!r.ok) throw new Error(data.error || ("HTTP " + r.status));
    status.textContent = "uloženo ✓";
    setTimeout(() => { status.textContent = ""; }, 3000);
  } catch (e) {
    errEl.textContent = "Chyba uložení: " + e.message;
  } finally {
    btn.disabled = false;
  }
};

const CART_COLOR_DEFAULTS = {
  cart_navy_dark: "#0f2138", cart_navy: "#16324f", cart_navy_light: "#1c4a6b",
  cart_orange: "#ff7a3d", cart_orange_light: "#ffb35c",
  cart_card_bg: "#f4f8fb", cart_ink: "#1b2430", cart_ink_soft: "#2a3646",
  cart_muted: "#7a8798", cart_border: "#e2e8ee",
};
document.getElementById("btnResetCartColors").onclick = async () => {
  if (!confirm("Vrátit barvy košíku na výchozí? Uloží se ihned.")) return;
  const errEl = document.getElementById("cartColorsErr");
  errEl.textContent = "";
  cartColorsCurrent = { ...CART_COLOR_DEFAULTS };
  renderCartColors();
  try {
    const r = await fetch("/api/admin/theme-colors", {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ surface: "cart", light: cartColorsCurrent, dark: cartColorsCurrent }),
    });
    const data = await r.json();
    if (!r.ok) throw new Error(data.error || ("HTTP " + r.status));
    const status = document.getElementById("cartColorsStatus");
    status.textContent = "vráceno na výchozí ✓";
    setTimeout(() => { status.textContent = ""; }, 3000);
  } catch (e) {
    errEl.textContent = "Chyba uložení: " + e.message;
  }
};

function applyAdminTheme(theme, opts) {
  opts = opts || {};
  theme = theme === "light" ? "light" : "dark";
  document.documentElement.setAttribute("data-theme", theme);
  try { localStorage.setItem("adminTheme", theme); } catch (e) {}
  applyThemeColorVars(theme);
  var btn = document.getElementById("themeToggleBtn");
  if (btn) {
    btn.innerHTML = theme === "light"
      ? '<span class="tt-icon">🌙</span>Tmavý motiv'
      : '<span class="tt-icon">☀️</span>Světlý motiv';
  }
  if (opts.persist) {
    fetch("/api/auth/theme", {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ scope: "admin", theme: theme }),
    }).catch(function () {});
  }
}
function toggleAdminTheme() {
  var current = document.documentElement.getAttribute("data-theme") === "light" ? "light" : "dark";
  applyAdminTheme(current === "light" ? "dark" : "light", { persist: true });
}
applyAdminTheme(document.documentElement.getAttribute("data-theme") || "dark", { persist: false });
