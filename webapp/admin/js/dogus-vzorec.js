// ==================== DOGUS: CENA NA E-SHOPU VS. VZOREC ====================
// Robert pres bot3, 2026-09-24 - navazuje na content_categories.dogus_sale_unit
// (FINALNI pevna klasifikace, bot5) a na scripts/2026-08-09_dogus_price_recompute.py
// (denni prepocet, ktery tenhle vzorec skutecne pouziva). Cisty READ-ONLY
// prehled: pro kazdou ze 3 sekci (tyc_3m / metraz / kus) ukazuje, jestli by
// se PRAVE TED (zivym kurzem Fio) spocitala jina cena, nez jakou ma e-shop
// ulozenou (shop_products.price_czk_placeholder, naposledy zapsana pri
// poslednim NEDELNIM behu se STARYM kurzem).
//
// Puvodni zadani bylo jedna tabulka s filtrem podle zarazeni - Robert to
// zmenil (pres bot3) na TRI SAMOSTATNE SEKCE, kazda s vlastnim vzorcem "na
// prvni pohled" a vlastnim nezavislym filtrem "jen kde se lisi". Vzorec
// samotny se NEPOCITA tady v JS (aby se nikdy nerozjel od backendu) - server
// (api/admin_profily.py::_dogus_formula_kc) uz vraci hotovy formula_price_czk
// + formula_calc_text + differs, JS jen renderuje/filtruje/straknuje.

const DOGUS_VZOREC_SECTIONS = [
  { key: "tyc_3m", title: "Hliníkové profily — tyče 3 m", hint: "1 ks = tyč 3000 mm, cena podle Dogus skupiny 9 + 2 potvrzené kategorie mimo ni (215, 192)." },
  { key: "metraz", title: "Metráž", hint: "Dogus sekce 84 profile-seals (naše kategorie 196) — prodává se po metrech, BEZ ×3." },
  { key: "kus", title: "Kusové položky", hint: "Vše ostatní spárované s Dogus (spojovací materiál, kryty, spojky…) — cena za 1 ks." },
];
const DOGUS_VZOREC_PAGE_STEP = 80;
// Datum Robertova jednorazoveho xlsx exportu (ne datum importu do DB) -
// jen pro popisek sloupce, at je hned videt, jak "cerstva" srovnavaci
// cena je (viz backups/2026-09-24_logiman_cenik_export.xlsx).
const DOGUS_VZOREC_EXPORT_DATE = "24.9.2026";

let dogusVzorecSections = { tyc_3m: [], metraz: [], kus: [] };
let dogusVzorecFioRate = null;
let dogusVzorecFioError = null;
// bot16, 2026-09-24 (Robert pres bot3, pravidlo 52) - srovnani s Robertovym
// jednorazovym xlsx exportem z logiman.cz (logiman_cz_price_export, viz
// api/admin_profily.py + sql/2026-09-24f_...). NENI totez jako prubezny
// crawl pouzity v zalozce "Ceny profilu" (logiman_cz_price_reference) -
// tady jde o historicky snapshot z konkretniho dne, ne o zivá data.
let dogusVzorecUnmatched = { file_not_in_catalog_count: 0, file_not_in_catalog: [], catalog_not_in_file_count: 0, catalog_not_in_file: [] };
let dogusVzorecUnmatchedOpen = { file: false, catalog: false };
const dogusVzorecOnlyDiff = { tyc_3m: false, metraz: false, kus: false };
const dogusVzorecPageSize = { tyc_3m: DOGUS_VZOREC_PAGE_STEP, metraz: DOGUS_VZOREC_PAGE_STEP, kus: DOGUS_VZOREC_PAGE_STEP };
// bot16, 2026-09-24 (dokonceni WIP - filtr "kategorie", chybel v puvodnim
// zadani "Filtry (minimum): kategorie, zařazení, přepínač jen rozdílné" -
// zařazení uz je pokryté 3 samostatnými sekcemi výš, kategorie ne).
// "" = vsechny kategorie, jinak string category_id (data-atributy jsou
// vzdy stringy, srovnava se proto stringove i v filtru nize).
let dogusVzorecCategoryFilter = "";

