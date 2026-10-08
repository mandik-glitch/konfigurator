// ==================== CENY ====================
const PRICES_API = "/api/admin/profily";
let priceRows = [];

// bot16, 2026-09-24 (Robert pres bot3, WORKFLOW.md pravidlo 52 "nic se
// neodklada" + pravidlo 9 "kurz vzdy zive, nikdy hardcoded/stale") -
// zivy kurz Fio "Devizove kurzy, Prodej" pro sloupec "Cena v Kc (zivy
// kurz Fio)" hned vedle "Cena USD (Dogus)". POZOR: tohle NENI totez
// jako row.dogus_price_usd_fetched_at/shop_products.dogus_price_rate_used
// (kurz POUZITY pri POSLEDNIM TYDENNIM prepoctu) - je to aktualni kurz
// stazeny PRAVE TED, pri kazdem loadPrices() volani (viz nize).
let fioLiveRate = null;        // number | null - Kc za 1 USD, nebo null kdyz zivy fetch selhal
let fioLiveRateFetchedAt = null; // ISO timestamp tohohle konkretniho pokusu o stazeni
let fioLiveRateError = null;   // string | null

function fmtCross(mm) { return mm[0] + "×" + mm[1] + " mm"; }

// bot16, 2026-09-24: bunka sloupce "Cena v Kc (zivy kurz Fio)" - prosty
// prevod USD ceny Dogus zivym kurzem, s celym vypoctem vypsanym v bunce
// (ne jen vysledek). Tri stavy: (1) neni USD cena od Dogus -> "-" jako
// u sousedniho sloupce, (2) USD cena JE, ale zivy kurz se nepodarilo
// stahnout -> cervene "kurz nedostupny" (WORKFLOW.md pravidlo 9 - zadna
// stara/odhadnuta hodnota misto toho), (3) oboje k dispozici -> vysledna
// Kc cena + cely vzorec pod ni.
function fmtLiveCzkCell(row) {
  if (row.dogus_price_usd == null) {
    return "<span style=\"color:#666;\">—</span>";
  }
  if (fioLiveRate == null) {
    return "<span style=\"color:#b33;\">kurz nedostupný</span>";
  }
  const czk = row.dogus_price_usd * fioLiveRate;
  return (
    `${czk.toLocaleString("cs-CZ", { maximumFractionDigits: 2 })} Kč` +
    `<div style="font-size:10.5px;color:#666;margin-top:2px;">` +
    `${row.dogus_price_usd.toFixed(2)} $ × ${fioLiveRate.toFixed(3)} Kč/$ = ${czk.toFixed(2)} Kč` +
    `</div>`
  );
}

// bot16, 2026-09-24: bunka sloupce "Cena logiman.cz (Kč/1m)" - cte
// hotova data z admin_profily_list() (viz api/admin_profily.py, JOIN na
// logiman_cz_price_reference pres SKU), zadny live fetch tady. Ctyri
// stavy: (1) nas profil nema parovane SKU vubec (zadny navazany
// shop_products, nebo produkt bez sku) -> "—", (2) SKU mame, ale crawl
// pro nej na logiman.cz nic nenasel -> cervene "SKU nenalezeno" (zadna
// domnenka/odhad), (3) stranka nalezena, ale nema radek "Měrná cena"
// (kusove zbozi typu zaslepky) -> "bez ceny/m" + odkaz, (4) plna shoda ->
// cena + odkaz na produkt (aby si Robert mohl sam proklikem overit) +
// cely vypocet rozdilu oproti nasi cene, kdyz ji mame.
function fmtLogimanCell(row) {
  if (!row.logiman_sku) {
    return "<span style=\"color:#666;\">—</span>";
  }
  if (!row.logiman_product_url) {
    return "<span style=\"color:#b33;\">SKU nenalezeno</span>" +
      `<div style="font-size:10.5px;color:#666;margin-top:2px;">SKU ${escapeHtmlAdmin(row.logiman_sku)}</div>`;
  }
  const link = `<a href="${row.logiman_product_url}" target="_blank" rel="noopener noreferrer" style="font-size:10.5px;">logiman.cz ↗</a>`;
  if (row.logiman_price_per_m_czk == null) {
    return `<span style="color:#666;">bez ceny/m</span><div style="margin-top:2px;">${link}</div>`;
  }
  let diffHtml = "";
  if (row.price_czk_per_m != null) {
    const diff = row.price_czk_per_m - row.logiman_price_per_m_czk;
    const smer = diff > 0 ? "dráž" : (diff < 0 ? "levněji" : "stejně");
    diffHtml =
      `<div style="font-size:10.5px;color:#666;margin-top:2px;">` +
      `naše ${row.price_czk_per_m.toFixed(2)} − jejich ${row.logiman_price_per_m_czk.toFixed(2)} = ${diff.toFixed(2)} Kč/m (u nás ${smer})` +
      `</div>`;
  }
  return (
    `${row.logiman_price_per_m_czk.toLocaleString("cs-CZ", { maximumFractionDigits: 2 })} Kč/m` +
    `<div style="margin-top:2px;">${link}</div>` +
    diffHtml
  );
}

function fmtFbxDate(iso) {
  try {
    const d = new Date(iso);
    return d.toLocaleDateString("cs-CZ") + " " + d.toLocaleTimeString("cs-CZ", { hour: "2-digit", minute: "2-digit" });
  } catch (e) {
    return "";
  }
}

// bot1, 2026-07-27: Robert upozornil, ze 5 puvodnich profilu (Object_1/2/7/
// 11/14) uz ma FUNKCNI model primo ve 3D scene (nahraný jinou cestou, ne
// pres tenhle admin upload) - predtim jim tabulka pisala zavadejici "zadny
// model", i kdyz ve scene bezne fungujou. "has_scene_model" (z backendu,
// odvozeno z toho, ze cfg_dily.glb_file NENI "_PENDING_..." placeholder)
// tohle rozlisuje.
function fbxStatusText(row) {
  if (row.fbx_original_name) {
    return "✓ " + escapeHtmlAdmin(row.fbx_original_name) + (row.fbx_uploaded_at ? " (" + fmtFbxDate(row.fbx_uploaded_at) + ")" : "");
  }
  if (row.has_scene_model) {
    return "✓ model už je ve 3D scéně";
  }
  return "žádný model";
}

async function uploadFbxFile(i, tr, file) {
  const statusEl = tr.querySelector(".fbx-status");
  const prevText = statusEl.textContent;
  statusEl.textContent = "nahrávám a převádím na 3D model…";
  try {
    const fd = new FormData();
    fd.append("file", file);
    const r = await fetch(`/api/admin/profily/${priceRows[i].id}/fbx-upload`, { method: "POST", body: fd });
    const data = await r.json();
    if (!r.ok) throw new Error(data.error || ("HTTP " + r.status));
    priceRows[i].fbx_original_name = data.fbx_original_name;
    priceRows[i].fbx_uploaded_at = new Date().toISOString();
    const conv = data.conversion || {};
    // bot1, 2026-07-27: Robert: "jakmile se fbx modely nahrajou supni je do
    // sceny do katalogu" - uspesny prevod rovnou nastavi has_scene_model,
    // takze staci prekreslit status bez nutnosti znovu volat loadPrices().
    if (conv.success) {
      priceRows[i].has_scene_model = true;
      statusEl.textContent = "✓ nahráno a zobrazeno ve 3D scéně (" + escapeHtmlAdmin(data.fbx_original_name) + ", " + fmtFbxDate(priceRows[i].fbx_uploaded_at) + ")";
    } else if (conv.attempted) {
      statusEl.textContent = "⚠ nahráno (" + escapeHtmlAdmin(data.fbx_original_name) + "), převod do 3D selhal: " + escapeHtmlAdmin(conv.error || "neznámá chyba");
    } else {
      statusEl.textContent = "✓ nahráno (" + escapeHtmlAdmin(data.fbx_original_name) + "), automatický převod nedostupný";
    }
    tr.querySelector(".btn-fbx-upload").textContent = "Nahradit";
  } catch (e) {
    statusEl.textContent = prevText + " (chyba: " + e.message + ")";
  }
}

