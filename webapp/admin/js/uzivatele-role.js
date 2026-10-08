// ==================== UZIVATELE ====================
let usersCache = [];
let userSelectedIds = new Set();
async function loadUsers() {
  const r = await fetch("/api/admin/users");
  const data = await r.json();
  usersCache = data.users || [];
  userSelectedIds.clear();
  updateUserBulkToolbar();
  renderUsers(usersCache);
}

function renderUsers(users) {
  const tbody = document.getElementById("usersTbody");
  tbody.innerHTML = "";
  users.forEach(u => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td><input type="checkbox" class="u-chk" data-id="${u.id}" ${userSelectedIds.has(u.id) ? "checked" : ""}></td>
      <td>${u.email}</td>
      <td>${u.name || ""}</td>
      <td>
        <select class="u-role">
          <option value="user" ${u.role === "user" ? "selected" : ""}>uživatel</option>
          <option value="manager" ${u.role === "manager" ? "selected" : ""}>manager</option>
          <option value="skladnik" ${u.role === "skladnik" ? "selected" : ""}>mistr</option>
          <option value="ucetni" ${u.role === "ucetni" ? "selected" : ""}>asistent</option>
          <option value="monter" ${u.role === "monter" ? "selected" : ""}>montér</option>
          <option value="sklad" ${u.role === "sklad" ? "selected" : ""}>skladník</option>
          <option value="admin" ${u.role === "admin" ? "selected" : ""}>admin</option>
        </select>
      </td>
      <td><input type="checkbox" class="u-active" ${u.active ? "checked" : ""}></td>
      <td><input type="password" class="u-newpass" placeholder="(beze změny)" style="width:120px;"></td>
      <td><button class="u-save">Uložit</button> <button class="u-delete danger">Smazat</button></td>
    `;
    tr.querySelector(".u-chk").onchange = (e) => {
      if (e.target.checked) userSelectedIds.add(u.id); else userSelectedIds.delete(u.id);
      updateUserBulkToolbar();
    };
    tr.querySelector(".u-save").onclick = async () => {
      const body = {
        role: tr.querySelector(".u-role").value,
        active: tr.querySelector(".u-active").checked,
      };
      const passField = tr.querySelector(".u-newpass");
      const pass = passField.value;
      if (pass) body.password = pass;
      const r = await fetch(`/api/admin/users/${u.id}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      const data = await r.json().catch(() => ({}));
      if (!r.ok) { alert(data.error || "Chyba."); return; }
      // Neresetuje se cela tabulka (loadUsers by smazalo rozepsane zmeny v
      // ostatnich radcich) - jen se potvrdi ulozeny stav tohoto radku.
      u.role = body.role;
      u.active = body.active;
      passField.value = "";
    };
    tr.querySelector(".u-delete").onclick = async () => {
      if (!confirm(`Smazat uživatele ${u.email}?`)) return;
      const r = await fetch(`/api/admin/users/${u.id}`, { method: "DELETE" });
      const data = await r.json();
      if (!r.ok) { alert(data.error || "Chyba."); return; }
      usersCache = usersCache.filter(x => x.id !== u.id);
      userSelectedIds.delete(u.id);
      updateUserBulkToolbar();
      tr.remove();
    };
    tbody.appendChild(tr);
  });
}

function updateUserBulkToolbar() {
  const bar = document.getElementById("userBulkToolbar");
  const count = userSelectedIds.size;
  bar.classList.toggle("active", count > 0);
  document.getElementById("userBulkCount").textContent = `${count} vybráno`;
}
document.getElementById("userSelectAll").onchange = (e) => {
  if (e.target.checked) usersCache.forEach(u => userSelectedIds.add(u.id));
  else userSelectedIds.clear();
  renderUsers(usersCache);
};
document.getElementById("userBulkApplyRole").onclick = async () => {
  if (!userSelectedIds.size) return;
  const role = document.getElementById("userBulkRole").value;
  if (!role) return;
  const r = await fetch("/api/admin/users/bulk-role", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ids: [...userSelectedIds], role }),
  });
  const data = await r.json().catch(() => ({}));
  if (data.failed && data.failed.length) {
    alert(`Nastaveno: ${data.updated}. Přeskočeno: ${data.failed.length} (např. poslední aktivní admin).`);
  }
  loadUsers();
};
async function userBulkSetActive(active) {
  if (!userSelectedIds.size) return;
  const r = await fetch("/api/admin/users/bulk-active", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ids: [...userSelectedIds], active }),
  });
  const data = await r.json().catch(() => ({}));
  if (data.failed && data.failed.length) {
    alert(`Nastaveno: ${data.updated}. Přeskočeno: ${data.failed.length} (např. poslední aktivní admin).`);
  }
  loadUsers();
}
document.getElementById("userBulkActivate").onclick = () => userBulkSetActive(true);
document.getElementById("userBulkDeactivate").onclick = () => userBulkSetActive(false);

