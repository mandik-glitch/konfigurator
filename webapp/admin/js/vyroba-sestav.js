// "Přehled postupu v adminu" - panel Tvorba sestav na Dashboardu (bot10,
// zadání bot3 koordinace 2026-09-11, viz PLAN_TVORBY_SESTAV.md).
//
// Řádek = KARTA (vozidlo × typologie), rozbalitelná na sestavy. Fázové
// sloupce (scéna/schváleno/karta/rendery/web) + "profil vyplněný" + R se
// NEUKLÁDAJÍ - server je dopočítává live (api/production_overview.py) -
// tenhle soubor je jen vykresluje a nabízí zaškrtnutí RUČNÍCH kroků
// (production_step_defs), které DB sama poznat neumí.
//
// Dvoustavové zaškrtnutí ("hlášeno" / "ověřeno JEDINĚ bot4") je tady JEN
// KE ČTENÍ - bez výjimky (bot3 2026-09-11, po incidentu: Robert v adminu
// omylem odkliknul krok navržený jako klikatelný pro staff). Zápis obou
// stavů jde výhradně přes API se servisním tokenem (viz
// api/production_overview.py) - tahle stránka nemá jediné tlačítko na
// zaškrtnutí kroku, jen na uložení "blokace" (jediný zápis, který
// obrazovka dělá).

let vyrobaSestavData = null;
const vyrobaSestavExpanded = new Set();
// Filtr podle serie (Robert 2026-09-12, pres bot3: paralelni serie regalu
// se stejnym receptem, jinou kolizni rezervou - "10-30mm od kolize" vedle
// dosavadnich "2-20mm") - "" = vse, jinak "<prepazka>|<podbeh>".
//
// bot16, 2026-09-13 (Robert primo v chatu, u screenshotu prehledu s "2-20mm
// od kolize" stitky: "nechci stare serie v prehledu") - PREPISUJE puvodni
// vychozi "vse" (bot3 2026-09-12: "nikdy ne prazdny/nerozliseny pohled jako
// dnes"). 2/20mm byla PUVODNI kolizni rezerva (zpetne dopoctena bot8
// 2026-09-12), 2026-09-13 nahrazena sirokym prepoctem na 10/30mm napric
// 266 z 293 sestav - zbylych 27 jsou vysloven leftover/orphany, uz
// nahrazene novejsimi radky se stejnym receptem (napr. "Doblo K-075 A"
// #134 -> #369, viz AGENTS_LOG.md 2026-09-13). Vychozi pohled proto
// schova KONKRETNE tuhle znamou starou rezervu (karty/sestavy, ktere na
// ni ZUSTAVAJI, napr. T6 K-282, tim z vychoziho pohledu take zmizi - to
// je zamerne, migrace na 10/30 jeste neprobehla, ukazovat je jako
// "hotovo" by bylo zavadejici). "Vse (obe serie)" zustava v selectu pro
// pripadny uklid/audit stareho stavu. Kdyz vznikne TRETI, legitimni
// paralelni serie (ne uklizeci pozustatek), tenhle pevny klic uz nebude
// davat smysl - prehodnotit (napr. "vychozi = nejpocetnejsi serie").
const VYROBA_SESTAV_STARA_SERIE_KEY = "2|20";
const VYROBA_SESTAV_FILTR_AKTUALNI = "aktualni"; // sentinel - nikdy nekoliduje s realnym klicem "<mm>|<mm>" (obsahuje "|") ani s "" (vse)
let vyrobaSestavSerieFilter = VYROBA_SESTAV_FILTR_AKTUALNI;

function vyrobaSestavSerieKey(prepazka, podbeh) {
  return `${prepazka}|${podbeh}`;
}
function vyrobaSestavSerieLabel(prepazka, podbeh) {
  if (prepazka == null || podbeh == null) return null;
  return `${prepazka}-${podbeh}mm od kolize`;
}
function vyrobaSestavSerieProchaziFiltrem(s) {
  const key = vyrobaSestavSerieKey(s.prepazka_rezerva_mm, s.podbeh_rezerva_mm);
  if (vyrobaSestavSerieFilter === VYROBA_SESTAV_FILTR_AKTUALNI) return key !== VYROBA_SESTAV_STARA_SERIE_KEY;
  return key === vyrobaSestavSerieFilter;
}