// bot16, 2026-09-24: samostatna funkce (ne soucast loadPrices try/catch),
// aby selhani ziveho kurzu NIKDY nezablokovalo/neshodilo nacteni zbytku
// tabulky - jen se sloupec "Cena v Kc (zivy kurz)" zobrazi jako
// nedostupny (viz renderFioRateStatus/renderPrices nize).
async function loadFioRate() {
  try {
    const r = await fetch("/api/admin/profily/fio-rate");
    const data = await r.json();
    if (!r.ok || data.rate == null) {
      fioLiveRate = null;
      fioLiveRateFetchedAt = data.fetched_at || null;
      fioLiveRateError = data.error || ("HTTP " + r.status);
    } else {
      fioLiveRate = data.rate;
      fioLiveRateFetchedAt = data.fetched_at;
      fioLiveRateError = null;
    }
  } catch (e) {
    fioLiveRate = null;
    fioLiveRateFetchedAt = null;
    fioLiveRateError = e.message;
  }
  renderFioRateStatus();
}

function renderFioRateStatus() {
  const el = document.getElementById("fioRateStatus");
  if (!el) return;
  if (fioLiveRate != null) {
    el.innerHTML =
      `Živý kurz Fio (Devizové kurzy, Prodej): <strong>${fioLiveRate.toFixed(3)} Kč/USD</strong>` +
      (fioLiveRateFetchedAt ? ` — staženo právě teď (${fmtFbxDate(fioLiveRateFetchedAt)})` : "") +
      ` <button id="btnRefreshFioRate" style="margin-left:8px;">↻ Obnovit kurz</button>` +
      ` <div style="color:#666;font-size:11.5px;margin-top:2px;">Pozor: tohle NENÍ totéž jako kurz u "staženo …" pod cenou USD (Dogus) níže — ten je kurz POUŽITÝ PŘI POSLEDNÍM TÝDENNÍM PŘEPOČTU cen (historický záznam). Tady vidíš AKTUÁLNÍ kurz, stažený právě při otevření/obnovení téhle záložky.</div>`;
  } else {
    el.innerHTML =
      `<span style="color:#b33;">⚠ Živý kurz Fio se nepodařilo stáhnout${fioLiveRateError ? " (" + escapeHtmlAdmin(fioLiveRateError) + ")" : ""} — sloupec "Cena v Kč (živý kurz Fio)" zůstává prázdný ("kurz nedostupný"), NEPOUŽÍVÁ se žádná stará/odhadnutá hodnota.</span>` +
      ` <button id="btnRefreshFioRate" style="margin-left:8px;">↻ Zkusit znovu</button>`;
  }
  const btn = document.getElementById("btnRefreshFioRate");
  if (btn) {
    btn.onclick = async () => {
      el.textContent = "Načítám živý kurz…";
      await loadFioRate();
      renderPrices();
    };
  }
}

async function loadPrices() {
  try {
    // Zivy kurz se stahuje soubezne s tabulkou - kazde nacteni/obnoveni
    // teto zalozky (pravidlo 9) tak vzdy dostane cerstvy kurz, ne
    // hodnotu z predchoziho volani.
    const [r] = await Promise.all([fetch(PRICES_API), loadFioRate()]);
    if (!r.ok) throw new Error("HTTP " + r.status);
    const data = await r.json();
    priceRows = data.rows || [];
    renderPrices();
  } catch (e) {
    document.getElementById("loadErr").textContent = "Nepodařilo se načíst data (" + e.message + ").";
  }
}

// Robert 2026-08-06 ("zkusím ti 1 nohu nahrát, udělej proto nějaký
// můstek do scény tvary"): novy dil katalogu primo z hotoveho FBX/STEP
// modelu (misto skladani z existujicich profilu v custom_shapes, ktere
// u slozitejsich tvaru "melo chyby") - viz POST /api/admin/profily/new.
document.getElementById("btnNewPartUpload").onclick = async () => {
  const statusEl = document.getElementById("newPartStatus");
  const name = document.getElementById("newPartName").value.trim();
  const fileInput = document.getElementById("newPartFile");
  const file = fileInput.files[0];
  if (!name) { statusEl.textContent = "Vyplň název dílu."; return; }
  if (!file) { statusEl.textContent = "Vyber soubor (.fbx/.stp/.step)."; return; }
  statusEl.textContent = "nahrávám a převádím na 3D model…";
  try {
    const fd = new FormData();
    fd.append("name", name);
    fd.append("file", file);
    const r = await fetch("/api/admin/profily/new", { method: "POST", body: fd });
    const data = await r.json();
    if (!r.ok) throw new Error(data.error || ("HTTP " + r.status));
    const conv = data.conversion || {};
    if (conv.success) {
      statusEl.textContent = `✓ díl "${data.id}" založen a zobrazen ve 3D scéně (${escapeHtmlAdmin(data.fbx_original_name)}). Otevři scénu, vlož ho a zkontroluj konektory.`;
      document.getElementById("newPartName").value = "";
      fileInput.value = "";
    } else {
      statusEl.textContent = `⚠ díl "${data.id}" založen, ale převod do 3D selhal: ${escapeHtmlAdmin(conv.error || "neznámá chyba")}`;
    }
    loadPrices();
  } catch (e) {
    statusEl.textContent = "Chyba: " + e.message;
  }
};

// Hromadny import noh (bot5, 2026-08-06) - kazdy FBX se na serveru
// ROZLOZI na katalogove profily (leg_fbx_import.py) a ulozi jako novy
// Vlastni tvar. Sekvencni smycka, jeden fetch na soubor - FBX prevod
// nema vlastni timeout a gunicorn/nginx maji limit 60s na request,
// jeden velky spolecny request by mohl celou davku shodit; navic
// izolace chyb (spatny soubor neshodi zbytek davky) - stejny zamer,
// jaky dokumentuje car_bodies_upload v app.py.
// Robert 2026-08-06 ("uprav tak, abych mohl nahrat strom - adresare se
// soubory"): druhy input s webkitdirectory - prohlizec preda VSECHNY
// soubory z vybrane slozky vc. relativni cesty (webkitRelativePath).
// Cesta podadresaru (bez nazvu souboru) se posila jako category_path -
// server z ni najde/zalozi strom kategorii (zrcadleni adresaru).
// Ne-FBX soubory ve slozce se tise preskoci (accept u webkitdirectory
// prohlizece ignoruji).
document.getElementById("btnLegImport").onclick = async () => {
  const filesInput = document.getElementById("legImportFiles");
  const dirInput = document.getElementById("legImportDir");
  const resultsEl = document.getElementById("legImportResults");
  const single = [...(filesInput.files || [])].map(f => ({ file: f, categoryPath: "" }));
  const fromDir = [...(dirInput.files || [])]
    .filter(f => f.name.toLowerCase().endsWith(".fbx"))
    .map(f => {
      const rel = f.webkitRelativePath || f.name;
      const dirPath = rel.includes("/") ? rel.slice(0, rel.lastIndexOf("/")) : "";
      return { file: f, categoryPath: dirPath };
    });
  const items = [...single, ...fromDir];
  if (!items.length) { resultsEl.textContent = "Vyber nejdřív FBX soubory nebo složku (obsahující .fbx)."; return; }
  const btn = document.getElementById("btnLegImport");
  btn.disabled = true;
  resultsEl.innerHTML = "";
  const rows = items.map(it => {
    const div = document.createElement("div");
    div.textContent = `⏳ ${it.file.name} – čekám…`;
    resultsEl.appendChild(div);
    return div;
  });
  for (let i = 0; i < items.length; i++) {
    const { file, categoryPath } = items[i];
    rows[i].textContent = `⏳ ${file.name} – nahrávám a rozkládám…`;
    try {
      const fd = new FormData();
      fd.append("file", file);
      if (categoryPath) fd.append("category_path", categoryPath);
      const r = await fetch("/api/admin/legs/import-fbx", { method: "POST", body: fd });
      const data = await r.json();
      if (!r.ok) throw new Error(data.error || ("HTTP " + r.status));
      let txt = `✓ ${file.name} → "${data.name}" (${data.profile_count} profilů, výška ${data.total_height_mm} mm, ${data.category})`;
      if (data.warnings && data.warnings.length) txt += ` ⚠ ${data.warnings.join("; ")}`;
      rows[i].textContent = txt;
    } catch (e) {
      rows[i].textContent = `✗ ${file.name} – ${e.message}`;
    }
  }
  btn.disabled = false;
  filesInput.value = "";
  dirInput.value = "";
};

