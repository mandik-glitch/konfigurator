// GPU render worker - zivy panel (Robert 2026-09-11: "chci videt zive v
// adminu teplotu PC GPU karty a rychlost ventilatoru"). Data sbira
// scripts/render_worker_agent.py + uklada/vyhodnocuje api/render_worker.py
// (bot9/bot16) - tenhle soubor jen cte /api/admin/render-worker/status a
// kresli. NEPOCITA nic znovu (historie/prah uz prichazi hotove).
//
// KRITICKE pravidlo (bot3 2026-09-11, po Robertove "at se stara teplota
// neukazuje jako aktualni"): `data.online`/`state` (server uz vyhodnocuje
// 90s okno, viz WORKER_ONLINE_S v api/render_worker.py) rozhoduje o tom,
// jestli se cisla zobrazi jako ziva, nebo jako zastarala/vypnuta - NIKDY
// se neukazuje posledni znama teplota bez tohodle rozliseni.

let gpuMonitorTimer = null;

function gpuMonFmtAge(s) {
  if (s == null) return "?";
  if (s < 60) return Math.round(s) + " s";
  if (s < 3600) return Math.round(s / 60) + " min";
  return (s / 3600).toFixed(1) + " h";
}

function gpuMonStatCell(label, value, unit, cls) {
  const valHtml = value == null
    ? `<span class="gpu-mon-stat-value gpu-mon-missing">nehlásí</span>`
    : `<span class="gpu-mon-stat-value ${cls || "gpu-mon-ok"}">${value}${unit || ""}</span>`;
  return `<div class="gpu-mon-stat"><div class="gpu-mon-stat-label">${label}</div>${valHtml}</div>`;
}

function gpuMonTempClass(temp, prah) {
  if (temp == null || prah == null) return "gpu-mon-ok";
  if (temp > prah) return "gpu-mon-hot";
  if (temp > prah - 8) return "gpu-mon-warn";
  return "gpu-mon-ok";
}

