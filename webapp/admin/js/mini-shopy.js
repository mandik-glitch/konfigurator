// ==================== MINI-SHOPY (miniweb_*: slovensky/anglicky shop sestav stolu) ====================
// bot16, 2026-10-03 (Robert pres bot3: sprava mini-shopu v ADMINU, stejne ucty a RBAC jako konfigurator). Data: api/miniweb_admin.py (bot5):
//   GET /api/admin/miniweb/shops | PUT /api/admin/miniweb/shops/<id> | GET /api/admin/miniweb/inquiries?shop= | GET /api/admin/miniweb/orders?shop=
// RBAC sekce `miniweb` (zobrazit = cteni, upravit = PUT) a `miniweb_schvalovani` (schvalovani textu na /miniweb-schvaleni.html).
// Stav shopu (draft/live) se TADY nemeni - live jen skriptem go-live (kontroly textu, dokumentu a vhostu).
let mwShops = [];
let mwSub = "shops";

const MW_PRICE_MODE = { hidden: "skryté", indicative: "orientační", shown: "zobrazené" };
const MW_ERR = {
  unknown_field: "Neznámé pole (stav shopu se zde nemění - live jen skriptem go-live).", price_mode_invalid: "Neplatný režim cen.", margin_pct_invalid: "Marže musí být 0 až 500 % (nebo prázdná).",
  eur_rate_invalid: "Kurz musí být kladné číslo (prázdný = živý kurz z Fio).", countries_invalid: "Neplatné země (např. SK nebo SK,CZ).", inquiry_enabled_invalid: "Neplatná hodnota poptávek.",
  orders_enabled_invalid: "Neplatná hodnota objednávek.", accent_invalid: "Barva musí být ve tvaru #rrggbb.", currency_invalid: "Neplatná měna.", contact_invalid: "Neplatný kontakt.",
  invalid_json: "Neplatný požadavek.", not_found: "Shop neexistuje.", forbidden: "Nemáte oprávnění tohle měnit.",
  price_not_configured: "Objednávky lze zapnout jen s cenami „zobrazené“, měnou EUR a nastavenou marží.",
};

function mwEsc(s) { return escapeHtmlAdmin(s == null ? "" : String(s)); }
async function mwGet(url) { const r = await fetch(url); const d = await r.json().catch(() => ({})); if (!r.ok) throw new Error(d.error || ("HTTP " + r.status)); return d; }

function loadMiniwebShops() {
  const err = document.getElementById("mwErr"); if (err) err.textContent = "";
  mwGet("/api/admin/miniweb/shops").then(d => { mwShops = d.shops || []; mwFillShopSelects(); mwRender(); }).catch(e => { if (err) err.textContent = "Nepodařilo se načíst mini-shopy: " + e.message; });
}

function mwFillShopSelects() {
  ["mwInqShop", "mwOrdShop"].forEach(id => {
    const sel = document.getElementById(id); if (!sel) return; const cur = sel.value;
    sel.innerHTML = mwShops.map(s => `<option value="${s.storefront_id}">${mwEsc(s.name)} · ${mwEsc(s.domain)}</option>`).join("");
    if (cur) sel.value = cur;
  });
}

function mwRender() {
  document.querySelectorAll("#tab-miniweb .mw-sub").forEach(b => b.classList.toggle("active", b.dataset.sub === mwSub));
  ["shops", "inquiries", "orders", "texts"].forEach(k => { const el = document.getElementById("mwSub-" + k); if (el) el.hidden = k !== mwSub; });
  if (mwSub === "shops") mwRenderShops(); else if (mwSub === "inquiries") mwLoadInquiries(); else if (mwSub === "orders") mwLoadOrders();
  else { const fr = document.getElementById("mwTextsFrame"); if (fr && !fr.getAttribute("src")) fr.setAttribute("src", "/miniweb-schvaleni.html"); }   // stejna prihlasena relace, stranka bot5 si hlida oprávnění sama
}