// Rozklad FBX na profily podle rozmeru (bot6, 2026-08-09, Robert: "tak
// tento script uloz pod tlacitkem" -> "nova sekce Importy" -> "stejnou
// formou, vlozim soubor stisknu prevod") - zalozka Importy, primy upload
// FBX (bez vazby na existujici produkt) -> POST /api/admin/decompose-
// fbx-upload (api/dimension_match_fbx.py, sdili logiku se scripts/
// dimension_match_fbx_to_custom_shape.py a s /decompose-fbx pro
// jednotlive produkty).
// bot8 2026-08-22 (Robert: "zde potřebujeme mít možnost nahrát sadu
// souborů") - vice souboru najednou, zpracovanych POSTUPNE (ne
// paralelne - kazdy prevod uz sam o sobe stoji vykon na serveru,
// soubezne davky by ho zbytecne zatezovaly), stejny vzor jako uz
// existujici "Hromadny import noh" nize (btnLegImport) - vlastni radek
// vysledku pro kazdy soubor.
document.getElementById("btnDmfUpload").onclick = async () => {
  const fileInput = document.getElementById("dmfUploadFile");
  const nameInput = document.getElementById("dmfUploadName");
  const toleranceInput = document.getElementById("dmfUploadTolerance");
  const resultEl = document.getElementById("dmfUploadResult");
  const btn = document.getElementById("btnDmfUpload");
  const files = [...(fileInput.files || [])];
  if (!files.length) { resultEl.textContent = "Vyber nejdřív FBX soubor(y)."; return; }
  // Vlastni nazev z pole ma smysl jen pro presne 1 soubor - u vice by
  // se vsechny prevody prebily na stejny nazev.
  const customName = files.length === 1 ? nameInput.value.trim() : "";
  btn.disabled = true;
  resultEl.innerHTML = "";
  const rows = files.map(f => {
    const div = document.createElement("div");
    div.textContent = `⏳ ${f.name} – čekám…`;
    resultEl.appendChild(div);
    return div;
  });
  for (let i = 0; i < files.length; i++) {
    const file = files[i];
    rows[i].textContent = `⏳ ${file.name} – nahrávám a rozkládám…`;
    try {
      const fd = new FormData();
      fd.append("file", file);
      if (customName) fd.append("name", customName);
      fd.append("tolerance", toleranceInput.value || "2");
      const r = await fetch("/api/admin/decompose-fbx-upload", { method: "POST", body: fd });
      const data = await r.json();
      if (!r.ok) throw new Error(data.error || ("HTTP " + r.status));
      const breakdown = (data.breakdown || []).map(b => `${b.cross}: ${b.count}×`).join(", ");
      const joints = data.joints_found || 0;
      rows[i].innerHTML = `✓ ${file.name} → Rozpoznáno ${data.recognized} z ${data.total_meshes} těles (${breakdown}) - `
        + `rozměry ${data.dims_mm.width_x}×${data.dims_mm.height_y}×${data.dims_mm.depth_z} mm, `
        + `nalezeno ${joints} ${joints === 1 ? "spoj" : (joints >= 2 && joints <= 4 ? "spoje" : "spojů")} mezi díly. `
        + `Uloženo jako Vlastní tvar "${escapeHtmlAdmin(data.name)}" (id ${data.custom_shape_id}).`;
    } catch (e) {
      rows[i].textContent = `✗ ${file.name} – ${e.message}`;
    }
  }
  btn.disabled = false;
  fileInput.value = "";
  nameInput.value = "";
};

// Obrázek ze schránky -> Sdílený disk (bot4, 2026-08-09, Robert: "udělej
// mi v adminu funkci, sekce importy, uložit na sdílený disk soubor
// obrázku, tím že tam nahraju jen schránku obrázek ve schránce, formát
// obrázku ideální pro náš web, jpg?"). Prevod PNG/BMP/cokoli ze schránky
// na JPG probíhá primo v prohlizeci (canvas.toBlob) - zadny novy backend
// kod, jen novy zpusob jak dojit k souboru pro uz existujici
// POST /api/admin/drive/files.
let clipImgBlob = null;

function flattenDriveFolders(folders, depth, out) {
  (folders || []).forEach(f => {
    out.push({ id: f.id, label: "　".repeat(depth) + f.name });
    if (f.children && f.children.length) flattenDriveFolders(f.children, depth + 1, out);
  });
  return out;
}

async function loadClipImgFolders() {
  const sel = document.getElementById("clipImgFolder");
  if (!sel) return;
  try {
    const r = await fetch("/api/admin/drive");
    if (!r.ok) return; // napr. role bez prav na sdileny disk - select zustane jen s korenovou volbou
    const data = await r.json();
    const flat = flattenDriveFolders(data.folders, 0, []);
    sel.innerHTML = '<option value="">— kořen sdíleného disku —</option>' +
      flat.map(f => `<option value="${f.id}">${escapeHtmlAdmin(f.label)}</option>`).join("");
  } catch (e) { /* ticho - select zustane jen s korenovou volbou */ }
}

const clipImgDropzone = document.getElementById("clipImgDropzone");
if (clipImgDropzone) {
  clipImgDropzone.onclick = () => clipImgDropzone.focus();
  clipImgDropzone.addEventListener("paste", async (e) => {
    e.preventDefault();
    const resultEl = document.getElementById("clipImgResult");
    const items = (e.clipboardData || window.clipboardData).items;
    let imageItem = null;
    for (const it of items) {
      if (it.type && it.type.indexOf("image/") === 0) { imageItem = it; break; }
    }
    if (!imageItem) { resultEl.textContent = "Ve schránce není žádný obrázek."; return; }
    resultEl.textContent = "";
    const file = imageItem.getAsFile();
    const bitmap = await createImageBitmap(file);
    const canvas = document.createElement("canvas");
    canvas.width = bitmap.width;
    canvas.height = bitmap.height;
    const ctx = canvas.getContext("2d");
    // JPG nema alfa kanal - bile pozadi misto pripadne pruhlednosti
    // (napr. screenshot s prusvitnymi rohy), aby prevod nezpusobil
    // cerne artefakty.
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(bitmap, 0, 0);
    const quality = (parseInt(document.getElementById("clipImgQuality").value, 10) || 85) / 100;
    canvas.toBlob((blob) => {
      clipImgBlob = blob;
      document.getElementById("clipImgPreview").src = URL.createObjectURL(blob);
      document.getElementById("clipImgMeta").textContent =
        `${canvas.width}×${canvas.height} px, ${(blob.size / 1024).toFixed(0)} KB (JPG, kvalita ${Math.round(quality * 100)}%)`;
      document.getElementById("clipImgPreviewWrap").style.display = "";
    }, "image/jpeg", quality);
  });
}

const btnClipImgUpload = document.getElementById("btnClipImgUpload");
if (btnClipImgUpload) {
  btnClipImgUpload.onclick = async () => {
    if (!clipImgBlob) return;
    const resultEl = document.getElementById("clipImgResult");
    btnClipImgUpload.disabled = true;
    resultEl.textContent = "⏳ Nahrávám…";
    try {
      let name = document.getElementById("clipImgName").value.trim();
      if (!name) name = `schranka-${new Date().toISOString().replace(/[:.]/g, "-")}`;
      if (!/\.jpe?g$/i.test(name)) name += ".jpg";
      const fd = new FormData();
      fd.append("files", clipImgBlob, name);
      const folderId = document.getElementById("clipImgFolder").value;
      if (folderId) fd.append("folder_id", folderId);
      const r = await fetch("/api/admin/drive/files", { method: "POST", body: fd });
      const data = await r.json();
      if (!r.ok) throw new Error(data.error || ("HTTP " + r.status));
      resultEl.textContent = "✓ Uloženo na Sdílený disk.";
      document.getElementById("clipImgPreviewWrap").style.display = "none";
      document.getElementById("clipImgName").value = "";
      clipImgBlob = null;
    } catch (e) {
      resultEl.textContent = "Chyba: " + e.message;
    } finally {
      btnClipImgUpload.disabled = false;
    }
  };
}