function gpuMonDrawChart(canvas, historie, prah) {
  const ctx = canvas.getContext("2d");
  const w = canvas.width, h = canvas.height;
  ctx.clearRect(0, 0, w, h);
  const body = (historie || []).filter(p => p.teplota_c != null);
  if (body.length < 2) {
    ctx.fillStyle = "#9aa4b2";
    ctx.font = "12px sans-serif";
    ctx.fillText("Zatím žádná historie.", 10, h / 2);
    return;
  }
  const pad = { l: 40, r: 10, t: 10, b: 20 };
  const plotW = w - pad.l - pad.r;
  const plotH = h - pad.t - pad.b;
  const temps = body.map(p => p.teplota_c);
  let minT = Math.min(...temps, prah != null ? prah : Infinity, 20);
  let maxT = Math.max(...temps, prah != null ? prah : -Infinity, minT + 10);
  minT = Math.floor(minT / 5) * 5 - 5;
  maxT = Math.ceil(maxT / 5) * 5 + 5;
  const t0 = body[0].ts, t1 = body[body.length - 1].ts;
  const xOf = (ts) => pad.l + (t1 > t0 ? (ts - t0) / (t1 - t0) : 0) * plotW;
  const yOf = (temp) => pad.t + (1 - (temp - minT) / (maxT - minT)) * plotH;

  const fmtTime = (ts) => {
    const d = new Date(ts * 1000);
    return String(d.getHours()).padStart(2, "0") + ":" + String(d.getMinutes()).padStart(2, "0");
  };

  // Mřížka + popisky (Robert 2026-09-29 "chci přesnější časovou osu i
  // teploty"): kroky se volí z "kulatých" hodnot podle skutečné velikosti
  // plátna, takže popisky nikdy nesplývají a čas leží na celých minutách/hodinách.
  const krokTeplot = [1, 2, 5, 10, 20, 50].find(s => (maxT - minT) / s <= plotH / 16) || 50;
  const krokCasu = [60, 120, 300, 600, 900, 1200, 1800, 3600, 7200, 10800, 21600]
    .find(s => (t1 - t0) / s <= plotW / 70) || 21600;

  ctx.lineWidth = 1;
  ctx.fillStyle = "#9aa4b2";
  ctx.font = "10px sans-serif";

  ctx.textAlign = "right";
  ctx.textBaseline = "middle";
  for (let v = Math.ceil(minT / krokTeplot) * krokTeplot; v <= maxT; v += krokTeplot) {
    const y = Math.round(yOf(v)) + 0.5;
    ctx.strokeStyle = "rgba(154,164,178,.16)";
    ctx.beginPath();
    ctx.moveTo(pad.l, y);
    ctx.lineTo(pad.l + plotW, y);
    ctx.stroke();
    ctx.fillText(v + "°C", pad.l - 4, y);
  }

  ctx.textAlign = "center";
  ctx.textBaseline = "alphabetic";
  const tzPosunS = -new Date(t0 * 1000).getTimezoneOffset() * 60;
  for (let ts = Math.ceil((t0 + tzPosunS) / krokCasu) * krokCasu - tzPosunS; ts <= t1; ts += krokCasu) {
    const x = Math.round(xOf(ts)) + 0.5;
    ctx.strokeStyle = "rgba(154,164,178,.16)";
    ctx.beginPath();
    ctx.moveTo(x, pad.t);
    ctx.lineTo(x, pad.t + plotH);
    ctx.stroke();
    ctx.fillText(fmtTime(ts), Math.min(Math.max(x, pad.l + 14), pad.l + plotW - 14), h - 4);
  }
  ctx.textAlign = "left";

  ctx.strokeStyle = "rgba(154,164,178,.35)";
  ctx.beginPath();
  ctx.moveTo(pad.l, pad.t);
  ctx.lineTo(pad.l, pad.t + plotH);
  ctx.lineTo(pad.l + plotW, pad.t + plotH);
  ctx.stroke();

  if (prah != null) {
    ctx.strokeStyle = "#d0524a";
    ctx.setLineDash([4, 3]);
    ctx.beginPath();
    ctx.moveTo(pad.l, yOf(prah));
    ctx.lineTo(pad.l + plotW, yOf(prah));
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.fillStyle = "#d0524a";
    ctx.fillText("práh " + Math.round(prah) + "°C", pad.l + plotW - 62, Math.max(pad.t + 9, yOf(prah) - 3));
  }

  ctx.strokeStyle = "#3fb8d4";
  ctx.lineWidth = 2;
  ctx.beginPath();
  body.forEach((p, i) => {
    const x = xOf(p.ts), y = yOf(p.teplota_c);
    if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
  });
  ctx.stroke();
}

// bot16, 2026-09-12 (bot4 zadani, po dnesnim omylu "GPU spí/neslyším
// ho", ktery vedl k rucnimu restartu agenta UPROSTRED behu renderu):
// detail prave zpracovavane ulohy + poslednich par dokoncenych. Cte
// data, ktera uz render_worker_status posila navic (current_job/
// recent_jobs) - nic tady nepocita znovu, stejna zasada jako u zbytku
// souboru.
function gpuMonFmtDuration(s) {
  if (s == null) return "?";
  if (s < 60) return Math.round(s) + " s";
  const m = Math.floor(s / 60), zbyle = Math.round(s % 60);
  return m < 60 ? `${m} min ${zbyle} s` : `${Math.floor(m / 60)} h ${m % 60} min`;
}

