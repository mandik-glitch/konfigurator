// ==================== SOCIALNI SITE (Robert 2026-07-31) ====================
async function loadOgSettings() {
  try {
    const r = await fetch("/api/admin/og-settings");
    const data = await r.json();
    document.getElementById("ogTitle").value = data.title || "";
    document.getElementById("ogDescription").value = data.description || "";
    document.getElementById("ogImage").value = data.image || "";
    updateOgImagePreview();
  } catch (e) {}
}
function updateOgImagePreview() {
  const img = document.getElementById("ogImagePreview");
  const val = document.getElementById("ogImage").value.trim();
  if (val) { img.src = val; img.style.display = ""; } else { img.style.display = "none"; }
}
document.getElementById("ogImage").addEventListener("input", updateOgImagePreview);
document.getElementById("btnSaveOgSettings").onclick = async () => {
  const errEl = document.getElementById("ogSettingsErr");
  const statusEl = document.getElementById("ogSettingsStatus");
  errEl.textContent = ""; statusEl.textContent = "Ukládám…";
  const body = {
    title: document.getElementById("ogTitle").value.trim(),
    description: document.getElementById("ogDescription").value.trim(),
    image: document.getElementById("ogImage").value.trim(),
  };
  const r = await fetch("/api/admin/og-settings", {
    method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) { errEl.textContent = data.error || "Chyba."; statusEl.textContent = ""; return; }
  statusEl.textContent = "Uloženo ✓";
  setTimeout(() => { statusEl.textContent = ""; }, 1600);
};

let socialPostsCache = [];
const socialPostsSelectedIds = new Set();
const SOCIAL_STATUS_LABELS = { planned: "Naplánováno", sent: "Odesláno", failed: "Selhalo", cancelled: "Zrušeno" };

async function loadSocialPosts() {
  try {
    const r = await fetch("/api/admin/social-posts");
    const data = await r.json();
    socialPostsCache = data.posts || [];
    renderSocialPosts();
  } catch (e) {}
}
function renderSocialPosts() {
  const tbody = document.getElementById("socialPostsTbody");
  tbody.innerHTML = socialPostsCache.map(p => `
    <tr>
      <td><input type="checkbox" class="social-post-check" data-id="${p.id}" ${socialPostsSelectedIds.has(p.id) ? "checked" : ""}></td>
      <td>${escapeHtmlAdmin(p.platform)}</td>
      <td class="wrap-ok">${escapeHtmlAdmin((p.message || "").slice(0, 120))}${(p.message || "").length > 120 ? "…" : ""}</td>
      <td>${p.scheduled_at ? new Date(p.scheduled_at).toLocaleString("cs-CZ") : ""}</td>
      <td>${SOCIAL_STATUS_LABELS[p.status] || p.status}</td>
      <td><button class="danger social-post-delete" data-id="${p.id}" style="padding:4px 9px;font-size:12px;">Smazat</button></td>
    </tr>
  `).join("") || `<tr><td colspan="6" style="color:var(--text-dim);">Zatím žádné naplánované příspěvky.</td></tr>`;
  tbody.querySelectorAll(".social-post-check").forEach(cb => {
    cb.onchange = () => {
      const id = parseInt(cb.dataset.id, 10);
      if (cb.checked) socialPostsSelectedIds.add(id); else socialPostsSelectedIds.delete(id);
      updateSocialPostsBulkToolbar();
    };
  });
  tbody.querySelectorAll(".social-post-delete").forEach(btn => {
    btn.onclick = async () => {
      if (!confirm("Opravdu smazat tento naplánovaný příspěvek?")) return;
      await fetch(`/api/admin/social-posts/${btn.dataset.id}`, { method: "DELETE" });
      loadSocialPosts();
    };
  });
  updateSocialPostsBulkToolbar();
}
function updateSocialPostsBulkToolbar() {
  const bar = document.getElementById("socialPostsBulkToolbar");
  const count = socialPostsSelectedIds.size;
  bar.classList.toggle("active", count > 0);
  document.getElementById("socialPostsBulkCount").textContent = `${count} vybráno`;
}
document.getElementById("socialPostsSelectAll").onchange = (e) => {
  if (e.target.checked) socialPostsCache.forEach(p => socialPostsSelectedIds.add(p.id));
  else socialPostsSelectedIds.clear();
  renderSocialPosts();
};
document.getElementById("socialPostsBulkDelete").onclick = async () => {
  if (!socialPostsSelectedIds.size) return;
  if (!confirm(`Opravdu smazat ${socialPostsSelectedIds.size} vybraných příspěvků?`)) return;
  await fetch("/api/admin/social-posts/bulk-delete", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ids: [...socialPostsSelectedIds] }),
  });
  socialPostsSelectedIds.clear();
  loadSocialPosts();
};
document.getElementById("btnAddSocialPost").onclick = async () => {
  const errEl = document.getElementById("socialPostsErr");
  errEl.textContent = "";
  const message = document.getElementById("newSocialMessage").value.trim();
  const scheduledAt = document.getElementById("newSocialScheduledAt").value;
  if (!message) { errEl.textContent = "Chybí text příspěvku."; return; }
  if (!scheduledAt) { errEl.textContent = "Chybí datum naplánování."; return; }
  const body = {
    platform: document.getElementById("newSocialPlatform").value,
    message,
    image_filename: document.getElementById("newSocialImage").value.trim() || null,
    scheduled_at: scheduledAt.replace("T", " ") + ":00",
  };
  const r = await fetch("/api/admin/social-posts", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) { errEl.textContent = data.error || "Chyba."; return; }
  document.getElementById("newSocialMessage").value = "";
  document.getElementById("newSocialImage").value = "";
  document.getElementById("newSocialScheduledAt").value = "";
  loadSocialPosts();
};