let pricesSelectedIds = new Set();

function renderPrices() {
  const tbody = document.getElementById("tbody");
  tbody.innerHTML = "";
  priceRows.forEach((row, i) => {
    const tr = document.createElement("tr");
    tr.dataset.i = i;
    tr.innerHTML = `
      <td><input type="checkbox" class="price-chk" data-id="${row.id}" ${pricesSelectedIds.has(row.id) ? "checked" : ""}></td>
      <td>${fmtCross(row.cross_section_mm)} <span style="color:#666;">(${row.id})</span></td>
      <td><input type="url" class="url-input" placeholder="https://www.logiman.cz/…" style="width:220px" value="${row.price_source_url ? row.price_source_url.replace(/"/g, '&quot;') : ""}"></td>
      <td>
        <!-- bot16, 2026-09-18 (Robert: "kazdy tyden jede smycka na
             stahovani cen z Dogusu... musi se to udrzovat zive") - jen
             pro cteni, zive ze shop_products.dogus_list_price_usd (viz
             admin_profily_list()), zadne rucni zadavani. -->
        ${row.dogus_price_usd != null ? row.dogus_price_usd.toFixed(2) + " $" : "<span style=\"color:#666;\">—</span>"}
        <div style="font-size:10.5px;color:#666;margin-top:2px;">${row.dogus_price_usd_fetched_at ? "staženo " + fmtFbxDate(row.dogus_price_usd_fetched_at) : ""}</div>
      </td>
      <td>
        <!-- bot16, 2026-09-24 (Robert pres bot3, "prepocitanou cenu USD
             s aktualnim kurzem FIO devize prodej", pravidlo 52) - prosty
             prevod row.dogus_price_usd * ZIVY kurz (fioLiveRate, viz
             loadFioRate() - stahovany znovu pri kazdem loadPrices()),
             cela pouzita rovnice vypsana rovnou v bunce (pravidlo
             "vzdy cely vypocet"). Zadny fallback - kdyz fioLiveRate
             chybi, bunka rovnou hlasi "kurz nedostupny", nikdy
             nedopocita se starym/ulozenym kurzem. -->
        ${fmtLiveCzkCell(row)}
      </td>
      <td><input type="number" step="0.001" class="w-input" style="width:90px" value="${row.weight_kg_per_m ?? ""}"></td>
      <td><input type="number" step="0.01" class="p-input" style="width:90px" value="${row.price_czk_per_m ?? ""}"></td>
      <td>
        <!-- bot16, 2026-09-24 (Robert pres bot3, "cenu profilů z 1 m z
             original logiman.cz, samozrejme SKU je parovaci znak",
             pravidlo 52) - CISTE READ-ONLY srovnavaci udaj z tabulky
             logiman_cz_price_reference (plni ji samostatny periodicky
             crawl, viz scripts/2026-09-24_logiman_price_reference_crawl.py),
             ZADNY zivy fetch logiman.cz pri nacteni teto zalozky. Neni
             to zdroj/vstup nasi vlastni ceny (viz komentar u "z logiman
             uz nic nebudeme tahat" v api/admin_profily.py) - jen srovnani
             vedle sebe. Zadny fallback: bez shody SKU -> "SKU nenalezeno",
             nikdy dopocitana/odhadnuta hodnota (stejny princip jako u
             kurzu Fio vlevo). -->
        ${fmtLogimanCell(row)}
      </td>
      <td><input type="number" step="0.01" class="cut-input" style="width:90px" value="${row.price_per_cut_czk ?? ""}"></td>
      <td style="white-space:nowrap;">
        <input type="file" class="fbx-input" accept=".fbx,.stp,.step" style="display:none;">
        <button class="btn-fbx-upload">${row.fbx_original_name ? "Nahradit" : "Nahrát model"}</button>
        <div class="fbx-status" style="font-size:11px;color:#666;margin-top:2px;">${fbxStatusText(row)}</div>
      </td>
      <td style="white-space:nowrap;"><button class="btn-save">Uložit</button></td>
      <td><span class="row-status"></span></td>
    `;
    const markDirty = () => tr.classList.add("dirty");
    tr.querySelector(".url-input").addEventListener("input", markDirty);
    tr.querySelector(".w-input").addEventListener("input", markDirty);
    tr.querySelector(".p-input").addEventListener("input", markDirty);
    tr.querySelector(".cut-input").addEventListener("input", markDirty);
    tr.querySelector(".btn-save").onclick = () => savePriceRow(i, tr);
    tr.querySelector(".price-chk").onchange = (e) => {
      if (e.target.checked) pricesSelectedIds.add(row.id); else pricesSelectedIds.delete(row.id);
      updatePricesBulkToolbar();
    };
    const fbxInput = tr.querySelector(".fbx-input");
    tr.querySelector(".btn-fbx-upload").onclick = () => fbxInput.click();
    fbxInput.addEventListener("change", () => {
      if (fbxInput.files && fbxInput.files[0]) uploadFbxFile(i, tr, fbxInput.files[0]);
    });
    tbody.appendChild(tr);
  });
  document.getElementById("tbl").style.display = priceRows.length ? "table" : "none";
  document.getElementById("saveAllWrap").style.display = priceRows.length ? "flex" : "none";
  updatePricesBulkToolbar();
}

function updatePricesBulkToolbar() {
  const bar = document.getElementById("pricesBulkToolbar");
  const count = pricesSelectedIds.size;
  bar.classList.toggle("active", count > 0 && priceRows.length > 0);
  document.getElementById("pricesBulkCount").textContent = `${count} vybráno`;
}
document.getElementById("pricesSelectAll").onchange = (e) => {
  if (e.target.checked) priceRows.forEach(row => pricesSelectedIds.add(row.id));
  else pricesSelectedIds.clear();
  renderPrices();
};
document.getElementById("pricesBulkRefresh").onclick = async () => {
  if (!pricesSelectedIds.size) return;
  const status = document.getElementById("refreshAllStatus");
  status.textContent = "načítám vybrané…";
  try {
    const r = await fetch("/api/admin/profily/bulk-refresh", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ids: [...pricesSelectedIds] }),
    });
    const data = await r.json();
    if (!r.ok) throw new Error(data.error || ("HTTP " + r.status));
    const okCount = (data.results || []).filter(x => x.status === "ok").length;
    const errCount = (data.results || []).length - okCount;
    status.textContent = `Načteno: ${okCount}${errCount ? `, chyby: ${errCount}` : ""} ✓`;
    setTimeout(() => { status.textContent = ""; }, 3000);
    await loadPrices();
  } catch (e) {
    status.textContent = "chyba: " + e.message;
  }
};

function readPriceRow(tr) {
  const w = tr.querySelector(".w-input").value;
  const p = tr.querySelector(".p-input").value;
  const c = tr.querySelector(".cut-input").value;
  const i = parseInt(tr.dataset.i, 10);
  return {
    id: priceRows[i].id,
    weight_kg_per_m: w === "" ? null : parseFloat(w),
    price_czk_per_m: p === "" ? null : parseFloat(p),
    price_per_cut_czk: c === "" ? null : parseFloat(c),
  };
}

async function savePriceRow(i, tr) {
  const update = readPriceRow(tr);
  const url = tr.querySelector(".url-input").value.trim();
  const status = tr.querySelector(".row-status");
  status.textContent = "ukládám…";
  try {
    await fetch(`/api/admin/profily/${priceRows[i].id}/source`, {
      method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ price_source_url: url }),
    });
    const r = await fetch(PRICES_API, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ updates: [update] }) });
    if (!r.ok) throw new Error("HTTP " + r.status);
    priceRows[i].price_source_url = url || null;
    tr.classList.remove("dirty");
    status.textContent = "uloženo ✓";
    setTimeout(() => { status.textContent = ""; }, 2000);
  } catch (e) {
    status.textContent = "chyba: " + e.message;
  }
}