document.getElementById("btnAddUser").onclick = async () => {
  const email = document.getElementById("newUserEmail").value.trim();
  const name = document.getElementById("newUserName").value.trim();
  const role = document.getElementById("newUserRole").value;
  const password = document.getElementById("newUserPassword").value;
  const r = await fetch("/api/admin/users", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, name, role, password }),
  });
  const data = await r.json();
  if (!r.ok) { document.getElementById("userErr").textContent = data.error || "Chyba."; return; }
  document.getElementById("userErr").textContent = "";
  document.getElementById("newUserEmail").value = "";
  document.getElementById("newUserName").value = "";
  document.getElementById("newUserPassword").value = "";
  loadUsers();
};

// ==================== ROLE A OPRAVNENI (RBAC checkbox UI) ====================
// bot2, 2026-07-25. Zdroj dat: GET/PUT /api/admin/role-permissions (bot3, viz
// api/app.py PERMISSION_SECTIONS/PERMISSION_ACTIONS/PERMISSION_ROLES).
const RP_SECTION_LABELS = {
  objednavky: "Objednávky", nakupni_objednavky: "Nákupní objednávky",
  doklady: "Doklady", emaily_odchozi: "Emaily odchozí", zakaznici: "Zákazníci",
  doprava_platba: "Doprava a platba",
  uzivatele: "Uživatelé", nastaveni: "Nastavení", audit_log: "Audit log",
  // bot16, 2026-09-29 (Robert pres bot3, "rozsekat kategorie_obsah/
  // ceny_prislusenstvi/produkty_sklad na dnesni granularitu zalozek",
  // potvrzeno - viz AGENTS_LOG.md): nahrazuje 3 puvodni siroke sekce.
  kategorie: "Kategorie", homepage_mozaika: "Homepage mozaika",
  homepage_carousel: "Homepage carousel", centralni_texty: "Centrální texty",
  hlasky: "Hlášky", postranni_panel: "Postranní panel",
  ceny_profilu: "Ceny profilů", dogus_cena: "Dogus cena", prislusenstvi: "Příslušenství",
  sklad_karty: "Skladové karty", sklad_pohyby: "Skladové pohyby",
  sklad_doobjednavky: "Sestava k objednání", rezne_plany: "Řezné plány",
  eshop_nastaveni: "Obecné nastavení e-shopu", rozklad_fbx: "Rozklad FBX na profily",
  kosiky: "Košíky", galerie: "Galerie", emaily_prichozi: "Emaily příchozí", crm: "Poptávky (CRM)",
  nabidky: "Nabídky", sdileny_disk: "Sdílený disk", kniha_jizd: "Kniha jízd",
  prijate_doklady: "Přijaté doklady", bankovni_vypisy: "Bankovní výpisy",
  mini_eshopy: "Mini-eshopy", miniweb: "Mini-shopy", miniweb_schvalovani: "Mini-shopy - schvalování textů", zakreslene_pripominky: "Zakreslené připomínky",
  // bot16, 2026-09-28 (bot3 nalez pri vysetrovani "polozky v rolich a
  // opravnenich vubec nefiguruji") - "reklamace"/"vyroba_sestav" v
  // PERMISSION_SECTIONS (api/app.py) uz nejakou dobu byly, jen se sem
  // nikdy nedostaly - stejny vzor jako nedavny TAB_SECTION bug. Bez
  // popisku se radek pro tyhle 2 sekce vykreslil se syrovym klicem
  // misto ceskeho nazvu (RP_SECTION_LABELS[sec] || sec fallback), ne
  // ze by radek chybel uplne.
  reklamace: "Reklamace", vyroba_sestav: "Výroba sestav",
  // bot5, 2026-09-29 (Robert primo: "okamzite vytvor mechanismus,
  // kterym se dostane kazdy panel adminu do tabulky roli a prav") -
  // jednotlive Dashboard panely, viz PERMISSION_SECTIONS (api/app.py)
  // + DASHBOARD_PANEL_SECTION (admin.html).
  dash_vyroba_sestav: "Dashboard: Tvorba sestav", dash_vandr_vyroba: "Dashboard: Tvorba sestav – Vandr",
  dash_gpu_monitor: "Dashboard: GPU render worker", dash_qa_bugy: "Dashboard: Chyby v kódu",
  dash_qa_ukoly: "Dashboard: Nahlášené úkoly", dash_qa_navrhy: "Dashboard: Návrhy na doplnění",
  dash_qa_system: "Dashboard: QA běhy (systém)", dash_js_chyby: "Dashboard: JS chyby z prohlížečů",
  dash_nasazeni: "Dashboard: Nasazení serveru",
  // bot16, 2026-10-06 (Robert pres bot9: Johnova prace v adminu) - zalozka Prehledy > John, viz PERMISSION_SECTIONS (api/app.py) + TAB_SECTION (admin.html).
  prehledy_john: "Přehledy: Johnova práce",
  // bot16, 2026-10-06 (Robert: schvalene doklady na emaily ucetni podle typu) - zalozka Prodej > E-maily ucetni, viz PERMISSION_SECTIONS (api/app.py) + TAB_SECTION (admin.html).
  ucetni_emaily: "E-maily účetní",
};
const RP_ACTION_LABELS = {
  zobrazit: "Zobrazit", vytvorit: "Vytvořit", upravit: "Upravit", smazat: "Smazat",
  foceni_mobil: "Focení v mobilu",
};
// Robert 2026-08: "kazdemu zatrzitku roli dej pri najeti mysi napovedu
// vysvetlivku" - popisek sekce (co pokryva) + popisek akce (co presne
// zaskrtnuti povoli) se slozi do title atributu checkboxu.
const RP_SECTION_DESC = {
  objednavky: "Přijaté (zákaznické) objednávky e-shopu - stavy, položky, doklady k nim.",
  nakupni_objednavky: "Nákupní objednávky dodavatelům + karty dodavatelů.",
  doklady: "Vystavené doklady - zálohová faktura, VDD, faktura, dodací list.",
  emaily_odchozi: "Historie e-mailů odeslaných zákazníkům z aplikace (potvrzení objednávek, faktury...).",
  zakaznici: "Karty zákazníků e-shopu (kontakty, adresy, historie objednávek).",
  doprava_platba: "Nastavení způsobů dopravy a platby v e-shopu.",
  kategorie: "Strom kategorií e-shopu - struktura, SEO, obrázky.",
  homepage_mozaika: "Dlaždice mozaiky na úvodní stránce + úvodní text.",
  homepage_carousel: "Rotující banner (carousel) na úvodní stránce.",
  centralni_texty: "Centrální panel popisných textů kategorií (obor/typologie).",
  hlasky: "Krátká oznámení/hlášky zobrazovaná zákazníkům na webu.",
  postranni_panel: "Postranní panel s bloky (text/obrázek/video) na vybraných stránkách.",
  ceny_profilu: "Ceny a hmotnosti katalogových hliníkových profilů, živý FIO kurz.",
  dogus_cena: "Porovnání ceny profilů Dogus s cenovým vzorcem.",
  prislusenstvi: "Ceníky a katalog příslušenství (spojky, úhelníky, kolečka...).",
  sklad_karty: "Skladové karty produktů - CRUD, 3D modely, kusovník sestav, GLB výběr do scény.",
  sklad_pohyby: "Skladové pohyby (příjemky/výdejky) a test. příjmy/výdeje.",
  sklad_doobjednavky: "Sestava položek k doobjednání u dodavatelů.",
  rezne_plany: "Řezné plány - rozpis profilů na tyče, optimalizace odpadu.",
  eshop_nastaveni: "Obecné nastavení e-shopu - popisky polí, ceníkové konfigurace, barvy motivu, OG obrázky.",
  rozklad_fbx: "Rozklad nahraného FBX modelu na jednotlivé katalogové profily.",
  uzivatele: "Uživatelské účty administrace (role, přístup, hesla).",
  nastaveni: "Obecné nastavení aplikace (vzhled, obecné parametry).",
  audit_log: "Záznam historie akcí provedených v administraci.",
  kosiky: "Rozpracované košíky zákazníků (ještě nedokončené objednávky).",
  galerie: "Fotogalerie realizací a obrázky připojené k produktům/kategoriím.",
  emaily_prichozi: "Příchozí zprávy od zákazníků (živý chat + e-maily netříděné jinam) a odpovědi na ně.",
  crm: "Poptávky (CRM) - příchozí zájemci a jejich stav vyřízení.",
  nabidky: "Obchodní cenové nabídky (adresáře s přílohami) pro zákazníky/poptávky.",
  sdileny_disk: "Sdílený disk - společné soubory a dokumenty firmy.",
  kniha_jizd: "Kniha jízd - firemní vozidla a přehled jízd (kdo, čím, kolik km).",
  prijate_doklady: "Faktury a doklady přijaté e-mailem, čekající na schválení před uložením do Sdíleného disku.",
  bankovni_vypisy: "Přijaté bankovní platby (kredit) synchronizované z FIO banky.",
  mini_eshopy: "Samostatné veřejné weby (vlastní doména) pro jednotlivé modely aut - řízené centrálně odsud.",
  miniweb: "Mini-shopy sestav stolů: seznam shopů, ceny/kurz/marže/země/kontakt, poptávky a objednávky z mini-shopů (zobrazit = číst, upravit = měnit nastavení).",
  miniweb_schvalovani: "Schvalování textů a právních dokumentů mini-shopů (zobrazit = přehled, upravit = schválit/vrátit do konceptu).",
  zakreslene_pripominky: "Zakreslené připomínky zákazníků k obrázku produktu/sestavy z e-shopu.",
  reklamace: "Reklamace a odstoupení od smlouvy - jejich stav vyřízení a dobropisy.",
  vyroba_sestav: "Přehled postupu výroby sestav (vlastní i Vandr) - kontrola kroků před vystavením.",
  dash_vyroba_sestav: "Panel na Dashboardu - přehledová tabulka výroby vlastních sestav (recept → scéna → schváleno → karta → rendery → web).",
  dash_vandr_vyroba: "Panel na Dashboardu - přehledová tabulka výroby sestav Vandr (FBX export → karta → cena → razítko → rendery → web).",
  dash_gpu_monitor: "Panel na Dashboardu - živá teplota/vytížení GPU render workeru a historie renderovacích úloh.",
  dash_qa_bugy: "Panel na Dashboardu - automatické kontroly kódu/dat, nalezené odchylky napříč aplikací.",
  dash_qa_ukoly: "Panel na Dashboardu - nahlášené úkoly vysoké priority poslané botům k vyřešení.",
  dash_qa_navrhy: "Panel na Dashboardu - automatické návrhy na doplnění chybějících dat.",
  dash_qa_system: "Panel na Dashboardu - denní systémová QA kontrola (health/logy/bezpečnost/SEO).",
  dash_js_chyby: "Panel na Dashboardu - JS chyby zachycené z prohlížečů návštěvníků webu.",
  dash_nasazeni: "Panel na Dashboardu - kdy půjde serverový kód ven, co čeká na nasazení a jak dopadlo poslední plánované nasazení.",
  prehledy_john: "Záložka Přehledy → Johnova práce - živý přehled práce externího bota Johna (úkoly, stavy, odkazy na náhledy, historie, běžící jednotky); jen čtení.",
  ucetni_emaily: "Záložka Prodej → E-maily účetní - tabulka adres účetní podle typu dokladu (kam mají jít schválené doklady). Jen ukládá adresy, nic neodesílá (pravidlo 16: e-maily jen přes frontu se schválením).",
};
const RP_ACTION_DESC = {
  zobrazit: "vidí obsah této sekce (bez možnosti cokoliv měnit).",
  vytvorit: "smí zakládat nové záznamy v této sekci.",
  upravit: "smí upravovat existující záznamy v této sekci.",
  smazat: "smí mazat záznamy v této sekci.",
  foceni_mobil: "smí použít mobilní fotoaparat (capture.html) k pořizování fotek do této sekce.",
};
function rpTooltip(sec, act) {
  const secDesc = RP_SECTION_DESC[sec] || "";
  const actDesc = RP_ACTION_DESC[act] || "";
  return `${RP_SECTION_LABELS[sec] || sec} – ${RP_ACTION_LABELS[act] || act}: ${secDesc} Zaškrtnuto = ${actDesc}`;
}
// Robert 2026-07-26: "pridej managera a odstran zakaznika" - manager je
// nyni realna spravovatelna role v matici, zakaznik (byval klic pro
// bezneho e-shop zakaznika/roli 'user') odstranen - zakaznici do
// administrace nemaji pristup vubec (viz has_permission() v app.py).
const RP_ROLE_LABELS = { manager: "Manažer", skladnik: "Mistr", ucetni: "Asistent", monter: "Montér", sklad: "Skladník" };
let rolePermData = null;
// Robert 2026-08-06 ("budu listovat rolemi, výběru si roli vstoupím a
// teprve potom vidím tabulku... na obrazovce vždy vidím pouze jednu
// roli"): drill-down misto vsech roli pod sebou najednou. Stav
// checkboxu se drzi v pameti (rpPendingState) NEZAVISLE na tom, ktera
// role je zrovna zobrazena - jinak by prepnuti na jinou roli PRED
// ulozenim ztratilo neulozene zmeny (DOM s checkboxy skryte role uz
// neexistuje).
let rpPendingState = {};
let rpSelectedRole = null;