function dogusVzorecProductUrl(row) {
  return row.slug ? `/produkt/${row.slug}` : `/product.html?id=${row.id}`;
}

async function loadDogusCenaVzorec() {
  const errEl = document.getElementById("dogusVzorecErr");
  const wrapEl = document.getElementById("dogusVzorecWrap");
  if (errEl) errEl.textContent = "";
  try {
    // Zivy kurz Fio se ziska JEDNOU za nacteni zalozky (ne za radek) -
    // stejny endpoint jako "Ceny profilů" (api/admin_profily.py::admin_profily_fio_rate).
    const rateResp = await fetch("/api/admin/profily/fio-rate");
    const rateData = await rateResp.json().catch(() => ({}));
    if (rateResp.ok && rateData.rate != null) {
      dogusVzorecFioRate = rateData.rate;
      dogusVzorecFioError = null;
    } else {
      dogusVzorecFioRate = null;
      dogusVzorecFioError = rateData.error || "kurz se nepodařilo stáhnout";
    }

    const qs = dogusVzorecFioRate != null ? `?rate=${encodeURIComponent(dogusVzorecFioRate)}` : "";
    const rowsResp = await fetch(`/api/admin/dogus-cena-vzorec${qs}`);
    if (rowsResp.status === 401 || rowsResp.status === 403) {
      // Bez opravneni "dogus_cena/zobrazit" (bot16, 2026-09-29: vlastni
      // sekce, drive sdilela "ceny_prislusenstvi" s "Ceny profilů" - viz
      // AGENTS_LOG.md) - tab-btn uz je skryty, tady jen tise nic nenacitat.
      return;
    }
    if (!rowsResp.ok) throw new Error(`Načtení řádků selhalo (HTTP ${rowsResp.status})`);
    const data = await rowsResp.json();
    dogusVzorecSections = data.sections || { tyc_3m: [], metraz: [], kus: [] };
    dogusVzorecUnmatched = data.unmatched || dogusVzorecUnmatched;
    if (wrapEl) wrapEl.style.display = "";
    renderDogusVzorec();
  } catch (e) {
    if (errEl) errEl.textContent = "Chyba: " + e.message;
  }
}