document.getElementById("btnSaveAll").onclick = async () => {
  const trs = [...document.querySelectorAll("#tbody tr")];
  const updates = trs.map(readPriceRow);
  const status = document.getElementById("saveAllStatus");
  status.textContent = "ukládám…";
  try {
    const r = await fetch(PRICES_API, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ updates }) });
    if (!r.ok) throw new Error("HTTP " + r.status);
    trs.forEach(tr => tr.classList.remove("dirty"));
    status.textContent = "vše uloženo ✓";
    setTimeout(() => { status.textContent = ""; }, 2500);
  } catch (e) {
    status.textContent = "chyba: " + e.message;
  }
};

document.getElementById("btnRefreshAll").onclick = async () => {
  const status = document.getElementById("refreshAllStatus");
  status.textContent = "načítám všechny zdroje…";
  try {
    const r = await fetch("/api/admin/profily/refresh-all", { method: "POST" });
    const data = await r.json();
    const ok = (data.results || []).filter(x => x.status === "ok").length;
    const fail = (data.results || []).filter(x => x.status !== "ok").length;
    status.textContent = `Hotovo: ${ok} načteno${fail ? ", " + fail + " chyb" : ""}.`;
    loadPrices();
    setTimeout(() => { status.textContent = ""; }, 4000);
  } catch (e) {
    status.textContent = "chyba: " + e.message;
  }
};

// ==================== SPOJE A PRISLUSENSTVI ====================
async function loadJointPrice() {
  try {
    const r = await fetch("/api/admin/settings");
    const data = await r.json();
    document.getElementById("jointPriceInput").value = data.joint_price_czk ?? "";
    document.getElementById("profileFlatFeeInput").value = data.profile_flat_fee_czk ?? "";
    document.getElementById("packagingPctInput").value = data.packaging_pct ?? "";
    document.getElementById("montazPctInput").value = data.montaz_pct ?? "";
    document.getElementById("vandraweeMontazPctInput").value = data.vandrawee_montaz_pct ?? "";
    zobrazPrepocetMontaze(data.montaz_prepocet === true);
    document.getElementById("scenePriceCoefInput").value = data.scene_price_coefficient ?? "";
    aplikujScenePriceCoefTexty(data);
    updateScenePriceCoefExample();
    const cenaObsahujeEl = document.getElementById("vandraweeCenaObsahujeInput");
    if (cenaObsahujeEl) cenaObsahujeEl.value = data.vandrawee_cena_obsahuje_text ?? "";
    const kotveniEl = document.getElementById("vandrKotveniInput");
    if (kotveniEl) kotveniEl.value = data.vandr_kotveni_text ?? "";
    const montazTextEl = document.getElementById("vandrMontazTextInput");
    if (montazTextEl) montazTextEl.value = data.vandr_montaz_text ?? "";
    document.getElementById("cartEnabledInput").checked = data.cart_enabled !== false;
    document.getElementById("discountCodesEnabledInput").checked = data.discount_codes_enabled !== false;
    document.getElementById("smtpHostInput").value = data.smtp_host ?? "";
    document.getElementById("smtpPortInput").value = data.smtp_port ?? "";
    document.getElementById("smtpUserInput").value = data.smtp_user ?? "";
    document.getElementById("smtpFromInput").value = data.smtp_from ?? "";
    document.getElementById("smtpPasswordHint").textContent = data.smtp_password_configured
      ? "(nastaveno - nech prázdné pro zachování)" : "(zatím nenastaveno)";
  } catch (e) {}
  loadStulMontaz();
}

// Sazba montaze STOLU z generatoru (bot16, 2026-10-07; Robert pres bot9: vsechny 3 sazby montaze u sebe v Obecne -> Montaz). Cte a zapisuje se pres STAVAJICI API
// GET/PUT /api/stul/montaz (api/stul_montaz.py, klic app_settings stul_montaz_pct; PUT = pravo nastaveni/upravit) - stejna hodnota jako pole "Montaz" primo v Generatoru stolu
// (js/stul-montaz-staff.js), zadna druha kopie ani druhy zdroj pravdy. Pole je do nacteni zakazane (starsi server / bez prava = zustane zakazane a rekne to).
async function loadStulMontaz() {
  const inp = document.getElementById("stulMontazPctInput"), btn = document.getElementById("btnSaveStulMontazPct"), st = document.getElementById("stulMontazPctStatus");
  if (!inp || !btn || !st) return;
  try {
    const r = await fetch("/api/stul/montaz", { credentials: "same-origin" });
    if (!r.ok) throw new Error("HTTP " + r.status);
    const d = await r.json();
    if (d.pct == null) throw new Error("neplatná odpověď");
    inp.value = String(d.pct);
    inp.placeholder = String(d.default != null ? d.default : 12);
    inp.disabled = false; btn.disabled = false;
    st.textContent = d.stored ? "" : "zatím nenastaveno - platí výchozí " + (d.default != null ? d.default : 12) + " %";
  } catch (e) {
    inp.disabled = true; btn.disabled = true;
    st.textContent = "sazbu stolů se nepodařilo načíst (" + e.message + ")";
  }
}

document.getElementById("btnSaveSmtp").onclick = async () => {
  const status = document.getElementById("smtpStatus");
  status.textContent = "ukládám…";
  try {
    const r = await fetch("/api/admin/settings", {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        smtp_host: document.getElementById("smtpHostInput").value.trim(),
        smtp_port: document.getElementById("smtpPortInput").value.trim(),
        smtp_user: document.getElementById("smtpUserInput").value.trim(),
        smtp_password: document.getElementById("smtpPasswordInput").value,
        smtp_from: document.getElementById("smtpFromInput").value.trim(),
      }),
    });
    if (!r.ok) throw new Error("HTTP " + r.status);
    document.getElementById("smtpPasswordInput").value = "";
    status.textContent = "uloženo ✓";
    loadJointPrice();
    setTimeout(() => { status.textContent = ""; }, 2000);
  } catch (e) {
    status.textContent = "chyba: " + e.message;
  }
};

// ==================== FIREMNI UDAJE (kontakt.html, DB-backed) ====================
async function loadCompanyInfo() {
  try {
    const r = await fetch("/api/admin/company-info");
    const data = await r.json();
    document.getElementById("companyNameInput").value = data.name ?? "";
    document.getElementById("companyAddressInput").value = data.address ?? "";
    document.getElementById("companyIcoInput").value = data.ico ?? "";
    document.getElementById("companyDicInput").value = data.dic ?? "";
    document.getElementById("companyPhoneInput").value = data.phone ?? "";
    document.getElementById("companyEmailInput").value = data.email ?? "";
  } catch (e) {}
}

document.getElementById("btnSaveCompanyInfo").onclick = async () => {
  const errEl = document.getElementById("companyInfoErr");
  const status = document.getElementById("companyInfoStatus");
  errEl.textContent = "";
  status.textContent = "ukládám…";
  try {
    const r = await fetch("/api/admin/company-info", {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: document.getElementById("companyNameInput").value.trim(),
        address: document.getElementById("companyAddressInput").value.trim(),
        ico: document.getElementById("companyIcoInput").value.trim(),
        dic: document.getElementById("companyDicInput").value.trim(),
        phone: document.getElementById("companyPhoneInput").value.trim(),
        email: document.getElementById("companyEmailInput").value.trim(),
      }),
    });
    const data = await r.json();
    if (!r.ok) throw new Error(data.error || ("HTTP " + r.status));
    status.textContent = "uloženo ✓";
    setTimeout(() => { status.textContent = ""; }, 2000);
  } catch (e) {
    status.textContent = "";
    errEl.textContent = "chyba: " + e.message;
  }
};