function escapeHtmlVyroba(s) {
  return String(s == null ? "" : s).replace(/[&<>"']/g, c => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
  ));
}

function vyrobaSestavKartaKey(k) { return (k.car_model_id ?? "null") + "|" + (k.typologie_id ?? "null"); }

function vyrobaSestavRatioCell(ratio) {
  if (!ratio || !ratio.celkem) return "–";
  const cls = ratio.hotovo === ratio.celkem ? "vs-ratio-full" : (ratio.hotovo === 0 ? "vs-ratio-zero" : "vs-ratio-partial");
  return `<span class="${cls}">${ratio.hotovo}/${ratio.celkem}</span>`;
}

// Aktivni render job (bot3 2026-09-11, po Robertove hlaseni "proc
// nerenderujeme, v prehledu je nula" - renderovalo se, 40/81 snimku, ale
// radek v DB se zapise az PO cele davce, takze 0 vypadalo jako necinnost
// celych 80 minut). "running"/"queued" nesmi vypadat jako "error", a
// hlavne "error" nesmi vypadat stejne jako "nic se nedeje".
const VS_RENDER_JOB_LABEL = {
  error: "✖ chyba renderu", running: "▶ renderuje se",
  queued: "⏳ ve frontě", stale: "❓ nejasný stav (dlouho beze změny)", cancelled: "⊘ zrušeno",
};
const VS_RENDER_JOB_CLASS = {
  error: "vs-render-job-error", running: "vs-render-job-running",
  queued: "vs-render-job-queued", stale: "vs-render-job-stale", cancelled: "vs-render-job-queued",
};
function vyrobaSestavRenderJobBadge(job) {
  if (!job) return "";
  const label = VS_RENDER_JOB_LABEL[job.kind] || job.kind;
  const cls = VS_RENDER_JOB_CLASS[job.kind] || "vs-render-job-queued";
  return `<span class="vs-render-job ${cls}">${label}${job.note ? ": " + escapeHtmlVyroba(job.note) : ""}</span>`;
}
function vyrobaSestavRenderyCellKarta(rendery) {
  const base = vyrobaSestavRatioCell(rendery);
  const jobBadge = rendery ? vyrobaSestavRenderJobBadge(rendery.aktivni_job) : "";
  return jobBadge ? `${base}<br>${jobBadge}` : base;
}

function vyrobaSestavBoolCell(v) {
  return v ? '<span class="vs-ratio-full">✓</span>' : '<span class="vs-ratio-zero">–</span>';
}

// Opustene zabrani automatu (bot9, production_work_claims - zabral,
// nedokoncil, ani neuvolnil). Cisty READ, needitovatelne - viditelnost
// podle Robertova pravidla "ležení musí být vidět, ne aby se na něj
// muselo přijít", ne samostatny watchdog proces.
function vyrobaSestavStuckClaimsBadge(stuckClaims) {
  if (!stuckClaims || !stuckClaims.length) return "";
  return stuckClaims.map(c =>
    `<span class="vs-stuck-claim" title="Zabral ${escapeHtmlVyroba(c.held_by)}, lhůta vypršela ${escapeHtmlVyroba(c.expires_at)}, nedokončeno ani neuvolněno.">🛑 uvízlo: ${escapeHtmlVyroba(c.step_key)}</span>`
  ).join(" ");
}

