// ==================== PREHLEDY > BOTI ====================
// bot16, 2026-09-12 - registr botu se specializaci (viz komentar u
// #tab-boti v admin.html). Vzor prevzaty z uzivatele-role.js
// (renderUsers) - primo editovatelna <table>, kazdy radek ma vlastni
// Ulozit/Smazat, zadny modal (na par poli by byl zbytecny navic).
let botiCache = [];

// Navazani na uzly Pipeline diagramu (bots.pipeline_uzly) se drive
// editovalo primo tady (sloupec + multi-select), Robert po vyzkouseni
// presunul editaci do #tab-pipeline - "stacilo by uplne kdyby to bylo
// v tom pipelinu, tady to byt nemusi" (viz PIPELINE_UZLY + ovladaci
// radek v crm-nabidky.js). Data se odsud tedy neposilaji, jen se pri
// GET vraci spolu se zbytkem radku (nevyuzito tady, vyuzito tam).

// bot9, 2026-09-12 (Robert pres bot3, "kazdy bot se musi divat prave na
// svou zed"): ktere radky maji rozbalenou mini-tabulku "moje ukoly" -
// zije MIMO renderBoti(), aby ji znovuvykresleni (napr. po pridani bota
// nebo oznaceni ukolu hotovym) nezavrelo.
const botiUkolyExpanded = new Set();

// bot3, 2026-09-12 (Robert: "udelej tu tabulku opravdu zivou jako maji
// profici", pak vyslovne "(Server-Sent Events / WebSocket)" - rychly
// polling nestacil, chtel skutecny server->prohlizec push). SSE misto
// pollingu: `/api/admin/bots/events` (api/bots.py) drzi jedno HTTP
// spojeni otevrene a POSILA zmenu, jakmile nastane (server ji sam
// zjistuje kazne 2s, ale klient uz nic nedotazuje - zadny dalsi
// request/response cyklus). Server-side ma vlastni pojistky (max. 15
// min na spojeni, posila jen pri skutecne zmene dat) - viz komentar
// tam. Fallback na starsi polling (3s), kdyz EventSource selze/neni
// podporovany - tabulka nesmi zustat uplne mrtva jen kvuli SSE vypadku.
let botiEventSource = null;
let botiPollFallbackTimer = null;

function botiStartPollFallback() {
  if (botiPollFallbackTimer) return;
  botiPollFallbackTimer = setInterval(() => {
    const tab = document.getElementById("tab-boti");
    if (tab && tab.classList.contains("active") && !document.hidden) loadBoti();
  }, 3000);
}

function botiConnectEvents() {
  if (botiEventSource) return;
  try {
    botiEventSource = new EventSource("/api/admin/bots/events");
  } catch (e) {
    botiStartPollFallback();
    return;
  }
  botiEventSource.onmessage = (ev) => {
    try {
      const data = JSON.parse(ev.data);
      botiCache = data.items || [];
      renderBoti();
    } catch (e) { /* jeden pokazeny snimek nema shodit zbytek */ }
  };
  botiEventSource.addEventListener("timeout", () => {
    // Server sam po 15 min zavrel (pojistka proti zapomenutemu panelu) -
    // znovu se pripoji jen pokud je zalozka porad aktivni a viditelna.
    botiEventSource.close();
    botiEventSource = null;
    const tab = document.getElementById("tab-boti");
    if (tab && tab.classList.contains("active") && !document.hidden) botiConnectEvents();
  });
  botiEventSource.onerror = () => {
    // Prohlizec sam retryuje EventSource spojeni - fallback polling
    // bezi SOUBEZNE jen jako pojistka, dokud se SSE samo neuzdravi.
    botiStartPollFallback();
  };
}

function botiDisconnectEvents() {
  if (botiEventSource) { botiEventSource.close(); botiEventSource = null; }
  if (botiPollFallbackTimer) { clearInterval(botiPollFallbackTimer); botiPollFallbackTimer = null; }
}

// Pripojit/odpojit podle viditelnosti zalozky - presne stejny duvod jako
// u driveho pollingu (nedrzet spojeni/workera, kdyz se na Boti nikdo
// nekouka), jen misto setIntervalu je to EventSource pripojeni/odpojeni.
document.addEventListener("visibilitychange", () => {
  const tab = document.getElementById("tab-boti");
  const aktivni = tab && tab.classList.contains("active") && !document.hidden;
  if (aktivni) botiConnectEvents(); else botiDisconnectEvents();
});

