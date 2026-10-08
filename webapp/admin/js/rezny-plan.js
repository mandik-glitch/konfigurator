// ==================== REZNY PLAN (bot4 cutting backend, bot2 UI) ====================
// Zdroj dat: GET /api/admin/orders/<id>/cutting-plan (bot4, viz api/cutting.py,
// NAVRH_REZNE_PLANY.md). Bez ukladani do DB - prepocita se pri kazdem otevreni.
// Stejna paleta jako ORDER_COLOR_PALETTE v api/cutting.py (udrzovat synchronne).
const CP_COLORS = ["#5b8def", "#e0a458", "#7ec488", "#d97b7b", "#9d7bd9", "#54b8b0", "#c78bd9", "#a3a86b", "#4fb3d9", "#e08ac0", "#a8c15a", "#c96f4a"];
// bot4, 2026-07-26 (vzhled dle referencniho CAM softwaru Truhlar/Aptechsoftware,
// obrazek od Roberta) - barevny "vzorník" materialu v hlavicce kazde tyce/desky
// (stejny material_key/stock_label = vzdy stejna barva, deterministicky hash) +
// zvyraznovaci barva pro olepene hrany (ABS 2mm - jediny pouzivany typ, Robert
// potvrdil "ABS 2mm").
function _cpMaterialColor(key) {
  let h = 0;
  const s = String(key || "");
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0;
  return `hsl(${h % 360}, 55%, 45%)`;
}
const CP_EDGE_BAND_COLOR = "#ffd23f";
// Robert 2026-08-08 ("pozadí nemuze byt barevne, kdyz se bude list
// tisknout musi to byt cernobile... muzou byt jen drobne odstiny barev
// které nezatíží toner tiskárny") - syte barvy CP_COLORS (i shodne
// ORDER_COLOR_PALETTE v api/cutting.py, ta se propisuje pres
// orderColors) jsou OK na obrazovce (tmave pozadi adminu), ale v
// printCuttingPlanArea() se kopiruje stejne SVG do tiskoveho okna -
// tam by sytá plocha kazdeho kusu spotrebovala hodne toneru. Mapa
// 1:1 nahrazuje kazdou znamou syte barvu (fill="#..." atribut) jejim
// velmi svetlym ekvivalentem (HSL L≈93%, S sniena) - odstin zustava
// rozeznatelny (kus od kusu, zakazka od zakazky), ale plocha je skoro
// bila. Odpadni usek (fill "#2a2e37" u _cpRenderUnitBar) nema zadny
// informacni odstin - ten jde primo na bilou.
const CP_PRINT_COLOR_MAP = {
  "#5b8def": "#e3eaf7", "#e0a458": "#f7eee3", "#7ec488": "#e8f3e9",
  "#d97b7b": "#f6e5e5", "#9d7bd9": "#ebe5f6", "#54b8b0": "#e7f3f2",
  "#c78bd9": "#f1e5f5", "#a3a86b": "#f0f1e9", "#4fb3d9": "#e3f2f7",
  "#e08ac0": "#f6e4ef", "#a8c15a": "#f1f4e6", "#c96f4a": "#f5eae5",
  "#2a2e37": "#ffffff",
};
function cpToPrintSafeColors(html) {
  let out = html;
  for (const [from, to] of Object.entries(CP_PRINT_COLOR_MAP)) {
    out = out.split(`fill="${from}"`).join(`fill="${to}"`);
  }
  return out;
}

