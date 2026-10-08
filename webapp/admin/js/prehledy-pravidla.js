// ==================== PREHLEDY > PRAVIDLA/POSTUPY ====================
// bot9, 2026-09-12 (Robert pres bot3, upřesněno Robertem přímo v chatu -
// viz komentář u #tab-pravidla v admin.html a docstring api/pravidla.py).
// ŽÁDNÁ DB kopie obsahu - `pravidlaCache` a `pravidlaObsahCache` jsou jen
// klientský cache aktuálního fetche, ne perzistentní úložiště. Do DB (přes
// PUT .../vyber) jde JEN checkbox "zobrazit ano/ne".
let pravidlaCache = [];
const pravidlaObsahCache = new Map(); // soubor -> {obsah_md, posledni_commit}
let prMode = "vybrane"; // "vybrane" | "vse"

async function loadPravidla() {
  document.getElementById("pravidlaErr").textContent = "";
  const r = await fetch("/api/admin/pravidla-postupy");
  const data = await r.json().catch(() => ({}));
  if (!r.ok) { document.getElementById("pravidlaErr").textContent = data.error || "Chyba načtení."; return; }
  pravidlaCache = data.items || [];
  renderPravidla();
}

function fmtPrDate(iso) {
  if (!iso) return "";
  try { return new Date(iso).toLocaleDateString("cs-CZ"); } catch (e) { return ""; }
}

async function nactiObsahSouboru(soubor) {
  if (pravidlaObsahCache.has(soubor)) return pravidlaObsahCache.get(soubor);
  const r = await fetch(`/api/admin/pravidla-postupy/soubor/${encodeURIComponent(soubor)}`);
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.error || "Chyba načtení souboru.");
  pravidlaObsahCache.set(soubor, data);
  return data;
}

async function nactiObsahReceptu(tabulka, receptId) {
  const klic = `${tabulka}#${receptId}`;
  if (pravidlaObsahCache.has(klic)) return pravidlaObsahCache.get(klic);
  const r = await fetch(`/api/admin/pravidla-postupy/recept/${encodeURIComponent(tabulka)}/${receptId}`);
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.error || "Chyba načtení receptu.");
  pravidlaObsahCache.set(klic, data);
  return data;
}