async function loadRolePermissions() {
  try {
    const r = await fetch("/api/admin/role-permissions");
    if (!r.ok) throw new Error("HTTP " + r.status);
    rolePermData = await r.json();
    rpPendingState = {};
    (rolePermData.permissions || []).forEach(p => {
      rpPendingState[p.role + "|" + p.section + "|" + p.action] = !!p.allowed;
    });
    const editableRoles = (rolePermData.roles || []).filter(r => r !== "admin");
    if (!rpSelectedRole || !editableRoles.includes(rpSelectedRole)) {
      rpSelectedRole = editableRoles[0] || null;
    }
    renderRolePermRoleList();
    renderRolePermissions();
  } catch (e) {
    document.getElementById("rolePermErr").textContent = "Chyba načtení: " + e.message;
  }
}

function renderRolePermRoleList() {
  const list = document.getElementById("rolePermRoleList");
  list.innerHTML = "";
  if (!rolePermData) return;
  const editableRoles = (rolePermData.roles || []).filter(r => r !== "admin");
  editableRoles.forEach(role => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "order-tab-btn" + (role === rpSelectedRole ? " active" : "");
    btn.textContent = RP_ROLE_LABELS[role] || role;
    btn.onclick = () => {
      rpSelectedRole = role;
      renderRolePermRoleList();
      renderRolePermissions();
    };
    list.appendChild(btn);
  });
}