function _cpEsc(s) {
  return String(s == null ? "" : s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}

// Olepeni hran (edge_bands) je v API vzdy vzhledem k DEKLAROVANE (nerotovane)
// orientaci kusu (viz cutting_algo.py docstring pack_2d) - "rotated" priznak
// rika, jestli algoritmus kus pro lepsi vyuziti otocil o 90 stupnu. Tahle
// funkce premapuje deklarovane strany na skutecnou vizualni stranu na desce
// (priblizne, jednotna konvence 90 CW - presny smer otoceni packer netrackuje,
// stejne priblizne jako _guillotine_cuts_2d na backendu).
function _cpVisualEdges(p) {
  const e = p.edge_bands || {};
  if (!p.rotated) return { top: !!e.top, bottom: !!e.bottom, left: !!e.left, right: !!e.right };
  return { top: !!e.left, bottom: !!e.right, left: !!e.bottom, right: !!e.top };
}

async function loadCuttingPlan(orderId) {
  const el = document.getElementById("cuttingPlanContent");
  el.className = "hint";
  el.textContent = "Načítám...";
  try {
    const r = await fetch(`/api/admin/orders/${orderId}/cutting-plan`);
    if (!r.ok) throw new Error("HTTP " + r.status);
    const data = await r.json();
    renderCuttingPlan(data, "cuttingPlanContent");
  } catch (e) {
    el.className = "err";
    el.textContent = "Chyba načtení řezného plánu: " + e.message;
  }
}

// ==================== HROMADNY REZNY PLAN - PERZISTENTNI (bot4, bot2 UI) ====================
// Zdroj dat (bot4, 2026-07-26, viz cutting.py):
//   POST /api/admin/cutting-plan/generate  - spocita a ULOZI nove jednotky
//                                             (mínus uz hotove/naplanovane kusy)
//   GET  /api/admin/cutting-plan?status=   - CTE ulozene jednotky (pending/done/vse),
//                                             + informativni order_progress
//   PATCH /api/admin/cutting-plan/units/<id> - odskrtnuti hotove/nehotove
// POZOR: tvar odpovedi GET je JINY nez u diagnostickeho per-objednavka
// pohledu (loadCuttingPlan/renderCuttingPlan nize) - tam se porad zivě
// prepocitava z shop_order_items, tady se cte hotova ulozena jednotka
// (materials[].units[] misto plans[].plan.bars/sheets).
function _cpGenerateSelectedOrderIds() {
  return Array.from(document.querySelectorAll("#cpGenerateOrderFilter .cp-gen-order-cb:checked")).map(cb => Number(cb.dataset.orderId));
}

async function _cpRenderGenerateOrderFilter() {
  const el = document.getElementById("cpGenerateOrderFilter");
  el.textContent = "Načítám...";
  try {
    const r = await fetch("/api/admin/cutting-plan/candidate-orders");
    if (!r.ok) throw new Error("HTTP " + r.status);
    const data = await r.json();
    const orders = data.orders || [];
    if (!orders.length) {
      el.textContent = "Žádné (nezrušené) objednávky s položkami k řezání.";
      return;
    }
    el.innerHTML = orders.map(o => {
      const done = o.remaining_pieces <= 0;
      const statusLabel = ORDER_STATUS_LABELS[o.status] || o.status;
      return `<label style="display:block;font-size:12.5px;margin-bottom:4px;${done ? "color:#6f7784;" : "color:#c7ccd4;"}">
        <input type="checkbox" class="cp-gen-order-cb" data-order-id="${o.order_id}" ${done ? "" : "checked"}>
        <strong>${escapeHtmlAdmin(o.order_number)}</strong> - ${escapeHtmlAdmin(o.customer_name)}
        (${escapeHtmlAdmin(statusLabel)}) - ${o.remaining_pieces}/${o.total_pieces} kusů k naplánování
      </label>`;
    }).join("");
    el.querySelectorAll(".cp-gen-order-cb").forEach(cb => {
      cb.onchange = () => {
        const all = el.querySelectorAll(".cp-gen-order-cb");
        document.getElementById("cpGenOrdersSelectAll").checked =
          Array.from(all).every(c => c.checked);
      };
    });
    document.getElementById("cpGenOrdersSelectAll").checked =
      Array.from(el.querySelectorAll(".cp-gen-order-cb")).every(c => c.checked);
  } catch (e) {
    el.className = "err";
    el.textContent = "Chyba načtení objednávek: " + e.message;
  }
}

document.getElementById("cpGenOrdersSelectAll").onchange = (ev) => {
  document.querySelectorAll("#cpGenerateOrderFilter .cp-gen-order-cb").forEach(cb => { cb.checked = ev.target.checked; });
};
document.getElementById("btnCpGenOrdersRefresh").onclick = _cpRenderGenerateOrderFilter;

// Spolecna logika pro POST /generate, sdilena mezi generovanim z
// objednavek a generovanim z rucnich kusu (Robert pres bot3, 2026-09-03:
// "dej to úplně bokem objednávkového řezného plánu" - DVE NEZAVISLE
// tlacitka/panely, ktere ale volaji STEJNY backend endpoint, protoze ten
// uz umi obojí nezávisle na sobě). Zobrazuje i `data.errors` (Robert,
// zivy nalez: preklepnuty material_key se drive tise ztratil - "Zadne
// kusy k naplanovani" bez duvodu, viz api/cutting.py komentar u
// plan_errors) - plati stejne pro rucni kusy i pro polozky objednavek se
// spatne nastavenym material_key na skladove karte.
async function _cpRunGenerate(btn, resultEl, body, onSuccess) {
  btn.disabled = true;
  resultEl.className = "";
  resultEl.textContent = "Počítám...";
  try {
    const r = await fetch("/api/admin/cutting-plan/generate", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await r.json();
    if (!r.ok) throw new Error(data.error || ("HTTP " + r.status));
    const skipped = (data.already_planned_skipped || []).length;
    const noDim = (data.items_without_dimensions || []).length;
    const errs = data.errors || [];
    // backend od 2026-08 pri nule jednotek plan vubec nezaklada a posila
    // message ("Zadne kusy k naplanovani...") - zobrazit ji misto
    // matouciho "Vygenerovano 0 novych jednotek"
    let text = (data.message || `Vygenerováno ${data.units_created} nových jednotek (tyčí/desek).`) +
      (skipped ? ` ${skipped} položek už bylo naplánováno nebo hotovo dřív, nepřidávaly se znovu.` : "") +
      (noDim ? ` ${noDim} položek bez rozměrů k řezání se přeskočilo.` : "");
    if (errs.length) {
      resultEl.className = data.units_created ? "" : "err";
      text += " ⚠ " + errs.map(e => `${e.material_key} (${e.cut_kind}): ${e.error}`).join(" ");
    }
    resultEl.textContent = text;
    document.querySelector('input[name="cpUnitFilter"][value="pending"]').checked = true;
    // loadBulkCuttingPlan() jen obnovi sdilenou tabulku "Prehled" nahoře
    // (dilenske trackovani "hotovo" napric vsemi plany) - NEPOSOUVA
    // pohled tam. Robert, 4. kolo pripominek k teto funkci: vysledek
    // rucniho generovani se ma zobrazit tam, kde vznikl (karta "Ruční
    // kusy"), ne jen v teto sdilene tabulce nahore. Proto onSuccess dostava
    // `data` (obsahuje `plan_id`), aby si volajici mohl dotahnout a
    // vykreslit JEN jednotky sveho plánu (viz generateManualCuttingPlan).
    loadBulkCuttingPlan();
    loadCpRemnants();
    onSuccess(data);
  } catch (e) {
    resultEl.className = "err";
    resultEl.textContent = "Chyba generování: " + e.message;
  } finally {
    btn.disabled = false;
  }
}

async function generateCuttingPlan() {
  const order_ids = _cpGenerateSelectedOrderIds();
  const resultEl = document.getElementById("cpGenerateResult");
  if (!order_ids.length) {
    resultEl.className = "err";
    resultEl.textContent = "Zaškrtni aspoň jednu objednávku.";
    return;
  }
  await _cpRunGenerate(
    document.getElementById("btnGenerateCuttingPlan"), resultEl,
    { order_ids },
    () => { _cpRenderGenerateOrderFilter(); },
  );
}

// ------------------------------------------------------------------
// Rucni kusy BEZ vazby na objednavku (Robert pres bot3, 2026-09-03,
// "hned", pote prepracovano na zadost Roberta do VLASTNIHO panelu s
// VLASTNIM tlacitkem, nesdileneho s vyberem objednavek vyse) -
// jednoduchy seznam v pameti (cpManualPieces), naplni se tlacitkem
// "+ Přidat řádek" a posle se VLASTNIM tlacitkem "Vygenerovat plán z
// ručních kusů" (order_ids vzdy prazdne). Zadna perzistence/checkbox
// vyber jako u objednavek - kazdy radek je "jednorazovy" popis, ktery
// se pri uspesnem vygenerovani vycisti.
//
// Material_key je SELECT (ne volny text) - zivy nalez (Robert, prvni
// pokus): do puvodniho textoveho pole s napovednym placeholderem
// "např. 30x30" napsal skutecny rozmer desky "2500x1250" mista
// katalogoveho klice jako "mdf_8" (30x30 jako priklad vypadalo jako
// rozmer, ne jako nazev). SELECT omezeny na skutecne aktivni varianty
// ze shop_cutting_stock eliminuje tenhle preklep uplne - nejde zadat
// nic, co by _fetch_stock_and_kerf nenasel.
let cpManualPieces = [];
let cpManualMaterialsByCutKind = { profil: [], deska: [] };

// "Univerzální tyč" (Robert pres bot3, 2026-09-07): vlastní délka SKLADOVÉ
// tyče u profilu, nezávislá na katalogu shop_cutting_stock (zbytek/odřezek/
// koupeno mimo sklad) - viz api/cutting.py::_get_or_create_universal_rod_stock.
// Zvlastni sentinel hodnota v #cpManualMaterial (ne skutecny material_key -
// backend si material_key sam odvodi/vytvori ze zadane delky).
const CP_UNIVERSAL_ROD_VALUE = "__universal__";
const CP_UNIVERSAL_ROD_MAX_MM = 6000;

function _cpManualUpdateDimFields() {
  const isProfil = document.getElementById("cpManualCutKind").value === "profil";
  document.getElementById("cpManualLength").style.display = isProfil ? "" : "none";
  document.getElementById("cpManualWidth").style.display = isProfil ? "none" : "";
  document.getElementById("cpManualHeight").style.display = isProfil ? "none" : "";
}

function _cpManualUpdateUniversalField() {
  const isUniversal = document.getElementById("cpManualMaterial").value === CP_UNIVERSAL_ROD_VALUE;
  document.getElementById("cpManualUniversalLength").style.display = isUniversal ? "" : "none";
}

function _cpManualRenderMaterialOptions() {
  const cutKind = document.getElementById("cpManualCutKind").value;
  const sel = document.getElementById("cpManualMaterial");
  const options = cpManualMaterialsByCutKind[cutKind] || [];
  let html = options.length
    ? options.map(mk => `<option value="${escapeHtmlAdmin(mk)}">${escapeHtmlAdmin(mk)}</option>`).join("")
    : '<option value="">Žádný aktivní materiál tohoto typu ve skladu</option>';
  // Jen u profilu - "univerzální tyč" dává smysl jen pro délku tyče,
  // ne pro rozměr desky. Pripojeno NA KONEC (ne prvni option), aby
  // vychozi vyber po prepnuti cut_kind zustal prvni katalogovy material
  // jako drive - "univerzalni tyc" je vedomy opt-in, ne novy vychozi stav.
  if (cutKind === "profil") {
    html += `<option value="${CP_UNIVERSAL_ROD_VALUE}">Univerzální tyč (vlastní délka)</option>`;
  }
  sel.innerHTML = html;
  _cpManualUpdateUniversalField();
}

document.getElementById("cpManualCutKind").onchange = () => {
  _cpManualUpdateDimFields();
  _cpManualRenderMaterialOptions();
};
document.getElementById("cpManualMaterial").onchange = _cpManualUpdateUniversalField;

function _cpRenderManualList() {
  const el = document.getElementById("cpManualList");
  if (!cpManualPieces.length) { el.textContent = "Žádné ruční položky."; return; }
  el.innerHTML = cpManualPieces.map((p, i) => {
    const dims = p.cut_kind === "profil" ? `${p.length_mm} mm` : `${p.width_mm}×${p.height_mm} mm`;
    const materialLabel = p.universal_stock_length_mm
      ? `Univerzální tyč ${p.universal_stock_length_mm} mm`
      : escapeHtmlAdmin(p.material_key);
    return `<div style="display:flex;justify-content:space-between;align-items:center;padding:3px 0;border-bottom:1px solid #2a2e37;">
      <span>${p.cut_kind === "profil" ? "Profil" : "Deska"} ${materialLabel}, ${dims}, ${p.qty} ks${p.label ? " - " + escapeHtmlAdmin(p.label) : ""}</span>
      <button type="button" data-i="${i}" class="cp-manual-remove" style="background:none;border:1px solid #3a3f4a;color:#e07070;padding:1px 8px;">Smazat</button>
    </div>`;
  }).join("");
  el.querySelectorAll(".cp-manual-remove").forEach(btn => {
    btn.onclick = () => { cpManualPieces.splice(parseInt(btn.dataset.i, 10), 1); _cpRenderManualList(); };
  });
}

async function _cpLoadManualMaterials() {
  const sel = document.getElementById("cpManualMaterial");
  try {
    const r = await fetch("/api/admin/cutting-plan/materials");
    if (!r.ok) throw new Error("HTTP " + r.status);
    const data = await r.json();
    cpManualMaterialsByCutKind = { profil: [], deska: [] };
    (data.materials || []).forEach(m => {
      if (cpManualMaterialsByCutKind[m.cut_kind]) cpManualMaterialsByCutKind[m.cut_kind].push(m.material_key);
    });
    _cpManualRenderMaterialOptions();
  } catch (e) {
    sel.innerHTML = '<option value="">Nepodařilo se načíst materiály</option>';
  }
}

document.getElementById("btnCpManualAdd").onclick = () => {
  const cut_kind = document.getElementById("cpManualCutKind").value;
  const material_key = document.getElementById("cpManualMaterial").value;
  const qty = parseInt(document.getElementById("cpManualQty").value, 10);
  const label = document.getElementById("cpManualLabel").value.trim();
  if (!material_key) { alert("Vyber materiál ze seznamu (žádný aktivní materiál tohoto typu možná není ve skladu nastaven)."); return; }
  if (!qty || qty <= 0) { alert("Počet kusů musí být kladné číslo."); return; }
  const isUniversal = cut_kind === "profil" && material_key === CP_UNIVERSAL_ROD_VALUE;
  const piece = { cut_kind, qty };
  if (label) piece.label = label;
  let universalLen = null;
  if (isUniversal) {
    // Obranne parsovani (Robert 2026-09-07, "6000 nepobralo") - .trim() proti
    // whitespace, nahrazeni ',' za '.' pro pripad, ze by nejaky vstupni
    // mechanismus (mobilni klavesnice/locale) poslal desetinnou carku misto
    // tecky. Math.round() na 0.01mm proti floating-point hranici presne NA
    // limitu (6000.00000000001 > 6000 by jinak umelo odmitlo platnou hodnotu).
    const rawLen = (document.getElementById("cpManualUniversalLength").value || "").trim().replace(",", ".");
    universalLen = Math.round(parseFloat(rawLen) * 100) / 100;
    if (!universalLen || universalLen <= 0 || universalLen > CP_UNIVERSAL_ROD_MAX_MM) {
      alert(`Zadej délku materiálu (kladné číslo do ${CP_UNIVERSAL_ROD_MAX_MM} mm). Zadaná hodnota: "${document.getElementById("cpManualUniversalLength").value}"`);
      return;
    }
    piece.universal_stock_length_mm = universalLen;
  } else {
    piece.material_key = material_key;
  }
  if (cut_kind === "profil") {
    const length_mm = parseFloat(document.getElementById("cpManualLength").value);
    if (!length_mm || length_mm <= 0) { alert("Zadej délku (mm)."); return; }
    if (isUniversal && length_mm > universalLen) {
      alert(`Délka kusu (${length_mm} mm) je delší než zadaná univerzální tyč (${universalLen} mm).`);
      return;
    }
    piece.length_mm = length_mm;
  } else {
    const width_mm = parseFloat(document.getElementById("cpManualWidth").value);
    const height_mm = parseFloat(document.getElementById("cpManualHeight").value);
    if (!width_mm || !height_mm || width_mm <= 0 || height_mm <= 0) { alert("Zadej šířku i výšku (mm)."); return; }
    piece.width_mm = width_mm;
    piece.height_mm = height_mm;
  }
  cpManualPieces.push(piece);
  document.getElementById("cpManualLength").value = "";
  document.getElementById("cpManualWidth").value = "";
  document.getElementById("cpManualHeight").value = "";
  document.getElementById("cpManualUniversalLength").value = "";
  document.getElementById("cpManualQty").value = "1";
  document.getElementById("cpManualLabel").value = "";
  _cpRenderManualList();
};

// Vysledek rucniho generovani se vykresli PRIMO v teto karte (viz
// #cpManualResultTable pod tlacitkem) - ne jen ve sdilene tabulce
// "Prehled" nahoře v panelu, kam by ho uzivatel bez scrollovani zpet
// nahoru vubec nevidel (Robert, 4. kolo: "plán se zobrazuje nahoře u
// objednávek, má se zobrazovat přece dole odděleně"). Filtrovano na
// backendu podle `plan_id` z odpovedi generate (?plan_id=), takze se tu
// ukazi VYHRADNE jednotky z prave vygenerovaneho planu, ne cely sdileny
// obsah.
async function _cpLoadManualResultTable(planId) {
  const el = document.getElementById("cpManualResultTable");
  el.innerHTML = '<p class="hint">Načítám výsledek...</p>';
  try {
    const r = await fetch(`/api/admin/cutting-plan?plan_id=${planId}`);
    if (!r.ok) throw new Error("HTTP " + r.status);
    const data = await r.json();
    el.innerHTML = _cpRenderManualResultTable(data.materials || []);
  } catch (e) {
    el.innerHTML = `<p class="err">Chyba načtení výsledku: ${escapeHtmlAdmin(e.message)}</p>`;
  }
}

function _cpRenderManualResultTable(materials) {
  const rows = [];
  materials.forEach(m => {
    const isProfil = m.cut_kind === "profil";
    m.units.forEach(u => {
      const rozmer = isProfil
        ? `${Math.round(u.stock_length_mm)} mm`
        : `${Math.round(u.stock_width_mm)}×${Math.round(u.stock_height_mm)} mm`;
      const odpad = isProfil
        ? `${Math.round(u.waste_amount)} mm`
        : `${Math.round(u.waste_amount / 1000)} cm²`;
      rows.push(`<tr>
        <td>${escapeHtmlAdmin(u.stock_label)}</td>
        <td>${rozmer}</td>
        <td>${u.cuts_count != null ? u.cuts_count : "?"}</td>
        <td>${odpad}</td>
      </tr>`);
    });
  });
  if (!rows.length) return '<p class="hint">Žádné jednotky v tomhle plánu.</p>';
  return `<table class="om-items-table">
    <thead><tr><th>Materiál</th><th>Rozměr</th><th>Počet řezů</th><th>Odpad</th></tr></thead>
    <tbody>${rows.join("")}</tbody>
  </table>`;
}

async function generateManualCuttingPlan() {
  const resultEl = document.getElementById("cpManualGenerateResult");
  if (!cpManualPieces.length) {
    resultEl.className = "err";
    resultEl.textContent = "Přidej aspoň jednu ruční položku.";
    return;
  }
  document.getElementById("cpManualResultTable").innerHTML = "";
  await _cpRunGenerate(
    document.getElementById("btnGenerateManualCuttingPlan"), resultEl,
    { pieces: cpManualPieces },
    (data) => {
      // Rucni kusy jsou "jednorazove" - po uspechu se lokalni seznam
      // vycisti (uz jsou ulozene do shop_cutting_manual_pieces na
      // backendu). Pri CHYBE zustavaji, at je jde opravit a odeslat
      // znovu bez rucniho prepisovani vseho od zacatku.
      cpManualPieces = [];
      _cpRenderManualList();
      if (data && data.plan_id) _cpLoadManualResultTable(data.plan_id);
    },
  );
}
document.getElementById("btnGenerateManualCuttingPlan").onclick = generateManualCuttingPlan;

_cpLoadManualMaterials();
_cpRenderManualList();
_cpManualUpdateDimFields();

function _cpSelectedUnitFilter() {
  const checked = document.querySelector('input[name="cpUnitFilter"]:checked');
  return checked ? checked.value : "pending";
}

async function loadBulkCuttingPlan() {
  if (!document.getElementById("cpGenerateOrderFilter").dataset.loaded) {
    document.getElementById("cpGenerateOrderFilter").dataset.loaded = "1";
    _cpRenderGenerateOrderFilter();
  }
  const progressEl = document.getElementById("bulkOrderProgress");
  const el = document.getElementById("bulkCuttingPlanContent");
  el.className = "hint";
  el.textContent = "Načítám...";
  progressEl.textContent = "";
  try {
    const statusFilter = _cpSelectedUnitFilter();
    const qs = statusFilter ? `?status=${statusFilter}` : "";
    const r = await fetch(`/api/admin/cutting-plan${qs}`);
    if (!r.ok) throw new Error("HTTP " + r.status);
    const data = await r.json();
    renderBulkCuttingUnits(data);
  } catch (e) {
    el.className = "err";
    el.textContent = "Chyba načtení řezného plánu: " + e.message;
  }
}

function renderBulkCuttingUnits(data) {
  const el = document.getElementById("bulkCuttingPlanContent");
  const progressEl = document.getElementById("bulkOrderProgress");
  const materials = data.materials || [];
  const progress = data.order_progress || [];
  const orderColors = data.order_colors || {};

  progressEl.innerHTML = progress.length
    ? "Postup podle objednávky: " + progress.map(p => {
        const done = p.done >= p.total && p.total > 0;
        return `<span style="${done ? 'color:#7ec488;' : ''}">${escapeHtmlAdmin(p.order_number)} (${p.done}/${p.total})</span>`;
      }).join(", ")
    : "";

  if (materials.length === 0) {
    el.className = "hint";
    el.textContent = "Žádné uložené jednotky. Klikni na \"Vygenerovat plán\" výše.";
    return;
  }
  el.className = "";

  let html = "";
  materials.forEach(m => {
    const isProfil = m.cut_kind === "profil";
    const doneCount = m.units.filter(u => u.status === "done").length;
    const swatch = `<span style="display:inline-block;width:12px;height:12px;border-radius:2px;background:${_cpMaterialColor(m.material_key)};margin-right:6px;vertical-align:middle;"></span>`;
    html += `<div style="margin-bottom:16px;">`;
    html += `<div style="font-size:12.5px;color:#c7ccd4;margin-bottom:6px;">${swatch}<strong>${escapeHtmlAdmin(m.material_key)}</strong> `
      + `(${isProfil ? "profil" : "deska"}) - ${m.units.length} ks, ${doneCount} hotovo</div>`;
    m.units.forEach(u => { html += isProfil ? _cpRenderUnitBar(u, orderColors) : _cpRenderUnitSheet(u, orderColors); });
    html += `</div>`;
  });
  el.innerHTML = html;

  el.querySelectorAll(".cp-unit-done-cb").forEach(cb => {
    cb.onchange = () => toggleCuttingPlanUnit(Number(cb.dataset.unitId), cb.checked);
  });
  const visibleIds = new Set();
  materials.forEach(m => m.units.forEach(u => visibleIds.add(u.id)));
  [...cpSelectedUnitIds].forEach(id => { if (!visibleIds.has(id)) cpSelectedUnitIds.delete(id); });
  el.querySelectorAll(".cp-unit-select-cb").forEach(cb => {
    cb.onchange = () => {
      const id = Number(cb.dataset.unitId);
      if (cb.checked) cpSelectedUnitIds.add(id); else cpSelectedUnitIds.delete(id);
      updateCpBulkToolbar();
    };
  });
  // Robert 2026-08: "chybi tam zatrzitko for all" - hromadny vyber vsech
  // prave ZOBRAZENYCH jednotek (respektuje aktivni filtr
  // pending/vse/done); stav zatrzitka se dopocitava i pri rucnim
  // (od)vybrani jednotlivych jednotek (viz updateCpBulkToolbar).
  cpVisibleUnitIds = visibleIds;
  const selAll = document.getElementById("cpSelectAll");
  selAll.onchange = () => {
    if (selAll.checked) visibleIds.forEach(id => cpSelectedUnitIds.add(id));
    else cpSelectedUnitIds.clear();
    el.querySelectorAll(".cp-unit-select-cb").forEach(cb => { cb.checked = selAll.checked; });
    updateCpBulkToolbar();
  };
  updateCpBulkToolbar();
}

async function toggleCuttingPlanUnit(unitId, done) {
  try {
    const r = await fetch(`/api/admin/cutting-plan/units/${unitId}`, {
      method: "PATCH", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: done ? "done" : "pending" }),
    });
    const data = await r.json();
    if (!r.ok) throw new Error(data.error || ("HTTP " + r.status));
    loadBulkCuttingPlan();
    loadCpRemnants();
  } catch (e) {
    alert("Chyba uložení: " + e.message);
    loadBulkCuttingPlan();
  }
}