// Vyhrady (production_comments, bot3/Robert 2026-09-11: "dej moznost
// napsat komentar, aniz bych musel schvalit"). Rozdil mezi OTEVRENOU a
// VYRESENOU musi byt videt uz na urovni radku karty, ne az po rozbaleni
// (Robert: "jinak se seznam za tyden zanese a prestane cist") - proto
// samostatny sloupec s POCTEM otevrenych primo v hlavni tabulce; plne
// zneni (vc. vyresenych, s odpovedi kdo/co) az v rozbalenem detailu
// sestavy (vyrobaSestavCommentsCellSestava nize). Cisty READ - zapis
// (POST .../komentare) dela vyhradne panel ve scene.html, uzavreni
// (.../vyresit) dela vyhradne bot s BOT_STEP_TOKEN (viz
// api/production_overview.py) - stejna filozofie jako rucni kroky,
// zadne tlacitko tady.
function vyrobaSestavCommentsBadgeKarta(count) {
  if (!count) return "–";
  return `<span class="vs-comment-open" title="${count} otevřených výhrad v kartě">💬 ${count}</span>`;
}
function vyrobaSestavCommentsCellSestava(comments) {
  if (!comments || !comments.length) return "–";
  const open = comments.filter(c => !c.resolved_at);
  const resolved = comments.filter(c => c.resolved_at);
  const parts = [];
  open.forEach(c => {
    parts.push(`<span class="vs-comment-open" title="${escapeHtmlVyroba(c.author)} · ${escapeHtmlVyroba(c.created_at)}">💬 ${escapeHtmlVyroba(c.body)}</span>`);
  });
  resolved.forEach(c => {
    parts.push(`<span class="vs-comment-resolved" title="${escapeHtmlVyroba(c.author)} · ${escapeHtmlVyroba(c.created_at)}">✔ ${escapeHtmlVyroba(c.body)} <span class="hint">– vyřešil ${escapeHtmlVyroba(c.resolved_by || "?")}${c.resolution_note ? ": " + escapeHtmlVyroba(c.resolution_note) : ""}</span></span>`);
  });
  return parts.join("<br>");
}

function vyrobaSestavRCell(r) {
  if (r === "!") return '<span title="Karta obsahuje horní blok, který závisí na zastaralém receptu (id=9, nepopisuje polici)." class="vs-r-warn">!</span>';
  if (r === "+") return '<span class="vs-ratio-full">+</span>';
  return '<span class="vs-ratio-zero">–</span>';
}

// Razítka (bot8, scripts/razitkovac.py::stav_razitek - sdílené se
// spouštěčem, dopočítaný sloupec, ne ruční krok). Tři stavy: "zadna" /
// "aktualni" / "zastarala" (má razítka, ale sestava se od orazítkování
// změnila - jiná past než "nemá vůbec", ukazuje se zvlášť oranžově).
function vyrobaSestavRazitkaCellKarta(razitka) {
  if (!razitka || !razitka.celkem) return "–";
  if (razitka.zastarala > 0) {
    return `<span class="vs-razitka-stale" title="${razitka.zastarala} sestav(y) má razítka neodpovídající aktuální sestavě - potřebují přerazítkovat">${razitka.hotovo}/${razitka.celkem} <span style="opacity:.8;">(${razitka.zastarala}× zastaralé)</span></span>`;
  }
  return vyrobaSestavRatioCell({ hotovo: razitka.hotovo, celkem: razitka.celkem });
}
function vyrobaSestavRazitkaCellSestava(stav) {
  if (stav === "aktualni") return '<span class="vs-ratio-full">✓</span>';
  if (stav === "zastarala") return '<span class="vs-razitka-stale" title="Razítka neodpovídají aktuální sestavě, potřebují přerazítkovat.">⚠ zastaralé</span>';
  return '<span class="vs-ratio-zero">–</span>';
}

// Kolizní úhelníky (bot16, scripts/2026-09-11_sweep_kolizni_uhelniky.cjs,
// pravidlo v3) - JEN úhelníky proti ostatním dílům, ne všechny dvojice
// (dohodnutý název sloupce "Kolizní úhelníky", ne "Kolize" - zelená
// neručí za celou sestavu). KRITICKÉ (bot16): "0 změřeno" a "nezměřeno"
// se NESMÍ zaměnit vizuálně - NULL nikdy nesmí vypadat jako zelená.
function vyrobaSestavKolizeCellKarta(kolize) {
  if (!kolize || !kolize.celkem) return "–";
  if (kolize.koliduje > 0) return `<span class="vs-ratio-zero" style="color:#d0524a;font-weight:600;">${kolize.koliduje}/${kolize.celkem} koliduje</span>`;
  if (kolize.zmereno < kolize.celkem) return `<span class="vs-kolize-unmeasured" title="${kolize.celkem - kolize.zmereno} sestav(y) ještě nezměřeno">? (${kolize.zmereno}/${kolize.celkem} změřeno)</span>`;
  return '<span class="vs-ratio-full">0</span>';
}
function vyrobaSestavKolizeCellSestava(pocet, detail) {
  let title = "";
  if (detail) {
    title = `měřeno ${escapeHtmlVyroba(detail.mereno || "?")} · pravidlo ${escapeHtmlVyroba(detail.pravidlo || "?")} · režim ${escapeHtmlVyroba(detail.rezim || "?")}`;
    if (Array.isArray(detail.kusy) && detail.kusy.length) {
      title += " · " + detail.kusy.map(k => `${k.role} × ${k.do}`).join(", ");
    }
  }
  if (pocet == null) return `<span class="vs-kolize-unmeasured" title="nikdy nezměřeno">?</span>`;
  if (pocet > 0) return `<span title="${title}" style="color:#d0524a;font-weight:600;">${pocet}</span>`;
  return `<span class="vs-ratio-full" title="${title}">0</span>`;
}

