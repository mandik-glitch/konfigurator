/* Přehledy > Geometrie - pravidla a postupy   (bot8, 2026-09-21)
 *
 * Robert: "pravidla postupy pro geometrii chci mít na nějaké tabuli v adminu
 * v přehledu" + "tak abych to mohl kdykoli editovat".
 *
 * Proč vlastní záložka a ne rozšíření "Pravidla/Postupy": ta obrazovka je
 * VÝBĚROVÁ (odklikáváš, co se má zobrazovat) a míchá .md kandidáty s DB
 * recepty. Tahle je EDITAČNÍ a jen nad recepty geometrie.
 *
 * Edituje se PO ČÁSTECH (jeden klíč JSON `definition`) - stejná zrnitost,
 * v jaké byly recepty 2026-09-21 rozděleny. Obsah se nikam nekopíruje, čte
 * se živě; každá změna povýší `version` a uloží předchozí znění do
 * `recept_historie`, takže jde vrátit.
 */
(function () {
  const API = "/api/admin/pravidla-postupy";
  let recepty = [];
  let otevreny = null;   // {tabulka, id}

  function el(id) { return document.getElementById(id); }
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, c =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }
  function chyba(t) { const e = el("geoErr"); if (e) e.textContent = t || ""; }

  async function nactiSeznam() {
    chyba("");
    const r = await fetch(`${API}/strom`);
    if (!r.ok) { chyba("Nepodařilo se načíst strom pravidel."); return; }
    const d = await r.json();
    vykresliStrom(d.strom || []);
  }

  /* Strom podle významu (Robert 2026-09-21: "ať se stejné shlukují do jedné
     větve"). Zařazení je DATA (sloupec `kategorie`), ne struktura v kódu -
     dá se přerovnat rovnou tady, bez zásahu do kódu. */
  function vykresliStrom(strom) {
    const box = el("geoSeznam");
    if (!box) return;
    if (!strom.length) { box.innerHTML = '<p class="hint">Žádná pravidla nenalezena.</p>'; return; }
    box.innerHTML = strom.map(v => `
      <div class="geo-vetev" data-vetev="${esc(v.nazev)}">
        <div class="geo-vetev-hlava">
          <span class="geo-sipka">▾</span>
          <span class="geo-vetev-nazev">${esc(v.nazev)}</span>
          <span class="geo-meta">${v.pocet} ${v.pocet === 1 ? "pravidlo" : (v.pocet < 5 ? "pravidla" : "pravidel")}</span>
        </div>
        <div class="geo-vetev-telo">
          ${v.podvetve.map(pv => `
            ${pv.nazev ? `<div class="geo-podvetev-nazev">${esc(pv.nazev)}</div>` : ""}
            ${pv.recepty.map(p => `
              <div class="geo-radek" data-tabulka="${esc(p.tabulka)}" data-id="${p.id}"
                   data-kategorie="${esc(p.kategorie)}">
                <div class="geo-radek-hlava">
                  <span class="geo-nazev">${esc(p.nazev)}</span>
                  <span style="display:flex;gap:6px;">
                    <button type="button" class="geo-presunout" title="Změnit zařazení ve stromu">Přeřadit</button>
                    <button type="button" class="geo-otevri">Otevřít</button>
                  </span>
                </div>
                <div class="geo-meta">verze ${p.verze} · ${p.klicu} ${p.klicu === 1 ? "část" : (p.klicu < 5 ? "části" : "částí")}
                  · ${p.overil ? "ověřil " + esc(p.overil) : "zatím neověřeno"}</div>
                ${p.popis ? `<div class="geo-popis">${esc(p.popis)}</div>` : ""}
              </div>`).join("")}`).join("")}
        </div>
      </div>`).join("");

    box.querySelectorAll(".geo-vetev-hlava").forEach(h => h.addEventListener("click", e => {
      if (e.target.closest("button")) return;
      const v = h.closest(".geo-vetev");
      v.classList.toggle("geo-zavreno");
      h.querySelector(".geo-sipka").textContent = v.classList.contains("geo-zavreno") ? "▸" : "▾";
    }));
    box.querySelectorAll(".geo-otevri").forEach(b => b.addEventListener("click", () => {
      const r = b.closest(".geo-radek");
      otevriRecept(r.dataset.tabulka, parseInt(r.dataset.id, 10));
    }));
    box.querySelectorAll(".geo-presunout").forEach(b => b.addEventListener("click", async () => {
      const r = b.closest(".geo-radek");
      const nova = prompt(
        "Zařazení ve stromu (Větev nebo Větev/Podvětev, prázdné = Nezařazené):",
        r.dataset.kategorie || "");
      if (nova === null) return;
      const res = await fetch(`${API}/recept/${encodeURIComponent(r.dataset.tabulka)}/${r.dataset.id}/kategorie`, {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ kategorie: nova }),
      });
      const d = await res.json().catch(() => ({}));
      if (!res.ok) { chyba(d.error || "Přeřazení selhalo."); return; }
      nactiSeznam();
    }));
  }

  async function otevriRecept(tabulka, id) {
    otevreny = { tabulka, id };
    chyba("");
    const r = await fetch(`${API}/recept/${encodeURIComponent(tabulka)}/${id}/casti`);
    if (!r.ok) { chyba("Recept se nepodařilo načíst k editaci."); return; }
    const d = await r.json();
    const det = el("geoDetail");
    det.style.display = "";
    det.innerHTML = `
      <div class="geo-detail-hlava">
        <div>
          <div class="geo-detail-nazev">${esc(d.nazev)}</div>
          <div class="geo-meta">verze ${d.verze} · ověřil: ${esc(d.overil || "zatím nikdo")} · zapsal ${esc(d.zapsal || "?")}</div>
        </div>
        <div style="display:flex;gap:8px;">
          <button type="button" id="geoPridat">+ Přidat pravidlo</button>
          <button type="button" id="geoHistorie">Historie změn</button>
          <button type="button" id="geoZavrit">Zavřít</button>
        </div>
      </div>
      <div id="geoCasti">${d.casti.map(vykresliCast).join("")}</div>
      <div id="geoHistorieBox" style="display:none;margin-top:16px;"></div>`;
    napojUdalosti();
  }

  function vykresliCast(c) {
    if (c.typ === "skupina") {
      return `<div class="geo-cast geo-cast-skupina"><div class="geo-cesta">${esc(c.cesta)}
        <span class="geo-meta">(${c.podcasti} podčástí)</span></div></div>`;
    }
    return `<div class="geo-cast" data-cesta="${esc(c.cesta)}" data-json="${c.typ === "json" ? 1 : 0}">
      <div class="geo-cast-hlava">
        <span class="geo-cesta">${esc(c.cesta)}</span>
        <span>
          <button type="button" class="geo-upravit">Upravit</button>
          <button type="button" class="geo-smazat">Smazat</button>
        </span>
      </div>
      <div class="geo-text">${esc(c.hodnota)}</div>
    </div>`;
  }

  function napojUdalosti() {
    el("geoZavrit").addEventListener("click", () => {
      el("geoDetail").style.display = "none"; otevreny = null;
    });
    el("geoPridat").addEventListener("click", pridatPravidlo);
    el("geoHistorie").addEventListener("click", zobrazHistorii);
    document.querySelectorAll("#geoCasti .geo-upravit").forEach(b =>
      b.addEventListener("click", () => zapniEditaci(b.closest(".geo-cast"))));
    document.querySelectorAll("#geoCasti .geo-smazat").forEach(b =>
      b.addEventListener("click", () => smazat(b.closest(".geo-cast"))));
  }

  function zapniEditaci(cast) {
    if (cast.querySelector("textarea")) return;
    const textEl = cast.querySelector(".geo-text");
    const puvodni = textEl.textContent;
    textEl.innerHTML = `
      <textarea class="geo-edit">${esc(puvodni)}</textarea>
      <div style="margin-top:6px;display:flex;gap:8px;">
        <button type="button" class="geo-ulozit">Uložit</button>
        <button type="button" class="geo-zrusit">Zrušit</button>
      </div>`;
    textEl.querySelector(".geo-zrusit").addEventListener("click", () => { textEl.textContent = puvodni; });
    textEl.querySelector(".geo-ulozit").addEventListener("click", async () => {
      const nova = textEl.querySelector("textarea").value;
      if (nova === puvodni) { textEl.textContent = puvodni; return; }
      await uloz(cast.dataset.cesta, nova, "upravit", cast.dataset.json === "1");
    });
  }

  async function uloz(cesta, hodnota, akce, jakoJson) {
    chyba("");
    const r = await fetch(`${API}/recept/${encodeURIComponent(otevreny.tabulka)}/${otevreny.id}/cast`, {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ cesta, hodnota, akce, jako_json: !!jakoJson }),
    });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) { chyba(d.error || "Uložení selhalo."); return false; }
    await otevriRecept(otevreny.tabulka, otevreny.id);
    return true;
  }

  async function pridatPravidlo() {
    const cesta = prompt("Název nového pravidla (klíč, bez mezer - tečka = zanoření):");
    if (!cesta) return;
    const hodnota = prompt("Znění pravidla:");
    if (!hodnota) return;
    await uloz(cesta.trim(), hodnota, "pridat", false);
  }

  async function smazat(cast) {
    if (!confirm(`Opravdu smazat pravidlo "${cast.dataset.cesta}"?\n\nPůjde vrátit přes Historii změn.`)) return;
    await uloz(cast.dataset.cesta, "", "smazat", false);
  }

  async function zobrazHistorii() {
    const box = el("geoHistorieBox");
    if (box.style.display !== "none") { box.style.display = "none"; return; }
    const r = await fetch(`${API}/recept/${encodeURIComponent(otevreny.tabulka)}/${otevreny.id}/historie`);
    if (!r.ok) { chyba("Historii se nepodařilo načíst."); return; }
    const d = await r.json();
    box.style.display = "";
    if (!(d.historie || []).length) { box.innerHTML = '<p class="hint">Zatím žádná ruční editace.</p>'; return; }
    box.innerHTML = `<table class="geo-hist"><thead><tr>
        <th>Kdy</th><th>Kdo</th><th>Co</th><th>Akce</th><th>Verze</th><th></th>
      </tr></thead><tbody>${d.historie.map(h => `
        <tr><td>${esc((h.kdy || "").replace("T", " ").slice(0, 16))}</td>
            <td>${esc(h.kdo)}</td><td><code>${esc(h.cesta)}</code></td>
            <td>${esc(h.akce)}</td><td>${h.verze_pred} → ${h.verze_po}</td>
            <td><button type="button" class="geo-vratit" data-hid="${h.id}">Vrátit</button></td></tr>`).join("")}
      </tbody></table>`;
    box.querySelectorAll(".geo-vratit").forEach(b => b.addEventListener("click", async () => {
      if (!confirm("Vrátit tuhle změnu zpět?")) return;
      const r2 = await fetch(`${API}/recept/${encodeURIComponent(otevreny.tabulka)}/${otevreny.id}/vratit/${b.dataset.hid}`, { method: "POST" });
      const d2 = await r2.json().catch(() => ({}));
      if (!r2.ok) { chyba(d2.error || "Vrácení selhalo."); return; }
      await otevriRecept(otevreny.tabulka, otevreny.id);
    }));
  }

  window.loadGeoPravidla = nactiSeznam;
  document.addEventListener("DOMContentLoaded", () => {
    const b = el("geoRefresh");
    if (b) b.addEventListener("click", nactiSeznam);
  });
})();