let cpSelectedUnitIds = new Set();
let cpVisibleUnitIds = new Set();
function _cpUnitCheckbox(unit) {
  const label = unit.status === "done" ? "Hotovo" : "Označit hotové";
  return `<label style="font-size:11px;color:#9aa4b2;margin-left:10px;">
    <input type="checkbox" class="cp-unit-select-cb" data-unit-id="${unit.id}" ${cpSelectedUnitIds.has(unit.id) ? "checked" : ""}> Vybrat
  </label>
  <label style="font-size:11px;color:#9aa4b2;margin-left:6px;">
    <input type="checkbox" class="cp-unit-done-cb" data-unit-id="${unit.id}" ${unit.status === "done" ? "checked" : ""}> ${label}
  </label>`;
}
function updateCpBulkToolbar() {
  const bar = document.getElementById("cpBulkToolbar");
  const count = cpSelectedUnitIds.size;
  bar.classList.toggle("active", count > 0);
  document.getElementById("cpBulkCount").textContent = `${count} vybráno`;
  // synchronizace "Vybrat vse": zaskrtnute jen kdyz jsou vybrane VSECHNY
  // prave zobrazene jednotky (a nejaka existuje)
  const selAll = document.getElementById("cpSelectAll");
  if (selAll) selAll.checked = cpVisibleUnitIds.size > 0 && [...cpVisibleUnitIds].every(id => cpSelectedUnitIds.has(id));
}
async function cpBulkSetStatus(status) {
  if (!cpSelectedUnitIds.size) return;
  const r = await fetch("/api/admin/cutting-plan/units/bulk-status", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ids: [...cpSelectedUnitIds], status }),
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) { alert(data.error || "Chyba při ukládání."); return; }
  cpSelectedUnitIds.clear();
  loadBulkCuttingPlan();
  loadCpRemnants();
}
document.getElementById("cpBulkMarkDone").onclick = () => cpBulkSetStatus("done");
document.getElementById("cpBulkMarkPending").onclick = () => cpBulkSetStatus("pending");
// Robert 2026-08: "dej reznym planum bulk mazani" - trvale SMAZE vybrane
// jednotky (vc. hotovych); backend zaroven uklidi plany bez jednotek.
document.getElementById("cpBulkDelete").onclick = async () => {
  if (!cpSelectedUnitIds.size) return;
  if (!confirm(`Trvale smazat ${cpSelectedUnitIds.size} vybraných jednotek řezného plánu? Tohle nejde vrátit.`)) return;
  const r = await fetch("/api/admin/cutting-plan/units/bulk-delete", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ids: [...cpSelectedUnitIds] }),
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) { alert(data.error || "Chyba při mazání."); return; }
  cpSelectedUnitIds.clear();
  loadBulkCuttingPlan();
  loadCpRemnants();
};