function dogusVzorecEscape(s) {
  return String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

// bot16, 2026-09-24: vsechny radky napric 3 sekcemi jednim polem (pro
// vypocet kategorii k filtru a "posledniho hromadneho prepoctu" -
// summary/CSV pozadavek "kdy naposledy bezel denni prepocet").
function dogusVzorecAllRows() {
  return DOGUS_VZOREC_SECTIONS.flatMap((sec) => dogusVzorecSections[sec.key] || []);
}

function dogusVzorecCategoryOptionsHtml() {
  const byId = new Map();
  dogusVzorecAllRows().forEach((r) => {
    if (r.category_id != null && !byId.has(r.category_id)) byId.set(r.category_id, r.category_name || String(r.category_id));
  });
  const opts = [...byId.entries()].sort((a, b) => a[1].localeCompare(b[1], "cs"));
  return (
    `<option value="">— všechny kategorie —</option>` +
    opts.map(([id, name]) => `<option value="${id}" ${String(id) === dogusVzorecCategoryFilter ? "selected" : ""}>${dogusVzorecEscape(name)}</option>`).join("")
  );
}

function dogusVzorecFilterRows(rows) {
  return dogusVzorecCategoryFilter
    ? rows.filter((r) => String(r.category_id) === dogusVzorecCategoryFilter)
    : rows;
}

function dogusVzorecSummary() {
  let totalN = 0, totalDiff = 0, lastRefreshed = null;
  const parts = DOGUS_VZOREC_SECTIONS.map((sec) => {
    const rows = dogusVzorecFilterRows(dogusVzorecSections[sec.key] || []);
    const diffN = rows.filter((r) => r.differs === true).length;
    totalN += rows.length;
    totalDiff += diffN;
    rows.forEach((r) => {
      if (r.price_last_refreshed_at && (!lastRefreshed || r.price_last_refreshed_at > lastRefreshed)) lastRefreshed = r.price_last_refreshed_at;
    });
    return `<div style="margin:2px 0;"><strong>${dogusVzorecEscape(sec.title)}:</strong> ${rows.length} položek`
      + (diffN > 0 ? `, <span style="color:#b33;">${diffN} se liší od vzorce</span>` : ", vše sedí")
      + "</div>";
  });
  const rateLine = dogusVzorecFioRate != null
    ? `Živý kurz Fio (USD/CZK, prodej): <strong>${dogusVzorecFioRate.toFixed(3)} Kč/$</strong>`
    : `<span style="color:#b33;">Živý kurz Fio se nepodařilo stáhnout${dogusVzorecFioError ? " (" + dogusVzorecEscape(dogusVzorecFioError) + ")" : ""} — vzorec/rozdíl níže nelze dopočítat.</span>`;
  // "Poslední hromadný přepočet" - MAX(price_last_refreshed_at) mezi
  // zobrazenymi radky, tedy kdy denni automat (kazdy den 03:20) naposledy
  // skutecne zapsal cenu na tenhle produkt - NENI totez jako zivy kurz
  // vyse (ten je z PRAVE TEHLE chvile).
  const lastRefreshLine = lastRefreshed
    ? `Poslední hromadný přepočet (denní automat): <strong>${fmtFbxDate(lastRefreshed)}</strong>`
    : `<span style="color:#666;">Poslední hromadný přepočet: zatím žádný záznam.</span>`;
  const catFilterHtml = `<div style="margin:6px 0;"><label style="font-size:13px;">Kategorie: <select id="dogusVzorecCatFilterSelect">${dogusVzorecCategoryOptionsHtml()}</select></label></div>`;
  // bot16, 2026-09-24 (pravidlo 52) - srovnani s Robertovym jednorazovym
  // xlsx exportem logiman.cz, viz dogusVzorecUnmatchedHtml() nize pro
  // rozklikavaci seznamy obou smeru.
  const unmatchedLine = `<div style="margin-top:6px;padding-top:6px;border-top:1px solid rgba(255,255,255,0.08);font-size:12.5px;color:#aaa;">`
    + `Srovnání s exportem logiman.cz (<code>backups/2026-09-24_logiman_cenik_export.xlsx</code>, jednorázový import, ne živý crawl): `
    + `<strong>${dogusVzorecUnmatched.file_not_in_catalog_count}</strong> kódů v souboru nemáme v aktivním katalogu (možná se už neprodávají), `
    + `<strong>${dogusVzorecUnmatched.catalog_not_in_file_count}</strong> našich aktivních SKU není v souboru (možná nové od exportu).</div>`;
  return (
    `<div style="margin-bottom:2px;">${rateLine}</div>` +
    `<div style="margin-bottom:6px;">${lastRefreshLine}</div>` +
    catFilterHtml +
    parts.join("") +
    `<div style="margin-top:4px;"><strong>Celkem${dogusVzorecCategoryFilter ? " (po filtru kategorie)" : ""}:</strong> ${totalN} položek, ${totalDiff} se liší od vzorce.</div>` +
    unmatchedLine
  );
}

// bot16, 2026-09-24 (pravidlo 52) - dva rozklikavaci seznamy (Robert
// specificky chtel videt obe smery, ne jen souhrnne cislo, "je to pro
// nej samo o sobe zajimave"). Prosty <details>, zadne dalsi strankovani -
// 76+84 radku je v pohode zobrazit naraz.
function dogusVzorecUnmatchedHtml() {
  const fileRows = dogusVzorecUnmatched.file_not_in_catalog || [];
  const catalogRows = dogusVzorecUnmatched.catalog_not_in_file || [];
  const fileTable = fileRows.length
    ? `<table style="width:100%;margin-top:6px;"><thead><tr><th>SKU</th><th>Název (logiman.cz)</th><th>Cena (export)</th></tr></thead><tbody>`
      + fileRows.map((r) => `<tr><td>${dogusVzorecEscape(r.sku)}</td><td>${dogusVzorecEscape(r.name || "")}</td><td>${r.price_czk != null ? r.price_czk.toLocaleString("cs-CZ") + " Kč" : "—"}</td></tr>`).join("")
      + `</tbody></table>`
    : `<p class="hint">Žádné.</p>`;
  const catalogTable = catalogRows.length
    ? `<table style="width:100%;margin-top:6px;"><thead><tr><th>SKU</th><th>Název / kategorie</th><th>Dogus?</th></tr></thead><tbody>`
      + catalogRows.map((r) => `<tr><td><a href="/product.html?id=${r.id}" target="_blank" rel="noopener noreferrer">${dogusVzorecEscape(r.sku)}</a></td><td>${dogusVzorecEscape(r.name)}<div style="font-size:10.5px;color:#666;">${dogusVzorecEscape(r.category_name || "")}</div></td><td>${r.has_dogus ? "ano" : "—"}</td></tr>`).join("")
      + `</tbody></table>`
    : `<p class="hint">Žádné.</p>`;
  return (
    `<h3 style="margin-bottom:2px;">Nespárované SKU (export logiman.cz ↔ náš aktivní katalog)</h3>` +
    `<p class="hint" style="margin-top:0;">Porovnání proti CELÉMU aktivnímu a zařazenému katalogu (ne jen položkám spárovaným s Dogus výše) — SKU je párovací klíč.</p>` +
    `<details ${dogusVzorecUnmatchedOpen.file ? "open" : ""} id="dogusVzorecUnmatchedFileDetails">` +
    `<summary style="cursor:pointer;">V souboru, ale nemáme v katalogu (${fileRows.length})</summary>${fileTable}</details>` +
    `<details ${dogusVzorecUnmatchedOpen.catalog ? "open" : ""} id="dogusVzorecUnmatchedCatalogDetails" style="margin-top:10px;">` +
    `<summary style="cursor:pointer;">Máme v katalogu, ale v souboru není (${catalogRows.length})</summary>${catalogTable}</details>`
  );
}

function dogusVzorecDiffCellHtml(r) {
  if (r.differs == null) return '<span style="color:#666;">—</span>';
  if (!r.differs) return '<span style="color:#2a7a2a;">sedí (0 Kč)</span>';
  // Konvence znamenka STEJNA jako CSV export (api/admin_profily.py):
  // rozdil = cena_na_webu − cena_dle_vzorce (kladne = web je DRAŽŠÍ, než
  // vzorec ríká).
  const diffKc = r.actual_price_czk - r.formula_price_czk;
  const diffPct = r.actual_price_czk ? (diffKc / r.actual_price_czk * 100) : null;
  const sign = diffKc > 0 ? "+" : "";
  return (
    `<span style="color:#b33;font-weight:600;">${sign}${diffKc.toFixed(0)} Kč</span>` +
    (diffPct != null ? `<div style="font-size:10.5px;color:#b33;">${sign}${diffPct.toFixed(1)} %</div>` : "")
  );
}

// bot16, 2026-09-24 (pravidlo 52) - obecna verze dogusVzorecDiffCellHtml
// parametrizovana na libovolny diffKc/diffPct pár (puvodni funkce je
// pevne svazana s r.actual_price_czk/r.formula_price_czk). POZOR na
// rozdilnou bazi procenta oproti puvodnimu sloupci "Rozdíl" (vzorec):
// tenhle sloupec pocita % vuci cene logiman.cz (kolik % jsme dražší/
// levnější NEŽ logiman.cz), ne vuci nasi vlastni cene - overeno primo
// proti bot3 zadanym medianum (tyc_3m +10.8 %, kus −5.1 %), s bazi
// "naše cena" by vyšla jiná čísla. Barva: cervena = jsme drazsi nez
// logiman.cz, zelena = jsme levnejsi.
function dogusVzorecGenericDiffCellHtml(diffKc, diffPct, { positiveIsBad = true } = {}) {
  if (diffKc == null) return '<span style="color:#666;">—</span>';
  if (Math.round(diffKc) === 0) return '<span style="color:#2a7a2a;">shoda (0 Kč)</span>';
  const bad = positiveIsBad ? diffKc > 0 : diffKc < 0;
  const color = bad ? "#b33" : "#2a7a2a";
  const sign = diffKc > 0 ? "+" : "";
  return (
    `<span style="color:${color};font-weight:600;">${sign}${diffKc.toFixed(0)} Kč</span>` +
    (diffPct != null ? `<div style="font-size:10.5px;color:${color};">${sign}${diffPct.toFixed(1)} %</div>` : "")
  );
}

// bot16, 2026-09-24 (pravidlo 52) - metrazova sekce mixuje jednotky na
// logiman.cz (7 z 39 polozek je cena za CELOU tyc 3 m, 32 za 1 m - viz
// _METRAZ_ROD_RATIO_THRESHOLD v api/admin_profily.py). Zobrazuje OBE
// baze vedle sebe s odhadovanym oznacenim, NIKDY nekolabuje do jedne
// "spravne" odpovedi - Robertovo vyslovne zadani.
function dogusVzorecMetrazLogimanCellsHtml(r) {
  const info = r.logiman_metraz_info;
  const logimanPrice = r.logiman_export_price_czk;
  if (logimanPrice == null || !info) {
    return { priceCell: '<span style="color:#666;">—</span>', diffCell: '<span style="color:#666;">—</span>' };
  }
  const basisLabel = info.basis_guess === "per_3m_rod"
    ? `<span style="color:#c98;font-weight:600;">pravděpodobně za tyč 3 m</span>`
    : (info.basis_guess === "per_meter" ? `<span style="color:#8ac;font-weight:600;">pravděpodobně za 1 m</span>` : "");
  const ratioText = info.ratio_logiman_to_our_per_m != null
    ? `<div style="font-size:10px;color:#666;">poměr logiman/naše-za-m: ${info.ratio_logiman_to_our_per_m.toFixed(2)}×</div>` : "";
  const priceCell = (
    `${logimanPrice.toLocaleString("cs-CZ")} Kč${basisLabel ? "<div style=\"font-size:10.5px;margin-top:2px;\">" + basisLabel + "</div>" : ""}${ratioText}` +
    `<div style="font-size:10px;color:#666;margin-top:2px;">naše/m: ${info.our_price_per_m_czk != null ? info.our_price_per_m_czk.toLocaleString("cs-CZ") + " Kč" : "—"}` +
    ` · naše×3: ${info.our_price_x3_czk != null ? info.our_price_x3_czk.toLocaleString("cs-CZ") + " Kč" : "—"}</div>`
  );
  const perMCell = dogusVzorecGenericDiffCellHtml(info.diff_per_m_kc, info.diff_per_m_pct);
  const x3Cell = dogusVzorecGenericDiffCellHtml(info.diff_x3_kc, info.diff_x3_pct);
  const dim = (html) => `<div style="opacity:0.45;">${html}</div>`;
  const diffCell = (
    `<div style="font-size:10px;color:#888;">vs. 1 m:</div>${info.basis_guess === "per_meter" ? perMCell : dim(perMCell)}` +
    `<div style="font-size:10px;color:#888;margin-top:4px;">vs. tyč 3 m:</div>${info.basis_guess === "per_3m_rod" ? x3Cell : dim(x3Cell)}`
  );
  return { priceCell, diffCell };
}

function dogusVzorecSectionRowsHtml(sec) {
  const allRows = dogusVzorecFilterRows(dogusVzorecSections[sec.key] || []);
  const rows = dogusVzorecOnlyDiff[sec.key] ? allRows.filter((r) => r.differs === true) : allRows;
  const shown = rows.slice(0, dogusVzorecPageSize[sec.key]);
  if (!shown.length) {
    return `<tr><td colspan="8" class="hint">Žádné položky${dogusVzorecOnlyDiff[sec.key] ? " (při aktivním filtru „jen rozdílné“)" : ""}.</td></tr>`;
  }
  return shown.map((r) => {
    const calc = r.formula_calc_text
      ? `<div style="font-size:11px;color:#666;margin-top:2px;">${dogusVzorecEscape(r.formula_calc_text)}</div>`
      : '<span style="color:#666;">kurz nedostupný</span>';
    const formulaCzk = r.formula_price_czk != null ? `${r.formula_price_czk} Kč` : "—";
    const actualCzk = r.actual_price_czk != null ? `${r.actual_price_czk.toLocaleString("cs-CZ")} Kč` : "—";
    // bot16, 2026-09-24: "kdy stažena" (shop_products.price_last_refreshed_at,
    // stejna konvence jako uz existujici "Ceny profilů" - viz admin_profily.py
    // komentar u dogus_price_usd_fetched_at) + kurz POUZITY PRI POSLEDNIM
    // dennim prepoctu (jiny udaj nez zivy kurz nahore v summary).
    const fetchedAt = r.price_last_refreshed_at
      ? `<div style="font-size:10.5px;color:#666;margin-top:2px;">staženo ${fmtFbxDate(r.price_last_refreshed_at)}</div>` : "";
    const rateUsed = r.dogus_price_rate_used != null
      ? `<div style="font-size:10.5px;color:#666;margin-top:2px;">kurz při posledním přepočtu: ${r.dogus_price_rate_used.toFixed(3)} Kč/$</div>` : "";
    const skuCell = r.dogus_url
      ? `<a href="${dogusVzorecEscape(r.dogus_url)}" target="_blank" rel="noopener noreferrer" title="Otevřít stránku produktu na Dogus">${dogusVzorecEscape(r.sku || "")}</a>`
      : dogusVzorecEscape(r.sku || "");
    // bot16, 2026-09-24 (pravidlo 52) - 2 nove sloupce: cena logiman.cz
    // (jednorazovy Robertuv export) + rozdil vuci ni. Metraz ma vlastni
    // rozsirenou verzi (dve baze, viz dogusVzorecMetrazLogimanCellsHtml).
    let logimanPriceCell, logimanDiffCell;
    if (sec.key === "metraz") {
      const cells = dogusVzorecMetrazLogimanCellsHtml(r);
      logimanPriceCell = cells.priceCell;
      logimanDiffCell = cells.diffCell;
    } else {
      logimanPriceCell = r.logiman_export_price_czk != null
        ? `${r.logiman_export_price_czk.toLocaleString("cs-CZ")} Kč` : '<span style="color:#666;">—</span>';
      logimanDiffCell = dogusVzorecGenericDiffCellHtml(r.logiman_export_diff_kc, r.logiman_export_diff_pct);
    }
    return (
      `<tr>` +
      `<td>${skuCell}</td>` +
      `<td><a href="${dogusVzorecProductUrl(r)}" target="_blank" rel="noopener noreferrer">${dogusVzorecEscape(r.name)}</a>` +
      `<div style="font-size:10.5px;color:#666;">${dogusVzorecEscape(r.category_name || "")}</div></td>` +
      `<td>${r.dogus_list_price_usd != null ? r.dogus_list_price_usd.toFixed(2) + " $" : "—"}${fetchedAt}</td>` +
      `<td>${formulaCzk}${calc}</td>` +
      `<td>${actualCzk}${rateUsed}</td>` +
      `<td>${dogusVzorecDiffCellHtml(r)}</td>` +
      `<td>${logimanPriceCell}</td>` +
      `<td>${logimanDiffCell}</td>` +
      `</tr>`
    );
  }).join("");
}

function dogusVzorecSectionHtml(sec) {
  const allRows = dogusVzorecFilterRows(dogusVzorecSections[sec.key] || []);
  const rows = dogusVzorecOnlyDiff[sec.key] ? allRows.filter((r) => r.differs === true) : allRows;
  const diffN = allRows.filter((r) => r.differs === true).length;
  const hasMore = rows.length > dogusVzorecPageSize[sec.key];
  return (
    `<h3 style="margin-bottom:2px;">${dogusVzorecEscape(sec.title)}</h3>` +
    `<p class="hint" style="margin-top:0;">${dogusVzorecEscape(sec.hint)}</p>` +
    `<p style="font-size:13px;margin:4px 0;">${allRows.length} položek, <strong>${diffN}</strong> se liší od vzorce.` +
    ` <label style="margin-left:10px;font-weight:normal;"><input type="checkbox" class="dogusVzorecOnlyDiff" data-section="${sec.key}" ${dogusVzorecOnlyDiff[sec.key] ? "checked" : ""}> jen ty, kde se cena na webu liší od vzorce</label></p>` +
    `<table style="width:100%;">` +
    `<thead><tr><th>SKU (odkaz na Dogus)</th><th>Název / kategorie</th><th>Cena USD (Dogus)</th><th>Vzorec (živý kurz)</th><th>Cena e-shop (aktuální)</th><th>Rozdíl (vzorec)</th>` +
    `<th>Cena logiman.cz (export ${dogusVzorecEscape(DOGUS_VZOREC_EXPORT_DATE)})</th><th>Rozdíl vs. logiman.cz</th></tr></thead>` +
    `<tbody id="dogusVzorecTbody_${sec.key}">${dogusVzorecSectionRowsHtml(sec)}</tbody>` +
    `</table>` +
    (hasMore
      ? `<button class="dogusVzorecMore" data-section="${sec.key}" style="margin:8px 0;">Zobrazit dalších ${Math.min(DOGUS_VZOREC_PAGE_STEP, rows.length - dogusVzorecPageSize[sec.key])} (z ${rows.length - dogusVzorecPageSize[sec.key]} zbývajících)</button>`
      : "")
  );
}

function renderDogusVzorec() {
  const summaryEl = document.getElementById("dogusVzorecSummary");
  if (summaryEl) summaryEl.innerHTML = dogusVzorecSummary();
  DOGUS_VZOREC_SECTIONS.forEach((sec) => {
    const el = document.getElementById(`dogusVzorecSection_${sec.key}`);
    if (el) el.innerHTML = dogusVzorecSectionHtml(sec);
  });
  const unmatchedEl = document.getElementById("dogusVzorecUnmatchedSection");
  if (unmatchedEl) {
    unmatchedEl.innerHTML = dogusVzorecUnmatchedHtml();
    const fileDetails = document.getElementById("dogusVzorecUnmatchedFileDetails");
    if (fileDetails) fileDetails.addEventListener("toggle", () => { dogusVzorecUnmatchedOpen.file = fileDetails.open; });
    const catalogDetails = document.getElementById("dogusVzorecUnmatchedCatalogDetails");
    if (catalogDetails) catalogDetails.addEventListener("toggle", () => { dogusVzorecUnmatchedOpen.catalog = catalogDetails.open; });
  }
  const catSel = document.getElementById("dogusVzorecCatFilterSelect");
  if (catSel) {
    catSel.onchange = () => {
      dogusVzorecCategoryFilter = catSel.value;
      DOGUS_VZOREC_SECTIONS.forEach((sec) => { dogusVzorecPageSize[sec.key] = DOGUS_VZOREC_PAGE_STEP; });
      renderDogusVzorec();
    };
  }
  document.querySelectorAll(".dogusVzorecOnlyDiff").forEach((cb) => {
    cb.addEventListener("change", (ev) => {
      const key = ev.target.dataset.section;
      dogusVzorecOnlyDiff[key] = ev.target.checked;
      dogusVzorecPageSize[key] = DOGUS_VZOREC_PAGE_STEP;
      renderDogusVzorec();
    });
  });
  document.querySelectorAll(".dogusVzorecMore").forEach((btn) => {
    btn.addEventListener("click", (ev) => {
      const key = ev.target.dataset.section;
      dogusVzorecPageSize[key] += DOGUS_VZOREC_PAGE_STEP;
      renderDogusVzorec();
    });
  });
}

function dogusVzorecExportUrl() {
  const params = new URLSearchParams();
  if (dogusVzorecFioRate != null) params.set("rate", dogusVzorecFioRate);
  if (dogusVzorecCategoryFilter) params.set("category_id", dogusVzorecCategoryFilter);
  DOGUS_VZOREC_SECTIONS.forEach((sec) => {
    params.set(`only_diff_${sec.key}`, dogusVzorecOnlyDiff[sec.key] ? "1" : "0");
  });
  return `/api/admin/dogus-cena-vzorec/export.csv?${params.toString()}`;
}

document.addEventListener("DOMContentLoaded", () => {
  const btn = document.getElementById("btnDogusVzorecExportCsv");
  if (btn) {
    btn.addEventListener("click", () => {
      window.open(dogusVzorecExportUrl(), "_blank");
    });
  }
});