async function loadBoti() {
  // Oba fetche najednou - pocty/mini-seznam u kazdeho radku potrebuji
  // botUkolyCache uz pri prvnim renderBoti(), ne az po dobehnuti
  // samostatneho loadBotUkoly() o beh pozdeji (jinak by se "moje ukoly
  // (0)" na kratko mihlo u vsech radku).
  const [rBots, rUkoly] = await Promise.all([
    fetch("/api/admin/bots"),
    fetch("/api/admin/bot-ukoly"),
  ]);
  const dataBots = await rBots.json().catch(() => ({}));
  const dataUkoly = await rUkoly.json().catch(() => ({}));
  botiCache = dataBots.items || [];
  botUkolyCache = dataUkoly.items || [];
  renderBoti();
  fillUkolBotSelect();
  renderBotUkoly();
  // initDashPanelCollapse (dashboard.js) je idempotentni per-tlacitko
  // (dataset.wired guard) - bezpecne zavolat znovu, jen tak se
  // sbalovaci tlacitko noveho panelu vubec zapoji na téhle záložce
  // (dashboard.js ho jinak vola jen z loadDashboard()).
  if (typeof initDashPanelCollapse === "function") initDashPanelCollapse();
  loadBotTokenHistory();
}

function fmtBotDate(iso) {
  if (!iso) return "";
  try { return new Date(iso).toLocaleString("cs-CZ"); } catch (e) { return ""; }
}

// bot3, 2026-09-12: "před X min/hod" - relativni cas je pro sloupec
// "naposledy se hlasil" citelnejsi nez holy datum (rychle poznat "to je
// v poradku" vs. "tohle uz je podezrele dlouho").
function fmtRelativeAgo(iso) {
  if (!iso) return "nikdy";
  const ms = Date.now() - new Date(iso).getTime();
  if (ms < 0) return fmtBotDate(iso);
  const min = Math.floor(ms / 60000);
  if (min < 1) return "právě teď";
  if (min < 60) return `před ${min} min`;
  const hod = Math.floor(min / 60);
  if (hod < 24) return `před ${hod} h`;
  return `před ${Math.floor(hod / 24)} dny`;
}

const BOT_STAV_LABEL = {
  aktivni: '<span style="color:var(--ok,#3fb87a);">● aktivní</span>',
  neaktivni: '<span style="color:var(--warn,#d9a441);">● neaktivní</span>',
  zmizel: '<span style="color:var(--danger,#d9534f);">● zmizel</span>',
  nikdy: '<span style="color:var(--text-faint);">○ nikdy se nehlásil</span>',
};

// bot16, 2026-09-17 (Robert primo): sloupec "Model / Effort" -
// skutecne aktualni model hlavni smycky bota (ne subagenti), z
// api/bots.py current_model/current_effort (viz komentar tam). Kratke
// prezdivky pro citelnost - NEZNAMY model se NESCHOVA, zobrazi se
// syrovy retezec tak, jak prisel (fallback), at novy model po vydani
// nezpusobi "—" misto uzitecne informace.
const BOT_MODEL_FRIENDLY = {
  "claude-opus-5[1m]": "Opus 5 (1M)",
  "claude-opus-5": "Opus 5",
  "claude-sonnet-5": "Sonnet 5",
  "claude-haiku-4-5-20251001": "Haiku 4.5",
  "claude-fable-5-1": "Fable 5.1",
};
function fmtModelEffort(b) {
  if (!b.current_model) return '<span style="color:var(--text-faint);">—</span>';
  const nazev = BOT_MODEL_FRIENDLY[b.current_model] || b.current_model;
  const effort = b.current_effort ? ` <span style="color:var(--text-faint);font-size:11px;">(${hpEscapeHtml(b.current_effort)})</span>` : "";
  return `<span title="${hpEscapeHtml(b.current_model)} · aktualizováno: ${fmtBotDate(b.current_model_updated_at)}">${hpEscapeHtml(nazev)}${effort}</span>`;
}

// bot16, 2026-09-12 (Robert pres bot3): sloupec "Tokeny" - skutecna
// spotreba, ne odhad. Zdroj: bot_token_usage (viz api/bots.py LEFT JOIN,
// scripts/2026-09-12_bot_token_usage_sync.py). Az do cutoveru
// 2026-09-16 22:00 (/opt/bot-telemetry/RUNBOOK_CUTOVER.md) budou tyhle
// hodnoty u vsech botu "—" - zadna bot session jeste neposila OTel
// metriky, to je OCEKAVANY stav, ne chyba.
function fmtTokeny(b) {
  if (b.tokens_total == null) return '<span style="color:var(--text-faint);">—</span>';
  const tokeny = Number(b.tokens_total).toLocaleString("cs-CZ");
  const cena = b.cost_usd_total != null ? ` (~$${Number(b.cost_usd_total).toFixed(2)})` : "";
  return `<span title="naposledy sesynchronizováno: ${fmtBotDate(b.tokens_last_synced_at)}">${tokeny}${cena}</span>`;
}