function mwRenderShops() {
  const wrap = document.getElementById("mwShopsList");
  if (!mwShops.length) { wrap.innerHTML = '<p class="hint">Zatím žádný mini-shop.</p>'; return; }
  wrap.innerHTML = `<table class="cn-form-tbl" style="width:100%;"><thead><tr><th>Shop</th><th>Doména</th><th>Jazyk</th><th>Stav</th><th>Ceny</th><th>Kurz</th><th>Marže</th><th>Země</th><th>Poptávky</th><th>Objednávky</th><th></th></tr></thead><tbody>${
    mwShops.map(s => `<tr data-id="${s.storefront_id}">
      <td>${mwEsc(s.name)}</td><td><a href="https://${mwEsc(s.domain)}" target="_blank" rel="noopener">${mwEsc(s.domain)}</a></td><td>${mwEsc(s.lang)}</td>
      <td>${s.status === "live" ? "🟢 live" : "⚪ koncept"}</td><td>${mwEsc(MW_PRICE_MODE[s.price_mode] || s.price_mode)} (${mwEsc(s.currency || "-")})</td>
      <td>${s.eur_rate != null ? mwEsc(s.eur_rate) + " (ruční)" : (s.live_rate != null ? mwEsc(s.live_rate) + " (Fio)" : "Fio")}</td>
      <td>${s.margin_pct != null ? mwEsc(s.margin_pct) + " %" : "-"}</td><td>${mwEsc((s.countries || []).join(", "))}</td>
      <td>${mwEsc(s.inquiries)}${s.inquiry_enabled ? "" : " (vypnuté)"}</td><td>${mwEsc(s.orders)}${s.orders_to_review ? ` <b style="color:#e0a070;">(${mwEsc(s.orders_to_review)} ke schválení)</b>` : ""}${s.orders_enabled ? "" : " (vypnuté)"}</td>
      <td><button type="button" class="mw-edit" data-id="${s.storefront_id}">Upravit</button></td></tr>`).join("")}</tbody></table>`;
  wrap.querySelectorAll(".mw-edit").forEach(b => b.onclick = () => mwOpenEdit(mwShops.find(s => s.storefront_id === parseInt(b.dataset.id, 10))));
}