async function loadVyrobaSestavPrehled() {
  const errEl = document.getElementById("vyrobaSestavErr");
  const contentEl = document.getElementById("vyrobaSestavContent");
  if (!contentEl) return;
  errEl.textContent = "";
  try {
    const r = await fetch("/api/admin/vyroba-sestav/prehled");
    const data = await r.json();
    if (!r.ok) {
      if (r.status === 403 || r.status === 401) {
        document.getElementById("vyrobaSestavPanel").style.display = "none";
        return;
      }
      errEl.textContent = data.error || "Nepodařilo se načíst přehled.";
      return;
    }
    document.getElementById("vyrobaSestavPanel").style.display = "";
    vyrobaSestavData = data;
    const totalEl = document.getElementById("vyrobaSestavTotal");
    if (totalEl) totalEl.textContent = `(${data.kartas.length} karet)`;
    renderVyrobaSestavTable();
  } catch (e) {
    errEl.textContent = "Nepodařilo se načíst přehled (spojení).";
  }
}

function vyrobaSestavSerieBarHtml() {
  const summary = (vyrobaSestavData && vyrobaSestavData.serie_summary) || [];
  if (summary.length <= 1) return ""; // jedina serie v datech - filtr/souhrn by nic neresil
  const badges = summary.map(s => {
    const label = vyrobaSestavSerieLabel(s.prepazka_rezerva_mm, s.podbeh_rezerva_mm) || "neznámá rezerva";
    return `<span class="vs-serie-badge">🏷️ ${escapeHtmlVyroba(label)}: <b>${s.pocet}</b></span>`;
  }).join(" ");
  // "Aktuální" (skryje VYROBA_SESTAV_STARA_SERIE_KEY) je vychozi volba -
  // viz komentar u vyrobaSestavSerieFilter vyse. "Vše" zustava pro
  // pripadny uklid/audit stare serie.
  const options = [
    `<option value="${VYROBA_SESTAV_FILTR_AKTUALNI}"${vyrobaSestavSerieFilter === VYROBA_SESTAV_FILTR_AKTUALNI ? " selected" : ""}>Aktuální (bez staré série)</option>`,
    `<option value=""${vyrobaSestavSerieFilter === "" ? " selected" : ""}>Vše (obě série)</option>`,
  ].concat(
    summary.map(s => {
      const key = vyrobaSestavSerieKey(s.prepazka_rezerva_mm, s.podbeh_rezerva_mm);
      const label = vyrobaSestavSerieLabel(s.prepazka_rezerva_mm, s.podbeh_rezerva_mm) || "neznámá rezerva";
      const sel = vyrobaSestavSerieFilter === key ? " selected" : "";
      return `<option value="${escapeHtmlVyroba(key)}"${sel}>${escapeHtmlVyroba(label)} (${s.pocet})</option>`;
    })
  ).join("");
  return `
    <div class="vs-serie-bar">
      <div class="vs-serie-summary">${badges}</div>
      <label class="vs-serie-filter-label">Zobrazit: <select id="vyrobaSestavSerieFilterSelect">${options}</select></label>
    </div>`;
}