function _cpRenderUnitBar(unit, orderColors) {
  const maxW = 560;
  const scale = maxW / unit.stock_length_mm;
  const h = 34;
  let x = 0;
  let rects = "";
  const dim = unit.status === "done" ? "opacity:0.55;" : "";
  unit.pieces.forEach((p, i) => {
    const w = p.length_mm * scale;
    // bot4, 2026-07-26 (Robert: "barva obřezávaného dílu ať se ošetří
    // podle zakázky") - barva podle objednavky (viz orderColors,
    // GET .../cutting-plan -> order_colors, prirazovano/uvolnovano na
    // backendu _sync_order_colors), fallback na indexovou barvu jen
    // pokud kus nema order_number (nemelo by nastat v ostrem provozu).
    const color = (orderColors && orderColors[p.order_number]) || CP_COLORS[i % CP_COLORS.length];
    const title = _cpEsc(p.label) + " - " + Math.round(p.length_mm) + " mm" + (p.order_number ? " (obj. " + _cpEsc(p.order_number) + ")" : "");
    rects += `<rect x="${x.toFixed(1)}" y="0" width="${w.toFixed(1)}" height="${h}" fill="${color}" stroke="#1b1e24" stroke-width="1"><title>${title}</title></rect>`;
    if (w > 44 && p.order_number) {
      rects += `<text x="${(x + w / 2).toFixed(1)}" y="${h / 2 - 2}" font-size="9.5" fill="#12141a" text-anchor="middle">${Math.round(p.length_mm)}</text>`;
      rects += `<text x="${(x + w / 2).toFixed(1)}" y="${h / 2 + 10}" font-size="7.5" fill="#12141a" text-anchor="middle">${_cpEsc(p.order_number)}</text>`;
    } else if (w > 26) {
      rects += `<text x="${(x + w / 2).toFixed(1)}" y="${h / 2 + 4}" font-size="10" fill="#12141a" text-anchor="middle">${Math.round(p.length_mm)}</text>`;
    }
    x += w;
  });
  const wasteW = maxW - x;
  if (wasteW > 0.5) {
    rects += `<rect x="${x.toFixed(1)}" y="0" width="${wasteW.toFixed(1)}" height="${h}" fill="#2a2e37" stroke="#1b1e24" stroke-width="1"></rect>`;
  }
  const swatch = `<span style="display:inline-block;width:11px;height:11px;border-radius:2px;background:${_cpMaterialColor(unit.stock_label)};margin-right:6px;vertical-align:middle;"></span>`;
  const counter = unit.unit_count_total ? `<span style="color:#6f95c4;">Tyč ${unit.unit_index}/${unit.unit_count_total}</span> - ` : "";
  const zakazkaTxt = unit.zakazka ? ` &middot; zakázka: <span style="color:#c7ccd4;">${_cpEsc(unit.zakazka)}</span>` : "";
  const utilTxt = unit.utilization_percent != null ? `${unit.utilization_percent} %` : "?";
  const kerfTxt = unit.kerf_mm != null ? `${unit.kerf_mm} mm` : "?";
  const cutsTxt = unit.cuts_count != null ? unit.cuts_count : "?";
  // Robert 2026-08-06: "zásoba zbytků vzniklých řezáním" - jednotka
  // narezana ze ZBYTKU (misto cerstve 3000mm tyce) je na dilne dobre
  // videt, aby se nespletla s beznou tyci.
  const remnantBadge = unit.is_remnant
    ? ` <span style="background:#3a5a3a;color:#a8e8a8;border-radius:3px;padding:1px 6px;font-size:10px;">♻ ze zbytku</span>` : "";
  return `<div style="margin:6px 0;${dim}">
    <div style="font-size:11.5px;color:#c7ccd4;margin-bottom:2px;">${swatch}${counter}<strong>${_cpEsc(unit.stock_label)}</strong>${remnantBadge}${zakazkaTxt}</div>
    <div style="font-size:10.5px;color:#8b93a1;margin-bottom:3px;">využito ${Math.round(unit.used_amount)}/${Math.round(unit.stock_length_mm)} mm (${utilTxt}), odpad ${Math.round(unit.waste_amount)} mm, šířka řezu ${kerfTxt}, ${cutsTxt} řezů${_cpUnitCheckbox(unit)}</div>
    <svg width="${maxW}" height="${h}" style="display:block;">${rects}</svg>
  </div>`;
}