// Kompaktni mini-seznam UKOLU JEDNOHO bota (filtr bot_id) - stejna data
// jako spolecny seznam "Úkoly na zeď" dole, jen uzsi pohled. Zadne
// tlacitko mazani, stejny duvod jako u toho spolecneho (viz api/bots.py).
function renderMiniUkoly(botId) {
  const moje = botUkolyCache.filter(u => u.bot_id === botId);
  if (!moje.length) return '<p class="hint" style="margin:6px 0;">Žádné úkoly.</p>';
  return moje.map(u => `
    <div style="display:flex;align-items:center;gap:8px;padding:3px 0;${u.hotovo ? "opacity:.55;" : ""}">
      <input type="checkbox" class="mu-hotovo" data-id="${u.id}" ${u.hotovo ? "checked" : ""}>
      <span style="flex:1;">${hpEscapeHtml(u.text)}</span>
      <span style="color:var(--text-faint);font-size:11px;">${fmtBotDate(u.created_at)}</span>
    </div>
  `).join("");
}

function wireMiniUkolyCheckboxes(container) {
  container.querySelectorAll(".mu-hotovo").forEach(chk => {
    chk.onchange = async () => {
      const id = parseInt(chk.dataset.id, 10);
      const r = await fetch(`/api/admin/bot-ukoly/${id}`, {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ hotovo: chk.checked }),
      });
      const data = await r.json().catch(() => ({}));
      if (!r.ok) { alert(data.error || "Chyba."); chk.checked = !chk.checked; return; }
      const u = botUkolyCache.find(x => x.id === id);
      if (u) u.hotovo = chk.checked;
      // Plny prekresleni obou pohledu - stav rozbaleni prezije diky
      // botiUkolyExpanded (viz komentar u ni).
      renderBotUkoly();
      renderBoti();
    };
  });
}