document.getElementById("btnSaveCartEnabled").onclick = async () => {
  const status = document.getElementById("cartEnabledStatus");
  const checked = document.getElementById("cartEnabledInput").checked;
  status.textContent = "ukládám…";
  try {
    const r = await fetch("/api/admin/settings", {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ cart_enabled: checked }),
    });
    if (!r.ok) throw new Error("HTTP " + r.status);
    status.textContent = "uloženo ✓";
    setTimeout(() => { status.textContent = ""; }, 2000);
  } catch (e) {
    status.textContent = "chyba: " + e.message;
  }
};

document.getElementById("btnSaveDiscountCodesEnabled").onclick = async () => {
  const status = document.getElementById("discountCodesEnabledStatus");
  const checked = document.getElementById("discountCodesEnabledInput").checked;
  status.textContent = "ukládám…";
  try {
    const r = await fetch("/api/admin/settings", {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ discount_codes_enabled: checked }),
    });
    if (!r.ok) throw new Error("HTTP " + r.status);
    status.textContent = "uloženo ✓";
    setTimeout(() => { status.textContent = ""; }, 2000);
  } catch (e) {
    status.textContent = "chyba: " + e.message;
  }
};

document.getElementById("btnSaveJointPrice").onclick = async () => {
  const status = document.getElementById("jointPriceStatus");
  const val = document.getElementById("jointPriceInput").value;
  status.textContent = "ukládám…";
  try {
    const r = await fetch("/api/admin/settings", {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ joint_price_czk: val === "" ? 0 : parseFloat(val) }),
    });
    if (!r.ok) throw new Error("HTTP " + r.status);
    status.textContent = "uloženo ✓";
    setTimeout(() => { status.textContent = ""; }, 2000);
  } catch (e) {
    status.textContent = "chyba: " + e.message;
  }
};

document.getElementById("btnSaveProfileFlatFee").onclick = async () => {
  const status = document.getElementById("profileFlatFeeStatus");
  const val = document.getElementById("profileFlatFeeInput").value;
  status.textContent = "ukládám…";
  try {
    const r = await fetch("/api/admin/settings", {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ profile_flat_fee_czk: val === "" ? 0 : parseFloat(val) }),
    });
    if (!r.ok) throw new Error("HTTP " + r.status);
    status.textContent = "uloženo ✓";
    setTimeout(() => { status.textContent = ""; }, 2000);
  } catch (e) {
    status.textContent = "chyba: " + e.message;
  }
};

document.getElementById("btnSavePackagingPct").onclick = async () => {
  const status = document.getElementById("packagingPctStatus");
  const val = document.getElementById("packagingPctInput").value;
  status.textContent = "ukládám…";
  try {
    const r = await fetch("/api/admin/settings", {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ packaging_pct: val === "" ? 0 : parseFloat(val) }),
    });
    if (!r.ok) { const d = await r.json().catch(() => ({})); throw new Error(d.error || ("HTTP " + r.status)); }
    status.textContent = "uloženo ✓";
    setTimeout(() => { status.textContent = ""; }, 2000);
  } catch (e) {
    status.textContent = "chyba: " + e.message;
  }
};

async function ulozMontazPct() {
  const status = document.getElementById("montazPctStatus");
  const val = document.getElementById("montazPctInput").value;
  status.textContent = "ukládám…";
  try {
    const r = await fetch("/api/admin/settings", {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ montaz_pct: val === "" ? 0 : parseFloat(val) }),
    });
    if (!r.ok) { const d = await r.json().catch(() => ({})); throw new Error(d.error || ("HTTP " + r.status)); }
    status.textContent = "uloženo ✓";
    setTimeout(() => { status.textContent = ""; }, 2000);
    return true;
  } catch (e) {
    status.textContent = "chyba: " + e.message;
    return false;
  }
}
document.getElementById("btnSaveMontazPct").onclick = ulozMontazPct;

async function ulozStulMontazPct() {
  const inp = document.getElementById("stulMontazPctInput"), status = document.getElementById("stulMontazPctStatus");
  const raw = String(inp.value || "").replace(/\s+/g, "").replace(",", ".");
  if (!/^\d{1,3}(\.\d{1,2})?$/.test(raw) || Number(raw) > 100) { status.textContent = "chyba: zadej číslo od 0 do 100 (0 = montáž se u stolů nenabízí)"; return false; }
  status.textContent = "ukládám…";
  try {
    const r = await fetch("/api/stul/montaz", {
      method: "PUT", credentials: "same-origin", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pct: Number(raw) }),
    });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(r.status === 403 ? "na změnu sazby nemáš oprávnění" : (d.message || d.error || ("HTTP " + r.status)));
    inp.value = String(d.pct != null ? d.pct : Number(raw));
    status.textContent = "uloženo ✓" + (Number(raw) === 0 ? " - u stolů se montáž nenabízí" : "");
    setTimeout(() => { status.textContent = ""; }, 3000);
    return true;
  } catch (e) {
    status.textContent = "chyba: " + e.message;
    return false;
  }
}
document.getElementById("btnSaveStulMontazPct").onclick = ulozStulMontazPct;

// "Ulozit a prepocitat vse" (bot16, 2026-10-07; Robert: "chci u tech tlacitek za montaze mit nejen ulozit ale prepocitat vse, aby se vsechny karty prekalkulovaly"). Karty vestaveb (sestavy typu AUTO)
// maji montaz ULOZENOU v price_summary (stav 2026-10-07: 530 karet pri 20 %, nastaveni 10 %) - zmena sazby se do nich sama nepromitne. Tlacitka se ukazou JEN kdyz server prepocet umi
// (GET /api/admin/settings -> montaz_prepocet; statika jde ven driv nez planovane nasazeni API). Postup: ulozit sazbu stavajicim mechanismem -> GET nahled (kolik karet, priklady) -> potvrzeni -> POST.
// Prepocet pouziva sazbu "Vestavby - 1. vetev" (montaz_pct), ktera se tlacitkem prave ulozila; karty vanDrawee a stoly pocitaji montaz zive, tem nova sazba plati hned po ulozeni.
function zobrazPrepocetMontaze(umi) {
  document.querySelectorAll(".montaz-prepocet-btn").forEach(b => { b.hidden = !umi; });
  const h = document.getElementById("montazPrepocetHint");
  if (h) h.hidden = !umi;
}
const _kc = n => (n == null ? "-" : Number(n).toLocaleString("cs-CZ"));
const _pctTxt = p => String(p).replace(".", ",");
const _karet = n => (Number(n) === 1 ? "karty" : "karet");          // genitiv po cislovce: u 1 karty, u 2 / 5 / 530 karet
async function prepocitatMontazVse(status) {
  try {
    const r = await fetch("/api/admin/montaz/prepocet", { credentials: "same-origin" });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(d.message || d.error || ("HTTP " + r.status));
    if (!d.ke_zmene) { status.textContent = "uloženo ✓ - karty vestaveb už mají aktuální montáž (" + _pctTxt(d.pct) + " %), není co přepočítávat"; return true; }
    const priklady = (d.ukazky || []).map(u => (u.nazev || ("karta #" + u.id)) + ": " + _kc(u.montaz_stara_czk) + " → " + _kc(u.montaz_nova_czk) + " Kč").join("\n");
    if (!confirm("Přepočítat montáž u " + d.ke_zmene + " z " + d.sestav_auto + " " + _karet(d.sestav_auto) + " vestaveb podle sazby " + _pctTxt(d.pct) + " % (Vestavby – 1. větev)?\n\nPříklady:\n" + priklady +
                 "\n\nCeny karet bez montáže se nemění, stejně jako už odeslané objednávky. Staré hodnoty se uloží do auditu.")) {
      status.textContent = "uloženo ✓ - přepočet karet zrušen"; return true;
    }
    status.textContent = "přepočítávám…";
    const p = await fetch("/api/admin/montaz/prepocet", { method: "POST", credentials: "same-origin" });
    const pd = await p.json().catch(() => ({}));
    if (!p.ok) throw new Error(pd.message || pd.error || ("HTTP " + p.status));
    status.textContent = "uloženo ✓ a přepočítáno: montáž změněna u " + pd.zmeneno + " " + _karet(pd.zmeneno) + " vestaveb (sazba 1. větve " + _pctTxt(pd.pct) + " %)";
    return true;
  } catch (e) {
    status.textContent = "uloženo, ale přepočet karet selhal: " + e.message;
    return false;
  }
}
// JEN u "Vestavby - 1. vetev" (Robert 2026-10-07 23:05: tlacitko u karty Stoly nesmi prepocitavat karty vestaveb - po kliku z karty stolu se prepocitalo podle ULOZENE sazby 1. vetve, ne podle toho, co bylo napsano
// v poli stolu): vanDrawee karty a stoly pocitaji montaz zive, tem staci Ulozit.
document.getElementById("btnSaveMontazPctPrepocet").onclick = async () => {
  const status = document.getElementById("montazPctStatus");
  const ok = await ulozMontazPct();                              // sazba se nejdriv ulozi (validace a chyby jako u tlacitka Ulozit); kdyz se neulozila, neprepocitava se
  if (ok === true) await prepocitatMontazVse(status);
};