function _cpRenderUnitSheet(unit, orderColors) {
  const maxW = 320;
  const scale = maxW / unit.stock_width_mm;
  const h = unit.stock_height_mm * scale;
  let rects = "";
  let hasAnyEdgeBand = false;
  const dim = unit.status === "done" ? "opacity:0.55;" : "";
  unit.pieces.forEach((p, i) => {
    const x = p.x_mm * scale, y = p.y_mm * scale, w = p.width_mm * scale, ph = p.height_mm * scale;
    // bot4, 2026-07-26 (Robert: "barva obřezávaného dílu ať se ošetří
    // podle zakázky") - barva podle objednavky (viz orderColors).
    const color = (orderColors && orderColors[p.order_number]) || CP_COLORS[i % CP_COLORS.length];
    const title = _cpEsc(p.label) + " - " + Math.round(p.width_mm) + "×" + Math.round(p.height_mm) + " mm" + (p.order_number ? " (obj. " + _cpEsc(p.order_number) + ")" : "");
    rects += `<rect x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${w.toFixed(1)}" height="${ph.toFixed(1)}" fill="${color}" stroke="#1b1e24" stroke-width="1"><title>${title}</title></rect>`;
    // bot4, 2026-07-26 (Robert, 2. referencni obrazek - kotovani kazde
    // hrany, ne jen stredovy rozmer): sirka podel horniho okraje, vyska
    // (otoceny text) podel leveho okraje - stejny princip jako realny CAM
    // export, bez slozite rekonstrukce sdilenych kotovacich car mezi
    // sousednimi kusy (viz AGENTS_LOG.md - vetsi rozsah za marginalni
    // prinos pro dilnu).
    if (w > 18) {
      rects += `<text x="${(x + w / 2).toFixed(1)}" y="${(y + 9).toFixed(1)}" font-size="8" fill="#12141a" text-anchor="middle">${Math.round(p.width_mm)}</text>`;
    }
    if (ph > 18) {
      const ly = (y + ph / 2).toFixed(1), lx = (x + 9).toFixed(1);
      rects += `<text x="${lx}" y="${ly}" font-size="8" fill="#12141a" text-anchor="middle" transform="rotate(-90 ${lx} ${ly})">${Math.round(p.height_mm)}</text>`;
    }
    // bot4, 2026-07-26 (Robert: "popis (číslo objednávky) dílu uprostřed")
    if (w > 44 && ph > 22 && p.order_number) {
      rects += `<text x="${(x + w / 2 + 8).toFixed(1)}" y="${(y + ph / 2 + 3).toFixed(1)}" font-size="9" fill="#12141a" text-anchor="middle" font-weight="600">${_cpEsc(p.order_number)}</text>`;
    }
    // bot4, 2026-07-26: barevne zvyrazneni olepenych hran (ABS 2mm) - dle
    // referencniho CAM softwaru. Deklarovane strany premapovane na vizualni
    // dle "rotated" (viz _cpVisualEdges).
    const edges = _cpVisualEdges(p);
    if (edges.top || edges.bottom || edges.left || edges.right) {
      hasAnyEdgeBand = true;
      const bw = 3;
      if (edges.top) rects += `<line x1="${x.toFixed(1)}" y1="${(y + bw / 2).toFixed(1)}" x2="${(x + w).toFixed(1)}" y2="${(y + bw / 2).toFixed(1)}" stroke="${CP_EDGE_BAND_COLOR}" stroke-width="${bw}"></line>`;
      if (edges.bottom) rects += `<line x1="${x.toFixed(1)}" y1="${(y + ph - bw / 2).toFixed(1)}" x2="${(x + w).toFixed(1)}" y2="${(y + ph - bw / 2).toFixed(1)}" stroke="${CP_EDGE_BAND_COLOR}" stroke-width="${bw}"></line>`;
      if (edges.left) rects += `<line x1="${(x + bw / 2).toFixed(1)}" y1="${y.toFixed(1)}" x2="${(x + bw / 2).toFixed(1)}" y2="${(y + ph).toFixed(1)}" stroke="${CP_EDGE_BAND_COLOR}" stroke-width="${bw}"></line>`;
      if (edges.right) rects += `<line x1="${(x + w - bw / 2).toFixed(1)}" y1="${y.toFixed(1)}" x2="${(x + w - bw / 2).toFixed(1)}" y2="${(y + ph).toFixed(1)}" stroke="${CP_EDGE_BAND_COLOR}" stroke-width="${bw}"></line>`;
    }
  });
  const legend = hasAnyEdgeBand
    ? `<div style="font-size:10px;color:#8b93a1;margin-top:3px;"><span style="display:inline-block;width:14px;height:3px;background:${CP_EDGE_BAND_COLOR};margin-right:4px;vertical-align:middle;"></span>olepená hrana (ABS 2mm)</div>`
    : "";
  const swatch = `<span style="display:inline-block;width:11px;height:11px;border-radius:2px;background:${_cpMaterialColor(unit.stock_label)};margin-right:6px;vertical-align:middle;"></span>`;
  const counter = unit.unit_count_total ? `<span style="color:#6f95c4;">Deska ${unit.unit_index}/${unit.unit_count_total}</span> - ` : "";
  const zakazkaTxt = unit.zakazka ? ` &middot; zakázka: <span style="color:#c7ccd4;">${_cpEsc(unit.zakazka)}</span>` : "";
  const utilTxt = unit.utilization_percent != null ? `${unit.utilization_percent} %` : "?";
  const kerfTxt = unit.kerf_mm != null ? `${unit.kerf_mm} mm` : "?";
  const cutsTxt = unit.cuts_count != null ? unit.cuts_count : "?";
  return `<div style="margin:6px 14px 10px 0;display:inline-block;vertical-align:top;max-width:${maxW}px;${dim}">
    <div style="font-size:11.5px;color:#c7ccd4;margin-bottom:2px;">${swatch}${counter}<strong>${_cpEsc(unit.stock_label)}</strong>${zakazkaTxt}</div>
    <div style="font-size:10.5px;color:#8b93a1;margin-bottom:3px;">využito ${utilTxt}, odpad ${Math.round(unit.waste_amount / 1000)} cm², šířka řezu ${kerfTxt}, ${cutsTxt} řezů${_cpUnitCheckbox(unit)}</div>
    <svg width="${maxW.toFixed(1)}" height="${h.toFixed(1)}" style="display:block;border:1px solid #333;">
      <rect x="0" y="0" width="${maxW.toFixed(1)}" height="${h.toFixed(1)}" fill="#2a2e37"></rect>
      ${rects}
    </svg>
    ${legend}
  </div>`;
}