function renderBoti() {
  const tbody = document.getElementById("botiTbody");
  tbody.innerHTML = "";
  botiCache.forEach(b => {
    const pocet = botUkolyCache.filter(u => u.bot_id === b.bot_id).length;
    const rozbaleno = botiUkolyExpanded.has(b.bot_id);
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td><input type="text" class="b-botid" value="${hpEscapeHtml(b.bot_id)}" style="width:120px;"></td>
      <td><textarea class="b-spec" rows="2" style="width:100%;min-width:260px;font-family:inherit;">${hpEscapeHtml(b.specializace)}</textarea></td>
      <td>
        <button class="b-ukoly-toggle" type="button" style="background:none;border:1px solid var(--border-soft2);border-radius:4px;font-size:11px;padding:2px 6px;">${rozbaleno ? "▾" : "▸"} moje úkoly (${pocet})</button>
      </td>
      <td>${BOT_STAV_LABEL[b.stav] || b.stav}</td>
      <td style="max-width:260px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="${hpEscapeHtml(b.aktualni_cinnost || "")}">${hpEscapeHtml(b.aktualni_cinnost || "")}</td>
      <td style="max-width:220px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-family:monospace;font-size:11px;" title="${hpEscapeHtml(b.aktualni_soubor || "")}">${hpEscapeHtml(b.aktualni_soubor || "")}</td>
      <td title="${fmtBotDate(b.last_checkin_at)}">${fmtRelativeAgo(b.last_checkin_at)}</td>
      <td>${fmtBotDate(b.updated_at)}</td>
      <td>${fmtModelEffort(b)}</td>
      <td>${fmtTokeny(b)}</td>
      <td>
        <button class="b-save">Uložit</button> <button class="b-delete danger">Smazat</button>
      </td>
    `;
    const detailTr = document.createElement("tr");
    detailTr.className = "b-ukoly-detail";
    detailTr.style.display = rozbaleno ? "" : "none";
    detailTr.innerHTML = `<td colspan="11" style="background:var(--panel-bg-alt);padding:6px 10px;">${renderMiniUkoly(b.bot_id)}</td>`;
    wireMiniUkolyCheckboxes(detailTr);
    tr.querySelector(".b-ukoly-toggle").onclick = () => {
      const budeRozbaleno = detailTr.style.display === "none";
      detailTr.style.display = budeRozbaleno ? "" : "none";
      tr.querySelector(".b-ukoly-toggle").textContent = `${budeRozbaleno ? "▾" : "▸"} moje úkoly (${pocet})`;
      if (budeRozbaleno) botiUkolyExpanded.add(b.bot_id); else botiUkolyExpanded.delete(b.bot_id);
    };
    tr.querySelector(".b-save").onclick = async () => {
      const body = {
        bot_id: tr.querySelector(".b-botid").value.trim(),
        specializace: tr.querySelector(".b-spec").value.trim(),
      };
      const r = await fetch(`/api/admin/bots/${b.id}`, {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await r.json().catch(() => ({}));
      if (!r.ok) { alert(data.error || "Chyba."); return; }
      // Bez plneho loadBoti() - to by zahodilo rozepsane zmeny v jinych
      // radcich (stejny duvod jako u renderUsers). Vyjimka: zmena bot_id
      // by mela projevit i v selectu "Úkoly na zeď" nize, tak ho znovu
      // naplnime z aktualizovane cache.
      b.bot_id = body.bot_id;
      b.specializace = body.specializace;
      fillUkolBotSelect();
    };
    tr.querySelector(".b-delete").onclick = async () => {
      if (!confirm(`Smazat bota "${b.bot_id}" z registru?`)) return;
      // Robert primo (pres bot3, 2026-09-14, po omylem smazanem bot5
      // pres obycejny confirm()) - druha, prisnejsi pojistka: opsani
      // vety "smazat <bot_id>". potvrdSmazaniOpisemVety() je globalni
      // funkce z crm-nabidky.js - oba soubory se nacitaji na stejne
      // strance admin.html (viz poradi <script> tagu), zadny
      // duplicitni kod tu proto neni potreba.
      if (!potvrdSmazaniOpisemVety(b.bot_id)) { alert("Smazání zrušeno - věta nesouhlasila."); return; }
      const r = await fetch(`/api/admin/bots/${b.id}`, { method: "DELETE" });
      const data = await r.json().catch(() => ({}));
      if (!r.ok) { alert(data.error || "Chyba."); return; }
      botiCache = botiCache.filter(x => x.id !== b.id);
      botiUkolyExpanded.delete(b.bot_id);
      tr.remove();
      detailTr.remove();
      fillUkolBotSelect();
    };
    tbody.appendChild(tr);
    tbody.appendChild(detailTr);
  });
}

// ==================== SPOTREBA TOKENU V CASE (linovy graf) ====================
// bot16, 2026-09-17 (Robert pres bot3): zdroj dat GET /api/admin/bots/
// token-history?range=... (jemnozrnna historie kumulativni hodnoty,
// viz api/bots.py RANGE_CONFIG a bot_token_usage_history). Vlastni
// canvas 2D kod po vzoru gpuMonDrawChart() v gpu-monitor.js - v repu
// neni Chart.js/D3. PUVODNI verze mela jen 1 bod/den/bota (plocha
// cara) - po zive zpetne vazbe prepracovano na meritka 5min az 1
// mesic s epoch-based skalovanim casu (misto rovnomerneho rozlozeni
// podle indexu/dne).
//
// Barvy: kazdemu bot_id patri PEVNY slot v kategoricke palete (dataviz
// skill, overena sada 8 odstinu bezpecnych pro barvoslepost - viz
// references/palette.md) podle ABECEDNIHO poradi bot_id, NIKDY podle
// velikosti hodnoty nebo poradi v odpovedi - barva se tak nikdy
// nepreskupi jen proto, ze se zmenilo poradi (anti-pattern
// "recolor-on-filter"). Vic nez 8 botu: prebytek jde do sedeho
// "Ostatní" a nahlasi se konzolove varovani - zadne tiche oriznuti.
const BTH_PALETTE_LIGHT = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"];
const BTH_PALETTE_DARK = ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9", "#e66767"];
const BTH_OTHER_COLOR = "#8b93a1";
// Rozsahy presne podle Robertova zadani (5min .. 1 mesic) - hodnoty
// klicu musi sedet s RANGE_CONFIG v api/bots.py.
const BTH_RANGES = [
  { key: "5m", label: "5 min" },
  { key: "15m", label: "15 min" },
  { key: "1h", label: "1 h" },
  { key: "5h", label: "5 h" },
  { key: "1d", label: "1 den" },
  { key: "1w", label: "1 týden" },
  { key: "1m", label: "1 měsíc" },
];
const BTH_RANGE_DEFAULT = "1d";
// Kratke rozsahy = syrova ~2min data -> na ose stac popisek casu (HH:MM).
// Delsi (1d+) muzou prekrocit den, ale i tak je cas uvnitr dne
// nejcitelnejsi popisek pro 1d; od tydne vyse uz je dulezitejsi datum.
const BTH_RANGES_S_DATEM = new Set(["1w", "1m"]);

let botiTokenHistoryCache = { items: [] };
let botiTokenHistoryMetric = "tokens_total";
let botiTokenHistoryRange = BTH_RANGE_DEFAULT;
let botiTokenHistoryTableShown = false;

function bthIsDarkTheme() {
  return document.documentElement.getAttribute("data-theme") !== "light";
}

function bthSurfaceColor() {
  const v = getComputedStyle(document.documentElement).getPropertyValue("--panel-bg").trim();
  return v || (bthIsDarkTheme() ? "#22262e" : "#ffffff");
}

function bthColorForBot(botId, sortedIds) {
  const idx = sortedIds.indexOf(botId);
  const paleta = bthIsDarkTheme() ? BTH_PALETTE_DARK : BTH_PALETTE_LIGHT;
  if (idx < 0 || idx >= paleta.length) return BTH_OTHER_COLOR;
  return paleta[idx];
}

function bthFmtCompact(n) {
  if (n == null) return "?";
  const abs = Math.abs(n);
  if (abs >= 1e6) return (n / 1e6).toFixed(1).replace(/\.0$/, "") + "M";
  if (abs >= 1e3) return (n / 1e3).toFixed(1).replace(/\.0$/, "") + "K";
  return String(Math.round(n));
}

function bthFmtValue(n, metric) {
  if (n == null) return "—";
  return metric === "cost_usd_total" ? ("$" + Number(n).toFixed(2)) : Number(n).toLocaleString("cs-CZ");
}

// Kratky popisek pro osu X - jen cas, nebo jen datum u tydne/mesice
// (viz BTH_RANGES_S_DATEM vyse).
function bthFmtTick(epochMs) {
  const d = new Date(epochMs);
  if (BTH_RANGES_S_DATEM.has(botiTokenHistoryRange)) {
    return String(d.getDate()).padStart(2, "0") + "." + String(d.getMonth() + 1).padStart(2, "0") + ".";
  }
  return String(d.getHours()).padStart(2, "0") + ":" + String(d.getMinutes()).padStart(2, "0");
}

// Plny popisek (tooltip/tabulka) - VZDY datum i cas, at je jednoznacny
// bez ohledu na zvoleny rozsah.
function bthFmtHeader(epochMs) {
  const d = new Date(epochMs);
  const datum = String(d.getDate()).padStart(2, "0") + "." + String(d.getMonth() + 1).padStart(2, "0") + ".";
  const cas = String(d.getHours()).padStart(2, "0") + ":" + String(d.getMinutes()).padStart(2, "0");
  return datum + " " + cas;
}

function bthGroupByBota(items) {
  const map = {};
  (items || []).forEach(it => { (map[it.bot_id] || (map[it.bot_id] = [])).push(it); });
  Object.values(map).forEach(arr => arr.sort((a, b) => (a.ts < b.ts ? -1 : a.ts > b.ts ? 1 : 0)));
  return map;
}

// Fetch-on-open (volano z loadBoti()) + fetch-on-range-change (viz
// tlacitka rozsahu nize) - Robert pres bot3: zadny periodicky polling
// na pozadi neni potreba, staci znovunacteni pri otevreni panelu nebo
// zmene rozsahu.
async function loadBotTokenHistory() {
  const errEl = document.getElementById("botiTokenHistoryErr");
  try {
    const r = await fetch("/api/admin/bots/token-history?range=" + encodeURIComponent(botiTokenHistoryRange));
    if (!r.ok) { if (errEl) errEl.textContent = "Nepodařilo se načíst historii tokenů."; return; }
    botiTokenHistoryCache = await r.json();
    if (errEl) errEl.textContent = "";
  } catch (e) {
    // Predchozi vykresleni se NEMAZE - "refetch keeps the frame", ne
    // blesknuti prazdnym stavem kvuli jednomu vypadku spojeni.
    if (errEl) errEl.textContent = "Nepodařilo se načíst historii tokenů (spojení).";
    return;
  }
  renderBotTokenHistory();
}

function renderBotTokenHistory() {
  const canvas = document.getElementById("botiTokenHistoryChart");
  if (!canvas) return;
  const rectW = canvas.getBoundingClientRect().width;
  if (rectW > 0 && Math.abs(canvas.width - rectW) > 4) canvas.width = Math.round(rectW);
  const bySeries = bthGroupByBota(botiTokenHistoryCache.items);
  const sortedIds = Object.keys(bySeries).sort();
  bthDrawChart(canvas, bySeries, sortedIds, botiTokenHistoryMetric);
  bthWireTooltip(canvas);
  bthRenderLegend(sortedIds);
  if (botiTokenHistoryTableShown) bthRenderTable(bySeries, sortedIds);
  if (sortedIds.length > 8) {
    console.warn(`Prehledy > Boti: token-history má ${sortedIds.length} botů, jen prvních 8 (abecedně) má vlastní barvu, zbytek je šedé "Ostatní" - kategorická paleta má 8 rozlišitelných odstínů.`);
  }
}

function bthDrawChart(canvas, bySeries, sortedIds, metric) {
  const ctx = canvas.getContext("2d");
  const w = canvas.width, h = canvas.height;
  ctx.clearRect(0, 0, w, h);
  let tMin = Infinity, tMax = -Infinity;
  sortedIds.forEach(id => bySeries[id].forEach(p => {
    const t = new Date(p.ts).getTime();
    if (t < tMin) tMin = t;
    if (t > tMax) tMax = t;
  }));
  if (!isFinite(tMin)) {
    ctx.fillStyle = "#9aa4b2";
    ctx.font = "12px sans-serif";
    ctx.fillText("Pro tenhle rozsah zatím nejsou data.", 10, h / 2);
    canvas._bthMeta = null;
    return;
  }
  const pad = { l: 54, r: 14, t: 12, b: 24 };
  const plotW = w - pad.l - pad.r;
  const plotH = h - pad.t - pad.b;
  const vals = [];
  sortedIds.forEach(id => bySeries[id].forEach(p => { if (p[metric] != null) vals.push(p[metric]); }));
  const maxV = Math.max(1, ...vals) * 1.1;
  // Epoch-based skalovani (vzor gpuMonDrawChart) - x-pozice je URMENA
  // SKUTECNYM casem, ne poradim/indexem bodu, takze nerovnomerne
  // rozestupy (bot dlouho necinny) vypadaji spravne jako mezera.
  const xOf = (t) => tMax > tMin ? pad.l + ((t - tMin) / (tMax - tMin)) * plotW : pad.l + plotW / 2;
  const yOf = (v) => pad.t + (1 - v / maxV) * plotH;

  // osy - hairline, recessive, plna cara (dashed = spatny vzor, viz dataviz)
  ctx.strokeStyle = "rgba(154,164,178,.35)";
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(pad.l, pad.t);
  ctx.lineTo(pad.l, pad.t + plotH);
  ctx.lineTo(pad.l + plotW, pad.t + plotH);
  ctx.stroke();

  // Y ticky - 4 kroky, kompaktni format (1.2K/3.4M)
  ctx.fillStyle = "#9aa4b2";
  ctx.font = "10px sans-serif";
  for (let k = 0; k <= 4; k++) {
    const v = (maxV / 4) * k;
    ctx.fillText(bthFmtCompact(v), 2, yOf(v) + 3);
  }

  // X ticky - az 5 rovnomerne rozlozenych v CASE (ne v poctu bodu)
  const pocetXTiku = tMax > tMin ? 5 : 1;
  for (let k = 0; k < pocetXTiku; k++) {
    const t = tMin + (pocetXTiku > 1 ? k / (pocetXTiku - 1) : 0) * (tMax - tMin);
    const label = bthFmtTick(t);
    const x = xOf(t);
    const sirka = ctx.measureText(label).width;
    const zarovnani = k === 0 ? 0 : (k === pocetXTiku - 1 ? -sirka : -sirka / 2);
    ctx.fillText(label, Math.max(pad.l, Math.min(pad.l + plotW - sirka, x + zarovnani)), h - 6);
  }

  const surfaceColor = bthSurfaceColor();
  sortedIds.forEach(id => {
    const barva = bthColorForBot(id, sortedIds);
    const body = bySeries[id].filter(p => p[metric] != null);
    if (!body.length) return;
    if (body.length >= 2) {
      ctx.strokeStyle = barva;
      ctx.lineWidth = 2;
      ctx.beginPath();
      body.forEach((p, i) => {
        const x = xOf(new Date(p.ts).getTime()), y = yOf(p[metric]);
        if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
      });
      ctx.stroke();
    }
    // koncovy marker (r=4, tedy 8px prumer dle mark-spec) + 2px "surface
    // ring" v barve pozadi, at je citelny i v miste krizeni krivek.
    const posl = body[body.length - 1];
    const x = xOf(new Date(posl.ts).getTime()), y = yOf(posl[metric]);
    ctx.fillStyle = surfaceColor;
    ctx.beginPath(); ctx.arc(x, y, 6, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = barva;
    ctx.beginPath(); ctx.arc(x, y, 4, 0, Math.PI * 2); ctx.fill();
  });

  // Ulozeno pro tooltip/crosshair (bthWireTooltip nize) - kresli se
  // znovu pri kazdem renderu.
  canvas._bthMeta = { tMin, tMax, pad, plotW };
}

function bthWireTooltip(canvas) {
  if (canvas.dataset.bthWired) return;
  canvas.dataset.bthWired = "1";
  const tip = document.createElement("div");
  tip.id = "botiTokenHistoryTooltip";
  tip.style.cssText = "position:fixed;pointer-events:none;background:var(--panel-bg);border:1px solid var(--border-soft2);border-radius:6px;padding:6px 8px;font-size:11.5px;box-shadow:0 2px 8px rgba(0,0,0,.3);display:none;z-index:60;max-width:260px;";
  document.body.appendChild(tip);
  // Crosshair najde cilovy CAS pod kurzorem (inverze xOf), pro kazdou
  // serii pak jeji NEJBLIZSI bod k tomu casu - funguje i kdyz casy
  // jednotlivych botu nejsou uplne shodne (napr. bot pridan pozdeji).
  canvas.addEventListener("mousemove", (ev) => {
    const meta = canvas._bthMeta;
    if (!meta) { tip.style.display = "none"; return; }
    const rect = canvas.getBoundingClientRect();
    const mx = (ev.clientX - rect.left) * (canvas.width / rect.width);
    const podil = meta.plotW > 0 ? Math.max(0, Math.min(1, (mx - meta.pad.l) / meta.plotW)) : 0;
    const cilovyCas = meta.tMin + podil * (meta.tMax - meta.tMin);
    const bySeries = bthGroupByBota(botiTokenHistoryCache.items);
    const sortedIds = Object.keys(bySeries).sort();
    // Jeden tooltip, VSECHNY serie najednou (viz dataviz "one tooltip,
    // every series") - kazda k SVEMU nejblizsimu bodu, ne k jednomu
    // sdilenemu casu, ktery by u asynchronnich sync tiku neseděl presne.
    const radky = sortedIds.map(id => {
      const body = bySeries[id];
      if (!body.length) return null;
      let nejblizsi = body[0], nejmensiRozdil = Infinity;
      body.forEach(p => {
        const t = new Date(p.ts).getTime();
        const d = Math.abs(t - cilovyCas);
        if (d < nejmensiRozdil) { nejmensiRozdil = d; nejblizsi = p; }
      });
      if (nejblizsi[botiTokenHistoryMetric] == null) return null;
      const barva = bthColorForBot(id, sortedIds);
      return `<div style="display:flex;align-items:center;gap:6px;padding:1px 0;">
        <span style="width:9px;height:2px;background:${barva};display:inline-block;"></span>
        <span style="color:var(--text-muted);">${hpEscapeHtml(id)}</span>
        <strong style="margin-left:auto;">${bthFmtValue(nejblizsi[botiTokenHistoryMetric], botiTokenHistoryMetric)}</strong>
      </div>`;
    }).filter(Boolean).join("");
    if (!radky) { tip.style.display = "none"; return; }
    tip.innerHTML = `<div style="font-weight:600;margin-bottom:3px;">${hpEscapeHtml(bthFmtHeader(cilovyCas))}</div>${radky}`;
    tip.style.left = (ev.clientX + 14) + "px";
    tip.style.top = (ev.clientY + 14) + "px";
    tip.style.display = "block";
  });
  canvas.addEventListener("mouseleave", () => { tip.style.display = "none"; });
}

function bthRenderLegend(sortedIds) {
  const el = document.getElementById("botiTokenHistoryLegend");
  if (!el) return;
  if (!sortedIds.length) { el.innerHTML = ""; return; }
  const zobrazene = sortedIds.slice(0, 8);
  const ostatni = sortedIds.slice(8);
  let html = zobrazene.map(id => {
    const barva = bthColorForBot(id, sortedIds);
    return `<span style="display:inline-flex;align-items:center;gap:5px;"><span style="width:10px;height:10px;border-radius:50%;background:${barva};display:inline-block;"></span>${hpEscapeHtml(id)}</span>`;
  }).join("");
  if (ostatni.length) {
    html += `<span style="display:inline-flex;align-items:center;gap:5px;color:var(--text-faint);"><span style="width:10px;height:10px;border-radius:50%;background:${BTH_OTHER_COLOR};display:inline-block;"></span>Ostatní (${ostatni.map(hpEscapeHtml).join(", ")})</span>`;
  }
  el.innerHTML = html;
}

// Tabulkovy pohled - dvojce ke grafu, ne nahrada (viz dataviz "table
// view twin"): kazda hodnota musi byt citelna i bez najeti mysi.
// Casy jsou napric boty SDILENE (jeden sync beh razitkuje vsechny
// najednou, viz snapshot_historie() v sync skriptu) - presna shoda
// retezce `ts` proto funguje spolehlive, na rozdil od "nejblizsi bod"
// pouziteho v tooltipu pro libovolnou pozici mysi.
function bthRenderTable(bySeries, sortedIds) {
  const wrap = document.getElementById("botiTokenHistoryTableWrap");
  if (!wrap) return;
  const vsechnyCasy = new Set();
  sortedIds.forEach(id => bySeries[id].forEach(p => vsechnyCasy.add(p.ts)));
  const casy = Array.from(vsechnyCasy).sort().reverse();
  if (!casy.length) { wrap.innerHTML = '<p class="hint">Pro tenhle rozsah zatím nejsou data.</p>'; return; }
  const hlavicka = sortedIds.map(id => `<th>${hpEscapeHtml(id)}</th>`).join("");
  const radky = casy.map(ts => {
    const bunky = sortedIds.map(id => {
      const p = bySeries[id].find(x => x.ts === ts);
      return `<td>${bthFmtValue(p ? p[botiTokenHistoryMetric] : null, botiTokenHistoryMetric)}</td>`;
    }).join("");
    return `<tr><td>${hpEscapeHtml(bthFmtHeader(new Date(ts).getTime()))}</td>${bunky}</tr>`;
  }).join("");
  wrap.innerHTML = `<table><thead><tr><th>Čas</th>${hlavicka}</tr></thead><tbody>${radky}</tbody></table>`;
}

document.querySelectorAll(".bth-range-btn").forEach(btn => {
  btn.onclick = () => {
    botiTokenHistoryRange = btn.dataset.range;
    document.querySelectorAll(".bth-range-btn").forEach(b => b.classList.toggle("active", b === btn));
    loadBotTokenHistory(); // fetch-on-range-change (Robert pres bot3: zadny polling neni potreba)
  };
});
document.getElementById("bthMetricTokens").onclick = () => {
  botiTokenHistoryMetric = "tokens_total";
  document.getElementById("bthMetricTokens").classList.add("active");
  document.getElementById("bthMetricCost").classList.remove("active");
  renderBotTokenHistory();
};
document.getElementById("bthMetricCost").onclick = () => {
  botiTokenHistoryMetric = "cost_usd_total";
  document.getElementById("bthMetricCost").classList.add("active");
  document.getElementById("bthMetricTokens").classList.remove("active");
  renderBotTokenHistory();
};
document.getElementById("bthTableToggle").onclick = () => {
  botiTokenHistoryTableShown = !botiTokenHistoryTableShown;
  document.getElementById("botiTokenHistoryTableWrap").style.display = botiTokenHistoryTableShown ? "" : "none";
  document.getElementById("bthTableToggle").textContent = botiTokenHistoryTableShown ? "Skrýt tabulku" : "Zobrazit jako tabulku";
  if (botiTokenHistoryTableShown) renderBotTokenHistory();
};

document.getElementById("btnAddBot").onclick = async () => {
  const bot_id = document.getElementById("newBotId").value.trim();
  const specializace = document.getElementById("newBotSpecializace").value.trim();
  const errEl = document.getElementById("botErr");
  errEl.textContent = "";
  if (!bot_id) { errEl.textContent = "Vyplň bot id."; return; }
  const r = await fetch("/api/admin/bots", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ bot_id, specializace }),
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) { errEl.textContent = data.error || "Chyba."; return; }
  document.getElementById("newBotId").value = "";
  document.getElementById("newBotSpecializace").value = "";
  loadBoti();
};

// -------------------- UKOLY NA ZED --------------------
// Robert (chat): "tabulka botů musí obsahovat mnou zadané ukoly a
// pravidla které v chatu oznacim jako: ukol na zed, s kompletní historí,
// a priradi se jen k tomu spravnemu botovi". Zadne tlacitko mazani -
// jen priznak "hotovo" (viz komentar v api/bots.py).
let botUkolyCache = [];

function fillUkolBotSelect() {
  const sel = document.getElementById("newUkolBotId");
  const puvodni = sel.value;
  sel.innerHTML = botiCache.map(b => `<option value="${hpEscapeHtml(b.bot_id)}">${hpEscapeHtml(b.bot_id)}</option>`).join("");
  if (botiCache.some(b => b.bot_id === puvodni)) sel.value = puvodni;
}

async function loadBotUkoly() {
  const r = await fetch("/api/admin/bot-ukoly");
  const data = await r.json().catch(() => ({}));
  botUkolyCache = data.items || [];
  renderBotUkoly();
  renderBoti();
}

function renderBotUkoly() {
  const tbody = document.getElementById("ukolyTbody");
  if (!botUkolyCache.length) {
    tbody.innerHTML = '<tr><td colspan="4" class="hint">Zatím žádné úkoly/pravidla na zdi.</td></tr>';
    return;
  }
  tbody.innerHTML = botUkolyCache.map(u => `
    <tr${u.hotovo ? ' style="opacity:.55;"' : ""}>
      <td><strong>${hpEscapeHtml(u.bot_id)}</strong></td>
      <td>${hpEscapeHtml(u.text)}</td>
      <td>${fmtBotDate(u.created_at)}</td>
      <td><input type="checkbox" class="u-hotovo" data-id="${u.id}" ${u.hotovo ? "checked" : ""}></td>
    </tr>
  `).join("");
  tbody.querySelectorAll(".u-hotovo").forEach(chk => {
    chk.onchange = async () => {
      const id = parseInt(chk.dataset.id, 10);
      const r = await fetch(`/api/admin/bot-ukoly/${id}`, {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ hotovo: chk.checked }),
      });
      const data = await r.json().catch(() => ({}));
      if (!r.ok) { alert(data.error || "Chyba."); chk.checked = !chk.checked; return; }
      const u = botUkolyCache.find(x => x.id === id);
      if (u) u.hotovo = chk.checked;
      chk.closest("tr").style.opacity = chk.checked ? ".55" : "";
      renderBoti(); // promitnout i do pripadne rozbalene mini-tabulky
    };
  });
}

document.getElementById("btnAddUkol").onclick = async () => {
  const bot_id = document.getElementById("newUkolBotId").value;
  const text = document.getElementById("newUkolText").value.trim();
  const errEl = document.getElementById("ukolErr");
  errEl.textContent = "";
  if (!bot_id) { errEl.textContent = "Nejdřív musí existovat aspoň jeden bot v tabulce výše."; return; }
  if (!text) { errEl.textContent = "Vyplň text úkolu/pravidla."; return; }
  const r = await fetch("/api/admin/bot-ukoly", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ bot_id, text }),
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) { errEl.textContent = data.error || "Chyba."; return; }
  document.getElementById("newUkolText").value = "";
  loadBotUkoly();
};