function gpuMonRenderCurrentJob(job, targetId) {
  // bot16, 2026-09-12 (bot4 zadani): druhy volitelny parametr, at jde
  // stejna funkce zavolat i z Pipeline > Render/GPU (crm-nabidky.js) bez
  // duplikace - vychozi cil zustava puvodni panel na Dashboardu.
  const el = document.getElementById(targetId || "gpuMonitorCurrentJob");
  if (!el) return;
  if (!job) {
    el.innerHTML = `<div style="font-size:12px;color:var(--text-faint);">Právě se nic nezpracovává.</div>`;
    return;
  }
  const nazev = job.assembly_name ? `${job.assembly_name} (#${job.assembly_id})` : (job.assembly_id ? `sestava #${job.assembly_id}` : job.job);
  const pripravaBadge = job.priprava
    ? `<span style="background:var(--warn);color:#1a1a1a;border-radius:4px;padding:1px 6px;font-size:10.5px;font-weight:600;margin-left:6px;">v přípravné fázi - žádný postup zatím normální</span>`
    : "";
  const snimky = job.expected_frames != null
    ? `${job.frames_written || 0} / ${job.expected_frames} snímků`
    : `${job.frames_written || 0} snímků`;
  const detaily = [
    job.samples != null ? `samples: ${job.samples} (override)` : null,
    job.hdri_rotace_deg ? `HDRI rotace: ${job.hdri_rotace_deg}°` : null,
  ].filter(Boolean).join(" · ");
  el.innerHTML = `
    <div style="border:1px solid var(--border-soft2);border-radius:8px;padding:8px 10px;font-size:12px;">
      <div style="font-weight:600;">⚙️ Právě se zpracovává: ${hpEscapeHtml(nazev)}${pripravaBadge}</div>
      <div style="color:var(--text-muted);margin-top:3px;">
        od startu: ${gpuMonFmtDuration(job.elapsed_s)} · ${snimky}${detaily ? " · " + detaily : ""}
      </div>
    </div>`;
}

function gpuMonRenderRecentJobs(jobs, targetId) {
  const el = document.getElementById(targetId || "gpuMonitorRecentJobs");
  if (!el) return;
  if (!jobs || !jobs.length) {
    el.innerHTML = "";
    return;
  }
  const stavBarva = { done: "var(--success)", error: "var(--error)", cancelled: "var(--text-faint)" };
  const stavLabel = { done: "hotovo", error: "chyba", cancelled: "zrušeno" };
  const radky = jobs.map(j => {
    const nazev = j.assembly_name ? `${j.assembly_name} (#${j.assembly_id})` : (j.assembly_id ? `#${j.assembly_id}` : j.job);
    const cas = j.render_seconds != null ? gpuMonFmtDuration(j.render_seconds) : "?";
    let stavInfo = "";
    if (j.state === "error" && j.error) {
      stavInfo = `<div style="color:var(--error);margin-top:1px;">${hpEscapeHtml(j.error)}</div>`;
    } else if (j.state === "done") {
      stavInfo = j.commit_pending
        ? `<div style="color:var(--text-faint);margin-top:1px;">čeká na aktivaci (commit_pending)${j.note ? " - " + hpEscapeHtml(j.note) : ""}</div>`
        : "";
    }
    return `
      <div style="padding:4px 0;border-top:1px solid var(--border-soft2);">
        <span style="color:${stavBarva[j.state] || "var(--text-faint)"};font-weight:600;">${stavLabel[j.state] || j.state}</span>
        · ${hpEscapeHtml(nazev)} · ${cas}
        ${stavInfo}
      </div>`;
  }).join("");
  el.innerHTML = `<div style="font-size:11.5px;color:var(--text-faint);margin-bottom:2px;">Posledních ${jobs.length} dokončených úloh:</div>${radky}`;
}