function renderRolePermissions() {
  const container = document.getElementById("rolePermTables");
  container.innerHTML = "";
  if (!rolePermData || !rpSelectedRole) return;
  const role = rpSelectedRole;
  const h = document.createElement("h3");
  h.textContent = RP_ROLE_LABELS[role] || role;
  container.appendChild(h);
  const table = document.createElement("table");
  table.className = "rp-table";
  const thead = "<thead><tr><th>Sekce</th>" +
    rolePermData.actions.map(a => `<th>${RP_ACTION_LABELS[a] || a}</th>`).join("") + "</tr></thead>";
  const rows = rolePermData.sections.map(sec => {
    const cells = rolePermData.actions.map(act => {
      const key = role + "|" + sec + "|" + act;
      const checked = rpPendingState[key] ? "checked" : "";
      const tip = rpTooltip(sec, act).replace(/"/g, "&quot;");
      return `<td><input type="checkbox" class="rp-cb" data-role="${role}" data-section="${sec}" data-action="${act}" ${checked} title="${tip}"></td>`;
    }).join("");
    return `<tr><td>${RP_SECTION_LABELS[sec] || sec}</td>${cells}</tr>`;
  }).join("");
  table.innerHTML = thead + "<tbody>" + rows + "</tbody>";
  container.appendChild(table);
  container.querySelectorAll(".rp-cb").forEach(cb => {
    cb.addEventListener("change", () => {
      rpPendingState[cb.dataset.role + "|" + cb.dataset.section + "|" + cb.dataset.action] = cb.checked;
    });
  });
}

async function saveRolePermissions() {
  const permissions = Object.keys(rpPendingState).map(key => {
    const [role, section, action] = key.split("|");
    return { role, section, action, allowed: rpPendingState[key] };
  });
  const btn = document.getElementById("btnSaveRolePermissions");
  btn.disabled = true;
  document.getElementById("rolePermErr").textContent = "";
  try {
    const r = await fetch("/api/admin/role-permissions", {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ permissions }),
    });
    const data = await r.json();
    if (!r.ok) throw new Error(data.error || ("HTTP " + r.status));
    document.getElementById("rolePermSavedMsg").textContent = `Uloženo (${data.updated} záznamů).`;
    setTimeout(() => { document.getElementById("rolePermSavedMsg").textContent = ""; }, 3000);
  } catch (e) {
    document.getElementById("rolePermErr").textContent = "Chyba uložení: " + e.message;
  } finally {
    btn.disabled = false;
  }
}