function mwOpenEdit(s) {
  const box = document.getElementById("mwEdit"); if (!s) return;
  const c = s.contact || {};
  box.hidden = false; box.dataset.id = s.storefront_id;
  box.innerHTML = `<h3>${mwEsc(s.name)} · ${mwEsc(s.domain)} (${s.status === "live" ? "live" : "koncept"})</h3>
    <div class="mw-grid">
      <label>Ceny <select id="mwfPrice"><option value="hidden">skryté</option><option value="shown">zobrazené</option><option value="indicative">orientační</option></select></label>
      <label>Měna <input id="mwfCurrency" maxlength="3" style="width:70px;" value="${mwEsc(s.currency || "")}"></label>
      <label>Marže % <input id="mwfMargin" type="number" min="0" max="500" step="0.1" style="width:90px;" value="${s.margin_pct != null ? mwEsc(s.margin_pct) : ""}"></label>
      <label>Kurz CZK→EUR (prázdný = živý Fio) <input id="mwfRate" type="number" min="0" step="0.001" style="width:110px;" value="${s.eur_rate != null ? mwEsc(s.eur_rate) : ""}"></label>
      <label>Země <input id="mwfCountries" style="width:110px;" value="${mwEsc((s.countries || []).join(","))}"></label>
      <label>Barva akcentu <input id="mwfAccent" style="width:90px;" value="${mwEsc(s.accent || "")}"></label>
      <label><input type="checkbox" id="mwfInq" ${s.inquiry_enabled ? "checked" : ""}> Poptávky zapnuté</label>
      <label><input type="checkbox" id="mwfOrd" ${s.orders_enabled ? "checked" : ""}> Objednávky zapnuté</label>
      <label>Telefon (kontakt) <input id="mwfPhone" style="width:150px;" value="${mwEsc(c.phone || "")}"></label>
      <label>Otevírací doba <input id="mwfHours" style="width:150px;" value="${mwEsc(c.hours || "")}"></label>
      <label><input type="checkbox" id="mwfUseCompany" ${c.use_company ? "checked" : ""}> Kontakt z údajů společnosti</label>
    </div>
    <div style="margin-top:8px;"><button type="button" id="mwfSave">Uložit</button> <button type="button" id="mwfCancel" style="background:none;border:1px solid #3a3f4a;color:#c7ccd4;">Zavřít</button> <span id="mwfMsg" style="margin-left:8px;"></span></div>`;
  document.getElementById("mwfPrice").value = s.price_mode === "indicative" ? "indicative" : (s.price_mode === "shown" ? "shown" : "hidden");
  document.getElementById("mwfCancel").onclick = () => { box.hidden = true; };
  document.getElementById("mwfSave").onclick = async () => {
    const msg = document.getElementById("mwfMsg"); msg.style.color = "#c7ccd4"; msg.textContent = "Ukládám…";
    const num = id => { const v = document.getElementById(id).value.trim(); return v === "" ? null : Number(v); };
    const body = { price_mode: document.getElementById("mwfPrice").value, currency: document.getElementById("mwfCurrency").value.trim().toUpperCase(), margin_pct: num("mwfMargin"), eur_rate: num("mwfRate"),
      countries: document.getElementById("mwfCountries").value.trim(), accent: document.getElementById("mwfAccent").value.trim() || undefined, inquiry_enabled: document.getElementById("mwfInq").checked, orders_enabled: document.getElementById("mwfOrd").checked,
      contact: { phone: document.getElementById("mwfPhone").value.trim(), hours: document.getElementById("mwfHours").value.trim(), use_company: document.getElementById("mwfUseCompany").checked } };
    try {
      const r = await fetch("/api/admin/miniweb/shops/" + s.storefront_id, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      const d = await r.json().catch(() => ({}));
      if (!r.ok) { msg.style.color = "#e07070"; msg.textContent = (MW_ERR[d.error] || d.error || "Chyba.") + (d.field ? " (" + d.field + ")" : ""); return; }
      msg.style.color = "#7ed49a"; msg.textContent = "Uloženo."; loadMiniwebShops();
    } catch (e) { msg.style.color = "#e07070"; msg.textContent = "Spojení selhalo."; }
  };
}

function mwTable(headers, rows) {
  return `<table class="cn-form-tbl" style="width:100%;"><thead><tr>${headers.map(h => `<th>${h}</th>`).join("")}</tr></thead><tbody>${rows.length ? rows.join("") : `<tr><td colspan="${headers.length}" style="color:#666;">Nic tu zatím není.</td></tr>`}</tbody></table>`;
}
function mwLoadInquiries() {
  const sel = document.getElementById("mwInqShop"), out = document.getElementById("mwInqList"); if (!sel || !sel.value) { out.innerHTML = ""; return; }
  mwGet("/api/admin/miniweb/inquiries?shop=" + sel.value + "&limit=100").then(d => {
    out.innerHTML = `<p class="hint">Celkem ${mwEsc(d.total)} poptávek (osobní údaje jsou v CRM).</p>` + mwTable(["#", "Datum", "Firma", "Jméno", "Země", "Položek", ""], (d.inquiries || []).map(i =>
      `<tr><td>${mwEsc(i.id)}</td><td>${mwEsc(new Date(i.created_at).toLocaleString("cs-CZ"))}</td><td>${mwEsc(i.company)}</td><td>${mwEsc(i.name)}</td><td>${mwEsc(i.country)}</td><td>${mwEsc(Array.isArray(i.items) ? i.items.length : i.items)}</td><td>${i.unread ? "●" : ""}</td></tr>`));
  }).catch(e => { out.innerHTML = `<p class="err">${mwEsc(e.message)}</p>`; });
}
function mwLoadOrders() {
  const sel = document.getElementById("mwOrdShop"), out = document.getElementById("mwOrdList"); if (!sel || !sel.value) { out.innerHTML = ""; return; }
  mwGet("/api/admin/miniweb/orders?shop=" + sel.value + "&limit=100").then(d => {
    out.innerHTML = `<p class="hint">Celkem ${mwEsc(d.total)} objednávek z tohoto shopu. Detail, úprava a schválení dopravy: Objednávky (klik na číslo).</p>` + mwTable(["Číslo", "Datum", "Firma", "IČO", "Celkem", "Stav", "Doprava", "DPH"], (d.orders || []).map(o =>
      `<tr><td><a href="#" class="mw-ord" data-id="${o.id}">${mwEsc(o.order_number)}</a></td><td>${mwEsc(new Date(o.created_at).toLocaleString("cs-CZ"))}</td><td>${mwEsc(o.company || o.customer_name)}</td><td>${mwEsc(o.company_id)}</td>
       <td>${o.total_czk != null ? Number(o.total_czk).toLocaleString("cs-CZ") + " Kč" : ""}</td><td>${mwEsc(o.status)}${o.is_urgent ? " ⚠ ruční kontrola" : ""}</td><td>${o.shipping_review ? "ke schválení" : "-"}</td><td>${mwEsc(o.vat_mode || "")}</td></tr>`));
    out.querySelectorAll(".mw-ord").forEach(a => a.onclick = (e) => { e.preventDefault(); const t = document.querySelector('.tab-btn[data-tab="orders"]'); if (t) t.click(); setTimeout(() => openOrderDetail(parseInt(a.dataset.id, 10)), 300); });
  }).catch(e => { out.innerHTML = `<p class="err">${mwEsc(e.message)}</p>`; });
}

document.addEventListener("click", (e) => {
  const b = e.target.closest("#tab-miniweb .mw-sub"); if (!b) return; mwSub = b.dataset.sub; mwRender();
});
["mwInqShop", "mwOrdShop"].forEach(id => { const el = document.getElementById(id); if (el) el.onchange = mwRender; });