// bot16, 2026-09-25 (nahlasil bot3, pravidlo 52) - pole/tlacitko pro
// scene_price_coefficient v HTML existovalo, ale nemelo ZADNY JS
// handler (ani load, ani save) - Robert zmenil hodnotu a klikl
// "Ulozit", nic se nestalo, system dal pocital se starym cislem beze
// zpravy o chybe. Vzor 1:1 podle btnSaveMontazPct vyse (stejny
// endpoint, stejne d.error preposilani chyby z backendu - viz
// api/admin_settings.py, kde uz 0/zaporna hodnota vraci 400).
function updateScenePriceCoefExample() {
  const el = document.getElementById("scenePriceCoefExample");
  if (!el) return;
  const val = parseFloat(document.getElementById("scenePriceCoefInput").value);
  if (!val || val <= 0) { el.textContent = ""; return; }
  const pct = (val - 1) * 100;
  const sign = pct >= 0 ? "+" : "";
  const cim = scenePriceCoefRozsahDogus ? "profilů a produktů z Dogusu" : "dílů";
  el.textContent = `Aktuálně: ${val} = ${sign}${pct.toFixed(1).replace(".", ",")} % nad cenou ${cim}.`;
}
document.getElementById("scenePriceCoefInput").addEventListener("input", updateScenePriceCoefExample);

// bot16, 2026-10-01 (Robert: "koeficient pro scenu se tyka jen profilu a produktu, ktere se nacitaji z dogusu";
// backend bot8 c77795b5, rozsah vraci GET /api/admin/settings jako scene_price_coefficient_scope, viz
// api/admin_settings.py SCENE_PRICE_COEF_SCOPE). Texty v admin.html (#scenePriceCoefHint, #scenePriceCoefWarn)
// uz uvadeji NOVY rozsah. Webapp se ale servíruje hned a backend s omezenim jde ven az v planovanem nasazeni, takze
// dokud pole v odpovedi CHYBI (starsi backend), vraci se tu pro tu dobu puvodni zneni - popisek tak vzdy odpovida
// tomu, co backend skutecne dela, a nemusi se nic prepisovat v konkretni cas. Po nasazeni je tenhle blok (i vetev
// "stare") zbytecny a jde bez nahrady smazat.
const SCENE_COEF_TEXTY_STARE = {
  hint: 'Systematicky navyšuje ceny <b>dílů</b> ve 3D konfigurátoru oproti běžným (webovým) cenám stejné položky. ' +
    '<b>1</b> = žádné navýšení, <b>1.15</b> = +15 %. Navýšení se projeví v přehledu ceny ve scéně i ve vygenerované ' +
    'nabídce (stejná částka na obou místech). Příplatky se <b>nenavyšují</b> - cena řezů, paušál za profil, cena spojů ' +
    'a spojovací materiál se nastavují zvlášť v Cenotvorbě a nemají obdobu na webu. Nesouvisí s koeficientem Doguskalip ' +
    'v tabulce níž (ten přepočítává nákupní USD ceny).',
  warn: '<b>⚠ Po uložení se nová cena projeví okamžitě jen ve scéně (nové/rozpracované sestavy).</b> Ceny už vystavených ' +
    'karet na e-shopu se samy nepřepočítají a zůstanou na starém koeficientu, dokud je někdo ručně nepřepočítá skriptem ' +
    '(dávkový přepočet přes bota, ne automaticky).',
};
let scenePriceCoefRozsahDogus = true;   // true = backend uz omezuje koeficient na profily a produkty z Dogusu
function aplikujScenePriceCoefTexty(settings) {
  scenePriceCoefRozsahDogus = !!settings && settings.scene_price_coefficient_scope === "profily_dogus";
  if (scenePriceCoefRozsahDogus) return;            // text z HTML uz je novy
  const h = document.getElementById("scenePriceCoefHint");
  const w = document.getElementById("scenePriceCoefWarn");
  if (h) h.innerHTML = SCENE_COEF_TEXTY_STARE.hint;
  if (w) w.innerHTML = SCENE_COEF_TEXTY_STARE.warn;
}

document.getElementById("btnSaveScenePriceCoef").onclick = async () => {
  const status = document.getElementById("scenePriceCoefMsg");
  const val = document.getElementById("scenePriceCoefInput").value;
  status.textContent = "ukládám…";
  try {
    const r = await fetch("/api/admin/settings", {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ scene_price_coefficient: val === "" ? 1 : parseFloat(val) }),
    });
    if (!r.ok) { const d = await r.json().catch(() => ({})); throw new Error(d.error || ("HTTP " + r.status)); }
    status.textContent = "uloženo ✓";
    updateScenePriceCoefExample();
    setTimeout(() => { status.textContent = ""; }, 3000);
  } catch (e) {
    status.textContent = "chyba: " + e.message;
  }
};

async function ulozVandraweeMontazPct() {
  const status = document.getElementById("vandraweeMontazPctStatus");
  const val = document.getElementById("vandraweeMontazPctInput").value;
  status.textContent = "ukládám…";
  try {
    const r = await fetch("/api/admin/settings", {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ vandrawee_montaz_pct: val === "" ? 20 : parseFloat(val) }),
    });
    if (!r.ok) { const d = await r.json().catch(() => ({})); throw new Error(d.error || ("HTTP " + r.status)); }
    status.textContent = "uloženo ✓";
    setTimeout(() => { status.textContent = ""; }, 2000);
    return true;
  } catch (e) {
    status.textContent = "chyba: " + e.message;
    return false;
  }
}
document.getElementById("btnSaveVandraweeMontazPct").onclick = ulozVandraweeMontazPct;

// Robert 2026-09-23: "tento text chci editovatelný v adminu, protože
// se bude opakovat na vsech Vandr sestavach" - "Cena obsahuje" blok
// (app_settings, čte se DYNAMICKY na kartě, viz api/products.py) +
// Kotvení/Montáž text (regal_umisteni.id=7, jediný řádek, který Vandr
// používá - viz komentář VANDR_UMISTENI_ID v api/admin_settings.py).
document.getElementById("btnSaveVandraweeCenaObsahuje").onclick = async () => {
  const status = document.getElementById("vandraweeCenaObsahujeStatus");
  const val = document.getElementById("vandraweeCenaObsahujeInput").value;
  status.textContent = "ukládám…";
  try {
    const r = await fetch("/api/admin/settings", {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ vandrawee_cena_obsahuje_text: val }),
    });
    if (!r.ok) { const d = await r.json().catch(() => ({})); throw new Error(d.error || ("HTTP " + r.status)); }
    status.textContent = "uloženo ✓";
    setTimeout(() => { status.textContent = ""; }, 2000);
  } catch (e) {
    status.textContent = "chyba: " + e.message;
  }
};