async function loadGpuMonitorPanel() {
  const panel = document.getElementById("gpuMonitorPanel");
  const errEl = document.getElementById("gpuMonitorErr");
  if (!panel || !errEl) return;
  errEl.innerHTML = "";

  let data;
  try {
    const r = await fetch("/api/admin/render-worker/status");
    if (!r.ok) {
      if (r.status === 403 || r.status === 401) { panel.style.display = "none"; return; }
      errEl.textContent = "Nepodařilo se načíst stav workeru.";
      return;
    }
    data = await r.json();
  } catch (e) {
    errEl.textContent = "Nepodařilo se načíst stav workeru (spojení).";
    return;
  }

  const labelEl = document.getElementById("gpuMonitorStateLabel");
  const statsEl = document.getElementById("gpuMonitorStats");
  const footEl = document.getElementById("gpuMonitorFootnote");

  if (data.last_seen_s == null) {
    // Zadny worker se jeste nikdy nehlasil - zadna "posledni znama"
    // hodnota k zobrazeni ani neexistuje, netvarit se opacne.
    labelEl.textContent = "";
    statsEl.innerHTML = "";
    footEl.textContent = "";
    gpuMonRenderCurrentJob(null);
    gpuMonRenderRecentJobs(null);
    errEl.innerHTML = `<div class="gpu-mon-offline-banner">Žádný render worker se zatím nikdy nehlásil.</div>`;
    return;
  }

  const offline = !data.online;
  const stuck = data.state === "stuck";
  const versionMismatch = data.version_matches === false;
  panel.classList.toggle("gpu-mon-stale", offline);
  labelEl.textContent = `${data.name || "?"} (${data.gpu || "?"})` + (data.version ? ` · v${data.version}` : "");

  // bot9, commit 01ebcd2f: verze agenta uz chodi spolehlive - stara verze
  // je dalsi zdroj "GPU teplota se nehlasi" vedle offline/zaseknuti (Robert/
  // bot3: "napiš, jak staré to číslo je, nebo to zašedni" plati i tady).
  const banners = [];
  if (offline) {
    banners.push(`<div class="gpu-mon-offline-banner">Stanice offline - naposledy hlášeno před ${gpuMonFmtAge(data.last_seen_s)}. Čísla níže NEJSOU aktuální.</div>`);
  } else if (stuck) {
    banners.push(`<div class="gpu-mon-stale-banner">Agent žije, ale nebere si práci (zaseknutý) - teplota/zatížení jsou i tak čerstvá.</div>`);
  }
  if (versionMismatch) {
    banners.push(`<div class="gpu-mon-stale-banner">Agent běží na staré verzi (v${data.version}, server má v${data.expected_version}) - po restartu se sám aktualizuje.</div>`);
  }
  errEl.innerHTML = banners.join("");

  // Ofline = posledni znama data se porad zobrazi (uzitecne "kde
  // skoncila", ne "co dela ted"), ale `.gpu-mon-stale` na panelu (vyse)
  // je vizualne zasedi - nezvyraznovat je tedy jeste barvou teploty.
  const tempClass = offline ? "gpu-mon-ok" : gpuMonTempClass(data.gpu_temp_c, data.gpu_teplota_prah_c);
  statsEl.innerHTML = [
    gpuMonStatCell("Teplota", data.gpu_temp_c != null ? Math.round(data.gpu_temp_c) : null, "°C", tempClass),
    gpuMonStatCell("Zatížení", data.gpu_util_pct != null ? Math.round(data.gpu_util_pct) : null, "%"),
    gpuMonStatCell("Takt", data.gpu_clock_mhz != null ? Math.round(data.gpu_clock_mhz) : null, " MHz"),
    gpuMonStatCell("Ventilátor", data.gpu_fan_pct != null ? Math.round(data.gpu_fan_pct) : null, "%"),
  ].join("") + `<div class="gpu-mon-stat"><div class="gpu-mon-stat-label">Poslední hlášení</div><span class="gpu-mon-stat-value gpu-mon-missing" style="font-size:14px;">před ${gpuMonFmtAge(data.last_seen_s)}</span></div>`;

  const canvas = document.getElementById("gpuMonitorChart");
  if (canvas) {
    const rectW = canvas.getBoundingClientRect().width;
    if (rectW > 0 && Math.abs(canvas.width - rectW) > 4) canvas.width = Math.round(rectW);
    gpuMonDrawChart(canvas, data.gpu_historie, data.gpu_teplota_prah_c);
  }

  const n = (data.gpu_historie || []).length;
  footEl.textContent = data.gpu_fan_pct == null
    ? `Historie: ${n} vzorků (posledních ~6 h). Otáčky ventilátoru agent zatím nehlásí.`
    : `Historie: ${n} vzorků (posledních ~6 h).`;

  gpuMonRenderCurrentJob(data.current_job);
  gpuMonRenderRecentJobs(data.recent_jobs);
}

if (!gpuMonitorTimer) {
  gpuMonitorTimer = setInterval(() => {
    const dashTab = document.getElementById("tab-dashboard");
    if (dashTab && dashTab.classList.contains("active") && !document.hidden) loadGpuMonitorPanel();
  }, 20000);
}