function renderVyrobaSestavTable() {
  const contentEl = document.getElementById("vyrobaSestavContent");
  if (!vyrobaSestavData || !vyrobaSestavData.kartas.length) {
    contentEl.innerHTML = '<p class="hint">Žádné sestavy.</p>';
    return;
  }
  const serieBarHtml = vyrobaSestavSerieBarHtml();
  const filterActive = !!vyrobaSestavSerieFilter;
  const kartasToShow = filterActive
    ? vyrobaSestavData.kartas.filter(k => k.sestavy.some(vyrobaSestavSerieProchaziFiltrem))
    : vyrobaSestavData.kartas;
  const rows = kartasToShow.map(k => {
    const key = vyrobaSestavKartaKey(k);
    const expanded = vyrobaSestavExpanded.has(key);
    const blokaceHtml = k.blokace
      ? `<span class="vs-blokace" title="${escapeHtmlVyroba(k.blokace.author)} · ${escapeHtmlVyroba(k.blokace.created_at)}">🚧 ${escapeHtmlVyroba(k.blokace.text)}</span>`
      : "";
    const head = `
      <tr class="vs-karta-row" data-key="${escapeHtmlVyroba(key)}">
        <td class="vs-expand-cell">${expanded ? "▾" : "▸"}</td>
        <td class="vs-center">${k.k_kod ? escapeHtmlVyroba(k.k_kod) : '<span class="hint">–</span>'}</td>
        <td>${escapeHtmlVyroba(k.nazev)} <span class="hint">(${k.typologie_kod || "?"}, ${k.pocet_sestav} sest.)</span></td>
        <td class="vs-center">${vyrobaSestavRCell(k.r)}</td>
        <td class="vs-center">${vyrobaSestavRatioCell(k.scena)}</td>
        <td class="vs-center">${vyrobaSestavRatioCell(k.schvaleno)}</td>
        <td class="vs-center">${vyrobaSestavBoolCell(k.karta)}</td>
        <td class="vs-center">${vyrobaSestavRazitkaCellKarta(k.razitka)}</td>
        <td class="vs-center">${vyrobaSestavRenderyCellKarta(k.rendery)}</td>
        <td class="vs-center">${vyrobaSestavBoolCell(k.web)}</td>
        <td class="vs-center">${vyrobaSestavRatioCell(k.profil_vyplnen)}</td>
        <td class="vs-center">${vyrobaSestavKolizeCellKarta(k.kolize)}</td>
        <td>${escapeHtmlVyroba(k.next_step)}${k.stuck_claims_count ? "<br>" + `<span class="vs-stuck-claim">🛑 ${k.stuck_claims_count}× uvízlé zabrání</span>` : ""}${k.joint_rule_stale_count ? "<br>" + `<span class="vs-joint-stale" title="Cena spocitana starym cenovym vzorcem - pocet spoju, marze a/nebo balne neodpovidaji aktualnimu pravidlu (viz production_overview.py CURRENT_JOINT_RULE_VERSION)">🕰 ${k.joint_rule_stale_count}× stará cena</span>` : ""}</td>
        <td class="vs-center">${vyrobaSestavCommentsBadgeKarta(k.open_comments_count)}</td>
        <td>${blokaceHtml}</td>
      </tr>`;
    if (!expanded) return head;
    return head + `<tr class="vs-detail-row"><td colspan="15">${renderVyrobaSestavKartaDetail(k)}</td></tr>`;
  }).join("");

  contentEl.innerHTML = `
    ${serieBarHtml}
    <div style="overflow-x:auto;">
    <table class="vs-table">
      <thead><tr>
        <th></th><th>K</th><th>Karta</th><th>R</th><th>1 Scéna</th><th>2 Schváleno</th>
        <th>3 Karta</th><th>Razítka</th><th>4 Rendery</th><th>5 Web</th><th>Profil</th>
        <th>Kolizní úhelníky</th><th>Další krok</th><th>Výhrady</th><th>Blokace</th>
      </tr></thead>
      <tbody>${rows}</tbody>
    </table>
    </div>`;

  const serieSelect = document.getElementById("vyrobaSestavSerieFilterSelect");
  if (serieSelect) {
    serieSelect.addEventListener("change", () => {
      vyrobaSestavSerieFilter = serieSelect.value;
      renderVyrobaSestavTable();
    });
  }

  contentEl.querySelectorAll(".vs-karta-row").forEach(tr => {
    tr.addEventListener("click", (e) => {
      if (e.target.closest("button,input,textarea,a")) return;
      const key = tr.dataset.key;
      if (vyrobaSestavExpanded.has(key)) vyrobaSestavExpanded.delete(key);
      else vyrobaSestavExpanded.add(key);
      renderVyrobaSestavTable();
    });
  });
  wireVyrobaSestavDetailHandlers(contentEl);
}