document.getElementById("btnGenerateCuttingPlan").onclick = generateCuttingPlan;
document.getElementById("btnCuttingPlanRefresh").onclick = loadBulkCuttingPlan;
document.querySelectorAll('input[name="cpUnitFilter"]').forEach(r => { r.onchange = loadBulkCuttingPlan; });

// ==================== ZASOBA ZBYTKU (Robert 2026-08-06) ====================
async function loadCpRemnants() {
  const tbody = document.getElementById("cpRemnantsTbody");
  tbody.innerHTML = '<tr><td colspan="5" style="color:#666;">Načítám...</td></tr>';
  try {
    const r = await fetch("/api/admin/cutting-plan/remnants");
    if (!r.ok) throw new Error("HTTP " + r.status);
    const data = await r.json();
    const remnants = data.remnants || [];
    if (!remnants.length) {
      tbody.innerHTML = '<tr><td colspan="5" style="color:#666;">Žádné zbytky v zásobě.</td></tr>';
      return;
    }
    tbody.innerHTML = remnants.map(rm => {
      const statusLabel = rm.status === "available"
        ? '<span style="color:#7ec488;">Volný</span>'
        : `<span style="color:#8b93a1;">Použitý (jednotka #${rm.used_by_unit_id})</span>`;
      const created = rm.created_at ? new Date(rm.created_at).toLocaleString("cs-CZ") : "";
      const delBtn = rm.status === "available"
        ? `<button type="button" class="cp-remnant-delete" data-id="${rm.id}" style="background:none;border:1px solid #3a3f4a;color:#e07070;padding:2px 8px;">Smazat</button>`
        : "";
      return `<tr>
        <td>${escapeHtmlAdmin(rm.material_key)}</td>
        <td>${Math.round(rm.length_mm)} mm</td>
        <td>${statusLabel}</td>
        <td>${created}</td>
        <td>${delBtn}</td>
      </tr>`;
    }).join("");
    tbody.querySelectorAll(".cp-remnant-delete").forEach(btn => {
      btn.onclick = () => deleteCpRemnant(parseInt(btn.dataset.id, 10));
    });
  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="5" class="err">Chyba načtení: ${escapeHtmlAdmin(e.message)}</td></tr>`;
  }
}

async function deleteCpRemnant(id) {
  if (!confirm("Opravdu smazat tento zbytek ze zásoby?")) return;
  try {
    const r = await fetch(`/api/admin/cutting-plan/remnants/${id}`, { method: "DELETE" });
    const data = await r.json();
    if (!r.ok) { alert(data.error || "Chyba při mazání."); return; }
    loadCpRemnants();
  } catch (e) {
    alert("Chyba při mazání: " + e.message);
  }
}

document.getElementById("btnCpRemnantsRefresh").onclick = loadCpRemnants;
loadCpRemnants();

// ==================== REZNY PLAN - DIAGNOSTICKY (per objednavka, ZIVY vypocet) ====================
// Zdroj dat: GET /api/admin/orders/<id>/cutting-plan - NEUKLADA nic, jen
// nahled "co presne je v TETO objednavce k rezani" (viz cutting.py
// docstring). Tvar odpovedi (plans[].plan.bars/sheets) je JINY nez
// hromadny perzistentni pohled vyse (materials[].units[]).
function renderCuttingPlan(data, containerId) {
  const el = document.getElementById(containerId);
  const plans = data.plans || [];
  const noDim = data.items_without_dimensions || [];

  if (plans.length === 0 && noDim.length === 0) {
    el.className = "hint";
    el.textContent = "Tato objednávka neobsahuje žádné položky k řezání (žádný profil ani deska s vyplněnými rozměry).";
    return;
  }
  el.className = "";

  let html = "";
  plans.forEach(p => {
    if (p.error) {
      html += `<div class="err" style="margin-bottom:10px;">${_cpEsc(p.material_key)} (${_cpEsc(p.cut_kind)}): ${_cpEsc(p.error)}</div>`;
      return;
    }
    const isProfil = p.cut_kind === "profil";
    const stats = p.plan.stats;
    html += `<div style="margin-bottom:16px;">`;
    html += `<div style="font-size:12.5px;color:#c7ccd4;margin-bottom:6px;"><strong>${_cpEsc(p.material_key)}</strong> (${isProfil ? "profil" : "deska"}, kerf ${p.kerf_mm} mm) - `;
    if (isProfil) {
      html += `${stats.bars_used} ks tyčí, odpad ${Math.round(stats.total_waste_mm)} mm, ${stats.total_cuts} řezů`;
    } else {
      const wastePct = stats.total_stock_area_mm2 ? Math.round(1000 * stats.total_waste_area_mm2 / stats.total_stock_area_mm2) / 10 : 0;
      html += `${stats.sheets_used} ks desek, odpad ${wastePct} % plochy`;
    }
    if (stats.total_price_czk) html += `, materiál ${stats.total_price_czk.toLocaleString("cs-CZ")} Kč`;
    html += `</div>`;

    const units = isProfil ? p.plan.bars : p.plan.sheets;
    units.forEach(u => { html += isProfil ? _cpRenderBar(u) : _cpRenderSheet(u); });

    if ((p.plan.unplaced || []).length) {
      html += `<div class="err" style="margin-top:4px;">Nevešlo se: ` +
        p.plan.unplaced.map(u => `${_cpEsc(u.label)} × ${u.qty}`).join(", ") + `</div>`;
    }
    html += `</div>`;
  });

  el.innerHTML = html;
}

function _cpRenderBar(bar) {
  const maxW = 560;
  const scale = maxW / bar.stock_length_mm;
  const h = 34;
  let x = 0;
  let rects = "";
  const orderSet = new Set();
  bar.pieces.forEach((p, i) => {
    const w = p.length_mm * scale;
    const color = CP_COLORS[i % CP_COLORS.length];
    if (p.order_number) orderSet.add(p.order_number);
    const title = _cpEsc(p.label) + " - " + Math.round(p.length_mm) + " mm";
    rects += `<rect x="${x.toFixed(1)}" y="0" width="${w.toFixed(1)}" height="${h}" fill="${color}" stroke="#1b1e24" stroke-width="1"><title>${title}</title></rect>`;
    if (w > 26) {
      rects += `<text x="${(x + w / 2).toFixed(1)}" y="${h / 2 + 4}" font-size="10" fill="#1b1e24" text-anchor="middle">${Math.round(p.length_mm)}</text>`;
    }
    x += w;
  });
  const wasteW = maxW - x;
  if (wasteW > 0.5) {
    rects += `<rect x="${x.toFixed(1)}" y="0" width="${wasteW.toFixed(1)}" height="${h}" fill="#2a2e37" stroke="#1b1e24" stroke-width="1"></rect>`;
  }
  // bot2: kazdy kus ma napovedu (title) s cislem objednavky pri najeti mysi
  // (viz "label" - obsahuje "(obj. XXX)", sestavuje backend v cutting.py) +
  // pod tycí souhrnny radek "Objednavky na teto tyci", aby bylo videt i
  // bez najeti mysi, kam jednotlive kusy patri (klicove pro HROMADNY plan
  // pres vice objednavek - Robert 2026-07-25).
  const ordersLine = orderSet.size
    ? `<div style="font-size:10.5px;color:#6f95c4;margin-top:2px;">Objednávky na této tyči: ${Array.from(orderSet).map(_cpEsc).join(", ")}</div>`
    : "";
  return `<div style="margin:6px 0;">
    <div style="font-size:11px;color:#8b93a1;margin-bottom:2px;">${_cpEsc(bar.stock_label)} - využito ${Math.round(bar.used_mm)}/${Math.round(bar.stock_length_mm)} mm, odpad ${Math.round(bar.waste_mm)} mm</div>
    <svg width="${maxW}" height="${h}" style="display:block;">${rects}</svg>
    ${ordersLine}
  </div>`;
}

function _cpRenderSheet(sheet) {
  const maxW = 320;
  const scale = maxW / sheet.width_mm;
  const h = sheet.height_mm * scale;
  let rects = "";
  const orderSet = new Set();
  sheet.pieces.forEach((p, i) => {
    const x = p.x_mm * scale, y = p.y_mm * scale, w = p.width_mm * scale, ph = p.height_mm * scale;
    const color = CP_COLORS[i % CP_COLORS.length];
    if (p.order_number) orderSet.add(p.order_number);
    const title = _cpEsc(p.label) + " - " + Math.round(p.width_mm) + "×" + Math.round(p.height_mm) + " mm";
    rects += `<rect x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${w.toFixed(1)}" height="${ph.toFixed(1)}" fill="${color}" stroke="#1b1e24" stroke-width="1"><title>${title}</title></rect>`;
    if (w > 30 && ph > 14) {
      rects += `<text x="${(x + w / 2).toFixed(1)}" y="${(y + ph / 2 + 3).toFixed(1)}" font-size="9" fill="#1b1e24" text-anchor="middle">${Math.round(p.width_mm)}×${Math.round(p.height_mm)}</text>`;
    }
  });
  const ordersLine = orderSet.size
    ? `<div style="font-size:10.5px;color:#6f95c4;margin-top:2px;max-width:${maxW}px;">Objednávky na této desce: ${Array.from(orderSet).map(_cpEsc).join(", ")}</div>`
    : "";
  return `<div style="margin:6px 14px 6px 0;display:inline-block;vertical-align:top;">
    <div style="font-size:11px;color:#8b93a1;margin-bottom:2px;">${_cpEsc(sheet.stock_label)} - odpad ${Math.round(sheet.waste_area_mm2 / 1000)} cm²</div>
    <svg width="${maxW.toFixed(1)}" height="${h.toFixed(1)}" style="display:block;border:1px solid #333;">
      <rect x="0" y="0" width="${maxW.toFixed(1)}" height="${h.toFixed(1)}" fill="#2a2e37"></rect>
      ${rects}
    </svg>
    ${ordersLine}
  </div>`;
}