document.getElementById("btnSaveRolePermissions").onclick = saveRolePermissions;

// Koeficienty cen podle kategorie (Robert 2026-08-09: "koeficient
// přepočtu cen potřebuji ještě kompletně pohromadě jako tabulku,
// Kategorie > koeficient" + "jen pro admina") - jen kategorie s aspoň
// 1 aktivním Dogus produktem (viz /api/admin/category-price-coefficients).
// Ukládání jednotlivých řádků jde přes už existující
// PUT /api/categories/<id> (žádný nový zápisový endpoint).
function pcFmtCzk(n) {
  return n == null ? "" : n.toLocaleString("cs-CZ", { maximumFractionDigits: 2 }) + " Kč";
}

// bot16, 2026-09-26 (nalezeno pri hledani "prazdneho panelu Menu
// kategorii" - Robertova konzole ukazala "Uncaught TypeError: can't
// access property addEventListener, document.getElementById(...) is
// null" prave tady) - DUPLICITNI, ROZBITA implementace "Koeficientu
// konfiguratoru" (Robert 2026-08-19). document.getElementById(
// "btnSaveScenePriceCoef") tady byl VZDY null - skutecna pricina byla
// jinde (admin.html: nedokonceny HTML komentar konci "*/" misto "-->",
// takze parser spolkl cely #scenePriceCoefInput/#btnSaveScenePriceCoef
// blok jako soucast komentare - viz oprava tamtez), ale i po te oprave
// zustava tenhle blok ZDVOJENY a zbytecny. Nasledek pred opravou: cely
// zbytek souboru PO tomhle radku se nikdy neprovedl (vc. `const
// auditLogPagerState` nize), coz pri kazdem F5 shazovalo Audit log a
// vse za nim v bootstrap sekvenci (admin.html ř. 6522+). Stejne pole
// uz ma funkcni obsluhu v ceny.js (loadJointPrice/btnSaveScenePriceCoef
// tam), zavedenou pri oprave "koeficient se neda ulozit" (2026-09-25).
// Cely blok odstranen, zadna funkcni zmena (uz stejne nikdy
// neposkytoval zadnou vizualni hodnotu - byl mrtvy od prvniho dne).
async function loadPriceCoefficients() {
  const tbody = document.getElementById("priceCoefTbody");
  const msgEl = document.getElementById("priceCoefMsg");
  if (!tbody) return;
  try {
    const r = await fetch("/api/admin/category-price-coefficients");
    if (!r.ok) throw new Error("HTTP " + r.status);
    const data = await r.json();
    const cats = data.categories || [];
    tbody.innerHTML = cats.map(c => {
      const rep = c.rep_product;
      const repCell = rep
        ? `${escapeHtmlAdmin(rep.name)}<div class="hint" style="margin:0;">${escapeHtmlAdmin(rep.sku)}</div>`
        : "—";
      const checkBtn = rep && rep.has_logiman_url
        ? `<button type="button" class="pc-check-btn" data-product-id="${rep.id}">Zjistit</button>`
        : (rep ? `<span class="hint" style="margin:0;">bez odkazu na logiman.cz</span>` : "");
      return `
      <tr data-cat-id="${c.id}">
        <td>${escapeHtmlAdmin(c.name)}</td>
        <td>${c.n_dogus}${c.n_dogus !== c.n_products ? ` / ${c.n_products}` : ""}</td>
        <td><input type="number" step="0.001" class="pc-coef-input" style="width:100px;" value="${c.dogus_price_coefficient ?? ""}" placeholder="—"></td>
        <td><button type="button" class="pc-save-btn">Uložit</button></td>
        <td>${repCell}</td>
        <td class="pc-our-price" data-our-price="${rep && rep.our_price_czk != null ? rep.our_price_czk : ""}">${rep ? pcFmtCzk(rep.our_price_czk) : ""}</td>
        <td class="pc-logiman-price">${checkBtn}</td>
        <td class="pc-diff"></td>
        <td></td>
      </tr>
    `;
    }).join("");
    tbody.querySelectorAll(".pc-save-btn").forEach(btn => {
      btn.onclick = () => savePriceCoefficient(btn);
    });
    tbody.querySelectorAll(".pc-check-btn").forEach(btn => {
      btn.onclick = () => checkLogimanPrice(btn);
    });
    msgEl.textContent = "";
  } catch (e) {
    msgEl.textContent = "Chyba načtení: " + e.message;
    msgEl.style.color = "var(--error, #e07070)";
  }
}