// Ruční kroky jsou v UI JEN KE ČTENÍ (bot3 2026-09-11, po incidentu:
// Robert v adminu omylem odkliknul zaškrtávátko navržené jako
// klikatelné pro staff - "zaškrtávátko, které jde kliknout omylem, je
// ve výkazu stavu vada"). Zápis jde výhradně přes API s botím/
// kontrolorským tokenem (viz api/production_overview.py), NIKDY
// klikáním tady - proto žádný <button>, jen badge stavu s VIDITELNÝM
// (ne jen v title) kdo/kdy.
function vyrobaSestavStepBadge(step, label) {
  if (step.verified) {
    // NESPLNENO musi vypadat ZASADNE jinak nez "jeste neoverene" (zluta
    // vs. cervena) - to jsou dva uplne jine stavy (bot4 review 2026-09-11):
    // "overeno a neprošlo" neni totez jako "jeste nikdo neoveril".
    if (step.verify_verdict === "NESPLNENO") {
      return `<span class="vs-step vs-step-failed">✘ ${escapeHtmlVyroba(label)} (NESPLNĚNO) <span class="hint">– ověřil ${escapeHtmlVyroba(step.verified_by)}, ${escapeHtmlVyroba(step.verified_at)}${step.verify_note ? ": " + escapeHtmlVyroba(step.verify_note) : ""}</span></span>`;
    }
    const verdict = step.verify_verdict === "CASTECNE" ? "ČÁSTEČNĚ" : "SPLNĚNO";
    return `<span class="vs-step vs-step-verified">✔✔ ${escapeHtmlVyroba(label)} (${verdict}) <span class="hint">– ověřil ${escapeHtmlVyroba(step.verified_by)}, ${escapeHtmlVyroba(step.verified_at)}${step.verify_note ? ": " + escapeHtmlVyroba(step.verify_note) : ""}</span></span>`;
  }
  if (step.reported) {
    return `<span class="vs-step vs-step-reported">✔ ${escapeHtmlVyroba(label)} <span class="hint">– nahlásil ${escapeHtmlVyroba(step.reported_by)}, ${escapeHtmlVyroba(step.reported_at)} (čeká na ověření)</span></span>`;
  }
  return `<span class="vs-step vs-step-empty">☐ ${escapeHtmlVyroba(label)}</span>`;
}