// -------------------- minimální markdown -> HTML --------------------
// Robert: "nic exotického v těch souborech není" - žádná knihovna,
// pokrývá jen to, co se v .md souborech projektu skutečně používá:
// nadpisy #-######, ` ```fence``` `, odrážky "- ", číslované seznamy
// "N. " (obojí i s odsazeným pokračováním na dalších řádcích), **tučné**,
// *kurzíva*, `inline kód`. Bez odkazů (v souborech se nepoužívají).
function mdToHtml(md) {
  const lines = String(md == null ? "" : md).replace(/\r\n/g, "\n").split("\n");
  let html = "";
  let listType = null;
  function closeList() { if (listType) { html += `</${listType}>`; listType = null; } }
  function inlineMd(s) {
    s = hpEscapeHtml(s);
    s = s.replace(/`([^`]+)`/g, (m, c) => `<code>${c}</code>`);
    s = s.replace(/\*\*([^*]+)\*\*/g, (m, b) => `<strong>${b}</strong>`);
    s = s.replace(/(^|[^*])\*([^*\s][^*]*?)\*(?!\*)/g, (m, pre, em) => `${pre}<em>${em}</em>`);
    return s;
  }
  function seberOdsazenePokracovani(i) {
    const dalsi = [];
    while (i < lines.length && /^\s+\S/.test(lines[i]) && !/^\s*```/.test(lines[i])) {
      dalsi.push(lines[i].trim());
      i++;
    }
    return [dalsi, i];
  }
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (/^```/.test(line)) {
      closeList();
      const buf = [];
      i++;
      while (i < lines.length && !/^```/.test(lines[i])) { buf.push(lines[i]); i++; }
      i++;
      html += `<pre style="white-space:pre-wrap;overflow-x:auto;background:var(--panel-bg-alt);padding:8px;border-radius:6px;font-size:12px;"><code>${hpEscapeHtml(buf.join("\n"))}</code></pre>`;
      continue;
    }
    const heading = line.match(/^(#{1,6})\s+(.*)$/);
    if (heading) {
      closeList();
      const level = Math.min(6, heading[1].length + 2); // v ramci karty nikdy nezacinat h1/h2
      html += `<h${level} style="margin:10px 0 4px;">${inlineMd(heading[2])}</h${level}>`;
      i++;
      continue;
    }
    const bullet = line.match(/^-\s+(.*)$/);
    if (bullet) {
      if (listType !== "ul") { closeList(); html += "<ul style=\"margin:4px 0;padding-left:20px;\">"; listType = "ul"; }
      const [pokracovani, dalsiI] = seberOdsazenePokracovani(i + 1);
      html += `<li>${inlineMd([bullet[1], ...pokracovani].join(" "))}</li>`;
      i = dalsiI;
      continue;
    }
    const numbered = line.match(/^\d+\.\s+(.*)$/);
    if (numbered) {
      if (listType !== "ol") { closeList(); html += "<ol style=\"margin:4px 0;padding-left:20px;\">"; listType = "ol"; }
      const [pokracovani, dalsiI] = seberOdsazenePokracovani(i + 1);
      html += `<li>${inlineMd([numbered[1], ...pokracovani].join(" "))}</li>`;
      i = dalsiI;
      continue;
    }
    if (!line.trim()) { closeList(); i++; continue; }
    closeList();
    const buf = [line];
    i++;
    while (i < lines.length && lines[i].trim() && !/^```/.test(lines[i]) && !/^#{1,6}\s/.test(lines[i]) && !/^-\s/.test(lines[i]) && !/^\d+\.\s/.test(lines[i])) {
      buf.push(lines[i]);
      i++;
    }
    html += `<p style="margin:4px 0;">${inlineMd(buf.join(" "))}</p>`;
  }
  closeList();
  return html;
}

function kratkyNazev(p) {
  if (p.typ === "soubor") return p.soubor;
  if (p.typ === "recept") return p.nazev;
  const m = p.text_md.match(/\*\*([^*]+)\*\*/);
  if (m) return m[1];
  const jednoradkovy = p.text_md.replace(/\s+/g, " ").replace(/^[-\d.]+\s*/, "");
  return jednoradkovy.length > 90 ? jednoradkovy.slice(0, 90) + "…" : jednoradkovy;
}

function oznacTlacitkaRezimu() {
  const vyb = document.getElementById("prZobrazitVybrane");
  const vse = document.getElementById("prZobrazitVse");
  vyb.style.fontWeight = prMode === "vybrane" ? "700" : "400";
  vyb.style.textDecoration = prMode === "vybrane" ? "underline" : "none";
  vse.style.fontWeight = prMode === "vse" ? "700" : "400";
  vse.style.textDecoration = prMode === "vse" ? "underline" : "none";
}

function vytvorKartu(p) {
  const el = document.createElement("div");
  el.style.cssText = "padding:10px 12px;border-top:1px solid var(--border-soft);";
  el.innerHTML = `
    <div style="display:flex;align-items:flex-start;gap:8px;">
      <input type="checkbox" class="pr-zobrazit" ${p.zobrazit ? "checked" : ""} style="margin-top:3px;" title="Zobrazit v přehledu &quot;Vybraná&quot;">
      <div style="flex:1;min-width:0;">
        <div style="font-weight:600;font-size:13.5px;">${hpEscapeHtml(kratkyNazev(p))}</div>
        <div class="pr-obsah" style="margin-top:2px;font-size:13px;"></div>
      </div>
      <span style="color:var(--text-faint);font-size:11px;white-space:nowrap;">${fmtPrDate(p.posledni_commit)}</span>
    </div>
  `;
  const obsahEl = el.querySelector(".pr-obsah");
  obsahEl.innerHTML = mdToHtml(p.text_md);

  if (p.typ === "soubor" || p.typ === "recept") {
    const popisek = p.typ === "soubor" ? "Zobrazit celý obsah souboru" : "Zobrazit celý recept";
    const btn = document.createElement("button");
    btn.type = "button";
    btn.textContent = popisek;
    btn.style.cssText = "font-size:11.5px;padding:2px 8px;margin-top:4px;";
    btn.onclick = async () => {
      btn.disabled = true;
      btn.textContent = "Načítám…";
      try {
        const data = p.typ === "soubor" ? await nactiObsahSouboru(p.soubor) : await nactiObsahReceptu(p.tabulka, p.recept_id);
        const cely = document.createElement("div");
        cely.style.cssText = "margin-top:8px;padding:10px;background:var(--panel-bg-alt);border-radius:8px;max-height:600px;overflow:auto;";
        cely.innerHTML = mdToHtml(data.obsah_md);
        btn.replaceWith(cely);
      } catch (e) {
        btn.disabled = false;
        btn.textContent = popisek;
        document.getElementById("pravidlaErr").textContent = e.message;
      }
    };
    obsahEl.appendChild(btn);
    // U vybraneho souboru/receptu v rezimu "Vybrana" rovnou natahnout cely
    // obsah - Robert uz vyslovne vybral, ze ho chce videt, netreba extra klik.
    if (prMode === "vybrane" && p.zobrazit) btn.click();
  }

  el.querySelector(".pr-zobrazit").onchange = async (ev) => {
    const zaskrtnuto = ev.target.checked;
    document.getElementById("pravidlaErr").textContent = "";
    ev.target.disabled = true;
    try {
      const r = await fetch("/api/admin/pravidla-postupy/vyber", {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ klic: p.klic, zobrazit: zaskrtnuto }),
      });
      const data = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(data.error || "Chyba.");
      p.zobrazit = zaskrtnuto;
      if (prMode === "vybrane") renderPravidla();
    } catch (e) {
      ev.target.checked = !zaskrtnuto;
      document.getElementById("pravidlaErr").textContent = e.message;
    } finally {
      ev.target.disabled = false;
    }
  };

  return el;
}

function renderPravidla() {
  oznacTlacitkaRezimu();
  const zobrazovana = prMode === "vybrane" ? pravidlaCache.filter(p => p.zobrazit) : pravidlaCache;

  const poradiSkupin = [];
  const podleSkupiny = new Map();
  zobrazovana.forEach(p => {
    const klicSkupiny = p.skupina || `__sam__${p.klic}`;
    if (!podleSkupiny.has(klicSkupiny)) { podleSkupiny.set(klicSkupiny, []); poradiSkupin.push(klicSkupiny); }
    podleSkupiny.get(klicSkupiny).push(p);
  });

  const wrap = document.getElementById("pravidlaList");
  wrap.innerHTML = "";
  if (!zobrazovana.length) {
    wrap.innerHTML = prMode === "vybrane"
      ? '<p class="hint">Zatím nic vybráno není - přepni na "Všechny kandidáty" a odklikni, co se má tady zobrazovat.</p>'
      : '<p class="hint">Žádní kandidáti nenalezeni.</p>';
    return;
  }
  poradiSkupin.forEach(klicSkupiny => {
    const polozky = podleSkupiny.get(klicSkupiny);
    const skupinaEl = document.createElement("div");
    skupinaEl.style.cssText = "margin-bottom:18px;border:1px solid var(--border-soft);border-radius:10px;overflow:hidden;";
    if (polozky[0].skupina) {
      const hlavicka = document.createElement("div");
      hlavicka.style.cssText = "padding:7px 12px;background:var(--panel-bg-alt);font-weight:600;font-size:12.5px;";
      hlavicka.textContent = polozky[0].skupina;
      skupinaEl.appendChild(hlavicka);
    }
    polozky.forEach(p => skupinaEl.appendChild(vytvorKartu(p)));
    wrap.appendChild(skupinaEl);
  });
}

document.getElementById("prZobrazitVybrane").onclick = () => { prMode = "vybrane"; renderPravidla(); };
document.getElementById("prZobrazitVse").onclick = () => { prMode = "vse"; renderPravidla(); };