async function checkLogimanPrice(btn) {
  const row = btn.closest("tr");
  const productId = btn.dataset.productId;
  const priceCell = row.querySelector(".pc-logiman-price");
  const diffCell = row.querySelector(".pc-diff");
  const ourPriceRaw = row.querySelector(".pc-our-price").dataset.ourPrice;
  const ourPrice = ourPriceRaw ? parseFloat(ourPriceRaw) : null;
  btn.disabled = true;
  btn.textContent = "Zjišťuji…";
  try {
    const r = await fetch("/api/admin/logiman-price-check", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ product_id: productId }),
    });
    const data = await r.json();
    if (!r.ok) throw new Error(data.error || ("HTTP " + r.status));
    priceCell.textContent = pcFmtCzk(data.logiman_price_czk);
    if (ourPrice != null && data.logiman_price_czk) {
      const pct = ((ourPrice - data.logiman_price_czk) / data.logiman_price_czk * 100);
      diffCell.textContent = (pct >= 0 ? "+" : "") + pct.toFixed(1) + " %";
    }
  } catch (e) {
    priceCell.innerHTML = `<span style="color:var(--error, #e07070);" title="${escapeHtmlAdmin(e.message)}">chyba</span>`;
  } finally {
    btn.disabled = false;
    btn.textContent = "Zjistit";
  }
}

