// ==================== PREHLEDY > ZALOHY ====================
// bot16, 2026-09-13 - Robert pres bot3: "chce videt otisk/stav offsite
// S3 zalohy, at se kvuli tomu nemusi prihlasovat na Contabo". Cte jen
// GET /api/admin/offsite-backup (api/offsite_backup.py) - zadne zive
// volani rclone odsud, jen DB zaznam, ktery si po kazdem pokusu zapisuje
// scripts/daily_backup.py (bezi jako root, ma k rclone pristup).

function fmtBajty(b) {
  if (b == null) return "?";
  const jednotky = ["B", "KB", "MB", "GB", "TB"];
  let i = 0, v = b;
  while (v >= 1024 && i < jednotky.length - 1) { v /= 1024; i++; }
  return `${v.toFixed(i === 0 ? 0 : 1)} ${jednotky[i]}`;
}

const ZALOHY_STAV_LABEL = {
  ok: '<span style="color:var(--ok,#3fb87a);">● OK</span>',
  chyba: '<span style="color:var(--danger,#d9534f);">● chyba</span>',
  preskoceno: '<span style="color:var(--warn,#d9a441);">● přeskočeno</span>',
};

function renderZalohyPosledni(posledni) {
  const el = document.getElementById("zalohyPosledni");
  if (!posledni) {
    el.innerHTML = `<p class="hint">Zatím žádný záznam o offsite záloze - buď ještě neproběhla první, nebo skript ještě neobsahuje tenhle zápis (do dalšího nočního běhu ve 03:30).</p>`;
    return;
  }
  const stary = (Date.now() - new Date(posledni.nahrano_at).getTime()) > 36 * 3600 * 1000;
  const varovani = stary
    ? `<div class="gpu-mon-offline-banner" style="margin-bottom:8px;">Poslední záznam je starší než 36 hodin - denní záloha (03:30) neproběhla, nebo se nezapsala.</div>`
    : "";
  el.innerHTML = `
    ${varovani}
    <div style="border:1px solid var(--border-soft2);border-radius:8px;padding:10px 14px;">
      <div style="font-size:13px;font-weight:600;margin-bottom:4px;">
        ${ZALOHY_STAV_LABEL[posledni.stav] || posledni.stav} &middot; ${posledni.soubor}
      </div>
      <div style="color:var(--text-muted);font-size:12px;line-height:1.6;">
        Nahráno: ${new Date(posledni.nahrano_at).toLocaleString("cs-CZ")}<br>
        Velikost archivu: ${fmtBajty(posledni.velikost_b)}<br>
        ${posledni.remote_objektu_celkem != null
          ? `Celkem na S3 (bez retence, roste): ${posledni.remote_objektu_celkem} souborů, ${fmtBajty(posledni.remote_bytu_celkem)}<br>`
          : ""}
        ${posledni.detail ? `<span style="color:var(--danger,#d9534f);">${hpEscapeHtml(posledni.detail)}</span>` : ""}
      </div>
    </div>`;
}

function renderZalohyHistorie(historie) {
  const tbody = document.getElementById("zalohyHistorieTbody");
  if (!historie || !historie.length) {
    tbody.innerHTML = '<tr><td colspan="5" class="hint">Žádná historie.</td></tr>';
    return;
  }
  tbody.innerHTML = historie.map(r => `
    <tr>
      <td>${new Date(r.nahrano_at).toLocaleString("cs-CZ")}</td>
      <td>${hpEscapeHtml(r.soubor)}</td>
      <td>${fmtBajty(r.velikost_b)}</td>
      <td>${ZALOHY_STAV_LABEL[r.stav] || r.stav}</td>
      <td style="max-width:320px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="${hpEscapeHtml(r.detail || "")}">${hpEscapeHtml(r.detail || "")}</td>
    </tr>
  `).join("");
}

// bot16, 2026-09-13 (Robert upresnil: "má zde být výpis uložených
// souborů záloh z uloziste S3, ne samotne soubory, jen seznam") -
// skutecny seznam souboru (zrcadlo rclone lsjson, viz api/offsite_backup.py).
function renderZalohySoubory(soubory) {
  document.getElementById("zalohySouboryPocet").textContent = soubory.length;
  const tbody = document.getElementById("zalohySouboryTbody");
  if (!soubory.length) {
    tbody.innerHTML = '<tr><td colspan="3" class="hint">Zatím žádný soubor - buď ještě neproběhla první offsite záloha, nebo skript ještě neobsahuje tenhle zápis.</td></tr>';
    return;
  }
  tbody.innerHTML = soubory.map(s => `
    <tr>
      <td>${hpEscapeHtml(s.soubor)}</td>
      <td>${fmtBajty(s.velikost_b)}</td>
      <td>${s.zmeneno_at ? new Date(s.zmeneno_at).toLocaleString("cs-CZ") : "?"}</td>
    </tr>
  `).join("");
}

async function loadZalohy() {
  const errEl = document.getElementById("zalohyErr");
  errEl.textContent = "";
  try {
    const r = await fetch("/api/admin/offsite-backup");
    if (!r.ok) { errEl.textContent = "Načtení selhalo."; return; }
    const data = await r.json();
    renderZalohyPosledni(data.posledni);
    renderZalohySoubory(data.soubory || []);
    renderZalohyHistorie(data.historie || []);
  } catch (e) {
    errEl.textContent = "Načtení selhalo: " + e.message;
  }
}
document.getElementById("zalohyRefreshBtn").onclick = loadZalohy;