// bot2: "dotazeni" bot4 navrhu (NAVRH_REZNE_PLANY.md bod 4 - "tlacitko
// export PDF, na dilnu") - zadny backend PDF endpoint pro rezny plan
// neexistuje (na rozdil od faktur/dodacich listu v documents.py), takze
// misto predstirani serverove generovane PDF pouzivam primociary tisk
// pres tiskovy dialog prohlizece (uzivatel muze zvolit "Ulozit jako
// PDF") - funkcne stejny vysledek pro "vzit si to na dilnu", bez
// vymysleni noveho backend kontraktu, ktery nikdo nezadal.
function printCuttingPlanArea(containerId, heading) {
  const content = cpToPrintSafeColors(document.getElementById(containerId).innerHTML);
  const w = window.open("", "_blank");
  if (!w) {
    alert("Prohlížeč zablokoval nové okno pro tisk. Povolte vyskakovací okna a zkuste to znovu.");
    return;
  }
  w.document.write(`<!DOCTYPE html><html lang="cs"><head><meta charset="utf-8"><title>${_cpEsc(heading)}</title>
    <style>
      body { font-family: Arial, sans-serif; color: #111; background: #fff; padding: 20px; }
      h1 { font-size: 16px; margin-bottom: 14px; }
    </style>
  </head><body>
    <h1>${_cpEsc(heading)}</h1>
    ${content}
  </body></html>`);
  w.document.close();
  w.focus();
  setTimeout(() => w.print(), 300);
}

document.getElementById("btnPrintBulkCuttingPlan").onclick = () => {
  printCuttingPlanArea("bulkCuttingPlanContent", "Hromadný řezný plán - " + new Date().toLocaleDateString("cs-CZ"));
};
document.getElementById("btnPrintOrderCuttingPlan").onclick = () => {
  const title = document.getElementById("orderModalTitle").textContent || "Objednávka";
  printCuttingPlanArea("cuttingPlanContent", "Řezný plán - " + title);
};