document.getElementById("btnPriceCoefCheckAll").onclick = async () => {
  const btns = [...document.querySelectorAll(".pc-check-btn")];
  for (const btn of btns) {
    if (!btn.disabled) await checkLogimanPrice(btn);
    await new Promise(res => setTimeout(res, 350));
  }
};

async function savePriceCoefficient(btn) {
  const row = btn.closest("tr");
  const catId = row.dataset.catId;
  const input = row.querySelector(".pc-coef-input");
  const msgEl = document.getElementById("priceCoefMsg");
  const raw = input.value.trim();
  btn.disabled = true;
  try {
    const r = await fetch(`/api/categories/${catId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ dogus_price_coefficient: raw === "" ? null : raw }),
    });
    const data = await r.json();
    if (!r.ok) throw new Error(data.error || ("HTTP " + r.status));
    msgEl.textContent = "Uloženo.";
    msgEl.style.color = "var(--success, #7ec488)";
  } catch (e) {
    msgEl.textContent = "Chyba uložení: " + e.message;
    msgEl.style.color = "var(--error, #e07070)";
  } finally {
    btn.disabled = false;
  }
}

// Stránkování (task #78/87) - nahrazuje puvodni pevny ?limit=200
const auditLogPagerState = { page: 1, page_size: 50 };

let auditLogEntriesCache = [];
let auditLogSelectedIds = new Set();

async function loadAuditLog() {
  const entityType = document.getElementById("alFilterEntity").value;
  const params = new URLSearchParams({
    page: auditLogPagerState.page, page_size: auditLogPagerState.page_size,
  });
  if (entityType) params.set("entity_type", entityType);
  try {
    const r = await fetch(`/api/admin/audit-log?${params.toString()}`);
    const data = await r.json();
    auditLogEntriesCache = data.entries || [];
    renderAuditLog(auditLogEntriesCache);
    renderPager("auditLogPager", data, auditLogPagerState, loadAuditLog);
  } catch (e) {
    document.getElementById("auditLogErr").textContent = "Nepodařilo se načíst audit log.";
  }
}

function renderAuditLog(entries) {
  const tbody = document.getElementById("auditLogTbody");
  if (!entries.length) {
    tbody.innerHTML = '<tr><td colspan="7" style="color:#666;">Zatím žádné záznamy.</td></tr>';
    updateAuditLogBulkToolbar();
    return;
  }
  const actionLabels = {
    create: "vytvořeno", update: "upraveno", delete: "smazáno", archive: "archivováno",
    unarchive: "obnoveno", bulk_update: "hromadná úprava", bulk_delete: "hromadné smazání",
    export: "export", import: "import", receipt: "příjem", issue: "výdej",
  };
  tbody.innerHTML = entries.map(e => {
    const date = new Date(e.created_at).toLocaleString("cs-CZ");
    const who = e.user_name || e.user_email || "—";
    return `<tr>
      <td><input type="checkbox" class="auditLogChk" data-id="${e.id}" ${auditLogSelectedIds.has(e.id) ? "checked" : ""}></td>
      <td>${date}</td>
      <td>${escapeHtmlAdmin(who)}</td>
      <td>${escapeHtmlAdmin(actionLabels[e.action] || e.action)}</td>
      <td>${escapeHtmlAdmin(e.entity_type)}</td>
      <td>${e.entity_id ?? ""}</td>
      <td>${escapeHtmlAdmin(e.detail || "")}</td>
    </tr>`;
  }).join("");
  tbody.querySelectorAll(".auditLogChk").forEach(chk => {
    chk.onchange = () => {
      const id = parseInt(chk.dataset.id, 10);
      if (chk.checked) auditLogSelectedIds.add(id); else auditLogSelectedIds.delete(id);
      updateAuditLogBulkToolbar();
    };
  });
  updateAuditLogBulkToolbar();
}

function updateAuditLogBulkToolbar() {
  const bar = document.getElementById("auditLogBulkToolbar");
  const count = auditLogSelectedIds.size;
  bar.classList.toggle("active", count > 0);
  document.getElementById("auditLogBulkCount").textContent = `${count} vybráno`;
}
document.getElementById("auditLogSelectAll").onchange = (e) => {
  if (e.target.checked) auditLogEntriesCache.forEach(x => auditLogSelectedIds.add(x.id));
  else auditLogSelectedIds.clear();
  renderAuditLog(auditLogEntriesCache);
};
document.getElementById("auditLogBulkDelete").onclick = async () => {
  if (!auditLogSelectedIds.size) return;
  if (!confirm(`Opravdu trvale smazat ${auditLogSelectedIds.size} vybraných záznamů auditního logu? ` +
               `Jde o záznam odpovědnosti za minulé akce - tuto akci nelze vrátit zpět.`)) return;
  const r = await fetch("/api/admin/audit-log/bulk-delete", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ids: [...auditLogSelectedIds] }),
  });
  const data = await r.json().catch(() => ({}));
  auditLogSelectedIds.clear();
  if (!r.ok) { document.getElementById("auditLogErr").textContent = data.error || "Chyba."; return; }
  loadAuditLog();
};

document.getElementById("alFilterApply").onclick = () => { auditLogPagerState.page = 1; loadAuditLog(); };
document.getElementById("alFilterReset").onclick = () => {
  document.getElementById("alFilterEntity").value = "";
  auditLogPagerState.page = 1;
  loadAuditLog();
};