document.getElementById("btnSaveVandrKotveniMontaz").onclick = async () => {
  const status = document.getElementById("vandrKotveniMontazStatus");
  const kotveni = document.getElementById("vandrKotveniInput").value;
  const montaz = document.getElementById("vandrMontazTextInput").value;
  status.textContent = "ukládám…";
  try {
    const r = await fetch("/api/admin/settings", {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ vandr_kotveni_text: kotveni, vandr_montaz_text: montaz }),
    });
    if (!r.ok) { const d = await r.json().catch(() => ({})); throw new Error(d.error || ("HTTP " + r.status)); }
    status.textContent = "uloženo ✓";
    setTimeout(() => { status.textContent = ""; }, 2000);
  } catch (e) {
    status.textContent = "chyba: " + e.message;
  }
};

// ==================== MISTA MONTAZE ====================
// Robert 2026-09-13: "u montáže nevidim v adminu ty dve volby kde se
// muze montovat" -> "Plně editovat". Maly seznam (montaz_mista),
// zobrazeny VCETNE neaktivnich (admin musi videt, co skryl), zakaznik
// na detailu produktu vidi jen aktivni (viz GET /api/montaz-mista).
let montazMistaRows = [];

async function loadMontazMista() {
  try {
    const r = await fetch("/api/admin/montaz-mista");
    const data = await r.json();
    montazMistaRows = data.rows || [];
    renderMontazMista();
  } catch (e) {
    document.getElementById("montazMistaErr").textContent = "Nepodařilo se načíst místa montáže.";
  }
}

function renderMontazMista() {
  const tbody = document.getElementById("montazMistaTbody");
  if (!tbody) return;
  tbody.innerHTML = "";
  montazMistaRows.forEach((row) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td><input type="text" class="mm-nazev" style="width:180px" value="${(row.nazev || "").replace(/"/g, "&quot;")}"></td>
      <td style="color:var(--text-muted,#8b93a1);font-family:monospace;">${row.klic}</td>
      <td><input type="checkbox" class="mm-aktivni" ${row.aktivni ? "checked" : ""}></td>
      <td><button class="mm-save">Uložit</button></td>
    `;
    tr.querySelector(".mm-save").onclick = async () => {
      const r = await fetch(`/api/admin/montaz-mista/${row.id}`, {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          nazev: tr.querySelector(".mm-nazev").value.trim(),
          aktivni: tr.querySelector(".mm-aktivni").checked,
        }),
      });
      const d = await r.json().catch(() => ({}));
      if (!r.ok) { document.getElementById("montazMistaErr").textContent = d.error || "Chyba."; return; }
      document.getElementById("montazMistaErr").textContent = "";
      loadMontazMista();
    };
    tbody.appendChild(tr);
  });
}

document.getElementById("btnAddMontazMisto").onclick = async () => {
  const input = document.getElementById("montazMistoNewName");
  const nazev = input.value.trim();
  const errEl = document.getElementById("montazMistaErr");
  if (!nazev) { errEl.textContent = "Zadejte název místa."; return; }
  const r = await fetch("/api/admin/montaz-mista", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ nazev }),
  });
  const d = await r.json().catch(() => ({}));
  if (!r.ok) { errEl.textContent = d.error || "Chyba."; return; }
  errEl.textContent = "";
  input.value = "";
  loadMontazMista();
};

let accessoryRows = [];
let accSelectedIds = new Set();
let accShowArchived = false;

async function loadAccessories() {
  try {
    const r = await fetch(`/api/admin/accessories${accShowArchived ? "?archived=1" : ""}`);
    const data = await r.json();
    accessoryRows = data.rows || [];
    renderAccessories();
  } catch (e) {
    document.getElementById("accErr").textContent = "Nepodařilo se načíst příslušenství.";
  }
}
document.getElementById("accShowArchivedBtn").onclick = () => {
  accShowArchived = !accShowArchived;
  const btn = document.getElementById("accShowArchivedBtn");
  btn.textContent = accShowArchived ? "Skrýt archivované" : "Zobrazit archivované";
  btn.style.background = accShowArchived ? "#3a5a7a" : "none";
  btn.style.color = accShowArchived ? "#fff" : "#c7ccd4";
  accSelectedIds.clear();
  loadAccessories();
};

function renderAccessories() {
  const tbody = document.getElementById("accTbody");
  tbody.innerHTML = "";
  accessoryRows.forEach((row) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td><input type="checkbox" class="a-chk" ${accSelectedIds.has(row.id) ? "checked" : ""}></td>
      <td><input type="text" class="a-name" style="width:200px" value="${(row.name || "").replace(/"/g, '&quot;')}"></td>
      <td><input type="number" step="0.01" class="a-price" style="width:90px" value="${row.price_czk}"></td>
      <td><input type="number" step="0.01" class="a-qty" style="width:90px" value="${row.qty_per_joint}"></td>
      <td><input type="checkbox" class="a-active" ${row.active ? "checked" : ""}></td>
      <td><button class="a-save">Uložit</button> <button class="a-delete danger">Smazat</button></td>
    `;
    tr.querySelector(".a-chk").onchange = (e) => {
      if (e.target.checked) accSelectedIds.add(row.id); else accSelectedIds.delete(row.id);
      updateAccBulkToolbar();
    };
    tr.querySelector(".a-save").onclick = async () => {
      await fetch(`/api/admin/accessories/${row.id}`, {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: tr.querySelector(".a-name").value.trim(),
          price_czk: parseFloat(tr.querySelector(".a-price").value || 0),
          qty_per_joint: parseFloat(tr.querySelector(".a-qty").value || 0),
          active: tr.querySelector(".a-active").checked,
        }),
      });
      loadAccessories();
    };
    tr.querySelector(".a-delete").onclick = async () => {
      if (!confirm(`Smazat příslušenství "${row.name}"?`)) return;
      await fetch(`/api/admin/accessories/${row.id}`, { method: "DELETE" });
      loadAccessories();
    };
    tbody.appendChild(tr);
  });
  document.getElementById("accTbl").style.display = accessoryRows.length ? "table" : "none";
  document.getElementById("accEmpty").style.display = accessoryRows.length ? "none" : "block";
  updateAccBulkToolbar();
}

function updateAccBulkToolbar() {
  const bar = document.getElementById("accBulkToolbar");
  const count = accSelectedIds.size;
  bar.classList.toggle("active", count > 0 && accessoryRows.length > 0);
  document.getElementById("accBulkCount").textContent = `${count} vybráno`;
}
document.getElementById("accSelectAll").onchange = (e) => {
  if (e.target.checked) accessoryRows.forEach(row => accSelectedIds.add(row.id));
  else accSelectedIds.clear();
  renderAccessories();
};
async function accBulkSetActive(active) {
  if (!accSelectedIds.size) return;
  const r = await fetch("/api/admin/accessories/bulk-active", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ids: [...accSelectedIds], active }),
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) { document.getElementById("accErr").textContent = data.error || "Chyba."; return; }
  loadAccessories();
}
document.getElementById("accBulkActivate").onclick = () => accBulkSetActive(true);
document.getElementById("accBulkDeactivate").onclick = () => accBulkSetActive(false);
document.getElementById("accBulkDelete").onclick = async () => {
  if (!accSelectedIds.size) return;
  if (!confirm(`Opravdu smazat ${accSelectedIds.size} vybraných příslušenství?`)) return;
  const r = await fetch("/api/admin/accessories/bulk-delete", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ids: [...accSelectedIds] }),
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) { document.getElementById("accErr").textContent = data.error || "Chyba."; return; }
  accSelectedIds.clear();
  loadAccessories();
};

document.getElementById("btnAddAccessory").onclick = async () => {
  const name = document.getElementById("newAccName").value.trim();
  const price = document.getElementById("newAccPrice").value;
  const qty = document.getElementById("newAccQty").value;
  if (!name) { document.getElementById("accErr").textContent = "Zadej název."; return; }
  const r = await fetch("/api/admin/accessories", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, price_czk: parseFloat(price || 0), qty_per_joint: parseFloat(qty || 0) }),
  });
  const data = await r.json();
  if (!r.ok) { document.getElementById("accErr").textContent = data.error || "Chyba."; return; }
  document.getElementById("accErr").textContent = "";
  document.getElementById("newAccName").value = "";
  document.getElementById("newAccPrice").value = "";
  document.getElementById("newAccQty").value = "";
  loadAccessories();
};