function renderVyrobaSestavKartaDetail(k) {
  const stepDefs = vyrobaSestavData.step_defs;
  const kartaSteps = stepDefs.filter(sd => sd.scope === "karta");
  const sestavaSteps = stepDefs.filter(sd => sd.scope === "sestava");

  const kartaStepsHtml = kartaSteps.map(sd =>
    vyrobaSestavStepBadge(k.karta_steps[sd.step_key] || { reported: false, verified: false }, sd.label)
  ).join(" ");

  const blokaceForm = `
    <div class="vs-blokace-form">
      <input type="text" class="vs-blokace-input" placeholder="Blokace (proč karta stojí)…"
        data-car-model-id="${k.car_model_id ?? ""}" data-typologie-id="${k.typologie_id ?? ""}"
        value="${k.blokace ? escapeHtmlVyroba(k.blokace.text) : ""}">
      <button type="button" class="vs-blokace-save" data-car-model-id="${k.car_model_id ?? ""}" data-typologie-id="${k.typologie_id ?? ""}">Uložit</button>
      ${k.blokace ? `<span class="hint">naposledy: ${escapeHtmlVyroba(k.blokace.author)} · ${escapeHtmlVyroba(k.blokace.created_at)}</span>` : ""}
    </div>`;

  // Filtr podle serie (viz vyrobaSestavSerieFilter) - dela se AZ TADY, na
  // urovni jednotlivych sestav, protoze jedna karta (vozidlo x typologie)
  // muze mit sestavy z OBOU serii soucasne (stejny recept/karoserie, jina
  // kolizni rezerva - bot8 2026-09-12). Radek karty i jeji souhrnna cisla
  // (scena/schvaleno/...) zustavaji nad CELOU kartou bez ohledu na filtr -
  // filtruje se jen tenhle rozbaleny seznam sestav.
  const sestavyFiltered = vyrobaSestavSerieFilter
    ? k.sestavy.filter(vyrobaSestavSerieProchaziFiltrem)
    : k.sestavy;

  const sestavyRows = sestavyFiltered.map(s => {
    const stepsHtml = sestavaSteps.map(sd =>
      vyrobaSestavStepBadge(s.steps[sd.step_key] || { reported: false, verified: false }, sd.label)
    ).join(" ");
    const serieLabel = vyrobaSestavSerieLabel(s.prepazka_rezerva_mm, s.podbeh_rezerva_mm);
    return `
      <tr>
        <td>${escapeHtmlVyroba(s.name)} <span class="hint">#${s.id}</span></td>
        <td class="vs-center">${vyrobaSestavBoolCell(s.scena)}</td>
        <td class="vs-center">${vyrobaSestavBoolCell(s.schvaleno)}</td>
        <td class="vs-center">${vyrobaSestavBoolCell(s.karta)}</td>
        <td class="vs-center">${vyrobaSestavRazitkaCellSestava(s.razitka_stav)}</td>
        <td class="vs-center">${s.rendery}${s.render_job ? "<br>" + vyrobaSestavRenderJobBadge(s.render_job) : ""}</td>
        <td class="vs-center">${vyrobaSestavBoolCell(s.web)}</td>
        <td class="vs-center">${s.profil_mm ?? "–"}</td>
        <td class="vs-center">${vyrobaSestavKolizeCellSestava(s.kolize_pocet, s.kolize_detail)}</td>
        <td class="vs-steps">${stepsHtml}${s.stuck_claims && s.stuck_claims.length ? " " + vyrobaSestavStuckClaimsBadge(s.stuck_claims) : ""}${s.joint_rule_stale ? ` <span class="vs-joint-stale" title="Cena spocitana starym cenovym vzorcem (pocet spoju/marze/balne)">🕰 stará cena</span>` : ""}</td>
        <td>${vyrobaSestavCommentsCellSestava(s.comments)}</td>
        <td class="vs-center">${serieLabel ? `<span class="vs-serie-badge">🏷️ ${escapeHtmlVyroba(serieLabel)}</span>` : "–"}</td>
      </tr>`;
  }).join("");

  return `
    <div class="vs-detail">
      <div class="vs-karta-steps"><strong>Kroky na úrovni karty:</strong> ${kartaStepsHtml || '<span class="hint">žádné</span>'}</div>
      ${blokaceForm}
      <div style="overflow-x:auto;">
      <table class="vs-table vs-subtable">
        <thead><tr><th>Sestava</th><th>Scéna</th><th>Schváleno</th><th>Karta</th><th>Razítka</th><th>Rendery</th><th>Web</th><th>Profil</th><th>Kolize</th><th>Ruční kroky</th><th>Výhrady</th><th>Série</th></tr></thead>
        <tbody>${sestavyRows}</tbody>
      </table>
      </div>
    </div>`;
}

function wireVyrobaSestavDetailHandlers(root) {
  // Ruční kroky (production_step_checks) jdou zapsat JEN přes API s
  // botím/kontrolorským tokenem (bot3 2026-09-11, po incidentu s
  // omylem odkliknutým krokem) - tahle obrazovka je pro ně čistě READ-
  // ONLY, žádný listener/tlačítko tu pro ně proto není. Blokace
  // zůstává jediný zápis, který tahle obrazovka dělá.
  root.querySelectorAll(".vs-blokace-save").forEach(btn => {
    btn.addEventListener("click", async () => {
      const input = root.querySelector(`.vs-blokace-input[data-car-model-id="${btn.dataset.carModelId}"][data-typologie-id="${btn.dataset.typologieId}"]`);
      btn.disabled = true;
      try {
        const r = await fetch("/api/admin/vyroba-sestav/blokace", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            car_model_id: parseInt(btn.dataset.carModelId, 10),
            typologie_id: parseInt(btn.dataset.typologieId, 10),
            text: input ? input.value : "",
          }),
        });
        const data = await r.json().catch(() => ({}));
        if (!r.ok) { alert(data.error || "Nepodařilo se uložit blokaci."); btn.disabled = false; return; }
        await loadVyrobaSestavPrehled();
      } catch (e) {
        alert("Nepodařilo se uložit blokaci (spojení).");
        btn.disabled = false;
      }
    });
  });
}

const vyrobaSestavRefreshBtnEl = document.getElementById("vyrobaSestavRefreshBtn");
if (vyrobaSestavRefreshBtnEl) vyrobaSestavRefreshBtnEl.onclick = loadVyrobaSestavPrehled;
